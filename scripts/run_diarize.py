"""Standalone diarization script — runs pyannote.audio in a clean process
to avoid CTranslate2/PyTorch CUDA heap corruption."""
import os
import sys
import json
import time
import subprocess
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.settings import (
    HF_TOKEN, DIARIZATION_MODEL,
    DIARIZATION_NUM_SPEAKERS, DIARIZATION_MIN_SPEAKERS, DIARIZATION_MAX_SPEAKERS,
)

def load_audio_ffmpeg(audio_path, sample_rate=16000):
    import torch
    print(f"[audio] Loading audio via FFmpeg (sr={sample_rate})...", flush=True)
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", "1", "-ar", str(sample_rate),
        "-loglevel", "error", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {proc.stderr.decode()}")
    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    waveform = torch.from_numpy(audio).unsqueeze(0)
    print(f"[audio] Loaded {waveform.shape[1]/sample_rate:.1f}s ({waveform.shape[1]} samples)", flush=True)
    return waveform, sample_rate

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("transcript_json", help="Path to existing transcript JSON")
    parser.add_argument("--hf-token", default=None)
    parser.add_argument("--num-speakers", type=int, default=None)
    args = parser.parse_args()

    import torch
    from pyannote.audio import Pipeline

    token = args.hf_token or HF_TOKEN
    if not token:
        print("[diarize] ERROR: No HF_TOKEN", flush=True)
        sys.exit(1)

    # Load transcript
    with open(args.transcript_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data["segments"]

    # Load audio
    waveform, sr = load_audio_ffmpeg(args.video_path)
    audio_input = {"waveform": waveform, "sample_rate": sr}

    # Load and run diarization
    print(f"[diarize] Loading pipeline '{DIARIZATION_MODEL}'...", flush=True)
    pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, token=token)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    print(f"[diarize] Running on {device}...", flush=True)

    kwargs = {}
    num_spk = args.num_speakers or DIARIZATION_NUM_SPEAKERS
    if num_spk:
        kwargs["num_speakers"] = num_spk
    if DIARIZATION_MIN_SPEAKERS:
        kwargs["min_speakers"] = DIARIZATION_MIN_SPEAKERS
    if DIARIZATION_MAX_SPEAKERS:
        kwargs["max_speakers"] = DIARIZATION_MAX_SPEAKERS

    t0 = time.time()
    try:
        diarization = pipeline(audio_input, **kwargs)
    except torch.cuda.OutOfMemoryError:
        print("[diarize] CUDA OOM, falling back to CPU...", flush=True)
        torch.cuda.empty_cache()
        pipeline.to(torch.device("cpu"))
        diarization = pipeline(audio_input, **kwargs)

    # pyannote 4.x returns DiarizeOutput dataclass — use .serialize()
    serialized = diarization.serialize()
    speaker_segments = serialized["diarization"]

    speakers = sorted(set(s["speaker"] for s in speaker_segments))
    print(f"[diarize] Done in {time.time()-t0:.1f}s | {len(speaker_segments)} turns, {len(speakers)} speakers: {', '.join(speakers)}", flush=True)

    # Assign speakers to transcript segments
    for seg in segments:
        best_speaker = None
        max_overlap = 0
        for ds in speaker_segments:
            overlap = max(0, min(seg["end"], ds["end"]) - max(seg["start"], ds["start"]))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = ds["speaker"]
        seg["speaker"] = best_speaker or "UNKNOWN"

    # Rebuild text with speaker labels
    current_speaker = None
    text_parts = []
    for seg in segments:
        if seg.get("speaker") != current_speaker:
            current_speaker = seg["speaker"]
            text_parts.append(f"\n[{current_speaker}]: {seg['text']}")
        else:
            text_parts.append(seg["text"])
    data["text"] = " ".join(text_parts).strip()
    data["segments"] = segments
    data["diarization"] = True

    # Overwrite outputs
    base = args.transcript_json.replace("_transcript.json", "")

    with open(f"{base}_transcript.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(f"{base}_transcript.txt", "w", encoding="utf-8") as f:
        f.write(data["text"])

    with open(f"{base}_transcript_timestamped.txt", "w", encoding="utf-8") as f:
        for seg in segments:
            start = _fmt(seg["start"])
            end = _fmt(seg["end"])
            spk = seg.get("speaker", "")
            if spk:
                f.write(f"[{start} -> {end}] {spk}: {seg['text']}\n")
            else:
                f.write(f"[{start} -> {end}] {seg['text']}\n")

    print(f"[diarize] Saved diarized transcripts.", flush=True)

def _fmt(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h}:{m:02d}:{sec:02d}" if h > 0 else f"{m}:{sec:02d}"

if __name__ == "__main__":
    main()

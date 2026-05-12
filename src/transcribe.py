"""
Audio Transcription Module - CUDA-Accelerated via faster-whisper
Extracts and transcribes audio from video files using the GPU.
"""
import os
import sys
import json
import time
import site
import subprocess

# Add NVIDIA CUDA DLLs to PATH so CTranslate2 can find cublas64_12.dll
_sp = site.getusersitepackages()
for _subdir in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_runtime/bin"):
    _dll_path = os.path.join(_sp, _subdir)
    if os.path.isdir(_dll_path):
        os.environ["PATH"] = _dll_path + os.pathsep + os.environ.get("PATH", "")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    WHISPER_BEAM_SIZE, WHISPER_LANGUAGE, TRANSCRIPTS_DIR,
    HF_TOKEN, DIARIZATION_MODEL, DIARIZATION_NUM_SPEAKERS,
    DIARIZATION_MIN_SPEAKERS, DIARIZATION_MAX_SPEAKERS,
)


def _load_audio_ffmpeg(audio_path: str, sample_rate: int = 16000):
    """
    Load audio from any media file using FFmpeg subprocess.
    Bypasses torchcodec entirely — works reliably on Windows.

    Returns:
        Tuple of (waveform: torch.Tensor [1, samples], sample_rate: int)
    """
    import torch
    import numpy as np

    print(f"[audio] Loading audio via FFmpeg (sr={sample_rate})...", flush=True)
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "f32le",        # raw 32-bit float PCM
        "-acodec", "pcm_f32le",
        "-ac", "1",           # mono
        "-ar", str(sample_rate),
        "-loglevel", "error",
        "-",                  # pipe to stdout
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {proc.stderr.decode()}")

    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    waveform = torch.from_numpy(audio).unsqueeze(0)  # [1, samples]
    duration = waveform.shape[1] / sample_rate
    print(f"[audio] Loaded {duration:.1f}s of audio ({waveform.shape[1]} samples)", flush=True)
    return waveform, sample_rate


def run_diarization(audio_path: str, hf_token: str = None) -> list:
    """
    Run speaker diarization on an audio/video file using pyannote.audio.

    Uses FFmpeg to load audio as a waveform tensor, bypassing torchcodec
    which is broken on Windows. Falls back to CPU if CUDA OOM occurs.

    Args:
        audio_path: Path to audio or video file
        hf_token: HuggingFace token (for gated pyannote models)

    Returns:
        List of dicts with keys: start, end, speaker
    """
    import torch
    from pyannote.audio import Pipeline

    token = hf_token or HF_TOKEN
    if not token:
        print("[diarize] ERROR: No HuggingFace token. Set HF_TOKEN env var or pass --hf-token", flush=True)
        print("[diarize] Accept model licenses at: https://hf.co/pyannote/speaker-diarization-3.1", flush=True)
        print("[diarize]                      and: https://hf.co/pyannote/segmentation-3.0", flush=True)
        return []

    # Load audio via FFmpeg (bypasses broken torchcodec on Windows)
    waveform, sample_rate = _load_audio_ffmpeg(audio_path)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}

    print(f"[diarize] Loading pipeline '{DIARIZATION_MODEL}'...", flush=True)
    pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, token=token)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    print(f"[diarize] Running on {device}...", flush=True)

    diarize_start = time.time()

    # Build kwargs for num_speakers control
    kwargs = {}
    if DIARIZATION_NUM_SPEAKERS:
        kwargs["num_speakers"] = DIARIZATION_NUM_SPEAKERS
    if DIARIZATION_MIN_SPEAKERS:
        kwargs["min_speakers"] = DIARIZATION_MIN_SPEAKERS
    if DIARIZATION_MAX_SPEAKERS:
        kwargs["max_speakers"] = DIARIZATION_MAX_SPEAKERS

    # Run with CUDA OOM fallback to CPU
    try:
        diarization = pipeline(audio_input, **kwargs)
    except torch.cuda.OutOfMemoryError:
        print("[diarize] CUDA OOM! Falling back to CPU...", flush=True)
        torch.cuda.empty_cache()
        pipeline.to(torch.device("cpu"))
        diarization = pipeline(audio_input, **kwargs)

    # pyannote 4.x returns DiarizeOutput with .speaker_diarization attribute
    # pyannote 3.x returns Annotation directly with .itertracks()
    annotation = getattr(diarization, "speaker_diarization", diarization)

    # Convert to list of segments
    speaker_segments = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        speaker_segments.append({
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker,
        })

    elapsed = time.time() - diarize_start
    speakers = sorted(set(s["speaker"] for s in speaker_segments))
    print(f"[diarize] Done in {elapsed:.1f}s | {len(speaker_segments)} turns, {len(speakers)} speakers: {', '.join(speakers)}", flush=True)

    return speaker_segments


def assign_speakers(transcript_segments: list, speaker_segments: list) -> list:
    """
    Assign speaker labels to transcript segments based on timestamp overlap.

    For each transcript segment, finds the diarization segment with the greatest
    temporal overlap and assigns that speaker.

    Args:
        transcript_segments: List of dicts with start, end, text
        speaker_segments: List of dicts with start, end, speaker (from diarization)

    Returns:
        transcript_segments updated in-place with 'speaker' key added
    """
    for seg in transcript_segments:
        best_speaker = None
        max_overlap = 0

        for ds in speaker_segments:
            # Calculate temporal overlap
            overlap_start = max(seg["start"], ds["start"])
            overlap_end = min(seg["end"], ds["end"])
            overlap = max(0, overlap_end - overlap_start)

            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = ds["speaker"]

        seg["speaker"] = best_speaker or "UNKNOWN"

    return transcript_segments


def _save_outputs(segments, full_text, info, elapsed, output_dir, video_path,
                  model_name, device, diarize):
    """Save transcript files. Separated so transcription output is saved
    even if diarization later fails."""
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    result = {
        "segments": segments,
        "text": full_text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(info.duration, 2),
        "transcription_time": round(elapsed, 2),
        "model": model_name,
        "device": device,
        "diarization": diarize,
    }

    # Plain text transcript
    txt_path = os.path.join(output_dir, f"{video_name}_transcript.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Timestamped transcript
    ts_path = os.path.join(output_dir, f"{video_name}_transcript_timestamped.txt")
    with open(ts_path, "w", encoding="utf-8") as f:
        for seg in segments:
            start_fmt = _format_time(seg["start"])
            end_fmt = _format_time(seg["end"])
            speaker = seg.get("speaker", "")
            if speaker:
                f.write(f"[{start_fmt} -> {end_fmt}] {speaker}: {seg['text']}\n")
            else:
                f.write(f"[{start_fmt} -> {end_fmt}] {seg['text']}\n")

    # JSON with full metadata
    json_path = os.path.join(output_dir, f"{video_name}_transcript.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[transcribe] Saved: {txt_path}", flush=True)
    print(f"[transcribe] Saved: {ts_path}", flush=True)
    print(f"[transcribe] Saved: {json_path}", flush=True)

    return result, txt_path, ts_path, json_path


def transcribe_video(video_path: str, output_dir: str = None, model_size: str = None,
                     diarize: bool = False, hf_token: str = None) -> dict:
    """
    Transcribe audio from a video file using faster-whisper with CUDA.
    Optionally run speaker diarization with pyannote.audio.

    Args:
        video_path: Path to the video file
        output_dir: Directory for output files (defaults to TRANSCRIPTS_DIR)
        model_size: Override whisper model size
        diarize: If True, run speaker diarization after transcription
        hf_token: HuggingFace token for diarization (or set HF_TOKEN env var)

    Returns:
        dict with keys: segments, text, language, duration
    """
    from faster_whisper import WhisperModel

    output_dir = output_dir or TRANSCRIPTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    model_name = model_size or WHISPER_MODEL
    device = WHISPER_DEVICE
    compute_type = WHISPER_COMPUTE_TYPE

    # Fallback to CPU if CUDA not available
    try:
        import torch
        if not torch.cuda.is_available():
            print("[WARN] CUDA not available, falling back to CPU (slower)", flush=True)
            device = "cpu"
            compute_type = "int8"
    except ImportError:
        # faster-whisper can use CUDA via CTranslate2 without torch
        pass

    print(f"[transcribe] Loading model '{model_name}' on {device} ({compute_type})...", flush=True)
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    print(f"[transcribe] Transcribing: {os.path.basename(video_path)}", flush=True)
    start_time = time.time()

    segments_raw, info = model.transcribe(
        video_path,
        beam_size=WHISPER_BEAM_SIZE,
        language=WHISPER_LANGUAGE,
        vad_filter=True,           # Voice activity detection - skips silence
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    # Collect segments
    segments = []
    full_text_parts = []
    for seg in segments_raw:
        segment_data = {
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        }
        segments.append(segment_data)
        full_text_parts.append(seg.text.strip())

    elapsed = time.time() - start_time
    full_text = " ".join(full_text_parts)

    print(f"[transcribe] Done in {elapsed:.1f}s | Language: {info.language} ({info.language_probability:.0%})", flush=True)
    print(f"[transcribe] Duration: {_format_time(info.duration)} | Segments: {len(segments)}", flush=True)

    # === SAVE TRANSCRIPT BEFORE freeing model or diarization ===
    # Save immediately — del model can segfault in CTranslate2/CUDA cleanup
    result, txt_path, ts_path, json_path = _save_outputs(
        segments, full_text, info, elapsed, output_dir, video_path,
        model_name, device, diarize=False,
    )
    print(f"[transcribe] Transcript saved (pre-diarization).", flush=True)

    # Free whisper model VRAM before diarization
    # Note: explicit del + empty_cache can segfault in CTranslate2 on Windows.
    # Instead, just drop the reference and let GC handle it.
    model = None
    import gc
    gc.collect()

    # Run speaker diarization if requested
    if diarize:
        print(f"[transcribe] Starting speaker diarization...", flush=True)
        try:
            speaker_segments = run_diarization(video_path, hf_token)
            if speaker_segments:
                segments = assign_speakers(segments, speaker_segments)
                # Rebuild full text with speaker labels
                current_speaker = None
                text_parts = []
                for seg in segments:
                    if seg.get("speaker") != current_speaker:
                        current_speaker = seg["speaker"]
                        text_parts.append(f"\n[{current_speaker}]: {seg['text']}")
                    else:
                        text_parts.append(seg["text"])
                full_text = " ".join(text_parts).strip()

                # Re-save with diarization data
                result, txt_path, ts_path, json_path = _save_outputs(
                    segments, full_text, info, elapsed, output_dir, video_path,
                    model_name, device, diarize=True,
                )
                speakers = sorted(set(s.get("speaker", "UNKNOWN") for s in segments))
                print(f"[transcribe] Speakers: {', '.join(speakers)}", flush=True)
                print(f"[transcribe] Transcript re-saved with speaker labels.", flush=True)
        except Exception as e:
            print(f"[diarize] ERROR: Diarization failed: {e}", flush=True)
            print(f"[diarize] Transcript without speakers was already saved.", flush=True)

    return result


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Transcribe video with optional speaker diarization")
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument("output_dir", nargs="?", default=None, help="Output directory (default: transcripts/)")
    parser.add_argument("model_size", nargs="?", default=None, help="Whisper model size override")
    parser.add_argument("--diarize", action="store_true", help="Run speaker diarization (requires HF_TOKEN)")
    parser.add_argument("--hf-token", default=None, help="HuggingFace token (or set HF_TOKEN env var)")
    parser.add_argument("--num-speakers", type=int, default=None, help="Exact number of speakers (if known)")
    args = parser.parse_args()

    if not os.path.exists(args.video_path):
        print(f"Error: Video not found: {args.video_path}")
        sys.exit(1)

    # Override speaker count if provided
    if args.num_speakers:
        import config.settings as _cfg
        _cfg.DIARIZATION_NUM_SPEAKERS = args.num_speakers

    transcribe_video(args.video_path, args.output_dir, args.model_size,
                     diarize=args.diarize, hf_token=args.hf_token)

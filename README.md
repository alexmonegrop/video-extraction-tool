# video-extraction-tool

**Local GPU-accelerated pipeline for transcribing, diarizing, and analyzing video files — designed to pair with [Claude Code](https://docs.claude.com/en/docs/claude-code)'s built-in vision.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CUDA](https://img.shields.io/badge/CUDA-12.x-76B900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)
[![faster-whisper](https://img.shields.io/badge/whisper-faster--whisper-blueviolet)](https://github.com/SYSTRAN/faster-whisper)
[![pyannote](https://img.shields.io/badge/diarization-pyannote%204.x-orange)](https://github.com/pyannote/pyannote-audio)

Drop a video in `videos/`, get back a timestamped transcript with speaker labels and a scene-aware frame extraction, then have Claude Code read the frames directly with its built-in vision to produce a combined audio + visual analysis.

Optimised for an NVIDIA RTX 4070 SUPER class GPU. ~1 minute of processing per 9 minutes of video on the transcription pass.

> **AI agents picking up this repo:** read [`AGENTS.md`](AGENTS.md) first. It's the one-page operator onboarding. Then `CLAUDE.md` for the detailed rules + gotchas.

---

## Why this exists

Off-the-shelf transcription services (otter.ai, fireflies, etc.) are fine for one-off meetings but:

- Don't combine **audio transcription** with **visual frame analysis** in a single artifact.
- Send your data to a third party.
- Cost per minute, which adds up if you process hours of long-form video.
- Can't be driven by an AI agent that also reads the resulting frames and writes the analysis.

This tool keeps everything local (no audio leaves your machine for transcription), pairs `faster-whisper` for audio with `PySceneDetect` for visual sampling, and is designed to be driven interactively by Claude Code via the `.claude/skills/` slash commands — the agent reads ~30 sampled frames with its native vision and writes a unified `_analysis.md`.

---

## What you get

- **`src/preprocess.py`** — NVENC GPU re-encode for >500MB videos (~560 MB/min, 10–15× compression).
- **`src/transcribe.py`** — `faster-whisper large-v3` on CUDA with `float16`, optional in-process diarization (`--diarize --num-speakers N`).
- **`src/extract_frames.py`** — scene-aware frame extraction via `PySceneDetect` + OpenCV.
- **`src/analyze_visual.py`** — headless-only Claude Vision API analysis (for batch / non-interactive use).
- **`src/pipeline.py`** — full orchestrator for headless runs.
- **`scripts/run_diarize.py`** — standalone diarization using `pyannote.audio` 4.x (run in a separate process to avoid the CTranslate2 + PyTorch CUDA heap-corruption bug on Windows).
- **`.claude/skills/`** — `/transcribe-video`, `/analyze-video`, `/download-video`, `/session-start`, `/session-end` slash commands.
- **`config/settings.py`** — centralised tunables (whisper model, scene detection threshold, frame dimensions, diarization model).

---

## Quickstart

### 1. Install

```bash
# CUDA-enabled PyTorch first (matches your CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Then the rest
pip install -r requirements.txt
pip install pyannote.audio  # for diarization
```

You also need:
- **FFmpeg** in PATH (e.g., `winget install Gyan.FFmpeg`)
- **NVIDIA drivers + CUDA toolkit** (12.x recommended)

### 2. Configure

Copy `.env.example` to `.env` and fill in `HF_TOKEN` (required for diarization).

You must accept the licenses for all three gated pyannote models:
- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`
- `pyannote/speaker-diarization-community-1`

### 3. Run

```bash
# Drop your video in videos/
# If >500MB, re-encode first:
python src/preprocess.py "videos/my-video.mp4"

# Transcribe with diarization (recommended for multi-speaker):
python src/transcribe.py "videos/my-video.mp4" transcripts --diarize --num-speakers 2

# Extract frames for visual analysis:
python src/extract_frames.py "videos/my-video_small.mp4"
```

Then open the directory in Claude Code and run `/analyze-video` — the agent reads ~30 sampled frames with its built-in vision and writes a combined `_analysis.md`.

---

## Performance (RTX 4070 SUPER, 12GB VRAM)

| Stage | Speed |
|---|---|
| Re-encode (NVENC) | ~560 MB/min |
| Transcription (`large-v3`, float16) | ~8.9× real-time |
| Diarization (pyannote 3.1) | ~3× real-time |
| Frame extraction (scene) | ~26K frames/min |

Full pipeline for a 2.4hr video: ~25 min local processing.

---

## Known gotchas (the file `CLAUDE.md` documents these for the agent)

- **`cublas64_12.dll` not found** — `src/transcribe.py` adds NVIDIA pip DLL dirs to PATH automatically.
- **CTranslate2 + PyTorch CUDA heap corruption (0xC0000409) on Windows** — always run diarization in a separate process via `scripts/run_diarize.py` if the in-process `--diarize` flag crashes.
- **`torchcodec` broken on Windows** — `pyannote` 4.x ships a `torchcodec` audio backend that can't find FFmpeg DLLs. Both transcribe and diarize scripts work around this by piping raw PCM through FFmpeg subprocess into numpy.
- **`pyannote` 4.x API change** — uses `token=` (not `use_auth_token=`); returns `DiarizeOutput` dataclass (not `Annotation`).
- **Exit code 127 / 0xC0000409 at end of transcription** — CTranslate2 CUDA cleanup segfaults but files **are** saved. Check for output files to verify success.
- **Quality check after diarization is mandatory** — see `.claude/skills/transcribe-video.md`. Watch for "speaker deserts" (5-min windows with only one speaker when 2+ expected → re-transcribe with `vad_filter=False`).

---

## Directory layout

```
src/                  Core pipeline modules
scripts/              Standalone runners (diarization, batch transcribe)
config/settings.py    Centralised tunables
.claude/skills/       Slash commands for Claude Code
videos/               (gitignored) — drop input videos here
videos/to-be-processed/  Staging area for new raw videos
videos/processed/     Originals + _small re-encodes after processing (auto-purged at 14d)
transcripts/          (gitignored) — per-video output folders
frames/               (gitignored) — per-video extracted frames
```

---

## Documentation

- **[`AGENTS.md`](AGENTS.md)** — one-page operator onboarding for an AI agent driving this tool.
- **[`CLAUDE.md`](CLAUDE.md)** — detailed rules, gotchas, benchmarks, configuration reference.
- **[`CHANGELOG.md`](CHANGELOG.md)** — release history.
- **[`SECURITY.md`](SECURITY.md)** — disclosure policy and what's in / out of scope.

## License

MIT. See [`LICENSE`](LICENSE).

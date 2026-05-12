# Changelog

All notable user-visible changes to this tool are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-11

First public release.

### Added

- **`src/preprocess.py`** — NVENC GPU re-encode for >500MB videos (1280px wide, CRF 28, mono 64k audio, typically 10–15× compression).
- **`src/transcribe.py`** — `faster-whisper large-v3` on CUDA with `float16`. Optional in-process diarization via `--diarize --num-speakers N`. Auto-fixes the `cublas64_12.dll` PATH issue by adding NVIDIA pip DLL dirs.
- **`src/extract_frames.py`** — Scene-aware frame extraction via PySceneDetect + OpenCV, plus interval mode for low-visual-change videos (meetings, webcam).
- **`src/analyze_visual.py`** — Headless-only Claude Vision API path for batch / non-interactive runs.
- **`src/pipeline.py`** — Full headless orchestrator.
- **`scripts/run_diarize.py`** — Standalone diarization using pyannote.audio 4.x. Runs in a separate process to avoid the CTranslate2 + PyTorch CUDA heap-corruption bug on Windows. Loads audio via FFmpeg subprocess → raw PCM → numpy → torch tensor to work around the broken torchcodec backend.
- **`.claude/skills/`** — `/transcribe-video`, `/analyze-video`, `/download-video`, `/session-start`, `/session-end` slash commands for Claude Code.
- **`config/settings.py`** — Centralised tunables (whisper model, device, compute type, scene detection threshold, max frame dimension, diarization model).
- **Documentation** — `README.md`, `CLAUDE.md` (detailed AI-agent rules + gotchas + benchmarks), `AGENTS.md` (one-page AI-operator onboarding), `.env.example`, `LICENSE` (MIT).
- **GitHub community standards** — `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml`, `SECURITY.md`, this `CHANGELOG.md`.

### Documented gotchas (worth reading before first run)

- `cublas64_12.dll not found` — auto-fixed by `src/transcribe.py`.
- CTranslate2 + PyTorch CUDA heap corruption (0xC0000409) on Windows — diarize in a separate process via `scripts/run_diarize.py` if `--diarize` crashes.
- `torchcodec` broken on Windows in pyannote 4.x — worked around with FFmpeg subprocess → raw PCM.
- pyannote 4.x API change — `token=` (not `use_auth_token=`); returns `DiarizeOutput` dataclass (not `Annotation`).
- Exit code 127 / 0xC0000409 at end of transcription — CTranslate2 CUDA cleanup segfaults but files **are** saved. Verify by checking outputs.

### Notes

- This is a working tool, not a template. Per-run content (`videos/`, `transcripts/`, `frames/`) is gitignored. Drop your own videos in and run the pipeline.
- Optimised for an NVIDIA RTX 4070 SUPER class GPU (12GB VRAM). Lower-VRAM cards may need a smaller whisper model — change `WHISPER_MODEL` in `config/settings.py`.

[1.0.0]: https://github.com/alexmonegrop/video-extraction-tool/releases/tag/v1.0.0

# AGENTS.md — How an AI Agent Operates This Repo

This document is the canonical onboarding for an AI agent (Claude Code, or any compatible agent) operating this repository. It is intentionally written for the AI to read, not the human. If you're a human, this is also the best one-page mental model.

If you're a fresh AI session that has just been pointed at this repo: read this file first, then `CLAUDE.md` (which has the detailed tool docs and the gotchas), then carry on.

---

## What This Repo Is

A **local GPU video pipeline**. It is not a template, not a service — it is the working tool. The agent's job is to drive it interactively:

1. Take a video the user has dropped in `videos/` (or `videos/to-be-processed/`).
2. Re-encode it if it's >500MB (NVENC GPU, ~560 MB/min).
3. Transcribe it with `faster-whisper large-v3` on CUDA.
4. Diarize it with `pyannote.audio` 4.x (separate process — see gotchas).
5. Extract frames with `PySceneDetect` (or fixed interval).
6. **Read ~30 sampled frames directly with your built-in vision tool**, plus the transcript, then write a unified `_analysis.md`.

The human user is the strategist (which video, which speakers, what the analysis is for). The agent is the operator.

---

## The Layer Model

| Layer | Location | Purpose | Loading |
|-------|----------|---------|---------|
| **Project rules** | `CLAUDE.md` | All hard rules + gotchas + benchmarks | Auto-loaded every session |
| **Skills** | `.claude/skills/*.md` | Invokable workflows (`/transcribe-video`, `/analyze-video`, `/download-video`, `/session-start`, `/session-end`) | Loaded on slash invocation |
| **Pipeline modules** | `src/*.py` | Re-encode, transcribe, frame-extract, headless-analyze, orchestrate | Run via subprocess |
| **Standalone runners** | `scripts/*.py`, `scripts/*.bat` | Diarization (separate-process workaround), wrapper batch files | Run on demand |
| **Config** | `config/settings.py` | All tunables — whisper model, scene threshold, frame dimensions, diarization model | Imported by modules |

Secrets live in `.env` (gitignored). The only required one is `HF_TOKEN` for pyannote diarization. `ANTHROPIC_API_KEY` is optional and only needed for the headless `src/analyze_visual.py` path.

---

## Bootstrapping Your Session

When a session starts:

1. **Run `/session-start`** if it hasn't run yet. The skill inventories the staging directories (`videos/to-be-processed/`, `videos/`) and reports what's awaiting work.
2. **Read `CLAUDE.md`** — it has the diarization gotchas (CTranslate2 + PyTorch CUDA heap corruption, torchcodec FFmpeg issue, pyannote 4.x API changes) that you WILL hit if you skip it.
3. **Confirm CUDA is available** before anything else. The pipeline is configured for an NVIDIA RTX 4070 SUPER class GPU (12GB VRAM, CUDA 12.x). Without CUDA, transcription will be ~30× slower and diarization will not run.

---

## The Invariants (do not break these)

- **Use CUDA**: `device="cuda"`, `compute_type="float16"`. Never fall back to CPU silently.
- **Use `faster-whisper`, never `openai-whisper`**: 4× faster on the same hardware. Same accuracy.
- **Use `large-v3`**: 12GB VRAM is enough; `base` is a waste.
- **Re-encode >500MB videos first**: OpenCV crashes on large files; NVENC re-encode at 1280px wide / CRF 28 / mono 64k typically achieves 10–15× compression.
- **Diarization runs in a separate process**: in-process diarization after transcription crashes with heap corruption on Windows. Use `scripts/run_diarize.py` after `src/transcribe.py` if the `--diarize` flag crashes.
- **Always pass `--num-speakers N` when you know the count**: prevents spurious extra speakers.
- **Use built-in vision for interactive analysis**: do NOT call the Anthropic API for frame analysis when running inside Claude Code. Read the frame jpgs directly with the Read tool — it's free and higher quality.
- **Sample, don't read everything**: ~30 frames spread across the timeline is enough for visual analysis. Reading 100+ frames wastes context.
- **All outputs go in `transcripts/<video_name>/`**: never write to repo root.
- **All frames go in `frames/<video_name>/`**: per-video subdir.
- **Run the quality check after every transcription**: see `.claude/skills/transcribe-video.md` for the criteria. Watch for "speaker deserts" (5-min windows with only one speaker when 2+ expected → re-transcribe with `vad_filter=False`).

---

## The Five Skills

| Skill | When to invoke |
|---|---|
| `/session-start` | First thing every session — inventories pending work |
| `/transcribe-video` | User wants audio transcript with optional diarization |
| `/analyze-video` | User wants the combined audio + visual `_analysis.md` |
| `/download-video` | User has a URL (YouTube, etc.) and wants it pulled into `videos/` |
| `/session-end` | Archive processed originals to `videos/processed/`, purge files older than 14 days, summarise |

---

## Privacy Posture

The data directories (`videos/`, `transcripts/`, `frames/`) are **gitignored** for a reason: meeting transcripts and frames contain real participant names, conversations, and visual identification. The agent must never:

- Echo a transcript or analysis file into chat unless the user explicitly asks.
- Suggest committing anything from these directories.
- Move files from `transcripts/` out of the per-video subfolder structure.

If the user asks you to share an analysis output externally (a Slack paste, an email, etc.), confirm before doing so — the default assumption is local-only.

---

## When You're Done

`/session-end` is not optional. It enforces the cleanup discipline: archive processed originals, purge stale files, summarise what changed. Without it, `videos/` fills up with multi-GB files and the pipeline gets confused about which file is which.

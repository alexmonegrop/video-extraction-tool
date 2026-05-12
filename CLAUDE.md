# Video Extraction & Analysis Tool

## Project Purpose
Analyze video files by combining **audio transcription** (faster-whisper + CUDA) with **visual frame analysis** (Claude Code's built-in vision) to produce comprehensive video summaries.

## Hardware
- **GPU**: NVIDIA RTX 4070 SUPER (12GB VRAM, CUDA 13.1) - ALWAYS use CUDA acceleration
- **Python**: 3.14 (all packages confirmed working)
- **FFmpeg**: 8.0.1 via WinGet, in PATH

## Quick Start Workflow (Interactive with Claude Code)
1. User places video in `videos/` folder
2. If multi-part: re-encode each part, then merge with FFmpeg concat demuxer (see Merging below)
3. If >500MB: `python src/preprocess.py "videos/video.mp4"` (re-encode with NVENC GPU)
4. Transcribe: `python src/transcribe.py "videos/video.mp4" transcripts`
5. Diarize (separate process — required for speaker ID):
   ```bash
   python scripts/run_diarize.py "videos/video.mp4" "transcripts/video_transcript.json" --hf-token %HF_TOKEN% --num-speakers 2
   ```
6. Extract frames: `python src/extract_frames.py "videos/video_small.mp4"`
7. Claude Code reads ~30 sampled frames directly (Read tool on jpgs) and the transcript
8. Claude Code writes the analysis to `transcripts/<name>_analysis.md`

### Merging Multi-Part Videos
When a video is split into parts (e.g., `lecture-part1.mp4`, `lecture-part2.mp4`):
1. Re-encode each part: `python src/preprocess.py "videos/to-be-processed/part1.mp4"`
2. Create a concat list file (`concat_list.txt`):
   ```
   file 'part1_small.mp4'
   file 'part2_small.mp4'
   ```
3. Merge: `ffmpeg -f concat -safe 0 -i concat_list.txt -c copy "videos/merged.mp4"`
4. Process the merged file through the normal pipeline

## Visual Analysis: USE BUILT-IN VISION (No API Key Needed)
**Claude Code has native vision.** Do NOT use the Anthropic API for visual analysis during interactive sessions. Instead:
1. Run frame extraction (creates jpgs in `frames/<video_name>/`)
2. Sample ~30 frames across the timeline (don't need all of them)
3. Read them directly with the Read tool - Claude Code sees the images
4. Read the transcript for audio context
5. Write the combined analysis as markdown

The `src/analyze_visual.py` module exists for **automated/headless** batch processing only (requires ANTHROPIC_API_KEY). For interactive use, direct vision is preferred - it's free and higher quality.

## Directory Structure
```
videos/              -> EMPTY (only subfolders, no loose files). _small.mp4 lives here only during active processing.
videos/to-be-processed/ -> Staging area for new raw video files before processing
videos/processed/    -> ALL video files (originals + _small.mp4) moved here after full processing; auto-purged after 14 days
transcripts/         -> Output transcripts and analysis files (per-video subfolders)
frames/              -> Extracted video frames (per-video subdirs)
src/
  preprocess.py      -> Re-encode large videos (NVENC GPU, 15x compression)
  transcribe.py      -> Audio transcription (faster-whisper, CUDA, large-v3)
  extract_frames.py  -> Scene-aware frame extraction (OpenCV + PySceneDetect)
  analyze_visual.py  -> Claude Vision API frame analysis (headless/automated only)
  pipeline.py        -> Full pipeline orchestrator (headless mode)
scripts/
  run_diarize.py     -> Standalone speaker diarization (MUST run in separate process from transcribe)
config/
  settings.py        -> All tunable parameters
.claude/skills/
  transcribe-video.md  -> /transcribe-video skill
  analyze-video.md     -> /analyze-video skill
  download-video.md    -> /download-video skill
```

## Rules for Claude Code

### MUST DO
- **Re-encode first**: Videos >500MB MUST be re-encoded via `src/preprocess.py` before frame extraction
- **Use CUDA**: All whisper/torch operations must use `device="cuda"`, `compute_type="float16"`
- **CUDA DLL fix**: `src/transcribe.py` adds NVIDIA pip DLL paths to PATH (cublas64_12.dll fix). If transcription fails with DLL errors, check this.
- **Use faster-whisper**: NOT openai-whisper (4x faster with CUDA)
- **Use built-in vision**: Read frame jpgs directly with Read tool. Do NOT default to API calls.
- **Scene detection first**: Use PySceneDetect for intelligent frame selection before falling back to interval
- **Sample frames**: Read ~30 frames spread across the timeline for visual analysis (not all 100+)
- **Save to transcripts/**: All output files go in `transcripts/`, never root
- **Save frames to frames/**: Extracted frames go in `frames/<video_name>/`
- **Include timestamps**: All transcript output must include timestamps
- **Correlate audio + visual**: Read both transcript and frames, then write a unified analysis

### MUST NOT
- Never save output files to the project root
- Never use the `base` whisper model when `large-v3` is available (we have the GPU for it)
- Never hardcode video paths - always use `videos/` dir or accept as argument
- Never run frame extraction on files >500MB without re-encoding first
- Never default to API-based visual analysis when running interactively

### Preprocessing (Large Files)
For videos >500MB, run preprocessing first:
```
python src/preprocess.py "videos/large_video.mp4"
```
- Uses NVENC GPU encoding (very fast)
- Compresses to 1280px wide, CRF 28, mono audio 64k
- Typically achieves 10-15x compression
- Output: `videos/<name>_small.mp4`
- Use the `_small` file for frame extraction; either file works for transcription

### Configuration (config/settings.py)
All tunable parameters are centralized in settings.py. Key settings:
- `WHISPER_MODEL = "large-v3"` - Best accuracy for RTX 4070 SUPER
- `WHISPER_DEVICE = "cuda"` - GPU acceleration
- `WHISPER_COMPUTE_TYPE = "float16"` - GPU precision
- `SCENE_DETECTION_THRESHOLD = 27.0` - Scene change sensitivity
- `MAX_FRAME_DIMENSION = 1024` - Resize for manageable frame sizes
- `HF_TOKEN` - HuggingFace token for pyannote diarization (set via env var `HF_TOKEN`)
- `DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"` - Speaker diarization model
- `DIARIZATION_NUM_SPEAKERS` - Set to exact count if known (helps accuracy)

### Dependencies
```
pip install faster-whisper opencv-python scenedetect[opencv] anthropic yt-dlp Pillow nvidia-cublas-cu12 nvidia-cudnn-cu12 pyannote.audio
```

### Performance Benchmarks (RTX 4070 SUPER)
| Stage | Speed | Example |
|---|---|---|
| Re-encode (NVENC) | ~560 MB/min | 4.5GB -> 288MB in ~8 min |
| Transcription (large-v3) | 8.9x real-time | 146 min video in 16.4 min |
| Frame extraction (scene) | ~26K frames/min | 263K frames in ~10 min |
| Visual analysis (direct) | ~2 min for 30 frames | Claude Code reads jpgs directly |

**Rule of thumb**: ~1 min processing per 9 min of video (transcription). Full pipeline for a 2.4hr video: ~25 min local processing + ~5 min for visual review.

### When User Says "Transcribe" or "Analyze"
Follow the skill procedures in `.claude/skills/transcribe-video.md` and `.claude/skills/analyze-video.md` exactly. Key steps:
1. Check `videos/` and `videos/to-be-processed/` for files
2. Ask which video if multiple exist; ask speaker count for diarization
3. If file >500MB, re-encode first with `src/preprocess.py`
4. Run transcription with diarization if multi-speaker:
   ```bash
   python src/transcribe.py "videos/file.mp4" transcripts --diarize --num-speakers 2
   ```
5. **Run quality check** (MANDATORY — see skill docs for the script)
6. Organize into per-video folder: `mkdir transcripts/<name> && mv transcripts/<name>_* transcripts/<name>/`
7. Run frame extraction (scene detection for presentations, interval for meetings)
8. For full analysis: sample ~30 frames with Read tool, read transcript, write `_analysis.md`
9. Final validation: confirm all 4 files present in subfolder

### Frame Analysis Strategy
- Screen recordings / presentations: Scene detection (catches slide changes)
- Meetings / webcam: Interval mode at 10s intervals (faces don't change much)
- Tutorials / demos: Scene detection with threshold 27
- Sample ~30 frames from the extracted set for visual review (spread evenly across timeline)

### Output Formats & Folder Organization
Output files are organized into per-video subfolders under `transcripts/`:
```
transcripts/
  meeting-recording/
    meeting-recording_transcript.txt
    meeting-recording_transcript_timestamped.txt
    meeting-recording_transcript.json
    meeting-recording_analysis.md
  another-video/
    ...
```

File types:
- `_transcript.txt` - Plain text transcript (with speaker labels if diarized)
- `_transcript_timestamped.txt` - Timestamped transcript (with speaker labels if diarized)
- `_transcript.json` - Full metadata JSON (includes timing stats, speaker per segment if diarized)
- `_analysis.md` - Complete analysis with visual + audio (markdown)

**After processing**, move output files into a per-video subfolder:
```bash
mkdir -p "transcripts/<video_name>"
mv transcripts/<video_name>_* "transcripts/<video_name>/"
```

### Speaker Diarization
Identifies who is speaking at each point in the transcript using pyannote.audio.

- **Prerequisite**: HuggingFace account with accepted licenses for ALL THREE:
  - `pyannote/speaker-diarization-3.1`
  - `pyannote/segmentation-3.0`
  - `pyannote/speaker-diarization-community-1`
- **Setup**: `HF_TOKEN` env var set permanently via `setx HF_TOKEN hf_...`
- **Primary approach** — use `--diarize` flag (runs in-process, both fit in 12GB):
  ```bash
  python src/transcribe.py "videos/file.mp4" transcripts --diarize --num-speakers 2
  ```
- **Fallback** — if in-process crashes before saving diarized output, use 2-step:
  ```bash
  python src/transcribe.py "videos/file.mp4" transcripts
  python scripts/run_diarize.py "videos/file.mp4" "transcripts/file_transcript.json" --hf-token %HF_TOKEN% --num-speakers 2
  ```
- **Speed**: ~165s transcription + ~55s diarization for 63 min audio on CUDA
- **Exit code 127** is expected — CTranslate2 CUDA cleanup segfaults but files ARE saved
- **Output**: Generic labels (`SPEAKER_00`, `SPEAKER_01`) — map to real names during visual analysis
- **Always** pass `--num-speakers N` when count is known (prevents spurious extra speakers)

### Quality Check After Transcription (MANDATORY)
Always run the quality check from the `/transcribe-video` skill after every transcription. Key checks:
- **Speaker balance**: Each speaker should have >10% of segments. If one has zero for long stretches, it's a remote audio issue.
- **Speaker deserts**: 5-min windows with only 1 speaker when 2+ expected = missing content.
- **Mega-segments**: Segments > 120s are usually VAD merge errors.
- **Remote audio fix**: Re-transcribe with `vad_filter=False` if remote speaker's audio is being dropped.

### Known Issues & Fixes
1. **cublas64_12.dll not found**: `src/transcribe.py` auto-fixes by adding NVIDIA pip DLL dirs to PATH
2. **Large files crash OpenCV**: Re-encode first with `src/preprocess.py`
3. **Buffered output**: Python print() is buffered when backgrounded - output appears only when process finishes. All scripts use `flush=True`.
4. **ANTHROPIC_API_KEY**: Only needed for headless `src/analyze_visual.py`. Not needed for interactive analysis.
5. **HF_TOKEN required for diarization**: Set env var via `setx` or pass `--hf-token`. Must accept licenses for ALL THREE pyannote gated models.
6. **CTranslate2 + PyTorch CUDA crash**: Running faster-whisper then pyannote in the same process causes heap corruption (0xC0000409) on Windows. **Solution**: Always run diarization via `scripts/run_diarize.py` in a separate process.
7. **torchcodec broken on Windows**: pyannote 4.x uses torchcodec for audio I/O, which can't find FFmpeg DLLs. **Solution**: Audio loaded via FFmpeg subprocess as raw PCM → numpy → torch tensor. Already implemented in both `src/transcribe.py` and `scripts/run_diarize.py`.
8. **pyannote 4.x API change**: Pipeline returns `DiarizeOutput` dataclass, not `Annotation` directly. Use `getattr(output, "speaker_diarization", output)` for `.itertracks()`, or `output.serialize()["diarization"]` for dict list.
9. **pyannote 4.x auth**: Uses `token=` param (NOT `use_auth_token=` which was 3.x).
10. **Background task exit code 127**: Bash tool on Windows sometimes reports exit 127 even when process completed. Check for output files to verify success.

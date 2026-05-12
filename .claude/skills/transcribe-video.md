---
name: transcribe-video
description: Transcribe a video file using faster-whisper with CUDA GPU acceleration, with optional speaker diarization (2-step process)
user_invocable: true
arguments:
  - name: video
    description: Video filename in videos/ folder (optional - will list available if omitted)
    required: false
  - name: diarize
    description: "Run speaker diarization after transcription (requires HF_TOKEN env var)"
    required: false
---

# Transcribe Video

Transcribe audio from a video file using faster-whisper with CUDA acceleration on the RTX 4070 SUPER. Optionally identify speakers with pyannote.audio diarization.

## Full Procedure

### Step 1: Identify the Video
1. List video files: `ls videos/` and `ls videos/to-be-processed/`
2. If multiple videos exist and none specified, ask the user which one
3. Ask: is this multi-speaker? How many speakers? (helps diarization accuracy)

### Step 2: Pre-process if Needed
- **Multi-part**: Re-encode each part, then merge (see Multi-Part section below)
- **Large files (>500MB)**: Re-encode first:
  ```bash
  python src/preprocess.py "videos/<filename>"
  ```
- Original file is fine for transcription; `_small` file is for frame extraction

### Step 3: Transcribe
Run transcription with `--diarize` flag for multi-speaker videos:
```bash
# Single speaker (no diarization)
python src/transcribe.py "videos/<filename>" transcripts

# Multi-speaker (with diarization — runs in-process, both fit in 12GB)
python src/transcribe.py "videos/<filename>" transcripts --diarize --num-speakers 2
```

**Important notes:**
- Always pass `--num-speakers N` when speaker count is known (improves accuracy significantly)
- Process exits with code 127 after saving files — this is the CTranslate2 CUDA cleanup segfault, files ARE saved correctly
- If `--diarize` crashes before saving diarized output, use the 2-step fallback (see below)

### Step 4: Organize Output
Move files into a per-video subfolder:
```bash
mkdir -p "transcripts/<video_name>"
mv transcripts/<video_name>_* "transcripts/<video_name>/"
```

### Step 5: Quality Check (MANDATORY)
Run this check EVERY TIME after transcription:

```python
python -c "
import json
d = json.load(open('transcripts/<name>/<name>_transcript.json','r',encoding='utf-8'))
segs = d['segments']
from collections import Counter
speakers = Counter(s.get('speaker','NONE') for s in segs)
print(f'Segments: {len(segs)}, Duration: {d[\"duration\"]:.0f}s')
for spk, cnt in speakers.most_common():
    times = [s for s in segs if s.get('speaker')==spk]
    dur = sum(t['end']-t['start'] for t in times)
    print(f'  {spk}: {cnt} segs, {dur:.0f}s speaking')
# Check gaps
for i in range(1, len(segs)):
    gap = segs[i]['start'] - segs[i-1]['end']
    if gap > 60: print(f'  GAP: {gap:.0f}s at {segs[i-1][\"end\"]:.0f}s')
# Long segments
long = [s for s in segs if s['end']-s['start'] > 60]
if long: print(f'  WARNING: {len(long)} segments > 60s (possible VAD merge errors)')
"
```

**Quality gates:**
| Check | Pass | Fail Action |
|---|---|---|
| Segments > 0 | File exists, segments present | Re-run transcription |
| Speaker balance (if diarized) | Each speaker has >10% of segments | See "Remote Audio" fix below |
| No gaps > 300s | All gaps < 5 min | Investigate — may be legit silence or audio issue |
| No mega-segments > 120s | All segments < 2 min | Lower VAD `min_silence_duration_ms` |
| Speaker count matches expected | e.g., 2 speakers for 2-person meeting | Re-run with correct `--num-speakers` |

### Known Issue: Remote Audio in Meeting Recordings
If video was recorded from one participant's device, the OTHER participant's voice comes through speakers (quiet, compressed). Whisper's VAD may drop it entirely.

**Symptoms:** One speaker has all the segments, the other has zero for long stretches.

**Fix:** Re-transcribe with VAD disabled:
```python
# In src/transcribe.py, change:
vad_filter=False  # was True
```
Then re-run. Will capture more noise but should get the remote speaker's audio.

## 2-Step Fallback (if in-process diarization crashes)
If `--diarize` crashes before saving diarized output:
```bash
# Step 1: Transcribe without diarize
python src/transcribe.py "videos/<filename>" transcripts

# Step 2: Diarize in separate process
python scripts/run_diarize.py "videos/<filename>" "transcripts/<name>_transcript.json" --hf-token %HF_TOKEN% --num-speakers 2
```

## Multi-Part Video Handling
1. Re-encode each part: `python src/preprocess.py "videos/to-be-processed/part1.mp4"`
2. Create concat list in `videos/to-be-processed/concat_list.txt`:
   ```
   file 'part1_small.mp4'
   file 'part2_small.mp4'
   ```
3. Merge: `ffmpeg -f concat -safe 0 -i "videos/to-be-processed/concat_list.txt" -c copy "videos/merged.mp4"`
4. Process merged file through normal pipeline

## Output
All output in `transcripts/<video_name>/`:
- `_transcript.txt` — plain text (with speaker labels if diarized)
- `_transcript_timestamped.txt` — timestamps + speakers
- `_transcript.json` — full metadata JSON
- Speed: ~165s for 63 min video (transcription) + ~55s (diarization)

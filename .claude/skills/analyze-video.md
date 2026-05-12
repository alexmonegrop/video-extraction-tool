---
name: analyze-video
description: Full video analysis combining audio transcription with visual frame analysis using Claude Code's built-in vision
user_invocable: true
arguments:
  - name: video
    description: Video filename in videos/ folder (optional - will list available if omitted)
    required: false
  - name: mode
    description: "Analysis mode: full (default), transcribe (audio only), visual (frames only)"
    required: false
---

# Analyze Video

Run the full video analysis pipeline: audio transcription (faster-whisper + CUDA) combined with visual frame analysis (Claude Code's built-in vision - no API key needed).

## Full Procedure (Follow This Exactly)

### Phase 1: Setup & Pre-processing

**1.1 Identify the video**
```bash
ls videos/
ls videos/to-be-processed/
```
- If multiple videos, ask user which one
- Ask: is this multi-speaker? How many speakers?
- Ask: what type of video? (meeting/webcam, presentation, screen recording, tutorial)

**1.2 Multi-part merge** (if split into parts)
```bash
# Re-encode each part
python src/preprocess.py "videos/to-be-processed/part1.mp4"
python src/preprocess.py "videos/to-be-processed/part2.mp4"

# Create concat list
echo "file 'part1_small.mp4'" > "videos/to-be-processed/concat_list.txt"
echo "file 'part2_small.mp4'" >> "videos/to-be-processed/concat_list.txt"

# Merge
ffmpeg -f concat -safe 0 -i "videos/to-be-processed/concat_list.txt" -c copy "videos/merged.mp4"
```

**1.3 Re-encode if >500MB**
```bash
python src/preprocess.py "videos/<filename>"
# Output: videos/<name>_small.mp4
```

### Phase 2: Transcription + Frame Extraction (Run in Parallel)

**2.1 Transcribe** (background)
```bash
# Multi-speaker with diarization
python src/transcribe.py "videos/<filename>" transcripts --diarize --num-speakers N

# Single speaker
python src/transcribe.py "videos/<filename>" transcripts
```
- Exit code 127 = CTranslate2 cleanup crash. Files ARE saved. Check output files, not exit code.
- If diarization crashes, use 2-step fallback: transcribe without `--diarize`, then `scripts/run_diarize.py`

**2.2 Extract frames** (parallel with transcription)
```bash
# Presentations / screen recordings / tutorials (scene detection)
python src/extract_frames.py "videos/<filename_or_small>"

# Meetings / webcam (interval mode — scene detection misses face-only video)
python src/extract_frames.py "videos/<filename_or_small>" --mode interval --interval 10
```

### Phase 3: Quality Gate (MANDATORY - Do NOT Skip)

**3.1 Check transcription output**
```bash
ls transcripts/<name>_transcript*
wc -c transcripts/<name>_transcript.json
```

**3.2 Run quality check script**
```python
python -c "
import json
d = json.load(open('transcripts/<name>_transcript.json','r',encoding='utf-8'))
segs = d['segments']
from collections import Counter
speakers = Counter(s.get('speaker','NONE') for s in segs)
print(f'Segments: {len(segs)}, Duration: {d[\"duration\"]:.0f}s, Diarized: {d.get(\"diarization\",False)}')
for spk, cnt in speakers.most_common():
    times = [s for s in segs if s.get('speaker')==spk]
    dur = sum(t['end']-t['start'] for t in times)
    pct = cnt/len(segs)*100
    print(f'  {spk}: {cnt} segs ({pct:.0f}%), {dur:.0f}s speaking')
# Timeline: check for speaker deserts (5-min windows with only 1 speaker when 2+ expected)
for t in range(0, int(d['duration']), 300):
    window = [s for s in segs if s['start'] < t+300 and s['end'] > t]
    spk_set = set(s.get('speaker') for s in window)
    spk_set.discard('UNKNOWN')
    if len(spk_set) <= 1 and len(window) > 0:
        mins = f'{t//60}:{t%60:02d}'
        print(f'  WARNING: Only {spk_set} speaking in {mins}-{(t+300)//60}:{(t+300)%60:02d}')
gaps = [(segs[i]['start']-segs[i-1]['end'], segs[i-1]['end']) for i in range(1,len(segs)) if segs[i]['start']-segs[i-1]['end']>60]
if gaps: print(f'  GAPS >60s: {len(gaps)} — largest {max(g[0] for g in gaps):.0f}s')
long = [s for s in segs if s['end']-s['start'] > 120]
if long: print(f'  MEGA-SEGMENTS >120s: {len(long)}')
"
```

**3.3 Quality gates**
| Check | Pass | Fail Action |
|---|---|---|
| Files exist | JSON + TXT + timestamped all present | Re-run transcription |
| Diarization flag | `diarization: True` if multi-speaker | Re-run with `--diarize` or use 2-step fallback |
| Speaker balance | Each speaker >10% of segments | **Remote audio issue** — re-transcribe with `vad_filter=False` |
| No speaker deserts | No 5-min window missing a known speaker | Same — remote audio or recording issue |
| Speaker count | Matches expected (e.g., 2 for 2 people) | Re-run with correct `--num-speakers` |
| No gaps > 300s | Largest gap < 5 min | May be legit (break) or audio issue |
| No mega-segments > 120s | All segments < 2 min | Lower `min_silence_duration_ms` in transcribe.py |

**3.4 Check frame coverage**
```bash
ls frames/<video_name>/ | head -5
ls frames/<video_name>/ | tail -5
ls frames/<video_name>/ | wc -l
```
- Last frame timestamp should be within 120s of video end
- Meeting videos: need >= 15 frames; if scene detection found too few, re-extract with interval mode
- Presentations: scene detection usually works well

**3.5 Report quality to user before proceeding**
Tell the user the quality check results. If there are issues (speaker imbalance, missing content), flag them and ask whether to re-transcribe or proceed.

### Phase 4: Organize Files
```bash
mkdir -p "transcripts/<video_name>"
mv transcripts/<video_name>_* "transcripts/<video_name>/"
```

### Phase 5: Visual Analysis

**5.1 Sample frames**
- Read ~30 frames spread across the timeline using the Read tool
- For meeting videos, focus on frames showing different contexts (screen shares, face shots, slide content)

**5.2 Read transcript**
- Read the timestamped transcript
- Note speaker labels and who says what

**5.3 Write analysis**
Write `transcripts/<video_name>/<video_name>_analysis.md` including:
- Meeting overview (date, platform, duration, participants)
- Speaker identification (map SPEAKER_00/01 to real names using visual + audio cues)
- Meeting structure with timestamps (break into logical sections)
- Key topics and themes
- Action items (if applicable)
- Transcript quality notes (flag any issues found in quality gate)

### Phase 6: Final Validation
```bash
wc -w "transcripts/<video_name>/<video_name>_analysis.md"
ls -la "transcripts/<video_name>/"
```
- Analysis should be > 500 words
- All 4 files present in the subfolder
- Report final file list to user

## Known Issues & Fixes

### Remote Audio in Meeting Recordings
If video was recorded from one participant's device, the other participant's voice comes through speakers and is quiet. Whisper's VAD drops it.

**Symptoms:** One speaker has all segments 00:00-36:00, other speaker has zero.

**Fix:** Re-transcribe with `vad_filter=False` in `src/transcribe.py`, then re-diarize.

### Meeting Videos Need Interval Mode for Frames
Scene detection finds few frames in webcam/meeting videos (faces don't change much). Use:
```bash
python src/extract_frames.py "videos/<file>" --mode interval --interval 10
```

### Exit Code 127
CTranslate2 CUDA cleanup segfaults on process exit. Files are saved correctly before the crash. Always verify by checking for output files, not exit code.

## Modes
- `full` - Complete analysis (audio + visual + written report)
- `transcribe` - Audio transcription only (fastest, no frame extraction)
- `visual` - Frame extraction + visual review only (skip audio)

## Performance (RTX 4070 SUPER, 1hr video)
| Stage | Time |
|---|---|
| Re-encode (if needed) | ~2 min |
| Transcription | ~3 min |
| Diarization | ~1 min |
| Frame extraction | ~1 min |
| Visual analysis (reading frames) | ~5 min |
| Writing analysis | ~3 min |
| **Total** | **~15 min** |

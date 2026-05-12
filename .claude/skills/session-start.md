---
name: session-start
description: Start a work session - check status of all videos, pending work, system health, and resume any interrupted processing
user_invocable: true
arguments: []
---

# Session Start

Initialize a work session by checking system health, listing all pending work, and offering to resume interrupted processing.

## Procedure

### Step 1: System Health Check
Run all checks in parallel:

**1.1 GPU & CUDA**
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}, VRAM: {torch.cuda.get_device_properties(0).total_mem/1e9:.1f}GB' if torch.cuda.is_available() else 'NO CUDA')"
```

**1.2 FFmpeg**
```bash
ffmpeg -version 2>&1 | head -1
```

**1.3 Disk space**
```bash
powershell -Command "Get-PSDrive C | Select-Object @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}"
```

**1.4 HF_TOKEN (for diarization)**
```bash
python -c "import os; print('HF_TOKEN: SET' if os.environ.get('HF_TOKEN') else 'HF_TOKEN: NOT SET - diarization will fail')"
```

### Step 2: Inventory Check
Run in parallel:

**2.1 New videos to process**
```bash
ls videos/to-be-processed/
```

**2.2 Videos folder (including _small re-encodes)**
```bash
ls videos/
```

**2.3 Existing transcripts**
```bash
ls transcripts/
```

**2.4 Existing frames**
```bash
ls frames/
```

### Step 3: Detect Interrupted Work
Check for partial outputs that indicate interrupted processing:

**3.1 Videos with _small but no transcript**
- List all `videos/*_small.mp4` files
- Check if corresponding `transcripts/<name>/` folder exists with all 3 transcript files
- Flag any that are missing transcripts

**3.2 Transcripts without analysis**
- List all `transcripts/<name>/` folders
- Check if `_analysis.md` exists in each
- Flag any that have transcripts but no analysis

**3.3 Videos in to-be-processed that haven't been re-encoded**
- List files in `videos/to-be-processed/`
- Check if corresponding `_small.mp4` exists in `videos/`
- Flag any unprocessed files

### Step 4: Report to User
Present a clear summary:

```
## Session Status

### System Health
- GPU: [status]
- FFmpeg: [version]
- Disk: [free/used]
- HF_TOKEN: [set/not set]

### New Videos (to-be-processed/)
- [list files with sizes]

### In Progress (interrupted)
- [any partially processed videos]

### Completed
- [videos with full transcript + analysis]

### Ready for Analysis (has transcript, needs visual)
- [videos with transcript but no analysis.md]
```

### Step 5: Offer to Resume
If any interrupted or pending work is found:
- Ask user which item to work on first
- If a video was mid-transcription (has _small but no transcript), offer to re-run transcription
- If a video has transcript but no analysis, offer to run visual analysis
- If new videos exist in to-be-processed, offer to start the full pipeline

## Notes
- This skill is purely diagnostic — it doesn't modify any files
- Run this at the start of every session to quickly orient
- All checks run in parallel for speed

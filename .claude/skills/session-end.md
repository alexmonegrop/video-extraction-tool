---
name: session-end
description: End a work session - archive processed videos, cleanup old files, capture lessons learned, and summarize work done
user_invocable: true
arguments: []
---

# Session End

Wrap up a work session by archiving processed files, purging old videos, capturing lessons learned, and producing a session summary.

**IMPORTANT**: Use simple unix commands (`ls`, `du`, `wc`, `mv`) instead of PowerShell — `$_` variables get mangled by bash.

## Procedure

### Step 1: Inventory What Was Done
Check all output directories to identify what was processed this session:

```bash
# Recent transcript files
ls -lt transcripts/*/  | head -20

# Frame directories with counts
for d in frames/*/; do echo "$d: $(ls "$d" | wc -l) frames"; done

# _small files created today
ls -la videos/*_small.mp4
```

### Step 2: Archive Processed Originals to videos/processed/
For videos that have been fully processed (all 4 transcript files exist):

**2.1 Identify fully processed videos**
A video is "fully processed" if its transcript folder contains all 4 files:
- `_transcript.txt`
- `_transcript_timestamped.txt`
- `_transcript.json`
- `_analysis.md`

**2.2 Move ALL processed files to videos/processed/**
For each fully processed video, move BOTH the original AND the `_small.mp4` re-encode:
- Original from `videos/to-be-processed/` -> `videos/processed/`
- `_small.mp4` from `videos/` -> `videos/processed/`
- `videos/` root should contain ONLY subfolders, never loose files

```bash
# Move originals from to-be-processed
mv "videos/to-be-processed/<original_file>" "videos/processed/"

# Move _small re-encodes from videos/ root
mv "videos/<name>_small.mp4" "videos/processed/"

# Clean any temp files (concat_list.txt, etc.)
rm -f "videos/to-be-processed/concat_list.txt"
rm -f "videos/processed/concat_list.txt"
```

**2.3 Confirm the move**
```bash
ls "videos/"
ls "videos/to-be-processed/"
ls "videos/processed/"
```
- `videos/` root should have ONLY `processed/` and `to-be-processed/` subfolders — no loose files
- `to-be-processed/` should be empty (or only contain unprocessed files)
- `processed/` should contain all originals + re-encodes for completed videos

### Step 3: Purge Old Processed Videos (>2 weeks)
Delete files in `videos/processed/` that are older than 14 days. These are originals that have already been transcribed, analyzed, and re-encoded — the `_small.mp4` and all transcripts are preserved.

```bash
# List files older than 14 days in processed/
find "videos/processed/" -type f -mtime +14

# Delete them (ONLY after confirming with user)
find "videos/processed/" -type f -mtime +14 -delete
```

**Rules:**
- ALWAYS show the list of files to be deleted BEFORE deleting
- Ask user for confirmation before purging
- NEVER delete `_small.mp4` files in `videos/` — only originals in `processed/`
- If no files are older than 14 days, skip this step and say so

### Step 4: Cleanup Temp Files

**4.1 Concat list files** (from multi-part merges)
```bash
rm -f "videos/to-be-processed/concat_list.txt"
```

**4.2 Orphan _small files in to-be-processed/**
If a `_small.mp4` exists in `videos/to-be-processed/` AND the final version is in `videos/`, remove the to-be-processed copy.

**4.3 Check total disk usage**
```bash
du -sh videos/
du -sh transcripts/
du -sh frames/
df -h /c/
```

### Step 5: Lessons Learned
Ask the user if anything notable happened this session:

**5.1 Prompt the user**
Ask: "Any lessons learned this session? (new issues, workarounds, things to remember)"

**5.2 If yes, update memory**
- Read the current `MEMORY.md` file
- Add the new lesson to the appropriate section
- Keep it concise — one line per lesson
- If the lesson contradicts an existing entry, update the existing one

**5.3 If no, skip**

### Step 6: Session Summary
Write a brief summary to the user:

```
## Session Summary

### Processed This Session
- [Video name]: [transcription time] transcription, [diarization time] diarization, [frame count] frames extracted
  - Duration: [video duration]
  - Speakers: [count] ([speaker mapping if identified])
  - Output: transcripts/[name]/ (4 files)

### Archived
- [Files moved to videos/processed/]
- [Files purged (>2 weeks old)]

### Storage
- Videos folder: [X GB] total
- Transcripts: [Y files across Z videos]
- Frames: [N directories]
- Disk free: [X GB]

### Still Pending
- [Any videos in to-be-processed not yet handled]
- [Any videos with transcripts but no analysis]

### Cleanup Done
- [Files moved/deleted]
- [Space recovered]
```

### Step 7: Final Check
```bash
ls "videos/to-be-processed/"
ls "videos/processed/"
ls transcripts/
```
Confirm staging area is clean and everything is organized.

## File Lifecycle
```
videos/to-be-processed/  -->  videos/processed/  -->  DELETED (after 14 days)
     (raw input)              (originals kept          (only originals purged;
                               for 2 weeks)             _small.mp4 + transcripts
                                                        kept forever)
```

## Notes
- NEVER delete without explicit user confirmation for the purge step
- `_small.mp4` re-encodes move to `processed/` alongside originals after completion
- NEVER delete transcript files or frames
- Memory updates should be concise — one line per lesson
- Use unix commands, not PowerShell (bash mangles `$_`)

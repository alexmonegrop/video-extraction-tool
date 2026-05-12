---
name: download-video
description: Download a video from a URL using yt-dlp into the videos/ folder
user_invocable: true
arguments:
  - name: url
    description: URL of the video to download
    required: true
---

# Download Video

Download a video from a URL (YouTube, Vimeo, etc.) into the `videos/` folder using yt-dlp.

## Steps

1. Run download:
   ```bash
   yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" --merge-output-format mp4 -o "videos/%(title)s.%(ext)s" "<url>"
   ```
2. Verify the file landed in `videos/`
3. Report filename and size to user
4. Ask if they want to transcribe or analyze it

## Notes
- Downloads best quality MP4 by default
- Requires yt-dlp: `pip install yt-dlp`
- Requires ffmpeg for format merging (installed)

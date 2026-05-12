# Security policy

Thanks for taking the time to disclose responsibly.

## Reporting a vulnerability

If you find a security issue **in the tool itself** (not in a fork or in your own deployment), please **do not open a public issue**.

Instead:

1. Open a [GitHub Security Advisory](https://github.com/alexmonegrop/video-extraction-tool/security/advisories/new) (preferred — private, structured, has a CVE workflow).
2. Or email the maintainer directly at the address in the GitHub profile commit history.

I aim to acknowledge reports within 5 business days and to ship a fix or mitigation within 30 days for confirmed issues, sooner for severe ones.

## What's in scope

This tool ships:

- Python pipeline modules under `src/` — `subprocess` calls to FFmpeg, file I/O on user-supplied paths, HuggingFace model downloads, optional Anthropic API calls.
- Standalone scripts under `scripts/` — same surface, plus a `.bat` convenience wrapper.
- The `.claude/skills/*.md` slash-command definitions — these are *prompts* to an AI agent, not executable code. Prompt-injection or instruction-bypass risks belong here.
- `config/settings.py` — tunables, plus the `HF_TOKEN` env-var read.

In-scope issues include (non-exhaustive):

- Path-traversal or command-injection via user-supplied video filenames passed to FFmpeg / subprocess.
- Insecure deserialization of `.json` transcript or pyannote output files.
- Leaking `HF_TOKEN` or `ANTHROPIC_API_KEY` into logs, stderr, or files written to disk.
- Prompt-injection vectors in the skill markdown that could cause the agent to exfiltrate transcripts.

## What's NOT in scope

- **The content of the videos / transcripts / frames you process.** These are your data; the tool does not transmit them anywhere (transcription is local; diarization is local; visual analysis is local when driven by Claude Code's built-in vision). If you opt into the headless `src/analyze_visual.py` path, you are sending frames to the Anthropic API under your own API key — that's your choice and your privacy contract with Anthropic.
- **Your HuggingFace account compromise.** `HF_TOKEN` is a read-only token used to download gated model weights. Rotate it via the HuggingFace UI if exposed.
- **Upstream dependency vulnerabilities.** `faster-whisper`, `pyannote.audio`, `opencv-python`, `scenedetect`, `torch`, `anthropic`, `yt-dlp`, FFmpeg, CUDA drivers — please report vulnerabilities in those projects to those projects.
- **AI model behaviour.** Hallucinations in the analysis output, mistranscribed speakers, mis-diarized turns — these are model-quality concerns, not security issues. File a regular bug.

## Secrets handling — the bare minimum a fork should do

If you fork this tool and run it against real meeting data, please:

1. **Never commit `.env` or `.claude/settings.local.json`.** Both are gitignored at the user level — keep it that way. Both can hold `HF_TOKEN` (and `ANTHROPIC_API_KEY` if you use the headless path).
2. **Never commit content from `videos/`, `transcripts/`, or `frames/`.** All three are gitignored by default. If you find yourself needing to share a transcript externally, redact participant names first.
3. **Rotate any credential that ever touches a tracked file, a shared screenshot, a Slack/Discord message, or a public AI-chat transcript.** Treat exposure as compromise.
4. **The `_small.mp4` files contain audio and video.** They are gitignored by default, but if you change that for some reason, treat them as PII.

## Known security considerations (tool-level)

- `subprocess` is used to invoke FFmpeg with user-supplied video paths. The current scripts pass the path as an argument (not via shell), so command injection requires the user to be tricked into typing an attacker-controlled path. If you wrap this tool in any service that takes paths from untrusted input, **validate / sanitise the path before invoking**.
- `yt-dlp` is invoked by the `/download-video` skill. yt-dlp downloads from arbitrary URLs — the standard yt-dlp security model applies (do not run with elevated permissions; review the destination directory).
- `pyannote.audio` downloads model weights from HuggingFace at first run. The model files are large (~100MB) and are cached under `~/.cache/huggingface/`. Audit the cache occasionally.

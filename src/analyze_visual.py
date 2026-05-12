"""
Visual Analysis Module - Analyze extracted frames using Claude Vision API.
Sends frames in batches with transcript context for comprehensive video understanding.
"""
import os
import sys
import json
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS, MAX_FRAMES_PER_API_CALL,
    FRAME_BATCH_OVERLAP
)


def analyze_frames(
    frames: list[dict],
    transcript_segments: list[dict] = None,
    prompt: str = None,
    api_key: str = None,
) -> list[dict]:
    """
    Analyze extracted video frames using Claude Vision API.

    Args:
        frames: List of frame dicts from extract_frames [{"path", "timestamp", "index"}, ...]
        transcript_segments: Optional transcript segments [{"start", "end", "text"}, ...]
        prompt: Custom analysis prompt (uses default if None)
        api_key: Anthropic API key (uses env var if None)

    Returns:
        List of batch analysis results [{"frames": [...], "analysis": str}, ...]
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    if not prompt:
        prompt = _default_prompt()

    # Batch frames (Claude supports up to 100 images per request)
    batches = _create_batches(frames)
    results = []

    for batch_idx, batch in enumerate(batches):
        print(f"[visual] Analyzing batch {batch_idx + 1}/{len(batches)} "
              f"({len(batch)} frames, {batch[0]['timestamp']:.0f}s-{batch[-1]['timestamp']:.0f}s)...")

        content = _build_content_blocks(batch, transcript_segments, prompt)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
        )

        analysis_text = message.content[0].text
        results.append({
            "batch_index": batch_idx,
            "frame_range": {
                "start": batch[0]["timestamp"],
                "end": batch[-1]["timestamp"],
            },
            "frame_count": len(batch),
            "analysis": analysis_text,
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        })

    return results


def _default_prompt() -> str:
    return """Analyze these video frames in chronological order. For each notable segment, describe:

1. **What is visually happening** - Actions, movements, screen content, gestures, environment
2. **Who/what is visible** - People, objects, UI elements, text on screen
3. **Notable changes** - What changed between frames, transitions, new content appearing

If a transcript is provided, correlate the visual content with what's being said.
Provide a cohesive scene-by-scene narrative, not individual frame descriptions.
Use timestamps to anchor your descriptions."""


def _create_batches(frames: list[dict]) -> list[list[dict]]:
    """Split frames into batches respecting MAX_FRAMES_PER_API_CALL with overlap."""
    if len(frames) <= MAX_FRAMES_PER_API_CALL:
        return [frames]

    batches = []
    step = MAX_FRAMES_PER_API_CALL - FRAME_BATCH_OVERLAP
    for i in range(0, len(frames), step):
        batch = frames[i:i + MAX_FRAMES_PER_API_CALL]
        if batch:
            batches.append(batch)

    return batches


def _build_content_blocks(
    frames: list[dict],
    transcript_segments: list[dict] = None,
    prompt: str = "",
) -> list[dict]:
    """Build Claude API content blocks with frames and optional transcript context."""
    content = []

    # Add transcript context if available
    if transcript_segments:
        start_time = frames[0]["timestamp"]
        end_time = frames[-1]["timestamp"]
        relevant_segments = [
            s for s in transcript_segments
            if s["end"] >= start_time and s["start"] <= end_time + 5
        ]
        if relevant_segments:
            transcript_text = "\n".join(
                f"[{_format_time(s['start'])} -> {_format_time(s['end'])}] {s['text']}"
                for s in relevant_segments
            )
            content.append({
                "type": "text",
                "text": f"**Audio transcript for this segment:**\n```\n{transcript_text}\n```\n"
            })

    # Add frames
    for frame in frames:
        content.append({
            "type": "text",
            "text": f"**Frame at {_format_time(frame['timestamp'])}:**"
        })

        img_data = _load_image_base64(frame["path"])
        if img_data:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_data,
                }
            })

    # Add the analysis prompt
    content.append({"type": "text", "text": prompt})

    return content


def _load_image_base64(image_path: str) -> str | None:
    """Load an image file and return base64-encoded string."""
    try:
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[visual] Warning: Could not load {image_path}: {e}")
        return None


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def synthesize_analysis(
    batch_results: list[dict],
    transcript_text: str = None,
    video_info: dict = None,
    api_key: str = None,
) -> str:
    """
    Final synthesis pass: combine all batch analyses into a cohesive summary.

    Args:
        batch_results: Results from analyze_frames()
        transcript_text: Full transcript text
        video_info: Video metadata dict
        api_key: Anthropic API key

    Returns:
        Final synthesized markdown summary
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # Build context from batch analyses
    analyses = "\n\n---\n\n".join(
        f"**Segment {r['batch_index']+1} ({_format_time(r['frame_range']['start'])} - "
        f"{_format_time(r['frame_range']['end'])}):**\n{r['analysis']}"
        for r in batch_results
    )

    prompt = f"""You are synthesizing a complete video analysis from multiple segment analyses.

**Video info:** {json.dumps(video_info) if video_info else 'N/A'}

**Segment analyses:**
{analyses}

{"**Full transcript:**" + chr(10) + transcript_text if transcript_text else ""}

Create a comprehensive, well-structured summary of the entire video that includes:
1. **Overview** - What this video is about (1-2 sentences)
2. **Key Sections** - Major segments with timestamps and descriptions
3. **Visual Highlights** - Notable visual elements, demonstrations, screen content
4. **Key Takeaways** - Main points, decisions, action items if applicable
5. **People & Context** - Who appears and their roles if identifiable

Use markdown formatting. Reference timestamps where relevant."""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS * 2,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text

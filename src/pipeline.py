"""
Video Analysis Pipeline - Full orchestrator.
Combines transcription, frame extraction, and visual analysis into one workflow.

Usage:
    python pipeline.py <video_path> [--mode full|transcribe|visual] [--output-dir DIR]
"""
import os
import sys
import json
import time
import argparse
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import VIDEOS_DIR, TRANSCRIPTS_DIR, FRAMES_DIR, OUTPUT_FORMAT


def find_videos(video_path: str = None) -> list[str]:
    """Find video files to process. If no path given, scan videos/ dir."""
    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}

    if video_path:
        if os.path.isfile(video_path):
            return [video_path]
        else:
            print(f"Error: File not found: {video_path}")
            return []

    # Scan videos directory
    videos = []
    for f in os.listdir(VIDEOS_DIR):
        ext = os.path.splitext(f)[1].lower()
        if ext in video_extensions:
            videos.append(os.path.join(VIDEOS_DIR, f))

    return sorted(videos)


def run_pipeline(
    video_path: str,
    mode: str = "full",
    output_dir: str = None,
    whisper_model: str = None,
    frame_method: str = "auto",
    custom_prompt: str = None,
) -> dict:
    """
    Run the video analysis pipeline.

    Args:
        video_path: Path to video file
        mode: "full" (transcript + visual), "transcribe" (audio only), "visual" (frames only)
        output_dir: Override output directory
        whisper_model: Override whisper model size
        frame_method: "scene", "interval", or "auto"
        custom_prompt: Custom prompt for visual analysis

    Returns:
        dict with all results and output file paths
    """
    from src.extract_frames import extract_frames, get_video_info

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = output_dir or TRANSCRIPTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    result = {"video": video_path, "video_name": video_name, "mode": mode}
    pipeline_start = time.time()

    # Get video info
    print(f"\n{'='*60}")
    print(f"Video Analysis Pipeline - {mode.upper()} mode")
    print(f"{'='*60}")

    info = get_video_info(video_path)
    result["video_info"] = info
    print(f"Video: {video_name}")
    print(f"  Resolution: {info['width']}x{info['height']} @ {info['fps']:.1f}fps")
    print(f"  Duration: {info['duration']:.0f}s ({info['duration']/60:.1f}min)")
    print(f"  Size: {info['size_mb']}MB")
    print()

    transcript_result = None
    visual_results = None

    # Step 1: Audio transcription
    if mode in ("full", "transcribe"):
        print("[STEP 1] Audio Transcription")
        print("-" * 40)
        from src.transcribe import transcribe_video
        transcript_result = transcribe_video(video_path, output_dir, whisper_model)
        result["transcript"] = transcript_result
        print()

    # Step 2: Frame extraction
    if mode in ("full", "visual"):
        step_num = 2 if mode == "full" else 1
        print(f"[STEP {step_num}] Frame Extraction")
        print("-" * 40)
        frames = extract_frames(video_path, method=frame_method)
        result["frames"] = [{"timestamp": f["timestamp"], "path": f["path"]} for f in frames]
        print()

        # Step 3: Visual analysis
        step_num += 1
        print(f"[STEP {step_num}] Visual Analysis (Claude Vision)")
        print("-" * 40)
        from src.analyze_visual import analyze_frames, synthesize_analysis

        transcript_segs = transcript_result["segments"] if transcript_result else None
        batch_results = analyze_frames(frames, transcript_segs, custom_prompt)
        result["visual_analysis_batches"] = batch_results

        # Synthesis pass
        print(f"\n[STEP {step_num + 1}] Synthesis")
        print("-" * 40)
        transcript_text = transcript_result["text"] if transcript_result else None
        summary = synthesize_analysis(batch_results, transcript_text, info)
        result["summary"] = summary
        print("[synthesis] Complete")

    # Save final output
    elapsed = time.time() - pipeline_start
    result["total_time"] = round(elapsed, 2)

    output_path = _save_output(result, output_dir, video_name)
    result["output_file"] = output_path

    print(f"\n{'='*60}")
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"Output: {output_path}")
    print(f"{'='*60}\n")

    return result


def _save_output(result: dict, output_dir: str, video_name: str) -> str:
    """Save the final analysis output."""
    if OUTPUT_FORMAT == "markdown":
        return _save_markdown(result, output_dir, video_name)
    elif OUTPUT_FORMAT == "json":
        return _save_json(result, output_dir, video_name)
    else:
        return _save_text(result, output_dir, video_name)


def _save_markdown(result: dict, output_dir: str, video_name: str) -> str:
    path = os.path.join(output_dir, f"{video_name}_analysis.md")
    info = result.get("video_info", {})

    lines = [
        f"# Video Analysis: {video_name}",
        "",
        f"**Duration:** {info.get('duration', 0)/60:.1f} min | "
        f"**Resolution:** {info.get('width', '?')}x{info.get('height', '?')} | "
        f"**Size:** {info.get('size_mb', '?')} MB",
        "",
    ]

    if result.get("summary"):
        lines.append(result["summary"])
        lines.append("")

    if result.get("transcript"):
        lines.append("---")
        lines.append("## Full Transcript")
        lines.append("")
        for seg in result["transcript"]["segments"]:
            start = _format_time(seg["start"])
            end = _format_time(seg["end"])
            lines.append(f"**[{start} -> {end}]** {seg['text']}")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def _save_json(result: dict, output_dir: str, video_name: str) -> str:
    path = os.path.join(output_dir, f"{video_name}_analysis.json")
    # Remove non-serializable frame paths from batches
    clean = {k: v for k, v in result.items() if k != "frames"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return path


def _save_text(result: dict, output_dir: str, video_name: str) -> str:
    path = os.path.join(output_dir, f"{video_name}_analysis.txt")
    with open(path, "w", encoding="utf-8") as f:
        if result.get("summary"):
            f.write(result["summary"])
            f.write("\n\n")
        if result.get("transcript"):
            f.write("=== TRANSCRIPT ===\n\n")
            f.write(result["transcript"]["text"])
    return path


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description="Video Analysis Pipeline")
    parser.add_argument("video", nargs="?", help="Path to video file (or scans videos/ dir)")
    parser.add_argument("--mode", choices=["full", "transcribe", "visual"], default="full",
                        help="Analysis mode: full, transcribe (audio only), visual (frames only)")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--whisper-model", help="Whisper model: base, small, medium, large-v3, turbo")
    parser.add_argument("--frame-method", choices=["scene", "interval", "auto"], default="auto",
                        help="Frame extraction method")
    parser.add_argument("--prompt", help="Custom prompt for visual analysis")
    args = parser.parse_args()

    videos = find_videos(args.video)
    if not videos:
        print("No videos found. Place video files in the videos/ directory.")
        sys.exit(1)

    print(f"Found {len(videos)} video(s) to process")
    for v in videos:
        run_pipeline(v, args.mode, args.output_dir, args.whisper_model,
                     args.frame_method, args.prompt)


if __name__ == "__main__":
    main()

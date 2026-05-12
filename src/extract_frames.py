"""
Frame Extraction Module - Scene-aware frame extraction from video files.
Uses OpenCV + PySceneDetect for intelligent keyframe selection.
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    FRAMES_DIR, FRAME_INTERVAL_SECONDS, SCENE_DETECTION_THRESHOLD,
    MAX_FRAME_DIMENSION, FRAME_QUALITY, USE_SCENE_DETECTION,
    MIN_SCENE_INTERVAL_SECONDS
)


def extract_frames(video_path: str, output_dir: str = None, method: str = "auto") -> list[dict]:
    """
    Extract representative frames from a video.

    Args:
        video_path: Path to the video file
        output_dir: Directory for extracted frames (defaults to FRAMES_DIR/<video_name>)
        method: "scene" for scene detection, "interval" for fixed interval, "auto" to choose

    Returns:
        List of dicts: [{"path": str, "timestamp": float, "index": int}, ...]
    """
    import cv2

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = output_dir or os.path.join(FRAMES_DIR, video_name)
    os.makedirs(output_dir, exist_ok=True)

    # Clear existing frames
    for f in os.listdir(output_dir):
        if f.endswith((".jpg", ".png")):
            os.remove(os.path.join(output_dir, f))

    if method == "auto":
        method = "scene" if USE_SCENE_DETECTION else "interval"

    if method == "scene":
        try:
            return _extract_scene_frames(video_path, output_dir)
        except Exception as e:
            print(f"[frames] Scene detection failed ({e}), falling back to interval method")
            return _extract_interval_frames(video_path, output_dir)
    else:
        return _extract_interval_frames(video_path, output_dir)


def _extract_scene_frames(video_path: str, output_dir: str) -> list[dict]:
    """Extract frames at scene boundaries using PySceneDetect."""
    import cv2
    from scenedetect import detect, ContentDetector

    print(f"[frames] Detecting scenes (threshold={SCENE_DETECTION_THRESHOLD})...")
    scene_list = detect(video_path, ContentDetector(
        threshold=SCENE_DETECTION_THRESHOLD,
        min_scene_len=int(MIN_SCENE_INTERVAL_SECONDS * 30)  # approx 30fps
    ))

    if not scene_list:
        print("[frames] No scene changes detected, using interval method")
        return _extract_interval_frames(video_path, output_dir)

    print(f"[frames] Found {len(scene_list)} scenes")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []

    for i, scene in enumerate(scene_list):
        # Extract frame from the start of each scene
        timestamp = scene[0].get_seconds()
        frame_num = int(timestamp * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            continue

        frame = _resize_frame(frame)
        frame_path = os.path.join(output_dir, f"frame_{i:04d}_{timestamp:.1f}s.jpg")
        cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, FRAME_QUALITY])

        frames.append({
            "path": frame_path,
            "timestamp": round(timestamp, 2),
            "index": i,
        })

    cap.release()

    # Ensure we also get the very first frame
    if frames and frames[0]["timestamp"] > 1.0:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            frame = _resize_frame(frame)
            frame_path = os.path.join(output_dir, f"frame_first_0.0s.jpg")
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, FRAME_QUALITY])
            frames.insert(0, {"path": frame_path, "timestamp": 0.0, "index": -1})
        cap.release()

    print(f"[frames] Extracted {len(frames)} scene frames")
    return frames


def _extract_interval_frames(video_path: str, output_dir: str) -> list[dict]:
    """Extract frames at fixed time intervals using OpenCV."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    interval_frames = int(fps * FRAME_INTERVAL_SECONDS)

    print(f"[frames] Extracting every {FRAME_INTERVAL_SECONDS}s from {duration:.0f}s video...")

    frames = []
    frame_count = 0
    saved_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % interval_frames == 0:
            timestamp = frame_count / fps
            frame = _resize_frame(frame)
            frame_path = os.path.join(output_dir, f"frame_{saved_count:04d}_{timestamp:.1f}s.jpg")
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, FRAME_QUALITY])

            frames.append({
                "path": frame_path,
                "timestamp": round(timestamp, 2),
                "index": saved_count,
            })
            saved_count += 1

        frame_count += 1

    cap.release()
    print(f"[frames] Extracted {len(frames)} frames at {FRAME_INTERVAL_SECONDS}s intervals")
    return frames


def _resize_frame(frame):
    """Resize frame so largest dimension <= MAX_FRAME_DIMENSION."""
    import cv2

    h, w = frame.shape[:2]
    if max(h, w) <= MAX_FRAME_DIMENSION:
        return frame

    scale = MAX_FRAME_DIMENSION / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def get_video_info(video_path: str) -> dict:
    """Get basic video metadata."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
            if cap.get(cv2.CAP_PROP_FPS) > 0 else 0,
        "size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 1),
    }
    cap.release()
    return info


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_frames.py <video_path> [output_dir] [method:scene|interval]")
        sys.exit(1)

    video = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    meth = sys.argv[3] if len(sys.argv) > 3 else "auto"

    if not os.path.exists(video):
        print(f"Error: Video not found: {video}")
        sys.exit(1)

    info = get_video_info(video)
    print(f"[frames] Video: {info['width']}x{info['height']} @ {info['fps']:.1f}fps, "
          f"{info['duration']:.0f}s, {info['size_mb']}MB")

    result = extract_frames(video, out, meth)
    for f in result:
        print(f"  {f['timestamp']:.1f}s -> {os.path.basename(f['path'])}")

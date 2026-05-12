"""
Video Preprocessing Module - Re-encode videos for faster processing.
Reduces file size dramatically while preserving quality needed for analysis.
"""
import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import VIDEOS_DIR


def find_ffmpeg() -> str:
    """Find ffmpeg executable."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Fallback for WinGet install
    winget_path = (
        r"C:\Users\alexm\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
    )
    if os.path.exists(winget_path):
        return winget_path
    raise FileNotFoundError("ffmpeg not found. Install via: winget install Gyan.FFmpeg")


def get_video_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def reencode_video(
    input_path: str,
    output_path: str = None,
    target_resolution: int = 1280,
    crf: int = 28,
    audio_bitrate: str = "64k",
    use_gpu: bool = True,
) -> str:
    """
    Re-encode a video to reduce file size for faster processing.

    For analysis purposes we don't need full quality - a 720p/1280-wide video
    with moderate compression is plenty for both whisper and frame analysis.

    Args:
        input_path: Path to original video
        output_path: Path for re-encoded video (default: adds _small suffix)
        target_resolution: Scale video to this width (maintains aspect ratio)
        crf: Constant Rate Factor (18=visually lossless, 28=good quality, 35=low quality)
        audio_bitrate: Audio bitrate (64k is fine for speech transcription)
        use_gpu: Use NVIDIA NVENC hardware encoding if available

    Returns:
        Path to the re-encoded video
    """
    ffmpeg = find_ffmpeg()

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_small.mp4"

    if os.path.exists(output_path):
        print(f"[preprocess] Re-encoded file already exists: {output_path}")
        return output_path

    original_size = get_video_size_mb(input_path)
    print(f"[preprocess] Original: {original_size:.0f} MB")
    print(f"[preprocess] Re-encoding to {target_resolution}px wide, CRF {crf}...")

    # Build ffmpeg command
    if use_gpu:
        # Try NVIDIA NVENC first (much faster)
        cmd = [
            ffmpeg, "-y", "-hwaccel", "cuda",
            "-i", input_path,
            "-vf", f"scale={target_resolution}:-2",
            "-c:v", "h264_nvenc",
            "-preset", "p4",        # balanced speed/quality
            "-cq", str(crf),
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ac", "1",             # mono audio (fine for speech)
            "-movflags", "+faststart",
            output_path
        ]
        try:
            print(f"[preprocess] Using NVIDIA NVENC GPU encoding...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                new_size = get_video_size_mb(output_path)
                ratio = original_size / new_size if new_size > 0 else 0
                print(f"[preprocess] Done: {new_size:.0f} MB ({ratio:.1f}x smaller)")
                return output_path
            else:
                print(f"[preprocess] NVENC failed, falling back to CPU encoding...")
        except subprocess.TimeoutExpired:
            print(f"[preprocess] GPU encoding timed out, trying CPU...")

    # CPU fallback (slower but always works)
    cmd = [
        ffmpeg, "-y",
        "-i", input_path,
        "-vf", f"scale={target_resolution}:-2",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ac", "1",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[preprocess] Using CPU encoding (libx264)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

    if result.returncode != 0:
        print(f"[preprocess] Error: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg re-encode failed: {result.stderr[-200:]}")

    new_size = get_video_size_mb(output_path)
    ratio = original_size / new_size if new_size > 0 else 0
    print(f"[preprocess] Done: {new_size:.0f} MB ({ratio:.1f}x smaller)")
    return output_path


def should_reencode(video_path: str, size_threshold_mb: float = 500) -> bool:
    """Check if a video would benefit from re-encoding before analysis."""
    size = get_video_size_mb(video_path)
    return size > size_threshold_mb


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python preprocess.py <video_path> [output_path] [resolution] [crf]")
        sys.exit(1)

    video = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    res = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    quality = int(sys.argv[4]) if len(sys.argv) > 4 else 28

    if not os.path.exists(video):
        print(f"Error: Video not found: {video}")
        sys.exit(1)

    result = reencode_video(video, out, target_resolution=res, crf=quality)
    print(f"Output: {result}")

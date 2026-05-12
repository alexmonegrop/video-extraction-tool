"""
Video Analysis Pipeline - Configuration
"""
import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_DIR = os.path.join(PROJECT_ROOT, "videos")
FRAMES_DIR = os.path.join(PROJECT_ROOT, "frames")
TRANSCRIPTS_DIR = os.path.join(PROJECT_ROOT, "transcripts")

# FFmpeg (auto-detected, override if needed)
FFMPEG_PATH = None  # Set to explicit path if not in PATH

# Whisper settings (CUDA-accelerated)
WHISPER_MODEL = "large-v3"       # Best accuracy; alternatives: "medium", "small", "base", "turbo"
WHISPER_DEVICE = "cuda"          # "cuda" for RTX GPU, "cpu" for fallback
WHISPER_COMPUTE_TYPE = "float16" # "float16" for GPU, "int8" for CPU
WHISPER_BEAM_SIZE = 5
WHISPER_LANGUAGE = None          # None = auto-detect, or "en", "es", etc.

# Speaker diarization settings (pyannote.audio)
HF_TOKEN = os.environ.get("HF_TOKEN", None)  # HuggingFace token for pyannote gated models
DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"
DIARIZATION_NUM_SPEAKERS = None  # None = auto-detect, or set to exact number (e.g., 2)
DIARIZATION_MIN_SPEAKERS = None  # Optional lower bound
DIARIZATION_MAX_SPEAKERS = None  # Optional upper bound

# Frame extraction settings
FRAME_INTERVAL_SECONDS = 5          # Extract 1 frame every N seconds (fallback)
SCENE_DETECTION_THRESHOLD = 27.0    # Lower = more scenes detected (20-40 range)
MAX_FRAME_DIMENSION = 1024          # Resize frames to this max dimension (saves API tokens)
FRAME_QUALITY = 85                  # JPEG quality (1-100)
USE_SCENE_DETECTION = True          # Use smart scene detection vs fixed interval
MIN_SCENE_INTERVAL_SECONDS = 2      # Minimum gap between extracted frames

# Claude Vision settings
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Vision model for frame analysis
CLAUDE_MAX_TOKENS = 4096
MAX_FRAMES_PER_API_CALL = 20       # Claude supports up to 100, but 20 keeps costs reasonable
FRAME_BATCH_OVERLAP = 2            # Overlap frames between batches for continuity

# Output settings
OUTPUT_FORMAT = "markdown"          # "markdown", "json", or "text"
INCLUDE_TIMESTAMPS = True
INCLUDE_FRAME_IMAGES = False        # Embed base64 frames in output (large files)

# Ensure directories exist
for d in [VIDEOS_DIR, FRAMES_DIR, TRANSCRIPTS_DIR]:
    os.makedirs(d, exist_ok=True)

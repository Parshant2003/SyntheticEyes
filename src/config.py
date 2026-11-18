import os
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Paths (sab relative to project root)
RIG_BLEND = os.path.join(ROOT, "blend", "gnm_head_v3_rig.blend")
# Frames (hazaron PNG) temp folder mein jaate hain taaki OneDrive unhe sync na kare. Badalna ho to:
#   PowerShell:  $env:EYES_FRAMES_DIR = "D:\\frames"
FRAMES_DIR = os.environ.get("EYES_FRAMES_DIR", os.path.join(tempfile.gettempdir(), "SyntheticEyes_frames"))
VIDEOS_DIR = os.path.join(ROOT, "renders", "videos")
BLENDER_EXE = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe")
FFMPEG_EXE = os.environ.get("FFMPEG_EXE", "ffmpeg")

# --- Motions jo user choose kar sakta hai
MOTIONS = ("left", "right", "up", "down", "generate")

# --- Gaze limits (degrees). yaw: + = screen ke RIGHT. pitch: + = neeche, - = upar.
MAX_YAW_DEG = 28.0
MAX_UP_DEG = 20.0
MAX_DOWN_DEG = 22.0

# --- Kaun si length. PPT: har video 15 sec se kam hona chahiye.
MAX_VIDEO_SECONDS = 14.5

# --- Quality presets
QUALITY = {
    "draft": {"res": 480, "samples": 8, "fps": 12},     # jaldi test ke liye
    "final": {"res": 720, "samples": 32, "fps": 24},    # submission ke liye
}
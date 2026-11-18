import glob
import os
import shutil
import subprocess

import cv2

import config

VIDEO_NAMES = {
    "left": "left_movement",
    "right": "right_movement",
    "up": "up_movement",
    "down": "down_movement",
    "generate": "generate_motion",
}


def video_path(motion, quality):
    os.makedirs(config.VIDEOS_DIR, exist_ok=True)
    suffix = "" if quality == "final" else f"_{quality}"
    return os.path.join(config.VIDEOS_DIR, VIDEO_NAMES[motion] + suffix + ".mp4")


def clear_frames(frames_dir):
    """Purane frame_*.png / preview_*.png hatao (sirf apne bane hue)."""
    for pattern in ("frame_*.png", "preview_*.png"):
        for f in glob.glob(os.path.join(frames_dir, pattern)):
            os.remove(f)


def encode(frames_dir, out_path, fps):
    """frame_0001.png, frame_0002.png ... ko H.264 MP4 mein jodo."""
    exe = config.FFMPEG_EXE
    if shutil.which(exe) is None and not os.path.isfile(exe):
        raise RuntimeError("FFmpeg nahi mila. PowerShell mein 'ffmpeg -version' chalake check karo.")
    n = len(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    if n == 0:
        raise RuntimeError("koi frame nahi mila: " + frames_dir)
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error",
           "-framerate", str(fps), "-i", os.path.join(frames_dir, "frame_%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError("FFmpeg fail hua:\n" + r.stderr[-1500:])
    return out_path


def verify(path, max_seconds=config.MAX_VIDEO_SECONDS):
    """OpenCV se video kholkar check: padh sakte hain? kitne frames? length 15 sec se kam?"""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("video khul nahi raha: " + path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("video ka pehla frame nahi padha ja saka")
    seconds = count / fps if fps else 0.0
    info = {"path": path, "frames": count, "fps": round(fps, 2), "width": w, "height": h,
            "seconds": round(seconds, 2), "size_mb": round(os.path.getsize(path) / 1e6, 2)}
    if seconds >= max_seconds:
        raise RuntimeError(f"video bahut lamba hai ({seconds:.1f}s). Limit {max_seconds}s. info={info}")
    return info
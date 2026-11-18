import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

ROOT = config.ROOT
OUT = os.path.join(ROOT, "Submission")

report = []
missing = []


def log(msg):
    print(msg)
    report.append(msg)


def copy(src, dst_rel, required=True):
    dst = os.path.join(OUT, dst_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isfile(src):
        shutil.copy2(src, dst)
        return True
    if required:
        missing.append(os.path.relpath(src, ROOT))
        log("  MISSING: " + os.path.relpath(src, ROOT))
    return False


def copy_glob(pattern, dst_dir, required=True):
    files = sorted(glob.glob(pattern))
    if not files and required:
        missing.append(os.path.relpath(pattern, ROOT))
        log("  MISSING: " + os.path.relpath(pattern, ROOT))
    for f in files:
        copy(f, os.path.join(dst_dir, os.path.basename(f)))
    return len(files)


if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
log("Submission folder: " + OUT)

# --- code
n = copy_glob(os.path.join(ROOT, "src", "*.py"), "src")
n += copy_glob(os.path.join(ROOT, "ui", "*.py"), "ui")
log(f"  python scripts: {n}")
copy(os.path.join(ROOT, "README.md"), "README.md")
copy(os.path.join(ROOT, "requirements.txt"), "requirements.txt")
copy(os.path.join(ROOT, "docs", "TESTING_CHECKLIST.md"), "docs/TESTING_CHECKLIST.md")

# --- blend files
for name in ("SyntheticEyes_final.blend", "gnm_head_v3_rig.blend", "gnm_head_v1.blend"):
    copy(os.path.join(ROOT, "blend", name), "blend/" + name)

# --- assets (exported GNM mesh + licence)
copy(os.path.join(ROOT, "assets", "gnm_neutral.npz"), "assets/gnm_neutral.npz")
copy(os.path.join(ROOT, "assets", "GNM-main", "LICENSE"), "assets/GNM_LICENSE", required=False)

# --- textures
t = copy_glob(os.path.join(ROOT, "textures", "skin_[0-9]*.png"), "textures")
t += copy_glob(os.path.join(ROOT, "textures", "iris_*.png"), "textures")
copy(os.path.join(ROOT, "textures", "skin_bump.png"), "textures/skin_bump.png")
copy(os.path.join(ROOT, "textures", "skin_rough.png"), "textures/skin_rough.png", required=False)
for extra in ("eye_info.json", "TEXTURE_NOTES.txt", "_debug_uv_masks.png", "_sheet_skins.png", "_sheet_irises.png"):
    copy(os.path.join(ROOT, "textures", extra), "textures/" + extra, required=False)
log(f"  texture maps: {t}")

# --- rendered images (stills) aur videos
imgs = copy_glob(os.path.join(ROOT, "renders", "textured_skin[0-9][0-9]_*.png"), "renders/images")
log(f"  rendered images: {imgs}")
vids = []
for pattern in ("left_movement", "right_movement", "up_movement", "down_movement", "generate_motion"):
    p = os.path.join(ROOT, "renders", "videos", pattern + ".mp4")
    if copy(p, "renders/videos/" + pattern + ".mp4"):
        vids.append(p)

# --- video check (OpenCV)
try:
    import video_output
    for p in vids:
        info = video_output.verify(p)
        log(f"  video OK: {os.path.basename(p)} {info['seconds']}s {info['frames']}f {info['width']}x{info['height']}")
except Exception as e:
    log("  VIDEO CHECK PROBLEM: " + str(e))
    missing.append("video check: " + str(e))

# --- .gitignore (GitHub ke liye)
with open(os.path.join(OUT, ".gitignore"), "w", encoding="utf-8") as fh:
    fh.write("__pycache__/\n*.pyc\n.venv/\n")

# --- size report
total = 0
for dp, _, fs in os.walk(OUT):
    for f in fs:
        total += os.path.getsize(os.path.join(dp, f))
log(f"  total size: {total / 1e6:.1f} MB")

os.makedirs(os.path.join(OUT, "docs"), exist_ok=True)
log("MISSING ITEMS: " + (", ".join(missing) if missing else "none"))
with open(os.path.join(OUT, "docs", "submission_report.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(report))

zip_path = shutil.make_archive(os.path.join(ROOT, "Submission"), "zip", OUT)
log("ZIP: " + zip_path)
log("MAKE_SUBMISSION_DONE")
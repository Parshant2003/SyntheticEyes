import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import sequences  # noqa: E402
import video_output  # noqa: E402

BLENDER_SCRIPT = os.path.join(config.ROOT, "src", "blender_entry.py")


def run_motion(motion, quality="final", gpu=True, preview=False, resume=False, status_cb=print, cancel_event=None):
    """Ek motion ko render karke video banata hai. Result dict wapas karta hai.
    gpu=True: Intel GPU (oneAPI) try karta hai, na chale to Blender CPU par chala leta hai.
    cancel_event: threading.Event; set hone par render rok diya jata hai (UI ka Cancel button)."""
    # --- Input validation
    if motion not in config.MOTIONS:
        raise ValueError(f"unknown motion '{motion}'. Allowed: {config.MOTIONS}")
    if quality not in config.QUALITY:
        raise ValueError(f"unknown quality '{quality}'. Allowed: {list(config.QUALITY)}")
    if not os.path.isfile(config.BLENDER_EXE):
        raise FileNotFoundError("Blender nahi mila: " + config.BLENDER_EXE + "  (BLENDER_EXE environment variable set karo)")
    if not os.path.isfile(config.RIG_BLEND):
        raise FileNotFoundError("rig file nahi mili: " + config.RIG_BLEND + "  (pehle: blender ... build_rig.py)")

    q = config.QUALITY[quality]
    plan = sequences.build(motion)
    total = int(round(plan["duration"] * q["fps"])) + 1
    frames_dir = os.path.join(config.FRAMES_DIR, f"{motion}_{quality}")
    os.makedirs(frames_dir, exist_ok=True)
    if not resume:
        video_output.clear_frames(frames_dir)

    cmd = [config.BLENDER_EXE, "--factory-startup", "--background", "--python", BLENDER_SCRIPT, "--",
           "--motion", motion, "--quality", quality, "--frames-dir", frames_dir]
    if gpu:
        cmd.append("--gpu")
    if preview:
        cmd.append("--preview")
    if resume:
        cmd.append("--resume")

    status_cb(f"[{motion}] Blender start ho raha hai ({quality}, {total} frames, {'GPU' if gpu else 'CPU'})...")
    t0 = time.time()
    done = 0
    tail = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        if cancel_event is not None and cancel_event.is_set():
            proc.terminate()
            raise RuntimeError("Render cancel kar diya gaya.")
        line = line.rstrip()
        tail = (tail + [line])[-25:]
        if "Saved:" in line:
            done += 1
            if not preview:
                status_cb(f"[{motion}] frame {done}/{total}  ({time.time() - t0:.0f}s)")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Blender fail hua. Aakhri lines:\n" + "\n".join(tail))

    if preview:
        status_cb(f"[{motion}] preview stills ban gaye: {frames_dir}")
        return {"motion": motion, "preview_dir": frames_dir, "seconds_elapsed": round(time.time() - t0, 1)}

    out = video_output.video_path(motion, quality)
    status_cb(f"[{motion}] FFmpeg se video ban raha hai...")
    video_output.encode(frames_dir, out, q["fps"])
    info = video_output.verify(out)
    info.update({"motion": motion, "seconds_elapsed": round(time.time() - t0, 1)})
    status_cb(f"[{motion}] DONE: {out}  ({info['seconds']} s, {info['frames']} frames)")
    return info


def move_left(**kw):
    """Dono aankhein (screen ke) LEFT ki taraf naturally dekhti hain."""
    return run_motion("left", **kw)


def move_right(**kw):
    """Dono aankhein RIGHT ki taraf."""
    return run_motion("right", **kw)


def move_up(**kw):
    """Dono aankhein UPAR."""
    return run_motion("up", **kw)


def move_down(**kw):
    """Dono aankhein NEECHE."""
    return run_motion("down", **kw)


def generate_motion(**kw):
    """Natural sequence: left, right, upar, centre par wapas, blinks, smooth transitions."""
    return run_motion("generate", **kw)


def main():
    ap = argparse.ArgumentParser(description="Eye motion render controller")
    ap.add_argument("motion", choices=config.MOTIONS)
    ap.add_argument("--quality", default="final", choices=list(config.QUALITY))
    ap.add_argument("--cpu", action="store_true", help="GPU ki jagah CPU se render")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    try:
        res = run_motion(a.motion, a.quality, not a.cpu, a.preview, a.resume)
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
    print("RESULT:", res)


if __name__ == "__main__":
    main()
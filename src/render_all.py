import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import eye_control  # noqa: E402
import video_output  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*", choices=config.MOTIONS, default=list(config.MOTIONS))
ap.add_argument("--quality", default="final", choices=list(config.QUALITY))
ap.add_argument("--force", action="store_true", help="pehle se bani video bhi dobara")
ap.add_argument("--fresh", action="store_true", help="purane frames hata kar shuru se")
ap.add_argument("--cpu", action="store_true")
args = ap.parse_args()

def _quiet_status(msg):
    """Har frame print karne ki jagah har 20wa frame."""
    m = re.search(r"frame (\d+)/(\d+)", msg)
    if m and int(m.group(1)) % 20 != 0 and m.group(1) != m.group(2):
        return
    print(msg)


results, failed = [], []
t_all = time.time()
for motion in args.only:
    out = video_output.video_path(motion, args.quality)
    if os.path.isfile(out) and not args.force:
        print(f"[{motion}] video pehle se hai, skip: {out}")
        continue
    try:
        info = eye_control.run_motion(motion, args.quality, gpu=not args.cpu, resume=not args.fresh,
                                      status_cb=_quiet_status)
        results.append(info)
    except Exception as e:
        print(f"[{motion}] FAILED: {e}")
        failed.append(motion)

print("\n=== SUMMARY ===")
for r in results:
    print(f"  {r['motion']}: {r['seconds']}s video, {r['frames']} frames @ {r['fps']} fps, "
          f"{r['width']}x{r['height']}, {r['size_mb']} MB -> {r['path']}")
print(f"failed: {failed}   total time: {(time.time() - t_all) / 60:.1f} min")
print("RENDER_ALL_DONE")
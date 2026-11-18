import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe")
SCRIPT = os.path.join(ROOT, "src", "apply_textures.py")
OUT = os.path.join(ROOT, "renders")

COMBOS = [(1, "brown"), (2, "hazel"), (3, "blue"), (4, "brown"),
          (5, "hazel"), (6, "brown"), (7, "blue"), (8, "hazel")]

ap = argparse.ArgumentParser()
ap.add_argument("--res", type=int, default=960)
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--only", type=int, default=0, help="sirf ek skin number render karo")
args = ap.parse_args()

if not os.path.isfile(BLENDER):
    sys.exit("ERROR: Blender nahi mila: " + BLENDER + "  (BLENDER_EXE set karo)")

done, failed = [], []
for skin, iris in COMBOS:
    if args.only and skin != args.only:
        continue
    t0 = time.time()
    cmd = [BLENDER, "--factory-startup", "--background", "--python", SCRIPT, "--",
           "--skin", str(skin), "--iris", iris, "--samples", str(args.samples), "--res", str(args.res)]
    if skin != 1:
        cmd.append("--no-save")                    # .blend sirf skin 1 ke saath save hoti hai
    r = subprocess.run(cmd, capture_output=True, text=True)
    png = os.path.join(OUT, f"textured_skin{skin:02d}_{iris}.png")
    ok = r.returncode == 0 and os.path.isfile(png)
    print(f"skin {skin} ({iris}): {'OK' if ok else 'FAILED'}  {time.time() - t0:.0f} s  -> {os.path.basename(png)}")
    if not ok:
        print(r.stdout[-1500:])
        print(r.stderr[-800:])
        failed.append(skin)
    else:
        done.append(skin)

print(f"RENDER_STILLS_DONE  ok={done}  failed={failed}")
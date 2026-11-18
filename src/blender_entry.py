import argparse
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import animator  # noqa: E402
import config  # noqa: E402
import sequences  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--motion", required=True, choices=config.MOTIONS)
ap.add_argument("--quality", default="final", choices=list(config.QUALITY))
ap.add_argument("--frames-dir", required=True)
ap.add_argument("--gpu", action="store_true")
ap.add_argument("--preview", action="store_true")
ap.add_argument("--resume", action="store_true")
args = ap.parse_args(argv)

q = config.QUALITY[args.quality]
if not os.path.isfile(config.RIG_BLEND):
    raise RuntimeError("rig file nahi mili: " + config.RIG_BLEND + "  (pehle build_rig.py chalao)")
os.makedirs(args.frames_dir, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=config.RIG_BLEND)
scene = bpy.context.scene

eyes = {"L": bpy.data.objects["GNM_left_eye"], "R": bpy.data.objects["GNM_right_eye"]}
key = bpy.data.objects["GNM_skin"].data.shape_keys
if key is None or "Blink_L" not in key.key_blocks:
    raise RuntimeError("shape keys nahi mili: build_rig.py dobara chalao")

# --- Camera: poora chehra frame mein
cam = bpy.data.objects.get("Camera_Face")
if cam is None:
    cd = bpy.data.cameras.new("Camera_Face")
    cd.lens = 85
    cam = bpy.data.objects.new("Camera_Face", cd)
    scene.collection.objects.link(cam)
cam.location = (0.0, -0.70, 0.265)
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.camera = cam

# --- Render settings
scene.render.engine = "CYCLES"
scene.cycles.samples = q["samples"]
scene.cycles.use_denoising = True
scene.render.resolution_x = q["res"]
scene.render.resolution_y = q["res"]
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.use_overwrite = not args.resume
scene.render.use_placeholder = False
if args.gpu:
    try:
        cprefs = bpy.context.preferences.addons["cycles"].preferences
        cprefs.compute_device_type = "ONEAPI"
        cprefs.refresh_devices()
        for dev in cprefs.devices:
            dev.use = dev.type == "ONEAPI"
        scene.cycles.device = "GPU"
        print("  render device: GPU (oneAPI)")
    except Exception as e:
        print("  GPU set nahi hua, CPU use hoga:", e)
        scene.cycles.device = "CPU"
else:
    scene.cycles.device = "CPU"
    print("  render device: CPU")

# --- Animation banao
plan = sequences.build(args.motion)
animator.build_animation(scene, eyes, key, plan, q["fps"])
print(f"  motion={args.motion} quality={args.quality} res={q['res']} samples={q['samples']} fps={q['fps']} "
      f"duration={plan['duration']}s frames={scene.frame_end}")

if args.preview:
    # Sirf 8 jagah ke stills (animation timeline sahi hai ya nahi, jaldi check)
    frames = sorted(set(int(round(f)) for f in np.linspace(1, scene.frame_end, 8)))
    for i, fr in enumerate(frames, start=1):
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(args.frames_dir, f"preview_{i:02d}_f{fr:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("PREVIEW_DONE")
else:
    scene.render.filepath = os.path.join(args.frames_dir, "frame_")
    bpy.ops.render.render(animation=True)
    print("RENDER_FRAMES_DONE")
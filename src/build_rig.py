import argparse
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import lid_math as L  # noqa: E402

SRC = os.path.join(ROOT, "blend", "gnm_head_v2_textured.blend")
DST = os.path.join(ROOT, "blend", "gnm_head_v3_rig.blend")
NPZ = os.path.join(ROOT, "assets", "gnm_neutral.npz")
OUT_DIR = os.path.join(ROOT, "renders", "rig_test")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--no-render", action="store_true")
args = ap.parse_args(argv)

for p in (SRC, NPZ):
    if not os.path.isfile(p):
        raise RuntimeError("file nahi mili: " + p)
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene

data = np.load(NPZ)
vert_comp = data["vert_comp"]
group_names = [str(n) for n in data["vertex_group_names"]]
groups = data["vertex_groups"]

skin = bpy.data.objects["GNM_skin"]
sel_v = np.where(vert_comp == 0)[0]                      # skin component ke vertices (build_head.py jaisi ordering)
if len(sel_v) != len(skin.data.vertices):
    raise RuntimeError("skin vertex count match nahi hua")
G = groups[:, sel_v]                                     # (46, n_skin)


def grp(name):
    return G[group_names.index(name)]


# ----------------------------------------------------------------------------
# 1) Eyeball pivots
# ----------------------------------------------------------------------------
eyes = {}
pivots = {}
for side, eye in (("L", "left"), ("R", "right")):
    obj = bpy.data.objects[f"GNM_{eye}_eye"]
    pivot = bpy.data.objects[f"joint_{eye}_eye"].location.copy()
    centroid = np.mean([[v.co.x, v.co.y, v.co.z] for v in obj.data.vertices], axis=0)
    dist_mm = 1000.0 * float(np.linalg.norm(centroid - np.array(pivot)))
    print(f"  {eye} eye: mesh centroid pivot se {dist_mm:.2f} mm door (chhota hona chahiye)")
    obj.data.transform(Matrix.Translation(-pivot))        # mesh ko pivot ke relative karo
    obj.location = pivot                                  # object origin = pivot
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (0.0, 0.0, 0.0)
    eyes[side] = obj
    pivots[side] = np.array([pivot.x, pivot.y, pivot.z], dtype=np.float64)

# ----------------------------------------------------------------------------
# 2) Shape keys on skin
# ----------------------------------------------------------------------------
n = len(skin.data.vertices)
co = np.empty(n * 3, dtype=np.float64)
skin.data.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
ed = np.empty(len(skin.data.edges) * 2, dtype=np.int64)
skin.data.edges.foreach_get("vertices", ed)
edges = ed.reshape(-1, 2)
sock = grp("eye_sockets") > 0.5

if skin.data.shape_keys is None:
    skin.shape_key_add(name="Basis", from_mix=False)


def add_key(name, coords):
    sk = skin.shape_key_add(name=name, from_mix=False)
    sk.data.foreach_set("co", np.asarray(coords, dtype=np.float32).reshape(-1))
    sk.slider_min = 0.0
    sk.slider_max = 1.0
    sk.value = 0.0
    return sk


print("--- LID KEYS ---")
for side in ("L", "R"):
    keys, info = L.compute_lid_keys(co, edges, sock, pivots[side])
    print(f"  {side}: {info}")
    for kname in ("Blink", "UpperDown", "UpperUp"):
        add_key(f"{kname}_{side}", keys[kname])

print("--- BROW KEYS ---")
for side, gname in (("L", "left_brow_region"), ("R", "right_brow_region")):
    w = L.smooth_weights(grp(gname), edges, 4)
    w = w / max(float(w.max()), 1e-9)
    up = co + np.stack([np.zeros(n), -0.0006 * w, 0.004 * w], axis=1)
    down = co + np.stack([np.zeros(n), 0.0004 * w, -0.003 * w], axis=1)
    add_key(f"BrowUp_{side}", up)
    add_key(f"BrowDown_{side}", down)
    print(f"  {gname}: {int((w > 0.05).sum())} vertices ko asar")

key = skin.data.shape_keys

# ----------------------------------------------------------------------------
# 3) Drivers: aankh ki pitch ke saath palkein
# ----------------------------------------------------------------------------


def add_driver(key_name, expression, eye_obj, blink_name):
    fc = key.driver_add(f'key_blocks["{key_name}"].value')
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    drv = fc.driver
    drv.type = "SCRIPTED"
    drv.expression = expression
    v1 = drv.variables.new()
    v1.name = "rx"
    v1.type = "SINGLE_PROP"
    t1 = v1.targets[0]
    t1.id_type = "OBJECT"
    t1.id = eye_obj
    t1.data_path = "rotation_euler[0]"
    v2 = drv.variables.new()
    v2.name = "bl"
    v2.type = "SINGLE_PROP"
    t2 = v2.targets[0]
    t2.id_type = "KEY"
    t2.id = key
    t2.data_path = f'key_blocks["{blink_name}"].value'


for side in ("L", "R"):
    # rx = pitch (radians). Positive = neeche. Blink ke waqt (bl=1) follow band.
    add_driver(f"UpperDown_{side}", "min(1.0, max(0.0, rx / 0.38)) * 0.55 * (1.0 - bl)", eyes[side], f"Blink_{side}")
    add_driver(f"UpperUp_{side}", "min(1.0, max(0.0, -rx / 0.35)) * 0.60 * (1.0 - bl)", eyes[side], f"Blink_{side}")

bpy.ops.wm.save_as_mainfile(filepath=DST)
print("SAVED:", DST)

if args.no_render:
    print("BUILD_RIG_DONE (render skip)")
    raise SystemExit(0)

# ----------------------------------------------------------------------------
# 4) Test poses
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera_Eyes")
cam_data.lens = 85
cam = bpy.data.objects.new("Camera_Eyes", cam_data)
cam.location = (0.0, -0.55, 0.31)
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = 800
scene.render.resolution_y = 450
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

POSES = [
    ("neutral", {}),
    ("look_left", {"yaw": -25}),
    ("look_right", {"yaw": 25}),
    ("look_up", {"pitch": -18}),
    ("look_down", {"pitch": 20}),
    ("blink_half", {"keys": {"Blink_L": 0.5, "Blink_R": 0.5}}),
    ("blink_full", {"keys": {"Blink_L": 1.0, "Blink_R": 1.0}}),
    ("brows_up", {"keys": {"BrowUp_L": 1.0, "BrowUp_R": 1.0}}),
]
DRIVEN = {f"{k}_{s}" for k in ("UpperDown", "UpperUp") for s in ("L", "R")}


def apply_pose(pose):
    for side in ("L", "R"):
        eyes[side].rotation_euler = (math.radians(pose.get("pitch", 0.0)), 0.0, math.radians(pose.get("yaw", 0.0)))
    for kb in key.key_blocks:
        if kb.name != "Basis" and kb.name not in DRIVEN:
            kb.value = 0.0
    for name, val in pose.get("keys", {}).items():
        key.key_blocks[name].value = val
    bpy.context.view_layer.update()


paths = []
print("--- POSE RENDERS ---")
for i, (name, pose) in enumerate(POSES, start=1):
    apply_pose(pose)
    path = os.path.join(OUT_DIR, f"pose_{i:02d}_{name}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    paths.append(path)
    vals = {kb.name: round(kb.value, 2) for kb in key.key_blocks if kb.name != "Basis" and kb.value > 0.001}
    print(f"  {name}: active keys {vals}")

# contact sheet 4x2
tiles = []
for p in paths:
    img = bpy.data.images.load(p)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    tiles.append(arr.reshape(h, w, 4))
top = np.hstack(tiles[0:4])
bottom = np.hstack(tiles[4:8])
sheet = np.vstack([bottom, top])           # Blender pixels neeche se upar
sh, sw = sheet.shape[:2]
out = bpy.data.images.new("sheet", sw, sh, alpha=True)
out.colorspace_settings.name = "Non-Color"
out.pixels.foreach_set(sheet.reshape(-1))
out.filepath_raw = os.path.join(OUT_DIR, "sheet_poses.png")
out.file_format = "PNG"
out.save()
print("SHEET:", out.filepath_raw)
print("BUILD_RIG_DONE")
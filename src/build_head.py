import math
import os

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPZ = os.path.join(ROOT, "assets", "gnm_neutral.npz")
BLEND_OUT = os.path.join(ROOT, "blend", "gnm_head_v0.blend")
PREVIEW = os.path.join(ROOT, "renders", "preview_front.png")
os.makedirs(os.path.dirname(BLEND_OUT), exist_ok=True)
os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)

if not os.path.isfile(NPZ):
    raise RuntimeError("gnm_neutral.npz nahi mili. Pehle: python src/export_gnm.py")

data = np.load(NPZ)
verts = data["verts"]
quads = data["quads"]
quad_uvs = data["quad_uvs_udim"]       # UDIM wale UV (har tile u-direction mein shift)
quad_tiles = data["quad_udim_tiles"]
vert_comp = data["vert_comp"]
quad_comp = data["quad_comp"]
names = [str(n) for n in data["component_names"]]
joint_names = [str(n) for n in data["joint_names"]]
joint_pos = data["joint_positions"]

# Viewport/preview mein pehchanan ke liye rang (ye final texture nahi hai)
COLORS = {
    "skin": (0.80, 0.60, 0.50, 1.0),
    "left_eye": (0.90, 0.92, 1.0, 1.0),
    "right_eye": (0.90, 0.92, 1.0, 1.0),
    "upper_teeth_and_gums": (0.95, 0.85, 0.80, 1.0),
    "lower_teeth_and_gums": (0.95, 0.85, 0.80, 1.0),
    "tongue": (0.80, 0.35, 0.40, 1.0),
}

# Scene saaf karo (default cube/camera/light hatao)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

scene = bpy.context.scene


def make_component(index, name):
    """Ek component ke vertices aur quads nikalkar Blender object banata hai."""
    sel_v = np.where(vert_comp == index)[0]
    sel_q = np.where(quad_comp == index)[0]
    # Purane (global) vertex numbers -> is object ke naye (local) numbers
    remap = np.full(len(verts), -1, dtype=np.int64)
    remap[sel_v] = np.arange(len(sel_v))
    faces = remap[quads[sel_q]]
    if (faces < 0).any():
        raise RuntimeError(f"{name}: face ka vertex kisi aur component mein hai")

    mesh = bpy.data.meshes.new(f"GNM_{name}_mesh")
    mesh.from_pydata(verts[sel_v].tolist(), [], faces.tolist())
    # NOTE: mesh.validate() jaan-bujhkar nahi chalaya, taaki face/UV ka order na badle.

    uv_layer = mesh.uv_layers.new(name="UVMap")
    if len(mesh.loops) != 4 * len(sel_q):
        raise RuntimeError(f"{name}: loop count galat")
    uv_layer.data.foreach_set("uv", quad_uvs[sel_q].reshape(-1).astype(np.float32))
    mesh.update()
    if hasattr(mesh, "shade_smooth"):
        mesh.shade_smooth()

    obj = bpy.data.objects.new(f"GNM_{name}", mesh)
    obj.color = COLORS[name]
    scene.collection.objects.link(obj)
    tiles_used = sorted(set(int(t) for t in quad_tiles[sel_q]))
    print(f"  {obj.name}: vertices={len(sel_v)} faces={len(sel_q)} UDIM tiles={tiles_used}")
    return obj


print("--- COMPONENTS ---")
for i, n in enumerate(names):
    make_component(i, n)

# Joint markers (chhote sphere-empties): aankh ghumane ke pivot points
print("--- JOINT MARKERS ---")
for n, p in zip(joint_names, joint_pos):
    empty = bpy.data.objects.new(f"joint_{n}", None)
    empty.empty_display_type = "SPHERE"
    empty.empty_display_size = 0.006
    empty.location = (float(p[0]), float(p[1]), float(p[2]))
    scene.collection.objects.link(empty)
    print(f"  {empty.name} at {tuple(round(float(c), 4) for c in p)}")

# Camera: samne se (face -Y ki taraf hai), 85mm lens
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 85
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (0.0, -1.0, 0.24)
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.collection.objects.link(cam)
scene.camera = cam

# Sirf quick-preview ke liye Workbench renderer (fast, GPU/CPU issue nahi)
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 1080
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
scene.render.filepath = PREVIEW

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("SAVED:", BLEND_OUT)
bpy.ops.render.render(write_still=True)
print("PREVIEW:", PREVIEW)
print("BUILD_HEAD_DONE")
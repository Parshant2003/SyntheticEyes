import math
import os

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "blend", "gnm_head_v1.blend")
OUT_DIR = os.path.join(ROOT, "renders", "groups_check")
os.makedirs(OUT_DIR, exist_ok=True)
if not os.path.isfile(SRC):
    raise RuntimeError("file nahi mili: " + SRC)

bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene
skin = bpy.data.objects["GNM_skin"]
joint = bpy.data.objects["joint_left_eye"]
mesh = skin.data
eye_c = np.array([float(c) for c in joint.location], dtype=np.float32)

# Har vertex ki aankh ke center se doori
n = len(mesh.vertices)
co = np.empty(n * 3, dtype=np.float32)
mesh.vertices.foreach_get("co", co)
dist = np.linalg.norm(co.reshape(-1, 3) - eye_c, axis=1)

# Vertex groups ki membership (weight > 0.5 matlab "is group ka hissa")
group_name = {vg.index: vg.name for vg in skin.vertex_groups}
members = {name: np.zeros(n, dtype=bool) for name in group_name.values()}
for v in mesh.vertices:
    for g in v.groups:
        if g.weight > 0.5:
            members[group_name[g.group]][v.index] = True

# Har face ke 4 vertex (build_head.py mein sab faces quads hain)
loop_v = np.empty(len(mesh.loops), dtype=np.int32)
mesh.loops.foreach_get("vertex_index", loop_v)
if len(loop_v) != 4 * len(mesh.polygons):
    raise RuntimeError("faces quads nahi hain, script ko badalna padega")
face_verts = loop_v.reshape(-1, 4)

# Do material: grey (baaki skin) aur red (highlight)
mesh.materials.clear()
for name, color in (("grey", (0.55, 0.55, 0.55, 1.0)), ("red", (0.9, 0.1, 0.1, 1.0))):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    mesh.materials.append(m)

# Camera: left eye ke samne, orthographic (bina perspective ke), chhota frame
cam = bpy.data.objects["Camera"]
cam.data.type = "ORTHO"
cam.data.ortho_scale = 0.09
cam.location = (float(eye_c[0]), -0.5, float(eye_c[2]))
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.camera = cam

scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 600
scene.render.resolution_y = 600
scene.render.resolution_percentage = 100
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "MATERIAL"


def need(name):
    if name not in members:
        raise KeyError("skin mein ye vertex group nahi mila: " + name)
    return members[name]


jobs = [
    ("1_eye_sockets", need("eye_sockets")),
    ("2_left_orbital_region", need("left_orbital_region")),
    ("3_left_infraorbital_region", need("left_infraorbital_region")),
    ("4_expression_basis_left_eye", need("expression_basis_left_eye")),
    ("5_within_20mm", dist <= 0.020),
    ("6_within_30mm", dist <= 0.030),
]

paths = []
for label, vmask in jobs:
    faces_on = vmask[face_verts].all(axis=1)       # face tab laal jab uske 4 vertex group mein hon
    mesh.polygons.foreach_set("material_index", faces_on.astype(np.int32))
    mesh.update()
    path = os.path.join(OUT_DIR, label + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"  {label}: vertices={int(vmask.sum())} red faces={int(faces_on.sum())}")
    paths.append(path)

# 6 images ko 3x2 sheet mein jodna (upar 1,2,3 aur neeche 4,5,6)
tiles = []
for p in paths:
    img = bpy.data.images.load(p)
    img.colorspace_settings.name = "Non-Color"     # rang ke values jaise hain waise hi rahein
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    tiles.append(arr.reshape(h, w, 4))
top = np.hstack(tiles[0:3])
bottom = np.hstack(tiles[3:6])
sheet = np.vstack([bottom, top])                   # Blender ke pixels neeche se upar order mein hote hain
sh, sw = sheet.shape[:2]
out = bpy.data.images.new("sheet", sw, sh, alpha=True)
out.colorspace_settings.name = "Non-Color"
out.pixels.foreach_set(sheet.reshape(-1))
out.filepath_raw = os.path.join(OUT_DIR, "sheet.png")
out.file_format = "PNG"
out.save()
print("SHEET:", out.filepath_raw)
print("CHECK_EYELID_DONE")
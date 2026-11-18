import os
import re
import sys

import numpy as np
from gnm.shape import gnm_numpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FILE = os.path.join(ROOT, "assets", "gnm_head.npz")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

if not os.path.isfile(MODEL_FILE):
    sys.exit("ERROR: model file nahi mili: " + MODEL_FILE)

lines = []


def out(text):
    print(text)
    lines.append(text)


gnm = gnm_numpy.GNM.from_custom_file(MODEL_FILE)
out("LOAD_OK")

out("--- JOINTS ---")
out("joint_names: " + str(list(gnm.joint_names)))
out("joint_parent_indices: " + str(gnm.joint_parent_indices.tolist()))
out("template_joint_positions:\n" + np.array2string(gnm.template_joint_positions, precision=4))

out("--- MESH COMPONENTS ---")
out(str(list(gnm.mesh_component_names)))

out("--- VERTEX GROUPS (index name: points with weight > 0.5) ---")
for i, name in enumerate(gnm.vertex_group_names):
    out(f"{i:2d} {name}: {int((gnm.vertex_groups[i] > 0.5).sum())}")

out("--- EXPRESSION NAMES ---")
names = list(gnm.expression_names)
out(f"total = {len(names)}")
for a, b in ((0, 6), (100, 104), (200, 204), (350, 354), (len(names) - 4, len(names))):
    out(f"[{a}:{b}] " + str(names[a:b]))
pattern = re.compile(r"blink|lid|brow|iris|close|squint|wide|gaze", re.IGNORECASE)
matches = [(i, n) for i, n in enumerate(names) if pattern.search(str(n))]
out(f"matching blink/lid/brow/iris/close/squint/wide/gaze: {len(matches)}")
for i, n in matches[:40]:
    out(f"  {i}: {n}")

out("--- UDIM TILES (quads) ---")
tiles, counts = np.unique(gnm.quad_udim_tiles, return_counts=True)
for t, c in zip(tiles, counts):
    m = gnm.quad_udim_tiles == t
    uv = gnm.quad_uvs[m].reshape(-1, 2)
    uu = gnm.quad_uvs_udim[m].reshape(-1, 2)
    out(
        f"tile {int(t)}: quads={int(c)} | quad_uvs u[{uv[:, 0].min():.2f},{uv[:, 0].max():.2f}] "
        f"v[{uv[:, 1].min():.2f},{uv[:, 1].max():.2f}] | udim u[{uu[:, 0].min():.2f},"
        f"{uu[:, 0].max():.2f}] v[{uu[:, 1].min():.2f},{uu[:, 1].max():.2f}]"
    )

out("--- NEUTRAL MESH SIZE ---")
try:
    v = gnm(
        np.zeros(gnm.identity_dim),
        np.zeros(gnm.expression_dim),
        np.zeros((gnm.num_joints, 3)),
        np.zeros(3),
    )
    v = np.asarray(v)
    out(f"vertices shape = {v.shape}")
    out("min xyz = " + str(np.round(v.min(axis=0), 4)))
    out("max xyz = " + str(np.round(v.max(axis=0), 4)))
except Exception as e:
    out("mesh generate error: " + repr(e))

out("--- BUILT-IN DATA FOLDER ---")
data_dir = os.path.join(ROOT, "assets", "GNM-main", "gnm", "shape", "data")
tex_dir = os.path.join(data_dir, "textures")
for d in (data_dir, tex_dir):
    out(d)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            size = os.path.getsize(p) // 1024 if os.path.isfile(p) else "folder"
            out(f"   {f}  ({size} KB)" if size != "folder" else f"   {f}  (folder)")
    else:
        out("   nahi mila")

with open(os.path.join(DOCS, "gnm_names.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
out("NAMES_DONE")
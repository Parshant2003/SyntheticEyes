import os
import sys

import numpy as np
from gnm.shape import gnm_numpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FILE = os.path.join(ROOT, "assets", "gnm_head.npz")
OUT_FILE = os.path.join(ROOT, "assets", "gnm_neutral.npz")

# Mesh ke 6 hisse (vertex group ke naam). Ye sabhi points ko bina overlap ke cover karte hain.
COMPONENTS = [
    "skin",
    "left_eye",
    "right_eye",
    "upper_teeth_and_gums",
    "lower_teeth_and_gums",
    "tongue",
]


def to_blender(points):
    """GNM (x, y, z) -> Blender (x, -z, y). Ye proper rotation hai, faces ulte nahi hote."""
    p = np.asarray(points, dtype=np.float32)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


if not os.path.isfile(MODEL_FILE):
    sys.exit("ERROR: model file nahi mili: " + MODEL_FILE)

gnm = gnm_numpy.GNM.from_custom_file(MODEL_FILE)

group_names = [str(n) for n in gnm.vertex_group_names]
missing = [c for c in COMPONENTS if c not in group_names]
if missing:
    sys.exit("ERROR: ye vertex groups nahi mile: " + str(missing))

# Har component ke liye: kaun-kaun se vertices uske hain
member = np.stack(
    [np.asarray(gnm.vertex_groups[group_names.index(c)]) > 0.5 for c in COMPONENTS]
)
per_vertex = member.sum(axis=0)
if not np.all(per_vertex == 1):
    sys.exit(
        "ERROR: kuch vertices kisi ek hi component mein nahi hain. "
        f"counts (0/1/2+) = {(per_vertex == 0).sum()}/{(per_vertex == 1).sum()}/{(per_vertex > 1).sum()}"
    )
vert_comp = member.argmax(axis=0).astype(np.int8)

# Har quad kis component ka hai (uske pehle vertex se), aur check ki mixed to nahi
quads = np.asarray(gnm.quads)
qc = vert_comp[quads]
mixed = int((qc != qc[:, :1]).any(axis=1).sum())
quad_comp = qc[:, 0].astype(np.int8)

# Neutral mesh (sab parameters zero)
verts = gnm(
    np.zeros(gnm.identity_dim),
    np.zeros(gnm.expression_dim),
    np.zeros((gnm.num_joints, 3)),
    np.zeros(3),
)
verts_b = to_blender(verts)
joints_b = to_blender(gnm.template_joint_positions)

np.savez_compressed(
    OUT_FILE,
    verts=verts_b,
    quads=quads.astype(np.int32),
    quad_uvs=np.asarray(gnm.quad_uvs, dtype=np.float32),
    quad_uvs_udim=np.asarray(gnm.quad_uvs_udim, dtype=np.float32),
    quad_udim_tiles=np.asarray(gnm.quad_udim_tiles, dtype=np.int32),
    vert_comp=vert_comp,
    quad_comp=quad_comp,
    component_names=np.array(COMPONENTS),
    joint_names=np.array([str(n) for n in gnm.joint_names]),
    joint_positions=joints_b,
    vertex_group_names=np.array(group_names),
    vertex_groups=np.asarray(gnm.vertex_groups, dtype=np.float32),
)

print("EXPORT_OK ->", OUT_FILE)
print("file size (KB):", os.path.getsize(OUT_FILE) // 1024)
print("vertices:", verts_b.shape, " quads:", quads.shape)
print("mixed-component quads (0 hona chahiye):", mixed)
for i, c in enumerate(COMPONENTS):
    print(f"  {c}: vertices={int((vert_comp == i).sum())} quads={int((quad_comp == i).sum())}")
print("min xyz:", np.round(verts_b.min(axis=0), 4))
print("max xyz:", np.round(verts_b.max(axis=0), 4))
print("joints (Blender coords):")
for n, p in zip(gnm.joint_names, joints_b):
    print("  ", n, np.round(p, 4))
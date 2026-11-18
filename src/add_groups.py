import os

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPZ = os.path.join(ROOT, "assets", "gnm_neutral.npz")
SRC = os.path.join(ROOT, "blend", "gnm_head_v0.blend")
DST = os.path.join(ROOT, "blend", "gnm_head_v1.blend")

for p in (NPZ, SRC):
    if not os.path.isfile(p):
        raise RuntimeError("file nahi mili: " + p)

bpy.ops.wm.open_mainfile(filepath=SRC)

data = np.load(NPZ)
vert_comp = data["vert_comp"]
comp_names = [str(n) for n in data["component_names"]]
group_names = [str(n) for n in data["vertex_group_names"]]
member = data["vertex_groups"] > 0.5      # (46, 17821) True/False

for ci, cname in enumerate(comp_names):
    obj = bpy.data.objects.get("GNM_" + cname)
    if obj is None:
        raise RuntimeError("object nahi mila: GNM_" + cname)
    sel_v = np.where(vert_comp == ci)[0]     # build_head.py jaisi hi ordering
    if len(obj.data.vertices) != len(sel_v):
        raise RuntimeError(f"{cname}: vertex count match nahi hua")
    added = 0
    for gi, gname in enumerate(group_names):
        idx = np.where(member[gi][sel_v])[0]
        if len(idx) == 0:
            continue                          # is object mein is group ka koi point nahi
        vg = obj.vertex_groups.new(name=gname)
        vg.add(idx.tolist(), 1.0, "REPLACE")
        added += 1
    print(f"  GNM_{cname}: {added} vertex groups added")

bpy.ops.wm.save_as_mainfile(filepath=DST)
print("SAVED:", DST)
print("ADD_GROUPS_DONE")
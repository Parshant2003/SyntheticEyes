import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

blend = os.path.join(config.ROOT, "blend", "gnm_head_v1.blend")
npz = np.load(os.path.join(config.ROOT, "assets", "gnm_neutral.npz"))
print("BLEND:", blend)
bpy.ops.wm.open_mainfile(filepath=blend)

comp_names = [str(n) for n in npz["component_names"]]
for eye in ("left", "right"):
    o = bpy.data.objects[f"GNM_{eye}_eye"]
    me = o.data
    print(f"\n=== {o.name} ===")
    print("  location", tuple(round(v, 4) for v in o.location), "rotation", tuple(round(v, 4) for v in o.rotation_euler),
          "scale", tuple(round(v, 4) for v in o.scale))
    xs = np.array([v.co.x for v in me.vertices])
    print(f"  vertices={len(me.vertices)} polys={len(me.polygons)} x-range=({xs.min():.4f}, {xs.max():.4f})")
    print("  uv layers:", [u.name for u in me.uv_layers], "| material slots:", len(o.material_slots))
    print(f"  loops={len(me.loops)}")
    for ul in me.uv_layers:
        n_data = len(ul.data)
        print(f"  uv layer '{ul.name}': len(data)={n_data} active={ul.active} active_render={ul.active_render}")
    # UV values padhne ke 2 tareeke (Blender ke naye version mein API badli hai)
    arr = None
    for ul in me.uv_layers:
        try:
            if len(ul.data) == len(me.loops):
                tmp = np.empty(len(me.loops) * 2)
                ul.data.foreach_get("uv", tmp)
                arr = tmp.reshape(-1, 2)
                print("  (UV padhe: layer.data)")
                break
        except Exception as e:
            print("  layer.data se padhne mein error:", e)
    if arr is None:
        for name in [a.name for a in me.attributes if "uv" in a.name.lower()]:
            try:
                at = me.attributes[name]
                tmp = np.empty(len(at.data) * 2)
                at.data.foreach_get("vector", tmp)
                arr = tmp.reshape(-1, 2)
                print(f"  (UV padhe: attribute '{name}', n={len(at.data)})")
                break
            except Exception as e:
                print(f"  attribute '{name}' se padhne mein error:", e)
    if arr is None or arr.size == 0:
        arr = None
        print("  !!! UV values nahi mil paye: UV layer khali hai (0 entries) - ye file kharab hai")
    else:
        print(f"  BLEND UV: u=({arr[:, 0].min():.3f}, {arr[:, 0].max():.3f}) v=({arr[:, 1].min():.3f}, {arr[:, 1].max():.3f})  zero-UV loops={int(((arr[:, 0] == 0) & (arr[:, 1] == 0)).sum())}")
        per_poly = arr.reshape(-1, 4, 2).mean(axis=1)
        for t in range(0, 6):
            c = int(((per_poly[:, 0] >= t) & (per_poly[:, 0] < t + 1)).sum())
            if c:
                print(f"    faces with u in [{t},{t + 1}): {c}")
    ci = comp_names.index(f"{eye}_eye")
    sel = npz["quad_comp"] == ci
    uu = npz["quad_uvs_udim"][sel]
    tiles = npz["quad_udim_tiles"][sel]
    print(f"  NPZ UV : u=({uu[..., 0].min():.3f}, {uu[..., 0].max():.3f}) tiles={sorted(set(int(t) for t in tiles))}")
print("\nDEBUG_EYES_DONE")
import argparse
import glob
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "textures")
SRC = os.path.join(ROOT, "blend", "gnm_head_v1.blend")
DST = os.path.join(ROOT, "blend", "gnm_head_v2_textured.blend")
NPZ = os.path.join(ROOT, "assets", "gnm_neutral.npz")
OUT_DIR = os.path.join(ROOT, "renders")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--skin", type=int, default=1)
ap.add_argument("--iris", default="brown", choices=["brown", "hazel", "blue"])
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--res", type=int, default=960)
ap.add_argument("--gpu", action="store_true")
ap.add_argument("--closeup", action="store_true", help="aankhon ka close-up frame (palak, nami, iris dekhne ke liye)")
ap.add_argument("--no-save", action="store_true", help=".blend save mat karo, sirf render")
args = ap.parse_args(argv)

for p in (SRC, NPZ, os.path.join(TEX, "eye_info.json")):
    if not os.path.isfile(p):
        raise RuntimeError("file nahi mili: " + p + "  (pehle make_textures.py chalao)")
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene

with open(os.path.join(TEX, "eye_info.json"), encoding="utf-8") as fh:
    eye_info = json.load(fh)

skin_matches = sorted(glob.glob(os.path.join(TEX, f"skin_{args.skin:02d}_*.png")))
if not skin_matches:
    raise RuntimeError(f"skin_{args.skin:02d}_*.png nahi mili textures/ mein")
skin_path = skin_matches[0]
print("skin texture:", os.path.basename(skin_path))


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def set_in(node, name, value):
    """Node ka input set karo; naam is Blender version mein na ho to sirf warning."""
    try:
        node.inputs[name].default_value = value
    except KeyError:
        print(f"  WARNING: input '{name}' nahi mila ({node.bl_idname})")


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True            # naye Blender mein deprecated ho sakta hai, par chalta hai
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    return mat, nt, out


def load_image(path):
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()                           # .blend ke andar pack: file portable rehti hai
    return img


def image_node(nt, img, tile_shift_x=0.0, extension="REPEAT"):
    """Image texture node, UV ko tile_shift_x se wapas 0..1 mein laata hai (UDIM tile ke liye)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-700, 0)
    mp.inputs["Location"].default_value = (-float(tile_shift_x), 0.0, 0.0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-450, 0)
    tex.image = img
    tex.extension = extension
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    return tex


def principled(nt, out):
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


def simple_material(name, color, roughness):
    mat, nt, out = new_material(name)
    b = principled(nt, out)
    set_in(b, "Base Color", (*color, 1.0))
    set_in(b, "Roughness", roughness)
    return mat


# ----------------------------------------------------------------------------
# Skin
# ----------------------------------------------------------------------------
mat, nt, out = new_material("GNM_skin_mat")
tex = image_node(nt, load_image(skin_path), 0.0, "REPEAT")
b = principled(nt, out)
nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
set_in(b, "Roughness", 0.5)                      # roughness map na mile to ye value
set_in(b, "Specular IOR Level", 0.4)
set_in(b, "Sheen Weight", 0.25)                  # halke rome (peach fuzz) ka asar
set_in(b, "Sheen Roughness", 0.4)
set_in(b, "Sheen Tint", (1.0, 0.85, 0.8, 1.0))
rough_png = os.path.join(TEX, "skin_rough.png")
if os.path.isfile(rough_png):
    rimg = load_image(rough_png)
    rimg.colorspace_settings.name = "Non-Color"
    rtex = image_node(nt, rimg, 0.0, "REPEAT")
    nt.links.new(rtex.outputs["Color"], b.inputs["Roughness"])
else:
    print("  NOTE: skin_rough.png nahi mili, roughness 0.5 fixed")
# Pores ka bump: grayscale height map -> Bump node -> Normal
bump_png = os.path.join(TEX, "skin_bump.png")
if os.path.isfile(bump_png):
    bimg = load_image(bump_png)
    bimg.colorspace_settings.name = "Non-Color"      # ye rang nahi, height data hai
    btex = image_node(nt, bimg, 0.0, "REPEAT")
    bnode = nt.nodes.new("ShaderNodeBump")
    bnode.location = (100, -300)
    set_in(bnode, "Strength", 0.4)
    set_in(bnode, "Distance", 0.001)
    nt.links.new(btex.outputs["Color"], bnode.inputs["Height"])
    nt.links.new(bnode.outputs["Normal"], b.inputs["Normal"])
else:
    print("  NOTE: skin_bump.png nahi mili, bump ke bina chal rahi hai")
set_in(b, "Subsurface Weight", 0.28)
set_in(b, "Subsurface Radius", (1.0, 0.35, 0.2))
set_in(b, "Subsurface Scale", 0.004)
skin_obj = bpy.data.objects["GNM_skin"]
skin_obj.data.materials.clear()
skin_obj.data.materials.append(mat)

# ----------------------------------------------------------------------------
# Eyes: alag iris texture har aankh ke liye
# ----------------------------------------------------------------------------
npz = np.load(NPZ)
quad_comp = npz["quad_comp"]
quad_tile = npz["quad_udim_tiles"]
comp_names = [str(n) for n in npz["component_names"]]

for eye in ("left", "right"):
    info = eye_info[eye]
    iris_tile = int(info["iris_tile"])
    iris_png = os.path.join(TEX, f"iris_{args.iris}_{eye}.png")
    if not os.path.isfile(iris_png):
        raise RuntimeError("iris texture nahi mili: " + iris_png)

    # slot 0: iris + sclera
    m0, nt0, out0 = new_material(f"GNM_{eye}_eye_iris_mat")
    iris_img = load_image(iris_png)
    print(f"  {eye} iris image: {os.path.basename(iris_png)} size={tuple(iris_img.size)} channels={iris_img.channels} "
          f"has_data={iris_img.has_data} packed={bool(iris_img.packed_file)} tile_shift={iris_tile - 1001}")
    tex0 = image_node(nt0, iris_img, iris_tile - 1001, "EXTEND")
    b0 = principled(nt0, out0)
    nt0.links.new(tex0.outputs["Color"], b0.inputs["Base Color"])
    set_in(b0, "Roughness", 0.2)
    set_in(b0, "Specular IOR Level", 0.5)
    # NOTE: Coat layer hata di gayi (GPU par ek aankh ki iris gayab ho rahi thi). Geeli chamak cornea glass se aati hai.

    # slot 1: cornea (bahar ka patla glass hissa)
    m1, nt1, out1 = new_material(f"GNM_{eye}_eye_cornea_mat")
    glass = nt1.nodes.new("ShaderNodeBsdfGlass")
    glass.location = (300, 0)
    set_in(glass, "Roughness", 0.0)
    set_in(glass, "IOR", 1.38)
    nt1.links.new(glass.outputs["BSDF"], out1.inputs["Surface"])

    obj = bpy.data.objects[f"GNM_{eye}_eye"]
    obj.data.materials.clear()
    obj.data.materials.append(m0)
    obj.data.materials.append(m1)
    # har face ka tile -> material (iris tile = slot 0, baaki = cornea)
    sel_q = np.where(quad_comp == comp_names.index(f"{eye}_eye"))[0]
    if len(sel_q) != len(obj.data.polygons):
        raise RuntimeError(f"{eye} eye: faces ki ginti match nahi hui")
    slots = (quad_tile[sel_q] != iris_tile).astype(np.int32)
    obj.data.polygons.foreach_set("material_index", slots)
    obj.data.update()
    print(f"  {eye} eye: iris tile {iris_tile}, iris faces={int((slots == 0).sum())}, cornea faces={int(slots.sum())}")

# Teeth / tongue (simple, UV textures nahi)
teeth = simple_material("GNM_teeth_mat", (0.88, 0.83, 0.74), 0.35)
for name in ("GNM_upper_teeth_and_gums", "GNM_lower_teeth_and_gums"):
    o = bpy.data.objects[name]
    o.data.materials.clear()
    o.data.materials.append(teeth)
tongue = simple_material("GNM_tongue_mat", (0.62, 0.24, 0.27), 0.5)
t_obj = bpy.data.objects["GNM_tongue"]
t_obj.data.materials.clear()
t_obj.data.materials.append(tongue)

# ----------------------------------------------------------------------------
# Lights, world, camera
# ----------------------------------------------------------------------------
for ob in [o for o in bpy.data.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(ob, do_unlink=True)


def add_sun(name, rot_deg, strength, angle_deg):
    ld = bpy.data.lights.new(name, type="SUN")
    ld.energy = strength
    ld.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, ld)
    ob.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    scene.collection.objects.link(ob)


add_sun("Key", (60, 0, -35), 1.8, 12)     # camera ke left-upar se
add_sun("Fill", (70, 0, 40), 0.5, 25)     # right se halka
add_sun("Rim", (-60, 0, 25), 1.0, 8)      # peeche-upar se kinaare ki roshni

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
if world.node_tree:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.035, 0.035, 0.04, 1.0)
        bg.inputs[1].default_value = 1.0

cam = bpy.data.objects["Camera"]
cam.data.type = "PERSP"
cam.data.lens = 85
cam.location = (0.0, -0.50, 0.30) if args.closeup else (0.0, -0.95, 0.27)
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.camera = cam

# ----------------------------------------------------------------------------
# Render settings
# ----------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.res
scene.render.resolution_y = args.res
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
try:
    scene.view_settings.view_transform = "Standard"
except Exception as e:
    print("  WARNING: view transform set nahi hua:", e)

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

if not args.no_save:
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED:", DST)

out_png = os.path.join(OUT_DIR, f"textured_skin{args.skin:02d}_{args.iris}" + ("_closeup" if args.closeup else "") + ".png")
scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print("RENDER:", out_png)
print("APPLY_TEXTURES_DONE")
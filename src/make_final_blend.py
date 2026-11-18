import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import animator  # noqa: E402
import config  # noqa: E402
import sequences  # noqa: E402

OUT = os.path.join(config.ROOT, "blend", "SyntheticEyes_final.blend")

if not os.path.isfile(config.RIG_BLEND):
    raise RuntimeError("rig file nahi mili: " + config.RIG_BLEND)
bpy.ops.wm.open_mainfile(filepath=config.RIG_BLEND)
scene = bpy.context.scene

eyes = {"L": bpy.data.objects["GNM_left_eye"], "R": bpy.data.objects["GNM_right_eye"]}
key = bpy.data.objects["GNM_skin"].data.shape_keys

# Camera: poora chehra
cam = bpy.data.objects.get("Camera_Face")
if cam is None:
    cd = bpy.data.cameras.new("Camera_Face")
    cd.lens = 85
    cam = bpy.data.objects.new("Camera_Face", cd)
    scene.collection.objects.link(cam)
cam.location = (0.0, -0.70, 0.265)
cam.rotation_euler = (math.radians(90), 0.0, 0.0)
scene.camera = cam

# Render settings (final preset)
q = config.QUALITY["final"]
scene.render.engine = "CYCLES"
scene.cycles.samples = q["samples"]
scene.cycles.use_denoising = True
scene.render.resolution_x = q["res"]
scene.render.resolution_y = q["res"]
scene.render.resolution_percentage = 100

plan = sequences.build("generate")
animator.build_animation(scene, eyes, key, plan, q["fps"])

# Saari images .blend ke andar pack (portable)
packed = 0
for img in bpy.data.images:
    if img.source == "FILE" and not img.packed_file and img.filepath:
        try:
            img.pack()
            packed += 1
        except Exception as e:
            print("  pack nahi hui:", img.name, e)
print("  extra images packed:", packed)

def make_cornea_viewport_friendly():
    """
    Glass cornea EEVEE (Material Preview) mein sirf reflection dikhata hai -> aankh kaali/hari dikhti hai.
    Fix: har cornea material mein 2 outputs: Cycles ke liye Glass (final render jaisa hi), EEVEE ke liye
    Transparent + Fresnel-Glossy mix (aankh ke andar ka iris/sclera dikhta hai).
    """
    for name in ("GNM_left_eye_cornea_mat", "GNM_right_eye_cornea_mat"):
        try:
            mat = bpy.data.materials.get(name)
            if mat is None or mat.node_tree is None:
                print("  NOTE: material nahi mila:", name)
                continue
            nt = mat.node_tree
            outs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
            if not outs:
                continue
            outs[0].target = "CYCLES"
            out_e = nt.nodes.new("ShaderNodeOutputMaterial")
            out_e.target = "EEVEE"
            out_e.location = (700, -300)
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            tr.location = (200, -300)
            gl = nt.nodes.new("ShaderNodeBsdfGlossy")
            gl.location = (200, -450)
            gl.inputs["Roughness"].default_value = 0.02
            fr = nt.nodes.new("ShaderNodeFresnel")
            fr.location = (200, -150)
            fr.inputs["IOR"].default_value = 1.38
            mix = nt.nodes.new("ShaderNodeMixShader")
            mix.location = (480, -300)
            nt.links.new(fr.outputs["Fac"], mix.inputs[0])
            nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
            nt.links.new(gl.outputs["BSDF"], mix.inputs[2])
            nt.links.new(mix.outputs["Shader"], out_e.inputs["Surface"])
            outs[0].is_active_output = True
            out_e.is_active_output = True
            print("  cornea viewport fix:", name)
        except Exception as e:
            print("  NOTE: cornea fix fail", name, e)


make_cornea_viewport_friendly()

# Viewport ko Material Preview + SCENE world/lights par set karo, taaki file kholte hi aankhein sahi (brown) dikhein.
# (Default HDRI ka hara reflection glass cornea par aa jata hai.) Camera view bhi lagao.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            try:
                space.shading.type = "MATERIAL"
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = True
                space.region_3d.view_perspective = "CAMERA"
            except Exception as e:
                print("  NOTE: viewport setting skip:", e)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED:", OUT)
print("MAKE_FINAL_BLEND_DONE")
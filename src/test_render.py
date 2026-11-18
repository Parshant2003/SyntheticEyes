import os
import time
import bpy

# Project root = src folder ka parent (relative path rule)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "renders")
os.makedirs(OUT, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.cycles.samples = 32          # kam samples = tez test
scene.cycles.use_denoising = False  # test ko simple rakhne ke liye

cprefs = bpy.context.preferences.addons["cycles"].preferences
cprefs.compute_device_type = "ONEAPI"
cprefs.refresh_devices()


def use_devices(kind):
    """kind = 'GPU' ya 'CPU'. Sirf wahi device on, baaki off."""
    for d in cprefs.devices:
        d.use = (d.type == "CPU") if kind == "CPU" else (d.type == "ONEAPI")
    scene.cycles.device = kind


def timed_render(label, kind, filename):
    use_devices(kind)
    scene.render.filepath = os.path.join(OUT, filename)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RESULT {label}: {time.time() - t0:.1f} sec")


timed_render("GPU run 1 (kernel compile ke saath)", "GPU", "test_gpu.png")
timed_render("GPU run 2 (asli speed)", "GPU", "test_gpu.png")
timed_render("CPU run", "CPU", "test_cpu.png")
print("TEST_RENDER_DONE")
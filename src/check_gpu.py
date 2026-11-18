import bpy

cprefs = bpy.context.preferences.addons["cycles"].preferences

# Ye sab types hum khud try karenge. Jo is machine par nahi hota, wo error dega.
CANDIDATE_TYPES = ["CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"]

print("=== DEVICES FOUND PER TYPE ===")
for t in CANDIDATE_TYPES:
    try:
        cprefs.compute_device_type = t
    except Exception as e:
        print(f"{t}: not supported by this Blender/PC")
        continue
    try:
        # Naye Blender mein refresh_devices(), purane mein get_devices()
        if hasattr(cprefs, "refresh_devices"):
            cprefs.refresh_devices()
        else:
            cprefs.get_devices()
        names = [f"{d.name} ({d.type})" for d in cprefs.devices]
        print(f"{t}: {names if names else 'no devices'}")
    except Exception as e:
        print(f"{t}: error -> {e}")

print("CHECK_GPU_DONE")
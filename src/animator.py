import bpy

import eye_motion
import eyelids


def _frame(t, fps):
    return int(round(1 + t * fps))


def build_animation(scene, eyes, key, plan, fps):
    """eyes={"L":obj,"R":obj}; key = skin ka Key datablock (shape keys); plan = sequences.build(...)"""
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = _frame(plan["duration"], fps)

    # Naye keyframes ke liye smooth (Bezier) interpolation
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
    except Exception as e:  # pragma: no cover
        print("  NOTE: interpolation preference set nahi hui:", e)

    # --- Gaze + bhaunhein
    for wp in plan["waypoints"]:
        fr = _frame(wp["t"], fps)
        eye_motion.set_gaze(eyes, wp["yaw"], wp["pitch"])
        eye_motion.key_gaze(eyes, fr)
        eyelids.set_brows(key, wp["pitch"])
        eyelids.key_brows(key, fr)

    # --- Blink: pehle sab frames par blink=0 ka base, phir blink ke points
    eyelids.set_blink(key, 0.0)
    eyelids.key_blink(key, 1)
    eyelids.key_blink(key, scene.frame_end)
    for b in plan["blinks"]:
        for (t, val) in eyelids.blink_frames(b["t"], b["strength"]):
            eyelids.set_blink(key, val)
            eyelids.key_blink(key, _frame(t, fps))

    # Frame 1 par wapas (clean state)
    scene.frame_set(1)
    print(f"  animation: {len(plan['waypoints'])} gaze keyframes, {len(plan['blinks'])} blinks, "
          f"frames 1..{scene.frame_end} @ {fps} fps")
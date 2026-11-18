import math


def set_gaze(eyes, yaw_deg, pitch_deg):
    """eyes = {"L": obj, "R": obj}. Rotation set karo (keyframe nahi)."""
    rot = (math.radians(pitch_deg), 0.0, math.radians(yaw_deg))
    for obj in eyes.values():
        obj.rotation_euler = rot


def key_gaze(eyes, frame):
    """Abhi ki rotation ko is frame par keyframe karo (Bezier = smooth ease in/out)."""
    for obj in eyes.values():
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
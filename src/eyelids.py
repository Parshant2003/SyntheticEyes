BLINK_KEYS = ("Blink_L", "Blink_R")


def set_blink(key, value):
    for name in BLINK_KEYS:
        key.key_blocks[name].value = value


def key_blink(key, frame):
    for name in BLINK_KEYS:
        key.key_blocks[name].keyframe_insert(data_path="value", frame=frame)


def set_brows(key, pitch_deg):
    """Upar dekho to bhaunhein halki uthti hain, neeche dekho to halki jhukti hain."""
    up = max(0.0, min(1.0, -pitch_deg / 18.0)) * 0.45
    down = max(0.0, min(1.0, pitch_deg / 20.0)) * 0.30
    for side in ("L", "R"):
        key.key_blocks[f"BrowUp_{side}"].value = up
        key.key_blocks[f"BrowDown_{side}"].value = down


def key_brows(key, frame):
    for side in ("L", "R"):
        for kind in ("BrowUp", "BrowDown"):
            key.key_blocks[f"{kind}_{side}"].keyframe_insert(data_path="value", frame=frame)


def blink_frames(t, strength, dur_close=0.09, hold=0.04, dur_open=0.17):
    """Ek blink ke (time, value) points: khula -> band (tez) -> thodi der band -> khulna (thoda dheere)."""
    return [(t, 0.0), (t + dur_close, strength), (t + dur_close + hold, strength),
            (t + dur_close + hold + dur_open, 0.0)]
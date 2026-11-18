import math
import random

import config


def _clamp_yaw(v):
    return max(-config.MAX_YAW_DEG, min(config.MAX_YAW_DEG, v))


def _clamp_pitch(v):
    return max(-config.MAX_UP_DEG, min(config.MAX_DOWN_DEG, v))


def _saccade_duration(amplitude_deg):
    """Bada shift = thoda zyada time. 25 deg ~ 0.22 s."""
    return 0.10 + 0.005 * amplitude_deg


def _plan(duration, moves, blinks, seed=7):
    """
    moves : [(t_start, yaw, pitch), ...]   (time seconds mein, ascending)
    blinks: [(t, strength), ...]
    Returns dict(duration, waypoints=[{t, yaw, pitch}], blinks=[...])
    """
    rng = random.Random(seed)
    cur = (0.0, 0.0)
    wps = [{"t": 0.0, "yaw": 0.0, "pitch": 0.0}]

    def add_drift(t_from, t_to, yaw, pitch):
        """Ruke hue waqt mein chhote random hilne wale keyframes (aankh 'jami' hui na lage)."""
        t = t_from + rng.uniform(0.35, 0.6)
        while t < t_to - 0.30:
            wps.append({"t": round(t, 3), "yaw": yaw + rng.uniform(-1.3, 1.3),
                        "pitch": pitch + rng.uniform(-0.9, 0.9)})
            t += rng.uniform(0.4, 0.75)

    last_t = 0.0
    for (t0, yaw, pitch) in moves:
        yaw, pitch = _clamp_yaw(yaw), _clamp_pitch(pitch)
        amp = math.hypot(yaw - cur[0], pitch - cur[1])
        dur = _saccade_duration(amp)
        add_drift(last_t, t0, cur[0], cur[1])
        wps.append({"t": round(t0, 3), "yaw": cur[0], "pitch": cur[1]})                # anchor: abhi yahin ruki thi
        over = 0.05 if amp > 8.0 else 0.0
        wps.append({"t": round(t0 + dur, 3), "yaw": _clamp_yaw(cur[0] + (yaw - cur[0]) * (1 + over)),
                    "pitch": _clamp_pitch(cur[1] + (pitch - cur[1]) * (1 + over))})     # overshoot
        wps.append({"t": round(t0 + dur + 0.12, 3), "yaw": yaw, "pitch": pitch})        # settle
        cur = (yaw, pitch)
        last_t = t0 + dur + 0.12
    add_drift(last_t, duration, cur[0], cur[1])
    wps.append({"t": round(duration, 3), "yaw": cur[0], "pitch": cur[1]})

    # time order + bahut paas wale points hatao
    wps.sort(key=lambda w: w["t"])
    clean = [wps[0]]
    for w in wps[1:]:
        if w["t"] - clean[-1]["t"] >= 1.0 / 48.0:
            clean.append(w)
    return {"duration": duration, "waypoints": clean,
            "blinks": [{"t": t, "strength": s} for (t, s) in blinks]}


def build(motion):
    """Motion ka naam do ('left','right','up','down','generate'), plan wapas milega."""
    if motion not in config.MOTIONS:
        raise ValueError(f"unknown motion '{motion}'. Allowed: {config.MOTIONS}")

    if motion == "left":
        return _plan(6.0, [(0.6, -24, 0), (3.9, 0, 0)], [(2.3, 1.0), (4.9, 1.0)])
    if motion == "right":
        return _plan(6.0, [(0.6, 24, 0), (3.9, 0, 0)], [(2.3, 1.0), (4.9, 1.0)])
    if motion == "up":
        return _plan(6.0, [(0.6, 0, -18), (3.9, 0, 0)], [(2.5, 1.0), (4.9, 1.0)])
    if motion == "down":
        return _plan(6.0, [(0.6, 0, 20), (3.9, 0, 0)], [(2.5, 1.0), (4.9, 1.0)])

    # generate: left -> right -> roll up -> return to centre -> chhote idle shifts, beech-beech mein blink
    return _plan(
        10.0,
        [(0.5, -26, 0),       # left gaze
         (2.1, 26, 0),        # right gaze (beech se guzarta hua)
         (3.9, 0, -18),       # upar "roll"
         (5.5, 0, 0),         # centre par wapas
         (6.9, -9, 2),        # chhota idle shift
         (8.0, 7, -1),        # aur ek chhota shift
         (9.0, 0, 0)],        # aakhir mein centre par wapas
        [(1.6, 1.0), (3.3, 1.0), (5.0, 1.0), (6.4, 0.9), (8.7, 1.0)],
        seed=11,
    )
import numpy as np


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def margin_mask(sock_mask, edges):
    """Socket-group ke un vertices ka mask jinke koi neighbour socket-group mein nahi hai (kinara)."""
    a, b = edges[:, 0], edges[:, 1]
    out = np.zeros(len(sock_mask), dtype=bool)
    m1 = sock_mask[a] & ~sock_mask[b]
    m2 = sock_mask[b] & ~sock_mask[a]
    out[a[m1]] = True
    out[b[m2]] = True
    return out


def compute_lid_keys(co, edges, sock_mask, center,
                     x_half=0.028, z_half=0.030,
                     up_fall=0.50, low_fall=0.35,
                     upper_close=0.68, lower_close=0.30,
                     lift=0.0005):
    """
    co        : (N,3) skin vertex positions (rest pose)
    edges     : (E,2) vertex pairs
    sock_mask : (N,) bool - 'eye_sockets' group (dono aankhon ka)
    center    : (3,) is aankh ka eyeball centre (pivot)

    Returns (keys, info):
      keys = {"Blink": coords, "UpperDown": coords, "UpperUp": coords}   (har ek (N,3) float32)
      info = diagnostics dict
    """
    co = np.asarray(co, dtype=np.float64)
    c = np.asarray(center, dtype=np.float64)
    rel = co - c
    N = len(co)

    # --- is aankh ke socket vertices (x ke hisaab se)
    near_x = np.abs(rel[:, 0]) < x_half + 0.004
    sock_eye = sock_mask & near_x

    # --- lid margin: socket ka kinara, jo aankh ke centre se aage (front) ho
    front = rel[:, 1] < -0.004                      # centre se >=4 mm aage (-Y)
    mm = margin_mask(sock_eye, edges) & front
    midx = np.where(mm)[0]
    info = {"sock_vertices": int(sock_eye.sum()), "margin_vertices": int(len(midx))}
    if len(midx) < 8:
        raise RuntimeError(f"lid margin ke vertices bahut kam mile ({len(midx)}). info={info}")

    theta_all = np.arctan2(rel[:, 2], -rel[:, 1])   # saamne se kitna upar
    z0 = rel[midx, 2].mean()                        # opening ki beech ki horizontal line
    up_m = midx[rel[midx, 2] > z0]
    lo_m = midx[rel[midx, 2] <= z0]
    info["upper_margin"] = int(len(up_m))
    info["lower_margin"] = int(len(lo_m))
    if len(up_m) < 3 or len(lo_m) < 3:
        raise RuntimeError(f"upper/lower margin split sahi nahi ({len(up_m)}/{len(lo_m)}). info={info}")

    def curve(idx):
        order = np.argsort(rel[idx, 0])
        return rel[idx, 0][order], theta_all[idx][order]

    ux, ut = curve(up_m)
    lx, lt = curve(lo_m)
    info["theta_upper_mean_deg"] = float(np.degrees(ut.mean()))
    info["theta_lower_mean_deg"] = float(np.degrees(lt.mean()))

    # --- zone: jin vertices par asar padega
    zone_skin = (np.abs(rel[:, 0]) < x_half) & (np.abs(rel[:, 2]) < z_half) & (rel[:, 1] < 0.0)
    zone = (zone_skin | sock_eye)
    zi = np.where(zone)[0]

    x = rel[zi, 0]
    th_u = np.interp(x, ux, ut)                     # x par upper margin ka angle
    th_l = np.interp(x, lx, lt)
    gap = np.clip(th_u - th_l, 0.0, None)           # palkon ke beech ka khula angle

    is_upper = rel[zi, 2] > z0
    th = theta_all[zi]
    is_sock = sock_eye[zi]

    # --- weight (1 = poori tarah hilegi, 0 = bilkul nahi)
    w = np.ones(len(zi))
    d_up = th - th_u
    d_lo = th_l - th
    w_up = 1.0 - smoothstep(0.0, up_fall, d_up)
    w_lo = 1.0 - smoothstep(0.0, low_fall, d_lo)
    w = np.where(is_upper, w_up, w_lo)
    w = np.where(is_sock, 1.0, w)                   # socket lining margin ke saath poori hilti hai
    w = np.where(is_upper & (d_up <= 0), 1.0, w)
    w = np.where(~is_upper & (d_lo <= 0), 1.0, w)
    w = np.where(is_sock, 1.0, w)

    def rotate(phi_zone, add_lift):
        """phi_zone: zone vertices ke liye X-axis rotation angles (radians). Positive = neeche."""
        out = co.copy()
        ry, rz = rel[zi, 1], rel[zi, 2]
        cs, sn = np.cos(phi_zone), np.sin(phi_zone)
        ny = cs * ry - sn * rz
        nz = sn * ry + cs * rz
        if add_lift:
            r = np.sqrt(ny * ny + nz * nz) + 1e-9
            amount = lift * w * (np.abs(phi_zone) > 1e-6)
            ny = ny + amount * ny / r
            nz = nz + amount * nz / r
        out[zi, 1] = c[1] + ny
        out[zi, 2] = c[2] + nz
        return out.astype(np.float32)

    blink_phi = np.where(is_upper, upper_close * gap * w, -lower_close * gap * w)
    # socket lining jo opening ke upar/neeche hai wo bhi apni taraf (upper/lower) ke hisaab se hilti hai
    keys = {
        "Blink": rotate(blink_phi, True),
        "UpperDown": rotate(np.where(is_upper, 0.40 * gap * w, 0.0), False),
        "UpperUp": rotate(np.where(is_upper, -0.35 * gap * w, 0.0), False),
    }
    info["zone_vertices"] = int(len(zi))
    info["max_gap_deg"] = float(np.degrees(gap.max()))
    info["max_blink_move_mm"] = float(1000.0 * np.abs(keys["Blink"] - co).max())
    return keys, info


def smooth_weights(w, edges, iterations=3):
    """Vertex weights ko neighbours ke saath average karke phailana (Laplacian smoothing)."""
    w = np.asarray(w, dtype=np.float64).copy()
    a, b = edges[:, 0], edges[:, 1]
    deg = np.bincount(a, minlength=len(w)) + np.bincount(b, minlength=len(w))
    deg = np.maximum(deg, 1)
    for _ in range(iterations):
        s = np.zeros_like(w)
        np.add.at(s, a, w[b])
        np.add.at(s, b, w[a])
        w = 0.5 * w + 0.5 * (s / deg)
    return w
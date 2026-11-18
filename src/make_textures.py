import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPZ = os.path.join(ROOT, "assets", "gnm_neutral.npz")
OUT = os.path.join(ROOT, "textures")

parser = argparse.ArgumentParser()
parser.add_argument("--quick", action="store_true", help="chhota size, jaldi test")
parser.add_argument("--skins", type=int, default=8, help="kitni skin textures (1-8)")
parser.add_argument("--skin-res", type=int, default=None, help="skin texture size (power of 2, jaise 2048)")
args = parser.parse_args()

SKIN_RES = 1024 if args.quick else 4096
EYE_RES = 512 if args.quick else 2048
if args.skin_res:
    SKIN_RES = args.skin_res
N_SKINS = max(1, min(8, args.skins))

if not os.path.isfile(NPZ):
    sys.exit("ERROR: gnm_neutral.npz nahi mili. Pehle chalao: python src/export_gnm.py")
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------
# 1) Mesh data load
# ----------------------------------------------------------------------------
d = np.load(NPZ)
quads = d["quads"]                       # (Q, 4) vertex numbers
quv = d["quad_uvs"]                      # (Q, 4, 2) tile-local UV (0..1)
qtile = d["quad_udim_tiles"]             # (Q,) 1001..1007
qcomp = d["quad_comp"]                   # (Q,) component number
comp_names = [str(n) for n in d["component_names"]]
vgroups = d["vertex_groups"]             # (46, V)
vg_names = [str(n) for n in d["vertex_group_names"]]


HAS_GEOM = all(k in d.files for k in ("verts", "joint_positions", "joint_names"))
verts = d["verts"] if HAS_GEOM else None
joint_names = [str(n) for n in d["joint_names"]] if HAS_GEOM else []
joint_pos = d["joint_positions"] if HAS_GEOM else None


def group_quads(names, require_all=True):
    """Un quads ka boolean mask jinke 4 vertices (ya koi ek) kisi bhi diye group mein hon."""
    sel = np.zeros(len(quads), dtype=bool)
    for name in names:
        if name not in vg_names:
            print("  WARNING: vertex group nahi mila:", name)
            continue
        g = vgroups[vg_names.index(name)] > 0.5
        sel |= g[quads].all(axis=1) if require_all else g[quads].any(axis=1)
    return sel


def raster(quad_sel, res, tile):
    """Quads ko UV space mein bharkar (res x res) uint8 mask banata hai. Image ka top = v=1."""
    m = np.zeros((res, res), np.uint8)
    idx = np.where(quad_sel & (qtile == tile))[0]
    if len(idx) == 0:
        return m
    uv = quv[idx]
    pts = np.stack([uv[..., 0] * (res - 1), (1.0 - uv[..., 1]) * (res - 1)], axis=-1)
    cv2.fillPoly(m, np.round(pts).astype(np.int32), 255)
    return m


def raster_weighted(quad_w, res, tile, min_w=0.02):
    """Har quad ko apni weight (0..1) ke hisaab se gray value se bharo -> float mask (blur se pehle)."""
    m = np.zeros((res, res), np.uint8)
    idx = np.where((quad_w > min_w) & (qtile == tile))[0]
    for i in idx:
        uv = quv[i]
        pts = np.stack([uv[:, 0] * (res - 1), (1.0 - uv[:, 1]) * (res - 1)], axis=-1)
        cv2.fillPoly(m, [np.round(pts).astype(np.int32)], int(round(255 * min(1.0, quad_w[i]))))
    return m.astype(np.float32) / 255.0


# ----------------------------------------------------------------------------
# 2) Noise helpers (left-right seam-free: noise wrap hota hai)
# ----------------------------------------------------------------------------
def tnoise(rng, h, w, cy, cx, wrap_y=True):
    """Smooth random noise, cx x cy cells; left-right (aur optional top-bottom) wrap karta hai."""
    small = rng.standard_normal((cy, cx)).astype(np.float32)
    p = 2
    small = np.pad(small, ((0, 0), (p, p)), mode="wrap")
    small = np.pad(small, ((p, p), (0, 0)), mode="wrap" if wrap_y else "edge")
    sx, sy = w // cx, h // cy
    big = cv2.resize(small, ((cx + 2 * p) * sx, (cy + 2 * p) * sy), interpolation=cv2.INTER_CUBIC)
    return big[p * sy:p * sy + h, p * sx:p * sx + w]


def std(a):
    a = a - a.mean()
    s = a.std()
    return a / s if s > 1e-8 else a


def fbm(rng, h, w, cells, amps):
    """Alag-alag size ke noise jodkar natural-looking variation."""
    out = np.zeros((h, w), np.float32)
    for c, a in zip(cells, amps):
        c = max(2, min(c, min(h, w)))
        out += a * std(tnoise(rng, h, w, c, c))
    return std(out)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def wblur(a, sigma_x, sigma_y=None):
    """Gaussian blur jo kinaaron par wrap karta hai (left-right seam nahi banta).
    (OpenCV ka BORDER_WRAP column ke liye kaam nahi karta, isliye pehle khud wrap-pad karte hain.)"""
    sigma_y = sigma_y if sigma_y else sigma_x
    px = int(np.ceil(4 * sigma_x)) + 2
    py = int(np.ceil(4 * sigma_y)) + 2
    padded = np.pad(a, ((py, py), (px, px)), mode="wrap")
    padded = cv2.GaussianBlur(padded, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y)
    return padded[py:-py, px:-px]


# ----------------------------------------------------------------------------
# 3) SKIN
# ----------------------------------------------------------------------------
SKIN_TILE = 1001
skin_quads = qcomp == comp_names.index("skin")


def soft_mask(names, sigma, res):
    m = raster(skin_quads & group_quads(names), res, SKIN_TILE).astype(np.float32) / 255.0
    return np.clip(cv2.GaussianBlur(m, (0, 0), sigma), 0, 1) if sigma > 0 else m


print(f"[1/4] Skin masks ban rahe hain ({SKIN_RES}px)...")
t0 = time.time()
s = SKIN_RES / 4096.0
M = {
    "cover": soft_mask([], 0, SKIN_RES),
    "lips": soft_mask(["upper_lip", "lower_lip"], 3 * s, SKIN_RES),
    "brows": soft_mask(["left_brow_region", "right_brow_region"], 4 * s, SKIN_RES),
    "cheeks": soft_mask(["left_cheek_region", "right_cheek_region", "left_zygomatic_region",
                         "right_zygomatic_region"], 40 * s, SKIN_RES),
    "nose": soft_mask(["nose_region"], 25 * s, SKIN_RES),
    "forehead": soft_mask(["forehead_region"], 40 * s, SKIN_RES),
    "orbital": soft_mask(["left_orbital_region", "right_orbital_region"], 12 * s, SKIN_RES),
    "infra": soft_mask(["left_infraorbital_region", "right_infraorbital_region"], 30 * s, SKIN_RES),
    "ears": soft_mask(["ears"], 15 * s, SKIN_RES),
}
M["cover"] = raster(skin_quads, SKIN_RES, SKIN_TILE).astype(np.float32) / 255.0

# Bhaunhein bahut moti thin: mask ko oopar-neeche se patla karo (do alag bhaunhein, beech mein gap)
_bm = raster(skin_quads & group_quads(["left_brow_region", "right_brow_region"]), SKIN_RES, SKIN_TILE)
_ky = max(3, int(round(110 * s)) | 1)
_thin = cv2.erode(_bm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, _ky)))
if int((_thin > 0).sum()) < 200:               # bahut kam bacha to purana mask hi rakho
    _thin = _bm
M["brows"] = np.clip(cv2.GaussianBlur(_thin.astype(np.float32) / 255.0, (0, 0), 5 * s), 0, 1)

# Aankh ke andar ki taraf (socket lining), palak ka kinara, aur andar ka kona (caruncle): halka pink + geela
M["socket"] = np.clip(cv2.GaussianBlur(raster(skin_quads & group_quads(["eye_sockets"], True), SKIN_RES, SKIN_TILE).astype(np.float32) / 255.0, (0, 0), 3 * s), 0, 1)
M["lidedge"] = np.clip(cv2.GaussianBlur(raster(skin_quads & group_quads(["eye_sockets"], False), SKIN_RES, SKIN_TILE).astype(np.float32) / 255.0, (0, 0), 3 * s), 0, 1)
M["caruncle"] = np.zeros((SKIN_RES, SKIN_RES), np.float32)
if HAS_GEOM and "eye_sockets" in vg_names:
    sock_v = vgroups[vg_names.index("eye_sockets")] > 0.5
    wv = np.zeros(len(verts), np.float32)
    for jn in ("left_eye", "right_eye"):
        if jn not in joint_names:
            continue
        pj = joint_pos[joint_names.index(jn)]
        cand = np.where(sock_v & (verts[:, 1] < pj[1] - 0.004) & (np.abs(verts[:, 0] - pj[0]) < 0.03))[0]
        if len(cand) == 0:
            continue
        inner = cand[np.argmin(np.abs(verts[cand, 0]))]          # naak ke sabse paas wala socket vertex = andar ka kona
        dist = np.linalg.norm(verts - verts[inner], axis=1)
        wv = np.maximum(wv, np.exp(-(dist / 0.004) ** 2).astype(np.float32))
    qw = wv[quads].mean(axis=1) * skin_quads
    M["caruncle"] = np.clip(cv2.GaussianBlur(raster_weighted(qw, SKIN_RES, SKIN_TILE), (0, 0), 2 * s), 0, 1)
else:
    print("   NOTE: geometry data nahi mila, caruncle skip")
for k, v in M.items():
    print(f"   mask {k}: {int((v > 0.5).sum())} pixels")
print(f"   ({time.time() - t0:.1f} s)")

# 8 variations: naam, base colour (RGB 0..1), blush, freckles, pore strength, seed
SKINS = [
    ("fair",   (0.87, 0.71, 0.62), 0.9, 0.5, 1.0, 11),
    ("light",  (0.81, 0.62, 0.50), 0.7, 0.2, 1.0, 12),
    ("medium", (0.73, 0.53, 0.41), 0.5, 0.0, 1.0, 13),
    ("tan",    (0.63, 0.44, 0.33), 0.5, 0.0, 0.9, 14),
    ("brown",  (0.50, 0.34, 0.25), 0.4, 0.0, 0.9, 15),
    ("deep",   (0.37, 0.24, 0.18), 0.3, 0.0, 0.8, 16),
    ("rosy",   (0.80, 0.58, 0.51), 1.0, 0.3, 1.0, 17),
    ("olive",  (0.68, 0.51, 0.37), 0.4, 0.1, 1.0, 18),
]


def make_skin(base, blush, freckles, pore, seed, res):
    rng = np.random.default_rng(seed)
    h = w = res
    base = np.array(base, np.float32)
    img = np.empty((h, w, 3), np.float32)
    img[:] = base

    # (a) bade dhabbe: tone aur laali ka halka farak
    cells = [c for c in (4, 8, 16, 32, 64) if c <= res // 8]
    lf = fbm(rng, h, w, cells, [1.0, 0.8, 0.6, 0.4, 0.3][:len(cells)])
    red = fbm(rng, h, w, cells[:4], [1.0, 0.8, 0.5, 0.3][:len(cells[:4])])
    img *= (1.0 + 0.018 * lf)[..., None]
    img[..., 1] *= 1.0 - 0.02 * red
    img[..., 2] *= 1.0 - 0.02 * red
    del lf, red

    # (b) gaal / naak / maatha: halka blush
    bl = np.clip(0.9 * M["cheeks"] + 0.8 * M["nose"] + 0.25 * M["forehead"], 0, 1)
    img[..., 0] *= 1.0 + 0.05 * blush * bl
    img[..., 1] *= 1.0 - 0.07 * blush * bl
    img[..., 2] *= 1.0 - 0.07 * blush * bl

    # (c) aankh ke aas-paas: palkon ki skin thodi gehri, aankh ke neeche halka dark
    img *= (1.0 - M["orbital"][..., None] * (1.0 - np.array([0.97, 0.91, 0.91], np.float32)))
    img *= (1.0 - M["infra"][..., None] * (1.0 - np.array([0.985, 0.955, 0.97], np.float32)))
    # kaan thode laal
    img[..., 0] *= 1.0 + 0.05 * M["ears"]
    img[..., 1] *= 1.0 - 0.06 * M["ears"]
    img[..., 2] *= 1.0 - 0.06 * M["ears"]

    # (c2) aankh ka andar: socket lining + palak ka kinara halka pink, andar ka kona zyada laal-gulabi
    wet_pink = np.clip(base * np.array([1.0, 0.55, 0.56], np.float32), 0, 1)
    k = (0.5 * M["socket"])[..., None]
    img = img * (1.0 - k) + (wet_pink * 0.92) * k
    k = (0.22 * M["lidedge"])[..., None]
    img = img * (1.0 - k) + wet_pink * k
    car_col = np.clip(base * np.array([1.0, 0.55, 0.57], np.float32), 0, 1)
    k = (0.5 * M["caruncle"])[..., None]
    img = img * (1.0 - k) + car_col * k

    # (d) hont
    lip_target = np.clip(base * np.array([1.0, 0.60, 0.64], np.float32), 0, 1)
    lip_target = lip_target * 0.9
    k = (0.85 * M["lips"])[..., None]
    img = img * (1.0 - k) + lip_target * k

    # (e) bhaunhein: dark + baal jaisi horizontal lakeerein
    hair = std(wblur(rng.standard_normal((h, w)).astype(np.float32), 4.0 * s, 0.7 * s))
    density = np.clip(0.5 + 0.7 * hair, 0, 1) * M["brows"]
    brow_col = base * 0.30
    k = (0.7 * density)[..., None]
    img = img * (1.0 - k) + brow_col * k
    del hair, density

    # (f) freckles
    if freckles > 0:
        f = std(wblur(rng.standard_normal((h, w)).astype(np.float32), 2.2 * s))
        zone = np.clip(M["cheeks"] + M["nose"], 0, 1)
        fm = np.clip((f - 1.9) / 0.6, 0, 1) * zone * freckles
        img = img * (1.0 - 0.55 * fm[..., None]) + (base * np.array([0.70, 0.52, 0.42], np.float32)) * (0.55 * fm[..., None])
        del f, fm

    # (g) pores (chhote dark dot) + fine grain + micro relief
    p = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.6, 1.1 * s)))
    pores = np.clip((-p - 1.5) / 1.2, 0, 1)
    zone = np.clip(0.55 + 0.8 * (M["cheeks"] + M["nose"]) - 0.9 * M["lips"] - 0.5 * M["orbital"], 0.1, 1.4)
    img *= (1.0 - 0.13 * pore * pores * zone)[..., None]
    grain = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.5, 0.7 * s)))
    img *= (1.0 + 0.025 * grain)[..., None]
    relief_cells = [c for c in (128, 256, 512) if c <= res // 2]
    if relief_cells:
        relief = fbm(rng, h, w, relief_cells, [1.0] * len(relief_cells))
        img *= (1.0 + 0.02 * relief)[..., None]
    del p, pores, grain

    return np.clip(img, 0.0, 1.0)


def make_bump(res):
    """Grayscale bump (height) map: pores + grain + halka relief. Blender mein Bump node ke liye."""
    rng = np.random.default_rng(7)
    h = w = res
    p = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.6, 1.1 * s)))
    pores = np.clip((-p - 1.3) / 1.2, 0, 1)
    grain = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.5, 0.7 * s)))
    cells = [c for c in (64, 128, 256, 512) if c <= res // 2]
    relief = fbm(rng, h, w, cells, [1.0] * len(cells)) if cells else np.zeros((h, w), np.float32)
    zone = np.clip(0.6 + 0.8 * (M["cheeks"] + M["nose"]) - 0.8 * M["lips"], 0.1, 1.4)
    height = 0.5 + 0.05 * grain + 0.04 * relief - 0.30 * pores * zone
    return np.clip(height, 0.0, 1.0)


def make_rough(res):
    """Roughness map (gray): oily T-zone chamakdaar, gaal/kaan matte, hont aur palak ka kinara geela/shiny, pores rough."""
    rng = np.random.default_rng(21)
    h = w = res
    cells = [c for c in (4, 8, 16, 32) if c <= res // 8]
    low = fbm(rng, h, w, cells, [1.0, 0.7, 0.4, 0.3][:len(cells)])
    rough = 0.54 + 0.04 * low
    rough -= 0.14 * np.clip(0.8 * M["forehead"] + 1.0 * M["nose"], 0, 1)      # T-zone oily
    rough += 0.03 * M["cheeks"] + 0.08 * M["ears"]
    p = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.6, 1.1 * s)))
    rough += 0.10 * np.clip((-p - 1.3) / 1.2, 0, 1)                           # pores thode rough
    grain = std(wblur(rng.standard_normal((h, w)).astype(np.float32), max(0.5, 0.7 * s)))
    rough += 0.02 * grain
    rough = rough * (1.0 - 0.75 * M["lips"]) + 0.36 * 0.75 * M["lips"]        # hont
    wet = np.clip(1.0 * M["socket"] + 0.8 * M["lidedge"] + 0.8 * M["caruncle"], 0, 1)
    rough = rough * (1.0 - wet) + 0.12 * wet                                   # geela (wet) hissa
    return np.clip(rough, 0.08, 0.9)


def save_rgb(path, rgb):
    bgr = (np.clip(rgb, 0, 1)[..., ::-1] * 255.0 + 0.5).astype(np.uint8)   # cv2 BGR chahta hai
    cv2.imwrite(path, bgr, [cv2.IMWRITE_PNG_COMPRESSION, 3])


print(f"[2/4] {N_SKINS} skin textures ban rahi hain...")
skin_files = []
skin_previews = []
for i, (name, base, blush, frk, pore, seed) in enumerate(SKINS[:N_SKINS], start=1):
    t0 = time.time()
    img = make_skin(base, blush, frk, pore, seed, SKIN_RES)
    fn = f"skin_{i:02d}_{name}.png"
    save_rgb(os.path.join(OUT, fn), img)
    skin_files.append(fn)
    skin_previews.append(cv2.resize(img, (384, 384), interpolation=cv2.INTER_AREA))
    print(f"   {fn}  ({time.time() - t0:.1f} s)")
    del img

bump = make_bump(SKIN_RES)
cv2.imwrite(os.path.join(OUT, "skin_bump.png"), (bump * 255.0 + 0.5).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 3])
print("   skin_bump.png  (bump/height map, sab skins ke saath use hota hai)")
del bump
rough = make_rough(SKIN_RES)
cv2.imwrite(os.path.join(OUT, "skin_rough.png"), (rough * 255.0 + 0.5).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 3])
print("   skin_rough.png (roughness map: oily T-zone, geela palak/hont)")
del rough

# ----------------------------------------------------------------------------
# 4) EYES (iris + sclera)
# ----------------------------------------------------------------------------
print(f"[3/4] Aankhon ki UV masks aur iris textures ({EYE_RES}px)...")
IRIS_COLORS = {
    "brown": ((0.55, 0.36, 0.16), (0.22, 0.12, 0.05)),
    "hazel": ((0.62, 0.52, 0.22), (0.27, 0.28, 0.11)),
    "blue":  ((0.55, 0.68, 0.80), (0.13, 0.27, 0.44)),
}

eye_info = {}
eye_masks = {}
for eye in ("left", "right"):
    comp = comp_names.index(f"{eye}_eye")
    sel = qcomp == comp
    tiles = sorted(set(int(t) for t in qtile[sel]))
    iris_sel = group_quads(["irises", "pupils"], True) & sel
    if iris_sel.sum() < 10:                       # fallback: koi ek vertex bhi group mein ho
        iris_sel = group_quads(["irises", "pupils"], False) & sel
    # iris wala tile = jahan sabse zyada iris quads hon
    counts = {t: int((iris_sel & (qtile == t)).sum()) for t in tiles}
    iris_tile = max(counts, key=counts.get)
    pupil_sel = group_quads(["pupils"], True) & sel
    sclera_sel = group_quads(["scleras"], True) & sel
    iris_m = raster(iris_sel, EYE_RES, iris_tile)
    pupil_m = raster(pupil_sel, EYE_RES, iris_tile)
    sclera_m = raster(sclera_sel, EYE_RES, iris_tile)
    cover_m = raster(sel, EYE_RES, iris_tile)
    iris_all = np.maximum(iris_m, pupil_m)
    area = float((iris_all > 0).sum())
    if area < 20:
        sys.exit(f"ERROR: {eye} eye mein iris ke pixels nahi mile (UV mask khali). Debug sheet bhejo.")
    mo = cv2.moments((iris_all > 0).astype(np.uint8), binaryImage=True)
    cx, cy = mo["m10"] / mo["m00"], mo["m01"] / mo["m00"]
    R = float(np.sqrt(area / np.pi))
    p_area = float((pupil_m > 0).sum())
    Rp = float(np.sqrt(p_area / np.pi)) if p_area > 20 else 0.4 * R
    eye_info[eye] = {
        "tiles": tiles, "tile_iris_quad_counts": counts, "iris_tile": int(iris_tile),
        "other_tiles": [t for t in tiles if t != iris_tile],
        "center_px": [cx, cy], "iris_radius_px": R, "pupil_radius_px": Rp,
        "eye_res": EYE_RES,
    }
    eye_masks[eye] = (iris_m, pupil_m, sclera_m, cover_m)
    print(f"   {eye}: tiles={tiles} iris_tile={iris_tile} centre=({cx:.0f},{cy:.0f}) "
          f"iris R={R:.0f}px pupil R={Rp:.0f}px  quad counts={counts}")


def polar_field(rng, ang_cells, rad_cells, Wt=1024, Hr=256):
    """Polar noise: x = angle (wrap), y = radius."""
    return std(tnoise(rng, Hr, Wt, rad_cells, ang_cells, wrap_y=False))


def make_eye(eye, colors, seed):
    inner, outer = [np.array(c, np.float32) for c in colors]
    cx, cy = eye_info[eye]["center_px"]
    R = eye_info[eye]["iris_radius_px"]
    Rp = eye_info[eye]["pupil_radius_px"]
    h = w = EYE_RES
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xx - cx, yy - cy
    rn = np.sqrt(dx * dx + dy * dy) / R                       # 1.0 = iris ki kinaari
    theta = np.arctan2(dy, dx)

    Wt, Hr = 1024, 256
    mx = ((theta + np.pi) / (2 * np.pi) * Wt).astype(np.float32)
    my = (np.clip(rn, 0, 1.6) / 1.6 * (Hr - 1)).astype(np.float32)

    def sample(field):
        return cv2.remap(field, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    fib = 0.7 * sample(polar_field(rng, 512, 16)) + 0.3 * sample(polar_field(rng, 256, 8))
    crypt = sample(polar_field(rng, 64, 8))

    t = smoothstep(0.15, 1.0, rn)[..., None]
    col = inner * (1.0 - t) + outer * t
    collar = np.exp(-(((rn - 0.42) / 0.07) ** 2)) * np.clip(0.6 + 0.4 * crypt, 0, 1.2)
    col = col * (1.0 + 0.35 * collar[..., None])
    col = col * (1.0 + 0.30 * fib[..., None] + 0.12 * crypt[..., None])
    col = col * (1.0 - 0.75 * smoothstep(0.80, 1.0, rn))[..., None]       # limbal ring
    pr = max(Rp / R, 0.05)
    pupil_w = 1.0 - smoothstep(pr * 0.93, pr * 1.06, rn)
    col = col * (1.0 - pupil_w[..., None]) + 0.02 * pupil_w[..., None]

    # sclera: off-white + halki peeli/gulabi variation + naso (veins)
    low = fbm(rng, h, w, [c for c in (4, 8, 16) if c <= h // 8], [1.0, 0.6, 0.4][:len([c for c in (4, 8, 16) if c <= h // 8])])
    sc = np.array([0.92, 0.90, 0.87], np.float32) * (1.0 + 0.012 * low)[..., None]
    sc[..., 1:] *= (1.0 - 0.02 * np.clip(low, 0, 3))[..., None]
    vc = [c for c in (16, 32, 64) if c <= h // 8]
    ridge = 1.0 - np.abs(fbm(rng, h, w, vc, [1.0, 0.6, 0.3][:len(vc)]))
    veins = np.clip((ridge - 0.955) / 0.045, 0, 1) * np.clip((rn - 1.2) / 0.8, 0, 1) * 0.25
    sc = sc * (1.0 - veins[..., None]) + np.array([0.75, 0.30, 0.28], np.float32) * veins[..., None]

    alpha = (1.0 - smoothstep(0.97, 1.03, rn))[..., None]
    out = sc * (1.0 - alpha) + col * alpha
    return np.clip(out, 0.0, 1.0)


eye_files = []
eye_previews = []
for cname, colors in IRIS_COLORS.items():
    for eye, seed in (("left", 101), ("right", 202)):
        t0 = time.time()
        img = make_eye(eye, colors, seed + len(cname))
        fn = f"iris_{cname}_{eye}.png"
        save_rgb(os.path.join(OUT, fn), img)
        eye_files.append(fn)
        eye_previews.append(cv2.resize(img, (384, 384), interpolation=cv2.INTER_AREA))
        print(f"   {fn}  ({time.time() - t0:.1f} s)")

# ----------------------------------------------------------------------------
# 5) Debug / preview sheets + notes
# ----------------------------------------------------------------------------
print("[4/4] Debug sheets aur notes...")


def sheet(images, cols, path):
    rows = (len(images) + cols - 1) // cols
    hh, ww = images[0].shape[:2]
    canvas = np.zeros((rows * hh, cols * ww, 3), np.float32)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        canvas[r * hh:(r + 1) * hh, c * ww:(c + 1) * ww] = im
    save_rgb(path, canvas)


sheet(skin_previews, 4, os.path.join(OUT, "_sheet_skins.png"))
sheet(eye_previews, 3, os.path.join(OUT, "_sheet_irises.png"))

# UV masks debug: skin (rang-bhari) + dono aankhon ke masks
P = 600
skin_dbg = np.full((SKIN_RES, SKIN_RES, 3), 0.25, np.float32)
skin_dbg[M["cover"] > 0.5] = 0.55
for key, color in (("cheeks", (0.2, 0.8, 0.2)), ("nose", (0.9, 0.9, 0.1)), ("orbital", (0.9, 0.2, 0.9)),
                   ("brows", (0.2, 0.3, 1.0)), ("lips", (1.0, 0.1, 0.1)), ("socket", (0.1, 0.9, 0.9)),
                   ("caruncle", (1.0, 0.6, 0.0))):
    k = (M[key] > 0.35)[..., None]
    skin_dbg = np.where(k, np.array(color, np.float32), skin_dbg)
panels = [cv2.resize(skin_dbg, (P, P), interpolation=cv2.INTER_AREA)]
for eye in ("left", "right"):
    iris_m, pupil_m, sclera_m, cover_m = eye_masks[eye]
    dbg = np.full((EYE_RES, EYE_RES, 3), 0.15, np.float32)
    dbg[cover_m > 0] = 0.45
    dbg[sclera_m > 0] = (0.9, 0.9, 0.9)
    dbg[iris_m > 0] = (0.1, 0.8, 0.2)
    dbg[pupil_m > 0] = (0.1, 0.2, 0.9)
    cxp, cyp = eye_info[eye]["center_px"]
    cv2.circle(dbg, (int(cxp), int(cyp)), int(eye_info[eye]["iris_radius_px"]), (1.0, 0.0, 0.0), max(1, EYE_RES // 400))
    panels.append(cv2.resize(dbg, (P, P), interpolation=cv2.INTER_AREA))
sheet(panels, 3, os.path.join(OUT, "_debug_uv_masks.png"))

eye_info["files"] = {"skins": skin_files, "irises": eye_files, "bump": "skin_bump.png", "roughness": "skin_rough.png"}
with open(os.path.join(OUT, "eye_info.json"), "w", encoding="utf-8") as fh:
    json.dump(eye_info, fh, indent=2)

with open(os.path.join(OUT, "TEXTURE_NOTES.txt"), "w", encoding="utf-8") as fh:
    fh.write(
        "TEXTURE NOTES\n"
        "-------------\n"
        "Ye saari textures PROCEDURAL hain: code (NumPy/OpenCV) se noise, GNM UV regions ke masks aur\n"
        "rang-niyamon se banayi gayi hain. Ye scanned ya photographic skin textures NAHI hain.\n"
        f"Skin maps: {SKIN_RES}x{SKIN_RES}, GNM UDIM tile 1001 (face+head). Left-right edge seam-free (wrap noise).\n"
        f"Iris/sclera maps: {EYE_RES}x{EYE_RES}, GNM eye tiles (left_eye iris tile {eye_info['left']['iris_tile']}, "
        f"right_eye iris tile {eye_info['right']['iris_tile']}).\n"
        "Bhaunhein skin texture mein painted hain; sir par baal (hair) nahi hain.\n"
    )

print("TEXTURES_DONE")
print("Files:", OUT)
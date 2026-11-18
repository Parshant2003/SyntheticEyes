import os
import sys

from gnm.shape import gnm_numpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
MODEL_FILE = os.path.join(ROOT, "assets", "gnm_head.npz")
os.makedirs(DOCS, exist_ok=True)

lines = []


def out(text):
    """Print bhi karo aur file ke liye yaad bhi rakho."""
    print(text)
    lines.append(text)


if not os.path.isfile(MODEL_FILE):
    sys.exit("ERROR: model file nahi mili: " + MODEL_FILE)

out("Loading GNM head from local file...")
gnm = gnm_numpy.GNM.from_custom_file(MODEL_FILE)
out("LOAD_OK")

for name in ("identity_dim", "expression_dim", "num_joints"):
    out(f"{name} = {getattr(gnm, name, '?')}")

out("--- public attributes ---")
for name in sorted(dir(gnm)):
    if name.startswith("_"):
        continue
    try:
        val = getattr(gnm, name)
    except Exception as e:
        out(f"{name}: <error {e}>")
        continue
    if callable(val):
        continue
    shape = getattr(val, "shape", None)
    if shape is not None:
        out(f"{name}: array shape={tuple(shape)} dtype={getattr(val, 'dtype', '?')}")
    elif isinstance(val, (list, tuple, dict, set)):
        out(f"{name}: {type(val).__name__} len={len(val)}")
    else:
        out(f"{name}: {type(val).__name__} = {str(val)[:80]}")

# Model ke saath aane wali built-in textures ki list
tex_dir = os.path.join(ROOT, "assets", "GNM-main", "gnm", "shape", "data", "textures")
out("--- built-in textures ---")
if os.path.isdir(tex_dir):
    for f in sorted(os.listdir(tex_dir)):
        out(f)
else:
    out("textures folder nahi mila: " + tex_dir)

with open(os.path.join(DOCS, "gnm_inspect.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
out("INSPECT_DONE")
"""Sets the texture import options that keep the web download small.

Colour art (foliage atlases, the textures the glTF models carry, the tiled ground
textures) is imported as lossy WebP (compress/mode=1) instead of lossless: about a
fifth of the size in the .pck, and gzip cannot squeeze an already-compressed
lossless WebP any further. Alpha stays lossless inside lossy WebP, so the alpha-
scissor cut-outs keep their edges. Data textures (world_data, world_shade, noise)
and the UI icons/portraits stay lossless.

terrain.glb is one big mesh drawn with its own shader and no shadow casting, so it
needs no LODs, shadow mesh or tangents (1.15 MB -> 0.42 MB imported); the rigged
characters skip LODs and tangents too (no shader here reads tangents).

The ground textures also get import-time mipmaps (world-space tiling needs them;
ground_fx.gd otherwise builds them at runtime on every start).

Run after new .png files have been imported once (Godot writes the .import files),
then re-import:

python3 tools/tune_imports.py && godot --headless --path game --import
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "game")
QUALITY = 0.8
# glob -> extra params
RULES = {
    "assets/models/*.png": {},
    "assets/textures/foliage/*.png": {},
    "assets/textures/ground/*.png": {"mipmaps/generate": "true"},
}


TEX = {"compress/mode": "1", "compress/lossy_quality": str(QUALITY), "detect_3d/compress_to": "0"}
SCENE_RULES = {
    "assets/models/terrain.glb": {"meshes/generate_lods": "false", "meshes/create_shadow_meshes": "false",
                                  "meshes/ensure_tangents": "false"},
    "assets/models/char_*.glb": {"meshes/generate_lods": "false", "meshes/ensure_tangents": "false"},
}


def tune(path, extra, base=TEX):
    s = open(path, encoding="utf-8").read()
    want = dict(base)
    want.update(extra)
    out = s
    for k, v in want.items():
        pat = re.compile(r"^" + re.escape(k) + r"=.*$", re.M)
        out = pat.sub(k + "=" + v, out) if pat.search(out) else out.rstrip("\n") + "\n" + k + "=" + v + "\n"
    if out != s:
        open(path, "w", encoding="utf-8").write(out)
        return True
    return False


def main():
    changed = 0
    for g, extra in RULES.items():
        for png in sorted(glob.glob(os.path.join(GAME, g))):
            imp = png + ".import"
            if os.path.exists(imp) and tune(imp, extra):
                changed += 1
                print("tuned", os.path.relpath(imp, GAME))
    for g, params in SCENE_RULES.items():
        for src in sorted(glob.glob(os.path.join(GAME, g))):
            imp = src + ".import"
            if os.path.exists(imp) and tune(imp, params, {}):
                changed += 1
                print("tuned", os.path.relpath(imp, GAME))
    print(changed, "import files changed")


if __name__ == "__main__":
    main()

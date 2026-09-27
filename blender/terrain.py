"""Island terrain, ground masks and world layout for Sawit The Franchise.

python3 blender/terrain.py

Outputs
  game/assets/models/terrain.glb       island mesh (Blender grid, displaced)
  game/assets/textures/world_data.png  RGBA masks, 512 px over 200 m:
                                       R height ((h+5)/7), G sand, B road, A grass tone
  game/assets/textures/noise.png       tileable detail noise for the shaders
  game/data/layout.json                buildings, parcels, props and scattered decor
  blender/previews/map.png             debug top-down map
"""
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_DIR = os.path.join(ROOT, "game", "assets", "textures")
DATA_DIR = os.path.join(ROOT, "game", "data")
MODELS_DIR = os.path.join(ROOT, "game", "assets", "models")
PREVIEW_DIR = os.path.join(ROOT, "blender", "previews")
for d in (TEX_DIR, DATA_DIR, MODELS_DIR, PREVIEW_DIR):
    os.makedirs(d, exist_ok=True)

N = 512
W = L.WORLD_SIZE
PX = W / N
rng = np.random.default_rng(7)

# pixel centre coordinates (godot x, z)
coords = (np.arange(N) + 0.5) * PX - W / 2
X, Z = np.meshgrid(coords, coords)  # row = z (north at row 0), col = x


def fractal_noise(n, octaves, beta=2.0, seed=0):
    """Tileable noise via random-phase FFT with a 1/f^beta spectrum, normalised to 0..1."""
    r = np.random.default_rng(seed)
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1.0
    amp = 1.0 / f ** (beta / 2.0)
    amp[f < 1.0 / n * octaves[0]] = 0
    amp[f > 1.0 / n * octaves[1]] = 0
    phase = r.uniform(0, 2 * np.pi, (n, n))
    spec = amp * np.exp(1j * phase)
    img = np.real(np.fft.ifft2(spec))
    img -= img.min()
    img /= img.max()
    return img


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ island
CX, CZ = 2.0, -2.0
theta = np.arctan2(Z - CZ, X - CX)
rho = np.sqrt(((X - CX) / 76.0) ** 2 + ((Z - CZ) / 60.0) ** 2)
edge = (1 + 0.045 * np.sin(3 * theta + 0.7) + 0.03 * np.sin(5 * theta + 2.0)
        + 0.018 * np.sin(9 * theta + 1.1) + 0.01 * np.sin(14 * theta + 0.3))
# south-east cove, like the reference screenshot
edge -= 0.16 * np.exp(-((theta - 0.62) / 0.16) ** 2)
coast_noise = fractal_noise(N, (4, 40), 2.2, seed=3)
edge += (coast_noise - 0.5) * 0.05
land = rho < edge

dist_in = ndimage.distance_transform_edt(land) * PX
dist_out = ndimage.distance_transform_edt(~land) * PX
sd = dist_in - dist_out  # >0 on land

# ------------------------------------------------------------------ height
h = np.zeros_like(sd)
beach = (sd >= 0) & (sd < 9)
h[beach] = -0.55 + 0.55 * smoothstep(0, 9, sd[beach])
sea = sd < 0
h[sea] = -0.55 - 3.6 * (1 - np.exp(sd[sea] / 12.0))
h = ndimage.gaussian_filter(h, 0.8)

# ------------------------------------------------------------------ masks
n_mid = fractal_noise(N, (6, 60), 2.0, seed=11)
sand = 1.0 - smoothstep(5.5, 7.5, sd + (n_mid - 0.5) * 4.0)


def seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    vx, vz = bx - ax, bz - az
    wx, wz = px - ax, pz - az
    t = np.clip((wx * vx + wz * vz) / (vx * vx + vz * vz), 0, 1)
    dx, dz = px - (ax + t * vx), pz - (az + t * vz)
    return np.sqrt(dx * dx + dz * dz)


road_d = np.full_like(X, 1e9)
for line in L.ROADS:
    for a, b in zip(line[:-1], line[1:]):
        road_d = np.minimum(road_d, seg_dist(X, Z, a, b))
wobble = (fractal_noise(N, (20, 120), 1.5, seed=5) - 0.5) * 0.9
road = 1.0 - smoothstep(L.ROAD_WIDTH / 2 - 0.4, L.ROAD_WIDTH / 2 + 0.5, road_d + wobble)
road *= (sd > 2).astype(float)

grass_tone = fractal_noise(N, (3, 30), 2.4, seed=21)

enc_h = np.clip((h + 5.0) / 7.0, 0, 1)
# full-precision heights for the game (float16, row-major, north row first)
h.astype("<f2").tofile(os.path.join(DATA_DIR, "height.bin"))
rgba = np.stack([enc_h, sand, road, grass_tone], axis=-1)
Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(TEX_DIR, "world_data.png"))

# detail noise (RGB = three different tileable noises)
nz = np.stack([fractal_noise(256, (4, 64), 1.8, seed=31), fractal_noise(256, (8, 128), 1.4, seed=32),
               fractal_noise(256, (2, 16), 2.2, seed=33)], axis=-1)
Image.fromarray((nz * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(TEX_DIR, "noise.png"))


def sample(arr, x, z):
    j = int(np.clip((x + W / 2) / PX, 0, N - 1))
    i = int(np.clip((z + W / 2) / PX, 0, N - 1))
    return float(arr[i, j])


# ------------------------------------------------------------------ keep-out zones
parcel_rects = []
for p in L.PARCELS:
    cx, cz = p["center"]
    hw = L.PARCEL_COLS * L.TILE / 2 + 1.6
    hd = L.PARCEL_ROWS * L.TILE / 2 + 1.6
    parcel_rects.append((cx - hw, cz - hd, cx + hw, cz + hd))
    if sample(sd, cx, cz) < 12:
        print("WARNING parcel near coast", p["name"], sample(sd, cx, cz))

BUILDING_R = {"kantor": 6.5, "toko": 6, "warung": 5, "pabrik": 11, "pos_calo": 4.5, "rumah_a": 5.5,
              "rumah_b": 5.5, "rumah_c": 5.5, "dermaga": 0}
circles = []
for b in L.BUILDINGS:
    r = BUILDING_R.get(b["model"], 5)
    if r:
        circles.append((b["pos"][0], b["pos"][1] + 1.0, r))
        if sample(sd, *b["pos"]) < 8:
            print("WARNING building near coast", b["id"], sample(sd, *b["pos"]))
for m, pos, _ in L.PROPS:
    circles.append((pos[0], pos[1], 1.6 if m != "truck" else 3.5))
for pos in L.TENT_SPOTS:
    circles.append((pos[0], pos[1], 2.5))
def snap_to_coast(pos, target=1.5):
    """Slide a coastal set piece towards the island centre until it sits just inside the shore."""
    x, z = pos
    for _ in range(200):
        if sample(sd, x, z) >= target:
            break
        dx, dz = CX - x, CZ - z
        ln = math.hypot(dx, dz)
        x += dx / ln * 0.5
        z += dz / ln * 0.5
    return (round(x, 2), round(z, 2))


CLIFFS = [(m, snap_to_coast(pos, 2.0 if m == "cliff_a" else 1.0), r) for m, pos, r in L.CLIFFS]
for m, pos, _ in CLIFFS:
    circles.append((pos[0], pos[1], 5 if m == "cliff_a" else 2.5))
circles.append((L.PLAYER_SPAWN[0], L.PLAYER_SPAWN[1], 4))


def blocked(x, z, pad=0.0, allow_road=False):
    for (x0, z0, x1, z1) in parcel_rects:
        if x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad:
            return True
    for (cx, cz, r) in circles:
        if (x - cx) ** 2 + (z - cz) ** 2 < (r + pad) ** 2:
            return True
    if not allow_road and sample(road_d, x, z) < L.ROAD_WIDTH / 2 + 1.0 + pad:
        return True
    return False


decor = []
placed = []  # (x, z, r) for spacing
prng = random.Random(42)


def try_place(model, count, r_self, sd_min, sd_max, region=None, scale=(0.85, 1.2), tries=4000, pad=0.0,
              min_gap=None):
    n = 0
    t = 0
    gap = r_self if min_gap is None else min_gap
    while n < count and t < tries:
        t += 1
        x = prng.uniform(-95, 95)
        z = prng.uniform(-95, 95)
        if region and not region(x, z):
            continue
        s = sample(sd, x, z)
        if not (sd_min <= s <= sd_max):
            continue
        if blocked(x, z, pad):
            continue
        if any((x - px) ** 2 + (z - pz) ** 2 < (gap + pr) ** 2 for px, pz, pr in placed):
            continue
        y = (sample(enc_h, x, z) * 7.0) - 5.0
        sc = prng.uniform(*scale)
        decor.append({"model": model, "pos": [round(x, 2), round(y, 3), round(z, 2)],
                      "rot": round(prng.uniform(0, 360), 1), "scale": round(sc, 2)})
        placed.append((x, z, r_self))
        n += 1
    return n


north = lambda x, z: z < -30 or abs(x) > 50
try_place("tree_big", 22, 3.5, 12, 999, region=north, pad=1.5)
try_place("tree_big", 10, 3.5, 12, 999, pad=2.0)
try_place("coconut", 34, 2.0, 4.0, 10.0, scale=(0.85, 1.15), pad=0.5)
try_place("banana", 16, 1.4, 10, 999, pad=0.8)
try_place("bush_a", 34, 1.2, 9, 999, pad=0.4)
try_place("bush_b", 34, 1.2, 9, 999, pad=0.4)
try_place("rock_b", 14, 1.0, 6, 999, pad=0.3)
try_place("rock_a", 26, 0.5, 2, 999, pad=0.2)
try_place("rock_c", 4, 1.8, 3, 12, pad=0.5)
try_place("flowers", 90, 0.5, 9, 999, scale=(0.8, 1.3), pad=0.2)
try_place("grass_tuft", 420, 0.25, 7.5, 999, scale=(0.8, 1.4), min_gap=0.3)

for m, pos, rot in CLIFFS:
    y = sample(enc_h, *pos) * 7.0 - 5.0
    decor.append({"model": m, "pos": [pos[0], round(max(y, -1.2), 3), pos[1]], "rot": rot, "scale": 1.0})


def height_at(x, z):
    return round(sample(enc_h, x, z) * 7.0 - 5.0, 3)


out = {
    "world_size": W,
    "water_level": L.WATER_LEVEL,
    "tile": L.TILE,
    "parcel_cols": L.PARCEL_COLS,
    "parcel_rows": L.PARCEL_ROWS,
    "parcels": [{"id": p["id"], "name": p["name"], "owner": p["owner"], "center": list(p["center"])}
                for p in L.PARCELS],
    "buildings": [{"id": b["id"], "model": b["model"], "pos": [b["pos"][0], height_at(*b["pos"]), b["pos"][1]],
                   "rot": b["rot"]} for b in L.BUILDINGS],
    "props": [{"model": m, "pos": [p[0], height_at(*p), p[1]], "rot": r} for m, p, r in L.PROPS],
    "tent_spots": [list(p) for p in L.TENT_SPOTS],
    "roads": [[list(pt) for pt in line] for line in L.ROADS],
    "player_spawn": list(L.PLAYER_SPAWN),
    "decor": decor,
}
with open(os.path.join(DATA_DIR, "layout.json"), "w") as f:
    json.dump(out, f, indent=1)
print("decor placed:", {m: sum(1 for d in decor if d["model"] == m) for m in sorted({d["model"] for d in decor})})

# ------------------------------------------------------------------ debug map
col = np.zeros((N, N, 3))
water_c = np.array([0.35, 0.72, 0.68])
grass_c = np.array([0.43, 0.57, 0.28])
sand_c = np.array([0.93, 0.87, 0.69])
road_c = np.array([0.62, 0.50, 0.34])
col[:] = grass_c * (0.85 + 0.3 * grass_tone[..., None])
col = col * (1 - sand[..., None]) + sand_c * sand[..., None]
col = col * (1 - road[..., None]) + road_c * road[..., None]
wet = h < L.WATER_LEVEL
col[wet] = water_c * (0.6 + 0.4 * np.clip(1 + (h[wet] - L.WATER_LEVEL) / 3.5, 0, 1))[:, None]
img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), "RGB").resize((1024, 1024), Image.NEAREST)
dr = ImageDraw.Draw(img)
S = 1024 / W


def to_px(x, z):
    return ((x + W / 2) * S, (z + W / 2) * S)


for (x0, z0, x1, z1) in parcel_rects:
    dr.rectangle([to_px(x0, z0), to_px(x1, z1)], outline=(120, 60, 20), width=2)
for b in L.BUILDINGS:
    x, y = to_px(*b["pos"])
    dr.rectangle([x - 8, y - 8, x + 8, y + 8], fill=(200, 90, 60))
    dr.text((x + 10, y - 6), b["id"], fill=(0, 0, 0))
dcol = {"tree_big": (30, 80, 30), "coconut": (120, 160, 40), "banana": (90, 170, 60), "rock_a": (150, 150, 150),
        "rock_b": (130, 130, 130), "rock_c": (100, 100, 100), "cliff_a": (70, 70, 70)}
for d in decor:
    if d["model"] in dcol:
        x, y = to_px(d["pos"][0], d["pos"][2])
        r = 5 if d["model"] in ("tree_big", "cliff_a") else 3
        dr.ellipse([x - r, y - r, x + r, y + r], fill=dcol[d["model"]])
x, y = to_px(*L.PLAYER_SPAWN)
dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 0, 255))
img.save(os.path.join(PREVIEW_DIR, "map.png"))

# ------------------------------------------------------------------ minimap base (game HUD)
mm = np.zeros((N, N, 4))
mm[..., :3] = np.array([0.44, 0.60, 0.30]) * (0.92 + 0.12 * grass_tone[..., None])
mm[..., :3] = mm[..., :3] * (1 - sand[..., None]) + np.array([0.94, 0.88, 0.70]) * sand[..., None]
mm[..., :3] = mm[..., :3] * (1 - road[..., None]) + np.array([0.80, 0.66, 0.46]) * road[..., None]
mm[..., 3] = 1.0
under = h < L.WATER_LEVEL
depth = np.clip((L.WATER_LEVEL - h) / 3.0, 0, 1)
mm[under, :3] = (np.array([0.55, 0.84, 0.78])[None, :] * (1 - depth[under, None]) + np.array([0.30, 0.62, 0.66])[None, :] * depth[under, None])
mm[under, 3] = 1.0 - 0.75 * depth[under]
Image.fromarray((np.clip(mm, 0, 1) * 255).astype(np.uint8), "RGBA").resize((256, 256), Image.LANCZOS).save(
    os.path.join(TEX_DIR, "minimap.png"))

# ------------------------------------------------------------------ terrain mesh (Blender)
if "--no-mesh" not in sys.argv:
    import bpy  # noqa: E402
    from common import reset_scene, mat, set_mat, export_glb, empty  # noqa: E402

    reset_scene()
    SEG = 160
    xs = np.linspace(-W / 2, W / 2, SEG + 1)
    hs = ndimage.map_coordinates(h, [[(z + W / 2) / PX - 0.5 for z in xs for x in xs],
                                     [(x + W / 2) / PX - 0.5 for z in xs for x in xs]], order=1, mode="nearest")
    verts = []
    k = 0
    for z in xs:
        for x in xs:
            verts.append((x, -z, float(hs[k])))  # blender y = -godot z
            k += 1
    faces = []
    for i in range(SEG):
        for j in range(SEG):
            a = i * (SEG + 1) + j
            faces.append((a, a + SEG + 1, a + SEG + 2, a + 1))
    me = bpy.data.meshes.new("TerrainMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    # flip to face up (+Z) if needed
    me.calc_loop_triangles()
    if me.polygons[0].normal.z < 0:
        for p in me.polygons:
            p.flip()
    for p in me.polygons:
        p.use_smooth = True
    root = empty("terrain")
    o = bpy.data.objects.new("Ground", me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = root
    set_mat(o, mat("M_Ground", "grass"))
    export_glb(root, "terrain")

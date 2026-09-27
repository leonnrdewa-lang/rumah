"""Island terrain, ground masks and world layout for Sawit The Franchise.

python3 blender/terrain.py

Outputs
  game/assets/models/terrain.glb       island mesh (Blender grid, displaced)
  game/assets/textures/world_data.png  RGBA masks, 512 px over 200 m:
                                       R height ((h+5)/7), G sand, B road, A grass tone
  game/assets/textures/noise.png       tileable detail noise for the shaders
  game/assets/textures/world_shade.png v2 RGBA 512 px: R contact shade (fake AO under
                                       trees/plants), G dryness, B forest-floor litter,
                                       A road direction (1 = along x)
  game/data/layout.json                buildings, parcels, props, scattered decor and the
                                       v2 dense "undergrowth" {model: [x,y,z,rot,scale,...]}
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
# v2: dead ends (road tips that do not join another road or a building) narrow
# and fade out over their last ~4 m instead of ending in a blunt round cap
def _dead_ends():
    ends = []
    for li, line in enumerate(L.ROADS):
        for pt in (line[0], line[-1]):
            joined = False
            for lj, other in enumerate(L.ROADS):
                if lj == li:
                    continue
                for a, b in zip(other[:-1], other[1:]):
                    if float(seg_dist(np.array(pt[0]), np.array(pt[1]), a, b)) < 1.0:
                        joined = True
            near_bld = any(math.hypot(pt[0] - bb["pos"][0], pt[1] - bb["pos"][1]) < 3.0 for bb in L.BUILDINGS)
            if not joined and not near_bld:
                ends.append(pt)
    return ends


DEAD_ENDS = _dead_ends()
for ex, ez in DEAD_ENDS:
    road_d = road_d + 1.9 * (1.0 - smoothstep(0.0, 4.5, np.hypot(X - ex, Z - ez)))
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


# v2: the camera looks north from 11 m up, so a tall tree just south (+z) of a parcel or
# building fills the bottom of the screen; keep tall decor out of those strips
TALL = ("tree_big", "sawit_wild", "banana", "coconut")

# approximate building footprints (half extents, local x/z) - measured from the GLBs
BUILDING_HALF = {"kantor": (2.7, 2.4), "toko": (3.0, 2.1), "warung": (2.1, 1.8), "pabrik": (7.1, 5.1),
                 "pos_calo": (1.7, 1.7), "rumah_a": (2.9, 2.5), "rumah_b": (2.5, 2.7), "rumah_c": (2.9, 2.2)}


def door_point(b):
    """Where world.gd puts the door interaction (1.1 m in front of the footprint)."""
    hz = BUILDING_HALF[b["model"]][1]
    th = math.radians(b["rot"])
    return b["pos"][0] + math.sin(th) * (hz + 1.1), b["pos"][1] + math.cos(th) * (hz + 1.1)


# villagers wander ~5 m around their door (Npc radius) and the player talks to them there
DOOR_PTS = [door_point(b) for b in L.BUILDINGS if b["model"] in BUILDING_HALF]


def tall_block(x, z):
    # not beside a road, and not in the strip just south of one (it would hide the road)
    for dz, m in ((0.0, 4.5), (3.5, 3.5), (6.5, 2.0)):
        if sample(road_d, x, z - dz) < L.ROAD_WIDTH / 2 + m:
            return True
    for (x0, z0, x1, z1) in parcel_rects:
        if x0 - 2.5 < x < x1 + 2.5 and z0 < z < z1 + 9.0:
            return True
    for b in L.BUILDINGS:
        bx, bz = b["pos"]
        if abs(x - bx) < 8.0 and bz - 3.0 < z < bz + 10.0:
            return True
    # the villagers' yards (door +- 5 m) and the camera strip south of them
    for dx, dz in DOOR_PTS:
        if abs(x - dx) < 11.0 and dz - 6.5 < z < dz + 12.0:
            return True
    return False


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
        if model in TALL and tall_block(x, z):
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
# v2: more big trees so forest patches have edges, and old wild oil palms
# ("sawit_wild" = sawit_3 without its fruit bunches) in groves between the roads
try_place("tree_big", 14, 3.2, 14, 999, pad=1.5, tries=12000)
try_place("sawit_wild", 26, 2.6, 11, 999, scale=(0.9, 1.15), pad=1.2, tries=20000)
try_place("coconut", 34, 2.0, 4.0, 10.0, scale=(0.85, 1.15), pad=0.5)
try_place("banana", 16, 1.4, 10, 999, pad=0.8)
try_place("bush_a", 34, 1.2, 9, 999, pad=0.4)
try_place("bush_b", 34, 1.2, 9, 999, pad=0.4)
try_place("rock_b", 14, 1.0, 6, 999, pad=0.3)
try_place("rock_a", 26, 0.5, 2, 999, pad=0.2)
try_place("rock_c", 4, 1.8, 3, 12, pad=0.5)
try_place("banana", 10, 1.4, 10, 999, pad=0.8)
# (v1 grass_tuft / flowers decor is replaced by the dense undergrowth below)

for m, pos, rot in CLIFFS:
    y = sample(enc_h, *pos) * 7.0 - 5.0
    decor.append({"model": m, "pos": [pos[0], round(max(y, -1.2), 3), pos[1]], "rot": rot, "scale": 1.0})


def height_at(x, z):
    return round(sample(enc_h, x, z) * 7.0 - 5.0, 3)


# ------------------------------------------------------------------ dense undergrowth (v2)
# Thousands of small plants scattered like the target screenshot: dense along road
# verges, around buildings, at forest edges and between parcels; sparse in open
# fields; never on roads, doors, parcel planting spots or interaction points.
# Stored compactly per model as flat [x, y, z, rot_deg, scale, ...] arrays.
# (world.gd filters again against the exact building boxes at load time.)
urng = np.random.default_rng(99)
upy = random.Random(99)


def to_local(b, x, z):
    th = math.radians(b["rot"])
    dx, dz = x - b["pos"][0], z - b["pos"][1]
    # inverse of Godot's rotation about +Y
    return dx * math.cos(th) - dz * math.sin(th), dx * math.sin(th) + dz * math.cos(th)


# rasterised zones over the 512 grid (godot x = columns, z = rows)
bld_dist = np.full_like(X, 1e9)      # distance to the nearest building footprint
door_block = np.zeros_like(X, bool)
door_low = np.zeros_like(X, bool)     # around the doorway: only low grass / flowers
for b in L.BUILDINGS:
    if b["model"] not in BUILDING_HALF:
        continue
    hx, hz = BUILDING_HALF[b["model"]]
    th = math.radians(b["rot"])
    dx, dz = X - b["pos"][0], Z - b["pos"][1]
    lx = dx * math.cos(th) - dz * math.sin(th)
    lz = dx * math.sin(th) + dz * math.cos(th)
    qx = np.maximum(np.abs(lx) - hx, 0)
    qz = np.maximum(np.abs(lz) - hz, 0)
    inside = (np.abs(lx) < hx) & (np.abs(lz) < hz)
    d = np.sqrt(qx ** 2 + qz ** 2)
    d[inside] = -1
    bld_dist = np.minimum(bld_dist, d)
    # keep the doorway and a short approach in front of it clear (+z local is the front);
    # low grass (see DOOR_LOW) fills its edges so the yard does not read as a bare patch
    door_block |= (np.abs(lx) < 1.5) & (lz > hz - 0.5) & (lz < hz + 3.0)
    door_low |= (np.abs(lx) < 2.6) & (lz > hz - 0.5) & (lz < hz + 4.5)

tile_pts = []
sign_pts = []
parcel_in = np.zeros_like(X, bool)    # planting grid of a parcel (+ margin)
parcel_ring = np.full_like(X, 1e9)    # distance outside the parcel rectangle
for p in L.PARCELS:
    cx, cz = p["center"]
    for idx in range(L.PARCEL_COLS * L.PARCEL_ROWS):
        col, row = idx % L.PARCEL_COLS, idx // L.PARCEL_COLS
        tile_pts.append((cx + (col - (L.PARCEL_COLS - 1) * 0.5) * L.TILE, cz + (row - (L.PARCEL_ROWS - 1) * 0.5) * L.TILE))
    sign_pts.append((cx - (L.PARCEL_COLS * L.TILE) * 0.5 - 0.6, cz + (L.PARCEL_ROWS * L.TILE) * 0.5 + 0.8))
    hx = L.PARCEL_COLS * L.TILE / 2 + 0.4
    hz = L.PARCEL_ROWS * L.TILE / 2 + 0.4
    qx = np.maximum(np.abs(X - cx) - hx, 0)
    qz = np.maximum(np.abs(Z - cz) - hz, 0)
    parcel_in |= (np.abs(X - cx) < hx) & (np.abs(Z - cz) < hz)
    parcel_ring = np.minimum(parcel_ring, np.sqrt(qx ** 2 + qz ** 2))

tree_d = np.full_like(X, 1e9)          # distance to the nearest big tree / wild palm
for d in decor:
    if d["model"] in ("tree_big", "sawit_wild"):
        tree_d = np.minimum(tree_d, np.hypot(X - d["pos"][0], Z - d["pos"][2]))

# planting spots: how close each plant may grow to a spot's centre. Low grass reaches
# the (smaller) piringan's edge, ferns and cover plants stay out of the harvest ring,
# taller plants keep 1.6-1.8 m clear so the palm, its fruit and the tile state stay
# readable (world.gd filters again at 0.85 m)
TILE_R = {"grass_a": 0.95, "grass_b": 0.95, "flowers_white": 1.0, "flowers_yellow": 1.0, "leaf_low": 1.05,
          "fern_low": 1.15, "rock_a": 1.2, "frond_fallen": 1.5, "fern_a": 1.35, "fern_b": 1.35, "keladi": 1.65,
          "shrub_a": 1.8, "shrub_b": 1.8, "vine_log": 2.2, "pile_fronds": 2.2}
keep_out = [(x, z, r) for (x, z, r) in circles if r < 3.4] + [(x, z, 1.7) for x, z in sign_pts]
for b in L.BUILDINGS:          # jetty and its road end
    if b["model"] == "dermaga":
        keep_out.append((b["pos"][0], b["pos"][1], 4.0))
for m, pos, _ in L.PROPS:
    keep_out.append((pos[0], pos[1], 3.2 if m == "truck" else (0.6 if m == "lampu" else 1.1)))
for d in decor:
    r = {"tree_big": 0.9, "sawit_wild": 0.8, "coconut": 0.5, "banana": 0.6, "bush_a": 0.7, "bush_b": 0.7,
         "rock_b": 0.8, "rock_c": 1.6, "rock_a": 0.35, "cliff_a": 4.5}.get(d["model"], 0.5)
    keep_out.append((d["pos"][0], d["pos"][2], r))
for pos in L.TENT_SPOTS:
    keep_out.append((pos[0], pos[1], 2.4))
keep_out.append((L.PLAYER_SPAWN[0], L.PLAYER_SPAWN[1], 1.8))
ko_grid = {}
for (x, z, r) in keep_out:
    for gx in range(int(math.floor((x - r) / 4)), int(math.floor((x + r) / 4)) + 1):
        for gz in range(int(math.floor((z - r) / 4)), int(math.floor((z + r) / 4)) + 1):
            ko_grid.setdefault((gx, gz), []).append((x, z, r))
tile_grid = {}
for (x, z) in tile_pts:
    for gx in range(int(math.floor((x - 2.5) / 4)), int(math.floor((x + 2.5) / 4)) + 1):
        for gz in range(int(math.floor((z - 2.5) / 4)), int(math.floor((z + 2.5) / 4)) + 1):
            tile_grid.setdefault((gx, gz), []).append((x, z))


def kept_out(x, z, pad=0.0):
    for (cx, cz, r) in ko_grid.get((int(math.floor(x / 4)), int(math.floor(z / 4))), ()):
        if (x - cx) ** 2 + (z - cz) ** 2 < (r + pad) ** 2:
            return True
    return False


def near_tile(x, z, r):
    for (tx, tz) in tile_grid.get((int(math.floor(x / 4)), int(math.floor(z / 4))), ()):
        if (x - tx) ** 2 + (z - tz) ** 2 < r * r:
            return True
    return False


land_ok = (sd > 3.0) & (sand < 0.5)
road_edge = road_d - L.ROAD_WIDTH / 2
# polish round: the v2 review measured undergrowth on only ~30-35% of the land pixels
# against ~2/3 in the target (and the player's parcel read as lawn with brown discs), so
# the carpet is ~3x denser. It is mostly the cheap cover plants (grass cards, and the
# procedural fern_low / leaf_low rosettes built in undergrowth.gd, 14-24 tris) around
# thickets of modelled ferns / shrubs / keladi (200-320 tris); the game only draws the
# plants under the camera, which pays for it.
zone_verge = land_ok & (road_edge > 0.25) & (road_edge < 5.0)
zone_wall = land_ok & (bld_dist > 0.15) & (bld_dist < 2.2) & ~door_block & ~door_low
zone_bld = land_ok & (bld_dist > 0.15) & (bld_dist < 6.0) & ~door_block
zone_parcel = land_ok & (parcel_ring > 0.2) & (parcel_ring < 5.5)
zone_forest = land_ok & (tree_d > 0.9) & (tree_d < 10.0)
zone_inner = land_ok & parcel_in
zone_beach = (sd > 2.0) & (sand > 0.35) & (sand < 0.9)
blocked_px = (road_edge < 0.25) | door_block | (bld_dist <= 0.15) | (sd < 2.0)

# (name, mask, big plants / m2, their species weights, cover plants / m2, their weights);
# the zone with the most plants wins
# (grass_b is the seed-head grass: a little of it reads as wild meadow, a lot of it as
# pale khaki wisps; the target's ground layer is mostly small leafy plants)
CARPET_OPEN = {"grass_a": 3.0, "grass_b": 1.0, "fern_low": 2.0, "leaf_low": 1.6, "flowers_white": 0.9,
               "flowers_yellow": 0.7, "frond_fallen": 0.1, "rock_a": 0.03}
ZONES = [
    ("wall", zone_wall, 0.9, {"shrub_a": 1.3, "shrub_b": 1.2, "keladi": 1.5, "fern_b": 0.6, "fern_a": 0.4,
                              "pile_fronds": 0.05},
     2.6, {"grass_a": 2.0, "grass_b": 0.8, "leaf_low": 2.2, "fern_low": 1.6, "flowers_white": 1.0,
           "flowers_yellow": 0.8}),
    ("verge", zone_verge, 0.2, {"fern_a": 1.0, "keladi": 0.6, "shrub_a": 0.5, "fern_b": 0.5},
     3.2, {"grass_a": 3.0, "grass_b": 1.2, "fern_low": 2.0, "leaf_low": 1.6, "flowers_white": 1.1,
           "flowers_yellow": 0.8, "frond_fallen": 0.12, "rock_a": 0.04}),
    ("bld", zone_bld, 0.45, {"shrub_a": 1.2, "shrub_b": 1.2, "keladi": 1.4, "fern_b": 0.6, "pile_fronds": 0.08},
     3.0, {"grass_a": 2.5, "grass_b": 0.8, "leaf_low": 2.0, "fern_low": 1.4, "flowers_white": 1.2,
           "flowers_yellow": 0.9}),
    ("parcel", zone_parcel, 0.35, {"fern_a": 1.0, "fern_b": 1.0, "keladi": 0.6, "shrub_b": 0.4, "pile_fronds": 0.1},
     3.2, {"grass_b": 1.0, "grass_a": 2.0, "fern_low": 2.4, "leaf_low": 1.4, "frond_fallen": 0.5,
           "flowers_white": 0.6}),
    ("forest", zone_forest, 0.4, {"fern_a": 1.3, "fern_b": 1.3, "shrub_a": 0.9, "shrub_b": 0.9, "keladi": 1.0,
                                  "vine_log": 0.12},
     2.6, {"grass_b": 1.0, "grass_a": 1.5, "fern_low": 2.6, "leaf_low": 1.6, "frond_fallen": 0.5, "rock_a": 0.06}),
    # the planting grid: low plants only, so paths and tiles stay readable
    ("inner", zone_inner, 0.08, {"fern_a": 1.0, "fern_b": 1.0},
     3.6, {"grass_b": 0.8, "grass_a": 2.5, "fern_low": 2.6, "leaf_low": 2.0, "flowers_white": 0.5,
           "flowers_yellow": 0.3, "frond_fallen": 0.6}),
    ("open", land_ok, 0.14, {"fern_a": 0.5, "fern_b": 0.3, "shrub_b": 0.25, "shrub_a": 0.15, "keladi": 0.3},
     2.8, CARPET_OPEN),
    ("beach", zone_beach, 0.0, {}, 0.3, {"grass_b": 1.0, "grass_a": 0.6}),
]
# the door approach keeps only low plants
DOOR_LOW = {"grass_a", "grass_b", "flowers_white", "flowers_yellow", "leaf_low"}
UG_SCALE = {"grass_a": (1.0, 1.6), "grass_b": (1.0, 1.6), "fern_a": (0.9, 1.4), "fern_b": (0.9, 1.4),
            "keladi": (0.85, 1.3), "shrub_a": (0.95, 1.5), "shrub_b": (0.95, 1.5), "flowers_white": (0.8, 1.2),
            "flowers_yellow": (0.8, 1.2), "frond_fallen": (0.65, 0.9), "vine_log": (0.8, 1.05),
            "pile_fronds": (0.9, 1.1), "rock_a": (0.45, 0.9), "fern_low": (0.85, 1.35), "leaf_low": (0.8, 1.3)}
UG_GAP = {"grass_a": 0.3, "grass_b": 0.3, "flowers_white": 0.3, "flowers_yellow": 0.3, "fern_a": 0.55, "fern_b": 0.55,
          "keladi": 0.5, "shrub_a": 0.8, "shrub_b": 0.8, "frond_fallen": 0.9, "vine_log": 1.3, "pile_fronds": 1.1,
          "rock_a": 0.4, "fern_low": 0.45, "leaf_low": 0.35}
UG_PAD = {"shrub_a": 0.5, "shrub_b": 0.5, "vine_log": 0.8, "pile_fronds": 0.6, "frond_fallen": 0.5}
DENSITY = float(os.environ.get("UG_DENSITY", "1.0"))

# plants grow in clumps (thickets of shrubs/ferns with open grass between), like the target
clump = smoothstep(0.42, 0.72, fractal_noise(N, (10, 90), 1.4, seed=51))
BIG = ("shrub_a", "shrub_b", "keladi", "fern_a", "fern_b", "vine_log", "pile_fronds")
SMALL = ("grass_a", "grass_b", "flowers_white", "flowers_yellow", "leaf_low")
zone_id = np.full(X.shape, -1)
best = np.zeros_like(X)
for zi in range(len(ZONES) - 1, -1, -1):   # earlier zones win ties
    name, mask, bd, _, cd, _ = ZONES[zi]
    upd = mask & ((bd + cd) >= best * 0.999)
    best[upd] = bd + cd
    zone_id[upd] = zi
zone_id[blocked_px] = -1
# thickets: 2.4x the big plants and a little less carpet; elsewhere the reverse
thick = 0.55 + 1.9 * clump
vary = (0.85 + 0.3 * n_mid) * DENSITY

undergrowth = {}
ug_pts = {}
ug_list = []


def ug_free(x, z, gap, small=False):
    # small clumps may tuck in closer to their neighbours (grass under fern edges)
    f = 0.42 if small else 0.55
    cx, cz = int(math.floor(x)), int(math.floor(z))
    for gx in (cx - 1, cx, cx + 1):
        for gz in (cz - 1, cz, cz + 1):
            for (px, pz, pg) in ug_pts.get((gx, gz), ()):
                if (x - px) ** 2 + (z - pz) ** 2 < (f * (gap + pg)) ** 2:
                    return False
    return True


rejects = {"keep_out": 0, "road": 0, "spacing": 0, "tile": 0}
cell_area = PX * PX


def pick(weights):
    names = list(weights.keys())
    r = upy.uniform(0, sum(weights.values()))
    for nm in names:
        r -= weights[nm]
        if r <= 0:
            return nm
    return names[-1]


def place(m, x, z):
    gap = UG_GAP[m]
    sc = upy.uniform(*UG_SCALE[m])
    y = height_at(x, z)
    undergrowth.setdefault(m, []).extend([round(x, 2), y, round(z, 2), round(upy.uniform(0, 360), 0), round(sc, 2)])
    ug_pts.setdefault((int(math.floor(x)), int(math.floor(z))), []).append((x, z, gap))
    ug_list.append((m, x, z, sc))


# Two passes so the carpet cannot crowd out the thickets: first the big plants (ferns,
# shrubs, keladi, logs), then the cover plants (grass, fern_low / leaf_low rosettes,
# flowers, fronds, pebbles) in the gaps.
for big_pass in (True, False):
    for i, j in zip(*np.nonzero(zone_id >= 0)):
        zi = zone_id[i, j]
        _, _, bd, bw, cd, cw = ZONES[zi]
        weights = dict(bw if big_pass else cw)
        dens = bd * thick[i, j] if big_pass else cd * (1.25 - 0.3 * clump[i, j])
        if door_low[i, j]:
            weights = {nm: w for nm, w in weights.items() if nm in DOOR_LOW}
            if big_pass or not weights:
                continue
        if not weights or dens <= 0:
            continue
        n = urng.poisson(dens * vary[i, j] * cell_area)
        for _ in range(n):
            x = float(X[i, j] + urng.uniform(-PX / 2, PX / 2))
            z = float(Z[i, j] + urng.uniform(-PX / 2, PX / 2))
            m = pick(weights)
            if kept_out(x, z):
                rejects["keep_out"] += 1
                continue
            if near_tile(x, z, TILE_R[m] + UG_PAD.get(m, 0.0) * 0.5):
                rejects["tile"] += 1
                continue
            # big pieces must not poke onto the road or into keep-out circles
            if m in UG_PAD and (sample(road_edge, x, z) < UG_PAD[m] + 0.3 or kept_out(x, z, UG_PAD[m])):
                rejects["road"] += 1
                continue
            if not ug_free(x, z, UG_GAP[m], m in SMALL):
                rejects["spacing"] += 1
                continue
            place(m, x, z)
print("undergrowth:", {m: len(v) // 5 for m, v in sorted(undergrowth.items())}, "total", len(ug_list), "rejected", rejects)

# ------------------------------------------------------------------ world_shade.png (v2)
# R contact shade (fake AO under canopies and plants), G dryness, B forest-floor
# litter, A road direction (1 = road runs along x). Baked from the layout so the
# terrain shader can darken the ground under trees without real-time AO.
shade_acc = np.zeros_like(X)
litter = np.zeros_like(X)


def splat(acc, x, z, sigma, amount):
    r = sigma * 3.0
    j0 = max(int((x - r + W / 2) / PX), 0)
    j1 = min(int((x + r + W / 2) / PX) + 1, N)
    i0 = max(int((z - r + W / 2) / PX), 0)
    i1 = min(int((z + r + W / 2) / PX) + 1, N)
    if j0 >= j1 or i0 >= i1:
        return
    gx = X[i0:i1, j0:j1] - x
    gz = Z[i0:i1, j0:j1] - z
    acc[i0:i1, j0:j1] += amount * np.exp(-(gx * gx + gz * gz) / (2 * sigma * sigma))


# (sigma m, amount): fix round 1 raised these so every plant sits in a dark contact patch
DECOR_SHADE = {"tree_big": (2.4, 1.3), "sawit_wild": (1.7, 1.0), "coconut": (1.0, 0.6), "banana": (1.1, 0.9),
               "bush_a": (0.9, 0.95), "bush_b": (0.9, 0.95), "rock_b": (0.6, 0.6), "rock_c": (1.2, 0.6),
               "rock_a": (0.35, 0.35), "cliff_a": (3.0, 0.6)}
for d in decor:
    if d["model"] in DECOR_SHADE:
        sg, am = DECOR_SHADE[d["model"]]
        s = d.get("scale", 1.0)
        splat(shade_acc, d["pos"][0], d["pos"][2], sg * s, am)
    if d["model"] == "tree_big":
        splat(litter, d["pos"][0], d["pos"][2], 1.8 * d.get("scale", 1.0), 0.9)
    elif d["model"] == "sawit_wild":
        splat(litter, d["pos"][0], d["pos"][2], 1.2 * d.get("scale", 1.0), 0.7)
# Contact shade pools tightly under the thickets; the (now dense) cover carpet only adds
# a faint patch, or the whole lawn would darken evenly (the v2 frames read murky olive
# because ~60% of the parcel ground sat in baked shade)
UG_SHADE = {"shrub_a": (0.45, 1.3), "shrub_b": (0.45, 1.3), "keladi": (0.32, 0.8), "fern_a": (0.32, 0.75),
            "fern_b": (0.32, 0.75), "vine_log": (0.5, 0.5), "pile_fronds": (0.5, 0.5), "grass_a": (0.2, 0.03),
            "grass_b": (0.2, 0.03), "frond_fallen": (0.4, 0.1), "rock_a": (0.25, 0.3),
            "flowers_white": (0.18, 0.02), "flowers_yellow": (0.18, 0.02), "fern_low": (0.28, 0.14),
            "leaf_low": (0.2, 0.08)}
for (m, x, z, sc) in ug_list:
    sg, am = UG_SHADE.get(m, (0.3, 0.1))
    splat(shade_acc, x, z, sg * sc, am)
# parcels: a little shade and litter where the palms will be
for (x, z) in tile_pts:
    splat(shade_acc, x, z, 1.1, 0.15)
    splat(litter, x, z, 0.9, 0.12)
shade_r = 1.0 - np.exp(-shade_acc * 1.1)
shade_r = ndimage.gaussian_filter(shade_r, 0.7)

dry = 0.1 + (fractal_noise(N, (4, 40), 2.0, seed=41) - 0.5) * 0.45
dry += 0.32 * np.exp(-((road_edge - 0.5) / 0.8) ** 2)                 # road verges
dry -= 0.45 * np.exp(-np.maximum(tree_d - 2.0, 0) / 5.0)               # lush near forest
dry -= 0.3 * np.exp(-np.maximum(parcel_ring, 0) / 3.0)                 # lush plantation
dry += 0.25 * (1 - smoothstep(4.0, 10.0, sd))                          # salty beach grass
dry -= 0.35 * shade_r
dry = np.clip(ndimage.gaussian_filter(dry, 1.0), 0, 1)

# road direction: which way the nearest road segment runs
best_d = np.full_like(X, 1e9)
horiz = np.zeros_like(X)
for line in L.ROADS:
    for a, b in zip(line[:-1], line[1:]):
        dseg = seg_dist(X, Z, a, b)
        upd = dseg < best_d
        best_d[upd] = dseg[upd]
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        horiz[upd] = abs(b[0] - a[0]) / ln
horiz = ndimage.gaussian_filter(horiz, 3.0)

litter = np.clip(ndimage.gaussian_filter(litter, 0.8), 0, 1)
shade_img = np.stack([shade_r, dry, litter, horiz], axis=-1)
Image.fromarray((np.clip(shade_img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(
    os.path.join(TEX_DIR, "world_shade.png"))
_imp = os.path.join(TEX_DIR, "world_shade.png.import")
if not os.path.exists(_imp):
    # data texture: lossless, no mipmaps (same settings as world_data.png)
    with open(_imp, "w") as f:
        f.write('[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\ncompress/mode=0\n'
                'mipmaps/generate=false\nprocess/fix_alpha_border=false\ndetect_3d/compress_to=0\n')

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
    # v2: {model: [x, y, z, rot_deg, scale, x, y, z, ...]} small plants without collision
    "undergrowth": undergrowth,
}
ug_json = json.dumps(out.pop("undergrowth"), separators=(",", ":"))
txt = json.dumps(out, indent=1)
# keep the small keys readable, the big undergrowth arrays compact
txt = txt[:txt.rindex("}")].rstrip() + ',\n "undergrowth": ' + ug_json + "\n}\n"
with open(os.path.join(DATA_DIR, "layout.json"), "w") as f:
    f.write(txt)
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
ucol = {"shrub_a": (60, 110, 40), "shrub_b": (60, 110, 40), "fern_a": (80, 140, 50), "fern_b": (80, 140, 50),
        "fern_low": (95, 150, 60), "leaf_low": (90, 160, 70),
        "keladi": (70, 150, 70), "flowers_white": (250, 250, 240), "flowers_yellow": (250, 210, 60)}
for m, arr in undergrowth.items():
    if m in ucol:
        for k in range(0, len(arr), 5):
            x, y = to_px(arr[k], arr[k + 2])
            dr.point((x, y), fill=ucol[m])
dcol["sawit_wild"] = (160, 120, 40)
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

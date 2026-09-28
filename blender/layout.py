"""World layout for Sawit The Franchise.

All coordinates are GODOT world coordinates in metres: x = east, z = south,
y = up. (Blender scripts convert with blender_y = -z.)  Buildings face +z
(south, towards the camera) unless `rot` says otherwise (degrees around y).

terrain.py reads this, paints the ground masks, scatters decoration and
writes game/data/layout.json for the Godot world builder.

Map v3 ("5x map"): the island is ~5x the area of v2 (450 m square, the old village
sits in its middle unchanged), two rivers cross it (the jetty now stands in the
river lagoon east of the mill), five bridges carry the roads over them, and six
hamlets (dusun) of generated houses surround the old village, each with villagers
and their gardens. Palm tiles are planted in a staggered (triangular, "mata lima")
grid 3.7 m apart instead of a square 4.4 m one, 5 x 4 = 20 palms per parcel.
"""
import math
import random

WORLD_SIZE = 450.0          # terrain square side (m), centred on the origin
WATER_LEVEL = -0.30

# island: an ellipse (radii in m) around (ISLAND_CX, ISLAND_CZ) with a wavy coast
ISLAND_CX, ISLAND_CZ = 2.0, -2.0
ISLAND_RX, ISLAND_RZ = 172.0, 140.0


def island_rho(x, z):
    """< 1 inside the (smooth, noise-free) island ellipse."""
    return math.hypot((x - ISLAND_CX) / ISLAND_RX, (z - ISLAND_CZ) / ISLAND_RZ)


# Rivers: polylines [(x, z), ...] with a half width (m) of open water. The ends that lie
# outside the island run into the sea; "ponds" are round pools (x, z, r) at a source.
RIVERS = [
    {"name": "Sungai Besar", "hw": 4.6,
     "pts": [(101, -170), (98, -104), (98, -76), (93, -58), (90, -40), (90, -16), (86, 0), (86, 24),
             (92, 36), (100, 48), (100, 76), (108, 100), (116, 125), (124, 170)]},
    {"name": "Kali Kecil", "hw": 3.8,
     "pts": [(-50, -110), (-72, -100), (-92, -80), (-100, -58), (-100, -32), (-102, -14), (-102, 26),
             (-107, 44), (-120, 68), (-138, 96), (-162, 128)]},
]
# the river widens into a lagoon east of the mill: the jetty and the boats are there
LAGOONS = [(87.0, 12.0, 12.5)]
PONDS = [(-50.0, -110.0, 8.0)]

# Bridges (model, centre, rot): the models run along X, 14 m long (2.5 m ramps at each end,
# deck 0.55 m up), 3.2 m wide. rot 0 = along x. world.gd makes them walkable.
BRIDGES = [
    {"model": "jembatan_beton", "pos": (90.0, -28.0), "rot": 0},
    {"model": "jembatan_kayu", "pos": (100.0, 62.0), "rot": 0},
    {"model": "jembatan_beton", "pos": (-102.0, 8.0), "rot": 0},
    {"model": "jembatan_kayu", "pos": (-100.0, -45.0), "rot": 0},
    {"model": "jembatan_kayu", "pos": (98.0, -85.0), "rot": 0},
]
BRIDGE_LEN = 14.0
BRIDGE_W = 3.2

# Dirt roads as polylines [(x, z), ...]
ROADS = [
    [(-62, 8), (-30, 9), (0, 8), (30, 7), (62, 8)],          # Jalan Desa (main)
    [(-48, -26), (-20, -25), (10, -26), (44, -26)],           # Jalan Utara
    [(-46, -26), (-46, 8)],
    [(-4, -26), (-4, 8)],
    [(34, -26), (34, 8)],
    [(-4, 8), (-4, 22)],                                      # to Kantor
    [(-46, 8), (-46, 22)],                                    # to Kakek's plot
    [(30, 7), (30, 22)],                                      # to Tarno's plot
    [(62, 8), (73, 12.5)],                                      # to the jetty
    # farm track along the north edge of the player's parcel, past the gudang (the
    # target's shed + truck on a dirt road beside the palms)
    [(-46, 20.4), (-30, 20.7), (-4, 20.4)],
    [(-20, -26), (-20, -36)],
    [(18, -26), (18, -36)],
    # ---- map v3: roads out to the hamlets (straight over the bridges)
    [(44, -26), (70, -28), (160, -28)],                       # east over Sungai Besar -> Dusun Seberang
    [(128, -28), (128, -62)],
    [(45, 8), (45, 40), (62, 62), (152, 62)],                 # south-east over the wooden bridge -> Dusun Muara
    [(126, 62), (126, 94)],
    [(-62, 8), (-160, 8)],                                    # west over Kali Kecil -> Dusun Barat
    [(-132, 8), (-132, 42)],
    [(-48, -26), (-75, -45), (-152, -45)],                    # north-west -> Dusun Bukit
    [(-128, -45), (-128, -72)],
    [(34, -26), (34, -85)],                                   # north -> Dusun Utara
    [(-30, -85), (122, -85)],
    [(45, 40), (30, 58), (30, 88)],                           # south -> Dusun Selatan
    [(-38, 88), (62, 88)],
]
ROAD_WIDTH = 3.0

# Palm parcels: 5 columns (x) by 4 rows (z), staggered (odd rows shifted half a column),
# 3.7 m between neighbours (rows 3.2 m apart).
# (env fix round v2 used a square 4.4 m grid; map v3 packs the palms closer, as on a real
# estate, and the game scales the palms to the grid so the crowns still do not touch)
TILE = 3.7
PARCEL_COLS = 5
PARCEL_ROWS = 4
ROW_STEP = round(TILE * math.sqrt(3.0) / 2.0, 3)


def tile_offsets():
    """Planting spots relative to a parcel centre, index = row * cols + col."""
    out = []
    for r in range(PARCEL_ROWS):
        for c in range(PARCEL_COLS):
            dx = (c - (PARCEL_COLS - 1) * 0.5) * TILE + (0.25 if r % 2 else -0.25) * TILE
            dz = (r - (PARCEL_ROWS - 1) * 0.5) * ROW_STEP
            out.append((round(dx, 3), round(dz, 3)))
    return out


PARCEL_HALF = ((PARCEL_COLS - 1) * 0.5 * TILE + 0.25 * TILE, (PARCEL_ROWS - 1) * 0.5 * ROW_STEP)

PARCELS = [
    {"id": 0, "name": "Lahan Kantor", "owner": "player", "center": (-16.4, 28.2)},
    {"id": 1, "name": "Kebun Kakek Darman", "owner": "kakek", "center": (-44, 31)},
    {"id": 2, "name": "Kebun Bu Sari", "owner": "ibu", "center": (-27, -12)},
    {"id": 3, "name": "Kebun Pak Kades", "owner": "kades", "center": (14, -12)},
    {"id": 4, "name": "Kebun Nenek Ijah", "owner": "nenek", "center": (-20, -44)},
    {"id": 5, "name": "Kebun Mas Joko", "owner": "pemuda", "center": (18, -44)},
    {"id": 6, "name": "Kebun Pak Tarno", "owner": "petani", "center": (22, 30)},
    # ---- map v3: the hamlets' gardens
    {"id": 7, "name": "Kebun Pak Haji Somad", "owner": "somad", "center": (114, -8)},
    {"id": 8, "name": "Kebun Bang Ucok", "owner": "ucok", "center": (144, -8)},
    {"id": 9, "name": "Kebun Rian", "owner": "rian", "center": (144, -50)},
    {"id": 10, "name": "Kebun Mbak Wati", "owner": "wati", "center": (124, 40)},
    {"id": 11, "name": "Kebun Pak Slamet", "owner": "slamet", "center": (78, 80)},
    {"id": 12, "name": "Kebun Kakek Dullah", "owner": "dullah", "center": (-146, -14)},
    {"id": 13, "name": "Kebun Bu Lastri", "owner": "lastri", "center": (-80, 72)},
    {"id": 14, "name": "Kebun Nenek Romlah", "owner": "romlah", "center": (-76, 44)},
    {"id": 15, "name": "Kebun Mbok Darsih", "owner": "darsih", "center": (-70, -72)},
    {"id": 16, "name": "Kebun Mas Yanto", "owner": "yanto", "center": (-4, -66)},
    {"id": 17, "name": "Kebun Bu Bidan Rina", "owner": "bidan", "center": (-12, 70)},
    {"id": 18, "name": "Kebun Pak RT Bejo", "owner": "rt", "center": (56, 108)},
    {"id": 19, "name": "Kebun Pak Karta", "owner": "karta", "center": (60, -104)},
]

# Buildings: model name, position, rotation (deg), interaction id
BUILDINGS = [
    {"id": "kantor", "model": "kantor", "pos": (-3, 31), "rot": 0},
    {"id": "toko", "model": "toko", "pos": (-14, -1), "rot": 0},
    {"id": "warung", "model": "warung", "pos": (8, 1), "rot": 0},
    {"id": "pabrik", "model": "pabrik", "pos": (50, -9), "rot": 0},
    {"id": "calo", "model": "pos_calo", "pos": (56, 18), "rot": 0},
    {"id": "rumah_kakek", "model": "rumah_c", "pos": (-58, 22), "rot": 90},
    {"id": "rumah_ibu", "model": "rumah_b", "pos": (-36, 0), "rot": 0},
    {"id": "rumah_kades", "model": "rumah_a", "pos": (24, 0), "rot": 0},
    {"id": "rumah_nenek", "model": "rumah_a", "pos": (-33, -38), "rot": 90},
    {"id": "rumah_pemuda", "model": "rumah_b", "pos": (31, -38), "rot": -90},
    {"id": "rumah_petani", "model": "rumah_c", "pos": (37, 24), "rot": -90},
    {"id": "dermaga", "model": "dermaga", "pos": (73, 13), "rot": -90},
    # the plantation's shed beside the farm track, north-west of the player's parcel
    {"id": "gudang", "model": "gudang", "pos": (-22.2, 16.0), "rot": 0},
]

# Small set pieces (model, pos, rot)
PROPS = [
    ("sumur", (-4, 13), 0), ("bangku", (12, 11.5), 0), ("bangku", (-10, 11.5), 0),
    ("lampu", (-6.5, 11), 0), ("lampu", (18, 11), 0), ("lampu", (-40, 11), 0), ("lampu", (40, 11), 0),
    ("lampu", (-4, 26), 0), ("lampu", (60, 12), 0),
    ("karung_pupuk", (-18.5, 3.2), 20), ("karung_pupuk", (-17.6, 3.6), -10), ("crate", (-9.5, 3.4), 10),
    ("gerobak", (3, 34), 30), ("tumpukan_tbs", (45, 0.5), 0), ("tumpukan_tbs", (48.5, 0.2), 40),
    ("truck", (57, 1), -20), ("crate", (60, 21), 0), ("crate", (60.8, 20.2), 25), ("meja", (5, 5), 0),
    ("perahu", (90, 18.5), 80), ("perahu", (90, -8), 10), ("perahu", (99, 58), 5), ("perahu", (-101, 20), 0),
    ("jerigen", (11.5, 4.6), 0), ("jerigen", (12.1, 4.9), 30),
    ("pagar", (-27.1, 16.4), 90), ("pagar", (-27.1, 14.4), 90),
    # the gudang yard: a loaded truck, drums and a pile of fresh bunches by the track
    ("truck", (-14.9, 17.3), 75), ("drum", (-18.6, 18.0), 0), ("drum", (-18.0, 18.4), 40),
    ("tumpukan_tbs", (-26.0, 18.6), 20), ("crate", (-26.6, 17.6), 15),
    # the mill yard: oil drums and stacked sacks by the loading dock
    ("drum", (42.6, -2.6), 0), ("drum", (43.3, -2.2), 30), ("drum", (42.9, -1.6), 70),
    ("karung_tumpuk", (56.6, -2.6), 15),
]

# Where villagers who lost their land end up (tents)
TENT_SPOTS = [(12, 16), (16, 17), (20, 15.5), (9, 19), (24, 18), (14, 20),
              (5, 44), (9, 46), (13, 44), (17, 46), (21, 44), (25, 46)]

# Big rocks / cliffs along the coast (model, pos, rot); terrain.py slides each one in
# from the given point until it sits just inside the shore
CLIFFS = [("cliff_a", (-60, -170), 10), ("cliff_a", (-35, -175), -8), ("cliff_a", (40, -175), 170),
          ("cliff_a", (-170, -80), 60), ("cliff_a", (200, -60), 200), ("cliff_a", (-200, 60), 100),
          ("rock_c", (-80, -170), 0), ("rock_c", (60, -170), 40), ("rock_c", (8, -175), 0),
          ("rock_c", (200, 20), 0), ("rock_c", (-60, 190), 30), ("rock_c", (150, 150), 0)]

# in front of (south of) the kantor: the first frame shows its door and sign instead of
# its roof covering the bottom of the screen
PLAYER_SPAWN = (-3.5, 37.5)

# ------------------------------------------------------------------ hamlets (map v3)
# Each hamlet lines houses up along its streets (segments of ROADS). The generator below
# picks a house type and colours per house, keeps clear of roads, rivers, parcels and
# other buildings, and adds fences and yard plants. Named villagers get the house of
# their hamlet closest to their garden ("home" ids rumah_<vid>).
VILLAGES = [
    {"id": "sukamakmur", "name": "Desa Sukamakmur", "center": (0, 4),
     "streets": [[(-62, 8), (-30, 9), (0, 8), (30, 7), (62, 8)], [(-48, -26), (44, -26)], [(-4, -26), (-4, 8)]],
     "n": 9, "villagers": []},
    {"id": "seberang", "name": "Dusun Seberang", "center": (128, -28),
     "streets": [[(102, -28), (160, -28)], [(128, -28), (128, -62)], [(104, -60), (104, -4)]], "n": 16,
     "villagers": ["somad", "ucok", "rian"]},
    {"id": "muara", "name": "Dusun Muara", "center": (126, 62),
     "streets": [[(108, 62), (152, 62)], [(126, 62), (126, 94)], [(62, 62), (92, 62)], [(45, 40), (62, 62)]], "n": 14,
     "villagers": ["wati", "slamet"]},
    {"id": "barat", "name": "Dusun Barat", "center": (-132, 8),
     "streets": [[(-160, 8), (-112, 8)], [(-132, 8), (-132, 42)], [(-92, 8), (-64, 8)], [(-112, 8), (-112, -24)]],
     "n": 16, "villagers": ["dullah", "romlah"]},
    {"id": "bukit", "name": "Dusun Bukit", "center": (-128, -45),
     "streets": [[(-152, -45), (-110, -45)], [(-128, -45), (-128, -72)], [(-90, -45), (-75, -45)],
                 [(-75, -45), (-48, -26)]], "n": 14,
     "villagers": ["darsih"]},
    {"id": "utara", "name": "Dusun Utara", "center": (34, -85),
     "streets": [[(-30, -85), (90, -85)], [(34, -40), (34, -85)], [(106, -85), (122, -85)]], "n": 14,
     "villagers": ["yanto", "karta"]},
    {"id": "selatan", "name": "Dusun Selatan", "center": (30, 88),
     "streets": [[(-38, 88), (62, 88)], [(30, 58), (30, 88)], [(45, 40), (30, 58)]], "n": 16,
     "villagers": ["bidan", "rt", "lastri"]},
]

# house footprints (half extents x, z; local, front = +z) incl. porch/steps - the
# generator's spacing and terrain.py's keep-out; measured from the GLBs
HOUSE_HALF = {"rumah_a": (2.9, 2.5), "rumah_b": (2.5, 2.7), "rumah_c": (2.9, 2.2), "rumah_d": (2.7, 2.6),
              "rumah_e": (2.4, 2.8), "rumah_f": (2.6, 2.7), "rumah_g": (3.4, 1.8)}
HOUSE_TYPES = ["rumah_a", "rumah_b", "rumah_c", "rumah_d", "rumah_e", "rumah_f", "rumah_g"]
WALL_COLOURS = ["#f4e3bf", "#e9d3a4", "#a86d3e", "#d6a867", "#b98a58", "#9fd0c0", "#f2b8a2", "#b9d7ea",
                "#f3e08a", "#c9e3a6", "#f6f1e7", "#e7c7df", "#8fb6a0", "#f0c987", "#d9b48f", "#bfa3d6"]
ROOF_COLOURS = ["#c2714a", "#9c4c2b", "#b8543a", "#6f8ea6", "#4e9a5a", "#8c8f86", "#3f6f9a", "#a33b2b",
                "#7a5a44", "#2f7d73", "#c98a3a", "#5c6d7a"]
HOUSE_PLANTS = ["banana", "bush_a", "bush_b", "keladi", "banana", "coconut", "bush_a", "flowers"]


def _seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    vx, vz = bx - ax, bz - az
    wx, wz = px - ax, pz - az
    L2 = vx * vx + vz * vz
    t = max(0.0, min(1.0, (wx * vx + wz * vz) / L2)) if L2 > 0 else 0.0
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def _poly_dist(px, pz, pts):
    return min(_seg_dist(px, pz, a, b) for a, b in zip(pts[:-1], pts[1:]))


def road_dist(x, z):
    return min(_poly_dist(x, z, r) for r in ROADS)


def water_dist(x, z):
    """Distance to open water inside the island: rivers (minus half width), lagoons, ponds."""
    d = 1e9
    for rv in RIVERS:
        d = min(d, _poly_dist(x, z, rv["pts"]) - rv["hw"])
    for (cx, cz, r) in LAGOONS + PONDS:
        d = min(d, math.hypot(x - cx, z - cz) - r)
    return d


def _parcel_rect(p, pad):
    cx, cz = p["center"]
    hx, hz = PARCEL_HALF
    return (cx - hx - pad, cz - hz - pad, cx + hx + pad, cz + hz + pad)


def _rect_circle(rect, x, z, r):
    x0, z0, x1, z1 = rect
    qx = max(x0 - x, 0, x - x1)
    qz = max(z0 - z, 0, z - z1)
    return qx * qx + qz * qz < r * r


def generate_houses():
    """Houses of every hamlet: [{"id", "model", "pos", "rot", "wall", "roof", "village"}],
    their fences [(model, (x, z), rot)] and yard plants [(model, (x, z), rot, scale)]."""
    rng = random.Random(2024)
    houses, fences, plants = [], [], []
    taken = [(b["pos"][0], b["pos"][1], 8.5) for b in BUILDINGS]
    taken += [(p[1][0], p[1][1], 3.0 if p[0] != "truck" else 5.0) for p in PROPS]
    taken += [(x, z, 4.0) for (x, z) in TENT_SPOTS]
    taken.append((PLAYER_SPAWN[0], PLAYER_SPAWN[1], 6.0))
    for b in BRIDGES:
        taken.append((b["pos"][0], b["pos"][1], BRIDGE_LEN * 0.5 + 4.0))
    rects = [_parcel_rect(p, 3.0) for p in PARCELS]
    for v in VILLAGES:
        cand = []
        for st in v["streets"]:
            for a, b in zip(st[:-1], st[1:]):
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                nx, nz = -uz, ux
                k = 6.0
                while k < L - 4.0:
                    for side in (-1, 1):
                        cand.append((a[0] + ux * k, a[1] + uz * k, nx * side, nz * side))
                    k += rng.uniform(11.5, 14.5)
        rng.shuffle(cand)
        # the hamlet centre first: houses cluster round the crossing
        cx0, cz0 = v["center"]
        cand.sort(key=lambda c: math.hypot(c[0] - cx0, c[1] - cz0) + rng.uniform(0, 14))
        placed = 0
        for (sx, sz, nx, nz) in cand:
            if placed >= v["n"]:
                break
            model = HOUSE_TYPES[rng.randrange(len(HOUSE_TYPES))]
            hx, hz = HOUSE_HALF[model]
            setback = ROAD_WIDTH * 0.5 + 2.6 + hz
            x, z = sx + nx * setback, sz + nz * setback
            # face the street: the local +z (front) points back along -n
            rot = math.degrees(math.atan2(-nx, -nz))
            rot = round(rot / 90.0) * 90.0 if abs(nx) < 0.2 or abs(nz) < 0.2 else rot
            r_foot = math.hypot(hx, hz) + 0.8
            if island_rho(x, z) > 0.86:
                continue
            if water_dist(x, z) < r_foot + 4.0:
                continue
            if road_dist(x, z) < r_foot + 0.2 - 0.9:
                continue
            if any(_rect_circle(rc, x, z, r_foot) for rc in rects):
                continue
            if any(math.hypot(x - tx, z - tz) < r_foot + tr for tx, tz, tr in taken):
                continue
            hid = "rumah_%s_%d" % (v["id"], placed)
            houses.append({"id": hid, "model": model, "pos": (round(x, 2), round(z, 2)), "rot": round(rot, 1),
                           "wall": WALL_COLOURS[rng.randrange(len(WALL_COLOURS))],
                           "roof": ROOF_COLOURS[rng.randrange(len(ROOF_COLOURS))], "village": v["id"]})
            taken.append((x, z, r_foot + 1.2))
            placed += 1
            th = math.radians(rot)
            fx, fz = math.sin(th), math.cos(th)        # front direction
            rx, rz = math.cos(th), -math.sin(th)       # local +x
            # a bamboo / rail fence along the front of the yard with a gate at the door
            if rng.random() < 0.6:
                fm = "pagar_bambu" if rng.random() < 0.65 else "pagar"
                d = hz + 1.9
                for s in (-1, 1):
                    for k in range(2):
                        off = s * (2.1 + k * 2.0)
                        px_ = x + fx * d + rx * off
                        pz_ = z + fz * d + rz * off
                        if road_dist(px_, pz_) > ROAD_WIDTH * 0.5 + 0.6:
                            fences.append((fm, (round(px_, 2), round(pz_, 2)), round(rot, 1)))
                # a side run from the front corner back along the yard
                if rng.random() < 0.5:
                    s = rng.choice((-1, 1))
                    for k in range(2):
                        px_ = x + fx * (d - 1.0 - k * 2.0) + rx * s * (hx + 2.0)
                        pz_ = z + fz * (d - 1.0 - k * 2.0) + rz * s * (hx + 2.0)
                        fences.append((fm, (round(px_, 2), round(pz_, 2)), round(rot + 90.0, 1)))
            # yard plants: beside and behind the house (tall ones never on its camera side)
            for k in range(rng.randint(2, 4)):
                m = HOUSE_PLANTS[rng.randrange(len(HOUSE_PLANTS))]
                side = rng.choice((-1, 1))
                along = rng.uniform(-hz, hz * 0.4)
                px_ = x + rx * side * (hx + rng.uniform(1.0, 2.2)) + fx * along
                pz_ = z + rz * side * (hx + rng.uniform(1.0, 2.2)) + fz * along
                if m in ("banana", "coconut") and pz_ > z + 1.0:
                    m = "bush_b"
                if road_dist(px_, pz_) < ROAD_WIDTH * 0.5 + 1.2 or water_dist(px_, pz_) < 1.5:
                    continue
                plants.append((m, (round(px_, 2), round(pz_, 2)), round(rng.uniform(0, 360), 1),
                               round(rng.uniform(0.85, 1.15), 2)))
    # named villagers: the house of their hamlet nearest their garden
    homes = {}
    for v in VILLAGES:
        own = [h for h in houses if h["village"] == v["id"]]
        for vid in v["villagers"]:
            pc = next(p["center"] for p in PARCELS if p["owner"] == vid)
            best = min((h for h in own if h["id"].startswith("rumah_" + v["id"])),
                       key=lambda h: math.hypot(h["pos"][0] - pc[0], h["pos"][1] - pc[1]))
            homes[vid] = best["id"]
            best["id"] = "rumah_" + vid
    return houses, fences, plants, homes


HOUSES, FENCES, HOUSE_PLANT_DECOR, VILLAGER_HOMES = generate_houses()

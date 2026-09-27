"""World layout for Sawit The Franchise.

All coordinates are GODOT world coordinates in metres: x = east, z = south,
y = up. (Blender scripts convert with blender_y = -z.)  Buildings face +z
(south, towards the camera) unless `rot` says otherwise (degrees around y).

terrain.py reads this, paints the ground masks, scatters decoration and
writes game/data/layout.json for the Godot world builder.
"""

WORLD_SIZE = 200.0          # terrain square side (m), centred on the origin
WATER_LEVEL = -0.30

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
    [(-20, -26), (-20, -36)],
    [(18, -26), (18, -36)],
]
ROAD_WIDTH = 3.0

# Palm parcels: 4 columns (x) by 3 rows (z) of tiles, 3.2 m apart.
TILE = 3.2
PARCEL_COLS = 4
PARCEL_ROWS = 3
PARCELS = [
    {"id": 0, "name": "Lahan Kantor", "owner": "player", "center": (-17, 27)},
    {"id": 1, "name": "Kebun Kakek Darman", "owner": "kakek", "center": (-44, 31)},
    {"id": 2, "name": "Kebun Bu Sari", "owner": "ibu", "center": (-27, -12)},
    {"id": 3, "name": "Kebun Pak Kades", "owner": "kades", "center": (14, -12)},
    {"id": 4, "name": "Kebun Nenek Ijah", "owner": "nenek", "center": (-20, -44)},
    {"id": 5, "name": "Kebun Mas Joko", "owner": "pemuda", "center": (18, -44)},
    {"id": 6, "name": "Kebun Pak Tarno", "owner": "petani", "center": (22, 30)},
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
]

# Small set pieces (model, pos, rot)
PROPS = [
    ("sumur", (-4, 13), 0), ("bangku", (12, 11.5), 0), ("bangku", (-10, 11.5), 0),
    ("lampu", (-6.5, 11), 0), ("lampu", (18, 11), 0), ("lampu", (-40, 11), 0), ("lampu", (40, 11), 0),
    ("lampu", (-4, 26), 0), ("lampu", (60, 12), 0),
    ("karung_pupuk", (-18.5, 3.2), 20), ("karung_pupuk", (-17.6, 3.6), -10), ("crate", (-9.5, 3.4), 10),
    ("gerobak", (3, 34), 30), ("tumpukan_tbs", (45, 0.5), 0), ("tumpukan_tbs", (48.5, 0.2), 40),
    ("truck", (57, 1), -20), ("crate", (60, 21), 0), ("crate", (60.8, 20.2), 25), ("meja", (5, 5), 0),
    ("perahu", (81, 17.5), 80), ("perahu", (76, -12), 20), ("jerigen", (11.5, 4.6), 0), ("jerigen", (12.1, 4.9), 30),
    ("pagar", (-27, 21.5), 0), ("pagar", (-25, 21.5), 0), ("pagar", (-9, 21.5), 0), ("pagar", (-7, 21.5), 0),
]

# Where villagers who lost their land end up (tents)
TENT_SPOTS = [(12, 16), (16, 17), (20, 15.5), (9, 19), (24, 18), (14, 20)]

# Big rocks / cliffs along the north coast (model, pos, rot)
CLIFFS = [("cliff_a", (-44, -55), 10), ("cliff_a", (-30, -58), -8), ("cliff_a", (40, -56), 170),
          ("rock_c", (-56, -48), 0), ("rock_c", (54, -49), 40), ("rock_c", (8, -60), 0)]

PLAYER_SPAWN = (-3, 26)

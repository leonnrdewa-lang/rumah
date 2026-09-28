"""Rumah kampung: single-storey Jakarta houses. Every variant except the loteng-room house stays <= 4.8 m, so they
also work as 'low' (the loteng room needs 2.2 m headroom on top of the dak, so that one is front/fill only).

Sub-styles, so a street of them is never monotonous:
  limasan   classic teras on columns under a hip (limasan) genteng roof, besi pagar on a low wall
  pelana    gable (pelana) roof with the gable end facing the street, tembok pagar + sliding steel gate
  teras     gable-end house whose gable roof also covers a column terrace, besi pagar
  carport   small house plus a carport (thin shed roof on posts) with parked motorbikes
  jemuran   house pushed to one side (gable or hip roof), side yard with clotheslines, pots and a tree
  loteng    flat concrete dak. mode 'room': a real loteng room on the back half of the dak (front/fill only);
            mode 'dak': open roof terrace for drying clothes with toren, AC condensers, dish and pots (<= 4.8 m)
  siku      L-shaped house: cross-gable roof, front wing with its gable to the street, terrace in the corner
  petak     narrow rumah petak with a single-slope spandek roof and a motorbike at the door
            (units=2: petak kontrakan, two small units side by side under one roof)
  emper     old-style house: hip roof plus a lower full-width emper (lean-to) on wooden posts, wooden langkan
  gerbang   hip-roof house with a small gable porch, garden with a tree, sliding gate
  besar     wide house: L-shaped hip roof, carport, garden, tembok+besi pagar
The back is always lived-in and varies per variant (v['bk']): dapur annex with a ribbed lean-to and back door,
bedroom window (+ AC only where it clears the window), toren on a stand or on the annex roof, jemuran of varying
length and height, pohon pisang, sumur pompa, a parked motorbike or pots.
Front-wing roofs (siku, besar) share the main roof's pitch and end exactly on the valley lines (nothing hidden
runs on under the main roof), with dark valley strips so the L reads clearly. Hip roofs get dark bubungan strips
along the hips so the four slopes still read at game distance.

Coordinates as in common.py: x in [-W/2, W/2], y in [0, D] with y = 0 the street side, z up.
Pitched-roof helpers here take z0 = top of the wall: the roof slab rests on the wall line and the eaves hang
below it, so gable triangles close exactly against the slab (no see-through slivers).
"""
import math

from common import PALETTE

TYPE = 'rumah'
ROLES = ['front', 'low', 'fill']

HMAX = 4.76          # every 'low' variant must stay <= 4.8 m
OV = 0.45            # roof overhang
TH = 0.14            # roof slab thickness (genteng + battens)
CAP = 0.07           # ridge cap (bubungan) height above the roof top
SKIP_WALL = {'front': 'back', 'back': 'front', 'left': 'right', 'right': 'left'}
GRASS = '#72a64a'
SOIL = '#a89576'
STONE = '#9c9890'
FABRICS = ['fabric_1', 'fabric_2', 'fabric_3', '#f4f1ea', '#e8873a', '#7a5bc2', '#3fae8c', '#d8433a', '#2f4f8f', '#f28fb0']
MOTORS = ['#c8312b', '#2f5fae', '#eeeeea', '#e06b1f', '#9aa3ad', '#2f8f6a']


# ------------------------------------------------------------------------------------------ colours
def hexof(c):
    return PALETTE.get(c, c)


def shade(c, f):
    """Darker (f < 1) or lighter (f > 1) version of a palette key / hex colour."""
    h = hexof(c).lstrip('#')
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    if f <= 1:
        rgb = [int(x * f) for x in rgb]
    else:
        rgb = [int(x + (255 - x) * (f - 1)) for x in rgb]
    return '#%02x%02x%02x' % tuple(max(0, min(255, x)) for x in rgb)


# The game lights (warm hemisphere 0.78 + warm sun 0.95, toon bands, no tone mapping) multiply a colour by about
# (1.48, 1.22, 0.93) on a sunlit front wall and (1.70, 1.43, 1.11) on a sunlit roof slope, so light pastels clip to
# the same cream/yellow. Wall and roof colours in variants() are therefore written as the colour the player should
# SEE on the sunlit face, and lit() turns that into the material colour (shaded faces keep the same hue, darker).
GAIN_WALL = (1.477, 1.224, 0.931)
GAIN_ROOF = (1.695, 1.429, 1.109)
WALL_KEYS = ('wall', 'accent', 'fwall', 'lwall', 'annex_wall', 'parapet', 'pillar', 'pgable', 'col')
ROOF_KEYS = ('roof', 'proof', 'eroof', 'troof', 'lroof', 'croof', 'annex_roof', 'kanopi', 'dak', 'coat')


def lit(c, gain=GAIN_WALL):
    h = hexof(c).lstrip('#')
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(x / g)))) for x, g in zip(rgb, gain))


# ------------------------------------------------------------------------------------------ polygons
def _ccw(pts):
    s = 0.0
    for i in range(len(pts)):
        a, c = pts[i], pts[(i + 1) % len(pts)]
        s += a[0] * c[1] - c[0] * a[1]
    return s > 0


def up(pts):
    """Polygon ordered counter-clockwise seen from above (normal points up)."""
    return pts if _ccw(pts) else pts[::-1]


def down(pts):
    """Polygon ordered clockwise seen from above (normal points down): soffits, undersides."""
    return pts[::-1] if _ccw(pts) else pts


def _nz(pts):
    """z component of a polygon's (Newell) normal."""
    s = 0.0
    for i in range(len(pts)):
        a, c = pts[i], pts[(i + 1) % len(pts)]
        s += (a[0] - c[0]) * (a[1] + c[1])
    return s


# ------------------------------------------------------------------------------------------ small helpers
def fbox(b, side, u0, u1, z0, z1, color, off=0.05, depth=0.05, wall=None):
    """Slab proud of a facade (like Bld.panel) without the hidden faces against the wall and underneath."""
    m, _ = b._frame(side, wall)
    (xa, ya), (xb, yb) = m(u0, off - depth), m(u1, off)
    b.box(xa, ya, z0, xb, yb, z1, color, skip=('bottom', SKIP_WALL[side]))


def post(b, x, y, z0, z1, color, r=0.05):
    """Square post / column (no top or bottom faces)."""
    b.box(x - r, y - r, z0, x + r, y + r, z1, color, skip=('bottom', 'top'))


def window(b, side, uc, z0, w, h, frame, wall=None, bars=2, glass='glass', sill=True, boven=0.0, teralis=None):
    """Cheap framed window: frame slab + glass quad (+ transom 'boven' vent, mullions, teralis bars, sill)."""
    t = 0.07
    ztop = z0 + h + (boven + t if boven else 0.0)
    fbox(b, side, uc - w / 2 - t, uc + w / 2 + t, z0 - t, ztop + t, frame, off=0.05, depth=0.06, wall=wall)
    b.decal(side, uc - w / 2, uc + w / 2, z0, z0 + h, glass, off=0.06, wall=wall)
    if boven:
        b.decal(side, uc - w / 2, uc + w / 2, z0 + h + t, ztop, 'glass_dark', off=0.06, wall=wall)
    for i in range(1, bars):
        u = uc - w / 2 + w * i / bars
        b.decal(side, u - 0.03, u + 0.03, z0, z0 + h, frame, off=0.07, wall=wall)
    if teralis:
        n = max(3, int(round(w / 0.17)))
        for i in range(1, n):
            u = uc - w / 2 + w * i / n
            b.decal(side, u - 0.013, u + 0.013, z0, z0 + h, teralis, off=0.08, wall=wall)
        b.decal(side, uc - w / 2, uc + w / 2, z0 + h * 0.5 - 0.015, z0 + h * 0.5 + 0.015, teralis, off=0.09, wall=wall)
    if sill:
        fbox(b, side, uc - w / 2 - 0.12, uc + w / 2 + 0.12, z0 - t - 0.06, z0 - t, frame, off=0.12, depth=0.12, wall=wall)


def door(b, side, uc, w, h, color, frame, wall=None, z0=0.0, leaves=1, boven=0.3):
    """Panelled wooden door with frame and a glass transom."""
    t = 0.07
    top = z0 + h + (boven + t if boven else 0.0)
    fbox(b, side, uc - w / 2 - t, uc + w / 2 + t, z0, top + t, frame, off=0.05, depth=0.06, wall=wall)
    b.decal(side, uc - w / 2, uc + w / 2, z0, z0 + h, color, off=0.06, wall=wall)
    if boven:
        b.decal(side, uc - w / 2, uc + w / 2, z0 + h + t, top, 'glass_dark', off=0.06, wall=wall)
    lw = w / leaves
    pc = shade(color, 0.78)
    for k in range(leaves):
        a = uc - w / 2 + k * lw
        b.decal(side, a + 0.09, a + lw - 0.09, z0 + h * 0.56, z0 + h - 0.12, pc, off=0.07, wall=wall)
        b.decal(side, a + 0.09, a + lw - 0.09, z0 + 0.14, z0 + h * 0.46, pc, off=0.07, wall=wall)
    if leaves == 2:
        b.decal(side, uc - 0.02, uc + 0.02, z0, z0 + h, frame, off=0.075, wall=wall)


def facade(b, side, u0, u1, z0, v, rng, wall=None, door_at=None, door_w=0.95, leaves=1, win_h=1.3, win_z=0.95,
           teralis=None, boven=0.3, maxwin=1.5):
    """Door + windows spread over a wall segment u0..u1. Returns the door centre."""
    du = u0 + (u1 - u0) * (door_at if door_at is not None else (0.3 if rng.random() < 0.5 else 0.7))
    door(b, side, du, door_w, 2.1, v.get('door', 'door_wood'), v['frame'], wall=wall, z0=z0, leaves=leaves, boven=boven)
    for a, c in ((u0 + 0.3, du - door_w / 2 - 0.35), (du + door_w / 2 + 0.35, u1 - 0.3)):
        L = c - a
        if L < 0.8:
            continue
        n = 1 if L < 3.2 else 2
        for k in range(n):
            uc = a + L * (k + 0.5) / n
            w = min(maxwin, L / n - 0.3)
            window(b, side, uc, z0 + win_z, w, win_h, v['frame'], wall=wall, bars=2 if w > 0.85 else 1,
                   teralis=teralis, boven=boven * 0.8 if boven else 0.0)
    return du


def xcyl(b, cx, cy, cz, r, xa, xb, color, seg=8):
    """Cylinder lying along x (wheels)."""
    ring = [(cy + r * math.cos(2 * math.pi * i / seg), cz + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, c = ring[i], ring[(i + 1) % seg]
        b.face([(xa, a[0], a[1]), (xa, c[0], c[1]), (xb, c[0], c[1]), (xb, a[0], a[1])], color)
    b.face([(xb, p[0], p[1]) for p in ring], color)
    b.face([(xa, p[0], p[1]) for p in ring[::-1]], color)


def bush(b, x, y, z0, r, h, color='plant', seg=5):
    """Rounded leafy blob (3 rings + cap)."""
    rings = [(0.72 * r, z0), (r, z0 + 0.5 * h), (0.5 * r, z0 + h)]
    pts = [[(x + rr * math.cos(2 * math.pi * (i + 0.5 * k) / seg), y + rr * math.sin(2 * math.pi * (i + 0.5 * k) / seg), z)
            for i in range(seg)] for k, (rr, z) in enumerate(rings)]
    # rings are rotated by half a segment each so the blob reads rounder; quads become two triangles
    for k in range(2):
        lo, hi = pts[k], pts[k + 1]
        for i in range(seg):
            j = (i + 1) % seg
            b.face([lo[i], lo[j], hi[i]], color)
            b.face([lo[j], hi[j], hi[i]], color)
    b.face(pts[2], shade(color, 1.08))


def pot(b, x, y, z0=0.0, s=1.0, plant='plant', potc='pot'):
    b.cyl(x, y, z0, z0 + 0.3 * s, 0.17 * s, potc, seg=6, top=False)
    bush(b, x, y, z0 + 0.26 * s, 0.3 * s, 0.55 * s, plant)


def tree(b, x, y, h=3.4, r=1.1, color='plant', seg=7):
    """Small yard tree (jambu / mangga): trunk + a rounded faceted crown."""
    b.box(x - 0.1, y - 0.1, 0, x + 0.1, y + 0.1, h * 0.52, 'frame_brown', skip=('bottom', 'top'))
    z0, hh = h * 0.42, h * 0.58
    rings = [(0.5 * r, z0), (0.98 * r, z0 + 0.34 * hh), (0.86 * r, z0 + 0.72 * hh), (0.38 * r, z0 + hh)]
    pts = [[(x + rr * math.cos(2 * math.pi * (i + 0.5 * k) / seg), y + rr * math.sin(2 * math.pi * (i + 0.5 * k) / seg), z)
            for i in range(seg)] for k, (rr, z) in enumerate(rings)]
    for k in range(3):
        lo, hi = pts[k], pts[k + 1]
        col = shade(color, 0.9) if k == 0 else color
        for i in range(seg):
            j = (i + 1) % seg
            b.face([lo[i], lo[j], hi[i]], col)
            b.face([lo[j], hi[j], hi[i]], col)
    b.face(pts[3], shade(color, 1.1))


def pisang(b, x, y, h=2.7, r=1.1, color='#5ea64a', dry='#a8914a', nl=6, phase=0.07):
    """Pohon pisang (banana plant): thick pseudo-stem, a crown of nl long arching, drooping leaves (each two quads:
    rising stalk half, drooping blade half, two-sided so it reads from above and from the street) and one dry
    leaf hanging down along the stem."""
    zt = h - 0.75
    b.cyl(x, y, 0.0, zt + 0.12, 0.15, '#8d8a52', seg=6, top=True)
    for k in range(nl):
        a = 2 * math.pi * (k / float(nl) + phase)
        ca, sa = math.cos(a), math.sin(a)
        n = (-sa, ca)
        rr = r * (0.85 + 0.15 * ((k * 5) % 3) / 2.0)
        z0 = zt + 0.1 + 0.12 * (k % 2)
        spine = [(x + ca * 0.08, y + sa * 0.08, z0), (x + ca * 0.45 * rr, y + sa * 0.45 * rr, h - 0.05 * (k % 3)),
                 (x + ca * rr, y + sa * rr, h - 0.6)]
        wid = [0.04, 0.24, 0.1]
        _leaf(b, spine, wid, n, color)
    # dry leaf hanging down the stem
    a = 2 * math.pi * (phase + 0.5 / nl)
    ca, sa = math.cos(a), math.sin(a)
    spine = [(x + ca * 0.16, y + sa * 0.16, zt + 0.05), (x + ca * 0.3, y + sa * 0.3, zt - 0.35), (x + ca * 0.24, y + sa * 0.24, zt - 1.0)]
    _leaf(b, spine, [0.05, 0.16, 0.07], (-sa, ca), dry)


def _leaf(b, spine, wid, n, col):
    for i in range(2):
        s0, s1, w0, w1 = spine[i], spine[i + 1], wid[i], wid[i + 1]
        q = [(s0[0] + n[0] * w0, s0[1] + n[1] * w0, s0[2]), (s0[0] - n[0] * w0, s0[1] - n[1] * w0, s0[2]),
             (s1[0] - n[0] * w1, s1[1] - n[1] * w1, s1[2]), (s1[0] + n[0] * w1, s1[1] + n[1] * w1, s1[2])]
        if _nz(q) < 0:
            q = q[::-1]
        b.face(q, col)
        b.face([(p[0], p[1], p[2] - 0.012) for p in q[::-1]], shade(col, 0.85))


def jerigen(b, x, y, z0=0.0, color='#e8c02a'):
    """Plastic jerry can with a cap."""
    b.box(x - 0.15, y - 0.1, z0, x + 0.15, y + 0.1, z0 + 0.42, color)
    b.box(x + 0.04, y - 0.03, z0 + 0.42, x + 0.1, y + 0.03, z0 + 0.48, shade(color, 0.7))


def gate_slide(b, a, c, color, h=1.3, y0=0.0, step=0.22, style='v'):
    """Cheap closed sliding gate (pagar geser) across a driveway: frame rails + two-sided vertical bars ('v'),
    or a sheet panel with ribs ('panel')."""
    if style == 'panel':
        gate_panel(b, a, c, color, h=h, y0=y0)
        return
    for z in (0.05, h * 0.5, h - 0.06):
        b.box(a, y0 + 0.08, z, c, y0 + 0.14, z + 0.06, color, skip=('bottom', 'left', 'right'))
    k = max(2, int((c - a) / step))
    for i in range(k + 1):
        u = a + 0.03 + (c - a - 0.06) * i / k
        b.box(u - 0.018, y0 + 0.095, 0.05, u + 0.018, y0 + 0.125, h, color, skip=('bottom', 'top', 'left', 'right'))
    post(b, a + 0.3, y0 + 0.11, 0.0, 0.05, 'frame_black', r=0.05)       # wheels
    post(b, c - 0.3, y0 + 0.11, 0.0, 0.05, 'frame_black', r=0.05)


def hedge(b, a, c, y, colors=('plant', 'plant_dark'), r=0.4, h=0.8, z0=0.0):
    """Hedge: a row of overlapping leafy blobs."""
    n = max(1, int(round((c - a) / (1.5 * r))))
    for i in range(n):
        x = a + (c - a) * (i + 0.5) / n
        bush(b, x, y, z0, r, h * (0.9 + 0.1 * (i % 2)), colors[i % len(colors)])


def sumur(b, x, y):
    """Sumur pompa: concrete apron, well ring with lid, green hand pump with spout and handle, a bucket."""
    b.box(x - 0.5, y - 0.5, 0, x + 0.5, y + 0.5, 0.08, 'concrete_dark')
    b.cyl(x, y, 0.08, 0.55, 0.3, 'concrete', seg=7)
    post(b, x, y + 0.06, 0.55, 1.25, 'rail_green', r=0.05)
    b.box(x - 0.03, y - 0.24, 0.93, x + 0.03, y + 0.01, 1.0, 'rail_green')                 # spout
    b.box(x - 0.02, y + 0.11, 1.2, x + 0.02, y + 0.62, 1.25, 'rail_green')                 # handle
    b.cyl(x + 0.33, y - 0.32, 0.08, 0.36, 0.13, '#3d7fc4', seg=6)                           # ember


def ac_floor(b, x, y, z0, along='x'):
    """AC condenser standing on a roof slab on two little rails. along='x': long side along x, fan facing -y;
    along='y': long side along y, fan facing -x / +x depending on x (towards the middle of the building)."""
    if along == 'x':
        b.box(x - 0.34, y - 0.16, z0, x + 0.34, y + 0.16, z0 + 0.08, 'metal', skip=('bottom', 'top'))
        b.box(x - 0.4, y - 0.15, z0 + 0.08, x + 0.4, y + 0.15, z0 + 0.63, 'ac_white')
        b.decal('front', x - 0.3, x + 0.06, z0 + 0.17, z0 + 0.54, 'metal', off=0.01, wall=y - 0.15)
    else:
        b.box(x - 0.16, y - 0.34, z0, x + 0.16, y + 0.34, z0 + 0.08, 'metal', skip=('bottom', 'top'))
        b.box(x - 0.15, y - 0.4, z0 + 0.08, x + 0.15, y + 0.4, z0 + 0.63, 'ac_white')
        side, wx = ('right', x + 0.15) if x < 0 else ('left', x - 0.15)
        b.decal(side, y - 0.3, y + 0.06, z0 + 0.17, z0 + 0.54, 'metal', off=0.01, wall=wx)


def toren(b, cx, cy, z0, stand, color, r=0.5, h=1.05):
    """Water tank (toren) on a steel stand."""
    if stand > 0:
        for dx in (-0.38, 0.38):
            for dy in (-0.38, 0.38):
                post(b, cx + dx, cy + dy, z0, z0 + stand, 'metal', r=0.035)
        b.box(cx - 0.52, cy - 0.52, z0 + stand - 0.07, cx + 0.52, cy + 0.52, z0 + stand, 'metal')
        z0 += stand
    b.cyl(cx, cy, z0, z0 + h, r, color, seg=9)
    b.cyl(cx, cy, z0 + h, z0 + h + 0.07, r * 0.36, shade(color, 0.85), seg=5)


def jemuran(b, a, c, fixed, axis, rng, z0=0.0, zl=1.75, posts=True, fill=0.85):
    """Clothesline from a to c along `axis` ('x' or 'y') with colourful clothes hanging from it."""
    if posts:
        for u in (a, c):
            x, y = (u, fixed) if axis == 'x' else (fixed, u)
            post(b, x, y, z0, z0 + zl + 0.08, 'frame_brown', r=0.03)
    if axis == 'x':
        b.box(a, fixed - 0.016, z0 + zl, c, fixed + 0.016, z0 + zl + 0.028, 'rail_black', skip=('bottom', 'left', 'right'))
    else:
        b.box(fixed - 0.016, a, z0 + zl, fixed + 0.016, c, z0 + zl + 0.028, 'rail_black', skip=('bottom', 'front', 'back'))
    u = a + 0.12
    end = a + (c - a) * fill
    while u < end - 0.25:
        kind = rng.random()
        w, h = (0.55, 0.62) if kind < 0.4 else ((0.34, 0.85) if kind < 0.7 else (0.7, 0.5))
        w = min(w, end - u)
        col = FABRICS[rng.randrange(len(FABRICS))]
        zt = z0 + zl + 0.01
        if axis == 'x':
            b.box(u, fixed - 0.008, zt - h, u + w, fixed + 0.008, zt, col, skip=('bottom', 'top', 'left', 'right'))
        else:
            b.box(fixed - 0.008, u, zt - h, fixed + 0.008, u + w, zt, col, skip=('bottom', 'top', 'front', 'back'))
        u += w + 0.07 + rng.random() * 0.12


def motor(b, x, y, color, face=-1, z0=0.0):
    """Parked matic scooter (~1.8 m long), nose to -y (the street) when face=-1, standing on z0."""
    def Y(t):
        return y + face * t
    dark = 'frame_black'
    for t in (0.6, -0.62):
        xcyl(b, x, Y(t), z0 + 0.24, 0.24, x - 0.055, x + 0.055, dark, seg=6)
    b.box(x - 0.12, Y(-0.35), z0 + 0.22, x + 0.12, Y(0.36), z0 + 0.34, 'trim_dark')            # floorboard
    b.box(x - 0.17, Y(-0.9), z0 + 0.34, x + 0.17, Y(-0.08), z0 + 0.7, color)                  # rear body
    b.box(x - 0.15, Y(-0.84), z0 + 0.7, x + 0.15, Y(-0.14), z0 + 0.79, dark)                  # seat
    b.box(x - 0.16, Y(0.28), z0 + 0.26, x + 0.16, Y(0.44), z0 + 0.94, color)                  # leg shield
    b.box(x - 0.08, Y(0.42), z0 + 0.5, x + 0.08, Y(0.8), z0 + 0.57, color)                    # front mudguard
    b.box(x - 0.1, Y(0.36), z0 + 0.94, x + 0.1, Y(0.56), z0 + 1.06, color)                    # headlight cowl
    b.box(x - 0.33, Y(0.42), z0 + 1.0, x + 0.33, Y(0.48), z0 + 1.05, dark)                    # handlebar


def bench(b, x0, x1, y, z0=0.0, color='door_wood'):
    """Wooden terrace bench (bangku) with a backrest against the wall behind it."""
    d = 0.42
    b.box(x0, y, z0, x1, y + d, z0 + 0.45, color)
    b.box(x0, y + d - 0.07, z0 + 0.45, x1, y + d, z0 + 0.9, color)


def _segments(x0, x1, gaps):
    segs, a = [], x0
    for g0, g1 in sorted(gaps):
        if g0 > a:
            segs.append((a, g0))
        a = max(a, g1)
    if x1 > a:
        segs.append((a, x1))
    return segs


def floor_split(b, x0, x1, y0, y1, h, color, holes=(), min_len=0.8):
    """Raised floor slab over [x0,x1] x [y0,y1] left open where a motorbike stands (so its wheels are not sunk
    into the step). Pieces shorter than min_len are dropped. Returns the pieces."""
    segs = [(a, c) for a, c in _segments(x0, x1, holes) if c - a >= min_len]
    for a, c in segs:
        b.box(a, y0, 0, c, y1, h, color)
    return segs


def coating(b, x0, x1, y0, y1, z, rng, color, n=2):
    """Painted waterproof coating (cat anti bocor) on a flat dak, inset from the parapet, plus n darker re-coated
    patches on top of it (each quad lifted a little higher than the one below, so nothing flickers)."""
    b.face([(x0, y0, z + 0.006), (x1, y0, z + 0.006), (x1, y1, z + 0.006), (x0, y1, z + 0.006)], color)
    x0, x1, y0, y1 = x0 + 0.3, x1 - 0.3, y0 + 0.3, y1 - 0.3
    color = shade(color, 0.9)
    for k in range(n):
        w, d = 0.8 + rng.random() * 1.3, 0.6 + rng.random() * 1.0
        cx = x0 + w / 2 + rng.random() * max(0.0, x1 - x0 - w)
        cy = y0 + d / 2 + rng.random() * max(0.0, y1 - y0 - d)
        zz = z + 0.006 + 0.008 * (k + 1)
        b.face([(cx - w / 2, cy - d / 2, zz), (cx + w / 2, cy - d / 2, zz), (cx + w / 2, cy + d / 2, zz), (cx - w / 2, cy + d / 2, zz)],
               color)


# ------------------------------------------------------------------------------------------ fences
def fence_besi(b, x0, x1, gaps=(), bars='rail_black', wallc='wall_white', pillar=None, h=1.2, hl=0.5, y0=0.0, step=0.2,
               style='v', slat=0.17):
    """Low wall + steel bars (pagar besi) along the street edge, with openings `gaps` [(a, c), ...].
    style 'v' = vertical bars, 'h' = horizontal 'minimalis' slats. Short stubs (< 0.3 m, e.g. between a gate and
    the lot edge) still get a pillar, so a gate always has something to hang on."""
    pillar = pillar or wallc
    for a, c in _segments(x0, x1, gaps):
        L = c - a
        if L < 0.3:
            if L > 0.05:
                b.box(a, y0, 0, c, y0 + 0.22, h + 0.1, pillar)
            continue
        b.box(a, y0 + 0.03, 0, c, y0 + 0.19, hl, wallc, skip=('bottom', 'left', 'right'))
        n = max(1, int(round(L / 2.6)))
        pcs = [a + 0.14] + [a + L * k / n for k in range(1, n)] + [c - 0.14]
        for p in pcs:
            b.box(max(a, p - 0.14), y0, 0, min(c, p + 0.14), y0 + 0.22, h + 0.1, pillar)
        for p, q in zip(pcs, pcs[1:]):
            ua, uc = p + 0.14, q - 0.14
            if uc - ua < 0.12:
                continue
            if style == 'h':
                n = max(2, int((h - hl) / slat))
                for i in range(n):
                    z = hl + 0.08 + (h - hl - 0.12) * i / (n - 1)
                    b.box(ua, y0 + 0.085, z - 0.035, uc, y0 + 0.135, z + 0.035, bars, skip=('bottom', 'left', 'right'))
                continue
            b.box(ua, y0 + 0.085, h - 0.05, uc, y0 + 0.135, h, bars, skip=('bottom', 'left', 'right'))
            k = max(1, int((uc - ua) / step))
            for i in range(k):
                u = ua + (uc - ua) * (i + 0.5) / k
                b.box(u - 0.015, y0 + 0.095, hl, u + 0.015, y0 + 0.125, h - 0.05, bars, skip=('bottom', 'top', 'left', 'right'))


def rail(b, x0, x1, y, z0, h, color, step=0.25, style='v'):
    """Balcony / dak railing along x: top rail + two-sided balusters ('v') or posts + horizontal bars ('h')."""
    b.box(x0, y - 0.03, z0 + h - 0.05, x1, y + 0.03, z0 + h, color, skip=('bottom', 'left', 'right'))
    if style == 'h':
        b.box(x0, y - 0.026, z0 + h * 0.5, x1, y + 0.026, z0 + h * 0.5 + 0.04, color, skip=('bottom', 'left', 'right'))
        step = 1.2
    k = max(1, int((x1 - x0) / step))
    for i in range(k + 1):
        u = x0 + 0.02 + (x1 - x0 - 0.04) * i / k
        b.box(u - 0.018, y - 0.02, z0, u + 0.018, y + 0.02, z0 + h - 0.05, color, skip=('bottom', 'top', 'left', 'right'))


def dish(b, x, y, z0, h=0.55, r=0.36, tilt=0.95):
    """Satellite dish (parabola) on a short pole, tilted up towards the street side."""
    n = (0.0, -math.sin(tilt), math.cos(tilt))
    w = (0.0, -n[2], n[1])                               # n x (1, 0, 0)
    cz = z0 + h + 0.25
    post(b, x, y + 0.08, z0, cz - 0.1, 'metal', r=0.03)
    ring = [(x + r * math.cos(t), y + r * math.sin(t) * w[1], cz + r * math.sin(t) * w[2])
            for t in [2 * math.pi * i / 8 for i in range(8)]]
    back = (x - 0.1 * n[0], y - 0.1 * n[1], cz - 0.1 * n[2])
    for i in range(8):
        a, c = ring[i], ring[(i + 1) % 8]
        b.face([c, a, back], 'ac_white')
        b.face([(a[0] - 0.012 * n[0], a[1] - 0.012 * n[1], a[2] - 0.012 * n[2]),
                (c[0] - 0.012 * n[0], c[1] - 0.012 * n[1], c[2] - 0.012 * n[2]),
                (back[0] - 0.012 * n[0], back[1] - 0.012 * n[1], back[2] - 0.012 * n[2])], 'metal')
    lx, ly, lz = x + 0.32 * n[0], y + 0.32 * n[1], cz + 0.32 * n[2]
    b.box(lx - 0.04, ly - 0.05, lz - 0.05, lx + 0.04, ly + 0.05, lz + 0.05, 'frame_black')
    b.box(x - 0.012, ly, cz - 0.28, x + 0.012, ly + 0.02, lz, 'metal', skip=('bottom', 'top'))


def gate_besi(b, a, c, color, h=1.2, y0=0.0, step=0.16):
    """Closed steel gate in a fence opening."""
    for z in (0.06, h * 0.55, h - 0.06):
        b.box(a, y0 + 0.085, z, c, y0 + 0.135, z + 0.06, color, skip=('bottom', 'left', 'right'))
    k = max(2, int((c - a) / step))
    for i in range(k + 1):
        u = a + 0.03 + (c - a - 0.06) * i / k
        b.box(u - 0.015, y0 + 0.095, 0.06, u + 0.015, y0 + 0.125, h, color, skip=('bottom', 'top', 'left', 'right'))


def fence_tembok(b, x0, x1, gaps, wallc, capc, h=1.5, y0=0.0, roster='trim_dark'):
    """Solid plastered fence wall (tembok pagar) with coping, pillars at both ends and a row of roster vents."""
    for a, c in _segments(x0, x1, gaps):
        if c - a < 0.7:
            continue
        ends = ('bottom', 'left', 'right')
        b.box(a, y0 + 0.03, 0, c, y0 + 0.19, h, wallc, skip=ends)
        b.box(a, y0 + 0.01, h, c, y0 + 0.21, h + 0.08, capc, skip=ends)
        b.box(a, y0 + 0.01, 0, c, y0 + 0.2, 0.25, shade(wallc, 0.8), skip=ends + ('top', 'back'))
        for pa, pc in ((a, a + 0.3), (c - 0.3, c)):
            b.box(pa, y0, 0, pc, y0 + 0.24, h + 0.22, capc)
        if roster:
            n = int((c - a - 0.6) / 0.6)
            for i in range(n):
                u = a + 0.3 + (c - a - 0.6) * (i + 0.5) / n
                b.decal('front', u - 0.13, u + 0.13, h - 0.42, h - 0.16, roster, off=0.01, wall=y0 + 0.03)


def gate_panel(b, a, c, color, h=1.45, y0=0.0):
    """Closed sheet-steel sliding gate with vertical ribs."""
    b.box(a, y0 + 0.07, 0.04, c, y0 + 0.15, h, color, skip=('bottom', 'left', 'right'))
    n = max(2, int((c - a) / 0.22))
    for i in range(1, n):
        u = a + (c - a) * i / n
        b.decal('front', u - 0.025, u + 0.025, 0.1, h - 0.08, shade(color, 0.7), off=0.01, wall=y0 + 0.07)


def front_fence(b, v, fa, fc, gap=None, h=1.2, hl=0.5, gate='besi', more=()):
    """Pagar along the street edge with per-variant looks: low-wall colour (v['fwall']), pillars (v['pillar']),
    total and wall heights (v['fh'], v['fhl']), bar style (v['fstyle']) and gate type (v['gate']: 'besi' steel
    bars, 'panel' sheet steel, None = open)."""
    h, hl = v.get('fh', h), v.get('fhl', hl)
    fence_besi(b, fa, fc, ([gap] if gap else []) + list(more), bars=v['fence'], wallc=v.get('fwall', 'wall_white'), pillar=v.get('pillar'),
               h=h, hl=hl, style=v.get('fstyle', 'v'), step=v.get('fstep', 0.2), slat=v.get('fslat', 0.17))
    g = v.get('gate', gate)
    if gap and g == 'besi':
        gate_besi(b, gap[0], gap[1], v['fence'], h=h)
    elif gap and g == 'panel':
        gate_panel(b, gap[0], gap[1], v.get('gatec', '#3f5a48'), h=h + 0.05)


# ------------------------------------------------------------------------------------------ roofs
def slab(b, top, thick, ctop, cedge, edges=None):
    """Roof slab from its top polygon (counter-clockwise from above); edges[i] adds the fascia under edge i->i+1."""
    assert _ccw(top), top
    b.face(top, ctop)
    n = len(top)
    for i in range(n):
        if edges is None or edges[i]:
            a, c = top[i], top[(i + 1) % n]
            b.face([(a[0], a[1], a[2] - thick), (c[0], c[1], c[2] - thick), c, a], cedge)


def _hip_strip(b, q, r, ze, zt, col, trap_fb, trap_side, dd=0.1, lift=0.02):
    """Dark bubungan strip along one hip line, from eave corner q to ridge end r (plan points): one strip on each of
    the two roof planes meeting there. On a front/back plane z depends on y only, so a shift along x stays on the
    plane (on a side plane a shift along y does). On a trapezoid plane (the ridge runs along it) the strip keeps its
    width up to the ridge; on a triangular hip end it tapers into the ridge point."""
    sx = 1 if r[0] > q[0] else -1
    sy = 1 if r[1] > q[1] else -1
    Q, R = (q[0], q[1], ze + lift), (r[0], r[1], zt + lift)
    if trap_fb:
        b.face(up([Q, R, (R[0] + sx * dd, R[1], R[2]), (Q[0] + sx * dd, Q[1], Q[2])]), col)
    else:
        b.face(up([Q, R, (Q[0] + sx * dd, Q[1], Q[2])]), col)
    if trap_side:
        b.face(up([Q, R, (R[0], R[1] + sy * dd, R[2]), (Q[0], Q[1] + sy * dd, Q[2])]), col)
    else:
        b.face(up([Q, R, (Q[0], Q[1] + sy * dd, Q[2])]), col)


def hip(b, x0, x1, y0, y1, z0, rise, color, fascia, over=OV, thick=TH, cap=True, strips=True):
    """Limasan: four-slope roof over the wall rectangle, slab resting on the wall line at z0.
    Dark strips run along the four hips; the ridge gets a raised cap when it is long, flat strips when short
    (a short raised cap on a near-square hip would read like a chimney stub)."""
    iw, idp = x1 - x0, y1 - y0
    p = rise / (min(iw, idp) / 2)                    # pitch
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    w, d = X1 - X0, Y1 - Y0
    ze = z0 - p * over + thick                       # top of slab at the eave
    zt = z0 + rise + thick
    if w >= d:
        r0, r1 = (X0 + d / 2, (Y0 + Y1) / 2), (X1 - d / 2, (Y0 + Y1) / 2)
    else:
        r0, r1 = ((X0 + X1) / 2, Y0 + w / 2), ((X0 + X1) / 2, Y1 - w / 2)
    c = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    if w >= d:
        polys = [[c[0], c[1], r1, r0], [c[1], c[2], r1], [c[2], c[3], r0, r1], [c[3], c[0], r0]]
    else:
        polys = [[c[0], c[1], r0], [c[1], c[2], r1, r0], [c[2], c[3], r1], [c[3], c[0], r0, r1]]
    ridge = {r0, r1}
    for poly in polys:
        pts = [(q[0], q[1], zt if q in ridge else ze) for q in poly]
        if abs(w - d) < 1e-6 and len(pts) == 4:
            pts = pts[:3]
        b.face(pts, color)
        courses(b, pts, shade(color, 0.8), margin=0.1)
    for i in range(4):
        a, e = c[i], c[(i + 1) % 4]
        b.face([(a[0], a[1], ze - thick), (e[0], e[1], ze - thick), (e[0], e[1], ze), (a[0], a[1], ze)], fascia)
    cc = shade(color, 0.8)
    L = abs(w - d)
    if cap and L >= 1.2:
        if w >= d:
            b.box(r0[0], r0[1] - 0.09, zt - 0.06, r1[0], r0[1] + 0.09, zt + CAP, cc, skip=('bottom',))
        else:
            b.box(r0[0] - 0.09, r0[1], zt - 0.06, r0[0] + 0.09, r1[1], zt + CAP, cc, skip=('bottom',))
    elif cap and L > 0.05:
        s, lz = 0.12, zt + 0.02
        for sg in (-1, 1):
            if w >= d:
                b.face(up([(r0[0], r0[1], lz), (r1[0], r1[1], lz), (r1[0], r1[1] + sg * s, lz - p * s),
                           (r0[0], r0[1] + sg * s, lz - p * s)]), cc)
            else:
                b.face(up([(r0[0], r0[1], lz), (r1[0], r1[1], lz), (r1[0] + sg * s, r1[1], lz - p * s),
                           (r0[0] + sg * s, r0[1], lz - p * s)]), cc)
    if strips:
        long_ = L > 0.25
        ends = [(c[0], r0), (c[1], r1 if w >= d else r0), (c[2], r1), (c[3], r0 if w >= d else r1)]
        for q, r in ends:
            _hip_strip(b, q, r, ze, zt, cc, long_ and w >= d, long_ and w < d)
    return p


def gable(b, x0, x1, y0, y1, z0, rise, color, fascia, gable_color, ridge='x', over=OV, over_end=None, thick=TH,
          cap=True, ends=(True, True), end_over=(None, None), soffit=True, ncourses=None):
    """Pelana: two-slope roof over the wall rectangle (slab resting on the wall line at z0).
    ridge='x': slopes face front/back, gable triangles on the left/right walls.
    ridge='y': slopes face left/right, gable triangles on the front/back walls (gable end to the street).
    ends: which gable triangles to build (first = left/front). end_over: per-end verge overhang override.
    soffit: close the underside of the verge overhangs (otherwise you look through them from the street)."""
    oe = over if over_end is None else over_end
    ea = oe if end_over[0] is None else end_over[0]
    eb = oe if end_over[1] is None else end_over[1]
    cc = shade(color, 0.8)
    if ridge == 'x':
        half = (y1 - y0) / 2
        p = rise / half
        ym = (y0 + y1) / 2
        X0, X1, Y0, Y1 = x0 - ea, x1 + eb, y0 - over, y1 + over
        ze, zr = z0 - p * over + thick, z0 + rise + thick
        for tp in ([(X0, Y0, ze), (X1, Y0, ze), (X1, ym, zr), (X0, ym, zr)], [(X1, Y1, ze), (X0, Y1, ze), (X0, ym, zr), (X1, ym, zr)]):
            slab(b, tp, thick, color, fascia, (1, 1, 0, 1))
            courses(b, tp, cc, n=ncourses)
        if ends[1]:
            b.face([(x1, y0, z0), (x1, y1, z0), (x1, ym, z0 + rise)], gable_color)
        if ends[0]:
            b.face([(x0, y1, z0), (x0, y0, z0), (x0, ym, z0 + rise)], gable_color)
        if cap:
            b.box(X0 - 0.03, ym - 0.09, zr - 0.06, X1 + 0.03, ym + 0.09, zr + CAP, cc, skip=('bottom',))
        if soffit:
            zb0, zbm = ze - thick, zr - thick
            for xa, xc in ((X0, x0), (x1, X1)):
                if xc - xa > 0.02:
                    b.face(down([(xa, Y0, zb0), (xc, Y0, zb0), (xc, ym, zbm), (xa, ym, zbm)]), fascia)
                    b.face(down([(xa, ym, zbm), (xc, ym, zbm), (xc, Y1, zb0), (xa, Y1, zb0)]), fascia)
    else:
        half = (x1 - x0) / 2
        p = rise / half
        xm = (x0 + x1) / 2
        X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - ea, y1 + eb
        ze, zr = z0 - p * over + thick, z0 + rise + thick
        for tp, ed in (([(X0, Y0, ze), (xm, Y0, zr), (xm, Y1, zr), (X0, Y1, ze)], (1, 0, 1, 1)),
                       ([(xm, Y0, zr), (X1, Y0, ze), (X1, Y1, ze), (xm, Y1, zr)], (1, 1, 1, 0))):
            slab(b, tp, thick, color, fascia, ed)
            courses(b, tp, cc, n=ncourses)
        if ends[0]:
            b.face([(x0, y0, z0), (x1, y0, z0), (xm, y0, z0 + rise)], gable_color)
        if ends[1]:
            b.face([(x1, y1, z0), (x0, y1, z0), (xm, y1, z0 + rise)], gable_color)
        if cap:
            b.box(xm - 0.09, Y0 - 0.03, zr - 0.06, xm + 0.09, Y1 + 0.03, zr + CAP, cc, skip=('bottom',))
        if soffit:
            zb0, zbm = ze - thick, zr - thick
            for ya, yc in ((Y0, y0), (y1, Y1)):
                if yc - ya > 0.02:
                    b.face(down([(X0, ya, zb0), (xm, ya, zbm), (xm, yc, zbm), (X0, yc, zb0)]), fascia)
                    b.face(down([(xm, ya, zbm), (X1, ya, zb0), (X1, yc, zb0), (xm, yc, zbm)]), fascia)
    return p


def valleys(b, xw0, xw1, ym0, zs, p, ow, color, d=0.09, start=0.12):
    """Dark valley flashing where a front wing roof (eaves at xw0-ow / xw1+ow, same pitch p) runs into the front
    slope of a main roof whose top surface is zs + p * (y - ym0). Two thin strips per valley, one on each roof plane.
    The strips start `start` up the valley from the eave corner, so they never hang out below the eaves."""
    xm = (xw0 + xw1) / 2
    lift = 0.02
    for sgn in (-1, 1):
        xa = xw0 - ow if sgn < 0 else xw1 + ow           # at the wing eave
        ya = ym0 + (xa - xw0 if sgn < 0 else xw1 - xa)
        yb_ = ym0 + (xw1 - xw0) / 2
        S = (xa, ya, zs + p * (ya - ym0) + lift)
        E = (xm, yb_, zs + p * (yb_ - ym0) + lift)
        t = start / math.sqrt(sum((E[i] - S[i]) ** 2 for i in range(3)))
        S = tuple(S[i] + (E[i] - S[i]) * t for i in range(3))
        # strip on the main slope (main plane depends on y only: shift along x, away from the wing)
        dx = -d if sgn < 0 else d
        b.face(up([S, E, (E[0] + dx, E[1], E[2]), (S[0] + dx, S[1], S[2])]), shade(color, 0.72))
        # strip on the wing slope (wing plane depends on x only: shift towards the street)
        b.face(up([S, E, (E[0], E[1] - d, E[2]), (S[0], S[1] - d, S[2])]), shade(color, 0.72))


def wing_gable(b, xw0, xw1, fy, ym0, hw, p, color, fascia, gable_color, ow=OV, of=OV):
    """Roof of a front wing (walls xw0..xw1, front wall at fy) with its gable end to the street, same pitch p as the
    main roof whose front wall is at ym0. Both slabs end exactly on the valley lines where they meet the main roof's
    front slope, from (xw0-ow, ym0-ow) up to (xm, ym0+ww/2), so nothing runs on under (or pokes out from under)
    the main roof. Fascia on the front verge and the side eaves only; verge and eave soffits closed."""
    ww = xw1 - xw0
    xm = (xw0 + xw1) / 2
    hr = p * ww / 2
    ze, zr = hw + TH - p * ow, hw + TH + hr
    yv, ys, Y0 = ym0 + ww / 2, ym0 - ow, fy - of
    for tp, ed in (([(xw0 - ow, Y0, ze), (xm, Y0, zr), (xm, yv, zr), (xw0 - ow, ys, ze)], (1, 0, 0, 1)),
                   ([(xm, Y0, zr), (xw1 + ow, Y0, ze), (xw1 + ow, ys, ze), (xm, yv, zr)], (1, 1, 0, 0))):
        slab(b, tp, TH, color, fascia, ed)
        courses(b, tp, shade(color, 0.8), margin=0.12)
    b.face([(xw0, fy, hw), (xw1, fy, hw), (xm, fy, hw + hr)], gable_color)
    zb0, zbm = ze - TH, zr - TH
    b.face(down([(xw0 - ow, Y0, zb0), (xm, Y0, zbm), (xm, fy, zbm), (xw0 - ow, fy, zb0)]), fascia)     # verge soffits
    b.face(down([(xm, Y0, zbm), (xw1 + ow, Y0, zb0), (xw1 + ow, fy, zb0), (xm, fy, zbm)]), fascia)
    zw = hw                                                                                         # eave soffits
    b.face(down([(xw0 - ow, fy, zb0), (xw0, fy, zw), (xw0, ys, zw), (xw0 - ow, ys, zb0)]), fascia)
    b.face(down([(xw1, fy, zw), (xw1 + ow, fy, zb0), (xw1 + ow, ys, zb0), (xw1, ys, zw)]), fascia)
    b.box(xm - 0.09, Y0 - 0.03, zr - 0.06, xm + 0.09, yv + 0.02, zr + CAP, shade(color, 0.8), skip=('bottom',))
    valleys(b, xw0, xw1, ym0, hw + TH, p, ow, color)


def wing_hip(b, xw0, xw1, fyw, ym0, hw, p, color, fascia, ow=OV):
    """Hip roof of a front wing (walls xw0..xw1, front wall at fyw) with the main roof's pitch p, clipped on the
    valley lines like wing_gable: front hip face, two side slopes ending on the valleys, hip strips, ridge cap."""
    ww = xw1 - xw0
    xm = (xw0 + xw1) / 2
    ze, zr = hw + TH - p * ow, hw + TH + p * ww / 2
    yr, yv, ys, Y0 = fyw + ww / 2, ym0 + ww / 2, ym0 - ow, fyw - ow
    A, B = (xw0 - ow, Y0, ze), (xw1 + ow, Y0, ze)
    R, V = (xm, yr, zr), (xm, yv, zr)
    SL, SR = (xw0 - ow, ys, ze), (xw1 + ow, ys, ze)
    slab(b, [A, B, R], TH, color, fascia, (1, 0, 0))
    slab(b, [A, R, V, SL], TH, color, fascia, (0, 0, 0, 1))
    slab(b, [B, SR, V, R], TH, color, fascia, (1, 0, 0, 0))
    for tp in ([A, B, R], [A, R, V, SL], [B, SR, V, R]):
        courses(b, tp, shade(color, 0.8), margin=0.12)
    cc = shade(color, 0.8)
    _hip_strip(b, (A[0], A[1]), (R[0], R[1]), ze, zr, cc, False, True)
    _hip_strip(b, (B[0], B[1]), (R[0], R[1]), ze, zr, cc, False, True)
    b.box(xm - 0.09, yr, zr - 0.06, xm + 0.09, yv + 0.02, zr + CAP, cc, skip=('bottom',))
    valleys(b, xw0, xw1, ym0, hw + TH, p, ow, color)


def under(y, y0, y1, zf, zb, thick, embed=0.03):
    """Height at which a post standing at y meets the underside of a shed slab (top zf at y0, zb at y1),
    pushed `embed` into the slab so the joint never shows a gap."""
    return zf + (zb - zf) * (y - y0) / (y1 - y0) - thick + embed


def shed(b, x0, x1, y0, y1, zf, zb, color, fascia=None, thick=0.08, edges=(1, 1, 1, 1), bottom=True, ncourses=0):
    """Single-slope slab over [x0,x1] x [y0,y1] (overhangs included): top at zf along y0 and zb along y1.
    edges = fascia on (front, right, back, left); bottom closes the underside (one quad), so the overhangs do not
    turn see-through when looked at from below."""
    fc = fascia or shade(color, 0.85)
    slab(b, [(x0, y0, zf), (x1, y0, zf), (x1, y1, zb), (x0, y1, zb)], thick, color, fc, edges)
    if ncourses:
        courses(b, [(x0, y0, zf), (x1, y0, zf), (x1, y1, zb), (x0, y1, zb)], shade(color, 0.8), n=ncourses)
    if bottom:
        t = thick
        b.face(down([(x0, y0, zf - t), (x1, y0, zf - t), (x1, y1, zb - t), (x0, y1, zb - t)]), fc)


def ribs(b, x0, x1, y0, y1, zf, zb, color, step=0.55):
    """Raised ribs on a zinc / spandek shed roof (runs along y, i.e. down the slope)."""
    n = int((x1 - x0) / step)
    for i in range(1, n):
        x = x0 + (x1 - x0) * i / n
        ya, yc = y0 + 0.04, y1 - 0.04
        za, zc = zf + (zb - zf) * 0.04 / (y1 - y0), zb - (zb - zf) * 0.04 / (y1 - y0)
        top = [(x - 0.03, ya, za + 0.035), (x + 0.03, ya, za + 0.035), (x + 0.03, yc, zc + 0.035), (x - 0.03, yc, zc + 0.035)]
        slab(b, top, 0.05, color, color, (1, 1, 0, 1))


def rib_decals(b, x0, x1, y0, y1, zf, zb, color, n=3, w=0.035, lift=0.02):
    """Cheap corrugation lines on a shed slab (top zf at y0, zb at y1): n single quads (2 tris each) running
    down the slope, lifted a little so they never flicker."""
    for i in range(1, n + 1):
        x = x0 + (x1 - x0) * i / (n + 1)
        ya, yc = y0 + 0.05, y1 - 0.03
        za = zf + (zb - zf) * (ya - y0) / (y1 - y0) + lift
        zc = zf + (zb - zf) * (yc - y0) / (y1 - y0) + lift
        b.face([(x - w, ya, za), (x + w, ya, za), (x + w, yc, zc), (x - w, yc, zc)], color)


COURSES = [5]        # tile course lines per genteng slope, set per variant in build()


def _slice(poly, z):
    """The two points where a convex planar polygon crosses the horizontal plane at height z."""
    out = []
    n = len(poly)
    for i in range(n):
        a, c = poly[i], poly[(i + 1) % n]
        if (a[2] - z) * (c[2] - z) < 0:
            t = (z - a[2]) / (c[2] - a[2])
            out.append(tuple(a[k] + (c[k] - a[k]) * t for k in range(3)))
    return out if len(out) == 2 else None


def courses(b, poly, color, n=None, w=0.07, lift=0.012, margin=0.0):
    """Genteng courses: n thin decal strips (2 tris each) parallel to the eave of a sloped roof face `poly` (its top
    polygon), evenly spaced between the lowest and highest point. Lifted a little (less than the hip/valley strips,
    which lie on top of them) so nothing flickers."""
    n = COURSES[0] if n is None else n
    if n <= 0:
        return
    zs = [p[2] for p in poly]
    zlo, zhi = min(zs), max(zs)
    if zhi - zlo < 0.1:
        return
    nx = ny = nz = 0.0
    for i in range(len(poly)):
        a, c = poly[i], poly[(i + 1) % len(poly)]
        nx += (a[1] - c[1]) * (a[2] + c[2])
        ny += (a[2] - c[2]) * (a[0] + c[0])
        nz += (a[0] - c[0]) * (a[1] + c[1])
    L = math.sqrt(nx * nx + ny * ny + nz * nz)
    dz = w * math.sqrt(nx * nx + ny * ny) / L           # rise over a strip width w measured along the slope
    along = (-ny, nx)                                    # horizontal direction of the course lines
    for k in range(1, n + 1):
        z = zlo + (zhi - zlo) * (k - 0.35) / (n + 0.3)
        s1, s2 = _slice(poly, z), _slice(poly, z + dz)
        if not s1 or not s2:
            continue
        s1 = sorted(s1, key=lambda p: p[0] * along[0] + p[1] * along[1])
        s2 = sorted(s2, key=lambda p: p[0] * along[0] + p[1] * along[1])
        if margin:
            for s in (s1, s2):
                d = [s[1][i] - s[0][i] for i in range(3)]
                ln = math.sqrt(sum(x * x for x in d)) or 1.0
                s[0] = tuple(s[0][i] + d[i] / ln * margin for i in range(3))
                s[1] = tuple(s[1][i] - d[i] / ln * margin for i in range(3))
        q = [s1[0], s1[1], s2[1], s2[0]]
        if math.dist(q[0], q[1]) < 0.25:
            continue
        b.face(up([(p[0], p[1], p[2] + lift) for p in q]), color)


# ------------------------------------------------------------------------------------------ house parts
def body(b, x0, x1, y0, y1, h, wall, plinth='plinth', top=False, skip=()):
    b.box(x0, y0, 0, x1, y1, h, wall, skip=('bottom',) + (() if top else ('top',)) + tuple(skip))
    if plinth:
        b.box(x0 - 0.04, y0 - 0.04, 0, x1 + 0.04, y1 + 0.04, 0.3, plinth, skip=('bottom', 'top') + tuple(skip))


def yard(b, color='concrete', y0=0.06):
    b.box(-b.W / 2 + 0.02, y0, 0, b.W / 2 - 0.02, b.D - 0.02, 0.03, color)


def side_windows(b, v, x0, x1, ya, yc, z=1.0, sides=('left', 'right')):
    L = yc - ya
    if L < 1.8:
        return
    n = 1 if L < 5.0 else 2
    for side in sides:
        wx = x0 if side == 'left' else x1
        for k in range(n):
            window(b, side, ya + L * (k + 0.5) / n, z, 0.9, 1.1, v['frame'], wall=wx, bars=2)


def back_side(b, v, rng, x0, x1, yb, hw, eave_z, left=None, toren_ok=True, annex_frac=0.55, ac=True,
              plinth='plinth', keep=0.0):
    """Lived-in back. Always: dapur annex (ribbed lean-to, back door, kitchen window) and a bedroom window on the
    free part of the main back wall. Per variant (v['bk'] dict):
      ac     AC condenser on the back wall, only placed where it clears the window (free wall part > 3.45 m)
      toren  'yard' (on a 1.9 m stand in the outer back corner; the window dodges it, or else the tank moves to the
             back fence), 'annex' (on a concrete plinth on the annex roof) or 'none'
      jem    'full' / 'short' / 'none' clothesline along the back fence, zl = line height (1.5-1.9 m)
      extra  'pisang', 'sumur', 'motor' or 'pots' in the free back yard
    `keep` = extra width next to the annex that props must leave clear (e.g. for a ladder). Returns (ax0, ax1, ya)."""
    W, D = b.W, b.D
    bk = v.get('bk', {})
    lay = bk.get('layout', 'annex')
    bd = D - yb
    ad = max(1.4, min(2.1, bd - 0.5))
    if left is None:
        left = rng.random() < 0.5
    aw = max(2.0, (x1 - x0) * annex_frac)
    ax0, ax1 = (x0, x0 + aw) if left else (x1 - aw, x1)
    ya = yb + ad
    awall = v.get('annex_wall') or lit('#ece6d8')
    aroof = v.get('annex_roof') or lit('#8d949a', GAIN_ROOF)
    zt0 = min(hw - 0.25, eave_z - 0.1)             # lean-to top against the main wall (below the main eave)
    slope = 0.2
    zt1 = zt0 - slope * (ad + 0.25)
    rx0, rx1 = max(ax0 - 0.15, -W / 2 + 0.03), min(ax1 + 0.15, W / 2 - 0.03)
    ry0, ry1 = yb - 0.03, ya + 0.25
    dx = ax0 + 0.75 if left else ax1 - 0.75
    wx = ax1 - 0.75 if left else ax0 + 0.75
    zd = None
    if lay == 'teras':
        # no annex: covered back terrace (lean-to on two posts) with the back door, a bench and pots
        tf = 0.15
        b.box(ax0, yb, 0, ax1, ya, tf, 'tile_floor', skip=('bottom', 'front'))
        shed(b, rx0, rx1, ry0, ry1, zt0, zt1, aroof, edges=(0, 1, 1, 1), ncourses=bk.get('tcourses', 0))
        if not bk.get('tcourses'):
            rib_decals(b, rx0, rx1, ry0, ry1, zt0, zt1, shade(aroof, 0.72), n=max(3, min(4, int((rx1 - rx0) / 0.75))))
        pc = bk.get('postc', 'frame_brown')
        for px in (ax0 + 0.12, ax1 - 0.12):
            post(b, px, ya - 0.12, tf, under(ya - 0.12, ry0, ry1, zt0, zt1, 0.08), pc, r=0.06)
        door(b, 'back', dx, 0.85, 2.0, 'door_dark', v['frame'], wall=yb, z0=tf, boven=0.25)
        if ax1 - ax0 > 2.3:
            window(b, 'back', wx, 1.15, 0.8, 0.8, v['frame'], wall=yb, bars=2, teralis='rail_black')
            b.box(wx - 0.6, yb, tf, wx + 0.6, yb + 0.4, 0.58, v.get('bench', 'door_wood'), skip=('bottom', 'front'))
        npots = bk.get('tpots', 2)
        for k in range(npots):
            px = (ax0 + ax1) / 2 + (k - 0.5 * (npots - 1)) * 0.7
            pot(b, px, ya - 0.3, tf, s=0.75 + 0.2 * k, plant='plant_dark' if k else 'plant')
    elif lay == 'dak':
        # flat cor-dak annex: concrete slab with a low parapet, the toren stands on it
        zd = min(2.75, eave_z - 0.12)
        b.box(ax0, yb, 0, ax1, ya, zd - 0.15, awall, skip=('bottom', 'top', 'front'))
        b.box(ax0 - 0.04, yb + 0.04, 0, ax1 + 0.04, ya + 0.04, 0.25, plinth, skip=('bottom', 'top', 'front'))
        dk = v.get('dakc', '#a8a39a')
        b.box(ax0 - 0.06, yb, zd - 0.15, ax1 + 0.06, ya + 0.06, zd, dk, skip=('front',))
        pa = v.get('annex_par', awall)
        b.box(ax0 - 0.06, ya - 0.08, zd, ax1 + 0.06, ya + 0.06, zd + 0.4, pa, skip=('bottom',))
        for xa, xc in ((ax0 - 0.06, ax0 + 0.06), (ax1 - 0.06, ax1 + 0.06)):
            b.box(xa, yb + 0.6, zd, xc, ya - 0.08, zd + 0.4, pa, skip=('bottom', 'back'))
        b.face([(ax0 + 0.06, yb + 0.03, zd + 0.006), (ax1 - 0.06, yb + 0.03, zd + 0.006), (ax1 - 0.06, ya - 0.08, zd + 0.006),
                (ax0 + 0.06, ya - 0.08, zd + 0.006)], aroof)
        b.box(ax1 - 0.35 if left else ax0 + 0.25, ya + 0.06, 0.3, ax1 - 0.25 if left else ax0 + 0.35, ya + 0.14, zd + 0.3, '#6f7680',
              skip=('bottom', 'front'))                                      # downpipe
        door(b, 'back', dx, 0.8, 1.95, 'door_dark', v['frame'], wall=ya, boven=0.0)
        if ax1 - ax0 > 2.3:
            window(b, 'back', wx, 1.2, 0.7, 0.6, v['frame'], wall=ya, bars=1, teralis='rail_black')
    else:
        hb = zt0 - slope * ad - 0.08                    # annex back wall height (meets the slab underside)
        hf = zt0 - 0.08
        b.box(ax0, yb, 0, ax1, ya, hb, awall, skip=('bottom', 'top', 'front'))
        b.face([(ax0, ya, hb), (ax0, yb, hb), (ax0, yb, hf)], awall)           # side gable of the lean-to (left)
        b.face([(ax1, yb, hb), (ax1, ya, hb), (ax1, yb, hf)], awall)           # (right)
        b.box(ax0 - 0.04, yb + 0.04, 0, ax1 + 0.04, ya + 0.04, 0.25, plinth, skip=('bottom', 'top', 'front'))
        tile = bk.get('tile', False)
        shed(b, rx0, rx1, ry0, ry1, zt0, zt1, aroof, edges=(0, 1, 1, 1), ncourses=3 if tile else 0)
        if not tile:
            rib_decals(b, rx0, rx1, ry0, ry1, zt0, zt1, shade(aroof, 0.72), n=max(3, min(4, int((rx1 - rx0) / 0.75))))
        # back door + small kitchen window on the annex
        door(b, 'back', dx, 0.8, 1.95, 'door_dark', v['frame'], wall=ya, boven=0.0)
        if ax1 - ax0 > 2.3:
            window(b, 'back', wx, 1.2, 0.7, 0.6, v['frame'], wall=ya, bars=1, teralis='rail_black')
    # the free part of the main back wall and of the yard behind it
    fx0, fx1 = (ax1, x1) if left else (x0, ax0)
    F = fx1 - fx0
    sg = 1 if left else -1                          # direction from the annex (inner) towards the lot edge
    inner = fx0 if left else fx1
    lot_out = W / 2 if left else -W / 2
    annex_ok = lay == 'annex' and ad >= 1.75 and zt0 + 1.1 <= HMAX
    tmode = bk.get('toren', 'yard') if toren_ok else 'none'
    if lay == 'dak' and tmode != 'none':
        tmode = 'dak' if ad >= 1.72 and zd + 1.45 <= HMAX else 'yard'
    if tmode == 'annex' and not annex_ok:
        tmode = 'yard'
    if tmode == 'yard' and (bd <= 1.9 or F <= 1.25):
        tmode = 'annex' if annex_ok else 'none'
    cur = [lot_out - sg * 0.08]
    lim = inner + sg * (0.25 + keep)

    def slot(width):
        """Next free x-slot in the back yard, filled from the lot edge towards the annex."""
        a, c = cur[0], cur[0] - sg * width
        if (c - lim) * sg < 0:
            return None
        cur[0] = c
        return (a + c) / 2
    tx = ty = None
    if tmode == 'yard':
        tx = slot(1.2)
        if tx is None:
            tmode = 'none'
        else:
            ty = min(D - 0.62, yb + OV + 0.62)
    extra = bk.get('extra')
    ex = None
    if extra:
        ex = slot({'pisang': 2.3, 'motor': 0.95, 'sumur': 1.15, 'pots': 1.6}[extra])
    pr = 1.1                                                          # pisang crown radius
    if extra == 'pisang' and ex is None:
        pr, ex = 0.8, slot(1.7)                                       # a younger, smaller plant
        if ex is None:
            extra, ex = 'pots', slot(1.6)
    # bedroom window (+ AC only where both fit side by side); it dodges the toren and the pisang crown
    fin = inner + sg * keep                                          # the window also leaves the `keep` strip clear
    Fw = F - keep
    if Fw > 1.3:
        ww = min(1.2, Fw - 0.6)
        wc = fin + sg * Fw / 2
        acx = None
        if ac and bk.get('ac') and Fw > 3.45:
            acx = fin + sg * 0.6
            wc += sg * 0.45
        half = ww / 2 + 0.12
        lo = fin + sg * ((1.15 if acx is not None else 0.25) + half)
        if (wc - lo) * sg < 0:
            wc = lo

        def overlap(edge):
            return sg * ((wc + sg * half) - edge)                    # how far the window runs in behind a prop
        if tx is not None:
            over_ = overlap(tx - sg * 0.56)
            if over_ > 0:
                if (wc - lo) * sg >= over_ + 0.05:
                    wc -= sg * (over_ + 0.05)
                elif bd >= 2.2:
                    ty = D - 0.62                                     # tank to the back fence instead
        if extra == 'pisang':
            over_ = overlap(ex - sg * pr)
            if over_ > 0:
                sh = min(over_ + 0.05, max(0.0, (wc - lo) * sg))
                wc -= sg * sh
                pr = max(0.75, pr - (over_ + 0.05 - sh))
        window(b, 'back', wc, 1.0, ww, 1.2, v['frame'], wall=yb, bars=2, teralis=v.get('teralis'))
        if acx is not None:
            b.ac_unit('back', acx, 2.0, wall=yb)
    tank = v.get('tank', 'tank_orange')
    if tmode == 'yard':
        toren(b, tx, ty, 0.03, 1.9, tank)
    elif tmode == 'dak':
        tax = (ax0 + ax1) / 2 + (-0.3 if left else 0.3)
        tay = max(yb + OV + 0.62, ya - 0.7)
        toren(b, tax, tay, zd, 0.3, tank)
    elif tmode == 'annex':
        tax, tay = ((ax0 + 0.72) if left else (ax1 - 0.72)), yb + 1.05

        def zroof(y):
            return zt0 + (zt1 - zt0) * (y - ry0) / (ry1 - ry0)
        zp = zroof(tay - 0.5) + 0.05
        b.box(tax - 0.5, tay - 0.5, zroof(tay + 0.5) - 0.03, tax + 0.5, tay + 0.5, zp, 'concrete')
        toren(b, tax, tay, zp, 0, tank)
    obst = []                                                         # x-ranges blocked at the back fence
    if tmode == 'yard' and ty > D - 1.2:
        obst.append((tx - 0.62, tx + 0.62))
    if ex is not None:
        if extra == 'pisang':
            pisang(b, ex, D - 1.2, r=pr, phase=0.07 + 0.3 * rng.random())
            obst.append((ex - pr, ex + pr))
        elif extra == 'motor':
            motor(b, ex, yb + 1.25, MOTORS[rng.randrange(len(MOTORS))], face=1, z0=0.03)
            obst.append((ex - 0.45, ex + 0.45))
        elif extra == 'sumur':
            sumur(b, ex, yb + 1.15)
        else:
            for k in range(3):
                pot(b, ex + (k - 1) * 0.5, D - 0.55, 0.03, s=0.8 + 0.25 * rng.random(), plant='plant_dark' if k % 2 else 'plant')
    jm = bk.get('jem', 'full')
    if jm != 'none':
        free = _segments(-W / 2 + 0.25, W / 2 - 0.25, obst)
        if free:
            ja, jc = max(free, key=lambda s: s[1] - s[0])
            if jm == 'short' and jc - ja > 2.8:
                ja, jc = (ja, ja + 2.8) if left else (jc - 2.8, jc)
            if jc - ja > 1.5:
                jemuran(b, ja, jc, D - 0.2, 'x', rng, z0=0.03, zl=bk.get('zl', 1.7))
    return ax0, ax1, ya


# ------------------------------------------------------------------------------------------ sub-styles
def k_limasan(b, v, rng):
    """Teras on columns under a hip roof, besi pagar."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 3.0)
    fy, t = v.get('yard', 0.95), v.get('terrace', 1.9)
    yf, yb = fy + t, D - v.get('back', 2.4)
    yard(b, v.get('yardc', 'concrete'))
    b.box(x0, fy, 0, x1, yf, 0.2, 'tile_floor')
    cols = [x0 + 0.14, x1 - 0.14]
    if x1 - x0 > 7.5:
        cols += [x0 + (x1 - x0) / 3, x0 + (x1 - x0) * 2 / 3]
    for xc in cols:
        post(b, xc, fy + 0.14, 0.2, hw - 0.25, v.get('col', 'column'), r=0.12)
    b.box(x0, fy + 0.02, hw - 0.25, x1, fy + 0.26, hw, v['wall'], skip=('bottom', 'top'))
    for xs in (x0, x1 - 0.24):
        b.box(xs, fy + 0.26, hw - 0.25, xs + 0.24, yf, hw, v['wall'], skip=('bottom', 'top', 'front', 'back'))
    body(b, x0, x1, yf, yb, hw, v['wall'])
    du = facade(b, 'front', x0, x1, 0.2, v, rng, wall=yf, teralis=v.get('teralis'))
    side_windows(b, v, x0, x1, yf, yb)
    rise = min(v.get('rise', 1.5), HMAX - hw - TH - CAP)
    p = hip(b, x0, x1, fy, yb, hw, rise, v['roof'], v['fascia'])
    back_side(b, v, rng, x0, x1, yb, hw, hw - p * OV)
    # step, fence with a gate in front of the door, terrace furniture and pots
    b.box(du - 0.6, fy - 0.35, 0, du + 0.6, fy, 0.1, 'tile_floor')
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (du - 0.55, du + 0.55))
    bx = x0 + 0.35 if du > 0 else x1 - 1.65
    bench(b, bx, bx + 1.3, yf - 0.5, z0=0.2, color=v.get('bench', 'door_wood'))
    for k in range(rng.randint(2, 4)):
        px = (x1 - 0.35 - k * 0.5) if du > 0 else (x0 + 0.35 + k * 0.5)
        pot(b, px, fy + 0.45, 0.2, s=0.8 + 0.3 * rng.random())


def k_pelana(b, v, rng):
    """Gable end to the street, front kanopi on posts, tembok pagar with a sliding steel gate."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 3.0)
    yf = v.get('yard', 2.3)
    yb = D - v.get('back', 2.4)
    yard(b, v.get('yardc', 'tile_floor'))
    body(b, x0, x1, yf, yb, hw, v['wall'])
    du = facade(b, 'front', x0, x1, 0.12, v, rng, wall=yf, teralis=v.get('teralis', 'rail_black'), maxwin=1.3)
    # sliding gate on the side away from the door; the motorbike stands in the yard behind it, so the terrace
    # floor stops short of it
    gw = 2.4
    ga = (-W / 2 + 0.35, -W / 2 + 0.35 + gw) if du > 0 else (W / 2 - 0.35 - gw, W / 2 - 0.35)
    mx = (ga[0] + ga[1]) / 2
    floor_split(b, x0, x1, yf - 1.55, yf, 0.12, v.get('terasc', '#c9b39a'), [(mx - 0.42, mx + 0.42)])
    side_windows(b, v, x0, x1, yf, yb)
    rise = min(v.get('rise', 1.6), HMAX - hw - TH - CAP)
    p = gable(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'], v['accent'], ridge='y')
    # gable-end details: ventilation roster + a lisplang ornament board under the verge
    xm = (x0 + x1) / 2
    b.decal('front', xm - 0.45, xm + 0.45, hw + 0.25, hw + 0.6, 'trim_white', off=0.02, wall=yf)
    for k in range(3):
        u = xm - 0.3 + k * 0.3
        b.decal('front', u - 0.1, u + 0.1, hw + 0.3, hw + 0.55, 'trim_dark', off=0.03, wall=yf)
    b.box(x0 - 0.02, yf - 0.06, hw - 0.12, x1 + 0.02, yf, hw, v['fascia'], skip=('bottom', 'back'))
    # kanopi (polycarbonate / zinc) over the terrace on two steel posts
    ky = yf - 1.6
    kz0 = hw - 0.12
    shed(b, x0 - 0.1, x1 + 0.1, ky, yf + 0.03, kz0 - 0.3, kz0, v.get('kanopi', '#7fb7b0'), edges=(1, 1, 0, 1))
    for xp in (x0 + 0.05, x1 - 0.05):
        post(b, xp, ky + 0.1, 0.03, under(ky + 0.1, ky, yf + 0.03, kz0 - 0.3, kz0, 0.08), 'rail_black', r=0.045)
    back_side(b, v, rng, x0, x1, yb, hw, hw - p * OV)
    fence_tembok(b, -W / 2 + 0.03, W / 2 - 0.03, [ga], v.get('fwall', v['wall']), v.get('fcap', 'trim_white'))
    gate_panel(b, ga[0], ga[1], v.get('gatec', '#3f5a48'))
    motor(b, mx, yf - 0.95 - 0.9 if yf > 2.6 else 1.25, MOTORS[rng.randrange(len(MOTORS))], z0=0.03)
    for k in range(rng.randint(2, 3)):
        px = (x1 - 0.3 - k * 0.5) if du < 0 else (x0 + 0.3 + k * 0.5)
        pot(b, px, 0.45, 0.03, s=0.9)


def k_teras(b, v, rng):
    """Gable end to the street whose roof also covers a column terrace; besi pagar."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 2.95)
    fy, t = v.get('yard', 1.0), v.get('terrace', 2.0)
    yf, yb = fy + t, D - v.get('back', 2.4)
    yard(b, v.get('yardc', 'concrete'))
    b.box(x0, fy, 0, x1, yf, 0.25, 'tile_floor')
    for xc in (x0 + 0.15, x1 - 0.15):
        post(b, xc, fy + 0.15, 0.25, hw - 0.3, v.get('col', 'column'), r=0.13)
    b.box(x0, fy + 0.02, hw - 0.3, x1, fy + 0.28, hw, v['wall'], skip=('bottom', 'top'))
    for xs in (x0, x1 - 0.26):
        b.box(xs, fy + 0.28, hw - 0.3, xs + 0.26, yf, hw, v['wall'], skip=('bottom', 'top', 'front', 'back'))
    # low terrace wall with a gap for the entrance
    xm = (x0 + x1) / 2
    for a, c in ((x0 + 0.28, xm - 0.6), (xm + 0.6, x1 - 0.28)):
        b.box(a, fy + 0.05, 0.25, c, fy + 0.25, 0.8, v['wall'])
        b.box(a, fy + 0.02, 0.8, c, fy + 0.28, 0.87, 'trim_white', skip=('bottom', 'left', 'right'))
    body(b, x0, x1, yf, yb, hw, v['wall'])
    facade(b, 'front', x0, x1, 0.25, v, rng, wall=yf, door_at=0.5, door_w=1.3, leaves=2, teralis=v.get('teralis'))
    side_windows(b, v, x0, x1, yf, yb)
    rise = min(v.get('rise', 1.75), HMAX - hw - TH - CAP)
    p = gable(b, x0, x1, fy, yb, hw, rise, v['roof'], v['fascia'], v['accent'], ridge='y')
    b.decal('front', xm - 0.5, xm + 0.5, hw + 0.3, hw + 0.7, 'trim_white', off=0.02, wall=fy)
    b.decal('front', xm - 0.4, xm + 0.4, hw + 0.37, hw + 0.63, 'glass_dark', off=0.03, wall=fy)
    back_side(b, v, rng, x0, x1, yb, hw, hw - p * OV)
    b.box(xm - 0.7, fy - 0.35, 0, xm + 0.7, fy, 0.12, 'tile_floor')
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (xm - 0.6, xm + 0.6), gate=None)
    for k in range(4):
        px = x0 + 0.5 + k * 0.55 if k < 2 else x1 - 0.5 - (k - 2) * 0.55
        pot(b, px, fy - 0.45, 0.03, s=0.9 + 0.2 * rng.random(), plant='plant' if k % 2 else 'plant_dark')
    bench(b, x0 + 0.5, x0 + 1.7, yf - 0.55, z0=0.25, color=v.get('bench', 'door_wood'))


def k_carport(b, v, rng):
    """Small house next to a carport: thin shed roof on steel posts over a parking pad with motorbikes."""
    W, D = b.W, b.D
    si = OV + 0.08
    cw = v.get('cw', 2.7)
    left = v.get('cleft', True)
    if left:
        cx0, cx1 = -W / 2 + 0.05, -W / 2 + cw
        x0, x1 = cx1, W / 2 - si
    else:
        cx0, cx1 = W / 2 - cw, W / 2 - 0.05
        x0, x1 = -W / 2 + si, cx0
    hw = v.get('hw', 3.0)
    yf = v.get('yard', 1.6)
    yb = D - v.get('back', 2.4)
    yard(b, v.get('yardc', 'concrete'))
    body(b, x0, x1, yf, yb, hw, v['wall'])
    du = facade(b, 'front', x0, x1, 0.12, v, rng, wall=yf, door_at=0.72 if left else 0.28, teralis=v.get('teralis', 'rail_white'))
    b.box(x0, yf - 1.2, 0, x1, yf, 0.12, 'tile_floor')
    # flat concrete door canopy on brackets
    b.box(du - 0.9, yf - 0.8, 2.62, du + 0.9, yf, 2.74, v.get('fascia', 'trim_white'), skip=('bottom', 'back'))
    side_windows(b, v, x0, x1, yf, yb, sides=('right',) if left else ('left',))
    rise = min(v.get('rise', 1.5), HMAX - hw - TH - CAP)
    if v.get('roofk', 'hip') == 'hip':
        p = hip(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'])
    else:
        p = gable(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'], v['wall'], ridge='x')
    eave = hw - p * OV
    # carport: pad, posts, thin sloping roof (high at the house, low at the street)
    cy1 = min(yb - 0.2, yf + 3.0)
    b.box(cx0, 0.0, 0, cx1, cy1, 0.06, 'concrete_dark')
    zb, zf = min(2.75, eave - 0.12), 2.5
    ox = cx0 + 0.12 if left else cx1 - 0.12
    ix = cx1 - 0.08 if left else cx0 + 0.08
    for (px, py) in ((ox, 0.45), (ox, cy1 - 0.15), (ix, 0.45)):
        post(b, px, py, 0.06, under(py, 0.3, cy1, zf, zb, 0.06), 'rail_black', r=0.05)
    croof = v.get('croof', '#5f9aa8')
    shed(b, cx0, cx1, 0.3, cy1, zf, zb, croof, fascia='rail_black', thick=0.06)
    rib_decals(b, cx0, cx1, 0.3, cy1, zf, zb, shade(croof, 0.72), n=max(3, int((cx1 - cx0) / 0.7)))
    mx = (cx0 + cx1) / 2
    # carport contents per variant: [(dx, y, colour index or None)] scooters, plus jerigen / pots
    for dxm, ym, ci in v.get('cmotors', [(-0.45, 1.9, None)]):
        motor(b, mx + dxm, ym, MOTORS[rng.randrange(len(MOTORS))] if ci is None else MOTORS[ci], z0=0.06)
    for kind, dxp, yp in v.get('cprops', ()):
        if kind == 'jerigen':
            jerigen(b, mx + dxp, yp, 0.06, v.get('jerc', '#e8c02a'))
        else:
            pot(b, mx + dxp, yp, 0.06, s=0.85, plant='plant_dark' if dxp > 0 else 'plant')
    back_side(b, v, rng, x0, x1, yb, hw, eave, left=not left)
    # strip behind the carport: clothesline and pots
    if yb - cy1 > 2.0:
        jemuran(b, cy1 + 0.4, yb - 0.1, mx, 'y', rng, z0=0.03, zl=1.7)
        for k in range(min(2, int((yb - cy1 - 0.6) / 0.7))):
            pot(b, cx0 + 0.3 if left else cx1 - 0.3, cy1 + 0.5 + k * 0.7, 0.03, s=0.8, plant='plant_dark' if k % 2 else 'plant')
    # fence over the full width: sliding gate across the carport, besi fence + small gate in front of the house
    cg = (cx0 + 0.25, cx1 + 0.05) if left else (cx0 - 0.05, cx1 - 0.25)
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (du - 0.5, du + 0.5), more=[cg])
    gate_slide(b, cg[0], cg[1], v.get('cgatec', v['fence']), h=v.get('fh', 1.2) + 0.05, style=v.get('cgate', 'v'))
    for k in range(2):
        px = (x1 - 0.35 - k * 0.5) if left else (x0 + 0.35 + k * 0.5)
        pot(b, px, yf - 0.55, 0.12, s=0.9)


def k_jemuran(b, v, rng):
    """House pushed to one side; side yard with clotheslines, pots and a small tree."""
    W, D = b.W, b.D
    si = OV + 0.08
    sw = v.get('sw', 2.1)
    left = v.get('sleft', True)
    if left:
        sx0, sx1 = -W / 2 + 0.1, -W / 2 + sw
        x0, x1 = sx1, W / 2 - si
    else:
        sx0, sx1 = W / 2 - sw, W / 2 - 0.1
        x0, x1 = -W / 2 + si, sx0
    hw = v.get('hw', 3.0)
    yf = v.get('yard', 1.5)
    yb = D - v.get('back', 2.4)
    yard(b, v.get('yardc', SOIL))
    b.box(x0 - 0.3, 0.2, 0, x1 + 0.3 if x1 + 0.3 < W / 2 else x1, yf, 0.06, 'tile_floor')
    body(b, x0, x1, yf, yb, hw, v['wall'])
    facade(b, 'front', x0, x1, 0.06, v, rng, wall=yf, door_at=0.3 if left else 0.7, teralis=v.get('teralis', 'rail_black'))
    # flat concrete kanopi over the door and windows
    b.box(x0 + 0.1, yf - 0.85, 2.6, x1 - 0.1, yf, 2.72, 'trim_white', skip=('bottom', 'back'))
    sides = ('right',) if left else ('left',)
    side_windows(b, v, x0, x1, yf, yb, sides=sides)
    # side door onto the side yard
    door(b, 'left' if left else 'right', yb - 1.2, 0.8, 2.0, v.get('door', 'door_wood'), v['frame'], wall=x0 if left else x1, boven=0.0)
    rise = min(v.get('rise', 1.5), HMAX - hw - TH - CAP)
    if v.get('roofk') == 'hip':
        p = hip(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'])
    else:
        p = gable(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'], v['accent'], ridge='x')
    eave = hw - p * OV
    back_side(b, v, rng, x0, x1, yb, hw, eave, left=not left)
    # side yard: two clotheslines running back, pots; a small tree in the outer front corner behind solid fence,
    # next to (not behind) a 1 m side gate on the house side of the side yard
    jx = (sx0 + sx1) / 2 + (0.15 if left else -0.15)
    jemuran(b, yf + 0.3, yb - 0.3, jx - 0.3, 'y', rng, z0=0.03, zl=1.75)
    jemuran(b, yf + 0.3, yb - 0.3, jx + 0.3, 'y', rng, z0=0.03, zl=1.75)
    gw = min(1.0, sw - 0.95)
    tr = min(0.62, 0.5 + (sw - 1.8) * 0.4)          # crown radius: stays inside the lot
    if left:
        gap = (sx1 - 0.15 - gw, sx1 - 0.15)
        tx = -W / 2 + tr + 0.02
    else:
        gap = (sx0 + 0.15, sx0 + 0.15 + gw)
        tx = W / 2 - tr - 0.02
    tree(b, tx, 0.95, h=3.1, r=tr / 0.98, color=v.get('treec', 'plant'))
    for k in range(3):
        pot(b, sx0 + 0.3 if left else sx1 - 0.3, yf + 0.5 + k * 0.6, 0.03, s=0.8)
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, gap)
    for k in range(rng.randint(2, 4)):
        px = (x1 - 0.35 - k * 0.55) if left else (x0 + 0.35 + k * 0.55)
        pot(b, px, 0.55, 0.03, s=0.85, plant='plant_dark' if k % 2 else 'plant')


def k_loteng(b, v, rng):
    """Flat concrete dak house.
    mode 'room': a real loteng room (2.2-2.45 m headroom) on the back half of the dak, toren, jemuran and pots on
                 the rest. About 5.6 m tall, so this one is front/fill only.
    mode 'dak':  open roof terrace (<= 4.8 m, works as 'low'): clotheslines, toren in a back corner, AC condensers,
                 dish and a row of pots on a patched waterproofed slab.
    The back gets the annex plus a steel ladder up to the dak."""
    W, D = b.W, b.D
    room = v.get('mode', 'room') == 'room'
    x0, x1 = -W / 2 + 0.12, W / 2 - 0.12
    hw = v.get('hw', 2.85)
    yf = v.get('yard', 2.0)
    yb = D - v.get('back', 2.3)
    zs = hw + 0.15                                    # top of the dak slab
    yard(b, v.get('yardc', 'concrete'))
    body(b, x0 + 0.05, x1 - 0.05, yf, yb, hw, v['wall'])
    # dak slab with a cantilevered front over the terrace (closed underneath)
    ky = yf - 1.2
    dak = v.get('dak', '#9e9a92')
    b.box(x0, ky, hw, x1, yb, zs, dak, skip=('bottom',))
    b.face([(x0, ky, hw), (x0, yf, hw), (x1, yf, hw), (x1, ky, hw)], shade(dak, 0.9))
    coating(b, x0 + 0.14, x1 - 0.14, ky + 0.15, yb - 0.14, zs, rng, v.get('coat', '#6f9d80'), n=v.get('patches', 1))
    du = facade(b, 'front', x0 + 0.05, x1 - 0.05, 0.15, v, rng, wall=yf, teralis=v.get('teralis', 'rail_black'), boven=0.25)
    side_windows(b, v, x0 + 0.05, x1 - 0.05, yf, yb, z=1.0)
    left = v.get('lleft', du > 0)
    # terrace floor under the cantilever, open where the motorbike stands
    mx = (x0 + du - 0.7) / 2 if du > 0 else (x1 + du + 0.7) / 2
    segs = floor_split(b, x0 + 0.05, x1 - 0.05, ky, yf, 0.15, 'tile_floor', [(mx - 0.42, mx + 0.42)], min_len=0.5)
    for xp in (x0 + 0.18, x1 - 0.18):
        zf = 0.15 if any(a <= xp - 0.1 and xp + 0.1 <= c for a, c in segs) else 0.03
        post(b, xp, ky + 0.15, zf, hw, v.get('col', 'column'), r=0.1)
    motor(b, mx, yf - 0.95, MOTORS[rng.randrange(len(MOTORS))], z0=0.03)
    # parapet: solid at the sides/back, railing on the front
    pc = v.get('parapet', v['wall'])
    b.box(x0, ky, zs, x1, ky + 0.15, zs + 0.35, pc)
    rail(b, x0 + 0.02, x1 - 0.02, ky + 0.075, zs + 0.35, 0.55, v['fence'], step=0.3, style=v.get('rstyle', 'v'))
    b.box(x0, ky + 0.15, zs, x0 + 0.14, yb, zs + 0.5, pc, skip=('bottom',))
    b.box(x1 - 0.14, ky + 0.15, zs, x1, yb, zs + 0.5, pc, skip=('bottom',))
    b.box(x0 + 0.14, yb - 0.14, zs, x1 - 0.14, yb, zs + 0.5, pc, skip=('bottom',))
    tank = v.get('tank', 'tank_blue')
    if room:
        lw = min(x1 - x0 - 1.6, v.get('lw', 3.6))
        lx0, lx1 = (x0 + 0.14, x0 + 0.14 + lw) if left else (x1 - 0.14 - lw, x1 - 0.14)
        ly0, ly1 = yb - v.get('ld', 3.0), yb - 0.14
        lz = zs + 2.6
        lwall = v.get('lwall', v['wall'])
        lfront = lz - 0.16
        lback = lfront - 0.25
        b.box(lx0, ly0, zs, lx1, ly1, lback, lwall, skip=('bottom', 'top'))
        b.face([(lx0, ly1, lback), (lx0, ly0, lback), (lx0, ly0, lfront)], lwall)
        b.face([(lx1, ly0, lback), (lx1, ly1, lback), (lx1, ly0, lfront)], lwall)
        b.box(lx0, ly0, lback, lx1, ly0 + 0.02, lfront, lwall, skip=('bottom', 'top', 'back', 'left', 'right'))
        lzb = lz - 0.28 * (ly1 - ly0 + 0.4) / (ly1 - ly0)
        lroof = v.get('lroof', v['roof'])
        shed(b, lx0 - 0.2, lx1 + 0.2, ly0 - 0.3, ly1 + 0.1, lz, lzb, lroof)
        rib_decals(b, lx0 - 0.2, lx1 + 0.2, ly0 - 0.3, ly1 + 0.1, lz, lzb, shade(lroof, 0.72), n=int((lw + 0.4) / 0.6))
        window(b, 'front', (lx0 + lx1) / 2, zs + 0.95, min(1.4, lw - 0.8), 1.05, v['frame'], wall=ly0, bars=2, boven=0.2)
        dside = 'right' if left else 'left'
        door(b, dside, ly0 + 0.75, 0.8, 2.0, v.get('door', 'door_wood'), v['frame'], wall=lx1 if left else lx0, z0=zs, boven=0.0)
        # dak life: toren, jemuran, pots
        fx0, fx1 = (lx1, x1 - 0.14) if left else (x0 + 0.14, lx0)
        toren(b, (fx0 + fx1) / 2 + (0.1 if left else -0.1), yb - 0.75, zs, 0.35, tank)
        jemuran(b, x0 + 0.4, x1 - 0.4, ly0 - 1.25, 'x', rng, z0=zs, zl=1.5)
        for k in range(3):
            pot(b, x0 + 0.5 + k * 0.6 if not left else x1 - 0.5 - k * 0.6, ky + 0.45, zs, s=0.8)
        if v.get('dish'):
            dish(b, x1 - 0.6 if not left else x0 + 0.6, ky + 1.3, zs)
    else:
        # open dak: toren in a back corner, two clotheslines, AC condensers along one side, pots, dish
        tx = (x1 - 0.8) if left else (x0 + 0.8)
        toren(b, tx, yb - 0.8, zs, 0.35, tank)
        ja, jc = (x0 + 0.45, tx - 0.75) if left else (tx + 0.75, x1 - 0.45)
        jemuran(b, ja, jc, yb - 0.7, 'x', rng, z0=zs, zl=1.5)
        jemuran(b, x0 + 0.45, x1 - 0.45, yb - 1.8, 'x', rng, z0=zs, zl=1.45, fill=0.7)
        ax = (x0 + 0.45) if left else (x1 - 0.45)
        for k in range(2):
            ac_floor(b, ax, ky + 1.4 + k * 1.1, zs, along='y')
        pots_x = [(x1 - 0.5 - k * 0.65) if left else (x0 + 0.5 + k * 0.65) for k in range(3)]
        for k, px in enumerate(pots_x):
            pot(b, px, ky + 0.45, zs, s=0.8 + 0.25 * rng.random(), plant='plant_dark' if k % 2 else 'plant')
        if v.get('dish'):
            dish(b, (x1 - 1.3) if not left else (x0 + 1.5), ky + 2.0, zs)
    # back: annex + steel ladder up to the dak, clear of the annex eave and of the bedroom window
    ax0, ax1, _ = back_side(b, v, rng, x0 + 0.05, x1 - 0.05, yb, hw, hw, left=not left, toren_ok=False, annex_frac=0.5,
                            ac=False, keep=0.75)
    lx = (ax1 + 0.42) if not left else (ax0 - 0.42)
    for dx in (-0.2, 0.2):
        b.box(lx + dx - 0.03, yb + 0.03, 0, lx + dx + 0.03, yb + 0.09, zs + 0.9, 'metal', skip=('bottom',))
    for k in range(1, 8):
        z = k * (zs + 0.6) / 8
        b.box(lx - 0.2, yb + 0.04, z, lx + 0.2, yb + 0.08, z + 0.035, 'metal', skip=('bottom', 'left', 'right'))
    # street fence + gate
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (du - 0.5, du + 0.5), h=1.1)


def k_siku(b, v, rng):
    """L-shaped house: main gable (ridge along the street) + front wing with its gable end to the street."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 3.0)
    fy = v.get('yard', 1.1)
    ww = v.get('ww', 3.8)
    left = v.get('wleft', True)
    xw0, xw1 = (x0, x0 + ww) if left else (x1 - ww, x1)
    ym0 = fy + v.get('wing', 2.6)                      # front wall of the main body
    yb = D - v.get('back', 2.4)
    yard(b, v.get('yardc', 'concrete'))
    body(b, x0, x1, ym0, yb, hw, v['wall'])
    body(b, xw0, xw1, fy, ym0, hw, v['wall'], skip=('back',))
    # wing front: big window; terrace in the corner in front of the main body
    window(b, 'front', (xw0 + xw1) / 2, 0.95, min(1.8, ww - 1.0), 1.3, v['frame'], wall=fy, bars=3, boven=0.25,
           teralis=v.get('teralis'))
    tx0, tx1 = (xw1, x1) if left else (x0, xw0)
    b.box(tx0, fy + 0.4, 0, tx1, ym0, 0.2, 'tile_floor')
    du = facade(b, 'front', tx0, tx1, 0.2, v, rng, wall=ym0, door_at=0.35 if left else 0.65, maxwin=1.2)
    side_windows(b, v, x0, x1, ym0, yb, sides=('right',) if left else ('left',))
    window(b, 'left' if left else 'right', (fy + ym0) / 2, 1.0, 0.9, 1.1, v['frame'], wall=xw0 if left else xw1)
    rise = min(v.get('rise', 1.55), HMAX - hw - TH - CAP)
    p = gable(b, x0, x1, ym0, yb, hw, rise, v['roof'], v['fascia'], v['wall'], ridge='x')
    # wing roof: same pitch, clipped on the valley lines (flush with the main verge on the outer side)
    wing_gable(b, xw0, xw1, fy, ym0, hw, p, v['roof'], v['fascia'], v['accent'])
    xm = (xw0 + xw1) / 2
    b.decal('front', xm - 0.35, xm + 0.35, hw + 0.2, hw + 0.5, 'trim_dark', off=0.02, wall=fy)
    # terrace lean-to on two columns in the corner (tucked under the wing and main eaves)
    zt = hw - p * OV - 0.12
    tz = zt - 0.3
    ty0 = fy + 0.5
    ex0, ex1 = (xw1 - 0.03, x1 + 0.15) if left else (x0 - 0.15, xw0 + 0.03)
    shed(b, ex0, ex1, ty0, ym0 + 0.03, tz, zt, v.get('troof', v['roof']), fascia=v['fascia'],
         edges=(1, 1, 0, 0) if left else (1, 0, 0, 1), ncourses=2)
    for xc in ((tx1 - 0.15) if left else (tx0 + 0.15), (tx0 + 0.25) if left else (tx1 - 0.25)):
        post(b, xc, ty0 + 0.2, 0.2, under(ty0 + 0.2, ty0, ym0 + 0.03, tz, zt, 0.08), v.get('col', 'column'), r=0.11)
    back_side(b, v, rng, x0, x1, yb, hw, hw - p * OV)
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (du - 0.55, du + 0.55), gate=None)
    # garden strip in front of the wing
    b.box(xw0, 0.25, 0, xw1, fy - 0.1, 0.08, GRASS)
    for k in range(3):
        bush(b, xw0 + 0.6 + k * (ww - 1.2) / 2, 0.65, 0.08, 0.35, 0.6, 'plant' if k % 2 else 'plant_dark')
    bench(b, tx0 + 0.5 if left else tx1 - 1.8, (tx0 + 1.8) if left else tx1 - 0.5, ym0 - 0.55, z0=0.2, color=v.get('bench', 'door_wood'))


def k_petak(b, v, rng):
    """Rumah petak: single-slope zinc roof falling to the street, motorbike at the door.
    units=2 gives a petak kontrakan (two small units side by side under one roof)."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.12, W / 2 - 0.12
    yf = v.get('yard', 1.9)
    yb = D - v.get('back', 2.3)
    hf, hbk = 2.85, 3.95
    fl = 0.06                                         # low teras step, flush enough for the motorbikes
    yard(b, v.get('yardc', 'concrete'))
    b.box(x0, yf, 0, x1, yb, hf, v['wall'], skip=('bottom', 'top'))
    b.box(x0 - 0.04, yf - 0.04, 0, x1 + 0.04, yb + 0.04, 0.3, 'plinth', skip=('bottom', 'top'))
    # the back wall rises to the high side of the roof; side walls get the matching triangles
    b.face([(x1, yb, hf), (x0, yb, hf), (x0, yb, hbk), (x1, yb, hbk)], v['wall'])
    b.face([(x0, yb, hf), (x0, yf, hf), (x0, yb, hbk)], v['wall'])
    b.face([(x1, yf, hf), (x1, yb, hf), (x1, yb, hbk)], v['wall'])
    # side walls (visible between lots): small window, high roster vent, downpipe at the back corner
    for side, wx in (('left', x0), ('right', x1)):
        window(b, side, yf + (yb - yf) * 0.45, 1.05, 0.7, 0.95, v['frame'], wall=wx, bars=1, teralis='rail_black')
        for k in range(3):
            u = yb - 1.5 + k * 0.32
            b.decal(side, u, u + 0.24, hf - 0.55, hf - 0.28, 'trim_dark', off=0.02, wall=wx)
        b.decal(side, yb - 0.3, yb - 0.2, 0.3, hbk - 0.05, '#6f7680', off=0.03, wall=wx)
    s = (hbk - hf) / (yb - yf)
    y0r = max(0.35, yf - 1.0)
    zf = hf - s * (yf - y0r) + 0.08
    zb = hbk + s * 0.12 + 0.08
    roof = v['roof']
    shed(b, x0 - 0.08, x1 + 0.08, y0r, yb + 0.12, zf, zb, roof, fascia=v['fascia'], thick=0.08)
    ribs(b, x0 - 0.08, x1 + 0.08, y0r, yb + 0.12, zf, zb, shade(roof, 0.85), step=0.9)
    b.box(x0, yf - 0.9, 0, x1, yf, fl, v.get('terasc', '#c9b39a'))
    if v.get('units', 1) == 2:
        xm = (x0 + x1) / 2
        doors = [v.get('door', 'door_dark'), v.get('door2', 'door_wood')]
        for k, (ua, uc) in enumerate(((x0, xm - 0.1), (xm + 0.1, x1))):
            vv = dict(v, door=doors[k])
            du = facade(b, 'front', ua, uc, fl, vv, rng, wall=yf, door_at=0.28, door_w=0.85,
                        teralis=v.get('teralis', 'rail_black'), boven=0.2, maxwin=1.1)
        fbox(b, 'front', xm - 0.12, xm + 0.12, fl, hf, v.get('pilaster', 'trim_white'), off=0.06, depth=0.08, wall=yf)
        b.box(xm - 0.06, yf - 0.9, fl, xm + 0.06, yf - 0.02, 0.85, v['wall'])          # low divider between the two teras
        motor(b, x1 - 0.6, 0.95, MOTORS[rng.randrange(len(MOTORS))], z0=0.03)
        du = x1 - 0.3
    else:
        du = facade(b, 'front', x0, x1, fl, v, rng, wall=yf, teralis=v.get('teralis', 'rail_black'), boven=0.2)
    for xp in (x0 + 0.06, x1 - 0.06):                 # slim steel posts carrying the overhang
        post(b, xp, y0r + 0.12, 0.03, under(y0r + 0.12, y0r, yb + 0.12, zf, zb, 0.08), 'rail_black', r=0.04)
    back_side(b, v, rng, x0, x1, yb, hbk, hbk, annex_frac=0.5)
    motor(b, x0 + 0.55 if du > 0 else x1 - 0.55, 0.95, MOTORS[rng.randrange(len(MOTORS))], z0=0.03)
    if v.get('units', 1) == 2:
        pxs = [(x0 + x1) / 2 - 0.5 + 0.5 * k for k in range(3)]
    else:
        pxs = [(x1 - 0.3 - k * 0.45) if du > 0 else (x0 + 0.3 + k * 0.45) for k in range(rng.randint(2, 4))]
    for k, px in enumerate(pxs):
        pot(b, px, 0.35, 0.03, s=0.75 + 0.25 * rng.random(), plant='plant_dark' if k % 2 else 'plant')
    if v.get('bird', True):                          # hanging bird cage under the eave
        cx = (x1 - 0.5) if du < 0 else (x0 + 0.5)
        b.box(cx - 0.01, yf - 0.6, 1.95, cx + 0.01, yf - 0.58, under(yf - 0.59, y0r, yb + 0.12, zf, zb, 0.08), 'rail_black',
              skip=('bottom', 'top'))
        b.cyl(cx, yf - 0.59, 1.55, 1.95, 0.18, v.get('cage', '#e9d9a8'), seg=6)


def k_emper(b, v, rng):
    """Old-style house: hip roof + a lower full-width emper on wooden posts, raised terrace with langkan."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 3.15)
    fy, t = v.get('yard', 0.9), v.get('terrace', 2.1)
    yf, yb = fy + t, D - v.get('back', 2.4)
    fl = 0.4                                            # raised floor
    yard(b, v.get('yardc', SOIL))
    b.box(x0, fy, 0, x1, yf, fl, 'tile_floor')
    body(b, x0, x1, yf, yb, hw, v['wall'], plinth='concrete_dark')
    facade(b, 'front', x0, x1, fl, v, rng, wall=yf, door_at=0.5, door_w=1.3, leaves=2, win_h=1.4, boven=0.25, maxwin=1.2)
    side_windows(b, v, x0, x1, yf, yb)
    rise = min(v.get('rise', 1.45), HMAX - hw - TH - CAP)
    p = hip(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'])
    eave = hw - p * OV
    # emper roof: attached under the main eave, sloping down to the posts
    ez0 = eave - 0.12
    ez1 = 2.5
    shed(b, x0 - 0.3, x1 + 0.3, fy - 0.3, yf + 0.03, ez1, ez0, v.get('eroof', v['roof']), fascia=v['fascia'], edges=(1, 1, 0, 1),
         ncourses=3)
    wood = v.get('wood', 'frame_brown')
    n = 4 if x1 - x0 > 6.5 else 3
    xs = [x0 + 0.12 + (x1 - x0 - 0.24) * k / (n - 1) for k in range(n)]
    for xc in xs:
        post(b, xc, fy + 0.12, fl, under(fy + 0.12, fy - 0.3, yf + 0.03, ez1, ez0, 0.08), wood, r=0.08)
    zbeam = under(fy + 0.06, fy - 0.3, yf + 0.03, ez1, ez0, 0.08)
    b.box(x0, fy + 0.06, zbeam - 0.16, x1, fy + 0.18, zbeam, wood, skip=('bottom', 'top'))
    # langkan (wooden railing) between the posts, open at the stairs in the middle
    xm = (x0 + x1) / 2
    for a, c in zip(xs, xs[1:]):
        a, c = a + 0.08, c - 0.08
        if a < xm < c:
            segs = ((a, xm - 0.6), (xm + 0.6, c))
        else:
            segs = ((a, c),)
        for sa, sc in segs:
            if sc - sa < 0.3:
                continue
            b.box(sa, fy + 0.08, fl + 0.72, sc, fy + 0.16, fl + 0.8, wood, skip=('bottom', 'left', 'right'))
            k = int((sc - sa) / 0.2)
            for i in range(k):
                u = sa + (sc - sa) * (i + 0.5) / k
                b.box(u - 0.025, fy + 0.09, fl, u + 0.025, fy + 0.15, fl + 0.72, wood, skip=('bottom', 'top', 'left', 'right'))
    for k in range(2):                                   # stairs
        b.box(xm - 0.6, fy - 0.3 * (k + 1), 0, xm + 0.6, fy - 0.3 * k, fl * (2 - k) / 3, 'tile_floor')
    back_side(b, v, rng, x0, x1, yb, hw, eave, plinth='concrete_dark')
    # hedge instead of a fence, pots along the terrace
    for a, c in ((-W / 2 + 0.45, xm - 0.95), (xm + 0.95, W / 2 - 0.45)):
        hedge(b, a, c, 0.47, r=0.4, h=0.8)
    for k in range(rng.randint(3, 5)):
        pot(b, x0 + 0.5 + k * 0.6, fy + 0.45, fl, s=0.8, plant='plant' if k % 2 else 'plant_dark')
    bench(b, x1 - 1.7, x1 - 0.35, yf - 0.55, z0=fl, color=wood)


def k_gerbang(b, v, rng):
    """Hip-roof house with a small front gable porch on two columns, lawn with a tree, besi pagar + sliding gate."""
    W, D = b.W, b.D
    si = OV + 0.08
    x0, x1 = -W / 2 + si, W / 2 - si
    hw = v.get('hw', 3.2)
    yf = v.get('yard', 3.8)
    yb = D - v.get('back', 2.5)
    yard(b, v.get('yardc', 'concrete'))
    body(b, x0, x1, yf, yb, hw, v['wall'])
    rise = min(v.get('rise', 1.4), HMAX - hw - TH - CAP)
    p = hip(b, x0, x1, yf, yb, hw, rise, v['roof'], v['fascia'])
    eave = hw - p * OV
    # porch: gable roof (ridge towards the street) below the main eave
    pw = v.get('pw', 2.8)
    pc = x0 + (x1 - x0) * v.get('pat', 0.35)
    px0, px1 = pc - pw / 2, pc + pw / 2
    py0 = yf - 1.9
    pz = eave - 0.12 - 0.65
    b.box(px0, py0, 0, px1, yf, 0.18, 'tile_floor')
    for xc in (px0 + 0.14, px1 - 0.14):
        post(b, xc, py0 + 0.14, 0.18, pz - 0.28, v.get('col', 'column'), r=0.13)
    b.box(px0, py0 + 0.02, pz - 0.28, px1, py0 + 0.28, pz, v.get('col', 'column'), skip=('bottom', 'top'))
    for xs in (px0, px1 - 0.2):
        b.box(xs, py0 + 0.28, pz - 0.28, xs + 0.2, yf, pz, v.get('col', 'column'), skip=('bottom', 'top', 'front', 'back'))
    gable(b, px0, px1, py0, yf - 0.02, pz, 0.62, v['proof'], v['fascia'], v.get('pgable', 'trim_white'), ridge='y',
          over=0.3, over_end=0.3, ends=(True, False), end_over=(0.3, 0.0), ncourses=2)
    b.decal('front', pc - 0.3, pc + 0.3, pz + 0.12, pz + 0.36, v.get('accent', 'trim_dark'), off=0.02, wall=py0)
    facade(b, 'front', x0, x1, 0.18, v, rng, wall=yf, door_at=(pc - x0) / (x1 - x0), door_w=1.2, leaves=2,
           teralis=v.get('teralis'), maxwin=1.6)
    side_windows(b, v, x0, x1, yf, yb)
    back_side(b, v, rng, x0, x1, yb, hw, eave)
    # driveway to the porch, lawn with a tree and bushes on the other side
    b.box(px0 - 0.1, 0.05, 0, px1 + 0.1, py0, 0.06, 'concrete_dark')
    lx0, lx1 = px1 + 0.2, W / 2 - 0.2
    if lx1 - lx0 > 1.5:
        b.box(lx0, 0.3, 0, lx1, yf - 0.3, 0.07, GRASS)
        tree(b, lx1 - 1.0, 1.35, h=3.3, r=0.95, color=v.get('treec', 'plant'))
        for k in range(int((lx1 - lx0 - 2.0) / 0.8)):
            bush(b, lx0 + 0.4 + k * 0.8, yf - 0.6, 0.07, 0.32, 0.55, 'plant_dark' if k % 2 else 'plant')
    ox0 = -W / 2 + 0.25
    if px0 - 0.2 - ox0 > 1.2:
        b.box(ox0, 0.3, 0, px0 - 0.2, yf - 0.3, 0.07, GRASS)
        pot(b, (ox0 + px0 - 0.2) / 2, 1.2, 0.07, s=1.1)
    motor(b, pc + 0.4, 1.02, MOTORS[rng.randrange(len(MOTORS))], z0=0.06)
    front_fence(b, v, -W / 2 + 0.03, W / 2 - 0.03, (px0 - 0.25, px1 + 0.25))


def k_besar(b, v, rng):
    """Wide house: L-shaped hip roof (front wing), carport, garden, tembok+besi pagar."""
    W, D = b.W, b.D
    si = OV + 0.08
    cw = v.get('cw', 3.0)
    left = v.get('cleft', False)
    if left:
        cx0, cx1 = -W / 2 + 0.05, -W / 2 + cw
        x0, x1 = cx1, W / 2 - si
    else:
        cx0, cx1 = W / 2 - cw, W / 2 - 0.05
        x0, x1 = -W / 2 + si, cx0
    hw = v.get('hw', 3.1)
    ym0 = v.get('yard', 4.0)
    yb = D - v.get('back', 2.5)
    ww = v.get('ww', 3.6)
    # wing sits inside the main body's length (not flush with its hip end) so the two hips meet cleanly
    xw0, xw1 = (x1 - ww - 0.9, x1 - 0.9) if left else (x0 + 0.9, x0 + 0.9 + ww)
    fyw = ym0 - v.get('wing', 2.4)
    yard(b, v.get('yardc', 'concrete'))
    body(b, x0, x1, ym0, yb, hw, v['wall'])
    body(b, xw0, xw1, fyw, ym0, hw, v['wall'], skip=('back',))
    rise = min(v.get('rise', 1.45), HMAX - hw - TH - CAP)
    p = hip(b, x0, x1, ym0, yb, hw, rise, v['roof'], v['fascia'])
    # wing: hip roof with the same pitch, clipped on the valley lines
    wing_hip(b, xw0, xw1, fyw, ym0, hw, p, v['roof'], v['fascia'])
    eave = hw - p * OV
    window(b, 'front', (xw0 + xw1) / 2, 0.95, min(2.0, ww - 1.0), 1.35, v['frame'], wall=fyw, bars=3, boven=0.25)
    for side, wx in (('left', xw0), ('right', xw1)):
        window(b, side, (fyw + ym0) / 2, 1.0, 0.8, 1.1, v['frame'], wall=wx)
    # terrace beside the wing (under the main eave) with the front door
    ta, tc = (xw1, x1) if not left else (x0, xw0)
    b.box(ta, ym0 - 1.5, 0, tc, ym0, 0.18, 'tile_floor')
    du = facade(b, 'front', ta, tc, 0.18, v, rng, wall=ym0, door_at=0.3 if not left else 0.7, door_w=1.2, leaves=2, maxwin=1.4)
    oa, oc = (x0, xw0) if not left else (xw1, x1)
    if oc - oa > 1.4:
        window(b, 'front', (oa + oc) / 2, 0.95, min(1.2, oc - oa - 0.5), 1.3, v['frame'], wall=ym0, bars=2)
    side_windows(b, v, x0, x1, ym0, yb, sides=('left',) if not left else ('right',))
    # carport: flat-ish polycarbonate roof along the house side
    cy1 = min(yb - 0.3, ym0 + 3.0)
    b.box(cx0, 0.0, 0, cx1, cy1, 0.06, 'concrete_dark')
    zb, zf = min(2.8, eave - 0.12), 2.55
    ox = cx1 - 0.12 if not left else cx0 + 0.12
    ix = cx0 + 0.08 if not left else cx1 - 0.08
    for (px, py) in ((ox, 0.5), (ox, cy1 - 0.2), (ix, 0.5)):
        post(b, px, py, 0.06, under(py, 0.35, cy1, zf, zb, 0.06), 'rail_black', r=0.05)
    croof = v.get('croof', '#6f93ad')
    shed(b, cx0, cx1, 0.35, cy1, zf, zb, croof, fascia='rail_black', thick=0.06)
    rib_decals(b, cx0, cx1, 0.35, cy1, zf, zb, shade(croof, 0.72), n=max(3, int((cx1 - cx0) / 0.7)))
    mx = (cx0 + cx1) / 2
    for dxm, ym, ci in v.get('cmotors', [(-0.5, 2.0, None), (0.5, 2.6, None)]):
        motor(b, mx + dxm, ym, MOTORS[rng.randrange(len(MOTORS))] if ci is None else MOTORS[ci], z0=0.06)
    back_side(b, v, rng, x0, x1, yb, hw, eave, left=left, annex_frac=0.4)
    # garden in front of the wing with a tree; fence with a gap at the carport
    ga, gc = (-W / 2 + 0.25, cx0 - 0.3) if not left else (cx1 + 0.3, W / 2 - 0.25)
    b.box(ga, 0.3, 0, gc, fyw - 0.25, 0.07, GRASS)
    tree(b, ga + 1.0 if not left else gc - 1.0, 1.4, h=3.5, r=1.0, color=v.get('treec', 'plant'))
    for k in range(int((gc - ga - 2.4) / 1.6)):
        bush(b, (ga + 2.2 + k * 1.6) if not left else (gc - 2.2 - k * 1.6), 0.7, 0.07, 0.45, 0.7, 'plant_dark' if k % 2 else 'plant')
    fa, fc = (-W / 2 + 0.03, cx0 - 0.05) if not left else (cx1 + 0.05, W / 2 - 0.03)
    gap = (du - 0.5, du + 0.5) if fa < du < fc else None
    front_fence(b, v, fa, fc, gap, h=1.4, hl=0.7, gate=None)


KINDS = {'limasan': k_limasan, 'pelana': k_pelana, 'teras': k_teras, 'carport': k_carport, 'jemuran': k_jemuran,
         'loteng': k_loteng, 'siku': k_siku, 'petak': k_petak, 'emper': k_emper, 'gerbang': k_gerbang, 'besar': k_besar}


def variants():
    """Wall / roof colours here are what the player sees on the sunlit face in game (build() runs them through lit()).
    bk['layout'] picks the back: 'annex' (dapur lean-to), 'dak' (flat cor-dak annex with the toren on it) or
    'teras' (no annex, covered back terrace on posts); bk['tile'] gives an annex a genteng roof."""
    V = [
        dict(kind='petak', w=5.5, d=8.5, wall='#c6dc68', roof='#6a9ccc', fascia='trim_white', frame='window_frame',
             door='door_dark', tank='tank_orange', annex_roof='#a9b0b4', annex_wall='#e6dcc8',
             bk=dict(toren='yard', jem='full', zl=1.6, extra='pots')),
        dict(kind='loteng', mode='room', roles=['front', 'fill'], w=6.0, d=10.0, wall='#f0ad86', roof='roof_blue',
             lroof='#5f8a6a', dish=True, frame='window_frame', fence='rail_black', fascia='trim_white', lwall='#f2e2b4',
             tank='tank_blue', lleft=True, annex_roof='#b85a3e', coat='#a0705c', fwall='#f0ad86', pillar='#f6f2ea',
             fh=1.1, fhl=0.6, fstep=0.26, bk=dict(jem='short', zl=1.6, tile=True)),
        dict(kind='pelana', w=6.5, d=10.0, wall='#94bde6', roof='#6a3a2a', fascia='trim_white', accent='#f4f0e6',
             frame='frame_brown', fwall='#eadcb2', pillar='#eadcb2', gatec='#35523f', kanopi='#8fc8bf', teralis='rail_white',
             tank='tank_white', dakc='#a8a39a', bk=dict(layout='dak', jem='full', zl=1.85, ac=True)),
        dict(kind='limasan', w=7.0, d=9.5, wall='#8fd4ac', roof='#cc6a3c', fascia='trim_white',
             frame='window_frame', fence='rail_black', teralis='rail_white', annex_roof='#b4bbbf', tank='tank_orange',
             fwall=STONE, pillar=STONE, fh=1.3, fhl=0.4,
             bk=dict(layout='teras', toren='yard', jem='short', zl=1.7, extra='sumur', postc='column')),
        dict(kind='jemuran', w=7.5, d=9.5, wall='#f0c850', roof='#b8352c', fascia='frame_brown', accent='#f2e4c0',
             frame='frame_brown', fence='rail_green', sleft=False, yardc=SOIL, annex_roof='#5b82ae', tank='tank_blue',
             fwall='#dcc39c', pillar='#dcc39c', fh=1.05, fhl=0.6,
             bk=dict(toren='annex', jem='none', extra='pisang', ac=True)),
        dict(kind='emper', w=8.0, d=10.5, wall='#eeebe3', roof='#a0684a', eroof='#8a5a45', fascia='#3d6b4a',
             frame='#3d6b4a', door='#4f7a55', wood='frame_brown', annex_roof='#9c5a40', tank='#8a8f96',
             annex_wall='#d8cfbe', bk=dict(toren='yard', jem='full', zl=1.55, extra='sumur', tile=True)),
        dict(kind='carport', w=8.5, d=10.0, wall='#eb9cac', roof='#76808a', fascia='trim_white', frame='window_frame',
             fence='rail_black', cleft=True, croof='#5f9aa8', roofk='hip', fstyle='h', tank='tank_orange',
             fwall='#eb9cac', pillar='#f6f2ea', fh=1.5, fhl=0.3, cgate='panel', cgatec='#4a5d6b', dakc='#b0aba2',
             cmotors=[(0.35, 2.1, 2)], cprops=[('pot', -0.75, 1.0), ('pot', -0.75, 2.6)],
             bk=dict(layout='dak', jem='short', zl=1.8, ac=True, extra='pots')),
        dict(kind='teras', w=9.0, d=10.5, wall='#b8a2e0', roof='roof_green', fascia='trim_white', accent='#f4f0e6',
             frame='window_frame', fence='rail_white', fwall='#b8a2e0', col='trim_white', annex_roof='#5b82ae',
             tank='tank_blue', bk=dict(toren='yard', jem='full', zl=1.8, ac=True)),
        dict(kind='siku', w=9.5, d=11.0, wall='#f0dcaa', roof='#86302a', fascia='frame_brown', accent='#d8bc90',
             frame='frame_brown', fence='rail_black', wleft=True, fwall='#d98a6a', pillar='#d98a6a',
             fh=1.25, fhl=0.8, annex_roof='#a9b0b4', tank='tank_white',
             bk=dict(layout='teras', toren='yard', jem='full', zl=1.75, extra='motor')),
        dict(kind='loteng', mode='dak', w=10.0, d=10.0, wall='#5aa8a0', roof='roof_red', rstyle='h', fstyle='h',
             frame='window_frame', fence='rail_white', fascia='trim_white', parapet='#f0eee6', tank='tank_orange',
             lleft=False, dish=True, dak='#a39d93', coat='#8a8f94', annex_roof='#b85a3e', fwall='#5aa8a0',
             pillar='#f0eee6', fh=1.2, gate='panel', gatec='#4a5d6b', bk=dict(jem='none', tile=True)),
        dict(kind='gerbang', w=11.0, d=11.5, wall='#d8b684', roof='roof_blue', proof='roof_blue', fascia='trim_white',
             frame='frame_black', fence='rail_black', fwall='#c9c9c4', pillar='#f0eee6', fh=1.5, pgable='trim_white',
             accent='trim_dark', door='door_dark', fstyle='h', fslat=0.3, tank='tank_blue', dakc='#a8a39a', courses=4,
             bk=dict(layout='dak', jem='short', zl=1.9, extra='pisang', ac=True)),
        dict(kind='carport', w=12.0, d=11.0, wall='#eb9a50', roof='#4a3a34', fascia='trim_white', frame='window_frame',
             fence='rail_green', cleft=False, cw=3.3, croof='#a9b0b4', roofk='gable', yard=2.2, annex_roof='#b85a3e',
             teralis=None, tank='tank_white', fwall=STONE, pillar=STONE, fh=1.2, fhl=0.35, courses=4,
             cmotors=[(-0.55, 2.2, 3)], cprops=[('jerigen', 0.75, 1.2), ('jerigen', 0.9, 2.6)], fstep=0.25,
             jerc='#3d7fc4',
             bk=dict(toren='yard', jem='full', zl=1.65, tile=True)),
        dict(kind='besar', w=14.0, d=12.0, wall='#cfcfca', roof='#5a5654', fascia='frame_brown',
             frame='frame_brown', fence='rail_black', pillar='#d98a6a', fwall='#d98a6a', door='door_dark',
             fstyle='h', annex_roof='#a9b0b4', tank='tank_orange', courses=4, cmotors=[(-0.55, 1.7, 5), (0.55, 2.9, 2)],
             bk=dict(layout='teras', toren='yard', jem='short', zl=1.75, ac=True, postc='rail_black', tpots=1)),
        dict(kind='petak', w=7.0, d=9.0, units=2, wall='#84bc70', roof='#bdbab2', fascia='trim_white',
             frame='window_frame', door='door_dark', door2='#3f6b8a', tank='tank_blue', annex_roof='#5b82ae',
             teralis='rail_white', bk=dict(layout='teras', toren='yard', jem='full', zl=1.5, extra='sumur')),
        dict(kind='jemuran', w=6.0, d=9.0, roofk='hip', sw=1.8, sleft=True, wall='#7aa2dc', roof='#3d4a52',
             fascia='trim_white', accent='#f4f0e6', frame='window_frame', fence='rail_black', yardc='concrete',
             tank='tank_orange', treec='plant_dark', fwall='#f0eee6', pillar='#7aa2dc', dakc='#a8a39a',
             fh=1.1, bk=dict(layout='dak', jem='none', extra='pots')),
    ]
    return V


def build(b, v, rng):
    v = dict(v)
    for k in WALL_KEYS:
        if v.get(k):
            v[k] = lit(v[k], GAIN_WALL)
    for k in ROOF_KEYS:
        if v.get(k):
            v[k] = lit(v[k], GAIN_ROOF)
    v.setdefault('annex_wall', lit('#ece6d8'))
    COURSES[0] = v.get('courses', 5)
    KINDS[v['kind']](b, v, rng)

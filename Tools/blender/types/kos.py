"""Kos-kosan / rumah susun sederhana: a 3-4 storey rooming house. A row of small rooms (door + window
each) opens onto an open gallery corridor with a railing on every floor, bright laundry hangs over the
railings, a concrete switch-back stair sits in an open bay at one end, and the roof carries water tanks
(toren), clothes lines, AC units and sometimes a small stair house. The corridor faces the street on some
variants; on others the rooms show their windows (with sun shades and AC units) to the street and the
corridor + stair face the back yard (those get a street door with a small canopy in the stair bay).

Every variant stays <= 12 m tall (the game's 'front' lots) and has its own roof layout: the flat roofs
place their props from a per-variant `items` list (toren row / toren on a steel stand, short clothes-line
segments along or across the street, AC condensers, dish, antenna, zinc lean-to shed, polycarbonate
canopy, pots); the pitched roofs have a flat dak strip over the stair bay with a parapet, a pipe railing
or a zinc lean-to over the toren.

Internal frame: t = depth measured from the CORRIDOR side of the building (t = 0 is the corridor edge,
t = FW the opposite facade). `Y(t)` maps it to the world y of common.py (y = 0 street front)."""
import math

from common import PALETTE

TYPE = 'kos'
ROLES = ['front']

CLOTH = ['#e25d7a', '#5db0e2', '#f2d24a', '#f6f4ee', '#ef7d2d', '#8cc47e', '#b86bd6', '#d8433a',
         '#3d6fb6', '#f29ac0', '#46b3a0', '#ffffff']

SW = 2.35      # stair bay width: outer wall 0.2 + lane 1.0 + spine 0.15 + lane 1.0
CD = 1.5       # corridor depth
N_STEP = 6     # steps per half flight
TREAD = 0.28
LAND = 1.0     # half-landing depth
BH = 0.3       # floor slab / beam band
HMAX = 12.0    # 'front' role height limit
PIPE = '#6f6a64'
VENT = '#6b645c'


def variants():
    V = []

    def add(**kw):
        V.append(kw)

    # items for flat roofs, (u, v) = fractions of the deck: u 0 = left .. 1 = right, v 0 = street .. 1 = back
    #   ('tanks', u, v, 'low'|'stand', 'x'|'y')    ('lines', 'x'|'y', u, v, length, count)
    #   ('ac', u, v, count)  ('dish', u, v)  ('antenna', u, v)  ('shed', u, v, w, d)  ('pots', u, v, count)
    #   ('canopy', u0, u1, v0, v1)  (a short clothes line hangs under it)

    # 0: narrow, corridor to the street, solid balustrades, fenced front yard, flat roof + stair house,
    #    green waterproofed deck, both torens on a tall steel stand in the back corner
    add(w=8.0, d=10.0, n=3, fh=3.0, corr='front', stair='right', roof='flat', hut='flat', rail='wall',
        wall='wall_mint', accent='#2f7f78', trim='trim_white', railc='trim_white', floor='tile_floor',
        door='door_wood', frame='window_frame', deck='#6f8f6a', parc='wall_mint', fy=1.0, fence='rail_black',
        tanks=['tank_orange', 'tank_blue'],
        items=[('tanks', 0.0, 1.0, 'stand', 'x'), ('lines', 'x', 0.28, 0.1, 3.0, 2), ('ac', 1.0, 1.0, 1),
               ('dish', 1.0, 0.62)])
    # 1: windows to the street, 4 floors, low blue hip roof, fenced front yard, entrance door,
    #    white sun shades, parapeted dak strip
    add(w=10.0, d=11.0, n=4, fh=2.75, corr='back', stair='left', roof='hip', roofc='roof_blue', rise=0.8,
        rail='pipe', wall='wall_cream', accent='wall_terracotta', trim='trim_white', railc='rail_black',
        floor='tile_floor', door='door_dark', frame='frame_brown', fy=1.3, ground='gate',
        tanks=['tank_blue'], grill=True, fence='rail_black', shade='cont', shadec='trim_white',
        strip='parapet', strip_near='ac', deck='#8f8b84')
    # 2: wide, corridor to the street, steel pipe railings, terracotta hip roof, fenced yard
    add(w=12.0, d=10.5, n=3, fh=3.0, corr='front', stair='left', roof='hip', roofc='roof_terracotta',
        rise=1.7, rail='pipe', wall='wall_peach', accent='trim_white', trim='column', railc='rail_black',
        floor='tile_floor', door='#e9e4d8', frame='frame_brown', fy=1.5, fence='rail_black',
        tanks=['tank_orange'], strip='pipe', strip_near='line', deck='#8f8b84')
    # 3: tall + narrow, corridor to the street, half-wall + rail, flat roof: clothes lines across the deck,
    #    torens in the front corner, pots
    add(w=9.0, d=11.0, n=4, fh=2.75, corr='front', stair='right', roof='flat', hut=None,
        rail='half', wall='wall_sky', accent='#3f6fa8', trim='trim_white', railc='rail_green',
        floor='concrete', door='door_wood', frame='window_frame', deck='#6a86a6', parc='wall_sky', ph=0.7,
        tanks=['tank_blue', 'tank_blue'], gfence=True,
        items=[('tanks', 0.0, 0.0, 'low', 'x'), ('lines', 'y', 0.45, 0.55, 3.4, 2), ('ac', 1.0, 1.0, 1),
               ('dish', 0.0, 0.93), ('pots', 1.0, 0.0, 3)])
    # 4: windows to the street, warung at the ground floor, flat roof + gabled stair house, red-oxide deck,
    #    zinc laundry shed, torens along the side parapet
    add(w=11.0, d=12.0, n=3, fh=3.0, corr='back', stair='right', roof='flat', hut='gable', hutroof='roof_zinc',
        hh=2.3, hutrise=0.55,
        rail='wall', wall='wall_yellow', accent='#4a4440', trim='trim_white', railc='wall_white',
        floor='tile_floor', door='door_wood', frame='frame_black', deck='#86503f', parc='wall_yellow',
        tanks=['tank_orange', 'tank_orange'], ground='shop', shade='cont', shadec='wall_yellow',
        items=[('tanks', 0.0, 0.0, 'low', 'y'), ('shed', 1.0, 0.0, 2.4, 1.8), ('lines', 'x', 0.3, 0.74, 3.0, 2),
               ('ac', 0.52, 1.0, 2), ('antenna', 0.45, 0.4)])
    # 5: 4 floors, corridor to the street, white rail on a half wall, low grey hip roof, railed dak strip
    add(w=11.5, d=10.0, n=4, fh=2.75, corr='front', stair='right', roof='hip', roofc='roof_grey', rise=0.8,
        rail='half', wall='wall_pink', accent='#b2536a', trim='trim_white', railc='rail_white',
        floor='tile_floor', door='door_dark', frame='window_frame', tanks=['tank_white'], gfence=True,
        strip='pipe', strip_near='ac', deck='#c9c5bd')
    # 6: big block, corridor to the street, orange balustrades, gated ground floor, flat roof with a
    #    polycarbonate canopy over the drying area, light concrete deck
    add(w=10.5, d=12.0, n=3, fh=3.1, corr='front', stair='left', roof='flat', hut=None,
        rail='wall', wall='wall_lilac', accent='#e0873a', trim='trim_white', railc='#e0873a', floor='concrete',
        door='#e9e4d8', frame='frame_black', deck='#c9c5bd', parc='wall_lilac', ph=0.8,
        tanks=['tank_orange', 'tank_blue'], gfence=True,
        items=[('canopy', 0.02, 0.5, 0.25, 0.62, '#3f86b8'), ('tanks', 1.0, 1.0, 'low', 'x'), ('ac', 0.0, 1.0, 2),
               ('lines', 'y', 0.8, 0.38, 3.4, 1), ('pots', 0.0, 0.0, 3), ('antenna', 0.5, 0.9)])
    # 7: small, windows to the street, red gable roof, green accents, per-window hoods, gated front yard
    #    with a canopy over the street door, zinc lean-to over the toren
    add(w=8.5, d=9.0, n=3, fh=3.0, corr='back', stair='right', roof='gable', roofc='roof_red', rise=1.6,
        rail='pipe', wall='wall_white', accent='#4f9a58', trim='wall_white', railc='rail_green',
        floor='tile_floor', door='door_wood', frame='window_frame', fy=1.2, ground='gate', fence='rail_green',
        canopy_door='awning_green', tanks=['tank_orange'], grill=False, shade='win', shadec='#4f9a58',
        strip='lean', strip_near='pots', deck='#a0493a')
    # 8: mid-width, corridor to the street, cream balustrades, green gable roof, teal walls, gated corridor,
    #    parapeted dak strip
    add(w=9.5, d=10.5, n=3, fh=3.0, corr='front', stair='left', roof='gable', roofc='roof_green', rise=1.7,
        rail='wall', wall='wall_teal', accent='#f2e3bf', trim='#f2e3bf', railc='#f2e3bf', floor='tile_floor',
        door='#3d6fb6', frame='window_frame', tanks=['tank_blue'], laundry=0.7, gfence=True,
        strip='parapet', strip_near='line', deck='#6f8796')
    return V


# ----------------------------------------------------------------------------------------- helpers
def shade(col, f):
    h = PALETTE.get(col, col).lstrip('#')
    return '#' + ''.join('%02x' % max(0, min(255, int(round(int(h[i:i + 2], 16) * f)))) for i in (0, 2, 4))


def _newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


def oface(b, pts, col, hint):
    """Polygon whose winding is flipped if needed so its normal points along `hint`."""
    n = _newell(pts)
    if n[0] * hint[0] + n[1] * hint[1] + n[2] * hint[2] < 0:
        pts = pts[::-1]
    b.face(pts, col)


def _sub(a, c):
    return (a[0] - c[0], a[1] - c[1], a[2] - c[2])


def _cross(a, c):
    return (a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0])


def _unit(a):
    m = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / m, a[1] / m, a[2] / m)


def beam(b, p0, p1, t, col):
    """Thin square-section bar between two arbitrary points (4 sides, no caps): braces, dish arms."""
    d = _unit(_sub(p1, p0))
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = _unit(_cross(d, ref))
    e2 = _cross(d, e1)
    h = t / 2
    for (s1, s2) in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        n = (e1[0] * s1 + e2[0] * s2, e1[1] * s1 + e2[1] * s2, e1[2] * s1 + e2[2] * s2)
        a = (e2[0] * s1 - e1[0] * s2, e2[1] * s1 - e1[1] * s2, e2[2] * s1 - e1[2] * s2)   # along the face
        c0 = [p0[k] + n[k] * h for k in range(3)]
        c1 = [p1[k] + n[k] * h for k in range(3)]
        pts = [tuple(c0[k] - a[k] * h for k in range(3)), tuple(c0[k] + a[k] * h for k in range(3)),
               tuple(c1[k] + a[k] * h for k in range(3)), tuple(c1[k] - a[k] * h for k in range(3))]
        oface(b, pts, col, n)


def cloth(b, axis, a0, a1, c, z0, z1, col, dirs=(-1, 1)):
    """Flat piece of laundry. axis 'x': spans x a0..a1 at y = c; axis 'y': spans y a0..a1 at x = c."""
    if axis == 'x':
        pts = [(a0, c, z0), (a1, c, z0), (a1, c, z1), (a0, c, z1)]
    else:
        pts = [(c, a0, z0), (c, a1, z0), (c, a1, z1), (c, a0, z1)]
    for s in dirs:
        oface(b, pts, col, (0, s, 0) if axis == 'x' else (s, 0, 0))


def shirt(b, axis, ac, c, ztop, col, dirs=(-1, 1), s=1.0):
    """T-shirt silhouette: sleeve band + body, hung from a line."""
    cloth(b, axis, ac - 0.32 * s, ac + 0.32 * s, c, ztop - 0.2 * s, ztop, col, dirs)
    cloth(b, axis, ac - 0.2 * s, ac + 0.2 * s, c, ztop - 0.62 * s, ztop - 0.2 * s, col, dirs)


def clothes_line(b, axis, a0, a1, c, z0, lh, rng):
    """Two posts, a wire and a row of shirts / towels (axis = direction the line runs)."""
    def bx(p0, p1, q0, q1, za, zb, col, skip):
        if axis == 'x':
            b.box(p0, q0, za, p1, q1, zb, col, skip=skip)
        else:
            b.box(q0, p0, za, q1, p1, zb, col, skip=skip)
    for aa in (a0, a1):
        bx(aa - 0.03, aa + 0.03, c - 0.03, c + 0.03, z0, z0 + lh + 0.1, 'metal', ('bottom', 'top'))
    ends = ('left', 'right') if axis == 'x' else ('front', 'back')
    bx(a0, a1, c - 0.015, c + 0.015, z0 + lh + 0.04, z0 + lh + 0.07, 'metal', ('bottom',) + ends)
    zt = z0 + lh + 0.05
    if axis == 'y':
        # a pipe running away from the street carries shirts on hangers, which hang across the pipe and so
        # face the street (seen face-on from the game camera, one behind the other like a clothes rack)
        a = a0 + 0.3
        while a < a1 - 0.25:
            shirt(b, 'x', c, a, zt - 0.06, rng.choice(CLOTH), s=0.85)
            a += rng.choice([0.35, 0.45, 0.55])
        return
    x = a0 + 0.45
    while x < a1 - 0.4:
        col = rng.choice(CLOTH)
        if rng.random() < 0.55:
            shirt(b, axis, x, c, zt, col, s=0.9)
            x += 0.75
        else:
            wdt = rng.choice([0.5, 0.7])
            cloth(b, axis, x - wdt / 2, x + wdt / 2, c, zt - rng.choice([0.55, 0.75]), zt, col)
            x += wdt + 0.25


def toren(b, cx, cy, z0, col, stand=0.3, r=0.5, h=1.05, stand_col='concrete'):
    """Plastic water tank on a small concrete plinth, with a ribbed band and a lid."""
    if stand > 0:
        b.box(cx - r - 0.06, cy - r - 0.06, z0, cx + r + 0.06, cy + r + 0.06, z0 + stand, stand_col)
    zb = z0 + stand
    b.cyl(cx, cy, zb, zb + h, r, col, seg=8)
    b.cyl(cx, cy, zb + h * 0.45, zb + h * 0.55, r + 0.035, col, seg=8, top=False)
    b.box(cx - r * 0.35, cy - r * 0.35, zb + h, cx + r * 0.35, cy + r * 0.35, zb + h + 0.12, col)


def tank_stand(b, x0, y0, x1, y1, z0, h, col='metal'):
    """Steel tower for torens: 4 angle posts, a mid rail on the long sides, one brace each, a platform."""
    for xx in (x0 + 0.05, x1 - 0.05):
        for yy in (y0 + 0.05, y1 - 0.05):
            b.box(xx - 0.05, yy - 0.05, z0, xx + 0.05, yy + 0.05, z0 + h - 0.08, col, skip=('bottom', 'top'))
    zm = z0 + h * 0.45
    for yy in (y0 + 0.05, y1 - 0.05):
        b.box(x0 + 0.1, yy - 0.025, zm, x1 - 0.1, yy + 0.025, zm + 0.05, col, skip=('left', 'right'))
        beam(b, (x0 + 0.1, yy, z0 + 0.05), (x1 - 0.1, yy, zm), 0.04, col)
    b.box(x0, y0, z0 + h - 0.08, x1, y1, z0 + h, col, skip=())


def dish(b, cx, cy, z0, h=0.9, r=0.42, face=-1):
    """Satellite dish on a short pole: a shallow cone (concave side up and towards `face` = +-y), its back in
    light grey, and an LNB arm from the lower rim to a small head in front of the dish."""
    b.box(cx - 0.03, cy - 0.03, z0, cx + 0.03, cy + 0.03, z0 + h, 'metal', skip=('bottom', 'top'))
    n = (0.0, 0.55 * face, 0.835)
    w = (0.0, n[2], -n[1])                                  # in-plane axis (n x u, u = +x)
    apex = (cx, cy, z0 + h)                                 # back centre of the dish, on the pole top
    c = tuple(apex[k] + 0.16 * n[k] for k in range(3))      # centre of the rim
    rim = []
    for i in range(6):
        a = math.radians(30 + 60 * i)                       # i = 4 is the lowest rim point (270 deg)
        rim.append(tuple(c[k] + r * (math.cos(a) * (1.0 if k == 0 else 0.0) + math.sin(a) * w[k]) for k in range(3)))
    for i in range(6):
        tri = [rim[i], rim[(i + 1) % 6], apex]
        oface(b, tri, 'ac_white', n)
        oface(b, tri, '#cfcfc8', (-n[0], -n[1], -n[2]))
    lnb = tuple(c[k] + 0.35 * n[k] for k in range(3))
    beam(b, rim[4], lnb, 0.03, 'metal')
    b.box(lnb[0] - 0.04, lnb[1] - 0.04, lnb[2] - 0.04, lnb[0] + 0.04, lnb[1] + 0.04, lnb[2] + 0.04, 'metal', skip=())


def antenna(b, cx, cy, z0, h=2.4):
    """TV antenna mast with three cross bars."""
    b.box(cx - 0.025, cy - 0.025, z0, cx + 0.025, cy + 0.025, z0 + h, 'metal', skip=('bottom',))
    for i, half in enumerate((0.55, 0.45, 0.35)):
        z = z0 + h - 0.12 - i * 0.28
        b.box(cx - half, cy - 0.015, z, cx + half, cy + 0.015, z + 0.03, 'metal', skip=('bottom', 'left', 'right'))


def pot(b, x, y, z0, leaf='plant'):
    """Square planter with a leafy block (cheap rooftop / terrace greenery)."""
    b.box(x - 0.2, y - 0.2, z0, x + 0.2, y + 0.2, z0 + 0.35, 'pot')
    b.box(x - 0.28, y - 0.28, z0 + 0.35, x + 0.28, y + 0.28, z0 + 0.85, leaf)


ZINC = '#8f999f'
ZINC_RIB = '#6c767d'


def lean_to(b, x0, x1, y0, y1, z0, z_y0, z_y1, col=ZINC, rib=ZINC_RIB, wall_y=None, wall_x=None):
    """Zinc lean-to on 4 posts: corrugated roof slab from z_y0 (at y0) to z_y1 (at y1) with ribs running down
    the slope; optional zinc sheet walls along the edge y = wall_y and/or x = wall_x."""
    def zr(y):
        return z_y0 + (z_y1 - z_y0) * (y - y0) / (y1 - y0)
    for xx in (x0 + 0.08, x1 - 0.08):
        for yy in (y0 + 0.08, y1 - 0.08):
            b.box(xx - 0.04, yy - 0.04, z0, xx + 0.04, yy + 0.04, zr(yy) - 0.005, 'metal', skip=('bottom', 'top'))
    th = 0.06
    b.roof_shed(x0, x1, y0, y1, z_y0, z_y1, col, over=0.0, thick=th)
    nrib = max(2, int(round((x1 - x0) / 0.5)))
    for i in range(1, nrib):
        xr = x0 + (x1 - x0) * i / nrib
        oface(b, [(xr - 0.03, y0, z_y0 + th + 0.012), (xr + 0.03, y0, z_y0 + th + 0.012),
                  (xr + 0.03, y1, z_y1 + th + 0.012), (xr - 0.03, y1, z_y1 + th + 0.012)], rib, (0, 0, 1))
    wc = shade(col, 0.9)
    if wall_y is not None:        # zinc sheet wall under the edge y = wall_y
        ya, yb = (wall_y, wall_y + 0.05) if wall_y < (y0 + y1) / 2 else (wall_y - 0.05, wall_y)
        b.box(x0 + 0.12, ya, z0, x1 - 0.12, yb, min(zr(ya), zr(yb)) - 0.01, wc, skip=('bottom', 'top'))
    if wall_x is not None:        # zinc sheet wall under the edge x = wall_x (top follows the slope)
        xa, xb = (wall_x, wall_x + 0.05) if wall_x < (x0 + x1) / 2 else (wall_x - 0.05, wall_x)
        ya, yb = y0 + 0.12, y1 - 0.12
        za_, zb_ = zr(ya) - 0.01, zr(yb) - 0.01
        for xe, sx in ((xa, -1), (xb, 1)):
            oface(b, [(xe, ya, z0), (xe, yb, z0), (xe, yb, zb_), (xe, ya, za_)], wc, (sx, 0, 0))
        for ye, sy, ze in ((ya, -1, za_), (yb, 1, zb_)):
            oface(b, [(xa, ye, z0), (xb, ye, z0), (xb, ye, ze), (xa, ye, ze)], wc, (0, sy, 0))


def cap(b, p, q, col, w=0.09, h=0.05):
    """Ridge / hip cap (bubungan): a shallow two-face ^ along the convex roof line p -> q. It makes low-pitch
    roofs read as roofs (the ink shader skips edges flatter than 25 deg) and hides dashed ridge lines."""
    d = _sub(q, p)
    e = _unit(_cross(d, (0.0, 0.0, 1.0)))
    up = (0.0, 0.0, h)
    pa = tuple(p[k] - e[k] * w for k in range(3)); qa = tuple(q[k] - e[k] * w for k in range(3))
    pb = tuple(p[k] + e[k] * w for k in range(3)); qb = tuple(q[k] + e[k] * w for k in range(3))
    pt = tuple(p[k] + up[k] for k in range(3)); qt = tuple(q[k] + up[k] for k in range(3))
    oface(b, [pa, qa, qt, pt], col, (-e[0], -e[1], 1.0))
    oface(b, [pt, qt, qb, pb], col, (e[0], e[1], 1.0))


def hip_caps(b, x0, x1, y0, y1, z0, rise, col, thick=0.12):
    """Caps on the hips and ridge of common.roof_hip(x0 - over .. x1 + over, ...) given its OUTER extents."""
    w, d = x1 - x0, y1 - y0
    ym, xm = (y0 + y1) / 2, (x0 + x1) / 2
    zt, ze = z0 + rise + thick, z0 + thick
    if w >= d:
        r0, r1 = (x0 + d / 2, ym, zt), (x1 - d / 2, ym, zt)
        ends = {(x0, y0): r0, (x0, y1): r0, (x1, y0): r1, (x1, y1): r1}
    else:
        r0, r1 = (xm, y0 + w / 2, zt), (xm, y1 - w / 2, zt)
        ends = {(x0, y0): r0, (x1, y0): r0, (x0, y1): r1, (x1, y1): r1}
    for (cx, cy), r in ends.items():
        f = 0.16 / math.hypot(r[0] - cx, r[1] - cy)      # start a little up the hip so the cap stays in the lot
        cap(b, (cx + (r[0] - cx) * f, cy + (r[1] - cy) * f, ze + (r[2] - ze) * f), r, col)
    if abs(r1[0] - r0[0]) + abs(r1[1] - r0[1]) > 0.05:
        cap(b, r0, r1, col)


def gable_roof(b, x0, x1, ylo, yhi, z0, rise, col, gcol, thick=0.14, vent=None):
    """Pitched roof with the ridge running front-to-back and the gable walls flush with the front and
    back facades (no overhang, so it stays inside the lot). Built as one closed shell: two slopes sharing
    the ridge, eave edges, and at each gable end a wall triangle plus the roof-thickness strips."""
    xm = (x0 + x1) / 2
    zt = z0 + rise + thick
    for xe, sx in ((x0, -1), (x1, 1)):
        oface(b, [(xe, ylo, z0 + thick), (xm, ylo, zt), (xm, yhi, zt), (xe, yhi, z0 + thick)], col, (sx * rise, 0, abs(xm - xe)))
        oface(b, [(xe, ylo, z0), (xe, yhi, z0), (xe, yhi, z0 + thick), (xe, ylo, z0 + thick)], col, (sx, 0, 0))
    for yy, s in ((ylo, -1), (yhi, 1)):
        oface(b, [(x0, yy, z0), (x1, yy, z0), (xm, yy, z0 + rise)], gcol, (0, s, 0))
        for xe in (x0, x1):
            oface(b, [(xe, yy, z0), (xm, yy, z0 + rise), (xm, yy, zt), (xe, yy, z0 + thick)], col, (0, s, 0))
        if vent:   # small ventilation grille in the gable
            w = min(0.5, (x1 - x0) * 0.08)
            oface(b, [(xm - w, yy + 0.02 * s, z0 + rise * 0.3), (xm + w, yy + 0.02 * s, z0 + rise * 0.3),
                      (xm + w, yy + 0.02 * s, z0 + rise * 0.3 + 0.35), (xm - w, yy + 0.02 * s, z0 + rise * 0.3 + 0.35)],
                  vent, (0, s, 0))


# ------------------------------------------------------------------------------------------- build
def build(b, v, rng):
    W, D = b.W, b.D
    n, fh = v['n'], v['fh']
    H0 = n * fh                 # roof slab top
    TOPB = H0 - BH              # top of the walls (roof slab underside)
    cf = v['corr'] == 'front'
    E = 0.03
    ya, yb = max(v.get('fy', 0.0), E), D - E
    margin = 0.35 if cf else 0.6          # room for AC units / sun shades on the far facade
    FW = (yb - ya) - margin               # t of the far facade
    CS, OS = ('front', 'back') if cf else ('back', 'front')
    XL, XR = -W / 2 + E, W / 2 - E
    sr = v['stair'] == 'right'
    OUT, IN = ('right', 'left') if sr else ('left', 'right')
    sx_out = 1 if sr else -1              # world x direction of the stair-side facade
    rise = fh / 2 / N_STEP
    run = N_STEP * TREAD
    SBD = CD + run + LAND                 # stair bay depth
    wall, acc, trim = v['wall'], v['accent'], v['trim']
    floor, railc = v['floor'], v['railc']
    frame, doorc = v['frame'], v['door']
    hut = v.get('hut') if v['roof'] == 'flat' else None
    LH = 1.6 if n == 3 else 0.85          # clothes line height on the roof (keeps 4 floors <= 12 m)
    TH = 1.0 if n == 3 else 0.85          # toren height

    def S(s):   # x measured from the stair-side edge inwards
        return XR - s if sr else XL + s

    def Q(s):   # x measured from the far edge inwards
        return XL + s if sr else XR - s

    rx0, rx1 = min(Q(0), S(SW)), max(Q(0), S(SW))       # room zone (includes the far end wall)
    sx0, sx1 = min(S(0), S(SW)), max(S(0), S(SW))       # stair zone
    nr = max(2, int(round((rx1 - rx0) / 3.0)))
    rw = (rx1 - rx0) / nr
    rooms = [(rx0 + i * rw, rx0 + (i + 1) * rw) for i in range(nr)]

    def Y(t):
        return ya + t if cf else yb - t

    SWP = {'front': 'back', 'back': 'front'}

    def box(x0, t0, z0, x1, t1, z1, col, skip=('bottom',)):
        b.box(x0, Y(t0), z0, x1, Y(t1), z1, col, skip=tuple(s if cf else SWP.get(s, s) for s in skip))

    def cs_dec(x0, x1, z0, z1, col, tw, off=0.02):
        b.decal(CS, x0, x1, z0, z1, col, off=off, wall=Y(tw))

    def os_dec(x0, x1, z0, z1, col, off=0.02):
        b.decal(OS, x0, x1, z0, z1, col, off=off, wall=Y(FW))

    def side_dec(side, t0, t1, z0, z1, col, off=0.02):
        b.decal(side, Y(t0), Y(t1), z0, z1, col, off=off, wall=XL if side == 'left' else XR)

    def xquad(x, t0, t1, z0, z1, col, nx):
        """Wall quad in the plane x = const, facing world +x (nx = 1) or -x."""
        oface(b, [(x, Y(t0), z0), (x, Y(t1), z0), (x, Y(t1), z1), (x, Y(t0), z1)], col, (nx, 0, 0))

    def tquad(x0, x1, t, z0, z1, col, towards_corridor=True):
        """Wall quad in the plane t = const."""
        s = cdir if towards_corridor else -cdir
        oface(b, [(x0, Y(t), z0), (x1, Y(t), z0), (x1, Y(t), z1), (x0, Y(t), z1)], col, (0, s, 0))

    cdir = -1 if cf else 1      # world y direction the corridor facade faces

    # ------------------------------------------------------------------ structure
    # Built face by face so no edge is shared by three faces (the game's ink shader draws those as cracks):
    # each side facade is one quad over the whole depth, the room block keeps only its corridor wall and
    # far facade, the block behind the stair bay only its far facade and the wall facing the stair bay.
    xquad(S(0), 0, FW, 0, TOPB, wall, sx_out)
    xquad(Q(0), 0, FW, 0, TOPB, wall, -sx_out)
    tquad(min(Q(0.2), S(SW)), max(Q(0.2), S(SW)), CD, 0, TOPB, wall)          # corridor wall
    tquad(XL, XR, FW, 0, TOPB, wall, towards_corridor=False)                  # far facade
    tquad(min(S(0.2), S(SW)), max(S(0.2), S(SW)), SBD, 0, TOPB, wall)         # back wall of the stair bay
    xquad(S(SW), CD, SBD, 0, TOPB, wall, sx_out)                              # room-block end in the stair bay
    # outer wall of the stair bay (lot edge) and the end wall at the far end of the corridor (their outer
    # faces are part of the side quads above)
    box(min(S(0), S(0.2)), 0, 0, max(S(0), S(0.2)), SBD, TOPB, trim, skip=('bottom', 'top', 'back', OUT))
    box(min(Q(0), Q(0.2)), 0, 0, max(Q(0), Q(0.2)), CD, TOPB, trim, skip=('bottom', 'top', 'back', IN))
    # spine wall between the two stair lanes
    box(min(S(1.2), S(1.35)), CD, 0, max(S(1.2), S(1.35)), CD + run, TOPB, trim, skip=('bottom', 'top'))
    # corridor slabs, ground terrace, columns
    cx0, cx1 = XL + 0.2, XR - 0.2
    box(cx0, 0.04, 0, cx1, CD, 0.15, floor, skip=('bottom', 'back', 'left', 'right'))
    for k in range(1, n):
        zf = k * fh
        box(cx0, 0.04, zf - BH, cx1, CD, zf, floor, skip=('back', 'left', 'right'))
        cs_dec(cx0, cx1, zf - BH, zf, acc, 0.04)
    cols = [r[0] for r in rooms[1:]] + [S(SW)]
    for xc in cols:
        box(xc - 0.15, 0.0, 0, xc + 0.15, 0.3, TOPB, trim, skip=('bottom', 'top'))

    # ------------------------------------------------------------------ stairs (switch-back, open bay)
    stc = v.get('stairc', 'concrete')

    def flight(xa, xb, t0, z0, dirn, soffit=True):
        for i in range(N_STEP):
            za, zb = z0 + i * rise, z0 + (i + 1) * rise
            if dirn > 0:
                ta, tb, keep = t0 + i * TREAD, t0 + (i + 1) * TREAD, 'front'
            else:
                ta, tb, keep = t0 - (i + 1) * TREAD, t0 - i * TREAD, 'back'
            box(xa, ta, za, xb, tb, zb, stc, skip=tuple(s for s in ('bottom', 'front', 'back', 'left', 'right') if s != keep))
        if soffit:
            t1, z1 = t0 + dirn * run, z0 + N_STEP * rise
            oface(b, [(xa, Y(t0), z0 - 0.12), (xb, Y(t0), z0 - 0.12), (xb, Y(t1), z1 - 0.12), (xa, Y(t1), z1 - 0.12)], stc, (0, 0, -1))

    laneA = (min(S(1.35), S(SW)), max(S(1.35), S(SW)))
    laneB = (min(S(0.2), S(1.2)), max(S(0.2), S(1.2)))
    runs = n - 1 + (1 if hut else 0)
    for k in range(runs):
        zf, zl = k * fh, k * fh + fh / 2
        flight(laneA[0], laneA[1], CD, zf, +1, soffit=k > 0)
        if k == 0:   # close the solid base under the first flight (seen under the half landing)
            yy = Y(CD + run)
            oface(b, [(laneA[0], yy, 0), (laneA[1], yy, 0), (laneA[1], yy, zl - 0.15), (laneA[0], yy, zl - 0.15)],
                  stc, (0, -cdir, 0))
        flight(laneB[0], laneB[1], CD + run, zl, -1)
        box(min(laneA[0], laneB[0]), CD + run, zl - 0.15, max(laneA[1], laneB[1]), SBD, zl, stc, skip=('back', 'left', 'right'))

    # ------------------------------------------------------------------ railings + laundry
    rt = v['rail']

    def railing(z, x0, x1, h=1.0):
        if rt == 'wall':      # solid balustrade with a coping
            box(x0, 0.08, z, x1, 0.2, z + h, railc, skip=('bottom', 'left', 'right'))
            box(x0, 0.06, z + h, x1, 0.22, z + h + 0.07, acc if railc != acc else trim, skip=('bottom', 'left', 'right'))
            return z + h + 0.07, 0.06
        if rt == 'half':      # low wall + steel rail on short posts
            box(x0, 0.08, z, x1, 0.2, z + 0.5, wall, skip=('bottom', 'left', 'right'))
            box(x0, 0.1, z + h - 0.06, x1, 0.18, z + h, railc, skip=('bottom', 'left', 'right'))
            box(x0, 0.11, z + 0.72, x1, 0.17, z + 0.76, railc, skip=('bottom', 'left', 'right', 'top'))
            npost = max(1, int(round((x1 - x0) / 1.4)))
            for i in range(1, npost):
                xp = x0 + (x1 - x0) * i / npost
                if all(abs(xp - c) > 0.3 for c in cols):
                    box(xp - 0.03, 0.125, z + 0.5, xp + 0.03, 0.155, z + h - 0.06, railc, skip=('bottom', 'top'))
            return z + h, 0.08
        # 'pipe': three horizontal steel tubes on posts
        box(x0, 0.1, z + h - 0.06, x1, 0.18, z + h, railc, skip=('bottom', 'left', 'right'))
        for zz in (0.62, 0.3):
            box(x0, 0.11, z + zz, x1, 0.17, z + zz + 0.04, railc, skip=('bottom', 'left', 'right', 'top'))
        npost = max(1, int(round((x1 - x0) / 1.2)))
        for i in range(0, npost + 1):
            xp = x0 + (x1 - x0) * i / npost
            xp = min(max(xp, x0 + 0.03), x1 - 0.03)
            if all(abs(xp - c) > 0.3 for c in cols):
                box(xp - 0.03, 0.125, z, xp + 0.03, 0.155, z + h - 0.06, railc, skip=('bottom', 'top'))
        return z + h, 0.08

    def hang(z_top, t_face, x0, x1, density):
        """Towels / sarongs / blankets draped over a railing top (front drop + fold over the top)."""
        x = x0 + rng.uniform(0.0, 0.5)
        while x < x1 - 0.4:
            if rng.random() < density:
                cw = rng.choice([0.5, 0.6, 0.75, 0.9, 1.1])
                a, c2 = x, min(x1, x + cw)
                if c2 - a > 0.35 and all(c2 < c - 0.2 or a > c + 0.2 for c in cols):
                    col = rng.choice(CLOTH)
                    drop = rng.choice([0.45, 0.55, 0.65, 0.8]) if cw < 1.0 else 0.9
                    cs_dec(a, c2, z_top - drop, z_top + 0.02, col, t_face, off=0.02)
                    yy0, yy1 = Y(t_face - 0.02), Y(t_face + 0.16)
                    zz = z_top + 0.02
                    oface(b, [(a, yy0, zz), (c2, yy0, zz), (c2, yy1, zz), (a, yy1, zz)], col, (0, 0, 1))
                    x = c2 + rng.choice([0.08, 0.15, 0.3])
                    continue
            x += rng.choice([0.4, 0.7, 1.0])

    lau = v.get('laundry', 0.55)
    for k in range(1, n):
        ztop, tf = railing(k * fh, cx0, cx1)
        hang(ztop, tf, cx0 + 0.1, cx1 - 0.1, lau)
    if v.get('gfence'):   # ground floor railing with a gate gap in front of the stair bay
        gx0, gx1 = (cx0, S(SW)) if sr else (S(SW), cx1)     # free end hidden inside the corner column
        railing(0.15, gx0, gx1, h=1.0)

    # hangers with shirts along the corridor ceiling (seen between railing and slab)
    for k in range(0, n):
        if rng.random() < 0.55:
            r0, r1 = rooms[rng.randrange(nr)]
            zc = (k + 1) * fh - BH          # hung from hooks in the corridor ceiling
            for j in range(rng.randint(1, 2)):
                xc = r0 + 0.8 + j * 0.75
                shirt(b, 'x', xc, Y(0.55), zc, rng.choice(CLOTH), (cdir,), s=0.9)

    # ------------------------------------------------------------------ corridor facade: doors + windows
    dleft = rng.random() < 0.5
    for k in range(n):
        zf = k * fh + (0.15 if k == 0 else 0.0)
        for (r0, r1) in rooms:
            dx = r0 + 0.75 if dleft else r1 - 0.75
            wx = dx + 1.25 if dleft else dx - 1.25
            cs_dec(dx - 0.48, dx + 0.48, zf, zf + 2.18, frame, CD, off=0.02)
            cs_dec(dx - 0.4, dx + 0.4, zf, zf + 2.1, doorc, CD, off=0.035)
            cs_dec(wx - 0.5, wx + 0.5, zf + 1.0, zf + 2.05, frame, CD, off=0.02)
            cs_dec(wx - 0.42, wx + 0.42, zf + 1.08, zf + 1.97, 'glass', CD, off=0.035)

    # ------------------------------------------------------------------ far facade + side walls
    for k in range(1, n):
        os_dec(XL, XR, k * fh - BH, k * fh, acc)
    os_dec(XL, XR, 0, 0.35, 'plinth')
    for side in ('left', 'right'):
        side_dec(side, 0.0, FW, 0, 0.35, 'plinth')
        for k in range(1, n):
            side_dec(side, 0.0, FW, k * fh - BH, k * fh, acc)
    # the kos towers over its 1-2 storey neighbours: give both party walls a lived-in look above ~4.5 m
    patch = shade(wall, 0.9)
    for si, side in enumerate(('left', 'right')):
        fwd = (si == 0) == (rng.random() < 0.5)
        tp = FW * (0.18 if fwd else 0.5) + rng.uniform(0.0, 0.4)
        zp = 2 * fh + 0.35
        side_dec(side, tp, tp + 2.0, zp, zp + 1.5, patch, off=0.012)                 # re-plastered patch
        tv = FW - 2.4 if fwd else 0.6
        for i in range(4):                                                            # roster vent blocks
            side_dec(side, tv + i * 0.45, tv + i * 0.45 + 0.3, TOPB - 0.75, TOPB - 0.45, VENT, off=0.025)
        tpp = FW - 0.35 if fwd else tp - 0.6                                          # drain pipe
        side_dec(side, tpp - 0.05, tpp + 0.05, 0.0, TOPB, PIPE, off=0.035)
    if cf:
        # back of a corridor-front kos: small bathroom windows + AC condensers + a drain pipe
        for k in range(n):
            zf = k * fh
            for (r0, r1) in rooms:
                xc = (r0 + r1) / 2 + (0.5 if dleft else -0.5)
                os_dec(xc - 0.4, xc + 0.4, zf + 1.45, zf + 2.15, frame)
                os_dec(xc - 0.33, xc + 0.33, zf + 1.52, zf + 2.08, 'glass_light', off=0.035)
                if rng.random() < 0.45:
                    b.ac_unit(OS, xc - (1.0 if dleft else -1.0), zf + 1.3, wall=Y(FW))
            xs = (sx0 + sx1) / 2
            os_dec(xs - 0.3, xs + 0.3, zf + 1.6, zf + 2.3, frame)
            os_dec(xs - 0.24, xs + 0.24, zf + 1.66, zf + 2.24, 'glass_light', off=0.035)
        xp = sx1 - 0.25 if sr else sx0 + 0.25
        box(xp - 0.06, FW, 0, xp + 0.06, FW + 0.1, H0, PIPE, skip=('bottom', 'front'))
    else:
        # street facade of a windowed kos: big windows, slim sun shades (continuous or one per window), AC units
        grill = v.get('grill', False)
        g = v.get('ground', 'rooms')
        shd, shc = v.get('shade', 'cont'), v.get('shadec', trim)
        for k in range(n):
            zf = k * fh
            bays = list(rooms) + [(sx0, sx1)]
            for bi, (r0, r1) in enumerate(bays):
                xc = (r0 + r1) / 2
                stair_bay = bi == len(bays) - 1
                if k == 0 and stair_bay and g in ('gate', 'shop'):
                    continue
                if k == 0 and bi == (0 if sr else nr - 1) and g == 'shop':
                    continue
                ww = 0.8 if stair_bay else min(1.4, (r1 - r0) - 1.4)
                os_dec(xc - ww / 2 - 0.08, xc + ww / 2 + 0.08, zf + 0.82, zf + 2.1, frame)
                os_dec(xc - ww / 2, xc + ww / 2, zf + 0.9, zf + 2.02, 'glass', off=0.035)
                if not stair_bay:
                    os_dec(xc - 0.025, xc + 0.025, zf + 0.9, zf + 2.02, frame, off=0.045)
                if grill and k < 2:
                    for zz in (1.3, 1.65):
                        os_dec(xc - ww / 2, xc + ww / 2, zf + zz, zf + zz + 0.035, 'rail_black', off=0.055)
                if not stair_bay and bi > 0 and rng.random() < 0.6 and not (k == 0 and g == 'shop'):
                    b.ac_unit(OS, r0, zf + 1.05, wall=Y(FW))
                if shd == 'win':      # small concrete hood over each window
                    box(xc - ww / 2 - 0.15, FW, zf + 2.3, xc + ww / 2 + 0.15, FW + 0.35, zf + 2.38, shc, skip=('front',))
            if shd == 'cont':         # continuous slim sun shade over the windows
                box(XL, FW, zf + 2.3, XR, FW + 0.35, zf + 2.4, shc, skip=('front',))
        # ground floor: entrance door in the stair bay, optionally a small warung in the far room
        if g in ('gate', 'shop'):
            xc = (sx0 + sx1) / 2
            os_dec(xc - 0.8, xc + 0.8, 0, 2.3, trim, off=0.035)          # in front of the plinth band
            os_dec(xc - 0.7, xc + 0.7, 0, 2.2, 'door_dark', off=0.05)
            os_dec(xc - 0.02, xc + 0.02, 0, 2.2, '#3a2a20', off=0.06)
            if v.get('canopy_door'):
                b.awning(OS, xc - 0.95, xc + 0.95, 2.62, out=0.55, drop=0.2, color=v['canopy_door'], wall=Y(FW))
        if g == 'shop':
            r0, r1 = rooms[0] if sr else rooms[-1]
            a, c2 = r0 + 0.35, r1 - 0.25
            b.panel(OS, a, c2, 0, 2.3, 'shutter', off=0.04, depth=0.04, wall=Y(FW))
            for zz in (0.6, 1.2, 1.8):
                os_dec(a + 0.03, c2 - 0.03, zz - 0.03, zz, 'shutter_groove', off=0.05)
            b.sign(OS, a - 0.1, c2 + 0.1, 2.45, 2.95, rng.choice(['sign_red', 'sign_blue', 'sign_green', 'sign_orange']),
                   off=0.1, wall=Y(FW))
        # downpipe at the far end
        xp = Q(0.18)
        box(xp - 0.06, FW, 0, xp + 0.06, FW + 0.1, H0, PIPE, skip=('bottom', 'front'))

    # ------------------------------------------------------------------ roof
    if v['roof'] in ('hip', 'gable'):
        pc = v.get('parc', wall)
        box(rx0, 0, TOPB, rx1, FW, H0, acc, skip=('top', OUT))
        box(sx0, 0, TOPB, sx1, FW, H0, v.get('deck', 'concrete_dark'), skip=(IN,))
        cs_dec(sx0, sx1, TOPB, H0, acc, 0.0)
        os_dec(sx0, sx1, TOPB, H0, acc)
        side_dec(OUT, 0.0, FW, TOPB, H0, acc)
        ov = 0.45
        ylo, yhi = min(Y(0), Y(FW)), max(Y(0), Y(FW))
        if v['roof'] == 'hip':
            b.roof_hip(rx0 + ov, rx1 - ov, ylo + ov, yhi - ov, H0, v.get('rise', 1.3), v['roofc'], over=ov, thick=0.12)
            hip_caps(b, rx0, rx1, ylo, yhi, H0, v.get('rise', 1.3), shade(v['roofc'], 0.78), thick=0.12)
        else:
            gable_roof(b, rx0, rx1, ylo, yhi, H0, v.get('rise', 1.5), v['roofc'], wall, vent='#5a4a3e')
            xm_ = (rx0 + rx1) / 2
            cap(b, (xm_, ylo, H0 + v.get('rise', 1.5) + 0.14), (xm_, yhi, H0 + v.get('rise', 1.5) + 0.14),
                shade(v['roofc'], 0.78), w=0.1, h=0.06)
        # flat dak strip over the stair bay: edge protection, toren at the far end, laundry / AC / pots near
        st = v.get('strip')
        if st == 'parapet':
            pw, ph2 = 0.12, 0.6
            box(sx0, 0, H0, sx1, pw, H0 + ph2, pc)
            box(sx0, FW - pw, H0, sx1, FW, H0 + ph2, pc)
            box(min(S(0), S(pw)), pw, H0, max(S(0), S(pw)), FW - pw, H0 + ph2, pc, skip=('bottom', 'front', 'back'))
            cs_dec(sx0, sx1, H0 + ph2 - 0.08, H0 + ph2, acc, 0.0)
            os_dec(sx0, sx1, H0 + ph2 - 0.08, H0 + ph2, acc)
            side_dec(OUT, 0.0, FW, H0 + ph2 - 0.08, H0 + ph2, acc)
        elif st == 'pipe':
            rc, ins, rh = v.get('striprail', 'rail_black'), 0.1, 0.9
            xo, xi = S(ins), S(SW - 0.05)
            for zz in (rh, rh * 0.5):
                for tt in (ins, FW - ins):
                    box(min(xo, xi), tt - 0.025, H0 + zz - 0.05, max(xo, xi), tt + 0.025, H0 + zz, rc, skip=('bottom',))
                box(xo - 0.025, ins + 0.025, H0 + zz - 0.05, xo + 0.025, FW - ins - 0.025, H0 + zz, rc,
                    skip=('bottom', 'front', 'back'))
            npost = max(2, int(round((FW - 2 * ins) / 1.6)))
            for i in range(npost + 1):
                tt = ins + (FW - 2 * ins) * i / npost
                box(xo - 0.03, tt - 0.03, H0, xo + 0.03, tt + 0.03, H0 + rh - 0.05, rc, skip=('bottom', 'top'))
            for tt in (ins, FW - ins):
                box(xi - 0.03, tt - 0.03, H0, xi + 0.03, tt + 0.03, H0 + rh - 0.05, rc, skip=('bottom', 'top'))
        tcol = v['tanks'][0]
        sc = (sx0 + sx1) / 2 + (0.1 if sr else -0.1)
        if st == 'lean':
            toren(b, sc, Y(FW - 1.25), H0, tcol, stand=0.15, r=0.5, h=TH)
            t_a, t_b = FW - 2.5, FW - 0.05
            y_a, y_b = min(Y(t_a), Y(t_b)), max(Y(t_a), Y(t_b))
            hi_at_far = Y(t_b) < Y(t_a)   # high side over the far facade end
            za, zb = (H0 + 1.95, H0 + 1.7) if hi_at_far else (H0 + 1.7, H0 + 1.95)
            lean_to(b, sx0 + 0.05, sx1 - 0.05, y_a, y_b, H0, za, zb, wall_x=S(0.05))
        else:
            toren(b, sc, Y(FW - 1.2), H0, tcol, stand=0.3 if n == 3 else 0.0, r=0.5, h=TH)
        near = v.get('strip_near', 'line')
        ty0 = Y(1.1)
        if near == 'line' and n == 3:
            lx0, lx1 = sx0 + 0.4, sx1 - 0.4
            clothes_line(b, 'x', lx0, lx1, ty0, H0, LH, rng)
        elif near == 'ac':
            ax = (sx0 + sx1) / 2
            b.box(ax - 0.4, ty0 - 0.175, H0, ax + 0.4, ty0 + 0.175, H0 + 0.55, 'ac_white')
            b.decal('front', ax - 0.3, ax + 0.05, H0 + 0.1, H0 + 0.45, 'metal', off=0.02, wall=ty0 - 0.175)
            pot(b, ax, Y(2.4), H0, leaf='plant')
        else:
            for i in range(2):
                pot(b, (sx0 + sx1) / 2 + (-0.45 + 0.9 * i), Y(0.6 + 0.2 * i), H0, leaf='plant' if i == 0 else 'plant_dark')
    else:
        deck = v.get('deck', 'concrete')
        ph = v.get('ph', 0.9)
        pc = v.get('parc', wall)
        if hut:   # leave the stairwell open under the stair house (the last flight climbs onto the roof)
            box(rx0, 0, TOPB, rx1, FW, H0, deck, skip=(OUT,))
            xquad(S(SW), CD, SBD, TOPB, H0, deck, sx_out)
            box(sx0, 0, TOPB, sx1, CD, H0, deck, skip=('top', IN))
            box(sx0, SBD, TOPB, sx1, FW, H0, deck, skip=(IN,))
            box(min(S(0), S(0.2)), CD, TOPB, max(S(0), S(0.2)), SBD, H0, trim, skip=('top', 'bottom', 'front', 'back'))
        else:
            box(XL, 0, TOPB, XR, FW, H0, deck, skip=())
        # parapet (split around the stair house)
        pt = 0.15
        fx0, fx1 = (rx0, rx1) if hut else (XL, XR)
        box(fx0, 0, H0, fx1, pt, H0 + ph, pc, skip=('bottom', OUT) if hut else ('bottom',))
        box(XL, FW - pt, H0, XR, FW, H0 + ph, pc)
        box(min(Q(0), Q(pt)), pt, H0, max(Q(0), Q(pt)), FW - pt, H0 + ph, pc, skip=('bottom', 'front', 'back'))
        box(min(S(0), S(pt)), SBD if hut else pt, H0, max(S(0), S(pt)), FW - pt, H0 + ph, pc,
            skip=('bottom', 'front', 'back'))
        # accent band on the roof slab edge + a thin coping line on the parapet
        for (z0b, z1b) in ((TOPB, H0), (H0 + ph - 0.1, H0 + ph)):
            cs_dec(fx0 if z0b > H0 else XL, fx1 if z0b > H0 else XR, z0b, z1b, acc, 0.0)
            os_dec(XL, XR, z0b, z1b, acc)
            for side in ('left', 'right'):
                side_dec(side, SBD if (hut and side == OUT and z0b > H0) else 0.0, FW, z0b, z1b, acc)
        # stair house
        if hut:
            hh = v.get('hh', 2.4)
            box(sx0, 0, H0, sx1, SBD, H0 + hh, wall, skip=('bottom', 'top'))
            b.decal(IN, Y(0.45), Y(1.25), H0, H0 + 2.05, 'door_dark', off=0.03, wall=S(SW))
            b.decal(IN, Y(0.37), Y(1.33), H0, H0 + 2.12, frame, off=0.02, wall=S(SW))
            b.decal(CS, sx0 + 0.6, sx1 - 0.6, H0 + 1.2, H0 + 1.9, frame, off=0.012, wall=Y(0))   # stays inside the lot
            b.decal(CS, sx0 + 0.68, sx1 - 0.68, H0 + 1.27, H0 + 1.83, 'glass', off=0.026, wall=Y(0))
            if hut == 'gable':
                hy0, hy1 = min(Y(0), Y(SBD)), max(Y(0), Y(SBD))
                b.roof_gable(sx0, sx1, hy0, hy1, H0 + hh, v.get('hutrise', 0.7), v.get('hutroof', 'roof_zinc'),
                             gable_color=wall, over=0.0, thick=0.1, ridge='y')
            else:     # flat concrete lid with an accent edge
                box(sx0, 0, H0 + hh, sx1, SBD, H0 + hh + 0.14, acc, skip=('bottom',))
        # deck interior in world coordinates; the stair house blocks x in [sx0, sx1] for y in [hy0, hy1]
        ylo, yhi = min(Y(0), Y(FW)) + pt, max(Y(0), Y(FW)) - pt
        X0, X1 = XL + pt, XR - pt
        hy0, hy1 = (min(Y(0), Y(SBD)), max(Y(0), Y(SBD))) if hut else (0.0, -1.0)
        taken = []

        def place(u, vv, hx, hy, what):
            x = min(max(X0 + u * (X1 - X0), X0 + hx + 0.05), X1 - hx - 0.05)
            y = min(max(ylo + vv * (yhi - ylo), ylo + hy + 0.05), yhi - hy - 0.05)
            r = (x - hx, y - hy, x + hx, y + hy)
            if hut and r[2] > sx0 - 0.05 and r[0] < sx1 + 0.05 and r[3] > hy0 - 0.05 and r[1] < hy1 + 0.05:
                print('   kos: %s at (%.2f, %.2f) hits the stair house' % (what, x, y))
            for (w_, q) in taken:
                if r[2] > q[0] and r[0] < q[2] and r[3] > q[1] and r[1] < q[3]:
                    print('   kos: %s at (%.2f, %.2f) overlaps %s' % (what, x, y, w_))
            taken.append((what, r))
            return x, y

        for it in v.get('items', []):
            kind = it[0]
            if kind == 'tanks':
                _, u, vv, mode, dirn = it
                cols_ = v['tanks']
                sp = 1.25
                L = (len(cols_) - 1) * sp
                hx, hy = (L / 2 + 0.62, 0.62) if dirn == 'x' else (0.62, L / 2 + 0.62)
                cx, cy = place(u, vv, hx, hy, 'tanks')
                if mode == 'stand':
                    sh = 1.5
                    tank_stand(b, cx - hx, cy - hy, cx + hx, cy + hy, H0, sh)
                    z, stn = H0 + sh, 0.0
                else:
                    z, stn = H0, (0.3 if n == 3 else 0.0)
                for i, tc in enumerate(cols_):
                    o = -L / 2 + i * sp
                    tx, ty = (cx + o, cy) if dirn == 'x' else (cx, cy + o)
                    toren(b, tx, ty, z, tc, stand=stn, r=0.5, h=TH)
            elif kind == 'lines':
                _, dirn, u, vv, length, cnt = it
                gap = 1.1
                if dirn == 'x':
                    cx, cy = place(u, vv, length / 2, 0.3 + gap * (cnt - 1) / 2, 'lines')
                    for i in range(cnt):
                        yl = cy + (i - (cnt - 1) / 2) * gap
                        clothes_line(b, 'x', cx - length / 2, cx + length / 2, yl, H0, LH, rng)
                else:
                    cx, cy = place(u, vv, 0.3 + gap * (cnt - 1) / 2, length / 2, 'lines')
                    for i in range(cnt):
                        xl = cx + (i - (cnt - 1) / 2) * gap
                        clothes_line(b, 'y', cy - length / 2, cy + length / 2, xl, H0, LH, rng)
            elif kind == 'ac':
                _, u, vv, cnt = it
                L = cnt * 1.0 - 0.2
                cx, cy = place(u, vv, L / 2, 0.2, 'ac')
                for i in range(cnt):
                    ax = cx - L / 2 + 0.4 + i * 1.0
                    b.box(ax - 0.4, cy - 0.175, H0, ax + 0.4, cy + 0.175, H0 + 0.55, 'ac_white')
                    b.decal('front', ax - 0.3, ax + 0.05, H0 + 0.1, H0 + 0.45, 'metal', off=0.02, wall=cy - 0.175)
            elif kind == 'dish':
                _, u, vv = it
                cx, cy = place(u, vv, 0.45, 0.45, 'dish')
                dish(b, cx, cy, H0, h=0.9 if n == 3 else 0.5, face=-1)
            elif kind == 'antenna':
                _, u, vv = it
                cx, cy = place(u, vv, 0.55, 0.1, 'antenna')
                antenna(b, cx, cy, H0)
            elif kind == 'pots':
                _, u, vv, cnt = it
                L = (cnt - 1) * 0.7
                cx, cy = place(u, vv, L / 2 + 0.3, 0.3, 'pots')
                for i in range(cnt):
                    pot(b, cx - L / 2 + i * 0.7, cy, H0, leaf='plant' if i % 2 == 0 else 'plant_dark')
            elif kind == 'shed':
                _, u, vv, sw_, sd_ = it
                cx, cy = place(u, vv, sw_ / 2, sd_ / 2, 'shed')
                x0_, x1_, y0_, y1_ = cx - sw_ / 2, cx + sw_ / 2, cy - sd_ / 2, cy + sd_ / 2
                wall_y0 = vv < 0.5            # walls against the nearest parapets, open to the middle of the deck
                wall_x0 = u < 0.5
                za, zb = (H0 + 2.05, H0 + 1.8) if wall_y0 else (H0 + 1.8, H0 + 2.05)
                lean_to(b, x0_, x1_, y0_, y1_, H0, za, zb, wall_y=y0_ if wall_y0 else y1_, wall_x=x0_ if wall_x0 else x1_)
                # washing machine against the back wall + a blue basin
                wy = y0_ + 0.45 if wall_y0 else y1_ - 0.45
                wx = x0_ + 0.6 if wall_x0 else x1_ - 0.6
                b.box(wx - 0.3, wy - 0.3, H0, wx + 0.3, wy + 0.3, H0 + 0.85, 'ac_white')
                b.decal('back' if wall_y0 else 'front', wx - 0.15, wx + 0.15, H0 + 0.3, H0 + 0.6, 'glass_dark',
                        off=0.02, wall=wy + 0.3 if wall_y0 else wy - 0.3)
                bx_ = wx + 0.75 if wall_x0 else wx - 0.75
                b.box(bx_ - 0.25, wy - 0.25, H0, bx_ + 0.25, wy + 0.25, H0 + 0.3, '#3c78b5')
            elif kind == 'canopy':
                _, u0, u1, v0, v1, ccol = it
                cxa, cya = place(u0, v0, 0.0, 0.0, 'canopy-a')
                cxb, cyb = place(u1, v1, 0.0, 0.0, 'canopy-b')
                taken.pop(); taken.pop()
                c0, c1, cy0, cy1 = cxa + 0.15, cxb - 0.15, cya + 0.15, cyb - 0.15
                taken.append(('canopy', (c0 - 0.15, cy0 - 0.15, c1 + 0.15, cy1 + 0.15)))
                za, zb = H0 + 2.34, H0 + 2.14          # canopy top at the street edge / back edge
                for xx in (c0, c1):
                    for yy in (cy0, cy1):
                        zbot = za - 0.06 + (zb - za) * (yy - (cy0 - 0.15)) / (cy1 - cy0 + 0.3)
                        b.box(xx - 0.04, yy - 0.04, H0, xx + 0.04, yy + 0.04, zbot + 0.02, 'metal', skip=('bottom', 'top'))
                top = [(c0 - 0.15, cy0 - 0.15, za), (c1 + 0.15, cy0 - 0.15, za),
                       (c1 + 0.15, cy1 + 0.15, zb), (c0 - 0.15, cy1 + 0.15, zb)]
                b._slab(top, [(p[0], p[1], p[2] - 0.06) for p in top], ccol)
                ncor = int((c1 - c0) / 0.55)
                for i in range(1, ncor):      # corrugation ribs running down the slope
                    xr = c0 - 0.15 + (c1 - c0 + 0.3) * i / ncor
                    oface(b, [(xr - 0.035, cy0 - 0.15, za + 0.015), (xr + 0.035, cy0 - 0.15, za + 0.015),
                              (xr + 0.035, cy1 + 0.15, zb + 0.015), (xr - 0.035, cy1 + 0.15, zb + 0.015)],
                          v.get('canopy_rib', shade(ccol, 0.75)), (0, 0, 1))
                # one clothes line under the canopy, clear of its posts
                clothes_line(b, 'x', c0 + 0.35, c1 - 0.35, (cy0 + cy1) / 2, H0, LH, rng)

    # ------------------------------------------------------------------ front yard fence
    if v.get('fy', 0.0) > 0.5:
        fc = v.get('fence', 'rail_black')
        gw = 1.9
        gc = (sx0 + sx1) / 2
        pl, pr = gc - gw / 2 - 0.15, gc + gw / 2 + 0.15            # gate pillar centres
        has_l, has_r = XL < pl - 0.15, pr + 0.15 < XR
        for (a, c2, sk) in ((XL, pl if has_l else gc - gw / 2, 'right' if has_l else None),
                            (pr if has_r else gc + gw / 2, XR, 'left' if has_r else None)):
            if c2 - a < 0.3:
                continue
            ex = (sk,) if sk else ()
            b.box(a, E + 0.03, 0, c2, E + 0.2, 0.5, trim, skip=('bottom',) + ex)
            b.box(a, E + 0.07, 1.45, c2, E + 0.15, 1.5, fc, skip=('bottom',) + ex)
            b.box(a, E + 0.08, 1.0, c2, E + 0.14, 1.04, fc, skip=('bottom', 'top') + ex)
            npost = max(1, int(round((c2 - a) / 1.3)))
            for i in range(npost + 1):
                xp = min(max(a + (c2 - a) * i / npost, a + 0.05), c2 - 0.05)
                if abs(xp - pl) > 0.2 and abs(xp - pr) > 0.2:
                    b.box(xp - 0.03, E + 0.095, 0.5, xp + 0.03, E + 0.125, 1.45, fc, skip=('bottom', 'top'))
        for xp, ok in ((pl, has_l), (pr, has_r)):
            if ok:
                b.box(xp - 0.15, E, 0, xp + 0.15, E + 0.3, 1.75, trim)

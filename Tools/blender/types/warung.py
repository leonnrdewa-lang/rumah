"""Warung: small single-storey Jakarta street businesses.

Ten clearly different variants: warung kelontong (window counter, hanging snack strips, crates), warung makan
with a striped tenda, bengkel motor (open front, tyre stacks, oily floor, tool board), laundry kiloan (glass
front, clothes drying on the flat roof), kios pulsa (tall sign facade), fotokopi (open shop, front gable),
toko grosir (wide, hip roof, blue tarp), warung kopi (long rusty zinc roof on wooden posts), warung bakso
(gerobak cart, flat roof with toren + dish) and depot air isi ulang (gallon racks, filter tubes).
Everything stays <= 4.8 m so every variant also works as a 'low' building, and every back side is finished
(back door, window, toren, crates, gas cylinders, clothes line).

Coordinates follow common.py: x in [-W/2, W/2], y in [0, D] with y = 0 the street front, z up.
"""
import math

TYPE = 'warung'
ROLES = ['front', 'low', 'fill']

FL = 0.15                 # teras floor height
INTERIOR = '#4a3f3a'      # dark shop interior seen through an open front
SHELF = '#c9a57a'
WOOD = '#9a6a43'
WOOD_DARK = '#6e4a30'
TYRE = '#2e2d31'
TYRE_HOLE = '#18171a'
OIL = '#625c55'
FLOOR_DARK = '#7a766f'
GALON = '#8fc3ec'
GALON_CAP = '#2f6fc0'
LPG_GREEN = '#58a84a'
LPG_BLUE = '#3f73b8'
CARDBOARD = '#c89c64'
GOODS = ['#e2574c', '#f2c94c', '#4f9ad8', '#6cc070', '#f08a3c', '#f4f1e8', '#c86dd7', '#e86aa0']
SNACK = ['#e2574c', '#f2c94c', '#4f9ad8', '#f08a3c', '#6cc070', '#e86aa0', '#f4f1e8']
CRATE = ['#d9443a', '#f0c02f', '#3b78c4', '#3f9a5a', '#e8812d']
CLOTHES = ['fabric_1', 'fabric_2', 'fabric_3', '#f4f1e8', '#7c4aa8', '#e8812d', '#3f9a5a', '#d9443a']


def variants():
    return [
        dict(kind='kelontong', w=5.6, d=7.5, wall='wall_mint', roof='#3565a8', rib='#28508a', tarp='awning_green',
             sign='sign_yellow', tank='tank_orange', curtain='fabric_2'),
        dict(kind='makan', w=7.2, d=8.5, wall='wall_cream', roof='roof_terracotta', course='#a8492a',
             tenda='awning_red', stripe='awning_stripe', sign='sign_red', tank='tank_blue', curtain='fabric_3'),
        dict(kind='bengkel', w=8.2, d=8.0, wall='wall_blue', roof='roof_grey', rib='#5d636b', sign='sign_orange',
             tank='tank_orange'),
        dict(kind='laundry', w=6.2, d=9.0, wall='wall_sky', sign='sign_purple', tank='tank_blue'),
        dict(kind='pulsa', w=4.2, d=6.0, wall='wall_yellow', roof='#a8443a', rib='#86352d', sign='sign_red',
             tarp='awning_blue', tank='tank_white'),
        dict(kind='fotokopi', w=4.8, d=7.0, wall='wall_lilac', roof='roof_blue', rib='#3f5d80', sign='sign_blue'),
        dict(kind='grosir', w=9.0, d=8.0, wall='wall_peach', roof='#5b6470', course='#48505b', cap='#3a4049',
             tarp='awning_blue', sign='sign_green',
             curtain='fabric_1'),
        dict(kind='warkop', w=5.2, d=7.0, wall='wall_green', roof='#7a4b37', rib='#613a2a', sign='sign_yellow',
             curtain='fabric_3', tank='tank_blue'),
        dict(kind='bakso', w=6.8, d=8.0, wall='wall_pink', tarp='awning_orange', sign='sign_yellow',
             tank='tank_orange', curtain='fabric_2'),
        dict(kind='depot', w=7.6, d=8.5, wall='wall_white', roof='roof_green', course='#3f6a4a', sign='sign_blue',
             tank='tank_blue'),
    ]


def build(b, v, rng):
    KINDS[v['kind']](b, v, rng)


# =============================================================================================== helpers
def lin(ya, za, yb, zb):
    s = (zb - za) / (yb - ya)
    return lambda y: za + s * (y - ya)


def _area_xy(pts):
    n = len(pts)
    return sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def face_up(b, pts, color):
    """Polygon whose normal points up, whatever order the points come in."""
    b.face(pts if _area_xy(pts) > 0 else pts[::-1], color)


def face_down(b, pts, color):
    b.face(pts if _area_xy(pts) < 0 else pts[::-1], color)


def ngon(b, cx, cy, z, r, color, seg=8, phase=0.0, ry=None):
    """Flat upward-facing polygon (stains, lids, tyre holes)."""
    ry = r if ry is None else ry
    b.face([(cx + r * math.cos(phase + 2 * math.pi * i / seg), cy + ry * math.sin(phase + 2 * math.pi * i / seg), z)
            for i in range(seg)], color)


def vngon(b, side, uc, zc, r, color, wall=None, off=0.03, seg=8):
    """Outward-facing polygon on a facade (washing machine doors, round signs)."""
    m, _ = b._frame(side, wall)
    ring = [(uc + r * math.cos(math.pi / seg + 2 * math.pi * i / seg), zc + r * math.sin(math.pi / seg + 2 * math.pi * i / seg))
            for i in range(seg)]
    if side in ('back', 'left'):
        ring = ring[::-1]
    b.face([m(u, off) + (z,) for (u, z) in ring], color)


def vcyl(b, cx, cy, z0, z1, r, color, seg=8, top=True, phase=0.0):
    ring = [(cx + r * math.cos(phase + 2 * math.pi * i / seg), cy + r * math.sin(phase + 2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, c = ring[i], ring[(i + 1) % seg]
        b.face([(a[0], a[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (a[0], a[1], z1)], color)
    if top:
        b.face([(p[0], p[1], z1) for p in ring], color)


def tcyl(b, cx, cy, rings, color, seg=8, top=True, phase=0.0):
    """Stacked frustum along z through `rings` = [(z, r), ...] (bottom to top), one colour per band if `color` is a
    list. Used for rounded shapes like potted bushes."""
    cols = color if isinstance(color, (list, tuple)) else [color] * (len(rings) - 1)

    def ring(z, r):
        return [(cx + r * math.cos(phase + 2 * math.pi * i / seg), cy + r * math.sin(phase + 2 * math.pi * i / seg), z)
                for i in range(seg)]
    for k in range(len(rings) - 1):
        lo, hi = ring(*rings[k]), ring(*rings[k + 1])
        for i in range(seg):
            j = (i + 1) % seg
            b.face([lo[i], lo[j], hi[j], hi[i]], cols[k])
    if top:
        b.face(ring(*rings[-1]), cols[-1])


def plant(b, x, y, z0=0.0, s=1.0):
    """Potted bush: tapered terracotta pot and a rounded, two-tone leafy crown on it (common.plant_pot is a green
    cube, which reads as a crate at game scale)."""
    tcyl(b, x, y, [(z0, 0.14 * s), (z0 + 0.3 * s, 0.19 * s), (z0 + 0.46 * s, 0.33 * s), (z0 + 0.66 * s, 0.3 * s),
                   (z0 + 0.8 * s, 0.16 * s)], ['pot', 'plant_dark', 'plant', 'plant'], seg=8, phase=math.pi / 8)


def xcyl(b, x0, x1, cy, cz, r, color, seg=8):
    """Cylinder lying along x (wheels of something that drives along y)."""
    ring = [(cy + r * math.cos(math.pi / seg + 2 * math.pi * i / seg), cz + r * math.sin(math.pi / seg + 2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, c = ring[i], ring[(i + 1) % seg]
        b.face([(x0, a[0], a[1]), (x0, c[0], c[1]), (x1, c[0], c[1]), (x1, a[0], a[1])], color)
    b.face([(x1, p[0], p[1]) for p in ring], color)
    b.face([(x0, p[0], p[1]) for p in ring[::-1]], color)


def ycyl(b, y0, y1, cx, cz, r, color, seg=8):
    """Cylinder lying along y (wheels of something that drives along x, e.g. a gerobak)."""
    ring = [(cx + r * math.cos(math.pi / seg + 2 * math.pi * i / seg), cz + r * math.sin(math.pi / seg + 2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, c = ring[i], ring[(i + 1) % seg]
        b.face([(a[0], y0, a[1]), (a[0], y1, a[1]), (c[0], y1, c[1]), (c[0], y0, c[1])], color)
    b.face([(p[0], y0, p[1]) for p in ring], color)
    b.face([(p[0], y1, p[1]) for p in ring[::-1]], color)


def post(b, x, y, z0, z1, color='metal', s=0.07):
    b.box(x - s / 2, y - s / 2, z0, x + s / 2, y + s / 2, z1, color)


# ---------------------------------------------------------------------------------------- walls
def shed_body(b, x0, x1, yf, yr, yb, zf, zb, color):
    """Walls under a single-slope (or flat, zf == zb) roof. The side walls run the full depth yf..yb (so the
    front wall pieces need no end faces), the facade plane behind the openings is at yr, the back wall at yb."""
    z = lin(yf, zf, yb, zb)
    b.face([(x0, yb, 0), (x0, yf, 0), (x0, yf, zf), (x0, yb, zb)], color)            # left
    b.face([(x1, yf, 0), (x1, yb, 0), (x1, yb, zb), (x1, yf, zf)], color)            # right
    b.face([(x1, yb, 0), (x0, yb, 0), (x0, yb, zb), (x1, yb, zb)], color)            # back
    zr = z(yr)
    b.face([(x0, yr, 0), (x1, yr, 0), (x1, yr, zr), (x0, yr, zr)], color)            # facade plane behind openings
    return z


def gable_body(b, x0, x1, yf, yr, yb, h, rise, color, ridge='x'):
    """Walls under a two-slope roof whose underside passes through the wall tops.
    ridge='x': gables on the left/right walls. ridge='y': gable triangle over the front (at yf) and the back."""
    if ridge == 'x':
        ym = (yf + yb) / 2
        b.face([(x0, yb, 0), (x0, yf, 0), (x0, yf, h), (x0, ym, h + rise), (x0, yb, h)], color)
        b.face([(x1, yf, 0), (x1, yb, 0), (x1, yb, h), (x1, ym, h + rise), (x1, yf, h)], color)
        b.face([(x1, yb, 0), (x0, yb, 0), (x0, yb, h), (x1, yb, h)], color)
    else:
        xm = (x0 + x1) / 2
        b.face([(x0, yb, 0), (x0, yf, 0), (x0, yf, h), (x0, yb, h)], color)
        b.face([(x1, yf, 0), (x1, yb, 0), (x1, yb, h), (x1, yf, h)], color)
        b.face([(x1, yb, 0), (x0, yb, 0), (x0, yb, h), (xm, yb, h + rise), (x1, yb, h)], color)
        b.face([(x0, yf, h), (x1, yf, h), (xm, yf, h + rise)], color)                # front gable triangle
    b.face([(x0, yr, 0), (x1, yr, 0), (x1, yr, h), (x0, yr, h)], color)


def teras(b, x0, x1, y0, yf, yr, z, bx0=None, bx1=None, color='tile_floor'):
    """Front terrace slab y0..yf plus its top surface under the front wall (yf..yr, so doorways have a floor).
    No side faces touch the building walls; where the terrace is wider than the body (bx0..bx1) its back face
    is closed."""
    bx0 = x0 if bx0 is None else bx0
    bx1 = x1 if bx1 is None else bx1
    b.box(x0, y0, 0, x1, yf, z, color, skip=('bottom', 'back'))
    for (a, c) in ((x0, bx0), (bx1, x1)):
        if c - a > 1e-3:
            b.face([(c, yf, 0), (a, yf, 0), (a, yf, z), (c, yf, z)], color)
    if yr > yf:
        face_up(b, [(bx0, yf, z), (bx1, yf, z), (bx1, yr, z), (bx0, yr, z)], color)


def front_wall(b, x0, x1, y, t, h, holes, color, top=False):
    """Front wall slab y..y+t, 0..h with rectangular openings [(u0, u1, z0, z1), ...]. The openings look into
    the facade plane at y+t (built by the *_body helpers). Outer end faces are left to the side walls."""
    sk = () if top else ('top',)
    u = x0

    def pier(a, c):
        skip = ['bottom', 'back'] + list(sk)
        if abs(a - x0) < 1e-6:
            skip.append('left')
        if abs(c - x1) < 1e-6:
            skip.append('right')
        b.box(a, y, 0, c, y + t, h, color, skip=tuple(skip))
    for (u0, u1, z0, z1) in sorted(holes):
        if u0 - u > 1e-3:
            pier(u, u0)
        if z0 > 0.2:
            b.box(u0, y, 0, u1, y + t, z0, color, skip=('bottom', 'back', 'left', 'right'))
        if z1 < h - 1e-3:
            b.box(u0, y, z1, u1, y + t, h, color, skip=('back', 'left', 'right') + sk)
        u = u1
    if x1 - u > 1e-3:
        pier(u, x1)


# ---------------------------------------------------------------------------------------- roofs
def slab(b, bot, thick, color, band=None, n=0, frac=0.2, along=0):
    """Closed slab over the planar quad `bot` (p0->p1 = u, p1->p2 = v) raised by `thick`. With `band` the top is
    split into n cells along u (along=0: corrugation ribs) or v (along=1: tile courses), each with a narrow band
    of the second colour. The strips share their edges and are coplanar, so the ink pass draws no line between
    them: the roof texture reads as colour, not as noise."""
    top = [(p[0], p[1], p[2] + thick) for p in bot]
    ccw = _area_xy(bot) > 0
    B, T = (bot, top) if ccw else (bot[::-1], top[::-1])
    b.face(B[::-1], color)
    for i in range(4):
        j = (i + 1) % 4
        b.face([B[i], B[j], T[j], T[i]], color)
    if not band or n < 1:
        b.face(T, color)
        return

    def P(s_, t_):
        a = [top[0][k] + (top[1][k] - top[0][k]) * s_ for k in range(3)]
        c = [top[3][k] + (top[2][k] - top[3][k]) * s_ for k in range(3)]
        return tuple(a[k] + (c[k] - a[k]) * t_ for k in range(3))
    cuts = [0.0]
    for i in range(n):
        c, w = (i + 0.5) / n, frac / (2 * n)
        cuts += [c - w, c + w]
    cuts.append(1.0)
    for k in range(len(cuts) - 1):
        s0, s1 = cuts[k], cuts[k + 1]
        q = [P(s0, 0), P(s1, 0), P(s1, 1), P(s0, 1)] if along == 0 else [P(0, s0), P(1, s0), P(1, s1), P(0, s1)]
        face_up(b, q, band if k % 2 else color)


def shed_roof(b, x0, x1, yf, yb, zf, zb, color, ox=0.0, of=0.3, ob=0.3, thick=0.1, rib=None, rib_step=0.75):
    """Single-slope roof whose underside passes through (yf, zf) and (yb, zb). Optional corrugation ribs."""
    z = lin(yf, zf, yb, zb)
    Ya, Yb, X0, X1 = yf - of, yb + ob, x0 - ox, x1 + ox
    bot = [(X0, Ya, z(Ya)), (X1, Ya, z(Ya)), (X1, Yb, z(Yb)), (X0, Yb, z(Yb))]
    slab(b, bot, thick, color, band=rib, n=max(3, int(round((X1 - X0) / rib_step))), frac=0.24, along=0)
    return lambda y: z(y) + thick


def gable_roof(b, x0, x1, yf, yb, h, rise, color, ridge='x', ox=0.3, oy=0.3, thick=0.1, cap=None, course=None,
               rib=None, ncourse=4):
    """Two-slope roof over the wall rectangle; underside passes through the wall tops (h) and the ridge (h+rise).
    `course` shades tile courses parallel to the ridge, `rib` corrugation ribs down the slopes."""
    X0, X1, Y0, Y1 = x0 - ox, x1 + ox, yf - oy, yb + oy
    zt = h + rise + thick
    if ridge == 'x':
        ym = (yf + yb) / 2
        ze = h - rise / (ym - yf) * oy
        quads = [[(X0, ya, ze), (X1, ya, ze), (X1, ym, h + rise), (X0, ym, h + rise)] for ya in (Y0, Y1)]
        across = X1 - X0
    else:
        xm = (x0 + x1) / 2
        ze = h - rise / (xm - x0) * ox
        quads = [[(xa, Y0, ze), (xa, Y1, ze), (xm, Y1, h + rise), (xm, Y0, h + rise)] for xa in (X0, X1)]
        across = Y1 - Y0
    for q in quads:
        if rib:
            slab(b, q, thick, color, band=rib, n=max(3, int(round(across / 0.75))), frac=0.24, along=0)
        elif course:
            slab(b, q, thick, color, band=course, n=ncourse, frac=0.16, along=1)
        else:
            slab(b, q, thick, color)
    if cap and ridge == 'x':
        b.box(X0 + 0.02, ym - 0.13, zt - 0.06, X1 - 0.02, ym + 0.13, zt + 0.07, cap)
    elif cap:
        b.box(xm - 0.13, Y0 + 0.02, zt - 0.06, xm + 0.13, Y1 - 0.02, zt + 0.07, cap)


def _poly(b, pts, color, eps=1e-5):
    """face_up() after dropping repeated points (strips that end in a hip apex become triangles)."""
    q = []
    for p in pts:
        if not q or max(abs(p[k] - q[-1][k]) for k in range(3)) > eps:
            q.append(p)
    if len(q) > 1 and max(abs(q[0][k] - q[-1][k]) for k in range(3)) <= eps:
        q.pop()
    if len(q) >= 3 and abs(_area_xy(q)) > 1e-6:
        face_up(b, q, color)


def hip_roof(b, x0, x1, y0, y1, z0, rise, color, course, cap, over=0.35, thick=0.12, bands=(0.25, 0.5, 0.75),
             bw=0.05, cw=0.13):
    """Limasan (hip) roof like common.roof_hip, but its four slopes carry tile courses (`bands`, as fractions of the
    rise, `bw` wide) and hip caps (`cw` wide on each side of every hip line). Like slab(), all strips are coplanar
    and share their edges exactly, so they read as colour on the roof (no z-fighting, no ink between them)."""
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    w, d = X1 - X0, Y1 - Y0
    c = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    if w >= d:
        r0, r1 = (X0 + d / 2, (Y0 + Y1) / 2), (X1 - d / 2, (Y0 + Y1) / 2)
        faces = [(c[0], c[1], r0, r1), (c[1], c[2], r1, r1), (c[2], c[3], r1, r0), (c[3], c[0], r0, r0)]
    else:
        r0, r1 = ((X0 + X1) / 2, Y0 + w / 2), ((X0 + X1) / 2, Y1 - w / 2)
        faces = [(c[0], c[1], r0, r0), (c[1], c[2], r0, r1), (c[2], c[3], r1, r1), (c[3], c[0], r1, r0)]
    ze = z0 + thick

    def lerp(p, q, t):
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    # one set of cut levels for all four slopes, so the strips meet exactly on the hip lines
    cuts = {0.0, 1.0}
    for bc in bands:
        cuts |= {bc - bw / 2, bc + bw / 2}
    for (eL, eR, aL, aR) in faces:
        W0, W1 = math.dist(eL, eR), math.dist(aL, aR)
        if W1 < 2 * cw < W0:
            cuts.add((W0 - 2 * cw) / (W0 - W1))       # where the two hip caps of a slope meet
    cuts = sorted(cuts)
    band_mid = [(bc - bw / 2 + 1e-6, bc + bw / 2 - 1e-6) for bc in bands]
    for (eL, eR, aL, aR) in faces:
        L0 = math.dist(eL, eR)
        e = ((eR[0] - eL[0]) / L0, (eR[1] - eL[1]) / L0)

        def pts(t):
            L, R = lerp(eL, aL, t), lerp(eR, aR, t)
            z = ze + rise * t
            if math.dist(L, R) > 2 * cw + 1e-6:
                cl, cr = (L[0] + e[0] * cw, L[1] + e[1] * cw), (R[0] - e[0] * cw, R[1] - e[1] * cw)
            else:
                cl = cr = lerp(L, R, 0.5)
            return [(p[0], p[1], z) for p in (L, cl, cr, R)]
        for k in range(len(cuts) - 1):
            ta, tb = cuts[k], cuts[k + 1]
            A, B = pts(ta), pts(tb)
            tm = (ta + tb) / 2
            is_band = any(lo <= tm <= hi for (lo, hi) in band_mid)
            _poly(b, [A[0], A[1], B[1], B[0]], cap)
            _poly(b, [A[1], A[2], B[2], B[1]], course if is_band else color)
            _poly(b, [A[2], A[3], B[3], B[2]], cap)
    # soffit + fascia, as in roof_hip
    b.face([(X0, Y0, z0), (X0, Y1, z0), (X1, Y1, z0), (X1, Y0, z0)], color)
    for i in range(4):
        p, q = c[i], c[(i + 1) % 4]
        b.face([(p[0], p[1], z0), (q[0], q[1], z0), (q[0], q[1], ze), (p[0], p[1], ze)], color)
    # ridge cap
    zt = ze + rise
    if w >= d:
        b.box(r0[0] - 0.02, r0[1] - 0.12, zt - 0.07, r1[0] + 0.02, r0[1] + 0.12, zt + 0.06, cap)
    else:
        b.box(r0[0] - 0.12, r0[1] - 0.02, zt - 0.07, r0[0] + 0.12, r1[1] + 0.02, zt + 0.06, cap)


def roof_patch(b, rt, xa, xb, ya, yb, color, lift=0.015):
    """Replacement sheet / stain lying on a shed roof whose top surface height is rt(y)."""
    face_up(b, [(xa, ya, rt(ya) + lift), (xb, ya, rt(ya) + lift), (xb, yb, rt(yb) + lift), (xa, yb, rt(yb) + lift)], color)


def roof_sheet(b, rt, X0, cell, i, ya, yb, color, rib, lift=0.015):
    """Replacement corrugated sheet lying on a ribbed shed roof (ribs `cell` apart from X0, as shed_roof draws
    them): it covers the two corrugations between rib i and rib i + 2 and carries its own rib i + 1, so it reads
    as one more sheet of the roof in another colour, not as a sticker."""
    cuts = [i + 0.62, i + 1.38, i + 1.62, i + 2.38]
    for k in range(3):
        roof_patch(b, rt, X0 + cuts[k] * cell, X0 + cuts[k + 1] * cell, ya, yb, rib if k == 1 else color, lift)


def hood(b, x0, x1, yw, yo, zw, zo, color, arm='metal'):
    """Small sheet hood over a back door or a washing corner, carried by two triangle brackets on the wall:
    a horizontal arm out to the sheet's outer edge and a vertical piece up to the sheet at the wall."""
    canopy(b, x0, x1, yw, yo, zw, zo, color, thick=0.04, val=0)
    sgn = 1 if yo > yw else -1
    for xc in (x0 + 0.06, x1 - 0.06):
        b.box(xc - 0.02, yw, zo - 0.045, xc + 0.02, yo - sgn * 0.02, zo, arm, skip=('back',) if sgn < 0 else ('front',))
        b.box(xc - 0.02, yw, zo - 0.22, xc + 0.02, yw + sgn * 0.045, zw, arm, skip=('back',) if sgn < 0 else ('front',))


def flat_roof(b, x0, x1, yf, yb, h, slab='concrete', parapet='trim_white', ph=0.4):
    b.box(x0, yf, h, x1, yb, h + 0.15, slab, skip=('bottom',))
    b.parapet(x0, x1, yf, yb, h + 0.15, ph, parapet, t=0.14)
    return h + 0.15


def canopy(b, x0, x1, yw, yo, zw, zo, color, stripe=None, thick=0.05, val=0.16, sw=0.55, posts=(), post_y=None,
           zfloor=FL, post_color='metal'):
    """Sloped canopy / tenda / tarp from a wall (yw, zw) out to (yo, zo), optional stripes, valance and posts."""
    slab(b, [(x0, yw, zw), (x1, yw, zw), (x1, yo, zo), (x0, yo, zo)], thick, color)
    zu = lin(yw, zw, yo, zo)
    sgn = 1 if yo > yw else -1
    if stripe:
        n = max(3, int(round((x1 - x0) / sw)))
        if n % 2 == 0:
            n += 1
        for i in range(1, n, 2):
            a, c = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
            face_up(b, [(a, yw, zw + thick + 0.02), (c, yw, zw + thick + 0.02), (c, yo, zo + thick + 0.02), (a, yo, zo + thick + 0.02)], stripe)
            face_down(b, [(a, yw, zw - 0.02), (c, yw, zw - 0.02), (c, yo, zo - 0.02), (a, yo, zo - 0.02)], stripe)
    if val > 0:
        yv0, yv1 = (yo - 0.01, yo + 0.02) if sgn < 0 else (yo - 0.02, yo + 0.01)
        b.box(x0 + 0.005, yv0, zo - val, x1 - 0.005, yv1, zo + thick, color, skip=())
        if stripe:
            side = 'front' if sgn < 0 else 'back'
            for i in range(1, n, 2):
                a, c = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
                b.decal(side, a, c, zo - val, zo + thick, stripe, off=0.025, wall=yo)
    py = post_y if post_y is not None else yo - sgn * 0.08
    for px in posts:
        post(b, px, py, zfloor, zu(py) + 0.02, post_color)
    return zu


# ---------------------------------------------------------------------------------------- openings
def interior(b, u0, u1, z0, z1, wy, rng, rows=3, goods=GOODS, off=0.02):
    """Dark shop interior with shelves of coloured goods, drawn on the facade plane behind an opening."""
    b.decal('front', u0, u1, z0, z1, INTERIOR, off=off, wall=wy)
    if rows <= 0:
        return
    zb, zt = z0 + 0.12, z1 - 0.12
    step = (zt - zb) / rows
    for r in range(rows):
        zs = zb + r * step
        b.decal('front', u0 + 0.06, u1 - 0.06, zs, zs + 0.04, SHELF, off=off + 0.02, wall=wy)
        u = u0 + 0.1
        while True:
            w = rng.uniform(0.28, 0.55)
            if u + w > u1 - 0.1:
                break
            hh = step * rng.uniform(0.45, 0.72)
            b.decal('front', u, u + w, zs + 0.04, zs + 0.04 + hh, rng.choice(goods), off=off + 0.02, wall=wy)
            u += w + rng.uniform(0.05, 0.12)


def snacks(b, u0, u1, ztop, wy, rng, n=8, length=(0.45, 0.8), off=0.08, colors=SNACK):
    """Renteng: strips of snack / coffee sachets hanging from a rod across the top of an opening."""
    b.panel('front', u0 - 0.04, u1 + 0.04, ztop - 0.05, ztop, 'metal', off=off + 0.04, depth=0.03, wall=wy)
    w = (u1 - u0) / n
    k = rng.randrange(len(colors))
    for i in range(n):
        a = u0 + i * w + w * 0.18
        L = rng.uniform(*length)
        b.decal('front', a, a + w * 0.64, ztop - 0.05 - L, ztop - 0.03, colors[(k + i) % len(colors)], off=off, wall=wy)


def open_door(b, u0, u1, z0, z1, wy, curtain=None):
    b.decal('front', u0, u1, z0, z1, INTERIOR, off=0.02, wall=wy)
    if curtain:
        m = (u0 + u1) / 2
        b.decal('front', u0 + 0.02, m - 0.02, z1 - 0.55, z1 - 0.02, curtain, off=0.04, wall=wy)
        b.decal('front', m + 0.02, u1 - 0.02, z1 - 0.55, z1 - 0.02, curtain, off=0.04, wall=wy)


def glass_front(b, u0, u1, z0, z1, wy, frame='window_frame', glass='glass_light', n=None, transom=None, side='front'):
    """Shop glazing: glass panel with a flat frame, mullions and an optional transom bar (no overlaps)."""
    b.panel(side, u0, u1, z0, z1, glass, off=0.04, depth=0.03, wall=wy)
    n = n or max(1, int(round((u1 - u0) / 0.95)))
    t = 0.06
    us = [u0 + (u1 - u0) * i / n for i in range(n + 1)]
    for i, u in enumerate(us):
        a = u if i == 0 else (u - t if i == n else u - t / 2)
        b.decal(side, a, a + t, z0, z1, frame, off=0.06, wall=wy)
    for i in range(n):
        a, c = us[i] + (t if i == 0 else t / 2), us[i + 1] - (t if i == n - 1 else t / 2)
        for zz in ([z0, z1 - t] + ([transom - t / 2] if transom else [])):
            b.decal(side, a, c, zz, zz + t, frame, off=0.06, wall=wy)


def glass_door(b, u0, u1, z0, z1, wy, frame='frame_black'):
    b.panel('front', u0, u1, z0, z1, 'glass_light', off=0.04, depth=0.03, wall=wy)
    t = 0.07
    b.decal('front', u0, u0 + t, z0, z1, frame, off=0.06, wall=wy)
    b.decal('front', u1 - t, u1, z0, z1, frame, off=0.06, wall=wy)
    b.decal('front', u0 + t, u1 - t, z1 - t, z1, frame, off=0.06, wall=wy)
    b.decal('front', u0 + t, u1 - t, z0, z0 + 0.25, frame, off=0.06, wall=wy)
    b.decal('front', u1 - 0.2, u1 - 0.14, z0 + 0.9, z0 + 1.2, 'metal', off=0.07, wall=wy)


def rollbox(b, u0, u1, ztop, wy, color='shutter_dark'):
    """Rolled-up rolling door housing tucked under the top of an opening."""
    b.panel('front', u0, u1, ztop - 0.24, ztop, color, off=0.2, depth=0.18, wall=wy)


# ---------------------------------------------------------------------------------------- props
def crates(b, x, y, z0, n, rng, colors=CRATE, w=0.46, d=0.34, h=0.27):
    for i in range(n):
        jx, jy = rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03)
        b.box(x - w / 2 + jx, y - d / 2 + jy, z0 + i * h, x + w / 2 + jx, y + d / 2 + jy, z0 + (i + 1) * h, rng.choice(colors))


def boxes(b, x, y, z0, n, rng, w=0.5, d=0.4, h=0.34):
    """Stack of taped cardboard boxes."""
    for i in range(n):
        jx = rng.uniform(-0.04, 0.04)
        b.box(x - w / 2 + jx, y - d / 2, z0 + i * h, x + w / 2 + jx, y + d / 2, z0 + (i + 1) * h, CARDBOARD)
        b.decal('front', x - 0.04 + jx, x + 0.04 + jx, z0 + i * h + 0.02, z0 + (i + 1) * h - 0.02, '#e9dcc0', off=0.02, wall=y - d / 2)


def galon(b, x, y, z0):
    vcyl(b, x, y, z0, z0 + 0.42, 0.14, GALON, seg=6)
    b.box(x - 0.045, y - 0.045, z0 + 0.42, x + 0.045, y + 0.045, z0 + 0.5, GALON_CAP)


def lpg(b, x, y, z0, big=False):
    r, h = (0.17, 0.55) if big else (0.14, 0.32)
    vcyl(b, x, y, z0, z0 + h, r, LPG_BLUE if big else LPG_GREEN, seg=6)
    b.box(x - 0.05, y - 0.05, z0 + h, x + 0.05, y + 0.05, z0 + h + 0.07, 'metal')


def bin_(b, x, y, z0=0.0, color='#3f8a4f'):
    vcyl(b, x, y, z0, z0 + 0.7, 0.24, color, seg=8)
    ngon(b, x, y, z0 + 0.72, 0.26, '#2f6b3c', seg=8)


def drum(b, x, y, z0=0.0, color='sign_blue'):
    vcyl(b, x, y, z0, z0 + 0.88, 0.29, color, seg=10)
    ngon(b, x + 0.12, y, z0 + 0.9, 0.05, 'metal', seg=6)


def stool(b, x, y, z0, color='sign_red'):
    b.box(x - 0.16, y - 0.16, z0, x + 0.16, y + 0.16, z0 + 0.44, color)


def bench(b, x0, x1, y0, y1, z0, color=WOOD, h=0.44):
    b.box(x0, y0, z0 + h - 0.05, x1, y1, z0 + h, color, skip=())
    for xl in (x0 + 0.08, x1 - 0.14):
        b.box(xl, y0 + 0.04, z0, xl + 0.06, y1 - 0.04, z0 + h - 0.05, WOOD_DARK, skip=('bottom', 'top'))


def table(b, x0, x1, y0, y1, z0, top='#efe7d2', legs=WOOD_DARK, h=0.75):
    b.box(x0, y0, z0 + h - 0.04, x1, y1, z0 + h, top, skip=())
    for xl in (x0 + 0.06, x1 - 0.12):
        b.box(xl, y0 + 0.06, z0, xl + 0.06, y1 - 0.06, z0 + h - 0.04, legs, skip=('bottom', 'top'))


def etalase(b, x0, x1, y0, y1, z0, rng, base=WOOD, goods=GOODS):
    """Glass display counter (etalase) with goods rows showing through the front glass."""
    b.box(x0, y0, z0, x1, y1, z0 + 0.45, base)
    b.box(x0 + 0.02, y0 + 0.02, z0 + 0.45, x1 - 0.02, y1 - 0.02, z0 + 0.95, 'glass_light', skip=('bottom', 'top'))
    b.box(x0, y0, z0 + 0.95, x1, y1, z0 + 0.99, 'window_frame', skip=())
    u = x0 + 0.08
    while True:
        w = rng.uniform(0.18, 0.34)
        if u + w > x1 - 0.08:
            break
        b.decal('front', u, u + w, z0 + 0.52, z0 + 0.52 + rng.uniform(0.12, 0.22), rng.choice(goods), off=0.02, wall=y0 + 0.02)
        u += w + 0.06


def fridge(b, x0, y0, z0, color, rng, w=0.64, d=0.58, h=1.8):
    """Drinks cooler (showcase) with a glass door, bottle rows and a blank header panel."""
    b.box(x0, y0, z0, x0 + w, y0 + d, z0 + h, color)
    b.panel('front', x0 + 0.06, x0 + w - 0.06, z0 + 0.22, z0 + h - 0.34, 'glass_light', off=0.02, depth=0.02, wall=y0)
    for k in range(3):
        zz = z0 + 0.34 + k * 0.38
        b.decal('front', x0 + 0.11, x0 + w - 0.11, zz, zz + 0.2, rng.choice(GOODS), off=0.035, wall=y0)
    b.decal('front', x0 + 0.08, x0 + w - 0.08, z0 + h - 0.28, z0 + h - 0.08, 'sign_white', off=0.02, wall=y0)


def tyres(b, x, y, z0, n, r=0.3, h=0.19):
    """Stack of motorbike/car tyres; alternate tyres are turned half a segment so every seam gets an ink line."""
    for i in range(n):
        vcyl(b, x, y, z0 + i * h, z0 + (i + 1) * h, r, TYRE, seg=8, phase=(math.pi / 8) * (i % 2))
    ngon(b, x, y, z0 + n * h + 0.02, r * 0.55, TYRE_HOLE, seg=8, phase=(math.pi / 8) * ((n - 1) % 2))


def toren(b, cx, cy, zbase, color, r=0.45, h=0.95, stand=0.45, spread=0.3, legs_z=None, brace=False):
    """Toren air (water tank) on a steel stand. legs_z(x, y) gives the surface under each leg (sloped roofs)."""
    if legs_z:
        zbase = max(legs_z(cx + dx, cy + dy) for dx in (-spread, spread) for dy in (-spread, spread))
    zt = zbase + stand
    for dx in (-spread, spread):
        for dy in (-spread, spread):
            zl = legs_z(cx + dx, cy + dy) - 0.03 if legs_z else zbase
            b.box(cx + dx - 0.035, cy + dy - 0.035, zl, cx + dx + 0.035, cy + dy + 0.035, zt - 0.06, 'metal', skip=('bottom', 'top'))
    if brace:
        zm = zbase + stand * 0.45
        for dy in (-spread, spread):
            b.box(cx - spread, cy + dy - 0.025, zm - 0.025, cx + spread, cy + dy + 0.025, zm + 0.025, 'metal', skip=())
        for dx in (-spread, spread):
            b.box(cx + dx - 0.025, cy - spread, zm + 0.35, cx + dx + 0.025, cy + spread, zm + 0.4, 'metal', skip=())
    b.box(cx - spread - 0.07, cy - spread - 0.07, zt - 0.06, cx + spread + 0.07, cy + spread + 0.07, zt, 'metal', skip=())
    vcyl(b, cx, cy, zt, zt + h, r, color, seg=10)
    vcyl(b, cx, cy, zt + h, zt + h + 0.06, r * 0.4, color, seg=6)


def jemuran(b, x0, x1, y, z0, h, rng, colors=CLOTHES, post_color='metal'):
    """Clothes line along x with colourful garments (double-sided: seen from front and back cameras)."""
    for px in (x0, x1):
        b.box(px - 0.03, y - 0.03, z0, px + 0.03, y + 0.03, z0 + h, post_color)
    zl = z0 + h - 0.08
    b.box(x0 + 0.03, y - 0.008, zl - 0.008, x1 - 0.03, y + 0.008, zl + 0.008, post_color, skip=())
    u = x0 + 0.14
    k = rng.randrange(len(colors))
    while True:
        w = rng.uniform(0.34, 0.6)
        if u + w > x1 - 0.1:
            break
        hh = min(h - 0.28, rng.uniform(0.4, 0.72))
        col = colors[k % len(colors)]
        k += rng.randint(1, 3)
        b.decal('front', u, u + w, zl - hh, zl + 0.012, col, off=0.02, wall=y)
        b.decal('back', u, u + w, zl - hh, zl + 0.012, col, off=0.02, wall=y)
        u += w + rng.uniform(0.07, 0.16)


def dish(b, cx, cy, z0, r=0.36, tilt=55, face=-1):
    """Satellite dish on a short pole, facing front (face=-1) or back (+1) and tilted up."""
    a = math.radians(tilt)
    zc = z0 + 0.62
    post(b, cx, cy, z0, zc + 0.02, 'metal', s=0.06)
    u = (1.0, 0.0, 0.0)
    vv = (0.0, math.cos(a) * -face, math.sin(a))
    ring = [(cx + r * math.cos(t) * u[0], cy + r * math.sin(t) * vv[1], zc + r * math.sin(t) * vv[2])
            for t in [2 * math.pi * i / 8 for i in range(8)]]
    # normal of the increasing-angle ring is u x v = (0, -v_z, v_y)
    if face < 0:
        b.face(ring, '#e6e6e0')
        b.face(ring[::-1], '#9aa1a6')
    else:
        b.face(ring[::-1], '#e6e6e0')
        b.face(ring, '#9aa1a6')


def gerobak(b, x0, y0, z0, accent='sign_red', body='#f3efe2', L=1.45, Wd=0.62):
    """Street-food cart: cabinet on two bicycle wheels, glass display box and a little roof on four posts."""
    zb = z0 + 0.36
    for yw in (y0 - 0.06, y0 + Wd):
        ycyl(b, yw, yw + 0.06, x0 + L * 0.42, z0 + 0.3, 0.3, TYRE, seg=8)
    b.box(x0 + L - 0.14, y0 + Wd / 2 - 0.04, z0, x0 + L - 0.06, y0 + Wd / 2 + 0.04, zb, 'metal')  # front leg
    b.box(x0, y0, zb, x0 + L, y0 + Wd, zb + 0.52, body, skip=())
    b.decal('front', x0 + 0.05, x0 + L - 0.05, zb + 0.14, zb + 0.32, accent, off=0.02, wall=y0)
    b.decal('back', x0 + 0.05, x0 + L - 0.05, zb + 0.14, zb + 0.32, accent, off=0.02, wall=y0 + Wd)
    b.box(x0 + 0.08, y0 + 0.07, zb + 0.52, x0 + L * 0.62, y0 + Wd - 0.07, zb + 0.9, 'glass_light')
    vcyl(b, x0 + L * 0.8, y0 + Wd / 2, zb + 0.52, zb + 0.78, 0.17, 'metal', seg=8)                  # soup pot
    for px in (x0 + 0.04, x0 + L - 0.1):
        for py in (y0 + 0.04, y0 + Wd - 0.1):
            b.box(px, py, zb + 0.52, px + 0.06, py + 0.06, zb + 1.32, 'metal')
    b.box(x0 - 0.05, y0 - 0.06, zb + 1.32, x0 + L + 0.05, y0 + Wd + 0.06, zb + 1.4, accent, skip=())
    b.box(x0 - 0.35, y0 + 0.08, zb + 0.35, x0, y0 + 0.13, zb + 0.4, 'metal')                        # push handles
    b.box(x0 - 0.35, y0 + Wd - 0.13, zb + 0.35, x0, y0 + Wd - 0.08, zb + 0.4, 'metal')


def motor(b, cx, y0, z0, color):
    """Parked scooter pointing to -y (front wheel at y0 + 0.3)."""
    r = 0.26
    yfw, yrw = y0 + 0.3, y0 + 1.45
    xcyl(b, cx - 0.05, cx + 0.05, yfw, z0 + r, r, TYRE, seg=8)
    xcyl(b, cx - 0.05, cx + 0.05, yrw, z0 + r, r, TYRE, seg=8)
    b.box(cx - 0.13, yfw + 0.28, z0 + 0.22, cx + 0.13, yrw - 0.45, z0 + 0.4, color)                  # footboard
    b.box(cx - 0.17, yrw - 0.5, z0 + 0.3, cx + 0.17, yrw + 0.22, z0 + 0.72, color)                   # rear body
    b.box(cx - 0.15, yrw - 0.48, z0 + 0.72, cx + 0.15, yrw + 0.12, z0 + 0.82, '#2a2626')             # seat
    b.box(cx - 0.18, yfw + 0.1, z0 + 0.3, cx + 0.18, yfw + 0.28, z0 + 0.95, color)                   # leg shield
    b.box(cx - 0.035, yfw - 0.035, z0 + 0.2, cx + 0.035, yfw + 0.035, z0 + 0.98, 'metal')            # fork
    b.box(cx - 0.12, yfw - 0.05, z0 + 0.86, cx + 0.12, yfw + 0.12, z0 + 1.02, color)                 # headlight cowl
    b.box(cx - 0.34, yfw + 0.03, z0 + 1.02, cx + 0.34, yfw + 0.1, z0 + 1.07, '#2a2626')              # handlebar


# =============================================================================================== variants
def k_kelontong(b, v, rng):
    """Warung kelontong: counter window with snack strips and an etalase, green tarp on poles, zinc shed roof
    falling to the back, toren on a steel tower behind."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, t, yb = 1.7, 0.22, D - 1.2
    yr = yf + t
    zf, zb = 3.3, 2.75
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    shed_body(b, x0, x1, yf, yr, yb, zf, zb, wall)
    win = (x0 + 0.35, x0 + 3.1, 0.95, 2.45)
    door = (x1 - 1.55, x1 - 0.6, FL, 2.3)
    front_wall(b, x0, x1, yf, t, zf, [win, door], wall)
    interior(b, *win, yr, rng, rows=3)
    snacks(b, win[0] + 0.05, win[1] - 0.05, win[3], yr, rng, n=9)
    open_door(b, *door, yr, curtain=v['curtain'])
    b.panel('front', win[0] - 0.08, win[1] + 0.08, win[2] - 0.03, win[2] + 0.03, WOOD, off=0.14, depth=0.14 + t - 0.04, wall=yf)
    b.sign('front', x0 + 0.3, x1 - 0.3, 2.84, 3.2, v['sign'], wall=yf)
    canopy(b, x0, x1, yf, 0.12, 2.72, 2.36, v['tarp'], thick=0.04, val=0.16, posts=(x0 + 0.1, x1 - 0.1))
    etalase(b, win[0] + 0.1, win[0] + 1.6, yf - 0.5, yf - 0.06, FL, rng)
    bench(b, win[0] + 0.1, win[0] + 1.7, 0.3, 0.62, FL)
    crates(b, x1 - 0.42, 0.5, FL, 3, rng)
    galon(b, win[1] + 0.33, yf - 0.28, FL)
    galon(b, win[1] + 0.33, yf - 0.62, FL)
    # back: door with a little zinc hood, window, crates, gas, toren tower
    b.door('back', x0 + 1.0, 0.85, 2.0, color='door_dark', wall=yb)
    b.window('back', x0 + 2.6, 1.15, 0.9, 0.75, bars=2, wall=yb)
    hood(b, x0 + 0.4, x0 + 1.6, yb, yb + 0.55, 2.4, 2.25, v['roof'])
    crates(b, x0 + 2.35, D - 0.4, 0, 2, rng)
    crates(b, x0 + 2.9, D - 0.4, 0, 1, rng)
    lpg(b, x0 + 0.3, D - 0.35, 0)
    lpg(b, x0 + 0.62, D - 0.3, 0)
    toren(b, x1 - 0.62, D - 0.55, 0, v['tank'], r=0.4, h=0.9, stand=2.45, spread=0.25, brace=True)
    shed_roof(b, x0, x1, yf, yb, zf, zb, v['roof'], ox=0.03, of=0.2, ob=0.2, rib=v['rib'])


def k_makan(b, v, rng):
    """Warung makan: terracotta front-gable house, striped tenda on poles over a long table with benches,
    food display window; kitchen annex with a chimney and a toren behind."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.28, W / 2 - 0.28
    yf, t, yb = 2.5, 0.22, D - 1.9
    yr = yf + t
    h, rise = 3.0, 1.25
    wall = v['wall']
    teras(b, x0 - 0.25, x1 + 0.25, 0.05, yf, yr, 0.12, bx0=x0, bx1=x1)
    gable_body(b, x0, x1, yf, yr, yb, h, rise, wall, ridge='y')
    disp = (x0 + 0.45, x0 + 3.5, 0.85, 2.15)
    door = (x1 - 1.75, x1 - 0.75, 0.12, 2.3)
    front_wall(b, x0, x1, yf, t, h, [disp, door], wall, top=True)
    # food display: glass with trays of food behind it
    glass_front(b, *disp, yr, n=3, frame='window_frame')
    FOOD = ['#e0873a', '#7a9a3a', '#b5542b', '#f2c94c', '#8a5a3a', '#e25d4a']
    for row, zz in enumerate((disp[2] + 0.12, disp[2] + 0.62)):
        u = disp[0] + 0.14
        while u < disp[1] - 0.45:
            b.decal('front', u, u + 0.3, zz, zz + 0.16, rng.choice(FOOD), off=0.075, wall=yr)
            u += 0.42
    open_door(b, *door, yr, curtain=v['curtain'])
    b.sign('front', -1.0, 1.0, 3.12, 3.52, v['sign'], text_color='sign_white', wall=yf)   # on the gable (at yf)
    for k in (-0.35, 0.0, 0.35):                                                    # gable vents
        b.decal('front', k - 0.1, k + 0.1, 3.75, 3.87, '#6b4a33', off=0.02, wall=yf)
    # tenda + long table with benches
    canopy(b, x0 - 0.2, x1 + 0.2, yf, 0.12, 2.62, 2.2, v['tenda'], stripe=v['stripe'], thick=0.05, val=0.24,
           posts=(x0 - 0.12, 0.0, x1 + 0.12), zfloor=0.12)
    table(b, -2.3, 1.1, 1.05, 1.62, 0.12)
    bench(b, -2.3, 1.1, 0.5, 0.82, 0.12)
    bench(b, -2.3, 1.1, 1.85, 2.17, 0.12)
    crates(b, x1 - 0.3, 0.45, 0.12, 2, rng)
    plant(b, x1 - 0.3, 1.2, 0.12, s=0.75)
    # back: kitchen annex (left) with chimney, back door, toren tower (right)
    ax1 = x0 + 3.0
    annex = shed_body(b, x0, ax1, yb, yb, D - 0.2, 2.45, 2.2, 'wall_white')
    b.window('back', x0 + 1.0, 1.25, 0.8, 0.6, bars=2, wall=D - 0.2)
    b.door('back', x0 + 2.3, 0.8, 1.95, color='door_dark', wall=D - 0.2)
    rt = shed_roof(b, x0, ax1, yb, D - 0.2, 2.45, 2.2, 'roof_zinc', ox=0.05, of=0.0, ob=0.12, rib='#8c949a')
    vcyl(b, x0 + 0.6, D - 1.0, rt(D - 1.0) - 0.05, 3.35, 0.08, 'metal', seg=6)
    b.box(x0 + 0.44, D - 1.16, 3.35, x0 + 0.76, D - 0.84, 3.42, 'metal', skip=())
    b.door('back', x1 - 1.3, 0.85, 2.05, color='door_wood', wall=yb)
    lpg(b, ax1 + 0.35, yb + 0.3, 0, big=True)
    lpg(b, ax1 + 0.75, yb + 0.3, 0, big=True)
    bin_(b, ax1 + 0.45, D - 0.4)
    toren(b, x1 - 0.5, D - 0.5, 0, v['tank'], r=0.4, h=0.9, stand=2.6, spread=0.25, brace=True)
    gable_roof(b, x0, x1, yf, yb, h, rise, v['roof'], ridge='y', ox=0.24, oy=0.35, cap='roof_brown', course=v['course'])


def k_bengkel(b, v, rng):
    """Bengkel motor: wide open front under a sign fascia, oil-stained floor, tyre stacks, tool board, workbench,
    a scooter being serviced, half-closed rolling door on one bay; asbestos shed roof with a toren."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, yb = 1.3, D - 1.1
    zf, zb = 3.9, 3.05
    wt = 0.15
    wall = v['wall']
    z = lin(yf, zf, yb, zb)
    b.box(x0, 0.05, 0, x1, yf, 0.08, FLOOR_DARK, skip=('bottom', 'back'))
    face_up(b, [(x0, yf, 0.08), (x1, yf, 0.08), (x1, yb, 0.08), (x0, yb, 0.08)], FLOOR_DARK)
    for (a, c) in ((x0, x0 + wt), (x1 - wt, x1)):
        b.face([(a, yb, 0), (a, yf, 0), (a, yf, zf), (a, yb, zb)], wall)
        b.face([(c, yf, 0), (c, yb, 0), (c, yb, zb), (c, yf, zf)], wall)
        b.face([(a, yf, 0), (c, yf, 0), (c, yf, zf), (a, yf, zf)], wall)
    b.face([(x1, yb, 0), (x0, yb, 0), (x0, yb, zb), (x1, yb, zb)], wall)                   # back wall outside
    yi = yb - wt
    b.face([(x0 + wt, yi, 0), (x1 - wt, yi, 0), (x1 - wt, yi, z(yi)), (x0 + wt, yi, z(yi))], '#e6e1d6')  # inside
    b.decal('front', x0 + wt, x1 - wt, 0.08, 1.0, '#b3aea4', off=0.02, wall=yi)            # grimy dado
    zh = 2.85
    b.box(x0 + wt, yf, zh, x1 - wt, yf + 0.2, zf, wall, skip=('top', 'left', 'right'))     # sign fascia beam
    b.box(-0.14, yf, 0, 0.14, yf + 0.2, zh, wall, skip=('bottom', 'top'))                  # middle column
    rollbox(b, x0 + wt, -0.14, zh, yf + 0.2)
    b.shutter('front', 0.14, x1 - wt, 1.95, zh - 0.02, wall=yf + 0.25, box=False)
    b.sign('front', x0 + 0.5, x1 - 0.5, 3.0, 3.68, v['sign'], text_color='sign_white', wall=yf)
    # tool board + workbench on the back wall, drum, tyres, scooter
    b.panel('front', x0 + 0.8, x0 + 2.8, 1.25, 2.25, '#56655d', off=0.03, depth=0.03, wall=yi)
    for k in range(6):
        u = x0 + 1.0 + k * 0.3
        b.decal('front', u, u + 0.07, 1.45 + 0.1 * (k % 2), 2.05, ['#d6d9dc', '#d93a33'][k % 2], off=0.05, wall=yi)
    b.box(x0 + 0.7, yi - 0.62, 0.08, x0 + 2.9, yi, 0.85, WOOD_DARK)
    b.box(x0 + 0.66, yi - 0.66, 0.85, x0 + 2.94, yi, 0.9, WOOD, skip=())
    drum(b, x1 - 0.55, yi - 0.45, 0.08, color='sign_red')
    drum(b, x1 - 1.15, yi - 0.4, 0.08, color='sign_blue')
    tyres(b, x0 + 0.5, yi - 1.3, 0.08, 4)
    motor(b, -1.4, 2.6, 0.08, '#d93a33')
    tyres(b, x0 + 0.42, 0.5, 0.08, 4)
    tyres(b, x0 + 1.05, 0.45, 0.08, 2)
    tyres(b, x1 - 0.45, 0.55, 0.08, 3)
    for (sx, sy, sr) in ((-0.5, 2.1, 0.38), (1.5, 3.5, 0.34)):                       # soft oil stains in the bay
        ngon(b, sx, sy, 0.1, sr, OIL, seg=10, phase=rng.uniform(0, 1), ry=sr * 0.55)
    bench(b, 1.2, 2.5, 0.35, 0.67, 0.08)
    # back: small door, high window, spare tyres, drum
    b.door('back', x0 + 1.1, 0.85, 2.0, color='door_dark', wall=yb)
    b.window('back', 0.8, 1.6, 1.2, 0.6, bars=3, wall=yb)
    tyres(b, x1 - 1.3, D - 0.45, 0.0, 3)
    drum(b, x1 - 0.5, D - 0.45, 0.0, color='#3f8a4f')
    step = 0.6
    rt = shed_roof(b, x0, x1, yf, yb, zf, zb, v['roof'], ox=0.03, of=0.3, ob=0.25, rib=v['rib'], rib_step=step)
    toren(b, x1 - 1.3, yb - 1.4, 0, v['tank'], r=0.42, h=0.85, stand=0.35, spread=0.3, legs_z=lambda x, y: rt(y))
    # one new (bright) zinc sheet and one rusty sheet among the grey ones, each exactly two corrugations wide
    X0, X1 = x0 - 0.03, x1 + 0.03
    cell = (X1 - X0) / max(3, int(round((X1 - X0) / step)))
    for (i, ya, yb_, col, rb) in ((2, yf + 0.9, yb + 0.1, '#8a96a0', '#6f7a84'), (9, yf - 0.2, yf + 2.2, '#86503a', '#6b3e2c')):
        roof_sheet(b, rt, X0, cell, i, ya, yb_, col, rb)


def k_laundry(b, v, rng):
    """Laundry kiloan: flat-roofed shop with a full glass front showing the washers, purple sign band, slim
    concrete canopy; clothes drying on the roof, toren, washers and AC at the back."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, t, yb = 1.2, 0.22, D - 0.9
    yr = yf + t
    h = 3.2
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    shed_body(b, x0, x1, yf, yr, yb, h, h, wall)
    gl = (x0 + 0.35, x0 + 3.75, 0.45, 2.45)
    door = (x0 + 4.1, x0 + 5.2, FL, 2.4)
    front_wall(b, x0, x1, yf, t, h, [gl, door], wall)
    b.panel('front', gl[0], gl[1], gl[2], gl[3], 'glass_light', off=0.04, depth=0.03, wall=yr)
    for k in range(3):                                          # washers seen through the glass
        u = gl[0] + 0.3 + k * 1.05
        b.decal('front', u, u + 0.8, gl[2] + 0.05, gl[2] + 0.95, '#f4f3ee', off=0.06, wall=yr)
        vngon(b, 'front', u + 0.4, gl[2] + 0.5, 0.26, '#2f3f55', wall=yr, off=0.08, seg=8)
        b.decal('front', u, u + 0.8, gl[2] + 1.0, gl[2] + 1.85, '#e9e7df', off=0.06, wall=yr)
        vngon(b, 'front', u + 0.4, gl[2] + 1.42, 0.24, '#2f3f55', wall=yr, off=0.08, seg=8)
    for u in (gl[0] + 1.18, gl[0] + 2.23):
        b.decal('front', u - 0.03, u + 0.03, gl[2], gl[3], 'window_frame', off=0.095, wall=yr)
    glass_door(b, *door, yr)
    b.box(x0, 0.3, 2.62, x1, yf, 2.74, 'trim_white', skip=())                               # slim canopy
    b.decal('front', x0, x1, 2.62, 2.74, v['sign'], off=0.02, wall=0.3)
    b.sign('front', x0 + 0.2, x1 - 0.2, 2.86, 3.62, v['sign'], text_color='sign_white', wall=yf)
    bench(b, x0 + 0.5, x0 + 1.9, 0.45, 0.8, FL, color='#e9e6de')
    plant(b, x1 - 0.35, 0.55, FL, s=0.8)
    plant(b, x0 + 2.4, 0.5, FL, s=0.7)
    # roof: toren + two clothes lines
    zr = flat_roof(b, x0, x1, yf, yb, h, parapet=wall, ph=0.4)
    toren(b, x0 + 0.9, yb - 0.9, zr, v['tank'], r=0.45, h=0.95, stand=0.38, spread=0.3)
    jemuran(b, x0 + 0.4, x1 - 0.5, 3.4, zr, 1.35, rng)
    jemuran(b, x0 + 0.4, x1 - 0.5, 4.9, zr, 1.35, rng)
    jemuran(b, x0 + 2.0, x1 - 0.5, 6.4, zr, 1.35, rng)
    # back: door, vents, AC, two washers under a lean-to
    b.door('back', x1 - 0.9, 0.85, 2.05, color='door_dark', wall=yb)
    b.window('back', x1 - 2.4, 1.3, 0.8, 0.8, bars=2, wall=yb)
    for u in (x0 + 0.5, x0 + 1.1):
        b.panel('back', u - 0.2, u + 0.2, 2.35, 2.75, '#9aa1a6', off=0.08, depth=0.08, wall=yb)
        b.decal('back', u - 0.14, u + 0.14, 2.41, 2.69, '#3a3634', off=0.1, wall=yb)
    b.ac_unit('back', x0 + 2.4, 2.3, wall=yb)
    for k in range(2):
        u = x0 + 0.5 + k * 0.72
        b.box(u - 0.3, yb + 0.1, 0, u + 0.3, yb + 0.7, 0.85, '#f1f0ea')
        vngon(b, 'back', u, 0.45, 0.2, '#2f3f55', wall=yb + 0.7, off=0.02, seg=8)
    hood(b, x0, x0 + 1.7, yb, D - 0.05, 2.2, 2.0, 'awning_blue')


def k_pulsa(b, v, rng):
    """Kios pulsa: narrow kiosk behind a tall false-front facade carrying a big sign, glass counter, hanging
    voucher strips, small blue awning; zinc shed roof behind the facade."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, t, yb = 1.0, 0.25, D - 0.7
    yr = yf + t
    zfac, zr0, zb = 4.25, 3.4, 2.8
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    shed_body(b, x0, x1, yr, yr, yb, zr0, zb, wall)
    hole = (x0 + 0.32, x1 - 0.32, FL, 2.55)
    front_wall(b, x0, x1, yf, t, zfac, [hole], wall, top=True)
    b.face([(x0, yr, 0), (x0, yf, 0), (x0, yf, zfac), (x0, yr, zfac)], wall)             # facade ends
    b.face([(x1, yf, 0), (x1, yr, 0), (x1, yr, zfac), (x1, yf, zfac)], wall)
    b.face([(x1, yr, zr0), (x0, yr, zr0), (x0, yr, zfac), (x1, yr, zfac)], wall)         # facade back above roof
    b.box(x0, yf - 0.06, zfac, x1, yr + 0.06, zfac + 0.08, 'trim_white', skip=())
    interior(b, hole[0], hole[1], 1.0, 2.35, yr, rng, rows=3)
    b.decal('front', hole[0], hole[1], FL, 1.0, INTERIOR, off=0.02, wall=yr)
    snacks(b, hole[0] + 0.1, hole[1] - 0.1, 2.3, yr, rng, n=7, length=(0.3, 0.5), colors=['#f2c94c', '#e2574c', '#4f9ad8', '#6cc070'])
    rollbox(b, hole[0], hole[1], hole[3], yr)
    b.sign('front', x0 + 0.15, x1 - 0.15, 2.85, 4.05, v['sign'], text_color='sign_white', wall=yf)
    b.decal('front', x0 + 0.28, x0 + 0.62, 3.05, 3.85, 'sign_yellow', off=0.135, wall=yf)
    canopy(b, x0, x1, yf, 0.12, 2.68, 2.42, v['tarp'], stripe='awning_white', thick=0.04, val=0.14,
           posts=(x0 + 0.1, x1 - 0.1))
    etalase(b, hole[0] + 0.05, x1 - 0.95, yf - 0.55, yf - 0.08, FL, rng, base='#3b5570', goods=['#2a2a2e', '#f4f1e8', '#e2574c', '#4f9ad8'])
    b.box(x1 - 0.7, 0.35, FL, x1 - 0.66, 0.39, FL + 0.9, 'metal')                            # standing sign
    b.box(x1 - 0.98, 0.32, FL + 0.45, x1 - 0.38, 0.35, FL + 1.1, 'sign_white', skip=())
    b.decal('front', x1 - 0.9, x1 - 0.46, FL + 0.8, FL + 0.98, v['sign'], off=0.02, wall=0.32)
    b.decal('front', x1 - 0.85, x1 - 0.51, FL + 0.56, FL + 0.68, 'sign_text', off=0.02, wall=0.32)
    stool(b, x0 + 0.55, 0.27, FL, color='sign_blue')
    # back
    b.door('back', x0 + 0.8, 0.8, 1.95, color='door_dark', wall=yb)
    b.window('back', x1 - 1.0, 1.35, 0.7, 0.6, bars=2, wall=yb)
    b.ac_unit('back', x1 - 1.0, 0.45, wall=yb)
    crates(b, x0 + 1.75, D - 0.3, 0, 2, rng)
    rt = shed_roof(b, x0, x1, yr - 0.02, yb, zr0 + (zb - zr0) * -0.02 / (yb - yr), zb, v['roof'], ox=0.03, of=0.0,
                   ob=0.25, rib=v["rib"])
    toren(b, x0 + 0.95, yb - 1.1, 0, v['tank'], r=0.36, h=0.8, stand=0.3, spread=0.24, legs_z=lambda x, y: rt(y))


def k_fotokopi(b, v, rng):
    """Fotokopi: narrow open shop under a blue zinc front gable, deep recess with a counter, copier and paper
    shelves, clear polycarbonate canopy on posts, cardboard boxes."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.2, W / 2 - 0.2
    yf, t, yb = 1.4, 0.95, D - 0.75
    yr = yf + t
    h, rise = 3.0, 1.1
    wall = v['wall']
    teras(b, x0 - 0.15, x1 + 0.15, 0.05, yf, yr, FL, bx0=x0, bx1=x1)
    gable_body(b, x0, x1, yf, yr, yb, h, rise, wall, ridge='y')
    hole = (x0 + 0.3, x1 - 0.3, FL, 2.4)
    front_wall(b, x0, x1, yf, t, h, [hole], wall)
    b.decal('front', x0 + 0.3, x1 - 0.3, FL, 2.4, '#ece6da', off=0.015, wall=yr)
    rollbox(b, hole[0], hole[1], hole[3], yf + 0.3)
    # shelves of paper on the recess back wall
    for k, zz in enumerate((0.6, 1.1, 1.6)):
        b.decal('front', hole[0] + 0.1, hole[1] - 0.1, zz, zz + 0.04, SHELF, off=0.03, wall=yr)
        u = hole[0] + 0.15
        while u < hole[1] - 0.45:
            w = rng.uniform(0.25, 0.4)
            b.decal('front', u, u + w, zz + 0.04, zz + 0.04 + rng.uniform(0.15, 0.3),
                    rng.choice(['#f4f1e8', '#f4f1e8', '#f2c94c', '#4f9ad8', '#e86aa0']), off=0.03, wall=yr)
            u += w + 0.08
    cx0, cx1, cy0, cy1 = x1 - 0.93, x1 - 0.38, yf + 0.15, yf + 0.68                          # copier beside the counter
    b.box(cx0, cy0, FL, cx1, cy1, FL + 1.0, '#dadcd8')
    for zz in (FL + 0.22, FL + 0.46):                                                        # paper drawers
        b.decal('front', cx0 + 0.05, cx1 - 0.05, zz, zz + 0.03, '#8e959b', off=0.02, wall=cy0)
    b.box(cx0, cy0 + 0.02, FL + 1.0, cx1, cy1, FL + 1.1, '#4a4f55')                              # scanner lid
    b.box(cx0 + 0.06, cy0 + 0.12, FL + 1.1, cx1 - 0.06, cy1 - 0.12, FL + 1.14, '#f4f1e8', skip=())   # sheet on the glass
    b.box(cx0 + 0.08, cy0 - 0.12, FL + 0.66, cx1 - 0.08, cy0, FL + 0.7, '#f4f1e8', skip=())      # output tray
    b.decal('front', cx1 - 0.2, cx1 - 0.07, FL + 0.8, FL + 0.9, '#3f73b8', off=0.02, wall=cy0)  # control panel
    b.box(x0 + 0.35, yf + 0.08, FL, x1 - 1.0, yf + 0.42, FL + 0.95, WOOD)                      # counter
    b.box(x0 + 0.3, yf + 0.05, FL + 0.95, x1 - 0.95, yf + 0.46, FL + 1.0, '#f4f1e8', skip=())
    for k, col in enumerate(('#f2c94c', '#fbfaf5', '#e86aa0')):                              # paper reams
        b.box(x0 + 0.55, yf + 0.14, FL + 1.0 + k * 0.07, x0 + 0.85, yf + 0.36, FL + 1.07 + k * 0.07, col)
    b.sign('front', -0.9, 0.9, 3.08, 3.45, v['sign'], text_color='sign_white', wall=yf)
    slab(b, [(x0 - 0.1, yf, 2.62), (x1 + 0.1, yf, 2.62), (x1 + 0.1, 0.12, 2.42), (x0 - 0.1, 0.12, 2.42)], 0.04,
         '#7cb4c4', band='#5f9aad', n=8, frac=0.24, along=0)                            # tinted polycarbonate
    zc = lin(yf, 2.62, 0.12, 2.42)
    for px in (x0 - 0.05, x1 + 0.05):
        post(b, px, 0.2, FL, zc(0.2) + 0.02, 'metal')
    boxes(b, x0 + 0.25, 0.5, FL, 2, rng, w=0.4, d=0.36, h=0.3)
    stool(b, x0 + 0.85, 0.5, FL, color='sign_red')
    # back
    b.door('back', x0 + 0.8, 0.8, 1.95, color='door_dark', wall=yb)
    b.window('back', x1 - 1.0, 1.3, 0.8, 0.7, bars=2, wall=yb)
    b.ac_unit('back', x1 - 1.0, 2.25, wall=yb)
    bin_(b, x0 + 1.7, D - 0.35, color='#3b78c4')
    boxes(b, x1 - 0.5, D - 0.3, 0, 1, rng, w=0.45, d=0.36, h=0.3)
    gable_roof(b, x0, x1, yf, yb, h, rise, v['roof'], ridge='y', ox=0.16, oy=0.3, cap='#3f5d80', rib=v['rib'])


def k_grosir(b, v, rng):
    """Toko kelontong / grosir: wide shop under a grey hip roof, blue tarp on three posts, counter window with
    snack strips, drinks cooler, closed rolling door bay with gas cylinders; clothes line behind."""
    W, D = b.W, b.D
    over = 0.35
    x0, x1 = -W / 2 + over + 0.02, W / 2 - over - 0.02
    yf, t, yb = 2.0, 0.22, D - 1.1
    yr = yf + t
    h = 3.3
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    shed_body(b, x0, x1, yf, yr, yb, h, h, wall)
    win = (x0 + 0.9, x0 + 3.3, 0.95, 2.4)
    door = (x0 + 3.65, x0 + 4.6, FL, 2.3)
    rd = (x0 + 5.0, x1 - 0.35, FL, 2.5)
    front_wall(b, x0, x1, yf, t, h, [win, door, rd], wall)
    interior(b, *win, yr, rng, rows=3)
    snacks(b, win[0] + 0.05, win[1] - 0.05, win[3], yr, rng, n=8)
    b.panel('front', win[0] - 0.08, win[1] + 0.08, win[2] - 0.03, win[2] + 0.03, WOOD, off=0.14, depth=0.14 + t - 0.04, wall=yf)
    open_door(b, *door, yr, curtain=v['curtain'])
    b.shutter('front', rd[0], rd[1], rd[2], rd[3], wall=yr, box=False)
    b.panel('front', rd[0] - 0.05, rd[1] + 0.05, rd[3], rd[3] + 0.26, 'shutter_dark', off=0.2, depth=0.2, wall=yr)
    b.sign('front', x0 + 0.4, x0 + 4.7, 2.76, 3.18, v['sign'], text_color='sign_white', wall=yf)
    canopy(b, x0, x1, yf, 0.12, 2.64, 2.3, v['tarp'], thick=0.04, val=0.14, posts=(x0 + 0.1, x0 + 4.8, x1 - 0.1))
    fridge(b, x0 + 0.1, yf - 0.62, FL, 'sign_blue', rng)
    etalase(b, win[0] + 0.1, win[0] + 1.6, yf - 0.5, yf - 0.06, FL, rng)
    b.box(x0 + 5.2, yf - 0.55, FL, x0 + 6.4, yf - 0.1, FL + 0.1, 'metal')                     # gas rack
    for k in range(4):
        lpg(b, x0 + 5.38 + k * 0.28, yf - 0.32, FL + 0.1)
    crates(b, x1 - 0.5, 0.5, FL, 3, rng)
    crates(b, x1 - 1.05, 0.5, FL, 2, rng)
    galon(b, x0 + 4.9, 0.45, FL)
    bench(b, win[0] + 0.1, win[0] + 1.7, 0.3, 0.62, FL)
    # back: door, windows, clothes line, crates, bin
    b.door('back', x0 + 1.0, 0.85, 2.05, color='door_dark', wall=yb)
    b.window('back', x0 + 2.6, 1.2, 1.0, 0.9, bars=2, wall=yb)
    b.window('back', x1 - 1.3, 1.2, 1.0, 0.9, bars=2, wall=yb)
    jemuran(b, x0 + 1.9, x1 - 0.3, D - 0.4, 0, 1.85, rng)
    crates(b, x0 + 0.3, D - 0.35, 0, 3, rng)
    bin_(b, x0 + 1.2, D - 0.35)
    hip_roof(b, x0, x1, yf, yb, h, 1.25, v['roof'], v['course'], v['cap'], over=over, thick=0.12)


def k_warkop(b, v, rng):
    """Warung kopi: long rusty-zinc roof falling to the street on wooden posts, open counter with jars and coffee
    sachet strips, benches, hanging banner between two posts; tall back wall with door, window and drums."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, t, yb = 2.1, 0.22, D - 0.85
    yr = yf + t
    z = lin(0.12, 2.42, yb, 3.5)
    zf, zb = z(yf), 3.5
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, 0.12)
    shed_body(b, x0, x1, yf, yr, yb, zf, zb, wall)
    ctr = (x0 + 0.3, x1 - 1.35, 0.95, 2.25)
    door = (x1 - 1.1, x1 - 0.25, 0.12, 2.2)
    front_wall(b, x0, x1, yf, t, zf, [ctr, door], wall)
    interior(b, *ctr, yr, rng, rows=2)
    snacks(b, ctr[0] + 0.05, ctr[1] - 0.05, ctr[3], yr, rng, n=11, length=(0.45, 0.75),
           colors=['#6b3f26', '#e2574c', '#f2c94c', '#2a2626', '#f08a3c'])
    b.panel('front', ctr[0] - 0.08, ctr[1] + 0.08, ctr[2] - 0.04, ctr[2] + 0.03, WOOD, off=0.22, depth=0.22 + t - 0.04, wall=yf)
    for k in range(4):                                           # toples (snack jars) on the counter
        xc = ctr[0] + 0.3 + k * 0.42
        vcyl(b, xc, yf - 0.08, ctr[2] + 0.03, ctr[2] + 0.25, 0.1, 'glass_light', seg=6, top=False)
        vcyl(b, xc, yf - 0.08, ctr[2] + 0.25, ctr[2] + 0.3, 0.105, ['#e2574c', '#f2c94c', '#3b78c4'][k % 3], seg=6)
    vcyl(b, ctr[1] - 0.25, yf - 0.06, ctr[2] + 0.03, ctr[2] + 0.36, 0.08, '#d93a33', seg=6)  # thermos
    open_door(b, *door, yr, curtain=v['curtain'])
    rt = shed_roof(b, x0, x1, yf, yb, zf, zb, v['roof'], ox=0.03, of=yf - 0.12, ob=0.25, rib=v['rib'])
    toren(b, x0 + 0.9, yb - 1.0, 0, v['tank'], r=0.38, h=0.8, stand=0.3, spread=0.24, legs_z=lambda x, y: rt(y))
    # blue fibreglass sheet over the seating in front (lets light onto the benches), two corrugations wide
    X0, X1 = x0 - 0.03, x1 + 0.03
    cell = (X1 - X0) / max(3, int(round((X1 - X0) / 0.75)))
    roof_sheet(b, rt, X0, cell, 3, 0.18, yf + 0.7, '#5f93b8', '#4d7ea3')
    for px in (x0 + 0.1, 0.0, x1 - 0.1):
        post(b, px, 0.22, 0.12, z(0.22) + 0.02, WOOD_DARK, s=0.09)
    b.box(x0 + 0.145, 0.2, 1.78, -0.045, 0.24, 2.2, v['sign'], skip=('left', 'right'))       # banner between posts
    b.decal('front', x0 + 0.35, -0.3, 2.0, 2.1, 'sign_text', off=0.02, wall=0.2)
    b.decal('front', x0 + 0.6, -0.55, 1.86, 1.94, 'sign_red', off=0.02, wall=0.2)
    bench(b, ctr[0], ctr[1], 1.3, 1.62, 0.12)
    bench(b, x0 + 0.3, x0 + 1.9, 0.45, 0.77, 0.12)
    stool(b, 0.9, 0.62, 0.12, color='sign_blue')
    plant(b, x1 - 0.45, 0.6, 0.12, s=0.75)
    # back
    b.door('back', x1 - 1.0, 0.85, 2.05, color='door_dark', wall=yb)
    b.window('back', x0 + 1.3, 1.5, 1.1, 0.8, bars=2, wall=yb)
    b.decal('back', x0 + 0.2, x1 - 1.6, 0, 0.45, '#5f8f55', off=0.02, wall=yb)
    b.decal('back', x1 - 0.4, x1 - 0.2, 0, 0.45, '#5f8f55', off=0.02, wall=yb)
    drum(b, x0 + 0.45, D - 0.45, 0, color='sign_blue')
    drum(b, x0 + 1.1, D - 0.4, 0, color='sign_blue')
    lpg(b, x0 + 1.7, D - 0.35, 0)
    hood(b, x1 - 1.6, x1 - 0.35, yb, yb + 0.55, 2.45, 2.28, v['roof'])


def k_bakso(b, v, rng):
    """Warung bakso: house-front warung with a flat concrete dak over the front room (toren, satellite dish, pots,
    clothes line) and a zinc roof over the back; gerobak cart parked in front, orange tarp over a plastic table
    and stools, window with louvres and a wide open eating room."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.04, W / 2 - 0.04
    yf, t, yb = 2.2, 0.22, D - 0.75
    yr = yf + t
    ym = yf + 3.0                     # dak / zinc roof break
    h, zb = 3.1, 2.65
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    b.face([(x0, yb, 0), (x0, yf, 0), (x0, yf, h), (x0, ym, h), (x0, yb, zb)], wall)
    b.face([(x1, yf, 0), (x1, yb, 0), (x1, yb, zb), (x1, ym, h), (x1, yf, h)], wall)
    b.face([(x1, yb, 0), (x0, yb, 0), (x0, yb, zb), (x1, yb, zb)], wall)
    b.face([(x0, yr, 0), (x1, yr, 0), (x1, yr, h), (x0, yr, h)], wall)
    win = (x0 + 0.45, x0 + 2.05, 0.95, 2.2)
    door = (x0 + 2.45, x0 + 3.35, FL, 2.25)
    room = (x0 + 3.75, x1 - 0.35, FL, 2.3)
    front_wall(b, x0, x1, yf, t, h, [win, door, room], wall)
    glass_front(b, *win, yr, n=2, frame='frame_brown')
    for k in range(1, 5):                                                            # nako louvres
        zz = win[2] + (win[3] - win[2]) * k / 5
        b.decal('front', win[0] + 0.06, win[1] - 0.06, zz - 0.015, zz + 0.015, '#5d7f99', off=0.075, wall=yr)
    open_door(b, *door, yr, curtain=v['curtain'])
    b.decal('front', room[0], room[1], room[2], room[3], INTERIOR, off=0.02, wall=yr)
    ta, tb = room[0] + 0.35, room[1] - 0.35                                          # table + stools inside
    b.decal('front', ta, tb, 0.72, 0.78, '#8a6a50', off=0.04, wall=yr)
    for u in (ta + 0.08, tb - 0.14):
        b.decal('front', u, u + 0.06, FL, 0.72, '#8a6a50', off=0.04, wall=yr)
    for u, col in ((ta + 0.45, 'sign_red'), (tb - 0.75, 'sign_blue')):
        b.decal('front', u, u + 0.3, FL, FL + 0.44, col, off=0.04, wall=yr)
    b.sign('front', x0 + 0.3, x0 + 3.45, 2.42, 2.88, v['sign'], text_color='sign_red', wall=yf)
    canopy(b, x0 + 3.55, x1, yf, 0.15, 2.62, 2.28, v['tarp'], thick=0.04, val=0.14, posts=(x0 + 3.62, x1 - 0.1))
    table(b, x0 + 4.0, x0 + 5.3, 0.85, 1.45, FL, top='#e8e2d0', legs='metal')
    for (sx, sy) in ((x0 + 4.25, 0.5), (x0 + 5.0, 0.5), (x0 + 4.25, 1.8), (x0 + 5.0, 1.8)):
        stool(b, sx, sy, FL, color=rng.choice(['sign_red', 'sign_blue']))
    gerobak(b, x0 + 0.65, 0.3, FL, accent='sign_red')
    # dak: toren, dish, pots, short clothes line
    zr = flat_roof(b, x0, x1, yf, ym, h, parapet='trim_white', ph=0.35)
    toren(b, x1 - 1.0, ym - 0.85, zr, v['tank'], r=0.45, h=0.95, stand=0.4, spread=0.3)
    dish(b, x0 + 0.75, yf + 0.9, zr, face=-1)
    plant(b, x1 - 0.45, yf + 0.5, zr, s=0.75)
    plant(b, x1 - 1.1, yf + 0.5, zr, s=0.75)
    jemuran(b, x0 + 0.35, x0 + 3.0, ym - 0.9, zr, 1.25, rng)
    # zinc roof over the back rooms
    shed_roof(b, x0, x1, ym - 0.03, yb, h + (zb - h) * -0.03 / (yb - ym), zb, 'roof_zinc', ox=0.03, of=0.0, ob=0.25,
              rib='#8c949a')
    # back: door with zinc hood, window, gas + crates, bin
    b.door('back', x0 + 1.2, 0.85, 2.0, color='door_wood', wall=yb)
    b.window('back', x1 - 1.6, 1.15, 1.2, 0.8, bars=3, wall=yb)
    hood(b, x0 + 0.5, x0 + 2.0, yb, D - 0.08, 2.3, 2.15, 'awning_orange')
    lpg(b, x0 + 2.3, yb + 0.35, 0, big=True)
    crates(b, x1 - 0.5, D - 0.35, 0, 3, rng)
    bin_(b, x1 - 1.2, D - 0.35)


def k_depot(b, v, rng):
    """Depot air isi ulang: white shop with a green zinc gable roof, glass front, blue sign, white canopy and a
    two-tier rack of blue gallons; toren tower and blue filter tubes behind."""
    W, D = b.W, b.D
    x0, x1 = -W / 2 + 0.3, W / 2 - 0.3
    yf, t, yb = 1.8, 0.22, D - 1.2
    yr = yf + t
    h, rise = 3.4, 1.05
    wall = v['wall']
    teras(b, x0, x1, 0.05, yf, yr, FL)
    gable_body(b, x0, x1, yf, yr, yb, h, rise, wall, ridge='x')
    gl = (x0 + 0.3, x0 + 3.6, 0.4, 2.45)
    door = (x0 + 3.95, x0 + 4.95, FL, 2.35)
    win = (x0 + 5.3, x1 - 0.3, 1.0, 2.2)
    front_wall(b, x0, x1, yf, t, h, [gl, door, win], wall)
    glass_front(b, *gl, yr, n=3, transom=2.0, frame='frame_black')
    pane = (gl[1] - gl[0]) / 3
    for k in range(3):                                                                   # filling station inside
        for j in (0.18, 0.58):
            u = gl[0] + k * pane + j * pane
            b.decal('front', u, u + 0.26, 0.5, 0.95, GALON_CAP, off=0.05, wall=yr)
    glass_door(b, *door, yr)
    glass_front(b, *win, yr, n=2, frame='frame_black')
    b.box(x0, 0.35, 2.55, x1, yf, 2.68, 'trim_white', skip=())                                   # ACP canopy
    b.decal('front', x0, x1, 2.55, 2.68, v['sign'], off=0.02, wall=0.35)
    b.sign('front', x0 + 0.3, x1 - 0.3, 2.84, 3.28, v['sign'], text_color='sign_white', wall=yf)
    # gallon rack
    rx0, rx1, ry0, ry1 = x1 - 1.6, x1 - 0.1, 0.4, 0.85
    for px in (rx0, rx1 - 0.05):
        b.box(px, ry0, FL, px + 0.05, ry1, FL + 1.25, 'metal', skip=('bottom', 'top'))
    for zz in (FL + 0.1, FL + 0.7):
        b.box(rx0 + 0.05, ry0, zz - 0.04, rx1 - 0.05, ry1, zz, 'metal', skip=())
        for k in range(3):
            galon(b, rx0 + 0.3 + k * 0.46, (ry0 + ry1) / 2, zz)
    b.box(rx0, ry0, FL + 1.25, rx1, ry1, FL + 1.29, 'metal', skip=())
    galon(b, x0 + 0.5, 0.55, FL)
    galon(b, x0 + 0.85, 0.5, FL)
    plant(b, x0 + 3.8, 0.5, FL, s=0.75)
    # back: door, window, filter tubes under a hood, toren tower
    b.door('back', x0 + 1.0, 0.85, 2.05, color='door_dark', wall=yb)
    b.window('back', x0 + 2.8, 1.25, 1.0, 0.8, bars=2, wall=yb)
    for k in range(3):
        xc = x1 - 2.4 + k * 0.42
        vcyl(b, xc, yb + 0.25, 0, 1.35, 0.16, '#3b78c4', seg=8)
        vcyl(b, xc, yb + 0.25, 1.35, 1.45, 0.06, 'metal', seg=6)
    hood(b, x1 - 2.75, x1 - 1.4, yb, yb + 0.7, 1.85, 1.7, 'roof_green')
    b.box(x1 - 1.0, D - 1.0, 0, x1, D - 0.02, 0.3, 'concrete')                                # ground tank on a block
    vcyl(b, x1 - 0.5, D - 0.51, 0.3, 1.4, 0.45, v['tank'], seg=10)
    vcyl(b, x1 - 0.5, D - 0.51, 1.4, 1.47, 0.18, v['tank'], seg=6)
    gable_roof(b, x0, x1, yf, yb, h, rise, v['roof'], ridge='x', ox=0.26, oy=0.28, cap='#3f6a4a', rib=v['course'])


KINDS = {
    'kelontong': k_kelontong, 'makan': k_makan, 'bengkel': k_bengkel, 'laundry': k_laundry, 'pulsa': k_pulsa,
    'fotokopi': k_fotokopi, 'grosir': k_grosir, 'warkop': k_warkop, 'bakso': k_bakso, 'depot': k_depot,
}

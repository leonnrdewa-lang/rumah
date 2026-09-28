"""Kantor: mid-rise offices and public-ish buildings of a Jakarta street.

Generic only (no brands, no government emblems, no religious buildings, no readable text). Kinds:
  bank     small bank branch: stone-grey podium, glass entry + ATM lobby, blank fascia band, finned upper floor
  ribbon   3-4 floor office: ribbon windows, vertical sunshade fins, (optionally) a recessed arcade lobby carried by
           every other fin running down as a blade column; or a flush lobby and a light roof deck with a roof garden
  klinik   2-3 floor white clinic / puskesmas with a coloured stripe, drop-off canopy or long front terrace,
           flat roof deck or a red genteng hip (limasan) roof
  sekolah  2 floor school: open front corridor with columns, cream + green trims, orange genteng hip roof, fence + blank name board
  glass    4 floor office: blue glass curtain wall + solid coloured stair core with a blank sign, monument sign
  grid     3 floor narrow office: portal frame around a dark infill with a window grid, shop-style fascia
  publik   2 floor public service office: double-height portico with round columns, walled front yard

Everything is built from boxes and single-quad decals (see common.py) so the models stay clean and under
1200 triangles. Flat roofs are decks inside a parapet and carry what you see on Jakarta office roofs from above:
AC condensers, toren / panel water tanks, stair bulkheads, masts, solar panels.
Colours were picked under the game's warm toon light: plain greys turn peach there, so the greys here are
slightly blue to read neutral.
"""
TYPE = 'kantor'
ROLES = ['front', 'fill']

SIDE = 0.06   # side walls sit this far inside the lot so window decals on them never poke out
BACK = 0.35   # back walls carrying hanging AC condensers sit this far inside the lot

# local colours (sRGB hex) on top of common.PALETTE
K = {
    'stone': '#7f8a94', 'granite': '#4a5159', 'alu': '#c8d0d8', 'alu_dark': '#6f7c88', 'panel_grey': '#b4c0cb',
    'glass_blue': '#4f86b8', 'glass_teal': '#3d7c86', 'glass_night': '#2c4660',
    'deck': '#5f6b78', 'deck_dark': '#4c5661', 'deck_green': '#5d8a6a', 'deck_red': '#7e5a52', 'deck_blue': '#56708a',
    'deck_sage': '#4f7a66', 'deck_teal': '#3f5f7a', 'deck_brown': '#6e5550', 'deck_tan': '#6a6f78',
    'slab': '#66717d', 'paving': '#9aa3aa', 'paving_warm': '#b5a898', 'line_yellow': '#f0cf3a',
    'bank_green': '#1f6e57', 'gold': '#eec35c',
    'fin_terracotta': '#c8653f', 'fin_navy': '#44587a', 'teal': '#22a39a', 'clinic_green': '#3aa35e',
    'green_trim': '#3f8a4f', 'green_dark': '#2f6b3d', 'core_brick': '#a4503a',
    'charcoal': '#555d66', 'sand': '#dcc49e', 'beige': '#e6d5b8', 'cool_white': '#d3dde6', 'pale_green': '#e2efd9',
    'maroon': '#8c3b3b', 'roof_school': '#3f5f7a', 'core_dark': '#7f3a2a',
    'genteng': '#bd5a2d', 'genteng_dark': '#853719', 'genteng_line': '#9e4722',
    'roof_klinik': '#7c2e24', 'roof_klinik_dark': '#521c15', 'roof_klinik_line': '#68261e',
    'deck_light': '#8f99a3', 'deck_pine': '#35656a',
    'solar': '#2c4a78', 'solar_line': '#9fb4cc', 'tank_grey': '#9fb6c4', 'tank_cream': '#e6dcc2',
    'atm': '#2b3a55', 'screen': '#9fd0e8', 'bench': '#6b5646',
}


def c(k):
    return K.get(k, k)


INNER = {'front': 'back', 'back': 'front', 'left': 'right', 'right': 'left'}


# ------------------------------------------------------------------------------------------ helpers
def pan(b, side, u0, u1, z0, z1, col, off=0.05, depth=None, wall=None, bottom=False, top=True):
    """Like Bld.panel but without the face that points into the wall (never visible) and, unless asked,
    without the bottom face (only visible from below the element)."""
    depth = off if depth is None else depth
    m, _ = b._frame(side, wall)
    (xa, ya), (xb, yb) = m(u0, off - depth), m(u1, off)
    skip = [INNER[side]]
    if not bottom:
        skip.append('bottom')
    if not top:
        skip.append('top')
    b.box(xa, ya, z0, xb, yb, z1, c(col), skip=tuple(skip))


def dec(b, side, u0, u1, z0, z1, col, off=0.02, wall=None):
    b.decal(side, min(u0, u1), max(u0, u1), z0, z1, c(col), off=off, wall=wall)


def win(b, side, u0, u1, z0, z1, glass='glass', frame='window_frame', wall=None, nx=1, ny=1, fw=0.07, sill=None):
    """Flush window made of decals: frame quad, glass quad, mullions/transoms. 4 + 2 per bar triangles."""
    dec(b, side, u0, u1, z0, z1, frame, off=0.02, wall=wall)
    dec(b, side, u0 + fw, u1 - fw, z0 + fw, z1 - fw, glass, off=0.035, wall=wall)
    for i in range(1, nx):
        u = u0 + (u1 - u0) * i / nx
        dec(b, side, u - fw / 2, u + fw / 2, z0 + fw, z1 - fw, frame, off=0.05, wall=wall)
    for j in range(1, ny):
        z = z0 + (z1 - z0) * j / ny
        dec(b, side, u0 + fw, u1 - fw, z - fw / 2, z + fw / 2, frame, off=0.055, wall=wall)
    if sill:
        pan(b, side, u0 - 0.06, u1 + 0.06, z0 - 0.07, z0, sill, off=0.1, wall=wall, bottom=True)


def door(b, side, uc, w, h, col, frame, wall=None, z0=0.0, leaves=1):
    dec(b, side, uc - w / 2 - 0.08, uc + w / 2 + 0.08, z0, z0 + h + 0.08, frame, off=0.02, wall=wall)
    dec(b, side, uc - w / 2, uc + w / 2, z0, z0 + h, col, off=0.035, wall=wall)
    if leaves > 1:
        dec(b, side, uc - 0.025, uc + 0.025, z0, z0 + h, frame, off=0.05, wall=wall)


def fit(a, e, w, gap=0.6):
    """Centres of as many w-wide openings as fit in [a, e] with at least `gap` between them."""
    n = int((e - a + gap) // (w + gap))
    if n <= 0:
        return []
    step = (e - a) / n
    return [a + step * (i + 0.5) for i in range(n)]


def flat_block(b, x0, x1, y0, y1, z0, z1, wall, deck, ph=0.9, t=0.2, cap=None, bottom=False):
    """Walls from z0 up to the parapet top z1+ph, roof deck at z1 inside the parapet ring. 26 triangles."""
    wall, deck = c(wall), c(deck)
    zt = z1 + ph
    b.box(x0, y0, z0, x1, y1, zt, wall, skip=('top',) if bottom else ('top', 'bottom'))
    xi0, xi1, yi0, yi1 = x0 + t, x1 - t, y0 + t, y1 - t
    b.face([(xi0, yi0, z1), (xi1, yi0, z1), (xi1, yi1, z1), (xi0, yi1, z1)], deck)
    b.face([(xi1, yi0, z1), (xi0, yi0, z1), (xi0, yi0, zt), (xi1, yi0, zt)], wall)   # inner of front parapet (+y)
    b.face([(xi0, yi1, z1), (xi1, yi1, z1), (xi1, yi1, zt), (xi0, yi1, zt)], wall)   # inner of back parapet (-y)
    b.face([(xi0, yi0, z1), (xi0, yi1, z1), (xi0, yi1, zt), (xi0, yi0, zt)], wall)   # inner of left parapet (+x)
    b.face([(xi1, yi1, z1), (xi1, yi0, z1), (xi1, yi0, zt), (xi1, yi1, zt)], wall)   # inner of right parapet (-x)
    cc = c(cap) if cap else wall
    b.face([(x0, y0, zt), (x1, y0, zt), (x1, yi0, zt), (x0, yi0, zt)], cc)
    b.face([(x0, yi1, zt), (x1, yi1, zt), (x1, y1, zt), (x0, y1, zt)], cc)
    b.face([(x0, yi0, zt), (xi0, yi0, zt), (xi0, yi1, zt), (x0, yi1, zt)], cc)
    b.face([(xi1, yi0, zt), (x1, yi0, zt), (x1, yi1, zt), (xi1, yi1, zt)], cc)


def band(b, x0, x1, y0, y1, z0, z1, col, sides=('front', 'back', 'left', 'right'), off=0.01):
    """Horizontal colour stripe wrapped around a block (decals, below the window/door decals)."""
    for s in sides:
        if s == 'front':
            dec(b, 'front', x0, x1, z0, z1, col, off=off, wall=y0)
        elif s == 'back':
            dec(b, 'back', x0, x1, z0, z1, col, off=off, wall=y1)
        elif s == 'left':
            dec(b, 'left', y0, y1, z0, z1, col, off=off, wall=x0)
        else:
            dec(b, 'right', y0, y1, z0, z1, col, off=off, wall=x1)


# ---- roof props
def ac(b, x, y, z, face='front'):
    """Rooftop AC condenser (box + fan grille on its front or back)."""
    b.box(x - 0.42, y - 0.17, z, x + 0.42, y + 0.17, z + 0.62, 'ac_white')
    if face == 'front':
        dec(b, 'front', x - 0.34, x + 0.06, z + 0.1, z + 0.5, 'metal', wall=y - 0.17)
    else:
        dec(b, 'back', x - 0.06, x + 0.34, z + 0.1, z + 0.5, 'metal', wall=y + 0.17)


def ac_row(b, x0, x1, y, z, n, face='front'):
    for i in range(max(0, n)):
        ac(b, x0 + (x1 - x0) * (i + 0.5) / n, y, z, face)


def toren(b, x, y, z, col='tank_orange', r=0.55, h=1.1, stand=0.45):
    """Round plastic water tank on a small concrete stand."""
    b.box(x - r - 0.08, y - r - 0.08, z, x + r + 0.08, y + r + 0.08, z + stand, c('slab'))
    b.cyl(x, y, z + stand, z + stand + h, r, c(col), seg=8)
    b.cyl(x, y, z + stand + h, z + stand + h + 0.12, r * 0.35, c(col), seg=6)


def panel_tank(b, x0, x1, y0, y1, z, h=1.4, col='tank_grey', leg=0.5):
    """Sectional (panel) water tank on a steel frame, the usual one on office roofs."""
    for yy in (y0 + 0.1, y1 - 0.25):
        b.box(x0 + 0.1, yy, z, x1 - 0.1, yy + 0.15, z + leg, 'metal')
    b.box(x0, y0, z + leg, x1, y1, z + leg + h, c(col), skip=())
    zz = z + leg
    n = max(2, int(round((x1 - x0) / 0.8)))
    for i in range(1, n):
        u = x0 + (x1 - x0) * i / n
        dec(b, 'front', u - 0.025, u + 0.025, zz + 0.05, zz + h - 0.05, 'alu_dark', wall=y0)
        dec(b, 'back', u - 0.025, u + 0.025, zz + 0.05, zz + h - 0.05, 'alu_dark', wall=y1)
    dec(b, 'front', x0 + 0.05, x1 - 0.05, zz + h / 2 - 0.025, zz + h / 2 + 0.025, 'alu_dark', off=0.03, wall=y0)
    dec(b, 'back', x0 + 0.05, x1 - 0.05, zz + h / 2 - 0.025, zz + h / 2 + 0.025, 'alu_dark', off=0.03, wall=y1)


def bulkhead(b, x0, x1, y0, y1, z, h, wall, roofc='slab', door_col='door_dark', band_col=None):
    """Stair / lift room on a flat roof with a door towards the street and a thin roof slab."""
    b.box(x0, y0, z, x1, y1, z + h, c(wall), skip=('bottom', 'top'))
    b.box(x0 - 0.12, y0 - 0.12, z + h, x1 + 0.12, y1 + 0.12, z + h + 0.16, c(roofc), skip=())
    xc = x0 + 0.75 if x1 - x0 > 2.0 else (x0 + x1) / 2
    door(b, 'front', xc, 0.85, 1.95, door_col, 'trim_dark', wall=y0, z0=z)
    win(b, 'back', (x0 + x1) / 2 - 0.4, (x0 + x1) / 2 + 0.4, z + 1.2, z + 1.8, glass='glass', frame='trim_white', wall=y1)
    if band_col:
        band(b, x0, x1, y0, y1, z + h - 0.35, z + h - 0.12, band_col, off=0.02)


def mast(b, x, y, z, h, col='metal'):
    b.box(x - 0.05, y - 0.05, z, x + 0.05, y + 0.05, z + h, col)


def solar(b, x0, x1, y0, y1, z, rise=0.45):
    """A row of solar panels tilted towards the street (the game camera sees their face)."""
    top = [(x0, y0, z + 0.3), (x1, y0, z + 0.3), (x1, y1, z + 0.3 + rise), (x0, y1, z + 0.3 + rise)]
    bot = [(p[0], p[1], p[2] - 0.06) for p in top]
    b._slab(top, bot, c('solar'))
    b.box(x0 + 0.2, y1 - 0.2, z, x1 - 0.2, y1 - 0.08, z + 0.3 + rise - 0.06, 'metal')
    b.box(x0 + 0.2, y0 + 0.05, z, x1 - 0.2, y0 + 0.15, z + 0.26, 'metal')
    n = max(1, int(round((x1 - x0) / 1.0)))
    for i in range(1, n):
        u = x0 + (x1 - x0) * i / n
        za, zb = z + 0.3 + 0.004, z + 0.3 + rise + 0.004
        b.face([(u - 0.02, y0, za), (u + 0.02, y0, za), (u + 0.02, y1, zb), (u - 0.02, y1, zb)], c('solar_line'))


def paving(b, x0, x1, y0, y1, h=0.12, col='paving'):
    b.box(x0, y0, 0, x1, y1, h, c(col), skip=('bottom', 'back'))


def planter(b, x0, x1, y0, y1, z=0.0, h=0.5, col='concrete'):
    b.box(x0, y0, z, x1, y1, z + h, c(col))
    b.box(x0 + 0.08, y0 + 0.08, z + h, x1 - 0.08, y1 - 0.08, z + h + 0.35, 'plant')


def downpipe(b, side, u, z0, z1, wall=None, col='alu_dark'):
    pan(b, side, u - 0.06, u + 0.06, z0, z1, col, off=0.14, depth=0.1, wall=wall)


def wall_ac(b, side, uc, z0, wall=None):
    """Split-AC condenser hanging on a wall (common.ac_unit, 0.32 m proud)."""
    b.ac_unit(side, uc, z0, wall=wall)


def face_to(b, pts, col, want):
    """Polygon wound so that its normal points along `want` (Newell normal, flipped when needed)."""
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        (x0, y0, z0), (x1, y1, z1) = pts[i], pts[(i + 1) % len(pts)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    if nx * want[0] + ny * want[1] + nz * want[2] < 0:
        pts = pts[::-1]
    b.face(list(pts), c(col))


def hip_roof(b, x0, x1, y0, y1, z0, rise, col, over=0.45, thick=0.14, cap=None, fascia=None, courses=0,
             course_col=None):
    """common.roof_hip (limasan) plus what makes it read as a real genteng roof from the game camera:
    raised ridge + hip caps (small tents), tile courses as thin contour strips, and a fascia board on the eaves."""
    b.roof_hip(x0, x1, y0, y1, z0, rise, c(col), over=over, thick=thick)
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    w, d = X1 - X0, Y1 - Y0
    run = min(w, d) / 2
    k = rise / run
    zb = z0 + thick

    def zr(x, y):   # every slope of a limasan has the same pitch: height = distance to the nearest eave
        return zb + k * max(0.0, min(x - X0, X1 - x, y - Y0, Y1 - y, run))

    if courses and course_col:
        cw = 0.07
        for i in range(1, courses + 1):
            u = run * i / (courses + 1)
            v_ = u + cw
            za, zc = zb + k * u + 0.008, zb + k * v_ + 0.008
            rings = [
                [(X0 + u, Y0 + u, za), (X1 - u, Y0 + u, za), (X1 - v_, Y0 + v_, zc), (X0 + v_, Y0 + v_, zc)],
                [(X1 - u, Y0 + u, za), (X1 - u, Y1 - u, za), (X1 - v_, Y1 - v_, zc), (X1 - v_, Y0 + v_, zc)],
                [(X1 - u, Y1 - u, za), (X0 + u, Y1 - u, za), (X0 + v_, Y1 - v_, zc), (X1 - v_, Y1 - v_, zc)],
                [(X0 + u, Y1 - u, za), (X0 + u, Y0 + u, za), (X0 + v_, Y0 + v_, zc), (X0 + v_, Y1 - v_, zc)],
            ]
            for q in rings:
                face_to(b, q, course_col, (0, 0, 1))

    if cap:
        hwc, hc = 0.09, 0.07

        def tent(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            L = (dx * dx + dy * dy) ** 0.5
            ux, uy = dx / L, dy / L
            px, py = -uy, ux
            a0, a1 = (p[0], p[1], zr(*p) + hc), (q[0], q[1], zr(*q) + hc)
            for s in (1, -1):
                l0 = (p[0] + s * px * hwc, p[1] + s * py * hwc)
                l1 = (q[0] + s * px * hwc, q[1] + s * py * hwc)
                face_to(b, [a0, a1, (l1[0], l1[1], zr(*l1) + 0.012), (l0[0], l0[1], zr(*l0) + 0.012)], cap, (s * px, s * py, 1))
            for pt, a, sg in ((p, a0, -1), (q, a1, 1)):
                l = (pt[0] + px * hwc, pt[1] + py * hwc)
                r = (pt[0] - px * hwc, pt[1] - py * hwc)
                face_to(b, [a, (l[0], l[1], zr(*l) + 0.012), (r[0], r[1], zr(*r) + 0.012)], cap, (sg * ux, sg * uy, 0))

        ym, xm = (Y0 + Y1) / 2, (X0 + X1) / 2
        if w >= d:
            r0, r1 = (X0 + run, ym), (X1 - run, ym)
            ends = [((X0, Y0), r0), ((X0, Y1), r0), ((X1, Y0), r1), ((X1, Y1), r1)]
        else:
            r0, r1 = (xm, Y0 + run), (xm, Y1 - run)
            ends = [((X0, Y0), r0), ((X1, Y0), r0), ((X0, Y1), r1), ((X1, Y1), r1)]
        if abs(w - d) > 0.2:
            tent(r0, r1)
        for cc, rr in ends:
            ddx, ddy = rr[0] - cc[0], rr[1] - cc[1]
            L = (ddx * ddx + ddy * ddy) ** 0.5
            tent((cc[0] + ddx / L * 0.16, cc[1] + ddy / L * 0.16), rr)

    if fascia:
        ft, fz0, fz1 = 0.04, z0 - 0.12, z0 + thick + 0.03
        f = c(fascia)
        # closed planks: their inner faces show below the soffit when you stand under the eaves
        b.box(X0 - ft, Y0 - ft, fz0, X1 + ft, Y0, fz1, f, skip=())
        b.box(X0 - ft, Y1, fz0, X1 + ft, Y1 + ft, fz1, f, skip=())
        b.box(X0 - ft, Y0, fz0, X0, Y1, fz1, f, skip=('front', 'back'))
        b.box(X1, Y0, fz0, X1 + ft, Y1, fz1, f, skip=('front', 'back'))


def roof_garden(b, x0, x1, y0, y1, z, n=3, col='concrete'):
    """A row of raised planter boxes on a flat roof (roof garden), alternating plant tones."""
    gap = 0.5
    wbox = (x1 - x0 - gap * (n - 1)) / n
    for i in range(n):
        a = x0 + i * (wbox + gap)
        b.box(a, y0, z, a + wbox, y1, z + 0.45, c(col))
        b.box(a + 0.1, y0 + 0.1, z + 0.45, a + wbox - 0.1, y1 - 0.1, z + 0.75, 'plant' if i % 2 == 0 else 'plant_dark')
        # a small tree / shrub head in the middle of every box
        b.cyl(a + wbox / 2, (y0 + y1) / 2, z + 0.75, z + 1.3, 0.33, 'plant_dark' if i % 2 == 0 else 'plant', seg=8)


# ------------------------------------------------------------------------------------------ variants
def variants():
    return [
        # 0: bank branch, green fascia, 2 floors
        dict(kind='bank', w=10.0, d=11.0, stone='stone', wall='panel_grey', fascia='bank_green', emblem='gold',
             deck='deck_green'),
        # 1: 4-floor ribbon office, beige with terracotta fins, arcade lobby
        dict(kind='ribbon', w=14.0, d=12.0, floors=4, wall='beige', fin='fin_terracotta', glass='glass_teal',
             deck='deck', ledges=True, nfins=9, arcade=True, bulkhead=True),
        # 2: 3-floor white clinic, teal stripe, drop-off canopy
        dict(kind='klinik', w=12.0, d=11.0, floors=3, wall='wall_white', stripe='teal', deck='deck_blue',
             entry='dropoff'),
        # 3: 2-floor school, cream + green, orange genteng hip roof
        dict(kind='sekolah', w=16.0, d=12.0, wall='wall_cream', trim='green_trim', roof='genteng',
             roof_cap='genteng_dark', roof_line='genteng_line'),
        # 4: 4-floor glass office with a brick-red core
        dict(kind='glass', w=11.0, d=12.0, floors=4, glass='glass_blue', core='core_brick', wall='wall_white',
             deck='deck_dark', sign='sign_white', sign_bar='core_brick'),
        # 5: narrow 3-floor office with a white portal frame, sand walls, charcoal infill (the one with solar panels)
        dict(kind='grid', w=9.0, d=11.0, floors=3, wall='sand', infill='charcoal', sign='sign_orange', deck='deck_red'),
        # 6: 2-floor public service office with a portico
        dict(kind='publik', w=13.0, d=11.0, wall='wall_white', trim='maroon', deck='deck_pine'),
        # 7: 2-floor puskesmas-like clinic, pale green with a green stripe, long front terrace, red-brown hip roof
        dict(kind='klinik', w=10.0, d=10.0, floors=2, wall='pale_green', stripe='clinic_green', deck='deck_teal',
             entry='terrace', roof='hip', roof_col='roof_klinik', roof_cap='roof_klinik_dark',
             roof_line='roof_klinik_line'),
        # 8: 3-floor ribbon office, cool white with navy fins, flush lobby with canopy, light roof with a roof garden
        dict(kind='ribbon', w=11.5, d=11.0, floors=3, wall='cool_white', fin='fin_navy', glass='glass_blue',
             deck='deck_light', ledges=False, nfins=7, arcade=False, bulkhead=False, gz=3.8, fh=3.3, ph=0.8),
    ]


def build(b, v, rng):
    BUILDERS[v['kind']](b, v, rng)
    # The game only picks 'fill' (back-lot) buildings up to 9 m tall; taller ones are street-front only
    # (south rows accept up to 18 m, side lots up to 12 m). Keep the manifest honest.
    v['roles'] = ['front', 'fill'] if b.top <= 9.0 else ['front']


# ------------------------------------------------------------------------------------------ bank
def build_bank(b, v, rng):
    W, D = b.W, b.D
    hw, yb = W / 2 - SIDE, D - SIDE
    yf, gz, rz = 2.0, 4.2, 7.6
    stone, wall, fas = v['stone'], v['wall'], v['fascia']
    paving(b, -W / 2, W / 2, 0, yf, 0.15)
    # podium (ground floor) in grey stone
    b.box(-hw, yf, 0, hw, yb, gz, c(stone))
    # upper floor, set back on the podium
    ux0, ux1, uy0, uy1 = -hw + 0.3, hw - 0.3, yf + 0.45, yb - 0.3
    flat_block(b, ux0, ux1, uy0, uy1, gz, rz, wall, v['deck'], ph=0.8, cap='alu')
    band(b, ux0, ux1, uy0, uy1, rz + 0.25, rz + 0.45, fas)
    # front: entrance, ATM lobby, window
    win(b, 'front', -1.7, 1.7, 0.15, 3.0, glass='glass_light', frame='granite', wall=yf, nx=4)
    dec(b, 'front', -0.85, 0.85, 0.15, 2.35, 'glass', off=0.045, wall=yf)
    dec(b, 'front', -0.03, 0.03, 0.15, 2.35, 'granite', off=0.06, wall=yf)
    dec(b, 'front', -0.9, 0.9, 2.35, 2.42, 'granite', off=0.06, wall=yf)
    win(b, 'front', -hw + 0.5, -2.3, 0.15, 3.0, glass='glass_light', frame='granite', wall=yf)
    dec(b, 'front', -hw + 0.9, -hw + 1.6, 0.15, 1.9, 'atm', off=0.045, wall=yf)
    dec(b, 'front', -hw + 1.0, -hw + 1.5, 1.2, 1.6, 'screen', off=0.05, wall=yf)
    win(b, 'front', 2.3, hw - 0.5, 0.9, 3.0, glass='glass', frame='granite', wall=yf, nx=2)
    # fascia board (blank: emblem square + one bar)
    pan(b, 'front', -hw + 0.2, hw - 0.2, 3.2, 4.12, fas, off=0.16, wall=yf, bottom=True)
    dec(b, 'front', -hw + 0.55, -hw + 1.3, 3.28, 4.03, v['emblem'], off=0.165, wall=yf)
    dec(b, 'front', -hw + 1.6, 1.2, 3.52, 3.78, 'sign_white', off=0.165, wall=yf)
    # entrance canopy on two slim posts
    b.box(-2.2, 0.35, 3.0, 2.2, yf, 3.18, c('alu'), skip=('back',))
    for x in (-2.0, 2.0):
        b.box(x - 0.06, 0.45, 0.15, x + 0.06, 0.57, 3.0, c('alu_dark'), skip=('bottom', 'top'))
    planter(b, 2.6, hw - 0.3, 0.3, 0.9, z=0.15, h=0.45, col='granite')
    # upper floor front: tall windows between stone fins
    n = 4
    a0, a1 = ux0 + 0.25, ux1 - 0.25
    for i in range(n):
        u0 = a0 + (a1 - a0) * i / n
        u1 = a0 + (a1 - a0) * (i + 1) / n
        win(b, 'front', u0 + 0.3, u1 - 0.3, 4.85, 7.05, glass='glass', frame='alu', wall=uy0, ny=2)
    for i in range(n + 1):
        u = a0 + (a1 - a0) * i / n
        pan(b, 'front', u - 0.12, u + 0.12, gz, rz + 0.6, stone, off=0.38, wall=uy0)
    pan(b, 'front', a0 - 0.12, a1 + 0.12, rz + 0.6, rz + 0.8, stone, off=0.38, wall=uy0, bottom=True)   # cornice
    # sides
    for side, wp, wu in (('left', -hw, ux0), ('right', hw, ux1)):
        win(b, side, yf + 2.2, yf + 3.8, 0.9, 2.8, glass='glass', frame='granite', wall=wp, nx=2)
        for yy in (uy0 + 2.2, uy0 + 4.8):
            win(b, side, yy, yy + 1.4, 5.0, 6.8, glass='glass', frame='alu', wall=wu)
    # back
    door(b, 'back', -hw + 1.4, 1.0, 2.1, 'alu_dark', 'granite', wall=yb)
    for x in (0.2, 2.6):
        win(b, 'back', x, x + 1.2, 1.5, 2.6, glass='glass', frame='granite', wall=yb, nx=2)
    for x in (-3.4, -0.4, 2.6):
        win(b, 'back', x, x + 1.3, 5.0, 6.6, glass='glass', frame='alu', wall=uy1)
    wall_ac(b, 'back', -1.9, 5.2, wall=uy1)
    wall_ac(b, 'back', 1.1, 5.2, wall=uy1)
    downpipe(b, 'back', hw - 0.6, 0, rz + 0.8, wall=uy1)
    # roof: stair bulkhead, a row of AC condensers, panel tank, mast
    left = rng.random() < 0.5
    bx0, bx1 = (ux0 + 0.3, ux0 + 2.6) if left else (ux1 - 2.6, ux1 - 0.3)
    bulkhead(b, bx0, bx1, uy1 - 2.9, uy1 - 0.3, rz, 2.3, 'wall_white', band_col=fas)
    ac_row(b, ux0 + 0.8, ux1 - 0.8, uy0 + 1.6, rz, 4)
    tx0, tx1 = (ux1 - 3.2, ux1 - 0.6) if left else (ux0 + 0.6, ux0 + 3.2)
    panel_tank(b, tx0, tx1, uy1 - 2.3, uy1 - 0.6, rz, h=1.2)
    mast(b, (bx0 + bx1) / 2, uy1 - 1.2, rz + 2.46, 1.1)


# ------------------------------------------------------------------------------------------ ribbon office
def build_ribbon(b, v, rng):
    W, D = b.W, b.D
    hw, yb = W / 2 - SIDE, D - BACK
    yf = 1.6                   # upper facade line
    arcade = v.get('arcade', True)
    yg = 3.0 if arcade else yf  # lobby glass line (recessed under the upper floors when there is an arcade)
    gz, fh, nf, ph = v.get('gz', 4.0), v.get('fh', 3.4), v['floors'], v.get('ph', 1.0)
    rz = gz + fh * (nf - 1)
    wall, fin, glass = v['wall'], v['fin'], v['glass']
    paving(b, -W / 2, W / 2, 0, yg, 0.12)
    # ground floor
    if arcade:
        b.box(-hw, yg, 0, hw, yb, gz, c('granite'), skip=('bottom', 'top'))
        flat_block(b, -hw, hw, yf, yb, gz, rz, wall, v['deck'], ph=ph, cap='alu', bottom=True)
        # (the arcade is carried by every other sunshade fin running down to the paving, see below)
    else:
        flat_block(b, -hw, hw, yf, yb, 0, rz, wall, v['deck'], ph=ph, cap='alu')
        band(b, -hw, hw, yf, yb, 0, gz, 'granite', sides=('front', 'left', 'right', 'back'))
        # entrance canopy
        b.box(-2.4, 0.3, gz - 0.55, 2.4, yf, gz - 0.35, c(fin), skip=('back',))
    win(b, 'front', -hw + 0.5, hw - 0.5, 0.12, gz - 0.6, glass='glass_light', frame='alu_dark', wall=yg,
        nx=max(3, int(W / 2)))
    dec(b, 'front', -1.0, 1.0, 0.12, 2.5, 'glass', off=0.06, wall=yg)
    dec(b, 'front', -0.03, 0.03, 0.12, 2.5, 'alu_dark', off=0.07, wall=yg)
    # ribbon windows per floor
    nb = v['nfins'] - 1
    a0, a1 = -hw + 0.35, hw - 0.35
    for k in range(nf - 1):
        f0 = gz + k * fh
        dec(b, 'front', a0, a1, f0 + 0.9, f0 + 2.75, glass, off=0.03, wall=yf)
        dec(b, 'front', a0, a1, f0 + 0.84, f0 + 0.9, 'alu', off=0.03, wall=yf)
        for i in range(nb):
            u = a0 + (a1 - a0) * (i + 0.5) / nb
            dec(b, 'front', u - 0.03, u + 0.03, f0 + 0.9, f0 + 2.75, 'alu', off=0.04, wall=yf)
        if v.get('ledges'):
            pan(b, 'front', -hw + 0.05, hw - 0.05, f0 + 2.8, f0 + 2.95, 'trim_white', off=0.5, wall=yf, bottom=True)
    # vertical sunshade fins over the whole upper facade; with an arcade every other fin (except the ones
    # over the entrance) continues down to the paving as a blade column, all in the one fin plane
    for i in range(nb + 1):
        u = a0 + (a1 - a0) * i / nb
        if arcade and i % 2 == 0 and abs(u) > 1.3:
            # blade column: closed box (its back is in the open arcade, not against a wall)
            b.box(u - 0.08, yf - 0.7, 0.12, u + 0.08, yf, rz + ph - 0.25, c(fin))
        else:
            pan(b, 'front', u - 0.08, u + 0.08, gz, rz + ph - 0.25, fin, off=0.7, wall=yf, bottom=True)
    # crown beam tying the fins together (a clean edge seen from behind too)
    pan(b, 'front', a0 - 0.08, a1 + 0.08, rz + ph - 0.25, rz + ph, fin, off=0.7, wall=yf, bottom=True)
    # sides: the ribbons wrap the front corner (framed, 3 panes), small high pantry/toilet windows at the back
    for side, w_ in (('left', -hw), ('right', hw)):
        for k in range(nf - 1):
            f0 = gz + k * fh
            win(b, side, yf + 0.3, yf + 4.6, f0 + 0.9, f0 + 2.75, glass=glass, frame='alu', wall=w_, nx=3)
            win(b, side, yb - 2.6, yb - 1.5, f0 + 1.7, f0 + 2.5, glass='glass', frame='alu', wall=w_)
        win(b, side, yg + 1.0, yg + 3.4, 0.9, 2.8, glass='glass', frame='alu_dark', wall=w_, nx=2)
    # back: punched windows, AC condensers, service door, downpipe
    nwin = 4 if W < 13 else 5
    for k in range(nf - 1):
        f0 = gz + k * fh
        for i in range(nwin):
            uc = -hw + 2 * hw * (i + 0.5) / nwin
            win(b, 'back', uc - 0.8, uc + 0.8, f0 + 1.0, f0 + 2.5, glass=glass, frame='alu', wall=yb, nx=2)
        wall_ac(b, 'back', -hw + 2 * hw * ((k % 2) + 1) / nwin, f0 + 0.3, wall=yb)
    door(b, 'back', -hw + 1.3, 1.6, 2.4, 'shutter', 'granite', wall=yb)
    for i in range(2, nwin):
        uc = -hw + 2 * hw * (i + 0.5) / nwin
        win(b, 'back', uc - 0.6, uc + 0.6, 1.4, 2.6, glass='glass', frame='alu_dark', wall=yb)
    downpipe(b, 'back', -hw + 2 * hw * (nwin - 1) / nwin, 0, rz + ph, wall=yb)   # on the pier between windows
    band(b, -hw, hw, yf, yb, rz + 0.3, rz + 0.55, fin)
    # roof
    right = rng.random() < 0.5
    if v.get('bulkhead', True):
        cx0, cx1 = (hw - 4.2, hw - 0.5) if right else (-hw + 0.5, -hw + 4.2)
        bulkhead(b, cx0, cx1, yb - 4.4, yb - 0.5, rz, 2.5, wall, band_col=fin)
        mast(b, (cx0 + cx1) / 2 + 0.8, yb - 1.2, rz + 2.66, 0.9)
        tx0, tx1 = (-hw + 0.7, -hw + 3.7) if right else (hw - 3.7, hw - 0.7)
        panel_tank(b, tx0, tx1, yb - 3.2, yb - 0.7, rz, h=1.5, col='tank_grey')
        ac_row(b, -hw + 1.2, hw - 1.2, yf + 1.4, rz, 6)
        ac_row(b, -hw + 2.2, hw - 5.0 if right else hw - 2.2, yf + 3.0, rz, 4 if right else 5)
    else:
        # light roof deck: small stair house, panel tank, AC row along the front, a roof garden in the middle
        tx0, tx1 = (hw - 3.4, hw - 0.7) if right else (-hw + 0.7, -hw + 3.4)
        panel_tank(b, tx0, tx1, yb - 2.8, yb - 0.7, rz, h=1.2, col='tank_cream', leg=0.3)
        sx0, sx1 = (-hw + 0.5, -hw + 3.0) if right else (hw - 3.0, hw - 0.5)
        bulkhead(b, sx0, sx1, yb - 3.0, yb - 0.5, rz, 2.2, 'cool_white', band_col=fin)
        ac_row(b, -hw + 1.0, hw - 1.0, yf + 1.3, rz, 5)
        roof_garden(b, -hw + 0.8, hw - 0.8, yf + 2.6, yf + 3.6, rz, n=3)


# ------------------------------------------------------------------------------------------ klinik / puskesmas
def build_klinik(b, v, rng):
    W, D = b.W, b.D
    hip = v.get('roof') == 'hip'
    # a hip roof overhangs its walls, so those walls sit 0.5 m inside the lot on the sides and at the back
    hw, yb = (W / 2 - 0.5, D - 0.5) if hip else (W / 2 - SIDE, D - BACK)
    dropoff = v.get('entry', 'dropoff') == 'dropoff'
    yf = 3.0 if dropoff else 2.4
    fz = [0.0, 3.5, 6.8, 10.1][:v['floors'] + 1]
    rz = fz[-1]
    ph = 0.0 if hip else 0.75
    wall, st = v['wall'], v['stripe']
    paving(b, -W / 2, W / 2, 0, yf, 0.15)
    if hip:
        b.box(-hw, yf, 0, hw, yb, rz, c(wall), skip=('bottom', 'top'))
        hip_roof(b, -hw, hw, yf, yb, rz, 1.9, v['roof_col'], over=0.45, thick=0.14, cap=v['roof_cap'],
                 fascia='trim_white', courses=3, course_col=v['roof_line'])
    else:
        flat_block(b, -hw, hw, yf, yb, 0, rz, wall, v['deck'], ph=ph, cap=st)
    # coloured stripes at the floor lines + fascia band under the parapet cap (or under the eaves) + plinth
    for z in fz[1:-1]:
        band(b, -hw, hw, yf, yb, z - 0.25, z + 0.2, st)
    if hip:
        band(b, -hw, hw, yf, yb, rz - 0.4, rz - 0.05, st)
    else:
        band(b, -hw, hw, yf, yb, rz + 0.05, rz + 0.45, st)
    band(b, -hw, hw, yf, yb, 0.0, 0.45, 'slab')
    # front ground floor: sliding glass entrance + windows
    win(b, 'front', -1.4, 1.4, 0.35, 2.75, glass='glass_light', frame='alu', wall=yf, nx=2)
    dec(b, 'front', -1.4, 1.4, 2.25, 2.32, 'alu', off=0.06, wall=yf)
    gw = 1.4
    for uc in fit(-hw + 0.5, -1.9, gw) + fit(1.9, hw - 0.5, gw):
        win(b, 'front', uc - gw / 2, uc + gw / 2, 0.95, 2.4, glass='glass', frame='window_frame', wall=yf, nx=2)
    # upper floors: window grid with small coloured hoods
    xs = fit(-hw + 0.5, hw - 0.5, 1.6, gap=0.8)
    for f0 in fz[1:-1]:
        for uc in xs:
            win(b, 'front', uc - 0.8, uc + 0.8, f0 + 0.9, f0 + 2.4, glass='glass', frame='window_frame', wall=yf, nx=2)
            pan(b, 'front', uc - 0.95, uc + 0.95, f0 + 2.5, f0 + 2.62, st, off=0.4, wall=yf, bottom=True)
    if dropoff:
        # drop-off canopy on round columns, blank sign on its edge, platform + ramp
        b.box(-3.2, 0.4, 3.0, 3.2, yf, 3.3, c('trim_white'), skip=('back',))
        b.sign('front', -3.0, 3.0, 3.3, 3.85, c(st), text_color='sign_white', off=0.1, bars=1, wall=0.55)
        for x in (-2.7, 2.7):
            b.cyl(x, 0.85, 0.15, 3.0, 0.17, c('trim_white'), seg=8, top=False)
        b.box(-3.2, 1.2, 0.15, 3.2, yf, 0.35, c('tile_floor'), skip=('bottom', 'back'))
        rx0 = -hw + 0.3
        ramp_top = [(rx0, 2.0, 0.17), (-3.2, 2.0, 0.35), (-3.2, yf, 0.35), (rx0, yf, 0.17)]
        b._slab(ramp_top, [(p[0], p[1], 0.14) for p in ramp_top], c('tile_floor'))
        b.box(rx0, 2.0, 0.95, -3.2, 2.05, 1.0, c('rail_white'), skip=())
        for x in (rx0 + 0.05, -3.25):
            b.box(x - 0.03, 1.99, 0.15, x + 0.03, 2.06, 0.97, c('rail_white'), skip=('bottom',))
        planter(b, 3.6, hw - 0.4, 0.3, 0.9, z=0.15, h=0.4)
    else:
        # long front terrace (teras) under a flat canopy on square columns, benches for waiting patients
        b.box(-hw + 0.2, 0.9, 0.15, hw - 0.2, yf, 0.4, c('tile_floor'), skip=('bottom', 'back'))
        b.box(-1.4, 0.55, 0.15, 1.4, 0.9, 0.28, c('tile_floor'), skip=('bottom', 'back'))
        b.box(-hw + 0.1, 0.3, 3.0, hw - 0.1, yf, 3.25, c('trim_white'), skip=('back',))
        dec(b, 'front', -hw + 0.1, hw - 0.1, 3.0, 3.25, st, off=0.01, wall=0.3)
        b.sign('front', -2.6, 2.6, 3.25, 3.8, c(st), text_color='sign_white', off=0.1, bars=1, wall=0.45)
        for x in (-hw + 0.5, -1.8, 1.8, hw - 0.5):
            b.box(x - 0.14, 0.95, 0.4, x + 0.14, 1.23, 3.0, c('trim_white'), skip=('bottom', 'top'))
        # waiting benches: seat slab on two legs, thin backrest resting on the back edge of the seat
        for x0 in (-hw + 0.9, 2.2):
            for lx in (x0 + 0.1, x0 + 1.44):
                b.box(lx, yf - 0.6, 0.4, lx + 0.06, yf - 0.2, 0.8, c('metal'), skip=('bottom', 'top'))
            b.box(x0, yf - 0.62, 0.8, x0 + 1.6, yf - 0.16, 0.85, c('bench'), skip=())
            b.box(x0, yf - 0.2, 0.85, x0 + 1.6, yf - 0.16, 1.3, c('bench'), skip=('bottom',))
    # sides
    for side, w_ in (('left', -hw), ('right', hw)):
        for f0 in fz[:-1]:
            for yy in fit(yf + 0.8, yb - 0.8, 1.4, gap=1.6):
                win(b, side, yy - 0.7, yy + 0.7, f0 + 1.0, f0 + 2.3, glass='glass', frame='window_frame', wall=w_)
    # back
    door(b, 'back', hw - 1.6, 1.4, 2.2, 'alu_dark', 'window_frame', wall=yb, leaves=2)
    for f0 in fz[:-1]:
        for uc in fit(-hw + 0.6, hw - (3.0 if f0 == 0 else 0.6), 1.4, gap=1.0):
            win(b, 'back', uc - 0.7, uc + 0.7, f0 + 1.0, f0 + 2.3, glass='glass', frame='window_frame', wall=yb)
    for f0 in fz[1:-1]:
        wall_ac(b, 'back', -hw + 2.3, f0 + 0.3, wall=yb)
        wall_ac(b, 'back', hw - 2.3, f0 + 0.3, wall=yb)
    # downpipe in a gap between the back windows (flat roof) or at the corner under the eaves gutter (hip roof)
    downpipe(b, 'back', hw - 0.3 if hip else -0.15, 0.0, rz + ph, wall=yb)
    # roof
    if hip:
        pass
    elif dropoff:
        for x in (hw - 1.4, hw - 3.0):
            toren(b, x, yb - 1.3, rz, col='tank_blue', r=0.55, h=1.15, stand=0.4)
        ac_row(b, -hw + 1.0, hw - 4.5, yf + 1.3, rz, 4)
        ac_row(b, -hw + 1.0, -hw + 4.5, yb - 1.4, rz, 2, face='back')
        b.box(-0.6, yf + 3.6, rz, 0.6, yf + 4.6, rz + 0.55, c('slab'))
    else:
        toren(b, -hw + 1.3, yb - 1.3, rz, col='tank_orange', r=0.55, h=1.1, stand=0.4)
        ac_row(b, -hw + 2.6, hw - 0.8, yb - 1.2, rz, 3, face='back')
        solar(b, -hw + 0.8, hw - 0.8, yf + 1.0, yf + 2.6, rz, rise=0.4)
        b.box(hw - 1.6, yf + 3.4, rz, hw - 0.6, yf + 4.4, rz + 0.55, c('slab'))


# ------------------------------------------------------------------------------------------ sekolah
def build_sekolah(b, v, rng):
    W, D = b.W, b.D
    hw = W / 2
    wall, trim, roof = v['wall'], v['trim'], v['roof']
    x0, x1 = -hw + 0.55, hw - 0.55          # walls inset so the roof overhang stays in the lot
    yc0, yc1, yb = 2.3, 4.5, D - 0.55       # corridor front edge, classroom front wall, back wall
    z1, ze = 3.8, 7.3                        # upper floor level, eaves
    # yard paving + fence with a gate + blank name board
    paving(b, -hw, hw, 0, yc0, 0.06, col='paving_warm')
    gx0, gx1 = -3.6, -0.6
    for (a, e) in ((-hw + 0.05, gx0), (gx1, hw - 0.05)):
        b.box(a + 0.02, 0.05, 0.06, e - 0.02, 0.25, 0.55, c(wall))
        b.box(a + 0.15, 0.13, 0.55, e - 0.15, 0.17, 1.35, c(trim))
        b.box(a + 0.15, 0.1, 1.35, e - 0.15, 0.2, 1.4, c(trim))
        for u in (a, e - 0.3):
            b.box(u, 0.02, 0.06, u + 0.3, 0.28, 1.55, c(wall))
            b.box(u - 0.03, 0.0, 1.55, u + 0.33, 0.3, 1.63, c(trim))
        nb = int((e - a) / 0.35)
        for i in range(1, nb):
            u = a + (e - a) * i / nb
            dec(b, 'front', u - 0.02, u + 0.02, 0.56, 1.34, 'green_dark', off=0.01, wall=0.13)
    # name board on two posts
    sx0, sx1 = 1.0, 3.6
    for x in (sx0 + 0.2, sx1 - 0.2):
        b.box(x - 0.06, 0.95, 0.06, x + 0.06, 1.07, 1.3, c('rail_white'), skip=('bottom', 'top'))
    b.sign('front', sx0, sx1, 1.3, 2.4, c(trim), text_color='sign_white', off=0.1, bars=2, wall=1.07)
    # corridor floor (raised) and classroom block
    b.box(x0, yc0, 0, x1, yc1, 0.3, c('concrete'), skip=('bottom', 'back'))
    b.box(x0, yc1, 0, x1, yb, ze, c(wall), skip=('bottom', 'top'))
    # end walls closing the corridor
    for (a, e) in ((x0, x0 + 0.25), (x1 - 0.25, x1)):
        b.box(a, yc0, 0, e, yc1, ze, c(wall), skip=('bottom', 'top', 'back'))
    # upper corridor slab, balustrade with roster blocks, columns, top beam
    b.box(x0 + 0.25, yc0, z1 - 0.25, x1 - 0.25, yc1, z1, c('concrete'), skip=('back', 'top'))
    b.face([(x0 + 0.25, yc0, z1), (x1 - 0.25, yc0, z1), (x1 - 0.25, yc1, z1), (x0 + 0.25, yc1, z1)], c('tile_floor'))
    b.box(x0 + 0.25, yc0, z1, x1 - 0.25, yc0 + 0.15, z1 + 0.95, c(wall), skip=('bottom',))
    dec(b, 'front', x0 + 0.25, x1 - 0.25, z1 + 0.85, z1 + 0.95, trim, off=0.02, wall=yc0)
    dec(b, 'front', x0 + 0.25, x1 - 0.25, z1 - 0.25, z1, trim, off=0.02, wall=yc0)
    nbay = 4
    cols = [x0 + (x1 - x0) * i / nbay for i in range(1, nbay)]
    for x in cols:
        b.box(x - 0.16, yc0 - 0.05, 0.3, x + 0.16, yc0 + 0.3, ze - 0.3, c(wall), skip=('bottom', 'top'))
        dec(b, 'front', x - 0.16, x + 0.16, 0.3, 1.0, trim, off=0.02, wall=yc0 - 0.05)
    for i in range(nbay):
        a = x0 + (x1 - x0) * i / nbay + 0.5
        e = x0 + (x1 - x0) * (i + 1) / nbay - 0.5
        for k in range(3):
            u = a + (e - a) * (k + 0.5) / 3
            dec(b, 'front', u - 0.25, u + 0.25, z1 + 0.25, z1 + 0.7, 'green_dark', off=0.02, wall=yc0)
    b.box(x0 + 0.25, yc0, ze - 0.3, x1 - 0.25, yc0 + 0.3, ze, c(wall), skip=('back', 'top'))
    # classrooms: two per floor, door + windows + vent row
    for zf in (0.3, z1):
        for i in range(2):
            a = x0 + 0.25 + (x1 - x0 - 0.5) * i / 2
            e = x0 + 0.25 + (x1 - x0 - 0.5) * (i + 1) / 2
            door(b, 'front', a + 0.9, 0.9, 2.1, trim, 'window_frame', wall=yc1, z0=zf)
            n = 3
            for k in range(n):
                u0 = a + 1.8 + (e - a - 2.2) * k / n
                u1 = a + 1.8 + (e - a - 2.2) * (k + 1) / n - 0.3
                win(b, 'front', u0, u1, zf + 0.9, zf + 2.1, glass='glass', frame=trim, wall=yc1, nx=2)
            dec(b, 'front', a + 1.8, e - 0.7, zf + 2.3, zf + 2.55, 'green_dark', off=0.02, wall=yc1)
    dec(b, 'front', x0, x1, 0.3, 0.8, trim, off=0.01, wall=yc1)
    # back: window rows
    for zf in (0.3, z1):
        for i in range(6):
            uc = x0 + (x1 - x0) * (i + 0.5) / 6
            win(b, 'back', uc - 0.75, uc + 0.75, zf + 1.0, zf + 2.2, glass='glass', frame=trim, wall=yb, nx=2)
    dec(b, 'back', x0, x1, 0.0, 0.6, trim, off=0.01, wall=yb)
    downpipe(b, 'back', 0.0, 0, ze, wall=yb)
    # ends: windows
    for side, w_ in (('left', x0), ('right', x1)):
        for zf in (0.3, z1):
            win(b, side, yc1 + 1.5, yc1 + 2.9, zf + 1.0, zf + 2.2, glass='glass', frame=trim, wall=w_, nx=2)
            win(b, side, yc1 + 4.0, yc1 + 5.4, zf + 1.0, zf + 2.2, glass='glass', frame=trim, wall=w_, nx=2)
        dec(b, side, yc0, yb, 0.0, 0.6, trim, off=0.01, wall=w_)
    # roof
    hip_roof(b, x0, x1, yc0, yb, ze, 2.1, roof, over=0.5, thick=0.14, cap=v.get('roof_cap'), fascia=trim,
             courses=3, course_col=v.get('roof_line'))


# ------------------------------------------------------------------------------------------ glass office
def build_glass(b, v, rng):
    W, D = b.W, b.D
    hw, yb = W / 2 - SIDE, D - BACK
    gz, fh, nf = 4.2, 3.4, v['floors']
    rz = gz + fh * (nf - 1)
    yf = 1.6
    core_left = rng.random() < 0.5
    cw = 3.4
    if core_left:
        gx0, gx1, cx0, cx1 = -hw + cw, hw, -hw, -hw + cw
    else:
        gx0, gx1, cx0, cx1 = -hw, hw - cw, hw - cw, hw
    glass, core, wall = v['glass'], v['core'], v['wall']
    paving(b, -W / 2, W / 2, 0, yf, 0.12)
    # glass volume (curtain wall from the first floor up to the parapet top)
    ph = 0.9
    flat_block(b, gx0, gx1, yf, yb, 0, rz, wall, v['deck'], ph=ph, cap='alu')
    cs = 'right' if core_left else 'left'    # glass side facing away from the core
    ce = gx1 if core_left else gx0
    pan(b, 'front', gx0 + 0.05, gx1 - 0.05, gz, rz + ph, glass, off=0.06, wall=yf)
    dec(b, cs, yf + 0.05, yb - 1.2, gz, rz + ph, glass, off=0.03, wall=ce)
    nm = max(3, int(round((gx1 - gx0) / 1.25)))
    for i in range(1, nm):
        u = gx0 + (gx1 - gx0) * i / nm
        dec(b, 'front', u - 0.035, u + 0.035, gz, rz + ph, 'alu', off=0.075, wall=yf)
    for k in range(1, nf):
        z = gz + k * fh
        zt = z + 0.05 if k < nf - 1 else z - 0.2
        dec(b, 'front', gx0 + 0.05, gx1 - 0.05, z - 0.45, zt, 'glass_night', off=0.07, wall=yf)
        dec(b, cs, yf + 0.05, yb - 1.2, z - 0.45, zt, 'glass_night', off=0.04, wall=ce)
    for i in range(1, 4):
        u = yf + (yb - 1.2 - yf) * i / 4
        dec(b, cs, u - 0.035, u + 0.035, gz, rz + ph, 'alu', off=0.05, wall=ce)
    # ground floor lobby + cantilever canopy
    win(b, 'front', gx0 + 0.3, gx1 - 0.3, 0.12, gz - 0.35, glass='glass_light', frame='alu_dark', wall=yf, nx=5)
    dm = (gx0 + gx1) / 2
    dec(b, 'front', dm - 0.9, dm + 0.9, 0.12, 2.5, 'glass', off=0.06, wall=yf)
    dec(b, 'front', dm - 0.03, dm + 0.03, 0.12, 2.5, 'alu_dark', off=0.07, wall=yf)
    b.box(gx0 + 0.2, 0.35, gz - 0.3, gx1 - 0.2, yf, gz - 0.08, c('alu'), skip=('back',))
    dec(b, cs, yf + 0.5, yb - 1.5, 0.9, gz - 0.6, 'glass', wall=ce)
    # solid core: stair + lift, taller than the glass volume, blank company sign near the top
    cz = rz + 1.8
    cy = yf - 0.4
    flat_block(b, cx0, cx1, cy, yb, 0, cz, core, 'deck_dark', ph=0.5, cap='alu')
    ccx = (cx0 + cx1) / 2
    for k in range(1, nf):
        z = gz + (k - 1) * fh + 0.9
        win(b, 'front', ccx - 0.3, ccx + 0.3, z, z + 2.2, glass='glass', frame='alu', wall=cy)
    b.sign('front', cx0 + 0.3, cx1 - 0.3, cz - 1.3, cz - 0.2, c(v['sign']), text_color=c(v['sign_bar']), off=0.1,
           bars=2, wall=cy)
    door(b, 'front', ccx, 1.0, 2.2, 'alu_dark', 'alu', wall=cy, z0=0.12)
    oside = 'left' if core_left else 'right'
    ow = cx0 if core_left else cx1
    for k in range(nf):
        z = 1.0 if k == 0 else gz + (k - 1) * fh + 1.0
        win(b, oside, yf + 1.5, yf + 2.3, z, z + 1.6, glass='glass', frame='alu', wall=ow)
        win(b, oside, yb - 2.5, yb - 1.7, z, z + 1.6, glass='glass', frame='alu', wall=ow)
    # darker brick floor bands wrapped around the exposed faces of the core (it no longer reads as one slab)
    for k in range(1, nf + 1):
        z = gz + (k - 1) * fh
        band(b, cx0, cx1, cy, yb, z - 0.12, z + 0.16, 'core_dark', sides=('front', 'back', oside))
    # a recessed darker strip down the middle of the outer side (vertical service shaft)
    dec(b, oside, (cy + yb) / 2 - 0.35, (cy + yb) / 2 + 0.35, 0.6, cz + 0.3, 'core_dark', off=0.012, wall=ow)
    # monument sign by the entrance + planter
    mx = gx0 + 0.9 if not core_left else gx1 - 2.9
    b.box(mx, 0.35, 0.12, mx + 2.0, 0.75, 1.05, c('granite'))
    dec(b, 'front', mx + 0.15, mx + 1.85, 0.5, 0.95, 'sign_white', off=0.02, wall=0.35)
    dec(b, 'front', mx + 0.35, mx + 1.65, 0.62, 0.78, glass, off=0.03, wall=0.35)
    px0 = (gx0 + 0.3) if core_left else (gx1 - 1.8)
    planter(b, px0, px0 + 1.5, 0.3, 0.8, z=0.12, h=0.4, col='granite')
    # back: rows of windows, AC units
    for k in range(nf):
        z = 1.0 if k == 0 else gz + (k - 1) * fh + 1.0
        for uc in fit(gx0 + 0.4, gx1 - 0.4, 1.8, gap=0.6):
            win(b, 'back', uc - 0.9, uc + 0.9, z, z + 1.5, glass=glass, frame='alu', wall=yb, nx=2)
        if k > 0:
            wall_ac(b, 'back', gx0 + (gx1 - gx0) * (1.0 if k % 2 else 2.0) / 3, z - 0.75, wall=yb)
    win(b, 'back', ccx - 0.3, ccx + 0.3, gz, cz - 1.0, glass='glass', frame='alu', wall=yb)
    downpipe(b, 'back', ccx + (1.0 if core_left else -1.0), 0, cz + 0.5, wall=yb)
    # roofs
    ac_row(b, gx0 + 0.9, gx1 - 0.9, yf + 1.4, rz, 4)
    ac_row(b, gx0 + 0.9, gx1 - 0.9, yf + 2.8, rz, 3)
    panel_tank(b, gx0 + 0.6, gx0 + 3.2, yb - 3.0, yb - 0.8, rz, h=1.3, col='tank_cream')
    solar(b, gx1 - 3.8, gx1 - 0.8, yb - 3.4, yb - 1.8, rz)
    mast(b, ccx + 0.6, yb - 1.0, cz, 1.2)
    b.box(ccx - 0.8, yb - 3.0, cz, ccx + 0.4, yb - 1.8, cz + 0.5, c('slab'))


# ------------------------------------------------------------------------------------------ grid office
def build_grid(b, v, rng):
    W, D = b.W, b.D
    hw, yb = W / 2 - SIDE, D - BACK
    yf = 1.2
    gz, fh, nf = 3.6, 3.3, v['floors']
    rz = gz + fh * (nf - 1)
    ph = 0.8
    wall, inf, sgn = v['wall'], v['infill'], v['sign']
    paving(b, -W / 2, W / 2, 0, yf, 0.12, col='paving')
    flat_block(b, -hw, hw, yf, yb, 0, rz, wall, v['deck'], ph=ph, cap='trim_white')
    # portal frame around the upper floors: pilasters + head/sill beams, dark infill with a window grid
    pw = 0.55
    pan(b, 'front', -hw, -hw + pw, gz - 0.3, rz + ph, 'trim_white', off=0.45, wall=yf)
    pan(b, 'front', hw - pw, hw, gz - 0.3, rz + ph, 'trim_white', off=0.45, wall=yf)
    pan(b, 'front', -hw + pw, hw - pw, rz + 0.05, rz + ph, 'trim_white', off=0.45, wall=yf, bottom=True)
    pan(b, 'front', -hw + pw, hw - pw, gz - 0.3, gz, 'trim_white', off=0.45, wall=yf, bottom=True)
    dec(b, 'front', -hw + pw, hw - pw, gz, rz + 0.05, inf, off=0.02, wall=yf)
    ncol = 3
    a0, a1 = -hw + pw + 0.3, hw - pw - 0.3
    for k in range(nf - 1):
        f0 = gz + k * fh
        for i in range(ncol):
            u0 = a0 + (a1 - a0) * i / ncol + 0.12
            u1 = a0 + (a1 - a0) * (i + 1) / ncol - 0.12
            win(b, 'front', u0, u1, f0 + 0.7, f0 + 2.8, glass='glass_light', frame='trim_white', wall=yf - 0.02, ny=2, fw=0.08)
        if k > 0:
            pan(b, 'front', -hw + pw, hw - pw, f0 - 0.12, f0 + 0.05, 'trim_white', off=0.3, wall=yf, bottom=True)
    # ground floor: glass office front + blank signboard + small canopy
    win(b, 'front', -hw + 0.4, hw - 0.4, 0.12, gz - 0.9, glass='glass', frame='frame_black', wall=yf, nx=4)
    dec(b, 'front', -0.55, 0.55, 0.12, 2.3, 'glass_light', off=0.06, wall=yf)
    b.sign('front', -hw + 0.3, hw - 0.3, gz - 0.85, gz - 0.35, c(sgn), text_color='sign_white', off=0.12, bars=1, wall=yf)
    b.box(-1.3, 0.4, 2.45, 1.3, yf, 2.6, c('frame_black'), skip=('back',))
    # sides
    for side, w_ in (('left', -hw), ('right', hw)):
        for k in range(nf):
            z = 1.0 if k == 0 else gz + (k - 1) * fh + 1.0
            win(b, side, yf + 2.0, yf + 3.0, z, z + 1.4, glass='glass', frame='trim_white', wall=w_)
    # back
    door(b, 'back', -hw + 1.2, 0.9, 2.1, 'door_dark', 'trim_white', wall=yb)
    for k in range(nf):
        z = 1.1 if k == 0 else gz + (k - 1) * fh + 1.0
        for uc in ((0.3, 2.6) if k == 0 else (-2.3, 0.3, 2.6)):
            win(b, 'back', uc - 0.6, uc + 0.6, z, z + 1.3, glass='glass', frame='trim_white', wall=yb, nx=2)
        if k > 0:
            wall_ac(b, 'back', -hw + 1.0 if k % 2 else hw - 0.7, z - 0.2, wall=yb)
    downpipe(b, 'back', -0.95, 0, rz + ph, wall=yb)
    # roof: orange toren, AC condensers, roof hatch, solar panels
    toren(b, hw - 1.3, yb - 1.3, rz, col='tank_orange', r=0.55, h=1.1, stand=0.4)
    ac_row(b, -hw + 0.8, hw - 2.8, yf + 1.1, rz, 3)
    b.box(-hw + 0.8, yb - 2.4, rz, -hw + 1.9, yb - 1.3, rz + 0.6, c('slab'))
    solar(b, -hw + 0.8, hw - 2.6, yf + 3.0, yf + 4.6, rz, rise=0.4)


# ------------------------------------------------------------------------------------------ public service office
def build_publik(b, v, rng):
    W, D = b.W, b.D
    hw, yb = W / 2 - SIDE, D - BACK
    yf = 2.8
    z1, rz = 3.6, 7.0
    ph = 0.8
    wall, trim = v['wall'], v['trim']
    # front yard: paving, walled fence with pillars and an open gate
    paving(b, -W / 2, W / 2, 0, yf, 0.08, col='paving')
    gx0, gx1 = -1.9, 1.9
    for (a, e) in ((-W / 2 + 0.05, gx0), (gx1, W / 2 - 0.05)):
        b.box(a + 0.02, 0.05, 0.08, e - 0.02, 0.25, 0.95, c(wall))
        dec(b, 'front', a, e, 0.8, 0.95, trim, wall=0.05)
        for u in (a, e - 0.34):
            b.box(u, 0.02, 0.08, u + 0.34, 0.28, 1.3, c(wall))
            b.box(u - 0.03, 0.0, 1.3, u + 0.37, 0.31, 1.4, c(trim))
    # main block
    flat_block(b, -hw, hw, yf, yb, 0, rz, wall, v['deck'], ph=ph, cap=trim)
    band(b, -hw, hw, yf, yb, 0, 0.5, 'slab')
    band(b, -hw, hw, yf, yb, z1 - 0.15, z1 + 0.15, trim)
    band(b, -hw, hw, yf, yb, rz + 0.3, rz + 0.5, trim)
    # windows either side of the portico
    for f0 in (0.0, z1):
        for uc in fit(-hw + 0.4, -3.05, 1.2, gap=0.5) + fit(3.05, hw - 0.4, 1.2, gap=0.5):
            win(b, 'front', uc - 0.6, uc + 0.6, f0 + 0.8, f0 + 2.8, glass='glass', frame=trim, wall=yf, nx=2, ny=2)
    # portico: steps, four round columns through both floors, flat roof block with a blank board
    px0, px1, py = -2.9, 2.9, 0.7
    b.box(px0, py, 0.08, px1, yf, 0.45, c('tile_floor'), skip=('bottom', 'back'))
    b.box(px0 + 0.3, py - 0.35, 0.08, px1 - 0.3, py, 0.27, c('tile_floor'), skip=('bottom', 'back'))
    for x in (-2.4, -0.8, 0.8, 2.4):
        b.cyl(x, py + 0.45, 0.45, rz, 0.21, c('trim_white'), seg=8, top=False)
    b.box(px0, py, rz, px1, yf, rz + 1.25, c(wall), skip=())
    b.sign('front', px0 + 0.4, px1 - 0.4, rz + 0.45, rz + 1.05, c(trim), text_color='sign_white', off=0.06, bars=1, wall=py)
    dec(b, 'front', px0, px1, rz + 0.12, rz + 0.3, trim, wall=py)
    door(b, 'front', 0, 1.8, 2.6, 'door_wood', trim, wall=yf, z0=0.45, leaves=2)
    for uc in (-1.3, 1.3):
        win(b, 'front', uc - 0.5, uc + 0.5, z1 + 0.8, z1 + 2.8, glass='glass', frame=trim, wall=yf, ny=2)
    # sides + back
    for side, w_ in (('left', -hw), ('right', hw)):
        for f0 in (0.0, z1):
            for yy in (yf + 1.6, yf + 4.6):
                win(b, side, yy, yy + 1.2, f0 + 0.9, f0 + 2.5, glass='glass', frame=trim, wall=w_, ny=2)
    for f0 in (0.0, z1):
        for i in range(4):
            uc = -hw + 2 * hw * (i + 0.5) / 4
            if f0 == 0 and i == 3:
                door(b, 'back', uc, 1.0, 2.1, 'door_dark', trim, wall=yb)
                continue
            win(b, 'back', uc - 0.6, uc + 0.6, f0 + 0.9, f0 + 2.5, glass='glass', frame=trim, wall=yb, ny=2)
    wall_ac(b, 'back', -hw + 2 * hw * 1.0 / 4, z1 + 0.3, wall=yb)
    wall_ac(b, 'back', -hw + 2 * hw * 3.0 / 4, z1 + 0.3, wall=yb)
    # roof: two toren, AC units
    toren(b, -hw + 1.3, yb - 1.3, rz, col='tank_white', stand=0.4)
    toren(b, -hw + 2.9, yb - 1.3, rz, col='tank_orange', stand=0.4)
    panel_tank(b, -1.2, 1.6, yb - 3.3, yb - 1.1, rz, h=1.0, col='tank_grey', leg=0.4)
    mast(b, 2.3, yb - 1.0, rz, 1.85)
    ac_row(b, 3.0, hw - 0.7, yb - 1.3, rz, 2, face='back')
    ac_row(b, -hw + 1.0, -hw + 4.0, yf + 1.2, rz, 2)
    ac_row(b, hw - 4.0, hw - 1.0, yf + 1.2, rz, 2)
    ac_row(b, hw - 3.4, hw - 1.0, yf + 3.6, rz, 2)


BUILDERS = {
    'bank': build_bank, 'ribbon': build_ribbon, 'klinik': build_klinik, 'sekolah': build_sekolah,
    'glass': build_glass, 'grid': build_grid, 'publik': build_publik,
}

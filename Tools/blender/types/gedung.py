"""Gedung: tall background towers for the outer ring of the city (the Jakarta CBD skyline behind the streets).

Glass office tower with spandrel bands, apartment tower with balconies, hotel with a podium, pool deck and a
crown, stepped setback tower with vertical fins and a helipad, twin slabs with a sky bridge, round glass tower,
an older concrete-grid office with a rooftop board, a rusun slab with a hip roof and a chamfered slate-glass
office tower with a flat crown. They are seen far away through golden haze, so everything is bold massing + banding; small detail
only at the base and on the roofs. Every variant is finished on all four sides (the camera may see the back).

Rules used everywhere below (so nothing flickers from far away):
  * details that cross a wall always overlap it volumetrically (never two same-facing faces in one plane),
  * decals on towers sit >= 5 cm proud of their wall,
  * every band / cornice is one box larger than the core, so it wraps all four sides and closes itself.
"""
import math

TYPE = 'gedung'
ROLES = ['tall']

TEAL = '#4f9ea8'
TEAL_DARK = '#2e6b77'
BLUE = '#4d7cae'
SKY = '#93c6d2'          # light glass: balustrades, lobby glass
WHITE = '#f2f0e9'
GREY = '#d3cfc6'
GREY_DARK = '#8e8a83'
STONE = '#d5c3a1'
CREAM = '#efe1c2'
DECK = '#8d918d'         # flat roof waterproofing (cool grey, reads against the warm walls)
DECK_GREEN = '#7fa075'   # roof garden / terrace
GRANITE = '#c49c86'      # pinkish granite cladding (90s Jakarta towers)
GRANITE_DARK = '#9c7662'
POOL = '#5cc3d6'
AMBER = '#e0a24f'
TERRA = '#c8704f'
RED_LIGHT = '#d8433a'
SIDES = ('front', 'back', 'left', 'right')


def variants():
    return [
        dict(style='office', w=18.0, d=18.0, floors=9, fh=3.6, glass=TEAL, band=WHITE),
        dict(style='apartment', w=20.0, d=16.0, floors=14, fh=3.0, wall=WHITE, accent=TERRA, rail=SKY, deck='#7b8e98'),
        dict(style='hotel', w=24.0, d=20.0, floors=13, fh=3.2, wall=CREAM, accent=AMBER, roof='#3f7176'),
        dict(style='stepped', w=22.0, d=22.0, glass=BLUE, fin=WHITE, deck=DECK),
        dict(style='twin', w=24.0, d=16.0, floors=12, fh=3.4, glass=TEAL_DARK, frame=GRANITE, crown='#3f7f8a', deck='#6f7a78'),
        dict(style='round', w=16.0, d=17.0, floors=13, fh=3.4, glass='#6fa8a0', band=WHITE, deck='#7e8a72'),
        dict(style='grid', w=14.0, d=14.0, floors=9, fh=3.5, glass='glass_dark', frame=WHITE, sign='sign_red', deck='#a08b78'),
        dict(style='rusun', w=22.0, d=14.0, floors=7, fh=3.0, wall='wall_cream', accent='wall_orange', roof='roof_terracotta', deck=DECK),
        dict(style='octa', w=15.0, d=15.0, floors=11, fh=3.5, glass='#5f7584', glass2='#465966', line='#dcc59a',
             mull='#3b4852', band='#efe4cc', deck='#8a8378'),
    ]


# ------------------------------------------------------------------------------------------ helpers
def span(r, side):
    return (r[0], r[2]) if side in ('front', 'back') else (r[1], r[3])


def wall(r, side):
    return {'front': r[1], 'back': r[3], 'left': r[0], 'right': r[2]}[side]


def grow(r, d):
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def cap(b, r, z0, z1, side, top, bottom=False):
    """Box whose top face has its own colour (roof decks, terraces, pool water)."""
    x0, y0, x1, y1 = r
    b.box(x0, y0, z0, x1, y1, z1, side, skip=('top',) if bottom else ('top', 'bottom'))
    b.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], top)


def ring(b, r, z0, z1, out, col, top=None):
    """Band / cornice wrapping a rectangular core: one closed box `out` larger than the core."""
    g = grow(r, out)
    if top:
        cap(b, g, z0, z1, col, top, bottom=True)
    else:
        b.box(g[0], g[1], z0, g[2], g[3], z1, col, skip=())


def fin(b, r, side, u, z0, z1, out, w, col, top=True, bottom=False):
    """Vertical fin / pilaster standing on a facade, embedded 5 cm into the core. Its wall-side face is only
    dropped when the fin lies entirely within the facade (an end fin that stands proud of the end wall keeps it,
    otherwise the sliver beyond the corner would be an open slot)."""
    x0, y0, x1, y1 = r
    e = 0.05
    sk = [] if bottom else ['bottom']
    if not top:
        sk.append('top')
    lo, hi = (x0, x1) if side in ('front', 'back') else (y0, y1)
    inside = lo - 1e-6 <= u - w / 2 and u + w / 2 <= hi + 1e-6
    ws = lambda face: [face] if inside else []
    if side == 'front':
        b.box(u - w / 2, y0 - out, z0, u + w / 2, y0 + e, z1, col, skip=tuple(sk + ws('back')))
    elif side == 'back':
        b.box(u - w / 2, y1 - e, z0, u + w / 2, y1 + out, z1, col, skip=tuple(sk + ws('front')))
    elif side == 'left':
        b.box(x0 - out, u - w / 2, z0, x0 + e, u + w / 2, z1, col, skip=tuple(sk + ws('right')))
    else:
        b.box(x1 - e, u - w / 2, z0, x1 + out, u + w / 2, z1, col, skip=tuple(sk + ws('left')))


def dividers(u0, u1, n):
    return [u0 + (u1 - u0) * i / n for i in range(1, n)]


def corner_piers(b, r, z0, z1, out, w, col, top=True):
    x0, y0, x1, y1 = r
    sk = ('bottom',) if top else ('bottom', 'top')
    for (xa, xb) in ((x0 - out, x0 + w), (x1 - w, x1 + out)):
        for (ya, yb) in ((y0 - out, y0 + w), (y1 - w, y1 + out)):
            b.box(xa, ya, z0, xb, yb, z1, col, skip=sk)


def drum(b, cx, cy, z0, z1, r, col, seg=16, top=True, bottom=False, top_col=None, phase=0.0):
    pts = [(cx + r * math.cos(phase + 2 * math.pi * i / seg), cy + r * math.sin(phase + 2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, d = pts[i], pts[(i + 1) % seg]
        b.face([(a[0], a[1], z0), (d[0], d[1], z0), (d[0], d[1], z1), (a[0], a[1], z1)], col)
    if top:
        b.face([(p[0], p[1], z1) for p in pts], top_col or col)
    if bottom:
        b.face([(p[0], p[1], z0) for p in reversed(pts)], col)


def tube(b, cx, cy, z0, z1, ri, ro, col, seg=16, top=True, bottom=False):
    """Hollow round wall (crown screen of the round tower)."""
    P = lambda r, i: (cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg))
    for i in range(seg):
        j = (i + 1) % seg
        ao, do, ai, di = P(ro, i), P(ro, j), P(ri, i), P(ri, j)
        b.face([(ao[0], ao[1], z0), (do[0], do[1], z0), (do[0], do[1], z1), (ao[0], ao[1], z1)], col)
        b.face([(di[0], di[1], z0), (ai[0], ai[1], z0), (ai[0], ai[1], z1), (di[0], di[1], z1)], col)
        if top:
            b.face([(ai[0], ai[1], z1), (ao[0], ao[1], z1), (do[0], do[1], z1), (di[0], di[1], z1)], col)
        if bottom:
            b.face([(di[0], di[1], z0), (do[0], do[1], z0), (ao[0], ao[1], z0), (ai[0], ai[1], z0)], col)


def cone(b, cx, cy, z0, z1, r, col, seg=8, bottom=True, phase=0.0):
    pts = [(cx + r * math.cos(phase + 2 * math.pi * i / seg), cy + r * math.sin(phase + 2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        a, d = pts[i], pts[(i + 1) % seg]
        b.face([(a[0], a[1], z0), (d[0], d[1], z0), (cx, cy, z1)], col)
    if bottom:
        b.face([(p[0], p[1], z0) for p in reversed(pts)], col)


def mast(b, x, y, z0, h, col='metal', w=0.3):
    b.box(x - w / 2, y - w / 2, z0, x + w / 2, y + w / 2, z0 + h, col, skip=('bottom', 'top'))
    b.box(x - w / 2 - 0.12, y - w / 2 - 0.12, z0 + h, x + w / 2 + 0.12, y + w / 2 + 0.12, z0 + h + 0.45, RED_LIGHT, skip=())


def cooler(b, x, y, z0, r=1.1, h=1.6):
    """Rooftop cooling tower: plinth, drum, dark fan ring."""
    b.box(x - r - 0.15, y - r - 0.15, z0, x + r + 0.15, y + r + 0.15, z0 + 0.4, 'concrete')
    drum(b, x, y, z0 + 0.4, z0 + 0.4 + h, r, 'ac_white', seg=10)
    drum(b, x, y, z0 + 0.4 + h, z0 + 0.55 + h, r * 0.72, 'frame_black', seg=8)


def condenser(b, x, y, z0, col='ac_white', fan='#5b5f63'):
    """Packaged AC condenser on a roof: white box with a dark fan grille on top."""
    cap(b, (x - 0.55, y - 0.5, x + 0.55, y + 0.5), z0, z0 + 0.95, col, fan)


def tank(b, x, y, z0, r=1.0, h=2.0, col='tank_white'):
    b.box(x - r - 0.1, y - r - 0.1, z0, x + r + 0.1, y + r + 0.1, z0 + 0.35, 'concrete')
    drum(b, x, y, z0 + 0.35, z0 + 0.35 + h, r, col, seg=10)


def plant_box(b, x0, y0, x1, y1, z0, h=0.7):
    cap(b, (x0, y0, x1, y1), z0, z0 + h * 0.55, 'concrete', 'plant_dark', bottom=False)
    b.box(x0 + 0.1, y0 + 0.1, z0 + h * 0.55, x1 - 0.1, y1 - 0.1, z0 + h, 'plant')


def machine_room(b, x0, y0, x1, y1, z0, h, col=GREY, top='#b3b1aa'):
    """Lift / plant room on a roof: box with a door on the front and louvres on the back."""
    cap(b, (x0, y0, x1, y1), z0, z0 + h, col, top)
    b.door('front', x0 + 1.0, 0.9, 2.1, color='door_dark', frame=GREY_DARK, z0=z0, wall=y0)
    for side, uc in (('back', (x0 + x1) / 2), ('left', (y0 + y1) / 2), ('right', (y0 + y1) / 2)):
        w = wall((x0, y0, x1, y1), side)
        b.decal(side, uc - 0.9, uc + 0.9, z0 + h - 1.6, z0 + h - 0.5, GREY_DARK, off=0.05, wall=w)


def lobby(b, r, zl, inset, frame, glass='glass_dark', col_step=7.0, entry=2.8, service=True, canopy=True):
    """Recessed glass ground floor under a tower: glass box, mullions, perimeter columns, entrance canopy,
    service door at the back. The tower above must cover r from zl - 0.3 (a band) upwards."""
    x0, y0, x1, y1 = r
    L = (x0 + inset, y0 + inset, x1 - inset, y1 - inset)
    b.box(L[0], L[1], 0, L[2], L[3], zl, glass, skip=('bottom', 'top'))
    for side in SIDES:
        u0, u1 = span(L, side)
        w = wall(L, side)
        gap = None
        if side == 'front':
            gap = (-entry / 2 - 0.3, entry / 2 + 0.3)
        elif side == 'back' and service:
            gap = (-2.0, 2.0)
        n = max(2, int(round((u1 - u0) / 2.2)))
        for u in dividers(u0, u1, n):
            if gap and gap[0] < u < gap[1]:
                continue
            b.decal(side, u - 0.07, u + 0.07, 0, zl, frame, off=0.05, wall=w)
        b.decal(side, u0, u1, 3.0, 3.2, frame, off=0.09, wall=w)
    # entrance (front) and service door (back)
    b.panel('front', -entry / 2, entry / 2, 0, 2.7, SKY, off=0.03, depth=0.03, wall=L[1])
    b.decal('front', -0.04, 0.04, 0, 2.7, 'frame_black', off=0.07, wall=L[1])
    if canopy:
        b.box(-entry / 2 - 1.2, 0.15, 3.4, entry / 2 + 1.2, L[1] + 0.1, 3.75, frame, skip=())
    if service:
        b.panel('back', -1.6, 1.6, 0, 2.9, 'shutter', off=0.04, depth=0.04, wall=L[3])
        for z in (0.7, 1.4, 2.1):
            b.decal('back', -1.55, 1.55, z, z + 0.06, 'shutter_groove', off=0.08, wall=L[3])
    # perimeter columns carrying the tower
    c = 0.35
    nx = max(1, int(round((x1 - x0) / col_step)))
    if nx % 2 == 0:
        nx += 1                      # keep a bay (not a column) in front of the entrance
    for i in range(nx + 1):
        x = x0 + c + (x1 - x0 - 2 * c) * i / nx
        for y in (y0 + c, y1 - c):
            b.box(x - c, y - c, 0, x + c, y + c, zl, frame, skip=('bottom', 'top'))
    ny = max(1, int(round((y1 - y0) / col_step)))
    for j in range(1, ny):
        y = y0 + c + (y1 - y0 - 2 * c) * j / ny
        for x in (x0 + c, x1 - c):
            b.box(x - c, y - c, 0, x + c, y + c, zl, frame, skip=('bottom', 'top'))


def podium_front(b, r, z0, z1, glass='glass_dark', frame='frame_black', step=2.4, sides=SIDES, skip_u=None):
    """Shopfront glazing band (glass panel + mullion decals) around a podium."""
    for side in sides:
        u0, u1 = span(r, side)
        w = wall(r, side)
        segs = [(u0 + 0.8, u1 - 0.8)]
        if skip_u and side in skip_u:
            a, c = skip_u[side]
            segs = [(u0 + 0.8, a), (c, u1 - 0.8)]
        for (a, c) in segs:
            if c - a < 1.0:
                continue
            b.panel(side, a, c, z0, z1, glass, off=0.05, depth=0.05, wall=w)
            n = max(1, int(round((c - a) / step)))
            for u in dividers(a, c, n):
                b.decal(side, u - 0.06, u + 0.06, z0, z1, frame, off=0.07, wall=w)


# ------------------------------------------------------------------------------------------ styles
def s_office(b, v, rng):
    """Glass office tower: teal curtain wall, a white spandrel band every floor, recessed lobby on columns,
    glass crown screen hiding the plant room, cooling towers and a mast."""
    W, D = b.W, b.D
    r = (-W / 2 + 0.6, 0.6, W / 2 - 0.6, D - 0.6)
    x0, y0, x1, y1 = r
    zl, fh, n = 5.6, v['fh'], v['floors']
    zt = zl + fh * n
    g, band = v['glass'], v['band']
    lobby(b, r, zl - 0.3, 1.6, band)
    b.box(x0, y0, zl, x1, y1, zt, g, skip=('bottom', 'top'))
    for k in range(n):
        z = zl + k * fh
        ring(b, r, z - 0.3, z + 0.7, 0.22, band)
    # vertical accent: a dark glass notch up the middle of every face
    for side in SIDES:
        u0, u1 = span(r, side)
        um = (u0 + u1) / 2
        b.decal(side, um - 0.9, um + 0.9, zl + 0.7, zt, TEAL_DARK, off=0.06, wall=wall(r, side))
    # crown: roof slab + a one-floor glass screen with a white cap
    ring(b, r, zt - 0.3, zt + 0.5, 0.3, band, top=DECK)
    zr = zt + 0.5
    b.parapet(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, zr, 3.6, g, t=0.35)
    b.parapet(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, zr + 3.6, 0.6, band, t=0.45)   # flush: no open lip underneath
    machine_room(b, -3.2, D / 2 - 1.0, 3.2, D / 2 + 3.4, zr, 5.2)
    cooler(b, x0 + 2.6, y0 + 2.8, zr)
    cooler(b, x0 + 2.6, y0 + 6.0, zr)
    tank(b, x1 - 2.4, y0 + 2.6, zr, col='tank_blue')
    mast(b, 2.0, D / 2 + 1.2, zr + 5.2, 7.0)


def s_apartment(b, v, rng):
    """Residential tower: white slab with continuous balconies front and back (glass balustrades),
    terracotta fins splitting the bays, accent panels on the end walls, crown frame + tanks on the roof."""
    W, D = b.W, b.D
    bal = 1.3
    r = (-W / 2 + 0.5, 0.4 + bal, W / 2 - 0.5, D - 0.4 - bal)
    x0, y0, x1, y1 = r
    zp, fh, n = 4.8, v['fh'], v['floors']
    zt = zp + fh * n
    wl, acc, rail = v['wall'], v['accent'], v['rail']
    # podium (lobby + shops), a little wider than the tower on every side
    P = (-W / 2 + 0.3, 0.3, W / 2 - 0.3, D - 0.3)
    b.box(P[0], P[1], 0, P[2], P[3], zp - 0.4, GREY_DARK, skip=('bottom', 'top'))
    cap(b, grow(P, 0.0), zp - 0.4, zp, wl, DECK_GREEN, bottom=True)
    podium_front(b, P, 0.3, 3.4, glass='glass_dark', skip_u={'front': (-1.8, 1.8), 'back': (-1.8, 1.8)})
    b.panel('front', -1.5, 1.5, 0, 2.6, SKY, off=0.04, depth=0.04, wall=P[1])
    b.box(-2.6, 0.02, 3.0, 2.6, P[1] + 0.1, 3.3, wl, skip=())
    b.panel('back', -1.5, 1.5, 0, 2.8, 'shutter', off=0.04, depth=0.04, wall=P[3])
    # tower
    cap(b, r, zp, zt, wl, v['deck'])
    for side, sgn in (('front', -1), ('back', 1)):
        yw = wall(r, side)
        yo = yw + sgn * bal                      # balcony edge
        for k in range(n):
            z = zp + k * fh
            b.decal(side, x0 + 0.4, x1 - 0.4, z + 0.3, z + 2.5, 'glass', off=0.06, wall=yw)
        for k in range(1, n + 1):                     # balcony slabs; the one at the roof covers the top floor
            z = zp + k * fh
            ya, yb = sorted((yo, yw - sgn * 0.05))
            b.box(x0 + 0.2, ya, z - 0.15, x1 - 0.2, yb, z + 0.12, wl, skip=('back',) if side == 'front' else ('front',))
            if k < n:
                ra, rb = sorted((yo, yo - sgn * 0.12))
                b.box(x0 + 0.2, ra, z + 0.12, x1 - 0.2, rb, z + 1.1, rail)
        # fins stop 5 cm under the parapet top: their wall-side face is inside the parapet, never seen
        for u in dividers(x0, x1, 4):
            fin(b, r, side, u, zp, zt + 1.15, bal + 0.12, 0.45, acc)
        for u in (x0 + 0.15, x1 - 0.15):              # end fins stand 5 cm proud of the end walls
            fin(b, r, side, u, zp, zt + 1.15, bal + 0.12, 0.4, wl)
    # end walls: accent panel in the middle, windows either side
    for side in ('left', 'right'):
        xw = wall(r, side)
        ym = (y0 + y1) / 2
        b.panel(side, ym - 1.6, ym + 1.6, zp, zt + 1.15, acc, off=0.25, depth=0.3, wall=xw)
        for k in range(n):
            z = zp + k * fh
            for yc in (y0 + 1.9, y1 - 1.9):
                b.decal(side, yc - 0.9, yc + 0.9, z + 0.8, z + 2.3, 'glass', off=0.06, wall=xw)
    # roof: parapet, lift room, tanks, crown frame
    b.parapet(x0, x1, y0, y1, zt, 1.2, wl, t=0.25)
    machine_room(b, -2.8, y0 + 3.4, 2.8, y1 - 2.4, zt, 3.6, col=acc, top='#a3978a')
    for k in range(3):
        tank(b, x0 + 2.0, y0 + 2.6 + k * 2.6, zt, r=0.9, h=1.8, col='tank_blue' if k != 1 else 'tank_white')
    for k in range(3):
        condenser(b, x1 - 2.2, y0 + 2.4 + k * 1.5, zt)
    # crown frame: four posts, two long beams and two short beams closing it into one rectangle
    zc = zt + 5.6
    for x in (x0 + 0.9, x1 - 0.9):
        for y in (y0 + 0.9, y1 - 0.9):
            b.box(x - 0.45, y - 0.45, zt, x + 0.45, y + 0.45, zc - 1.1, acc, skip=('bottom', 'top'))
    for y in (y0 + 0.9, y1 - 0.9):
        b.box(x0 + 0.3, y - 0.55, zc - 1.1, x1 - 0.3, y + 0.55, zc, acc, skip=())
    for x in (x0 + 0.9, x1 - 0.9):
        b.box(x - 0.45, y0 + 1.45, zc - 1.0, x + 0.45, y1 - 1.45, zc - 0.1, acc, skip=('front', 'back'))


def s_hotel(b, v, rng):
    """Hotel: stone podium with porte-cochere and a pool deck on its roof, cream slab with pilasters and
    window bays, amber lantern floor and a hip-roofed crown."""
    W, D = b.W, b.D
    wl, acc, rf, fh, n = v['wall'], v['accent'], v['roof'], v['fh'], v['floors']
    zp = 9.6
    P = (-W / 2 + 0.4, 3.3, W / 2 - 0.4, D - 0.4)
    b.box(P[0], P[1], 0, P[2], P[3], zp - 0.6, STONE, skip=('bottom', 'top'))
    ring(b, P, zp - 0.6, zp + 0.1, 0.2, WHITE, top=DECK)
    zr = zp + 0.1
    podium_front(b, P, 0.3, 4.0, glass='glass_dark', skip_u={'front': (-3.2, 3.2), 'back': (-5.5, 0.5)})
    for side in SIDES:
        u0, u1 = span(P, side)
        b.decal(side, u0 + 0.8, u1 - 0.8, 5.4, 7.8, 'glass', off=0.06, wall=wall(P, side))
    b.panel('front', -2.4, 2.4, 0, 3.0, SKY, off=0.04, depth=0.04, wall=P[1])
    b.decal('front', -0.05, 0.05, 0, 3.0, 'frame_black', off=0.09, wall=P[1])
    # porte-cochere
    b.box(-5.6, 0.3, 4.3, 5.6, P[1] + 0.2, 4.8, WHITE, skip=())
    b.decal('front', -5.6, 5.6, 4.35, 4.75, acc, off=0.05, wall=0.3)
    for x in (-4.6, 4.6):
        b.box(x - 0.3, 0.9, 0, x + 0.3, 1.5, 4.3, WHITE, skip=('bottom', 'top'))
    # loading dock at the back
    for xc in (-4.0, -1.0):
        b.panel('back', xc - 1.3, xc + 1.3, 0, 3.2, 'shutter', off=0.04, depth=0.04, wall=P[3])
        b.decal('back', xc - 1.25, xc + 1.25, 1.6, 1.66, 'shutter_groove', off=0.09, wall=P[3])
    # pool deck on the podium roof
    b.parapet(P[0] - 0.2, P[2] + 0.2, P[1] - 0.2, P[3] + 0.2, zr, 1.1, SKY, t=0.12)
    T = (-7.6, 9.8, 7.6, 18.4)
    cap(b, (-9.6, P[1] + 0.6, 7.0, T[1] + 0.2), zr, zr + 0.15, 'tile_floor', 'tile_floor')
    cap(b, (-6.4, P[1] + 1.6, 2.2, T[1] - 1.4), zr + 0.05, zr + 0.45, WHITE, POOL)
    for (x, y, c) in ((4.0, P[1] + 2.0, 'awning_orange'), (5.6, P[1] + 4.6, 'awning_white'), (-8.2, T[1] - 1.6, 'awning_orange')):
        b.box(x - 0.05, y - 0.05, zr + 0.15, x + 0.05, y + 0.05, zr + 2.3, 'metal', skip=('bottom',))
        cone(b, x, y, zr + 2.0, zr + 2.7, 1.2, c, seg=8)
    for x in (-W / 2 + 1.2, W / 2 - 1.2):
        plant_box(b, x - 0.5, P[1] + 0.6, x + 0.5, T[1] - 0.6, zr)
    plant_box(b, 8.2, T[1] + 0.2, W / 2 - 1.8, P[3] - 0.8, zr)
    # tower
    zt = zr + fh * n
    b.box(T[0], T[1], zr, T[2], T[3], zt, wl, skip=('bottom', 'top'))
    for side in ('front', 'back'):
        us = dividers(T[0], T[2], 5)
        for u in [T[0] + 0.2] + us + [T[2] - 0.2]:
            fin(b, T, side, u, zr, zt, 0.35, 0.5, WHITE, top=False)
        edges = [T[0] + 0.5] + us + [T[2] - 0.5]
        for k in range(n):
            z = zr + k * fh
            for i in range(len(edges) - 1):
                b.decal(side, edges[i] + 0.45, edges[i + 1] - 0.45, z + 0.8, z + 2.6, 'glass_dark', off=0.06, wall=wall(T, side))
    for side in ('left', 'right'):
        ym = (T[1] + T[3]) / 2
        b.panel(side, ym - 1.4, ym + 1.4, zr, zt, WHITE, off=0.3, depth=0.35, wall=wall(T, side))
        for k in range(n):
            z = zr + k * fh
            for yc in (T[1] + 1.5, T[3] - 1.5):
                b.decal(side, yc - 0.7, yc + 0.7, z + 0.8, z + 2.6, 'glass_dark', off=0.06, wall=wall(T, side))
    # crown: cornice, amber lantern floor with dark slits, hip roof
    ring(b, T, zt - 0.2, zt + 0.6, 0.5, WHITE)
    C = grow(T, -0.6)
    zc = zt + 0.6
    b.box(C[0], C[1], zc, C[2], C[3], zc + 3.4, acc, skip=('bottom', 'top'))
    for side in SIDES:
        u0, u1 = span(C, side)
        m = max(2, int(round((u1 - u0) / 1.6)))
        for u in dividers(u0, u1, m):
            b.decal(side, u - 0.3, u + 0.3, zc + 0.5, zc + 2.8, '#8a5a2a', off=0.06, wall=wall(C, side))
    b.roof_hip(C[0], C[2], C[1], C[3], zc + 3.4, 3.4, rf, over=0.45, thick=0.3)


def annulus(b, cx, cy, z, ri, ro, col, seg=16):
    """Flat upward-facing ring (helipad markings)."""
    P = lambda r, i: (cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg))
    for i in range(seg):
        j = (i + 1) % seg
        ai, aj, oi, oj = P(ri, i), P(ri, j), P(ro, i), P(ro, j)
        b.face([(ai[0], ai[1], z), (oi[0], oi[1], z), (oj[0], oj[1], z), (aj[0], aj[1], z)], col)


def s_stepped(b, v, rng):
    """Stepped setback tower: three blue-glass tiers with white vertical fins, roof gardens with glass rails
    and planters on every setback, a stone-clad shopfront base with the lobby entrance, and a helipad on
    top of the plant room."""
    W, D = b.W, b.D
    g, fc = v['glass'], v['fin']
    tiers = [(0.7, 0.0, 23.2), (3.1, 24.0, 38.4), (5.5, 39.2, 49.6)]
    zlb = 5.8                                        # top of the lobby band: tier-1 fins start here
    for ti, (ins, z0, z1) in enumerate(tiers):
        R = (-W / 2 + ins, ins, W / 2 - ins, D - ins)
        b.box(R[0], R[1], z0, R[2], R[3], z1, g, skip=('bottom', 'top'))
        for side in SIDES:
            u0, u1 = span(R, side)
            nb = max(3, int(round((u1 - u0) / 2.7)))
            for u in dividers(u0, u1, nb):
                if ti == 0:
                    fin(b, R, side, u, zlb, z1 - 0.1, 0.4, 0.34, fc, top=False, bottom=True)
                else:
                    fin(b, R, side, u, z0, z1 - 0.1, 0.4, 0.34, fc, top=False)
        corner_piers(b, R, z0, z1 - 0.1, 0.4, 0.6, fc, top=False)
        ring(b, R, z1 - 0.5, z1 + 0.8, 0.5, fc, top=DECK_GREEN if ti < 2 else v['deck'])
        zt = z1 + 0.8
        if ti < 2:
            O = grow(R, 0.5)
            b.parapet(O[0], O[2], O[1], O[3], zt, 1.1, SKY, t=0.12)
            ni = tiers[ti + 1][0]
            Rn = (-W / 2 + ni, ni, W / 2 - ni, D - ni)
            # planters all round the terrace, against the parapet
            plant_box(b, Rn[0], O[1] + 0.35, Rn[2], O[1] + 1.15, zt)
            plant_box(b, Rn[0], O[3] - 1.15, Rn[2], O[3] - 0.35, zt)
            plant_box(b, O[0] + 0.35, Rn[1] + 1.0, O[0] + 1.15, Rn[3] - 1.0, zt)
            plant_box(b, O[2] - 1.15, Rn[1] + 1.0, O[2] - 0.35, Rn[3] - 1.0, zt)
    # base: stone cladding with dark shopfront glazing between the corner piers, lobby band on top
    R0 = (-W / 2 + 0.7, 0.7, W / 2 - 0.7, D - 0.7)
    B = grow(R0, 0.12)
    b.box(B[0], B[1], 0, B[2], B[3], 5.0, GREY, skip=('bottom', 'top'))
    ring(b, R0, 5.0, zlb, 0.22, fc)
    podium_front(b, B, 0.3, 4.4, glass='glass_dark', step=2.3, skip_u={'front': (-2.2, 2.2), 'back': (-1.9, 1.9)})
    b.panel('front', -1.6, 1.6, 0, 2.8, SKY, off=0.04, depth=0.04, wall=B[1])
    b.decal('front', -0.05, 0.05, 0, 2.8, 'frame_black', off=0.09, wall=B[1])
    b.decal('front', -1.6, 1.6, 3.9, 4.6, 'glass_dark', off=0.06, wall=B[1])
    b.box(-2.8, 0.1, 3.2, 2.8, B[1] + 0.1, 3.6, fc, skip=())
    b.panel('back', -1.5, 1.5, 0, 3.0, 'shutter', off=0.04, depth=0.04, wall=B[3])
    for z in (0.75, 1.5, 2.25):
        b.decal('back', -1.45, 1.45, z, z + 0.06, 'shutter_groove', off=0.09, wall=B[3])
    # top: plant room carrying a helipad deck (round, dark, yellow ring + white edge line, no lettering)
    zt = tiers[2][2] + 0.8
    R2 = (-W / 2 + 5.5, 5.5, W / 2 - 5.5, D - 5.5)
    b.parapet(R2[0] - 0.5, R2[2] + 0.5, R2[1] - 0.5, R2[3] + 0.5, zt, 1.4, fc, t=0.3)
    cy = D / 2
    machine_room(b, -3.0, cy - 2.4, 3.0, cy + 2.6, zt, 4.2, col=fc, top=GREY_DARK)
    for (x, y) in ((-4.3, cy), (4.3, cy), (0.0, cy + 4.3), (1.6, cy - 4.0)):
        b.box(x - 0.18, y - 0.18, zt, x + 0.18, y + 0.18, zt + 4.2, GREY_DARK, skip=('bottom', 'top'))
    drum(b, 0.0, cy, zt + 4.2, zt + 4.6, 5.0, GREY_DARK, seg=16, bottom=True, top_col='#5a5e62')
    annulus(b, 0.0, cy, zt + 4.65, 3.1, 3.6, 'sign_yellow')
    annulus(b, 0.0, cy, zt + 4.65, 4.45, 4.7, WHITE)
    for a in range(4):                                # edge lights
        x, y = 4.75 * math.cos(math.pi / 4 + a * math.pi / 2), cy + 4.75 * math.sin(math.pi / 4 + a * math.pi / 2)
        b.box(x - 0.12, y - 0.12, zt + 4.6, x + 0.12, y + 0.12, zt + 4.78, AMBER)


def wedge_x(b, x0, y0, x1, y1, z0, zl, zh, col, top_col):
    """Solid with vertical sides and a roof sloping along x: height zl at x0, zh at x1 (bottom open)."""
    b.face([(x0, y0, zl), (x1, y0, zh), (x1, y1, zh), (x0, y1, zl)], top_col)
    b.face([(x0, y0, z0), (x1, y0, z0), (x1, y0, zh), (x0, y0, zl)], col)
    b.face([(x1, y1, z0), (x0, y1, z0), (x0, y1, zl), (x1, y1, zh)], col)
    b.face([(x0, y1, z0), (x0, y0, z0), (x0, y0, zl), (x0, y1, zl)], col)
    b.face([(x1, y0, z0), (x1, y1, z0), (x1, y1, zh), (x1, y0, zh)], col)


def s_twin(b, v, rng):
    """Twin slabs on a shared granite podium: dark teal glass, granite floor bands and piers, a sky bridge
    and mirrored sloping glass crowns that rise towards each other."""
    W, D = b.W, b.D
    g, fr, fh, n = v['glass'], v['frame'], v['fh'], v['floors']
    zp = 7.2
    P = (-W / 2 + 0.35, 0.35, W / 2 - 0.35, D - 0.35)
    b.box(P[0], P[1], 0, P[2], P[3], zp - 0.6, GRANITE_DARK, skip=('bottom', 'top'))
    ring(b, P, zp - 0.6, zp, 0.12, fr, top=DECK_GREEN)
    podium_front(b, P, 0.3, 4.2, glass='glass_dark', skip_u={'front': (-2.0, 2.0), 'back': (-2.0, 2.0)})
    b.panel('front', -1.8, 1.8, 0, 2.7, SKY, off=0.04, depth=0.04, wall=P[1])
    b.box(-3.0, 0.08, 3.3, 3.0, P[1] + 0.1, 3.6, WHITE, skip=())
    b.panel('back', -1.6, 1.6, 0, 3.0, 'shutter', off=0.04, depth=0.04, wall=P[3])
    for side in SIDES:
        u0, u1 = span(P, side)
        b.decal(side, u0 + 0.8, u1 - 0.8, 4.9, 6.3, 'glass', off=0.06, wall=wall(P, side))
    for (x0, x1) in ((P[0] + 1.0, -3.4), (3.4, P[2] - 1.0)):
        plant_box(b, x0, P[1] + 0.5, x1, P[1] + 1.2, zp)
    zt = zp + fh * n
    slabs = [(-W / 2 + 0.9, 1.4, -2.9, D - 1.4), (2.9, 1.4, W / 2 - 0.9, D - 1.4)]
    for si, S in enumerate(slabs):
        x0, y0, x1, y1 = S
        b.box(x0, y0, zp, x1, y1, zt, g, skip=('bottom', 'top'))
        for k in range(n - 1):
            z = zp + (k + 1) * fh
            ring(b, S, z - 0.8, z, 0.18, fr)
        corner_piers(b, S, zp, zt + 0.2, 0.36, 0.7, fr, top=False)
        xm = (x0 + x1) / 2
        for side in ('front', 'back'):
            fin(b, S, side, xm, zp, zt + 0.2, 0.36, 0.6, fr, top=False)
        ring(b, S, zt - 0.4, zt + 0.5, 0.42, fr, top=v['deck'])
        # sloping glass crown: rises towards the gap between the slabs; a flat plant deck on the outer side
        zr = zt + 0.5
        if si == 0:
            xo, xw, xi = x0, x0 + 2.6, x1
            ha, hb = zt + 2.4, zt + 5.4             # crown height at xw (left end) and xi (right end)
            wedge_x(b, xw, y0, xi, y1, zt + 0.4, ha, hb, g, v['crown'])
            inner = 'right'
        else:
            xo, xw, xi = x1, x1 - 2.6, x0
            ha, hb = zt + 5.4, zt + 2.4             # at xi (left end) and xw (right end)
            wedge_x(b, xi, y0, xw, y1, zt + 0.4, ha, hb, g, v['crown'])
            inner = 'left'
        xa, xb = min(xw, xi), max(xw, xi)
        zs = lambda x: ha + (hb - ha) * (x - xa) / (xb - xa)
        # floor lines + mullions on the crown's front, back and inner faces, clipped under the slope
        m = 0.3
        for (za, zb_) in ((zt + 1.0, zt + 1.35), (zt + 2.7, zt + 3.05), (zt + 4.4, zt + 4.75)):
            iv = []
            for z in (za, zb_):
                lo, hi = xa + 0.1, xb - 0.1
                xz = xa + (z + m - ha) / (hb - ha) * (xb - xa)
                if hb > ha:
                    lo = max(lo, xz)
                else:
                    hi = min(hi, xz)
                iv.append((lo, hi))
            if iv[1][1] - iv[1][0] > 0.4:
                (l0, h0), (l1, h1) = iv
                yf, yk = y0 - 0.1, y1 + 0.1
                b.face([(l0, yf, za), (h0, yf, za), (h1, yf, zb_), (l1, yf, zb_)], fr)
                b.face([(h0, yk, za), (l0, yk, za), (l1, yk, zb_), (h1, yk, zb_)], fr)
            b.decal(inner, y0 + 0.1, y1 - 0.1, za, zb_, fr, off=0.1, wall=xi)
        for u in dividers(xa, xb, 3):
            for (yy, sgn) in ((y0 - 0.06, 1), (y1 + 0.06, -1)):
                a, c = (u - 0.15, u + 0.15) if sgn > 0 else (u + 0.15, u - 0.15)
                b.face([(a, yy, zr), (c, yy, zr), (c, yy, zs(c) - m), (a, yy, zs(a) - m)], fr)
        for u in dividers(y0, y1, 4):
            b.decal(inner, u - 0.15, u + 0.15, zr, max(ha, hb) - m, fr, off=0.06, wall=xi)
        # granite ribs running down the glass slope (rims on the front and back edges)
        for yk in (y0 + 0.15, y0 + (y1 - y0) / 3, y0 + 2 * (y1 - y0) / 3, y1 - 0.15):
            top = [(xa - 0.05, yk - 0.2, ha + 0.15), (xb + 0.05, yk - 0.2, hb + 0.15), (xb + 0.05, yk + 0.2, hb + 0.15), (xa - 0.05, yk + 0.2, ha + 0.15)]
            b._slab(top, [(p[0], p[1], p[2] - 0.35) for p in top], fr)
        # plant deck on the outer side: plant room + condensers
        pa, pb = sorted((xo + (0.3 if si == 0 else -0.3), xo + (2.3 if si == 0 else -2.3)))
        machine_room(b, pa, y0 + 1.2, pb, y0 + 5.6, zr, 2.6, col=GRANITE_DARK, top='#6e6862')
        for yc in (y1 - 1.6, y1 - 3.0):
            condenser(b, (pa + pb) / 2, yc, zr)
    # sky bridge
    zb = zp + fh * 7 - 0.3
    b.box(-3.1, 5.2, zb, 3.1, D - 5.2, zb + 3.0, SKY, skip=('bottom', 'top'))
    b.box(-3.1, 5.0, zb - 0.6, 3.1, D - 5.0, zb, fr, skip=())
    b.box(-3.1, 5.0, zb + 3.0, 3.1, D - 5.0, zb + 3.5, fr, skip=())


def s_round(b, v, rng):
    """Round glass tower on a square stone podium: a white band every floor, a white service core rising
    up the back, recessed glass crown ring around the roof, round plant room and a mast."""
    W, D = b.W, b.D
    g, bd, fh, n = v['glass'], v['band'], v['fh'], v['floors']
    R = W / 2 - 0.9
    cx, cy = 0.0, R + 0.6
    zp = 6.0
    P = (-W / 2 + 0.4, 0.4, W / 2 - 0.4, D - 0.4)
    b.box(P[0], P[1], 0, P[2], P[3], zp - 0.5, STONE, skip=('bottom', 'top'))
    ring(b, P, zp - 0.5, zp, 0.12, WHITE, top=DECK_GREEN)
    podium_front(b, P, 0.3, 4.0, glass='glass_dark', skip_u={'front': (-2.0, 2.0), 'back': (-2.0, 2.0)})
    b.panel('front', -1.6, 1.6, 0, 2.7, SKY, off=0.04, depth=0.04, wall=P[1])
    b.box(-2.8, 0.1, 3.2, 2.8, P[1] + 0.1, 3.5, WHITE, skip=())
    b.panel('back', -1.5, 1.5, 0, 2.9, 'shutter', off=0.04, depth=0.04, wall=P[3])
    for (x, y) in ((P[0] + 1.0, P[1] + 1.0), (P[2] - 1.0, P[1] + 1.0), (P[0] + 1.0, P[3] - 1.0), (P[2] - 1.0, P[3] - 1.0)):
        plant_box(b, x - 0.55, y - 0.55, x + 0.55, y + 0.55, zp)
    zt = zp + fh * n
    drum(b, cx, cy, zp, zt, R, g, top=False)
    for k in range(1, n):
        z = zp + k * fh
        drum(b, cx, cy, z - 0.45, z + 0.35, R + 0.25, bd, top=True, bottom=True)
    drum(b, cx, cy, zp, zp + 0.6, R + 0.3, bd, top=True, bottom=False)
    # crown: glass screen ring + white cap, plant room inside
    zd = zt + 0.3                                  # roof deck = top of the crown band
    drum(b, cx, cy, zt - 0.4, zd, R + 0.3, bd, top=True, bottom=True, top_col=v['deck'])
    tube(b, cx, cy, zd - 0.1, zt + 3.4, R - 0.35, R, g, top=False)
    tube(b, cx, cy, zt + 3.4, zt + 4.0, R - 0.45, R + 0.3, bd, top=True, bottom=True)
    # round plant room turned 15 degrees so a flat facet (not a corner) faces the front: the door sits on it
    ph = math.pi / 12
    drum(b, cx, cy + 0.6, zd - 0.1, zd + 4.2, 2.6, bd, seg=12, top_col=GREY_DARK, phase=ph)
    b.door('front', cx, 0.9, 2.1, color='door_dark', frame=GREY_DARK, z0=zd, wall=cy + 0.6 - 2.6 * math.cos(ph))
    for x in (cx - 4.3, cx + 4.3):
        for y in (cy - 1.6, cy - 0.3):
            condenser(b, x, y, zd)
    mast(b, cx, cy + 0.6, zd + 4.2, 3.4, w=0.35)
    # service core (lifts + stairs) up the back of the drum
    C = (-2.6, cy + R - 1.2, 2.6, D - 0.45)
    cap(b, C, zp, zt + 5.4, bd, DECK)
    for k in range(n):
        z = zp + k * fh
        b.decal('back', -0.7, 0.7, z + 1.0, z + 2.6, 'glass_dark', off=0.06, wall=C[3])
    for side in ('left', 'right'):
        b.decal(side, C[3] - 1.2, C[3] - 0.6, zp + 0.5, zt + 4.8, GREY, off=0.06, wall=wall(C, side))
    tank(b, -1.2, (C[1] + C[3]) / 2 + 0.2, zt + 5.4, r=0.7, h=1.3, col='tank_blue')
    tank(b, 1.2, (C[1] + C[3]) / 2 + 0.2, zt + 5.4, r=0.7, h=1.3, col='tank_blue')


def s_grid(b, v, rng):
    """Older concrete-grid office (1990s Jakarta): white floor bands and close mullion fins over dark glass,
    stone base with shopfronts, a big blank rooftop board on a steel frame, tanks."""
    W, D = b.W, b.D
    g, fr, fh, n = v['glass'], v['frame'], v['fh'], v['floors']
    r = (-W / 2 + 0.7, 0.7, W / 2 - 0.7, D - 0.7)
    x0, y0, x1, y1 = r
    zb = 4.6
    B = grow(r, 0.2)
    b.box(B[0], B[1], 0, B[2], B[3], zb, STONE, skip=('bottom', 'top'))
    podium_front(b, B, 0.3, 3.4, glass='glass_dark', step=2.0, skip_u={'front': (-1.6, 1.6), 'back': (-1.6, 1.6)})
    b.panel('front', -1.4, 1.4, 0, 2.6, SKY, off=0.04, depth=0.04, wall=B[1])
    b.box(-2.4, 0.1, 3.0, 2.4, B[1] + 0.1, 3.3, fr, skip=())
    b.panel('back', -1.4, 1.4, 0, 2.8, 'shutter', off=0.04, depth=0.04, wall=B[3])
    zt = zb + fh * n
    b.box(x0, y0, zb, x1, y1, zt, g, skip=('bottom', 'top'))
    for k in range(n + 1):
        z = zb + k * fh
        # the base and roof rings project further than the fins (0.42) so they close the fin and pier ends
        ring(b, r, z - 0.35, z + 0.45, 0.47 if k in (0, n) else 0.25, fr, top=v['deck'] if k == n else None)
    for side in SIDES:
        u0, u1 = span(r, side)
        for u in dividers(u0, u1, max(4, int(round((u1 - u0) / 1.6)))):
            fin(b, r, side, u, zb + 0.4, zt - 0.3, 0.42, 0.26, fr, top=False)
    corner_piers(b, r, zb, zt - 0.3, 0.42, 0.5, fr, top=False)
    zr = zt + 0.45
    b.parapet(x0 - 0.47, x1 + 0.47, y0 - 0.47, y1 + 0.47, zr, 1.0, fr, t=0.3)
    tank(b, x0 + 1.8, y1 - 2.0, zr, r=0.9, h=1.8, col='tank_orange')
    tank(b, x0 + 4.2, y1 - 2.0, zr, r=0.9, h=1.8, col='tank_orange')
    machine_room(b, 1.0, y1 - 4.4, x1 - 0.9, y1 - 0.9, zr, 3.2, col='wall_grey', top=GREY_DARK)
    # rooftop board facing the street (blank colour board with bar decals, no text)
    yb = y0 + 1.6
    for x in (-4.0, 0.0, 4.0):
        b.box(x - 0.14, yb + 0.1, zr, x + 0.14, yb + 0.38, zr + 7.0, 'metal')
        b.box(x - 0.1, yb + 0.3, zr, x + 0.1, yb + 2.2, zr + 0.2, 'metal')
    u0, u1, z0, z1 = -5.4, 5.4, zr + 2.4, zr + 6.8
    b.sign('front', u0, u1, z0, z1, v['sign'], bars=0, off=0.0, wall=yb)
    b.face([(u0, yb, z0), (u0, yb + 0.1, z0), (u1, yb + 0.1, z0), (u1, yb, z0)], v['sign'])   # board underside
    L, H = u1 - u0, z1 - z0                          # the two blank 'lettering' bars, 5 cm proud of the board
    b.decal('front', u0 + L * 0.14, u1 - L * 0.14, z0 + H * 0.52, z0 + H * 0.78, 'sign_white', off=0.05, wall=yb)
    b.decal('front', u0 + L * 0.26, u1 - L * 0.26, z0 + H * 0.22, z0 + H * 0.4, 'sign_white', off=0.05, wall=yb)
    b.decal('back', -5.3, 5.3, zr + 2.5, zr + 6.7, 'metal', off=0.04, wall=yb + 0.1)


def s_rusun(b, v, rng):
    """Rusun / mid-rise public housing slab: balconies with colour-banded balustrades at the front, open
    access galleries at the back that lead into a stair + lift tower on the right end, tanks on the tower,
    big terracotta hip roof."""
    W, D = b.W, b.D
    wl, acc, rf, fh, n = v['wall'], v['accent'], v['roof'], v['fh'], v['floors']
    bal, gal = 1.2, 1.6
    r = (-W / 2 + 0.6, 0.35 + bal, W / 2 - 4.3, D - 0.35 - gal)
    x0, y0, x1, y1 = r
    zg = 3.6
    zt = zg + fh * n
    # ground floor: kiosks under the slab
    b.box(x0, y0, 0, x1, y1, zg, 'wall_grey', skip=('bottom',))
    nb = 4
    bays = dividers(x0, x1, nb)
    edges = [x0] + bays + [x1]
    kc = ['awning_blue', 'awning_green', 'awning_red', 'awning_yellow']
    for i in range(nb):
        a, c = edges[i] + 0.5, edges[i + 1] - 0.5
        b.panel('front', a, c, 0, 2.6, 'shutter', off=0.04, depth=0.04, wall=y0)
        b.decal('front', a + 0.05, c - 0.05, 1.3, 1.36, 'shutter_groove', off=0.09, wall=y0)
        b.panel('front', a, c, 2.75, 3.3, kc[i], off=0.1, depth=0.08, wall=y0)
    b.door('back', x0 + 2.0, 1.4, 2.4, color='door_dark', frame=GREY, wall=y1)
    b.box(x0, y0, zg, x1, y1, zt, wl, skip=('bottom', 'top'))
    cols = [acc, 'wall_teal', acc, 'wall_teal']
    for k in range(n):
        z = zg + k * fh
        # front balconies
        b.box(x0 + 0.1, y0 - bal, z - 0.15, x1 - 0.1, y0 + 0.05, z + 0.1, WHITE, skip=('back',))
        for i in range(nb):
            a, c = edges[i] + 0.3, edges[i + 1] - 0.3
            b.box(a, y0 - bal, z + 0.1, c, y0 - bal + 0.12, z + 1.05, cols[i])
            b.decal('front', a + 0.3, a + 1.3, z + 0.2, z + 2.3, 'door_wood', off=0.06, wall=y0)
            b.decal('front', a + 1.8, c - 0.3, z + 1.0, z + 2.2, 'glass', off=0.06, wall=y0)
        # back galleries
        b.box(x0 + 0.1, y1 - 0.05, z - 0.15, x1 + 0.1, y1 + gal, z + 0.1, GREY, skip=('front', 'right'))
        b.box(x0 + 0.1, y1 + gal - 0.14, z + 0.1, x1 + 0.1, y1 + gal, z + 1.0, WHITE, skip=('bottom', 'right'))
        for i in range(nb * 2):
            u = x0 + (x1 - x0) * (i + 0.5) / (nb * 2)
            b.decal('back', u - 0.45, u + 0.45, z + 0.1, z + 2.2, 'door_dark', off=0.06, wall=y1)
    for u in bays:
        fin(b, r, 'front', u, zg, zt, bal + 0.1, 0.35, WHITE)
    for u in (x0 + 0.1, x1 - 0.1):
        fin(b, r, 'front', u, zg, zt, bal + 0.1, 0.3, WHITE)
    fin(b, r, 'back', x0 + 0.1, zg, zt, gal + 0.1, 0.3, WHITE)
    ym = y0 + (y1 - y0) * 0.35
    for side in ('left', 'right'):
        for k in range(n):
            z = zg + k * fh
            b.decal(side, ym - 0.7, ym + 0.7, z + 0.9, z + 2.2, 'glass', off=0.06, wall=wall(r, side))
    # stair + lift tower against the right end wall, behind the front rooms; the galleries run into it
    S = (x1 - 0.05, y0 + (y1 - y0) * 0.6, W / 2 - 0.6, y1 + gal + 0.1)
    zs = zt + 4.2
    cap(b, S, 0, zs, acc, v['deck'], bottom=False)
    b.parapet(S[0], S[2], S[1], S[3], zs, 0.6, acc, t=0.2)
    sx = (S[0] + S[2]) / 2
    b.door('back', sx, 1.3, 2.3, color='door_dark', frame=GREY, wall=S[3])
    b.decal('back', sx - 0.55, sx + 0.55, zg + 0.4, zt + 2.6, 'glass', off=0.06, wall=S[3])
    b.decal('front', sx - 0.55, sx + 0.55, zg + 0.4, zt + 2.6, 'glass', off=0.06, wall=S[1])
    for yc in dividers(S[1], S[3], 3):
        b.decal('right', yc - 0.45, yc + 0.45, 1.0, zt + 2.6, 'glass', off=0.06, wall=S[2])
    for zz in (zg - 0.6, zt + 1.0):                   # white bands under the first gallery and above the eaves
        ring(b, S, zz, zz + 0.4, 0.08, WHITE)
    tank(b, S[0] + 1.0, (S[1] + S[3]) / 2 - 1.2, zs, r=0.55, h=1.2, col='tank_orange')
    tank(b, S[2] - 1.0, (S[1] + S[3]) / 2 + 1.2, zs, r=0.55, h=1.2, col='tank_blue')
    b.roof_hip(x0, x1, y0 - 0.2, y1 + 0.2, zt, 3.4, rf, over=0.4, thick=0.2)


def chamfer(r, c):
    """Rectangle with 45-degree cut corners, counter-clockwise from above (front edge first)."""
    x0, y0, x1, y1 = r
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


def prism(b, pts, z0, z1, cols, top_col=None, bottom=False):
    """Vertical prism over a CCW polygon; `cols` is one colour or one per edge."""
    n = len(pts)
    for i in range(n):
        a, d = pts[i], pts[(i + 1) % n]
        c = cols if isinstance(cols, str) else cols[i]
        b.face([(a[0], a[1], z0), (d[0], d[1], z0), (d[0], d[1], z1), (a[0], a[1], z1)], c)
    if top_col:
        b.face([(p[0], p[1], z1) for p in pts], top_col)
    if bottom:
        c = cols if isinstance(cols, str) else cols[0]
        b.face([(p[0], p[1], z0) for p in reversed(pts)], c)


def pyramid(b, pts, z0, z1, cx, cy, col):
    for i in range(len(pts)):
        a, d = pts[i], pts[(i + 1) % len(pts)]
        b.face([(a[0], a[1], z0), (d[0], d[1], z0), (cx, cy, z1)], col)


def oct_band(b, r, c, out, z0, z1, col):
    """Thin band `out` proud of a chamfered core: outer faces plus the top and bottom ledges back to the core."""
    K = 2 - math.sqrt(2)
    i = chamfer(r, c)
    o = chamfer(grow(r, out), c + out * K)
    prism(b, o, z0, z1, col)
    for k in range(8):
        j = (k + 1) % 8
        b.face([(i[k][0], i[k][1], z1), (o[k][0], o[k][1], z1), (o[j][0], o[j][1], z1), (i[j][0], i[j][1], z1)], col)
        b.face([(i[j][0], i[j][1], z0), (o[j][0], o[j][1], z0), (o[k][0], o[k][1], z0), (i[k][0], i[k][1], z0)], col)


def oct_wall(b, r, c, t, z0, z1, col):
    """Parapet following a chamfered outline: outer face on chamfer(r, c), `t` thick, closed top."""
    K = 2 - math.sqrt(2)
    o = chamfer(r, c)
    i = chamfer(grow(r, -t), max(0.0, c - t * K))
    prism(b, o, z0, z1, col)
    for k in range(8):
        j = (k + 1) % 8
        b.face([(i[j][0], i[j][1], z0), (i[k][0], i[k][1], z0), (i[k][0], i[k][1], z1), (i[j][0], i[j][1], z1)], col)
        b.face([(i[k][0], i[k][1], z1), (o[k][0], o[k][1], z1), (o[j][0], o[j][1], z1), (i[j][0], i[j][1], z1)], col)


def s_octa(b, v, rng):
    """Chamfered-corner office tower: slate glass on all eight faces with champagne floor lines, a flush cream
    band every four floors, a granite base with an entrance portal, and a set-back glass crown floor under
    a flat roof with a parapet, a plant room and two aviation masts."""
    W, D = b.W, b.D
    g, gc, bd, fl, fh, n = v['glass'], v['glass2'], v['band'], v['line'], v['fh'], v['floors']
    K = 2 - math.sqrt(2)                              # chamfer growth per unit of outward offset
    r = (-W / 2 + 0.6, 0.6, W / 2 - 0.6, D - 0.6)
    c = 1.6
    zl = 6.0
    zt = zl + fh * n
    body = chamfer(r, c)
    prism(b, body, zl, zt, [g, gc] * 4)               # faces: front, corner, right, corner, back, corner, left, corner
    # base: dark glass faces between granite corners on a granite plinth
    prism(b, body, 0.0, zl, ['glass_dark', GRANITE_DARK] * 4)
    prism(b, chamfer(grow(r, 0.12), c + 0.12 * K), 0.0, 0.6, GRANITE_DARK, top_col=GRANITE_DARK)
    for side in SIDES:
        u0, u1 = span(r, side)
        u0, u1 = u0 + c, u1 - c
        w = wall(r, side)
        for u in dividers(u0, u1, 4):
            if (side == 'front' and abs(u) < 2.6) or (side == 'back' and abs(u) < 1.8):
                continue
            b.decal(side, u - 0.07, u + 0.07, 0.6, zl, 'frame_black', off=0.05, wall=w)
        b.decal(side, u0, u1, 3.4, 3.6, 'frame_black', off=0.08, wall=w)
        # dark mullion strips on every glass face (the floor lines below run over them)
        for u in dividers(u0, u1, 4):
            b.decal(side, u - 0.22, u + 0.22, zl, zt, v['mull'], off=0.05, wall=w)
    # entrance: granite portal standing proud of the front, glass doors, transom and a canopy
    yf = r[1]
    b.panel('front', -2.3, 2.3, 0.0, 5.0, GRANITE, off=0.3, depth=0.35, wall=yf)
    b.panel('front', -1.5, 1.5, 0.0, 2.8, SKY, off=0.34, depth=0.04, wall=yf)
    b.decal('front', -0.05, 0.05, 0.0, 2.8, 'frame_black', off=0.39, wall=yf)
    b.decal('front', -1.5, 1.5, 3.9, 4.6, 'glass_dark', off=0.35, wall=yf)
    b.box(-3.0, 0.02, 3.2, 3.0, yf + 0.12, 3.55, bd, skip=())
    b.panel('back', -1.5, 1.5, 0, 2.9, 'shutter', off=0.04, depth=0.04, wall=r[3])
    for z in (0.75, 1.5, 2.25):
        b.decal('back', -1.45, 1.45, z, z + 0.06, 'shutter_groove', off=0.09, wall=r[3])
    # light floor lines wrapping all eight faces
    for k in range(1, n):
        if k % 4:
            z = zl + k * fh
            oct_band(b, r, c, 0.09, z - 0.3, z, fl)
    # flush white bands (10 cm proud) at the lobby top and every fourth floor, cornice at the roof
    for z in [zl] + [zl + k * fh for k in range(4, n, 4)]:
        prism(b, chamfer(grow(r, 0.1), c + 0.1 * K), z - 0.5, z + 0.3, bd, top_col=bd, bottom=True)
    prism(b, chamfer(grow(r, 0.3), c + 0.3 * K), zt - 0.3, zt + 0.7, bd, top_col=v['deck'], bottom=True)
    # crown: set-back glass floor, cornice + parapet, flat roof with a plant room and two masts
    L = grow(r, -1.0)
    cl = c - 1.0 * K
    zc = zt + 0.7
    prism(b, chamfer(L, cl), zc, zc + 3.6, [g, gc] * 4)
    for side in SIDES:
        u0, u1 = span(L, side)
        for u in dividers(u0 + cl, u1 - cl, 4):
            b.decal(side, u - 0.2, u + 0.2, zc, zc + 3.6, v['mull'], off=0.05, wall=wall(L, side))
    zr = zc + 4.2
    prism(b, chamfer(grow(L, 0.25), cl + 0.25 * K), zc + 3.6, zr, bd, top_col=v['deck'], bottom=True)
    oct_wall(b, grow(L, 0.25), cl + 0.25 * K, 0.25, zr, zr + 0.9, bd)
    cx, cy = 0.0, D / 2
    machine_room(b, -1.6, cy - 1.8, 3.2, cy + 2.2, zr, 3.2, col=GRANITE, top=GRANITE_DARK)
    mast(b, -3.2, cy + 1.8, zr, 7.0)
    mast(b, 2.4, cy + 1.2, zr + 3.2, 3.2)
    condenser(b, -3.4, cy - 1.4, zr)


STYLES = {'office': s_office, 'apartment': s_apartment, 'hotel': s_hotel, 'stepped': s_stepped,
          'twin': s_twin, 'round': s_round, 'grid': s_grid, 'rusun': s_rusun, 'octa': s_octa}


def build(b, v, rng):
    STYLES[v['style']](b, v, rng)

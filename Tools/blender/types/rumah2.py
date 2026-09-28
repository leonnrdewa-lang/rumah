"""Rumah minimalis 2 lantai: the two-storey modern perumahan house of Jakarta's suburbs.

Boxy volumes, a carport with a sliding steel gate behind a low front fence, big black-framed windows,
accent panels (wood slats, batu alam stone cladding, dark frames), and one of three roof families:
flat dak with parapet + toren, low single-slope metal roof, or a low limasan hip roof.

Three massing archetypes (every variant picks one, with the carport on the left or the right):
  'over'    the upper floor runs over the carport, carried by a stone wing wall or a column
            (optionally split in two volumes with different roofs)
  'terrace' the carport roof is a concrete slab used as an open terrace in front of a set-back room
  'flush'   both floors share one front line, cantilever balcony on the house side, steel canopy
            over the carport

Plan positions in this module are written as s = distance from the carport-side lot edge (0..W) and
mapped to x by xr()/xs(), so one description serves both mirror images.
"""
import math

TYPE = 'rumah2'
ROLES = ['front', 'fill']

INWARD = {'front': 'back', 'back': 'front', 'left': 'right', 'right': 'left'}

# NB: the game's warm sky light washes pale paints out to cream, so walls use fairly saturated
# pastels and roof decks are darker than real concrete to read as grey from the game camera.
BASE = {
    'wall': '#f1efe6', 'gwall': None, 'wall2': '#d9d8d3', 'accent': '#3f4044', 'frame': '#2d2a28',
    'glass': '#3b5570', 'wood': '#b07542', 'wood_line': '#7a4a28', 'stone': '#8f8579', 'stone_line': '#6a6157',
    'deck': '#77736d', 'roof': '#5b6068', 'tile': '#c9b89e', 'gate': '#2e2c2a', 'rail': '#2e2c2a',
    'rglass': '#8fc0d6', 'floor': '#a9a399', 'grass': '#5f8a45', 'hedge': '#3f7a3a',
    'toren': '#e8872c', 'canopy': '#6e757c', 'parapet': None, 'fwall': None, 'door': '#8a5a3a',
    'door2': '#6b4a33',
}
TYRE = '#2a2a2c'
CAR_GLASS = '#26323f'


# ------------------------------------------------------------------------------------ small helpers
def slab(b, side, u0, u1, z0, z1, color, off=0.04, depth=0.04, wall=None, bottom=False):
    """Block proud of a wall (like Bld.panel) without the face inside the wall (and the underside)."""
    m, _ = b._frame(side, wall)
    (xa, ya), (xb, yb) = m(u0, off - depth), m(u1, off)
    b.box(xa, ya, z0, xb, yb, z1, color, skip=(INWARD[side],) if bottom else (INWARD[side], 'bottom'))


def quad_up(b, x0, y0, x1, y1, z, color):
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    b.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], color)


def win(b, side, u0, u1, z0, z1, frame, glass, wall=None, panes=2, transom=None, t=0.07):
    """Modern window: a dark frame block with the glass pane on its face and thin mullions."""
    slab(b, side, u0 - t, u1 + t, z0 - t, z1 + t, frame, off=0.05, depth=0.05, wall=wall)
    b.decal(side, u0, u1, z0, z1, glass, off=0.062, wall=wall)
    for i in range(1, panes):
        u = u0 + (u1 - u0) * i / panes
        b.decal(side, u - 0.025, u + 0.025, z0, z1, frame, off=0.072, wall=wall)
    if transom:
        zt = z1 - transom
        b.decal(side, u0, u1, zt - 0.025, zt + 0.025, frame, off=0.08, wall=wall)


def slats(b, side, u0, u1, z0, z1, base, line, wall=None, pitch=0.16, off=0.05):
    """Wood-slat accent panel (kisi-kisi kayu): a wood block with dark vertical joints."""
    slab(b, side, u0, u1, z0, z1, base, off=off, depth=off, wall=wall)
    n = max(2, int(round((u1 - u0) / pitch)))
    for i in range(1, n):
        u = u0 + (u1 - u0) * i / n
        b.decal(side, u - 0.018, u + 0.018, z0 + 0.02, z1 - 0.02, line, off=off + 0.012, wall=wall)


def stone(b, side, u0, u1, z0, z1, base, line, wall=None, off=0.05, step=0.3):
    """Batu alam cladding: a stone-coloured block with horizontal coursing lines."""
    slab(b, side, u0, u1, z0, z1, base, off=off, depth=off, wall=wall)
    z = z0 + step
    while z < z1 - 0.12:
        b.decal(side, u0 + 0.02, u1 - 0.02, z - 0.02, z + 0.02, line, off=off + 0.012, wall=wall)
        z += step


def door(b, side, u0, u1, z0, h, color, frame, wall=None, grooves=0, handle='#c9c6bd'):
    t = 0.07
    slab(b, side, u0 - t, u1 + t, z0, z0 + h + t, frame, off=0.05, depth=0.05, wall=wall)
    b.decal(side, u0, u1, z0, z0 + h, color, off=0.062, wall=wall)
    for i in range(1, grooves + 1):
        u = u0 + (u1 - u0) * i / (grooves + 1)
        b.decal(side, u - 0.012, u + 0.012, z0 + 0.1, z0 + h - 0.1, '#5a3a24', off=0.07, wall=wall)
    ha = u1 - 0.14 if (u1 - u0) < 1.05 else u0 + (u1 - u0) * 0.5 + 0.08
    b.decal(side, ha - 0.02, ha + 0.02, z0 + 0.8, z0 + 1.4, handle, off=0.075, wall=wall)


def elem(b, side, wall, kind, u0, u1, zlo, zhi, P):
    """One facade element between u0..u1 on a storey spanning zlo..zhi."""
    fr, gl = P['frame'], P['glass']
    w = u1 - u0
    if kind == 'W':      # big window (almost floor to ceiling)
        z0, z1 = zlo + 0.45, zhi - 0.4
        win(b, side, u0, u1, z0, z1, fr, gl, wall, panes=max(2, int(round(w / 0.75))), transom=0.5 if z1 - z0 > 1.8 else None)
    elif kind == 'w':    # ordinary window
        win(b, side, u0, u1, zlo + 0.95, min(zhi - 0.45, zlo + 2.3), fr, gl, wall, panes=2 if w > 0.9 else 1)
    elif kind == 'h':    # high bathroom/kitchen window
        win(b, side, u0, u1, zlo + 1.75, min(zhi - 0.45, zlo + 2.3), fr, gl, wall, panes=1)
    elif kind == 'N':    # narrow vertical strip window
        win(b, side, u0, u1, zlo + 0.35, zhi - 0.45, fr, gl, wall, panes=1)
    elif kind == 'D':    # sliding glass door (balcony)
        win(b, side, u0, u1, zlo + 0.07, zlo + 2.35, fr, gl, wall, panes=2 if w < 1.8 else 3, transom=0.45)
    elif kind == 'd':    # main entrance door, wood
        door(b, side, u0, u1, zlo, 2.35, P['door'], fr, wall, grooves=3 if w > 1.05 else 2)
    elif kind == 'k':    # side / service door
        door(b, side, u0, u1, zlo, 2.1, P['door2'], fr, wall, grooves=0)
    elif kind == 'S':    # wood slats, full storey
        slats(b, side, u0, u1, zlo + 0.05, zhi - 0.05, P['wood'], P['wood_line'], wall)
    elif kind == 'T':    # stone cladding, full storey
        stone(b, side, u0, u1, zlo, zhi, P['stone'], P['stone_line'], wall)


def place(items, a, c, margin=0.3, min_gap=0.25):
    """Spread (kind, width) items evenly across a..c (shrinking them if they do not fit)."""
    total = sum(w for _, w in items)
    room = (c - a) - 2 * margin - min_gap * (len(items) - 1)
    if total > room:
        k = room / total
        items = [(t, w * k) for t, w in items]
        total = sum(w for _, w in items)
    gap = ((c - a) - total) / (len(items) + 1)
    out, s = [], a + gap
    for t, w in items:
        out.append((t, s, s + w))
        s += w + gap
    return out


def car(b, cx, y0, color, length=4.2, width=1.72):
    """Generic MPV parked nose-in (front of the car towards +y)."""
    x0, x1, y1 = cx - width / 2, cx + width / 2, y0 + length
    for ya in (y0 + 0.78, y1 - 0.8):
        b.box(x0 - 0.02, ya - 0.33, 0, x1 + 0.02, ya + 0.33, 0.62, TYRE, skip=('bottom', 'top'))
    b.box(x0, y0, 0.3, x1, y1, 0.98, color)
    zb, zt = 0.98, 1.6
    bx0, bx1, by0, by1 = x0 + 0.06, x1 - 0.06, y0 + 0.25, y1 - 1.25
    tx0, tx1, ty0, ty1 = x0 + 0.16, x1 - 0.16, y0 + 0.4, y1 - 1.75
    b.face([(bx0, by0, zb), (bx1, by0, zb), (tx1, ty0, zt), (tx0, ty0, zt)], CAR_GLASS)
    b.face([(bx1, by1, zb), (bx0, by1, zb), (tx0, ty1, zt), (tx1, ty1, zt)], CAR_GLASS)
    b.face([(bx0, by1, zb), (bx0, by0, zb), (tx0, ty0, zt), (tx0, ty1, zt)], CAR_GLASS)
    b.face([(bx1, by0, zb), (bx1, by1, zb), (tx1, ty1, zt), (tx1, ty0, zt)], CAR_GLASS)
    b.face([(tx0, ty0, zt), (tx1, ty0, zt), (tx1, ty1, zt), (tx0, ty1, zt)], color)


def motorbike(b, cx, y0, color):
    """Parked scooter (length along y)."""
    b.box(cx - 0.05, y0, 0.0, cx + 0.05, y0 + 1.75, 0.5, TYRE)
    b.box(cx - 0.17, y0 + 0.25, 0.35, cx + 0.17, y0 + 1.35, 0.78, color)
    b.box(cx - 0.15, y0 + 0.35, 0.78, cx + 0.15, y0 + 1.0, 0.86, '#2b2826')
    b.box(cx - 0.3, y0 + 1.4, 0.95, cx + 0.3, y0 + 1.48, 1.02, '#2b2826')
    b.box(cx - 0.12, y0 + 1.35, 0.5, cx + 0.12, y0 + 1.5, 0.95, color, skip=('bottom', 'top'))


def toren(b, cx, cy, z0, color, stand=0.35, r=0.5, h=1.0):
    """Water tank (toren) on a steel stand."""
    if stand > 0:
        for dx in (-0.36, 0.36):
            for dy in (-0.36, 0.36):
                b.box(cx + dx - 0.04, cy + dy - 0.04, z0, cx + dx + 0.04, cy + dy + 0.04, z0 + stand - 0.06, 'metal', skip=('bottom', 'top'))
        b.box(cx - 0.46, cy - 0.46, z0 + stand - 0.06, cx + 0.46, cy + 0.46, z0 + stand, 'metal', skip=())
    b.cyl(cx, cy, z0 + stand, z0 + stand + h, r, color, seg=10)


def ac_box(b, cx, cy, z0):
    """AC condenser standing on a roof deck, fan towards the street."""
    b.box(cx - 0.4, cy - 0.15, z0, cx + 0.4, cy + 0.15, z0 + 0.55, 'ac_white')
    b.decal('front', cx - 0.3, cx + 0.05, z0 + 0.1, z0 + 0.45, 'metal', off=0.01, wall=cy - 0.15)


def dish(b, cx, cy, z0, r=0.42):
    """Satellite dish on a short post, aimed up and towards the street."""
    b.box(cx - 0.04, cy - 0.04, z0, cx + 0.04, cy + 0.04, z0 + 0.75, 'metal', skip=('bottom',))
    c = (cx, cy - 0.05, z0 + 0.95)
    e2 = (0.0, 0.707, 0.707)
    pts = []
    for i in range(8):
        a = 2 * math.pi * i / 8
        u, w = math.cos(a) * r, math.sin(a) * r
        pts.append((c[0] + u, c[1] + w * e2[1], c[2] + w * e2[2]))
    b.face(pts, '#e8e6e0')
    b.face(pts[::-1], '#b9b7b0')


def pot(b, x, y, z0=0.0, s=1.0, leaf='plant'):
    """Square planter with a shrub (cheaper than Bld.plant_pot)."""
    b.box(x - 0.22 * s, y - 0.22 * s, z0, x + 0.22 * s, y + 0.22 * s, z0 + 0.4 * s, '#8c8a86')
    b.box(x - 0.3 * s, y - 0.3 * s, z0 + 0.4 * s, x + 0.3 * s, y + 0.3 * s, z0 + 0.95 * s, leaf)


def tree(b, x, y, h=2.8, r=0.85):
    """Small garden tree: trunk + two stacked octagonal crowns."""
    b.box(x - 0.08, y - 0.08, 0.0, x + 0.08, y + 0.08, h - 1.0, '#6b4a33', skip=('bottom', 'top'))
    b.cyl(x, y, h - 1.2, h - 0.5, r, '#4a8a3c', seg=8)
    b.cyl(x, y, h - 0.5, h, r * 0.62, '#5a9a44', seg=8)


def double_quad(b, pts, color):
    b.face(pts, color)
    b.face(pts[::-1], color)


def jemuran(b, xa, xb, y, z0, colors, h=1.7):
    """Clothesline between two posts with a few pieces of laundry (along x at y)."""
    xa, xb = min(xa, xb), max(xa, xb)
    for x in (xa, xb):
        b.box(x - 0.04, y - 0.04, z0, x + 0.04, y + 0.04, z0 + h, 'metal', skip=('bottom',))
    b.box(xa + 0.04, y - 0.012, z0 + h - 0.1, xb - 0.04, y + 0.012, z0 + h - 0.07, 'metal', skip=('bottom', 'left', 'right'))
    n = len(colors)
    span = (xb - xa - 0.3) / n
    for i, c in enumerate(colors):
        u0 = xa + 0.15 + i * span + 0.05
        u1 = u0 + span - 0.12
        zb = z0 + h - 0.1 - (0.7 if i % 2 == 0 else 0.5)
        double_quad(b, [(u0, y, zb), (u1, y, zb), (u1, y, z0 + h - 0.1), (u0, y, z0 + h - 0.1)], c)


def solar_heater(b, cx, cy, z0):
    """Rooftop solar water heater (generic): collector tilted towards the street + tank on top."""
    x0, x1 = cx - 0.9, cx + 0.9
    ya, yb_ = cy - 0.55, cy + 0.55
    top = [(x0, ya, z0 + 0.3), (x1, ya, z0 + 0.3), (x1, yb_, z0 + 0.85), (x0, yb_, z0 + 0.85)]
    bot = [(p[0], p[1], p[2] - 0.06) for p in top]
    b._slab(top, bot, '#2c3e5c')
    for x in (x0 + 0.1, x1 - 0.1):
        b.box(x - 0.03, ya + 0.05, z0, x + 0.03, ya + 0.11, z0 + 0.27, 'metal', skip=('bottom', 'top'))
        b.box(x - 0.03, yb_ - 0.11, z0, x + 0.03, yb_ - 0.05, z0 + 0.8, 'metal', skip=('bottom', 'top'))
    b.box(x0 - 0.05, yb_ - 0.05, z0 + 0.8, x1 + 0.05, yb_ + 0.3, z0 + 1.15, '#e4e2dc')


def rail(b, xa, ya, xb, yb, z0, style, P, h=1.0, post_every=1.6):
    """Balcony railing along an axis-aligned line: 'glass' (glass pane + black handrail) or 'steel'
    (black flat bars). Stays within 0.04 of the line."""
    along_x = abs(ya - yb) < 1e-6
    lo, hi = (min(xa, xb), max(xa, xb)) if along_x else (min(ya, yb), max(ya, yb))
    c = ya if along_x else xa

    def seg(z_0, z_1, th, col, skip=('bottom',), inset=0.0):
        if along_x:
            b.box(lo + inset, c - th / 2, z_0, hi - inset, c + th / 2, z_1, col, skip=skip)
        else:
            b.box(c - th / 2, lo + inset, z_0, c + th / 2, hi - inset, z_1, col, skip=skip)

    def post(p):
        if along_x:
            b.box(p - 0.03, c - 0.035, z0, p + 0.03, c + 0.035, z0 + h - 0.06, P['rail'], skip=('bottom', 'top'))
        else:
            b.box(c - 0.035, p - 0.03, z0, c + 0.035, p + 0.03, z0 + h - 0.06, P['rail'], skip=('bottom', 'top'))
    n = max(1, int(round((hi - lo) / post_every)))
    if style == 'glass':
        seg(z0 + 0.06, z0 + h - 0.06, 0.02, P['rglass'], skip=('bottom', 'top'), inset=0.02)
        seg(z0 + h - 0.06, z0 + h, 0.07, P['rail'])
    else:
        seg(z0 + h - 0.06, z0 + h, 0.06, P['rail'])
        ends = ('left', 'right') if along_x else ('front', 'back')
        for zz in (0.62, 0.32):
            seg(z0 + h * zz, z0 + h * zz + 0.05, 0.04, P['rail'], skip=('bottom',) + ends)
    for i in range(n + 1):
        post(lo + 0.03 + (hi - lo - 0.06) * i / n)


# ------------------------------------------------------------------------------------ variants
# Props: (kind, s, y, ...) with s measured from the carport-side lot edge (negative: from the far
# lot edge) and y from the front (negative: from the back wall of the upper floor). Their height is
# taken from whichever roof deck lies under that point.
def variants():
    V = []
    # 0: narrow white house, upper floor over the carport on a stone wing wall, flat roof + orange toren
    V.append(dict(w=6.0, d=10.0, arch='over', cp='L', cw=3.0, gc=5.0, gh=2.5, by=1.6, uy0=1.1, z1=3.3, zr=6.4,
                  support='wing', roof=dict(kind='flat', ph=0.6), bingkai=(0.0, 3.3, 0.45),
                  up=[(0.0, 3.3, [('W', 2.2)]), (3.3, 6.0, [('S', 0.8), ('N', 0.5)])],
                  gf=[('d', 1.1), ('w', 1.1)], cf=[('k', 0.85), ('h', 0.8)],
                  car='#ecebe6', fence='rail',
                  props=[('toren', -0.8, -0.9, '#e8872c'), ('ac', -0.7, -2.3), ('ac', -0.7, -3.3), ('dish', 0.9, -1.0),
                         ('jemuran', 0.7, 3.6, 3.2)],
                  pal=dict(wall='#f1efe6', accent='#3f4044', stone='#8a7f73')))
    # 1: cream + brown, carport terrace with glass railing, low shed roof rising to the back
    V.append(dict(w=7.0, d=11.0, arch='terrace', cp='R', cw=3.2, gc=5.3, gh=2.2, by=1.8, cy0=0.6, z1=3.3, zr=6.5, zrb=6.1,
                  roof=dict(kind='shed', dir='y', f=0.0, b=0.9, over=(0.4, 0.3, 0.4)), roofb=dict(kind='flat', ph=0.45),
                  up=[(3.2, 7.0, [('W', 1.8), ('S', 0.7)])], upb=[('D', 1.6)],
                  gf=[('d', 1.1), ('W', 1.4)], cf=[('k', 0.85), ('w', 1.0)],
                  car='#b8322c', fence='wall', terr_rail='glass',
                  props=[('pots', 3), ('ac', 1.0, -0.6), ('ac', 2.1, -0.6)], back_tower=True,
                  pal=dict(wall='#e6c89a', wall2='#f0e2c6', accent='#6b4430', roof='#7a4630', frame='#3e2c20',
                           door='#6b4430', gate='#4a3426', rail='#3a2a20', stone='#b9a17f', stone_line='#94805f',
                           toren='#3c78b5', parapet='#6b4430', deck='#7d766c')))
    # 2: two-tone (white ground floor, grey upper), everything flush, low charcoal hip roof, steel canopy
    V.append(dict(w=8.0, d=12.0, arch='flush', cp='L', cw=3.3, g=4.6, by=2.0, ext=2.2, si=0.45, z1=3.3, zr=6.3,
                  roof=dict(kind='hip', rise=1.3, over=0.45), balc=(3.1, 7.55, 1.1, 'steel'),
                  up=[(0.45, 7.55, [('w', 1.4), ('D', 1.6), ('S', 1.0)])],
                  gf=[('d', 1.2), ('W', 1.8)], cf=[('k', 0.85), ('T', 1.3)],
                  fence='rail', canopy=True, tree=2.8,
                  props=[('toren', -1.1, 9.0, '#ecebe4'), ('jemuran_back',), ('ac', 1.5, 9.4)],
                  pal=dict(wall='#a9a6a0', gwall='#f1efe6', wall2='#f1efe6', accent='#3f4247', roof='#3a3d42',
                           frame='#2a2a2c', canopy='#4f555c', parapet='#f1efe6', stone='#9a8f84')))
    # 3: white + black, upper floor over the carport on a column, wood cantilever box, floating slab roof
    #    with a small roof garden
    V.append(dict(w=9.0, d=12.0, arch='over', cp='R', cw=3.4, gc=5.3, gh=3.0, by=1.8, uy0=1.6, z1=3.4, zr=6.3,
                  support='col', roof=dict(kind='slab', over=(1.0, 0.0, 0.3), t=0.32),
                  cbox=(0.2, 3.6, 0.9, 'wood'),
                  up=[(3.6, 9.0, [('w', 1.3), ('T', 1.1), ('N', 0.45)])],
                  gf=[('W', 1.8), ('d', 1.2), ('T', 1.1)], cf=[('k', 0.85), ('h', 1.0)],
                  car='#27282b', fence='rail',
                  props=[('patch', 0.4, 4.6, 0.9, 4.2, '#6a4632'), ('pots_row', 0.8, 4.2, 1.2, 4),
                         ('planter', 5.0, 8.6, 0.95), ('toren', -1.0, -1.0, '#ecebe4'), ('solar', 5.4, -1.3),
                         ('ac', -1.0, -2.6)],
                  pal=dict(wall='#f4f3ee', accent='#2c2c2e', deck='#6d6a65', gate='#2c2c2e', stone='#57534e',
                           stone_line='#3c3935', wood='#8f5a34')))
    # 4: sand + terracotta, big terrace over the carport, split flat roofs (red waterproofing) with laundry
    V.append(dict(w=10.0, d=13.0, arch='terrace', cp='L', cw=3.5, gc=5.5, gh=2.0, by=2.0, cy0=0.6, z1=3.3, zr=6.6, zrb=6.0,
                  roof=dict(kind='flat', ph=0.5), roofb=dict(kind='flat', ph=0.5),
                  up=[(3.5, 10.0, [('S', 1.1), ('W', 2.4), ('w', 1.2)])], upb=[('D', 1.8)],
                  gf=[('d', 1.2), ('W', 2.2), ('w', 1.0)], cf=[('k', 0.9), ('w', 1.0)],
                  car='#bfc3c6', fence='wall', terr_rail='steel',
                  props=[('toren', -1.0, -1.0, '#e8872c'), ('jemuran', 4.3, 7.4, 8.0), ('pots', 2), ('ac', -2.5, -0.5),
                         ('ac', 1.2, -0.6), ('dish', 2.6, -0.9)],
                  pal=dict(wall='#dcb98a', wall2='#f0e4cc', accent='#b5603e', parapet='#b5603e', frame='#3a2b22',
                           deck='#6b7a6a', tile='#c98b62', door='#7a4a2c', gate='#3a2b22', rail='#3a2b22')))
    # 5: mint + white, wide house with double carport, terracotta hip roof, white cantilever box
    V.append(dict(w=11.0, d=13.0, arch='flush', cp='R', cw=5.4, g=5.4, by=2.0, ext=2.4, si=0.45, z1=3.4, zr=6.5,
                  roof=dict(kind='hip', rise=1.3, over=0.45), balc=(6.1, 10.2, 1.2, 'glass'),
                  cbox=(0.8, 3.4, 0.8, 'wall2'),
                  up=[(3.4, 5.9, [('W', 1.4)]), (5.9, 10.55, [('D', 1.6), ('w', 1.2)])],
                  gf=[('d', 1.2), ('W', 1.8)], cf=[('k', 0.9), ('w', 1.2), ('T', 1.4)],
                  car='#2f4f7a', car2=True, fence='rail', canopy=True, tree=3.0,
                  props=[('toren', -1.0, 10.0, '#3c78b5'), ('ac', 1.3, 10.4), ('jemuran', 2.2, 5.6, 9.2)],
                  pal=dict(wall='#86b8a8', wall2='#f2f1ea', accent='#f2f1ea', roof='#a4533a', frame='#2d2a28',
                           canopy='#4d5359', parapet='#f2f1ea', fwall='#f2f1ea', stone='#8f8579')))
    # 6: narrow pale-blue house, upper floor on a column, shed roof high at the street behind a box frame
    V.append(dict(w=6.5, d=9.0, arch='over', cp='R', cw=3.0, gc=4.8, gh=2.2, by=1.5, uy0=0.9, z1=3.2, zr=6.2,
                  support='col', roof=dict(kind='shed', dir='y', f=1.0, b=0.0, over=(0.0, 0.4, 0.0), front_wall=0.4),
                  bingkai=(0.0, 6.5, 0.35),
                  up=[(0.0, 6.5, [('w', 1.6), ('S', 0.8), ('w', 1.2)])],
                  gf=[('d', 1.0), ('w', 1.2)], cf=[('k', 0.85)],
                  moto='#c23a33', fence='rail', back_tower=True,
                  props=[],
                  pal=dict(wall='#86acd6', accent='#f4f4ef', roof='#4b5561', frame='#2b3038', gate='#4b5561',
                           rail='#2b3038', toren='#ecebe4', fwall='#f4f4ef')))
    # 7: soft yellow + grey, terrace over the carport, brown hip roof over the house side, lower flat room
    V.append(dict(w=8.5, d=11.0, arch='terrace', cp='L', cw=3.3, gc=5.2, gh=1.8, by=1.8, cy0=0.5, z1=3.3, zr=6.5, zrb=5.9,
                  si=0.4, roof=dict(kind='hip', rise=1.2, over=0.4), roofb=dict(kind='flat', ph=0.4),
                  up=[(3.3, 8.1, [('w', 1.3), ('S', 0.6), ('w', 1.3)])], upb=[('D', 1.5)],
                  gf=[('W', 1.6), ('d', 1.1)], cf=[('k', 0.85), ('h', 0.9)],
                  car='#e6e4de', fence='rail', terr_rail='steel',
                  props=[('toren', 1.3, -0.9, '#e8872c'), ('pots', 2), ('ac', 2.6, -2.6)],
                  pal=dict(wall='#e3d08e', wall2='#f4f1e8', accent='#6d7075', roof='#553a2e', frame='#2d2a28',
                           parapet='#6d7075', tile='#d6c9b3', stone='#9a8f84')))
    # 8: big house: double carport under a flat-roofed wing (with rooftop kit) + a hip-roofed main wing
    V.append(dict(w=14.0, d=14.0, arch='over', cp='L', cw=6.0, gc=5.8, gh=3.4, by=2.2, uy0=1.4, z1=3.4, zr=6.0, si=0.4,
                  support='wing', roof=dict(kind='flat', ph=0.45), bingkai=(0.4, 6.2, 0.5),
                  split=(6.6, dict(kind='hip', rise=1.35, over=0.4), 6.5),
                  up=[(0.4, 6.2, [('W', 2.6), ('S', 1.0), ('N', 0.5)]), (6.6, 13.6, [('W', 2.2), ('w', 1.2), ('W', 2.2)])],
                  gf=[('W', 2.2), ('d', 1.3), ('W', 2.2), ('w', 1.2)], cf=[('k', 0.9), ('T', 1.6), ('w', 1.2)],
                  car='#a9adb0', car2=True, fence='wall',
                  props=[('toren', 1.2, -1.0, '#3c78b5'), ('toren', 2.5, -1.0, '#3c78b5'), ('solar', 3.4, 4.2),
                         ('ac', 5.4, -0.6), ('ac', 5.4, -1.6), ('dish', 1.2, 3.0), ('planter', 0.8, 5.9, 1.95)],
                  pal=dict(wall='#f4f2ec', accent='#34353a', stone='#4d4a47', stone_line='#35322f', roof='#34424f',
                           wood='#b8793f', gate='#34353a', deck='#6f6d69')))
    # 9: warm grey + white, flush front, single-slope roof falling sideways, orange wood slats
    V.append(dict(w=12.0, d=13.0, arch='flush', cp='R', cw=3.5, g=5.0, by=2.0, ext=0.0, si=0.0, z1=3.3, zr=6.2,
                  roof=dict(kind='shed', dir='x', f=1.1, b=0.0, over=(0.4, 0.4, 0.0)), balc=(3.5, 12.0, 1.2, 'glass'),
                  up=[(0.0, 12.0, [('W', 2.2), ('S', 1.2), ('D', 1.8), ('w', 1.2)])],
                  gf=[('W', 2.4), ('d', 1.2), ('w', 1.2)], cf=[('k', 0.85), ('h', 1.0)],
                  car='#8c1f24', fence='wall', canopy=True, back_tower=True, tree=3.2,
                  props=[],
                  pal=dict(wall='#a39c92', wall2='#f3f1ea', accent='#f3f1ea', roof='#2f5566', wood='#c07a3e',
                           frame='#2d2a28', canopy='#5d646b', toren='#e8872c', fwall='#f3f1ea')))
    # 10: greige + black, flush front with a wood cantilever box, flat roof with red waterproofing and
    #     a tiled roof terrace
    V.append(dict(w=7.5, d=12.0, arch='flush', cp='L', cw=3.2, g=4.4, by=1.8, ext=0.0, si=0.0, z1=3.3, zr=6.3,
                  roof=dict(kind='flat', ph=0.6), cbox=(3.7, 7.1, 0.9, 'wood'),
                  up=[(0.0, 3.6, [('w', 1.5), ('N', 0.45)])],
                  gf=[('d', 1.1), ('W', 1.6)], cf=[('k', 0.85), ('h', 0.9)],
                  car='#d9d7d0', fence='rail', canopy=True,
                  props=[('patch', 0.3, 4.2, 4.6, 7.2, '#b9a58a'), ('pots_row', 0.6, 3.8, 4.95, 3),
                         ('toren', -0.9, -0.9, '#ecebe4'), ('jemuran', 0.6, 4.4, 9.0), ('ac', -0.8, -2.3)],
                  pal=dict(wall='#c6b7a3', accent='#2d2d30', parapet='#2d2d30', wood='#9a6035', deck='#8a5a48',
                           canopy='#3f4448', gate='#2d2d30', stone='#8a8078', fwall='#ecebe4')))
    # 11: teal + white, upper floor over the carport on a stone wall; flat-roofed wing over the carport and
    #     a white main wing under a low single-slope roof rising to the back
    V.append(dict(w=9.5, d=11.0, arch='over', cp='R', cw=3.3, gc=5.0, gh=2.4, by=1.6, uy0=1.2, z1=3.3, zr=6.0,
                  support='wing', roof=dict(kind='flat', ph=0.5),
                  split=(3.5, dict(kind='shed', dir='y', f=0.2, b=1.0, over=(0.4, 0.3, 0.0)), 6.3, 'wall2'),
                  up=[(0.0, 3.5, [('W', 2.1)]), (3.5, 9.5, [('w', 1.3), ('S', 0.9), ('W', 1.8)])],
                  gf=[('d', 1.1), ('W', 2.0), ('w', 1.0)], cf=[('k', 0.85), ('h', 0.9)],
                  car='#7d8ea3', fence='wall',
                  props=[('toren', 1.2, -1.0, '#e8872c'), ('ac', 2.4, -2.4), ('dish', 1.0, 2.4)],
                  pal=dict(wall='#7fb3ad', wall2='#f3f1ea', accent='#34383c', roof='#6b2f2c', parapet='#f3f1ea',
                           fwall='#f3f1ea', stone='#9a8f84', wood='#b37040')))
    return V


# ------------------------------------------------------------------------------------ builder
def build(b, v, rng):
    W, D = b.W, b.D
    X0, X1 = -W / 2, W / 2
    P = dict(BASE)
    P.update(v.get('pal', {}))
    P['parapet'] = P['parapet'] or P['wall']
    left = v['cp'] == 'L'
    CS, HS = ('left', 'right') if left else ('right', 'left')

    def xr(a, c):
        return (X0 + a, X0 + c) if left else (X1 - c, X1 - a)

    def xs(a):
        return X0 + a if left else X1 - a

    def sk(skip):
        return tuple({'cs': CS, 'hs': HS}.get(n, n) for n in skip)

    def B(a, y0, z0, c, y1, z1, col, skip=('bottom',)):
        xa, xc = xr(a, c)
        b.box(xa, y0, z0, xc, y1, z1, col, skip=sk(skip))

    def Q(a, y0, c, y1, z, col):
        xa, xc = xr(a, c)
        quad_up(b, xa, y0, xc, y1, z, col)

    def front_prog(items, a, c, y, zlo, zhi, margin=0.3):
        for kind, s0, s1 in place(items, a, c, margin):
            if kind != '.':
                u0, u1 = xr(s0, s1)
                elem(b, 'front', y, kind, u0, u1, zlo, zhi, P)

    arch, cw, si = v['arch'], v['cw'], v.get('si', 0.0)
    Z1, ZR = v['z1'], v['zr']
    yb = D - v['by']
    ext = v.get('ext', 0.0)
    uyb = yb - ext
    wall, wall2 = P['wall'], P['wall2']
    gwall = P['gwall'] or wall
    if arch == 'flush':
        gc = gh = v['g']
    else:
        gc, gh = v['gc'], v['gh']
    roof = v['roof']
    decks = []    # (s0, s1, y0, y1, z) flat areas props can stand on

    # ---------------------------------------------------------------- yard, fence, gate
    fwall = P['fwall'] or gwall
    Q(0.3, 0.3, cw, gc, 0.04, P['floor'])                              # carport floor
    terr0 = max(0.45, gh - 1.4)
    if terr0 > 0.75:
        Q(cw, 0.3, W - si, terr0, 0.03, P['grass'])                    # front garden
    B(cw, terr0, 0, W - si, gh, 0.15, P['tile'], skip=('bottom', 'back'))   # entrance terrace
    ph = 1.75
    cap = P['accent'] if P['accent'] not in (fwall, P['wall2']) else P['stone']
    for a, c in ((0.02, 0.3), (cw - 0.14, cw + 0.14), (W - 0.3, W - 0.02)):
        B(a, 0.02, 0, c, 0.3, ph, P['stone'] if v['fence'] == 'rail' else fwall)
        B(a - 0.02, 0.0, ph, c + 0.02, 0.32, ph + 0.1, cap)
    # sliding gate across the carport: steel posts + horizontal slats
    g0, g1 = 0.3, cw - 0.14
    gy0, gy1 = 0.1, 0.15
    gm = (g0 + g1) / 2
    for a in (g0, gm - 0.03, g1 - 0.06):
        B(a, gy0 - 0.01, 0.05, a + 0.06, gy1 + 0.01, 1.62, P['gate'])
    for z in (0.15, 0.42, 0.69, 0.96, 1.23):
        B(g0 + 0.06, gy0, z, g1 - 0.06, gy1, z + 0.15, P['gate'], skip=('bottom', 'left', 'right'))
    B(g0 + 0.06, gy0, 1.5, g1 - 0.06, gy1, 1.6, P['gate'], skip=('bottom', 'left', 'right'))
    # house-side fence
    f0, f1 = cw + 0.14, W - 0.3
    if v['fence'] == 'rail':
        B(f0, 0.05, 0, f1, 0.25, 0.55, fwall, skip=('bottom', 'left', 'right'))
        for zz in (0.8, 1.1, 1.4):
            B(f0, 0.12, zz, f1, 0.17, zz + 0.08, P['gate'], skip=('bottom', 'left', 'right'))
        n = max(1, int(round((f1 - f0) / 1.4)))
        for i in range(1, n):
            a = f0 + (f1 - f0) * i / n
            B(a - 0.03, 0.11, 0.55, a + 0.03, 0.18, 1.5, P['gate'], skip=('bottom',))
    else:
        B(f0, 0.05, 0, f1, 0.25, 1.45, fwall, skip=('bottom', 'left', 'right'))
        u0, u1 = xr(f0 + 0.25, f0 + 1.25)
        slats(b, 'front', u0, u1, 0.1, 1.35, P['wood'], P['wood_line'], wall=0.05, off=0.03, pitch=0.12)
    if terr0 > 1.3:
        B(f0 + 0.05, 0.3, 0, f1 - 0.05, 0.7, 0.85, P['hedge'], skip=('bottom',))   # hedge behind the fence
    if v.get('tree') and terr0 > 2.4:
        tree(b, xs(W - si - 1.2), (0.7 + terr0) / 2 + 0.1, h=v['tree'])

    # ---------------------------------------------------------------- ground floor
    # walls; the tops are drawn as deck quads (hidden under the upper floor, visible as dak elsewhere)
    if gc == gh:
        B(si, gc, 0, W - si, yb, Z1, gwall, skip=('bottom', 'top'))
        Q(si, gc, W - si, yb, Z1, P['deck'])
    else:
        B(si, gc, 0, cw, yb, Z1, gwall, skip=('bottom', 'top', 'hs'))
        B(cw, gh, 0, W - si, yb, Z1, gwall, skip=('bottom', 'top'))
        Q(si, gc, cw, yb, Z1, P['deck'])
        Q(cw, gh, W - si, yb, Z1, P['deck'])
        if gc - gh > 1.6:   # side wall of the house next to the carport: window
            elem(b, CS, xs(cw), 'w', gh + 0.6, min(gc - 0.5, gh + 1.8), 0.0, Z1, P)
    u0, u1 = xr(si, W - si)
    b.decal('back', u0, u1, 0.0, 0.3, P['stone_line'], off=0.02, wall=yb)          # plinth
    front_prog(v['gf'], cw, W - si, gh, 0.15, Z1)                                   # house front
    front_prog(v['cf'], si, cw, gc, 0.04, Z1, margin=0.35)                          # wall behind the carport
    # ground floor back: service door under a small canopy, window, AC
    ku = xr(si + 0.6, si + 1.45)
    door(b, 'back', ku[0], ku[1], 0.0, 2.1, P['door2'], P['frame'], wall=yb)
    wu = xr(W - si - 2.2, W - si - 0.9)
    win(b, 'back', wu[0], wu[1], 1.2, 2.2, P['frame'], P['glass'], wall=yb, panes=2)
    au = xr(si + 0.25, si + 1.8)
    b.awning('back', au[0], au[1], 2.55, out=0.9, drop=0.25, color=P['canopy'], wall=yb, thick=0.05)
    b.ac_unit('back', xs(si + 2.4), 2.3, wall=yb)
    if yb - gh > 3.5 and si >= 0.1:   # side windows only where the walls step in from the lot line
        elem(b, HS, xs(W - si), 'w', gh + 1.2, gh + 2.4, 0.0, Z1, P)
    Q(si, yb, W - si, D - 0.05, 0.03, P['floor'])                                   # back yard paving

    # ---------------------------------------------------------------- carport structure
    car_s0, car_s1 = si + 0.25, cw - 0.2
    if arch == 'over':
        uy0 = v['uy0']
        if v['support'] == 'wing':
            B(si, uy0, 0, si + 0.22, gc, Z1, P['stone'], skip=('bottom', 'top'))
            stone(b, HS, uy0 + 0.05, gc - 0.05, 0.0, Z1, P['stone'], P['stone_line'], wall=xs(si + 0.22), off=0.03)
            car_s0 = si + 0.4
        else:
            B(si + 0.1, uy0 + 0.1, 0, si + 0.4, uy0 + 0.4, Z1, P['accent'], skip=('bottom', 'top'))
    elif arch == 'terrace':
        cy0 = v['cy0']
        B(si, cy0, Z1 - 0.3, cw, gc, Z1, P['accent'], skip=('top', 'back'))
        Q(si, cy0, cw, gc, Z1, P['tile'])
        decks.append((si, cw, cy0, gc, Z1))
        for a in (si + 0.08, cw - 0.38):
            B(a, cy0 + 0.08, 0, a + 0.3, cy0 + 0.38, Z1 - 0.3, P['accent'], skip=('bottom', 'top'))
        st = v.get('terr_rail', 'steel')
        rail(b, xs(si + 0.05), cy0 + 0.05, xs(cw - 0.05), cy0 + 0.05, Z1, st, P)
        rail(b, xs(si + 0.05), cy0 + 0.12, xs(si + 0.05), gc, Z1, st, P)
        if gh > cy0 + 0.2:
            rail(b, xs(cw - 0.05), cy0 + 0.12, xs(cw - 0.05), gh, Z1, st, P)
    elif v.get('canopy'):   # flush: light steel canopy over the carport, sloping to the street
        zh, zl = Z1 - 0.35, Z1 - 0.75
        a, c = xr(0.08, cw - 0.08)
        top = [(a, 0.45, zl + 0.05), (c, 0.45, zl + 0.05), (c, gc, zh + 0.05), (a, gc, zh + 0.05)]
        bot = [(p[0], p[1], p[2] - 0.05) for p in top]
        b._slab(top, bot, P['canopy'])
        B(0.1, 0.48, zl - 0.14, cw - 0.1, 0.56, zl + 0.005, P['rail'])
        for s in (0.12, cw - 0.2):
            B(s, 0.49, 0, s + 0.08, 0.55, zl - 0.14, P['rail'], skip=('bottom', 'top'))
    if v.get('car'):
        mid = (car_s0 + car_s1) / 2
        cars = [mid]
        if v.get('car2'):
            cars = [car_s0 + (mid - car_s0) / 2 + 0.1, car_s1 - (car_s1 - mid) / 2 - 0.1]
        for k, cs in enumerate(cars):
            car(b, xs(cs), 0.7 if k == 0 else 0.9, v['car'] if k == 0 else '#e9e8e3')
    if v.get('moto'):
        motorbike(b, xs((car_s0 + car_s1) / 2), 1.5, v['moto'])

    # ---------------------------------------------------------------- upper floor + roof
    def ribs(pts_fn, n, color):
        for i in range(n):
            b.face(pts_fn(i), color)

    def upper(a, c, y0, y1, zt, rf, bottom, col):
        """Walls of an upper volume a..c (s) x y0..y1 from Z1 to zt, and its roof. Flat decks are
        registered for props."""
        k = rf['kind']
        x0, x1 = xr(a, c)
        if k == 'shed':
            of, ob, osd = rf['over']
            thick = 0.12
            X0r, X1r = max(X0, x0 - osd), min(X1, x1 + osd)
            rib = '#%02x%02x%02x' % tuple(int(int(P['roof'][i:i + 2], 16) * 0.72) for i in (1, 3, 5))
            if rf['dir'] == 'y':      # slope front <-> back; f/b = extra wall height at the front/back
                zf, zb = zt + rf['f'], zt + rf['b']
                b.face([(x0, y0, Z1), (x1, y0, Z1), (x1, y0, zf), (x0, y0, zf)], col)
                b.face([(x1, y1, Z1), (x0, y1, Z1), (x0, y1, zb), (x1, y1, zb)], col)
                b.face([(x0, y1, Z1), (x0, y0, Z1), (x0, y0, zf), (x0, y1, zb)], col)
                b.face([(x1, y0, Z1), (x1, y1, Z1), (x1, y1, zb), (x1, y0, zf)], col)
                sl = (zb - zf) / (y1 - y0)
                if rf.get('front_wall'):
                    of = -0.2      # the roof starts behind the front parapet wall
                za, zc = zf - sl * of + thick, zb + sl * ob + thick
                top = [(X0r, y0 - of, za), (X1r, y0 - of, za), (X1r, y1 + ob, zc), (X0r, y1 + ob, zc)]
                n = max(3, int((X1r - X0r) / 0.9))
                ribs(lambda i: [(X0r + (X1r - X0r) * (i + 0.5) / n - 0.03, y0 - of, za + 0.015),
                                (X0r + (X1r - X0r) * (i + 0.5) / n + 0.03, y0 - of, za + 0.015),
                                (X0r + (X1r - X0r) * (i + 0.5) / n + 0.03, y1 + ob, zc + 0.015),
                                (X0r + (X1r - X0r) * (i + 0.5) / n - 0.03, y1 + ob, zc + 0.015)], n, rib)
                if rf.get('front_wall'):
                    # tall front parapet that hides the slope from the street (boxy "kotak" facade)
                    fh = max(zf, zb) + rf['front_wall']
                    b.box(x0, y0, zf, x1, y0 + 0.2, fh, col, skip=('bottom',))
            else:                     # slope sideways; f = extra height at the carport side
                hc, hh = zt + rf['f'], zt + rf['b']
                zl, zr_ = (hc, hh) if left else (hh, hc)
                b.face([(x0, y0, Z1), (x1, y0, Z1), (x1, y0, zr_), (x0, y0, zl)], col)
                b.face([(x1, y1, Z1), (x0, y1, Z1), (x0, y1, zl), (x1, y1, zr_)], col)
                b.face([(x0, y1, Z1), (x0, y0, Z1), (x0, y0, zl), (x0, y1, zl)], col)
                b.face([(x1, y0, Z1), (x1, y1, Z1), (x1, y1, zr_), (x1, y0, zr_)], col)
                sl = (zr_ - zl) / (x1 - x0)
                zL, zR = zl - sl * (x0 - X0r) + thick, zr_ + sl * (X1r - x1) + thick
                top = [(X0r, y0 - of, zL), (X1r, y0 - of, zR), (X1r, y1 + ob, zR), (X0r, y1 + ob, zL)]
                Y0r, Y1r = y0 - of, y1 + ob
                n = max(3, int((Y1r - Y0r) / 0.9))
                ribs(lambda i: [(X0r, Y0r + (Y1r - Y0r) * (i + 0.5) / n - 0.03, zL + 0.015),
                                (X1r, Y0r + (Y1r - Y0r) * (i + 0.5) / n - 0.03, zR + 0.015),
                                (X1r, Y0r + (Y1r - Y0r) * (i + 0.5) / n + 0.03, zR + 0.015),
                                (X0r, Y0r + (Y1r - Y0r) * (i + 0.5) / n + 0.03, zL + 0.015)], n, rib)
            if bottom:
                b.face([(x0, y0, Z1), (x0, y1, Z1), (x1, y1, Z1), (x1, y0, Z1)], col)
            bot = [(p[0], p[1], p[2] - thick) for p in top]
            b._slab(top, bot, P['roof'])
            return
        b.box(x0, y0, Z1, x1, y1, zt, col, skip=('top',) if bottom else ('top', 'bottom'))
        if k == 'flat':
            quad_up(b, x0, y0, x1, y1, zt, P['deck'])
            b.parapet(x0, x1, y0, y1, zt, rf['ph'], P['parapet'], t=0.15)
            decks.append((a, c, y0, y1, zt))
        elif k == 'slab':
            of, ob, osd = rf['over']
            t = rf.get('t', 0.3)
            X0r, X1r = max(X0, x0 - osd), min(X1, x1 + osd)
            b.box(X0r, y0 - of, zt, X1r, y1 + ob, zt + t, P['accent'], skip=('top',))
            quad_up(b, X0r, y0 - of, X1r, y1 + ob, zt + t, P['deck'])
            b.parapet(X0r, X1r, y0 - of, y1 + ob, zt + t, 0.18, P['accent'], t=0.12)
            decks.append((min(a, c) - osd, max(a, c) + osd, y0 - of, y1 + ob, zt + t))
        elif k == 'hip':
            b.roof_hip(x0, x1, y0, y1, zt, rf['rise'], P['roof'], over=rf['over'], thick=0.12)

    if arch == 'over':
        uy0 = v['uy0']
        if v.get('split'):
            sp, roof2, zr2 = v['split'][:3]
            upper(si, sp, uy0, uyb, ZR, roof, True, wall)
            upper(sp, W - si, uy0, uyb, zr2, roof2, True, P[v['split'][3]] if len(v['split']) > 3 else wall)
        else:
            upper(si, W - si, uy0, uyb, ZR, roof, True, wall)
        yf = uy0
    elif arch == 'terrace':
        upper(cw, W - si, gh, uyb, ZR, roof, False, wall)
        upper(si, cw, gc, uyb, v['zrb'], v['roofb'], False, wall2)
        front_prog(v['upb'], si, cw, gc, Z1, v['zrb'])
        if gc - gh > 1.8:   # door from the room onto the terrace
            elem(b, CS, xs(cw), 'D', gh + 0.5, gh + 1.5, Z1, ZR, P)
        u0, u1 = xr(cw, W - si)
        slab(b, 'front', u0, u1, Z1 - 0.3, Z1, P['accent'], off=0.08, depth=0.08, wall=gh)   # floor band
        yf = gh
    else:
        upper(si, W - si, gc, uyb, ZR, roof, False, wall)
        yf = gc
        u0, u1 = xr(si + 0.005, W - si - 0.005)
        slab(b, 'front', u0, u1, Z1 - 0.2, Z1 + 0.02, P['accent'], off=0.08, depth=0.08, wall=gc)   # floor band
        if v.get('balc'):
            a, c, bd, st = v['balc']
            B(a, gc - bd, Z1 - 0.25, c, gc, Z1 + 0.05, P['accent'], skip=('top', 'back'))
            Q(a, gc - bd, c, gc, Z1 + 0.05, P['tile'])
            rail(b, xs(a + 0.05), gc - bd + 0.05, xs(c - 0.05), gc - bd + 0.05, Z1 + 0.05, st, P)
            for s in (a + 0.05, c - 0.05):
                rail(b, xs(s), gc - bd + 0.12, xs(s), gc, Z1 + 0.05, st, P)
    for a, c, items in v['up']:
        front_prog(items, a, c, yf, Z1, ZR)

    # rear single-storey part (kitchen / laundry): its dak is the ground-floor top, add a low parapet
    if ext > 0:
        B(si, yb - 0.15, Z1, W - si, yb, Z1 + 0.4, P['parapet'])
        B(si, uyb, Z1, si + 0.15, yb - 0.15, Z1 + 0.4, P['parapet'])
        B(W - si - 0.15, uyb, Z1, W - si, yb - 0.15, Z1 + 0.4, P['parapet'])
        decks.append((si, W - si, uyb, yb, Z1))

    # upper floor back and side windows
    ztop_back = ZR if arch != 'terrace' else min(ZR, v['zrb'])
    items = [('w', 1.2), ('h', 0.8), ('w', 1.2)] if W > 8 else [('w', 1.1), ('h', 0.7)]
    for kind, s0, s1 in place(items, si, W - si, 0.5):
        u0, u1 = xr(s0, s1)
        elem(b, 'back', uyb, kind, u0, u1, Z1, ztop_back, P)
    b.ac_unit('back', xs(W / 2 + 0.3), Z1 + 0.25, wall=uyb)
    ym = (yf + uyb) / 2
    if si >= 0.1:
        elem(b, HS, xs(W - si), 'w', ym - 0.6, ym + 0.6, Z1, ZR, P)
        if arch != 'terrace':
            elem(b, CS, xs(si), 'h', ym - 0.4, ym + 0.4, Z1, ZR, P)

    # cantilever box on the upper front
    if v.get('cbox'):
        a, c, dep, col = v['cbox']
        colr = P['wood'] if col == 'wood' else P[col]
        top = ZR if roof['kind'] == 'slab' else (ZR - 0.05 if roof['kind'] == 'hip' else ZR + 0.15)
        B(a, yf - dep, Z1 - 0.2, c, yf, top, colr, skip=('top',) if roof['kind'] == 'slab' else ())
        u0, u1 = xr(a + 0.3, c - 0.3)
        win(b, 'front', u0, u1, Z1 + 0.35, top - 0.35, P['frame'], P['glass'], wall=yf - dep, panes=3, transom=0.5)

    # bingkai: protruding frame around part of the upper facade
    if v.get('bingkai'):
        a, c, out = v['bingkai']
        if roof['kind'] == 'flat':
            ztop = ZR + roof['ph'] + 0.05
        elif roof['kind'] == 'shed':
            ztop = ZR + max(roof['f'], roof['b']) + roof.get('front_wall', 0.0) + 0.05
        else:
            ztop = ZR + 0.2
        zb = Z1 - 0.2
        fcol = P['accent']
        B(a, yf - out, ztop - 0.25, c, yf, ztop, fcol, skip=())
        B(a, yf - out, zb, a + 0.22, yf, ztop - 0.25, fcol, skip=())
        B(c - 0.22, yf - out, zb, c, yf, ztop - 0.25, fcol, skip=())
        B(a + 0.22, yf - out, zb, c - 0.22, yf, zb + 0.2, fcol, skip=('left', 'right'))

    # ---------------------------------------------------------------- props
    def at(s, y):
        """Prop position -> (x, y, deck z)."""
        s = s if s >= 0 else W - si + s
        y = y if y >= 0 else uyb + y
        z = 0.0
        for (a, c, y0, y1, zz) in decks:
            if a - 1e-6 <= s <= c + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                z = max(z, zz)
        return xs(s), y, z

    laundry = ['fabric_1', 'fabric_2', 'fabric_3', 'awning_white', 'sign_blue']
    rng.shuffle(laundry)
    for p in v.get('props', []):
        k = p[0]
        if k == 'toren':
            x, y, z = at(p[1], p[2])
            toren(b, x, y, z, p[3], stand=0.3 if z > Z1 + 0.5 else 0.35)
        elif k == 'ac':
            x, y, z = at(p[1], p[2])
            ac_box(b, x, y, z)
        elif k == 'solar':
            x, y, z = at(p[1], p[2])
            solar_heater(b, x, y, z)
        elif k == 'dish':
            x, y, z = at(p[1], p[2])
            dish(b, x, y, z)
        elif k == 'jemuran':      # ('jemuran', s0, s1, y)
            xa, y, z = at(p[1], p[3])
            xb, _, _ = at(p[2], p[3])
            h = 1.7 if z < Z1 + 0.5 else 1.25
            jemuran(b, xa, xb, y, z, laundry[:3 if abs(xb - xa) < 3 else 4], h=h)
        elif k == 'jemuran_back':
            x0_, x1_ = xr(si + 2.0, W - si - 0.4)
            jemuran(b, x0_, x1_, yb + (D - yb) * 0.6, 0.0, laundry[:3], h=1.8)
        elif k == 'patch':        # ('patch', s0, s1, y0, y1, colour): roof-terrace flooring
            xa, y0, z = at(p[1], p[3])
            xb, y1, _ = at(p[2], p[4])
            quad_up(b, xa, y0, xb, y1, z + 0.02, p[5])
        elif k == 'pots_row':     # ('pots_row', s0, s1, y, n)
            for i in range(p[4]):
                s = p[1] + (p[2] - p[1]) * i / max(1, p[4] - 1)
                x, y, z = at(s, p[3])
                pot(b, x, y, z, s=0.75)
        elif k == 'planter':      # ('planter', s0, s1, y): long hedge box along a parapet
            xa, y, z = at(p[1], p[3])
            xb, _, _ = at(p[2], p[3])
            b.box(min(xa, xb), y - 0.22, z, max(xa, xb), y + 0.22, z + 0.3, '#8c8a86')
            b.box(min(xa, xb) + 0.03, y - 0.19, z + 0.3, max(xa, xb) - 0.03, y + 0.19, z + 0.62, P['hedge'])
        elif k == 'pots':
            for i in range(p[1]):
                if arch == 'terrace':
                    pot(b, xs(si + 0.5 + i * 0.75), v['cy0'] + 0.5, Z1, s=0.8)
                else:
                    pot(b, xs(W - si - 0.5 - i * 0.7), terr0 + 0.4, 0.15, s=0.8)
    if v.get('back_tower'):
        # toren on a tall steel stand in the back yard
        toren(b, xs(W - si - 1.0), yb + (D - yb) / 2, 0.0, P['toren'], stand=min(ZR - 1.8, 3.8))

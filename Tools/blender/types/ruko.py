"""Ruko (rumah toko): THE Jakarta street building. One to three 4-5 m shop units side by side, 2-4 floors.

Ground floor: rolling doors (closed, half open or fully open on a dark shop with shelves and a counter),
a concrete canopy, a striped/zinc tenda or an overhanging upper floor on columns, and a big blank signboard
per unit. Upper floors: framed windows, ribbon windows with a sun hood, balconies, loggias, glass fronts,
AC condensers, banners and blank 'dijual' boards. Roof: flat dak with parapet (stepped or gable crowns),
mansard tile band or zinc sheds, with toren air, jemuran, stair houses and zinc canopies.
All units of one building share the architecture but differ in sign colour, shutter state, paint and props.
"""
import math

from common import PALETTE

TYPE = 'ruko'
ROLES = ['front']   # a shop row makes no sense as a back-yard filler

T0 = 0.15          # teras / shop floor level
PE = 0.22          # end pilaster width
PI = 0.15          # half width of a pilaster between two units
PD = 0.10          # pilasters stand this far proud of the facade

INT_BACK, INT_SIDE, INT_CEIL = '#3a302a', '#6b5f55', '#4a413b'
LOGO = {'sign_red': 'sign_yellow', 'sign_blue': 'sign_white', 'sign_green': 'sign_yellow', 'sign_yellow': 'sign_red',
        'sign_orange': 'sign_white', 'sign_white': 'sign_blue', 'sign_purple': 'sign_yellow'}
SIGN_DARK_TEXT = ('sign_yellow', 'sign_white', 'sign_orange', '#9fd8e8')
GOODS = ['#e25d4a', '#f2c230', '#3d8fd1', '#58b35c', '#f07c24', '#e8e4d8', '#c64f8f', '#8a5a3a']
# roof deck coatings (back zone, front terrace zone, terrace fraction). The game's warm sun + sky light brightens
# up-facing faces ~1.5x, so these are darker than they read in-game (lighter greys all came out beige).
GREY, GREY2, GREEN, BLUEG, RED, TILE, TILE2 = '#646a72', '#5a5e66', '#4f7a58', '#4d6078', '#7a4a40', '#b0704e', '#9a9488'
# darker tone of a roof colour for tile courses / ribs
DARK = {'roof_terracotta': '#8f3b1f', 'roof_blue': '#3c566f', 'roof_green': '#34563c', 'roof_red': '#7e2520',
        'roof_brown': '#5a2e1c', 'roof_zinc': '#6f777d', 'roof_grey': '#4a5058'}
# Facade paints: the game's warm light washes pastel paints out to one pale cream, so the walls use deeper,
# more saturated paints that keep their hue in-game (only ruko_02 stays white as the modern glass ruko).
PIPE = '#8d9296'
CLOTH = ['fabric_1', 'fabric_2', 'fabric_3', '#f3f1ea', '#6fb06a', '#e8872c', '#8f7fd0']


# ----------------------------------------------------------------------------------------- variants
def variants():
    V = [
        # 0: classic 2-storey pair, terracotta paint, signs standing on the canopy, nako ribbon windows,
        #    green glazed-tile mansard band
        dict(w=8.0, d=12.0, n=2, F=2, gh=3.9, fh=3.3, front='canopy', yF=1.6, sign='top',
             walls=['#d98a5f'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['ribbon'], shut=['open', 'closed'], shops=['toko', None], signs=['sign_yellow', 'sign_blue'],
             roof='mansard', roofcols=['roof_green'], ph=0.7, props=[['toren', 'ac'], ['room', 'jemuran1']]),
        # 1: single 3-storey unit, fascia sign, balcony + windows, stair house with toren, back annex
        dict(w=5.0, d=12.0, n=1, F=3, gh=3.8, fh=3.2, front='canopy', yF=1.5, sign='fascia',
             walls=['#6fb39a'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['balcony', 'win2'], shut=['half'], shops=['warung'], signs=['sign_yellow'],
             roof='flat', crown='gable', ph=0.9, roofcols=[(GREY2, TILE2, 0.5)], annex=2.6,
             props=[['room_t', 'jemuran1']], rail='rail_black'),
        # 2: modern 3-unit row, upper floors overhang the teras on columns, glass fronts, one unit for sale
        dict(w=13.5, d=13.0, n=3, F=3, gh=4.0, fh=3.3, front='cantilever', yF=2.3, yU=0.35, sign='wall',
             walls=['wall_white'], trim='#55504b', band='#55504b', frame='frame_black',
             floors=['glass', 'glass'], shut=['open', 'glass', 'closed'], shops=['makan', None, None],
             signs=['sign_orange', 'sign_blue', 'sign_white'], cells={(2, 1): 'dijual', (2, 2): 'shut'},
             roof='flat', crown='flat', ph=1.1, roofcols=[GREY, (BLUEG, GREY, 0.4), GREY],
             props=[['ac', 'toren_blk'], ['zinc', 'jemuran1'], ['dish', 'toren_blk', 'hatch']]),
        # 3: 2-unit 3-storey, each unit painted by its owner (coral / blue), loggias with railings, gable crowns
        dict(w=9.0, d=11.0, n=2, F=3, gh=3.8, fh=3.2, front='canopy', yF=1.6, sign='top',
             walls=['#d0707a', '#5b8fd6'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['loggia', 'win2'], shut=['half', 'closed'], shops=['toko', None],
             signs=['sign_green', 'sign_yellow'], roof='flat', crown='gable', ph=0.9,
             roofcols=[(GREY, TILE, 0.4), (RED, GREY, 0.45)], props=[['toren', 'jemuran'], ['toren_b', 'ac', 'hatch']]),
        # 4: narrow 4-storey unit, striped tenda, blade sign, banner floor, blue zinc shed roof behind a tall parapet
        dict(w=4.5, d=10.0, n=1, F=4, gh=3.4, fh=2.9, front='awning', yF=1.3, sign='blade',
             walls=['wall_yellow'], trim='wall_orange', band='trim_white', frame='window_frame',
             floors=['win2', 'banner', 'win2'], shut=['open'], shops=['warung'], signs=['sign_red'],
             awning=('awning_red', 'awning_stripe'), roof='shed', crown='flat', ph=1.2, roofcols=['roof_blue'],
             props=[['toren']]),
        # 5: 4-storey pair (blue / off-white) with fascia signs, sun hoods; a green zinc roof over one unit's terrace
        dict(w=10.0, d=13.0, n=2, F=4, gh=3.4, fh=2.9, front='canopy', yF=1.5, sign='fascia',
             walls=['#4a7fd0', '#e6e0cf'], trim='#3a6ea0', band='trim_white', frame='window_frame',
             floors=['ribbon', 'win2', 'win3'], shut=['closed', 'half'], shops=[None, 'bengkel'],
             signs=['sign_yellow', 'sign_green'], roof='flat', crown='step', ph=0.8,
             roofcols=[(GREY2, TILE, 0.5), (BLUEG, GREY, 0.3)], props=[['pots', 'jemuran1', 'hatch'], ['zincfull']]),
        # 6: old 3-unit 2-storey row (lime / mauve / peach), tenda awnings, teralis, zinc shed roofs behind gable crowns
        dict(w=12.0, d=11.0, n=3, F=2, gh=3.6, fh=3.2, front='awning', yF=1.3, sign='wall',
             walls=['#8fbf5a', '#9a88d8', '#e89070'], trim='trim_white', band='trim_white',
             frame='frame_brown', floors=['win2'], shut=['open', 'closed', 'half'],
             shops=['bengkel', None, 'toko'], signs=['sign_yellow', 'sign_purple', 'sign_red'],
             cells={(1, 1): 'walled'}, teralis=True, awning=[('awning_blue', 'awning_stripe'), ('roof_zinc', None),
                                                               ('awning_green', 'awning_stripe')],
             roof='shed', crown='gable', ph=1.3, roofcols=['roof_zinc', 'roof_blue', '#a86a4a'], props=[[], ['toren'], []]),
        # 7: wide single unit with shutter + house door, balcony, terracotta mansard
        dict(w=6.0, d=11.0, n=1, F=2, gh=3.8, fh=3.3, front='canopy', yF=1.5, sign='top',
             walls=['wall_orange'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['balcony'], shut=['open'], shops=['makan'], signs=['sign_green'],
             openings=[[(0.0, 0.74, None), (0.8, 1.0, 'door')]],
             roof='mansard', roofcols=['roof_terracotta'], ph=0.6, props=[['toren_blk', 'jemuran1']],
             rail='rail_black'),
        # 8: teal 3-storey pair overhanging on columns, blue-grey mansard with fire walls
        dict(w=8.5, d=12.0, n=2, F=3, gh=3.7, fh=3.2, front='cantilever', yF=2.0, yU=0.4, sign='wall',
             walls=['#4c9ec0'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['win3', 'win2'], shut=['closed', 'open'], shops=[None, 'toko'],
             signs=['sign_red', 'sign_yellow'], roof='mansard', roofcols=['roof_blue'], ph=0.6,
             props=[['toren'], ['ac', 'jemuran1']]),
        # 9: wide classic 3-unit 3-storey block in mustard, stair houses, jemuran, different roof coatings
        dict(w=14.0, d=14.0, n=3, F=3, gh=3.8, fh=3.2, front='canopy', yF=1.6, sign='top',
             walls=['#e2b64e'], trim='wall_green', band='trim_white', frame='frame_brown',
             floors=['win2', 'ribbon'], shut=['open', 'half', 'closed'], shops=['warung', 'makan', None],
             signs=['sign_blue', 'sign_orange', 'sign_green'], cells={(1, 1): 'banner'},
             roof='flat', crown='flat', ph=1.25, roofcols=[(GREY, TILE2, 0.35), (GREEN, TILE, 0.5), (RED, GREY2, 0.4)],
             props=[['room_t'], ['jemuran1', 'hatch'], ['toren', 'ac']]),
        # 10: small old rose single unit, blue zinc awning, bricked-up window with dijual board, tile roof + dish
        dict(w=5.5, d=10.0, n=1, F=2, gh=3.6, fh=3.1, front='awning', yF=1.3, sign='wall',
             walls=['#b86a8a'], trim='trim_white', band='trim_white', frame='frame_brown',
             floors=['dijual'], shut=['closed'], shops=[None], signs=['sign_white'],
             openings=[[(0.0, 0.76, None), (0.82, 1.0, 'door')]], awning=[('#5f8fb0', None)],
             roof='pitched', roofcols=['roof_terracotta'], annex=2.2, annex_props=['toren', 'ac'], dish=True),
        # 11: purple / sea-green 2-storey pair on columns, a semi-permanent zinc-roofed room added on one roof
        dict(w=9.5, d=10.0, n=2, F=2, gh=3.9, fh=3.3, front='cantilever', yF=2.0, yU=0.4, sign='wall',
             walls=['#7a6ad0', '#62a7a0'], trim='trim_white', band='trim_white', frame='window_frame',
             floors=['win3'], shut=['glass', 'open'], shops=[None, 'warung'], signs=['sign_yellow', 'sign_orange'],
             cells={(1, 1): 'banner'}, roof='flat', crown='flat', ph=0.9, roofcols=[GREY, (BLUEG, GREY, 0.4)],
             props=[['addon'], ['toren', 'jemuran1']]),
    ]
    for v in V:
        v['d'] = float(v['d'])
    return V


# ----------------------------------------------------------------------------------------- low level
def qf(b, y, x0, x1, z0, z1, c):   # quad facing -y (front)
    b.face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], c)


def qb(b, y, x0, x1, z0, z1, c):   # quad facing +y (back)
    b.face([(x1, y, z0), (x0, y, z0), (x0, y, z1), (x1, y, z1)], c)


def qu(b, z, x0, x1, y0, y1, c):   # quad facing up
    b.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], c)


def qd(b, z, x0, x1, y0, y1, c):   # quad facing down
    b.face([(x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z)], c)


def ql(b, x, y0, y1, z0, z1, c):   # quad facing -x
    b.face([(x, y1, z0), (x, y0, z0), (x, y0, z1), (x, y1, z1)], c)


def qr(b, x, y0, y1, z0, z1, c):   # quad facing +x
    b.face([(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)], c)


def prism_x(b, x0, x1, prof, cols, caps=(None, None)):
    """Solid extruded along x. prof: (y, z) points clockwise in the (y, z) plane (so the x0 cap faces -x).
    cols[i] colours the face along prof[i] -> prof[i+1] (None = skip); caps = (x0 colour, x1 colour)."""
    m = len(prof)
    for i in range(m):
        c = cols[i]
        if c is None:
            continue
        (ya, za), (yb, zb) = prof[i], prof[(i + 1) % m]
        b.face([(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)], c)
    if caps[0]:
        b.face([(x0, y, z) for (y, z) in prof], caps[0])
    if caps[1]:
        b.face([(x1, y, z) for (y, z) in prof[::-1]], caps[1])


def strip_x(b, x0, x1, p, q, c, off=0.012):
    """Flat stripe lying on the prism_x face p -> q (same winding rules), lifted `off` along its normal."""
    dy, dz = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dy, dz)
    ny, nz = -dz / L * off, dy / L * off
    b.face([(x0, p[0] + ny, p[1] + nz), (x1, p[0] + ny, p[1] + nz), (x1, q[0] + ny, q[1] + nz), (x0, q[0] + ny, q[1] + nz)], c)


def prism_y(b, y0, y1, prof, cols, caps=(None, None)):
    """Solid extruded along y. prof: (x, z) points counter-clockwise in (x, z) (so the y0 cap faces -y)."""
    m = len(prof)
    for i in range(m):
        c = cols[i]
        if c is None:
            continue
        (xa, za), (xb, zb) = prof[i], prof[(i + 1) % m]
        b.face([(xa, y1, za), (xb, y1, zb), (xb, y0, zb), (xa, y0, za)], c)
    if caps[0]:
        b.face([(x, y0, z) for (x, z) in prof], caps[0])
    if caps[1]:
        b.face([(x, y1, z) for (x, z) in prof[::-1]], caps[1])


def front_wall(b, y, x0, x1, z0, z1, holes, col):
    """Front-facing wall rectangle with rectangular holes (holes must not overlap in x)."""
    cur = x0
    for (hx0, hx1, hz0, hz1) in sorted(holes):
        if hx0 > cur + 1e-4:
            qf(b, y, cur, hx0, z0, z1, col)
        if hz0 > z0 + 1e-4:
            qf(b, y, hx0, hx1, z0, hz0, col)
        if hz1 < z1 - 1e-4:
            qf(b, y, hx0, hx1, hz1, z1, col)
        cur = hx1
    if cur < x1 - 1e-4:
        qf(b, y, cur, x1, z0, z1, col)


def recess(b, y, x0, x1, z0, z1, dp, back, side, ceil, floor):
    """Inside of an opening in a front wall at y: back wall, jambs, ceiling, floor (all facing the viewer)."""
    qf(b, y + dp, x0, x1, z0, z1, back)
    qr(b, x0, y, y + dp, z0, z1, side)
    ql(b, x1, y, y + dp, z0, z1, side)
    qd(b, z1, x0, x1, y, y + dp, ceil)
    if floor:
        qu(b, z0, x0, x1, y, y + dp, floor)


def shade(c, f):
    """Palette key or hex colour scaled by f (f < 1 darkens)."""
    h = PALETTE.get(c, c).lstrip('#')
    return '#' + ''.join('%02x' % max(0, min(255, int(round(int(h[i:i + 2], 16) * f)))) for i in (0, 2, 4))


def txt_col(c):
    return 'sign_text' if c in SIGN_DARK_TEXT else 'sign_white'


def board(b, y, x0, x1, z0, z1, col, bars=2, depth=0.1, logo=False, skip=('back',)):
    """Blank sign board on a front wall at y (lettering = bars, never text). Free-standing boards (on a canopy)
    pass skip=() / ('bottom',) so they are closed at the back."""
    b.box(x0, y - depth, z0, x1, y, z1, col, skip=skip)
    t, w, h, yy = txt_col(col), x1 - x0, z1 - z0, y - depth - 0.012
    a = x0 + w * 0.14
    if logo:   # plain square mark in an accent colour (no brand, no letters)
        sq = min(h * 0.5, w * 0.16)
        qf(b, yy, x0 + w * 0.06, x0 + w * 0.06 + sq, z0 + h / 2 - sq / 2, z0 + h / 2 + sq / 2, LOGO.get(col, 'sign_white'))
        a = x0 + w * 0.12 + sq
    qf(b, yy, a, x1 - w * 0.1, z0 + h * 0.54, z0 + h * 0.76, t)
    if bars >= 2:
        qf(b, yy, a + (x1 - a) * 0.12, x1 - w * 0.2, z0 + h * 0.24, z0 + h * 0.4, t)


def fwin(b, y, xc, z0, w, h, frame, glass='glass', panes=2, sill=None, transom=False, bars=None):
    """Framed window on a front wall at y."""
    t = 0.08
    b.box(xc - w / 2 - t, y - 0.07, z0 - t, xc + w / 2 + t, y, z0 + h + t, frame, skip=('back',))
    yg = y - 0.08
    qf(b, yg, xc - w / 2, xc + w / 2, z0, z0 + h, glass)
    for i in range(1, panes):
        u = xc - w / 2 + w * i / panes
        qf(b, yg - 0.01, u - 0.035, u + 0.035, z0, z0 + h, frame)
    if transom:
        qf(b, yg - 0.02, xc - w / 2, xc + w / 2, z0 + h * 0.72, z0 + h * 0.72 + 0.06, frame)
    if bars:
        k = max(3, int(w / 0.16))
        for i in range(1, k):
            u = xc - w / 2 + w * i / k
            qf(b, yg - 0.035, u - 0.012, u + 0.012, z0, z0 + h, bars)
    if sill:
        b.box(xc - w / 2 - 0.14, y - 0.15, z0 - t - 0.07, xc + w / 2 + 0.14, y, z0 - t, sill, skip=('back',))


def bwin(b, y, xc, z0, w, h, frame, glass='glass', bars=None):
    """Framed window on a back wall at y (protrudes +y)."""
    t = 0.07
    b.box(xc - w / 2 - t, y, z0 - t, xc + w / 2 + t, y + 0.06, z0 + h + t, frame, skip=('front',))
    qb(b, y + 0.07, xc - w / 2, xc + w / 2, z0, z0 + h, glass)
    if bars:
        for i in range(1, 4):
            u = xc - w / 2 + w * i / 4
            qb(b, y + 0.08, u - 0.012, u + 0.012, z0, z0 + h, bars)


INFILL, MORTAR = '#b5ae9f', '#857c6c'


def bricked(b, y, xc, z0, w, h, frame, sill):
    """Window bricked up with unpainted blocks: frame and sill stay, infill with mortar courses."""
    fwin(b, y, xc, z0, w, h, frame, glass=INFILL, panes=1, sill=sill)
    for i in range(1, 5):
        z = z0 + h * i / 5
        qf(b, y - 0.09, xc - w / 2, xc + w / 2, z - 0.0125, z + 0.0125, MORTAR)


def krepyak(b, y, xc, z0, w, h, frame, col, sill):
    """Window closed with two wooden louvred shutters (krepyak)."""
    fwin(b, y, xc, z0, w, h, frame, glass=col, panes=2, sill=sill)
    dk = shade(col, 0.62)
    for (xa, xb) in ((xc - w / 2 + 0.04, xc - 0.05), (xc + 0.05, xc + w / 2 - 0.04)):
        z = z0 + 0.15
        while z < z0 + h - 0.08:
            qf(b, y - 0.09, xa, xb, z - 0.014, z + 0.014, dk)
            z += 0.15


def fac(b, y, xc, z0):
    """AC condenser hanging on a front wall."""
    b.box(xc - 0.4, y - 0.3, z0, xc + 0.4, y, z0 + 0.55, 'ac_white', skip=('back',))
    qf(b, y - 0.312, xc - 0.3, xc + 0.06, z0 + 0.1, z0 + 0.45, 'metal')


def bac(b, y, xc, z0):
    """AC condenser hanging on a back wall."""
    b.box(xc - 0.4, y, z0, xc + 0.4, y + 0.3, z0 + 0.55, 'ac_white', skip=('front',))
    qb(b, y + 0.312, xc - 0.3, xc + 0.06, z0 + 0.1, z0 + 0.45, 'metal')


def frail(b, y, x0, x1, z0, h, col, gap=0.24):
    """Balcony railing whose front face is at y: top rail, end posts, bars."""
    b.box(x0, y, z0 + h - 0.06, x1, y + 0.05, z0 + h, col, skip=())
    for x in (x0, x1 - 0.05):
        b.box(x, y, z0, x + 0.05, y + 0.05, z0 + h - 0.06, col, skip=('bottom', 'top'))
    k = max(2, int((x1 - x0) / gap))
    for i in range(1, k):
        u = x0 + (x1 - x0) * i / k
        qf(b, y + 0.02, u - 0.012, u + 0.012, z0, z0 + h - 0.06, col)


# ----------------------------------------------------------------------------------------- roof props
def toren(b, cx, cy, z0, col, stand=0.8, r=0.5, h=1.05):
    """Toren air on a steel stand (stand > 0) or straight on the slab."""
    if stand > 0:
        for dx in (-0.36, 0.36):
            for dy in (-0.36, 0.36):
                b.box(cx + dx - 0.04, cy + dy - 0.04, z0, cx + dx + 0.04, cy + dy + 0.04, z0 + stand - 0.06, 'metal',
                      skip=('bottom', 'top'))
        b.box(cx - 0.46, cy - 0.46, z0 + stand - 0.06, cx + 0.46, cy + 0.46, z0 + stand, 'metal', skip=())
    b.cyl(cx, cy, z0 + stand, z0 + stand + h, r, col, seg=8)


def toren_block(b, cx, cy, z0, col, base=0.45, h=1.0):
    b.box(cx - 0.5, cy - 0.5, z0, cx + 0.5, cy + 0.5, z0 + base, 'concrete')
    toren(b, cx, cy, z0 + base, col, stand=0, h=h)


def roof_ac(b, x, y, z0):
    b.box(x - 0.4, y - 0.28, z0, x + 0.4, y + 0.28, z0 + 0.6, 'ac_white')
    qf(b, y - 0.292, x - 0.3, x + 0.06, z0 + 0.12, z0 + 0.48, 'metal')


def pot(b, x, y, z0):
    b.box(x - 0.2, y - 0.2, z0, x + 0.2, y + 0.2, z0 + 0.35, 'pot')
    b.box(x - 0.27, y - 0.27, z0 + 0.35, x + 0.27, y + 0.27, z0 + 0.75, 'plant')


def jemuran(b, x0, x1, yc, z0, rng, two=True):
    """Clothes-drying lines between two T posts, clothes hanging both ways (visible front and back)."""
    hg = 1.65
    for x in (x0, x1):
        b.box(x - 0.035, yc - 0.035, z0, x + 0.035, yc + 0.035, z0 + hg - (0.06 if two else 0), 'metal')
        if two:
            b.box(x - 0.03, yc - 0.42, z0 + hg - 0.06, x + 0.03, yc + 0.42, z0 + hg, 'metal', skip=())
    for ly in ((yc - 0.38, yc + 0.38) if two else (yc,)):
        if not two:
            ly = yc - 0.05
        b.box(x0, ly - 0.012, z0 + hg - 0.04, x1, ly + 0.012, z0 + hg - 0.016, 'rail_white', skip=('bottom',))
        x = x0 + 0.12 + rng.uniform(0, 0.2)
        cnt = 0
        while x < x1 - 0.45 and cnt < 4:
            w, hh = rng.uniform(0.35, 0.6), rng.uniform(0.45, 0.85)
            c = rng.choice(CLOTH)
            zt = z0 + hg - 0.04
            qf(b, ly - 0.004, x, x + w, zt - hh, zt, c)
            qb(b, ly + 0.004, x, x + w, zt - hh, zt, c)
            x += w + rng.uniform(0.1, 0.35)
            cnt += 1


def zinc_canopy(b, x0, x1, y0, y1, z0, hf, hb, col):
    """Light steel canopy with a zinc sheet roof on four posts (roof terrace)."""
    for (x, y, hh) in ((x0 + 0.06, y0 + 0.06, hf), (x1 - 0.06, y0 + 0.06, hf), (x0 + 0.06, y1 - 0.06, hb),
                       (x1 - 0.06, y1 - 0.06, hb)):
        b.box(x - 0.04, y - 0.04, z0, x + 0.04, y + 0.04, z0 + hh, 'metal', skip=('bottom', 'top'))
    top = [(x0, y0, z0 + hf + 0.05), (x1, y0, z0 + hf + 0.05), (x1, y1, z0 + hb + 0.05), (x0, y1, z0 + hb + 0.05)]
    bot = [(p[0], p[1], p[2] - 0.05) for p in top]
    b._slab(top, bot, col)
    # corrugation ribs (front-to-back stripes)
    k = max(2, int((x1 - x0) / 0.7))
    for i in range(1, k):
        x = x0 + (x1 - x0) * i / k
        b.face([(x - 0.04, y0, z0 + hf + 0.062), (x + 0.04, y0, z0 + hf + 0.062), (x + 0.04, y1, z0 + hb + 0.062),
                (x - 0.04, y1, z0 + hb + 0.062)], 'metal')


def dish(b, x, y, z0, side=1):
    """Small satellite dish on a short pole. Near the equator dishes look steeply up, so the disc faces 65 deg up
    and turned to the side (side=+1 right, -1 left): from the front and the back game camera it reads as an
    oval, never edge-on as a bar on a pole."""
    el, az = math.radians(65), math.radians(-30 if side > 0 else 210)
    n = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
    u1 = (-math.sin(az), math.cos(az), 0.0)
    u2 = (n[1] * u1[2] - n[2] * u1[1], n[2] * u1[0] - n[0] * u1[2], n[0] * u1[1] - n[1] * u1[0])
    ctr = (x, y, z0 + 0.95)
    b.box(x - 0.03, y - 0.03, z0, x + 0.03, y + 0.03, ctr[2] - 0.01, 'metal')
    pts = []
    for i in range(8):
        a = 2 * math.pi * i / 8
        ca, sa = math.cos(a) * 0.4, math.sin(a) * 0.4
        pts.append(tuple(ctr[k] + ca * u1[k] + sa * u2[k] for k in range(3)))
    b.face(pts, 'ac_white')
    b.face(pts[::-1], 'metal')
    # LNB feed arm from the low rim to the focus + LNB head: asymmetric, unmistakably a dish from every side
    r0 = tuple(ctr[k] - 0.4 * u2[k] for k in range(3))
    f = tuple(ctr[k] + 0.34 * n[k] for k in range(3))
    d = [f[k] - r0[k] for k in range(3)]
    L = math.sqrt(sum(c * c for c in d))
    d = [c / L for c in d]
    h = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = (h[1] * d[2] - h[2] * d[1], h[2] * d[0] - h[0] * d[2], h[0] * d[1] - h[1] * d[0])
    m = math.sqrt(sum(c * c for c in e1))
    e1 = tuple(0.02 * c / m for c in e1)
    e2 = (d[1] * e1[2] - d[2] * e1[1], d[2] * e1[0] - d[0] * e1[2], d[0] * e1[1] - d[1] * e1[0])   # |e2| = |e1|
    cs = [e1, e2, tuple(-c for c in e1), tuple(-c for c in e2)]
    for k in range(4):
        a, c = cs[k], cs[(k + 1) % 4]
        b.face([tuple(r0[i] + a[i] for i in range(3)), tuple(r0[i] + c[i] for i in range(3)),
                tuple(f[i] + c[i] for i in range(3)), tuple(f[i] + a[i] for i in range(3))], 'metal')
    b.box(f[0] - 0.06, f[1] - 0.06, f[2] - 0.05, f[0] + 0.06, f[1] + 0.06, f[2] + 0.07, 'trim_dark', skip=())


def stair_room(b, x0, x1, y0, y1, z0, h, wall, slab, frame):
    """Roof stair house: box, overhanging slab roof, door on the front, small back window."""
    b.box(x0, y0, z0, x1, y1, z0 + h, wall, skip=('bottom', 'top'))
    b.box(x0 - 0.08, y0 - 0.25, z0 + h, x1 + 0.08, y1 + 0.08, z0 + h + 0.14, slab, skip=())
    dx = x0 + 0.65
    b.box(dx - 0.5, y0 - 0.05, z0, dx + 0.5, y0, z0 + 2.08, frame, skip=('back', 'bottom'))
    qf(b, y0 - 0.06, dx - 0.42, dx + 0.42, z0, z0 + 2.0, 'door_dark')
    bwin(b, y1, (x0 + x1) / 2, z0 + 1.3, 0.6, 0.5, frame)


# ----------------------------------------------------------------------------------------- building
def build(b, v, rng):
    W, D = b.W, b.D
    n, F, gh, fh = v['n'], v['F'], v['gh'], v['fh']
    style, yF = v['front'], v['yF']
    yU = v.get('yU', yF)
    yGB = D - 0.45                           # ground-floor back wall (room for AC units / pipes behind it)
    yUB = yGB - v.get('annex', 0.0)          # upper-floor back wall
    Hr = gh + (F - 1) * fh                   # main roof slab level
    ph = v.get('ph', 1.0)
    roof = v['roof']
    uw = W / n
    trim, band, frame = v['trim'], v['band'], v['frame']
    zo = gh - 0.5 if style == 'cantilever' else min(3.0, gh - 0.75)   # shop opening top
    zc = zo + 0.3                                                     # canopy slab bottom

    U = []
    for i in range(n):
        ux0, ux1 = -W / 2 + i * uw, -W / 2 + (i + 1) * uw
        u = dict(i=i, x0=ux0, x1=ux1, cx0=ux0 + (PE if i == 0 else PI), cx1=ux1 - (PE if i == n - 1 else PI),
                 wall=v['walls'][i % len(v['walls'])], sign=v['signs'][i % len(v['signs'])],
                 shut=v['shut'][i % len(v['shut'])], shop=v['shops'][i % len(v['shops'])],
                 roofcol=v['roofcols'][i % len(v['roofcols'])],
                 props=v.get('props', [[]] * n)[i] if v.get('props') else [])
        u['cc'] = (u['cx0'] + u['cx1']) / 2
        u['cw'] = u['cx1'] - u['cx0']
        U.append(u)
    shutcols = ['shutter', 'shutter', '#5d86b0', 'shutter_dark', '#6f9f78']
    for u in U:
        u['shutcol'] = shutcols[rng.randrange(len(shutcols))]

    # ---------------------------------------------------------------- teras, body shell
    b.box(-W / 2, 0, 0, W / 2, yF, T0, 'concrete', skip=('bottom', 'back'))
    wl, wr = U[0]['wall'], U[-1]['wall']
    ql(b, -W / 2, yF, yGB, 0, gh, wl)
    qr(b, W / 2, yF, yGB, 0, gh, wr)
    zs = Hr - 0.25 if roof == 'pitched' else Hr
    ql(b, -W / 2, yU, yUB, gh, zs, wl)
    qr(b, W / 2, yU, yUB, gh, zs, wr)
    for u in U:
        if yUB < yGB - 1e-3:
            qb(b, yGB, u['x0'], u['x1'], 0, gh, u['wall'])
            qb(b, yUB, u['x0'], u['x1'], gh, zs, u['wall'])
        else:
            qb(b, yGB, u['x0'], u['x1'], 0, zs, u['wall'])
    if yU < yF - 1e-3:
        qd(b, gh, -W / 2, W / 2, yU, yF, 'trim_white' if trim != 'trim_white' else 'concrete')
    if yUB < yGB - 1e-3:   # one-storey back annex (dapur) with a flat slab and a low parapet
        qu(b, gh, -W / 2, W / 2, yUB, yGB, 'concrete')
        b.box(-W / 2, yGB - 0.12, gh, W / 2, yGB, gh + 0.4, wl)
        b.box(-W / 2, yUB, gh, -W / 2 + 0.12, yGB - 0.12, gh + 0.4, wl, skip=('bottom', 'back'))
        b.box(W / 2 - 0.12, yUB, gh, W / 2, yGB - 0.12, gh + 0.4, wr, skip=('bottom', 'back'))

    # ---------------------------------------------------------------- ground floor front
    for u in U:
        ops = (v.get('openings') or [None] * n)[u['i']] or [(0.0, 1.0, None)]
        holes, specs = [], []
        for (f0, f1, kind) in ops:
            ox0 = u['cx0'] + f0 * u['cw'] + (0.12 if f0 > 0 else 0)
            ox1 = u['cx0'] + f1 * u['cw'] - (0.12 if f1 < 1 else 0)
            kind = kind or u['shut']
            top = T0 + 2.15 if kind == 'door' else zo
            holes.append((ox0, ox1, T0, top))
            specs.append((ox0, ox1, top, kind))
        front_wall(b, yF, u['x0'], u['x1'], T0, gh, holes, u['wall'])
        for (ox0, ox1, top, kind) in specs:
            shop_opening(b, v, u, yF, ox0, ox1, top, kind, yGB, rng)

    # ---------------------------------------------------------------- front style: canopy / awning / columns
    if style == 'canopy':
        cy0 = 0.26 if v['sign'] == 'fascia' else 0.12
        b.box(-W / 2 + 0.01, cy0, zc, W / 2 - 0.01, yF, zc + 0.15, 'concrete', skip=('back',))
        if v['sign'] == 'fascia':
            for u in U:
                x0 = u['x0'] + (0.02 if u['i'] == 0 else 0.03)
                x1 = u['x1'] - (0.02 if u['i'] == n - 1 else 0.03)
                board(b, cy0, x0, x1, zc - 0.3, zc + 0.5, u['sign'], depth=0.16, logo=u['i'] % 2 == 0, skip=())
        else:
            for u in U:
                sh = 1.0 + 0.12 * ((u['i'] + 1) % 2)
                board(b, cy0 + 0.12, u['x0'] + 0.12, u['x1'] - 0.12, zc + 0.15, zc + 0.15 + sh, u['sign'],
                      depth=0.12, logo=u['i'] % 2 == 1, skip=('bottom',))
    elif style == 'awning':
        aw = v.get('awning', [('awning_red', 'awning_stripe')])
        if isinstance(aw, tuple):
            aw = [aw]
        for u in U:
            col, stripe = aw[u['i'] % len(aw)]
            awning(b, u['cx0'] + 0.02, u['cx1'] - 0.02, yF, zo + 0.45, min(1.1, yF - 0.2), 0.42, col, stripe)
    elif style == 'cantilever':
        # columns under the overhang, same width as the pilasters and flush with their front, so each post
        # runs straight from the teras to the roof
        for k in range(n + 1):
            xb = -W / 2 + k * uw
            x0, x1 = (xb, xb + PE) if k == 0 else ((xb - PE, xb) if k == n else (xb - PI, xb + PI))
            b.box(x0, yU - PD, T0, x1, yU + 0.26, gh, trim, skip=('bottom', 'top'))

    # ---------------------------------------------------------------- upper floors
    lowsign = v['sign'] in ('wall', 'blade') and style != 'canopy'
    for u in U:
        sts = {k: v.get('cells', {}).get((u['i'], k), v['floors'][k - 1]) for k in range(1, F)}
        if 'loggia' not in sts.values():
            qf(b, yU, u['x0'], u['x1'], gh, Hr, u['wall'])
        for k in range(1, F):
            zf = gh + (k - 1) * fh
            if 'loggia' in sts.values() and sts[k] != 'loggia':
                qf(b, yU, u['x0'], u['x1'], zf, zf + fh, u['wall'])
            upper_cell(b, v, u, k, zf, zf + fh, sts[k], yU, lowsign and k == 1, rng)

    # floor bands and pilasters
    for k in range(1, F):
        z = gh + (k - 1) * fh
        b.box(-W / 2 + 0.02, yU - 0.06, z - 0.12, W / 2 - 0.02, yU, z + 0.12, band, skip=('back',))
    top_pil = {'mansard': Hr - 0.35, 'pitched': Hr - 0.25}.get(roof, Hr + ph + 0.2)
    z_pil = gh if style == 'cantilever' else T0
    for k in range(n + 1):
        xb = -W / 2 + k * uw
        x0, x1 = (xb, xb + PE) if k == 0 else ((xb - PE, xb) if k == n else (xb - PI, xb + PI))
        # on flat / shed roofs the pilaster rises above the coping, so it is closed at the back there
        b.box(x0, yU - PD, z_pil, x1, yU, top_pil, trim,
              skip=('back', 'top', 'bottom') if roof in ('mansard', 'pitched') else ('bottom',))

    # signs mounted on the upper facade
    if lowsign:
        for u in U:
            board(b, yU, u['cx0'] + 0.08, u['cx1'] - 0.08, gh + 0.2, gh + 1.0, u['sign'], depth=0.14,
                  logo=u['i'] % 2 == 0)
    if v['sign'] == 'blade':
        xb = W / 2 - PE / 2
        c = U[-1]['sign']
        c2 = 'sign_yellow' if c != 'sign_yellow' else 'sign_blue'
        y0, y1, z0, z1 = yU - 1.0, yU - PD, gh + 1.25, gh + 3.4
        b.box(xb - 0.06, y0, z0, xb + 0.06, y1, z1, c2, skip=('back',))
        for i in range(3):
            za = z0 + 0.25 + i * 0.62
            ql(b, xb - 0.072, y0 + 0.15, y1 - 0.15, za, za + 0.4, txt_col(c2))
            qr(b, xb + 0.072, y0 + 0.15, y1 - 0.15, za, za + 0.4, txt_col(c2))

    # ---------------------------------------------------------------- back facade
    for u in U:
        xc = u['cc'] + (0.5 if u['i'] % 2 else -0.5) * (u['cw'] * 0.25)
        dx = u['x0'] + 0.9 if u['i'] % 2 == 0 else u['x1'] - 0.9
        # back door + kitchen window
        b.box(dx - 0.5, yGB, 0, dx + 0.5, yGB + 0.06, 2.2, frame, skip=('front', 'bottom'))
        qb(b, yGB + 0.07, dx - 0.42, dx + 0.42, 0, 2.12, 'door_dark')
        wx = u['cc'] + (0.9 if u['i'] % 2 == 0 else -0.9)
        bwin(b, yGB, wx, 1.35, 0.8, 0.7, frame, bars='rail_black')
        for k in range(1, F):
            zf = gh + (k - 1) * fh
            bwin(b, yUB, xc, zf + 1.1, 1.0, 1.1, frame, bars='rail_black' if (k == 1 and n < 3) else None)
            if (u['i'] + k) % 2 == 0 and u['cw'] > 3.0:
                bac(b, yUB, xc + (1.25 if xc < u['cc'] else -1.25), zf + 0.35)
        # rain pipe at the right edge of every unit (one per unit boundary plus one at the right end)
        px = u['x1'] - 0.3
        zp0 = 0 if yUB >= yGB - 1e-3 else gh
        if roof in ('pitched', 'shed'):
            # pipe stops under the eave and bends out into the gutter along the eave
            yg, zg0, zg1 = ((yUB + 0.35, Hr - 0.44, Hr - 0.28) if roof == 'pitched' else (yUB + 0.3, Hr - 0.22, Hr - 0.06))
            b.box(px - 0.06, yUB, zp0, px + 0.06, yUB + 0.12, zg0 + 0.08, PIPE, skip=('bottom', 'front', 'top'))
            b.box(px - 0.05, yUB, zg0, px + 0.05, yg + 0.05, zg1, PIPE, skip=('front',))
        else:
            b.box(px - 0.06, yUB, zp0, px + 0.06, yUB + 0.12, Hr + 0.2, PIPE, skip=('bottom', 'front'))
    if roof == 'pitched':      # gutter hung on the back eave fascia
        b.box(-W / 2 + 0.02, yUB + 0.35, Hr - 0.3, W / 2 - 0.02, yUB + 0.45, Hr - 0.14, PIPE, skip=('front',))
    elif roof == 'shed':
        b.box(-W / 2 + 0.02, yUB + 0.3, Hr - 0.1, W / 2 - 0.02, yUB + 0.4, Hr + 0.04, PIPE, skip=('front',))

    # ---------------------------------------------------------------- roof
    if roof == 'flat':
        flat_roof(b, v, U, yU, yUB, Hr, ph, rng)
    elif roof == 'shed':
        shed_roof(b, v, U, yU, yUB, Hr, ph)
    elif roof == 'mansard':
        mansard_roof(b, v, U, yU, yUB, Hr, ph, rng)
    elif roof == 'pitched':
        pitched_roof(b, v, U, yU, yUB, Hr)
    # props on the back annex slab
    for p in v.get('annex_props', []):
        ya = (yUB + yGB) / 2
        if p == 'toren':
            toren(b, W / 2 - 0.9, ya, gh, 'tank_orange', stand=0.8)
        elif p == 'ac':
            roof_ac(b, -W / 2 + 1.0, ya, gh)


def awning(b, x0, x1, yw, z, out, drop, col, stripe):
    """Sloped tenda / zinc awning hanging off a front wall at yw."""
    t = 0.05
    A, B, C, Dd = (yw, z), (yw - out, z - drop), (yw - out, z - drop + t), (yw, z + t)
    prism_x(b, x0, x1, [A, B, C, Dd], [col, col, col, None], caps=(col, col))
    b.box(x0 + 0.01, yw - out - 0.03, z - drop - 0.26, x1 - 0.01, yw - out + 0.01, z - drop + t, col, skip=())
    if stripe:
        k = max(3, int(round((x1 - x0) / 0.45)))
        for i in range(1, k, 2):
            a, c = x0 + (x1 - x0) * i / k, x0 + (x1 - x0) * (i + 1) / k
            strip_x(b, a, c, C, Dd, stripe)
            qf(b, yw - out - 0.042, a, c, z - drop - 0.26, z - drop + t, stripe)
    else:   # corrugated zinc: ribs down the slope and on the edge board, darker drip edge
        rib = DARK.get(col, shade(col, 0.62))
        k = max(3, int(round((x1 - x0) / 0.25)))
        for i in range(1, k):
            x = x0 + (x1 - x0) * i / k
            strip_x(b, x - 0.03, x + 0.03, C, Dd, rib)
            qf(b, yw - out - 0.042, x - 0.015, x + 0.015, z - drop - 0.19, z - drop + t, rib)
        qf(b, yw - out - 0.042, x0 + 0.01, x1 - 0.01, z - drop - 0.26, z - drop - 0.19, '#8e959b' if col == 'roof_zinc' else rib)
    # two slim brackets from the wall to the valance
    for x in (x0 + 0.1, x1 - 0.14):
        b.box(x, yw - out + 0.01, z - drop - 0.02, x + 0.04, yw, z - drop + 0.02, 'metal', skip=('back',))


def shop_opening(b, v, u, yF, ox0, ox1, top, kind, yGB, rng):
    """Recessed shop opening: closed / half / open rolling door, glass shop front or house door."""
    sc = u['shutcol']
    if kind == 'door':
        recess(b, yF, ox0, ox1, T0, top, 0.12, 'door_wood', u['wall'], u['wall'], 'tile_floor')
        qf(b, yF + 0.11, ox0 + 0.08, ox1 - 0.08, top - 0.35, top - 0.08, 'glass_dark')
        return
    if kind == 'glass':
        recess(b, yF, ox0, ox1, T0, top, 0.2, 'glass', '#d8d6cf', '#d8d6cf', 'tile_floor')
        w = ox1 - ox0
        k = max(2, int(round(w / 1.1)))
        for i in range(1, k):
            x = ox0 + w * i / k
            qf(b, yF + 0.185, x - 0.04, x + 0.04, T0, top, 'frame_black')
        qf(b, yF + 0.17, ox0, ox1, top - 0.6, top - 0.54, 'frame_black')
        dm = (ox0 + ox1) / 2
        qf(b, yF + 0.155, dm - 0.5, dm + 0.5, T0, top - 0.6, 'glass_dark')
        return
    # roll box above the opening
    b.box(ox0, yF - 0.17, top, ox1, yF, top + 0.24, sc, skip=('back',))
    if kind == 'closed':
        recess(b, yF, ox0, ox1, T0, top, 0.08, sc, sc, sc, 'tile_floor')
        z = T0 + 0.3
        while z < top - 0.1:
            qf(b, yF + 0.07, ox0 + 0.02, ox1 - 0.02, z - 0.035, z, 'shutter_groove')
            z += 0.3
        # padlock plate
        m = (ox0 + ox1) / 2
        qf(b, yF + 0.065, m - 0.12, m + 0.12, T0 + 0.05, T0 + 0.2, 'frame_black')
        return
    dp = min(2.0, yGB - yF - 0.6)
    recess(b, yF, ox0, ox1, T0, top, dp, INT_BACK, INT_SIDE, INT_CEIL, 'tile_floor')
    yb = yF + dp
    shop = u['shop'] or 'toko'
    if shop == 'bengkel':
        qf(b, yb - 0.01, ox0 + 0.3, ox1 - 0.3, T0 + 0.9, T0 + 2.0, '#5a5550')
        for i in range(4):
            x = ox0 + 0.5 + i * (ox1 - ox0 - 1.0) / 3
            qf(b, yb - 0.02, x - 0.12, x + 0.12, T0 + 1.1 + (i % 2) * 0.3, T0 + 1.6 + (i % 2) * 0.3, GOODS[(i * 3) % 8])
        for j, x in enumerate((ox0 + 0.45, ox0 + 1.05)):
            b.cyl(x, yb - 0.5, T0, T0 + 0.8 + 0.2 * j, 0.3, '#2f2d2c', seg=8)
    else:
        # shelves full of goods on the back wall
        b.box(ox0 + 0.15, yb - 0.38, T0, ox1 - 0.15, yb, T0 + 2.1, '#b89a74' if shop != 'makan' else '#d9d2c2',
              skip=('back', 'bottom', 'top'))
        for r in range(3):
            z = T0 + 0.25 + r * 0.62
            x = ox0 + 0.25
            while x < ox1 - 0.45:
                w = min(rng.uniform(0.6, 1.3), ox1 - 0.25 - x)
                qf(b, yb - 0.392, x, x + w, z, z + 0.4, GOODS[rng.randrange(len(GOODS))])
                x += w + 0.06
        if shop == 'makan':   # glass food cabinet (etalase) near the front
            ex = ox0 + 0.3
            b.box(ex, yF + 0.25, T0, ex + 1.3, yF + 0.75, T0 + 0.8, 'trim_white')
            b.box(ex, yF + 0.25, T0 + 0.8, ex + 1.3, yF + 0.75, T0 + 1.3, 'glass_light')
        else:              # counter
            ex = ox1 - 0.35 - min(1.6, (ox1 - ox0) * 0.4)
            b.box(ex, yF + 0.5, T0, ox1 - 0.35, yF + 0.95, T0 + 0.95, '#c9a86e' if shop == 'toko' else '#4f86c6')
        if shop == 'warung':  # renteng sachets hanging at the front
            x = ox0 + 0.2
            i = 0
            while x < ox0 + (ox1 - ox0) * 0.45:
                qf(b, yF + 0.25, x, x + 0.13, top - 0.95 + (i % 2) * 0.2, top - 0.05, GOODS[(i * 5 + 1) % 8])
                x += 0.2
                i += 1
    if kind == 'half':
        zh = T0 + (top - T0) * 0.52
        b.box(ox0, yF + 0.04, zh, ox1, yF + 0.1, top, sc, skip=('left', 'right', 'back', 'top'))
        z = zh + 0.3
        while z < top - 0.1:
            qf(b, yF + 0.028, ox0 + 0.02, ox1 - 0.02, z - 0.035, z, 'shutter_groove')
            z += 0.3


def upper_cell(b, v, u, k, zf, zt, st, yU, lowsign, rng):
    """One unit x one upper floor of the front facade."""
    cx0, cx1, cc, cw = u['cx0'], u['cx1'], u['cc'], u['cw']
    frame = v['frame']
    sill = v['band'] if v['band'] != frame else 'trim_white'
    wz = zf + (1.25 if lowsign else 0.95)
    wh = min(1.45, zt - 0.5 - wz)
    bars = 'rail_black' if v.get('teralis') else None
    ac_ok = True
    if st == 'win2' or st == 'dijual' or st == 'shut':
        w = min(1.35, cw * 0.32)
        xs = (cc - cw * 0.24, cc + cw * 0.24)
        for j, x in enumerate(xs):
            if st == 'dijual' and j == 1:
                # bricked-up window with a blank 'dijual' board (white, red header band) fixed inside the frame
                bricked(b, yU, x, wz, w, wh, frame, sill)
                bx0, bx1, bz0, bz1 = x - w / 2 + 0.1, x + w / 2 - 0.1, wz + 0.22, wz + wh - 0.14
                board(b, yU - 0.095, bx0, bx1, bz0, bz1, 'sign_white', depth=0.03)
                qf(b, yU - 0.137, bx0, bx1, bz1 - 0.15, bz1, 'sign_red')
            elif st == 'shut':
                fwin(b, yU, x, wz, w, wh, frame, glass='#c9c3b4', panes=2, sill=sill)
            else:
                fwin(b, yU, x, wz, w, wh, frame, panes=2, sill=sill, transom=True, bars=bars)
    elif st == 'win3':
        w = min(0.85, cw * 0.2)
        for x in (cc - cw * 0.31, cc, cc + cw * 0.31):
            fwin(b, yU, x, wz - 0.1, w, wh + 0.2, frame, panes=1, sill=sill, transom=True, bars=bars)
        ac_ok = False
    elif st == 'ribbon':
        w = cw - 0.5
        fwin(b, yU, cc, wz + 0.05, w, wh - 0.2, frame, glass='glass_light' if rng.random() < 0.4 else 'glass',
             panes=max(3, int(round(w / 0.75))), sill=sill, bars=bars)
        hz = wz + wh - 0.15 + 0.2
        b.box(cx0 + 0.02, yU - 0.55, hz, cx1 - 0.02, yU, hz + 0.1, v['band'], skip=('back',))
    elif st == 'glass':
        w = cw - 0.35
        z0 = zf + (1.15 if lowsign else 0.45)
        fwin(b, yU, cc, z0, w, zt - 0.4 - z0, frame, glass='glass_dark', panes=max(2, int(round(w / 1.3))),
             transom=True)
        ac_ok = False
    elif st == 'banner':
        c = ['sign_yellow', 'sign_green', 'sign_orange', 'sign_blue'][(u['i'] + k) % 4]
        if c == u['sign']:
            c = 'sign_red'
        board(b, yU, cx0 + 0.12, cx1 - 0.12, zf + (1.2 if lowsign else 0.45), zt - 0.5, c, depth=0.05)
        ac_ok = False
    elif st == 'walled':
        # empty unit: one window closed with wooden krepyak shutters, the other bricked up with a 'disewakan' board
        w = min(1.35, cw * 0.32)
        krepyak(b, yU, cc - cw * 0.24, wz, w, wh, frame, '#4f7a58', sill)
        x = cc + cw * 0.24
        bricked(b, yU, x, wz, w, wh, frame, sill)
        board(b, yU - 0.095, x - w / 2 + 0.1, x + w / 2 - 0.1, wz + 0.3, wz + wh - 0.3, 'sign_yellow', depth=0.03)
    elif st == 'balcony':
        dp = min(1.0, yU - 0.1)
        rc = v.get('rail', 'rail_black')
        b.box(cx0, yU - dp, zf - 0.02, cx1, yU, zf + 0.16, v['band'], skip=('back',))
        frail(b, yU - dp + 0.02, cx0 + 0.04, cx1 - 0.04, zf + 0.16, 1.0, rc)
        for x in (cx0 + 0.04, cx1 - 0.09):   # side rails
            b.box(x, yU - dp + 0.07, zf + 1.1, x + 0.05, yU, zf + 1.16, rc, skip=())
            for j in range(1, 4):
                y = yU - dp + 0.07 + (dp - 0.07) * j / 4
                if x < cc:
                    ql(b, x + 0.02, y - 0.012, y + 0.012, zf + 0.16, zf + 1.1, rc)
                else:
                    qr(b, x + 0.03, y - 0.012, y + 0.012, zf + 0.16, zf + 1.1, rc)
        # glass door + window behind
        dx = cc - cw * 0.22
        fwin(b, yU, dx, zf + 0.16, 0.9, 2.1, frame, glass='glass', panes=2)
        fwin(b, yU, cc + cw * 0.2, wz, min(1.3, cw * 0.3), wh, frame, panes=2)
        if cw > 3.5:
            pot(b, cx0 + 0.5, yU - dp + 0.45, zf + 0.16)
        ac_ok = False
        fac(b, yU, cx1 - 0.55, zf + 0.2) if cw > 4.2 else None
    elif st == 'loggia':
        hx0, hx1, hz0, hz1 = cx0 + 0.15, cx1 - 0.15, zf + 0.12, zt - 0.5
        dp = 1.1
        front_wall(b, yU, u['x0'], u['x1'], zf, zt, [(hx0, hx1, hz0, hz1)], u['wall'])
        inner = 'wall_white' if u['wall'] != 'wall_white' else 'wall_cream'
        recess(b, yU, hx0, hx1, hz0, hz1, dp, inner, u['wall'], inner, 'tile_floor')
        yb = yU + dp
        fwin(b, yb, hx0 + 0.75, hz0, 0.9, 2.1, frame, glass='door_wood', panes=1)
        fwin(b, yb, hx1 - 1.05, hz0 + 0.9, 1.1, 1.2, frame, panes=2)
        frail(b, yU - 0.05, hx0 - 0.05, hx1 + 0.05, hz0, 1.0, v.get('rail', 'rail_white'))
        if rng.random() < 0.7:   # washing hung inside
            ly = yU + 0.5
            b.box(hx0, ly - 0.01, hz1 - 0.2, hx1, ly + 0.01, hz1 - 0.18, 'rail_white', skip=('bottom',))
            x = hx0 + 0.3
            for j in range(3):
                w = rng.uniform(0.35, 0.55)
                qf(b, ly - 0.012, x, x + w, hz1 - 0.2 - rng.uniform(0.5, 0.8), hz1 - 0.2, CLOTH[rng.randrange(len(CLOTH))])
                x += w + 0.4
        ac_ok = False
    # AC condenser under a window (not where the shop sign hangs)
    if ac_ok and not lowsign and cw > 3.0 and rng.random() < 0.65:
        fac(b, yU, cc + (cw * 0.24 if rng.random() < 0.5 else -cw * 0.24), zf + 0.2)


def unit_roof_props(b, v, u, y0, y1, z0, rng):
    """Toren, stair house, jemuran, zinc canopy, AC units, pots and dishes on one unit's flat roof."""
    x0, x1 = u['x0'] + 0.2, u['x1'] - 0.2
    props = u['props']
    frame = v['frame']
    back = y1 - 0.2
    right = u['i'] % 2 == 0
    for p in props:
        if p in ('toren', 'toren_b'):
            cx = x1 - 0.6 if right else x0 + 0.6
            toren(b, cx, back - 0.6, z0, 'tank_orange' if p == 'toren' else 'tank_blue', stand=0.8)
        elif p == 'toren_blk':
            cx = x1 - 0.65 if right else x0 + 0.65
            toren_block(b, cx, back - 0.65, z0, 'tank_blue' if u['i'] % 2 else 'tank_orange')
        elif p == 'toren_low':
            cx = x1 - 0.65 if right else x0 + 0.65
            toren_block(b, cx, back - 0.65, z0, 'tank_orange', base=0.2, h=0.95)
        elif p in ('room', 'room_t'):
            rw = min(2.3, x1 - x0 - 0.4)
            rx0 = x0 + 0.1 if not right else x1 - 0.1 - rw
            ry1 = back - 0.05
            ry0 = ry1 - 2.6
            h = 2.3
            wallc = u['wall']
            stair_room(b, rx0, rx0 + rw, ry0, ry1, z0, h, wallc, 'concrete', frame)
            if p == 'room_t':
                toren(b, rx0 + rw / 2, ry0 + 1.5, z0 + h + 0.14, 'tank_orange', stand=0, h=1.0)
        elif p in ('jemuran', 'jemuran1'):
            yc = y0 + (y1 - y0) * 0.45
            jemuran(b, x0 + 0.35, x1 - 0.35, yc, z0, rng, two=p == 'jemuran')
        elif p == 'zinc':
            zy0 = y0 + 0.5
            zy1 = min(y1 - 0.4, zy0 + 4.0)
            zinc_canopy(b, x0 + 0.1, x1 - 0.1, zy0, zy1, z0, 2.45, 2.2, 'roof_blue' if u['i'] % 2 else '#d9d4c7')
        elif p == 'zincfull':   # green spandek roof over the whole roof terrace, washing lines underneath
            zinc_canopy(b, x0 + 0.05, x1 - 0.05, y0 + 0.1, y1 - 0.1, z0, 1.9, 1.75, '#4f8a5a')
            jemuran(b, x0 + 0.5, x1 - 0.5, y0 + (y1 - y0) * 0.6, z0, rng, two=False)
        elif p == 'ac':
            ax = x0 + 0.7 if right else x1 - 0.7
            roof_ac(b, ax, y0 + 1.0, z0)
            if u['cw'] > 3.5:
                roof_ac(b, ax + (1.0 if right else -1.0), y0 + 1.0, z0)
        elif p == 'pots':
            px0 = x0 + 0.3 if right else x1 - 2.4
            b.box(px0, y0 + 0.1, z0, px0 + 2.1, y0 + 0.55, z0 + 0.4, 'pot')
            b.box(px0 + 0.05, y0 + 0.05, z0 + 0.4, px0 + 2.05, y0 + 0.6, z0 + 0.85, 'plant')
        elif p == 'hatch':   # roof hatch over the stair, on the side opposite the toren
            hx = x0 + 0.3 if right else x1 - 1.3
            b.box(hx, y1 - 2.6, z0, hx + 1.0, y1 - 1.4, z0 + 0.55, '#8f8b84')
        elif p == 'dish':
            dish(b, x1 - 0.8 if not right else x0 + 0.8, y0 + 1.2, z0)
        elif p == 'addon':
            # semi-permanent extra room with a zinc lean-to roof covering most of the unit roof
            ax0, ax1 = x0 + 0.05, x1 - 0.05
            ay0, ay1 = y0 + 1.6, y1 - 0.1
            h = 2.5
            wallc = '#e6dcc4'
            b.box(ax0, ay0, z0, ax1, ay1, z0 + h, wallc, skip=('bottom', 'top'))
            fwin(b, ay0, (ax0 + ax1) / 2 + 0.6, z0 + 1.0, 1.2, 1.0, frame, panes=2)
            b.box(ax0 + 0.4, ay0 - 0.05, z0, ax0 + 1.3, ay0, z0 + 2.05, frame, skip=('back', 'bottom'))
            qf(b, ay0 - 0.06, ax0 + 0.47, ax0 + 1.23, z0, z0 + 1.98, 'door_wood')
            bwin(b, ay1, (ax0 + ax1) / 2, z0 + 1.2, 1.0, 0.8, frame)
            top = [(ax0 - 0.1, ay0 - 0.6, z0 + h + 0.45), (ax1 + 0.1, ay0 - 0.6, z0 + h + 0.45),
                   (ax1 + 0.1, ay1 + 0.08, z0 + h + 0.05), (ax0 - 0.1, ay1 + 0.08, z0 + h + 0.05)]
            bot = [(p_[0], p_[1], p_[2] - 0.06) for p_ in top]
            b._slab(top, bot, 'roof_blue')
            # gable-ish fill between wall top and sloped roof on the sides
            s = (0.4 / (ay1 + 0.08 - ay0 + 0.6))
            zf_ = z0 + h + 0.39 - s * 0.6
            b.face([(ax0, ay1, z0 + h), (ax0, ay0, z0 + h), (ax0, ay0, zf_)], wallc)
            b.face([(ax1, ay0, z0 + h), (ax1, ay1, z0 + h), (ax1, ay0, zf_)], wallc)
            b.face([(ax0, ay0, z0 + h), (ax1, ay0, z0 + h), (ax1, ay0, zf_), (ax0, ay0, zf_)], wallc)
            k = 5
            for j in range(1, k):
                x = ax0 - 0.1 + (ax1 - ax0 + 0.2) * j / k
                b.face([(x - 0.04, ay0 - 0.6, z0 + h + 0.462), (x + 0.04, ay0 - 0.6, z0 + h + 0.462),
                        (x + 0.04, ay1 + 0.08, z0 + h + 0.062), (x - 0.04, ay1 + 0.08, z0 + h + 0.062)], 'metal')
            pot(b, x1 - 0.5, y0 + 0.6, z0)


def flat_roof(b, v, U, yU, yUB, Hr, ph, rng):
    W = b.W
    n = len(U)
    trim = v['trim']
    phb = min(ph, 0.85)
    for u in U:
        rc = u['roofcol']
        if isinstance(rc, (tuple, list)):
            ys = yU + 0.15 + (yUB - yU - 0.3) * rc[2]
            qu(b, Hr, u['x0'], u['x1'], yU, ys, rc[1])
            qu(b, Hr, u['x0'], u['x1'], ys, yUB, rc[0])
        else:
            qu(b, Hr, u['x0'], u['x1'], yU, yUB, rc)
    # front parapet (facade continued) per unit, coping, crowns
    for u in U:
        sk = ('bottom',) + (('left',) if u['i'] > 0 else ()) + (('right',) if u['i'] < n - 1 else ())
        b.box(u['x0'], yU, Hr, u['x1'], yU + 0.15, Hr + ph, u['wall'], skip=sk)
    b.box(-W / 2 + 0.01, yU - 0.06, Hr + ph, W / 2 - 0.01, yU + 0.22, Hr + ph + 0.08, 'trim_white'
          if trim != 'trim_white' else 'concrete', skip=('bottom',))
    ztop = Hr + ph + 0.08
    for u in U:
        crown(b, v, u, yU, ztop)
    # side and back parapets
    wl, wr = U[0]['wall'], U[-1]['wall']
    b.box(-W / 2, yU + 0.15, Hr, -W / 2 + 0.15, yUB - 0.15, Hr + phb, wl)
    b.box(W / 2 - 0.15, yU + 0.15, Hr, W / 2, yUB - 0.15, Hr + phb, wr)
    for u in U:
        sk = ('bottom',) + (('left',) if u['i'] > 0 else ()) + (('right',) if u['i'] < n - 1 else ())
        b.box(u['x0'], yUB - 0.15, Hr, u['x1'], yUB, Hr + phb, u['wall'], skip=sk)
    # low party walls between units
    for k in range(1, n):
        xb = -W / 2 + k * (W / n)
        b.box(xb - 0.1, yU + 0.15, Hr, xb + 0.1, yUB - 0.15, Hr + phb * 0.75, U[k]['wall'],
              skip=('bottom', 'front', 'back'))
    for u in U:
        unit_roof_props(b, v, u, yU + 0.15, yUB - 0.15, Hr, rng)


def crown(b, v, u, yU, ztop):
    kind = v.get('crown', 'flat')
    cc, cw = u['cc'], u['cw']
    if kind == 'step':
        w = cw * 0.28
        b.box(cc - w, yU - 0.04, ztop, cc + w, yU + 0.2, ztop + 0.5, v['trim'] if v['trim'] != 'trim_white' else u['wall'])
    elif kind == 'gable':
        x0, x1 = cc - cw * 0.42, cc + cw * 0.42
        prism_y(b, yU - 0.04, yU + 0.18, [(x0, ztop), (x1, ztop), (cc, ztop + 0.75)],
                [None, u['wall'], u['wall']], caps=(u['wall'], u['wall']))
        qf(b, yU - 0.052, cc - 0.2, cc + 0.2, ztop + 0.18, ztop + 0.38, v['trim'])


def shed_roof(b, v, U, yU, yUB, Hr, ph):
    """Tall front parapet with crowns, and per unit a zinc/tile shed roof falling to the back."""
    W = b.W
    n = len(U)
    trim = v['trim']
    for u in U:
        sk = ('bottom',) + (('left',) if u['i'] > 0 else ()) + (('right',) if u['i'] < n - 1 else ())
        b.box(u['x0'], yU, Hr, u['x1'], yU + 0.15, Hr + ph, u['wall'], skip=sk)
    b.box(-W / 2 + 0.01, yU - 0.06, Hr + ph, W / 2 - 0.01, yU + 0.22, Hr + ph + 0.08,
          'trim_white' if trim != 'trim_white' else 'concrete', skip=('bottom',))
    for u in U:
        crown(b, v, u, yU, Hr + ph + 0.08)
    for u in U:
        rc = u['roofcol']
        F1 = (yU + 0.15, Hr + ph - 0.12)
        B1 = (yUB + 0.3, Hr + 0.1)
        B0 = (yUB + 0.3, Hr)
        F0 = (yU + 0.15, Hr)
        prof = [F0, F1, B1, B0]
        caps = (u['wall'] if u['i'] == 0 else None, u['wall'] if u['i'] == n - 1 else None)
        prism_x(b, u['x0'], u['x1'], prof, [None, rc, 'trim_white', rc], caps=caps)
        rib = DARK.get(rc, shade(rc, 0.65))
        if rc == 'roof_terracotta':
            # tile courses across the slope
            for j in range(1, 5):
                t = j / 5
                p = (F1[0] + (B1[0] - F1[0]) * t, F1[1] + (B1[1] - F1[1]) * t)
                q = (p[0] + 0.1, p[1] + (B1[1] - F1[1]) / (B1[0] - F1[0]) * 0.1)
                strip_x(b, u['x0'] + 0.02, u['x1'] - 0.02, p, q, rib)
        else:
            k = max(3, int(u['x1'] - u['x0']) // 1 + 1)
            for j in range(1, k):
                x = u['x0'] + (u['x1'] - u['x0']) * j / k
                strip_x(b, x - 0.04, x + 0.04, F1, B1, rib)
    # toren air on a steel stand standing on the zinc near the back (legs follow the slope)
    F1, B1 = (yU + 0.15, Hr + ph - 0.12), (yUB + 0.3, Hr + 0.1)

    def zs(y):
        return F1[1] + (B1[1] - F1[1]) * (y - F1[0]) / (B1[0] - F1[0])
    for u in U:
        if 'toren' not in u['props']:
            continue
        cx = u['x1'] - 0.75 if u['i'] % 2 == 0 else u['x0'] + 0.75
        cy = yUB - 0.9
        zp = zs(cy - 0.36) + 0.35
        for dx in (-0.36, 0.36):
            for dy in (-0.36, 0.36):
                b.box(cx + dx - 0.04, cy + dy - 0.04, zs(cy + dy + 0.04) - 0.02, cx + dx + 0.04, cy + dy + 0.04, zp - 0.06,
                      'metal', skip=('bottom', 'top'))
        b.box(cx - 0.46, cy - 0.46, zp - 0.06, cx + 0.46, cy + 0.46, zp, 'metal', skip=())
        b.cyl(cx, cy, zp, zp + 1.0, 0.5, 'tank_orange', seg=8)
    # fire walls between units, following the slope
    for k in range(1, n):
        xb = -W / 2 + k * (W / n)
        prof = [(yU + 0.15, Hr), (yU + 0.15, Hr + ph + 0.08), (yUB, Hr + 0.35), (yUB, Hr)]
        prism_x(b, xb - 0.1, xb + 0.1, prof, [None, U[k]['wall'], U[k]['wall'], None],
                caps=(U[k - 1]['wall'], U[k]['wall']))


def mansard_roof(b, v, U, yU, yUB, Hr, ph, rng):
    """Sloped tile band over the top of the facade (90s ruko), flat roof with low parapet behind it."""
    W = b.W
    n = len(U)
    rc = U[0]['roofcol']
    e = min(0.55, yU - 0.1)
    E, A, B, C, Dd = (yU, Hr - 0.3), (yU - e, Hr - 0.3), (yU - e, Hr - 0.15), (yU + 1.2, Hr + 1.3), (yU + 1.2, Hr)
    prof = [E, A, B, C, Dd]
    # the band spans between the fire walls
    walls_x = []
    for k in range(n + 1):
        xb = -W / 2 + k * (W / n)
        x0, x1 = (xb + 0.01, xb + 0.24) if k == 0 else ((xb - 0.24, xb - 0.01) if k == n else (xb - 0.15, xb + 0.15))
        walls_x.append((x0, x1))
    for u in U:
        a, c = walls_x[u['i']][1], walls_x[u['i'] + 1][0]
        prism_x(b, a, c, prof, ['trim_white', v['trim'], rc, u['wall'], None])
        for j in range(1, 5):
            t = j / 5
            p = (B[0] + (C[0] - B[0]) * t, B[1] + (C[1] - B[1]) * t)
            q = (p[0] + 0.08, p[1] + 0.08 * (C[1] - B[1]) / (C[0] - B[0]))
            strip_x(b, a + 0.01, c - 0.01, p, q, DARK.get(rc, shade(rc, 0.65)))
    # fire walls poking through the slope
    fw = [(yU - e - 0.05, Hr - 0.35), (yU - e - 0.05, Hr + 0.0), (yU + 1.35, Hr + 1.52), (yU + 1.35, Hr - 0.35)]
    for k, (x0, x1) in enumerate(walls_x):
        wc = U[min(k, n - 1)]['wall']
        prism_x(b, x0, x1, fw, ['trim_white', v['trim'], wc, wc], caps=(wc, wc))
    # flat roof behind
    yR = yU + 1.35
    for u in U:
        qu(b, Hr, u['x0'], u['x1'], yU + 1.2, yUB, GREY if u['i'] % 2 == 0 else GREEN)
    phb = ph
    wl, wr = U[0]['wall'], U[-1]['wall']
    b.box(-W / 2, yR, Hr, -W / 2 + 0.15, yUB - 0.15, Hr + phb, wl, skip=('bottom', 'front'))
    b.box(W / 2 - 0.15, yR, Hr, W / 2, yUB - 0.15, Hr + phb, wr, skip=('bottom', 'front'))
    for u in U:
        sk = ('bottom',) + (('left',) if u['i'] > 0 else ()) + (('right',) if u['i'] < n - 1 else ())
        b.box(u['x0'], yUB - 0.15, Hr, u['x1'], yUB, Hr + phb, u['wall'], skip=sk)
    for k in range(1, n):
        xb = -W / 2 + k * (W / n)
        b.box(xb - 0.1, yR, Hr, xb + 0.1, yUB - 0.15, Hr + phb * 0.75, U[k]['wall'], skip=('bottom', 'front', 'back'))
    for u in U:
        unit_roof_props(b, v, u, yR + 0.1, yUB - 0.15, Hr, rng)


def pitched_roof(b, v, U, yU, yUB, Hr):
    """Old-style tile roof, ridge parallel to the street, eaves over the facade and the back wall,
    party walls between units standing proud of the tiles."""
    W = b.W
    n = len(U)
    rc = U[0]['roofcol']
    e, eb = 0.5, 0.35
    ym = (yU - e + yUB + eb) / 2
    rise = (ym - (yU - e)) * math.tan(math.radians(27))
    P0, P1 = (yU - e, Hr - 0.25), (yU - e, Hr - 0.1)
    P2 = (ym, Hr - 0.1 + rise)
    P3, P4 = (yUB + eb, Hr - 0.1), (yUB + eb, Hr - 0.25)
    prof = [P0, P1, P2, P3, P4]
    dark = '#8f3b1f' if rc == 'roof_terracotta' else '#5a3a28'
    for u in U:
        caps = (u['wall'] if u['i'] == 0 else None, u['wall'] if u['i'] == n - 1 else None)
        prism_x(b, u['x0'], u['x1'], prof, [v['trim'], rc, rc, v['trim'], 'trim_white'], caps=caps)
        for (p, q) in ((P1, P2), (P2, P3)):
            for j in range(1, 5):
                t = j / 5
                a = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
                c = (a[0] + (q[0] - p[0]) * 0.03, a[1] + (q[1] - p[1]) * 0.03)
                strip_x(b, u['x0'] + 0.02, u['x1'] - 0.02, a, c, dark)
        # ridge capping
        a = (P2[0] + (P1[0] - P2[0]) * 0.04, P2[1] + (P1[1] - P2[1]) * 0.04)
        c = (P2[0] + (P3[0] - P2[0]) * 0.04, P2[1] + (P3[1] - P2[1]) * 0.04)
        strip_x(b, u['x0'] + 0.02, u['x1'] - 0.02, a, P2, dark, off=0.03)
        strip_x(b, u['x0'] + 0.02, u['x1'] - 0.02, P2, c, dark, off=0.03)
    if v.get('dish'):   # satellite dish on a short mast fixed to the ridge
        dish(b, -W / 2 + W * 0.3, P2[0], P2[1] - 0.2)
    for k in range(1, n):
        xb = -W / 2 + k * (W / n)
        fw = [(P0[0] - 0.05, P0[1] - 0.05), (P1[0] - 0.05, P1[1] + 0.2), (P2[0], P2[1] + 0.25),
              (P3[0] + 0.0, P3[1] + 0.2), (P4[0], P4[1] - 0.05)]
        prism_x(b, xb - 0.12, xb + 0.12, fw, [v['trim'], U[k]['wall'], U[k]['wall'], U[k]['wall'], None],
                caps=(U[k - 1]['wall'], U[k]['wall']))

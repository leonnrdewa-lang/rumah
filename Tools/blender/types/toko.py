"""Toko: modern small shops and services on a Jakarta street.

Minimarkets with a full-width glass front, automatic sliding door, a blank striped fascia and a parking
apron; a small apotek and klinik (white boxes with a green/blue fascia and a projecting blank sign - never a
cross); a bakery with a striped awning and outdoor seats; a two-storey cafe with a roof terrace; handphone
counters with a big colour fascia. Generic only: no brands, no logos, no readable text (signs are blank
boards with a few colour bars).

One-storey variants stay <= 4.8 m in total (role 'low'); two-storey ones are 'front' only.
Coordinate convention as in common.py: x in [-W/2, W/2], y = 0 is the street facade, z up.
"""
import math

TYPE = 'toko'
ROLES = ['front', 'low']
LOW = ['front', 'low']             # one storey, total height <= 4.8 m (never 'fill': shops need the street)
FRONT = ['front']                  # two storeys: street-facing rows only

# extra colours (sRGB hex) on top of common.PALETTE
C = {
    'magenta': '#d8367f', 'teal': '#1c9c9a', 'navy': '#244a78', 'lime': '#86c440',
    'wood': '#a86b3e', 'wood_dark': '#6e4428', 'steel': '#34373a', 'brick': '#b4634a',
    'roof_green': '#97ab98', 'roof_red': '#b3705f', 'roof_light': '#cdcfca', 'solar': '#2c4470',
    'cream': '#f4dcb4', 'lpg': '#3f9a5a', 'deck': '#b98a5e', 'terrazzo': '#d9d2c4', 'card': '#c9a36b',
    'glass_green': '#6fa59a', 'frost': '#dfe8ea', 'olive': '#7d8c4e',
}
SHELF = ['#e8c35a', '#e07a5f', '#8ab89c', '#f2efe4', '#7fa8d9']


def variants():
    return [
        # 00 minimarket, flat roof, white box, white fascia with a teal top band and an orange base stripe,
        #    ATM booth at one end, 3 car bays
        dict(kind='mini', roof='flat', w=10.0, d=13.0, roles=LOW, apron=4.0, bays=3, stops='sign_yellow',
             wall='wall_white', roofc='#6e7276', fascia='sign_white', fz=(3.05, 4.45), fout=0.95,
             stripes=[(4.12, 4.45, C['teal']), (3.05, 3.3, 'sign_orange')],
             logo=(C['teal'], 'sign_white'), door=0.5, front='atm', emblem='fascia'),
        # 01 minimarket, wide, blue metal gable roof, green/yellow fascia, door at the terrace end, terrace seating
        dict(kind='mini', roof='gable', w=12.0, d=14.0, roles=LOW, apron=4.6, bays=3, stops='sign_white',
             lines_x=(-6.0, 2.2), wall='wall_cream', roofc='roof_blue', fascia='sign_green', fz=(2.95, 4.3),
             fout=1.05, stripes=[(2.95, 3.22, 'sign_yellow'), (4.08, 4.15, 'sign_white')],
             logo=('sign_white', 'sign_yellow'), door=1.35, front='terrace', emblem='fascia'),
        # 02 apotek: white box, green fascia, projecting blank sign, small canopy
        dict(kind='apotek', w=7.0, d=10.0, roles=LOW, wall='wall_white', roofc='#3f6f55', fascia='sign_green',
             tank='tank_blue'),
        # 03 klinik, two storeys, blue fascia, drop-off canopy, sun fins
        dict(kind='klinik', w=9.0, d=12.0, roles=FRONT, wall='wall_white', accent='wall_sky',
             roofc='#6f8f74', fascia='sign_blue'),
        # 04 bakery with a striped awning, outdoor seats and a front gable tile roof
        dict(kind='bakery', w=7.5, d=10.0, roles=LOW, wall=C['cream'], roofc='roof_terracotta',
             awning=('awning_red', 'awning_stripe'), sign='sign_red', floor=C['terrazzo']),
        # 05 handphone counter, narrow, big magenta fascia, mono-pitch zinc roof
        dict(kind='hp', w=6.0, d=9.0, roles=LOW, wall='wall_grey', fascia=C['magenta'], accent='sign_yellow',
             roofc='#76858f', ribs='#55616a'),
        # 06 cafe, two storeys: roof terrace with pergola, parasols on the street terrace
        dict(kind='cafe2', w=8.0, d=11.0, roles=FRONT, wall='wall_white', upper=C['olive'],
             roofc='#9a8f80', deck=C['deck']),
        # 07 handphone counter, two storeys, giant yellow fascia over the upper floor
        dict(kind='hp2', w=6.5, d=10.0, roles=FRONT, wall='wall_peach', fascia='sign_yellow', accent='sign_blue',
             roofc='#6b4a3f'),
        # 08 small minimarket with a terracotta hip roof and an orange fascia, emblem on a pylon, LPG cage and
        #    gallon-water rack out front, motorbike parking
        dict(kind='mini', roof='hip', w=8.0, d=13.0, roles=LOW, apron=3.3, bays=4, stops=None,
             lines_x=(-2.7, 4.0), wall='wall_white', roofc='#7a2f2a', fascia='sign_orange', fz=(2.85, 3.95),
             fout=0.8, stripes=[(3.72, 3.8, 'sign_white'), (2.85, 3.05, 'sign_green')],
             logo=('sign_white', 'sign_orange'), door=-0.7, front='cage', emblem='pylon'),
        # 09 wide klinik/apotek: entrance block, long canopy, pylon sign, solar panels
        dict(kind='klinik_wide', w=11.5, d=12.0, roles=LOW, wall='wall_white', accent=C['teal'],
             roofc='#5a6470', fascia='sign_blue'),
        # 10 laundry kiloan: glass front with washing machines, laundry drying on the flat roof
        dict(kind='laundry', w=9.0, d=10.5, roles=LOW, wall='wall_sky', roofc='#7d8a6e', fascia=C['navy'],
             canopy='awning_yellow'),
        # 11 coffee kiosk: dark box, pick-up window, mono-pitch roof with a deep front overhang, benches
        dict(kind='kopi', w=6.5, d=9.0, roles=LOW, wall='#3f3a37', roofc='#56606a', deck=C['deck']),
    ]


# ============================================================================================ helpers
def hq(b, x0, y0, x1, y1, z, c):
    """Upward-facing horizontal quad (roof slab, floor, painted lines)."""
    b.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], c)


def face_out(b, pts, c, hint):
    """Polygon whose winding is fixed so that its normal points along `hint`."""
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        a, d = pts[i], pts[(i + 1) % n]
        nx += (a[1] - d[1]) * (a[2] + d[2])
        ny += (a[2] - d[2]) * (a[0] + d[0])
        nz += (a[0] - d[0]) * (a[1] + d[1])
    if nx * hint[0] + ny * hint[1] + nz * hint[2] < 0:
        pts = list(reversed(pts))
    return b.face(pts, c)


def walls(b, x0, y0, x1, y1, z0, z1, c, skip=()):
    b.box(x0, y0, z0, x1, y1, z1, c, skip=('bottom', 'top') + tuple(skip))


def parapet(b, x0, x1, y0, y1, z0, h, c, t=0.15, front=True, cap=None):
    """Low wall around a flat roof (top faces in `cap` colour). front=False leaves the front open (a fascia
    stands there)."""
    cap = cap or c
    ys = y0
    boxes = []
    if front:
        boxes.append((x0, y0, x1, y0 + t))
        ys = y0 + t
    boxes += [(x0, y1 - t, x1, y1), (x0, ys, x0 + t, y1 - t), (x1 - t, ys, x1, y1 - t)]
    for (a0, b0, a1, b1) in boxes:
        b.box(a0, b0, z0, a1, b1, z0 + h, c, skip=('bottom', 'top'))
        hq(b, a0, b0, a1, b1, z0 + h, cap)


def wedge(b, x0, x1, y0, y1, z0, za, zb, c, top=True):
    """Box whose top slopes from za (at y0) to zb (at y1)."""
    face_out(b, [(x0, y0, z0), (x0, y1, z0), (x0, y1, zb), (x0, y0, za)], c, (-1, 0, 0))
    face_out(b, [(x1, y0, z0), (x1, y1, z0), (x1, y1, zb), (x1, y0, za)], c, (1, 0, 0))
    face_out(b, [(x0, y0, z0), (x1, y0, z0), (x1, y0, za), (x0, y0, za)], c, (0, -1, 0))
    face_out(b, [(x0, y1, z0), (x1, y1, z0), (x1, y1, zb), (x0, y1, zb)], c, (0, 1, 0))
    if top:
        face_out(b, [(x0, y0, za), (x1, y0, za), (x1, y1, zb), (x0, y1, zb)], c, (0, 0, 1))


def gable_roof(b, x0, x1, y0, y1, z0, rise, c, gable=None, over=0.3, over_end=0.3, thick=0.12, ridge='y'):
    """Closed two-slope roof whose underside passes exactly through the wall tops (no gap at the eaves).
    ridge='y': ridge runs front-to-back so the gable end faces the street. Returns slope info for on_slope()."""
    if ridge == 'y':
        a0, a1, l0, l1 = x0, x1, y0, y1
        P = lambda a, l, z: (a, l, z)
    else:
        a0, a1, l0, l1 = y0, y1, x0, x1
        P = lambda a, l, z: (l, a, z)
    am = (a0 + a1) / 2
    s = rise / (am - a0)
    la, lb = l0 - over_end, l1 + over_end
    ze = z0 - s * over
    Lb, Lt = (a0 - over, ze), (a0 - over, ze + thick)
    Rb, Rt = (a1 + over, ze), (a1 + over, ze + thick)
    Mb, Mt = (am, z0 + rise), (am, z0 + rise + thick)

    def strip(p, q, hint):
        face_out(b, [P(p[0], la, p[1]), P(q[0], la, q[1]), P(q[0], lb, q[1]), P(p[0], lb, p[1])], c, P(*hint))
    strip(Lt, Mt, (-s, 0, 1))
    strip(Mt, Rt, (s, 0, 1))
    strip(Lb, Mb, (s, 0, -1))
    strip(Mb, Rb, (-s, 0, -1))
    strip(Lb, Lt, (-1, 0, 0))
    strip(Rb, Rt, (1, 0, 0))
    for l, d in ((la, -1), (lb, 1)):
        for quad in ((Lb, Mb, Mt, Lt), (Mb, Rb, Rt, Mt)):
            face_out(b, [P(p[0], l, p[1]) for p in quad], c, P(0, d, 0))
    if gable:
        for l, d in ((l0, -1), (l1, 1)):
            face_out(b, [P(a0, l, z0), P(a1, l, z0), P(am, l, z0 + rise)], gable, P(0, d, 0))
    b.top = max(b.top, z0 + rise + thick)
    g = dict(P=P, a0=a0, a1=a1, am=am, z0=z0, s=s, thick=thick, la=la, lb=lb, over=over)
    return g


def roof_lines(b, g, c, courses=0, ribs=0.0, cap=None, cap_w=0.13, width=0.06):
    """Line work on a gable_roof so it reads from far away: tile courses parallel to the ridge,
    corrugation ribs down the slope (every `ribs` metres) and a ridge cap strip."""
    a0, a1, am, la, lb = g['a0'] - g['over'], g['a1'] + g['over'], g['am'], g['la'], g['lb']
    for k in range(1, courses + 1):
        t = k / (courses + 1)
        for (ae, sg) in ((a0, 1), (a1, -1)):
            a = ae + (am - ae) * t
            on_slope(b, g, a, a + sg * width, la + 0.02, lb - 0.02, c, eps=0.02)
    if ribs:
        n = int((lb - la) / ribs)
        for i in range(1, n + 1):
            l = la + (lb - la) * i / (n + 1)
            for (ae, e2) in ((a0 + 0.02, am - cap_w), (a1 - 0.02, am + cap_w)):
                on_slope(b, g, ae, e2, l - 0.025, l + 0.025, c, eps=0.02)
    if cap:
        P = g['P']
        z = slope_z(g, am) + 0.035
        zs = slope_z(g, am - cap_w) + 0.02
        face_out(b, [P(am - cap_w, la, zs), P(am, la, z), P(am, lb, z), P(am - cap_w, lb, zs)], cap, (0, 0, 1))
        face_out(b, [P(am, la, z), P(am + cap_w, la, zs), P(am + cap_w, lb, zs), P(am, lb, z)], cap, (0, 0, 1))


def hip_lines(b, x0, x1, y0, y1, z0, rise, c, over=0.3, thick=0.12, courses=3, width=0.07, cap=None):
    """Tile courses + hip/ridge caps on top of common.roof_hip (same arguments)."""
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    m = min(X1 - X0, Y1 - Y0) / 2
    zt = lambda e: z0 + thick + rise * e / m + 0.025

    def ring(e0, e1, col):
        a, bq = e0, e1
        za, zb = zt(a), zt(bq)
        o = [(X0 + a, Y0 + a), (X1 - a, Y0 + a), (X1 - a, Y1 - a), (X0 + a, Y1 - a)]
        i = [(X0 + bq, Y0 + bq), (X1 - bq, Y0 + bq), (X1 - bq, Y1 - bq), (X0 + bq, Y1 - bq)]
        for k in range(4):
            j = (k + 1) % 4
            face_out(b, [(o[k][0], o[k][1], za), (o[j][0], o[j][1], za), (i[j][0], i[j][1], zb), (i[k][0], i[k][1], zb)], col, (0, 0, 1))
    for k in range(1, courses + 1):
        e = m * k / (courses + 1)
        ring(e, e + width, c)
    if cap:
        # ridge + four hips as thin strips raised above the roof
        w, d = X1 - X0, Y1 - Y0
        if w >= d:
            r0, r1 = (X0 + d / 2, (Y0 + Y1) / 2), (X1 - d / 2, (Y0 + Y1) / 2)
        else:
            r0, r1 = ((X0 + X1) / 2, Y0 + w / 2), ((X0 + X1) / 2, Y1 - w / 2)
        ztop = z0 + thick + rise + 0.04
        hw = 0.08
        segs = [((X0, Y0), r0), ((X1, Y0), r1 if w >= d else r0), ((X1, Y1), r1), ((X0, Y1), r0 if w >= d else r1)]
        for (p, q) in segs:
            dx, dy = q[0] - p[0], q[1] - p[1]
            L = math.hypot(dx, dy)
            nx, ny = -dy / L * hw, dx / L * hw
            p = (p[0] + dx / L * 0.15, p[1] + dy / L * 0.15)
            zp = z0 + thick + 0.04 + rise * 0.15 / L
            face_out(b, [(p[0] - nx, p[1] - ny, zp), (p[0] + nx, p[1] + ny, zp), (q[0] + nx, q[1] + ny, ztop), (q[0] - nx, q[1] - ny, ztop)], cap, (0, 0, 1))
        if abs(r0[0] - r1[0]) + abs(r0[1] - r1[1]) > 1e-3:
            if w >= d:
                face_out(b, [(r0[0], r0[1] - hw, ztop), (r1[0], r1[1] - hw, ztop), (r1[0], r1[1] + hw, ztop), (r0[0], r0[1] + hw, ztop)], cap, (0, 0, 1))
            else:
                face_out(b, [(r0[0] - hw, r0[1], ztop), (r0[0] + hw, r0[1], ztop), (r1[0] + hw, r1[1], ztop), (r1[0] - hw, r1[1], ztop)], cap, (0, 0, 1))


def slope_z(g, a):
    return g['z0'] + g['thick'] + g['s'] * min(a - g['a0'], g['a1'] - a)


def on_slope(b, g, a_from, a_to, l_from, l_to, c, eps=0.03):
    """Flat quad lying just on top of one slope of a gable_roof (skylight sheets, solar water heater...)."""
    P = g['P']
    pts = [P(a_from, l_from, slope_z(g, a_from) + eps), P(a_to, l_from, slope_z(g, a_to) + eps),
           P(a_to, l_to, slope_z(g, a_to) + eps), P(a_from, l_to, slope_z(g, a_from) + eps)]
    face_out(b, pts, c, (0, 0, 1))


def shed_roof(b, x0, x1, y0, y1, z_hi, z_lo, c, fill=None, over=0.25, over_side=0.25, thick=0.1, over_front=None):
    """Mono-pitch roof falling from the front wall (z_hi at y0) to the back wall (z_lo at y1). Its underside
    passes through both wall tops; `fill` closes the front strip and side triangles above z_lo."""
    s = (z_hi - z_lo) / (y1 - y0)
    of = over if over_front is None else over_front
    ya, yb = y0 - of, y1 + over
    za, zb = z_hi + s * of, z_lo - s * over
    X0, X1 = x0 - over_side, x1 + over_side
    top = [(X0, ya, za + thick), (X1, ya, za + thick), (X1, yb, zb + thick), (X0, yb, zb + thick)]
    bot = [(p[0], p[1], p[2] - thick) for p in top]
    b._slab(top, bot, c)
    if fill:
        face_out(b, [(x0, y0, z_lo), (x1, y0, z_lo), (x1, y0, z_hi), (x0, y0, z_hi)], fill, (0, -1, 0))
        face_out(b, [(x0, y0, z_lo), (x0, y1, z_lo), (x0, y0, z_hi)], fill, (-1, 0, 0))
        face_out(b, [(x1, y0, z_lo), (x1, y1, z_lo), (x1, y0, z_hi)], fill, (1, 0, 0))
    b.top = max(b.top, za + thick)
    return lambda y: z_hi + thick - s * (y - y0)     # roof top height at y


def apron(b, x0, x1, y0, y1, lx=None, bays=0, stops=None, h=0.1, c='concrete', line='trim_white'):
    """Paved parking apron in front of the shop, painted bay lines and wheel stops."""
    b.box(x0, y0, 0, x1, y1, h, c, skip=('bottom', 'back'))
    if bays:
        a, e = lx if lx else (x0, x1)
        a, e = a + 0.3, e - 0.3
        for i in range(bays + 1):
            x = a + (e - a) * i / bays
            hq(b, x - 0.05, y0 + 0.5, x + 0.05, y1 - 0.9, h + 0.015, line)     # stops short of the props zone
        if stops:
            for i in range(bays):
                xc = a + (e - a) * (i + 0.5) / bays
                b.box(xc - 0.45, y1 - 1.3, h, xc + 0.45, y1 - 1.15, h + 0.1, stops)


def fascia(b, x0, x1, yf, yb, z0, z1, base, stripes=()):
    """Projecting fascia box with horizontal colour stripes wrapped onto its two ends."""
    b.box(x0, yf, z0, x1, yb, z1, base, skip=())
    for (za, zb, c) in stripes:
        b.decal('front', x0, x1, za, zb, c, off=0.02, wall=yf)
        b.decal('left', yf, yb, za, zb, c, off=0.02, wall=x0)
        b.decal('right', yf, yb, za, zb, c, off=0.02, wall=x1)


def storefront(b, x0, x1, z0, z1, wall, door=None, frame='metal', glass='glass_light', leaf='glass', bay=1.5,
               kick=0.3, kick_col=None, auto=True, shelves=(), shelf_cols=SHELF, side='front'):
    """Aluminium shop front: one frame slab with glass panes (decals) on it, optional shelves seen through the
    glass, a door (automatic sliding door with a motor header when auto=True)."""
    S, t = side, 0.06
    b.panel(S, x0, x1, z0, z1, frame, off=0.05, depth=0.05, wall=wall)
    segs = [(x0, x1)]
    if door:
        du, dw, dh = door
        segs = [(x0, du - dw / 2 - t / 2), (du + dw / 2 + t / 2, x1)]
    k = 0
    for (a, c) in segs:
        if c - a < 0.3:
            continue
        if kick_col:
            b.decal(S, a + t, c - t, z0 + t, z0 + kick - t / 2, kick_col, off=0.055, wall=wall)
        n = max(1, int(round((c - a) / bay)))
        pw = (c - a - (n + 1) * t) / n
        for i in range(n):
            u0 = a + t + i * (pw + t)
            b.decal(S, u0, u0 + pw, z0 + kick, z1 - t, glass, off=0.055, wall=wall)
            for j, zs in enumerate(shelves):
                b.decal(S, u0 + 0.04, u0 + pw - 0.04, zs, zs + 0.13, shelf_cols[(k + j) % len(shelf_cols)], off=0.06, wall=wall)
            k += 1
    if door:
        b.decal(S, du - dw / 2, du + dw / 2, z0, z0 + dh, leaf, off=0.055, wall=wall)
        b.decal(S, du - dw / 2, du + dw / 2, z0 + dh + t, z1 - t, glass, off=0.055, wall=wall)
        b.decal(S, du - 0.03, du + 0.03, z0, z0 + dh, frame, off=0.06, wall=wall)
        if auto:
            b.panel(S, du - dw / 2 - 0.12, du + dw / 2 + 0.12, z0 + dh + 0.02, z0 + dh + 0.24, frame, off=0.17, depth=0.12, wall=wall)


def win(b, side, uc, z0, w, h, wall=None, frame='window_frame', glass='glass', bars=1, off=0.05):
    """Cheap framed window: one frame slab + glass pane decals (12-16 tris)."""
    t = 0.07
    b.panel(side, uc - w / 2, uc + w / 2, z0, z0 + h, frame, off=off, depth=off, wall=wall)
    pw = (w - (bars + 1) * t) / bars
    for i in range(bars):
        u0 = uc - w / 2 + t + i * (pw + t)
        b.decal(side, u0, u0 + pw, z0 + t, z0 + h - t, glass, off=off + 0.005, wall=wall)


def cdoor(b, side, uc, w, h, wall=None, frame='trim_white', leaf='shutter_dark', z0=0.0):
    """Cheap door: frame slab + leaf decal."""
    b.panel(side, uc - w / 2 - 0.07, uc + w / 2 + 0.07, z0, z0 + h + 0.07, frame, off=0.05, depth=0.05, wall=wall)
    b.decal(side, uc - w / 2, uc + w / 2, z0, z0 + h, leaf, off=0.055, wall=wall)


def pipe(b, side, u, z1, wall, c='rail_white'):
    b.panel(side, u - 0.05, u + 0.05, 0, z1, c, off=0.13, depth=0.09, wall=wall)


def tank(b, cx, cy, z0, c, r=0.5, h=0.82):
    """Low water tank (toren) on a small concrete plinth - fits under the 4.8 m limit on a flat roof."""
    b.box(cx - r - 0.06, cy - r - 0.06, z0, cx + r + 0.06, cy + r + 0.06, z0 + 0.12, 'concrete')
    b.cyl(cx, cy, z0 + 0.12, z0 + 0.12 + h, r, c, seg=8)
    b.cyl(cx, cy, z0 + 0.12 + h, z0 + 0.19 + h, r * 0.4, c, seg=6)


def roof_ac(b, cx, cy, z0, face='front'):
    b.box(cx - 0.42, cy - 0.16, z0, cx + 0.42, cy + 0.16, z0 + 0.58, 'ac_white')
    if face == 'front':
        b.decal('front', cx - 0.34, cx + 0.04, z0 + 0.1, z0 + 0.48, 'metal', off=0.01, wall=cy - 0.16)
    else:
        b.decal('back', cx - 0.04, cx + 0.34, z0 + 0.1, z0 + 0.48, 'metal', off=0.01, wall=cy + 0.16)


def hatch(b, cx, cy, z0):
    b.box(cx - 0.42, cy - 0.42, z0, cx + 0.42, cy + 0.42, z0 + 0.3, 'concrete')
    b.box(cx - 0.48, cy - 0.48, z0 + 0.3, cx + 0.48, cy + 0.48, z0 + 0.36, 'concrete_dark')


def freezer(b, cx, cy, z0, band):
    """Ice-cream chest freezer in front of a minimarket."""
    b.box(cx - 0.5, cy - 0.3, z0, cx + 0.5, cy + 0.3, z0 + 0.82, 'ac_white')
    b.box(cx - 0.45, cy - 0.25, z0 + 0.82, cx + 0.45, cy + 0.25, z0 + 0.86, 'glass_light')
    b.decal('front', cx - 0.5, cx + 0.5, z0 + 0.32, z0 + 0.62, band, off=0.01, wall=cy - 0.3)


def bench(b, x0, x1, y0, y1, z0, c=None, leg='rail_black'):
    b.box(x0, y0, z0 + 0.4, x1, y1, z0 + 0.46, c or C['wood'])
    b.box(x0 + 0.08, y0 + 0.05, z0, x0 + 0.14, y1 - 0.05, z0 + 0.4, leg)
    b.box(x1 - 0.14, y0 + 0.05, z0, x1 - 0.08, y1 - 0.05, z0 + 0.4, leg)


def trash_bin(b, cx, cy, z0, c):
    b.box(cx - 0.22, cy - 0.22, z0, cx + 0.22, cy + 0.22, z0 + 0.75, c, skip=('bottom', 'top'))
    b.box(cx - 0.25, cy - 0.25, z0 + 0.75, cx + 0.25, cy + 0.25, z0 + 0.82, 'concrete_dark')


def lpg(b, cx, cy, z0=0.0, c=None):
    """3 kg 'melon' gas cylinder."""
    b.cyl(cx, cy, z0, z0 + 0.42, 0.15, c or C['lpg'], seg=6)
    b.box(cx - 0.04, cy - 0.04, z0 + 0.42, cx + 0.04, cy + 0.04, z0 + 0.5, 'metal')


def crates(b, x, y, n, rng, z0=0.0, cols=('awning_red', 'awning_blue', 'awning_yellow', 'awning_green')):
    for i in range(n):
        top = i == n - 1
        b.box(x - 0.26, y - 0.18, z0 + 0.3 * i, x + 0.26, y + 0.18, z0 + 0.3 * (i + 1), cols[rng.randrange(len(cols))],
              skip=('bottom',) if top else ('bottom', 'top'))


def chair(b, cx, cy, z0, fx, fy, c):
    """Cafe chair on a single pedestal; (fx, fy) = direction it faces (towards the table)."""
    b.box(cx - 0.04, cy - 0.04, z0, cx + 0.04, cy + 0.04, z0 + 0.42, 'rail_black')
    b.box(cx - 0.21, cy - 0.21, z0 + 0.42, cx + 0.21, cy + 0.21, z0 + 0.48, c)
    if fx:
        xb = cx - fx * 0.21
        b.box(min(xb, xb + fx * 0.06), cy - 0.21, z0 + 0.48, max(xb, xb + fx * 0.06), cy + 0.21, z0 + 0.9, c)
    else:
        yb = cy - fy * 0.21
        b.box(cx - 0.21, min(yb, yb + fy * 0.06), z0 + 0.48, cx + 0.21, max(yb, yb + fy * 0.06), z0 + 0.9, c)


def table_set(b, cx, cy, z0, top='trim_white', seat=None, axis='x'):
    b.box(cx - 0.05, cy - 0.05, z0, cx + 0.05, cy + 0.05, z0 + 0.72, 'rail_black')
    b.box(cx - 0.36, cy - 0.36, z0 + 0.72, cx + 0.36, cy + 0.36, z0 + 0.77, top)
    seat = seat or C['wood']
    for sg in (-1, 1):
        if axis == 'x':
            chair(b, cx + sg * 0.62, cy, z0, -sg, 0, seat)
        else:
            chair(b, cx, cy + sg * 0.62, z0, 0, -sg, seat)


def parasol(b, cx, cy, z0, c1, c2, r=0.95, h=2.15, rise=0.42, seg=8):
    """Market umbrella: pole + striped cone canopy (the pole passes through its table)."""
    b.box(cx - 0.03, cy - 0.03, z0, cx + 0.03, cy + 0.03, z0 + h + rise + 0.08, 'metal')
    ring = [(cx + r * math.cos(2 * math.pi * (i + 0.5) / seg), cy + r * math.sin(2 * math.pi * (i + 0.5) / seg)) for i in range(seg)]
    apex = (cx, cy, z0 + h + rise)
    for i in range(seg):
        a, d = ring[i], ring[(i + 1) % seg]
        mx, my = (a[0] + d[0]) / 2 - cx, (a[1] + d[1]) / 2 - cy
        face_out(b, [(a[0], a[1], z0 + h), (d[0], d[1], z0 + h), apex], c1 if i % 2 == 0 else c2, (mx, my, r * 0.6))
    face_out(b, [(p[0], p[1], z0 + h) for p in ring], c1, (0, 0, -1))
    b.top = max(b.top, z0 + h + rise + 0.08)


def turbine(b, cx, cy, z0, r=0.2):
    """Roof turbine ventilator (the spinning 'turbin ventilator' seen on metal roofs), 0.38 m tall."""
    b.cyl(cx, cy, z0 - 0.12, z0 + 0.1, r * 0.7, 'metal', seg=6, top=False)
    b.cyl(cx, cy, z0 + 0.1, z0 + 0.28, r, 'rail_white', seg=8, top=False)
    ring = [(cx + r * math.cos(2 * math.pi * i / 8), cy + r * math.sin(2 * math.pi * i / 8)) for i in range(8)]
    apex = (cx, cy, z0 + 0.38)
    for i in range(8):
        a, d = ring[i], ring[(i + 1) % 8]
        face_out(b, [(a[0], a[1], z0 + 0.28), (d[0], d[1], z0 + 0.28), apex], 'rail_white',
                 ((a[0] + d[0]) / 2 - cx, (a[1] + d[1]) / 2 - cy, 0.3))
    b.top = max(b.top, z0 + 0.38)


def flag(b, x, y, h, c1, c2, sgn=1):
    """Umbul-umbul: a tall pole with a long vertical banner (blank, two colours)."""
    b.box(x - 0.035, y - 0.035, 0, x + 0.035, y + 0.035, h, 'rail_white')
    fx0, fx1 = (x + 0.035, x + 0.5) if sgn > 0 else (x - 0.5, x - 0.035)
    b.box(fx0, y - 0.012, h - 2.4, fx1, y + 0.012, h - 0.1, c1, skip=())
    for side, w in (('front', y - 0.012), ('back', y + 0.012)):
        b.decal(side, fx0, fx1, h - 1.7, h - 1.25, c2, off=0.01, wall=w)
        b.decal(side, fx0, fx1, h - 0.75, h - 0.55, c2, off=0.01, wall=w)


def dish(b, cx, cy, z0, fx=0.0, fy=-1.0, r=0.42):
    """Satellite dish (parabola) on a short post, facing (fx, fy) and tilted up."""
    b.box(cx - 0.04, cy - 0.04, z0, cx + 0.04, cy + 0.04, z0 + 0.95, 'metal')
    e = math.radians(35)
    n = (fx * math.cos(e), fy * math.cos(e), math.sin(e))
    u = (-fy, fx, 0.0)
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
    c = (cx - fx * 0.05, cy - fy * 0.05, z0 + 1.0)       # back of the dish rests on the pole top
    ring = []
    for i in range(8):
        t = 2 * math.pi * i / 8
        ring.append(tuple(c[k] + r * (math.cos(t) * u[k] + math.sin(t) * v[k]) for k in range(3)))
    face_out(b, ring, 'ac_white', n)
    back = [(p[0] - n[0] * 0.02, p[1] - n[1] * 0.02, p[2] - n[2] * 0.02) for p in ring]
    face_out(b, back, 'metal', (-n[0], -n[1], -n[2]))


def jemuran(b, x0, x1, y, z0, rng, h=1.7):
    """Clothes line with colourful laundry (both sides visible)."""
    for x in (x0, x1):
        b.box(x - 0.03, y - 0.03, z0, x + 0.03, y + 0.03, z0 + h, 'metal')
    b.box(x0, y - 0.012, z0 + h - 0.08, x1, y + 0.012, z0 + h - 0.05, 'metal')
    cols = ['fabric_1', 'fabric_2', 'fabric_3', 'awning_white', 'sign_blue', 'awning_green']
    x = x0 + 0.2
    zt = z0 + h - 0.08
    while x < x1 - 0.55:
        w, hh = rng.uniform(0.35, 0.6), rng.uniform(0.45, 0.85)
        c = cols[rng.randrange(len(cols))]
        pts = [(x, y, zt - hh), (x + w, y, zt - hh), (x + w, y, zt), (x, y, zt)]
        face_out(b, [(p[0], p[1] - 0.006, p[2]) for p in pts], c, (0, -1, 0))
        face_out(b, [(p[0], p[1] + 0.006, p[2]) for p in pts], c, (0, 1, 0))
        x += w + 0.14


def solar_row(b, x0, x1, y0, z0, depth=1.0, lift=0.25, tilt=0.35):
    """Row of PV panels tilted towards the street on two wedge supports."""
    za, zb = z0 + lift, z0 + lift + tilt
    for xc in (x0 + 0.25, x1 - 0.25):
        wedge(b, xc - 0.04, xc + 0.04, y0 + 0.08, y0 + depth - 0.08, z0, za + tilt * 0.08 / depth, zb - tilt * 0.08 / depth, 'metal', top=False)
    top = [(x0, y0, za + 0.05), (x1, y0, za + 0.05), (x1, y0 + depth, zb + 0.05), (x0, y0 + depth, zb + 0.05)]
    b._slab(top, [(p[0], p[1], p[2] - 0.05) for p in top], C['solar'])
    n = max(2, int(round((x1 - x0) / 1.1)))
    for i in range(1, n):
        x = x0 + (x1 - x0) * i / n
        face_out(b, [(x - 0.025, y0, za + 0.065), (x + 0.025, y0, za + 0.065), (x + 0.025, y0 + depth, zb + 0.065),
                     (x - 0.025, y0 + depth, zb + 0.065)], 'metal', (0, 0, 1))
    b.top = max(b.top, zb + 0.05)


def blank_sign_faces(b, xs, y0, y1, z0, z1, inner, bar):
    """Decals on both faces of a projecting blade sign (x-thin box at xs +- 0.07)."""
    for side, w in (('left', xs - 0.07), ('right', xs + 0.07)):
        b.decal(side, y0 + 0.1, y1 - 0.1, z0 + 0.1, z1 - 0.1, inner, off=0.01, wall=w)
        h = z1 - z0
        b.decal(side, y0 + 0.22, y1 - 0.22, z0 + h * 0.55, z0 + h * 0.7, bar, off=0.02, wall=w)
        b.decal(side, y0 + 0.3, y1 - 0.3, z0 + h * 0.3, z0 + h * 0.42, bar, off=0.02, wall=w)


def atm_booth(b, x0, x1, y0, y1, band, door_side):
    """Small ATM room built against a shop front: white box, glass door, colour band + blank bars, flat lid."""
    h = 2.45
    b.box(x0, y0, 0.1, x1, y1, 0.1 + h, 'wall_white', skip=('bottom', 'back', 'top'))
    b.box(x0 - 0.04, y0 - 0.04, 0.1 + h, x1 + 0.04, y1, 0.1 + h + 0.1, band, skip=('bottom', 'back'))
    xc = (x0 + x1) / 2
    b.decal('front', x0 + 0.1, x1 - 0.1, 1.95, 2.4, band, off=0.02, wall=y0)
    b.decal('front', x0 + 0.3, x1 - 0.3, 2.1, 2.24, 'sign_white', off=0.03, wall=y0)
    cdoor(b, 'front', xc, 0.8, 1.75, wall=y0, frame='metal', leaf='glass', z0=0.1)
    b.decal('front', xc - 0.3, xc + 0.3, 0.9, 1.5, 'glass_light', off=0.065, wall=y0)   # machine seen inside
    # side window towards the shop door
    sd, xw = ('right', x1) if door_side > 0 else ('left', x0)
    b.decal(sd, y0 + 0.25, y1 - 0.25, 1.0, 1.9, 'glass', off=0.02, wall=xw)


def lpg_cage(b, x0, x1, y0, y1, z0=0.0, c='rail_green'):
    """Steel cage with 3 kg LPG 'melon' cylinders on two shelves (sold at every minimarket)."""
    h = 1.3
    b.box(x0, y0, z0, x1, y1, z0 + 0.08, 'metal')
    for x in (x0, x1 - 0.05):
        for y in (y0, y1 - 0.05):
            b.box(x, y, z0 + 0.08, x + 0.05, y + 0.05, z0 + h - 0.08, c, skip=('bottom', 'top'))
    b.box(x0, y0, z0 + 0.66, x1, y1, z0 + 0.7, c)
    b.box(x0 - 0.02, y0 - 0.02, z0 + h - 0.08, x1 + 0.02, y1 + 0.02, z0 + h, c)
    n = max(2, int((x1 - x0) / 0.36))
    for zs in (z0 + 0.08, z0 + 0.7):
        for i in range(n):
            lpg(b, x0 + (x1 - x0) * (i + 0.5) / n, (y0 + y1) / 2, zs)
    for i in range(1, 4):                                          # front bars
        x = x0 + (x1 - x0) * i / 4
        b.box(x - 0.015, y0 - 0.03, z0 + 0.08, x + 0.015, y0, z0 + h - 0.08, c, skip=('bottom', 'top', 'back'))


def gallon_rack(b, x0, x1, y0, y1, z0=0.0, empties=False):
    """Two-shelf rack of 19 l drinking-water gallons (blue bottles)."""
    for x in (x0, x1 - 0.05):
        for y in (y0, y1 - 0.05):
            b.box(x, y, z0, x + 0.05, y + 0.05, z0 + 1.1, 'metal')
    col = '#9cc3dc' if empties else '#4d8fd6'
    n = max(2, int((x1 - x0) / 0.34))
    for zs in (z0 + 0.1, z0 + 0.6):
        b.box(x0, y0, zs - 0.04, x1, y1, zs, 'metal')
        for i in range(n):
            gx = x0 + (x1 - x0) * (i + 0.5) / n
            b.cyl(gx, (y0 + y1) / 2, zs, zs + 0.38, 0.14, col, seg=6)
            b.box(gx - 0.04, (y0 + y1) / 2 - 0.04, zs + 0.38, gx + 0.04, (y0 + y1) / 2 + 0.04, zs + 0.45, 'sign_blue')


def pylon(b, px, y0, y1, board, emblem, zb=(1.3, 3.4), w=1.2, z0=0.1):
    """Free-standing sign on two legs: blank colour board with an emblem block and lettering bars, both faces."""
    for dx in (-w * 0.33, w * 0.33):
        b.box(px + dx - 0.06, y0 + 0.04, z0, px + dx + 0.06, y1 - 0.04, zb[0], 'metal')
    b.box(px - w / 2, y0, zb[0], px + w / 2, y1, zb[1], board, skip=())
    e1, e2 = emblem
    h = zb[1] - zb[0]
    for side, wl in (('front', y0), ('back', y1)):
        b.decal(side, px - w * 0.36, px + w * 0.36, zb[1] - h * 0.5, zb[1] - 0.12, e1, off=0.01, wall=wl)
        b.decal(side, px - w * 0.36, px + w * 0.36, zb[1] - h * 0.36, zb[1] - h * 0.24, e2, off=0.02, wall=wl)
        b.decal(side, px - w * 0.36, px + w * 0.36, zb[0] + h * 0.22, zb[0] + h * 0.36, 'sign_white', off=0.01, wall=wl)
        b.decal(side, px - w * 0.26, px + w * 0.26, zb[0] + 0.12, zb[0] + h * 0.14, 'sign_white', off=0.01, wall=wl)


# =========================================================================================== builders
def minimarket(b, v, rng):
    W, D = b.W, b.D
    roof, ap, wall = v['roof'], v['apron'], v['wall']
    H = {'flat': 3.7, 'gable': 3.3, 'hip': 3.3}[roof]
    ins = 0.1 if roof == 'flat' else 0.35
    xL, xR, yB = -W / 2 + ins, W / 2 - ins, D - 1.0
    fz0, fz1 = v['fz']
    fx0, fx1 = -W / 2 + 0.02, W / 2 - 0.02
    fy0, fy1 = ap - v['fout'], ap + 0.25
    apron(b, -W / 2, W / 2, 0, ap, v.get('lines_x'), v['bays'], stops=v.get('stops'))
    walls(b, xL, ap, xR, yB, 0, H, wall)
    b.panel('back', xL, xR, 0, 0.4, 'plinth', off=0.02, depth=0.02, wall=yB)
    fascia(b, fx0, fx1, fy0, fy1, fz0, fz1, v['fascia'], v['stripes'])
    front = v['front']
    dw, du = 1.9, v['door']
    sx0, sx1 = xL + 0.3, xR - 0.3
    lc1, lc2 = v['logo']
    hg = fz1 - fz0
    if v['emblem'] == 'fascia':
        # blank emblem block at the fascia end away from the door (no text, no real logo)
        lw = hg * 1.25
        lu = fx0 + 0.4 if du > 0 else fx1 - 0.4 - lw
        b.decal('front', lu, lu + lw, fz0 + 0.12, fz1 - 0.12, lc1, off=0.035, wall=fy0)
        b.decal('front', lu + 0.17, lu + lw - 0.17, fz0 + 0.3, fz1 - 0.3, lc2, off=0.05, wall=fy0)
    else:
        # emblem lives on a pylon at the apron corner; the fascia only carries blank lettering bars
        b.decal('front', fx0 + 1.2, fx1 - 1.2, fz0 + hg * 0.45, fz0 + hg * 0.68, 'sign_white', off=0.035, wall=fy0)
        pylon(b, -W / 2 + 0.72, 0.25, 0.45, v['fascia'], (lc1, lc2), zb=(1.3, 3.2), w=1.1)
    if front == 'atm':
        # ATM room at the end away from the door, under the fascia
        if du > 0:
            atm_booth(b, xL + 0.05, xL + 1.45, ap - 1.0, ap, lc1, 1)
            sx0 = xL + 1.55
        else:
            atm_booth(b, xR - 1.45, xR - 0.05, ap - 1.0, ap, lc1, -1)
            sx1 = xR - 1.55
    # full-width glass front with an automatic sliding door
    storefront(b, sx0, sx1, 0.1, fz0 - 0.1, ap, door=(du, dw, 2.3), frame='metal', bay=1.5, kick=0.35,
               kick_col='metal', auto=True, shelves=(0.95, 1.5, 2.05))
    # props under the fascia; free spans left and right of the door (0.25 m clear of the door leaf)
    L0, L1 = sx0 + 0.15, du - dw / 2 - 0.25
    R0, R1 = du + dw / 2 + 0.25, sx1 - 0.15
    band = v['fascia'] if v['fascia'] != 'sign_white' else lc1
    if front == 'atm':
        trash_bin(b, L1 - 0.25, ap - 0.3, 0.1, 'awning_green')
        freezer(b, L1 - 1.2, ap - 0.42, 0.1, band)
        bench(b, R0 + 0.3, R0 + 1.8, ap - 0.6, ap - 0.2, 0.1)
    elif front == 'terrace':
        freezer(b, L1 - 0.5, ap - 0.42, 0.1, band)
        freezer(b, L1 - 1.6, ap - 0.42, 0.1, band)
        bench(b, L0 + 0.2, L0 + 1.7, ap - 0.6, ap - 0.2, 0.1)
        trash_bin(b, R0 + 0.25, ap - 0.3, 0.1, 'awning_green')
        # hang-out terrace on the part of the apron without parking bays: parasols 0.2 m apart
        tx0 = v['lines_x'][1] + 0.2
        for tx in (tx0 + 0.95, tx0 + 2.65):
            if tx + 0.8 <= W / 2:
                table_set(b, tx, ap - 2.0, 0.1, top='trim_white', seat='sign_red', axis='y')
                parasol(b, tx, ap - 2.0, 0.1, v['fascia'], 'awning_white', r=0.75)
    else:
        lpg_cage(b, L0, L0 + 1.1, ap - 0.7, ap - 0.12, 0.1)
        trash_bin(b, R0 + 0.25, ap - 0.3, 0.1, 'awning_green')
        gallon_rack(b, R0 + 0.8, R0 + 1.85, ap - 0.55, ap - 0.1, 0.1)
        b.plant_pot(R1 - 0.3, ap - 0.4, 0.1, s=0.75)
    # roof
    if roof == 'flat':
        hq(b, xL, ap, xR, yB, H, v['roofc'])
        parapet(b, xL, xR, fy1, yB, H, 0.45, wall, front=False)
        n = 3 if W >= 9 else 2
        for i in range(n):
            roof_ac(b, xL + 1.0 + i * 1.05, yB - 0.6, H, face='back')
        tank(b, xR - 1.0, yB - 1.2, H, 'tank_blue')
        hatch(b, xL + 1.3, fy1 + 2.2, H)
        # small rooftop store room (gudang) with a steel door, two skylight domes
        sx = 0.9 if rng.random() < 0.5 else -3.0
        b.box(sx, fy1 + 2.8, H, sx + 2.1, fy1 + 4.4, H + 0.95, 'wall_grey')
        b.box(sx - 0.08, fy1 + 2.72, H + 0.95, sx + 2.18, fy1 + 4.48, H + 1.03, 'concrete_dark')
        cdoor(b, 'front', sx + 0.6, 0.7, 0.8, wall=fy1 + 2.8, frame='metal', leaf='shutter_dark', z0=H)
        for (kx, ky) in ((-0.9 if sx > 0 else 1.6, fy1 + 1.4), (-0.9 if sx > 0 else 1.6, fy1 + 5.3)):
            b.box(kx - 0.5, ky - 0.5, H, kx + 0.5, ky + 0.5, H + 0.12, 'concrete')
            b.box(kx - 0.4, ky - 0.4, H + 0.12, kx + 0.4, ky + 0.4, H + 0.3, 'glass_light')
        # cable tray from the condensers to the front
        b.box(xL + 0.6, fy1 + 0.2, H, xL + 0.8, yB - 0.8, H + 0.1, 'metal')
    elif roof == 'gable':
        rise = 0.95
        g = gable_roof(b, xL, xR, fy1 + 0.3, yB, H, rise, v['roofc'], gable=wall, over=0.3, over_end=0.3, ridge='y')
        roof_lines(b, g, '#3d5873', ribs=1.0, cap='rail_white')
        # translucent skylight sheets running down both slopes, two turbine ventilators on the ridge
        for l0 in (fy1 + 2.4, yB - 2.6):
            for a0, a1 in ((xL - 0.1, -0.35), (0.35, xR + 0.1)):
                on_slope(b, g, a0, a1, l0, l0 + 0.7, '#d4e3ea', eps=0.035)
        for yy in (fy1 + 4.3, yB - 4.2):
            turbine(b, 0.0, yy, H + rise + 0.12)
        b.decal('back', -0.5, 0.5, H + 0.25, H + 0.6, 'shutter_dark', off=0.02, wall=yB)
    else:
        rise = 1.32
        b.roof_hip(xL, xR, ap, yB, H, rise, v['roofc'], over=0.3)
        hip_lines(b, xL, xR, ap, yB, H, rise, '#5a221e', over=0.3, courses=3, width=0.06, cap='#4e1f1b')
        # solar water heater on the right-hand slope: collector sheet + white tank strapped above it
        X1, m = xR + 0.3, min(xR - xL, yB - ap) / 2 + 0.3
        zr = lambda x: H + 0.12 + rise * (X1 - x) / m
        ym = (ap + yB) / 2 + 0.4
        ca, cb = X1 - 0.5, X1 - 1.7                   # collector from 0.5 to 1.7 m up the slope
        face_out(b, [(ca, ym - 1.0, zr(ca) + 0.05), (cb, ym - 1.0, zr(cb) + 0.05), (cb, ym + 1.0, zr(cb) + 0.05),
                     (ca, ym + 1.0, zr(ca) + 0.05)], C['solar'], (0, 0, 1))
        for k in (-0.34, 0.34):
            face_out(b, [(ca, ym + k - 0.03, zr(ca) + 0.06), (cb, ym + k - 0.03, zr(cb) + 0.06),
                         (cb, ym + k + 0.03, zr(cb) + 0.06), (ca, ym + k + 0.03, zr(ca) + 0.06)], 'metal', (0, 0, 1))
        tx = cb - 0.25
        b.box(tx - 0.22, ym - 1.05, zr(tx + 0.22) - 0.03, tx + 0.22, ym + 1.05, zr(tx + 0.22) + 0.42, 'tank_white')
    # back side (different for each roof type so a row of them is not a repeat)
    sb = 1 if du <= 0 else -1                      # service side = away from the ATM / terrace end
    if roof == 'flat':
        # stock delivery: rolling shutter + service door, condensers high up, bins
        su = sb * (W / 2 - 2.0)
        b.shutter('back', su - 1.0, su + 1.0, 0.0, 2.5, color='shutter', wall=yB)
        cdoor(b, 'back', su - sb * 1.9, 0.9, 2.1, wall=yB, frame='trim_white', leaf='shutter_dark')
        for i in range(2):
            b.ac_unit('back', -sb * (0.6 + i * 1.1), 2.5, wall=yB)
        pipe(b, 'back', -sb * (W / 2 - 0.35), H + 0.45, yB)
        trash_bin(b, -sb * 1.2, yB + 0.45, 0, 'awning_orange')
        trash_bin(b, -sb * 1.8, yB + 0.45, 0, 'awning_blue')
        crates(b, su - sb * 3.0, yB + 0.4, 2, rng, cols=(C['card'], '#b8925e'))
    elif roof == 'gable':
        bd = sb * (xR - 1.1)
        cdoor(b, 'back', bd, 0.95, 2.1, wall=yB, frame='trim_white', leaf='shutter_dark')
        wu = bd - sb * 1.6
        win(b, 'back', wu, 1.5, 1.0, 0.8, wall=yB, frame='trim_white', glass='glass', bars=2)
        for i in range(2):
            b.ac_unit('back', -sb * (0.8 + i * 1.1), 2.2, wall=yB)
        pipe(b, 'back', -sb * (xR - 0.25), H, yB)
        cx = -sb * 0.2
        crates(b, cx, yB + 0.5, 3, rng)
        crates(b, cx - sb * 0.6, yB + 0.5, 2, rng)
        trash_bin(b, cx + sb * 0.7, yB + 0.5, 0, 'awning_orange')
        b.water_tank(-sb * (xR - 1.0), yB + 0.5, 0, 'tank_orange', r=0.45, h=0.9, stand=1.7)
    else:
        # small back yard: door, frosted window, condenser on a ground plinth, cardboard bales, bin
        bd = sb * (xR - 1.0)
        cdoor(b, 'back', bd, 0.95, 2.1, wall=yB, frame='trim_white', leaf='door_dark')
        win(b, 'back', bd - sb * 1.4, 1.6, 0.7, 0.6, wall=yB, frame='trim_white', glass=C['frost'], bars=1)
        au = -sb * 0.6
        b.box(au - 0.48, yB, 0, au + 0.48, yB + 0.45, 0.25, 'concrete')
        b.ac_unit('back', au, 0.25, wall=yB)
        b.ac_unit('back', -sb * 1.7, 2.2, wall=yB)
        pipe(b, 'back', -sb * (xR - 0.25), H, yB)
        for k in range(3):
            b.box(bd - sb * 2.2 - 0.4, yB + 0.15, 0.18 * k, bd - sb * 2.2 + 0.4, yB + 0.75, 0.18 * (k + 1),
                  C['card'] if k % 2 == 0 else '#b8925e', skip=('bottom',) if k == 2 else ('bottom', 'top'))
        trash_bin(b, -sb * (xR - 0.7), yB + 0.45, 0, 'awning_orange')


def apotek(b, v, rng):
    W, D = b.W, b.D
    yF, H = 1.7, 3.4
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 1.1
    wall, fc = v['wall'], v['fascia']
    sgn = 1 if rng.random() < 0.5 else -1          # side of the projecting sign
    b.box(-W / 2 + 0.02, 0.25, 0, W / 2 - 0.02, yF, 0.18, 'tile_floor', skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, H, wall)
    fy0, fy1 = yF - 0.3, yF + 0.2
    fz0, fz1 = 2.95, 4.3
    g = gable_roof(b, xL, xR, fy1 + 0.3, yB, H, 1.2, v['roofc'], gable=wall, over=0.3, over_end=0.06, ridge='x')
    roof_lines(b, g, '#2b5540', courses=4, cap='#2b5540')
    fascia(b, xL - 0.05, xR + 0.05, fy0, fy1, fz0, fz1, fc, [(4.14, 4.22, 'sign_white'), (3.03, 3.09, 'sign_white')])
    # blank lettering bars on the fascia (away from the sign)
    bx0, bx1 = (xL + 0.5, xR - 1.1) if sgn > 0 else (xL + 1.1, xR - 0.5)
    b.decal('front', bx0, bx1, 3.62, 3.9, 'sign_white', off=0.03, wall=fy0)
    b.decal('front', bx0 + 0.6, bx1 - 0.6, 3.27, 3.45, 'sign_white', off=0.03, wall=fy0)
    # door away from the sign, small flat canopy over it
    du = (xL + 1.6) if sgn > 0 else (xR - 1.6)
    b.box(du - 1.2, yF - 1.15, 2.74, du + 1.2, yF, 2.86, 'trim_white', skip=())
    b.decal('front', du - 1.2, du + 1.2, 2.76, 2.84, fc, off=0.015, wall=yF - 1.15)
    storefront(b, xL + 0.3, xR - 0.3, 0.18, 2.62, yF, door=(du, 1.1, 2.2), frame='trim_white', glass='glass_light',
               leaf='glass', bay=1.3, kick=0.55, auto=False, shelves=(1.2, 1.7),
               shelf_cols=['#f2efe4', '#9fd0b4', '#f2efe4', '#e8c35a'])
    # projecting blank sign (square light box, no cross)
    xs = xR - 0.3 if sgn > 0 else xL + 0.3
    sy0, sy1, sz0, sz1 = fy0 - 0.85, fy0 + 0.05, 3.05, 3.95
    b.box(xs - 0.07, sy0, sz0, xs + 0.07, sy1, sz1, fc, skip=())
    blank_sign_faces(b, xs, sy0, sy1, sz0, sz1, 'sign_white', fc)
    # terrace props
    bx = du + 0.8 if sgn > 0 else du - 2.1
    bench(b, bx, bx + 1.3, yF - 0.55, yF - 0.18, 0.18)
    b.plant_pot(du - 0.85 * sgn, yF - 0.4, 0.18, s=0.8)
    b.plant_pot(xs, 0.6, 0.18, s=0.7)
    # back
    bd = xR - 1.0 if sgn > 0 else xL + 1.0
    cdoor(b, 'back', bd, 0.9, 2.1, wall=yB)
    win(b, 'back', -bd * 0.2, 1.5, 1.2, 0.9, wall=yB, frame='trim_white', glass='glass', bars=2)
    win(b, 'back', -bd * 0.66, 1.7, 0.55, 0.6, wall=yB, frame='trim_white', glass=C['frost'], bars=1)
    au = bd * 0.44                                  # between the service door and the big window
    b.ac_unit('back', au, 1.05, wall=yB)
    b.ac_unit('back', au, 2.25, wall=yB)
    b.box(au - 0.34, yB + 0.05, 1.0, au - 0.3, yB + 0.33, 1.05, 'metal')
    b.box(au + 0.3, yB + 0.05, 1.0, au + 0.34, yB + 0.33, 1.05, 'metal')
    crates(b, -bd * 0.2, yB + 0.4, 2, rng, cols=(C['card'], '#b8925e'))
    b.water_tank(-bd * 0.95, yB + 0.55, 0, v['tank'], r=0.42, h=0.85, stand=1.6)


def klinik(b, v, rng):
    W, D = b.W, b.D
    ap, H1, H2 = 3.3, 3.4, 6.7
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 0.9
    wall, acc, fc = v['wall'], v['accent'], v['fascia']
    sgn = 1 if rng.random() < 0.5 else -1
    apron(b, -W / 2, W / 2, 0, ap, None, 3, stops='concrete_dark')
    walls(b, xL, ap, xR, yB, 0, H2, wall)
    # accent colour on the upper floor sides (wraps the corner)
    hq(b, xL, ap, xR, yB, H2, v['roofc'])
    parapet(b, xL, xR, ap, yB, H2, 0.5, wall)
    # fascia band between the floors
    fascia(b, xL - 0.05, xR + 0.05, ap - 0.35, ap + 0.02, 3.35, 4.05, fc, [(3.4, 3.46, 'sign_white')])
    b.decal('front', -2.2, 2.2, 3.62, 3.9, 'sign_white', off=0.03, wall=ap - 0.35)
    # drop-off canopy on two columns
    b.box(-2.4, 0.6, 3.02, 2.4, ap, 3.3, 'trim_white', skip=())
    b.decal('front', -2.4, 2.4, 3.05, 3.26, fc, off=0.015, wall=0.6)
    for x in (-1.4, 1.4):                          # on the bay lines, not in the bay mouths
        b.box(x - 0.12, 0.72, 0.1, x + 0.12, 0.96, 3.02, 'column')
    # ground floor: entrance + two windows with frosted lower panes
    storefront(b, -1.6, 1.6, 0.1, 2.9, ap, door=(0.0, 1.8, 2.3), frame='metal', bay=1.2, kick=0.35, auto=True)
    for u in (-3.05, 3.05):
        win(b, 'front', u, 0.9, 1.5, 1.7, wall=ap, frame='trim_white', glass='glass_light', bars=2)
        b.decal('front', u - 0.68, u + 0.68, 0.97, 1.5, C['frost'], off=0.06, wall=ap)
    # upper floor: glass band shaded by vertical fins, blade sign
    gx0, gx1 = (xL + 0.4, xR - 1.0) if sgn > 0 else (xL + 1.0, xR - 0.4)
    b.panel('front', gx0, gx1, 4.45, 6.1, 'glass', off=0.02, depth=0.02, wall=ap)
    b.panel('front', gx0 - 0.1, gx1 + 0.1, 4.3, 4.45, acc, off=0.12, depth=0.12, wall=ap)
    b.panel('front', gx0 - 0.1, gx1 + 0.1, 6.1, 6.3, acc, off=0.12, depth=0.12, wall=ap)
    n = int(round((gx1 - gx0) / 0.85))
    for i in range(n + 1):
        u = gx0 + (gx1 - gx0) * i / n
        b.panel('front', u - 0.05, u + 0.05, 4.45, 6.1, 'trim_white', off=0.4, depth=0.38, wall=ap)
    xs = xR - 0.45 if sgn > 0 else xL + 0.45
    b.box(xs - 0.07, ap - 1.0, 4.3, xs + 0.07, ap + 0.02, 6.3, fc, skip=())
    blank_sign_faces(b, xs, ap - 1.0, ap, 4.3, 6.3, 'sign_white', fc)
    # roof: stair bulkhead with door, water tank, condensers, dish
    sx0, sx1 = (xL + 0.3, xL + 2.6) if sgn > 0 else (xR - 2.6, xR - 0.3)
    b.box(sx0, yB - 3.3, H2, sx1, yB - 0.3, H2 + 2.4, acc)
    cdoor(b, 'front', (sx0 + sx1) / 2, 0.85, 2.0, wall=yB - 3.3, frame='trim_white', leaf='door_dark', z0=H2)
    b.water_tank(sgn * (W / 2 - 1.1), yB - 1.1, H2, 'tank_blue', r=0.5, h=1.0, stand=0.8)
    b.water_tank(sgn * (W / 2 - 2.4), yB - 1.1, H2, 'tank_blue', r=0.5, h=1.0, stand=0.8)
    for i in range(3):
        roof_ac(b, sgn * (0.2 + i * 1.0) - sgn * 1.2, ap + 0.65, H2, face='front')
    # light steel canopy (zinc) on posts over the service area of the roof
    cx0, cx1 = (sx1 + 0.5, xR - 0.35) if sgn > 0 else (xL + 0.35, sx0 - 0.5)
    cy0, cy1 = ap + 1.6, ap + 4.4
    zc = lambda y: H2 + 2.18 + 0.24 * (y - cy0 + 0.2) / (cy1 - cy0 + 0.4)     # canopy underside at y
    for x in (cx0 + 0.1, cx1 - 0.1):
        for y in (cy0 + 0.1, cy1 - 0.1):
            b.box(x - 0.05, y - 0.05, H2, x + 0.05, y + 0.05, zc(y) + 0.02, 'metal')
    top = [(cx0 - 0.1, cy0 - 0.2, H2 + 2.24), (cx1 + 0.1, cy0 - 0.2, H2 + 2.24), (cx1 + 0.1, cy1 + 0.2, H2 + 2.48), (cx0 - 0.1, cy1 + 0.2, H2 + 2.48)]
    b._slab(top, [(p[0], p[1], p[2] - 0.06) for p in top], 'roof_blue')
    n = int((cx1 - cx0) / 0.7)
    for i in range(1, n + 1):
        x = cx0 + (cx1 - cx0) * i / (n + 1)
        face_out(b, [(x - 0.025, cy0 - 0.18, H2 + 2.26), (x + 0.025, cy0 - 0.18, H2 + 2.26), (x + 0.025, cy1 + 0.18, H2 + 2.5),
                     (x - 0.025, cy1 + 0.18, H2 + 2.5)], '#3d5873', (0, 0, 1))
    jemuran(b, cx0 + 0.3, cx1 - 0.3, (cy0 + cy1) / 2, H2, rng, h=1.6)
    dish(b, (sx0 + sx1) / 2, yB - 1.8, H2 + 2.4, fx=0.0, fy=-1.0, r=0.35)
    # back side: windows on both floors, service door, condensers, downpipe
    for u in (-2.6, 0.0, 2.6):
        win(b, 'back', u, 4.4, 1.3, 1.3, wall=yB, frame='trim_white', glass='glass', bars=2)
    win(b, 'back', 2.6 * sgn, 1.1, 1.3, 1.2, wall=yB, frame='trim_white', glass='glass', bars=2)
    win(b, 'back', 0.0, 1.5, 0.8, 0.7, wall=yB, frame='trim_white', glass=C['frost'], bars=1)
    cdoor(b, 'back', -2.6 * sgn, 0.95, 2.1, wall=yB)
    b.ac_unit('back', 1.3, 3.8, wall=yB)
    b.ac_unit('back', -1.3, 3.8, wall=yB)
    b.ac_unit('back', 1.3 * sgn, 2.3, wall=yB)
    pipe(b, 'back', -xL - 0.25 if sgn > 0 else xL + 0.25, H2 + 0.5, yB)
    trash_bin(b, -2.6 * sgn + 1.0 * sgn, yB + 0.45, 0, 'awning_yellow')


def bakery(b, v, rng):
    W, D = b.W, b.D
    yF, H = 2.3, 3.1
    xL, xR, yB = -W / 2 + 0.35, W / 2 - 0.35, D - 0.9
    wall = v['wall']
    sgn = 1 if rng.random() < 0.5 else -1          # door side
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.15, v['floor'], skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, H, wall)
    b.panel('front', xL, xR, 0.15, 0.6, C['brick'], off=0.02, depth=0.02, wall=yF)
    for side, w in (('left', xL), ('right', xR)):
        b.panel(side, yF, yB, 0.0, 0.6, C['brick'], off=0.02, depth=0.02, wall=w)
    g = gable_roof(b, xL, xR, yF, yB, H, 1.45, v['roofc'], gable=wall, over=0.3, over_end=0.35, ridge='y')
    roof_lines(b, g, '#9c4325', courses=4, cap='#8a3a20')
    # shop windows in wooden frames + glazed door
    du = sgn * (xR - 1.2)
    storefront(b, xL + 0.25, xR - 0.25, 0.6, 2.5, yF, door=None, frame='frame_brown', glass='glass_light', bay=1.2,
               kick=0.0, shelves=(1.0, 1.45), shelf_cols=['#dca25e', '#c9803f', '#e8c890'])
    # the door cuts through the sill: draw it over the window band
    b.panel('front', du - 0.62, du + 0.62, 0.15, 2.55, 'frame_brown', off=0.075, depth=0.03, wall=yF)
    b.decal('front', du - 0.5, du + 0.5, 0.15, 2.4, 'glass', off=0.08, wall=yF)
    b.decal('front', du - 0.5, du + 0.5, 1.0, 1.1, 'frame_brown', off=0.085, wall=yF)
    # striped awning and a blank sign board on the gable
    a1, a2 = v['awning']
    b.awning('front', xL + 0.1, xR - 0.1, 2.85, out=1.3, drop=0.38, color=a1, stripe=a2, wall=yF)
    b.sign('front', -1.3, 1.3, 3.28, 3.85, v['sign'], text_color='sign_white', wall=yF)
    b.decal('front', -0.35, 0.35, 4.05, 4.3, C['wood_dark'], off=0.02, wall=yF)     # attic vent
    # outdoor seats on the terrace (away from the door)
    for k in range(2):
        tx = -sgn * (xR - 0.95 - k * 1.85)
        table_set(b, tx, 1.05, 0.15, top='trim_white', seat=C['wood'], axis='x')
    # A-frame menu board and planters
    mx = du - sgn * 0.95
    wedge(b, mx - 0.3, mx + 0.3, 0.55, 0.75, 0.15, 1.05, 1.05, C['steel'])
    b.plant_pot(-W / 2 + 0.35, 0.35, 0.15, s=0.75)
    b.plant_pot(W / 2 - 0.35, 0.35, 0.15, s=0.75)
    # oven chimney on the back slope
    cxh = -sgn * 1.5
    zr = slope_z(g, cxh + 0.25)
    b.box(cxh - 0.22, yB - 1.6, H, cxh + 0.22, yB - 1.16, zr + 0.55, C['brick'])
    b.box(cxh - 0.28, yB - 1.66, zr + 0.55, cxh + 0.28, yB - 1.1, zr + 0.62, 'concrete_dark')
    # back: kitchen door, window, exhaust fan, gas cylinders, flour sacks
    bd = sgn * (xR - 1.0)
    cdoor(b, 'back', bd, 0.9, 2.1, wall=yB, frame='frame_brown', leaf='door_wood')
    win(b, 'back', -bd * 0.3, 1.2, 1.2, 1.0, wall=yB, frame='frame_brown', glass='glass', bars=2)
    b.panel('back', -bd * 0.85 - 0.3, -bd * 0.85 + 0.3, 1.9, 2.5, 'metal', off=0.06, depth=0.06, wall=yB)
    b.decal('back', -bd * 0.85 - 0.22, -bd * 0.85 + 0.22, 1.98, 2.42, 'shutter_dark', off=0.065, wall=yB)
    b.decal('back', -0.3, 0.3, H + 0.3, H + 0.6, C['wood_dark'], off=0.02, wall=yB)
    for i in range(3):
        lpg(b, bd - sgn * (0.9 + i * 0.36), yB + 0.35)
    for i in range(2):
        b.box(-bd * 0.3 - 0.35 + i * 0.7 - 0.28, yB + 0.2, 0, -bd * 0.3 - 0.35 + i * 0.7 + 0.28, yB + 0.6, 0.32, '#efe6d2')


def hp(b, v, rng):
    W, D = b.W, b.D
    yF, zlo, zhi = 1.3, 3.2, 3.7
    xL, xR, yB = -W / 2 + 0.25, W / 2 - 0.25, D - 1.3
    wall, fc, acc = v['wall'], v['fascia'], v['accent']
    sgn = 1 if rng.random() < 0.5 else -1
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.15, 'concrete', skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, zlo, wall)
    zt = shed_roof(b, xL, xR, yF, yB, zhi, zlo, v['roofc'], fill=wall, over=0.25, over_side=0.22)
    fy0, fy1 = yF - 0.6, yF + 0.3
    ya, yb = fy1 + 0.02, yB + 0.23
    n = int((xR - xL + 0.4) / 0.3)                 # close-pitched ribs so the sheet reads as corrugated zinc
    for i in range(n + 1):
        x = xL - 0.2 + (xR - xL + 0.4) * i / n
        face_out(b, [(x - 0.025, ya, zt(ya) + 0.02), (x + 0.025, ya, zt(ya) + 0.02), (x + 0.025, yb, zt(yb) + 0.02),
                     (x - 0.025, yb, zt(yb) + 0.02)], v['ribs'], (0, 0, 1))
    on_band = [(fy1 + 1.8, fy1 + 2.5), (yB - 2.2, yB - 1.5)]
    for (y0s, y1s) in on_band:
        face_out(b, [(xL + 0.6, y0s, zt(y0s) + 0.03), (xL + 1.6, y0s, zt(y0s) + 0.03), (xL + 1.6, y1s, zt(y1s) + 0.03),
                     (xL + 0.6, y1s, zt(y1s) + 0.03)], '#d4e3ea', (0, 0, 1))
    fz0, fz1 = 2.8, 4.55
    fx0, fx1 = -W / 2 + 0.02, W / 2 - 0.02
    fascia(b, fx0, fx1, fy0, fy1, fz0, fz1, fc, [(fz0, fz0 + 0.2, acc), (fz1 - 0.1, fz1, acc)])
    # phone icon on a white tile + lettering bars
    ic = fx0 + 0.3 if sgn > 0 else fx1 - 1.5
    b.decal('front', ic, ic + 1.2, 3.1, 4.33, 'sign_white', off=0.03, wall=fy0)
    b.decal('front', ic + 0.34, ic + 0.86, 3.2, 4.22, 'sign_text', off=0.04, wall=fy0)
    b.decal('front', ic + 0.4, ic + 0.8, 3.36, 4.1, 'glass_light', off=0.05, wall=fy0)
    lx0, lx1 = (ic + 1.5, fx1 - 0.3) if sgn > 0 else (fx0 + 0.3, ic - 0.3)
    b.decal('front', lx0, lx1, 3.75, 4.2, 'sign_white', off=0.03, wall=fy0)
    b.decal('front', lx0 + 0.3, lx1 - 0.6, 3.25, 3.55, acc, off=0.03, wall=fy0)
    # glass front with display shelves, glazed door
    du = sgn * -0.9
    storefront(b, xL + 0.2, xR - 0.2, 0.15, 2.7, yF, door=(du, 1.1, 2.2), frame='frame_black', glass='glass_light',
               bay=1.1, kick=0.75, kick_col='sign_white', auto=False, shelves=(1.35, 1.85),
               shelf_cols=['#f2efe4', fc, acc, '#7fa8d9'])
    # umbul-umbul flags at the front corners
    flag(b, -W / 2 + 0.2, 0.2, 4.4, fc, acc, sgn=1)
    flag(b, W / 2 - 0.2, 0.2, 4.4, acc, fc, sgn=-1)
    # small outdoor showcase table next to the door
    sx = du - sgn * 1.25
    b.box(sx - 0.5, yF - 0.75, 0.15, sx + 0.5, yF - 0.25, 0.95, 'glass_light')
    b.box(sx - 0.53, yF - 0.78, 0.95, sx + 0.53, yF - 0.22, 1.0, 'frame_black')
    # back: white tank on a masonry plinth, door, window, condenser between door and window
    bd = sgn * (xR - 0.9)
    cdoor(b, 'back', bd, 0.9, 2.1, wall=yB)
    win(b, 'back', -bd * 0.15, 1.4, 1.0, 0.8, wall=yB, frame='trim_white', glass='glass', bars=2)
    b.ac_unit('back', bd * 0.42, 2.3, wall=yB)
    tx, ty = -sgn * (xR - 0.6), yB + 0.7
    b.box(tx - 0.55, ty - 0.55, 0, tx + 0.55, ty + 0.55, 1.2, 'concrete_dark', skip=('bottom', 'top'))
    b.box(tx - 0.6, ty - 0.6, 1.2, tx + 0.6, ty + 0.6, 1.28, 'concrete')
    tank(b, tx, ty, 1.28, 'tank_white', r=0.45, h=0.85)
    b.box(bd - sgn * 1.0 - 0.3, yB + 0.15, 0, bd - sgn * 1.0 + 0.3, yB + 0.55, 0.45, C['card'])


def cafe2(b, v, rng):
    W, D = b.W, b.D
    yF, H1, H2 = 2.4, 3.4, 6.6
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 0.9
    yU = yF + 3.0
    wall, up = v['wall'], v['upper']
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.12, v['deck'], skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, H1, wall)
    hq(b, xL, yF, xR, yU, H1, v['deck'])
    # slab edge = sign band with blank lettering
    b.panel('front', xL - 0.05, xR + 0.05, 2.95, H1 + 0.12, C['steel'], off=0.12, depth=0.12, wall=yF)
    b.decal('front', -1.6, 1.6, 3.12, 3.38, C['wood'], off=0.14, wall=yF)
    # flat steel canopy over the ground-floor glass
    b.box(xL + 0.2, yF - 1.2, 2.83, xR - 0.2, yF, 2.95, C['steel'], skip=())
    storefront(b, xL + 0.3, xR - 0.3, 0.12, 2.75, yF, door=(0.0, 1.0, 2.2), frame=C['steel'], glass='glass_light',
               bay=0.9, kick=0.3, auto=False, shelves=(1.1,), shelf_cols=['#e8c890'])
    b.decal('front', xL + 0.3, xR - 0.3, 2.2, 2.26, C['steel'], off=0.06, wall=yF)
    # street terrace: two parasol tables
    for sg in (-1, 1):
        cx = sg * (W / 4 + 0.35)
        table_set(b, cx, 1.0, 0.12, top='trim_white', seat=C['steel'], axis='x')
        parasol(b, cx, 1.0, 0.12, 'awning_green' if sg < 0 else 'awning_orange', 'awning_white', r=0.92)
    # upper storey (set back behind the roof terrace)
    walls(b, xL, yU, xR, yB, H1, H2, up)
    hq(b, xL, yU, xR, yB, H2, v['roofc'])
    parapet(b, xL, xR, yU, yB, H2, 0.4, up)
    storefront(b, xL + 0.65, xR - 0.65, H1, H1 + 2.5, yU, door=(0.0, 1.6, 2.2), frame=C['steel'], glass='glass',
               bay=1.2, kick=0.1, auto=False)
    b.panel('front', xL, xL + 0.6, H1, H2, C['wood'], off=0.04, depth=0.04, wall=yU)
    b.panel('front', xR - 0.6, xR, H1, H2, C['wood'], off=0.04, depth=0.04, wall=yU)
    b.panel('front', xL + 0.6, xR - 0.6, H1 + 2.62, H2, C['wood'], off=0.04, depth=0.04, wall=yU)
    # roof terrace: glass balustrade, side planters, pergola, tables
    b.box(xL + 0.1, yF + 0.02, H1, xR - 0.1, yF + 0.06, H1 + 1.0, 'glass_light')
    b.box(xL + 0.05, yF, H1 + 1.0, xR - 0.05, yF + 0.08, H1 + 1.06, C['steel'])
    for x in (xL, xR - 0.45):
        b.box(x, yF + 0.1, H1, x + 0.45, yU, H1 + 0.5, 'concrete')
        b.box(x + 0.05, yF + 0.15, H1 + 0.5, x + 0.4, yU - 0.05, H1 + 0.75, 'plant')
    for x in (xL + 0.75, xR - 0.75):
        b.box(x - 0.07, yF + 0.3, H1, x + 0.07, yF + 0.44, H1 + 2.6, C['wood_dark'])
        b.box(x - 0.07, yF + 0.3, H1 + 2.6, x + 0.07, yU, H1 + 2.76, C['wood_dark'])
    for k in range(6):
        y = yF + 0.35 + k * (yU - yF - 0.5) / 5
        b.box(xL + 0.5, y - 0.04, H1 + 2.76, xR - 0.5, y + 0.04, H1 + 2.86, C['wood'])
    for sg in (-1, 1):
        table_set(b, sg * 1.45, yF + 1.55, H1, top='trim_white', seat=C['wood'], axis='x')
    # upper roof
    roof_ac(b, xL + 1.1, yB - 0.6, H2, face='back')
    roof_ac(b, xL + 2.2, yB - 0.6, H2, face='back')
    b.water_tank(xR - 1.0, yB - 1.2, H2, 'tank_white', r=0.5, h=1.0, stand=0.7)
    hatch(b, 0.6, yU + 1.3, H2)
    # back side
    for u in (-2.0, 2.0):
        win(b, 'back', u, 4.4, 1.3, 1.3, wall=yB, frame=C['steel'], glass='glass', bars=2)
    cdoor(b, 'back', -2.4, 0.9, 2.1, wall=yB, frame=C['steel'], leaf='door_dark')
    win(b, 'back', 1.2, 1.3, 1.4, 0.9, wall=yB, frame=C['steel'], glass='glass', bars=2)
    b.ac_unit('back', 0.0, 4.6, wall=yB)
    b.ac_unit('back', 2.9, 2.4, wall=yB)
    pipe(b, 'back', xR - 0.25, H2 + 0.4, yB)
    trash_bin(b, -1.2, yB + 0.45, 0, 'awning_green')
    crates(b, -0.5, yB + 0.45, 2, rng, cols=(C['card'],))


def hp2(b, v, rng):
    W, D = b.W, b.D
    yF, H = 0.9, 6.5
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 1.0
    wall, fc, acc = v['wall'], v['fascia'], v['accent']
    sgn = 1 if rng.random() < 0.5 else -1
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.15, 'concrete', skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, H, wall)
    hq(b, xL, yF, xR, yB, H, v['roofc'])
    fy0, fy1 = yF - 0.45, yF + 0.2
    fx0, fx1 = -W / 2 + 0.02, W / 2 - 0.02
    fz0, fz1 = 3.25, 7.0
    fascia(b, fx0, fx1, fy0, fy1, fz0, fz1, fc, [(fz0, fz0 + 0.3, acc), (fz1 - 0.22, fz1, acc)])
    parapet(b, xL, xR, fy1, yB, H, 0.5, wall, front=False)
    # billboard graphics: white field with bars, big phone icon, accent chevron bar
    ic = fx0 + 0.45 if sgn > 0 else fx1 - 1.95
    b.decal('front', ic, ic + 1.5, 3.8, 6.4, 'sign_white', off=0.03, wall=fy0)
    b.decal('front', ic + 0.35, ic + 1.15, 3.95, 6.2, 'sign_text', off=0.04, wall=fy0)
    b.decal('front', ic + 0.43, ic + 1.07, 4.2, 5.95, C['teal'], off=0.05, wall=fy0)
    lx0, lx1 = (ic + 1.85, fx1 - 0.4) if sgn > 0 else (fx0 + 0.4, ic - 0.35)
    b.decal('front', lx0, lx1, 5.55, 6.3, acc, off=0.03, wall=fy0)
    b.decal('front', lx0 + 0.25, lx1 - 0.25, 5.72, 6.13, 'sign_white', off=0.04, wall=fy0)
    b.decal('front', lx0, lx1 - 0.5, 4.75, 5.1, 'sign_text', off=0.03, wall=fy0)
    b.decal('front', lx0, lx1 - 1.1, 4.2, 4.5, 'sign_text', off=0.03, wall=fy0)
    b.decal('front', lx0, lx1, 3.75, 3.95, 'sign_red', off=0.03, wall=fy0)
    # ground floor: glass front, rolled-up shutter box and guide rails
    du = sgn * 1.2
    storefront(b, xL + 0.3, xR - 0.3, 0.15, 2.85, yF, door=(du, 1.1, 2.2), frame='metal', glass='glass_light',
               bay=1.2, kick=0.7, kick_col='sign_white', auto=False, shelves=(1.3, 1.8),
               shelf_cols=[fc, '#f2efe4', acc, '#e07a5f'])
    b.panel('front', xL + 0.1, xR - 0.1, 2.95, 3.22, 'shutter', off=0.24, depth=0.22, wall=yF)
    for u in (xL + 0.12, xR - 0.2):
        b.panel('front', u, u + 0.08, 0.15, 2.95, 'shutter_dark', off=0.1, depth=0.08, wall=yF)
    flag(b, -sgn * (W / 2 - 0.2), 0.25, 4.6, acc, fc, sgn=sgn)
    # roof: tank on stand, dish, laundry line, pots
    b.water_tank(sgn * (W / 2 - 1.0), yB - 1.0, H, 'tank_orange', r=0.5, h=1.0, stand=0.9)
    dish(b, -sgn * (W / 2 - 0.8), yB - 0.8, H, fx=0.0, fy=-1.0, r=0.4)
    jemuran(b, xL + 0.6, xR - 0.6, fy1 + 2.4, H, rng)
    b.plant_pot(-sgn * (W / 2 - 0.6), fy1 + 0.6, H, s=0.8)
    b.plant_pot(-sgn * (W / 2 - 1.3), fy1 + 0.6, H, s=0.7)
    for i in range(3):                              # condenser row behind the billboard
        roof_ac(b, sgn * (W / 2 - 0.75 - i * 1.0), fy1 + 0.55, H, face='front')
    b.box(sgn * 0.3, fy1 + 0.25, H, sgn * (W / 2 - 0.35), fy1 + 0.35, H + 0.08, 'metal')
    # back: windows on both floors, door, condensers, downpipe
    win(b, 'back', -1.4, 4.2, 1.4, 1.3, wall=yB, frame='trim_white', glass='glass', bars=2)
    win(b, 'back', 1.4, 4.4, 0.8, 0.9, wall=yB, frame='trim_white', glass=C['frost'], bars=1)
    win(b, 'back', 1.2 * sgn, 1.3, 1.2, 0.9, wall=yB, frame='trim_white', glass='glass', bars=2)
    cdoor(b, 'back', -1.4 * sgn, 0.9, 2.1, wall=yB)
    b.ac_unit('back', 0.0, 3.4, wall=yB)
    pipe(b, 'back', xR - 0.25, H + 0.5, yB)
    lpg(b, 1.9 * sgn, yB + 0.4)
    crates(b, 0.2 * sgn, yB + 0.5, 3, rng)


def klinik_wide(b, v, rng):
    W, D = b.W, b.D
    ap, H, HE = 3.6, 3.6, 4.5
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 1.1
    wall, acc, fc = v['wall'], v['accent'], v['fascia']
    left = rng.random() < 0.5                      # entrance block on the left?
    sg = -1 if left else 1                         # which side the entrance block is on
    apron(b, -W / 2, W / 2, 0, ap - 0.5, None, 0)
    b.box(-W / 2, ap - 0.5, 0, W / 2, ap, 0.1, 'concrete', skip=('bottom', 'back', 'front'))
    ew = 3.0
    ex0, ex1 = (xL, xL + ew) if left else (xR - ew, xR)
    mx0, mx1 = (ex1, xR) if left else (xL, ex0)
    eyF = ap - 0.5
    # parking lines in front of the main wing only (the pylon stands in front of the entrance block)
    a, e = mx0 + 0.3, mx1 - 0.3
    nb = 3
    bay_x = [a + (e - a) * i / nb for i in range(nb + 1)]
    for x in bay_x:
        hq(b, x - 0.05, 0.5, x + 0.05, eyF - 0.9, 0.115, 'trim_white')
    # entrance block: a real little building (white walls, flat roof behind a capped parapet) with teal
    # cladding on its street face and short returns round both corners
    HR = HE - 0.4
    walls(b, ex0, eyF, ex1, yB, 0, HR, wall)
    hq(b, ex0, eyF, ex1, yB, HR, v['roofc'])
    parapet(b, ex0, ex1, eyF, yB, HR, 0.4, wall, cap='trim_white')
    cf = eyF - 0.03                                # face of the cladding
    b.panel('front', ex0 - 0.03, ex1 + 0.03, 0, HE, acc, off=0.03, depth=0.03, wall=eyF)
    inner = 'right' if left else 'left'
    outer = 'left' if left else 'right'
    b.panel(outer, eyF, eyF + 0.6, 0, HE, acc, off=0.03, depth=0.03, wall=ex0 if left else ex1)
    b.panel(inner, eyF, ap, 0, HE, acc, off=0.03, depth=0.03, wall=ex1 if left else ex0)
    storefront(b, ex0 + 0.4, ex1 - 0.4, 0.1, 2.75, cf, door=((ex0 + ex1) / 2, 1.8, 2.3), frame='metal', bay=1.3,
               kick=0.3, auto=True)
    b.box(ex0 + 0.2, eyF - 1.1, 2.92, ex1 - 0.2, cf, 3.04, 'trim_white', skip=())
    b.sign('front', ex0 + 0.35, ex1 - 0.35, 3.25, 4.1, 'sign_white', text_color=fc, wall=cf)
    ec = (ex0 + ex1) / 2
    roof_ac(b, ec - 0.55, yB - 0.7, HR, face='back')
    hatch(b, ec + 0.6, eyF + 2.2, HR)
    # main wing: white box, blue fascia band as the front parapet, long canopy on slim posts
    walls(b, mx0, ap, mx1, yB, 0, H, wall, skip=('left',) if left else ('right',))
    hq(b, mx0, ap, mx1, yB, H, v['roofc'])
    fascia(b, mx0 if left else mx0 - 0.05, mx1 + 0.05 if left else mx1, ap - 0.3, ap + 0.15, 2.95, 3.95, fc,
           [(3.05, 3.1, 'sign_white')])
    b.decal('front', mx0 + 0.6, mx1 - 0.6, 3.4, 3.72, 'sign_white', off=0.03, wall=ap - 0.3)
    # parapet on the far side and the back
    fx = mx1 - 0.15 if left else mx0
    b.box(fx, ap + 0.15, H, fx + 0.15, yB - 0.15, 3.95, wall)
    b.box(mx0, yB - 0.15, H, mx1, yB, 3.95, wall)
    b.box(mx0 + 0.05, ap - 1.7, 2.72, mx1 - 0.05, ap, 2.84, 'trim_white', skip=())
    b.decal('front', mx0 + 0.05, mx1 - 0.05, 2.74, 2.82, fc, off=0.015, wall=ap - 1.7)
    for x in bay_x:                                # canopy posts stand on the bay lines
        b.box(x - 0.05, ap - 1.6, 0.1, x + 0.05, ap - 1.5, 2.72, 'metal')
    storefront(b, mx0 + 0.3, mx1 - 0.3, 0.1, 2.62, ap, door=None, frame='trim_white', glass='glass_light', bay=1.4,
               kick=0.95, kick_col=C['frost'], auto=False, shelves=(1.6,), shelf_cols=['#f2efe4'])
    # pylon sign at the street corner in front of the entrance block (clear of the parking bays)
    px = (ex0 + 0.75) if left else (ex1 - 0.75)
    for dx in (-0.4, 0.4):
        b.box(px + dx - 0.06, 0.32, 0.1, px + dx + 0.06, 0.44, 1.3, 'metal')
    b.box(px - 0.6, 0.28, 1.3, px + 0.6, 0.48, 3.7, fc, skip=())
    for side, w in (('front', 0.28), ('back', 0.48)):
        b.decal(side, px - 0.48, px + 0.48, 1.45, 3.55, 'sign_white', off=0.01, wall=w)
        b.decal(side, px - 0.35, px + 0.35, 2.9, 3.25, fc, off=0.02, wall=w)
        b.decal(side, px - 0.3, px + 0.3, 2.35, 2.6, fc, off=0.02, wall=w)
        b.decal(side, px - 0.3, px + 0.3, 1.7, 2.0, 'sign_green', off=0.02, wall=w)
    # roof: solar panels, condensers, hatch
    sx0, sx1 = mx0 + 0.6, mx1 - 0.6
    for y0 in (ap + 1.0, ap + 2.9):
        solar_row(b, sx0, sx1, y0, H)
    for i in range(3):
        roof_ac(b, sx0 + 0.6 + i * 1.05, yB - 0.7, H, face='back')
    hatch(b, sx1 - 0.7, yB - 1.0, H)
    # back: windows, doors, condensers, tank on stand, downpipes
    wus = ((mx0 + 1.5), (mx0 + mx1) / 2, (mx1 - 1.5))
    for u in wus:
        win(b, 'back', u, 1.3, 1.2, 1.0, wall=yB, frame='trim_white', glass='glass', bars=2)
    for k in range(2):                             # condensers between the windows, not over the glass
        b.ac_unit('back', (wus[k] + wus[k + 1]) / 2, 2.4, wall=yB)
    cdoor(b, 'back', (ex0 + ex1) / 2, 0.95, 2.1, wall=yB)
    win(b, 'back', (ex0 + ex1) / 2, 3.2, 1.0, 0.6, wall=yB, frame='trim_white', glass=C['frost'])
    pipe(b, 'back', (mx1 - 0.25) if left else (mx0 + 0.25), 3.95, yB)
    b.water_tank((ex0 + ex1) / 2 + 1.0 * (-sg), yB + 0.55, 0, 'tank_blue', r=0.45, h=0.9, stand=1.8)
    gx = (ex0 + ex1) / 2 + 2.4 * (-sg)
    b.box(gx - 0.55, yB + 0.2, 0, gx + 0.55, yB + 0.9, 0.95, 'sign_green')
    b.decal('back', gx - 0.4, gx + 0.1, 0.25, 0.7, 'metal', off=0.01, wall=yB + 0.9)


def octagon(b, side, uc, zc, r, c, off, wall):
    """Flat octagon decal on a facade (porthole of a washing machine, bubble on a sign)."""
    m, _ = b._frame(side, wall)
    pts = []
    for i in range(8):
        t = 2 * math.pi * (i + 0.5) / 8
        x, y = m(uc + r * math.cos(t), off)
        pts.append((x, y, zc + r * math.sin(t)))
    hint = {'front': (0, -1, 0), 'back': (0, 1, 0), 'left': (-1, 0, 0), 'right': (1, 0, 0)}[side]
    face_out(b, pts, c, hint)


def laundry(b, v, rng):
    W, D = b.W, b.D
    yF, H = 1.5, 3.4
    xL, xR, yB = -W / 2 + 0.1, W / 2 - 0.1, D - 0.9
    wall, fc = v['wall'], v['fascia']
    sgn = 1 if rng.random() < 0.5 else -1
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.15, 'concrete', skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, H, wall)
    b.panel('front', xL, xR, 0.15, 0.5, 'plinth', off=0.02, depth=0.02, wall=yF)
    hq(b, xL, yF, xR, yB, H, v['roofc'])
    # sign board standing on the front edge (doubles as the front parapet): bars + soap bubbles
    fy0, fy1 = yF - 0.15, yF + 0.12
    fascia(b, xL - 0.05, xR + 0.05, fy0, fy1, 2.9, 4.2, fc, [(2.9, 3.0, 'sign_yellow')])
    bu = xL + 0.9 if sgn > 0 else xR - 0.9
    for (du_, dz, r) in ((0.0, 3.55, 0.42), (0.55 * sgn, 3.85, 0.2), (0.62 * sgn, 3.3, 0.14)):
        octagon(b, 'front', bu + du_, dz, r, 'sign_white', 0.03 + 0.005 * (r < 0.3), fy0)
    lx0, lx1 = (bu + 1.0, xR - 0.4) if sgn > 0 else (xL + 0.4, bu - 1.0)
    b.decal('front', lx0, lx1, 3.62, 3.95, 'sign_white', off=0.03, wall=fy0)
    b.decal('front', lx0, lx1 - 1.2 if sgn > 0 else lx1, 3.2, 3.42, 'sign_yellow', off=0.03, wall=fy0)
    parapet(b, xL, xR, fy1, yB, H, 0.4, wall, front=False, cap='trim_white')
    # yellow metal canopy, glass front with a row of front-loading washers behind it
    b.awning('front', xL + 0.1, xR - 0.1, 2.8, out=1.1, drop=0.2, color=v['canopy'], wall=yF)
    du = sgn * (xR - 0.95)
    storefront(b, xL + 0.25, xR - 0.25, 0.5, 2.6, yF, door=None, frame='trim_white', glass='glass_light', bay=1.3,
               kick=0.0, shelves=(2.05,), shelf_cols=['#e25d7a', '#5db0e2', '#f2d24a'])
    b.panel('front', du - 0.6, du + 0.6, 0.15, 2.67, 'trim_white', off=0.075, depth=0.03, wall=yF)
    b.decal('front', du - 0.5, du + 0.5, 0.15, 1.0, 'glass', off=0.08, wall=yF)
    b.decal('front', du - 0.5, du + 0.5, 1.08, 2.55, 'glass_light', off=0.08, wall=yF)
    b.decal('front', du - 0.5, du + 0.5, 1.0, 1.08, 'trim_white', off=0.085, wall=yF)    # mid rail
    hu = du - sgn * 0.36                            # pull handle on the lock side
    b.panel('front', hu - 0.03, hu + 0.03, 0.8, 1.35, 'metal', off=0.14, depth=0.05, wall=yF)
    mx0, mx1 = (xL + 0.45, du - 0.8) if sgn > 0 else (du + 0.8, xR - 0.45)
    n = int((mx1 - mx0) / 0.78)
    for i in range(n):
        u = mx0 + (mx1 - mx0) * (i + 0.5) / n
        b.decal('front', u - 0.33, u + 0.33, 0.62, 1.42, 'ac_white', off=0.07, wall=yF)
        octagon(b, 'front', u, 1.05, 0.22, 'glass_dark', 0.075, yF)
    # customers' bench and laundry baskets
    bx = du - sgn * 2.6
    bench(b, bx - 0.75, bx + 0.75, yF - 0.55, yF - 0.2, 0.15, c='sign_blue')
    for k, c in enumerate(('awning_blue', 'awning_red')):
        x = du - sgn * (1.1 + 0.55 * k)
        b.box(x - 0.24, yF - 0.5, 0.15, x + 0.24, yF - 0.15, 0.5, c)
    # roof: rows of drying laundry, tank, hatch
    for k, yy in enumerate((fy1 + 1.4, fy1 + 3.0, fy1 + 4.6)):
        jemuran(b, xL + 0.5, xR - 2.0 if k == 2 else xR - 0.5, yy, H, rng, h=1.3)
    tank(b, xR - 0.9, yB - 0.9, H, 'tank_blue', r=0.45)
    hatch(b, xL + 1.0, yB - 1.0, H)
    # back: door, windows, drain pipe, condensers
    bd = -sgn * (xR - 1.0)
    cdoor(b, 'back', bd, 0.9, 2.1, wall=yB)
    for u in (-bd * 0.05, -bd * 0.75):
        win(b, 'back', u, 1.4, 1.1, 0.9, wall=yB, frame='trim_white', glass='glass', bars=2)
    b.ac_unit('back', -bd * 0.4, 2.5, wall=yB)       # between the two windows
    pipe(b, 'back', bd + sgn * 0.8, H + 0.4, yB)
    crates(b, bd + sgn * 1.5, yB + 0.45, 2, rng, cols=('awning_blue', 'awning_white'))


def kopi(b, v, rng):
    W, D = b.W, b.D
    yF, zlo, zhi = 2.0, 3.2, 3.75
    xL, xR, yB = -W / 2 + 0.25, W / 2 - 0.25, D - 0.9
    wall = v['wall']
    sgn = 1 if rng.random() < 0.5 else -1
    b.box(-W / 2 + 0.02, 0.0, 0, W / 2 - 0.02, yF, 0.15, v['deck'], skip=('bottom', 'back'))
    walls(b, xL, yF, xR, yB, 0, zlo, wall)
    zt = shed_roof(b, xL, xR, yF, yB, zhi, zlo, v['roofc'], fill=wall, over=0.25, over_side=0.22, over_front=1.3)
    ya, yb = yF - 1.28, yB + 0.23
    n = int((xR - xL + 0.4) / 0.55)
    for i in range(n + 1):
        x = xL - 0.2 + (xR - xL + 0.4) * i / n
        face_out(b, [(x - 0.025, ya, zt(ya) + 0.02), (x + 0.025, ya, zt(ya) + 0.02), (x + 0.025, yb, zt(yb) + 0.02),
                     (x - 0.025, yb, zt(yb) + 0.02)], '#3a4148', (0, 0, 1))
    # two slim posts carry the deep front overhang
    for x in (xL + 0.1, xR - 0.1):
        b.box(x - 0.05, yF - 1.15, 0.15, x + 0.05, yF - 1.05, zt(yF - 1.1) - 0.1, C['steel'])
    # timber slat facade, pick-up window with a counter, glazed door, blank light sign
    wu = -sgn * 0.7
    b.panel('front', xL, xR, 0.15, zlo, C['wood'], off=0.03, depth=0.03, wall=yF)
    k = int((xR - xL) / 0.28)
    for i in range(1, k):
        u = xL + (xR - xL) * i / k
        b.decal('front', u - 0.03, u + 0.03, 0.15, zlo - 0.05, C['wood_dark'], off=0.035, wall=yF)
    win(b, 'front', wu, 1.0, 2.3, 1.35, wall=yF, frame=C['steel'], glass='glass_light', bars=2, off=0.08)
    b.panel('front', wu - 1.25, wu + 1.25, 0.95, 1.02, C['wood_dark'], off=0.42, depth=0.34, wall=yF)
    du = sgn * (xR - 0.8)
    cdoor(b, 'front', du, 0.95, 2.2, wall=yF, frame=C['steel'], leaf='glass')
    b.sign('front', wu - 1.0, wu + 1.0, 2.55, 3.05, 'sign_white', text_color=C['wood_dark'], off=0.14, wall=yF)
    # benches for waiting drivers + a menu board and planters
    bench(b, -W / 2 + 0.3, -W / 2 + 1.9, 0.35, 0.75, 0.15, c=C['wood'])
    bench(b, W / 2 - 1.9, W / 2 - 0.3, 0.35, 0.75, 0.15, c=C['wood'])
    mx = du - sgn * 1.0
    wedge(b, mx - 0.28, mx + 0.28, yF - 0.75, yF - 0.55, 0.15, 1.0, 1.0, C['steel'])
    b.decal('front', mx - 0.2, mx + 0.2, 0.3, 0.9, 'sign_white', off=0.01, wall=yF - 0.75)
    b.plant_pot(wu - sgn * 1.55, yF - 0.35, 0.15, s=0.8)
    # back: door, small window, condenser, milk crates, bin, gas
    bd = sgn * (xR - 0.9)
    cdoor(b, 'back', bd, 0.9, 2.1, wall=yB, frame=C['steel'], leaf='door_dark')
    win(b, 'back', -bd * 0.3, 1.5, 1.0, 0.8, wall=yB, frame=C['steel'], glass='glass', bars=2)
    b.ac_unit('back', bd * 0.35, 2.3, wall=yB)        # between the door and the window
    crates(b, -bd * 0.85, yB + 0.45, 3, rng, cols=('awning_blue', 'awning_green', 'awning_red'))
    trash_bin(b, bd - sgn * 1.0, yB + 0.4, 0, 'awning_orange')
    lpg(b, bd - sgn * 1.6, yB + 0.4)
    b.box(xL + 0.9, yB - 1.5, zt(yB - 1.3) - 0.3, xL + 1.1, yB - 1.3, zt(yB - 1.3) + 0.45, 'metal')


BUILDERS = {'mini': minimarket, 'apotek': apotek, 'klinik': klinik, 'bakery': bakery, 'hp': hp, 'cafe2': cafe2,
            'hp2': hp2, 'klinik_wide': klinik_wide, 'laundry': laundry, 'kopi': kopi}


def build(b, v, rng):
    BUILDERS[v['kind']](b, v, rng)

"""Shared helpers for the Ojol Rush building generators.

Runs inside Blender 4.2 used as a Python module (`pip install bpy==4.2.0`), fully headless.
Every building is modelled from simple, clean primitives (boxes, slabs, roof prisms, flat "decal"
quads) with flat colours, so nothing can come out warped or abstract, and the triangle count stays
low enough for phones. The game converts the material colours to cel-shaded vertex colours.

Coordinate convention inside a builder (metres, Blender Z-up):
  x in [-W/2, W/2]  left -> right when looking at the front
  y in [0, D]       y = 0 is the FRONT facade (faces -Y, i.e. the street), y = D is the back
  z in [0, H]       ground at z = 0
On export the footprint is re-centred (y -> y - D/2); Blender's -Y front becomes glTF +Z, which is
what the game expects (buildings face +Z towards their street).
"""
import bpy  # must come first: it registers bmesh/mathutils
import bmesh
import json
import math
import os
import random
import zlib

# ------------------------------------------------------------------------------------------ palette
# sRGB hex colours. Walls are the pastel paints you see on Jakarta houses and ruko.
PALETTE = {
    # walls
    'wall_cream': '#f2e3bf', 'wall_white': '#f1efe6', 'wall_mint': '#a8d8c0', 'wall_sky': '#a9cbe8',
    'wall_peach': '#f2b891', 'wall_pink': '#ecaeb8', 'wall_yellow': '#f5dc72', 'wall_lime': '#bfe08a',
    'wall_lilac': '#c3b5e3', 'wall_sand': '#dcc39f', 'wall_grey': '#c9c9c4', 'wall_terracotta': '#d9896a',
    'wall_teal': '#6fb7b0', 'wall_orange': '#f0a24e', 'wall_blue': '#7fa8d9', 'wall_green': '#8cc47e',
    # trims / structure
    'trim_white': '#fbfaf5', 'trim_dark': '#4a4440', 'concrete': '#b9b5ad', 'concrete_dark': '#8f8b84',
    'plinth': '#8a8078', 'tile_floor': '#d8cbb8', 'column': '#ece6da',
    # roofs
    'roof_terracotta': '#c2582f', 'roof_brown': '#8e4a2e', 'roof_red': '#b8372d', 'roof_grey': '#6f7680',
    'roof_blue': '#4f6f93', 'roof_green': '#4f7f5a', 'roof_zinc': '#a7aeb3', 'roof_asbestos': '#bdbab2',
    # openings
    'glass': '#3b5570', 'glass_light': '#7fa6c4', 'glass_dark': '#27394d', 'window_frame': '#f4f2ea',
    'frame_brown': '#6b4a33', 'frame_black': '#2d2a28', 'door_wood': '#8a5a3a', 'door_dark': '#5b3b28',
    'shutter': '#b7bcc0', 'shutter_dark': '#8e959b', 'shutter_groove': '#7c848a',
    # metal / misc
    'rail_black': '#2e2c2a', 'rail_white': '#eeeeea', 'rail_green': '#3f6b4a', 'metal': '#9aa1a6',
    'tank_orange': '#e8872c', 'tank_blue': '#3c78b5', 'tank_white': '#ecebe4', 'ac_white': '#e8e8e2',
    'awning_red': '#d8433a', 'awning_blue': '#3d6fb6', 'awning_green': '#3f9a5a', 'awning_yellow': '#f2c230',
    'awning_orange': '#ef7d2d', 'awning_white': '#f3f1ea', 'awning_stripe': '#f7f4ec',
    'sign_red': '#d93a33', 'sign_blue': '#2f6fc0', 'sign_yellow': '#f5cc2a', 'sign_green': '#2f9a57',
    'sign_orange': '#f07c24', 'sign_white': '#f6f4ee', 'sign_purple': '#7c4aa8', 'sign_text': '#2a2622',
    'plant': '#4f9a48', 'plant_dark': '#3a7a38', 'pot': '#b0643c', 'fabric_1': '#e25d7a', 'fabric_2': '#5db0e2',
    'fabric_3': '#f2d24a', 'ground_yard': '#9c8f78',
}


def hex_to_linear(h):
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def seeded(*parts):
    """Deterministic RNG (Python's hash() is randomised per process)."""
    return random.Random(zlib.crc32('|'.join(str(p) for p in parts).encode()))


_MATS = {}


def material(color):
    """Material for a palette key or '#rrggbb' hex. Shared across buildings, named by hex."""
    hexc = PALETTE.get(color, color)
    if not hexc.startswith('#'):
        raise KeyError('unknown colour ' + color)
    hexc = hexc.lower()
    m = _MATS.get(hexc)
    if m is None or m.name not in bpy.data.materials:
        m = bpy.data.materials.new('c' + hexc[1:])
        m.use_nodes = True
        bsdf = m.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = hex_to_linear(hexc)
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Metallic'].default_value = 0.0
        m.diffuse_color = hex_to_linear(hexc)
        _MATS[hexc] = m
    return m


# ------------------------------------------------------------------------------------------ builder
SIDES = ('front', 'back', 'left', 'right')


class Bld:
    """Accumulates one building as a single bmesh with per-face material slots."""

    def __init__(self, name, width, depth):
        self.name, self.W, self.D = name, float(width), float(depth)
        self.bm = bmesh.new()
        self.slots = []   # material objects, index = slot
        self.top = 0.0    # highest z seen, for the manifest

    # ---- low level
    def _slot(self, color):
        m = material(color)
        if m not in self.slots:
            self.slots.append(m)
        return self.slots.index(m)

    def face(self, pts, color):
        """Planar polygon from (x, y, z) points, counter-clockwise when seen from the outside."""
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self._slot(color)
        self.top = max(self.top, max(p[2] for p in pts))
        return f

    def box(self, x0, y0, z0, x1, y1, z1, color, skip=('bottom',)):
        """Axis-aligned box. `skip` drops faces nobody will see ('bottom', 'top', 'front', 'back', 'left', 'right')."""
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            return
        F = {
            'bottom': [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
            'top': [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            'front': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            'back': [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            'left': [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
            'right': [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        }
        for k, pts in F.items():
            if k not in skip:
                self.face(pts, color)

    def cyl(self, cx, cy, z0, z1, r, color, seg=10, top=True):
        """Vertical cylinder (water tanks, poles, columns)."""
        ring = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        for i in range(seg):
            a, b = ring[i], ring[(i + 1) % seg]
            self.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], color)
        if top:
            self.face([(p[0], p[1], z1) for p in ring], color)

    # ---- facade helpers: (u, z) coordinates on a wall, `off` = distance proud of that wall (negative = recessed)
    def _frame(self, side, wall):
        """Return mapping (u, n) -> (x, y) and the outward axis for a facade.
        u is the plain world coordinate along the wall: x for 'front'/'back', y for 'left'/'right'.
        n is the distance outward from the wall plane.
        wall: the facade plane position (y for front/back, x for left/right); defaults to the footprint edge
        (front y=0, back y=D, left x=-W/2, right x=W/2). Pass it for set-back upper floors etc."""
        W, D = self.W, self.D
        if side == 'front':
            w = 0.0 if wall is None else wall
            return (lambda u, n: (u, w - n)), 'y-'
        if side == 'back':
            w = D if wall is None else wall
            return (lambda u, n: (u, w + n)), 'y+'
        if side == 'left':
            w = -W / 2 if wall is None else wall
            return (lambda u, n: (w - n, u)), 'x-'
        if side == 'right':
            w = W / 2 if wall is None else wall
            return (lambda u, n: (w + n, u)), 'x+'
        raise ValueError(side)

    def panel(self, side, u0, u1, z0, z1, color, off=0.03, depth=0.03, wall=None):
        """A thin slab on a facade: spans u0..u1 horizontally and z0..z1 vertically, from off-depth to off
        proud of the wall. Use for windows, doors, signs, frames, stripes, pilasters."""
        m, _ = self._frame(side, wall)
        (xa, ya), (xb, yb) = m(u0, off - depth), m(u1, off)
        self.box(xa, ya, z0, xb, yb, z1, color)

    def decal(self, side, u0, u1, z0, z1, color, off=0.02, wall=None):
        """Single outward-facing quad (2 triangles) `off` in front of a facade. Cheapest detail there is."""
        m, _ = self._frame(side, wall)
        a, b = m(u0, off), m(u1, off)
        # orient outward
        if side == 'front':
            pts = [(min(a[0], b[0]), a[1], z0), (max(a[0], b[0]), a[1], z0), (max(a[0], b[0]), a[1], z1), (min(a[0], b[0]), a[1], z1)]
        elif side == 'back':
            pts = [(max(a[0], b[0]), a[1], z0), (min(a[0], b[0]), a[1], z0), (min(a[0], b[0]), a[1], z1), (max(a[0], b[0]), a[1], z1)]
        elif side == 'left':
            pts = [(a[0], max(a[1], b[1]), z0), (a[0], min(a[1], b[1]), z0), (a[0], min(a[1], b[1]), z1), (a[0], max(a[1], b[1]), z1)]
        else:
            pts = [(a[0], min(a[1], b[1]), z0), (a[0], max(a[1], b[1]), z0), (a[0], max(a[1], b[1]), z1), (a[0], min(a[1], b[1]), z1)]
        self.face(pts, color)

    def window(self, side, uc, z0, w, h, glass='glass', frame='window_frame', bars=1, sill=True, wall=None, mullion=True):
        """Framed window centred at uc, bottom at z0. `bars` vertical panes (1..4)."""
        t = 0.08
        self.panel(side, uc - w / 2, uc + w / 2, z0, z0 + h, glass, off=0.015, depth=0.015, wall=wall)
        self.panel(side, uc - w / 2 - t, uc + w / 2 + t, z0 + h, z0 + h + t, frame, off=0.06, depth=0.06, wall=wall)
        self.panel(side, uc - w / 2 - t, uc + w / 2 + t, z0 - t, z0, frame, off=0.06, depth=0.06, wall=wall)
        self.panel(side, uc - w / 2 - t, uc - w / 2, z0, z0 + h, frame, off=0.06, depth=0.06, wall=wall)
        self.panel(side, uc + w / 2, uc + w / 2 + t, z0, z0 + h, frame, off=0.06, depth=0.06, wall=wall)
        if mullion and bars > 1:
            for i in range(1, bars):
                u = uc - w / 2 + w * i / bars
                self.decal(side, u - 0.03, u + 0.03, z0, z0 + h, frame, off=0.03, wall=wall)
        if sill:
            self.panel(side, uc - w / 2 - 0.14, uc + w / 2 + 0.14, z0 - t - 0.06, z0 - t, frame, off=0.14, depth=0.14, wall=wall)

    def door(self, side, uc, w, h, color='door_wood', frame='window_frame', z0=0.0, wall=None):
        self.panel(side, uc - w / 2, uc + w / 2, z0, z0 + h, color, off=0.02, depth=0.02, wall=wall)
        self.panel(side, uc - w / 2 - 0.08, uc + w / 2 + 0.08, z0 + h, z0 + h + 0.08, frame, off=0.05, depth=0.05, wall=wall)
        self.panel(side, uc - w / 2 - 0.08, uc - w / 2, z0, z0 + h, frame, off=0.05, depth=0.05, wall=wall)
        self.panel(side, uc + w / 2, uc + w / 2 + 0.08, z0, z0 + h, frame, off=0.05, depth=0.05, wall=wall)

    def shutter(self, side, u0, u1, z0, z1, color='shutter', groove='shutter_groove', step=0.32, wall=None, box=True):
        """Rolling door (rolling door ruko): panel + horizontal grooves + roll box on top."""
        self.panel(side, u0, u1, z0, z1, color, off=0.03, depth=0.03, wall=wall)
        z = z0 + step
        while z < z1 - 0.05:
            self.decal(side, u0 + 0.02, u1 - 0.02, z - 0.03, z, groove, off=0.035, wall=wall)
            z += step
        if box:
            self.panel(side, u0 - 0.05, u1 + 0.05, z1, z1 + 0.28, color, off=0.2, depth=0.2, wall=wall)

    def sign(self, side, u0, u1, z0, z1, color, text_color='sign_text', off=0.12, bars=2, wall=None):
        """Blank shop sign board with a couple of 'lettering' bars (no readable text, no brands)."""
        self.panel(side, u0, u1, z0, z1, color, off=off, depth=0.1, wall=wall)
        h = z1 - z0
        if bars >= 1:
            self.decal(side, u0 + (u1 - u0) * 0.14, u1 - (u1 - u0) * 0.14, z0 + h * 0.52, z0 + h * 0.78, text_color, off=off + 0.005, wall=wall)
        if bars >= 2:
            self.decal(side, u0 + (u1 - u0) * 0.26, u1 - (u1 - u0) * 0.26, z0 + h * 0.22, z0 + h * 0.4, text_color, off=off + 0.005, wall=wall)

    def railing(self, side, u0, u1, z0, h=1.0, color='rail_black', off=1.0, post=0.6, wall=None):
        """Balcony railing standing `off` in front of the wall: top rail, mid rail and posts."""
        self.panel(side, u0, u1, z0 + h - 0.06, z0 + h, color, off=off, depth=0.06, wall=wall)
        self.panel(side, u0, u1, z0 + h * 0.45, z0 + h * 0.45 + 0.04, color, off=off, depth=0.04, wall=wall)
        n = max(1, int(round((u1 - u0) / post)))
        for i in range(n + 1):
            u = u0 + (u1 - u0) * i / n
            self.panel(side, u - 0.03, u + 0.03, z0, z0 + h, color, off=off, depth=0.05, wall=wall)

    def awning(self, side, u0, u1, z, out=1.2, drop=0.45, color='awning_red', stripe=None, wall=None, thick=0.06):
        """Sloped canopy (kanopi / tenda) sticking out of a facade. Optional alternating stripes."""
        m, _ = self._frame(side, wall)
        n = 1 if stripe is None else max(2, int(round((u1 - u0) / 0.6)))
        for i in range(n):
            a, b = u0 + (u1 - u0) * i / n, u0 + (u1 - u0) * (i + 1) / n
            col = color if (stripe is None or i % 2 == 0) else stripe
            p = [m(a, 0.0), m(b, 0.0), m(b, out), m(a, out)]
            zz = [z, z, z - drop, z - drop]
            top = [(p[k][0], p[k][1], zz[k] + thick) for k in range(4)]
            bot = [(p[k][0], p[k][1], zz[k]) for k in range(4)]
            self._slab(top, bot, col)
        # valance at the outer edge
        self.panel(side, u0, u1, z - drop - 0.22, z - drop + thick, color, off=out + 0.02, depth=0.04, wall=wall)

    def _slab(self, top, bot, color):
        """Closed slab between two quads given in matching order (top counter-clockwise from above)."""
        # make top CCW seen from above
        def ccw(pts):
            s = sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))
            return s > 0
        if not ccw(top):
            top, bot = top[::-1], bot[::-1]
        self.face(top, color)
        self.face(bot[::-1], color)
        for i in range(4):
            j = (i + 1) % 4
            self.face([bot[i], bot[j], top[j], top[i]], color)

    # ---- roofs
    def roof_gable(self, x0, x1, y0, y1, z0, rise, color, gable_color=None, over=0.45, thick=0.12, ridge='x'):
        """Pitched two-slope roof over the rectangle. ridge='x' runs the ridge left-right (slopes face
        front and back); gable ends are filled with gable_color (defaults to the roof colour)."""
        gc = gable_color or color
        if ridge == 'x':
            ym = (y0 + y1) / 2
            for (ya, yb) in ((y0 - over, ym), (y1 + over, ym)):
                top = [(x0 - over, ya, z0 + thick), (x1 + over, ya, z0 + thick), (x1 + over, yb, z0 + rise + thick), (x0 - over, yb, z0 + rise + thick)]
                bot = [(p[0], p[1], p[2] - thick) for p in top]
                self._slab(top, bot, color)
            for x in (x0, x1):
                pts = [(x, y0, z0), (x, y1, z0), (x, ym, z0 + rise)] if x == x1 else [(x, y1, z0), (x, y0, z0), (x, ym, z0 + rise)]
                self.face(pts, gc)
        else:
            xm = (x0 + x1) / 2
            for (xa, xb) in ((x0 - over, xm), (x1 + over, xm)):
                top = [(xa, y0 - over, z0 + thick), (xa, y1 + over, z0 + thick), (xb, y1 + over, z0 + rise + thick), (xb, y0 - over, z0 + rise + thick)]
                bot = [(p[0], p[1], p[2] - thick) for p in top]
                self._slab(top, bot, color)
            for y in (y0, y1):
                pts = [(x0, y, z0), (x1, y, z0), (xm, y, z0 + rise)] if y == y0 else [(x1, y, z0), (x0, y, z0), (xm, y, z0 + rise)]
                self.face(pts, gc)
        self.top = max(self.top, z0 + rise + thick)

    def roof_hip(self, x0, x1, y0, y1, z0, rise, color, over=0.45, thick=0.12):
        """Four-slope limasan roof, the classic Indonesian house roof."""
        X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
        w, d = X1 - X0, Y1 - Y0
        if w >= d:
            r0, r1 = (X0 + d / 2, (Y0 + Y1) / 2), (X1 - d / 2, (Y0 + Y1) / 2)
        else:
            r0, r1 = ((X0 + X1) / 2, Y0 + w / 2), ((X0 + X1) / 2, Y1 - w / 2)
        zt = z0 + rise
        c = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
        if abs(w - d) < 1e-6:
            polys = [[c[0], c[1], r0], [c[1], c[2], r0], [c[2], c[3], r0], [c[3], c[0], r0]]
        elif w >= d:
            polys = [[c[0], c[1], r1, r0], [c[1], c[2], r1], [c[2], c[3], r0, r1], [c[3], c[0], r0]]
        else:
            polys = [[c[0], c[1], r0], [c[1], c[2], r1, r0], [c[2], c[3], r1], [c[3], c[0], r0, r1]]
        ridge = {r0, r1}
        for poly in polys:
            top = [(p[0], p[1], (zt if p in ridge else z0) + thick) for p in poly]
            self.face(top, color)
        # underside / eaves: flat soffit ring so the roof reads solid from low angles
        self.face([(X0, Y0, z0), (X0, Y1, z0), (X1, Y1, z0), (X1, Y0, z0)], color)
        for i in range(4):
            a, b = c[i], c[(i + 1) % 4]
            self.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z0 + thick), (a[0], a[1], z0 + thick)], color)
        self.top = max(self.top, zt + thick)

    def roof_shed(self, x0, x1, y0, y1, z_front, z_back, color, over=0.4, thick=0.1):
        """Single-slope roof (front edge at z_front, back edge at z_back)."""
        top = [(x0 - over, y0 - over, z_front + thick), (x1 + over, y0 - over, z_front + thick), (x1 + over, y1 + over, z_back + thick), (x0 - over, y1 + over, z_back + thick)]
        bot = [(p[0], p[1], p[2] - thick) for p in top]
        self._slab(top, bot, color)

    def parapet(self, x0, x1, y0, y1, z0, h, color, t=0.15):
        """Low wall around a flat roof edge."""
        self.box(x0, y0, z0, x1, y0 + t, z0 + h, color)
        self.box(x0, y1 - t, z0, x1, y1, z0 + h, color)
        self.box(x0, y0 + t, z0, x0 + t, y1 - t, z0 + h, color)
        self.box(x1 - t, y0 + t, z0, x1, y1 - t, z0 + h, color)

    # ---- small props that make a roof read as Jakarta
    def water_tank(self, cx, cy, z0, color='tank_orange', r=0.55, h=1.1, stand=0.9):
        """Toren air on a small steel stand."""
        for dx in (-0.4, 0.4):
            for dy in (-0.4, 0.4):
                self.box(cx + dx - 0.04, cy + dy - 0.04, z0, cx + dx + 0.04, cy + dy + 0.04, z0 + stand, 'metal')
        self.box(cx - 0.5, cy - 0.5, z0 + stand - 0.06, cx + 0.5, cy + 0.5, z0 + stand, 'metal', skip=())
        self.cyl(cx, cy, z0 + stand, z0 + stand + h, r, color, seg=10)

    def ac_unit(self, side, uc, z0, wall=None):
        """Outdoor AC condenser hanging on a wall."""
        self.panel(side, uc - 0.4, uc + 0.4, z0, z0 + 0.55, 'ac_white', off=0.32, depth=0.3, wall=wall)
        self.decal(side, uc - 0.3, uc + 0.05, z0 + 0.1, z0 + 0.45, 'metal', off=0.33, wall=wall)

    def plant_pot(self, x, y, z0=0.0, s=1.0):
        self.cyl(x, y, z0, z0 + 0.35 * s, 0.22 * s, 'pot', seg=8)
        self.box(x - 0.3 * s, y - 0.3 * s, z0 + 0.35 * s, x + 0.3 * s, y + 0.3 * s, z0 + 0.85 * s, 'plant')

    # ---- export
    def export(self, path):
        """Write the building as a GLB (footprint re-centred on y) and return its manifest stats."""
        bm = self.bm
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, -self.D / 2, 0.0))
        # every primitive above is built with outward (counter-clockwise) winding, so no normal recalculation:
        # that would guess (and sometimes flip) the orientation of the single-quad decals.
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.slots:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        for o in bpy.context.scene.objects:
            o.select_set(o is ob)
        bpy.context.view_layer.objects.active = ob
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
        # how far anything pokes outside the lot (neighbours abut, so this must stay ~0)
        overflow = max(0.0, -self.W / 2 - min(xs), max(xs) - self.W / 2, -self.D / 2 - min(ys), max(ys) - self.D / 2, -min(zs))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                                  export_texcoords=False, export_normals=True, export_materials='EXPORT',
                                  export_animations=False, export_extras=False, export_yup=True)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        return {'tris': tris, 'w': round(max(xs) - min(xs), 3), 'd': round(max(ys) - min(ys), 3), 'h': round(max(zs), 3),
                'footprint_w': self.W, 'footprint_d': self.D, 'overflow': round(overflow, 3)}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()

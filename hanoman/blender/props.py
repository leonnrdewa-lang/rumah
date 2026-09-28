#!/usr/bin/env python3
"""Hanoman Duta - environment props and pickups (static: one root Empty, meshes joined).

Run:  python3 hanoman/blender/props.py [ids...] [--no-preview] [--no-export]

All props: root Empty <id> at the ground centre (z = 0), front = -Y. Exceptions:
  dermaga  - deck TOP is at z = 0 (walkable), posts go down to z = -1.4 into the water;
  teratai  - sits on the water surface (z = 0);
  peti     - has a child pivot `lid` (hinge at the back top edge) so the game can open it.
Pickups (orb_dewa, kepeng, tirta, wijayakusuma) rest on z = 0; the game floats/spins them.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import V, TAU, Model, run_cli  # noqa: E402

G = "static"  # the single joined mesh group of a prop


def new(mid):
    m = Model(mid)
    m.smooth_default = False
    return m


# ------------------------------------------------------------------ shared builders
def bricks(m, BR, BR2, x0, x1, y0, y1, z0, z1, course=0.22, seed=0, inset=0.018, broken=None):
    """Stack of brick courses (slightly alternating inset, random darker courses).
    broken(z) -> (x0, x1) limits the course extent to simulate a ruined edge (or None)."""
    rnd = random.Random(seed)
    z = z0
    i = 0
    while z < z1 - 1e-4:
        h = min(course, z1 - z)
        a, b = x0, x1
        if broken:
            lim = broken(z + h, rnd)
            if lim is None:
                break
            a, b = max(a, lim[0]), min(b, lim[1])
            if b - a < 0.15:
                break
        d = inset if i % 2 else 0.0
        mt = BR2 if rnd.random() < 0.3 else BR
        m.box(G, mt, (b - a - d * 2, y1 - y0 - d * 2, h - 0.01), loc=((a + b) / 2, (y0 + y1) / 2, z + h / 2))
        z += h
        i += 1
    return z


def stone_cap(m, ST, x0, x1, y0, y1, z, h=0.14, over=0.06):
    m.box(G, ST, (x1 - x0 + over * 2, y1 - y0 + over * 2, h), loc=((x0 + x1) / 2, (y0 + y1) / 2, z + h / 2))


def blob_cluster(m, mt_list, centers, seed=0, sub=1, jitter=0.12, smooth=True):
    """Foliage lumps: smooth-shaded jittered icospheres (soft painted look under the toon shader)."""
    for i, (c, r, sc) in enumerate(centers):
        m.ico(G, mt_list[i % len(mt_list)], r, loc=c, scale=sc, sub=sub, jitter=jitter, seed=seed + i, smooth=smooth)


def flame(m, mt, mt_core, base, h=0.35, r=0.1):
    b = V(base)
    m.loft(G, mt, [b, b + V(0.02, 0, h * 0.4), b + V(-0.03, 0.01, h * 0.75), b + V(0.02, 0, h)],
           [r, r * 0.9, r * 0.45, 0.004], segs=8, res=3, smooth=True)
    m.loft(G, mt_core, [b + V(0, -0.02, 0.0), b + V(0, -0.03, h * 0.3), b + V(0, -0.02, h * 0.6)],
           [r * 0.6, r * 0.5, 0.004], segs=6, res=2, smooth=True)


def branch(m, mt, start, direction, length, r0, depth, rnd, segs=6, out=None, droop=0.0):
    """Recursive twisted branch; records tips in `out`."""
    d = V(direction).normalized()
    pts = [V(start)]
    p = V(start)
    for i in range(3):
        jitter = V((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.1, 0.2)))
        d = (d + jitter * 0.6 + V((0, 0, -droop))).normalized()
        p = p + d * (length / 3)
        pts.append(p)
    m.loft(G, mt, pts, [r0, r0 * 0.8, r0 * 0.6, r0 * 0.35 if depth > 0 else 0.01], segs=segs, res=1,
           smooth=True, cap0=False)
    if out is not None:
        out.append((pts[-1], d))
    if depth > 0:
        for k in range(2 if depth > 1 else rnd.choice((1, 2))):
            nd = d + V((rnd.uniform(-0.9, 0.9), rnd.uniform(-0.9, 0.9), rnd.uniform(-0.1, 0.5)))
            branch(m, mt, pts[-1 - k], nd, length * 0.65, r0 * 0.55, depth - 1, rnd, max(4, segs - 1), out, droop)


# ------------------------------------------------------------------ vegetation
def beringin():
    m = new("beringin")
    BARK = m.mat("M_Bark", "#4a3a2e")
    LEAF = m.mat("M_Leaf", "#2e5a45")
    LEAF2 = m.mat("M_LeafDark", "#1f3b33")
    rnd = random.Random(7)
    # braided multi-stem trunk with flaring buttress roots
    for i in range(4):
        a = TAU * i / 4 + 0.3
        base = V((math.cos(a) * 0.55, math.sin(a) * 0.55, 0))
        pts = [base + V((math.cos(a) * 0.35, math.sin(a) * 0.35, 0)), base + V((0, 0, 0.8)),
               V((math.cos(a + 0.8) * 0.25, math.sin(a + 0.8) * 0.25, 2.2)),
               V((math.cos(a + 1.4) * 0.3, math.sin(a + 1.4) * 0.3, 3.6))]
        m.loft(G, BARK, pts, [0.2, 0.32, 0.3, 0.26], segs=6, res=2, smooth=True, cap0=False)
    tips = []
    for i in range(5):
        a = TAU * i / 5 + 0.5
        branch(m, BARK, (math.cos(a) * 0.2, math.sin(a) * 0.2, 3.4), (math.cos(a), math.sin(a), 0.55), 2.6, 0.2,
               1, rnd, segs=5, out=tips)
    # canopy: broad flattened lumps, two tones
    cs = [((0, 0, 5.3), 2.2, (1.35, 1.35, 0.6))]
    for i in range(7):
        a = TAU * i / 7
        cs.append(((math.cos(a) * 2.4, math.sin(a) * 2.4, 4.8 + rnd.uniform(-0.3, 0.4)), 1.5 + rnd.uniform(0, 0.4),
                   (1.2, 1.2, 0.62)))
    for i in range(4):
        a = TAU * i / 4 + 0.4
        cs.append(((math.cos(a) * 1.2, math.sin(a) * 1.2, 6.1), 1.2, (1.2, 1.2, 0.6)))
    blob_cluster(m, [LEAF, LEAF2], cs, seed=3, sub=1, jitter=0.16)
    # hanging aerial roots (akar gantung)
    for i in range(16):
        a = rnd.uniform(0, TAU)
        r = rnd.uniform(1.2, 3.4)
        x, y = math.cos(a) * r, math.sin(a) * r
        top = 4.4 if r > 2.0 else 4.8
        bottom = rnd.choice((0.0, rnd.uniform(0.8, 2.4)))
        m.cyl(G, BARK, 0.035, top - bottom, loc=(x, y, (top + bottom) / 2), r2=0.02, segs=4, cap=False)
    return m


def pohon_mati():
    m = new("pohon_mati")
    BARK = m.mat("M_Bark", "#3a3036")
    MOSS = m.mat("M_Moss", "#2e5a45")
    rnd = random.Random(11)
    pts = [V((0, 0, 0)), V((0.1, 0.05, 1.0)), V((-0.15, 0.1, 2.0)), V((0.05, -0.1, 2.8))]
    m.loft(G, BARK, pts, [0.32, 0.22, 0.18, 0.12], segs=7, res=2, smooth=True)
    for i in range(4):  # roots
        a = TAU * i / 4 + 0.4
        m.loft(G, BARK, [V((0, 0, 0.5)), V((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.15)),
                         V((math.cos(a) * 0.9, math.sin(a) * 0.9, 0.0))], [0.16, 0.1, 0.02], segs=6, res=2, smooth=True)
    tips = []
    for i, (h, a) in enumerate(((1.6, 0.3), (2.3, 2.5), (2.7, 4.4), (2.9, 1.3))):
        branch(m, BARK, (0, 0, h), (math.cos(a), math.sin(a), 0.8), 1.4, 0.1, 2, rnd, segs=4, out=tips)
    for p, d in tips[:6]:  # hanging moss strands
        m.cyl(G, MOSS, 0.04, 0.5, loc=p + V((0, 0, -0.25)), r2=0.01, segs=4)
    m.scale_groups([G], 0.8, (0, 0, 0))  # ~4 m tall
    return m


def bakau():
    m = new("bakau")
    BARK = m.mat("M_Bark", "#5a4636")
    LEAF = m.mat("M_Leaf", "#3f6b44")
    LEAF2 = m.mat("M_LeafDark", "#2e5a45")
    rnd = random.Random(5)
    m.loft(G, BARK, [V((0, 0, 1.0)), V((0.05, 0, 2.2)), V((-0.05, 0.05, 3.0))], [0.16, 0.13, 0.1], segs=7, res=2,
           smooth=True)
    for i in range(8):  # arching stilt roots
        a = TAU * i / 8 + rnd.uniform(-0.2, 0.2)
        r = rnd.uniform(0.9, 1.3)
        top = V((math.cos(a) * 0.08, math.sin(a) * 0.08, 1.1 + rnd.uniform(0, 0.4)))
        mid = V((math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, 0.9))
        end = V((math.cos(a) * r, math.sin(a) * r, 0.0))
        m.loft(G, BARK, [top, mid, end], [0.08, 0.06, 0.05], segs=5, res=3, smooth=True, cap0=False)
    tips = []
    for i in range(4):
        a = TAU * i / 4 + 0.7
        branch(m, BARK, (0, 0, 2.6), (math.cos(a), math.sin(a), 0.7), 1.2, 0.08, 1, rnd, segs=5, out=tips)
    cs = [((0, 0, 3.4), 1.2, (1.3, 1.3, 0.7))]
    for i in range(5):
        a = TAU * i / 5
        cs.append(((math.cos(a) * 1.2, math.sin(a) * 1.2, 3.1 + rnd.uniform(-0.2, 0.3)), 0.85, (1.2, 1.2, 0.7)))
    blob_cluster(m, [LEAF, LEAF2], cs, seed=9)
    return m


def semak():
    m = new("semak")
    L1 = m.mat("M_Leaf", "#2e5a45")
    L2 = m.mat("M_LeafDark", "#1f3b33")
    rnd = random.Random(2)
    cs = [((0, 0, 0.45), 0.55, (1.2, 1.1, 0.85))]
    for i in range(5):
        a = TAU * i / 5 + 0.3
        cs.append(((math.cos(a) * 0.45, math.sin(a) * 0.45, 0.32 + rnd.uniform(0, 0.15)), 0.36 + rnd.uniform(0, 0.08),
                   (1, 1, 0.9)))
    blob_cluster(m, [L2, L1], cs, seed=4, jitter=0.2)
    return m


def pakis():
    m = new("pakis")
    L1 = m.mat("M_Leaf", "#4f7a4a")
    L2 = m.mat("M_LeafDark", "#2e5a45")
    rnd = random.Random(8)
    for i in range(9):
        a = TAU * i / 9 + rnd.uniform(-0.15, 0.15)
        L = rnd.uniform(0.7, 1.0)
        d = V((math.cos(a), math.sin(a), 0))
        pts = [V((0, 0, 0.05)), d * L * 0.35 + V((0, 0, 0.55)), d * L * 0.75 + V((0, 0, 0.6)), d * L + V((0, 0, 0.3))]
        # flat ribbon frond: wide across (side), paper thin vertically
        m.loft(G, L1 if i % 2 else L2, pts, [(0.015, 0.01), (0.11, 0.012), (0.08, 0.01), (0.005, 0.005)], segs=4,
               res=3, ref=(0, 0, 1), smooth=True)
    for i in range(3):  # curled fiddleheads
        a = TAU * i / 3 + 0.5
        d = V((math.cos(a), math.sin(a), 0))
        m.loft(G, L1, [V((0, 0, 0)), d * 0.1 + V((0, 0, 0.5)), d * 0.2 + V((0, 0, 0.62)), d * 0.12 + V((0, 0, 0.55))],
               [0.02, 0.018, 0.02, 0.03], segs=5, res=2, smooth=True)
    return m


def bunga_glow():
    m = new("bunga_glow")
    STEM = m.mat("M_Leaf", "#2e5a45")
    MAG = m.mat("M_GlowFlower", "#e0508f")
    TEAL = m.mat("M_GlowFlowerTeal", "#5fe0c8")
    rnd = random.Random(12)
    for i in range(6):  # leaves
        a = TAU * i / 6
        d = V((math.cos(a), math.sin(a), 0))
        m.loft(G, STEM, [V((0, 0, 0.02)), d * 0.25 + V((0, 0, 0.12)), d * 0.42 + V((0, 0, 0.05))],
               [(0.01, 0.01), (0.07, 0.01), (0.005, 0.005)], segs=4, res=2, ref=(0, 0, 1), smooth=True)
    for i in range(7):
        a = TAU * i / 7 + rnd.uniform(-0.3, 0.3)
        r = 0.08 + 0.2 * (i % 3) / 2
        h = rnd.uniform(0.35, 0.7)
        top = V((math.cos(a) * r, math.sin(a) * r, h))
        m.loft(G, STEM, [V((0, 0, 0)), top * 0.5 + V((0, 0, 0.05)), top], [0.014, 0.012, 0.01], segs=4, res=2)
        mt = MAG if i % 2 == 0 else TEAL
        # bell flower: 5 petals round a cup
        m.lathe(G, mt, [(0.0, 0.0), (0.03, 0.02), (0.06, 0.07), (0.08, 0.1)], loc=top, rot=(180, 0, 0),
                segs=6, smooth=True)
        m.ico(G, mt, 0.03, loc=top + V((0, 0, 0.02)), sub=1)
    return m


def teratai():
    m = new("teratai")
    PAD = m.mat("M_Leaf", "#3f7a4a")
    PETAL = m.mat("M_Petal", "#f2a6c4")
    GOLD = m.mat("M_Gold", "#f2b845")
    # lily pad: disc with a V notch (fan of triangles from the centre)
    for j, (c, R) in enumerate((((0, 0), 0.6), ((0.75, 0.45), 0.4))):
        n = 20
        verts = [(c[0], c[1], 0.02)]
        for k in range(n + 1):
            a = 0.35 + (TAU - 0.7) * k / n + j
            verts.append((c[0] + math.cos(a) * R, c[1] + math.sin(a) * R, 0.02 + 0.01 * math.sin(a * 3)))
        faces = [(0, k + 1, k + 2) for k in range(n)]
        m.mesh(G, PAD, verts, faces)
    # flower: two rings of pointed petals + golden centre
    for ring, (cnt, L, tilt, z) in enumerate(((8, 0.28, 55, 0.05), (6, 0.22, 25, 0.08))):
        for k in range(cnt):
            a = 360 * k / cnt + ring * 30
            m.prism(G, PETAL, [(-0.07, 0), (0.07, 0), (0.05, L * 0.6), (0.0, L)], 0.02,
                    loc=(0.1, -0.1, z), rot=(-tilt, 0, a), taper=lambda x, zz: 1.0)
    m.cyl(G, GOLD, 0.05, 0.06, loc=(0.1, -0.1, 0.12), segs=8)
    return m


# ------------------------------------------------------------------ candi (Majapahit brick)
def brick_mats(m):
    return (m.mat("M_Brick", "#b0643f"), m.mat("M_BrickDark", "#8a4a36"), m.mat("M_Stone", "#6c707a"),
            m.mat("M_Moss", "#4f7a4a"))


def candi_pilar():
    m = new("candi_pilar")
    BR, BR2, ST, MOSS = brick_mats(m)
    stone_cap(m, ST, -0.55, 0.55, -0.55, 0.55, 0.0, h=0.25, over=0.0)
    stone_cap(m, ST, -0.45, 0.45, -0.45, 0.45, 0.25, h=0.12, over=0.0)

    def broken(z, rnd):
        if z < 2.3:
            return None if False else (-1, 1)
        cut = (z - 2.3) * 1.2
        return (-0.4 + cut * 0.9, 0.4 - cut * 0.2)
    bricks(m, BR, BR2, -0.38, 0.38, -0.38, 0.38, 0.37, 3.0, course=0.2, seed=1, broken=broken)
    # decorative stone band + fallen bricks + moss
    m.box(G, ST, (0.84, 0.84, 0.1), loc=(0, 0, 1.5))
    for i, (x, y, r) in enumerate(((0.7, -0.3, 20), (0.55, 0.6, -35), (-0.7, 0.2, 60))):
        m.box(G, BR if i % 2 else BR2, (0.34, 0.18, 0.14), loc=(x, y, 0.07), rot=(0, 0, r))
    m.ico(G, MOSS, 0.3, loc=(0.1, -0.1, 2.55), scale=(1.2, 1.2, 0.35), sub=1, jitter=0.2)
    m.ico(G, MOSS, 0.25, loc=(-0.4, -0.45, 0.35), scale=(1.2, 1, 0.4), sub=1, jitter=0.2)
    return m


def candi_reruntuhan():
    m = new("candi_reruntuhan")
    BR, BR2, ST, MOSS = brick_mats(m)
    stone_cap(m, ST, -2.0, 2.0, -0.45, 0.45, 0.0, h=0.3, over=0.0)

    def broken(z, rnd):
        # stepped, broken top: high on the left, crumbling to the right
        top_right = 2.0 - max(0, z - 0.8) * 1.3 + rnd.uniform(-0.15, 0.1)
        left = -1.9 + max(0, z - 2.1) * 2.5
        if z > 2.7:
            return None
        return (left, top_right)
    bricks(m, BR, BR2, -1.9, 1.9, -0.32, 0.32, 0.3, 2.8, course=0.2, seed=3, broken=broken)
    # pilaster frames + a relief panel in andesite
    for x in (-1.9, -0.6):
        m.box(G, ST, (0.18, 0.72, 1.6), loc=(x + 0.09, 0, 1.1))
    m.box(G, ST, (1.0, 0.1, 0.8), loc=(-1.25, -0.35, 1.3))
    m.box(G, BR2, (0.7, 0.06, 0.5), loc=(-1.25, -0.4, 1.3))
    # rubble
    rnd = random.Random(4)
    for i in range(9):
        x = rnd.uniform(-1.8, 2.2)
        y = rnd.uniform(-1.0, 0.9)
        if abs(y) < 0.5:
            y = -0.8 if y < 0 else 0.8
        m.box(G, [BR, BR2, ST][i % 3], (0.35, 0.18, 0.14), loc=(x, y, 0.07), rot=(0, rnd.uniform(-10, 10), rnd.uniform(0, 90)))
    m.ico(G, MOSS, 0.4, loc=(-1.3, 0, 2.6), scale=(1.5, 1.0, 0.35), sub=1, jitter=0.2)
    m.ico(G, MOSS, 0.35, loc=(1.0, -0.4, 0.3), scale=(1.5, 1.0, 0.5), sub=1, jitter=0.2)
    return m


def tiered_roof(m, BR, BR2, ST, cx, w, d, z, tiers, h=0.32, shrink=0.8, pinnacles=True, x_half=None):
    """Stepped Majapahit roof: diminishing brick tiers with stone cornices and corner pinnacles.
    x_half = +1/-1 keeps only one half (for candi bentar split gates, inner face at x = cx)."""
    for t in range(tiers):
        x0, x1 = cx - w / 2, cx + w / 2
        if x_half == 1:
            x0 = cx
        elif x_half == -1:
            x1 = cx
        stone_cap(m, ST, x0, x1, -d / 2, d / 2, z, h=0.08, over=0.05 if x_half is None else 0.0)
        m.box(G, BR if t % 2 == 0 else BR2, (x1 - x0, d, h), loc=((x0 + x1) / 2, 0, z + 0.08 + h / 2))
        if pinnacles:
            for xx in (x0, x1):
                if x_half is not None and abs(xx - cx) < 1e-6:
                    continue
                for yy in (-d / 2, d / 2):
                    m.cyl(G, ST, 0.08 * shrink ** t + 0.02, 0.22, loc=(xx, yy, z + 0.08 + h + 0.11),
                          r2=0.02, segs=6)
        z += h + 0.08
        w *= shrink
        d *= shrink
    return z


def candi_kecil():
    m = new("candi_kecil")
    BR, BR2, ST, MOSS = brick_mats(m)
    DARK = m.mat("M_Dark", "#1c1a1f")
    # batur (platform) + stairs at the front
    stone_cap(m, ST, -1.3, 1.3, -1.3, 1.3, 0.0, h=0.2, over=0.0)
    bricks(m, BR, BR2, -1.15, 1.15, -1.15, 1.15, 0.2, 0.6, course=0.2, seed=2)
    stone_cap(m, ST, -1.15, 1.15, -1.15, 1.15, 0.6, h=0.1, over=0.04)
    for i in range(3):
        m.box(G, ST, (0.8, 0.28, 0.2 * (i + 1)), loc=(0, -1.3 - 0.28 * (2 - i) + 0.14, 0.1 * (i + 1)))
    for sg in (1, -1):
        m.box(G, ST, (0.15, 0.9, 0.75), loc=(sg * 0.47, -1.5, 0.375), taper=(1, 0.3))
    # body with door niche and kala head above
    bricks(m, BR, BR2, -0.8, 0.8, -0.8, 0.8, 0.7, 2.0, course=0.2, seed=5)
    m.box(G, DARK, (0.55, 0.12, 0.85), loc=(0, -0.79, 1.15))
    m.box(G, ST, (0.75, 0.1, 0.1), loc=(0, -0.84, 1.62))
    for sg in (1, -1):
        m.box(G, ST, (0.1, 0.1, 0.95), loc=(sg * 0.33, -0.84, 1.15))
    m.ico(G, ST, 0.16, loc=(0, -0.86, 1.8), scale=(1.3, 0.5, 1.0), sub=1)  # kala head
    for sg in (1, -1):
        m.ico(G, DARK, 0.035, loc=(sg * 0.07, -0.93, 1.83), sub=0)
    # tiered roof + finial
    z = tiered_roof(m, BR, BR2, ST, 0, 1.8, 1.8, 2.0, 4, h=0.26, shrink=0.78)
    m.lathe(G, ST, [(0.22, 0), (0.18, 0.12), (0.1, 0.25), (0.05, 0.4), (0.0, 0.5)], loc=(0, 0, z), segs=8)
    m.ico(G, MOSS, 0.3, loc=(0.8, 0.9, 0.7), scale=(1.4, 1, 0.3), sub=1, jitter=0.2)
    return m


def gapura():
    """Candi bentar: two mirrored half-towers, 3 m gap between the inner faces (x = +/-1.5), passage along Y."""
    m = new("gapura")
    BR, BR2, ST, MOSS = brick_mats(m)
    for sg in (1, -1):
        xi = sg * 1.5  # inner face
        xo = sg * 3.0  # outer face
        x0, x1 = min(xi, xo), max(xi, xo)
        stone_cap(m, ST, x0 - (0.1 if sg < 0 else 0), x1 + (0.1 if sg > 0 else 0), -0.95, 0.95, 0.0, h=0.25, over=0.0)
        bricks(m, BR, BR2, x0, x1, -0.8, 0.8, 0.25, 1.0, course=0.375, seed=7 + sg)
        stone_cap(m, ST, x0 + (0.0 if sg > 0 else -0.05), x1 + (0.05 if sg > 0 else 0.0), -0.85, 0.85, 1.0, h=0.12,
                  over=0.0)
        bricks(m, BR, BR2, x0 + (0.1 if sg > 0 else 0), x1 - (0.1 if sg < 0 else 0), -0.7, 0.7, 1.12, 2.3,
               course=0.22, seed=9 + sg)
        # relief panel on the front face
        m.box(G, ST, (0.8, 0.06, 0.7), loc=(sg * 2.3, -0.73, 1.7))
        m.box(G, BR2, (0.55, 0.05, 0.45), loc=(sg * 2.3, -0.76, 1.7))
        # stepped half roof: widest tier spans the half's width, shrinking towards the inner face
        z = 2.3
        w, d, h = 1.5, 1.5, 0.3
        for t in range(5):
            xa, xb = (xi, xi + sg * w)
            xa, xb = min(xa, xb), max(xa, xb)
            stone_cap(m, ST, xa, xb, -d / 2, d / 2, z, h=0.08, over=0.0)
            m.box(G, BR if t % 2 == 0 else BR2, (xb - xa, d, h), loc=((xa + xb) / 2, 0, z + 0.08 + h / 2))
            xo_t = xi + sg * w
            for yy in (-d / 2, d / 2):
                m.cyl(G, ST, 0.07, 0.24, loc=(xo_t, yy, z + 0.08 + h + 0.12), r2=0.015, segs=5)
            z += h + 0.08
            w *= 0.8
            d *= 0.8
            h *= 0.9
        m.box(G, ST, (0.35, 0.35, 0.3), loc=(xi + sg * 0.17, 0, z + 0.15), taper=(0.5, 0.5))
        # guardian stone lamps at the outer front corners + moss
        m.lathe(G, ST, [(0.18, 0), (0.12, 0.2), (0.08, 0.5), (0.16, 0.6), (0.12, 0.72), (0.0, 0.8)],
                loc=(sg * 2.9, -1.25, 0), segs=8)
        m.ico(G, MOSS, 0.3, loc=(sg * 2.6, 0.5, 2.35), scale=(1.4, 1, 0.3), sub=1, jitter=0.2)
    # (the gap is left empty: the game draws the glowing barrier / reward icon there)
    return m


# ------------------------------------------------------------------ small set dressing
def oncor():
    m = new("oncor")
    BAM = m.mat("M_Bamboo", "#b99a55")
    DARK = m.mat("M_Dark", "#3a2a1c")
    FIRE = m.mat("M_GlowFire", "#ff8a2a")
    CORE = m.mat("M_GlowFireCore", "#ffd84a")
    m.cyl(G, BAM, 0.045, 1.5, loc=(0, 0, 0.75), segs=8, smooth=True)
    for z in (0.35, 0.8, 1.2):  # bamboo nodes
        m.torus(G, BAM, 0.047, 0.012, loc=(0, 0, z), segs=8, rsegs=4)
    m.cyl(G, DARK, 0.05, 0.25, loc=(0, 0, 0.12), r2=0.06, segs=8)  # ground stake socket
    # oil tube (bumbung) at the top: wider slanted-cut bamboo with rope binding
    m.cyl(G, BAM, 0.07, 0.3, loc=(0, 0, 1.55), segs=10, smooth=True)
    m.torus(G, DARK, 0.072, 0.014, loc=(0, 0, 1.45), segs=10, rsegs=4)
    m.torus(G, DARK, 0.072, 0.014, loc=(0, 0, 1.5), segs=10, rsegs=4)
    m.cyl(G, DARK, 0.02, 0.1, loc=(0, 0, 1.73), segs=6)  # wick
    flame(m, FIRE, CORE, (0, 0, 1.68), h=0.42, r=0.1)
    return m


def batu():
    m = new("batu")
    ST = m.mat("M_Stone", "#6c707a")
    ST2 = m.mat("M_StoneDark", "#4b4f57")
    MOSS = m.mat("M_Moss", "#4f7a4a")
    m.ico(G, ST, 0.4, loc=(0, 0, 0.22), scale=(1.2, 1.0, 0.7), sub=1, jitter=0.2, seed=1)
    m.ico(G, ST2, 0.22, loc=(0.4, 0.2, 0.1), scale=(1.1, 1, 0.7), sub=1, jitter=0.2, seed=2)
    m.ico(G, MOSS, 0.25, loc=(-0.05, 0.05, 0.43), scale=(1.3, 1.1, 0.3), sub=1, jitter=0.2, seed=3)
    return m


def batu_besar():
    m = new("batu_besar")
    ST = m.mat("M_Stone", "#6c707a")
    ST2 = m.mat("M_StoneDark", "#4b4f57")
    MOSS = m.mat("M_Moss", "#4f7a4a")
    m.ico(G, ST, 1.0, loc=(0, 0, 0.75), scale=(1.1, 0.95, 0.85), sub=1, jitter=0.18, seed=5)
    m.ico(G, ST2, 0.7, loc=(0.9, 0.3, 0.45), scale=(1.0, 1, 0.8), sub=1, jitter=0.2, seed=6)
    m.ico(G, ST2, 0.45, loc=(-0.8, -0.5, 0.3), scale=(1.0, 1, 0.8), sub=1, jitter=0.2, seed=7)
    m.ico(G, MOSS, 0.8, loc=(0.05, 0.1, 1.45), scale=(1.1, 1.0, 0.25), sub=1, jitter=0.2, seed=8)
    return m


def arca():
    """Dwarapala: squatting guardian giant on a pedestal, club planted at his right side."""
    m = new("arca")
    ST = m.mat("M_Stone", "#6c707a")
    ST2 = m.mat("M_StoneDark", "#4b4f57")
    MOSS = m.mat("M_Moss", "#4f7a4a")
    m.box(G, ST2, (1.1, 1.0, 0.3), loc=(0, 0, 0.15))
    m.box(G, ST, (1.0, 0.9, 0.12), loc=(0, 0, 0.36))
    m.smooth_default = True
    # squatting legs: left knee up, right knee down
    m.sphere(G, ST, 0.26, loc=(0, 0.1, 0.62), scale=(1.4, 1.1, 0.8), segs=8, rings=6)  # hips
    m.loft(G, ST, [(0.22, 0.05, 0.55), (0.3, -0.3, 0.85), (0.3, -0.3, 0.45)], [0.14, 0.12, 0.1], segs=6, res=2)
    m.loft(G, ST, [(-0.22, 0.05, 0.55), (-0.34, -0.35, 0.55), (-0.3, -0.15, 0.45)], [0.14, 0.12, 0.1], segs=6, res=2)
    m.sphere(G, ST, 0.1, loc=(0.3, -0.36, 0.47), scale=(1, 1.5, 0.6), segs=8, rings=6)
    # fat torso + belly
    m.loft(G, ST, [(0, 0.1, 0.65), (0, 0.05, 1.0), (0, 0.1, 1.35), (0, 0.12, 1.5)],
           [(0.3, 0.26), (0.36, 0.32), (0.34, 0.24), (0.14, 0.12)], segs=10, res=2)
    m.sphere(G, ST, 0.25, loc=(0, -0.13, 0.95), scale=(1.1, 0.8, 1.0), segs=8, rings=6)
    # arms: left hand on knee, right hand on the club head
    m.loft(G, ST, [(0.34, 0.1, 1.35), (0.46, 0.0, 1.05), (0.34, -0.25, 0.9)], [0.1, 0.09, 0.08], segs=6, res=2)
    m.loft(G, ST, [(-0.34, 0.1, 1.35), (-0.5, -0.05, 1.12), (-0.5, -0.25, 1.2)], [0.1, 0.09, 0.08], segs=6, res=2)
    # club planted on the ground: head at the top under his hand
    m.cyl(G, ST, 0.05, 0.9, loc=(-0.52, -0.3, 0.8), segs=8)
    m.sphere(G, ST, 0.17, loc=(-0.52, -0.3, 1.25), scale=(1, 1, 1.2), segs=8, rings=6)
    for k in range(6):
        a = TAU * k / 6
        m.ico(G, ST2, 0.05, loc=(-0.52 + math.cos(a) * 0.16, -0.3 + math.sin(a) * 0.16, 1.28), sub=0)
    # head: bulging eyes, fangs, curly hair, crown band
    hc = V((0, -0.02, 1.68))
    m.sphere(G, ST, 0.24, loc=hc, scale=(1.05, 0.95, 1.0), segs=10, rings=7)
    m.sphere(G, ST, 0.08, loc=hc + V((0, -0.22, -0.03)), segs=8, rings=6)
    for sg in (1, -1):
        m.sphere(G, ST, 0.07, loc=hc + V((sg * 0.1, -0.19, 0.06)), segs=8, rings=6)
        m.sphere(G, ST2, 0.03, loc=hc + V((sg * 0.1, -0.25, 0.06)), segs=6, rings=4)
        m.cyl(G, ST, 0.03, 0.12, loc=hc + V((sg * 0.09, -0.2, -0.15)), r2=0.004, segs=5)
    for i in range(9):
        a = math.pi * i / 8
        m.ico(G, ST2, 0.09, loc=hc + V((math.cos(a) * 0.22, 0.05 + math.sin(a) * 0.12, 0.12)), sub=0, smooth=False)
    m.torus(G, ST2, 0.23, 0.03, loc=hc + V((0, 0, 0.08)), segs=12, rsegs=4)
    m.smooth_default = False
    m.ico(G, MOSS, 0.2, loc=(0.2, 0.2, 1.5), scale=(1.4, 1.2, 0.4), sub=1, jitter=0.2)
    m.ico(G, MOSS, 0.25, loc=(-0.3, 0.3, 0.42), scale=(1.4, 1.2, 0.4), sub=1, jitter=0.2)
    return m


def dermaga():
    m = new("dermaga")
    WOOD = m.mat("M_Wood", "#7a5236")
    WOOD2 = m.mat("M_WoodDark", "#4e3423")
    ROPE = m.mat("M_Rope", "#b99a55")
    rnd = random.Random(3)
    n = 14
    w = 4.0 / n
    for i in range(n):  # deck planks along X, top at z = 0
        y = -2 + w * (i + 0.5)
        dz = rnd.uniform(-0.02, 0.0)
        L = 4.0 + rnd.uniform(-0.15, 0.05)
        m.box(G, WOOD if rnd.random() < 0.7 else WOOD2, (L, w - 0.03, 0.08), loc=(rnd.uniform(-0.05, 0.05), y, -0.04 + dz),
              rot=(0, 0, rnd.uniform(-0.8, 0.8)))
    for x in (-1.7, 0, 1.7):  # joists
        m.box(G, WOOD2, (0.18, 4.0, 0.18), loc=(x, 0, -0.17))
    for x in (-1.85, 1.85):
        for y in (-1.85, 1.85):
            m.cyl(G, WOOD2, 0.12, 1.8, loc=(x, y, -0.6), segs=8)
            m.cyl(G, WOOD2, 0.12, 0.08, loc=(x, y, 0.3), r2=0.04, segs=8)
            m.torus(G, ROPE, 0.13, 0.025, loc=(x, y, 0.12), segs=8, rsegs=4)
    return m


def perahu():
    """Jukung: slim dugout hull with upswept ends, two bamboo outriggers (cadik)."""
    m = new("perahu")
    WOOD = m.mat("M_Wood", "#7a5236")
    PAINT = m.mat("M_Paint", "#2c5f8a")
    BAM = m.mat("M_Bamboo", "#c9ad6a")
    RED = m.mat("M_Red", "#b3262e")
    # hull stations along Y: (y, half width, depth, sheer z)
    st = []
    N = 13
    for i in range(N):
        t = i / (N - 1)
        y = -2.0 + 4.0 * t
        e = abs(t - 0.5) * 2
        hw = 0.34 * (1 - e ** 2.2) + 0.02
        depth = 0.32 * (1 - e ** 3) + 0.04
        sheer = 0.45 + 0.35 * e ** 3
        st.append((y, hw, depth, sheer))
    prof = 7  # U profile points from left gunwale to right gunwale
    outer, inner = [], []
    for y, hw, depth, sheer in st:
        ro, ri = [], []
        for k in range(prof):
            a = math.pi * k / (prof - 1)  # 0 -> left, pi -> right
            x = hw * math.cos(a)
            z = sheer - depth * math.sin(a) ** 0.8 * 1.0 - (sheer - 0.45) * 0.0
            ro.append((x, y, z))
            ri.append((x * 0.85, y, z + 0.04 * math.sin(a) + 0.02))
        outer.append(ro)
        inner.append(ri)
    verts, faces_o, faces_i = [], [], []
    for ring in outer:
        verts += ring
    off = len(verts)
    for ring in inner:
        verts += ring
    for i in range(N - 1):
        for k in range(prof - 1):
            a = i * prof + k
            faces_o.append((a, a + prof, a + prof + 1, a + 1))
            b = off + a
            faces_i.append((b, b + 1, b + prof + 1, b + prof))
    faces_rim = []
    for i in range(N - 1):
        for k in (0, prof - 1):
            a, b = i * prof + k, off + i * prof + k
            f = (a, a + prof, b + prof, b) if k == prof - 1 else (a, b, b + prof, a + prof)
            faces_rim.append(f)
    # hull verts lifted so the keel is at z ~ 0.1 (boat sits in water; root = waterline centre)
    rev = lambda fs: [tuple(reversed(f)) for f in fs]
    m.mesh(G, PAINT, verts, rev(faces_o), smooth=True)
    m.mesh(G, WOOD, verts, rev(faces_i), smooth=True)
    m.mesh(G, RED, verts, rev(faces_rim), smooth=False)
    # upswept prow ornaments
    for sg in (1, -1):
        m.prism(G, RED, [(-0.03, 0), (0.03, 0), (0.06, 0.3), (0.0, 0.45), (-0.05, 0.3)], 0.04,
                loc=(0, sg * 2.0, 0.78), rot=(0, 0, 0))
        m.sphere(G, (PAINT if sg > 0 else WOOD), 0.05, loc=(sg * 0.18, -1.2, 0.5), segs=8, rings=5)  # eye
    # outriggers
    for sg in (1, -1):
        m.cyl(G, BAM, 0.06, 3.2, loc=(sg * 1.3, 0, 0.18), rot=(90, 0, 0), segs=8, smooth=True)
        for yb in (-0.9, 0.9):
            m.loft(G, BAM, [(0, yb, 0.55), (sg * 0.7, yb, 0.62), (sg * 1.3, yb, 0.25)], [0.03, 0.03, 0.03],
                   segs=5, res=3, ref=(0, 1, 0))
    m.cyl(G, WOOD, 0.04, 1.4, loc=(0, -0.5, 1.1), segs=6)  # short mast
    return m


def pendopo():
    """Hub pavilion 8x8 m: raised stone floor, 4 soko guru + 12 perimeter pillars, joglo roof."""
    m = new("pendopo")
    ST = m.mat("M_Stone", "#6c707a")
    WOOD = m.mat("M_Wood", "#6e4630")
    ROOF = m.mat("M_Roof", "#5a3328")
    GOLD = m.mat("M_Gold", "#d9a93a")
    m.box(G, ST, (8.4, 8.4, 0.35), loc=(0, 0, 0.175), bevel=0.03)
    m.box(G, ST, (8.0, 8.0, 0.08), loc=(0, 0, 0.39))
    for i in range(2):  # front steps
        m.box(G, ST, (2.4, 0.35, 0.18 * (i + 1)), loc=(0, -4.2 - 0.35 * (1 - i) - 0.175, 0.09 * (i + 1)))
    # perimeter pillars on umpak stones
    ring = [-3.6, -1.2, 1.2, 3.6]
    for x in ring:
        for y in ring:
            inner = abs(x) < 2 and abs(y) < 2
            h = 4.2 if inner else 2.6
            r = 0.14 if inner else 0.11
            m.box(G, ST, (0.36, 0.36, 0.14), loc=(x, y, 0.5), taper=(0.7, 0.7))
            m.box(G, WOOD, (r * 2, r * 2, h), loc=(x, y, 0.57 + h / 2))
            if inner:
                m.box(G, GOLD, (r * 2 + 0.04, r * 2 + 0.04, 0.1), loc=(x, y, 0.9))
    # beams (blandar) on the perimeter and the tumpang sari under the brunjung
    for s in (-3.6, 3.6):
        m.box(G, WOOD, (7.5, 0.2, 0.22), loc=(0, s, 3.25))
        m.box(G, WOOD, (0.2, 7.5, 0.22), loc=(s, 0, 3.25))
    for t, w in enumerate((2.8, 2.5, 2.2)):
        z = 4.8 + t * 0.18
        for s in (-1, 1):
            m.box(G, WOOD, (w, 0.18, 0.18), loc=(0, s * w / 2, z))
            m.box(G, WOOD, (0.18, w, 0.18), loc=(s * w / 2, 0, z))
    # roofs: lower penanggap (shallow, wide eaves) + steep central brunjung + ridge ornaments
    def hip_roof(z0, w0, z1, w1, ridge=0.0, thick=0.12):
        v = [(-w0, -w0, z0), (w0, -w0, z0), (w0, w0, z0), (-w0, w0, z0),
             (-w1 - ridge, -w1, z1), (w1 + ridge, -w1, z1), (w1 + ridge, w1, z1), (-w1 - ridge, w1, z1)]
        v += [(x, y, z - thick) for x, y, z in v[:4]]
        f = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7),
             (8, 9, 1, 0), (9, 10, 2, 1), (10, 11, 3, 2), (11, 8, 0, 3), (11, 10, 9, 8)]
        m.mesh(G, ROOF, v, f, smooth=False)
    hip_roof(3.0, 4.9, 4.8, 1.7)
    hip_roof(4.75, 1.9, 7.0, 0.12, ridge=0.9)
    m.box(G, ROOF, (2.2, 0.2, 0.12), loc=(0, 0, 7.05))
    for sg in (1, -1):
        m.prism(G, GOLD, [(-0.18, 0), (0.18, 0), (0.1, 0.35), (0.0, 0.55), (-0.1, 0.35)], 0.08,
                loc=(sg * 1.05, 0, 7.08), rot=(0, 0, 0))
    m.sphere(G, GOLD, 0.16, loc=(0, 0, 7.25), segs=10, rings=6)
    return m


def sumur():
    """Stone well = run-start portal: glowing water inside, timber frame with a small roof."""
    m = new("sumur")
    ST = m.mat("M_Stone", "#6c707a")
    WOOD = m.mat("M_Wood", "#6e4630")
    ROOF = m.mat("M_Roof", "#5a3328")
    WATER = m.mat("M_GlowWater", "#5fe0c8")
    m.lathe(G, ST, [(0.62, 0.0), (0.65, 0.12), (0.6, 0.18), (0.6, 0.62), (0.68, 0.68), (0.68, 0.78), (0.48, 0.78),
                    (0.48, 0.1)], segs=14, smooth=False)
    m.cyl(G, WATER, 0.49, 0.04, loc=(0, 0, 0.5), segs=14)
    for k in range(7):  # stone blocks pattern ring
        a = TAU * k / 7
        m.box(G, ST, (0.32, 0.1, 0.18), loc=(math.cos(a) * 0.63, math.sin(a) * 0.63, 0.35), rot=(0, 0, math.degrees(a) + 90))
    for sg in (1, -1):
        m.box(G, WOOD, (0.1, 0.1, 1.2), loc=(sg * 0.6, 0, 1.2))
    m.box(G, WOOD, (1.5, 0.1, 0.1), loc=(0, 0, 1.75))
    m.cyl(G, WOOD, 0.05, 1.3, loc=(0, 0, 1.55), rot=(0, 90, 0), segs=8)  # winch
    m.cyl(G, m.mat("M_Rope", "#b99a55"), 0.012, 0.5, loc=(0, 0, 1.28), segs=4)
    m.lathe(G, WOOD, [(0.08, 0), (0.1, 0.16), (0, 0.16)], loc=(0, 0, 0.9), segs=8)  # bucket
    # little gable roof (atap)
    v = [(-0.85, -0.55, 1.75), (0.85, -0.55, 1.75), (0.85, 0.0, 2.1), (-0.85, 0.0, 2.1),
         (-0.85, 0.55, 1.75), (0.85, 0.55, 1.75)]
    m.mesh(G, ROOF, v, [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)])
    return m


def gamelan():
    m = new("gamelan")
    WOOD = m.mat("M_Wood", "#7a2a22")
    GOLD = m.mat("M_Gold", "#c89b3c")
    DARK = m.mat("M_Dark", "#241c18")
    # gong stand (gayor) with a big hanging gong
    for sg in (1, -1):
        m.box(G, WOOD, (0.3, 0.5, 0.15), loc=(sg * 0.7, 0, 0.075), bevel=0.02)
        m.box(G, WOOD, (0.12, 0.12, 1.7), loc=(sg * 0.7, 0, 0.95))
        m.prism(G, GOLD, [(-0.12, 0), (0.12, 0), (0.05, 0.25), (0, 0.35), (-0.05, 0.25)], 0.06,
                loc=(sg * 0.7, 0, 1.85))
    m.box(G, WOOD, (1.7, 0.14, 0.18), loc=(0, 0, 1.75))
    m.prism(G, WOOD, [(-0.6, 0), (0.6, 0), (0.35, 0.18), (0, 0.28), (-0.35, 0.18)], 0.1, loc=(0, 0, 1.84))
    m.cyl(G, DARK, 0.01, 0.2, loc=(0, 0, 1.58), segs=4)
    m.lathe(G, GOLD, [(0.0, -0.05), (0.52, -0.02), (0.55, 0.06), (0.5, 0.1), (0.16, 0.1), (0.12, 0.2), (0, 0.2)],
            loc=(0, 0.02, 1.0), rot=(90, 0, 0), segs=20, smooth=True)
    # saron in front: wooden trough + 7 bronze bars
    m.box(G, WOOD, (1.1, 0.4, 0.28), loc=(0, -0.7, 0.14), taper=(0.9, 0.8), bevel=0.02)
    for i in range(7):
        m.box(G, GOLD, (0.11, 0.3 - i * 0.012, 0.03), loc=(-0.42 + i * 0.14, -0.7, 0.3))
    m.cyl(G, DARK, 0.015, 0.4, loc=(0.4, -1.0, 0.2), rot=(70, 0, 30), segs=5)  # mallet
    return m


def altar_dewa():
    m = new("altar_dewa")
    ST = m.mat("M_Stone", "#6c707a")
    ST2 = m.mat("M_StoneDark", "#4b4f57")
    GOLD = m.mat("M_Gold", "#d9a93a")
    MOSS = m.mat("M_Moss", "#4f7a4a")
    m.box(G, ST2, (1.0, 1.0, 0.18), loc=(0, 0, 0.09), bevel=0.02)
    m.box(G, ST, (0.8, 0.8, 0.12), loc=(0, 0, 0.24))
    m.box(G, ST, (0.5, 0.5, 0.4), loc=(0, 0, 0.5), taper=(0.9, 0.9))
    m.box(G, GOLD, (0.52, 0.52, 0.05), loc=(0, 0, 0.62))
    # padma (lotus cushion) top
    m.lathe(G, ST, [(0.28, 0.7), (0.4, 0.8), (0.42, 0.88), (0.32, 0.92), (0.3, 0.98), (0.0, 0.98)], segs=12,
            smooth=False)
    for k in range(8):
        a = TAU * k / 8
        m.prism(G, ST2, [(-0.08, 0), (0.08, 0), (0.0, 0.14)], 0.03,
                loc=(math.cos(a) * 0.36, math.sin(a) * 0.36, 0.74), rot=(-15, 0, math.degrees(a) - 90 + 180))
    m.ico(G, MOSS, 0.2, loc=(0.35, 0.3, 0.2), scale=(1.4, 1.2, 0.4), sub=1, jitter=0.2)
    return m


def lentera():
    """Standing bracket post with a hanging brass lamp (the glow is M_GlowLamp)."""
    m = new("lentera")
    WOOD = m.mat("M_Wood", "#4e3423")
    GOLD = m.mat("M_Gold", "#c89b3c")
    LAMP = m.mat("M_GlowLamp", "#ffc861")
    m.box(G, WOOD, (0.3, 0.3, 0.12), loc=(0, 0, 0.06), bevel=0.02)
    m.box(G, WOOD, (0.1, 0.1, 2.3), loc=(0, 0, 1.2))
    m.loft(G, WOOD, [(0, 0, 2.1), (0.25, -0.02, 2.3), (0.55, 0, 2.3)], [0.04, 0.035, 0.03], segs=6, res=2)
    m.cyl(G, GOLD, 0.008, 0.25, loc=(0.55, 0, 2.17), segs=4)
    c = V((0.55, 0, 1.85))
    m.lathe(G, GOLD, [(0.02, 0.3), (0.16, 0.2), (0.17, 0.17), (0.0, 0.17)], loc=c - V((0, 0, 0.12)), segs=8)
    m.lathe(G, LAMP, [(0.09, 0.0), (0.13, 0.08), (0.13, 0.17), (0.0, 0.17)], loc=c - V((0, 0, 0.12)), segs=8)
    m.lathe(G, GOLD, [(0.0, -0.05), (0.12, 0.0), (0.1, 0.02), (0.0, 0.02)], loc=c - V((0, 0, 0.12)), segs=8)
    m.cyl(G, GOLD, 0.02, 0.12, loc=c - V((0, 0, 0.23)), r2=0.002, rot=(180, 0, 0), segs=5)
    return m


def peti():
    """Reward chest; the lid is under pivot `lid` (hinge at the back top edge; rotate -X to open)."""
    m = new("peti")
    WOOD = m.mat("M_Wood", "#6e4630")
    GOLD = m.mat("M_Gold", "#d9a93a")
    RED = m.mat("M_Red", "#8a2a22")
    m.box(G, WOOD, (0.9, 0.55, 0.45), loc=(0, 0, 0.26), bevel=0.02)
    m.box(G, RED, (0.8, 0.02, 0.28), loc=(0, -0.28, 0.26))
    for x in (-0.36, 0.36):
        m.box(G, GOLD, (0.07, 0.59, 0.49), loc=(x, 0, 0.26))
    for sg in (1, -1):
        m.box(G, GOLD, (0.14, 0.6, 0.06), loc=(sg * 0.45, 0, 0.05))
    m.pivot("lid", (0, 0.28, 0.48))
    m.lathe("lid", WOOD, [(0.28, -0.45), (0.28, 0.45)], loc=(0, 0, 0.48), rot=(0, 90, 0), scale=(1, 1.0, 1),
            segs=12, smooth=True)
    for x in (-0.36, 0.0, 0.36):
        m.torus("lid", GOLD, 0.285, 0.022, loc=(x, 0, 0.48), rot=(0, 90, 0), segs=12, rsegs=4)
    m.box("lid", GOLD, (0.14, 0.05, 0.16), loc=(0, -0.29, 0.5), bevel=0.01)
    m.box("lid", WOOD, (0.9, 0.55, 0.02), loc=(0, 0, 0.485))
    # clip the lower half of the lid cylinder into the box: flatten verts below the rim
    for v in m.groups["lid"].verts:
        if v.co.z < 0.48:
            v.co.z = 0.48
        v.co.y *= 0.98
    return m


# ------------------------------------------------------------------ pickups
def orb_dewa():
    m = new("orb_dewa")
    GOLD = m.mat("M_Gold", "#d9a93a")
    CORE = m.mat("M_GlowOrb", "#ffffff")
    c = V((0, 0, 0.25))
    m.sphere(G, CORE, 0.14, loc=c, segs=14, rings=10, smooth=True)
    m.smooth_default = True
    for rot in ((0, 0, 0), (90, 0, 0), (90, 0, 90), (0, 45, 45)):
        m.torus(G, GOLD, 0.2, 0.014, loc=c, rot=rot, segs=20, rsegs=4)
    for k in range(4):  # little flame-shaped petals (filigree) around the equator
        a = 90 * k + 45
        m.prism(G, GOLD, [(-0.03, 0), (0.03, 0), (0.0, 0.07)], 0.015, loc=c + V((math.cos(math.radians(a)) * 0.21,
                math.sin(math.radians(a)) * 0.21, 0)), rot=(0, 0, a - 90))
    m.lathe(G, GOLD, [(0.0, 0.0), (0.06, 0.0), (0.03, 0.04), (0.0, 0.06)], loc=c + V((0, 0, 0.19)), segs=8)
    m.lathe(G, GOLD, [(0.0, 0.0), (0.03, 0.02), (0.06, 0.06), (0.0, 0.06)], loc=(0, 0, 0.0), segs=8)
    return m


def kepeng():
    """Ancient coin with a square hole, standing on its edge facing -Y (0.4 m across)."""
    m = new("kepeng")
    GOLD = m.mat("M_Gold", "#e0b040")
    DARK = m.mat("M_GoldDark", "#a87a22")
    R, h, t = 0.2, 0.06, 0.04
    n = 24
    verts, faces = [], []
    sq = []
    for i in range(n):  # matching points on the square hole perimeter
        a = TAU * i / n + math.pi / 4
        x, z = math.cos(a), math.sin(a)
        s = max(abs(x), abs(z))
        sq.append((x / s * h, z / s * h))
    for yy in (-t / 2, t / 2):
        for i in range(n):
            a = TAU * i / n + math.pi / 4
            verts.append((math.cos(a) * R, yy, math.sin(a) * R))
        for i in range(n):
            verts.append((sq[i][0], yy, sq[i][1]))
    for i in range(n):
        j = (i + 1) % n
        b = 2 * n
        faces.append((i, n + i, n + j, j))  # front (y-); all faces are flipped when added
        faces.append((b + i, b + j, b + n + j, b + n + i))
        faces.append((i, j, b + j, b + i))  # rim
        faces.append((n + i, b + n + i, b + n + j, n + j))  # hole wall
    m.mesh(G, GOLD, verts, [tuple(reversed(f)) for f in faces])
    for v in m.groups[G].verts:
        v.co.z += R
    # raised rim + four embossed glyph blocks
    m.torus(G, DARK, R - 0.012, 0.012, loc=(0, 0, R), rot=(90, 0, 0), segs=24, rsegs=4)
    for (x, z) in ((0, 0.12), (0, -0.12), (0.12, 0), (-0.12, 0)):
        m.box(G, DARK, (0.045, t + 0.016, 0.045), loc=(x, 0, R + z))
    return m


def tirta():
    """Tirta amerta: small golden kendi (spouted water jug) with glowing water."""
    m = new("tirta")
    GOLD = m.mat("M_Gold", "#d9a93a")
    WATER = m.mat("M_GlowWater", "#6fe8ff")
    m.smooth_default = True
    m.lathe(G, GOLD, [(0.0, 0.0), (0.09, 0.0), (0.1, 0.03), (0.17, 0.12), (0.18, 0.2), (0.14, 0.29), (0.06, 0.33),
                      (0.045, 0.4), (0.065, 0.44), (0.05, 0.45)], segs=16)
    m.cyl(G, WATER, 0.045, 0.02, loc=(0, 0, 0.445), segs=10)
    m.loft(G, GOLD, [(0, -0.12, 0.22), (0, -0.2, 0.28), (0, -0.25, 0.34)], [0.045, 0.03, 0.022], segs=8, res=2,
           cap1=False)
    m.torus(G, GOLD, 0.175, 0.012, loc=(0, 0, 0.18), segs=16, rsegs=4)
    for i in range(3):  # droplets rising
        m.sphere(G, WATER, 0.025 - i * 0.004, loc=(0.02 * (i - 1), -0.26 - i * 0.02, 0.4 + i * 0.07), segs=8, rings=5)
    m.sphere(G, WATER, 0.03, loc=(0, 0, 0.5), segs=8, rings=5)
    return m


def wijayakusuma():
    """Kembang Wijayakusuma: large white night-blooming flower (epiphyllum) on a curved stem."""
    m = new("wijayakusuma")
    LEAF = m.mat("M_Leaf", "#3f7a4a")
    WHITE = m.mat("M_GlowFlower", "#fff6e6")
    GOLD = m.mat("M_Gold", "#f2d27a")
    m.smooth_default = True
    # flat leaf-stem (phylloclade) curving up
    m.loft(G, LEAF, [(0, 0.1, 0.0), (0.02, 0.12, 0.08), (0, 0.06, 0.16), (0, 0.0, 0.2)],
           [(0.035, 0.012), (0.05, 0.012), (0.03, 0.012), (0.02, 0.012)], segs=6, res=2)
    c = V((0, -0.02, 0.24))
    for ring, (cnt, L, tilt, w) in enumerate(((10, 0.19, 60, 0.05), (8, 0.15, 35, 0.045), (6, 0.1, 15, 0.035))):
        for k in range(cnt):
            a = 360 * k / cnt + ring * 17
            m.prism(G, WHITE, [(-w, 0), (w, 0), (w * 0.8, L * 0.7), (0.0, L)], 0.012,
                    loc=c + V((0, 0, ring * 0.015)), rot=(-tilt, 0, a), smooth=True)
    for k in range(7):  # stamens
        a = TAU * k / 7
        m.loft(G, GOLD, [c, c + V((math.cos(a) * 0.04, math.sin(a) * 0.04, 0.1))], [0.004, 0.004], segs=4)
        m.sphere(G, GOLD, 0.01, loc=c + V((math.cos(a) * 0.04, math.sin(a) * 0.04, 0.1)), segs=6, rings=4)
    return m


BUILDERS = {f.__name__: f for f in (
    beringin, pohon_mati, bakau, semak, pakis, bunga_glow, teratai, candi_pilar, candi_reruntuhan, candi_kecil,
    gapura, oncor, batu, batu_besar, arca, dermaga, perahu, pendopo, sumur, gamelan, altar_dewa, lentera, peti,
    orb_dewa, kepeng, tirta, wijayakusuma)}

if __name__ == "__main__":
    run_cli(BUILDERS)

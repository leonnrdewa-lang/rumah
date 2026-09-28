#!/usr/bin/env python3
"""Hanoman Duta - bosses of Muara Kalimas: sura (shark king) and baya (crocodile lord).

Run:  python3 hanoman/blender/bosses.py [sura|baya] [--no-preview] [--no-export]

Both are modelled in a horizontal swimming/crawling pose, head towards -Y, root on the ground.
sura:  body (torso centre) > head > jaw ; body > arm_l/arm_r (pectoral fins) ; body > tail > tail_tip
baya:  body > head > jaw ; body > arm_l/arm_r (front legs) ; body > tail > tail_tip ;
       root > leg_l/leg_r (hind legs)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import V, TAU, Model, run_cli  # noqa: E402
from characters import jamang  # noqa: E402


def teeth_row(m, g, mt, pts, length, r, up):
    for p in pts:
        m.cyl(g, mt, r, length, loc=V(p) + V(0, 0, length / 2 if up else -length / 2), r2=0.003,
              rot=(0, 0, 0) if up else (180, 0, 0), segs=5)


def u_curve(y0, y1, half_w, z, n, x_shrink=0.35):
    """Points along a U-shaped jaw line from the left hinge round the snout to the right hinge."""
    pts = []
    for i in range(n):
        t = i / (n - 1)  # 0..1 left->right
        a = math.pi * t
        x = half_w * math.cos(a) * (1 - x_shrink * math.sin(a) ** 4)
        y = y0 + (y1 - y0) * math.sin(a) ** 0.6
        pts.append((x, y, z))
    return pts


# ------------------------------------------------------------------ Sura
def sura():
    m = Model("sura")
    SKIN = m.mat("M_Skin", "#5b7590")
    BELLY = m.mat("M_Belly", "#dfe2da")
    GOLD = m.mat("M_Gold", "#d9a93a")
    SASH = m.mat("M_Batik", "#7c2a24")
    EYE = m.mat("M_GlowEye", "#ffd23a")
    zc = 0.8  # body axis height; belly underside ~0.25 m above the ground/water
    m.pivot("body", (0, 0, zc))
    # torso + pale belly (slightly lower & smaller so it shows underneath)
    tor = [(0, -1.15, zc), (0, -0.4, zc + 0.02), (0, 0.45, zc), (0, 1.1, zc - 0.03)]
    m.loft("body", SKIN, tor, [(0.56, 0.52), (0.6, 0.58), (0.5, 0.48), (0.33, 0.31)], segs=16, res=3,
           ref=(0, 0, 1), cap0=False, cap1=False)
    m.loft("body", BELLY, [(x, y, z - 0.13) for x, y, z in tor], [(0.5, 0.44), (0.54, 0.5), (0.44, 0.41), (0.27, 0.25)],
           segs=16, res=3, ref=(0, 0, 1), cap0=False, cap1=False)
    # dorsal fin (outline x -> world +Y after rot)
    m.prism("body", SKIN, [(-0.6, -0.1), (0.45, -0.1), (0.2, 0.25), (0.5, 0.95), (0.15, 0.75), (-0.05, 0.55),
                           (-0.35, 0.25)], 0.26, loc=(0, -0.2, zc + 0.5), rot=(0, 0, 90),
            taper=lambda x, z: max(0.15, 1 - z * 0.9))
    m.prism("body", SKIN, [(-0.12, 0), (0.12, 0), (0.1, 0.25)], 0.05, loc=(0, 0.9, zc + 0.27), rot=(0, 0, 90))
    # torn batik sash (kain) across the body: band + torn trailing ends with gold parang marks
    m.torus("body", SASH, 0.6, 0.06, loc=(0, 0.35, zc - 0.03), rot=(90, 0, 0), scale=(0.9, 0.86, 1.0),
            segs=20, rsegs=5)
    m.torus("body", GOLD, 0.6, 0.022, loc=(0, 0.28, zc - 0.03), rot=(90, 0, 0), scale=(0.92, 0.88, 1.0),
            segs=20, rsegs=4)
    for sg in (1, -1):
        m.prism("body", SASH, [(0, 0), (0.18, 0), (0.22, -0.55), (0.14, -0.4), (0.08, -0.7), (0.0, -0.45)], 0.03,
                loc=(sg * 0.52, 0.4, zc - 0.1), rot=(0, sg * -20, 90), scale=(1, 1, 1))
        for i in range(5):  # gold parang diagonal strokes on the band
            a = math.radians(-60 + i * 30)
            m.box("body", GOLD, (0.03, 0.04, 0.12), loc=(sg * 0.54 * math.cos(a) * 0.95, 0.38, zc + 0.53 * math.sin(a)),
                  rot=(0, 40 * sg + math.degrees(a), 0))
    # scars: pale slashes on the flanks
    for sg, (y, z, r) in ((1, (-0.5, zc + 0.25, 30)), (1, (-0.3, zc + 0.3, 25)), (-1, (0.1, zc + 0.2, -35)),
                          (-1, (-0.7, zc + 0.05, 20))):
        m.box("body", BELLY, (0.05, 0.45, 0.04), loc=(sg * 0.58, y, z), rot=(r, 0, sg * 8))
    # pectoral fins (arm_l / arm_r), outline: x outward, z backward
    for sg, side in ((1, "l"), (-1, "r")):
        root = V(sg * 0.45, -0.55, zc - 0.28)
        m.pivot("arm_" + side, root, parent="body")
        m.prism("arm_" + side, SKIN, [(0, -0.3), (0, 0.3), (0.5, 0.45), (1.05, 0.8), (0.7, 0.3)], 0.16,
                loc=root, rot=(-90, 22 * sg, 0), scale=(sg, 1, 1), taper=lambda x, z: max(0.2, 1 - x * 0.9))
        # small pelvic fins on the body
        m.prism("body", SKIN, [(0, -0.12), (0, 0.15), (0.35, 0.35)], 0.04, loc=V(sg * 0.3, 0.8, zc - 0.28),
                rot=(-90, 30 * sg, 0), scale=(sg, 1, 1))
    # head: tapered snout, crown, glowing eyes, gills, upper teeth
    hp = V(0, -1.15, zc)
    m.pivot("head", hp, parent="body")
    hd = [(0, -1.0, zc + 0.02), (0, -1.55, zc + 0.08), (0, -2.05, zc + 0.08), (0, -2.35, zc + 0.02)]
    m.loft("head", SKIN, hd, [(0.57, 0.53), (0.5, 0.42), (0.32, 0.28), (0.04, 0.05)], segs=16, res=3,
           ref=(0, 0, 1), cap0=False)
    m.loft("head", BELLY, [(0, -1.0, zc - 0.12), (0, -1.5, zc - 0.12), (0, -1.9, zc - 0.07)],
           [(0.5, 0.42), (0.42, 0.3), (0.2, 0.15)], segs=14, res=2, ref=(0, 0, 1), cap0=False)
    m.box("head", SASH, (0.62, 0.8, 0.06), loc=(0, -1.72, zc - 0.2), rot=(-4, 0, 0), bevel=0.02)  # mouth gap
    teeth_row(m, "head", BELLY, u_curve(-1.35, -2.15, 0.32, zc - 0.15, 13), 0.12, 0.035, up=False)
    for sg in (1, -1):
        m.sphere("head", EYE, 0.09, loc=(sg * 0.37, -1.72, zc + 0.16), scale=(0.5, 1.0, 0.8), segs=10, rings=6)
        m.box("head", SKIN, (0.1, 0.22, 0.05), loc=(sg * 0.35, -1.72, zc + 0.25), rot=(0, sg * 25, sg * 10))  # brow
        for i in range(3):
            m.box("head", SASH, (0.03, 0.03, 0.3), loc=(sg * 0.54, -1.2 + i * 0.12, zc), rot=(0, sg * 10, 0))
    jamang(m, "head", GOLD, EYE, (0, -1.35, zc + 0.47), 0.3, k=2.0, tall=0.45)
    # jaw
    jp = V(0, -1.25, zc - 0.25)
    m.pivot("jaw", jp, parent="head")
    m.loft("jaw", SKIN, [(0, -1.2, zc - 0.28), (0, -1.6, zc - 0.28), (0, -2.0, zc - 0.26), (0, -2.15, zc - 0.24)],
           [(0.46, 0.13), (0.4, 0.13), (0.22, 0.1), (0.05, 0.05)], segs=12, res=2, ref=(0, 0, 1))
    m.loft("jaw", BELLY, [(0, -1.2, zc - 0.34), (0, -1.6, zc - 0.34), (0, -1.95, zc - 0.31)],
           [(0.42, 0.1), (0.36, 0.1), (0.15, 0.06)], segs=12, res=2, ref=(0, 0, 1))
    teeth_row(m, "jaw", BELLY, u_curve(-1.4, -2.06, 0.3, zc - 0.2, 11), 0.1, 0.032, up=True)
    # tail + caudal fin on tail_tip
    tp = V(0, 1.05, zc - 0.03)
    m.pivot("tail", tp, parent="body")
    m.loft("tail", SKIN, [(0, 0.95, zc - 0.03), (0, 1.6, zc), (0, 2.25, zc + 0.02)],
           [(0.34, 0.32), (0.22, 0.22), (0.1, 0.13)], segs=12, res=3, ref=(0, 0, 1), cap0=False)
    m.prism("tail", SKIN, [(-0.1, 0), (0.15, 0), (0.1, -0.22)], 0.04, loc=(0, 1.8, zc - 0.15), rot=(0, 0, 90))
    ttp = V(0, 2.2, zc + 0.02)
    m.pivot("tail_tip", ttp, parent="tail")
    m.prism("tail_tip", SKIN, [(0, -0.12), (0.5, -0.62), (0.38, -0.12), (0.36, 0.05), (0.95, 1.0), (0.55, 0.85),
                               (0.0, 0.16)], 0.2, loc=ttp + V(0, -0.05, 0), rot=(0, 0, 90),
            taper=lambda x, z: max(0.15, 1 - x * 1.0))
    m.box("tail_tip", BELLY, (0.03, 0.4, 0.04), loc=ttp + V(0.05, 0.35, 0.4), rot=(50, 0, 0))  # scar notch
    return m


# ------------------------------------------------------------------ Baya
def baya():
    m = Model("baya")
    SCALE = m.mat("M_Scales", "#556b30")
    BELLY = m.mat("M_Belly", "#cdbf86")
    GOLD = m.mat("M_Gold", "#d9a93a")
    KAIN = m.mat("M_Kain", "#9c2a24")
    EYE = m.mat("M_GlowEye", "#ffb52a")
    zc = 0.55
    m.pivot("body", (0, 0, zc))
    tor = [(0, -1.25, zc + 0.02), (0, -0.5, zc + 0.05), (0, 0.4, zc + 0.03), (0, 1.15, zc - 0.03)]
    m.loft("body", SCALE, tor, [(0.42, 0.3), (0.62, 0.36), (0.6, 0.35), (0.4, 0.28)], segs=16, res=3,
           ref=(0, 0, 1), cap0=False, cap1=False)
    m.loft("body", BELLY, [(x, y, z - 0.1) for x, y, z in tor], [(0.36, 0.24), (0.56, 0.28), (0.54, 0.27), (0.34, 0.2)],
           segs=16, res=3, ref=(0, 0, 1), cap0=False, cap1=False)

    def scutes(g, y0, y1, n, width, z_of, h, rows=(-1, 1), size=0.14):
        for i in range(n):
            y = y0 + (y1 - y0) * i / max(1, n - 1)
            for r in rows:
                x = r * width
                m.box(g, SCALE, (size, size * 1.2, h), loc=(x, y, z_of(y) + h * 0.3), taper=(0.35, 0.6))

    top = lambda y: zc + 0.33 + 0.05 * math.cos(y)
    scutes("body", -1.1, 1.05, 9, 0.12, top, 0.13)
    scutes("body", -0.9, 0.9, 7, 0.33, lambda y: top(y) - 0.06, 0.1)
    # red-gold kain around the waist (hips) with hanging flaps
    m.torus("body", KAIN, 0.58, 0.13, loc=(0, 0.72, zc), rot=(90, 0, 0), scale=(0.95, 0.62, 1.0), segs=20, rsegs=5)
    m.torus("body", GOLD, 0.58, 0.03, loc=(0, 0.62, zc), rot=(90, 0, 0), scale=(0.97, 0.64, 1.0), segs=20, rsegs=4)
    m.torus("body", GOLD, 0.58, 0.03, loc=(0, 0.82, zc), rot=(90, 0, 0), scale=(0.97, 0.64, 1.0), segs=20, rsegs=4)
    for sg in (1, -1):
        m.prism("body", KAIN, [(-0.18, 0), (0.18, 0), (0.22, -0.34), (0.0, -0.28), (-0.2, -0.36)], 0.03,
                loc=(sg * 0.58, 0.72, zc - 0.02), rot=(0, sg * 15, 90))
        m.box("body", GOLD, (0.03, 0.4, 0.04), loc=(sg * 0.6, 0.72, zc - 0.33), rot=(0, sg * 15, 0))
    # head
    m.pivot("head", (0, -1.2, zc + 0.02), parent="body")
    hd = [(0, -1.1, zc + 0.05), (0, -1.55, zc + 0.08), (0, -2.1, zc + 0.02), (0, -2.65, zc - 0.02),
          (0, -2.8, zc - 0.04)]
    m.loft("head", SCALE, hd, [(0.42, 0.28), (0.36, 0.22), (0.22, 0.13), (0.2, 0.11), (0.06, 0.06)], segs=14,
           res=3, ref=(0, 0, 1), cap0=False)
    m.box("head", KAIN, (0.5, 1.2, 0.05), loc=(0, -2.0, zc - 0.1), taper=(1, 1))  # mouth interior
    teeth_row(m, "head", BELLY, u_curve(-1.45, -2.72, 0.22, zc - 0.07, 17, x_shrink=0.1), 0.09, 0.025, up=False)
    for sg in (1, -1):
        m.sphere("head", SCALE, 0.11, loc=(sg * 0.2, -1.55, zc + 0.27), scale=(1, 1.2, 0.8), segs=10, rings=6)
        m.sphere("head", EYE, 0.06, loc=(sg * 0.22, -1.63, zc + 0.3), scale=(0.8, 0.9, 0.7), segs=8, rings=6)
        m.sphere("head", SCALE, 0.05, loc=(sg * 0.07, -2.68, zc + 0.08), segs=8, rings=5)  # nostrils
        m.torus("head", GOLD, 0.05, 0.015, loc=(sg * 0.3, -1.3, zc + 0.18), rot=(0, 90, 0), segs=10, rsegs=4)
    scutes("head", -1.2, -1.45, 2, 0.1, lambda y: zc + 0.28, 0.1)
    # gold crest plate (garuda mungkur) behind the eyes: he is a lord of the river
    m.prism("head", GOLD, [(-0.25, 0), (0.25, 0), (0.18, 0.18), (0.08, 0.14), (0.0, 0.3), (-0.08, 0.14),
                           (-0.18, 0.18)], 0.04, loc=(0, -1.35, zc + 0.3), rot=(-20, 0, 0))
    # jaw
    m.pivot("jaw", (0, -1.3, zc - 0.1), parent="head")
    m.loft("jaw", SCALE, [(0, -1.2, zc - 0.13), (0, -1.8, zc - 0.13), (0, -2.4, zc - 0.13), (0, -2.72, zc - 0.12)],
           [(0.38, 0.1), (0.3, 0.09), (0.2, 0.08), (0.08, 0.06)], segs=12, res=2, ref=(0, 0, 1))
    m.loft("jaw", BELLY, [(0, -1.2, zc - 0.18), (0, -1.8, zc - 0.18), (0, -2.4, zc - 0.17)],
           [(0.34, 0.08), (0.27, 0.07), (0.17, 0.06)], segs=12, res=2, ref=(0, 0, 1))
    teeth_row(m, "jaw", BELLY, u_curve(-1.55, -2.66, 0.2, zc - 0.07, 15, x_shrink=0.1), 0.08, 0.024, up=True)
    # tail (tail + tail_tip)
    m.pivot("tail", (0, 1.1, zc - 0.03), parent="body")
    m.loft("tail", SCALE, [(0, 1.0, zc - 0.03), (0, 1.7, zc - 0.08), (0, 2.35, zc - 0.13)],
           [(0.4, 0.28), (0.27, 0.22), (0.16, 0.15)], segs=12, res=3, ref=(0, 0, 1), cap0=False)
    tl = lambda y: zc + 0.24 - (y - 1.0) * 0.12
    scutes("tail", 1.15, 2.3, 6, 0.09, tl, 0.14, size=0.12)
    m.pivot("tail_tip", (0, 2.3, zc - 0.13), parent="tail")
    m.loft("tail_tip", SCALE, [(0, 2.25, zc - 0.13), (0, 2.8, zc - 0.16), (0, 3.35, zc - 0.18)],
           [(0.16, 0.15), (0.1, 0.1), (0.02, 0.03)], segs=10, res=3, ref=(0, 0, 1), cap0=False)
    for i in range(6):
        y = 2.35 + i * 0.17
        h = 0.16 - i * 0.018
        m.box("tail_tip", SCALE, (0.03, 0.14, h), loc=(0, y, zc - 0.05 - i * 0.01 + h * 0.3), taper=(0.5, 0.4))
    # legs: splayed, elbows out; hind legs are root children, front legs under body
    for sg, side in ((1, "l"), (-1, "r")):
        for g, y, par, big in (("leg_" + side, 0.7, None, 1.15), ("arm_" + side, -0.75, "body", 1.0)):
            hip = V(sg * 0.45, y, zc - 0.05)
            m.pivot(g, hip, parent=par)
            el = V(sg * 0.85, y + 0.05, zc - 0.05)
            ft = V(sg * 0.9, y - 0.08, 0.06)
            m.loft(g, SCALE, [hip, el, ft], [0.17 * big, 0.12 * big, 0.09 * big], segs=10, res=3, ref=(0, -1, 0))
            m.sphere(g, SCALE, 0.14 * big, loc=ft + V(0, -0.08, -0.02), scale=(1.1, 1.4, 0.45), segs=10, rings=6)
            for c in range(4):
                a = math.radians(-50 + c * 30) * sg
                d = V(math.sin(a), -math.cos(a), 0)
                m.cyl(g, BELLY, 0.03, 0.12, loc=ft + V(0, -0.08, -0.02) + d * 0.2, rot=d.to_track_quat("Z", "Y").to_matrix(),
                      r2=0.004, segs=5)
            m.torus(g, GOLD, 0.15 * big, 0.035, loc=(hip + el) / 2, rot=(0, 90, 0), segs=12, rsegs=4)
            m.torus(g, GOLD, 0.11 * big, 0.03, loc=el + (ft - el) * 0.55, rot=(0, 0, 0), segs=12, rsegs=4)
    return m


BUILDERS = {"sura": sura, "baya": baya}

if __name__ == "__main__":
    run_cli(BUILDERS)

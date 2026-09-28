#!/usr/bin/env python3
"""Hanoman Duta - enemies: wil, cakil, buto_ijo, banaspati, yuyu, kijang, kijang_raksasa.

Run:  python3 hanoman/blender/enemies.py [ids...] [--no-preview] [--no-export]
Rig contract: see characters.py / README.md. Own left = +X, front = -Y.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import V, TAU, Model, humanoid, run_cli  # noqa: E402


def claws(m, g, mt, hand, n=3, length=0.09, r=0.022, down=True, spread=0.035):
    for i in range(n):
        off = (i - (n - 1) / 2) * spread
        base = V(hand) + V(off, -0.04, -0.03)
        m.cyl(g, mt, r, length, loc=base + V(0, -0.02, -length * 0.4), r2=0.002, rot=(160, 0, 0), segs=6)


def fang(m, g, mt, base, length, r, up=True, tilt=(0, 0, 0)):
    rot = (tilt[0], tilt[1], tilt[2]) if up else (180 + tilt[0], tilt[1], tilt[2])
    off = V(0, 0, length / 2 if up else -length / 2)
    m.cyl(g, mt, r, length, loc=V(base) + off, r2=0.003, rot=rot, segs=6)


# ------------------------------------------------------------------ Wil
def wil():
    m = Model("wil")
    SKIN = m.mat("M_Skin", "#b3372c")
    DARK = m.mat("M_Dark", "#1f1a1d")
    BONE = m.mat("M_Bone", "#eadfc4")
    EYE = m.mat("M_GlowEye", "#ffd23a")
    s = dict(
        hip=0.46, leg_x=0.11, leg_z=0.44, knee=0.25, knee_y=-0.09, knee_x=0.05, ankle=0.06,
        thigh=0.08, calf=0.07, ankle_r=0.045, foot=(0.13, 0.22, 0.08),
        torso=[(0.4, 0.14, 0.11, 0.03), (0.52, 0.17, 0.14, 0.02), (0.66, 0.21, 0.16, -0.04),
               (0.77, 0.19, 0.13, -0.1), (0.83, 0.09, 0.08, -0.15)],
        neck=(0, -0.16, 0.82), sh=(0.2, -0.07, 0.75), elbow=(0.31, -0.13, 0.55), wrist=(0.33, -0.24, 0.38),
        upper=0.07, fore=0.068, wrist_r=0.05, hand=0.07, arm_segs=8, leg_segs=8, torso_segs=12,
        mats=dict(leg=SKIN, foot=SKIN, torso=SKIN, arm=SKIN, hand=SKIN))
    p = humanoid(m, s)
    for side in ("l", "r"):
        claws(m, "arm_" + side, BONE, p["hand_" + side], length=0.1, r=0.02)
    for sg, side in ((1, "l"), (-1, "r")):
        for i in range(3):
            m.cyl("leg_" + side, BONE, 0.015, 0.05, loc=(sg * 0.16 + (i - 1) * 0.035, -0.2, 0.03), rot=(90, 0, 0),
                  r2=0.002, segs=5)
    # ragged loincloth + belly
    m.lathe("body", DARK, [(0.2, 0.3), (0.17, 0.42), (0.15, 0.5)], segs=10, smooth=False)
    m.sphere("body", SKIN, 0.13, loc=(0, -0.08, 0.53), scale=(1.1, 0.9, 0.9), segs=10, rings=6)
    # spiky back ridge
    for i, z in enumerate((0.58, 0.68, 0.76)):
        m.cyl("body", BONE, 0.035, 0.1, loc=(0, 0.12 - i * 0.04, z + 0.04), rot=(-40, 0, 0), r2=0.003, segs=5)
    # head: big, low, horned, fanged, glowing eyes, pointed ears, wild black hair
    hc = V(0, -0.25, 0.9)
    m.sphere("head", SKIN, 0.17, loc=hc, scale=(1.05, 1.0, 0.92), segs=14, rings=9)
    m.sphere("head", SKIN, 0.1, loc=hc + V(0, -0.13, -0.07), scale=(1.3, 0.8, 0.7), segs=10, rings=6)
    m.sphere("head", SKIN, 0.04, loc=hc + V(0, -0.19, 0.0), scale=(1.1, 1, 0.9), segs=8, rings=5)  # nose
    m.box("head", DARK, (0.17, 0.02, 0.02), loc=hc + V(0, -0.2, -0.1))
    for sg in (1, -1):
        fang(m, "head", BONE, hc + V(sg * 0.06, -0.2, -0.12), 0.07, 0.018, up=True)
        m.sphere("head", EYE, 0.032, loc=hc + V(sg * 0.07, -0.15, 0.05), scale=(1.2, 0.6, 0.8), segs=8, rings=5)
        m.loft("head", SKIN, [hc + V(sg * 0.02, -0.16, 0.1), hc + V(sg * 0.1, -0.15, 0.09)], [0.02, 0.018],
               segs=5, ref=(0, 0, 1))  # angry brow
        m.loft("head", BONE, [hc + V(sg * 0.1, -0.05, 0.12), hc + V(sg * 0.17, -0.02, 0.24),
                               hc + V(sg * 0.16, 0.05, 0.33)], [0.04, 0.025, 0.004], segs=6, res=3)
        m.prism("head", SKIN, [(0, 0), (0.14, 0.05), (0.0, 0.07)], 0.02, loc=hc + V(sg * 0.15, 0.0, 0.0),
                rot=(0, 0, 0), scale=(sg, 1, 1))
    for i in range(7):
        a = TAU * i / 7
        m.cyl("head", DARK, 0.05, 0.16, loc=hc + V(math.cos(a) * 0.09, 0.08 + math.sin(a) * 0.06, 0.15),
              rot=(-35 + math.sin(a) * 20, math.cos(a) * 30, 0), r2=0.005, segs=5)
    return m


# ------------------------------------------------------------------ Buto Cakil
def cakil():
    m = Model("cakil")
    SKIN = m.mat("M_Skin", "#8fa3b3")
    RED = m.mat("M_Red", "#a8232b")
    DARK = m.mat("M_Dark", "#1c1a20")
    GOLD = m.mat("M_Gold", "#d9a93a")
    BONE = m.mat("M_Bone", "#ece6d6")
    s = dict(
        hip=0.94, leg_x=0.13, leg_z=0.9, knee=0.5, knee_y=-0.12, knee_x=0.07, ankle=0.09,
        thigh=0.07, calf=0.055, ankle_r=0.038, foot=(0.1, 0.26, 0.07),
        torso=[(0.86, 0.14, 0.1, 0.02), (1.02, 0.12, 0.09, 0.0), (1.2, 0.17, 0.11, -0.06),
               (1.36, 0.17, 0.1, -0.12), (1.44, 0.06, 0.06, -0.17)],
        neck=(0, -0.18, 1.43), sh=(0.21, -0.1, 1.35), elbow=(0.36, -0.1, 1.12), wrist=(0.4, -0.25, 0.97),
        upper=0.05, fore=0.045, wrist_r=0.035, hand=0.055, arm_segs=8, leg_segs=8, torso_segs=12,
        mats=dict(leg=SKIN, foot=DARK, torso=SKIN, arm=SKIN, hand=SKIN))
    p = humanoid(m, s)
    # red & black clothes: short red kain, black under-trousers band, red sash hanging long
    m.lathe("body", RED, [(0.22, 0.6), (0.17, 0.8), (0.15, 0.98)], segs=12, smooth=False)
    m.torus("body", DARK, 0.22, 0.02, loc=(0, 0, 0.6), segs=12, rsegs=4)
    m.torus("body", GOLD, 0.15, 0.028, loc=(0, 0.0, 0.98), scale=(1, 0.75, 0.9), segs=12, rsegs=4)
    for sg in (1, -1):
        m.prism("body", DARK if sg > 0 else RED, [(-0.03, 0), (0.03, 0), (0.05, -0.6), (0.0, -0.55), (-0.04, -0.62)],
                0.015, loc=(sg * 0.1, 0.12, 0.98), rot=(-12, 0, 0))
        m.cyl("leg_" + ("l" if sg > 0 else "r"), DARK, 0.085, 0.14,
              loc=(sg * 0.15, -0.05, 0.62), segs=10)  # black trouser cuffs
    # chest cross sash
    m.torus("body", RED, 0.17, 0.022, loc=(0, -0.06, 1.24), rot=(8, -38, 0), scale=(1, 0.62, 1), segs=14, rsegs=4)
    # head: small cranium, long hooked nose, huge protruding under-jaw with tusks, big hair bun
    hc = V(0, -0.26, 1.6)
    m.sphere("head", SKIN, 0.1, loc=hc, scale=(0.9, 1.1, 1.0), segs=12, rings=8)
    m.loft("head", SKIN, [hc + V(0, -0.07, 0.03), hc + V(0, -0.16, 0.0), hc + V(0, -0.22, -0.06)],
           [0.03, 0.025, 0.008], segs=6, res=3)  # hooked nose
    for sg in (1, -1):
        e = hc + V(sg * 0.045, -0.085, 0.035)
        m.sphere("head", BONE, 0.025, loc=e, scale=(1.3, 0.6, 0.8), segs=8, rings=5)
        m.sphere("head", DARK, 0.012, loc=e + V(0, -0.013, 0), segs=6, rings=4)
    # hair: black gelung bun with red band and gold jamang
    m.sphere("head", DARK, 0.1, loc=hc + V(0, 0.08, 0.06), scale=(0.9, 1.1, 1.0), segs=10, rings=7)
    m.sphere("head", DARK, 0.085, loc=hc + V(0, 0.14, 0.17), scale=(1.1, 1.0, 0.8), segs=10, rings=6)
    m.torus("head", RED, 0.075, 0.018, loc=hc + V(0, 0.13, 0.12), rot=(15, 0, 0), segs=10, rsegs=4)
    m.torus("head", GOLD, 0.098, 0.015, loc=hc + V(0, 0.0, 0.05), scale=(0.95, 1.1, 1.3), segs=12, rsegs=4)
    m.loft("head", DARK, [hc + V(0, 0.18, 0.1), hc + V(0, 0.3, 0.0), hc + V(0, 0.32, -0.2)],
           [0.04, 0.03, 0.005], segs=6, res=3)  # hair tail
    # jaw: hinge under the ear, long protruding lower jaw curving upward, tusks + teeth
    jh = hc + V(0, -0.02, -0.06)
    m.pivot("jaw", jh, parent="head")
    m.loft("jaw", SKIN, [jh + V(0, 0.02, 0.0), jh + V(0, -0.12, -0.05), jh + V(0, -0.26, -0.04),
                         jh + V(0, -0.33, 0.04)], [(0.08, 0.05), (0.08, 0.05), (0.065, 0.04), (0.025, 0.025)],
           segs=8, res=3, ref=(0, 0, 1))
    m.box("jaw", RED, (0.07, 0.2, 0.012), loc=jh + V(0, -0.16, -0.005))
    for sg in (1, -1):
        fang(m, "jaw", BONE, jh + V(sg * 0.04, -0.25, -0.01), 0.1, 0.017, up=True, tilt=(-15, sg * 12, 0))
        fang(m, "jaw", BONE, jh + V(sg * 0.045, -0.14, -0.01), 0.05, 0.012, up=True)
    # keris in the right hand, wavy blade pointing forward
    h = p["hand_r"]
    m.pivot("weapon", h, parent="arm_r")
    m.sphere("weapon", GOLD, 0.03, loc=h + V(0, 0.0, 0.06), scale=(1, 1, 1.4), segs=8, rings=5)  # hilt pommel
    m.cyl("weapon", GOLD, 0.02, 0.1, loc=h, segs=6)
    m.prism("weapon", GOLD, [(-0.06, 0), (0.06, 0), (0.03, 0.03), (-0.04, 0.035)], 0.02,
            loc=h + V(0, -0.02, -0.06), rot=(90, 0, 0))  # ganja (guard)
    blade = [h + V(0.025 * math.sin(i * 1.3), -0.07 - 0.07 * i, -0.06 - 0.006 * i) for i in range(7)]
    m.loft("weapon", BONE, blade, [(0.03, 0.006), (0.028, 0.006), (0.026, 0.005), (0.024, 0.005), (0.02, 0.004),
                                   (0.013, 0.004), (0.002, 0.002)], segs=6, res=2, ref=(0, 0, 1))
    m.scale_groups(["head", "jaw"], 1.3, (0, -0.18, 1.43))
    return m


# ------------------------------------------------------------------ Buto Ijo
def buto_ijo():
    m = Model("buto_ijo")
    SKIN = m.mat("M_Skin", "#4f8a3a")
    DARK = m.mat("M_Dark", "#1a1718")
    GOLD = m.mat("M_Gold", "#d9a93a")
    BONE = m.mat("M_Bone", "#ece2c8")
    EYE = m.mat("M_GlowEye", "#ff5a2a")
    s = dict(
        hip=1.3, leg_x=0.3, leg_z=1.22, knee=0.7, knee_y=-0.08, knee_x=0.06, ankle=0.16,
        thigh=0.24, calf=0.2, ankle_r=0.14, foot=(0.36, 0.5, 0.2),
        torso=[(1.1, 0.42, 0.34, 0.0), (1.35, 0.56, 0.52, -0.12), (1.75, 0.6, 0.52, -0.12),
               (2.1, 0.66, 0.42, -0.02), (2.38, 0.62, 0.36, 0.02), (2.52, 0.3, 0.25, -0.02)],
        neck=(0, -0.1, 2.45), sh=(0.64, 0.02, 2.28), elbow=(0.84, 0.06, 1.8), wrist=(0.9, -0.08, 1.38),
        upper=0.21, fore=0.21, wrist_r=0.14, hand=0.2, arm_segs=10, leg_segs=10, torso_segs=16,
        mats=dict(leg=SKIN, foot=SKIN, torso=SKIN, arm=SKIN, hand=SKIN))
    p = humanoid(m, s)
    # big shoulder muscles, belly button, loincloth (black with gold hem), gold belt
    for sg in (1, -1):
        m.sphere("body", SKIN, 0.3, loc=(sg * 0.55, 0.0, 2.3), scale=(1, 1, 0.85), segs=12, rings=8)
    m.lathe("body", DARK, [(0.52, 0.85), (0.5, 1.05), (0.44, 1.2)], segs=16, smooth=False)
    m.torus("body", GOLD, 0.52, 0.03, loc=(0, 0, 0.85), segs=16, rsegs=4)
    m.torus("body", GOLD, 0.46, 0.06, loc=(0, -0.02, 1.22), scale=(1, 0.95, 0.8), segs=16, rsegs=5)
    m.box("body", GOLD, (0.24, 0.05, 0.2), loc=(0, -0.5, 1.23), bevel=0.02)
    m.torus("body", GOLD, 0.34, 0.05, loc=(0, -0.12, 2.36), rot=(-25, 0, 0), scale=(1.25, 1, 0.7), segs=16, rsegs=5)
    for side in ("l", "r"):
        e, w = p["elbow_" + side], p["wrist_" + side]
        m.torus("arm_" + side, GOLD, 0.2, 0.045, loc=V(e.x * 0.95, e.y, e.z + 0.3), segs=12, rsegs=5)
        m.torus("arm_" + side, GOLD, 0.15, 0.04, loc=w + (w - e).normalized() * -0.05, segs=12, rsegs=5)
        claws(m, "arm_" + side, BONE, p["hand_" + side], length=0.14, r=0.035, spread=0.08)
    # head sunk into shoulders: fat face, bulging glowing eyes, round nose, tusks, curly hair mane
    hc = V(0, -0.2, 2.68)
    m.sphere("head", SKIN, 0.3, loc=hc, scale=(1.05, 0.95, 0.95), segs=16, rings=10)
    m.sphere("head", SKIN, 0.2, loc=hc + V(0, -0.2, -0.14), scale=(1.4, 0.8, 0.8), segs=12, rings=8)  # jowls
    m.sphere("head", SKIN, 0.09, loc=hc + V(0, -0.3, 0.0), scale=(1.2, 0.9, 0.9), segs=10, rings=6)  # nose
    m.box("head", DARK, (0.32, 0.03, 0.04), loc=hc + V(0, -0.35, -0.16))
    for sg in (1, -1):
        m.sphere("head", BONE, 0.075, loc=hc + V(sg * 0.13, -0.23, 0.1), scale=(1, 0.6, 0.9), segs=10, rings=6)
        m.sphere("head", EYE, 0.04, loc=hc + V(sg * 0.13, -0.27, 0.1), scale=(1, 0.5, 1), segs=8, rings=5)
        m.loft("head", DARK, [hc + V(sg * 0.04, -0.27, 0.2), hc + V(sg * 0.22, -0.22, 0.24)], [0.035, 0.03],
               segs=6, ref=(0, 0, 1))
        fang(m, "head", BONE, hc + V(sg * 0.13, -0.33, -0.18), 0.2, 0.04, up=True, tilt=(-10, sg * 10, 0))
        m.torus("head", GOLD, 0.06, 0.018, loc=hc + V(sg * 0.3, 0.0, -0.12), rot=(0, 90, 0), segs=10, rsegs=4)
        m.sphere("head", SKIN, 0.07, loc=hc + V(sg * 0.3, 0.0, 0.02), scale=(0.5, 1, 1.2), segs=8, rings=5)
    for i in range(16):  # curly black hair: ring of lumps round the back + top
        a = math.pi * (i / 15) - math.pi
        rr = 0.3
        m.ico("head", DARK, 0.12, loc=hc + V(math.cos(a) * rr * 1.05, 0.05 - math.sin(a) * rr * 0.9,
                                                0.1 + 0.12 * math.sin(i * 1.7)), sub=1, jitter=0.15, seed=i)
    for i in range(5):
        m.ico("head", DARK, 0.13, loc=hc + V((i - 2) * 0.11, 0.08, 0.28), sub=1, jitter=0.15, seed=20 + i)
    m.torus("head", GOLD, 0.29, 0.03, loc=hc + V(0, 0.0, 0.14), scale=(1.05, 1, 1.4), segs=16, rsegs=4)
    # club (gada kayu): dark wood with gold bands and bone spikes, resting forward/down
    h = p["hand_r"]
    m.pivot("weapon", h, parent="arm_r")
    d = V(0, -0.45, 0.9).normalized()
    pts = [h - d * 0.2, h + d * 0.6, h + d * 1.5]
    m.loft("weapon", DARK, pts, [0.07, 0.13, 0.22], segs=10, res=2)
    for t in (0.35, 0.9, 1.3):
        m.torus("weapon", GOLD, 0.14 + t * 0.06, 0.03, loc=h + d * t, rot=d.to_track_quat("Z", "Y").to_matrix(),
                segs=12, rsegs=4)
    for k in range(8):
        a = TAU * k / 8
        side = V(math.cos(a), math.sin(a), 0)
        side = (side - d * side.dot(d)).normalized()
        base = h + d * (1.1 + 0.15 * (k % 2)) + side * 0.18
        m.cyl("weapon", BONE, 0.035, 0.12, loc=base + side * 0.05, rot=side.to_track_quat("Z", "Y").to_matrix(),
              r2=0.003, segs=5)
    return m


# ------------------------------------------------------------------ Banaspati
def banaspati():
    m = Model("banaspati")
    BONE = m.mat("M_Bone", "#e6d8b8")
    DARK = m.mat("M_Dark", "#241615")
    FIRE = m.mat("M_GlowFire", "#ff7a1f")
    CORE = m.mat("M_GlowFireCore", "#ffd84a")
    EYE = m.mat("M_GlowEye", "#fff2a0")
    c = V(0, 0, 1.2)
    m.pivot("body", c)
    # skull: cranium + cheek bones + eye sockets
    m.sphere("body", BONE, 0.24, loc=c + V(0, 0.02, 0.05), scale=(1.0, 1.1, 0.95), segs=16, rings=10)
    m.sphere("body", BONE, 0.17, loc=c + V(0, -0.1, -0.06), scale=(1.15, 0.9, 0.8), segs=12, rings=8)
    for sg in (1, -1):
        m.sphere("body", DARK, 0.07, loc=c + V(sg * 0.085, -0.2, 0.02), scale=(1.1, 0.5, 1.0), segs=10, rings=6)
        m.sphere("body", EYE, 0.035, loc=c + V(sg * 0.085, -0.225, 0.02), scale=(1, 0.6, 1), segs=8, rings=5)
    m.prism("body", DARK, [(-0.03, 0), (0.03, 0), (0, 0.05)], 0.03, loc=c + V(0, -0.24, -0.07))
    for i in range(6):  # upper teeth
        m.box("body", BONE, (0.03, 0.03, 0.05), loc=c + V((i - 2.5) * 0.034, -0.23 + abs(i - 2.5) * 0.012, -0.15),
              bevel=0.006)
    # jaw
    jh = c + V(0, 0.02, -0.12)
    m.pivot("jaw", jh, parent="body")
    m.loft("jaw", BONE, [jh + V(-0.15, -0.02, 0), jh + V(-0.12, -0.18, -0.06), jh + V(0, -0.24, -0.08),
                         jh + V(0.12, -0.18, -0.06), jh + V(0.15, -0.02, 0)], [0.03, 0.035, 0.04, 0.035, 0.03],
           segs=6, res=3, ref=(0, 0, 1))
    for i in range(5):
        m.box("jaw", BONE, (0.028, 0.03, 0.045), loc=jh + V((i - 2) * 0.034, -0.22 + abs(i - 2) * 0.015, -0.04),
              bevel=0.006)
    # flames: fat licking tongues engulfing the skull, swept back and up; inner yellow core
    for i in range(7):
        a = math.pi * (0.05 + 0.9 * i / 6)
        x = math.cos(a) * 0.2
        base = c + V(x, 0.1, 0.02 + math.sin(a) * 0.14)
        h = 0.35 + 0.25 * math.sin(a) + 0.07 * ((i * 5) % 3)
        wob = 0.07 * (1 if i % 2 else -1)
        pts = [base, base + V(x * 0.3 + wob, 0.12, h * 0.35), base + V(x * 0.5 - wob, 0.25, h * 0.7),
               base + V(x * 0.8 + wob * 0.5, 0.36, h)]
        m.loft("body", FIRE, pts, [0.13, 0.11, 0.06, 0.004], segs=7, res=3)
    for i in range(4):
        a = math.pi * (0.2 + 0.6 * i / 3)
        base = c + V(math.cos(a) * 0.12, 0.12, 0.18)
        tip = base + V(math.cos(a) * 0.12, 0.2, 0.34 + 0.12 * math.sin(a))
        m.loft("body", CORE, [base, (base + tip) / 2 + V(0.03, 0.04, 0), tip], [0.08, 0.06, 0.004], segs=6, res=3)
    # a few wisps below (it floats)
    for i in range(4):
        a = TAU * i / 4 + 0.4
        base = c + V(math.cos(a) * 0.12, math.sin(a) * 0.1 + 0.05, -0.18)
        m.loft("body", FIRE, [base, base + V(math.cos(a) * 0.05, 0.08, -0.15), base + V(0, 0.15, -0.3)],
               [0.06, 0.04, 0.004], segs=5, res=2)
    return m


# ------------------------------------------------------------------ Yuyu Kangkang
def yuyu():
    m = Model("yuyu")
    SHELL = m.mat("M_Shell", "#8a2420")
    GOLD = m.mat("M_Gold", "#d9a93a")
    PALE = m.mat("M_Belly", "#d9a57a")
    DARK = m.mat("M_Dark", "#2a1614")
    EYE = m.mat("M_GlowEye", "#ffe36a")
    c = V(0, 0, 0.72)
    m.pivot("body", c)
    # carapace: wide flattened dome with serrated gold rim and front spikes
    m.lathe("body", SHELL, [(0, 0.2), (0.55, 0.19), (0.72, 0.12), (0.76, 0.0), (0.7, -0.08), (0.55, -0.14),
                            (0.0, -0.16)][::-1], loc=c, scale=(1.0, 0.72, 1.0), segs=20)
    m.lathe("body", PALE, [(0.0, -0.24), (0.5, -0.2), (0.62, -0.1)], loc=c, scale=(1.0, 0.72, 1.0), segs=16)
    m.torus("body", GOLD, 0.75, 0.035, loc=c + V(0, 0, 0.02), scale=(1.0, 0.72, 1.0), segs=24, rsegs=4)
    for i in range(9):
        a = math.pi * (0.2 + 0.6 * i / 8)
        pos = c + V(math.cos(a) * 0.76, -math.sin(a) * 0.76 * 0.72, 0.03)
        out = V(math.cos(a), -math.sin(a), 0.2).normalized()
        m.cyl("body", GOLD, 0.04, 0.12, loc=pos + out * 0.05, rot=out.to_track_quat("Z", "Y").to_matrix(),
              r2=0.003, segs=5)
    # shell bumps / markings
    for i, (x, y) in enumerate(((0, -0.1), (-0.25, 0.05), (0.25, 0.05), (0, 0.22), (-0.4, -0.15), (0.4, -0.15))):
        m.sphere("body", SHELL, 0.12, loc=c + V(x, y, 0.16), scale=(1, 1, 0.45), segs=8, rings=5)
    m.sphere("body", GOLD, 0.06, loc=c + V(0, -0.2, 0.2), scale=(1, 1, 0.5), segs=8, rings=5)
    # eye stalks + mouth parts
    for sg in (1, -1):
        base = c + V(sg * 0.14, -0.42, 0.12)
        m.loft("body", SHELL, [base, base + V(sg * 0.03, -0.04, 0.2), base + V(sg * 0.05, -0.05, 0.3)],
               [0.035, 0.03, 0.03], segs=6, res=2, cap1=False)
        m.sphere("body", EYE, 0.055, loc=base + V(sg * 0.05, -0.06, 0.33), segs=8, rings=6)
        m.sphere("body", DARK, 0.02, loc=base + V(sg * 0.05, -0.11, 0.34), segs=6, rings=4)
    m.box("body", PALE, (0.26, 0.08, 0.14), loc=c + V(0, -0.5, -0.1), bevel=0.02)
    # walking legs: 3 per side, spider-like, joined into the leg pivot (at the shell side)
    for sg, side in ((1, "l"), (-1, "r")):
        g = "leg_" + side
        m.pivot(g, (sg * 0.55, 0.05, 0.62))
        for i, yy in enumerate((-0.2, 0.08, 0.34)):
            hip = V(sg * 0.5, yy, 0.64)
            knee = V(sg * 0.95, yy + (i - 1) * 0.12, 0.95)
            foot = V(sg * 1.2, yy + (i - 1) * 0.25, 0.0)
            m.loft(g, SHELL, [hip, knee], [0.07, 0.06], segs=6, res=1)
            m.loft(g, SHELL, [knee, (knee + foot) / 2 + V(sg * 0.02, 0, 0.05), foot], [0.058, 0.045, 0.012],
                   segs=6, res=2, ref=(0, -1, 0))
            m.sphere(g, GOLD, 0.07, loc=knee, segs=8, rings=5)
    # big claws: arm pivot at the front corner; arm_x carries the lower (fixed) pincer,
    # claw_x (child) the upper finger that opens (rotate around its local X).
    for sg, side in ((1, "l"), (-1, "r")):
        g = "arm_" + side
        sh = V(sg * 0.45, -0.38, 0.66)
        m.pivot(g, sh, parent="body")
        el = V(sg * 0.8, -0.62, 0.72)
        wr = V(sg * 0.72, -0.98, 0.72)
        m.loft(g, SHELL, [sh, el], [0.1, 0.09], segs=8, res=1)
        m.loft(g, SHELL, [el, wr], [0.1, 0.1], segs=8, res=1)
        m.sphere(g, GOLD, 0.11, loc=el, segs=8, rings=6)
        # palm (propodus): big swollen block
        palm = wr + V(0, -0.16, 0.0)
        m.sphere(g, SHELL, 0.2, loc=palm, scale=(0.95, 1.2, 0.85), segs=12, rings=8)
        m.torus(g, GOLD, 0.16, 0.025, loc=wr + V(0, -0.04, 0), rot=(90, 0, 0), segs=12, rsegs=4)
        # fixed lower finger
        m.loft(g, SHELL, [palm + V(0, -0.18, -0.06), palm + V(0, -0.38, -0.08), palm + V(sg * -0.02, -0.52, -0.02)],
               [(0.08, 0.06), (0.06, 0.045), (0.005, 0.005)], segs=7, res=2, ref=(0, 0, 1))
        for t in range(3):
            m.cyl(g, PALE, 0.018, 0.04, loc=palm + V(0, -0.24 - t * 0.08, -0.02), r2=0.002, segs=4)
        # movable upper finger
        cg = "claw_" + side
        hinge = palm + V(0, -0.14, 0.08)
        m.pivot(cg, hinge, parent=g)
        m.loft(cg, SHELL, [hinge, hinge + V(0, -0.2, 0.06), hinge + V(sg * -0.02, -0.4, 0.0)],
               [(0.075, 0.06), (0.055, 0.045), (0.005, 0.005)], segs=7, res=2, ref=(0, 0, 1))
        m.cyl(cg, DARK, 0.03, 0.08, loc=hinge + V(0, -0.36, -0.02), r2=0.004, rot=(180, 0, 0), segs=5)
    return m


# ------------------------------------------------------------------ Kijang (quadruped)
def quadruped(m, s):
    """Deer-like quadruped. Pivots: body (torso centre), leg_l/leg_r = hind legs (root children),
    arm_l/arm_r = front legs (under body), head (neck base, under body), tail (under body)."""
    k = s["k"]
    BODY, BELLY, HOOF = s["body"], s["belly"], s["hoof"]
    bc = V(0, 0, 0.98 * k)
    m.pivot("body", bc)
    m.loft("body", BODY, [V(0, 0.5, 0.97) * k, V(0, 0.2, 0.99) * k, V(0, -0.2, 1.0) * k, V(0, -0.45, 1.05) * k],
           [(0.19 * k, 0.2 * k), (0.2 * k, 0.24 * k), (0.21 * k, 0.26 * k), (0.17 * k, 0.2 * k)],
           segs=12, res=2, ref=(0, 0, 1))
    m.sphere("body", BELLY, 0.2 * k, loc=V(0, -0.05, 0.86) * k, scale=(0.85, 2.0, 0.55), segs=12, rings=6)
    for sg in (1, -1):  # haunches and shoulders
        m.sphere("body", BODY, 0.2 * k, loc=V(sg * 0.1, 0.42, 1.0) * k, scale=(0.7, 1.2, 1.2), segs=10, rings=7)
    # neck
    m.pivot("head", V(0, -0.5, 1.1) * k, parent="body")
    m.loft("head", BODY, [V(0, -0.46, 1.06) * k, V(0, -0.62, 1.3) * k, V(0, -0.7, 1.46) * k],
           [(0.1 * k, 0.13 * k), (0.08 * k, 0.09 * k), (0.075 * k, 0.08 * k)], segs=10, res=2, ref=(0, -1, 0))
    hc = V(0, -0.74, 1.5) * k
    m.sphere("head", BODY, 0.11 * k, loc=hc, scale=(0.9, 1.1, 1.0), segs=12, rings=8)
    m.loft("head", BODY, [hc + V(0, -0.05, 0) * k, hc + V(0, -0.18, -0.05) * k, hc + V(0, -0.26, -0.09) * k],
           [0.08 * k, 0.06 * k, 0.045 * k], segs=10, res=2, ref=(0, 0, 1))
    m.sphere("head", HOOF, 0.03 * k, loc=hc + V(0, -0.29, -0.08) * k, segs=8, rings=5)
    for sg in (1, -1):
        m.prism("head", BODY, [(0, 0), (0.05, 0.14), (0.0, 0.2), (-0.05, 0.14)], 0.02,
                loc=hc + V(sg * 0.09, 0.03, 0.06) * k, rot=(20, sg * -55, 0), scale=k)  # ears
    # legs: thin, hocks bend backwards
    m.pivot("leg_l", V(0.13, 0.42, 0.92) * k)
    m.pivot("leg_r", V(-0.13, 0.42, 0.92) * k)
    m.pivot("arm_l", V(0.13, -0.38, 0.92) * k, parent="body")
    m.pivot("arm_r", V(-0.13, -0.38, 0.92) * k, parent="body")
    for sg, side in ((1, "l"), (-1, "r")):
        x = 0.13 * sg
        hind = [V(x, 0.42, 0.95), V(x, 0.34, 0.62), V(x, 0.5, 0.36), V(x, 0.46, 0.07)]
        m.loft("leg_" + side, BODY, [p * k for p in hind], [0.1 * k, 0.06 * k, 0.035 * k, 0.03 * k], segs=8, res=2)
        m.cyl("leg_" + side, HOOF, 0.04 * k, 0.08 * k, loc=V(x, 0.45, 0.04) * k, r2=0.03 * k, segs=8)
        fr = [V(x, -0.38, 0.95), V(x, -0.4, 0.62), V(x, -0.39, 0.34), V(x, -0.41, 0.07)]
        m.loft("arm_" + side, BODY, [p * k for p in fr], [0.085 * k, 0.05 * k, 0.034 * k, 0.03 * k], segs=8, res=2)
        m.cyl("arm_" + side, HOOF, 0.04 * k, 0.08 * k, loc=V(x, -0.41, 0.04) * k, r2=0.03 * k, segs=8)
    m.pivot("tail", V(0, 0.62, 1.05) * k, parent="body")
    return hc


def kijang():
    m = Model("kijang")
    GOLD = m.mat("M_GoldFur", "#e2b43f")
    PALE = m.mat("M_Belly", "#f6e2a8")
    HOOF = m.mat("M_Dark", "#3a2616")
    EYE = m.mat("M_GlowEye", "#6dff9a")
    ANT = m.mat("M_Gold", "#b98526")
    k = 1.0
    hc = quadruped(m, dict(k=k, body=GOLD, belly=PALE, hoof=HOOF))
    for sg in (1, -1):
        m.sphere("head", EYE, 0.028, loc=hc + V(sg * 0.075, -0.07, 0.03), scale=(0.6, 1, 0.8), segs=8, rings=5)
        # small branching antlers (kijang = muntjac-like), gold
        base = hc + V(sg * 0.05, 0.0, 0.09)
        m.loft("head", ANT, [base, base + V(sg * 0.04, 0.03, 0.12), base + V(sg * 0.02, 0.1, 0.22)],
               [0.022, 0.016, 0.004], segs=6, res=2)
        m.loft("head", ANT, [base + V(sg * 0.035, 0.03, 0.1), base + V(sg * 0.06, -0.04, 0.16)], [0.012, 0.003],
               segs=5)
    # jewel spots along the flanks and back (glowing green gems)
    for i, (y, z) in enumerate(((0.3, 1.1), (0.05, 1.12), (-0.2, 1.12), (0.2, 0.92), (-0.08, 0.9), (0.42, 0.96))):
        for sg in (1, -1):
            m.ico("body", EYE, 0.032, loc=(sg * (0.2 if z < 1.0 else 0.17), y, z), sub=0, smooth=False)
    m.ico("body", EYE, 0.04, loc=(0, -0.1, 1.27), sub=0)
    # gold collar with bell-like pendant
    m.sphere("head", EYE, 0.035, loc=V(0, -0.7, 1.12), segs=8, rings=5)
    # tail: short upturned tuft
    t0 = V(0, 0.62, 1.05)
    m.loft("tail", GOLD, [t0, t0 + V(0, 0.08, 0.1), t0 + V(0, 0.1, 0.18)], [0.05, 0.05, 0.01], segs=8, res=2)
    m.sphere("tail", PALE, 0.04, loc=t0 + V(0, 0.07, 0.07), segs=8, rings=5)
    return m


def kijang_raksasa():
    """Kala Marica unmasked: the same rig as kijang, 1.3x bigger (~2.4 m at the head), dark and horned."""
    m = Model("kijang_raksasa")
    FUR = m.mat("M_Fur", "#2a2233")
    BELLY = m.mat("M_Belly", "#4a3350")
    HORN = m.mat("M_Bone", "#d8cbb0")
    GOLD = m.mat("M_Gold", "#c8952e")
    EYE = m.mat("M_GlowEye", "#ff3b5c")
    k = 1.3
    hc = quadruped(m, dict(k=k, body=FUR, belly=BELLY, hoof=GOLD))
    for sg in (1, -1):
        m.sphere("head", EYE, 0.035 * k, loc=hc + V(sg * 0.075, -0.07, 0.03) * k, scale=(0.6, 1, 0.8), segs=8, rings=5)
        # great curved ram/buffalo horns sweeping back and up
        base = hc + V(sg * 0.06, 0.0, 0.08) * k
        pts = [base, base + V(sg * 0.2, 0.05, 0.15) * k, base + V(sg * 0.32, 0.25, 0.25) * k,
               base + V(sg * 0.25, 0.45, 0.42) * k]
        m.loft("head", HORN, pts, [0.06 * k, 0.05 * k, 0.03 * k, 0.003], segs=8, res=3)
        fang_base = hc + V(sg * 0.04, -0.22, -0.12) * k
        m.cyl("head", HORN, 0.018 * k, 0.1 * k, loc=fang_base + V(0, 0, -0.04) * k, r2=0.002, rot=(180, 0, 0), segs=5)
    # spiky mane along the neck and back
    for i in range(9):
        y = -0.62 + i * 0.14
        z = 1.42 - 0.3 * min(1, (i + 1) / 3) if i < 3 else 1.24 - (i - 3) * 0.012
        m.cyl("body" if i >= 3 else "head", FUR, 0.07 * k, 0.28 * k, loc=V(0, y + 0.05, z + 0.1) * k,
              rot=(-50, 0, 0), r2=0.004, segs=5)
    for sg in (1, -1):  # gold ankle cuffs on the front legs + glowing sigil spots
        m.torus("arm_" + ("l" if sg > 0 else "r"), GOLD, 0.05 * k, 0.015 * k, loc=V(sg * 0.13, -0.39, 0.3) * k,
                segs=10, rsegs=4)
        m.ico("body", EYE, 0.035 * k, loc=V(sg * 0.2, 0.05, 1.02) * k, sub=0)
    t0 = V(0, 0.62, 1.05) * k
    m.loft("tail", FUR, [t0, t0 + V(0, 0.25, -0.1) * k, t0 + V(0, 0.45, -0.05) * k], [0.05 * k, 0.03 * k, 0.005],
           segs=6, res=2)
    m.cyl("tail", HORN, 0.04 * k, 0.12 * k, loc=t0 + V(0, 0.5, -0.04) * k, rot=(-90, 0, 0), r2=0.002, segs=5)
    return m


BUILDERS = {"wil": wil, "cakil": cakil, "buto_ijo": buto_ijo, "banaspati": banaspati, "yuyu": yuyu,
            "kijang": kijang, "kijang_raksasa": kijang_raksasa}

if __name__ == "__main__":
    run_cli(BUILDERS)

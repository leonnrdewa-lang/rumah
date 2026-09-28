#!/usr/bin/env python3
"""Hanoman Duta - playable/hub characters: hanoman, rama, jembawan, sugriwa.

Run:  python3 hanoman/blender/characters.py [ids...] [--no-preview] [--no-export]

Rig contract (no armature, parts rotated from code): root Empty <id> at the feet, facing -Y;
children body (hips), leg_l, leg_r (hip joints); under body: head (neck), arm_l, arm_r
(shoulders), tail (tail base); weapon under arm_r (in the fist). Own left = +X.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import V, TAU, Model, humanoid, eye_pair, gada, run_cli  # noqa: E402


# ------------------------------------------------------------------ shared monkey bits
def monkey_body_spec(mt, scale=1.0):
    k = scale
    return dict(
        hip=0.88 * k, leg_x=0.12 * k, leg_z=0.84 * k, knee=0.45 * k, knee_y=-0.06 * k, ankle=0.1 * k,
        knee_x=0.035,
        thigh=0.105 * k, calf=0.082 * k, ankle_r=0.05 * k, foot=(0.15 * k, 0.27 * k, 0.1 * k),
        torso=[(0.78 * k, 0.16 * k, 0.12 * k, 0.0), (0.9 * k, 0.18 * k, 0.13 * k, 0.0),
               (1.02 * k, 0.16 * k, 0.12 * k, -0.01 * k), (1.18 * k, 0.22 * k, 0.15 * k, -0.035 * k),
               (1.31 * k, 0.25 * k, 0.14 * k, -0.025 * k), (1.41 * k, 0.13 * k, 0.1 * k, 0.0),
               (1.48 * k, 0.075 * k, 0.075 * k, -0.01 * k)],
        neck=(0, -0.02 * k, 1.45 * k), sh=(0.27 * k, 0.0, 1.36 * k),
        elbow=(0.36 * k, 0.03 * k, 1.1 * k), wrist=(0.39 * k, -0.04 * k, 0.87 * k),
        upper=0.088 * k, fore=0.082 * k, wrist_r=0.055 * k, hand=0.082 * k, arm_segs=8, leg_segs=8,
        mats=mt)


def monkey_head(m, mt_fur, mt_face, mt_dark, c, k=1.0, mt_mouth=None, mt_eye=None):
    """Monkey head centred at c (world): big round eyes (wayang 'thelengan'), muzzle, jowls."""
    cx, cy, cz = c
    m.sphere("head", mt_fur, 0.15 * k, loc=(cx, cy + 0.02 * k, cz + 0.01 * k), scale=(1.0, 1.0, 1.0), segs=14, rings=9)
    for sg in (1, -1):  # cheek fur ruff (wide jowls read from above)
        m.sphere("head", mt_fur, 0.075 * k, loc=(cx + sg * 0.125 * k, cy - 0.03 * k, cz - 0.05 * k),
                 scale=(1.2, 0.9, 1.0), segs=8, rings=6)
    # face mask + protruding muzzle
    m.sphere("head", mt_face, 0.105 * k, loc=(cx, cy - 0.085 * k, cz), scale=(1.15, 0.6, 0.95), segs=12, rings=8)
    m.sphere("head", mt_face, 0.08 * k, loc=(cx, cy - 0.15 * k, cz - 0.06 * k), scale=(1.15, 0.85, 0.75),
             segs=12, rings=7)
    m.box("head", mt_mouth or mt_dark, (0.09 * k, 0.012, 0.014), loc=(cx, cy - 0.214 * k, cz - 0.08 * k))
    # bulging round eyes with dark pupils, heavy brow
    for sg in (1, -1):
        e = (cx + sg * 0.05 * k, cy - 0.15 * k, cz + 0.025 * k)
        m.sphere("head", mt_eye or mt_fur, 0.032 * k, loc=e, scale=(1, 0.7, 1), segs=8, rings=6)
        m.sphere("head", mt_dark, 0.017 * k, loc=(e[0], e[1] - 0.018 * k, e[2]), scale=(1, 0.6, 1), segs=6, rings=4)
    m.loft("head", mt_fur, [(cx - 0.1 * k, cy - 0.13 * k, cz + 0.055 * k), (cx, cy - 0.16 * k, cz + 0.07 * k),
                            (cx + 0.1 * k, cy - 0.13 * k, cz + 0.055 * k)], [0.018 * k, 0.026 * k, 0.018 * k],
           segs=6, res=3, ref=(0, 0, 1))
    for sg in (1, -1):  # ears
        m.sphere("head", mt_face, 0.045 * k, loc=(cx + sg * 0.16 * k, cy + 0.01, cz + 0.0), scale=(0.5, 1, 1.1),
                 segs=8, rings=5)
    return cz + 0.16 * k


def jamang(m, g, mt_gold, mt_gem, c, r, k=1.0, tall=0.0):
    """Wayang crown: jamang band, front ornament, sumping ear-wings and a garuda mungkur
    plate rising at the back of the head. `tall` > 0 adds a makuta tower."""
    cx, cy, cz = c
    m.torus(g, mt_gold, r * 1.0, 0.02 * k, loc=(cx, cy, cz), scale=(1.0, 1.05, 1.5), segs=16, rsegs=4)
    # front diadem points
    for i, x in enumerate((-0.07, -0.035, 0.0, 0.035, 0.07)):
        h = (0.07 if i == 2 else 0.045) * k
        m.prism(g, mt_gold, [(-0.02 * k, 0), (0.02 * k, 0), (0, h)], 0.02,
                loc=(cx + x * k, cy - r * 0.98 + abs(x) * 0.5 * k, cz + 0.02 * k),
                rot=(-12, 0, math.degrees(math.asin(max(-1, min(1, x * k / r))))))
    m.sphere(g, mt_gem, 0.022 * k, loc=(cx, cy - r * 1.04, cz + 0.02 * k), segs=8, rings=6)
    # sumping (ear ornaments, flame-like)
    for sg in (1, -1):
        m.prism(g, mt_gold, [(0, 0), (0.05 * k, 0.03 * k), (0.11 * k, 0.1 * k), (0.07 * k, 0.07 * k),
                             (0.05 * k, 0.12 * k), (0.02 * k, 0.05 * k)], 0.02,
                loc=(cx + sg * r * 0.95, cy + 0.02, cz - 0.02 * k), rot=(0, 0, 90 * sg) if False else (0, 0, 0),
                scale=(sg, 1, 1))
    # garuda mungkur: curled plate at the back (outline in x-z, placed in the Y plane behind head)
    out = [(-0.13, 0.0), (-0.16, 0.08), (-0.12, 0.16), (-0.05, 0.2), (0.0, 0.26), (0.05, 0.2), (0.12, 0.16),
           (0.16, 0.08), (0.13, 0.0), (0.06, 0.05), (0.0, 0.03), (-0.06, 0.05)]
    m.prism(g, mt_gold, [(x * k, z * k) for x, z in out], 0.03, loc=(cx, cy + r * 0.85, cz - 0.02 * k),
            rot=(-15, 0, 0))
    m.sphere(g, mt_gem, 0.025 * k, loc=(cx, cy + r * 0.8 - 0.02, cz + 0.12 * k), segs=8, rings=6)
    if tall > 0:
        # makuta: stacked tapering tiers
        z = cz + 0.02 * k
        prof = [(r * 0.95, 0), (r * 0.9, tall * 0.25), (r * 0.75, tall * 0.3), (r * 0.72, tall * 0.55),
                (r * 0.5, tall * 0.62), (r * 0.45, tall * 0.8), (r * 0.25, tall * 0.88), (0.02, tall), (0, tall * 1.02)]
        m.lathe(g, mt_gold, prof, loc=(cx, cy + 0.01, z), segs=12, smooth=False)
        m.sphere(g, mt_gem, 0.028 * k, loc=(cx, cy - r * 0.9, z + tall * 0.2), segs=8, rings=6)


def armlets(m, mt_gold, pts, s_upper, s_wrist):
    """Gold armlets (kelat bahu) on the upper arm and bracelets at the wrists."""
    for sg, side in ((1, "l"), (-1, "r")):
        e = pts["elbow_" + side]
        w = pts["wrist_" + side]
        shp = V(e.x * 0.85, e.y, e.z + 0.14)
        m.torus("arm_" + side, mt_gold, s_upper, 0.022, loc=shp, rot=(0, -12 * sg, 0), segs=12, rsegs=5,
                scale=(1, 1, 1.4))
        m.prism("arm_" + side, mt_gold, [(-0.04, 0), (0.04, 0), (0.0, 0.07)], 0.02,
                loc=(shp.x + sg * s_upper * 0.95, shp.y, shp.z + 0.01), rot=(0, 0, 90))
        m.torus("arm_" + side, mt_gold, s_wrist, 0.018, loc=w + (w - e).normalized() * -0.02, rot=(0, -8 * sg, 0),
                segs=12, rsegs=5, scale=(1, 1, 1.5))


# ------------------------------------------------------------------ Hanoman
def hanoman():
    m = Model("hanoman")
    FUR = m.mat("M_Fur", "#f4f1ea")
    FACE = m.mat("M_Skin", "#d7a98c")
    GOLD = m.mat("M_Gold", "#d9a93a")
    RED = m.mat("M_Red", "#b3262e")
    DARK = m.mat("M_Dark", "#1c1a1f")
    s = monkey_body_spec(dict(leg=FUR, foot=FACE, torso=FUR, arm=FUR, hand=FACE))
    pts = humanoid(m, s)
    # chest fur tufts/pecs
    for sg in (1, -1):
        m.sphere("body", FUR, 0.1, loc=(sg * 0.09, -0.08, 1.26), scale=(1.1, 0.7, 0.8), segs=10, rings=6)
        # shoulder fur mantle
        m.sphere("body", FUR, 0.11, loc=(sg * 0.22, 0.0, 1.38), scale=(1.0, 1.0, 0.8), segs=10, rings=6)
    # necklace (kalung) crescent
    m.torus("body", GOLD, 0.12, 0.02, loc=(0, -0.05, 1.37), rot=(-35, 0, 0), segs=16, rsegs=5, scale=(1.2, 1, 1))
    # poleng red/black waist cloth + gold belt + red sampur ends
    m.poleng("body", RED, DARK, 1.02, 0.64, (0.165, 0.12), rows=3, cols=12, flare=0.1)
    m.torus("body", GOLD, 0.165, 0.03, loc=(0, 0, 1.02), scale=(1, 0.75, 0.8), segs=16, rsegs=5)
    m.sphere("body", RED, 0.05, loc=(0, -0.12, 1.02), scale=(1, 0.6, 1), segs=8, rings=6)
    for sg in (1, -1):
        m.prism("body", RED, [(-0.03, 0), (0.03, 0), (0.05, -0.34), (0.0, -0.3), (-0.04, -0.36)], 0.02,
                loc=(sg * 0.1, -0.15, 1.0), rot=(8, 0, 0))
    # head
    hc = (0, -0.03, 1.57)
    monkey_head(m, FUR, FACE, DARK, hc, k=1.1)
    # white hair knot (gelung) above the crown
    m.sphere("head", FUR, 0.085, loc=(0, 0.03, 1.73), scale=(1, 1.2, 0.8), segs=10, rings=6)
    jamang(m, "head", GOLD, RED, (0, -0.01, 1.66), 0.145)
    armlets(m, GOLD, pts, 0.085, 0.058)
    # anklets
    for sg, side in ((1, "l"), (-1, "r")):
        m.torus("leg_" + side, GOLD, 0.055, 0.016, loc=(sg * 0.128, 0.02, 0.14), segs=12, rsegs=5)
    # long curling tail
    m.pivot("tail", (0, 0.12, 0.92), parent="body")
    tail_pts = [(0, 0.1, 0.92), (0, 0.32, 0.82), (0, 0.55, 0.9), (0.02, 0.68, 1.2), (0.02, 0.6, 1.5),
                (0.0, 0.42, 1.6), (0.0, 0.32, 1.48), (0.0, 0.38, 1.36)]
    m.loft("tail", FUR, tail_pts, [0.055, 0.05, 0.046, 0.042, 0.038, 0.034, 0.03, 0.025], segs=8, res=3,
           ref=(1, 0, 0))
    m.sphere("tail", FUR, 0.055, loc=(0.0, 0.4, 1.34), segs=10, rings=6)
    m.torus("tail", GOLD, 0.05, 0.012, loc=(0, 0.33, 0.82), rot=(80, 0, 0), segs=10, rsegs=4)
    # weapon: golden gada, grip in right fist pointing forward/up
    hand = pts["hand_r"]
    m.pivot("weapon", hand, parent="arm_r")
    gada(m, "weapon", GOLD, RED, hand, (0, -0.55, 0.83), length=1.0, head_r=0.14, mt_accent=GOLD)
    return m


# ------------------------------------------------------------------ Sugriwa
def sugriwa():
    m = Model("sugriwa")
    FUR = m.mat("M_Fur", "#b8432a")
    FACE = m.mat("M_Skin", "#e0b48c")
    GOLD = m.mat("M_Gold", "#d9a93a")
    CLOTH = m.mat("M_Cloth", "#2f5b46")
    DARK = m.mat("M_Dark", "#1c1a1f")
    s = monkey_body_spec(dict(leg=FUR, foot=FACE, torso=FUR, arm=FUR, hand=FACE))
    s["torso"][3] = (1.2, 0.22, 0.15, -0.04)
    s["torso"][4] = (1.33, 0.24, 0.14, -0.02)
    pts = humanoid(m, s)
    for sg in (1, -1):
        m.sphere("body", FUR, 0.12, loc=(sg * 0.22, 0.0, 1.39), scale=(1.0, 1.0, 0.8), segs=10, rings=6)
    # royal kain: green with gold hem, long back tail (dodot) + gold belt
    m.lathe("body", CLOTH, [(0.2, 0.6), (0.175, 0.8), (0.165, 1.03)], segs=14, smooth=True)
    m.torus("body", GOLD, 0.2, 0.02, loc=(0, 0, 0.6), segs=14, rsegs=4)
    m.torus("body", GOLD, 0.165, 0.035, loc=(0, 0, 1.03), scale=(1, 0.75, 0.9), segs=14, rsegs=5)
    m.prism("body", GOLD, [(-0.07, 0), (0.07, 0), (0.05, -0.4), (0.0, -0.46), (-0.05, -0.4)], 0.02,
            loc=(0, -0.17, 1.0), rot=(6, 0, 0))
    # broad gold collar (praba-like ulur)
    m.torus("body", GOLD, 0.13, 0.035, loc=(0, -0.03, 1.39), rot=(-20, 0, 0), scale=(1.25, 1.0, 0.6), segs=16, rsegs=5)
    hc = (0, -0.03, 1.6)
    monkey_head(m, FUR, FACE, DARK, hc)
    jamang(m, "head", GOLD, CLOTH, (0, -0.02, 1.66), 0.14, tall=0.2)
    armlets(m, GOLD, pts, 0.088, 0.058)
    m.pivot("tail", (0, 0.12, 0.92), parent="body")
    m.loft("tail", FUR, [(0, 0.1, 0.92), (0, 0.4, 0.78), (0, 0.7, 0.85), (0, 0.8, 1.1), (0, 0.66, 1.2)],
           [0.055, 0.05, 0.045, 0.035, 0.028], segs=8, res=4, ref=(1, 0, 0))
    return m


# ------------------------------------------------------------------ Rama
def rama():
    m = Model("rama")
    SKIN = m.mat("M_Skin", "#4a3530")
    GOLD = m.mat("M_Gold", "#d9a93a")
    GREEN = m.mat("M_Cloth", "#2d6b4a")
    DARK = m.mat("M_Dark", "#16151a")
    k = 1.06
    s = dict(
        hip=0.95, leg_x=0.1, leg_z=0.92, knee=0.5, knee_y=-0.02, ankle=0.1,
        thigh=0.085, calf=0.062, ankle_r=0.04, foot=(0.1, 0.25, 0.08),
        torso=[(0.86, 0.15, 0.11, 0.0), (0.98, 0.16, 0.11, 0.0), (1.1, 0.14, 0.1, -0.01),
               (1.3, 0.2, 0.13, -0.025), (1.43, 0.21, 0.12, -0.01), (1.52, 0.1, 0.09, 0.0),
               (1.58, 0.055, 0.055, -0.01)],
        neck=(0, -0.015, 1.56), sh=(0.23, 0.0, 1.46), elbow=(0.3, 0.03, 1.18), wrist=(0.33, -0.02, 0.94),
        upper=0.062, fore=0.052, wrist_r=0.038, hand=0.055,
        mats=dict(leg=SKIN, foot=SKIN, torso=SKIN, arm=SKIN, hand=SKIN))
    pts = humanoid(m, s)
    # long royal dodot: green kain to the shins, gold hem + front panel, flowing back train
    m.lathe("body", GREEN, [(0.26, 0.34), (0.22, 0.6), (0.18, 0.9), (0.16, 1.1)], segs=16, smooth=True)
    m.torus("body", GOLD, 0.26, 0.022, loc=(0, 0, 0.34), segs=16, rsegs=4)
    m.box("body", GOLD, (0.12, 0.02, 0.66), loc=(0, -0.2, 0.72), rot=(-6, 0, 0))
    m.torus("body", GOLD, 0.165, 0.035, loc=(0, 0, 1.1), scale=(1, 0.72, 0.9), segs=16, rsegs=5)
    # green sash across the chest (slempang) + gold collar
    m.torus("body", GREEN, 0.2, 0.03, loc=(0, -0.0, 1.3), rot=(0, 38, 0), scale=(1, 0.66, 1), segs=16, rsegs=5)
    m.torus("body", GOLD, 0.11, 0.03, loc=(0, -0.03, 1.49), rot=(-20, 0, 0), scale=(1.25, 1.0, 0.6), segs=16, rsegs=5)
    # head: slim face, eyes, long hair (ukel) at the back
    hc = V(0, -0.02, 1.68)
    m.sphere("head", SKIN, 0.115, loc=hc, scale=(0.95, 1.05, 1.1), segs=14, rings=10)
    m.sphere("head", SKIN, 0.05, loc=hc + V(0, -0.1, -0.05), scale=(0.8, 1.0, 1.1), segs=8, rings=6)
    eye_pair(m, "head", m.mat("M_Eye", "#f2e8d0"), (0, hc.y - 0.1, hc.z + 0.01), 0.044, 0.024)
    eye_pair(m, "head", DARK, (0, hc.y - 0.113, hc.z + 0.01), 0.044, 0.012)
    m.sphere("head", DARK, 0.1, loc=hc + V(0, 0.07, -0.05), scale=(1.0, 0.8, 1.0), segs=10, rings=6)
    m.sphere("head", DARK, 0.08, loc=hc + V(0, 0.14, -0.14), scale=(1.2, 0.8, 1.2), segs=10, rings=6)
    jamang(m, "head", GOLD, GREEN, (0, -0.02, 1.74), 0.12, tall=0.32)
    armlets(m, GOLD, pts, 0.075, 0.05)
    # the bow in the left hand (vertical, string towards the body)
    hl = pts["hand_l"]
    bow = [(hl.x + 0.02, hl.y - 0.02 + 0.12 * math.sin(math.pi * t) ** 0.7 * -1, hl.z + 1.4 * (t - 0.5))
           for t in [i / 8 for i in range(9)]]
    m.loft("arm_l", GOLD, bow, [0.018, 0.024, 0.028, 0.03, 0.032, 0.03, 0.028, 0.024, 0.018], segs=6, res=2,
           ref=(1, 0, 0))
    m.cyl("arm_l", DARK, 0.004, 1.38, loc=(hl.x + 0.02, hl.y + 0.0, hl.z), segs=4)
    for sg in (1, -1):
        m.sphere("arm_l", GREEN, 0.03, loc=(hl.x + 0.02, hl.y - 0.02, hl.z + sg * 0.7), segs=8, rings=5)
    # quiver on the back
    m.cyl("body", GREEN, 0.07, 0.6, loc=(0.1, 0.16, 1.3), rot=(20, -25, 0), segs=10)
    for i in range(3):
        m.cyl("body", GOLD, 0.012, 0.25, loc=(0.18 + i * 0.03, 0.26, 1.63 - i * 0.02), rot=(20, -25, 0), segs=5)
    return m


# ------------------------------------------------------------------ Jembawan
def jembawan():
    m = Model("jembawan")
    FUR = m.mat("M_Fur", "#7b6a5a")
    PALE = m.mat("M_FurPale", "#d8d0c2")
    CLOTH = m.mat("M_Cloth", "#6b3b2a")
    GOLD = m.mat("M_Gold", "#c89b3c")
    DARK = m.mat("M_Dark", "#1c1a1f")
    s = dict(
        hip=0.72, leg_x=0.13, leg_z=0.7, knee=0.38, knee_y=-0.06, ankle=0.08,
        thigh=0.11, calf=0.085, ankle_r=0.06, foot=(0.16, 0.26, 0.1),
        # hunched: torso leans forward as it rises
        torso=[(0.62, 0.22, 0.17, 0.02), (0.75, 0.26, 0.2, 0.0), (0.95, 0.27, 0.21, -0.06),
               (1.1, 0.25, 0.19, -0.14), (1.2, 0.2, 0.16, -0.2), (1.26, 0.1, 0.1, -0.25)],
        neck=(0, -0.26, 1.2), sh=(0.24, -0.15, 1.12), elbow=(0.33, -0.2, 0.86), wrist=(0.34, -0.3, 0.66),
        upper=0.085, fore=0.075, wrist_r=0.06, hand=0.075,
        mats=dict(leg=FUR, foot=FUR, torso=FUR, arm=FUR, hand=FUR), torso_segs=14)
    pts = humanoid(m, s)
    # hump on the back
    m.sphere("body", FUR, 0.2, loc=(0, 0.02, 1.1), scale=(1.2, 1.0, 0.8), segs=12, rings=8)
    # sarong (kain) - brown with gold hem
    m.lathe("body", CLOTH, [(0.3, 0.3), (0.28, 0.5), (0.25, 0.8)], loc=(0, 0.0, 0), segs=16, smooth=True)
    m.torus("body", GOLD, 0.3, 0.02, loc=(0, 0, 0.3), segs=16, rsegs=4)
    m.torus("body", CLOTH, 0.25, 0.045, loc=(0, 0, 0.8), segs=16, rsegs=5, scale=(1, 0.85, 1))
    # shawl over shoulders
    m.torus("body", CLOTH, 0.19, 0.06, loc=(0, -0.12, 1.14), rot=(-30, 0, 0), segs=16, rsegs=6, scale=(1.25, 1, 1))
    # head: bear with long pale beard and brows, round ears
    hc = V(0, -0.34, 1.26)
    m.sphere("head", FUR, 0.15, loc=hc, scale=(1.05, 1.0, 0.95), segs=14, rings=10)
    m.sphere("head", PALE, 0.08, loc=hc + V(0, -0.13, -0.04), scale=(0.9, 1.1, 0.75), segs=10, rings=7)
    m.sphere("head", DARK, 0.03, loc=hc + V(0, -0.22, -0.02), segs=8, rings=5)
    for sg in (1, -1):
        m.sphere("head", FUR, 0.05, loc=hc + V(sg * 0.11, 0.02, 0.11), scale=(1, 0.6, 1), segs=8, rings=6)
        m.sphere("head", PALE, 0.035, loc=hc + V(sg * 0.055, -0.13, 0.06), scale=(1.4, 0.7, 0.6), segs=8, rings=5)
    eye_pair(m, "head", DARK, (0, hc.y - 0.135, hc.z + 0.03), 0.05, 0.016)
    beard = [hc + V(0, -0.12, -0.08), hc + V(0, -0.14, -0.2), hc + V(0, -0.1, -0.34)]
    m.loft("head", PALE, beard, [(0.09, 0.05), (0.08, 0.05), (0.01, 0.01)], segs=8, res=3)
    # small gold head band (sage's topknot ring)
    m.torus("head", GOLD, 0.06, 0.018, loc=hc + V(0, 0.03, 0.14), segs=10, rsegs=4)
    m.sphere("head", PALE, 0.06, loc=hc + V(0, 0.03, 0.18), segs=8, rings=6)
    # staff (weapon): gnarled wooden tongkat, vertical, taller than him
    h = pts["hand_r"]
    m.pivot("weapon", h, parent="arm_r")
    m.loft("weapon", CLOTH, [(h.x - 0.02, h.y, 0.0), (h.x, h.y - 0.02, h.z), (h.x + 0.02, h.y, 1.4),
                             (h.x - 0.05, h.y, 1.55)], [0.025, 0.028, 0.025, 0.03], segs=6, res=2, ref=(0, -1, 0))
    m.torus("weapon", GOLD, 0.06, 0.02, loc=(h.x - 0.05, h.y, 1.58), rot=(90, 0, 0), segs=10, rsegs=4)
    return m


BUILDERS = {"hanoman": hanoman, "rama": rama, "jembawan": jembawan, "sugriwa": sugriwa}

if __name__ == "__main__":
    run_cli(BUILDERS)

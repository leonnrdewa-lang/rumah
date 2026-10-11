#!/usr/bin/env python3
"""Hanoman Duta - placeholder dialogue/boon portraits (to be replaced by painted Higgsfield art).

Run:  python3 hanoman/blender/portraits.py [ids...]

Renders a 768x1024 transparent PNG per id into game/assets/portraits/<id>.png:
  hanoman rama jembawan sugriwa sura baya kijang  (built from the game models, posed via their pivots)
  dewa_bayu dewa_surya dewa_baruna dewa_indra      (simple god figures modelled here, portrait-only)

Look: Cycles Toon BSDF (2 tone bands + flat ambient) with Freestyle ink lines, a warm key light and a
strong cool/coloured rim light from behind; Pillow adds paper grain and a slight saturation lift.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import common  # noqa: E402
from common import V, TAU, Model, humanoid, PORTRAIT_DIR, descendants, reset_scene  # noqa: E402
import characters  # noqa: E402
import enemies  # noqa: E402
import bosses  # noqa: E402
from characters import jamang, armlets  # noqa: E402

W, H = 768, 1024


# ------------------------------------------------------------------ god figures (portrait only)
def god(mid, skin, cloth, cloth2, accent, glow, crown_tall=0.3, poleng=False):
    m = Model(mid)
    SKIN = m.mat("M_Skin", skin)
    CLOTH = m.mat("M_Cloth", cloth)
    CLOTH2 = m.mat("M_Cloth2", cloth2)
    GOLD = m.mat("M_Gold", accent)
    GLOW = m.mat("M_Glow" + mid.split("_")[1].title(), glow)
    DARK = m.mat("M_Dark", "#16151a")
    s = dict(
        hip=0.95, leg_x=0.1, leg_z=0.92, knee=0.5, knee_y=-0.02, ankle=0.1,
        thigh=0.09, calf=0.065, ankle_r=0.042, foot=(0.1, 0.25, 0.08),
        torso=[(0.86, 0.16, 0.11, 0.0), (0.98, 0.16, 0.11, 0.0), (1.1, 0.15, 0.1, -0.01),
               (1.3, 0.22, 0.14, -0.03), (1.43, 0.23, 0.13, -0.01), (1.52, 0.1, 0.09, 0.0),
               (1.58, 0.058, 0.058, -0.01)],
        neck=(0, -0.015, 1.56), sh=(0.25, 0.0, 1.46), elbow=(0.33, 0.03, 1.18), wrist=(0.35, -0.02, 0.94),
        upper=0.068, fore=0.058, wrist_r=0.04, hand=0.058,
        mats=dict(leg=SKIN, foot=SKIN, torso=SKIN, arm=SKIN, hand=SKIN))
    pts = humanoid(m, s)
    if poleng:
        m.poleng("body", CLOTH, CLOTH2, 1.1, 0.5, (0.17, 0.12), rows=4, cols=12, flare=0.1)
    else:
        m.lathe("body", CLOTH, [(0.26, 0.4), (0.21, 0.7), (0.17, 1.1)], segs=16)
        m.torus("body", GOLD, 0.26, 0.022, loc=(0, 0, 0.4), segs=16, rsegs=4)
    m.torus("body", GOLD, 0.17, 0.035, loc=(0, 0, 1.1), scale=(1, 0.72, 0.9), segs=16, rsegs=5)
    # sash across the chest + broad gold necklace (praba-like)
    m.torus("body", CLOTH2 if not poleng else GLOW, 0.21, 0.03, loc=(0, 0, 1.3), rot=(0, 38, 0), scale=(1, 0.66, 1),
            segs=16, rsegs=5)
    m.torus("body", GOLD, 0.12, 0.035, loc=(0, -0.03, 1.5), rot=(-20, 0, 0), scale=(1.3, 1.0, 0.6), segs=16, rsegs=5)
    hc = V(0, -0.02, 1.69)
    m.sphere("head", SKIN, 0.115, loc=hc, scale=(0.95, 1.05, 1.1), segs=16, rings=10)
    m.sphere("head", SKIN, 0.045, loc=hc + V(0, -0.1, -0.03), scale=(0.7, 1.0, 1.0), segs=8, rings=6)
    for sg in (1, -1):
        m.sphere("head", m.mat("M_Eye", "#f4ecd8"), 0.026, loc=hc + V(sg * 0.044, -0.098, 0.01), scale=(1.3, 0.6, 0.8),
                 segs=8, rings=5)
        m.sphere("head", DARK, 0.013, loc=hc + V(sg * 0.044, -0.114, 0.01), segs=6, rings=4)
        m.box("head", DARK, (0.05, 0.01, 0.008), loc=hc + V(sg * 0.042, -0.105, 0.04), rot=(0, -sg * 10, 0))
    m.sphere("head", DARK, 0.1, loc=hc + V(0, 0.07, -0.05), scale=(1.0, 0.8, 1.0), segs=10, rings=6)
    jamang(m, "head", GOLD, GLOW, (0, -0.02, 1.75), 0.12, tall=crown_tall)
    armlets(m, GOLD, pts, 0.08, 0.052)
    return m, pts, hc, dict(SKIN=SKIN, CLOTH=CLOTH, CLOTH2=CLOTH2, GOLD=GOLD, GLOW=GLOW, DARK=DARK)


def dewa_bayu():
    m, p, hc, M = god("dewa_bayu", "#7a5a48", "#ece6d8", "#23222a", "#c8d2d8", "#5fe0c8", crown_tall=0.22,
                      poleng=True)
    # swirling wind ribbons (teal glow) around the body
    for k in range(3):
        pts = []
        for i in range(14):
            a = i / 13 * TAU * 0.9 + k * 2.1
            r = 0.38 + 0.08 * math.sin(i * 0.8 + k)
            pts.append((math.cos(a) * r, math.sin(a) * r * 0.8, 0.95 + i * 0.05 + k * 0.1))
        m.loft("body", M["GLOW"], pts, [(0.004, 0.004)] + [(0.05, 0.006)] * 12 + [(0.004, 0.004)], segs=4, res=1,
               ref=(0, 0, 1))
    # the Pancanaka claw nail (Bayu's kuku) on the raised right hand
    h = p["hand_r"]
    m.cyl("arm_r", M["GOLD"], 0.018, 0.16, loc=h + V(0, -0.05, 0.06), rot=(-30, 0, 0), r2=0.002, segs=6)
    return m


def dewa_surya():
    m, p, hc, M = god("dewa_surya", "#c98a4a", "#e0701f", "#8a2a1a", "#f2b845", "#ffc640", crown_tall=0.34)
    # sun-disc halo (surya majapahit: disc with 8 main + 8 short rays) behind the head
    c = hc + V(0, 0.2, 0.05)
    m.cyl("head", M["GLOW"], 0.32, 0.03, loc=c, rot=(90, 0, 0), segs=24)
    m.cyl("head", M["GOLD"], 0.22, 0.035, loc=c + V(0, -0.005, 0), rot=(90, 0, 0), segs=24)
    for k in range(16):
        a = TAU * k / 16
        L = 0.24 if k % 2 == 0 else 0.14
        m.prism("head", M["GLOW"], [(-0.05, 0), (0.05, 0), (0, L)], 0.025,
                loc=c + V(math.cos(a) * 0.3, 0.005, math.sin(a) * 0.3), rot=(0, math.degrees(-a) + 90, 0))
    return m


def dewa_baruna():
    m, p, hc, M = god("dewa_baruna", "#4a78a8", "#1d3f7a", "#4aa3ff", "#9fd0ff", "#4aa3ff", crown_tall=0.0)
    # wave crown: curling crests
    for k in range(5):
        x = (k - 2) * 0.07
        base = hc + V(x, -0.02 + abs(k - 2) * 0.03, 0.12)
        m.loft("head", M["GLOW"], [base, base + V(0, 0.02, 0.12 + 0.04 * (k == 2)), base + V(0, -0.06, 0.18),
                                    base + V(0, -0.08, 0.12)], [0.035, 0.03, 0.02, 0.004], segs=6, res=3)
    # trident in the right hand
    h = p["hand_r"]
    m.pivot("weapon", h, parent="arm_r")
    m.cyl("weapon", M["GOLD"], 0.018, 2.0, loc=h + V(0, 0, 0.55), segs=8)
    for x in (-0.1, 0, 0.1):
        m.cyl("weapon", M["GOLD"], 0.02, 0.28 if x == 0 else 0.2, loc=h + V(x, 0, 1.62 + (0.04 if x == 0 else 0)),
              r2=0.002, segs=6)
    m.loft("weapon", M["GOLD"], [h + V(-0.1, 0, 1.52), h + V(0, 0, 1.47), h + V(0.1, 0, 1.52)], [0.02, 0.025, 0.02],
           segs=6, res=2, ref=(0, -1, 0))
    return m


def dewa_indra():
    m, p, hc, M = god("dewa_indra", "#e2c2a6", "#f2eef6", "#6b3fb8", "#d9a93a", "#b784ff", crown_tall=0.42)
    # vajra (double-ended thunderbolt sceptre) in the right hand + crackling arcs
    h = p["hand_r"]
    m.pivot("weapon", h, parent="arm_r")
    m.cyl("weapon", M["GOLD"], 0.025, 0.14, loc=h, segs=8)
    for sg in (1, -1):
        c = h + V(0, 0, sg * 0.13)
        m.sphere("weapon", M["GOLD"], 0.035, loc=c - V(0, 0, sg * 0.04), segs=8, rings=5)
        for k in range(4):
            a = TAU * k / 4
            m.loft("weapon", M["GOLD"], [c - V(0, 0, sg * 0.04), c + V(math.cos(a) * 0.05, math.sin(a) * 0.05, sg * 0.04),
                                         c + V(0, 0, sg * 0.12)], [0.012, 0.01, 0.004], segs=4, res=2)
        m.cyl("weapon", M["GLOW"], 0.012, 0.14, loc=c + V(0, 0, sg * 0.06), segs=5)
    rnd = random.Random(3)
    for k in range(3):
        pts = [h + V(0, 0, 0.25)]
        for i in range(5):
            pts.append(pts[-1] + V(rnd.uniform(-0.12, 0.12), rnd.uniform(-0.08, 0.08), 0.09))
        for a, b in zip(pts, pts[1:]):
            m.loft("weapon", M["GLOW"], [a, b], [0.012, 0.012], segs=4)
    return m


# ------------------------------------------------------------------ posing / framing
# per id: builder, pivot rotations (deg, XYZ), camera: target (world), distance, yaw, pitch, lens, rim colour
SHOTS = {
    "hanoman": (characters.hanoman, {"arm_r": (-70, 0, 15), "arm_l": (-15, -25, 0), "head": (5, 0, -12),
                                     "body": (0, 0, -8), "tail": (0, 0, 20)},
                dict(target=(0, -0.05, 1.3), dist=3.5, yaw=-28, pitch=6, lens=50, rim="#9fe8ff")),
    "rama": (characters.rama, {"arm_l": (-25, -10, 0), "arm_r": (-10, 10, 0), "head": (0, 0, -10)},
             dict(target=(0, 0, 1.4), dist=3.6, yaw=-25, pitch=5, lens=50, rim="#c8ffd8")),
    "jembawan": (characters.jembawan, {"head": (-10, 0, 10), "arm_r": (-10, 0, 0)},
                 dict(target=(0, -0.2, 1.0), dist=3.4, yaw=-30, pitch=4, lens=50, rim="#ffe0a0")),
    "sugriwa": (characters.sugriwa, {"arm_r": (-40, 20, 0), "arm_l": (-40, -20, 0), "head": (6, 0, 10)},
                dict(target=(0, -0.05, 1.35), dist=3.4, yaw=-25, pitch=6, lens=50, rim="#ffd0a0")),
    "sura": (bosses.sura, {"body": (-35, 0, 0), "head": (-10, 0, 0), "jaw": (22, 0, 0), "tail": (40, 0, 0),
                           "arm_l": (0, -20, 0), "arm_r": (0, 20, 0)},
             dict(target=(0, -1.3, 1.7), dist=8.2, yaw=-35, pitch=8, lens=50, rim="#8fd0ff")),
    "baya": (bosses.baya, {"head": (-12, 0, 0), "jaw": (28, 0, 0), "tail": (0, 0, 25), "tail_tip": (0, 0, 30)},
             dict(target=(0, -2.0, 0.75), dist=7.6, yaw=-40, pitch=16, lens=50, rim="#d8ff9a")),
    "kijang": (enemies.kijang, {"head": (8, 0, -15), "arm_l": (-30, 0, 0)},
               dict(target=(0, -0.3, 1.1), dist=4.8, yaw=-40, pitch=4, lens=50, rim="#9affc0")),
    "dewa_bayu": (dewa_bayu, {"arm_r": (-55, 0, 20), "arm_l": (-10, -20, 0), "head": (5, 0, -8)},
                  dict(target=(0, 0, 1.45), dist=3.2, yaw=-22, pitch=5, lens=50, rim="#5fe0c8")),
    "dewa_surya": (dewa_surya, {"arm_r": (-35, 0, 25), "arm_l": (-35, 0, -25), "head": (3, 0, 0)},
                   dict(target=(0, 0, 1.5), dist=3.2, yaw=-18, pitch=5, lens=50, rim="#ffb040")),
    "dewa_baruna": (dewa_baruna, {"arm_r": (-25, 0, 10), "head": (0, 0, -8)},
                    dict(target=(0, 0, 1.5), dist=3.6, yaw=-22, pitch=5, lens=50, rim="#4aa3ff")),
    "dewa_indra": (dewa_indra, {"arm_r": (-50, 0, 25), "head": (4, 0, -8)},
                   dict(target=(0, 0, 1.5), dist=3.4, yaw=-22, pitch=5, lens=50, rim="#b784ff")),
}


def sun(name, travel, energy, color):
    L = bpy.data.lights.new(name, "SUN")
    L.energy = energy
    L.color = tuple(color)
    L.angle = math.radians(2)
    o = bpy.data.objects.new(name, L)
    o.rotation_euler = V(travel).normalized().to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


def render_portrait(pid):
    reset_scene()
    builder, pose, cam = SHOTS[pid]
    root = builder().build()
    objs = {o.name: o for o in descendants(root)}
    for name, rot in pose.items():
        if name in objs:
            objs[name].rotation_euler = tuple(math.radians(a) for a in rot)
    bpy.context.view_layer.update()
    common.toonify_materials(shade=0.3)
    common.setup_toon_render(W, H, transparent=True, samples=24, line=3.4)
    s = bpy.context.scene
    s.render.film_transparent = True
    tgt = V(cam["target"])
    yaw, pitch = math.radians(cam["yaw"]), math.radians(cam["pitch"])
    d = V(math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))
    # lights (given as travel directions): warm key from upper camera-left, coloured rim from behind
    side = d.cross(V(0, 0, 1)).normalized()
    sun("_Key", -(d * 0.8 + side * 0.7 + V(0, 0, 0.9)), 3.4, (1.0, 0.92, 0.8))
    sun("_Rim", d * 1.0 - side * 0.5 + V(0, 0, -0.5), 9.0, common.hex_rgba(cam["rim"])[:3])
    sun("_Rim2", d * 1.0 + side * 0.9 + V(0, 0, -0.2), 4.0, common.hex_rgba(cam["rim"])[:3])
    c = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    s.collection.objects.link(c)
    c.location = tgt + d * cam["dist"]
    c.rotation_euler = (tgt - c.location).normalized().to_track_quat("-Z", "Y").to_euler()
    c.data.lens = cam["lens"]
    c.data.sensor_fit = "VERTICAL"
    s.camera = c
    path = os.path.join(PORTRAIT_DIR, pid + ".png")
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    postprocess(path)
    print(f"[portrait] {pid}.png")


def postprocess(path):
    """Paper grain + gentle saturation/contrast lift; alpha kept (slightly softened edge)."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:
        return
    im = Image.open(path).convert("RGBA")
    rgb = im.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(1.15)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.06)
    # paper grain: low-frequency blotches + fine noise, multiplied in
    rnd = random.Random(1)
    small = Image.new("L", (W // 8, H // 8))
    small.putdata([int(235 + rnd.random() * 20) for _ in range(small.width * small.height)])
    blot = small.resize((W, H), Image.BICUBIC)
    fine = Image.effect_noise((W, H), 18).point(lambda v: int(240 + (v - 128) * 0.12))
    grain = Image.blend(blot, fine, 0.5).convert("RGB")
    from PIL import ImageChops
    rgb = ImageChops.multiply(rgb, grain)
    rgb = ImageChops.screen(rgb, Image.new("RGB", (W, H), (14, 10, 8)))
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(0.6))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    out.save(path)


if __name__ == "__main__":
    ids = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SHOTS)
    for pid in ids:
        render_portrait(pid)

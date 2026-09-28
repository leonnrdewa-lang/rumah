#!/usr/bin/env python3
"""Hanoman Duta - title-screen key art -> game/assets/portraits/title.png (1920x1080, opaque).

Run:  python3 hanoman/blender/title.py [--fast]

Two toon+Freestyle renders are layered in Pillow over a painted night sky:
  sky (gradient, big pale moon + halo)  <  background layer (gapura, beringin, ruins; hazed)
  <  mist band (teal/magenta)  <  foreground layer (Hanoman leaping with the gada, glowing flowers).
The upper ~30% is kept dark and empty for the "HANOMAN DUTA" title text.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import common  # noqa: E402
from common import V, PORTRAIT_DIR, descendants, reset_scene  # noqa: E402
import characters  # noqa: E402
import props  # noqa: E402
from portraits import sun  # noqa: E402

W, H = 1920, 1080
FAST = "--fast" in sys.argv
SCR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")


GATE = (1.2, 20.0, 0.0)
CAM_LOC = (-1.25, -4.3, 1.2)
CAM_TGT = (0.25, 0.0, 1.55)


def place(builder, loc=(0, 0, 0), rotz=0.0, scale=1.0):
    root = builder().build()
    root.location = loc
    root.rotation_euler = (0, 0, math.radians(rotz))
    root.scale = (scale, scale, scale)
    return root


def darken_materials(objs, factor=0.28, tint=(0.05, 0.08, 0.12)):
    """Background silhouettes: darken + tint non-glow materials (makes per-object copies)."""
    done = {}
    for o in objs:
        if o.type != "MESH":
            continue
        for i, m in enumerate(o.data.materials):
            if m is None or m.name.startswith("M_Glow"):
                continue
            if m.name not in done:
                c = m.copy()
                c.name = "_bg_" + m.name
                b = c.node_tree.nodes["Principled BSDF"]
                col = b.inputs["Base Color"].default_value
                b.inputs["Base Color"].default_value = (col[0] * factor + tint[0], col[1] * factor + tint[1],
                                                        col[2] * factor + tint[2], 1)
                done[m.name] = c
            o.data.materials[i] = done[m.name]


def build_scene():
    reset_scene()
    fg, bg = [], []
    # --- hero: Hanoman mid-leap, gada swung up across the frame
    h = place(characters.hanoman, (0.0, 0.0, 0.3), rotz=-12)
    parts = {o.name: o for o in descendants(h)}
    pose = {"body": (10, -8, 0), "head": (-8, 0, 8), "leg_l": (-75, 0, 8), "leg_r": (40, 0, -5),
            "arm_r": (-120, 38, -10), "weapon": (95, 0, 20), "arm_l": (45, -35, 0), "tail": (25, 0, 30)}
    for k, r in pose.items():
        parts[k].rotation_euler = tuple(math.radians(a) for a in r)
    fg += descendants(h)
    for b, loc, rz, s in ((props.bunga_glow, (-2.3, -1.9, 0), 0, 1.3), (props.bunga_glow, (2.1, -1.2, 0), 50, 1.1),
                          (props.pakis, (-3.0, -0.8, 0), 20, 1.4), (props.batu, (1.6, -2.3, 0), 30, 1.0),
                          (props.pakis, (3.2, 0.4, 0), 70, 1.3), (props.wijayakusuma, (1.1, -2.0, 0), 0, 1.4)):
        fg += descendants(place(b, loc, rz, s))
    # --- background
    for b, loc, rz, s in ((props.gapura, GATE, 0, 1.2), (props.oncor, (GATE[0] - 2.4, GATE[1] - 1.5, 0), 0, 1.3),
                          (props.oncor, (GATE[0] + 2.4, GATE[1] - 1.5, 0), 0, 1.3),
                          (props.beringin, (-14, 26, 0), 20, 1.4), (props.beringin, (16, 30, 0), 80, 1.3),
                          (props.pohon_mati, (8.5, 13, 0), 0, 1.3), (props.bakau, (-9.0, 16, 0), 0, 1.3),
                          (props.candi_pilar, (-6.5, 11, 0), 15, 1.2), (props.candi_reruntuhan, (-9.5, 19, 0), -20, 1.3),
                          (props.arca, (GATE[0] + 4.3, GATE[1] - 2.5, 0), -25, 1.2),
                          (props.arca, (GATE[0] - 4.3, GATE[1] - 2.5, 0), 25, 1.2),
                          (props.batu_besar, (-4.8, 6.5, 0), 10, 0.9), (props.semak, (6.5, 7.5, 0), 0, 1.4),
                          (props.semak, (-7.5, 8.0, 0), 0, 1.6), (props.candi_pilar, (12.0, 20.0, 0), 50, 1.3),
                          (props.batu, (3.5, 4.5, 0), 0, 1.2)):
        bg += descendants(place(b, loc, rz, s))
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 20, 0))
    ground = bpy.context.view_layer.objects.active
    ground.data.materials.append(common.get_mat("M_Ground", "#1f2a2a"))
    bg.append(ground)
    darken_materials([o for o in bg if o is not ground], factor=0.32, tint=(0.01, 0.02, 0.035))
    return fg, bg


def setup(line):
    common.toonify_materials(shade=0.28, size=0.55)
    common.setup_toon_render(W, H, transparent=True, samples=8 if FAST else 24, line=line)
    s = bpy.context.scene
    if FAST:
        s.render.resolution_percentage = 50
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    s.collection.objects.link(cam)
    cam.location = CAM_LOC
    tgt = V(CAM_TGT)
    cam.rotation_euler = (tgt - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 28
    cam.data.shift_y = 0.05  # keep the horizon low -> dark empty band on top for the title
    cam.data.clip_end = 200
    s.camera = cam
    # moonlight rim from behind (upper right), teal key from the left, magenta kicker from the right
    sun("_Moon", V(-0.35, -1.0, -0.45), 7.0, (0.85, 0.92, 1.0))
    sun("_Teal", V(1.0, 0.45, -0.35), 2.6, common.hex_rgba("#5fe0c8")[:3])
    sun("_Mag", V(-1.0, 0.2, -0.2), 2.0, common.hex_rgba("#e0508f")[:3])
    sun("_Fill", V(0.2, 1.0, -0.6), 0.8, (0.7, 0.75, 1.0))
    return s


def render_layer(s, show, hide, path, line):
    for o in hide:
        o.hide_render = True
    for o in show:
        o.hide_render = False
    ls = s.view_layers[0].freestyle_settings.linesets[0].linestyle
    ls.thickness = line
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)


def moon_pos():
    """Screen position (pixels) of a point high in the gapura gap, so the moon shows through the split gate."""
    from bpy_extras.object_utils import world_to_camera_view
    s = bpy.context.scene
    p = world_to_camera_view(s, s.camera, V(GATE[0], GATE[1], 3.2))
    return int(p.x * W), int((1 - p.y) * H) - 60


def sky(mpos=None):
    from PIL import Image, ImageDraw, ImageFilter
    top, mid, hor = (8, 10, 16), (16, 22, 34), (34, 52, 62)
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        t = y / H
        if t < 0.45:
            a, b, f = top, mid, t / 0.45
        else:
            a, b, f = mid, hor, min(1, (t - 0.45) / 0.3)
        c = tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))
        for x in range(W):
            px[x, y] = c
    # stars (sparse, only low contrast so the title stays readable)
    rnd = random.Random(4)
    d = ImageDraw.Draw(im)
    for _ in range(160):
        x, y = rnd.randrange(W), rnd.randrange(int(H * 0.6))
        v = rnd.randrange(40, 90)
        d.point((x, y), fill=(v, v, v + 10))
    # moon + halo
    mx, my = mpos or (int(W * 0.6), int(H * 0.47))
    r = 170
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).ellipse((mx - r * 2.2, my - r * 2.2, mx + r * 2.2, my + r * 2.2), fill=110)
    halo = halo.filter(ImageFilter.GaussianBlur(90))
    im = Image.composite(Image.new("RGB", (W, H), (120, 150, 165)), im, halo)
    moon = Image.new("L", (W, H), 0)
    ImageDraw.Draw(moon).ellipse((mx - r, my - r, mx + r, my + r), fill=255)
    moon = moon.filter(ImageFilter.GaussianBlur(1.5))
    mcol = Image.new("RGB", (W, H), (236, 232, 212))
    # soft craters
    cr = ImageDraw.Draw(mcol)
    for (dx, dy, rr) in ((-50, -40, 38), (40, 30, 28), (-10, 70, 22), (70, -60, 18), (-80, 40, 16)):
        cr.ellipse((mx + dx - rr, my + dy - rr, mx + dx + rr, my + dy + rr), fill=(214, 210, 192))
    im = Image.composite(mcol, im, moon)
    return im


def compose(bg_path, fg_path, out, mpos=None):
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter
    base = sky(mpos)
    bgl = Image.open(bg_path).convert("RGBA").resize((W, H))
    # atmospheric haze on the background layer
    haze = Image.new("RGBA", (W, H), (30, 48, 60, 255))
    r, g, b, a = bgl.split()
    hazed = Image.blend(bgl, haze, 0.22)
    hazed.putalpha(a)
    base = base.convert("RGBA")
    base.alpha_composite(hazed)
    # mist band with teal / magenta glows near the ground line
    mist = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mist)
    rnd = random.Random(2)
    for _ in range(26):
        x = rnd.randrange(-200, W)
        y = rnd.randrange(int(H * 0.62), int(H * 0.8))
        w, h = rnd.randrange(300, 700), rnd.randrange(40, 90)
        md.ellipse((x, y, x + w, y + h), fill=(110, 150, 160, 38))
    for (x, y, col, rr) in ((W * 0.22, H * 0.78, (224, 80, 143, 70), 220), (W * 0.8, H * 0.74, (95, 224, 200, 70), 260),
                            (W * 0.45, H * 0.86, (95, 224, 200, 50), 300)):
        md.ellipse((x - rr, y - rr * 0.45, x + rr, y + rr * 0.45), fill=col)
    mist = mist.filter(ImageFilter.GaussianBlur(40))
    base.alpha_composite(mist)
    fgl = Image.open(fg_path).convert("RGBA").resize((W, H))
    # soft glow around glowing bits of the foreground (bright pixels, bloomed)
    bright = fgl.convert("L").point(lambda v: 255 if v > 215 else 0).filter(ImageFilter.GaussianBlur(14))
    glow = Image.new("RGBA", (W, H), (120, 230, 210, 0))
    glow.putalpha(bright.point(lambda v: int(v * 0.35)))
    base.alpha_composite(fgl)
    base.alpha_composite(glow)
    # vignette + keep the top band dark for the title
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.rectangle((0, 0, W, int(H * 0.3)), fill=90)
    vd.ellipse((-W * 0.2, -H * 0.1, W * 1.2, H * 1.25), fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    base = Image.composite(Image.new("RGBA", (W, H), (6, 8, 12, 255)), base, vig)
    top = Image.new("L", (W, H), 0)
    ImageDraw.Draw(top).rectangle((0, 0, W, int(H * 0.22)), fill=120)
    top = top.filter(ImageFilter.GaussianBlur(80))
    base = Image.composite(Image.new("RGBA", (W, H), (6, 8, 12, 255)), base, top)
    # paper grain
    rgb = base.convert("RGB")
    fine = Image.effect_noise((W, H), 16).point(lambda v: int(242 + (v - 128) * 0.1)).convert("RGB")
    rgb = ImageChops.multiply(rgb, fine)
    rgb = ImageEnhance.Color(rgb).enhance(1.1)
    rgb.save(out)


def main():
    fg, bg = build_scene()
    s = setup(line=3.0)
    bgp = os.path.join(SCR, "_title_bg.png")
    fgp = os.path.join(SCR, "_title_fg.png")
    # background: fg objects hidden (no holdout needed: hero is layered on top afterwards)
    render_layer(s, bg, fg, bgp, line=2.0 if not FAST else 1.2)
    render_layer(s, fg, bg, fgp, line=3.6 if not FAST else 2.0)
    out = os.path.join(PORTRAIT_DIR, "title.png")
    mp = moon_pos()
    print("[title] moon at", mp)
    compose(bgp, fgp, out, mp)
    for p in (bgp, fgp):
        os.remove(p)
    print("[title] title.png")


if __name__ == "__main__":
    main()

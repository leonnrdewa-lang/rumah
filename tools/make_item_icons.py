"""Item icons for fishing and the bag, drawn with Pillow in a cel-shaded look close to
the Blender-rendered item icons: the fish species, the fishing rod (pancing), the
bag HUD badge (ui_bag) and the house / bed glyphs.

python3 tools/make_item_icons.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_ui_icons import Pad, shade, CREAM_HI  # noqa: E402

INK = (58, 36, 24, 255)

# species: body colour, belly colour, fin colour, shape (length, height), extras
FISH = {
    "ikan_nila": ((122, 128, 118, 255), (214, 206, 186, 255), (196, 92, 70, 255), (0.62, 0.34), "stripes"),
    "ikan_lele": ((92, 84, 78, 255), (190, 178, 160, 255), (70, 62, 58, 255), (0.74, 0.2), "whiskers"),
    "ikan_patin": ((150, 162, 172, 255), (236, 236, 232, 255), (120, 130, 140, 255), (0.72, 0.26), ""),
    "ikan_gabus": ((96, 104, 70, 255), (206, 196, 150, 255), (80, 86, 58, 255), (0.74, 0.22), "spots"),
    "ikan_bawal": ((168, 168, 176, 255), (230, 228, 232, 255), (60, 60, 70, 255), (0.54, 0.44), ""),
    "ikan_kakap": ((214, 96, 70, 255), (246, 196, 170, 255), (190, 70, 50, 255), (0.64, 0.34), ""),
    "ikan_arwana": ((226, 172, 60, 255), (250, 226, 150, 255), (214, 110, 40, 255), (0.76, 0.26), "scales"),
}


def fish(name, body, belly, fin, dims, extra, px=128):
    p = Pad(px)
    L, Hh = dims
    cx, cy = 0.47, 0.52
    x0, x1 = cx - L / 2, cx + L / 2
    tilt = -0.18

    def R(x, y):
        dx, dy = x - cx, y - cy
        return (cx + dx * math.cos(tilt) - dy * math.sin(tilt), cy + dx * math.sin(tilt) + dy * math.cos(tilt))

    def body_pts(scale=1.0, dy=0.0, top_only=False, bottom_only=False):
        pts = []
        n = 40
        for i in range(n + 1):
            u = i / n
            x = x0 + u * L
            # plump front, tapering tail
            h = Hh * 0.5 * scale * (math.sin(math.pi * min(1.0, u * 1.05)) ** 0.7) * (1.0 - 0.55 * u ** 2.2)
            pts.append((x, cy - h + dy))
        bottom = []
        for i in range(n, -1, -1):
            u = i / n
            x = x0 + u * L
            h = Hh * 0.5 * scale * (math.sin(math.pi * min(1.0, u * 1.05)) ** 0.7) * (1.0 - 0.55 * u ** 2.2)
            bottom.append((x, cy + h * (0.95 if not bottom_only else 1.0) + dy))
        if top_only:
            return pts + [(x1, cy + dy), (x0, cy + dy)]
        if bottom_only:
            return [(x0, cy + dy), (x1, cy + dy)] + bottom[::1]
        return pts + bottom

    # tail
    tail = [(x1 - 0.04, cy), (x1 + 0.16, cy - Hh * 0.55), (x1 + 0.1, cy), (x1 + 0.16, cy + Hh * 0.55)]
    ol = 0.022
    p.poly([R(x, y) for x, y in [(tail[0][0] - ol, cy), (tail[1][0] + ol, tail[1][1] - ol), (tail[2][0] + ol * 0.5, cy), (tail[3][0] + ol, tail[3][1] + ol)]], INK)
    p.poly([R(x, y) for x, y in tail], fin)
    # dorsal fin
    dors = [(cx - L * 0.2, cy - Hh * 0.42), (cx - L * 0.02, cy - Hh * 0.78), (cx + L * 0.22, cy - Hh * 0.3)]
    p.poly([R(x, y + (-ol if i == 1 else 0)) for i, (x, y) in enumerate(dors)], INK)
    p.poly([R(x, y + 0.012) for x, y in dors], fin)
    # outline + body + belly + highlight
    big = [(cx + (x - cx) * 1.0 + (-ol if x < cx else 0), cy + (y - cy) * (1.0 + ol / max(Hh, 0.1) * 2.2)) for x, y in body_pts()]
    p.poly([R(x, y) for x, y in big], INK)
    p.poly([R(x, y) for x, y in body_pts()], body)
    p.poly([R(x, y) for x, y in body_pts(0.62, Hh * 0.2, bottom_only=True)], belly)
    p.poly([R(x, y) for x, y in body_pts(0.55, -Hh * 0.12, top_only=True)], shade(body, 1.18))
    if extra == "stripes":
        for i in range(4):
            x = cx - L * 0.12 + i * L * 0.12
            p.line([R(x, cy - Hh * 0.35), R(x - 0.02, cy + Hh * 0.25)], shade(body, 0.72), 0.022)
    elif extra == "spots":
        for i in range(5):
            x = cx - L * 0.2 + i * L * 0.13
            p.circle(*R(x, cy - Hh * 0.08 * (i % 2)), 0.022, shade(body, 0.62))
    elif extra == "scales":
        for i in range(4):
            for j in range(2):
                x = cx - L * 0.18 + i * L * 0.12
                y = cy - Hh * 0.14 + j * Hh * 0.26
                p.circle(*R(x, y), 0.03, None, outline=shade(body, 0.8), width=0.012)
    elif extra == "whiskers":
        for a in (-1, 1):
            p.line([R(x0 + 0.03, cy + 0.02), R(x0 - 0.08, cy + 0.02 + a * 0.08 + 0.05)], INK, 0.014)
    # pectoral fin, gill line, eye
    p.poly([R(x, y) for x, y in [(cx - L * 0.2, cy + 0.02), (cx - L * 0.05, cy + Hh * 0.28), (cx - L * 0.02, cy + 0.03)]], shade(fin, 0.9))
    p.line([R(x0 + L * 0.22, cy - Hh * 0.3), R(x0 + L * 0.2, cy + Hh * 0.25)], shade(body, 0.7), 0.016)
    ex, ey = R(x0 + L * 0.1, cy - Hh * 0.08)
    p.circle(ex, ey, 0.045, (250, 246, 236, 255))
    p.circle(ex + 0.006, ey, 0.026, INK)
    p.circle(ex - 0.006, ey - 0.012, 0.009, (255, 255, 255, 255))
    p.save(name)


def udang(px=128):
    p = Pad(px)
    body = (226, 112, 70, 255)
    claw = (70, 110, 170, 255)
    cx, cy = 0.5, 0.52
    segs = []
    for i in range(7):
        a = math.pi * 0.95 - i * 0.2
        r = 0.22
        segs.append((cx + math.cos(a) * r * 1.2, cy - math.sin(a) * r * 0.9 + 0.05, 0.1 - i * 0.009))
    for x, y, r in segs:
        p.circle(x, y, r + 0.02, INK)
    for x, y, r in segs:
        p.circle(x, y, r, body)
        p.circle(x - r * 0.25, y - r * 0.3, r * 0.45, shade(body, 1.2))
    tx, ty, _ = segs[-1]
    p.poly([(tx, ty), (tx + 0.12, ty + 0.06), (tx + 0.1, ty - 0.08)], INK)
    p.poly([(tx + 0.01, ty), (tx + 0.1, ty + 0.04), (tx + 0.085, ty - 0.055)], shade(body, 0.9))
    hx, hy, _ = segs[0]
    # long blue claws (udang galah) and feelers
    p.line([(hx - 0.02, hy + 0.04), (hx - 0.2, hy + 0.2), (hx - 0.02, hy + 0.33)], INK, 0.05)
    p.line([(hx - 0.02, hy + 0.04), (hx - 0.2, hy + 0.2), (hx - 0.02, hy + 0.33)], claw, 0.03)
    p.line([(hx - 0.06, hy - 0.04), (0.1, 0.1)], INK, 0.012)
    p.line([(hx - 0.04, hy - 0.06), (0.24, 0.06)], INK, 0.012)
    p.circle(hx - 0.02, hy - 0.03, 0.022, INK)
    p.save("udang_galah")


def rod(px=128):
    p = Pad(px)
    # bamboo rod diagonal with a reel, line and a red-white bobber
    p.line([(0.2, 0.86), (0.84, 0.12)], INK, 0.07)
    p.line([(0.2, 0.86), (0.84, 0.12)], (201, 169, 94, 255), 0.045)
    for u in (0.3, 0.5, 0.7):
        x, y = 0.2 + u * 0.64, 0.86 - u * 0.74
        p.line([(x - 0.02, y - 0.02), (x + 0.02, y + 0.02)], (151, 121, 58, 255), 0.02)
    p.line([(0.2, 0.86), (0.33, 0.71)], (92, 58, 36, 255), 0.06)
    p.circle(0.37, 0.72, 0.07, INK)
    p.circle(0.37, 0.72, 0.05, (190, 196, 200, 255))
    p.circle(0.37, 0.72, 0.018, INK)
    p.line([(0.84, 0.12), (0.8, 0.45), (0.74, 0.62)], (250, 246, 236, 255), 0.012)
    p.circle(0.74, 0.7, 0.075, INK)
    p.circle(0.74, 0.7, 0.058, (250, 246, 236, 255))
    p.d.pieslice([(0.74 - 0.058) * p.k, (0.7 - 0.058) * p.k, (0.74 + 0.058) * p.k, (0.7 + 0.058) * p.k], 180, 360, fill=(214, 64, 50, 255))
    p.save("icon_pancing")


def bag_badge(px=128):
    p = Pad(px)
    p.badge((138, 96, 60, 255), ring=(98, 64, 38, 255))
    # a canvas backpack: straps, body, rounded flap with a buckle, front pocket
    body = (226, 176, 84, 255)
    dark = (176, 124, 52, 255)
    p.line([(0.36, 0.34), (0.4, 0.2), (0.6, 0.2), (0.64, 0.34)], dark, 0.05)
    p.rect(0.22, 0.42, 0.3, 0.66, dark, r=0.035)
    p.rect(0.7, 0.42, 0.78, 0.66, dark, r=0.035)
    p.rect(0.28, 0.28, 0.72, 0.8, body, r=0.12)
    p.d.pieslice([0.28 * p.k, 0.26 * p.k, 0.72 * p.k, 0.66 * p.k], 180, 360, fill=dark)
    p.rect(0.28, 0.44, 0.72, 0.5, dark, r=0.0)
    p.rect(0.46, 0.42, 0.54, 0.56, (98, 64, 38, 255), r=0.02)
    p.rect(0.35, 0.6, 0.65, 0.75, (244, 212, 140, 255), r=0.05)
    p.line([(0.37, 0.64), (0.63, 0.64)], dark, 0.02)
    p.save("ui_bag")


def bed(px=128):
    p = Pad(px)
    wood = (150, 96, 56, 255)
    p.rect(0.1, 0.36, 0.2, 0.84, INK, r=0.03)
    p.rect(0.12, 0.38, 0.18, 0.82, wood, r=0.02)
    p.rect(0.12, 0.56, 0.9, 0.78, INK, r=0.04)
    p.rect(0.14, 0.58, 0.88, 0.76, wood, r=0.03)
    p.rect(0.16, 0.46, 0.88, 0.62, INK, r=0.06)
    p.rect(0.18, 0.48, 0.86, 0.6, (250, 246, 236, 255), r=0.05)
    p.rect(0.44, 0.44, 0.88, 0.62, INK, r=0.06)
    p.rect(0.46, 0.46, 0.86, 0.6, (92, 150, 190, 255), r=0.05)
    p.rect(0.2, 0.4, 0.4, 0.52, INK, r=0.05)
    p.rect(0.22, 0.42, 0.38, 0.5, CREAM_HI, r=0.04)
    p.save("icon_kasur")


if __name__ == "__main__":
    for n, spec in FISH.items():
        fish(n, *spec)
    udang()
    rod()
    bag_badge()
    bed()
    print("ok")

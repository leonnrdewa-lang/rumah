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

# species: body colour, belly colour, fin colour, shape (length, height), extras, rarity
# extras (comma separated): stripes, whiskers, spots, scales, bars, tiny, flat, long,
# sail, knife, tie, crown, glossy, eye3, spiny, sparkle (SSR)
FISH = {
    # --- N
    "ikan_nila": ((122, 128, 118, 255), (214, 206, 186, 255), (196, 92, 70, 255), (0.62, 0.34), "stripes", "N", "Ikan Nila"),
    "ikan_lele": ((92, 84, 78, 255), (190, 178, 160, 255), (70, 62, 58, 255), (0.74, 0.2), "whiskers", "N", "Ikan Lele"),
    "ikan_mujair": ((96, 110, 96, 255), (200, 196, 170, 255), (80, 90, 110, 255), (0.6, 0.36), "bars", "N", "Ikan Mujair"),
    "ikan_sepat": ((150, 150, 110, 255), (224, 220, 184, 255), (120, 140, 100, 255), (0.5, 0.3), "spots,flat", "N", "Ikan Sepat"),
    "ikan_bawal": ((168, 168, 176, 255), (230, 228, 232, 255), (60, 60, 70, 255), (0.54, 0.44), "", "N", "Ikan Bawal"),
    "ikan_kembung": ((70, 120, 150, 255), (224, 230, 232, 255), (200, 190, 120, 255), (0.66, 0.26), "stripes_h", "N", "Ikan Kembung"),
    "ikan_tongkol": ((50, 70, 110, 255), (220, 226, 232, 255), (60, 80, 120, 255), (0.68, 0.32), "stripes_h,spiny", "N", "Ikan Tongkol"),
    "ikan_teri": ((190, 200, 204, 255), (240, 242, 244, 255), (160, 176, 184, 255), (0.44, 0.14), "tiny", "N", "Ikan Teri"),
    # --- R
    "ikan_patin": ((150, 162, 172, 255), (236, 236, 232, 255), (120, 130, 140, 255), (0.72, 0.26), "whiskers_s", "R", "Ikan Patin"),
    "ikan_gabus": ((96, 104, 70, 255), (206, 196, 150, 255), (80, 86, 58, 255), (0.74, 0.22), "spots", "R", "Ikan Gabus"),
    "ikan_baung": ((132, 110, 90, 255), (220, 206, 184, 255), (110, 92, 76, 255), (0.72, 0.24), "whiskers,spiny", "R", "Ikan Baung"),
    "ikan_kakap": ((214, 96, 70, 255), (246, 196, 170, 255), (190, 70, 50, 255), (0.64, 0.34), "", "R", "Kakap Merah"),
    "ikan_baronang": ((150, 140, 90, 255), (230, 220, 180, 255), (120, 110, 70, 255), (0.56, 0.4), "spots_w,spiny", "R", "Ikan Baronang"),
    # --- SR
    "ikan_toman": ((70, 80, 60, 255), (220, 120, 90, 255), (200, 80, 60, 255), (0.8, 0.24), "bars_r", "SR", "Ikan Toman"),
    "ikan_belida": ((180, 186, 196, 255), (240, 240, 244, 255), (150, 156, 170, 255), (0.8, 0.34), "knife", "SR", "Ikan Belida"),
    "lele_sawit": ((150, 110, 30, 255), (240, 200, 90, 255), (120, 80, 20, 255), (0.8, 0.28), "whiskers,glossy,eye3", "SR", "Lele Sawit"),
    "ikan_kerapu": ((170, 120, 80, 255), (230, 200, 160, 255), (140, 90, 60, 255), (0.64, 0.38), "spots,bars", "SR", "Kerapu Macan"),
    # --- SSR
    "ikan_arwana": ((226, 172, 60, 255), (250, 226, 150, 255), (214, 110, 40, 255), (0.76, 0.26), "scales,sparkle", "SSR", "Arwana Emas"),
    "ikan_berdasi": ((236, 150, 40, 255), (252, 220, 140, 255), (230, 110, 30, 255), (0.62, 0.38), "scales,tie,crown,sparkle", "SSR", "Mas Berdasi"),
}
RARITY_COL = {"N": (138, 138, 138, 255), "R": (58, 116, 192, 255), "SR": (138, 74, 192, 255), "SSR": (224, 168, 32, 255)}


def sparkle(p, x, y, r, col=(255, 252, 235, 255)):
    """a four-pointed star glint (gold edge, white core)"""
    if col != (214, 150, 20, 255):
        sparkle(p, x, y, r * 1.35, (214, 150, 20, 255))
    p.poly([(x, y - r), (x + r * 0.25, y - r * 0.25), (x + r, y), (x + r * 0.25, y + r * 0.25),
            (x, y + r), (x - r * 0.25, y + r * 0.25), (x - r, y), (x - r * 0.25, y - r * 0.25)], col)


def fish(name, body, belly, fin, dims, extra, rar="N", label="", px=128, save=True):
    p = Pad(px)
    exs = set(extra.split(",")) if extra else set()
    L, Hh = dims
    cx, cy = 0.47 - max(0.0, L - 0.64) * 0.6, 0.52
    x0, x1 = cx - L / 2, cx + L / 2
    tilt = -0.18
    if "sparkle" in exs:
        # SSR: a soft golden halo behind the fish
        for i, a in enumerate((60, 90, 130)):
            rr = 0.46 - i * 0.07
            p.circle(0.5, 0.5, rr, (255, 226, 120, a))

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
    if "stripes" in exs:
        for i in range(4):
            x = cx - L * 0.12 + i * L * 0.12
            p.line([R(x, cy - Hh * 0.35), R(x - 0.02, cy + Hh * 0.25)], shade(body, 0.72), 0.022)
    if "stripes_h" in exs:
        for j in range(3):
            y = cy - Hh * 0.28 + j * Hh * 0.1
            p.line([R(cx - L * 0.25, y), R(cx + L * 0.3, y + 0.01)], shade(body, 0.7), 0.014)
    if "bars" in exs or "bars_r" in exs:
        c = (200, 70, 50, 255) if "bars_r" in exs else shade(body, 0.66)
        for i in range(5):
            x = cx - L * 0.22 + i * L * 0.11
            p.line([R(x, cy - Hh * 0.38), R(x + 0.01, cy + Hh * 0.15)], c, 0.03)
    if "spots" in exs:
        for i in range(5):
            x = cx - L * 0.2 + i * L * 0.13
            p.circle(*R(x, cy - Hh * 0.08 * (i % 2)), 0.022, shade(body, 0.62))
    if "spots_w" in exs:
        for i in range(6):
            x = cx - L * 0.22 + i * L * 0.09
            p.circle(*R(x, cy - Hh * 0.18 + (i % 2) * Hh * 0.2), 0.016, (246, 240, 220, 255))
    if "scales" in exs:
        for i in range(4):
            for j in range(2):
                x = cx - L * 0.18 + i * L * 0.12
                y = cy - Hh * 0.14 + j * Hh * 0.26
                p.circle(*R(x, y), 0.03, None, outline=shade(body, 0.8), width=0.012)
    if "whiskers" in exs or "whiskers_s" in exs:
        n = 1 if "whiskers_s" in exs else 2
        for a in (-1, 1)[:n] if n == 1 else (-1, 1):
            p.line([R(x0 + 0.03, cy + 0.02), R(x0 - 0.08, cy + 0.02 + a * 0.08 + 0.05)], INK, 0.014)
    if "knife" in exs:
        # belida: a long rippled anal fin along the belly and a hump
        for i in range(8):
            x = cx - L * 0.2 + i * L * 0.07
            p.circle(*R(x, cy + Hh * 0.46), 0.02, shade(fin, 0.95))
        for i in range(4):
            p.circle(*R(cx - L * 0.05 + i * L * 0.08, cy - Hh * 0.05), 0.014, shade(body, 0.7))
    if "glossy" in exs:
        # an oily rainbow sheen
        p.line([R(cx - L * 0.25, cy - Hh * 0.22), R(cx + L * 0.2, cy - Hh * 0.18)], (140, 220, 200, 200), 0.02)
        p.line([R(cx - L * 0.2, cy - Hh * 0.12), R(cx + L * 0.15, cy - Hh * 0.08)], (230, 140, 220, 180), 0.014)
    if "spiny" in exs:
        for i in range(4):
            x = cx + L * 0.1 + i * L * 0.06
            p.line([R(x, cy - Hh * 0.38), R(x + 0.01, cy - Hh * 0.6)], INK, 0.012)
    # pectoral fin, gill line, eye
    p.poly([R(x, y) for x, y in [(cx - L * 0.2, cy + 0.02), (cx - L * 0.05, cy + Hh * 0.28), (cx - L * 0.02, cy + 0.03)]], shade(fin, 0.9))
    p.line([R(x0 + L * 0.22, cy - Hh * 0.3), R(x0 + L * 0.2, cy + Hh * 0.25)], shade(body, 0.7), 0.016)
    ex, ey = R(x0 + L * 0.1, cy - Hh * 0.08)
    p.circle(ex, ey, 0.045, (250, 246, 236, 255))
    p.circle(ex + 0.006, ey, 0.026, INK)
    p.circle(ex - 0.006, ey - 0.012, 0.009, (255, 255, 255, 255))
    if "eye3" in exs:
        e3x, e3y = R(x0 + L * 0.16, cy - Hh * 0.3)
        p.circle(e3x, e3y, 0.03, INK)
        p.circle(e3x, e3y, 0.02, (200, 240, 90, 255))
        p.circle(e3x + 0.004, e3y, 0.01, INK)
    if "tie" in exs:
        # a red necktie under the gills and a white collar
        tx, ty = R(x0 + L * 0.24, cy + Hh * 0.18)
        p.poly([(tx - 0.05, ty - 0.03), (tx + 0.05, ty - 0.03), (tx, ty + 0.01)], (250, 246, 236, 255))
        p.poly([(tx - 0.022, ty - 0.005), (tx + 0.022, ty - 0.005), (tx + 0.03, ty + 0.13), (tx, ty + 0.17), (tx - 0.03, ty + 0.13)], INK)
        p.poly([(tx - 0.014, ty + 0.002), (tx + 0.014, ty + 0.002), (tx + 0.02, ty + 0.125), (tx, ty + 0.155), (tx - 0.02, ty + 0.125)], (200, 40, 40, 255))
    if "crown" in exs:
        # a black peci on the head
        hx_, hy_ = R(x0 + L * 0.16, cy - Hh * 0.46)
        p.rect(hx_ - 0.07, hy_ - 0.07, hx_ + 0.07, hy_ + 0.01, INK, r=0.02)
        p.rect(hx_ - 0.06, hy_ - 0.06, hx_ + 0.06, hy_, (40, 40, 48, 255), r=0.015)
    if "sparkle" in exs:
        sparkle(p, 0.2, 0.2, 0.07)
        sparkle(p, 0.84, 0.3, 0.05)
        sparkle(p, 0.72, 0.84, 0.06)
    if save:
        p.save(name)
    return p


def udang(px=128, save=True):
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
    if save:
        p.save("udang_galah")
    return p


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


def fish_sheet():
    """all species in a 5x4 grid with names and rarity -> game/assets/ui/fish_sheet.png"""
    from PIL import Image, ImageDraw, ImageFont
    cw, ch = 220, 230
    specs = dict(FISH)
    specs["udang_galah"] = (None, None, None, None, "", "R", "Udang Galah")
    keys = list(FISH.keys())
    keys.insert(keys.index("ikan_kakap"), "udang_galah")
    order = sorted(keys, key=lambda k: ("N", "R", "SR", "SSR").index(specs[k][5]))
    W, H = cw * 5, ch * 4
    im = Image.new("RGBA", (W, H), (252, 242, 221, 255))
    d = ImageDraw.Draw(im)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font = None
    for fp in [os.path.join(root, "game", "assets", "fonts", f) for f in os.listdir(os.path.join(root, "game", "assets", "fonts"))
               if f.lower().endswith((".ttf", ".otf"))] if os.path.isdir(os.path.join(root, "game", "assets", "fonts")) else []:
        try:
            font = ImageFont.truetype(fp, 22)
            fsmall = ImageFont.truetype(fp, 18)
            break
        except OSError:
            pass
    if font is None:
        font = fsmall = ImageFont.load_default()
    for i, k in enumerate(order):
        body, belly, fin, dims, extra, rar, label = specs[k]
        cx, cy = (i % 5) * cw, (i // 5) * ch
        rc = RARITY_COL[rar]
        d.rounded_rectangle([cx + 8, cy + 8, cx + cw - 8, cy + ch - 8], radius=22, fill=(255, 250, 238, 255),
                            outline=rc if rar != "N" else (216, 194, 154, 255), width=5 if rar != "N" else 3)
        p = udang(176, False) if k == "udang_galah" else fish(k, body, belly, fin, dims, extra, rar, label, px=176, save=False)
        small = p.im.convert("RGBa").resize((176, 176), Image.LANCZOS).convert("RGBA")
        im.alpha_composite(small, (cx + (cw - 176) // 2, cy + 18))
        # rarity badge
        tw = d.textlength(rar, font=fsmall)
        d.rounded_rectangle([cx + 16, cy + 16, cx + 16 + tw + 16, cy + 44], radius=10, fill=rc)
        d.text((cx + 24, cy + 18), rar, fill=(255, 255, 255, 255), font=fsmall)
        nw = d.textlength(label, font=font)
        d.text((cx + (cw - nw) / 2, cy + ch - 46), label, fill=(74, 47, 29, 255), font=font)
    out = os.path.join(root, "game", "assets", "ui")
    os.makedirs(out, exist_ok=True)
    im.save(os.path.join(out, "fish_sheet.png"))
    print("wrote fish_sheet")


if __name__ == "__main__":
    for n, spec in FISH.items():
        fish(n, *spec)
    udang()
    rod()
    bag_badge()
    bed()
    fish_sheet()
    print("ok")

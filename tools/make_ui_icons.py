"""Flat UI glyphs for the HUD (coin stack, sun, leaf, eye, energy bolt, quest,
menu, status, toast badges, phone) and the app icon, drawn with Pillow.

Everything is drawn 8x supersampled and downscaled with premultiplied alpha,
so edges stay crisp and free of dark fringes.

python3 tools/make_ui_icons.py
"""
import math
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "icons")
os.makedirs(OUT, exist_ok=True)
S = 8  # supersampling

CREAM = (252, 242, 221, 255)
CREAM_HI = (255, 250, 238, 255)
RING = (122, 84, 52, 255)
BROWN = (74, 47, 29, 255)


class Pad:
    """Drawing helper working in unit coordinates (0..1) on a supersampled canvas."""

    def __init__(self, px):
        self.px = px
        self.k = px * S
        self.im = Image.new("RGBA", (self.k, self.k), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, x, y):
        return (x * self.k, y * self.k)

    def circle(self, cx, cy, r, fill, outline=None, width=0.0):
        k = self.k
        self.d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=fill,
                       outline=outline, width=int(width * k) if outline else 0)

    def ellipse(self, x0, y0, x1, y1, fill, outline=None, width=0.0):
        k = self.k
        self.d.ellipse([x0 * k, y0 * k, x1 * k, y1 * k], fill=fill, outline=outline,
                       width=int(width * k) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill, r=0.0):
        k = self.k
        self.d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=int(r * k), fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([self.P(x, y) for x, y in pts], fill=fill)

    def line(self, pts, fill, w):
        self.d.line([self.P(x, y) for x, y in pts], fill=fill, width=max(1, int(w * self.k)), joint="curve")
        for x, y in (pts[0], pts[-1]):  # round caps
            self.circle(x, y, w / 2, fill)

    def badge(self, fill, ring=None, ring_w=0.055):
        """Round badge background: optional darker ring + soft top highlight."""
        if ring:
            self.circle(0.5, 0.5, 0.49, ring)
            self.circle(0.5, 0.5, 0.49 - ring_w, fill)
        else:
            self.circle(0.5, 0.5, 0.49, fill)

    def save(self, name):
        small = self.im.convert("RGBa").resize((self.px, self.px), Image.LANCZOS).convert("RGBA")
        small.save(os.path.join(OUT, name + ".png"))
        print("wrote", name)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + (c[3] if len(c) > 3 else 255,)


# ------------------------------------------------------------------ HUD glyphs
def coins(px=128):
    p = Pad(px)
    p.badge((190, 132, 74, 255), ring=(132, 86, 48, 255), ring_w=0.05)
    p.circle(0.5, 0.5, 0.39, (205, 146, 86, 255))
    gold, edge, dark = (246, 204, 92, 255), (214, 158, 52, 255), (170, 112, 36, 255)
    # two stacks of coins seen slightly from above
    for cx, n, base in ((0.39, 4, 0.72), (0.63, 3, 0.74)):
        w, h, step = 0.19, 0.075, 0.075
        for i in range(n):
            y = base - i * step
            p.ellipse(cx - w, y - h + 0.03, cx + w, y + h + 0.03, dark)
            p.rect(cx - w, y, cx + w, y + 0.03, edge)
            p.ellipse(cx - w, y - h, cx + w, y + h, gold)
        ytop = base - (n - 1) * step
        p.ellipse(cx - w * 0.62, ytop - h * 0.62, cx + w * 0.62, ytop + h * 0.62, (255, 226, 130, 255))
        p.ellipse(cx - w * 0.35, ytop - h * 0.35, cx + w * 0.35, ytop + h * 0.35, gold)
    # a leaning coin with an "Rp"-ish mark
    p.circle(0.66, 0.36, 0.14, dark)
    p.circle(0.655, 0.35, 0.13, gold)
    p.circle(0.655, 0.35, 0.085, (255, 222, 120, 255))
    p.rect(0.64, 0.30, 0.67, 0.40, edge, r=0.01)
    p.save("ui_coins")


def sun(px=128):
    p = Pad(px)
    c = 0.5
    ray = (245, 160, 48, 255)
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        r1, r2, w = 0.30, 0.48, 0.085
        pts = [(c + math.cos(a) * r1 - math.sin(a) * w, c + math.sin(a) * r1 + math.cos(a) * w),
               (c + math.cos(a) * r2, c + math.sin(a) * r2),
               (c + math.cos(a) * r1 + math.sin(a) * w, c + math.sin(a) * r1 - math.cos(a) * w)]
        p.poly(pts, ray)
        p.circle(c + math.cos(a) * (r2 - 0.03), c + math.sin(a) * (r2 - 0.03), 0.03, ray)
    p.circle(c, c, 0.30, (236, 134, 40, 255))
    p.circle(c, c, 0.27, (252, 190, 60, 255))
    p.circle(c - 0.05, c - 0.06, 0.16, (255, 214, 102, 255))
    p.circle(c - 0.09, c - 0.10, 0.05, (255, 240, 190, 255))
    p.save("ui_sun")


def leaf(px=128):
    p = Pad(px)
    p.badge(CREAM, ring=RING, ring_w=0.07)
    # leaf: two arcs meeting at the tips, tilted 45 degrees
    cx, cy, L, W = 0.5, 0.5, 0.34, 0.19
    ang = -math.pi / 4

    def rot(x, y):
        return (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))

    outline, pts = [], []
    for i in range(41):
        t = -1 + 2 * i / 40
        pts.append(rot(t * L, -W * (1 - t * t) ** 0.8))
    for i in range(41):
        t = 1 - 2 * i / 40
        pts.append(rot(t * L, W * (1 - t * t) ** 0.8))
    p.poly(pts, (58, 128, 58, 255))
    inner = [(cx + (x - cx) * 0.86, cy + (y - cy) * 0.86) for x, y in pts]
    p.poly(inner, (86, 168, 76, 255))
    half = pts[:41] + [rot(-L * 0.86, 0)]
    p.poly([(cx + (x - cx) * 0.84, cy + (y - cy) * 0.84) for x, y in half], (112, 190, 90, 255))
    p.line([rot(-L * 1.25, 0), rot(L * 0.8, 0)], (44, 104, 48, 255), 0.03)
    for s in (-0.45, -0.1, 0.25):
        p.line([rot(s * L, 0), rot((s + 0.3) * L, -W * 0.62)], (60, 130, 58, 255), 0.018)
        p.line([rot(s * L, 0), rot((s + 0.3) * L, W * 0.62)], (60, 130, 58, 255), 0.018)
    p.save("ui_leaf")


def eye(px=128):
    p = Pad(px)
    p.badge(CREAM, ring=RING, ring_w=0.07)
    cx, cy = 0.5, 0.52
    top, bot = [], []
    for i in range(41):
        t = -1 + 2 * i / 40
        x = cx + t * 0.31
        top.append((x, cy - 0.19 * (1 - t * t)))
        bot.append((x, cy + 0.15 * (1 - t * t)))
    lid = (96, 60, 34, 255)
    p.poly(top + bot[::-1], lid)
    p.poly([(cx + (x - cx) * 0.9, cy + (y - cy) * 0.78) for x, y in top + bot[::-1]], (255, 250, 238, 255))
    p.circle(cx, cy, 0.125, (150, 96, 50, 255))
    p.circle(cx, cy, 0.09, (112, 70, 36, 255))
    p.circle(cx, cy, 0.055, (40, 24, 16, 255))
    p.circle(cx - 0.04, cy - 0.045, 0.028, (255, 255, 255, 255))
    # upper lid line + lashes
    p.line(top, lid, 0.04)
    for t in (-0.55, 0.0, 0.55):
        x = cx + t * 0.31
        y = cy - 0.19 * (1 - t * t)
        p.line([(x, y), (x + t * 0.05, y - 0.07)], lid, 0.03)
    p.save("ui_eye")


def bolt(px=128):
    p = Pad(px)
    p.badge((248, 190, 70, 255), ring=(214, 140, 40, 255))
    p.circle(0.46, 0.42, 0.3, (252, 206, 96, 255))
    pts = [(0.56, 0.14), (0.28, 0.56), (0.47, 0.56), (0.40, 0.87), (0.73, 0.43), (0.53, 0.43), (0.62, 0.14)]
    p.poly([(x + 0.012, y + 0.02) for x, y in pts], (196, 118, 30, 255))
    p.poly(pts, CREAM_HI)
    p.save("ui_energy")


def quest(px=128):
    p = Pad(px)
    p.badge((111, 158, 62, 255), ring=(76, 118, 44, 255))
    # rolled scroll with an exclamation mark
    p.rect(0.3, 0.26, 0.7, 0.74, CREAM_HI, r=0.05)
    p.rect(0.26, 0.22, 0.74, 0.31, (232, 214, 176, 255), r=0.045)
    p.rect(0.26, 0.69, 0.74, 0.78, (232, 214, 176, 255), r=0.045)
    p.rect(0.465, 0.36, 0.535, 0.56, (201, 86, 60, 255), r=0.03)
    p.circle(0.5, 0.63, 0.04, (201, 86, 60, 255))
    p.save("ui_quest")


def menu_icon(px=128):
    p = Pad(px)
    p.badge((138, 96, 60, 255), ring=(98, 64, 38, 255))
    for y in (0.35, 0.5, 0.65):
        p.rect(0.29, y - 0.045, 0.71, y + 0.045, CREAM_HI, r=0.045)
    p.save("ui_menu")


def status_icon(px=128):
    p = Pad(px)
    p.badge((138, 96, 60, 255), ring=(98, 64, 38, 255))
    # clipboard with bars
    p.rect(0.3, 0.24, 0.7, 0.78, CREAM_HI, r=0.05)
    p.rect(0.4, 0.19, 0.6, 0.29, (214, 190, 146, 255), r=0.03)
    for i, (h, c) in enumerate(((0.16, (111, 158, 62, 255)), (0.26, (233, 185, 73, 255)), (0.1, (201, 86, 60, 255)))):
        x = 0.37 + i * 0.1
        p.rect(x, 0.7 - h, x + 0.07, 0.7, c, r=0.015)
    p.save("ui_status")


def toast_badges(px=96):
    p = Pad(px)  # good: check mark
    p.badge((111, 158, 62, 255), ring=(76, 118, 44, 255))
    p.line([(0.3, 0.52), (0.44, 0.66), (0.71, 0.36)], CREAM_HI, 0.1)
    p.save("ui_good")
    p = Pad(px)  # bad: exclamation
    p.badge((214, 90, 64, 255), ring=(160, 60, 40, 255))
    p.rect(0.445, 0.22, 0.555, 0.6, CREAM_HI, r=0.05)
    p.circle(0.5, 0.72, 0.065, CREAM_HI)
    p.save("ui_bad")
    p = Pad(px)  # info: i
    p.badge((138, 96, 60, 255), ring=(98, 64, 38, 255))
    p.circle(0.5, 0.29, 0.065, CREAM_HI)
    p.rect(0.445, 0.41, 0.555, 0.77, CREAM_HI, r=0.05)
    p.save("ui_info")
    p = Pad(px)  # quest done: star
    p.badge((240, 176, 56, 255), ring=(200, 130, 36, 255))
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 0.3 if i % 2 == 0 else 0.13
        pts.append((0.5 + math.cos(a) * r, 0.53 + math.sin(a) * r))
    p.poly(pts, CREAM_HI)
    p.save("ui_star")


def tap(px=96):
    """Touch-screen twin of the "E" key badge in the action prompt: a finger
    tapping (the round action button does what E does on a keyboard)."""
    p = Pad(px)
    ink = (62, 38, 23, 255)
    p.circle(0.5, 0.5, 0.49, ink)
    hand = CREAM_HI
    # tap ripples above the fingertip
    for r, w in ((0.13, 0.045), (0.215, 0.04)):
        p.d.arc([(0.5 - r) * p.k, (0.3 - r) * p.k, (0.5 + r) * p.k, (0.3 + r) * p.k], 208, 332,
                fill=(233, 185, 73, 255), width=int(w * p.k))
    # index finger pointing up, a fist below it and the thumb on the left
    p.rect(0.445, 0.27, 0.575, 0.64, hand, r=0.065)
    p.rect(0.4, 0.5, 0.71, 0.82, hand, r=0.11)
    p.circle(0.625, 0.53, 0.07, hand)
    p.circle(0.69, 0.585, 0.058, hand)
    p.poly([(0.29, 0.56), (0.35, 0.52), (0.46, 0.66), (0.42, 0.75)], hand)
    p.circle(0.32, 0.545, 0.045, hand)
    # knuckle creases
    p.line([(0.585, 0.585), (0.585, 0.64)], ink, 0.022)
    p.line([(0.655, 0.625), (0.655, 0.67)], ink, 0.022)
    p.save("ui_tap")


def phone(px=256):
    """Fallback portrait for the franchise HQ calling on the phone."""
    p = Pad(px)
    p.badge((233, 139, 58, 255), ring=(190, 96, 40, 255), ring_w=0.035)
    p.circle(0.5, 0.5, 0.4, (242, 160, 74, 255))
    # handset
    arc = [(0.5 + math.cos(a) * 0.25, 0.5 + math.sin(a) * 0.25)
           for a in [math.radians(d) for d in range(125, 236, 5)]]
    arc = [(x + 0.02, y) for x, y in arc]
    p.line(arc, BROWN, 0.15)
    for x, y in (arc[0], arc[-1]):  # fat ear and mouth pieces
        p.circle(x, y, 0.1, BROWN)
    # ringing waves
    for r in (0.12, 0.2):
        p.d.arc([(0.62 - r) * p.k, (0.36 - r) * p.k, (0.62 + r) * p.k, (0.36 + r) * p.k], 250, 20,
                fill=CREAM_HI, width=int(0.035 * p.k))
    p.save("ui_phone")


def app_icon(px=256):
    p = Pad(px)
    k = 1.0
    p.rect(0, 0, 1, 1, CREAM, r=0.22)
    p.ellipse(0.14, 0.6, 0.86, 0.9, (109, 145, 72, 255))
    p.rect(0.45, 0.36, 0.56, 0.76, (107, 90, 62, 255), r=0.03)
    for i in range(9):
        a = math.pi + i * math.pi / 8
        x2 = 0.5 + math.cos(a) * 0.36 * k
        y2 = 0.36 + math.sin(a) * 0.2 + 0.08 * abs(math.cos(a))
        p.line([(0.5, 0.36), (x2, y2)], (79, 138, 42, 255), 0.07)
    for x, y in [(0.44, 0.42), (0.56, 0.43), (0.5, 0.47)]:
        p.circle(x, y, 0.05, (201, 64, 31, 255))
    p.save("app_icon")


if __name__ == "__main__":
    coins()
    sun()
    leaf()
    eye()
    bolt()
    quest()
    menu_icon()
    status_icon()
    toast_badges()
    tap()
    phone()
    if "--app-icon" in sys.argv:  # app_icon.png is shared with the web build; only on request
        app_icon()
    print("ok")

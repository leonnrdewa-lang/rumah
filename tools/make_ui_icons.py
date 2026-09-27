"""Small flat UI glyphs (sun, energy bolt) and the app icon, drawn with Pillow.

python3 tools/make_ui_icons.py
"""
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "icons")
os.makedirs(OUT, exist_ok=True)
S = 4  # supersampling


def canvas(px):
    im = Image.new("RGBA", (px * S, px * S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def save(im, name, px):
    im.resize((px, px), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))


def sun(px=64):
    im, d = canvas(px)
    c = px * S / 2
    d.ellipse([0, 0, px * S - 1, px * S - 1], fill=(233, 160, 64, 255))
    r1, r2 = px * S * 0.30, px * S * 0.42
    for i in range(8):
        a = i * math.pi / 4
        w = px * S * 0.07
        p = [(c + math.cos(a) * r1 - math.sin(a) * w, c + math.sin(a) * r1 + math.cos(a) * w),
             (c + math.cos(a) * r2, c + math.sin(a) * r2),
             (c + math.cos(a) * r1 + math.sin(a) * w, c + math.sin(a) * r1 - math.cos(a) * w)]
        d.polygon(p, fill=(253, 243, 220, 255))
    rr = px * S * 0.2
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(253, 243, 220, 255))
    save(im, "ui_sun", px)


def bolt(px=64):
    im, d = canvas(px)
    d.ellipse([0, 0, px * S - 1, px * S - 1], fill=(214, 154, 44, 255))
    k = px * S
    pts = [(0.56, 0.14), (0.28, 0.56), (0.48, 0.56), (0.40, 0.88), (0.74, 0.42), (0.53, 0.42), (0.62, 0.14)]
    d.polygon([(x * k, y * k) for x, y in pts], fill=(253, 243, 220, 255))
    save(im, "ui_energy", px)


def app_icon(px=256):
    im, d = canvas(px)
    k = px * S
    d.rounded_rectangle([0, 0, k - 1, k - 1], radius=int(k * 0.22), fill=(253, 243, 220, 255))
    d.ellipse([k * 0.14, k * 0.6, k * 0.86, k * 0.9], fill=(109, 145, 72, 255))
    # trunk
    d.rounded_rectangle([k * 0.45, k * 0.36, k * 0.56, k * 0.76], radius=int(k * 0.03), fill=(107, 90, 62, 255))
    # fronds
    for i in range(9):
        a = math.pi + i * math.pi / 8
        x2 = k * 0.5 + math.cos(a) * k * 0.36
        y2 = k * 0.36 + math.sin(a) * k * 0.2 + k * 0.08 * abs(math.cos(a))
        d.line([(k * 0.5, k * 0.36), (x2, y2)], fill=(79, 138, 42, 255), width=int(k * 0.07))
    for i, (x, y) in enumerate([(0.44, 0.42), (0.56, 0.43), (0.5, 0.47)]):
        r = k * 0.05
        d.ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill=(201, 64, 31, 255))
    save(im, "app_icon", px)


sun()
bolt()
app_icon()
print("ok")

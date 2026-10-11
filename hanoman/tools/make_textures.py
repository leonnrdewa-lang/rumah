#!/usr/bin/env python3
"""Paint the tiling floor textures, shader noise, UI frames and icons for Hanoman Duta.

Everything is procedural (numpy + Pillow), tileable where it needs to be, and written
to hanoman/game/assets/{textures,icons}. Run:  python3 hanoman/tools/make_textures.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "game", "assets", "textures")
ICO = os.path.join(ROOT, "game", "assets", "icons")
os.makedirs(TEX, exist_ok=True)
os.makedirs(ICO, exist_ok=True)
rng = np.random.default_rng(7)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def fft_noise(n, scale, aniso=(1.0, 1.0), seed=None):
    """Tileable noise: white noise low-passed in the frequency domain, 0..1."""
    r = np.random.default_rng(seed) if seed is not None else rng
    w = r.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None] * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    filt = np.exp(-(f * scale) ** 2)
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * filt))
    out -= out.min()
    return out / max(out.max(), 1e-9)


def save_rgb(arr, name, folder=TEX):
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(os.path.join(folder, name), optimize=True)


def shared_noise():
    n = 256
    a = fft_noise(n, 18, seed=1) * 0.6 + fft_noise(n, 5, seed=2) * 0.4
    save_rgb(np.dstack([a] * 3), "noise.png")
    # brush: elongated strokes at two angles
    s1 = fft_noise(n, 30, aniso=(0.25, 1.0), seed=3)
    s2 = fft_noise(n, 30, aniso=(1.0, 0.3), seed=4)
    b = np.clip((s1 * 0.6 + s2 * 0.4 - 0.5) * 2.2 + 0.5, 0, 1)
    save_rgb(np.dstack([b] * 3), "brush.png")


def kawung(img_a, cx, cy, r, strength):
    """Carve a kawung motif (four petals around a centre) as a height offset."""
    n = img_a.shape[0]
    yy, xx = np.mgrid[0:n, 0:n]
    for k in range(4):
        ang = k * math.pi / 2 + math.pi / 4
        px, py = cx + math.cos(ang) * r * 0.55, cy + math.sin(ang) * r * 0.55
        dx = (xx - px + n / 2) % n - n / 2
        dy = (yy - py + n / 2) % n - n / 2
        u = dx * math.cos(ang) + dy * math.sin(ang)
        v = -dx * math.sin(ang) + dy * math.cos(ang)
        e = (u / (r * 0.5)) ** 2 + (v / (r * 0.27)) ** 2
        ring = np.exp(-((e - 1.0) / 0.18) ** 2)
        img_a -= ring * strength
    dx = (xx - cx + n / 2) % n - n / 2
    dy = (yy - cy + n / 2) % n - n / 2
    dd = np.sqrt(dx * dx + dy * dy)
    img_a -= np.exp(-((dd - r * 0.12) / 2.2) ** 2) * strength
    return img_a


def shade_height(h, light=(-0.6, -0.8), k=6.0):
    gy, gx = np.gradient(h)
    return np.clip(0.5 + (gx * light[0] + gy * light[1]) * k, 0, 1)


def floor_dandaka():
    n = 1024
    base = np.zeros((n, n, 3))
    height = np.zeros((n, n))
    rows = 6
    rh = n // rows
    stone_a, stone_b = hexc("#3b4541"), hexc("#5b6459")
    moss_c, moss_d = hexc("#2f5a42"), hexc("#20402f")
    for r in range(rows):
        y0 = r * rh
        x = int(rng.integers(0, 160))
        while x < n + 200:
            w = int(rng.integers(140, 260))
            col = stone_a + (stone_b - stone_a) * rng.random() + rng.normal(0, 0.02, 3)
            col += np.array([0.0, 0.02, 0.01]) * rng.random()
            xs = np.arange(x, x + w) % n
            base[y0:y0 + rh][:, xs] = col
            # gap mask
            height[y0:y0 + rh][:, xs] = 1.0
            height[y0:y0 + 6, :][:, xs] = 0.0
            for xg in (xs[:6]):
                height[y0:y0 + rh, xg] = 0.0
            if rng.random() < 0.3:
                kawung(height, (x + w / 2) % n, y0 + rh / 2, min(w, rh) * 0.8, 0.35)
            x += w
    height = np.array(Image.fromarray((height * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2))) / 255.0
    sh = shade_height(height, k=5.0)
    n1 = fft_noise(n, 60, seed=11)
    n2 = fft_noise(n, 14, seed=12)
    strokes = fft_noise(n, 40, aniso=(0.2, 1.0), seed=13)
    c = base * (0.75 + 0.5 * sh[..., None])
    c *= (0.85 + 0.3 * n2[..., None])
    c *= (0.9 + 0.2 * strokes[..., None])
    gap = 1.0 - np.clip(height * 3.0, 0, 1)
    c = c * (1 - gap[..., None] * 0.85)
    moss = np.clip((n1 - 0.55) * 4.0, 0, 1) * (0.4 + 0.6 * gap)
    moss = np.maximum(moss, gap * np.clip((n2 - 0.4) * 3, 0, 1))
    mc = moss_c * (1 - n2[..., None] * 0.5) + moss_d * n2[..., None] * 0.5
    c = c * (1 - moss[..., None] * 0.8) + mc * moss[..., None] * 0.8
    save_rgb(c, "floor_dandaka.png")


def floor_muara():
    n = 1024
    planks = 10
    ph = n / planks
    c = np.zeros((n, n, 3))
    grain = fft_noise(n, 90, aniso=(0.03, 1.0), seed=21)
    knots = fft_noise(n, 10, seed=22)
    yy, xx = np.mgrid[0:n, 0:n]
    wood_a, wood_b = hexc("#4a3b2e"), hexc("#6b5642")
    for p in range(planks):
        y0, y1 = int(p * ph), int((p + 1) * ph)
        tone = wood_a + (wood_b - wood_a) * rng.random()
        off = int(rng.integers(0, n))
        c[y0:y1] = tone
        seam = off % n
        c[y0:y1, max(0, seam - 3):seam + 3] *= 0.35
        c[y0:y0 + 5] *= 0.3
        for nx in (seam + 18, seam - 18):
            for ny in (y0 + ph * 0.3, y0 + ph * 0.7):
                d = np.hypot(xx - nx % n, yy - ny)
                c[d < 4] = hexc("#2a2622")
    c *= (0.72 + 0.5 * grain[..., None])
    c *= (0.9 + 0.2 * knots[..., None])
    wet = np.clip((fft_noise(n, 50, seed=23) - 0.55) * 3, 0, 1)
    c = c * (1 - wet[..., None] * 0.35) + hexc("#1c3a3c") * wet[..., None] * 0.25
    save_rgb(c, "floor_muara.png")


def floor_hub():
    n = 1024
    c = np.zeros((n, n, 3))
    h = np.zeros((n, n))
    bw, bh = 128, 64
    brick_a, brick_b = hexc("#4e3430"), hexc("#6e4636")
    for by in range(0, n, bh):
        shift = (by // bh % 2) * bw // 2
        for bx in range(-bw, n, bw):
            x0 = (bx + shift)
            col = brick_a + (brick_b - brick_a) * rng.random()
            xs = np.arange(x0 + 4, x0 + bw - 4) % n
            c[by + 4:by + bh - 4][:, xs] = col
            h[by + 4:by + bh - 4][:, xs] = 1
    h = np.array(Image.fromarray((h * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0))) / 255.0
    sh = shade_height(h, k=4)
    n2 = fft_noise(n, 16, seed=31)
    mortar = hexc("#2a2320")
    c = c * (0.8 + 0.4 * sh[..., None]) * (0.85 + 0.3 * n2[..., None])
    c = c * h[..., None] + mortar * (1 - h[..., None])
    moss = np.clip((fft_noise(n, 70, seed=32) - 0.6) * 3, 0, 1) * (1 - h * 0.6)
    c = c * (1 - moss[..., None] * 0.6) + hexc("#2d4a36") * moss[..., None] * 0.6
    save_rgb(c, "floor_hub.png")


# --- icons -----------------------------------------------------------------
S = 512


def canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def finish(img, name, size=128):
    img = img.resize((size, size), Image.LANCZOS)
    img.save(os.path.join(ICO, name + ".png"), optimize=True)


def ink(d, pts, w, fill=None):
    d.line(pts, fill=fill or (20, 14, 18, 255), width=w, joint="curve")


def medallion(color, inner=None):
    img = canvas()
    d = ImageDraw.Draw(img)
    d.ellipse((24, 24, S - 24, S - 24), fill=(20, 14, 18, 255))
    d.ellipse((40, 40, S - 40, S - 40), fill=(217, 169, 58, 255))
    d.ellipse((58, 58, S - 58, S - 58), fill=(20, 14, 18, 255))
    d.ellipse((66, 66, S - 66, S - 66), fill=inner or tuple(int(v * 0.35 * 255) for v in color) + (255,))
    return img, d


def god_icon(name, col, draw_fn):
    c = tuple(int(v * 255) for v in hexc(col))
    img, d = medallion(hexc(col))
    draw_fn(d, c)
    finish(img, "god_" + name)


def sym_bayu(d, c):
    pts = []
    for i in range(80):
        t = i / 79 * 4.2 * math.pi
        r = 20 + t * 11
        pts.append((S / 2 + math.cos(t) * r, S / 2 + math.sin(t) * r * 0.85))
    ink(d, pts, 40)
    ink(d, pts, 24, c + (255,))


def sym_surya(d, c):
    cx = cy = S / 2
    for k in range(12):
        a = k * math.pi / 6
        p = [(cx + math.cos(a - 0.12) * 80, cy + math.sin(a - 0.12) * 80), (cx + math.cos(a) * 170, cy + math.sin(a) * 170),
             (cx + math.cos(a + 0.12) * 80, cy + math.sin(a + 0.12) * 80)]
        d.polygon(p, fill=c + (255,), outline=(20, 14, 18, 255))
    d.ellipse((cx - 85, cy - 85, cx + 85, cy + 85), fill=(20, 14, 18, 255))
    d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill=c + (255,))


def sym_baruna(d, c):
    for row in range(3):
        y = 170 + row * 70
        pts = [(110 + i * 3, y - math.sin(i / 97 * 2 * math.pi * 1.5) * 26) for i in range(98)]
        ink(d, pts, 34)
        ink(d, pts, 20, c + (255,))


def sym_indra(d, c):
    p = [(290, 90), (170, 280), (250, 280), (210, 430), (350, 220), (265, 220), (320, 90)]
    d.polygon(p, fill=c + (255,), outline=(20, 14, 18, 255), width=10)


def reward_icons():
    # kepeng coin
    img = canvas()
    d = ImageDraw.Draw(img)
    d.ellipse((60, 60, S - 60, S - 60), fill=(20, 14, 18, 255))
    d.ellipse((76, 76, S - 76, S - 76), fill=(226, 176, 62, 255))
    d.ellipse((120, 120, S - 120, S - 120), outline=(150, 100, 30, 255), width=10)
    d.rectangle((S / 2 - 50, S / 2 - 50, S / 2 + 50, S / 2 + 50), fill=(20, 14, 18, 255))
    finish(img, "rw_kepeng")
    # tirta (water drop in kendi)
    img = canvas()
    d = ImageDraw.Draw(img)
    d.polygon([(256, 60), (140, 280), (372, 280)], fill=(20, 14, 18, 255))
    d.ellipse((130, 190, 382, 442), fill=(20, 14, 18, 255))
    d.polygon([(256, 90), (158, 280), (354, 280)], fill=(229, 70, 90, 255))
    d.ellipse((148, 208, 364, 424), fill=(229, 70, 90, 255))
    d.ellipse((190, 250, 240, 300), fill=(255, 200, 210, 255))
    finish(img, "rw_tirta")
    # wijayakusuma flower
    img = canvas()
    d = ImageDraw.Draw(img)
    for k in range(8):
        a = k * math.pi / 4
        cx, cy = S / 2 + math.cos(a) * 110, S / 2 + math.sin(a) * 110
        d.ellipse((cx - 80, cy - 80, cx + 80, cy + 80), fill=(20, 14, 18, 255))
    for k in range(8):
        a = k * math.pi / 4
        cx, cy = S / 2 + math.cos(a) * 110, S / 2 + math.sin(a) * 110
        d.ellipse((cx - 66, cy - 66, cx + 66, cy + 66), fill=(245, 240, 230, 255))
    d.ellipse((S / 2 - 60, S / 2 - 60, S / 2 + 60, S / 2 + 60), fill=(240, 200, 90, 255), outline=(20, 14, 18, 255), width=12)
    finish(img, "rw_bunga")
    # pusaka palu (hammer) for boon upgrade
    img = canvas()
    d = ImageDraw.Draw(img)
    d.polygon([(230, 200), (282, 200), (300, 470), (212, 470)], fill=(20, 14, 18, 255))
    d.polygon([(240, 210), (272, 210), (286, 460), (226, 460)], fill=(140, 90, 50, 255))
    d.rounded_rectangle((100, 80, 412, 220), 30, fill=(20, 14, 18, 255))
    d.rounded_rectangle((116, 96, 396, 204), 22, fill=(200, 200, 210, 255))
    finish(img, "rw_palu")
    # app icon: Hanoman mask silhouette in gold on dark
    img = Image.new("RGBA", (S, S), (16, 20, 28, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((96, 120, 416, 460), fill=(244, 241, 234, 255), outline=(217, 169, 58, 255), width=14)
    d.polygon([(110, 170), (256, 40), (402, 170), (256, 120)], fill=(217, 169, 58, 255))
    d.ellipse((170, 250, 230, 300), fill=(20, 14, 18, 255))
    d.ellipse((282, 250, 342, 300), fill=(20, 14, 18, 255))
    d.ellipse((190, 330, 322, 420), fill=(214, 160, 150, 255), outline=(20, 14, 18, 255), width=10)
    finish(img, "app_icon", 192)


def slot_icons():
    specs = {
        "slot_serang": lambda d: (d.rounded_rectangle((226, 90, 286, 420), 20, fill=(217, 169, 58, 255), outline=(20, 14, 18, 255), width=12),
                                  d.ellipse((180, 60, 332, 212), fill=(217, 169, 58, 255), outline=(20, 14, 18, 255), width=12)),
        "slot_jurus": lambda d: [ink(d, [(140 + k * 70, 400), (200 + k * 70, 110)], 34) or ink(d, [(140 + k * 70, 400), (200 + k * 70, 110)], 18, (230, 240, 240, 255)) for k in range(3)],
        "slot_ajian": lambda d: (d.ellipse((80, 80, 432, 432), outline=(20, 14, 18, 255), width=46),
                                 d.ellipse((80, 80, 432, 432), outline=(95, 224, 200, 255), width=26),
                                 d.ellipse((190, 190, 322, 322), outline=(95, 224, 200, 255), width=18)),
        "slot_lesat": lambda d: [ink(d, [(90, 170 + k * 80), (420, 170 + k * 80)], 32) or ink(d, [(90 + k * 40, 170 + k * 80), (420, 170 + k * 80)], 16, (230, 240, 240, 255)) for k in range(3)],
        "slot_pasif": lambda d: (d.regular_polygon((256, 256, 150), 6, fill=(217, 169, 58, 255), outline=(20, 14, 18, 255), width=12),),
    }
    for name, fn in specs.items():
        img = canvas()
        d = ImageDraw.Draw(img)
        fn(d)
        finish(img, name, 96)


def panel():
    """9-slice dialogue/menu frame: near-black glass with a thin gold double border
    and small wayang-style corner ornaments. 96 px, 28 px margins."""
    n = 96 * 4
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((8, 8, n - 8, n - 8), fill=(12, 14, 20, 236))
    d.rectangle((20, 20, n - 20, n - 20), outline=(217, 169, 58, 255), width=6)
    d.rectangle((34, 34, n - 34, n - 34), outline=(120, 90, 40, 255), width=3)
    for cx, cy in ((20, 20), (n - 20, 20), (20, n - 20), (n - 20, n - 20)):
        d.regular_polygon((cx, cy, 26), 4, rotation=45, fill=(217, 169, 58, 255), outline=(20, 14, 18, 255))
        d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(20, 14, 18, 255))
    img.resize((96, 96), Image.LANCZOS).save(os.path.join(TEX, "panel.png"))
    # nameplate: gold bar with dark centre
    w, h = 128 * 4, 40 * 4
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(0, h / 2), (30, 0), (w - 30, 0), (w, h / 2), (w - 30, h), (30, h)], fill=(217, 169, 58, 255))
    d.polygon([(14, h / 2), (38, 10), (w - 38, 10), (w - 14, h / 2), (w - 38, h - 10), (38, h - 10)], fill=(28, 22, 20, 255))
    img.resize((128, 40), Image.LANCZOS).save(os.path.join(TEX, "nameplate.png"))


def veil():
    """Soft wispy mask for the glowing barrier in the gates (bright at the bottom)."""
    h, w = 128, 64
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    r = np.random.default_rng(3)
    f = np.sqrt(np.fft.fftfreq(h)[:, None] ** 2 * 4 + np.fft.fftfreq(w)[None, :] ** 2)
    n = np.real(np.fft.ifft2(np.fft.fft2(r.standard_normal((h, w))) * np.exp(-(f * 12) ** 2)))
    n = (n - n.min()) / (n.max() - n.min())
    a = np.clip((0.25 + 0.75 * y) * (1 - np.abs(x) ** 3) * (0.5 + 0.7 * n), 0, 1)
    save_rgb(np.dstack([a] * 3), "veil.png")


def main():
    shared_noise()
    floor_dandaka()
    floor_muara()
    floor_hub()
    god_icon("bayu", "#5fe0c8", sym_bayu)
    god_icon("surya", "#f2b845", sym_surya)
    god_icon("baruna", "#4aa3ff", sym_baruna)
    god_icon("indra", "#b784ff", sym_indra)
    reward_icons()
    slot_icons()
    panel()
    veil()
    print("textures ->", TEX)
    print("icons    ->", ICO)


if __name__ == "__main__":
    main()

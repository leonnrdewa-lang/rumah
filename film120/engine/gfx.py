"""Compositing primitives (numpy + Pillow) shared by every sequence.  All canvases are uint8 (H, W, 3)."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .tokens import *

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def lerp(a, b, x): return a + (b - a) * x
def prog(t, t0, t1): return clamp((t - t0) / max(1e-9, t1 - t0))
def ease_out(x, p=3): x = clamp(x); return 1 - (1 - x) ** p
def ease_in(x, p=3): x = clamp(x); return x ** p
def ease_io(x): x = clamp(x); return 3 * x * x - 2 * x ** 3
def ease_io5(x): x = clamp(x); return 16 * x ** 5 if x < .5 else 1 - (-2 * x + 2) ** 5 / 2
def out_expo(x): x = clamp(x); return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)

def kinetic(x, antic=0.10, over=0.045):
    """Anticipation -> fast movement -> controlled settle.  0 -> 1 (peaks ~1+over near 75 % then settles)."""
    x = clamp(x)
    a, m = 0.16, 0.72
    if x < a:  return -antic * math.sin(x / a * math.pi / 2) ** 2
    if x < m:  u = (x - a) / (m - a); return -antic + (1 + over + antic) * out_expo(u * 1.02)
    u = (x - m) / (1 - m); return (1 + over) - over * ease_io(u)

def spring(x, damp=6.0, freq=9.0):
    x = max(0.0, x); return 1 - math.exp(-damp * x) * math.cos(freq * x)

# ------------------------------------------------------------------ fonts / text
_fc = {}
def font(kind, size):
    k = (kind, int(size))
    if k not in _fc:
        for d in FONT_DIRS:
            p = os.path.join(d, FONT_FILES[kind])
            if os.path.exists(p): _fc[k] = ImageFont.truetype(p, int(size)); break
        else: _fc[k] = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(size))
    return _fc[k]

_tc = {}
def text_rgba(txt, kind, size, fill=WHITE, track=0.0, stroke=0, stroke_fill=(0, 0, 0), shadow=0, pad=8):
    key = (txt, kind, int(size), tuple(fill), round(track, 3), stroke, tuple(stroke_fill), shadow)
    if key in _tc: return _tc[key]
    f = font(kind, size); sp = track * size
    widths = [f.getlength(c) for c in txt]; tw = int(sum(widths) + sp * max(0, len(txt) - 1))
    asc, desc = f.getmetrics(); pd = pad + stroke + shadow; bw = tw + 2 * pd; bh = asc + desc + 2 * pd
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if shadow:
        sh = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh); xx = pd
        for c, w_ in zip(txt, widths): sd.text((xx + shadow * .4, pd + shadow * 1.2), c, font=f, fill=(0, 0, 0, 190)); xx += w_ + sp
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(shadow))); d = ImageDraw.Draw(im)
    x = pd
    for c, w_ in zip(txt, widths):
        d.text((x, pd), c, font=f, fill=tuple(fill) + (255,), stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,)); x += w_ + sp
    a = np.asarray(im); _tc[key] = a
    if len(_tc) > 800: _tc.pop(next(iter(_tc)))
    return a

def text_w(txt, kind, size, track=0.0):
    f = font(kind, size); return sum(f.getlength(c) for c in txt) + track * size * max(0, len(txt) - 1)

def text_size(txt, kind, size, track=0.0, pad=8):
    a = text_rgba(txt, kind, size, WHITE, track=track, pad=pad); return a.shape[1], a.shape[0]

def scale_rgba(a, s):
    if abs(s - 1) < 1e-3: return a
    return np.asarray(Image.fromarray(a).resize((max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), Image.BICUBIC))

def alpha_mul(a, k):
    if k >= 1: return a
    b = a.copy(); b[..., 3] = (b[..., 3] * max(0, k)).astype(np.uint8); return b

def rs(a, w, h, method=Image.BICUBIC):
    return np.array(Image.fromarray(a).resize((max(1, int(w)), max(1, int(h))), method))

# ------------------------------------------------------------------ compositing
def new_canvas(color=CHARCOAL):
    c = np.empty((H, W, 3), np.uint8); c[:] = color; return c

def paste(dst, src, x, y, alpha=1.0):
    x, y = int(round(x)), int(round(y)); sh, sw = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + sw), min(dst.shape[0], y + sh)
    if x1 <= x0 or y1 <= y0 or alpha <= 0: return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]; d = dst[y0:y1, x0:x1]
    if s.shape[2] == 4:
        a = (s[..., 3:4].astype(np.float32) / 255.0) * alpha
        d[:] = (d * (1 - a) + s[..., :3] * a).astype(np.uint8)
    elif alpha >= 1: d[:] = s
    else: d[:] = (d * (1 - alpha) + s * alpha).astype(np.uint8)
    return dst

def paste_masked(dst, src, x, y, mask, alpha=1.0):
    """src (h,w,3) placed at (x,y) through float mask (h,w) 0..1."""
    x, y = int(round(x)), int(round(y)); sh, sw = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + sw), min(dst.shape[0], y + sh)
    if x1 <= x0 or y1 <= y0: return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); m = (mask[y0 - y:y1 - y, x0 - x:x1 - x] * alpha)[..., None]
    d = dst[y0:y1, x0:x1]; d[:] = (d * (1 - m) + s * m).astype(np.uint8); return dst

def fill_rect(dst, x, y, w, h, color, alpha=1.0):
    x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(dst.shape[1], int(x + w)), min(dst.shape[0], int(y + h))
    if x1 > x0 and y1 > y0:
        d = dst[y0:y1, x0:x1]; d[:] = (d * (1 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)
    return dst

def draw_text(dst, txt, kind, size, x, y, fill=WHITE, anchor='l', alpha=1.0, scale=1.0, **kw):
    """(x,y) = top-left of the glyph box (anchor l), top-centre (c) or top-right (r)."""
    a = text_rgba(txt, kind, size, fill, **kw)
    if scale != 1: a = scale_rgba(a, scale)
    if alpha < 1: a = alpha_mul(a, alpha)
    w = a.shape[1]; ox = x if anchor == 'l' else x - w / 2 if anchor == 'c' else x - w
    return paste(dst, a, ox, y)

def vector(dst, fn, bbox=None, alpha=1.0, ss=2):
    """Run fn(ImageDraw, ss, ox, oy) on a supersampled transparent layer and composite it. Give a tight bbox for speed."""
    x, y, w, h = bbox or (0, 0, dst.shape[1], dst.shape[0]); x, y, w, h = int(x), int(y), int(w), int(h)
    if w < 2 or h < 2: return dst
    im = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0)); d = ImageDraw.Draw(im); fn(d, ss, x, y)
    return paste(dst, np.asarray(im.resize((w, h), Image.LANCZOS)), x, y, alpha)

def rrect(d, ss, ox, oy, x, y, w, h, r, fill=None, outline=None, width=2):
    d.rounded_rectangle([(x - ox) * ss, (y - oy) * ss, (x - ox + w) * ss, (y - oy + h) * ss], radius=r * ss, fill=fill, outline=outline, width=int(width * ss))

def line(d, ss, ox, oy, pts, col, width=2, alpha=255):
    d.line([((px - ox) * ss, (py - oy) * ss) for px, py in pts], fill=tuple(col) + (alpha,), width=int(width * ss))

_rm = {}
def round_mask(w, h, r):
    k = (int(w), int(h), int(r))
    if k not in _rm:
        ss = 3; im = Image.new('L', (w * ss, h * ss), 0); ImageDraw.Draw(im).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r * ss, fill=255)
        _rm[k] = np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255.0
    return _rm[k]

def shadow_rect(dst, x, y, w, h, blur=28, alpha=.55, dy=14):
    pad = int(blur * 2.5); m = np.zeros((int(h) + pad * 2, int(w) + pad * 2), np.uint8); m[pad:pad + int(h), pad:pad + int(w)] = 255
    m = np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255.0 * alpha
    x0, y0 = int(x) - pad, int(y) - pad + dy; sh, sw = m.shape
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + sw), min(H, y0 + sh)
    if X1 > X0 and Y1 > Y0:
        d = dst[Y0:Y1, X0:X1]; mm = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]; d[:] = (d * (1 - mm)).astype(np.uint8)
    return dst

def gradient_v(c, y0, y1, a0, a1, color=(0, 0, 0)):
    y0, y1 = int(max(0, y0)), int(min(H, y1))
    if y1 <= y0: return c
    k = np.linspace(a0, a1, y1 - y0, dtype=np.float32)[:, None, None]
    c[y0:y1] = (c[y0:y1] * (1 - k) + np.array(color, np.float32) * k).astype(np.uint8); return c

# ------------------------------------------------------------------ framing
def crop_window(fr, cx, cy, zoom, aspect):
    """Virtual camera window (aspect = w/h) centred at normalised (cx,cy); zoom>=1 relative to the full fit."""
    sh, sw = fr.shape[:2]; wh = sh / zoom; ww = wh * aspect
    if ww > sw: ww = sw / zoom if zoom > 1 else sw; wh = ww / aspect
    x0 = clamp(cx * sw - ww / 2, 0, sw - ww); y0 = clamp(cy * sh - wh / 2, 0, sh - wh)
    return fr[int(round(y0)):int(round(y0 + wh)), int(round(x0)):int(round(x0 + ww))], (x0 / sw, y0 / sh, ww / sw, wh / sh)

def fit_cover(fr, w, h, cx=.5, cy=.5, zoom=1.0):
    win, box = crop_window(fr, cx, cy, zoom, w / h); return rs(win, w, h), box

def fit_inside(fr, w, h):
    """Uncropped fit of the whole source frame inside (w,h); returns (img, (x_off, y_off))."""
    sh, sw = fr.shape[:2]; s = min(w / sw, h / sh); nw, nh = int(round(sw * s)), int(round(sh * s))
    return rs(fr, nw, nh), ((w - nw) // 2, (h - nh) // 2)

def blur_bg(fr, w=W, h=H, dark=.4, k=14):
    sm = rs(fr, 48, max(2, int(48 * fr.shape[0] / fr.shape[1])), Image.BOX)
    im = Image.fromarray(sm).resize((w // 8, h // 8), Image.BICUBIC).filter(ImageFilter.GaussianBlur(k / 4))
    return (np.asarray(im.resize((w, h), Image.BILINEAR)).astype(np.float32) * dark).astype(np.uint8)

# ------------------------------------------------------------------ fullscreen fx
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_vig = None
def vignette(img, strength=.3):
    global _vig
    if _vig is None:
        r = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2); _vig = np.clip(r / 1.45, 0, 1) ** 2.2
    return (img * (1 - strength * _vig[..., None])).astype(np.uint8)

_grain = None
def grain(img, amp, seed):
    global _grain
    if amp <= 0: return img
    if _grain is None:
        rng = np.random.default_rng(7); _grain = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    g = _grain[seed % 6]; g = np.roll(np.roll(g, (seed * 37) % (W // 2), 1), (seed * 53) % (H // 2), 0); g = np.repeat(np.repeat(g, 2, 0), 2, 1)
    return np.clip(img.astype(np.float32) + g[..., None] * amp, 0, 255).astype(np.uint8)

def grade(img, sat=1.0, contrast=1.0, lift=0.0, tint=(1, 1, 1), gain=1.0):
    f = img.astype(np.float32) / 255.0
    if sat != 1.0:
        l = (f * np.array([.299, .587, .114], np.float32)).sum(-1, keepdims=True); f = l + (f - l) * sat
    f = (f - .5) * contrast + .5; f = f * np.array(tint, np.float32) * gain + lift
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)

def motion_blur_h(img, px):
    px = int(px)
    if px < 2: return img
    acc = np.zeros(img.shape, np.float32); n = min(px, 14)
    for i in range(n): acc += np.roll(img, int((i / (n - 1) - .5) * px), 1)
    return (acc / n).astype(np.uint8)

def motion_blur_v(img, px):
    px = int(px)
    if px < 2: return img
    acc = np.zeros(img.shape, np.float32); n = min(px, 14)
    for i in range(n): acc += np.roll(img, int((i / (n - 1) - .5) * px), 0)
    return (acc / n).astype(np.uint8)

def chroma(img, px):
    px = int(px)
    if px < 1: return img
    o = img.copy(); o[..., 0] = np.roll(img[..., 0], px, 1); o[..., 2] = np.roll(img[..., 2], -px, 1); return o

def shake(img, dx, dy): return np.roll(np.roll(img, int(dx), 1), int(dy), 0)

def scale_about(img, s, cx=.5, cy=.5):
    if abs(s - 1) < 1e-3: return img
    h, w = img.shape[:2]
    if s > 1:
        ww, hh = w / s, h / s; x0 = clamp(cx * w - ww / 2, 0, w - ww); y0 = clamp(cy * h - hh / 2, 0, h - hh)
        return rs(img[int(y0):int(y0 + hh), int(x0):int(x0 + ww)], w, h)
    small = rs(img, w * s, h * s); out = np.zeros_like(img); paste(out, small, (w - small.shape[1]) / 2, (h - small.shape[0]) / 2); return out

def flash(img, k, color=(255, 255, 255)):
    return img if k <= 0 else (img * (1 - k) + np.array(color, np.float32) * k).astype(np.uint8)

# ------------------------------------------------------------------ perspective quads (3-D panels)
def homography(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b += [u, v]
    return np.linalg.solve(np.array(A, np.float64), np.array(b, np.float64))

def warp_quad(c, img, quad, alpha=1.0, resample=Image.BILINEAR):
    """Draw RGB image onto canvas inside the projected quad (TL,TR,BR,BL). Returns the clipped bbox drawn."""
    xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
    x0, y0, x1, y1 = int(max(0, min(xs) - 2)), int(max(0, min(ys) - 2)), int(min(W, max(xs) + 2)), int(min(H, max(ys) + 2))
    if x1 - x0 < 4 or y1 - y0 < 4: return None
    ih, iw = img.shape[:2]
    try: coef = homography([(0, 0), (iw, 0), (iw, ih), (0, ih)], [(px - x0, py - y0) for px, py in quad])
    except np.linalg.LinAlgError: return None
    im = Image.fromarray(img).transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, tuple(coef), resample)
    mk = Image.new('L', (iw, ih), 255).transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, tuple(coef), Image.BILINEAR)
    a = np.asarray(mk, np.float32)[..., None] / 255 * alpha; d = c[y0:y1, x0:x1]; d[:] = (d * (1 - a) + np.asarray(im) * a).astype(np.uint8)
    return (x0, y0, x1, y1)

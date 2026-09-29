"""Design system + compositing primitives (numpy/Pillow). 1080x1920 canvas, 30 fps."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
# Safe zones for Reels/TikTok chrome: keep meaningful type inside SAFE; captions live in CAP_Y band.
SAFE = dict(l=64, r=1016, t=210, b=1500)
CAP_Y = 1290
INK = (7, 8, 10); PAPER = (244, 241, 234); AMBER = (255, 122, 26); CYAN = (94, 226, 234); RED = (255, 64, 52)

FONT_DIRS = [os.environ.get('FONT_DIR', ''), '/home/user/fonts', '/tmp/fonts']
FONT_FILES = dict(
    black='montserrat-latin-900-normal.woff', bold='montserrat-latin-800-normal.woff', semi='montserrat-latin-700-normal.woff',
    inter='inter-latin-600-normal.woff', mono='space-mono-latin-700-normal.woff', monor='space-mono-latin-400-normal.woff')
_fc = {}
def font(kind, size):
    k = (kind, int(size))
    if k not in _fc:
        for d in FONT_DIRS:
            p = os.path.join(d, FONT_FILES[kind]) if d else ''
            if p and os.path.exists(p): _fc[k] = ImageFont.truetype(p, int(size)); break
        else:
            _fc[k] = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(size))
    return _fc[k]

# ---------- easing ----------
clamp = lambda x, a=0.0, b=1.0: a if x < a else b if x > b else x
def ease_out(x, p=3): x = clamp(x); return 1 - (1 - x) ** p
def ease_in(x, p=3): x = clamp(x); return x ** p
def ease_io(x): x = clamp(x); return 3 * x * x - 2 * x ** 3
def ease_io5(x): x = clamp(x); return 16 * x ** 5 if x < .5 else 1 - (-2 * x + 2) ** 5 / 2
def out_back(x, s=1.70158): x = clamp(x); return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2
def lerp(a, b, x): return a + (b - a) * x
def prog(t, t0, t1): return clamp((t - t0) / max(1e-6, t1 - t0))

# ---------- image helpers ----------
def rs(a, w, h, method=Image.BICUBIC):
    return np.array(Image.fromarray(a).resize((int(w), int(h)), method))

def crop_window(fr, cx, cy, zoom, aspect=W / H, base_h=None):
    """Virtual camera: window of `aspect` ratio centred at (cx,cy) in normalised source coords, zoom>=1 relative to full height."""
    sh, sw = fr.shape[:2]; wh = sh / zoom; ww = wh * aspect
    if ww > sw: ww = sw; wh = ww / aspect
    x0 = clamp(cx * sw - ww / 2, 0, sw - ww); y0 = clamp(cy * sh - wh / 2, 0, sh - wh)
    return fr[int(round(y0)):int(round(y0 + wh)), int(round(x0)):int(round(x0 + ww))], (x0 / sw, y0 / sh, ww / sw, wh / sh)

def fit_cover(fr, w, h, cx=.5, cy=.5, zoom=1.0):
    win, box = crop_window(fr, cx, cy, zoom, aspect=w / h)
    return rs(win, w, h), box

def blur_bg(fr, w=W, h=H, dark=.45, k=14):
    sm = rs(fr, 48, max(2, int(48 * fr.shape[0] / fr.shape[1])), Image.BOX)
    im = Image.fromarray(sm).resize((w // 8, h // 8), Image.BICUBIC).filter(ImageFilter.GaussianBlur(k / 4))
    return (np.asarray(im.resize((w, h), Image.BILINEAR)).astype(np.float32) * dark).astype(np.uint8)

def paste(dst, src, x, y, alpha=1.0):
    """Alpha-composite src (h,w,3|4 uint8) onto dst at (x,y) with clipping. Modifies dst."""
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

def fill_rect(dst, x, y, w, h, color, alpha=1.0):
    x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(dst.shape[1], int(x + w)), min(dst.shape[0], int(y + h))
    if x1 > x0 and y1 > y0:
        d = dst[y0:y1, x0:x1]; d[:] = (d * (1 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)
    return dst

_tc = {}
def text_rgba(txt, kind, size, fill=PAPER, track=0.0, stroke=0, stroke_fill=(0, 0, 0), shadow=0, pad=8):
    """Render text to an RGBA uint8 array. track = letter-spacing in em."""
    key = (txt, kind, int(size), fill, round(track, 3), stroke, shadow)
    if key in _tc: return _tc[key]
    f = font(kind, size); sp = track * size
    widths = [f.getlength(c) for c in txt]; tw = int(sum(widths) + sp * max(0, len(txt) - 1))
    asc, desc = f.getmetrics(); bw = tw + 2 * (pad + stroke + shadow); bh = asc + desc + 2 * (pad + stroke + shadow)
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = pad + stroke + shadow
    if shadow:
        sh = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh); xx = x
        for c, w_ in zip(txt, widths): sd.text((xx + shadow * .5, pad + stroke + shadow * 1.5), c, font=f, fill=(0, 0, 0, 170)); xx += w_ + sp
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(shadow))); d = ImageDraw.Draw(im)
    for c, w_ in zip(txt, widths):
        d.text((x, pad + stroke + shadow), c, font=f, fill=tuple(fill) + (255,), stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
        x += w_ + sp
    a = np.asarray(im); _tc[key] = a
    if len(_tc) > 600: _tc.pop(next(iter(_tc)))
    return a

def text_w(txt, kind, size, track=0.0):
    f = font(kind, size); return sum(f.getlength(c) for c in txt) + track * size * max(0, len(txt) - 1)

def scale_rgba(a, s):
    if abs(s - 1) < 1e-3: return a
    im = Image.fromarray(a); return np.asarray(im.resize((max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), Image.BICUBIC))

def alpha_mul(a, k):
    if k >= 1: return a
    b = a.copy(); b[..., 3] = (b[..., 3] * k).astype(np.uint8); return b

def draw_text(dst, txt, kind, size, x, y, fill=PAPER, anchor='l', alpha=1.0, scale=1.0, **kw):
    a = text_rgba(txt, kind, size, fill, **kw)
    if scale != 1: a = scale_rgba(a, scale)
    if alpha < 1: a = alpha_mul(a, alpha)
    h, w = a.shape[:2]
    ox = x if anchor == 'l' else x - w / 2 if anchor == 'c' else x - w
    return paste(dst, a, ox, y - (0 if kw.get('top', True) else h / 2))

# ---------- shapes via Pillow overlay (small) ----------
def vector(dst, fn, bbox=None, alpha=1.0, ss=2):
    """Run fn(ImageDraw) on a transparent layer (supersampled) and composite. bbox=(x,y,w,h) limits the layer."""
    x, y, w, h = bbox or (0, 0, dst.shape[1], dst.shape[0])
    im = Image.new('RGBA', (int(w) * ss, int(h) * ss), (0, 0, 0, 0)); d = ImageDraw.Draw(im); fn(d, ss, x, y)
    a = np.asarray(im.resize((int(w), int(h)), Image.LANCZOS)); return paste(dst, a, x, y, alpha)

def brackets(d, ss, ox, oy, x, y, w, h, c, col, th=4):
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        px, py = (px - ox) * ss, (py - oy) * ss
        d.line([(px, py + dy * c * ss), (px, py), (px + dx * c * ss, py)], fill=col + (255,), width=th * ss)

# ---------- fullscreen fx ----------
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_vig = None
def vignette(img, strength=.35):
    global _vig
    if _vig is None:
        r = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
        _vig = np.clip(r / 1.45, 0, 1) ** 2.2
    return (img * (1 - strength * _vig[..., None])).astype(np.uint8)

_grain = None
def grain(img, amp, seed):
    global _grain
    if amp <= 0: return img
    if _grain is None:
        rng = np.random.default_rng(7); _grain = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    g = _grain[seed % 6]; sx, sy = (seed * 37) % (W // 2), (seed * 53) % (H // 2)
    g = np.roll(np.roll(g, sx, 1), sy, 0); g = np.repeat(np.repeat(g, 2, 0), 2, 1)
    return np.clip(img.astype(np.float32) + g[..., None] * amp, 0, 255).astype(np.uint8)

def grade(img, sat=1.0, contrast=1.0, lift=0.0, tint=(1, 1, 1), gain=1.0):
    f = img.astype(np.float32) / 255.0
    if sat != 1.0:
        l = (f * np.array([.299, .587, .114], np.float32)).sum(-1, keepdims=True); f = l + (f - l) * sat
    f = (f - .5) * contrast + .5
    f = f * np.array(tint, np.float32) * gain + lift
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)

def motion_blur_h(img, px):
    px = int(px)
    if px < 2: return img
    acc = np.zeros(img.shape, np.float32); n = min(px, 14)
    for i in range(n): acc += np.roll(img, int((i / (n - 1) - .5) * px), 1)
    return (acc / n).astype(np.uint8)

def chroma(img, px):
    px = int(px)
    if px < 1: return img
    o = img.copy(); o[..., 0] = np.roll(img[..., 0], px, 1); o[..., 2] = np.roll(img[..., 2], -px, 1); return o

def shake(img, dx, dy):
    return np.roll(np.roll(img, int(dx), 1), int(dy), 0)

def scale_about(img, s, cx=.5, cy=.5):
    """Zoom the whole frame by s about (cx,cy) (crop+resize)."""
    if abs(s - 1) < 1e-3: return img
    h, w = img.shape[:2]
    if s > 1:
        ww, hh = w / s, h / s; x0 = clamp(cx * w - ww / 2, 0, w - ww); y0 = clamp(cy * h - hh / 2, 0, h - hh)
        return rs(img[int(y0):int(y0 + hh), int(x0):int(x0 + ww)], w, h)
    small = rs(img, w * s, h * s); out = np.zeros_like(img); paste(out, small, (w - small.shape[1]) / 2, (h - small.shape[0]) / 2); return out

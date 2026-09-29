"""Higher-level helpers shared by sequences: hero framing that respects watermarks, fitted panels, label helpers, cue helpers."""
import numpy as np
from PIL import Image
from .tokens import *
from . import gfx as G, ui
from .gfx import clamp, lerp, prog, ease_io, ease_out, kinetic


def hero_frame(ctx, eid, u, zoom=(1.0, 1.08), dur=None, drift=0.0, focus=None, allow_cover=True, max_h=1080):
    """Full-canvas (H,W,3) hero image of an excerpt at excerpt time u.
    Full-bleed cover crop only when profiled overlays (watermarks/logos) all stay inside the crop window; otherwise an uncropped fit (full width) over a blurred, darkened extension."""
    ex = ctx.ex(eid); fr = ex.frame(u, max_h=max_h); dur = dur or ex.dur; k = ease_io(clamp(u / max(dur, .01)))
    z = lerp(zoom[0], zoom[1], k); fx = ctx.focus(eid) if focus is None else focus; fx = clamp(fx + drift * (k - .5), .1, .9)
    if allow_cover and ctx.cover_safe(eid, cx=fx, zoom=z) and ex.aspect > .8:
        img, _ = G.fit_cover(fr, W, H, fx, .5, z); return img, 'cover'
    if ex.aspect < .8:                                               # portrait source: fit height, blur the sides
        bg = G.blur_bg(fr, dark=.35); fit, (ox, oy) = G.fit_inside(G.crop_window(fr, .5, .5, z, fr.shape[1] / fr.shape[0])[0], W, H); G.paste(bg, fit, ox, oy); return bg, 'fit'
    bg = G.blur_bg(fr, dark=.32); fit, (ox, oy) = G.fit_inside(fr, W, int(H * .62))
    fit = G.scale_about(fit, z) if z > 1.001 else fit
    yy = int((H - fit.shape[0]) * .42); G.paste(bg, fit, ox, yy); return bg, 'fit'


def panel_image(ctx, eid, u, max_w, max_h, speed=1.0, loop=False, max_h_src=720):
    """Uncropped fitted excerpt frame for an editorial panel; returns (img, excerpt)."""
    ex = ctx.ex(eid); fr = ex.frame(u, speed=speed, loop=loop, max_h=max_h_src); img, _ = G.fit_inside(fr, max_w, max_h); return img, ex


def early_grade(img, k=1.0):
    """Cool, slightly flattened grade used for early-era footage inside panels (k blends 0..1)."""
    return G.grade(img, sat=1 - .22 * k, contrast=1 - .06 * k, lift=.02 * k, tint=(1, 1 - .005 * k, 1 - .015 * k))


def label_for(ex, extra=None):
    lab = dict(ex.label)
    if extra: lab.update(extra)
    return lab


def visible(t, a, b, fade=.15):
    """0..1 visibility ramp for an element alive in [a,b]."""
    return clamp((t - a) / fade) * clamp((b - t) / fade)


def free_corner(ex, x, y, w, h, bw, bh, order=('bl', 'tl', 'br', 'tr'), pad=12):
    """Top-left of a (bw,bh) box placed in a corner of the panel rect (x,y,w,h) that avoids profiled static overlays (watermarks/logos) of the excerpt's clip.
    The panel is an uncropped fit (aspect preserved) so normalised overlay boxes map directly onto the rect."""
    ov = ex.clip.get('overlays') or []
    corners = {'bl': (x + pad, y + h - bh - pad), 'tl': (x + pad, y + pad), 'br': (x + w - bw - pad, y + h - bh - pad), 'tr': (x + w - bw - pad, y + pad)}
    def hit(pos):
        px, py = pos
        for o in ov:
            ox0, oy0, ox1, oy1 = x + o['x'] * w, y + o['y'] * h, x + (o['x'] + o['w']) * w, y + (o['y'] + o['h']) * h
            if not (px + bw < ox0 - 6 or px > ox1 + 6 or py + bh < oy0 - 6 or py > oy1 + 6): return True
        return False
    for k in order:
        if not hit(corners[k]): return corners[k]
    return corners[order[0]]


def place_label(c, ex, x, y, w, h, alpha=1.0, extra=None, size=22):
    """Source label INSIDE a panel rect, bottom-left unless a profiled overlay sits there (then another free corner); shrinks to fit narrow panels.  Returns the label rect."""
    lab = label_for(ex, extra); l1, l2 = ui.label_lines(lab)
    while True:
        lw = max(G.text_w(l1, 'mono', size, .04), G.text_w(l2, 'monor', int(size * .76), .02)) + 40
        if lw <= w - 24 or size <= 12: break
        size -= 1
    lh = int(size * 2.35) + 4; px, py = free_corner(ex, x, y, w, h, lw, lh)
    ui.source_label(c, lab, px, py, alpha=alpha, size=size); return (px, py, lw, lh)


def fit_size(txt, kind, size, maxw, track=0.0, min_size=20):
    """Largest font size <= size at which txt (with tracking) fits maxw."""
    w = G.text_w(txt, kind, size, track)
    return int(size) if w <= maxw else max(min_size, int(size * maxw / w))


def wrap_text(txt, kind, size, maxw, track=0.0):
    """Greedy word wrap to maxw; returns list of lines."""
    lines, cur = [], ''
    for w_ in txt.split():
        t_ = (cur + ' ' + w_).strip()
        if cur and G.text_w(t_, kind, size, track) > maxw: lines.append(cur); cur = w_
        else: cur = t_
    if cur: lines.append(cur)
    return lines


def tile_image(ctx, eid, u, tw, th, loop=True, max_h=360):
    """Fixed-size thumbnail tile of an excerpt.  Cover-crop only when no profiled watermark/logo would be cropped out; otherwise an uncropped fit on a dark plate."""
    ex = ctx.ex(eid); fr = ex.frame(u, loop=loop, max_h=max_h); fx = ctx.focus(eid)
    if ctx.cover_safe(eid, aspect=tw / th, cx=fx): return G.fit_cover(fr, tw, th, fx, .5, 1.0)[0]
    img = np.zeros((th, tw, 3), np.uint8); img[:] = (14, 14, 16); fit, (ox, oy) = G.fit_inside(fr, tw, th); G.paste(img, fit, ox, oy); return img


def window_from(big, X0, Y0, X1, Y1, s, cx=None, cy=None):
    """The rectangle (X0,Y0,X1,Y1) of the canvas showing a window of a full-canvas image `big` at scale s (s=1 shows all of `big` when the rect is the whole canvas)."""
    h, w = big.shape[:2]; rw, rh = max(2, int(X1 - X0)), max(2, int(Y1 - Y0)); ww, wh = min(w, rw / s), min(h, rh / s)
    cx = w / 2 if cx is None else cx; cy = h / 2 if cy is None else cy; x0 = clamp(cx - ww / 2, 0, w - ww); y0 = clamp(cy - wh / 2, 0, h - wh)
    return G.rs(big[int(round(y0)):int(round(y0 + wh)), int(round(x0)):int(round(x0 + ww))], rw, rh)

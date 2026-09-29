"""Recurring identity components: source labels, panels, year plates, the Spine, subtitles."""
import numpy as np
from PIL import Image
from .tokens import *
from . import gfx as G
from .gfx import clamp, lerp, prog, ease_out, ease_io, kinetic

# ---------------------------------------------------------------- source label
def label_lines(lab):
    """lab = {"model": "SORA", "year": "2024", "creator": "OpenAI", "license": "PD (Commons)"} -> (line1, line2)"""
    l1 = f"{lab.get('model', '')} · {lab.get('year', '')}".strip(' ·').upper()
    l2 = ' · '.join(x for x in (lab.get('creator'), lab.get('license')) if x)
    return l1, l2

def source_label(c, lab, x, y, anchor='l', alpha=1.0, plate=True, size=24):
    l1, l2 = label_lines(lab)
    a1 = G.text_rgba(l1, 'mono', size, WHITE, track=.04, pad=2); a2 = G.text_rgba(l2, 'monor', int(size * .76), (200, 196, 186), track=.02, pad=2) if l2 else None
    w = max(a1.shape[1], a2.shape[1] if a2 is not None else 0) + 28; h = a1.shape[0] + (a2.shape[0] if a2 is not None else 0) + 18
    x0 = x if anchor == 'l' else x - w / 2 if anchor == 'c' else x - w
    if plate:
        G.vector(c, lambda d, ss, ox, oy: G.rrect(d, ss, ox, oy, x0, y, w, h, 8, fill=(8, 8, 9, int(200 * alpha))), bbox=(x0 - 2, y - 2, w + 4, h + 4))
    G.paste(c, G.alpha_mul(a1, alpha), x0 + 12, y + 7)
    if a2 is not None: G.paste(c, G.alpha_mul(a2, alpha), x0 + 12, y + 7 + a1.shape[0] - 3)
    G.fill_rect(c, x0, y + 8, 4, h - 16, VOLT, alpha)
    return (x0, y, w, h)

def chip(c, txt, x, y, size=22, fg=WHITE, bg=(8, 8, 9), bga=.8, kind='mono', track=.06, alpha=1.0, anchor='l', dot=None):
    a = G.text_rgba(txt, kind, size, fg, track=track, pad=2); th, tw = a.shape[:2]; pad = int(size * .55); dw = int(size * .9) if dot else 0
    w = tw + 2 * pad + dw; h = th + int(size * .5); x0 = x if anchor == 'l' else x - w / 2 if anchor == 'c' else x - w
    G.vector(c, lambda d, ss, ox, oy: G.rrect(d, ss, ox, oy, x0, y, w, h, h / 2, fill=tuple(bg) + (int(255 * bga * alpha),)), bbox=(x0 - 2, y - 2, w + 4, h + 4))
    if dot is not None:
        G.vector(c, lambda d, ss, ox, oy: d.ellipse([(x0 + pad - ox) * ss, (y + h / 2 - size * .17 - oy) * ss, (x0 + pad + size * .34 - ox) * ss, (y + h / 2 + size * .17 - oy) * ss], fill=tuple(dot) + (int(255 * alpha),)), bbox=(x0, y, w, h))
    G.paste(c, G.alpha_mul(a, alpha), x0 + pad + dw, y + int(size * .22)); return (x0, y, w, h)

# ---------------------------------------------------------------- panels
def panel_frame(c, x, y, w, h, alpha=1.0, shadow=True, ticks=True, outline=True):
    if shadow: G.shadow_rect(c, x, y, w, h, alpha=.5 * alpha)
    if outline: G.vector(c, lambda d, ss, ox, oy: G.rrect(d, ss, ox, oy, x - 4, y - 4, w + 8, h + 8, 8, outline=(244, 239, 228, int(46 * alpha)), width=1.5), bbox=(x - 8, y - 8, w + 16, h + 16))
    if ticks:
        for (px, py, dx, dy) in ((x - 14, y - 14, 1, 1), (x + w + 14, y - 14, -1, 1), (x - 14, y + h + 14, 1, -1), (x + w + 14, y + h + 14, -1, -1)):
            G.fill_rect(c, px if dx > 0 else px - 12, py, 12, 2, WHITE, .5 * alpha); G.fill_rect(c, px, py if dy > 0 else py - 12, 2, 12, WHITE, .5 * alpha)

def panel(c, img, x, y, alpha=1.0, radius=6, shadow=True, ticks=True, outline=True):
    """Paste an already-fitted image (h,w,3) as an editorial panel with rounded corners."""
    h, w = img.shape[:2]; panel_frame(c, x, y, w, h, alpha, shadow, ticks, outline)
    G.paste_masked(c, img, x, y, G.round_mask(w, h, radius), alpha); return (x, y, w, h)

# ---------------------------------------------------------------- Spine (the recurring timeline)
Y0, Y1 = 2016, 2026
def year_x(year, x0=MARGIN, x1=W - MARGIN): return x0 + (year - Y0) / (Y1 - Y0) * (x1 - x0)

def spine(c, y=SPINE_Y, reveal=1.0, crack=0.0, years=(), highlight=None, alpha=1.0, seed=3, t=0.0, x0=MARGIN, x1=W - MARGIN, color=WHITE, lock=0.0):
    """Hairline timeline.  reveal 0..1 = how much of the line is drawn; crack 0..1 = segments displaced/jittering (melting); lock 0..1 = volt lock flash.
    years: iterable of years whose ticks/labels are shown; highlight: year drawn in volt with a larger tick."""
    xe = x0 + (x1 - x0) * clamp(reveal); rng = np.random.default_rng(seed + int(t * 8) * (1 if crack > 0.02 else 0))
    if crack > 0.02:
        n = 22; edges = np.linspace(x0, xe, n + 1)
        for i in range(n):
            if rng.random() < .28 * crack: continue                                   # gaps
            dy = rng.normal(0, 7 * crack); dx = rng.normal(0, 5 * crack)
            G.fill_rect(c, edges[i] + dx, y + dy, max(2, edges[i + 1] - edges[i] - 3), 2, color, alpha * (.5 + .4 * rng.random()))
    else:
        G.fill_rect(c, x0, y, xe - x0, 2, color, alpha * .85)
    if lock > 0: G.fill_rect(c, x0, y - 1, xe - x0, 4, VOLT, alpha * lock)
    for yr in years:
        px = year_x(yr, x0, x1)
        if px > xe + 1: continue
        hl = (highlight == yr); col = VOLT if hl else color; th = 22 if hl else 12
        jx = rng.normal(0, 3 * crack) if crack > .02 else 0
        G.fill_rect(c, px + jx, y - th // 2, 2, th, col, alpha * (1 if hl else .7))
        G.draw_text(c, str(yr), 'mono', 20, px + jx, YEARS_Y - 6, col, anchor='c', alpha=alpha * (1 if hl else .55), track=.04, pad=2)

def frame_icons(c, y, x0, x1, n, prog_, seed=5, alpha=1.0, w=26, h=15):
    """Small frame rectangles scattered above the spine (fragments) that are later swept onto the line."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        base = x0 + (x1 - x0) * (i + .5) / n; dy0 = rng.normal(0, 28); ang = rng.normal(0, .5)
        k = clamp(prog_ * 1.4 - i / n * .4); e = ease_io(k); yy = y - 12 - lerp(abs(dy0) + 10, 0, e)
        xx = base + rng.normal(0, 10) * (1 - e)
        G.fill_rect(c, xx - w / 2, yy - h, w, h, WHITE, alpha * (.25 + .5 * e)); G.fill_rect(c, xx - w / 2 + 3, yy - h + 3, w - 6, h - 6, CHARCOAL, alpha)

# ---------------------------------------------------------------- hero type helpers
def smear_rgba(a, dy):
    dy = int(dy)
    if dy < 2: return a
    n = min(dy, 9); f = a.astype(np.float32); acc = np.zeros_like(f)
    for i in range(n): acc += np.roll(f, int((i / (n - 1) - .5) * dy), 0)
    return (acc / n).astype(np.uint8)

def hero_lines(c, lines, x, y, size, colors, t0, t, lh=1.02, kind='display', anchor='l', stagger=.12, dur=.55, slide=60, track=-.005, alpha=1.0, scale_in=0.0):
    """Kinetic stacked type: each line rises with anticipation -> movement -> settle; vertical motion blur while in flight."""
    for i, (ln, col) in enumerate(zip(lines, colors)):
        u = (t - t0 - i * stagger) / dur
        if u <= 0: continue
        e = kinetic(u); a = G.text_rgba(ln, kind, size, col, track=track, pad=4)
        speed = abs(kinetic(u) - kinetic(u - .04)) * slide * 1.5
        a = smear_rgba(a, speed)
        if scale_in: a = G.scale_rgba(a, 1 + scale_in * (1 - clamp(e)))
        yy = y + i * size * lh + (1 - e) * slide; xx = x if anchor == 'l' else x - a.shape[1] / 2 if anchor == 'c' else x - a.shape[1]
        G.paste(c, a, xx, yy, alpha=clamp(u * 3) * alpha)

# ---------------------------------------------------------------- subtitles
def caption_chunks(words_by_line):
    """words_by_line: {line: [(word, t0, t1), ...]} (global times).  -> [[t0, t1, [(w,s,e)..], line]]  (<=4 words, phrase-level, no orphans)."""
    out = []
    for n, ws in words_by_line.items():
        clauses, cur = [], []
        for w in ws:
            cur.append(w)
            if w[0][-1] in '.?!,;:—': clauses.append(cur); cur = []
        if cur: clauses.append(cur)
        merged = []
        for cl in clauses:
            if merged and len(merged[-1]) == 1 and merged[-1][0][0][-1] in ',—': merged[-1] = merged[-1] + cl
            else: merged.append(list(cl))
        for cl in merged:
            k = len(cl); short = k <= 5 and sum(len(w[0]) for w in cl) + k <= 26
            m = 1 if short else -(-k // 4); base, extra = divmod(k, m); i = 0
            for j in range(m):
                ln = base + (1 if j < extra else 0); part = cl[i:i + ln]; i += ln; out.append([part[0][1], part[-1][2], part, n])
    for i, ch in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else ch[1] + .5
        ch[1] = min(ch[1] + .35, max(ch[1], nxt - .02))
    return out

def draw_subtitle(c, t, chunks, accent=VOLT, y=SUB_Y):
    for t0, t1, ws, n in chunks:
        if not (t0 - .05 <= t < t1): continue
        txt = ' '.join(w[0] for w in ws); size = 60
        while G.text_w(txt, 'ui_xb', size, -.01) > 940 and size > 38: size -= 2
        tw = G.text_w(txt, 'ui_xb', size, -.01); x = (W - tw) / 2; pop = ease_out(prog(t, t0 - .05, t0 + .10)); yy = y + (1 - pop) * 10
        for (w, s, e) in ws:
            ww = G.text_w(w, 'ui_xb', size, -.01); sp = G.text_w(' ', 'ui_xb', size, -.01); active = s - .03 <= t < e + .06
            G.draw_text(c, w, 'ui_xb', size, x - 8, yy - 8, accent if active else WHITE, track=-.01, shadow=9, alpha=min(1, pop + .25)); x += ww + sp
        return

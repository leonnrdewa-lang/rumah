"""SEQUENCES 6 + gallery - the race accelerates (S4: 43-56 s): a moving gallery of excerpts from different developers/model families, each introduced by its own content-linked transition.
Cast (plan.cast.seq06): entries = [ {"ex": excerpt id, "model": "KLING 1.0", "dev": "KUAISHOU", "year": "2024", "date": "JUN 6, 2024", "note": "what to notice (from verified facts)", "hold": 2.2, "tr": "letters|lane|iris|slat|shards|split"} ... ] (6-8).
Layout per entry: developer lane strip (all lanes shown, active one volt) + year-marked Spine at the top, uncropped panel, big model name (Anton), date/notes.  Transitions: letters = footage plays INSIDE the year's digits which then expand
to the panel (chapter-style typographic transition); lane = conveyor push along the developer lane; iris = circular reveal from the panel's subject; slat / shards / split = masks.  cues: s6.entries = [t0, ...]."""
import numpy as np
from PIL import Image
from engine import gfx as G, ui, kit, transitions as TR
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'gallery'
STYLE = lambda t: 'early' if t < 45.0 else 'now'
T0, T1 = 43.0, 56.0
TR_D = .55
PW, PH = 952, 536


def _entries(ctx): return list(ctx.cast('seq06', 'entries', [])) or []


def _starts(ctx, n):
    ts = ctx.cue('s6.entries')
    if ts and len(ts) >= n: return ts[:n]
    holds = [e.get('hold', (T1 - T0 - .3) / max(1, n)) for e in _entries(ctx)]; tot = sum(holds); k = (T1 - T0 - .3) / tot; out = []; a = T0
    for h in holds: out.append(a); a += h * k
    return out


def _lanes(ctx): 
    seen = []
    for e in _entries(ctx):
        if e['dev'] not in seen: seen.append(e['dev'])
    return seen


def scene(ctx, i, t, ts, letters_mask=None):
    """Static layout for entry i at time t (its own local clock)."""
    e = _entries(ctx)[i]; c = G.new_canvas(); u = max(0.0, t - ts[i]); lanes = _lanes(ctx)
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=int(e['year']), t=t, alpha=.9)
    # developer lane strip
    ly = 290
    for j, ln in enumerate(lanes):
        on = ln == e['dev']; y = ly + j * 0  # single row of lane tags
    x = MARGIN
    for ln in lanes:
        on = ln == e['dev']; w = G.text_w(ln, 'mono', 20, .06) + 28
        if x + w > W - MARGIN: break
        G.vector(c, lambda d, ss, ox, oy: G.rrect(d, ss, ox, oy, x, ly, w, 38, 19, fill=(VOLT + (255,) if on else (255, 255, 255, 28))), bbox=(x - 2, ly - 2, w + 4, 42))
        G.draw_text(c, ln, 'mono', 20, x + 14, ly + 6, (10, 10, 10) if on else (170, 166, 156), track=.06, pad=2); x += w + 10
    if e.get('ex'):
        img, ex = kit.panel_image(ctx, e['ex'], u, PW, PH, loop=True, max_h_src=720); img = kit.early_grade(img, 1.0 if int(e['year']) < 2024 else 0.0)
        px = (W - img.shape[1]) // 2; py = 430 + (PH - img.shape[0]) // 2
        x0, y0, w0, h0 = ui.panel(c, img, px, py); kit.place_label(c, ex, x0, y0, w0, h0, size=21)
    else:                                                       # data card: no reusable footage exists for this product - say so, show only developer-stated facts
        px = (W - PW) // 2; py = 430; card = np.zeros((PH, PW, 3), np.uint8); card[:] = (18, 19, 21); x0, y0, w0, h0 = ui.panel(c, card, px, py)
        G.draw_text(c, 'NO REUSABLE DEMO FOOTAGE', 'mono', 22, px + 34, py + 30, GREY, track=.08, alpha=clamp(u / .4)); G.fill_rect(c, px + 34, py + 70, 120 * ease_out(prog(u, .1, .6)), 3, VOLT, 1.0)
        ft = ctx.cue(e['fact_cue']) if e.get('fact_cue') else None
        for k, fct in enumerate(e.get('facts', [])[:4]):
            a2 = ease_out(prog(t, ft[k], ft[k] + .4)) if ft and k < len(ft) else ease_out(prog(u, .25 + .18 * k, .6 + .18 * k)); G.draw_text(c, fct, 'ui_xb', kit.fit_size(fct, 'ui_xb', 34, PW - 76, -.005), px + 34, py + 110 + k * 88 + (1 - a2) * 24, WHITE, alpha=a2, track=-.005)
            G.fill_rect(c, px + 34, py + 110 + k * 88 + 60, PW - 68, 1, WHITE, .14 * a2)
        G.draw_text(c, 'SOURCE · DEVELOPER PAGES', 'monor', 18, px + 34, py + PH - 44, GREY, track=.05, alpha=clamp((u - .8) / .4))
    # model name + date + note
    a = kinetic(u / .6)
    G.draw_text(c, e['model'], 'display', 130, MARGIN, 1000 + (1 - clamp(a)) * 50, WHITE, alpha=clamp(a * 3), track=-.005)
    G.draw_text(c, f"{e['dev']} · {e.get('date', e['year'])}", 'mono', 26, MARGIN, 1178, VOLT, alpha=clamp((u - .2) / .3), track=.05)
    if e.get('note'): G.draw_text(c, e['note'], 'ui', 32, MARGIN, 1222, (222, 218, 208), alpha=clamp((u - .35) / .3))
    return c


def _trans(ctx, kind, a, b, p, i):
    if kind == 'letters':
        yr = _entries(ctx)[i]['year']; m = np.zeros((H, W), np.float32)
        glyph = G.text_rgba(yr, 'display', 560, WHITE, track=-.02, pad=0)[..., 3].astype(np.float32) / 255; gh, gw = glyph.shape
        e = ease_io(p); sc = lerp(1.0, 5.5, ease_io(clamp((p - .35) / .65))); g2 = np.asarray(Image.fromarray((glyph * 255).astype(np.uint8)).resize((int(gw * sc), int(gh * sc)), Image.BILINEAR), np.float32) / 255
        ox = int(W / 2 - g2.shape[1] / 2); oy = int(760 - g2.shape[0] / 2); y0, x0 = max(0, oy), max(0, ox); y1, x1 = min(H, oy + g2.shape[0]), min(W, ox + g2.shape[1])
        if y1 > y0 and x1 > x0: m[y0:y1, x0:x1] = g2[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        dark = (a.astype(np.float32) * (1 - .6 * clamp(p * 3))).astype(np.uint8); return TR.blend_mask(dark, b, np.clip(m * clamp(p * 4), 0, 1))
    if kind == 'lane':
        off = int(ease_io(p) * W); return G.motion_blur_h(np.concatenate([a, b], 1)[:, off:off + W], int(200 * np.sin(np.pi * p)) + 2)
    if kind == 'iris': return TR.transition('iris', a, b, p)
    if kind == 'slat': return TR.transition('slat_v', a, b, p)
    if kind == 'shards': return TR.transition('shards', a, b, p, seed=i)
    if kind == 'split':
        x = int(ease_io(p) * W); out = a.copy(); out[:, :x] = b[:, :x]; G.fill_rect(out, x - 3, 0, 6, H, VOLT, 1.0 if 0 < p < 1 else 0); return out
    return TR.transition('flash', a, b, p)


def render(ctx, t):
    es = _entries(ctx); n = len(es)
    if not n: return G.new_canvas()
    ts = _starts(ctx, n); i = max(j for j in range(n) if t >= ts[j] - 1e-6) if t >= ts[0] else 0
    if i + 1 < n and t > ts[i + 1] - TR_D / 2 - .0:
        p = (t - (ts[i + 1] - TR_D / 2)) / TR_D
        if 0 <= p < 1: return _trans(ctx, es[i + 1].get('tr', 'slat'), scene(ctx, i, t, ts), scene(ctx, i + 1, t, ts), p, i + 1)
    if t < ts[0]:
        return scene(ctx, 0, t, ts)
    if i > 0 and t < ts[i] + TR_D / 2:
        p = (t - (ts[i] - TR_D / 2)) / TR_D
        if 0 <= p < 1: return _trans(ctx, es[i].get('tr', 'slat'), scene(ctx, i - 1, t, ts), scene(ctx, i, t, ts), p, i)
    return scene(ctx, i, t, ts)


def events(ctx):
    es = _entries(ctx); ts = _starts(ctx, len(es)) if es else []; ev = []
    for i, e in enumerate(es):
        k = e.get('tr', 'slat'); t0 = ts[i] - TR_D / 2
        ev.append({'letters': ('type_hit', ts[i], dict(size=.9)), 'lane': ('slide', t0, dict(dur=.55)), 'iris': ('whoosh', t0, dict(dur=.5, up=True)), 'slat': ('whoosh', t0, dict(dur=.5)), 'shards': ('glitch', t0 + .2, {}), 'split': ('whoosh', t0, dict(dur=.4, up=True))}.get(k, ('whoosh', t0, dict(dur=.4))))
        ev.append(('lock', ts[i] + .1, dict(size=.6, f=1200 + 90 * (i % 5))))
    return ev

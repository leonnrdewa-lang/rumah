"""SEQUENCE - Hero shots (S6: 90-104 s).  Let the best recent clips breathe (3-5 s each) with minimal overlay.
Cast (plan.cast.seq11): heroes = [ {"ex": excerpt id, "dur": 3.6, "zoom": [1.0, 1.08], "note": null | "STILL VISIBLE: ...", "note_src": "developer page", "continue_seq10": true (hero 0 only)} ... ] (4-6); hero 0 = the excerpt of the tile that expanded in seq10.
Overlay per shot: source label only (placed off any profiled watermark) + a thin playhead bar (the Spine, receded).  One shot may carry a short, sourced limitation note."""
import numpy as np
from engine import gfx as G, ui, kit, transitions as TR
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'heroes'
STYLE = 'now'
T0, T1 = 90.0, 104.0
SUBS = True


def _heroes(ctx): return list(ctx.cast('seq11', 'heroes', [])) or []


def _starts(ctx, n):
    ts = ctx.cue('s11.heroes')
    if ts and len(ts) >= n: return ts[:n]
    hs = _heroes(ctx); tot = sum(h.get('dur', 3.5) for h in hs); k = (T1 - T0) / tot; out = []; a = T0
    for h in hs: out.append(a); a += h.get('dur', 3.5) * k
    return out


def shot(ctx, i, t, ts):
    h = _heroes(ctx)[i]; u = max(0.0, t - ts[i]); ex = ctx.ex(h['ex']); dur = (ts[i + 1] if i + 1 < len(ts) else T1) - ts[i]
    if i == 0 and h.get('continue_seq10'):                       # same clip time and zoom curve as the tile that expanded in seq10
        from seq import seq10_contact as C
        img, mode = kit.hero_frame(ctx, h['ex'], max(0.0, t - C.HERO_T0), zoom=(1.0, 1.08), dur=C.T1 - C.T0 + 3)
    else: img, mode = kit.hero_frame(ctx, h['ex'], u, zoom=tuple(h.get('zoom', (1.0, 1.08))), dur=dur + .3, drift=h.get('drift', 0.0))
    c = img.copy(); G.gradient_v(c, 1180, H, 0, .5)
    if u < .5: c = G.scale_about(c, 1 + .015 * (1 - u / .5))
    # minimal overlay: label + playhead
    ui.spine(c, reveal=1.0, years=(), t=t, alpha=.35)
    ph = clamp(u / dur); G.fill_rect(c, MARGIN, SPINE_Y - 1, (W - 2 * MARGIN) * ph, 4, VOLT, .9)
    lab_y = 1440 if h.get('note') is None else 1440
    ui.source_label(c, ex.label, MARGIN, lab_y, alpha=ease_out(prog(u, .25, .6)) * (1 - ease_out(prog(u, dur - .35, dur - .05))))
    if h.get('note'):
        a = ease_out(prog(u, .8, 1.2)) * (1 - ease_out(prog(u, dur - .4, dur - .05))); lines = kit.wrap_text(h['note'], 'ui_xb', 32, W - 2 * MARGIN - 52, -.005)[:3]
        ph = 26 + 42 * len(lines) + (34 if h.get('note_src') else 8)
        G.vector(c, lambda d, ss, ox, oy: G.rrect(d, ss, ox, oy, MARGIN, 300, W - 2 * MARGIN, ph, 10, fill=(8, 8, 9, int(215 * a))), bbox=(MARGIN - 2, 298, W - 2 * MARGIN + 4, ph + 4))
        G.fill_rect(c, MARGIN, 312, 5, ph - 24, VOLT, a)
        for k, ln in enumerate(lines): G.draw_text(c, ln, 'ui_xb', 32, MARGIN + 26, 318 + 42 * k, WHITE, alpha=a, track=-.005)
        if h.get('note_src'): G.draw_text(c, 'SOURCE · ' + h['note_src'], 'monor', 18, MARGIN + 26, 318 + 42 * len(lines) + 4, GREY, alpha=a, track=.04)
    return c


def render(ctx, t):
    hs = _heroes(ctx); n = len(hs)
    if not n: return G.new_canvas()
    ts = _starts(ctx, n); i = max(j for j in range(n) if t >= ts[j] - 1e-6) if t >= ts[0] else 0; c = shot(ctx, i, t, ts)
    if i + 1 < n and t > ts[i + 1] - .18: c = TR.transition('dip', c, shot(ctx, i + 1, t, ts), (t - (ts[i + 1] - .18)) / .18)
    return c


def events(ctx):
    hs = _heroes(ctx); ts = _starts(ctx, len(hs)) if hs else []; ev = []
    for i, h in enumerate(hs):
        if i: ev.append(('whoosh', ts[i] - .2, dict(dur=.3, gain=.6)))
        ev.append(('swell', ts[i] - .1, dict(dur=2.2, f=146.83 * (1 + .12 * i))))
    return ev

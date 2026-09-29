"""SEQUENCE 7 - Matched split-screen comparisons of similar subjects across generations (S4: 56-63 s).
Cast (plan.cast.seq07): pairs = [ {"a": older excerpt id, "b": newer excerpt id, "subject": "dogs", "ya": "2023", "yb": "2026", "ma": "RUNWAY GEN-2", "mb": "SEEDANCE 2.0", "same_prompt": false} ... ] (2, ~3.4 s each).
Both frames use identical geometry; year plates in Anton; a volt divider slides between them.  Anything that is not the same prompt/conditions carries ILLUSTRATIVE · DIFFERENT PROMPTS.  cues: s7.pairs = [t0, t1, ...]."""
import numpy as np
from engine import gfx as G, ui, kit, transitions as TR
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'splits'
STYLE = 'now'
T0, T1 = 56.0, 63.0
PW, PH = 853, 480


def _pairs(ctx): return list(ctx.cast('seq07', 'pairs', [])) or []


def _starts(ctx, n):
    ts = ctx.cue('s7.pairs')
    if ts and len(ts) >= n: return ts[:n]
    span = (T1 - T0 - .2) / max(1, n); return [T0 + .1 + i * span for i in range(n)]


def pair_scene(ctx, i, t, ts):
    p = _pairs(ctx)[i]; u = max(0.0, t - ts[i]); c = G.new_canvas()
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=int(p['yb']) if p['yb'].isdigit() else None, t=t, alpha=.85)
    ea, eb = ctx.ex(p['a']), ctx.ex(p['b']); gap = 26; y0 = 322
    ia, _ = G.fit_inside(ea.frame(u, loop=True, max_h=720), PW, PH); ib, _ = G.fit_inside(eb.frame(u, loop=True, max_h=1080), PW, PH); ia = kit.early_grade(ia, 1.0)
    xa = (W - ia.shape[1]) // 2; xb = (W - ib.shape[1]) // 2
    # entrance: top panel drops in, bottom slides in from the right, divider scans between
    e1 = kinetic(u / .55); e2 = kinetic((u - .28) / .55)
    ya = y0 + (PH - ia.shape[0]) // 2 - (1 - clamp(e1, 0, 1.05)) * 260; yb = y0 + PH + gap + (PH - ib.shape[0]) // 2; xb2 = xb + (1 - clamp(e2, 0, 1.05)) * 900
    pa = ui.panel(c, ia, xa, ya, alpha=clamp(e1 * 3)); pb = ui.panel(c, ib, xb2, yb, alpha=clamp(e2 * 3))
    kit.place_label(c, ea, *pa, alpha=clamp(e1 * 2), size=20); kit.place_label(c, eb, *pb, alpha=clamp(e2 * 2), size=20)
    sy = y0 + PH + gap / 2; sw = (W - 2 * MARGIN) * clamp(ease_out(u / .6)); G.fill_rect(c, MARGIN, sy - 1, sw, 3, VOLT, .95)
    G.draw_text(c, p['ya'], 'display', 120, pa[0] + 18, pa[1] + 12, WHITE, alpha=clamp(e1 * 2), shadow=8)
    G.draw_text(c, p['yb'], 'display', 120, pb[0] + 18, pb[1] + 12, VOLT, alpha=clamp(e2 * 2), shadow=8)
    if not p.get('same_prompt', False): ui.chip(c, 'ILLUSTRATIVE · DIFFERENT PROMPTS', W - MARGIN, yb + PH + 34, 19, anchor='r', dot=VOLT, alpha=clamp((u - .7) / .3))
    G.draw_text(c, p.get('subject', '').upper(), 'mono', 22, MARGIN, yb + PH + 36, (200, 196, 186), track=.08, alpha=clamp((u - .5) / .3))
    return c


def render(ctx, t):
    ps = _pairs(ctx); n = len(ps)
    if not n: return G.new_canvas()
    ts = _starts(ctx, n); i = max(j for j in range(n) if t >= ts[j] - 1e-6) if t >= ts[0] else 0; c = pair_scene(ctx, i, t, ts)
    if i + 1 < n and t > ts[i + 1] - .3:
        c = TR.transition('slat', c, pair_scene(ctx, i + 1, t, ts), (t - (ts[i + 1] - .3)) / .3)
    return c


def events(ctx):
    ps = _pairs(ctx); ts = _starts(ctx, len(ps)) if ps else []; ev = []
    for i in range(len(ps)):
        ev += [('slide', ts[i], dict(dur=.5)), ('slide', ts[i] + .28, dict(dur=.5, up=False)), ('lock', ts[i] + .85, dict(size=.8, f=1400 + 180 * i))]
        if i: ev.append(('whoosh', ts[i] - .3, dict(dur=.3)))
    return ev

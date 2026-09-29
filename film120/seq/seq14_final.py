"""SEQUENCE - Final line + replay seam (S8: 115-120 s).
Cast (plan.cast.seq14): shot = excerpt id that plays full-bleed (>= 4.8 s; default seq13.recent), lines = [[text, 'white'|'volt'], ...] the on-screen final line, credit = small credit line (optional).
115.0        the shot continues under the final line (hard cut on the beat; seq13's peak clip may be reused)
118.35-119.25 the full-bleed frame closes down (iris) into the panel rect of frame 0 of the film
119.1-119.8  content cross-fades to seq01's frame 0; the last frames ARE frame 0 (loops seamlessly); the grade eases to the opening's early grade.
NAME = 'final'."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, ease_io5, kinetic
from engine.compose import style_params, blend_style
from seq import seq01_hook as S1

NAME = 'final'
T0, T1 = 115.0, 120.0
T_TYPE, T_TXT_OUT, T_SH0, T_SH1, T_XF0, T_XF1 = 115.3, 118.0, 118.35, 119.25, 119.1, 119.8
SUB_Y = 1300


def STYLE(t): return blend_style(style_params('now', t), style_params('early', t), ease_io(prog(t, 119.0, 119.9)))


def _target(ctx):
    if 'final_target' not in ctx.cache:
        early = ctx.cast_ex('seq01', 'early'); fr = early.frame(0.0, loop=True, max_h=720); img, _ = G.fit_inside(fr, W - 2 * 24, 700); h, w = img.shape[:2]; ctx.cache['final_target'] = ((W - w) // 2, 790, w, h)
    return ctx.cache['final_target']


def _shot(ctx, t):
    eid = ctx.cast('seq14', 'shot') or ctx.cast('seq13', 'recent'); ex = ctx.ex(eid); u = t - T0
    big, _ = kit.hero_frame(ctx, eid, u, zoom=(1.0, 1.06), dur=T1 - T0); c = big.copy(); G.gradient_v(c, 760, H, 0, .62)
    ta = 1 - ease_out(prog(t, T_TXT_OUT, T_TXT_OUT + .35))
    if u < .5: c = G.scale_about(c, 1 + .02 * (1 - u / .5))
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=2026, t=t, alpha=.85 * ta)
    lines = ctx.cast('seq14', 'lines') or [['FROM MELTING PIXELS', 'white'], ['TO MOVING WORLDS.', 'volt']]
    size = min(kit.fit_size(tx, 'display', 176, W - 2 * MARGIN, -.005) for tx, _ in lines)
    if ta > 0: ui.hero_lines(c, [tx for tx, _ in lines], MARGIN, 820, size, [VOLT if col == 'volt' else WHITE for _, col in lines], T_TYPE, t, lh=1.02, stagger=.5, dur=.65, alpha=ta)
    cr = ctx.cast('seq14', 'credit')
    for k, ln in enumerate([cr] if isinstance(cr, str) else (cr or [])):
        if ta > 0: G.draw_text(c, ln, 'monor', kit.fit_size(ln, 'monor', 17, W - 2 * MARGIN, .03, 12), MARGIN, 1472 + 26 * k, (200, 196, 186), alpha=ta * ease_out(prog(t, T_TYPE + 1.2 + .2 * k, T_TYPE + 1.7 + .2 * k)), track=.03)
    if ta > 0: ui.source_label(c, ex.label, MARGIN, 1440, alpha=ta * ease_out(prog(t, T0 + .3, T0 + .7)))
    return c


def render(ctx, t):
    c = _shot(ctx, t)
    if t >= T_SH0:
        e = ease_io5(prog(t, T_SH0, T_SH1)); px, py, pw, ph = _target(ctx); X0, Y0, X1, Y1 = lerp(0, px, e), lerp(0, py, e), lerp(W, px + pw, e), lerp(H, py + ph, e)
        rw, rh = max(2, int(X1 - X0)), max(2, int(Y1 - Y0)); img = kit.window_from(c, X0, Y0, X1, Y1, 1.0); c2 = G.new_canvas()
        G.shadow_rect(c2, X0, Y0, X1 - X0, Y1 - Y0, alpha=.5 * e); G.paste_masked(c2, img, int(X0), int(Y0), G.round_mask(rw, rh, int(lerp(0, 6, e)))); c = c2
    if t >= T_XF0:
        w = ease_io(prog(t, T_XF0, T_XF1)); b = S1.render(ctx, 0.0); c = (c.astype(np.float32) * (1 - w) + b.astype(np.float32) * w).astype(np.uint8)
    return c


def events(ctx):
    return [('impact', T0, dict(size=.9, ungated=True)), ('type_hit', T_TYPE + .1, dict(size=1.0)), ('type_hit', T_TYPE + .6, dict(size=1.0)), ('lock', T_TYPE + 1.1, dict(size=.8)),
            ('whoosh', T_SH0 - .05, dict(dur=.9, gain=.8)), ('tape_stop', T_XF0 - .05, dict(dur=.7)), ('lock', T_XF1, dict(size=.6, f=1174.66))]

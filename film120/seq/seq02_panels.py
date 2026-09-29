"""SEQUENCE 3 (film numbering) - Footage arranged inside animated editorial panels (S2: 8-16 s).
Cast (plan.cast.seq02): panels = [excerpt ids of EARLY clips] (4-6).  Framed panels slide into a staggered three-row collage (left / right / left) with anticipation and settle, live for ~3.7 s each and exit
in their direction of travel; a giant ghost word (serif italic) sits behind; the Spine grows from scattered frame fragments into a continuous line.  cues: s2.ghost = [[t, word], ...]."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'panels'
STYLE = 'early'
T0, T1 = 8.0, 16.0
PW, PH = 780, 372
ROW_Y = [290, 655, 1020]
LIFE = 3.7; STEP = 1.12; ENTER = .62; EXIT = .5


def _slots(ctx):
    ids = list(ctx.cast('seq02', 'panels', [])) or []
    out = []
    for k, eid in enumerate(ids):
        row = k % 3; side = 'L' if row % 2 == 0 else 'R'; te = T0 + .15 + k * STEP
        x_rest = MARGIN if side == 'L' else W - MARGIN - PW
        out.append(dict(k=k, eid=eid, row=row, side=side, te=te, tx=te + LIFE, x_rest=x_rest, y=ROW_Y[row]))
    return out


def render(ctx, t):
    c = G.new_canvas()
    ghosts = ctx.cue('s2.ghost') or [[T0 + .4, 'flicker'], [T0 + 3.4, 'melted'], [T0 + 6.0, 'drift']]
    cur = None
    for gt, gw in ghosts:
        if t >= gt: cur = (gt, gw)
    if cur:
        gt, gw = cur; e = kinetic((t - gt) / .8); a = G.text_rgba(gw, 'serif_i', 500, WHITE, track=-.02, pad=4); a = G.alpha_mul(a, .09 * clamp((t - gt) / .3))
        G.paste(c, a, (W - a.shape[1]) / 2 + (1 - e) * 140, 520)
    ui.spine(c, reveal=prog(t, T0, T0 + 6.5), crack=max(0, 1 - prog(t, T0 + .5, T0 + 7)), years=[y for y in range(2016, 2023) if t > T0 + (y - 2016) * .7], t=t, alpha=.9)
    ui.frame_icons(c, SPINE_Y, MARGIN, W - MARGIN, 22, prog(t, T0, T0 + 6.5), alpha=.8)
    for p in _slots(ctx):
        if t < p['te'] - .05 or t > p['tx'] + EXIT + .05: continue
        ein = kinetic((t - p['te']) / ENTER); eout = ease_io((t - p['tx']) / EXIT)
        dirn = -1 if p['side'] == 'L' else 1
        x = lerp(p['x_rest'] - dirn * (W * .9), p['x_rest'], clamp(ein, 0, 1.06)) + dirn * (eout * W * .95) if t < p['tx'] else p['x_rest'] + dirn * eout * W * .95
        u = max(0.0, t - p['te']); img, ex = kit.panel_image(ctx, p['eid'], u, PW, PH, loop=True); img = kit.early_grade(img)
        vel = abs(x - p['x_rest']); img = G.motion_blur_h(np.ascontiguousarray(img), int(min(28, vel / 40))) if vel > 60 else img
        y = p['y'] + (PH - img.shape[0]) / 2; px, py, pw, ph = ui.panel(c, img, x, y, alpha=clamp(ein * 3))
        kit.place_label(c, ex, px, py, pw, ph, alpha=clamp(1 - abs(x - p['x_rest']) / 260), size=20)
    return c


def events(ctx):
    ev = []
    for p in _slots(ctx):
        if p['te'] < T1: ev.append(('slide', p['te'] + .05, dict(dur=.6, gain=.8)))
    ev += [('jump', T0 + 5.9, dict(dur=.7))]
    return ev

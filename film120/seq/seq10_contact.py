"""SEQUENCE 9 - Contact sheet of model examples that expands into hero shots (S6: 83-90 s).
Cast (plan.cast.seq10): tiles = [12 excerpt ids] (3 x 4, different families/years), hero_tile = index of the tile that expands, sheet_year_labels optional.
The sheet plays (each tile is a live excerpt with year plate), the camera pushes into one tile which grows to a full hero frame (the first hero of seq11).  cues: s10.expand = t."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'contact'
STYLE = 'now'
T0, T1 = 83.0, 90.0
HERO_T0 = T0 + .1                    # the hero tile plays from here without looping; seq11's first hero continues the same clip time (needs >= ~10.5 s of footage)
TW, TH = 304, 210
GX, GY = 20, 20


def _tiles(ctx): return list(ctx.cast('seq10', 'tiles', [])) or []


def render(ctx, t):
    c = G.new_canvas(); ids = _tiles(ctx); u = t - T0
    if not ids: return c
    t_exp = ctx.cue('s10.expand', T0 + 3.4); hero = ctx.cast('seq10', 'hero_tile', 5); cols, rows = 3, 4
    x0 = (W - (cols * TW + (cols - 1) * GX)) // 2; y0 = 376
    e_exp = ease_io(prog(t, t_exp, t_exp + .9)); title = 'TODAY: MANY FAMILIES, MANY LOOKS'
    ui.spine(c, reveal=1.0, years=range(2016, 2027), t=t, alpha=.7 * (1 - e_exp))
    G.draw_text(c, title, 'display', kit.fit_size(title, 'display', 84, W - 2 * MARGIN, -.005), MARGIN, 250, WHITE, alpha=clamp(u / .5) * (1 - e_exp), track=-.005)
    hero_draw = None
    for k, eid in enumerate(ids[:12]):
        r, cc = divmod(k, cols); ex = ctx.ex(eid); e = kinetic((u - .1 - (k % cols) * .07 - r * .09) / .5)
        if e <= 0: continue
        tx = x0 + cc * (TW + GX); ty = y0 + r * (TH + GY) + (1 - clamp(e, 0, 1.05)) * 80; al = clamp(e * 2)
        if k == hero:
            hero_draw = (eid, tx, ty, al)                                  # drawn last so it grows over its neighbours
        else:
            img = kit.tile_image(ctx, eid, max(0.0, t - T0 - k * .11), TW, TH); img = kit.early_grade(img, 1.0 if int(ex.label.get('year', '2025') or 2025) < 2024 else 0.0)
            ui.panel(c, img, tx, ty, alpha=al * (1 - e_exp * .85), shadow=False, ticks=False)
        G.draw_text(c, ex.label.get('year', ''), 'mono', 20, tx + 10, ty + 8, WHITE, alpha=al * (1 - e_exp), track=.04, shadow=4)
        G.draw_text(c, ex.label.get('model', '').upper(), 'monor', 16, tx + 10, ty + TH - 28, (236, 232, 222), alpha=al * (1 - e_exp), track=.03, shadow=4)
    if hero_draw:
        eid, tx, ty, al = hero_draw; big, mode = kit.hero_frame(ctx, eid, max(0.0, t - HERO_T0), dur=T1 - T0 + 3)
        X0, Y0, X1, Y1 = lerp(tx, 0, e_exp), lerp(ty, 0, e_exp), lerp(tx + TW, W, e_exp), lerp(ty + TH, H, e_exp)
        rw, rh = max(2, int(X1 - X0)), max(2, int(Y1 - Y0)); a_ = kit.tile_image(ctx, eid, max(0.0, t - HERO_T0), rw, rh, loop=False, max_h=720); b_ = kit.window_from(big, X0, Y0, X1, Y1, lerp(.36, 1.0, e_exp)); mx = ease_io(prog(e_exp, .5, 1.0))
        img = a_ if mx <= 0 else (a_.astype(np.float32) * (1 - mx) + b_.astype(np.float32) * mx).astype(np.uint8)
        if e_exp < .02: ui.panel(c, img, int(tx), int(ty), alpha=al, shadow=False, ticks=False)
        else:
            G.shadow_rect(c, X0, Y0, X1 - X0, Y1 - Y0, alpha=.5 * (1 - e_exp)); G.paste_masked(c, img, int(X0), int(Y0), G.round_mask(img.shape[1], img.shape[0], max(0, int(lerp(6, 0, e_exp)))))
    if e_exp > .8: G.gradient_v(c, 1100, H, 0, .5 * e_exp)
    return c


def events(ctx):
    t_exp = ctx.cue('s10.expand', T0 + 3.4)
    return [('slide', T0 + .1, dict(dur=.8, gain=.8)), ('riser', t_exp - .9, dict(dur=.9)), ('impact', t_exp + .55, dict(size=.6)), ('lock', t_exp + .9, dict(size=.8))]

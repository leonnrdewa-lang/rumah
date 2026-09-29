"""SEQUENCE 12 - Final visual callback (S7: 110-115 s).
Cast (plan.cast.seq13): early = the excerpt the film OPENED on (seq01.early), recent = an exceptional recent clip (>= 4.5 s, same as seq01.recent), peak_lines = optional [[text, 'white'|'volt'], ...] hero type for the peak.
110.0-110.8  the montage wall collapses into a point (volt)
110.8-113.2  the point opens into two matched panels (same geometry, year plates, volt divider, ILLUSTRATIVE tag): the opening clip above, the recent clip below
113.2-113.95 the divider sweeps: the recent panel expands to full-bleed while the opening clip slides away (the peak); 113.95 white flash, hero type
NAME = 'callback'."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, ease_io5, kinetic
from seq import seq12_montage as M

NAME = 'callback'
STYLE = 'now'
T0, T1 = 110.0, 115.0
T_COL1, T_OPEN, T_PEAK0, T_PEAK1 = 110.8, 110.85, 113.2, 113.95
PW, PH = 853, 480
PX = (W - PW) // 2; Y_TOP = 262; Y_BOT = Y_TOP + PH + 40
CX, CY = M.CX, M.CY


def _blit(c, img, cx, cy, s, alpha):
    h, w = img.shape[:2]; sw, sh = max(2, int(w * s)), max(2, int(h * s)); im = G.rs(img, sw, sh) if (sw, sh) != (w, h) else img
    G.paste_masked(c, im, int(cx - sw / 2), int(cy - sh / 2), G.round_mask(sw, sh, 6), alpha)


def _plate(c, ex, x, y, w, h, alpha, col, slide):
    txt = str(ex.label.get('year', '')); size = 92; tw = G.text_w(txt, 'display', size, .0); px, py = kit.free_corner(ex, x, y, w, h, tw + 24, int(size * 1.05), order=('tl', 'tr', 'bl', 'br'), pad=10)
    G.draw_text(c, txt, 'display', size, px + 8 - slide, py - 4, col, alpha=alpha, shadow=6)


def render(ctx, t):
    if t < T_COL1: return M.montage(ctx, t, collapse=prog(t, T0, T_COL1))
    early, recent = ctx.cast('seq13', 'early'), ctx.cast('seq13', 'recent'); ex_e, ex_r = ctx.ex(early), ctx.ex(recent); u = max(0.0, t - T_OPEN)
    e5 = ease_io5(prog(t, T_PEAK0, T_PEAK1)); c = G.new_canvas(); yr = ex_r.label.get('year', ''); hl = int(yr) if str(yr).isdigit() else None
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=hl, t=t, alpha=.75 * (1 - e5))
    # ---- opening clip (top)
    if e5 < 1:
        ke = kinetic((t - T_OPEN) / .5); ye = lerp(CY, Y_TOP + PH / 2, ease_out(prog(t, T_OPEN, T_OPEN + .4))) - e5 * (Y_TOP + PH + 80); s = lerp(.05, 1.0, clamp(ke, 0, 1.05))
        img = kit.early_grade(kit.tile_image(ctx, early, u, PW, PH, max_h=540), 1.0); al = clamp(ke * 2.4) * (1 - e5 * e5)
        _blit(c, img, lerp(CX, W / 2, ease_out(prog(t, T_OPEN, T_OPEN + .4))), ye, s, al)
        if ke > .85:
            a2 = ease_out(prog(t, T_OPEN + .45, T_OPEN + .8)) * (1 - e5); ex, ry = ex_e, ye - PH / 2
            _plate(c, ex, PX, ry, PW, PH, a2, WHITE, (1 - a2) * 40); kit.place_label(c, ex, PX, ry, PW, PH, alpha=a2, size=20)
    # ---- recent clip (bottom -> peak)
    ke = kinetic((t - T_OPEN - .12) / .5); pe = ease_out(prog(t, T_OPEN + .12, T_OPEN + .52))
    if e5 <= 0:
        s = lerp(.05, 1.0, clamp(ke, 0, 1.05)); img = kit.tile_image(ctx, recent, u, PW, PH, max_h=540)
        _blit(c, img, lerp(CX, W / 2, pe), lerp(CY, Y_BOT + PH / 2, pe), s, clamp(ke * 2.4))
    else:
        X0, Y0, X1, Y1 = lerp(PX, 0, e5), lerp(Y_BOT, 0, e5), lerp(PX + PW, W, e5), lerp(Y_BOT + PH, H, e5)
        big, _ = kit.hero_frame(ctx, recent, u, zoom=(1.0, 1.06), dur=T1 - T_OPEN + .5); rw, rh = max(2, int(X1 - X0)), max(2, int(Y1 - Y0))
        a_ = kit.tile_image(ctx, recent, u, rw, rh, max_h=720); b_ = kit.window_from(big, X0, Y0, X1, Y1, lerp(.8, 1.0, e5)); mx = ease_io(prog(e5, .5, 1.0))
        img = a_ if mx <= 0 else (a_.astype(np.float32) * (1 - mx) + b_.astype(np.float32) * mx).astype(np.uint8)
        G.shadow_rect(c, X0, Y0, X1 - X0, Y1 - Y0, alpha=.5 * (1 - e5)); G.paste_masked(c, img, int(X0), int(Y0), G.round_mask(rw, rh, max(0, int(lerp(6, 0, e5)))))
        G.fill_rect(c, X0, Y0 - 3, X1 - X0, 3, VOLT, 1 - e5)          # the divider travels with the growing panel
    ry = lerp(Y_BOT, 0, e5)
    if e5 < .6 and ke > .85:
        a2 = ease_out(prog(t, T_OPEN + .6, T_OPEN + .95)) * (1 - e5 / .6)
        _plate(c, ex_r, PX, Y_BOT, PW, PH, a2, VOLT, (1 - a2) * 40); kit.place_label(c, ex_r, PX, Y_BOT, PW, PH, alpha=a2, size=20)
    # ---- divider + honest tag in the gap
    if ke > .5 and e5 < 1:
        dy = Y_TOP + PH + 20; a3 = ease_out(prog(t, T_OPEN + .5, T_OPEN + .9)) * (1 - clamp(e5 * 4))
        G.fill_rect(c, PX, dy - 1, PW * ease_out(prog(t, T_OPEN + .5, T_OPEN + 1.0)), 2, VOLT, a3)
        ui.chip(c, 'ILLUSTRATIVE · DIFFERENT PROMPTS', W // 2, dy - 15, 17, anchor='c', alpha=a3, dot=VOLT, bga=1.0)
    # ---- the peak
    if t >= T_PEAK1 - .02:
        d = t - T_PEAK1
        if d < .3: c = G.flash(c, .55 * (1 - d / .3))
        if d < .4: c = G.scale_about(c, 1 + .03 * (1 - d / .4) ** 2)
        G.gradient_v(c, 900, H, 0, .6)
        lines = ctx.cast('seq13', 'peak_lines') or []
        if lines:
            size = min(kit.fit_size(tx, 'display', 168, W - 2 * MARGIN, -.005) for tx, _ in lines)
            ui.hero_lines(c, [tx for tx, _ in lines], MARGIN, 760, size, [VOLT if col == 'volt' else WHITE for _, col in lines], T_PEAK1 + .12, t, lh=1.0, stagger=.25)
        ui.spine(c, reveal=1.0, years=(), t=t, alpha=.35); G.fill_rect(c, MARGIN, SPINE_Y - 1, (W - 2 * MARGIN) * clamp((t - T_PEAK1) / (T1 - T_PEAK1)), 4, VOLT, .9)
        ui.source_label(c, ex_r.label, MARGIN, 1440, alpha=ease_out(prog(t, T_PEAK1 + .3, T_PEAK1 + .7)))
    return c


def events(ctx):
    return [('whoosh', T0 - .05, dict(dur=.8, gain=.9)), ('sub_drop', T_COL1 - .05, dict(dur=1.4)), ('lock', T_OPEN + .05, dict(size=.8)), ('lock', T_OPEN + .2, dict(size=.7, f=1568.0)),
            ('data_blip', T_OPEN + .55, dict(f=2000.0)), ('data_blip', T_OPEN + .75, dict(f=2600.0)),
            ('riser', T_PEAK0 - .5, dict(dur=.5 + (T_PEAK1 - T_PEAK0))), ('slide', T_PEAK0, dict(dur=.75, gain=.9)),
            ('impact', T_PEAK1, dict(size=1.25, ungated=True)), ('type_hit', T_PEAK1 + .12, dict(size=1.0)), ('type_hit', T_PEAK1 + .37, dict(size=.9))]

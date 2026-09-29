"""SEQUENCE 11 - Multi-panel montage on the beat grid (S7: 104-110 s).
Cast (plan.cast.seq12): panels = [10 excerpt ids] (bento layout, row-major), swaps = [up to 8 excerpt ids] that replace panels on the late beats.
104.0-104.6  the Spine collapses into a point, drops to the centre and detonates on beat 1 (104.6 s)
104.6-107.0  10 panels burst out from the point, two per beat (beat = 0.6 s, the drums start at 104.0 so the grid is 104.0 + 0.6 k)
107.6-109.4  panels swap content on the beats; every beat the panel outlines pulse; the Spine is the metronome (one tick per beat)
NAME = 'montage'.  montage(ctx, t, collapse) is reused by seq13 to collapse the wall."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'montage'
STYLE = 'now'
T0, T1 = 104.0, 110.0
BEAT = 0.6
CX, CY = W // 2, 740
AX, AY, GAP = 64, 262, 12
ROWS = [(236, [464, 476]), (236, [296, 296, 336]), (236, [476, 464]), (236, [296, 336, 296])]
ENTRY = [(0, 5), (3, 8), (1, 6), (4, 9), (2, 7)]                 # panel indices entering on beats 1..5
SWAP_AT = [(6, (2, 7)), (7, (0, 9)), (8, (4, 5)), (9, (1, 3))]  # (beat, panel indices) that swap content


def rects():
    out = []; y = AY
    for h, ws in ROWS:
        x = AX
        for w in ws: out.append((x, y, w, h)); x += w + GAP
        y += h + GAP
    return out


def beat_t(k): return T0 + BEAT * k


def entry_time(k):
    for b, pair in enumerate(ENTRY, 1):
        if k in pair: return beat_t(b)
    return beat_t(5)


def content(ctx, k, t):
    """(excerpt id, local time origin) that panel k shows at time t."""
    panels = list(ctx.cast('seq12', 'panels', [])); swaps = list(ctx.cast('seq12', 'swaps', [])); eid = panels[k % len(panels)]; o = entry_time(k)
    slots = [(b, k2) for b, pair in SWAP_AT for k2 in pair]
    for i, (b, k2) in enumerate(slots):
        if k2 == k and swaps and t >= beat_t(b): eid, o = swaps[i % len(swaps)], beat_t(b)
    return eid, o


def _spine(c, t, alpha=1.0):
    x0, x1 = MARGIN, W - MARGIN; y = SPINE_Y
    if t < beat_t(1) - .3:                                             # the line collapses into a point at its centre
        p = ease_io(prog(t, T0, T0 + .35)); hw = (x1 - x0) / 2 * (1 - p); G.fill_rect(c, CX - hw, y - 1, 2 * hw, 3, WHITE, .8 * (1 - p * .3))
        return
    g = ease_out(prog(t, beat_t(1), beat_t(1) + .5)); hw = (x1 - x0) / 2 * g
    if hw < 2: return
    G.fill_rect(c, CX - hw, y - 1, 2 * hw, 2, WHITE, .35 * alpha)
    for b in range(0, 11):
        xb = x0 + (x1 - x0) * b / 10
        if abs(xb - CX) > hw: continue
        passed = t >= beat_t(b); age = t - beat_t(b)
        if passed and 0 <= age < .16: G.fill_rect(c, xb - 2, y - 26, 4, 52, VOLT, 1.0 - age / .16 * .3)
        else: G.fill_rect(c, xb - 1, y - (12 if passed else 7), 2, 24 if passed else 14, VOLT if passed else WHITE, .9 if passed else .4)
    nb = int(np.floor((t - T0) / BEAT))
    if nb >= 0:
        age = (t - T0) - nb * BEAT
        if age < .14: G.fill_rect(c, 0, 0, W, 6, VOLT, .5 * (1 - age / .14))


def montage(ctx, t, collapse=0.0, alpha_all=1.0):
    c = G.new_canvas(); R = rects(); panels = list(ctx.cast('seq12', 'panels', []))
    if not panels: return c
    _spine(c, t)
    if t < beat_t(1):                                                  # the point: drops to the centre, swells, detonates
        a = ease_io(prog(t, T0 + .3, T0 + .62)); y = lerp(SPINE_Y, CY, a); r = lerp(5, 26, kinetic(prog(t, T0 + .55, beat_t(1)) )) if t > T0 + .55 else 5
        gl = clamp(prog(t, T0 + .3, beat_t(1)))
        G.vector(c, lambda d, ss, ox, oy: d.ellipse([(CX - r - ox) * ss, (y - r - oy) * ss, (CX + r - ox) * ss, (y + r - oy) * ss], fill=VOLT + (255,)), bbox=(CX - 60, y - 60, 120, 120))
        return c
    since = t - beat_t(1)
    if since < .5:                                                     # shock ring
        k = ease_out(since / .5); rr = 30 + 700 * k; a = (1 - k) * .8
        G.vector(c, lambda d, ss, ox, oy: d.ellipse([(CX - rr - ox) * ss, (CY - rr - oy) * ss, (CX + rr - ox) * ss, (CY + rr - oy) * ss], outline=VOLT + (int(255 * a),), width=int(3 * ss)), bbox=(CX - rr - 8, CY - rr - 8, 2 * rr + 16, 2 * rr + 16))
    order = sorted(range(len(R)), key=lambda k: entry_time(k))
    for k in order:
        te = entry_time(k)
        if t < te - 1e-6: continue
        x, y, w, h = R[k]; eid, o = content(ctx, k, t); e = kinetic((t - te) / .42); ep = ease_out(prog(t, te, te + .34))
        img = kit.tile_image(ctx, eid, max(0.0, t - o) + k * .13, w, h, max_h=540); s = lerp(.30, 1.0, clamp(e, 0, 1.06))
        pcx, pcy = lerp(CX, x + w / 2, ep), lerp(CY, y + h / 2, ep)
        # collapse (seq13): everything is drawn into the centre point
        if collapse > 0:
            q = ease_io(collapse); pcx, pcy = lerp(pcx, CX, q), lerp(pcy, CY, q); s *= lerp(1, .04, q)
        sw, sh = max(2, int(w * s)), max(2, int(h * s)); im = G.rs(img, sw, sh) if (sw, sh) != (w, h) else img
        al = clamp(e * 2.4) * alpha_all * (1 - clamp(collapse * 1.15) ** 2)
        if collapse == 0 and t - te < .12 and ep < 1:                    # short trail while flying in
            G.paste_masked(c, im, int(lerp(CX, pcx, .55) - sw / 2), int(lerp(CY, pcy, .55) - sh / 2), G.round_mask(sw, sh, 6), .28 * al)
        G.paste_masked(c, im, int(pcx - sw / 2), int(pcy - sh / 2), G.round_mask(sw, sh, 6), al)
        if collapse == 0:
            ex = ctx.ex(eid); age = (t - T0) % BEAT
            pulse = np.exp(-age / .06) * (.9 if t > beat_t(1) + .3 else .0); sw_age = t - o
            if o > te + .1 and sw_age < .1: G.fill_rect(c, x, y, w, h, WHITE, .35 * (1 - sw_age / .1))      # swap cut flash
            if pulse > .02:
                for (rx, ry, rw, rh) in ((x, y, w, 3), (x, y + h - 3, w, 3), (x, y, 3, h), (x + w - 3, y, 3, h)): G.fill_rect(c, rx, ry, rw, rh, VOLT, pulse)
            if e > .8: kit.place_label(c, ex, x, y, w, h, alpha=ease_out(prog(t - te, .3, .6)), size=15)
    return c


def render(ctx, t): return montage(ctx, t)


def events(ctx):
    ev = [('riser', T0 - 1.2, dict(dur=1.75)), ('sub_drop', beat_t(1) - .02, dict(dur=1.8)), ('impact', beat_t(1), dict(size=1.15)), ('lock', beat_t(1) + .02, dict(size=.9, f=1320.0))]
    for b in range(0, 11): ev.append(('tick_hi', beat_t(b), {}))
    for b in range(1, 6): ev.append(('whoosh', beat_t(b) - .05, dict(dur=.32, gain=.55)))
    for b, _ in SWAP_AT: ev.append(('data_blip', beat_t(b), dict(f=1800.0 + 160 * b)))
    ev.append(('riser', beat_t(8), dict(dur=BEAT * 2)))
    return ev

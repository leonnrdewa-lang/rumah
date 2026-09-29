"""SEQUENCE 1 - Explosive before/after hook (0-8 s).
Cast (data/edit_plan.json -> cast.seq01): early = excerpt id of a GENUINE early, visibly unstable clip (>= 3 s); recent = excerpt id of an exceptional recent clip (>= 4.5 s).
0.0-2.9   the early clip plays in a framed panel; THIS WAS / AI VIDEO.; a tracked annotation locks onto the most unstable region (measured from the pixels)
2.9-3.44  FREEZE on the revealing frame, all sound gated out
3.44-3.5  white flash; 3.5 smash cut: the panel opens to full-bleed and the content becomes the recent clip; LOOK HOW FAR / it has come.
NAME = 'hook'."""
import numpy as np
from engine import gfx as G, ui, kit, tracker
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'hook'
T_FREEZE, T_FLASH, T_CUT, T_END = 2.9, 3.44, 3.5, 8.0
SUBS = False
STYLE = lambda t: 'early' if t < T_CUT else 'now'


def _annotation(ctx, early):
    if 'hook_ann' in ctx.cache: return ctx.cache['hook_ann']
    fps = 12; frames = [early.frame(k / fps, max_h=360, loop=True) for k in range(int(T_FREEZE * fps) + 1)]
    b0 = tracker.most_unstable_box(frames[int(.7 * fps):]) or (.35, .25, .3, .4)
    k0 = int(1.0 * fps); tr = tracker.block_track(frames[k0:], b0, search=5, grid=96)
    ctx.cache['hook_ann'] = dict(fps=fps, k0=k0, boxes=tr, box0=b0, resid=tracker.residual_change(frames), meta=early.clip); return ctx.cache['hook_ann']


def _early(ctx, t):
    early = ctx.cast_ex('seq01', 'early'); c = G.new_canvas()
    ui.spine(c, reveal=prog(t, 0, .9), crack=1.0 - .3 * prog(t, 1.5, T_FREEZE), years=range(2016, 2027), t=t, alpha=.9)
    ui.hero_lines(c, ['THIS WAS', 'AI VIDEO.'], MARGIN, 262, 200, [WHITE, VOLT], .12, t, lh=1.0, stagger=.22)
    frozen = t >= T_FREEZE; u = min(t, T_FREEZE); fr = early.frame(u, loop=True, max_h=720)
    zoom = 1.0 + (.045 * ease_out(prog(t, T_FREEZE, T_FLASH)) if frozen else 0)
    img, _ = G.fit_inside(fr, W - 2 * 24, 700); img = kit.early_grade(img)
    if zoom > 1: img = G.scale_about(img, zoom, .5, .5)
    if frozen and t < T_FLASH: img = G.chroma(img, int(7 * ease_out(prog(t, T_FREEZE, T_FREEZE + .12))))
    px = (W - img.shape[1]) // 2; py = 790; x, y, w, h = ui.panel(c, img, px, py)
    m = early.clip
    if t >= 1.1:
        ann = _annotation(ctx, early)
        kk = int(clamp((min(t, T_FREEZE) - 1.0) * ann['fps'], 0, len(ann['boxes']) - 1)); bx, by, bw, bh = ann['boxes'][kk]
        e = kinetic(prog(t, 1.1, 1.75)); s = lerp(2.3, 1.0, ease_out(prog(t, 1.1, 1.6)))                 # reticle closes in on the target
        cx, cy = x + (bx + bw / 2) * w, y + (by + bh / 2) * h; rw, rh = max(90, bw * w) * s, max(90, bh * h) * s
        ui_reticle(c, cx - rw / 2, cy - rh / 2, rw, rh, VOLT, min(1, e * 1.4))
        if t > 1.5:                                                            # leader line + label
            lx, ly = (x + w - 40, y - 78) if cx > x + w / 2 else (x + 40, y - 78); a = ease_out(prog(t, 1.5, 1.9))
            G.vector(c, lambda d, ss, ox, oy: G.line(d, ss, ox, oy, [(cx, cy - rh / 2), (cx, ly + 30), (lx, ly + 30)], VOLT, 2, int(255 * a)), bbox=(min(cx, lx) - 4, ly + 20, abs(cx - lx) + 8, cy - rh / 2 - ly - 16))
            ui.chip(c, 'TRACKED · MOST UNSTABLE REGION', lx, ly, 22, fg=(10, 10, 10), bg=VOLT, bga=1.0, anchor='r' if cx > x + w / 2 else 'l', alpha=a)
    G.draw_text(c, f"{m['width']}×{m['height']} · {m['fps']:g} FPS · {early.dur:.1f} S CLIP", 'monor', 22, x + w, y + h + 74, (200, 196, 186), anchor='r', track=.05, alpha=ease_out(prog(t, .6, 1.0)))
    ui.source_label(c, early.label, x, y + h + 22, alpha=ease_out(prog(t, .4, .9)))
    if frozen:
        ui.chip(c, f'FREEZE · FRAME {int(u * early.clip["fps"]) + 1}', W // 2, y + h - 62, 22, fg=WHITE, bg=(8, 8, 9), bga=.85, anchor='c', dot=VOLT, alpha=ease_out(prog(t, T_FREEZE, T_FREEZE + .1)))
    return c


def ui_reticle(c, x, y, w, h, col, a):
    L = min(w, h) * .26
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        G.fill_rect(c, px if dx > 0 else px - L, py - 2, L, 4, col, a); G.fill_rect(c, px - 2, py if dy > 0 else py - L, 4, L, col, a)


def _recent(ctx, t):
    rid = ctx.cast('seq01', 'recent'); rex = ctx.ex(rid); u = max(0.0, t - T_CUT)
    img, mode = kit.hero_frame(ctx, rid, u, zoom=(1.0, 1.10), dur=T_END - T_CUT + .5)
    e = ease_io(prog(t, T_CUT, T_CUT + .34)); c = G.new_canvas()
    # panel opens to full-bleed: clip rectangle grows from the early panel's geometry
    y0 = lerp(790, 0, e); y1 = lerp(790 + 620, H, e); x0 = lerp(24, 0, e); x1 = lerp(W - 24, W, e)
    mask = np.zeros((H, W), np.float32); mask[int(y0):int(y1), int(x0):int(x1)] = 1.0
    G.paste_masked(c, img, 0, 0, mask)
    if e < 1: c = G.motion_blur_v(c, int(90 * np.sin(np.pi * e)))
    G.gradient_v(c, 980, H, 0, .72)
    ui.spine(c, reveal=1.0, crack=0.0, years=range(2016, 2027), highlight=2025, lock=max(0, 1 - (t - T_CUT) / .6), t=t)
    ui.hero_lines(c, ['LOOK HOW FAR'], MARGIN, 1040, 168, [WHITE], T_CUT + .12, t, slide=80)
    ui.hero_lines(c, ['it has come.'], MARGIN, 1200, 210, [VOLT], T_CUT + .5, t, kind='serif_i', slide=80, track=0)
    ex = rex; ui.source_label(c, ex.label, MARGIN, 1440, alpha=ease_out(prog(t, T_CUT + 1.0, T_CUT + 1.5)))
    d = t - T_CUT
    if d < .35: c = G.chroma(c, int(16 * (1 - d / .35))); c = G.shake(c, np.sin(d * 120) * 18 * (1 - d / .35), np.cos(d * 97) * 12 * (1 - d / .35))
    return c


def render(ctx, t):
    c = _early(ctx, t) if t < T_CUT else _recent(ctx, t)
    if T_FLASH <= t < T_CUT + .06: c = G.flash(c, .95 * (1 - abs(t - (T_CUT - .01)) / .08) if abs(t - (T_CUT - .01)) < .08 else 0)
    return c


def events(ctx):
    return [('tick_hi', .1, {}), ('type_hit', .3, dict(size=.8)), ('type_hit', .55, dict(size=.8)), ('riser', 1.45, dict(dur=1.45)), ('data_blip', 1.15, dict(f=1500)), ('data_blip', 1.7, dict(f=2200)),
            ('freeze', T_FREEZE - .02, dict(dur=.45, ungated=True)), ('shutter', T_FREEZE, dict(ungated=True)), ('gate', T_FREEZE, dict(dur=T_CUT - T_FREEZE - .02)),
            ('impact', T_CUT, dict(size=1.0, ungated=True)), ('lock', T_CUT, dict(ungated=True)), ('type_hit', T_CUT + .12, dict(size=.9)), ('type_hit', T_CUT + .5, dict(size=.7)), ('whoosh', T_END - .5, dict(dur=.5))]

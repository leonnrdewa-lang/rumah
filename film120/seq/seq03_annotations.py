"""SEQUENCE 4 - Tracked annotations of early visual failures (S2: 16-25 s).
Cast (plan.cast.seq03): targets = [ {"ex": excerpt id, "u0": start seconds inside the excerpt, "box": [x,y,w,h] normalised initial target (optional; default = most unstable region measured on the clip),
                                      "zoom": 2.4, "tag": "SHORT LABEL", "note": "what a viewer can check on the page/in the clip"} ... ] (2-3 targets, ~3 s each).
Annotations only state measurable facts (resolution, fps, length, measured frame-to-frame change) or facts stated on the source page.  cues: s3.targets = [t_start, ...]."""
import numpy as np
from PIL import Image
from engine import gfx as G, ui, kit, tracker
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'annotations'
STYLE = 'early'
T0, T1 = 16.0, 25.0
SLOT = 3.0


def _targets(ctx): return list(ctx.cast('seq03', 'targets', [])) or []


def _track(ctx, i, tg):
    k = ('ann', i)
    if k in ctx.cache: return ctx.cache[k]
    ex = ctx.ex(tg['ex']); u0 = tg.get('u0', 0.0); fps = 10; n = int(min(ex.dur - u0, SLOT + .4) * fps); frames = [ex.frame(u0 + j / fps, max_h=360, loop=True) for j in range(max(4, n))]
    box0 = tuple(tg['box']) if tg.get('box') else (tracker.most_unstable_box(frames) or (.35, .25, .3, .4))
    boxes = tracker.block_track(frames, box0, search=5, grid=96)
    ctx.cache[k] = dict(fps=fps, boxes=boxes, resid=tracker.residual_change(frames), flick=tracker.flicker_index(frames), n=len(frames)); return ctx.cache[k]


def _slot_scene(ctx, i, tg, t, ts):
    ex = ctx.ex(tg['ex']); tr = _track(ctx, i, tg); u = t - ts; c = G.new_canvas(); u0 = tg.get('u0', 0.0)
    ui.spine(c, reveal=1.0, crack=max(0, .5 - prog(t, T0, T0 + 3) * .5), years=range(2016, 2027), highlight=None, t=t, alpha=.85)
    fr = ex.frame(u0 + u, loop=True, max_h=720); sh, sw = fr.shape[:2]
    kk = int(clamp(u * tr['fps'], 0, tr['n'] - 1)); bx, by, bw, bh = tr['boxes'][kk]
    zin = kinetic(prog(u, .0, .6)); zoom = lerp(1.0, tg.get('zoom', 2.4), clamp(zin, 0, 1.05))
    # crop window follows the tracked target
    win_w = 952; win_h = 760; aspect = win_w / win_h
    cx, cy = bx + bw / 2, by + bh / 2
    wn = min(1.0, (aspect * sh / sw) / zoom) if sw / sh >= aspect else 1.0 / zoom; hn = wn * sw / sh / aspect
    hn = min(hn, 1.0); wn = min(wn, 1.0); x0 = clamp(cx - wn / 2, 0, 1 - wn); y0 = clamp(cy - hn / 2, 0, 1 - hn)
    crop = fr[int(y0 * sh):int((y0 + hn) * sh), int(x0 * sw):int((x0 + wn) * sw)]; img = kit.early_grade(G.rs(crop, win_w, win_h))
    px, py = MARGIN, 300; x, y, w, h = ui.panel(c, img, px, py)
    # target reticle (in crop coordinates)
    tx = x + ((cx - x0) / wn) * w; ty = y + ((cy - y0) / hn) * h; rw = max(120, bw / wn * w); rh = max(120, bh / hn * h); rw = min(rw, 420); rh = min(rh, 420)
    e = kinetic(prog(u, .5, 1.05)); s = lerp(1.9, 1.0, clamp(e, 0, 1))
    L = min(rw, rh) * s * .28; rx, ry, rW, rH = tx - rw * s / 2, ty - rh * s / 2, rw * s, rh * s
    for (qx, qy, dx, dy) in ((rx, ry, 1, 1), (rx + rW, ry, -1, 1), (rx, ry + rH, 1, -1), (rx + rW, ry + rH, -1, -1)):
        G.fill_rect(c, qx if dx > 0 else qx - L, qy - 2, L, 4, VOLT, clamp(e * 1.5)); G.fill_rect(c, qx - 2, qy if dy > 0 else qy - L, 4, L, VOLT, clamp(e * 1.5))
    # callout
    a = ease_out(prog(u, 1.0, 1.4)); cy2 = y + h + 40
    G.draw_text(c, tg['tag'], 'display', 96, MARGIN, cy2 + 8, WHITE, track=-.005, alpha=a)
    G.draw_text(c, tg.get('note', ''), 'ui', 30, MARGIN, cy2 + 118, (214, 210, 200), alpha=a * .95, track=0)
    m = ex.clip; readout = f"MEASURED ON THIS CLIP · {m['width']}×{m['height']} · {m['fps']:g} FPS · MEAN FRAME-TO-FRAME CHANGE {tr['resid']:.1f}/255"
    G.draw_text(c, readout, 'monor', 19, MARGIN, y - 36, VOLT, track=.04, alpha=a)
    kit.place_label(c, ex, x, y, w, h, alpha=clamp(u * 4), size=20)
    # whole-frame inset with the crop window marked (so the viewer can inspect where the close-up comes from)
    ins_w = 300; ins, _ = G.fit_inside(fr, ins_w, 200); ix, iy = W - MARGIN - ins.shape[1], y + h + 40
    G.paste(c, kit.early_grade(ins), ix, iy, alpha=a); G.fill_rect(c, ix - 2, iy - 2, ins.shape[1] + 4, 2, WHITE, .5 * a); G.fill_rect(c, ix - 2, iy + ins.shape[0], ins.shape[1] + 4, 2, WHITE, .5 * a)
    bx0, by0 = ix + x0 * ins.shape[1], iy + y0 * ins.shape[0]; bw_, bh_ = wn * ins.shape[1], hn * ins.shape[0]
    for (qx, qy, ww, hh) in ((bx0, by0, bw_, 3), (bx0, by0 + bh_, bw_, 3), (bx0, by0, 3, bh_), (bx0 + bw_, by0, 3, bh_)): G.fill_rect(c, qx, qy, ww, hh, VOLT, a)
    G.draw_text(c, 'WHOLE FRAME', 'monor', 17, ix, iy + ins.shape[0] + 8, (200, 196, 186), track=.05, alpha=a)
    ui.chip(c, f'CROP ×{zoom:.1f} · UPSCALED FROM SOURCE', x + w - 12, y + 12, 18, anchor='r', alpha=a, bga=.7)
    return c


def render(ctx, t):
    ts_list = ctx.cue('s3.targets') or [T0 + SLOT * i for i in range(3)]; tgs = _targets(ctx)
    if not tgs: return G.new_canvas()
    i = max(j for j in range(len(tgs)) if t >= ts_list[j] - 1e-6) if t >= ts_list[0] else 0
    c = _slot_scene(ctx, i, tgs[i], t, ts_list[i]); tn = ts_list[i] + SLOT
    if i + 1 < len(tgs) and t > tn - .3:                                              # masked hand-off to the next target
        from engine import transitions as TR
        c = TR.transition('slat_v', c, _slot_scene(ctx, i + 1, tgs[i + 1], t, ts_list[i + 1]), (t - (tn - .3)) / .3)
    return c


def events(ctx):
    ts_list = ctx.cue('s3.targets') or [T0 + SLOT * i for i in range(3)]; ev = []
    for i, tg in enumerate(_targets(ctx)):
        ev += [('data_blip', ts_list[i] + .55, dict(f=1500)), ('lock', ts_list[i] + 1.05, dict(size=.7)), ('type_hit', ts_list[i] + 1.0, dict(size=.6))]
        if i: ev.append(('slide', ts_list[i] - .25, dict(dur=.35)))
    return ev

"""SEQUENCE 8 - Animated diagrams explaining camera and motion control (S5: 63-75 s).
Cast (plan.cast.seq08): items = [ {"type": "i2v" | "keyframes" | "camera" | "refs" | "edit", "ex": excerpt id (+ "ex2", "refs": [excerpt ids]), "title": "START FROM AN IMAGE", "product": "RUNWAY GEN-2", "date": "2023",
                                    "note": "plain sentence, verified", "path": "dolly|orbit|crane|pan" (camera), "src": "short source tag"} ... ] (2-3 items, ~4 s each).
Every diagram is drawn over REAL example footage from the plan; the diagram is explanatory graphics (labelled ILLUSTRATIVE) and only features/dates verified in data/research are used.  cues: s8.items = [t0, ...]."""
import math
import numpy as np
from engine import gfx as G, ui, kit, transitions as TR
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'control'
STYLE = 'now'
T0, T1 = 63.0, 72.0


def _items(ctx): return list(ctx.cast('seq08', 'items', [])) or []


def _starts(ctx, n):
    ts = ctx.cue('s8.items')
    if ts and len(ts) >= n: return ts[:n]
    span = (T1 - T0 - .2) / max(1, n); return [T0 + .1 + i * span for i in range(n)]


def _header(c, it, u):
    a = kinetic(u / .6)
    G.draw_text(c, it['title'], 'display', 118, MARGIN, 262 + (1 - clamp(a)) * 40, WHITE, alpha=clamp(a * 3), track=-.005)
    ui.chip(c, f"{it.get('product', '')} · {it.get('date', '')}", MARGIN, 262 + 138, 22, dot=VOLT, alpha=clamp((u - .25) / .3)) if it.get('product') else None
    if it.get('note'): G.draw_text(c, it['note'], 'ui', 30, MARGIN, 262 + 196, (222, 218, 208), alpha=clamp((u - .4) / .3))


def _cam_path(kind, n=60):
    s = np.linspace(0, 1, n)
    if kind == 'orbit': ang = np.radians(-70 + 140 * s); return np.stack([np.sin(ang), .45 - .45 * np.cos(ang)], 1)
    if kind == 'crane': return np.stack([-.8 + 1.6 * s, .8 - 1.7 * s ** 2 + .3 * np.sin(s * 3)], 1) * np.array([1, .9])
    if kind == 'pan': return np.stack([-.9 + 1.8 * s, .1 * np.sin(s * 4)], 1)
    return np.stack([.35 * np.sin(s * 5), .9 - 1.8 * s], 1)                       # dolly in


def _diagram_camera(c, ctx, it, u):
    ex = ctx.ex(it['ex']); img, _ = G.fit_inside(ex.frame(u, loop=True, max_h=1080), 952, 560); x0, y0 = MARGIN + (952 - img.shape[1]) // 2, 560
    x, y, w, h = ui.panel(c, img, x0, y0); kit.place_label(c, ex, x, y, w, h, size=20)
    pts = _cam_path(it.get('path', 'dolly')); px = x + w / 2 + pts[:, 0] * w * .36; py = y + h / 2 + pts[:, 1] * h * .36
    k = ease_io(prog(u, .5, 3.3)); n = max(2, int(len(pts) * k)); path = list(zip(px[:n], py[:n]))
    G.vector(c, lambda d, ss, ox, oy: G.line(d, ss, ox, oy, path, VOLT, 5, 255), bbox=(x, y, w, h), ss=2)
    # camera icon rides the path and points along it
    cx, cy = path[-1]; ang = math.atan2(path[-1][1] - path[max(0, len(path) - 4)][1], path[-1][0] - path[max(0, len(path) - 4)][0]) if len(path) > 4 else 0
    r = 22; body = [(cx + r * math.cos(ang + a), cy + r * math.sin(ang + a)) for a in (2.6, 3.7, -0.55, 0.55)]
    G.vector(c, lambda d, ss, ox, oy: (d.polygon([((qx - ox) * ss, (qy - oy) * ss) for qx, qy in body], fill=VOLT + (255,)), d.ellipse([((cx + 30 * math.cos(ang) - 9 - ox) * ss, (cy + 30 * math.sin(ang) - 9 - oy) * ss), ((cx + 30 * math.cos(ang) + 9 - ox) * ss, (cy + 30 * math.sin(ang) + 9 - oy) * ss)], outline=VOLT + (255,), width=3 * ss)),
             bbox=(cx - 70, cy - 70, 140, 140))
    # parameter sliders (illustrative)
    for j, (nm, val) in enumerate((('PAN', .5 + .5 * math.sin(u * 1.2)), ('TILT', .5 + .3 * math.sin(u * .9 + 1)), ('ZOOM', .3 + .5 * k), ('ROLL', .5))):
        sx = MARGIN + j * 240; sy = y + h + 40; G.fill_rect(c, sx, sy + 28, 200, 3, WHITE, .35); G.fill_rect(c, sx + 200 * val - 5, sy + 20, 10, 19, VOLT, 1.0); G.draw_text(c, nm, 'mono', 18, sx, sy - 4, (200, 196, 186), track=.08)
    ui.chip(c, f"CAMERA PATH · {it.get('path', 'dolly').upper()} · ILLUSTRATIVE OVERLAY", W - MARGIN, y - 42, 18, anchor='r', alpha=.9)


def _diagram_i2v(c, ctx, it, u):
    ex = ctx.ex(it['ex']); src = ctx.F.still(ex.spec['clip'], ex.t_in, 540); stl, _ = G.fit_inside(src, 300, 420)
    e = kinetic(u / .7); G.paste(c, G.alpha_mul(np.dstack([stl, np.full(stl.shape[:2], 255, np.uint8)]), clamp(e * 2)), MARGIN + (1 - clamp(e, 0, 1.05)) * -300, 620)
    ui.panel(c, stl, MARGIN, 620, alpha=clamp(e * 2)); G.draw_text(c, 'INPUT IMAGE', 'mono', 20, MARGIN, 620 + stl.shape[0] + 16, VOLT, track=.08, alpha=clamp(e * 2))
    # arrow + filmstrip of frames sampled from the real clip
    ax0, ax1 = MARGIN + 320, MARGIN + 400; k = ease_io(prog(u, .6, 1.2)); G.fill_rect(c, ax0, 830, (ax1 - ax0) * k, 4, VOLT, 1); 
    n = 5; fw = 128; fx = MARGIN + 420
    for i in range(n):
        a = kinetic((u - 1.0 - i * .16) / .5)
        if a <= 0: continue
        fr = ex.frame(min(ex.dur - .05, i * ex.dur / n), max_h=360, loop=True); im, _ = G.fit_inside(fr, fw, int(fw * 1.75)); G.paste(c, im, fx + i * (fw + 8), 640 + (1 - clamp(a, 0, 1)) * 60, alpha=clamp(a * 2))
        G.fill_rect(c, fx + i * (fw + 8), 640 + int(fw * 1.75) + 10, fw, 3, WHITE, .4 * clamp(a * 2))
    G.draw_text(c, 'FRAMES GENERATED FROM THE IMAGE + A TEXT PROMPT', 'mono', 18, fx, 640 + int(fw * 1.75) + 26, (200, 196, 186), track=.05, alpha=clamp((u - 1.9) / .4))
    big, _ = G.fit_inside(ex.frame(u, loop=True, max_h=720), 952, 420); ui.panel(c, big, MARGIN + (952 - big.shape[1]) // 2, 1010 - 40, alpha=clamp((u - 1.6) / .4)); kit.place_label(c, ex, MARGIN + (952 - big.shape[1]) // 2, 970, big.shape[1], big.shape[0], alpha=clamp((u - 1.8) / .4), size=20)


def _diagram_keyframes(c, ctx, it, u):
    ex = ctx.ex(it['ex']); img, _ = G.fit_inside(ex.frame(u, loop=True, max_h=1080), 952, 520); x0 = MARGIN + (952 - img.shape[1]) // 2; x, y, w, h = ui.panel(c, img, x0, 590); kit.place_label(c, ex, x, y, w, h, size=20)
    first = ctx.F.still(ex.spec['clip'], ex.t_in, 300); last = ctx.F.still(ex.spec['clip'], ex.t_out - .1, 300); f1, _ = G.fit_inside(first, 260, 150); f2, _ = G.fit_inside(last, 260, 150)
    yy = y + h + 50; e = kinetic((u - .4) / .6)
    ui.panel(c, f1, MARGIN, yy, alpha=clamp(e * 2)); ui.panel(c, f2, W - MARGIN - f2.shape[1], yy, alpha=clamp(e * 2))
    bx0, bx1 = MARGIN + f1.shape[1] + 24, W - MARGIN - f2.shape[1] - 24; G.fill_rect(c, bx0, yy + 75, (bx1 - bx0), 3, WHITE, .3); k = prog(u, .9, 3.2); G.fill_rect(c, bx0, yy + 74, (bx1 - bx0) * k, 5, VOLT, 1); G.fill_rect(c, bx0 + (bx1 - bx0) * k - 4, yy + 62, 8, 30, VOLT, 1)
    G.draw_text(c, 'FIRST FRAME', 'mono', 18, MARGIN, yy + 162, VOLT, track=.08); G.draw_text(c, 'LAST FRAME', 'mono', 18, W - MARGIN, yy + 162, VOLT, anchor='r', track=.08)
    ui.chip(c, 'ILLUSTRATIVE · FIRST / LAST FRAME CONTROL', W - MARGIN, 560 - 6, 18, anchor='r', alpha=.9) if False else None


def _diagram_refs(c, ctx, it, u):
    refs = list(it.get('refs', [])) or [it['ex']]; ex = ctx.ex(it['ex']); img, _ = G.fit_inside(ex.frame(u, loop=True, max_h=1080), 800, 470); x0 = (W - img.shape[1]) // 2; x, y, w, h = ui.panel(c, img, x0, 900); kit.place_label(c, ex, x, y, w, h, size=20)
    n = len(refs); tw = 250; gapx = (W - 2 * MARGIN - n * tw) / max(1, n - 1) if n > 1 else 0
    for i, rid in enumerate(refs):
        e = kinetic((u - .3 - i * .18) / .55); rx = MARGIN + i * (tw + gapx) if n > 1 else (W - tw) // 2; still = ctx.F.still(ctx.ex(rid).spec['clip'], ctx.ex(rid).t_in + .3, 300); im, _ = G.fit_inside(still, tw, 170)
        ry = 560 - (1 - clamp(e, 0, 1.05)) * 80; ui.panel(c, im, rx, ry, alpha=clamp(e * 2)); G.draw_text(c, f'REFERENCE {i + 1}', 'mono', 18, rx, ry + im.shape[0] + 12, VOLT, track=.08, alpha=clamp(e * 2))
        k = ease_io(prog(u, 1.0 + i * .12, 1.8 + i * .12)); cx0, cy0 = rx + im.shape[1] / 2, ry + im.shape[0] + 40; cx1, cy1 = W / 2, y - 6
        G.vector(c, lambda d, ss, ox, oy: G.line(d, ss, ox, oy, [(cx0, cy0), (cx0 + (cx1 - cx0) * k, cy0 + (cy1 - cy0) * k)], VOLT, 3, 230), bbox=(0, cy0 - 4, W, cy1 - cy0 + 8), ss=1)


def _diagram_edit(c, ctx, it, u):
    ea = ctx.ex(it['ex']); eb = ctx.ex(it.get('ex2', it['ex'])); ia, _ = G.fit_inside(ea.frame(u, loop=True, max_h=720), 952, 640); ib, _ = G.fit_inside(eb.frame(u, loop=True, max_h=720), 952, 640)
    if ib.shape != ia.shape: ib = G.rs(ib, ia.shape[1], ia.shape[0])
    x0 = MARGIN + (952 - ia.shape[1]) // 2; k = ease_io(prog(u, .5, 3.2)); cut = int(ia.shape[1] * k); comp = ia.copy(); comp[:, :cut] = ib[:, :cut]
    x, y, w, h = ui.panel(c, comp, x0, 560); G.fill_rect(c, x + cut - 3, y - 10, 6, h + 20, VOLT, 1.0); kit.place_label(c, ea, x, y, w, h, size=20)
    G.draw_text(c, 'AFTER', 'mono', 22, x + 16, y + 14, VOLT, track=.1); G.draw_text(c, 'BEFORE', 'mono', 22, x + w - 16, y + 14, WHITE, anchor='r', track=.1)


DIAGRAMS = dict(camera=_diagram_camera, i2v=_diagram_i2v, keyframes=_diagram_keyframes, refs=_diagram_refs, edit=_diagram_edit)


def item_scene(ctx, i, t, ts):
    it = _items(ctx)[i]; u = max(0.0, t - ts[i]); c = G.new_canvas()
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=int(it['date'][-4:]) if str(it.get('date', ''))[-4:].isdigit() else None, t=t, alpha=.85)
    DIAGRAMS[it['type']](c, ctx, it, u); _header(c, it, u)
    if it.get('src'): G.draw_text(c, 'SOURCE · ' + it['src'], 'monor', 17, MARGIN, 1490, GREY, track=.04, alpha=clamp((u - 1.2) / .4))
    return c


def render(ctx, t):
    its = _items(ctx); n = len(its)
    if not n: return G.new_canvas()
    ts = _starts(ctx, n); i = max(j for j in range(n) if t >= ts[j] - 1e-6) if t >= ts[0] else 0; c = item_scene(ctx, i, t, ts)
    if i + 1 < n and t > ts[i + 1] - .35: c = TR.transition('whip_up' if i % 2 == 0 else 'slat_v', c, item_scene(ctx, i + 1, t, ts), (t - (ts[i + 1] - .35)) / .35)
    return c


def events(ctx):
    its = _items(ctx); ts = _starts(ctx, len(its)) if its else []; ev = []
    for i, it in enumerate(its):
        ev += [('type_hit', ts[i] + .1, dict(size=.7)), ('data_blip', ts[i] + .55, dict(f=1300)), ('jump', ts[i] + 1.0, dict(dur=.6, up=True)), ('lock', ts[i] + 3.2, dict(size=.8))]
        if i: ev.append(('whoosh', ts[i] - .35, dict(dur=.35, up=True)))
    return ev

"""SEQUENCE 2 - Spatial timeline through verified milestones (S3: 25-34 s).
Cast (plan.cast.seq05): milestones = [ {"year": "2022", "model": "MAKE-A-VIDEO", "dev": "META", "date": "SEP 29, 2022", "ex": excerpt id (era example) or null, "note": "one plain-English line"} ... ] (3-5, chronological).
The Spine becomes a corridor along the time axis: milestone panels stand in depth, alternating left / right, the camera dollies along the axis and settles on each (anticipation, movement, settle).
The excerpt inside a panel is an ERA EXAMPLE and carries its own provenance label; the milestone card describes the milestone, not necessarily that clip.  cues: s5.milestones = [t, ...]."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'corridor'
STYLE = lambda t: 'early' if t < 30.0 else 'now'
T0, T1 = 25.0, 36.4
PANEL_W = 720
DZ = 1000.0                      # spacing between milestones along the axis
FD = 1500.0


def _ms(ctx): return list(ctx.cast('seq05', 'milestones', [])) or []


def _times(ctx, n):
    ts = ctx.cue('s5.milestones')
    if ts and len(ts) >= n: return ts[:n]
    span = (T1 - 1.0) - (T0 + .2); return [T0 + .2 + i * span / n for i in range(n)]


def render(ctx, t):
    ms = _ms(ctx); n = len(ms); c = G.new_canvas()
    if not n: return c
    ts = _times(ctx, n)
    # camera z along the axis: settles on each milestone (kinetic between stops)
    cam = 120.0 + sum(DZ * clamp(kinetic(prog(t, ts[i] - .85, ts[i] + .1)), -.1, 1.04) for i in range(1, n))
    yaw = np.radians(-4 * np.sin(t * .35)); pitch = np.radians(6)
    def proj(p):
        x, y, z = p; z = z - cam; x, z = x * np.cos(yaw) - z * np.sin(yaw), x * np.sin(yaw) + z * np.cos(yaw); y, z = y * np.cos(pitch) - z * np.sin(pitch), y * np.sin(pitch) + z * np.cos(pitch)
        if z < -.5 * FD: return None, 0
        s_ = FD / (FD + z); return (540 + x * s_, 780 + y * s_), s_
    # floor: rails + cross ticks (the Spine in perspective)
    segs = []
    for xr in (-420, 420):
        p0, _ = proj((xr, 400, -600 + cam)); p1, _ = proj((xr, 400, cam + n * DZ)); 
        if p0 and p1: segs.append((p0, p1, WHITE, 2, 60))
    axis0, _ = proj((0, 400, -600 + cam)); axis1, _ = proj((0, 400, cam + n * DZ))
    if axis0 and axis1: segs.append((axis0, axis1, VOLT, 4, 255))
    for k in range(-1, n * 2 + 2):
        z = k * DZ / 2; pa, _ = proj((-420, 400, z)); pb, _ = proj((420, 400, z))
        if pa and pb: segs.append((pa, pb, WHITE, 1, 40))
    G.vector(c, lambda d, ss, ox, oy: [G.line(d, ss, ox, oy, [p0, p1], col, w_, al) for p0, p1, col, w_, al in segs], ss=1)
    # milestones (draw far -> near)
    order = sorted(range(n), key=lambda i: -(i * DZ - cam))
    for i in order:
        m = ms[i]; z = i * DZ; side = -1 if i % 2 == 0 else 1; cx = side * 60
        pc, s_ = proj((cx, 0, z))
        if pc is None or s_ < .12 or s_ > 2.2: continue
        appear = ease_out(prog(t, ts[i] - 1.1, ts[i] - .3)); live = abs(ts[i] - t) < 1.6 or (i == n - 1 and t > ts[i] - 1.6)
        w = PANEL_W * s_; ph = w * 9 / 16
        ex = ctx.ex(m['ex']) if m.get('ex') else None
        if ex is not None:
            fr = ex.frame(max(0.0, t - (ts[i] - .7)), loop=True, max_h=540) if live else ctx.F.still(ex.spec['clip'], ex.t_in, 360)
            img, _ = G.fit_inside(fr, int(w), int(ph)); img = kit.early_grade(img, 1.0 if int(m['year']) < 2024 else 0.0)
            quad = [proj((cx - PANEL_W / 2 * (1), 0 - PANEL_W * 9 / 32, z))[0], proj((cx + PANEL_W / 2, 0 - PANEL_W * 9 / 32, z))[0], proj((cx + PANEL_W / 2, 0 + PANEL_W * 9 / 32, z))[0], proj((cx - PANEL_W / 2, 0 + PANEL_W * 9 / 32, z))[0]]
            if all(q is not None for q in quad):
                G.shadow_rect(c, quad[0][0], quad[0][1], quad[1][0] - quad[0][0], quad[3][1] - quad[0][1], blur=22, alpha=.5 * appear)
                G.warp_quad(c, G.rs(fr, 600, 338), quad, alpha=appear)
                G.vector(c, lambda d_, ss, ox, oy: G.line(d_, ss, ox, oy, quad + [quad[0]], WHITE, 2, int(120 * appear)), bbox=(min(q[0] for q in quad) - 4, min(q[1] for q in quad) - 4, max(q[0] for q in quad) - min(q[0] for q in quad) + 8, max(q[1] for q in quad) - min(q[1] for q in quad) + 8), ss=1)
                if s_ > .55: kit.place_label(c, ex, quad[0][0], quad[0][1], quad[1][0] - quad[0][0], quad[3][1] - quad[0][1], alpha=appear, size=max(14, int(20 * s_)))
        # milestone card: big year + model + note (billboards in depth)
        if s_ > .3:
            ys = int(260 * s_); tx = pc[0] - w / 2 if side < 0 else pc[0] - w / 2; ty = pc[1] - ph / 2 - ys * 1.05
            G.draw_text(c, m['year'], 'display', ys, tx, ty, VOLT if int(m['year']) >= 2024 else WHITE, alpha=appear, track=-.01, pad=2)
            G.draw_text(c, f"{m['model']} · {m['dev']}", 'mono', max(14, int(28 * s_)), tx, pc[1] + ph / 2 + 22 * s_, WHITE, alpha=appear, track=.04, pad=2)
            G.draw_text(c, m.get('date', ''), 'monor', max(12, int(20 * s_)), tx, pc[1] + ph / 2 + 22 * s_ + 40 * s_, GREY, alpha=appear * .95, track=.05, pad=2)
            if m.get('note') and s_ > .8: G.draw_text(c, m['note'], 'ui', int(28 * s_), tx, pc[1] + ph / 2 + 22 * s_ + 78 * s_, (222, 218, 208), alpha=appear, pad=2)
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=int(ms[min(n - 1, max(0, sum(1 for x in ts if t >= x) - 1))]['year']), t=t, alpha=.9)
    return c


def events(ctx):
    n = len(_ms(ctx)); ts = _times(ctx, n) if n else []; ev = []
    for i in range(n):
        ev += [('jump', ts[i] - .85, dict(dur=.8, up=True)), ('lock', ts[i] + .05, dict(size=.9, f=1046 * (1 + .12 * i))), ('type_hit', ts[i] + .05, dict(size=.6))]
    return ev

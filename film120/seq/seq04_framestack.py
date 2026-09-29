"""SEQUENCE 5 - Frame-stack: what "consistency across time" means (S3: 34-43 s).
Cast (plan.cast.seq04): early = excerpt id (early, unstable), modern = excerpt id (recent, coherent); optional u_early, u_modern (start seconds inside each), step (seconds between stacked frames, default .12), box (normalised tracked point box).
Ten real consecutive-ish frames per clip stand as slabs in a 3-D stack; a subject point is TRACKED through the slabs and its path drawn in volt: a smooth path for a subject that holds together, a ragged one where it does not.
Both numbers on screen are measured from the two clips (mean frame-to-frame luma change; path jitter).  Different prompts, different content: labelled ILLUSTRATIVE."""
import numpy as np
from PIL import Image
from engine import gfx as G, ui, kit, tracker
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'framestack'
STYLE = lambda t: 'early' if t < 38.8 else 'now'
T0, T1 = 34.0, 43.0
K = 10
SW, SH = 760, 428


def _data(ctx, key, eid, u0, step, box):
    ck = ('fs', key)
    if ck in ctx.cache: return ctx.cache[ck]
    ex = ctx.ex(eid); u0 = min(u0, max(0, ex.dur - K * step - .05)); frames = [ex.frame(u0 + i * step, max_h=360, loop=True) for i in range(K)]
    tr = tracker.block_track(frames, box, search=7, grid=96); pts = np.array([(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in tr])
    jit = float(np.abs(np.diff(pts, 2, axis=0)).mean()) if len(pts) > 2 else 0.0
    slabs = [G.rs(f, SW, SH) for f in frames]; d = dict(ex=ex, slabs=slabs, pts=pts, jitter=jit, resid=tracker.residual_change(frames)); ctx.cache[ck] = d; return d


def render(ctx, t):
    c = G.new_canvas(); u = t - T0; step = ctx.cast('seq04', 'step', .12); box = tuple(ctx.cast('seq04', 'box', (.36, .26, .28, .4)))
    A = _data(ctx, 'early', ctx.cast('seq04', 'early'), ctx.cast('seq04', 'u_early', 0.0), step, box); B = _data(ctx, 'modern', ctx.cast('seq04', 'modern'), ctx.cast('seq04', 'u_modern', 0.0), step, box)
    ui.spine(c, reveal=1.0, years=range(2016, 2027), highlight=2023 if t < 38.8 else 2025, t=t, alpha=.85)
    yaw = np.radians(lerp(-30, 24, ease_io(u / (T1 - T0)))); pitch = np.radians(9); fd = 2100.0
    def proj(p, cy):
        x, y, z = p; x, z = x * np.cos(yaw) - z * np.sin(yaw), x * np.sin(yaw) + z * np.cos(yaw); y, z = y * np.cos(pitch) - z * np.sin(pitch), y * np.sin(pitch) + z * np.cos(pitch)
        s_ = fd / (fd + z + 520); return (540 + x * s_, cy + y * s_)
    for si, (D, cy, name, col) in enumerate(((A, 660, 'EARLY', WHITE), (B, 1130, 'RECENT', VOLT))):
        t_in = T0 + .2 + si * 1.2; sp = 52
        for i in reversed(range(K)):
            e = kinetic((t - t_in - i * .07) / .6)
            if e <= 0: continue
            z = (i - K / 2) * sp - (1 - clamp(e, 0, 1)) * 700; hw, hh = SW / 2, SH / 2
            quad = [proj((px, py, z), cy) for (px, py) in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            img = kit.early_grade(D['slabs'][i], 1.0 if si == 0 else 0.0)
            G.warp_quad(c, img, quad, alpha=clamp(e * 1.5) * (.55 + .45 * (1 - i / K)))
            G.vector(c, lambda d_, ss, ox, oy: G.line(d_, ss, ox, oy, quad + [quad[0]], WHITE, 1.5, 90), bbox=(min(q[0] for q in quad) - 4, min(q[1] for q in quad) - 4, max(q[0] for q in quad) - min(q[0] for q in quad) + 8, max(q[1] for q in quad) - min(q[1] for q in quad) + 8), ss=1)
        # tracked-point path through the slabs
        a = ease_out(prog(t, t_in + 1.4, t_in + 2.4))
        if a > 0:
            path = []
            for i in range(K):
                px = (D['pts'][i][0] - .5) * SW; py = (D['pts'][i][1] - .5) * SH; z = (i - K / 2) * sp; path.append(proj((px, py, z), cy))
            n_show = max(2, int(2 + (K - 2) * a)); pp = path[:n_show]
            G.vector(c, lambda d_, ss, ox, oy: (G.line(d_, ss, ox, oy, pp, VOLT, 5, 255), [d_.ellipse([(q[0] - ox - 6) * ss, (q[1] - oy - 6) * ss, (q[0] - ox + 6) * ss, (q[1] - oy + 6) * ss], fill=VOLT + (255,)) for q in pp]),
                     bbox=(min(q[0] for q in pp) - 12, min(q[1] for q in pp) - 12, max(q[0] for q in pp) - min(q[0] for q in pp) + 24, max(q[1] for q in pp) - min(q[1] for q in pp) + 24))
        lab_y = cy - 305
        G.draw_text(c, name, 'display', 64, MARGIN, lab_y, col, track=.01, alpha=clamp((t - t_in) / .4))
        G.draw_text(c, f"{K} FRAMES · {step * 1000:.0f} MS APART · {D['ex'].label.get('model', '').upper()} {D['ex'].label.get('year', '')}", 'monor', 19, MARGIN, lab_y + 76, (200, 196, 186), track=.04, alpha=clamp((t - t_in - .3) / .4))
        G.draw_text(c, f"MEASURED · CHANGE {D['resid']:.1f}/255 · PATH JITTER {D['jitter'] * 100:.1f}", 'mono', 19, MARGIN, lab_y + 106, VOLT, track=.03, alpha=a if a > 0 else 0)
    ui.chip(c, 'ILLUSTRATIVE · DIFFERENT PROMPTS AND CONTENT', W // 2, 1430, 20, anchor='c', dot=VOLT, alpha=ease_out(prog(t, T0 + 1.0, T0 + 1.6)))
    return c


def events(ctx):
    ev = []
    for si in range(2):
        t_in = T0 + .2 + si * 1.2
        ev += [('slide', t_in, dict(dur=.7, gain=.7)), ('lock', t_in + 1.9, dict(size=.8, f=1320 + si * 440))]
    return ev + [('whoosh', T1 - .6, dict(dur=.6, up=True))]

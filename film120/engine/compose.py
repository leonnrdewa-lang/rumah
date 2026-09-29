"""Compositor: picks the active sequence for time t, handles sequence-to-sequence transitions, style, subtitles, and renders frame ranges.

A sequence is a module in film120/seq/ exposing:
    NAME      : str
    STYLE     : 'early' | 'now' | callable(t)->'early'|'now'|dict(sat=,contrast=,grain=,vig=)
    SUBS      : bool (subtitles on; default True)   /  SUB_Y : int (optional)
    render(ctx, t) -> uint8 (H,W,3)    valid for t within [t0 - 0.6, t1 + 0.6]
    events(ctx) -> [(kind, t, params_dict)]   audio events for the sound designer
and is registered in data/edit_plan.json under "sequences": [{"id","module","t0","t1","transition_out": ["kind", dur]}].
"""
import importlib, json, os, sys, time
import numpy as np
from PIL import Image
from .tokens import *
from . import gfx as G, ui, transitions as TR
from .footage import Footage
from .storyboard import Storyboard


class Ctx:
    def __init__(self, plan_path, script_path, vo_path, media_dir=None, max_streams=8):
        self.plan = json.load(open(plan_path)); self.F = Footage(plan_path, media_dir, max_streams); self.SB = Storyboard(script_path, vo_path)
        self.prev = {}; self.cache = {}; self.seqs = []
        for s in self.plan['sequences']:
            mod = importlib.import_module(s['module']); self.seqs.append(dict(spec=s, mod=mod, t0=s['t0'], t1=s['t1']))
        self.chunks = ui.caption_chunks(self.SB.words_by_line())
        self.end_speech = max(self.SB.E.values())

    def ex(self, eid): return self.F.ex(eid)

    # ---- plan helpers used by sequences
    def cue(self, name, default=None):
        """Named time cue from data/edit_plan.json 'cues' (seconds), else default."""
        return self.plan.get('cues', {}).get(name, default)

    def cast(self, seq, key, default=None):
        """Excerpt id (or other value) cast for a sequence role: plan['cast'][seq][key]."""
        return self.plan.get('cast', {}).get(seq, {}).get(key, default)

    def cast_ex(self, seq, key):
        eid = self.cast(seq, key); return self.F.ex(eid) if eid else None

    def focus(self, eid):
        """Horizontal focus of interest 0..1 from edge energy of a few frames of the excerpt (drives 9:16 crops)."""
        k = ('focus', eid)
        if k not in self.cache:
            ex = self.F.ex(eid); acc = None
            for dt in (.2, .9, 1.6):
                if dt > ex.dur - .05: continue
                f = ex.F.frame(ex.spec['clip'], ex.t_in, ex.t_in + dt, max_h=180); g = np.asarray(Image.fromarray(f).convert('L'), np.float32)
                e = np.abs(np.diff(g, axis=1))[:-1] + np.abs(np.diff(g, axis=0))[:, :-1]; acc = e if acc is None else acc + e
            if acc is None: self.cache[k] = .5
            else:
                col = np.convolve(acc.sum(0), np.ones(9) / 9, 'same'); xs = np.linspace(0, 1, len(col)); w_ = col ** 2; self.cache[k] = float(np.clip((xs * w_).sum() / w_.sum(), .32, .68))
        return self.cache[k]

    def cover_safe(self, eid, aspect=W / H, cx=.5, zoom=1.0, cy=.5):
        """True if a cover-crop window (aspect, centre cx/cy, zoom) leaves every profiled static overlay (watermark/logo) inside the frame, i.e. none is cropped away."""
        ex = self.F.ex(eid); ov = ex.clip.get('overlays') or []
        if not ov: return True
        ar = ex.aspect; wh = 1.0 / zoom; ww = wh * aspect                     # source is ar x 1 in these units (same rules as gfx.crop_window)
        if ww > ar: ww = ar / zoom if zoom > 1 else ar; wh = ww / aspect
        x0 = min(max(cx * ar - ww / 2, 0), ar - ww) / ar; y0 = min(max(cy - wh / 2, 0), 1 - wh); wn = ww / ar
        return all(o['x'] >= x0 - 1e-3 and o['x'] + o['w'] <= x0 + wn + 1e-3 and o['y'] >= y0 - 1e-3 and o['y'] + o['h'] <= y0 + wh + 1e-3 for o in ov)


def style_params(style, t):
    if callable(style): style = style(t)
    if isinstance(style, dict): return style
    if style == 'early': return dict(sat=.80, contrast=.95, lift=.02, tint=(1.0, .995, .985), grain=8.0, vig=.38)
    return dict(sat=1.03, contrast=1.05, lift=.0, tint=(1, 1, 1.01), grain=2.8, vig=.30)


def blend_style(a, b, k):
    out = dict(a)
    for key in ('sat', 'contrast', 'lift', 'grain', 'vig'): out[key] = a[key] * (1 - k) + b[key] * k
    out['tint'] = tuple(a['tint'][i] * (1 - k) + b['tint'][i] * k for i in range(3)); return out


def active_index(ctx, t):
    for i, s in enumerate(ctx.seqs):
        if s['t0'] <= t < s['t1']: return i
    return len(ctx.seqs) - 1 if t >= ctx.seqs[-1]['t1'] else 0


def compose_frame(ctx, t, fidx):
    i = active_index(ctx, t); seqs = ctx.seqs; s = seqs[i]; c = None; st = style_params(s['mod'].STYLE, t); sub_on = getattr(s['mod'], 'SUBS', True); sub_y = getattr(s['mod'], 'SUB_Y', SUB_Y)
    tr = s['spec'].get('transition_out')                       # transition from seq i to seq i+1 centred on its t1
    if tr and i + 1 < len(seqs):
        kind, d = tr[0], float(tr[1])
        if s['t1'] - d / 2 <= t < s['t1'] + d / 2 or (t < s['t1'] and t >= s['t1'] - d / 2):
            n = seqs[i + 1]; p = (t - (s['t1'] - d / 2)) / d
            a = s['mod'].render(ctx, t); b = n['mod'].render(ctx, t); c = TR.transition(kind, a, b, p, seed=i)
            st = blend_style(st, style_params(n['mod'].STYLE, t), clamp01(p))
    if c is None and i > 0:
        pv = seqs[i - 1]; tr = pv['spec'].get('transition_out')
        if tr:
            kind, d = tr[0], float(tr[1])
            if pv['t1'] - d / 2 <= t < pv['t1'] + d / 2:
                p = (t - (pv['t1'] - d / 2)) / d; a = pv['mod'].render(ctx, t); b = s['mod'].render(ctx, t); c = TR.transition(kind, a, b, p, seed=i - 1)
                st = blend_style(style_params(pv['mod'].STYLE, t), st, clamp01(p))
    if c is None: c = s['mod'].render(ctx, t)
    c = finish(c, st, fidx)
    if sub_on and t < ctx.end_speech + .5:
        if getattr(s['mod'], 'SCRIM', True): G.gradient_v(c, sub_y - 150, sub_y + 210, 0, .58)      # legibility scrim under subtitles
        ui.draw_subtitle(c, t, ctx.chunks, VOLT, sub_y)
    return c


def clamp01(x): return 0.0 if x < 0 else 1.0 if x > 1 else x


def finish(c, st, fidx):
    c = G.grade(c, st['sat'], st['contrast'], st['lift'], st['tint']); c = G.vignette(c, st['vig']); return G.grain(c, st['grain'], fidx)


def collect_events(ctx):
    ev = []
    for s in ctx.seqs:
        if hasattr(s['mod'], 'events'): ev += list(s['mod'].events(ctx))
    return sorted(ev, key=lambda e: e[1])

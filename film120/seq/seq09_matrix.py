"""SEQUENCE 10 - A restrained capability comparison from VERIFIED FACTS (S5: 75-83 s).
Cast (plan.cast.seq09): cols = [ {"name": "RUNWAY", "sub": "GEN-4"} ... ] (4-5 products), rows = [ {"name": "IMAGE-TO-VIDEO", "cells": [ {"has": true, "since": "2023", "src": "url-short"} | null ... ]} ... ] (5-6 rows).
Only presence of a documented feature and the year it was first documented for that product are shown - no scores, no percentages, no ranking.  Header: DOCUMENTED FEATURES · ILLUSTRATIVE · NOT A RANKING.  cues: s9.rows = [t_row0, ...]."""
import numpy as np
from engine import gfx as G, ui, kit
from engine.tokens import *
from engine.gfx import clamp, lerp, prog, ease_io, ease_out, kinetic

NAME = 'matrix'
STYLE = 'now'
T0, T1 = 72.0, 83.0


def render(ctx, t):
    c = G.new_canvas(); cols = ctx.cast('seq09', 'cols', []); rows = ctx.cast('seq09', 'rows', [])
    ui.spine(c, reveal=1.0, years=range(2016, 2027), t=t, alpha=.85)
    u = t - T0; a = kinetic(u / .6); title = 'WHAT THE TOOLS DOCUMENT'; ts_ = kit.fit_size(title, 'display', 112, W - 2 * MARGIN, -.005)
    G.draw_text(c, title, 'display', ts_, MARGIN, 262 + (1 - clamp(a)) * 40, WHITE, alpha=clamp(a * 3), track=-.005)
    ui.chip(c, 'FEATURES DEVELOPERS DOCUMENT · ILLUSTRATIVE · NOT A RANKING', MARGIN, 262 + int(ts_ * 1.3), 20, dot=VOLT, alpha=clamp((u - .3) / .3))
    if not cols or not rows: return c
    n = len(rows); lw = 330; cw = (W - 2 * MARGIN - lw) / len(cols); x0 = MARGIN; y0 = 540; rh = int(min(150, (1215 - y0 - 70) / n))
    for j, col in enumerate(cols):
        e = kinetic((u - .5 - j * .1) / .5); cx = x0 + lw + j * cw + cw / 2
        G.draw_text(c, col['name'], 'mono', 25, cx, y0 - 76 + (1 - clamp(e, 0, 1)) * -20, WHITE, anchor='c', alpha=clamp(e * 2), track=.04); G.draw_text(c, col.get('sub', ''), 'monor', 19, cx, y0 - 40, GREY, anchor='c', alpha=clamp(e * 2), track=.03)
    G.fill_rect(c, x0, y0 - 6, W - 2 * MARGIN, 2, WHITE, .35)
    ts = ctx.cue('s9.rows') or [T0 + 1.0 + i * .55 for i in range(n)]
    for i, row in enumerate(rows):
        ry = y0 + i * rh + 12; e = kinetic((t - ts[i]) / .55)
        if e <= 0: continue
        G.draw_text(c, row['name'], 'ui_xb', 29, x0, ry + rh * .30 + (1 - clamp(e, 0, 1)) * 30, WHITE, alpha=clamp(e * 3), track=-.005); G.fill_rect(c, x0, ry + rh - 14, W - 2 * MARGIN, 1, WHITE, .16 * clamp(e * 3))
        for j, cell in enumerate(row['cells']):
            cx = x0 + lw + j * cw + cw / 2; cy = ry + rh * .30
            if cell and cell.get('has'):
                r = 18 * clamp(kinetic((t - ts[i] - j * .07) / .45), 0, 1.15)
                G.vector(c, lambda d, ss, ox, oy: d.ellipse([(cx - r - ox) * ss, (cy - r - oy) * ss, (cx + r - ox) * ss, (cy + r - oy) * ss], fill=VOLT + (255,)), bbox=(cx - 28, cy - 28, 56, 56))
                G.draw_text(c, str(cell.get('since', '')), 'mono', 20, cx, cy + 27, WHITE, anchor='c', alpha=clamp((t - ts[i] - j * .07 - .2) / .3), track=.03)
            else:
                G.fill_rect(c, cx - 9, cy - 1, 18, 3, GREY, .55 * clamp(e * 3))
    ly = y0 + n * rh + 26; la = clamp((u - 2.8) / .5); r = 7
    G.vector(c, lambda d, ss, ox, oy: d.ellipse([(MARGIN + 6 - r - ox) * ss, (ly + 14 - r - oy) * ss, (MARGIN + 6 + r - ox) * ss, (ly + 14 + r - oy) * ss], fill=VOLT + (int(255 * la),)), bbox=(MARGIN - 4, ly, 24, 30))
    G.draw_text(c, '= DOCUMENTED (EARLIEST YEAR VERIFIED)   — = NOT VERIFIED HERE', 'monor', 16, MARGIN + 22, ly + 4, (168, 164, 154), track=.02, alpha=la)
    return c


def events(ctx):
    rows = ctx.cast('seq09', 'rows', []); ts = ctx.cue('s9.rows') or [T0 + 1.0 + i * .55 for i in range(len(rows))]
    return [('type_hit', T0 + .1, dict(size=.7))] + [('tick', tt, {}) for tt in ts[:len(rows)]] + [('lock', T1 - 1.2, dict(size=.9))]

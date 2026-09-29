"""Engine smoke-test sequence: exercises panel, label, spine, kinetic hero type."""
import numpy as np
from engine import gfx as G, ui
from engine.tokens import *
NAME = 'demo'; STYLE = 'early'
def render(ctx, t):
    c = G.new_canvas()
    ui.spine(c, reveal=G.prog(t, 0, 3), crack=max(0, 1 - t / 2.5), years=range(2016, 2027), highlight=2022 if t > 3 else None, t=t)
    ui.frame_icons(c, SPINE_Y, MARGIN, W - MARGIN, 18, G.prog(t, 0.5, 3))
    ui.hero_lines(c, ['THIS WAS', 'AI VIDEO.'], MARGIN, 300, 210, [WHITE, VOLT], 0.4, t)
    ex = ctx.ex('e1'); fr = ex.frame(t, loop=True); img, _ = G.fit_inside(fr, 952, 620)
    x, y, w, h = ui.panel(c, img, MARGIN + (952 - img.shape[1]) // 2, 780)
    ui.source_label(c, ex.label, x, y + h + 24)
    ui.chip(c, 'ILLUSTRATIVE · DIFFERENT PROMPTS', W - MARGIN, y + h + 24, 20, anchor='r', dot=VOLT)
    return c
def events(ctx): return [('impact', 1.0, {})]

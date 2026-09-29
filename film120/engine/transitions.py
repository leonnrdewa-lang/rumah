"""Transitions between two full canvases.  transition(kind, a, b, p) -> canvas, p in 0..1.  Sequences may also build custom, content-linked transitions."""
import numpy as np
from .tokens import *
from . import gfx as G
from .gfx import clamp, ease_io, ease_out

_gx = _gy = None
def grids():
    global _gx, _gy
    if _gx is None: _gy, _gx = np.mgrid[0:H, 0:W].astype(np.float32)
    return _gx, _gy

def blend_mask(a, b, m):
    m = m[..., None]; return (a * (1 - m) + b * m).astype(np.uint8)

def radial(img, k):
    if k < .05: return img
    acc = img.astype(np.float32); n = 4
    for i in range(1, n + 1): acc += G.scale_about(img, 1 + k * .05 * i).astype(np.float32)
    return (acc / (n + 1)).astype(np.uint8)

def transition(kind, a, b, p, accent=VOLT, seed=1):
    if kind == 'cut': return b if p >= .5 else a
    if kind == 'flash':
        f = 1 - abs(p * 2 - 1); base = b if p >= .5 else a; return (base * (1 - f) + 255 * f).astype(np.uint8)
    if kind == 'dip':
        f = 1 - abs(p * 2 - 1); base = b if p >= .5 else a; return (base * (1 - f) + np.array(CHARCOAL, np.float32) * f).astype(np.uint8)
    if kind == 'whip':
        off = int(ease_io(p) * W); cat = np.concatenate([a, b], 1)[:, off:off + W]
        return G.motion_blur_h(cat, int(240 * np.sin(np.pi * clamp(p))) + 2)
    if kind == 'whip_up':
        off = int(ease_io(p) * H); cat = np.concatenate([a, b], 0)[off:off + H]
        return G.motion_blur_v(cat, int(240 * np.sin(np.pi * clamp(p))) + 2)
    if kind == 'zoomthrough':
        if p < .5:
            k = ease_io(p * 2); return radial(G.scale_about(a, 1 + 1.4 * k), k)
        k = ease_io((p - .5) * 2); return radial(G.scale_about(b, 1 + .35 * (1 - k)), 1 - k)
    if kind in ('iris', 'iris_in'):
        gx, gy = grids(); r = np.sqrt((gx - W / 2) ** 2 + (gy - H * .46) ** 2); rad = ease_io(p) * 1250
        m = np.clip((rad - r) / 3.0 + .5, 0, 1); out = blend_mask(a, b, m)
        ring = np.clip(1 - np.abs(r - rad) / 5.0, 0, 1) * (1 if 0 < p < 1 else 0)
        return (out * (1 - ring[..., None]) + np.array(accent, np.float32) * ring[..., None]).astype(np.uint8)
    if kind == 'slat':
        gx, gy = grids(); n = 9; u = ((gx + gy * .55) / (W + H * .55)) * n; idx = np.floor(u); fr = u - idx
        return blend_mask(a, b, np.clip((p * 1.6 - idx / n * .6) * 4.0 - (1 - fr) * 1.6, 0, 1))
    if kind == 'slat_v':
        gx, gy = grids(); n = 12; u = (gx / W) * n; idx = np.floor(u); fr = u - idx
        return blend_mask(a, b, np.clip((p * 1.5 - (idx % 2) * .25 - idx / n * .35) * 5.0 - (1 - fr) * 1.2, 0, 1))
    if kind == 'shards':
        gx, gy = grids(); rng = np.random.default_rng(seed); cx = rng.uniform(.3, .7) * W; cy = rng.uniform(.3, .6) * H
        ang = np.arctan2(gy - cy, gx - cx); k = 14; sector = np.floor((ang + np.pi) / (2 * np.pi) * k); jitter = (np.sin(sector * 12.9898) * 43758.5453 % 1)
        return blend_mask(a, b, np.clip((p * 1.5 - jitter * .5) * 6.0 - .3, 0, 1))
    return b if p >= .5 else a

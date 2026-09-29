"""Small numpy trackers and clip measurements used for *honest* annotations.
Nothing here judges 'quality'; it measures what is in the pixels (motion, flicker, ghosting) so labels can say 'measured on this clip'."""
import numpy as np
from PIL import Image

def luma_small(fr, w=96):
    im = Image.fromarray(fr).convert('L'); h = max(8, int(w * fr.shape[0] / fr.shape[1])); return np.asarray(im.resize((w, h), Image.BOX), np.float32)

def block_track(frames, box0, search=6, grid=96):
    """Track a box (x,y,w,h normalised 0..1) through a list of RGB frames by SAD block matching on a small luma grid.
    Returns a list of normalised boxes, one per frame (frame 0 = box0)."""
    ls = [luma_small(f, grid) for f in frames]; gh, gw = ls[0].shape
    x, y, w, h = box0; bx, by, bw, bh = int(x * gw), int(y * gh), max(6, int(w * gw)), max(6, int(h * gh))
    tmpl = ls[0][by:by + bh, bx:bx + bw]; out = [box0]
    for k in range(1, len(ls)):
        best, bp = 1e18, (bx, by); cur = ls[k]
        for dy in range(-search, search + 1):
            for dx in range(-search, search + 1):
                px, py = bx + dx, by + dy
                if px < 0 or py < 0 or px + bw > gw or py + bh > gh: continue
                sad = np.abs(cur[py:py + bh, px:px + bw] - tmpl).mean()
                if sad < best: best, bp = sad, (px, py)
        bx, by = bp; tmpl = 0.85 * tmpl + 0.15 * cur[by:by + bh, bx:bx + bw]     # slow template update
        out.append((bx / gw, by / gh, bw / gw, bh / gh))
    # light smoothing
    arr = np.array(out); k = 3; pad = np.pad(arr, ((k, k), (0, 0)), mode='edge'); sm = np.stack([np.convolve(pad[:, i], np.ones(2 * k + 1) / (2 * k + 1), 'valid') for i in range(4)], 1)
    return [tuple(r) for r in sm]

def most_unstable_box(frames, grid=64, keep=.08):
    """Normalised box around the region that changes most between consecutive frames (after removing the global brightness change)."""
    ls = [luma_small(f, grid) for f in frames]; d = np.zeros_like(ls[0])
    for a, b in zip(ls[:-1], ls[1:]): d += np.abs((b - b.mean()) - (a - a.mean()))
    thr = np.percentile(d, 100 * (1 - keep)); ys, xs = np.where(d >= thr)
    if len(xs) < 3: return None
    gh, gw = d.shape; x0, x1 = np.percentile(xs, 6), np.percentile(xs, 94); y0, y1 = np.percentile(ys, 6), np.percentile(ys, 94)
    return (x0 / gw, y0 / gh, max(.08, (x1 - x0 + 1) / gw), max(.08, (y1 - y0 + 1) / gh))

def flicker_index(frames, grid=48):
    """Mean absolute change of the global mean luminance between consecutive frames, in 0..255 luma levels (a measured statistic, not a quality score)."""
    m = [luma_small(f, grid).mean() for f in frames]; return float(np.mean(np.abs(np.diff(m)))) if len(m) > 1 else 0.0

def residual_change(frames, grid=64):
    """Mean absolute frame-to-frame luma difference after removing the global mean (0..255)."""
    ls = [luma_small(f, grid) for f in frames]; return float(np.mean([np.abs((b - b.mean()) - (a - a.mean())).mean() for a, b in zip(ls[:-1], ls[1:])])) if len(ls) > 1 else 0.0

def onion(frames, alphas=None):
    """Multi-frame overlay (onion skin): average of frames - ghosting shows where content does not line up across time."""
    acc = np.zeros(frames[0].shape, np.float32); ws = alphas or [1.0] * len(frames)
    for f, w in zip(frames, ws): acc += f.astype(np.float32) * w
    return (acc / sum(ws)).astype(np.uint8)

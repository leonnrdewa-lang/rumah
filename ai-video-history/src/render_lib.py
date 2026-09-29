"""Footage streaming, widgets, transitions, captions, post."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
import design as D
from design import W, H, FPS, clamp, ease_out, ease_io, prog, lerp

FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')

class Stream:
    """Sequential 30 fps RGB reader on top of an ffmpeg pipe. Holds last frames; restarts if asked to go backwards."""
    def __init__(self, path, t_in, w, h):
        self.path, self.t_in, self.w, self.h = path, t_in, w, h; self.fsz = w * h * 3
        self.p = None; self.base = 0; self.buf = []; self.eof = False; self._start(0)
    def _start(self, idx):
        self.close(); self.base = idx; self.buf = []; self.eof = False
        ss = max(0.0, self.t_in + idx / FPS)
        self.p = subprocess.Popen([FFMPEG, '-v', 'error', '-ss', f'{ss:.3f}', '-i', self.path, '-an', '-vf', f'fps={FPS},scale={self.w}:{self.h}:flags=bicubic',
                                   '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.fsz * 2)
    def close(self):
        if self.p:
            try: self.p.kill(); self.p.stdout.close(); self.p.wait()
            except Exception: pass
            self.p = None
    def _read(self):
        b = self.p.stdout.read(self.fsz)
        if len(b) < self.fsz: self.eof = True; return None
        return np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3)
    def get(self, idx):
        idx = max(0, int(idx))
        if idx < self.base or idx > self.base + len(self.buf) + 90: self._start(idx)
        while self.base + len(self.buf) <= idx and not self.eof:
            f = self._read()
            if f is None: break
            self.buf.append(f)
            if len(self.buf) > 4: self.buf.pop(0); self.base += 1
        if not self.buf: return np.zeros((self.h, self.w, 3), np.uint8)
        return self.buf[min(idx - self.base, len(self.buf) - 1)] if idx >= self.base else self.buf[0]

class Footage:
    def __init__(self, fdir):
        self.dir = fdir; self.man = json.load(open(os.path.join(fdir, 'footage_manifest.json'))); self.streams = {}
    def meta(self, cid): return self.man[cid]
    def segments(self, cid, min_len=1.5):
        m = self.man[cid]; cs = [0.0] + list(m.get('cuts', [])) + [m['duration']]
        return [(a + .12, b - .05) for a, b in zip(cs[:-1], cs[1:]) if b - a >= min_len]
    def pick(self, cid, nth, dur):
        """In-point of the nth clean (cut-free) segment that can hold `dur` seconds; falls back to the longest."""
        segs = self.segments(cid, 0.9) or [(0, self.man[cid]['duration'])]
        ok = [s for s in segs if s[1] - s[0] >= dur]
        s = (ok or [max(segs, key=lambda x: x[1] - x[0])])[nth % len(ok or [0])] if ok else max(segs, key=lambda x: x[1] - x[0])
        return round(min(s[0], max(0.0, self.man[cid]['duration'] - dur - .05)), 3)
    def frame(self, cid, t_in, src_t, max_h=1080):
        """Frame at source time src_t (absolute seconds), reader anchored at t_in."""
        m = self.man[cid]; dh = min(m['height'], max_h); dw = int(round(dh * m['width'] / m['height'] / 2)) * 2; dh = dh // 2 * 2
        key = (cid, round(t_in, 3), dw, dh); st = self.streams.get(key)
        if st is None:
            if len(self.streams) >= 5:
                k0 = next(iter(self.streams)); self.streams.pop(k0).close()
            st = self.streams[key] = Stream(m['local'] if os.path.exists(m['local']) else os.path.join(self.dir, os.path.basename(m['local'])), t_in, dw, dh)
        x = (src_t - t_in) * FPS; i = int(np.floor(x)); a = x - i
        f0 = st.get(i)
        if a > 0.08:
            f1 = st.get(i + 1); return (f0 * (1 - a) + f1 * a).astype(np.uint8) if f1 is not f0 else f0
        return f0
    def close(self):
        for s in self.streams.values(): s.close()
        self.streams = {}

# ---------- widgets ----------
def rrect(d, ss, ox, oy, x, y, w, h, r, fill=None, outline=None, width=2):
    d.rounded_rectangle([(x - ox) * ss, (y - oy) * ss, (x - ox + w) * ss, (y - oy + h) * ss], radius=r * ss, fill=fill, outline=outline, width=width * ss)

def chip(c, txt, x, y, size=26, fg=D.PAPER, bg=(0, 0, 0), bga=.62, kind='mono', track=.06, alpha=1.0, anchor='l', dot=None, scale=1.0):
    a = D.text_rgba(txt, kind, size, fg, track=track, pad=2); th, tw = a.shape[:2]; pad = int(size * .55); dw = int(size * .9) if dot else 0
    w = tw + 2 * pad + dw; h = th + int(size * .5)
    if scale != 1: pass
    x0 = x if anchor == 'l' else x - w / 2 if anchor == 'c' else x - w
    D.vector(c, lambda d, ss, ox, oy: rrect(d, ss, ox, oy, x0, y, w, h, h / 2 if size < 40 else 10, fill=tuple(bg) + (int(255 * bga * alpha),)), bbox=(x0 - 2, y - 2, w + 4, h + 4))
    if dot is not None:
        D.vector(c, lambda d, ss, ox, oy: d.ellipse([(x0 + pad - ox) * ss, (y + h / 2 - size * .17 - oy) * ss, (x0 + pad + size * .34 - ox) * ss, (y + h / 2 + size * .17 - oy) * ss], fill=tuple(dot) + (int(255 * alpha),)), bbox=(x0, y, w, h))
    D.paste(c, D.alpha_mul(a, alpha), x0 + pad + dw, y + int(size * .22))
    return w, h

def tc_str(sec):
    s = max(0, sec); return f'{int(s // 3600):02d}:{int(s // 60 % 60):02d}:{int(s % 60):02d}:{int((s % 1) * FPS):02d}'

def reticle(c, box, col, label=None, size=22):
    x, y, w, h = box; D.vector(c, lambda d, ss, ox, oy: D.brackets(d, ss, ox, oy, x, y, w, h, min(w, h) * .22, col, 3), bbox=(x - 6, y - 6, w + 12, h + 12))
    if label: D.draw_text(c, label, 'mono', size, x, y - size * 1.9, col, track=.08)

def motion_box(prev, cur, box):
    """Bounding box (in canvas px) of where consecutive frames change most - a tracked reticle that follows real motion."""
    a = np.asarray(Image.fromarray(prev).convert('L').resize((64, 36), Image.BOX), np.float32); b = np.asarray(Image.fromarray(cur).convert('L').resize((64, 36), Image.BOX), np.float32)
    d = np.abs(a - b); thr = max(6.0, np.percentile(d, 92)); ys, xs = np.where(d >= thr)
    if len(xs) < 3: return None
    x0, x1, y0, y1 = np.percentile(xs, 8), np.percentile(xs, 92), np.percentile(ys, 8), np.percentile(ys, 92)
    bx, by, bw, bh = box; sx, sy = bw / 64, bh / 36
    return (bx + x0 * sx, by + y0 * sy, max(70, (x1 - x0 + 1) * sx), max(70, (y1 - y0 + 1) * sy))

def gradient_v(c, y0, y1, a0, a1, color=(0, 0, 0)):
    y0, y1 = int(max(0, y0)), int(min(H, y1))
    if y1 <= y0: return
    k = np.linspace(a0, a1, y1 - y0, dtype=np.float32)[:, None, None]
    c[y0:y1] = (c[y0:y1] * (1 - k) + np.array(color, np.float32) * k).astype(np.uint8)

# ---------- captions ----------
def caption_chunks(SB):
    """Split each line into 2-4 word caption chunks at punctuation; returns [(t0, t1, [(word, ws, we)...])]."""
    out = []
    for n, ws in SB['W'].items():
        cur = []
        for i, w in enumerate(ws):
            cur.append(w)
            end = w[0][-1] in '.?!,' or len(cur) >= 4 or (len(cur) >= 3 and i + 1 < len(ws) and len(ws[i + 1][0]) > 8)
            if end or i == len(ws) - 1:
                if len(cur) == 1 and out and out[-1][2][0][0] and len(out[-1][2]) < 3 and n == out[-1][3] and out[-1][2][-1][0][-1] not in '.?!': out[-1][2].extend(cur)
                else: out.append([cur[0][1], cur[-1][2], cur, n])
                cur = []
    # hold each chunk until next starts (max 0.35s past its last word)
    for i, ch in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else ch[1] + .4
        ch[1] = min(max(ch[1] + .12, ch[1]), nxt if nxt - ch[1] < .5 else ch[1] + .35)
    return out

def draw_caption(c, t, chunks, accent, off=0):
    for t0, t1, ws, n in chunks:
        if not (t0 - .04 <= t < t1): continue
        txt = ' '.join(w[0] for w in ws); size = 64
        while D.text_w(txt, 'bold', size, -.005) > 940 and size > 40: size -= 2
        tw = D.text_w(txt, 'bold', size, -.005); x = (W - tw) / 2; y = D.CAP_Y + off
        pop = ease_out(prog(t, t0 - .04, t0 + .10)); sc = lerp(.94, 1.0, pop)
        for (w, ws_, we_) in ws:
            ww = D.text_w(w, 'bold', size, -.005); active = ws_ - .03 <= t < we_ + .06
            spc = D.text_w(' ', 'bold', size, -.005)
            col = accent if active else D.PAPER
            D.draw_text(c, w, 'bold', size, x - 8, y - 8, col, track=-.005, stroke=0, shadow=7, alpha=min(1, pop + .2), scale=1.0)
            x += ww + spc
        return

# ---------- transitions ----------
_gx = _gy = None
def _grids():
    global _gx, _gy
    if _gx is None: _gy, _gx = np.mgrid[0:H, 0:W].astype(np.float32)
    return _gx, _gy

def blend_mask(a, b, m):
    m = m[..., None]; return (a * (1 - m) + b * m).astype(np.uint8)

def transition(kind, a, b, p, ring=D.PAPER):
    """a = outgoing frame, b = incoming frame, p in 0..1."""
    if kind == 'cut': return b if p >= .5 else a
    if kind == 'flash':
        f = 1 - abs(p * 2 - 1); base = b if p >= .5 else a; return (base * (1 - f) + 255 * f).astype(np.uint8)
    if kind == 'dip':
        f = 1 - abs(p * 2 - 1); base = b if p >= .5 else a; return (base * (1 - f)).astype(np.uint8)
    if kind == 'glitch':
        out = (b if p > .35 else a).copy(); rng = np.random.default_rng(int(p * 977))
        for _ in range(7):
            y0 = int(rng.integers(0, H - 80)); hh = int(rng.integers(20, 140)); dx = int(rng.integers(-90, 90))
            out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], dx, 1)
        return D.chroma(out, int(14 * (1 - p)))
    if kind == 'whip':
        e = ease_io(p); off = int(e * W * 1.05)
        cat = np.concatenate([a, b], 1); win = cat[:, off:off + W]
        return D.motion_blur_h(win, int(260 * np.sin(np.pi * clamp(p))) + 2)
    if kind == 'zoomthrough':
        e = ease_io(p)
        if p < .5: return D.motion_blur_h(D.scale_about(a, 1 + 1.6 * ease_io(p * 2)), 0) if False else _radial(D.scale_about(a, 1 + 1.4 * ease_io(p * 2)), ease_io(p * 2))
        return _radial(D.scale_about(b, 1 + .35 * (1 - ease_io((p - .5) * 2))), 1 - ease_io((p - .5) * 2))
    if kind in ('iris', 'iris_in'):
        gx, gy = _grids(); r = np.sqrt((gx - W / 2) ** 2 + (gy - H * .46) ** 2); rad = ease_io(p) * 1250
        edge = 3.0; m = np.clip((rad - r) / edge + .5, 0, 1); out = blend_mask(a, b, m)
        ringm = np.clip(1 - np.abs(r - rad) / 5.0, 0, 1) * (1 - abs(p * 2 - 1) * .3) * (1 if 0 < p < 1 else 0)
        return (out * (1 - ringm[..., None]) + np.array(ring, np.float32) * ringm[..., None]).astype(np.uint8)
    if kind == 'slat':
        gx, gy = _grids(); n = 9; u = ((gx + gy * .55) / (W + H * .55)) * n; fr = u - np.floor(u)
        m = np.clip((p * 1.35 - (np.floor(u) / n) * .35 - 0.0) * 6 - fr * 5 * 0 , 0, 1)
        m = np.clip((p * (1 + .3) - (np.floor(u) / n) * .3) * 1.0 - 0.0, 0, 1); m = np.clip((m - fr * .0) * 1.0, 0, 1)
        m2 = np.clip(p * 1.6 - fr * .6 - np.floor(u) / n * .5, 0, 1); return blend_mask(a, b, np.clip(m2 * 1.5, 0, 1))
    return b if p >= .5 else a

def _radial(img, k):
    """Cheap radial zoom blur: blend a few progressively scaled copies."""
    if k < .05: return img
    acc = img.astype(np.float32); n = 4
    for i in range(1, n + 1): acc += D.scale_about(img, 1 + k * .05 * i).astype(np.float32)
    return (acc / (n + 1)).astype(np.uint8)

# ---------- post ----------
def finish(c, t, style, frame_idx, flash=0.0):
    """style: 'early' | 'now' | 'neutral'"""
    if style == 'early': c = D.grade(c, sat=.78, contrast=.94, lift=.025, tint=(1.04, .99, .93)); amp = 9
    elif style == 'now': c = D.grade(c, sat=1.06, contrast=1.07, lift=0.0, tint=(1.0, 1.0, 1.02)); amp = 3.2
    else: amp = 5
    c = D.vignette(c, .30 if style == 'now' else .40); c = D.grain(c, amp, frame_idx)
    if flash > 0: c = (c * (1 - flash) + 255 * flash).astype(np.uint8)
    return c

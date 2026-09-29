"""Footage access: streaming 30 fps decoder over ffmpeg pipes, excerpts (clip + in/out), stills, audio envelopes.

Everything is addressed by *excerpt id* from data/edit_plan.json:
  "excerpts": { "sora_tokyo_a": {"clip": "sora_tokyo_walk", "in": 3.2, "out": 8.0, "label": {...}} }
  "clips":    { "sora_tokyo_walk": {"local": "...", "width":1920, "height":1080, "fps":30, "duration":60.0, "cuts":[...], "overlays":[...], "license":..., ...} }
"""
import json, os, subprocess
import numpy as np
from .tokens import FPS

FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')


class Stream:
    """Sequential RGB reader (fps-normalised) on an ffmpeg pipe; keeps the last 4 frames, restarts when asked to go backwards or far ahead."""
    def __init__(self, path, t_in, w, h):
        self.path, self.t_in, self.w, self.h = path, t_in, w, h; self.fsz = w * h * 3
        self.p = None; self.base = 0; self.buf = []; self.eof = False; self._start(0)

    def _start(self, idx):
        self.close(); self.base = idx; self.buf = []; self.eof = False
        ss = max(0.0, self.t_in + idx / FPS)
        self.p = subprocess.Popen([FFMPEG, '-v', 'error', '-threads', '2', '-ss', f'{ss:.3f}', '-i', self.path, '-an', '-vf', f'fps={FPS},scale={self.w}:{self.h}:flags=bicubic',
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
        if not self.buf and idx > 0:                                       # seek landed after the last source frame (low-fps sources): restart earlier and hold the last frame
            for back in (8, 30, 90):
                self._start(max(0, idx - back))
                while not self.eof:
                    f = self._read()
                    if f is None: break
                    self.buf.append(f)
                    if len(self.buf) > 4: self.buf.pop(0); self.base += 1
                if self.buf: break
        if not self.buf: raise RuntimeError(f'no frame decoded from {self.path} at {self.t_in + idx / FPS:.2f}s (unreadable file or seek past the end)')
        return self.buf[min(idx - self.base, len(self.buf) - 1)] if idx >= self.base else self.buf[0]


class Excerpt:
    def __init__(self, F, eid, spec):
        self.F, self.id, self.spec = F, eid, spec
        self.clip = F.clips[spec['clip']]; self.t_in = float(spec['in']); self.t_out = float(spec['out'])
        self.dur = self.t_out - self.t_in; self.label = spec.get('label', {}); self.meta = self.clip

    def src_time(self, u, speed=1.0, loop=False):
        u = u * speed
        if loop and self.dur > 0: u = u % self.dur
        return self.t_in + min(max(u, 0.0), max(0.0, self.dur - 1e-3))

    def frame(self, u, speed=1.0, max_h=1080, loop=False):
        return self.F.frame(self.spec['clip'], self.t_in, self.src_time(u, speed, loop), max_h=max_h)

    @property
    def aspect(self): return self.clip['width'] / self.clip['height']


class Footage:
    def __init__(self, plan_path, media_dir=None, max_streams=8):
        self.plan_dir = os.path.dirname(os.path.abspath(plan_path)); self.plan = json.load(open(plan_path)); self.clips = self.plan['clips']; self.exs = self.plan['excerpts']
        self.media_dir = media_dir; self.streams = {}; self.max_streams = max_streams; self._still = {}; self._ex = {}; self._env = {}

    def path(self, cid):
        c = self.clips[cid]; p = c.get('local', '')
        if self.media_dir: p = os.path.join(self.media_dir, os.path.basename(p))
        if not os.path.exists(p):                                       # plan paths are relative to the work dir that holds media/ (parent of data/)
            for base in (self.plan_dir, os.path.dirname(self.plan_dir)):
                q = os.path.join(base, p)
                if os.path.exists(q): p = q; break
            else: raise FileNotFoundError(f'footage for clip {cid} not found: {p} (plan dir {self.plan_dir})')     # never render black silently
        return p

    def ex(self, eid):
        if eid not in self._ex: self._ex[eid] = Excerpt(self, eid, self.exs[eid])
        return self._ex[eid]

    def frame(self, cid, t_in, src_t, max_h=1080):
        m = self.clips[cid]; dh = max(2, min(m['height'], max_h) // 2 * 2); dw = int(round(dh * m['width'] / m['height'] / 2)) * 2
        key = (cid, round(t_in, 3), dw, dh); st = self.streams.get(key)
        if st is None:
            while len(self.streams) >= self.max_streams: self.streams.pop(next(iter(self.streams))).close()
            st = self.streams[key] = Stream(self.path(cid), t_in, dw, dh)
        else:                                     # LRU: refresh position
            self.streams[key] = self.streams.pop(key)
        x = (src_t - t_in) * FPS; i = int(np.floor(x)); a = x - i; f0 = st.get(i)
        if a > 0.08:
            f1 = st.get(i + 1)
            if f1 is not f0: return (f0 * (1 - a) + f1 * a).astype(np.uint8)
        return f0

    def still(self, cid, t, max_h=540):
        k = (cid, round(t, 2), max_h)
        if k not in self._still:
            m = self.clips[cid]; dh = max(2, min(m['height'], max_h) // 2 * 2); dw = int(round(dh * m['width'] / m['height'] / 2)) * 2
            b = subprocess.run([FFMPEG, '-v', 'error', '-ss', f'{t:.2f}', '-i', self.path(cid), '-frames:v', '1', '-vf', f'scale={dw}:{dh}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
            if len(b) != dw * dh * 3: raise RuntimeError(f'still of clip {cid} at {t:.2f}s failed ({len(b)} bytes)')
            self._still[k] = np.frombuffer(b, np.uint8).reshape(dh, dw, 3).copy()
        return self._still[k]

    def audio_env(self, cid, t_in, n_frames):
        """Loudness envelope 0..1 at 30 fps from the clip's own audio track (None if silent/no audio)."""
        k = (cid, round(t_in, 2), n_frames)
        if k not in self._env:
            b = subprocess.run([FFMPEG, '-v', 'error', '-ss', f'{t_in:.2f}', '-i', self.path(cid), '-vn', '-ac', '1', '-ar', '8000', '-t', f'{n_frames / FPS + .2:.2f}', '-f', 's16le', '-'], capture_output=True).stdout
            a = np.frombuffer(b, '<i2').astype(np.float32) / 32768 if len(b) > 800 else None
            if a is not None and a.std() > 1e-4:
                spf = 8000 // FPS; nn = len(a) // spf; e = np.sqrt((a[:nn * spf].reshape(nn, spf) ** 2).mean(1)); self._env[k] = (e / (np.percentile(e, 95) + 1e-6)).clip(0, 1)
            else: self._env[k] = None
        return self._env[k]

    def close(self):
        for s in self.streams.values(): s.close()
        self.streams = {}

#!/usr/bin/env python3
"""Original score + sound design, synthesised from scratch with numpy (no samples => nothing to license), then mixed with the narration.
The score is a sonic metaphor for the story: the arpeggio starts bit-crushed and low-rate (early AI video) and slowly resolves to full fidelity.
Usage: synth_audio.py --vo vo.json --vo-dir vo_clean --out mix_raw.wav [--stems DIR]"""
import argparse, json, os, subprocess, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storyboard

SR = 48000
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
rng = np.random.default_rng(11)
clamp = lambda x, a=0., b=1.: min(b, max(a, x))
prog = lambda t, a, b: clamp((t - a) / max(1e-9, b - a))
mtof = lambda m: 440.0 * 2 ** ((m - 69) / 12)

# ---------------------------------------------------------------- DSP helpers
def fft_shape(x, fn):
    n = len(x); nf = 1 << int(np.ceil(np.log2(max(n, 8)))); X = np.fft.rfft(x, nf); f = np.fft.rfftfreq(nf, 1 / SR)
    return np.fft.irfft(X * fn(f), nf)[:n].astype(np.float32)
def lowpass(x, fc, order=2): return fft_shape(x, lambda f: 1 / (1 + (f / fc) ** (2 * order)))
def highpass(x, fc, order=2): return fft_shape(x, lambda f: (f / fc) ** (2 * order) / (1 + (f / fc) ** (2 * order)))
def bandpass(x, f0, q=2.0): return fft_shape(x, lambda f: 1 / (1 + ((f - f0) / (f0 / q)) ** 2))
def tarr(n): return np.arange(n, dtype=np.float32) / SR
def exp_env(n, tau): return np.exp(-tarr(n) / tau)
def fade(x, a=.003, b=.01):
    x = x.copy(); na, nb = int(a * SR), int(b * SR)
    if na: x[:na] *= np.linspace(0, 1, na)
    if nb: x[-nb:] *= np.linspace(1, 0, nb)
    return x

def reverb_ir(rt60, seed, pre=.018, damp=5500):
    r = np.random.default_rng(seed); n = int(rt60 * SR); t = tarr(n)
    ir = r.standard_normal(n).astype(np.float32) * np.exp(-6.9 * t / rt60); ir = lowpass(ir, damp, 1)
    return np.concatenate([np.zeros(int(pre * SR), np.float32), ir]) * (1 / np.sqrt(np.sum(ir ** 2)))
def convolve(x, ir):
    n = len(x) + len(ir); nf = 1 << int(np.ceil(np.log2(n))); return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:len(x)].astype(np.float32)
def reverb_st(x, rt60=1.8, wet=.2):
    return np.stack([x * (1 - wet) + convolve(x, reverb_ir(rt60, 1)) * wet * 1.0, x * (1 - wet) + convolve(x, reverb_ir(rt60, 2)) * wet * 1.0])
def crush(x, div, bits):
    y = np.repeat(x[::max(1, int(div))], max(1, int(div)))[:len(x)]; q = 2 ** (bits - 1); return np.round(y * q) / q

class Bus:
    def __init__(self, n): self.n = n; self.buf = np.zeros((2, n), np.float32)
    def add(self, sig, t0, gain=1.0, pan=0.0):
        if sig.ndim == 1: sig = np.stack([sig * np.sqrt(.5 * (1 - pan)), sig * np.sqrt(.5 * (1 + pan))])
        i = int(round(t0 * SR)); a = max(0, -i); j = min(self.n, i + sig.shape[1])
        if j > max(i, 0): self.buf[:, max(i, 0):j] += sig[:, a:a + (j - max(i, 0))] * gain

def saw_add(f, dur, n_part=14, tilt=1.2, vib=0.0):
    """Band-limited saw by additive synthesis from a frequency array (Hz per sample) - alias-free."""
    ph = 2 * np.pi * np.cumsum(f) / SR; out = np.zeros(len(f), np.float32)
    for k in range(1, n_part + 1):
        out += np.sin(k * ph).astype(np.float32) / k ** tilt * (k * f.max() < 0.45 * SR)
    return out

# ---------------------------------------------------------------- SFX
def sfx_impact(size=1.0):
    n = int(2.6 * SR); t = tarr(n); f = 38 + 60 * np.exp(-t / .09); sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .9)
    thump = np.sin(2 * np.pi * np.cumsum(70 + 160 * np.exp(-t / .03)) / SR) * np.exp(-t / .16)
    noise = lowpass(rng.standard_normal(n).astype(np.float32), 2600, 1) * np.exp(-t / .28); air = highpass(rng.standard_normal(n).astype(np.float32), 5000, 1) * np.exp(-t / .5) * .25
    x = (sub * .95 + thump * .7 + noise * .55 + air * .3) * size
    return reverb_st(fade(x.astype(np.float32), .0005, .05), 2.4, .28) * .9
def sfx_hit():
    n = int(.9 * SR); t = tarr(n); x = np.sin(2 * np.pi * np.cumsum(50 + 130 * np.exp(-t / .03)) / SR) * np.exp(-t / .22) + highpass(rng.standard_normal(n).astype(np.float32), 1800, 1) * np.exp(-t / .07) * .5
    return reverb_st(fade(x.astype(np.float32), .0005, .03), 1.0, .15) * .7
def swept_noise(dur, f0, f1, q=1.6, blocks=14, seed=0):
    r = np.random.default_rng(seed); n = int(dur * SR); noise = r.standard_normal(n).astype(np.float32); out = np.zeros(n, np.float32); bl = n // blocks * 2
    w = np.hanning(bl).astype(np.float32); hop = bl // 2
    for i in range(blocks):
        s = i * hop; seg = noise[s:s + bl]
        if len(seg) < bl: break
        fc = f0 * (f1 / f0) ** (i / max(1, blocks - 1)); out[s:s + bl] += bandpass(seg, fc, q) * w
    return out / (np.abs(out).max() + 1e-9)
def sfx_whoosh(dur=.4, up=False):
    x = swept_noise(dur, 400, 3600, 1.2, seed=3) if up else swept_noise(dur, 3600, 400, 1.2, seed=4)
    n = len(x); env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6; return reverb_st(fade(x * env * .8, .01, .05), 1.2, .18) * .8
def sfx_riser(dur=1.0):
    n = int(dur * SR); t = tarr(n); x = swept_noise(dur, 300, 7000, .9, blocks=18, seed=5) * np.linspace(.05, 1, n) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (t / dur * 2.6)) / SR) * np.linspace(0, 1, n) ** 3 * .35
    return reverb_st(fade((x * .8 + tone) * .8, .01, .02), 1.4, .15) * .75
def sfx_glitch():
    n = int(.11 * SR); t = tarr(n); f = rng.uniform(300, 2200); x = np.sign(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 70 * t) * 3)) * (rng.random(n) > .25)
    x = crush(x.astype(np.float32) * .5 + rng.standard_normal(n).astype(np.float32) * .15, 6, 6) * np.exp(-t / .05)
    return np.stack([x, np.roll(x, 13)]) * .6
def sfx_tape_stop(dur=.55):
    n = int(dur * SR); t = tarr(n); f = 190 * np.exp(-t / dur * 3.4); x = saw_add(f, dur, 10, 1.0) * np.linspace(1, 0, n) ** .8 * .45
    x += rng.standard_normal(n).astype(np.float32) * .05 * np.linspace(1, 0, n); return np.stack([x, x]) * .8
def sfx_chime(f=523.25):
    n = int(1.8 * SR); t = tarr(n); m = 2 * np.exp(-t / .5)
    x = (np.sin(2 * np.pi * f * t + m * np.sin(2 * np.pi * f * 2.01 * t)) * np.exp(-t / .5) * .6 + np.sin(2 * np.pi * f * 3.98 * t) * np.exp(-t / .12) * .15).astype(np.float32)
    return reverb_st(fade(x, .002, .1), 2.0, .3) * .55
def sfx_tick(n_ticks=1, span=0.0, base=3300):
    out = np.zeros((2, int((span + .2) * SR)), np.float32)
    for i in range(n_ticks):
        t0 = i * span / max(1, n_ticks - 1) if n_ticks > 1 else 0; t0 += rng.uniform(-.012, .012) if n_ticks > 1 else 0; t0 = max(0, t0)
        n = int(.012 * SR); t = tarr(n); f = base * rng.uniform(.85, 1.2); x = (np.sin(2 * np.pi * f * t) * np.exp(-t / .0025) + rng.standard_normal(n).astype(np.float32) * .3 * np.exp(-t / .002)) * .5
        j = int(t0 * SR); out[:, j:j + n] += x[None, :]
    return out * .7
def sfx_shutter():
    out = np.zeros((2, int(.35 * SR)), np.float32)
    for k, (t0, a) in enumerate(((0, 1.0), (.045, .7))):
        n = int(.03 * SR); t = tarr(n); x = highpass(rng.standard_normal(n).astype(np.float32), 1200, 1) * np.exp(-t / .006) * a + np.sin(2 * np.pi * 220 * t) * np.exp(-t / .012) * .5 * a
        j = int(t0 * SR); out[:, j:j + n] += x[None, :]
    return reverb_st(out[0], .5, .12) * .8
def sfx_sub_drop():
    n = int(2.2 * SR); t = tarr(n); x = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t / .9) + 22) / SR) * np.exp(-t / .8); return np.stack([x, x]).astype(np.float32) * .9

def make_sfx(ev):
    k, p = ev[0], ev[2]
    if k == 'impact': return sfx_impact(p.get('size', 1))
    if k == 'hit': return sfx_hit()
    if k == 'whoosh': return sfx_whoosh(p.get('dur', .4), p.get('up', False))
    if k == 'riser': return sfx_riser(p.get('dur', 1.0))
    if k == 'glitch': return sfx_glitch()
    if k == 'tape_stop': return sfx_tape_stop(p.get('dur', .55))
    if k == 'chime': return sfx_chime(p.get('f', 523.25))
    if k == 'tick': return sfx_tick(p.get('n', 1), p.get('span', 0))
    if k == 'tick_hi': return sfx_tick(1, 0, 5200) * .5
    if k == 'shutter': return sfx_shutter()
    if k == 'sub_drop': return sfx_sub_drop()
    raise KeyError(k)

# ---------------------------------------------------------------- music
def chord_notes(root, kind): return [root + i for i in ({'m': (0, 3, 7), 'M': (0, 4, 7), 'm7': (0, 3, 7, 10)}[kind])]
PROG = [(50, 'm'), (46, 'M'), (53, 'M'), (48, 'M')]        # Dm | Bb | F | C   (root MIDI)
BEAT = .6

def drone(total, cues):
    n = int(total * SR); t = tarr(n); out = np.zeros((2, n), np.float32)
    lvl = np.interp(t, [0, 3.6, 13, 38, 46, 64.5, 70.5, total], [.55, .5, .55, .6, .35, .45, .6, .0])
    sweep = np.interp(t, [0, 13, 38, 49, 64.5, total], [140, 260, 700, 1300, 500, 900])
    for ch, det in ((0, .996), (1, 1.004)):
        f = np.full(n, 36.71 * det, np.float32) * (1 + .0025 * np.sin(2 * np.pi * .17 * t + ch)); ph = 2 * np.pi * np.cumsum(f) / SR; x = np.zeros(n, np.float32)
        for k in range(1, 13): x += np.sin(k * ph + k).astype(np.float32) / k ** 1.1 * (1 / (1 + (k * 36.7 / sweep) ** 4))
        out[ch] = x * lvl * .45
    # unsettling high cluster (a minor second beating), fades as the story resolves
    hi = (np.sin(2 * np.pi * 830.6 * t) + np.sin(2 * np.pi * 784 * t + 1.1) * .9) * (1 + .5 * np.sin(2 * np.pi * 5.1 * t)) * np.interp(t, [0, 3.6, 13, 30, 38.3], [.010, .022, .028, .012, 0]) * (t < 38.5)
    out[0] += hi.astype(np.float32); out[1] += np.roll(hi, 900).astype(np.float32)
    return out

def heartbeat(total):
    out = np.zeros((2, int(total * SR)), np.float32)
    for t0 in np.arange(3.7, 13.0, 1.0):
        for d, g in ((0, 1.0), (.27, .6)):
            n = int(.35 * SR); t = tarr(n); x = np.sin(2 * np.pi * np.cumsum(46 + 40 * np.exp(-t / .04)) / SR) * np.exp(-t / .1) * g * .55
            i = int((t0 + d) * SR); out[:, i:i + n] += x[None]
    return out

def pluck(m, dur, crush_div, bits, bright=1.0):
    n = int(dur * SR); t = tarr(n); f = mtof(m); x = np.zeros(n, np.float32)
    for k, a in enumerate((1, .55, .32, .2, .12, .07), 1): x += a * np.sin(2 * np.pi * f * k * t + k) * np.exp(-t / (.22 / (1 + .35 * (k - 1))) / bright * 1.0)
    x = x * np.minimum(1, t / .004)
    if crush_div > 1 or bits < 15: x = crush(x, crush_div, bits)
    return x

def arp(total, t_a=13.0, t_b=59.0):
    """Minor arpeggio in 8ths (0.3 s); bit-crush and sample-rate reduction relax as the story moves from early AI video to today."""
    bus = Bus(int(total * SR)); step = BEAT / 2; k = 0; t = t_a
    pattern = [0, 2, 1, 2, 0, 2, 1, 2]
    while t < t_b:
        bar = int((t - t_a) / (BEAT * 4)) % 4; root, kind = PROG[bar]; ns = chord_notes(root + 12, kind) + [root + 24]
        m = ns[pattern[k % 8] % 4] + (12 if (k // 8) % 4 == 3 else 0)
        p = prog(t, t_a, 46.0); div = int(round(11 - 10 * p ** .8)); bits = 5 + 11 * p
        g = np.interp(t, [t_a, 20, 38, 46, 59], [.16, .2, .24, .3, .3]) * (1 if k % 4 else 1.15)
        bus.add(pluck(m, .9, div, bits), t, g, pan=(-.35 if k % 2 else .35)); k += 1; t += step
    return bus.buf

def pad(total, t_a, t_b, tail=2.5, level=.16, chords=None, open_=True):
    n = int((t_b - t_a + tail) * SR); out = np.zeros((2, n), np.float32); t = tarr(n); seg = BEAT * 4; nseg = int(np.ceil((t_b - t_a) / seg)); chords = chords or PROG
    for s in range(nseg):
        root, kind = chords[s % len(chords)]; i0 = int(s * seg * SR); i1 = min(n, int((s + 1) * seg * SR + tail * SR * .5)); m = i1 - i0; tt = tarr(m)
        env = np.minimum(1, tt / 1.0) * np.clip((seg + tail * .5 - tt) / (tail * .5), 0, 1)
        for note in chord_notes(root + 12, kind):
            for ch, det in ((0, .997), (1, 1.003)):
                f = np.full(m, mtof(note) * det, np.float32) * (1 + .002 * np.sin(2 * np.pi * .3 * tt + ch + note))
                x = saw_add(f, 0, 9, 1.4); out[ch, i0:i1] += lowpass(x * env, 1800, 1) * .12
    return out * level

def drums(total, t_a, t_b, kick_from=None):
    bus = Bus(int(total * SR)); t = t_a; i = 0
    while t < t_b:
        beat = i % 4
        if kick_from is None or t >= kick_from:
            n = int(.4 * SR); tt = tarr(n); k = np.sin(2 * np.pi * np.cumsum(42 + 110 * np.exp(-tt / .022)) / SR) * np.exp(-tt / .17); k[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR)); bus.add(k.astype(np.float32), t, .85)
        if beat in (1, 3):
            n = int(.25 * SR); tt = tarr(n); cl = bandpass(rng.standard_normal(n).astype(np.float32), 1600, .8) * np.exp(-tt / .06); bus.add(reverb_st(cl, .6, .2), t, .32)
        for off in (BEAT / 2,):
            n = int(.08 * SR); tt = tarr(n); h = highpass(rng.standard_normal(n).astype(np.float32), 7500, 1) * np.exp(-tt / .018); bus.add(h, t + off, .13 * (1.0 if beat % 2 else .7), pan=.2)
        t += BEAT; i += 1
    return bus.buf

def bassline(total, t_a, t_b):
    bus = Bus(int(total * SR)); t = t_a; k = 0; step = BEAT / 2
    while t < t_b:
        bar = int((t - t_a) / (BEAT * 4)) % 4; root, _ = PROG[bar]; m = root - 12 + (12 if k % 8 == 6 else 0)
        n = int(.28 * SR); tt = tarr(n); f = mtof(m); x = (np.sin(2 * np.pi * f * tt) + .35 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / .18); bus.add(x.astype(np.float32), t, .3); t += step; k += 1
    return bus.buf

def build_music(total, SB):
    cu = SB['cues']; f = cu['finale']; sc = {s['name']: s for s in SB['scenes']}
    bus = np.zeros((2, int(total * SR)), np.float32); add = lambda x: bus.__iadd__(x[:, :bus.shape[1]] if x.shape[1] >= bus.shape[1] else np.pad(x, ((0, 0), (0, bus.shape[1] - x.shape[1]))))
    add(drone(total, cu)); add(heartbeat(total) * 1.0)
    add(arp(total, 13.0, sc['compare']['t1'] - .05))
    p = pad(total, sc['concept']['t0'] - 1.0, sc['compare']['t1'], 1.5, .22); off = int((sc['concept']['t0'] - 1.0) * SR); m = min(p.shape[1], bus.shape[1] - off); bus[:, off:off + m] += p[:, :m]
    # beat: builds through concept, full through now/styles/compare
    k0 = sc['concept']['t0'] + 3.0
    add(drums(total, k0, sc['compare']['t1'] - .05, kick_from=sc['now']['t0'] - .0) * np.interp(np.arange(int(total * SR)) / SR, [k0, sc['now']['t0'], sc['compare']['t1']], [.35, 1, 1])[None, :])
    add(bassline(total, sc['now']['t0'], sc['compare']['t1'] - .05))
    # finale: sparse pad, then a major-key swell (D major) on the render
    p = pad(total, f['start'], f['render'], 1.0, .2, chords=[(50, 'm'), (46, 'M'), (50, 'm'), (57, 'm')]); off = int(f['start'] * SR); m = min(p.shape[1], bus.shape[1] - off); bus[:, off:off + m] += p[:, :m]
    sw = pad(total, f['render'], total, .2, .34, chords=[(50, 'M')]); off = int(f['render'] * SR); m = min(sw.shape[1], bus.shape[1] - off); bus[:, off:off + m] += sw[:, :m]
    bus = np.stack([reverb_st(bus[0], 2.2, .16)[0], reverb_st(bus[1], 2.2, .16)[1]])
    return bus

# ---------------------------------------------------------------- narration
def load_wav(path):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768; sr = w.getframerate()
    p = subprocess.run([FFMPEG, '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True); return np.frombuffer(p.stdout, np.float32).copy()

def vo_chain(x):
    x = highpass(x, 75, 2)
    x = x + .55 * fft_shape(x, lambda f: np.exp(-((np.log2(np.maximum(f, 1) / 3200)) ** 2) / .5))            # presence
    x = x + .25 * highpass(x, 6500, 1) * 0                                                                     # (air left alone: source is 24 kHz)
    hop = int(.01 * SR); n = len(x) // hop; e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-9); db = 20 * np.log10(e); gr = np.clip((db - (-24)) * (1 - 1 / 3.0), 0, 12)
    g = np.interp(np.arange(len(x)), np.arange(n) * hop + hop / 2, 10 ** (-gr / 20)); return (x * g).astype(np.float32)

def duck_curve(vo, depth=.55):
    hop = int(.02 * SR); n = len(vo) // hop; e = np.sqrt((vo[:n * hop].reshape(n, hop) ** 2).mean(1)); e = np.clip(e / .05, 0, 1)
    sm = np.zeros(n, np.float32); a_att, a_rel = .5, .06
    for i in range(1, n): sm[i] = sm[i - 1] + (a_att if e[i] > sm[i - 1] else a_rel) * (e[i] - sm[i - 1])
    return np.interp(np.arange(len(vo)), np.arange(n) * hop + hop / 2, 1 - depth * np.clip(sm * 1.6, 0, 1)).astype(np.float32)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--vo', required=True); ap.add_argument('--vo-dir', required=True); ap.add_argument('--out', required=True); ap.add_argument('--stems', default='')
    a = ap.parse_args(); SB = storyboard.build(json.load(open(a.vo))); total = SB['total'] + .6; N = int(total * SR)
    print('music...', flush=True); music = build_music(total, SB)
    print('sfx...', flush=True); sfx = Bus(N)
    for ev in SB['sfx']:
        s = make_sfx(ev); sfx.add(s, ev[1], 1.0)
    print('vo...', flush=True); vo = np.zeros(N, np.float32)
    for n in SB['T']:
        x = vo_chain(load_wav(os.path.join(a.vo_dir, f'L{n}.wav'))); i = int(SB['T'][n] * SR); vo[i:i + len(x)] += x[:N - i]
    vo_st = reverb_st(vo, .9, .07)
    duck = duck_curve(vo, .8); mus = music * duck[None, :] * 0.75
    sfx_b = sfx.buf * .5 * (1 - .3 * np.clip(1 - duck, 0, 1))[None, :]
    vo_st = vo_st * 1.6
    mix = mus + sfx_b + vo_st
    # end: hard cut with a 40 ms fade into black
    e = int(SB['total'] * SR); mix[:, e:] *= 0; mix[:, e - int(.04 * SR):e] *= np.linspace(1, 0, int(.04 * SR))[None, :]
    if a.stems:
        os.makedirs(a.stems, exist_ok=True)
    pk = float(np.abs(mix).max()); g = min(1.0, .89 / pk)
    if a.stems:
        for nm, b in (('music', mus), ('sfx', sfx_b), ('vo', vo_st)): write(os.path.join(a.stems, nm + '.wav'), b * g)
    mix = mix * g; write(a.out, mix); print('pre-master peak', pk, 'scaled by', g); print('peak', float(np.abs(mix).max()), 'rms dB', 20 * np.log10(np.sqrt((mix ** 2).mean())))

def write(path, st):
    x = np.clip(st.T, -1, 1);
    with wave.open(path, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype('<i2').tobytes())

if __name__ == '__main__': main()

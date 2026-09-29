"""Original 120-second score (numpy synthesis, nothing to license).
Arc: strange sparse opening (detuned drone + beating minor second, irregular heartbeat) -> rhythm locks in (arpeggio starts bit-crushed and resolves to full fidelity as the story
improves) -> gallery energy (drums, bass) -> cinematic lift for the hero shots (pads, rising motif, drums drop out) -> peak -> controlled resolution that melts back into the opening drone
so the film loops.  100 BPM, 4/4: BEAT = 0.6 s, BAR = 2.4 s, 120 s = 200 beats."""
import numpy as np
from .dsp import *

BPM = 100; BEAT = 60.0 / BPM; BAR = 4 * BEAT
PROG = [(50, 'm'), (46, 'M'), (53, 'M'), (48, 'M')]             # Dm | Bb | F | C  (root MIDI note)
def chord(root, kind): return [root + i for i in ({'m': (0, 3, 7), 'M': (0, 4, 7), 'm7': (0, 3, 7, 10)}[kind])]
def curve(t, pts): xs, ys = zip(*pts); return np.interp(t, xs, ys)

def drone(total):
    n = int(total * SR); t = tarr(n); out = np.zeros((2, n), np.float32)
    lvl = curve(t, [(0, .55), (8, .5), (25, .42), (43, .28), (83, .22), (104, .3), (113, .35), (116, .5), (120, .55)])
    sweep = curve(t, [(0, 150), (25, 300), (43, 800), (83, 1200), (104, 900), (120, 150)])
    for ch, det in ((0, .996), (1, 1.004)):
        f = np.full(n, 36.71 * det, np.float32) * (1 + .0025 * np.sin(2 * np.pi * .17 * t + ch)); ph = 2 * np.pi * np.cumsum(f) / SR; x = np.zeros(n, np.float32)
        for k in range(1, 13): x += np.sin(k * ph + k).astype(np.float32) / k ** 1.1 * (1 / (1 + (k * 36.7 / sweep) ** 4))
        out[ch] = x * lvl * .45
    hi = (np.sin(2 * np.pi * 830.6 * t) + np.sin(2 * np.pi * 784 * t + 1.1) * .9) * (1 + .5 * np.sin(2 * np.pi * 5.1 * t)) * curve(t, [(0, .02), (8, .03), (25, .02), (37, 0), (114, 0), (118, .012), (120, .02)])
    out[0] += hi.astype(np.float32); out[1] += np.roll(hi, 900).astype(np.float32); return out

def heartbeat(total, t_a=8.0, t_b=25.0, lock_at=25.0):
    """Sub pulses; timing jitter melts away as the story approaches the 'lock' at S3."""
    out = np.zeros((2, int(total * SR)), np.float32); r = np.random.default_rng(4); t0 = t_a
    while t0 < t_b + 18:
        jit = r.normal(0, .16) * max(0.0, 1 - max(0.0, t0 - t_a) / (lock_at + 4 - t_a)); tt = t0 + jit
        for d, g in ((0, 1.0), (.27, .6)):
            n = int(.35 * SR); x = np.sin(2 * np.pi * np.cumsum(46 + 40 * np.exp(-tarr(n) / .04)) / SR) * np.exp(-tarr(n) / .1) * g * .5 * curve(tt, [(t_a, .5), (lock_at, 1.0), (t_b + 18, .5)]); i = int((tt + d) * SR)
            if 0 <= i < out.shape[1] - n: out[:, i:i + n] += x[None]
        t0 += BEAT * 2
    return out

def pluck(m, dur, crush_div, bits, bright=1.0):
    n = int(dur * SR); t = tarr(n); f = mtof(m); x = np.zeros(n, np.float32)
    for k, a in enumerate((1, .55, .32, .2, .12, .07), 1): x += a * np.sin(2 * np.pi * f * k * t + k) * np.exp(-t / (.22 / (1 + .35 * (k - 1))) / bright)
    x = x * np.minimum(1, t / .004)
    return crush(x, crush_div, bits) if (crush_div > 1 or bits < 15) else x

def arp(total, t_a=8.0, t_b=115.0, levels=((8, .10), (25, .17), (43, .26), (63, .30), (83, .16), (104, .28), (115, .0))):
    bus = Bus(int(total * SR)); step = BEAT / 2; k = 0; t = t_a; pattern = [0, 2, 1, 2, 0, 2, 1, 2]
    while t < t_b:
        bar = int((t - t_a) / BAR) % 4; root, kind = PROG[bar]; ns = chord(root + 12, kind) + [root + 24]
        m = ns[pattern[k % 8] % 4] + (12 if (k // 8) % 4 == 3 else 0); p = prog(t, t_a, 43.0)
        div = int(round(11 - 10 * p ** .8)); bits = 5 + 11 * p; g = float(curve(t, levels)) * (1 if k % 4 else 1.15)
        bus.add(pluck(m, .9, div, bits), t, g, pan=(-.35 if k % 2 else .35)); k += 1; t += step
    return bus.buf

def pad(total, t_a, t_b, tail=2.0, level=.16, chords=None, bar_offset=0):
    n = int((t_b - t_a + tail) * SR); out = np.zeros((2, n), np.float32); nseg = int(np.ceil((t_b - t_a) / BAR)); chords = chords or PROG
    for s in range(nseg):
        root, kind = chords[(s + bar_offset) % len(chords)]; i0 = int(s * BAR * SR); i1 = min(n, int((s + 1) * BAR * SR + tail * SR * .5)); m = i1 - i0; tt = tarr(m)
        env = np.minimum(1, tt / 1.0) * np.clip((BAR + tail * .5 - tt) / (tail * .5), 0, 1)
        for note in chord(root + 12, kind):
            for ch, det in ((0, .997), (1, 1.003)):
                f = np.full(m, mtof(note) * det, np.float32) * (1 + .002 * np.sin(2 * np.pi * .3 * tt + ch + note)); out[ch, i0:i1] += lowpass(saw_add(f, 0, 9, 1.4) * env, 1800, 1) * .12
    return out * level

def drums(total, t_a, t_b, kick_from=None, kick_every=1, hats=True, level=1.0):
    bus = Bus(int(total * SR)); t = t_a; i = 0; r = np.random.default_rng(9)
    while t < t_b:
        beat = i % 4
        if (kick_from is None or t >= kick_from) and (i % kick_every == 0):
            n = int(.4 * SR); tt = tarr(n); k = np.sin(2 * np.pi * np.cumsum(42 + 110 * np.exp(-tt / .022)) / SR) * np.exp(-tt / .17); k[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR)); bus.add(k.astype(np.float32), t, .8 * level)
        if beat in (1, 3) and (kick_from is None or t >= kick_from):
            n = int(.25 * SR); tt = tarr(n); cl = bandpass(r.standard_normal(n).astype(np.float32), 1600, .8) * np.exp(-tt / .06); bus.add(reverb_st(cl, .6, .2), t, .3 * level)
        if hats:
            n = int(.08 * SR); tt = tarr(n); h = highpass(r.standard_normal(n).astype(np.float32), 7500, 1) * np.exp(-tt / .018); bus.add(h, t + BEAT / 2, .12 * level * (1.0 if beat % 2 else .7), pan=.2)
        t += BEAT; i += 1
    return bus.buf

def bassline(total, t_a, t_b, level=.3):
    bus = Bus(int(total * SR)); t = t_a; k = 0; step = BEAT / 2
    while t < t_b:
        bar = int((t - t_a) / BAR) % 4; root, _ = PROG[bar]; m = root - 12 + (12 if k % 8 == 6 else 0)
        n = int(.28 * SR); tt = tarr(n); f = mtof(m); x = (np.sin(2 * np.pi * f * tt) + .35 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / .18); bus.add(x.astype(np.float32), t, level); t += step; k += 1
    return bus.buf

def motif(t0, total, level=.2):
    """Slow rising four-note figure (D-F-A-D') on a soft saw pad: the 'cinematic lift'."""
    bus = Bus(int(total * SR))
    for j, m in enumerate((62, 65, 69, 74)):
        dur = BEAT * 2.2; n = int(dur * SR); tt = tarr(n); env = np.minimum(1, tt / .25) * np.exp(-tt / (dur * .6)); f = np.full(n, mtof(m), np.float32)
        x = lowpass(saw_add(f, 0, 8, 1.3) * env, 2600, 1) * .3; bus.add(reverb_st(x, 2.0, .3), t0 + j * BEAT * 2, level, pan=-.2 + .13 * j)
    return bus.buf

def build_score(total, gates=(), extra=None):
    """Returns (2, N) float32 music bus.  gates = [(t0, t1), ...] where music is cut (freeze frame silence)."""
    N = int(total * SR); bus = np.zeros((2, N), np.float32)
    def add(x, off=0):
        m = min(x.shape[1], N - off)
        if m > 0: bus[:, off:off + m] += x[:, :m]
    add(drone(total)); add(heartbeat(total)); add(arp(total))
    add(pad(total, 8, 25, 2.0, .05), int(8 * SR)); add(pad(total, 25, 43, 2.0, .11), int(25 * SR)); add(pad(total, 43, 63, 2.0, .10, bar_offset=1), int(43 * SR))
    add(pad(total, 63, 83, 2.0, .10), int(63 * SR)); add(pad(total, 83, 104, 3.0, .30, chords=[(50, 'm'), (46, 'M'), (53, 'M'), (55, 'M')]), int(83 * SR))
    add(pad(total, 104, 115, 3.0, .32), int(104 * SR))
    add(pad(total, 115, 120, .5, .30, chords=[(50, "M")]), int(115 * SR))
    # drums / bass by chapter
    t = np.arange(N) / SR
    add(drums(total, 25, 43, kick_from=33, kick_every=2, level=.6) * curve(t, [(25, .3), (43, .8)])[None, :])
    add(drums(total, 43, 83, kick_from=43, level=1.0)); add(bassline(total, 43, 83, .28))
    add(drums(total, 83, 104, kick_from=83, kick_every=4, hats=False, level=.7) * curve(t, [(83, .6), (104, 1.0)])[None, :])
    add(drums(total, 104, 115, kick_from=104, level=1.1)); add(bassline(total, 104, 115, .32))
    for tm in (83.5, 92.0, 99.5): add(motif(tm, total, .18))
    bus = np.stack([reverb_st(bus[0], 2.2, .16)[0], reverb_st(bus[1], 2.2, .16)[1]])
    for a, b in gates:                                                                  # abrupt audio pause with 10 ms fades
        i, j = int(a * SR), int(b * SR); g = np.ones(N, np.float32); f = int(.01 * SR); g[i:j] = 0; g[max(0, i - f):i] = np.linspace(1, 0, min(f, i)); g[j:j + f] = np.linspace(0, 1, len(g[j:j + f])); bus *= g[None, :]
    return bus

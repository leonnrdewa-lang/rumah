"""Procedural sound-effect library (all original; used alongside licensed CC0 recordings listed in docs/SOURCES).
Every function returns a stereo float32 array at 48 kHz, peak <= ~0.9.  make(kind, **params) is the event entry point."""
import numpy as np
from .dsp import *

def impact(size=1.0, tail=2.6):
    n = int(tail * SR); t = tarr(n); f = 38 + 60 * np.exp(-t / .09); sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .9)
    thump = np.sin(2 * np.pi * np.cumsum(70 + 160 * np.exp(-t / .03)) / SR) * np.exp(-t / .16)
    noise = lowpass(rng.standard_normal(n).astype(np.float32), 2600, 1) * np.exp(-t / .28); air = highpass(rng.standard_normal(n).astype(np.float32), 5000, 1) * np.exp(-t / .5) * .25
    return reverb_st(fade(((sub * .95 + thump * .7 + noise * .55 + air * .3) * size).astype(np.float32), .0005, .05), 2.4, .28) * .55

def hit(size=1.0):
    n = int(.9 * SR); t = tarr(n); x = np.sin(2 * np.pi * np.cumsum(50 + 130 * np.exp(-t / .03)) / SR) * np.exp(-t / .22) + highpass(rng.standard_normal(n).astype(np.float32), 1800, 1) * np.exp(-t / .07) * .5
    return reverb_st(fade((x * size).astype(np.float32), .0005, .03), 1.0, .15) * .5

def whoosh(dur=.4, up=False, gain=1.0):
    x = swept_noise(dur, 400, 3600, 1.2, seed=3) if up else swept_noise(dur, 3600, 400, 1.2, seed=4)
    env = np.sin(np.pi * np.linspace(0, 1, len(x))) ** 1.6; return reverb_st(fade(x * env * .8, .01, .05), 1.2, .18) * .6 * gain

def riser(dur=1.0):
    n = int(dur * SR); t = tarr(n); x = swept_noise(dur, 300, 7000, .9, blocks=18, seed=5) * np.linspace(.05, 1, n) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (t / dur * 2.6)) / SR) * np.linspace(0, 1, n) ** 3 * .35
    return reverb_st(fade((x * .8 + tone) * .8, .01, .02), 1.4, .15) * .55

def glitch():
    n = int(.11 * SR); t = tarr(n); f = rng.uniform(300, 2200); x = np.sign(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 70 * t) * 3)) * (rng.random(n) > .25)
    x = crush(x.astype(np.float32) * .5 + rng.standard_normal(n).astype(np.float32) * .15, 6, 6) * np.exp(-t / .05); return np.stack([x, np.roll(x, 13)]) * .45

def tape_stop(dur=.55):
    n = int(dur * SR); t = tarr(n); f = 190 * np.exp(-t / dur * 3.4); x = saw_add(f, dur, 10, 1.0) * np.linspace(1, 0, n) ** .8 * .45
    x += rng.standard_normal(n).astype(np.float32) * .05 * np.linspace(1, 0, n); return np.stack([x, x]) * .6

def chime(f=523.25):
    n = int(1.8 * SR); t = tarr(n); m = 2 * np.exp(-t / .5)
    x = (np.sin(2 * np.pi * f * t + m * np.sin(2 * np.pi * f * 2.01 * t)) * np.exp(-t / .5) * .6 + np.sin(2 * np.pi * f * 3.98 * t) * np.exp(-t / .12) * .15).astype(np.float32)
    return reverb_st(fade(x, .002, .1), 2.0, .3) * .4

def tick(n_ticks=1, span=0.0, base=3300):
    out = np.zeros((2, int((span + .2) * SR)), np.float32)
    for i in range(int(n_ticks)):
        t0 = i * span / max(1, n_ticks - 1) if n_ticks > 1 else 0; t0 += rng.uniform(-.012, .012) if n_ticks > 1 else 0; t0 = max(0, t0)
        n = int(.012 * SR); t = tarr(n); f = base * rng.uniform(.85, 1.2); x = (np.sin(2 * np.pi * f * t) * np.exp(-t / .0025) + rng.standard_normal(n).astype(np.float32) * .3 * np.exp(-t / .002)) * .5
        j = int(t0 * SR); out[:, j:j + n] += x[None, :]
    return out * .5

def shutter():
    out = np.zeros((2, int(.35 * SR)), np.float32)
    for t0, a in ((0, 1.0), (.045, .7)):
        n = int(.03 * SR); t = tarr(n); x = highpass(rng.standard_normal(n).astype(np.float32), 1200, 1) * np.exp(-t / .006) * a + np.sin(2 * np.pi * 220 * t) * np.exp(-t / .012) * .5 * a
        j = int(t0 * SR); out[:, j:j + n] += x[None, :]
    return reverb_st(out[0], .5, .12) * .6

def sub_drop(dur=2.2):
    n = int(dur * SR); t = tarr(n); x = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t / .9) + 22) / SR) * np.exp(-t / .8); return np.stack([x, x]).astype(np.float32) * .7

# ---- new for film120 -------------------------------------------------------------------------
def lock(f=1760.0, size=1.0):
    """Frame lock: tight tonal click + short sub thump (the 'it snapped into place' sound)."""
    n = int(.6 * SR); t = tarr(n)
    click = (np.sin(2 * np.pi * f * t) * np.exp(-t / .012) + np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / .006) * .5) * .5
    thump = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t / .05) + 46) / SR) * np.exp(-t / .12) * .8
    x = (click + thump * size).astype(np.float32); return reverb_st(fade(x, .0003, .03), .6, .12) * .55

def slide(dur=.5, up=True, gain=1.0):
    """Panel move: soft filtered-noise slide plus a low body; length follows the move."""
    x = swept_noise(dur, 900, 2600, .9, blocks=10, seed=11) * np.hanning(int(dur * SR)) ** 1.3 * .5
    t = tarr(len(x)); body = np.sin(2 * np.pi * np.cumsum(np.linspace(150, 90, len(x)) if up else np.linspace(90, 150, len(x))) / SR) * np.hanning(len(x)) * .25
    return reverb_st(fade((x + body).astype(np.float32), .005, .05), .8, .12) * .6 * gain

def jump(dur=.6, up=True):
    """Timeline jump: pitched sweep with a tick at the landing."""
    n = int(dur * SR); t = tarr(n); f = (300 * 2 ** (t / dur * 2.2)) if up else (1200 * 2 ** (-t / dur * 2.2)); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.hanning(n) ** .8 * .35
    x = x + swept_noise(dur, 500, 5000, 1.1, seed=13) * np.hanning(n) * .18; land = np.zeros(n, np.float32); m = int(.02 * SR); land[-m - int(.01 * SR):-int(.01 * SR)] = np.sin(2 * np.pi * 2400 * tarr(m)) * np.exp(-tarr(m) / .004) * .5
    return reverb_st(fade((x + land).astype(np.float32), .005, .02), .9, .14) * .55

def type_hit(size=1.0):
    """Typographic impact: low hit with air, shorter than a cinematic impact."""
    n = int(1.2 * SR); t = tarr(n); sub = np.sin(2 * np.pi * np.cumsum(46 + 70 * np.exp(-t / .05)) / SR) * np.exp(-t / .35)
    air = highpass(rng.standard_normal(n).astype(np.float32), 3500, 1) * np.exp(-t / .16) * .3; body = lowpass(rng.standard_normal(n).astype(np.float32), 900, 1) * np.exp(-t / .1) * .4
    return reverb_st(fade(((sub + air + body) * size).astype(np.float32), .0005, .05), 1.4, .2) * .55

def data_blip(f=1200.0):
    n = int(.09 * SR); t = tarr(n); x = np.sin(2 * np.pi * f * t) * np.exp(-t / .02) * .5 + np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / .012) * .25; return np.stack([x, x]).astype(np.float32) * .45

def freeze(dur=.4):
    """Freeze-frame: a downward 'suck' into silence (the gate mutes everything else)."""
    n = int(dur * SR); t = tarr(n); f = 900 * np.exp(-t / dur * 3); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.linspace(1, 0, n) ** 2 * .3 + highpass(rng.standard_normal(n).astype(np.float32), 4000, 1) * np.linspace(1, 0, n) ** 3 * .1
    return np.stack([x, x]).astype(np.float32) * .6

def swell(dur=3.0, f=146.83):
    n = int(dur * SR); t = tarr(n); x = sum(np.sin(2 * np.pi * f * k * t + k) / k for k in (1, 2, 3, 4, 5)).astype(np.float32) * np.hanning(n) ** 1.6 * .3
    return reverb_st(lowpass(x, 2500, 1), 2.5, .3) * .6

REGISTRY = dict(impact=impact, hit=hit, whoosh=whoosh, riser=riser, glitch=glitch, tape_stop=tape_stop, chime=chime, tick=tick, shutter=shutter, sub_drop=sub_drop,
                lock=lock, slide=slide, jump=jump, type_hit=type_hit, data_blip=data_blip, freeze=freeze, swell=swell)

def make(kind, **p):
    if kind == 'tick_hi': return tick(1, 0, 5200) * .6
    return REGISTRY[kind](**p)

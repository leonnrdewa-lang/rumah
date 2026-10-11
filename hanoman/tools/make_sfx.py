#!/usr/bin/env python3
"""Synthesises the sound effects and ambience beds of Hanoman Duta with numpy.

Every sound is built from scratch (noise, oscillators, filters, envelopes); gamelan
colours (gender/bell chimes, bonang, kempul/gong shimmer, kendang) reuse the physical
bar/kettle/gong models of make_music.py so SFX and music share the same tuning (slendro
on D) and timbre.

Output (hanoman/game/assets/audio/, Ogg Vorbis 44.1 kHz):
  sfx_*.ogg   mono one-shots, peak-normalised to -1 dBFS
  amb_forest.ogg, amb_river.ogg   stereo seamless loops (circular synthesis: every
              filter is an FFT filter over the whole loop and every event wraps around)

  python3 hanoman/tools/make_sfx.py                   # everything
  python3 hanoman/tools/make_sfx.py sfx_hit amb_river # only these
  python3 hanoman/tools/make_sfx.py --png /tmp/png    # also spectrogram PNGs
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_music as mm  # noqa: E402  (gamelan models + tuning)

SR = 44100
OUT = mm.OUT
PEAK_DB = -1.0
AMB_LUFS = {"amb_forest": -27.0, "amb_river": -25.0}
SFX_Q = 3
AMB_Q = 1


# ============================================================== basics
def n_of(sec):
    return int(round(sec * SR))


def tax(sec):
    return np.arange(n_of(sec)) / SR


def rng_of(name):
    return np.random.default_rng(sum(map(ord, name)) * 7919)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR / 2 - 100)], "bandpass", fs=SR, output="sos"), x)


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, min(fc, SR / 2 - 100), "lowpass", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "highpass", fs=SR, output="sos"), x)


def env_ad(n, a, d, curve=1.0):
    t = np.arange(n) / SR
    return np.clip(t / max(a, 1e-5), 0, 1) ** curve * np.exp(-np.maximum(0, t - a) / d)


def shape(n, pts):
    """piecewise-linear envelope; pts = [(0..1 position, value)]"""
    x = np.linspace(0, 1, n)
    return np.interp(x, [p for p, _ in pts], [v for _, v in pts])


def glide_osc(fpts, n, harm=((1, 1.0),), jitter=0.0, rng=None):
    f = shape(n, fpts) if isinstance(fpts, list) else np.full(n, float(fpts))
    if jitter and rng is not None:
        f = f * (1 + jitter * lp(rng.standard_normal(n), 30) * 8)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return sum(a * np.sin(h * ph) for h, a in harm)


def sweep_noise(n, fpts, q=1.0, rng=None, order=2, bands=16, lo=80, hi=14000):
    """noise whose band centre follows fpts (crossfaded filter bank, smooth)"""
    rng = rng or np.random.default_rng(1)
    x = rng.standard_normal(n)
    fc = shape(n, fpts)
    lf = np.log(np.maximum(fc, 20))
    out = np.zeros(n)
    for c in np.geomspace(lo, hi, bands):
        w = np.exp(-0.5 * ((np.log(c) - lf) / (0.3 / q)) ** 2)
        if w.max() < 1e-3:
            continue
        k = 1 + 0.45 / q
        out += bp(x, c / k, c * k, order) * w
    return out


def place(buf, x, at, gain=1.0, wrap=False):
    i = int(round(at * SR))
    if wrap:
        idx = (np.arange(len(x)) + i) % len(buf)
        np.add.at(buf, idx, x * gain)
    else:
        m = min(len(x), len(buf) - i)
        if m > 0:
            buf[i:i + m] += x[:m] * gain
    return buf


def sat(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def norm(x):
    return x / (np.max(np.abs(x)) + 1e-12)


def fade_out(x, sec=0.03):
    k = min(len(x), n_of(sec))
    x[-k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    return x


def fade_in(x, sec=0.002):
    k = min(len(x), n_of(sec))
    x[:k] *= np.linspace(0, 1, k)
    return x


def mono(y):
    return y.mean(axis=0) if y.ndim == 2 else y


def small_room(x, rt=0.35, mix=0.15, seed=3):
    rng = np.random.default_rng(seed)
    n = n_of(rt * 1.3)
    t = np.arange(n) / SR
    ir = lp(rng.standard_normal(n), 6000) * np.exp(-6.9 * t / rt)
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = signal.oaconvolve(x, ir)[:len(x)]
    return x + mix * wet * (np.std(x) / (np.std(wet) + 1e-12))


def pad_tail(x, sec):
    return np.concatenate([x, np.zeros(n_of(sec))])


# gamelan pitch helpers (slendro on D, same as the music)
def sl(tok, oct=0):
    return 440.0 * 2 ** ((62 - 69) / 12 + (mm.SLENDRO[int(tok[0])] + 1200 * (oct + tok.count("'"))) / 1200)


def metal(kind, f, vel=0.8, hold=None, seed=1, beat=None):
    return mono(mm.metal_note(kind, f, vel, hold, seed, beat))


def gong(kind, f, vel=0.9, seed=1):
    return mono(mm.gong_note(kind, f, vel, seed))


# ============================================================== combat
def whoosh(rng, dur, f0, f1, f2, peak=0.45, body=0.3, q=0.8):
    n = n_of(dur)
    w = sweep_noise(n, [(0, f0), (peak, f1), (1, f2)], q=q, rng=rng)
    e = shape(n, [(0, 0), (peak * 0.8, 0.8), (peak, 1.0), (1, 0)]) ** 1.6
    y = norm(w) * e
    # air displacement 'woof' under the whoosh
    woof = glide_osc([(0, 70), (1, 110)], n) * shape(n, [(0, 0), (peak, 1), (1, 0)]) ** 2
    y += body * woof
    return y


def sfx_swing(k):
    rng = rng_of(f"swing{k}")
    if k == 1:
        y = whoosh(rng, 0.26, 350, 1500, 500, peak=0.42, body=0.1)
    elif k == 2:
        y = whoosh(rng, 0.28, 450, 1900, 600, peak=0.45, body=0.08)
    else:      # finisher: heavier, longer, lower, with a second flutter layer
        y = whoosh(rng, 0.42, 220, 1100, 300, peak=0.55, body=0.16, q=1.0)
        y2 = whoosh(rng, 0.42, 900, 3200, 700, peak=0.5, body=0.0, q=0.6)
        n = len(y)
        y = y + 0.35 * y2 * (0.7 + 0.3 * np.sin(2 * np.pi * 34 * np.arange(n) / SR))
    return fade_out(y, 0.03)


def impact(rng, f_hi, f_lo, tdec, body_lp, crack, dur, noise_dec=0.04):
    n = n_of(dur)
    t = np.arange(n) / SR
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.03)
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / tdec)
    body = lp(rng.standard_normal(n), body_lp, 2) * np.exp(-t / noise_dec)
    cr = hp(rng.standard_normal(n), 2500) * np.exp(-t / 0.004) * crack
    return thump * 1.0 + norm(body) * 0.8 + cr


def sfx_hit():
    rng = rng_of("hit")
    y = impact(rng, 180, 55, 0.07, 1400, 0.6, 0.35)
    # slap: mid resonance of flesh
    y += 0.5 * bp(rng.standard_normal(len(y)), 600, 1800) * env_ad(len(y), 0.001, 0.02) * 4
    return fade_out(sat(y, 2.2), 0.05)


def sfx_hit_heavy():
    rng = rng_of("hit_heavy")
    y = impact(rng, 140, 38, 0.16, 900, 0.8, 0.7, noise_dec=0.09)
    crunch = bp(rng.standard_normal(len(y)), 300, 2500) * env_ad(len(y), 0.002, 0.05)
    y += 0.7 * norm(crunch) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 45 * np.arange(len(y)) / SR)))
    # debris ticks
    for i in range(10):
        c = hp(rng.standard_normal(n_of(0.01)), 1500) * env_ad(n_of(0.01), 0.0005, 0.002)
        place(y, c, 0.03 + rng.uniform(0, 0.25), 0.25 * rng.uniform(0.3, 1))
    return fade_out(small_room(sat(y, 2.8), 0.4, 0.12), 0.08)


def sfx_crit():
    rng = rng_of("crit")
    y = pad_tail(impact(rng, 220, 60, 0.08, 2000, 1.0, 0.35), 0.45)
    ring = metal("peking", sl("2", 2), 1.0, None, 5)
    ring2 = metal("bell", sl("6", 2), 0.9, None, 6)
    y = sat(y, 2.5)
    place(y, ring[:n_of(0.8)] * 0.7, 0.005)
    place(y, ring2[:n_of(0.8)] * 0.5, 0.012)
    # zing: fast rising tone
    n = n_of(0.18)
    z = glide_osc([(0, 1800), (1, 3400)], n, ((1, 1), (2, 0.3))) * env_ad(n, 0.004, 0.06)
    place(y, z * 0.3, 0.0)
    return fade_out(y, 0.1)


def sfx_dash():
    rng = rng_of("dash")
    n = n_of(0.36)
    w = sweep_noise(n, [(0, 600), (0.25, 2600), (1, 900)], q=0.9, rng=rng)
    e = shape(n, [(0, 0), (0.12, 1), (0.35, 0.7), (1, 0)]) ** 1.5
    flutter = 0.75 + 0.25 * np.sin(2 * np.pi * 28 * np.arange(n) / SR)
    y = norm(w) * e * flutter
    y += 0.25 * glide_osc([(0, 90), (1, 60)], n) * shape(n, [(0, 0), (0.1, 1), (1, 0)]) ** 2
    return fade_out(y, 0.03)


def sfx_special():
    rng = rng_of("special")
    n = n_of(0.65)
    y = whoosh(rng, 0.65, 500, 2600, 1200, peak=0.12, body=0.2, q=0.7)
    # 'shing' of the wind blade: bright inharmonic glide
    s = glide_osc([(0, 1300), (0.2, 2100), (1, 1700)], n, ((1, 1.0), (2.76, 0.35), (5.4, 0.12)))
    s *= env_ad(n, 0.01, 0.16)
    whistle = glide_osc([(0, 2400), (1, 1500)], n, ((1, 1.0),)) * shape(n, [(0, 0), (0.1, 0.5), (0.6, 0.3), (1, 0)])
    whistle *= 1 + 0.3 * lp(rng.standard_normal(n), 40) * 10
    y = norm(y) + 0.45 * s + 0.12 * whistle
    return fade_out(y, 0.08)


def sfx_cast():
    rng = rng_of("cast")
    n = n_of(1.6)
    y = np.zeros(n)
    # soft gong swell under the circle
    g = gong("kempul", sl("2", -2), 0.7, 3)
    place(y, g[:n] * 0.7, 0.02)
    # quick gender arpeggio drawing the circle, then a shimmer cluster
    for i, tok in enumerate(["1", "2", "3", "5", "6", "1'", "2'", "3'"]):
        place(y, metal("gender", sl(tok, 1), 0.55 + 0.05 * i, None, 10 + i, beat=5.0) * 0.35, 0.03 + i * 0.045)
    for i, tok in enumerate(["2'", "6", "3'"]):
        place(y, metal("bell", sl(tok, 1), 0.5, None, 30 + i, beat=6.0) * 0.25, 0.42 + i * 0.01)
    # swirling air rising
    sw = sweep_noise(n, [(0, 400), (0.4, 3000), (1, 5000)], q=0.6, rng=rng)
    sw = norm(sw) * shape(n, [(0, 0), (0.3, 1), (1, 0)]) ** 2 * (0.7 + 0.3 * np.sin(2 * np.pi * 7 * np.arange(n) / SR))
    y += 0.25 * sw
    return fade_out(y, 0.3)


def voice(f0pts, n, formants, rng, rough=0.1, breath=0.1, jitter=0.01):
    """glottal-ish pulse source through formant resonators"""
    f0 = shape(n, f0pts) * (1 + jitter * lp(rng.standard_normal(n), 25) * 10)
    ph = np.cumsum(f0) / SR
    src = 2 * (ph % 1.0) - 1                 # sawtooth
    src = src + rough * rng.standard_normal(n) * (np.sin(np.pi * ph * 2) > 0)
    src = lp(src, 5000) + breath * rng.standard_normal(n)
    out = np.zeros(n)
    for fc, bw, a in formants:
        out += a * bp(src, max(40, fc - bw / 2), fc + bw / 2)
    return out


def sfx_player_hurt():
    rng = rng_of("hurt")
    n = n_of(0.34)
    th = impact(rng, 160, 60, 0.05, 1200, 0.3, 0.34)
    v = voice([(0, 300), (0.25, 340), (1, 210)], n, [(750, 250, 1.0), (1250, 300, 0.6), (2600, 500, 0.25)], rng,
              rough=0.3, breath=0.08)
    v *= shape(n, [(0, 0), (0.06, 1), (0.4, 0.8), (1, 0)])
    return fade_out(0.8 * sat(th, 2) + 1.2 * norm(v), 0.04)


def sfx_enemy_die():
    rng = rng_of("die")
    n = n_of(1.0)
    growl = voice([(0, 130), (0.5, 90), (1, 55)], n, [(500, 200, 1.0), (900, 250, 0.6), (2300, 400, 0.2)], rng,
                  rough=0.8, breath=0.2, jitter=0.03)
    growl *= shape(n, [(0, 0), (0.04, 1), (0.4, 0.5), (0.7, 0)])
    puff = sweep_noise(n, [(0, 2500), (0.3, 900), (1, 300)], q=1.0, rng=rng)
    puff = norm(puff) * shape(n, [(0, 0), (0.05, 1), (0.25, 0.6), (1, 0)]) ** 1.5
    y = 0.5 * norm(growl) + 0.8 * puff
    # dissolving sparkles (ash embers)
    for i in range(22):
        m = n_of(0.03)
        c = bp(rng.standard_normal(m), 3000, 9000) * env_ad(m, 0.001, 0.006)
        place(y, c, 0.1 + rng.uniform(0, 0.8) ** 1.5 * 0.8, 0.25 * rng.uniform(0.3, 1) * (1 - i / 30))
    return fade_out(y, 0.15)


def sfx_boss_roar():
    rng = rng_of("roar")
    n = n_of(2.2)
    y = np.zeros(n)
    for k, (fs, g) in enumerate([(1.0, 1.0), (0.995, 0.7), (1.51, 0.3), (0.5, 0.6)]):
        v = voice([(0, 75 * fs), (0.15, 95 * fs), (0.5, 88 * fs), (1, 55 * fs)], n,
                  [(420, 220, 1.0), (780, 300, 0.8), (1500, 500, 0.35), (2800, 800, 0.15)], np.random.default_rng(k + 5),
                  rough=1.2, breath=0.3, jitter=0.05)
        y += g * norm(v)
    y *= shape(n, [(0, 0), (0.08, 0.9), (0.35, 1.0), (0.75, 0.6), (1, 0)])
    rumble = lp(rng.standard_normal(n), 120, 4) * shape(n, [(0, 0), (0.1, 1), (1, 0)])
    y = sat(norm(y) * 1.5, 2.5) + 0.7 * norm(rumble)
    return fade_out(small_room(y, 0.8, 0.2), 0.2)


def water_splash(rng, dur, size=1.0):
    n = n_of(dur)
    y = np.zeros(n)
    # displacement whump
    m = n_of(0.25)
    t = np.arange(m) / SR
    wh = np.sin(2 * np.pi * np.cumsum(55 + 60 * np.exp(-t / 0.04)) / SR) * np.exp(-t / 0.08)
    place(y, wh * 0.8 * size, 0)
    # splash sheet: bright noise with a fast attack
    sp = bp(rng.standard_normal(n), 400, 7000) * shape(n, [(0, 0), (0.02, 1), (0.15, 0.5), (0.5, 0.12), (1, 0)])
    sp *= 1 + 0.5 * lp(rng.standard_normal(n), 60) * 8
    y += norm(sp) * 0.9
    # droplets / bubbles falling back
    for i in range(int(30 * size)):
        f0 = math.exp(rng.uniform(math.log(700), math.log(3500)))
        m = n_of(0.08)
        t = np.arange(m) / SR
        b = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 4 * t)) / SR) * np.exp(-t / 0.02)
        place(y, b, rng.uniform(0.08, dur * 0.8), 0.18 * rng.uniform(0.3, 1))
    return y


def sfx_shark_splash():
    rng = rng_of("shark")
    y = water_splash(rng, 1.3, 1.3)
    return fade_out(small_room(y, 0.6, 0.12), 0.2)


def sfx_croc_snap():
    rng = rng_of("croc")
    n = n_of(0.45)
    y = np.zeros(n)
    # quick hiss as the jaws open
    hs = hp(rng.standard_normal(n_of(0.12)), 2500) * shape(n_of(0.12), [(0, 0), (0.7, 1), (1, 0.3)])
    place(y, hs * 0.25, 0.0)
    # the snap: two hard bony clacks with wood-like resonances
    for k, at in enumerate([0.115, 0.123]):
        m = n_of(0.08)
        c = rng.standard_normal(m) * env_ad(m, 0.0003, 0.004)
        c = bp(c, 700, 1600) * 3 + bp(c, 2000, 4200) * 2 + c * 0.5
        place(y, c, at, 1.0 if k == 0 else 0.6)
    m = n_of(0.2)
    t = np.arange(m) / SR
    place(y, np.sin(2 * np.pi * np.cumsum(90 + 80 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.05), 0.115, 0.8)
    return fade_out(sat(y, 1.8), 0.05)


def sfx_slam():
    rng = rng_of("slam")
    n = n_of(1.3)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 60 * np.exp(-t / 0.05)) / SR) * np.exp(-t / 0.25)
    rumble = lp(rng.standard_normal(n), 220, 3) * np.exp(-t / 0.35)
    crack = hp(rng.standard_normal(n), 1200) * np.exp(-t / 0.012)
    y = boom * 1.0 + norm(rumble) * 0.8 + crack * 0.35
    for i in range(40):     # crumbling stone debris
        m = n_of(0.02)
        c = bp(rng.standard_normal(m), 800, 5000) * env_ad(m, 0.0005, 0.004)
        place(y, c, 0.05 + rng.uniform(0, 0.9) ** 1.7, 0.2 * rng.uniform(0.2, 1))
    return fade_out(small_room(sat(y, 2.2), 0.6, 0.15), 0.2)


def crackle(rng, n, rate, lo=1500, hi=8000, amp=1.0):
    y = np.zeros(n)
    k = int(rate * n / SR)
    for i in range(k):
        m = n_of(0.008)
        c = rng.standard_normal(m) * env_ad(m, 0.0002, 0.0015)
        place(y, c, rng.uniform(0, n / SR - 0.01), amp * rng.lognormal(0, 0.6))
    return bp(y, lo, hi)


def sfx_fireball():
    rng = rng_of("fireball")
    n = n_of(0.8)
    fw = sweep_noise(n, [(0, 250), (0.2, 900), (1, 400)], q=1.2, rng=rng, lo=60, hi=6000)
    fw = norm(fw) * shape(n, [(0, 0), (0.15, 1), (0.5, 0.5), (1, 0)])
    fw *= 1 + 0.4 * lp(rng.standard_normal(n), 25) * 10    # flame flutter
    roar = lp(rng.standard_normal(n), 300) * shape(n, [(0, 0), (0.1, 1), (1, 0)])
    y = fw + 0.6 * norm(roar) + 0.5 * norm(crackle(rng, n, 60)) * shape(n, [(0, 0), (0.1, 1), (1, 0.2)])
    return fade_out(y, 0.1)


def sfx_explode():
    rng = rng_of("explode")
    n = n_of(1.8)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(32 + 70 * np.exp(-t / 0.06)) / SR) * np.exp(-t / 0.35)
    blast = lp(rng.standard_normal(n), 2500) * np.exp(-t / 0.18)
    body = lp(rng.standard_normal(n), 400, 3) * np.exp(-t / 0.6)
    y = boom + norm(blast) * 0.9 + norm(body) * 0.6
    y += 0.35 * norm(crackle(rng, n, 90)) * np.exp(-t / 0.5)
    return fade_out(small_room(sat(y, 3.0), 0.9, 0.15), 0.3)


def sfx_lightning():
    rng = rng_of("lightning")
    n = n_of(1.4)
    t = np.arange(n) / SR
    y = np.zeros(n)
    # the strike: a cluster of hard cracks
    for i in range(8):
        m = n_of(0.02)
        c = rng.standard_normal(m) * env_ad(m, 0.0002, 0.003)
        place(y, c, 0.002 + i * rng.uniform(0.004, 0.012), 1.0 - 0.08 * i)
    # electric buzz (60 Hz-ish saw ring modulated)
    bz = (2 * ((np.cumsum(np.full(n, 72.0)) / SR) % 1) - 1) * hp(rng.standard_normal(n), 3000) * 0.5
    bz = bp(bz + 0.3 * np.sign(np.sin(2 * np.pi * 144 * t)), 200, 6000) * np.exp(-t / 0.12)
    # thunder tail
    th = lp(rng.standard_normal(n), 300, 3) * shape(n, [(0, 0), (0.08, 1), (1, 0)]) ** 1.3
    th *= 1 + 0.6 * lp(rng.standard_normal(n), 8) * 20
    y = norm(y) + 0.5 * norm(bz) + 0.7 * norm(th)
    return fade_out(sat(y, 1.8), 0.2)


def sfx_burn():
    rng = rng_of("burn")
    n = n_of(0.5)
    hs = hp(rng.standard_normal(n), 2500) * shape(n, [(0, 0), (0.1, 1), (1, 0)]) ** 1.3
    fl = lp(rng.standard_normal(n), 500) * shape(n, [(0, 0), (0.15, 1), (1, 0)])
    y = 0.5 * norm(hs) + 0.5 * norm(fl) + 0.8 * norm(crackle(rng, n, 120, 1200, 7000)) * shape(n, [(0, 1), (1, 0.2)])
    return fade_out(fade_in(y, 0.01), 0.05)


def sfx_wave():
    rng = rng_of("wave")
    n = n_of(1.6)
    rise = sweep_noise(n, [(0, 200), (0.45, 1800), (0.6, 3500), (1, 1500)], q=1.4, rng=rng, lo=60)
    rise = norm(rise) * shape(n, [(0, 0), (0.4, 0.8), (0.5, 1), (1, 0)]) ** 1.3
    wash = lp(rng.standard_normal(n), 900) * shape(n, [(0, 0), (0.45, 0.2), (0.55, 1), (1, 0)])
    fizz = hp(rng.standard_normal(n), 3500) * shape(n, [(0, 0), (0.5, 0), (0.6, 0.6), (1, 0)])
    y = rise + 0.6 * norm(wash) + 0.25 * norm(fizz)
    return fade_out(fade_in(y, 0.02), 0.15)


# ============================================================== pickups / divine
def coin_clink(rng, f0):
    m = n_of(0.25)
    t = np.arange(m) / SR
    y = np.zeros(m)
    for r, a, d in [(1, 1, 0.09), (2.32, 0.7, 0.06), (3.9, 0.5, 0.04), (5.6, 0.3, 0.025)]:
        f = f0 * r * rng.uniform(0.98, 1.02)
        if f < 16000:
            y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t / d)
    y[:n_of(0.002)] += rng.standard_normal(n_of(0.002)) * 0.5
    return y


def sfx_pickup_coin():
    rng = rng_of("coin")
    y = np.zeros(n_of(0.6))
    for i, at in enumerate([0.0, 0.045, 0.08, 0.13, 0.17]):   # a string of kepeng jingling
        place(y, coin_clink(rng, rng.uniform(2600, 3600)), at, 1.0 - 0.12 * i)
    place(y, metal("peking", sl("1", 2), 0.8, None, 3)[:n_of(0.4)], 0.02, 0.5)
    return fade_out(y, 0.05)


def sfx_pickup_heal():
    rng = rng_of("heal")
    n = n_of(1.2)
    y = np.zeros(n)
    for i, tok in enumerate(["1", "3", "5", "1'"]):
        place(y, metal("gender", sl(tok, 1), 0.6, None, 20 + i)[:n], 0.0 + i * 0.07, 0.6)
    sh = sweep_noise(n, [(0, 2000), (1, 7000)], q=0.6, rng=rng) * shape(n, [(0, 0), (0.25, 1), (1, 0)])
    pad = glide_osc(sl("1", 0), n, ((1, 1), (2, 0.3), (3, 0.1))) * shape(n, [(0, 0), (0.3, 1), (1, 0)])
    y = norm(y) + 0.12 * norm(sh) + 0.2 * pad
    return fade_out(y, 0.15)


def sfx_boon_appear():
    rng = rng_of("boon_appear")
    n = n_of(2.4)
    y = np.zeros(n)
    sw = sweep_noise(n, [(0, 800), (0.2, 6000), (1, 4000)], q=0.5, rng=rng)
    y += 0.12 * norm(sw) * shape(n, [(0, 0), (0.18, 1), (0.5, 0.2), (1, 0)])
    for i, tok in enumerate(["2", "5", "1'", "3'"]):
        place(y, metal("gender", sl(tok, 1), 0.65, None, 40 + i, beat=4.0)[:n], 0.25 + i * 0.012, 0.45)
    for i, tok in enumerate(["6'", "2''"]):
        place(y, metal("bell", sl(tok, 1), 0.55, None, 50 + i, beat=5.0)[:n], 0.3 + i * 0.1, 0.35)
    place(y, gong("kempul", sl("2", -1), 0.5, 8)[:n] * 0.25, 0.25)
    return fade_out(y, 0.4)


def sfx_boon_pick():
    rng = rng_of("boon_pick")
    n = n_of(1.5)
    y = np.zeros(n)
    for i, tok in enumerate(["3", "5", "6", "2'"]):
        place(y, metal("bonang", sl(tok, 1), 0.75, None, 60 + i)[:n], i * 0.06, 0.6)
    place(y, metal("bell", sl("2", 3), 0.7, None, 70)[:n], 0.18, 0.4)
    place(y, gong("kempul", sl("2", -1), 0.8, 2)[:n] * 0.6, 0.18)
    sp = sweep_noise(n, [(0, 3000), (1, 9000)], q=0.5, rng=rng) * shape(n, [(0, 0), (0.12, 0), (0.2, 1), (1, 0)])
    y += 0.1 * norm(sp)
    return fade_out(y, 0.3)


def sfx_door_open():
    rng = rng_of("door")
    n = n_of(2.0)
    t = np.arange(n) / SR
    grind = lp(rng.standard_normal(n), 700, 3) + 0.4 * bp(rng.standard_normal(n), 900, 2500)
    rough = np.clip(lp(rng.standard_normal(n), 35) * 12, -1, 1) * 0.5 + 0.6
    judder = 0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 11 * t))
    grind = norm(grind) * rough * judder * shape(n, [(0, 0), (0.05, 0.9), (0.6, 1), (0.72, 0.2), (1, 0)])
    thud = np.sin(2 * np.pi * np.cumsum(45 + 40 * np.exp(-np.maximum(0, t - 1.35) / 0.05)) / SR)
    thud *= np.where(t > 1.35, np.exp(-(t - 1.35) / 0.15), 0)
    y = grind + 0.6 * thud
    chime = metal("bell", sl("1", 2), 0.6, None, 4)
    place(y, chime[:n] * 0.4, 1.4)
    place(y, metal("gender", sl("5", 1), 0.6, None, 5)[:n] * 0.4, 1.42)
    return fade_out(y, 0.25)


def sfx_room_clear():
    rng = rng_of("clear")
    n = n_of(2.6)
    y = np.zeros(n)
    place(y, gong("gong", sl("2", -2), 0.9, 1)[:n] * 0.9, 0.0)
    for i, tok in enumerate(["1", "2", "3", "5", "6", "1'"]):
        place(y, metal("bonang", sl(tok, 1), 0.7, None, 80 + i)[:n], 0.02 + i * 0.07, 0.45)
    place(y, metal("peking", sl("2", 2), 0.8, None, 90)[:n], 0.45, 0.35)
    place(y, metal("bell", sl("1", 3), 0.7, None, 91)[:n], 0.46, 0.25)
    return fade_out(y, 0.4)


# ============================================================== UI
def sfx_ui_move():
    y = metal("kethuk", sl("5", 1), 0.6, None, 1)[:n_of(0.09)]
    return fade_out(y, 0.02)


def sfx_ui_select():
    n = n_of(0.45)
    y = np.zeros(n)
    place(y, metal("bonang", sl("2", 1), 0.7, None, 2)[:n], 0.0, 0.8)
    place(y, metal("bonang", sl("5", 1), 0.8, None, 3)[:n], 0.07, 1.0)
    return fade_out(y, 0.1)


def sfx_ui_back():
    n = n_of(0.35)
    y = np.zeros(n)
    place(y, metal("bonang", sl("3", 1), 0.6, None, 4)[:n], 0.0, 0.8)
    place(y, metal("bonang", sl("1", 1), 0.55, None, 5)[:n], 0.06, 0.8)
    return fade_out(y, 0.08)


def sfx_telegraph():
    rng = rng_of("telegraph")
    n = n_of(0.6)
    t = np.arange(n) / SR
    y = glide_osc([(0, 520), (1, 1250)], n, ((1, 1.0), (2, 0.25), (3, 0.1)))
    y += 0.8 * glide_osc([(0, 527), (1, 1268)], n, ((1, 1.0), (2, 0.2)))
    y *= 0.7 + 0.3 * np.sin(2 * np.pi * np.cumsum(shape(n, [(0, 9), (1, 22)])) / SR)
    y *= shape(n, [(0, 0), (0.1, 0.6), (0.85, 1), (1, 0)])
    y += 0.1 * hp(rng.standard_normal(n), 4000) * shape(n, [(0, 0), (0.9, 1), (1, 0)])
    return fade_out(y, 0.03)


SFX = {
    "sfx_swing1": lambda: sfx_swing(1), "sfx_swing2": lambda: sfx_swing(2), "sfx_swing3": lambda: sfx_swing(3),
    "sfx_hit": sfx_hit, "sfx_hit_heavy": sfx_hit_heavy, "sfx_crit": sfx_crit, "sfx_dash": sfx_dash,
    "sfx_special": sfx_special, "sfx_cast": sfx_cast, "sfx_player_hurt": sfx_player_hurt,
    "sfx_enemy_die": sfx_enemy_die, "sfx_boss_roar": sfx_boss_roar, "sfx_shark_splash": sfx_shark_splash,
    "sfx_croc_snap": sfx_croc_snap, "sfx_slam": sfx_slam, "sfx_fireball": sfx_fireball, "sfx_explode": sfx_explode,
    "sfx_lightning": sfx_lightning, "sfx_burn": sfx_burn, "sfx_wave": sfx_wave, "sfx_pickup_coin": sfx_pickup_coin,
    "sfx_pickup_heal": sfx_pickup_heal, "sfx_boon_appear": sfx_boon_appear, "sfx_boon_pick": sfx_boon_pick,
    "sfx_door_open": sfx_door_open, "sfx_room_clear": sfx_room_clear, "sfx_ui_move": sfx_ui_move,
    "sfx_ui_select": sfx_ui_select, "sfx_ui_back": sfx_ui_back, "sfx_telegraph": sfx_telegraph,
}


# ============================================================== ambience (circular)
def fft_filter(x, fn):
    """zero-phase circular filter: fn(freqs) -> magnitude"""
    X = np.fft.rfft(x, axis=-1)
    f = np.fft.rfftfreq(x.shape[-1], 1 / SR)
    return np.fft.irfft(X * fn(f), n=x.shape[-1], axis=-1)


def lpf(f, fc, order=2):
    return 1 / np.sqrt(1 + (f / fc) ** (2 * order))


def hpf(f, fc, order=2):
    return 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def bpf(f, lo, hi, order=2):
    return lpf(f, hi, order) * hpf(f, lo, order)


def periodic_lfo(n, rng, cycles_lo=1, cycles_hi=6, k=3):
    """smooth random modulation that is exactly periodic over the loop"""
    t = np.arange(n) / n
    y = np.zeros(n)
    for _ in range(k):
        c = rng.integers(cycles_lo, cycles_hi + 1)
        y += rng.uniform(0.3, 1) * np.sin(2 * np.pi * c * t + rng.uniform(0, 6.28))
    return y / k


def stereo_place(buf, x, at, pan, gain=1.0):
    a = (pan + 1) * math.pi / 4
    place(buf[0], x, at, gain * math.cos(a) * math.sqrt(2), wrap=True)
    place(buf[1], x, at, gain * math.sin(a) * math.sqrt(2), wrap=True)


def cricket_chirp(rng, f, pulses=3):
    parts = []
    for i in range(pulses):
        m = n_of(0.016)
        y = np.sin(2 * np.pi * f * np.arange(m) / SR) * np.sin(np.pi * np.linspace(0, 1, m)) ** 1.5
        parts.append(np.concatenate([y, np.zeros(n_of(0.018))]))
    return np.concatenate(parts)


def cicada(rng, dur, fc):
    n = n_of(dur)
    t = np.arange(n) / SR
    carrier = bp(rng.standard_normal(n), fc * 0.85, fc * 1.18)
    carrier = norm(carrier)
    rate = 110 * (1 + 0.08 * np.clip(t / (dur * 0.6), 0, 1))
    am = 0.3 + 0.7 * np.clip(np.sin(2 * np.pi * np.cumsum(rate) / SR), 0, 1) ** 3
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return carrier * am * env


def frog(rng, kind):
    if kind == "kerok":
        dur = rng.uniform(0.35, 0.5)
        n = n_of(dur)
        f0 = rng.uniform(200, 240)
        y = glide_osc([(0, f0 * 0.95), (0.5, f0), (0.6, f0 * 1.12), (1, f0 * 1.04)], n,
                      ((1, 1.0), (2, 0.55), (3, 0.3), (4, 0.12)))
        y *= 0.75 + 0.25 * np.sin(2 * np.pi * 38 * np.arange(n) / SR)
        y *= shape(n, [(0, 0), (0.08, 0.75), (0.42, 0.85), (0.5, 0.3), (0.6, 1.0), (0.9, 0.7), (1, 0)])
        return lp(y, 900)
    dur, rate, fc = rng.uniform(0.12, 0.2), rng.uniform(55, 75), rng.uniform(950, 1250)
    n = n_of(dur)
    car = glide_osc([(0, fc * 1.03), (1, fc * 0.97)], n, ((1, 1.0), (2, 0.3)))
    am = np.clip(np.sin(np.pi * np.cumsum(np.full(n, rate)) / SR), 0, 1) ** 2
    return lp(car * am * shape(n, [(0, 0), (0.15, 1), (0.6, 0.85), (1, 0)]), 2600)


def owl(rng):
    f = rng.uniform(360, 420)
    out = []
    for d, fp, gap in [(0.42, [(0, f * 0.96), (0.3, f * 1.03), (1, f * 0.94)], 0.75), (0.18, [(0, f), (1, f * 0.97)], 0.12),
                       (0.36, [(0, f * 1.01), (1, f * 0.93)], 0.0)]:
        n = n_of(d)
        y = glide_osc(fp, n, ((1, 1.0), (2, 0.08), (3, 0.02)))
        y += 0.12 * lp(rng.standard_normal(n), 1500)
        y *= shape(n, [(0, 0), (0.25, 1), (0.7, 0.8), (1, 0)])
        out += [y, np.zeros(n_of(gap))]
    return np.concatenate(out)


def amb_forest():
    rng = np.random.default_rng(101)
    L = 24.0
    n = n_of(L)
    buf = np.zeros((2, n))
    # night air: soft wind in leaves, circular, slowly breathing
    wind = fft_filter(rng.standard_normal((2, n)), lambda f: bpf(f, 150, 1800, 1) / np.sqrt(np.maximum(f, 50) / 50))
    wind *= 0.6 + 0.4 * periodic_lfo(n, rng, 1, 4)
    buf += 0.05 * wind / np.std(wind)
    # tree-cricket trills: continuous, several voices (periodic AM so they loop)
    t = np.arange(n) / SR
    for k in range(4):
        f = rng.uniform(3900, 4900)
        rate = round(rng.uniform(28, 45) * L) / L
        tr = np.sin(2 * np.pi * f * t) * (0.3 + 0.7 * np.clip(np.sin(2 * np.pi * rate * t), 0, 1) ** 2)
        tr *= 0.55 + 0.45 * (0.5 + 0.5 * periodic_lfo(n, rng, 1, 3))
        pan = rng.uniform(-0.9, 0.9)
        stereo_place(buf, tr, 0.0, pan, 0.012)
    # field crickets: chirps in regular rhythms, each insect its own pitch and place
    for k in range(6):
        f = rng.uniform(4300, 5600)
        pan = rng.uniform(-1, 1)
        period = rng.uniform(0.45, 0.8)
        g = rng.uniform(0.02, 0.05)
        tt = rng.uniform(0, period)
        while tt < L:
            stereo_place(buf, cricket_chirp(rng, f * rng.uniform(0.995, 1.005), int(rng.integers(2, 5))), tt, pan,
                         g * rng.uniform(0.8, 1))
            tt += period * rng.uniform(0.95, 1.05) + (rng.uniform(1, 3) if rng.random() < 0.08 else 0)
    # tonggeret (cicada) swells, far away
    for at, fc, pan in [(2.0, 3200, -0.6), (11.0, 2900, 0.5), (17.5, 3400, 0.1)]:
        stereo_place(buf, cicada(rng, rng.uniform(5, 7), fc), at, pan, 0.05)
    # frogs from the damp ground
    for k in range(9):
        kind = "kerok" if k % 3 == 0 else "ngorek"
        at = rng.uniform(0, L)
        pan = rng.uniform(-0.8, 0.8)
        for j in range(int(rng.integers(2, 6))):
            x = frog(rng, kind)
            stereo_place(buf, lp(x, 1800), at, pan, 0.07 if kind == "ngorek" else 0.09)
            at += len(x) / SR + (rng.uniform(0.2, 0.35) if kind == "ngorek" else rng.uniform(1.0, 1.4))
    # distant owl, twice (with a distant-sounding low-pass)
    for at, pan in [(6.0, -0.5), (19.0, 0.6)]:
        stereo_place(buf, lp(owl(rng), 1400), at, pan, 0.08)
    # gentle circular reverb for space
    ir = mm.make_ir(1.8, seed=5)
    wet = np.stack([np.real(np.fft.ifft(np.fft.fft(buf[c]) * np.fft.fft(ir[c], n))) for c in range(2)])
    return buf + 0.35 * wet * np.std(buf) / (np.std(wet) + 1e-12)


def amb_river():
    rng = np.random.default_rng(202)
    L = 24.0
    n = n_of(L)
    t = np.arange(n) / SR
    buf = np.zeros((2, n))
    # broad river flow: brown-ish noise, slow periodic swells
    flow = fft_filter(rng.standard_normal((2, n)), lambda f: bpf(f, 60, 2500, 1) / np.sqrt(np.maximum(f, 40) / 40))
    flow *= 0.75 + 0.25 * periodic_lfo(n, rng, 2, 7)
    buf += 0.25 * flow / np.std(flow)
    # waves lapping at the piles: 4 swells per loop (6 s), each a rising wash + fizz
    for k in range(4):
        at = k * 6.0 + rng.uniform(-0.4, 0.4)
        m = n_of(3.2)
        w = fft_filter(rng.standard_normal(m), lambda f: bpf(f, 200, 3000, 1))
        w *= shape(m, [(0, 0), (0.35, 0.6), (0.45, 1.0), (0.6, 0.5), (1, 0)]) ** 1.5
        fz = fft_filter(rng.standard_normal(m), lambda f: hpf(f, 3000, 2)) * shape(m, [(0, 0), (0.42, 0), (0.5, 1), (1, 0)])
        pan = rng.uniform(-0.6, 0.6)
        stereo_place(buf, w / np.std(w) * 0.12 + fz / np.std(fz) * 0.03, at, pan)
    # lapping/gurgle: bubbles near the bank
    for k in range(260):
        f0 = math.exp(rng.uniform(math.log(350), math.log(2200)))
        m = n_of(0.07)
        tt = np.arange(m) / SR
        b = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 3 * tt)) / SR) * np.exp(-tt / 0.018)
        b[:12] *= np.linspace(0, 1, 12)
        stereo_place(buf, b, rng.uniform(0, L), rng.uniform(-0.9, 0.9), 0.03 * rng.lognormal(0, 0.5))
    # a distant fish splash and a heron-ish call? keep it to one small splash + a couple of frogs
    stereo_place(buf, lp(water_splash(rng, 0.9, 0.5), 3000), 9.3, 0.7, 0.12)
    for k in range(3):
        at = rng.uniform(0, L)
        for j in range(3):
            x = frog(rng, "ngorek")
            stereo_place(buf, lp(x, 1500), at, -0.7 + 0.6 * k, 0.03)
            at += len(x) / SR + 0.3
    ir = mm.make_ir(1.4, seed=9)
    wet = np.stack([np.real(np.fft.ifft(np.fft.fft(buf[c]) * np.fft.fft(ir[c], n))) for c in range(2)])
    return buf + 0.25 * wet * np.std(buf) / (np.std(wet) + 1e-12)


AMB = {"amb_forest": amb_forest, "amb_river": amb_river}


# ============================================================== output
def encode(y, path, q):
    tmp = path + ".tmp.wav"
    sf.write(tmp, (y.T if y.ndim == 2 else y).astype(np.float32), SR, subtype="FLOAT")
    ch = 2 if y.ndim == 2 else 1
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-map_metadata", "-1", "-c:a", "libvorbis",
                    "-q:a", str(q), "-ar", str(SR), "-ac", str(ch), path], check=True)
    os.remove(tmp)


def png(y, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = y.mean(axis=0) if y.ndim == 2 else y
    fig, ax = plt.subplots(2, 1, figsize=(8, 4), sharex=True, gridspec_kw={"height_ratios": [1, 2]})
    tt = np.arange(len(x)) / SR
    ax[0].plot(tt, x, lw=0.4)
    ax[0].set_ylim(-1, 1)
    ax[0].set_title(title, fontsize=9)
    f, t2, s = signal.spectrogram(x, SR, nperseg=1024, noverlap=768)
    ax[1].pcolormesh(t2, f, 10 * np.log10(s + 1e-14), shading="auto", vmin=-130, vmax=-40, cmap="magma")
    ax[1].set_yscale("symlog", linthresh=200)
    ax[1].set_ylim(30, 20000)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


def finish_sfx(name, y, png_dir):
    y = np.asarray(y, dtype=np.float64)
    y = hp(y, 25, 2)
    # trim trailing silence (-70 dB) and add a short fade
    e = np.abs(y)
    idx = np.nonzero(e > np.max(e) * 10 ** (-70 / 20))[0]
    y = y[:idx[-1] + n_of(0.01)] if len(idx) else y
    y = fade_in(fade_out(y.copy(), 0.01), 0.0005)
    y = y / (np.max(np.abs(y)) + 1e-12) * 10 ** (PEAK_DB / 20)
    path = os.path.join(OUT, name + ".ogg")
    for k in range(10):     # Vorbis moves the peak a little: re-measure the decoded file
        encode(y, path, SFX_Q)
        z, _ = sf.read(path, dtype="float64")
        pk = 20 * math.log10(np.max(np.abs(z)) + 1e-12)
        if -1.2 <= pk <= PEAK_DB + 0.05:
            break
        y *= 10 ** ((PEAK_DB - 0.05 - pk) / 20 * (0.8 if k < 5 else 0.5))
    print(f"  {name}.ogg  {len(z) / SR:.2f}s  peak {pk:.1f} dBFS  {os.path.getsize(path) / 1024:.1f} KB")
    if png_dir:
        png(z, os.path.join(png_dir, name + ".png"), name)


def finish_amb(name, y, png_dir):
    y = fft_filter(y, lambda f: hpf(f, 30, 2))       # circular: keeps the loop seamless
    meter = pyln.Meter(SR)
    L = meter.integrated_loudness(y.T)
    y = y * 10 ** ((AMB_LUFS[name] - L) / 20)
    pk = np.max(np.abs(y))
    if pk > 10 ** (-3 / 20):
        y *= 10 ** (-3 / 20) / pk
    path = os.path.join(OUT, name + ".ogg")
    encode(y, path, AMB_Q)
    z, _ = sf.read(path, dtype="float64", always_2d=True)
    z = z.T
    seam = np.abs(z[:, 0] - z[:, -1]).max()
    p99 = np.percentile(np.abs(np.diff(z, axis=1)), 99)
    print(f"  {name}.ogg  {z.shape[1] / SR:.2f}s  {meter.integrated_loudness(z.T):.1f} LUFS  peak "
          f"{20 * math.log10(np.max(np.abs(z))):.1f} dBFS  seam step {seam:.4f} (p99 step {p99:.4f})  "
          f"{os.path.getsize(path) / 1024:.0f} KB")
    if png_dir:
        png(z, os.path.join(png_dir, name + ".png"), name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--png")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.png:
        os.makedirs(a.png, exist_ok=True)
    names = a.names or list(SFX) + list(AMB)
    for nm in names:
        if nm in SFX:
            finish_sfx(nm, SFX[nm](), a.png)
        elif nm in AMB:
            finish_amb(nm, AMB[nm](), a.png)
        else:
            sys.exit("unknown: " + nm)


if __name__ == "__main__":
    main()

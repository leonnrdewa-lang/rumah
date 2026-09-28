#!/usr/bin/env python3
"""Synthesises the calls of the farm and village animals of Sawit The Franchise.

No samples: every call comes from a source-filter model of the real animal.
  * voiced calls (cow, buffalo, goat, chicken, rooster, duck, cat, dog): a band-limited
    glottal source (one period of a Rosenberg flow derivative, resynthesised harmonic by
    harmonic so nothing aliases) with pitch glides, vibrato / quaver, jitter, shimmer,
    optional period-doubling roughness and pulse-synchronous breath noise, sent through a
    Klatt-style cascade of time-varying formant resonators (+ a nasal pole/zero pair for
    the closed-mouth "mmm" of a moo or a bleat). Mouth shapes are key-framed vowels.
  * frogs: trains of damped vocal-sac pulses (the pulse rate is the "rrr", the resonance
    the hollow "kung" / "krok").
Every call gets a whisper of outdoor space, a gentle top roll-off (cute, never harsh),
is trimmed, faded and normalised to about -16 LUFS with a soft look-ahead limiter
(peaks <= -1.5 dBFS).

Output (mono Ogg Vorbis, 24 kHz) into game/assets/audio/animals/, used by
game/scripts/world/animals.gd through AudioStreamPlayer3D on the "SFX" bus:
  sapi_1..3      Bali cow moo            kerbau_1..3   water buffalo, lower and longer
  kambing_1..3   goat "mbeeek" bleat     ayam_1..3     hen clucks
  ayam_crow      rooster "kukuruyuk"     bebek_1..3    duck "kwek"
  kodok_1..3     frog kung-kong / ribbit / krok     kucing_1..3  cat meow
  anjing_1..3    kampung dog "guk" barks

  python3 tools/make_animal_sounds.py                # everything
  python3 tools/make_animal_sounds.py sapi kodok     # only these species
  python3 tools/make_animal_sounds.py --png DIR      # also spectrogram overviews per species
  python3 tools/make_animal_sounds.py --wav DIR      # also keep 16-bit WAV masters

Needs numpy, scipy, soundfile, pyloudnorm, ffmpeg with libvorbis (matplotlib for --png).
"""
import argparse
import os
import subprocess
import tempfile

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "audio", "animals")
SR = 24000
TARGET_LUFS = -16.0
PEAK_DB = -1.5
MAX_GR_DB = 4.0          # the limiter may shave at most this much; beyond it the gain drops
VORBIS_Q = 3             # ffmpeg libvorbis -q:a (mono 24 kHz: ~55 kbps)


# ====================================================================== basics
def n_of(sec):
    return max(1, int(round(sec * SR)))


def db(x):
    return 10 ** (x / 20.0)


def track(pts, n, log=True):
    """a control curve over n samples from key points [(t_sec, value), ...] (monotone
    cubic; in the log domain for frequencies), or a constant from a scalar"""
    if np.isscalar(pts):
        return np.full(n, float(pts))
    pts = np.asarray(pts, float)
    if len(pts) == 1:
        return np.full(n, pts[0, 1])
    t = np.clip(np.arange(n) / SR, pts[0, 0], pts[-1, 0])
    if log and np.all(pts[:, 1] > 0):
        return np.exp(PchipInterpolator(pts[:, 0], np.log(pts[:, 1]))(t))
    return PchipInterpolator(pts[:, 0], pts[:, 1])(t)


def smooth_noise(n, rng, width):
    """band-limited random curve (unit-ish std) that changes about every `width` samples"""
    width = max(2, int(width))
    m = n // width + 4
    k = rng.normal(size=m)
    x = np.arange(n) / width
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return k[i] * (1 - f) + k[i + 1] * f


def fade(x, a=0.004, r=0.03):
    x = x.copy()
    na, nr = min(len(x), n_of(a)), min(len(x), n_of(r))
    x[:na] *= np.sin(np.linspace(0, np.pi / 2, na)) ** 2
    x[-nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    return x


def seq(parts):
    """[(signal, gap_after_sec) or signal, ...] -> one signal"""
    out = []
    for p in parts:
        sig, gap = p if isinstance(p, tuple) else (p, 0.0)
        out.append(sig)
        if gap > 0:
            out.append(np.zeros(n_of(gap)))
        elif gap < 0:                       # overlap into the next part
            out.append(-n_of(-gap))
    y = np.zeros(sum(len(o) if not isinstance(o, int) else 0 for o in out) + 1)
    pos = 0
    for o in out:
        if isinstance(o, int):
            pos += o
            continue
        end = pos + len(o)
        if end > len(y):
            y = np.concatenate([y, np.zeros(end - len(y))])
        y[pos:end] += o
        pos = end
    return y


def butter(x, fc, kind, order=2):
    return signal.sosfilt(signal.butter(order, fc / (SR / 2), kind, output="sos"), x)


# ====================================================================== the voice
_GLOT = {}


def glottal_coefs(oq, sq, K=600):
    """harmonic amplitudes / phases of one period of a Rosenberg glottal flow derivative
    (open quotient oq, rise/fall speed quotient sq); fundamental normalised to 1"""
    key = (round(oq, 3), round(sq, 3))
    if key not in _GLOT:
        N = 8192
        t = np.arange(N) / N
        tn = oq / (1 + sq)
        tp = oq - tn
        g = np.where(t < tp, 0.5 * (1 - np.cos(np.pi * t / tp)),
                     np.where(t < oq, np.cos(0.5 * np.pi * (t - tp) / tn), 0.0))
        d = np.diff(np.concatenate([g, g[:1]]))
        C = np.fft.rfft(d)[1:K + 1]
        _GLOT[key] = (np.abs(C) / np.abs(C[0]), np.angle(C))
    return _GLOT[key]


def glottal_source(f0, rng, oq=0.6, sq=2.5, tilt=0.0, jitter=0.01, shimmer=0.05, rough=0.0):
    """band-limited voiced source following f0 (Hz per sample). tilt: extra spectral
    slope in dB/octave (array or scalar; softer = darker); rough: period doubling"""
    n = len(f0)
    per = SR / max(60.0, float(np.median(f0)))
    f = f0 * (1 + np.asarray(jitter) * smooth_noise(n, rng, per))
    ph = 2 * np.pi * np.cumsum(f) / SR + rng.uniform(0, 6.28)
    mag, pha = glottal_coefs(oq, sq)
    kmax = min(len(mag), int(SR * 0.46 / max(40.0, f.min())))
    tilt = np.asarray(tilt, float)
    y = np.zeros(n)
    for k in range(1, kmax + 1):
        g = np.clip((SR * 0.46 - k * f) / (SR * 0.05), 0.0, 1.0)      # fade out at Nyquist
        a = mag[k - 1] * g
        if np.any(tilt != 0):
            a = a * np.exp(-tilt / 6.02 * np.log(k))
        y += a * np.cos(k * ph + pha[k - 1])
    y *= 1 + np.asarray(shimmer) * smooth_noise(n, rng, per)
    rough = np.asarray(rough, float)
    if np.any(rough > 0):
        # alternate louder / softer cycles (subharmonics at f0/2) + a little cycle chaos
        y *= 1 + rough * (0.8 * np.cos(ph / 2 + 0.3) + 0.35 * smooth_noise(n, rng, per))
    return y, ph


def klatt_res(x, F, BW):
    """time-varying 2-pole resonator, unity gain at DC (Klatt 1980)"""
    C = -np.exp(-2 * np.pi * BW / SR)
    B = 2 * np.exp(-np.pi * BW / SR) * np.cos(2 * np.pi * F / SR)
    A = 1 - B - C
    if np.ndim(F) == 0 and np.ndim(BW) == 0:
        return signal.lfilter([A], [1, -B, -C], x)
    n = len(x)
    A = np.broadcast_to(A, (n,)).tolist()
    B = np.broadcast_to(B, (n,)).tolist()
    C = np.broadcast_to(C, (n,)).tolist()
    xs = x.tolist()
    out = [0.0] * n
    y1 = y2 = 0.0
    for i in range(n):
        y = A[i] * xs[i] + B[i] * y1 + C[i] * y2
        out[i] = y
        y2 = y1
        y1 = y
    return np.array(out)


def klatt_anti(x, F, BW):
    """time-varying antiresonator (the nasal zero), unity gain at DC"""
    C = -np.exp(-2 * np.pi * BW / SR)
    B = 2 * np.exp(-np.pi * BW / SR) * np.cos(2 * np.pi * F / SR)
    A = 1 - B - C
    x1 = np.concatenate([[0.0], x[:-1]])
    x2 = np.concatenate([[0.0, 0.0], x[:-2]])
    return (x - B * x1 - C * x2) / A


def vowel_tracks(keys, n):
    """keys [(t_sec, [(F, BW), ...]), ...] -> [(F array, BW array), ...] per formant"""
    nf = len(keys[0][1])
    out = []
    for j in range(nf):
        Fp = [(t, v[j][0]) for t, v in keys]
        Bp = [(t, v[j][1]) for t, v in keys]
        out.append((track(Fp, n), track(Bp, n)))
    return out


def voice(dur, f0, amp, vowels, rng, oq=0.6, sq=2.5, tilt=2.0, dyn_tilt=5.0, jitter=0.01, shimmer=0.05,
          vib=None, trem=0.0, rough=0.0, breath=0.08, nasal=None, noise_hp=400.0):
    """one voiced call.
    f0, amp, rough, breath, jitter: key points [(t, v)] or scalars
    vowels: [(t, [(F1, BW1), ... (F5, BW5)]), ...] mouth shapes over time
    vib: (rate Hz, depth (fraction) pts, irregularity) - pitch vibrato / quaver
    trem: how much the loudness follows the vibrato (goat bleat)
    nasal: [(t, nasal pole Hz, nasal zero Hz), ...] - equal values = mouth open
    dyn_tilt: extra darkening (dB/oct) where the call is soft (loud = bright, like a voice)"""
    n = n_of(dur)
    f = track(f0, n)
    a = track(amp, n, log=False).clip(0, None)
    if vib is not None:
        rate, depth, irr = vib
        r = track(rate, n) * (1 + irr * smooth_noise(n, rng, n_of(0.07)))
        vph = 2 * np.pi * np.cumsum(r) / SR + rng.uniform(0, 6.28)
        d = track(depth, n, log=False)
        # a slightly peaky wave: bleats and moos quaver in pulses, not in sines
        w = np.sin(vph) + 0.25 * np.sin(2 * vph + 0.7)
        f = f * (1 + d * w / 1.1)
        if trem:
            a = a * (1 - trem * (0.5 - 0.5 * w / 1.1))
    tl = tilt + dyn_tilt * (1 - a / (a.max() + 1e-9))
    src, ph = glottal_source(f, rng, oq, sq, tl, track(jitter, n, log=False), shimmer,
                             track(rough, n, log=False))
    rms = np.sqrt(np.mean(src ** 2)) + 1e-9
    nz = rng.normal(size=n)
    nz = butter(nz, noise_hp, "high", 1)
    nz *= 0.45 + 0.55 * (0.5 + 0.5 * np.cos(ph - 1.0))           # pulse-synchronous breath
    nz *= rms / (np.sqrt(np.mean(nz ** 2)) + 1e-9)
    x = a * (src + track(breath, n, log=False) * nz)
    if nasal is not None:
        npf = track([(t, p) for t, p, z in nasal], n)
        nzf = track([(t, z) for t, p, z in nasal], n)
        x = klatt_res(x, npf, 110.0)
        x = klatt_anti(x, nzf, 110.0)
    for F, BW in vowel_tracks(vowels, n):
        x = klatt_res(x, F, BW)
    return x


def burst(dur, fc, bw, rng, decay=None):
    """a short, soft noise burst (a beak 'tok', a 'k' release)"""
    n = n_of(dur)
    lo, hi = max(80.0, fc - bw / 2), min(SR * 0.45, fc + bw / 2)
    y = signal.sosfilt(signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), rng.normal(size=n))
    t = np.arange(n) / SR
    env = (1 - np.exp(-t / 0.002)) * np.exp(-t / (decay or dur / 3))
    return y * env


def pad_to(x, n):
    return np.concatenate([x, np.zeros(max(0, n - len(x)))])


# ====================================================================== space & output
_IR = {}


def space_ir(rt60=0.35, seed=5):
    """a small, soft outdoor space: diffuse tail with the highs dying first"""
    if rt60 in _IR:
        return _IR[rt60]
    rng = np.random.default_rng(seed)
    n = n_of(rt60 * 1.1)
    t = np.arange(n) / SR
    lo = butter(rng.normal(size=n), 1800, "low") * np.exp(-6.91 * t / rt60)
    hi = butter(rng.normal(size=n), 1800, "high") * np.exp(-6.91 * t / (rt60 * 0.45))
    ir = (lo + 0.5 * hi) * (1 - np.exp(-t / 0.006))
    ir = butter(ir, 120, "high")
    ir /= np.sqrt(np.sum(ir ** 2))
    ir = np.concatenate([np.zeros(n_of(0.008)), ir])
    _IR[rt60] = ir
    return ir


def lufs(x):
    meter = pyln.Meter(SR, block_size=0.4)
    return meter.integrated_loudness(pad_to(x, n_of(0.6)))


def limiter(y, ceil_db=PEAK_DB):
    """look-ahead peak limiter (smooth gain; ~3 ms look-ahead, ~12 ms smoothing)"""
    c = db(ceil_db)
    env = maximum_filter1d(np.abs(y), size=2 * n_of(0.003) + 1)
    g = np.minimum(1.0, c / np.maximum(env, 1e-12))
    w = n_of(0.012)
    g = minimum_filter1d(g, size=2 * w + 1)
    g = uniform_filter1d(g, size=w)
    return y * g


def write_ogg(path, y):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp = tf.name
    try:
        sf.write(tmp, y.astype(np.float32), SR, subtype="PCM_16")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-map_metadata", "-1",
                        "-c:a", "libvorbis", "-q:a", str(VORBIS_Q), "-ac", "1", "-ar", str(SR), path], check=True)
    finally:
        os.remove(tmp)


RESULTS = {}


def finish(name, y, args, hp=60.0, lp=7500.0, wet=0.12, rt60=0.35):
    y = np.asarray(y, float)
    y = y - np.mean(y)
    y = butter(y, hp, "high")
    y = butter(y, lp, "low", 1)                               # a soft top, never a hiss
    y = y / (np.abs(y).max() + 1e-12)
    ir = space_ir(rt60)
    y = np.concatenate([np.zeros(n_of(0.004)), y, np.zeros(len(ir))])
    y = (1 - wet) * y + wet * signal.fftconvolve(y, ir)[:len(y)]
    # trim: start at the first sound, end where the tail is 55 dB down
    thr = np.abs(y).max() * db(-55)
    on = np.nonzero(np.abs(y) > thr)[0]
    y = y[max(0, on[0] - n_of(0.003)):on[-1] + 1]
    y = fade(y, 0.003, min(0.06, len(y) / SR / 5))
    gain = TARGET_LUFS - lufs(y)
    y = y * db(gain)
    pk = 20 * np.log10(np.abs(y).max() + 1e-12)
    over = pk - PEAK_DB
    if over > MAX_GR_DB:                                      # don't squash: drop the gain instead
        y *= db(-(over - MAX_GR_DB))
    if over > 0:
        y = limiter(y)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".ogg")
    write_ogg(path, y)
    L = lufs(y)
    pk = 20 * np.log10(np.abs(y).max() + 1e-12)
    size = os.path.getsize(path)
    P = np.abs(np.fft.rfft(y)) ** 2
    fr = np.fft.rfftfreq(len(y), 1.0 / SR)
    cen = float(np.sum(fr * P) / np.sum(P))
    hi = 10 * np.log10(np.sum(P[fr > 2000]) / np.sum(P) + 1e-12)
    print(f"  {name:12s} {len(y) / SR:5.2f}s  {L:6.1f} LUFS  peak {pk:5.1f} dBFS  {size / 1024:5.1f} KB  "
          f"centroid {cen:5.0f} Hz  >2k {hi:5.1f} dB", flush=True)
    RESULTS[name] = (y, size)
    if args.wav:
        os.makedirs(args.wav, exist_ok=True)
        sf.write(os.path.join(args.wav, name + ".wav"), y.astype(np.float32), SR, subtype="PCM_16")


# ====================================================================== cow & buffalo
# Mouth shapes (F, BW) of a big bovine vocal tract (~55 cm: formants ~300 Hz apart)
COW_M = [(220, 110), (650, 260), (1250, 380), (1900, 450), (2600, 550), (3300, 700), (4000, 900)]  # closed "mmm"
COW_U = [(330, 80), (760, 130), (1300, 190), (1950, 240), (2650, 320), (3300, 450), (4000, 600)]  # "ooo"
COW_O = [(440, 90), (880, 120), (1400, 170), (2000, 230), (2700, 300), (3350, 420), (4050, 550)]  # open "oOO"
BUF_M = [(190, 110), (560, 260), (1080, 380), (1650, 450), (2250, 550), (2900, 700), (3600, 900)]
BUF_U = [(280, 80), (640, 140), (1120, 200), (1680, 260), (2300, 330), (2950, 450), (3650, 600)]
BUF_O = [(360, 95), (740, 130), (1200, 180), (1750, 240), (2350, 320), (3000, 420), (3700, 550)]


def moo(rng, dur, f0, amp, mouth, closed, mid, opn, rough=0.05, breath=0.12, vib=(4.5, 0.012, 0.3),
        jitter=0.012, tilt=-4.0):
    """mouth: [(t, 0 closed .. 1 mid .. 2 open)] -> vowel key frames + nasal coupling.
    The source is pre-emphasised (tilt < 0): a 7-formant cascade of a long bovine tract
    falls far too steeply without it and the moo would be a dull hum on phone speakers."""
    keys, nas = [], []
    for t, m in mouth:
        if m <= 1:
            v = [(np.exp(np.log(c[0]) * (1 - m) + np.log(u[0]) * m), c[1] * (1 - m) + u[1] * m)
                 for c, u in zip(closed, mid)]
        else:
            k = m - 1
            v = [(np.exp(np.log(u[0]) * (1 - k) + np.log(o[0]) * k), u[1] * (1 - k) + o[1] * k)
                 for u, o in zip(mid, opn)]
        keys.append((t, v))
        nz = 900 * (1 - min(1, m)) + 300 * min(1, m)          # the nasal zero closes up as the mouth opens
        nas.append((t, 300.0, nz))
    return voice(dur, f0, amp, keys, rng, oq=0.62, sq=2.4, tilt=tilt, dyn_tilt=5.0, jitter=jitter,
                 shimmer=0.06, vib=vib, rough=rough, breath=breath, nasal=nas, noise_hp=250.0)


def sapi(rng):
    out = []
    # 1: the classic long "mmmmOOOOoh" with a swell and a creaky end
    out.append(moo(rng, 1.75,
                   [(0, 96), (0.3, 108), (0.65, 136), (1.05, 142), (1.35, 126), (1.62, 96), (1.75, 84)],
                   [(0, 0), (0.1, 0.22), (0.35, 0.4), (0.7, 0.95), (1.15, 1.0), (1.45, 0.72), (1.66, 0.25), (1.75, 0)],
                   [(0, 0), (0.3, 0.1), (0.62, 1.2), (0.95, 2.0), (1.3, 1.8), (1.55, 1.0), (1.75, 0.5)],
                   COW_M, COW_U, COW_O,
                   rough=[(0, 0.03), (1.3, 0.05), (1.6, 0.45), (1.75, 0.6)],
                   jitter=[(0, 0.01), (1.35, 0.012), (1.7, 0.04)]))
    # 2: a shorter, higher "mm-MOO-oh?" (calling the herd)
    out.append(moo(rng, 1.25,
                   [(0, 104), (0.2, 116), (0.55, 158), (0.85, 164), (1.1, 128), (1.25, 104)],
                   [(0, 0), (0.08, 0.3), (0.3, 0.7), (0.55, 1.0), (0.95, 0.85), (1.15, 0.35), (1.25, 0)],
                   [(0, 0), (0.18, 0.2), (0.45, 1.6), (0.8, 2.0), (1.05, 1.3), (1.25, 0.6)],
                   COW_M, COW_U, COW_O,
                   rough=[(0, 0.03), (1.0, 0.06), (1.25, 0.35)], vib=(5.0, 0.014, 0.3)))
    # 3: a soft, content "mmmh-oh" hum, mouth hardly open
    out.append(moo(rng, 0.95,
                   [(0, 100), (0.3, 112), (0.6, 114), (0.95, 92)],
                   [(0, 0), (0.1, 0.5), (0.45, 1.0), (0.75, 0.7), (0.95, 0)],
                   [(0, 0), (0.35, 0.5), (0.6, 1.3), (0.95, 0.5)],
                   COW_M, COW_U, COW_O, rough=[(0, 0.03), (0.7, 0.05), (0.95, 0.4)], breath=0.16,
                   vib=(4.0, 0.01, 0.3)))
    return out


def kerbau(rng):
    out = []
    # 1: a long, low, hoarse "mmmuuuuuh"
    out.append(moo(rng, 2.25,
                   [(0, 74), (0.4, 84), (0.9, 94), (1.5, 92), (1.95, 76), (2.25, 64)],
                   [(0, 0), (0.15, 0.25), (0.5, 0.6), (0.9, 1.0), (1.6, 0.9), (2.0, 0.4), (2.25, 0)],
                   [(0, 0), (0.45, 0.4), (0.9, 1.4), (1.5, 1.8), (1.9, 1.2), (2.25, 0.5)],
                   BUF_M, BUF_U, BUF_O,
                   rough=[(0, 0.12), (1.5, 0.15), (2.0, 0.5), (2.25, 0.6)], breath=0.2,
                   vib=(3.5, 0.01, 0.4), jitter=[(0, 0.015), (1.8, 0.02), (2.2, 0.05)], tilt=-5.5))
    # 2: "uuh ... uuuuh" - a low grunt then the call
    a = moo(rng, 0.55, [(0, 70), (0.2, 80), (0.55, 68)], [(0, 0), (0.08, 0.8), (0.3, 1.0), (0.55, 0)],
            [(0, 0.2), (0.25, 1.0), (0.55, 0.5)], BUF_M, BUF_U, BUF_O, rough=0.3, breath=0.22,
            vib=(3.0, 0.008, 0.4), jitter=0.02, tilt=-5.5)
    b = moo(rng, 1.5, [(0, 78), (0.45, 96), (0.9, 98), (1.25, 82), (1.5, 66)],
            [(0, 0), (0.15, 0.5), (0.5, 1.0), (1.0, 0.85), (1.3, 0.4), (1.5, 0)],
            [(0, 0.1), (0.4, 1.4), (0.9, 1.6), (1.2, 1.0), (1.5, 0.4)], BUF_M, BUF_U, BUF_O,
            rough=[(0, 0.12), (1.1, 0.15), (1.5, 0.55)], breath=0.2, vib=(3.5, 0.012, 0.4),
            jitter=[(0, 0.015), (1.2, 0.02), (1.5, 0.05)], tilt=-5.5)
    out.append(seq([(a * 0.7, 0.28), b]))
    # 3: a short questioning "mmh-oh"
    out.append(moo(rng, 1.05, [(0, 80), (0.35, 92), (0.7, 104), (1.05, 84)],
                   [(0, 0), (0.12, 0.45), (0.5, 1.0), (0.85, 0.6), (1.05, 0)],
                   [(0, 0), (0.4, 0.8), (0.75, 1.7), (1.05, 0.8)], BUF_M, BUF_U, BUF_O,
                   rough=[(0, 0.1), (0.8, 0.15), (1.05, 0.5)], breath=0.2, vib=(3.8, 0.01, 0.4), tilt=-5.5))
    return out


# ====================================================================== goat
GOAT_M = [(320, 120), (1250, 350), (2500, 450), (3400, 500), (4300, 600)]     # closed "m"
GOAT_E = [(640, 110), (1750, 150), (2650, 220), (3450, 300), (4400, 400)]     # "eeh"
GOAT_A = [(760, 120), (1550, 150), (2550, 220), (3400, 300), (4400, 400)]     # "eh/ah"


def bleat(rng, dur, f0, amp, keys, vib, trem=0.45, rough=0.12, breath=0.1):
    t_open = keys[1][0]
    nas = [(0, 400.0, 1100.0), (t_open, 400.0, 700.0), (t_open + 0.08, 400.0, 400.0), (dur, 400.0, 400.0)]
    return voice(dur, f0, amp, keys, rng, oq=0.55, sq=2.8, tilt=1.5, dyn_tilt=5.0, jitter=0.012,
                 shimmer=0.08, vib=vib, trem=trem, rough=rough, breath=breath, nasal=nas)


def kambing(rng):
    out = []
    # 1: an adult "mbeeeeh-eh", the quaver slowing and deepening towards the end
    out.append(bleat(rng, 1.05,
                     [(0, 255), (0.12, 300), (0.4, 335), (0.8, 305), (1.05, 250)],
                     [(0, 0), (0.05, 0.35), (0.14, 1.0), (0.7, 0.85), (0.95, 0.4), (1.05, 0)],
                     [(0, GOAT_M), (0.1, GOAT_M), (0.2, GOAT_E), (0.75, GOAT_E), (1.05, GOAT_A)],
                     vib=([(0, 11.5), (1.05, 7.5)], [(0, 0.015), (0.22, 0.06), (1.05, 0.1)], 0.25)))
    # 2: a kid's higher, thinner "meeeh"
    out.append(bleat(rng, 0.7,
                     [(0, 470), (0.1, 540), (0.35, 575), (0.7, 470)],
                     [(0, 0), (0.05, 0.4), (0.12, 1.0), (0.5, 0.8), (0.7, 0)],
                     [(0, GOAT_M), (0.07, GOAT_M), (0.15, GOAT_E), (0.7, GOAT_A)],
                     vib=([(0, 12.5), (0.7, 9.5)], [(0, 0.02), (0.2, 0.05), (0.7, 0.075)], 0.25),
                     trem=0.4, rough=0.06, breath=0.08))
    # 3: "meh ... meeeh-eh-eh"
    a = bleat(rng, 0.32, [(0, 285), (0.1, 320), (0.32, 280)], [(0, 0), (0.05, 0.5), (0.1, 1.0), (0.32, 0)],
              [(0, GOAT_M), (0.06, GOAT_M), (0.13, GOAT_A), (0.32, GOAT_A)],
              vib=(11.0, 0.03, 0.2), trem=0.3, rough=0.1)
    b = bleat(rng, 0.9, [(0, 300), (0.12, 350), (0.5, 340), (0.9, 265)],
              [(0, 0), (0.05, 0.45), (0.13, 1.0), (0.6, 0.8), (0.9, 0)],
              [(0, GOAT_M), (0.08, GOAT_M), (0.17, GOAT_E), (0.9, GOAT_A)],
              vib=([(0, 11.0), (0.9, 7.0)], [(0, 0.02), (0.2, 0.065), (0.9, 0.11)], 0.3), trem=0.5)
    out.append(seq([(a * 0.8, 0.12), b]))
    return out


# ====================================================================== chicken & rooster
HEN_O = [(560, 130), (1350, 200), (2600, 300), (3500, 400), (4500, 500)]
HEN_A = [(820, 140), (1600, 200), (2700, 300), (3600, 400), (4600, 500)]
HEN_U = [(480, 120), (1100, 200), (2500, 300), (3400, 400), (4400, 500)]


def cluck(rng, dur, f0a, f0b, amp=1.0, vowel=HEN_O, click=0.12, rough=0.2):
    """one 'bok' / 'tok': a short voiced call with a soft beak click in front"""
    v = voice(dur, [(0, f0a), (dur * 0.3, f0a * 1.04), (dur, f0b)],
              [(0, 0), (dur * 0.12, 1.0), (dur * 0.55, 0.7), (dur, 0)],
              [(0, HEN_U), (dur * 0.35, vowel), (dur, HEN_U)], rng, oq=0.5, sq=3.0, tilt=1.5, dyn_tilt=4.0,
              jitter=0.02, shimmer=0.12, rough=rough, breath=0.12)
    v /= np.abs(v).max() + 1e-9
    if click:
        b = burst(0.014, 1500, 1400, rng, decay=0.003)
        b /= np.abs(b).max() + 1e-9
        v = seq([(b * click, -0.006), v])
    return v * amp


def ayam(rng):
    out = []
    # 1: a content hen pottering about: "tok ... tok-tok ... took"
    out.append(seq([(cluck(rng, 0.07, 300, 280, 0.8), 0.32), (cluck(rng, 0.06, 320, 295, 0.7), 0.13),
                    (cluck(rng, 0.065, 310, 285, 0.75), 0.42),
                    (cluck(rng, 0.11, 290, 250, 0.85, HEN_O, 0.1), 0.0)]))
    # 2: the egg song: "bok bok bok b'GAAAWK"
    n = 0.38
    gawk = voice(n, [(0, 380), (0.08, 560), (0.2, 600), (n, 470)], [(0, 0), (0.03, 0.6), (0.08, 1.0), (0.25, 0.85), (n, 0)],
                 [(0, HEN_U), (0.07, HEN_O), (0.13, HEN_A), (0.3, HEN_A), (n, HEN_O)], rng, oq=0.45, sq=3.0,
                 tilt=1.0, dyn_tilt=4.0, jitter=0.025, shimmer=0.12, rough=[(0, 0.15), (0.15, 0.3), (n, 0.2)],
                 breath=0.15, vib=(24.0, 0.02, 0.3))
    gawk /= np.abs(gawk).max() + 1e-9
    out.append(seq([(cluck(rng, 0.075, 360, 330, 0.75, HEN_A), 0.2), (cluck(rng, 0.075, 370, 335, 0.8, HEN_A), 0.16),
                    (cluck(rng, 0.075, 380, 340, 0.85, HEN_A), 0.1), (gawk * 0.95, 0.0)]))
    # 3: a quick purring "brrr-rook?" (a hen talking to her chicks)
    trill = [(cluck(rng, 0.03, 330, 320, 0.45 + 0.08 * i, HEN_U, 0.0, 0.1), 0.018) for i in range(5)]
    ook = voice(0.16, [(0, 330), (0.1, 400), (0.16, 420)], [(0, 0), (0.03, 1.0), (0.1, 0.8), (0.16, 0)],
                [(0, HEN_U), (0.07, HEN_O), (0.16, HEN_U)], rng, oq=0.5, sq=3.0, tilt=2.0, jitter=0.02,
                shimmer=0.1, rough=0.15, breath=0.12)
    ook /= np.abs(ook).max() + 1e-9
    out.append(seq(trill + [(ook * 0.85, 0.0)]))
    return out


def ayam_crow(rng):
    """ayam jago: "ku-ku-ru-yuuuuk" - brassy but round"""
    U = [(620, 140), (1200, 200), (2600, 300), (3500, 400), (4500, 500)]
    E = [(950, 150), (1850, 220), (2800, 300), (3700, 400), (4600, 500)]
    O = [(780, 140), (1450, 200), (2650, 300), (3600, 400), (4500, 500)]
    parts = []
    for d, fa, fb, gap, amp in [(0.11, 500, 540, 0.07, 0.7), (0.11, 560, 600, 0.06, 0.8), (0.16, 620, 740, 0.03, 0.9)]:
        v = voice(d, [(0, fa), (d, fb)], [(0, 0), (d * 0.2, 1.0), (d * 0.7, 0.85), (d, 0)], [(0, U), (d, U)], rng,
                  oq=0.45, sq=3.0, tilt=1.0, dyn_tilt=4.0, jitter=0.025, shimmer=0.12, rough=0.18, breath=0.15)
        parts.append((v / (np.abs(v).max() + 1e-9) * amp, gap))
    d = 1.0
    v = voice(d, [(0, 760), (0.1, 840), (0.55, 820), (0.8, 760), (0.95, 640), (d, 560)],
              [(0, 0), (0.05, 1.0), (0.6, 0.92), (0.85, 0.6), (0.95, 0.35), (d, 0)],
              [(0, U), (0.1, E), (0.55, E), (0.8, O), (d, U)], rng, oq=0.42, sq=3.0, tilt=0.8, dyn_tilt=4.0,
              jitter=0.02, shimmer=0.12, rough=[(0, 0.2), (0.5, 0.28), (d, 0.35)], breath=0.16,
              vib=(7.0, 0.012, 0.3))
    parts.append(v / (np.abs(v).max() + 1e-9))
    return [seq(parts)]


# ====================================================================== duck
DUCK_W = [(420, 150), (900, 220), (2300, 350), (3300, 450), (4300, 550)]
DUCK_A = [(1000, 160), (1650, 200), (2600, 280), (3500, 380), (4400, 500)]
DUCK_E = [(820, 150), (1850, 200), (2700, 280), (3600, 380), (4500, 500)]


def quack(rng, dur, f0, amp=1.0, vowel=DUCK_A):
    """"kwek": a nasal, buzzy, fast-opening quack with a soft 'k' and a clipped end"""
    v = voice(dur, [(0, f0 * 0.92), (dur * 0.25, f0 * 1.05), (dur, f0 * 0.86)],
              [(0, 0), (dur * 0.12, 0.9), (dur * 0.3, 1.0), (dur * 0.82, 0.8), (dur, 0)],
              [(0, DUCK_W), (dur * 0.3, vowel), (dur * 0.8, vowel), (dur, DUCK_E)], rng, oq=0.42, sq=3.2,
              tilt=0.5, dyn_tilt=3.0, jitter=0.03, shimmer=0.15, rough=0.35, breath=0.22,
              nasal=[(0, 1100.0, 750.0), (dur, 1100.0, 800.0)])
    v /= np.abs(v).max() + 1e-9
    k = burst(0.016, 1500, 1600, rng, decay=0.004)
    k /= np.abs(k).max() + 1e-9
    return seq([(k * 0.18, -0.008), v]) * amp


def bebek(rng):
    out = []
    out.append(seq([(quack(rng, 0.15, 290, 0.95), 0.1), (quack(rng, 0.14, 280, 0.85, DUCK_E), 0.0)]))  # kwek kwek
    out.append(quack(rng, 0.24, 250, 1.0))                                                             # quaaack
    parts = []
    for i in range(5):                                                         # the laughing decrescendo
        parts.append((quack(rng, 0.13 - 0.008 * i, 305 - 14 * i, 1.0 - 0.12 * i), 0.07 + 0.012 * i))
    out.append(seq(parts))
    return out


# ====================================================================== frog
def frog_call(rng, dur, rate, fc, amp, tau=0.004, fc2=None, a2=0.0, jit=0.04):
    """a pulse train: every vocal-sac pulse is a damped sinusoid (fc) with an optional
    second resonance (fc2); the pulse rate gives the 'rrr'"""
    n = n_of(dur)
    y = np.zeros(n + n_of(tau * 8))
    rate_t = track(rate, n)
    fc_t = track(fc, n)
    fc2_t = track(fc2, n) if fc2 is not None else None
    amp_t = track(amp, n, log=False)
    t = 0.0
    while t < dur:
        i = min(n - 1, int(t * SR))
        m = n_of(tau * 8)
        tt = np.arange(m) / SR
        env = (1 - np.exp(-tt / 0.0012)) * np.exp(-tt / tau)
        p = np.sin(2 * np.pi * fc_t[i] * tt) * env
        if fc2_t is not None:
            p += a2 * np.sin(2 * np.pi * fc2_t[i] * tt + 0.5) * (1 - np.exp(-tt / 0.0008)) * np.exp(-tt / (tau * 0.6))
        y[i:i + m] += p * amp_t[i] * (1 + 0.1 * rng.normal())
        t += (1.0 / rate_t[i]) * (1 + jit * rng.normal())
    return y


def kodok(rng):
    out = []
    # 1: "kung ... kong" - two hollow, low calls (the kodok of the rice-field song)
    kung = frog_call(rng, 0.24, [(0, 105), (0.24, 92)], [(0, 540), (0.05, 560), (0.24, 500)],
                     [(0, 0), (0.02, 1.0), (0.1, 0.8), (0.24, 0)], tau=0.007, fc2=[(0, 1100), (0.24, 1000)], a2=0.25)
    kong = frog_call(rng, 0.3, [(0, 92), (0.3, 80)], [(0, 440), (0.06, 460), (0.3, 400)],
                     [(0, 0), (0.025, 1.0), (0.12, 0.8), (0.3, 0)], tau=0.008, fc2=[(0, 900), (0.3, 820)], a2=0.2)
    kung2 = frog_call(rng, 0.22, [(0, 102), (0.22, 92)], [(0, 530), (0.05, 550), (0.22, 500)],
                      [(0, 0), (0.02, 1.0), (0.1, 0.8), (0.22, 0)], tau=0.007, fc2=[(0, 1080), (0.22, 1000)], a2=0.25)
    out.append(seq([(kung, 0.16), (kong, 0.42), (kung2 * 0.8, 0.0)]))
    # 2: "rib-bit ... rib-bit"
    def ribbit(s):
        rib = frog_call(rng, 0.13, [(0, 60), (0.13, 75)], [(0, 700 * s), (0.13, 780 * s)],
                        [(0, 0.3), (0.03, 1.0), (0.1, 0.9), (0.13, 0.3)], tau=0.0035, fc2=1500 * s, a2=0.45)
        bit = frog_call(rng, 0.07, 95, [(0, 820 * s), (0.07, 900 * s)], [(0, 0.5), (0.02, 1.0), (0.07, 0.2)],
                        tau=0.003, fc2=1700 * s, a2=0.4)
        return seq([(rib, 0.05), bit])
    out.append(seq([(ribbit(1.0), 0.36), ribbit(0.95) * 0.85]))
    # 3: "krok krok krok" (kodok ngorek)
    parts = []
    for i in range(4):
        c = frog_call(rng, 0.12 + 0.01 * (i == 3), [(0, 58), (0.12, 66)], [(0, 610), (0.12, 650)],
                      [(0, 0.2), (0.02, 1.0), (0.09, 0.85), (0.13, 0.1)], tau=0.0045, fc2=1250, a2=0.4)
        parts.append((c * (0.8 + 0.2 * (i % 2)), 0.17 + 0.03 * rng.random()))
    out.append(seq(parts))
    return out


# ====================================================================== cat
CAT_M = [(480, 120), (2200, 300), (3300, 350), (4300, 450), (5300, 550)]
CAT_I = [(620, 110), (2450, 180), (3350, 250), (4300, 350), (5300, 450)]
CAT_A = [(1100, 150), (1850, 170), (3150, 250), (4200, 350), (5200, 450)]
CAT_O = [(820, 130), (1350, 160), (3000, 250), (4100, 350), (5100, 450)]
CAT_U = [(560, 120), (1050, 170), (2900, 280), (4000, 380), (5000, 480)]


def meow(rng, dur, f0, amp, keys, breath=0.08, vib=(6.0, 0.01, 0.3), trem=0.0):
    t_open = keys[1][0]
    nas = [(0, 500.0, 1400.0), (t_open, 500.0, 900.0), (t_open + 0.06, 500.0, 500.0), (dur, 500.0, 500.0)]
    return voice(dur, f0, amp, keys, rng, oq=0.6, sq=2.6, tilt=2.5, dyn_tilt=5.0, jitter=0.008, shimmer=0.05,
                 vib=vib, trem=trem, rough=0.02, breath=breath, nasal=nas)


def kucing(rng):
    out = []
    # 1: "mi-aaa-ow"
    out.append(meow(rng, 0.85, [(0, 470), (0.15, 560), (0.38, 690), (0.6, 640), (0.85, 470)],
                    [(0, 0), (0.05, 0.35), (0.2, 0.9), (0.5, 1.0), (0.72, 0.6), (0.85, 0)],
                    [(0, CAT_M), (0.05, CAT_M), (0.16, CAT_I), (0.42, CAT_A), (0.66, CAT_O), (0.85, CAT_U)]))
    # 2: a short, high "mew"
    out.append(meow(rng, 0.42, [(0, 640), (0.12, 780), (0.25, 800), (0.42, 660)],
                    [(0, 0), (0.04, 0.5), (0.12, 1.0), (0.3, 0.75), (0.42, 0)],
                    [(0, CAT_M), (0.03, CAT_M), (0.1, CAT_I), (0.25, CAT_A), (0.42, CAT_U)], breath=0.06))
    # 3: "mrrr-aaow" - a rolled chirrup, then the ask
    d = 1.0
    out.append(meow(rng, d, [(0, 400), (0.22, 430), (0.45, 640), (0.65, 620), (d, 440)],
                    [(0, 0), (0.03, 0.4), (0.22, 0.5), (0.35, 0.95), (0.6, 1.0), (0.85, 0.5), (d, 0)],
                    [(0, CAT_M), (0.2, CAT_M), (0.33, CAT_I), (0.55, CAT_A), (0.8, CAT_O), (d, CAT_U)],
                    breath=0.1, vib=([(0, 26.0), (0.24, 24.0), (0.3, 6.0), (d, 6.0)],
                                     [(0, 0.05), (0.22, 0.05), (0.3, 0.01), (d, 0.01)], 0.1), trem=0.0))
    # the rolled 'rrr': amplitude flutter over the first 0.25 s
    y = out[-1]
    t = np.arange(len(y)) / SR
    flutter = 1 - 0.75 * (0.5 - 0.5 * np.cos(2 * np.pi * 25 * t)) * np.clip((0.32 - t) / 0.1, 0, 1)
    out[-1] = y * flutter
    return out


# ====================================================================== dog
DOG_W = [(420, 140), (950, 200), (2400, 300), (3300, 400), (4300, 500)]
DOG_A = [(760, 150), (1400, 180), (2500, 260), (3400, 360), (4400, 460)]
DOG_O = [(600, 140), (1100, 180), (2450, 280), (3350, 380), (4300, 480)]


def bark(rng, dur, f0, amp=1.0, vowel=DOG_A, grit=0.45):
    """"guk": a fast, rough, noisy onset that falls away in pitch and loudness"""
    v = voice(dur, [(0, f0 * 0.88), (dur * 0.18, f0 * 1.05), (dur * 0.55, f0 * 0.85), (dur, f0 * 0.62)],
              [(0, 0), (dur * 0.08, 0.85), (dur * 0.2, 1.0), (dur * 0.6, 0.55), (dur, 0)],
              [(0, DOG_W), (dur * 0.25, vowel), (dur * 0.6, vowel), (dur, DOG_O)], rng, oq=0.5, sq=3.0, tilt=1.5,
              dyn_tilt=5.0, jitter=[(0, 0.04), (dur * 0.3, 0.02), (dur, 0.03)], shimmer=0.15,
              rough=[(0, grit), (dur * 0.4, grit * 0.6), (dur, grit * 0.8)],
              breath=[(0, 0.7), (dur * 0.15, 0.25), (dur, 0.35)], noise_hp=500.0)
    v /= np.abs(v).max() + 1e-9
    return v * amp


def anjing(rng):
    out = []
    out.append(bark(rng, 0.2, 330, 1.0, DOG_A, 0.45))                                          # "woof"
    out.append(seq([(bark(rng, 0.15, 400, 1.0), 0.13), (bark(rng, 0.16, 385, 0.9, DOG_O), 0.0)]))  # "guk-guk"
    out.append(seq([(bark(rng, 0.11, 540, 0.9, DOG_A, 0.3), 0.12), (bark(rng, 0.11, 560, 1.0, DOG_A, 0.3), 0.11),
                    (bark(rng, 0.12, 530, 0.85, DOG_A, 0.3), 0.0)]))                             # "arf-arf-arf"
    return out


# ====================================================================== main
SPECIES = {
    "sapi": (sapi, dict(hp=45.0, lp=6500.0)),
    "kerbau": (kerbau, dict(hp=40.0, lp=6000.0)),
    "kambing": (kambing, dict()),
    "ayam": (ayam, dict(hp=120.0)),
    "bebek": (bebek, dict(hp=120.0, lp=7000.0)),
    "kodok": (kodok, dict(hp=70.0, lp=5000.0, wet=0.1)),
    "kucing": (kucing, dict(hp=120.0, lp=8000.0)),
    "anjing": (anjing, dict(hp=90.0, lp=7000.0)),
}


def png(names, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(len(names), 1, figsize=(12, 2.4 * len(names)), squeeze=False)
    for a, nm in zip(ax[:, 0], names):
        y = RESULTS[nm][0]
        f, t, S = signal.spectrogram(y, SR, nperseg=512, noverlap=448)
        a.pcolormesh(t, f, 10 * np.log10(S + 1e-14), vmin=-110, vmax=-35, shading="auto", cmap="magma")
        a.set_ylim(0, 8000)
        a.plot(np.arange(len(y)) / SR, 4000 + 3500 * y, lw=0.3, color="c", alpha=0.6)
        a.set_title(nm, fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=60)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*", help="species ids (default: all)")
    ap.add_argument("--png", help="write spectrogram overviews into this folder")
    ap.add_argument("--wav", help="also keep the WAV masters in this folder")
    args = ap.parse_args()
    todo = args.only or list(SPECIES)
    for sp in todo:
        fn, opts = SPECIES[sp]
        rng = np.random.default_rng(sum(map(ord, sp)) * 7919)      # stable per species
        print(sp, flush=True)
        names = []
        for i, y in enumerate(fn(rng), 1):
            finish(f"{sp}_{i}", y, args, **opts)
            names.append(f"{sp}_{i}")
        if sp == "ayam":
            finish("ayam_crow", ayam_crow(rng)[0], args, hp=150.0, lp=7000.0)
            names.append("ayam_crow")
        if args.png:
            os.makedirs(args.png, exist_ok=True)
            png(names, os.path.join(args.png, sp + ".png"))
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith(".ogg"))
    print(f"total {total / 1024:.1f} KB in {OUT}")


if __name__ == "__main__":
    main()

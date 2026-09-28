#!/usr/bin/env python3
"""Synthesises the location-based nature ambience of Sawit The Franchise.

Everything is generated from scratch in numpy (no samples): the noise beds come from
a spectro-temporal "mask" (each 11.6 ms frame gets a random-phase spectrum shaped by
the mask and the frames are overlap-added, so waves, wind gusts and water can change
colour over time), the animals from oscillator / pulse-train / formant models of the
real calls, and every element gets distance (air absorption + level) and a synthetic
outdoor reverb. Loops are built circularly (periodic noise, wrap-around event
placement, circular convolution and IIR warm-up over the loop), so the loop point is
seamless by construction.

Beds (seamless loops, played by game/scripts/world/ambience.gd on the "Ambience" bus):
  amb_sea       surf on the beach: low swell rumble, irregular waves (build-up, crash,
                wash, receding foam fizz), distant surf              (3D, at the coast)
  amb_river     a flowing river: flow bed, babbling bubbles (Minnaert bubble model),
                resonant gurgles, low rumble                          (3D, at the water)
  amb_lake      calm water lapping at the bank / jetty posts (the lagoon and the pond, 3D)
  amb_forest    tropical forest by day: wind in the leaves, distant birds of 8 species,
                a far tonggeret (cicada) swell
  amb_field     open land: soft wind with gusts, grass rustle, a few field birds
  amb_village   hamlet by day: breeze, chickens, sparrows, spotted doves, bamboo wind
                chimes, far-off carpentry
  amb_night     tropical night: crickets, tree crickets, distant insect wall, cicak
  amb_frogs     frog chorus (kodok ngorek, kodok kerok, tree frogs)  (near water at night)
One-shots for the 3D emitters:
  amb_bird_{kutilang,kacer,takur,tekukur,perkutut,koel,cinenen,cucak}, amb_frog_a/b,
  amb_tokek, amb_owl, amb_splash_a/b, amb_rooster, amb_chicken, amb_tonggeret

Written as mono Ogg Vorbis 22.05 kHz into game/assets/audio/ (needs ffmpeg with
libvorbis; numpy, scipy, soundfile, pyloudnorm; matplotlib for --png).

  python3 tools/make_ambience.py                 # everything
  python3 tools/make_ambience.py sea river       # only these (names without amb_)
  python3 tools/make_ambience.py --png /tmp/png  # also waveform + spectrogram overviews
  python3 tools/make_ambience.py --wav /tmp/wav  # also keep the 16-bit WAV masters
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal
from scipy.interpolate import PchipInterpolator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "audio")
SR = 22050
NFFT = 1024          # 46 ms frames for the noise synthesis
HOP = NFFT // 4      # 11.6 ms (Hann at 75 % overlap: constant power)
FREQS = np.fft.rfftfreq(NFFT, 1.0 / SR)
BED_LUFS = -24.0     # file loudness of the beds (ambience.gd sets the mix levels)
VORBIS_Q = 1         # ffmpeg libvorbis -q:a (mono 22 kHz: ~30 kbps; band levels within 1 dB)
SHOT_Q = 1


# ====================================================================== basics
def n_of(sec):
    return int(round(sec * SR))


def loop_len(sec):
    """samples for a loop of ~sec seconds, a whole number of noise frames"""
    return int(round(sec * SR / HOP)) * HOP


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def db(x):
    return 10 ** (x / 20.0)


def lowpass_shape(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (f / np.maximum(fc, 1.0)) ** (2 * order))


def highpass_shape(f, fc, order=2):
    r = (f / np.maximum(fc, 1.0)) ** (2 * order)
    return np.sqrt(r / (1.0 + r))


def band_shape(f, lo, hi, order=2):
    return highpass_shape(f, lo, order) * lowpass_shape(f, hi, order)


def peak_shape(f, fc, q):
    """resonance bump (magnitude of a 2-pole bandpass, 1.0 at fc)"""
    x = f / fc - fc / np.maximum(f, 1.0)
    return 1.0 / np.sqrt(1.0 + (q * x) ** 2)


def pink(f, f0=100.0):
    return 1.0 / np.sqrt(np.maximum(f, 20.0) / f0)


def periodic_lfo(n, rng, cycles=(1, 8), slope=1.0):
    """zero-mean, unit-peak random curve of n points that wraps around seamlessly
    (sum of the loop's own harmonics cycles[0]..cycles[1], 1/k^slope amplitudes)"""
    spec = np.zeros(n // 2 + 1, complex)
    k = np.arange(cycles[0], cycles[1] + 1)
    spec[k] = (rng.normal(size=k.size) + 1j * rng.normal(size=k.size)) / k ** slope
    y = np.fft.irfft(spec, n)
    return y / (np.max(np.abs(y)) + 1e-12)


def smooth_noise(n, rng, width):
    """random curve (n points) smoothed over `width` points, unit std"""
    y = rng.normal(size=n + 4 * width)
    k = np.hanning(2 * width + 1)
    y = np.convolve(y, k / k.sum(), "same")[2 * width:2 * width + n]
    return y / (y.std() + 1e-12)


def ola_noise(mag, rng):
    """Noise with a time-varying spectrum: `mag` (frames, bins) magnitude per 11.6 ms frame.
    Frames are random-phase spectra overlap-added circularly -> a seamless loop of
    frames * HOP samples."""
    K = mag.shape[0]
    ph = np.exp(2j * np.pi * rng.random(mag.shape))
    win = np.hanning(NFFT + 1)[:NFFT]
    out = np.zeros((K, HOP))
    for a in range(0, K, 512):                      # chunks keep the memory small
        fr = np.fft.irfft(mag[a:a + 512] * ph[a:a + 512], NFFT, axis=1) * win
        fr = fr.reshape(fr.shape[0], 4, HOP)
        for j in range(4):
            idx = (np.arange(a, a + fr.shape[0]) + j - 2) % K
            np.add.at(out, idx, fr[:, j, :])
    return out.reshape(-1) * np.sqrt(NFFT / 1.5)


def frames_t(K):
    return np.arange(K) * HOP / SR


def place(buf, sig, at, wrap=True):
    """adds sig into buf at `at` seconds (wrapping round the end of a loop)"""
    i = int(round(at * SR))
    n = len(sig)
    if wrap:
        i %= len(buf)
        k = min(n, len(buf) - i)
        buf[i:i + k] += sig[:k]
        if k < n:
            place(buf, sig[k:], 0.0, wrap)
    else:
        if i >= len(buf):
            return
        k = min(n, len(buf) - i)
        buf[i:i + k] += sig[:k]


def circ_filter(b, a, x):
    """IIR filter applied to a loop in its steady state (seamless)"""
    y = signal.lfilter(b, a, np.concatenate([x, x]))
    return y[len(x):]


def circ_conv(x, h):
    n = len(x)
    L = 1 << int(np.ceil(np.log2(n + len(h))))
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(h, L), L)
    out = y[:n].copy()
    tail = y[n:n + len(h)]
    place(out, tail, 0.0)
    return out


def lin_conv(x, h):
    return signal.fftconvolve(x, h)[:len(x) + len(h) - 1]


def spectral_filter(x, shape_fn, circular=True):
    """zero-phase FFT filter of a whole signal; shape_fn(freqs) -> gain"""
    n = len(x)
    if circular:
        X = np.fft.rfft(x)
        return np.fft.irfft(X * shape_fn(np.fft.rfftfreq(n, 1.0 / SR)), n)
    L = 1 << int(np.ceil(np.log2(n + SR // 4)))
    X = np.fft.rfft(x, L)
    return np.fft.irfft(X * shape_fn(np.fft.rfftfreq(L, 1.0 / SR)), L)[:n]


def fade(x, a=0.005, r=0.02):
    x = x.copy()
    na, nr = min(len(x), n_of(a)), min(len(x), n_of(r))
    if na:
        x[:na] *= np.sin(np.linspace(0, np.pi / 2, na)) ** 2
    if nr:
        x[-nr:] *= np.cos(np.linspace(0, np.pi / 2, nr)) ** 2
    return x


# ====================================================================== space
_IR_CACHE = {}


def reverb_ir(rt60=1.2, hf_rt=0.45, predelay=0.012, early=6, seed=1):
    """synthetic outdoor reverb: sparse early reflections + a diffuse tail whose highs
    die faster (hf_rt = rt60 at 5 kHz relative to 250 Hz)"""
    key = (rt60, hf_rt, predelay, early, seed)
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    rng = np.random.default_rng(seed)
    dur = rt60 * 1.1 + predelay
    K = int(np.ceil(dur * SR / HOP)) + 8
    t = frames_t(K)[:, None]
    rt_f = rt60 * (hf_rt + (1 - hf_rt) / (1 + (FREQS[None, :] / 1500.0) ** 1.3))
    mag = np.exp(-6.91 * t / rt_f) * lowpass_shape(FREQS, 7000)[None, :] * highpass_shape(FREQS, 90)[None, :]
    mag *= smoothstep(0.0, 0.05, t)                       # the tail builds up
    tail = ola_noise(mag, rng)
    ir = np.zeros(len(tail) + n_of(predelay))
    ir[n_of(predelay):] = tail / np.sqrt(np.sum(tail ** 2)) * np.sqrt(0.88)
    # a few soft ground / trunk reflections carrying the rest of the energy
    amps = rng.uniform(0.4, 1.0, early) * rng.choice([-1, 1], early)
    amps *= np.sqrt(0.12 / np.sum(amps ** 2))
    for a in amps:
        ir[n_of(predelay + rng.uniform(0.005, 0.035))] += a
    ir = ir[:n_of(dur)]
    _IR_CACHE[key] = ir
    return ir


def at_distance(x, dist, wet=None, rt60=1.2, circular=False, seed=1):
    """a dry source heard from `dist` metres: level, air absorption and reverb"""
    g = 1.0 / max(1.0, dist / 4.0)
    fc = 9000.0 / (1.0 + dist / 25.0)                  # air + foliage absorption
    y = spectral_filter(x, lambda f: lowpass_shape(f, fc, 1), circular)
    w = wet if wet is not None else float(np.clip(0.18 + dist / 90.0, 0.18, 0.75))
    ir = reverb_ir(rt60, seed=seed)
    if circular:
        r = circ_conv(y, ir)
    else:
        y = np.concatenate([y, np.zeros(len(ir))])
        r = lin_conv(y, ir)[:len(y)]
    return g * ((1 - w) * y + w * 0.55 * r)


# ====================================================================== sources
def osc(f, harm=((1, 1.0),), phase0=0.0):
    """additive oscillator following the frequency curve f (Hz per sample)"""
    ph = 2 * np.pi * np.cumsum(f) / SR + phase0
    y = np.zeros_like(f)
    for k, a in harm:
        ok = (k * f) < SR * 0.45
        y += a * np.sin(k * ph) * ok
    return y


def curve(pts, n, smooth=True):
    """curve through (t 0..1, value) points, n samples: monotone cubic (PCHIP) in the log
    domain when smooth (bird glides bend like real ones), else piecewise linear"""
    pts = np.asarray(pts, float)
    t = np.linspace(0, 1, n)
    if smooth and len(pts) >= 2 and np.all(pts[:, 1] > 0):
        if len(pts) == 2:
            e = t * t * (3 - 2 * t) * 0.35 + t * 0.65                   # a gentle ease
            return np.exp(np.log(pts[0, 1]) + (np.log(pts[1, 1]) - np.log(pts[0, 1])) * e)
        return np.exp(PchipInterpolator(pts[:, 0], np.log(pts[:, 1]))(t))
    return np.interp(t, pts[:, 0], pts[:, 1])


def note(dur, fpts, apts=((0, 0), (0.08, 1), (0.7, 0.8), (1, 0)), harm=((1, 1.0), (2, 0.06), (3, 0.02)),
         jitter=0.004, vib=(0.0, 0.0), breath=0.0, rng=None, smooth=True):
    """one bird-like note: frequency points fpts [(t, Hz)], amplitude points apts"""
    rng = rng or np.random.default_rng()
    n = max(16, n_of(dur))
    f = curve(fpts, n, smooth)
    if jitter:
        f *= 1 + jitter * smooth_noise(n, rng, max(2, n_of(0.004)))
    if vib[0] > 0:
        f *= 1 + vib[1] * np.sin(2 * np.pi * vib[0] * np.arange(n) / SR + rng.uniform(0, 6.28))
    a = curve(apts, n, smooth=False)
    k = min(n // 3, n_of(0.004))
    if k > 1:                                               # click-free edges
        a[:k] *= np.linspace(0, 1, k)
        a[-k:] *= np.linspace(1, 0, k)
    a *= 1 + 0.08 * smooth_noise(n, rng, max(2, n_of(0.006)))    # a living, not a synth, tone
    y = osc(f, harm, rng.uniform(0, 6.28)) * a
    if breath > 0:                                          # a little air in the tone
        nz = rng.normal(size=n)
        nz = spectral_filter(nz, lambda fr: peak_shape(fr, float(np.median(f)), 3.0), circular=False)
        y += breath * nz / (np.abs(nz).max() + 1e-9) * a
    return y


def seq(parts, gap_default=0.0):
    """concatenates [(signal, gap_after_sec), ...]"""
    out = []
    for p in parts:
        sig, gap = (p if isinstance(p, tuple) else (p, gap_default))
        out.append(sig)
        if gap > 0:
            out.append(np.zeros(n_of(gap)))
    return np.concatenate(out)


def resonator(x, fc, bw):
    """2-pole resonant bandpass (unit peak gain)"""
    r = np.exp(-np.pi * bw / SR)
    th = 2 * np.pi * fc / SR
    b = [(1 - r * r) / 2, 0, -(1 - r * r) / 2]
    a = [1, -2 * r * np.cos(th), r * r]
    return signal.lfilter(b, a, x)


def formant_voice(f0, formants, n, rng, jitter=0.01, shimmer=0.08, rough=0.0, open_q=0.5):
    """pulse-train voice (glottal-like pulses) through parallel formant resonators.
    f0: array (n) Hz; formants: [(Hz, bandwidth, gain)] or array-valued Hz"""
    f = f0 * (1 + jitter * smooth_noise(n, rng, 3))
    ph = np.cumsum(f) / SR
    frac = ph % 1.0
    # Rosenberg-like glottal flow derivative, band-limited enough at these f0s
    src = np.where(frac < open_q, np.sin(np.pi * frac / open_q), 0.0) ** 2
    src = np.diff(src, prepend=0.0)
    src *= 1 + shimmer * smooth_noise(n, rng, 20)
    if rough > 0:                                           # period-doubling harshness
        src *= 1 + rough * np.sign(np.sin(np.pi * ph))
    src += 0.02 * rng.normal(size=n) * np.abs(src).max()
    y = np.zeros(n)
    for fc, bw, g in formants:
        if np.ndim(fc):
            # time-varying formant: process in blocks
            blk = 256
            zi = np.zeros(2)
            out = np.zeros(n)
            for i in range(0, n, blk):
                c = float(np.mean(fc[i:i + blk]))
                r = np.exp(-np.pi * bw / SR)
                th = 2 * np.pi * c / SR
                b = [(1 - r * r) / 2, 0, -(1 - r * r) / 2]
                a = [1, -2 * r * np.cos(th), r * r]
                out[i:i + blk], zi = signal.lfilter(b, a, src[i:i + blk], zi=zi)
            y += g * out
        else:
            y += g * resonator(src, fc, bw)
    return y


# ====================================================================== output
def lufs(x):
    meter = pyln.Meter(SR, block_size=0.4)
    if len(x) < SR * 0.5:
        x = np.concatenate([x, np.zeros(SR)])
    return meter.integrated_loudness(x)


def write_ogg(name, y, q):
    path = os.path.join(OUT, name + ".ogg")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp = tf.name
    try:
        sf.write(tmp, y.astype(np.float32), SR, subtype="PCM_16")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-map_metadata", "-1",
                        "-c:a", "libvorbis", "-q:a", str(q), "-ac", "1", "-ar", str(SR), path], check=True)
    finally:
        os.remove(tmp)
    return path


REPORT = []


def finish_bed(name, y, target=BED_LUFS, args=None):
    y = y - np.mean(y)
    y = circ_filter(*signal.butter(2, 28.0 / (SR / 2), "high"), y)   # no DC / sub rumble
    L = lufs(y)
    y = y * db(target - L)
    pk = np.max(np.abs(y))
    if pk > db(-3.0):                                     # soft-limit rare peaks
        y = np.tanh(y / db(-3.0)) * db(-3.0)
    path = write_ogg("amb_" + name, y, VORBIS_Q)
    _report("amb_" + name, y, path, loop=True, args=args)


def finish_shot(name, y, peak_db=-3.0, args=None):
    y = y - np.mean(y)
    y = spectral_filter(y, lambda f: highpass_shape(f, 40.0), circular=False)
    # trim silence at the end, fade
    thr = np.max(np.abs(y)) * db(-60)
    last = np.nonzero(np.abs(y) > thr)[0]
    y = y[:last[-1] + 1] if len(last) else y
    y = fade(y, 0.002, min(0.08, len(y) / SR / 4))
    y = y / (np.max(np.abs(y)) + 1e-12) * db(peak_db)
    path = write_ogg("amb_" + name, y, SHOT_Q)
    _report("amb_" + name, y, path, loop=False, args=args)


def _report(name, y, path, loop, args):
    L = lufs(y)
    pk = 20 * np.log10(np.max(np.abs(y)) + 1e-12)
    size = os.path.getsize(path)
    seam = ""
    if loop:
        # loop seam: short-time level and spectrum across the wrap vs. anywhere else
        w = n_of(0.05)
        def band_db(seg):
            s = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            return 20 * np.log10(np.array([s[a:b].mean() + 1e-9 for a, b in ((1, 8), (8, 40), (40, 200), (200, w // 2))]))
        diffs = []
        for i in range(w, len(y) - w, w):
            diffs.append(np.abs(band_db(y[i - w:i]) - band_db(y[i:i + w])).mean())
        wrap = np.abs(band_db(y[-w:]) - band_db(y[:w])).mean()
        jump = abs(float(y[-1]) - float(y[0]))
        seam = f"  seam {wrap:.1f} dB (median frame step {np.median(diffs):.1f}, p95 {np.percentile(diffs, 95):.1f})  jump {jump:.4f}"
    # harshness: frames with a narrow whistle in 2.5-6.5 kHz standing 25 dB over its band,
    # and clicks (crest factor of everything above 4 kHz)
    f, _, S = signal.spectrogram(y, SR, nperseg=1024, noverlap=512)
    band = (f > 2500) & (f < 6500)
    Sb = S[band] + 1e-20
    loud = Sb.sum(0) > 0.03 * S.sum(0)
    ratio = 10 * np.log10(Sb.max(0) / np.median(Sb, 0))
    whine = float(np.mean((ratio > 25) & loud)) * 100
    pk_bin = np.argmax(Sb, 0)
    on = (ratio > 25) & loud
    run = best = 0
    for i in range(1, len(on)):                    # longest steady tone (same bin +-2)
        run = run + 1 if (on[i] and on[i - 1] and abs(int(pk_bin[i]) - int(pk_bin[i - 1])) <= 2) else 0
        best = max(best, run)
    sustained = best * 512 / SR
    hi = spectral_filter(y, lambda fr: highpass_shape(fr, 4000, 4), circular=loop)
    crest = 20 * np.log10(np.max(np.abs(hi)) / (np.sqrt(np.mean(hi ** 2)) + 1e-12))
    msg = (f"{name:22s} {len(y) / SR:6.2f}s  {L:6.1f} LUFS  peak {pk:5.1f} dBFS  {size / 1024:6.1f} KB  "
           f"tonal {whine:4.1f}% (longest {sustained:3.1f}s)  hf-crest {crest:4.1f} dB{seam}")
    print(msg, flush=True)
    REPORT.append((name, len(y) / SR, L, pk, size))
    if args is not None:
        if args.wav:
            os.makedirs(args.wav, exist_ok=True)
            sf.write(os.path.join(args.wav, name + ".wav"), y.astype(np.float32), SR, subtype="PCM_16")
        if args.png:
            os.makedirs(args.png, exist_ok=True)
            _png(y, name, os.path.join(args.png, name + ".png"), loop)


def _png(y, name, path, loop):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.concatenate([y, y[:n_of(min(8.0, len(y) / SR))]]) if loop else y
    t = np.arange(len(x)) / SR
    fig, ax = plt.subplots(2, 1, figsize=(15, 5.5), gridspec_kw={"height_ratios": [1, 2.6]})
    ax[0].plot(t, x, lw=0.3)
    ax[0].set_xlim(0, t[-1])
    ax[0].set_ylim(-1, 1)
    ax[0].set_title(name + ("  (loop + first 8 s again; seam at the red line)" if loop else ""))
    f, tt, S = signal.spectrogram(x, SR, nperseg=1024, noverlap=768)
    ax[1].pcolormesh(tt, f, 10 * np.log10(S + 1e-14), vmin=-120, vmax=-40, shading="auto", cmap="magma")
    ax[1].set_ylabel("Hz")
    if loop:
        for a in ax:
            a.axvline(len(y) / SR, color="r", lw=0.8)
    plt.tight_layout()
    plt.savefig(path, dpi=64)
    plt.close(fig)


# ====================================================================== birds
def kutilang(rng):
    """sooty-headed bulbul: bright liquid 'cuk-cuk-li-li-dyu' phrase"""
    base = rng.uniform(1700, 2100)
    parts = []
    for i in range(rng.integers(4, 7)):
        kind = rng.integers(0, 3)
        if kind == 0:     # up-down chevron
            d = rng.uniform(0.07, 0.12)
            fp = [(0, base * 0.85), (0.45, base * rng.uniform(1.25, 1.5)), (1, base * 0.9)]
        elif kind == 1:   # quick down-slur
            d = rng.uniform(0.05, 0.09)
            fp = [(0, base * 1.45), (1, base * 0.95)]
        else:             # short liquid 'cuk'
            d = rng.uniform(0.035, 0.05)
            fp = [(0, base * 1.1), (0.5, base * 1.25), (1, base * 1.05)]
        parts.append((note(d, fp, harm=((1, 1.0), (2, 0.12), (3, 0.03)), jitter=0.006, rng=rng),
                      rng.uniform(0.025, 0.07)))
        base *= rng.uniform(0.93, 1.08)
    return seq(parts)


def kacer(rng):
    """oriental magpie-robin: long melodious whistles with slow glides and trills"""
    parts = []
    f = rng.uniform(1800, 2400)
    for i in range(rng.integers(4, 7)):
        kind = rng.integers(0, 4)
        if kind == 0:     # long sweet whistle, slow glide
            d = rng.uniform(0.25, 0.45)
            f2 = f * rng.uniform(0.8, 1.3)
            y = note(d, [(0, f), (0.6, f2), (1, f2 * 0.97)], apts=((0, 0), (0.15, 1), (0.8, 0.85), (1, 0)),
                     vib=(rng.uniform(18, 30), 0.012), jitter=0.003, breath=0.02, rng=rng)
        elif kind == 1:   # rapid trill of 5-8 tiny notes
            m = rng.integers(5, 9)
            y = seq([(note(0.028, [(0, f * 1.2), (1, f * 0.95)], jitter=0.004, rng=rng), 0.018) for _ in range(m)])
        elif kind == 2:   # rising 'swee-it'
            d = rng.uniform(0.12, 0.2)
            y = note(d, [(0, f * 0.7), (0.7, f * 1.35), (1, f * 1.4)], rng=rng)
        else:             # two-part 'tee-oo'
            y = seq([(note(0.1, [(0, f * 1.3), (1, f * 1.25)], rng=rng), 0.02),
                     note(0.16, [(0, f * 0.95), (1, f * 0.8)], rng=rng)])
        parts.append((y, rng.uniform(0.06, 0.2)))
        f = np.clip(f * rng.uniform(0.85, 1.18), 1500, 3200)
    return seq(parts)


def takur(rng):
    """coppersmith barbet: hollow 'tuk ... tuk ... tuk' at a steady tempo"""
    f = rng.uniform(640, 760)
    n = rng.integers(7, 13)
    period = rng.uniform(0.34, 0.46)
    parts = []
    for i in range(n):
        a = 0.6 + 0.4 * np.sin(np.pi * min(1.0, (i + 1) / 3.0))
        y = note(0.07, [(0, f * 1.04), (0.3, f), (1, f * 0.97)], apts=((0, 0), (0.12, 1), (0.5, 0.7), (1, 0)),
                 harm=((1, 1.0), (2, 0.25), (3, 0.08)), jitter=0.002, breath=0.05, rng=rng) * a
        parts.append((y, period - 0.07 + rng.normal(0, 0.006)))
    return seq(parts)


def tekukur(rng):
    """spotted dove: soft hollow 'ter-kuk ... kurrr' coo"""
    f = rng.uniform(480, 560)
    harm = ((1, 1.0), (2, 0.18), (3, 0.05))
    ku = note(0.13, [(0, f * 0.95), (0.3, f * 1.08), (1, f)], apts=((0, 0), (0.2, 1), (0.7, 0.8), (1, 0)),
              harm=harm, breath=0.04, rng=rng)
    kur_n = n_of(0.5)
    kurr = note(0.5, [(0, f * 1.12), (0.4, f * 1.05), (1, f * 0.9)], apts=((0, 0), (0.1, 1), (0.75, 0.8), (1, 0)),
                harm=harm, breath=0.05, rng=rng)
    kurr *= 0.65 + 0.35 * np.sin(2 * np.pi * 26 * np.arange(kur_n) / SR)   # the rolling 'rrr'
    kuk = note(0.11, [(0, f * 0.98), (1, f * 0.92)], harm=harm, breath=0.04, rng=rng)
    return seq([(ku, 0.05), (note(0.1, [(0, f * 1.02), (1, f * 1.0)], harm=harm, rng=rng), 0.12), (kurr, 0.18), kuk])


def perkutut(rng):
    """zebra dove (perkutut): gentle staccato cooing 'ku-ku-krrr-kuk-kuk-kuk'"""
    f = rng.uniform(820, 980)
    harm = ((1, 1.0), (2, 0.15), (3, 0.04))
    parts = [(note(0.09, [(0, f * 0.9), (1, f)], harm=harm, breath=0.04, rng=rng), 0.07),
             (note(0.09, [(0, f), (1, f * 1.05)], harm=harm, breath=0.04, rng=rng), 0.08)]
    rr = note(0.28, [(0, f * 1.1), (1, f * 1.02)], harm=harm, breath=0.05, rng=rng)
    rr *= 0.55 + 0.45 * np.sin(2 * np.pi * 34 * np.arange(len(rr)) / SR)
    parts.append((rr, 0.1))
    for i in range(rng.integers(3, 6)):
        parts.append((note(0.075, [(0, f * 1.05), (1, f * 0.96)], harm=harm, breath=0.04, rng=rng) * (1 - 0.1 * i),
                      rng.uniform(0.09, 0.13)))
    return seq(parts)


def koel(rng):
    """Asian koel (tuwur): rising 'ku-OO' repeated, each one a bit higher"""
    f = rng.uniform(640, 720)
    parts = []
    for i in range(rng.integers(3, 6)):
        k = 1 + 0.045 * i
        y = seq([(note(0.1, [(0, f * k), (1, f * k * 1.02)], harm=((1, 1.0), (2, 0.1)), breath=0.03, rng=rng), 0.015),
                 note(0.28, [(0, f * k * 1.05), (0.7, f * k * 1.42), (1, f * k * 1.45)],
                      apts=((0, 0), (0.15, 0.8), (0.75, 1), (1, 0)), harm=((1, 1.0), (2, 0.08)), breath=0.03, rng=rng)])
        parts.append((y * (0.7 + 0.08 * i), rng.uniform(0.35, 0.5)))
    return seq(parts)


def cinenen(rng):
    """common tailorbird: emphatic repeated 'twee-twee-twee'"""
    f = rng.uniform(2300, 2700)
    parts = []
    for i in range(rng.integers(4, 8)):
        y = note(0.07, [(0, f * 0.8), (0.55, f * 1.18), (1, f * 1.1)], apts=((0, 0), (0.3, 1), (0.8, 0.8), (1, 0)),
                 harm=((1, 1.0), (2, 0.05)), jitter=0.004, rng=rng)
        parts.append((y, rng.uniform(0.16, 0.2)))
    return seq(parts)


def cucak(rng):
    """straw-headed bulbul (cucak rawa): rich, bubbling, liquid warble"""
    parts = []
    f = rng.uniform(1300, 1700)
    for i in range(rng.integers(8, 13)):
        d = rng.uniform(0.05, 0.14)
        f2 = np.clip(f * rng.uniform(0.7, 1.45), 900, 3000)
        mid = (f + f2) / 2 * rng.uniform(0.9, 1.2)
        y = note(d, [(0, f), (0.5, mid), (1, f2)], harm=((1, 1.0), (2, 0.2), (3, 0.06)), jitter=0.005,
                 breath=0.02, rng=rng)
        parts.append((y * rng.uniform(0.6, 1.0), rng.uniform(0.0, 0.05)))
        f = f2
    return seq(parts)


def sparrow_burst(rng):
    """burung gereja: a cluster of short 'cip' chirps"""
    parts = []
    for i in range(rng.integers(3, 9)):
        f = rng.uniform(2900, 3700)
        y = note(rng.uniform(0.03, 0.05), [(0, f * 1.1), (0.4, f), (1, f * 0.85)], harm=((1, 1.0), (2, 0.05)),
                 jitter=0.01, breath=0.06, rng=rng)
        parts.append((y * rng.uniform(0.4, 1.0), rng.uniform(0.04, 0.2)))
    return seq(parts)


def cici(rng):
    """zitting cisticola (cici padi): high 'tsip' notes at a steady pace"""
    parts = []
    f = rng.uniform(3600, 4200)
    for i in range(rng.integers(4, 8)):
        parts.append((note(0.025, [(0, f * 1.1), (1, f * 0.9)], harm=((1, 1.0),), rng=rng), rng.uniform(0.35, 0.45)))
    return seq(parts)


def munia(rng):
    """scaly-breasted munia (pipit): soft 'pee-pee'"""
    parts = []
    for i in range(rng.integers(1, 4)):
        f = rng.uniform(2800, 3300)
        parts.append((note(0.09, [(0, f), (0.5, f * 1.04), (1, f * 0.93)], harm=((1, 1.0), (2, 0.1)), breath=0.06,
                           rng=rng), rng.uniform(0.2, 0.5)))
    return seq(parts)


BIRDS = {"kutilang": kutilang, "kacer": kacer, "takur": takur, "tekukur": tekukur, "perkutut": perkutut,
         "koel": koel, "cinenen": cinenen, "cucak": cucak}


# ====================================================================== insects, frogs, geckos
def cricket_chirp(rng, f, pulses=3, pulse=0.016, gap=0.018):
    parts = []
    for i in range(pulses):
        n = n_of(pulse)
        y = np.sin(2 * np.pi * f * (1 + 0.01 * np.linspace(1, -1, n)) * np.arange(n) / SR)
        y *= np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
        parts.append((y * (0.85 + 0.15 * (i == 0)), gap))
    return seq(parts)


def tree_cricket(rng, n, f, rate, depth=0.8):
    """continuous soft trill (tree cricket): carrier f, pulse rate `rate`"""
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t + 0.002 * f * smooth_noise(n, rng, 400))
    am = (1 - depth) + depth * np.clip(np.sin(2 * np.pi * rate * t), 0, 1) ** 2
    return y * am


def cicada_swell(rng, dur, fc=3100.0):
    """tonggeret: a pulsing buzz that swells up and fades, pitch rising a little"""
    n = n_of(dur)
    t = np.arange(n) / SR
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    rise = 1 + 0.08 * smoothstep(0, dur * 0.6, t)
    # noise through a resonance that glides up with the swell (no steady sine: no whine)
    K = int(np.ceil(n / HOP)) + 4
    tk = np.minimum(frames_t(K), dur)
    fck = fc * (1 + 0.08 * smoothstep(0, dur * 0.6, tk))
    mag = peak_shape(FREQS[None, :], fck[:, None], 6.0) * lowpass_shape(FREQS[None, :], 4600, 3)
    carrier = ola_noise(mag, rng)[:n]
    carrier /= np.abs(carrier).max() + 1e-9
    pr = 118 * rise                                           # tymbal pulse rate
    am = 0.3 + 0.7 * np.clip(np.sin(2 * np.pi * np.cumsum(pr) / SR), 0, 1) ** 3
    return carrier * am * env


def frog_croak(rng, kind="ngorek"):
    """one croak: a pulsed tone (the pulse rate gives the 'rrr', the carrier the vocal-sac
    resonance), smooth pulses so it stays soft instead of clicky"""
    if kind == "kerok":         # banded bullfrog: a low, hollow 'ooom-wah'
        dur = rng.uniform(0.45, 0.6)
        n = n_of(dur)
        tt = np.linspace(0, 1, n)
        f0 = rng.uniform(210, 250) * np.interp(tt, [0, 0.45, 0.55, 1], [0.95, 1.0, 1.12, 1.05])
        y = osc(f0, ((1, 1.0), (2, 0.55), (3, 0.3), (4, 0.12), (5, 0.05)))
        y *= 0.75 + 0.25 * np.sin(2 * np.pi * np.cumsum(np.full(n, 38.0)) / SR)
        env = np.interp(tt, [0, 0.08, 0.42, 0.5, 0.6, 0.9, 1], [0, 0.75, 0.85, 0.3, 1.0, 0.7, 0])
        return spectral_filter(y * env, lambda f: lowpass_shape(f, 900, 2), circular=False)
    if kind == "ngorek":        # rice-field frog: a buzzy 'krok'
        dur, rate, fc = rng.uniform(0.12, 0.2), rng.uniform(55, 75), rng.uniform(950, 1250)
        sharp, h2 = 2.0, 0.3
    else:                       # tree frog: a short knocking 'kek'
        dur, rate, fc = rng.uniform(0.05, 0.08), rng.uniform(90, 120), rng.uniform(1300, 1600)
        sharp, h2 = 3.0, 0.2
    n = n_of(dur)
    tt = np.linspace(0, 1, n)
    f = fc * (1.03 - 0.06 * tt)
    car = osc(f, ((1, 1.0), (2, h2)))
    am = np.clip(np.sin(np.pi * np.cumsum(np.full(n, rate)) / SR), 0, 1) ** sharp
    env = np.interp(tt, [0, 0.15, 0.6, 1], [0, 1, 0.85, 0])
    return spectral_filter(car * am * env, lambda fr: lowpass_shape(fr, 2600, 2), circular=False)


def frog_bout(rng, kind):
    parts = []
    m = {"ngorek": (3, 7), "kerok": (1, 3), "tree": (3, 6)}[kind]
    gap = {"ngorek": (0.22, 0.35), "kerok": (1.0, 1.5), "tree": (0.12, 0.2)}[kind]
    for i in range(rng.integers(*m)):
        parts.append((frog_croak(rng, kind) * rng.uniform(0.75, 1.0), rng.uniform(*gap)))
    return seq(parts)


def cicak(rng):
    """house gecko: rapid 'cak-cak-cak'"""
    parts = []
    for i in range(rng.integers(5, 9)):
        n = n_of(0.03)
        y = note(0.03, [(0, 2600), (1, 2300)], apts=((0, 0), (0.1, 1), (1, 0)), harm=((1, 1.0), (2, 0.2), (3, 0.06)),
                 jitter=0.02, rng=rng)
        parts.append((y * (1 - 0.06 * i), 0.07))
    return seq(parts)


def tokek(rng):
    """tokay gecko: a gravelly wind-up 'krrrr', then 'to-KEK' calls that tire out"""
    parts = []
    n = n_of(0.9)
    f0 = np.full(n, 95.0) * (1 + 0.1 * np.linspace(0, 1, n))
    wind = formant_voice(f0, [(500, 160, 1.0), (1100, 250, 0.4)], n, rng, jitter=0.05, shimmer=0.4, rough=0.6)
    wind *= np.interp(np.linspace(0, 1, n), [0, 0.2, 0.8, 1], [0, 0.35, 0.5, 0])
    parts.append((wind, 0.35))
    calls = rng.integers(5, 9)
    for i in range(calls):
        tired = i / max(1, calls - 1)
        n1 = n_of(0.13)
        to = formant_voice(np.full(n1, 210.0 * (1 - 0.05 * tired)), [(480, 120, 1.0), (850, 160, 0.6), (2400, 300, 0.15)],
                           n1, rng, jitter=0.02, shimmer=0.15, rough=0.25)
        to *= np.interp(np.linspace(0, 1, n1), [0, 0.1, 0.6, 1], [0, 1, 0.7, 0])
        n2 = n_of(0.24)
        f0 = 250.0 * (1 - 0.06 * tired) * np.interp(np.linspace(0, 1, n2), [0, 0.3, 1], [1.0, 1.08, 0.9])
        kek = formant_voice(f0, [(650, 140, 1.0), (1750, 220, 0.8), (2700, 320, 0.25)], n2, rng, jitter=0.02,
                            shimmer=0.15, rough=0.3)
        kek *= np.interp(np.linspace(0, 1, n2), [0, 0.06, 0.4, 1], [0, 1, 0.75, 0])
        call = seq([(to * 0.7, 0.05), kek])
        parts.append((call * (1.0 - 0.45 * tired), rng.uniform(0.75, 1.0) + 0.25 * tired))
    return seq(parts)


def owl(rng):
    """soft owl hoots 'hoo ... hoo-hoo'"""
    f = rng.uniform(360, 420)
    harm = ((1, 1.0), (2, 0.08), (3, 0.02))
    h1 = note(0.42, [(0, f * 0.96), (0.3, f * 1.03), (1, f * 0.94)], apts=((0, 0), (0.25, 1), (0.7, 0.8), (1, 0)),
              harm=harm, breath=0.12, rng=rng)
    h2 = note(0.18, [(0, f), (1, f * 0.97)], apts=((0, 0), (0.3, 1), (1, 0)), harm=harm, breath=0.12, rng=rng)
    h3 = note(0.36, [(0, f * 1.01), (1, f * 0.93)], apts=((0, 0), (0.25, 1), (1, 0)), harm=harm, breath=0.12, rng=rng)
    return seq([(h1, 0.75), (h2 * 0.8, 0.12), h3 * 0.9])


# ====================================================================== farm & village
def rooster(rng):
    """ayam jago: 'ku-ku-ru-yuuuk' - a rough, brassy voice (pulse source with heavy
    jitter, a breathy noise part and moving formants), sung from a distance"""
    #        dur   f0 from/to   gap   amp  F1   F2
    sylls = [(0.10, 480, 520, 0.075, 0.75, 650, 1300),
             (0.11, 560, 600, 0.07, 0.85, 700, 1400),
             (0.17, 620, 760, 0.035, 0.95, 800, 1600),
             (0.9, 800, 690, 0.0, 1.0, 950, 1850)]
    parts = []
    for i, (d, fa, fb, gap, amp, F1, F2) in enumerate(sylls):
        n = n_of(d)
        tt = np.linspace(0, 1, n)
        if i == 3:
            f0 = np.interp(tt, [0, 0.1, 0.55, 0.8, 1], [fa * 0.93, fa * 1.04, fa, fb * 1.02, fb * 0.8])
            env = np.interp(tt, [0, 0.05, 0.6, 0.85, 1], [0, 1, 0.9, 0.55, 0])
            f1 = np.interp(tt, [0, 0.15, 0.8, 1], [800, F1, F1 * 0.95, 700])
        else:
            f0 = np.interp(tt, [0, 1], [fa, fb])
            env = np.interp(tt, [0, 0.15, 0.7, 1], [0, 1, 0.85, 0])
            f1 = np.full(n, float(F1))
        v = formant_voice(f0, [(f1, 200, 1.0), (F2, 300, 0.75), (3000, 450, 0.3)], n, rng, jitter=0.03,
                          shimmer=0.25, rough=0.35 if i == 3 else 0.15, open_q=0.35)
        v /= np.abs(v).max() + 1e-9
        nz = rng.normal(size=n)                                   # the breathy rasp
        nz = resonator(nz, F1, 400) + 0.6 * resonator(nz, F2, 500)
        v += 0.25 * nz / (np.abs(nz).max() + 1e-9)
        parts.append((v * env * amp, gap))
    return seq(parts)


def chicken(rng):
    """hens clucking: 'bok ... bok bok ... b'gaawk'"""
    parts = []
    for i in range(rng.integers(2, 5)):
        n = n_of(rng.uniform(0.06, 0.09))
        f0 = np.full(n, rng.uniform(300, 360))
        v = formant_voice(f0, [(620, 150, 1.0), (1400, 240, 0.5), (2600, 350, 0.15)], n, rng, jitter=0.03,
                          shimmer=0.2, rough=0.2)
        v *= np.interp(np.linspace(0, 1, n), [0, 0.1, 0.5, 1], [0, 1, 0.6, 0])
        parts.append((v * rng.uniform(0.5, 0.9), rng.uniform(0.12, 0.35)))
    if rng.random() < 0.6:
        n = n_of(0.32)
        tt = np.linspace(0, 1, n)
        f0 = np.interp(tt, [0, 0.3, 1], [380, 560, 470])
        v = formant_voice(f0, [(np.interp(tt, [0, 0.3, 1], [600, 900, 800]), 170, 1.0), (1600, 260, 0.6)], n, rng,
                          jitter=0.03, shimmer=0.2, rough=0.3)
        v *= np.interp(tt, [0, 0.08, 0.6, 1], [0, 1, 0.7, 0])
        parts.append(v)
    return seq(parts)


BAMBOO = [523.0, 587.0, 698.0, 784.0, 880.0, 1046.0]   # a pentatonic set of bamboo tubes


def bamboo_knock(rng, f):
    n = n_of(0.6)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for ratio, amp, dec in ((1.0, 1.0, 0.16), (2.76, 0.3, 0.06), (5.4, 0.1, 0.025), (0.5, 0.15, 0.08)):
        y += amp * np.sin(2 * np.pi * f * ratio * t + rng.uniform(0, 6)) * np.exp(-t / dec)
    click = rng.normal(size=n_of(0.006)) * np.exp(-np.arange(n_of(0.006)) / (SR * 0.0015))
    y[:len(click)] += 0.15 * spectral_filter(click, lambda fr: lowpass_shape(fr, 2500, 2), circular=False)
    return y


def chime_cluster(rng):
    out = np.zeros(n_of(3.5))
    t = 0.0
    for i in range(rng.integers(3, 8)):
        place(out, bamboo_knock(rng, BAMBOO[rng.integers(len(BAMBOO))]) * rng.uniform(0.3, 1.0), t, wrap=False)
        t += rng.uniform(0.08, 0.45)
    return out


def carpentry(rng):
    """someone hammering far away: 'tok ... tok ... tok'"""
    out = np.zeros(n_of(6.0))
    t = 0.0
    for i in range(rng.integers(5, 10)):
        n = n_of(0.15)
        tt = np.arange(n) / SR
        f = rng.uniform(380, 460)
        y = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 2.3 * tt)) * np.exp(-tt / 0.03)
        y += 0.4 * rng.normal(size=n) * np.exp(-tt / 0.006)
        place(out, y * rng.uniform(0.7, 1.0), t, wrap=False)
        t += rng.uniform(0.45, 0.7)
    return out


# ====================================================================== water
def bubble(rng, f0, amp, rise=None):
    """Minnaert bubble: a decaying sinusoid whose pitch rises as it reaches the surface"""
    d = 0.043 * f0 + 0.0014 * f0 ** 1.5                # damping (1/s), van den Doel 2005
    dur = min(0.25, 6.0 / d)
    n = n_of(dur)
    t = np.arange(n) / SR
    s = rise if rise is not None else rng.uniform(0.03, 0.15)
    f = f0 * (1 + s * d * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-d * t)
    k = min(n, 12)
    y[:k] *= np.linspace(0, 1, k)
    return amp * y


def bubbles_track(n, rng, rate_curve, fmin, fmax, amp=1.0, rise=(0.1, 0.5), wrap=True):
    """Poisson bubbles, rate_curve (per second, length n), log-uniform pitches"""
    out = np.zeros(n)
    expected = np.cumsum(rate_curve) / SR
    total = int(expected[-1])
    times = np.searchsorted(expected, np.sort(rng.uniform(0, expected[-1], total)))
    for i in times:
        f0 = np.exp(rng.uniform(np.log(fmin), np.log(fmax)))
        a = amp * rng.lognormal(0, 0.6) * (1000.0 / f0) ** 0.4    # bigger bubbles are louder
        place(out, bubble(rng, f0, a, rng.uniform(*rise)), i / SR, wrap=wrap)
    return out


def grains(n, rng, rate_curve, lo, hi, amp=1.0, spread=0.5):
    """crackle: sparse tiny clicks (foam, sand, droplets) with a smooth band-limited
    spectrum (filtered impulses, so no tonal lines)"""
    expected = np.cumsum(rate_curve) / SR
    total = int(expected[-1])
    idx = np.searchsorted(expected, rng.uniform(0, expected[-1], total)) % n
    imp = np.zeros(n)
    np.add.at(imp, idx, rng.lognormal(0, spread, total) * rng.choice([-1, 1], total))
    return spectral_filter(imp, lambda f: band_shape(f, lo, hi, 3)) * amp


def splash(rng, big=False):
    n = n_of(1.4)
    y = np.zeros(n)
    # plop: the fish breaking the surface
    n1 = n_of(0.06)
    tt = np.arange(n1) / SR
    f = rng.uniform(170, 240) * (1 + 3.0 * tt / 0.06)
    y[:n1] += 0.8 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.02)
    # splash: a short bright noise burst
    nz = rng.normal(size=n_of(0.35))
    tt = np.arange(len(nz)) / SR
    nz = spectral_filter(nz, lambda fr: band_shape(fr, 500, 3800, 1), circular=False)
    nz *= np.exp(-tt / (0.07 if big else 0.045)) * (1 - np.exp(-tt / 0.004))
    nz /= np.abs(nz).max() + 1e-9
    place(y, nz * (0.9 if big else 0.6), 0.012, wrap=False)
    # droplets and bubbles falling back
    for i in range(rng.integers(6, 14) if big else rng.integers(3, 8)):
        place(y, bubble(rng, rng.uniform(900, 2800), rng.uniform(0.15, 0.4)), rng.uniform(0.05, 0.6), wrap=False)
    return y


# ====================================================================== beds
def bed_sea(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    t = frames_t(K)
    T = n / SR
    F = FREQS[None, :]
    ts = np.arange(n) / SR
    mag = np.zeros((K, len(FREQS)))
    # distant surf: a steady low roar, slowly breathing
    breathe = 1 + 0.25 * periodic_lfo(K, rng, (2, 9))
    mag += (0.5 * breathe[:, None]) * pink(F, 80) * lowpass_shape(F, 480, 2) * highpass_shape(F, 40)
    mag += (0.1 * breathe[:, None]) * pink(F) * band_shape(F, 450, 1800, 1)
    # waves at irregular times and sizes; now and then a small one right behind a big one
    waves = []
    tw = rng.uniform(0.5, 2.0)
    while True:
        size = float(rng.choice([0.4, 0.6, 0.85, 1.1], p=[0.2, 0.3, 0.3, 0.2]))
        waves.append((tw, size))
        if size >= 0.85 and rng.random() < 0.45:          # a small one right behind a big one
            waves.append((tw + rng.uniform(2.6, 3.4), 0.35))
            tw += 3.0
        tw += rng.uniform(4.5, 8.5) * (0.8 + 0.3 * size)
        if tw > T - 4.5:
            break
    fizz_rate = np.zeros(n)
    for (tb, size) in waves:
        dt = (t - tb + T / 2) % T - T / 2                  # seconds from this wave's break (wrapping)
        dp = np.clip(dt, 0, None)
        build = smoothstep(-2.4, 0.0, dt) * np.exp(-dp / 0.3)
        crash = smoothstep(-0.15, 0.3, dt) * np.exp(-dp / 0.55)
        wash = smoothstep(0.0, 0.6, dt) * np.exp(-dp / (1.5 + 0.6 * size))
        recede = smoothstep(1.2, 2.8, dt) * np.exp(-np.clip(dt - 2.8, 0, None) / 1.8)
        fc_build = 250 + 700 * smoothstep(-2.4, 0.0, dt)
        fc_wash = 1100 + 2100 * np.exp(-dp / 1.1)
        mag += (0.45 * size * build)[:, None] * pink(F, 80) * lowpass_shape(F, fc_build[:, None], 2) * highpass_shape(F, 40)
        mag += (0.9 * size * crash)[:, None] * pink(F, 150) * lowpass_shape(F, 2200 * size, 2) * highpass_shape(F, 55)
        mag += (0.7 * size * wash)[:, None] * pink(F, 300) * band_shape(F, 240, fc_wash[:, None], 2)
        mag += (0.12 * size * recede)[:, None] * band_shape(F, 1200, 3800, 2)
        dts = (ts - tb + T / 2) % T - T / 2
        fizz_rate += 2500 * size * smoothstep(0.8, 2.2, dts) * np.exp(-np.clip(dts - 2.2, 0, None) / 1.6)
    mag *= lowpass_shape(F, 4200, 1)                         # a soft top, never hissy
    y = ola_noise(mag, rng)
    fizz = grains(n, rng, fizz_rate, 1400, 4200, spread=0.45)
    pops = grains(n, rng, fizz_rate * 0.05, 900, 3000, spread=0.5)
    y += fizz / (np.std(fizz) + 1e-9) * np.std(y) * 0.07 + pops / (np.std(pops) + 1e-9) * np.std(y) * 0.03
    # the beach is open: a short diffuse tail
    y = 0.85 * y + 0.15 * circ_conv(y, reverb_ir(0.9, seed=3))
    return y


def bed_river(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    ts = np.arange(n) / SR
    mod = 1 + 0.15 * periodic_lfo(K, rng, (3, 20)) + 0.08 * periodic_lfo(K, rng, (20, 80))
    mag = (0.6 * mod[:, None]) * pink(F, 200) * band_shape(F, 120, 1700, 2)       # the flow
    mag += 0.3 * pink(F, 60) * band_shape(F, 40, 240, 2)                            # low rumble
    flow = ola_noise(mag, rng)
    # babble: bubbles of many sizes, the busy stretches come and go
    lfo = np.interp(ts, frames_t(K), periodic_lfo(K, rng, (4, 30)), period=n / SR)
    clusters = np.zeros(n)
    tc = 0.0
    while tc < n / SR:
        d = rng.uniform(0.15, 0.7)
        m = (ts >= tc) & (ts < tc + d)
        clusters[m] += rng.uniform(80, 260) * np.sin(np.pi * (ts[m] - tc) / d)
        tc += rng.uniform(0.3, 1.6)
    fine = bubbles_track(n, rng, np.full(n, 260.0), 800, 2400, amp=0.22, rise=(0.03, 0.12))
    mid = bubbles_track(n, rng, 45 * (1 + 0.5 * lfo) + clusters, 380, 1400, rise=(0.03, 0.15))
    low = bubbles_track(n, rng, 5 * (1 + 0.6 * lfo) + clusters * 0.06, 170, 420, amp=0.8, rise=(0.02, 0.1))
    bub = fine + mid + low
    # resonant gurgles ('glug')
    gl = np.zeros(n)
    tg = 0.0
    while tg < n / SR:
        L = n_of(rng.uniform(0.06, 0.16))
        nz = rng.normal(size=L) * np.sin(np.pi * np.linspace(0, 1, L)) ** 2
        g = resonator(nz, rng.uniform(220, 600), rng.uniform(30, 70))
        place(gl, g * rng.uniform(0.3, 1.0), tg)
        tg += rng.uniform(0.3, 1.5)
    sb = np.std(bub)
    y = bub + flow / (np.std(flow) + 1e-9) * sb * 0.45 + gl / (np.std(gl) + 1e-9) * sb * 0.25
    y = spectral_filter(y, lambda f: lowpass_shape(f, 4800, 1))
    y = 0.85 * y + 0.15 * circ_conv(y, reverb_ir(0.8, seed=4))
    return y


def bed_lake(sec, rng):
    """calm water (the lagoon at the jetty, the pond): small wavelets lapping against the
    bank and the jetty posts, a hollow 'blup' under the planks now and then"""
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    T = n / SR
    mod = 1 + 0.2 * periodic_lfo(K, rng, (2, 12))
    mag = (0.35 * mod[:, None]) * pink(F, 120) * band_shape(F, 60, 900, 2)
    y = ola_noise(mag, rng)
    laps = np.zeros(n)
    tl = rng.uniform(0.2, 0.8)
    while tl < T:
        size = rng.lognormal(0, 0.45)
        att, dec = rng.uniform(0.05, 0.12), rng.uniform(0.1, 0.22)
        L = n_of(att + 5 * dec)
        tt = np.arange(L) / SR
        env = np.sin(0.5 * np.pi * np.clip(tt / att, 0, 1)) ** 2 * np.exp(-np.clip(tt - att, 0, None) / dec)
        env = fade(env, 0.0, 0.05)
        lo, hi = rng.uniform(250, 450), rng.uniform(1100, 2200)
        nz = spectral_filter(rng.normal(size=L), lambda f: band_shape(f, lo, hi, 2), circular=False)
        lap = nz / (np.abs(nz).max() + 1e-9) * env
        if rng.random() < 0.35:                          # water slapping a post: a hollow 'blup'
            f0 = rng.uniform(160, 300)
            nb = n_of(0.2)
            tb = np.arange(nb) / SR
            blup = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 1.5 * tb)) / SR) * np.exp(-tb / 0.03)
            blup *= np.clip(tb / 0.006, 0, 1)
            place(lap, 0.4 * blup, att * 0.7, wrap=False)
        for i in range(rng.integers(0, 4)):             # a few droplet plinks
            place(lap, bubble(rng, rng.uniform(700, 2000), rng.uniform(0.1, 0.3)), rng.uniform(0.02, 0.2), wrap=False)
        place(laps, lap * size, tl)
        tl += rng.uniform(0.45, 1.6)
    laps = spectral_filter(laps, lambda f: lowpass_shape(f, 3500, 2))
    laps = 0.8 * laps + 0.2 * circ_conv(laps, reverb_ir(0.6, seed=6))
    return mix_events(y, laps, 5.0)


def active_rms(x, floor_db=-30.0):
    """RMS over the stretches where a sparse layer actually sounds"""
    w = n_of(0.05)
    e = np.sqrt(np.convolve(x * x, np.ones(w) / w, "same"))
    on = e > e.max() * db(floor_db)
    return float(np.sqrt(np.mean(x[on] ** 2))) if on.any() else 1e-9


def mix_events(bed, events, rel_db):
    """adds a sparse event layer so that, while it sounds, it sits rel_db over the bed"""
    return bed + events * (np.sqrt(np.mean(bed ** 2)) * db(rel_db) / active_rms(events))


def spaced_times(rng, T, count, min_gap):
    """count random times in [0, T) (circular), at least min_gap apart"""
    for _ in range(200):
        t = np.sort(rng.uniform(0, T, count))
        gaps = np.diff(np.concatenate([t, [t[0] + T]]))
        if gaps.min() >= min_gap:
            return t
    return np.sort(rng.uniform(0, T, count))


def _scatter(buf, rng, makers, count, dist_range, rt60, min_gap=0.8):
    """places `count` calls from weighted makers at spread-out times and random distances"""
    names = list(makers.keys())
    w = np.array([makers[k][1] for k in names], float)
    w /= w.sum()
    T = len(buf) / SR
    last = None
    for tc in spaced_times(rng, T, count, min_gap):
        k = names[rng.choice(len(names), p=w)]
        if k == last and len(names) > 1:                    # not the same bird twice in a row
            k = names[rng.choice(len(names), p=w)]
        last = k
        fn = makers[k][0]
        d = rng.uniform(*dist_range)
        sig = at_distance(fn(rng), d, rt60=rt60, seed=int(rng.integers(1, 6)))
        place(buf, sig * makers[k][2] if len(makers[k]) > 2 else sig, tc)


def bed_forest(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    T = n / SR
    gust = 0.45 + 0.55 * (0.5 + 0.5 * periodic_lfo(K, rng, (3, 7))) ** 1.5
    flutter = np.exp(0.25 * smooth_noise(K, rng, 4))                       # leaves shimmering
    mag = gust[:, None] * pink(F, 250) * band_shape(F, 180, 1700, 2)
    mag += (0.1 * gust ** 2 * flutter)[:, None] * band_shape(F, 1500, 3800, 2)
    mag += 0.25 * pink(F, 60) * band_shape(F, 40, 220, 2)
    y = ola_noise(mag, rng)
    birds = np.zeros(n)
    makers = {"kutilang": (kutilang, 3.0, 0.8), "kacer": (kacer, 2.2, 1.0), "takur": (takur, 1.2, 0.9),
              "tekukur": (tekukur, 1.3, 1.3), "koel": (koel, 0.7, 0.9), "cinenen": (cinenen, 1.0, 0.6),
              "cucak": (cucak, 1.3, 0.9), "perkutut": (perkutut, 0.7, 1.1)}
    _scatter(birds, rng, makers, int(sec * 0.42), (14, 55), 1.6, min_gap=1.3)
    y = mix_events(y, birds, 5.0)
    cs = at_distance(cicada_swell(rng, 7.5), 70, rt60=1.6)               # a far-off tonggeret
    place(y, cs / (np.abs(cs).max() + 1e-9) * np.sqrt(np.mean(y ** 2)) * 0.9, rng.uniform(0, T))
    return y


def bed_field(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    gust = 0.35 + 0.65 * (0.5 + 0.5 * periodic_lfo(K, rng, (2, 6))) ** 1.5
    fc = 700 + 1500 * gust
    mag = gust[:, None] * pink(F, 120) * lowpass_shape(F, fc[:, None], 2) * highpass_shape(F, 45)
    whistle_f = 520 + 140 * periodic_lfo(K, rng, (1, 4))
    mag += (0.18 * gust ** 3)[:, None] * peak_shape(F, whistle_f[:, None], 14.0)
    rust = np.exp(0.3 * smooth_noise(K, rng, 4))
    mag += (0.06 * gust ** 2 * rust)[:, None] * band_shape(F, 1800, 4200, 2)      # grass
    y = ola_noise(mag, rng)
    fb = np.zeros(n)
    _scatter(fb, rng, {"cici": (cici, 1.0, 0.6), "munia": (munia, 1.0, 1.0)}, int(sec * 0.12), (25, 60), 0.6,
             min_gap=3.0)
    return mix_events(y, fb, -1.0)


def bed_village(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    T = n / SR
    gust = 0.5 + 0.5 * (0.5 + 0.5 * periodic_lfo(K, rng, (2, 6)))
    mag = gust[:, None] * pink(F, 150) * band_shape(F, 60, 1500, 2)
    mag += (0.06 * gust)[:, None] * band_shape(F, 1500, 3800, 2)
    y = ola_noise(mag, rng)
    life = np.zeros(n)
    _scatter(life, rng, {"chicken": (chicken, 2.2, 1.4), "sparrow": (sparrow_burst, 1.6, 0.45),
                         "tekukur": (tekukur, 1.0, 1.2), "perkutut": (perkutut, 0.8, 1.0)},
             int(sec * 0.4), (8, 35), 0.7, min_gap=1.2)
    for tc in spaced_times(rng, T, 3, 8.0):             # bamboo chimes stirred by the breeze
        place(life, at_distance(chime_cluster(rng), rng.uniform(10, 20), rt60=0.7) * 0.45, tc)
    place(life, at_distance(carpentry(rng), 60, rt60=0.9) * 1.6, rng.uniform(0, T))
    return mix_events(y, life, 6.0)


def bed_night(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    T = n / SR
    breeze = 0.6 + 0.4 * (0.5 + 0.5 * periodic_lfo(K, rng, (2, 5)))
    mag = breeze[:, None] * pink(F, 100) * band_shape(F, 45, 800, 2)
    wall = 1 + 0.2 * periodic_lfo(K, rng, (5, 40))                         # the far insect chorus
    mag += (0.02 * wall)[:, None] * peak_shape(F, 3400, 2.5) * lowpass_shape(F, 4500, 2)
    y = ola_noise(mag, rng)
    ins = np.zeros(n)
    ts = np.arange(n) / SR
    # field crickets: each sings in bouts with its own rhythm, then rests
    for c in range(3):                                   # review: 4 -> 3 voices, more rests (was a near-constant pulse wall)
        f = rng.uniform(3100, 4200)
        period = rng.uniform(0.4, 0.8)
        pulses = int(rng.integers(3, 5))
        a = 1.0 / max(1.0, rng.uniform(8, 30) / 6.0)
        chirp = cricket_chirp(rng, f, pulses)
        tc = rng.uniform(0, T)
        sung = 0.0
        while sung < T * rng.uniform(0.3, 0.5):
            bout = rng.uniform(4, 11)
            k = 0.0
            while k < bout:
                sw = np.sin(np.pi * k / bout) ** 0.5                    # bouts swell in and out
                place(ins, chirp * a * (0.5 + 0.5 * sw), tc + k)
                k += period * rng.uniform(0.97, 1.03)
            sung += bout
            tc += bout + rng.uniform(5.0, 12.0)
    # one tree cricket, a soft trill in long bouts
    tr = tree_cricket(rng, n, 2500.0, round(46.0 * T) / T)
    gate = np.zeros(n)
    for tb in spaced_times(rng, T, 3, 7.0):
        d = rng.uniform(4.0, 7.0)
        u = ((ts - tb) % T) / d
        gate += np.where(u < 1, np.sin(np.pi * np.clip(u, 0, 1)) ** 0.7, 0.0)
    ins += 0.12 * tr * np.clip(gate, 0, 1)
    ins = spectral_filter(ins, lambda f: lowpass_shape(f, 4200, 2))
    ins = 0.65 * ins + 0.35 * circ_conv(ins, reverb_ir(1.3, seed=5))
    for tc in spaced_times(rng, T, 2, 10.0):            # a cicak on a wall somewhere
        place(ins, at_distance(cicak(rng), rng.uniform(12, 22), rt60=0.9) * 1.2, tc)
    return mix_events(y, ins, 0.0)


def bed_frogs(sec, rng):
    n = loop_len(sec)
    K = n // HOP
    F = FREQS[None, :]
    T = n / SR
    mag = pink(F, 100) * band_shape(F, 45, 600, 2) * np.ones((K, 1))
    y = ola_noise(mag, rng)
    fr = np.zeros(n)
    frogs = [("ngorek", rng.uniform(8, 20)) for _ in range(3)] + [("kerok", rng.uniform(12, 25)) for _ in range(2)] + \
            [("tree", rng.uniform(10, 20))]
    for kind, dist in frogs:
        tc = rng.uniform(0, 4)
        while tc < T:
            b = at_distance(frog_bout(rng, kind), dist, rt60=1.1)
            place(fr, b * (1.3 if kind == "kerok" else 1.0), tc)
            tc += len(b) / SR + rng.uniform(2.0, 6.0 if kind != "kerok" else 8.0)
    fr = spectral_filter(fr, lambda f: lowpass_shape(f, 3500, 2))
    return mix_events(y, fr, 6.0)


BEDS = {
    "sea": (bed_sea, 44.0, 11),
    "river": (bed_river, 32.0, 12),
    "lake": (bed_lake, 26.0, 18),
    "forest": (bed_forest, 48.0, 13),
    "field": (bed_field, 34.0, 14),
    "village": (bed_village, 40.0, 15),
    "night": (bed_night, 40.0, 16),
    "frogs": (bed_frogs, 32.0, 17),
}


# ====================================================================== one-shots
def shot_bird(kind):
    def make(rng):
        return at_distance(BIRDS[kind](rng), 6.0, wet=0.16, rt60=1.1)
    return make


SHOTS = {f"bird_{k}": (shot_bird(k), 100 + i) for i, k in enumerate(BIRDS)}
SHOTS.update({
    "frog_a": (lambda rng: at_distance(frog_bout(rng, "ngorek"), 5, wet=0.15, rt60=0.9), 201),
    "frog_b": (lambda rng: at_distance(frog_bout(rng, "kerok"), 5, wet=0.15, rt60=0.9), 202),
    "tokek": (lambda rng: at_distance(tokek(rng), 6, wet=0.2, rt60=0.8), 203),
    "owl": (lambda rng: at_distance(owl(rng), 10, wet=0.25, rt60=1.3), 204),
    "splash_a": (lambda rng: at_distance(splash(rng, False), 3, wet=0.1, rt60=0.6), 205),
    "splash_b": (lambda rng: at_distance(splash(rng, True), 3, wet=0.1, rt60=0.6), 206),
    "rooster": (lambda rng: at_distance(rooster(rng), 12, wet=0.3, rt60=1.0), 207),
    "chicken": (lambda rng: at_distance(chicken(rng), 5, wet=0.15, rt60=0.7), 208),
    "tonggeret": (lambda rng: at_distance(cicada_swell(rng, 6.5), 12, wet=0.2, rt60=1.2), 209),
})
SHOT_PEAK = {"tonggeret": -9.0, "splash_a": -4.0, "owl": -4.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--png")
    ap.add_argument("--wav")
    ap.add_argument("--out", help="write the .ogg files here instead of game/assets/audio")
    args = ap.parse_args()
    global OUT
    if args.out:
        OUT = args.out
    want = set(args.names)
    os.makedirs(OUT, exist_ok=True)
    for name, (fn, sec, seed) in BEDS.items():
        if want and name not in want:
            continue
        y = fn(sec, np.random.default_rng(seed))
        finish_bed(name, y, args=args)
    for name, (fn, seed) in SHOTS.items():
        if want and name not in want and not ("shots" in want):
            continue
        y = fn(np.random.default_rng(seed))
        finish_shot(name, y, SHOT_PEAK.get(name, -3.0), args=args)
    total = sum(r[4] for r in REPORT)
    print(f"total {total / 1024:.0f} KB in {len(REPORT)} files")


if __name__ == "__main__":
    main()

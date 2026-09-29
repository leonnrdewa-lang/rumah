"""DSP helpers (numpy only): FFT filters, convolution reverb, bit-crush, additive saw, bus mixing."""
import os, subprocess, wave
import numpy as np
SR = 48000
rng = np.random.default_rng(11)
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
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
    x = x.copy(); na, nb = min(int(a * SR), len(x) // 2), min(int(b * SR), len(x) // 2)              # very short files: fades never longer than half the file
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


mtof = lambda m: 440.0 * 2 ** ((m - 69) / 12)
clamp = lambda x, a=0., b=1.: min(b, max(a, x))
prog = lambda t, a, b: clamp((t - a) / max(1e-9, b - a))

def swept_noise(dur, f0, f1, q=1.6, blocks=14, seed=0):
    r = np.random.default_rng(seed); n = int(dur * SR); noise = r.standard_normal(n).astype(np.float32); out = np.zeros(n, np.float32); bl = max(16, n // blocks * 2)
    w = np.hanning(bl).astype(np.float32); hop = bl // 2
    for i in range(blocks):
        s = i * hop; seg = noise[s:s + bl]
        if len(seg) < bl: break
        fc = f0 * (f1 / f0) ** (i / max(1, blocks - 1)); out[s:s + bl] += bandpass(seg, fc, q) * w
    return out / (np.abs(out).max() + 1e-9)

def load_audio(path, sr=SR, mono=True):
    p = subprocess.run([FFMPEG, '-v', 'error', '-i', path, '-ac', '1' if mono else '2', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True)
    a = np.frombuffer(p.stdout, np.float32).copy(); return a if mono else a.reshape(-1, 2).T

def write_wav(path, st):
    st = np.atleast_2d(st); x = np.clip(st.T, -1, 1)
    with wave.open(path, 'wb') as w: w.setnchannels(st.shape[0]); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype('<i2').tobytes())

"""Synthesises the game's sound effects, a looping island tune and a beach
ambience with numpy, written as 16-bit mono WAV into game/assets/audio/.
The two long loops (music, ambient) are written as Ogg Vorbis instead (needs
`pip install soundfile`): as QOA-compressed WAV they cost ~500 KB of the web
download, as Vorbis ~240 KB.

python3 tools/make_audio.py
"""
import os
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "audio")
os.makedirs(OUT, exist_ok=True)
SR = 22050
rng = np.random.default_rng(3)


def t_axis(sec):
    return np.arange(int(SR * sec)) / SR


def env(n, attack=0.005, decay=0.2):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def tone(freq, sec, decay=0.2, harmonics=((1, 1.0),), attack=0.004):
    t = t_axis(sec)
    y = sum(amp * np.sin(2 * np.pi * freq * h * t) for h, amp in harmonics)
    return y * env(len(t), attack, decay)


def noise(sec):
    return rng.uniform(-1, 1, int(SR * sec))


def lowpass(x, alpha):
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def pad(x, sec_before):
    return np.concatenate([np.zeros(int(SR * sec_before)), x])


def save(name, y, peak=0.8, vorbis=None):
    """vorbis: soundfile compression level (0 = best quality, 1 = smallest) to write
    <name>.ogg instead of <name>.wav."""
    y = np.asarray(y, dtype=np.float64)
    m = np.max(np.abs(y)) or 1.0
    y = y / m * peak
    if vorbis is not None:
        import soundfile
        soundfile.write(os.path.join(OUT, name + ".ogg"), y, SR, format="OGG", subtype="VORBIS",
                        compression_level=vorbis)
        stale = os.path.join(OUT, name + ".wav")
        for f in (stale, stale + ".import"):
            if os.path.exists(f):
                os.remove(f)
        print(name, f"{len(y) / SR:.2f}s (ogg)")
        return
    data = (y * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(name, f"{len(y) / SR:.2f}s")


MARIMBA = ((1, 1.0), (4, 0.25), (10, 0.05))
BELL = ((1, 1.0), (2.76, 0.35), (5.4, 0.12))

# ---------------------------------------------------------------- sfx
save("click", tone(1400, 0.05, 0.012) * 0.6)
save("pop", tone(700, 0.12, 0.05) * np.linspace(1, 1, int(SR * 0.12)) + tone(1050, 0.12, 0.04) * 0.4)
save("coin", mix(tone(1976, 0.25, 0.08, BELL), pad(tone(2637, 0.35, 0.12, BELL), 0.07)))
save("cash", mix(tone(1568, 0.3, 0.1, BELL), pad(tone(2093, 0.3, 0.1, BELL), 0.06), pad(tone(2637, 0.6, 0.25, BELL), 0.12),
                 pad(noise(0.08) * env(int(SR * 0.08), 0.001, 0.02) * 0.4, 0.0)))
chop_n = lowpass(noise(0.22), 0.35) * env(int(SR * 0.22), 0.001, 0.05)
save("chop", mix(chop_n, tone(110, 0.2, 0.06) * 0.8, pad(lowpass(noise(0.15), 0.5) * env(int(SR * 0.15), 0.001, 0.04) * 0.5, 0.09)))
save("plant", mix(lowpass(noise(0.25), 0.12) * env(int(SR * 0.25), 0.01, 0.08), pad(tone(523, 0.3, 0.1, MARIMBA) * 0.5, 0.08)))
save("harvest", mix(tone(90, 0.3, 0.1) * 1.2, lowpass(noise(0.3), 0.25) * env(int(SR * 0.3), 0.002, 0.1) * 0.7,
                    pad(tone(784, 0.3, 0.12, MARIMBA) * 0.4, 0.1)))
save("bad", mix(tone(220, 0.25, 0.12, MARIMBA), pad(tone(165, 0.35, 0.16, MARIMBA), 0.12)))
save("quest", mix(*[pad(tone(f, 0.7, 0.3, BELL) * 0.8, i * 0.09) for i, f in enumerate([523, 659, 784, 1047])]))
sweep_t = t_axis(0.45)
wh = lowpass(noise(0.45), 0.08) * np.sin(np.pi * sweep_t / 0.45) ** 2
save("whoosh", wh, 0.5)
save("step", lowpass(noise(0.06), 0.2) * env(int(SR * 0.06), 0.002, 0.015), 0.5)
save("door", mix(tone(180, 0.12, 0.03, ((1, 1), (2.3, 0.4))), pad(tone(170, 0.14, 0.035, ((1, 1), (2.3, 0.4))), 0.13)))

# ---------------------------------------------------------------- music: easy island loop
BPM = 96
beat = 60 / BPM
bars = 16
total = int(SR * beat * 4 * bars)
music = np.zeros(total)


def place(buf, sig, at_sec):
    i = int(at_sec * SR) % len(buf)
    n = len(sig)
    end = i + n
    if end <= len(buf):
        buf[i:end] += sig
    else:
        k = len(buf) - i
        buf[i:] += sig[:k]
        buf[:n - k] += sig[k:]  # wrap so the loop is seamless


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


chords = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]  # C Am F G
melody = [
    [72, None, 74, 76, None, 79, 76, None], [76, None, 74, 72, None, 69, 72, None],
    [69, None, 72, 74, None, 72, 69, None], [67, None, 71, 74, None, 76, 74, None],
    [72, None, 76, 79, None, 81, 79, 76], [76, None, 72, 74, None, 76, 72, None],
    [69, 72, 74, None, 77, None, 76, 74], [74, None, 71, 67, None, 71, 74, None],
]
for bar in range(bars):
    c = chords[bar % 4]
    t0 = bar * 4 * beat
    # bass: root on 1 and 3
    for b in (0, 2):
        place(music, tone(midi(c[0] - 24), beat * 1.6, 0.35, ((1, 1.0), (2, 0.3))) * 0.55, t0 + b * beat)
    # soft marimba chords on off-beats
    for b in (1, 3):
        for n in c:
            place(music, tone(midi(n), beat, 0.18, MARIMBA) * 0.13, t0 + b * beat + beat * 0.5)
    # melody (eighth notes), second half of the song an octave-ish variation
    mel = melody[bar % 8]
    for k, n in enumerate(mel):
        if n is None:
            continue
        if bar >= 8 and k % 4 == 3:
            continue
        place(music, tone(midi(n), beat * 1.2, 0.28, MARIMBA) * 0.32, t0 + k * beat * 0.5)
    # shaker
    for k in range(8):
        s = lowpass(noise(0.05), 0.7) * env(int(SR * 0.05), 0.001, 0.012) * (0.07 if k % 2 else 0.04)
        place(music, s, t0 + k * beat * 0.5)
save("music", music, 0.55, vorbis=0.45)

# ---------------------------------------------------------------- ambience: waves + birds
amb_sec = 16.0
n = int(SR * amb_sec)
waves = lowpass(rng.uniform(-1, 1, n), 0.04)
tt = np.arange(n) / SR
swell = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 8.0) ** 2
waves *= swell
amb = waves * 1.0
for i in range(7):
    at = rng.uniform(0, amb_sec)
    f0 = rng.uniform(2400, 3600)
    for k in range(rng.integers(2, 5)):
        ct = t_axis(0.09)
        chirp = np.sin(2 * np.pi * (f0 + 2500 * ct) * ct) * env(len(ct), 0.005, 0.03)
        place(amb, chirp * 0.05, at + k * 0.13)
save("ambient", amb, 0.5, vorbis=0.6)

#!/usr/bin/env python3
"""Composes, renders and masters the soundtrack of Hanoman Duta.

Everything is original and written out below. Two sound sources are mixed:

* numpy-synthesised gamelan: saron / demung / peking (inharmonic free-bar partials,
  damped by the next stroke), gender (soft mallet, long ring), bonang (kettle gongs,
  short pitch settle), kenong / kethuk, kempul and gong ageng (low inharmonic partials,
  slow bloom and beating), kendang strokes (dhang/tak/tung/ket...), plus cinematic
  booms, risers and water drops. Every metallophone voice is a detuned pair
  (pengumbang/pengisep) so it has "ombak" beating, spread across the stereo field.
* FluidSynth-rendered MIDI stems from the MuseScore General SoundFont (drum kit,
  distorted guitars, bass, choir, brass, strings, suling = flute). Each note is
  retuned to true slendro/pelog cents: every distinct pitch-bend offset gets its own
  MIDI channel, so polyphonic parts stay in tune with the synthesised gamelan.

Mixing in numpy: per-stem loudness balance, EQ, drive, echo, pan, synthetic stereo
hall reverb, glue compression, -18 LUFS loudness normalisation and a true-peak limiter
(-1 dBTP). Loops are rendered with a tail that is wrapped back onto the start and the
master chain runs circularly, so the loop point is seamless (checked and reported).

Output (hanoman/game/assets/audio/, Ogg Vorbis 44.1 kHz stereo):
  mus_hub, mus_dandaka, mus_muara, mus_boss, mus_title   seamless loops
  stg_victory, stg_death                                 one-shot stings

Needs: apt fluidsynth musescore-general-soundfont (or fluid-soundfont-gm), ffmpeg;
pip numpy scipy soundfile pyloudnorm mido (matplotlib for --png).

  python3 hanoman/tools/make_music.py                 # everything
  python3 hanoman/tools/make_music.py hub boss        # only these
  python3 hanoman/tools/make_music.py --png /tmp/png  # also waveform + spectrogram PNGs
"""
import argparse
import math
import os
import random
import re
import shutil
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

import mido
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "game", "assets", "audio")
WORK = os.environ.get("MUSIC_WORK", "/tmp/hanoman_audio/music")
SOUNDFONTS = ["/usr/share/sounds/sf3/MuseScore_General.sf3", "/usr/share/sounds/sf2/FluidR3_GM.sf2"]
SR = 44100
TPB = 480
TAIL = 10.0
TARGET_LUFS = -18.0
CEILING_DBTP = -1.0
VORBIS_Q = 1.5

# cents above tuning note "1" (Javanese kepatihan numbers)
SLENDRO = {1: 0, 2: 236, 3: 474, 5: 714, 6: 952}
PELOG = {1: 0, 2: 122, 3: 262, 4: 539, 5: 677, 6: 784, 7: 948}


# ============================================================== song model
class Lane:
    """a numpy-synthesised instrument (one stem)"""

    def __init__(self, inst, level=-24, pan=0.0, width=1.0, rev=0.25, hp=0, lp=0, ring=None, echo=None, beat=None):
        self.inst, self.level, self.pan, self.width, self.rev = inst, level, pan, width, rev
        self.hp, self.lp, self.ring, self.echo, self.beat = hp, lp, ring, echo, beat
        self.ev = []            # (beat, pitch-or-stroke, vel, extra)


class Part:
    """a FluidSynth-rendered MIDI stem"""

    def __init__(self, program, bank=0, drum=False, level=-24, pan=0.0, width=1.0, rev=0.2, hp=0, lp=0,
                 drive=0.0, echo=None, jitter=0.006, velrand=6, gate=0.95, shelf=None):
        self.program, self.bank, self.drum = program, bank, drum
        self.level, self.pan, self.width, self.rev, self.hp, self.lp = level, pan, width, rev, hp, lp
        self.drive, self.echo, self.jitter, self.velrand, self.gate, self.shelf = drive, echo, jitter, velrand, gate, shelf
        self.notes = []         # (beat, dur, midi_float, vel, flags)
        self.ccs = []           # (beat, cc, value)


class Song:
    def __init__(self, name, bpm, beats, scale, mode, tonic, loop=True, rt60=2.2, max_len=None, meter=4,
                 target=TARGET_LUFS, seed=1):
        self.name, self.bpm, self.beats, self.scale, self.mode, self.tonic = name, bpm, beats, scale, mode, tonic
        self.loop, self.rt60, self.max_len, self.meter, self.target = loop, rt60, max_len, meter, target
        self.lanes, self.parts = {}, {}
        self.rng = random.Random(seed)
        lad = []
        for o in range(-5, 6):
            for d in mode:
                lad.append(scale[d] + 1200 * o)
        self.ladder = sorted(lad)

    def spb(self):
        return 60.0 / self.bpm

    def lane(self, name, inst, **kw):
        self.lanes[name] = Lane(inst, **kw)
        return self.lanes[name]

    def part(self, name, program, **kw):
        self.parts[name] = Part(program, **kw)
        return self.parts[name]

    def hz(self, cents):
        return 440.0 * 2 ** ((self.tonic - 69) / 12 + cents / 1200)

    def cents(self, tok, oct=0):
        """'6' -> cents, "1'" one octave up, '5,' one down; oct shifts octaves"""
        d = int(tok[0])
        return self.scale[d] + 1200 * (tok.count("'") - tok.count(",") + oct)

    def step(self, cents, k):
        i = int(np.argmin([abs(c - cents) for c in self.ladder]))
        return self.ladder[max(0, min(len(self.ladder) - 1, i + k))]

    def n_mode(self):
        return len(self.mode)


def grid(text, step):
    """tokens on a grid: note tokens, '-' extends the previous one, '.' is a rest"""
    out = []
    for i, tok in enumerate(text.split()):
        if tok == "-":
            if out:
                out[-1][1] += step
        elif tok != ".":
            out.append([i * step, step, tok])
    return out, len(text.split()) * step


def seq(text):
    """'tok:dur' pairs ('-' rest); returns [(start, dur, tok)], total"""
    out, t = [], 0.0
    for item in text.split():
        tok, d = item.rsplit(":", 1)
        d = float(d)
        if tok != "-":
            out.append((t, d, tok))
        t += d
    return out, t


# ============================================================== note helpers
def hit(song, lane, beat, what, vel=0.8, **extra):
    song.lanes[lane].ev.append((beat, what, vel, extra))


def note(song, part, beat, dur, cents, vel=80, **flags):
    song.parts[part].notes.append((beat, dur, song.tonic + cents / 100.0, vel, flags))


def dnote(song, part, beat, key, vel=90, dur=0.25):
    song.parts[part].notes.append((beat, dur, float(key), vel, {}))


def line(song, part, beat0, text, oct=0, vel=80, gate=None, scoop=False, cents_shift=0, lane=None):
    """melody in 'tok:dur' notation on a SoundFont part (or numpy lane); '~' prefix = scoop"""
    notes, total = seq(text)
    for t, d, tok in notes:
        sc = tok.startswith("~")
        tok = tok.lstrip("~")
        c = song.cents(tok, oct) + cents_shift
        if lane:
            hit(song, lane, beat0 + t, c, vel / 127)
        else:
            fl = {}
            if sc or scoop:
                fl["scoop"] = True
            if gate:
                fl["gate"] = gate
            note(song, part, beat0 + t, d, c, vel, **fl)
    return total


def balungan(song, lanes, beat0, text, step=1.0, vel=0.7, oct=0):
    """core melody: token i sounds at beat0 + (i+1)*step (the last one on the gong).
    returns [(beat, cents-or-None)]"""
    toks = text.split()
    pos = []
    for i, tok in enumerate(toks):
        b = beat0 + (i + 1) * step
        if tok == ".":
            pos.append((b, None))
            continue
        c = song.cents(tok, oct)
        pos.append((b, c))
        for ln, o, v in lanes:
            hit(song, ln, b, c + 1200 * o, vel * v * (1.08 if (i + 1) % 4 == 0 else 1.0))
    return pos


def targets(pos):
    """fill rests with the next sounding note (the note the elaboration heads for)"""
    out = [c for _, c in pos]
    nxt = None
    for i in range(len(out) - 1, -1, -1):
        if out[i] is None:
            out[i] = nxt
        else:
            nxt = out[i]
    last = None
    for i in range(len(out)):
        if out[i] is None:
            out[i] = last
        last = out[i]
    return out


COLOTOMY = {
    # positions 1..N: kethuk, kempul, kenong, gong
    "lancaran": (16, [1, 3, 5, 7, 9, 11, 13, 15], [6, 10, 14], [4, 8, 12, 16], [16]),
    "ladrang": (32, [2, 6, 10, 14, 18, 22, 26, 30], [12, 20, 28], [8, 16, 24, 32], [32]),
    "ketawang": (16, [2, 6, 10, 14], [12], [8, 16], [16]),
}


def colotomy(song, pos, form, gong_cents, vel=1.0, kethuk=True, kempul=True, kenong=True, gong=True):
    n, kt, kp, kn, gg = COLOTOMY[form]
    tg = targets(pos)
    for i, (b, _) in enumerate(pos):
        p = i % n + 1
        c = tg[i] if tg[i] is not None else 0
        if kethuk and p in kt and "kethuk" in song.lanes:
            hit(song, "kethuk", b, song.scale[song.mode[0]] - 1200, 0.55 * vel)
        if kempul and p in kp and "kempul" in song.lanes:
            hit(song, "kempul", b, (c % 1200) - 1200, 0.75 * vel)
        if kenong and p in kn and "kenong" in song.lanes and p not in gg:
            hit(song, "kenong", b, (c % 1200), 0.7 * vel)
        if gong and p in gg and "gong" in song.lanes:
            hit(song, "gong", b, gong_cents, 1.0 * vel)
            if "kenong" in song.lanes and kenong:
                hit(song, "kenong", b, (c % 1200), 0.75 * vel)


IMBAL_T = [[1, 0, 1, 0], [-1, 0, -1, 0], [1, 2, 1, 0], [0, 1, -1, 0], [-1, -2, -1, 0], [1, 0, -1, 0],
           [2, 1, 2, 0]]


def imbal(song, la, lb, pos, sub=4, oct=1, vel=0.7, seed=0, every=1):
    """interlocking bonang: a fast figure heading for each balungan note, alternate
    notes split between the two players"""
    rng = random.Random(seed)
    tg = targets(pos)
    step = pos[1][0] - pos[0][0] if len(pos) > 1 else 1.0
    tpl = rng.choice(IMBAL_T)
    for i, (b, _) in enumerate(pos):
        if i % 4 == 0:
            tpl = rng.choice(IMBAL_T)
        if i % every:
            continue
        t = tg[i]
        if t is None:
            continue
        t += 1200 * oct
        for j in range(sub):
            k = tpl[int(j * 4 / sub)] if sub != 4 else tpl[j]
            if j == sub - 1:
                k = 0
            c = song.step(t, k)
            tb = b - step + (j + 1) * step / sub
            hit(song, la if j % 2 == 0 else lb, tb, c, vel * (1.1 if j == sub - 1 else 0.9))


def peking(song, lane, pos, oct=1, vel=0.5, pattern="nacah"):
    tg = targets(pos)
    step = pos[1][0] - pos[0][0]
    for i, (b, c) in enumerate(pos):
        t = tg[i]
        if t is None:
            continue
        t += 1200 * oct
        if pattern == "nacah":
            hit(song, lane, b - step / 2, t, vel * 0.8)
            hit(song, lane, b, t, vel)
        else:
            hit(song, lane, b, t, vel)


GENDER_T = [
    [2, 1, 2, 3, 2, 1, 0, 1, 2, 1, 0, -1, 0, 1, -1, 0],
    [0, -1, 0, 1, 0, -1, -2, -1, 0, 1, 2, 1, 0, -1, 1, 0],
    [-2, -1, 0, -1, -2, -3, -2, -1, 0, 1, 0, -1, -2, -1, 1, 0],
    [3, 2, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 1, -1, 1, 0],
    [0, 1, 2, 1, 0, 1, 0, -1, -2, -1, 0, 1, 2, 1, -1, 0],
    [-1, 0, 1, 0, 1, 2, 1, 0, -1, -2, -1, 0, -1, 1, -1, 0],
]
RIPPLE_T = [
    [0, 2, 4, 5, 4, 2, 0, 2, 4, 5, 7, 5, 4, 2, 1, 0],
    [5, 4, 2, 0, 2, 4, 5, 7, 5, 4, 2, 0, -1, 0, 2, 0],
    [0, 1, 2, 4, 2, 1, 0, 1, 2, 4, 5, 4, 2, 1, -1, 0],
]


def gender(song, lr, ll, pos, per_beat=4, oct=0, vel=0.6, seed=0, tpls=GENDER_T, left=True, rest_every=None):
    """flowing two-hand elaboration: each 4-beat gatra is a 16-step figure landing on
    the gatra's final note (seleh); the left hand plays every other step an octave down"""
    rng = random.Random(seed)
    tg = targets(pos)
    step = pos[1][0] - pos[0][0]
    for g in range(0, len(pos), 4):
        gat = pos[g:g + 4]
        if len(gat) < 4:
            break
        t = tg[g + 3]
        if t is None:
            continue
        t += 1200 * oct
        tpl = rng.choice(tpls)
        n = per_beat * 4
        b0 = gat[0][0] - step
        for j in range(n):
            k = tpl[int(j * 16 / n)] if j < n - 1 else 0
            c = song.step(t, k)
            tb = b0 + (j + 1) * 4 * step / n
            acc = 1.12 if (j + 1) % per_beat == 0 else 0.92
            hit(song, lr, tb, c, vel * acc)
            if left and (j % 2 == 1):
                cl = song.step(c, -song.n_mode())
                if j == n - 1:
                    cl = t - 1200
                hit(song, ll, tb, cl, vel * 0.85 * acc)


def kendang(song, lane, beat0, text, vel=1.0, sub=4):
    """strokes on a 16th grid: D dhang, d soft dhang, B ciblon bend-up, T tak, t ket,
    O tung, P dlang (D+O), k ghost ket, . rest"""
    s = text.replace(" ", "")
    for i, ch in enumerate(s):
        if ch == ".":
            continue
        hit(song, lane, beat0 + i / sub, ch, vel)


def drums(song, part, beat0, pats, sub=4, vel=1.0):
    """pats: {midi key: pattern} 16th grid, X accent, x normal, o ghost, r roll(32nds)"""
    for key, pat in pats.items():
        s = pat.replace(" ", "")
        for i, ch in enumerate(s):
            if ch == ".":
                continue
            v = {"X": 118, "x": 96, "o": 60, "r": 80}[ch] * vel
            b = beat0 + i / sub
            dnote(song, part, b, key, min(127, v), 0.2)
            if ch == "r":
                dnote(song, part, b + 0.5 / sub, key, min(127, v * 0.85), 0.2)


def riff(song, part, beat0, text, oct=-2, vel=100, step=0.25, chord=True, bass=None, bass_oct=-3):
    """guitar riff on a 16th grid: '1_' palm-muted chug, '2!' power chord, '-' hold"""
    toks, total = grid(text, step)
    for t, d, tok in toks:
        mute = tok.endswith("_")
        pc = tok.endswith("!")
        base = tok.rstrip("_!")
        c = song.cents(base, oct)
        if mute:
            note(song, part, beat0 + t, d, c, vel * 0.82, gate=0.5)
        else:
            note(song, part, beat0 + t, d, c, vel)
            if chord and pc:
                note(song, part, beat0 + t, d, c + 700, vel * 0.9)
                note(song, part, beat0 + t, d, c + 1200, vel * 0.8)
        if bass:
            cb = song.cents(base, bass_oct)
            note(song, bass, beat0 + t, d, cb, 100 if not mute else 88, gate=0.6 if mute else 0.92)
    return total


def sustain(song, part, beat, dur, cents_list, vel=70):
    for c in cents_list:
        note(song, part, beat, dur, c, vel)


def swell(song, part, beat0, beats, lo=30, hi=110, cc=11, steps=24):
    for k in range(steps + 1):
        song.parts[part].ccs.append((beat0 + beats * k / steps, cc, int(lo + (hi - lo) * k / steps)))


# ============================================================== DSP basics
def sos_hp(fc, order=2):
    return signal.butter(order, fc, "highpass", fs=SR, output="sos")


def sos_lp(fc, order=2):
    return signal.butter(order, fc, "lowpass", fs=SR, output="sos")


def sos_bp(lo, hi, order=2):
    return signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos")


def filt(sos, x):
    return signal.sosfilt(sos, x, axis=-1)


def biquad_shelf(fc, gain_db, high=True, q=0.707):
    a = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * fc / SR
    al = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    s = 1 if high else -1
    b0 = a * ((a + 1) + s * (a - 1) * cw + 2 * math.sqrt(a) * al)
    b1 = -2 * s * a * ((a - 1) + s * (a + 1) * cw)
    b2 = a * ((a + 1) + s * (a - 1) * cw - 2 * math.sqrt(a) * al)
    a0 = (a + 1) - s * (a - 1) * cw + 2 * math.sqrt(a) * al
    a1 = 2 * s * ((a - 1) - s * (a + 1) * cw)
    a2 = (a + 1) - s * (a - 1) * cw - 2 * math.sqrt(a) * al
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


def make_ir(rt60, seed=7, predelay=0.02, bright=1.0):
    rng = np.random.default_rng(seed)
    n = int(SR * (rt60 * 1.2 + predelay))
    t = np.arange(n) / SR
    ir = np.zeros((2, n))
    for c in range(2):
        noise = rng.standard_normal(n)
        tail = np.zeros(n)
        for lo, hi, k in [(None, 350, 1.15), (350, 2500, 1.0), (2500, 6000, 0.6 * bright), (6000, None, 0.33 * bright)]:
            if lo is None:
                b = filt(sos_lp(hi, 4), noise)
            elif hi is None:
                b = filt(sos_hp(lo, 4), noise)
            else:
                b = filt(sos_bp(lo, hi, 4), noise)
            tail += b * np.exp(-6.91 * np.maximum(0, t - predelay) / (rt60 * k))
        tail *= np.clip((t - predelay) / 0.03, 0, 1)
        ir[c] = tail
        for k in range(10):
            i = int((predelay * 0.3 + rng.uniform(0.004, 0.06)) * SR)
            ir[c, i] += rng.uniform(0.3, 0.9) * (0.75 ** k) * rng.choice([-1, 1]) * 6.0
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir


def reverb(x, ir):
    return np.stack([signal.oaconvolve(x[c], ir[c])[:x.shape[1]] for c in range(2)])


def lufs(x):
    try:
        v = pyln.Meter(SR).integrated_loudness(np.ascontiguousarray(x.T))
    except ValueError:
        return -120.0
    return v if np.isfinite(v) else -120.0


def true_peak_db(x):
    pk = max(float(np.max(np.abs(signal.resample_poly(c, 4, 1)))) for c in x)
    return 20 * math.log10(pk + 1e-12)


def pan_width(x, pan, width):
    mid = (x[0] + x[1]) * 0.5
    side = (x[0] - x[1]) * 0.5 * width
    l, r = mid + side, mid - side
    a = (pan + 1) * math.pi / 4
    return np.stack([l * math.cos(a) * math.sqrt(2), r * math.sin(a) * math.sqrt(2)])


def echo(x, delay_s, fb=0.35, mix=0.35, pingpong=True):
    d = int(delay_s * SR)
    y = x.copy()
    g = mix
    src = x
    k = 1
    while g > 0.01 and k * d < x.shape[1]:
        src = filt(sos_lp(5000, 1), src)
        sh = np.zeros_like(x)
        sh[:, k * d:] = src[:, :x.shape[1] - k * d]
        if pingpong and k % 2 == 1:
            sh = sh[::-1]
        y += g * sh
        g *= fb
        k += 1
    return y


def compressor(x, thresh_db=-18.0, ratio=2.0, attack=0.02, release=0.25, knee=6.0, block=32):
    p = np.mean(x ** 2, axis=0)
    nb = len(p) // block
    pb = p[:nb * block].reshape(nb, block).mean(axis=1)
    lvl = 10 * np.log10(pb + 1e-12)
    over = lvl - thresh_db
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, (1 - 1 / ratio) * over, (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    dt = block / SR
    ka, kr = 1 - math.exp(-dt / attack), 1 - math.exp(-dt / release)
    g = np.empty(nb)
    s = 0.0
    for i in range(nb):
        k = ka if gr[i] > s else kr
        s += k * (gr[i] - s)
        g[i] = s
    gain = 10 ** (-np.repeat(g, block) / 20)
    gain = np.concatenate([gain, np.full(len(p) - len(gain), gain[-1] if len(gain) else 1.0)])
    return x * gain, float(np.max(g)) if nb else 0.0


def limiter(x, ceiling_db=CEILING_DBTP - 0.3, look=0.004):
    ceil = 10 ** (ceiling_db / 20)
    pk = np.zeros(x.shape[1])
    for c in x:
        up = np.abs(signal.resample_poly(c, 4, 1))
        pk = np.maximum(pk, up[:x.shape[1] * 4].reshape(-1, 4).max(axis=1))
    req = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    w = max(3, int(look * SR))
    g = minimum_filter1d(req, 2 * w + 1)
    g = uniform_filter1d(g, w + 1)
    g = np.minimum(g, req)
    return x * g, 20 * math.log10(float(np.min(g)))


# ============================================================== gamelan synthesis
# partials: (ratio, amplitude, decay seconds at 440 Hz)
METAL = {
    "saron": dict(p=[(1, 1, 2.0), (2.76, 0.30, 0.6), (5.18, 0.10, 0.22), (8.6, 0.035, 0.1)],
                  att=0.0008, click=0.30, cf=(2500, 6000), beat=3.0, max=3.2, glide=0.0),
    "demung": dict(p=[(1, 1, 2.8), (2.71, 0.26, 0.8), (5.05, 0.07, 0.3)],
                   att=0.0012, click=0.22, cf=(1500, 4000), beat=2.2, max=4.5, glide=0.0),
    "peking": dict(p=[(1, 1, 1.1), (2.82, 0.28, 0.35), (5.3, 0.07, 0.12)],
                   att=0.0006, click=0.40, cf=(4000, 9000), beat=4.5, max=2.0, glide=0.0),
    "gender": dict(p=[(1, 1, 3.6), (2.0, 0.04, 1.5), (2.74, 0.10, 0.7), (4.4, 0.03, 0.25)],
                   att=0.005, click=0.05, cf=(1200, 3000), beat=1.8, max=5.0, glide=0.0),
    "bonang": dict(p=[(1, 1, 1.25), (1.52, 0.07, 0.45), (2.03, 0.30, 0.6), (2.88, 0.16, 0.3), (4.15, 0.06, 0.16)],
                   att=0.0015, click=0.22, cf=(1800, 5000), beat=3.4, max=2.4, glide=0.006),
    "kenong": dict(p=[(1, 1, 3.2), (2.03, 0.22, 1.3), (2.94, 0.10, 0.6), (4.2, 0.04, 0.3)],
                   att=0.004, click=0.10, cf=(900, 2500), beat=1.4, max=5.0, glide=0.004),
    "kethuk": dict(p=[(1, 1, 0.16), (2.1, 0.25, 0.07), (3.02, 0.08, 0.04)],
                   att=0.002, click=0.25, cf=(700, 2000), beat=0.0, max=0.45, glide=0.01),
    "bell": dict(p=[(1, 1, 3.0), (2.0, 0.5, 2.0), (2.76, 0.35, 1.2), (5.4, 0.2, 0.5), (8.9, 0.08, 0.25)],
                 att=0.0006, click=0.2, cf=(5000, 12000), beat=2.5, max=4.0, glide=0.0),
}
_CACHE = {}


def _phase(f, t, glide=0.0, tau=0.025):
    return 2 * np.pi * f * (t + glide * tau * (1 - np.exp(-t / tau)))


def metal_note(kind, f, vel, hold, seed, beat=None):
    key = (kind, round(f, 2), round(vel, 2), None if hold is None else round(hold, 2), beat)
    if key in _CACHE:
        return _CACHE[key]
    P = METAL[kind]
    rng = np.random.default_rng(seed)
    dk = (440.0 / f) ** 0.35
    length = P["max"] * min(2.0, dk)
    if hold is not None:
        length = min(length, hold + 0.25)
    n = max(64, int(length * SR))
    t = np.arange(n) / SR
    bt = (P["beat"] if beat is None else beat) * rng.uniform(0.85, 1.15)
    ya = np.zeros(n)
    yb = np.zeros(n)
    for r, a, T in P["p"]:
        fr = f * r
        if fr > 15000:
            continue
        amp = a * (vel ** 0.9 if r > 1.3 else 1.0)
        env = np.exp(-t / (T * dk))
        ya += amp * env * np.sin(_phase(fr, t, P["glide"]) + rng.uniform(0, 6.28))
        yb += amp * env * np.sin(_phase(fr + bt * math.sqrt(r), t, P["glide"]) + rng.uniform(0, 6.28))
    att = 1 - np.exp(-t / P["att"])
    ya *= att
    yb *= att
    nc = min(n, int(0.03 * SR))
    click = filt(sos_bp(*P["cf"]), rng.standard_normal(nc)) * np.exp(-np.arange(nc) / SR / 0.0035)
    click *= P["click"] * vel * 2.5
    ya[:nc] += click
    yb[:nc] += click * 0.8
    if hold is not None:
        damp = np.where(t < hold, 1.0, np.exp(-(t - hold) / 0.05))
        ya *= damp
        yb *= damp
    y = np.stack([ya + 0.35 * yb, 0.35 * ya + yb]) / 1.35 * (vel ** 1.3) * 0.5
    _CACHE[key] = y
    return y


GONGS = {
    # (ratio, amp, decay s, beat Hz)
    "gong": dict(p=[(1.0, 1.0, 7.0, 0.75), (1.47, 0.10, 2.0, 0.0), (2.0, 0.55, 4.0, 1.1), (2.32, 0.10, 1.6, 0.0),
                    (2.99, 0.32, 2.6, 1.6), (3.56, 0.08, 1.2, 0.0), (4.08, 0.12, 1.5, 2.0), (5.2, 0.05, 0.9, 0.0),
                    (6.4, 0.03, 0.6, 0.0)], bloom=0.18, dur=11.0, thump=160),
    "kempul": dict(p=[(1.0, 1.0, 3.2, 2.2), (1.5, 0.08, 1.0, 0.0), (2.0, 0.45, 1.8, 2.6), (2.94, 0.2, 0.9, 0.0),
                      (4.1, 0.1, 0.5, 0.0), (5.5, 0.04, 0.3, 0.0)], bloom=0.05, dur=5.0, thump=300),
}


def gong_note(kind, f0, vel, seed):
    key = (kind, round(f0, 2), round(vel, 2), seed % 4)
    if key in _CACHE:
        return _CACHE[key]
    G = GONGS[kind]
    rng = np.random.default_rng(seed % 4 + 11)
    n = int(G["dur"] * SR)
    t = np.arange(n) / SR
    y = np.zeros((2, n))
    for idx, (r, a, T, bt) in enumerate(G["p"]):
        f = f0 * r
        env = np.exp(-t / T)
        if idx == 0:
            env = env * (1 - 0.6 * np.exp(-t / G["bloom"]))
        amp = a * (vel ** 0.8 if r > 1.2 else 1.0)
        for c in range(2):
            ph = rng.uniform(0, 6.28, 2)
            if bt:
                s = np.sin(2 * np.pi * f * t + ph[0]) + 0.85 * np.sin(2 * np.pi * (f + bt * (1 + 0.1 * c)) * t + ph[1])
            else:
                s = np.sin(2 * np.pi * f * t + ph[0])
            y[c] += amp * env * s
    y *= 1 - np.exp(-t / 0.01)
    nt = int(0.1 * SR)
    th = filt(sos_lp(G["thump"], 2), rng.standard_normal(nt)) * np.exp(-np.arange(nt) / SR / 0.025) * 3.0
    y[:, :nt] += th
    y = y / (np.max(np.abs(y)) + 1e-9) * vel
    _CACHE[key] = y
    return y


def membrane(f_start, f_end, glide, decay, modes=((1, 1.0), (1.59, 0.35), (2.14, 0.18), (2.3, 0.12)), n_s=0.8):
    n = int(n_s * SR)
    t = np.arange(n) / SR
    # frequency glides exponentially from f_start to f_end
    fr = f_end + (f_start - f_end) * np.exp(-t / glide)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    y = np.zeros(n)
    for r, a in modes:
        y += a * np.sin(ph * r) * np.exp(-t / (decay / r ** 0.7))
    return y * (1 - np.exp(-t / 0.0008))


def noise_burst(n_s, lo, hi, decay, seed):
    rng = np.random.default_rng(seed)
    n = int(n_s * SR)
    return filt(sos_bp(lo, hi), rng.standard_normal(n)) * np.exp(-np.arange(n) / SR / decay)


def kendang_note(ch, vel, seed):
    key = ("kendang", ch, round(vel, 2), seed % 6)
    if key in _CACHE:
        return _CACHE[key]
    s = seed % 6
    j = 1 + 0.02 * (s - 3) / 3
    L = int(0.9 * SR)
    y = np.zeros(L)

    def add(z, g=1.0):
        m = min(L, len(z))
        y[:m] += g * z[:m]

    if ch in "Dd":
        add(membrane(118 * j, 84 * j, 0.05, 0.28), 1.0)
        add(noise_burst(0.05, 300, 1500, 0.008, s), 0.35)
    if ch == "B":      # ciblon "dhe": pitch bends up as the heel presses the head
        add(membrane(78 * j, 112 * j, 0.09, 0.3), 1.0)
        add(noise_burst(0.04, 300, 1400, 0.008, s), 0.3)
    if ch in "Tt":
        add(noise_burst(0.06, 1800, 6500, 0.010 if ch == "T" else 0.006, s + 1), 1.2 if ch == "T" else 0.8)
        add(membrane(470 * j, 420 * j, 0.01, 0.035, modes=((1, 1.0), (1.59, 0.5), (2.3, 0.3))), 0.8)
    if ch == "k":
        add(noise_burst(0.04, 2000, 6000, 0.005, s + 2), 0.35)
        add(membrane(430 * j, 400 * j, 0.01, 0.02, modes=((1, 1.0), (1.59, 0.4))), 0.3)
    if ch in "OP":
        add(membrane(300 * j, 262 * j, 0.03, 0.22, modes=((1, 1.0), (1.59, 0.25), (2.14, 0.12))), 0.8)
        add(noise_burst(0.03, 1000, 4000, 0.004, s + 3), 0.4)
    if ch == "P":
        add(membrane(110 * j, 82 * j, 0.05, 0.3), 0.9)
    g = {"D": 1.0, "d": 0.55, "B": 0.9, "T": 0.9, "t": 0.6, "k": 0.5, "O": 0.8, "P": 1.0}[ch] * vel
    y = np.tanh(y * 1.2) * g * 0.6
    out = np.stack([y, y])
    _CACHE[key] = out
    return out


def fx_note(kind, vel, seed, length=1.0, f=None):
    rng = np.random.default_rng(seed)
    if kind == "boom":       # cinematic sub hit
        n = int(2.5 * SR)
        t = np.arange(n) / SR
        fr = 34 + 60 * np.exp(-t / 0.06)
        y = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.7)
        y += filt(sos_lp(400, 2), rng.standard_normal(n)) * np.exp(-t / 0.08) * 1.5
        y += filt(sos_bp(1500, 6000), rng.standard_normal(n)) * np.exp(-t / 0.02) * 0.3
        y = np.tanh(y * 1.5)
        return np.stack([y, y]) * vel
    if kind == "riser":      # noise sweep that ends exactly at the event end
        n = int(length * SR)
        t = np.arange(n) / SR / length
        out = np.zeros((2, n))
        for c in range(2):
            x = rng.standard_normal(n)
            pos = np.log(250 * (8000 / 250) ** (t ** 1.4))
            for fc in np.geomspace(250, 8000, 12):     # crossfaded filter bank = smooth sweep
                w = np.exp(-0.5 * ((np.log(fc) - pos) / 0.35) ** 2)
                out[c] += filt(sos_bp(fc * 0.8, min(18000, fc * 1.25)), x) * w
            out[c] *= t ** 2.2
        return out * vel * 3
    if kind == "swell":      # reverse cymbal
        n = int(length * SR)
        t = np.arange(n) / SR / length
        x = filt(sos_hp(3000, 2), rng.standard_normal((2, n)))
        return x * t ** 3 * vel * 1.5
    if kind == "drop":       # water drop plink
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        f0 = f or 900
        fr = f0 * (1 + 0.9 * (1 - np.exp(-t / 0.018)))
        y = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.06) * (1 - np.exp(-t / 0.001))
        p = rng.uniform(-0.7, 0.7)
        return np.stack([y * (1 - p), y * (1 + p)]) * 0.5 * vel
    raise ValueError(kind)


def render_lane(song, name, lane, total):
    spb = song.spb()
    buf = np.zeros((2, total))
    ev = sorted(lane.ev, key=lambda e: e[0])
    rng = random.Random(zlib.crc32((song.name + name).encode()))
    for i, (b, what, vel, extra) in enumerate(ev):
        t = b * spb + rng.uniform(-0.004, 0.004) * (lane.inst not in ("gong", "kempul"))
        t = max(0.0, t)
        v = max(0.05, min(1.2, vel * rng.uniform(0.93, 1.05)))
        seed = rng.randrange(1 << 30)
        inst = lane.inst
        if inst in METAL:
            f = song.hz(what)
            hold = None
            if lane.ring is not None and i + 1 < len(ev):
                hold = max(0.05, (ev[i + 1][0] - b) * spb + lane.ring)
            y = metal_note(inst, f, round(v, 2), hold, seed, lane.beat)
        elif inst in GONGS:
            y = gong_note(inst, song.hz(what), round(v, 2), seed)
        elif inst == "kendang":
            y = kendang_note(what, round(v, 2), seed)
        elif inst == "fx":
            y = fx_note(what, v, seed, **extra)
            if what in ("riser", "swell"):
                t -= y.shape[1] / SR     # ends on the beat
                if t < 0:
                    y = y[:, int(-t * SR):]
                    t = 0.0
        else:
            raise ValueError(inst)
        s = int(t * SR)
        m = min(y.shape[1], total - s)
        if m > 0:
            buf[:, s:s + m] += y[:, :m]
    return buf


# ============================================================== MIDI + FluidSynth
def write_midi(song, part, path):
    rng = random.Random(zlib.crc32((song.name + "/" + id_name(song, part)).encode()))
    spb = song.spb()

    def tk(b):
        return max(0, int(round(b * TPB)))

    ev = [(0, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm)))]
    free = [c for c in range(16) if c != 9]
    chans = {}         # bend (cents) -> channel
    placed = []
    for t, d, m, v, fl in part.notes:
        if part.drum:
            ch, key, bend = 9, int(round(m)), 0
        else:
            key = int(round(m))
            bend = int(round((m - key) * 100))
            if bend not in chans:
                if not free:
                    bend = min(chans, key=lambda b: abs(b - bend))
                else:
                    chans[bend] = free.pop(0)
            ch = chans[bend]
        st = t + max(-2.5, min(2.5, rng.gauss(0, 1))) * part.jitter / spb
        vv = int(max(1, min(127, v + rng.uniform(-part.velrand, part.velrand))))
        gate = fl.get("gate", part.gate)
        on = tk(st)
        off = on + max(10, int(round(d * gate * TPB)))
        placed.append([on, off, ch, key, vv, fl, bend])
    used = sorted({p[2] for p in placed}) or [9 if part.drum else 0]
    for ch in used:
        if part.drum:
            ev.append((0, 0, mido.Message("program_change", channel=9, program=part.program)))
        else:
            ev.append((0, 0, mido.Message("control_change", channel=ch, control=0, value=part.bank)))
            ev.append((0, 0, mido.Message("program_change", channel=ch, program=part.program)))
            for c, val in ((101, 0), (100, 0), (6, 2), (38, 0)):
                ev.append((0, 1, mido.Message("control_change", channel=ch, control=c, value=val)))
        for c, val in {7: 100, 10: 64, 11: 127, 91: 0, 93: 0, 64: 0}.items():
            ev.append((0, 1, mido.Message("control_change", channel=ch, control=c, value=val)))
    for bend, ch in chans.items():
        ev.append((0, 1, mido.Message("pitchwheel", channel=ch, pitch=int(8191 * bend / 200))))
    for t, c, v in part.ccs:
        for ch in used:
            ev.append((tk(t), 2, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, v)))))
    placed.sort(key=lambda x: (x[0], x[3]))
    last = {}
    for nt in placed:
        k = (nt[2], nt[3])
        prev = last.get(k)
        if prev is not None and prev[1] > nt[0] - 1:
            prev[1] = max(prev[0] + 6, nt[0] - 1)
        last[k] = nt
    for on, off, ch, key, vv, fl, bend in placed:
        if fl.get("scoop"):
            depth = bend - 70
            ev.append((max(0, on - 1), 2, mido.Message("pitchwheel", channel=ch, pitch=int(8191 * depth / 200))))
            span = int(0.16 / spb * TPB)
            for k in range(1, 9):
                cur = bend + (depth - bend) * (1 - k / 8) ** 2
                ev.append((on + span * k // 8, 2, mido.Message("pitchwheel", channel=ch, pitch=int(8191 * cur / 200))))
        ev.append((on, 3, mido.Message("note_on", channel=ch, note=key, velocity=vv)))
        ev.append((off, 1, mido.Message("note_off", channel=ch, note=key, velocity=0)))
    end = tk(song.beats + TAIL / spb + 4)
    ev.append((end, 2, mido.Message("control_change", channel=used[0], control=110, value=0)))
    ev.sort(key=lambda e: (e[0], e[1]))
    mf = mido.MidiFile(ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mf.tracks.append(tr)
    now = 0
    for tick, _, msg in ev:
        tr.append(msg.copy(time=tick - now))
        now = tick
    mf.save(path)


def id_name(song, part):
    for k, v in song.parts.items():
        if v is part:
            return k
    return "?"


def soundfont():
    for s in SOUNDFONTS:
        if os.path.exists(s):
            return s
    sys.exit("no SoundFont (apt install musescore-general-soundfont or fluid-soundfont-gm)")


def render_part(song, name, part, wdir, sfont):
    mid = os.path.join(wdir, name + ".mid")
    wav = os.path.join(wdir, name + ".wav")
    write_midi(song, part, mid)
    subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.5", "-r", str(SR), "-R", "0", "-C", "0",
                    "-o", "synth.dynamic-sample-loading=1", "-o", "audio.file.format=float",
                    "-o", "synth.polyphony=512", "-F", wav, sfont, mid],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    x, sr = sf.read(wav, dtype="float32", always_2d=True)
    os.remove(wav)
    return np.ascontiguousarray(x.T).astype(np.float64)


# ============================================================== mix + master
def process_stem(buf, o, spb):
    if o.hp:
        buf = filt(sos_hp(o.hp), buf)
    if o.lp:
        buf = filt(sos_lp(o.lp), buf)
    if getattr(o, "shelf", None):
        lo, hi = o.shelf
        if lo:
            buf = filt(biquad_shelf(250, lo, high=False), buf)
        if hi:
            buf = filt(biquad_shelf(4000, hi, high=True), buf)
    if getattr(o, "drive", 0):
        pk = np.max(np.abs(buf)) + 1e-9
        buf = np.tanh(buf / pk * (1 + 4 * o.drive)) * pk
        buf = filt(sos_lp(6500), buf)
    if o.echo:
        beats, fb, mix = o.echo
        buf = echo(buf, beats * spb, fb, mix)
    if o.width != 1.0 or o.pan:
        buf = pan_width(buf, o.pan, o.width)
    return buf


def mixdown(song, stems):
    spb = song.spb()
    body = int(round(song.beats * spb * SR))
    total = body + int(TAIL * SR)
    dry = np.zeros((2, total))
    send = np.zeros((2, total))
    report = []
    for name in list(stems):
        x = stems.pop(name)
        o = song.parts.get(name) or song.lanes.get(name)
        buf = np.zeros((2, total))
        m = min(total, x.shape[1])
        buf[:, :m] = x[:, :m]
        buf = process_stem(buf, o, spb)
        l0 = lufs(buf)
        if l0 <= -100:
            continue
        buf *= 10 ** ((o.level - l0) / 20)
        dry += buf
        send += buf * o.rev
        report.append(f"{name}:{o.level:+.0f}")
    ir = make_ir(song.rt60, seed=len(song.name))
    wet = reverb(send, ir)
    wet = filt(sos_hp(200), wet)
    wet = filt(sos_lp(7500), wet)
    mix = dry + wet
    if song.loop:
        out = mix[:, :body].copy()
        tail = mix[:, body:]
        k = 0
        while k < tail.shape[1]:
            m = min(body, tail.shape[1] - k)
            out[:, :m] += tail[:, k:k + m]
            k += m
    else:
        out = mix
    print("  stems " + " ".join(report))
    return out


def master(song, x):
    n = x.shape[1]
    pad_n = min(n, int(3 * SR)) if song.loop else 0
    if song.loop:
        y = np.concatenate([x[:, -pad_n:], x, x[:, :pad_n]], axis=1)
    else:
        y = np.concatenate([x, np.zeros((2, int(0.2 * SR)))], axis=1)
    y = filt(sos_hp(30, 2), y)
    y = filt(biquad_shelf(120, -1.0, high=False), y)
    y = filt(biquad_shelf(4000, 1.5, high=True), y)
    if not song.loop and song.max_len:
        m = int(song.max_len * SR)
        y = y[:, :m]
        f = int(1.2 * SR)
        y[:, -f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        n = y.shape[1]
    t = song.target
    l0 = lufs(y[:, pad_n:pad_n + n])
    y *= 10 ** ((t + 2.5 - l0) / 20)
    y, gr = compressor(y, thresh_db=t - 2, ratio=2.0, attack=0.02, release=0.3)
    for _ in range(3):
        l1 = lufs(y[:, pad_n:pad_n + n])
        y *= 10 ** ((t - l1) / 20)
        y, lim = limiter(y)
    if song.loop:
        y = y[:, pad_n:pad_n + n]
    return y, gr


def seam_report(y, bar_s):
    d = np.abs(y[:, 0] - y[:, -1]).max()
    steps = np.abs(np.diff(y, axis=1))
    w = int(0.05 * SR)

    def jump(i):
        z = np.roll(y, -i + w, axis=1)[:, :2 * w]
        a = np.sqrt(np.mean(z[:, :w] ** 2)) + 1e-12
        b = np.sqrt(np.mean(z[:, w:] ** 2)) + 1e-12
        return 20 * math.log10(b / a)

    n = y.shape[1]
    bars = [int(round(k * bar_s * SR)) for k in range(1, int(n / SR / bar_s))]
    others = [jump(i) for i in bars if w < i < n - w]
    return d, float(np.percentile(steps, 99)), jump(0), float(np.median(others)), float(np.max(others))


def encode(y, path, channels=2, q=VORBIS_Q):
    tmp = path + ".tmp.wav"
    sf.write(tmp, y.T.astype(np.float32), SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-map_metadata", "-1", "-c:a", "libvorbis",
                    "-q:a", str(q), "-ar", str(SR), "-ac", str(channels), path], check=True)
    os.remove(tmp)


def overview_png(y, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mono = y.mean(axis=0)
    fig, ax = plt.subplots(2, 1, figsize=(12, 5.2), sharex=True, gridspec_kw={"height_ratios": [1, 2]})
    blk = max(1, len(mono) // 2400)
    m = mono[:blk * (len(mono) // blk)].reshape(-1, blk)
    tt0 = (np.arange(m.shape[0]) + 0.5) * blk / SR
    ax[0].fill_between(tt0, m.min(axis=1), m.max(axis=1), color="#3a7ca5", lw=0)
    ax[0].plot(tt0, np.sqrt(np.mean(m ** 2, axis=1)), color="#f4a259", lw=0.8)
    ax[0].set_ylim(-1, 1)
    ax[0].set_title(title, fontsize=10)
    f, tt, s = signal.spectrogram(mono, SR, nperseg=2048, noverlap=1024)
    ax[1].pcolormesh(tt, f, 10 * np.log10(s + 1e-12), shading="auto", vmin=-120, vmax=-40, cmap="magma")
    ax[1].set_yscale("symlog", linthresh=200)
    ax[1].set_ylim(30, 16000)
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def build(song, png_dir=None):
    wdir = os.path.join(WORK, song.name)
    os.makedirs(wdir, exist_ok=True)
    sfont = soundfont()
    spb = song.spb()
    total = int(round(song.beats * spb * SR)) + int(TAIL * SR)
    parts = {k: p for k, p in song.parts.items() if p.notes}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {k: ex.submit(render_part, song, k, p, wdir, sfont) for k, p in parts.items()}
        stems = {}
        for k, ln in song.lanes.items():
            if ln.ev:
                stems[k] = render_lane(song, k, ln, total)
        for k, f in futs.items():
            stems[k] = f.result()
    x = mixdown(song, stems)
    y, gr = master(song, x)
    prefix = "mus_" if song.loop else "stg_"
    path = os.path.join(OUT, f"{prefix}{song.name}.ogg")
    encode(y, path)
    z, _ = sf.read(path, dtype="float64", always_2d=True)
    z = z.T
    L, tp = lufs(z), true_peak_db(z)
    msg = (f"  {os.path.basename(path)}: {z.shape[1] / SR:.2f}s  {L:.1f} LUFS  TP {tp:.1f} dBTP  comp {gr:.1f} dB  "
           f"{os.path.getsize(path) / 1024:.0f} KB")
    if song.loop:
        d, p99, jump, med, mx = seam_report(z, song.meter * spb)
        msg += (f"\n  seam: |x0-x-1| {d:.4f} (p99 step {p99:.4f}); RMS change across seam {jump:+.1f} dB "
                f"(other bar lines median {med:+.1f}, max {mx:+.1f})")
        if z.shape[1] != y.shape[1]:
            msg += f"  WARNING decoded length {z.shape[1]} != {y.shape[1]}"
    print(msg)
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
        overview_png(z, os.path.join(png_dir, f"{prefix}{song.name}.png"), f"{song.name} {L:.1f} LUFS TP {tp:.1f}")
    if not os.environ.get("MUSIC_KEEP"):
        shutil.rmtree(wdir, ignore_errors=True)
    _CACHE.clear()


# ============================================================== GM programs
FLUTE, PANFLUTE, SHAKU, CHOIR, OOHS, BRASS, HORN, TROMBONE, STR_SLOW, STR_FAST, TREM, PIZZ, CELLO = \
    73, 75, 77, 52, 53, 61, 60, 57, 49, 48, 44, 45, 42
DIST, OVERDRIVE, PICKBASS, FINGBASS, WARMPAD, TAIKO, TIMPANI, FIDDLE, HALO, SWEEP = \
    30, 29, 34, 33, 89, 116, 47, 110, 94, 95
KICK, SNARE, RIM, HAT, OHAT, PHAT, CRASH, CRASH2, RIDE, CHINA, TOM_L, TOM_M, TOM_H, FTOM, SPLASH = \
    36, 38, 37, 42, 46, 44, 49, 57, 51, 52, 45, 47, 50, 41, 55


def gamelan_lanes(song, bal=-24, rev=0.22):
    song.lane("saron", "saron", level=bal, pan=0.12, rev=rev, ring=0.02)
    song.lane("demung", "demung", level=bal - 3, pan=-0.1, rev=rev, ring=0.03)
    song.lane("peking", "peking", level=bal - 3, pan=0.35, rev=rev, ring=0.04)
    song.lane("bonang_a", "bonang", level=bal - 1, pan=-0.45, rev=rev, ring=0.12)
    song.lane("bonang_b", "bonang", level=bal - 1, pan=0.45, rev=rev, ring=0.12, beat=4.2)
    song.lane("kenong", "kenong", level=bal - 3, pan=0.25, rev=rev + 0.1)
    song.lane("kethuk", "kethuk", level=bal - 8, pan=-0.2, rev=rev)
    song.lane("kempul", "kempul", level=bal - 2, pan=-0.3, rev=rev + 0.1)
    song.lane("gong", "gong", level=bal + 1, pan=0.0, width=0.5, rev=rev + 0.1)
    song.lane("kendang", "kendang", level=bal + 2, pan=0.05, rev=0.12)
    song.lane("fx", "fx", level=bal - 2, pan=0.0, rev=0.2)


# ============================================================== the pieces
def song_hub():
    """Pancawati at night: slendro ladrang, gender + suling over a warm drone"""
    s = Song("hub", 62, 96, SLENDRO, [1, 2, 3, 5, 6], tonic=62, rt60=3.2, seed=3)
    s.lane("saron", "saron", level=-31, pan=0.2, rev=0.35, ring=0.05)
    s.lane("demung", "demung", level=-28, pan=-0.15, rev=0.35, ring=0.1)
    s.lane("peking", "peking", level=-33, pan=0.4, rev=0.4, ring=0.2)
    s.lane("gender_r", "gender", level=-24, pan=-0.3, rev=0.4, ring=0.9)
    s.lane("gender_l", "gender", level=-27, pan=0.25, rev=0.4, ring=1.2, beat=1.2)
    s.lane("kenong", "kenong", level=-29, pan=0.3, rev=0.45)
    s.lane("kethuk", "kethuk", level=-36, pan=-0.25, rev=0.3)
    s.lane("kempul", "kempul", level=-28, pan=-0.3, rev=0.45)
    s.lane("gong", "gong", level=-22, width=0.5, rev=0.4)
    s.lane("bell", "bell", level=-36, pan=0.5, rev=0.6, ring=None)
    s.part("drone", WARMPAD, level=-27, rev=0.4, lp=2500, width=1.3)
    s.part("choir", OOHS, level=-31, rev=0.6, width=1.2)
    s.part("suling", FLUTE, level=-22, pan=0.15, rev=0.5, jitter=0.01, gate=1.0)
    A = "3 5 3 2  6 5 3 2  5 6 5 3  2 1 2 6,  3 2 1 2  5 3 2 1  3 5 6 5  3 2 1 2"
    B = "5 6 1' 6  5 3 2 3  5 6 5 3  6 5 3 2  1 2 1 6,  3 5 3 2  6 5 3 2  1 2 1 2"
    C = "6 6 . .  5 6 1' 2'  1' 6 5 3  6 5 3 2  5 3 2 1  3 2 1 6,  2 1 2 6,  3 5 3 2"
    gong_c = s.cents("2", -3)
    for g, (txt, lanes) in enumerate([(A, [("demung", -1, 0.7)]),
                                       (B, [("demung", -1, 0.6), ("saron", 0, 0.5)]),
                                       (C, [("demung", -1, 0.6), ("saron", 0, 0.55)])]):
        b0 = g * 32
        pos = balungan(s, lanes, b0, txt, 1.0, vel=0.6)
        colotomy(s, pos, "ladrang", gong_c, vel=0.8, kethuk=g > 0)
        gender(s, "gender_r", "gender_l", pos, per_beat=2 if g == 0 else 4, oct=0, vel=0.55, seed=g + 10)
        if g == 2:
            peking(s, "peking", pos[::2], oct=1, vel=0.4, pattern="single")
        sustain(s, "drone", b0, 32, [s.cents("2", -2), s.cents("6", -2)], 62)
    # suling over gongan 2 and 3
    line(s, "suling", 32, "-:2 ~3:2 5:1 6:1 5:4 3:1 2:1 ~3:4 -:2 ~6:2 1':1 2':1 1':3 6:1 5:4 -:2", oct=1, vel=78)
    line(s, "suling", 64, "~2':3 1':1 6:2 5:2 ~6:4 -:2 5:1 3:1 2:2 3:1 5:1 ~6:4 3:1 2:1 1:1 ~2:5", oct=1, vel=82)
    # distant choir colour and bell sparkles in the last gongan
    sustain(s, "choir", 64, 16, [s.cents("2", -1), s.cents("6", -1)], 50)
    sustain(s, "choir", 80, 16, [s.cents("1", -1), s.cents("5", -1)], 48)
    for b, tok in [(8.5, "6'"), (40.5, "3'"), (56.5, "5'"), (72.5, "2''"), (88.5, "6'")]:
        hit(s, "bell", b, s.cents(tok, 1), 0.5)
    return s


DAN_GA = "6, 1 2 3  2 1 6, 5,  6, 1 2 3  5 3 2 1"
DAN_GB = "2 3 5 6  5 3 2 3  5 6 1' 6  5 3 2 1"
DAN_GC = ". 3 . 2  . 1 . 6,  . 3 . 5  . 3 . 1"


def song_dandaka():
    """Hutan Dandaka combat: pelog nem lancaran + kendang + distorted riffs, 140 bpm"""
    s = Song("dandaka", 140, 192, PELOG, [1, 2, 3, 5, 6], tonic=64, rt60=1.6, seed=5)
    gamelan_lanes(s, bal=-24)
    s.part("kit", 16, drum=True, level=-19, rev=0.12, width=1.2, jitter=0.003, velrand=5)
    s.part("gtr_l", DIST, level=-24, pan=-0.75, rev=0.08, hp=90, lp=7000, jitter=0.008)
    s.part("gtr_r", DIST, level=-24, pan=0.75, rev=0.08, hp=90, lp=7000, jitter=0.008)
    s.part("bass", PICKBASS, level=-21, rev=0.02, drive=0.5, lp=3000, jitter=0.004)
    s.part("lead", OVERDRIVE, level=-21, pan=0.05, rev=0.3, echo=(0.75, 0.3, 0.22), jitter=0.01, gate=1.0)
    s.part("choir", CHOIR, level=-27, rev=0.5, width=1.3)
    s.part("suling", FLUTE, level=-23, pan=0.2, rev=0.5, echo=(0.75, 0.3, 0.25), gate=1.0)
    gong_c = s.cents("1", -3) + 1200 * 0 + 0
    order = [DAN_GA, DAN_GA, DAN_GA, DAN_GB, DAN_GA, DAN_GB, DAN_GC, DAN_GC, DAN_GA, DAN_GB, DAN_GA, DAN_GB]
    RA = "1_ 1_ . 1_  1_ . 2! -  1_ 1_ . 1_  3! - 2! -"
    RB = "1_ 1_ . 1_  5,! - - .  1_ 1_ . 1_  6,! - 2! -"
    KG = ["D . t T . t D .  D . t T O t T .", "D . t T . t D .  D t T . O O T .",
          "D . t T . t D .  D . t T O t T .", "D . T . D T . T  D D T T O T P ."]
    KF = ["D t T t O t T t  D t D T O O T t", "B . T t B . T t  D T O T D T O T",
          "D t T t O t T t  D t D T O O T t", "P . P . T T T T  O T O T D D D ."]
    for g, txt in enumerate(order):
        b0 = g * 16
        sec = "groove" if g < 2 else "full" if g < 6 else "break" if g < 8 else "climax"
        if sec in ("full", "climax"):
            lanes = [("saron", 0, 0.8), ("demung", -1, 0.7)]
        elif sec == "break":
            lanes = [("demung", -1, 0.6)]
        else:
            lanes = []
        pos = balungan(s, lanes, b0, txt, 1.0, vel=0.75)
        colotomy(s, pos, "lancaran", gong_c, vel=0.9, kethuk=sec != "break")
        if sec != "break":
            imbal(s, "bonang_a", "bonang_b", pos, sub=4, oct=1, vel=0.7, seed=g)
        else:
            imbal(s, "bonang_a", "bonang_b", pos, sub=2, oct=1, vel=0.5, seed=g, every=2)
        if sec in ("full", "climax"):
            peking(s, "peking", pos, oct=2, vel=0.45)
        # kendang
        for bar in range(4):
            pat = (KF if sec == "break" else KG)[bar]
            kendang(s, "kendang", b0 + bar * 4, pat, vel=0.95 if sec != "groove" else 0.85)
        # drums
        for bar in range(4):
            bb = b0 + bar * 4
            last = bar == 3
            if sec == "groove":
                p = {KICK: "x . . . . . x . x . . . . . . .", PHAT: "x . x . x . x . x . x . x . x .",
                     FTOM: ". . . . x . . . . . . . x . . ."}
                if last and g == 1:
                    p = {KICK: "x . . . . . x . x . . . . . . .", SNARE: ". . . . x . . . r r r r X X X X",
                         TOM_L: ". . . . . . . . . . . . . . . ."}
            elif sec in ("full", "climax"):
                p = {KICK: "x . . x . . x . x . . x . . x ." if sec == "full" else "x . x x . . x . x . x x . . x x",
                     SNARE: ". . . . X . . . . . . . X . . .",
                     (HAT if sec == "full" else RIDE): "x . x . x . x . x . x . x . x ."}
                if last:
                    p[SNARE] = ". . . . X . . . X . x x . . . ."
                    p[TOM_M] = ". . . . . . . . . . . . X x . ."
                    p[FTOM] = ". . . . . . . . . . . . . . X x"
            else:  # break: tribal toms
                p = {FTOM: "X . . x . . x . X . . x . . x .", TOM_L: ". . x . . x . . . . x . . x . x",
                     KICK: "x . . . . . . . x . . . . . . ."}
                if g == 7 and bar == 3:
                    p = {SNARE: "r r r r r r r r X X X X X X X X", KICK: "x . . . x . . . x . x . x x x x"}
                if g == 7 and bar >= 2:
                    p.setdefault(SNARE, "o . o . o . o . o o o o x x x x")
            drums(s, "kit", bb, p)
        if sec in ("full", "climax") or (sec == "groove" and g == 1):
            dnote(s, "kit", b0, CRASH, 110, 1)
            if sec == "climax":
                dnote(s, "kit", b0, CHINA, 95, 1)
        # riffs
        if sec in ("full", "climax"):
            for bar in range(4):
                r = RB if bar == 3 else RA
                riff(s, "gtr_l", b0 + bar * 4, r, oct=-2, vel=100, bass="bass", bass_oct=-3)
                riff(s, "gtr_r", b0 + bar * 4, r, oct=-2, vel=98)
        elif sec == "groove":
            for bar in range(4):
                riff(s, "bass", b0 + bar * 4, "1 . . 1  . . 1 .  1 . . 1  . . 2 -", oct=-3, vel=100, chord=False)
        else:
            sustain(s, "bass", b0, 8, [s.cents("1", -3)], 100)
            sustain(s, "bass", b0 + 8, 8, [s.cents("6", -4) + 1200], 100)
            note(s, "gtr_l", b0, 8, s.cents("1", -2), 90)
            note(s, "gtr_l", b0, 8, s.cents("1", -2) + 700, 80)
            note(s, "gtr_r", b0 + 8, 8, s.cents("6", -3), 88)
            note(s, "gtr_r", b0 + 8, 8, s.cents("6", -3) + 700, 78)
    # break: eerie suling + choir, riser into the climax
    line(s, "suling", 96, "~5:3 3:1 2:4 -:2 ~1:2 2:1 3:1 ~2:4 -:2 ~6,:4 1:2 ~2:6", oct=1, vel=84)
    for b0 in (96, 112):
        sustain(s, "choir", b0, 16, [s.cents("1", -1), s.cents("5", -1), s.cents("2", 0)], 64)
    hit(s, "fx", 128, "riser", 0.9, length=4 * s.spb())
    hit(s, "fx", 128, "boom", 1.0)
    hit(s, "fx", 32, "boom", 0.8)
    # climax lead
    lead = ("3:1 5:1 6:2 5:1 3:1 2:2 1:1 2:1 3:4 -:2 5:1 6:1 1':2 6:1 5:1 3:2 2:1 3:1 1:4 -:2 "
            "6:1 1':1 2':2 1':1 6:1 5:2 6:1 5:1 3:4 -:2 2:1 3:1 5:2 3:1 2:1 1:2 6,:1 1:1 1:4 -:2")
    line(s, "lead", 128, lead, oct=0, vel=100)
    for b0 in range(128, 192, 16):
        sustain(s, "choir", b0, 16, [s.cents("1", -1), s.cents("5", -1)], 58)
    return s


MUA_HA = "2 3 2 7,  2 3 2 6,  7, 2 3 5  3 2 7, 6,"
MUA_HB = "3 5 6 7  6 5 3 2  3 5 3 2  7, 2 7, 6,"
MUA_HC = ". 7, . 6,  . 2 . 3  . 5 . 3  . 2 . 6,"


def song_muara():
    """Muara Kalimas combat: pelog barang, rippling gender with echo, pizzicato ostinato"""
    s = Song("muara", 132, 176, PELOG, [2, 3, 5, 6, 7], tonic=66.0 - 7.84 + 0.0, rt60=2.0, seed=7)
    gamelan_lanes(s, bal=-25)
    s.lane("gender_r", "gender", level=-25, pan=-0.35, rev=0.35, ring=0.4, echo=(0.75, 0.4, 0.35))
    s.lane("gender_l", "gender", level=-29, pan=0.35, rev=0.35, ring=0.6, beat=1.1)
    s.lane("drops", "fx", level=-30, rev=0.5, echo=(0.5, 0.35, 0.3))
    s.part("kit", 16, drum=True, level=-20, rev=0.14, width=1.2, jitter=0.003)
    s.part("taiko", TAIKO, level=-22, rev=0.3, jitter=0.004)
    s.part("pizz", PIZZ, level=-24, pan=0.3, rev=0.25, jitter=0.006)
    s.part("trem", TREM, level=-25, rev=0.4, width=1.3)
    s.part("gtr", DIST, level=-27, pan=-0.6, rev=0.08, hp=100, lp=6500)
    s.part("bass", PICKBASS, level=-21, drive=0.55, lp=2800, jitter=0.004)
    s.part("lead", STR_FAST, level=-22, pan=-0.1, rev=0.35, width=1.2, gate=1.0)
    s.part("flute", FLUTE, level=-25, pan=0.25, rev=0.4, gate=1.0)
    s.part("choir", CHOIR, level=-28, rev=0.5, width=1.3)
    s.part("brass", BRASS, level=-25, rev=0.35)
    gong_c = s.cents("6", -3)
    order = [MUA_HA, MUA_HA, MUA_HA, MUA_HB, MUA_HA, MUA_HB, MUA_HC, MUA_HC, MUA_HA, MUA_HB, MUA_HB]
    K1 = ["d . t . O . t k  d . t . O t T .", "d . t . O . t k  d t T . O O T ."]
    K2 = ["D . t T . t D t  O . t T D t T .", "D . t T . t D t  O t T . O O T t",
          "D . t T . t D t  O . t T D t T .", "D t T t O t T t  D D T T O T P ."]
    K3 = ["B . T . B . T .  D t O t D t O t", "B . T . B . T t  D T O T P . P ."]
    ost = "6,, 6, 3, 6, 7,, 6, 2, 7,"
    for g, txt in enumerate(order):
        b0 = g * 16
        sec = "pulse" if g < 2 else "full" if g < 6 else "break" if g < 8 else "climax"
        lanes = [("saron", 0, 0.8), ("demung", -1, 0.7)] if sec in ("full", "climax") else \
            [("demung", -1, 0.55)] if sec == "break" else []
        pos = balungan(s, lanes, b0, txt, 1.0, vel=0.75)
        colotomy(s, pos, "lancaran", gong_c, vel=0.9, kethuk=sec != "break")
        gender(s, "gender_r", "gender_l", pos, per_beat=4, oct=0, vel=0.5 if sec != "pulse" else 0.6,
               seed=g + 40, tpls=RIPPLE_T, left=sec in ("pulse", "break"))
        if sec in ("full", "climax"):
            imbal(s, "bonang_a", "bonang_b", pos, sub=4, oct=0, vel=0.6, seed=g + 7)
            peking(s, "peking", pos, oct=1, vel=0.4)
        for bar in range(4):
            k = K1 if sec == "pulse" else K3 if sec == "break" else K2
            kendang(s, "kendang", b0 + bar * 4, k[bar % len(k)], vel=0.9)
        # bass pulse
        if sec != "break":
            for bar in range(4):
                bt = "6_ 6_ 6_ 6_  6_ 6_ 7! -  6_ 6_ 6_ 6_  2'! - 7! -" if sec != "pulse" else \
                     "6 . 6 .  6 . 6 .  6 . 6 .  7 - 6 ."
                riff(s, "gtr" if sec != "pulse" else "bass", b0 + bar * 4, bt, oct=-2 if sec != "pulse" else -3,
                     vel=92, bass="bass" if sec != "pulse" else None, bass_oct=-3)
        else:
            sustain(s, "bass", b0, 16, [s.cents("6", -3)], 96)
        # pizzicato ostinato
        if sec in ("full", "climax"):
            for bar in range(0, 4, 2):
                toks, _ = grid(ost, 0.5)
                for rep in range(2):
                    for t, d, tok in toks:
                        note(s, "pizz", b0 + bar * 4 + rep * 4 + t, 0.5, s.cents(tok), 84)
        # drums
        for bar in range(4):
            bb = b0 + bar * 4
            last = bar == 3
            if sec == "full" or sec == "climax":
                p = {KICK: "x . . . . . x . . . x . . . . ." if sec == "full" else "x . . x . . x . . . x . x . . .",
                     SNARE: ". . . . X . . . . . . . X . . o", HAT: "x x x o x x x o x x x o x x x o"}
                if last:
                    p[SNARE] = ". . . . X . . . x x X x X X X X"
                drums(s, "kit", bb, p)
                note(s, "taiko", bb, 1, s.cents("6", -2), 100)
            elif sec == "pulse":
                drums(s, "kit", bb, {RIDE: "x . x . x . x . x . x . x . x .", KICK: "x . . . . . . . x . . . . . . ."},
                      vel=0.8)
            else:
                for off, v in ((0, 115), (1.5, 90), (2, 100), (3, 80), (3.5, 95)):
                    note(s, "taiko", bb + off, 1, s.cents("6", -2), v)
        if sec in ("full", "climax"):
            dnote(s, "kit", b0, CRASH, 105, 1)
            sustain(s, "brass", b0, 1.5, [s.cents("6", -1), s.cents("6", 0), s.cents("3", 1)], 100)
    # water drops sprinkled (pentatonic pitches)
    rng = random.Random(99)
    for k in range(70):
        b = rng.uniform(0, 176)
        hit(s, "drops", b, "drop", rng.uniform(0.3, 0.8), f=s.hz(s.cents(rng.choice("23567"), 1)))
    # break: tremolo strings rising, low choir, riser
    swell(s, "trem", 96, 27, 40, 120)
    for b0, ch in ((96, ["6,", "7,", "2"]), (104, ["6,", "2", "3"]), (112, ["7,", "3", "5"]), (120, ["6,", "3", "6"])):
        sustain(s, "trem", b0, 8, [s.cents(t, 0) for t in ch], 80)
    for b0 in (96, 112):
        sustain(s, "choir", b0, 16, [s.cents("6", -1), s.cents("3", 0)], 66)
    hit(s, "fx", 128, "riser", 0.9, length=4 * s.spb())
    hit(s, "fx", 128, "boom", 1.0)
    swell(s, "trem", 124, 4, 127, 40)
    # climax lead: strings + flute an octave up
    lead = ("6,:1 7,:1 2:2 3:2 2:1 7,:1 6,:4 -:2 2:1 3:1 5:3 6:1 5:2 3:2 2:4 -:4 "
            "3:1 5:1 6:2 7:2 6:1 5:1 3:4 2:1 7,:1 6,:2")
    line(s, "lead", 128, lead, oct=0, vel=100)
    line(s, "flute", 128, lead, oct=1, vel=90)
    return s


BOSS_G = ["1 2 1 7,  1 2 3 2  4 3 2 1  7, 6, 7, 1", "3 4 5 4  3 2 1 2  3 4 3 2  1 7, 6, 1",
          "1 . 1 .  7, . 6, .  1 . 2 .  3 . 1 ."]


def song_boss():
    """Sura & Baya: pelog with the tritone '4', 150 bpm, double kick, choir + brass, gong ageng"""
    s = Song("boss", 150, 192, PELOG, [1, 2, 3, 5, 6], tonic=62, rt60=2.0, seed=11)
    gamelan_lanes(s, bal=-25)
    s.part("kit", 16, drum=True, level=-18, rev=0.14, width=1.2, jitter=0.002, velrand=4)
    s.part("orch", 48, drum=True, level=-24, rev=0.35, width=1.2)
    s.part("taiko", TAIKO, level=-21, rev=0.3, jitter=0.003)
    s.part("gtr_l", DIST, level=-23, pan=-0.8, rev=0.07, hp=90, lp=7000, jitter=0.006)
    s.part("gtr_r", DIST, level=-23, pan=0.8, rev=0.07, hp=90, lp=7000, jitter=0.006)
    s.part("bass", PICKBASS, level=-20, drive=0.6, lp=3000, jitter=0.003)
    s.part("choir", CHOIR, level=-22, rev=0.45, width=1.3, gate=1.0)
    s.part("brass", BRASS, level=-22, rev=0.35, width=1.2, gate=1.0)
    s.part("lowbrass", TROMBONE, level=-25, rev=0.35, gate=1.0)
    s.part("strings", STR_FAST, level=-26, rev=0.3, width=1.3)
    gong_c = s.cents("3", -3)
    RA = "1_ 1_ 1_ 1_  2! - 1_ 1_  4! - - 1_  3! - 2! -"
    RB = "1_ . 1_ 1_  7,! - 1_ .  6,! - 1_ 1_  5,! - 4,! -"
    # sections by gongan (16 beats): intro, A x3, B x4, C x2, D x2
    secs = ["intro", "A", "A", "A", "B", "B", "B", "B", "C", "C", "D", "D"]
    KA = ["D t T t D t T t  O t D T O t T t", "D t T t D t T t  O O T T D D T t",
          "D t T t D t T t  O t D T O t T t", "P . P . T T T T  O T O T D D D D"]
    for g, sec in enumerate(secs):
        b0 = g * 16
        txt = BOSS_G[2] if sec in ("intro", "C") else BOSS_G[g % 2]
        lanes = [("saron", 0, 0.85), ("demung", -1, 0.7)] if sec in ("A", "B", "D") else [("demung", -1, 0.6)]
        pos = balungan(s, lanes, b0, txt, 1.0, vel=0.8)
        colotomy(s, pos, "lancaran", gong_c, vel=1.0, kethuk=sec in ("A", "B", "D"))
        if sec in ("A", "B", "D"):
            imbal(s, "bonang_a", "bonang_b", pos, sub=4, oct=1, vel=0.72, seed=g + 3)
            peking(s, "peking", pos, oct=2, vel=0.45)
        for bar in range(4):
            kendang(s, "kendang", b0 + bar * 4, KA[bar], vel=1.0 if sec != "intro" else 0.8)
        for bar in range(4):
            bb = b0 + bar * 4
            last = bar == 3
            if sec in ("A", "D"):
                p = {KICK: "x x x x x x x x x x x x x x x x", SNARE: ". . . . X . . . . . . . X . . .",
                     CHINA: "x . x . x . x . x . x . x . x ."}
                if last:
                    p[SNARE] = ". . . . X . x x X x X x X X X X"
            elif sec == "B":
                p = {KICK: "x . . x x . . x x . . x x . x x", SNARE: ". . . . X . . . . . . . X . . .",
                     RIDE: "x . x . x . x . x . x . x . x ."}
                if last:
                    p[TOM_M] = ". . . . . . . . X x X x . . . ."
                    p[FTOM] = ". . . . . . . . . . . . X X X X"
            elif sec == "C":
                p = {KICK: "x . . . . . . . x . . . . . . .", SNARE: ". . . . . . . . X . . . . . . ."}
                if g == 9 and last:
                    p = {SNARE: "r r r r r r r r X X X X X X X X", KICK: "x . x . x . x . x x x x x x x x"}
            else:  # intro
                p = {FTOM: "X . . . . . . . X . . . . . . ." if bar < 3 else "X . X . X X X X X X X X r r r r",
                     KICK: "X . . . . . . . X . . . . . . ."}
            drums(s, "kit", bb, p)
            if sec in ("B", "C", "intro"):
                for off, v in ((0, 118), (1.5, 96), (2, 108), (3, 90)) if sec != "C" else ((0, 120), (2, 100)):
                    note(s, "taiko", bb + off, 1, s.cents("1", -2), v)
        dnote(s, "kit", b0, CRASH, 118, 1)
        dnote(s, "orch", b0, 52, 110, 2)      # orchestra kit crash
        hit(s, "fx", b0, "boom", 1.0 if sec in ("intro", "C") or g == 4 else 0.6)
        # guitars / bass
        if sec in ("A", "B", "D"):
            for bar in range(4):
                r = RB if bar % 2 else RA
                riff(s, "gtr_l", b0 + bar * 4, r, oct=-2, vel=102, bass="bass", bass_oct=-3)
                riff(s, "gtr_r", b0 + bar * 4, r, oct=-2, vel=100)
        else:
            for k in range(4 if sec == "C" else 2):
                d = 16 / (4 if sec == "C" else 2)
                c = s.cents("1" if k % 2 == 0 else "2", -2)
                for part in ("gtr_l", "gtr_r"):
                    note(s, part, b0 + k * d, d, c, 100)
                    note(s, part, b0 + k * d, d, c + 700, 90)
                note(s, "bass", b0 + k * d, d, c - 1200, 100)
        # brass stabs on gong + choir chord
        chord = [s.cents("1", -1), s.cents("5", -1), s.cents("1", 0), s.cents("3", 0)]
        sustain(s, "brass", b0, 2, chord, 112)
        sustain(s, "lowbrass", b0, 2, [s.cents("1", -2), s.cents("5", -2)], 110)
        if sec in ("intro", "C"):
            sustain(s, "choir", b0, 16, [s.cents("1", -1), s.cents("2", -1), s.cents("5", -1)], 90)
            sustain(s, "lowbrass", b0 + 8, 8, [s.cents("1", -2), s.cents("4", -2)], 92)
    # choir + brass melody in B (64 beats) and first half again in D
    mel = ("1:2 2:2 3:4 5:2 4:2 3:4 2:2 3:2 1:4 7,:2 6,:2 1:4 "
           "5:2 6:2 7:4 6:2 5:2 4:4 3:2 2:2 1:8 -:4")
    line(s, "choir", 64, mel, oct=0, vel=100)
    line(s, "brass", 64, mel, oct=-1, vel=104)
    line(s, "strings", 64, mel, oct=1, vel=92)
    half = "1:2 2:2 3:4 5:2 4:2 3:4 2:2 3:2 1:4 7,:2 6,:2 1:4"
    line(s, "choir", 160, half, oct=0, vel=104)
    line(s, "brass", 160, half, oct=-1, vel=108)
    swell(s, "strings", 128, 32, 50, 120)
    for b0 in (128, 136, 144, 152):
        sustain(s, "strings", b0, 8, [s.cents("1", 0), s.cents("2", 0), s.cents("4", 0)], 80)
    hit(s, "fx", 160, "riser", 1.0, length=4 * s.spb())
    hit(s, "fx", 192, "riser", 0.8, length=2 * s.spb())
    return s


def song_title():
    """title: heroic horn over gender and drone, then a melancholic suling answer (slendro)"""
    s = Song("title", 76, 80, SLENDRO, [1, 2, 3, 5, 6], tonic=62, rt60=2.8, seed=13)
    gamelan_lanes(s, bal=-27, rev=0.3)
    s.lane("gender_r", "gender", level=-24, pan=-0.3, rev=0.4, ring=0.8)
    s.lane("gender_l", "gender", level=-27, pan=0.3, rev=0.4, ring=1.0, beat=1.3)
    s.part("drone", WARMPAD, level=-27, rev=0.4, lp=3000, width=1.3)
    s.part("horn", HORN, level=-20, pan=-0.1, rev=0.45, gate=1.0)
    s.part("strings", STR_SLOW, level=-23, rev=0.45, width=1.3, gate=1.0)
    s.part("cello", CELLO, level=-24, pan=0.2, rev=0.4, gate=1.0)
    s.part("suling", FLUTE, level=-21, pan=0.15, rev=0.5, gate=1.0)
    s.part("taiko", TAIKO, level=-25, rev=0.35)
    s.part("choir", OOHS, level=-28, rev=0.5, width=1.3)
    gong_c = s.cents("5", -3)
    bal = ["2 1 2 6,  3 5 6 1'  6 5 3 2  5 3 2 1",
           "3 5 3 2  5 6 5 3  6 5 3 2  1 2 1 6,", "2 3 5 6  1' 6 5 3  6 5 3 2  3 2 1 2",
           "5 3 2 1  3 2 1 6,  2 1 2 6,  3 5 3 2", "6 5 3 2  5 3 2 1  2 1 6, 5,  1 2 1 6,"]
    for g, txt in enumerate(bal):
        b0 = g * 16
        lanes = [("demung", -1, 0.6)] + ([("saron", 0, 0.55)] if 1 <= g <= 2 else [])
        pos = balungan(s, lanes, b0, txt, 1.0, vel=0.65)
        colotomy(s, pos, "ketawang", gong_c, vel=0.85, kethuk=g > 0)
        gender(s, "gender_r", "gender_l", pos, per_beat=2 if g == 0 else 4, vel=0.5, seed=g + 70)
        sustain(s, "drone", b0, 16, [s.cents("6", -2), s.cents("2", -2)], 64)
        if 1 <= g <= 2:
            kendang(s, "kendang", b0, "D . . t . . O .  D . t . O . T .", 0.6)
            kendang(s, "kendang", b0 + 4, "D . . t . . O .  D t T . O O T .", 0.6)
            kendang(s, "kendang", b0 + 8, "D . . t . . O .  D . t . O . T .", 0.6)
            kendang(s, "kendang", b0 + 12, "B . . t B . O .  D T O T D . P .", 0.6)
            for bar in range(4):
                note(s, "taiko", b0 + bar * 4, 1, s.cents("6", -2), 96)
                note(s, "taiko", b0 + bar * 4 + 2.5, 1, s.cents("6", -2), 70)
                note(s, "taiko", b0 + bar * 4 + 3, 1, s.cents("6", -2), 84)
    horn = ("1:1.5 2:0.5 3:2 5:3 6:1 5:2 3:1 2:1 3:4 "
            "5:1.5 6:0.5 1':2 2':3 1':1 6:4 5:4")
    line(s, "horn", 16, horn, oct=-1, vel=100)
    # strings: kempyung (two keys below) harmony + octave bass
    notes, _ = seq(horn)
    for t, d, tok in notes:
        c = s.cents(tok, -1)
        note(s, "strings", 16 + t, d, s.step(c, -2), 78)
        note(s, "strings", 16 + t, d, c - 1200, 70)
    swell(s, "strings", 16, 32, 60, 115)
    sustain(s, "choir", 16, 16, [s.cents("6", -2), s.cents("2", -1)], 60)
    sustain(s, "choir", 32, 16, [s.cents("5", -2), s.cents("1", -1)], 64)
    line(s, "suling", 48, "~6:3 5:1 3:2 2:2 ~3:4 2:1 1:1 6,:2 ~1:4 -:1 ~2:2 3:1 5:2 3:1 2:1 ~1:4", oct=1, vel=86)
    line(s, "cello", 48, "1:4 6,:4 5,:4 6,:4 3,:4 2,:4 1,:8", oct=-1, vel=86)
    swell(s, "cello", 48, 8, 60, 110)
    hit(s, "fx", 16, "swell", 0.6, length=2 * s.spb())
    return s


def stinger_victory():
    s = Song("victory", 120, 16, SLENDRO, [1, 2, 3, 5, 6], tonic=62, loop=False, rt60=2.6, max_len=9.0, seed=17)
    gamelan_lanes(s, bal=-24, rev=0.35)
    s.lane("bell", "bell", level=-26, pan=0.3, rev=0.6)
    s.part("brass", BRASS, level=-19, rev=0.4, width=1.2, gate=1.0)
    s.part("horn", HORN, level=-21, rev=0.45, gate=1.0)
    s.part("choir", CHOIR, level=-24, rev=0.5, width=1.3, gate=1.0)
    s.part("kit", 48, drum=True, level=-22, rev=0.4)
    s.part("taiko", TAIKO, level=-21, rev=0.35)
    kendang(s, "kendang", 0, "D t T t O t T t", 0.9)
    run = ["1", "2", "3", "5", "6", "1'", "2'", "3'"]
    for i, tok in enumerate(run):
        hit(s, "bonang_a" if i % 2 == 0 else "bonang_b", i * 0.25, s.cents(tok, 0), 0.7 + 0.04 * i)
    hit(s, "gong", 2, s.cents("2", -3), 1.0)
    hit(s, "kempul", 2, s.cents("1", -2), 0.8)
    hit(s, "fx", 2, "boom", 0.9)
    dnote(s, "kit", 2, 57, 120, 2)
    dnote(s, "kit", 2, 49, 110, 2)
    note(s, "taiko", 2, 1, s.cents("1", -2), 124)
    note(s, "taiko", 1.5, 1, s.cents("1", -2), 90)
    sustain(s, "brass", 2, 6, [s.cents("1", -1), s.cents("5", -1), s.cents("1", 0), s.cents("3", 0)], 110)
    line(s, "horn", 2, "5:0.5 6:0.5 1':5", oct=-1, vel=108)
    sustain(s, "choir", 2, 6, [s.cents("1", -1), s.cents("5", -1), s.cents("3", 0)], 90)
    for i, tok in enumerate(["3''", "2''", "1''", "6'", "5'", "3'", "5'", "1''"]):
        hit(s, "peking", 2.5 + i * 0.25, s.cents(tok, 0), 0.5)
    hit(s, "bell", 4.5, s.cents("1''", 0), 0.6)
    hit(s, "saron", 2, s.cents("1'", 0), 0.9)
    return s


def stinger_death():
    s = Song("death", 60, 8, SLENDRO, [1, 2, 3, 5, 6], tonic=62, loop=False, rt60=3.0, max_len=5.5, seed=19)
    s.lane("gender_r", "gender", level=-22, pan=-0.2, rev=0.5, ring=None, beat=4.5)
    s.lane("gong", "gong", level=-20, width=0.5, rev=0.4)
    s.lane("kempul", "kempul", level=-26, pan=0.3, rev=0.4)
    s.part("choir", OOHS, level=-25, rev=0.6, width=1.3, gate=1.0)
    s.part("low", CELLO, level=-27, rev=0.5, gate=1.0)
    hit(s, "gong", 0, s.cents("2", -3) - 60, 1.0)
    for i, tok in enumerate(["6", "5", "3", "2", "1"]):
        hit(s, "gender_r", 0.15 + i * 0.45, s.cents(tok, 0) - 20 * i, 0.7 - 0.08 * i)
        hit(s, "gender_r", 0.15 + i * 0.45, s.cents(tok, -1) - 20 * i, 0.45 - 0.05 * i)
    hit(s, "kempul", 2.6, s.cents("6", -3), 0.7)
    sustain(s, "choir", 0.1, 4.5, [s.cents("1", -1), s.cents("2", -1), s.cents("6", -2)], 80)
    swell(s, "choir", 0.1, 4.5, 110, 20)
    sustain(s, "low", 0.0, 4.5, [s.cents("1", -2)], 90)
    swell(s, "low", 0.0, 4.5, 110, 10)
    return s


SONGS = {"hub": song_hub, "dandaka": song_dandaka, "muara": song_muara, "boss": song_boss, "title": song_title,
         "victory": stinger_victory, "death": stinger_death}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="subset of: " + " ".join(SONGS))
    ap.add_argument("--png", help="write waveform + spectrogram PNGs to this directory")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for n in a.names or list(SONGS):
        print(f"[{n}]")
        build(SONGS[n](), a.png)


if __name__ == "__main__":
    main()

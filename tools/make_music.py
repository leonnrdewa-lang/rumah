#!/usr/bin/env python3
"""Composes, renders and masters the soundtrack of Sawit The Franchise.

Everything here is original and written out note by note below (melodies, chord
progressions, accompaniment patterns). The score is rendered with FluidSynth from the
free MuseScore General SoundFont (apt: musescore-general-soundfont; falls back to
FluidR3 GM), one stem per instrument, then mixed in numpy: per-stem loudness balance,
EQ, pan, a synthetic stereo hall reverb, synthesised gamelan gong/kempul, a glue
compressor, loudness normalisation to -20 LUFS and a true-peak limiter. Loops are
rendered with an 8 s tail that is wrapped back onto the start, and the master bus is
processed circularly, so the loop point is seamless.

Colour: gamelan-like pelog/slendro motifs (imbal/kotekan on marimba, bonang patterns on
vibraphone, angklung = marimba tremolo in octaves, gong ageng + kempul), kendang-like
congas, keroncong (cak/cuk ukuleles, pizzicato cello, flute obbligato) for the sunset,
lo-fi Rhodes + brushes indoors, music box + celesta at night.

Output (game/assets/audio/, Ogg Vorbis 44.1 kHz stereo):
  music_title, music_day, music_evening, music_night, music_indoor   seamless loops
  music_rare, music_newday                                           ~2 s stingers

Needs fluidsynth + ffmpeg (libvorbis) and python3 -m pip install mido numpy scipy
soundfile pyloudnorm (matplotlib for --png).

  python3 tools/make_music.py                  # everything
  python3 tools/make_music.py day night        # only these
  python3 tools/make_music.py --png /tmp/png   # also waveform + spectrogram overviews
"""
import argparse
import itertools
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "assets", "audio")
WORK = os.environ.get("MUSIC_WORK", "/tmp/audio_work/music")
SOUNDFONTS = ["/usr/share/sounds/sf3/MuseScore_General.sf3", "/usr/share/sounds/sf3/MuseScore_General_Full.sf3",
              "/usr/share/sounds/sf2/FluidR3_GM.sf2"]
SR = 44100
TPB = 480
TAIL = 8.0            # seconds rendered past the loop end (reverb, gong, releases)
TARGET_LUFS = -20.0
CEILING_DBTP = -1.5
VORBIS_Q = 1          # ffmpeg libvorbis -q:a (oggenc scale; 1 ~ 80 kbps nominal)
PAN_SPREAD = 1.3      # widens every part's pan position

# ============================================================== music theory
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def pc_of(name):
    return (PC[name[0]] + name[1:].count("#") - name[1:].count("b")) % 12


def pitch(name):
    m = re.fullmatch(r"([A-G][#b]?)(-?\d)", name)
    if not m:
        raise ValueError("bad note " + name)
    base = PC[m[1][0]] + (1 if "#" in m[1] else -1 if "b" in m[1] else 0)
    return 12 * (int(m[2]) + 1) + base


QUAL = {
    "": [0, 4, 7], "maj7": [0, 4, 7, 11], "maj9": [0, 4, 7, 11, 14], "maj7#11": [0, 4, 7, 11, 18],
    "6": [0, 4, 7, 9], "add9": [0, 4, 7, 14], "m": [0, 3, 7], "m7": [0, 3, 7, 10], "m9": [0, 3, 7, 10, 14],
    "m6": [0, 3, 7, 9], "7": [0, 4, 7, 10], "9": [0, 4, 7, 10, 14], "13": [0, 4, 7, 10, 14, 21],
    "7b9": [0, 4, 7, 10, 13], "sus4": [0, 5, 7], "7sus4": [0, 5, 7, 10], "9sus4": [0, 5, 7, 10, 14],
    "13sus4": [0, 5, 7, 10, 14, 21], "sus2": [0, 2, 7], "dim": [0, 3, 6], "m7b5": [0, 3, 6, 10],
}


class Chord:
    def __init__(self, sym):
        m = re.fullmatch(r"([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?", sym)
        if not m or m[2] not in QUAL:
            raise ValueError("bad chord " + sym)
        self.sym = sym
        self.root = pc_of(m[1])
        self.ivs = QUAL[m[2]]
        self.bass = pc_of(m[3]) if m[3] else self.root
        self.pcs = {(self.root + i) % 12 for i in self.ivs}

    def core(self):
        """root, 3rd (or sus), 5th, 7th/6th pitch classes (no extensions)"""
        return {(self.root + i) % 12 for i in self.ivs if i < 12}

    def priority(self):
        """pitch classes in voicing priority: 3rd/sus, 7th/6th, extensions, 5th, root"""
        iv = self.ivs
        groups = [[i for i in iv if i in (2, 3, 4, 5)], [i for i in iv if i in (9, 10, 11)],
                  [i for i in iv if i > 12], [i for i in iv if i in (6, 7, 8)], [0]]
        out = []
        for g in groups:
            for i in g:
                pc = (self.root + i) % 12
                if pc not in out:
                    out.append(pc)
        return out


def pick_pcs(ch, n):
    pri = ch.priority()
    if len(pri) >= n:
        return pri[:n]
    extra = [ch.root, (ch.root + 7) % 12] + pri
    out = list(pri)
    i = 0
    while len(out) < n:
        out.append(extra[i % len(extra)])
        i += 1
    return out


def harsh(a, b):
    """minor 2nd / minor 9th (/ 16th): the intervals voicings must not contain"""
    return abs(a - b) % 12 == 1


def pc_sets(ch, n):
    """candidate pitch-class sets: the priority set, and variants with the root replaced by
    the 9th or a doubled 5th (rootless voicings; the bass plays the root)"""
    base = pick_pcs(ch, n)
    out = [(base, 0.0)]
    fifth = (ch.root + 7) % 12
    if ch.root in base and len(base) >= 3:
        rest = [p for p in base if p != ch.root]
        nine = (ch.root + 2) % 12
        # a 9th sits a semitone under a minor 3rd: only on major/dominant/sus chords
        if nine not in rest and 13 not in ch.ivs and 6 not in ch.ivs and 3 not in ch.ivs:
            out.append((rest + [nine], 0.6))
        out.append((rest + [fifth], 0.9))
    ext = {(ch.root + i) % 12 for i in ch.ivs if i > 12}
    if ext & set(base):
        # the same chord without its colour tones (they may rub against the tune)
        plain = [p if p not in ext else (fifth if fifth not in base else ch.root) for p in base]
        out.append((plain, 0.8))
    return out


def voice(ch, n, lo, hi, prev=None, center=None, avoid=()):
    """a close-ish voicing of n notes inside [lo, hi] leading smoothly from prev, free of
    minor 2nds/9ths inside itself and against the pitches in avoid (sounding notes)"""
    center = center if center is not None else (lo + hi) / 2
    avoid = list(avoid)
    best, best_cost = None, 1e9
    for pcs, extra in pc_sets(ch, n):
        opts = [[p for p in range(lo, hi + 1) if p % 12 == pc] for pc in pcs]
        for combo in itertools.product(*opts):
            s = sorted(combo)
            if len(set(s)) < len(s):
                continue
            span = s[-1] - s[0]
            if span > 17:
                continue
            gaps = [b - a for a, b in zip(s, s[1:])]
            cost = extra + 1.5 * sum(1 for g in gaps if g == 2)
            cost += 9.0 * sum(1 for a, b in itertools.combinations(s, 2) if harsh(a, b))
            cost += 6.0 * sum(1 for a in s for q in avoid if harsh(a, q))
            if s[0] < 53 and gaps and gaps[0] < 5:
                cost += 4
            cost += 0.35 * abs(sum(s) / len(s) - center)
            if prev and len(prev) == len(s):
                cost += 0.8 * sum(abs(a - b) for a, b in zip(s, prev))
            if cost < best_cost:
                best, best_cost = s, cost
    if best is None:
        best = sorted(lo + ((pc - lo) % 12) for pc in pick_pcs(ch, n))
    return best


def clean(pool, avoid):
    """drops pool pitches that would rub (m2/m9) against sounding notes"""
    ok = [p for p in pool if not any(harsh(p, q) for q in avoid)]
    return ok if ok else pool


def bass_pitch(ch, lo):
    return lo + ((ch.bass - lo) % 12)


def scale_pcs(key_root, mode="major"):
    steps = {"major": [0, 2, 4, 5, 7, 9, 11], "slendro": [0, 2, 4, 7, 9]}[mode]
    return {(key_root + s) % 12 for s in steps}


# ============================================================== score model
class Part:
    def __init__(self, song, name, program, bank=0, drum=False, pan=0.0, level=-6.0, hp=0.0, lp=0.0,
                 rev=0.2, jitter=0.006, velrand=5, gate=0.95, expr=None, width=1.0, shelf=None):
        self.song, self.name, self.program, self.bank, self.drum = song, name, program, bank, drum
        self.pan, self.level, self.hp, self.lp, self.rev = pan, level, hp, lp, rev
        self.jitter, self.velrand, self.gate, self.expr, self.width = jitter, velrand, gate, expr, width
        self.shelf = shelf           # (low_shelf_db, high_shelf_db) or None
        self.notes = []              # [t, d, p, v, flags]
        self.ccs = []                # [t, cc, val]
        self.prev = None             # last voicing (voice leading)

    def n(self, t, d, p, v, **flags):
        self.notes.append([float(t), float(d), int(p), int(max(1, min(127, v))), flags])

    def cc(self, t, c, v):
        self.ccs.append([float(t), int(c), int(max(0, min(127, v)))])


class Song:
    def __init__(self, name, bpm, bars, meter=4, swing16=0.5, swing8=0.5, loop=True, rt60=2.0,
                 lofi=False, seed=1, key=0):
        self.name, self.bpm, self.bars, self.meter = name, bpm, bars, meter
        self.swing16, self.swing8, self.loop, self.rt60, self.lofi = swing16, swing8, loop, rt60, lofi
        self.key = key
        self.harm = []               # [start_beat, end_beat, Chord]
        self.hold = []               # (t0, t1, pitch): sustained notes voicings keep clear of
        self.parts = {}
        self.synth = []              # numpy instruments: (beat, kind, midi_pitch, gain_db)
        self.rng = random.Random(seed)
        self.tail_beats = 0.0        # stingers: extra beats rendered after the bars
        self.gong_level = -24.0      # LUFS of the synthesised gamelan stem
        self.max_len = 0.0           # stingers: hard length (s), faded over the last 0.7 s
        self.target = TARGET_LUFS

    @property
    def beats(self):
        return self.bars * self.meter

    def spb(self):
        return 60.0 / self.bpm

    def part(self, name, program, bank=0, **kw):
        p = Part(self, name, program, bank, **kw)
        self.parts[name] = p
        return p

    def chords(self, bar0, text):
        for i, bar in enumerate(text.split("|")):
            syms = bar.split()
            d = self.meter / len(syms)
            for j, s in enumerate(syms):
                t = (bar0 + i) * self.meter + j * d
                self.harm.append([t, t + d, Chord(s)])
        self.harm.sort(key=lambda h: h[0])

    def chord_at(self, t):
        t = t % self.beats if self.loop else t
        for h in self.harm:
            if h[0] <= t + 1e-6 < h[1]:
                return h[2]
        return self.harm[-1][2]

    def events(self, bar0, nbars):
        a, b = bar0 * self.meter, (bar0 + nbars) * self.meter
        return [h for h in self.harm if a - 1e-6 <= h[0] < b - 1e-6]

    def reg(self, t0, t1, pitches):
        for p in pitches:
            self.hold.append((t0, t1, p))

    def sounding(self, t0, t1):
        return [p for a, b, p in self.hold if a < t1 - 1e-3 and b > t0 + 1e-3]

    def gong(self, bar, kind="gong", note="C2", db=0.0, beat=0.0):
        self.synth.append((bar * self.meter + beat, kind, pitch(note), db))


# ============================================================== composition helpers
def accent(song, t):
    pos = t % song.meter
    if abs(pos) < 1e-6:
        return 6
    if song.meter == 4 and abs(pos - 2) < 1e-6:
        return 3
    if abs(pos - round(pos)) < 1e-6:
        return 0
    if abs((pos % 1) - 0.5) < 1e-6:
        return -3
    return -5


def mel(part, bar0, text, vel=80, shift=0, roll=None, scoop=0.0, gate=None, arch=6):
    """melody from 'E5:1 G5:.5 | ...' (bars must be full; 'r' = rest, 'C5+E5' = dyad).
    roll: marimba-style tremolo roll for notes >= roll beats. scoop: chance of a suling-like
    bend into long notes. Returns the list of (t, d, pitch) placed."""
    song = part.song
    t = bar0 * song.meter
    placed = []
    for bi, bar in enumerate(text.split("|")):
        start = t
        for tok in bar.split():
            name, dur = tok.split(":")
            dur = float(dur)
            if name != "r":
                pos_in_phrase = ((t - bar0 * song.meter) % (2 * song.meter)) / (2 * song.meter)
                v = vel + accent(song, t) + arch * math.sin(math.pi * pos_in_phrase)
                for nm in name.split("+"):
                    p = pitch(nm) + shift
                    fl = {}
                    if scoop and dur >= 1.5 and song.rng.random() < scoop:
                        fl["scoop"] = True
                    if gate is not None:
                        fl["gate"] = gate
                    if roll and dur >= roll:
                        part.n(t, song.meter / 16, p, v, **fl)
                        step = 0.125 if song.bpm >= 80 else 1 / 6
                        k, tt = 0, t + step
                        while tt < t + dur * 0.88:
                            frac = (tt - t) / dur
                            rv = v * (0.62 + 0.12 * math.sin(math.pi * frac)) + song.rng.uniform(-4, 4)
                            part.n(tt, step * 1.3, p, rv, roll=True)
                            tt += step
                            k += 1
                    else:
                        part.n(t, dur, p, v, **fl)
                    placed.append((t, dur, p))
                    if dur >= 1.0:
                        song.reg(t, t + dur, [p])
            t += dur
        if abs((t - start) - song.meter) > 1e-6:
            raise ValueError(f"{song.name}/{part.name}: bar {bar0 + bi} has {t - start} beats: {bar}")
    return placed


def harmony_below(part, placed, vel, lo_iv=3, hi_iv=9, shift=0):
    """doubles a melody with the nearest chord tone 3..9 semitones below each note"""
    song = part.song
    for t, d, p in placed:
        ch = song.chord_at(t)
        cand = [q for q in range(p - hi_iv, p - lo_iv + 1) if q % 12 in ch.pcs]
        if cand:
            part.n(t, d, max(cand) + shift, vel + accent(song, t))


def strum(part, bar0, nbars, pattern, vel=64, lo=52, hi=67, blo=40, spread=0.011, upper=4):
    """guitar/ukulele strums: pattern = [(beat, 'D'|'U', vel_scale, dur_beats)]"""
    song = part.song
    sp = spread / song.spb()
    for bar in range(bar0, bar0 + nbars):
        for off, d, vs, dur in pattern:
            t = bar * song.meter + off
            ch = song.chord_at(t)
            up = voice(ch, upper, lo, hi, part.prev, avoid=song.sounding(t, t + dur))
            part.prev = up
            song.reg(t, t + dur, up)
            notes = ([bass_pitch(ch, blo)] if (d == "D" and blo) else []) + up
            if d == "U":
                notes = list(reversed(notes[-3:]))
            v0 = vel * vs + accent(song, t) * 0.5
            jit = song.rng.gauss(0, 0.004) / song.spb()
            for i, p in enumerate(notes):
                part.n(t + jit + i * sp, dur, p, v0 - i * 1.5 + song.rng.uniform(-3, 3), nojit=True)


def arp(part, bar0, nbars, pattern, step=0.5, vel=55, lo=55, hi=72, blo=40, ring=2.0, upper=3):
    """fingerpicked arpeggio; pattern indexes [bass, upper...] per step"""
    song = part.song
    per_bar = int(round(song.meter / step))
    for bar in range(bar0, bar0 + nbars):
        for k in range(per_bar):
            t = bar * song.meter + k * step
            ch = song.chord_at(t)
            if k == 0 or song.chord_at(t - 1e-3) is not ch:
                end = next((h[1] for h in song.harm if h[2] is ch), t + song.meter)
                part.prev = voice(ch, upper, lo, hi, part.prev, avoid=song.sounding(t, end))
                song.reg(t, end, part.prev)
            notes = [bass_pitch(ch, blo)] + part.prev
            idx = pattern[k % len(pattern)]
            if idx is None:
                continue
            p = notes[min(idx, len(notes) - 1)]
            part.n(t, step * ring, p, vel + accent(song, t) * 0.7 + (4 if idx == 0 else 0))


def imbal(part, bar0, nbars, contours, anchor=60, lo=55, hi=79, vel=52, step=0.5, add9=True):
    """gamelan-like interlocking figure over chord tones (+9th), contour index per step"""
    song = part.song
    per_bar = int(round(song.meter / step))
    for bi, bar in enumerate(range(bar0, bar0 + nbars)):
        cont = contours[bi % len(contours)]
        for k in range(per_bar):
            c = cont[k % len(cont)]
            if c is None:
                continue
            t = bar * song.meter + k * step
            ch = song.chord_at(t)
            pcs = set(ch.core())
            if add9:
                pcs.add((ch.root + 2) % 12)
            pool = clean([p for p in range(lo, hi + 1) if p % 12 in pcs], song.sounding(t, t + step))
            i0 = next((i for i, p in enumerate(pool) if p >= anchor), 0)
            p = pool[max(0, min(len(pool) - 1, i0 + c))]
            part.n(t, step * 1.6, p, vel + accent(song, t) * 0.8)


def bass(part, bar0, nbars, style="island", lo=36, vel=78):
    song = part.song
    for h in song.events(bar0, nbars):
        t0, t1, ch = h
        dur = t1 - t0
        r = bass_pitch(ch, lo)
        f5 = (ch.root + 7) % 12
        fifth = r + ((f5 - r) % 12 or 12)
        if fifth > lo + 16:
            fifth -= 12
        nxt = song.chord_at(t1 + 1e-3)
        nr = bass_pitch(nxt, lo)
        sc = scale_pcs(song.key)
        appr = nr - 1 if (nr - 1) % 12 in sc else nr + 2
        if style == "island":
            if dur >= 4:
                seq = [(0, r, 1.4, 0), (1.5, r, .45, -14), (2, fifth, 1.4, -6), (3.5, appr, .45, -16)]
            else:
                seq = [(0, r, 1.4, 0), (1.5, fifth, .45, -14)]
        elif style == "half":
            seq = [(0, r, dur * 0.5 - .1, 0)] + ([(dur / 2, fifth, dur / 2 - .1, -8)] if dur >= 4 else [])
        elif style == "whole":
            seq = [(0, r, dur - .05, 0)]
        elif style == "lofi":
            if dur >= 4:
                seq = [(0, r, 1.6, 0), (2.5, r + 12 if r + 12 <= lo + 19 else fifth, .45, -12),
                       (3, fifth, .5, -8), (3.5, appr, .45, -12)]
            else:
                seq = [(0, r, 1.4, 0), (1.5, fifth, .45, -10)]
        elif style == "keroncong":
            # pizzicato cello imitating the kendang: syncopated, busy but soft
            if dur >= 4:
                seq = [(0, r, .5, 0), (1, fifth, .5, -10), (1.75, r, .25, -18), (2, r + 12 if r + 12 <= lo + 19 else r, .5, -6),
                       (2.75, fifth, .25, -16), (3, fifth, .5, -8), (3.5, appr, .5, -12)]
            else:
                seq = [(0, r, .5, 0), (1, fifth, .5, -8), (1.5, appr if dur <= 2 else r, .5, -12)]
        else:
            raise ValueError(style)
        for off, p, d, dv in seq:
            if off < dur - 1e-6:
                part.n(t0 + off, d, p, vel + dv)
                if d >= 1.0:
                    song.reg(t0 + off, t0 + off + d, [p])


def pad(part, bar0, nbars, lo=55, hi=74, n=4, vel=60, cc=11, swell=(0.7, 1.0, 0.85), lvl=100):
    """sustained chords with a slow expression swell per chord"""
    song = part.song
    for t0, t1, ch in song.events(bar0, nbars):
        part.prev = voice(ch, n, lo, hi, part.prev, avoid=song.sounding(t0, t1))
        song.reg(t0, t1, part.prev)
        for p in part.prev:
            part.n(t0, (t1 - t0) + 0.05, p, vel)
        if cc:
            steps = max(4, int((t1 - t0) * 4))
            for k in range(steps + 1):
                f = k / steps
                if f < 0.4:
                    g = swell[0] + (swell[1] - swell[0]) * math.sin(f / 0.4 * math.pi / 2)
                else:
                    g = swell[1] + (swell[2] - swell[1]) * (f - 0.4) / 0.6
                part.cc(t0 + f * (t1 - t0) - 0.01, cc, lvl * g)


def rolled(part, bar0, nbars, vel=40, lo=55, hi=74, blo=31, roll=0.35, pedal=True, n=4, second=None):
    """soft piano: bass note + upper voicing, rolled upward; sustain pedal per chord"""
    song = part.song
    for t0, t1, ch in song.events(bar0, nbars):
        part.prev = voice(ch, n, lo, hi, part.prev, avoid=song.sounding(t0, t1))
        b = bass_pitch(ch, blo)
        song.reg(t0, t1, part.prev + [b, b + 12])
        notes = [b, b + 12] + part.prev
        if pedal:
            part.cc(t0 - 0.02, 64, 0)
            part.cc(t0 + 0.05, 64, 110)
        for i, p in enumerate(notes):
            part.n(t0 + roll * i / len(notes), (t1 - t0) * 0.9, p, vel - (10 if i == 0 else 5 if i == 1 else i))
        if second is not None and t1 - t0 >= 4:
            for i, p in enumerate(part.prev[-3:]):
                part.n(t0 + second + 0.06 * i, (t1 - t0 - second) * 0.9, p, vel - 10)
    if pedal:
        part.cc(song.beats - 0.05, 64, 0)


def sparkle(part, t, ch, lo=84, count=5, step=0.25, vel=48, down=False):
    pool = clean([p for p in range(lo, min(lo + 30, 97)) if p % 12 in ch.core()], part.song.sounding(t, t + count * step))[:count]
    if down:
        pool = pool[::-1]
    for i, p in enumerate(pool):
        part.n(t + i * step, 1.5, p, vel - 2 * i)


def gliss(part, t, lo, hi, pcs, dur, vel=50, up=True):
    pool = clean([p for p in range(lo, hi + 1) if p % 12 in pcs], part.song.sounding(t, t + dur + 1))
    if not up:
        pool = pool[::-1]
    for i, p in enumerate(pool):
        part.n(t + dur * i / len(pool), 1.2, p, vel + (i * 6 / len(pool)))


def angklung(part, t0, t1, pitches, vel=50, rate_hz=8.5, octave=True):
    """angklung: every tube is shaken (fast tremolo), tubes tuned in octaves, swelling"""
    song = part.song
    step = song.bpm / 60.0 / rate_hz
    for p in pitches:
        for q in ([p, p + 12] if octave else [p]):
            tt = t0 + song.rng.uniform(0, step)
            while tt < t1:
                f = (tt - t0) / max(1e-6, t1 - t0)
                env = math.sin(math.pi * min(1.0, 0.15 + f * 0.85)) ** 0.7
                v = vel * (0.55 + 0.45 * env) * (1.0 if q == p else 0.7) + song.rng.uniform(-5, 5)
                part.n(tt, step * 1.1, q, v, nojit=True)
                tt += step * song.rng.uniform(0.92, 1.08)


def run(part, t, start, count, pcs, step=0.25, vel=58, down=True):
    """scale run (keroncong guitar fill) from start, count notes, within pcs"""
    p = start
    k = 0
    while k < count:
        if p % 12 in pcs:
            part.n(t + k * step, step * 1.5, p, vel - k * 0.8)
            k += 1
        p += -1 if down else 1


def hits(part, bar0, nbars, pattern, mapping):
    """percussion from a per-bar grid string ('.' = rest), chars map to (note, vel)"""
    song = part.song
    pat = pattern.replace(" ", "")
    step = song.meter / len(pat)
    for bar in range(bar0, bar0 + nbars):
        for k, c in enumerate(pat):
            if c == ".":
                continue
            note, v = mapping[c]
            part.n(bar * song.meter + k * step, step * 0.9, note, v)


def expr_curve(part, cc=2, lo=70, hi=118, vib=0, vib_cc=1):
    """breath/expression per note (Expr presets use CC2): long notes swell and relax,
    and grow a delayed vibrato"""
    song = part.song
    notes = sorted((n for n in part.notes if not n[4].get("roll")), key=lambda n: n[0])
    for i, (t, d, p, v, fl) in enumerate(notes):
        base = lo + (hi - lo) * (v - 40) / 70.0
        if d >= 0.9:
            steps = max(3, int(d * 6))
            for k in range(steps + 1):
                f = k / steps
                g = 0.84 + 0.16 * math.sin(min(1.0, f / 0.45) * math.pi / 2) - 0.1 * max(0.0, f - 0.6)
                part.cc(t + f * d * 0.97, cc, base * g)
                if vib:
                    part.cc(t + f * d * 0.97, vib_cc, vib * max(0.0, min(1.0, (f - 0.25) / 0.35)))
            if vib:
                part.cc(t + d, vib_cc, 0)
        else:
            part.cc(t - 0.01, cc, base * 0.95)


# ============================================================== MIDI + FluidSynth
def swing_time(song, t):
    frac = t - math.floor(t)
    if song.swing16 != 0.5:
        if abs(frac - 0.25) < 1e-4:
            return math.floor(t) + 0.5 * song.swing16
        if abs(frac - 0.75) < 1e-4:
            return math.floor(t) + 0.5 + 0.5 * song.swing16
    if song.swing8 != 0.5 and abs(frac - 0.5) < 1e-4:
        return math.floor(t) + song.swing8
    return t


def write_midi(song, part, path):
    rng = random.Random(zlib.crc32((song.name + "/" + part.name).encode()))
    beat_s = song.spb()
    ch = 9 if part.drum else 0
    ev = []

    def tk(b):
        return max(0, int(round(b * TPB)))

    ev.append((0, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm))))
    if not part.drum:
        ev.append((0, 0, mido.Message("control_change", channel=ch, control=0, value=part.bank)))
    ev.append((0, 0, mido.Message("program_change", channel=ch, program=part.program)))
    pan = max(-1.0, min(1.0, part.pan * PAN_SPREAD))
    init = {7: 100, 10: int(round(64 + pan * 63)), 11: 127, 91: 0, 93: 0, 1: 0, 64: 0}
    if part.expr == 2:
        init[2] = 100
    for c, v in init.items():
        ev.append((0, 1, mido.Message("control_change", channel=ch, control=c, value=max(0, min(127, v)))))
    for t, c, v in part.ccs:
        ev.append((tk(max(0.0, t)), 2, mido.Message("control_change", channel=ch, control=c, value=v)))
    placed = []
    for t, d, p, v, fl in part.notes:
        st = swing_time(song, t)
        if not fl.get("nojit"):
            j = max(-2.5, min(2.5, rng.gauss(0, 1))) * part.jitter / beat_s
            st += j
        v = v + rng.uniform(-part.velrand, part.velrand)
        gate = fl.get("gate", part.gate)
        on = tk(max(0.0, st))
        off = on + max(12, int(round(d * gate * TPB)))
        placed.append([on, off, p, int(max(1, min(127, v))), fl])
    placed.sort(key=lambda x: (x[0], x[2]))
    last = {}
    for nt in placed:     # a repeated pitch must not be cut by the previous note's note-off
        prev = last.get(nt[2])
        if prev is not None and prev[1] > nt[0] - 1:
            prev[1] = max(prev[0] + 6, nt[0] - 1)
        last[nt[2]] = nt
    for on, off, p, v, fl in placed:
        ev.append((on, 3, mido.Message("note_on", channel=ch, note=p, velocity=v)))
        ev.append((off, 1, mido.Message("note_off", channel=ch, note=p, velocity=0)))
        if fl.get("scoop"):
            depth = -int(8192 * 0.55 / 2)   # start ~55 cents flat, bend up (suling-like)
            ev.append((max(0, on - 2), 2, mido.Message("pitchwheel", channel=ch, pitch=depth)))
            n = 8
            span = int(0.14 / beat_s * TPB)
            for k in range(1, n + 1):
                ev.append((on + span * k // n, 2, mido.Message("pitchwheel", channel=ch, pitch=int(depth * (1 - k / n) ** 2))))
    end = tk(song.beats + song.tail_beats + TAIL / beat_s)
    ev.append((end, 2, mido.Message("control_change", channel=ch, control=110, value=0)))
    ev.sort(key=lambda e: (e[0], e[1]))
    mf = mido.MidiFile(ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mf.tracks.append(tr)
    now = 0
    for tick, _, msg in ev:
        tr.append(msg.copy(time=tick - now))
        now = tick
    mf.save(path)


def soundfont():
    for s in SOUNDFONTS:
        if os.path.exists(s):
            return s
    sys.exit("no SoundFont found (apt install musescore-general-soundfont or fluid-soundfont-gm)")


def render_stem(song, part, wdir, sfont):
    mid = os.path.join(wdir, part.name + ".mid")
    wav = os.path.join(wdir, part.name + ".wav")
    write_midi(song, part, mid)
    cmd = os.path.join(wdir, "interp.cmd")
    subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.5", "-r", str(SR), "-R", "0", "-C", "0",
                    "-o", "synth.dynamic-sample-loading=1", "-o", "audio.file.format=float",
                    "-o", "synth.polyphony=512", "-f", cmd, "-F", wav, sfont, mid],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    x, sr = sf.read(wav, dtype="float32", always_2d=True)
    assert sr == SR
    os.remove(wav)
    return np.ascontiguousarray(x.T)


# ============================================================== DSP
def sos_hp(fc, order=2):
    return signal.butter(order, fc, "highpass", fs=SR, output="sos")


def sos_lp(fc, order=2):
    return signal.butter(order, fc, "lowpass", fs=SR, output="sos")


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


def filt(sos, x):
    return signal.sosfilt(sos, x, axis=-1)


def make_ir(rt60, seed=7, predelay=0.018, bright=1.0):
    """stereo hall impulse response: early reflections + decorrelated diffuse tail whose
    highs die faster than its lows"""
    rng = np.random.default_rng(seed)
    n = int(SR * (rt60 * 1.15 + predelay))
    t = np.arange(n) / SR
    ir = np.zeros((2, n))
    for c in range(2):
        noise = rng.standard_normal(n)
        bands = [(None, 350, 1.15), (350, 2500, 1.0), (2500, 6000, 0.62 * bright), (6000, None, 0.35 * bright)]
        tail = np.zeros(n)
        for lo, hi, k in bands:
            if lo is None:
                b = filt(sos_lp(hi, 4), noise)
            elif hi is None:
                b = filt(sos_hp(lo, 4), noise)
            else:
                b = filt(signal.butter(4, [lo, hi], "bandpass", fs=SR, output="sos"), noise)
            tail += b * np.exp(-6.91 * np.maximum(0, t - predelay) / (rt60 * k))
        tail *= np.clip((t - predelay) / 0.03, 0, 1)
        ir[c] = tail
        # early reflections
        for k in range(10):
            d = predelay * 0.3 + rng.uniform(0.004, 0.06)
            i = int(d * SR)
            ir[c, i] += rng.uniform(0.3, 0.9) * (0.75 ** k) * rng.choice([-1, 1]) * 6.0
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir


def reverb(x, ir):
    return np.stack([signal.oaconvolve(x[c], ir[c])[:x.shape[1]] for c in range(2)])


def lufs(x):
    m = pyln.Meter(SR)
    try:
        v = m.integrated_loudness(x.T)
    except ValueError:
        return -120.0
    return v if np.isfinite(v) else -120.0


def true_peak_db(x):
    pk = max(float(np.max(np.abs(signal.resample_poly(c, 4, 1)))) for c in x)
    return 20 * math.log10(pk + 1e-12)


def pan_width(x, pan, width):
    """stereo width (0 = mono) then constant-power balance"""
    mid = (x[0] + x[1]) * 0.5
    side = (x[0] - x[1]) * 0.5 * width
    l, r = mid + side, mid - side
    a = (pan + 1) * math.pi / 4
    return np.stack([l * math.cos(a) * math.sqrt(2), r * math.sin(a) * math.sqrt(2)])


def compressor(x, thresh_db=-18.0, ratio=2.0, attack=0.02, release=0.25, knee=6.0, block=32):
    """stereo-linked RMS compressor at control rate (block samples)"""
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
    return x * gain, float(np.max(g))


def limiter(x, ceiling_db=CEILING_DBTP, look=0.004):
    """non-causal (offline) true-peak limiter with 4x oversampled peak detection"""
    ceil = 10 ** (ceiling_db / 20)
    pk = np.zeros(x.shape[1])
    for c in x:      # per channel: 4x oversampled peaks folded back to the sample grid
        up = np.abs(signal.resample_poly(c, 4, 1))
        pk = np.maximum(pk, up[:x.shape[1] * 4].reshape(-1, 4).max(axis=1))
        del up
    req = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    w = max(3, int(look * SR))
    g = minimum_filter1d(req, 2 * w + 1)
    g = uniform_filter1d(g, w + 1)
    g = np.minimum(g, req)
    return x * g, 20 * math.log10(float(np.min(g)))


def gong_synth(f0, dur, kind="gong", seed=0):
    """gamelan gong ageng / kempul: inharmonic partials with the 'ombak' beating,
    soft mallet thump, long decay"""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "gong":
        parts = [(1.0, 1.0, 1.0), (1.51, 0.12, 0.5), (2.0, 0.45, 0.7), (2.66, 0.14, 0.45), (3.0, 0.22, 0.5),
                 (4.03, 0.10, 0.35), (5.1, 0.05, 0.25)]
        T, beat = 2.6, 0.9 + 0.3 * rng.random()
    else:
        parts = [(1.0, 1.0, 1.0), (2.0, 0.5, 0.6), (2.92, 0.18, 0.4), (4.0, 0.12, 0.3), (5.6, 0.05, 0.2)]
        T, beat = 1.2, 2.5 + rng.random()
    y = np.zeros(n)
    for r, a, ds in parts:
        f = f0 * r
        if f > 9000:
            continue
        ph = rng.uniform(0, 2 * np.pi, 2)
        env = np.exp(-t / (T * ds))
        y += a * env * (np.sin(2 * np.pi * f * t + ph[0]) + 0.8 * np.sin(2 * np.pi * (f + beat * r ** 0.5) * t + ph[1]))
    y *= 1 - np.exp(-t / 0.012)
    thump = rng.standard_normal(int(0.06 * SR))
    thump = filt(sos_lp(240, 2), thump) * np.exp(-np.arange(len(thump)) / SR / 0.018) * 1.2
    y[:len(thump)] += thump
    return y / (np.max(np.abs(y)) + 1e-9)


# ============================================================== mixdown
def mixdown(song, stems, wdir):
    spb = song.spb()
    body = int(round(song.beats * spb * SR))
    total = body + int((TAIL + song.tail_beats * spb) * SR)
    dry = np.zeros((2, total))
    send = np.zeros((2, total))
    report = []
    for name in list(stems):
        x = stems.pop(name)      # one stem at a time keeps the memory use low
        p = song.parts.get(name)
        buf = np.zeros((2, total))
        m = min(total, x.shape[1])
        buf[:, :m] = x[:, :m]
        del x
        if p is None:     # numpy synth stem (gong/kempul)
            level, hp, lp, rev, width, shelf = song.gong_level, 30, 0, 0.35, 0.3, None
        else:
            level, hp, lp, rev, width, shelf = p.level, p.hp, p.lp, p.rev, p.width, p.shelf
        if hp:
            buf = filt(sos_hp(hp), buf)
        if lp:
            buf = filt(sos_lp(lp), buf)
        if shelf:
            if shelf[0]:
                buf = filt(biquad_shelf(250, shelf[0], high=False), buf)
            if shelf[1]:
                buf = filt(biquad_shelf(4500, shelf[1], high=True), buf)
        if width != 1.0:      # pan itself is done in the MIDI (CC10)
            buf = pan_width(buf, 0.0, width)
        l0 = lufs(buf)
        if l0 <= -100:
            continue
        g = 10 ** ((level - l0) / 20)
        buf *= g
        dry += buf
        send += buf * rev
        report.append(f"{name}:{l0:.0f}->{level:+.0f}")
    ir = make_ir(song.rt60, seed=len(song.name), bright=0.8 if song.lofi else 1.0)
    wet = reverb(send, ir)
    wet = filt(sos_hp(220), wet)
    wet = filt(sos_lp(7000 if not song.lofi else 5000), wet)
    mix = dry + wet
    if song.loop:
        out = mix[:, :body].copy()
        tail = mix[:, body:]
        k = 0
        while k < tail.shape[1]:     # wrap the tail onto the start (seamless loop)
            m = min(body, tail.shape[1] - k)
            out[:, :m] += tail[:, k:k + m]
            k += m
    else:
        out = mix
    print(f"  stems  " + "  ".join(report))
    return out


def master(song, x):
    """circular (loop-aware) master chain: HPF, glue compression, tone, loudness, limiter"""
    n = x.shape[1]
    pad_n = min(n, int(3 * SR)) if song.loop else 0
    if song.loop:
        y = np.concatenate([x[:, -pad_n:], x, x[:, :pad_n]], axis=1)
        # the IIR filters settle inside the 3 s pad, so the seam matches as well
    else:
        y = np.concatenate([x, np.zeros((2, int(0.2 * SR)))], axis=1)
    y = filt(sos_hp(32, 2), y)
    y = filt(biquad_shelf(130, -1.5, high=False), y)
    if not song.lofi:
        y = filt(biquad_shelf(3500, 2.5, high=True), y)
    if song.lofi:
        y = filt(sos_lp(8000, 2), y)
        y = wow(y, song, pad_n, n)
        y = np.tanh(y * 1.4 / (np.max(np.abs(y)) + 1e-9)) * (np.max(np.abs(y)) + 1e-9) / 1.4
    if not song.loop and song.max_len:
        m = int(song.max_len * SR)
        y = y[:, :m]
        f = int(0.7 * SR)
        y[:, -f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        n = y.shape[1]
    target = song.target
    l0 = lufs(y[:, pad_n:pad_n + n])
    y *= 10 ** ((target + 2.5 - l0) / 20)
    y, gr = compressor(y, thresh_db=target - 3, ratio=1.8, attack=0.03, release=0.35)
    for _ in range(3):
        l1 = lufs(y[:, pad_n:pad_n + n])
        y *= 10 ** ((target - l1) / 20)
        y, lim = limiter(y)
    y = y[:, pad_n:pad_n + n] if song.loop else y
    if not song.loop and not song.max_len:
        # trim the silent end, gentle fade
        e = np.max(np.abs(y), axis=0)
        idx = np.nonzero(e > 10 ** (-62 / 20))[0]
        end = min(y.shape[1], (idx[-1] if len(idx) else y.shape[1]) + int(0.05 * SR))
        y = y[:, :end]
        f = int(0.25 * SR)
        y[:, -f:] *= np.linspace(1, 0, f) ** 2
    return y, gr


def wow(y, song, pad_n, n):
    """tape wow for the lo-fi track: a slow pitch wobble whose period divides the loop"""
    loop_s = n / SR
    cycles = max(1, round(loop_s / 2.3))
    f = cycles / loop_s
    t = (np.arange(y.shape[1]) - pad_n) / SR
    d = 0.0011 * (1 + np.sin(2 * np.pi * f * t)) * SR + 2
    idx = np.arange(y.shape[1]) - d
    i0 = np.clip(np.floor(idx).astype(int), 0, y.shape[1] - 2)
    fr = idx - np.floor(idx)
    return y[:, i0] * (1 - fr) + y[:, i0 + 1] * fr


def seam_report(y, bar_s):
    """loop seam: sample jump between the last and first sample vs the typical step, and the
    RMS change across the seam (50 ms each side) vs the same measure at every other bar line"""
    d = np.abs(y[:, 0] - y[:, -1]).max()
    steps = np.abs(np.diff(y, axis=1))
    typ, p99 = np.median(steps), np.percentile(steps, 99)
    w = int(0.05 * SR)

    def jump(i):
        z = np.roll(y, -i + w, axis=1)[:, :2 * w]
        a = np.sqrt(np.mean(z[:, :w] ** 2)) + 1e-12
        b = np.sqrt(np.mean(z[:, w:] ** 2)) + 1e-12
        return 20 * math.log10(b / a)

    n = y.shape[1]
    bars = [int(round(k * bar_s * SR)) for k in range(1, int(n / SR / bar_s))]
    others = [jump(i) for i in bars if w < i < n - w]
    return d, typ, p99, jump(0), float(np.median(others)), float(np.max(others))


def encode(y, path):
    tmp = path + ".tmp.wav"
    sf.write(tmp, y.T.astype(np.float32), SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-map_metadata", "-1", "-c:a", "libvorbis",
                    "-q:a", str(VORBIS_Q), "-ar", str(SR), "-ac", "2", path], check=True)
    os.remove(tmp)


def overview_png(y, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mono = y.mean(axis=0)
    fig, ax = plt.subplots(2, 1, figsize=(12, 5.2), sharex=True, gridspec_kw={"height_ratios": [1, 2]})
    cols = 2400
    blk = max(1, len(mono) // cols)
    m = mono[:blk * (len(mono) // blk)].reshape(-1, blk)
    tt0 = (np.arange(m.shape[0]) + 0.5) * blk / SR
    ax[0].fill_between(tt0, m.min(axis=1), m.max(axis=1), color="#3a7ca5", lw=0)
    rms = np.sqrt(np.mean(m ** 2, axis=1))
    ax[0].plot(tt0, rms, color="#f4a259", lw=0.8)
    ax[0].set_ylim(-1, 1)
    ax[0].set_ylabel("wave")
    ax[0].set_title(title, fontsize=10)
    f, tt, s = signal.spectrogram(mono, SR, nperseg=2048, noverlap=1024)
    ax[1].pcolormesh(tt, f, 10 * np.log10(s + 1e-12), shading="auto", vmin=-120, vmax=-40, cmap="magma")
    ax[1].set_yscale("symlog", linthresh=200)
    ax[1].set_ylim(40, 16000)
    ax[1].set_ylabel("Hz")
    ax[1].set_xlabel("s")
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def build(song, png_dir=None):
    wdir = os.path.join(WORK, song.name)
    os.makedirs(wdir, exist_ok=True)
    sfont = soundfont()
    with open(os.path.join(wdir, "interp.cmd"), "w") as f:
        f.write("interp 7\n")
    parts = [p for p in song.parts.values() if p.notes]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {p.name: ex.submit(render_stem, song, p, wdir, sfont) for p in parts}
        stems = {k: f.result() for k, f in futs.items()}
    if song.synth:
        spb = song.spb()
        total = int(round((song.beats + song.tail_beats) * spb * SR)) + int(TAIL * SR)
        g = np.zeros((2, total))
        for i, (beat, kind, midi, db) in enumerate(song.synth):
            f0 = 440.0 * 2 ** ((midi - 69) / 12)
            y = gong_synth(f0, 9.0 if kind == "gong" else 4.5, kind, seed=i + 3) * 10 ** (db / 20)
            s = int(beat * spb * SR)
            m = min(len(y), total - s)
            g[:, s:s + m] += y[:m]
        stems["gamelan"] = g
    x = mixdown(song, stems, wdir)
    y, gr = master(song, x)
    path = os.path.join(OUT, f"music_{song.name}.ogg")
    encode(y, path)
    # --- measurements on the decoded Ogg (what the game plays)
    z, zsr = sf.read(path, dtype="float64", always_2d=True)
    z = z.T
    L = lufs(z)
    tp = true_peak_db(z)
    msg = (f"  {song.name}: {z.shape[1] / SR:.2f}s (pcm {y.shape[1] / SR:.2f}s)  {L:.1f} LUFS  "
           f"TP {tp:.1f} dBTP  comp {gr:.1f} dB  {os.path.getsize(path) / 1024:.0f} KB  "
           f"{os.path.getsize(path) * 8 / (z.shape[1] / SR) / 1000:.0f} kbps")
    if song.loop:
        d, typ, p99, jump, med, mx = seam_report(z, song.meter * song.spb())
        msg += (f"\n  seam: |x[0]-x[-1]| {d:.4f} (median step {typ:.4f}, p99 {p99:.4f}); RMS change across "
                f"seam {jump:+.1f} dB (other bar lines: median {med:+.1f}, max {mx:+.1f})")
        if z.shape[1] != y.shape[1]:
            msg += f"  WARNING length {z.shape[1]} != {y.shape[1]}"
    print(msg)
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
        overview_png(z, os.path.join(png_dir, f"music_{song.name}.png"),
                     f"music_{song.name}  {song.bpm} bpm  {L:.1f} LUFS  TP {tp:.1f} dBTP")
    if not os.environ.get("MUSIC_KEEP"):
        shutil.rmtree(wdir, ignore_errors=True)
    return {"name": song.name, "lufs": L, "tp": tp, "bytes": os.path.getsize(path), "sec": z.shape[1] / SR}


# ============================================================== the pieces
# GM programs (MuseScore General): bank 0 unless noted
MELLOW_PIANO, EPIANO, CELESTA, GLOCK, MUSICBOX, VIBES, MARIMBA = 0, 4, 8, 9, 10, 11, 12   # (bank 8 for the mellow grand)
NYLON, UKULELE, ABASS, PIZZ, HARP, STRINGS_SLOW, FLUTE, KALIMBA = 24, 24, 32, 45, 46, 49, 73, 108  # (bank 8 ukulele, 40 celli pizz)
WARM_PAD, CELLO = 89, 42
EXPR = 17                                    # "Expr." banks: dynamics via CC2 (breath)
DR = {"D": (64, 64), "d": (64, 46), "T": (63, 50), "t": (62, 40), "k": (60, 34), "K": (61, 44),
      "s": (70, 26), "S": (70, 40), "c": (69, 26), "x": (75, 34)}     # kendang-ish congas, shaker, cabasa, claves


def song_day():
    """'Pagi di Sukamakmur' - C major, 96 bpm. Intro | A marimba | A' flute + imbal |
    B call-and-response | C kalimba breakdown + angklung | A'' flute over marimba."""
    s = Song("day", 96, 44, key=0, rt60=1.7, seed=11)
    s.chords(0, "C | Am7 | Fmaj7 | G7sus4")
    s.chords(4, "C | Am7 | Fmaj7 | G | C | Am7 | Dm7 G7 | C")
    s.chords(12, "C | Am7 | Fmaj7 | G | C | Am7 | Dm7 G7 | C C7")
    s.chords(20, "Fmaj7 | G | Em7 | Am7 | Dm7 | G | Em7 A7 | Dm7 G7sus4")
    s.chords(28, "Am7 | Fmaj7 | C | G | Am7 | Fmaj7 | Dm7 | G7sus4 G7")
    s.chords(36, "C | Am7 | Fmaj7 | G | C | Am7 | Dm7 G7 | C G7sus4")
    mar = s.part("marimba", MARIMBA, pan=-0.1, level=-14, hp=90, rev=0.22, shelf=(-1, 2))
    fl = s.part("flute", FLUTE, bank=EXPR, pan=0.12, level=-15, hp=150, rev=0.3, jitter=0.01, gate=0.97, expr=2,
                shelf=(0, 3))
    imb = s.part("imbal", MARIMBA, pan=0.3, level=-22, hp=110, rev=0.25, velrand=6)
    vib = s.part("vibes", VIBES, pan=0.35, level=-21, hp=150, rev=0.35, gate=0.8)
    kal = s.part("kalimba", KALIMBA, pan=-0.25, level=-17, hp=150, rev=0.3)
    gtr = s.part("guitar", NYLON, pan=-0.35, level=-20, hp=150, rev=0.18, jitter=0.004, shelf=(-2, 3))
    bs = s.part("bass", ABASS, pan=0.0, level=-20, hp=35, lp=2500, rev=0.05, width=0.0)
    strg = s.part("strings", STRINGS_SLOW, bank=EXPR, level=-25, hp=180, rev=0.45, expr=2)
    ang = s.part("angklung", MARIMBA, pan=0.2, level=-24, hp=250, rev=0.4, velrand=3)
    cel = s.part("celesta", CELESTA, pan=0.3, level=-24, hp=300, rev=0.5)
    kd = s.part("kendang", 0, drum=True, pan=0.25, level=-24, hp=60, rev=0.12, jitter=0.005, width=0.6)
    sh = s.part("shaker", 0, drum=True, pan=-0.45, level=-33, hp=300, lp=9000, rev=0.1, jitter=0.004, shelf=(0, -3))

    A = ("E5:1 G5:.5 A5:.5 G5:1 E5:.5 D5:.5 | C5:1.5 D5:.5 E5:1 r:1 | A4:.5 C5:.5 D5:.5 E5:.5 G5:1 E5:1 | "
         "D5:2 r:1 C5:.5 D5:.5 | E5:1 G5:.5 A5:.5 G5:1 E5:.5 G5:.5 | C6:1.5 A5:.5 G5:1 E5:1 | "
         "F5:1 A5:.5 F5:.5 G5:.5 F5:.5 D5:.5 B4:.5 | ")
    A2 = ("E5:1 G5:.5 A5:.5 G5:1 E5:.5 D5:.5 | C5:1.5 D5:.5 E5:1 r:1 | A4:.5 C5:.5 D5:.5 E5:.5 G5:.75 A5:.25 G5:.5 E5:.5 | "
          "D5:2 r:1 C5:.5 D5:.5 | E5:1 G5:.5 A5:.5 G5:1 E5:.5 G5:.5 | C6:1.5 A5:.5 G5:.5 A5:.5 E5:1 | "
          "F5:1 A5:.5 F5:.5 G5:.5 F5:.5 D5:.5 B4:.5 | ")
    # intro: bonang-like vibraphone figure, gong on the downbeat of the cycle
    s.gong(0, "gong", "C2", 0)
    imbal(vib, 0, 4, [[2, 1, 0, 1, 2, 1, 3, None], [2, 1, 0, 1, 2, 3, 2, None]], anchor=72, lo=67, hi=88, vel=50)
    arp(gtr, 0, 1, [0, None, 2, 3, None, 2, 1, 2], vel=50)
    strum(gtr, 1, 3, [(0, "D", 1, .9), (1, "D", .8, .45), (1.5, "U", .7, .45), (2.5, "U", .7, .45), (3, "D", .85, .45), (3.5, "U", .7, .4)], vel=58)
    bass(bs, 2, 2, "island")
    hits(sh, 2, 2, "s.S.s.S.s.S.s.S.", DR)
    sparkle(cel, 3 * 4 + 2, Chord("G7sus4"), lo=79, count=6, step=0.25, vel=44)
    # A: marimba melody
    mel(mar, 4, A + "C5:3 r:1", vel=82, roll=1.5)
    GS = [(0, "D", 1, .9), (1, "D", .8, .45), (1.5, "U", .7, .45), (2.5, "U", .7, .45), (3, "D", .85, .45), (3.5, "U", .7, .4)]
    strum(gtr, 4, 8, GS, vel=60)
    bass(bs, 4, 8, "island")
    hits(kd, 4, 7, "D.....t.D.T.t...", DR)
    hits(kd, 11, 1, "D..t..t.D.T.TtTt", DR)
    hits(sh, 4, 8, "s.S.s.S.s.S.s.S.", DR)
    sparkle(cel, 11 * 4 + 3, Chord("C"), lo=84, count=4, step=0.25, vel=40)
    # A': flute takes the tune, marimba interlocks below (imbal)
    mel(fl, 12, A2 + "C5:2 r:.5 E5:.5 G5:.5 Bb5:.5", vel=80, scoop=0.5)
    for b in range(12, 20):
        dy = voice(s.chord_at(b * 4), 2, 64, 76, avoid=s.sounding(b * 4, b * 4 + 3.8))
        s.reg(b * 4, b * 4 + 3.8, dy)
        for p in dy:
            vib.n(b * 4, 3.8, p, 36)
    imbal(imb, 12, 8, [[0, 2, 1, 2, 3, 2, 1, 2], [0, 2, 1, 2, 0, 2, 3, 2]], anchor=60, lo=55, hi=76, vel=50)
    strum(gtr, 12, 8, GS, vel=58)
    bass(bs, 12, 8, "island")
    hits(kd, 12, 7, "D.....t.D.T.t...", DR)
    hits(kd, 19, 1, "D..t..t.D.T.TtTt", DR)
    hits(sh, 12, 8, "s.S.s.S.s.S.s.S.", DR)
    sparkle(cel, 19 * 4 + 2, Chord("C7"), lo=84, count=6, step=0.25, vel=42)
    # B: call (marimba) and response (flute), then together in harmony
    s.gong(20, "kempul", "F3", -3)
    mel(mar, 20, "A5:.5 G5:.5 E5:.5 G5:.5 A5:1 r:1 | r:4 | G5:.5 E5:.5 D5:.5 E5:.5 B4:1 r:1 | r:4 | r:4 | r:4 | r:4 | r:4", vel=80, roll=1.5)
    Bfl = mel(fl, 20, "r:4 | r:.5 D5:.5 G5:.5 A5:.5 B5:1.5 r:.5 | r:4 | r:.5 C5:.5 E5:.5 G5:.5 A5:2 | "
              "F5:1 E5:.5 F5:.5 A5:1.5 C6:.5 | B5:1 A5:.5 G5:.5 D5:2 | E5:1 G5:.5 B5:.5 A5:.5 G5:.5 E5:.5 C#5:.5 | "
              "D5:1.5 E5:.5 F5:1 G5:1", vel=80, scoop=0.5)
    harmony_below(mar, [n for n in Bfl if n[0] >= 24 * 4], 66)
    strum(gtr, 20, 8, GS, vel=56)
    bass(bs, 20, 8, "island")
    pad(strg, 20, 8, lo=55, hi=74, n=4, vel=70, cc=2, lvl=90)
    hits(kd, 20, 3, "D.....t.D.T.t...", DR)
    hits(kd, 23, 1, "D..t..t.D.T.t.T.", DR)
    hits(kd, 24, 3, "D..t..t.D.T.t...", DR)
    hits(kd, 27, 1, "D..t..t.D.TtTtTt", DR)
    hits(sh, 20, 8, "s.S.s.S.s.S.s.S.", DR)
    # C: breakdown - kalimba ostinato, fingerpicked guitar, angklung swell, suling-like flute
    K1 = ("A4:.5 C5:.5 E5:.5 D5:.5 C5:.5 A4:.5 G4:.5 A4:.5 | A4:.5 C5:.5 E5:.5 G5:.5 E5:.5 C5:.5 A4:.5 C5:.5 | "
          "G4:.5 C5:.5 E5:.5 D5:.5 C5:.5 G4:.5 E4:.5 G4:.5 | G4:.5 B4:.5 D5:.5 G5:.5 D5:.5 B4:.5 A4:.5 B4:.5")
    K2 = ("A4:.5 C5:.5 E5:.5 D5:.5 C5:.5 A4:.5 G4:.5 A4:.5 | A4:.5 C5:.5 E5:.5 G5:.5 E5:.5 C5:.5 A4:.5 C5:.5 | "
          "A4:.5 D5:.5 F5:.5 E5:.5 D5:.5 A4:.5 F4:.5 A4:.5 | G4:.5 C5:.5 D5:.5 F5:.5 D5:.5 B4:.5 G4:.5 B4:.5")
    s.gong(28, "gong", "A1", -4)
    mel(kal, 28, K1 + " | " + K2, vel=66, arch=8)
    mel(fl, 28, "r:4 | r:4 | r:4 | r:4 | r:2 E5:1 G5:1 | A5:3 G5:1 | F5:2 E5:1 D5:1 | D5:2 r:1 C5:.5 D5:.5", vel=74, scoop=0.6)
    arp(gtr, 28, 8, [0, 2, 1, 2, 3, 2, 1, 2], vel=48)
    bass(bs, 28, 8, "half", vel=70)
    pad(strg, 28, 8, lo=55, hi=74, n=4, vel=70, cc=2, lvl=80)
    hits(sh, 28, 8, "s...s.S.s...s.S.", DR)
    for b in range(32, 36):
        ch = s.chord_at(b * 4)
        angklung(ang, b * 4, b * 4 + 3.6, voice(ch, 3, 64, 76, avoid=s.sounding(b * 4, b * 4 + 3.6)), vel=46)
    # A'': flute with the marimba an octave below, full band
    s.gong(36, "kempul", "C3", -3)
    mel(fl, 36, A + "C5:2 r:2", vel=84, scoop=0.4)
    mel(mar, 36, A + "C5:2 r:2", vel=72, shift=-12, roll=1.5)
    strum(gtr, 36, 8, GS, vel=60)
    bass(bs, 36, 8, "island")
    pad(strg, 36, 8, lo=55, hi=74, n=4, vel=64, cc=2, lvl=70)
    hits(kd, 36, 7, "D.....t.D.T.t...", DR)
    hits(kd, 43, 1, "D..t..t.D.T.TtTt", DR)
    hits(sh, 36, 8, "s.S.s.S.s.S.s.S.", DR)
    sparkle(cel, 43 * 4 + 2, Chord("G7sus4"), lo=79, count=6, step=0.25, vel=42)
    expr_curve(fl, 2, lo=72, hi=116, vib=34)
    return s


def song_title():
    """'Sawit The Franchise' title - F major, 84 bpm. Harp + celesta intro, the main theme
    on low flute with strings, a marimba/vibraphone B with a cello counter-line, outro."""
    s = Song("title", 84, 24, key=5, rt60=2.4, seed=5)
    s.chords(0, "Fmaj7 | Bbmaj7 | Fmaj7 | C9sus4")
    s.chords(4, "F | Dm7 | Bbmaj7 | C | F | Dm7 | Gm7 C7 | F")
    s.chords(12, "Bbmaj7 | C | Am7 | Dm7 | Gm7 | C/E | Bbmaj7 | C7sus4 C7")
    s.chords(20, "Bbmaj7 | C | Dm7 | C9sus4")
    fl = s.part("flute", FLUTE, bank=EXPR, pan=0.05, level=-14, hp=140, rev=0.34, jitter=0.01, gate=0.97, expr=2,
                shelf=(0, 3))
    harp = s.part("harp", HARP, pan=-0.3, level=-19, hp=90, rev=0.4)
    cel = s.part("celesta", CELESTA, pan=0.3, level=-20, hp=250, rev=0.45)
    strg = s.part("strings", STRINGS_SLOW, bank=EXPR, level=-21, hp=120, rev=0.5, expr=2)
    vln = s.part("violins", STRINGS_SLOW, bank=21, pan=0.2, level=-24, hp=300, rev=0.5, expr=2, jitter=0.012)
    cello = s.part("cello", CELLO, bank=EXPR, pan=-0.2, level=-20, hp=60, rev=0.35, expr=2, jitter=0.01)
    mar = s.part("marimba", MARIMBA, pan=-0.15, level=-15, hp=90, rev=0.25)
    vib = s.part("vibes", VIBES, pan=0.25, level=-19, hp=140, rev=0.35, gate=0.9)
    gtr = s.part("guitar", NYLON, pan=-0.35, level=-21, hp=150, rev=0.2, jitter=0.004, shelf=(-2, 3))
    bs = s.part("bass", ABASS, level=-21, hp=35, lp=2400, rev=0.06, width=0.0)
    kd = s.part("kendang", 0, drum=True, pan=0.25, level=-26, hp=60, rev=0.15, width=0.6)
    ang = s.part("angklung", MARIMBA, pan=0.2, level=-24, hp=250, rev=0.45, velrand=3)
    glk = s.part("glock", GLOCK, pan=0.35, level=-27, hp=400, rev=0.5)

    s.gong(0, "gong", "F1", 0)
    mel(cel, 0, "A5:.5 C6:.5 D6:.5 C6:2.5 | r:4 | A5:.5 C6:.5 D6:.5 C6:2.5 | Bb5:.5 C6:.5 D6:.5 C6:2.5", vel=58)
    pad(strg, 0, 4, lo=53, hi=72, vel=66, cc=2, swell=(0.4, 1.0, 0.8), lvl=90)
    for b in range(4):
        ch = s.chord_at(b * 4)
        gliss(harp, b * 4, 53, 81, ch.core(), 1.5, vel=52)
        gliss(harp, b * 4 + 2, 60, 84, ch.core(), 1.5, vel=44)
    # A: the main theme (day tune in F), low flute, strings grow under it
    A = ("A4:1 C5:.5 D5:.5 C5:1 A4:.5 G4:.5 | F4:1.5 G4:.5 A4:1 r:1 | D4:.5 F4:.5 G4:.5 A4:.5 C5:1 A4:1 | "
         "G4:2 r:1 F4:.5 G4:.5 | A4:1 C5:.5 D5:.5 C5:1 A4:.5 C5:.5 | F5:1.5 D5:.5 C5:1 A4:1 | "
         "Bb4:1 D5:.5 Bb4:.5 C5:.5 Bb4:.5 G4:.5 E4:.5 | F4:3 r:1")
    mel(fl, 4, A, vel=86, scoop=0.4)
    mel(vln, 8, "A5:1 C6:.5 D6:.5 C6:1 A5:.5 C6:.5 | F6:1.5 D6:.5 C6:1 A5:1 | Bb5:1 D6:.5 Bb5:.5 C6:.5 Bb5:.5 G5:.5 E5:.5 | F5:3 r:1", vel=60)
    pad(strg, 4, 8, lo=48, hi=65, vel=64, cc=2, lvl=78)
    arp(harp, 4, 8, [0, 2, 3, 1, 3, 2, 3, 1], vel=42, lo=65, hi=84, blo=41)
    arp(gtr, 4, 8, [0, None, 2, 3, None, 2, 1, 2], vel=46)
    bass(bs, 4, 8, "half", vel=72)
    sparkle(glk, 11 * 4 + 2, Chord("F"), lo=84, count=5, vel=40)
    # B: marimba + vibraphone tune, cello counter-line, gentle kendang and strum
    s.gong(12, "kempul", "Bb2", -3)
    B = ("D6:1 C6:.5 A5:.5 F5:1 A5:1 | G5:2 E5:1 G5:1 | C6:1.5 A5:.5 G5:1 E5:1 | F5:3 r:1 | "
         "Bb5:1 A5:.5 G5:.5 D5:1 F5:1 | G5:1.5 E5:.5 C5:2 | D5:1 F5:1 A5:1 C6:1 | Bb5:1.5 G5:.5 E5:2")
    mel(mar, 12, B, vel=80, roll=1.5)
    mel(vib, 12, B, vel=52)
    mel(cello, 12, "F3:4 | E3:2 G3:2 | E3:4 | F3:2 A3:2 | Bb3:4 | G3:2 E3:2 | F3:2 A3:2 | Bb3:2 G3:2", vel=70)
    strum(gtr, 12, 8, [(0, "D", 1, .9), (1.5, "U", .7, .45), (2, "D", .85, .9), (3, "D", .8, .45), (3.5, "U", .7, .4)], vel=54)
    bass(bs, 12, 8, "island", vel=72)
    pad(strg, 12, 8, lo=55, hi=74, vel=60, cc=2, lvl=70)
    hits(kd, 12, 7, "D.......D.T.t...", DR)
    hits(kd, 19, 1, "D..t..t.D.T.TtTt", DR)
    sparkle(glk, 19 * 4 + 2, Chord("C7"), lo=84, count=5, vel=40)
    # outro: flute sighs, harp and angklung, back to the gong
    mel(fl, 20, "A5:2 F5:2 | G5:4 | F5:2 D5:2 | C5:4", vel=70, scoop=0.5)
    arp(harp, 20, 4, [0, 2, 3, 1, 3, 2, 3, 1], vel=40, lo=60, hi=77, blo=41)
    pad(strg, 20, 4, lo=53, hi=72, vel=64, cc=2, swell=(0.8, 1.0, 0.5), lvl=80)
    bass(bs, 20, 4, "whole", vel=64)
    angklung(ang, 20 * 4, 21 * 4 + 3.5, voice(Chord("Bbmaj7"), 3, 64, 76, avoid=s.sounding(80, 87.5)), vel=42)
    angklung(ang, 22 * 4, 23 * 4 + 2, [pitch("F4"), pitch("A4"), pitch("C5")], vel=38)
    expr_curve(fl, 2, lo=70, hi=116, vib=36)
    expr_curve(vln, 2, lo=55, hi=95, vib=0)
    expr_curve(cello, 2, lo=65, hi=105, vib=0)
    return s


def song_evening():
    """'Senja di Kebun' - keroncong-style sunset, Bb major, 74 bpm: cak/cuk ukuleles on the
    off-beats, pizzicato cello bass, nylon-guitar runs, flute obbligato, minor-iv colour."""
    s = Song("evening", 74, 28, key=10, rt60=2.2, seed=21)
    s.chords(0, "Bbmaj7 | Gm7 | Cm7 | F7")
    s.chords(4, "Bb | Bb | F7 | F7 | Bb | Bb7 | Eb | Eb")
    s.chords(12, "Cm7 | F7 | Dm7 | Gm7 | Cm7 | Ebm6 | Bb/F | F7sus4 F7")
    s.chords(20, "Bb | Bb | F7 | F7 | Bb | Bb7 | Eb Ebm6 | Bb F7")
    fl = s.part("flute", FLUTE, bank=EXPR, pan=0.1, level=-14, hp=150, rev=0.35, jitter=0.012, gate=0.97, expr=2,
                shelf=(0, 3))
    cak = s.part("cak", UKULELE, bank=8, pan=-0.3, level=-22, hp=200, rev=0.18, jitter=0.004)
    cuk = s.part("cuk", UKULELE, bank=8, pan=0.35, level=-26, hp=250, rev=0.18, jitter=0.004)
    cel = s.part("cello", PIZZ, bank=40, pan=-0.05, level=-20, hp=45, lp=3000, rev=0.12, width=0.3)
    gtr = s.part("guitar", NYLON, pan=-0.2, level=-19, hp=150, rev=0.25, jitter=0.006, shelf=(-2, 3))
    strg = s.part("strings", STRINGS_SLOW, bank=EXPR, level=-25, hp=160, rev=0.5, expr=2)
    vib = s.part("vibes", VIBES, pan=0.3, level=-23, hp=160, rev=0.4, gate=0.9)
    BB = scale_pcs(10)

    # intro: guitar alone (rolling arpeggio), cello, strings; flute pickup
    arp(gtr, 0, 4, [0, 2, 3, 1, 3, 2, 3, 1], step=0.25, vel=46, lo=58, hi=74, blo=38, ring=3)
    bass(cel, 0, 4, "whole", lo=36, vel=66)
    pad(strg, 0, 4, lo=55, hi=72, vel=60, cc=2, swell=(0.4, 1.0, 0.8), lvl=80)
    mel(fl, 0, "r:4 | r:4 | r:4 | r:3 C5:.5 Eb5:.5", vel=70)
    CAK = [(0.5, "D", 1, .3), (1.5, "U", .85, .3), (2.5, "D", 1, .3), (3.5, "U", .85, .3)]
    CUK = [(0.25, "D", .8, .2), (0.75, "U", .7, .2), (1.25, "D", .8, .2), (1.75, "U", .7, .2),
           (2.25, "D", .8, .2), (2.75, "U", .7, .2), (3.25, "D", .8, .2), (3.75, "U", .7, .2)]
    A = ("D5:1.5 Eb5:.5 F5:1 Bb5:1 | A5:1.5 G5:.5 F5:2 | Eb5:1.5 D5:.5 C5:1 A4:1 | C5:3 r:1 | "
         "D5:1 F5:1 Bb5:1.5 C6:.5 | D6:1.5 C6:.5 Ab5:2 | G5:1.5 F5:.5 Eb5:1 G5:1 | Bb5:3 r:1")
    B = ("G5:1.5 F5:.5 Eb5:1 C5:1 | F5:2 Eb5:1 C5:1 | A5:1.5 G5:.5 F5:1 D5:1 | F5:3 r:.5 D5:.5 | "
         "Eb5:1.5 D5:.5 C5:1 G5:1 | Gb5:1.5 F5:.5 Eb5:2 | D5:1.5 C5:.5 D5:1 F5:1 | F5:2 Eb5:1.5 C5:.5")
    A2 = ("D5:1.5 Eb5:.5 F5:1 Bb5:1 | A5:1 Bb5:.5 A5:.5 G5:1 F5:1 | Eb5:1.5 D5:.5 C5:1 A4:1 | C5:2 r:1.5 F5:.5 | "
          "D6:1.5 C6:.5 Bb5:1 F5:1 | Ab5:1.5 G5:.5 F5:1 D5:1 | Eb5:1 G5:1 Gb5:1.5 Eb5:.5 | D5:2 C5:1 A4:1")
    for b0, text in ((4, A), (12, B), (20, A2)):
        mel(fl, b0, text, vel=80, scoop=0.55)
        strum(cak, b0, 8, CAK, vel=52, lo=60, hi=72, blo=0, upper=3, spread=0.006)
        strum(cuk, b0, 8, CUK, vel=40, lo=67, hi=79, blo=0, upper=2, spread=0.004)
        bass(cel, b0, 8, "keroncong", lo=36, vel=74)
        arp(gtr, b0, 8, [0, None, 2, None, 3, None, 2, None], vel=40, lo=55, hi=70, blo=38, ring=2)
    pad(strg, 12, 16, lo=55, hi=72, vel=60, cc=2, lvl=72)
    # guitar runs in the flute's rests (keroncong "gitar melodi")
    run(gtr, 7 * 4 + 3, pitch("F5"), 4, BB, vel=56)
    run(gtr, 11 * 4 + 3, pitch("Eb5"), 4, BB, vel=56)
    run(gtr, 15 * 4 + 3, pitch("C5"), 2, BB, step=0.25, vel=54)
    run(gtr, 23 * 4 + 2, pitch("A4"), 5, BB, step=0.25, vel=54, down=False)
    for b in (11, 19):
        ch = s.chord_at(b * 4 + 2)
        for p in voice(ch, 3, 67, 79, avoid=s.sounding(b * 4 + 2, b * 4 + 4)):
            vib.n(b * 4 + 2, 2, p, 44)
    vib.n(27 * 4, 3.8, pitch("D6"), 36)
    vib.n(27 * 4, 3.8, pitch("F6"), 32)
    expr_curve(fl, 2, lo=70, hi=116, vib=40)
    return s


def song_night():
    """'Malam Sunyi' - Eb major with lydian colour, 64 bpm: music box + celesta over rolled
    mellow piano, warm pad and a soft gong; lots of space."""
    s = Song("night", 64, 24, key=3, rt60=3.0, seed=31)
    A = "Ebmaj9 | Abmaj7#11 | Ebmaj9 | Abmaj7#11 | Cm9 | Abmaj7 | Fm9 | Bb7sus4"
    s.chords(0, A)
    s.chords(8, "Abmaj7 | Gm7 | Fm7 | Ebmaj7 | Abmaj7 | Gm7 | Fm9 | Bb9sus4")
    s.chords(16, A)
    mb = s.part("musicbox", MUSICBOX, pan=0.1, level=-15, hp=250, rev=0.45)
    cel = s.part("celesta", CELESTA, pan=-0.25, level=-18, hp=250, rev=0.5)
    pno = s.part("piano", MELLOW_PIANO, bank=8, pan=-0.05, level=-19, hp=60, rev=0.45, jitter=0.01, shelf=(-3, 0))
    pd = s.part("pad", WARM_PAD, level=-24, hp=120, lp=5000, rev=0.5)
    strg = s.part("strings", STRINGS_SLOW, bank=EXPR, level=-29, hp=180, rev=0.6, expr=2)
    harp = s.part("harp", HARP, pan=0.3, level=-24, hp=120, rev=0.5)
    MA = ("G5:1 Bb5:1 F5:2 | Eb6:1 D6:1 C6:2 | Bb5:1 G5:1 F5:1 G5:1 | Eb5:3 r:1 | "
          "G5:1 Bb5:.5 C6:.5 D6:2 | C6:1.5 Bb5:.5 G5:2 | Ab5:1 G5:1 F5:1 Eb5:1 | F5:3 r:1")
    MB = ("r:2 Eb5:.5 F5:.5 G5:1 | Bb5:2 F5:2 | Ab5:1.5 G5:.5 F5:1 C5:1 | G5:4 | "
          "C6:1 Eb6:1 D6:1 C6:1 | Bb5:2 G5:2 | Ab5:1 C6:1 G5:2 | F5:2 Eb5:1 F5:1")
    s.gong(0, "gong", "Eb2", -2)
    s.gong(8, "kempul", "Ab2", -6)
    s.gong(16, "kempul", "Eb3", -6)
    # A: music box; B: celesta sings, music box answers an octave up; A': music box with
    # a celesta echo a beat later (canon). Melodies first, so the chords keep clear of them.
    mel(mb, 0, MA, vel=70, arch=4)
    Bp = mel(cel, 8, MB, vel=64, arch=4)
    Ap = mel(mb, 16, MA, vel=66, arch=4)
    for t, d, p in Bp:
        if (t // 4) % 2 == 1 and d >= 1:
            mb.n(t + 1.0, d, p + 12, 42)
            s.reg(t + 1.0, t + 1.0 + d, [p + 12])
    for t, d, p in Ap:
        if d >= 2 and p + 12 <= 88:
            cel.n(t + 1.0, d, p + 12, 38)
            s.reg(t + 1.0, t + 1.0 + d, [p + 12])
    rolled(pno, 0, 24, vel=40, lo=55, hi=72, blo=31, roll=0.45, second=2.0)
    pad(pd, 0, 24, lo=51, hi=70, n=3, vel=50, cc=11, swell=(0.6, 1.0, 0.8), lvl=100)
    pad(strg, 8, 8, lo=55, hi=74, vel=60, cc=2, swell=(0.3, 1.0, 0.6), lvl=70)
    gliss(harp, 7 * 4 + 2, 63, 87, Chord("Bb7sus4").pcs, 1.5, vel=40)
    gliss(harp, 15 * 4 + 2, 63, 87, Chord("Bb9sus4").pcs, 1.5, vel=40)
    sparkle(harp, 23 * 4 + 1, Chord("Bb7sus4"), lo=70, count=6, step=1 / 3, vel=34)
    return s


def song_indoor():
    """'Rumah Juragan' - cosy lo-fi, F major, 78 bpm swung 16ths: Rhodes comping, upright
    bass, brushes, vibraphone tune with kalimba answers; tape wow + low-pass on the bus."""
    s = Song("indoor", 78, 24, key=5, rt60=1.3, lofi=True, swing16=0.58, seed=41)
    A = "Bbmaj7 | Am7 | Gm7 | C9 | Fmaj7 | Dm7 | Gm9 | C13sus4"
    s.chords(0, A)
    s.chords(8, "Bbmaj7 | Bbm6 | Am7 | D7 | Gm7 | C7 | Fmaj7 | C9sus4")
    s.chords(16, A)
    vib = s.part("vibes", VIBES, pan=0.05, level=-15, hp=150, rev=0.3, gate=0.92, jitter=0.009, shelf=(0, 3))
    ep = s.part("rhodes", EPIANO, pan=-0.2, level=-18, hp=150, rev=0.25, jitter=0.008, shelf=(-3, 2))
    bs = s.part("bass", ABASS, level=-20, hp=40, lp=1500, rev=0.05, width=0.0, jitter=0.008)
    kal = s.part("kalimba", KALIMBA, pan=0.35, level=-20, hp=180, rev=0.35)
    dr = s.part("drums", 40, drum=True, level=-23, hp=60, rev=0.12, jitter=0.006, width=0.7)
    pd = s.part("pad", WARM_PAD, level=-29, hp=150, lp=4000, rev=0.4)
    KIT = {"K": (36, 70), "k": (36, 50), "S": (38, 52), "s": (38, 30), "h": (42, 30), "H": (42, 42),
           "w": (40, 26), "r": (51, 26)}
    MA = ("r:.5 D5:.5 F5:.5 A5:.5 C6:1 A5:1 | G5:1.5 E5:.5 C5:2 | r:.5 Bb4:.5 D5:.5 F5:.5 A5:1 G5:1 | "
          "E5:2 r:1 C5:.5 D5:.5 | E5:1.5 C5:.5 A4:1 r:1 | r:.5 F5:.5 A5:.5 C6:.5 D6:1 A5:1 | "
          "Bb5:1 A5:.5 G5:.5 F5:1 D5:1 | G5:3 r:1")
    MB = ("r:1 F5:.5 A5:.5 C6:2 | Db6:1.5 C6:.5 Bb5:1 G5:1 | A5:1.5 G5:.5 E5:2 | F#5:1 A5:.5 C6:.5 A5:2 | "
          "Bb5:1.5 A5:.5 G5:1 F5:1 | E5:1 G5:.5 Bb5:.5 A5:1 G5:1 | A5:1.5 G5:.5 E5:1 C5:1 | D5:2 r:2")
    MA2 = ("r:.5 D5:.5 F5:.5 A5:.5 C6:.75 D6:.25 C6:.5 A5:.5 | G5:1.5 E5:.5 C5:2 | r:.5 Bb4:.5 D5:.5 F5:.5 A5:1 G5:1 | "
           "E5:2 r:1 C5:.5 D5:.5 | E5:1.5 C5:.5 A4:1 r:1 | r:.5 F5:.5 A5:.5 C6:.5 D6:1 A5:1 | "
           "Bb5:1 A5:.5 G5:.5 F5:1 D5:1 | G5:3 r:1")
    mel(vib, 0, MA, vel=70, arch=4)
    mel(vib, 8, MB, vel=72, arch=4)
    mel(vib, 16, MA2, vel=70, arch=4)
    # Rhodes comping: two rhythms alternating per bar
    for bar in range(24):
        t0 = bar * 4
        ch = s.chord_at(t0)
        ep.prev = voice(ch, 4, 55, 72, ep.prev, avoid=s.sounding(t0, t0 + 4))
        hits_ = [(0, 1.7, 52), (2.5, 1.2, 44)] if bar % 2 == 0 else [(0, 2.6, 50), (3.5, 0.45, 40)]
        for off, d, v in hits_:
            c2 = s.chord_at(t0 + off)
            vv = ep.prev if c2 is ch else voice(c2, 4, 55, 72, ep.prev, avoid=s.sounding(t0 + off, t0 + off + d))
            s.reg(t0 + off, t0 + off + d, vv)
            for i, p in enumerate(vv):
                ep.n(t0 + off + 0.012 * i, d, p, v - i)
    bass(bs, 0, 24, "lofi", lo=33, vel=76)
    pad(pd, 0, 24, lo=55, hi=72, n=3, vel=46, cc=11, lvl=90)
    hits(dr, 0, 1, "K......k..K.....", KIT)
    hits(dr, 1, 23, "K...S.....K.S..s", KIT)
    hits(dr, 0, 24, "h.h.h.hhh.h.h.hh", KIT)
    for b in (7, 15, 23):
        hits(dr, b, 1, "..............ss", KIT)
    # kalimba answers in B and A'
    for b, fig in ((9, "r:3 Bb5:.25 G5:.25 F5:.5"), (11, "r:2.5 A5:.5 C6:.5 D6:.5"), (13, "r:3 E6:.5 C6:.5"),
                   (15, "r:2.5 C6:.5 A5:.5 G5:.5"), (19, "r:2.5 C6:.5 A5:.5 G5:.5"), (23, "r:2 C6:.5 A5:.5 G5:.5 F5:.5")):
        mel(kal, b, fig, vel=58, arch=0)
    return s


def stinger_rare():
    """SR/SSR catch: rising pentatonic sparkle into a ringing C(add9) with angklung shimmer"""
    s = Song("rare", 132, 1, key=0, loop=False, rt60=1.8, seed=51)
    s.tail_beats = 3.0
    s.max_len, s.target = 2.9, -17.0
    s.gong_level = -32.0      # just a soft low bloom under the sparkle
    s.chords(0, "Cadd9")
    s.harm.append([4, 8, Chord("Cadd9")])
    mar = s.part("marimba", MARIMBA, level=-16, hp=150, rev=0.3)
    glk = s.part("glock", GLOCK, pan=0.3, level=-19, hp=400, rev=0.4)
    vib = s.part("vibes", VIBES, pan=-0.25, level=-18, hp=200, rev=0.45)
    strg = s.part("strings", STRINGS_SLOW, bank=EXPR, level=-20, hp=150, rev=0.5, expr=2)
    ang = s.part("angklung", MARIMBA, pan=0.15, level=-22, hp=300, rev=0.4, velrand=3)
    harp = s.part("harp", HARP, pan=-0.3, level=-20, hp=150, rev=0.45)
    tri = s.part("triangle", 0, drum=True, pan=0.4, level=-28, hp=2000, rev=0.3)
    run_ = ["G4", "A4", "C5", "D5", "E5", "G5"]
    for i, nm in enumerate(run_):
        mar.n(i * 0.25, 0.5, pitch(nm), 70 + i * 4)
        glk.n(i * 0.25, 0.5, pitch(nm) + 12, 50 + i * 3)
    for nm in ["C5", "E5", "G5", "D6"]:
        vib.n(1.5, 5, pitch(nm), 72)
    mar.n(1.5, 0.5, pitch("C6"), 92)
    glk.n(1.5, 3, pitch("E6"), 70)
    glk.n(1.5, 3, pitch("C7"), 60)
    gliss(harp, 0.25, 60, 88, {0, 2, 4, 7, 9}, 1.25, vel=56)
    for p in voice(Chord("Cadd9"), 4, 55, 76):
        strg.n(1.5, 4.0, p, 80)
    strg.cc(1.45, 2, 100)
    strg.cc(3.0, 2, 90)
    strg.cc(4.8, 2, 40)
    angklung(ang, 1.5, 4.6, [pitch("E6"), pitch("G6")], vel=46, rate_hz=10)
    tri.n(1.5, 1, 81, 60)
    s.gong(0, "kempul", "C3", -6, beat=1.5)
    return s


def stinger_newday():
    """new-day jingle: the day theme's head on marimba + flute, ringing Cmaj9 with celesta"""
    s = Song("newday", 108, 1, key=0, loop=False, rt60=1.8, seed=61)
    s.tail_beats = 2.5
    s.max_len, s.target = 2.8, -17.0
    s.gong_level = -30.0
    s.chords(0, "Cmaj7")
    s.harm.append([4, 8, Chord("Cmaj9")])
    mar = s.part("marimba", MARIMBA, level=-15, hp=120, rev=0.28)
    fl = s.part("flute", FLUTE, bank=EXPR, pan=0.15, level=-17, hp=200, rev=0.35, expr=2, gate=0.98)
    cel = s.part("celesta", CELESTA, pan=-0.3, level=-20, hp=300, rev=0.45)
    gtr = s.part("guitar", NYLON, pan=-0.35, level=-21, hp=120, rev=0.25)
    mel(mar, 0, "E5:.5 G5:.5 A5:.5 G5:.5 C6:2", vel=80, roll=1.5)
    mel(fl, 0, "r:1.5 G5:.5 C6:2", vel=74)
    fl.cc(0, 2, 90)
    fl.cc(2, 2, 100)
    fl.cc(3.5, 2, 70)
    fl.cc(4.3, 2, 30)
    for i, p in enumerate(voice(Chord("Cmaj9"), 4, 52, 67)):
        gtr.n(2 + i * 0.03, 3, p, 58)
    gtr.n(2, 3, pitch("C3"), 60)
    sparkle(cel, 2, Chord("Cmaj9"), lo=79, count=5, step=1 / 6, vel=50)
    s.gong(0, "kempul", "C3", -9, beat=2)
    return s


SONGS = {"title": song_title, "day": song_day, "evening": song_evening, "night": song_night,
         "indoor": song_indoor, "rare": stinger_rare, "newday": stinger_newday}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="subset of " + ", ".join(SONGS))
    ap.add_argument("--png", help="write waveform/spectrogram overview PNGs into this folder")
    args = ap.parse_args()
    names = args.names or list(SONGS)
    os.makedirs(OUT, exist_ok=True)
    results = []
    for n in names:
        print(f"[{n}]")
        results.append(build(SONGS[n](), args.png))
    tot = sum(r["bytes"] for r in results)
    print(f"total {tot / 1024:.0f} KB for {len(results)} files")


if __name__ == "__main__":
    main()

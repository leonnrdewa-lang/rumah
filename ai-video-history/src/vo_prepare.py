#!/usr/bin/env python3
"""Raw TTS takes -> tightened takes + word timings.
 1. faster-whisper gives word times; 2. long internal pauses (TTS artefacts) are shortened;
 3. script words (not ASR spelling) are mapped onto those times for captions.
Usage: vo_prepare.py <raw_dir> <out_dir>    raw_dir holds L1.wav ... L11.wav"""
import difflib, json, os, re, subprocess, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import LINES
RAW, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
SR = 24000; HOP = 240
MAXGAP, KEEPGAP, LEAD, TAIL = 0.36, 0.26, 0.05, 0.22

def load(p):
    with wave.open(p) as w:
        assert w.getsampwidth() == 2
        a = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
        if w.getnchannels() > 1: a = a.reshape(-1, w.getnchannels()).mean(1)
        return a, w.getframerate()

def save(p, a, sr):
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype('<i2').tobytes())

def asr_words(paths):
    from faster_whisper import WhisperModel
    m = WhisperModel('small.en', device='cpu', compute_type='int8', cpu_threads=8); res = {}
    for n, p in paths.items():
        segs, _ = m.transcribe(p, word_timestamps=True, language='en', beam_size=5)
        res[n] = [[w.word.strip(), w.start, w.end] for s in segs for w in s.words]
    return res

norm = lambda s: re.sub(r"[^a-z0-9']", '', s.lower().replace('modelling', 'modeling'))

def tighten(x):
    n = len(x) // HOP; env = 20 * np.log10(np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(1)) + 1e-9)
    act = env > env.max() - 40
    act = np.convolve(act, np.ones(5), 'same') > 0
    idx = np.where(act)[0]; f, l = idx[0], idx[-1]
    start = max(0, int((f * HOP / SR - LEAD) * SR)); end = min(len(x), int((l * HOP / SR + HOP / SR + TAIL) * SR))
    segs, removed, i = [], [], f
    cur = start
    while i <= l:
        if not act[i]:
            j = i
            while j <= l and not act[j]: j += 1
            if (j - i) * HOP / SR > MAXGAP:
                a = i * HOP; b = j * HOP; cut0 = a + int(KEEPGAP / 2 * SR); cut1 = b - int(KEEPGAP / 2 * SR)
                segs.append(x[cur:cut0]); removed.append((cut0 / SR, cut1 / SR)); cur = cut1
            i = j
        else: i += 1
    segs.append(x[cur:end]); y = np.concatenate([s * 1.0 for s in segs])
    return y, start / SR, removed

def remap(t, lead, removed):
    r = 0.0
    for a, b in removed:
        if t >= b: r += b - a
        elif t > a: r += t - a
    return max(0.0, t - lead - r)

def main():
    paths = {n: os.path.join(RAW, f'L{n}.wav') for n in LINES if os.path.exists(os.path.join(RAW, f'L{n}.wav'))}
    asr = asr_words(paths); info = {}
    for n, p in paths.items():
        x, sr = load(p); assert sr == SR, sr
        y, lead, removed = tighten(x)
        act = np.abs(y) > 0.01; rms = np.sqrt((y[act] ** 2).mean()); y = y * (10 ** (-20 / 20) / rms)
        y = np.clip(y, -0.98, 0.98)
        save(os.path.join(OUT, f'L{n}.wav'), y, SR)
        aw = [(norm(w), remap(s, lead, removed), remap(e, lead, removed)) for w, s, e in asr[n] if norm(w)]
        sw = LINES[n].split(); sn = [norm(w) for w in sw]
        sm = difflib.SequenceMatcher(None, sn, [a[0] for a in aw], autojunk=False); tm = [None] * len(sw)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size): tm[a + k] = (aw[b + k][1], aw[b + k][2])
        # fill unmatched words by interpolation
        for i, t in enumerate(tm):
            if t is None:
                pl = next((tm[k][1] for k in range(i - 1, -1, -1) if tm[k]), LEAD)
                nx = next((tm[k][0] for k in range(i + 1, len(tm)) if tm[k]), len(y) / SR - TAIL)
                gaps = [k for k in range(len(tm)) if tm[k] is None]
                tm[i] = (pl, max(pl + 0.05, min(nx, pl + 0.4)))
        # snap word edges to the real silences of the tightened take (ASR times drift around pauses)
        env = 20 * np.log10(np.sqrt((y[:len(y) // HOP * HOP].reshape(-1, HOP) ** 2).mean(1)) + 1e-9); act = env > env.max() - 40
        runs, i0 = [], None
        for k, a_ in enumerate(act):
            if not a_ and i0 is None: i0 = k
            if a_ and i0 is not None:
                if k - i0 >= 6: runs.append((i0 * HOP / SR, k * HOP / SR))
                i0 = None
        tm = [list(t_) for t_ in tm]
        for a_, b_ in runs:
            for i in range(len(tm)):
                if a_ - .02 <= tm[i][0] < b_ - .01: tm[i][0] = b_                                   # word 'starts' inside a silence -> starts when it ends
                if tm[i][0] < a_ - .02 and a_ + .01 < tm[i][1] <= b_ + .30: tm[i][1] = a_             # word 'ends' after the silence began -> ends where it began
        for i in range(len(tm)):
            if i: tm[i][0] = max(tm[i][0], tm[i - 1][0] + .06)
            tm[i][1] = max(tm[i][1], tm[i][0] + .10)
        info[n] = dict(file=f'L{n}.wav', dur=round(len(y) / SR, 3), text=LINES[n], removed_s=round(sum(b - a for a, b in removed), 2),
                       words=[dict(w=sw[i], s=round(tm[i][0], 3), e=round(tm[i][1], 3)) for i in range(len(sw))],
                       asr=' '.join(w[0] for w in asr[n]))
        print(n, info[n]['dur'], 'trimmed', info[n]['removed_s'], '|', info[n]['asr'], flush=True)
    json.dump(info, open(os.path.join(OUT, 'vo.json'), 'w'), indent=1)

if __name__ == '__main__': main()

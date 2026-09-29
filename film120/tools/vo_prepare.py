#!/usr/bin/env python3
"""Raw narration takes -> tightened takes + word timings in the storyboard format.
  1. faster-whisper gives word times; 2. long internal pauses (TTS artefacts) are shortened; 3. script words (not ASR spelling) are mapped onto those times.
usage: vo_prepare.py SCRIPT.json RAW_DIR OUT_DIR      RAW_DIR holds <line id>.wav (mono 16-bit wav, any rate)  ->  OUT_DIR/<id>.wav + OUT_DIR/vo.json {"L01": {"dur": s, "words": [[w, s, e], ...]}}"""
import difflib, json, os, re, sys, wave
import numpy as np

SCRIPT, RAW, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
MAXGAP, KEEPGAP, LEAD, TAIL = 0.42, 0.30, 0.04, 0.16
norm = lambda s: re.sub(r"[^a-z0-9']", '', s.lower())


def load(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
        if w.getnchannels() > 1: a = a.reshape(-1, w.getnchannels()).mean(1)
        return a, w.getframerate()


def save(p, a, sr):
    with wave.open(p, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(a, -1, 1) * 32767).astype('<i2').tobytes())


def asr_words(paths):
    from faster_whisper import WhisperModel
    m = WhisperModel('small.en', device='cpu', compute_type='int8', cpu_threads=8); res = {}
    for n, p in paths.items():
        segs, _ = m.transcribe(p, word_timestamps=True, language='en', beam_size=5); res[n] = [[w.word.strip(), w.start, w.end] for s in segs for w in s.words]
    return res


def tighten(x, sr, hop):
    n = len(x) // hop; env = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9); act = np.convolve(env > env.max() - 40, np.ones(5), 'same') > 0
    idx = np.where(act)[0]; f, l = idx[0], idx[-1]; start = max(0, int((f * hop / sr - LEAD) * sr)); end = min(len(x), int((l * hop / sr + hop / sr + TAIL) * sr))
    segs, removed, i, cur = [], [], f, start
    while i <= l:
        if not act[i]:
            j = i
            while j <= l and not act[j]: j += 1
            if (j - i) * hop / sr > MAXGAP:
                a, b = i * hop, j * hop; cut0, cut1 = a + int(KEEPGAP / 2 * sr), b - int(KEEPGAP / 2 * sr); segs.append(x[cur:cut0]); removed.append((cut0 / sr, cut1 / sr)); cur = cut1
            i = j
        else: i += 1
    segs.append(x[cur:end]); return np.concatenate(segs), start / sr, removed


def remap(t, lead, removed):
    r = 0.0
    for a, b in removed:
        if t >= b: r += b - a
        elif t > a: r += t - a
    return max(0.0, t - lead - r)


def main():
    lines = json.load(open(SCRIPT))['lines']; paths = {l['id']: os.path.join(RAW, l['id'] + '.wav') for l in lines if os.path.exists(os.path.join(RAW, l['id'] + '.wav'))}
    asr = asr_words(paths); vo = {}; report = {}
    for ln in lines:
        n = ln['id']
        if n not in paths: print('MISSING take', n); continue
        x, sr = load(paths[n]); hop = int(sr * .01); y, lead, removed = tighten(x, sr, hop)
        act = np.abs(y) > 0.01; rms = np.sqrt((y[act] ** 2).mean()); y = np.clip(y * (10 ** (-20 / 20) / rms), -.98, .98); save(os.path.join(OUT, n + '.wav'), y, sr)
        aw = [(norm(w), remap(s, lead, removed), remap(e, lead, removed)) for w, s, e in asr[n] if norm(w)]; sw = ln['text'].split(); sn = [norm(w) for w in sw]
        sm = difflib.SequenceMatcher(None, sn, [a[0] for a in aw], autojunk=False); tm = [None] * len(sw)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size): tm[a + k] = (aw[b + k][1], aw[b + k][2])
        for i, t in enumerate(tm):
            if t is None:
                pl = next((tm[k][1] for k in range(i - 1, -1, -1) if tm[k]), LEAD); nx = next((tm[k][0] for k in range(i + 1, len(tm)) if tm[k]), len(y) / sr - TAIL); tm[i] = (pl, max(pl + 0.05, min(nx, pl + 0.4)))
        env = 20 * np.log10(np.sqrt((y[:len(y) // hop * hop].reshape(-1, hop) ** 2).mean(1)) + 1e-9); act2 = env > env.max() - 40; runs, i0 = [], None
        for k, a_ in enumerate(act2):
            if not a_ and i0 is None: i0 = k
            if a_ and i0 is not None:
                if k - i0 >= 6: runs.append((i0 * hop / sr, k * hop / sr))
                i0 = None
        tm = [list(t_) for t_ in tm]
        for a_, b_ in runs:
            for i in range(len(tm)):
                if a_ - .02 <= tm[i][0] < b_ - .01: tm[i][0] = b_
                if tm[i][0] < a_ - .02 and a_ + .01 < tm[i][1] <= b_ + .30: tm[i][1] = a_
        for i in range(len(tm)):
            if i: tm[i][0] = max(tm[i][0], tm[i - 1][0] + .06)
            tm[i][1] = max(tm[i][1], tm[i][0] + .10)
        vo[n] = dict(dur=round(len(y) / sr, 3), words=[[sw[i], round(tm[i][0], 3), round(tm[i][1], 3)] for i in range(len(sw))])
        report[n] = dict(asr=' '.join(w[0] for w in asr[n]), script=ln['text'], trimmed_s=round(sum(b - a for a, b in removed), 2), matched=sum(b.size for b in sm.get_matching_blocks()), n_words=len(sw))
        print(n, vo[n]['dur'], 'matched', report[n]['matched'], '/', len(sw), '| ASR:', report[n]['asr'], flush=True)
    json.dump(vo, open(os.path.join(OUT, 'vo.json'), 'w'), indent=1); json.dump(report, open(os.path.join(OUT, 'vo_report.json'), 'w'), indent=1)


if __name__ == '__main__': main()

"""Timing model: script lines placed on the 120 s timeline, processed narration word times, chapter windows, cue lookups.

data/script.json  = {"lines": [{"id": "L01", "section": "s2", "start": 8.6, "text": "..."}, ...]}
data/vo/vo.json   = {"L01": {"dur": 3.2, "words": [["This", 0.05, 0.21], ...]}, ...}   (processed takes, times relative to take start)
"""
import json, re

WINDOWS = dict(s1=(0.0, 8.0), s2=(8.0, 25.0), s3=(25.0, 43.0), s4=(43.0, 63.0), s5=(63.0, 83.0), s6=(83.0, 104.0), s7=(104.0, 115.0), s8=(115.0, 120.0))
TOTAL = 120.0
norm = lambda s: re.sub(r"[^a-z0-9']", '', s.lower())


class Storyboard:
    def __init__(self, script_path, vo_path):
        sc = json.load(open(script_path)); vo = json.load(open(vo_path))
        self.lines = sc['lines']; self.T, self.E, self.W, self.text, self.section = {}, {}, {}, {}, {}
        for ln in self.lines:
            i = ln['id']; d = vo[i]['dur']; s = float(ln['start']); self.T[i] = s; self.E[i] = s + d; self.text[i] = ln['text']; self.section[i] = ln['section']
            self.W[i] = [(w[0], round(s + w[1], 3), round(s + w[2], 3)) for w in vo[i]['words']]
        self.win = WINDOWS

    # ---- cue lookups (absolute seconds)
    def at(self, line, idx): return self.W[line][idx][1]                   # start of word idx of a line
    def end_of(self, line, idx): return self.W[line][idx][2]
    def find(self, line, word, nth=0):
        """Start time of the nth occurrence of `word` in `line` (punctuation/case-insensitive)."""
        hits = [w for w in self.W[line] if norm(w[0]) == norm(word)]
        if len(hits) <= nth: raise KeyError(f'{word!r} #{nth} not in {line}: {self.text[line]}')
        return hits[nth][1]
    def find_any(self, word, nth=0):
        hits = [(w[1], i) for i, ws in self.W.items() for w in ws if norm(w[0]) == norm(word)]
        hits.sort()
        if len(hits) <= nth: raise KeyError(word)
        return hits[nth]

    def validate(self):
        msgs = []; prev_end = 0.0
        for ln in sorted(self.lines, key=lambda l: l['start']):
            i = ln['id']
            if self.T[i] < prev_end - 1e-6: msgs.append(f'{i} overlaps previous line')
            if self.E[i] > TOTAL: msgs.append(f'{i} runs past {TOTAL}')
            a, b = self.win[ln['section']]
            if self.T[i] < a - 0.6 or self.E[i] > b + 0.6: msgs.append(f'{i} outside its section window {a}-{b} ({self.T[i]:.2f}-{self.E[i]:.2f})')
            prev_end = self.E[i]
        return msgs

    def words_by_line(self): return self.W

    def section_of(self, t):
        for k, (a, b) in self.win.items():
            if a <= t < b: return k
        return 's8'

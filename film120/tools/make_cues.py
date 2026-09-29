#!/usr/bin/env python3
"""Resolve data/cue_spec.json against the processed narration (word times) into absolute cue times for the plan.
usage: make_cues.py CUE_SPEC.json SCRIPT.json VO.json OUT_CUES.json
spec value kinds:  number                          -> absolute seconds
                   ["L07", "Kling", 0, -0.10]      -> start of the 0th occurrence of the word 'Kling' in line L07, plus offset
                   ["L07", "Kling", 0, -0.10, "end"] -> END of that word
                   [[...], [...]]                  -> list of cues (each as above or a number)
Unresolvable words are reported and the cue is dropped (sequences fall back to their default timings)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.storyboard import Storyboard, norm


def resolve(SB, v):
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, list) and v and isinstance(v[0], str):
        line, word = v[0], v[1]; nth = v[2] if len(v) > 2 else 0; off = v[3] if len(v) > 3 else 0.0; end = len(v) > 4 and v[4] == 'end'
        hits = [w for w in SB.W[line] if norm(w[0]) == norm(word)]
        if len(hits) <= nth: raise KeyError(f'{word!r}#{nth} not in {line}: {SB.text[line]}')
        return round(hits[nth][2 if end else 1] + off, 3)
    if isinstance(v, list): return [resolve(SB, x) for x in v]
    raise ValueError(v)


def main():
    spec, script, vo, out = sys.argv[1:5]; SB = Storyboard(script, vo); res, bad = {}, []
    for k, v in json.load(open(spec)).items():
        if k.startswith('_'): continue
        try: res[k] = resolve(SB, v)
        except Exception as e: bad.append(f'{k}: {e}')
    json.dump(res, open(out, 'w'), indent=1); print(len(res), 'cues ->', out)
    for b in bad: print('UNRESOLVED', b)
    for m in SB.validate(): print('STORYBOARD', m)


if __name__ == '__main__': main()

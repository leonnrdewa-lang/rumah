#!/usr/bin/env python3
"""Mix narration + score + SFX (procedural and licensed recordings) into a 120.000 s stereo bed.
usage: mixer.py --script data/script.json --vo data/vo/vo.json --vo-dir DIR --events events.json --out mix_raw.wav [--stems DIR] [--licensed licensed.json]
events.json : [{"kind": "lock", "t": 12.3, "params": {...}}, ..., {"kind": "gate", "t": 3.3, "params": {"dur": .4}}]     (sequences' events() output)
licensed.json: {"<name>": {"file": "/path/sound.wav", "trim": [0, 1.2], "gain": 0.8}}  referenced by events of kind 'file' with params {"name": "<name>"}"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from audio.dsp import *
from audio import sfx as SFX, score as SC
from engine.storyboard import Storyboard

TOTAL = 120.0


def vo_chain(x):
    x = highpass(x, 75, 2)
    x = x + .5 * fft_shape(x, lambda f: np.exp(-((np.log2(np.maximum(f, 1) / 3200)) ** 2) / .5))                    # presence
    hop = int(.01 * SR); n = len(x) // hop; e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-9); db = 20 * np.log10(e); gr = np.clip((db - (-24)) * (1 - 1 / 3.0), 0, 12)
    g = np.interp(np.arange(len(x)), np.arange(n) * hop + hop / 2, 10 ** (-gr / 20)); return (x * g).astype(np.float32)


def duck_curve(vo, depth=.8):
    hop = int(.02 * SR); n = len(vo) // hop; e = np.sqrt((vo[:n * hop].reshape(n, hop) ** 2).mean(1)); e = np.clip(e / .05, 0, 1)
    sm = np.zeros(n, np.float32); a_att, a_rel = .5, .06
    for i in range(1, n): sm[i] = sm[i - 1] + (a_att if e[i] > sm[i - 1] else a_rel) * (e[i] - sm[i - 1])
    return np.interp(np.arange(len(vo)), np.arange(n) * hop + hop / 2, 1 - depth * np.clip(sm * 1.6, 0, 1)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    for k in ('script', 'vo', 'vo-dir', 'events', 'out'): ap.add_argument('--' + k, required=True)
    ap.add_argument('--stems', default=''); ap.add_argument('--licensed', default='')
    a = ap.parse_args(); SB = Storyboard(a.script, a.vo); N = int(TOTAL * SR)
    ev = json.load(open(a.events)); lic = json.load(open(a.licensed)) if a.licensed else {}
    gates = [(e['t'], e['t'] + e['params'].get('dur', .4)) for e in ev if e['kind'] == 'gate']
    print('score...', flush=True); music = SC.build_score(TOTAL + .6, gates)[:, :N]
    print('sfx...', flush=True); bus = Bus(N); ungated = Bus(N)
    for e in ev:
        k, t, p = e['kind'], e['t'], dict(e.get('params', {}))
        if k == 'gate': continue
        g = p.pop('gain', 1.0); tgt = ungated if p.pop('ungated', False) else bus
        if k == 'file':
            spec = lic[p['name']]; x = load_audio(spec['file'], SR, mono=False); tr = spec.get('trim')
            if tr: x = x[:, int(tr[0] * SR):int(tr[1] * SR)]
            x = fade(x[0], .003, .03)[None].repeat(2, 0) if x.shape[0] == 1 else np.stack([fade(x[0], .003, .03), fade(x[1], .003, .03)])
            tgt.add(x, t, g * spec.get('gain', 1.0))
        else: tgt.add(SFX.make(k, **p), t, g)
    print('vo...', flush=True); vo = np.zeros(N, np.float32)
    for i, t0 in SB.T.items():
        x = vo_chain(load_audio(os.path.join(a.vo_dir, f'{i}.wav'), SR)); j = int(t0 * SR); m = min(len(x), N - j); vo[j:j + m] += x[:m]
    vo_st = reverb_st(vo, .9, .07) * 1.6
    duck = duck_curve(vo, .8); mus = music * duck[None, :] * .75
    gate = np.ones(N, np.float32); f = int(.01 * SR)
    for g0, g1 in gates:
        i, j = int(g0 * SR), int(g1 * SR); gate[i:j] = 0; gate[max(0, i - f):i] = np.linspace(1, 0, min(f, i) or 1)[:len(gate[max(0, i - f):i])]; gate[j:j + f] = np.linspace(0, 1, len(gate[j:j + f]))
    sfx_b = bus.buf * .5 * (1 - .3 * np.clip(1 - duck, 0, 1))[None, :] * gate[None, :] + ungated.buf * .5
    mix = mus + sfx_b + vo_st
    fo = int(.02 * SR); mix[:, -fo:] *= np.linspace(1, 0, fo)[None, :]                          # 20 ms fade at the very end (loop seam is tonal, not a click)
    pk = float(np.abs(mix).max()); g = min(1.0, .89 / pk)
    if a.stems:
        os.makedirs(a.stems, exist_ok=True)
        for nm, b in (('music', mus), ('sfx', sfx_b), ('vo', vo_st)): write_wav(os.path.join(a.stems, nm + '.wav'), b * g)
    write_wav(a.out, mix * g); print('pre-master peak', pk, 'scaled', g, 'rms dB', 20 * np.log10(np.sqrt(((mix * g) ** 2).mean())))


if __name__ == '__main__': main()

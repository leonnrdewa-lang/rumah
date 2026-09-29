"""All timing decisions in one place: consumed by render.py (pictures) and synth_audio.py (sound)."""
import json, os
GAPS = {1: .50, 2: .50, 3: .40, 4: .40, 5: .45, 6: .50, 7: .50, 8: .30, 9: .25, 10: .80}
HOOK_END = 3.55; VO_START = 3.75; TAIL = 2.3

def build(vo):
    vo = {int(k): v for k, v in vo.items()}
    for v in vo.values(): v['words'] = [dict(w=x[0], s=x[1], e=x[2]) if isinstance(x, list) else x for x in v['words']]
    T, E, t = {}, {}, VO_START
    for n in sorted(vo):
        T[n] = t; E[n] = t + vo[n]['dur']; t = E[n] + GAPS.get(n, 0)
    total = round(E[11] + TAIL, 3)
    W = {}   # global word list per line
    for n in sorted(vo): W[n] = [(w['w'], round(T[n] + w['s'], 3), round(T[n] + w['e'], 3)) for w in vo[n]['words']]
    def at(n, i): return W[n][i][1]           # global start time of word i in line n
    sc = lambda name, a, b: dict(name=name, t0=round(a, 3), t1=round(b, 3))
    scenes = [
        sc('hook', 0, HOOK_END),
        sc('early_faces', HOOK_END, T[2] - .02),
        sc('early_montage', T[2] - .02, T[3] - .15),
        sc('timeline', T[3] - .15, E[6] + .30),
        sc('concept', E[6] + .30, E[7] + .35),
        sc('now', E[7] + .35, T[9] - .08),
        sc('styles', T[9] - .08, T[10] - .05),
        sc('compare', T[10] - .05, T[11] - .25),
        sc('finale', T[11] - .25, total),
    ]
    trans = [  # (time, type, duration) at each scene boundary
        (HOOK_END, 'iris_in', .34), (T[2] - .02, 'glitch', .16), (T[3] - .15, 'whip', .30), (E[6] + .30, 'zoomthrough', .42),
        (E[7] + .35, 'iris', .50), (T[9] - .08, 'flash', .12), (T[10] - .05, 'slat', .34), (T[11] - .25, 'dip', .40)]
    IMPACT = 1.85
    cues = dict(
        impact=IMPACT,
        # early_faces: cut on "barely" and "face"
        faces=[HOOK_END, at(1, 7), at(1, 10)],
        # early_montage: cuts on Hands / Backgrounds / And every clip
        montage=[T[2] - .02, at(2, 2), at(2, 4)],
        seconds=at(2, 10),
        # timeline nodes arrive slightly before their narration
        tl=[T[3] - .15, T[4] - .10, T[5] - .10, T[6] - .10],
        tl_jump=at(5, 6),                 # "full minute": the Tokyo shot's clock jumps to the end
        tl_sound=at(6, 5),                # "sound"
        # concept keywords
        kw=dict(light=at(7, 13), weight=at(7, 14), momentum=at(7, 15), camera=at(7, 20), time=at(7, 10), merge=at(7, 8)),
        # now: three shots
        now=[E[7] + .35, at(8, 7) - .05, at(8, 10) - .05], now_chips=[('LIGHT', at(8, 6)), ('LENS', at(8, 8)), ('CHARACTERS', at(8, 11))],
        styles=[(T[9] - .08, 'DOCUMENTARY'), (at(9, 1) - .05, 'ANIMATION'), (at(9, 2) - .05, 'PERIOD DRAMA'), (at(9, 4) - .05, 'SCIENCE FICTION')],
        compare=dict(split=T[10] - .05, full=at(10, 5) - .1, twice=at(10, 9), end=T[11] - .25),
        finale=dict(start=T[11] - .25, camera=at(11, 8), now=at(11, 9), type0=at(11, 9) + .12, sentence=at(11, 15), render=E[11] + .05, black=total),
    )
    sfx = [
        ('impact', IMPACT, dict(size=1.0)), ('riser', 0.9, dict(dur=0.95)), ('tick_hi', 0.05, {}),
        ('whoosh', HOOK_END - .1, dict(dur=.4)),
        ('glitch', T[2] - .02, {}), ('glitch', at(2, 2), {}), ('glitch', at(2, 4), {}), ('tape_stop', cues['seconds'], dict(dur=.55)),
        ('whoosh', T[3] - .3, dict(dur=.4)),
        ('chime', cues['tl'][0] + .12, dict(f=440)), ('chime', cues['tl'][1] + .12, dict(f=523.25)), ('chime', cues['tl'][2] + .12, dict(f=659.25)), ('chime', cues['tl'][3] + .12, dict(f=783.99)),
        ('whoosh', cues['tl_jump'], dict(dur=.5)),
        ('whoosh', E[6] + .05, dict(dur=.5, up=True)),
        ('tick', cues['kw']['light'], {}), ('tick', cues['kw']['weight'], {}), ('tick', cues['kw']['momentum'], {}), ('shutter', cues['kw']['camera'], {}),
        ('riser', E[7] - .9, dict(dur=1.2)),
        ('impact', cues['now'][0] + .35, dict(size=.6)), ('whoosh', cues['now'][1] - .1, dict(dur=.25)), ('whoosh', cues['now'][2] - .1, dict(dur=.25)),
        ('hit', T[9] - .08, {}), ('hit', cues['styles'][1][0], {}), ('hit', cues['styles'][2][0], {}), ('hit', cues['styles'][3][0], {}),
        ('whoosh', T[10] - .2, dict(dur=.35)),
        ('shutter', cues['compare']['twice'] + .02, {}), ('shutter', cues['compare']['twice'] + .27, {}),
        ('riser', T[11] - 1.0, dict(dur=.9)),
        ('shutter', cues['finale']['camera'] + .3, {}),
        ('tick', cues['finale']['type0'], dict(n=28, span=cues['finale']['sentence'] + .55 - cues['finale']['type0'])),
        ('impact', cues['finale']['render'], dict(size=1.0)), ('sub_drop', cues['finale']['black'] - .05, {}),
    ]
    return dict(T=T, E=E, W=W, total=total, scenes=scenes, trans=trans, cues=cues, sfx=sfx)

if __name__ == '__main__':
    import sys
    sb = build(json.load(open(sys.argv[1])))
    print('total', sb['total']); [print(s) for s in sb['scenes']]; print(sb['cues'])

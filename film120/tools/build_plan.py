#!/usr/bin/env python3
"""Assemble data/edit_plan.json from the curated shortlist + measured clip profiles.
  build_plan.py fetchlist SHORTLIST.json OUT_CLIPS.json          -> {clip_id: {media_url}} for tools/profile_clips.py fetch/profile
  build_plan.py plan SHORTLIST.json PROFILES.json OUT_PLAN.json  -> edit plan: clips (shortlist meta + profile), excerpts, cast, cues, sequences
SHORTLIST.json = {"clips": {clip_id: {media_url, page, family, model, year, creator, license, ...}}, "excerpts": {eid: {clip, in, out, label{model,year,creator,license}, role}}, "cast": {...}, "cues": {...}}"""
import json, sys

SEQUENCES = [('seq01', 'seq.seq01_hook', 0, 8, ['shards', .4]), ('seq02', 'seq.seq02_panels', 8, 16, ['slat', .5]), ('seq03', 'seq.seq03_annotations', 16, 25, ['zoomthrough', .6]),
             ('seq05', 'seq.seq05_corridor', 25, 36.4, ['whip_up', .5]), ('seq04', 'seq.seq04_framestack', 36.4, 43, ['slat_v', .5]), ('seq06', 'seq.seq06_gallery', 43, 56, ['whip', .4]),
             ('seq07', 'seq.seq07_splits', 56, 63, ['iris', .5]), ('seq08', 'seq.seq08_control', 63, 72, ['dip', .3]), ('seq09', 'seq.seq09_matrix', 72, 83, ['slat_v', .4]),
             ('seq10', 'seq.seq10_contact', 83, 90, None), ('seq11', 'seq.seq11_heroes', 90, 104, ['dip', .3]), ('seq12', 'seq.seq12_montage', 104, 110, None),
             ('seq13', 'seq.seq13_callback', 110, 115, None), ('seq14', 'seq.seq14_final', 115, 120, None)]


def main():
    cmd = sys.argv[1]; sl = json.load(open(sys.argv[2]))
    if cmd == 'fetchlist': json.dump({cid: {'media_url': c['media_url']} for cid, c in sl['clips'].items()}, open(sys.argv[3], 'w'), indent=1); print(len(sl['clips']), 'clips'); return
    prof = json.load(open(sys.argv[3])); plan = dict(clips={}, excerpts=sl['excerpts'], cast=sl.get('cast', {}), cues=sl.get('cues', {}), sequences=[])
    for cid, c in sl['clips'].items():
        p = prof.get(cid)
        if not p: print('NO PROFILE for', cid); continue
        plan['clips'][cid] = {**{k: v for k, v in c.items() if k != 'media_url'}, **p}
        if 'overlays_override' in c: plan['clips'][cid]['overlays'] = c['overlays_override']            # authoritative list of watermarks/logos to keep visible (profiling is a heuristic)
    for eid, e in plan['excerpts'].items():
        c = plan['clips'].get(e['clip'])
        if not c: print('excerpt', eid, 'has no clip', e['clip']); continue
        if e['out'] > c['duration'] + .05: print('WARN excerpt', eid, 'out', e['out'], '> clip duration', c['duration']); e['out'] = min(e['out'], c['duration'])
    for sid, mod, t0, t1, tr in SEQUENCES:
        s = dict(id=sid, module=mod, t0=t0, t1=t1)
        if tr: s['transition_out'] = tr
        plan['sequences'].append(s)
    json.dump(plan, open(sys.argv[4], 'w'), indent=1); print('plan:', len(plan['clips']), 'clips', len(plan['excerpts']), 'excerpts ->', sys.argv[4])


if __name__ == '__main__': main()

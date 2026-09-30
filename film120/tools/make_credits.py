#!/usr/bin/env python3
"""Footage source / credit list from the edit plan (+ optional research verification records).
usage: make_credits.py PLAN.json OUT.md OUT.csv [--strict]
For every excerpt actually cast in a sequence: model/version, creator, licence, source page, media URL, span, story role and where it appears (sequence, film time).  --strict exits 1 if any used excerpt lacks source URL, creator, licence or model/year."""
import csv, json, sys

LIC_URL = [('CC BY-SA', 'https://creativecommons.org/licenses/by-sa/4.0/'), ('CC BY', 'https://creativecommons.org/licenses/by/4.0/'), ('CC0', 'https://creativecommons.org/publicdomain/zero/1.0/'), ('MIT', 'https://opensource.org/license/mit'),
           ('Apache', 'https://www.apache.org/licenses/LICENSE-2.0'), ('OpenRAIL', 'https://huggingface.co/spaces/CompVis/stable-diffusion-license'), ('PD', 'https://commons.wikimedia.org/wiki/Template:PD-algorithm')]
CHANGES = 'fitted/cropped to 9:16, retimed, colour-graded (early-era look), overlaid with annotations and source labels, cut into excerpts'
def lic_url(name): return next((u for k, u in LIC_URL if name.startswith(k)), '')

def walk(o, found):
    if isinstance(o, dict):
        for k, v in o.items(): walk(v, found)
    elif isinstance(o, list):
        for v in o: walk(v, found)
    elif isinstance(o, str): found.add(o)

def main():
    plan = json.load(open(sys.argv[1])); md, cs = sys.argv[2], sys.argv[3]; strict = '--strict' in sys.argv
    if '--native' in sys.argv:                                            # native (source-file) geometry recorded when the proxies were cut: id -> [w, h, fps, duration, proxy_offset]
        for cid, (nw, nh, nf, nd, po) in json.load(open(sys.argv[sys.argv.index('--native') + 1])).items():
            if cid in plan['clips']: plan['clips'][cid].update(native_width=nw, native_height=nh, native_fps=nf, native_duration=nd, proxy_offset=0)
    ex = plan['excerpts']; rows = {}; win = {s['id']: (s['t0'], s['t1']) for s in plan['sequences']}
    for sid, cast in plan.get('cast', {}).items():
        found = set(); walk(cast, found)
        for eid in found:
            if eid in ex: rows.setdefault(eid, []).append(sid)
    bad = []; out = []
    for eid, seqs in sorted(rows.items(), key=lambda kv: min(win.get(s, (999, 0))[0] for s in kv[1])):
        e = ex[eid]; c = plan['clips'][e['clip']]; lab = e.get('label', {})
        rec = dict(excerpt=eid, model=lab.get('model', ''), year=lab.get('year', ''), family=c.get('family', ''), version=c.get('model_version', ''), released=c.get('created', ''), creator=lab.get('creator', ''), license=lab.get('license', ''),
                   license_basis=c.get('license_basis', ''), source_page=c.get('source_page_url') or c.get('page', ''), media_url=c.get('media_url', ''), span=f"{e['in'] + c.get('proxy_offset', 0):.2f}-{e['out'] + c.get('proxy_offset', 0):.2f}s of {c.get('native_duration') or c.get('duration', 0):.1f}s",
                   native=f"{c.get('native_width') or c.get('width')}x{c.get('native_height') or c.get('height')}@{c.get('native_fps') or c.get('fps')}", role=e.get('role', ''), used_in='; '.join(f"{s} ({win[s][0]:g}-{win[s][1]:g}s)" for s in seqs if s in win), license_url=lic_url(lab.get('license', '')), changes=CHANGES)
        for k in ('model', 'year', 'creator', 'license', 'source_page'):
            if not rec[k]: bad.append(f'{eid}: missing {k}')
        out.append(rec)
    with open(cs, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    fams = {r['family'] or r['model'] for r in out}; pages = {r['source_page'] for r in out}
    lines = ['# Footage source & credit list', '', f'{len(out)} excerpts used - {len(pages)} distinct source pages - {len(fams)} model families / projects.', '',
             '| # | Model · year | Creator | Licence | Licence URL | Source page | Native | Span | Changes made | Used in |', '|---|---|---|---|---|---|---|---|---|---|']
    for i, r in enumerate(out, 1):
        lines.append(f"| {i} | {r['model']} · {r['year']}<br><sub>{r['version'][:80]}</sub> | {r['creator']} | {r['license']} | {r['license_url']} | {r['source_page']} | {r['native']} | {r['span']} | {r['changes']} | {r['used_in']} |")
    open(md, 'w').write('\n'.join(lines) + '\n'); print(len(out), 'excerpts,', len(pages), 'pages,', len(fams), 'families;', len(bad), 'problems')
    for b in bad: print('  ', b)
    if strict and bad: sys.exit(1)

if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Merge hunter candidates (data/candidates/H*.json) with verifier verdicts (data/verified/H*.json) into a clip pool for acquisition/profiling.
usage: shortlist_from_candidates.py OUT.json [--skip id,id] [--max-span 30]
Every non-rejected candidate becomes a clip (media_url, page, verdict, conditions, label) plus one whole-clip 'probe' excerpt (<= max-span s) so the proxy maker can fetch and profile it."""
import glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# label model text + the year the MODEL was released (not the file's generation date); extended as new candidates arrive
LABELS = {
    'sora_': ('SORA', '2024'), 'veo3_': ('VEO 3', '2025'), 'veo31_': ('VEO 3.1', '2025'), 'veo2_': ('VEO 2', '2024'), 'sd14_': ('STABLE DIFFUSION 1.4', '2022'), 'deepdream_': ('DEEPDREAM', '2015'),
    'runway_gen1_': ('RUNWAY GEN-1', '2023'), 'runway_gen2_': ('RUNWAY GEN-2', '2023'), 'runway_gen3_': ('RUNWAY GEN-3 ALPHA', '2024'), 'cogvideox_': ('COGVIDEOX', '2024'), 'hailuo_': ('HAILUO', '2024'),
    'grok_': ('GROK IMAGINE', '2025'), 'ltxv': ('LTX-VIDEO', '2025'), 'svd_': ('STABLE VIDEO DIFFUSION', '2023'), 'seedance': ('SEEDANCE 2.0', '2026'),
}
CREATOR_RULES = [('benlisquare', 'Benlisquare'), ('oronbb', 'Oronbb'), ('lwneal', 'Lwneal'), ('vulcansphere', 'VulcanSphere'), ('nesnad', 'Nesnad'), ('achim raschka', 'Achim Raschka'), ('premeditated', 'Premeditated / OWS Photography'),
                 ('pantheraleo', 'PantheraLeo1359531'), ('google deepmind', 'Google DeepMind demo'), ('sora / openai', 'OpenAI demo')]


def short_license(lic, verdict_conditions):
    i = lic.get('id', '')
    for k, v in (('CC BY-SA 4.0', 'CC BY-SA 4.0'), ('CC BY 4.0', 'CC BY 4.0'), ('CC BY 3.0', 'CC BY 3.0'), ('CC0', 'CC0')):
        if k in i and not (k == 'CC BY 4.0' and 'BY-SA' in i): return v
    if 'PD' in i or 'public' in i.lower(): return 'PD (Commons: AI output)'
    return i[:24]


def main():
    out = sys.argv[1]; skip = set(); maxspan = 30.0
    if '--skip' in sys.argv: skip = set(sys.argv[sys.argv.index('--skip') + 1].split(','))
    if '--max-span' in sys.argv: maxspan = float(sys.argv[sys.argv.index('--max-span') + 1])
    verd = {}
    for f in glob.glob(os.path.join(HERE, 'data/verified/H*.json')):
        for v in json.load(open(f))['verdicts']: verd.setdefault(v['cand_id'], v)
    clips, excerpts, seen, by_url = {}, {}, set(), {}
    for f in sorted(glob.glob(os.path.join(HERE, 'data/candidates/H*.json'))):
        for c in json.load(open(f))['candidates']:
            cid = c['cand_id']
            if cid in seen or cid in skip: continue
            v = verd.get(cid); fv = v['final_verdict'] if v else 'unverified'
            if fv == 'reject': continue
            u = c['media_url'].split('?')[0]
            if u in by_url:
                if fv != 'unverified' and clips[by_url[u]]['verdict'] == 'unverified': del clips[by_url[u]]; del excerpts['probe_' + by_url[u]]           # a verified duplicate replaces an unverified one
                else: continue
            by_url[u] = cid; seen.add(cid); lab = next((val for k, val in LABELS.items() if cid.startswith(k)), (c['family'].upper()[:26], str(c.get('created', ''))[:4]))
            cr = next((val for k, val in CREATOR_RULES if k in c['creator_credit'].lower()), c['creator_credit'][:40])
            lic = short_license(c['license'], v.get('conditions', []) if v else [])
            m = c['media']; dur = float(m.get('duration_s') or 0)
            clips[cid] = dict(media_url=c['media_url'], page=c['source_page_url'], family=c['family'], model_version=c['model_version'], created=c.get('created'), date_basis=c.get('date_basis'), creator=cr, license=lic,
                              license_basis=c['license'].get('basis_note', ''), verdict=fv, verdict_confidence=(v or {}).get('confidence'), conditions=(v or {}).get('conditions', []), risk_flags=c.get('risk_flags', []),
                              story_roles=c.get('story_roles', []), description=c.get('description', ''), prompt=c.get('prompt', ''), listed_media=m, source_file=os.path.basename(f))
            excerpts['probe_' + cid] = dict(clip=cid, **{'in': 0.0, 'out': round(min(dur, maxspan), 3)}, label=dict(model=lab[0], year=lab[1], creator=cr, license=lic), role='probe')
    json.dump(dict(clips=clips, excerpts=excerpts, cast={}, cues={}), open(out, 'w'), indent=1); print(len(clips), 'clips ->', out)


if __name__ == '__main__': main()

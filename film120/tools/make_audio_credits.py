#!/usr/bin/env python3
"""Audio credit list for the licensed sounds/music that the mix actually uses (LAYERS + MUSIC in audio_layers.py) -> markdown.
usage: make_audio_credits.py OUT.md"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_layers as AL
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'audio')
sfx = json.load(open(os.path.join(D, 'licensed_sfx.json'))); mus = json.load(open(os.path.join(D, 'licensed_music.json')))
S = {s['id']: s for s in sfx['sounds']}; SRC = {s['id']: s for s in sfx['sources']}; T = {t['id']: t for t in mus['tracks']}
used = sorted({i for L in AL.LAYERS.values() for i, _ in L['ids']}); L = ['# Audio credits', '',
    'Narration: ElevenLabs Eleven v4 (text-to-speech, generated through Higgsfield; preset voice "Arthur"), original script.',
    'Score: original, procedurally synthesised for this film (no third-party music in the score itself).',
    'Sound design: original procedural SFX layered with the licensed recordings below. Every licensed sound only supports a procedural one or sits far below the score; all were selected from metadata and measurements (nobody listened to the sources).', '',
    '## Attribution required', '']
cc = [i for i in used if S[i]['licence'].startswith('CC-BY')]; done = set()
for i in cc:
    s = S[i]; src = SRC.get(s['source_id'], {}); a = src.get('attribution') or ''
    L.append(f"- \"{s['source']}\" - {src.get('creator', '')} - {s['licence']} - {src.get('page_url', '')} - modified (trimmed)" + (f"\n  - {a}" if a else ''))
for name, M in AL.MUSIC.items():
    t = T[M['track']]
    if t['licence'].startswith('CC-BY'): L.append(f"- {t['attribution'].replace(chr(10), ' - ')} - source: {t['url']} - modified (segment {M['seg'][0]:.0f}-{M['seg'][1]:.0f} s, faded, layered at low level under the score)")
L += ['', '## Music beds', '']
for name, M in AL.MUSIC.items():
    t = T[M['track']]; L.append(f"- **{t['title']}** - {t['artist']} - {t['licence']} - film {M['place']:g}-{M['place'] + M['dur']:g} s - {t['page_url']}")
L += ['', '## Sound effects (licence, source page)', '', '| Sound | Category | Source / creator | Licence | Page |', '|---|---|---|---|---|']
for i in used:
    s = S[i]; src = SRC.get(s['source_id'], {}); L.append(f"| {i} | {s['category']} | {s['source']} - {src.get('creator', '')} | {s['licence']} | {src.get('page_url', s.get('listing_page', ''))} |")
L += ['', '## Caveats', ''] + [f'- {c}' for c in sfx['caveats']] + ['- Mixkit files are downloaded at build time from the Mixkit CDN and are not redistributed in this repository.', '- CC0 / public-domain tags on OpenGameArt, archive.org and Wikimedia Commons are assertions by the uploaders; provenance of the originals was not independently verified.']
open(sys.argv[1], 'w').write('\n'.join(L) + '\n'); print(len(used), 'sounds,', len(AL.MUSIC), 'music beds ->', sys.argv[1])

#!/usr/bin/env python3
"""Write subtitles.srt from the same caption chunks the renderer burns in (script text, ASR-aligned word times)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storyboard, render_lib as R
vo = json.load(open(sys.argv[1])); SB = storyboard.build(vo)
def ts(t): t = max(0, t); return f'{int(t // 3600):02d}:{int(t // 60 % 60):02d}:{int(t % 60):02d},{int(round((t % 1) * 1000)):03d}'
out = []
for i, (t0, t1, ws, n) in enumerate(R.caption_chunks(SB), 1): out.append(f"{i}\n{ts(t0)} --> {ts(t1)}\n{' '.join(w[0] for w in ws)}\n")
open(sys.argv[2], 'w').write('\n'.join(out)); print(len(out), 'cues')

#!/usr/bin/env python3
"""Download each shortlisted clip and cut a working proxy that covers only the excerpts used (+pad), downscaled only if taller than 1080 (never upscaled), video only, intra-friendly H.264.
usage: make_proxies.py SHORTLIST.json MEDIA_DIR OUT_SHORTLIST.json [--pad 0.5] [--max-mb 400] [--only id,id]
Clips in the output shortlist point at the proxy (local path, native_* fields keep the ORIGINAL geometry) and every excerpt's in/out is shifted to proxy time, so the render never decodes more than it needs.
Runs inside the Higgsfield sandbox (internet + ffmpeg)."""
import argparse, json, os, subprocess, sys, urllib.parse

UA = 'Mozilla/5.0 (film120-research; contact leonrdewa@gmail.com)'
ap = argparse.ArgumentParser(); ap.add_argument('shortlist'); ap.add_argument('media'); ap.add_argument('out'); ap.add_argument('--pad', type=float, default=.5); ap.add_argument('--max-mb', type=float, default=400); ap.add_argument('--only', default=''); a = ap.parse_args()
sl = json.load(open(a.shortlist)); os.makedirs(a.media, exist_ok=True); orig = os.path.join(a.media, 'orig'); os.makedirs(orig, exist_ok=True); prox = os.path.join(a.media, 'proxy'); os.makedirs(prox, exist_ok=True)
only = set(x for x in a.only.split(',') if x)
def sh(cmd): return subprocess.run(cmd, capture_output=True, text=True)
def work(cid, c):
    if only and cid not in only: return
    ex = {k: e for k, e in sl['excerpts'].items() if e['clip'] == cid}
    if not ex: return
    ext = os.path.splitext(urllib.parse.urlparse(c['media_url']).path)[1] or '.mp4'; src = os.path.join(orig, cid + ext); out = os.path.join(prox, cid + '.mp4')
    if not (os.path.exists(src) and os.path.getsize(src) > 1000):
        head = sh(['curl', '-sSIL', '-m', '30', '-A', UA, c['media_url']]).stdout; mb = 0
        for l in head.splitlines():
            if l.lower().startswith('content-length:'): mb = int(l.split(':')[1]) / 1e6
        if mb > a.max_mb: src = c['media_url']; print('remote-seek (too large to download)', cid, round(mb), 'MB', flush=True)      # ffmpeg reads only the needed byte ranges
        else:
            r = sh(['curl', '-sS', '-L', '-m', '600', '-A', UA, '-o', src, '-w', '%{http_code}', c['media_url']]); print('fetch', cid, r.stdout.strip(), os.path.getsize(src) if os.path.exists(src) else 0, flush=True)
            if r.stdout.strip() != '200': c['skipped'] = 'http ' + r.stdout.strip(); return
    UAO = ['-user_agent', UA] if src.startswith('http') else []
    pj = json.loads(sh(['ffprobe', '-v', 'error'] + UAO + [ '-show_entries', 'stream=codec_type,width,height,avg_frame_rate:format=duration', '-of', 'json', src]).stdout); v = next(s for s in pj['streams'] if s['codec_type'] == 'video')
    n, d = (v['avg_frame_rate'].split('/') + ['1'])[:2]; fps = float(n) / float(d) if float(d) else 30; dur = float(pj['format']['duration'])
    t0 = max(0.0, min(e['in'] for e in ex.values()) - a.pad); t1 = min(dur, max(e['out'] for e in ex.values()) + a.pad)
    vf = 'scale=-2:1080:flags=lanczos' if int(v['height']) > 1080 else 'crop=trunc(iw/2)*2:trunc(ih/2)*2'      # x264 needs even sizes; a 1 px crop, never a resample
    meta = out + '.meta'; want = f'{t0:.3f},{t1:.3f}'
    if os.path.exists(out) and os.path.getsize(out) > 1000 and os.path.exists(meta) and open(meta).read() == want: r = subprocess.CompletedProcess([], 0, '', '')        # cached proxy for exactly this span
    else: r = sh(['ffmpeg', '-y', '-v', 'error'] + UAO + ['-ss', f'{t0:.3f}', '-i', src, '-t', f'{t1 - t0:.3f}', '-an', '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-g', '12', '-pix_fmt', 'yuv420p', '-r', f'{fps:.3f}', '-movflags', '+faststart', out])
    if r.returncode: print('FFMPEG FAIL', cid, r.stderr[-300:]); c['skipped'] = 'ffmpeg'; return
    open(meta, 'w').write(want)
    c.update(local=out, native_width=int(v['width']), native_height=int(v['height']), native_fps=round(fps, 3), native_duration=round(dur, 3), proxy_offset=round(t0, 3))
    for e in ex.values(): e['in'] = round(e['in'] - t0, 3); e['out'] = round(min(e['out'], t1) - t0, 3); e['proxied'] = True
    print('proxy', cid, f"{v['width']}x{v['height']}@{fps:.2f}", f'{t0:.1f}-{t1:.1f}s of {dur:.1f}s', round(os.path.getsize(out) / 1e6, 1), 'MB', flush=True)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=4) as ex_: list(ex_.map(lambda kv: work(*kv), list(sl['clips'].items())))
json.dump(sl, open(a.out, 'w'), indent=1)

#!/usr/bin/env python3
"""Download and profile clips (run inside the Higgsfield sandbox).
  profile_clips.py fetch  CLIPS.json MEDIA_DIR          # CLIPS.json: {"clip_id": {"media_url": "...", ...}}  -> MEDIA_DIR/<clip_id>.<ext>
  profile_clips.py profile CLIPS.json MEDIA_DIR OUT.json # ffprobe, cuts, per-second motion/luma, letterbox, static-overlay candidates, audio presence
  profile_clips.py ascii  FILE T [COLS]                  # ASCII rendering of the frame at T seconds (for eyeballing composition without an image channel)
Profiles are measurements only; they never claim what a clip *shows*."""
import json, os, re, subprocess, sys, urllib.parse
import numpy as np

UA = 'Mozilla/5.0 (film120-research; contact leonrdewa@gmail.com)'


def sh(cmd, **kw): return subprocess.run(cmd, capture_output=True, **kw)


def fetch(clips, media):
    os.makedirs(media, exist_ok=True)
    for cid, c in clips.items():
        url = c['media_url']; ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or '.mp4'; p = os.path.join(media, cid + ext)
        if not (os.path.exists(p) and os.path.getsize(p) > 1000):
            r = sh(['curl', '-sS', '-L', '-m', '300', '-A', UA, '-o', p, '-w', '%{http_code}', url], text=True)
            print(cid, r.stdout.strip(), os.path.getsize(p) if os.path.exists(p) else 0, flush=True)
        c['local'] = p
    return clips


def probe(p):
    j = json.loads(sh(['ffprobe', '-v', 'error', '-show_entries', 'stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_frames,sample_rate,channels:format=duration,size,bit_rate', '-of', 'json', p], text=True).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video'); a = [s for s in j['streams'] if s['codec_type'] == 'audio']
    n, d = (v['avg_frame_rate'].split('/') + ['1'])[:2]
    return dict(width=int(v['width']), height=int(v['height']), fps=round(float(n) / float(d), 3) if float(d) else 0.0, duration=round(float(j['format']['duration']), 3),
                size_mb=round(int(j['format'].get('size', 0)) / 1e6, 2), bitrate_kbps=int(int(j['format'].get('bit_rate', 0)) / 1000), codec=v['codec_name'], has_audio=bool(a))


def frames_gray(p, fps, w, t0=0, dur=None):
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(t0)] + (['-t', str(dur)] if dur else []) + ['-i', p, '-vf', f'fps={fps},scale={w}:-2', '-pix_fmt', 'gray', '-f', 'rawvideo', '-']
    raw = sh(cmd).stdout; return raw


def cuts(p, thr=0.30):
    r = sh(['ffmpeg', '-hide_banner', '-nostats', '-i', p, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'], text=True).stderr
    return [round(float(m), 3) for m in re.findall(r'pts_time:([0-9.]+)', r)]


def letterbox(p, dur):
    r = sh(['ffmpeg', '-hide_banner', '-ss', str(min(2.0, dur / 3)), '-i', p, '-t', '3', '-vf', 'cropdetect=24:2:0', '-f', 'null', '-'], text=True).stderr
    m = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', r); return [int(x) for x in m[-1]] if m else None


def overlays(p, info, samples=24):
    """Static-overlay candidates (logos / watermarks / burnt-in captions): boxes where luma is temporally constant AND has strong edges while the rest of the frame moves."""
    w = 320; h = int(round(w * info['height'] / info['width'] / 2) * 2); dur = info['duration']; fps = max(0.5, min(8, samples / max(dur, 1)))
    raw = frames_gray(p, fps, w); n = len(raw) // (w * h)
    if n < 6: return []
    fr = np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)
    std = fr.std(0); med = np.median(fr, 0); gx = np.abs(np.diff(med, axis=1))[:-1]; gy = np.abs(np.diff(med, axis=0))[:, :-1]; edge = gx + gy
    glob = np.percentile(std, 60); still = (std < max(2.0, .25 * glob)) & (edge[:std.shape[0] - 1, :std.shape[1] - 1].shape == edge.shape or True)
    still = still[:edge.shape[0], :edge.shape[1]] & (edge > 24)
    if still.sum() < 12 or glob < 3.0: return []
    # connected components on a coarse grid
    cell = 8; gh, gw = still.shape[0] // cell, still.shape[1] // cell; coarse = still[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).mean((1, 3)) > .12
    seen = np.zeros_like(coarse); boxes = []
    for y in range(gh):
        for x in range(gw):
            if coarse[y, x] and not seen[y, x]:
                st = [(y, x)]; seen[y, x] = True; pts = []
                while st:
                    cy, cx = st.pop(); pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < gh and 0 <= nx < gw and coarse[ny, nx] and not seen[ny, nx]: seen[ny, nx] = True; st.append((ny, nx))
                ys = [q[0] for q in pts]; xs = [q[1] for q in pts]
                if len(pts) >= 2:
                    bx0, by0, bx1, by1 = min(xs) * cell / w, min(ys) * cell / h, (max(xs) + 1) * cell / w, (max(ys) + 1) * cell / h
                    near_edge = bx0 < .25 or by0 < .25 or bx1 > .75 or by1 > .75
                    if near_edge and (bx1 - bx0) < .6 and (by1 - by0) < .35: boxes.append(dict(x=round(bx0, 3), y=round(by0, 3), w=round(bx1 - bx0, 3), h=round(by1 - by0, 3), cells=len(pts), note='static high-contrast region near a border (possible logo/watermark/caption) - verify'))
    return boxes


def motion_profile(p, info):
    dur = info['duration']; w = 160; h = int(round(w * info['height'] / info['width'] / 2) * 2); raw = frames_gray(p, 4, w, 0, min(dur, 120)); n = len(raw) // (w * h)
    if n < 2: return [], []
    fr = np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w).astype(np.float32); luma = fr.mean((1, 2)); d = np.abs(np.diff(fr, axis=0)).mean((1, 2))
    per_s = [round(float(d[i * 4:(i + 1) * 4].mean()), 2) for i in range(int(len(d) / 4))]; lm = [round(float(luma[i * 4:(i + 1) * 4].mean()), 1) for i in range(int(n / 4))]
    return per_s, lm


def profile(clips, media, out):
    res = {}
    for cid, c in clips.items():
        p = c.get('local') or next((os.path.join(media, f) for f in os.listdir(media) if f.startswith(cid + '.')), None)
        if not p or not os.path.exists(p): print('missing', cid); continue
        info = probe(p); info['cuts'] = cuts(p); info['letterbox_crop'] = letterbox(p, info['duration']); info['overlays'] = overlays(p, info)
        ms, lm = motion_profile(p, info); info['motion_per_s'] = ms; info['luma_per_s'] = lm; info['local'] = p; res[cid] = info
        print(cid, info['width'], info['height'], info['fps'], info['duration'], 'cuts', len(info['cuts']), 'overlays', len(info['overlays']), 'audio', info['has_audio'], flush=True)
    json.dump(res, open(out, 'w'), indent=1); return res


RAMP = ' .:-=+*#%@'
def ascii_frame(p, t, cols=100):
    info = probe(p); rows = int(cols * info['height'] / info['width'] * .5)
    raw = sh(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', p, '-frames:v', '1', '-vf', f'scale={cols}:{rows}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-']).stdout
    a = np.frombuffer(raw, np.uint8)[:cols * rows].reshape(rows, cols).astype(np.float32); lo, hi = np.percentile(a, 2), np.percentile(a, 98); a = np.clip((a - lo) / max(1, hi - lo), 0, 1)
    return '\n'.join(''.join(RAMP[int(v * (len(RAMP) - 1))] for v in row) for row in a)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'fetch': clips = json.load(open(sys.argv[2])); fetch(clips, sys.argv[3]); json.dump(clips, open(sys.argv[2], 'w'), indent=1)
    elif cmd == 'profile': profile(json.load(open(sys.argv[2])), sys.argv[3], sys.argv[4])
    elif cmd == 'ascii': print(ascii_frame(sys.argv[2], float(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 100))

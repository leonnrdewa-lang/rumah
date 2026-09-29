#!/usr/bin/env python3
"""Numeric QA of the finished film (run where ffmpeg/ffprobe exist).
usage: qa_video.py final.mp4 [--freeze 2.9,3.44] [--report qa_report.json]
Checks: exact geometry / frame count / duration of both streams, black or near-black frames, frozen stretches (excluding the intended freeze), hard-cut times, replay-seam difference (last vs first frame),
audio loudness (EBU R128), true peak, clipping, silences, per-stream duration match."""
import argparse, json, re, subprocess, sys
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--freeze', default='2.9,3.44'); ap.add_argument('--report', default='qa_report.json'); a = ap.parse_args()
f = a.file; fz = [float(x) for x in a.freeze.split(',')]; rep = dict(file=f, fails=[], warns=[])
def fail(m): rep['fails'].append(m); print('FAIL', m)
def warn(m): rep['warns'].append(m); print('WARN', m)
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,sample_aspect_ratio,sample_rate,channels,bit_rate,duration,nb_read_frames,color_space:format=duration,size', '-of', 'json', f], capture_output=True, text=True).stdout)
v = next(s for s in pr['streams'] if s['codec_type'] == 'video'); au = next(s for s in pr['streams'] if s['codec_type'] == 'audio'); rep['video'] = v; rep['audio'] = au; rep['format'] = pr['format']
print(json.dumps(v)); print(json.dumps(au)); print(pr['format'])
if (int(v['width']), int(v['height'])) != (1080, 1920): fail(f"resolution {v['width']}x{v['height']}")
if v['r_frame_rate'] != '30/1': fail('frame rate ' + v['r_frame_rate'])
if int(v['nb_read_frames']) != 3600: fail(f"frame count {v['nb_read_frames']} != 3600")
if v['pix_fmt'] != 'yuv420p': warn('pix_fmt ' + v['pix_fmt'])
dv, da, df = float(v['duration']), float(au['duration']), float(pr['format']['duration'])
if abs(dv - 120.0) > 1e-3: fail(f'video duration {dv}')
if abs(da - 120.0) > .02: fail(f'audio duration {da}')
if abs(df - 120.0) > .02: fail(f'container duration {df}')
if au['sample_rate'] not in ('48000',) or au['channels'] != 2: warn(f"audio {au['sample_rate']} Hz x{au['channels']}")
# ---- per-frame analysis at 108x192 (all 3600 frames)
w, h = 108, 192
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-vf', f'scale={w}:{h}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32); n = len(fr); print('decoded', n, 'frames')
mean = fr.mean((1, 2)); std = fr.std((1, 2)); d = np.abs(np.diff(fr, axis=0)).mean((1, 2))
black = [i for i in range(n) if mean[i] < 7 and std[i] < 4]
if black: fail(f'{len(black)} near-black frames, first at {black[0] / 30:.2f}s (frames {black[:12]})')
still = np.where(d < .02)[0]; runs = []
for i in still:
    t = i / 30
    if fz[0] - .05 <= t <= fz[1] + .05: continue
    if runs and i - runs[-1][1] <= 1: runs[-1][1] = i
    else: runs.append([i, i])
long_still = [(r[0] / 30, (r[1] - r[0] + 2) / 30) for r in runs if r[1] - r[0] >= 8]
if long_still: warn('frozen stretches >0.27s: ' + ', '.join(f'{s:.2f}s +{l:.2f}s' for s, l in long_still))
cuts = [round((i + 1) / 30, 2) for i in np.where(d > 22)[0]]; rep['hard_cuts_s'] = cuts; print('hard cuts (frame diff > 22):', cuts)
seam = float(np.abs(fr[-1] - fr[0]).mean()); rep['seam_diff'] = seam; print('replay seam last-vs-first mean abs diff', round(seam, 2))
if seam > 6: warn(f'replay seam differs (mean abs diff {seam:.1f})')
top, bot = fr[:, :4].mean(), fr[:, -4:].mean(); print('edge luma top/bottom', round(float(top), 1), round(float(bot), 1))
rep['per_second'] = [dict(t=s, mean=round(float(mean[s * 30:(s + 1) * 30].mean()), 1), motion=round(float(d[s * 30:(s + 1) * 30].mean()), 2)) for s in range(int(n / 30))]
# ---- audio
e = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128=peak=true', '-vn', '-f', 'null', '-'], capture_output=True, text=True).stderr; s = e[e.rfind('Summary'):]
def grab(k): m = re.search(k + r':\s+(-?[\d.]+)', s); return float(m.group(1)) if m else None
lufs, lra, tp = grab('I'), grab('LRA'), grab('Peak'); rep['lufs'], rep['lra'], rep['true_peak_dbtp'] = lufs, lra, tp; print('LUFS', lufs, 'LRA', lra, 'true peak', tp)
if lufs is None or abs(lufs + 14) > 1.0: warn(f'integrated loudness {lufs} (target -14 +-1)')
if tp is None or tp > -1.0: fail(f'true peak {tp} dBTP > -1.0')
st = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'astats=metadata=0:reset=0', '-vn', '-f', 'null', '-'], capture_output=True, text=True).stderr
ov = st[st.rfind('Overall'):]; pk = re.search(r'Peak level dB:\s+(-?[\d.]+)', ov); cc = re.search(r'Peak count:\s+(\d+)', ov); print('sample peak dB', pk and pk.group(1), 'peak count', cc and cc.group(1))
if pk and float(pk.group(1)) > -0.3: fail('sample peak too close to full scale (clipping risk)')
sil = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'silencedetect=n=-60dB:d=0.06', '-vn', '-f', 'null', '-'], capture_output=True, text=True).stderr
starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', sil)]; ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', sil)]
rep['silences'] = list(zip(starts, ends)); print('silences (< -60 dB, >= 60 ms):', [(round(a_, 2), round(b_, 2)) for a_, b_ in zip(starts, ends)])
unexpected = [(a_, b_) for a_, b_ in zip(starts, ends) if not (fz[0] - .3 <= a_ <= fz[1] + .1) and a_ > .1 and b_ < 119.8]
if unexpected: warn(f'unexpected silences: {unexpected}')
rep['verdict'] = 'PASS' if not rep['fails'] else 'FAIL'; json.dump(rep, open(a.report, 'w'), indent=1); print('VERDICT', rep['verdict'], 'fails', rep['fails'], 'warns', len(rep['warns']))

#!/usr/bin/env python3
"""Numeric QA of the finished file: geometry, duration, per-second brightness/contrast (flags blank or frozen stretches), audio peaks/loudness.
Usage: qa_video.py final.mp4"""
import json, subprocess, sys
import numpy as np
f = sys.argv[1]
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,color_space,sample_rate,channels,bit_rate,duration', '-show_entries', 'format=duration,size,bit_rate', '-of', 'json', f], capture_output=True, text=True).stdout)
for s in pr['streams']: print(s)
print('format', pr['format'])
W, H = 108, 192
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-vf', f'fps=10,scale={W}:{H}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32); print('frames sampled @10fps:', len(fr))
flags = []
for s in range(int(len(fr) / 10)):
    blk = fr[s * 10:(s + 1) * 10]; mean = blk.mean(); std = blk.std(); mot = np.abs(np.diff(blk, axis=0)).mean() if len(blk) > 1 else 0
    tag = '' if s < len(fr) / 10 - 2 else ' (tail)'
    line = f't={s:2d}s mean={mean:6.1f} std={std:5.1f} motion={mot:5.2f}'
    if mean < 8 and tag == '': flags.append(f'dark@{s}s')
    if mot < .12 and mean > 8: flags.append(f'frozen?@{s}s')
    print(line + tag)
print('FLAGS:', flags or 'none')
a = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
print(a[a.rfind('Summary'):] if 'Summary' in a else a[-600:])
v = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'astats=metadata=0:reset=0', '-vn', '-f', 'null', '-'], capture_output=True, text=True).stderr
for l in v.splitlines():
    if any(k in l for k in ('Peak level dB', 'RMS level dB', 'Number of samples', 'Flat factor', 'Peak count')) and 'Overall' not in l: pass
print([l.strip() for l in v.splitlines() if 'Overall' in l or ('Peak level dB' in l) or ('Peak count' in l)][:6])

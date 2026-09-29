#!/usr/bin/env python3
"""Stand-in footage for layout work: one synthetic clip per plan clip (same width/height/fps, duration capped at 14 s) with the clip id and time burnt in
and a moving figure so motion/tracking code has something to chew on.
usage: make_mock.py PLAN.json OUTDIR   -> OUTDIR/<clip>.mp4 and OUTDIR/mock_plan.json (plan whose 'local' paths point at the mock files)"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

plan = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True); FF = os.environ.get('FFMPEG', 'ffmpeg')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def make(cid, i, w, h, fps, dur, path):
    rng = np.random.default_rng(i + 1); c0 = rng.uniform(30, 120, 3); c1 = rng.uniform(110, 230, 3)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); f1 = ImageFont.truetype(FONT, max(22, h // 12)); f2 = ImageFont.truetype(FONT, max(14, h // 26))
    p = subprocess.Popen([FF, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-', '-f', 'lavfi', '-i', 'sine=f=220:r=44100', '-t', str(dur),
                          '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', path], stdin=subprocess.PIPE)
    n = int(dur * fps)
    for k in range(n):
        t = k / fps; g = (np.sin((xx / w * 3 + yy / h * 2) + t * .6 + i) * .5 + .5)[..., None]; img = (c0 * (1 - g) + c1 * g).astype(np.uint8)
        im = Image.fromarray(img); d = ImageDraw.Draw(im); cx = w * (.5 + .3 * np.sin(t * .9 + i)); cy = h * (.55 + .12 * np.cos(t * 1.3))
        d.ellipse([cx - h * .13, cy - h * .13, cx + h * .13, cy + h * .13], fill=(240, 235, 225)); d.rectangle([cx - h * .05, cy + h * .13, cx + h * .05, cy + h * .34], fill=(40, 40, 50))
        d.text((w / 2, h * .12), cid, font=f1, fill=(255, 255, 255), anchor='mm'); d.text((16, h - 12), f'{t:5.2f}s  {w}x{h}@{fps:g}', font=f2, fill=(255, 255, 255), anchor='lb')
        p.stdin.write(np.asarray(im).tobytes())
    p.stdin.close(); p.wait()

for i, (cid, c) in enumerate(plan['clips'].items()):
    w, h, fps = int(c['width']), int(c['height']), float(c['fps']); dur = min(float(c['duration']), 14.0); w -= w % 2; h -= h % 2; p = os.path.join(out, cid + '.mp4')
    if not os.path.exists(p): make(cid, i, w, h, fps, dur, p)
    c['local'] = p; c['duration'] = dur
json.dump(plan, open(os.path.join(out, 'mock_plan.json'), 'w'), indent=1); print('mock clips:', len(plan['clips']))

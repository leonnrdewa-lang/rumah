#!/usr/bin/env python3
"""Compose the reel.  render.py --footage DIR --vo vo.json --out DIR [--preview t1,t2,..] [--range a,b] [--workers N]"""
import argparse, json, multiprocessing as mp, os, subprocess, sys, time
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D, render_lib as R, scenes as S, storyboard
from design import W, H, FPS

SCENE_FN = [S.hook, S.early_faces, S.early_montage, S.timeline, S.concept, S.now, S.styles, S.compare, S.finale]
NO_CAPTION = {0}

def style_at(SB, t):
    imp = SB['cues']['impact']
    if t < imp: return 'early'
    if t < SB['scenes'][1]['t0']: return 'now'
    if t < SB['cues']['tl'][2] - .05: return 'early'
    return 'now'

def accent_at(SB, t): return D.AMBER if t < SB['cues']['tl'][2] else D.CYAN

def scene_index(SB, t):
    for i, s in enumerate(SB['scenes']):
        if s['t0'] <= t < s['t1']: return i
    return len(SB['scenes']) - 1

def compose(ctx, chunks, t, fidx):
    SB = ctx.SB; i = scene_index(SB, t); c = None
    for tb, kind, dur in SB['trans']:
        if tb - dur / 2 <= t < tb + dur / 2:
            j = min(range(len(SB['scenes'])), key=lambda k: abs(SB['scenes'][k]['t0'] - tb))
            if j >= 1:
                p = (t - (tb - dur / 2)) / dur
                a = SCENE_FN[j - 1](ctx, t); b = SCENE_FN[j](ctx, t)
                c = R.transition(kind, a, b, p, ring=accent_at(SB, t)); i = j if p >= .5 else j - 1
            break
    if c is None: c = SCENE_FN[i](ctx, t)
    imp = SB['cues']['impact']; flash = max(0.0, 1 - (t - imp) / .14) * .85 if imp <= t < imp + .14 else 0.0
    c = R.finish(c, t, style_at(SB, t), fidx, flash)
    if i not in NO_CAPTION and t >= storyboard.VO_START - .1 and t < SB['E'][11] + .5:
        R.gradient_v(c, 1120, H, 0, .55)
        R.draw_caption(c, t, chunks, accent_at(SB, t))
    if t >= SB['total'] - .13: c[:] = 0
    return c

def load(args):
    vo = json.load(open(args.vo)); SB = storyboard.build(vo); return SB

def worker(job):
    args, a, b, part = job
    D.FONT_DIRS[:0] = [d for d in args.fonts.split(':') if d]
    R.FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
    SB = load(args); F = R.Footage(args.footage); ctx = S.Ctx(F, SB); chunks = R.caption_chunks(SB)
    enc = subprocess.Popen([R.FFMPEG, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'fast', '-threads', '2', '-crf', '13', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-g', '30', os.path.join(args.out, f'part_{part:03d}.mp4')], stdin=subprocess.PIPE, stderr=open(os.path.join(args.out, f'enc_{part:03d}.log'), 'w'))
    t0 = time.time()
    for f in range(a, b):
        enc.stdin.write(np.ascontiguousarray(compose(ctx, chunks, f / FPS, f)).tobytes())
    enc.stdin.close(); enc.wait(); F.close()
    return part, b - a, time.time() - t0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--footage', required=True); ap.add_argument('--vo', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--fonts', default=''); ap.add_argument('--preview', default=''); ap.add_argument('--range', default=''); ap.add_argument('--workers', type=int, default=6); ap.add_argument('--chunk', type=int, default=60); ap.add_argument('--smoke', action='store_true')
    args = ap.parse_args(); os.makedirs(args.out, exist_ok=True)
    D.FONT_DIRS[:0] = [d for d in args.fonts.split(':') if d]; R.FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
    SB = load(args); total_frames = int(round(SB['total'] * FPS))
    if args.smoke:   # compose frames around every scene boundary / transition window and a sparse sweep, to catch exceptions cheaply
        F = R.Footage(args.footage); ctx = S.Ctx(F, SB); chunks = R.caption_chunks(SB); ts = set()
        for tb, kind, dur in SB['trans']:
            for k in range(-8, 9): ts.add(round(tb + k * dur / 8, 3))
        for sc in SB['scenes']: ts.update([sc['t0'], sc['t0'] + .5, sc['t1'] - .05])
        ts.update([SB['total'] - .2, SB['total'] - .05]); n = 0
        for t in sorted(x for x in ts if 0 <= x < SB['total']):
            compose(ctx, chunks, t, int(t * FPS)); n += 1
        print('smoke ok', n, 'frames'); F.close(); return
    if args.preview:
        F = R.Footage(args.footage); ctx = S.Ctx(F, SB); chunks = R.caption_chunks(SB)
        for ts in args.preview.split(','):
            t = float(ts); f = int(t * FPS)
            for k in range(max(0, f - 2), f):  # warm streams so motion boxes have a previous frame
                compose(ctx, chunks, k / FPS, k)
            img = compose(ctx, chunks, t, f); Image.fromarray(img).save(os.path.join(args.out, f'prev_{t:07.3f}.png')); print('saved', t, flush=True)
        F.close(); return
    a, b = (0, total_frames) if not args.range else [int(float(x) * FPS) for x in args.range.split(',')]
    jobs = [(args, s, min(s + args.chunk, b), n) for n, s in enumerate(range(a, b, args.chunk))]
    print(f'{b - a} frames in {len(jobs)} chunks, {args.workers} workers', flush=True); t0 = time.time(); done = 0
    with mp.Pool(args.workers) as pool:
        for part, n, dt in pool.imap_unordered(worker, jobs):
            done += n; print(f'part {part} {n}f {dt:.0f}s  [{done}/{b - a}] elapsed {time.time() - t0:.0f}s', flush=True)
    with open(os.path.join(args.out, 'parts.txt'), 'w') as fh:
        for n in range(len(jobs)): fh.write(f"file 'part_{n:03d}.mp4'\n")
    subprocess.run([R.FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', os.path.join(args.out, 'parts.txt'), '-c', 'copy', os.path.join(args.out, 'video_silent.mp4')], check=True)
    json.dump(dict(total=SB['total'], frames=total_frames), open(os.path.join(args.out, 'render_info.json'), 'w'))

if __name__ == '__main__': main()

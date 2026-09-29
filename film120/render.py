#!/usr/bin/env python3
"""film120 renderer.
  render.py --plan data/edit_plan.json --script data/script.json --vo data/vo/vo.json --media MEDIA_DIR --out OUT [--fonts DIR:DIR]
            [--preview 1.5,44.2] | [--smoke] | [--range 0,30] [--workers 5] [--chunk 60] [--part-offset N]
Frames are rendered in independent chunks (multiprocessing), each piped to an x264 encoder; parts are concatenated by mux.sh."""
import argparse, json, multiprocessing as mp, os, subprocess, sys, time
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import tokens, gfx, footage
from engine.tokens import W, H, FPS, TOTAL_FRAMES
from engine import compose


def setup(args):
    if args.fonts: tokens.FONT_DIRS[:0] = [d for d in args.fonts.split(':') if d]
    footage.FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
    return compose.Ctx(args.plan, args.script, args.vo, args.media, max_streams=args.streams)


def worker(job):
    args, a, b, part = job; ctx = setup(args)
    enc = subprocess.Popen([footage.FFMPEG, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'fast', '-threads', '2', '-crf', '13', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-g', '30',
                            os.path.join(args.out, f'part_{part:03d}.mp4')], stdin=subprocess.PIPE, stderr=open(os.path.join(args.out, f'enc_{part:03d}.log'), 'w'))
    t0 = time.time()
    for f in range(a, b): enc.stdin.write(np.ascontiguousarray(compose.compose_frame(ctx, f / FPS, f)).tobytes())
    enc.stdin.close(); enc.wait(); ctx.F.close(); return part, b - a, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    for k in ('plan', 'script', 'vo', 'out'): ap.add_argument('--' + k, required=True)
    ap.add_argument('--media', default=None); ap.add_argument('--fonts', default=''); ap.add_argument('--preview', default=''); ap.add_argument('--range', default='')
    ap.add_argument('--workers', type=int, default=5); ap.add_argument('--chunk', type=int, default=60); ap.add_argument('--streams', type=int, default=8)
    ap.add_argument('--smoke', action='store_true'); ap.add_argument('--part-offset', type=int, default=0)
    args = ap.parse_args(); os.makedirs(args.out, exist_ok=True)
    if args.smoke or args.preview:
        ctx = setup(args)
        if args.smoke:                                # frames around every sequence boundary + a sparse sweep
            ts = set(np.arange(0, 120, 1.7))
            for s in ctx.seqs:
                for k in np.linspace(-.6, .6, 9): ts.add(round(s['t1'] + k, 3))
                ts.update([s['t0'] + .05, (s['t0'] + s['t1']) / 2])
            ts = sorted(t for t in ts if 0 <= t < 120); bad = 0
            for t in ts:
                try: compose.compose_frame(ctx, t, int(t * FPS))
                except Exception as e: bad += 1; print('ERR at', t, repr(e))
            print('smoke', len(ts), 'frames,', bad, 'errors'); ctx.F.close(); sys.exit(1 if bad else 0)
        for ts in args.preview.split(','):
            t = float(ts); f = int(round(t * FPS))
            for k in range(max(0, f - 2), f): compose.compose_frame(ctx, k / FPS, k)
            Image.fromarray(compose.compose_frame(ctx, f / FPS, f)).save(os.path.join(args.out, f'prev_{t:07.3f}.png')); print('saved', t, flush=True)
        ctx.F.close(); return
    a, b = (0, TOTAL_FRAMES) if not args.range else [int(round(float(x) * FPS)) for x in args.range.split(',')]
    jobs = [(args, s, min(s + args.chunk, b), n + args.part_offset) for n, s in enumerate(range(a, b, args.chunk))]
    print(f'{b - a} frames in {len(jobs)} chunks, {args.workers} workers', flush=True); t0 = time.time(); done = 0
    with mp.Pool(args.workers) as pool:
        for part, n, dt in pool.imap_unordered(worker, jobs):
            done += n; print(f'part {part} {n}f {dt:.0f}s [{done}/{b - a}] elapsed {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__': main()

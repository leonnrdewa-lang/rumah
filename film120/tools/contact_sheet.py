#!/usr/bin/env python3
"""Small labelled contact sheets of a rendered film (for eyeballing layout when only text can leave the sandbox).
usage: contact_sheet.py FILM.mp4 OUT_PREFIX WIDTH COLS QUALITY T1,T2,... [--per N]   -> OUT_PREFIX_0.jpg, _1.jpg ... (N frames per sheet, default 6)"""
import io, subprocess, sys
from PIL import Image, ImageDraw
film, pre, W, cols, q, ts = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), [float(x) for x in sys.argv[6].split(',')]
per = int(sys.argv[sys.argv.index('--per') + 1]) if '--per' in sys.argv else 6
def grab(t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', film, '-frames:v', '1', '-vf', f'scale={W}:-2', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(raw)).convert('RGB')
for k in range(0, len(ts), per):
    grp = ts[k:k + per]; tiles = [grab(t) for t in grp]; H = max(t.size[1] for t in tiles); rows = (len(tiles) + cols - 1) // cols; sh = Image.new('RGB', (cols * W, rows * H), (30, 30, 30))
    for i, im in enumerate(tiles):
        x, y = (i % cols) * W, (i // cols) * H; sh.paste(im, (x, y)); d = ImageDraw.Draw(sh); d.rectangle([x, y, x + 30, y + 10], fill=(0, 0, 0)); d.text((x + 2, y), f'{grp[i]:g}', fill=(255, 255, 0))
    out = f'{pre}_{k // per}.jpg'; sh.save(out, quality=q, optimize=True); print(out, sh.size)

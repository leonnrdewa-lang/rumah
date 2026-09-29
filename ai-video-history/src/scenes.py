"""Scene painters. Each takes (ctx, t) -> uint8 (H,W,3) canvas. ctx = Ctx(F, SB)."""
import os, subprocess
import numpy as np
from PIL import Image
import design as D
from design import W, H, FPS, clamp, ease_out, ease_io, out_back, prog, lerp
import render_lib as R

AM, CY, PA = D.AMBER, D.CYAN, D.PAPER

class Ctx:
    def __init__(self, F, SB): self.F, self.SB = F, SB; self._focus = {}; self._still = {}; self._env = {}; self.prev = {}
    def focus(self, cid, t_in):
        """Horizontal focus of interest (0..1) from edge energy of a few frames - drives the 9:16 reframe."""
        k = (cid, t_in)
        if k not in self._focus:
            m = self.F.meta(cid); acc = None
            for dt in (0.2, 0.9, 1.6):
                if t_in + dt > m['duration'] - .1: continue
                f = self.F.frame(cid, t_in, t_in + dt, max_h=180)
                g = np.asarray(Image.fromarray(f).convert('L'), np.float32); e = np.abs(np.diff(g, axis=1))[:-1] + np.abs(np.diff(g, axis=0))[:, :-1]
                acc = e if acc is None else acc + e
            if acc is None: self._focus[k] = .5
            else:
                col = acc.sum(0); col = np.convolve(col, np.ones(9) / 9, 'same'); xs = np.linspace(0, 1, len(col)); w_ = col ** 2
                self._focus[k] = float(np.clip((xs * w_).sum() / w_.sum(), .32, .68))
        return self._focus[k]
    def still(self, cid, t):
        k = (cid, round(t, 1))
        if k not in self._still:
            m = self.F.meta(cid); dh = min(m['height'], 540); dw = int(round(dh * m['width'] / m['height'] / 2)) * 2
            b = subprocess.run([R.FFMPEG, '-v', 'error', '-ss', f'{t:.2f}', '-i', m['local'], '-frames:v', '1', '-vf', f'scale={dw}:{dh}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
            self._still[k] = np.frombuffer(b, np.uint8).reshape(dh, dw, 3).copy() if len(b) == dw * dh * 3 else np.zeros((dh, dw, 3), np.uint8)
        return self._still[k]
    def env(self, cid, t_in, n):
        """Audio loudness envelope (0..1) of a clip at 30 fps from t_in; falls back to a soft synthetic pulse when the clip has no audio."""
        k = (cid, t_in)
        if k not in self._env:
            m = self.F.meta(cid)
            b = subprocess.run([R.FFMPEG, '-v', 'error', '-ss', f'{t_in:.2f}', '-i', m['local'], '-vn', '-ac', '1', '-ar', '8000', '-t', f'{n / FPS + .2:.2f}', '-f', 's16le', '-'], capture_output=True).stdout
            a = np.frombuffer(b, '<i2').astype(np.float32) / 32768 if len(b) > 800 else None
            if a is not None and a.std() > 1e-4:
                spf = 8000 // FPS; nn = len(a) // spf; e = np.sqrt((a[:nn * spf].reshape(nn, spf) ** 2).mean(1)); self._env[k] = (e / (np.percentile(e, 95) + 1e-6)).clip(0, 1); self._env[k + ('real',)] = True
            else: self._env[k] = None
        return self._env[k]

def shot_full(ctx, cid, t_in, src_t, u, dur, zoom=(1.0, 1.10), drift=0.0, cx=None, cy=.5, rot=0.0):
    """Full-bleed 9:16 shot with slow push-in (virtual camera) and optional drift/rotation."""
    fr = ctx.F.frame(cid, t_in, src_t, max_h=1080); fx = ctx.focus(cid, t_in) if cx is None else cx
    z = lerp(zoom[0], zoom[1], ease_io(clamp(u / max(dur, .01)))); fx = clamp(fx + drift * (u / max(dur, .01) - .5), .1, .9)
    img, box = D.fit_cover(fr, W, H, fx, cy, z)
    if abs(rot) > 1e-3:
        im = Image.fromarray(img).rotate(rot * np.sin(u / max(dur, .01) * 2.4), resample=Image.BICUBIC); img = np.asarray(im.resize((W, H)))
        img = D.scale_about(img, 1.03)
    return img

def monitor(ctx, c, cid, t_in, src_t, box=(1000, 860), center=(540, 700), tint=None, scan=True):
    """Fit (no crop) a clip into a max box, drawn as a framed monitor. Returns (x,y,w,h)."""
    m = ctx.F.meta(cid); ar = m['width'] / m['height']; bw, bh = box
    w = min(bw, bh * ar); h = w / ar; x = center[0] - w / 2; y = center[1] - h / 2
    fr = ctx.F.frame(cid, t_in, src_t, max_h=720); img = D.rs(fr, w, h)
    if scan:
        sl = np.ones((img.shape[0], 1, 1), np.float32); sl[::3] = .86; img = (img * sl).astype(np.uint8)
    D.paste(c, img, x, y)
    D.fill_rect(c, x - 3, y - 3, w + 6, 3, (255, 255, 255), .18); D.fill_rect(c, x - 3, y + h, w + 6, 3, (255, 255, 255), .18)
    return (x, y, w, h)

def ambient(ctx, cid, t_in, src_t, dark=.32, tint=(1, .9, .75)):
    fr = ctx.F.frame(cid, t_in, src_t, max_h=180); b = D.blur_bg(fr, dark=dark)
    return (b * np.array(tint, np.float32)).astype(np.uint8)

def headline(c, lines, x, y, size, cols, t0, t, lh=1.12, kind='black', track=-.01, anchor='l', shadow=6, stagger=.09, slam=False):
    for i, (ln, col) in enumerate(zip(lines, cols)):
        u = (t - t0 - i * stagger)
        if u < 0: continue
        e = ease_out(u / .22); sc = lerp(1.55 if slam else 1.0, 1.0, ease_out(u / .16)) if slam else lerp(.92, 1, out_back(u / .3))
        a = D.text_rgba(ln, kind, size, col, track=track, shadow=shadow)
        a = D.scale_rgba(a, sc) if abs(sc - 1) > 1e-3 else a
        if slam and u < .16: a = D.alpha_mul(a, .35 + .65 * (u / .16))
        yy = y + i * size * lh - (a.shape[0] - D.text_rgba(ln, kind, size, col, track=track, shadow=shadow).shape[0]) / 2
        xx = x if anchor == 'l' else x - a.shape[1] / 2
        D.paste(c, a, xx - (a.shape[1] - D.text_rgba(ln, kind, size, col, track=track, shadow=shadow).shape[1]) / 2 if anchor == 'l' else xx, yy, alpha=min(1, e * 1.4))

# =====================================================================================
def hook(ctx, t):
    SB = ctx.SB; imp = SB['cues']['impact']
    if t < imp:
        c = np.full((H, W, 3), (11, 11, 13), np.uint8); src = .30 + t
        fr = ctx.F.frame('e_gen2_dog', .30, src, max_h=720)
        w, h = W, int(W * fr.shape[0] / fr.shape[1]); y = 380
        img = D.rs(fr, w, h); sl = np.ones((h, 1, 1), np.float32); sl[::3] = .84; img = (img * sl).astype(np.uint8)
        D.paste(c, img, 0, y)
        prev = ctx.prev.get('hook'); box = (0, y, w, h)
        if prev is not None:
            mb = R.motion_box(prev, fr, box)
            if mb: R.reticle(c, mb, AM, 'TRACKING')
        ctx.prev['hook'] = fr.copy()
        R.chip(c, 'RUNWAY GEN-2 · 2023', 64, 300, 26, fg=PA, bg=(0, 0, 0), bga=.7, dot=AM if int(t * 3) % 2 == 0 else (90, 40, 10))
        D.draw_text(c, R.tc_str(t), 'mono', 26, W - 64, y + h + 16, (200, 200, 200), anchor='r', track=.06)
        headline(c, ['AI VIDEO', 'USED TO LOOK', 'LIKE THIS.'], 64, 1090, 112, [PA, PA, AM], 0.0, t, lh=1.13, stagger=.14)
        return c
    u = t - imp; end = SB['scenes'][0]['t1'] - imp
    tin = ctx.F.pick('n_veo3_owl', 0, 3.0); c = shot_full(ctx, 'n_veo3_owl', tin, tin + u, u, end + .6, zoom=(1.02, 1.16))
    R.gradient_v(c, 900, H, 0, .78)
    R.chip(c, 'VEO 3 · MAY 2025', 64, 236, 26, fg=PA, bg=(0, 0, 0), bga=.55, dot=CY)
    headline(c, ['NOW LOOK', 'AT IT.'], 64, 1170, 132, [PA, CY], imp, t, lh=1.06, slam=True, stagger=.08)
    if u < .5:
        k = 1 - u / .5; c = D.chroma(c, int(18 * k * k)); c = D.shake(c, np.sin(u * 90) * 22 * k * k, np.cos(u * 77) * 16 * k * k)
    return c

def early_faces(ctx, t):
    SB = ctx.SB; cu = SB['cues']['faces']; t0 = SB['scenes'][1]['t0']
    if t < cu[1]: cid, tin = 'e_sd_park', 1.0; src = tin + (t - cu[0])
    elif t < cu[2]: cid, tin = 'e_2022_b', 2.0; src = tin + (t - cu[1])
    else: cid, tin = 'e_head', 0.3; src = tin + (t - cu[2])
    c = ambient(ctx, cid, tin, src, .30, (1.15, .85, .6)); box = monitor(ctx, c, cid, tin, src, (1000, 760), (540, 640))
    fr = ctx.F.frame(cid, tin, src, max_h=360); prev = ctx.prev.get(('ef', cid))
    if prev is not None and prev.shape == fr.shape:
        mb = R.motion_box(prev, fr, box)
        if mb: R.reticle(c, mb, AM, None)
    ctx.prev[('ef', cid)] = fr.copy()
    lab = ctx.F.meta(cid)['label']; R.chip(c, lab, 64, 226, 24, dot=AM if int(t * 2.5) % 2 == 0 else (90, 40, 10), bga=.6)
    D.draw_text(c, R.tc_str(t - t0), 'mono', 24, W - 64, box[1] + box[3] + 14, (215, 200, 180), anchor='r', track=.06)
    D.draw_text(c, '2022', 'black', 190, 56, 1042, AM, track=-.02, alpha=.95, shadow=0)
    D.draw_text(c, 'EVERY FRAME, REDRAWN' if cid == 'e_sd_park' else 'NO MEMORY BETWEEN FRAMES' if False else 'EARLY AI VIDEO', 'mono', 24, 66, 1236, (230, 200, 170), track=.14)
    return c

def early_montage(ctx, t):
    SB = ctx.SB; cu = SB['cues']['montage']; sec = SB['cues']['seconds']; end = SB['scenes'][2]['t1']
    seq = [('e_vp_cat', 0.0), ('e_gen1', 0.4), ('e_vp_dog', 0.0)]
    i = 2 if t >= cu[2] else 1 if t >= cu[1] else 0; cid, tin = seq[i]; ls = cu[i]; src = tin + (t - ls)
    m = ctx.F.meta(cid); src = min(src, m['duration'] - .05)
    c = ambient(ctx, cid, tin, src, .28, (1.15, .85, .6)); box = monitor(ctx, c, cid, tin, src, (1000, 760), (540, 640))
    fr = ctx.F.frame(cid, tin, src, max_h=360); prev = ctx.prev.get(('em', cid))
    if prev is not None and prev.shape == fr.shape:
        mb = R.motion_box(prev, fr, box)
        if mb: R.reticle(c, mb, AM, None)
    ctx.prev[('em', cid)] = fr.copy()
    R.chip(c, m['label'], 64, 226, 24, dot=AM, bga=.6)
    # clip-length clock: how long this clip has been alive
    age = t - ls; D.draw_text(c, f'CLIP  00:0{min(9, int(age))}.{int((age % 1) * 10)}', 'mono', 34, 64, box[1] + box[3] + 22, (245, 210, 170), track=.08)
    if t > sec: R.chip(c, 'END OF CLIP', W - 64, box[1] + box[3] + 20, 26, fg=(255, 255, 255), bg=D.RED, bga=.9, anchor='r')
    # CRT power-off in the last 0.35 s
    off = prog(t, end - .40, end - .04)
    if off > 0:
        k = ease_io(off); hh = max(2, int(H * (1 - k) ** 2)); band = c[H // 2 - hh // 2:H // 2 + hh // 2].copy(); c[:] = 0; c[H // 2 - hh // 2:H // 2 + hh // 2] = band
        if k > .7: D.fill_rect(c, W / 2 - (1 - k) * 500 - 20, H / 2 - 2, 2 * ((1 - k) * 500 + 20), 4, (255, 255, 255), .9)
    return c

# =====================================================================================
TL_NODES = [
    dict(year='2022', clip='e_2022_a', tin=0.4, lines=['MAKE-A-VIDEO · META', 'IMAGEN VIDEO · GOOGLE'], sub='RESEARCH PREVIEWS · SEP–OCT 2022', col=AM, late=False),
    dict(year='2023', clip='e_gen1', tin=0.0, lines=['RUNWAY GEN-2', 'STABLE VIDEO DIFFUSION'], sub='SHORT CLIPS ANYONE COULD TRY · 2023', col=AM, late=False),
    dict(year='2024', clip='m_sora_tokyo', tin=0.0, lines=['SORA · OPENAI', 'UP TO A FULL MINUTE'], sub='PREVIEW · FEB 15, 2024', col=PA, late=True),
    dict(year='2025', clip='n_veo3_owl', tin=0.0, lines=['VEO 3 · GOOGLE', 'VIDEO WITH NATIVE AUDIO'], sub='MAY 20, 2025  ·  SORA 2 · SEP 30, 2025', col=CY, late=True),
]
YEARS = [2022, 2023, 2024, 2025, 2026]

def tl_bar(c, k, u, y=232, col=AM):
    x0, x1 = 110, 970
    D.fill_rect(c, x0, y, x1 - x0, 3, (255, 255, 255), .22)
    px = lambda i: x0 + (x1 - x0) * i / 4
    cur = px(k) if k < 3 else px(3)
    D.fill_rect(c, x0, y - 1, (px(k) - x0) * ease_out(u / .5) + 0.0 if k > 0 else 1, 5, col, 1.0)
    for i, yr in enumerate(YEARS):
        on = i <= k; dd = 14 if i == k else 10
        pulse = 1 + .35 * np.sin(u * 7) if i == k else 1
        D.vector(c, lambda d, ss, ox, oy: d.ellipse([(px(i) - dd * pulse - ox) * ss, (y + 1.5 - dd * pulse - oy) * ss, (px(i) + dd * pulse - ox) * ss, (y + 1.5 + dd * pulse - oy) * ss], fill=(tuple(col) if on else (90, 90, 96)) + (255,)), bbox=(px(i) - 30, y - 30, 60, 60))
        D.draw_text(c, str(yr), 'mono', 22, px(i), y + 26, PA if on else (120, 120, 126), anchor='c', track=.04)

def tl_node(ctx, t, k, u):
    SB = ctx.SB; nd = TL_NODES[k]; cid = nd['clip']; m = ctx.F.meta(cid); cu = SB['cues']
    tin = nd['tin']; src = tin + u
    if k == 2:   # Sora: clock runs; jump to the end of the shot on "minute"
        jump = cu['tl_jump'] - cu['tl'][2]; end = m['duration']
        if u < jump: src = tin + u
        else:
            e = ease_io(prog(u, jump, jump + .45)); src = lerp(tin + jump, end - 3.4, e) + (max(0, u - jump - .45))
        src = min(src, end - .05)
    if k == 3:
        tin = ctx.F.pick(cid, 0, 4.0); src = tin + u
    src = min(src, m['duration'] - .05)
    c = ambient(ctx, cid, tin if k != 2 else 0.0, src, .26, (1.1, .95, .85) if not nd['late'] else (.85, .95, 1.1))
    box = monitor(ctx, c, cid, tin if k != 2 else 0.0, src, (1000, 600), (540, 665))
    x, y, w, h = box
    tl_bar(c, k, u, 232, nd['col'])
    R.chip(c, 'ERA EXAMPLE · ' + m['label'], x, y - 50, 22, bga=.62, dot=nd['col'])
    if k == 2:
        clk = src if src < 60 else 60; R.chip(c, f'SHOT CLOCK  0:{int(clk):02d}', x + w - 6, y + h - 60, 28, fg=(255, 255, 255), bg=(0, 0, 0), bga=.7, anchor='r', dot=D.RED)
    if k == 3:
        ev = ctx.env(cid, tin, 200); n = 48; bx, by, bw = x + 24, y + h - 70, w - 48
        for i in range(n):
            j = int((u * FPS) + (i - n) * .6); a = ev[j % len(ev)] if ev is not None and j >= 0 else (.25 + .25 * np.sin(u * 5 + i * .6)) * (u > 0)
            a = .12 + .88 * float(a) * (.85 + .15 * np.sin(i * 1.7 + u * 9)); hh = 8 + 50 * a
            D.fill_rect(c, bx + i * bw / n, by + 30 - hh / 2, bw / n - 4, hh, CY, .9)
        R.chip(c, 'NATIVE AUDIO', x + w - 6, y - 52, 22, fg=(0, 0, 0), bg=CY, bga=1, anchor='r')
    # year + text stack
    yr = nd['year']; enter = ease_out(u / .45)
    D.draw_text(c, yr, 'black', 176, 56, 962 + (1 - enter) * 60, nd['col'], track=-.02, alpha=enter, shadow=0)
    for i, ln in enumerate(nd['lines']):
        e = ease_out((u - .12 - i * .1) / .35); D.draw_text(c, ln, 'bold', 38, 64 + (1 - e) * 40, 1138 + i * 48, PA, track=.0, alpha=e, shadow=4)
    e = ease_out((u - .4) / .35); D.draw_text(c, nd['sub'], 'mono', 22, 66, 1238, (190, 190, 196), track=.09, alpha=e)
    return c

def timeline(ctx, t):
    SB = ctx.SB; tl = SB['cues']['tl']; ks = [0, 1, 2, 3]
    k = max(i for i in ks if t >= tl[i] - .0) if t >= tl[0] else 0
    u = t - tl[k]; c = tl_node(ctx, t, k, max(0, u))
    if k > 0 and u < .34:   # masked wipe between eras, previous node keeps playing underneath
        prev = tl_node(ctx, t, k - 1, t - tl[k - 1]); c = R.transition('slat' if k % 2 else 'iris', prev, c, u / .34, ring=nd_col(k))
    return c

def nd_col(k): return TL_NODES[k]['col']

# ---------------------------------------------------------------------------------
def _homography(src, dst):
    A = []; b = []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b += [u, v]
    return np.linalg.solve(np.array(A, np.float64), np.array(b, np.float64))

def warp_quad(c, img, quad, alpha=1.0, edge=None):
    """Draw RGB image `img` onto canvas c inside the projected quad (TL,TR,BR,BL)."""
    xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
    x0, y0, x1, y1 = int(max(0, min(xs) - 2)), int(max(0, min(ys) - 2)), int(min(W, max(xs) + 2)), int(min(H, max(ys) + 2))
    if x1 - x0 < 4 or y1 - y0 < 4: return
    ih, iw = img.shape[:2]; coef = _homography([(0, 0), (iw, 0), (iw, ih), (0, ih)], [(px - x0, py - y0) for px, py in quad])
    im = Image.fromarray(img).transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, tuple(coef), Image.BICUBIC)
    mk = Image.new('L', (iw, ih), 255).transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, tuple(coef), Image.BILINEAR)
    a = np.asarray(mk, np.float32)[..., None] / 255 * alpha; d = c[y0:y1, x0:x1]; d[:] = (d * (1 - a) + np.asarray(im) * a).astype(np.uint8)
    if edge is not None:
        D.vector(c, lambda dr, ss, ox, oy: dr.line([((px - ox) * ss, (py - oy) * ss) for px, py in quad + [quad[0]]], fill=tuple(edge) + (150,), width=2 * ss), bbox=(x0, y0, x1 - x0, y1 - y0))

def concept(ctx, t):
    SB = ctx.SB; s = SB['scenes'][4]; kw = SB['cues']['kw']; u = t - s['t0']; dur = s['t1'] - s['t0']
    c = np.full((H, W, 3), (6, 8, 12), np.uint8)
    yaw = np.radians(lerp(-38, 22, ease_io(u / dur))); pitch = np.radians(lerp(14, 6, ease_io(u / dur))); fdist = 1500.0; cxp, cyp = 540, 690; SC = 1.42
    merge = ease_io(prog(t, kw['merge'], kw['merge'] + 1.2))
    def proj(p):
        x, y, z = p; x, y = x * SC, y * SC; x, z = x * np.cos(yaw) - z * np.sin(yaw), x * np.sin(yaw) + z * np.cos(yaw); y, z = y * np.cos(pitch) - z * np.sin(pitch), y * np.sin(pitch) + z * np.cos(pitch)
        s_ = fdist / (fdist + z + 700); return (cxp + x * s_, cyp + y * s_), s_
    # floor grid (one vector layer)
    segs = []
    for gz in range(-4, 9): segs.append((proj((-700, 260, gz * 110))[0], proj((700, 260, gz * 110))[0]))
    for gx in range(-6, 7): segs.append((proj((gx * 115, 260, -440))[0], proj((gx * 115, 260, 990))[0]))
    D.vector(c, lambda d, ss, ox, oy: [d.line([(p0[0] * ss, p0[1] * ss), (p1[0] * ss, p1[1] * ss)], fill=(60, 120, 140, 70), width=2 * ss) for p0, p1 in segs], ss=1)
    cid = 'n_veo3_cafe'; tin = 0.3; K = int(round(lerp(8, 15, merge))); sp = lerp(96, 46, merge); rng = np.random.default_rng(3)
    jit = rng.normal(0, 1, (16, 3)) * (1 - merge)
    slabs = []
    dur_c = ctx.F.meta(cid)['duration']
    for i in range(K):
        st = min(tin + (i * 14 // K) * .35, dur_c - .3)              # stills sampled along the clip's own timeline
        th = D.fit_cover(ctx.still(cid, st), 512, 288, .5, .5, 1.0)[0]; z = (i - K / 2) * sp
        j = jit[i % 16]; hw, hh = 300, 169
        quad = []
        for (px, py) in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            p, _ = proj((px + j[0] * 26, py + j[1] * 18, z)); quad.append(p)
        tint = np.array([1 + .18 * j[2], 1, 1 - .18 * j[2]], np.float32); th = np.clip(th * tint, 0, 255).astype(np.uint8)
        slabs.append((z, th, quad))
    slabs.sort(key=lambda s_: -(s_[0] * np.cos(yaw)))
    for z, th, quad in slabs: warp_quad(c, th, quad, alpha=lerp(.95, .8, merge), edge=(160, 230, 240))
    # time axis + tracked labels (connectors drawn in one layer, chips on top)
    a0, _ = proj((-360, 190, -K * sp / 2)); a1, _ = proj((-360, 190, K * sp / 2 + 40)); lines = [(a0, a1, CY, 3)]
    tags = [('LIGHT', (300, -169, -K * sp / 2 + 20), kw['light'], (255, 214, 120), 20, -110), ('WEIGHT', (300, 169, 0), kw['weight'], CY, 40, 70),
            ('MOMENTUM', (0, 190, K * sp / 2), kw['momentum'], (255, 140, 120), 20, 70), ('CAMERA', (-300, -169, K * sp / 2), kw['camera'], PA, -190, -90)]
    live = []
    for label, world, ts, col, dx, dy in tags:
        e = out_back(prog(t, ts, ts + .3))
        if e <= 0: continue
        p, _ = proj(world); q = (p[0] + dx * min(1, e), p[1] + dy * min(1, e)); lines.append((p, q, col, 2)); live.append((label, q, col))
    D.vector(c, lambda d, ss, ox, oy: [d.line([(p0[0] * ss, p0[1] * ss), (p1[0] * ss, p1[1] * ss)], fill=tuple(col) + (230,), width=w_ * ss) for p0, p1, col, w_ in lines], ss=1)
    D.draw_text(c, 'TIME  →', 'mono', 26, a1[0] + 10, a1[1] - 12, CY, track=.1)
    for label, q, col in live: R.chip(c, label, q[0], q[1] - 22, 30, fg=(0, 0, 0), bg=col, bga=1.0, kind='mono')
    # headline swap
    D.draw_text(c, 'FRAME BY FRAME' if merge < .5 else 'ACROSS TIME', 'black', 74, 64, 300, AM if merge < .5 else CY, track=-.01, shadow=0, alpha=1)
    if merge < .5: D.fill_rect(c, 64, 300 + 46, D.text_w('FRAME BY FRAME', 'black', 74, -.01) * ease_out(prog(t, kw['merge'] - .5, kw['merge'])), 6, D.RED, .95)
    return c

# =====================================================================================
def now(ctx, t):
    SB = ctx.SB; cu = SB['cues']['now']; s = SB['scenes'][5]; chips = SB['cues']['now_chips']
    seq = [('n_veo31', 0), ('n_veo3_cafe', 0), ('n_seedance', 0)]
    ends = [cu[1], cu[2], s['t1']]; i = 0 if t < cu[1] else 1 if t < cu[2] else 2
    cid, nth = seq[i]; st = cu[i]; dur = ends[i] - st + .3; u = max(0, t - st)
    tin = ctx.F.pick(cid, nth, max(3.0, dur)); src = tin + u
    c = shot_full(ctx, cid, tin, src, u, dur, zoom=(1.0, 1.12 if i != 1 else 1.2), drift=[.10, -.08, .06][i], rot=[.6, .0, -.5][i])
    R.gradient_v(c, 1000, H, 0, .72)
    m = ctx.F.meta(cid); R.chip(c, m['label'], 64, 236, 26, bga=.55, dot=CY)
    lab, ts = chips[i]; e = ease_out((t - ts) / .18)
    if t >= ts - .02:
        sc = lerp(1.35, 1.0, ease_out((t - ts) / .14)); tw = D.text_w(lab, 'black', 92, -.01)
        a = D.scale_rgba(D.text_rgba(lab, 'black', 92, PA, track=-.01, shadow=6), sc); D.paste(c, D.alpha_mul(a, min(1, e * 1.5)), 64 - (a.shape[1] - D.text_rgba(lab, 'black', 92, PA, track=-.01, shadow=6).shape[1]) / 2, 1000 + (D.text_rgba(lab, 'black', 92, PA, track=-.01, shadow=6).shape[0] - a.shape[0]) / 2)
        D.fill_rect(c, 72, 1000 + 112, tw * ease_out((t - ts - .05) / .3), 6, CY, 1)
    # impact entry
    v = t - st
    if i == 0 and 0 <= v < .3: c = D.chroma(c, int(10 * (1 - v / .3)))
    return c

def styles(ctx, t):
    SB = ctx.SB; st = SB['cues']['styles']; s = SB['scenes'][6]; lo = ['n_veo3_owl', 'm_sora_mammoth', 'm_sora_gold', 'm_hailuo']
    order = [(0, 'm_sora_mammoth'), (1, 'n_veo3_owl'), (2, 'm_sora_gold'), (3, 'm_hailuo')]
    i = max(j for j in range(4) if t >= st[j][0] - 1e-6); cid = order[i][1]; u = t - st[i][0]
    tin = ctx.F.pick(cid, 1 if cid == 'n_veo3_owl' else 0, 3.0); c = shot_full(ctx, cid, tin, tin + u, u, 2.0, zoom=(1.0, 1.10), drift=.06 * (1 if i % 2 else -1))
    R.gradient_v(c, 0, 520, .6, 0); R.gradient_v(c, 1000, H, 0, .6)
    R.chip(c, ctx.F.meta(cid)['label'], 64, 236, 24, bga=.55, dot=CY)
    lab = st[i][1]; sc = lerp(1.28, 1.0, ease_out(u / .16)); words = lab.split()
    size = 96 if len(words) == 1 else 104
    for j, wd in enumerate(words):
        a = D.scale_rgba(D.text_rgba(wd, 'black', size, PA if j == 0 else CY if j == len(words) - 1 and len(words) > 1 else PA, track=-.01, shadow=6), sc)
        D.paste(c, D.alpha_mul(a, min(1, u / .08)), 56, 330 + j * size * 1.08)
    D.fill_rect(c, 64, 330 + len(words) * size * 1.08 + 18, 240 * ease_out(u / .3), 6, CY, 1)
    D.draw_text(c, f'0{i + 1} / 04', 'mono', 24, W - 64, 236, PA, anchor='r', track=.1)
    if u < .22: c = D.chroma(c, int(12 * (1 - u / .22)))
    return c

def compare(ctx, t):
    SB = ctx.SB; cu = SB['cues']['compare']; s = SB['scenes'][7]; u = t - cu['split']
    a_id, a_in = 'e_sd_park', 3.0; b_id = 'n_veo3_cafe'; b_in = ctx.F.pick(b_id, 0, 5.0)
    fa = ctx.F.frame(a_id, a_in, a_in + u, max_h=720); fb = ctx.F.frame(b_id, b_in, b_in + u, max_h=1080)
    c = np.full((H, W, 3), (7, 8, 10), np.uint8)
    full = ease_io(prog(t, cu['full'], cu['full'] + .5))
    # geometry: stacked windows -> bottom window expands to full bleed
    ty, th_ = 226, 500; by, bh = 748, 500
    A = (int(lerp(40, 40, full)), int(lerp(ty, -H, full)), 1000, th_)
    B = (int(lerp(40, 0, full)), int(lerp(by, 0, full)), int(lerp(1000, W, full)), int(lerp(bh, H, full)))
    ia = D.fit_cover(fa, A[2], A[3], .5, .38, 1.0)[0]; ia = D.grade(ia, sat=.8, contrast=.94, lift=.02, tint=(1.05, 1, .92))
    if A[1] > -A[3]: D.paste(c, ia, A[0], A[1])
    twice = t - cu['twice']; punch = 0.0
    if twice > -.05:
        for k0 in (0.0, .25):
            v = twice - k0
            if 0 <= v < .2: punch = max(punch, 1 - v / .2)
    ib = D.fit_cover(fb, B[2], B[3], ctx.focus(b_id, b_in) if full > .5 else .5, .45, 1.0 + .10 * punch + .06 * full)[0]
    D.paste(c, ib, B[0], B[1])
    if full < .98:
        R.chip(c, '2022 · STABLE DIFFUSION', 64, A[1] + 16, 22, bga=.62, dot=AM); R.chip(c, '2025 · VEO 3', 64, B[1] + 16, 22, bga=.62, dot=CY)
        D.fill_rect(c, 40, A[1] + A[3] + 8, 1000, 4, (255, 255, 255), .7 * (1 - full))
        D.draw_text(c, 'THEN', 'black', 46, 1010, A[1] + A[3] - 74, AM, anchor='r', alpha=1 - full, shadow=4); D.draw_text(c, 'NOW', 'black', 46, 1010, B[1] + B[3] - 74, CY, anchor='r', alpha=1 - full, shadow=4)
    else:
        R.gradient_v(c, 1000, H, 0, .6); R.chip(c, '2025 · VEO 3', 64, 236, 24, bga=.55, dot=CY)
    if punch > 0: c = (c * (1 - .35 * punch) + 255 * .35 * punch).astype(np.uint8)
    return c

# ---------------------------------------------------------------------------------
STRIP = ['e_2022_a', 'e_sd_park', 'e_gen1', 'e_vp_cat', 'e_head', 'm_sora_pup', 'm_gen3', 'm_hailuo', 'n_veo31', 'n_seedance', 'n_sora2', 'n_veo3_owl']
STILL_T = dict(e_2022_a=.5, e_sd_park=3, e_gen1=1.5, e_vp_cat=.5, e_head=1, m_sora_pup=2, m_gen3=2, m_hailuo=2, n_veo31=3, n_seedance=3, n_sora2=6, n_veo3_owl=6)

def mblur_v(img, px):
    px = int(px)
    if px < 2: return img
    acc = np.zeros(img.shape, np.float32); n = min(px, 12)
    for k in range(n): acc += np.roll(img, int((k / (n - 1) - .5) * px), 0)
    return (acc / n).astype(np.uint8)

def finale(ctx, t):
    SB = ctx.SB; f = SB['cues']['finale']; u = t - f['start']
    c = np.full((H, W, 3), (5, 5, 7), np.uint8)
    if t < f['now']:
        # a film strip accelerates upward; frames evolve from soft/amber (2022) to crisp/vivid (today); it locks on "camera"
        n = len(STRIP); fw, fh_, pitch, sx = 600, 338, 400, 240
        s_tot = 1500 + (n - 1) * pitch - (900 - fh_ / 2); dur = f['camera'] - f['start']; x = clamp(u / dur)
        pos = s_tot * x ** 2.1; speed = s_tot * 2.1 * x ** 1.1 / dur if x < 1 else 0
        D.fill_rect(c, sx - 70, 0, fw + 140, H, (15, 15, 17), 1)
        for i in range(n):
            y = 1500 + i * pitch - pos
            if y < -fh_ - 60 or y > H + 60: continue
            cid = STRIP[i]; still = ctx.still(cid, STILL_T[cid]); q = i / (n - 1)
            img = D.fit_cover(still, fw, fh_, .5, .5, 1.0)[0]
            if q < .45:
                img = D.rs(D.rs(img, fw // 4, fh_ // 4, Image.BOX), fw, fh_, Image.NEAREST); img = D.grade(img, sat=.75, contrast=.94, lift=.03, tint=(1.05, 1, .9))
            else: img = D.grade(img, sat=1.06, contrast=1.06)
            D.paste(c, img, sx, y)
            for hole in range(4):
                for hx in (sx - 50, sx + fw + 22): D.fill_rect(c, hx, y + 24 + hole * 84, 28, 40, (2, 2, 3), 1)
            D.fill_rect(c, sx - 8, y + fh_ + 28, fw + 16, 4, (70, 70, 76), 1)
        c = mblur_v(c, speed / 60)
        R.gradient_v(c, 0, 300, .95, 0); R.gradient_v(c, 1250, H, 0, .95)
        yr = int(lerp(2022, 2026, clamp(pos / s_tot)))
        D.draw_text(c, str(yr), 'black', 120, 64, 250, AM if yr < 2024 else CY, track=-.02, shadow=0)
        if t >= f['camera']:   # lock-on
            k = ease_out((t - f['camera']) / .12); yy = 1500 + (n - 1) * pitch - s_tot
            R.reticle(c, (sx - 20, yy - 20, fw + 40, fh_ + 40), CY)
            if k < 1: c = (c * (1 - .5 * (1 - k)) + 255 * .5 * (1 - k)).astype(np.uint8)
        return c
    # phase 2: a prompt types itself; on the last word the frame is "rendered"
    e = ease_out(prog(t, f['now'] - .05, f['now'] + .25))
    txt = 'a film begins with a sentence.'; a = clamp((t - f['type0']) / max(.2, f['sentence'] + .55 - f['type0'])); n_ch = int(len(txt) * a)
    R.chip(c, 'PROMPT', 64, 960, 24, fg=(0, 0, 0), bg=CY, bga=1, alpha=e)
    D.vector(c, lambda d, ss, ox, oy: R.rrect(d, ss, ox, oy, 64, 1020, 952, 130, 22, fill=(18, 20, 24, 255), outline=(70, 200, 210, 200), width=2), bbox=(58, 1014, 964, 142), alpha=e)
    shown = txt[:n_ch]; D.draw_text(c, shown, 'inter', 46, 100, 1056, PA, alpha=e)
    if (int(t * 2.2) % 2 == 0) or n_ch < len(txt): cx = 100 + D.text_w(shown, 'inter', 46); D.fill_rect(c, cx + 4, 1062, 5, 54, CY, e)
    rt = t - f['render']
    if rt >= 0:
        k = ease_out(rt / .5); cid = 'n_veo3_owl'; tin = ctx.F.pick(cid, 0, 3.5) + 3.0
        fr = ctx.F.frame(cid, tin, tin + rt, max_h=1080); win = D.fit_cover(fr, W, 452, ctx.focus(cid, tin), .5, 1.0 + .05 * rt)[0]
        hh = int(452 * k); y0 = 470 + (452 - hh) // 2
        if hh > 4: D.paste(c, win[(452 - hh) // 2:(452 - hh) // 2 + hh], 0, y0)
        D.fill_rect(c, 0, y0 - 3, W, 3, CY, .8 * k); D.fill_rect(c, 0, y0 + hh, W, 3, CY, .8 * k)
        R.chip(c, 'VEO 3 · MAY 2025', 64, 420, 22, bga=.6, dot=CY, alpha=k)
        if rt < .3: c = (c * (1 - .5 * (1 - rt / .3)) + 255 * .5 * (1 - rt / .3)).astype(np.uint8)
    return c

def ease_in_(x): return D.ease_in(x, 2)

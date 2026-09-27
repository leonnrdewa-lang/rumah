#!/usr/bin/env python3
"""Tileable ground textures for the terrain shader (Sawit The Franchise v2).

Run:  python3 blender/ground_textures.py                  # all five textures
      python3 blender/ground_textures.py grass dirt       # only some
Flags: --check   also write <name>_3x3.png tiling mosaics + a seam report to $GT_SCRATCH (default /tmp/gt)
       --keep-raw  keep the raw Cycles render as $GT_SCRATCH/<name>_raw.png
       --from-raw  skip building / rendering and only redo the post-processing from that kept raw render

Output: game/assets/textures/ground/{grass,grass_dry,dirt,sand,mulch}.png  (512 x 512 RGB, seamless)

Scale: every texture shows TILE_M = 4 m of ground; sample it with  uv = world.xz / 4.0
(image up = world -Z / "far", matching the baked soft light from the upper left).

Method: each texture is a small 3D patch of ground built in Blender and rendered straight down
with an orthographic Cycles camera:
  * a displaced ground plane with a numpy-painted *periodic* albedo (FFT noise, so it wraps);
  * thousands of scattered, vertex-coloured grass blades / clover / leaf litter / frond bits /
    pebbles / twigs. Anything that crosses the tile border is duplicated on the opposite side,
    so the render tiles without seams;
  * soft sky light + a soft warm sun from the upper left.
The render is then given a wrap-around painterly (Kuwahara) filter and graded to the palette
anchors of ART_DIRECTION_V2.md (mean colour + contrast), so the shader only needs a light tint.
"""
import math
import os
import random
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import common as C  # noqa: E402

TILE = 4.0                     # metres of ground per texture
RES = 512
PAD = 16                       # extra rendered border (cropped) so denoiser / pixel filter edges never show
OUT_DIR = os.path.join(C.ROOT, "game", "assets", "textures", "ground")
CHECK_DIR = os.environ.get("GT_SCRATCH", "/tmp/gt")
TMP = tempfile.mkdtemp(prefix="groundtex_")
os.makedirs(OUT_DIR, exist_ok=True)


def lin(h):
    """sRGB hex -> linear rgb tuple (Blender colour space)."""
    return C.hex_rgba(h)[:3]


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def scale(c, k):
    return tuple(x * k for x in c)


# ============================================================ periodic noise (numpy, wraps at the tile edge)
def pnoise(n, sigma_px, seed, aniso=(1.0, 1.0)):
    """Zero-mean, unit-std periodic noise: white noise low-passed by a Gaussian of `sigma_px`."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    ky = np.fft.fftfreq(n)[:, None] * aniso[1]
    kx = np.fft.fftfreq(n)[None, :] * aniso[0]
    filt = np.exp(-2.0 * (math.pi * sigma_px) ** 2 * (kx ** 2 + ky ** 2))
    out = np.fft.ifft2(np.fft.fft2(w) * filt).real
    return (out - out.mean()) / (out.std() + 1e-9)


def fbm(n, sigma_px, seed, octaves=4, gain=0.55):
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for i in range(octaves):
        out += amp * pnoise(n, max(0.6, sigma_px / (2 ** i)), seed + 17 * i)
        tot += amp
        amp *= gain
    return out / tot


def gblur(a, sigma_px):
    """Periodic Gaussian blur (works on 2D or HxWxC arrays)."""
    n0, n1 = a.shape[0], a.shape[1]
    ky = np.fft.fftfreq(n0)[:, None]
    kx = np.fft.fftfreq(n1)[None, :]
    filt = np.exp(-2.0 * (math.pi * sigma_px) ** 2 * (kx ** 2 + ky ** 2))
    if a.ndim == 3:
        return np.stack([np.fft.ifft2(np.fft.fft2(a[..., c]) * filt).real for c in range(a.shape[2])], -1)
    return np.fft.ifft2(np.fft.fft2(a) * filt).real


class Field:
    """A periodic scalar field over the tile, sampled at world (x, y) in metres (bilinear, wraps)."""

    def __init__(self, arr):
        self.a = arr
        self.n = arr.shape[0]

    def __call__(self, x, y):
        n = self.n
        fx = ((x / TILE + 0.5) * n) % n
        fy = ((y / TILE + 0.5) * n) % n
        x0, y0 = int(fx), int(fy)
        tx, ty = fx - x0, fy - y0
        x1, y1 = (x0 + 1) % n, (y0 + 1) % n
        a = self.a
        return ((a[y0, x0] * (1 - tx) + a[y0, x1] * tx) * (1 - ty) +
                (a[y1, x0] * (1 - tx) + a[y1, x1] * tx) * ty)


# ============================================================ scatter batch (one mesh, vertex colours)
class Batch:
    def __init__(self):
        self.v, self.c, self.f = [], [], []

    def add(self, verts, faces, cols, x, y, radius, z=0.0):
        """Add local geometry at (x, y), plus wrap-around copies wherever it reaches over a tile edge."""
        h = TILE / 2 + (PAD + 4) * TILE / RES
        for dx in (-TILE, 0.0, TILE):
            for dy in (-TILE, 0.0, TILE):
                cx, cy = x + dx, y + dy
                if abs(cx) - radius > h or abs(cy) - radius > h:
                    continue
                b = len(self.v)
                self.v.extend((vx + cx, vy + cy, vz + z) for vx, vy, vz in verts)
                self.c.extend(cols)
                self.f.extend(tuple(b + i for i in f) for f in faces)

    def obj(self, name, material):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        flat = np.ones((len(self.c), 4), dtype=np.float32)
        flat[:, :3] = np.asarray(self.c, dtype=np.float32)
        attr.data.foreach_set("color", flat.ravel())
        for p in me.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        C.link(o)
        me.materials.append(material)
        print(f"  [{name}] verts={len(self.v)} faces={len(self.f)}")
        return o


def vcol_material(name, rough=0.85, sss=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    ca = nt.nodes.new("ShaderNodeVertexColor")
    ca.layer_name = "Col"
    nt.links.new(ca.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    return m


# ============================================================ element generators (local geometry)
def blade(rnd, L, w, lean, bend, ang, cb, ct, segs=3):
    """Curved tapered grass blade from the origin; colour base cb -> tip ct."""
    d = (math.cos(ang), math.sin(ang))
    s = (-d[1], d[0])
    pts = [(0.0, 0.0, 0.0)]
    x = y = z = 0.0
    for i in range(segs):
        a = lean + bend * (i + 0.5) / segs
        st = L / segs
        x += d[0] * math.sin(a) * st
        y += d[1] * math.sin(a) * st
        z += math.cos(a) * st
        pts.append((x, y, z))
    verts, cols, faces = [], [], []
    for i in range(segs):
        t = i / segs
        hw = w / 2 * (1 - t) ** 0.6
        px, py, pz = pts[i]
        verts += [(px + s[0] * hw, py + s[1] * hw, pz), (px - s[0] * hw, py - s[1] * hw, pz)]
        c = mix(cb, ct, t)
        cols += [c, c]
    verts.append(pts[-1])
    cols.append(ct)
    for i in range(segs - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    faces.append((2 * (segs - 1), 2 * (segs - 1) + 1, 2 * segs))
    return verts, faces, cols, L * 1.05


def leaf_flat(rnd, l, w, ang, col, col_mid=None, z=0.0, curl=0.0, notch=False):
    """Flat lanceolate (or obcordate when notch=True) leaf lying on the ground, base at the origin."""
    d = (math.cos(ang), math.sin(ang))
    s = (-d[1], d[0])
    if notch:
        side = [(0.22, 0.26), (0.5, 0.46), (0.8, 0.46), (0.98, 0.24)]
        tip = (0.84, 0.0)
    else:
        side = [(0.2, 0.36), (0.45, 0.5), (0.72, 0.36)]
        tip = (1.0, 0.0)
    P = lambda t, hw, zz: (d[0] * l * t + s[0] * w * hw, d[1] * l * t + s[1] * w * hw, zz)
    rim = [P(0.0, 0.0, z)] + [P(t, hw, z + curl * 0.3) for t, hw in side] + [P(tip[0], 0.0, z + curl * 0.5)] + \
          [P(t, -hw, z + curl * 0.3) for t, hw in reversed(side)]
    verts = [P(0.5, 0.0, z + curl)] + rim
    cols = [col_mid or col] + [col] * len(rim)
    nr = len(rim)
    faces = [(0, 1 + k, 1 + (k + 1) % nr) for k in range(nr)]
    return verts, faces, cols, l


def clover(rnd, size, col, col_light, h):
    """Three heart-shaped leaflets at height h."""
    V, F, Cc = [], [], []
    a0 = rnd.uniform(0, 2 * math.pi)
    for k in range(3):
        ang = a0 + k * 2 * math.pi / 3 + rnd.uniform(-0.2, 0.2)
        l = size * rnd.uniform(0.85, 1.1)
        v, f, c, _ = leaf_flat(rnd, l, l * 1.25, ang, col, col_light, z=h, curl=0.004, notch=True)
        b = len(V)
        V += v
        Cc += c
        F += [tuple(b + i for i in ff) for ff in f]
    return V, F, Cc, size * 1.2


def strip(rnd, L, w, ang, col, col2, z=0.0, segs=5, arc=0.0, fold=0.0):
    """Long thin flat strip (dry palm leaflet / fibre) lying on the ground, slightly arced.
    fold > 0 raises the midrib (V-folded leaflet: the two halves catch the light differently)."""
    d = (math.cos(ang), math.sin(ang))
    s = (-d[1], d[0])
    V, Cc, F = [], [], []
    for i in range(segs + 1):
        t = i / segs
        off = arc * L * 4 * t * (1 - t)
        cx = d[0] * L * (t - 0.5) + s[0] * off
        cy = d[1] * L * (t - 0.5) + s[1] * off
        hw = w / 2 * (1.0 - 0.75 * abs(2 * t - 1) ** 3)
        zz = z + 0.004 * math.sin(math.pi * t) + rnd.uniform(0, 0.002)
        c = mix(col, col2, t)
        V += [(cx + s[0] * hw, cy + s[1] * hw, zz), (cx, cy, zz + fold * hw), (cx - s[0] * hw, cy - s[1] * hw, zz)]
        Cc += [c, scale(c, 1.08), scale(c, 0.9)]
    for i in range(segs):
        a = 3 * i
        F.append((a, a + 1, a + 4, a + 3))
        F.append((a + 1, a + 2, a + 5, a + 4))
    return V, F, Cc, L * 0.55


def chip(rnd, l, w, ang, col, z=0.003):
    """Small flat wood chip / bark flake."""
    d = (math.cos(ang), math.sin(ang))
    s = (-d[1], d[0])
    t = rnd.uniform(0.004, 0.008)
    V = []
    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x = d[0] * l / 2 * a + s[0] * w / 2 * b
        y = d[1] * l / 2 * a + s[1] * w / 2 * b
        V.append((x, y, z + t + rnd.uniform(-0.002, 0.002)))
    F = [(0, 1, 2, 3)]
    return V, F, [col, scale(col, 0.92), col, scale(col, 1.06)], max(l, w) * 0.75


_ICO = {}


def pebble(rnd, r, col, flat=0.55, sub=2, jit=0.18):
    """Irregular flattened pebble (ico sphere), sunk a little into the ground."""
    if sub not in _ICO:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        verts = [tuple(v.co) for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        _ICO[sub] = (verts, faces)
    verts, faces = _ICO[sub]
    sx, sy = r * rnd.uniform(0.8, 1.25), r * rnd.uniform(0.7, 1.0)
    rot = rnd.uniform(0, math.pi)
    cr, sr = math.cos(rot), math.sin(rot)
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    V, Cc = [], []
    for vx, vy, vz in verts:
        k = 1.0 + jit * (math.sin(3 * vx + ph[0]) * math.sin(2.5 * vy + ph[1]) + 0.5 * math.sin(4 * vz + ph[2]))
        x, y, z = vx * sx * k, vy * sy * k, vz * r * flat * k
        V.append((x * cr - y * sr, x * sr + y * cr, z + r * flat * 0.35))
        shade = 0.9 + 0.2 * (vz * 0.5 + 0.5)
        Cc.append(scale(col, shade * rnd.uniform(0.95, 1.05)))
    return V, faces, Cc, max(sx, sy) * 1.3


def twig(rnd, L, r, ang, col, z=0.005):
    d = (math.cos(ang), math.sin(ang))
    s = (-d[1], d[0])
    bend = rnd.uniform(-0.25, 0.25)
    cpts = []
    for i in range(3):
        t = i / 2
        off = bend * L * 0.5 * (1 - abs(2 * t - 1))
        cpts.append((d[0] * L * (t - 0.5) + s[0] * off, d[1] * L * (t - 0.5) + s[1] * off, z + r))
    V, F, Cc = [], [], []
    for (cx, cy, cz) in cpts:
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            V.append((cx + s[0] * r * math.cos(a), cy + s[1] * r * math.cos(a), cz + r * math.sin(a)))
            Cc.append(scale(col, 0.8 + 0.25 * (math.sin(a) * 0.5 + 0.5)))
    for i in range(2):
        for k in range(4):
            a, b = i * 4 + k, i * 4 + (k + 1) % 4
            F.append((a, b, b + 4, a + 4))
    return V, F, Cc, L * 0.6


# ============================================================ scene pieces
def ground_plane(height, albedo_png, margin=0.3, cells=300):
    """Displaced grid over [-TILE/2 - margin, TILE/2 + margin]^2, heights from a periodic Field,
    albedo from a periodic PNG mapped with uv = world / TILE (repeat)."""
    ext = TILE / 2 + margin
    n = cells
    xs = np.linspace(-ext, ext, n + 1)
    verts = []
    for y in xs:
        for x in xs:
            verts.append((x, y, height(x, y)))
    faces = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    me = bpy.data.meshes.new("ground")
    me.from_pydata(verts, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    co = np.array(verts)
    uvs = np.empty((len(me.loops), 2), dtype=np.float32)
    vi = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", vi)
    uvs[:, 0] = co[vi, 0] / TILE + 0.5
    uvs[:, 1] = co[vi, 1] / TILE + 0.5
    uv.data.foreach_set("uv", uvs.ravel())
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("ground", me)
    C.link(o)
    m = bpy.data.materials.new("M_GroundTex")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(albedo_png)
    tex.extension = "REPEAT"
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.95
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    me.materials.append(m)
    return o


def save_albedo(arr, name):
    """arr: (n, n, 3) sRGB 0..1 in world orientation (row 0 = y = -TILE/2). Saved flipped for Blender."""
    from PIL import Image
    img = (np.clip(np.flipud(arr), 0, 1) * 255 + 0.5).astype(np.uint8)
    p = os.path.join(TMP, name + "_albedo.png")
    Image.fromarray(img).save(p)
    return p


def srgb_arr(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def paint(n, noise, stops):
    """Map a noise field to a colour ramp: stops = [(value, hex), ...] (sRGB, linear interpolation)."""
    vals = [s for s, _ in stops]
    cols = np.array([srgb_arr(h) for _, h in stops])
    out = np.empty((n, n, 3))
    for c in range(3):
        out[..., c] = np.interp(noise, vals, cols[:, c])
    return out


def setup_render(sun_strength=2.6, sky=0.85, sun_elev=52.0, sun_az=135.0, samples=24):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 4
    s.render.threads_mode = "FIXED"
    s.render.threads = 3
    s.render.resolution_x = RES + 2 * PAD
    s.render.resolution_y = RES + 2 * PAD
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    if s.world is None:
        s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bg = s.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.82, 0.9, 1.0, 1.0)
    bg.inputs[1].default_value = sky
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = sun_strength
    sun.data.angle = math.radians(28)
    sun.data.color = (1.0, 0.95, 0.85)
    el, az = math.radians(sun_elev), math.radians(sun_az)
    # light travels FROM the upper-left of the image (-X, +Y) down onto the ground
    dirv = Vector((-math.cos(el) * math.cos(az), -math.cos(el) * math.sin(az), -math.sin(el)))
    sun.rotation_euler = dirv.to_track_quat("-Z", "Y").to_euler()
    C.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = TILE * (RES + 2 * PAD) / RES
    cam.data.clip_end = 50
    cam.location = (0, 0, 10)
    cam.rotation_euler = (0, 0, 0)
    C.link(cam)
    s.camera = cam


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ============================================================ post: painterly filter + grade
def kuwahara(img, r=2):
    """Wrap-around Kuwahara filter (painterly, edge preserving)."""
    k = r + 1
    lum = img @ np.array([0.3, 0.59, 0.11])

    def box(a):
        s = np.zeros_like(a)
        for dy in range(k):
            for dx in range(k):
                s += np.roll(a, (-dy, -dx), axis=(0, 1))
        return s / (k * k)
    m = box(img)
    m2 = box(lum ** 2)
    ml = box(lum)
    var = m2 - ml ** 2
    best = None
    bestv = None
    for sy, sx in ((r, r), (r, 0), (0, r), (0, 0)):
        mv = np.roll(m, (sy, sx), axis=(0, 1))
        vv = np.roll(var, (sy, sx), axis=(0, 1))
        if best is None:
            best, bestv = mv.copy(), vv.copy()
        else:
            sel = vv < bestv
            best[sel] = mv[sel]
            bestv[sel] = vv[sel]
    return best


def grade(img, mean_hex, lum_std):
    m = img.reshape(-1, 3).mean(0)
    lum = img @ np.array([0.3, 0.59, 0.11])
    k = lum_std / (lum.std() + 1e-9)
    return (img - m) * k + srgb_arr(mean_hex)


def painterly(img, seed, soft=1.3, amount=0.5, blotch=0.07, sigma=12.0):
    """Soften the blade-level noise and lay soft, periodic light/dark patches over it (light patches
    lean yellow, dark ones blue-green), so the grass reads as painted rather than as a lawn photo."""
    n = img.shape[0]
    img = img * (1 - amount) + gblur(img, soft) * amount
    b = 0.75 * pnoise(n, sigma, seed) + 0.35 * pnoise(n, sigma * 0.4, seed + 1)
    b = 1.8 * np.tanh(b / 1.8)          # soft-limit the extremes: no single dark / light blob that repeats per tile
    img = img * (1 + blotch * b)[..., None]
    img[..., 0] += 0.018 * b
    img[..., 2] -= 0.01 * b
    return img


def finish_texture(render_png, name, mean_hex, lum_std, kuwa=2, soften=0.0, sat=1.0, flatten=0.6, paint_kw=None):
    from PIL import Image
    img = np.asarray(Image.open(render_png).convert("RGB")).astype(np.float64) / 255.0
    img = img[PAD:PAD + RES, PAD:PAD + RES]
    if paint_kw is not None:
        img = painterly(img, **paint_kw)
    if flatten:
        # damp the large blotches (> ~0.3 m) that would make the 4 m repeat visible; the terrain shader
        # adds its own large-scale variation
        low = gblur(img, 36)
        img = img - flatten * (low - low.reshape(-1, 3).mean(0))
    if kuwa:
        img = kuwahara(img, kuwa)
    if soften:
        img = img * (1 - 0.5) + gblur(img, soften) * 0.5
    if sat != 1.0:
        g = (img @ np.array([0.3, 0.59, 0.11]))[..., None]
        img = g + (img - g) * sat
    img = grade(img, mean_hex, lum_std)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    path = os.path.join(OUT_DIR, name + ".png")
    Image.fromarray(out).save(path, optimize=True)
    print(f"[texture] {path}  mean={out.reshape(-1, 3).mean(0).round(1)}")
    return path


# ============================================================ the five textures
def uniform_xy(rnd):
    return rnd.uniform(-TILE / 2, TILE / 2), rnd.uniform(-TILE / 2, TILE / 2)


def build_grass(dry=False):
    name = "grass_dry" if dry else "grass"
    seed = 11 if dry else 7
    rnd = random.Random(seed)
    n = RES
    clump = Field(fbm(n, 22, seed + 1, 3))           # grass tone patches (~0.5 m)
    fine = Field(pnoise(n, 3, seed + 2))
    height = Field(fbm(n, 30, seed + 3, 3) * 0.006)
    # --- ground under the grass: dark olive earth with a hint of green
    tone = fbm(n, 10, seed + 4, 3)
    if dry:
        alb = paint(n, tone, [(-2, "#6f6236"), (0, "#8c7c48"), (2, "#a89a5e")])
    else:
        alb = paint(n, tone, [(-2, "#3c4a22"), (0, "#4d5e2a"), (2, "#62743a")])
    ground_plane(height, save_albedo(alb, name))
    B = Batch()
    if dry:
        dark = [lin("#7f8a44"), lin("#74823f"), lin("#8e8a4c")]
        mid = [lin("#b7a96e"), lin("#c7ba6b"), lin("#a9a85a"), lin("#98a64e"), lin("#a6b056")]
        tips = [lin("#dbcb94"), lin("#d8c77e"), lin("#c9c86e"), lin("#b8c75e")]
        nbl, Lr, wr = 4600, (0.15, 0.3), (0.032, 0.048)
    else:
        dark = [lin("#4f6e2c"), lin("#5b7536"), lin("#56722f")]
        mid = [lin("#7fa047"), lin("#88a646"), lin("#98ac4d"), lin("#739a40")]
        tips = [lin("#b8c75e"), lin("#a9bd5d"), lin("#c2cb6a"), lin("#9fbd52")]
        nbl, Lr, wr = 4900, (0.14, 0.29), (0.036, 0.054)
    for _ in range(nbl):
        x, y = uniform_xy(rnd)
        c = clump(x, y)
        t = min(1.0, max(0.0, 0.5 + 0.35 * c + 0.25 * fine(x, y)))
        cb = mix(rnd.choice(dark), rnd.choice(mid), 0.25 + 0.35 * t)
        ct = mix(rnd.choice(mid), rnd.choice(tips), 0.25 + 0.7 * t * rnd.uniform(0.6, 1.0))
        L = rnd.uniform(*Lr) * (0.85 + 0.3 * t)
        v, f, cc, r = blade(rnd, L, rnd.uniform(*wr), rnd.uniform(0.45, 1.15), rnd.uniform(0.2, 0.7),
                            rnd.uniform(0, 2 * math.pi), cb, ct)
        B.add(v, f, cc, x, y, r, z=height(x, y) - 0.004)
    # --- clover patches
    # clover patches: big enough (leaflets 4-6 cm, ~4 texels at the game camera) to read as clover
    ncl_patch = 5 if dry else 12
    for _ in range(ncl_patch):
        px, py = uniform_xy(rnd)
        rad = rnd.uniform(0.14, 0.3) if dry else rnd.uniform(0.16, 0.36)
        for _k in range(int(rad * 30)):
            a = rnd.uniform(0, 2 * math.pi)
            rr = rad * math.sqrt(rnd.random())
            x, y = px + rr * math.cos(a), py + rr * math.sin(a)
            base = mix(lin("#4c8636"), lin("#63a044"), rnd.random())
            if dry:
                base = mix(base, lin("#aaa85a"), 0.78)
            v, f, cc, r = clover(rnd, rnd.uniform(0.042, 0.058), base, mix(base, lin("#c2de84"), 0.5),
                                 rnd.uniform(0.07, 0.13))
            B.add(v, f, cc, x, y, r, z=height(x, y))
    # --- leaf litter + dry frond leaflet bits + twigs + a few pebbles
    litter = [lin("#a0763e"), lin("#b8914e"), lin("#8a6a3e"), lin("#c9a55e"), lin("#7d6a44")]
    for _ in range(60 if dry else 40):
        x, y = uniform_xy(rnd)
        col = rnd.choice(litter)
        v, f, cc, r = leaf_flat(rnd, rnd.uniform(0.04, 0.075), rnd.uniform(0.02, 0.034), rnd.uniform(0, 6.28),
                                col, scale(col, 1.1), z=rnd.uniform(0.004, 0.03), curl=0.006)
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(14 if dry else 8):
        x, y = uniform_xy(rnd)
        col = rnd.choice([lin("#b59a5a"), lin("#9c8350"), lin("#c2a868")])
        v, f, cc, r = strip(rnd, rnd.uniform(0.14, 0.26), rnd.uniform(0.018, 0.026), rnd.uniform(0, 6.28), col,
                            scale(col, 0.85), z=rnd.uniform(0.01, 0.03), arc=rnd.uniform(-0.12, 0.12))
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(6):
        x, y = uniform_xy(rnd)
        v, f, cc, r = twig(rnd, rnd.uniform(0.06, 0.14), 0.004, rnd.uniform(0, 6.28), lin("#6b5238"))
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(6):
        x, y = uniform_xy(rnd)
        v, f, cc, r = pebble(rnd, rnd.uniform(0.01, 0.022), rnd.choice([lin("#a8a496"), lin("#b5a882")]), sub=1)
        B.add(v, f, cc, x, y, r, z=height(x, y) - 0.004)
    B.obj("scatter", vcol_material("M_Scatter"))
    return name


def build_dirt():
    name = "dirt"
    seed = 23
    rnd = random.Random(seed)
    n = RES
    # --- height: gentle lumps + fine grain + two faint wobbly tyre tracks along Y (period TILE)
    yy, xx = np.meshgrid((np.arange(n) + 0.5) / n * TILE - TILE / 2, (np.arange(n) + 0.5) / n * TILE - TILE / 2,
                         indexing="ij")
    h = fbm(n, 14, seed, 3) * 0.004 + pnoise(n, 5, seed + 1) * 0.0025 + pnoise(n, 1.2, seed + 2) * 0.001
    track = np.zeros((n, n))
    for x0, ph in ((-0.72, 0.4), (0.74, 1.9)):
        wob = 0.05 * np.sin(2 * math.pi * yy / TILE + ph) + 0.02 * np.sin(4 * math.pi * yy / TILE + 2 * ph)
        d = (xx - x0 - wob) / 0.1
        prof = np.exp(-d ** 4)
        tread = 0.5 + 0.5 * np.cos(2 * math.pi * yy / (TILE / 34))
        track += prof * (1.0 + 0.25 * tread * (np.abs(d) < 0.8))
    track *= 0.7 + 0.3 * (0.5 + 0.5 * pnoise(n, 40, seed + 5))        # fades in and out a little
    h = h * (1 - 0.5 * np.clip(track, 0, 1)) - 0.0075 * track
    height = Field(h)
    # --- albedo: packed earth #97865c .. #b7a96e, darker compacted track, light dusty patches, grain speckle
    tone = 0.75 * fbm(n, 7, seed + 6, 3) + 0.35 * pnoise(n, 1.6, seed + 7)
    alb = paint(n, tone, [(-2.2, "#94805a"), (-0.8, "#a58f63"), (0.2, "#b39c6c"), (1.2, "#c2ab7a"),
                                 (2.4, "#cdb888")])
    speck = pnoise(n, 0.7, seed + 8)
    alb *= (1 + 0.06 * np.clip(speck, -2, 2))[..., None]
    alb *= (1 - 0.11 * np.clip(track, 0, 1.3))[..., None]           # compacted, darker ruts
    ground_plane(height, save_albedo(alb, name))
    B = Batch()
    pcols = [lin("#b3aea0"), lin("#c9bd98"), lin("#a88f68"), lin("#9a8a72"), lin("#d4c49a"), lin("#8e877a")]
    clusters = [uniform_xy(rnd) for _ in range(7)]
    for i in range(320):
        if i < 150:
            cx, cy = rnd.choice(clusters)
            x, y = cx + rnd.gauss(0, 0.18), cy + rnd.gauss(0, 0.18)
        else:
            x, y = uniform_xy(rnd)
        r = rnd.uniform(0.008, 0.018) if rnd.random() < 0.8 else rnd.uniform(0.02, 0.04)
        v, f, cc, rr = pebble(rnd, r, rnd.choice(pcols), sub=1 if r < 0.015 else 2)
        B.add(v, f, cc, x, y, rr, z=height(x, y) - r * 0.2)
    for _ in range(26):   # clods of darker earth
        x, y = uniform_xy(rnd)
        r = rnd.uniform(0.01, 0.022)
        v, f, cc, rr = pebble(rnd, r, lin("#86744e"), flat=0.4, sub=1, jit=0.3)
        B.add(v, f, cc, x, y, rr, z=height(x, y) - r * 0.25)
    for _ in range(10):
        x, y = uniform_xy(rnd)
        col = rnd.choice([lin("#a0763e"), lin("#8a6a3e"), lin("#b59a5a")])
        v, f, cc, r = leaf_flat(rnd, rnd.uniform(0.025, 0.045), rnd.uniform(0.012, 0.02), rnd.uniform(0, 6.28), col,
                                scale(col, 1.1), z=0.004, curl=0.003)
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(5):
        x, y = uniform_xy(rnd)
        v, f, cc, r = twig(rnd, rnd.uniform(0.05, 0.12), 0.0035, rnd.uniform(0, 6.28), lin("#6b5238"))
        B.add(v, f, cc, x, y, r, z=height(x, y))
    B.obj("scatter", vcol_material("M_Scatter"))
    return name


def build_sand():
    name = "sand"
    seed = 31
    rnd = random.Random(seed)
    n = RES
    yy, xx = np.meshgrid((np.arange(n) + 0.5) / n * TILE, (np.arange(n) + 0.5) / n * TILE, indexing="ij")
    warp = fbm(n, 40, seed, 3) * 0.12
    ph = 2 * math.pi * (9 * xx + 4 * yy) / TILE + warp * 2 * math.pi / 0.4
    rip = np.sin(ph) + 0.35 * np.sin(2 * ph + 1.0)
    rip *= 0.75 + 0.25 * (0.5 + 0.5 * pnoise(n, 50, seed + 1))
    h = rip * 0.0032 + fbm(n, 16, seed + 2, 3) * 0.003 + pnoise(n, 1.0, seed + 3) * 0.0005
    height = Field(h)
    tone = fbm(n, 10, seed + 4, 3)
    alb = paint(n, tone, [(-2, "#c2b284"), (0, "#cdbf94"), (2, "#d9cca4")])
    speck = pnoise(n, 0.6, seed + 5)
    alb *= (1 + 0.045 * np.clip(speck, -2.5, 2.5))[..., None]
    alb *= (1 - 0.06 * rip)[..., None]
    ground_plane(height, save_albedo(alb, name))
    B = Batch()
    for _ in range(60):
        x, y = uniform_xy(rnd)
        r = rnd.uniform(0.004, 0.011)
        v, f, cc, rr = pebble(rnd, r, rnd.choice([lin("#b8ad98"), lin("#d2c3a0"), lin("#9f978a"), lin("#e8dcc2")]),
                              sub=1)
        B.add(v, f, cc, x, y, rr, z=height(x, y) - r * 0.2)
    for _ in range(12):   # little shell fragments
        x, y = uniform_xy(rnd)
        v, f, cc, rr = leaf_flat(rnd, rnd.uniform(0.012, 0.022), rnd.uniform(0.012, 0.02), rnd.uniform(0, 6.28),
                                 lin("#f4ece0"), lin("#e2c9b0"), z=0.002, curl=0.003, notch=True)
        B.add(v, f, cc, x, y, rr, z=height(x, y))
    for _ in range(6):
        x, y = uniform_xy(rnd)
        v, f, cc, r = twig(rnd, rnd.uniform(0.05, 0.12), 0.003, rnd.uniform(0, 6.28), lin("#8c7456"))
        B.add(v, f, cc, x, y, r, z=height(x, y) - 0.001)
    for _ in range(5):
        x, y = uniform_xy(rnd)
        col = rnd.choice([lin("#b59a5a"), lin("#a88f5a")])
        v, f, cc, r = strip(rnd, rnd.uniform(0.08, 0.15), 0.012, rnd.uniform(0, 6.28), col, scale(col, 0.9),
                            z=0.002, arc=rnd.uniform(-0.1, 0.1))
        B.add(v, f, cc, x, y, r, z=height(x, y))
    B.obj("scatter", vcol_material("M_Scatter"))
    return name


def build_mulch():
    name = "mulch"
    seed = 43
    rnd = random.Random(seed)
    n = RES
    h = fbm(n, 30, seed, 3) * 0.01 + pnoise(n, 3, seed + 1) * 0.002
    height = Field(h)
    tone = fbm(n, 14, seed + 2, 4)
    alb = paint(n, tone, [(-2, "#4a3222"), (0, "#5e412b"), (2, "#735237")])
    ground_plane(height, save_albedo(alb, name))
    B = Batch()
    frond_cols = [lin("#8a6a45"), lin("#9a7a4f"), lin("#74563a"), lin("#a88a5a"), lin("#6f5a42"), lin("#8c7058"),
                  lin("#7d6650"), lin("#946a44")]
    NS = 1500
    for i in range(NS):       # dead palm leaflets, layered (V-folded, 2.5-4 cm wide)
        x, y = uniform_xy(rnd)
        col = rnd.choice(frond_cols)
        L = rnd.uniform(0.12, 0.34)
        v, f, cc, r = strip(rnd, L, rnd.uniform(0.022, 0.04), rnd.uniform(0, 6.28), col, scale(col, 0.8),
                            z=0.002 + 0.03 * i / NS, arc=rnd.uniform(-0.12, 0.12), fold=rnd.uniform(0.2, 0.5))
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for i in range(1300):     # wood chips / bark flakes
        x, y = uniform_xy(rnd)
        col = rnd.choice([lin("#8a5a3a"), lin("#7a4c30"), lin("#9c6c46"), lin("#6a4430")])
        v, f, cc, r = chip(rnd, rnd.uniform(0.015, 0.035), rnd.uniform(0.008, 0.018), rnd.uniform(0, 6.28), col,
                           z=0.004 + 0.02 * rnd.random())
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(160):      # fallen leaves
        x, y = uniform_xy(rnd)
        col = rnd.choice([lin("#a0763e"), lin("#8a5e34"), lin("#b8864a"), lin("#6e5034")])
        v, f, cc, r = leaf_flat(rnd, rnd.uniform(0.03, 0.06), rnd.uniform(0.015, 0.026), rnd.uniform(0, 6.28), col,
                                scale(col, 1.12), z=rnd.uniform(0.01, 0.03), curl=0.006)
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(30):
        x, y = uniform_xy(rnd)
        v, f, cc, r = twig(rnd, rnd.uniform(0.06, 0.16), 0.004, rnd.uniform(0, 6.28), lin("#5c4230"), z=0.02)
        B.add(v, f, cc, x, y, r, z=height(x, y))
    for _ in range(10):       # a few loose palm fruitlets (brondolan)
        x, y = uniform_xy(rnd)
        v, f, cc, rr = pebble(rnd, rnd.uniform(0.011, 0.015), rnd.choice([lin("#c43b1c"), lin("#e0572a"), lin("#8a2a18")]),
                              flat=0.75, sub=1, jit=0.05)
        B.add(v, f, cc, x, y, rr, z=height(x, y) + 0.01)
    for _ in range(18):       # a little green: tiny sprouts
        x, y = uniform_xy(rnd)
        for _k in range(rnd.randint(2, 4)):
            v, f, cc, r = blade(rnd, rnd.uniform(0.03, 0.06), 0.008, rnd.uniform(0.3, 0.9), 0.4, rnd.uniform(0, 6.28),
                                lin("#5b7536"), lin("#98ac4d"))
            B.add(v, f, cc, x, y, r, z=height(x, y) + 0.01)
    B.obj("scatter", vcol_material("M_Scatter"))
    return name


# name -> (builder, grade mean, luminance std, kuwahara radius, soften sigma, saturation)
TEXTURES = {
    "grass": (lambda: build_grass(False), "#8ea84a", 0.07, 2, 0.0, 1.0),
    "grass_dry": (lambda: build_grass(True), "#b0a862", 0.07, 2, 0.0, 1.0),
    "dirt": (build_dirt, "#b8a16c", 0.05, 0, 0.0, 1.0),
    "sand": (build_sand, "#cdbf94", 0.05, 0, 0.0, 1.0),
    "mulch": (build_mulch, "#7a5a3c", 0.08, 0, 0.0, 1.0),
}


FLATTEN = {"grass": 0.75, "grass_dry": 0.75, "dirt": 0.75, "sand": 0.7, "mulch": 0.6}
PAINT = {"grass": dict(seed=91, soft=1.2, blotch=0.07, sigma=16.0), "grass_dry": dict(seed=95, soft=1.2, blotch=0.06, sigma=16.0),
         "mulch": dict(seed=93, amount=0.3, blotch=0.04, sigma=9.0)}


def check_tiling(path, name):
    """3x3 mosaic + seam metric (mean abs difference across the wrap edge vs. inside the image)."""
    from PIL import Image
    os.makedirs(CHECK_DIR, exist_ok=True)
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float64)
    w = im.size[0]
    big = Image.new("RGB", (w * 3, w * 3))
    for i in range(3):
        for j in range(3):
            big.paste(im, (i * w, j * w))
    big.resize((w * 3 // 2, w * 3 // 2), Image.LANCZOS).save(os.path.join(CHECK_DIR, name + "_3x3.png"))
    inside = np.abs(np.diff(a, axis=1)).mean()
    seam_x = np.abs(a[:, 0] - a[:, -1]).mean()
    seam_y = np.abs(a[0, :] - a[-1, :]).mean()
    print(f"[check] {name}: neighbour diff inside={inside:.2f}  seam x={seam_x:.2f}  seam y={seam_y:.2f}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or list(TEXTURES)
    for nm in names:
        builder, mean_hex, lstd, kuwa, soft, sat = TEXTURES[nm]
        kept = os.path.join(CHECK_DIR, nm + "_raw.png")
        if "--from-raw" in sys.argv and os.path.exists(kept):
            path = finish_texture(kept, nm, mean_hex, lstd, kuwa, soft, sat, FLATTEN.get(nm, 0.6), PAINT.get(nm))
            if "--check" in sys.argv:
                check_tiling(path, nm)
            continue
        C.reset_scene()
        print(f"[build] {nm}")
        builder()
        setup_render()
        raw = os.path.join(TMP, nm + "_render.png")
        render_to(raw)
        if "--keep-raw" in sys.argv:
            os.makedirs(CHECK_DIR, exist_ok=True)
            import shutil
            shutil.copy(raw, os.path.join(CHECK_DIR, nm + "_raw.png"))
        path = finish_texture(raw, nm, mean_hex, lstd, kuwa, soft, sat, FLATTEN.get(nm, 0.6), PAINT.get(nm))
        if "--check" in sys.argv:
            check_tiling(path, nm)


if __name__ == "__main__":
    main()

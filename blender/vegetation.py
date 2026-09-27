#!/usr/bin/env python3
"""Vegetation, rocks and nature props for Sawit The Franchise (art direction v2).

Run:  python3 blender/vegetation.py                 # textures (if missing) + every asset
      python3 blender/vegetation.py sawit_3 fern_a  # only the named assets
      python3 blender/vegetation.py textures        # re-render every foliage texture
      python3 blender/vegetation.py tex:frond       # re-render one texture
      python3 blender/vegetation.py scene           # composite test render at the game camera (reads the GLBs)
      python3 blender/vegetation.py scene_close     # same plantation corner from 8 m (detail check)
      python3 blender/vegetation.py scene_win       # palms within +-35 deg yaw (camera window towards the camera)
                                                    # -> blender/previews/veg_scene*.png (+ _vs_target)

Look (see ART_DIRECTION_V2.md and art/reference/07_target_gameplay.png): lush, layered,
broad-leaved.  Leaves are alpha-textured cards.  Every texture is made here: a high
detail model (hundreds of folded leaflets, veins, blades, petals...) is rendered
top-down / side-on with an orthographic Cycles camera and transparent film into
game/assets/textures/foliage/<name>.png (<= 512 px, colour dilated into the
transparent area so mipmaps do not get dark fringes).  The game assets then use
those textures on cheap curved / V-folded card strips:

  frond.png      oil-palm frond (sawit_*, spear leaves, trunk epiphytes, pile_fronds)
  frond_dry.png  dead frond (frond_fallen, pile_fronds)
  frond_coco.png coconut frond (narrow drooping leaflets)
  fern.png       pakis frond (fern_a, fern_b)
  leaves.png     2x2 atlas: canopy cluster | leafy sprig / broad leaf | keladi leaf
  grass.png      2 side-view clumps: lush | tall wild with dry blades
  flowers.png    2 side-view clumps: white daisies | yellow wedelia
  piringan.png   top-down weeded circle: red-brown mulch + dry frond bits, ragged edge
  banana.png     banana leaf: pleated blade, pale midrib, wind-torn slits (banana)

Material contract (the game relies on it):
  * textured materials export as glTF alphaMode MASK (texture alpha -> Math ROUND ->
    BSDF alpha) with baseColorFactor white, doubleSided for leaf cards;
  * every mesh carries an active colour attribute `Col` (COLOR_0): baked Cycles AO on
    solid parts (trunks, rocks, logs) and procedural darkening towards the plant centre
    / ground on cards.  It is a plain multiply (0.45..1), with a few mild tints (moss on
    trunks / logs, yellowing on old fronds);
  * one material name <-> one texture:  M_Frond=frond, M_FrondDry=frond_dry,
    M_CocoFrond=frond_coco, M_Fern=fern, M_Leaf / M_Bush / M_Canopy=leaves,
    M_Grass=grass, M_Flower=flowers, M_BananaLeaf=banana, M_Piringan=piringan (single-sided ground decal).
  * sawit_3: root Empty -> `sawit_3_body` + child Empty `Fruits` -> `Fruit_0..n`.  Its spreading fronds
    leave a "camera window" facing -Y (the game camera side) so the trunk and the front bunches show
    under the crown like in the target; keep the in-game yaw of sawit_3 within ~+-40 deg to use it.
  * vertex colours are soft-floored at 0.46 (finalize); leaf-card vertices stay >= 1.5 cm above z=0,
    solid rocks / logs may sink below it.
  * game/assets/textures/foliage/materials.json lists material -> texture for the game side.

Set VEG_SCRATCH=<dir> to also write extra close-up debug renders there.
Set VEG_ICONS=1 to also re-render the item icons icon_bibit / icon_tbs.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector, Matrix, noise  # noqa: E402

import common  # noqa: E402
from common import (  # noqa: E402
    reset_scene, mat, add_box, add_ico, join, shade_smooth, set_mat, empty, export_glb,
    count_tris, all_descendants, hex_rgba,
)

UP = Vector((0.0, 0.0, 1.0))
GOLDEN = math.radians(137.508)
SCRATCH = os.environ.get("VEG_SCRATCH")
TEX_DIR = os.path.join(common.ROOT, "game", "assets", "textures", "foliage")
os.makedirs(TEX_DIR, exist_ok=True)


# ============================================================ small math / colour helpers
def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def lin(h):
    """hex -> linear rgb tuple"""
    return tuple(hex_rgba(h)[:3])


def cmix(a, b, t):
    t = clamp01(t)
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def cscale(a, s):
    return tuple(min(1.0, x * s) for x in a)


def cmul(a, b):
    return tuple(min(1.0, x * y) for x, y in zip(a, b))


def grey(v):
    return (v, v, v)


def newell(pts):
    n = Vector((0.0, 0.0, 0.0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


# ============================================================ mesh builder
class Geo:
    """Mesh builder: verts with a colour (-> `Col` attribute), faces with material index,
    smooth flag and optional per-corner UVs."""

    def __init__(self):
        self.v, self.c, self.f, self.fm, self.fs, self.fuv = [], [], [], [], [], []
        self.n = {}  # optional custom vertex normals (index -> Vector), e.g. dome-shaded fruitlets

    def vert(self, co, col=(1.0, 1.0, 1.0), nrm=None):
        self.v.append(Vector(co))
        self.c.append(tuple(col)[:3])
        if nrm is not None:
            self.n[len(self.v) - 1] = Vector(nrm).normalized()
        return len(self.v) - 1

    def face(self, idx, mi=0, ref=None, smooth=False, uv=None):
        idx = list(idx)
        uv = list(uv) if uv is not None else None
        if ref is not None and newell([self.v[i] for i in idx]).dot(Vector(ref)) < 0:
            idx.reverse()
            if uv:
                uv.reverse()
        self.f.append(idx)
        self.fm.append(mi)
        self.fs.append(smooth)
        self.fuv.append(uv)

    def obj(self, name, mats, parent=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.fm)
        me.polygons.foreach_set("use_smooth", self.fs)
        if any(u is not None for u in self.fuv):
            flat = []
            for f, uv in zip(self.f, self.fuv):
                for p in (uv if uv is not None else [(0.0, 0.0)] * len(f)):
                    flat.extend(p)
            layer = me.uv_layers.new(name="UVMap")
            layer.data.foreach_set("uv", flat)
        cols = []
        for f in self.f:
            for i in f:
                c = self.c[i]
                cols.extend((c[0], c[1], c[2], 1.0))
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        attr.data.foreach_set("color", cols)
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
        me.update()
        if self.n:
            nrm = [self.n.get(i) or me.vertices[i].normal.copy() for i in range(len(self.v))]
            me.normals_split_custom_set_from_vertices(nrm)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        if parent is not None:
            o.parent = parent
        return o


_ICO = {}


def ico_data(subdiv):
    if subdiv not in _ICO:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
        verts = [v.co.copy() for v in bm.verts]
        faces = [[v.index for v in f.verts] for f in bm.faces]
        bm.free()
        _ICO[subdiv] = (verts, faces)
    return _ICO[subdiv]


def geo_blob(g, mi, center, radius, scale=(1, 1, 1), seed=0, subdiv=1, amp=0.2, freq=1.4, col_fn=None,
             uv_fn=None, floor=None, smooth=True, face_uv=None):
    """Lumpy ellipsoid added to Geo `g`. col_fn(p, n) -> rgb, uv_fn(p) -> (u, v);
    face_uv(points) -> [uv...] gives every face its own texture patch instead."""
    verts, faces = ico_data(subdiv)
    off = Vector((seed * 1.71, seed * 2.93, seed * 0.77))
    C = Vector(center)
    base = len(g.v)
    pts = []
    for co in verts:
        n = co.normalized()
        d = 1.0 + amp * noise.noise(n * freq + off)
        p = C + Vector((n.x * scale[0], n.y * scale[1], n.z * scale[2])) * radius * d
        if floor is not None and p.z < floor:
            p.z = floor
        pts.append(p)
        g.vert(p, col_fn(p, n) if col_fn else (1.0, 1.0, 1.0))
    for f in faces:
        idx = [base + i for i in f]
        ctr = sum((pts[i] for i in f), Vector()) / len(f)
        if face_uv:
            uv = face_uv([pts[i] for i in f])
        elif uv_fn:
            uv = [uv_fn(pts[i], verts[i].normalized()) for i in f]
        else:
            uv = None
        g.face(idx, mi, ref=ctr - C, smooth=smooth, uv=uv)
    return pts


def tube(g, path, radii, sides, mi, rnd=None, jitter=0.0, cap_top=False, smooth=True, twist=0.0, col_fn=None,
         uv_fn=None):
    """Generalised cylinder along a list of points. col_fn(j, i, p) -> rgb."""
    rows = []
    n = len(path)
    for j, (p, r) in enumerate(zip(path, radii)):
        p = Vector(p)
        T = (Vector(path[min(j + 1, n - 1)]) - Vector(path[max(j - 1, 0)])).normalized()
        S = T.cross(Vector((0.0, 1.0, 0.0)) if abs(T.y) < 0.9 else Vector((1.0, 0.0, 0.0))).normalized()
        B = T.cross(S)
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides + twist * j
            rr = r * (1.0 + (rnd.uniform(-jitter, jitter) if rnd else 0.0))
            q = p + (S * math.cos(a) + B * math.sin(a)) * rr
            row.append(g.vert(q, col_fn(j, i, q) if col_fn else (1.0, 1.0, 1.0)))
        rows.append((row, p))
    for j in range(n - 1):
        (ra, pa), (rb, pb) = rows[j], rows[j + 1]
        for i in range(sides):
            q = (ra[i], ra[(i + 1) % sides], rb[(i + 1) % sides], rb[i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            m = mi if not callable(mi) else mi(j)
            g.face(q, m, ref=fc - (pa + pb) * 0.5, smooth=smooth,
                   uv=[uv_fn(g.v[x]) for x in q] if uv_fn else None)
    if cap_top:
        row, p = rows[-1]
        tp = p + (Vector(path[-1]) - Vector(path[-2])).normalized() * radii[-1] * 0.8
        tip = g.vert(tp, col_fn(n - 1, 0, tp) if col_fn else (1.0, 1.0, 1.0))
        for i in range(sides):
            q = (row[i], row[(i + 1) % sides], tip)
            g.face(q, mi if not callable(mi) else mi(n - 1), ref=g.v[row[i]] - p, smooth=smooth,
                   uv=[uv_fn(g.v[x]) for x in q] if uv_fn else None)
    return rows


# ============================================================ materials
def _col_node(nt):
    ca = nt.nodes.new("ShaderNodeVertexColor")
    ca.layer_name = "Col"
    return ca


def _multiply_col(nt, color_socket_or_value, bsdf):
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    if isinstance(color_socket_or_value, tuple):
        mix.inputs[6].default_value = color_socket_or_value
    else:
        nt.links.new(color_socket_or_value, mix.inputs[6])
    nt.links.new(_col_node(nt).outputs[0], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])


def vmat(name, color, rough=0.9, spec=0.25):
    """Flat colour multiplied by the `Col` colour attribute (exported as baseColorFactor + COLOR_0)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    _multiply_col(nt, hex_rgba(common.PALETTE.get(color, color)), b)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = spec
    m.diffuse_color = hex_rgba(common.PALETTE.get(color, color))
    return m


def tex_image(tex):
    path = tex_path(tex)
    if not os.path.exists(path):
        raise SystemExit(f"texture {tex}.png missing - run: python3 blender/vegetation.py tex:{tex}")
    img = bpy.data.images.load(path, check_existing=True)
    img.alpha_mode = "STRAIGHT"
    return img


def tmat(name, tex, rough=0.75, spec=0.3, double=True):
    """Alpha-tested textured card material (glTF alphaMode MASK)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = tex_image(tex)
    t.extension = "EXTEND"
    _multiply_col(nt, t.outputs["Color"], b)
    r = nt.nodes.new("ShaderNodeMath")
    r.operation = "ROUND"
    nt.links.new(t.outputs["Alpha"], r.inputs[0])
    nt.links.new(r.outputs[0], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = spec
    m.use_backface_culling = not double
    if double:
        m["double_sided"] = True
    m["texture"] = tex
    return m


def M_frond():
    return tmat("M_Frond", "frond", rough=0.55, spec=0.35)


def M_frond_dry():
    return tmat("M_FrondDry", "frond_dry", rough=0.85, spec=0.2)


def M_leaf(name="M_Leaf"):
    return tmat(name, "leaves", rough=0.6, spec=0.35)


def M_grass():
    return tmat("M_Grass", "grass", rough=0.85, spec=0.2)


def M_flower():
    return tmat("M_Flower", "flowers", rough=0.8, spec=0.2)


def M_fern():
    return tmat("M_Fern", "fern", rough=0.7, spec=0.25)


def set_cols(o, fn):
    """(Re)write the `Col` attribute of a bpy mesh object from fn(world_pos, normal) -> rgb."""
    me = o.data
    if "Col" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["Col"])
    attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    mw = o.matrix_world
    cols = []
    for p in me.polygons:
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            c = fn(mw @ me.vertices[vi].co, (mw.to_3x3() @ me.vertices[vi].normal).normalized())
            cols.extend((c[0], c[1], c[2], 1.0))
    attr.data.foreach_set("color", cols)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index


def get_cols(o):
    me = o.data
    if "Col" not in me.color_attributes:
        return None
    attr = me.color_attributes["Col"]
    arr = [0.0] * (len(attr.data) * 4)
    attr.data.foreach_get("color", arr)
    return arr, attr.domain


def bake_ao(objs, samples=40, distance=1.0, floor=0.45, gamma=0.8, ground=True):
    """Cycles AO bake into `Col`, multiplied onto the colours the objects already had."""
    objs = [o for o in objs if o.type == "MESH"]
    keep = {o.name: get_cols(o) for o in objs}
    common.bake_vertex_ao(objs, samples=samples, distance=distance, floor=floor, gamma=gamma, ground=ground)
    for o in objs:
        old = keep[o.name]
        if old is None or old[1] != "CORNER":
            continue
        attr = o.data.color_attributes["Col"]
        cur = [0.0] * (len(attr.data) * 4)
        attr.data.foreach_get("color", cur)
        if len(cur) != len(old[0]):
            continue
        out = [a * b for a, b in zip(cur, old[0])]
        attr.data.foreach_set("color", out)


# ============================================================ texture generation (Cycles)
def tex_path(name):
    return os.path.join(TEX_DIR, name + ".png")


TEXTURES = {}


def texture(name, size):
    def deco(fn):
        TEXTURES[name] = (fn, size)
        return fn
    return deco


def _tex_setup(w, h, samples=24, world=0.8):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 4
    s.render.resolution_x = w
    s.render.resolution_y = h
    s.render.resolution_percentage = 100
    s.render.film_transparent = True
    s.render.filter_size = 1.2
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.render.image_settings.color_depth = "8"
    if s.world is None:
        s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bg = s.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs[1].default_value = world


def _tex_sun(direction, strength=1.4, angle=8.0):
    """direction: vector pointing from the scene TOWARD the sun."""
    sun = bpy.data.objects.new("_TexSun", bpy.data.lights.new("_TexSun", "SUN"))
    sun.data.energy = strength
    sun.data.angle = math.radians(angle)
    sun.rotation_euler = (-Vector(direction)).normalized().to_track_quat("-Z", "Y").to_euler()
    common.link(sun)
    return sun


def _tex_camera(target, span, elev=90.0):
    """Orthographic camera looking at `target`; elev=90 top-down (image up=+Y), elev=0 front (image up=+Z)."""
    cam = bpy.data.objects.new("_TexCam", bpy.data.cameras.new("_TexCam"))
    common.link(cam)
    e = math.radians(elev)
    d = Vector((0.0, math.cos(e), -math.sin(e)))  # view direction
    cam.location = Vector(target) - d * 20.0
    cam.rotation_euler = (math.radians(90.0 - elev), 0.0, 0.0)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = span
    cam.data.clip_end = 60.0
    bpy.context.scene.camera = cam
    return cam


def _tex_render(w, h, target, span, elev=90.0, samples=24, world=0.8, sun=((-0.25, 0.35, 1.0), 1.4)):
    _tex_setup(w, h, samples, world)
    _tex_camera(target, span, elev)
    if sun:
        _tex_sun(sun[0], sun[1])
    tmp = os.path.join(bpy.app.tempdir or "/tmp", f"_vegtex_{os.getpid()}.png")
    bpy.context.scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    arr = np.asarray(Image.open(tmp).convert("RGBA")).astype(np.float32) / 255.0
    os.remove(tmp)
    return arr


def _tex_save(arr, name):
    """Dilate colour into transparent texels (no dark mip fringes) and save the PNG."""
    from PIL import Image
    from scipy import ndimage
    a = arr.copy()
    solid = a[..., 3] >= 0.5
    if solid.any() and not solid.all():
        idx = ndimage.distance_transform_edt(~solid, return_distances=False, return_indices=True)
        rgb = a[..., :3][idx[0], idx[1]]
        rgb = ndimage.uniform_filter(rgb, size=(3, 3, 1))
        a[..., :3] = np.where(solid[..., None], a[..., :3], rgb)
    img = Image.fromarray(np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    img.save(tex_path(name), optimize=True)
    print(f"[texture] {name}.png {img.size}")


def _tex_mat(name="_TexMat", rough=0.55, spec=0.3):
    return vmat(name, "#ffffff", rough=rough, spec=spec)


def shape_lance(s):
    """Linear-lanceolate leaflet: broad base, long pointed tip."""
    return math.sin(math.pi * (0.1 + 0.9 * s ** 0.8)) ** 0.7


def shape_oval(s):
    return math.sin(math.pi * s ** 0.85) ** 0.65


def shape_acuminate(s):
    return (math.sin(math.pi * s ** 0.8) ** 0.7) * (1.0 - 0.25 * s ** 3)


def flat_leaf(g, base, direction, length, width, col_fn, st=5, fold=0.22, bend=0.0, z0=0.0, zdrop=0.0,
              shape=shape_lance, lobes=0, lobe_depth=0.35, mi=0, zbend=None):
    """A leaf in (roughly) the XY plane seen from above: midrib + two edges, V-folded (midrib up).
    col_fn(s, side) -> rgb, s: 0 base..1 tip, side -1 / 0 (midrib) / 1."""
    D = Vector((direction[0], direction[1], 0.0)).normalized()
    Sv = Vector((-D.y, D.x, 0.0))
    b = Vector(base)
    rows = []
    for i in range(st + 1):
        s = i / st
        c = b + D * length * s + Sv * bend * length * s * s
        # tangent follows the bend so the width stays perpendicular to the midrib
        Tn = (D + Sv * 2.0 * bend * s).normalized()
        Sn = Vector((-Tn.y, Tn.x, 0.0))
        hw = 0.5 * width * max(0.04, shape(s))
        if lobes:
            hw *= 1.0 - lobe_depth * (0.5 + 0.5 * math.cos(2.0 * math.pi * lobes * s))
        z = z0 - zdrop * s * s
        rows.append((g.vert(c + Sn * hw + UP * (z - fold * hw), col_fn(s, 1)),
                     g.vert(c + UP * z, col_fn(s, 0)),
                     g.vert(c - Sn * hw + UP * (z - fold * hw), col_fn(s, -1))))
    for i in range(st):
        a, c = rows[i], rows[i + 1]
        g.face((a[0], a[1], c[1], c[0]), mi, ref=UP)
        g.face((a[1], a[2], c[2], c[1]), mi, ref=UP)
    return rows


def strip_xy(g, pts, widths, col_fn, z=0.0, mi=0):
    """Flat ribbon along a 2D polyline (veins, rachis, stems seen from above)."""
    n = len(pts)
    rows = []
    for i, p in enumerate(pts):
        p = Vector((p[0], p[1], 0.0))
        a = Vector((pts[min(i + 1, n - 1)][0], pts[min(i + 1, n - 1)][1], 0.0))
        b = Vector((pts[max(i - 1, 0)][0], pts[max(i - 1, 0)][1], 0.0))
        T = (a - b).normalized()
        S = Vector((-T.y, T.x, 0.0))
        w = widths[i] * 0.5
        zz = z[i] if isinstance(z, (list, tuple)) else z
        c = col_fn(i / max(1, n - 1))
        rows.append((g.vert(p + S * w + UP * (zz - w * 0.3), cscale(c, 0.9)), g.vert(p + UP * zz, c),
                     g.vert(p - S * w + UP * (zz - w * 0.3), cscale(c, 0.9))))
    for i in range(n - 1):
        a, c = rows[i], rows[i + 1]
        g.face((a[0], a[1], c[1], c[0]), mi, ref=UP)
        g.face((a[1], a[2], c[2], c[1]), mi, ref=UP)


# ---------------------------------------------------------------- palm fronds (top-down, base at bottom)
FROND_KINDS = {
    #          leaflets/side, max len, max width, angle base/tip (deg from rachis)
    # the oil-palm frond keeps long, broad leaflets right to its end (blunt, fan-like tip as in the target)
    "frond": dict(N=18, lmax=0.56, wmax=0.17, th0=58, th1=30, seed=1, skip=0.0, blunt=True, y1=1.63,
                  base="#284f18", mid="#4f862a", tip="#8fb23e", rach0="#56682c", rach1="#b3b552", jit=0.1),
    "frond_dry": dict(N=24, lmax=0.5, wmax=0.1, th0=66, th1=40, seed=2, skip=0.14,
                      base="#6b4f2c", mid="#a07e45", tip="#c9a86a", rach0="#8a6a3e", rach1="#c7a468", jit=0.14),
    "frond_coco": dict(N=38, lmax=0.62, wmax=0.058, th0=74, th1=52, seed=3, skip=0.0,
                       base="#3f6e28", mid="#6f9d3a", tip="#a7bf55", rach0="#9a9350", rach1="#d8cc80", jit=0.06),
}


def _frond_model(kind):
    P = FROND_KINDS[kind]
    rnd = random.Random(P["seed"])
    m = _tex_mat(rough=0.6 if kind != "frond_dry" else 0.85, spec=0.18 if kind != "frond_dry" else 0.1)
    g = Geo()
    y0, y1, ytip = 0.24, P.get("y1", 1.93), (1.9 if P.get("blunt") else 1.985)
    cb, cm, ct = lin(P["base"]), lin(P["mid"]), lin(P["tip"])
    r0, r1 = lin(P["rach0"]), lin(P["rach1"])
    olive = (lin("#5d5b2f"), lin("#87873f"), lin("#a8a25a"))
    # rachis: raised ribbon, thick at the petiole
    n = 28
    pts = [(0.0, ytip * i / n) for i in range(n + 1)]
    widths = [lerp(0.045, 0.008, (i / n) ** 0.6) for i in range(n + 1)]
    strip_xy(g, pts, widths, lambda t: cmix(r0, r1, min(1.0, t * 2.2)), z=[0.09 - 0.03 * i / n for i in range(n + 1)])
    # petiole spines
    for k in range(9):
        y = 0.03 + 0.2 * k / 8
        for side in (-1, 1):
            b = Vector((side * 0.03, y, 0.07))
            flat_leaf(g, b, (side * 1.0, 0.5), 0.06 + 0.02 * rnd.random(), 0.018, lambda s, sd: cscale(r0, 0.8),
                      st=1, fold=0.0, shape=lambda s: 1.0 - s)
    for side in (-1, 1):
        for k in range(P["N"]):
            u = clamp01((k + 0.5 + 0.28 * side) / P["N"])
            if rnd.random() < P["skip"]:
                continue
            y = y0 + (y1 - y0) * u
            if P.get("blunt"):
                prof = lerp(0.4, 1.0, smoothstep(0.0, 0.32, u)) * (1.0 - 0.36 * u * u)
            else:
                prof = math.sin(math.pi * (0.07 + 0.91 * u)) ** 0.6 * (1.0 - 0.22 * u)
            ln = P["lmax"] * prof * rnd.uniform(0.93, 1.05)
            th = math.radians(lerp(P["th0"], P["th1"], u) + rnd.uniform(-4, 4) * (2 if kind == "frond_dry" else 1))
            w = P["wmax"] * (0.62 + 0.38 * prof) * rnd.uniform(0.9, 1.08)
            D = (side * math.sin(th), math.cos(th))
            rw = lerp(0.035, 0.008, u)
            b = (side * rw, y)
            br = rnd.uniform(0.8, 1.12)
            tint = olive if (kind == "frond_dry" and rnd.random() < 0.35) else (cb, cm, ct)
            hue = rnd.uniform(-P["jit"], P["jit"])

            def col(s, sd, tint=tint, br=br, hue=hue):
                c = cmix(tint[0], tint[1], s * 2.0) if s < 0.5 else cmix(tint[1], tint[2], (s - 0.5) * 2.0)
                c = (c[0] * (1 + hue), c[1], c[2] * (1 - hue))
                if sd == 0:
                    c = cmul(cscale(c, 1.12), (1.05, 1.03, 0.85))
                elif sd == side:  # outer half catches more light
                    c = cscale(c, 1.04)
                else:
                    c = cscale(c, 0.84)
                return cscale(c, br)

            flat_leaf(g, (b[0], b[1], 0.0), D, ln, w, col, st=6, fold=0.3, bend=-side * 0.06 * rnd.uniform(0.5, 1.5),
                      z0=0.02 + 0.08 * u, zdrop=0.06 * ln, shape=shape_lance)
    # frond tip: a last pair of leaflets fused into a point (a broad fan on the oil-palm frond)
    if P.get("blunt"):
        for side, ang, ln in ((-1, 16, 0.3), (1, 16, 0.3), (-1, 6, 0.33), (1, 5, 0.34)):
            th = math.radians(ang)
            flat_leaf(g, (side * 0.008, y1 - 0.01, 0.1), (side * math.sin(th), math.cos(th)), ln, 0.13,
                      lambda s, sd: cscale(cmix(cm, ct, s), 1.0 if sd == 0 else 0.92), st=6, fold=0.3,
                      bend=-side * 0.05, zdrop=0.02, shape=shape_lance)
    else:
        for side in (-1, 1):
            flat_leaf(g, (0.0, y1 - 0.02, 0.06), (side * 0.25, 1.0), 0.09, 0.035, lambda s, sd: cm, st=2, fold=0.2)
    o = g.obj("_frond_tex", [m])
    return o


def _render_frond(kind, w, h):
    _frond_model(kind)
    arr = _tex_render(w, h, (0.0, 1.0, 0.0), 2.0, samples=24, world=0.62, sun=((-0.3, 0.8, 1.0), 2.4))
    _tex_save(arr, kind)


@texture("frond", (256, 512))
def _t_frond(w, h):
    _render_frond("frond", w, h)


@texture("frond_dry", (256, 512))
def _t_frond_dry(w, h):
    _render_frond("frond_dry", w, h)


@texture("frond_coco", (256, 512))
def _t_frond_coco(w, h):
    _render_frond("frond_coco", w, h)


# ---------------------------------------------------------------- fern (pakis)
@texture("fern", (256, 512))
def _t_fern(w, h):
    """Pakis frond: few, broad, shallowly lobed pinnae so the comb outline survives mipmapping at game
    distance (a fern card is only ~60 px long on screen); dark rachis base (plant centre stays dark)."""
    rnd = random.Random(5)
    m = _tex_mat(rough=0.7, spec=0.2)
    g = Geo()
    ytip = 1.97
    y0 = 0.26
    n = 24
    pts = [(0.03 * math.sin(i / n * 2.5), ytip * i / n) for i in range(n + 1)]
    strip_xy(g, pts, [lerp(0.045, 0.01, i / n) for i in range(n + 1)],
             lambda t: cmix(lin("#34501f"), lin("#6f9038"), min(1.0, t * 1.6)), z=0.06)
    cb, cm, ct = lin("#2c5220"), lin("#4d8232"), lin("#83ac4a")
    N = 13
    for side in (-1, 1):
        for k in range(N):
            u = clamp01((k + 0.5 + 0.3 * side) / N)
            y = y0 + (ytip - 0.08 - y0) * u
            x = 0.03 * math.sin(y / ytip * 2.5)
            prof = math.sin(math.pi * (0.16 + 0.84 * u)) ** 0.5 * (1.0 - 0.3 * u)
            ln = 0.47 * prof * rnd.uniform(0.93, 1.05)
            th = math.radians(lerp(74, 50, u) + rnd.uniform(-3, 3))
            br = rnd.uniform(0.86, 1.08) * lerp(0.82, 1.0, min(1.0, u * 2.5))

            def col(s, sd, br=br):
                c = cmix(cb, cm, s * 1.6) if s < 0.6 else cmix(cm, ct, (s - 0.6) * 2.5)
                return cscale(c, br * (1.1 if sd == 0 else (0.9 if sd == -side else 1.0)))

            flat_leaf(g, (x + side * 0.012, y, 0.02 + 0.02 * u), (side * math.sin(th), math.cos(th)), ln,
                      0.155 * (0.72 + 0.28 * prof), col, st=18, fold=0.2, bend=-side * 0.1,
                      shape=lambda s: math.sin(math.pi * (0.12 + 0.88 * s ** 0.9)) ** 0.55, lobes=4,
                      lobe_depth=0.26, zdrop=0.03)
    # a small lobed tip
    flat_leaf(g, (0.03 * math.sin(2.4), ytip - 0.12, 0.08), (0.02, 1.0), 0.14, 0.07,
              lambda s, sd: cscale(cm, 1.05), st=6, fold=0.2, shape=shape_lance)
    g.obj("_fern_tex", [m])
    arr = _tex_render(w, h, (0.0, 1.0, 0.0), 2.0, samples=24, world=0.78, sun=((-0.2, 0.45, 1.0), 1.5))
    _tex_save(arr, "fern")


# ---------------------------------------------------------------- leaves atlas (2x2)
def _leaf_col(base, mid, tip, br=1.0, midrib=1.12):
    def col(s, sd):
        c = cmix(base, mid, s * 1.8) if s < 0.55 else cmix(mid, tip, (s - 0.55) / 0.45)
        return cscale(c, br * (midrib if sd == 0 else (0.93 if sd < 0 else 1.0)))
    return col


def _leaves_cluster():
    """Q0: round clump of small glossy leaves (canopy / bush), opaque dense core."""
    rnd = random.Random(7)
    g = Geo()
    # dense dark core disc so the centre of the tile is fully opaque
    geo_blob(g, 0, (0, 0, -0.1), 0.34, (1, 1, 0.25), seed=3, subdiv=3, amp=0.12, freq=3.0,
             col_fn=lambda p, n: lin("#4a7434"))
    greens = [("#3f6a2f", "#5c8a3a", "#7aa447"), ("#4a7632", "#6a9840", "#8db34f"),
              ("#365d2b", "#557f36", "#6f9a42"), ("#52803a", "#79a547", "#9dbd58")]
    for k in range(130):
        r = 0.43 * math.sqrt(rnd.random()) ** 0.8
        a = rnd.uniform(0, 2 * math.pi)
        p = Vector((r * math.cos(a), r * math.sin(a), 0.0))
        dome = 0.2 * (1.0 - (r / 0.45) ** 2)
        out = Vector((math.cos(a), math.sin(a), 0.0))
        d = (out * 0.8 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.5).normalized()
        ln = rnd.uniform(0.13, 0.19)
        gset = greens[rnd.randrange(len(greens))]
        lit = 0.85 + 0.3 * (dome / 0.2)
        flat_leaf(g, p - d * ln * 0.3, d, ln, ln * rnd.uniform(0.45, 0.55),
                  _leaf_col(lin(gset[0]), lin(gset[1]), lin(gset[2]), br=lit * rnd.uniform(0.92, 1.05)),
                  st=4, fold=0.3, z0=dome + rnd.uniform(0, 0.02), zdrop=0.02, shape=shape_oval)
    return g


def _leaves_sprig():
    """Q1: twig with alternate glossy oval leaves, base at the bottom centre."""
    rnd = random.Random(8)
    g = Geo()
    stem = [(0.0 + 0.04 * math.sin(t * 2.2), -0.48 + 0.9 * t) for t in [i / 10 for i in range(11)]]
    strip_xy(g, stem, [lerp(0.03, 0.01, i / 10) for i in range(11)], lambda t: lin("#6b6a3a"), z=0.03)
    n = 9
    for k in range(n):
        t = 0.12 + 0.8 * k / (n - 1)
        side = -1 if k % 2 else 1
        x, y = 0.04 * math.sin(t * 2.2), -0.48 + 0.9 * t
        th = math.radians(lerp(58, 25, t) + rnd.uniform(-6, 6))
        ln = lerp(0.36, 0.22, t) * rnd.uniform(0.92, 1.05)
        br = rnd.uniform(0.92, 1.06)
        flat_leaf(g, (x, y, 0.05 - 0.02 * t), (side * math.sin(th), math.cos(th)), ln, ln * 0.5,
                  _leaf_col(lin("#3f6b2f"), lin("#679640"), lin("#8ab04e"), br=br), st=5, fold=0.28,
                  bend=-side * 0.1, zdrop=0.04, shape=shape_acuminate)
    flat_leaf(g, (0.04 * math.sin(2.2), 0.4, 0.06), (0.05, 1.0), 0.1, 0.06,
              _leaf_col(lin("#5c8c3a"), lin("#7fa84a"), lin("#a2c25c")), st=3, fold=0.25, shape=shape_acuminate)
    return g


def _leaves_broad():
    """Q2: single broad elliptic leaf with veins, base at the bottom."""
    g = Geo()
    L, W = 0.9, 0.46
    b0 = -0.46
    strip_xy(g, [(0, b0), (0, b0 + 0.06)], [0.035, 0.03], lambda t: lin("#6f8c3b"), z=0.05)
    cb, cm, ct = lin("#3a6628"), lin("#5a8c38"), lin("#7ea648")

    def col(s, sd):
        c = cmix(cb, cm, s * 2.0) if s < 0.5 else cmix(cm, ct, (s - 0.5) * 2.0)
        return cscale(c, 1.08 if sd == 0 else (0.9 if sd < 0 else 1.0))

    rows = flat_leaf(g, (0, b0 + 0.05, 0.0), (0, 1), L - 0.06, W, col, st=10, fold=0.22, shape=shape_acuminate,
                     zdrop=0.03)
    # veins: midrib + 6 lateral pairs, a bit lighter
    vc = lin("#a9c865")
    strip_xy(g, [(0, b0 + 0.05 + (L - 0.08) * t) for t in [i / 8 for i in range(9)]],
             [lerp(0.022, 0.004, i / 8) for i in range(9)], lambda t: vc,
             z=[0.012 - 0.03 * (i / 8) ** 2 for i in range(9)])
    for k in range(6):
        t = 0.14 + 0.13 * k
        y = b0 + 0.05 + (L - 0.06) * t
        hw = 0.5 * W * shape_acuminate(t + 0.08) * 0.85
        for side in (-1, 1):
            pts = [(0, y), (side * hw * 0.5, y + hw * 0.35), (side * hw, y + hw * 0.85)]
            strip_xy(g, pts, [0.01, 0.007, 0.003], lambda t, vc=vc: cscale(vc, 0.95), z=0.0 - 0.02 * t - 0.01)
    return g


def _leaves_keladi():
    """Q3: peltate heart-shaped taro leaf, tip up, basal lobes down, radiating light veins."""
    g = Geo()
    A = Vector((0.0, -0.1, 0.0))  # petiole attachment
    ctrl = [(0.0, 0.47), (0.2, 0.36), (0.37, 0.12), (0.36, -0.14), (0.27, -0.36), (0.2, -0.46),
            (0.1, -0.36), (0.0, -0.22)]

    def catmull(pts, n):
        out = []
        P = [pts[0]] + pts + [pts[-1]]
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = (Vector(P[i - 1]), Vector(P[i]), Vector(P[i + 1]), Vector(P[i + 2]))
            for k in range(n):
                t = k / n
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                                  (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        out.append(Vector(pts[-1]))
        return out

    right = catmull([Vector(p) for p in ctrl], 5)
    left = [Vector((-p.x, p.y)) for p in reversed(right[1:-1])]
    outline = right + left  # tip -> right side -> notch -> left side (closed)
    cb, cm, ce = lin("#3c6f2b"), lin("#578f39"), lin("#4a7d31")
    ci = g.vert(A + UP * 0.04, cb)
    inner, outer = [], []
    for p in outline:
        d = (Vector((p.x, p.y, 0)) - A)
        q_in = A + d * 0.5 + UP * 0.03
        q_out = Vector((p.x, p.y, -0.02 - 0.05 * max(0.0, (p.y - 0.1))))
        inner.append(g.vert(q_in, cm))
        outer.append(g.vert(q_out, ce))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        g.face((ci, inner[i], inner[j]), 0, ref=UP)
        g.face((inner[i], outer[i], outer[j], inner[j]), 0, ref=UP)
    vc = lin("#9fc063")
    # main veins from the attachment: to tip, to each basal lobe, and laterals
    targets = [(0.0, 0.45), (0.25, -0.43), (-0.25, -0.43), (0.33, 0.2), (-0.33, 0.2), (0.35, -0.05),
               (-0.35, -0.05), (0.2, 0.36), (-0.2, 0.36)]
    for tx, ty in targets:
        pts = [(A.x + (tx - A.x) * t, A.y + (ty - A.y) * t) for t in [i / 6 for i in range(7)]]
        strip_xy(g, pts, [lerp(0.022, 0.004, i / 6) for i in range(7)], lambda t: vc, z=0.045)
    return g


@texture("leaves", (512, 512))
def _t_leaves(w, h):
    tiles = []
    for fn, rough in ((_leaves_cluster, 0.55), (_leaves_sprig, 0.45), (_leaves_broad, 0.45), (_leaves_keladi, 0.4)):
        reset_scene()
        fn().obj("_leaves", [_tex_mat(rough=rough, spec=0.35)])
        tiles.append(_tex_render(w // 2, h // 2, (0.0, 0.0, 0.0), 1.0, samples=24, world=0.66,
                                 sun=((-0.3, 0.7, 1.0), 2.2)))
    top = np.concatenate([tiles[0], tiles[1]], axis=1)
    bot = np.concatenate([tiles[2], tiles[3]], axis=1)
    _tex_save(np.concatenate([top, bot], axis=0), "leaves")


# ---------------------------------------------------------------- grass (side view)
def _blade_xz(g, base, tip_dir, height, width, cols, segs=5, curve=0.35, yoff=0.0, twist=0.0):
    """Grass blade in the XZ plane (facing -Y), bending outward. cols=(base, mid, tip)."""
    b = Vector(base)
    d = Vector((tip_dir, 0.0, 1.0)).normalized()
    rows = []
    for i in range(segs + 1):
        t = i / segs
        p = b + Vector((d.x * height * t + curve * tip_dir * height * t * t, yoff, d.z * height * t * (1 - 0.25 * curve * t)))
        wv = width * 0.5 * (1.0 - t ** 1.4) + 0.001
        Sd = Vector((math.cos(twist * t), math.sin(twist * t), 0.0))
        c = cmix(cols[0], cols[1], t * 2) if t < 0.5 else cmix(cols[1], cols[2], (t - 0.5) * 2)
        rows.append((g.vert(p - Sd * wv, cscale(c, 0.92)), g.vert(p + Sd * wv, c)))
    for i in range(segs):
        a, c = rows[i], rows[i + 1]
        g.face((a[0], a[1], c[1], c[0]), 0, ref=Vector((0, -1, 0)))


def _grass_clump(seed, n, hmin, hmax, dry, heads, spread=0.55):
    rnd = random.Random(seed)
    g = Geo()
    greens = [("#355d27", "#5d8c38", "#98b955"), ("#3c6a2c", "#6d9a40", "#aac65c"),
              ("#2f5324", "#557f33", "#86ab4b"), ("#446f2e", "#7aa645", "#b7cc66")]
    drys = [("#7d7443", "#b7a96e", "#dbcb94"), ("#6e6a3c", "#a89c62", "#d2c38a")]
    for k in range(n):
        x = rnd.gauss(0, 0.07)
        lean = rnd.uniform(-spread, spread) + x * 1.5
        h = rnd.uniform(hmin, hmax) * (1.0 - 0.35 * abs(lean))
        isdry = rnd.random() < dry
        cols = [lin(c) for c in (drys if isdry else greens)[rnd.randrange(2 if isdry else 4)]]
        _blade_xz(g, (x, rnd.uniform(-0.15, 0.15), 0.0), lean, h, rnd.uniform(0.028, 0.05), cols,
                  curve=rnd.uniform(0.2, 0.6), yoff=0.0, twist=rnd.uniform(-1.0, 1.0))
    for k in range(heads):  # seed heads on thin stems
        x = rnd.gauss(0, 0.05)
        lean = rnd.uniform(-0.35, 0.35)
        h = rnd.uniform(hmax * 0.85, hmax * 1.05)
        cols = [lin("#8a8a4a"), lin("#a9a462"), lin("#c9bb78")]
        _blade_xz(g, (x, 0.1, 0.0), lean, h, 0.012, cols, segs=4, curve=0.2)
        top = Vector((x + lean * h * 1.15, 0.09, h * 0.97))
        for j in range(5):
            t = j / 5
            flat = Vector((lean * 0.12 * t, 0, -0.03 * j))
            p = top + flat
            _blade_xz(g, (p.x, p.y - 0.01, p.z), lean + rnd.uniform(-0.6, 0.6), 0.06, 0.03,
                      [lin("#b8a867"), lin("#d4c488"), lin("#e3d7a4")], segs=2, curve=0.1)
    return g


@texture("grass", (512, 256))
def _t_grass(w, h):
    tiles = []
    for args in ((11, 70, 0.45, 0.92, 0.06, 0, 0.55), (12, 46, 0.6, 0.95, 0.28, 5, 0.45)):
        reset_scene()
        m = _tex_mat(rough=0.8, spec=0.15)
        _grass_clump(*args).obj("_grass", [m])
        tiles.append(_tex_render(w // 2, h, (0.0, 0.0, 0.5), 1.0, elev=0.0, samples=24, world=0.8,
                                 sun=((-0.3, -0.6, 1.0), 1.4)))
    _tex_save(np.concatenate(tiles, axis=1), "grass")


# ---------------------------------------------------------------- flowers (side-ish view)
def _flower_head(g, center, normal, radius, petals, pcol, ccol, rnd, cup=0.15):
    N = Vector(normal).normalized()
    a = N.cross(Vector((0.0, 0.0, 1.0)) if abs(N.z) < 0.95 else Vector((1.0, 0.0, 0.0))).normalized()
    b = N.cross(a)
    C = Vector(center)
    ph = rnd.uniform(0, 6.28)
    for i in range(petals):
        ang = ph + 2 * math.pi * i / petals
        d = a * math.cos(ang) + b * math.sin(ang)
        s_ = d.cross(N)
        L = radius * rnd.uniform(0.9, 1.08)
        w = radius * (2.4 / petals) * 1.2
        p0 = C + d * radius * 0.18
        p1 = C + d * L * 0.6 + s_ * w * 0.5 + N * L * cup * 0.5
        p2 = C + d * L * 1.0 + N * L * cup
        p3 = C + d * L * 0.6 - s_ * w * 0.5 + N * L * cup * 0.5
        ids = [g.vert(p0, cscale(pcol, 0.85)), g.vert(p1, pcol), g.vert(p2, pcol), g.vert(p3, pcol)]
        g.face(ids, 0, ref=N)
    ring = [g.vert(C + (a * math.cos(t) + b * math.sin(t)) * radius * 0.28 + N * radius * 0.05, ccol)
            for t in [2 * math.pi * k / 6 for k in range(6)]]
    top = g.vert(C + N * radius * 0.16, cscale(ccol, 1.1))
    for k in range(6):
        g.face((ring[k], ring[(k + 1) % 6], top), 0, ref=N)


def _flower_clump(seed, pcol, ccol, petals, radius, leafcols, n=8):
    rnd = random.Random(seed)
    g = Geo()
    # leafy base rosette
    for k in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a), math.sin(a) * 0.6, rnd.uniform(0.3, 0.9))).normalized()
        base = Vector((rnd.gauss(0, 0.05), rnd.gauss(0, 0.05), 0.0))
        ln = rnd.uniform(0.16, 0.26)
        tip = base + d * ln
        s_ = d.cross(UP).normalized() if abs(d.z) < 0.99 else Vector((1, 0, 0))
        wv = ln * 0.22
        c0, c1 = lin(leafcols[0]), lin(leafcols[1])
        ids = [g.vert(base, cscale(c0, 0.8)), g.vert(base + d * ln * 0.45 + s_ * wv, c1), g.vert(tip, c1),
               g.vert(base + d * ln * 0.45 - s_ * wv, cscale(c1, 0.9))]
        g.face(ids, 0, ref=Vector((0, -1, 0.3)))
    for k in range(n):
        x = rnd.uniform(-0.3, 0.3)
        y = rnd.uniform(-0.15, 0.15)
        hgt = rnd.uniform(0.4, 0.78) * (1.0 - 0.5 * abs(x))
        top = Vector((x + rnd.uniform(-0.05, 0.05), y, hgt))
        pts = [Vector((x * 0.6, y, 0.0)), (Vector((x * 0.6, y, 0.0)) + top) * 0.5 + Vector((rnd.uniform(-.03, .03), 0, 0)), top]
        rows = []
        for p in pts:
            rows.append((g.vert(p + Vector((-0.006, 0, 0)), lin(leafcols[0])), g.vert(p + Vector((0.006, 0, 0)), lin(leafcols[1]))))
        for i in range(2):
            g.face((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]), 0, ref=Vector((0, -1, 0)))
        # a stem leaf
        mid = pts[1]
        side = 1 if rnd.random() < 0.5 else -1
        d = Vector((side * 0.8, 0.0, 0.6)).normalized()
        ids = [g.vert(mid, lin(leafcols[0])), g.vert(mid + d * 0.05 + Vector((0, 0, 0.02)), lin(leafcols[1])),
               g.vert(mid + d * 0.11, lin(leafcols[1])), g.vert(mid + d * 0.05 - Vector((0, 0, 0.02)), lin(leafcols[0]))]
        g.face(ids, 0, ref=Vector((0, -1, 0)))
        nrm = Vector((rnd.uniform(-0.3, 0.3), -0.75, 0.75))
        _flower_head(g, top, nrm, radius * rnd.uniform(0.85, 1.15), petals, pcol, ccol, rnd)
    return g


@texture("flowers", (512, 256))
def _t_flowers(w, h):
    tiles = []
    specs = ((21, lin("#f7f3ea"), lin("#f0b73c"), 9, 0.075, ("#3f6a2e", "#6d9a42")),
             (22, lin("#f6c43d"), lin("#d68a22"), 8, 0.082, ("#3a672c", "#5f9039")))
    for spec in specs:
        reset_scene()
        m = _tex_mat(rough=0.7, spec=0.15)
        _flower_clump(*spec).obj("_flowers", [m])
        tiles.append(_tex_render(w // 2, h, (0.0, 0.0, 0.42), 0.92, elev=28.0, samples=24, world=0.8,
                                 sun=((-0.3, -0.6, 1.0), 1.4)))
    _tex_save(np.concatenate(tiles, axis=1), "flowers")


# ---------------------------------------------------------------- banana leaf (top-down, base at bottom)
@texture("banana", (256, 512))
def _t_banana(w, h):
    """Banana (pisang) leaf: oblong pleated blade, pale midrib, lateral veins at ~70 deg, wind-torn
    slits along the veins and a few dry brown edges."""
    rnd = random.Random(19)
    m = _tex_mat(rough=0.45, spec=0.35)
    g = Geo()
    yb, yt = 0.14, 1.8
    n = 24
    strip_xy(g, [(0.0, yb - 0.1 + (yt - yb + 0.06) * i / n) for i in range(n + 1)],
             [lerp(0.05, 0.012, i / n) for i in range(n + 1)], lambda t: cmix(lin("#9fb45a"), lin("#c4cf7c"), t),
             z=0.05)
    cb, cm, ce = lin("#3a7428"), lin("#5b9a3c"), lin("#86b650")
    dry = lin("#a08445")
    cot = 1.0 / math.tan(math.radians(70))

    def half_w(y):
        u = clamp01((y - yb) / (yt - yb))
        tip = math.sqrt(max(0.0, 1.0 - ((u - 0.72) / 0.28) ** 2)) if u > 0.72 else 1.0
        return 0.45 * min(1.0, u / 0.16) ** 0.55 * tip + 0.004

    for side in (-1, 1):
        y = yb
        k = 0
        while y < yt - 0.02:
            dy = rnd.uniform(0.045, 0.075)
            y1 = min(yt, y + dy)
            tear0 = k > 0 and rnd.random() < 0.34      # slit at this strip's lower boundary
            tin = rnd.uniform(0.08, 0.55)               # slit reaches this far towards the midrib
            gap = rnd.uniform(0.008, 0.02)
            br = rnd.uniform(0.94, 1.05) * (1.02 if k % 2 else 0.98)
            dry_edge = rnd.random() < 0.12
            pleat = 0.006 if k % 2 else -0.006
            rows = []
            for j in range(5):
                t = j / 4
                pts = []
                for yy, lower in ((y, True), (y1, False)):
                    wv = half_w(yy)
                    q = Vector((side * (0.02 + (wv - 0.02) * t), yy + wv * t * cot * 0.8, 0.0))
                    if lower and tear0 and t >= tin:
                        q.y += gap * smoothstep(tin, min(1.0, tin + 0.15), t)
                    q.z = 0.03 - 0.06 * t * t + (pleat if not lower else -pleat) * t
                    pts.append(q)
                c = cmix(cb, cm, t * 1.6) if t < 0.6 else cmix(cm, ce, (t - 0.6) * 2.5)
                if dry_edge and t > 0.7:
                    c = cmix(c, dry, (t - 0.7) / 0.3)
                c = cscale(c, br)
                rows.append((g.vert(pts[0], c), g.vert(pts[1], c)))
            for j in range(4):
                a, b = rows[j], rows[j + 1]
                g.face((a[0], a[1], b[1], b[0]), 0, ref=UP)
            y = y1
            k += 1
    g.obj("_banana_tex", [m])
    arr = _tex_render(w, h, (0.0, 1.0, 0.0), 2.0, samples=24, world=0.7, sun=((-0.3, 0.6, 1.0), 2.0))
    _tex_save(arr, "banana")


# ---------------------------------------------------------------- piringan (weeded mulch circle, top-down)
@texture("piringan", (512, 512))
def _t_piringan(w, h):
    rnd = random.Random(31)
    # base disc: procedural red-brown mulch with a ragged alpha edge
    bpy.ops.mesh.primitive_plane_add(size=2.6, location=(0, 0, 0))
    plane = bpy.context.view_layer.objects.active
    m = bpy.data.materials.new("_Mulch")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.95
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 9.0
    n1.inputs["Detail"].default_value = 8.0
    n1.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.3
    cr.elements[0].color = hex_rgba("#4e3222")
    cr.elements[1].position = 0.7
    cr.elements[1].color = hex_rgba("#8c6244")
    e = cr.elements.new(0.5)
    e.color = hex_rgba("#6c4631")
    nt.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    # fine speckle (fibres / chips) on top
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    sp = nt.nodes.new("ShaderNodeMapRange")
    sp.inputs["From Min"].default_value = 0.0
    sp.inputs["From Max"].default_value = 0.35
    sp.inputs["To Min"].default_value = 0.75
    sp.inputs["To Max"].default_value = 1.08
    nt.links.new(vor.outputs["Distance"], sp.inputs["Value"])
    mix.inputs[0].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(sp.outputs["Result"], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    # alpha: radius 1.0 +- noise, ragged
    sep = nt.nodes.new("ShaderNodeVectorMath")
    sep.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 3.2
    n2.inputs["Detail"].default_value = 10.0
    n2.inputs["Roughness"].default_value = 0.75
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.42
    add.inputs[2].default_value = 0.8
    nt.links.new(n2.outputs["Fac"], add.inputs[0])
    lt = nt.nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(sep.outputs["Value"], lt.inputs[0])
    nt.links.new(add.outputs[0], lt.inputs[1])
    nt.links.new(lt.outputs[0], b.inputs["Alpha"])
    plane.data.materials.append(m)
    # debris: dry frond leaflets, rachis pieces, chips, a few old fruitlets, weeds at the rim
    g = Geo()
    dry = [("#7a5a32", "#a8854a", "#c8a86a"), ("#6d6034", "#9c8e52", "#bfae70"), ("#5e4526", "#8a6a3c", "#a98a58")]
    for k in range(46):
        r = 0.95 * math.sqrt(rnd.random())
        a = rnd.uniform(0, 2 * math.pi)
        d = (rnd.uniform(-1, 1), rnd.uniform(-1, 1))
        c = [lin(x) for x in dry[rnd.randrange(3)]]
        br = rnd.uniform(0.85, 1.1)
        flat_leaf(g, (r * math.cos(a), r * math.sin(a), 0.01 + 0.01 * k / 46), d, rnd.uniform(0.18, 0.42),
                  rnd.uniform(0.03, 0.05), _leaf_col(c[0], c[1], c[2], br=br), st=3, fold=0.2,
                  bend=rnd.uniform(-0.15, 0.15), shape=shape_lance)
    for k in range(7):
        r = 0.8 * math.sqrt(rnd.random())
        a = rnd.uniform(0, 2 * math.pi)
        p0 = (r * math.cos(a), r * math.sin(a))
        ang = rnd.uniform(0, 6.28)
        ln = rnd.uniform(0.25, 0.5)
        pts = [(p0[0] + math.cos(ang) * ln * t, p0[1] + math.sin(ang) * ln * t) for t in (0, 0.5, 1)]
        strip_xy(g, pts, [0.05, 0.04, 0.03], lambda t: lin("#9c7c4c"), z=0.035)
    for k in range(10):  # a few old dark fruitlets (brondolan) near the trunk
        r = rnd.uniform(0.22, 0.6)
        a = rnd.uniform(0, 2 * math.pi)
        c = lin("#7a2a18") if k % 3 else lin("#3a1f18")
        flat_leaf(g, (r * math.cos(a), r * math.sin(a), 0.05), (rnd.uniform(-1, 1), rnd.uniform(-1, 1)), 0.05, 0.035,
                  lambda s, sd, c=c: cscale(c, 1.2 if sd == 0 else 0.9), st=2, fold=0.6, shape=shape_oval)
    for k in range(26):  # small weeds creeping in at the rim
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.92, 1.18)
        base = Vector((r * math.cos(a), r * math.sin(a), 0.03))
        for j in range(3):
            d = (math.cos(a + rnd.uniform(-1.5, 1.5)), math.sin(a + rnd.uniform(-1.5, 1.5)))
            ln = rnd.uniform(0.07, 0.13)
            flat_leaf(g, base, d, ln, ln * 0.5, _leaf_col(lin("#3f6c2c"), lin("#5f9038"), lin("#86ad4b")), st=3,
                      fold=0.3, shape=shape_oval)
    g.obj("_debris", [_tex_mat(rough=0.9, spec=0.1)])
    arr = _tex_render(w, h, (0.0, 0.0, 0.0), 2.4, samples=24, world=0.85, sun=((-0.3, 0.4, 1.0), 1.2))
    _tex_save(arr, "piringan")


def ensure_texture(name, force=False):
    if force or not os.path.exists(tex_path(name)):
        fn, (w, h) = TEXTURES[name]
        reset_scene()
        fn(w, h)
        reset_scene()


_PROFILES = {}


def alpha_profile(tex, region=(0.0, 0.0, 1.0, 1.0), thr=0.35):
    """Half-width (fraction of the region half-width) covered by opaque texels, per row, as t->frac.
    Used to trim card strips to the actual leaf outline."""
    key = (tex, region)
    if key not in _PROFILES:
        from PIL import Image
        from scipy import ndimage
        a = np.asarray(Image.open(tex_path(tex)).convert("RGBA"))[..., 3].astype(np.float32) / 255.0
        H, W = a.shape
        u0, v0, u1, v1 = region
        x0, x1 = int(u0 * W), int(u1 * W)
        y0, y1 = int((1 - v1) * H), int((1 - v0) * H)
        sub = a[y0:y1, x0:x1][::-1]  # row 0 = bottom (v0)
        hh, ww = sub.shape
        xs = np.abs(np.arange(ww) + 0.5 - ww / 2.0) / (ww / 2.0)
        prof = np.array([xs[row > thr].max() if (row > thr).any() else 0.0 for row in sub])
        prof = ndimage.maximum_filter1d(prof, size=max(3, hh // 40))
        _PROFILES[key] = prof

    prof = _PROFILES[key]

    def f(t):
        x = clamp01(t) * (len(prof) - 1)
        i = int(x)
        j = min(i + 1, len(prof) - 1)
        return float(lerp(prof[i], prof[j], x - i))
    return f



def alpha_bbox(tex, region=(0.0, 0.0, 1.0, 1.0), thr=0.3):
    """Tight uv rect (u0, v0, u1, v1) around the opaque texels of `region`, plus its pixel aspect w/h."""
    from PIL import Image
    a = np.asarray(Image.open(tex_path(tex)).convert("RGBA"))[..., 3].astype(np.float32) / 255.0
    H, W = a.shape
    u0, v0, u1, v1 = region
    x0, x1 = int(u0 * W), int(u1 * W)
    y0, y1 = int((1 - v1) * H), int((1 - v0) * H)
    sub = a[y0:y1, x0:x1] > thr
    cols = np.where(sub.any(axis=0))[0]
    rows = np.where(sub.any(axis=1))[0]
    cx0, cx1 = x0 + cols[0], x0 + cols[-1] + 1
    ry0, ry1 = y0 + rows[0], y0 + rows[-1] + 1
    rect = (cx0 / W, 1 - ry1 / H, cx1 / W, 1 - ry0 / H)
    return rect, (cx1 - cx0) / float(ry1 - ry0)


# ============================================================ card geometry
ATLAS = {"cluster": (0.0, 0.5, 0.5, 1.0), "sprig": (0.5, 0.5, 1.0, 1.0),
         "broad": (0.0, 0.0, 0.5, 0.5), "keladi": (0.5, 0.0, 1.0, 0.5)}
HALVES = {"left": (0.0, 0.0, 0.5, 1.0), "right": (0.5, 0.0, 1.0, 1.0)}


def arc_points(base, phi, elev, droop, L, segs, yaw_drift=0.0, pw=1.4):
    """Centre line of an arching leaf: starts at `elev` degrees, bends down by `droop` degrees
    (droop * t**pw: a larger pw keeps the leaf rising longer and bends it down near the tip)."""
    pts = [Vector(base)]
    ds = L / segs
    for i in range(segs):
        t = (i + 0.5) / segs
        a = math.radians(elev - droop * t ** pw)
        ph = phi + yaw_drift * t
        pts.append(pts[-1] + Vector((math.cos(ph) * math.cos(a), math.sin(ph) * math.cos(a), math.sin(a))) * ds)
    return pts


def card_path(g, mi, pts, W, uv=(0.0, 0.0, 1.0, 1.0), prof=None, fold=(0.2, 0.3), across=5, twist=0.0,
              col_fn=None, side_hint=None, margin=1.06, smooth=True, vmap=None):
    """Textured card strip along `pts` (texture v0 at pts[0]), Λ-folded: the edges hang below the
    midrib by hw*(fold0*|s| + fold1*s^2).  prof(t) trims the width to the texture's opaque extent.
    vmap(t) -> texture t (e.g. stretch the bare petiole over the first part of the card)."""
    n = len(pts) - 1
    offs = (-1.0, -0.5, 0.0, 0.5, 1.0) if across == 5 else (-1.0, 0.0, 1.0)
    u0, v0, u1, v1 = uv
    prevS = None
    rows = []
    for i, p in enumerate(pts):
        t = i / n
        tv = vmap(t) if vmap else t
        T = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        S = T.cross(UP)
        if S.length < 0.25:
            S = prevS if prevS is not None else (Vector(side_hint) if side_hint is not None else Vector((1, 0, 0)))
        S = (S - T * S.dot(T)).normalized()
        prevS = S.copy()
        N = S.cross(T).normalized()
        if twist:
            R = Matrix.Rotation(math.radians(twist) * t, 3, T)
            S, N = R @ S, R @ N
        rt = max(0.03, min(1.0, (prof(tv) if prof else 1.0) * margin))
        hw = 0.5 * W * rt
        row = []
        for s in offs:
            a = abs(s)
            q = p + S * s * hw - N * hw * (fold[0] * a + fold[1] * a * a)
            c = col_fn(t, s) if col_fn else (1.0, 1.0, 1.0)
            row.append((g.vert(q, c), (lerp(u0, u1, 0.5 + 0.5 * s * rt), lerp(v0, v1, tv)), N))
        rows.append(row)
    for i in range(n):
        for j in range(len(offs) - 1):
            a0, a1, b0, b1 = rows[i][j], rows[i][j + 1], rows[i + 1][j], rows[i + 1][j + 1]
            g.face((a0[0], a1[0], b1[0], b0[0]), mi, ref=a0[2] + b0[2], smooth=smooth,
                   uv=(a0[1], a1[1], b1[1], b0[1]))


def leaf_card(g, mi, base, direction, length, W, uv, droop=0.25, segs=3, **kw):
    """Card rooted at `base` pointing along `direction`, sagging by `droop`*length at the tip."""
    D = Vector(direction).normalized()
    pts = [Vector(base) + D * length * (i / segs) - UP * length * droop * (i / segs) ** 2 for i in range(segs + 1)]
    side = D.cross(UP)
    kw.setdefault("side_hint", side.normalized() if side.length > 1e-3 else Vector((1, 0, 0)))
    card_path(g, mi, pts, W, uv=uv, **kw)


def cross_card(g, mi, center, yaw, w, h, uv, lean=(0.0, 0.0), segs=2, col_fn=None):
    """Vertical card (grass / flowers) standing on the ground; top leans by `lean` (m)."""
    d = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    nrm = Vector((-d.y, d.x, 0.0))
    if nrm.y > 0:
        nrm = -nrm
    C = Vector(center)
    u0, v0, u1, v1 = uv
    Lv = Vector((lean[0], lean[1], 0.0))
    rows = []
    for i in range(segs + 1):
        t = i / segs
        c = col_fn(t) if col_fn else (1.0, 1.0, 1.0)
        off = Lv * t * t + UP * h * t
        rows.append((g.vert(C + off - d * w * 0.5, c), g.vert(C + off + d * w * 0.5, c)))
    for i in range(segs):
        a, b = rows[i], rows[i + 1]
        va, vb = lerp(v0, v1, i / segs), lerp(v0, v1, (i + 1) / segs)
        g.face((a[0], a[1], b[1], b[0]), mi, uv=((u0, va), (u1, va), (u1, vb), (u0, vb)), ref=nrm)


def quad_card(g, mi, center, normal, size, uv, spin=0.0, col=(1.0, 1.0, 1.0), cup=0.12, col_rim=None, flat=False):
    """Square card facing `normal` (leaf clusters on canopies / bushes), centre pushed out a little."""
    N = Vector(normal).normalized()
    a = N.cross(UP) if abs(N.z) < 0.95 else Vector((1.0, 0.0, 0.0))
    a = (a - N * a.dot(N)).normalized()
    b = N.cross(a)
    R = Matrix.Rotation(spin, 3, N)
    a, b = R @ a, R @ b
    C = Vector(center)
    u0, v0, u1, v1 = uv
    h = size * 0.5
    cr = col_rim or col
    ids = [g.vert(C + (-a - b) * h - N * cup * size, cr), g.vert(C + (a - b) * h - N * cup * size, cr),
           g.vert(C + (a + b) * h - N * cup * size, cr), g.vert(C + (-a + b) * h - N * cup * size, cr)]
    uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if flat:
        g.face(ids, mi, ref=N, uv=uvs)
        return
    ci = g.vert(C, col)
    cuv = ((u0 + u1) * 0.5, (v0 + v1) * 0.5)
    for k in range(4):
        g.face((ids[k], ids[(k + 1) % 4], ci), mi, ref=N, uv=(uvs[k], uvs[(k + 1) % 4], cuv))


def plant_ao(t, s=0.0, lo=0.52, reach=0.45, edge=0.08):
    """Card darkening: dark where the card starts (plant centre), full at `reach` along it."""
    return lo + (1.0 - lo) * smoothstep(0.0, reach, t) - edge * abs(s)


# ============================================================ oil palm (sawit)
def trunk_radius(z, H, r):
    flare = max(0.0, 1.0 - z / 0.5) ** 2 * 0.5 * r
    return r * (1.0 + 0.05 * math.sin(z * 2.1)) + flare


def palm_trunk(g, mi, H, r, rnd, boots, boot, rings, sides=12, z0=0.3, z1=None, moss=0.3, crown_dark=True):
    """Tapered trunk core + phyllotactic spiral of cut frond bases ("boots").  Colours: dark core,
    mid boot sides, light fresh cut faces, some moss; darker under the crown."""
    def shade(z):
        return lerp(1.0, 0.8, smoothstep(H - 1.1, H, z)) if crown_dark else 1.0

    rows = []
    for j in range(rings + 1):
        z = H * (j / rings) ** 1.1
        rr = trunk_radius(z, H, r) * (0.9 if j == rings else 1.0)
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides + j * 0.3
            jr = rr * rnd.uniform(0.95, 1.05)
            row.append(g.vert((jr * math.cos(a), jr * math.sin(a), z), grey((0.66 + 0.08 * rnd.random()) * shade(z))))
        rows.append(row)
    for j in range(rings):
        for i in range(sides):
            a, b = rows[j][i], rows[j][(i + 1) % sides]
            c, d = rows[j + 1][(i + 1) % sides], rows[j + 1][i]
            mid = (g.v[a] + g.v[c]) * 0.5
            g.face((a, b, c, d), mi, ref=Vector((mid.x, mid.y, 0)), smooth=True)
    top = g.vert((0, 0, H + r * 0.7), grey(0.55))
    for i in range(sides):
        g.face((rows[-1][i], rows[-1][(i + 1) % sides], top), mi, ref=UP, smooth=True)
    L0, Wb, Tb = boot
    z1 = z1 if z1 is not None else H - 0.12
    for k in range(boots):
        f = k / max(1, boots - 1)
        z = lerp(z0, z1, f ** 0.9)
        a = k * GOLDEN + rnd.uniform(-0.15, 0.15)
        O = Vector((math.cos(a), math.sin(a), 0.0))
        Tg = Vector((-math.sin(a), math.cos(a), 0.0))
        rr = trunk_radius(z, H, r)
        C = O * (rr - 0.06) + UP * z
        el = math.radians(rnd.uniform(36, 62))
        D = (O * math.cos(el) + UP * math.sin(el)).normalized()
        Rn = D.cross(Tg).normalized()
        ln = L0 * rnd.uniform(0.8, 1.15) * (0.75 + 0.25 * f)
        wb = Wb * rnd.uniform(0.85, 1.1)
        we = wb * 0.62
        tb, te = Tb, Tb * 0.75
        E = C + D * ln
        cut = ln * 0.32
        sh = shade(z)
        mossy = rnd.random() < moss
        tint = (0.74, 0.88, 0.56) if mossy else (1.0, 1.0, 1.0)
        c_base = cscale(cmul(tint, grey(0.72)), sh)
        c_top = cscale(cmul(tint, grey(0.92)), sh)
        c_keel = cscale(grey(0.8), sh)
        base = [C + Tg * wb * 0.5 + Rn * tb * 0.4, C - Tg * wb * 0.5 + Rn * tb * 0.4, C - Rn * tb]
        end = [E - D * cut + Tg * we * 0.5 + Rn * te * 0.4, E - D * cut - Tg * we * 0.5 + Rn * te * 0.4, E - Rn * te]
        bi = [g.vert(base[0], c_base), g.vert(base[1], c_base), g.vert(base[2], c_base)]
        ei = [g.vert(end[0], c_top), g.vert(end[1], c_top), g.vert(end[2], c_keel)]
        ctr = (C + E) * 0.5 - Rn * tb * 0.2
        for i in range(3):
            q = (bi[i], bi[(i + 1) % 3], ei[(i + 1) % 3], ei[i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            g.face(q, mi, ref=fc - ctr)
        cut_c = cscale(grey(1.0) if not mossy else (0.85, 0.9, 0.65), sh)
        ci = [g.vert(p, cut_c) for p in end]
        g.face(ci, mi, ref=D + Rn)


# Fruit colours come from a tiny ramp texture (fruit.png) picked by UV, so a whole bunch is ONE opaque material:
#   columns  0..7   near-black fruitlet tips (#3a1f18)
#   columns  8..47  ramp: deep maroon #5e1a12 -> #8a2a18 -> #c43b1c -> #e0572a -> #f08a3a -> light orange #f7a94f
#   columns 52..63  pale spines / stalk fibre (#d9c58c)
# Band edges sit on 4-texel boundaries so GPU block compression never mixes two bands.
FRUIT_TEX_W = 64
U_DARK = 4.0 / FRUIT_TEX_W
U_SPINE = 56.0 / FRUIT_TEX_W
FRUIT_V = 0.5


def fruit_u(k):
    """Ramp position: k=0 light orange (top of a bunch, lit fruitlet domes) .. k=1 deep maroon."""
    return (8.5 + (1.0 - clamp01(k)) * 38.5) / FRUIT_TEX_W


@texture("fruit", (FRUIT_TEX_W, 8))
def _t_fruit(w, h):
    def srgb(hx):
        hx = hx.lstrip("#")
        return np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0
    stops = [(0.0, "#5e1a12"), (0.18, "#8a2a18"), (0.4, "#c43b1c"), (0.62, "#e0572a"), (0.82, "#f08a3a"),
             (1.0, "#f7a94f")]
    arr = np.ones((h, w, 4), np.float32)
    for x in range(w):
        if x < 8:
            c = srgb("#2c1712") * (1 - x / 7.0) + srgb("#3a1f18") * (x / 7.0)
        elif x < 48:
            t = (x - 8) / 39.0
            for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
                if t <= t1:
                    c = srgb(c0) + (srgb(c1) - srgb(c0)) * ((t - t0) / (t1 - t0))
                    break
        elif x < 52:
            c = srgb("#f7a94f")
        else:
            c = srgb("#d9c58c")
        arr[:, x, :3] = c
    _tex_save(arr, "fruit")


def M_fruit():
    """Oil-palm fruit: one opaque material (fruit.png ramp by UV) x vertex-colour shading."""
    if "M_Fruit" in bpy.data.materials:
        return bpy.data.materials["M_Fruit"]
    m = bpy.data.materials.new("M_Fruit")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = tex_image("fruit")
    t.extension = "EXTEND"
    _multiply_col(nt, t.outputs["Color"], b)
    b.inputs["Roughness"].default_value = 0.38
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.5
    m.diffuse_color = hex_rgba("#e0572a")
    return m


def _frame(D):
    U = D.cross(Vector((0.31, 0.83, 0.47)))
    if U.length < 1e-4:
        U = D.cross(Vector((1.0, 0.0, 0.0)))
    U.normalize()
    return U, D.cross(U)


def fruit_bunch(name, center, axis, length, rnd, mat_, parent=None, n=44, width=0.4, dark=0.2, spines=10, sides=6,
                out=None, stalk_to=None, fsize=0.115, redness=0.0):
    """Oil-palm fresh fruit bunch (TBS): an egg-shaped core packed with `n` small rounded fruitlets.
    Each fruitlet is a low cone (6 tris) with custom dome normals, so it shades like a round bead;
    ~`dark` of them get a small near-black cap (mid ring + dark apex).  Colour by UV on the fruit.png ramp:
    orange towards the stalk end, maroon-red at the apex end and on the side facing `out` (away from the
    trunk), lighter on each dome top, deep maroon in the crevices; `spines` pale spikes between them.
    Apex (narrow end) along +axis; the stalk end is at -axis (stalk_to: optional point for a short stalk)."""
    g = Geo()
    ax = Vector(axis).normalized()
    R = ax.to_track_quat("Z", "Y").to_matrix()
    C = Vector(center)
    a_, b_ = length * 0.5, length * width
    ca, cb = a_ * 0.76, b_ * 0.76  # core semi-axes (fruitlets stick out of it)
    outv = Vector(out).normalized() if out is not None else None

    def egg(z):
        return 1.0 - 0.13 * z  # narrower towards the apex

    def core_pt(c):
        e = egg(c.z)
        return Vector((c.x * cb * e, c.y * cb * e, c.z * ca))

    def core_nrm(c):
        e = egg(c.z)
        return Vector((c.x / (cb * e), c.y / (cb * e), c.z / ca)).normalized()

    W = lambda q: C + R @ q  # noqa: E731  local -> world
    uv_of = lambda u: (u, FRUIT_V)  # noqa: E731
    # core: deep maroon, dark (seen only in the crevices)
    verts, faces = ico_data(2)
    base = len(g.v)
    u_core = fruit_u(1.0)
    for co in verts:
        nn = co.normalized()
        g.vert(W(core_pt(nn)), grey(0.62), nrm=R @ core_nrm(nn))
    for f in faces:
        ctr = sum((verts[i] for i in f), Vector()) / 3
        g.face([base + i for i in f], 0, ref=R @ ctr, smooth=True, uv=[uv_of(u_core)] * 3)
    rf0 = fsize * length
    for k in range(n):
        zc = lerp(0.96, -0.8, (k + 0.5) / n) + rnd.uniform(-0.025, 0.025)
        ang = k * GOLDEN + rnd.uniform(-0.15, 0.15)
        rc = math.sqrt(max(0.0, 1 - zc * zc))
        c = Vector((rc * math.cos(ang), rc * math.sin(ang), zc))
        p = core_pt(c)
        nrm = core_nrm(c)
        apex = Vector((0, 0, 1)) - nrm * nrm.z
        apex = apex.normalized() if apex.length > 1e-3 else Vector((1, 0, 0))
        D = (nrm * math.cos(math.radians(rnd.uniform(8, 22))) + apex * math.sin(math.radians(15))).normalized()
        rf = rf0 * rnd.uniform(0.88, 1.12) * (0.78 + 0.22 * rc)
        hf = rf * rnd.uniform(1.0, 1.25)
        U, V_ = _frame(D)
        # colour: orange at the stalk end -> maroon-red at the apex / outer side, random per fruitlet
        t_ax = (zc + 0.8) / 1.76
        kk = redness + 0.12 + 0.5 * t_ax + rnd.uniform(-0.2, 0.2)
        if outv is not None:
            kk += 0.22 * max(0.0, (R @ nrm).dot(outv))
        kk = clamp01(kk)
        u_base, u_top = fruit_u(kk + 0.14), fruit_u(kk - 0.16)
        ph = rnd.uniform(0, 6.28)
        dirs = [U * math.cos(ph + 2 * math.pi * s_ / sides) + V_ * math.sin(ph + 2 * math.pi * s_ / sides)
                for s_ in range(sides)]
        b0 = p - D * rf * 0.35
        ring = [g.vert(W(b0 + d * rf), grey(0.8), nrm=R @ (d + D * 0.2)) for d in dirs]
        Dw = R @ D
        P0 = W(p)
        if rnd.random() < dark:
            # red body -> small near-black cap
            mid = [g.vert(W(p + D * hf * 0.5 + d * rf * 0.62), grey(0.97), nrm=R @ (d * 0.8 + D * 0.7))
                   for d in dirs]
            tip = g.vert(W(p + D * hf * 0.78), grey(1.0), nrm=Dw)
            u_mid = fruit_u(max(kk, 0.55))
            for s_ in range(sides):
                s1 = (s_ + 1) % sides
                q = (ring[s_], ring[s1], mid[s1], mid[s_])
                g.face(q, 0, ref=sum((g.v[x] for x in q), Vector()) / 4 - P0, smooth=True,
                       uv=[uv_of(fruit_u(kk + 0.14))] * 2 + [uv_of(u_mid)] * 2)
                g.face((mid[s_], mid[s1], tip), 0, ref=Dw, smooth=True,
                       uv=[uv_of(U_DARK + 0.02)] * 2 + [uv_of(U_DARK)])
        else:
            tip = g.vert(W(p + D * hf), grey(1.0), nrm=Dw)
            for s_ in range(sides):
                s1 = (s_ + 1) % sides
                tri = (ring[s_], ring[s1], tip)
                g.face(tri, 0, ref=(g.v[ring[s_]] + g.v[ring[s1]]) * 0.5 - P0 + Dw * 0.3 * rf, smooth=True,
                       uv=[uv_of(u_base), uv_of(u_base), uv_of(u_top)])
    for k in range(spines):
        # pale fibrous spikes poking out between the fruitlets (mostly around the middle / stalk half)
        zc = rnd.uniform(-0.7, 0.55)
        ang = rnd.uniform(0, 6.28)
        rc = math.sqrt(max(0.0, 1 - zc * zc))
        c = Vector((rc * math.cos(ang), rc * math.sin(ang), zc))
        p = core_pt(c)
        nrm = core_nrm(c)
        D = (nrm + Vector((0, 0, -0.35))).normalized()
        U, V_ = _frame(D)
        ln = length * rnd.uniform(0.2, 0.26)
        bw = length * 0.022
        bs = [g.vert(W(p + (U * math.cos(q) + V_ * math.sin(q)) * bw), grey(0.85)) for q in (0.0, 2.09, 4.19)]
        tip = g.vert(W(p + D * ln), grey(1.0))
        for s_ in range(3):
            g.face((bs[s_], bs[(s_ + 1) % 3], tip), 0, ref=R @ ((g.v[bs[s_]] + g.v[bs[(s_ + 1) % 3]]) * 0.5 - C),
                   smooth=True, uv=[uv_of(U_SPINE)] * 3)
    if stalk_to is not None:
        top = W(Vector((0, 0, -ca * 0.9)))
        tube(g, [top, (top + Vector(stalk_to)) * 0.5 + Vector((0, 0, 0.04)), Vector(stalk_to)],
             [length * 0.07, length * 0.06, length * 0.055], 4, 0, smooth=True,
             col_fn=lambda j, i, q: grey(0.7), uv_fn=lambda q: uv_of(U_SPINE))
    return g.obj(name, [mat_], parent)


PALMS = {
    # tiers: fronds from the youngest (top) down; el / droop in degrees, zr = attach depth below the crown top,
    # pw = how late the frond bends down (see arc_points).  pet = bare petiole share of the frond.
    # sawit_3 matches the target: ~3.4 m rough trunk with the bunches hanging on it under an arching umbrella
    # crown (~5 m across, ~5.2 m tall); lower fronds rise first and droop, tips stay >= ~2.4 m up.
    "sawit_1": dict(H=0.25, r=0.11, wr=0.56, boots=5, boot=(0.14, 0.12, 0.06), rings=2, spear=0.5, segs=6, fruits=0,
                    epi=0, crown_r=0.05, ao=0.6, pet=0.12,
                    tiers=[dict(n=11, el=(80, 30), droop=(20, 60), zr=(-0.1, 0.2), L=(0.8, 1.3), pw=1.6)]),
    "sawit_2": dict(H=0.9, r=0.2, wr=0.58, boots=20, boot=(0.26, 0.2, 0.09), rings=3, spear=0.8, segs=7, fruits=0,
                    epi=1, crown_r=0.12, ao=0.58, pet=0.16,
                    tiers=[dict(n=7, el=(78, 58), droop=(20, 40), zr=(-0.1, 0.08), L=(1.3, 1.75), pw=1.5),
                           dict(n=9, el=(44, 26), droop=(58, 72), zr=(0.14, 0.26), L=(1.8, 2.05), pw=1.7)]),
    # sawit_3 must show its ripe bunches from the 45 deg game camera at ANY yaw (the game rotates palms at random):
    # 4 bunches hang low on the trunk (fruit_z), well out from it (fruit_r past the trunk surface), each under a
    # gap of +-`gap` deg in the spreading tiers; the spreading fronds attach above them.
    "sawit_3": dict(H=3.4, r=0.31, wr=0.62, boots=48, boot=(0.42, 0.3, 0.14), rings=7, spear=1.1, segs=7,
                    fruits=4, epi=1, crown_r=0.24, ao=0.55, fruit=(0.66, 0.74), fruit_z=(2.4, 2.1), fruit_r=0.42,
                    fruit_out=0.45, fruit_az=0.0, gap=30, pet=0.18,
                    tiers=[dict(n=6, el=(76, 62), droop=(45, 60), zr=(-0.12, 0.0), L=(2.1, 2.4), pw=1.5),
                           dict(n=8, el=(54, 44), droop=(74, 86), zr=(0.02, 0.1), L=(2.75, 3.0), pw=2.1, win=True),
                           dict(n=6, el=(50, 44), droop=(70, 80), zr=(0.12, 0.2), L=(2.5, 2.7), pw=2.2, win=True,
                                off=0.5)]),
}


def petiole_map(p):
    """card t -> texture t: the first `p` of the card shows the bare petiole (texture 0..0.12)."""
    def f(t):
        return t / p * 0.12 if t < p else 0.12 + (t - p) / (1.0 - p) * 0.88
    return f


def build_palm(name, P, seed=3):
    rnd = random.Random(seed)
    root = empty(name)
    mf = M_frond()
    mt = vmat("M_Trunk", "#a3875e")
    prof = alpha_profile("frond")
    H, r = P["H"], P["r"]
    tg = Geo()
    palm_trunk(tg, 0, H, r, rnd, P["boots"], P["boot"], P["rings"], z0=min(0.3, H * 0.3), crown_dark=H > 0.8)
    trunk = tg.obj(name + "_trunk", [mt])
    bake_ao([trunk], distance=0.6, floor=0.62)
    g = Geo()
    top = H + 0.05
    N = sum(T["n"] for T in P["tiers"])
    vm = petiole_map(P["pet"])
    # bunch azimuths first: the crown's frond gaps can be centred over them
    nf = P["fruits"]
    fa = [math.radians(P.get("fruit_az", 0.0)) + (k + 0.5) * 2 * math.pi / max(1, nf) + rnd.uniform(-0.1, 0.1)
          for k in range(nf)]
    # arcs of azimuth left open by the spreading ("win") tiers, as (centre, half width) in radians
    wins = [(math.radians(c), math.radians(h)) for c, h in P.get("wins", ())]
    if P.get("gap") and nf:
        wins = [(a, math.radians(P["gap"])) for a in fa]
    win = len(wins) > 0
    arcs = []
    if win:
        ws = sorted(((c + math.pi) % (2 * math.pi) - math.pi, h) for c, h in wins)
        for j, (c, h) in enumerate(ws):
            c2, h2 = ws[(j + 1) % len(ws)]
            a0, a1 = c + h, c2 - h2 + (2 * math.pi if j == len(ws) - 1 else 0.0)
            arcs.append((a0, a1 - a0))
    arc_len = sum(l for _, l in arcs)

    def arc_angle(u):
        d = u * arc_len
        for a0, l in arcs:
            if d <= l:
                return a0 + d
            d -= l
        return arcs[-1][0] + arcs[-1][1]
    i = 0
    for T in P["tiers"]:
        for k in range(T["n"]):
            f = k / max(1, T["n"] - 1)
            age = i / max(1, N - 1)  # 0 youngest (upright, top) -> 1 oldest (spreading, drooping)
            if T.get("win") and win:
                # spread evenly over the arcs outside the gaps
                u = ((k + 0.5 + T.get("off", 0.0)) / T["n"]) % 1.0
                phi = arc_angle(u) + rnd.uniform(-0.08, 0.08)
            else:
                phi = i * GOLDEN + rnd.uniform(-0.12, 0.12)
            i += 1
            el = lerp(T["el"][0], T["el"][1], f) + rnd.uniform(-4, 4)
            dr = lerp(T["droop"][0], T["droop"][1], f) + rnd.uniform(-5, 5)
            L = lerp(T["L"][0], T["L"][1], f) * rnd.uniform(0.95, 1.04)
            zb = top - lerp(T["zr"][0], T["zr"][1], f)
            rb = P["crown_r"] * (0.35 + 0.65 * age)
            base = Vector((rb * math.cos(phi), rb * math.sin(phi), zb))
            pts = arc_points(base, phi, el, dr, L, P["segs"], yaw_drift=rnd.uniform(-0.15, 0.15), pw=T.get("pw", 1.4))
            tint = (1.0, 1.0, 0.88) if age < 0.18 else ((0.97, 0.93, 0.74) if age > 0.9 else (1.0, 1.0, 1.0))
            card_path(g, 0, pts, L * P["wr"], prof=prof, fold=(lerp(0.36, 0.2, age), lerp(0.25, 0.5, age)),
                      across=5, twist=rnd.uniform(-12, 12), vmap=vm,
                      col_fn=lambda t, s, tint=tint: cscale(tint, plant_ao(t, s, lo=P["ao"], reach=0.42)),
                      side_hint=Vector((math.sin(phi), -math.cos(phi), 0.0)))
    for k, (sp, el) in enumerate(((P["spear"], 87), (P["spear"] * 0.72, 74))):
        phi = rnd.uniform(0, 6.28)
        pts = arc_points(Vector((0, 0, top - 0.12)), phi, el, 6, sp, 4)
        card_path(g, 0, pts, sp * 0.16, uv=(0.4, 0.15, 0.6, 1.0), across=3, fold=(0.6, 0.2),
                  col_fn=lambda t, s: cscale((1.0, 1.0, 0.85), plant_ao(t, s, lo=0.6, reach=0.5)),
                  side_hint=Vector((math.sin(phi), -math.cos(phi), 0.0)))
    for k in range(P["epi"]):  # small ferny epiphytes on the trunk
        z = lerp(0.9, H - 1.0, (k + 0.5) / max(1, P["epi"])) + rnd.uniform(-0.2, 0.2)
        a = rnd.uniform(0, 6.28)
        for j in range(3):
            aa = a + (j - 1) * 0.6
            b = Vector((math.cos(aa), math.sin(aa), 0)) * (trunk_radius(z, H, r) + 0.12) + UP * z
            pts = arc_points(b, aa, rnd.uniform(25, 50), 70, rnd.uniform(0.4, 0.55), 4)
            card_path(g, 0, pts, 0.24, prof=prof, across=3, fold=(0.2, 0.3),
                      col_fn=lambda t, s: cscale((0.92, 1.0, 0.82), plant_ao(t, s, lo=0.55)))
    crown = g.obj(name + "_crown", [mf, mt])
    body = join([trunk, crown], name + "_body")
    body.parent = root
    if nf:
        # 3-4 separate egg-shaped bunches hanging on the trunk under the crown, spread in angle and height so
        # the trunk shows between them; axis mostly down and a little out, a short stalk into the trunk
        fr = empty("Fruits", parent=root)
        mfr = M_fruit()
        z_hi, z_lo = P["fruit_z"]
        for k in range(nf):
            a = fa[k]
            ln = rnd.uniform(*P["fruit"])
            z = lerp(z_hi, z_lo, (k % 2) if nf % 2 == 0 else k / max(1, nf - 1)) + rnd.uniform(-0.05, 0.05)
            out = Vector((math.cos(a), math.sin(a), 0.0))
            side = Vector((-out.y, out.x, 0.0)) * rnd.uniform(-0.12, 0.12)
            c = out * (trunk_radius(z, H, r) + P["fruit_r"]) + UP * z
            axis = out * P.get("fruit_out", 0.4) + side - UP * 0.9
            stalk_to = out * trunk_radius(z, H, r) * 0.7 + UP * (z + ln * 0.5)
            fruit_bunch(f"Fruit_{k}", c, axis, ln, rnd, mfr, fr, n=P.get("fruit_n", 44), width=0.4, out=out,
                        stalk_to=stalk_to, redness=rnd.uniform(-0.08, 0.08))
    return root


def build_sawit_0():
    """Seedling in a black polybag (bibit)."""
    rnd = random.Random(11)
    root = empty("sawit_0")
    m_bag = vmat("M_Polybag", "#35302c", rough=0.55, spec=0.4)
    m_soil = vmat("M_Soil", "#5a4030")
    g = Geo()
    sides, rings, Hb, R = 14, 5, 0.35, 0.17
    rows = []
    for j in range(rings + 1):
        t = j / rings
        z = Hb * t
        rr = R * (0.92 + 0.14 * math.sin(math.pi * min(1.0, t * 1.2)))
        if j == rings:
            rr = R * 0.98
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides
            wr = rr * (1.0 + 0.05 * math.sin(a * 5 + j * 1.7) + rnd.uniform(-0.02, 0.02))
            row.append(g.vert((wr * math.cos(a), wr * math.sin(a), z + (rnd.uniform(-0.012, 0.012) if j else 0))))
        rows.append(row)
    for j in range(rings):
        for i in range(sides):
            a, b = rows[j][i], rows[j][(i + 1) % sides]
            c, d = rows[j + 1][(i + 1) % sides], rows[j + 1][i]
            mid = (g.v[a] + g.v[c]) * 0.5
            g.face((a, b, c, d), 0, ref=Vector((mid.x, mid.y, 0)), smooth=True)
    soil_ring = [g.vert((R * 0.9 * math.cos(2 * math.pi * i / sides), R * 0.9 * math.sin(2 * math.pi * i / sides),
                         Hb - 0.035)) for i in range(sides)]
    for i in range(sides):
        g.face((rows[-1][i], rows[-1][(i + 1) % sides], soil_ring[(i + 1) % sides], soil_ring[i]), 0, ref=UP,
               smooth=True)
    sc = g.vert((0, 0, Hb - 0.015))
    for i in range(sides):
        g.face((soil_ring[i], soil_ring[(i + 1) % sides], sc), 1, ref=UP, smooth=True)
    bag = g.obj("sawit_0_bag", [m_bag, m_soil])
    bake_ao([bag], distance=0.3)
    fg = Geo()
    prof = alpha_profile("frond")
    for i in range(6):
        phi = i * 2 * math.pi / 6 + 0.5 + rnd.uniform(-0.2, 0.2)
        el = lerp(82, 45, (i % 3) / 2) + rnd.uniform(-4, 4)
        L = rnd.uniform(0.36, 0.46)
        pts = arc_points((0.015 * math.cos(phi), 0.015 * math.sin(phi), Hb - 0.02), phi, el, rnd.uniform(25, 45), L, 4)
        card_path(fg, 0, pts, L * 0.52, prof=prof, across=3, fold=(0.35, 0.25),
                  col_fn=lambda t, s: cscale((1.0, 1.0, 0.9), plant_ao(t, s, lo=0.6)),
                  side_hint=Vector((math.sin(phi), -math.cos(phi), 0.0)))
    leaves = fg.obj("sawit_0_leaves", [M_frond()])
    o = join([bag, leaves], "sawit_0_body")
    o.parent = root
    return root


def build_tbs():
    """A harvested bunch (carried by the player and dropped on the ground): the same egg of small rounded
    fruitlets as on the palm (~400 tris), one solid piece with a cut stalk stub, lying on its side."""
    rnd = random.Random(21)
    root = empty("tbs")
    L = 0.5
    axis = Vector((1.0, 0.15, 0.25)).normalized()
    stalk_to = -axis * (L * 0.5 + 0.13) + Vector((0.0, 0.0, -0.02))
    o = fruit_bunch("tbs_mesh", (0, 0, 0), axis, L, rnd, M_fruit(), None, n=32, width=0.42, spines=6,
                    stalk_to=stalk_to, fsize=0.13)
    bpy.context.view_layer.update()
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin
    # soft contact shadow on the underside (the bunch lies on the ground)
    h = max(v.co.z for v in o.data.vertices)
    cols, dom = get_cols(o)
    me = o.data
    for pg in me.polygons:
        for li in pg.loop_indices:
            z = me.vertices[me.loops[li].vertex_index].co.z
            f = lerp(0.72, 1.0, smoothstep(0.0, h * 0.6, z))
            for c in range(3):
                cols[li * 4 + c] *= f
    me.color_attributes["Col"].data.foreach_set("color", cols)
    o.parent = root
    return root


# ============================================================ undergrowth
def build_fern(name, seed, tiers, tint=(1.0, 1.0, 1.0), spread=0.05, wmul=0.56, segs=5):
    """Mounded fern clump: tiers of arching fronds, the young inner ones upright and the outer ones
    spreading and drooping, so the clump reads as layered (not a flat star) from the game camera.
    tiers: (n, el0, el1, droop0, droop1, L0, L1, pw, brightness, yellow tint).  Dark centre."""
    rnd = random.Random(seed)
    root = empty(name)
    g = Geo()
    prof = alpha_profile("fern")
    i = 0
    for n, el0, el1, dr0, dr1, L0, L1, pw, br0, yel in tiers:
        for k in range(n):
            f = k / max(1, n - 1)
            phi = i * GOLDEN + rnd.uniform(-0.25, 0.25)
            i += 1
            el = lerp(el0, el1, f) + rnd.uniform(-5, 5)
            dr = lerp(dr0, dr1, f) + rnd.uniform(-8, 8)
            Li = lerp(L0, L1, f) * rnd.uniform(0.84, 1.1)
            base = Vector((spread * math.cos(phi), spread * math.sin(phi), 0.02))
            pts = arc_points(base, phi, el, dr, Li, segs, yaw_drift=rnd.uniform(-0.3, 0.3), pw=pw)
            br = br0 * rnd.uniform(0.92, 1.06)
            tt = cmul(tint, (1.0, 1.0, 1.0 - yel))
            card_path(g, 0, pts, Li * wmul, prof=prof, across=3, fold=(0.14, 0.2), twist=rnd.uniform(-14, 14),
                      col_fn=lambda t, s, br=br, tt=tt: cscale(tt, br * plant_ao(t, s, lo=0.46, reach=0.6)),
                      side_hint=Vector((math.sin(phi), -math.cos(phi), 0.0)))
    g.obj(name + "_mesh", [M_fern()], root)
    return root


def build_keladi():
    """Taro: big heart-shaped leaves on long petioles, tips drooping outward."""
    rnd = random.Random(14)
    root = empty("keladi")
    g = Geo()
    u0, v0, u1, v1 = ATLAS["keladi"]
    ax, ay = 0.0, -0.1  # petiole attachment in tile coords (-0.5..0.5)
    stem_uv = (lerp(u0, u1, 0.5), lerp(v0, v1, 0.5 + ay - 0.03))
    leaves = [(0.0, 0.78, 0.6, 58), (1.25, 0.62, 0.52, 42), (2.5, 0.7, 0.56, 50), (3.7, 0.5, 0.46, 35),
              (4.9, 0.66, 0.54, 46), (5.8, 0.42, 0.4, 30), (0.7, 0.36, 0.34, 25)]
    for k, (phi, h, S, tilt) in enumerate(leaves):
        phi += rnd.uniform(-0.2, 0.2)
        O = Vector((math.cos(phi), math.sin(phi), 0.0))
        P = O * h * 0.38 + UP * h
        b0 = O * 0.04
        mid = (b0 + P) * 0.5 + O * 0.02 + UP * 0.05
        tube(g, [b0, mid, P], [0.028, 0.022, 0.016], 3, 0, smooth=True,
             col_fn=lambda j, i, q: grey(lerp(0.55, 0.95, j / 2)), uv_fn=lambda q: stem_uv)
        tl = math.radians(tilt + rnd.uniform(-8, 8))
        Tv = (O * math.cos(tl) - UP * math.sin(tl)).normalized()  # tip direction (outward, drooping)
        Rv = Tv.cross(UP).normalized()
        N = Rv.cross(Tv).normalized()
        grid = []
        for iy in range(4):
            y = -0.5 + iy / 3
            row = []
            for ix in range(4):
                x = -0.5 + ix / 3
                q = P + Rv * (x - ax) * S + Tv * (y - ay) * S - N * S * (0.1 * (2 * x) ** 2 + 0.05 * max(0, y) ** 2)
                d = math.hypot(x - ax, y - ay)
                row.append((g.vert(q, grey(lerp(0.85, 1.0, min(1.0, d * 2)))), (lerp(u0, u1, x + 0.5), lerp(v0, v1, y + 0.5))))
            grid.append(row)
        for iy in range(3):
            for ix in range(3):
                a, b, c, d = grid[iy][ix], grid[iy][ix + 1], grid[iy + 1][ix + 1], grid[iy + 1][ix]
                g.face((a[0], b[0], c[0], d[0]), 0, ref=N, uv=(a[1], b[1], c[1], d[1]), smooth=True)
    g.obj("keladi_mesh", [M_leaf()], root)
    return root


def build_shrub_a():
    """Dense broad-leaf shrub (~0.75 m): a dome of big glossy leaves, leaf clusters on top."""
    rnd = random.Random(33)
    root = empty("shrub_a")
    g = Geo()
    cc = ((ATLAS["cluster"][0] + ATLAS["cluster"][2]) / 2, (ATLAS["cluster"][1] + ATLAS["cluster"][3]) / 2)
    geo_blob(g, 0, (0, 0, 0.26), 0.26, (1.2, 1.1, 0.95), seed=4, subdiv=2, amp=0.12,
             col_fn=lambda p, n: grey(lerp(0.45, 0.8, smoothstep(0.0, 0.5, p.z))), uv_fn=sphere_uv(cc, 0.06),
             floor=0.0)
    for k in range(7):
        a = k * GOLDEN + 0.4
        e = rnd.uniform(0.3, 1.3)
        n = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        p = Vector((0, 0, 0.3)) + Vector((n.x * 0.3, n.y * 0.28, n.z * 0.26))
        quad_card(g, 0, p, n + UP * 0.4, rnd.uniform(0.42, 0.52), ATLAS["cluster"], spin=rnd.uniform(0, 6.28),
                  col=grey(lerp(0.75, 1.0, n.z)), col_rim=grey(0.7))
    bprof = alpha_profile("leaves", ATLAS["broad"])
    for k in range(22):
        a = k * GOLDEN + rnd.uniform(-0.2, 0.2)
        e = math.radians(lerp(-5, 62, (k % 4) / 3) + rnd.uniform(-8, 8))
        D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        base = Vector((0.12 * math.cos(a), 0.12 * math.sin(a), 0.12 + 0.2 * rnd.random()))
        L = rnd.uniform(0.36, 0.48)
        br = rnd.uniform(0.88, 1.05)
        leaf_card(g, 0, base, D, L, L * 0.9, ATLAS["broad"], droop=0.3, segs=2, prof=bprof, across=3,
                  fold=(0.3, 0.2), twist=rnd.uniform(-20, 20),
                  col_fn=lambda t, s, br=br: grey(br * plant_ao(t, s, lo=0.55, reach=0.5)))
    g.obj("shrub_a_mesh", [M_leaf("M_Bush")], root)
    return root


def build_shrub_b():
    """Mounded broad-leaf bush (~0.8 m): a dark leafy core with tiers of big glossy pointed leaves -
    wide and drooping at the bottom, rising towards the top - plus a few sprigs and leaf clusters."""
    rnd = random.Random(35)
    root = empty("shrub_b")
    g = Geo()
    cc = ((ATLAS["cluster"][0] + ATLAS["cluster"][2]) / 2, (ATLAS["cluster"][1] + ATLAS["cluster"][3]) / 2)
    geo_blob(g, 0, (0, 0, 0.34), 0.2, (1.1, 1.0, 1.75), seed=8, subdiv=1, amp=0.14,
             col_fn=lambda p, n: grey(lerp(0.5, 0.75, smoothstep(0.0, 0.7, p.z))), uv_fn=sphere_uv(cc, 0.05),
             floor=0.0)
    bprof = alpha_profile("leaves", ATLAS["broad"])
    # stacked tiers of near-horizontal leaves (broad side up, so they read from the 45 deg camera):
    #        n, z,    el range,  length range, droop, brightness
    tiers = [(7, 0.1, (0, 12), (0.46, 0.54), 0.36, 0.8),
             (7, 0.28, (8, 20), (0.42, 0.5), 0.32, 0.86),
             (7, 0.46, (14, 28), (0.38, 0.44), 0.28, 0.93),
             (6, 0.62, (22, 36), (0.32, 0.38), 0.24, 1.0),
             (4, 0.76, (38, 56), (0.26, 0.3), 0.18, 1.06)]
    k = 0
    for cnt, z, els, lens, droop, br0 in tiers:
        for i in range(cnt):
            a = k * GOLDEN + rnd.uniform(-0.25, 0.25)
            k += 1
            e = math.radians(rnd.uniform(*els))
            D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
            L = rnd.uniform(*lens)
            r0 = 0.06 + 0.12 * (1.0 - z / 0.76)
            base = Vector((r0 * math.cos(a), r0 * math.sin(a), z + rnd.uniform(-0.03, 0.03)))
            br = br0 * rnd.uniform(0.94, 1.05)
            leaf_card(g, 0, base, D, L, L * 0.95, ATLAS["broad"], droop=droop, segs=2, prof=bprof, across=3,
                      fold=(0.16, 0.14), twist=rnd.uniform(-8, 8),
                      col_fn=lambda t, s, br=br: grey(br * plant_ao(t, s, lo=0.62, reach=0.5)))
    sprof = alpha_profile("leaves", ATLAS["sprig"])
    for i in range(3):
        a = i * 2.1 + 0.6
        e = math.radians(rnd.uniform(35, 55))
        D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        leaf_card(g, 0, Vector((0.08 * math.cos(a), 0.08 * math.sin(a), 0.35)), D, 0.5, 0.42, ATLAS["sprig"],
                  droop=0.3, segs=2, prof=sprof, across=3, col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.6, reach=0.6)))
    for i in range(4):
        a = i * 1.57 + 0.3
        n = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 0.8))
        quad_card(g, 0, Vector((0.12 * math.cos(a), 0.12 * math.sin(a), 0.62)), n, 0.4, ATLAS["cluster"],
                  spin=rnd.uniform(0, 6.28), col=grey(1.0), col_rim=grey(0.8))
    g.obj("shrub_b_mesh", [M_leaf("M_Leaf")], root)
    return root


def build_bush(name, seed, blobs, sprigs, clusters, broad=0):
    """Wild thicket: dark leafy core blobs covered by many leaf-cluster cards, a few sprigs sticking out."""
    rnd = random.Random(seed)
    root = empty(name)
    g = Geo()
    cu0, cv0, cu1, cv1 = ATLAS["cluster"]
    cc = ((cu0 + cu1) / 2, (cv0 + cv1) / 2)
    top = max(z + r * sz for (x, y, z, r, sx, sy, sz) in blobs)
    for i, (x, y, z, r, sx, sy, sz) in enumerate(blobs):
        geo_blob(g, 0, (x, y, z), r * 0.85, (sx, sy, sz), seed=seed + i, subdiv=1, amp=0.12,
                 col_fn=lambda p, n: grey(lerp(0.38, 0.62, smoothstep(0.0, top, p.z))),
                 uv_fn=sphere_uv(cc, 0.05), floor=0.0)
    for k in range(clusters):
        x, y, z, r, sx, sy, sz = blobs[k % len(blobs)]
        a = k * GOLDEN + rnd.uniform(-0.3, 0.3)
        e = math.asin(clamp01(rnd.uniform(-0.25, 1.0)) if k % 5 else rnd.uniform(0.6, 1.0))
        n = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        p = Vector((x, y, z)) + Vector((n.x * r * sx, n.y * r * sy, n.z * r * sz)) * rnd.uniform(0.8, 1.0)
        if p.z < 0.15:
            p.z = 0.15
        v = lerp(0.62, 1.0, smoothstep(0.0, top, p.z)) * (0.85 + 0.15 * n.z)
        quad_card(g, 0, p, n + UP * 0.35, rnd.uniform(0.42, 0.58), ATLAS["cluster"], spin=rnd.uniform(0, 6.28),
                  col=grey(v), flat=True)
    prof = alpha_profile("leaves", ATLAS["sprig"])
    for k in range(sprigs):
        x, y, z, r, sx, sy, sz = blobs[k % len(blobs)]
        a = rnd.uniform(0, 2 * math.pi)
        e = math.radians(rnd.uniform(-10, 55))
        D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        base = Vector((x + math.cos(a) * r * sx * 0.6, y + math.sin(a) * r * sy * 0.6, max(0.1, z)))
        L = rnd.uniform(0.45, 0.62)
        leaf_card(g, 0, base, D, L, L, ATLAS["sprig"], droop=0.3, segs=2, prof=prof, across=3,
                  col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.5, reach=0.6)))
    bprof = alpha_profile("leaves", ATLAS["broad"])
    for k in range(broad):
        a = rnd.uniform(0, 2 * math.pi)
        e = math.radians(rnd.uniform(5, 30))
        D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        x, y, z, r, sx, sy, sz = blobs[k % len(blobs)]
        base = Vector((x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5, 0.05))
        L = rnd.uniform(0.4, 0.5)
        leaf_card(g, 0, base, D, L, L * 0.9, ATLAS["broad"], droop=0.35, segs=2, prof=bprof, across=3,
                  col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.5, reach=0.5)))
    g.obj(name + "_mesh", [M_leaf("M_Bush")], root)
    return root


def build_bush_a():
    blobs = [(0.0, 0.0, 0.55, 0.5, 1.0, 0.95, 1.0), (0.42, 0.2, 0.35, 0.38, 1.0, 1.0, 0.9),
             (-0.4, -0.12, 0.32, 0.36, 1.1, 0.9, 0.85)]
    return build_bush("bush_a", 31, blobs, sprigs=6, clusters=100, broad=2)


def build_bush_b():
    blobs = [(-0.3, 0.0, 0.3, 0.45, 1.2, 1.0, 0.85), (0.4, 0.12, 0.26, 0.42, 1.15, 1.0, 0.8),
             (0.0, -0.3, 0.2, 0.34, 1.2, 1.0, 0.75)]
    return build_bush("bush_b", 47, blobs, sprigs=6, clusters=100, broad=3)


def grass_cards(g, mi, rnd, n, w, h, rects, center=(0.0, 0.0), spread=0.06, lean=0.08, lo=0.68):
    for k in range(n):
        rect, asp = rects[k % len(rects)]
        yaw = k * math.pi / n + rnd.uniform(-0.25, 0.25)
        hh = h * rnd.uniform(0.85, 1.12)
        ww = hh * asp * (w / h) if w else hh * asp
        c = Vector((center[0] + rnd.uniform(-spread, spread), center[1] + rnd.uniform(-spread, spread), 0.0))
        cross_card(g, mi, c, yaw, ww, hh, rect, lean=(rnd.uniform(-lean, lean), rnd.uniform(-lean, lean)),
                   col_fn=lambda t: grey(lerp(lo, 1.0, smoothstep(0.0, 0.7, t))))


def build_grass(name, seed, n, h, half, wmul=1.0, spread=0.06, lo=0.68):
    rnd = random.Random(seed)
    root = empty(name)
    g = Geo()
    rect = alpha_bbox("grass", HALVES[half])
    grass_cards(g, 0, rnd, n, 0, h, [(rect[0], rect[1] * wmul)], spread=spread, lo=lo)
    g.obj(name + "_mesh", [M_grass()], root)
    return root


def build_flowers(name, seed, halves, n=3, h=0.42):
    rnd = random.Random(seed)
    root = empty(name)
    g = Geo()
    rects = [alpha_bbox("flowers", HALVES[x]) for x in halves]
    grass_cards(g, 0, rnd, n, 0, h, rects, spread=0.1, lean=0.04, lo=0.6)
    g.obj(name + "_mesh", [M_flower()], root)
    return root


# ============================================================ ground litter
def build_frond_fallen():
    """A dead frond lying on the ground (petiole butt + leaflets)."""
    rnd = random.Random(51)
    root = empty("frond_fallen")
    g = Geo()
    prof = alpha_profile("frond_dry")
    L = 2.4
    pts = []
    for i in range(8):
        t = i / 7
        pts.append(Vector((-L * 0.5 + L * t, 0.12 * math.sin(t * 2.5) * (1 - t), 0.03 + 0.13 * (1 - t) ** 2 + 0.03 * math.sin(math.pi * t))))
    card_path(g, 0, pts, L * 0.52, prof=prof, across=3, fold=(-0.05, 0.15), twist=8,
              col_fn=lambda t, s: grey(lerp(0.78, 1.0, t) - 0.05 * abs(s)), side_hint=Vector((0, -1, 0)))
    wood = vmat("M_FrondButt", "#b08e5c")
    wg = Geo()
    tube(wg, [pts[0] - Vector((0.18, 0.0, -0.02)), pts[0] + Vector((0.05, 0, 0))], [0.075, 0.05], 5, 0, cap_top=True,
         smooth=False, col_fn=lambda j, i, q: grey(0.7 + 0.25 * j))
    card = g.obj("frond_fallen_leaf", [M_frond_dry()])
    butt = wg.obj("frond_fallen_butt", [wood])
    o = join([card, butt], "frond_fallen_mesh")
    o.parent = root
    return root


def build_pile_fronds():
    """Stack of cut fronds between palm rows (gawangan): dry at the bottom, fresher on top."""
    rnd = random.Random(53)
    root = empty("pile_fronds")
    g = Geo()
    pd, pg = alpha_profile("frond_dry"), alpha_profile("frond")
    butts = Geo()
    specs = [(0, -0.25, 0.0, 0.12, 0), (1, 0.28, 0.1, -0.1, 0), (0, 0.02, 0.2, 0.05, 1), (1, -0.1, 0.3, -0.18, 1),
             (0, 0.15, 0.38, 0.2, 2)]
    for k, (mi, dy, z, yaw, lvl) in enumerate(specs):
        L = rnd.uniform(2.2, 2.6)
        d = Vector((math.cos(yaw), math.sin(yaw), 0.0))
        side = Vector((-d.y, d.x, 0.0))
        pts = []
        for i in range(7):
            t = i / 6
            pts.append(d * (-L * 0.5 + L * t) + side * dy + UP * (0.04 + z * (1 - 0.6 * abs(t - 0.45)) +
                                                                 0.08 * math.sin(math.pi * t)))
        prof = pd if mi == 0 else pg
        tint = (1.0, 1.0, 1.0) if mi == 0 else (0.92, 0.9, 0.62)
        card_path(g, mi, pts, L * 0.5, prof=prof, across=3, fold=(0.0, 0.2), twist=rnd.uniform(-10, 10),
                  col_fn=lambda t, s, tint=tint, lvl=lvl: cscale(tint, lerp(0.62, 0.8, lvl / 2) + 0.2 * t - 0.05 * abs(s)),
                  side_hint=-side)
        tube(butts, [pts[0] - d * 0.2 + UP * 0.02, pts[0] + d * 0.04], [0.07, 0.05], 5, 0, cap_top=True, smooth=False,
             col_fn=lambda j, i, q: grey(0.7 + 0.25 * j))
    leaves = g.obj("pile_leaves", [M_frond_dry(), M_frond()])
    b = butts.obj("pile_butts", [vmat("M_FrondButt", "#b08e5c")])
    o = join([leaves, b], "pile_fronds_mesh")
    o.parent = root
    return root


def build_piringan():
    """Weeded mulch circle around a palm: flat 2.4 m alpha decal, raised 2-3 cm."""
    root = empty("piringan")
    m = tmat("M_Piringan", "piringan", rough=0.95, spec=0.1, double=False)
    g = Geo()
    S = 2.4
    n = 8
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n + math.pi / n
        rr = S * 0.5 / math.cos(math.pi / n)
        p = Vector((rr * math.cos(a), rr * math.sin(a), 0.02))
        ring.append((g.vert(p, grey(1.0)), (0.5 + p.x / S, 0.5 + p.y / S)))
    c = g.vert((0, 0, 0.035), grey(0.8))
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        g.face((a[0], b[0], c), 0, ref=UP, uv=(a[1], b[1], (0.5, 0.5)))
    g.obj("piringan_mesh", [m], root)
    return root


def build_vine_log():
    """Fallen log sunk a little into the ground: ridged bark with dark crevices, moss (M_Moss) on its
    upper side, sawn ends, a branch stub, ivy sprigs and a few broad leaves growing over it."""
    rnd = random.Random(57)
    root = empty("vine_log")
    m_bark = vmat("M_LogBark", "#7d6547")
    m_wood = vmat("M_Wood", "#c9a06a")
    m_moss = vmat("M_Moss", "#6d8a36", rough=1.0, spec=0.1)
    g = Geo()
    L, sides = 2.2, 14
    n = 7
    path = [Vector((-L / 2 + L * t, 0.05 * math.sin(t * 5), 0.17 + 0.03 * math.sin(t * 3))) for t in
            [i / (n - 1) for i in range(n)]]
    rows = []
    for j, p in enumerate(path):
        rr = lerp(0.22, 0.18, j / (n - 1)) * (1.0 + 0.05 * math.sin(j * 1.9))
        T = (path[min(j + 1, n - 1)] - path[max(j - 1, 0)]).normalized()
        S = T.cross(UP).normalized()
        B = S.cross(T)
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides + 0.12 * math.sin(j * 1.3)
            ridge = i % 2 == 0
            r_ = rr * (1.06 if ridge else 0.9) * rnd.uniform(0.97, 1.03)
            q = p + (S * math.cos(a) + B * math.sin(a)) * r_
            row.append(g.vert(q, grey(1.0 if ridge else 0.62)))
        rows.append((row, p))
    for j in range(n - 1):
        (ra, pa), (rb, pb) = rows[j], rows[j + 1]
        for i in range(sides):
            q = (ra[i], ra[(i + 1) % sides], rb[(i + 1) % sides], rb[i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            g.face(q, 0, ref=fc - (pa + pb) * 0.5, smooth=True)
    for (row, p), sgn in ((rows[0], -1), (rows[-1], 1)):  # sawn ends with a darker heart
        T = (path[-1] - path[0]).normalized() * sgn
        cidx = g.vert(p + T * 0.02, grey(0.7))
        for i in range(sides):
            g.face((row[i], row[(i + 1) % sides], cidx), 1, ref=T)
    tube(g, [path[2] + Vector((0, 0.1, 0.08)), path[2] + Vector((0.1, 0.35, 0.28))], [0.06, 0.03], 4, 0, cap_top=True)
    log = g.obj("vine_log_wood", [m_bark, m_wood])
    bake_ao([log], distance=0.5)
    moss_faces(log, m_moss, thr=0.93, amp=0.34, freq=4.2)
    moss_tint(log, thr=0.5, amp=0.5, freq=2.5, tint=(0.85, 0.92, 0.7))
    # the moss material only on the bark (never on the sawn ends)
    me = log.data
    mi_moss = [m.name for m in me.materials].index("M_Moss")
    for pg in me.polygons:
        if pg.material_index == mi_moss and abs(pg.normal.x) > 0.8:
            pg.material_index = 1
    lg = Geo()
    prof = alpha_profile("leaves", ATLAS["sprig"])
    for k in range(10):
        t = rnd.uniform(0.05, 0.95)
        p = Vector((-L / 2 + L * t, 0.0, 0.3))
        a = rnd.uniform(0, 6.28)
        D = Vector((math.cos(a) * 0.5, math.sin(a), rnd.uniform(-0.6, 0.1)))
        leaf_card(lg, 0, p + Vector((0, 0, 0.06)), D, rnd.uniform(0.35, 0.5), 0.4, ATLAS["sprig"], droop=0.5, segs=2,
                  prof=prof, across=3, col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.6)))
    bprof = alpha_profile("leaves", ATLAS["broad"])
    for k in range(3):
        a = rnd.uniform(0, 6.28)
        e = math.radians(rnd.uniform(15, 40))
        D = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        base = Vector((rnd.uniform(-0.8, 0.8), rnd.choice((-0.28, 0.28)), 0.02))
        leaf_card(lg, 0, base, D, 0.38, 0.34, ATLAS["broad"], droop=0.3, segs=2, prof=bprof, across=3,
                  col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.55)))
    leaves = lg.obj("vine_log_leaves", [M_leaf()])
    o = join([log, leaves], "vine_log_mesh")
    o.parent = root
    return root


def sphere_uv(center_uv, spread=0.06):
    """uv_fn for blobs: normal-direction mapping around an opaque texture spot (seamless, no holes)."""
    def fn(p, n):
        return (center_uv[0] + spread * n.x, center_uv[1] + spread * n.y)
    return fn


def moss_tint(o, thr=0.55, amp=0.35, freq=2.0, tint=(0.72, 0.86, 0.5), soft=0.18):
    """Multiply a soft moss tint into `Col` on upward-facing, noisy patches (after the AO bake)."""
    me = o.data
    attr = me.color_attributes["Col"]
    cols = [0.0] * (len(attr.data) * 4)
    attr.data.foreach_get("color", cols)
    for p in me.polygons:
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index]
            k = v.normal.z + amp * noise.noise(v.co * freq + Vector((3.1, 1.7, 0.4)))
            m = smoothstep(thr - soft, thr + soft, k)
            for c in range(3):
                cols[li * 4 + c] *= lerp(1.0, tint[c], m)
    attr.data.foreach_set("color", cols)


def patch_uv(center_uv, scale, jitter, rnd):
    """face_uv callback: each face samples a random patch of an opaque texture region."""
    def fn(points):
        c = sum(points, Vector()) / len(points)
        n = newell(points).normalized() if newell(points).length > 1e-9 else UP
        a = n.cross(UP) if abs(n.z) < 0.9 else Vector((1.0, 0.0, 0.0))
        a.normalize()
        b = n.cross(a)
        ou = center_uv[0] + rnd.uniform(-jitter, jitter)
        ov = center_uv[1] + rnd.uniform(-jitter, jitter)
        return [(ou + (p - c).dot(a) * scale, ov + (p - c).dot(b) * scale) for p in points]
    return fn


# ============================================================ big broadleaf shade tree
def build_tree_big():
    rnd = random.Random(9)
    root = empty("tree_big")
    m_bark = vmat("M_Bark", "#76593c")
    tg = Geo()
    trunk = [(0, 0, 0), (0.05, 0.0, 0.6), (0.0, 0.05, 1.4), (-0.1, 0.05, 2.2), (-0.05, 0.0, 2.7)]
    tube(tg, trunk, [0.44, 0.33, 0.28, 0.26, 0.24], 9, 0, rnd=rnd, jitter=0.05)
    limbs = [((-0.05, 0, 2.4), (0.8, 0.2, 3.3), (1.5, 0.3, 3.9)), ((-0.05, 0, 2.4), (-0.8, 0.4, 3.4), (-1.4, 0.6, 3.9)),
             ((-0.05, 0, 2.4), (0.1, -0.6, 3.5), (0.2, -1.1, 4.0)), ((-0.05, 0, 2.5), (-0.2, 0.3, 3.6), (-0.3, 0.9, 4.4))]
    for lp in limbs:
        tube(tg, lp, [0.19, 0.13, 0.07], 6, 0, rnd=rnd, jitter=0.05)
    for k in range(5):
        a = k * 2 * math.pi / 5 + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        tube(tg, [d * 0.25 + UP * 0.4, d * 0.6 + UP * 0.1, d * 0.9 + UP * 0.0], [0.14, 0.09, 0.03], 5, 0)
    wood = tg.obj("tree_wood", [m_bark])
    bake_ao([wood], distance=0.8)
    g = Geo()
    cu0, cv0, cu1, cv1 = ATLAS["cluster"]
    cc = ((cu0 + cu1) / 2, (cv0 + cv1) / 2)
    canopy = [(0.1, 0.0, 4.55, 1.55, 1.15, 1.1, 0.78), (1.65, 0.35, 4.0, 1.18, 1.0, 1.0, 0.82),
              (-1.55, 0.7, 4.05, 1.15, 1.0, 1.0, 0.82), (0.3, -1.45, 3.95, 1.1, 1.0, 1.0, 0.8),
              (-0.45, 1.55, 4.5, 1.0, 1.0, 1.0, 0.84), (0.4, 0.15, 5.35, 1.0, 1.0, 1.0, 0.8),
              (-1.0, -0.9, 4.6, 0.9, 1.0, 1.0, 0.85)]
    ztop = 6.2
    for i, (x, y, z, r, sx, sy, sz) in enumerate(canopy):
        geo_blob(g, 0, (x, y, z), r * 0.84, (sx, sy, sz), seed=90 + i, subdiv=2, amp=0.12, freq=1.6,
                 col_fn=lambda p, n: grey(lerp(0.32, 0.62, 0.5 + 0.5 * n.z) * lerp(0.8, 1.0, smoothstep(3.0, ztop, p.z))),
                 uv_fn=sphere_uv(cc, 0.05))
    for i, (x, y, z, r, sx, sy, sz) in enumerate(canopy):
        cnt = int(70 + 55 * r)
        for k in range(cnt):
            a = k * GOLDEN + rnd.uniform(-0.3, 0.3)
            e = math.asin(lerp(1.0, -0.4, (k + 0.5) / cnt))  # Fibonacci sphere with the golden-angle azimuth
            n = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
            p = Vector((x, y, z)) + Vector((n.x * r * sx, n.y * r * sy, n.z * r * sz)) * rnd.uniform(0.9, 1.0)
            p += n * 0.22
            v = lerp(0.5, 0.9, 0.5 + 0.5 * n.z) * lerp(0.8, 1.0, smoothstep(3.0, ztop, p.z))
            quad_card(g, 0, p, n + UP * 0.25, rnd.uniform(0.9, 1.25), ATLAS["cluster"], spin=rnd.uniform(0, 6.28),
                      col=grey(v), flat=True)
    leaves = g.obj("tree_canopy", [M_leaf("M_Canopy")])
    o = join([wood, leaves], "tree_big_mesh")
    o.parent = root
    return root


# ============================================================ coconut palm (kelapa)
def build_coconut():
    rnd = random.Random(17)
    root = empty("coconut")
    m_trunk = vmat("M_CocoTrunk", "#a39275")
    m_nut = vmat("M_Coconut", "#8fa232", rough=0.5, spec=0.4)
    tg = Geo()
    H, lean = 5.7, 1.35
    bands = 22
    path, radii = [], []
    for j in range(bands):
        for k in range(2):
            t = (j + (0.3 if k else 0.0)) / bands
            path.append((lean * (1 - (1 - t) ** 2), 0.1 * math.sin(t * 3), H * t))
            r = lerp(0.2, 0.13, t) + 0.1 * max(0.0, 1 - t * 8) ** 2
            radii.append(r * (1.07 if k == 0 else 1.0))
    path.append((lean, 0.1 * math.sin(3), H))
    radii.append(0.12)
    tube(tg, path, radii, 8, 0, smooth=True, col_fn=lambda j, i, q: grey(0.62 if j % 2 == 0 else 0.95))
    top = Vector(path[-1])
    for k in range(6):
        a = k * 1.1 + rnd.uniform(-0.2, 0.2)
        rr = 0.24 + 0.06 * (k % 2)
        c = top + Vector((rr * math.cos(a), rr * math.sin(a), -0.32 - 0.1 * (k % 3)))
        geo_blob(tg, 1, c, 0.16, (1.0, 1.0, 1.12), seed=k, subdiv=1, amp=0.05)
    wood = tg.obj("coconut_trunk", [m_trunk, m_nut])
    bake_ao([wood], distance=0.6)
    g = Geo()
    prof = alpha_profile("frond_coco")
    n = 16
    for i in range(n):
        f = i / (n - 1)
        phi = i * GOLDEN + rnd.uniform(-0.1, 0.1)
        el = lerp(66, -8, f) + rnd.uniform(-5, 5)
        dr = lerp(50, 100, f) + rnd.uniform(-8, 8)
        L = 3.0 * lerp(0.8, 1.0, min(1.0, f * 2)) * rnd.uniform(0.93, 1.05)
        base = top + Vector((0.06 * math.cos(phi), 0.06 * math.sin(phi), 0.05 - 0.15 * f))
        pts = arc_points(base, phi, el, dr, L, 8)
        card_path(g, 0, pts, L * 0.5, prof=prof, fold=(0.7, 0.5), across=5, twist=rnd.uniform(-10, 10),
                  col_fn=lambda t, s: grey(plant_ao(t, s, lo=0.55, reach=0.35)),
                  side_hint=Vector((math.sin(phi), -math.cos(phi), 0.0)))
    fr = g.obj("coconut_fronds", [tmat("M_CocoFrond", "frond_coco", rough=0.6, spec=0.3)])
    o = join([wood, fr], "coconut_mesh")
    o.parent = root
    return root


# ============================================================ banana plant (pisang)
def banana_leaf(g, base, az, el, L, W, rnd, mi, torn=False, segs=6, droop=70):
    """Big paddle leaf: petiole + oblong blade with raised midrib, edges curling down; torn leaves
    are split into ragged strips along the veins.  Colours: pale midrib, darker edges."""
    base = Vector(base)
    pts = [base]
    for i in range(segs + 1):
        t = i / segs
        a = math.radians(el - droop * t ** 1.3)
        d = Vector((math.cos(az) * math.cos(a), math.sin(az) * math.cos(a), math.sin(a)))
        pts.append(pts[-1] + d * (0.25 if i == 0 else L / segs))
    tube(g, [pts[0], pts[1]], [0.03, 0.022], 4, mi, smooth=True)
    st = pts[1:]
    mids, lefts, rights, frames = [], [], [], []
    for i, p in enumerate(st):
        t = i / segs
        T = (st[min(i + 1, segs)] - st[max(i - 1, 0)]).normalized()
        S = T.cross(UP)
        if S.length < 1e-3:
            S = Vector((-math.sin(az), math.cos(az), 0))
        S.normalize()
        N = S.cross(T).normalized()
        w = W * 0.5 * (min(1.0, t * 4.0 + 0.12) ** 0.6) * (max(0.0, 1.0 - t ** 5)) ** 0.5
        mids.append(g.vert(p + N * 0.02, grey(1.0)))
        lefts.append(p + S * w - N * w * 0.4)
        rights.append(p - S * w - N * w * 0.4)
        frames.append((S, N))
    li = [g.vert(x, grey(0.78)) for x in lefts]
    ri = [g.vert(x, grey(0.78)) for x in rights]
    for i in range(segs):
        S, N = frames[i]
        for edge, idx in ((lefts, li), (rights, ri)):
            if torn and 0 < i < segs - 1 and rnd.random() < 0.8:
                ea, eb = edge[i], edge[i + 1]
                sag = -N * rnd.uniform(0.06, 0.16) - UP * rnd.uniform(0.02, 0.08)
                ia = g.vert(ea + sag * 0.6 + (eb - ea) * 0.1, grey(0.72))
                ib = g.vert(eb + sag - (eb - ea) * 0.14, grey(0.72))
            else:
                ia, ib = idx[i], idx[i + 1]
            g.face((mids[i], ia, ib, mids[i + 1]), mi, ref=N, smooth=True)


def leafy(m):
    m.use_backface_culling = False
    m["double_sided"] = True
    return m


def banana_card(g, gs, base, az, el, L, rnd, droop=70, segs=6, pw=1.3, br=1.0):
    """Textured banana leaf: short petiole tube (Geo `gs`, stem material) + a pleated, Λ-folded card
    with the torn-leaf texture (Geo `g`)."""
    base = Vector(base)
    d0 = Vector((math.cos(az) * math.cos(math.radians(el)), math.sin(az) * math.cos(math.radians(el)),
                 math.sin(math.radians(el))))
    p1 = base + d0 * 0.22
    tube(gs, [base, p1], [0.03, 0.022], 4, 0, smooth=True, col_fn=lambda j, i, q: grey(0.8 + 0.15 * j))
    pts = arc_points(p1, az, el, droop, L, segs, yaw_drift=rnd.uniform(-0.15, 0.15), pw=pw)
    card_path(g, 0, pts, L * 0.52, prof=alpha_profile("banana"), across=5, fold=(0.22, 0.32),
              twist=rnd.uniform(-10, 10),
              col_fn=lambda t, s: grey(br * plant_ao(t, s, lo=0.62, reach=0.4)),
              side_hint=Vector((math.sin(az), -math.cos(az), 0.0)))


def build_banana():
    rnd = random.Random(23)
    root = empty("banana")
    m_leaf = tmat("M_BananaLeaf", "banana", rough=0.5, spec=0.35)
    m_stem = vmat("M_Stem", "#8e9a4c")
    m_dry = leafy(vmat("M_DryLeaf", "#a3814a"))
    m_fruit = vmat("M_Banana", "#a6bb3c", rough=0.5)
    g = Geo()
    main_top = Vector((0.06, 0.02, 1.4))
    tube(g, [(0, 0, 0), (0.02, 0.0, 0.5), (0.05, 0.02, 1.0), tuple(main_top)], [0.15, 0.12, 0.1, 0.085], 8, 1,
         rnd=rnd, jitter=0.04, cap_top=True)
    suck_top = Vector((0.42, -0.25, 0.55))
    tube(g, [(0.4, -0.25, 0), (0.41, -0.25, 0.3), tuple(suck_top)], [0.07, 0.055, 0.045], 6, 1, cap_top=True)
    lg = Geo()
    sg = Geo()
    for i in range(8):
        f = i / 7
        az = i * GOLDEN + 0.3
        banana_card(lg, sg, main_top - UP * 0.1 * f, az, lerp(80, 34, f) + rnd.uniform(-4, 4),
                    lerp(1.3, 1.65, min(1.0, f * 2)) * rnd.uniform(0.92, 1.05), rnd, droop=lerp(40, 95, f),
                    br=lerp(1.04, 0.92, f))
    for i in range(3):
        banana_card(lg, sg, suck_top, i * 2.2 - 0.4, lerp(76, 50, i / 2), 0.66, rnd, droop=50, segs=4)
    for k, az in enumerate((2.5, 4.5)):
        banana_leaf(g, main_top - UP * (0.12 + 0.15 * k), az, -62, 0.8 - 0.15 * k, 0.34, rnd, 2, torn=True, droop=18,
                    segs=4)
    stalk = [main_top - UP * 0.05, main_top + Vector((0.05, -0.28, 0.08)), main_top + Vector((0.06, -0.45, -0.25)),
             main_top + Vector((0.06, -0.47, -0.72))]
    tube(g, stalk, [0.035, 0.032, 0.028, 0.02], 5, 1)
    for h in range(3):
        cc = Vector((stalk[2].x, stalk[2].y, stalk[2].z - 0.06 - h * 0.14))
        for k in range(6):
            a = k * 1.047 + h * 0.5
            d = Vector((math.cos(a), math.sin(a), 0))
            p0 = cc + d * 0.035
            p1 = p0 + d * 0.08 + UP * 0.03
            tube(g, [p0, p1, p1 + d * 0.035 + UP * 0.1], [0.024, 0.027, 0.01], 4, 3, smooth=True)
    petioles = sg.obj("banana_petioles", [m_stem])
    o = g.obj("banana_mesh", [m_leaf, m_stem, m_dry, m_fruit])
    o = join([o, petioles], "banana_mesh")
    bake_ao([o], distance=0.6, floor=0.55)
    leaves = lg.obj("banana_leaves", [m_leaf])
    o = join([o, leaves], "banana_mesh")
    o.parent = root
    # a few grass clumps around the foot
    gg = Geo()
    rect = alpha_bbox("grass", HALVES["left"])
    grass_cards(gg, 0, rnd, 3, 0, 0.35, [rect], spread=0.2)
    gm = gg.obj("banana_grass", [M_grass()])
    o2 = join([o, gm], "banana_mesh")
    o2.parent = root
    return root


# ============================================================ rocks
def blob(name, radius, loc, scale, material, seed, subdiv=2, amp=0.2, freq=1.4, amp2=0.0, freq2=3.0):
    o = add_ico(name, 1.0, subdiv=subdiv, material=material)
    off = Vector((seed * 1.71, seed * 2.93, seed * 0.77))
    off2 = Vector((seed * 0.37, seed * 1.13, seed * 2.21))
    for v in o.data.vertices:
        n = v.co.normalized()
        d = 1.0 + amp * noise.noise(n * freq + off) + amp2 * noise.noise(n * freq2 + off2)
        v.co = Vector((n.x * scale[0], n.y * scale[1], n.z * scale[2])) * radius * d + Vector(loc)
    o.data.update()
    shade_smooth(o)
    return o


def clamp_floor(o, z0=0.0):
    for v in o.data.vertices:
        if v.co.z < z0:
            v.co.z = z0
    o.data.update()
    return o


def moss_faces(o, m_moss, thr=0.5, amp=0.3, freq=1.6, mi=None):
    """Assign the moss material to upward-facing faces with a noisy border."""
    me = o.data
    if m_moss.name not in [m.name for m in me.materials]:
        me.materials.append(m_moss)
    idx = [m.name for m in me.materials].index(m_moss.name)
    for p in me.polygons:
        c = p.center
        if p.normal.z > thr + amp * noise.noise(c * freq + Vector((3.1, 1.7, 0.4))):
            p.material_index = idx


def boulder(name, size, seed, material, flat=0.7, stretch=(1.0, 0.82), subdiv=2, sink=0.1, loc=(0, 0, 0)):
    h = size * flat
    o = blob(name, 0.5, (0, 0, 0), (size * stretch[0], size * stretch[1], h), material, seed, subdiv=subdiv,
             amp=0.3, freq=0.85, amp2=0.07, freq2=2.2)
    rnd = random.Random(seed)
    pn = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 1.6)).normalized()
    top = max(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        if v.co.z < 0:
            v.co.x *= 1.08
            v.co.y *= 1.08
        d = v.co.dot(pn) - top * 0.72
        if d > 0:
            v.co -= pn * d * 0.75
        if v.co.z > top * 0.45:
            v.co.z = top * 0.45 + (v.co.z - top * 0.45) * 0.6
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin + h * sink
        v.co += Vector(loc)
    o.data.update()
    return o  # the bottom stays sunk `sink`*height below the ground (sits into uneven terrain)


def build_rock(name, size, seed, extras=(), subdiv=2, grass=0):
    rnd = random.Random(seed)
    root = empty(name)
    m_rock = vmat("M_Rock", "#8b897f")
    m_moss = vmat("M_RockMoss", "#71883e", rough=1.0, spec=0.1)
    parts = [boulder(name + "_main", size, seed, m_rock, subdiv=subdiv)]
    for i, (dx, dy, s) in enumerate(extras):
        parts.append(boulder(f"{name}_x{i}", size * s, seed + 11 * (i + 1), m_rock, subdiv=2 if s < 0.3 else 3,
                             flat=0.55, loc=(size * dx, size * dy, 0)))
    o = join(parts, name + "_mesh") if len(parts) > 1 else parts[0]
    o.name = name + "_mesh"
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    # lit tops a touch lighter, undersides darker (on top of the baked AO), mossy caps as a material
    set_cols(o, lambda p, n: grey(lerp(0.8, 1.0, 0.5 + 0.5 * n.z)))
    bake_ao([o], distance=size * 0.6)
    moss_faces(o, m_moss, thr=0.86, amp=0.45, freq=3.6 / size)
    moss_tint(o, thr=0.55, amp=0.5, freq=3.0 / size, tint=(0.82, 0.92, 0.68))
    o.parent = root
    if grass:
        g = Geo()
        rect = alpha_bbox("grass", HALVES["left"])
        for k in range(grass):
            a = k * 2 * math.pi / grass + rnd.uniform(-0.3, 0.3)
            c = (math.cos(a) * size * 0.55, math.sin(a) * size * 0.45)
            grass_cards(g, 0, rnd, 2, 0, rnd.uniform(0.25, 0.35), [rect], center=c, spread=0.03)
        gm = g.obj(name + "_grass", [M_grass()])
        o = join([o, gm], name + "_mesh")
        o.parent = root
    return root


# ============================================================ cliff / rocky outcrop
def two_tone(o, m_top, m_under, thr=-0.3, m_lit=None, lit_thr=0.75):
    me = o.data
    me.materials.clear()
    me.materials.append(m_top)
    me.materials.append(m_under)
    if m_lit is not None:
        me.materials.append(m_lit)
    for pg in me.polygons:
        if pg.normal.z < thr:
            pg.material_index = 1
        elif m_lit is not None and pg.normal.z > lit_thr:
            pg.material_index = 2
        else:
            pg.material_index = 0
    return o


def slab(name, size, loc, rot, seed, material, bevel=0.2, amp=0.14):
    o = add_box(name, size, loc=(0, 0, 0), material=material)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2 if max(size) > 2.5 else 1, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    mod = o.modifiers.new("Bevel", "BEVEL")
    mod.width = min(bevel, min(size) * 0.3)
    mod.segments = 2
    mod.limit_method = "ANGLE"
    common.apply_modifiers(o)
    off = Vector((seed * 1.3, seed * 0.7, seed * 2.1))
    for v in o.data.vertices:
        c = v.co
        v.co = c + Vector((noise.noise(c * 0.7 + off), noise.noise(c * 0.7 + off + Vector((5, 0, 0))),
                           noise.noise(c * 0.7 + off + Vector((0, 9, 0))) * 0.5)) * amp
    o.rotation_euler = rot
    o.location = loc
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    shade_smooth(o)
    return o


def build_cliff_a():
    """Stepped outcrop (7 x 3 x 2.5 m): rounded slabs, mossy ledges, grass and ferns at the foot."""
    rnd = random.Random(41)
    root = empty("cliff_a")
    m_c = vmat("M_Cliff", "#8a8a80")
    parts = []
    strata = [
        [(-2.2, -0.3, 0.0, 3.1, 2.4, 0.9, 0.07), (1.15, -0.4, 0.0, 3.5, 2.2, 0.8, -0.05),
         (3.15, -0.05, 0.0, 1.2, 1.9, 0.62, 0.25)],
        [(-1.55, 0.3, 0.72, 3.3, 1.9, 0.95, 0.1), (1.65, 0.4, 0.66, 2.6, 1.8, 0.88, -0.14)],
        [(-0.35, 0.85, 1.52, 2.9, 1.3, 0.98, -0.06), (2.05, 0.95, 1.4, 1.3, 1.1, 0.7, 0.3)],
    ]
    k = 0
    for layer in strata:
        for (x, y, z0, w, d, h, rz) in layer:
            rot = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.06, 0.06), rz)
            o = slab(f"cliff_s{k}", (w, d, h), (x, y, z0 + h * 0.5), rot, 70 + k, m_c, amp=0.22)
            parts.append(o)
            k += 1
    o = slab("cliff_lean", (1.3, 0.35, 1.0), (-3.45, -1.2, 0.42), (0.35, 0.0, 0.5), 99, m_c, bevel=0.1, amp=0.1)
    parts.append(o)
    for i, (x, y, s) in enumerate(((-2.6, -1.55, 0.6), (0.6, -1.6, 0.5), (2.75, -1.45, 0.6), (-1.3, -1.65, 0.35))):
        o = boulder(f"cliff_foot{i}", s, 60 + i, m_c, subdiv=2, loc=(x, y, 0))
        parts.append(o)
    o = join(parts, "cliff_rock")
    set_cols(o, lambda p, n: grey(1.0))
    bake_ao([o], distance=1.2)
    moss_tint(o, thr=0.62, amp=0.45, freq=0.9, tint=(0.66, 0.8, 0.46))
    g = Geo()
    rect = alpha_bbox("grass", HALVES["left"])
    rect2 = alpha_bbox("grass", HALVES["right"])
    tufts = [(-2.9, -0.9, 0.95), (-0.8, -0.75, 0.85), (1.3, -0.5, 1.58), (-2.9, 0.1, 1.72), (0.3, 0.4, 2.45),
             (2.6, -0.2, 0.9), (-1.0, -1.7, 0.0), (1.9, -1.7, 0.0), (3.4, -1.1, 0.0), (-3.0, -1.9, 0.0),
             (0.2, -1.9, 0.0)]
    for (x, y, z) in tufts:
        for j in range(3):
            yaw = j * math.pi / 3 + rnd.uniform(-0.2, 0.2)
            rc, asp = (rect if (j + int(x * 3)) % 3 else rect2)
            h = rnd.uniform(0.35, 0.5)
            cross_card(g, 0, (x + rnd.uniform(-0.1, 0.1), y + rnd.uniform(-0.1, 0.1), z - 0.03), yaw, h * asp, h, rc,
                       col_fn=lambda t: grey(lerp(0.55, 1.0, t)))
    gm = g.obj("cliff_grass", [M_grass()])
    o = join([o, gm], "cliff_a_mesh")
    o.parent = root
    return root


# ============================================================ stump
def build_stump():
    rnd = random.Random(5)
    root = empty("stump")
    m_bark = vmat("M_Bark", "#76593c")
    m_wood = vmat("M_Wood", "#d9b27a")
    m_ring = vmat("M_WoodDark", "#b8864f")
    g = Geo()
    sides = 11
    R = 0.16
    rows = []
    for z, k in [(0.0, 1.35), (0.06, 1.12), (0.15, 1.0), (0.25, 0.97)]:
        rows.append([g.vert((R * k * rnd.uniform(0.94, 1.06) * math.cos(2 * math.pi * i / sides),
                             R * k * rnd.uniform(0.94, 1.06) * math.sin(2 * math.pi * i / sides), z)) for i in range(sides)])
    top = []
    for i in range(sides):
        v0 = g.v[rows[-1][i]]
        top.append(g.vert((v0.x, v0.y, 0.29 + 0.05 * v0.x / R + rnd.uniform(-0.004, 0.004))))
    rows.append(top)
    for j in range(len(rows) - 1):
        for i in range(sides):
            q = (rows[j][i], rows[j][(i + 1) % sides], rows[j + 1][(i + 1) % sides], rows[j + 1][i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            g.face(q, 0, ref=Vector((fc.x, fc.y, 0)), smooth=True)

    def ring_at(scale, dz=0.0):
        return [g.vert((g.v[top[i]].x * scale, g.v[top[i]].y * scale, g.v[top[i]].z + dz)) for i in range(sides)]
    r1, r2, r3 = ring_at(0.84, 0.004), ring_at(0.55, 0.006), ring_at(0.45, 0.006)
    for ra, rb, mi in ((top, r1, 0), (r1, r2, 1), (r2, r3, 2)):
        for i in range(sides):
            g.face((ra[i], ra[(i + 1) % sides], rb[(i + 1) % sides], rb[i]), mi, ref=UP)
    c = g.vert((0, 0, 0.301))
    for i in range(sides):
        g.face((r3[i], r3[(i + 1) % sides], c), 1, ref=UP)
    for k in range(4):
        a = k * 1.57 + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        tube(g, [d * R * 0.55 + UP * 0.15, d * R * 1.3 + UP * 0.05, d * R * 1.85 + UP * 0.008],
             [0.075, 0.055, 0.036], 6, 0, smooth=True, cap_top=True)
    o = g.obj("stump_wood", [m_bark, m_wood, m_ring])
    clamp_floor(o, 0.0)
    bake_ao([o], distance=0.3)
    gg = Geo()
    rect = alpha_bbox("grass", HALVES["left"])
    grass_cards(gg, 0, rnd, 2, 0, 0.28, [rect], center=(0.25, -0.15), spread=0.02)
    grass_cards(gg, 0, rnd, 2, 0, 0.22, [rect], center=(-0.22, 0.12), spread=0.02)
    o = join([o, gg.obj("stump_grass", [M_grass()])], "stump_mesh")
    o.parent = root
    return root


# ============================================================ preview / export / checks
COL_FLOOR = 0.46   # contract: vertex colour never darker than ~0.45 (the game multiplies albedo by it)
CARD_LIFT = 0.015  # leaf-card vertices stay this far above the ground plane (no z-fighting with terrain)


def soft_floor(c, lo=COL_FLOOR, knee=0.62):
    """Monotonic soft floor: values above `knee` untouched, below it squeezed into [lo, knee]."""
    if c >= knee:
        return c
    t = max(0.0, c) / knee
    return lo + (knee - lo) * t * t


def finalize(root):
    """Cull back faces on closed (non-leaf) materials, soft-floor every vertex colour at ~0.45 and
    lift leaf-card vertices to >= 1.5 cm above the ground.  Solid parts (rocks, logs, stumps) may
    sink below z=0 so they sit into uneven terrain."""
    for o in all_descendants(root):
        if o.type != "MESH":
            continue
        me = o.data
        card_mat = []
        for slot in o.material_slots:
            m = slot.material
            dbl = m is not None and bool(m.get("double_sided", False))
            card_mat.append(dbl)
            if m is not None and not dbl:
                m.use_backface_culling = True
        card_v = set()
        for pg in me.polygons:
            if card_mat and card_mat[min(pg.material_index, len(card_mat) - 1)]:
                card_v.update(pg.vertices)
        mw = o.matrix_world
        inv = mw.inverted()
        for vi in card_v:
            v = me.vertices[vi]
            w = mw @ v.co
            if w.z < CARD_LIFT:
                w.z = CARD_LIFT
                v.co = inv @ w
        if "Col" in me.color_attributes:
            attr = me.color_attributes["Col"]
            cols = [0.0] * (len(attr.data) * 4)
            attr.data.foreach_get("color", cols)
            for i in range(0, len(cols), 4):
                for c in range(3):
                    cols[i + c] = soft_floor(cols[i + c])
            attr.data.foreach_set("color", cols)
        me.update()


def _game_lights():
    sun = bpy.data.objects.new("_Sun", bpy.data.lights.new("_Sun", "SUN"))
    sun.data.energy = 3.6
    sun.data.angle = math.radians(6)
    sun.data.color = (1.0, 0.94, 0.82)
    d = Vector((0.5, -0.42, -0.76))  # light travels right / toward camera / down: sun at the upper left
    sun.rotation_euler = d.normalized().to_track_quat("-Z", "Y").to_euler()
    common.link(sun)
    return [sun]


def _fit_camera(root, pitch=45.0, yaw=0.0, margin=1.08):
    mn, mx = common._bounds(root)
    corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
    p, yw = math.radians(pitch), math.radians(yaw)
    back = Vector((math.sin(yw) * math.cos(p), -math.cos(yw) * math.cos(p), math.sin(p)))
    fwd = -back
    right = fwd.cross(UP).normalized()
    up = right.cross(fwd)
    xs = [c.dot(right) for c in corners]
    ys = [c.dot(up) for c in corners]
    C0 = (mn + mx) * 0.5
    cx, cy = (min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5
    center = C0 + right * (cx - C0.dot(right)) + up * (cy - C0.dot(up))
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    common.link(cam)
    cam.location = center + back * 60.0
    cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * margin
    cam.data.clip_end = 200.0
    bpy.context.scene.camera = cam
    return cam


def preview(root, name, res=384, samples=16, pitch=45.0, yaw=0.0, margin=1.08, path=None):
    """Cycles preview from the game camera direction (45 deg pitch, looking north) -> blender/previews/."""
    common._setup_render(res, res, transparent=False, samples=samples)
    tmp = _game_lights()
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.002))
    gr = bpy.context.view_layer.objects.active
    gr.name = "_Ground"
    set_mat(gr, mat("_M_PreviewGround", "#8fae52"))
    tmp.append(gr)
    tmp.append(_fit_camera(root, pitch, yaw, margin))
    bpy.context.scene.render.filepath = path or os.path.join(common.PREVIEW_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)


def extra_views(root, name, views):
    """Debug renders into $VEG_SCRATCH (not deliverables): (tag, pitch, yaw, margin)."""
    if not SCRATCH:
        return
    os.makedirs(SCRATCH, exist_ok=True)
    for tag, pitch, yaw, margin in views:
        preview(root, name, res=320, samples=12, pitch=pitch, yaw=yaw, margin=margin,
                path=os.path.join(SCRATCH, f"{name}_{tag}.png"))


def glb_check(name):
    """Read the exported glTF JSON: per material alphaMode / doubleSided / texture; COLOR_0 per primitive."""
    import json
    import struct
    data = open(os.path.join(common.MODELS_DIR, name + ".glb"), "rb").read()
    ln = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + ln])
    mats = []
    for m in js.get("materials", []):
        tex = "tex" if "baseColorTexture" in m.get("pbrMetallicRoughness", {}) else "flat"
        mats.append(f"{m['name']}:{m.get('alphaMode', 'OPAQUE')}/{'2s' if m.get('doubleSided') else '1s'}/{tex}")
    prims = [p for me in js.get("meshes", []) for p in me["primitives"]]
    col = sum(1 for p in prims if "COLOR_0" in p["attributes"])
    return f"mats=[{', '.join(mats)}] COLOR_0={col}/{len(prims)} images={len(js.get('images', []))}"


BUDGET = {"sawit_3": 4500, "sawit_2": 3500, "sawit_1": 3500, "tree_big": 3500, "coconut": 3500, "banana": 3500,
          "cliff_a": 4000}
UNDERGROWTH = {"fern_a", "fern_b", "keladi", "shrub_a", "shrub_b", "grass_a", "grass_b", "grass_tuft", "flowers",
               "flowers_white", "flowers_yellow", "vine_log", "pile_fronds", "frond_fallen", "piringan", "bush_a",
               "bush_b"}
RESULTS = {}


def finish(root, name, views=(), icon=None, icon_kw=None):
    bpy.context.view_layer.update()
    finalize(root)
    preview(root, name)
    extra_views(root, name, views)
    export_glb(root, name)
    if icon and os.environ.get("VEG_ICONS"):
        common.render_icon(root, icon, **(icon_kw or {}))
    tris = count_tris(root)
    budget = BUDGET.get(name, 350 if name in UNDERGROWTH else 1500)
    rep = glb_check(name)
    flag = "" if tris <= budget else f"  !! OVER BUDGET ({budget})"
    RESULTS[name] = (tris, budget, rep)
    print(f"[done] {name}: tris={tris}/{budget}{flag} {rep}")


# ============================================================ registry
ASSETS = {}


def asset(name, builder, views=(), **kw):
    ASSETS[name] = lambda: finish(builder(), name, views=views, **kw)


asset("sawit_0", build_sawit_0, icon="icon_bibit", icon_kw=dict(pitch_deg=25, margin=1.0))
asset("sawit_1", lambda: build_palm("sawit_1", PALMS["sawit_1"], seed=5))
asset("sawit_2", lambda: build_palm("sawit_2", PALMS["sawit_2"], seed=7))
asset("sawit_3", lambda: build_palm("sawit_3", PALMS["sawit_3"], seed=3),
      views=(("side", 8, 0, 1.0), ("close", 45, 0, 0.55), ("top", 88, 0, 1.0)))
asset("tbs", build_tbs, icon="icon_tbs", icon_kw=dict(pitch_deg=48, yaw_deg=20, margin=0.95))
# fern_a: tall pakis clump (~0.65 m tall, ~1.5 m wide), 16 fronds in 3 tiers
asset("fern_a", lambda: build_fern("fern_a", 61, [(5, 86, 76, 66, 80, 0.78, 0.86, 1.6, 1.04, 0.12),
                                                  (6, 70, 60, 88, 96, 0.86, 0.94, 1.7, 0.96, 0.0),
                                                  (5, 54, 44, 98, 106, 0.8, 0.88, 1.8, 0.88, 0.0)]))
# fern_b: lower, yellower, denser clump (~0.5 m tall, ~1.2 m wide), 18 narrower fronds
asset("fern_b", lambda: build_fern("fern_b", 62, [(5, 82, 74, 55, 68, 0.62, 0.7, 1.5, 1.05, 0.2),
                                                  (7, 66, 56, 80, 92, 0.66, 0.76, 1.6, 0.97, 0.12),
                                                  (6, 48, 40, 92, 102, 0.62, 0.7, 1.7, 0.9, 0.08)],
                                   tint=(1.0, 1.0, 0.9), spread=0.03, wmul=0.5, segs=4))
asset("keladi", build_keladi)
asset("shrub_a", build_shrub_a)
asset("shrub_b", build_shrub_b)
asset("bush_a", build_bush_a)
asset("bush_b", build_bush_b)
asset("grass_a", lambda: build_grass("grass_a", 71, 5, 0.42, "left", spread=0.08))
asset("grass_b", lambda: build_grass("grass_b", 72, 6, 0.7, "right", spread=0.1, lo=0.62))
asset("grass_tuft", lambda: build_grass("grass_tuft", 73, 3, 0.3, "left", spread=0.04))
asset("flowers", lambda: build_flowers("flowers", 81, ("left", "right"), n=4, h=0.4))
asset("flowers_white", lambda: build_flowers("flowers_white", 82, ("left",), n=3, h=0.42))
asset("flowers_yellow", lambda: build_flowers("flowers_yellow", 83, ("right",), n=3, h=0.4))
asset("piringan", build_piringan)
asset("frond_fallen", build_frond_fallen)
asset("pile_fronds", build_pile_fronds)
asset("vine_log", build_vine_log)
asset("tree_big", build_tree_big)
asset("coconut", build_coconut)
asset("banana", build_banana)
asset("rock_a", lambda: build_rock("rock_a", 0.5, 3, subdiv=3, grass=2))
asset("rock_b", lambda: build_rock("rock_b", 1.0, 7, extras=((0.62, -0.25, 0.28),), subdiv=3, grass=3))
asset("rock_c", lambda: build_rock("rock_c", 2.0, 13, extras=((-0.55, -0.35, 0.34), (0.6, -0.2, 0.18)), subdiv=3,
                                   grass=4))
asset("cliff_a", build_cliff_a)
asset("stump", build_stump)


# ============================================================ composite test scene
def _import_asset(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(common.MODELS_DIR, name + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.hide_render = True
    roots = [o for o in new if o.parent is None]
    return roots[0]


def _place(src, loc, rot_z=0.0, scale=1.0):
    def dup(o, parent):
        c = o.copy()
        bpy.context.scene.collection.objects.link(c)
        c.hide_render = False
        c.parent = parent
        for ch in o.children:
            dup(ch, c)
        return c
    r = dup(src, None)
    r.location = loc
    r.rotation_mode = "XYZ"  # glTF imports use quaternions: rotation_euler alone would be ignored
    r.rotation_euler = (0.0, 0.0, rot_z)
    r.scale = (scale, scale, scale)
    return r


def _ground_mat(name, tex, tile, fallback):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Specular IOR Level"].default_value = 0.1
    path = os.path.join(common.ROOT, "game", "assets", "textures", "ground", tex + ".png")
    if os.path.exists(path):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0 / tile, 1.0 / tile, 1.0)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(path, check_existing=True)
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = hex_rgba(fallback)
    return m


def scene_test(spacing=6.4, tag="veg_scene", dist=16.0, target=(0.5, 1.0, 0.0), palm_yaw=None):
    """A plantation corner with the exported GLBs at the game camera (45 deg, FOV 35, 16 m), rendered
    small and put side by side with the target screenshot -> blender/previews/veg_scene*.png.
    palm_yaw: None = fully random palm rotation, else max |yaw| in degrees (camera-window use)."""
    from PIL import Image
    reset_scene()
    rnd = random.Random(2024)
    names = ["sawit_3", "sawit_2", "piringan", "fern_a", "fern_b", "keladi", "shrub_a", "shrub_b", "grass_a",
             "grass_b", "grass_tuft", "flowers_white", "flowers_yellow", "rock_a", "rock_b", "pile_fronds",
             "frond_fallen", "vine_log", "bush_a", "bush_b", "tbs", "banana"]
    src = {n: _import_asset(n) for n in names if os.path.exists(os.path.join(common.MODELS_DIR, n + ".glb"))}
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
    gr = bpy.context.view_layer.objects.active
    gr.data.materials.append(_ground_mat("_Grass", "grass", 4.0, "#8aa84a"))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.01))
    path = bpy.context.view_layer.objects.active
    path.scale = (3.4, 40, 1)
    path.rotation_euler = (0, 0, math.radians(-28))
    path.location = (-7.5, 2.0, 0.01)
    path.data.materials.append(_ground_mat("_Dirt", "dirt", 4.0, "#b89c68"))

    def on_path(x, y):
        # distance to the rotated path centre line
        a = math.radians(-28)
        d = Vector((x + 7.5, y - 2.0, 0))
        across = d.dot(Vector((math.cos(a), math.sin(a), 0)))
        return abs(across) < 2.0

    palms = []
    for i in range(-3, 4):
        for j in range(-2, 4):
            x = i * spacing + (spacing * 0.5 if j % 2 else 0.0) + 1.5
            y = j * spacing * 0.866
            if on_path(x, y) or abs(x) > 16 or y > 16:
                continue
            palms.append((x, y))
    for k, (x, y) in enumerate(palms):
        yaw = rnd.uniform(0, 6.28) if palm_yaw is None else math.radians(rnd.uniform(-palm_yaw, palm_yaw))
        _place(src["sawit_3" if k % 5 else "sawit_2"], (x, y, 0), yaw, rnd.uniform(0.92, 1.06))
        _place(src["piringan"], (x, y, 0), yaw)
    small = [("fern_a", 5), ("fern_b", 5), ("keladi", 3), ("shrub_a", 3), ("shrub_b", 6), ("grass_a", 10),
             ("grass_b", 4), ("grass_tuft", 10), ("flowers_white", 4), ("flowers_yellow", 2), ("rock_a", 2),
             ("rock_b", 1), ("bush_a", 1), ("bush_b", 1)]
    bag = [n for n, w in small for _ in range(w) if n in src]
    placed = 0
    tries = 0
    while placed < 320 and tries < 6000:
        tries += 1
        x, y = rnd.uniform(-14, 14), rnd.uniform(-9, 14)
        if any((x - px) ** 2 + (y - py) ** 2 < 1.4 ** 2 for px, py in palms):
            continue
        n = rnd.choice(bag)
        if on_path(x, y) and not n.startswith("grass"):
            continue
        if on_path(x, y) and rnd.random() < 0.8:
            continue
        _place(src[n], (x, y, 0), rnd.uniform(0, 6.28), rnd.uniform(0.85, 1.2))
        placed += 1
    for n, (x, y, r) in (("pile_fronds", (6.0, -2.5, 0.4)), ("frond_fallen", (-1.2, -1.8, 2.0)),
                         ("vine_log", (-3.5, 5.0, 0.3)), ("tbs", (0.2, -0.6, 0.5)), ("tbs", (1.0, -1.2, 2.5)),
                         ("banana", (-11.0, 8.0, 0.0))):
        if n in src:
            _place(src[n], (x, y, 0), r)
    s = bpy.context.scene
    common._setup_render(512, 288, transparent=False, samples=20)
    s.cycles.transparent_max_bounces = 24
    s.cycles.max_bounces = 4
    _game_lights()
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    common.link(cam)
    back = Vector((0.0, -math.cos(math.radians(45)), math.sin(math.radians(45))))
    target = Vector(target)
    cam.location = target + back * dist
    cam.rotation_euler = (-back).to_track_quat("-Z", "Y").to_euler()
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle = math.radians(35.0)
    s.camera = cam
    out = os.path.join(common.PREVIEW_DIR, tag + ".png")
    s.render.filepath = out
    bpy.ops.render.render(write_still=True)
    ref = Image.open(os.path.join(common.ROOT, "art", "reference", "07_target_gameplay.png")).convert("RGB")
    ref = ref.resize((512, 288))
    mine = Image.open(out).convert("RGB")
    both = Image.new("RGB", (512, 576))
    both.paste(mine, (0, 0))
    both.paste(ref, (0, 288))
    both.save(os.path.join(common.PREVIEW_DIR, tag + "_vs_target.png"))
    print(f"[scene] {out}")


MANIFEST = {
    # material -> texture in game/assets/textures/foliage (all alpha-tested at 0.5, glTF alphaMode MASK)
    "M_Frond": ("frond", True, "palm frond: sways above ~1 m"),
    "M_FrondDry": ("frond_dry", True, "dead frond lying on the ground: no sway"),
    "M_CocoFrond": ("frond_coco", True, "coconut frond"),
    "M_Fern": ("fern", True, "fern frond, low"),
    "M_Leaf": ("leaves", True, "broad leaves (keladi, shrub_b, vine_log ivy)"),
    "M_Bush": ("leaves", True, "bushes / shrub_a: leaf-cluster cards + leafy core"),
    "M_Canopy": ("leaves", True, "tree_big canopy (core blobs + cluster cards)"),
    "M_Grass": ("grass", True, "grass clump cards"),
    "M_Flower": ("flowers", True, "flower clump cards"),
    "M_BananaLeaf": ("banana", True, "banana leaf cards (torn-leaf texture)"),
    "M_Piringan": ("piringan", False, "flat ground decal (single-sided), keep above terrain"),
}


def write_manifest():
    import json
    out = {m: {"texture": f"res://assets/textures/foliage/{t}.png", "alpha_scissor": 0.5, "double_sided": d, "note": n}
           for m, (t, d, n) in MANIFEST.items()}
    with open(os.path.join(TEX_DIR, "materials.json"), "w") as f:
        json.dump(out, f, indent=1)


# ============================================================ entry point
def main(argv):
    force_all = "textures" in argv
    tex_force = [a[4:] for a in argv if a.startswith("tex:")]
    for t in tex_force:
        if t not in TEXTURES:
            raise SystemExit(f"unknown texture {t!r}; choose from {list(TEXTURES)}")
    names = [a for a in argv if a not in ("textures", "scene", "scene_close", "scene_win") and not a.startswith("tex:")]
    for n in names:
        if n not in ASSETS:
            raise SystemExit(f"unknown asset {n!r}; choose from {list(ASSETS)}")
    for t in TEXTURES:
        ensure_texture(t, force=force_all or t in tex_force)
    write_manifest()
    if not argv:
        names = list(ASSETS)
    for n in names:
        reset_scene()
        ASSETS[n]()
    if "scene" in argv:
        scene_test()
    if "scene_win" in argv:  # palms turned within +-35 deg: the crown's camera window faces the camera
        scene_test(tag="veg_scene_win", palm_yaw=35.0)
    if "scene_close" in argv:
        scene_test(tag="veg_scene_close", dist=8.0, target=(1.0, -0.5, 0.5))
    if RESULTS:
        print("\n==== vegetation summary ====")
        for n, (tris, budget, rep) in RESULTS.items():
            print(f"{n:15s} {tris:5d}/{budget:<5d} {'OK ' if tris <= budget else 'OVER'} {rep}")


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("-")])

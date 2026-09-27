"""Props, shared modelling helpers and UI icons for Sawit The Franchise.

Run:  python3 blender/props.py               (build every prop + previews + all prop icons)
      python3 blender/props.py crate icons   (only some; "icons" = the icon scenes)
Flags: --no-render  skip previews/icons (fast tri check)
       --debug      extra game-camera views to $SAWIT_DEBUG_DIR and per-part tri breakdown

The generic helpers here (bx, rod, beam, ...) are also imported by buildings.py.
Every asset: root Empty named after the asset, meshes parented to it, front facing -Y,
origin at the ground centre. Reserved materials: M_Glass (windows), M_Lamp (lamp bulb).

v2: every exported mesh carries an active colour attribute `Col` (glTF COLOR_0) = ray-traced
ambient occlusion x cheap weathering (per-part / per-plank shade, dark plank grooves, rust and moss
streaks, a dirt band at the base), see weather_bake(). The game multiplies albedo by it (linear).
New props: karung_tumpuk (sack stack on a pallet), drum (rusty oil drum), pagar_bambu (2 m bamboo
fence along X); pagar is now a rustic post-and-rail fence. Both fences end in HALF posts so tiled
segments share one post. tumpukan_tbs / the truck cargo use bunch(): red cores, round orange
fruitlets, dark spikes (the target's bunches). The vertex colour never goes below COL_FLOOR (0.46,
soft knee) and can carry a second colour per face (w_tint) to stay within 4 materials.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import common as C  # noqa: E402
from common import (reset_scene, mat, add_box, add_cyl, add_sphere, add_ico, mesh_from_data,  # noqa: E402
                    join, bevel_obj, export_glb, render_preview, render_icon, empty, reparent,
                    set_mat, shade_smooth, jitter_verts, count_tris, all_descendants, PALETTE)

# ============================================================ generic helpers
Z = Vector((0, 0, 1))
GLASS_HEX = "#f8e7a2"   # warm pale yellow, the game makes M_Glass glow at night


def glass_mat():
    return mat("M_Glass", GLASS_HEX, roughness=0.35)


def bx(name, size, loc, m, bevel=0.04, seg=2, rotz=0.0, rot=None):
    """Box with (clamped) bevel. size = full extents, loc = centre."""
    o = add_box(name, size, loc, m, rot=rot if rot is not None else (0, 0, rotz))
    if bevel > 0:
        bevel_obj(o, min(bevel, min(size) * 0.45), seg)
    return o


def rod(name, p1, p2, r, m, verts=8, r2=None, smooth=False, bevel=0.0):
    """Cylinder (or cone when r2 is given) from p1 to p2."""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    q = d.normalized().to_track_quat('Z', 'Y')
    return add_cyl(name, r, d.length, loc=(p1 + p2) / 2, material=m, verts=verts, rot=q.to_euler(),
                   radius2=r2, smooth=smooth, bevel=bevel)


def fix_normals(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    return o


def weld(o, dist=1e-4):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(o.data)
    bm.free()
    return o


def smooth_angle(o, deg=35.0):
    """Smooth shading with edges sharper than `deg` kept hard (glTF-safe)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    thr = math.radians(deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) <= thr
        else:
            e.smooth = False
    bm.to_mesh(o.data)
    bm.free()
    return o


def mk_multi(name, verts, faces, mats, fmat, smooth=False):
    """Mesh with several materials; fmat = material index per face."""
    o = mesh_from_data(name, verts, faces)
    for m in mats:
        o.data.materials.append(m)
    for p, mi in zip(o.data.polygons, fmat):
        p.material_index = mi
    if smooth:
        shade_smooth(o)
    return o


def beam(name, p1, p2, w, h, up, m, bevel=0.02, seg=1):
    """Oriented box from p1 to p2; cross-section w (side) x h (along `up`)."""
    p1, p2 = Vector(p1), Vector(p2)
    d = (p2 - p1).normalized()
    u = Vector(up)
    u = (u - d * u.dot(d)).normalized()
    s = d.cross(u).normalized()
    pts = []
    for p in (p1, p2):
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(p + s * (a * w / 2) + u * (b * h / 2))
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    o = mesh_from_data(name, pts, faces, m)
    fix_normals(o)
    if bevel > 0:
        bevel_obj(o, min(bevel, w * 0.45, h * 0.45), seg)
    return o


def fpt(origin, rotz, lp):
    """Point in a local frame at `origin` rotated by rotz (local -Y = outward/front)."""
    c, s = math.cos(rotz), math.sin(rotz)
    x, y, z = lp
    return Vector((origin[0] + c * x - s * y, origin[1] + s * x + c * y, origin[2] + z))


def facing_rot(f):
    """rotz so that local -Y points along horizontal direction f."""
    return math.atan2(f[0], -f[1])


def world_bounds(root):
    """Exact world-space bounds of all mesh vertices under root (evaluated, modifiers applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in all_descendants(root):
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            w = o.matrix_world @ v.co
            mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
            mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
        ev.to_mesh_clear()
    return mn, mx


def center_root(root, keep_y=False, ground=True):
    """Shift the root's children so the XY bounding-box centre is at the origin (and the lowest
    point at z = 0 when `ground`)."""
    bpy.context.view_layer.update()
    mn, mx = world_bounds(root)
    off = Vector((-(mn.x + mx.x) / 2, 0 if keep_y else -(mn.y + mx.y) / 2, -mn.z if ground else 0))
    if off.length < 1e-6:
        return
    for ch in root.children:
        if ch.type == "MESH" and ch.name.endswith("_mesh"):
            ch.data.transform(Matrix.Translation(off))   # merged static mesh keeps an identity node
            ch.data.update()
        else:
            ch.location += off                            # special children keep their own origin
    bpy.context.view_layer.update()


def part_tris(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def finish(root, parts, name, var=0.09):
    """Join parts into '<name>_mesh' under root (prints a tri breakdown with --debug).
    Every part without its own weathering tag gets a small random brightness offset (`var`), so
    planks, posts and boxes of one material read as separate hand-made pieces once baked."""
    part_variation(parts, name, var)
    if DEBUG:
        agg = {}
        for p in parts:
            k = p.name.split(".")[0]
            agg[k] = agg.get(k, 0) + part_tris(p)
        print("[tris]", name, sorted(agg.items(), key=lambda kv: -kv[1]))
    o = join(parts, name + "_mesh")
    o.data.name = name + "_mesh"
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    reparent(o, root)
    return o


def dims(root):
    bpy.context.view_layer.update()
    mn, mx = world_bounds(root)
    d = mx - mn
    return d.x, d.y, d.z


def board_with_uv(name, w, h, d, m, origin, bevel=0.012):
    """Flat sign board: separate object, origin at the centre of its FRONT face (facing -Y),
    front face UV-mapped 0..1 (u → +X, v → +Z) so the game can put text/texture on it."""
    hw, hh = w / 2, h / 2
    vs = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh),
          (-hw, d, -hh), (hw, d, -hh), (hw, d, hh), (-hw, d, hh)]
    faces = [(0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7), (1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = vs[me.loops[li].vertex_index]
            if poly.index == 0:
                uv.data[li].uv = ((x + hw) / w, (z + hh) / h)
            else:
                uv.data[li].uv = (0.02 + 0.02 * (x + hw) / w, 0.02 + 0.02 * (z + hh) / h)
    o = bpy.data.objects.new(name, me)
    C.link(o)
    set_mat(o, m)
    o.location = origin
    if bevel:
        bevel_obj(o, bevel, 1)
    return o


# ============================================================ weathering + baked vertex AO
# Everything static is exported with an active colour attribute `Col` that the game multiplies
# into the albedo: Cycles-baked ambient occlusion (soft, floor ~0.45) times cheap weathering:
#   w_shade (FACE)  brightness offset: per plank / tile / part variation, dark plank grooves
#   w_rust  (FACE)  rust streak amount on corrugated zinc (stronger toward the eave via w_down)
#   w_moss  (FACE)  moss / algae amount (roofs, damp bases)
#   w_down  (POINT) 0 at a roof ridge .. 1 at the eave
# plus a brownish dirt band near the ground. The helper attributes are removed after baking.
#   w_tint  (FACE, FLOAT_VECTOR) colour multiplier stored as (tint - 1), so parts without it (0) are
#           untinted: lets one material carry a second colour (window glass on the cab paint, a green
#           print on cream sacks) and keeps assets within the 4-material budget.
#   w_mossv (POINT) extra moss with a soft per-vertex falloff (moss blobs on clay tiles).
#   w_shadev (POINT) extra per-vertex brightness offset (streaky weathering along planks).
# The brightest channel of the result never drops below COL_FLOOR (contract: never darker than ~0.45).
# the game multiplies these in linear space, so they are much stronger than they look as hex
RUST = np.array((0.55, 0.24, 0.09))
MOSS = np.array((0.45, 0.62, 0.16))
MOSS_V = np.array((0.34, 0.74, 0.22))      # moss blobs on (orange) clay tiles: kill red to read olive-green
DIRT = np.array((0.52, 0.38, 0.24))
COL_FLOOR = 0.46          # > 0.45 even after 8-bit quantisation
KNEE, KNEE_LO = 0.66, 0.15


def soft_floor(v):
    """v >= KNEE unchanged; below it compressed smoothly (slope 1 at KNEE) onto [COL_FLOOR, KNEE],
    reaching the floor at KNEE_LO."""
    g = (KNEE - KNEE_LO) / (KNEE - COL_FLOOR)
    t = np.clip((v - KNEE_LO) / (KNEE - KNEE_LO), 0.0, 1.0)
    return np.where(v >= KNEE, v, COL_FLOOR + (KNEE - COL_FLOOR) * t ** g)
NO_VAR = ("Glass", "Lamp", "Window", "Fruit")
W_ATTRS = ("w_shade", "w_shadev", "w_rust", "w_moss", "w_mossv", "w_down", "w_tint")


def lin_hex(h):
    """sRGB hex -> linear rgb numpy array."""
    return np.array(C.hex_rgba(h)[:3])


def tint_to(o, target_hex, base_hex, faces=None):
    """Make (some) faces of o show `target_hex` although their material colour is `base_hex`
    (via the w_tint vertex-colour multiplier; the ratio is normalised so its brightest channel is 1,
    the remaining brightness difference goes into w_shade)."""
    r = lin_hex(target_hex) / np.maximum(lin_hex(base_hex), 1e-4)
    k = float(r.max())
    me = o.data
    a = me.attributes.get("w_tint") or me.attributes.new("w_tint", "FLOAT_VECTOR", "FACE")
    vals = np.zeros((len(a.data), 3), np.float32)
    a.data.foreach_get("vector", vals.ravel())
    sel = range(len(vals)) if faces is None else faces
    for i in sel:
        vals[i] = r / k - 1.0
    a.data.foreach_set("vector", vals.ravel())
    if k < 0.999:
        sh = _fattr(me, "w_shade", len(me.polygons)) if "w_shade" in me.attributes else np.zeros(len(me.polygons))
        for i in sel:
            sh[i] = k - 1.0
        wattr(o, "w_shade", list(sh))
    return o


def _seed(*vals):
    """Deterministic integer seed from numbers/strings (Python's hash() is salted per run)."""
    s = 0
    for v in vals:
        if isinstance(v, str):
            for ch in v:
                s = (s * 131 + ord(ch)) % 2147483647
        else:
            s = (s * 131 + int(round(float(v) * 1000))) % 2147483647
    return s


def wattr(o, name, values, domain="FACE"):
    """Set a float weathering attribute on mesh object o. `values`: constant, per-element list,
    or fn(element centre / vertex co in object space)."""
    me = o.data
    a = me.attributes.get(name)
    if a is None:
        a = me.attributes.new(name, "FLOAT", domain)
    n = len(a.data)
    if callable(values):
        elems = me.polygons if domain == "FACE" else me.vertices
        vals = [float(values(e.center if domain == "FACE" else e.co)) for e in elems]
    elif isinstance(values, (list, tuple, np.ndarray)):
        vals = [float(v) for v in values]
        assert len(vals) == n, (name, len(vals), n)
    else:
        vals = [float(values)] * n
    a.data.foreach_set("value", vals)
    return o


def part_variation(parts, name, var=0.09):
    rnd = random.Random(_seed(name, len(parts)))
    for p in parts:
        if p.type != "MESH" or var <= 0 or "w_shade" in p.data.attributes:
            continue
        mname = p.data.materials[0].name if len(p.data.materials) and p.data.materials[0] else ""
        if any(w in mname for w in NO_VAR):
            continue
        wattr(p, "w_shade", rnd.uniform(-var * 1.3, var * 0.7))


def _fattr(me, name, n):
    a = me.attributes.get(name)
    if a is None:
        return np.zeros(n, np.float32)
    arr = np.empty(len(a.data), np.float32)
    a.data.foreach_get("value", arr)
    return arr


def _lattr(me, name, fi, vi):
    """Float attribute `name` per loop (FACE or POINT domain; 0 when missing)."""
    a = me.attributes.get(name)
    if a is None:
        return np.zeros(len(fi), np.float32)
    arr = np.empty(len(a.data), np.float32)
    a.data.foreach_get("value", arr)
    if a.domain == "POINT":
        return arr[vi]
    if a.domain == "CORNER":
        return arr
    return arr[fi]


def _hemi_dirs(k, seed=3):
    """Stratified cosine-weighted hemisphere directions around +Z (k rounded to a square)."""
    rnd = random.Random(seed)
    n = max(2, int(round(math.sqrt(k))))
    out = []
    for i in range(n):
        for j in range(n):
            u, v = (i + rnd.random()) / n, (j + rnd.random()) / n
            r, ph = math.sqrt(u), 2 * math.pi * v
            out.append((r * math.cos(ph), r * math.sin(ph), math.sqrt(max(0.0, 1 - u))))
    return out


def vertex_ao(meshes, distance=1.0, samples=36, floor=0.45, gamma=0.8, ground=True, inset=0.05):
    """Ray-traced ambient occlusion into a CORNER colour attribute `Col` (same output as
    common.bake_vertex_ao, but every corner is sampled a few cm inside its own face, so corners
    that are buried in a neighbouring part (kit-bashed boxes, posts through slats) do not darken
    the whole face, while real contacts still get a soft shadow). The ground plane z = 0 occludes
    too when `ground`. Values are remapped to [floor, 1] with `gamma`."""
    from mathutils.bvhtree import BVHTree
    for o in meshes:
        C.apply_modifiers(o)
    allv, allf = [], []
    for o in meshes:
        M = o.matrix_world
        b = len(allv)
        allv += [tuple(M @ v.co) for v in o.data.vertices]
        allf += [tuple(b + i for i in p.vertices) for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(allv, allf)
    H = _hemi_dirs(samples)
    for o in meshes:
        me = o.data
        M = o.matrix_world
        N3 = M.to_3x3().inverted().transposed()
        wco = [M @ v.co for v in me.vertices]
        vals = np.ones(len(me.loops))
        for p in me.polygons:
            n = (N3 @ p.normal).normalized()
            if n.length < 0.5:
                continue
            c = M @ p.center
            t1 = n.orthogonal().normalized()
            t2 = n.cross(t1)
            dirs = [t1 * h[0] + t2 * h[1] + n * h[2] for h in H]
            for li in p.loop_indices:
                v = wco[me.loops[li].vertex_index]
                to_c = c - v
                L = to_c.length
                pos = v + (to_c * (min(inset, 0.35 * L) / L) if L > 1e-6 else Vector()) + n * 0.003
                occ = 0.0
                for d in dirs:
                    t = distance
                    hit = bvh.ray_cast(pos, d, distance)
                    if hit[0] is not None:
                        t = hit[3]
                    if ground and d.z < -1e-4 and pos.z > -1e-3:
                        tg = -pos.z / d.z
                        if tg < t:
                            t = tg
                    if t < distance:
                        occ += 1.0 - (t / distance) ** 2
                ao = 1.0 - occ / len(dirs)
                vals[li] = floor + (1.0 - floor) * max(0.0, ao) ** gamma
        # smooth-shaded faces: average per vertex so the AO is not faceted
        sm = np.zeros(len(me.vertices))
        cnt = np.zeros(len(me.vertices))
        for p in me.polygons:
            if p.use_smooth:
                for li in p.loop_indices:
                    vi = me.loops[li].vertex_index
                    sm[vi] += vals[li]
                    cnt[vi] += 1
        for p in me.polygons:
            if p.use_smooth:
                for li in p.loop_indices:
                    vi = me.loops[li].vertex_index
                    vals[li] = sm[vi] / cnt[vi]
        if "Col" in me.color_attributes:
            me.color_attributes.remove(me.color_attributes["Col"])
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
        buf = np.ones((len(me.loops), 4), np.float32)
        buf[:, :3] = vals[:, None]
        attr.data.foreach_set("color", buf.ravel())


def weather_bake(root, dirt=0.5, dirt_h=0.45, ground=True, distance=1.0, floor=0.45, samples=36):
    """Bake AO into `Col` on every mesh under root, then multiply the weathering tints in."""
    bpy.context.view_layer.update()
    meshes = [o for o in all_descendants(root) if o.type == "MESH" and len(o.data.polygons)]
    vertex_ao(meshes, distance=distance, samples=samples, floor=floor, ground=ground)
    for o in meshes:
        me = o.data
        nl, nf, nv = len(me.loops), len(me.polygons), len(me.vertices)
        col = me.color_attributes["Col"]
        buf = np.empty(nl * 4, np.float32)
        col.data.foreach_get("color", buf)
        ao = buf.reshape(-1, 4)[:, 0].astype(np.float64)
        vi = np.empty(nl, np.int64)
        me.loops.foreach_get("vertex_index", vi)
        lt = np.empty(nf, np.int64)
        me.polygons.foreach_get("loop_total", lt)
        fi = np.repeat(np.arange(nf), lt)
        shade = _lattr(me, "w_shade", fi, vi) + _lattr(me, "w_shadev", fi, vi)
        rust = _lattr(me, "w_rust", fi, vi)
        moss = _lattr(me, "w_moss", fi, vi)
        mossv = _lattr(me, "w_mossv", fi, vi)
        down = _lattr(me, "w_down", fi, vi)
        ta = me.attributes.get("w_tint")
        tint = np.ones((nl, 3))
        if ta is not None:
            tv = np.empty(len(ta.data) * 3, np.float32)
            ta.data.foreach_get("vector", tv)
            tint = 1.0 + tv.reshape(-1, 3)[fi]
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        M = np.array(o.matrix_world)
        wz = (co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 2][vi]
        rgb = np.repeat((ao * (1.0 + shade))[:, None], 3, 1)
        ra = np.clip(rust * (0.3 + 0.7 * down), 0, 1)[:, None]
        rgb *= 1.0 - ra * (1.0 - RUST)
        ma = np.clip(moss * (0.25 + 0.75 * down), 0, 1)[:, None]
        rgb *= 1.0 - ma * (1.0 - MOSS)
        rgb *= 1.0 - np.clip(mossv, 0, 1)[:, None] * (1.0 - MOSS_V)
        if dirt > 0:
            t = np.clip(wz / dirt_h, 0, 1)
            t = t * t * (3 - 2 * t)
            rgb *= 1.0 - (dirt * (1 - t))[:, None] * (1.0 - DIRT)
        rgb *= tint
        # keep the hue but never let the brightest channel drop below COL_FLOOR: a soft knee (C1 at KNEE)
        # instead of a hard clamp, so deep corners keep their gradation instead of flattening at the floor
        m = np.maximum(rgb.max(1), 1e-4)
        rgb *= (soft_floor(m) / m)[:, None]
        out = np.ones((nl, 4), np.float32)
        out[:, :3] = np.clip(rgb, 0.0, 1.0)
        col.data.foreach_set("color", out.ravel())
        for a in W_ATTRS:
            if a in me.attributes:
                me.attributes.remove(me.attributes[a])
        me.color_attributes.active_color = me.color_attributes["Col"]


def preview_vcol(root):
    """After export: make the materials multiply their colour by `Col` so previews / icons show the
    baked AO + weathering the way the game will (never call this before export_glb)."""
    done = set()
    for o in all_descendants(root):
        if o.type != "MESH" or "Col" not in o.data.color_attributes:
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            nt = m.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            if bsdf is None or bsdf.inputs["Base Color"].is_linked:
                continue
            ca = nt.nodes.new("ShaderNodeVertexColor")
            ca.layer_name = "Col"
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            mx.blend_type = "MULTIPLY"
            sock = lambda coll, nm: [s for s in coll if s.name == nm and s.type == "RGBA"][0]
            mx.inputs[0].default_value = 1.0
            sock(mx.inputs, "A").default_value = bsdf.inputs["Base Color"].default_value
            nt.links.new(ca.outputs["Color"], sock(mx.inputs, "B"))
            nt.links.new(sock(mx.outputs, "Result"), bsdf.inputs["Base Color"])


# ============================================================ debug rendering
DEBUG = "--debug" in sys.argv
DEBUG_DIR = os.environ.get("SAWIT_DEBUG_DIR", "/tmp")


def debug_view(root, name, pitch=55.0, yaw=0.0, res=512, figure=True):
    """Game-camera style view written to DEBUG_DIR (not part of the deliverables)."""
    C._setup_render(res, res, transparent=False, samples=16)
    tmp = C._temp_lights()
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.001))
    g = C._active()
    set_mat(g, mat("_M_PreviewGround", "#8fb35c"))
    tmp.append(g)
    if figure:  # a 1.1 m chibi stand-in for scale
        mn, mx = C._bounds(root)
        f = add_cyl("_fig", 0.22, 0.6, loc=(mn.x - 0.5, mn.y + 0.3, 0.3), material=mat("_M_fig", "#e05a8a"))
        h = add_sphere("_head", 0.25, loc=(mn.x - 0.5, mn.y + 0.3, 0.85), material=mat("_M_fig", "#e05a8a"))
        tmp += [f, h]
    tmp.append(C._temp_camera(root, pitch, yaw))
    bpy.context.scene.render.filepath = os.path.join(DEBUG_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)




# ============================================================ shared part makers
def sack(name, m_body, m_band, loc=(0, 0, 0), rotz=0.0, L=0.74, W=0.48, T=0.2, lo=False, tilt=(0.0, 0.0),
         seed=0):
    """Pillow-shaped fertiliser sack lying flat (long axis X), printed band round its middle."""
    rnd = random.Random(seed)
    Lh = L / 2
    b = 0.1
    if lo:
        xs = [-Lh, -0.72 * Lh, -b, b, 0.72 * Lh, Lh]
        around = 8
    else:
        xs = [-Lh, -0.9 * Lh, -0.7 * Lh, -0.42 * Lh, -b, 0.0, b, 0.42 * Lh, 0.7 * Lh, 0.9 * Lh, Lh]
        around = 12
    ne = 2.6
    verts, faces, fm = [], [], []
    for x in xs:
        u = min(1.0, abs(x) / Lh)
        tk = T * max(0.08, (1 - u ** 3.2)) ** 0.55
        wd = W * (0.9 + 0.1 * (1 - u * u))
        for k in range(around):
            th = 2 * math.pi * k / around + math.pi / around
            c, s = math.cos(th), math.sin(th)
            y = wd / 2 * math.copysign(abs(c) ** (2 / ne), c)
            z = tk / 2 * math.copysign(abs(s) ** (2 / ne), s)
            z = max(z, -tk / 2 * 0.72)       # flattened underside
            verts.append(Vector((x + rnd.uniform(-0.006, 0.006), y, z + T * 0.36)))
    for i in range(len(xs) - 1):
        xm = (xs[i] + xs[i + 1]) / 2
        for k in range(around):
            a, bb = i * around + k, i * around + (k + 1) % around
            faces.append((a, bb, bb + around, a + around))
            fm.append(1 if abs(xm) < b else 0)
    last = (len(xs) - 1) * around
    faces.append(tuple(range(around))[::-1])
    faces.append(tuple(range(last, last + around)))
    fm += [0, 0]
    o = mk_multi(name, verts, faces, [m_body, m_band], fm)
    fix_normals(o)
    smooth_angle(o, 50)
    o.rotation_euler = (tilt[0], tilt[1], rotz)
    o.location = loc
    return o


def bunch(name, mats, loc=(0, 0, 0), size=1.0, seed=0, rot=(0, 0, 0), n=10, spikes=10, sides=5, core=-0.05,
          red=0.15, core_tint=None):
    """Palm fruit bunch (TBS) like the target's: a red ovoid core covered in round orange fruitlets with
    near-black spikes (bracts) poking out between them. Cheap (~20 + 5n + 3*spikes tris): each fruitlet is
    a low `sides`-sided smooth-shaded dome whose rim sits just inside the core (reads as a round bump),
    each spike a thin 3-sided cone. Fruitlets cover the top / sides (bunches lie on the ground or in a
    heap, their undersides are never seen). mats = (red, orange, dark): core + a few (`red`) fruitlets in
    red, the rest orange. core_tint = (target_hex, material_hex) tints the core through the vertex colour
    instead (when red and orange are one material). Origin at the bottom of the bunch."""
    rnd = random.Random(seed)
    rx, rz = 0.21 * size, 0.25 * size
    GOLD = math.radians(137.508)

    def surf(c):
        egg = 1.0 - 0.12 * c.z
        return Vector((c.x * rx * egg, c.y * rx * egg, c.z * rz))

    def normal(c):
        egg = 1.0 - 0.12 * c.z
        return Vector((c.x / (rx * egg), c.y / (rx * egg), c.z / rz)).normalized()

    def frame(D):
        U = D.cross(Vector((0.31, 0.83, 0.47))).normalized()
        return U, D.cross(U)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    vs = []
    for v in bm.verts:
        c = v.co.normalized()
        vs.append(surf(c) * (0.94 + rnd.uniform(-0.03, 0.03)))
    fs = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    verts, faces, fmat = list(vs), list(fs), [0] * len(fs)
    shade = [core] * len(fs)
    # fruitlets: golden-spiral over the upper ~80 % of the ovoid
    for k in range(n):
        zc = 0.95 - 1.55 * (k + 0.5) / n + rnd.uniform(-0.04, 0.04)
        ang = k * GOLD + rnd.uniform(-0.2, 0.2)
        rc = math.sqrt(max(0.0, 1 - zc * zc))
        c = Vector((rc * math.cos(ang), rc * math.sin(ang), zc))
        D = normal(c)
        U, V = frame(D)
        rw = 0.113 * size * rnd.uniform(0.88, 1.06)
        base = surf(c) * 0.92 - D * 0.02 * size
        ph = rnd.uniform(0, 6.28)
        b0 = len(verts)
        verts += [base + (U * math.cos(q) + V * math.sin(q)) * rw
                  for q in (ph + 2 * math.pi * s_ / sides for s_ in range(sides))]
        verts.append(base + D * rw * rnd.uniform(0.85, 1.05))
        body = 0 if rnd.random() < red else 1
        fsh = rnd.uniform(-0.08, 0.08)
        for s_ in range(sides):
            faces.append((b0 + s_, b0 + (s_ + 1) % sides, b0 + sides))
            fmat.append(body)
            shade.append(fsh)
    # spikes: thin dark cones between the fruitlets, leaning up and out
    for k in range(spikes):
        zc = 0.9 - 1.5 * (k + 0.5) / spikes + rnd.uniform(-0.05, 0.05)
        ang = (k + 0.5) * GOLD * 1.618 + rnd.uniform(-0.3, 0.3)
        rc = math.sqrt(max(0.0, 1 - zc * zc))
        c = Vector((rc * math.cos(ang), rc * math.sin(ang), zc))
        D = (normal(c) + Vector((0, 0, 0.3))).normalized()
        U, V = frame(D)
        r0 = 0.03 * size
        base = surf(c) * 0.93
        ph = rnd.uniform(0, 6.28)
        b0 = len(verts)
        verts += [base + (U * math.cos(q) + V * math.sin(q)) * r0 for q in (ph, ph + 2.09, ph + 4.19)]
        verts.append(base + D * 0.15 * size * rnd.uniform(0.85, 1.15))
        for s_ in range(3):
            faces.append((b0 + s_, b0 + (s_ + 1) % 3, b0 + 3))
            fmat.append(2)
            shade.append(0.0)
    o = mk_multi(name, verts, faces, list(mats), fmat)
    wattr(o, "w_shade", shade)
    if core_tint:
        tint_to(o, core_tint[0], core_tint[1], faces=range(len(fs)))
    fix_normals(o)
    shade_smooth(o)
    o.location = Vector(loc) + Vector((0, 0, rz * 0.85))
    o.rotation_euler = rot
    return o


def polybag(P, m_bag, m_leaf, loc, seed=0, size=1.0):
    """Oil-palm seedling in a black polybag: bag + three arching leaf blades."""
    rnd = random.Random(seed)
    x, y, z = loc
    h = 0.26 * size
    P.append(add_cyl("polybag", 0.13 * size, h, loc=(x, y, z + h / 2), material=m_bag, verts=7, radius2=0.115 * size))
    for k in range(3):
        a = rnd.uniform(0, 2 * math.pi / 3) + k * 2 * math.pi / 3
        L = rnd.uniform(0.34, 0.44) * size
        tip = Vector((x + math.cos(a) * L * 0.75, y + math.sin(a) * L * 0.75, z + h + L * 0.62))
        P.append(rod("leaf", (x, y, z + h - 0.02), tip, 0.045 * size, m_leaf, verts=3, r2=0.004))


def plastic_stool(P, m, x, y, s=1.0):
    P.append(add_cyl("stool_leg", 0.17 * s, 0.4 * s, loc=(x, y, 0.2 * s), material=m, verts=8, radius2=0.13 * s))
    P.append(add_cyl("stool_top", 0.19 * s, 0.06 * s, loc=(x, y, 0.43 * s), material=m, verts=10))


def plastic_chair(P, m, x, y, rotz=0.0):
    """Stackable monobloc chair, faces -Y in its local frame."""
    fr = lambda lx, ly, lz: fpt((x, y, 0), rotz, (lx, ly, lz))
    P.append(bx("chair_seat", (0.46, 0.44, 0.06), fr(0, 0, 0.44), m, 0.03, 1, rotz))
    P.append(bx("chair_back", (0.46, 0.06, 0.4), fr(0, 0.23, 0.7), m, 0.03, 1, rot=(math.radians(-8), 0, rotz)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(bx("chair_leg", (0.06, 0.06, 0.44), fr(sx * 0.19, sy * 0.18, 0.22), m, 0, rotz=rotz))
        P.append(bx("chair_arm", (0.05, 0.42, 0.05), fr(sx * 0.23, 0.0, 0.62), m, 0.015, 1, rotz))


def crate_parts(P, m_wood, m_dark, loc=(0, 0, 0), size=(0.6, 0.45, 0.4), rotz=0.0, lo=False):
    """Slatted wooden crate: dark core + light slats + corner posts (lo=True: no bevels, ~84 tris;
    the core is tagged darker so one wood material is enough). Slats and posts get streaky per-vertex
    weathering (w_shadev), the full crate a lid of three planks with dark gaps."""
    x, y, z = loc
    sx, sy, sz = size
    b1, b2 = (0.0, 0.0) if lo else (0.015, 0.015)
    rnd = random.Random(_seed("crate", x, y, z, rotz))
    fr = lambda lx, ly, lz: fpt((x, y, z), rotz, (lx, ly, lz))

    def streak(o, lo_=-0.16, hi_=0.06):
        return wattr(o, "w_shadev", [rnd.uniform(lo_, hi_) for _ in o.data.vertices], "POINT")
    core = bx("crate_core", (sx - 0.04, sy - 0.04, sz - 0.02), fr(0, 0, sz / 2), m_dark, 0, rotz=rotz)
    if lo or m_dark is m_wood:
        wattr(core, "w_shade", -0.45)
    P.append(core)
    for k, zz in enumerate((0.25, 0.75)):
        P.append(streak(bx("crate_slat", (sx - 0.02, sy - 0.02, sz * 0.3), fr(0, 0, sz * zz), m_wood, b1, 1, rotz)))
    for ax in (-1, 1):
        for ay in (-1, 1):
            P.append(streak(bx("crate_post", (0.07, 0.07, sz), fr(ax * (sx / 2 - 0.035), ay * (sy / 2 - 0.035), sz / 2),
                               m_wood, b2, 1, rotz), -0.2, 0.02))
    if not lo:
        w = (sx - 0.1) / 3
        for i in range(3):
            P.append(streak(bx("crate_top", (w - 0.018, sy - 0.1, 0.03), fr(-(sx - 0.1) / 2 + w * (i + 0.5), 0, sz - 0.02),
                               m_wood, 0, rotz=rotz)))


def prop_root(name):
    return empty(name)


def gold_mat(name="M_Gold", col="#f2c14e", metallic=0.55, rough=0.35):
    m = mat(name, col, roughness=rough)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = metallic
    return m


# ============================================================ props
def build_crate():
    name = "crate"
    root = prop_root(name)
    P = []
    crate_parts(P, mat("M_Wood", "wood_light"), mat("M_WoodDark", "wood_dark"), size=(0.62, 0.46, 0.42))
    finish(root, P, name)
    return root


def build_karung_pupuk():
    name = "karung_pupuk"
    root = prop_root(name)
    P = [sack("sack", mat("M_Sack", "white"), mat("M_Print", "green_sign"), rotz=0.0, seed=2)]
    finish(root, P, name)
    center_root(root)
    return root


def build_jerigen():
    """Yellow jerry can of cooking oil: chunky bevelled body, top grip, red cap, white label."""
    name = "jerigen"
    root = prop_root(name)
    M = dict(pl=mat("M_Plastic", "#f2c14e"), cap=mat("M_Cap", "red"), lab=mat("M_Label", "white"))
    P = []
    w, d, h = 0.34, 0.2, 0.42
    P.append(bx("body", (w, d, h), (0, 0, h / 2), M['pl'], 0.05, 2))
    P.append(bx("shoulder", (w - 0.06, d - 0.04, 0.05), (0, 0, h + 0.015), M['pl'], 0))
    # grip: two posts + bar along X at the back half
    for x in (-0.1, 0.06):
        P.append(bx("grip_post", (0.04, 0.06, 0.08), (x, 0.03, h + 0.07), M['pl'], 0.012, 1))
    P.append(bx("grip", (0.22, 0.06, 0.045), (-0.02, 0.03, h + 0.12), M['pl'], 0.018, 1))
    # spout + cap at the front-right corner
    P.append(add_cyl("neck", 0.035, 0.05, loc=(0.11, -0.03, h + 0.05), material=M['pl'], verts=8))
    P.append(add_cyl("cap", 0.045, 0.05, loc=(0.11, -0.03, h + 0.095), material=M['cap'], verts=8))
    # label on the front face + moulded ribs on the sides
    P.append(bx("label", (0.22, 0.012, 0.2), (0, -d / 2 - 0.004, 0.2), M['lab'], 0.006, 1))
    P.append(bx("label_band", (0.22, 0.014, 0.05), (0, -d / 2 - 0.006, 0.2), M['cap'], 0))
    for sx in (-1, 1):
        P.append(bx("rib", (0.012, d * 0.7, 0.28), (sx * (w / 2 + 0.003), 0, 0.2), M['pl'], 0))
    finish(root, P, name)
    center_root(root)
    return root


def cut_half(o, keep):
    """Apply o's modifiers, cut it by its local YZ plane and keep the half on the `keep` side
    (+1 = +X, -1 = -X), capping the cut (a half post for tiling fence segments)."""
    C.apply_modifiers(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, 0), plane_no=(1, 0, 0),
                                 clear_inner=keep > 0, clear_outer=keep < 0)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if cut:
        bmesh.ops.edgenet_fill(bm, edges=cut)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


def picket(name, x, y, w, h, t, m, z0=0.0):
    """Pointed fence picket (pentagon prism) facing -Y."""
    prof = [(-w / 2, 0), (w / 2, 0), (w / 2, h - w / 2), (0, h), (-w / 2, h - w / 2)]
    vs = [(x + px, y - t / 2, z0 + pz) for px, pz in prof] + [(x + px, y + t / 2, z0 + pz) for px, pz in prof]
    fs = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)] + [(i, 5 + i, 5 + (i + 1) % 5, (i + 1) % 5) for i in range(5)]
    o = mesh_from_data(name, vs, fs, m)
    fix_normals(o)
    return o


def build_pagar():
    """Rustic post-and-rail wooden fence segment (like the target's), 2 m along X. Segments tile: the
    middle post is whole, the end posts are HALF posts (x = +-1 .. +-0.925), so two neighbouring
    segments build one full post at their joint (no doubled, z-fighting post) and the open end of a
    run still has a post. Rails are nailed to the front (-Y) of the posts, one rail board per 1 m bay
    (ending on the post centres, so neighbours never overlap), slightly skewed so a long fence looks
    hand-built."""
    name = "pagar"
    root = prop_root(name)
    M = dict(w=mat("M_Wood", "#94724c"), d=mat("M_WoodDark", "#6f5439"))
    P = []
    rnd = random.Random(6)
    pw, ph = 0.15, 1.08
    P.append(bx("post", (pw, pw, ph), (0.0, 0.0, ph / 2), M['d'], 0.03, 1))
    for sx in (-1, 1):   # half posts, one fixed shade so the two halves of a joint post match
        o = bx("post_end", (pw, pw, ph), (sx * 1.0, 0.0, ph / 2), M['d'], 0.03, 1)
        wattr(o, "w_shade", -0.04)
        P.append(cut_half(o, -sx))
    for p in P:
        if p.name.startswith("post") and not p.name.startswith("post_end"):
            wattr(p, "w_shade", -0.04)
    for z in (0.5, 0.88):
        for xa, xb in ((-1.0, -0.004), (0.004, 1.0)):
            dz = rnd.uniform(-0.025, 0.025)
            P.append(beam("rail", (xa, -0.105, z - dz), (xb, -0.105, z + dz), 0.06, 0.13, Z, M['w'], 0.015))
    finish(root, P, name)
    return root


def build_papan():
    """Signpost: one post with a blank cream board facing -Y. The board is child `Board`
    (origin = centre of its front face, front face UV 0..1) so text can be put on it."""
    name = "papan"
    root = prop_root(name)
    M = dict(w=mat("M_Wood", "wood"), b=mat("M_Board", "cream"))
    P = []
    P.append(bx("post", (0.12, 0.12, 1.55), (0, 0.04, 0.775), M['w'], 0.025, 1))
    P.append(bx("frame", (1.0, 0.06, 0.62), (0, -0.04, 1.2), M['w'], 0.03, 2))
    P.append(beam("cap", (-0.58, -0.04, 1.55), (0.58, -0.04, 1.55), 0.2, 0.05, Z, M['w'], 0.02))
    P.append(bx("mound", (0.3, 0.3, 0.06), (0, 0.04, 0.03), M['w'], 0.02, 1))
    finish(root, P, name)
    b = board_with_uv("Board", 0.9, 0.52, 0.03, M['b'], (0, -0.1, 1.2), bevel=0.008)
    b.parent = root
    return root


def build_bangku():
    """Wooden bench with a low backrest (seat front toward -Y)."""
    name = "bangku"
    root = prop_root(name)
    M = dict(w=mat("M_Wood", "wood_light"), d=mat("M_WoodDark", "wood"))
    P = []
    L = 1.4
    for y in (-0.1, 0.1):
        P.append(bx("seat", (L, 0.18, 0.06), (0, y, 0.45), M['w'], 0.025, 1))
    for sx in (-1, 1):
        x = sx * (L / 2 - 0.16)
        P.append(bx("leg_f", (0.08, 0.08, 0.42), (x, -0.13, 0.21), M['d'], 0.02, 1))
        P.append(bx("leg_b", (0.08, 0.08, 0.86), (x, 0.17, 0.43), M['d'], 0.02, 1, rot=(math.radians(-6), 0, 0)))
        P.append(bx("side_rail", (0.06, 0.36, 0.07), (x, 0.02, 0.36), M['d'], 0.015, 1))
    P.append(bx("back", (L, 0.05, 0.16), (0, 0.21, 0.76), M['w'], 0.02, 1, rot=(math.radians(-6), 0, 0)))
    P.append(bx("stretcher", (L - 0.32, 0.05, 0.06), (0, 0.0, 0.14), M['d'], 0.015, 1))
    finish(root, P, name)
    center_root(root)
    return root


def tray_mesh(name, top, bot, depth, z0, t, m_out, m_in):
    """Open tapered tub (wheelbarrow tray): outer shell, inner shell, rim. top/bot = (half x, half y front, half y back)."""
    def rect(hx, yf, yb, z):
        return [(-hx, -yf, z), (hx, -yf, z), (hx, yb, z), (-hx, yb, z)]
    ot = rect(top[0], top[1], top[2], z0 + depth)
    ob = rect(bot[0], bot[1], bot[2], z0)
    it = rect(top[0] - t, top[1] - t, top[2] - t, z0 + depth)
    ib = rect(bot[0] - t, bot[1] - t, bot[2] - t, z0 + t)
    vs = ot + ob + it + ib
    fs, fm = [], []
    for i in range(4):
        j = (i + 1) % 4
        fs.append((4 + i, 4 + j, j, i)); fm.append(0)           # outer walls
        fs.append((i, j, 8 + j, 8 + i)); fm.append(0)           # rim
        fs.append((8 + i, 8 + j, 12 + j, 12 + i)); fm.append(1)  # inner walls
    fs.append((7, 6, 5, 4)); fm.append(0)
    fs.append((12, 13, 14, 15)); fm.append(1)
    o = mk_multi(name, vs, fs, [m_out, m_in], fm)
    fix_normals(o)
    bevel_obj(o, 0.02, 1)
    return o


def gerobak_parts(P, M):
    # tray: deep tapered tub, front (-Y) slanted forward
    P.append(tray_mesh("tray", (0.36, 0.55, 0.32), (0.22, 0.22, 0.2), 0.34, 0.42, 0.03, M['tray'], M['tray']))
    # wheel at the front
    P.append(add_cyl("tyre", 0.2, 0.1, loc=(0, -0.62, 0.2), material=M['tyre'], verts=12, rot=(0, math.pi / 2, 0),
                     bevel=0.03))
    P.append(add_cyl("hub", 0.08, 0.13, loc=(0, -0.62, 0.2), material=M['metal'], verts=8, rot=(0, math.pi / 2, 0)))
    for sx in (-1, 1):
        P.append(beam("fork", (sx * 0.08, -0.62, 0.2), (sx * 0.17, -0.25, 0.46), 0.03, 0.03, Z, M['metal'], 0))
        # handles run back (+Y), under the tray
        P.append(beam("handle", (sx * 0.14, -0.45, 0.4), (sx * 0.27, 0.8, 0.6), 0.05, 0.05, Z, M['wood'], 0.015))
        P.append(add_cyl("grip", 0.037, 0.2, loc=(sx * 0.272, 0.76, 0.595), material=M['tyre'], verts=6,
                         rot=(math.radians(-80), 0, 0)))
        P.append(beam("leg", (sx * 0.2, 0.28, 0.5), (sx * 0.22, 0.4, 0.0), 0.035, 0.035, (0, 1, 0), M['metal'], 0))
        P.append(bx("foot", (0.05, 0.14, 0.03), (sx * 0.22, 0.42, 0.015), M['metal'], 0))


def build_gerobak():
    """Wheelbarrow (gerobak sorong): blue tray, wheel at the front (-Y), wooden handles."""
    name = "gerobak"
    root = prop_root(name)
    M = dict(tray=mat("M_Tray", "blue"), wood=mat("M_Wood", "wood"), tyre=mat("M_Tyre", "black"),
             metal=mat("M_Metal", "metal_dark"))
    P = []
    gerobak_parts(P, M)
    finish(root, P, name)
    center_root(root)
    return root


def lathe(name, prof, n, m, cap_top=False, cap_bot=False, loc=(0, 0, 0)):
    """Revolve profile [(r, z), ...] around Z with n segments."""
    vs, fs = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        for r, z in prof:
            vs.append((loc[0] + r * math.cos(a), loc[1] + r * math.sin(a), loc[2] + z))
    np_ = len(prof)
    for k in range(n):
        k2 = (k + 1) % n
        for i in range(np_ - 1):
            fs.append((k * np_ + i, k2 * np_ + i, k2 * np_ + i + 1, k * np_ + i + 1))
    if cap_top:
        fs.append(tuple(k * np_ + np_ - 1 for k in range(n)))
    if cap_bot:
        fs.append(tuple(k * np_ for k in range(n))[::-1])
    o = mesh_from_data(name, vs, fs, m)
    fix_normals(o) if (cap_top and cap_bot) else None
    return o


def build_sumur():
    """Village well: round stone wall with coursed grooves, water inside, two posts with a crank
    roller, a little clay-tile roof and a bucket on a rope."""
    name = "sumur"
    root = prop_root(name)
    M = dict(stone=mat("M_Stone", "rock"), wood=mat("M_Wood", "wood"), roof=mat("M_Roof", "roof"),
             water=mat("M_Water", "#3f8f99", roughness=0.3))
    P = []
    R, r, H = 0.62, 0.46, 0.78
    prof = [(R + 0.04, 0.0), (R, 0.08), (R, 0.24), (R - 0.03, 0.27), (R, 0.3), (R, 0.47), (R - 0.03, 0.5), (R, 0.53),
            (R, H - 0.06), (R + 0.05, H - 0.03), (R + 0.05, H + 0.03), (R - 0.02, H + 0.07), (r, H + 0.07), (r, H - 0.05),
            (r, 0.35)]
    o = lathe("wall", prof, 12, M['stone'])
    smooth_angle(o, 40)
    P.append(o)
    P.append(add_cyl("water", r + 0.01, 0.02, loc=(0, 0, 0.42), material=M['water'], verts=12))
    for sx in (-1, 1):
        P.append(bx("post", (0.1, 0.12, 1.75), (sx * (R + 0.02), 0, 0.875), M['wood'], 0.025, 1))
    P.append(rod("roller", (-R - 0.08, 0, 1.3), (R + 0.08, 0, 1.3), 0.07, M['wood'], 8))
    P.append(bx("crank", (0.04, 0.05, 0.2), (R + 0.12, 0, 1.22), M['wood'], 0.01, 1))
    P.append(rod("crank_h", (R + 0.12, 0, 1.13), (R + 0.24, 0, 1.13), 0.025, M['wood'], 6))
    P.append(add_cyl("rope_coil", 0.085, 0.3, loc=(0, 0, 1.3), material=M['stone'], verts=8, rot=(0, math.pi / 2, 0)))
    P.append(rod("rope", (0.05, 0, 1.24), (0.05, 0, 0.98), 0.012, M['stone'], 4))
    P.append(add_cyl("bucket", 0.12, 0.2, loc=(0.05, 0, 0.88), material=M['wood'], verts=8, radius2=0.14))
    P.append(bx("bucket_rim", (0.24, 0.02, 0.02), (0.05, 0, 0.99), M['stone'], 0))
    # little gable roof (ridge along X)
    pitch = math.radians(35)
    c, s_ = math.cos(pitch), math.sin(pitch)
    zr, sl = 1.97, 0.72
    for sy in (-1, 1):
        P.append(bx("roof", (1.6, sl, 0.07), (0, sy * sl / 2 * c, zr - sl / 2 * s_ - 0.02), M['roof'], 0.03, 1,
                    rot=(-sy * pitch, 0, 0)))
        for k in range(3):
            d = 0.16 + k * 0.24
            P.append(bx("tile_row", (1.62, 0.05, 0.04), (0, sy * d * c, zr - d * s_ + 0.03), M['roof'], 0.0,
                        rot=(-sy * pitch, 0, 0)))
    P.append(rod("ridge", (-0.85, 0, 1.99), (0.85, 0, 1.99), 0.07, M['roof'], 6))
    finish(root, P, name)
    center_root(root)
    return root


def build_lampu():
    """Village street lamp ~3 m: stone base, green pole, curved arm toward -Y, hanging lantern whose
    glass panes use M_Lamp (lit at night)."""
    name = "lampu"
    root = prop_root(name)
    M = dict(pole=mat("M_Pole", "#3f5b4f"), lamp=mat("M_Lamp", "#fff1b0", roughness=0.4),
             base=mat("M_Base", "rock"))
    P = []
    P.append(add_cyl("base", 0.24, 0.34, loc=(0, 0, 0.17), material=M['base'], verts=8, radius2=0.19, bevel=0.03))
    P.append(add_cyl("pole", 0.085, 2.7, loc=(0, 0, 0.34 + 1.35), material=M['pole'], verts=8, radius2=0.065))
    P.append(add_cyl("collar", 0.115, 0.1, loc=(0, 0, 0.42), material=M['pole'], verts=8))
    P.append(add_cyl("collar", 0.1, 0.08, loc=(0, 0, 1.4), material=M['pole'], verts=8))
    pts = [(0, 0, 2.95), (0, -0.2, 3.1), (0, -0.48, 3.12), (0, -0.66, 3.04)]
    for a_, b_ in zip(pts, pts[1:]):
        P.append(rod("arm", a_, b_, 0.05, M['pole'], 6))
    P.append(add_sphere("knob", 0.09, loc=(0, 0, 3.05), material=M['pole'], segments=8, rings=4))
    # hanging lantern: glowing panes (M_Lamp) under a little pyramid cap
    lx, ly, lz = 0.0, -0.66, 2.72
    P.append(rod("hanger", (lx, ly, 3.04), (lx, ly, lz + 0.26), 0.02, M['pole'], 4))
    P.append(bx("lantern_glass", (0.26, 0.26, 0.34), (lx, ly, lz), M['lamp'], 0.02, 1))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(bx("lantern_post", (0.04, 0.04, 0.38), (lx + sx * 0.13, ly + sy * 0.13, lz), M['pole'], 0))
    P.append(bx("lantern_base", (0.32, 0.32, 0.05), (lx, ly, lz - 0.19), M['pole'], 0.015, 1))
    P.append(add_cyl("lantern_cap", 0.28, 0.16, loc=(lx, ly, lz + 0.25), material=M['pole'], verts=4, radius2=0.03,
                     rot=(0, 0, math.pi / 4)))
    finish(root, P, name)
    center_root(root)
    return root


def build_tumpukan_tbs():
    """Heap of 6 harvested palm fruit bunches (~1.2 m wide): five on the ground, spread so each outline
    reads from the game camera, one on top. Orange fruitlets on red cores with dark spikes (the target's
    bunches); <= 600 tris."""
    name = "tumpukan_tbs"
    root = prop_root(name)
    mats = (mat("M_Fruit", "#d24c26", roughness=0.55), mat("M_FruitOrange", "#ec7430", roughness=0.5),
            mat("M_FruitDark", "#3a1f18", roughness=0.5))
    P = []
    rnd = random.Random(5)
    spots = [(-0.41, -0.18, 0), (0.07, -0.36, 0), (0.46, 0.03, 0), (-0.27, 0.32, 0), (0.2, 0.35, 0),
             (-0.04, 0.0, 0.2)]
    for i, (x, y, z) in enumerate(spots):
        top = z > 0
        P.append(bunch("tbs", mats, loc=(x, y, z), size=rnd.uniform(0.98, 1.08) * (1.05 if top else 1.0), seed=i + 3,
                       rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))))
    finish(root, P, name)
    center_root(root)
    return root


def build_tenda():
    """Sad little blue-tarp tent for displaced villagers: saggy A-frame tarp on crooked sticks,
    a grey patch, a guy rope and a dented cooking pot. Opening faces -Y."""
    name = "tenda"
    root = prop_root(name)
    M = dict(tarp=mat("M_Tarp", "#4a7fbf"), wood=mat("M_Wood", "wood"), patch=mat("M_Patch", "#9aa08a"),
             pot=mat("M_Pot", "metal_dark"))
    P = []
    L, hw, H = 2.0, 0.85, 1.05
    nl, nw = 5, 3
    verts, faces = [], []
    rnd = random.Random(4)
    for i in range(nl + 1):
        y = -L / 2 + L * i / nl
        ridge = H - 0.12 * math.sin(math.pi * i / nl) - (0.1 if i == nl else 0.0)   # sagging ridge
        for j in range(-nw, nw + 1):
            u = j / nw
            x = hw * u * (1.0 + 0.08 * (i == 0))
            z = ridge * (1 - abs(u)) + 0.02
            z -= 0.08 * math.sin(math.pi * abs(u)) * (1.0 + 0.6 * (j < 0))       # belly between ridge and ground
            verts.append((x + rnd.uniform(-0.02, 0.02), y + rnd.uniform(-0.02, 0.02), max(0.0, z)))
    row = 2 * nw + 1
    for i in range(nl):
        for j in range(row - 1):
            a = i * row + j
            faces.append((a, a + 1, a + row + 1, a + row))
    top = mesh_from_data("tarp", verts, faces, M['tarp'])
    fix_normals(top)
    # make sure normals point outward/up
    if sum(p.normal.z for p in top.data.polygons) < 0:
        for p in top.data.polygons:
            p.flip()
    shade_smooth(top)
    P.append(top)
    under = mesh_from_data("tarp_in", [(x, y, z - 0.015) for x, y, z in verts], [f[::-1] for f in faces], M['tarp'])
    shade_smooth(under)
    P.append(under)
    # patch on the right slope
    P.append(bx("patch", (0.36, 0.4, 0.02), (0.42, 0.25, H * 0.52), M['patch'], 0.008, 1,
                rot=(0, -math.atan2(H, hw), 0.1)))
    # crooked sticks + ridge pole
    P.append(rod("stick", (0.03, -L / 2 - 0.02, 0), (0.0, -L / 2, H + 0.1), 0.035, M['wood'], 6))
    P.append(rod("stick", (-0.04, L / 2 + 0.02, 0), (0.05, L / 2, H - 0.02), 0.035, M['wood'], 6))
    P.append(rod("ridge", (0.0, -L / 2 - 0.05, H + 0.04), (0.05, L / 2 + 0.05, H - 0.06), 0.03, M['wood'], 6))
    # guy rope to a peg, and a dented pot on three stones
    P.append(rod("rope", (0.0, -L / 2, H + 0.05), (0.0, -L / 2 - 0.55, 0.05), 0.01, M['patch'], 4))
    P.append(rod("peg", (0.0, -L / 2 - 0.55, 0.0), (0.02, -L / 2 - 0.58, 0.14), 0.02, M['wood'], 4))
    P.append(add_cyl("pot", 0.13, 0.14, loc=(0.75, -1.1, 0.17), material=M['pot'], verts=8, radius2=0.11))
    for k in range(3):
        a = k * 2.1
        P.append(add_ico("stone", 0.07, loc=(0.75 + 0.14 * math.cos(a), -1.1 + 0.14 * math.sin(a), 0.05),
                         material=M['patch'], subdiv=1))
    P.append(bx("mat", (0.9, 0.6, 0.02), (-0.05, 0.1, 0.01), M['patch'], 0))
    finish(root, P, name)
    center_root(root)
    return root


def build_spanduk():
    """Protest banner: blank white cloth ~2.5 x 0.8 m between two bamboo poles (faces -Y).
    The cloth is child `Cloth` (origin at its centre, front UV 0..1)."""
    name = "spanduk"
    root = prop_root(name)
    M = dict(bam=mat("M_Bamboo", "#c8a15e"), cloth=mat("M_Cloth", "white"))
    P = []
    W, Hc, zc = 2.5, 0.8, 1.55
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.06)
        P.append(add_cyl("pole", 0.045, 2.25, loc=(x, 0, 1.125), material=M['bam'], verts=6))
        for z in (0.7, 1.4):
            P.append(add_cyl("node", 0.056, 0.04, loc=(x, 0, z), material=M['bam'], verts=6))
        for z in (zc - Hc / 2 + 0.05, zc + Hc / 2 - 0.05):
            P.append(rod("tie", (x, 0, z), (sx * W / 2, 0, z), 0.018, M['bam'], 4))
    finish(root, P, name)
    # cloth: gently waving grid, double sided, UVs 0..1 on the front
    nx, nz = 8, 2
    vs, uvs = [], []
    for j in range(nz + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / nz
            x = -W / 2 + W * u
            z = -Hc / 2 + Hc * v - 0.04 * math.sin(math.pi * u) * (1 - v)
            y = 0.035 * math.sin(u * math.pi * 3)
            vs.append((x, y, z))
            uvs.append((u, v))
    fs = []
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            fs.append((a, a + 1, a + nx + 2, a + nx + 1))
    n0 = len(vs)
    vs2 = vs + [(x, y + 0.008, z) for x, y, z in vs]
    fs2 = fs + [tuple(n0 + k for k in f[::-1]) for f in fs]
    me = bpy.data.meshes.new("Cloth")
    me.from_pydata(vs2, [], fs2)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uu, vv = uvs[vi % n0]
            uv.data[li].uv = (uu if vi < n0 else 1 - uu, vv)
    cloth = bpy.data.objects.new("Cloth", me)
    C.link(cloth)
    set_mat(cloth, M['cloth'])
    shade_smooth(cloth)
    cloth.location = (0, 0, zc)
    cloth.parent = root
    return root


def build_karung_tumpuk():
    """Stack of fertiliser sacks on a wooden pallet: 3 + 2 layers, one jute sack for variety
    (~1.25 x 0.85 x 0.5 m)."""
    name = "karung_tumpuk"
    root = prop_root(name)
    M = dict(sack=mat("M_Sack", "#ece6d6"), band=mat("M_Print", "#4a8a4c"), jute=mat("M_Jute", "#b48d5c"),
             wood=mat("M_Wood", "#9a7a52"))
    P = []
    # pallet: 4 deck boards on 3 runners
    for i in range(4):
        P.append(bx("deck", (1.25, 0.18, 0.035), (0, -0.33 + i * 0.22, 0.1175), M['wood'], 0))
    for x in (-0.54, 0.0, 0.54):
        P.append(bx("runner", (0.12, 0.84, 0.1), (x, 0, 0.05), M['wood'], 0))
    z = 0.135
    L, W, T = 0.62, 0.4, 0.22
    for i, x in enumerate((-0.41, 0.0, 0.41)):                       # layer 1: long axis Y
        body = M['jute'] if i == 2 else M['sack']
        P.append(sack("sack", body, M['band'] if i != 2 else M['jute'], loc=(x, 0.0, z), rotz=math.pi / 2 + 0.05 * (i - 1),
                      L=L, W=W, T=T, lo=True, seed=i))
    z2 = z + T * 0.82
    for i, y in enumerate((-0.2, 0.2)):                               # layer 2: long axis X
        P.append(sack("sack", M['sack'], M['band'], loc=(-0.12 + 0.1 * i, y, z2), rotz=0.06 * (1 - 2 * i), L=L, W=W, T=T,
                      lo=True, seed=5 + i, tilt=(0.04 * (1 - 2 * i), 0.0)))
    finish(root, P, name)
    center_root(root)
    return root


def build_drum():
    """Red steel oil drum (~0.6 m wide, 0.88 m tall) with rolling hoops, rim, two bung caps and
    rust at the base / in streaks (baked into the vertex colours)."""
    name = "drum"
    root = prop_root(name)
    M = dict(steel=mat("M_Drum", "#c0503a", roughness=0.6), cap=mat("M_DrumCap", "#c9c3b4", roughness=0.5))
    P = []
    R, H = 0.29, 0.88
    prof = [(0.0, 0.004), (R - 0.03, 0.0), (R - 0.004, 0.012), (R, 0.03), (R, 0.27), (R + 0.012, 0.285), (R + 0.012, 0.305),
            (R, 0.32), (R, 0.56), (R + 0.012, 0.575), (R + 0.012, 0.595), (R, 0.61), (R, H - 0.03), (R + 0.006, H - 0.01),
            (R - 0.006, H), (R - 0.02, H - 0.012), (R - 0.03, H - 0.016), (0.0, H - 0.016)]
    o = lathe("drum", prof, 16, M['steel'])
    weld(o, 1e-5)
    fix_normals(o)
    smooth_angle(o, 50)
    rnd = random.Random(8)
    streaks = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.2, 0.5), rnd.uniform(0.4, 1.0)) for _ in range(5)]

    def rust(c):
        a = math.atan2(c.y, c.x)
        s = max((st * max(0.0, 1 - abs(math.atan2(math.sin(a - a0), math.cos(a - a0))) / w) for a0, w, st in streaks))
        base = max(0.0, 1 - c.z / 0.22) * 1.2 + max(0.0, (c.z - (H - 0.08)) / 0.08) * 0.6
        return min(1.5, base + s * 1.3 * (1 - 0.6 * c.z / H))
    wattr(o, "w_rust", rust)
    wattr(o, "w_down", lambda co: 1.0 - co.z / H, "POINT")
    wattr(o, "w_shade", 0.0)
    P.append(o)
    for x, y, r in ((0.15, 0.08, 0.045), (-0.17, -0.02, 0.03)):
        P.append(add_cyl("bung", r, 0.03, loc=(x, y, H - 0.005), material=M['cap'], verts=8))
    finish(root, P, name)
    center_root(root)
    return root


def bamboo(P, p1, p2, r, m, verts=6, slant=0.0, name="bamboo"):
    """Bamboo pole from p1 to p2 (open-ended cylinder, top cut slanted by `slant` metres)."""
    o = rod(name, p1, p2, r, m, verts)
    if slant:
        top = max(v.co.z for v in o.data.vertices)
        for v in o.data.vertices:
            if v.co.z > top - 1e-4:
                v.co.z += slant * (v.co.x / r)
    P.append(o)
    return o


def build_pagar_bambu():
    """Bamboo fence segment, 2 m along X: a whole bamboo post in the middle and HALF posts (cut
    lengthwise) at x = +-1, so two neighbouring segments build one full post at their joint (no doubled
    post); two rails behind with rope ties, a row of slim vertical poles with slanted cuts."""
    name = "pagar_bambu"
    root = prop_root(name)
    M = dict(b=mat("M_Bamboo", "#c9a462"), d=mat("M_BambooDark", "#a3864f"), rope=mat("M_Rope", "#7a6446"))
    P = []
    rnd = random.Random(4)
    R, H = 0.05, 1.12
    bamboo(P, (0.0, 0.03, 0.0), (0.0, 0.03, H), R, M['d'], 8, slant=0.05, name="post")
    for sx in (-1, 1):
        # half of an 8-sided bamboo post, the flat cut face on the segment end plane (hidden in a joint)
        a0 = math.pi / 2 if sx > 0 else -math.pi / 2     # right end: the -X half, left end: the +X half
        ring = [(sx * 1.0 + R * math.cos(a0 + k * math.pi / 4), 0.03 + R * math.sin(a0 + k * math.pi / 4))
                for k in range(5)]
        vs = [(x, y, 0.0) for x, y in ring] + [(x, y, H - 0.02) for x, y in ring]
        fs = [(k, k + 1, 6 + k, 5 + k) for k in range(4)] + [(4, 0, 5, 9), tuple(range(5)), tuple(range(9, 4, -1))]
        o = mesh_from_data("post_end", vs, fs, M['d'])
        fix_normals(o)
        wattr(o, "w_shade", -0.04)
        P.append(o)
    for z in (0.34, 0.8):
        P.append(rod("rail", (-1.0, 0.05, z), (1.0, 0.05, z), 0.03, M['d'], 6))
        P.append(bx("tie", (0.12, 0.13, 0.07), (0.0, 0.035, z), M['rope'], 0))
        for sx in (-1, 1):
            o = bx("tie_end", (0.06, 0.13, 0.07), (sx * 0.97, 0.035, z), M['rope'], 0)
            wattr(o, "w_shade", 0.0)
            P.append(o)
    xs = [-0.88 + i * 0.136 for i in range(14)]
    for x in xs:
        if min(abs(x - px) for px in (-1.0, 0.0, 1.0)) < 0.07:
            continue
        h = rnd.uniform(0.88, 1.02)
        xx = x + rnd.uniform(-0.015, 0.015)
        bamboo(P, (xx, -0.005, 0.0), (xx + rnd.uniform(-0.02, 0.02), -0.005, h), rnd.uniform(0.021, 0.026), M['b'], 6,
               slant=rnd.choice((-1, 1)) * 0.03, name="pole")
    finish(root, P, name, var=0.08)
    return root


def build_meja():
    """Small wooden table (~0.9 x 0.6 x 0.72 m)."""
    name = "meja"
    root = prop_root(name)
    M = dict(w=mat("M_Wood", "wood_light"), d=mat("M_WoodDark", "wood"))
    P = []
    P.append(bx("top", (0.9, 0.6, 0.06), (0, 0, 0.71), M['w'], 0.025, 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(bx("leg", (0.07, 0.07, 0.68), (sx * 0.37, sy * 0.22, 0.34), M['d'], 0.018, 1))
    for sy in (-1, 1):
        P.append(bx("apron", (0.7, 0.03, 0.08), (0, sy * 0.22, 0.63), M['d'], 0.01, 1))
    for sx in (-1, 1):
        P.append(bx("apron", (0.03, 0.4, 0.08), (sx * 0.37, 0, 0.63), M['d'], 0.01, 1))
    P.append(bx("shelf", (0.72, 0.42, 0.03), (0, 0, 0.16), M['w'], 0.01, 1))
    finish(root, P, name)
    return root


# ============================================================ icon-only scenes
def icon_surat():
    """Paper document with text lines, a red stamp and a signature squiggle, slightly tilted."""
    root = empty("icon_surat")
    M = dict(p=mat("M_Paper", "#fbf6ea"), ink=mat("M_Ink", "#5a6270"), red=mat("M_Stamp", "#d23c32"),
             sig=mat("M_Sig", "#26324a"))
    P = []
    w, h = 0.7, 0.95
    # slightly curled sheet
    nx, ny = 4, 5
    vs, fs = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = -w / 2 + w * i / nx, -h / 2 + h * j / ny
            vs.append((x, y, 0.03 * ((i / nx) - 0.5) ** 2 * 4 + 0.025 * (j == ny)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            fs.append((a, a + 1, a + nx + 2, a + nx + 1))
    sheet = mesh_from_data("sheet", vs, fs, M['p'])
    P.append(sheet)
    P.append(bx("sheet_back", (w, h, 0.01), (0, 0, -0.006), M['p'], 0))
    # title + text lines
    P.append(bx("title", (0.34, 0.05, 0.01), (0, 0.36, 0.035), M['sig'], 0))
    for k in range(6):
        ln = 0.52 if k % 3 != 2 else 0.34
        P.append(bx("line", (ln, 0.028, 0.008), (-0.03 - (0.52 - ln) / 2, 0.24 - k * 0.075, 0.03), M['ink'], 0))
    # red stamp: ring + inner mark
    bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.018, major_segments=20, minor_segments=4,
                                     location=(0.17, -0.3, 0.04))
    t = C._active()
    t.scale = (1, 1, 0.3)
    set_mat(t, M['red'])
    P.append(t)
    P.append(bx("stamp_star", (0.1, 0.03, 0.01), (0.17, -0.3, 0.04), M['red'], 0, rotz=0.4))
    P.append(bx("stamp_star", (0.1, 0.03, 0.01), (0.17, -0.3, 0.04), M['red'], 0, rotz=-0.6))
    # signature squiggle (flat ribbon along a loopy curve)
    pts = []
    for k in range(26):
        s_ = k / 25
        x = -0.28 + 0.34 * s_
        y = -0.3 + 0.05 * math.sin(s_ * 14) + 0.03 * math.sin(s_ * 5)
        pts.append(Vector((x + 0.025 * math.cos(s_ * 14), y, 0.036)))
    vs2, fs2 = [], []
    for k, p in enumerate(pts):
        d = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        n = Vector((-d.y, d.x, 0)) * 0.011
        vs2 += [p + n, p - n]
    for k in range(len(pts) - 1):
        fs2.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2))
    sig = mesh_from_data("sig", vs2, fs2, M['sig'])
    P.append(sig)
    P.append(bx("sig_line", (0.36, 0.012, 0.006), (-0.11, -0.37, 0.03), M['ink'], 0))
    o = finish(root, P, "icon_surat")
    o.rotation_euler = (math.radians(-12), math.radians(6), math.radians(-14))
    return root


def icon_koin():
    """Stack of gold coins plus one leaning coin."""
    root = empty("icon_koin")
    M = dict(g=gold_mat(), d=gold_mat("M_GoldDark", "#d49a2e", 0.5, 0.4))
    P = []
    rnd = random.Random(2)

    def coin(loc, rot=(0, 0, 0)):
        c = add_cyl("coin", 0.3, 0.08, loc=(0, 0, 0), material=M['d'], verts=20)
        bevel_obj(c, 0.02, 1)
        P.append(c)
        c.location = loc
        c.rotation_euler = rot
        f = add_cyl("face", 0.22, 0.086, loc=(0, 0, 0), material=M['g'], verts=20)
        f.location = loc
        f.rotation_euler = rot
        P.append(f)
    for k in range(6):
        coin((rnd.uniform(-0.03, 0.03) - 0.12, rnd.uniform(-0.03, 0.03), 0.04 + k * 0.085))
    for k in range(3):
        coin((0.42 + rnd.uniform(-0.03, 0.03), 0.2, 0.04 + k * 0.085))
    coin((0.25, -0.28, 0.27), rot=(math.radians(70), 0, math.radians(15)))
    finish(root, P, "icon_koin")
    return root


def icon_pupuk():
    """Fertiliser sack standing up, print band facing the viewer."""
    root = empty("icon_pupuk")
    o = sack("sack", mat("M_Sack", "white"), mat("M_Print", "green_sign"), seed=2, T=0.28)
    o.rotation_euler = (math.radians(8), math.radians(90), math.radians(-90))
    finish(root, [o], "icon_pupuk")
    return root


def icon_uang():
    """Thick bundle of reddish-pink banknotes (Rp 100.000 style) held by a cream paper band."""
    root = empty("icon_uang")
    M = dict(n=mat("M_Note", "#e98d98"), d=mat("M_NoteDark", "#c85a6c"), band=mat("M_Band", "#f6ecd2"),
             g=mat("M_NoteLight", "#f8d2d6"))
    P = []
    w, h, t = 1.0, 0.5, 0.028
    n = 9
    for k in range(n):
        P.append(bx("note", (w, h, t), (0.006 * (k % 3), -0.005 * (k % 2), t / 2 + k * t), M['n'] if k % 2 else M['d'],
                    0.004, 1, rotz=0.012 * (k % 3 - 1)))
    top = n * t
    P.append(bx("frame", (w - 0.08, h - 0.08, 0.008), (0, 0, top + 0.002), M['d'], 0))
    P.append(bx("field", (w - 0.14, h - 0.14, 0.008), (0, 0, top + 0.005), M['n'], 0))
    P.append(add_cyl("portrait", 0.13, 0.01, loc=(0.24, 0, top + 0.009), material=M['g'], verts=14))
    P.append(bx("num", (0.2, 0.07, 0.01), (-0.28, 0.12, top + 0.009), M['g'], 0))
    P.append(bx("num2", (0.14, 0.05, 0.01), (-0.3, -0.13, top + 0.009), M['d'], 0))
    P.append(bx("band", (0.2, h + 0.04, top + 0.04), (-0.05, 0, top / 2 + 0.01), M['band'], 0.012, 1))
    o = finish(root, P, "icon_uang")
    o.rotation_euler = (0, 0, math.radians(-18))
    return root


def blade_mesh(name, outline, t, m, edge_m=None):
    """Extrude a 2D outline (XY) to thickness t (Z)."""
    n = len(outline)
    vs = [(x, y, t / 2) for x, y in outline] + [(x, y, -t / 2) for x, y in outline]
    fs = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        fs.append((i, n + i, n + j, j))
    o = mesh_from_data(name, vs, fs, m)
    fix_normals(o)
    return o


def lay_diagonal(o, tilt=12.0):
    """Lay a flat XY icon object (long axis +X) along the screen diagonal for a pitch-70 camera."""
    o.rotation_euler = (math.radians(tilt), 0, math.radians(38))


def icon_parang():
    """Parang (machete): broad blade widening to an angled tip, pale sharpened edge, wooden grip."""
    root = empty("icon_parang")
    M = dict(bl=mat("M_Blade", "#b9c6ca", roughness=0.35), edge=mat("M_Edge", "#eef4f5", roughness=0.3),
             wood=mat("M_Handle", "#7a4d2e"), rivet=mat("M_Rivet", "#e0c080"))
    P = []
    spine, belly = [], []
    for k in range(9):
        s_ = k / 8
        x = 0.02 + 1.05 * s_
        spine.append((x, 0.09 + 0.03 * s_ + 0.02 * math.sin(s_ * math.pi)))
        belly.append((x, -0.08 - 0.14 * s_ ** 1.5))
    outline = belly + [(1.2, -0.2), (1.16, 0.15)] + spine[::-1]
    P.append(blade_mesh("blade", outline, 0.04, M['bl']))
    edge = belly + [(1.2, -0.2), (1.17, -0.13)] + [(x, y + 0.055) for x, y in belly[::-1]]
    P.append(blade_mesh("edge", edge, 0.05, M['edge']))
    P.append(bx("guard", (0.07, 0.3, 0.1), (0.0, 0.0, 0), M['rivet'], 0.02, 1))
    P.append(bx("grip", (0.5, 0.17, 0.12), (-0.27, 0.0, 0), M['wood'], 0.05, 2))
    P.append(bx("pommel", (0.08, 0.2, 0.13), (-0.53, 0.0, 0), M['rivet'], 0.03, 1))
    for x in (-0.15, -0.38):
        P.append(add_cyl("rivet", 0.03, 0.14, loc=(x, 0.0, 0), material=M['rivet'], verts=8))
    o = finish(root, P, "icon_parang")
    lay_diagonal(o)
    return root


def icon_egrek():
    """Egrek: long harvesting pole with a big curved sickle blade (framed along the diagonal)."""
    root = empty("icon_egrek")
    M = dict(pole=mat("M_Pole", "#c8a15e"), bl=mat("M_Blade", "#b9c6ca", roughness=0.35),
             bind=mat("M_Bind", "#3f5b4f"), edge=mat("M_Edge", "#eef4f5", roughness=0.3))
    P = []
    L = 1.3
    P.append(rod("pole", (0, 0, 0), (L, 0, 0), 0.055, M['pole'], 8))
    for x in (0.35, 0.75):
        P.append(rod("node", (x - 0.025, 0, 0), (x + 0.025, 0, 0), 0.068, M['pole'], 8))
    P.append(rod("bind", (L - 0.2, 0, 0), (L - 0.02, 0, 0), 0.072, M['bind'], 8))
    P.append(rod("butt", (-0.04, 0, 0), (0.09, 0, 0), 0.07, M['bind'], 8))
    outer, inner = [], []
    cx, cy, R = L + 0.0, -0.3, 0.38
    for k in range(12):
        a = math.radians(92 - 155 * k / 11)
        wdt = 0.13 * (1 - k / 12.5) + 0.02
        outer.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        inner.append((cx + (R - wdt) * math.cos(a), cy + (R - wdt) * math.sin(a)))
    outline = [(L - 0.16, 0.06), (L - 0.16, -0.06)] + inner + outer[::-1]
    P.append(blade_mesh("sickle", outline, 0.035, M['bl']))
    edge = inner[2:] + [(cx + (x - cx) * 1.08, cy + (y - cy) * 1.08) for x, y in inner[2:][::-1]]
    P.append(blade_mesh("edge", edge, 0.045, M['edge']))
    o = finish(root, P, "icon_egrek")
    lay_diagonal(o)
    return root


def icon_helm():
    """Yellow worker hard hat: dome with a raised centre rib and a peaked brim."""
    root = empty("icon_helm")
    M = dict(y=mat("M_Helmet", "#f5c443", roughness=0.4), d=mat("M_HelmetDark", "#e0a52c", roughness=0.45))
    P = []

    def dome(name, sx, sy, sz, m, seg=20):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=10, radius=1.0)
        o = C._active()
        o.name = name
        for v in o.data.vertices:
            v.co.z = max(0.0, v.co.z)
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
        set_mat(o, m)
        shade_smooth(o)
        o.location = (0, 0, 0.1)
        return o
    P.append(dome("dome", 0.48, 0.55, 0.46, M['y']))
    P.append(dome("rib", 0.09, 0.575, 0.495, M['d'], seg=12))
    brim = add_cyl("brim", 0.6, 0.05, loc=(0, 0, 0.1), material=M['y'], verts=24)
    for v in brim.data.vertices:
        v.co.x *= 0.95
        if v.co.y < 0:
            v.co.y *= 1.35                       # peak at the front
            v.co.z += 0.06 * (-v.co.y / 0.8)     # tipped up slightly
        else:
            v.co.y *= 1.05
    bevel_obj(brim, 0.02, 1)
    shade_smooth(brim)
    P.append(brim)
    P.append(add_cyl("band", 0.5, 0.06, loc=(0, 0, 0.16), material=M['d'], verts=24, radius2=0.49))
    o = finish(root, P, "icon_helm")
    o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
    return root


def icon_kunci():
    """Chunky golden key (land deed) with a small cream tag and green sprout."""
    root = empty("icon_kunci")
    M = dict(g=gold_mat(), d=gold_mat("M_GoldDark", "#d49a2e", 0.5, 0.4), tag=mat("M_Tag", "cream"),
             leaf=mat("M_Leaf", "green_sign"))
    P = []
    bpy.ops.mesh.primitive_torus_add(major_radius=0.26, minor_radius=0.085, major_segments=20, minor_segments=8,
                                     location=(-0.5, 0, 0))
    bow = C._active()
    bow.name = "bow"
    set_mat(bow, M['g'])
    shade_smooth(bow)
    P.append(bow)
    P.append(add_cyl("bow_gem", 0.11, 0.08, loc=(-0.5, 0, 0), material=M['d'], verts=12))
    P.append(rod("collar", (-0.27, 0, 0), (-0.17, 0, 0), 0.085, M['d'], 12))
    P.append(rod("shaft", (-0.24, 0, 0), (0.62, 0, 0), 0.06, M['g'], 12, smooth=True))
    P.append(add_sphere("tip", 0.065, loc=(0.62, 0, 0), material=M['g'], segments=12, rings=6))
    for x, hgt in ((0.34, 0.24), (0.47, 0.15), (0.58, 0.24)):
        P.append(bx("tooth", (0.09, hgt, 0.08), (x, -hgt / 2 - 0.03, 0), M['g'], 0.02, 1))
    P.append(rod("string", (-0.72, 0.1, 0), (-0.8, 0.28, 0.0), 0.015, M['tag'], 4))
    P.append(bx("tag", (0.22, 0.15, 0.025), (-0.84, 0.36, 0), M['tag'], 0.02, 1, rotz=-0.4))
    P.append(add_sphere("leaf", 0.06, loc=(-0.84, 0.36, 0.02), material=M['leaf'], segments=8, rings=4,
                        scale=(1.4, 0.7, 0.3)))
    o = finish(root, P, "icon_kunci")
    lay_diagonal(o, tilt=18)
    return root


# ============================================================ registry / main
BUILDERS = {
    "crate": build_crate,
    "karung_pupuk": build_karung_pupuk,
    "jerigen": build_jerigen,
    "pagar": build_pagar,
    "papan": build_papan,
    "bangku": build_bangku,
    "gerobak": build_gerobak,
    "sumur": build_sumur,
    "lampu": build_lampu,
    "tumpukan_tbs": build_tumpukan_tbs,
    "tenda": build_tenda,
    "spanduk": build_spanduk,
    "meja": build_meja,
    "karung_tumpuk": build_karung_tumpuk,
    "drum": build_drum,
    "pagar_bambu": build_pagar_bambu,
}
# baked AO + weathering per prop (weather_bake kwargs); small props: short AO rays, low dirt band
PROP_WEATHER = dict(dirt=0.4, dirt_h=0.25, distance=0.6)
WEATHER = {
    "lampu": dict(dirt=0.4, dirt_h=0.3, distance=0.8),
    "sumur": dict(dirt=0.45, dirt_h=0.35, distance=0.8),
    "tenda": dict(dirt=0.4, dirt_h=0.3, distance=0.8),
    "spanduk": dict(dirt=0.4, dirt_h=0.3, distance=0.8),
    "drum": dict(dirt=0.3, dirt_h=0.2, distance=0.6),
    "pagar_bambu": dict(dirt=0.45, dirt_h=0.3, distance=0.6),
    "pagar": dict(dirt=0.45, dirt_h=0.3, distance=0.6),
}
# icons rendered from the finished prop
PROP_ICONS = {
    "jerigen": dict(name="icon_minyak", pitch_deg=25, yaw_deg=30, margin=1.02),
    "gerobak": dict(name="icon_gerobak", pitch_deg=32, yaw_deg=55, margin=0.96),
}
# dedicated icon-only scenes: builder, render kwargs
ICON_SCENES = {
    "icon_pupuk": (icon_pupuk, dict(pitch_deg=22, yaw_deg=25, margin=1.0)),
    "icon_surat": (icon_surat, dict(pitch_deg=75, yaw_deg=0, margin=0.8)),
    "icon_koin": (icon_koin, dict(pitch_deg=30, yaw_deg=20, margin=0.8)),
    "icon_uang": (icon_uang, dict(pitch_deg=42, yaw_deg=18, margin=0.82)),
    "icon_parang": (icon_parang, dict(pitch_deg=70, yaw_deg=0, margin=0.8)),
    "icon_egrek": (icon_egrek, dict(pitch_deg=70, yaw_deg=0, margin=0.8)),
    "icon_helm": (icon_helm, dict(pitch_deg=28, yaw_deg=25, margin=0.86)),
    "icon_kunci": (icon_kunci, dict(pitch_deg=70, yaw_deg=0, margin=0.8)),
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_render = "--no-render" in sys.argv
    names = args or (list(BUILDERS) + ["icons"])
    if "icons" in names:
        names = [n for n in names if n != "icons"] + list(ICON_SCENES)
    for n in names:
        reset_scene()
        if n in ICON_SCENES:
            fn, kw = ICON_SCENES[n]
            root = fn()
            bpy.context.view_layer.update()
            print(f"[icon-scene] {n} tris={count_tris(root)}")
            if not no_render:
                render_icon(root, n, **kw)
            continue
        root = BUILDERS[n]()
        bpy.context.view_layer.update()
        d = dims(root)
        print(f"[dims] {n}: {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f} m  tris={count_tris(root)}  "
              f"mats={sorted({s.material.name for o in all_descendants(root) if o.type == 'MESH' for s in o.material_slots})}")
        weather_bake(root, **WEATHER.get(n, PROP_WEATHER))
        export_glb(root, n)
        preview_vcol(root)
        if not no_render:
            render_preview(root, n)
            if DEBUG:
                debug_view(root, n + "_game", 55, 0)
        if not no_render and n in PROP_ICONS:
            kw = dict(PROP_ICONS[n])
            render_icon(root, kw.pop("name"), **kw)


if __name__ == "__main__":
    main()

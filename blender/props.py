"""Props, shared modelling helpers and UI icons for Sawit The Franchise.

Run:  python3 blender/props.py               (build every prop + previews + all prop icons)
      python3 blender/props.py crate icons   (only some; "icons" = the icon scenes)
Flags: --no-render  skip previews/icons (fast tri check)
       --debug      extra game-camera views to $SAWIT_DEBUG_DIR and per-part tri breakdown

The generic helpers here (bx, rod, beam, ...) are also imported by buildings.py.
Every asset: root Empty named after the asset, meshes parented to it, front facing -Y,
origin at the ground centre. Reserved materials: M_Glass (windows), M_Lamp (lamp bulb).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

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


def center_root(root, keep_y=False):
    """Shift the root's children so the XY bounding-box centre is at the origin."""
    mn, mx = C._bounds(root)
    off = Vector((-(mn.x + mx.x) / 2, 0 if keep_y else -(mn.y + mx.y) / 2, -mn.z if mn.z > 0.001 else 0))
    for ch in root.children:
        ch.location += off
    bpy.context.view_layer.update()


def part_tris(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def finish(root, parts, name):
    """Join parts into '<name>_mesh' under root (prints a tri breakdown with --debug)."""
    if DEBUG:
        agg = {}
        for p in parts:
            k = p.name.split(".")[0]
            agg[k] = agg.get(k, 0) + part_tris(p)
        print("[tris]", name, sorted(agg.items(), key=lambda kv: -kv[1]))
    o = join(parts, name + "_mesh")
    o.data.name = name + "_mesh"
    reparent(o, root)
    return o


def dims(root):
    mn, mx = C._bounds(root)
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


def bunch(name, mats, loc=(0, 0, 0), size=1.0, seed=0, rot=(0, 0, 0), nspk=10):
    """Palm fruit bunch (TBS): bumpy red-orange ovoid, darker cap and dark-tipped spiky fruitlets.
    mats = (red body, orange base, dark tips). ~95 tris. Origin at the bottom of the bunch."""
    rnd = random.Random(seed)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=5, radius=1.0)
    o = C._active()
    o.name = name
    me = o.data
    rx, rz = 0.2 * size, 0.26 * size
    shape = lambda d: Vector((d.x * rx * (1.0 - 0.2 * max(0.0, d.z)), d.y * rx * (1.0 - 0.2 * max(0.0, d.z)), d.z * rz))
    for v in me.vertices:
        d = v.co.normalized()
        v.co = shape(d) * rnd.uniform(0.9, 1.1)
    me.update()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        cz = p.center.z / rz
        p.material_index = 2 if cz > 0.8 else (0 if cz > -0.35 else 1)
    shade_smooth(o)
    verts, faces = [], []
    for k in range(nspk):
        zz = max(-0.6, min(0.85, 1 - (k + 0.5) / nspk * 1.5))
        a = k * 2.39996 + rnd.uniform(-0.3, 0.3)
        rr = math.sqrt(max(0.0, 1 - zz * zz))
        d = Vector((rr * math.cos(a), rr * math.sin(a), zz))
        c = shape(d) * 0.92
        n = Vector((d.x / rx, d.y / rx, d.z / rz)).normalized()
        t1 = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized()
        t2 = n.cross(t1)
        w = 0.05 * size
        b0 = len(verts)
        for j in range(3):
            ang = j * 2 * math.pi / 3 + rnd.uniform(0, 1)
            verts.append(c + (t1 * math.cos(ang) + t2 * math.sin(ang)) * w)
        verts.append(c + n * (0.065 * size + rnd.uniform(0, 0.02)))
        faces += [(b0, b0 + 1, b0 + 3), (b0 + 1, b0 + 2, b0 + 3), (b0 + 2, b0, b0 + 3)]
    sp = mesh_from_data(name + "_tips", verts, faces, mats[2])
    fix_normals(sp)
    o = join([o, sp], name)
    o.location = Vector(loc) + Vector((0, 0, rz * 0.92))
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


def crate_parts(P, m_wood, m_dark, loc=(0, 0, 0), size=(0.6, 0.45, 0.4), rotz=0.0):
    """Slatted wooden crate: dark core + light slats + corner posts."""
    x, y, z = loc
    sx, sy, sz = size
    fr = lambda lx, ly, lz: fpt((x, y, z), rotz, (lx, ly, lz))
    P.append(bx("crate_core", (sx - 0.04, sy - 0.04, sz - 0.02), fr(0, 0, sz / 2), m_dark, 0, rotz=rotz))
    for k, zz in enumerate((0.25, 0.75)):
        P.append(bx("crate_slat", (sx - 0.02, sy - 0.02, sz * 0.3), fr(0, 0, sz * zz), m_wood, 0.015, 1, rotz))
    for ax in (-1, 1):
        for ay in (-1, 1):
            P.append(bx("crate_post", (0.07, 0.07, sz), fr(ax * (sx / 2 - 0.035), ay * (sy / 2 - 0.035), sz / 2),
                        m_wood, 0.015, 1, rotz))
    P.append(bx("crate_top", (sx - 0.1, sy - 0.1, 0.03), fr(0, 0, sz - 0.02), m_wood, 0, rotz=rotz))

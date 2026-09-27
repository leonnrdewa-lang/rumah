#!/usr/bin/env python3
"""Vegetation, rocks and nature props for Sawit The Franchise.

Run:  python3 blender/vegetation.py            # build everything
      python3 blender/vegetation.py sawit_3    # build only the named assets

Every asset is built from scratch after reset_scene(), previewed to
blender/previews/<name>.png and exported to game/assets/models/<name>.glb.

Node / material names the game relies on:
  * sawit_3 root Empty -> child Empty `Fruits` -> separate meshes `Fruit_0..n`
    (toggle `Fruits` visibility for harvest state).
  * `M_Frond` is the single leaf material of every palm (sawit_*, coconut,
    banana); it has backface culling OFF so Godot imports it double-sided.
    Other thin materials (grass, petals, bush leaves, dry leaves) are double-sided
    too; every closed/solid material is exported with backface culling ON.

Set VEG_SCRATCH=<dir> to also write extra close-up debug renders there.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector, Matrix, noise  # noqa: E402

import common  # noqa: E402
from common import (  # noqa: E402
    reset_scene, mat, add_box, add_cyl, add_ico, join, shade_smooth, set_mat,
    empty, export_glb, render_preview, render_icon, count_tris, all_descendants,
)

UP = Vector((0.0, 0.0, 1.0))
GOLDEN = math.radians(137.508)
SCRATCH = os.environ.get("VEG_SCRATCH")  # optional extra debug views


# ============================================================ geometry helpers
def newell(pts):
    n = Vector((0.0, 0.0, 0.0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


class Geo:
    """Tiny mesh builder: verts + faces with per-face material index / smooth flag."""

    def __init__(self):
        self.v, self.f, self.fm, self.fs = [], [], [], []

    def vert(self, co):
        self.v.append(Vector(co))
        return len(self.v) - 1

    def face(self, idx, mi=0, ref=None, smooth=False):
        idx = list(idx)
        if ref is not None:
            if newell([self.v[i] for i in idx]).dot(ref) < 0:
                idx.reverse()
        self.f.append(idx)
        self.fm.append(mi)
        self.fs.append(smooth)

    def obj(self, name, mats, parent=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        me.update()
        for m in mats:
            me.materials.append(m)
        for p, mi, s in zip(me.polygons, self.fm, self.fs):
            p.material_index = mi
            p.use_smooth = s
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        if parent is not None:
            o.parent = parent
        return o


def lerp(a, b, t):
    return a + (b - a) * t


def ground(o):
    """Move object so its lowest vertex sits at z=0 (in object space, identity transforms)."""
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin
    o.data.update()
    return o


def leafy(m):
    """Mark a material double-sided (thin leaves / blades). Every other material is exported
    with backface culling ON (see finish()), so Godot only disables culling for leaves."""
    m.use_backface_culling = False
    m["double_sided"] = True
    return m


def frond_mat():
    return leafy(mat("M_Frond", "#528a33"))


def _debug_camera(center, scale, pitch_deg, yaw_deg):
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    common.link(cam)
    pitch, yaw = math.radians(pitch_deg), math.radians(yaw_deg)
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = Vector(center) + dirv * 40
    cam.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    cam.data.clip_end = 200
    bpy.context.scene.camera = cam
    return cam


def extra_views(root, name, views):
    """Debug renders into $VEG_SCRATCH (not part of the deliverables).

    views: (tag, pitch, yaw) or (tag, pitch, yaw, center, ortho_scale)."""
    if not SCRATCH:
        return
    for view in views:
        tag, pitch, yaw = view[:3]
        common._setup_render(420, 420, transparent=False, samples=12)
        tmp = common._temp_lights()
        bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.001))
        g = bpy.context.view_layer.objects.active
        set_mat(g, mat("_M_PreviewGround", "#8fb35c"))
        tmp.append(g)
        if len(view) > 3:
            tmp.append(_debug_camera(view[3], view[4], pitch, yaw))
        else:
            tmp.append(common._temp_camera(root, pitch, yaw, margin=0.8))
        bpy.context.scene.render.filepath = os.path.join(SCRATCH, f"{name}_{tag}.png")
        bpy.ops.render.render(write_still=True)
        for o in tmp:
            bpy.data.objects.remove(o, do_unlink=True)


def finalize(root):
    """Cull back faces on closed (non-leaf) materials and make sure nothing dips below z=0."""
    for o in all_descendants(root):
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is not None and not m.get("double_sided", False):
                m.use_backface_culling = True
        mw = o.matrix_world
        inv = mw.inverted()
        for v in o.data.vertices:
            w = mw @ v.co
            if w.z < 0.0:
                w.z = 0.0
                v.co = inv @ w
        o.data.update()


def finish(root, name, icon=None, icon_kw=None, views=()):
    bpy.context.view_layer.update()
    finalize(root)
    render_preview(root, name)
    extra_views(root, name, views)
    export_glb(root, name)
    if icon:
        render_icon(root, icon, **(icon_kw or {}))
    tris = count_tris(root)
    mats = sorted({s.material.name for o in all_descendants(root) if o.type == "MESH"
                   for s in o.material_slots if s.material})
    print(f"[done] {name}: tris={tris} mats={mats}")
    return tris


# ============================================================ palm fronds
def frond_profile(u):
    """Leaflet length along the leafy part of the rachis (u: 0 base -> 1 tip)."""
    return max(0.12, math.sin(math.pi * (0.1 + 0.9 * u))) ** 0.7


def frond(g, mi, base, phi, elev, L, droop, rnd, n_side=18, lmax=0.8, lw=0.09, bare=0.22,
          vfold=18.0, theta0=62.0, twist=0.0, rachis_w=0.05, segs=8, leaf_droop=0.28):
    """Add one pinnate frond (curved rachis + leaflets on both sides) to Geo `g`.

    base: attachment point, phi: azimuth (rad), elev: start angle above horizon (deg),
    droop: how many degrees the rachis bends down toward the tip.
    """
    base = Vector(base)
    yaw_drift = rnd.uniform(-0.18, 0.18)
    pts = [base]
    ds = L / segs
    for i in range(segs):
        t = (i + 0.5) / segs
        a = math.radians(elev - droop * t ** 1.4)
        ph = phi + yaw_drift * t
        d = Vector((math.cos(ph) * math.cos(a), math.sin(ph) * math.cos(a), math.sin(a)))
        pts.append(pts[-1] + d * ds)

    def frame(t):
        x = min(max(t, 0.0), 1.0) * segs
        i = min(int(x), segs - 1)
        f = x - i
        p = pts[i].lerp(pts[i + 1], f)
        T = (pts[i + 1] - pts[i]).normalized()
        S = T.cross(UP)
        if S.length < 1e-4:
            S = Vector((math.sin(phi), -math.cos(phi), 0.0))
        S.normalize()
        N = S.cross(T).normalized()
        if twist:
            r = Matrix.Rotation(math.radians(twist) * t, 3, T)
            S, N = r @ S, r @ N
        return p, T, S, N

    # rachis: a thin tapering ridge (Λ profile), 2 quads per segment
    ring = []
    for i in range(segs + 1):
        t = i / segs
        p, T, S, N = frame(t)
        w = rachis_w * (0.22 + 0.78 * (1.0 - t) ** 2.2)
        ring.append((g.vert(p + S * w - N * w * 0.3), g.vert(p + N * w * 0.7), g.vert(p - S * w - N * w * 0.3)))
    for i in range(segs):
        a, b = ring[i], ring[i + 1]
        _, _, _, N = frame((i + 0.5) / segs)
        g.face((a[0], b[0], b[1], a[1]), mi, ref=N + frame((i + 0.5) / segs)[2])
        g.face((a[1], b[1], b[2], a[2]), mi, ref=N - frame((i + 0.5) / segs)[2])

    # leaflets: 2-tri kites, alternating upper/lower insertion -> feathery volume
    for k in range(n_side):
        for side in (-1, 1):
            t = bare + (1.0 - bare) * (k + 0.5 + (0.25 if side > 0 else -0.25)) / n_side
            t = min(0.985, t + rnd.uniform(-0.3, 0.3) / n_side)
            p, T, S, N = frame(t)
            u = (t - bare) / (1.0 - bare)
            prof = frond_profile(u)
            ln = lmax * prof * rnd.uniform(0.85, 1.1)
            th = math.radians(theta0 * (1.0 - 0.4 * u) + rnd.uniform(-7, 7))
            v = math.radians(vfold + (10 if (k % 2) else -6) + rnd.uniform(-5, 5))
            sd = S * side * math.cos(v) + N * math.sin(v)
            D = (T * math.cos(th) + sd * math.sin(th)).normalized()
            W = D.cross(N).normalized()
            w = lw * (0.55 + 0.45 * prof)
            A = p + S * side * rachis_w * (0.22 + 0.78 * (1.0 - t) ** 2.2) * 0.6
            mid = A + D * ln * 0.42 - UP * ln * leaf_droop * 0.25
            tip = A + D * ln - UP * ln * leaf_droop
            ia, il, ir, it = g.vert(A), g.vert(mid + W * w * 0.5), g.vert(mid - W * w * 0.5), g.vert(tip)
            ref = N + UP * 0.5
            g.face((ia, ir, il), mi, ref=ref)
            g.face((il, ir, it), mi, ref=ref)
    return pts


# ============================================================ palm trunk
def trunk_radius(z, H, r):
    """Oil-palm trunk: flared root bole, then near-cylindrical."""
    flare = max(0.0, 1.0 - z / 0.45) ** 2 * 0.45 * r
    return r * (1.0 + 0.06 * math.sin(z * 2.1)) + flare


def palm_trunk(g, mi_core, mi_boot, H, r, rnd, sides=10, rings=6, boots=36, boot_z0=0.35, boot_z1=None,
               boot_len=0.34, boot_w=0.22, boot_t=0.1, boot_el=(35, 60), cap=True):
    """Tapered trunk core + spiral of cut frond bases ("boots")."""
    rows = []
    for j in range(rings + 1):
        z = H * (j / rings) ** 1.15
        rr = trunk_radius(z, H, r) * (0.92 if j == rings else 1.0)
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides + j * 0.3
            jr = rr * rnd.uniform(0.95, 1.05)
            row.append(g.vert((jr * math.cos(a), jr * math.sin(a), z)))
        rows.append(row)
    for j in range(rings):
        for i in range(sides):
            a, b = rows[j][i], rows[j][(i + 1) % sides]
            c, d = rows[j + 1][(i + 1) % sides], rows[j + 1][i]
            mid = (g.v[a] + g.v[c]) * 0.5
            g.face((a, b, c, d), mi_core, ref=Vector((mid.x, mid.y, 0)), smooth=True)
    if cap:
        top = g.vert((0, 0, H + r * 0.6))
        for i in range(sides):
            a, b = rows[-1][i], rows[-1][(i + 1) % sides]
            g.face((a, b, top), mi_core, ref=UP, smooth=True)

    # boots: phyllotactic spiral of wedge-shaped cut petiole bases.  Each boot is a
    # triangular prism (flat top, keel underneath) with a slanted cut end.
    for k in range(boots):
        f = k / max(1, boots - 1)
        z = lerp(boot_z0, boot_z1 if boot_z1 is not None else H - 0.3, f ** 0.85)
        a = k * GOLDEN + rnd.uniform(-0.15, 0.15)
        O = Vector((math.cos(a), math.sin(a), 0.0))
        Tg = Vector((-math.sin(a), math.cos(a), 0.0))
        rr = trunk_radius(z, H, r)
        C = O * (rr - 0.05) + UP * z
        el = math.radians(rnd.uniform(*boot_el))
        D = (O * math.cos(el) + UP * math.sin(el)).normalized()
        Rn = D.cross(Tg).normalized()  # thickness axis, points up / inward
        ln = boot_len * rnd.uniform(0.8, 1.15) * (0.7 + 0.3 * f)
        wb = boot_w * rnd.uniform(0.85, 1.1)
        we = wb * 0.55
        tb, te = boot_t, boot_t * 0.7
        E = C + D * ln
        cut = ln * 0.3  # upper edge shorter than keel -> cut face looks up/out
        base = [C + Tg * wb * 0.5 + Rn * tb * 0.4, C - Tg * wb * 0.5 + Rn * tb * 0.4, C - Rn * tb]
        end = [E - D * cut + Tg * we * 0.5 + Rn * te * 0.4, E - D * cut - Tg * we * 0.5 + Rn * te * 0.4,
               E - Rn * te]
        bi = [g.vert(p) for p in base]
        ei = [g.vert(p) for p in end]
        ctr = (C + E) * 0.5 - Rn * tb * 0.2
        for i in range(3):
            q = (bi[i], bi[(i + 1) % 3], ei[(i + 1) % 3], ei[i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            g.face(q, mi_boot, ref=fc - ctr)
        g.face(ei, mi_boot, ref=D + Rn)


# ============================================================ fruit bunch (TBS)
def fruit_bunch(name, center, axis, length, rnd, mats, parent=None, n_fruitlets=40, sides=5,
                core_detail=1, fr_size=0.2, core_mat=0):
    """Oil-palm fresh fruit bunch (TBS): an ovoid packed with oval fruitlets that
    point outward and toward the apex like pine-cone scales; each fruitlet is
    red-orange with a near-black tip.  mats = (M_Fruit, M_Dark).
    Long axis along `axis`, apex (free end) at +axis.
    """
    g = Geo()
    ax = Vector(axis).normalized()
    rot = ax.to_track_quat("Z", "Y").to_matrix()
    C = Vector(center)
    rad = length * 0.33
    half = length * 0.5

    def surf(c):
        egg = 1.0 - 0.14 * c.z
        return Vector((c.x * rad * egg, c.y * rad * egg, c.z * half))

    # dark core (visible in the gaps between fruitlets)
    tmp = add_ico("_tmp_core", 1.0, subdiv=core_detail, smooth=False)
    cv = [v.co.copy() for v in tmp.data.vertices]
    cf = [list(p.vertices) for p in tmp.data.polygons]
    me = tmp.data
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.meshes.remove(me)
    base = len(g.v)
    for co in cv:
        g.vert(C + rot @ (surf(co.normalized()) * 0.8))
    for f in cf:
        g.face([base + i for i in f], core_mat, smooth=True)

    # fruitlets on a fibonacci spiral over the ovoid (skip the stalk end)
    for k in range(n_fruitlets):
        zc = lerp(0.95, -0.8, (k + 0.5) / n_fruitlets) + rnd.uniform(-0.03, 0.03)
        ang = k * GOLDEN + rnd.uniform(-0.2, 0.2)
        rc = math.sqrt(max(0.0, 1 - zc * zc))
        c = Vector((rc * math.cos(ang), rc * math.sin(ang), zc))
        p = surf(c) * 0.86
        egg = 1.0 - 0.14 * c.z
        n = Vector((c.x / (rad * egg), c.y / (rad * egg), c.z / half)).normalized()
        apex = (Vector((0, 0, 1)) - n * n.z)
        apex = apex.normalized() if apex.length > 1e-3 else Vector((1, 0, 0))
        tilt = math.radians(rnd.uniform(38, 55) * (0.4 + 0.6 * rc))
        D = (n * math.cos(tilt) + apex * math.sin(tilt)).normalized()
        sz = length * fr_size * rnd.uniform(0.9, 1.1) * (0.7 + 0.3 * rc)
        rw = sz * 0.5
        U = D.cross(Vector((0.31, 0.83, 0.47))).normalized()
        V = D.cross(U)
        # dark cap grows toward the sunny apex of the bunch
        cap = lerp(0.12, 0.22, (zc + 0.8) / 1.75) * rnd.uniform(0.8, 1.2)
        dark = 1 if rnd.random() < lerp(0.2, 0.8, (zc + 0.8) / 1.75) else 0
        inner = p - D * sz * 0.4
        ringc = p + D * sz * (0.5 - cap)
        outer = p + D * sz * 0.5
        ii = g.vert(C + rot @ inner)
        io = g.vert(C + rot @ outer)
        ring = [g.vert(C + rot @ (ringc + (U * math.cos(q) + V * math.sin(q)) * rw * rnd.uniform(0.9, 1.1)))
                for q in (2 * math.pi * s / sides + k for s in range(sides))]
        Dw = rot @ D
        for s in range(sides):
            a, b = ring[s], ring[(s + 1) % sides]
            mid = (g.v[a] + g.v[b]) * 0.5
            g.face((a, b, ii), 0, ref=mid - g.v[ii] - Dw * 0.3, smooth=True)
            g.face((a, b, io), dark, ref=mid - g.v[io] + Dw * 0.3, smooth=True)
    return g.obj(name, list(mats), parent)


# ============================================================ palms (sawit stages)
SAWIT_STAGES = {
    # name: trunk height, radius, frond count, frond length, leaflets per side, ...
    "sawit_1": dict(young=0.95, H=0.22, r=0.15, n=10, L=1.55, n_side=12, lmax=0.66, lw=0.13, boots=8, boot_len=0.2,
                    boot_w=0.15, boot_t=0.08, rachis_w=0.055, el=(85, 22), droop=(10, 48), spear=0.6,
                    base_r=0.08, fruits=0),
    "sawit_2": dict(young=0.92, H=0.85, r=0.23, n=14, L=2.35, n_side=15, lmax=0.85, lw=0.16, boots=20, boot_len=0.3,
                    boot_w=0.2, boot_t=0.1, rachis_w=0.075, el=(84, 8), droop=(16, 44), spear=0.9,
                    base_r=0.14, fruits=0),
    "sawit_3": dict(H=2.85, r=0.27, n=22, L=2.8, n_side=15, lmax=1.0, lw=0.18, boots=42, boot_len=0.42,
                    boot_w=0.24, boot_t=0.12, rachis_w=0.1, el=(80, -8), droop=(22, 50), spear=1.2,
                    base_r=0.2, fruits=5),
}


def build_palm(name, P, seed=3):
    rnd = random.Random(seed)
    root = empty(name)
    m_frond = frond_mat()
    m_trunk = mat("M_Trunk", "#7a5f40")
    m_dark = mat("M_Dark", "#3a2820")
    m_fruit = mat("M_Fruit", "#e0521f")
    g = Geo()
    H, r = P["H"], P["r"]
    palm_trunk(g, 2, 1, H, r, rnd, boots=P["boots"], boot_len=P["boot_len"], boot_w=P["boot_w"],
               boot_t=P["boot_t"], boot_z0=min(0.35, H * 0.25), rings=max(2, int(H / 0.45)))
    n = P["n"]
    top = H + 0.05
    first_frond_vert = len(g.v)
    for i in range(n):
        f = i / (n - 1)  # 0 youngest (upright) -> 1 oldest (drooping)
        phi = i * GOLDEN + rnd.uniform(-0.1, 0.1)
        el = lerp(P["el"][0], P["el"][1], f ** 0.85) + rnd.uniform(-4, 4)
        dr = lerp(P["droop"][0], P["droop"][1], f) + rnd.uniform(-5, 5)
        L = P["L"] * lerp(P.get("young", 0.72), 1.0, min(1.0, f * 2.2)) * rnd.uniform(0.94, 1.04)
        zb = top - (0.1 + 0.55 * f) * min(1.0, P["H"] / 1.5 + 0.2)
        rb = P["base_r"] * (0.4 + 0.6 * f)
        base = (rb * math.cos(phi), rb * math.sin(phi), zb)
        frond(g, 0, base, phi, el, L, dr, rnd, n_side=P["n_side"], lmax=P["lmax"], lw=P["lw"],
              rachis_w=P["rachis_w"], twist=rnd.uniform(-12, 12) + 18 * f, segs=P.get("segs", 6),
              vfold=lerp(34, 12, min(1.0, f * 1.6)))
    # spear(s): unopened young leaves pointing straight up out of the crown heart
    for si, (sp, lean) in enumerate(((P["spear"], 0.06), (P["spear"] * 0.7, -0.1))):
        spr = P["rachis_w"] * 0.8
        la = rnd.uniform(0, 6.28)
        sb = [g.vert((spr * math.cos(a), spr * math.sin(a), top - 0.15)) for a in
              (la, la + 1.57, la + 3.14, la + 4.71)]
        st = g.vert((lean * sp * math.cos(la), lean * sp * math.sin(la), top + sp))
        for i in range(4):
            g.face((sb[i], sb[(i + 1) % 4], st), 0,
                   ref=(g.v[sb[i]] + g.v[sb[(i + 1) % 4]]) * 0.5 - Vector((0, 0, top)))
    for v in g.v[first_frond_vert:]:  # old fronds of young palms rest on the ground instead of piercing it
        if v.z < 0.02:
            v.z = 0.02 + 0.01 * (v.x * 7 % 1)
    body = g.obj(name + "_body", [m_frond, m_trunk, m_dark], root)
    if P["fruits"]:
        fr = empty("Fruits", parent=root)
        for k in range(P["fruits"]):
            a = (k + 0.5) * (2 * math.pi / P["fruits"]) + rnd.uniform(-0.25, 0.25)
            z = H - 0.38 + rnd.uniform(-0.08, 0.08)
            rr = trunk_radius(z, H, r) + 0.16
            c = (rr * math.cos(a), rr * math.sin(a), z)
            axis = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1.0))
            fruit_bunch(f"Fruit_{k}", c, axis, 0.48 * rnd.uniform(0.94, 1.05), rnd, (m_fruit, m_dark), fr,
                        n_fruitlets=15, sides=4, core_detail=1, fr_size=0.28)
    return root


def build_sawit_0():
    rnd = random.Random(11)
    root = empty("sawit_0")
    m_frond = frond_mat()
    m_bag = mat("M_Polybag", "#2e2a28", roughness=0.6)
    m_soil = mat("M_Soil", "#5a4030")
    m_stem = mat("M_Trunk", "#7a6a3a")
    g = Geo()
    # polybag: bulgy wrinkled cylinder with a folded rim
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
            row.append(g.vert((wr * math.cos(a), wr * math.sin(a), z + (rnd.uniform(-0.012, 0.012) if 0 < j else 0))))
        rows.append(row)
    for j in range(rings):
        for i in range(sides):
            a, b = rows[j][i], rows[j][(i + 1) % sides]
            c, d = rows[j + 1][(i + 1) % sides], rows[j + 1][i]
            mid = (g.v[a] + g.v[c]) * 0.5
            g.face((a, b, c, d), 1, ref=Vector((mid.x, mid.y, 0)), smooth=True)
    # rim folds inward, then soil surface slightly domed
    soil_ring = []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        soil_ring.append(g.vert((R * 0.9 * math.cos(a), R * 0.9 * math.sin(a), Hb - 0.035)))
    for i in range(sides):
        g.face((rows[-1][i], rows[-1][(i + 1) % sides], soil_ring[(i + 1) % sides], soil_ring[i]), 1, ref=UP,
               smooth=True)
    sc = g.vert((0, 0, Hb - 0.015))
    for i in range(sides):
        g.face((soil_ring[i], soil_ring[(i + 1) % sides], sc), 2, ref=UP, smooth=True)
    # short fat seedling base
    stem = []
    for j, (z, rr) in enumerate(((Hb - 0.03, 0.035), (Hb + 0.07, 0.028))):
        stem.append([g.vert((rr * math.cos(a), rr * math.sin(a), z)) for a in (0, 2.09, 4.19)])
    for i in range(3):
        g.face((stem[0][i], stem[0][(i + 1) % 3], stem[1][(i + 1) % 3], stem[1][i]), 3,
               ref=Vector((math.cos(i * 2.09 + 1), math.sin(i * 2.09 + 1), 0)))
    g.face(stem[1], 3, ref=UP)
    # 5 stiff young fronds fanning out evenly
    for i in range(5):
        phi = i * 2 * math.pi / 5 + 0.5 + rnd.uniform(-0.2, 0.2)
        el = lerp(80, 50, (i % 3) / 2) + rnd.uniform(-4, 4)
        base = (0.012 * math.cos(phi), 0.012 * math.sin(phi), Hb + 0.06)
        frond(g, 0, base, phi, el, rnd.uniform(0.34, 0.4), rnd.uniform(18, 30), rnd, n_side=8, lmax=0.17,
              lw=0.055, bare=0.18, rachis_w=0.014, vfold=30, theta0=55, segs=5, leaf_droop=0.12)
    g.obj("sawit_0_body", [m_frond, m_bag, m_soil, m_stem], root)
    return root


def build_tbs():
    rnd = random.Random(21)
    root = empty("tbs")
    m_fruit = mat("M_Fruit", "#e0521f")
    m_dark = mat("M_Dark", "#3a2820")
    m_stalk = mat("M_Stalk", "#b59a5c")
    L = 0.45
    axis = Vector((1.0, 0.15, 0.12))
    body = fruit_bunch("tbs_bunch", (0, 0, 0), axis, L, rnd, (m_fruit, m_dark), root, n_fruitlets=46, sides=5,
                       core_detail=1, fr_size=0.22)
    # stalk stub sticking out of the top end
    ax = axis.normalized()
    st = add_cyl("tbs_stalk", 0.045, 0.16, material=m_stalk, verts=6, radius2=0.035)
    st.rotation_euler = ax.to_track_quat("Z", "Y").to_euler()
    st.location = -ax * (L * 0.5 + 0.02)
    parts = [body, st]
    # a couple of loose fruitlets (brondolan) on the ground
    for k, (x, y) in enumerate(((0.05, -0.27), (-0.14, -0.24), (0.22, 0.2))):
        fl = add_ico(f"tbs_loose{k}", 0.035, subdiv=1, scale=(1.0, 0.85, 0.8),
                     material=m_fruit if k != 1 else m_dark)
        fl.location = (x, y, 0.028)
        parts.append(fl)
    o = join(parts, "tbs_mesh")
    bake(o)
    ground(o)
    o.parent = root
    return root


# ============================================================ generic organic helpers
def bake(o):
    """Apply the object's transform into its mesh (origin -> world origin)."""
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.data.update()
    return o


def blob(name, radius, loc, scale, material, seed, subdiv=2, amp=0.2, freq=1.4, amp2=0.0, freq2=3.0):
    """Lumpy smooth ellipsoid (bush clumps, canopy blobs, boulders)."""
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


def two_tone(o, m_top, m_under, thr=-0.3, m_lit=None, lit_thr=0.75):
    """Assign an underside (and optional lit-top) material by face normal."""
    me = o.data
    me.materials.clear()
    me.materials.append(m_top)
    me.materials.append(m_under)
    if m_lit is not None:
        me.materials.append(m_lit)
    for pgn in me.polygons:
        if pgn.normal.z < thr:
            pgn.material_index = 1
        elif m_lit is not None and pgn.normal.z > lit_thr:
            pgn.material_index = 2
        else:
            pgn.material_index = 0
    return o


def clamp_floor(o, z0=0.0):
    for v in o.data.vertices:
        if v.co.z < z0:
            v.co.z = z0
    o.data.update()
    return o


def tube(g, path, radii, sides, mi, rnd=None, jitter=0.0, cap_top=False, smooth=True, twist=0.0):
    """Generalised cylinder along a list of points."""
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
            row.append(g.vert(p + (S * math.cos(a) + B * math.sin(a)) * rr))
        rows.append((row, p))
    for j in range(n - 1):
        (ra, pa), (rb, pb) = rows[j], rows[j + 1]
        for i in range(sides):
            q = (ra[i], ra[(i + 1) % sides], rb[(i + 1) % sides], rb[i])
            fc = sum((g.v[x] for x in q), Vector()) / 4
            g.face(q, mi if not callable(mi) else mi(j), ref=fc - (pa + pb) * 0.5, smooth=smooth)
    if cap_top:
        row, p = rows[-1]
        tip = g.vert(p + (Vector(path[-1]) - Vector(path[-2])).normalized() * radii[-1] * 0.8)
        for i in range(sides):
            g.face((row[i], row[(i + 1) % sides], tip), mi if not callable(mi) else mi(n - 1),
                   ref=g.v[row[i]] - p, smooth=smooth)
    return rows


def blade(g, base, az, height, width, lean, mi, segs=2, curl=0.0, ref=None):
    """Grass blade / thin leaf: tapered strip that bends outward (segs quads + tip tri)."""
    base = Vector(base)
    d = Vector((math.cos(az), math.sin(az), 0.0))
    side = Vector((-math.sin(az), math.cos(az), 0.0))
    prev = None
    for k in range(segs + 1):
        t = k / (segs + 1)
        bend = lean * t * t
        p = base + d * bend * height + UP * height * t * (1.0 - 0.35 * lean * t) + side * curl * t * t * height
        w = width * (1.0 - t) * 0.5
        cur = (g.vert(p - side * w), g.vert(p + side * w))
        if prev:
            g.face((prev[0], prev[1], cur[1], cur[0]), mi, ref=ref if ref else (d * 0.3 + UP * -0.2 - d))
        prev = cur
    tipp = base + d * lean * height + UP * height * (1.0 - 0.35 * lean) + side * curl * height
    tip = g.vert(tipp)
    g.face((prev[0], prev[1], tip), mi, ref=ref if ref else (d * 0.3 + UP * -0.2 - d))


def leaf_card(g, base, direction, length, width, mi, droop=0.3, fold=0.3):
    """Small folded leaf (4 tris) pointing along `direction`."""
    D = Vector(direction).normalized()
    Sd = D.cross(UP)
    if Sd.length < 1e-3:
        Sd = Vector((1, 0, 0))
    Sd.normalize()
    N = Sd.cross(D).normalized()
    b = Vector(base)
    mid = b + D * length * 0.5 + N * width * fold * 0.5 - UP * length * droop * 0.3
    tip = b + D * length - UP * length * droop
    ib, il, ir, it, im = (g.vert(b), g.vert(mid + Sd * width * 0.5 - N * width * fold),
                          g.vert(mid - Sd * width * 0.5 - N * width * fold), g.vert(tip), g.vert(mid))
    ref = N if N.z >= 0 else -N
    for f in ((ib, il, im), (ib, im, ir), (im, il, it), (im, it, ir)):
        g.face(f, mi, ref=ref)


# ============================================================ bushes (semak belukar)
def kite_leaf(g, base, direction, length, width, mi, droop=0.25, fold=0.35):
    """Cheap folded leaf: 2 triangles hinged along the midrib."""
    D = Vector(direction).normalized()
    Sd = D.cross(UP)
    if Sd.length < 1e-3:
        Sd = Vector((1, 0, 0))
    Sd.normalize()
    N = Sd.cross(D).normalized()
    b = Vector(base)
    mid = b + D * length * 0.45 - UP * length * droop * 0.25
    tip = b + D * length - UP * length * droop
    il = g.vert(mid + Sd * width * 0.5 - N * width * fold)
    ir = g.vert(mid - Sd * width * 0.5 - N * width * fold)
    ib, it = g.vert(b), g.vert(tip)
    ref = N if N.z >= 0 else -N
    g.face((ib, il, it), mi, ref=ref)
    g.face((ib, it, ir), mi, ref=ref)


def build_bush(name, seed, blobs, ferns, grass, twigs, leaves=40):
    """Wild scrub (semak belukar): lumpy mixed-green core bristling with leaves, fern fronds,
    green + dry grass blades and dead sticks -> clearly untended vs. cultivated plants."""
    rnd = random.Random(seed)
    root = empty(name)
    m = [mat("M_Leaf", "#55833a"), mat("M_LeafDark", "#3a6030"), mat("M_LeafLight", "#7ea544"),
         mat("M_Dry", "#a08a58")]
    for x in m:
        leafy(x)
    parts = []
    for i, (x, y, z, r, sx, sy, sz, mi) in enumerate(blobs):
        o = blob(f"{name}_b{i}", r * 0.92, (x, y, z), (sx, sy, sz), m[0 if mi == 2 else mi], seed * 10 + i,
                 subdiv=2, amp=0.22,
                 freq=1.5)
        clamp_floor(o, 0.0)
        parts.append(o)
    g = Geo()
    # leaves bristling out of the clumps in every direction -> ragged silhouette
    placed = 0
    tries = 0
    while placed < leaves and tries < leaves * 4:
        tries += 1
        bx, by, bz, br, sx, sy, sz, bmi = blobs[rnd.randrange(len(blobs))]
        a = rnd.uniform(0, 2 * math.pi)
        el = rnd.uniform(-0.2, 1.2)
        dirv = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
        p = Vector((bx, by, bz)) + Vector((dirv.x * br * sx, dirv.y * br * sy, dirv.z * br * sz)) * 0.75
        if p.z < 0.12:
            continue
        mi = (2, 0, 2, 1, 0)[placed % 5] if bmi != 2 else (0, 2, 1)[placed % 3]
        kite_leaf(g, p, dirv + UP * 0.35 + Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), 0)),
                  rnd.uniform(0.28, 0.44), rnd.uniform(0.14, 0.2), mi, droop=rnd.uniform(0.15, 0.4))
        placed += 1
    for (x, y, z, az, el, L) in ferns:  # pakis fronds arching out of the scrub
        frond(g, 2, (x, y, z), az, el, L, 55, rnd, n_side=7, lmax=0.24, lw=0.07, bare=0.1, rachis_w=0.014,
              vfold=15, theta0=70, segs=4, leaf_droop=0.15)
    for (x, y, n, h) in grass:  # alang-alang: green and dry blades
        for k in range(n):
            blade(g, (x + rnd.uniform(-0.1, 0.1), y + rnd.uniform(-0.1, 0.1), 0.0), rnd.uniform(0, 6.28),
                  h * rnd.uniform(0.7, 1.1), 0.055, rnd.uniform(0.3, 0.9), 3 if k % 3 == 0 else 2, segs=1)
    for (x, y, z, az, el, L) in twigs:  # dead sticks poking out
        e = math.radians(el)
        dvec = Vector((math.cos(az) * math.cos(e), math.sin(az) * math.cos(e), math.sin(e)))
        p0 = Vector((x, y, z))
        p1 = p0 + dvec * L * 0.6
        p2 = p1 + (dvec + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0.2))).normalized() * L * 0.4
        tube(g, [p0, p1, p2], [0.03, 0.022, 0.008], 4, 3, smooth=False)
        fork = p1 + (dvec + Vector((0.5, -0.3, 0.4))).normalized() * L * 0.25
        tube(g, [p1, fork], [0.015, 0.006], 3, 3, smooth=False)
    parts.append(g.obj(name + "_bits", m, None))
    o = join(parts, name + "_mesh")
    bake(o)
    clamp_floor(o, 0.0)
    o.parent = root
    return root


def build_bush_a():
    # tall, lumpy thicket (~1.3 m) with fern fronds, tall grass and a dead stick
    blobs = [(0.0, 0.0, 0.5, 0.5, 1.0, 0.9, 1.05, 0), (0.45, 0.2, 0.32, 0.36, 1.0, 1.0, 0.9, 1),
             (-0.42, -0.1, 0.3, 0.35, 1.1, 0.9, 0.85, 2), (0.08, -0.25, 0.9, 0.32, 1.0, 1.0, 1.05, 2)]
    ferns = [(0.4, -0.3, 0.3, -0.9, 40, 0.8), (-0.5, 0.2, 0.3, 2.6, 35, 0.75)]
    grass = [(0.55, -0.4, 5, 1.0), (-0.45, -0.45, 4, 0.8), (0.1, 0.5, 3, 1.05)]
    twigs = [(0.05, 0.05, 0.6, 0.6, 62, 0.8)]
    return build_bush("bush_a", 31, blobs, ferns, grass, twigs, leaves=62)


def build_bush_b():
    # low, sprawling scrub (~1.0 m) with tall alang-alang and a sideways dead branch
    blobs = [(-0.3, 0.0, 0.4, 0.46, 1.15, 1.0, 1.0, 0), (0.38, 0.12, 0.34, 0.42, 1.1, 1.0, 0.95, 1),
             (0.05, -0.28, 0.28, 0.34, 1.2, 1.0, 0.85, 2), (-0.75, 0.25, 0.22, 0.3, 1.0, 1.0, 0.9, 1)]
    ferns = [(0.62, -0.1, 0.25, -0.2, 30, 0.65), (-0.3, -0.38, 0.3, 4.4, 40, 0.7)]
    grass = [(0.8, 0.3, 6, 1.1), (-0.1, 0.45, 5, 0.95), (-0.9, -0.25, 4, 0.8)]
    twigs = [(-0.2, 0.1, 0.45, 2.9, 25, 0.85)]
    return build_bush("bush_b", 47, blobs, ferns, grass, twigs, leaves=60)


# ============================================================ stump / cleared debris
def build_stump():
    rnd = random.Random(5)
    root = empty("stump")
    m_bark = mat("M_Bark", "#6e5236")
    m_wood = mat("M_Wood", "#d9b27a")
    m_ring = mat("M_WoodDark", "#b8864f")
    m_dry = mat("M_DryLeaf", "#b98a45")
    leafy(m_dry)
    g = Geo()
    sides = 11
    R = 0.16
    prof = [(0.0, 1.35), (0.06, 1.12), (0.15, 1.0), (0.25, 0.97)]
    rows = []
    for z, k in prof:
        row = []
        for i in range(sides):
            a = 2 * math.pi * i / sides
            rr = R * k * rnd.uniform(0.94, 1.06)
            row.append(g.vert((rr * math.cos(a), rr * math.sin(a), z)))
        rows.append(row)
    # slanted saw cut on top
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
    # cut face: bark rim -> light wood -> growth ring -> light heart
    def ring_at(scale, dz=0.0):
        out = []
        for i in range(sides):
            v0 = g.v[top[i]]
            out.append(g.vert((v0.x * scale, v0.y * scale, v0.z + dz)))
        return out
    r1, r2, r3 = ring_at(0.84, 0.004), ring_at(0.55, 0.006), ring_at(0.45, 0.006)
    for ra, rb, mi in ((top, r1, 0), (r1, r2, 1), (r2, r3, 2)):
        for i in range(sides):
            g.face((ra[i], ra[(i + 1) % sides], rb[(i + 1) % sides], rb[i]), mi, ref=UP)
    c = g.vert((0, 0, 0.295 + 0.006))
    for i in range(sides):
        g.face((r3[i], r3[(i + 1) % sides], c), 1, ref=UP)
    # roots spreading over the ground
    for k in range(4):
        a = k * 1.57 + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        p0 = d * R * 0.55 + UP * 0.15
        p1 = d * R * 1.3 + UP * 0.05
        p2 = d * R * 1.85 + UP * 0.008
        tube(g, [p0, p1, p2], [0.075, 0.055, 0.036], 6, 0, smooth=True, cap_top=True)
    # dry leaves + a wood chip
    for k, (x, y, rz, s) in enumerate(((0.3, -0.12, 0.4, 1.0), (-0.26, -0.22, 2.2, 0.85), (0.02, 0.05, 1.2, 0.7))):
        z = 0.02 if k < 2 else 0.31
        dvec = Vector((math.cos(rz), math.sin(rz), 0.05))
        leaf_card(g, (x, y, z), dvec, 0.2 * s, 0.1 * s, 3, droop=-0.1, fold=0.25)
    o = g.obj("stump_mesh", [m_bark, m_wood, m_ring, m_dry], root)
    chip = add_box("stump_chip", (0.08, 0.05, 0.025), loc=(-0.22, 0.2, 0.012), rot=(0, 0, 0.6), material=m_wood,
                   bevel=0.008)
    chip2 = add_box("stump_chip2", (0.06, 0.04, 0.02), loc=(0.18, 0.26, 0.01), rot=(0, 0, 2.0), material=m_wood,
                    bevel=0.006)
    o = join([o, chip, chip2], "stump_mesh")
    bake(o)
    clamp_floor(o, 0.0)
    o.parent = root
    return root


# ============================================================ big broadleaf shade tree
def build_tree_big():
    rnd = random.Random(9)
    root = empty("tree_big")
    m_bark = mat("M_Bark", "#7a5c3e")
    m_fol = mat("M_Foliage", "#5a8c38")
    m_dark = mat("M_FoliageDark", "#3d6630")
    m_lit = mat("M_FoliageLight", "#80ab47")
    g = Geo()
    # trunk: flared base, slight S-bend, splits into 3 limbs
    trunk = [(0, 0, 0), (0.05, 0.0, 0.5), (0.0, 0.05, 1.3), (-0.1, 0.05, 2.1), (-0.05, 0.0, 2.6)]
    tube(g, trunk, [0.46, 0.33, 0.28, 0.26, 0.24], 9, 0, rnd=rnd, jitter=0.05)
    limbs = [((-0.05, 0, 2.4), (0.8, 0.2, 3.3), (1.5, 0.3, 3.9)),
             ((-0.05, 0, 2.4), (-0.8, 0.4, 3.4), (-1.4, 0.6, 3.9)),
             ((-0.05, 0, 2.4), (0.1, -0.6, 3.5), (0.2, -1.1, 4.0)),
             ((-0.05, 0, 2.5), (-0.2, 0.3, 3.6), (-0.3, 0.9, 4.4))]
    for lp in limbs:
        tube(g, lp, [0.19, 0.13, 0.07], 6, 0, rnd=rnd, jitter=0.05)
    # root flares
    for k in range(5):
        a = k * 2 * math.pi / 5 + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        tube(g, [d * 0.25 + UP * 0.35, d * 0.55 + UP * 0.1, d * 0.8 + UP * 0.0], [0.13, 0.09, 0.03], 5, 0,
             smooth=True)
    parts = [g.obj("tree_trunk", [m_bark], None)]
    # canopy: clumped rounded blobs, lit tops / dark undersides
    canopy = [(0.1, 0.0, 4.5, 1.6, 1.15, 1.1, 0.78, 0), (1.7, 0.35, 3.95, 1.2, 1.0, 1.0, 0.8, 0),
              (-1.6, 0.7, 4.0, 1.18, 1.0, 1.0, 0.8, 0), (0.3, -1.5, 3.9, 1.12, 1.0, 1.0, 0.8, 0),
              (-0.45, 1.6, 4.45, 1.02, 1.0, 1.0, 0.82, 1), (0.4, 0.15, 5.3, 1.05, 1.0, 1.0, 0.78, 1)]
    for i, (x, y, z, r, sx, sy, sz, lit) in enumerate(canopy):
        o = blob(f"tree_can{i}", r, (x, y, z), (sx, sy, sz), m_fol, 90 + i, subdiv=3, amp=0.14, freq=1.6,
                 amp2=0.05, freq2=4.0)
        two_tone(o, m_lit if lit else m_fol, m_dark, thr=-0.45)
        parts.append(o)
    o = join(parts, "tree_big_mesh")
    bake(o)
    o.parent = root
    return root


# ============================================================ coconut palm (kelapa)
def build_coconut():
    rnd = random.Random(17)
    root = empty("coconut")
    m_frond = mat("M_Frond", "#7ea63c")
    leafy(m_frond)
    m_trunk = mat("M_Trunk", "#a08e70")
    m_ring = mat("M_TrunkRing", "#6f604b")
    m_nut = mat("M_Coconut", "#8fa232")
    g = Geo()
    H, lean = 5.7, 1.35
    bands = 20
    path, radii = [], []
    for j in range(bands):
        for k in range(2):  # ridge row + plain row -> dark ring band between them
            t = (j + (0.25 if k else 0.0)) / bands
            x = lean * (1 - (1 - t) ** 2)
            z = H * t
            r = lerp(0.2, 0.13, t) + 0.1 * max(0.0, 1 - t * 8) ** 2
            path.append((x, 0.1 * math.sin(t * 3), z))
            radii.append(r * (1.08 if k == 0 else 1.0))
    path.append((lean, 0.1 * math.sin(3), H))
    radii.append(0.12)
    # faces from ridge row (k=0) to plain row (k=1) are the dark ring band
    tube(g, path, radii, 8, lambda j: 1 if j % 2 == 0 else 0, smooth=True)
    top = Vector(path[-1])
    # crown heart
    heart = [top + Vector((0.13 * math.cos(a), 0.13 * math.sin(a), -0.05)) for a in (0, 1.57, 3.14, 4.71)]
    hi = [g.vert(p) for p in heart]
    ht = g.vert(top + UP * 0.35)
    for i in range(4):
        g.face((hi[i], hi[(i + 1) % 4], ht), 1, ref=(g.v[hi[i]] + g.v[hi[(i + 1) % 4]]) * 0.5 - top)
    # fronds: long, strongly arching, leaflets hanging down (inverted V) -> droopy mop
    n = 14
    for i in range(n):
        f = i / (n - 1)
        phi = i * GOLDEN + rnd.uniform(-0.1, 0.1)
        el = lerp(62, -5, f) + rnd.uniform(-5, 5)
        dr = lerp(55, 105, f) + rnd.uniform(-8, 8)
        L = 3.0 * lerp(0.8, 1.0, min(1.0, f * 2)) * rnd.uniform(0.93, 1.05)
        base = top + Vector((0.08 * math.cos(phi), 0.08 * math.sin(phi), 0.05 - 0.15 * f))
        frond(g, 2, base, phi, el, L, dr, rnd, n_side=18, lmax=1.0, lw=0.09, bare=0.12, vfold=-35,
              theta0=72, rachis_w=0.05, segs=6, leaf_droop=0.75, twist=rnd.uniform(-10, 10))
    body = g.obj("coconut_body", [m_trunk, m_ring, m_frond, m_nut], None)
    parts = [body]
    # green coconuts clustered under the crown
    for k in range(6):
        a = k * 1.1 + rnd.uniform(-0.2, 0.2)
        rr = 0.24 + 0.06 * (k % 2)
        c = top + Vector((rr * math.cos(a), rr * math.sin(a), -0.32 - 0.1 * (k % 3)))
        nut = add_ico(f"nut{k}", 0.16, loc=c, subdiv=2, scale=(1.0, 1.0, 1.12), material=m_nut)
        parts.append(nut)
    o = join(parts, "coconut_mesh")
    bake(o)
    o.parent = root
    return root


# ============================================================ banana plant (pisang)
def banana_leaf(g, base, az, el, L, W, rnd, mi, torn=False, segs=6, droop=70):
    """Big paddle leaf: petiole + oblong blade with raised midrib, edges curling down.
    Torn leaves are split into ragged strips along the veins."""
    base = Vector(base)
    pet = 0.25
    pts = [base]
    for i in range(segs + 1):
        t = i / segs
        a = math.radians(el - droop * t ** 1.3)
        d = Vector((math.cos(az) * math.cos(a), math.sin(az) * math.cos(a), math.sin(a)))
        pts.append(pts[-1] + d * ((pet if i == 0 else L / segs)))
    tube(g, [pts[0], pts[1]], [0.03, 0.022], 4, mi, smooth=True)
    stations = pts[1:]
    mids, lefts, rights, frames = [], [], [], []
    for i, p in enumerate(stations):
        t = i / segs
        T = (stations[min(i + 1, segs)] - stations[max(i - 1, 0)]).normalized()
        S = T.cross(UP)
        if S.length < 1e-3:
            S = Vector((-math.sin(az), math.cos(az), 0))
        S.normalize()
        N = S.cross(T).normalized()
        w = W * 0.5 * (min(1.0, t * 4.0 + 0.12) ** 0.6) * (max(0.0, 1.0 - t ** 5)) ** 0.5
        drop = w * 0.4
        mids.append(g.vert(p + N * 0.02))
        lefts.append(p + S * w - N * drop)
        rights.append(p - S * w - N * drop)
        frames.append((S, N))
    li = [g.vert(x) for x in lefts]
    ri = [g.vert(x) for x in rights]
    for i in range(segs):
        S, N = frames[i]
        for edge, idx in ((lefts, li), (rights, ri)):
            if torn and 0 < i < segs - 1 and rnd.random() < 0.8:
                # ragged strip: outer edge sags and a gap opens toward the next strip
                ea, eb = edge[i], edge[i + 1]
                sag = -N * rnd.uniform(0.06, 0.16) - UP * rnd.uniform(0.02, 0.08)
                ia = g.vert(ea + sag * 0.6 + (eb - ea) * 0.1)
                ib = g.vert(eb + sag - (eb - ea) * 0.14)
            else:
                ia, ib = idx[i], idx[i + 1]
            g.face((mids[i], ia, ib, mids[i + 1]), mi, ref=N, smooth=True)
    return pts


def build_banana():
    rnd = random.Random(23)
    root = empty("banana")
    m_leaf = mat("M_Frond", "#6fa640")
    leafy(m_leaf)
    m_stem = mat("M_Stem", "#9aa655")
    m_dry = mat("M_DryLeaf", "#a3814a")
    leafy(m_dry)
    m_fruit = mat("M_Banana", "#a6bb3c")
    g = Geo()
    # pseudostem (main) + a small sucker
    main_top = Vector((0.06, 0.02, 1.35))
    tube(g, [(0, 0, 0), (0.02, 0.0, 0.5), (0.05, 0.02, 1.0), tuple(main_top)], [0.14, 0.12, 0.1, 0.085], 8, 1,
         rnd=rnd, jitter=0.04, cap_top=True)
    suck_top = Vector((0.42, -0.25, 0.55))
    tube(g, [(0.4, -0.25, 0), (0.41, -0.25, 0.3), tuple(suck_top)], [0.07, 0.055, 0.045], 6, 1, cap_top=True)
    # leaves on the main stem
    leaves = 7
    for i in range(leaves):
        f = i / (leaves - 1)
        az = i * GOLDEN + 0.3
        el = lerp(78, 30, f) + rnd.uniform(-4, 4)
        L = lerp(1.25, 1.55, min(1.0, f * 2)) * rnd.uniform(0.92, 1.05)
        banana_leaf(g, main_top - UP * 0.1 * f, az, el, L, lerp(0.42, 0.5, f), rnd, 0,
                    torn=(i in (2, 4, 5)), droop=lerp(35, 80, f))
    for i in range(3):
        az = i * 2.2 - 0.4
        banana_leaf(g, suck_top, az, lerp(75, 45, i / 2), 0.6, 0.24, rnd, 0, droop=40, segs=4)
    # old dead leaves hanging down against the pseudostem
    for k, az in enumerate((2.5, 4.5)):
        banana_leaf(g, main_top - UP * (0.12 + 0.15 * k), az, -62, 0.8 - 0.15 * k, 0.34, rnd, 2, torn=True,
                    droop=18, segs=4)
    # hanging bunch: stalk arching out toward the camera side, hands of green bananas
    stalk = [main_top - UP * 0.05, main_top + Vector((0.05, -0.28, 0.08)), main_top + Vector((0.06, -0.45, -0.25)),
             main_top + Vector((0.06, -0.47, -0.72))]
    tube(g, stalk, [0.035, 0.032, 0.028, 0.02], 5, 1)
    for h in range(3):
        cz = stalk[2].z - 0.06 - h * 0.14
        cc = Vector((stalk[2].x, stalk[2].y, cz))
        for k in range(6):
            a = k * 1.047 + h * 0.5
            d = Vector((math.cos(a), math.sin(a), 0))
            p0 = cc + d * 0.035
            p1 = p0 + d * 0.08 + UP * 0.03
            p2 = p1 + d * 0.035 + UP * 0.1
            tube(g, [p0, p1, p2], [0.024, 0.027, 0.01], 4, 3, smooth=True)
    o = g.obj("banana_mesh", [m_leaf, m_stem, m_dry, m_fruit], root)
    return root


# ============================================================ rocks
def boulder(name, size, seed, material, flat=0.7, stretch=(1.0, 0.82), subdiv=3, sink=0.1, loc=(0, 0, 0)):
    """Soft rounded boulder: lumpy, a bit flattened, broad flat-ish top, flat bottom at z=0."""
    h = size * flat
    o = blob(name, 0.5, (0, 0, 0), (size * stretch[0], size * stretch[1], h), material, seed, subdiv=subdiv,
             amp=0.3, freq=0.85, amp2=0.07, freq2=2.2)
    rnd = random.Random(seed)
    # a gently sloped "shoulder" plane squashes one upper side -> reads as stone, not an egg
    pn = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 1.6)).normalized()
    top = max(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        if v.co.z < 0:  # bottom-heavy: rocks sit, they don't balance
            v.co.x *= 1.08
            v.co.y *= 1.08
        d = v.co.dot(pn) - top * 0.72
        if d > 0:
            v.co -= pn * d * 0.75
        if v.co.z > top * 0.45:  # broad, softly flattened top
            v.co.z = top * 0.45 + (v.co.z - top * 0.45) * 0.6
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin + h * sink
        v.co += Vector(loc)
    o.data.update()
    clamp_floor(o, loc[2] if loc else 0.0)
    return o


def build_rock(name, size, seed, extras=()):
    root = empty(name)
    m_rock = mat("M_Rock", "#8e8b80")
    m_dark = mat("M_RockDark", "#737067")
    parts = [boulder(name + "_main", size, seed, m_rock)]
    for i, (dx, dy, s, dark) in enumerate(extras):
        parts.append(boulder(f"{name}_x{i}", size * s, seed + 11 * (i + 1), m_dark if dark else m_rock,
                             subdiv=2, flat=0.55, loc=(size * dx, size * dy, 0)))
    o = join(parts, name + "_mesh") if len(parts) > 1 else parts[0]
    o.name = name + "_mesh"
    bake(o)
    clamp_floor(o, 0.0)
    o.parent = root
    return root


# ============================================================ cliff / rocky outcrop
def slab(name, size, loc, rot, seed, material, bevel=0.2, amp=0.14):
    """Rounded, lumpy rock slab: subdivided box, bevelled edges, low-frequency warp."""
    import bmesh
    o = common.add_box(name, size, loc=(0, 0, 0), material=material)
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
    bake(o)
    shade_smooth(o)
    return o


def build_cliff_a():
    """Stepped outcrop of three strata of rounded slabs (7 x 3 x 2.5 m), grass on the ledges."""
    rnd = random.Random(41)
    root = empty("cliff_a")
    m_c = mat("M_Cliff", "#676863")
    m_top = mat("M_CliffTop", "#979890")
    m_dk = mat("M_CliffDark", "#4f504c")
    m_grass = mat("M_Grass", "#6f9a45")
    leafy(m_grass)
    parts = []
    # (x, y, z_bottom, w, d, h) per slab; each stratum steps back (+y) and up
    strata = [  # (x, y, z_bottom, w, d, h, rot_z): long slabs, joints offset between strata
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
            two_tone(o, m_c, m_dk, thr=-0.35, m_lit=m_top, lit_thr=0.6)
            parts.append(o)
            k += 1
    # a split-off slab leaning against the foot
    o = slab("cliff_lean", (1.3, 0.35, 1.0), (-3.45, -1.2, 0.42), (0.35, 0.0, 0.5), 99, m_c, bevel=0.1, amp=0.1)
    two_tone(o, m_c, m_dk, thr=-0.35, m_lit=m_top, lit_thr=0.6)
    parts.append(o)
    for i, (x, y, s) in enumerate(((-2.6, -1.55, 0.6), (0.6, -1.6, 0.5), (2.75, -1.45, 0.6), (-1.3, -1.65, 0.35))):
        o = boulder(f"cliff_foot{i}", s, 60 + i, m_c, subdiv=2, loc=(x, y, 0))
        two_tone(o, m_c, m_dk, thr=-0.35, m_lit=m_top, lit_thr=0.6)
        parts.append(o)
    # grass tufts growing on the ledges and at the foot
    g = Geo()
    tufts = [(-2.9, -0.9, 0.95, 7), (-0.8, -0.75, 0.85, 6), (1.3, -0.5, 1.58, 6), (-2.9, 0.1, 1.72, 5),
             (0.3, 0.4, 2.45, 6), (2.6, -0.2, 0.9, 5), (-1.0, -1.5, 0.0, 7), (1.9, -1.6, 0.0, 6),
             (3.4, -1.0, 0.0, 6)]
    for (x, y, z, n) in tufts:
        for b in range(n):
            blade(g, (x + rnd.uniform(-0.15, 0.15), y + rnd.uniform(-0.15, 0.15), z - 0.04), rnd.uniform(0, 6.28),
                  rnd.uniform(0.25, 0.4), 0.07, rnd.uniform(0.3, 0.7), 0, segs=1)
    parts.append(g.obj("cliff_grass", [m_grass], None))
    o = join(parts, "cliff_a_mesh")
    bake(o)
    clamp_floor(o, 0.0)
    o.parent = root
    return root


# ============================================================ grass tuft / flowers
def build_grass_tuft():
    rnd = random.Random(3)
    root = empty("grass_tuft")
    m = mat("M_Grass", "#78a84a")
    m2 = mat("M_GrassLight", "#a3c45a")
    for x in (m, m2):
        leafy(x)
    g = Geo()
    n = 15
    for k in range(n):
        a = k * GOLDEN + rnd.uniform(-0.3, 0.3)
        r = rnd.uniform(0.0, 0.07)
        base = (r * math.cos(a), r * math.sin(a), 0.0)
        h = rnd.uniform(0.22, 0.36) * (1.0 - 0.5 * r / 0.07 * 0.5)
        blade(g, base, a, h, rnd.uniform(0.04, 0.055), rnd.uniform(0.25, 0.75), 1 if k % 4 == 0 else 0, segs=2,
              curl=rnd.uniform(-0.1, 0.1))
    g.obj("grass_tuft_mesh", [m, m2], root)
    return root


def build_flowers():
    rnd = random.Random(8)
    root = empty("flowers")
    m_stem = mat("M_Stem", "#5f9440")
    m_w = mat("M_PetalWhite", "#f7f2e6")
    m_y = mat("M_PetalYellow", "#f4c542")
    m_p = mat("M_PetalPink", "#ef8fae")
    for x in (m_stem, m_w, m_y, m_p):
        leafy(x)
    g = Geo()
    # (x, y, height, petal mat, centre mat, radius)
    fl = [(0.0, 0.0, 0.26, 1, 2, 0.055), (0.12, 0.08, 0.2, 3, 2, 0.05), (-0.11, 0.07, 0.22, 2, 1, 0.045),
          (0.07, -0.12, 0.16, 1, 2, 0.045), (-0.14, -0.08, 0.18, 3, 2, 0.045), (0.2, -0.04, 0.13, 2, 1, 0.04),
          (-0.02, 0.17, 0.15, 1, 2, 0.04), (-0.22, 0.12, 0.11, 3, 2, 0.035)]
    for (x, y, h, pm, cm, r) in fl:
        lean = Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.05, 0.02), 0))
        top = Vector((x, y, h)) + lean
        # stem: thin triangular prism
        tube(g, [(x, y, 0), tuple(top)], [0.008, 0.006], 3, 0, smooth=False)
        # flower head: 5-petal star tilted slightly toward the camera
        tilt = Matrix.Rotation(math.radians(rnd.uniform(10, 25)), 3, Vector((1, 0, 0))) @ \
            Matrix.Rotation(rnd.uniform(0, 6.28), 3, UP)
        ctr = g.vert(top + tilt @ Vector((0, 0, 0.004)))
        ring = []
        for i in range(5):  # each petal: notch + two rounded lobe corners
            a0 = i * 2 * math.pi / 5
            for fa, rr, dz in ((0.0, 0.42, 0.0), (0.24, 1.0, 0.008), (0.76, 1.0, 0.008)):
                a = a0 + fa * 2 * math.pi / 5
                ring.append(g.vert(top + tilt @ Vector((r * rr * math.cos(a), r * rr * math.sin(a), dz))))
        for i in range(15):
            g.face((ring[i], ring[(i + 1) % 15], ctr), pm, ref=tilt @ UP)
        # centre bump
        cb = [g.vert(top + tilt @ Vector((r * 0.3 * math.cos(a), r * 0.3 * math.sin(a), 0.008))) for a in (0, 2.1, 4.2)]
        ct = g.vert(top + tilt @ Vector((0, 0, 0.02)))
        for i in range(3):
            g.face((cb[i], cb[(i + 1) % 3], ct), cm, ref=tilt @ UP)
    # leaves at the base
    for k in range(10):
        a = k * GOLDEN
        r = rnd.uniform(0.02, 0.18)
        blade(g, (r * math.cos(a), r * math.sin(a), 0.0), a, rnd.uniform(0.07, 0.12), 0.045, 0.9, 0, segs=1)
    g.obj("flowers_mesh", [m_stem, m_w, m_y, m_p], root)
    return root


# ============================================================ registry
ASSETS = {}


def asset(name):
    def deco(fn):
        ASSETS[name] = fn
        return fn
    return deco


SAWIT3_VIEWS = (("game", 55, 0, (0, 0, 2.2), 7.5), ("side", 8, 0, (0, 0, 2.6), 7.0),
                ("trunk", 12, 30, (0, 0, 1.9), 3.2), ("crown", 40, 30, (0, 0, 2.7), 2.6),
                ("far", 55, 0, (0, 0, 2.0), 16.0))


@asset("sawit_0")
def _a_sawit_0():
    root = build_sawit_0()
    finish(root, "sawit_0", icon="icon_bibit", icon_kw=dict(pitch_deg=25, margin=1.0),
           views=(("game", 55, 0, (0, 0, 0.35), 1.1), ("side", 8, 0, (0, 0, 0.4), 1.1)))


@asset("sawit_1")
def _a_sawit_1():
    finish(build_palm("sawit_1", SAWIT_STAGES["sawit_1"], seed=5), "sawit_1",
           views=(("game", 55, 0, (0, 0, 0.6), 3.0), ("side", 8, 0, (0, 0, 0.8), 3.0)))


@asset("sawit_2")
def _a_sawit_2():
    finish(build_palm("sawit_2", SAWIT_STAGES["sawit_2"], seed=7), "sawit_2",
           views=(("game", 55, 0, (0, 0, 1.2), 5.0), ("side", 8, 0, (0, 0, 1.5), 5.0)))


@asset("sawit_3")
def _a_sawit_3():
    finish(build_palm("sawit_3", SAWIT_STAGES["sawit_3"], seed=3), "sawit_3", views=SAWIT3_VIEWS)


@asset("tbs")
def _a_tbs():
    finish(build_tbs(), "tbs", icon="icon_tbs", icon_kw=dict(pitch_deg=48, yaw_deg=20, margin=0.95), views=(("game", 55, 0, (0, 0, 0.15), 0.9),
                                                        ("side", 20, 60, (0, 0, 0.15), 0.9)))


def _simple(name, builder, views=()):
    def fn():
        finish(builder(), name, views=views)
    ASSETS[name] = fn


_simple("bush_a", build_bush_a, views=(("game", 55, 0, (0, 0, 0.5), 2.2), ("side", 10, 0, (0, 0, 0.6), 2.2)))
_simple("bush_b", build_bush_b, views=(("game", 55, 0, (0, 0, 0.4), 2.4), ("side", 10, 0, (0, 0, 0.5), 2.4)))
_simple("stump", build_stump, views=(("game", 55, 0, (0, 0, 0.12), 0.9), ("side", 25, 30, (0, 0, 0.15), 0.9)))
_simple("tree_big", build_tree_big, views=(("game", 55, 0, (0, 0, 3.0), 8.5), ("side", 8, 0, (0, 0, 3.0), 8.0)))
_simple("coconut", build_coconut, views=(("game", 55, 0, (0.7, 0, 3.5), 8.0), ("side", 8, 0, (0.7, 0, 3.2), 7.5)))
_simple("banana", build_banana, views=(("game", 55, 0, (0, 0, 1.2), 3.8), ("side", 8, 0, (0, 0, 1.3), 3.6)))
_simple("rock_a", lambda: build_rock("rock_a", 0.5, 3), views=(("game", 55, 0, (0, 0, 0.1), 0.9),))
_simple("rock_b", lambda: build_rock("rock_b", 1.0, 7, extras=((0.62, -0.25, 0.28, True),)),
        views=(("game", 55, 0, (0.1, 0, 0.2), 1.8),))
_simple("rock_c", lambda: build_rock("rock_c", 2.0, 13, extras=((-0.55, -0.35, 0.34, False), (0.6, -0.2, 0.18, True))),
        views=(("game", 55, 0, (0, 0, 0.4), 3.4), ("side", 10, 0, (0, 0, 0.5), 3.4)))
_simple("cliff_a", build_cliff_a, views=(("game", 55, 0, (0, 0, 1.0), 8.5), ("side", 15, 20, (0, 0, 1.2), 8.5)))
_simple("grass_tuft", build_grass_tuft, views=(("game", 55, 0, (0, 0, 0.12), 0.6), ("side", 10, 0, (0, 0, 0.16), 0.6)))
_simple("flowers", build_flowers, views=(("game", 55, 0, (0, 0, 0.1), 0.65), ("side", 15, 0, (0, 0, 0.12), 0.65)))


def main(argv):
    names = argv or list(ASSETS)
    for n in names:
        if n not in ASSETS:
            raise SystemExit(f"unknown asset {n!r}; choose from {list(ASSETS)}")
    for n in names:
        reset_scene()
        ASSETS[n]()


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("-")])

#!/usr/bin/env python3
"""Sawit The Franchise - chibi villager characters (Animal Crossing-ish proportions).

Run:  python3 blender/characters.py              all characters + lineup preview
      python3 blender/characters.py kakek ibu    only these (no lineup)
      python3 blender/characters.py --lineup     only the lineup preview

Every character is built from a handful of procedural primitives (lathe, ellipsoid,
hair/hat shell, tube, surface decal) and assembled into the rig the game animates:

  char_<name>        Empty at the feet centre (z = 0)
    Hips             Empty at hip height
      Body           mesh (torso + clothes)
      LegL / LegR    Empty at the hip joint   -> LegL_Mesh / LegR_Mesh
      ArmL / ArmR    Empty at the shoulder    -> ArmL_Mesh / ArmR_Mesh
        HandR        (ArmR only) Empty at the right hand; held tools attach here
      Head           Empty at the neck        -> Head_Mesh (face, hair, hat)

Front = -Y, the character's LEFT = +X. All empties have zero rotation / unit scale,
so rotating a limb empty about its local X swings it forward/back from the joint.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import common  # noqa: E402
from common import (PREVIEW_DIR, all_descendants, count_tris, empty, export_glb, link,  # noqa: E402
                    mat, render_icon, render_preview, reset_scene)

TAU = math.tau


# --------------------------------------------------------------------------- math
def rad(d):
    return math.radians(d)


def sstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def T(x, y=0.0, z=0.0):
    if isinstance(x, Vector):
        return Matrix.Translation(x)
    return Matrix.Translation((x, y, z))


def R(axis, deg):
    return Matrix.Rotation(rad(deg), 4, axis)


def orient(p, n, up=(0.0, 0.0, 1.0)):
    """Matrix placing a local shape at p with its local -Y along the outward normal n."""
    y = -Vector(n).normalized()
    x = y.cross(Vector(up))
    if x.length < 1e-6:
        x = Vector((1.0, 0.0, 0.0))
    x.normalize()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p
    return m


def align_z(p, d):
    """Matrix placing a local shape at p with its local +Z along direction d."""
    m = Vector(d).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    m.translation = p
    return m


# --------------------------------------------------------------------------- materials
# Every material name maps to exactly one colour, so characters can share a scene.
MATS = {
    "M_Skin": ("#f0b57d", 0.75), "M_SkinTan": ("#d89a66", 0.75),
    "M_Dark": ("#2b2522", 0.35), "M_Blush": ("#f5958c", 0.9),
    "M_Straw": ("#e8c67c", 0.9), "M_Batik": ("#c56a2e", 0.9), "M_Khaki": ("#bba570", 0.9),
    "M_Bamboo": ("#caa053", 0.9), "M_FadedShirt": ("#d6d3c6", 0.9), "M_Sarong": ("#8b5230", 0.9),
    "M_Hijab": ("#c9848d", 0.9), "M_Dress": ("#f59a78", 0.9), "M_Floral": ("#fff2da", 0.9),
    "M_White": ("#f7f3ea", 0.85), "M_Trousers": ("#3a3f52", 0.9), "M_Gold": ("#eab93a", 0.4),
    "M_HairGrey": ("#bdbab3", 0.8), "M_Kebaya": ("#f5e8cf", 0.9), "M_Kain": ("#4f4a28", 0.9),
    "M_GreenTee": ("#5cc046", 0.9), "M_Jeans": ("#4f78b0", 0.9), "M_SarongRed": ("#a63a4c", 0.9),
    "M_WorkBlue": ("#4a74a8", 0.9), "M_Olive": ("#7c7b45", 0.9), "M_CapBlue": ("#2f70d8", 0.7),
    "M_TeeOrange": ("#f38a2b", 0.9), "M_Ink": ("#3d4e66", 0.8), "M_Army": ("#5f6b43", 0.9),
    "M_Hawaii": ("#22aaa6", 0.9), "M_HawaiiFlower": ("#ffd84a", 0.9), "M_Tweed": ("#8d8069", 0.9),
    "M_Uniform": ("#8e6d44", 0.9), "M_HardHat": ("#f5c43f", 0.5), "M_Dusty": ("#aba18a", 0.9),
    "M_WorkPants": ("#585c66", 0.9),
}


def M(name):
    col, rough = MATS[name]
    return mat(name, col, roughness=rough)


# --------------------------------------------------------------------------- primitives
# Each primitive returns (verts, faces) in local space; xf() moves them.
def xf(vf, m):
    return [m @ Vector(v) for v in vf[0]], vf[1]


def lathe_vf(prof, seg=16, sx=1.0, sy=1.0, phase=0.0, deform=None):
    """Revolve a (r, z) profile around Z. r == 0 makes a pole. Angle 0 = front (-Y),
    90 deg = +X. Profiles walked 'bottom -> outside -> top' get outward normals."""
    verts, faces, rings = [], [], []
    for (r, z) in prof:
        if r <= 1e-6:
            p = Vector((0.0, 0.0, z))
            if deform:
                p = deform(p, 0.0, z)
            rings.append([len(verts)])
            verts.append(p)
            continue
        ring = []
        for i in range(seg):
            a = TAU * i / seg + phase
            p = Vector((r * sx * math.sin(a), -r * sy * math.cos(a), z))
            if deform:
                p = deform(p, a, z)
            ring.append(len(verts))
            verts.append(p)
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            faces += [(A[0], B[(i + 1) % seg], B[i]) for i in range(seg)]
        elif len(B) == 1:
            faces += [(A[i], A[(i + 1) % seg], B[0]) for i in range(seg)]
        else:
            faces += [(A[i], A[(i + 1) % seg], B[(i + 1) % seg], B[i]) for i in range(seg)]
    return verts, faces


def ellipsoid_vf(radii, seg=12, rings=8, clip_top=None):
    rx, ry, rz = radii
    prof = [(rx * math.sin(math.pi * j / rings), -rz * math.cos(math.pi * j / rings)) for j in range(rings + 1)]
    prof[0], prof[-1] = (0.0, -rz), (0.0, rz)
    v, f = lathe_vf(prof, seg, 1.0, ry / rx)
    if clip_top is not None:  # flatten the top (half-lidded eyes, D-shaped mouths)
        for p in v:
            p.z = min(p.z, clip_top)
    return v, f


def box_vf(sx, sy, sz):
    """Axis aligned box centred on the origin (half sizes)."""
    k = math.sqrt(2.0)
    return lathe_vf([(0.0, -sz), (k, -sz), (k, sz), (0.0, sz)], 4, sx, sy, phase=math.pi / 4)


def shell_vf(radii, tmax, seg=24, rings=6, rim=0.93, rmod=None, tmin=0.0):
    """Ellipsoidal cap from the top pole down to polar angle tmax(phi) (phi 0 = front).
    `rim` adds a ring tucked inward so the edge reads as a thick fabric/hair edge.
    tmin > 0 leaves the top open (a band of hair peeking out under a hat)."""
    rx, ry, rz = radii

    def pt(phi, th, s=1.0):
        if rmod:
            s *= rmod(phi, th)
        return Vector((math.sin(th) * math.sin(phi) * rx * s, -math.sin(th) * math.cos(phi) * ry * s,
                       math.cos(th) * rz * s))

    verts = [] if tmin else [pt(0.0, 0.0)]
    ring_ids = []
    for j in range(0 if tmin else 1, rings + 1):
        ring = []
        for i in range(seg):
            phi = TAU * i / seg
            ring.append(len(verts))
            tm = tmax(phi)
            verts.append(pt(phi, tmin + (tm - tmin) * j / rings if tmin else tm * j / rings))
        ring_ids.append(ring)
    if rim:
        ring = []
        for i in range(seg):
            phi = TAU * i / seg
            ring.append(len(verts))
            verts.append(pt(phi, tmax(phi) + 0.03, rim))
        ring_ids.append(ring)
    R1 = ring_ids[0]
    faces = [] if tmin else [(R1[i], R1[(i + 1) % seg], 0) for i in range(seg)]
    for B, A in zip(ring_ids, ring_ids[1:]):
        faces += [(A[i], A[(i + 1) % seg], B[(i + 1) % seg], B[i]) for i in range(seg)]
    return verts, faces


def tube_vf(pts, radius, seg=6, closed=False, up=(0.0, 0.0, 1.0), caps=True):
    """Tube through points. radius: float, list of floats or list of (r_side, r_up)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    up = Vector(up)

    def rr(i):
        r = radius[i] if isinstance(radius, list) else radius
        return (r, r) if isinstance(r, (int, float)) else r

    verts, faces, rings = [], [], []
    for i, p in enumerate(pts):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        nn = up - up.dot(t) * t
        if nn.length < 1e-6:
            nn = Vector((1.0, 0.0, 0.0))
        nn.normalize()
        b = t.cross(nn)
        rw, rh = rr(i)
        ring = []
        for j in range(seg):
            th = TAU * j / seg
            ring.append(len(verts))
            verts.append(p + b * (rw * math.cos(th)) + nn * (rh * math.sin(th)))
        rings.append(ring)
    for i in range(n if closed else n - 1):
        A, B = rings[i], rings[(i + 1) % n]
        faces += [(A[j], B[j], B[(j + 1) % seg], A[(j + 1) % seg]) for j in range(seg)]
    if caps and not closed:
        c0 = len(verts)
        verts.append(pts[0].copy())
        faces += [(c0, rings[0][j], rings[0][(j + 1) % seg]) for j in range(seg)]
        c1 = len(verts)
        verts.append(pts[-1].copy())
        faces += [(c1, rings[-1][(j + 1) % seg], rings[-1][j]) for j in range(seg)]
    return verts, faces


def bill_vf(w, l, t, n=10, bend=0.0):
    """Flat D-shaped cap bill: attached (straight) edge along X at y=0, rounded tip at y=-l."""
    outline = [(w * math.cos(math.pi * i / n), -l * math.sin(math.pi * i / n)) for i in range(n + 1)]
    outline = outline[::-1]  # x from -w to +w along the rounded edge
    verts = []
    for (x, y) in outline:
        verts.append(Vector((x, y, t - bend * x * x)))
    for (x, y) in outline:
        verts.append(Vector((x, y, -t - bend * x * x)))
    k = len(outline)
    faces = [tuple(range(k)), tuple(range(2 * k - 1, k - 1, -1))]
    faces += [(i + k, i + 1 + k, i + 1, i) for i in range(k - 1)]
    faces.append((0, k - 1, 2 * k - 1, k))
    return verts, faces


def hood_vf(radii, open_h=50.0, open_up=30.0, open_dn=44.0, seg=24, rings=7, rim=0.9):
    """Ellipsoid hood with an oval face opening, parametrised around the face axis (-Y) so the
    opening edge is one clean ring. psi = angle from the face axis, beta = angle around it."""
    rx, ry, rz = radii

    def psi0(b):
        av = open_up if math.sin(b) > 0 else open_dn
        c_, s_ = math.cos(b) / open_h, math.sin(b) / av
        return rad(1.0 / math.sqrt(c_ * c_ + s_ * s_))

    def pt(psi, b, sc=1.0):
        d = Vector((math.sin(psi) * math.cos(b), -math.cos(psi), math.sin(psi) * math.sin(b)))
        return Vector((d.x * rx * sc, d.y * ry * sc, d.z * rz * sc))

    verts, rings_ = [], []
    if rim:
        ring = []
        for i in range(seg):
            b = TAU * i / seg
            ring.append(len(verts))
            verts.append(pt(psi0(b) + 0.05, b, rim))
        rings_.append(ring)
    for j in range(rings):
        ring = []
        for i in range(seg):
            b = TAU * i / seg
            p0 = psi0(b)
            ring.append(len(verts))
            verts.append(pt(p0 + (math.pi - p0) * j / rings, b))
        rings_.append(ring)
    pole = len(verts)
    verts.append(pt(math.pi, 0.0))
    faces = []
    for A, B in zip(rings_, rings_[1:]):
        faces += [(A[i], B[i], B[(i + 1) % seg], A[(i + 1) % seg]) for i in range(seg)]
    L = rings_[-1]
    faces += [(L[i], pole, L[(i + 1) % seg]) for i in range(seg)]
    return verts, faces


# ---- parametric surfaces (for decals): f(a, z) -> point; a = angle around, z = height/elevation
def ell_surf(c, radii):
    c = Vector(c)

    def f(yaw, el):
        return c + Vector((radii[0] * math.sin(yaw) * math.cos(el), -radii[1] * math.cos(yaw) * math.cos(el),
                           radii[2] * math.sin(el)))
    return f


def lathe_surf(prof, sx=1.0, sy=1.0, deform=None, m=None):
    pts = [(r, z) for (r, z) in prof if r > 1e-6]

    def r_at(z):
        if z <= pts[0][1]:
            return pts[0][0]
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            if z0 <= z <= z1:
                return r0 + (r1 - r0) * ((z - z0) / (z1 - z0) if z1 > z0 else 0.0)
        return pts[-1][0]

    def f(a, z):
        r = r_at(z)
        p = Vector((r * sx * math.sin(a), -r * sy * math.cos(a), z))
        if deform:
            p = deform(p, a, z)
        if m is not None:
            p = m @ p
        return p
    f.r_at = r_at
    return f


def snormal(f, a, z, e=1e-3):
    n = (f(a + e, z) - f(a - e, z)).cross(f(a, z + e) - f(a, z - e))
    return n.normalized()


def _metric(f, a, z, e=1e-3):
    du = (f(a + e, z) - f(a - e, z)).length / (2 * e)
    dz = (f(a, z + e) - f(a, z - e)).length / (2 * e)
    return du, dz


def decal_vf(f, a, z, outline, off=0.004):
    """Flat-ish patch conforming to surface f around (a, z). outline: CCW (u, v) metres."""
    du, dz = _metric(f, a, z)

    def P(aa, zz):
        return f(aa, zz) + snormal(f, aa, zz) * off
    verts = [P(a, z)] + [P(a + u / du, z + v / dz) for (u, v) in outline]
    k = len(outline)
    return verts, [(0, i + 1, (i + 1) % k + 1) for i in range(k)]


def strip_vf(f, a, z0, z1, width, off=0.004, steps=6):
    verts, faces = [], []
    for k in range(steps + 1):
        z = z0 + (z1 - z0) * k / steps
        du, _ = _metric(f, a, z)
        for u in (-width / 2, width / 2):
            aa = a + u / du
            verts.append(f(aa, z) + snormal(f, aa, z) * off)
    for k in range(steps):
        i = 2 * k
        faces.append((i, i + 1, i + 3, i + 2))
    return verts, faces


def surf_path(f, pts_az, off):
    return [f(a, z) + snormal(f, a, z) * off for (a, z) in pts_az]


# ---- 2D outlines (CCW)
def circle(r, n=8):
    return [(r * math.cos(TAU * i / n), r * math.sin(TAU * i / n)) for i in range(n)]


def ellipse(rx, ry, n=10):
    return [(rx * math.cos(TAU * i / n), ry * math.sin(TAU * i / n)) for i in range(n)]


def diamond(w, h):
    return [(0.0, -h / 2), (w / 2, 0.0), (0.0, h / 2), (-w / 2, 0.0)]


def rect(w, h):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


def flower(r, petals=5, n=20, rot=0.0):
    out = []
    for i in range(n):
        t = TAU * i / n + rot
        k = 0.5 + 0.5 * abs(math.cos(petals * (t - rot) / 2))
        out.append((r * k * math.cos(t), r * k * math.sin(t)))
    return out


def star(r, points=5, inner=0.45):
    out = []
    for i in range(points * 2):
        t = math.pi / 2 + math.pi * i / points
        rr = r if i % 2 == 0 else r * inner
        out.append((rr * math.cos(t), rr * math.sin(t)))
    return out


# --------------------------------------------------------------------------- character rig
PARTS = ("Body", "LegL", "LegR", "ArmL", "ArmR", "Head", "Held")
DEF = dict(hip=0.30, leg_x=0.085, leg_r=0.05, sh_x=0.16, sh_z=0.50, arm_len=0.175, arm_tilt=14.0,
           hand_r=0.047, arm_s=1.0, neck=0.56, head_up=0.25, head_r=(0.265, 0.245, 0.24))


class Char:
    def __init__(self, name, scale=1.0, **kw):
        self.name, self.S = name, scale
        self.d = dict(DEF, **kw)
        d = self.d
        self.hc = Vector((0.0, 0.0, d["neck"] + d["head_up"]))
        self.hr = d["head_r"]
        self.head = ell_surf(self.hc, self.hr)
        self.chunks = {p: [] for p in PARTS}
        self.held_name = "Held"

    def add(self, part, vf, m, smooth=True):
        self.chunks[part].append((vf[0], vf[1], m, smooth))
        if CHECK_NORMALS:
            vol = signed_volume(vf)
            if vol < -1e-9:
                import traceback
                fr = traceback.extract_stack(limit=3)[0]
                print(f"  !! inward normals? {self.name}/{part} {m} vol={vol:.2e} (line {fr.lineno}: {fr.line})")

    def hp(self, yaw, el, lift=0.0):
        a, e = rad(yaw), rad(el)
        n = snormal(self.head, a, e)
        return self.head(a, e) + n * lift, n

    def head_path(self, pts, lift):
        return [self.hp(y, e, lift)[0] for (y, e) in pts]

    def shoulder(self, side):
        return Vector((side * self.d["sh_x"], 0.0, self.d["sh_z"]))

    def arm_M(self, side):
        return T(self.shoulder(side)) @ R("Y", -side * self.d["arm_tilt"])

    def hand(self, side):
        return self.arm_M(side) @ Vector((0.0, 0.0, -self.d["arm_len"]))


CHECK_NORMALS = True


def signed_volume(vf):
    """Signed volume w.r.t. the chunk centroid: > 0 when faces point outward (closed-ish shapes)."""
    vs = [Vector(v) for v in vf[0]]
    c = sum(vs, Vector()) / max(1, len(vs))
    vol = 0.0
    for f in vf[1]:
        a = vs[f[0]] - c
        for i in range(1, len(f) - 1):
            vol += a.dot((vs[f[i]] - c).cross(vs[f[i + 1]] - c)) / 6.0
    return vol


def build_part_mesh(name, chunks, scale, origin):
    verts, faces, fmat, fsmooth, mats = [], [], [], [], []
    for (vs, fs, mname, smooth) in chunks:
        if mname not in mats:
            mats.append(mname)
        mi = mats.index(mname)
        base = len(verts)
        verts.extend(Vector(v) * scale - origin for v in vs)
        for f in fs:
            faces.append(tuple(base + i for i in f))
            fmat.append(mi)
            fsmooth.append(smooth)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for mn in mats:
        me.materials.append(M(mn))
    me.polygons.foreach_set("material_index", fmat)
    me.polygons.foreach_set("use_smooth", fsmooth)
    me.update()
    me.validate()
    return bpy.data.objects.new(name, me)


def assemble(c):
    S, d = c.S, c.d
    root = empty("char_" + c.name)
    hips_w = Vector((0.0, 0.0, d["hip"])) * S
    hips = empty("Hips", hips_w, root)

    def mesh(name, part, parent, origin):
        if not c.chunks[part]:
            return None
        o = build_part_mesh(name, c.chunks[part], S, origin)
        link(o, parent)
        return o

    mesh("Body", "Body", hips, hips_w)
    for side, sfx in ((1, "L"), (-1, "R")):
        lw = Vector((side * d["leg_x"], 0.0, d["hip"])) * S
        leg = empty("Leg" + sfx, lw - hips_w, hips)
        mesh("Leg" + sfx + "_Mesh", "Leg" + sfx, leg, lw)
    for side, sfx in ((1, "L"), (-1, "R")):
        aw = c.shoulder(side) * S
        arm = empty("Arm" + sfx, aw - hips_w, hips)
        mesh("Arm" + sfx + "_Mesh", "Arm" + sfx, arm, aw)
        if side < 0:
            hw = c.hand(-1) * S
            hand = empty("HandR", hw - aw, arm)
            hand.empty_display_size = 0.06
            mesh(c.held_name, "Held", hand, hw)
    nw = Vector((0.0, 0.0, d["neck"])) * S
    head = empty("Head", nw - hips_w, hips)
    mesh("Head_Mesh", "Head", head, nw)
    return root


# --------------------------------------------------------------------------- body parts
def blend3(phi, front, side, back):
    a = abs(math.atan2(math.sin(phi), math.cos(phi)))
    if a < math.pi / 2:
        return front + (side - front) * sstep(a / (math.pi / 2))
    return side + (back - side) * sstep((a - math.pi / 2) / (math.pi / 2))


def face(c, skin, eyes="dot", mouth="smile", brows="normal", brow_mat="M_Dark", ears=True, nose=True,
         blush=True, eye_yaw=24.0, eye_el=-5.0, eye_k=1.0, head_seg=22):
    DK = "M_Dark"
    c.add("Head", xf(ellipsoid_vf(c.hr, head_seg, 11), T(c.hc)), skin)
    if ears:
        for s in (1, -1):
            p, n = c.hp(90 * s, -7, -0.01)
            c.add("Head", xf(ellipsoid_vf((0.036, 0.024, 0.046), 8, 4), orient(p, n)), skin)
    if nose:
        p, n = c.hp(0, -12, -0.007)
        c.add("Head", xf(ellipsoid_vf((0.024, 0.02, 0.018), 6, 4), orient(p, n)), skin)
    for s in (1, -1):
        y = s * eye_yaw
        if eyes in ("dot", "big"):
            k = eye_k * (1.12 if eyes == "big" else 1.0)
            p, n = c.hp(y, eye_el, -0.003)
            c.add("Head", xf(ellipsoid_vf((0.024 * k, 0.011, 0.034 * k), 8, 5), orient(p, n)), DK)
        elif eyes == "smug":
            p, n = c.hp(y, eye_el - 1, -0.003)
            c.add("Head", xf(ellipsoid_vf((0.028, 0.011, 0.026), 8, 5, clip_top=0.004), orient(p, n)), DK)
        elif eyes == "narrow":
            p, n = c.hp(y, eye_el, -0.003)
            c.add("Head", xf(ellipsoid_vf((0.027, 0.01, 0.014), 8, 4), orient(p, n)), DK)
        elif eyes == "happy":
            pts = [(y + 3.6 * t, eye_el - 1.5 + 3.4 * (1 - t * t)) for t in (-1, -0.5, 0, 0.5, 1)]
            c.add("Head", tube_vf(c.head_path(pts, 0.002), [0.004, 0.0058, 0.006, 0.0058, 0.004], 4), DK)
        if blush:
            c.add("Head", decal_vf(c.head, rad(s * 41), rad(-17), ellipse(0.036, 0.021, 10), 0.0025), "M_Blush")
    # brows
    if brows:
        for s in (1, -1):
            y0 = s * eye_yaw
            e0 = eye_el + 12.5
            r = [0.004, 0.0065, 0.004]
            if brows == "normal":
                pts = [(y0 - s * 6, e0), (y0, e0 + 1.2), (y0 + s * 6, e0)]
            elif brows == "soft":
                pts = [(y0 - s * 5.5, e0 + 0.5), (y0, e0 + 1.8), (y0 + s * 5.5, e0 + 0.2)]
                r = [0.003, 0.005, 0.003]
            elif brows == "smug":
                lift = 3.0 if s > 0 else 0.0
                pts = [(y0 - s * 6, e0 + lift - 1.0), (y0, e0 + lift + 1.0), (y0 + s * 6, e0 + lift - 0.2)]
            elif brows == "angry":
                pts = [(y0 - s * 7, e0 - 3.5), (y0, e0 - 1.0), (y0 + s * 6, e0 + 1.2)]
                r = [0.006, 0.009, 0.006]
            elif brows == "worried":
                pts = [(y0 - s * 6, e0 + 2.0), (y0, e0 + 1.2), (y0 + s * 6, e0 - 0.8)]
            elif brows == "bushy":
                pts = [(y0 - s * 7, e0 - 0.5), (y0, e0 + 1.4), (y0 + s * 7, e0 - 1.5)]
                r = [0.007, 0.011, 0.007]
            c.add("Head", tube_vf(c.head_path(pts, 0.004), r, 4), brow_mat)
    # mouth
    if mouth == "smile":
        pts = [(yy, -21.0 - 2.4 * (1 - (yy / 8.0) ** 2)) for yy in (-8, -4, 0, 4, 8)]
        c.add("Head", tube_vf(c.head_path(pts, 0.002), [0.0035, 0.0055, 0.006, 0.0055, 0.0035], 4), DK)
    elif mouth == "smirk":
        pts = [(-6, -21.6), (-2, -22.0), (2, -21.6), (6, -20.4), (9.5, -18.4)]
        c.add("Head", tube_vf(c.head_path(pts, 0.002), [0.0035, 0.0055, 0.006, 0.0055, 0.0035], 4), DK)
    elif mouth == "flat":
        pts = [(-6, -21.8), (-2, -22.2), (2, -22.2), (6, -21.8)]
        c.add("Head", tube_vf(c.head_path(pts, 0.002), [0.0035, 0.0055, 0.0055, 0.0035], 4), DK)
    elif mouth == "frown":
        pts = [(yy, -22.5 + 1.8 * (1 - (yy / 7.0) ** 2)) for yy in (-7, -3.5, 0, 3.5, 7)]
        c.add("Head", tube_vf(c.head_path(pts, 0.002), [0.0035, 0.0055, 0.006, 0.0055, 0.0035], 4), DK)
    elif mouth == "open":
        p, n = c.hp(0, -21.5, -0.004)
        c.add("Head", xf(ellipsoid_vf((0.028, 0.009, 0.02), 8, 5, clip_top=0.006), orient(p, n)), DK)


def hair(c, m, front=68, side=95, back=118, part=0.0, lift=0.018, rim=0.93, seg=22, rings=5, rmod=None,
         off=(0.0, 0.004, 0.006), tmin=0.0):
    """Hair cap. tmin (deg) > 0 = only the band peeking out below a hat."""
    radii = tuple(r + lift for r in c.hr)

    def tmax(phi):
        return rad(blend3(phi, front, side, back) + part * math.sin(phi) * max(0.0, math.cos(phi)))
    c.add("Head", xf(shell_vf(radii, tmax, seg, rings, rim, rmod, rad(tmin)), T(c.hc + Vector(off))), m)


def messy_hair(c, m, front=66, side=94, back=112, teeth=14, amp=13.0, lump=0.045, lump2=0.03, lift=0.022, seg=28,
               rings=5):
    """Hair cap with a zig-zag edge all round and a lumpy surface (tousled look)."""
    def tooth(phi):
        t = ((phi + 0.1) / (TAU / teeth)) % 2.0
        return 1.0 - abs(t - 1.0)

    def tmax(phi):
        return rad(blend3(phi, front, side, back) + amp * tooth(phi))

    def lumpy(phi, th):
        return 1.0 + lump * math.sin(3 * phi + 1.0) * math.sin(2.2 * th) + lump2 * math.sin(7 * phi) * th

    radii = tuple(r + lift for r in c.hr)
    c.add("Head", xf(shell_vf(radii, tmax, seg, rings, 0.9, lumpy), T(c.hc + Vector((0, 0.006, 0.01)))), m)


def cowlick(c, m, spots, lift=0.03):
    """Short, wide, slightly flattened cones sticking up from the crown: (yaw, el, dir, length)."""
    hs = ell_surf(c.hc + Vector((0, 0.006, 0.01)), tuple(r + lift for r in c.hr))
    for (y, e, d, L) in spots:
        p = hs(rad(y), rad(e))
        n = snormal(hs, rad(y), rad(e))
        z = (n + Vector(d)).normalized()
        c.add("Head", xf(lathe_vf([(0.06, -0.04), (0.045, 0.01), (0.0, L)], 7, 1.0, 0.6),
                         align_z(p - n * 0.02, z)), m)


def moustache(c, m, thick=1.0, droop=4.0, width=15.0, el=-15.0):
    ys = [-width, -width * 0.6, -width * 0.27, 0.0, width * 0.27, width * 0.6, width]
    es = [el - droop, el - 0.3, el + 0.5, el, el + 0.5, el - 0.3, el - droop]
    r = [x * thick for x in (0.004, 0.011, 0.013, 0.01, 0.013, 0.011, 0.004)]
    c.add("Head", tube_vf(c.head_path(list(zip(ys, es)), 0.007 * thick), r, 6), m)


def sunglasses_on_face(c, m, eye_yaw=24.0, eye_el=-5.0):
    for s in (1, -1):
        p, n = c.hp(s * eye_yaw, eye_el, 0.012)
        c.add("Head", xf(ellipsoid_vf((0.052, 0.012, 0.036), 10, 6), orient(p, n)), m)
    br = c.head_path([(-eye_yaw + 11, eye_el + 2), (0, eye_el + 3.5), (eye_yaw - 11, eye_el + 2)], 0.016)
    c.add("Head", tube_vf(br, 0.005, 4), m)
    for s in (1, -1):
        tp = c.head_path([(s * (eye_yaw + 12), eye_el + 2), (s * 60, eye_el + 3), (s * 86, eye_el + 1)], 0.008)
        c.add("Head", tube_vf(tp, 0.0045, 4), m)


# ---- torso / legs / arms
SHIRT = [(0.0, 0.284), (0.13, 0.287), (0.16, 0.30), (0.161, 0.34), (0.153, 0.43), (0.13, 0.498),
         (0.085, 0.545), (0.0, 0.57)]
TUCKED = [(0.0, 0.318), (0.14, 0.32), (0.155, 0.34), (0.157, 0.39), (0.153, 0.43), (0.13, 0.498),
          (0.085, 0.545), (0.0, 0.57)]
PELVIS = [(0.0, 0.225), (0.085, 0.228), (0.13, 0.245), (0.148, 0.28), (0.151, 0.33), (0.0, 0.345)]
BODY_SY = 0.85


def torso(c, m, prof=SHIRT, sx=1.0, sy=BODY_SY, deform=None, seg=18):
    c.add("Body", lathe_vf(prof, seg, sx, sy, deform=deform), m)
    return lathe_surf(prof, sx, sy, deform)


def pelvis(c, m, prof=PELVIS, sx=1.0, sy=BODY_SY, seg=16):
    c.add("Body", lathe_vf(prof, seg, sx, sy), m)


def arms(c, skin, sleeve=None, sleeve_mat=None, cuff_mat=None):
    s, L, hr = c.d["arm_s"], c.d["arm_len"], c.d["hand_r"]
    for side in (1, -1):
        part = "ArmL" if side > 0 else "ArmR"
        Mw = c.arm_M(side)
        # arm + hand as one lathe (the hand is a round mitten at distance L from the shoulder)
        hand = [(0.034 * s, -L + hr * 0.72), (hr * 0.98, -L + hr * 0.3), (hr, -L - hr * 0.25),
                (hr * 0.72, -L - hr * 0.78), (0.0, -L - hr * 1.02)]
        if sleeve in (None, "tank"):
            prof = [(0.0, 0.036 * s), (0.028 * s, 0.032 * s), (0.042 * s, 0.01 * s), (0.042 * s, -0.04),
                    (0.038 * s, -L * 0.55)] + hand
        elif sleeve == "long":
            prof = [(0.0, -L + 0.06)] + hand
        else:
            prof = [(0.0, -0.02), (0.04 * s, -0.03), (0.037 * s, -L * 0.6)] + hand
        c.add(part, xf(lathe_vf(prof[::-1], 8 if sleeve == "long" else 9, 1.0, 0.9), Mw), skin)
        if sleeve == "short":
            prof = [(0.0, 0.05), (0.04, 0.045), (0.058, 0.022), (0.062, -0.03), (0.062, -0.066),
                    (0.044, -0.075)]
        elif sleeve == "rolled":
            prof = [(0.0, 0.05), (0.04, 0.045), (0.058, 0.022), (0.055, -0.078), (0.064, -0.092),
                    (0.058, -0.108), (0.043, -0.11)]
        elif sleeve == "long":
            prof = [(0.0, 0.05), (0.036, 0.046), (0.057, 0.025), (0.058, -0.02), (0.052, -L + 0.07),
                    (0.05, -L + 0.045), (0.036, -L + 0.04)]
        else:
            prof = None
        if prof:
            prof = [(r * s, z) for (r, z) in prof][::-1]
            c.add(part, xf(lathe_vf(prof, 10), Mw), sleeve_mat)
        if sleeve == "long" and cuff_mat:
            prof = [(0.046 * s, -L + 0.036), (0.054 * s, -L + 0.04), (0.056 * s, -L + 0.06), (0.05 * s, -L + 0.064)]
            c.add(part, xf(lathe_vf(prof, 10), Mw), cuff_mat)


def legs(c, skin, pants=None, pants_mat=None, foot="sandal", foot_mat="M_Dark", strap_mat=None, shorts_z=0.19):
    lr, hip = c.d["leg_r"], c.d["hip"]
    for side in (1, -1):
        part = "LegL" if side > 0 else "LegR"
        x = side * c.d["leg_x"]
        Mw = T(x, 0, 0)
        if pants != "long":
            prof = [(0.0, 0.03), (lr * 0.85, 0.04), (lr, 0.09), (lr, hip - 0.08), (0.0, hip - 0.03)]
            c.add(part, xf(lathe_vf(prof, 8), Mw), skin)
        prof = None
        if pants == "shorts":
            z0 = shorts_z
            prof = [(lr + 0.003, z0 + 0.004), (lr + 0.02, z0), (lr + 0.026, z0 + 0.02), (lr + 0.023, hip - 0.05),
                    (0.0, hip - 0.01)]
        elif pants == "long":
            prof = [(0.0, 0.06), (lr + 0.006, 0.062), (lr + 0.014, 0.076), (lr + 0.015, 0.16),
                    (lr + 0.021, hip - 0.05), (0.0, hip - 0.01)]
        elif pants == "rolled":
            z0 = 0.17
            prof = [(lr + 0.003, z0), (lr + 0.024, z0 - 0.002), (lr + 0.031, z0 + 0.018), (lr + 0.016, z0 + 0.035),
                    (lr + 0.019, hip - 0.05), (0.0, hip - 0.01)]
        if prof:
            c.add(part, xf(lathe_vf(prof, 10), Mw), pants_mat)
        fy = -0.022
        if foot in ("sandal", "bare"):
            c.add(part, xf(ellipsoid_vf((0.046, 0.068, 0.034), 8, 5), T(x, fy, 0.042 if foot == "sandal" else 0.034)),
                  skin)
            if foot == "sandal":
                c.add(part, xf(ellipsoid_vf((0.054, 0.08, 0.012), 8, 3), T(x, fy - 0.004, 0.012)), foot_mat)
                pts = []
                for t in (-1, -0.34, 0.34, 1):
                    ang = t * rad(80)
                    pts.append((x + 0.047 * math.sin(ang), fy - 0.03, 0.042 + 0.034 * math.cos(ang)))
                c.add(part, tube_vf(pts, 0.008, 4, up=(0, 1, 0)), strap_mat or foot_mat)
        elif foot in ("shoe", "boot"):
            c.add(part, xf(ellipsoid_vf((0.056, 0.086, 0.048), 9, 5), T(x, fy, 0.048)), foot_mat)
            if foot == "boot":
                bprof = [(0.0, 0.05), (0.06, 0.055), (0.064, 0.165), (0.058, 0.172), (0.0, 0.174)]
                c.add(part, xf(lathe_vf(bprof, 9), Mw), foot_mat)


# --------------------------------------------------------------------------- characters
def hat_band(c, H, prof_pts, m, seg=22):
    c.add("Head", xf(lathe_vf(prof_pts, seg, 1.0, 0.94), H), m)


def build_player():
    c = Char("player")
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="smug", mouth="smirk", brows="smug")
    hair(c, DK, front=70, side=96, back=116, part=8, tmin=50, rings=2)
    # straw safari hat, tipped back a little
    H = T(c.hc) @ R("X", -10) @ R("Y", 3)
    crown = [(0.232, 0.074), (0.35, 0.052), (0.368, 0.058), (0.355, 0.07), (0.258, 0.094), (0.25, 0.16),
             (0.232, 0.232), (0.19, 0.284), (0.1, 0.313), (0.0, 0.318)]
    c.add("Head", xf(lathe_vf(crown, 24, 1.0, 0.94), H), "M_Straw")
    hat_band(c, H, [(0.254, 0.094), (0.263, 0.117), (0.251, 0.142)], "M_Batik", 24)
    # sunglasses pushed up, resting on the brim in front of the crown
    for s in (1, -1):
        c.add("Head", xf(ellipsoid_vf((0.05, 0.013, 0.034), 8, 4),
                         H @ T(s * 0.058, -0.252, 0.13) @ R("Z", -s * 14) @ R("X", -12)), DK)
    c.add("Head", xf(tube_vf([(-0.02, -0.262, 0.14), (0.0, -0.265, 0.146), (0.02, -0.262, 0.14)], 0.0055, 4), H), DK)
    # batik shirt + khaki shorts
    surf = torso(c, "M_Batik")
    pelvis(c, "M_Khaki")
    for row, z in enumerate((0.33, 0.40, 0.465)):
        n = 8
        for k in range(n):
            a = TAU * (k + 0.5 * (row % 2)) / n
            c.add("Body", decal_vf(surf, a, z, diamond(0.026, 0.036)), DK)
    for row, z in enumerate((0.365, 0.432)):
        for k in range(8):
            a = TAU * (k + 0.5 * ((row + 1) % 2)) / 8
            c.add("Body", decal_vf(surf, a, z, circle(0.012, 6)), "M_Straw")
    arms(c, SK, sleeve="short", sleeve_mat="M_Batik")
    legs(c, SK, pants="shorts", pants_mat="M_Khaki", foot="sandal", foot_mat=DK, strap_mat="M_Batik")
    return c


def build_kakek():
    c = Char("kakek", head_r=(0.262, 0.245, 0.235))
    SK, DK, PALE = "M_SkinTan", "M_Dark", "M_FadedShirt"
    face(c, SK, eyes="happy", mouth=None, brows="bushy", brow_mat=PALE)
    hair(c, PALE, front=80, side=97, back=116, seg=20, tmin=58, rings=2)
    moustache(c, PALE, thick=1.1, droop=5.0)
    # wide conical caping hat (bamboo), tipped back slightly, with two woven rings
    H = T(c.hc) @ R("X", -9)
    cone = [(0.2, 0.17), (0.46, 0.05), (0.475, 0.06), (0.45, 0.076), (0.3, 0.16), (0.15, 0.255), (0.05, 0.325),
            (0.0, 0.345)]
    c.add("Head", xf(lathe_vf(cone, 24), H), "M_Bamboo")
    c.add("Head", xf(ellipsoid_vf((0.026, 0.026, 0.028), 6, 4), H @ T(0, 0, 0.345)), "M_Bamboo")
    for rr in (0.41, 0.24):
        # radius -> height on the cone's top surface, then a thin raised ring following the slope
        z = 0.076 + (0.45 - rr) / 0.15 * 0.084 if rr > 0.3 else 0.16 + (0.3 - rr) / 0.15 * 0.095
        prof = [(rr + 0.014, z - 0.004), (rr + 0.001, z + 0.009), (rr - 0.013, z + 0.019)]
        c.add("Head", xf(lathe_vf(prof, 24), H @ T(0, 0, 0.003)), "M_Sarong")
    # faded shirt over a checked sarong
    torso(c, PALE, [SHIRT[0], (0.13, 0.327), (0.165, 0.335)] + SHIRT[3:])
    sar = [(0.0, 0.1), (0.14, 0.09), (0.17, 0.092), (0.172, 0.12), (0.162, 0.25), (0.153, 0.345), (0.0, 0.35)]
    c.add("Body", lathe_vf(sar, 20, 1.0, 0.88), "M_Sarong")
    ssurf = lathe_surf(sar, 1.0, 0.88)
    for z in (0.14, 0.2, 0.26):
        prof = [(ssurf.r_at(z - 0.007) + 0.003, z - 0.007), (ssurf.r_at(z + 0.007) + 0.003, z + 0.007)]
        c.add("Body", lathe_vf(prof, 20, 1.0, 0.88), PALE)
    for k in range(10):
        a = TAU * (k + 0.5) / 10
        c.add("Body", strip_vf(ssurf, a, 0.1, 0.33, 0.012, 0.0035, 3), PALE)
    arms(c, SK, sleeve="short", sleeve_mat=PALE)
    legs(c, SK, pants="skirt", foot="sandal", foot_mat=DK, strap_mat="M_Sarong")
    return c


def build_ibu():
    c = Char("ibu", sh_x=0.14, sh_z=0.47, arm_len=0.165)
    SK = "M_Skin"
    face(c, SK, eyes="dot", mouth="smile", brows="soft", ears=False)
    # hijab: a hood framing the face (wrapping under the chin) ...
    radii = (c.hr[0] + 0.024, c.hr[1] + 0.03, c.hr[2] + 0.03)
    c.add("Head", xf(hood_vf(radii, 52, 30, 46, 24, 7, 0.9), T(c.hc + Vector((0, 0.012, -0.008)))), "M_Hijab")
    # ... flowing into a bell-shaped drape over the shoulders and upper arms (on the body, so it
    # doesn't turn with the head; the arms sit just inside it and the hands come out below)
    cape = [(0.0, 0.37), (0.2, 0.365), (0.25, 0.37), (0.254, 0.386), (0.24, 0.44), (0.222, 0.5), (0.198, 0.55),
            (0.16, 0.6), (0.0, 0.62)]
    c.add("Body", lathe_vf(cape, 22, 1.0, 0.86), "M_Hijab")
    # long floral dress, bell shaped
    dress = [(0.0, 0.075), (0.2, 0.07), (0.242, 0.08), (0.247, 0.1), (0.226, 0.19), (0.19, 0.28), (0.16, 0.36),
             (0.145, 0.42), (0.11, 0.5), (0.0, 0.53)]
    c.add("Body", lathe_vf(dress, 22, 1.0, 0.88), "M_Dress")
    dsurf = lathe_surf(dress, 1.0, 0.88)
    rows = ((0.125, 9, 0.028), (0.21, 8, 0.026), (0.295, 7, 0.024))
    for ri, (z, n, r) in enumerate(rows):
        for k in range(n):
            a = TAU * (k + 0.5 * (ri % 2)) / n
            c.add("Body", decal_vf(dsurf, a, z, flower(r, 5, 15, rot=0.4 * k)), "M_Floral")
    arms(c, SK, sleeve="long", sleeve_mat="M_Dress")
    legs(c, SK, pants="skirt", foot="sandal", foot_mat="M_Hijab")
    return c


def build_kades():
    c = Char("kades")
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="dot", mouth="smile", brows="normal")
    hair(c, DK, front=74, side=94, back=114, lift=0.012, seg=20, tmin=40, rings=2)
    moustache(c, DK, thick=1.2, droop=3.0, width=14)
    # black peci
    H = T(c.hc) @ R("X", -4)
    peci = [(0.245, 0.09), (0.251, 0.102), (0.247, 0.206), (0.233, 0.237), (0.13, 0.25), (0.0, 0.253)]
    c.add("Head", xf(lathe_vf(peci, 24, 1.0, 0.93), H), DK)

    # crisp white shirt with a round belly, tucked into dark trousers
    def belly(p, a, z):
        g = math.exp(-((z - 0.37) / 0.085) ** 2)
        front = max(0.0, math.cos(a)) ** 1.5
        p.y -= 0.045 * g * front
        p.x *= 1.0 + 0.1 * g
        return p
    surf = torso(c, "M_White", TUCKED, sx=1.04, deform=belly)
    pelvis(c, "M_Trousers", [(0.0, 0.225), (0.085, 0.228), (0.13, 0.245), (0.152, 0.28), (0.158, 0.33),
                             (0.0, 0.345)], sx=1.04)
    prof = [(0.157, 0.312), (0.163, 0.328), (0.157, 0.344)]
    c.add("Body", lathe_vf(prof, 18, 1.04, BODY_SY, deform=belly), DK)
    c.add("Body", xf(box_vf(0.022, 0.006, 0.016), T(surf(0.0, 0.328) + Vector((0, -0.009, 0)))), "M_Gold")
    for z in (0.38, 0.43, 0.475):
        c.add("Body", decal_vf(surf, 0.0, z, circle(0.008, 6)), "M_Gold")
    c.add("Body", decal_vf(surf, rad(38), 0.455, rect(0.024, 0.032)), "M_Gold")
    arms(c, SK, sleeve="long", sleeve_mat="M_White", cuff_mat="M_White")
    legs(c, SK, pants="long", pants_mat="M_Trousers", foot="shoe", foot_mat=DK)
    return c


def build_nenek():
    c = Char("nenek")
    SK, DK, GR = "M_Skin", "M_Dark", "M_HairGrey"
    face(c, SK, eyes="happy", mouth="smile", brows="soft", brow_mat=GR)
    hair(c, GR, front=62, side=92, back=116, lift=0.02)
    # bun + hair stick
    c.add("Head", xf(ellipsoid_vf((0.1, 0.09, 0.085), 12, 7), T(c.hc + Vector((0, 0.19, 0.17)))), GR)
    c.add("Head", tube_vf([c.hc + Vector((-0.1, 0.18, 0.24)), c.hc + Vector((0.1, 0.22, 0.15))], 0.0065, 4),
          "M_Kain")
    # round glasses
    for s in (1, -1):
        p, n = c.hp(s * 24, -5, 0.014)
        loop = [orient(p, n) @ Vector((0.043 * math.cos(t), 0, 0.04 * math.sin(t))) for t in
                [TAU * i / 12 for i in range(12)]]
        c.add("Head", tube_vf(loop, 0.0045, 4, closed=True, up=-n), DK)
        tp = c.head_path([(s * 36, -4), (s * 62, -2), (s * 86, -3)], 0.008)
        c.add("Head", tube_vf(tp, 0.004, 4), DK)
    c.add("Head", tube_vf(c.head_path([(-13, -3), (0, -1.5), (13, -3)], 0.017), 0.0045, 4), DK)
    # kebaya top (light, with a small peplum) and batik kain to the ankles
    keb = [(0.0, 0.3), (0.14, 0.296), (0.172, 0.305), (0.168, 0.33), (0.157, 0.39), (0.15, 0.44), (0.13, 0.498),
           (0.085, 0.545), (0.0, 0.57)]
    surf = torso(c, "M_Kebaya", keb)
    for z in (0.37, 0.42, 0.47):
        c.add("Body", decal_vf(surf, 0.0, z, circle(0.009, 6)), GR)
    kain = [(0.0, 0.065), (0.13, 0.06), (0.158, 0.064), (0.162, 0.09), (0.157, 0.25), (0.152, 0.34), (0.0, 0.345)]
    c.add("Body", lathe_vf(kain, 20, 1.0, 0.88), "M_Kain")
    ksurf = lathe_surf(kain, 1.0, 0.88)
    for ri, z in enumerate((0.1, 0.16, 0.22, 0.28)):
        for k in range(9):
            a = TAU * (k + 0.5 * (ri % 2)) / 9
            c.add("Body", decal_vf(ksurf, a, z, diamond(0.026, 0.032), 0.0035), "M_Kebaya")
    c.add("Body", strip_vf(ksurf, rad(-18), 0.065, 0.3, 0.01, 0.0045, 3), "M_Kebaya")
    arms(c, SK, sleeve="long", sleeve_mat="M_Kebaya")
    legs(c, SK, pants="skirt", foot="sandal", foot_mat=DK, strap_mat="M_Kain")
    return c


def build_pemuda():
    c = Char("pemuda")
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="dot", mouth="open", brows="normal")
    # messy hair: zig-zag edge all round, lumpy volume and a cowlick
    messy_hair(c, DK)
    cowlick(c, DK, [(-8, 64, (0.1, 0.6, 0.3), 0.075), (14, 60, (-0.3, 0.8, 0.1), 0.065),
                    (178, 58, (0.2, 0.9, -0.2), 0.06)])
    # bright green tee + jeans shorts + sarong slung over the left shoulder
    torso(c, "M_GreenTee")
    pelvis(c, "M_Jeans")
    L_ = Vector((0.12, 0.0, 0.548))
    Rp = Vector((-0.168, 0.0, 0.3))
    C = (L_ + Rp) / 2
    u = (L_ - Rp).normalized()
    v = Vector((0.0, 1.0, 0.0))
    A = (L_ - Rp).length / 2 + 0.01
    B = 0.168
    nrm = u.cross(v)
    N = 28
    pts = [C + u * (A * math.cos(TAU * i / N)) + v * (B * math.sin(TAU * i / N)) for i in range(N)]
    for i in range(N):  # checked sarong: dark stripes every few segments
        mname = DK if i % 4 == 0 else "M_SarongRed"
        c.add("Body", tube_vf([pts[i], pts[(i + 1) % N]], (0.02, 0.046), 4, up=nrm, caps=False), mname)
    c.add("Body", xf(ellipsoid_vf((0.05, 0.04, 0.045), 8, 5), T(Rp + Vector((-0.01, -0.02, 0.0)))), "M_SarongRed")
    c.add("Body", xf(ellipsoid_vf((0.028, 0.02, 0.06), 6, 4), T(Rp + Vector((-0.018, -0.03, -0.065)))),
          "M_SarongRed")
    arms(c, SK, sleeve="short", sleeve_mat="M_GreenTee")
    legs(c, SK, pants="shorts", pants_mat="M_Jeans", foot="sandal", foot_mat=DK)
    return c


def build_petani():
    c = Char("petani")
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="dot", mouth="smile", brows="normal")
    hair(c, DK, front=78, side=97, back=116, seg=20, tmin=58, rings=2)
    # olive bucket hat
    H = T(c.hc) @ R("X", -8)
    bucket = [(0.248, 0.085), (0.36, 0.025), (0.372, 0.034), (0.35, 0.052), (0.26, 0.1), (0.25, 0.17),
              (0.228, 0.25), (0.16, 0.287), (0.0, 0.297)]
    c.add("Head", xf(lathe_vf(bucket, 22, 1.0, 0.94), H), "M_Olive")
    hat_band(c, H, [(0.258, 0.098), (0.266, 0.115), (0.256, 0.132)], DK)
    # blue work shirt, rolled sleeves; white towel round the neck
    surf = torso(c, "M_WorkBlue")
    pelvis(c, "M_Olive")
    loop = []
    for i in range(18):
        t = TAU * i / 18
        dip = 0.018 * max(0.0, math.cos(t))
        loop.append(Vector((0.118 * math.sin(t), -0.108 * math.cos(t), 0.552 - dip)))
    c.add("Body", tube_vf(loop, (0.03, 0.026), 5, closed=True), "M_White")
    for s in (1, -1):
        path = surf_path(surf, [(rad(s * 22), 0.535), (rad(s * 20), 0.48), (rad(s * 19), 0.41)], 0.014)
        c.add("Body", tube_vf(path, [(0.034, 0.011), (0.036, 0.012), (0.038, 0.012)], 5, up=(0, -1, 0)),
              "M_White")
    arms(c, SK, sleeve="rolled", sleeve_mat="M_WorkBlue")
    legs(c, SK, pants="rolled", pants_mat="M_Olive", foot="boot", foot_mat=DK)
    return c


def build_anak():
    c = Char("anak", scale=0.78, head_r=(0.285, 0.265, 0.258))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="big", mouth="open", brows="soft", eye_yaw=25, eye_el=-6)
    messy_hair(c, DK, front=76, side=97, back=116, teeth=18, amp=9.0, lump=0.0, lump2=0.0, lift=0.014, seg=36, rings=4)
    # baseball cap worn backwards: crown + flat (orange) bill sticking out at the back
    capr = (c.hr[0] + 0.026, c.hr[1] + 0.026, c.hr[2] + 0.022)
    Hc = T(c.hc + Vector((0, 0.006, 0.008)))

    def ctm(phi):
        return rad(blend3(phi, 66, 78, 88))
    c.add("Head", xf(shell_vf(capr, ctm, 22, 5, 0.95), Hc), "M_CapBlue")
    c.add("Head", xf(ellipsoid_vf((0.026, 0.026, 0.015), 6, 3), Hc @ T(0, 0, capr[2])), "M_TeeOrange")
    c.add("Head", xf(bill_vf(0.165, 0.19, 0.008, 10, bend=0.6), Hc @ T(0, 0.2, 0.05) @ R("X", 8) @ R("Z", 180)),
          "M_CapBlue", smooth=False)
    # a tuft of hair poking out of the strap opening
    cowlick(c, DK, [(0, 24, (0, -0.9, 0.2), 0.06)], lift=0.03)
    cs = ell_surf(Vector((0, 0, 0)), capr)
    c.add("Head", tube_vf([Hc @ cs(rad(a_), rad(20 + 0.014 * a_ * a_)) for a_ in (-28, -14, 0, 14, 28)],
                          0.007, 4), "M_CapBlue")
    # orange tee with a star, blue shorts
    surf = torso(c, "M_TeeOrange")
    pelvis(c, "M_Jeans")
    c.add("Body", decal_vf(surf, 0.0, 0.42, star(0.042, 5, 0.45)), "M_CapBlue")
    arms(c, SK, sleeve="short", sleeve_mat="M_TeeOrange")
    legs(c, SK, pants="shorts", pants_mat="M_Jeans", foot="sandal", foot_mat="M_CapBlue", strap_mat=DK)
    return c


PREMAN_TORSO = [(0.0, 0.31), (0.16, 0.31), (0.19, 0.33), (0.2, 0.4), (0.212, 0.5), (0.218, 0.58), (0.206, 0.64),
                (0.176, 0.685), (0.126, 0.722), (0.075, 0.744), (0.0, 0.755)]


def build_preman():
    c = Char("preman", hip=0.33, leg_x=0.1, leg_r=0.062, sh_x=0.215, sh_z=0.63, arm_len=0.215, arm_tilt=16,
             hand_r=0.064, arm_s=1.42, neck=0.745)
    SK, DK, INK = "M_SkinTan", "M_Dark", "M_Ink"
    face(c, SK, eyes="narrow", mouth="frown", brows="angry")
    hair(c, DK, front=60, side=88, back=112, lift=0.006, rim=None, seg=22, rings=4)
    # toothpick
    p0, n0 = c.hp(9, -21.2, 0.0)
    c.add("Head", tube_vf([p0 - n0 * 0.01, p0 + Vector((0.055, -0.03, -0.018))], [0.0045, 0.0035], 4), "M_Gold")
    # black tank top over a big chest, skin shoulders
    sy = 0.78
    tank = [p for p in PREMAN_TORSO if p[1] <= 0.64] + [(0.19, 0.648), (0.0, 0.65)]
    tank = [(r + (0.004 if z > 0.55 else 0.0), z) for (r, z) in tank]
    c.add("Body", lathe_vf(tank, 20, 1.05, sy), DK)
    skin_top = [(0.0, 0.55), (0.212, 0.56)] + [p for p in PREMAN_TORSO if p[1] > 0.56]
    c.add("Body", lathe_vf(skin_top, 20, 1.05, sy), SK)
    surf = lathe_surf(PREMAN_TORSO, 1.05, sy)
    for s in (1, -1):  # straps
        path = surf_path(surf, [(rad(s * 28), 0.62), (rad(s * 40), 0.69), (rad(s * 90), 0.715),
                                (rad(s * 140), 0.69), (rad(s * 152), 0.62)], 0.004)
        c.add("Body", tube_vf(path, (0.03, 0.006), 4, up=(0, 0, 1)), DK)
    # gold chain resting on the chest
    N = 22
    chain = [(TAU * i / N, 0.727 - 0.065 * (0.5 + 0.5 * math.cos(TAU * i / N)) ** 1.5) for i in range(N)]
    cp = surf_path(surf, chain, 0.012)
    c.add("Body", tube_vf(cp, [0.011 if i % 2 else 0.007 for i in range(N)], 4, closed=True), "M_Gold")
    c.add("Body", xf(ellipsoid_vf((0.022, 0.01, 0.026), 6, 4), T(surf(0.0, 0.63) + Vector((0, -0.02, 0)))), "M_Gold")
    pelvis(c, "M_Army", [(0.0, 0.25), (0.1, 0.255), (0.16, 0.28), (0.18, 0.31), (0.182, 0.36), (0.0, 0.37)], sx=1.05,
           sy=sy)
    c.add("Body", lathe_vf([(0.19, 0.33), (0.198, 0.347), (0.19, 0.362)], 20, 1.05, sy), DK)
    arms(c, SK, sleeve=None)
    # tattoos: a band + patches on each upper arm
    s_ = c.d["arm_s"]
    aprof = [(0.042 * s_, 0.01 * s_), (0.042 * s_, -0.04), (0.038 * s_, -0.215 * 0.55)]
    asurf = lathe_surf(aprof[::-1], 1.0, 0.9)
    for side in (1, -1):
        part = "ArmL" if side > 0 else "ArmR"
        Mw = c.arm_M(side)
        z = -0.06
        prof = [(asurf.r_at(z - 0.012) + 0.003, z - 0.012), (asurf.r_at(z + 0.012) + 0.003, z + 0.012)]
        c.add(part, xf(lathe_vf(prof, 9, 1.0, 0.9), Mw), INK)
        out = rad(90 * side)
        for (aa, zz, shp) in ((out, -0.1, star(0.032, 6, 0.5)), (out - rad(65 * side), -0.012, ellipse(0.02, 0.026, 8)),
                              (out + rad(70 * side), -0.105, diamond(0.032, 0.042))):
            c.add(part, xf(decal_vf(asurf, aa, zz, shp, 0.004), Mw), INK)
    legs(c, SK, pants="long", pants_mat="M_Army", foot="boot", foot_mat=DK)
    return c


def build_calo():
    c = Char("calo")
    SK, DK, TW = "M_Skin", "M_Dark", "M_Tweed"
    face(c, SK, eyes=None, mouth="smirk", brows=None)
    hair(c, DK, front=80, side=96, back=114, lift=0.014, seg=20, tmin=60, rings=2)
    sunglasses_on_face(c, DK)
    # pencil moustache (two halves)
    for s in (1, -1):
        pts = [(s * 2.5, -15.8), (s * 7, -16.2), (s * 11.5, -15.2), (s * 14, -13.2)]
        c.add("Head", tube_vf(c.head_path(pts, 0.004), [0.004, 0.0055, 0.0045, 0.003], 4), DK)
    # flat cap
    H = T(c.hc) @ R("X", 4)
    c.add("Head", xf(ellipsoid_vf((0.29, 0.3, 0.115), 22, 7), H @ T(0, -0.012, 0.172)), TW)
    c.add("Head", xf(ellipsoid_vf((0.18, 0.1, 0.02), 12, 4), H @ T(0, -0.25, 0.14) @ R("X", 14)), TW)
    c.add("Head", xf(ellipsoid_vf((0.022, 0.022, 0.012), 6, 3), H @ T(0, -0.02, 0.286)), TW)
    # loud Hawaiian shirt, bum bag
    surf = torso(c, "M_Hawaii")
    pelvis(c, TW)
    placed = [(0, 0.35), (1, 0.44), (2, 0.36), (3, 0.47), (4, 0.34), (5, 0.43), (6, 0.37), (7, 0.46), (8, 0.39)]
    for i, (k, z) in enumerate(placed):
        a = TAU * (k + 0.15) / 9
        c.add("Body", decal_vf(surf, a, z, flower(0.036 if i % 2 else 0.03, 5, 15, rot=i * 0.7)), "M_HawaiiFlower")
    # bum bag worn across the belly
    strap = surf_path(lathe_surf(SHIRT), [(TAU * i / 18, 0.335 + 0.04 * math.cos(TAU * i / 18 + 0.9)) for i in
                                          range(18)], 0.006)
    c.add("Body", tube_vf(strap, (0.009, 0.014), 4, closed=True), DK)
    bb = surf(rad(-10), 0.325) + Vector((0, -0.04, 0))
    c.add("Body", xf(ellipsoid_vf((0.09, 0.045, 0.055), 10, 5), T(bb) @ R("Y", 12)), DK)
    c.add("Body", xf(tube_vf([(-0.07, -0.045, 0.012), (0.0, -0.05, 0.014), (0.07, -0.045, 0.012)], 0.004, 4),
                     T(bb) @ R("Y", 12)), "M_HawaiiFlower")
    arms(c, SK, sleeve="short", sleeve_mat="M_Hawaii")
    for side in (1, -1):
        part = "ArmL" if side > 0 else "ArmR"
        ssurf = lathe_surf([(0.063, -0.064), (0.062, -0.03), (0.058, 0.022)], 1.0, 1.0)
        c.add(part, xf(decal_vf(ssurf, rad(90 * side), -0.035, flower(0.026, 5, 15), 0.005), c.arm_M(side)),
              "M_HawaiiFlower")
    legs(c, SK, pants="long", pants_mat=TW, foot="shoe", foot_mat=DK)
    return c


def build_petugas():
    c = Char("petugas")
    SK, DK, UN = "M_Skin", "M_Dark", "M_Uniform"
    face(c, SK, eyes="dot", mouth="flat", brows="angry")
    hair(c, DK, front=80, side=95, back=114, lift=0.012, seg=20, tmin=58, rings=2)
    # peaked uniform cap with a dark band + visor and a gold badge
    H = T(c.hc) @ R("X", -3)
    cap = [(0.238, 0.1), (0.247, 0.17), (0.285, 0.225), (0.292, 0.24), (0.272, 0.253), (0.0, 0.264)]
    c.add("Head", xf(lathe_vf(cap, 22, 1.0, 0.95), H), UN)
    c.add("Head", xf(lathe_vf([(0.243, 0.104), (0.254, 0.13), (0.249, 0.156)], 22, 1.0, 0.95), H), DK)
    c.add("Head", xf(ellipsoid_vf((0.16, 0.1, 0.016), 12, 4), H @ T(0, -0.235, 0.112) @ R("X", 18)), DK)
    c.add("Head", xf(ellipsoid_vf((0.028, 0.012, 0.03), 6, 4), H @ T(0, -0.248, 0.19) @ R("X", -30)), "M_Gold")
    # uniform shirt tucked in, belt, badge, name tag, epaulettes
    surf = torso(c, UN, TUCKED)
    pelvis(c, UN)
    c.add("Body", lathe_vf([(0.153, 0.312), (0.16, 0.328), (0.153, 0.344)], 18, 1.0, BODY_SY), DK)
    c.add("Body", xf(box_vf(0.022, 0.006, 0.016), T(surf(0.0, 0.328) + Vector((0, -0.009, 0)))), "M_Gold")
    c.add("Body", decal_vf(surf, rad(36), 0.45, star(0.032, 5, 0.45)), "M_Gold")
    c.add("Body", decal_vf(surf, rad(-36), 0.445, rect(0.055, 0.016)), "M_White")
    for z in (0.37, 0.41, 0.45, 0.49):
        c.add("Body", decal_vf(surf, 0.0, z, circle(0.007, 6)), "M_Gold")
    for s in (1, -1):
        c.add("Body", xf(ellipsoid_vf((0.05, 0.036, 0.01), 8, 3), T(s * 0.118, 0.0, 0.52) @ R("Y", -s * 38)), UN)
    arms(c, SK, sleeve="short", sleeve_mat=UN)
    legs(c, SK, pants="long", pants_mat=UN, foot="shoe", foot_mat=DK)
    # clipboard held in the right hand (child of HandR)
    c.held_name = "Clipboard"
    h = c.hand(-1)
    Mc = T(h) @ R("Z", 40) @ T(-0.032, -0.0, -0.075)
    c.add("Held", xf(box_vf(0.009, 0.08, 0.105), Mc), DK, smooth=False)
    c.add("Held", xf(box_vf(0.003, 0.07, 0.085), Mc @ T(-0.01, 0.0, -0.012)), "M_White", smooth=False)
    c.add("Held", xf(box_vf(0.014, 0.028, 0.014), Mc @ T(0.0, 0.0, 0.1)), "M_Gold", smooth=False)
    return c


def build_buruh():
    c = Char("buruh")
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="dot", mouth="flat", brows="worried")
    hair(c, DK, front=80, side=96, back=114, lift=0.012, seg=20, tmin=58, rings=2)
    # yellow hard hat with a short front peak and a ridge over the top
    H = T(c.hc) @ R("X", -5)

    def peak(p, a, z):
        if z < 0.105:
            p.y -= 0.05 * max(0.0, math.cos(a)) ** 3
        return p
    hat = [(0.248, 0.092), (0.318, 0.076), (0.322, 0.088), (0.3, 0.098), (0.266, 0.108), (0.26, 0.17),
           (0.232, 0.24), (0.16, 0.297), (0.0, 0.318)]
    c.add("Head", xf(lathe_vf(hat, 24, 1.0, 0.95, deform=peak), H), "M_HardHat")
    dome = lathe_surf(hat[5:], 1.0, 0.95)
    ridge = [(0.0, z) for z in (0.14, 0.2, 0.25, 0.29)] + [(math.pi, z) for z in (0.29, 0.25, 0.2, 0.14)]
    rp = surf_path(dome, ridge, 0.004)
    rp.insert(4, H.inverted() @ (H @ Vector((0, 0, 0.323))))
    c.add("Head", xf(tube_vf(rp, (0.02, 0.011), 5, up=(1, 0, 0)), H), "M_HardHat")
    # dusty long-sleeve shirt, work trousers, boots
    surf = torso(c, "M_Dusty")
    pelvis(c, "M_WorkPants")
    for s in (1, -1):
        c.add("Body", decal_vf(surf, rad(s * 34), 0.43, rect(0.05, 0.055)), "M_WorkPants")
    arms(c, SK, sleeve="long", sleeve_mat="M_Dusty", cuff_mat="M_WorkPants")
    legs(c, SK, pants="long", pants_mat="M_WorkPants", foot="boot", foot_mat=DK)
    return c


BUILDERS = {
    "player": build_player, "kakek": build_kakek, "ibu": build_ibu, "kades": build_kades,
    "nenek": build_nenek, "pemuda": build_pemuda, "petani": build_petani, "anak": build_anak,
    "preman": build_preman, "calo": build_calo, "petugas": build_petugas, "buruh": build_buruh,
}


# --------------------------------------------------------------------------- output
def mesh_bounds(root):
    pts = []
    for o in all_descendants(root):
        if o.type == "MESH":
            pts += [o.matrix_world @ v.co for v in o.data.vertices]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def materials_of(root):
    out = set()
    for o in all_descendants(root):
        if o.type == "MESH":
            out.update(m.name for m in o.data.materials)
    return sorted(out)


def portrait(c, root):
    """Head-and-shoulders icon. render_icon frames the bounds of what it is given, so give it a
    hidden flat framing card (in the XZ plane) sized so ortho_scale == wanted frame size F."""
    bpy.context.view_layer.update()
    S = c.S
    head = next(o for o in all_descendants(root) if o.name.startswith("Head_Mesh"))
    top = max((head.matrix_world @ v.co).z for v in head.data.vertices)
    hc = c.hc.z * S
    bottom = hc - 0.36 * S
    F = min(0.82 * S, max(0.66 * S, top - bottom + 0.08 * S))
    cz = bottom + F / 2 - 0.02 * S
    a = F / math.sqrt(2.0) / 2.0
    me = bpy.data.meshes.new("_frame")
    me.from_pydata([(-a, 0, cz - a), (a, 0, cz - a), (a, 0, cz + a), (-a, 0, cz + a)], [], [(0, 1, 2, 3)])
    fr = bpy.data.objects.new("_frame", me)
    link(fr)
    fr.hide_render = True
    render_icon(fr, "portrait_" + c.name, pitch_deg=8, yaw_deg=15, res=256, margin=1.0)
    bpy.data.objects.remove(fr, do_unlink=True)


def build_one(name, out=True, pitch=55.0):
    c = BUILDERS[name]()
    root = assemble(c)
    bpy.context.view_layer.update()
    mn, mx = mesh_bounds(root)
    tris = count_tris(root)
    mats = materials_of(root)
    info = dict(name=name, height=mx.z, min_z=mn.z, tris=tris, mats=mats,
                hips=c.d["hip"] * c.S, shoulder=c.d["sh_z"] * c.S, neck=c.d["neck"] * c.S,
                leg_x=c.d["leg_x"] * c.S, sh_x=c.d["sh_x"] * c.S, hand=tuple(round(v, 3) for v in c.hand(-1) * c.S))
    print(f"[char] {name}: h={mx.z:.3f} minz={mn.z:.3f} tris={tris} mats={len(mats)} {mats}")
    if tris > 3000:
        print(f"  !! {name} over triangle budget")
    if len(mats) > 6:
        print(f"  !! {name} over material budget")
    if out:
        render_preview(root, "char_" + name, pitch_deg=pitch, yaw_deg=20)
        export_glb(root, "char_" + name)
        portrait(c, root)
    return c, root, info


def lineup(names):
    reset_scene()
    holder = empty("lineup")
    per_row = 6
    for i, n in enumerate(names):
        c = BUILDERS[n]()
        root = assemble(c)
        row, col = divmod(i, per_row)
        root.location = ((col - (per_row - 1) / 2) * 1.0, row * 1.5, 0.0)
        root.parent = holder
    bpy.context.view_layer.update()
    w, h = 1600, 1000
    common._setup_render(w, h, transparent=False, samples=20)
    tmp = common._temp_lights()
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.001))
    g = bpy.context.view_layer.objects.active
    common.set_mat(g, mat("_M_PreviewGround", "#8fb35c"))
    tmp.append(g)
    mn, mx = mesh_bounds(holder)
    center = (mn + mx) / 2
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    link(cam)
    pitch, yaw = rad(55), rad(0)
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = center + dirv * 20
    cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = (mx.x - mn.x) * 1.1
    cam.data.clip_end = 100
    bpy.context.scene.camera = cam
    tmp.append(cam)
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, "lineup.png")
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    print("[preview] lineup.png")


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    only_lineup = "--lineup" in argv
    no_out = "--no-out" in argv
    order = list(BUILDERS)
    todo = names or ([] if only_lineup else order)
    infos = []
    for n in todo:
        reset_scene()
        _, _, info = build_one(n, out=not no_out)
        infos.append(info)
    if not names or only_lineup:
        lineup(order)
    print("\n==== summary ====")
    for i in infos:
        print(f"{i['name']:8s} height={i['height']:.3f} tris={i['tris']:5d} mats={len(i['mats'])} "
              f"hips={i['hips']:.3f} shoulder={i['shoulder']:.3f} neck={i['neck']:.3f} handR={i['hand']}")


if __name__ == "__main__":
    main(sys.argv[1:])

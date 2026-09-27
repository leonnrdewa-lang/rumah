#!/usr/bin/env python3
"""Sawit The Franchise - rigged, skinned and animated chibi villagers (art direction v2).

Run:  python3 blender/characters.py                  all 12 characters + lineup preview
      python3 blender/characters.py kakek ibu        only these (no lineup)
      python3 blender/characters.py --lineup         only the lineup preview
      options: --sheets        also render per-clip contact sheets (game camera + side view)
                               to blender/previews/char_<name>_<clip>.png
               --sheets=walk,harvest   only these clips
               --no-out        build only (no export / renders)

Each character is ONE smooth mesh (all parts joined) skinned to an armature with the
contract bone names (ART_DIRECTION_V2.md):

  char_<name>  (armature object, origin at the feet, faces -Y)
    hips > spine > chest > neck > head > extra_eye_L/R, extra_brow_L/R, extra_mouth, extra_jaw
                         chest > upperarm_L > forearm_L > hand_L   (and _R)
           hips > thigh_L > shin_L > foot_L                        (and _R)
    Body   (mesh, Armature modifier, <= 6000 tris, <= 6 materials, baked AO + blush in `Col`)

Bone axes: every limb/spine bone points along its local +Y; local +Z points to the
character's front (feet: local +Z points up). So +X rotation swings any arm/leg/spine
bone forward. The head extras point out of the face (local +Z up): scaling Z blinks the
eyes (extra_eye_*), opens the mouth (extra_jaw) or flattens the smile (extra_mouth).

Ten actions per character (30 fps, in place):
  idle walk run talk sad (seamless loops, first frame == last frame)
  harvest chop plant cheer wave (one-shots that start and end in the neutral stance)
Poses are authored as eased key curves (monotone cubic = auto-clamped Bezier) driving
an FK/IK pose solver (planted feet, two-handed pole grips), with overlapping action
(head/torso lag the hips, arms trail), then baked to Bezier keyframes on the armature.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import common  # noqa: E402
from common import (ICONS_DIR, PREVIEW_DIR, bake_vertex_ao, count_tris, export_glb, link,  # noqa: E402
                    mat, reset_scene)

TAU = math.tau
FPS = 30


# --------------------------------------------------------------------------- math
def rad(d):
    return math.radians(d)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def sstep(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ss(e0, e1, x):
    """smoothstep from e0 to e1 (e0 > e1 allowed: falls from 1 to 0)."""
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    return sstep((x - e0) / (e1 - e0))


def lerp(a, b, t):
    return a + (b - a) * t


def T(x, y=0.0, z=0.0):
    if isinstance(x, Vector):
        return Matrix.Translation(x)
    return Matrix.Translation((x, y, z))


def R(axis, deg):
    return Matrix.Rotation(rad(deg), 4, axis)


def Sc(k):
    return Matrix.Diagonal((k, k, k, 1.0))


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


def align_z(p, d, up=(0.0, 1.0, 0.0)):
    """Matrix placing a local shape at p with its local +Z along direction d."""
    m = Vector(d).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    m.translation = p
    return m


def frame_y(p, y, z):
    """Matrix with local +Y along y and local +Z towards z (orthogonalised), origin p."""
    y = Vector(y).normalized()
    z = Vector(z)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p
    return m


# --------------------------------------------------------------------------- materials
# Every material name maps to exactly one colour, so characters can share a scene.
# (Names must not contain the game's foliage words: Leaf, Flower, Plant, ...)
MATS = {
    "M_Skin": ("#f2b98a", 0.75), "M_SkinTan": ("#d59a6a", 0.75),
    "M_Dark": ("#2e2724", 0.45), "M_White": ("#fbf7ee", 0.8),
    "M_Straw": ("#ecc97c", 0.9), "M_Batik": ("#c9682c", 0.9), "M_Khaki": ("#b9a371", 0.9),
    "M_Bamboo": ("#d0a257", 0.9), "M_FadedShirt": ("#dcd7c6", 0.9), "M_Sarong": ("#8b4f2e", 0.9),
    "M_Hijab": ("#d08791", 0.9), "M_Dress": ("#f59f7c", 0.9), "M_Floral": ("#fff4de", 0.9),
    "M_Trousers": ("#3b4155", 0.9), "M_Gold": ("#edbc3c", 0.5),
    "M_HairGrey": ("#c4c0b8", 0.8), "M_Kebaya": ("#f6ead3", 0.9), "M_Kain": ("#56502c", 0.9),
    "M_GreenTee": ("#62c24c", 0.9), "M_Jeans": ("#5079b0", 0.9), "M_SarongRed": ("#ac3c4f", 0.9),
    "M_WorkBlue": ("#4c78ab", 0.9), "M_Olive": ("#7f7e46", 0.9), "M_CapBlue": ("#3274d9", 0.7),
    "M_TeeOrange": ("#f58d2e", 0.9), "M_Ink": ("#3e5068", 0.8), "M_Army": ("#626e45", 0.9),
    "M_Hawaii": ("#26aca7", 0.9), "M_HawaiiBloom": ("#ffd94c", 0.9), "M_Tweed": ("#8f826a", 0.9),
    "M_Uniform": ("#8f6e45", 0.9), "M_HardHat": ("#f6c63f", 0.55), "M_Dusty": ("#b1a78f", 0.9),
    "M_WorkPants": ("#5a5e69", 0.9),
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


def ellipsoid_vf(radii, seg=12, rings=8, clip_top=None, clip_bottom=None):
    rx, ry, rz = radii
    prof = [(rx * math.sin(math.pi * j / rings), -rz * math.cos(math.pi * j / rings)) for j in range(rings + 1)]
    prof[0], prof[-1] = (0.0, -rz), (0.0, rz)
    v, f = lathe_vf(prof, seg, 1.0, ry / rx)
    if clip_top is not None:  # flatten the top (half-lidded eyes, D-shaped mouths)
        for p in v:
            p.z = min(p.z, clip_top)
    if clip_bottom is not None:  # flat soles
        for p in v:
            p.z = max(p.z, clip_bottom)
    return v, f


def box_vf(sx, sy, sz):
    """Axis aligned box centred on the origin (half sizes)."""
    k = math.sqrt(2.0)
    return lathe_vf([(0.0, -sz), (k, -sz), (k, sz), (0.0, sz)], 4, sx, sy, phase=math.pi / 4)


def rbox_vf(sx, sy, sz, r=0.3, seg=16):
    """Rounded box-ish (superellipse lathe) - softer than box_vf."""
    prof = [(0.0, -sz), (1.0 - r * 0.6, -sz), (1.0, -sz * (1 - r)), (1.0, sz * (1 - r)), (1.0 - r * 0.6, sz),
            (0.0, sz)]

    def sq(p, a, z):
        c, s = math.cos(a), math.sin(a)
        k = 1.0 / max(abs(c), abs(s)) ** 0.55 if max(abs(c), abs(s)) > 0 else 1.0
        return Vector((p.x * k, p.y * k, p.z))
    v, f = lathe_vf(prof, seg, sx, sy, phase=0.0, deform=sq)
    return v, f


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


def tube_vf(pts, radius, seg=6, closed=False, up=(0.0, 0.0, 1.0), caps=True, round_caps=0):
    """Tube through points. radius: float, list of floats or list of (r_side, r_up).
    round_caps=n closes the ends with n shrinking rings (a rounded capsule end)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    up = Vector(up)

    def rr(i):
        r = radius[i] if isinstance(radius, list) else radius
        return (r, r) if isinstance(r, (int, float)) else r

    def frame(i):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        nn = up - up.dot(t) * t
        if nn.length < 1e-6:
            nn = Vector((1.0, 0.0, 0.0)) - t * t.x
        nn.normalize()
        return t, nn, t.cross(nn)

    verts, faces, rings = [], [], []

    def ring_at(p, nn, b, rw, rh):
        ring = []
        for j in range(seg):
            th = TAU * j / seg
            ring.append(len(verts))
            verts.append(p + b * (rw * math.cos(th)) + nn * (rh * math.sin(th)))
        return ring

    t0, nn0, b0 = frame(0)
    if round_caps and not closed:
        rw, rh = rr(0)
        for k in range(round_caps, 0, -1):
            a = (math.pi / 2) * k / (round_caps + 1)
            rings.append(ring_at(pts[0] - t0 * (max(rw, rh) * math.sin(a)), nn0, b0, rw * math.cos(a),
                                 rh * math.cos(a)))
    for i, p in enumerate(pts):
        t, nn, b = frame(i)
        rw, rh = rr(i)
        rings.append(ring_at(p, nn, b, rw, rh))
    t1, nn1, b1 = frame(n - 1)
    if round_caps and not closed:
        rw, rh = rr(n - 1)
        for k in range(1, round_caps + 1):
            a = (math.pi / 2) * k / (round_caps + 1)
            rings.append(ring_at(pts[-1] + t1 * (max(rw, rh) * math.sin(a)), nn1, b1, rw * math.cos(a),
                                 rh * math.cos(a)))
    nr = len(rings)
    for i in range(nr if closed else nr - 1):
        A, B = rings[i], rings[(i + 1) % nr]
        faces += [(A[j], B[j], B[(j + 1) % seg], A[(j + 1) % seg]) for j in range(seg)]
    if caps and not closed:
        c0 = len(verts)
        first = pts[0] - (t0 * max(rr(0)) if round_caps else Vector())
        verts.append(first)
        faces += [(c0, rings[0][j], rings[0][(j + 1) % seg]) for j in range(seg)]
        c1 = len(verts)
        last = pts[-1] + (t1 * max(rr(n - 1)) if round_caps else Vector())
        verts.append(last)
        faces += [(c1, rings[-1][(j + 1) % seg], rings[-1][j]) for j in range(seg)]
    return verts, faces


def bill_vf(w, l, t, n=10, bend=0.0):
    """Flat D-shaped cap bill: attached (straight) edge along X at y=0, rounded tip at y=-l."""
    outline = [(w * math.cos(math.pi * i / n), -l * math.sin(math.pi * i / n)) for i in range(n + 1)]
    outline = outline[::-1]
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
    """Ellipsoid hood with an oval face opening, parametrised around the face axis (-Y)."""
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


def decal_vf(f, a, z, outline, off=0.004, thick=0.0):
    """Patch conforming to surface f around (a, z). outline: CCW (u, v) metres.
    thick > 0 gives it a raised edge (a flat puck) so it reads from grazing angles."""
    du, dz = _metric(f, a, z)

    def P(aa, zz, o):
        return f(aa, zz) + snormal(f, aa, zz) * o
    k = len(outline)
    if thick <= 0:
        verts = [P(a, z, off)] + [P(a + u / du, z + v / dz, off) for (u, v) in outline]
        return verts, [(0, i + 1, (i + 1) % k + 1) for i in range(k)]
    verts = [P(a, z, off + thick)] + [P(a + u / du, z + v / dz, off + thick) for (u, v) in outline]
    verts += [P(a + u * 1.06 / du, z + v * 1.06 / dz, off - 0.002) for (u, v) in outline]
    faces = [(0, i + 1, (i + 1) % k + 1) for i in range(k)]
    faces += [(i + 1, k + 1 + i, k + 1 + (i + 1) % k, (i + 1) % k + 1) for i in range(k)]
    return verts, faces


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


def blend3(phi, front, side, back):
    a = abs(math.atan2(math.sin(phi), math.cos(phi)))
    if a < math.pi / 2:
        return front + (side - front) * sstep(a / (math.pi / 2))
    return side + (back - side) * sstep((a - math.pi / 2) / (math.pi / 2))



# --------------------------------------------------------------------------- skeleton / proportions
# Unscaled proportions (metres) of the default villager; Char(scale=..) scales everything.
DEF = dict(
    # legs: hip joint, knee, ankle (all straight down at rest), toe tip
    hip_z=0.335, leg_x=0.07, knee_z=0.205, ankle_z=0.078, toe_y=-0.085, toe_z=0.03,
    thigh_r=0.05, knee_r=0.042, shin_r=0.041, ankle_r=0.033,
    # spine joints
    pelvis_z=0.35, spine_z=0.425, chest_z=0.495, neck_z=0.598, head_z=0.646,
    # arms: shoulder joint, rest A-pose angle from vertical, segment lengths, radii
    sh_x=0.126, sh_z=0.556, arm_a=35.0, l_up=0.112, l_fore=0.098, l_hand=0.07,
    up_r=0.034, elbow_r=0.031, fore_r=0.03, wrist_r=0.026, hand_k=1.0,
    # head
    head_c=0.846, head_r=(0.228, 0.212, 0.206),
)
BONES = ("hips", "spine", "chest", "neck", "head", "upperarm_L", "forearm_L", "hand_L", "upperarm_R",
         "forearm_R", "hand_R", "thigh_L", "shin_L", "foot_L", "thigh_R", "shin_R", "foot_R")
EXTRAS = ("extra_eye_L", "extra_eye_R", "extra_brow_L", "extra_brow_R", "extra_mouth", "extra_jaw")
FRONT = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))


def sfx(side):
    return "L" if side > 0 else "R"


class Char:
    def __init__(self, name, scale=1.0, style=None, **kw):
        self.name, self.S = name, scale
        self.d = dict(DEF, **kw)
        self.style = dict(style or {})
        d = self.d
        self.hc = Vector((0.0, 0.0, d["head_c"]))
        self.hr = d["head_r"]
        self.head = ell_surf(self.hc, self.hr)
        self.chunks = []
        self.extras = {}          # extra bone name -> (point, outward normal) (unscaled)
        self.blush = []           # (centre, radius) cheek tint spots
        self.skin = "M_Skin"

    # ---- geometry bookkeeping
    def add(self, rule, vf, m, smooth=True):
        self.chunks.append((vf[0], vf[1], m, smooth, rule))

    def hp(self, yaw, el, lift=0.0):
        a, e = rad(yaw), rad(el)
        n = snormal(self.head, a, e)
        return self.head(a, e) + n * lift, n

    def head_path(self, pts, lift):
        return [self.hp(y, e, lift)[0] for (y, e) in pts]

    # ---- joints (unscaled)
    def arm_dir(self, side):
        a = rad(self.d["arm_a"])
        return Vector((side * math.sin(a), 0.0, -math.cos(a)))

    def arm_pts(self, side):
        d = self.d
        S = Vector((side * d["sh_x"], 0.0, d["sh_z"]))
        v = self.arm_dir(side)
        E = S + v * d["l_up"]
        W = E + v * d["l_fore"]
        return S, v, E, W

    def leg_pts(self, side):
        d = self.d
        x = side * d["leg_x"]
        return (Vector((x, 0.0, d["hip_z"])), Vector((x, 0.0, d["knee_z"])), Vector((x, 0.0, d["ankle_z"])))

    # ---- skin weights (rules are evaluated on the unscaled rest position)
    def w_spine(self, z):
        d = self.d
        w = {"hips": 1.0}
        for bone, z0, wd in (("spine", d["spine_z"], 0.035), ("chest", d["chest_z"] + 0.01, 0.04),
                             ("neck", d["neck_z"] + 0.006, 0.018), ("head", d["head_z"] + 0.012, 0.014)):
            t = ss(z0 - wd, z0 + wd, z)
            for k in w:
                w[k] *= 1.0 - t
            w[bone] = t
        return w

    @staticmethod
    def _mix(w, bone, a):
        if a <= 0:
            return
        for k in w:
            w[k] *= 1.0 - a
        w[bone] = w.get(bone, 0.0) + a

    def w_torso(self, p, arm_k=0.5, thigh_k=0.3, arm_r=0.085):
        d = self.d
        w = self.w_spine(p.z)
        for side in (1, -1):
            S = Vector((side * d["sh_x"], 0.0, d["sh_z"]))
            lat = p.x * side
            if lat > 0.02:
                a = arm_k * ss(arm_r, 0.02, (p - S).length) * ss(0.03, 0.09, lat)
                self._mix(w, "upperarm_" + sfx(side), a)
        if p.z < d["hip_z"] + 0.03 and thigh_k > 0:
            k = thigh_k * ss(d["hip_z"] + 0.03, d["hip_z"] - 0.04, p.z)
            sL = ss(-0.05, 0.05, p.x)
            self._mix(w, "thigh_L", k * sL)
            self._mix(w, "thigh_R", k * (1 - sL) / max(1e-6, 1 - k * sL))
        return w

    def w_pelvis(self, p):
        d = self.d
        w = self.w_spine(p.z)
        k = 0.85 * ss(d["hip_z"] + 0.01, d["hip_z"] - 0.055, p.z)
        sL = ss(-0.035, 0.035, p.x)
        self._mix(w, "thigh_L", k * sL)
        self._mix(w, "thigh_R", k * (1 - sL) / max(1e-6, 1 - k * sL))
        return w

    def w_skirt(self, p, kmax=0.72):
        d = self.d
        k = kmax * ss(d["hip_z"] + 0.04, d["ankle_z"] + 0.02, p.z)
        sL = ss(-0.08, 0.08, p.x)
        sh = 0.45 * ss(d["knee_z"] + 0.02, d["ankle_z"], p.z)
        w = {b: v * (1 - k) for b, v in self.w_spine(p.z).items()}
        w["thigh_L"] = k * sL * (1 - sh)
        w["shin_L"] = k * sL * sh
        w["thigh_R"] = k * (1 - sL) * (1 - sh)
        w["shin_R"] = k * (1 - sL) * sh
        return w

    def w_arm(self, p, side):
        d = self.d
        S, v, E, W = self.arm_pts(side)
        s = (p - S).dot(v)
        lu, lw = d["l_up"], d["l_up"] + d["l_fore"]
        t1 = ss(lu - 0.03, lu + 0.03, s)
        t2 = ss(lw - 0.014, lw + 0.014, s)
        x = sfx(side)
        w = {"upperarm_" + x: 1 - t1, "forearm_" + x: t1 * (1 - t2), "hand_" + x: t1 * t2}
        self._mix(w, "chest", 0.42 * ss(0.025, -0.04, s))
        return w

    def w_leg(self, p, side):
        d = self.d
        s = d["hip_z"] - p.z
        lk, la = d["hip_z"] - d["knee_z"], d["hip_z"] - d["ankle_z"]
        t1 = ss(lk - 0.03, lk + 0.03, s)
        t2 = ss(la - 0.012, la + 0.012, s)
        x = sfx(side)
        w = {"thigh_" + x: 1 - t1, "shin_" + x: t1 * (1 - t2), "foot_" + x: t1 * t2}
        self._mix(w, "hips", 0.45 * ss(0.03, -0.035, s))
        return w

    def weights(self, rule, p):
        kind, side = (rule if isinstance(rule, tuple) else (rule, 0))
        if kind == "head":
            return {"head": 1.0}
        if kind in ("eye", "brow"):
            return {"extra_%s_%s" % (kind, sfx(side)): 1.0}
        if kind == "mouth":
            return {"extra_mouth": 1.0}
        if kind == "jaw":
            return {"extra_jaw": 1.0}
        if kind == "hand":
            return {"hand_" + sfx(side): 1.0}
        if kind == "foot":
            return {"foot_" + sfx(side): 1.0}
        if kind == "torso":
            return self.w_torso(p)
        if kind == "torso_rigid":   # things sitting on the chest (bags, chains): no shoulder/thigh pull
            return self.w_torso(p, arm_k=0.0, thigh_k=0.0)
        if kind == "cape":         # hijab / shawl over the shoulders: follows the upper arms more
            return self.w_torso(p, arm_k=0.62, thigh_k=0.0, arm_r=0.13)
        if kind == "pelvis":
            return self.w_pelvis(p)
        if kind == "skirt":
            return self.w_skirt(p)
        if kind == "arm":
            return self.w_arm(p, side)
        if kind == "leg":
            return self.w_leg(p, side)
        raise ValueError(rule)


# --------------------------------------------------------------------------- face / head
def face(c, skin, eyes="round", mouth="smile", brows="normal", brow_mat="M_Dark", ears=True, nose=True,
         eye_yaw=25.0, eye_el=-6.0, eye_k=1.0, hl="M_White", lash=False, blush=True, mouth_el=-21.0):
    DK = "M_Dark"
    c.skin = skin
    c.add("head", xf(ellipsoid_vf(c.hr, 24, 13), T(c.hc)), skin)
    if ears:
        for s in (1, -1):
            p, n = c.hp(90 * s, -8, -0.012)
            c.add("head", xf(ellipsoid_vf((0.032, 0.022, 0.042), 8, 5), orient(p, n)), skin)
            p2, n2 = c.hp(90 * s, -8, 0.004)
            c.add("head", xf(ellipsoid_vf((0.016, 0.008, 0.024), 6, 3), orient(p2 + n2 * 0.004, n2)), skin)
    if nose:
        p, n = c.hp(0, -13.5, -0.008)
        c.add("head", xf(ellipsoid_vf((0.021, 0.018, 0.016), 8, 4), orient(p, n)), skin)
    for s in (1, -1):
        y = s * eye_yaw
        p, n = c.hp(y, eye_el, 0.0)
        c.extras["extra_eye_" + sfx(s)] = (p.copy(), n.copy())
        E = orient(p, n)
        rule = ("eye", s)
        if eyes in ("round", "big", "smug"):
            k = eye_k * (1.14 if eyes == "big" else 1.0)
            clip = 0.012 * k if eyes == "smug" else None
            c.add(rule, xf(ellipsoid_vf((0.026 * k, 0.012, 0.037 * k), 10, 6, clip_top=clip), E @ T(0, 0.004, 0)),
                  DK)
            if hl:
                c.add(rule, xf(ellipsoid_vf((0.0095 * k, 0.004, 0.011 * k), 8, 4),
                               E @ T(0.0085 * k, -0.0085, (0.004 if eyes == "smug" else 0.013) * k)), hl)
                c.add(rule, xf(ellipsoid_vf((0.0048 * k, 0.003, 0.0048 * k), 6, 3),
                               E @ T(-0.009 * k, -0.0082, -0.016 * k)), hl)
            if eyes == "smug":   # heavy upper lid
                lid = [(y - s * 5.2, eye_el + 1.6), (y, eye_el + 2.6), (y + s * 5.2, eye_el + 1.2)]
                c.add(rule, tube_vf(c.head_path(lid, 0.004), [0.004, 0.006, 0.004], 5, round_caps=1), DK)
            if lash:
                lp = [(y - s * 4.5, eye_el + 4.2 * k), (y + s * 1.5, eye_el + 5.4 * k), (y + s * 6.8, eye_el + 4.6 * k),
                      (y + s * 8.6, eye_el + 6.6 * k)]
                c.add(rule, tube_vf(c.head_path(lp, 0.003), [0.0025, 0.0045, 0.004, 0.002], 5), DK)
        elif eyes == "narrow":
            c.add(rule, xf(ellipsoid_vf((0.029, 0.01, 0.013), 10, 5), E @ T(0, 0.003, 0)), DK)
            lid = [(y - s * 6, eye_el + 0.5), (y, eye_el + 2.2), (y + s * 6, eye_el + 2.6)]
            c.add(rule, tube_vf(c.head_path(lid, 0.003), [0.004, 0.0055, 0.004], 5), DK)
        elif eyes == "happy":
            pts = [(y + 4.2 * t, eye_el - 1.5 + 3.8 * (1 - t * t)) for t in (-1, -0.5, 0, 0.5, 1)]
            c.add(rule, tube_vf(c.head_path(pts, 0.002), [0.0045, 0.0065, 0.007, 0.0065, 0.0045], 6), DK)
        if blush:
            bp, _ = c.hp(s * 41, -17.5, 0.0)
            c.blush.append((bp, 0.04))
    # brows
    if brows:
        for s in (1, -1):
            y0 = s * eye_yaw
            e0 = eye_el + 13.0 * eye_k
            r = [0.0045, 0.007, 0.0045]
            if brows == "normal":
                pts = [(y0 - s * 6, e0), (y0, e0 + 1.3), (y0 + s * 6, e0)]
            elif brows == "soft":
                pts = [(y0 - s * 5.5, e0 + 0.5), (y0, e0 + 1.8), (y0 + s * 5.5, e0 + 0.2)]
                r = [0.0035, 0.0055, 0.0035]
            elif brows == "smug":
                lift = 2.6 if s > 0 else 0.0
                pts = [(y0 - s * 6, e0 + lift - 1.0), (y0, e0 + lift + 1.0), (y0 + s * 6, e0 + lift - 0.2)]
            elif brows == "angry":
                pts = [(y0 - s * 7, e0 - 3.5), (y0, e0 - 1.0), (y0 + s * 6, e0 + 1.2)]
                r = [0.0065, 0.0095, 0.0065]
            elif brows == "worried":
                pts = [(y0 - s * 6, e0 + 2.2), (y0, e0 + 1.2), (y0 + s * 6, e0 - 0.8)]
            elif brows == "bushy":
                pts = [(y0 - s * 7, e0 - 0.5), (y0, e0 + 1.4), (y0 + s * 7, e0 - 1.5)]
                r = [0.008, 0.012, 0.008]
            bp, bn = c.hp(y0, e0 + 0.5, 0.0)
            c.extras["extra_brow_" + sfx(s)] = (bp, bn)
            c.add(("brow", s), tube_vf(c.head_path(pts, 0.005), r, 5, round_caps=1), brow_mat)
    # mouth (the resting expression line) + the open mouth (extra_jaw, scaled open when talking)
    me = mouth_el
    mp, mn = c.hp(0, me - 0.5, 0.0)
    c.extras["extra_mouth"] = (mp, mn)
    c.extras["extra_jaw"] = (mp, mn)
    rr = [0.0035, 0.0055, 0.006, 0.0055, 0.0035]
    if mouth == "smile":
        pts = [(yy, me - 2.6 * (1 - (yy / 8.5) ** 2)) for yy in (-8.5, -4.2, 0, 4.2, 8.5)]
    elif mouth == "grin":
        pts = [(yy, me - 3.2 * (1 - (yy / 10.0) ** 2)) for yy in (-10, -5, 0, 5, 10)]
    elif mouth == "smirk":
        pts = [(-6, me - 0.6), (-2, me - 1.0), (2, me - 0.6), (6, me + 0.6), (9.5, me + 2.6)]
    elif mouth == "flat":
        pts = [(-6, me - 0.8), (-2, me - 1.2), (2, me - 1.2), (6, me - 0.8)]
        rr = rr[:4]
    elif mouth == "frown":
        pts = [(yy, me - 1.5 + 1.8 * (1 - (yy / 7.0) ** 2)) for yy in (-7, -3.5, 0, 3.5, 7)]
    else:
        pts = None
    if pts:
        c.add("mouth", tube_vf(c.head_path(pts, 0.0025), rr, 6, round_caps=1), DK)
    # open mouth: a thin dark lens hidden behind the line, scaled open by extra_jaw
    c.add("jaw", xf(ellipsoid_vf((0.02, 0.006, 0.0035), 10, 5), orient(mp + mn * 0.0005, mn)), DK)


def hair(c, m, front=68, side=95, back=118, part=0.0, lift=0.016, rim=0.93, seg=24, rings=5, rmod=None,
         off=(0.0, 0.004, 0.006), tmin=0.0):
    """Hair cap. tmin (deg) > 0 = only the band peeking out below a hat."""
    radii = tuple(r + lift for r in c.hr)

    def tmax(phi):
        return rad(blend3(phi, front, side, back) + part * math.sin(phi) * max(0.0, math.cos(phi)))
    c.add("head", xf(shell_vf(radii, tmax, seg, rings, rim, rmod, rad(tmin)), T(c.hc + Vector(off))), m)


def messy_hair(c, m, front=66, side=94, back=112, teeth=14, amp=13.0, lump=0.045, lump2=0.03, lift=0.02, seg=28,
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
    c.add("head", xf(shell_vf(radii, tmax, seg, rings, 0.9, lumpy), T(c.hc + Vector((0, 0.006, 0.01)))), m)


def cowlick(c, m, spots, lift=0.026):
    """Short, wide, slightly flattened cones sticking up from the crown: (yaw, el, dir, length)."""
    hs = ell_surf(c.hc + Vector((0, 0.006, 0.01)), tuple(r + lift for r in c.hr))
    for (y, e, d, L) in spots:
        p = hs(rad(y), rad(e))
        n = snormal(hs, rad(y), rad(e))
        z = (n + Vector(d)).normalized()
        c.add("head", xf(lathe_vf([(0.052, -0.035), (0.04, 0.008), (0.0, L)], 8, 1.0, 0.6),
                         align_z(p - n * 0.018, z)), m)


def moustache(c, m, thick=1.0, droop=4.0, width=15.0, el=-15.0):
    ys = [-width, -width * 0.6, -width * 0.27, 0.0, width * 0.27, width * 0.6, width]
    es = [el - droop, el - 0.3, el + 0.5, el, el + 0.5, el - 0.3, el - droop]
    r = [x * thick for x in (0.004, 0.011, 0.013, 0.01, 0.013, 0.011, 0.004)]
    c.add("head", tube_vf(c.head_path(list(zip(ys, es)), 0.007 * thick), r, 6, round_caps=1), m)


def sunglasses_on_face(c, m, eye_yaw=25.0, eye_el=-6.0):
    for s in (1, -1):
        p, n = c.hp(s * eye_yaw, eye_el, 0.012)
        c.add("head", xf(ellipsoid_vf((0.05, 0.012, 0.035), 12, 6), orient(p, n)), m)
    br = c.head_path([(-eye_yaw + 11, eye_el + 2), (0, eye_el + 3.5), (eye_yaw - 11, eye_el + 2)], 0.017)
    c.add("head", tube_vf(br, 0.005, 5), m)
    for s in (1, -1):
        tp = c.head_path([(s * (eye_yaw + 12), eye_el + 2), (s * 60, eye_el + 3), (s * 86, eye_el + 1)], 0.008)
        c.add("head", tube_vf(tp, 0.0045, 5), m)


def hat_xf(c, tilt=-10.0, roll=0.0, lift=0.0, fwd=0.0):
    """Transform for hat profiles designed on the reference head (radius 0.228)."""
    return T(c.hc + Vector((0.0, fwd, lift))) @ R("X", tilt) @ R("Y", roll) @ Sc(c.hr[0] / 0.228)


# --------------------------------------------------------------------------- body
# (radius, z) profiles, revolved with sy = BODY_SY
TORSO = [(0.0, 0.296), (0.118, 0.297), (0.146, 0.308), (0.153, 0.33), (0.151, 0.39), (0.147, 0.45),
         (0.141, 0.5), (0.128, 0.545), (0.101, 0.58), (0.062, 0.603), (0.0, 0.61)]
TUCKED = [(0.0, 0.33), (0.13, 0.331), (0.146, 0.345), (0.149, 0.39)] + TORSO[5:]
PELVIS = [(0.0, 0.262), (0.07, 0.265), (0.116, 0.279), (0.137, 0.305), (0.143, 0.345), (0.14, 0.385),
          (0.0, 0.395)]
BODY_SY = 0.84


def torso(c, m, prof=TORSO, sx=1.0, sy=BODY_SY, deform=None, seg=20, hem=True, hem_mat=None, rule="torso"):
    c.add(rule, lathe_vf(prof, seg, sx, sy, deform=deform), m)
    surf = lathe_surf(prof, sx, sy, deform)
    if hem:   # a rolled hem at the bottom edge so the shirt reads as cloth
        z0 = [p for p in prof if p[0] > 0][0][1]
        r0 = surf.r_at(z0 + 0.012)
        ring = [(r0 + 0.004, z0 - 0.002), (r0 + 0.011, z0 + 0.004), (r0 + 0.012, z0 + 0.014),
                (r0 + 0.004, z0 + 0.022)]
        c.add(rule, lathe_vf(ring, seg, sx, sy, deform=deform), hem_mat or m)
    return surf


def pelvis(c, m, prof=PELVIS, sx=1.0, sy=BODY_SY, seg=18):
    c.add("pelvis", lathe_vf(prof, seg, sx, sy), m)


def neck(c, skin, r=0.047):
    d = c.d
    c.add("torso", lathe_vf([(0.0, d["neck_z"] - 0.03), (r, d["neck_z"] - 0.025), (r * 0.95, d["head_z"] + 0.03),
                             (0.0, d["head_z"] + 0.05)], 12), skin)


def collar(c, m, z=0.592, rx=0.078, ry=0.068, dip=0.03, thick=(0.016, 0.02), vneck=True, seg=20):
    """A thick rolled collar round the neck opening (dips at the front for a V-neck)."""
    loop = []
    for i in range(seg):
        t = TAU * i / seg
        front = max(0.0, math.cos(t))
        zz = z - (dip * front ** 3 if vneck else 0.0) + 0.006 * (1 - front)
        loop.append(Vector((rx * math.sin(t), -ry * math.cos(t) * (1 + 0.1 * front), zz)))
    c.add("torso", tube_vf(loop, thick, 5, closed=True), m)


def collar_flaps(c, m, z=0.6, spread=0.05, length=0.06, thick=0.01):
    """Two pointed shirt-collar flaps lying on the chest."""
    for s in (1, -1):
        base = Vector((s * 0.03, -0.075, z))
        tip = Vector((s * (0.03 + spread), -0.115, z - length))
        side = Vector((s * 0.07, -0.03, z - 0.005))
        pts = [base, side, tip]
        n = (side - base).cross(tip - base).normalized()
        if n.y > 0:
            n = -n
        v = [p + n * thick for p in pts] + [p - n * thick * 0.3 for p in pts]
        f = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
        if s < 0:
            f = [tuple(reversed(ff)) for ff in f]
        c.add("torso", (v, f), m, smooth=False)


def arms(c, skin, sleeve=None, sleeve_mat=None, cuff_mat=None, puff=1.0):
    """Arms with elbows and mitten hands with a thumb. sleeve: None/'tank', 'short', 'rolled', 'long'."""
    d = c.d
    k = d["hand_k"]
    lu, lf = d["l_up"], d["l_fore"]
    for side in (1, -1):
        rule = ("arm", side)
        S, v, E, W = c.arm_pts(side)
        s_ = [-0.035, 0.0, 0.05, lu, lu + 0.05, lu + lf - 0.004]
        rr_ = [d["up_r"] * 0.9, d["up_r"], d["up_r"] * 0.97, d["elbow_r"], d["fore_r"], d["wrist_r"]]
        if sleeve == "long":
            s_, rr_ = s_[-2:], rr_[-2:]
            s_[0] = lu + lf - 0.05
        c.add(rule, tube_vf([S + v * s for s in s_], rr_, 8, up=FRONT, round_caps=1), skin)
        # hand: flattened mitten (palm faces the body) + thumb pointing forward
        Hf = frame_y(W, v, FRONT)
        c.add(("hand", side), xf(ellipsoid_vf((0.027 * k, 0.034 * k, 0.041 * k), 10, 6),
                                 Hf @ T(0, 0.034 * k, 0.0) @ R("X", -90)), skin)
        th = [Hf @ Vector((side * 0.004, 0.014 * k, 0.018 * k)), Hf @ Vector((side * 0.002, 0.032 * k, 0.035 * k)),
              Hf @ Vector((0.0, 0.047 * k, 0.04 * k))]
        c.add(("hand", side), tube_vf(th, [0.012 * k, 0.012 * k, 0.0105 * k], 6, up=v, round_caps=2), skin)
        # sleeves
        sm = sleeve_mat
        if sleeve in ("short", "rolled"):
            end = 0.07 if sleeve == "short" else lu + 0.012
            r0 = (d["up_r"] + 0.018) * puff
            pts = [S + v * s for s in (-0.03, 0.0, 0.035, end - 0.012, end)]
            c.add(rule, tube_vf(pts, [r0 * 0.9, r0 * 1.02, r0, r0 * 0.93, r0 * 0.9], 10, up=FRONT, round_caps=1), sm)
            # thick rolled hem / cuff
            hr_ = r0 * 0.93 + (0.006 if sleeve == "short" else 0.01)
            hw = 0.008 if sleeve == "short" else 0.014
            c.add(rule, tube_vf([S + v * (end - hw), S + v * (end + hw * 0.6)], [hr_, hr_ * 0.97], 10, up=FRONT,
                                round_caps=1), cuff_mat or sm)
        elif sleeve == "long":
            r0 = (d["up_r"] + 0.015) * puff
            pts = [S + v * s for s in (-0.03, 0.0, 0.04, lu, lu + 0.05, lu + lf - 0.012)]
            rr2 = [r0 * 0.92, r0, r0 * 0.97, d["elbow_r"] + 0.012, d["fore_r"] + 0.011, d["wrist_r"] + 0.012]
            c.add(rule, tube_vf(pts, rr2, 10, up=FRONT, round_caps=1), sm)
            cw = lu + lf - 0.016
            c.add(rule, tube_vf([S + v * (cw - 0.008), S + v * (cw + 0.01)],
                                [d["wrist_r"] + 0.016, d["wrist_r"] + 0.015], 10, up=FRONT, round_caps=1),
                  cuff_mat or sm)


def legs(c, skin, pants=None, pants_mat=None, foot="shoe", foot_mat="M_Dark", strap_mat=None, sole_mat=None,
         shorts_z=0.235, hem_mat=None, dress=False, sock_mat=None):
    """pants: None (bare), 'shorts', 'rolled' (below the knee), 'long'. dress=True: only the ankles show."""
    d = c.d
    for side in (1, -1):
        rule = ("leg", side)
        H, K, A = c.leg_pts(side)
        x = H.x
        up = Vector((0, 0, 1))
        if dress:
            c.add(rule, tube_vf([A + up * 0.085, A + up * 0.02], [d["ankle_r"] * 1.05, d["ankle_r"]], 10,
                                up=FRONT, round_caps=1), skin)
        elif pants != "long":
            zs = [H.z + 0.03, H.z - 0.02, (H.z + K.z) / 2, K.z, (K.z + A.z) / 2 + 0.01, A.z + 0.015]
            rs = [d["thigh_r"] * 0.9, d["thigh_r"], d["thigh_r"] * 0.94, d["knee_r"], d["shin_r"], d["ankle_r"]]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 8, up=FRONT, round_caps=1), sock_mat or skin)
        hm = hem_mat or pants_mat
        if pants == "long":
            zs = [H.z + 0.04, H.z - 0.02, (H.z + K.z) / 2, K.z, (K.z + A.z) / 2, A.z + 0.03, A.z + 0.004]
            rs = [d["thigh_r"] + 0.006, d["thigh_r"] + 0.012, d["thigh_r"] + 0.008, d["knee_r"] + 0.012,
                  d["shin_r"] + 0.013, d["ankle_r"] + 0.016, d["ankle_r"] + 0.017]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 10, up=FRONT, round_caps=1), pants_mat)
        elif pants in ("shorts", "rolled"):
            z0 = shorts_z if pants == "shorts" else K.z - 0.035
            zs = [H.z + 0.04, H.z - 0.02, (H.z + z0) / 2, z0]
            rs = [d["thigh_r"] + 0.012, d["thigh_r"] + 0.02, d["thigh_r"] + 0.018, d["thigh_r"] + 0.014]
            if pants == "rolled":
                rs = [d["thigh_r"] + 0.008, d["thigh_r"] + 0.013, d["knee_r"] + 0.014, d["shin_r"] + 0.012]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 10, up=FRONT, round_caps=1), pants_mat)
            hw = 0.009 if pants == "shorts" else 0.016
            c.add(rule, tube_vf([Vector((x, 0, z0 + hw)), Vector((x, 0, z0 - hw * 0.5))],
                                [rs[-1] + 0.006, rs[-1] + 0.005], 10, up=FRONT, round_caps=1), hm)
        # feet
        fy = -0.026
        fr = ("foot", side)
        if foot in ("sandal", "bare"):
            c.add(fr, xf(ellipsoid_vf((0.043, 0.066, 0.03), 10, 6, clip_bottom=-0.018),
                         T(x, fy, 0.033 if foot == "sandal" else 0.028)), skin)
            if foot == "sandal":
                c.add(fr, xf(ellipsoid_vf((0.05, 0.078, 0.012), 12, 4), T(x, fy - 0.004, 0.011)), foot_mat)
                pts = []
                for t in (-1, -0.4, 0.4, 1):
                    ang = t * rad(78)
                    pts.append((x + 0.044 * math.sin(ang), fy - 0.026, 0.034 + 0.031 * math.cos(ang)))
                c.add(fr, tube_vf(pts, 0.0085, 5, up=(0, 1, 0), round_caps=1), strap_mat or foot_mat)
        elif foot in ("shoe", "boot"):
            c.add(fr, xf(ellipsoid_vf((0.05, 0.079, 0.045), 12, 7, clip_bottom=-0.03), T(x, fy - 0.002, 0.042)),
                  foot_mat)
            c.add(fr, xf(ellipsoid_vf((0.054, 0.084, 0.013), 12, 4), T(x, fy - 0.002, 0.012)), sole_mat or foot_mat)
            if foot == "boot":
                c.add(rule, tube_vf([Vector((x, 0, z)) for z in (0.06, 0.1, 0.14, 0.158)],
                                    [0.049, 0.05, 0.052, 0.055], 12, up=FRONT, round_caps=1), foot_mat)


def hem_ring(c, surf, z, m, sx=1.0, sy=BODY_SY, out=0.008, w=0.012, seg=20, rule="torso"):
    r0 = surf.r_at(z)
    prof = [(r0 + out * 0.4, z - w), (r0 + out, z - w * 0.4), (r0 + out, z + w * 0.4), (r0 + out * 0.4, z + w)]
    c.add(rule, lathe_vf(prof, seg, sx, sy), m)



# --------------------------------------------------------------------------- assembly
def build_rig(c, name):
    S, d = c.S, c.d
    arm = bpy.data.armatures.new(name + "_Rig")
    ob = bpy.data.objects.new(name, arm)
    link(ob)
    arm.display_type = "STICK"
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones

    def bone(n, head, tail, parent=None, connect=False, roll_to=FRONT):
        b = eb.new(n)
        b.head = Vector(head) * S
        b.tail = Vector(tail) * S
        b.align_roll(Vector(roll_to))
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        return b

    def z(v):
        return Vector((0.0, 0.0, v))
    bone("hips", z(d["pelvis_z"]), z(d["spine_z"]))
    bone("spine", z(d["spine_z"]), z(d["chest_z"]), "hips", True)
    bone("chest", z(d["chest_z"]), z(d["neck_z"]), "spine", True)
    bone("neck", z(d["neck_z"]), z(d["head_z"]), "chest", True)
    bone("head", z(d["head_z"]), z(d["head_c"] + d["head_r"][2]), "neck", True)
    for side in (1, -1):
        x = sfx(side)
        S_, v, E, W = c.arm_pts(side)
        bone("upperarm_" + x, S_, E, "chest")
        bone("forearm_" + x, E, W, "upperarm_" + x, True)
        bone("hand_" + x, W, W + v * d["l_hand"], "forearm_" + x, True)
        H, K, A = c.leg_pts(side)
        bone("thigh_" + x, H, K, "hips")
        bone("shin_" + x, K, A, "thigh_" + x, True)
        bone("foot_" + x, A, Vector((H.x, d["toe_y"], d["toe_z"])), "shin_" + x, True, roll_to=UP)
    for n in EXTRAS:
        p, nrm = c.extras.get(n, (c.hc + Vector((0, -c.hr[1], 0)), FRONT))
        up = (UP - nrm * UP.dot(nrm)).normalized()
        bone(n, p, p + nrm * 0.03, "head", roll_to=up)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "XYZ"
    return ob


def build_mesh(c, name):
    verts, faces, fmat, fsmooth, mats, vw = [], [], [], [], [], []
    for (vs, fs, mname, smooth, rule) in c.chunks:
        if mname not in mats:
            mats.append(mname)
        mi = mats.index(mname)
        base = len(verts)
        for v in vs:
            v = Vector(v)
            vw.append(c.weights(rule, v))
            verts.append(v * c.S)
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
    nv = len(me.vertices)
    me.validate()
    assert len(me.vertices) == nv, "validate() removed vertices"
    ob = bpy.data.objects.new(name, me)
    link(ob)
    groups = {b: ob.vertex_groups.new(name=b) for b in BONES + EXTRAS}
    for i, w in enumerate(vw):
        items = sorted(((b, x) for b, x in w.items() if x > 0.004), key=lambda t: -t[1])[:4]
        tot = sum(x for _, x in items)
        for b, x in items:
            groups[b].add([i], x / tot, "REPLACE")
    return ob


def tint_blush(c, ob, tint=(1.0, 0.64, 0.74)):
    """Multiply the baked AO colours by a soft pink on the cheeks (skin faces only)."""
    if not c.blush:
        return
    me = ob.data
    col = me.color_attributes["Col"]
    skin_idx = [i for i, m in enumerate(me.materials) if m.name == c.skin]
    for poly in me.polygons:
        if poly.material_index not in skin_idx:
            continue
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co / c.S
            w = 0.0
            for (b, r) in c.blush:
                w = max(w, ss(r, r * 0.25, (p - b).length))
            if w > 0:
                cc = col.data[li].color
                col.data[li].color = tuple(cc[k] * lerp(1.0, tint[k], w) for k in range(3)) + (1.0,)


def assemble(c, bake=True):
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    name = "char_" + c.name
    rig = build_rig(c, name)
    body = build_mesh(c, "Body")
    if bake:
        bake_vertex_ao([body], samples=24, distance=0.13 * c.S, floor=0.5, gamma=0.8, ground=True)
        tint_blush(c, body)
    body.parent = rig
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return rig, body



# --------------------------------------------------------------------------- animation: curves
class Curve:
    """Keyed scalar curve with monotone cubic easing (behaves like Blender's auto-clamped
    Bezier keys: flat tangents at extremes -> ease in/out, smooth through the rest, no overshoot
    between keys). keys: [(frame, value)] or [(frame, value, tangent_scale)].
    period=N makes it cyclic (a key at N must equal the key at 0 or is added)."""

    def __init__(self, keys, period=None):
        keys = sorted(keys, key=lambda k: k[0])
        self.period = period
        if period:
            keys = [k for k in keys if k[0] < period - 1e-6]
            pre = [(k[0] - period,) + tuple(k[1:]) for k in keys[-2:]]
            post = [(k[0] + period,) + tuple(k[1:]) for k in keys[:2]]
            keys = pre + keys + post
        self.f = [float(k[0]) for k in keys]
        self.v = [float(k[1]) for k in keys]
        ts = [k[2] if len(k) > 2 else 1.0 for k in keys]
        n = len(self.f)
        self.m = [0.0] * n
        for i in range(n):
            if i == 0 or i == n - 1:
                continue
            h0, h1 = self.f[i] - self.f[i - 1], self.f[i + 1] - self.f[i]
            d0 = (self.v[i] - self.v[i - 1]) / h0
            d1 = (self.v[i + 1] - self.v[i]) / h1
            if d0 * d1 <= 0:
                m = 0.0
            else:
                m = 3 * (h0 + h1) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1)
            self.m[i] = m * ts[i]

    def __call__(self, t):
        f, v, m = self.f, self.v, self.m
        if self.period:
            t = t % self.period
        if t <= f[0]:
            return v[0]
        if t >= f[-1]:
            return v[-1]
        lo, hi = 0, len(f) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if f[mid] <= t:
                lo = mid
            else:
                hi = mid
        h = f[hi] - f[lo]
        s = (t - f[lo]) / h
        s2, s3 = s * s, s * s * s
        return ((2 * s3 - 3 * s2 + 1) * v[lo] + (s3 - 2 * s2 + s) * h * m[lo] + (-2 * s3 + 3 * s2) * v[hi]
                + (s3 - s2) * h * m[hi])


class Track:
    """Several channels, each a tuple-valued keyed curve. tracks: {chan: [(frame, tuple|scalar), ...]}"""

    def __init__(self, tracks, period=None, defaults=None):
        self.curves = {}
        self.period = period
        self.defaults = defaults or {}
        for ch, keys in tracks.items():
            vals = [(k[0], k[1] if isinstance(k[1], (tuple, list)) else (k[1],)) + tuple(k[2:]) for k in keys]
            dim = len(vals[0][1])
            self.curves[ch] = [Curve([(k[0], k[1][i]) + tuple(k[2:]) for k in vals], period) for i in range(dim)]

    def __call__(self, ch, t):
        if ch not in self.curves:
            return self.defaults[ch]
        return tuple(c(t) for c in self.curves[ch])


def cyc(phase):
    return math.cos(TAU * phase), math.sin(TAU * phase)


# --------------------------------------------------------------------------- animation: pose solver
def rotw(p, y, r):
    """World-aligned rotation: pitch (lean forward +), yaw (turn to own left +), roll (top to own left +)."""
    return (Matrix.Rotation(rad(y), 3, "Z") @ Matrix.Rotation(rad(p), 3, "X") @ Matrix.Rotation(rad(r), 3, "Y"))


def cols(x, y, z):
    return Matrix((x, y, z)).transposed()


def two_bone(S, Tg, L1, L2, pole, soft=0.95):
    """Two-bone IK with a soft reach limit (the limb straightens asymptotically instead of snapping
    when a target is almost or entirely out of reach). Returns (elbow/knee, point reached)."""
    d = Tg - S
    dist = d.length
    lo, hi = abs(L1 - L2) + 1e-4, (L1 + L2) * 0.9995
    ds = hi * soft
    if dist > ds:
        dist = ds + (hi - ds) * (1.0 - math.exp(-(dist - ds) / (hi - ds)))
    reach = clamp(dist, lo, hi)
    u = d / max(dist, 1e-9)
    p = pole - u * pole.dot(u)
    if p.length < 1e-6:
        p = Vector((0, 0, 1)) - u * u.z
    p.normalize()
    ca = clamp((L1 * L1 + reach * reach - L2 * L2) / (2 * L1 * reach), -1.0, 1.0)
    a = math.acos(ca)
    E = S + (u * math.cos(a) + p * math.sin(a)) * L1
    return E, S + u * reach


class Rig:
    def __init__(self, ob, c):
        self.ob, self.c, self.S = ob, c, c.S
        bones = ob.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.par = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.rel = {}
        for n, p in self.par.items():
            self.rel[n] = self.rest[p].inverted() @ self.rest[n] if p else self.rest[n].copy()
        self.len = {b.name: b.length for b in bones}
        self.warn = 0
        self.log = []

    def r3(self, b):
        return self.rest[b].to_3x3()

    def solve(self, P):
        """P: pose spec (see pose()). Returns {bone: (loc, Quaternion, scale)} pose-bone basis."""
        S = self.S
        out, W = {}, {}   # W: world (armature space) 4x4 matrices

        def put(b, rot3, loc=None, scale=None):
            loc = loc if loc is not None else Vector()
            out[b] = (loc, rot3.to_quaternion(), scale if scale is not None else Vector((1, 1, 1)))
            m = Matrix.Translation(loc) @ rot3.to_4x4()
            if scale is not None:
                m = m @ Matrix.Diagonal(tuple(scale) + (1.0,))
            parent = self.par[b]
            W[b] = (W[parent] @ self.rel[b] if parent else self.rest[b]) @ m

        def conj(b, Q):
            r = self.r3(b)
            return r.inverted() @ Q @ r

        # --- hips + spine chain (world-aligned rotations relative to the parent)
        r = self.r3("hips")
        put("hips", conj("hips", rotw(*P["hips"])), r.inverted() @ (Vector(P["hips_off"]) * S))
        for b in ("spine", "chest", "neck", "head"):
            put(b, conj(b, rotw(*P[b])))
        Qc = W["chest"].to_3x3() @ self.r3("chest").inverted()

        # --- arms
        for side in (1, -1):
            x = sfx(side)
            up, fo, ha = "upperarm_" + x, "forearm_" + x, "hand_" + x
            base = W["chest"] @ self.rel[up]
            Sw = base.translation
            sw, ab, tw, el = P["arm" + x]
            s_, c_ = math.sin(rad(sw)), math.cos(rad(sw))
            d1 = Qc @ Vector((side * math.sin(rad(ab)), -s_ * math.cos(rad(ab)), -c_ * math.cos(rad(ab))))
            w = Qc @ Vector((0.0, -c_, s_))
            w = Quaternion(d1, rad(side * tw)) @ w
            fk1 = cols(d1.cross(w), d1, w)
            d2 = d1 * math.cos(rad(el)) + w * math.sin(rad(el))
            fk2 = cols(d1.cross(w), d2, d1.cross(w).cross(d2))
            ikw = P.get("ik" + x, 0.0)
            f1, f2 = fk1, fk2
            if ikw > 1e-4:
                tgt = Vector(P["ikt" + x]) * S
                grip = P.get("grip" + x)
                if P.get("iksp", 0.0) > 0.5:     # target + grip axis given in the chest's rest frame
                    tgt = W["chest"] @ (self.rest["chest"].inverted() @ tgt)
                    grip = Qc @ Vector(grip) if grip is not None else None
                pole = Qc @ Vector(P.get("ikp" + x, (side * 0.7, 0.5, -0.5)))
                L1, L2 = self.len[up], self.len[fo]
                g = 0.036 * S * self.c.d["hand_k"]
                wr = tgt.copy()
                for _ in range(3):   # solve for the wrist so that the fist (not the wrist) lands on the target
                    E, reached = two_bone(Sw, wr, L1, L2, pole, soft=0.88)
                    D1 = (E - Sw).normalized()
                    D2 = (reached - E).normalized()
                    if grip is not None:
                        G = Vector(grip).normalized()
                        yh = (D2 - G * D2.dot(G)).normalized()
                    else:
                        yh = D2
                    wr = tgt - yh * g
                short = (tgt - Sw).length - (L1 + L2 + g)
                if short > 0.006 * S and ikw > 0.5:
                    self.warn += 1
                    self.log.append(("arm" + x, round(short / S, 3)))
                Wf = D2 - D1 * D1.dot(D2)
                Wf = Wf.normalized() if Wf.length > 1e-4 else -(pole - D1 * pole.dot(D1)).normalized()
                ik1 = cols(D1.cross(Wf), D1, Wf)
                ik2 = cols(D1.cross(Wf), D2, D1.cross(Wf).cross(D2))
                f1 = fk1.to_quaternion().slerp(ik1.to_quaternion(), ikw).to_matrix()
                f2 = fk2.to_quaternion().slerp(ik2.to_quaternion(), ikw).to_matrix()
            put(up, base.to_3x3().inverted() @ f1)
            put(fo, (W[up] @ self.rel[fo]).to_3x3().inverted() @ f2)
            hb = (W[fo] @ self.rel[ha]).to_3x3()
            hx, hy, hz = P["hand" + x]
            fk_h = Matrix.Rotation(rad(hx), 3, "X") @ Matrix.Rotation(rad(side * hy), 3, "Y") @ \
                Matrix.Rotation(rad(side * hz), 3, "Z")
            grip = P.get("grip" + x)
            gw = P.get("gripw" + x, 0.0)
            if grip is not None and gw > 1e-4:
                G = Vector(grip).normalized()
                if P.get("iksp", 0.0) > 0.5:
                    G = Qc @ G
                Y2 = f2.col[1]
                yh = (Y2 - G * Y2.dot(G)).normalized()
                gm = hb.inverted() @ cols(yh.cross(G), yh, G)
                fk_h = fk_h.to_quaternion().slerp(gm.to_quaternion(), gw).to_matrix()
            put(ha, fk_h)

        # --- legs (IK: ankle target in world, knee pole forward, foot orientation in world)
        for side in (1, -1):
            x = sfx(side)
            th, sh, ft = "thigh_" + x, "shin_" + x, "foot_" + x
            base = W["hips"] @ self.rel[th]
            J = base.translation
            dx, dy, dz, toe, yaw = P["leg" + x]
            A0 = self.rest[ft].translation
            tgt = A0 + Vector((dx, dy, dz)) * S
            fwd = Matrix.Rotation(rad(yaw), 3, "Z") @ FRONT
            pole = fwd + Vector((side * P.get("knee_out", 0.12), 0, 0.35))
            E, reached = two_bone(J, tgt, self.len[th], self.len[sh], pole, soft=0.975)
            if (reached - tgt).length > 0.004 * S:
                self.warn += 1
                self.log.append(("leg" + x, round((reached - tgt).length / S, 3)))
            D1 = (E - J).normalized()
            D2 = (reached - E).normalized()
            # knee hinge axis from the actual bend (a pole-based frame flips once the thigh rises
            # above horizontal, e.g. when kneeling); nearly straight legs fall back to the pole
            X1 = D2.cross(D1)
            pz = (pole - D1 * pole.dot(D1)).normalized()
            if X1.length < 0.05:
                X1 = D1.cross(pz)
            X1.normalize()
            Z1 = X1.cross(D1)
            put(th, base.to_3x3().inverted() @ cols(X1, D1, Z1))
            put(sh, (W[th] @ self.rel[sh]).to_3x3().inverted() @ cols(X1, D2, X1.cross(D2)))
            want = Matrix.Rotation(rad(yaw), 3, "Z") @ Matrix.Rotation(rad(toe), 3, "X") @ self.r3(ft)
            put(ft, (W[sh] @ self.rel[ft]).to_3x3().inverted() @ want)

        # --- face extras
        eL, eR = P["eyes"]
        for x, e in (("L", eL), ("R", eR)):
            put("extra_eye_" + x, Matrix.Identity(3), scale=Vector((1.0 + 0.08 * (1 - e), 1.0, max(0.05, e))))
            tilt, lift = P["brow"]
            sgn = 1 if x == "L" else -1
            put("extra_brow_" + x, Matrix.Rotation(rad(sgn * tilt), 3, "Y"), loc=Vector((0, 0, lift * S)))
        put("extra_mouth", Matrix.Identity(3), scale=Vector((1.0, 1.0, P["mouth"][0])))
        jw = P["jaw"][0]
        put("extra_jaw", Matrix.Identity(3), scale=Vector((1.0 + 0.1 * (jw - 1), 1.0, jw)))
        return out


# --------------------------------------------------------------------------- animation: clips
STYLE = dict(stride=1.0, bob=1.0, energy=1.0, stoop=0.0, chest=0.0, arm_out=0.0, idle_arms="hang",
             swagger=0.0, head_tilt=0.0, walk_arms=1.0)


def stand(st):
    """Neutral standing pose channels (one-shots start and end here)."""
    s = st["stoop"]
    return {
        "hips_off": (0.0, 0.0, -0.006), "hips": (0.0, 0.0, 0.0), "spine": (s * 0.4, 0.0, 0.0),
        "chest": (s * 0.6 + st["chest"], 0.0, 0.0), "neck": (-s * 0.3, 0.0, 0.0),
        "head": (-s * 0.5 - st["chest"] * 0.5, 0.0, st["head_tilt"]),
        "armL": (3.0, 9.0 + st["arm_out"], 6.0, 16.0), "armR": (3.0, 9.0 + st["arm_out"], 6.0, 16.0),
        "handL": (0.0, 0.0, 0.0), "handR": (0.0, 0.0, 0.0),
        "legL": (0.008, 0.0, 0.0, 0.0, 7.0), "legR": (-0.008, 0.0, 0.0, 0.0, -7.0),
        "eyes": (1.0, 1.0), "brow": (0.0, 0.0), "mouth": (1.0,), "jaw": (1.0,),
        "ikL": (0.0,), "ikR": (0.0,), "iktL": (0.1, -0.2, 0.3), "iktR": (-0.1, -0.2, 0.3),
        "gripL": (0.0, -1.0, 0.0), "gripR": (0.0, -1.0, 0.0), "gripwL": (0.0,), "gripwR": (0.0,),
        "iksp": (0.0,),
    }


def spec_from(get, f):
    """Build a solver pose spec from channel getter get(chan, frame)."""
    P = {}
    for k in ("hips_off", "hips", "spine", "chest", "neck", "head", "armL", "armR", "handL", "handR", "legL",
              "legR", "eyes", "brow", "mouth", "jaw"):
        P[k] = get(k, f)
    for x in ("L", "R"):
        P["ik" + x] = get("ik" + x, f)[0]
        P["ikt" + x] = get("ikt" + x, f)
        P["grip" + x] = get("grip" + x, f)
        P["gripw" + x] = get("gripw" + x, f)[0]
    P["iksp"] = get("iksp", f)[0]
    return P


def idle_arm_pose(st, side, rig):
    """(fk arm, ik weight, ik target) for the character's idle arm habit."""
    a = st["idle_arms"]
    base = (3.0, 9.0 + st["arm_out"], 6.0, 16.0)
    if a == "behind":
        return (-24.0, 14.0, -10.0, 70.0), 0.0, None
    if a in ("akimbo", "front") or (a == "clip" and side > 0):
        return base, 1.0, None
    return base, 0.0, None


def clip_idle(rig, st):
    N = 72
    c = rig.c
    d = c.d
    base = stand(st)
    blink = Curve([(0, 1), (44, 1), (46, 0.08), (47, 0.08), (50, 1), (72, 1)])
    look = Curve([(0, 0), (14, 0), (26, 7), (42, 7), (56, -3), (66, 0)], 72)
    tilt = Curve([(0, 0), (20, 0), (30, 3), (46, 3), (58, -1), (72, 0)], 72)

    def get(ch, f):
        ph = f / N
        br = math.sin(TAU * ph)                   # breathing, inhale peaks at 1/4
        sh = math.sin(TAU * ph + 0.6)             # weight shift towards the left leg
        shl = math.sin(TAU * (ph - 5 / N) + 0.6)  # torso follows a little later
        shl2 = math.sin(TAU * (ph - 9 / N) + 0.6)
        brl = math.sin(TAU * (ph - 6 / N))
        if ch == "hips_off":
            return (0.011 * sh, 0.0, -0.007 + 0.002 * math.sin(2 * TAU * ph))
        if ch == "hips":
            return (0.0, 1.2 * sh, -2.4 * sh)
        if ch == "spine":
            return (base["spine"][0] + 0.5 * br, -0.6 * shl, 1.4 * shl)
        if ch == "chest":
            return (base["chest"][0] - 1.6 * br, -0.4 * shl2, 0.9 * shl2)
        if ch == "neck":
            return (base["neck"][0] + 0.8 * brl, 0.4 * look(f - 3), 0.0)
        if ch == "head":
            return (base["head"][0] + 1.3 * brl, 0.8 * look(f), base["head"][2] + tilt(f) - 0.8 * shl2)
        if ch in ("armL", "armR"):
            side = 1 if ch == "armL" else -1
            fk, ikw, _ = idle_arm_pose(st, side, rig)
            lag = math.sin(TAU * (ph - 10 / N))
            return (fk[0] + 1.6 * lag, fk[1] + 1.4 * brl + 0.8 * side * shl, fk[2], fk[3] + 3.0 * lag)
        if ch in ("handL", "handR"):
            lag = math.sin(TAU * (ph - 14 / N))
            return (4.0 * lag, 0.0, 0.0)
        if ch in ("ikL", "ikR"):
            return (idle_arm_pose(st, 1 if ch == "ikL" else -1, rig)[1],)
        if ch in ("iktL", "iktR"):
            side = 1 if ch == "iktL" else -1
            # hands on hips (akimbo) / clasped in front of the belly / clipboard at the chest
            if st["idle_arms"] == "clip" and side > 0:
                return (0.07, -0.16, 0.44 + 0.004 * br)
            if st["idle_arms"] == "front":
                rub = 0.012 * st.get("rub", 0.0) * math.sin(2 * TAU * 4 * ph) * side
                return (side * 0.03 + rub, -0.15 * d["sh_x"] / DEF["sh_x"], d["hip_z"] + 0.07 + 0.003 * br)
            return (side * (d["sh_x"] + 0.05), -0.01, d["hip_z"] + 0.055 + 0.003 * br)
        if ch in ("gripL", "gripR"):
            return (0.0, 0.0, 1.0) if st["idle_arms"] == "clip" else (0.0, -1.0, 0.0)
        if ch == "gripwL":
            return (1.0 if st["idle_arms"] == "clip" else 0.0,)
        if ch == "eyes":
            b = blink(f)
            return (b, b)
        return base[ch]
    return N, True, get


def gait(rig, st, N, stance, amp, lift, bob, lean, arm, run=False):
    """Shared walk / run cycle. Left foot contacts at frame 0, right at N/2."""
    base = stand(st)
    A = amp * st["stride"]
    Y0 = (9.0 if run else 7.0) + st["swagger"]

    def foot(u):
        """(dy, dz, toe_down) of one foot at its own phase u."""
        if u < stance:
            v = u / stance
            y = -A + 2 * A * v
            if run:
                toe = lerp(4.0, 30.0, sstep((v - 0.45) / 0.55))
            else:
                toe = -14.0 * (1 - sstep(v / 0.22)) + 22.0 * sstep((v - 0.62) / 0.38)
            z = 0.0
        else:
            v = (u - stance) / (1 - stance)
            e = v * v * v * (v * (6 * v - 15) + 10)       # smootherstep
            y = A - 2 * A * e
            if run:   # kick the heel up behind, then reach forward
                y += 0.07 * math.sin(math.pi * v) * (1 - v) * 1.4
                toe = lerp(30.0, 4.0, sstep(v / 0.9))
                z = lift * math.sin(math.pi * v ** 0.75)
            else:
                toe = lerp(22.0, -14.0, sstep(v / 0.85))
                z = lift * math.sin(math.pi * v ** 0.8)
        # keep the toe (or heel) on the ground while the foot rolls
        piv = 0.085 if toe > 0 else 0.03
        z += piv * math.sin(rad(abs(toe)))
        return y, z, toe

    def get(ch, f):
        ph = f / N
        if ch in ("legL", "legR"):
            side = 1 if ch == "legL" else -1
            u = (ph + (0.0 if side > 0 else 0.5)) % 1.0
            y, z, toe = foot(u)
            return (side * 0.006, y, z, toe, side * 5.0)
        bounce = abs(math.sin(TAU * ph))                    # 0 at contacts, 1 at passing
        bl = abs(math.sin(TAU * (ph - 2 / N)))
        c1, s1 = cyc(ph)
        if ch == "hips_off":
            if run:
                zz = -0.05 - bob * math.cos(2 * TAU * (ph - stance / 2))
            else:
                zz = -0.02 + bob * (0.65 * bounce + 0.35 * bounce * bounce - 0.55)
            return (0.014 * st["energy"] * math.sin(TAU * (ph - 1 / N)), 0.0, zz)
        if ch == "hips":
            return (lean * 0.5 + 1.5 * math.cos(2 * TAU * ph), -Y0 * c1, -4.5 * st["energy"] * s1)
        if ch == "spine":
            c2, s2 = cyc(ph - 2 / N)
            return (base["spine"][0] + lean * 0.3, 0.35 * Y0 * c2, 2.4 * s2)
        if ch == "chest":
            c3, s3 = cyc(ph - 3 / N)
            return (base["chest"][0] + lean * 0.4 + 2.0 * (bl - 0.5), 0.95 * Y0 * c3, 1.0 * s3)
        if ch == "neck":
            c4, _ = cyc(ph - 3 / N)
            return (base["neck"][0] - lean * 0.3, -0.5 * Y0 * c4, 0.0)
        if ch == "head":
            c5, s5 = cyc(ph - 4 / N)
            nod = math.cos(2 * TAU * (ph - 4 / N))
            return (base["head"][0] - lean * 0.4 + 2.6 * nod, -0.35 * Y0 * c5, base["head"][2] + 1.6 * s5)
        if ch in ("armL", "armR"):
            side = 1 if ch == "armL" else -1
            fwd = -side * math.cos(TAU * (ph - 2 / N))     # left arm forward with the right leg
            ab = 10.0 + st["arm_out"] + (4.0 if run else 3.0) * bounce
            a = arm * st["walk_arms"]
            if run:
                return (8.0 + a * fwd, ab + 4, 12.0, 82.0 - 12.0 * fwd)
            return (4.0 + a * fwd, ab, 8.0, 22.0 + 14.0 * fwd)
        if ch in ("handL", "handR"):
            side = 1 if ch == "handL" else -1
            fwd = -side * math.cos(TAU * (ph - 5 / N))
            return (-10.0 * fwd, 0.0, 0.0)
        if ch == "eyes":
            return (1.0, 1.0)
        return base[ch]
    return get


def clip_walk(rig, st):
    N = 27
    return N, True, gait(rig, st, N, stance=0.56, amp=0.085, lift=0.052 * st["bob"], bob=0.025 * st["bob"],
                         lean=5.0, arm=28.0)


def clip_run(rig, st):
    N = 18
    return N, True, gait(rig, st, N, stance=0.38, amp=0.1, lift=0.075 * min(st["bob"], 1.1),
                         bob=0.018 * min(st["bob"], 1.15),
                         lean=14.0, arm=38.0, run=True)


def clip_talk(rig, st):
    N = 72
    base = stand(st)
    tr = Track({
        "armR": [(0, base["armR"]), (7, (36, 24, 30, 84)), (13, (40, 28, 34, 92)), (19, (32, 22, 30, 70)),
                 (25, (40, 28, 34, 88)), (33, (30, 48, 50, 64)), (40, (28, 44, 44, 60)), (50, (8, 14, 10, 26)),
                 (60, base["armR"])],
        "armL": [(0, base["armL"]), (26, base["armL"]), (34, (30, 26, 30, 76)), (41, (32, 44, 44, 66)),
                 (47, (28, 32, 36, 72)), (56, (8, 13, 10, 24)), (64, base["armL"])],
        "handR": [(0, (0, 0, 0)), (8, (-18, 20, 0)), (20, (-6, 20, 0)), (33, (-20, 30, 0)), (48, (0, 0, 0))],
        "handL": [(0, (0, 0, 0)), (30, (0, 0, 0)), (37, (-18, 24, 0)), (50, (-10, 20, 0)), (60, (0, 0, 0))],
        "head": [(0, base["head"]), (9, (base["head"][0] - 4, 5, base["head"][2] + 3)),
                 (16, (base["head"][0] + 5, 4, base["head"][2] + 1)),
                 (22, (base["head"][0] - 3, 3, base["head"][2] + 4)),
                 (29, (base["head"][0] + 4, -2, base["head"][2])),
                 (38, (base["head"][0] - 3, -6, base["head"][2] - 3)),
                 (46, (base["head"][0] + 4, -4, base["head"][2] - 1)),
                 (56, (base["head"][0] - 1, 1, base["head"][2] + 1)), (64, base["head"])],
        "chest": [(0, base["chest"]), (10, (base["chest"][0] + 2, -4, 0)), (24, (base["chest"][0] + 3, -3, 0)),
                  (38, (base["chest"][0] + 1, 4, 0)), (50, (base["chest"][0] + 2, 3, 0)), (62, base["chest"])],
        "hips": [(0, (0, 0, 0)), (20, (0, -2, 1.5)), (44, (0, 2, -1.5)), (66, (0, 0, 0))],
        "hips_off": [(0, base["hips_off"]), (20, (-0.006, 0, -0.007)), (44, (0.006, 0, -0.007)),
                     (66, base["hips_off"])],
        "brow": [(0, (0, 0)), (8, (0, 0.006)), (14, (0, 0.001)), (24, (0, 0.005)), (32, (0, 0.0)),
                 (40, (-6, 0.004)), (50, (0, 0.0))],
        "eyes": [(0, (1, 1)), (34, (1, 1)), (36, (0.08, 0.08)), (37, (0.08, 0.08)), (40, (1, 1))],
    }, period=N, defaults=base)
    # speech rhythm: syllables with a pause in the middle and at the end of the loop
    syl = [(2, 2.6), (6, 3.6), (10, 2.2), (14, 3.4), (18, 2.8), (22, 3.8), (26, 2.4), (39, 3.0), (43, 2.2),
           (47, 3.6), (51, 2.6), (55, 3.2), (59, 2.4)]
    jk = [(0, 1.0)]
    for (f, a) in syl:
        jk += [(f, a), (f + 2, 1.2)]
    jk += [(30, 1.0), (36, 1.0), (63, 1.0)]
    jaw = Curve(sorted(set(jk)), N)

    def get(ch, f):
        if ch == "jaw":
            return (jaw(f),)
        if ch == "neck":
            h = tr("head", f - 2)
            return (base["neck"][0] + 0.3 * (h[0] - base["head"][0]), 0.4 * h[1], 0.0)
        if ch == "spine":
            cst = tr("chest", f - 3)
            return (base["spine"][0] + 0.4 * (cst[0] - base["chest"][0]), 0.4 * cst[1], 0.0)
        if ch in ("legL", "legR"):
            return base[ch]
        return tr(ch, f)
    return N, True, get


def clip_sad(rig, st):
    N = 72
    base = stand(st)
    tr = Track({
        "chest": [(0, (12, 0, 0)), (16, (12, 0, 0)), (27, (6, 0, 0)), (40, (15, 0, 0)), (54, (12, 0, 0))],
        "hips_off": [(0, (0, 0.006, -0.016)), (27, (0, 0.006, -0.011)), (40, (0, 0.006, -0.019)),
                     (54, (0, 0.006, -0.016))],
        "armL": [(0, (9, 5, -4, 10)), (27, (7, 10, -4, 12)), (41, (11, 4, -4, 8)), (54, (9, 5, -4, 10))],
        "armR": [(0, (9, 5, -4, 10)), (28, (7, 10, -4, 12)), (42, (11, 4, -4, 8)), (55, (9, 5, -4, 10))],
        "head": [(0, (10, 4, -4)), (18, (10, 4, -4)), (29, (3, 0, -1)), (42, (13, -3, 2)), (56, (10, 4, -4))],
        "eyes": [(0, (0.6, 0.6)), (58, (0.6, 0.6)), (61, (0.06, 0.06)), (63, (0.06, 0.06)), (67, (0.6, 0.6))],
    }, period=N, defaults=base)

    def get(ch, f):
        if ch in ("chest", "hips_off", "armL", "armR", "head", "eyes"):
            v = tr(ch, f)
            if ch == "chest":
                return (v[0] + st["stoop"] * 0.6, v[1], v[2])
            return v
        if ch == "hips":
            return (-5.0, 0.0, 0.0)
        if ch == "spine":
            cst = tr("chest", f - 3)
            return (5.0 + 0.4 * (cst[0] - 12) + st["stoop"] * 0.4, 0.0, 0.0)
        if ch == "neck":
            h = tr("head", f - 3)
            return (4.0 + 0.3 * (h[0] - 10), 0.3 * h[1], 0.0)
        if ch in ("handL", "handR"):
            return (6.0, 0.0, 0.0)
        if ch == "brow":
            return (-13.0, 0.002)
        if ch == "mouth":
            return (0.3,)
        return base[ch]
    return N, True, get


def one_shot(N, base, tracks):
    """Keyed one-shot: every channel eases out of and back into the neutral stance `base`."""
    full = {}
    for ch, keys in tracks.items():
        keys = list(keys)
        if keys[0][0] > 0:
            keys.insert(0, (0, base[ch]))
        if keys[-1][0] < N:
            keys.append((N, base[ch]))
        full[ch] = keys
    return Track(full, None, base)


def clip_cheer(rig, st):
    """Anticipation crouch, hop with both arms flung up and out in a wide V, squash on landing,
    one extra fist pump, settle."""
    N = 36
    b = stand(st)
    hc, hh = b["chest"][0], b["head"][0]
    V = (28, 126, -12, 22)
    tr = one_shot(N, b, {
        "hips_off": [(0, b["hips_off"]), (5, (0, 0.006, -0.048)), (10, (0, 0, 0.066)), (13, (0, 0, 0.072)),
                     (17, (0, 0, -0.042)), (21, (0, 0, -0.004)), (25, (0, 0, -0.016)), (30, (0, 0, -0.003))],
        "hips": [(0, b["hips"]), (5, (6, 0, 0)), (10, (-3, 0, 0)), (17, (5, 0, 0)), (23, (0, 0, 0))],
        "chest": [(0, b["chest"]), (5, (hc + 5, 0, 0)), (10, (hc - 7, 0, 0)), (14, (hc - 6, 0, 0)),
                  (18, (hc + 4, 0, 0)), (24, (hc - 4, 0, 0)), (30, b["chest"])],
        "head": [(0, b["head"]), (5, (hh + 4, 0, 0)), (11, (hh - 9, 0, 0)), (16, (hh - 7, 0, 3)),
                 (20, (hh + 2, 0, -3)), (25, (hh - 6, 0, 2)), (31, b["head"])],
        "armL": [(0, b["armL"]), (5, (-26, 18, 6, 26)), (10, V), (14, (26, 130, -12, 18)), (18, (24, 116, -12, 36)),
                 (22, (40, 84, -20, 96)), (26, (26, 132, -12, 16)), (31, (12, 40, 4, 34))],
        "armR": [(0, b["armR"]), (5, (-26, 18, 6, 26)), (10, V), (14, (26, 130, -12, 18)), (18, (24, 116, -12, 36)),
                 (22, (40, 84, -20, 96)), (26, (26, 132, -12, 16)), (31, (12, 40, 4, 34))],
        "handL": [(0, b["handL"]), (10, (-12, 0, 0)), (18, (8, 0, 0)), (26, (-12, 0, 0)), (32, b["handL"])],
        "handR": [(0, b["handR"]), (10, (-12, 0, 0)), (18, (8, 0, 0)), (26, (-12, 0, 0)), (32, b["handR"])],
        "legL": [(0, b["legL"]), (6, b["legL"]), (10, (0.012, 0.012, 0.056, 30, 7)), (13, (0.014, 0.012, 0.062, 26, 7)),
                 (16, (0.01, 0.0, 0.004, 4, 7)), (17, b["legL"])],
        "legR": [(0, b["legR"]), (6, b["legR"]), (10, (-0.012, 0.012, 0.056, 30, -7)),
                 (13, (-0.014, 0.012, 0.062, 26, -7)), (16, (-0.01, 0.0, 0.004, 4, -7)), (17, b["legR"])],
        "eyes": [(0, (1, 1)), (6, (1, 1)), (9, (0.3, 0.3)), (28, (0.3, 0.3)), (32, (1, 1))],
        "jaw": [(0, (1,)), (6, (1,)), (10, (4.2,)), (18, (3.2,)), (22, (4.0,)), (28, (3.4,)), (32, (1,))],
        "brow": [(0, (0, 0)), (8, (4, 0.008)), (28, (4, 0.008)), (33, (0, 0))],
    })
    return N, False, tr


def clip_wave(rig, st):
    """Raise the right arm out to the side and wave the forearm three times, head tilted, smiling."""
    N = 36
    b = stand(st)
    out_, in_ = (24, 108, -82, 22), (24, 104, -82, 66)
    tr = one_shot(N, b, {
        "armR": [(0, b["armR"]), (7, (24, 106, -82, 44)), (10, out_), (13, in_), (16, out_), (19, in_), (22, out_),
                 (25, (24, 106, -82, 50)), (29, (14, 50, -20, 44))],
        "handR": [(0, b["handR"]), (7, (0, -70, 0)), (10, (0, -70, 14)), (13, (0, -70, -16)), (16, (0, -70, 14)),
                  (19, (0, -70, -16)), (22, (0, -70, 14)), (26, (0, -60, 0)), (31, b["handR"])],
        "armL": [(0, b["armL"]), (8, (6, 14, 6, 20)), (26, (6, 14, 6, 20))],
        "chest": [(0, b["chest"]), (8, (b["chest"][0] - 2, -6, 5)), (26, (b["chest"][0] - 2, -6, 5))],
        "spine": [(0, b["spine"]), (9, (b["spine"][0], -2, 3)), (27, (b["spine"][0], -2, 3))],
        "hips": [(0, b["hips"]), (8, (0, -3, -2)), (26, (0, -3, -2))],
        "hips_off": [(0, b["hips_off"]), (8, (0.006, 0, -0.008)), (26, (0.006, 0, -0.008))],
        "head": [(0, b["head"]), (9, (b["head"][0] - 4, -8, -7)), (18, (b["head"][0] - 3, -8, -9)),
                 (27, (b["head"][0] - 4, -8, -7))],
        "eyes": [(0, (1, 1)), (6, (0.7, 0.7)), (28, (0.7, 0.7))],
        "mouth": [(0, (1,)), (6, (1.35,)), (28, (1.35,))],
        "jaw": [(0, (1,)), (7, (2.2,)), (12, (1.8,)), (26, (2.0,)), (30, (1,))],
        "brow": [(0, (0, 0)), (6, (0, 0.006)), (28, (0, 0.006))],
    })
    return N, False, tr


def clip_harvest(rig, st):
    """Egrek (long pole sickle): grab the pole with both hands, thrust it up into the crown, yank down.
    Grips are given in the chest's rest frame, so the torso motion adds to the arms. The pole stays
    below ~58 deg so it clears the big hat brims; hand_R's local +Z runs up the pole."""
    N = 36
    b = stand(st)
    d = rig.c.d
    k = d["sh_z"] / DEF["sh_z"]
    kx = d["sh_x"] / DEF["sh_x"]

    def grips(x, y, z, el):
        e = rad(el)
        D = Vector((0.1, -math.cos(e), math.sin(e))).normalized()
        gR = Vector((x * kx, y * k, z * k))
        gL = gR + D * 0.11 * k
        return tuple(gR), tuple(gL), tuple(D)
    ready = (-0.035, -0.13, 0.4, 44)
    kf = {0: ready, 5: (-0.03, -0.125, 0.42, 49), 10: (-0.03, -0.12, 0.39, 47),
          15: (-0.03, -0.1, 0.52, 57), 19: (-0.03, -0.1, 0.53, 58), 23: (-0.02, -0.13, 0.385, 50),
          26: (-0.02, -0.135, 0.37, 47), 31: (-0.03, -0.128, 0.41, 46), 36: ready}
    ktR, ktL, kg = [], [], []
    for f, v in kf.items():
        gR, gL, D = grips(*v)
        ktR.append((f, gR))
        ktL.append((f, gL))
        kg.append((f, D))
    hc = b["chest"][0]
    tr = one_shot(N, b, {
        "iksp": [(0, (1,)), (36, (1,))],
        "ikR": [(0, (1,)), (36, (1,))], "ikL": [(0, (1,)), (36, (1,))],
        "gripwR": [(0, (1,)), (36, (1,))], "gripwL": [(0, (1,)), (36, (1,))],
        "iktR": ktR, "iktL": ktL, "gripR": kg, "gripL": kg,
        "hips_off": [(0, b["hips_off"]), (6, (0, 0.008, -0.012)), (10, (0, 0.01, -0.032)), (15, (0, 0.0, 0.012)),
                     (19, (0, 0.0, 0.013)), (23, (0, 0.014, -0.042)), (26, (0, 0.016, -0.046)),
                     (31, (0, 0.008, -0.014))],
        "hips": [(0, b["hips"]), (6, (0, -6, 0)), (10, (4, -6, 0)), (15, (-3, -4, 0)), (23, (7, -7, 0)),
                 (26, (8, -7, 0)), (31, (1, -4, 0))],
        "spine": [(0, b["spine"]), (7, (0, -4, 0)), (11, (2, -4, 0)), (16, (-3, -3, 0)), (24, (4, -5, 0)),
                  (27, (5, -5, 0)), (32, (1, -2, 0))],
        "chest": [(0, b["chest"]), (7, (hc - 2, -4, 0)), (11, (hc + 3, -5, 0)), (16, (hc - 6, -3, 0)),
                  (20, (hc - 6, -3, 0)), (24, (hc + 8, -6, 0)), (27, (hc + 9, -6, 0)), (32, (hc, -3, 0))],
        "neck": [(0, b["neck"]), (8, (-4, 0, 0)), (17, (-6, 0, 0)), (25, (0, 0, 0)), (32, (-2, 0, 0))],
        "head": [(0, b["head"]), (8, (-8, 4, 0)), (12, (-6, 4, 0)), (17, (-12, 5, 2)), (21, (-12, 5, 2)),
                 (25, (-2, 4, 0)), (28, (0, 4, 0)), (33, (-4, 2, 0))],
        "legL": [(0, b["legL"]), (7, (0.02, -0.04, 0.0, 0, 10)), (15, (0.02, -0.04, 0.012, 12, 10)),
                 (20, (0.02, -0.04, 0.012, 12, 10)), (23, (0.02, -0.04, 0.0, 0, 10)), (30, (0.02, -0.04, 0.0, 0, 10))],
        "legR": [(0, b["legR"]), (7, (-0.02, 0.04, 0.0, 0, -10)), (15, (-0.02, 0.04, 0.014, 14, -10)),
                 (20, (-0.02, 0.04, 0.014, 14, -10)), (23, (-0.02, 0.04, 0.0, 0, -10)),
                 (30, (-0.02, 0.04, 0.0, 0, -10))],
        "jaw": [(0, (1,)), (21, (1,)), (23, (2.4,)), (27, (1.6,)), (31, (1,))],
        "eyes": [(0, (1, 1)), (21, (1, 1)), (23, (0.45, 0.45)), (27, (0.6, 0.6)), (31, (1, 1))],
        "brow": [(0, (0, 0)), (10, (0, 0.004)), (21, (0, 0.004)), (23, (8, -0.003)), (29, (0, 0))],
    })
    return N, False, tr


def clip_chop(rig, st):
    """Parang (machete) slash with the right hand: cock it up at the right shoulder, then a fast
    diagonal sweep across the front to the lower left, follow through, recover.
    The blade runs along hand_R's local +Z (the thumb side of the fist)."""
    N = 24
    b = stand(st)
    hc, hh = b["chest"][0], b["head"][0]
    tr = one_shot(N, b, {
        "armR": [(0, b["armR"]), (6, (36, 80, -20, 96)), (9, (40, 84, -22, 102)), (12, (72, 6, 18, 22)),
                 (14, (64, -16, 24, 26)), (18, (30, 8, 10, 36))],
        "handR": [(0, b["handR"]), (6, (24, 0, 0)), (9, (30, 0, 0)), (12, (-42, 0, 0)), (14, (-52, 0, 0)),
                  (19, (-10, 0, 0))],
        "armL": [(0, b["armL"]), (6, (12, 30, 6, 42)), (9, (14, 32, 6, 44)), (12, (-6, 26, 6, 30)),
                 (15, (-4, 24, 6, 28)), (20, (4, 14, 6, 22))],
        "hips_off": [(0, b["hips_off"]), (6, (-0.01, 0.006, -0.012)), (9, (-0.011, 0.007, -0.014)),
                     (12, (0.01, -0.008, -0.032)), (14, (0.011, -0.009, -0.034)), (19, (0.003, -0.002, -0.012))],
        "hips": [(0, b["hips"]), (6, (-1, -9, 1)), (9, (-1, -10, 1)), (12, (4, 9, -1)), (14, (5, 11, -1)),
                 (19, (1, 3, 0))],
        "spine": [(0, b["spine"]), (7, (b["spine"][0], -6, 0)), (10, (b["spine"][0], -7, 0)),
                  (13, (b["spine"][0] + 2, 7, 0)), (15, (b["spine"][0] + 3, 8, 0)), (20, (b["spine"][0], 2, 0))],
        "chest": [(0, b["chest"]), (7, (hc - 3, -16, 3)), (10, (hc - 3, -17, 3)), (13, (hc + 6, 16, -3)),
                  (15, (hc + 7, 20, -3)), (20, (hc + 1, 4, 0))],
        "head": [(0, b["head"]), (8, (hh + 3, 9, 0)), (10, (hh + 3, 9, 0)), (14, (hh + 3, -6, 0)),
                 (17, (hh + 3, -8, 0)), (21, (hh + 1, -2, 0))],
        "legL": [(0, b["legL"]), (5, (0.012, -0.03, 0, 0, 12)), (19, (0.012, -0.03, 0, 0, 12))],
        "legR": [(0, b["legR"]), (5, (-0.014, 0.03, 0, 0, -12)), (19, (-0.014, 0.03, 0, 0, -12))],
        "jaw": [(0, (1,)), (9, (1,)), (12, (2.2,)), (16, (1.4,)), (20, (1,))],
        "eyes": [(0, (1, 1)), (8, (1, 1)), (11, (0.5, 0.5)), (16, (0.7, 0.7)), (20, (1, 1))],
        "brow": [(0, (0, 0)), (6, (6, -0.004)), (16, (6, -0.004)), (21, (0, 0))],
    })
    return N, False, tr


def clip_plant(rig, st):
    """Step, kneel on the right knee, dig twice with the right hand, set the seedling down with the
    left hand, pat the soil, stand back up (with a little stretch)."""
    N = 36
    b = stand(st)
    d = rig.c.d
    kz = d["hip_z"] / DEF["hip_z"]
    g = 0.12 * kz                     # fist height over the soil (chibi arms are short)
    drop = -0.158 * kz
    dig = (-0.055, -0.19, g)
    kneel_r = (-0.008, 0.115 * kz, 0.022 * kz, 52, -8)
    foot_l = (0.02, -0.075 * kz, 0.0, 0, 12)
    tr = one_shot(N, b, {
        "hips_off": [(0, b["hips_off"]), (4, (0.004, -0.01, -0.05)), (8, (0.0, -0.005, drop)),
                     (24, (0.0, -0.005, drop)), (28, (0.004, -0.012, drop * 0.55)), (32, (0, 0.0, 0.006)),
                     (35, (0, 0, -0.008))],
        "hips": [(0, b["hips"]), (4, (4, 3, 0)), (8, (12, 3, 0)), (24, (12, 3, 0)), (28, (8, 2, 0)),
                 (32, (-3, 0, 0))],
        "spine": [(0, b["spine"]), (9, (b["spine"][0] + 7, 0, 0)), (25, (b["spine"][0] + 7, 0, 0)),
                  (33, (b["spine"][0] - 2, 0, 0))],
        "chest": [(0, b["chest"]), (9, (b["chest"][0] + 12, -4, 0)), (13, (b["chest"][0] + 14, -7, 0)),
                  (19, (b["chest"][0] + 13, 5, 0)), (25, (b["chest"][0] + 11, 0, 0)), (33, (b["chest"][0] - 6, 0, 0))],
        "neck": [(0, b["neck"]), (10, (b["neck"][0] + 3, 0, 0)), (26, (b["neck"][0] + 3, 0, 0)), (33, b["neck"])],
        "head": [(0, b["head"]), (10, (b["head"][0] + 4, -6, 2)), (16, (b["head"][0] + 6, -9, 3)),
                 (22, (b["head"][0] + 6, 6, -2)), (27, (b["head"][0] + 2, 0, 0)), (32, (b["head"][0] - 8, 0, 0))],
        "legL": [(0, b["legL"]), (3, (0.02, -0.04 * kz, 0.03 * kz, 0, 12)), (6, foot_l), (26, foot_l),
                 (31, (0.012, -0.02, 0.0, 0, 9))],
        "legR": [(0, b["legR"]), (5, (-0.01, 0.05 * kz, 0.01, 20, -8)), (8, kneel_r), (24, kneel_r),
                 (28, (-0.01, 0.07 * kz, 0.015, 30, -8)), (31, (-0.01, 0.01, 0.0, 4, -7))],
        "ikR": [(0, (0,)), (8, (1,)), (19, (1,)), (26, (0.0,))],
        "iktR": [(0, (-0.08, -0.12, 0.25)), (7, (-0.06, -0.2, g + 0.05)), (9, dig),
                 (11, (-0.05, -0.14, g + 0.015)), (13, (-0.065, -0.21, g + 0.05)), (15, dig),
                 (17, (-0.05, -0.14, g + 0.015)), (20, (-0.08, -0.16, g + 0.08))],
        "ikL": [(0, (0,)), (8, (1,)), (26, (1,)), (30, (0,))],
        "iktL": [(0, (0.1, -0.1, 0.25)), (8, (0.075, -0.13, g + 0.1)), (16, (0.075, -0.13, g + 0.1)),
                 (19, (0.035, -0.17, g + 0.05)), (21, (0.01, -0.19, g + 0.004)), (23, (0.01, -0.19, g + 0.03)),
                 (24, (0.01, -0.19, g)), (26, (0.03, -0.17, g + 0.06))],
        "armR": [(0, b["armR"]), (7, (50, 16, 10, 40)), (19, (50, 16, 10, 40)), (26, (40, 14, 10, 40))],
        "armL": [(0, b["armL"]), (7, (40, 16, 10, 40)), (26, (40, 16, 10, 40))],
        "handR": [(0, b["handR"]), (9, (30, 0, 0)), (11, (-10, 0, 0)), (15, (30, 0, 0)), (17, (-10, 0, 0)),
                  (22, (0, 0, 0))],
        "handL": [(0, b["handL"]), (21, (20, 0, 0)), (24, (30, 0, 0)), (28, b["handL"])],
        "eyes": [(0, (1, 1)), (26, (1, 1)), (29, (0.4, 0.4)), (33, (0.8, 0.8))],
        "mouth": [(0, (1,)), (26, (1,)), (30, (1.3,))],
    })
    return N, False, tr


CLIPS = {"idle": clip_idle, "walk": clip_walk, "run": clip_run, "harvest": clip_harvest, "chop": clip_chop,
         "plant": clip_plant, "talk": clip_talk, "cheer": clip_cheer, "sad": clip_sad, "wave": clip_wave}
LOOPS = ("idle", "walk", "run", "talk", "sad")


def clip_spec(rig, st, name):
    N, loop, get = CLIPS[name](rig, st)
    return N, loop, (lambda f: spec_from(get, f))


def apply_pose(rig, basis):
    for pb in rig.ob.pose.bones:
        loc, q, sc = basis[pb.name]
        pb.location = loc
        pb.rotation_euler = q.to_euler("XYZ", pb.rotation_euler)
        pb.scale = sc


def bake_actions(rig, st, names=None):
    """Evaluate every clip at each frame and write it as Bezier keys into one action per clip."""
    ob = rig.ob
    if ob.animation_data is None:
        ob.animation_data_create()
    acts = {}
    for name in names or CLIPS:
        N, loop, spec = clip_spec(rig, st, name)
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        ob.animation_data.action = act
        rig.warn = 0
        frames = {}
        prev = {pb.name: None for pb in ob.pose.bones}
        for f in range(N + 1):
            basis = rig.solve(spec(f))
            row = {}
            for pb in ob.pose.bones:
                loc, q, sc = basis[pb.name]
                e = q.to_euler("XYZ", prev[pb.name]) if prev[pb.name] else q.to_euler("XYZ")
                prev[pb.name] = e
                row[pb.name] = (loc, e, sc)
            frames[f] = row
        # first frame: keyframe_insert creates the action slot + F-curves; the rest is bulk-filled
        for pb in ob.pose.bones:
            loc, e, sc = frames[0][pb.name]
            pb.location, pb.rotation_euler, pb.scale = loc, e, sc
            pb.keyframe_insert("rotation_euler", frame=0, group=pb.name)
            pb.keyframe_insert("location", frame=0, group=pb.name)
            if pb.name.startswith("extra_"):
                pb.keyframe_insert("scale", frame=0, group=pb.name)
        for fc in act.fcurves:
            bname = fc.data_path.split('"')[1]
            prop = fc.data_path.rsplit(".", 1)[1]
            k = {"location": 0, "rotation_euler": 1, "scale": 2}[prop]
            vals = [frames[f][bname][k][fc.array_index] for f in range(N + 1)]
            if loop:
                vals[N] = vals[0]
            fc.keyframe_points.clear()
            fc.keyframe_points.add(N + 1)
            co = []
            for f, v in enumerate(vals):
                co += [float(f), v]
            fc.keyframe_points.foreach_set("co", co)
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            if loop:
                fc.modifiers.new("CYCLES")
            fc.update()
        act.use_frame_range = True
        act.frame_start, act.frame_end = 0, N
        act.use_cyclic = loop
        if rig.warn:
            worst = {}
            for limb, v in rig.log:
                worst[limb] = max(worst.get(limb, 0.0), v)
            print(f"  [anim] {rig.c.name}/{name}: {rig.warn} IK targets out of reach, worst (m): {worst}")
        rig.log = []
        acts[name] = act
    ob.animation_data.action = acts.get("idle")
    return acts



# --------------------------------------------------------------------------- characters
def build_player():
    c = Char("player", style=dict(energy=1.0, bob=1.05))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="smug", mouth="smirk", brows="smug")
    hair(c, DK, front=70, side=96, back=116, part=8, tmin=48, rings=2)
    # straw safari hat, tipped back, thick rolled brim + batik band
    H = hat_xf(c, tilt=-13, roll=3, lift=0.004)
    crown = [(0.214, 0.066), (0.33, 0.047), (0.35, 0.052), (0.357, 0.066), (0.347, 0.078), (0.3, 0.078),
             (0.24, 0.086), (0.232, 0.15), (0.215, 0.215), (0.176, 0.262), (0.095, 0.29), (0.0, 0.296)]
    c.add("head", xf(lathe_vf(crown, 24, 1.0, 0.95), H), "M_Straw")
    c.add("head", xf(lathe_vf([(0.236, 0.084), (0.243, 0.098), (0.243, 0.12), (0.236, 0.132)], 24, 1.0, 0.95), H),
          "M_Batik")
    # sunglasses pushed up, resting on the hat band
    for s in (1, -1):
        c.add("head", xf(ellipsoid_vf((0.045, 0.013, 0.031), 10, 5),
                         H @ T(s * 0.054, -0.232, 0.116) @ R("Z", -s * 14) @ R("X", -14)), DK)
    c.add("head", xf(tube_vf([(-0.018, -0.242, 0.124), (0.0, -0.245, 0.129), (0.018, -0.242, 0.124)], 0.0055, 5), H),
          DK)
    # batik shirt (open collar) + khaki shorts
    neck(c, SK)
    surf = torso(c, "M_Batik")
    collar(c, "M_Batik", dip=0.035)
    pelvis(c, "M_Khaki")
    for row, z in enumerate((0.345, 0.415, 0.485)):
        n = 9
        for k in range(n):
            a = TAU * (k + 0.5 * (row % 2)) / n
            c.add("torso", decal_vf(surf, a, z, diamond(0.024, 0.032)), DK)
    for row, z in enumerate((0.38, 0.45)):
        for k in range(9):
            a = TAU * (k + 0.5 * ((row + 1) % 2)) / 9
            c.add("torso", decal_vf(surf, a, z, circle(0.011, 6)), "M_Straw")
    arms(c, SK, sleeve="short", sleeve_mat="M_Batik")
    legs(c, SK, pants="shorts", pants_mat="M_Khaki", foot="sandal", foot_mat=DK, strap_mat="M_Batik")
    return c


def build_kakek():
    c = Char("kakek", style=dict(stoop=9.0, stride=0.8, bob=0.7, energy=0.7, idle_arms="behind"),
             head_r=(0.226, 0.212, 0.204))
    SK, DK, PALE = "M_SkinTan", "M_Dark", "M_FadedShirt"
    face(c, SK, eyes="happy", mouth=None, brows="bushy", brow_mat=PALE)
    hair(c, PALE, front=80, side=97, back=116, seg=20, tmin=60, rings=2)
    moustache(c, PALE, thick=1.1, droop=5.0)
    # wide conical caping (woven bamboo) with a thick rim and two woven rings
    H = hat_xf(c, tilt=-10)
    cone = [(0.17, 0.146), (0.385, 0.04), (0.402, 0.041), (0.412, 0.052), (0.406, 0.066), (0.388, 0.07),
            (0.258, 0.14), (0.13, 0.22), (0.045, 0.278), (0.0, 0.295)]
    c.add("head", xf(lathe_vf(cone, 24), H), "M_Bamboo")
    c.add("head", xf(ellipsoid_vf((0.024, 0.024, 0.026), 8, 4), H @ T(0, 0, 0.294)), "M_Bamboo")
    for rr in (0.35, 0.21):
        z = 0.07 + (0.388 - rr) / 0.13 * 0.07 if rr > 0.258 else 0.14 + (0.258 - rr) / 0.128 * 0.08
        prof = [(rr + 0.014, z - 0.006), (rr + 0.001, z + 0.008), (rr - 0.013, z + 0.018)]
        c.add("head", xf(lathe_vf(prof, 24), H @ T(0, 0, 0.004)), "M_Sarong")
    # faded shirt over a checked sarong to mid-shin
    neck(c, SK)
    torso(c, PALE)
    collar(c, PALE, dip=0.02, thick=(0.014, 0.018))
    sar = [(0.0, 0.118), (0.13, 0.112), (0.162, 0.114), (0.168, 0.132), (0.162, 0.25), (0.152, 0.35), (0.0, 0.37)]
    c.add("skirt", lathe_vf(sar, 20, 1.0, 0.88), "M_Sarong")
    ssurf = lathe_surf(sar, 1.0, 0.88)
    for z in (0.16, 0.22, 0.28):
        prof = [(ssurf.r_at(z - 0.008) + 0.003, z - 0.008), (ssurf.r_at(z + 0.008) + 0.003, z + 0.008)]
        c.add("skirt", lathe_vf(prof, 20, 1.0, 0.88), PALE)
    for k in range(10):
        a = TAU * (k + 0.5) / 10
        c.add("skirt", strip_vf(ssurf, a, 0.12, 0.33, 0.012, 0.0035, 3), PALE)
    arms(c, SK, sleeve="short", sleeve_mat=PALE)
    legs(c, SK, dress=True, foot="sandal", foot_mat=DK, strap_mat="M_Sarong")
    return c


def build_ibu():
    c = Char("ibu", style=dict(stride=0.75, energy=0.85, idle_arms="front", head_tilt=2.0), sh_x=0.118,
             sh_z=0.545)
    SK = "M_Skin"
    face(c, SK, eyes="round", mouth="smile", brows="soft", ears=False, lash=True, hl="M_Floral")
    # hijab: a hood framing the face, and a short drape over the shoulders
    radii = (c.hr[0] + 0.022, c.hr[1] + 0.026, c.hr[2] + 0.026)
    c.add("head", xf(hood_vf(radii, 52, 30, 46, 24, 7, 0.9), T(c.hc + Vector((0, 0.012, -0.008)))), "M_Hijab")
    cape = [(0.0, 0.47), (0.15, 0.472), (0.178, 0.48), (0.183, 0.494), (0.176, 0.52), (0.16, 0.56),
            (0.128, 0.6), (0.085, 0.64), (0.0, 0.66)]
    c.add("cape", lathe_vf(cape, 22, 1.0, 0.86), "M_Hijab")
    # long floral dress, bell shaped
    dress = [(0.0, 0.07), (0.19, 0.066), (0.228, 0.074), (0.234, 0.094), (0.215, 0.18), (0.182, 0.27),
             (0.158, 0.35), (0.148, 0.42), (0.132, 0.5), (0.0, 0.53)]
    c.add("skirt", lathe_vf(dress, 22, 1.0, 0.88), "M_Dress")
    dsurf = lathe_surf(dress, 1.0, 0.88)
    hem_ring(c, dsurf, 0.085, "M_Floral", sx=1.0, sy=0.88, out=0.006, w=0.009, rule="skirt")
    rows = ((0.135, 9, 0.026), (0.215, 8, 0.024), (0.3, 7, 0.022))
    for ri, (z, n, r) in enumerate(rows):
        for k in range(n):
            a = TAU * (k + 0.5 * (ri % 2)) / n
            c.add("skirt", decal_vf(dsurf, a, z, flower(r, 5, 12, rot=0.4 * k)), "M_Floral")
    arms(c, SK, sleeve="long", sleeve_mat="M_Dress", cuff_mat="M_Floral")
    legs(c, SK, dress=True, foot="sandal", foot_mat="M_Hijab")
    return c


def build_kades():
    c = Char("kades", style=dict(chest=-5.0, idle_arms="behind", swagger=2.0, energy=0.85))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="round", mouth="smile", brows="normal")
    hair(c, DK, front=74, side=94, back=114, lift=0.012, seg=20, tmin=40, rings=2)
    moustache(c, DK, thick=1.2, droop=3.0, width=14)
    # black peci (velvet cap)
    H = hat_xf(c, tilt=-4)
    peci = [(0.21, 0.078), (0.216, 0.088), (0.214, 0.18), (0.2, 0.205), (0.11, 0.216), (0.0, 0.218)]
    c.add("head", xf(lathe_vf(peci, 24, 1.0, 0.93), H), DK)

    # crisp white shirt with a round belly, tucked into dark trousers
    def belly(p, a, z):
        g = math.exp(-((z - 0.39) / 0.085) ** 2)
        front = max(0.0, math.cos(a)) ** 1.5
        p.y -= 0.045 * g * front
        p.x *= 1.0 + 0.1 * g
        return p
    neck(c, SK)
    surf = torso(c, "M_White", TUCKED, sx=1.04, deform=belly, hem=False)
    collar_flaps(c, "M_White", z=0.6)
    collar(c, "M_White", dip=0.015, thick=(0.012, 0.016))
    pelvis(c, "M_Trousers", [(0.0, 0.262), (0.07, 0.265), (0.118, 0.28), (0.142, 0.305), (0.15, 0.345),
                             (0.0, 0.36)], sx=1.04)
    prof = [(0.148, 0.328), (0.155, 0.343), (0.148, 0.358)]
    c.add("torso", lathe_vf(prof, 20, 1.04, BODY_SY, deform=belly), DK)
    c.add("torso_rigid", xf(rbox_vf(0.022, 0.007, 0.015), T(surf(0.0, 0.343) + Vector((0, -0.01, 0)))), "M_Gold")
    for z in (0.4, 0.45, 0.5):
        c.add("torso", decal_vf(surf, 0.0, z, circle(0.008, 6), thick=0.002), "M_Gold")
    c.add("torso", decal_vf(surf, rad(36), 0.475, rect(0.022, 0.03), thick=0.002), "M_Gold")
    arms(c, SK, sleeve="long", sleeve_mat="M_White")
    legs(c, SK, pants="long", pants_mat="M_Trousers", foot="shoe", foot_mat=DK)
    return c


def build_nenek():
    c = Char("nenek", style=dict(stoop=15.0, stride=0.7, bob=0.6, energy=0.6, idle_arms="front", head_tilt=-2.0))
    SK, DK, GR = "M_Skin", "M_Dark", "M_HairGrey"
    face(c, SK, eyes="happy", mouth="smile", brows="soft", brow_mat=GR)
    hair(c, GR, front=62, side=92, back=116, lift=0.018)
    # bun + hair stick
    c.add("head", xf(ellipsoid_vf((0.088, 0.08, 0.075), 12, 7), T(c.hc + Vector((0, 0.165, 0.15)))), GR)
    c.add("head", tube_vf([c.hc + Vector((-0.09, 0.155, 0.215)), c.hc + Vector((0.09, 0.19, 0.13))], 0.0065, 5,
                          round_caps=1), "M_Kain")
    # round glasses
    for s in (1, -1):
        p, n = c.hp(s * 25, -6, 0.014)
        loop = [orient(p, n) @ Vector((0.04 * math.cos(t), 0, 0.037 * math.sin(t))) for t in
                [TAU * i / 12 for i in range(12)]]
        c.add("head", tube_vf(loop, 0.0048, 4, closed=True, up=-n), DK)
        tp = c.head_path([(s * 37, -5), (s * 62, -3), (s * 86, -4)], 0.008)
        c.add("head", tube_vf(tp, 0.004, 4), DK)
    c.add("head", tube_vf(c.head_path([(-14, -4), (0, -2.5), (14, -4)], 0.017), 0.0045, 4), DK)
    # kebaya top (light, with a peplum) and batik kain to the ankles
    neck(c, SK)
    keb = [(0.0, 0.3), (0.136, 0.296), (0.166, 0.305), (0.164, 0.33), (0.153, 0.39), (0.148, 0.45), (0.141, 0.5),
           (0.128, 0.545), (0.101, 0.58), (0.062, 0.603), (0.0, 0.61)]
    surf = torso(c, "M_Kebaya", keb)
    collar(c, "M_Kebaya", dip=0.05, thick=(0.012, 0.016))
    for z in (0.39, 0.44, 0.49):
        c.add("torso", decal_vf(surf, 0.0, z, circle(0.009, 6), thick=0.002), GR)
    kain = [(0.0, 0.07), (0.125, 0.064), (0.152, 0.068), (0.157, 0.09), (0.153, 0.25), (0.148, 0.34), (0.0, 0.345)]
    c.add("skirt", lathe_vf(kain, 20, 1.0, 0.88), "M_Kain")
    ksurf = lathe_surf(kain, 1.0, 0.88)
    for ri, z in enumerate((0.11, 0.17, 0.23, 0.29)):
        for k in range(9):
            a = TAU * (k + 0.5 * (ri % 2)) / 9
            c.add("skirt", decal_vf(ksurf, a, z, diamond(0.024, 0.03), 0.0035), "M_Kebaya")
    c.add("skirt", strip_vf(ksurf, rad(-18), 0.07, 0.3, 0.01, 0.0045, 3), "M_Kebaya")
    arms(c, SK, sleeve="long", sleeve_mat="M_Kebaya")
    legs(c, SK, dress=True, foot="sandal", foot_mat=DK, strap_mat="M_Kain")
    return c


def build_pemuda():
    c = Char("pemuda", style=dict(energy=1.2, bob=1.2, swagger=3.0, stride=1.05))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="round", mouth="grin", brows="normal")
    messy_hair(c, DK)
    cowlick(c, DK, [(-8, 64, (0.1, 0.6, 0.3), 0.065), (14, 60, (-0.3, 0.8, 0.1), 0.058),
                    (178, 58, (0.2, 0.9, -0.2), 0.052)])
    # bright green tee + jeans shorts + checked sarong slung over the left shoulder
    neck(c, SK)
    torso(c, "M_GreenTee")
    collar(c, "M_GreenTee", dip=0.0, vneck=False, thick=(0.012, 0.014), rx=0.07, ry=0.062)
    pelvis(c, "M_Jeans")
    L_ = Vector((0.11, 0.0, 0.59))
    Rp = Vector((-0.16, 0.0, 0.32))
    C = (L_ + Rp) / 2
    u = (L_ - Rp).normalized()
    v = Vector((0.0, 1.0, 0.0))
    A = (L_ - Rp).length / 2 + 0.012
    B = 0.155
    nrm = u.cross(v)
    N = 24
    pts = [C + u * (A * math.cos(TAU * i / N)) + v * (B * math.sin(TAU * i / N)) for i in range(N)]
    for i in range(N):
        mname = DK if i % 4 == 0 else "M_SarongRed"
        c.add("torso_rigid", tube_vf([pts[i], pts[(i + 1) % N]], (0.02, 0.044), 5, up=nrm, caps=False), mname)
    c.add("torso_rigid", xf(ellipsoid_vf((0.048, 0.04, 0.044), 8, 5), T(Rp + Vector((-0.01, -0.02, 0.0)))),
          "M_SarongRed")
    c.add("torso_rigid", xf(ellipsoid_vf((0.027, 0.02, 0.058), 6, 4), T(Rp + Vector((-0.018, -0.03, -0.062)))),
          "M_SarongRed")
    arms(c, SK, sleeve="short", sleeve_mat="M_GreenTee")
    legs(c, SK, pants="shorts", pants_mat="M_Jeans", foot="sandal", foot_mat=DK)
    return c


def build_petani():
    c = Char("petani", style=dict(energy=0.95))
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="round", mouth="smile", brows="normal")
    hair(c, DK, front=78, side=97, back=116, seg=20, tmin=58, rings=2)
    # olive bucket hat with a thick rolled brim
    H = hat_xf(c, tilt=-9)
    bucket = [(0.212, 0.074), (0.3, 0.024), (0.318, 0.022), (0.326, 0.034), (0.318, 0.048), (0.3, 0.052),
              (0.226, 0.088), (0.216, 0.148), (0.196, 0.214), (0.14, 0.246), (0.0, 0.255)]
    c.add("head", xf(lathe_vf(bucket, 24, 1.0, 0.94), H), "M_Olive")
    c.add("head", xf(lathe_vf([(0.223, 0.086), (0.23, 0.1), (0.228, 0.116), (0.22, 0.128)], 24, 1.0, 0.94), H), DK)
    # blue work shirt, rolled sleeves; white towel round the neck
    neck(c, SK)
    surf = torso(c, "M_WorkBlue")
    collar_flaps(c, "M_WorkBlue", z=0.6)
    pelvis(c, "M_Olive")
    loop = []
    for i in range(18):
        t = TAU * i / 18
        dip = 0.02 * max(0.0, math.cos(t))
        loop.append(Vector((0.108 * math.sin(t), -0.098 * math.cos(t), 0.594 - dip)))
    c.add("torso", tube_vf(loop, (0.029, 0.025), 6, closed=True), "M_White")
    for s in (1, -1):
        path = surf_path(surf, [(rad(s * 22), 0.574), (rad(s * 20), 0.52), (rad(s * 19), 0.45)], 0.014)
        c.add("torso", tube_vf(path, [(0.032, 0.011), (0.034, 0.012), (0.036, 0.012)], 6, up=(0, -1, 0),
                               round_caps=1), "M_White")
    c.add("torso", decal_vf(surf, rad(-34), 0.47, rect(0.048, 0.05), thick=0.004), "M_WorkBlue")
    arms(c, SK, sleeve="rolled", sleeve_mat="M_WorkBlue")
    legs(c, SK, pants="rolled", pants_mat="M_Olive", foot="boot", foot_mat=DK)
    return c


def build_anak():
    c = Char("anak", scale=0.76, style=dict(energy=1.3, bob=1.35, stride=1.1),
             head_r=(0.248, 0.23, 0.224), head_c=0.855)
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="big", mouth="grin", brows="soft", eye_yaw=25, eye_el=-7)
    messy_hair(c, DK, front=76, side=97, back=116, teeth=18, amp=9.0, lump=0.0, lump2=0.0, lift=0.013, seg=32,
               rings=4)
    # baseball cap worn backwards: crown + flat bill sticking out at the back
    capr = (c.hr[0] + 0.024, c.hr[1] + 0.024, c.hr[2] + 0.02)
    Hc = T(c.hc + Vector((0, 0.006, 0.008)))

    def ctm(phi):
        return rad(blend3(phi, 66, 78, 88))
    c.add("head", xf(shell_vf(capr, ctm, 24, 5, 0.95), Hc), "M_CapBlue")
    c.add("head", xf(ellipsoid_vf((0.024, 0.024, 0.014), 6, 3), Hc @ T(0, 0, capr[2])), "M_TeeOrange")
    c.add("head", xf(bill_vf(0.155, 0.18, 0.011, 10, bend=0.6), Hc @ T(0, 0.19, 0.045) @ R("X", 8) @ R("Z", 180)),
          "M_CapBlue", smooth=False)
    cowlick(c, DK, [(0, 24, (0, -0.9, 0.2), 0.055)], lift=0.028)
    cs = ell_surf(Vector((0, 0, 0)), capr)
    c.add("head", tube_vf([Hc @ cs(rad(a_), rad(20 + 0.014 * a_ * a_)) for a_ in (-28, -14, 0, 14, 28)],
                          0.007, 4), "M_CapBlue")
    # orange tee with a star, blue shorts
    neck(c, SK)
    surf = torso(c, "M_TeeOrange")
    collar(c, "M_TeeOrange", dip=0.0, vneck=False, thick=(0.012, 0.014), rx=0.07, ry=0.062)
    pelvis(c, "M_Jeans")
    c.add("torso", decal_vf(surf, 0.0, 0.44, star(0.042, 5, 0.45), thick=0.002), "M_CapBlue")
    arms(c, SK, sleeve="short", sleeve_mat="M_TeeOrange")
    legs(c, SK, pants="shorts", pants_mat="M_Jeans", foot="sandal", foot_mat="M_CapBlue", strap_mat=DK)
    return c


PREMAN_TORSO = [(0.0, 0.36), (0.16, 0.36), (0.19, 0.38), (0.2, 0.45), (0.212, 0.55), (0.218, 0.63), (0.207, 0.69),
                (0.18, 0.735), (0.13, 0.77), (0.078, 0.79), (0.0, 0.8)]


def build_preman():
    c = Char("preman", style=dict(arm_out=10.0, swagger=5.0, chest=-4.0, idle_arms="akimbo", energy=0.9,
                                  stride=1.1, bob=0.9),
             hip_z=0.4, leg_x=0.092, knee_z=0.245, ankle_z=0.085, toe_y=-0.1, thigh_r=0.062, knee_r=0.054,
             shin_r=0.052, ankle_r=0.042, pelvis_z=0.415, spine_z=0.5, chest_z=0.585, neck_z=0.76, head_z=0.81,
             sh_x=0.2, sh_z=0.71, arm_a=30.0, l_up=0.135, l_fore=0.12, l_hand=0.09, up_r=0.05, elbow_r=0.044,
             fore_r=0.045, wrist_r=0.036, hand_k=1.35, head_c=1.012, head_r=(0.222, 0.208, 0.2))
    SK, DK, INK = "M_SkinTan", "M_Dark", "M_Ink"
    face(c, SK, eyes="narrow", mouth="frown", brows="angry", hl=None)
    hair(c, DK, front=60, side=88, back=112, lift=0.006, rim=None, seg=22, rings=4)
    p0, n0 = c.hp(9, -21.2, 0.0)   # toothpick
    c.add("head", tube_vf([p0 - n0 * 0.01, p0 + Vector((0.055, -0.03, -0.018))], [0.0045, 0.0035], 4), "M_Gold")
    # black tank top over a big chest, skin shoulders
    sy = 0.78
    neck(c, SK, r=0.062)
    tank = [p for p in PREMAN_TORSO if p[1] <= 0.69] + [(0.19, 0.698), (0.0, 0.7)]
    tank = [(r + (0.004 if z > 0.6 else 0.0), z) for (r, z) in tank]
    c.add("torso", lathe_vf(tank, 20, 1.05, sy), DK)
    skin_top = [(0.0, 0.6), (0.212, 0.61)] + [p for p in PREMAN_TORSO if p[1] > 0.61]
    c.add("torso", lathe_vf(skin_top, 20, 1.05, sy), SK)
    surf = lathe_surf(PREMAN_TORSO, 1.05, sy)
    for s in (1, -1):  # straps
        path = surf_path(surf, [(rad(s * 28), 0.67), (rad(s * 40), 0.74), (rad(s * 90), 0.765),
                                (rad(s * 140), 0.74), (rad(s * 152), 0.67)], 0.004)
        c.add("torso", tube_vf(path, (0.03, 0.007), 4, up=(0, 0, 1)), DK)
    # gold chain resting on the chest
    N = 22
    chain = [(TAU * i / N, 0.777 - 0.065 * (0.5 + 0.5 * math.cos(TAU * i / N)) ** 1.5) for i in range(N)]
    cp = surf_path(surf, chain, 0.012)
    c.add("torso_rigid", tube_vf(cp, [0.011 if i % 2 else 0.007 for i in range(N)], 4, closed=True), "M_Gold")
    c.add("torso_rigid", xf(ellipsoid_vf((0.022, 0.01, 0.026), 6, 4), T(surf(0.0, 0.68) + Vector((0, -0.02, 0)))),
          "M_Gold")
    pelvis(c, "M_Army", [(0.0, 0.3), (0.1, 0.305), (0.16, 0.33), (0.18, 0.37), (0.184, 0.42), (0.0, 0.43)],
           sx=1.05, sy=sy)
    c.add("torso", lathe_vf([(0.19, 0.38), (0.198, 0.397), (0.19, 0.412)], 20, 1.05, sy), DK)
    arms(c, SK, sleeve=None)
    # tattoos: a band + patches on each upper arm
    d = c.d
    for side in (1, -1):
        S_, v, E, W = c.arm_pts(side)
        Mw = frame_y(S_, v, FRONT) @ R("X", -90)     # local +Z along the arm (towards the hand)
        asurf = lathe_surf([(d["up_r"] * 0.98, -0.02), (d["up_r"], 0.1)], 1.0, 1.0)
        z = 0.06
        prof = [(d["up_r"] + 0.003, z - 0.012), (d["up_r"] + 0.003, z + 0.012)]
        c.add(("arm", side), xf(lathe_vf(prof, 10), Mw), INK)
        for (aa, zz, shp) in ((rad(-90), 0.095, star(0.03, 6, 0.5)), (rad(-30), 0.02, ellipse(0.018, 0.024, 8)),
                              (rad(-150), 0.1, diamond(0.03, 0.04))):
            c.add(("arm", side), xf(decal_vf(asurf, aa, zz, shp, 0.004), Mw), INK)
    legs(c, SK, pants="long", pants_mat="M_Army", foot="boot", foot_mat=DK)
    return c


def build_calo():
    c = Char("calo", style=dict(swagger=4.0, idle_arms="front", head_tilt=4.0, energy=1.0, rub=1.0))
    SK, DK, TW = "M_Skin", "M_Dark", "M_Tweed"
    face(c, SK, eyes=None, mouth="smirk", brows=None)
    hair(c, DK, front=80, side=96, back=114, lift=0.014, seg=20, tmin=60, rings=2)
    sunglasses_on_face(c, DK)
    for s in (1, -1):   # pencil moustache
        pts = [(s * 2.5, -15.8), (s * 7, -16.2), (s * 11.5, -15.2), (s * 14, -13.2)]
        c.add("head", tube_vf(c.head_path(pts, 0.004), [0.004, 0.0055, 0.0045, 0.003], 4), DK)
    # flat cap
    H = hat_xf(c, tilt=4)
    c.add("head", xf(ellipsoid_vf((0.25, 0.26, 0.1), 22, 7), H @ T(0, -0.01, 0.148)), TW)
    c.add("head", xf(ellipsoid_vf((0.16, 0.09, 0.02), 12, 4), H @ T(0, -0.215, 0.12) @ R("X", 14)), TW)
    c.add("head", xf(ellipsoid_vf((0.02, 0.02, 0.011), 6, 3), H @ T(0, -0.018, 0.246)), TW)
    # loud Hawaiian shirt, bum bag
    neck(c, SK)
    surf = torso(c, "M_Hawaii")
    collar_flaps(c, "M_Hawaii", z=0.6, spread=0.06)
    pelvis(c, TW)
    placed = [(0, 0.36), (1, 0.45), (2, 0.37), (3, 0.49), (4, 0.35), (5, 0.44), (6, 0.38), (7, 0.48), (8, 0.41)]
    for i, (k, z) in enumerate(placed):
        a = TAU * (k + 0.15) / 9
        c.add("torso", decal_vf(surf, a, z, flower(0.033 if i % 2 else 0.028, 5, 12, rot=i * 0.7)), "M_HawaiiBloom")
    strap = surf_path(lathe_surf(TORSO), [(TAU * i / 18, 0.345 + 0.035 * math.cos(TAU * i / 18 + 0.9)) for i in
                                          range(18)], 0.007)
    c.add("torso_rigid", tube_vf(strap, (0.009, 0.014), 4, closed=True), DK)
    bb = surf(rad(-10), 0.335) + Vector((0, -0.04, 0))
    c.add("torso_rigid", xf(ellipsoid_vf((0.085, 0.043, 0.052), 12, 6), T(bb) @ R("Y", 12)), DK)
    c.add("torso_rigid", xf(tube_vf([(-0.066, -0.043, 0.012), (0.0, -0.048, 0.014), (0.066, -0.043, 0.012)],
                                    0.004, 4), T(bb) @ R("Y", 12)), "M_HawaiiBloom")
    arms(c, SK, sleeve="short", sleeve_mat="M_Hawaii")
    legs(c, SK, pants="long", pants_mat=TW, foot="shoe", foot_mat=DK)
    return c


def build_petugas():
    c = Char("petugas", style=dict(chest=-3.0, idle_arms="clip", energy=0.8))
    SK, DK, UN = "M_Skin", "M_Dark", "M_Uniform"
    face(c, SK, eyes="round", mouth="flat", brows="angry")
    hair(c, DK, front=80, side=95, back=114, lift=0.012, seg=20, tmin=58, rings=2)
    # peaked uniform cap with a dark band, visor and a gold badge
    H = hat_xf(c, tilt=-3)
    cap = [(0.205, 0.086), (0.212, 0.146), (0.245, 0.194), (0.254, 0.2), (0.255, 0.212), (0.236, 0.222),
           (0.0, 0.228)]
    c.add("head", xf(lathe_vf(cap, 22, 1.0, 0.95), H), UN)
    c.add("head", xf(lathe_vf([(0.209, 0.088), (0.22, 0.112), (0.215, 0.136)], 22, 1.0, 0.95), H), DK)
    c.add("head", xf(ellipsoid_vf((0.14, 0.09, 0.017), 12, 4), H @ T(0, -0.205, 0.096) @ R("X", 18)), DK)
    c.add("head", xf(ellipsoid_vf((0.025, 0.012, 0.027), 6, 4), H @ T(0, -0.215, 0.165) @ R("X", -30)), "M_Gold")
    # uniform shirt tucked in, belt, badge, name tag, epaulettes
    neck(c, SK)
    surf = torso(c, UN, TUCKED, hem=False)
    collar_flaps(c, UN, z=0.6)
    pelvis(c, UN)
    c.add("torso", lathe_vf([(0.146, 0.327), (0.153, 0.343), (0.146, 0.359)], 20, 1.0, BODY_SY), DK)
    c.add("torso_rigid", xf(rbox_vf(0.022, 0.007, 0.015), T(surf(0.0, 0.343) + Vector((0, -0.009, 0)))), "M_Gold")
    c.add("torso", decal_vf(surf, rad(36), 0.47, star(0.03, 5, 0.45), thick=0.002), "M_Gold")
    c.add("torso", decal_vf(surf, rad(-36), 0.465, rect(0.052, 0.016), thick=0.002), "M_White")
    for z in (0.39, 0.43, 0.47, 0.51):
        c.add("torso", decal_vf(surf, 0.0, z, circle(0.007, 6), thick=0.002), "M_Gold")
    for s in (1, -1):
        c.add("torso", xf(ellipsoid_vf((0.048, 0.034, 0.011), 8, 3), T(s * 0.108, 0.0, 0.565) @ R("Y", -s * 40)), UN)
    arms(c, SK, sleeve="short", sleeve_mat=UN)
    legs(c, SK, pants="long", pants_mat=UN, foot="shoe", foot_mat=DK)
    # clipboard held in the LEFT hand (the right hand stays free for the game's tools)
    S_, v, E, W = c.arm_pts(1)
    Hf = frame_y(W, v, FRONT)
    Mc = Hf @ T(-0.026, 0.035, 0.07)
    c.add(("hand", 1), xf(box_vf(0.006, 0.075, 0.1), Mc), DK, smooth=False)
    c.add(("hand", 1), xf(box_vf(0.003, 0.065, 0.082), Mc @ T(-0.007, 0.0, -0.01)), "M_White", smooth=False)
    c.add(("hand", 1), xf(box_vf(0.01, 0.026, 0.012), Mc @ T(0.0, 0.0, 0.095)), "M_Gold", smooth=False)
    return c


def build_buruh():
    c = Char("buruh", style=dict(stoop=4.0, energy=0.8, stride=0.95))
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="round", mouth="flat", brows="worried")
    hair(c, DK, front=80, side=96, back=114, lift=0.012, seg=20, tmin=58, rings=2)
    # yellow hard hat with a short front peak and a ridge over the top
    H = hat_xf(c, tilt=-5)

    def peak(p, a, z):
        if z < 0.09:
            p.y -= 0.045 * max(0.0, math.cos(a)) ** 3
        return p
    hat = [(0.212, 0.078), (0.272, 0.064), (0.282, 0.07), (0.28, 0.084), (0.258, 0.09), (0.228, 0.094),
           (0.223, 0.146), (0.2, 0.206), (0.138, 0.255), (0.0, 0.274)]
    c.add("head", xf(lathe_vf(hat, 24, 1.0, 0.95, deform=peak), H), "M_HardHat")
    dome = lathe_surf(hat[6:], 1.0, 0.95)
    ridge = [(0.0, z) for z in (0.12, 0.172, 0.215, 0.25)] + [(math.pi, z) for z in (0.25, 0.215, 0.172, 0.12)]
    rp = surf_path(dome, ridge, 0.004)
    rp.insert(4, Vector((0, 0, 0.279)))
    c.add("head", xf(tube_vf(rp, (0.018, 0.01), 5, up=(1, 0, 0)), H), "M_HardHat")
    # dusty long-sleeve shirt with pockets, work trousers, boots
    neck(c, SK)
    surf = torso(c, "M_Dusty")
    collar_flaps(c, "M_Dusty", z=0.6)
    pelvis(c, "M_WorkPants")
    for s in (1, -1):
        c.add("torso", decal_vf(surf, rad(s * 34), 0.45, rect(0.048, 0.052), thick=0.004), "M_WorkPants")
    arms(c, SK, sleeve="long", sleeve_mat="M_Dusty", cuff_mat="M_WorkPants")
    legs(c, SK, pants="long", pants_mat="M_WorkPants", foot="boot", foot_mat=DK)
    return c


BUILDERS = {
    "player": build_player, "kakek": build_kakek, "ibu": build_ibu, "kades": build_kades,
    "nenek": build_nenek, "pemuda": build_pemuda, "petani": build_petani, "anak": build_anak,
    "preman": build_preman, "calo": build_calo, "petugas": build_petugas, "buruh": build_buruh,
}


# --------------------------------------------------------------------------- rendering
def preview_materials(on=True):
    """Blender renders only: multiply each M_ material by the baked `Col` attribute (AO + blush),
    like the game shader does. Export happens before this, with plain materials."""
    for m in bpy.data.materials:
        if not m.name.startswith("M_") or not m.use_nodes:
            continue
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        if on and "VCol" not in nt.nodes:
            a = nt.nodes.new("ShaderNodeAttribute")
            a.name, a.attribute_name = "VCol", "Col"
            mix = nt.nodes.new("ShaderNodeMix")
            mix.name, mix.data_type, mix.blend_type = "VMul", "RGBA", "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            mix.inputs[6].default_value = b.inputs["Base Color"].default_value
            nt.links.new(a.outputs["Color"], mix.inputs[7])
            nt.links.new(mix.outputs[2], b.inputs["Base Color"])


def snapshot(body, name, loc=(0, 0, 0), yaw=0.0):
    """Static copy of the posed (evaluated) mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(body.evaluated_get(dg))
    o = bpy.data.objects.new(name, me)
    link(o)
    o.location = loc
    o.rotation_euler = (0.0, 0.0, rad(yaw))
    return o


def set_frame(rig, action, f):
    rig.ob.animation_data.action = action
    bpy.context.scene.frame_set(int(f))
    bpy.context.view_layer.update()


def _scene_setup(w, h, samples=14, transparent=False, ground="#a9c46a"):
    common._setup_render(w, h, transparent=transparent, samples=samples)
    sc = bpy.context.scene
    sc.cycles.use_adaptive_sampling = True
    tmp = common._temp_lights()
    if not transparent:
        bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
        g = bpy.context.view_layer.objects.active
        common.set_mat(g, mat("_M_PreviewGround", ground))
        tmp.append(g)
    return tmp


def _camera(target, pitch, yaw=0.0, dist=12.0, ortho=None, lens=None):
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    link(cam)
    p, y = rad(pitch), rad(yaw)
    dirv = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    cam.location = Vector(target) + dirv * dist
    cam.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    if lens:
        cam.data.lens = lens
    cam.data.clip_end = dist * 4
    bpy.context.scene.camera = cam
    return cam


def _cleanup(objs):
    for o in objs:
        if o.name in bpy.data.objects:
            me = o.data if o.type == "MESH" else None
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0 and me.name.startswith("snap"):
                bpy.data.meshes.remove(me)


PROXY_TOOLS = {   # clip -> list of (z0, z1, (r_side, r_thick), colour) segments along hand_R local +Z
    "harvest": [(-0.4, 2.2, (0.014, 0.014), "#b58a4c"), (2.2, 2.45, (0.03, 0.006), "#8c9aa0")],
    "chop": [(-0.05, 0.07, (0.017, 0.017), "#5a3b24"), (0.07, 0.42, (0.028, 0.004), "#b9c3c6")],
}


def attach_proxy(c, rig, clip):
    """A stand-in tool on hand_R (like the game's BoneAttachment3D) so the sheets show the grip."""
    segs = PROXY_TOOLS.get(clip)
    if not segs:
        return []
    out = []
    ob = rig.ob
    bone = ob.data.bones["hand_R"]
    g = 0.036 * c.S * c.d["hand_k"]
    for i, (z0, z1, rr, col) in enumerate(segs):
        v, f = tube_vf([(0, 0, z0 * c.S), (0, 0, z1 * c.S)], rr, 8, up=(1, 0, 0))
        me = bpy.data.meshes.new("_tool%d" % i)
        me.from_pydata([tuple(p) for p in v], [], f)
        me.materials.append(mat("_M_Tool%d_%s" % (i, col[1:]), col, 0.6))
        o = bpy.data.objects.new("_tool%d" % i, me)
        link(o)
        o.parent = ob
        o.parent_type = "BONE"
        o.parent_bone = "hand_R"
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = T(0, g - bone.length, 0)
        out.append(o)
    return out


def render_sheet(c, rig, body, acts, clip, path, n=8):
    """Contact sheet: n evenly spaced frames of one clip, from the game camera (45 deg pitch, 3/4)
    on the top row and from the character's right side on the bottom row."""
    from PIL import Image, ImageDraw
    act = acts[clip]
    N = int(act.frame_range[1])
    frames = [round(i * N / (n - 1 if clip not in LOOPS else n)) for i in range(n)]
    cell = 0.62 * max(1.0, c.S * 1.1)
    rows = []
    body.hide_render = False
    tools = attach_proxy(c, rig, clip)
    for view in ("game", "side"):
        snaps = []
        for i, f in enumerate(frames):
            set_frame(rig, act, f)
            x = (i - (n - 1) / 2) * cell
            yaw = 25.0 if view == "game" else 90.0
            snaps.append(snapshot(body, "snap%d" % i, (x, 0, 0), yaw))
            for j, t in enumerate(tools):
                tw = t.matrix_world.copy()
                ts = snapshot(t, "snapt%d_%d" % (i, j))
                ts.matrix_world = T(x, 0, 0) @ R("Z", yaw) @ tw
                snaps.append(ts)
        body.hide_render = True
        for t in tools:
            t.hide_render = True
        tmp = _scene_setup(n * 150, 300, samples=12)
        H = 1.25 * c.S * (1.25 if c.name == "preman" else 1.0)
        if view == "game":
            cam = _camera((0, 0, H * 0.42), 45.0, 0.0, 14, ortho=n * cell)
        else:
            cam = _camera((0, 0, H * 0.5), 4.0, 0.0, 14, ortho=n * cell)
        tmp.append(cam)
        out = path.replace(".png", "_%s.png" % view)
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        _cleanup(snaps + tmp)
        body.hide_render = False
        rows.append(out)
    _cleanup(tools)
    ims = [Image.open(p).convert("RGB") for p in rows]
    sheet = Image.new("RGB", (ims[0].width, sum(i.height for i in ims) + 18), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    dr.text((6, 3), "%s / %s  (%d frames @30fps)  frames: %s" % (c.name, clip, N, frames), fill=(255, 255, 255))
    y = 18
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height
    sheet.save(path)
    for p in rows:
        os.remove(p)
    print("[sheet]", path)


def render_preview_posed(c, rig, body, acts, name):
    set_frame(rig, acts["idle"], 0)
    sn = snapshot(body, "snapP", (0, 0, 0), 20.0)
    body.hide_render = True
    tmp = _scene_setup(512, 512, samples=20, ground="#8fb35c")
    tmp.append(_camera((0, 0, 0.55 * c.S * (1.15 if c.name == "preman" else 1.0)), 38.0, 0.0, 10,
                       ortho=1.75 * c.S * (1.15 if c.name == "preman" else 1.0)))
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    _cleanup([sn] + tmp)
    body.hide_render = False
    print("[preview]", name)


def render_portrait(c, rig, body, acts):
    """256 px transparent head-and-shoulders icon (fallback dialog portrait), near-front."""
    set_frame(rig, acts["idle"], 0)
    sn = snapshot(body, "snapQ", (0, 0, 0), 0.0)
    body.hide_render = True
    pts = [sn.matrix_world @ v.co for v in sn.data.vertices]
    top = max(p.z for p in pts)
    bottom = (c.d["sh_z"] - 0.1) * c.S
    head = [p for p in pts if p.z > (c.d["head_z"] - 0.02) * c.S]
    width = (max(p.x for p in head) - min(p.x for p in head)) * math.cos(rad(14)) + 0.06 * c.S
    F = max((top - bottom) * 1.06, width * 1.04)
    tmp = _scene_setup(256, 256, samples=24, transparent=True)
    cz = bottom + F / 2 - 0.01 * c.S
    tmp.append(_camera((0, 0, cz), 6.0, 14.0, 6.0, ortho=F))
    bpy.context.scene.render.filepath = os.path.join(ICONS_DIR, "portrait_%s.png" % c.name)
    bpy.ops.render.render(write_still=True)
    _cleanup([sn] + tmp)
    body.hide_render = False
    print("[portrait]", c.name)


# --------------------------------------------------------------------------- build / export
def mark_loops_in_import(name):
    """Tell Godot's importer to loop the cyclic clips (sets loop_mode = LINEAR on re-import) by
    writing them into the existing .glb.import sidecar. Other import settings are left alone."""
    import re
    path = os.path.join(common.MODELS_DIR, name + ".glb.import")
    if not os.path.exists(path):
        return
    txt = open(path).read()
    block = "_subresources={\n\"animations\": {\n" + ",\n".join(
        "\"%s\": {\n\"settings/loop_mode\": 1\n}" % n for n in LOOPS) + "\n}\n}"
    new, n = re.subn(r"_subresources=\{.*?\n\}\n(?=\S)|_subresources=\{\}", block, txt, count=1, flags=re.S)
    if n and new != txt:
        open(path, "w").write(new)
        print("[import] loops marked in", os.path.basename(path))



def mesh_bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def build_one(name, out=True, sheets=None):
    c = BUILDERS[name]()
    st = dict(STYLE, **c.style)
    rig_ob, body = assemble(c, bake=True)
    rig = Rig(rig_ob, c)
    acts = bake_actions(rig, st)
    bpy.context.view_layer.update()
    mn, mx = mesh_bounds(body)
    tris = count_tris(body)
    mats = sorted(m.name for m in body.data.materials)
    info = dict(name=name, height=mx.z, tris=tris, mats=mats)
    print(f"[char] {name}: h={mx.z:.3f} tris={tris} mats={len(mats)} {mats}")
    if tris > 6000:
        print(f"  !! {name} over triangle budget")
    if len(mats) > 6:
        print(f"  !! {name} over material budget")
    if out:
        rig_ob.animation_data.action = acts["idle"]
        bpy.context.scene.frame_set(0)
        export_glb(rig_ob, "char_" + name, animations=True)
        mark_loops_in_import("char_" + name)
        preview_materials(True)
        render_preview_posed(c, rig, body, acts, "char_" + name)
        render_portrait(c, rig, body, acts)
    if sheets:
        preview_materials(True)
        for clip in sheets:
            render_sheet(c, rig, body, acts, clip, os.path.join(PREVIEW_DIR, "char_%s_%s.png" % (name, clip)))
    return c, rig, body, info


def lineup(names):
    reset_scene()
    per_row = 6
    snaps = []
    for i, n in enumerate(names):
        c = BUILDERS[n]()
        st = dict(STYLE, **c.style)
        rig_ob, body = assemble(c, bake=True)
        rig = Rig(rig_ob, c)
        acts = bake_actions(rig, st, ["idle"])
        set_frame(rig, acts["idle"], (i * 11) % 72)
        row, col = divmod(i, per_row)
        snaps.append(snapshot(body, "snapL%d" % i, ((col - (per_row - 1) / 2) * 0.95, row * 1.3, 0.0), 0.0))
        body.hide_render = True
    preview_materials(True)
    tmp = _scene_setup(1600, 1000, samples=16, ground="#8fb35c")
    tmp.append(_camera((0, 0.62, 0.5), 30.0, 0.0, 20, ortho=5.9))
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, "lineup.png")
    bpy.ops.render.render(write_still=True)
    print("[preview] lineup.png")


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    only_lineup = "--lineup" in argv
    no_out = "--no-out" in argv
    sheets = None
    for a in argv:
        if a.startswith("--sheets"):
            sheets = a.split("=", 1)[1].split(",") if "=" in a else list(CLIPS)
    order = list(BUILDERS)
    todo = names or ([] if only_lineup else order)
    infos = []
    for n in todo:
        reset_scene()
        _, _, _, info = build_one(n, out=not no_out, sheets=sheets)
        infos.append(info)
    if (not names or only_lineup) and not no_out:
        lineup(order)
    print("\n==== summary ====")
    for i in infos:
        print(f"{i['name']:8s} height={i['height']:.3f} tris={i['tris']:5d} mats={len(i['mats'])}")


if __name__ == "__main__":
    main(sys.argv[1:])

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
           hips > extra_skirt_0..7   (kakek, ibu, nenek only: skirt panels, see skirt_rig())
    Body   (mesh, Armature modifier, <= 6000 tris, <= 6 materials, baked AO + blush in `Col`)

Cloth layers around the hips (shirt over trousers / skirt over the tops of the leg tubes) share one
skin-weight field there (Char.hip_field), and geometry hidden under a layer is trimmed, so kneeling
and high knees don't push one layer through another; decals take the weights of the cloth point under
them. Every build runs automated checks and prints them (walk/run knee flare and thigh turn per frame,
cloth layer exposure, parang clearance over the chop, fist sinking into the body).

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

Locomotion is sized for the game's speeds: a planted foot rolls over its own (rounded) sole
without slipping while the ground slides back at a constant speed, and walk/run strides are long
enough that the NPC stroll (1.25 m/s) and the player's run (~5 m/s) need only ~2x playback.
The numbers the game needs are exported as glTF extras on the armature node (Godot: the
`extras` metadata of node `char_<name>`): walk_speed / run_speed = ground speed in m/s at 1x,
walk_stance / run_stance = share of the cycle a foot is planted, *_stance_ankle = the same
measured on the ankle (use it if you estimate speed from the foot bone's travel), grip_offset
= fist centre along hand_R +Y (tool shafts run along hand_R local +Z).

The .glb.import sidecars get loop flags for the looping clips (balanced, idempotent rewrite).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: E402

import common  # noqa: E402
from common import (ICONS_DIR, PREVIEW_DIR, bake_vertex_ao, count_tris, link,  # noqa: E402
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
    if len(vf) > 2:
        return [m @ Vector(v) for v in vf[0]], vf[1], [m @ Vector(a) for a in vf[2]]
    return [m @ Vector(v) for v in vf[0]], vf[1]


def anchored(vf, surf):
    """Attach weight anchors to geometry lying on a lathe surface (straps, piping): each vertex takes
    the skin weights of the surface point radially below it."""
    return vf[0], vf[1], [surf.anchor(Vector(p)) for p in vf[0]]


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

    rc0, rc1 = round_caps if isinstance(round_caps, tuple) else (round_caps, round_caps)
    t0, nn0, b0 = frame(0)
    if rc0 and not closed:
        rw, rh = rr(0)
        for k in range(rc0, 0, -1):
            a = (math.pi / 2) * k / (rc0 + 1)
            rings.append(ring_at(pts[0] - t0 * (max(rw, rh) * math.sin(a)), nn0, b0, rw * math.cos(a),
                                 rh * math.cos(a)))
    for i, p in enumerate(pts):
        t, nn, b = frame(i)
        rw, rh = rr(i)
        rings.append(ring_at(p, nn, b, rw, rh))
    t1, nn1, b1 = frame(n - 1)
    if rc1 and not closed:
        rw, rh = rr(n - 1)
        for k in range(1, rc1 + 1):
            a = (math.pi / 2) * k / (rc1 + 1)
            rings.append(ring_at(pts[-1] + t1 * (max(rw, rh) * math.sin(a)), nn1, b1, rw * math.cos(a),
                                 rh * math.cos(a)))
    nr = len(rings)
    for i in range(nr if closed else nr - 1):
        A, B = rings[i], rings[(i + 1) % nr]
        faces += [(A[j], B[j], B[(j + 1) % seg], A[(j + 1) % seg]) for j in range(seg)]
    if caps and not closed:
        c0 = len(verts)
        first = pts[0] - (t0 * max(rr(0)) if rc0 else Vector())
        verts.append(first)
        faces += [(c0, rings[0][j], rings[0][(j + 1) % seg]) for j in range(seg)]
        c1 = len(verts)
        last = pts[-1] + (t1 * max(rr(n - 1)) if rc1 else Vector())
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
    minv = m.inverted() if m is not None else None

    def anchor(p):
        q = minv @ p if minv is not None else p
        return f(math.atan2(q.x / sx, -q.y / sy), q.z)
    f.anchor = anchor
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
    anch = [f(a, z)] + [f(a + u / du, z + v / dz) for (u, v) in outline]
    if thick <= 0:
        verts = [P(a, z, off)] + [P(a + u / du, z + v / dz, off) for (u, v) in outline]
        return verts, [(0, i + 1, (i + 1) % k + 1) for i in range(k)], anch
    verts = [P(a, z, off + thick)] + [P(a + u / du, z + v / dz, off + thick) for (u, v) in outline]
    verts += [P(a + u * 1.06 / du, z + v * 1.06 / dz, off - 0.002) for (u, v) in outline]
    anch += [f(a + u * 1.06 / du, z + v * 1.06 / dz) for (u, v) in outline]
    faces = [(0, i + 1, (i + 1) % k + 1) for i in range(k)]
    faces += [(i + 1, k + 1 + i, k + 1 + (i + 1) % k, (i + 1) % k + 1) for i in range(k)]
    return verts, faces, anch


def strip_vf(f, a, z0, z1, width, off=0.004, steps=6):
    verts, faces, anch = [], [], []
    for k in range(steps + 1):
        z = z0 + (z1 - z0) * k / steps
        du, _ = _metric(f, a, z)
        for u in (-width / 2, width / 2):
            aa = a + u / du
            anch.append(f(aa, z))
            verts.append(f(aa, z) + snormal(f, aa, z) * off)
    for k in range(steps):
        i = 2 * k
        faces.append((i, i + 1, i + 3, i + 2))
    return verts, faces, anch


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
SKIRT_N = 8
SKIRT = tuple("extra_skirt_%d" % i for i in range(SKIRT_N))   # skirt panels (children of hips), see skirt_rig()
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
        self.skirt = None         # skirt panel rig (long skirts / sarongs), see skirt_rig()

    # ---- geometry bookkeeping
    def add(self, rule, vf, m, smooth=True):
        """vf = (verts, faces) or (verts, faces, anchors): anchors are the points whose skin weights
        the vertices take (decals use the cloth surface point under them, so they ride the cloth)."""
        self.chunks.append((vf[0], vf[1], m, smooth, rule, vf[2] if len(vf) > 2 else None))

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

    # Around the hips several layers overlap (shirt over trousers/skirt over the tops of the leg
    # tubes). They all take their weights from ONE field there (thigh_share + hip_field), so that
    # the layers deform alike and cannot cross when the hips flex (kneeling, high knees): a layer
    # with even a little more thigh weight than the one under it folds through it.
    def zones(self):
        """(waist, top's hem, crotch) heights: the thigh share starts at the waist, is 0.3 at the
        hem line of the tops and rises to its full value at the crotch (visible trousers)."""
        d = self.d
        return d["hip_z"] + 0.03, d["hip_z"] - 0.04, d.get("crotch_z", d["hip_z"] - 0.073)

    def thigh_share(self, p, low=0.55, top=0.3):
        zw, zh, zc = self.zones()
        k = top * ss(zw, zh, p.z) + low * ss(zh, zc, p.z)
        return k * (1.0 - 0.45 * ss(-0.02, 0.1, p.y))   # the seat stays with the pelvis

    def hip_field(self, p, k, split=0.05):
        w = {b: v * (1.0 - k) for b, v in self.w_spine(p.z).items()}
        sL = ss(-split, split, p.x)
        w["thigh_L"] = w.get("thigh_L", 0.0) + k * sL
        w["thigh_R"] = w.get("thigh_R", 0.0) + k * (1.0 - sL)
        return w

    def w_torso(self, p, arm_k=0.5, thigh_k=0.3, arm_r=0.085):
        d = self.d
        w = self.hip_field(p, self.thigh_share(p, low=0.0, top=thigh_k)) if thigh_k > 0 else self.w_spine(p.z)
        for side in (1, -1):
            S = Vector((side * d["sh_x"], 0.0, d["sh_z"]))
            lat = p.x * side
            if lat > 0.02:
                a = arm_k * ss(arm_r, 0.02, (p - S).length) * ss(0.03, 0.09, lat)
                self._mix(w, "upperarm_" + sfx(side), a)
        return w

    def w_pelvis(self, p):
        return self.hip_field(p, self.thigh_share(p, low=0.55))

    def w_skirt(self, p, kmax=0.72):
        d = self.d
        zw, zh, zc = self.zones()
        if self.skirt:     # hip field at the waist (like the top over it), panels below
            g = ss(zh, zh - 0.07, p.z)
            w = {b: v * (1 - g) for b, v in self.hip_field(p, self.thigh_share(p, low=0.0)).items()}
            a = math.atan2(p.x, -p.y / self.skirt["sy"]) % TAU
            t = a / (TAU / SKIRT_N)
            i0 = int(math.floor(t)) % SKIRT_N
            t -= math.floor(t)
            w[SKIRT[i0]] = w.get(SKIRT[i0], 0.0) + g * (1 - t)
            i1 = (i0 + 1) % SKIRT_N
            w[SKIRT[i1]] = w.get(SKIRT[i1], 0.0) + g * t
            return w
        lo = ss(zh, d["ankle_z"] + 0.02, p.z)
        k = self.thigh_share(p, low=0.0) + (kmax - 0.3) * lo * (1.0 - 0.45 * ss(-0.02, 0.1, p.y))
        w = self.hip_field(p, k, split=0.05 + 0.03 * ss(zh, zh - 0.08, p.z))
        sh = 0.45 * ss(d["knee_z"] + 0.02, d["ankle_z"], p.z)
        for x in ("L", "R"):
            t = w.pop("thigh_" + x)
            w["thigh_" + x], w["shin_" + x] = t * (1 - sh), t * sh
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
        # inside the pelvis the leg tube's top takes the shared hip field, so it stays under the
        # trousers and the shirt; it becomes a plain leg just below the crotch
        zw, zh, zc = self.zones()
        t = ss(zc + 0.01, zc - 0.035, p.z)
        if t < 1.0:
            hf = self.hip_field(p, self.thigh_share(p, low=0.55))
            w = {b: (1 - t) * hf.get(b, 0.0) + t * w.get(b, 0.0) for b in set(hf) | set(w)}
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


def skirt_rig(c, prof, sy):
    """Long skirts / sarongs get SKIRT_N panel bones (extra_skirt_*, children of hips) hinged at the
    hip joints' height around the body. The solver swings each panel out just enough to clear the
    legs and the ground and lets it hang back when the hips tilt, so the cloth never has to follow
    two legs going opposite ways (kneeling, running) - it drapes over the knee instead."""
    d = c.d
    surf = lathe_surf(prof, 1.0, sy)
    pz = d["hip_z"]
    zs = [z for (r, z) in prof if r > 1e-6]
    hem_z = min(zs)
    dirs, tabs, hems = [], [], []
    for i in range(SKIRT_N):
        a = TAU * i / SKIRT_N
        k = math.hypot(math.sin(a), sy * math.cos(a))
        h = Vector((math.sin(a), -sy * math.cos(a), 0.0)).normalized()
        tab = []
        z = hem_z
        while z < pz - 1e-4:
            rr, dz = surf.r_at(z) * k, pz - z
            tab.append((math.hypot(rr, dz), math.atan2(rr, dz)))    # (distance from hinge, angle from down)
            z += 0.005
        widest = max(prof, key=lambda q: q[0] if q[1] < pz else -1.0)
        hem = h * surf.r_at(hem_z) * k + Vector((0.0, 0.0, hem_z - pz))
        dirs.append((h * widest[0] * k + Vector((0.0, 0.0, widest[1] - pz))).normalized())
        tabs.append(sorted(tab))
        hems.append(hem)
    c.skirt = dict(sy=sy, dirs=dirs, tabs=tabs, hems=hems)


def skirt_beta(tab, dist):
    """Angle (from straight down) of the skirt surface at `dist` from the hinge (unscaled)."""
    if dist <= tab[0][0]:
        return math.pi / 2
    for (d0, b0), (d1, b1) in zip(tab, tab[1:]):
        if d0 <= dist <= d1:
            return b0 + (b1 - b0) * ((dist - d0) / (d1 - d0) if d1 > d0 else 0.0)
    return tab[-1][1]


# --------------------------------------------------------------------------- body
# (radius, z) profiles, revolved with sy = BODY_SY
# (the tops get extra rings around the hips, where the skin weights change quickly, so the shirt
# bends as smoothly as the trousers under it; the trousers end in a low dome just above the hem)
TORSO = [(0.0, 0.296), (0.118, 0.297), (0.146, 0.308), (0.153, 0.33), (0.1528, 0.35), (0.152, 0.37),
         (0.151, 0.39), (0.147, 0.45), (0.141, 0.5), (0.128, 0.545), (0.101, 0.58), (0.062, 0.603), (0.0, 0.61)]
TUCKED = [(0.0, 0.33), (0.13, 0.331), (0.146, 0.345), (0.148, 0.365), (0.149, 0.39)] + \
    [p for p in TORSO if p[1] >= 0.45]
PELVIS = [(0.0, 0.262), (0.07, 0.265), (0.116, 0.279), (0.137, 0.305), (0.1415, 0.325), (0.138, 0.34),
          (0.1, 0.352), (0.0, 0.356)]
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
        # leg tubes start (flat-capped) at the hip joint, well inside the pelvis/trousers, instead of
        # reaching up under the shirt where a flexing thigh would push them out through it
        top = H.z
        if dress:
            c.add(rule, tube_vf([A + up * 0.085, A + up * 0.02], [d["ankle_r"] * 1.05, d["ankle_r"]], 10,
                                up=FRONT, round_caps=1), skin)
        elif pants != "long":
            zs = [top, H.z - 0.025, (H.z + K.z) / 2, K.z, (K.z + A.z) / 2 + 0.01, A.z + 0.015]
            rs = [d["thigh_r"] * 0.95, d["thigh_r"], d["thigh_r"] * 0.94, d["knee_r"], d["shin_r"], d["ankle_r"]]
            if pants in ("shorts", "rolled"):   # bare leg only from just inside the trouser hem down
                z0 = (shorts_z if pants == "shorts" else K.z - 0.035) + 0.025
                r0 = lathe_surf(list(zip(rs, zs))[::-1]).r_at(z0)
                keep = [(z, r) for z, r in zip(zs, rs) if z < z0 - 0.012]
                zs, rs = [z0] + [z for z, r in keep], [r0] + [r for z, r in keep]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 8, up=FRONT, round_caps=(0, 1)),
                  sock_mat or skin)
        hm = hem_mat or pants_mat
        if pants == "long":
            zs = [top, H.z - 0.025, (H.z + K.z) / 2, K.z, (K.z + A.z) / 2, A.z + 0.03, A.z + 0.004]
            rs = [d["thigh_r"] + 0.009, d["thigh_r"] + 0.012, d["thigh_r"] + 0.008, d["knee_r"] + 0.012,
                  d["shin_r"] + 0.013, d["ankle_r"] + 0.016, d["ankle_r"] + 0.017]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 10, up=FRONT, round_caps=(0, 1)), pants_mat)
        elif pants in ("shorts", "rolled"):
            z0 = shorts_z if pants == "shorts" else K.z - 0.035
            zs = [top, H.z - 0.025, (H.z + z0) / 2, z0]
            rs = [d["thigh_r"] + 0.016, d["thigh_r"] + 0.02, d["thigh_r"] + 0.018, d["thigh_r"] + 0.014]
            if pants == "rolled":    # (a ring at the knee, so the bent knee stays inside)
                zs = [top, H.z - 0.025, (H.z + K.z) / 2, K.z + 0.01, K.z - 0.012, z0]
                rs = [d["thigh_r"] + 0.011, d["thigh_r"] + 0.013, d["thigh_r"] + 0.01, d["knee_r"] + 0.016,
                      d["knee_r"] + 0.015, d["shin_r"] + 0.012]
            c.add(rule, tube_vf([Vector((x, 0, z)) for z in zs], rs, 10, up=FRONT, round_caps=0), pants_mat)
            hw = 0.009 if pants == "shorts" else 0.016
            c.add(rule, tube_vf([Vector((x, 0, z0 + hw)), Vector((x, 0, z0 - hw * 0.5))],
                                [rs[-1] + 0.006, rs[-1] + 0.005], 10, up=FRONT, round_caps=0), hm)
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
    if c.skirt:
        piv = Vector((0.0, 0.0, d["hip_z"]))
        for i, n in enumerate(SKIRT):
            bone(n, piv, piv + c.skirt["dirs"][i] * 0.12, "hips", roll_to=UP)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "XYZ"
    return ob


def build_mesh(c, name):
    verts, faces, fmat, fsmooth, mats, vw = [], [], [], [], [], []
    c.vranges = []
    for (vs, fs, mname, smooth, rule, anchors) in c.chunks:
        if mname not in mats:
            mats.append(mname)
        mi = mats.index(mname)
        base = len(verts)
        c.vranges.append((base, base + len(vs), rule, mname))
        for k, v in enumerate(vs):
            v = Vector(v)
            vw.append(c.weights(rule, Vector(anchors[k]) if anchors is not None else v))
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
    groups = {b: ob.vertex_groups.new(name=b) for b in BONES + EXTRAS + (SKIRT if c.skirt else ())}
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
    u = d / max(dist, 1e-9)
    lo, hi = abs(L1 - L2) + 1e-4, (L1 + L2) * 0.9995
    ds = hi * soft
    if dist > ds:
        dist = ds + (hi - ds) * (1.0 - math.exp(-(dist - ds) / (hi - ds)))
    reach = clamp(dist, lo, hi)
    p = pole - u * pole.dot(u)
    if p.length < 1e-6:
        p = Vector((0, 0, 1)) - u * u.z
    p.normalize()
    ca = clamp((L1 * L1 + reach * reach - L2 * L2) / (2 * L1 * reach), -1.0, 1.0)
    a = math.acos(ca)
    E = S + (u * math.cos(a) + p * math.sin(a)) * L1
    return E, S + u * reach


FOOT_PTS = ((0.0, -0.095, -0.045, 0.034), (0.0, -0.03, -0.055, 0.04), (0.0, 0.04, -0.035, 0.034))
SKIRT_GRAVITY = 0.7     # how much of the hips' tilt a hanging skirt panel takes back


class Rig:
    def solve_skirt(self, W, put, conj, Qh):
        c, S, d, sk = self.c, self.S, self.c.d, self.c.skirt
        QhT = Qh.transposed()
        piv = W["hips"] @ (self.rest["hips"].inverted() @ (Vector((0.0, 0.0, d["hip_z"])) * S))
        pts = []                                  # leg surface samples in the hips frame (scaled)
        for x in ("L", "R"):
            J, E, A = W["thigh_" + x].translation, W["shin_" + x].translation, W["foot_" + x].translation
            Mf = W["foot_" + x] @ self.rest["foot_" + x].inverted()
            A0 = self.rest["foot_" + x].translation
            smp = [(J.lerp(E, 0.5), d["thigh_r"] + 0.015), (E, d["knee_r"] + 0.012), (E.lerp(A, 0.5), d["shin_r"] + 0.012),
                   (A, d["ankle_r"] + 0.01)]
            smp += [(Mf @ (A0 + Vector(o[:3]) * S), o[3]) for o in FOOT_PTS]
            pts += [(QhT @ (p - piv), r * S) for (p, r) in smp]
        g_h = QhT @ Vector((0.0, 0.0, -1.0))
        dA = TAU / SKIRT_N
        m = 0.018 * S          # (a little spare room: the game may widen the stride procedurally)
        ths, axes = [], []
        for i, n in enumerate(SKIRT):
            D0 = sk["dirs"][i]
            h = Vector((D0.x, D0.y, 0.0)).normalized()
            axis = Vector((0.0, 0.0, -1.0)).cross(h).normalized()
            tab = sk["tabs"][i]
            hem_d = tab[-1][0] * S
            th = SKIRT_GRAVITY * math.atan2(g_h.dot(h), -g_h.z)          # hang with gravity
            pref = th
            for (ph, r) in pts:
                rho = math.hypot(ph.x, ph.y)
                if rho < 1e-6:
                    continue
                psi = math.acos(clamp((ph.x * h.x + ph.y * h.y) / rho, -1.0, 1.0))
                wf = ss(dA, dA * 0.5, psi)
                ro = rho + r + m
                Dp = math.hypot(ro, ph.z)
                w = wf * ss(hem_d + 0.03 * S, hem_d - 0.02 * S, Dp)
                if w <= 0.0:
                    continue
                need = math.atan2(ro, -ph.z) - skirt_beta(tab, Dp / S)
                if need > pref:
                    th = max(th, pref + w * (need - pref))
            th = clamp(th, rad(-35.0), rad(100.0))
            q = sk["hems"][i] * S                                     # keep the hem above the ground
            for _ in range(140):
                if piv.z + (Qh @ (Matrix.Rotation(th, 3, axis) @ q)).z >= 0.006 * S or th >= rad(100.0):
                    break
                th += rad(0.5)
            ths.append(th)
            axes.append(axis)
        # a panel next to a strongly lifted one lifts a little too (round hem, no spikes)
        ths = [max(t, 0.5 * t + 0.25 * (ths[i - 1] + ths[(i + 1) % SKIRT_N])) for i, t in enumerate(ths)]
        for n, th, axis in zip(SKIRT, ths, axes):
            put(n, conj(n, Matrix.Rotation(th, 3, axis)))

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
        self.seams = {}      # loop clip -> (rotation deg, offset m) between the solver's last and first frame

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

        # --- arms (right first: a two-handed pole grip puts the left hand on the right hand's pole)
        g = 0.036 * S * self.c.d["hand_k"]
        for side in (-1, 1):
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
            L1, L2 = self.len[up], self.len[fo]
            grip = P.get("grip" + x)
            grip_world = False
            tgt = None
            if ikw > 1e-4:
                tgt = Vector(P["ikt" + x]) * S
                if P.get("iksp", 0.0) > 0.5:     # target + grip axis given in the chest's rest frame
                    tgt = W["chest"] @ (self.rest["chest"].inverted() @ tgt)
                    grip = Qc @ Vector(grip) if grip is not None else None
                    grip_world = True
                if P.get("ikgnd", 0.0) > 0.5:    # (inward, forward offset from the shoulder, height)
                    o = Vector(P["ikt" + x]) * S
                    tgt = Vector((Sw.x - side * o.x, Sw.y + o.y, o.z))
                if side > 0 and P.get("polefollow", 0.0) > 0.5 and "hand_R" in W:
                    # left hand on the pole axis through the right fist (hand_R local +Z), sliding
                    # along it (within +-5 cm of the wanted spacing) to stay inside the arm's reach
                    MR = W["hand_R"]
                    ax = (MR.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
                    gR = MR @ Vector((0.0, g, 0.0))
                    t0 = P.get("poled", 0.11) * S
                    ok = 0.86 * (L1 + L2) + 0.8 * g
                    tf = (Sw - gR).dot(ax)
                    perp2 = (Sw - (gR + ax * tf)).length_squared
                    t = t0
                    if (gR + ax * t0 - Sw).length > ok and perp2 < ok * ok:
                        h = math.sqrt(ok * ok - perp2)
                        t = min((tf - h, tf + h), key=lambda v: abs(v - t0))
                    t = clamp(t, t0 - 0.05 * S, t0 + 0.05 * S)
                    tgt = gR + ax * t
                    grip, grip_world = ax, True
            if tgt is not None:
                pole = Qc @ Vector(P["ikp" + x])
                wr = tgt.copy()
                for _ in range(4):   # solve for the wrist so that the fist (not the wrist) lands on the target
                    E, reached = two_bone(Sw, wr, L1, L2, pole, soft=P["iksoft"])
                    D1 = (E - Sw).normalized()
                    D2 = (reached - E).normalized()
                    if grip is not None:
                        G = Vector(grip).normalized()
                        yh = (D2 - G * D2.dot(G)).normalized()
                    else:
                        yh = D2
                    wr = tgt - yh * g
                miss = (reached + yh * g - tgt).length
                if miss > 0.006 * S and ikw > 0.5:
                    self.warn += 1
                    self.log.append(("arm" + x, round(miss / S, 3)))
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
            gw = P.get("gripw" + x, 0.0)
            if grip is not None and gw > 1e-4:
                G = Vector(grip).normalized()
                if P.get("iksp", 0.0) > 0.5 and not grip_world:
                    G = Qc @ G
                Y2 = f2.col[1]
                yh = (Y2 - G * Y2.dot(G)).normalized()
                gm = hb.inverted() @ cols(yh.cross(G), yh, G)
                fk_h = fk_h.to_quaternion().slerp(gm.to_quaternion(), gw).to_matrix()
            put(ha, fk_h)

        # --- legs (IK: ankle target in world, knee pole in the leg's sagittal plane, foot orientation
        # in world). The pole is built from the lateral axis (hips + foot yaw) and the hip->ankle
        # direction: lateral x (hip->ankle) always points to the front of the leg line (forward-down
        # when the heel kicks up behind, forward-up when the foot reaches ahead), so the knee stays
        # in the sagittal plane and never flips out sideways; `kneeout` opens it outward on purpose.
        Qh = W["hips"].to_3x3() @ self.r3("hips").inverted()
        for side in (1, -1):
            x = sfx(side)
            th, sh, ft = "thigh_" + x, "shin_" + x, "foot_" + x
            base = W["hips"] @ self.rel[th]
            J = base.translation
            dx, dy, dz, toe, yaw = P["leg" + x]
            A0 = self.rest[ft].translation
            tgt = A0 + Vector((dx, dy, dz)) * S
            lat = Matrix.Rotation(rad(yaw), 3, "Z") @ Vector((1.0, 0.0, 0.0)) + Qh @ Vector((1.0, 0.0, 0.0))
            lat.z = 0.0
            lat.normalize()
            u = tgt - J
            u = u.normalized() if u.length > 1e-6 else -UP
            pole = u.cross(lat)
            pole = (pole.normalized() if pole.length > 1e-4 else FRONT.copy()) + \
                lat * (side * P["kneeout"][0 if side > 0 else 1])
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

        # --- skirt panels: swing out just enough to clear the legs and the ground, hang with gravity
        if self.c.skirt:
            self.solve_skirt(W, put, conj, Qh)

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
        self.W = W
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
        "iksp": (0.0,), "ikgnd": (0.0,), "polefollow": (0.0,), "poled": (0.11,), "kneeout": (0.12, 0.12),
        "ikpL": (0.7, 0.5, -0.5), "ikpR": (-0.7, 0.5, -0.5), "iksoft": (0.88,),
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
        P["ikp" + x] = get("ikp" + x, f)
        P["grip" + x] = get("grip" + x, f)
        P["gripw" + x] = get("gripw" + x, f)[0]
    for k in ("iksp", "ikgnd", "polefollow", "poled", "iksoft"):
        P[k] = get(k, f)[0]
    P["kneeout"] = get("kneeout", f)
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
        # (sized to read at game scale: ~3 cm of hip sway, the chest and shoulders rise with the breath)
        if ch == "hips_off":
            return (0.016 * sh, 0.0, -0.008 + 0.003 * math.sin(2 * TAU * ph))
        if ch == "hips":
            return (0.0, 1.8 * sh, -3.6 * sh)
        if ch == "spine":
            return (base["spine"][0] + 0.9 * br, -0.9 * shl, 2.3 * shl)
        if ch == "chest":
            return (base["chest"][0] - 2.6 * br, -0.6 * shl2, 1.5 * shl2)
        if ch == "neck":
            return (base["neck"][0] + 1.2 * brl, 0.4 * look(f - 3), 0.0)
        if ch == "head":
            return (base["head"][0] + 2.0 * brl, 0.8 * look(f), base["head"][2] + tilt(f) - 1.2 * shl2)
        if ch in ("armL", "armR"):
            side = 1 if ch == "armL" else -1
            fk, ikw, _ = idle_arm_pose(st, side, rig)
            lag = math.sin(TAU * (ph - 10 / N))
            return (fk[0] + 2.4 * lag, fk[1] + 2.6 * brl + 1.2 * side * shl, fk[2], fk[3] + 4.5 * lag)
        if ch in ("handL", "handR"):
            lag = math.sin(TAU * (ph - 14 / N))
            return (6.0 * lag, 0.0, 0.0)
        if ch in ("ikL", "ikR"):
            return (idle_arm_pose(st, 1 if ch == "ikL" else -1, rig)[1],)
        if ch in ("iktL", "iktR"):
            side = 1 if ch == "iktL" else -1
            # hands on hips (akimbo) / clasped in front of the belly / clipboard at the chest
            if st["idle_arms"] == "clip" and side > 0:
                return (0.07, -0.16, 0.44 + 0.006 * br)
            if st["idle_arms"] == "front":
                rub = 0.012 * st.get("rub", 0.0) * math.sin(2 * TAU * 4 * ph) * side
                return (side * 0.03 + rub, -0.15 * d["sh_x"] / DEF["sh_x"], d["hip_z"] + 0.07 + 0.006 * br)
            return (side * (d["sh_x"] + 0.05), -0.01, d["hip_z"] + 0.055 + 0.005 * br)
        if ch in ("gripL", "gripR"):
            return (0.0, 0.0, 1.0) if st["idle_arms"] == "clip" else (0.0, -1.0, 0.0)
        if ch == "gripwL":
            return (1.0 if st["idle_arms"] == "clip" else 0.0,)
        if ch == "eyes":
            b = blink(f)
            return (b, b)
        return base[ch]
    return N, True, get


# Locomotion. The stride is sized for the game's speeds (NPC stroll 1.25 m/s, player run ~5 m/s):
# the planted foot travels `front + back` metres (x stride style x leg length) while it is on the
# ground for `sigma` of the cycle, so ground speed = travel / (sigma * clip length) at 1x playback.
# The foot really rolls over its heel and ball (pivot fixed on the ground), so the ankle travels
# less than the ground does - see gait_speed().
GAIT = {
    "walk": dict(N=27, sigma=0.55, front=0.14, back=0.18, reach=0.968, heel=0.48, td_toe=-18.0, to_toe=38.0,
                 lift=0.036,
                 bob=0.03, lean=6.0, arm=34.0, yaw=7.0),
    "run": dict(N=18, sigma=0.30, front=0.13, back=0.27, reach=0.968, heel=0.3, td_toe=3.0, to_toe=56.0,
                lift=0.12,
                bob=0.03, lean=19.0, arm=46.0, yaw=10.0),
}
# Run swing keys: (share of the swing, kind, a, b, foot pitch in deg (+ = toe down; None = just short
# of the touchdown pitch), least sole clearance x `lift`). kind "fk": a = thigh angle forward from
# straight down, b = knee bend (deg, + energy x 10 deg extra drive; the knee folds further where the
# sole would come closer to the ground than the clearance); kind "ik": the ankle at a = 0 (toe-off
# spot) .. 1 (touchdown spot), b x `lift` above the line from the toe-off to the touchdown ankle
# height. Heel kick up behind, foot tucked high under the hip while the knee drives forward, reach
# just past the touchdown spot with the foot still well off the ground, then a short drop onto it
# (with a little paw-back).
RUN_SWING = ((0.14, "fk", -14.0, 92.0, 72.0, 0.25), (0.34, "fk", 6.0, 124.0, 60.0, 0.6),
             (0.55, "fk", 44.0, 118.0, 30.0, 0.4), (0.74, "fk", 64.0, 84.0, 12.0, 0.4),
             (0.88, "ik", 1.06, 0.2, None, 0.0))


def gait_dims(c, st, kind):
    """Scaled stride numbers of one character for one gait (unscaled metres, like pose specs)."""
    g = GAIT[kind]
    d = c.d
    legk = (d["hip_z"] - d["ankle_z"]) / (DEF["hip_z"] - DEF["ankle_z"])
    sk = st["stride"] * legk
    return g, legk, g["front"] * sk, g["back"] * sk


def foot_table(c):
    """How the planted foot rolls, from the character's own (rounded) sole: for each pitch angle
    (+ = heel up / toe down) the ankle offset that keeps the sole touching the ground without
    slipping (the contact point walks along the sole by the arc length it rolls over).
    Returns {deg: (dy, dz)} relative to the flat foot, deg in -40..90."""
    d = c.d
    A = Vector((d["leg_x"], 0.0, d["ankle_z"]))
    pts = [Vector(v) - A for ch in c.chunks if ch[4] == ("foot", 1) for v in ch[0]]
    yz = [(p.y, p.z) for p in pts]

    def contact(deg):
        th = rad(deg)
        cth, sth = math.cos(th), math.sin(th)
        best = min(range(len(yz)), key=lambda i: yz[i][0] * sth + yz[i][1] * cth)
        y, z = yz[best]
        return best, y * cth - z * sth, y * sth + z * cth
    tab = {}
    i0, cy0, cz0 = contact(0.0)
    for sgn, rng in ((1, range(0, 91)), (-1, range(0, -41, -1))):
        s_arc, prev = 0.0, None
        # the flat foot touches at its lowest point; rolling starts from the contact at +-0.5 deg
        for deg in rng:
            i, cy, cz = contact(deg if deg else sgn * 0.5)
            if prev is not None and i != prev:
                s_arc += math.hypot(yz[i][0] - yz[prev][0], yz[i][1] - yz[prev][1])
            prev = i
            if deg == 0:
                base_y = cy
            tab[deg] = (base_y - sgn * s_arc - cy, cz0 - cz)
    tab[0] = (0.0, 0.0)
    return tab


def foot_roll(L, toe, tab):
    """Ankle (dy, dz) of a planted foot whose flat-foot ankle would be at dy = L, rolled by
    `toe` degrees (+ = heel up, rolling onto the ball; - = toe up, rocking on the heel)."""
    t = clamp(toe, -40.0, 90.0)
    a = math.floor(t)
    b = min(a + 1, 90)
    k = t - a
    (ya, za), (yb, zb) = tab[int(a)], tab[int(b)]
    return L + lerp(ya, yb, k), lerp(za, zb, k)


def gait_speed(c, st, kind):
    """(ground speed at 1x in m/s, ankle travel / ground travel) for one character's clip."""
    g, legk, Af, Ab = gait_dims(c, st, kind)
    tab = foot_table(c)
    y0 = foot_roll(-Af, g["td_toe"], tab)[0]
    y1 = foot_roll(Ab, g["to_toe"], tab)[0]
    T = g["N"] / FPS
    return (Af + Ab) * c.S / (g["sigma"] * T), (y1 - y0) / (Af + Ab)


def gait(rig, st, kind):
    """Shared walk / run cycle. Left foot touches down at frame 0, right at N/2. In place: the
    pelvis never drifts; planted feet slide back at exactly the ground speed."""
    c = rig.c
    d = c.d
    g, legk, Af, Ab = gait_dims(c, st, kind)
    N, sig, run = g["N"], g["sigma"], kind == "run"
    base = stand(st)
    az = d["ankle_z"]
    Y0 = g["yaw"] + st["swagger"]
    lean, arm = g["lean"], g["arm"]
    td_toe, to_toe = g["td_toe"], g["to_toe"]
    lift = g["lift"] * legk * clamp(st["bob"], 0.8, 1.15)   # (even a shuffling gait clears the ground)
    bob = g["bob"] * legk * st["bob"]

    def stance_toe(v):
        """planted foot pitch at v = 0 (touchdown) .. 1 (toe-off): land, roll flat, peel the heel up"""
        r0 = g["heel"]
        if run:
            return td_toe * (1 - sstep(v / 0.3)) + to_toe * sstep((v - r0) / (1 - r0))
        return td_toe * (1 - sstep(v / 0.2)) + to_toe * sstep((v - r0) / (1 - r0))

    tab = foot_table(c)
    y_td, z_td = foot_roll(-Af, td_toe, tab)
    y_to, z_to = foot_roll(Ab, to_toe, tab)
    if run:   # swing: kick the heel up behind, drive the knee forward and high, reach, land flat
        sw_toe = Curve([(0.0, to_toe)] + [(k[0], k[4] if k[4] is not None else td_toe + 4.0) for k in RUN_SWING]
                       + [(1.0, td_toe)])
    else:
        sw_toe = Curve([(0.0, to_toe), (0.3, 12.0), (0.72, td_toe - 4.0), (1.0, td_toe)])

    def foot(u):
        """(dy, dz, toe) of one foot at its own phase u (0 = touchdown, sig = toe-off)."""
        if u < sig:
            v = u / sig
            toe = stance_toe(v)
            y, z = foot_roll(-Af + (Af + Ab) * v, toe, tab)
            return y, z, toe
        w = (u - sig) / (1 - sig)
        if run:
            e = sstep((w - 0.06) / 0.84)
            e = e * e * (3 - 2 * e)
            bump = math.sin(math.pi * clamp(w / 0.92) ** 0.62)
        else:
            e = w * w * w * (w * (6 * w - 15) + 10)       # smootherstep
            bump = math.sin(math.pi * w ** 0.8)
        y = y_to + (y_td - y_to) * e
        z = z_to + (z_td - z_to) * sstep(w) + lift * bump
        return y, z, sw_toe(w)

    # pelvis height: as high as the legs allow at touchdown / toe-off (walk: knees just short of
    # straight; run: knees still a little bent, so they flex and extend smoothly through the stance
    # instead of whipping out of / into the locked-straight singularity between two keys)
    reach = g["reach"] * (d["hip_z"] - d["ankle_z"])

    def hip_allowed(ph, y, z):
        hy = d["leg_x"] * math.sin(rad(-Y0 * math.cos(TAU * ph)))
        dy = y - hy
        return az + z + math.sqrt(max(1e-6, reach * reach - dy * dy)) - d["hip_z"]

    if run:
        def prof(ph):    # 0 at mid-stance (lowest), 1 in mid-flight (highest)
            return 0.5 - 0.5 * math.cos(2 * TAU * (ph - sig / 2))
    else:
        def prof(ph):    # 0 at the contacts (lowest), 1 at passing (highest); sharp bounce off the ground
            b = abs(math.sin(TAU * ph))
            return 0.65 * b + 0.35 * b * b
    roll = 4.0 * st["energy"]
    if run:
        z_lo = min(hip_allowed(0.0, y_td, z_td) - bob * prof(0.0), hip_allowed(sig, y_to, z_to) - bob * prof(sig))
        z_hi = z_lo + bob
    else:   # highest at passing, with the stance knee just short of straight (the hip rolls up a bit)
        z_hi = -(1.0 - 0.972) * (d["hip_z"] - az) - d["leg_x"] * math.sin(rad(roll))
        z_lo = min(z_hi - bob, (hip_allowed(0.0, y_td, z_td) - z_hi * prof(0.0)) / (1.0 - prof(0.0)),
                   (hip_allowed(sig, y_to, z_to) - z_hi * prof(sig)) / (1.0 - prof(sig)))

    def hips_off_at(ph):
        return (0.014 * st["energy"] * math.sin(TAU * (ph - 1 / N)), 0.0, z_lo + (z_hi - z_lo) * prof(ph))

    def hips_rot_at(ph):
        c1, s1 = cyc(ph)
        return (lean * 0.5 + 1.5 * math.cos(2 * TAU * ph), -Y0 * c1, -roll * s1)

    # Run swing leg in forward kinematics: thigh angle and knee bend are keyed curves, joined to the
    # exact planted-foot IK angles at toe-off and touchdown (stance keys on the same cyclic curves, so
    # the joints keep their pace through both), so the thigh turns smoothly and the ankle path never
    # folds through the hip. The swing keys are designed as ankle positions (RUN_SWING: heel kick
    # behind, foot tucked high under the hip, knee drive, reach, then a short drop onto the touchdown
    # spot with a little paw-back) and turned into joint angles by planar IK at their own phase: the
    # foot stays well off the ground until the last ~10% of the swing and never drags forward.
    L1u, L2u = d["hip_z"] - d["knee_z"], d["knee_z"] - d["ankle_z"]
    head = Vector((0.0, 0.0, d["pelvis_z"]))

    def hip_joint(ph, side):
        Rh = rotw(*hips_rot_at(ph))
        return head + Vector(hips_off_at(ph)) + Rh @ (Vector((side * d["leg_x"], 0.0, d["hip_z"])) - head)

    def leg_angles(J, y, z):
        """(thigh forward angle from straight down, knee bend) in degrees reaching ankle offset (y, z)."""
        dy, dz = y - J.y, d["ankle_z"] + z - J.z
        dist = clamp(math.hypot(dy, dz), abs(L1u - L2u) + 1e-4, (L1u + L2u) * 0.9999)
        al = math.acos(clamp((L1u * L1u + dist * dist - L2u * L2u) / (2 * L1u * dist), -1.0, 1.0))
        ka = math.pi - math.acos(clamp((L1u * L1u + L2u * L2u - dist * dist) / (2 * L1u * L2u), -1.0, 1.0))
        return math.degrees(math.atan2(-dy, -dz) + al), math.degrees(ka)

    def leg_fk(J, th, ka):
        t, k = rad(th), rad(th - ka)
        return (J.y - L1u * math.sin(t) - L2u * math.sin(k),
                J.z - L1u * math.cos(t) - L2u * math.cos(k) - d["ankle_z"])

    # the foot's lowest sole point relative to the flat foot's, pitched by t degrees (+ = toe down)
    fyz = [(p.y, p.z) for p in (Vector(v) - Vector((d["leg_x"], 0.0, az)) for ch in c.chunks
                                if ch[4] == ("foot", 1) for v in ch[0])]
    flat = min(z for _, z in fyz)

    def sole_drop(t):
        st_, ct = math.sin(rad(t)), math.cos(rad(t))
        return min(y * st_ + z * ct for y, z in fyz) - flat

    swing_fk = {}
    if run:
        E = st["energy"]
        for side in (1, -1):
            off = 0.0 if side > 0 else 0.5
            keys = []
            for v in (0.0, 0.34, 0.67, 1.0):          # planted: sampled from the exact stance IK
                uu = v * sig
                y, z, _ = foot(uu)
                keys.append((uu,) + leg_angles(hip_joint((uu - off) % 1.0, side), y, z))
            for w, kind_, a, b, t, h in RUN_SWING:
                uu = sig + w * (1 - sig)
                J = hip_joint((uu - off) % 1.0, side)
                if kind_ == "ik":
                    y = y_to + (y_td - y_to) * a              # 0 = toe-off spot, 1 = touchdown spot
                    z = z_to + (z_td - z_to) * w + lift * b   # above the line from toe-off to touchdown
                    keys.append((uu,) + leg_angles(J, y, z))
                    continue
                th, ka = a + 10.0 * (E - 1.0), b + 10.0 * (E - 1.0)
                # the sole keeps at least h x lift off the ground whatever the character's hip height:
                # a hip that sits low for its legs folds the knee more
                need = h * lift - sole_drop(t)
                lo_, hi_ = ka, 165.0
                if leg_fk(J, th, ka)[1] < need:
                    for _ in range(30):
                        mid = (lo_ + hi_) / 2
                        lo_, hi_ = (mid, hi_) if leg_fk(J, th, mid)[1] < need else (lo_, mid)
                    ka = hi_
                keys.append((uu, th, ka))
            swing_fk[side] = (Curve([(k[0], k[1]) for k in keys], 1.0), Curve([(k[0], k[2]) for k in keys], 1.0))

    def get(ch, f):
        ph = f / N
        if ch in ("legL", "legR"):
            side = 1 if ch == "legL" else -1
            u = (ph + (0.0 if side > 0 else 0.5)) % 1.0
            if run and u >= sig:
                thc, kac = swing_fk[side]
                y, z = leg_fk(hip_joint(ph, side), thc(u), kac(u))
                toe = sw_toe((u - sig) / (1 - sig))
            else:
                y, z, toe = foot(u)
            return (side * 0.006, y, z, toe, side * 5.0)
        bounce = abs(math.sin(TAU * ph))                    # 0 at contacts, 1 at passing
        bl = abs(math.sin(TAU * (ph - 2 / N)))
        if ch == "hips_off":
            return hips_off_at(ph)
        if ch == "hips":
            return hips_rot_at(ph)
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
                return (8.0 + a * fwd, ab + 4, 12.0, 84.0 - 14.0 * fwd)
            return (4.0 + a * fwd, ab, 8.0, 22.0 + 16.0 * fwd)
        if ch in ("handL", "handR"):
            side = 1 if ch == "handL" else -1
            fwd = -side * math.cos(TAU * (ph - 5 / N))
            return (-10.0 * fwd, 0.0, 0.0)
        if ch == "eyes":
            return (1.0, 1.0)
        return base[ch]
    return get


def clip_walk(rig, st):
    return GAIT["walk"]["N"], True, gait(rig, st, "walk")


def clip_run(rig, st):
    return GAIT["run"]["N"], True, gait(rig, st, "run")


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
        # (feet tucked a little at the top of the hop so the legs never have to over-stretch)
        "legL": [(0, b["legL"]), (6, b["legL"]), (10, (0.012, 0.012, 0.07, 30, 7)), (13, (0.014, 0.012, 0.076, 26, 7)),
                 (16, (0.01, 0.0, 0.004, 4, 7)), (17, b["legL"])],
        "legR": [(0, b["legR"]), (6, b["legR"]), (10, (-0.012, 0.012, 0.07, 30, -7)),
                 (13, (-0.014, 0.012, 0.076, 26, -7)), (16, (-0.01, 0.0, 0.004, 4, -7)), (17, b["legR"])],
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
    # grips are laid out relative to the right shoulder and scaled by arm length (preman's long arms
    # and wide shoulders); the pole leans a little to the left so it passes near the left shoulder
    k = (d["l_up"] + d["l_fore"]) / (DEF["l_up"] + DEF["l_fore"])

    def grips(x, y, z, el):
        e = rad(el)
        D = Vector((0.24, -math.cos(e), math.sin(e))).normalized()
        gR = Vector((-d["sh_x"] + (x + DEF["sh_x"] + 0.035) * k, (y + 0.015) * k, d["sh_z"] - (DEF["sh_z"] - z) * k))
        gR = fit_grip(gR, D, 0.11 * k)
        gL = gR + D * 0.11 * k
        return tuple(gR), tuple(gL), tuple(D)

    ok = 0.84 * (d["l_up"] + d["l_fore"]) + 0.8 * 0.036 * d["hand_k"]
    SR, SL = Vector((-d["sh_x"], 0.0, d["sh_z"])), Vector((d["sh_x"], 0.0, d["sh_z"]))

    def fit_grip(gR, D, t):
        """Nudge the right grip (least distance) until both fists are inside the arms' reach
        (wide-shouldered, short-armed characters): chest-frame geometry, the shoulders don't move."""
        def excess(p):
            return max((p - SR).length - ok, (p + D * t - SL).length - ok)
        if excess(gR) <= 0.0:
            return gR
        best, bkey = gR, (excess(gR), 0.0)
        for ix in range(-10, 11):
            for iy in range(-4, 13):
                for iz in range(-8, 9):
                    q = gR + Vector((ix, iy, iz)) * 0.01
                    e = excess(q)
                    key = (max(e, 0.0), (q - gR).length)
                    if key < bkey:
                        best, bkey = q, key
        return best
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
    tab = foot_table(rig.c)     # up on the balls of the feet for the thrust (heels rise, toes stay put)
    tipL = (0.02,) + foot_roll(-0.04, 22.0, tab) + (22.0, 10.0)
    tipR = (-0.02,) + foot_roll(0.04, 22.0, tab) + (22.0, -10.0)
    tr = one_shot(N, b, {
        "iksp": [(0, (1,)), (36, (1,))],
        "ikR": [(0, (1,)), (36, (1,))], "ikL": [(0, (1,)), (36, (1,))],
        "gripwR": [(0, (1,)), (36, (1,))], "gripwL": [(0, (1,)), (36, (1,))],
        "iktR": ktR, "iktL": ktL, "gripR": kg, "gripL": kg,
        "polefollow": [(0, (1,)), (36, (1,))], "poled": [(0, (0.11 * k,)), (36, (0.11 * k,))],
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
        "legL": [(0, b["legL"]), (7, (0.02, -0.04, 0.0, 0, 10)), (15, tipL), (20, tipL),
                 (23, (0.02, -0.04, 0.0, 0, 10)), (30, (0.02, -0.04, 0.0, 0, 10))],
        "legR": [(0, b["legR"]), (7, (-0.02, 0.04, 0.0, 0, -10)), (15, tipR), (20, tipR),
                 (23, (-0.02, 0.04, 0.0, 0, -10)), (30, (-0.02, 0.04, 0.0, 0, -10))],
        "jaw": [(0, (1,)), (21, (1,)), (23, (2.4,)), (27, (1.6,)), (31, (1,))],
        "eyes": [(0, (1, 1)), (21, (1, 1)), (23, (0.45, 0.45)), (27, (0.6, 0.6)), (31, (1, 1))],
        "brow": [(0, (0, 0)), (10, (0, 0.004)), (21, (0, 0.004)), (23, (8, -0.003)), (29, (0, 0))],
    })
    return N, False, tr


def stand_hand(rig, st, side, arm=None, hand=None):
    """Fist centre, blade axis (hand local +Z) and elbow pole direction of the neutral stance (or of
    the FK arm / hand angles given), in the chest's rest frame (unscaled): IK arm clips start and end
    exactly on the FK stance and can pass through FK-designed poses."""
    b = dict(stand(st))
    x = sfx(side)
    if arm is not None:
        b["arm" + x] = arm
    if hand is not None:
        b["hand" + x] = hand
    rig.solve(spec_from(lambda ch, f: b[ch], 0))
    W = rig.W
    Ci = rig.rest["chest"] @ W["chest"].inverted()
    Mh = W["hand_" + x]
    fist = Ci @ (Mh @ Vector((0.0, 0.036 * rig.S * rig.c.d["hand_k"], 0.0)))
    G = Ci.to_3x3() @ (Mh.to_3x3() @ Vector((0.0, 0.0, 1.0)))
    Sh, El, Wr = (Ci @ W[n + x].translation for n in ("upperarm_", "forearm_", "hand_"))
    u = (Wr - Sh).normalized()
    pole = (El - Sh) - u * (El - Sh).dot(u)
    return tuple(fist / rig.S), tuple(G.normalized()), tuple(pole.normalized())


def clip_chop(rig, st):
    """Parang (machete) chop with the right hand: cock it high out over the right shoulder with the
    blade pointing up and back (clear of the head, the widest hat brims and the back), then a fast
    swing down the right side and forward, the blade slicing forward-down at the bushes in front,
    follow through, recover. The right arm is IK all through (fist + blade direction = hand_R
    local +Z, where the game puts the blade, in the chest frame so the torso twist adds to the
    swing); it starts and ends exactly on the neutral stance."""
    N = 24
    b = stand(st)
    d = rig.c.d
    hc, hh = b["chest"][0], b["head"][0]
    k = (d["l_up"] + d["l_fore"]) / (DEF["l_up"] + DEF["l_fore"])
    shR = Vector((-d["sh_x"], 0.0, d["sh_z"]))
    f0, g0, p0 = stand_hand(rig, st, -1)
    fk = {f: stand_hand(rig, st, -1, arm, hand) for f, arm, hand in
          ((12, (72, 6, 18, 22), (-42, 0, 0)), (14, (64, -16, 24, 26), (-52, 0, 0)), (18, (30, 8, 10, 36), (-10, 0, 0)))}

    def fist(x, y, z):      # offset from the right shoulder (x < 0 = outward), scaled by arm length
        return tuple(shR + Vector((x, y, z)) * k)
    tr = one_shot(N, b, {
        # IK all through the swing: the wind-up poses are designed as fist + blade direction, the
        # strike and follow-through are the fist / blade of keyed FK arm poses
        "iksp": [(0, (1,)), (24, (1,))], "iksoft": [(0, (0.985,)), (24, (0.985,))],
        "ikR": [(0, (0,)), (3, (1,)), (19, (1,)), (23, (0,))], "gripwR": [(0, (0,)), (3, (1,)), (19, (1,)), (23, (0,))],
        # (the fist leaves and comes back out to the side, clear of hip bags and sashes)
        "iktR": [(0, f0), (2, fist(-0.1, -0.03, -0.12)), (3, fist(-0.11, -0.02, 0.0)), (6, fist(-0.135, 0.02, 0.085)),
                 (9, fist(-0.135, 0.035, 0.095)), (11, fist(-0.1, -0.1, 0.02))] + [(f, fk[f][0]) for f in (12, 14, 18)] +
                [(20, fist(-0.09, -0.07, -0.17)), (22, f0)],
        "gripR": [(0, g0), (3, (-0.75, -0.35, 0.55)), (6, (-0.68, 0.42, 0.6)), (9, (-0.64, 0.52, 0.56)),
                  (11, (-0.68, -0.22, 0.7))] + [(f, fk[f][1]) for f in (12, 14, 18)] + [(22, g0)],
        "ikpR": [(0, p0), (4, (-0.6, -0.2, -0.8)), (9, (-0.6, -0.1, -0.8))] + [(f, fk[f][2]) for f in (12, 14, 18)] +
                [(22, p0)],
        "armL": [(0, b["armL"]), (6, (12, 30, 6, 42)), (9, (14, 32, 6, 44)), (12, (-6, 26, 6, 30)),
                 (15, (-4, 24, 6, 28)), (20, (4, 14, 6, 22))],
        "hips_off": [(0, b["hips_off"]), (6, (-0.01, 0.006, -0.012)), (9, (-0.011, 0.007, -0.014)),
                     (12, (0.01, -0.008, -0.032)), (14, (0.011, -0.009, -0.034)), (19, (0.003, -0.002, -0.012))],
        "hips": [(0, b["hips"]), (6, (-1, -9, 1)), (9, (-1, -10, 1)), (12, (3, 9, -1)), (14, (3, 11, -1)),
                 (19, (1, 3, 0))],
        "spine": [(0, b["spine"]), (7, (b["spine"][0], -6, 0)), (10, (b["spine"][0], -7, 0)),
                  (13, (b["spine"][0] + 2, 7, 0)), (15, (b["spine"][0] + 3, 8, 0)), (20, (b["spine"][0], 2, 0))],
        "chest": [(0, b["chest"]), (7, (hc - 3, -16, 3)), (10, (hc - 3, -17, 3)), (13, (hc + 4, 16, -3)),
                  (15, (hc + 5, 20, -3)), (20, (hc + 1, 4, 0))],
        "head": [(0, b["head"]), (8, (hh + 3, 9, 0)), (10, (hh + 3, 9, 0)), (14, (hh + 3, -6, 0)),
                 (17, (hh + 3, -8, 0)), (21, (hh + 1, -2, 0))],
        "legL": [(0, b["legL"]), (5, (0.012, -0.03, 0, 0, 12)), (19, (0.012, -0.03, 0, 0, 12))],
        "legR": [(0, b["legR"]), (5, (-0.014, 0.03, 0, 0, -12)), (19, (-0.014, 0.03, 0, 0, -12))],
        "jaw": [(0, (1,)), (9, (1,)), (12, (2.2,)), (16, (1.4,)), (20, (1,))],
        "eyes": [(0, (1, 1)), (8, (1, 1)), (11, (0.5, 0.5)), (16, (0.7, 0.7)), (20, (1, 1))],
        "brow": [(0, (0, 0)), (6, (6, -0.004)), (16, (6, -0.004)), (21, (0, 0))],
    })
    return N, False, tr


def plant_lean(d, st, drop, fist_z, reach_xy):
    """Torso lean scale so the shoulders come down to where the fists reach the soil."""
    segs = (d["spine_z"] - d["pelvis_z"], d["chest_z"] - d["spine_z"], d["sh_z"] - d["chest_z"])
    base = (0.0, st["stoop"] * 0.4, st["stoop"] * 0.6 + st["chest"])
    reach = 0.86 * (d["l_up"] + d["l_fore"]) + 0.036 * d["hand_k"]
    want = fist_z + math.sqrt(max(1e-4, reach * reach - reach_xy * reach_xy))

    def sh_z(k):
        z, a = d["pelvis_z"] + drop, 0.0
        for L, b0, p in zip(segs, base, PLANT_LEAN):
            a += b0 + k * p
            z += L * math.cos(rad(a))
        return z
    lo, hi = 0.4, 1.7
    for _ in range(30):
        mid = (lo + hi) / 2
        if sh_z(mid) > want:
            lo = mid
        else:
            hi = mid
    return hi


PLANT_LEAN = (26.0, 19.0, 17.0)   # hips, spine, chest pitch (deg) of the default character's dig pose
PLANT_FIST = 0.058                # fist centre height when the knuckles touch the soil (x hand size)


def clip_plant(rig, st):
    """Step the left foot out, kneel on the right knee sitting back towards the heel, bend forward
    from the hips, dig twice with the right hand, set the seedling in with the left, pat the soil with
    both hands, stand back up with a little stretch. The fists really reach the soil (the arm targets
    are placed relative to the shoulders at a fixed height above the ground) and the head stays
    fairly upright, so the arms show past a wide hat brim from the 45 deg game camera."""
    N = 36
    b = stand(st)
    c = rig.c
    d = c.d
    kz = (d["hip_z"] - d["ankle_z"]) / (DEF["hip_z"] - DEF["ankle_z"])
    hk = d["hand_k"]
    G = PLANT_FIST * hk
    GL = G + st.get("plant_lift_L", 0.0)      # (petugas keeps the clipboard in the left hand off the soil)
    drop = -0.2 * kz
    back = 0.03 * kz
    lam = plant_lean(d, st, drop, G, 0.035)
    lh, ls, lc = (lam * v for v in PLANT_LEAN)
    # kneeling right leg: knee on the ground, shin back to a toe-down foot under the hip
    tab = foot_table(c)
    toe_k = 55.0
    z_hip = d["hip_z"] + drop
    z_knee = d["knee_r"] * 1.0
    Lt, Ls = d["hip_z"] - d["knee_z"], d["knee_z"] - d["ankle_z"]
    y_knee = back - math.sqrt(max(1e-6, Lt * Lt - (z_hip - z_knee) ** 2))
    z_ank = d["ankle_z"] + tab[int(toe_k)][1]
    y_ank = y_knee + math.sqrt(max(1e-6, Ls * Ls - (z_ank - z_knee) ** 2))
    kneel_r = (-0.012 * kz, y_ank, tab[int(toe_k)][1], toe_k, -10.0)
    foot_l = (0.035 * kz, -0.085 * kz, 0.0, 0.0, 26.0)
    hc, hs, hh, hn = b["chest"][0], b["spine"][0], b["head"][0], b["neck"][0]
    # the head stays fairly upright (~4-10 deg net pitch, the neck taking part of the bend) whatever the
    # torso does: the hat brim then stays level and the hands show below it from the 45 deg camera
    tot = lh + ls + lc + (hs + hc)
    neck_p = hn - 0.3 * (tot - 4.0)
    head_p = 4.0 - tot - neck_p
    bob = 0.006 * kz

    def dz(z):
        return (0.0, back, drop + z)
    tr = one_shot(N, b, {
        "hips_off": [(0, b["hips_off"]), (3, (0.012, -0.004, -0.02)), (6, (0.006, back * 0.6, drop * 0.75)),
                     (9, dz(-0.004)), (10, dz(-bob)), (12, dz(0.0)), (14, dz(-bob)), (16, dz(0.0)),
                     (20, dz(-bob * 0.5)), (22, dz(-bob)), (24, dz(-bob)), (26, dz(0.0)),
                     (29, (0.004, back * 0.4, drop * 0.45)), (32, (0.0, 0.0, -0.001)), (35, (0, 0, -0.007))],
        "hips": [(0, b["hips"]), (3, (3, 4, -2)), (6, (lh * 0.7, -4, 0)), (9, (lh, -8, 0)), (24, (lh, -8, 0)),
                 (28, (lh * 0.5, -4, 0)), (32, (-4, 0, 0))],
        "spine": [(0, b["spine"]), (7, (hs + ls * 0.6, -2, 0)), (10, (hs + ls, -3, 0)), (25, (hs + ls, -3, 0)),
                  (29, (hs + ls * 0.4, -1, 0)), (33, (hs - 3, 0, 0))],
        "chest": [(0, b["chest"]), (7, (hc + lc * 0.5, -2, 0)), (10, (hc + lc, -5, -2)), (12, (hc + lc - 3, -3, -2)),
                  (14, (hc + lc, -6, -2)), (16, (hc + lc - 3, -2, 0)), (19, (hc + lc, 6, 3)),
                  (22, (hc + lc + 1, 0, 0)), (24, (hc + lc + 1, 0, 0)), (27, (hc + lc * 0.5, 0, 0)),
                  (31, (hc - 8, 0, 0)), (34, (hc + 1, 0, 0))],
        "neck": [(0, b["neck"]), (8, (hn + (neck_p - hn) * 0.6, 0, 0)), (11, (neck_p, -2, 0)), (25, (neck_p, 2, 0)),
                 (30, (hn, 0, 0)), (33, (hn + 2, 0, 0))],
        "head": [(0, b["head"]), (4, (hh + 4, 0, 0)), (9, (head_p + 6, -6, 3)), (12, (head_p + 1, -9, 4)),
                 (16, (head_p + 4, -7, 3)), (20, (head_p + 2, 7, -3)), (24, (head_p + 4, 2, 0)),
                 (28, (hh + 2, 0, 0)), (32, (hh - 10, 0, 0))],
        "kneeout": [(0, (0.12, 0.12)), (4, (0.9, 0.12)), (28, (0.9, 0.12))],
        "legL": [(0, b["legL"]), (3, (0.02 * kz, -0.045 * kz, 0.035 * kz, -6, 16)), (6, foot_l), (26, foot_l),
                 (29, (0.02 * kz, -0.05 * kz, 0.012, 0, 16)), (31, (0.012, -0.015, 0.0, 0, 9))],
        "legR": [(0, b["legR"]), (4, (-0.01, 0.04 * kz, tab[20][1] + 0.004, 20, -8)), (8, kneel_r), (25, kneel_r),
                 (28, (-0.01, y_ank * 0.6, tab[34][1] + 0.006, 34, -8)), (31, (-0.01, 0.01, tab[4][1], 4, -7))],
        "ikgnd": [(0, (1,)), (36, (1,))],
        "ikR": [(0, (0,)), (4, (0,)), (9, (1,)), (25, (1,)), (29, (0.0,))],
        "iktR": [(0, (0.0, -0.06, 0.3)), (7, (0.0, -0.05, G + 0.06)), (10, (0.0, -0.035, G)),
                 (12, (-0.005, 0.0, G + 0.035)), (14, (0.0, -0.04, G)), (16, (-0.005, 0.0, G + 0.04)),
                 (19, (-0.01, -0.02, G + 0.05)), (22, (0.015, -0.035, G)), (23, (0.015, -0.035, G + 0.025)),
                 (24, (0.015, -0.035, G)), (26, (0.0, -0.02, G + 0.06))],
        "ikL": [(0, (0,)), (4, (0,)), (9, (1,)), (26, (1,)), (30, (0,))],
        "iktL": [(0, (0.0, -0.06, 0.3)), (8, (0.02, -0.06, GL + 0.09)), (15, (0.02, -0.06, GL + 0.08)),
                 (18, (0.035, -0.04, GL + 0.03)), (20, (0.035, -0.035, GL + 0.002)), (21, (0.035, -0.035, GL)),
                 (22, (0.03, -0.035, GL + 0.02)), (23, (0.03, -0.035, GL)), (24, (0.03, -0.035, GL + 0.02)),
                 (25, (0.03, -0.035, GL)), (27, (0.02, -0.03, GL + 0.06))],
        "armR": [(0, b["armR"]), (7, (40, 16, 10, 40)), (25, (40, 16, 10, 40))],
        "armL": [(0, b["armL"]), (7, (40, 16, 10, 40)), (26, (40, 16, 10, 40))],
        # wrists stay nearly straight while the fists are on the soil (the IK aims the fist, not the
        # wrist), with a small scoop on each dig
        "handR": [(0, b["handR"]), (8, (6, 0, 0)), (10, (-4, 0, 0)), (12, (14, 0, 0)), (14, (-4, 0, 0)),
                  (16, (14, 0, 0)), (22, (0, 0, 0)), (26, (4, 0, 0))],
        "handL": [(0, b["handL"]), (8, (10, 0, 0)), (18, (6, 0, 0)), (21, (-2, 0, 0)), (25, (0, 0, 0)),
                  (28, b["handL"])],
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


LOC_BONES = ("hips", "extra_brow_L", "extra_brow_R")                        # translated (pelvis bob, brow lift)
SCALE_BONES = ("extra_eye_L", "extra_eye_R", "extra_mouth", "extra_jaw")   # scaled only (blink, mouth)


CHECKS = {}    # name -> {clip: numbers} filled by the automated clip checks (printed in the summary)
KNEE_MAX = 25.0        # deg: walk/run thigh direction change per frame and sideways knee angle
BLADE_MIN = 0.015      # m: parang blade clearance from the body (right arm excluded) over the chop
FIST_SINK_MAX = 0.008  # m: how deep the right fist may sink into the body in the chop


def leg_metrics(legs_fk, loop):
    """(max thigh-direction change between consecutive frames, max sideways knee angle) in degrees
    over both legs. Sideways knee = how far the knee's offset from the hip-ankle line leans out of
    the sagittal (world YZ) plane - a flared or flipping knee shows up here."""
    step = side_ = 0.0
    for x in ("L", "R"):
        dirs = []
        for row in legs_fk:
            J, E, A = row["thigh_" + x], row["shin_" + x], row["foot_" + x]
            dirs.append((E - J).normalized())
            u = (A - J).normalized()
            k = (E - J) - u * (E - J).dot(u)
            if k.length > 0.004 * (E - J).length:
                side_ = max(side_, math.degrees(math.asin(min(1.0, abs(k.normalized().x)))))
        for a, b in zip(dirs, dirs[1:]):
            step = max(step, math.degrees(a.angle(b, 0.0)))
    return step, side_


def cloth_layer(rule, mname, skin):
    """Layer of a chunk for the clipping check: bare legs < trouser legs < pelvis/skirt < top < shawl.
    None = not checked (head, arms, feet, accessories)."""
    kind = rule[0] if isinstance(rule, tuple) else rule
    if kind == "leg":
        return 1.0 if mname == skin else 1.5
    if kind in ("pelvis", "skirt"):
        return 2.0
    if kind == "torso":
        return None if mname == skin else 3.0
    if kind == "cape":
        return 4.0
    return None


def layer_check(c, body, set_pose, frames, near=0.035, far=0.08, verbose=False):
    """Cloth clipping check on the skinned mesh: every vertex of an inner layer that is hidden inside
    an outer layer at rest (a ray along its normal leaves through an outer surface within `near`)
    must still be hidden in the pose (within `far`). set_pose(frame) poses the rig.
    Returns {frame: (exposed count, {material: count})}."""
    from mathutils.bvhtree import BVHTree
    me = body.data
    vlayer = [None] * len(me.vertices)
    vmat = [None] * len(me.vertices)
    for (a, b, rule, mname) in c.vranges:
        L = cloth_layer(rule, mname, c.skin)
        for i in range(a, b):
            vlayer[i], vmat[i] = L, mname
    polys = [tuple(p.vertices) for p in me.polygons]
    play = [vlayer[p[0]] for p in polys]            # a face lies in one chunk
    levels = sorted({L for L in vlayer if L is not None})

    fmat_of = [vmat[p[0]] for p in polys]
    L_faces = {}

    def trees(co):
        out = {}
        for L in levels:
            idx = [k for k, pl in enumerate(play) if pl is not None and pl > L]
            out[L] = BVHTree.FromPolygons(co, [polys[k] for k in idx], all_triangles=False) if idx else None
            L_faces[id(out[L])] = idx
        return out

    def covered(tr, p, n, dist):
        if tr is None:
            return False
        hit = tr.ray_cast(p, n, dist)
        return hit[0] is not None and hit[1].dot(n) > 0.0

    def same_mat(tr, p, m):
        """poking through a same-coloured layer (trouser leg through the trousers) is invisible"""
        hit = tr.find_nearest(p, 0.008 * c.S)
        return hit[0] is not None and fmat_of[L_faces[id(tr)][hit[2]]] == m

    co0 = [v.co.copy() for v in me.vertices]
    tr0 = trees(co0)
    down = Vector((0.0, 0.0, -0.7))
    # hidden at rest = covered along the normal and along the normal tipped down (so vertices
    # peeking out right at a hem line, which are visible anyway, are not counted)
    test = [i for i, L in enumerate(vlayer) if L is not None and L in tr0 and
            covered(tr0[L], co0[i], me.vertices[i].normal, near * c.S) and
            covered(tr0[L], co0[i], (me.vertices[i].normal + down).normalized(), near * c.S)]
    res = {}
    for f in frames:
        set_pose(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        em = ev.to_mesh()
        co = [v.co.copy() for v in em.vertices]
        nr = [v.normal.copy() for v in em.vertices]
        ev.to_mesh_clear()
        tr = trees(co)
        bad = {}
        for i in test:
            if not covered(tr[vlayer[i]], co[i], nr[i], far * c.S) and \
                    not same_mat(tr[vlayer[i]], co[i], vmat[i]):
                bad[vmat[i]] = bad.get(vmat[i], 0) + 1
                if verbose:
                    print("    exposed f%d v%d %s L%.1f rest=(%.3f %.3f %.3f)" % ((f, i, vmat[i], vlayer[i]) +
                                                                            tuple(co0[i] / c.S)))
        res[f] = (sum(bad.values()), bad)
    return res


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
        legs_fk = []
        for f in range(N + 1):
            basis = rig.solve(spec(f))
            legs_fk.append({b: rig.W[b].translation.copy() for b in
                            ("thigh_L", "shin_L", "foot_L", "thigh_R", "shin_R", "foot_R")})
            row = {}
            for pb in ob.pose.bones:
                loc, q, sc = basis[pb.name]
                e = q.to_euler("XYZ", prev[pb.name]) if prev[pb.name] else q.to_euler("XYZ")
                prev[pb.name] = e
                row[pb.name] = (loc, e, sc)
            frames[f] = row
        # first frame: keyframe_insert creates the action slot + F-curves; the rest is bulk-filled.
        # Only channels some clip really uses are keyed (every clip keys the same set, so Godot
        # blends like with like; the rest stay at the rest pose and are not exported).
        for pb in ob.pose.bones:
            loc, e, sc = frames[0][pb.name]
            pb.location, pb.rotation_euler, pb.scale = loc, e, sc
            if pb.name not in SCALE_BONES:
                pb.keyframe_insert("rotation_euler", frame=0, group=pb.name)
            if pb.name in LOC_BONES:
                pb.keyframe_insert("location", frame=0, group=pb.name)
            if pb.name in SCALE_BONES:
                pb.keyframe_insert("scale", frame=0, group=pb.name)
        if loop:   # the solver's own last frame must already be the first one (seamless loop)
            rot_d = max(quat_angle(frames[0][b][1].to_quaternion(), frames[N][b][1].to_quaternion())
                        for b in frames[0])
            loc_d = max((frames[0][b][0] - frames[N][b][0]).length for b in frames[0]) / rig.S
            rig.seams[name] = (rot_d, loc_d)
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
        if name in ("walk", "run"):
            step, side_ = leg_metrics(legs_fk, loop)
            print(f"  [check] {rig.c.name}/{name}: thigh turn per frame max {step:.1f} deg, "
                  f"sideways knee max {side_:.1f} deg")
            if max(step, side_) > KNEE_MAX:
                fail(rig.c.name, f"{name}: knee flare / thigh turn over {KNEE_MAX:.0f} deg "
                                 f"(thigh {step:.1f} deg per frame, sideways knee {side_:.1f} deg)")
            CHECKS.setdefault(rig.c.name, {})[name] = (round(step, 1), round(side_, 1))
        acts[name] = act
    ob.animation_data.action = acts.get("idle")
    return acts


# --------------------------------------------------------------------------- animation: motion checks
# Automated checks on the baked clips, evaluated from the F-curves the exporter samples (so they see
# what the game plays), plus a check of the exported GLB's rotation keys themselves. A failed check
# prints "!! FAIL" and is collected in FAILS: build_one() then does not export that character (unless
# --allow-fail) and main() ends with exit status 1.
JUMP_MAX = 30.0       # deg: most any bone may turn in one 1/60 s step (the game draws at 60 fps)
SLIDE_MAX = 0.10      # planted foot: mean speed error of its sole contact point / ground speed
SWING_EARLY = 0.06    # share of a swing at its start in which the toe is still peeling off the ground
SWING_LATE = 0.90     # share of a swing after which the foot may come down for the touchdown
CLEAR = 0.008         # m (x scale): a sole point closer than this to the ground is touching it
                      # (the game's foot probe counts a sole within 8 mm of the floor as planted)
SEAM_DEG, SEAM_M = 0.5, 0.0005   # loops: largest bone turn / offset between the last and first frame
FAILS = []            # (character, message)


def fail(name, msg):
    FAILS.append((name, msg))
    print(f"  !! FAIL {name}: {msg}")


def quat_angle(a, b):
    """Angle (deg) between two rotations, whatever the quaternions' hemispheres."""
    return math.degrees(2.0 * math.acos(min(1.0, abs(a.dot(b)))))


class Sampler:
    """A baked action as the game plays it: the exporter samples the F-curves at every frame and
    writes LINEAR glTF channels, so between two frames the rotations slerp and locations / scales
    lerp. Evaluated at any (fractional) frame (cyclic clips wrap), with forward kinematics to
    armature space like Blender's pose."""

    def __init__(self, rig, act):
        self.rig = rig
        self.fc = {}
        for fc in act.fcurves:
            b = fc.data_path.split('"')[1]
            prop = fc.data_path.rsplit(".", 1)[1]
            self.fc.setdefault(b, {}).setdefault(prop, [None, None, None])[fc.array_index] = fc

        def depth(n):
            return 0 if rig.par[n] is None else 1 + depth(rig.par[n])
        self.order = sorted(rig.rest, key=depth)
        self.rest_inv = {b: m.inverted() for b, m in rig.rest.items()}
        self.keys = {}

    def key(self, f):
        """{bone: (location, quaternion, scale)} of the exported key at integer frame f."""
        if f not in self.keys:
            out = {}
            for b in self.order:
                ch = self.fc.get(b, {})

                def val(prop, dflt):
                    fcs = ch.get(prop)
                    return dflt if not fcs else [fcs[i].evaluate(f) if fcs[i] else dflt[i] for i in range(3)]
                out[b] = (Vector(val("location", (0.0, 0.0, 0.0))),
                          Euler(val("rotation_euler", (0.0, 0.0, 0.0)), "XYZ").to_quaternion(),
                          Vector(val("scale", (1.0, 1.0, 1.0))))
            self.keys[f] = out
        return self.keys[f]

    def local(self, f):
        """{bone: (location, rotation quaternion, scale)} at frame f (keys interpolated like the game)."""
        f0 = math.floor(f + 1e-9)
        t = f - f0
        A = self.key(f0)
        if t < 1e-9:
            return A
        B = self.key(f0 + 1)
        out = {}
        for b in self.order:
            (la, qa, sa), (lb, qb, sb) = A[b], B[b]
            if qa.dot(qb) < 0.0:
                qb = -qb
            out[b] = (la.lerp(lb, t), qa.slerp(qb, t), sa.lerp(sb, t))
        return out

    def world(self, f):
        """{bone: armature-space pose matrix} at frame f."""
        W = {}
        for b, (loc, q, sc) in self.local(f).items():
            m = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ Matrix.Diagonal(tuple(sc) + (1.0,))
            p = self.rig.par[b]
            W[b] = (W[p] @ self.rig.rel[b] if p else self.rig.rest[b]) @ m
        return W


def rotation_steps(rig, act, N, loop, step=0.5):
    """{bone: (largest local rotation in one step, frame)} over the clip, `step` frames apart
    (0.5 = 1/60 s); loops are also checked across the seam."""
    smp = Sampler(rig, act)
    worst, prev = {}, None
    n = int(round(N / step)) + (1 if loop else 0)
    for i in range(n + 1):
        f = i * step
        cur = smp.local(f)
        if prev is not None:
            for b, (_, q, _) in cur.items():
                a = quat_angle(prev[b][1], q)
                if a > worst.get(b, (0.0, 0.0))[0]:
                    worst[b] = (a, f)
        prev = cur
    return worst


def seam_kink(act, N):
    """Loops: how much more the keyed channels change pace across the seam than anywhere inside the
    cycle (largest second difference at the seam minus the largest inside, degrees / units x 100)."""
    inside = seam = 0.0
    for fc in act.fcurves:
        k = 100.0 if "location" in fc.data_path else (math.degrees(1.0) if "rotation" in fc.data_path else 10.0)
        v = [fc.evaluate(f) for f in range(N + 1)]
        v[N] = v[0]
        dd = [abs(v[(i + 1) % N] - 2 * v[i] + v[(i - 1) % N]) * k for i in range(N)]
        seam = max(seam, dd[0])
        inside = max([inside] + dd[1:])
    return seam - inside


def foot_points(body, x):
    """Rest positions and bone weights of the vertices weighted mostly to foot_<x> (the sole the
    game's foot probe tracks)."""
    names = {g.index: g.name for g in body.vertex_groups}
    out = []
    for v in body.data.vertices:
        ws = [(names[g.group], g.weight) for g in v.groups if g.weight > 0.0]
        if dict(ws).get("foot_" + x, 0.0) >= 0.5:
            out.append((v.co.copy(), ws))
    return out


def gait_check(c, st, rig, body, act, kind, step=0.25, win=4):
    """Walk/run feet on the ground, sampled every `step` frames at 1x playback while the ground moves
    back at the exported ground speed (gait_speed):
      slide   - planted foot (its phase in the stance share): the lowest sole point tracked over `win`
                steps (one frame, about one game frame at the game's ~2x playback, starting between keys
                too), |its speed - ground speed| / ground speed, mean and 90th percentile
      lift    - swinging foot: lowest sole point above the ground between SWING_EARLY and SWING_LATE
                of the swing (min), and the share of the swing after which it is back within CLEAR
      band    - the game measures the stride from the ankle while it is in the lowest quarter of its
                height range: share of mid-swing (0.15..0.75, before the foot comes down) spent there
                (must be 0)
      ankle   - planted ankle's mean backward speed, m/s at 1x (moves back under the hips)"""
    g = GAIT[kind]
    N, sig = g["N"], g["sigma"]
    v = gait_speed(c, st, kind)[0]
    smp = Sampler(rig, act)
    feet = {x: foot_points(body, x) for x in ("L", "R")}
    n = int(round(N / step))
    dt = step / FPS
    rows = {x: [] for x in feet}
    for i in range(n + 1):
        W = smp.world(i * step)
        M = {b: W[b] @ smp.rest_inv[b] for b in W}
        for x, pts in feet.items():
            ps = []
            for co, ws in pts:
                p = Vector()
                for b, w in ws:
                    p += (M[b] @ co) * w
                ps.append(p)
            rows[x].append((ps, W["foot_" + x].translation.copy()))
    S = c.S
    res = dict(slide=0.0, slide_p90=0.0, lift=9.0, down=1.0, band=0.0, ankle=0.0, stance_h=0.0)
    slides, lifts, heights, ank_v = [], [], [], []
    for x, off in (("L", 0.0), ("R", 0.5)):
        R_ = rows[x]
        ank_z = [r[1].z for r in R_]
        lo, hi = min(ank_z), max(ank_z)
        band = lo + 0.25 * (hi - lo)
        in_band = n_mid = 0
        for i in range(n):
            u0 = (i * step / N + off) % 1.0
            u1 = u0 + win * step / N
            P0, P1 = R_[i][0], R_[(i + win) % n][0]
            k = min(range(len(P0)), key=lambda j: P0[j].z)
            if u1 <= sig + 1e-9:
                d = (P1[k] - P0[k]) / (win * dt)
                slides.append(math.hypot(d.x, d.y - v) / v)
                heights.append(P0[k].z)
                ank_v.append((R_[(i + win) % n][1].y - R_[i][1].y) / (win * dt))
            elif u0 >= sig:
                w = (u0 - sig) / (1.0 - sig)
                lifts.append((w, P0[k].z))
                if 0.15 <= w <= 0.75:
                    n_mid += 1
                    in_band += R_[i][1].z < band
        res["band"] = max(res["band"], in_band / max(1, n_mid))
    ground = sorted(heights)[len(heights) // 2]
    slides.sort()
    res["slide"] = sum(slides) / len(slides)
    res["slide_p90"] = slides[int(0.9 * len(slides))]
    res["stance_h"] = (max(heights) - ground) / S
    res["ankle"] = sum(ank_v) / len(ank_v)
    mid = [h - ground for (w, h) in lifts if SWING_EARLY <= w <= SWING_LATE]
    res["lift"] = min(mid) / S
    touching = [w for (w, h) in lifts if h - ground < CLEAR * S and w > SWING_EARLY]
    res["down"] = min(touching) if touching else 1.0
    res["v"] = v
    return res


def motion_checks(c, st, rig, body, acts):
    """Rotation jumps (every clip, every bone), loop seams, and the walk/run feet (see gait_check)."""
    name = c.name
    out = {}
    jumps = {}
    for clip, act in acts.items():
        N = int(act.frame_range[1])
        loop = clip in LOOPS
        w = rotation_steps(rig, act, N, loop)
        b, (a, f) = max(w.items(), key=lambda kv: kv[1][0])
        jumps[clip] = round(a, 1)
        if a > JUMP_MAX:
            bad = ", ".join(f"{bb} {aa:.0f} deg @{ff / FPS:.3f}s" for bb, (aa, ff) in
                            sorted(w.items(), key=lambda kv: -kv[1][0]) if aa > JUMP_MAX)
            fail(name, f"{clip}: bones turn more than {JUMP_MAX:.0f} deg in 1/60 s: {bad}")
        if loop:
            rd, ld = rig.seams.get(clip, (0.0, 0.0))
            kink = seam_kink(act, N)
            if rd > SEAM_DEG or ld > SEAM_M or kink > 3.0:
                fail(name, f"{clip}: loop seam mismatch (last vs first frame {rd:.2f} deg / {ld * 1000:.1f} mm, "
                           f"pace change {kink:.1f} over the inside)")
    out["jump"] = jumps
    out["seam"] = {k: round(v[0], 2) for k, v in rig.seams.items()}
    for kind in ("walk", "run"):
        r = gait_check(c, st, rig, body, acts[kind], kind)
        out[kind + "_feet"] = r
        print(f"  [check] {name}/{kind}: planted slide mean {100 * r['slide']:.1f}% p90 {100 * r['slide_p90']:.1f}% "
              f"(ground {r['v']:.2f} m/s at 1x, ankle back {r['ankle']:.2f} m/s, sole lift in stance "
              f"{r['stance_h'] * 1000:.1f} mm), swing lift min {r['lift'] * 1000:.0f} mm "
              f"(w {SWING_EARLY}..{SWING_LATE}), down at {100 * r['down']:.0f}% of swing, "
              f"ankle in stance band {100 * r['band']:.0f}% of mid-swing")
        if r["slide"] > SLIDE_MAX:
            fail(name, f"{kind}: planted foot slides {100 * r['slide']:.0f}% of the ground speed (max {100 * SLIDE_MAX:.0f}%)")
        if r["lift"] < CLEAR:
            fail(name, f"{kind}: swinging foot touches the ground at {100 * r['down']:.0f}% of its swing "
                       f"(lowest {r['lift'] * 1000:.0f} mm before {100 * SWING_LATE:.0f}%)")
        if r["band"] > 0.0:
            fail(name, f"{kind}: ankle in the stance height band for {100 * r['band']:.0f}% of mid-swing")
        if r["ankle"] <= 0.0:
            fail(name, f"{kind}: planted ankle does not move back ({r['ankle']:.2f} m/s)")
    print(f"  [check] {name}: most turn per 1/60 s by clip {jumps} (max {JUMP_MAX:.0f}), loop seams {out['seam']} deg")
    CHECKS.setdefault(name, {}).update(motion=out)
    return out


def glb_anim_check(path, name):
    """The exported rotation keys as the game reads them: largest turn per 1/60 s (linear slerp
    between keys), quaternion hemisphere flips between consecutive keys, loop first key == last key."""
    import json
    import struct
    data = open(path, "rb").read()
    length = struct.unpack_from("<III", data, 0)[2]
    off, js, blob = 12, None, None
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + clen]
        off += 8 + clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            blob = chunk

    def acc(i):
        a = js["accessors"][i]
        bv = js["bufferViews"][a["bufferView"]]
        k = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
        o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 4 * k)
        return [struct.unpack_from("<%df" % k, blob, o + j * stride) for j in range(a["count"])]
    out = {}
    for an in js.get("animations", []):
        worst, flips, seam = (0.0, ""), 0, 0.0
        for ch in an["channels"]:
            if ch["target"]["path"] != "rotation":
                continue
            s = an["samplers"][ch["sampler"]]
            t, q = acc(s["input"]), [Quaternion((w, x, y, z)) for (x, y, z, w) in acc(s["output"])]
            bone = js["nodes"][ch["target"]["node"]].get("name", "?")
            for j in range(1, len(q)):
                flips += q[j - 1].dot(q[j]) < 0.0
                a = quat_angle(q[j - 1], q[j]) * min(1.0, (1.0 / 60.0) / max(1e-6, t[j][0] - t[j - 1][0]))
                if a > worst[0]:
                    worst = (a, "%s @%.3fs" % (bone, t[j][0]))
            if an["name"] in LOOPS:
                seam = max(seam, quat_angle(q[0], q[-1]))
        out[an["name"]] = (round(worst[0], 1), worst[1], flips, round(seam, 2))
        if worst[0] > JUMP_MAX:
            fail(name, f"GLB {an['name']}: {worst[1]} turns {worst[0]:.0f} deg in 1/60 s")
        if seam > SEAM_DEG:
            fail(name, f"GLB {an['name']}: loop's last rotation key differs from the first by {seam:.1f} deg")
        if flips:
            print(f"  [check] {name}: GLB {an['name']} has {flips} quaternion hemisphere flips between keys "
                  f"(harmless for slerp, reported)")
    print(f"  [check] {name}: GLB most turn per 1/60 s {{{', '.join(f'{k}: {v[0]}' for k, v in out.items())}}}")
    CHECKS.setdefault(name, {}).update(glb=out)
    return out



# --------------------------------------------------------------------------- characters
def build_player():
    c = Char("player", style=dict(energy=1.0, bob=1.05, arm_out=4.0))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="smug", mouth="smirk", brows="smug")
    hair(c, DK, front=70, side=95, back=134, part=8, tmin=48, rings=4)
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
    c = Char("kakek", style=dict(stoop=9.0, stride=0.9, bob=0.7, energy=0.7, idle_arms="behind", arm_out=8.0),
             head_r=(0.226, 0.212, 0.204))
    SK, DK, PALE = "M_SkinTan", "M_Dark", "M_FadedShirt"
    face(c, SK, eyes="happy", mouth=None, brows="bushy", brow_mat=PALE)
    hair(c, PALE, front=80, side=95, back=130, seg=20, tmin=60, rings=4)
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
    # (the sarong's top tucks in under the shirt's hem band)
    sar = [(0.0, 0.118), (0.13, 0.112), (0.162, 0.114), (0.168, 0.132), (0.162, 0.25), (0.152, 0.285),
           (0.145, 0.305), (0.13, 0.325), (0.0, 0.335)]
    c.add("skirt", lathe_vf(sar, 20, 1.0, BODY_SY), "M_Sarong")
    skirt_rig(c, sar, BODY_SY)
    ssurf = lathe_surf(sar, 1.0, BODY_SY)
    for z in (0.16, 0.22, 0.272):
        prof = [(ssurf.r_at(z - 0.008) + 0.003, z - 0.008), (ssurf.r_at(z + 0.008) + 0.003, z + 0.008)]
        c.add("skirt", lathe_vf(prof, 20, 1.0, BODY_SY), PALE)
    for k in range(10):
        a = TAU * (k + 0.5) / 10
        c.add("skirt", strip_vf(ssurf, a, 0.12, 0.3, 0.012, 0.0035, 3), PALE)
    arms(c, SK, sleeve="short", sleeve_mat=PALE)
    legs(c, SK, dress=True, foot="sandal", foot_mat=DK, strap_mat="M_Sarong")
    return c


def build_ibu():
    c = Char("ibu", style=dict(stride=0.88, energy=0.85, idle_arms="front", head_tilt=2.0, arm_out=12.0), sh_x=0.118,
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
    skirt_rig(c, dress, 0.88)
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
    c = Char("kades", style=dict(chest=-5.0, idle_arms="behind", swagger=2.0, energy=0.85, arm_out=4.0))
    SK, DK = "M_Skin", "M_Dark"
    face(c, SK, eyes="round", mouth="smile", brows="normal")
    hair(c, DK, front=74, side=95, back=132, lift=0.012, seg=20, tmin=40, rings=4)
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
    c = Char("nenek", style=dict(stoop=15.0, stride=0.85, bob=0.6, energy=0.6, idle_arms="front", head_tilt=-2.0,
                              arm_out=12.0))
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
    keb = [(0.0, 0.3), (0.136, 0.296), (0.166, 0.305), (0.164, 0.33), (0.1595, 0.35), (0.156, 0.37), (0.153, 0.39),
           (0.148, 0.45), (0.141, 0.5),
           (0.128, 0.545), (0.101, 0.58), (0.062, 0.603), (0.0, 0.61)]
    surf = torso(c, "M_Kebaya", keb)
    collar(c, "M_Kebaya", dip=0.05, thick=(0.012, 0.016))
    for z in (0.39, 0.44, 0.49):
        c.add("torso", decal_vf(surf, 0.0, z, circle(0.009, 6), thick=0.002), GR)
    kain = [(0.0, 0.07), (0.125, 0.064), (0.152, 0.068), (0.157, 0.09), (0.153, 0.25), (0.151, 0.29), (0.147, 0.31),
            (0.13, 0.33), (0.0, 0.335)]
    c.add("skirt", lathe_vf(kain, 20, 1.0, 0.88), "M_Kain")
    skirt_rig(c, kain, 0.88)
    ksurf = lathe_surf(kain, 1.0, 0.88)
    for ri, z in enumerate((0.105, 0.16, 0.215, 0.27)):
        for k in range(9):
            a = TAU * (k + 0.5 * (ri % 2)) / 9
            c.add("skirt", decal_vf(ksurf, a, z, diamond(0.024, 0.03), 0.0035), "M_Kebaya")
    c.add("skirt", strip_vf(ksurf, rad(-18), 0.07, 0.285, 0.01, 0.0045, 3), "M_Kebaya")
    arms(c, SK, sleeve="long", sleeve_mat="M_Kebaya")
    legs(c, SK, dress=True, foot="sandal", foot_mat=DK, strap_mat="M_Kain")
    return c


def build_pemuda():
    c = Char("pemuda", style=dict(energy=1.2, bob=1.2, swagger=3.0, stride=1.05, arm_out=12.0))
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
    Rp = Vector((-0.155, 0.03, 0.325))   # knot towards the back of the right hip (clear of the swinging hand)
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
    c.add("torso_rigid", xf(ellipsoid_vf((0.046, 0.04, 0.044), 8, 5), T(Rp + Vector((-0.004, 0.02, 0.0)))),
          "M_SarongRed")
    c.add("torso_rigid", xf(ellipsoid_vf((0.025, 0.02, 0.056), 6, 4), T(Rp + Vector((-0.008, 0.04, -0.06)))),
          "M_SarongRed")
    arms(c, SK, sleeve="short", sleeve_mat="M_GreenTee")
    legs(c, SK, pants="shorts", pants_mat="M_Jeans", foot="sandal", foot_mat=DK)
    return c


def build_petani():
    c = Char("petani", style=dict(energy=0.95, arm_out=4.0))
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="round", mouth="smile", brows="normal")
    hair(c, DK, front=78, side=95, back=134, seg=20, tmin=58, rings=4)
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
    c = Char("anak", scale=0.76, style=dict(energy=1.3, bob=1.35, stride=1.1, arm_out=4.0),
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


PREMAN_TORSO = [(0.0, 0.36), (0.16, 0.36), (0.19, 0.38), (0.196, 0.405), (0.199, 0.428), (0.2, 0.45), (0.212, 0.55), (0.218, 0.63), (0.207, 0.69),
                (0.18, 0.735), (0.13, 0.77), (0.078, 0.79), (0.0, 0.8)]


def build_preman():
    c = Char("preman", style=dict(arm_out=10.0, swagger=5.0, chest=-4.0, idle_arms="akimbo", energy=0.9,
                                  stride=1.1, bob=0.9),
             hip_z=0.4, leg_x=0.092, knee_z=0.245, ankle_z=0.085, toe_y=-0.1, thigh_r=0.062, knee_r=0.054,
             shin_r=0.052, ankle_r=0.042, pelvis_z=0.415, spine_z=0.5, chest_z=0.585, neck_z=0.76, head_z=0.81,
             sh_x=0.2, sh_z=0.71, arm_a=30.0, l_up=0.135, l_fore=0.12, l_hand=0.09, up_r=0.05, elbow_r=0.044,
             fore_r=0.045, wrist_r=0.036, hand_k=1.35, head_c=1.012, head_r=(0.222, 0.208, 0.2),
             crotch_z=0.315)
    SK, DK, INK = "M_SkinTan", "M_Dark", "M_Ink"
    face(c, SK, eyes="narrow", mouth="frown", brows="angry", hl=None)
    hair(c, DK, front=60, side=90, back=122, lift=0.006, rim=None, seg=22, rings=4)
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
    # (fine links: many short segments, round section, alternating thickness; hugs the chest surface)
    N = 44
    chain = [(TAU * i / N, 0.777 - 0.068 * (0.5 + 0.5 * math.cos(TAU * i / N)) ** 1.6) for i in range(N)]
    cr = [0.0095 if i % 2 else 0.0068 for i in range(N)]
    cp = [surf(a_, z_) + snormal(surf, a_, z_) * (0.0075 + 0.4 * r_) for (a_, z_), r_ in zip(chain, cr)]
    c.add("torso_rigid", tube_vf(cp, cr, 6, closed=True), "M_Gold")
    c.add("torso_rigid", xf(ellipsoid_vf((0.022, 0.01, 0.026), 6, 4), T(surf(0.0, 0.68) + Vector((0, -0.02, 0)))),
          "M_Gold")
    pelvis(c, "M_Army", [(0.0, 0.3), (0.1, 0.305), (0.16, 0.33), (0.18, 0.37), (0.183, 0.395), (0.15, 0.41),
                         (0.0, 0.415)], sx=1.05, sy=sy)
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
    c = Char("calo", style=dict(swagger=4.0, idle_arms="front", head_tilt=4.0, energy=1.0, rub=1.0, arm_out=12.0))
    SK, DK, TW = "M_Skin", "M_Dark", "M_Tweed"
    face(c, SK, eyes=None, mouth="smirk", brows=None)
    hair(c, DK, front=80, side=95, back=132, lift=0.014, seg=20, tmin=60, rings=4)
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
    # bum-bag strap: follows the real (elliptic) waist and uses the shirt's own skin weights, so it
    # stays on the body when the hips and legs move
    strap = surf_path(lathe_surf(TORSO, 1.0, BODY_SY), [(TAU * i / 28, 0.35 + 0.03 * math.cos(TAU * i / 28 + 0.9))
                                                        for i in range(28)], 0.006)
    c.add("torso", tube_vf(strap, (0.008, 0.014), 4, closed=True), DK)
    bb = surf(rad(6), 0.335) + Vector((0, -0.04, 0))      # (a little to his left: the right fist swings past)
    c.add("torso_rigid", xf(ellipsoid_vf((0.085, 0.043, 0.052), 12, 6), T(bb) @ R("Y", 12)), DK)
    c.add("torso_rigid", xf(tube_vf([(-0.066, -0.043, 0.012), (0.0, -0.048, 0.014), (0.066, -0.043, 0.012)],
                                    0.004, 4), T(bb) @ R("Y", 12)), "M_HawaiiBloom")
    arms(c, SK, sleeve="short", sleeve_mat="M_Hawaii")
    legs(c, SK, pants="long", pants_mat=TW, foot="shoe", foot_mat=DK)
    return c


def build_petugas():
    c = Char("petugas", style=dict(chest=-3.0, idle_arms="clip", energy=0.8, arm_out=4.0, plant_lift_L=0.024))
    SK, DK, UN = "M_Skin", "M_Dark", "M_Uniform"
    face(c, SK, eyes="round", mouth="flat", brows="angry")
    hair(c, DK, front=80, side=95, back=132, lift=0.012, seg=20, tmin=58, rings=4)
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
    c = Char("buruh", style=dict(stoop=4.0, energy=0.8, stride=0.95, arm_out=6.0))
    SK, DK = "M_SkinTan", "M_Dark"
    face(c, SK, eyes="round", mouth="flat", brows="worried")
    hair(c, DK, front=80, side=95, back=132, lift=0.012, seg=20, tmin=58, rings=4)
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


# clip -> (z0, z1, (r_side, r_thick), colour, y offset) segments along hand_R local +Z, in metres
# like the game's tools (char_anim.gd tool_mesh: parang grip -0.07..0.08, blade 0.10..0.46 with its
# edge towards the fingers, i.e. hand_R +Y)
PROXY_TOOLS = {
    "harvest": [(-0.4, 2.2, (0.014, 0.014), "#b58a4c", 0.0), (2.2, 2.45, (0.03, 0.006), "#8c9aa0", 0.0)],
    "chop": [(-0.07, 0.1, (0.02, 0.02), "#5a3b24", 0.0), (0.1, 0.46, (0.036, 0.004), "#b9c3c6", 0.012)],
}
PARANG_BLADE = [(yy, z) for yy in (-0.026, 0.0, 0.025, 0.048) for z in [0.1 + 0.02 * k for k in range(19)]]


def blade_check(c, rig, body, act, frames):
    """Smallest distance (m) between the game's parang blade (in the right fist) and the body,
    excluding the right arm and hand, per frame: {frame: (distance, nearest material, fist sink depth)}."""
    from mathutils.bvhtree import BVHTree
    me = body.data
    skip = set()
    for (a, b, rule, mname) in c.vranges:
        if rule in (("arm", -1), ("hand", -1)):
            skip.update(range(a, b))
    polys = [tuple(p.vertices) for p in me.polygons if p.vertices[0] not in skip]
    pmat = [me.materials[p.material_index].name for p in me.polygons if p.vertices[0] not in skip]
    hand = [i for (a, b, rule, mname) in c.vranges if rule == ("hand", -1) for i in range(a, b)][::3]
    g = 0.036 * c.S * c.d["hand_k"]
    pb = rig.ob.pose.bones["hand_R"]
    out = {}
    for f in frames:
        set_frame(rig, act, f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        em = ev.to_mesh()
        ev_co = [v.co.copy() for v in em.vertices]
        tr = BVHTree.FromPolygons(ev_co, polys, all_triangles=False)
        ev.to_mesh_clear()
        M = pb.matrix
        best = (9.0, "")
        for (yy, z) in PARANG_BLADE:
            hit = tr.find_nearest(M @ Vector((0.0, g + yy, z)))
            if hit[0] is not None and hit[3] < best[0]:
                best = (hit[3], pmat[hit[2]])
        # and how deep the right fist sinks into the body (m, 0 = not at all)
        sink = 0.0
        for i in hand:
            co = ev_co[i]
            hit = tr.find_nearest(co, 0.05 * c.S)
            if hit[0] is not None and hit[1].dot(co - hit[0]) < 0:
                # inside only if every face about as near agrees (the nearest point on the rim of a
                # thin plate or sash belongs to faces facing both ways)
                near = tr.find_nearest_range(co, hit[3] + 0.001 * c.S)
                if all(h[1].dot(co - h[0]) < 0 for h in near):
                    sink = max(sink, hit[3])
        out[f] = best + (sink,)
    return out


def attach_proxy(c, rig, clip):
    """A stand-in tool on hand_R (like the game's BoneAttachment3D) so the sheets show the grip."""
    segs = PROXY_TOOLS.get(clip)
    if not segs:
        return []
    out = []
    ob = rig.ob
    bone = ob.data.bones["hand_R"]
    g = 0.036 * c.S * c.d["hand_k"]
    for i, (z0, z1, rr, col, yo) in enumerate(segs):
        v, f = tube_vf([(0, yo, z0), (0, yo, z1)], rr, 8, up=(1, 0, 0))
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
    k = c.S * (1.12 if c.name == "preman" else 1.0)
    tmp.append(_camera((0, 0, 0.5 * k), 38.0, 0.0, 10, ortho=1.32 * k))
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
def _brace_balance(txt):
    """{ minus } outside double-quoted strings (the .import format is Godot's ConfigFile)."""
    depth, q, esc = 0, False, False
    for ch in txt:
        if q:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                q = False
        elif ch == '"':
            q = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    return depth


def loops_import_text(txt):
    """Return the .glb.import text with `_subresources=` set to exactly our loop block.
    Line based and idempotent: the old value (however many lines, balanced or not - e.g. the
    stray `}` lines an earlier regex version left behind) is dropped up to the next `key=` line or
    section header, then one balanced block is written. `gltf/naming_version` is kept at 2."""
    import re
    block = ["_subresources={", "\"animations\": {"]
    block += [",\n".join("\"%s\": {\n\"settings/loop_mode\": 1\n}" % n for n in LOOPS)]
    block += ["}", "}"]
    block = "\n".join(block).split("\n")
    key = re.compile(r"^[A-Za-z_][\w/.\-]*=")
    out, skipping, done = [], False, False
    for line in txt.split("\n"):
        if skipping:
            if key.match(line) or line.startswith("["):
                skipping = False
            else:
                continue
        if line.startswith("_subresources="):
            if not done:
                out += block
                done = True
            skipping = not line.rstrip().endswith("{}") and _brace_balance(line) != 0
            continue
        if line.startswith("gltf/naming_version="):
            line = "gltf/naming_version=2"
        out.append(line)
    if not done:   # no _subresources line yet: put it at the end of [params]
        i = max(k for k, l in enumerate(out) if l.strip()) + 1
        out[i:i] = block
    new = "\n".join(out)
    assert _brace_balance(new) == 0, "unbalanced braces in the .import sidecar"
    return new


def mark_loops_in_import(name):
    """Tell Godot's importer to loop the cyclic clips (sets loop_mode = LINEAR on re-import) by
    writing them into the existing .glb.import sidecar. Other import settings are left alone."""
    path = os.path.join(common.MODELS_DIR, name + ".glb.import")
    if not os.path.exists(path):
        print("[import] no sidecar yet for", name, "- open the project in Godot once, then re-run")
        return
    txt = open(path).read()
    new = loops_import_text(txt)
    assert loops_import_text(new) == new, "sidecar rewrite is not idempotent"
    if new != txt:
        open(path, "w").write(new)
        print("[import] loops marked in", os.path.basename(path))



def gait_extras(c, st):
    """Numbers the game needs to drive the clips, stored as glTF extras on the armature node
    (Godot imports them as the node's "extras" metadata)."""
    out = {"grip_offset": round(0.036 * c.S * c.d["hand_k"], 4)}
    for kind in ("walk", "run"):
        v, ratio = gait_speed(c, st, kind)
        sig = GAIT[kind]["sigma"]
        out["%s_speed" % kind] = round(v, 3)                 # ground speed (m/s) at playback 1.0
        out["%s_stance" % kind] = sig                        # share of the cycle a foot is planted
        out["%s_stance_ankle" % kind] = round(sig * ratio, 3)  # = (ankle travel / ground travel) * stance
    return out


def export_char(rig_ob, name, extras):
    """common.export_glb(root, name, animations=True) plus: glTF extras on (only) the armature node,
    and constant channels of never-keyed bone properties dropped (they stay at the rest pose)."""
    for k, v in extras.items():
        rig_ob[k] = v
    bpy.ops.object.select_all(action="DESELECT")
    for o in common.all_descendants(rig_ob):
        o.select_set(True)
    path = os.path.join(common.MODELS_DIR, name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
        export_materials="EXPORT", export_animations=True, export_extras=True, export_cameras=False,
        export_lights=False, export_vertex_color="ACTIVE" if common._has_colors(rig_ob) else "NONE",
        export_animation_mode="ACTIONS", export_skins=True, export_force_sampling=True,
        export_optimize_animation_size=True, export_optimize_animation_keep_anim_armature=False)
    for k in extras:
        del rig_ob[k]
    print(f"[export] {name}.glb  tris={count_tris(rig_ob)}  extras={extras}")
    return path


def mesh_bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def build_one(name, out=True, sheets=None, bake=True, allow_fail=False):
    """Build, animate, check and (out=True) export one character. bake=False skips the AO bake (fast
    check-only runs). A character failing a check is not exported unless allow_fail."""
    nfail = len(FAILS)
    c = BUILDERS[name]()
    st = dict(STYLE, **c.style)
    rig_ob, body = assemble(c, bake=bake)
    rig = Rig(rig_ob, c)
    acts = bake_actions(rig, st)
    bpy.context.view_layer.update()
    motion_checks(c, st, rig, body, acts)
    # automated clip checks: cloth layers (hidden inner-layer vertices that come out in a pose, worst
    # frame), parang blade clearance over the swing and how deep the right fist sinks into the body
    lay = {}
    for clip in ("plant", "walk", "run", "cheer"):
        a = acts[clip]
        res = layer_check(c, body, lambda f, a=a: set_frame(rig, a, f), range(0, int(a.frame_range[1]) + 1, 2))
        lay[clip] = max(v[0] for v in res.values())
    bl = blade_check(c, rig, body, acts["chop"], range(0, 25))
    CHECKS.setdefault(name, {}).update(
        layers=lay, blade_cm=round(min(v[0] for f, v in bl.items() if 2 <= f <= 20) * 100, 1),
        fist_sink_mm=round(max(v[2] for v in bl.values()) * 1000, 1))
    print(f"  [check] {name}: exposed cloth vertices (worst frame) {lay}, parang clearance "
          f"{CHECKS[name]['blade_cm']} cm, fist sink {CHECKS[name]['fist_sink_mm']} mm")
    if CHECKS[name]["blade_cm"] < BLADE_MIN * 100:
        fail(name, f"chop: parang blade {CHECKS[name]['blade_cm']} cm from the body (min {BLADE_MIN * 100:.1f} cm)")
    if CHECKS[name]["fist_sink_mm"] > FIST_SINK_MAX * 1000:
        fail(name, f"chop: right fist sinks {CHECKS[name]['fist_sink_mm']} mm into the body")
    mn, mx = mesh_bounds(body)
    tris = count_tris(body)
    mats = sorted(m.name for m in body.data.materials)
    info = dict(name=name, height=mx.z, tris=tris, mats=mats)
    print(f"[char] {name}: h={mx.z:.3f} tris={tris} mats={len(mats)} {mats}")
    if tris > 6000:
        print(f"  !! {name} over triangle budget")
    if len(mats) > 6:
        print(f"  !! {name} over material budget")
    ok = len(FAILS) == nfail
    if out and not ok and not allow_fail:
        print(f"  !! {name}: {len(FAILS) - nfail} check(s) failed - NOT exported (--allow-fail exports anyway)")
    if out and (ok or allow_fail):
        rig_ob.animation_data.action = acts["idle"]
        bpy.context.scene.frame_set(0)
        path = export_char(rig_ob, "char_" + name, gait_extras(c, st))
        glb_anim_check(path, name)
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
    tmp = _scene_setup(1200, 750, samples=12, ground="#8fb35c")
    tmp.append(_camera((0, 0.62, 0.5), 30.0, 0.0, 20, ortho=5.9))
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, "lineup.png")
    bpy.ops.render.render(write_still=True)
    print("[preview] lineup.png")


def main(argv):
    """python3 blender/characters.py [names...] [--sheets[=clip,..]] [--no-out] [--lineup]
    [--check-only] [--allow-fail]. --check-only = no AO bake, no export, no renders: just build,
    animate and run the checks (fast). Exit status 1 when any check failed."""
    names = [a for a in argv if not a.startswith("--")]
    only_lineup = "--lineup" in argv
    check_only = "--check-only" in argv
    no_out = "--no-out" in argv or check_only
    allow_fail = "--allow-fail" in argv
    sheets = None
    for a in argv:
        if a.startswith("--sheets"):
            sheets = a.split("=", 1)[1].split(",") if "=" in a else list(CLIPS)
    order = list(BUILDERS)
    todo = names or ([] if only_lineup else order)
    infos = []
    for n in todo:
        reset_scene()
        _, _, _, info = build_one(n, out=not no_out, sheets=sheets, bake=not check_only, allow_fail=allow_fail)
        infos.append(info)
    if (not names or only_lineup) and not no_out and not FAILS:
        lineup(order)
    print("\n==== summary ====")
    for i in infos:
        ck = CHECKS.get(i["name"], {})
        print(f"{i['name']:8s} height={i['height']:.3f} tris={i['tris']:5d} mats={len(i['mats'])}  "
              f"walk/run thigh-step,side-knee={ck.get('walk')}/{ck.get('run')}  layers={ck.get('layers')}  "
              f"parang={ck.get('blade_cm')}cm fist_sink={ck.get('fist_sink_mm')}mm")
        mo = ck.get("motion")
        if mo:
            feet = "  ".join(f"{k}: slide {100 * mo[k + '_feet']['slide']:.1f}% lift {mo[k + '_feet']['lift'] * 1000:.0f}mm "
                             f"down@{100 * mo[k + '_feet']['down']:.0f}%" for k in ("walk", "run"))
            top = max(mo["jump"].items(), key=lambda kv: kv[1])
            glb = ck.get("glb")
            gtop = max(((k, v[0]) for k, v in glb.items()), key=lambda kv: kv[1]) if glb else None
            print(f"{'':8s} {feet}  most turn/60Hz: {top[0]} {top[1]} deg (chop {mo['jump'].get('chop')})"
                  + (f"  GLB: {gtop[0]} {gtop[1]} deg" if gtop else ""))
    if FAILS:
        print("\n" + "!" * 72)
        print(f"!! {len(FAILS)} CHECK(S) FAILED:")
        for n, msg in FAILS:
            print(f"!!   {n}: {msg}")
        print("!" * 72)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main(sys.argv[1:])

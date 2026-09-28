#!/usr/bin/env python3
"""Sawit The Franchise - farm & village animals: skinned, animated, cel-shade-ready GLBs.

Run:  python3 blender/animals.py                  all species: GLBs, previews, lineup, game/data/animal_models.json
      python3 blender/animals.py sapi kodok       only these (no lineup)
      python3 blender/animals.py --lineup         only the lineup preview (blender/previews/animal_lineup.png)
      options: --sheets[=walk,run,...]   contact sheets of the clips to /tmp/anim_work/models/sheets/
               --views=game,side,front,top  sheet rows;  --sheet-n=8  frames per sheet
               --look                    quick 4-view render of the idle pose (/tmp/anim_work/models/look_<id>.png)
               --hen                     (with --look) hide the rooster parts
               --no-export               build, bake AO, animate, render only (keep the GLBs as they are)
               --no-out                  build, animate and check only (no AO bake, export, renders)
      Godot check: godot --path game -- --autotest=animals_models (xvfb-run + --shots=<dir> for pictures)

Species (ANIMAL CONTRACT): sapi (Bali cow), kerbau (water buffalo), kambing (goat), ayam (chicken,
hen + rooster), bebek (duck), kodok (frog, modelled ~2x real size), kucing (village cat), anjing
(kampung dog). Output: game/assets/models/animal_<id>.glb + blender/previews/animal_<id>.png and
blender/previews/animal_lineup.png.

Conventions (same as the villagers in characters.py):
  * 1 unit = 1 m, Z up, ground at z = 0, the animal faces -Y in Blender = +Z in Godot (glTF), so a
    Godot node moving along direction d turns with rotation.y = atan2(d.x, d.z) like the villagers.
  * One armature node `animal_<id>` (glTF extras on it, see below) with ONE skinned mesh `Body`
    (the chicken has a second skinned mesh `Rooster`: sickle tail + big comb, hide it for hens).
  * Smooth normals everywhere (the game's inverted-hull ink outline pushes along them), closed
    surfaces with outward normals, baked vertex AO in colour attribute `Col` (never below ~0.5).

Materials (names never contain the game's foliage/glow words):
  AnimalFur_<id>    main coat / plumage           -> tint per instance (variants)
  AnimalMark_<id>   markings (socks, rump patch, muzzle, belly, patches, wing/tail feathers)
  AnimalMark2_<id>  second marking colour (cat patches, frog spots, dog ear tips) where present
  AnimalDark        eyes, nostrils, hooves, mouth interior, tail tuft (shared by all species)
  AnimalShine       eye highlights (shared)
  AnimalHorn / AnimalBeak_<id> / AnimalComb / AnimalWhite / AnimalTongue   fixed accent colours
Colour variants: the game swaps the albedo of AnimalFur_<id> / AnimalMark_<id> / AnimalMark2_<id>
per instance (e.g. ModelLib.retuned(mat, "var_<id>_<n>", {"albedo": Color(hex)}) on the surfaces
whose resource_name matches); the palette of each species is in the glTF extras `variants`
(JSON list of {name, fur, mark[, mark2][, rooster]}) and in game/data/animal_models.json.

Rig: `hips` is the root (pelvis, translated for body bob); spine > chest > neck > head > jaw, eye_L/R
(scaled on local Z to blink), ear_L/R; tail_1.. under hips; legs <front|hind>_<upper|lower|cannon|foot>_<L|R>
(birds: leg_<...>_<L|R> + wing_L/R; frog: body (squash & stretch), throat (vocal sac)). _L = the
animal's own left (+X in Blender). Legs are driven by a small IK solver (planted feet, hoof/paw
roll, carpus/hock flexion) and baked to per-frame quaternion keys (30 fps, in place).

Clips (exact names): idle walk run eat call (+ kodok hop, bebek swim, kucing sit, anjing wag).
Loops: idle walk run eat swim sit wag (first frame == last frame); one-shots: call, hop.
glTF extras on the armature node (Godot: "extras" metadata): species, walk_speed / run_speed
(ground speed in m/s the walk/run clip covers at playback 1.0: playback rate = speed / that),
walk_stance / run_stance, height, length, call_open (s into `call` when the mouth opens: start the
sound there), variants (JSON), loops, and per species: hop_speed / hop_time (kodok: move the node at
hop_speed while `hop` plays), swim_draft (bebek: in `swim` the model's origin is the water line).
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import common  # noqa: E402
from common import MODELS_DIR, PREVIEW_DIR, bake_vertex_ao, count_tris, link, mat, reset_scene  # noqa: E402
import characters as CH  # noqa: E402

FPS = 30
TAU = math.tau
SCRATCH = "/tmp/anim_work/models"
DATA_JSON = os.path.join(common.ROOT, "game", "data", "animal_models.json")
TRI_BUDGET = 3000


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


def V(x, y=0.0, z=0.0):
    if isinstance(x, (tuple, list, Vector)):
        return Vector(x)
    return Vector((x, y, z))


def Rx(d):
    """+d: a forward-pointing bone's tip goes down, a downward bone's tip goes back (+Y)."""
    return Matrix.Rotation(rad(d), 3, "X")


def Ry(d):
    """+d: the top leans to the animal's left (+X)."""
    return Matrix.Rotation(rad(d), 3, "Y")


def Rz(d):
    """+d: turns a forward-pointing bone to the animal's left (+X)."""
    return Matrix.Rotation(rad(d), 3, "Z")


def D(pitch=0.0, yaw=0.0, roll=0.0):
    """World-axis rotation delta: pitch (+ = nose down / leg back), yaw (+ = turn left), roll (+ = lean left)."""
    return Rz(yaw) @ Rx(pitch) @ Ry(roll)


def sgnpow(s, e):
    return math.copysign(abs(s) ** e, s)


def cyc(x):
    """cos(2 pi x)"""
    return math.cos(TAU * x)


def syc(x):
    return math.sin(TAU * x)


def Kc(keys, period=None):
    """Keyed scalar curve (monotone cubic easing, CH.Curve)."""
    return CH.Curve(keys, period)


def blink(f, at, dur=5.0):
    """eye scale (1 open .. 0.08 shut) for a blink starting at frame `at`."""
    t = (f - at) / dur
    if t <= 0.0 or t >= 1.0:
        return 1.0
    return 1.0 - 0.92 * math.sin(math.pi * t) ** 0.7


def smooth_cyclic(vals, sigma, loop=True):
    n = len(vals) - 1 if loop else len(vals)
    if sigma <= 0 or n < 3:
        return list(vals)
    r = int(math.ceil(sigma * 3))
    ker = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
    out = []
    for i in range(n):
        s = w = 0.0
        for k, kw in zip(range(-r, r + 1), ker):
            j = i + k
            if loop:
                j %= n
            elif j < 0 or j >= n:
                continue
            s += vals[j] * kw
            w += kw
        out.append(s / w)
    if loop:
        out.append(out[0])
    return out


class Frame:
    """Local frame: origin o, forward f, up u (orthogonalised), lateral x (= the animal's left when f = -Y)."""

    def __init__(self, o, f, u):
        self.o = V(o)
        self.f = V(f).normalized()
        u = V(u)
        self.u = (u - self.f * u.dot(self.f)).normalized()
        self.x = self.u.cross(self.f)

    def p(self, x, f, u):
        return self.o + self.x * x + self.f * f + self.u * u

    def d(self, x, f, u):
        return (self.x * x + self.f * f + self.u * u).normalized()

    def m(self, p=None):
        """4x4 placing local (x, y, z) along (x, f, u)."""
        M = Matrix((self.x, self.f, self.u)).transposed().to_4x4()
        M.translation = self.o if p is None else V(p)
        return M


def frame_m(p, x, y, z):
    M = Matrix((V(x), V(y), V(z))).transposed().to_4x4()
    M.translation = V(p)
    return M


# --------------------------------------------------------------------------- geometry
class Spline:
    """Catmull-Rom spline through points, parametrised by chord length (t in 0..1)."""

    def __init__(self, pts):
        self.p = [V(q) for q in pts]
        n = len(self.p)
        self.m = []
        for i in range(n):
            a, b = self.p[max(i - 1, 0)], self.p[min(i + 1, n - 1)]
            self.m.append((b - a) * (0.5 if 0 < i < n - 1 else 1.0))
        self.L = [0.0]
        for i in range(n - 1):
            self.L.append(self.L[-1] + (self.p[i + 1] - self.p[i]).length)

    def at(self, t):
        if len(self.p) == 1:
            return self.p[0].copy()
        s = clamp(t) * self.L[-1]
        i = 0
        while i < len(self.p) - 2 and self.L[i + 1] < s:
            i += 1
        h = max(self.L[i + 1] - self.L[i], 1e-9)
        u = clamp((s - self.L[i]) / h)
        u2, u3 = u * u, u * u * u
        return ((2 * u3 - 3 * u2 + 1) * self.p[i] + (u3 - 2 * u2 + u) * self.m[i] + (-2 * u3 + 3 * u2) * self.p[i + 1]
                + (u3 - u2) * self.m[i + 1])

    def tan(self, t):
        e = 1e-3
        a, b = self.at(max(0.0, t - e)), self.at(min(1.0, t + e))
        d = b - a
        if d.length < 1e-9:
            d = self.p[-1] - self.p[0]
        return d.normalized()


def signed_volume(verts, faces):
    v = 0.0
    for f in faces:
        a = verts[f[0]]
        for i in range(1, len(f) - 1):
            v += a.dot(verts[f[i]].cross(verts[f[i + 1]]))
    return v / 6.0


def outward(vf):
    verts, faces = vf[0], vf[1]
    if signed_volume(verts, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def loft(pts, prof, seg=12, rings=8, up=(0, 0, 1), caps=(0.8, 0.8), cap_rings=2, sq=2.0, amod=None, ts=None):
    """Closed tube along a spline through pts. prof: [(t, rx, rz[, du[, dx]])] - rx along the side
    axis X = U x T, rz along U (the `up` reference made perpendicular to the path), du/dx offset the
    section centre. caps: rounded end length / mean end radius (0 = flat). amod(t, a) scales the
    radius at angle a (0 = +U, pi/2 = +X)."""
    sp = Spline(pts)
    keys = sorted([tuple(k) + (0.0,) * (5 - len(k)) for k in prof])
    cv = [Kc([(k[0], k[i]) for k in keys]) for i in (1, 2, 3, 4)]
    if ts is None:
        ts = [i / (rings - 1) for i in range(rings)]
    upv = V(up).normalized()
    verts, faces, R = [], [], []

    def ring(C, X, U, rx, rz, t):
        idx = []
        for j in range(seg):
            a = TAU * j / seg
            m = amod(t, a) if amod else 1.0
            idx.append(len(verts))
            verts.append(C + X * (rx * m * sgnpow(math.sin(a), 2.0 / sq)) + U * (rz * m * sgnpow(math.cos(a), 2.0 / sq)))
        return idx

    frames = []
    U = None
    Tp = None
    for t in ts:
        C, T = sp.at(t), sp.tan(t)
        if U is None:           # first ring: the `up` reference; then parallel transport (no flips)
            U = upv - T * upv.dot(T)
            if U.length < 1e-6:
                U = V(0, -1, 0) - T * (-T.y)
        else:
            U = Tp.rotation_difference(T).to_matrix() @ U
            U = U - T * U.dot(T)
        U.normalize()
        Tp = T
        X = U.cross(T)
        rx, rz, du, dx = (c(t) for c in cv)
        frames.append((C + U * du + X * dx, T, X, U, max(rx, 1e-4), max(rz, 1e-4), t))
    C0, T0, X0, U0, rx0, rz0, t0 = frames[0]
    L0 = caps[0] * 0.5 * (rx0 + rz0)
    for k in (range(cap_rings, 0, -1) if L0 > 0 else []):
        ph = (math.pi / 2) * k / (cap_rings + 1)
        R.append(ring(C0 - T0 * (L0 * math.sin(ph)), X0, U0, rx0 * math.cos(ph), rz0 * math.cos(ph), t0))
    for (C, T, X, U, rx, rz, t) in frames:
        R.append(ring(C, X, U, rx, rz, t))
    C1, T1, X1, U1, rx1, rz1, t1 = frames[-1]
    L1 = caps[1] * 0.5 * (rx1 + rz1)
    for k in (range(1, cap_rings + 1) if L1 > 0 else []):
        ph = (math.pi / 2) * k / (cap_rings + 1)
        R.append(ring(C1 + T1 * (L1 * math.sin(ph)), X1, U1, rx1 * math.cos(ph), rz1 * math.cos(ph), t1))
    p0 = len(verts)
    verts.append(C0 - T0 * L0)
    p1 = len(verts)
    verts.append(C1 + T1 * L1)
    for i in range(len(R) - 1):
        A, B = R[i], R[i + 1]
        faces += [(A[j], A[(j + 1) % seg], B[(j + 1) % seg], B[j]) for j in range(seg)]
    faces += [(p0, R[0][(j + 1) % seg], R[0][j]) for j in range(seg)]
    faces += [(p1, R[-1][j], R[-1][(j + 1) % seg]) for j in range(seg)]
    return outward((verts, faces))


def ellip(M, radii, seg=10, rings=6):
    """Ellipsoid with local radii (x, y, z) placed by 4x4 matrix M."""
    v, f = CH.ellipsoid_vf(radii, seg, rings)
    return outward(([M @ Vector(p) for p in v], f))


def mesh_tree(vf):
    return BVHTree.FromPolygons([tuple(v) for v in vf[0]], [tuple(f) for f in vf[1]], all_triangles=False)


def surf(vf, origin, direction, tree=None):
    """First hit of a ray cast from far outside along -direction back towards origin: (point, outward normal)."""
    tree = tree or mesh_tree(vf)
    d = V(direction).normalized()
    o = V(origin) + d * 5.0
    p, n, _i, _dist = tree.ray_cast(o, -d, 10.0)
    if p is None:
        p, n, _i, _dist = tree.find_nearest(V(origin) + d * 0.5)
    if n.dot(d) < 0:
        n = -n
    return p, n.normalized()


def decal(target, center, normal, up, rx, ry, rings=2, seg=16, lift=0.003, shape=None):
    """Flat ellipse (rx along the side axis, ry along `up`) projected onto the target surface along
    -normal and lifted by `lift` (a marking that lies on the skin). shape(a) scales the outline."""
    tree = mesh_tree(target)
    n = V(normal).normalized()
    u = V(up)
    u = (u - n * u.dot(n)).normalized()
    x = u.cross(n)
    pts = [(0.0, 0.0)]
    for k in range(1, rings + 1):
        for j in range(seg):
            a = TAU * j / seg
            s = shape(a) if shape else 1.0
            pts.append((k / rings * rx * s * math.cos(a), k / rings * ry * s * math.sin(a)))
    verts = []
    c = V(center)
    for (a, b) in pts:
        o = c + x * a + u * b + n * 2.0
        hit = tree.ray_cast(o, -n, 4.0)
        if hit[0] is None:
            hit = tree.find_nearest(c + x * a + u * b)
        hn = hit[1] if hit[1].dot(n) > 0 else -hit[1]
        verts.append(hit[0] + hn.normalized() * lift)
    faces = [(0, 1 + j, 1 + (j + 1) % seg) for j in range(seg)]
    for k in range(rings - 1):
        A, B = 1 + k * seg, 1 + (k + 1) * seg
        faces += [(A + j, B + j, B + (j + 1) % seg, A + (j + 1) % seg) for j in range(seg)]
    f0 = faces[0]
    nn = (verts[f0[1]] - verts[f0[0]]).cross(verts[f0[2]] - verts[f0[0]])
    if nn.dot(n) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def strip(target, pts, width, normal, lift=0.003, taper=0.25):
    """A thin stripe (dorsal line) following pts over the target surface (cast along -normal)."""
    tree = mesh_tree(target)
    n = V(normal).normalized()
    sp = Spline(pts)
    k = 20
    verts, faces = [], []
    for i in range(k + 1):
        t = i / k
        c, T = sp.at(t), sp.tan(t)
        side = T.cross(n).normalized()
        w = width * 0.5 * min(1.0, min(t, 1 - t) / taper + 0.15)
        for s in (-1, 1):
            o = c + side * (w * s) + n * 2.0
            hit = tree.ray_cast(o, -n, 4.0)
            if hit[0] is None:
                hit = tree.find_nearest(c + side * (w * s))
            hn = hit[1] if hit[1].dot(n) > 0 else -hit[1]
            verts.append(hit[0] + hn.normalized() * lift)
    for i in range(k):
        a = 2 * i
        faces.append((a, a + 2, a + 3, a + 1))
    f0 = faces[0]
    nn = (verts[f0[1]] - verts[f0[0]]).cross(verts[f0[2]] - verts[f0[0]])
    if nn.dot(n) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


# --------------------------------------------------------------------------- skin weight rules
def chain(bones, joints, blend=0.04, pre=None, pre_blend=0.04):
    """Weights along a bone chain: bone k spans joints[k] -> joints[k+1]; smooth blends of +-blend (m)
    around each inner joint; `pre` = the parent bone taking the part before joints[0]."""
    J = [V(j) for j in joints]
    S = [0.0]
    for i in range(len(J) - 1):
        S.append(S[-1] + (J[i + 1] - J[i]).length)
    bl = list(blend) if isinstance(blend, (list, tuple)) else [blend] * len(bones)

    def w(p):
        best = None
        for i in range(len(J) - 1):
            a, b = J[i], J[i + 1]
            d = b - a
            L2 = max(d.length_squared, 1e-12)
            t = (p - a).dot(d) / L2
            tc = max(t, 0.0) if i > 0 else t
            tc = min(tc, 1.0) if i < len(J) - 2 else tc
            dist = (p - (a + d * clamp(tc, 0.0, 1.0))).length
            if best is None or dist < best[0] - 1e-9:
                best = (dist, S[i] + tc * math.sqrt(L2))
        s = best[1]
        out = {}
        tp = ss(-pre_blend, pre_blend, s) if pre else 1.0
        if pre:
            out[pre] = 1.0 - tp
        for k, bn in enumerate(bones):
            tn = ss(S[k + 1] - bl[k], S[k + 1] + bl[k], s) if k + 1 < len(bones) else 0.0
            out[bn] = out.get(bn, 0.0) + max(0.0, tp - tn)
            tp = min(tp, tn)
        return out
    return w


def mix(w, bone, a):
    if a <= 0:
        return w
    for k in w:
        w[k] *= 1.0 - a
    w[bone] = w.get(bone, 0.0) + a
    return w


# --------------------------------------------------------------------------- animal definition
class Leg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Animal:
    def __init__(self, sid, size):
        self.id = sid
        self.name = "animal_" + sid
        self.size = size              # overall length (m): AO distance, previews, checks
        self.bones = []               # (name, head, tail, parent, zref)
        self.chunks = []              # (verts, faces, mat key | fn(centroid, normal) -> key, smooth, rule, target)
        self.legs = []
        self.chains = {}
        self.mats = {}                # key -> (material name, hex, roughness)
        self.scale_bones = []
        self.loc_bones = ["hips"]
        self.meta = {}
        self.variants = []
        self.clips = {}               # name -> fn(an, solver) -> (N, loop, [Pose] * (N + 1))
        self.anim = {}
        self.pose_skip = set()

    def bone(self, name, head, tail, parent=None, zref=None):
        h, t = V(head), V(tail)
        if zref is None:
            d = (t - h).normalized()
            zref = V(0, -1, 0) if abs(d.z) > 0.7 else V(0, 0, 1)
        self.bones.append((name, h, t, parent, V(zref)))
        return name

    def blen(self, name):
        for (n, h, t, p, z) in self.bones:
            if n == name:
                return (t - h).length
        raise KeyError(name)

    def bhead(self, name):
        for (n, h, t, p, z) in self.bones:
            if n == name:
                return h.copy()
        raise KeyError(name)

    def mat(self, key, name, hexcol, rough=0.85):
        self.mats[key] = (name, hexcol, rough)

    def add(self, vf, m, rule, target="Body", smooth=True):
        self.chunks.append(([V(v) for v in vf[0]], [tuple(f) for f in vf[1]], m, smooth, rule, target))
        return vf


def add_leg(an, name, side, prefix, parent, H, K, C, A, toe, pivot, pole, flex_sign, front, radii, top_z,
            seg=8, rings=6, skin=0.6, sock=None, foot_key="fur", lift=0.1, sock_key="mark", from_H=False, paint=None,
            pre=None, plane=False):
    """Leg bones (upper H->K hidden in the body, lower K->C, cannon C->A, foot A->toe) + the visible
    leg tube from top_z (inside the body) down to A. C may be None (3-bone leg: lower K->A)."""
    sx = "L" if side > 0 else "R"
    b = lambda part: "%s_%s_%s" % (prefix, part, sx)   # noqa: E731
    H, K, A, toe, pivot = V(H), V(K), V(A), V(toe), V(pivot)
    C = V(C) if C is not None else None
    an.bone(b("upper"), H, K, parent)
    if C is not None:
        an.bone(b("lower"), K, C, b("upper"))
        an.bone(b("cannon"), C, A, b("lower"))
        an.bone(b("foot"), A, toe, b("cannon"))
    else:
        an.bone(b("lower"), K, A, b("upper"))
        an.bone(b("foot"), A, toe, b("lower"))
    l1 = (K - H).length
    nrest = (K - H).cross(A - K).normalized()
    if C is not None:
        l2, l3 = (C - K).length, (A - C).length
        dl, dc = (C - K).normalized(), (A - C).normalized()
        cr = dl.cross(dc)
        ref = nrest if plane else V(1, 0, 0)
        beta0 = math.degrees(dl.angle(dc, 0.0)) * (1.0 if cr.dot(ref) >= 0 else -1.0)
    else:
        l2, l3, beta0 = (A - K).length, 0.0, 0.0
    if plane:     # splayed leg: bend towards the rest knee (perpendicular to hip -> ankle)
        ax = (A - H).normalized()
        pole = (K - H) - ax * (K - H).dot(ax)
        pole = tuple(pole.normalized())
    lg = Leg(name=name, side=side, front=front, parent=parent, upper=b("upper"), lower=b("lower"),
             cannon=b("cannon") if C is not None else None, foot=b("foot"), H=H, K=K, C=C, A=A, toe=toe,
             pivot=pivot, pole=V(pole), flex_sign=flex_sign, l1=l1, l2=l2, l3=l3, beta0=beta0,
             r_top=radii[0], top_z=top_z, skin=skin, lift=lift, plane=plane, nrest=nrest)
    an.legs.append(lg)
    # the visible tube
    top = H.copy() if from_H else V(K.x, K.y, top_z)
    pts = [top, K] + ([C] if C is not None else []) + [A]
    prof = [(0.0, radii[0], radii[0]), (0.25, radii[1], radii[1])]
    if C is not None:
        sK = (K - top).length
        tot = sK + (C - K).length + (A - C).length
        prof = [(0.0, radii[0], radii[0]), (sK / tot, radii[1], radii[1]), ((sK + (C - K).length) / tot, radii[2], radii[2]),
                (1.0, radii[3], radii[3])]
    else:
        prof = [(0.0, radii[0], radii[0]), (0.35, radii[1], radii[1]), (1.0, radii[-1], radii[-1])]
    vf = loft(pts, prof, seg=seg, rings=rings, up=(0, -1, 0), caps=(0.5, 0.4), cap_rings=1)
    bones = [lg.lower] + ([lg.cannon] if C is not None else []) + [lg.foot]
    joints = [K] + ([C] if C is not None else []) + [A, toe]
    if from_H:
        rule = chain([lg.upper] + bones, [H] + joints, blend=[0.012 * an.size + 0.004] * (len(bones) + 1), pre=pre,
                     pre_blend=0.01 * an.size + 0.003)
    else:
        rule = chain(bones, joints, blend=[0.035 * an.size / 1.5 + 0.01] * len(bones), pre=lg.upper,
                     pre_blend=0.02 * an.size / 1.5 + 0.01)
    if paint is not None:
        m = paint
    elif sock is not None:
        m = (lambda c, n, z=sock, fk=foot_key, sk=sock_key: sk if c.z < z else fk)
    else:
        m = foot_key
    an.add(vf, m, rule)
    return lg


def leg_skin(an, base_rule, extra=None):
    """Body weights: the spine chain + a share of each leg's upper bone on the skin around the leg top."""
    def w(p):
        out = base_rule(p)
        for lg in an.legs:
            r = lg.r_top
            q = math.hypot(p.x - lg.K.x, p.y - lg.K.y)
            a = lg.skin * ss(r * 2.3, r * 0.9, q) * ss(lg.K.z + r * 2.2, lg.K.z, p.z)
            mix(out, lg.upper, a)
        if extra:
            extra(p, out)
        return out
    return w


def add_eye(an, head_vf, hf, name, parent, origin, direction, w, h, thick=None, shine=True, sunk=0.25,
            hl=(0.34, 0.28), key="dark", rule=None, tree=None):
    """Glossy cartoon eye (dark oval + two highlights) on the head surface; bone eye_<side> (local Z up)
    scales it shut for blinks."""
    thick = thick or 0.3 * w
    p, n = surf(head_vf, origin, direction, tree)
    up = hf.u - n * hf.u.dot(n)
    up.normalize()
    fwd = hf.f - n * hf.f.dot(n) - up * (hf.f - n * hf.f.dot(n)).dot(up)
    if fwd.length < 1e-6:
        fwd = up.cross(n)
    fwd.normalize()
    side = up.cross(n)
    c = p - n * (thick * sunk)
    an.bone(name, c, c + n * max(0.02, w), parent, zref=up)
    rule = rule or name
    an.add(ellip(frame_m(c, side, n, up), (w, thick, h), 8, 5), key, rule)
    if shine:
        c1 = c + n * (thick * 0.72) + up * (h * hl[0]) + fwd * (w * hl[1])
        an.add(ellip(frame_m(c1, side, n, up), (w * 0.34, thick * 0.35, h * 0.3), 8, 4), "shine", rule)
        c2 = c + n * (thick * 0.66) - up * (h * 0.42) - fwd * (w * 0.3)
        an.add(ellip(frame_m(c2, side, n, up), (w * 0.15, thick * 0.3, h * 0.13), 6, 3), "shine", rule)
    return p, n


# --------------------------------------------------------------------------- build: rig + meshes
def build_rig(an):
    arm = bpy.data.armatures.new(an.name + "_Rig")
    ob = bpy.data.objects.new(an.name, arm)
    link(ob)
    arm.display_type = "STICK"
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for (n, h, t, p, z) in an.bones:
        b = eb.new(n)
        b.head, b.tail = h, t
        d = (t - h).normalized()
        zz = z - d * z.dot(d)
        if zz.length < 1e-4:
            zz = V(0, -1, 0) if abs(d.z) < 0.9 else V(0, 0, 1)
        b.align_roll(zz.normalized())
        if p:
            b.parent = eb[p]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


def build_mesh(an, target, name):
    verts, faces, fmat, fsmooth, mats, vw = [], [], [], [], [], []
    for (vs, fs, m, smooth, rule, tg) in an.chunks:
        if tg != target:
            continue
        base = len(verts)
        for v in vs:
            w = rule(v) if callable(rule) else ({rule: 1.0} if isinstance(rule, str) else dict(rule))
            vw.append(w)
            verts.append(v)
        for f in fs:
            if callable(m):
                c = sum((vs[i] for i in f), Vector()) / len(f)
                nn = Vector()
                for i in range(len(f)):
                    a, b = vs[f[i]], vs[f[(i + 1) % len(f)]]
                    nn += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
                key = m(c, nn.normalized() if nn.length > 0 else Vector((0, 0, 1)))
            else:
                key = m
            if key not in mats:
                mats.append(key)
            faces.append(tuple(base + i for i in f))
            fmat.append(mats.index(key))
            fsmooth.append(smooth)
    if not verts:
        return None
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for k in mats:
        mn, col, rough = an.mats[k]
        me.materials.append(mat(mn, col, roughness=rough))
    me.polygons.foreach_set("material_index", fmat)
    me.polygons.foreach_set("use_smooth", fsmooth)
    me.update()
    nv = len(me.vertices)
    me.validate()
    assert len(me.vertices) == nv, "validate() removed vertices"
    ob = bpy.data.objects.new(name, me)
    link(ob)
    groups = {}
    for (n, h, t, p, z) in an.bones:
        groups[n] = ob.vertex_groups.new(name=n)
    for i, w in enumerate(vw):
        items = sorted(((b, x) for b, x in w.items() if x > 0.004), key=lambda t: -t[1])[:4]
        tot = sum(x for _, x in items)
        if tot <= 0:
            raise ValueError("vertex without weights in %s" % an.id)
        for b, x in items:
            groups[b].add([i], x / tot, "REPLACE")
    return ob


def assemble(an, bake=True):
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    rig = build_rig(an)
    meshes = []
    for target in ("Body", "Rooster"):
        ob = build_mesh(an, target, target)
        if ob is not None:
            meshes.append(ob)
    if bake:
        dist = 0.1 * an.size
        for ob in meshes:
            others = [o for o in meshes if o is not ob]
            for o in others:     # each mesh bakes alone (the hen hides the rooster parts)
                o.hide_render = True
            bake_vertex_ao([ob], samples=24, distance=dist, floor=0.52, gamma=0.8, ground=True)
            for o in others:
                o.hide_render = False
    for ob in meshes:
        ob.parent = rig
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
    return rig, meshes


# --------------------------------------------------------------------------- pose solver
class Pose:
    __slots__ = ("rot", "loc", "scl", "legs", "chains")

    def __init__(self):
        self.rot, self.loc, self.scl, self.legs, self.chains = {}, {}, {}, {}, {}

    def r(self, bone, pitch=0.0, yaw=0.0, roll=0.0):
        m = D(pitch, yaw, roll)
        self.rot[bone] = m @ self.rot[bone] if bone in self.rot else m
        return self

    def rm(self, bone, M3):
        self.rot[bone] = M3 @ self.rot[bone] if bone in self.rot else M3.copy()
        return self

    def mv(self, bone, dx=0.0, dy=0.0, dz=0.0):
        self.loc[bone] = self.loc.get(bone, Vector()) + V(dx, dy, dz)
        return self

    def sc(self, bone, sx=1.0, sy=1.0, sz=1.0):
        o = self.scl.get(bone, (1.0, 1.0, 1.0))
        self.scl[bone] = (o[0] * sx, o[1] * sy, o[2] * sz)
        return self


def orth_frame(Y, xhint):
    X = xhint - Y * xhint.dot(Y)
    if X.length < 1e-8:
        X = Vector((1, 0, 0)) - Y * Y.x
    X.normalize()
    Z = X.cross(Y)
    return Matrix((X, Y, Z)).transposed()


class Solver:
    def __init__(self, an, ob):
        self.an, self.ob = an, ob
        bs = ob.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in bs}
        self.par = {b.name: (b.parent.name if b.parent else None) for b in bs}
        self.r3 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.r3i = {n: m.inverted() for n, m in self.r3.items()}
        self.rel = {n: (self.rest[p].inverted() @ self.rest[n] if p else self.rest[n].copy()) for n, p in self.par.items()}
        names = [b.name for b in bs]
        order, seen = [], set()
        while len(order) < len(names):
            for n in names:
                if n not in seen and (self.par[n] is None or self.par[n] in seen):
                    order.append(n)
                    seen.add(n)
        self.order = order
        self.leg_of = {lg.upper: lg for lg in an.legs}
        self.leg_bones = set()
        for lg in an.legs:
            self.leg_bones.update(b for b in (lg.upper, lg.lower, lg.cannon, lg.foot) if b)
        self.chain_of = {c["b1"]: c for c in an.chains.values()}
        self.nrest_of = {}
        for lg in an.legs:
            if lg.plane:
                for bn in (lg.upper, lg.lower, lg.cannon):
                    if bn:
                        self.nrest_of[bn] = lg.nrest
        self.err = {}

    def _set(self, n, base, Y, posed, basis):
        b3 = base.to_3x3().normalized()
        M3 = orth_frame(Y, b3.col[0])
        q = (b3.inverted() @ M3).to_quaternion()
        posed[n] = base @ q.to_matrix().to_4x4()
        basis[n] = (Vector(), q, Vector((1.0, 1.0, 1.0)))

    def _set_plane(self, n, base, Y, nrm, posed, basis):
        """leg bone along Y whose twist follows the leg plane normal (splayed legs)."""
        Y0 = self.r3[n].col[1].normalized()
        n0 = self.nrest_of[n]
        n0 = (n0 - Y0 * n0.dot(Y0)).normalized()
        n1 = (nrm - Y * nrm.dot(Y)).normalized()
        B0 = Matrix((Y0, n0, Y0.cross(n0))).transposed()
        B1 = Matrix((Y, n1, Y.cross(n1))).transposed()
        self._rot_to(n, base, (B1 @ B0.transposed()) @ self.r3[n], posed, basis)

    def _rot_to(self, n, base, Mw3, posed, basis):
        b3 = base.to_3x3().normalized()
        q = (b3.inverted() @ Mw3).to_quaternion()
        posed[n] = base @ q.to_matrix().to_4x4()
        basis[n] = (Vector(), q, Vector((1.0, 1.0, 1.0)))

    def leg_target(self, lg, tg):
        th = tg.get("hoof", 0.0)
        if "A" in tg:
            return V(tg["A"]), th
        return lg.pivot + Rx(th) @ (lg.A - lg.pivot), th

    def virtual(self, lg, flex):
        if lg.cannon is None:
            return lg.l2, 0.0, 0.0
        beta = rad(lg.beta0 + lg.flex_sign * flex)
        vx, vy = lg.l2 + lg.l3 * math.cos(beta), lg.l3 * math.sin(beta)
        return math.hypot(vx, vy), math.atan2(vy, vx), beta

    def _leg(self, lg, pose, posed, basis):
        base_u = posed[self.par[lg.upper]] @ self.rel[lg.upper]
        H = base_u.translation.copy()
        tg = pose.legs.get(lg.name, {})
        A, th = self.leg_target(lg, tg)
        Lv, gam, beta = self.virtual(lg, tg.get("flex", 0.0))
        lat = base_u.to_3x3().col[0].normalized()
        if lat.x < 0:
            lat = -lat
        pole = V(tg.get("pole", lg.pole))
        if lg.plane:
            Pn = self.par[lg.upper]
            pole = (posed[Pn].to_3x3().normalized() @ self.r3i[Pn]) @ pole
        K, Ar = CH.two_bone(H, A, lg.l1, Lv, pole, soft=0.985)
        if lg.plane:     # splayed legs (frog): flex about the rest leg plane's normal, carried by the hips
            Pn = self.par[lg.upper]
            Dp = posed[Pn].to_3x3().normalized() @ self.r3i[Pn]
            lat = Dp @ lg.nrest
            ax = (A - H).normalized()
            lat = (lat - ax * lat.dot(ax)).normalized()
        vhat = (Ar - K).normalized()
        d_l = Matrix.Rotation(-gam, 3, lat) @ vhat
        setb = (lambda n, base, Y: self._set_plane(n, base, Y, lat, posed, basis)) if lg.plane else \
            (lambda n, base, Y: self._set(n, base, Y, posed, basis))
        setb(lg.upper, base_u, (K - H).normalized())
        base_l = posed[lg.upper] @ self.rel[lg.lower]
        setb(lg.lower, base_l, d_l)
        last = lg.lower
        if lg.cannon:
            d_c = Matrix.Rotation(beta, 3, lat) @ d_l
            base_c = posed[lg.lower] @ self.rel[lg.cannon]
            setb(lg.cannon, base_c, d_c)
            last = lg.cannon
        base_f = posed[last] @ self.rel[lg.foot]
        fr = tg.get("foot_rot")
        Mw = (Rx(th) @ (fr if fr is not None else Matrix.Identity(3))) @ self.r3[lg.foot]
        self._rot_to(lg.foot, base_f, Mw, posed, basis)
        got = posed[lg.foot].translation
        self.err[lg.name] = (got - A).length

    def _chain(self, ch, pose, posed, basis):
        tg = pose.chains[ch["name"]]
        b1, b2, end = ch["b1"], ch["b2"], ch.get("end")
        base1 = posed[self.par[b1]] @ self.rel[b1]
        S = base1.translation.copy()
        E, Rr = CH.two_bone(S, V(tg["T"]), ch["l1"], ch["l2"], V(tg.get("pole", ch["pole"])), soft=0.99)
        self._set(b1, base1, (E - S).normalized(), posed, basis)
        base2 = posed[b1] @ self.rel[b2]
        self._set(b2, base2, (Rr - E).normalized(), posed, basis)
        if end and "end_rot" in tg:
            basee = posed[b2] @ self.rel[end]
            self._rot_to(end, basee, tg["end_rot"] @ self.r3[end], posed, basis)

    def solve(self, pose, legs=True):
        posed, basis = {}, {}
        I4 = Matrix.Identity(4)
        for n in self.order:
            if n in basis:
                continue
            if n in self.leg_bones:
                if legs and n in self.leg_of:
                    self._leg(self.leg_of[n], pose, posed, basis)
                continue
            if n in self.chain_of and self.chain_of[n]["name"] in pose.chains:
                self._chain(self.chain_of[n], pose, posed, basis)
                continue
            p = self.par[n]
            if p is not None and p not in posed:
                continue      # (a child of a leg bone while legs are off)
            base = (posed[p] if p else I4) @ self.rel[n]
            Dm = pose.rot.get(n)
            q = (self.r3i[n] @ Dm @ self.r3[n]).to_quaternion() if Dm is not None else Quaternion()
            loc = pose.loc.get(n)
            l = self.r3i[n] @ V(loc) if loc is not None else Vector()
            s = Vector(pose.scl.get(n, (1.0, 1.0, 1.0)))
            posed[n] = base @ Matrix.LocRotScale(l, q, s)
            basis[n] = (l, q, s)
        return basis, posed

    # ---- keep planted feet reachable: lower / pitch the body where a leg would have to overstretch
    def reach_needs(self, pose):
        _, posed = self.solve(pose, legs=False)
        out = {}
        for lg in self.an.legs:
            H = (posed[self.par[lg.upper]] @ self.rel[lg.upper]).translation
            tg = pose.legs.get(lg.name, {})
            A, _ = self.leg_target(lg, tg)
            Lv, _, _ = self.virtual(lg, tg.get("flex", 0.0))
            rmax = 0.975 * (lg.l1 + Lv)
            d = A - H
            dz = 0.0
            if d.length > rmax:
                hz = math.hypot(d.x, d.y)
                dz = (H.z - A.z) - math.sqrt(max(rmax * rmax - hz * hz, 0.0))
                dz = min(dz, 0.2 * (lg.l1 + Lv))
            out[lg.name] = dz
        return out, posed

    def reach_fix(self, poses, loop, sigma=1.3, root="hips"):
        legs = self.an.legs
        fr = [lg for lg in legs if lg.front]
        hi = [lg for lg in legs if not lg.front]
        if not legs:
            return
        yf = sum(lg.H.y for lg in fr) / len(fr) if fr else None
        yh = sum(lg.H.y for lg in hi) / len(hi) if hi else None
        Dl = abs(yh - yf) if (fr and hi) else 1.0
        for it in range(2):
            dh, dp = [], []
            for p in poses:
                need, _ = self.reach_needs(p)
                a = max([need[lg.name] for lg in hi] or [0.0])
                b = max([need[lg.name] for lg in fr] or [0.0])
                if not hi:
                    a = b
                if not fr:
                    b = a
                dh.append(a)
                dp.append(math.degrees(math.asin(clamp((b - a) / Dl, -0.4, 0.4))))
            if it == 0:
                dh, dp = smooth_cyclic(dh, sigma, loop), smooth_cyclic(dp, sigma, loop)
            for p, a, b in zip(poses, dh, dp):
                if abs(a) > 1e-6:
                    p.mv(root, dz=-a)
                if abs(b) > 1e-6:
                    p.r(root, pitch=b)


# --------------------------------------------------------------------------- gait engine
LS_WALK = {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}      # lateral-sequence 4-beat walk
TROT = {"FL": 0.0, "HR": 0.0, "FR": 0.5, "HL": 0.5}           # diagonal pairs
BOUND = {"HL": 0.0, "HR": 0.07, "FL": 0.45, "FR": 0.53}       # half-bound / gallop (cat, dog)
BIPED = {"L": 0.0, "R": 0.5}


class Gait:
    def __init__(self, N, stride, stance, phase, lift, flex=(50.0, 35.0), hoof=40.0, roll=18.0, centre=1.0,
                 lift_bias=0.85, splay=0.0):
        self.N, self.stride, self.stance, self.phase = N, stride, stance, phase
        self.lift, self.flex, self.hoof, self.roll = lift, flex, hoof, roll
        self.centre, self.lift_bias, self.splay = centre, lift_bias, splay

    def per(self, lg, v):
        if isinstance(v, (tuple, list)):
            return v[0] if lg.front else v[1]
        return v

    def speed(self):
        return self.stride / (self.N / FPS)

    def leg(self, lg, f):
        """(ankle target, hoof pitch, flex) of one leg at frame f."""
        g = self
        u = (f / g.N - g.phase[lg.name]) % 1.0
        sig, L = g.stance, g.stride
        c = V(0, (lg.H.y - lg.A.y) * g.centre, 0)      # stance centred under the hip/shoulder joint
        piv0 = lg.pivot + c
        off = lg.A - lg.pivot
        roll, hoof = g.per(lg, g.roll), g.per(lg, g.hoof)
        if u < sig:
            s = u / sig
            piv = piv0 + V(0, (s - 0.5) * sig * L, 0)
            th = roll * ss(0.7, 1.0, s)
            return dict(A=piv + Rx(th) @ off, hoof=th, flex=0.0)
        w = (u - sig) / (1.0 - sig)
        A0 = piv0 + V(0, 0.5 * sig * L, 0) + Rx(roll) @ off
        A1 = piv0 - V(0, 0.5 * sig * L, 0) + off
        e = sstep(w) * 0.85 + w * 0.15
        A = A0.lerp(A1, e)
        A.z += g.per(lg, g.lift) * math.sin(math.pi * clamp(w) ** g.lift_bias)
        A.x += lg.side * g.splay * math.sin(math.pi * w)
        th = roll * (1.0 - ss(0.0, 0.4, w)) + hoof * math.sin(math.pi * clamp(w / 0.82)) ** 1.5
        fl = g.per(lg, g.flex) * math.sin(math.pi * clamp(w / 0.92)) ** 1.2
        return dict(A=A, hoof=th, flex=fl)

    def swing_mid(self, name):
        return (self.phase[name] + self.stance + 0.5 * (1.0 - self.stance)) % 1.0


# --------------------------------------------------------------------------- bake / export
def bake(an, solver, clips):
    ob = solver.ob
    if ob.animation_data is None:
        ob.animation_data_create()
    acts, report = {}, {}
    for name, fn in clips.items():
        N, loop, poses = fn(an, solver)
        assert len(poses) == N + 1, (name, len(poses), N)
        rows, prev, err = [], {}, {}
        for f in range(N + 1):
            basis, _posed = solver.solve(poses[f])
            for k, v in solver.err.items():
                err[k] = max(err.get(k, 0.0), v)
            row = {}
            for pb in ob.pose.bones:
                l, q, s = basis[pb.name]
                q = q.copy()
                if pb.name in prev and prev[pb.name].dot(q) < 0:
                    q.negate()
                prev[pb.name] = q
                row[pb.name] = (l.copy(), q, Vector(s))
            rows.append(row)
        if loop:
            rows[N] = {k: (v[0].copy(), v[1].copy(), v[2].copy()) for k, v in rows[0].items()}
            for k in rows[N]:
                if rows[N - 1][k][1].dot(rows[N][k][1]) < 0:
                    print(f"  !! {an.id}/{name}: bone {k} flips hemisphere at the loop seam")
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        ob.animation_data.action = act
        for pb in ob.pose.bones:
            l, q, s = rows[0][pb.name]
            pb.location, pb.rotation_quaternion, pb.scale = l, q, s
            pb.keyframe_insert("rotation_quaternion", frame=0, group=pb.name)
            if pb.name in an.loc_bones:
                pb.keyframe_insert("location", frame=0, group=pb.name)
            if pb.name in an.scale_bones:
                pb.keyframe_insert("scale", frame=0, group=pb.name)
        for fc in act.fcurves:
            bname = fc.data_path.split('"')[1]
            prop = fc.data_path.rsplit(".", 1)[1]
            k = {"location": 0, "rotation_quaternion": 1, "scale": 2}[prop]
            vals = [rows[f][bname][k][fc.array_index] for f in range(N + 1)]
            fc.keyframe_points.clear()
            fc.keyframe_points.add(N + 1)
            co = []
            for f, v in enumerate(vals):
                co += [float(f), v]
            fc.keyframe_points.foreach_set("co", co)
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.update()
        act.use_frame_range = True
        act.frame_start, act.frame_end = 0, N
        act.use_cyclic = loop
        # checks: largest bone turn between frames (1/30 s)
        worst = (0.0, "")
        for f in range(1, N + 1):
            for b in rows[f]:
                a = CH.quat_angle(rows[f - 1][b][1], rows[f][b][1])
                if a > worst[0]:
                    worst = (a, "%s@%d" % (b, f))
        report[name] = dict(N=N, loop=loop, turn=round(worst[0], 1), at=worst[1],
                            foot_err_mm=round(1000 * max(err.values()), 1) if err else 0.0)
        acts[name] = act
    ob.animation_data.action = acts.get("idle")
    return acts, report


def loops_import_text(txt, loops):
    import re
    block = ["_subresources={", "\"animations\": {"]
    block += [",\n".join("\"%s\": {\n\"settings/loop_mode\": 1\n}" % n for n in loops)]
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
            skipping = not line.rstrip().endswith("{}") and CH._brace_balance(line) != 0
            continue
        out.append(line)
    if not done:
        i = max(k for k, l in enumerate(out) if l.strip()) + 1
        out[i:i] = block
    new = "\n".join(out)
    assert CH._brace_balance(new) == 0
    return new


def mark_loops(name, loops):
    """Loop flags for Godot's importer (loop_mode = LINEAR) in the .glb.import sidecar. Writes a
    minimal sidecar when there is none yet (Godot fills in the rest on import)."""
    path = os.path.join(MODELS_DIR, name + ".glb.import")
    if not os.path.exists(path):
        txt = "[remap]\n\nimporter=\"scene\"\nimporter_version=1\ntype=\"PackedScene\"\n\n[params]\n\n" \
              "meshes/ensure_tangents=false\nmeshes/generate_lods=false\nanimation/fps=30\n"
    else:
        txt = open(path).read()
    # like the villagers: no tangents (no normal maps), no automatic LODs on the skinned mesh
    txt = txt.replace("meshes/ensure_tangents=true", "meshes/ensure_tangents=false")
    txt = txt.replace("meshes/generate_lods=true", "meshes/generate_lods=false")
    new = loops_import_text(txt, loops)
    if new != txt:
        open(path, "w").write(new)
        print("[import] loops marked in", os.path.basename(path))


def glb_check(path, loops):
    """Exported rotation keys: most turn per 1/60 s, hemisphere flips, loop seams."""
    import struct
    data, js, (b0, blen) = CH._glb_read(path)
    blob = data[b0: b0 + blen]

    def acc(i):
        a = js["accessors"][i]
        bv = js["bufferViews"][a["bufferView"]]
        k = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
        o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 4 * k)
        return [struct.unpack_from("<%df" % k, blob, o + j * stride) for j in range(a["count"])]
    out = {}
    for an in js.get("animations", []):
        worst, flips, seam = 0.0, 0, 0.0
        for ch in an["channels"]:
            if ch["target"]["path"] != "rotation":
                continue
            s = an["samplers"][ch["sampler"]]
            t, q = acc(s["input"]), [Quaternion((w, x, y, z)) for (x, y, z, w) in acc(s["output"])]
            for j in range(1, len(q)):
                flips += q[j - 1].dot(q[j]) < 0.0
                a = CH.quat_angle(q[j - 1], q[j]) * min(1.0, (1.0 / 60.0) / max(1e-6, t[j][0] - t[j - 1][0]))
                worst = max(worst, a)
            if an["name"] in loops:
                seam = max(seam, CH.quat_angle(q[0], q[-1]))
        out[an["name"]] = (round(worst, 1), flips, round(seam, 2))
    return out


def export(an, rig, meshes, extras):
    for k, v in extras.items():
        rig[k] = v
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for m in meshes:
        m.select_set(True)
    path = os.path.join(MODELS_DIR, an.name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
        export_materials="EXPORT", export_animations=True, export_extras=True, export_cameras=False,
        export_lights=False, export_vertex_color="ACTIVE", export_animation_mode="ACTIONS", export_skins=True,
        export_force_sampling=True, export_optimize_animation_size=True,
        export_optimize_animation_keep_anim_armature=False)
    for k in extras:
        del rig[k]
    return path


# --------------------------------------------------------------------------- previews
def preview_materials():
    for m in bpy.data.materials:
        if not m.name.startswith("Animal") or not m.use_nodes:
            continue
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        if "VCol" in nt.nodes:
            continue
        a = nt.nodes.new("ShaderNodeAttribute")
        a.name, a.attribute_name = "VCol", "Col"
        mx = nt.nodes.new("ShaderNodeMix")
        mx.name, mx.data_type, mx.blend_type = "VMul", "RGBA", "MULTIPLY"
        mx.inputs[0].default_value = 1.0
        mx.inputs[6].default_value = b.inputs["Base Color"].default_value
        nt.links.new(a.outputs["Color"], mx.inputs[7])
        nt.links.new(mx.outputs[2], b.inputs["Base Color"])


def set_frame(ob, act, f):
    ob.animation_data.action = act
    bpy.context.scene.frame_set(int(f))
    bpy.context.view_layer.update()


def snaps(meshes, tag, loc, yaw):
    return [CH.snapshot(m, "snap%s_%s" % (tag, m.name), loc, yaw) for m in meshes if not m.hide_render]


def recolour(objs, an, var):
    """give snapshot copies the variant's fur / mark colours (material copies, previews only)."""
    keys = {"AnimalFur_" + an.id: "fur", "AnimalMark_" + an.id: "mark", "AnimalMark2_" + an.id: "mark2"}
    for o in objs:
        me = o.data
        for i, m in enumerate(me.materials):
            if m is None:
                continue
            base = m.name.split("__")[0]
            k = keys.get(base)
            if k and var.get(k):
                m2 = m.copy()
                col = common.hex_rgba(var[k])
                bs = m2.node_tree.nodes.get("Principled BSDF")
                vm = m2.node_tree.nodes.get("VMul")
                if vm is not None:
                    vm.inputs[6].default_value = col
                elif bs is not None:
                    bs.inputs["Base Color"].default_value = col
                me.materials[i] = m2


def variant_snaps(an, rig, meshes, acts, vi, loc, yaw, frame=10):
    var = an.variants[vi] if an.variants else {}
    set_frame(rig, acts["idle"], frame)
    show = [m for m in meshes if m.name != "Rooster" or var.get("rooster")]
    sn = [CH.snapshot(m, "V%s_%d_%s" % (an.id, vi, m.name), loc, yaw) for m in show]
    if vi > 0:
        recolour(sn, an, var)
    return sn


def render_preview_variants(an, rig, meshes, acts, path=None):
    """default colours + the second variant side by side, 3/4 game-like view."""
    L = an.meta["length"]
    n = 2 if len(an.variants) > 1 else 1
    gap = max(an.meta["width"], L * 0.55) * 1.25
    sn = []
    for vi in range(n):
        sn += variant_snaps(an, rig, meshes, acts, vi, ((vi - (n - 1) / 2) * gap, 0, 0), 28.0, 4 + 36 * vi)
    for m in meshes:
        m.hide_render = True
    tmp = CH._scene_setup(768, 512, samples=20, ground="#8fb35c")
    h = an.meta["height"]
    k = max(L * 1.2, h * 1.9, (gap * (n - 1) + L) * 0.85)
    tmp.append(CH._camera((0, 0, h * 0.42), 38.0, 0.0, 10 * k, ortho=1.3 * k))
    bpy.context.scene.render.filepath = path or os.path.join(PREVIEW_DIR, an.name + ".png")
    bpy.ops.render.render(write_still=True)
    CH._cleanup(sn + tmp)
    for m in meshes:
        m.hide_render = False
    print("[preview]", bpy.context.scene.render.filepath)


SHEET_VIEWS = {"game": (25.0, 45.0), "side": (90.0, 4.0), "front": (0.0, 8.0), "top": (0.0, 80.0)}


def render_sheet(an, rig, meshes, acts, clip, path, n=8, views=("game", "side")):
    from PIL import Image, ImageDraw
    act = acts[clip]
    N = int(act.frame_range[1])
    loop = act.use_cyclic
    frames = [round(i * N / (n if loop else n - 1)) for i in range(n)]
    rows = []
    for view in views:
        cell = (an.meta["length"] if view == "side" else max(an.meta["width"], an.meta["height"]) * 1.25) * 1.08
        sn = []
        for i, f in enumerate(frames):
            set_frame(rig, act, f)
            x = (i - (n - 1) / 2) * cell
            sn += snaps(meshes, "%d" % i, (x, 0, 0), SHEET_VIEWS[view][0])
        for m in meshes:
            m.hide_render = True
        px = 150
        tmp = CH._scene_setup(n * px, 2 * px, samples=10)
        H = an.meta["height"]
        pitch = SHEET_VIEWS[view][1]
        tmp.append(CH._camera((0, 0, H * (0.4 if pitch > 20 else 0.5)), pitch, 0.0, 20 * an.size, ortho=n * cell))
        out = path.replace(".png", "_%s.png" % view)
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        CH._cleanup(sn + tmp)
        for m in meshes:
            m.hide_render = False
        rows.append(out)
    ims = [Image.open(p).convert("RGB") for p in rows]
    sheet = Image.new("RGB", (ims[0].width, sum(i.height for i in ims) + 18), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    dr.text((6, 3), "%s / %s  (%d frames @30fps)  frames: %s" % (an.id, clip, N, frames), fill=(255, 255, 255))
    y = 18
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height
    sheet.save(path)
    for p in rows:
        os.remove(p)
    print("[sheet]", path)


def render_views(an, rig, meshes, acts, path, clip="idle", frame=0, views=(("game", 28.0, 45.0), ("side", 90.0, 6.0),
                                                                           ("front", 0.0, 10.0), ("top", 28.0, 70.0))):
    if "--hen" in sys.argv:
        for m in meshes:
            if m.name == "Rooster":
                m.hide_render = True
        meshes = [m for m in meshes if m.name != "Rooster"]
    """One frame from several views side by side (quick look while modelling)."""
    from PIL import Image
    set_frame(rig, acts[clip], frame)
    ims = []
    L = max(an.meta["length"], an.meta["height"] * 1.2)
    for (tag, yaw, pitch) in views:
        sn = snaps(meshes, tag, (0, 0, 0), yaw)
        for m in meshes:
            m.hide_render = True
        tmp = CH._scene_setup(400, 400, samples=12, ground="#8fb35c")
        tmp.append(CH._camera((0, 0, an.meta["height"] * 0.45), pitch, 0.0, 12 * L, ortho=L * 1.2))
        out = path.replace(".png", "_%s.png" % tag)
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        CH._cleanup(sn + tmp)
        for m in meshes:
            m.hide_render = False
        ims.append(out)
    pics = [Image.open(p).convert("RGB") for p in ims]
    sheet = Image.new("RGB", (sum(i.width for i in pics), pics[0].height))
    x = 0
    for im in pics:
        sheet.paste(im, (x, 0))
        x += im.width
    sheet.save(path)
    for p in ims:
        os.remove(p)
    print("[views]", path)


# =========================================================================== shared clip helpers
def quad_bones(an):
    return dict(tails=[b[0] for b in an.bones if b[0].startswith("tail_")])


def seq(N):
    return [Pose() for _ in range(N + 1)]


def ears(p, back=0.0, down=0.0, dl=None):
    """both ears: back (+ = tips back), down (+ = tips droop). dl = (back, down) extra on the left ear only."""
    for side, sx in ((1, "L"), (-1, "R")):
        b, d = back, down
        if dl and side > 0:
            b += dl[0]
            d += dl[1]
        p.r("ear_" + sx, yaw=side * b, roll=side * d)


def eyes(p, k):
    if k != 1.0:
        p.sc("eye_L", 1.0, 1.0, k)
        p.sc("eye_R", 1.0, 1.0, k)


def tail_wave(p, tails, f, N, amp, cycles=1, lag=0.12, axis="roll", base=0.0, base_axis="pitch", grow=1.25):
    for i, t in enumerate(tails):
        v = amp * (grow ** i) * math.sin(TAU * (cycles * f / N - lag * i))
        kw = {axis: v}
        if base:
            kw[base_axis] = kw.get(base_axis, 0.0) + (base if i == 0 else base * 0.3)
        p.r(t, **kw)


# ----------------------------------------------------------------- quadruped clips
def q_walk(kind):
    def clip(an, solver):
        P = an.anim[kind]
        g = P["gait"]
        N = g.N
        poses = seq(N)
        tails = quad_bones(an)["tails"]
        fl_td = g.phase["FL"]
        hl_sm = g.swing_mid("HL")
        fl_sm = g.swing_mid("FL")
        for f, p in enumerate(poses):
            ph = f / N
            for lg in an.legs:
                p.legs[lg.name] = g.leg(lg, f)
            if kind == "walk":
                p.mv("hips", dz=P.get("bob", 0.01) * cyc(2 * (ph - fl_td - 0.08)))
            else:
                p.mv("hips", dz=-P.get("bob", 0.03) * cyc(2 * (ph - g.stance / 2)))
            hr = P.get("hip_roll", 2.0) * cyc(ph - hl_sm)
            cr = P.get("chest_roll", 1.5) * cyc(ph - fl_sm)
            p.r("hips", pitch=P.get("pitch", 0.0) * syc(2 * ph + P.get("pitch_ph", 0.0)) + P.get("lean", 0.0),
                yaw=P.get("hip_yaw", 1.2) * syc(ph - hl_sm), roll=hr)
            p.r("spine", roll=-hr * 0.5, pitch=P.get("flexs", 0.0) * syc(ph + P.get("flex_ph", 0.0)))
            p.r("chest", roll=cr - hr * 0.5, yaw=-P.get("hip_yaw", 1.2) * 0.8 * syc(ph - hl_sm),
                pitch=P.get("flexc", 0.0) * syc(ph + P.get("flex_ph", 0.0)))
            nod = P.get("nod", 3.0) * cyc(2 * (ph - fl_td - P.get("nod_lag", 0.12)))
            p.r("neck", pitch=nod + P.get("neck", 0.0), roll=-cr * 0.6)
            p.r("head", pitch=-nod * P.get("head_k", 0.4) + P.get("head", 0.0), yaw=-P.get("hip_yaw", 1.2) * 0.5 * syc(ph - hl_sm))
            ears(p, back=P.get("ear_back", 0.0), down=P.get("ear", 3.0) * cyc(2 * (ph - fl_td - 0.2)))
            tail_wave(p, tails, f, N, P.get("tail", 8.0), cycles=1, lag=0.1, axis=P.get("tail_axis", "roll"),
                      base=P.get("tail_up", 0.0), base_axis=P.get("tail_up_axis", "pitch"))
            if "jaw" in P:
                p.r("jaw", pitch=P["jaw"])
            eyes(p, 1.0)
        solver.reach_fix(poses, True)
        return N, True, poses
    return clip


def q_idle(an, solver):
    P = an.anim.get("idle", {})
    N = P.get("N", 120)
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    look = Kc(P.get("look", [(0, 0), (22, 0), (40, 14), (62, 14), (80, -9), (100, -9), (120, 0)]), N)
    tilt = Kc([(0, 0), (40, 4), (62, 5), (80, -3), (100, -3), (120, 0)], N)
    shift = Kc([(0, 0), (30, 1), (60, 0), (90, -1), (120, 0)], N)
    for f, p in enumerate(poses):
        br = syc(3 * f / N)                          # breathing: 3 per loop
        s = shift(f)
        p.mv("hips", dx=0.008 * an.size * s, dz=-0.003 * an.size * (1 + br) * 0.5)
        p.r("hips", roll=1.0 * s)
        p.r("spine", pitch=-0.5 * br, roll=-0.6 * s)
        p.r("chest", pitch=-0.6 * br, roll=-0.3 * s)
        p.r("neck", yaw=look(f) * 0.55, pitch=P.get("neck", 0.0) + 1.5 * syc(f / N + 0.2))
        p.r("head", yaw=look(f) * 0.45, roll=tilt(f), pitch=P.get("head", 0.0) + 1.0 * syc(2 * f / N))
        # ear flicks
        fl = math.exp(-((f - 34) / 3.0) ** 2) * 28.0
        fr = math.exp(-((f - 86) / 3.0) ** 2) * 26.0
        for side, sx, fk in ((1, "L", fl), (-1, "R", fr)):
            p.r("ear_" + sx, yaw=side * (fk + 3 * syc(f / N)), roll=side * (P.get("ear_down", 0.0) + 2.0 * br))
        # tail: slow sway + a swish
        sw = math.exp(-((f - 58) / 9.0) ** 2)
        for i, t in enumerate(tails):
            v = 4.0 * syc(f / N - 0.08 * i) + 26.0 * sw * math.sin(TAU * (f - 50) / 16.0 - 0.6 * i) * (1.2 ** i)
            p.r(t, **{P.get("tail_axis", "roll"): v})
            if i == 0 and P.get("tail_up"):
                p.r(t, **{P.get("tail_up_axis", "pitch"): P["tail_up"]})
        k = min(blink(f, 18), blink(f, 97), blink(f, 103))
        eyes(p, k)
        if P.get("chew"):     # cud chewing: jaw grinds sideways
            c = P["chew"]
            p.r("jaw", pitch=c * (0.5 + 0.5 * syc(8 * f / N)), yaw=c * 0.6 * syc(8 * f / N + 0.25))
        else:
            p.r("jaw", pitch=0.0)
    solver.reach_fix(poses, True)
    return N, True, poses


def q_eat(an, solver):
    P = an.anim["eat"]
    N = P.get("N", 72)
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    for f, p in enumerate(poses):
        ph = f / N
        tear = math.exp(-((f - 40) / 3.5) ** 2)
        p.mv("hips", dy=-0.015 * an.size, dz=-P.get("drop", 0.01) * an.size)
        p.r("hips", pitch=P.get("lean", 3.0))
        p.r("spine", pitch=0.4 * syc(2 * ph))
        p.r("neck", pitch=P["neck"] + 2.0 * syc(2 * ph) - 6.0 * tear, yaw=4.0 * syc(ph))
        p.r("head", pitch=P["head"] + 2.0 * syc(4 * ph + 0.1) + 3.0 * tear, yaw=6.0 * syc(ph + 0.15), roll=3.0 * syc(ph))
        p.r("jaw", pitch=P.get("chew", 9.0) * (0.5 - 0.5 * cyc(P.get("chews", 6) * ph)))
        ears(p, back=-5.0, down=P.get("ear_down", 10.0) + 2 * syc(2 * ph),
             dl=(24.0 * math.exp(-((f - 16) / 3.0) ** 2), 0.0))
        tail_wave(p, tails, f, N, P.get("tail", 10.0), cycles=2, lag=0.1, axis=P.get("tail_axis", "roll"),
                  base=P.get("tail_up", 0.0), base_axis=P.get("tail_up_axis", "pitch"))
        eyes(p, blink(f, 56, 6))
    solver.reach_fix(poses, True)
    return N, True, poses


def q_call(an, solver):
    """head up, mouth open (the sound starts at call_open), hold with a tremble, back to rest."""
    P = an.anim["call"]
    N = P.get("N", 42)
    o0, o1 = P.get("open", (12, 30))
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    up = Kc([(0, 0), (5, -0.15), (o0 - 2, 1.0), (o1, 1.05), (o1 + 7, 0.3), (N, 0)])
    jaw = Kc([(0, 0), (o0 - 3, 0), (o0 + 1, 1.0), (o1 - 2, 0.95), (o1 + 4, 0), (N, 0)])
    for f, p in enumerate(poses):
        u, j = up(f), jaw(f)
        trem = math.sin(TAU * f / 5.0) * j
        p.r("hips", pitch=-1.5 * u)
        p.r("chest", pitch=-2.0 * u)
        p.r("neck", pitch=P.get("neck", -22.0) * u + 1.0 * trem)
        p.r("head", pitch=P.get("head", -18.0) * u + 1.2 * trem)
        p.r("jaw", pitch=P.get("jaw", 22.0) * j)
        ears(p, back=P.get("ear_back", 18.0) * u, down=P.get("ear_down", -6.0) * u)
        tail_wave(p, tails, f, N, P.get("tail", 6.0) * u, cycles=2, lag=0.1, axis=P.get("tail_axis", "roll"),
                  base=P.get("tail_up", 0.0) * u, base_axis=P.get("tail_up_axis", "pitch"))
        eyes(p, 1.0 - 0.45 * j)
    solver.reach_fix(poses, False)
    return N, False, poses


QUAD_CLIPS = {"idle": q_idle, "walk": q_walk("walk"), "run": q_walk("run"), "eat": q_eat, "call": q_call}


# =========================================================================== species helpers
DARK, SHINE = "#2e2522", "#fffaf0"


def std_mats(an, fur, mark, mark2=None, horn=None):
    an.mat("fur", "AnimalFur_" + an.id, fur)
    an.mat("mark", "AnimalMark_" + an.id, mark)
    if mark2:
        an.mat("mark2", "AnimalMark2_" + an.id, mark2)
    an.mat("dark", "AnimalDark", DARK, 0.5)
    an.mat("shine", "AnimalShine", SHINE, 0.4)
    if horn:
        an.mat("horn", "AnimalHorn", horn, 0.6)


def spine3(an, pts):
    """hips (root) > spine > chest from 4 points along the back (rear to front)."""
    an.bone("hips", pts[0], pts[1])
    an.bone("spine", pts[1], pts[2], "hips")
    an.bone("chest", pts[2], pts[3], "spine")
    P = [V(q) for q in pts]
    ext = an.size * 0.4
    joints = [P[0] + (P[0] - P[1]).normalized() * ext, P[1], P[2], P[3] + (P[3] - P[2]).normalized() * ext]
    return chain(["hips", "spine", "chest"], joints, blend=[0.09 * an.size, 0.08 * an.size])


def leg_pair(an, prefix, parent, x, H, K, C, A, toe, radii, top_z, front, pivot=None, sock=None, foot_key="fur",
             seg=8, rings=6, skin=0.6):
    """Two legs from (y, z) joints: H hip/shoulder pivot (hidden), K elbow/stifle (top of the visible leg),
    C carpus/hock, A fetlock/paw joint, toe tip (ground). pivot = ground contact (y) for the roll."""
    out = []
    for side in (1, -1):
        sx = "L" if side > 0 else "R"
        X = x * side
        P = lambda q: V(X, q[0], q[1])   # noqa: E731
        pv = P((pivot if pivot is not None else toe[0], 0.0))
        out.append(add_leg(an, ("F" if front else "H") + sx, side, prefix, parent, P(H), P(K),
                           P(C) if C is not None else None, P(A), P(toe), pv, pole=(0, 1, 0) if front else (0, -1, 0),
                           flex_sign=1 if front else -1, front=front, radii=radii, top_z=top_z, sock=sock,
                           foot_key=foot_key, seg=seg, rings=rings, skin=skin))
    return out


def hooves(an, r0, r1, h, key="dark", seg=8):
    for lg in an.legs:
        c = V(lg.A.x, lg.A.y + (0.004 if lg.front else -0.004) * an.size, 0.0)
        an.add(loft([c, c + V(0, 0, h)], [(0, r0, r0 * 0.97), (1, r1, r1 * 0.98)], seg=seg, rings=2, up=(0, -1, 0),
                    caps=(0.12, 0.35), cap_rings=1), key, lg.foot)


def paws(an, rx, ry, rz, key="fur", fwd=0.35, seg=8):
    for lg in an.legs:
        c = lg.A.lerp(lg.toe, fwd)
        c.z = rz * 0.92
        an.add(ellip(frame_m(c, (1, 0, 0), (0, 1, 0), (0, 0, 1)), (rx, ry, rz), seg, 5), key, lg.foot)


def neck_seg(an, base, O, start, prof, hf, seg=12, rings=5, key="fur", blend=0.05, pre_blend=0.07):
    an.bone("neck", base, O, "chest")
    w = chain(["neck", "head"], [base, O, hf.p(0, 0.6 * an.size * 0.25, 0)], blend=[blend], pre="chest", pre_blend=pre_blend)
    vf = loft([start, V(base).lerp(V(O), 0.5), hf.p(0, 0.02 * an.size, -0.01 * an.size)], prof, seg=seg, rings=rings,
              caps=(0.5, 0.5), cap_rings=1)
    an.add(vf, key, w)
    return vf, w


def add_ear(an, hf, side, root, tip, width, thick, key="fur", inner="mark", lift=0.012, rule_bone=None, up=None,
            prof=None, seg=8, rings=4, caps=(0.5, 0.9), inner_k=(0.55, 0.62, 0.55), paint=None):
    sx = "L" if side > 0 else "R"
    R0, T1 = V(root), V(tip)
    name = rule_bone or "ear_" + sx
    an.bone(name, R0, T1, "head", zref=hf.u)
    ew = chain([name], [R0, T1], pre="head", pre_blend=0.2 * width)
    mid = R0.lerp(T1, 0.5)
    upv = V(up) if up is not None else hf.f
    prof = prof or [(0, width * 0.47, thick * 0.9), (0.45, width, thick), (1, width * 0.3, thick * 0.6)]
    ear = loft([R0, mid + hf.u * lift, T1], prof, seg=seg, rings=rings, up=upv, caps=caps, cap_rings=1)
    an.add(ear, paint or key, ew)
    if inner:
        T = (T1 - R0).normalized()
        n = upv - T * upv.dot(T)
        n.normalize()
        wv = n.cross(T).normalized()
        L = (T1 - R0).length
        an.add(ellip(frame_m(R0.lerp(T1, inner_k[0]) + n * (thick * 0.72), T, wv, n),
                     (L * inner_k[1] * 0.5, width * inner_k[2], thick * 0.35), 8, 4), inner, ew)
    return ear


def add_horn(an, pts, r0, r1, key="horn", seg=6, rings=4, up=(0, 0, 1), bone="head", mid=None):
    mid = mid if mid is not None else (r0 + r1) * 0.55
    an.add(loft(pts, [(0, r0, r0), (0.5, mid, mid), (1, r1, r1)], seg=seg, rings=rings, up=up, caps=(0.2, 1.0),
                cap_rings=1), key, bone)


def add_tail(an, pts, radii, parent="hips", key="fur", seg=6, rings=None, tuft=None, tuft_key="dark", paint=None):
    pts = [V(q) for q in pts]
    names = []
    for i in range(len(pts) - 1):
        n = "tail_%d" % (i + 1)
        an.bone(n, pts[i], pts[i + 1], parent if i == 0 else names[-1])
        names.append(n)
    tw = chain(names, pts, blend=[0.04 * an.size] * len(names), pre=parent, pre_blend=0.015 * an.size + 0.005)
    prof = [(i / (len(radii) - 1), r, r) for i, r in enumerate(radii)]
    an.add(loft(pts, prof, seg=seg, rings=rings or max(5, len(pts) + 2), caps=(0.5, 0.6), cap_rings=1),
           paint or key, tw)
    if tuft:
        c, r = tuft
        an.add(ellip(frame_m(c, (1, 0, 0), (0, 1, 0), (0, 0, 1)), r, 8, 5), tuft_key, tw)
    return names, tw


def body_az(n):
    """angle of a body normal around the long axis: 0 = up, 90 = the animal's left side, 180 = belly."""
    return math.degrees(math.atan2(n.x, n.z))


# =========================================================================== species: sapi (Bali cow)
def build_sapi():
    an = Animal("sapi", size=1.5)
    std_mats(an, "#b86b3d", "#f6f0e4", horn="#e6d8ba")
    an.variants = [dict(name="coklat", fur="#b86b3d", mark="#f6f0e4"),
                   dict(name="jantan", fur="#3a2f2b", mark="#f3ebdd"),
                   dict(name="merah", fur="#a4532f", mark="#f3ebdd")]
    spine_w = spine3(an, [(0, 0.36, 0.8), (0, 0.0, 0.78), (0, -0.22, 0.8), (0, -0.36, 0.86)])
    body = loft([(0, 0.42, 0.74), (0, 0.15, 0.72), (0, -0.15, 0.72), (0, -0.4, 0.76)],
                [(0.0, 0.26, 0.26), (0.2, 0.31, 0.3), (0.55, 0.325, 0.31, -0.01), (0.85, 0.3, 0.3), (1.0, 0.25, 0.27)],
                seg=16, rings=8, caps=(0.8, 0.7), sq=2.3)
    leg_pair(an, "front", "chest", 0.18, H=(-0.36, 0.85), K=(-0.22, 0.48), C=(-0.25, 0.28), A=(-0.255, 0.11),
             toe=(-0.335, 0.0), radii=(0.092, 0.086, 0.074, 0.068), top_z=0.6, front=True, sock=0.3)
    leg_pair(an, "hind", "hips", 0.18, H=(0.4, 0.85), K=(0.23, 0.5), C=(0.3, 0.29), A=(0.28, 0.11),
             toe=(0.2, 0.0), radii=(0.1, 0.09, 0.074, 0.068), top_z=0.62, front=False, sock=0.3)
    hooves(an, 0.081, 0.071, 0.135)
    bw = leg_skin(an, spine_w)
    # white rump patch = the body's rear cap (its boundary follows a loft ring: a clean oval)
    an.add(body, lambda c, n: "mark" if c.y > 0.545 and c.z < 0.93 else "fur", bw)
    an.add(strip(body, [(0, -0.36, 1.2), (0, -0.1, 1.2), (0, 0.2, 1.2), (0, 0.5, 1.2)], 0.032, (0, 0, 1), lift=0.006),
           "dark", spine_w)
    O = V(0, -0.52, 1.0)
    hf = Frame(O, (0, -math.cos(rad(18)), -math.sin(rad(18))), (0, 0, 1))
    _nv, neck_w = neck_seg(an, (0, -0.36, 0.86), O, (0, -0.26, 0.8), [(0, 0.2, 0.22), (0.6, 0.175, 0.18), (1, 0.16, 0.15)], hf)
    an.add(ellip(frame_m((0, -0.46, 0.76), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.05, 0.1, 0.09), 8, 5), "fur", neck_w)
    an.bone("head", O, hf.p(0, 0.4, 0), "neck")
    head = loft([hf.p(0, -0.06, 0.0), hf.p(0, 0.33, -0.03)],
                [(0, 0.18, 0.17), (0.3, 0.205, 0.185), (0.65, 0.19, 0.16), (1.0, 0.165, 0.13)],
                seg=14, rings=6, up=hf.u, caps=(0.9, 0.45), sq=2.2)
    an.add(head, "fur", "head")
    muz_c = hf.p(0, 0.33, -0.065)
    muz = ellip(hf.m(muz_c), (0.172, 0.11, 0.112), 12, 7)
    an.add(muz, "mark", "head")
    mt = mesh_tree(muz)
    for s in (1, -1):
        p, n = surf(muz, muz_c, hf.d(0.42 * s, 0.85, 0.3), mt)
        an.add(ellip(CH.orient(p - n * 0.004, n, hf.u), (0.026, 0.011, 0.019), 6, 3), "dark", "head")
    an.bone("jaw", hf.p(0, 0.17, -0.1), hf.p(0, 0.38, -0.15), "head")
    an.add(ellip(hf.m(hf.p(0, 0.31, -0.145)), (0.12, 0.08, 0.05), 8, 5), "mark", "jaw")
    an.add(ellip(hf.m(hf.p(0, 0.31, -0.15)), (0.11, 0.075, 0.034), 8, 4), "dark", "head")
    ht = mesh_tree(head)
    for s, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hf.p(0, 0.1, 0.04), hf.d(0.62 * s, 0.66, 0.42), 0.044, 0.056, tree=ht)
        add_ear(an, hf, s, hf.p(0.16 * s, 0.03, 0.09), hf.p(0.39 * s, 0.07, 0.02), 0.085, 0.026)
        add_horn(an, [hf.p(0.095 * s, 0.05, 0.14), hf.p(0.16 * s, 0.04, 0.2), hf.p(0.19 * s, 0.08, 0.27)], 0.036, 0.013,
                 up=hf.f)
    an.add(ellip(hf.m(hf.p(0, 0.05, 0.165)), (0.065, 0.055, 0.04), 6, 4), "fur", "head")
    add_tail(an, [(0, 0.58, 0.92), (0, 0.665, 0.81), (0, 0.69, 0.63), (0, 0.695, 0.45)], [0.028, 0.022, 0.02],
             tuft=((0, 0.695, 0.43), (0.05, 0.05, 0.085)))
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=120, chew=4.0, ear_down=4.0),
        walk=dict(gait=Gait(30, 0.5, 0.62, LS_WALK, lift=(0.1, 0.08), flex=(60.0, 38.0), hoof=40.0, roll=18.0),
                  bob=0.012, hip_roll=2.5, chest_roll=1.8, hip_yaw=1.5, nod=4.0, tail=7.0, ear=3.0),
        run=dict(gait=Gait(20, 0.95, 0.42, TROT, lift=(0.15, 0.12), flex=(90.0, 55.0), hoof=55.0, roll=24.0,
                           lift_bias=0.8), bob=0.03, hip_roll=1.5, chest_roll=1.0, hip_yaw=1.0, nod=-2.5,
                 tail=5.0, tail_up=35.0, ear=4.0, ear_back=18.0, pitch=1.2),
        eat=dict(N=72, neck=70.0, head=8.0, lean=4.0, drop=0.012, chew=10.0, chews=6, tail=8.0),
        call=dict(N=42, open=(13, 31), neck=-20.0, head=-22.0, jaw=24.0, tail_up=20.0, tail=5.0),
    )
    an.clips = dict(QUAD_CLIPS)
    an.meta["call_open"] = round((13 - 1) / FPS, 3)
    return an


# =========================================================================== species: kerbau (water buffalo)
def build_kerbau():
    an = Animal("kerbau", size=1.65)
    std_mats(an, "#74716e", "#b9b1a7", horn="#4c4641")
    an.variants = [dict(name="abu", fur="#74716e", mark="#b9b1a7"),
                   dict(name="gelap", fur="#53504e", mark="#a8a097"),
                   dict(name="bule", fur="#d8b3a2", mark="#f1e2d8")]
    spine_w = spine3(an, [(0, 0.4, 0.78), (0, 0.0, 0.76), (0, -0.26, 0.78), (0, -0.42, 0.84)])
    body = loft([(0, 0.46, 0.73), (0, 0.15, 0.71), (0, -0.18, 0.71), (0, -0.44, 0.75)],
                [(0.0, 0.28, 0.28), (0.2, 0.35, 0.31), (0.55, 0.37, 0.33, -0.015), (0.85, 0.345, 0.315), (1.0, 0.28, 0.29)],
                seg=16, rings=8, caps=(0.8, 0.7), sq=2.4)
    leg_pair(an, "front", "chest", 0.2, H=(-0.4, 0.84), K=(-0.26, 0.46), C=(-0.285, 0.27), A=(-0.29, 0.11),
             toe=(-0.38, 0.0), radii=(0.108, 0.1, 0.086, 0.079), top_z=0.58, front=True, sock=0.24)
    leg_pair(an, "hind", "hips", 0.2, H=(0.44, 0.84), K=(0.27, 0.48), C=(0.34, 0.28), A=(0.32, 0.11),
             toe=(0.235, 0.0), radii=(0.118, 0.102, 0.086, 0.079), top_z=0.6, front=False, sock=0.24)
    hooves(an, 0.092, 0.081, 0.13)
    bw = leg_skin(an, spine_w)
    an.add(body, "fur", bw)
    O = V(0, -0.62, 0.92)
    hf = Frame(O, (0, -math.cos(rad(34)), -math.sin(rad(34))), (0, 0, 1))
    neck_prof = [(0, 0.24, 0.25), (0.6, 0.2, 0.2), (1, 0.18, 0.17)]
    # light chevron on the throat
    an.bone("neck", (0, -0.42, 0.84), O, "chest")
    neck_w = chain(["neck", "head"], [(0, -0.42, 0.84), O, hf.p(0, 0.3, 0)], blend=[0.05], pre="chest", pre_blend=0.08)
    an.add(loft([(0, -0.3, 0.77), (0, -0.52, 0.86), hf.p(0, 0.03, -0.02)], neck_prof, seg=12, rings=5, caps=(0.5, 0.5),
                cap_rings=1), lambda c, n: "mark" if (n.z < -0.25 and n.y < 0.2 and -0.62 < c.y < -0.45) else "fur", neck_w)
    an.bone("head", O, hf.p(0, 0.42, 0), "neck")
    head = loft([hf.p(0, -0.06, 0.0), hf.p(0, 0.37, -0.02)],
                [(0, 0.175, 0.165), (0.3, 0.19, 0.175), (0.7, 0.172, 0.145), (1.0, 0.16, 0.125)],
                seg=14, rings=6, up=hf.u, caps=(0.85, 0.45), sq=2.3)
    an.add(head, "fur", "head")
    muz_c = hf.p(0, 0.37, -0.05)
    muz = ellip(hf.m(muz_c), (0.168, 0.105, 0.108), 12, 7)
    an.add(muz, "mark", "head")
    mt = mesh_tree(muz)
    for s in (1, -1):
        p, n = surf(muz, muz_c, hf.d(0.42 * s, 0.85, 0.32), mt)
        an.add(ellip(CH.orient(p - n * 0.004, n, hf.u), (0.028, 0.012, 0.02), 6, 3), "dark", "head")
    an.bone("jaw", hf.p(0, 0.2, -0.09), hf.p(0, 0.42, -0.14), "head")
    an.add(ellip(hf.m(hf.p(0, 0.35, -0.13)), (0.12, 0.08, 0.05), 8, 5), "mark", "jaw")
    an.add(ellip(hf.m(hf.p(0, 0.35, -0.135)), (0.11, 0.075, 0.034), 8, 4), "dark", "head")
    ht = mesh_tree(head)
    for s, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hf.p(0, 0.12, 0.03), hf.d(0.66 * s, 0.6, 0.42), 0.04, 0.05, tree=ht)
        add_ear(an, hf, s, hf.p(0.15 * s, 0.03, 0.06), hf.p(0.36 * s, 0.05, -0.04), 0.08, 0.026)
        r0 = hf.p(0.1 * s, 0.03, 0.13)
        pts = [r0, r0 + V(0.15 * s, 0.03, 0.035), r0 + V(0.3 * s, 0.14, 0.06), r0 + V(0.36 * s, 0.3, 0.1),
               r0 + V(0.29 * s, 0.43, 0.15)]
        an.add(loft(pts, [(0, 0.07, 0.05), (0.35, 0.058, 0.042), (0.7, 0.04, 0.03), (1, 0.013, 0.012)], seg=8, rings=8,
                    up=(0, 0, 1), caps=(0.2, 1.0), cap_rings=1), "horn", "head")
    an.add(ellip(hf.m(hf.p(0, 0.04, 0.15)), (0.09, 0.06, 0.04), 6, 4), "fur", "head")
    add_tail(an, [(0, 0.62, 0.9), (0, 0.705, 0.79), (0, 0.73, 0.61), (0, 0.735, 0.43)], [0.03, 0.024, 0.02],
             tuft=((0, 0.735, 0.41), (0.048, 0.048, 0.08)))
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=132, chew=4.0, ear_down=6.0, neck=4.0),
        walk=dict(gait=Gait(34, 0.52, 0.64, LS_WALK, lift=(0.09, 0.075), flex=(55.0, 35.0), hoof=38.0, roll=16.0),
                  bob=0.012, hip_roll=2.8, chest_roll=2.0, hip_yaw=1.6, nod=4.5, tail=7.0, ear=3.0, neck=4.0),
        run=dict(gait=Gait(22, 0.95, 0.42, TROT, lift=(0.14, 0.11), flex=(85.0, 50.0), hoof=50.0, roll=22.0,
                           lift_bias=0.8), bob=0.03, hip_roll=1.5, chest_roll=1.0, hip_yaw=1.0, nod=-2.5,
                 tail=5.0, tail_up=30.0, ear=4.0, ear_back=14.0, pitch=1.2),
        eat=dict(N=78, neck=62.0, head=12.0, lean=4.0, drop=0.012, chew=10.0, chews=6, tail=8.0),
        call=dict(N=48, open=(14, 36), neck=-14.0, head=-20.0, jaw=20.0, tail_up=15.0, tail=5.0),
    )
    an.clips = dict(QUAD_CLIPS)
    an.meta["call_open"] = round((14 - 1) / FPS, 3)
    return an


# =========================================================================== species: kambing (goat)
def build_kambing():
    an = Animal("kambing", size=0.95)
    std_mats(an, "#f1ede4", "#b9875a", horn="#cbbd9f")
    an.variants = [dict(name="putih", fur="#f1ede4", mark="#b9875a"),
                   dict(name="coklat", fur="#8c5a36", mark="#f1ede4"),
                   dict(name="hitam", fur="#3a3432", mark="#efe9df")]
    spine_w = spine3(an, [(0, 0.2, 0.46), (0, 0.0, 0.45), (0, -0.14, 0.46), (0, -0.22, 0.5)])
    body = loft([(0, 0.24, 0.44), (0, 0.06, 0.43), (0, -0.12, 0.43), (0, -0.24, 0.46)],
                [(0.0, 0.135, 0.14), (0.3, 0.162, 0.158), (0.6, 0.166, 0.162, -0.005), (1.0, 0.136, 0.148)],
                seg=14, rings=8, caps=(0.8, 0.7), sq=2.2)
    leg_pair(an, "front", "chest", 0.088, H=(-0.24, 0.53), K=(-0.14, 0.3), C=(-0.155, 0.17), A=(-0.162, 0.065),
             toe=(-0.212, 0.0), radii=(0.056, 0.048, 0.04, 0.036), top_z=0.38, front=True)
    leg_pair(an, "hind", "hips", 0.088, H=(0.26, 0.53), K=(0.15, 0.31), C=(0.2, 0.17), A=(0.187, 0.065),
             toe=(0.137, 0.0), radii=(0.062, 0.05, 0.04, 0.036), top_z=0.39, front=False)
    hooves(an, 0.043, 0.039, 0.08)
    bw = leg_skin(an, spine_w)
    # saddle patch on the back
    an.add(body, lambda c, n: "mark" if (abs(body_az(n)) < 62 and -0.1 < c.y < 0.14) else "fur", bw)
    O = V(0, -0.33, 0.64)
    hf = Frame(O, (0, -math.cos(rad(26)), -math.sin(rad(26))), (0, 0, 1))
    neck_seg(an, (0, -0.22, 0.5), O, (0, -0.17, 0.45), [(0, 0.1, 0.11), (0.6, 0.078, 0.086), (1, 0.072, 0.072)], hf,
             seg=10, rings=5)
    an.bone("head", O, hf.p(0, 0.24, 0), "neck")
    head = loft([hf.p(0, -0.04, 0.0), hf.p(0, 0.2, -0.02)],
                [(0, 0.092, 0.09), (0.35, 0.1, 0.095), (0.75, 0.078, 0.072), (1.0, 0.064, 0.058)],
                seg=12, rings=6, up=hf.u, caps=(0.85, 0.6), sq=2.1)
    # brown cap over the forehead and ears' base
    an.add(head, lambda c, n: "mark" if (n.dot(hf.u) > 0.35 and (c - O).dot(hf.f) < 0.12) else "fur", "head")
    muz_c = hf.p(0, 0.2, -0.035)
    muz = ellip(hf.m(muz_c), (0.066, 0.06, 0.056), 10, 6)
    an.add(muz, "fur", "head")
    mt = mesh_tree(muz)
    for s in (1, -1):
        p, n = surf(muz, muz_c, hf.d(0.4 * s, 0.85, 0.35), mt)
        an.add(ellip(CH.orient(p - n * 0.002, n, hf.u), (0.012, 0.006, 0.009), 6, 3), "dark", "head")
    an.bone("jaw", hf.p(0, 0.1, -0.05), hf.p(0, 0.23, -0.08), "head")
    an.add(ellip(hf.m(hf.p(0, 0.19, -0.075)), (0.05, 0.05, 0.03), 8, 4), "fur", "jaw")
    an.add(ellip(hf.m(hf.p(0, 0.19, -0.08)), (0.045, 0.045, 0.02), 6, 4), "dark", "head")
    an.add(loft([hf.p(0, 0.19, -0.09), hf.p(0, 0.17, -0.16)], [(0, 0.022, 0.018), (1, 0.008, 0.008)], seg=6, rings=3,
                up=hf.f, caps=(0.3, 0.8), cap_rings=1), "fur", "jaw")          # beard
    ht = mesh_tree(head)
    for s, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hf.p(0, 0.06, 0.03), hf.d(0.7 * s, 0.56, 0.42), 0.03, 0.037, tree=ht)
        add_ear(an, hf, s, hf.p(0.075 * s, 0.01, 0.05), hf.p(0.2 * s, 0.05, -0.06), 0.05, 0.015, inner="mark")
        add_horn(an, [hf.p(0.04 * s, 0.01, 0.08), hf.p(0.058 * s, -0.04, 0.15), hf.p(0.066 * s, -0.13, 0.175)],
                 0.021, 0.006, up=hf.f)
    add_tail(an, [(0, 0.3, 0.53), (0, 0.33, 0.59), (0, 0.34, 0.65)], [0.03, 0.022, 0.015], seg=6)
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=96, chew=5.0, ear_down=2.0, tail_axis="roll"),
        walk=dict(gait=Gait(22, 0.3, 0.6, LS_WALK, lift=(0.065, 0.055), flex=(60.0, 40.0), hoof=40.0, roll=18.0),
                  bob=0.008, hip_roll=3.0, chest_roll=2.0, hip_yaw=2.0, nod=4.0, tail=10.0, ear=4.0),
        run=dict(gait=Gait(14, 0.56, 0.4, TROT, lift=(0.1, 0.085), flex=(90.0, 55.0), hoof=55.0, roll=24.0,
                           lift_bias=0.8), bob=0.022, hip_roll=2.0, chest_roll=1.5, hip_yaw=1.5, nod=-3.0,
                 tail=12.0, ear=6.0, ear_back=12.0, pitch=2.0),
        eat=dict(N=60, neck=78.0, head=0.0, lean=4.0, drop=0.01, chew=12.0, chews=6, tail=14.0),
        call=dict(N=36, open=(9, 26), neck=-18.0, head=-20.0, jaw=26.0, tail=10.0),
    )
    an.clips = dict(QUAD_CLIPS)
    an.meta["call_open"] = round((9 - 1) / FPS, 3)
    return an


# =========================================================================== dog & cat clips
def d_wag(an, solver):
    """standing, tail wagging fast, happy body wiggle, panting with the tongue out."""
    P = an.anim["wag"]
    N = P.get("N", 16)
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    for f, p in enumerate(poses):
        ph = f / N
        w = syc(2 * ph)
        p.mv("hips", dz=-0.004 * an.size * (1 + cyc(4 * ph)))
        p.r("hips", yaw=P.get("wiggle", 4.0) * w, roll=-1.5 * w)
        p.r("spine", yaw=-P.get("wiggle", 4.0) * 0.4 * w, pitch=0.8 * syc(4 * ph))
        p.r("chest", yaw=-P.get("wiggle", 4.0) * 0.4 * w, pitch=-1.0 * syc(4 * ph))
        p.r("neck", pitch=-4.0, yaw=2.0 * syc(ph))
        p.r("head", roll=P.get("tilt", 8.0) * (0.6 + 0.4 * syc(ph)), pitch=-3.0 + 1.5 * syc(4 * ph))
        p.r("jaw", pitch=P.get("pant", 16.0) * (0.75 + 0.25 * syc(4 * ph)))
        ears(p, back=P.get("ear_back", 14.0), down=0.0)
        for i, t in enumerate(tails):
            p.r(t, roll=P.get("tail", 30.0) * (1.0 + 0.2 * i) * math.sin(TAU * (2 * ph) - 0.5 * i))
        eyes(p, 1.0)
    solver.reach_fix(poses, True)
    return N, True, poses


def d_bark(an, solver):
    """one bark: crouch, thrust the head forward-up with the mouth open, settle."""
    P = an.anim["call"]
    N = P.get("N", 24)
    o0 = P.get("open", 6)
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    thr = Kc([(0, 0), (o0 - 3, -0.4), (o0 + 1, 1.0), (o0 + 5, 0.7), (N - 6, 0.15), (N, 0)])
    jaw = Kc([(0, 0), (o0 - 1, 0), (o0 + 1, 1.0), (o0 + 5, 0.9), (o0 + 9, 0.0), (N, 0)])
    for f, p in enumerate(poses):
        u, j = thr(f), jaw(f)
        p.mv("hips", dy=0.012 * an.size * u, dz=-0.008 * an.size * max(0.0, -u) * 2)
        p.r("hips", pitch=-2.0 * u)
        p.r("chest", pitch=-3.0 * u)
        p.r("neck", pitch=P.get("neck", -12.0) * u)
        p.r("head", pitch=P.get("head", -14.0) * u)
        p.r("jaw", pitch=P.get("jaw", 30.0) * j)
        ears(p, back=-6.0 * u, down=-4.0 * u)
        tail_wave(p, tails, f, N, 10.0 * abs(u), cycles=2, lag=0.1)
        eyes(p, 1.0 - 0.3 * j)
    solver.reach_fix(poses, False)
    return N, False, poses


def c_sit(an, solver):
    """cat sitting: haunches down, front legs straight, tail curled round the paws (tip twitching)."""
    P = an.anim["sit"]
    N = P.get("N", 96)
    poses = seq(N)
    tails = quad_bones(an)["tails"]
    look = Kc([(0, 0), (20, 0), (34, 16), (54, 16), (66, -10), (84, -10), (96, 0)], N)
    for f, p in enumerate(poses):
        ph = f / N
        br = syc(3 * ph)
        p.mv("hips", dy=P["dy"], dz=-P["drop"])
        p.r("hips", pitch=P["pitch"])
        p.r("spine", pitch=P["spine"] - 0.6 * br)
        p.r("chest", pitch=P["chest"] - 0.6 * br)
        p.r("neck", pitch=P["neck"], yaw=look(f) * 0.5)
        p.r("head", pitch=P["head"], yaw=look(f) * 0.5, roll=3.0 * syc(ph))
        for lg in an.legs:
            if lg.front:
                p.legs[lg.name] = dict(A=lg.A + V(0, P["front_dy"], 0), hoof=0.0, flex=0.0)
            else:
                p.legs[lg.name] = dict(A=lg.A + V(lg.side * P.get("hind_dx", 0.0), P["hind_dy"], P.get("hind_dz", 0.0)),
                                       hoof=P.get("hind_hoof", 0.0), flex=P["hind_flex"])
        curl = P["curl"]
        for i, t in enumerate(tails):
            tw = 10.0 * math.sin(TAU * (2 * ph) - 0.7 * i) * (i / max(1, len(tails) - 1)) ** 2
            p.r(t, pitch=curl[i][0], yaw=curl[i][1], roll=curl[i][2] + tw)
        fl = math.exp(-((f - 44) / 2.5) ** 2) * 24.0
        ears(p, back=2.0, down=0.0, dl=(fl, 0.0))
        eyes(p, min(blink(f, 12, 10), blink(f, 70, 5)))
        p.r("jaw", pitch=0.0)
    solver.reach_fix(poses, True)
    return N, True, poses


# =========================================================================== species: anjing (kampung dog)
def build_anjing():
    an = Animal("anjing", size=0.8)
    std_mats(an, "#cf9a5e", "#f3e5c8", mark2="#b98150")
    an.mat("tongue", "AnimalTongue", "#e2727a", 0.5)
    an.variants = [dict(name="coklat", fur="#cf9a5e", mark="#f3e5c8", mark2="#b98150"),
                   dict(name="hitam", fur="#34302d", mark="#e9ddca", mark2="#2a2624"),
                   dict(name="putih", fur="#efe6d6", mark="#fbf6ec", mark2="#d9b58b"),
                   dict(name="belang", fur="#efe6d6", mark="#fbf6ec", mark2="#5a3f2c")]
    spine_w = spine3(an, [(0, 0.17, 0.33), (0, 0.0, 0.32), (0, -0.13, 0.33), (0, -0.2, 0.37)])
    body = loft([(0, 0.2, 0.315), (0, 0.05, 0.31), (0, -0.1, 0.315), (0, -0.2, 0.335)],
                [(0, 0.095, 0.098, 0.006), (0.35, 0.105, 0.108), (0.7, 0.112, 0.12, -0.01), (1, 0.104, 0.114, -0.006)],
                seg=14, rings=8, caps=(0.8, 0.7), sq=2.1)
    leg_pair(an, "front", "chest", 0.06, H=(-0.24, 0.39), K=(-0.16, 0.22), C=(-0.165, 0.075), A=(-0.175, 0.035),
             toe=(-0.225, 0.0), pivot=-0.2, radii=(0.05, 0.044, 0.036, 0.032), top_z=0.29, front=True, sock=0.09)
    leg_pair(an, "hind", "hips", 0.06, H=(0.22, 0.39), K=(0.14, 0.23), C=(0.195, 0.1), A=(0.182, 0.035),
             toe=(0.14, 0.0), pivot=0.16, radii=(0.058, 0.047, 0.036, 0.032), top_z=0.3, front=False, sock=0.09)
    paws(an, 0.037, 0.05, 0.026, key="mark")
    bw = leg_skin(an, spine_w)

    def body_paint(c, n):
        if n.z < -0.5 or (c.y < -0.22 and n.z < 0.2):
            return "mark"
        if abs(body_az(n)) < 45 and -0.04 < c.y < 0.15:
            return "mark2"
        return "fur"
    an.add(body, body_paint, bw)
    O = V(0, -0.27, 0.47)
    hf = Frame(O, (0, -math.cos(rad(8)), -math.sin(rad(8))), (0, 0, 1))
    an.bone("neck", (0, -0.2, 0.37), O, "chest")
    neck_w = chain(["neck", "head"], [(0, -0.2, 0.37), O, hf.p(0, 0.12, 0)], blend=[0.03], pre="chest", pre_blend=0.04)
    an.add(loft([(0, -0.15, 0.34), (0, -0.24, 0.42), hf.p(0, 0.015, -0.01)], [(0, 0.075, 0.08), (0.6, 0.064, 0.066),
                (1, 0.058, 0.058)], seg=10, rings=5, caps=(0.5, 0.5), cap_rings=1),
           lambda c, n: "mark" if (n.z < -0.15 and n.y < 0.3) else "fur", neck_w)
    an.bone("head", O, hf.p(0, 0.2, 0), "neck")
    head = loft([hf.p(0, -0.055, 0.0), hf.p(0, 0.08, -0.005)], [(0, 0.085, 0.08), (0.5, 0.096, 0.086), (1, 0.08, 0.07)],
                seg=14, rings=6, up=hf.u, caps=(0.9, 0.5), sq=2.1)
    an.add(head, lambda c, n: "mark" if n.dot(hf.u) < -0.55 else "fur", "head")
    snout = loft([hf.p(0, 0.05, -0.028), hf.p(0, 0.185, -0.04)], [(0, 0.056, 0.05), (0.6, 0.045, 0.041), (1, 0.039, 0.035)],
                 seg=10, rings=4, up=hf.u, caps=(0.3, 0.7), cap_rings=1)
    an.add(snout, "mark", "head")
    an.add(ellip(hf.m(hf.p(0, 0.207, -0.024)), (0.022, 0.016, 0.016), 8, 4), "dark", "head")
    an.bone("jaw", hf.p(0, 0.07, -0.065), hf.p(0, 0.19, -0.07), "head")
    an.add(ellip(hf.m(hf.p(0, 0.135, -0.068)), (0.036, 0.058, 0.02), 8, 4), "mark", "jaw")
    an.add(ellip(hf.m(hf.p(0, 0.125, -0.058)), (0.034, 0.058, 0.016), 8, 4), "dark", "head")
    an.add(ellip(hf.m(hf.p(0, 0.15, -0.058)), (0.024, 0.052, 0.008), 8, 4), "tongue", "jaw")
    ht = mesh_tree(head)
    for s_, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hf.p(0, 0.03, 0.02), hf.d(0.52 * s_, 0.72, 0.4), 0.027, 0.033, tree=ht)
        R0, T1 = hf.p(0.052 * s_, -0.015, 0.06), hf.p(0.088 * s_, -0.03, 0.158)
        tipc = T1
        add_ear(an, hf, s_, R0, T1, 0.036, 0.012, inner="mark", lift=0.0, prof=[(0, 0.036, 0.012), (0.5, 0.027, 0.01),
                (1, 0.005, 0.005)], caps=(0.4, 0.6), inner_k=(0.4, 0.6, 0.45),
                paint=lambda c, n, t=tipc: "mark2" if (c - t).length < 0.035 else "fur")
    tp = [V(0, 0.24, 0.4), V(0, 0.29, 0.47), V(0, 0.293, 0.55), V(0, 0.25, 0.6), V(0, 0.197, 0.588)]
    add_tail(an, tp, [0.03, 0.031, 0.026, 0.019, 0.011], seg=8, rings=11,
             paint=lambda c, n, t=tp[-1]: "mark" if (c - t).length < 0.04 else "fur")
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=96, ear_down=0.0),
        walk=dict(gait=Gait(20, 0.4, 0.6, LS_WALK, lift=(0.06, 0.05), flex=(75.0, 45.0), hoof=45.0, roll=25.0),
                  bob=0.006, hip_roll=3.0, chest_roll=2.0, hip_yaw=2.5, nod=2.5, tail=10.0, ear=2.0),
        run=dict(gait=Gait(12, 0.9, 0.32, BOUND, lift=(0.1, 0.09), flex=(105.0, 70.0), hoof=70.0, roll=30.0,
                           lift_bias=0.8), bob=0.025, hip_roll=1.0, chest_roll=1.0, hip_yaw=0.5, nod=-3.0,
                 tail=8.0, ear=5.0, ear_back=20.0, flexs=6.0, flexc=5.0, flex_ph=0.2, jaw=10.0),
        eat=dict(N=48, neck=62.0, head=18.0, lean=4.0, drop=0.01, chew=14.0, chews=8, tail=12.0),
        call=dict(N=24, open=7, neck=-12.0, head=-14.0, jaw=32.0),
        wag=dict(N=16, tail=30.0, wiggle=4.0, pant=16.0, tilt=8.0, ear_back=14.0),
    )
    an.clips = dict(QUAD_CLIPS, call=d_bark, wag=d_wag)
    an.meta["call_open"] = round((7 - 1) / FPS, 3)
    return an


# =========================================================================== species: kucing (village cat)
def build_kucing():
    an = Animal("kucing", size=0.55)
    std_mats(an, "#eb9a4c", "#cc7331", mark2="#d8843b")
    an.mat("white", "AnimalWhite", "#fbf6ec")
    an.variants = [dict(name="oren", fur="#eb9a4c", mark="#cc7331", mark2="#d8843b"),
                   dict(name="belang_tiga", fur="#f7f2e8", mark="#e39445", mark2="#3b3431"),
                   dict(name="hitam", fur="#35302d", mark="#3f3935", mark2="#3f3935"),
                   dict(name="abu", fur="#a09d98", mark="#6d6a67", mark2="#85827e")]
    spine_w = spine3(an, [(0, 0.12, 0.185), (0, 0.0, 0.18), (0, -0.1, 0.185), (0, -0.155, 0.215)])
    body = loft([(0, 0.15, 0.18), (0, 0.03, 0.17), (0, -0.08, 0.175), (0, -0.15, 0.19)],
                [(0, 0.068, 0.07), (0.4, 0.08, 0.08, -0.004), (1, 0.072, 0.078)], seg=14, rings=8, caps=(0.8, 0.75), sq=2.1)
    leg_pair(an, "front", "chest", 0.043, H=(-0.17, 0.225), K=(-0.12, 0.12), C=(-0.125, 0.04), A=(-0.132, 0.02),
             toe=(-0.165, 0.0), pivot=-0.148, radii=(0.032, 0.028, 0.024, 0.022), top_z=0.17, front=True, sock=0.05)
    leg_pair(an, "hind", "hips", 0.043, H=(0.155, 0.225), K=(0.105, 0.125), C=(0.15, 0.055), A=(0.14, 0.02),
             toe=(0.11, 0.0), pivot=0.125, radii=(0.038, 0.03, 0.024, 0.022), top_z=0.175, front=False, sock=0.05)
    paws(an, 0.025, 0.033, 0.017, key="white")
    bw = leg_skin(an, spine_w)

    def body_paint(c, n):
        az = body_az(n)
        if n.z < -0.55 or (c.y < -0.17 and n.z < 0.3):
            return "white"
        if abs(az) < 62 and (int(math.floor((c.y + 0.3) / 0.034)) % 2 == 0) and c.y > -0.1:
            return "mark"                           # tabby stripes over the back
        if 75 < az < 125 and -0.1 < c.y < 0.06:
            return "mark2"                          # patch on the left flank
        return "fur"
    an.add(body, body_paint, bw)
    O = V(0, -0.2, 0.265)
    hf = Frame(O, (0, -math.cos(rad(4)), -math.sin(rad(4))), (0, 0, 1))
    an.bone("neck", (0, -0.155, 0.215), O, "chest")
    neck_w = chain(["neck", "head"], [(0, -0.155, 0.215), O, hf.p(0, 0.08, 0)], blend=[0.02], pre="chest", pre_blend=0.03)
    an.add(loft([(0, -0.12, 0.195), (0, -0.175, 0.235), hf.p(0, 0.0, -0.01)], [(0, 0.052, 0.056), (1, 0.045, 0.045)],
                seg=10, rings=4, caps=(0.5, 0.5), cap_rings=1),
           lambda c, n: "white" if (n.z < -0.2 and n.y < 0.3) else "fur", neck_w)
    an.bone("head", O, hf.p(0, 0.13, 0), "neck")
    head = loft([hf.p(0, -0.035, 0.012), hf.p(0, 0.075, 0.0)], [(0, 0.074, 0.066), (0.45, 0.086, 0.074), (1, 0.066, 0.056)],
                seg=14, rings=6, up=hf.u, caps=(0.9, 0.55), sq=2.05)

    def head_paint(c, n):
        u = n.dot(hf.u)
        if u < -0.45:
            return "white"
        if u > 0.55 and abs((c - O).dot(hf.x)) < 0.03 and (c - O).dot(hf.f) > -0.02:
            return "mark"                           # forehead stripe
        if (c - O).dot(hf.x) > 0.04 and u > 0.1 and (c - O).dot(hf.f) < 0.03:
            return "mark2"                          # patch over the left ear
        return "fur"
    an.add(head, head_paint, "head")
    for s_ in (1, -1):   # whisker pads
        an.add(ellip(hf.m(hf.p(0.024 * s_, 0.098, -0.022)), (0.027, 0.022, 0.021), 8, 5), "white", "head")
    an.add(ellip(hf.m(hf.p(0, 0.118, -0.004)), (0.011, 0.007, 0.008), 6, 3), "dark", "head")
    an.bone("jaw", hf.p(0, 0.05, -0.035), hf.p(0, 0.11, -0.04), "head")
    an.add(ellip(hf.m(hf.p(0, 0.088, -0.042)), (0.022, 0.024, 0.013), 8, 4), "white", "jaw")
    an.add(ellip(hf.m(hf.p(0, 0.084, -0.036)), (0.02, 0.022, 0.01), 6, 4), "dark", "head")
    ht = mesh_tree(head)
    for s_, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hf.p(0, 0.02, 0.012), hf.d(0.46 * s_, 0.8, 0.26), 0.025, 0.029,
                tree=ht)
        add_ear(an, hf, s_, hf.p(0.042 * s_, -0.004, 0.048), hf.p(0.064 * s_, -0.006, 0.108), 0.032, 0.01, inner="white",
                lift=0.0, prof=[(0, 0.032, 0.01), (0.5, 0.022, 0.008), (1, 0.004, 0.004)], caps=(0.4, 0.5),
                inner_k=(0.38, 0.55, 0.45))
    tp = [V(0, 0.19, 0.215), V(0, 0.245, 0.265), V(0, 0.27, 0.335), V(0, 0.275, 0.405), V(0, 0.25, 0.455)]
    add_tail(an, tp, [0.021, 0.02, 0.019, 0.018, 0.015], seg=7, rings=9,
             paint=lambda c, n: "mark" if int(math.floor((c.z - 0.165) / 0.045)) % 2 == 1 else "fur")
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=120, ear_down=0.0),
        walk=dict(gait=Gait(24, 0.3, 0.62, LS_WALK, lift=(0.04, 0.035), flex=(70.0, 45.0), hoof=45.0, roll=25.0),
                  bob=0.004, hip_roll=3.0, chest_roll=2.5, hip_yaw=2.5, nod=2.0, tail=8.0, ear=1.5),
        run=dict(gait=Gait(12, 0.62, 0.32, BOUND, lift=(0.07, 0.06), flex=(105.0, 70.0), hoof=70.0, roll=30.0,
                           lift_bias=0.8), bob=0.016, hip_roll=1.0, chest_roll=1.0, hip_yaw=0.5, nod=-3.0,
                 tail=8.0, ear=4.0, ear_back=24.0, flexs=7.0, flexc=6.0, flex_ph=0.2),
        eat=dict(N=48, neck=55.0, head=24.0, lean=3.0, drop=0.01, chew=12.0, chews=8, tail=10.0),
        call=dict(N=34, open=(9, 24), neck=-10.0, head=-16.0, jaw=26.0, tail=6.0),
        sit=dict(N=96, dy=0.02, drop=0.095, pitch=-34.0, spine=-4.0, chest=-14.0, neck=-18.0, head=58.0, front_dy=0.065,
                 hind_dy=-0.045, hind_dz=0.0, hind_flex=85.0, hind_hoof=0.0,
                 curl=[(-38.0, 0.0, 0.0), (10.0, 0.0, 55.0), (8.0, 0.0, 50.0), (6.0, 0.0, 50.0), (0.0, 0.0, 40.0)]),
    )
    an.clips = dict(QUAD_CLIPS, sit=c_sit)
    an.meta["call_open"] = round((9 - 1) / FPS, 3)
    return an


# =========================================================================== birds
def bird_leg(an, x, H, K, C, A, toe, radii, top_z, knee_key, shank_key, shank_z, toes, toe_r, web=None, seg=7):
    """Bird legs: upper (hidden thigh) > lower (drumstick) > cannon (shank) > foot (toes)."""
    out = []
    for side in (1, -1):
        sx = "L" if side > 0 else "R"
        P = lambda q: V(x * side + q[0] * side, q[1], q[2])   # noqa: E731
        lg = add_leg(an, sx, side, "leg", "hips", P((0,) + H), P((0,) + K), P((0,) + C), P((0,) + A), P((0,) + toe),
                     P((0, toe[0] * 0.55 + A[0] * 0.45, 0.0)), pole=(0, -1, 0.1), flex_sign=-1, front=False,
                     radii=radii, top_z=top_z, sock=shank_z, foot_key=knee_key, sock_key=shank_key, seg=seg, rings=7,
                     skin=0.3)
        Av = P((0,) + A)
        for (dx, dy) in toes:
            tip = V(Av.x + dx * side, Av.y + dy, toe_r * 0.8)
            base = V(Av.x, Av.y, toe_r * 1.1 + 0.004)
            an.add(loft([base, base.lerp(tip, 0.5) + V(0, 0, toe_r * 0.3), tip], [(0, toe_r, toe_r * 0.8), (1, toe_r * 0.7, toe_r * 0.6)],
                        seg=4, rings=2, up=(0, 0, 1), caps=(0.4, 0.8), cap_rings=1), shank_key, lg.foot)
        if web:
            (wx, wy, wz, off) = web
            c = V(Av.x, Av.y - off, wz + 0.002)
            an.add(ellip(frame_m(c, (1, 0, 0), (0, 1, 0), (0, 0, 1)), (wx, wy, wz), 10, 4), shank_key, lg.foot)
        out.append(lg)
    return out


def bird_head_chain(an, base, mid, O):
    an.bone("neck_1", base, mid, "hips")
    an.bone("neck_2", mid, O, "neck_1")
    an.chains["neck"] = dict(name="neck", b1="neck_1", b2="neck_2", end="head", pole=V(0, -1, 0.35),
                             l1=(V(mid) - V(base)).length, l2=(V(O) - V(mid)).length)


def b_head_target(an, dy=0.0, dz=0.0):
    return an.bhead("head") + V(0, dy, dz)


def neck_base(solver, pose):
    """armature-space neck root of a pose (body posed, no neck IK)."""
    ch = dict(pose.chains)
    pose.chains = {}
    _, posed = solver.solve(pose, legs=False)
    pose.chains = ch
    return (posed[solver.par["neck_1"]] @ solver.rel["neck_1"]).translation.copy()


def neck_reach(an, ang, k=0.93):
    """head-joint offset from the neck root at `ang` deg from straight up (+ = forward and down)."""
    ch = an.chains["neck"]
    L = (ch["l1"] + ch["l2"]) * k
    return V(0, -math.sin(rad(ang)) * L, math.cos(rad(ang)) * L)


def b_idle(an, solver):
    P = an.anim.get("idle", {})
    N = P.get("N", 90)
    poses = seq(N)
    look = Kc([(0, 0), (8, 0), (10, 28), (26, 28), (28, -8), (40, -8), (42, -30), (58, -30), (60, 6), (74, 6),
               (76, 0), (90, 0)], N)
    cock = Kc([(0, 0), (26, 0), (28, 14), (40, 14), (42, 0), (60, 0), (62, -10), (74, -10), (76, 0), (90, 0)], N)
    for f, p in enumerate(poses):
        ph = f / N
        br = syc(3 * ph)
        p.mv("hips", dz=0.002 * an.size * br)
        p.r("hips", pitch=0.8 * br)
        p.r("neck_1", pitch=1.0 * br, yaw=look(f) * 0.3)
        p.r("neck_2", yaw=look(f) * 0.3)
        p.r("head", yaw=look(f) * 0.4, roll=cock(f), pitch=-1.0 * br)
        p.r("tail", roll=10.0 * math.exp(-((f - 50) / 2.5) ** 2) * syc((f - 50) / 6.0), pitch=2.0 * br)
        ruf = math.exp(-((f - 66) / 4.0) ** 2)
        for sd, sx in ((1, "L"), (-1, "R")):
            p.r("wing_" + sx, roll=sd * (2.0 * br + 12.0 * ruf))
        p.r("jaw", pitch=0.0)
        eyes(p, min(blink(f, 18, 4), blink(f, 62, 4)))
    return N, True, poses


def b_walk(kind):
    def clip(an, solver):
        P = an.anim[kind]
        g = P["gait"]
        N = g.N
        poses = seq(N)
        v = g.stride / N          # m per frame
        for f, p in enumerate(poses):
            ph = f / N
            for lg in an.legs:
                p.legs[lg.name] = g.leg(lg, f)
            p.mv("hips", dz=-P.get("bob", 0.006) * cyc(2 * (ph - g.stance / 2)))
            wob = P.get("roll", 4.0) * cyc(ph - g.swing_mid("L"))
            p.r("hips", roll=wob, yaw=P.get("yaw", 3.0) * syc(ph - g.swing_mid("L")), pitch=P.get("lean", 0.0))
            p.r("tail", roll=-wob * 1.5 + P.get("tail", 6.0) * syc(2 * ph), pitch=P.get("tail_up", 0.0))
            for sd, sx in ((1, "L"), (-1, "R")):
                p.r("wing_" + sx, roll=sd * (P.get("wing", 0.0) + P.get("flap", 0.0) * (0.5 + 0.5 * syc(2 * ph))))
            if P.get("headbob"):
                # the head holds still in the world while the body walks on, then thrusts forward
                k = (2 * ph + P.get("bob_ph", 0.0)) % 1.0
                hold = P.get("hold", 0.65)
                amp = v * N * 0.5 * hold * P["headbob"]
                dy = amp * (k / hold) if k < hold else amp * (1.0 - sstep((k - hold) / (1 - hold)))
                dy -= amp * 0.3
                p.chains["neck"] = dict(T=b_head_target(an, dy=dy + P.get("head_fwd", 0.0), dz=P.get("head_dz", 0.0)),
                                        end_rot=D(pitch=P.get("head_pitch", 0.0)))
            else:
                p.r("neck_1", pitch=P.get("neck", 0.0) + 2.0 * syc(2 * ph))
                p.r("head", pitch=P.get("head", 0.0) - 2.0 * syc(2 * ph))
            p.r("jaw", pitch=P.get("jaw", 0.0))
            eyes(p, 1.0)
        solver.reach_fix(poses, True)
        return N, True, poses
    return clip


def b_peck(an, solver):
    """chicken: tip forward, peck the ground twice (the neck sweeps down at full reach), scratch once."""
    P = an.anim["eat"]
    N = P.get("N", 48)
    poses = seq(N)
    keys = P.get("pecks", [(0, 0.0), (6, 0.0), (10, 1.0), (13, 1.0), (17, 0.3), (20, 0.3), (24, 1.0), (27, 1.0),
                           (32, 0.0), (48, 0.0)])
    pk = Kc(keys, N)
    lean = Kc([(0, 1.0), (30, 1.0), (36, 0.75), (44, 0.75), (48, 1.0)], N)
    a0, a1 = P.get("ready", 35.0), P.get("down", 150.0)
    for f, p in enumerate(poses):
        k = pk(f)
        p.r("hips", pitch=P.get("lean", 22.0) * lean(f))
        p.mv("hips", dz=-P.get("drop", 0.02) * an.size * lean(f))
        base = neck_base(solver, p)
        ang = lerp(a0, a1, k)
        T = base + neck_reach(an, ang, lerp(0.9, P.get("reach", 0.97), k))
        p.chains["neck"] = dict(T=T, end_rot=D(pitch=lerp(20.0, P.get("head_down", 70.0), k)),
                                pole=neck_reach(an, ang - 90.0))
        p.r("jaw", pitch=12.0 * math.exp(-((k - 0.95) / 0.12) ** 2))
        p.r("tail", pitch=-6.0 * lean(f), roll=4.0 * syc(2 * f / N))
        u = clamp((f - 32) / 12.0)          # scratch with the right foot
        if 0 < u < 1:
            lg = [l for l in an.legs if l.name == "R"][0]
            A = lg.A + V(0, -0.02 * an.size + 0.07 * an.size * sstep(u), 0.02 * an.size * math.sin(math.pi * u))
            p.legs["R"] = dict(A=A, hoof=30.0 * math.sin(math.pi * u), flex=20.0 * math.sin(math.pi * u))
        eyes(p, blink(f, 40, 4))
    solver.reach_fix(poses, True)
    return N, True, poses


def b_call(an, solver):
    """cluck / crow: chest out, neck up, beak open (sound at call_open), wings flap."""
    P = an.anim["call"]
    N = P.get("N", 36)
    o0, o1 = P.get("open", (9, 26))
    poses = seq(N)
    up = Kc([(0, 0), (4, -0.2), (o0 - 1, 1.0), (o1, 1.0), (o1 + 5, 0.2), (N, 0)])
    jaw = Kc([(0, 0), (o0 - 2, 0), (o0 + 1, 1.0), (o1 - 2, 0.9), (o1 + 2, 0), (N, 0)])
    base0 = an.bhead("neck_1")
    rest = an.bhead("head") - base0
    a_rest = math.degrees(math.atan2(-rest.y, rest.z))
    k_rest = rest.length / (an.chains["neck"]["l1"] + an.chains["neck"]["l2"])
    for f, p in enumerate(poses):
        u, j = up(f), jaw(f)
        p.r("hips", pitch=P.get("chest", -14.0) * u)
        base = neck_base(solver, p)
        ang = a_rest + P.get("neck_ang", -12.0) * u
        T = base + neck_reach(an, ang, lerp(k_rest, P.get("reach", 0.97), u))
        p.chains["neck"] = dict(T=T, end_rot=D(pitch=P.get("head", -22.0) * u + 2.0 * j * math.sin(TAU * f / 4.0)),
                                pole=neck_reach(an, ang - 90.0))
        p.r("jaw", pitch=P.get("jaw", 30.0) * j)
        fl = P.get("flap", 25.0) * u * (0.5 + 0.5 * math.sin(TAU * f / 6.0))
        for sd, sx in ((1, "L"), (-1, "R")):
            p.r("wing_" + sx, roll=sd * fl)
        p.r("tail", pitch=-8.0 * u)
        eyes(p, 1.0 - 0.3 * j)
    solver.reach_fix(poses, False)
    return N, False, poses


BIRD_CLIPS = {"idle": b_idle, "walk": b_walk("walk"), "run": b_walk("run"), "eat": b_peck, "call": b_call}


def build_ayam():
    an = Animal("ayam", size=0.45)
    std_mats(an, "#c46a2c", "#763a1c")
    an.mat("comb", "AnimalComb", "#d8392b", 0.6)
    an.mat("beak", "AnimalBeak_ayam", "#f0b843", 0.6)
    an.variants = [dict(name="betina", fur="#c46a2c", mark="#763a1c", rooster=False),
                   dict(name="jago", fur="#c1462b", mark="#27352c", rooster=True),
                   dict(name="putih", fur="#f6f1e7", mark="#e2d6c1", rooster=False),
                   dict(name="hitam", fur="#34302e", mark="#2c3a31", rooster=False)]
    an.bone("hips", (0, 0.07, 0.27), (0, -0.07, 0.29))
    body = loft([(0, 0.12, 0.31), (0, 0.02, 0.28), (0, -0.09, 0.27)],
                [(0, 0.075, 0.08), (0.4, 0.103, 0.1, -0.005), (0.78, 0.098, 0.1, -0.004), (1, 0.074, 0.075)],
                seg=14, rings=7, caps=(0.9, 0.95), sq=2.0)
    bw = lambda p: {"hips": 1.0}   # noqa: E731
    bird_leg(an, 0.045, H=(0.02, 0.24), K=(-0.01, 0.185), C=(0.02, 0.1), A=(0.006, 0.02), toe=(-0.05, 0.0),
             radii=(0.042, 0.04, 0.012, 0.01), top_z=0.23, knee_key="fur", shank_key="beak", shank_z=0.115,
             toes=[(0.028, -0.048), (0.0, -0.058), (-0.028, -0.048), (0.0, 0.034)], toe_r=0.0065)
    an.add(body, "fur", leg_skin(an, bw))
    # wings (mark) on the flanks
    for sd, sx in ((1, "L"), (-1, "R")):
        sh, tip = V(0.07 * sd, -0.04, 0.3), V(0.082 * sd, 0.1, 0.305)
        an.bone("wing_" + sx, sh, tip, "hips", zref=(0, 0, 1))
        ww = chain(["wing_" + sx], [sh, tip], pre="hips", pre_blend=0.015)
        an.add(loft([sh, sh.lerp(tip, 0.5) + V(0.018 * sd, 0, 0.0), tip + V(0.004 * sd, 0.025, 0.012)],
                    [(0, 0.018, 0.04), (0.5, 0.024, 0.056), (1, 0.008, 0.022)], seg=10, rings=6, up=(0, 0, 1),
                    caps=(0.6, 0.9), cap_rings=1, sq=2.0), "mark", ww)
    # tail fan
    an.bone("tail", (0, 0.1, 0.33), (0, 0.16, 0.42), "hips", zref=(0, 1, 0))
    tw = chain(["tail"], [(0, 0.1, 0.33), (0, 0.16, 0.42)], pre="hips", pre_blend=0.02)
    an.add(loft([(0, 0.1, 0.32), (0, 0.15, 0.39), (0, 0.17, 0.44)], [(0, 0.03, 0.045), (0.5, 0.028, 0.06), (1, 0.012, 0.03)],
                seg=10, rings=5, up=(0, 1, 0), caps=(0.5, 0.9), cap_rings=1), "mark", tw)
    # neck + head
    O = V(0, -0.115, 0.43)
    bird_head_chain(an, (0, -0.07, 0.32), (0, -0.115, 0.37), O)
    nw = chain(["neck_1", "neck_2", "head"], [(0, -0.07, 0.32), (0, -0.115, 0.37), O, (0, -0.125, 0.5)],
               blend=[0.02, 0.018], pre="hips", pre_blend=0.02)
    an.add(loft([(0, -0.06, 0.29), (0, -0.108, 0.372), (0, -0.117, 0.45)], [(0, 0.058, 0.06), (0.5, 0.046, 0.048),
                (1, 0.038, 0.04)], seg=10, rings=5, caps=(0.4, 0.5), cap_rings=1), "fur", nw)
    hc = V(0, -0.125, 0.47)
    an.bone("head", O, V(0, -0.185, 0.47), "neck_2", zref=(0, 0, 1))
    hf = Frame(hc, (0, -1, 0), (0, 0, 1))
    head = ellip(hf.m(), (0.047, 0.058, 0.052), 12, 7)
    an.add(head, "fur", "head")
    # beak (upper on the head, lower = jaw)
    an.add(loft([hf.p(0, 0.035, 0.0), hf.p(0, 0.063, -0.006), hf.p(0, 0.083, -0.016)],
                [(0, 0.017, 0.012), (0.6, 0.009, 0.007), (1, 0.003, 0.003)], seg=7, rings=4, up=(0, 0, 1),
                caps=(0.3, 0.7), cap_rings=1), "beak", "head")
    an.bone("jaw", hf.p(0, 0.035, -0.012), hf.p(0, 0.075, -0.02), "head")
    an.add(loft([hf.p(0, 0.036, -0.012), hf.p(0, 0.07, -0.019)], [(0, 0.012, 0.006), (1, 0.003, 0.003)], seg=6,
                rings=3, up=(0, 0, 1), caps=(0.3, 0.6), cap_rings=1), "beak", "jaw")
    # small comb + wattles
    for (y, z, r) in ((0.018, 0.052, 0.017), (-0.006, 0.058, 0.019), (-0.028, 0.05, 0.015)):
        an.add(ellip(hf.m(hf.p(0, y + 0.01, z - 0.004)), (0.009, r * 0.9, r), 7, 5), "comb", "head")
    for sd in (1, -1):
        an.add(ellip(hf.m(hf.p(0.008 * sd, 0.038, -0.035)), (0.008, 0.009, 0.015), 6, 4), "comb", "jaw")
    ht = mesh_tree(head)
    for sd, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hc, hf.d(0.82 * sd, 0.45, 0.28), 0.016, 0.019, tree=ht, hl=(0.3, 0.2))
    # ---- rooster parts (separate mesh `Rooster`: hide it for hens)
    for (y, z, r) in ((0.03, 0.056, 0.02), (0.008, 0.072, 0.026), (-0.018, 0.076, 0.027), (-0.043, 0.066, 0.023),
                      (-0.062, 0.05, 0.017)):
        an.add(ellip(hf.m(hf.p(0, y, z)), (0.01, r * 0.85, r), 6, 4), "comb", "head", target="Rooster")
    for sd in (1, -1):
        an.add(ellip(hf.m(hf.p(0.01 * sd, 0.04, -0.05)), (0.009, 0.011, 0.024), 6, 4), "comb", "jaw", target="Rooster")
    for (dx, a, L) in ((0.0, 0.0, 1.0), (0.022, 8.0, 0.85), (-0.022, -8.0, 0.85)):
        b0 = V(dx, 0.11, 0.34)
        pts = [b0, b0 + V(dx * 0.4, 0.07 * L, 0.13 * L), b0 + V(dx * 0.8, 0.17 * L, 0.15 * L),
               b0 + V(dx, 0.23 * L, 0.06 * L)]
        an.add(loft(pts, [(0, 0.022, 0.009), (0.5, 0.026, 0.008), (1, 0.006, 0.004)], seg=8, rings=7, up=(1, 0, 0),
                    caps=(0.4, 0.9), cap_rings=1), "mark", tw, target="Rooster")
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        idle=dict(N=90),
        walk=dict(gait=Gait(16, 0.2, 0.6, BIPED, lift=0.045, flex=55.0, hoof=45.0, roll=18.0, centre=0.0, lift_bias=0.8),
                  bob=0.005, roll=4.0, yaw=3.0, headbob=0.9, hold=0.62, tail=4.0),
        run=dict(gait=Gait(10, 0.3, 0.45, BIPED, lift=0.06, flex=70.0, hoof=55.0, roll=22.0, centre=0.0, lift_bias=0.8),
                 bob=0.012, roll=5.0, yaw=2.0, lean=14.0, wing=16.0, flap=10.0, neck=-6.0, head=-10.0, tail=3.0,
                 tail_up=-8.0),
        eat=dict(N=48, lean=30.0, drop=0.03, ready=30.0, down=158.0, reach=0.97, head_down=62.0),
        call=dict(N=36, open=(9, 27), chest=-16.0, neck_ang=-14.0, reach=0.98, head=-26.0, jaw=32.0, flap=28.0),
    )
    an.clips = dict(BIRD_CLIPS)
    an.meta["call_open"] = round((9 - 1) / FPS, 3)
    return an


# =========================================================================== species: bebek (duck)
def k_idle_duck(an, solver):
    """look around, then turn the head back and preen the wing, tail wiggle."""
    N = 120
    poses = seq(N)
    look = Kc([(0, 0), (10, 0), (13, 24), (28, 24), (31, -18), (44, -18), (47, 0), (120, 0)], N)
    preen = Kc([(0, 0), (54, 0), (64, 1.0), (84, 1.0), (94, 0), (120, 0)], N)
    for f, p in enumerate(poses):
        ph = f / N
        br = syc(3 * ph)
        pr = preen(f)
        p.mv("hips", dz=0.002 * br)
        p.r("hips", pitch=0.8 * br, roll=3.0 * pr)
        p.r("neck_1", yaw=look(f) * 0.3 + 70.0 * pr, pitch=8.0 * pr)
        p.r("neck_2", yaw=look(f) * 0.3 + 60.0 * pr, pitch=25.0 * pr)
        p.r("head", yaw=look(f) * 0.4 + 30.0 * pr + 8.0 * pr * syc(6 * ph), pitch=35.0 * pr)
        p.r("jaw", pitch=6.0 * pr * (0.5 + 0.5 * syc(10 * ph)))
        wig = math.exp(-((f - 30) / 3.0) ** 2) + math.exp(-((f - 104) / 3.0) ** 2)
        p.r("tail", roll=18.0 * wig * math.sin(TAU * f / 5.0), pitch=2.0 * br)
        for sd, sx in ((1, "L"), (-1, "R")):
            p.r("wing_" + sx, roll=sd * (1.5 * br + (10.0 * pr if sd > 0 else 0.0)))
        eyes(p, min(blink(f, 20, 4), blink(f, 100, 4), 1.0 - 0.5 * pr))
    return N, True, poses


def k_dabble(an, solver):
    """duck: lean forward, bill down to the ground and dabble (quick nibbling, side sweeps)."""
    P = an.anim["eat"]
    N = P.get("N", 60)
    poses = seq(N)
    down = Kc([(0, 0.0), (8, 1.0), (40, 1.0), (48, 0.2), (52, 0.2), (56, 1.0), (60, 1.0)], N)
    ch = an.chains["neck"]
    rest = an.bhead("head") - an.bhead("neck_1")
    a_rest = math.degrees(math.atan2(-rest.y, rest.z))
    k_rest = rest.length / (ch["l1"] + ch["l2"])
    for f, p in enumerate(poses):
        ph = f / N
        d = down(f)
        p.r("hips", pitch=P.get("lean", 30.0) * (0.3 + 0.7 * d))
        p.mv("hips", dz=-0.015 * an.size * d)
        base = neck_base(solver, p)
        ang = lerp(a_rest, P.get("down", 150.0), d)
        T = base + neck_reach(an, ang, lerp(k_rest, 0.97, d)) + V(0.012 * an.size * d * syc(3 * ph), 0, 0)
        p.chains["neck"] = dict(T=T, end_rot=D(pitch=lerp(0.0, P.get("head_down", 60.0), d), yaw=10.0 * d * syc(3 * ph)),
                                pole=neck_reach(an, ang - 90.0))
        p.r("jaw", pitch=d * 9.0 * (0.5 + 0.5 * syc(15 * ph)))
        p.r("tail", roll=6.0 * syc(3 * ph), pitch=-5.0 * d)
        eyes(p, blink(f, 30, 4))
    solver.reach_fix(poses, True)
    return N, True, poses


def k_quack(an, solver):
    """two quacks: head forward, bill opens twice."""
    P = an.anim["call"]
    N = P.get("N", 30)
    poses = seq(N)
    fwd = Kc([(0, 0), (4, 1.0), (20, 1.0), (30, 0)])
    jaw = Kc([(0, 0), (4, 0), (6, 1.0), (9, 0.9), (11, 0), (13, 0), (15, 1.0), (18, 0.9), (20, 0), (30, 0)])
    for f, p in enumerate(poses):
        u, j = fwd(f), jaw(f)
        p.r("hips", pitch=4.0 * u)
        p.r("neck_1", pitch=14.0 * u)
        p.r("neck_2", pitch=-6.0 * u + 3.0 * j)
        p.r("head", pitch=-12.0 * u - 4.0 * j)
        p.r("jaw", pitch=P.get("jaw", 30.0) * j)
        p.r("tail", roll=10.0 * j * math.sin(TAU * f / 4.0))
        for sd, sx in ((1, "L"), (-1, "R")):
            p.r("wing_" + sx, roll=sd * 8.0 * u)
        eyes(p, 1.0)
    solver.reach_fix(poses, False)
    return N, False, poses


def k_swim(an, solver):
    """floating (origin = water line): body level and low in the water, feet paddling, gentle bob."""
    P = an.anim["swim"]
    N = P.get("N", 36)
    poses = seq(N)
    for f, p in enumerate(poses):
        ph = f / N
        p.mv("hips", dz=-P["draft"] + 0.004 * an.size * syc(ph), dy=P.get("dy", 0.0))
        p.r("hips", pitch=P.get("pitch", 22.0) + 1.5 * syc(ph + 0.25), roll=1.5 * syc(ph))
        p.r("neck_1", pitch=P.get("neck", -10.0) + 2.0 * syc(2 * ph))
        p.r("neck_2", pitch=-6.0)
        p.r("head", pitch=P.get("head", -8.0) - 2.0 * syc(2 * ph), yaw=6.0 * syc(ph))
        p.r("tail", roll=5.0 * syc(2 * ph), pitch=-10.0)
        for sd, sx in ((1, "L"), (-1, "R")):
            p.r("wing_" + sx, roll=sd * 2.0)
        for lg in an.legs:
            q = ph + (0.0 if lg.name == "L" else 0.5)
            A = lg.A + V(0, P.get("foot_y", 0.05) + P.get("stroke", 0.045) * syc(q), -P["draft"] + P.get("foot_z", 0.06)
                         + 0.012 * cyc(q))
            p.legs[lg.name] = dict(A=A, hoof=P.get("fold", 70.0) * (0.5 + 0.5 * cyc(q)) + P.get("foot_pitch", -10.0),
                                   flex=P.get("tuck", 40.0))
        p.r("jaw", pitch=0.0)
        eyes(p, blink(f, 20, 4))
    return N, True, poses


def build_bebek():
    an = Animal("bebek", size=0.42)
    std_mats(an, "#f5f1e8", "#ddd3c1")
    an.mat("beak", "AnimalBeak_bebek", "#ef9a3a", 0.6)
    an.variants = [dict(name="putih", fur="#f5f1e8", mark="#ddd3c1"),
                   dict(name="coklat", fur="#9e7c5a", mark="#6c533c"),
                   dict(name="belang", fur="#d8cab0", mark="#8a6a4c")]
    an.bone("hips", (0, 0.07, 0.22), (0, -0.05, 0.28))
    body = loft([(0, 0.12, 0.2), (0, 0.02, 0.24), (0, -0.07, 0.3)],
                [(0, 0.064, 0.06), (0.35, 0.09, 0.087), (0.75, 0.084, 0.084), (1, 0.06, 0.062)],
                seg=14, rings=7, caps=(0.9, 0.75), sq=2.0)
    bw = lambda p: {"hips": 1.0}   # noqa: E731
    bird_leg(an, 0.04, H=(0.05, 0.2), K=(0.02, 0.15), C=(0.055, 0.075), A=(0.045, 0.018), toe=(-0.015, 0.0),
             radii=(0.03, 0.026, 0.011, 0.01), top_z=0.19, knee_key="fur", shank_key="beak", shank_z=0.1,
             toes=[], toe_r=0.006, web=(0.03, 0.034, 0.0055, 0.03))
    an.add(body, "fur", leg_skin(an, bw))
    for sd, sx in ((1, "L"), (-1, "R")):
        sh, tip = V(0.058 * sd, -0.035, 0.29), V(0.045 * sd, 0.12, 0.21)
        an.bone("wing_" + sx, sh, tip, "hips", zref=(0, 0, 1))
        ww = chain(["wing_" + sx], [sh, tip], pre="hips", pre_blend=0.015)
        an.add(loft([sh, sh.lerp(tip, 0.5) + V(0.02 * sd, 0, 0.005), tip + V(-0.01 * sd, 0.025, -0.005)],
                    [(0, 0.016, 0.034), (0.5, 0.022, 0.05), (1, 0.007, 0.018)], seg=10, rings=6, up=(0, 0, 1),
                    caps=(0.6, 0.9), cap_rings=1), "mark", ww)
    an.bone("tail", (0, 0.13, 0.21), (0, 0.19, 0.26), "hips", zref=(0, 1, 0))
    tw = chain(["tail"], [(0, 0.13, 0.21), (0, 0.19, 0.26)], pre="hips", pre_blend=0.02)
    an.add(loft([(0, 0.12, 0.2), (0, 0.17, 0.225), (0, 0.2, 0.265)], [(0, 0.035, 0.022), (0.6, 0.02, 0.014),
                (1, 0.004, 0.004)], seg=8, rings=4, caps=(0.5, 0.9), cap_rings=1), "fur", tw)
    O = V(0, -0.084, 0.425)
    bird_head_chain(an, (0, -0.065, 0.33), (0, -0.09, 0.375), O)
    nw = chain(["neck_1", "neck_2", "head"], [(0, -0.065, 0.33), (0, -0.09, 0.375), O, (0, -0.1, 0.52)],
               blend=[0.02, 0.018], pre="hips", pre_blend=0.02)
    an.add(loft([(0, -0.05, 0.3), (0, -0.087, 0.375), (0, -0.088, 0.445)], [(0, 0.056, 0.056), (0.5, 0.043, 0.044),
                (1, 0.04, 0.04)], seg=10, rings=5, caps=(0.4, 0.5), cap_rings=1), "fur", nw)
    hc = V(0, -0.1, 0.468)
    an.bone("head", O, V(0, -0.17, 0.468), "neck_2", zref=(0, 0, 1))
    hf = Frame(hc, (0, -1, 0), (0, 0, 1))
    head = ellip(hf.m(), (0.052, 0.066, 0.053), 12, 7)
    an.add(head, "fur", "head")
    an.add(loft([hf.p(0, 0.04, -0.006), hf.p(0, 0.08, -0.015), hf.p(0, 0.112, -0.021)],
                [(0, 0.027, 0.013), (0.5, 0.027, 0.009), (1, 0.026, 0.007)], seg=10, rings=4, up=(0, 0, 1),
                caps=(0.2, 0.55), cap_rings=1, sq=2.6), "beak", "head")
    an.bone("jaw", hf.p(0, 0.045, -0.019), hf.p(0, 0.105, -0.029), "head")
    an.add(loft([hf.p(0, 0.045, -0.02), hf.p(0, 0.104, -0.029)], [(0, 0.02, 0.007), (1, 0.021, 0.005)], seg=8, rings=3,
                up=(0, 0, 1), caps=(0.2, 0.5), cap_rings=1, sq=2.4), "beak", "jaw")
    ht = mesh_tree(head)
    for sd, sx in ((1, "L"), (-1, "R")):
        add_eye(an, head, hf, "eye_" + sx, "head", hc, hf.d(0.76 * sd, 0.48, 0.42), 0.017, 0.02, tree=ht, hl=(0.3, 0.2))
    an.scale_bones = ["eye_L", "eye_R"]
    an.anim = dict(
        walk=dict(gait=Gait(18, 0.17, 0.62, BIPED, lift=0.032, flex=45.0, hoof=35.0, roll=15.0, centre=0.0,
                            lift_bias=0.85, splay=0.01), bob=0.004, roll=8.0, yaw=5.0, tail=8.0, neck=2.0, head=-2.0),
        run=dict(gait=Gait(11, 0.26, 0.5, BIPED, lift=0.045, flex=55.0, hoof=45.0, roll=20.0, centre=0.0,
                           lift_bias=0.8, splay=0.012), bob=0.008, roll=10.0, yaw=5.0, lean=10.0, wing=22.0,
                 flap=22.0, neck=8.0, head=-8.0, tail=6.0),
        eat=dict(N=60, lean=32.0, down=150.0, head_down=55.0),
        call=dict(N=30, jaw=30.0),
        swim=dict(N=36, draft=0.2, pitch=24.0, neck=-12.0, head=-6.0, foot_y=0.04, foot_z=0.05, stroke=0.04,
                  fold=70.0, tuck=35.0),
    )
    an.clips = dict(idle=k_idle_duck, walk=b_walk("walk"), run=b_walk("run"), eat=k_dabble, call=k_quack, swim=k_swim)
    an.meta["call_open"] = round(5 / FPS, 3)
    an.meta["swim_draft"] = 0.0
    return an


# =========================================================================== species: kodok (frog)
FROG_HOP = {"HL": -0.26, "HR": -0.26, "FL": -0.33, "FR": -0.33}


def f_idle(an, solver):
    N = 90
    poses = seq(N)
    look = Kc([(0, 0), (30, 0), (38, 12), (60, 12), (68, 0), (90, 0)], N)
    for f, p in enumerate(poses):
        ph = f / N
        th = 0.5 + 0.5 * syc(6 * ph)
        p.sc("throat", 1.0 + 0.14 * th, 1.0 + 0.1 * th, 1.0 + 0.18 * th)
        p.sc("body", 1.0 + 0.012 * syc(3 * ph), 1.0, 1.0 + 0.02 * syc(3 * ph))
        p.r("head", yaw=look(f), pitch=-1.0 * syc(3 * ph))
        p.r("jaw", pitch=0.0)
        p.sc("tongue", 1.0, 1.0, 1.0)
        eyes(p, min(blink(f, 22, 6), blink(f, 75, 6)))
    return N, True, poses


def f_crawl(an, solver):
    g = an.anim["walk"]["gait"]
    N = g.N
    poses = seq(N)
    for f, p in enumerate(poses):
        ph = f / N
        for lg in an.legs:
            p.legs[lg.name] = g.leg(lg, f)
        p.r("hips", roll=3.0 * syc(ph), yaw=3.0 * syc(ph + 0.25))
        p.r("head", yaw=-2.0 * syc(ph + 0.25))
        p.sc("throat", 1.0 + 0.08 * (0.5 + 0.5 * syc(2 * ph)), 1.0, 1.0 + 0.1 * (0.5 + 0.5 * syc(2 * ph)))
        p.sc("body", 1.0, 1.0, 1.0)
        p.sc("tongue", 1.0, 1.0, 1.0)
        p.r("jaw", pitch=0.0)
        eyes(p, 1.0)
    solver.reach_fix(poses, True)
    return N, True, poses


HOP = dict(N=18, lift_front=4, lift_hind=6, land_front=12, land_hind=13, distance=0.3)


def f_hop_poses(an, solver):
    """One hop IN PLACE: crouch, push off (hind feet planted while the legs extend), airborne (hind legs
    trail, front legs reach), land front first, squash, settle. The game moves the node forward by
    hop_distance between hop_air_start and hop_air_end (the feet are off the ground then)."""
    h = HOP
    N = h["N"]
    k = an.size / 0.28
    poses = seq(N)
    up = Kc([(0, 0.0), (2, -0.009), (4, 0.004), (6, 0.03), (9, 0.062), (12, 0.02), (13, 0.004), (14, -0.011),
             (16, -0.004), (18, 0.0)])
    pit = Kc([(0, 0.0), (2, 6.0), (4, -14.0), (6, -24.0), (9, -4.0), (11, 10.0), (13, 7.0), (15, -2.0), (18, 0.0)])
    st = Kc([(0, 0.0), (2, -0.35), (5, 0.8), (7, 1.0), (10, 0.2), (12, 0.0), (14, -1.0), (16, -0.3), (18, 0.0)])
    for f, p in enumerate(poses):
        q = st(f)
        p.mv("hips", dz=up(f) * k)
        p.r("hips", pitch=pit(f))
        if q >= 0:
            p.sc("body", 1.0 - 0.08 * q, 1.0 + 0.22 * q, 1.0 - 0.08 * q)
        else:
            p.sc("body", 1.0 - 0.12 * q, 1.0 - 0.06 * q, 1.0 + 0.22 * q)
        air = clamp((f - h["lift_front"]) / (h["land_front"] - h["lift_front"]))
        p.r("head", pitch=-8.0 * math.sin(math.pi * air))
        for lg in an.legs:
            if lg.front:
                w = clamp((f - h["lift_front"]) / (h["land_front"] - h["lift_front"]))
                reach = math.sin(math.pi * w)
                A = lg.A + V(0.004 * lg.side * reach, -0.018 * k * reach, 0.03 * k * reach ** 0.7)
                p.legs[lg.name] = dict(A=A, hoof=25.0 * reach)
            else:
                w = clamp((f - h["lift_hind"]) / (h["land_hind"] - h["lift_hind"]))
                tr = ss(0.0, 0.4, w) * (1.0 - ss(0.55, 1.0, w))
                A = lg.A + V(-0.02 * lg.side * tr, 0.15 * k * tr, 0.035 * k * tr)
                p.legs[lg.name] = dict(A=A, hoof=60.0 * tr, flex=-60.0 * tr)
        p.sc("throat", 1.0, 1.0, 1.0)
        p.sc("tongue", 1.0, 1.0, 1.0)
        p.r("jaw", pitch=0.0)
        eyes(p, 1.0 - 0.3 * max(0.0, -q))
    return N, poses


def f_hop(an, solver):
    N, poses = f_hop_poses(an, solver)
    return N, False, poses


def f_run(an, solver):
    N, poses = f_hop_poses(an, solver)
    return N, True, poses


def f_eat(an, solver):
    """tongue flick: lunge, mouth open, tongue shoots out and back, gulp (eyes pressed shut)."""
    N = 48
    poses = seq(N)
    lunge = Kc([(0, 0), (10, 0), (13, 1.0), (17, 1.0), (21, 0.2), (30, 0), (48, 0)])
    jaw = Kc([(0, 0), (11, 0), (13, 1.0), (17, 1.0), (19, 0), (48, 0)])
    tongue = Kc([(0, 1.0), (12, 1.0), (14, 4.2), (16, 4.2), (18, 1.0), (48, 1.0)])
    gulp = Kc([(0, 0), (20, 0), (23, 1.0), (30, 1.0), (33, 0), (48, 0)])
    for f, p in enumerate(poses):
        l, j, t, gp = lunge(f), jaw(f), tongue(f), gulp(f)
        p.r("hips", pitch=8.0 * l)
        p.mv("hips", dy=-0.01 * l * an.size / 0.24)
        p.r("head", pitch=-8.0 * l)
        p.r("jaw", pitch=32.0 * j)
        p.sc("tongue", 1.0, t, 1.0 + 0.3 * (t - 1.0) / 3.2)
        p.sc("throat", 1.0 + 0.2 * gp, 1.0, 1.0 + 0.3 * gp)
        p.sc("body", 1.0, 1.0, 1.0 - 0.05 * gp)
        eyes(p, 1.0 - 0.9 * gp)
    solver.reach_fix(poses, True)
    return N, True, poses


def f_call(an, solver):
    """croak: the vocal sac balloons twice (sound starts at call_open)."""
    N = 40
    poses = seq(N)
    sac = Kc([(0, 0), (6, 0), (10, 1.0), (14, 1.0), (17, 0.1), (21, 0.1), (25, 1.0), (29, 1.0), (33, 0), (40, 0)])
    for f, p in enumerate(poses):
        k = sac(f)
        p.sc("throat", 1.0 + 1.15 * k, 1.0 + 0.8 * k, 1.0 + 1.3 * k)
        p.sc("body", 1.0 + 0.04 * k, 1.0, 1.0 + 0.05 * k)
        p.r("hips", pitch=-4.0 * k)
        p.r("head", pitch=-6.0 * k)
        p.r("jaw", pitch=0.0)
        p.sc("tongue", 1.0, 1.0, 1.0)
        eyes(p, 1.0 - 0.35 * k)
    solver.reach_fix(poses, False)
    return N, False, poses


def build_kodok():
    an = Animal("kodok", size=0.28)
    std_mats(an, "#7cb04a", "#efe3a8", mark2="#4a7630")
    an.mat("tongue", "AnimalTongue", "#e2727a", 0.5)
    an.variants = [dict(name="hijau", fur="#7cb04a", mark="#efe3a8", mark2="#4a7630"),
                   dict(name="coklat", fur="#9a7a4c", mark="#eadcb4", mark2="#5f4a2e"),
                   dict(name="kuning", fur="#b7bd4a", mark="#f3ebbd", mark2="#6f7a2e")]
    an.bone("hips", (0, 0.05, 0.058), (0, -0.02, 0.066))
    an.bone("body", (0, 0.05, 0.058), (0, -0.035, 0.072), "hips")
    spots = [(0.03, 0.035, 0.016), (-0.028, 0.05, 0.014), (0.004, 0.0, 0.013), (-0.036, 0.0, 0.011), (0.042, -0.01, 0.01),
             (0.0, 0.07, 0.012)]

    body = loft([(0, 0.078, 0.052), (0, 0.02, 0.062), (0, -0.035, 0.072)],
                [(0, 0.05, 0.034), (0.4, 0.068, 0.044), (1, 0.06, 0.042)], seg=14, rings=6, caps=(0.8, 0.5), sq=2.2)
    an.add(body, lambda c, n: "mark" if n.z < -0.35 else "fur", "body")
    for (x, y, r) in spots:        # round dark spots on the back
        an.add(decal(body, (x, y, 0.1), (0, 0, 1), (0, -1, 0), r, r * 1.15, rings=2, seg=12, lift=0.0015), "mark2", "body")
    an.bone("head", (0, -0.03, 0.074), (0, -0.12, 0.07), "body")
    head = loft([(0, -0.02, 0.075), (0, -0.075, 0.074), (0, -0.115, 0.064)],
                [(0, 0.062, 0.04), (0.5, 0.06, 0.034), (1, 0.042, 0.022)], seg=14, rings=6, caps=(0.3, 0.8), sq=2.3)
    an.add(head, lambda c, n: "mark" if n.z < -0.4 else "fur", "head")
    an.bone("jaw", (0, -0.03, 0.052), (0, -0.11, 0.05), "head")
    an.add(loft([(0, -0.03, 0.052), (0, -0.08, 0.051), (0, -0.113, 0.053)], [(0, 0.056, 0.02), (1, 0.036, 0.012)],
                seg=12, rings=4, caps=(0.3, 0.8), cap_rings=1), "mark", "jaw")
    an.add(ellip(frame_m((0, -0.075, 0.056), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.045, 0.036, 0.008), 10, 4), "dark", "head")
    an.bone("tongue", (0, -0.05, 0.057), (0, -0.1, 0.057), "jaw", zref=(0, 0, 1))
    an.add(ellip(frame_m((0, -0.075, 0.058), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.015, 0.028, 0.007), 8, 4), "tongue", "tongue")
    an.bone("throat", (0, -0.055, 0.046), (0, -0.055, 0.02), "head", zref=(0, -1, 0))
    an.add(ellip(frame_m((0, -0.06, 0.04), (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.03, 0.028, 0.017), 10, 5), "mark", "throat")
    hf = Frame((0, -0.06, 0.08), (0, -1, 0), (0, 0, 1))
    for sd, sx in ((1, "L"), (-1, "R")):
        bc = V(0.036 * sd, -0.056, 0.104)
        bulge = ellip(frame_m(bc, (1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.024, 0.024, 0.021), 10, 6)
        an.add(bulge, "fur", "head")
        add_eye(an, bulge, hf, "eye_" + sx, "head", bc, (0.62 * sd, -0.5, 0.6), 0.017, 0.019, hl=(0.3, 0.25))
    # legs: short front legs, folded Z hind legs (thighs outside the body)
    for sd, sx in ((1, "L"), (-1, "R")):
        P = lambda x, y, z: V(x * sd, y, z)   # noqa: E731
        fl = add_leg(an, "F" + sx, sd, "front", "hips", P(0.042, -0.032, 0.052), P(0.062, -0.045, 0.03), None,
                     P(0.06, -0.068, 0.012), P(0.068, -0.094, 0.0), P(0.066, -0.085, 0.0), pole=(0, 1, 0), flex_sign=1,
                     front=True, radii=(0.016, 0.014, 0.011, 0.01), top_z=0.06, seg=7, rings=5, skin=0.2, plane=True)
        an.add(ellip(frame_m(fl.A.lerp(fl.toe, 0.55) + V(0, 0, 0.004), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
                     (0.017, 0.019, 0.005), 8, 3), "fur", fl.foot)
        H = P(0.045, 0.058, 0.055)

        def bars(c, n, H=H):
            d = (c - H).length
            return "mark2" if (n.z > 0.1 and int(d / 0.022) % 2 == 1) else ("mark" if n.z < -0.5 else "fur")
        hl = add_leg(an, "H" + sx, sd, "hind", "hips", H, P(0.105, 0.0, 0.048), P(0.088, 0.085, 0.026),
                     P(0.1, 0.035, 0.012), P(0.122, -0.04, 0.0), P(0.112, -0.005, 0.0), pole=(0.9 * sd, -0.5, 0.2),
                     flex_sign=-1, front=False, radii=(0.03, 0.026, 0.015, 0.012), top_z=0.06, seg=8, rings=8,
                     from_H=True, paint=bars, pre="hips", skin=0.0, plane=True)
        fc = hl.A.lerp(hl.toe, 0.5)
        fd = (hl.toe - hl.A).normalized()
        an.add(ellip(frame_m(fc + V(0, 0, 0.004), V(fd.y, -fd.x, 0).normalized() * sd, fd, (0, 0, 1)),
                     (0.03, 0.05, 0.005), 10, 3), "fur", hl.foot)
    an.scale_bones = ["eye_L", "eye_R", "throat", "body", "tongue"]
    an.anim = dict(
        walk=dict(gait=Gait(24, 0.06, 0.72, {"FL": 0.25, "HR": 0.5, "FR": 0.75, "HL": 0.0}, lift=(0.015, 0.012),
                            flex=(0.0, 20.0), hoof=15.0, roll=8.0, centre=0.0)),
        run=dict(gait=Gait(18, 0.3, 0.52, FROG_HOP, lift=(0.03, 0.02), flex=(0.0, 0.0), hoof=40.0, roll=25.0,
                           centre=0.0, lift_bias=0.7)),
    )
    an.clips = dict(idle=f_idle, walk=f_crawl, run=f_run, eat=f_eat, call=f_call, hop=f_hop)
    an.meta["call_open"] = round(7 / FPS, 3)
    t0 = (HOP["lift_front"] + HOP["lift_hind"]) * 0.5 / FPS
    t1 = (HOP["land_front"] + HOP["land_hind"]) * 0.5 / FPS
    an.meta["hop_time"] = round(HOP["N"] / FPS, 3)
    an.meta["hop_distance"] = HOP["distance"]
    an.meta["hop_air_start"] = round(t0, 3)
    an.meta["hop_air_end"] = round(t1, 3)
    an.meta["hop_speed"] = round(HOP["distance"] / (HOP["N"] / FPS), 3)   # average, if the node moves steadily
    return an


# --------------------------------------------------------------------------- main
BUILDERS = {"sapi": build_sapi, "kerbau": build_kerbau, "kambing": build_kambing, "anjing": build_anjing,
            "kucing": build_kucing, "ayam": build_ayam, "bebek": build_bebek,
            "kodok": build_kodok}
ORDER = ["sapi", "kerbau", "kambing", "ayam", "bebek", "kodok", "kucing", "anjing"]


def mesh_dims(meshes):
    pts = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def build_one(sid, out=True, sheets=None, sheet_n=8, views=("game", "side"), look=False):
    reset_scene()
    an = BUILDERS[sid]()
    rig, meshes = assemble(an, bake=out)
    solver = Solver(an, rig)
    mn, mx = mesh_dims(meshes)
    an.meta["height"] = round(mx.z, 3)
    an.meta["length"] = round(mx.y - mn.y, 3)
    an.meta["width"] = round(mx.x - mn.x, 3)
    acts, rep = bake(an, solver, an.clips)
    tris = sum(count_tris(m) for m in meshes)
    mats = sorted({s.material.name for m in meshes for s in m.material_slots})
    info = dict(id=sid, tris=tris, mats=mats, bones=len(rig.data.bones), clips=rep, dims=(an.meta["length"], an.meta["width"], an.meta["height"]))
    print(f"[animal] {sid}: tris={tris} bones={len(rig.data.bones)} mats={mats} "
          f"L/W/H={an.meta['length']}/{an.meta['width']}/{an.meta['height']}")
    for k, v in rep.items():
        print(f"    {k:5s} N={v['N']:3d} loop={v['loop']!s:5s} max turn/frame {v['turn']:5.1f} deg ({v['at']}) "
              f"IK foot err {v['foot_err_mm']} mm")
    if tris > TRI_BUDGET:
        print(f"  !! {sid} over the triangle budget ({tris} > {TRI_BUDGET})")
    extras = dict(species=sid, height=an.meta["height"], length=an.meta["length"],
                  variants=json.dumps(an.variants), loops=",".join(k for k, v in rep.items() if v["loop"]),
                  clips=",".join(rep.keys()))
    for kind in ("walk", "run"):
        if kind in an.anim and "gait" in an.anim[kind]:
            g = an.anim[kind]["gait"]
            extras["%s_speed" % kind] = round(g.speed(), 3)
            extras["%s_stance" % kind] = g.stance
    for k in ("call_open", "hop_speed", "hop_time", "hop_distance", "hop_air_start", "hop_air_end", "swim_draft"):
        if k in an.meta:
            extras[k] = an.meta[k]
    info["extras"] = extras
    if out and "--no-export" not in sys.argv:
        rig.animation_data.action = acts["idle"]
        bpy.context.scene.frame_set(0)
        path = export(an, rig, meshes, extras)
        fl = CH.glb_quat_continuity(path)
        chk = glb_check(path, [k for k, v in rep.items() if v["loop"]])
        info["glb"] = chk
        print(f"  [export] {os.path.basename(path)} ({os.path.getsize(path) // 1024} KB), {fl} keys re-signed, GLB "
              f"turn/60Hz, flips, seam: {chk}")
        mark_loops(an.name, [k for k, v in rep.items() if v["loop"]])
        preview_materials()
        render_preview_variants(an, rig, meshes, acts)
    if look:
        preview_materials()
        os.makedirs(SCRATCH, exist_ok=True)
        render_views(an, rig, meshes, acts, os.path.join(SCRATCH, "look_%s.png" % sid))
    if sheets:
        preview_materials()
        os.makedirs(os.path.join(SCRATCH, "sheets"), exist_ok=True)
        for clip in sheets:
            if clip in acts:
                render_sheet(an, rig, meshes, acts, clip, os.path.join(SCRATCH, "sheets", "animal_%s_%s.png" % (sid, clip)),
                             n=sheet_n, views=views)
    return an, rig, meshes, acts, info


LINEUP_ROWS = [["kerbau", "sapi", "kambing", "anjing"], ["kucing", "ayam", "bebek", "kodok"]]


def lineup():
    """All species (+ a second colour variant, the rooster, and a villager for scale) in two rows."""
    reset_scene()
    rows = []
    for ri, row in enumerate(LINEUP_ROWS):
        items = []
        for sid in row:
            an = BUILDERS[sid]()
            rig, meshes = assemble(an, bake=True)
            solver = Solver(an, rig)
            acts, _rep = bake(an, solver, {"idle": an.clips["idle"]})
            mn, mx = mesh_dims(meshes)
            an.meta["height"] = mx.z
            preview_materials()
            for vi in range(min(2, len(an.variants))):
                w = max(mx.x - mn.x, (mx.y - mn.y) * 0.62)
                sn = variant_snaps(an, rig, meshes, acts, vi, (0, 0, 0), 24.0, 12 + 17 * vi)
                items.append((sn, w))
            for m in list(bpy.data.materials):
                if m.name.startswith("Animal") and "__" not in m.name:
                    m.name = m.name + "__" + sid
            for o in meshes + [rig]:
                bpy.data.objects.remove(o, do_unlink=True)
        rows.append(items)
    # villager for scale (front row, left)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS_DIR, "char_petani.glb"))
    vill = [o for o in bpy.data.objects if o not in before]
    rows[0].insert(0, (vill, 0.5))
    for o in vill:
        if o.parent is None:
            o.rotation_euler = (0, 0, rad(24.0))
    ys = [0.0, -1.6]
    total_w = 0.0
    for ri, items in enumerate(rows):
        gap = 0.18 if ri else 0.3
        width = sum(w for _, w in items) + gap * (len(items) - 1)
        total_w = max(total_w, width)
        x = -width / 2
        for objs, w in items:
            for o in objs:
                if o.parent is None:
                    o.location.x += x + w / 2
                    o.location.y += ys[ri]
            x += w + gap
    tmp = CH._scene_setup(1600, 900, samples=16, ground="#8fb35c")
    tmp.append(CH._camera((0, -0.75, 0.45), 32.0, 0.0, 30, ortho=total_w * 1.08))
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, "animal_lineup.png")
    bpy.ops.render.render(write_still=True)
    print("[preview] animal_lineup.png")


def write_data(infos):
    """game/data/animal_models.json: what the behaviour code needs (clips, speeds, variants, sizes)."""
    data = {}
    if os.path.exists(DATA_JSON):
        try:
            data = json.load(open(DATA_JSON)).get("species", {})
        except Exception:
            data = {}
    for i in infos:
        ex = dict(i["extras"])
        ex["variants"] = json.loads(ex["variants"])
        data[i["id"]] = dict(model="res://assets/models/animal_%s.glb" % i["id"], triangles=i["tris"], bones=i["bones"],
                             materials=i["mats"], size_lwh=list(i["dims"]),
                             clips={k: dict(frames=v["N"], seconds=round(v["N"] / FPS, 3), loop=v["loop"])
                                    for k, v in i["clips"].items()}, **{k: v for k, v in ex.items() if k not in ("clips", "loops")})
    doc = dict(note="Generated by blender/animals.py - do not edit. Models face +Z (Godot), origin on the ground, "
                    "1 unit = 1 m. walk_speed/run_speed = ground speed (m/s) of the walk/run clip at playback 1.0. "
                    "Variants: set the albedo of surfaces named AnimalFur_<id> / AnimalMark_<id> / AnimalMark2_<id>; "
                    "ayam: hide the `Rooster` mesh unless the variant has rooster=true. kodok hop is in place: move the "
                    "node hop_distance forward between hop_air_start and hop_air_end. bebek swim: the origin is the "
                    "water line (place the node at the water level).",
               species={k: data[k] for k in ORDER if k in data})
    json.dump(doc, open(DATA_JSON, "w"), indent=1)
    print("[data]", DATA_JSON)


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    no_out = "--no-out" in argv
    sheets = None
    views = ("game", "side")
    n = 8
    for a in argv:
        if a == "--sheets":
            sheets = ["idle", "walk", "run", "eat", "call", "hop", "swim", "sit", "wag"]
        elif a.startswith("--sheets="):
            sheets = a.split("=", 1)[1].split(",")
        elif a.startswith("--views="):
            views = tuple(a.split("=", 1)[1].split(","))
        elif a.startswith("--sheet-n="):
            n = int(a.split("=", 1)[1])
    order = [s for s in ORDER if s in BUILDERS]
    if "--lineup" in argv:
        lineup()
        return
    todo = names or order
    infos = []
    for sid in todo:
        _an, _rig, _meshes, _acts, info = build_one(sid, out=not no_out, sheets=sheets, sheet_n=n, views=views,
                                                    look="--look" in argv)
        infos.append(info)
    if not no_out and "--no-export" not in argv:
        write_data(infos)
    if not names and not no_out and "--no-export" not in argv:
        lineup()
    print("\n==== summary ====")
    for i in infos:
        print(f"{i['id']:8s} tris={i['tris']:5d} bones={i['bones']:3d} L/W/H={i['dims']} mats={i['mats']}")
        print(f"{'':8s} clips: " + ", ".join(f"{k}({v['N']}f{'-loop' if v['loop'] else ''})" for k, v in i["clips"].items()))


if __name__ == "__main__":
    main(sys.argv[1:])

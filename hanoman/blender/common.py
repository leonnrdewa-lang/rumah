"""Shared helpers for the Hanoman Duta Blender asset scripts.

Run any asset script with plain Python 3 (Blender 4.5 is installed as the `bpy` module):

    python3 hanoman/blender/characters.py            # all characters
    python3 hanoman/blender/characters.py hanoman    # just one
    python3 hanoman/blender/props.py --no-preview    # export only

Conventions (see ../DESIGN.md "Kontrak aset"):
  * 1 unit = 1 m, Z up, feet / base on z = 0, front faces -Y (glTF export -> Godot +Z).
  * One root Empty named `<id>`; characters get pivot Empties (body, head, arm_l ...)
    with the meshes of each part joined into ONE mesh parented under its pivot.
  * Flat materials (Principled, roughness 0.8), named M_<Surface>; emissive ones are
    named M_Glow<Something> and their base colour is the glow colour.

Geometry is built straight into bmesh "groups" (one per pivot) in WORLD coordinates,
so there are no intermediate Blender objects; `Model.build()` creates the Empties and
meshes (mesh data expressed relative to its pivot) and `export()` writes the GLB.
"""
import math
import os
import random
import sys

import bpy  # noqa: I001 (bpy must be imported before bmesh)
import bmesh
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # hanoman/
MODELS_DIR = os.path.join(ROOT, "game", "assets", "models")
PORTRAIT_DIR = os.path.join(ROOT, "game", "assets", "portraits")
ICONS_DIR = os.path.join(ROOT, "game", "assets", "icons")
PREVIEW_DIR = os.path.join(HERE, "previews")
for _d in (MODELS_DIR, PORTRAIT_DIR, ICONS_DIR, PREVIEW_DIR):
    os.makedirs(_d, exist_ok=True)

# DESIGN.md palette + extra tones used by the assets
P = {
    "night": "#10141c", "night2": "#1b2330",
    "moss_dark": "#1f3b33", "moss": "#2e5a45", "leaf": "#4f7a4a",
    "brick_dark": "#8a4a36", "brick": "#b0643f",
    "stone_dark": "#4b4f57", "stone": "#6c707a",
    "teal": "#5fe0c8", "sun": "#f2b845", "blue": "#4aa3ff", "violet": "#b784ff",
    "magenta": "#e0508f", "fur_white": "#f4f1ea", "gold": "#d9a93a",
    "gold_dark": "#a87a22", "red": "#b3262e", "red_dark": "#7a1a22", "black": "#1c1a1f",
    "poleng_w": "#ece6d8", "poleng_b": "#23222a", "wood": "#7a5236", "wood_dark": "#4e3423",
    "bamboo": "#b99a55", "fire": "#ffb040", "bone": "#e8dcc0",
}

TAU = math.tau


def hex_rgba(h, a=1.0):
    h = P.get(h, h).lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), a)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.materials, bpy.data.meshes, bpy.data.objects):
        for d in list(coll):
            coll.remove(d)


def get_mat(name, color, roughness=0.8, glow=None):
    """Flat material. Names starting with M_Glow are emissive (emission colour = base colour)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    col = hex_rgba(color)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.2
    if name.startswith("M_Glow"):
        b.inputs["Emission Color"].default_value = col
        b.inputs["Emission Strength"].default_value = glow or 2.0
    m.diffuse_color = col
    return m


# ------------------------------------------------------------------ math helpers
def V(*a):
    if len(a) == 1:
        return Vector(a[0])
    return Vector(a)


def rot_m(rot):
    """rot = Euler degrees tuple (x, y, z) or a Matrix."""
    if isinstance(rot, Matrix):
        return rot.to_4x4()
    return Euler(tuple(math.radians(r) for r in rot), "XYZ").to_matrix().to_4x4()


def TRS(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    s = Matrix.Diagonal((*scale, 1.0)) if not isinstance(scale, (int, float)) else Matrix.Diagonal(
        (scale, scale, scale, 1.0))
    return Matrix.Translation(Vector(loc)) @ rot_m(rot) @ s


def catmull(points, n):
    """Catmull-Rom through `points` with n samples per segment. Returns (pts, t-params 0..len-1)."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3 or n <= 1:
        return pts, list(range(len(pts)))
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out, ts = [], []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
            ts.append(i - 1 + t)
    out.append(pts[-1])
    ts.append(len(pts) - 1)
    return out, ts


def interp(vals, t):
    """Linear interpolation of a list (scalars or tuples) at float index t."""
    i = min(int(math.floor(t)), len(vals) - 2)
    f = t - i
    a, b = vals[i], vals[i + 1]
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * f for x, y in zip(a, b))
    return a + (b - a) * f


# ------------------------------------------------------------------ the model builder
class Model:
    """Collects geometry per group (pivot) in world space, then builds Blender objects."""

    def __init__(self, mid):
        self.id = mid
        self.mats = {}  # name -> bpy material
        self.groups = {}  # name -> bmesh
        self.gmats = {}  # group -> [mat names]
        self.pivots = {}  # name -> (parent, loc)
        self.order = []
        self.smooth_default = True
        self.root = None

    # -------------------------------------------------- setup
    def mat(self, name, color, glow=None):
        self.mats[name] = get_mat(name, color, glow=glow)
        return name

    def pivot(self, name, loc=(0, 0, 0), parent=None):
        """parent None -> child of the root."""
        self.pivots[name] = (parent, Vector(loc))
        self.order.append(name)
        return name

    def _bm(self, g):
        if g not in self.groups:
            self.groups[g] = bmesh.new()
            self.gmats[g] = []
        return self.groups[g]

    def _mi(self, g, m):
        lst = self.gmats[g]
        if m not in lst:
            lst.append(m)
        return lst.index(m)

    def _finish(self, g, m, verts, faces=None, smooth=None):
        bm = self.groups[g]
        if faces is None:
            vs = set(verts)
            faces = {f for v in verts for f in v.link_faces if all(x in vs for x in f.verts)}
        mi = self._mi(g, m)
        sm = self.smooth_default if smooth is None else smooth
        for f in faces:
            f.material_index = mi
            f.smooth = sm
        return list(verts)

    # -------------------------------------------------- primitives (all world space)
    def box(self, g, m, size, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, smooth=False, taper=None):
        """Box of `size` (x, y, z). taper=(sx, sy) scales the top face."""
        bm = self._bm(g)
        r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((*size, 1.0)))
        verts = r["verts"]
        if taper:
            for v in verts:
                if v.co.z > 0:
                    v.co.x *= taper[0]
                    v.co.y *= taper[1]
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(bm, geom=verts + edges, offset=bevel, segments=2, affect="EDGES",
                                  profile=0.5, clamp_overlap=True)
            verts = list(set(verts) | set(res["verts"]))
            verts = [v for v in verts if v.is_valid]
        bmesh.ops.transform(bm, matrix=TRS(loc, rot), verts=verts)
        return self._finish(g, m, verts, smooth=smooth)

    def cyl(self, g, m, r1, depth, loc=(0, 0, 0), rot=(0, 0, 0), r2=None, segs=12, smooth=None,
            cap=True, scale=(1, 1, 1)):
        """Cylinder / cone along local Z centred on loc."""
        bm = self._bm(g)
        r2 = r1 if r2 is None else r2
        res = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r1,
                                    radius2=r2, depth=depth, matrix=TRS(loc, rot, scale))
        return self._finish(g, m, res["verts"], smooth=smooth)

    def sphere(self, g, m, radius, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), segs=16, rings=10,
               smooth=True):
        bm = self._bm(g)
        res = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius,
                                        matrix=TRS(loc, rot, scale))
        return self._finish(g, m, res["verts"], smooth=smooth)

    def ico(self, g, m, radius, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), sub=1, smooth=False,
            jitter=0.0, seed=0):
        bm = self._bm(g)
        res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=radius, matrix=Matrix())
        verts = res["verts"]
        if jitter:
            rnd = random.Random(seed)
            for v in verts:
                v.co *= 1.0 + rnd.uniform(-jitter, jitter)
        bmesh.ops.transform(bm, matrix=TRS(loc, rot, scale), verts=verts)
        return self._finish(g, m, verts, smooth=smooth)

    def mesh(self, g, m, verts, faces, matrix=None, smooth=None):
        """Raw geometry: verts list of 3-tuples, faces list of index tuples."""
        bm = self._bm(g)
        mx = matrix or Matrix()
        bv = [bm.verts.new(mx @ Vector(v)) for v in verts]
        bf = []
        flip = mx.to_3x3().determinant() < 0
        for f in faces:
            if flip:
                f = tuple(reversed(f))
            try:
                bf.append(bm.faces.new([bv[i] for i in f]))
            except ValueError:
                pass
        return self._finish(g, m, bv, faces=bf, smooth=smooth)

    def loft(self, g, m, points, radii, segs=10, res=1, ref=(0, -1, 0), cap0=True, cap1=True,
             smooth=True, twist=0.0, shape=None):
        """Tube through `points` (Catmull-Rom, `res` samples per segment).

        radii: per control point, a scalar or (side, ref) half-widths: `side` is measured along
        cross(tangent, ref) and `ref` along the reference direction (default -Y = front), so
        (0.2, 0.1) is a tube 0.4 wide and 0.2 deep. `shape(angle)` -> radius multiplier.
        """
        pts, ts = catmull(points, res)
        refv = Vector(ref).normalized()
        rows = []
        n = len(pts)
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            r = interp([(x, x) if not isinstance(x, (tuple, list)) else tuple(x) for x in radii], ts[i])
            n1 = refv - t * refv.dot(t)
            if n1.length < 1e-5:
                n1 = Vector((0, 0, 1)) - t * t.z
            n1.normalize()
            n2 = t.cross(n1).normalized()
            row = []
            for k in range(segs):
                a = TAU * k / segs + twist
                sh = shape(a) if shape else 1.0
                row.append(p + n2 * (math.cos(a) * r[0] * sh) + n1 * (math.sin(a) * r[1] * sh))
            rows.append(row)
        verts, faces = [], []
        for row in rows:
            verts += row
        for i in range(n - 1):
            for k in range(segs):
                a, b = i * segs + k, i * segs + (k + 1) % segs
                faces.append((a, a + segs, b + segs, b))
        if cap0:
            verts.append(pts[0])
            c = len(verts) - 1
            for k in range(segs):
                faces.append((c, k, (k + 1) % segs))
        if cap1:
            verts.append(pts[-1])
            c = len(verts) - 1
            base = (n - 1) * segs
            for k in range(segs):
                faces.append((c, base + (k + 1) % segs, base + k))
        return self.mesh(g, m, verts, faces, smooth=smooth)

    def lathe(self, g, m, profile, loc=(0, 0, 0), rot=(0, 0, 0), segs=16, smooth=True, scale=(1, 1, 1),
              closed=False):
        """Revolve [(r, z), ...] around local Z. r == 0 at an end makes a pole."""
        verts, faces, rows = [], [], []
        for r, z in profile:
            if r <= 1e-6:
                verts.append((0, 0, z))
                rows.append([len(verts) - 1])
            else:
                row = []
                for k in range(segs):
                    a = TAU * k / segs
                    verts.append((r * math.cos(a), r * math.sin(a), z))
                    row.append(len(verts) - 1)
                rows.append(row)
        nr = len(rows) if not closed else len(rows) + 1
        for i in range(nr - 1):
            A, B = rows[i % len(rows)], rows[(i + 1) % len(rows)]
            if len(A) == 1 and len(B) == 1:
                continue
            for k in range(segs):
                if len(A) == 1:
                    faces.append((A[0], B[(k + 1) % segs], B[k]))
                elif len(B) == 1:
                    faces.append((A[k], A[(k + 1) % segs], B[0]))
                else:
                    faces.append((A[k], A[(k + 1) % segs], B[(k + 1) % segs], B[k]))
        if not closed:
            if len(rows[0]) > 1:
                faces.append(tuple(reversed(rows[0])))
            if len(rows[-1]) > 1:
                faces.append(tuple(rows[-1]))
        return self.mesh(g, m, verts, faces, matrix=TRS(loc, rot, scale), smooth=smooth)

    def torus(self, g, m, R, r, loc=(0, 0, 0), rot=(0, 0, 0), segs=16, rsegs=6, scale=(1, 1, 1),
              smooth=True):
        prof = [(R + r * math.cos(TAU * k / rsegs), r * math.sin(TAU * k / rsegs)) for k in range(rsegs)]
        return self.lathe(g, m, prof, loc=loc, rot=rot, segs=segs, smooth=smooth, scale=scale, closed=True)

    def prism(self, g, m, outline, depth, loc=(0, 0, 0), rot=(0, 0, 0), smooth=False, scale=(1, 1, 1),
              taper=None):
        """Extrude a 2D outline [(x, z), ...] (counter-clockwise seen from -Y) along Y by `depth`,
        centred on y = 0, then transform. Good for crown plates, blades, leaves, fins."""
        area = sum(outline[i][0] * outline[(i + 1) % len(outline)][1] - outline[(i + 1) % len(outline)][0] *
                   outline[i][1] for i in range(len(outline)))
        if area < 0:
            outline = list(reversed(outline))
        n = len(outline)
        tf = taper or (lambda x, z: 1.0)
        verts = ([(x, -depth / 2 * tf(x, z), z) for x, z in outline] +
                 [(x, depth / 2 * tf(x, z), z) for x, z in outline])
        faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, n + i, n + j, j))
        # front face must point -Y: outline CCW in (x, z) seen from -Y is CCW in x-z plane
        return self.mesh(g, m, verts, faces, matrix=TRS(loc, rot, scale), smooth=smooth)

    # -------------------------------------------------- composite helpers
    def poleng(self, g, m_w, m_b, z0, z1, radii, rows=3, cols=10, loc=(0, 0, 0), flare=0.0):
        """Checkered black/white wrap (kain poleng) as a tube from z0 down/up to z1.
        radii = (rx, ry) at z0; flare adds to the radius at z1."""
        verts, fw, fb = [], [], []
        grid = []
        for i in range(rows + 1):
            t = i / rows
            z = z0 + (z1 - z0) * t
            rx, ry = radii[0] + flare * t, radii[1] + flare * t
            row = []
            for k in range(cols):
                a = TAU * k / cols
                verts.append((loc[0] + rx * math.cos(a), loc[1] + ry * math.sin(a), z))
                row.append(len(verts) - 1)
            grid.append(row)
        faces = []
        for i in range(rows):
            for k in range(cols):
                f = (grid[i][k], grid[i][(k + 1) % cols], grid[i + 1][(k + 1) % cols], grid[i + 1][k])
                if z1 < z0:
                    f = tuple(reversed(f))
                faces.append((f, (i + k) % 2))
        bm = self._bm(g)
        bv = [bm.verts.new(v) for v in verts]
        wf, bf = [], []
        for f, c in faces:
            face = bm.faces.new([bv[i] for i in f])
            (wf if c == 0 else bf).append(face)
        self._finish(g, m_w, [], faces=wf, smooth=False)
        self._finish(g, m_b, [], faces=bf, smooth=False)
        return bv

    def deform(self, verts, fn):
        for v in verts:
            v.co = Vector(fn(v.co.copy()))

    def scale_groups(self, groups, f, center):
        """Uniformly scale the geometry and pivot positions of `groups` about `center`."""
        c = Vector(center)
        for g in groups:
            if g in self.groups:
                for v in self.groups[g].verts:
                    v.co = c + (v.co - c) * f
            if g in self.pivots:
                par, loc = self.pivots[g]
                self.pivots[g] = (par, c + (loc - c) * f)

    def mirror_x(self, fn):
        """Call fn(s, side) for s=+1 (character's left, +X, 'l') and s=-1 ('r')."""
        fn(1, "l")
        fn(-1, "r")

    # -------------------------------------------------- output
    def tris(self, g=None):
        gs = [g] if g else list(self.groups)
        return sum(len(f.verts) - 2 for k in gs for f in self.groups[k].faces)

    def build(self):
        root = bpy.data.objects.new(self.id, None)
        root.empty_display_size = 0.3
        bpy.context.scene.collection.objects.link(root)
        objs = {}
        world = {}

        def wloc(name):
            if name not in self.pivots:
                return Vector((0, 0, 0))
            return self.pivots[name][1]

        for name in self.order:
            parent, loc = self.pivots[name]
            e = bpy.data.objects.new(name, None)
            e.empty_display_size = 0.15
            bpy.context.scene.collection.objects.link(e)
            e.parent = objs.get(parent, root)
            e.location = loc - (wloc(parent) if parent else Vector())
            objs[name] = e
        for g, bm in self.groups.items():
            if not bm.faces:
                continue
            origin = wloc(g) if g in self.pivots else Vector()
            bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            me = bpy.data.meshes.new(f"{g}_mesh" if g in self.pivots else self.id + "_mesh")
            bm.to_mesh(me)
            for mn in self.gmats[g]:
                me.materials.append(self.mats[mn])
            o = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(o)
            o.parent = objs.get(g, root)
            o.location = (0, 0, 0)
            bm.free()
        self.groups = {}
        bpy.context.view_layer.update()
        self.root = root
        return root


# ------------------------------------------------------------------ scene helpers
def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


def count_tris(root):
    n = 0
    for o in descendants(root):
        if o.type == "MESH":
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n


def export_glb(root, name=None):
    name = name or root.name
    bpy.ops.object.select_all(action="DESELECT")
    for o in descendants(root):
        o.select_set(True)
    path = os.path.join(MODELS_DIR, name + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_materials="EXPORT", export_animations=False,
                              export_extras=False, export_cameras=False, export_lights=False,
                              export_vertex_color="NONE", export_normals=True, export_texcoords=False)
    print(f"[export] {name}.glb tris={count_tris(root)} size={os.path.getsize(path) // 1024}KB")
    return path


def bounds(objs):
    pts = []
    for o in objs:
        if o.type == "MESH":
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


# ------------------------------------------------------------------ toon rendering (Cycles)
def toonify_materials(shade=0.42, rim=True, size=0.62):
    """Replace every material's shader with a Cycles toon setup driven by its base colour
    (approximates the in-game toon+ink shader). Only for renders; call after export."""
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.startswith("_"):
            continue
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        if b is None:
            continue
        col = tuple(b.inputs["Base Color"].default_value)
        glow = m.name.startswith("M_Glow")
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        if glow:
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs[0].default_value = col
            em.inputs[1].default_value = 1.6
            nt.links.new(em.outputs[0], out.inputs[0])
            continue
        toon = nt.nodes.new("ShaderNodeBsdfToon")
        toon.inputs["Color"].default_value = col
        toon.inputs["Size"].default_value = size
        toon.inputs["Smooth"].default_value = 0.04
        amb = nt.nodes.new("ShaderNodeEmission")  # flat ambient floor so shadows keep their hue
        amb.inputs[0].default_value = col
        amb.inputs[1].default_value = shade
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(toon.outputs[0], add.inputs[0])
        nt.links.new(amb.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs[0])


def setup_toon_render(res_x, res_y, transparent=True, samples=16, line=2.2, bg="#1b2330"):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = False
    s.cycles.max_bounces = 2
    s.render.resolution_x, s.render.resolution_y = res_x, res_y
    s.render.resolution_percentage = 100
    s.render.film_transparent = transparent
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    if s.world is None:
        s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bgn = s.world.node_tree.nodes["Background"]
    bgn.inputs[0].default_value = hex_rgba(bg)
    bgn.inputs[1].default_value = 0.0  # lighting from the toon ambient term only
    s.render.use_freestyle = line > 0
    if line > 0:
        s.render.line_thickness_mode = "ABSOLUTE"
        vl = s.view_layers[0]
        fs = vl.freestyle_settings
        fs.crease_angle = math.radians(120)
        ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("ink")
        ls.select_by_visibility = True
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = True
        ls.select_material_boundary = False
        ls.select_contour = True
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.new("ink")
        st = ls.linestyle
        st.color = (0.03, 0.025, 0.03)
        st.thickness = line
        st.thickness_position = "CENTER"
        st.use_chaining = True
        st.caps = "ROUND"


def add_lights(key=(50, -10, -35), key_e=3.0, rim=(-60, 0, 160), rim_e=4.0, rim_col=(0.75, 0.9, 1.0)):
    objs = []
    for name, r, e, c in (("_Key", key, key_e, (1.0, 0.93, 0.82)), ("_Rim", rim, rim_e, rim_col)):
        L = bpy.data.lights.new(name, "SUN")
        L.energy = e
        L.color = c
        L.angle = math.radians(3)
        o = bpy.data.objects.new(name, L)
        o.rotation_euler = tuple(math.radians(a) for a in r)
        bpy.context.scene.collection.objects.link(o)
        objs.append(o)
    return objs


def game_camera(objs, pitch=55.0, yaw=30.0, margin=1.12, ortho=True, aspect=1.0):
    mn, mx = bounds(objs)
    c = (mn + mx) / 2
    size = max((mx - mn).length, 0.5)
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    bpy.context.scene.collection.objects.link(cam)
    p, y = math.radians(pitch), math.radians(yaw)
    d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    cam.location = c + d * size * 2
    cam.rotation_euler = (c - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    cam.data.ortho_scale = size * margin * max(1.0, aspect)
    cam.data.clip_end = size * 10
    bpy.context.scene.camera = cam
    return cam


def render_preview(root, name=None, pitch=55.0, yaw=30.0, res=640, ground=True, extra_views=True):
    """Toon preview from the game camera (+ a small front view inset) -> blender/previews/<name>.png"""
    name = name or root.name
    objs = descendants(root)
    toonify_materials()
    setup_toon_render(res, res, transparent=False, samples=12, line=3.2)
    tmp = add_lights()
    if ground:
        mn, mx = bounds(objs)
        bpy.ops.mesh.primitive_plane_add(size=max(40, (mx - mn).length * 4), location=(0, 0, min(0.0, mn.z) - 0.002))
        gnd = bpy.context.view_layer.objects.active
        gnd.name = "_Ground"
        gm = get_mat("_Ground", "#2a3340")
        gnd.data.materials.append(gm)
        tmp.append(gnd)
    shots = [(pitch, yaw, "")] + ([(8.0, 0.0, "_front"), (8.0, 90.0, "_side")] if extra_views else [])
    files = []
    for pch, yw, suf in shots:
        cam = game_camera(objs, pch, yw, margin=0.95)
        s = bpy.context.scene
        s.render.filepath = os.path.join(PREVIEW_DIR, name + suf + ".png")
        bpy.ops.render.render(write_still=True)
        files.append(s.render.filepath)
        bpy.data.objects.remove(cam, do_unlink=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    if extra_views:
        _composite(files)
    print(f"[preview] {name}.png")


def _composite(files):
    """Main view on the left, front + side views stacked on the right -> the main file."""
    try:
        from PIL import Image
    except ImportError:
        return
    main = Image.open(files[0]).convert("RGB")
    w, h = main.size
    out = Image.new("RGB", (w + w // 2, h), (27, 35, 48))
    out.paste(main, (0, 0))
    for i, f in enumerate(files[1:]):
        im = Image.open(f).convert("RGB").resize((w // 2, h // 2))
        out.paste(im, (w, i * h // 2))
        os.remove(f)
    out.save(files[0])


def run_cli(builders, default_preview=True):
    """builders: dict id -> fn() returning a Model (unbuilt). CLI: ids..., --no-preview, --no-export."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    ids = args or list(builders)
    for mid in ids:
        reset_scene()
        model = builders[mid]()
        root = model.build()
        tri = count_tris(root)
        print(f"[{mid}] tris={tri} groups={[o.name for o in descendants(root)]}")
        if "--no-export" not in flags:
            export_glb(root, mid)
        if default_preview and "--no-preview" not in flags:
            render_preview(root, mid)


# ------------------------------------------------------------------ humanoid scaffolding
def humanoid(m, s):
    """Standard biped: creates pivots body/leg_l/leg_r/head/arm_l/arm_r and the limb + torso
    meshes from spec dict `s` (all world coordinates, character faces -Y, own left = +X).

    Keys: hip (z of body pivot), leg_x, leg_z (hip joint z), knee (z), knee_y, ankle (z),
    thigh, calf, ankle_r (radii), foot (sx, sy, sz), torso [(z, rx, ry, y), ...] (bottom->top),
    neck (x, y, z of head pivot), sh (x, y, z shoulder), elbow (x, y, z), wrist (x, y, z),
    upper, fore, wrist_r, hand (radius), mats: dict(leg, foot, torso, arm, hand).
    Returns useful points: hand_l, hand_r (world centres of the fists).
    """
    mt = s["mats"]
    m.pivot("body", (0, 0, s["hip"]))
    m.pivot("leg_l", (s["leg_x"], 0, s["leg_z"]))
    m.pivot("leg_r", (-s["leg_x"], 0, s["leg_z"]))
    m.pivot("head", s["neck"], parent="body")
    sh = s["sh"]
    m.pivot("arm_l", sh, parent="body")
    m.pivot("arm_r", (-sh[0], sh[1], sh[2]), parent="body")
    out = {}
    for sgn, side in ((1, "l"), (-1, "r")):
        g = "leg_" + side
        x = s["leg_x"] * sgn
        kx = x + s.get("knee_x", 0) * sgn
        m.loft(g, mt["leg"], [(x, 0, s["leg_z"] + s["thigh"] * 0.6), (kx, s.get("knee_y", -0.02), s["knee"]),
                              (kx * 0.98, s.get("ankle_y", 0.02), s["ankle"])],
               [s["thigh"], s["calf"] * 1.05, s["ankle_r"]], segs=s.get("leg_segs", 9), res=3)
        fx, fy, fz = s["foot"]
        m.sphere(g, mt["foot"], 1.0, loc=(kx * 0.98, s.get("ankle_y", 0.02) - fy * 0.3, fz * 0.5),
                 scale=(fx / 2, fy / 2, fz / 2 + 0.005), segs=10, rings=6)
        g = "arm_" + side
        shp = V(sh[0] * sgn, sh[1], sh[2])
        el = V(s["elbow"][0] * sgn, s["elbow"][1], s["elbow"][2])
        wr = V(s["wrist"][0] * sgn, s["wrist"][1], s["wrist"][2])
        m.loft(g, mt["arm"], [shp + V(0, 0, s["upper"] * 0.5), el, wr],
               [s["upper"] * 1.15, s["fore"] * 1.05, s["wrist_r"]], segs=s.get("arm_segs", 9), res=3)
        d = (wr - el).normalized()
        hc = wr + d * s["hand"] * 0.8
        m.sphere(g, mt["hand"], s["hand"], loc=hc, scale=(0.85, 1.0, 1.1), segs=10, rings=7)
        out["hand_" + side] = hc
        out["elbow_" + side] = el
        out["wrist_" + side] = wr
    t = s["torso"]
    m.loft("body", mt["torso"], [(0, r[3], r[0]) for r in t], [(r[1], r[2]) for r in t],
           segs=s.get("torso_segs", 14), res=2)
    return out


def eye_pair(m, g, mt, c, dx, r, scale=(1, 0.6, 1)):
    for sg in (1, -1):
        m.sphere(g, mt, r, loc=(c[0] + dx * sg, c[1], c[2]), scale=scale, segs=8, rings=6)


def gada(m, g, mt_gold, mt_grip, grip, direction, length=1.0, head_r=0.13, mt_accent=None):
    """Javanese gada (mace) held at `grip`, pointing along `direction`."""
    d = V(direction).normalized()
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    M = Matrix.Translation(V(grip)) @ rot
    L = length
    prof = [(0, -0.12), (0.035, -0.12), (0.03, -0.09), (0.022, -0.08), (0.022, 0.12), (0.035, 0.14),
            (0.028, 0.18), (0.028, L * 0.42), (0.06, L * 0.47), (head_r * 0.8, L * 0.55),
            (head_r, L * 0.68), (head_r * 0.95, L * 0.8), (head_r * 0.6, L * 0.9), (0.05, L * 0.94),
            (0.035, L * 0.98), (0, L * 1.02)]
    vs = m.lathe(g, mt_gold, prof, segs=12, smooth=True)
    for v in vs:
        v.co = M @ v.co
    # grip wrap
    vs = m.lathe(g, mt_grip, [(0.026, -0.07), (0.026, 0.1)], segs=10, smooth=True)
    for v in vs:
        v.co = M @ v.co
    # knobs around the head in two staggered rings + top finial
    for ring, (zf, rf) in enumerate(((0.62, 0.97), (0.76, 0.93))):
        for k in range(6):
            a = TAU * (k + 0.5 * ring) / 6
            vs = m.sphere(g, mt_accent or mt_gold, head_r * 0.28,
                          loc=(math.cos(a) * head_r * rf, math.sin(a) * head_r * rf, L * zf), segs=6, rings=4)
            for v in vs:
                v.co = M @ v.co

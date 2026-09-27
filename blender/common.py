"""Shared helpers for the Sawit The Franchise Blender asset scripts.

Run any asset script with plain Python 3.11 (Blender is installed as the `bpy`
module):  python3 blender/<script>.py

Conventions (see STYLE_GUIDE.md):
  * 1 unit = 1 metre, Z up, object origin at the ground centre (z = 0).
  * Characters / buildings face -Y in Blender (becomes +Z in Godot).
  * Materials are flat colours (Principled BSDF, rough, non-metal).
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "game", "assets", "models")
ICONS_DIR = os.path.join(ROOT, "game", "assets", "icons")
PREVIEW_DIR = os.path.join(ROOT, "blender", "previews")
for _d in (MODELS_DIR, ICONS_DIR, PREVIEW_DIR):
    os.makedirs(_d, exist_ok=True)

# Palette sampled from the Higgsfield reference images (see art/reference/README.md)
PALETTE = {
    "grass": "#6d9148", "grass_light": "#a9bd5d", "grass_dark": "#4c733c",
    "foliage": "#5f8a3c", "foliage_dark": "#3e522d", "frond": "#6b8a3a",
    "frond_light": "#8fae4f", "sand": "#efdfb0", "sand_dark": "#dad29b",
    "water": "#73c7aa", "soil": "#8a6a48", "soil_dark": "#6b5038",
    "trunk": "#6b5a3e", "trunk_dark": "#4f4230", "bark": "#7a6446",
    "roof": "#c2714a", "roof_dark": "#9c4c2b", "cream": "#fdf3dc",
    "wood": "#a8703f", "wood_light": "#c99a5e", "wood_dark": "#6e4a2c",
    "skin": "#f0b57d", "skin_dark": "#d9965e", "hair": "#4a3428",
    "fruit": "#c9401f", "fruit_orange": "#e3702c", "fruit_dark": "#3b1d16",
    "rock": "#a4a39a", "rock_dark": "#86857c", "metal": "#b8c4c2",
    "metal_dark": "#7f8c8b", "white": "#f6f1e7", "black": "#2b2522",
    "red": "#d5543d", "yellow": "#f2c14e", "blue": "#4f86b8", "green_sign": "#3f8a4e",
    "polybag": "#2e2a28", "straw": "#e0c080", "khaki": "#9a8f5a",
}


def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    # sRGB -> linear (Blender colour sockets are linear)
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), a)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def mat(name, color, roughness=0.9, emission=None):
    """Get or create a flat material. `color` is a hex string or PALETTE key."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    col = PALETTE.get(color, color)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = hex_rgba(col)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    if emission:
        bsdf.inputs["Emission Color"].default_value = hex_rgba(PALETTE.get(emission, emission))
        bsdf.inputs["Emission Strength"].default_value = 1.0
    m.diffuse_color = hex_rgba(col)
    return m


def set_mat(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.2
    e.location = loc
    link(e, parent)
    return e


def _active():
    return bpy.context.view_layer.objects.active


def add_box(name, size, loc=(0, 0, 0), material=None, bevel=0.0, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = _active()
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        bevel_obj(o, bevel)
    if material:
        set_mat(o, material)
    if parent is not None:
        reparent(o, parent)
    return o


def add_cyl(name, radius, depth, loc=(0, 0, 0), material=None, verts=12, parent=None, rot=(0, 0, 0),
            radius2=None, smooth=False, bevel=0.0):
    if radius2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=radius, radius2=radius2, depth=depth,
                                        location=loc, rotation=rot)
    o = _active()
    o.name = name
    if bevel > 0:
        bevel_obj(o, bevel)
    if smooth:
        shade_smooth(o)
    if material:
        set_mat(o, material)
    if parent is not None:
        reparent(o, parent)
    return o


def add_sphere(name, radius, loc=(0, 0, 0), material=None, scale=(1, 1, 1), segments=16, rings=10,
               parent=None, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=loc)
    o = _active()
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if smooth:
        shade_smooth(o)
    if material:
        set_mat(o, material)
    if parent is not None:
        reparent(o, parent)
    return o


def add_ico(name, radius, loc=(0, 0, 0), material=None, subdiv=2, scale=(1, 1, 1), parent=None, smooth=True):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius, location=loc)
    o = _active()
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if smooth:
        shade_smooth(o)
    if material:
        set_mat(o, material)
    if parent is not None:
        reparent(o, parent)
    return o


def bevel_obj(o, width, segments=2):
    mod = o.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    return o


def subsurf(o, levels=1):
    mod = o.modifiers.new("Subsurf", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    return o


def shade_smooth(o):
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def jitter_verts(o, amount=0.03, seed=0):
    rnd = random.Random(seed)
    for v in o.data.vertices:
        v.co += Vector((rnd.uniform(-amount, amount), rnd.uniform(-amount, amount), rnd.uniform(-amount, amount)))
    return o


def reparent(child, parent):
    """Parent keeping the world transform."""
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = mw
    return child


def apply_modifiers(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def join(objs, name):
    """Join mesh objects into one (materials are kept as separate surfaces)."""
    objs = [o for o in objs if o.type == "MESH"]
    for o in objs:
        apply_modifiers(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = _active()
    o.name = name
    return o


def mesh_from_data(name, verts, faces, material=None, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    o = bpy.data.objects.new(name, me)
    link(o)
    if smooth:
        shade_smooth(o)
    if material:
        set_mat(o, material)
    if parent is not None:
        reparent(o, parent)
    return o


def all_descendants(root):
    out = [root]
    for c in root.children:
        out.extend(all_descendants(c))
    return out


def count_tris(root):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in all_descendants(root):
        if o.type == "MESH":
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            ev.to_mesh_clear()
    return n


def bake_vertex_ao(objs, samples=48, distance=1.0, floor=0.45, gamma=0.8, ground=True):
    """Bake Cycles ambient occlusion into an active colour attribute `Col` on each mesh.

    The AO is remapped to [floor, 1] (never pitch black) and softened with `gamma`.
    `ground=True` adds a temporary ground plane so bases darken where they meet the floor.
    Modifiers are applied first so the colours match the exported geometry.
    """
    objs = [o for o in objs if o.type == "MESH"]
    if not objs:
        return
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.light_settings.distance = distance
    tmp = None
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
        tmp = _active()
        tmp.name = "_AOGround"
    for o in objs:
        apply_modifiers(o)
        me = o.data
        if "Col" in me.color_attributes:
            me.color_attributes.remove(me.color_attributes["Col"])
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    scene.render.bake.target = "VERTEX_COLORS"
    bpy.ops.object.bake(type="AO")
    for o in objs:
        attr = o.data.color_attributes["Col"]
        for d in attr.data:
            v = d.color[0] ** gamma
            v = floor + (1.0 - floor) * v
            d.color = (v, v, v, 1.0)
    if tmp is not None:
        bpy.data.objects.remove(tmp, do_unlink=True)


def _has_colors(root):
    return any(o.type == "MESH" and len(o.data.color_attributes) > 0 for o in all_descendants(root))


def export_glb(root, name, animations=False):
    """Export `root` and all of its children to game/assets/models/<name>.glb.

    Vertex colours (baked AO, attribute `Col`) are exported when present; pass
    animations=True for rigged characters (all actions are exported).
    """
    bpy.ops.object.select_all(action="DESELECT")
    for o in all_descendants(root):
        o.select_set(True)
    path = os.path.join(MODELS_DIR, name + ".glb")
    kwargs = dict(
        filepath=path, export_format="GLB", use_selection=True, export_apply=True,
        export_yup=True, export_materials="EXPORT", export_animations=animations,
        export_extras=False, export_cameras=False, export_lights=False,
        export_vertex_color="ACTIVE" if _has_colors(root) else "NONE",
    )
    if animations:
        kwargs.update(export_animation_mode="ACTIONS", export_skins=True, export_force_sampling=True,
                      export_optimize_animation_size=True)
    bpy.ops.export_scene.gltf(**kwargs)
    print(f"[export] {name}.glb  tris={count_tris(root)}")
    return path


# ---------------------------------------------------------------- rendering
def _setup_render(res_x, res_y, transparent=True, samples=24):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.render.resolution_x = res_x
    s.render.resolution_y = res_y
    s.render.resolution_percentage = 100
    s.render.film_transparent = transparent
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    if s.world is None:
        s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bg = s.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = hex_rgba("#dfe8ea")
    bg.inputs[1].default_value = 0.9


def _temp_lights():
    objs = []
    sun = bpy.data.objects.new("_Sun", bpy.data.lights.new("_Sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(12)
    sun.data.color = (1.0, 0.95, 0.85)
    sun.rotation_euler = (math.radians(40), math.radians(-18), math.radians(-30))
    link(sun)
    objs.append(sun)
    return objs


def _bounds(root):
    pts = []
    for o in all_descendants(root):
        if o.type == "MESH":
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def _temp_camera(root, pitch_deg=55.0, yaw_deg=0.0, margin=1.15, ortho=True):
    mn, mx = _bounds(root)
    center = (mn + mx) / 2
    size = (mx - mn).length
    cam = bpy.data.objects.new("_Cam", bpy.data.cameras.new("_Cam"))
    link(cam)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    d = size * 2.0
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = center + dirv * d
    look = (center - cam.location).normalized()
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = size * margin
    cam.data.clip_end = d * 4
    bpy.context.scene.camera = cam
    return cam


def render_preview(root, name, pitch_deg=50.0, yaw_deg=20.0, res=512, ground=True):
    """Render a quick Cycles preview to blender/previews/<name>.png (view it to check the model)."""
    _setup_render(res, res, transparent=False, samples=20)
    tmp = _temp_lights()
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.001))
        g = _active()
        g.name = "_Ground"
        set_mat(g, mat("_M_PreviewGround", "#8fb35c"))
        tmp.append(g)
    tmp.append(_temp_camera(root, pitch_deg, yaw_deg))
    bpy.context.scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    print(f"[preview] {name}.png")


def render_icon(root, name, pitch_deg=35.0, yaw_deg=25.0, res=128, margin=1.05):
    """Render a transparent square icon to game/assets/icons/<name>.png."""
    _setup_render(res, res, transparent=True, samples=24)
    tmp = _temp_lights()
    tmp.append(_temp_camera(root, pitch_deg, yaw_deg, margin=margin))
    bpy.context.scene.render.filepath = os.path.join(ICONS_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    print(f"[icon] {name}.png")


def delete_hierarchy(root):
    for o in reversed(all_descendants(root)):
        bpy.data.objects.remove(o, do_unlink=True)

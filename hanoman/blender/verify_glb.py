#!/usr/bin/env python3
"""Re-import exported GLBs and print their node hierarchy, pivot positions, triangle counts,
materials and a winding sanity check (signed volume of each mesh; negative = inside-out).

Run:  python3 hanoman/blender/verify_glb.py [ids...]      (default: every .glb in models/)
Positions are printed in Blender space (Z up, front -Y) after the importer's Y-up conversion.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

from common import MODELS_DIR, reset_scene  # noqa: E402


def signed_volume(o):
    me = o.data
    me.calc_loop_triangles()
    v = 0.0
    for t in me.loop_triangles:
        a, b, c = (me.vertices[i].co for i in t.vertices)
        v += a.dot(b.cross(c)) / 6.0
    return v


def show(o, depth=0):
    w = o.matrix_world.translation
    extra = ""
    if o.type == "MESH":
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        mats = ",".join(m.name for m in o.data.materials if m)
        vol = signed_volume(o)
        extra = f"  mesh tris={tris} vol={vol:+.3f} mats=[{mats}]" + ("  !! INSIDE-OUT?" if vol < -1e-4 else "")
    print(f"{'  ' * depth}{o.name:<16} ({w.x:+.2f}, {w.y:+.2f}, {w.z:+.2f}){extra}")
    for c in sorted(o.children, key=lambda c: (c.type == 'MESH', c.name)):
        show(c, depth + 1)


def main():
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = [i + ".glb" for i in ids] if ids else sorted(f for f in os.listdir(MODELS_DIR) if f.endswith(".glb"))
    total = 0
    for f in files:
        reset_scene()
        path = os.path.join(MODELS_DIR, f)
        total += os.path.getsize(path)
        bpy.ops.import_scene.gltf(filepath=path)
        roots = [o for o in bpy.context.scene.objects if o.parent is None]
        print(f"=== {f} ({os.path.getsize(path) // 1024} KB)")
        for r in roots:
            show(r)
    print(f"total {total / 1024 / 1024:.2f} MB in {len(files)} files")


if __name__ == "__main__":
    main()

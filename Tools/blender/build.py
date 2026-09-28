"""Build every Ojol Rush building variant with Blender and write the GLBs + manifest.

    python3 Tools/blender/build.py                      # all types -> Web/models/bld/
    python3 Tools/blender/build.py --types ruko rumah    # only some types
    python3 Tools/blender/build.py --out /tmp/bld       # other output folder

Each module in Tools/blender/types/ defines:
    TYPE  = 'ruko'                         # short id, used in file names
    ROLES = ['front']                      # where the game may place it: 'front' (street-facing row,
                                           # seen from the front), 'back' (seen from behind / as roofs),
                                           # 'tall' (outer ring only), 'fill' (back-lot filler)
    def variants(): -> list of dicts       # one dict per model; must include 'w' and 'd' (footprint, m)
    def build(b, v, rng): ...              # b: common.Bld (already sized w x d), v: the dict, rng: seeded
Optionally ROLES can be overridden per variant with v['roles'].
"""
import argparse
import glob
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


def load_types(only):
    mods = []
    for path in sorted(glob.glob(os.path.join(HERE, 'types', '*.py'))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith('_') or (only and name not in only):
            continue
        spec = importlib.util.spec_from_file_location('bt_' + name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods.append(mod)
    return mods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--types', nargs='*')
    ap.add_argument('--out', default=os.path.join(HERE, '..', '..', 'Web', 'models', 'bld'))
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    common.reset_scene()
    manifest_path = os.path.join(out, 'manifest.json')
    entries = {}
    if a.types and os.path.exists(manifest_path):   # partial rebuild keeps the other types
        for e in json.load(open(manifest_path)):
            entries[e['file']] = e
        for f in list(entries):
            if entries[f]['type'] in a.types:
                del entries[f]
    for mod in load_types(a.types):
        for i, v in enumerate(mod.variants()):
            name = '%s_%02d' % (mod.TYPE, i)
            b = common.Bld(name, v['w'], v['d'])
            mod.build(b, v, common.seeded(mod.TYPE, i))
            stats = b.export(os.path.join(out, name + '.glb'))
            e = {'file': name + '.glb', 'type': mod.TYPE, 'roles': v.get('roles', mod.ROLES)}
            e.update(stats)
            entries[e['file']] = e
            warn = '  !! OVERFLOW %.2fm outside the lot' % stats['overflow'] if stats['overflow'] > 0.05 else ''
            print('%-14s %5d tris  %5.1f x %5.1f x %5.1f m  %s%s' % (name, stats['tris'], stats['w'], stats['d'], stats['h'], ','.join(e['roles']), warn))
    with open(manifest_path, 'w') as f:
        json.dump([entries[k] for k in sorted(entries)], f, indent=1)
    sys.stdout.flush()


if __name__ == '__main__':
    main()
    os._exit(0)   # the bpy module can segfault in its atexit handlers; everything is written by now

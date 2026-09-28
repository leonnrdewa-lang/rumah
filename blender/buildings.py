"""Buildings / vehicles for Sawit The Franchise.

Run:  python3 blender/buildings.py              (build everything + previews + icons)
      python3 blender/buildings.py rumah_a truck (build only those)
Flags: --no-render  skip previews/icons (fast tri check)
       --debug      also write extra game-camera views to $SAWIT_DEBUG_DIR (default /tmp)

Every asset: root Empty named after the asset, merged static mesh(es) parented to
it, front (doors) facing -Y, origin at the ground centre of the footprint.
Special child nodes: kantor/SignBoard, toko/SignBoard, gudang/SignBoard, truck/Cargo.
Night-lit material: M_Glass.
Every mesh gets baked vertex AO + weathering (props.weather_bake) in the active colour
attribute `Col` before export: plank grooves, per-plank / per-tile variation, rust and moss
streaks on corrugated zinc, a dirt band at the base.
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
                    set_mat, shade_smooth, count_tris, all_descendants)
import props as PR  # noqa: E402  (shared helpers + prop part makers)
from props import (Z, glass_mat, bx, rod, fix_normals, weld, smooth_angle, mk_multi, beam, fpt,  # noqa: E402
                   facing_rot, center_root, finish, dims, board_with_uv, debug_view, DEBUG,
                   wattr, weather_bake, preview_vcol, _seed)

# ------------------------------------------------------------ wall pieces
def siding_ring(name, poly, z0, z1, n, groove, m):
    """Horizontal V-groove plank siding around an axis-aligned CCW polygon."""
    N = len(poly)
    offs = []
    for i in range(N):
        a, b, c = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % N])
        e1, e2 = (b - a).normalized(), (c - b).normalized()
        n1, n2 = Vector((e1.y, -e1.x)), Vector((e2.y, -e2.x))
        offs.append((n1 + n2) / (1 + n1.dot(n2)))
    prof = []
    h = (z1 - z0) / n
    for k in range(n):
        zb = z0 + k * h
        zt = zb + h
        prof += [(zb, 0.0), (zb + groove * 0.8, groove), (zt - groove * 1.6, groove)]
    prof.append((z1, 0.0))
    verts, faces = [], []
    for z, o in prof:
        for i in range(N):
            p = Vector(poly[i]) + offs[i] * o
            verts.append((p.x, p.y, z))
    rnd = random.Random(_seed(name, z0, z1, n, *[c for p_ in poly for c in p_]))
    pshade = [[rnd.uniform(-0.24, 0.1) for _ in range(N)] for _ in range(n)]
    shade = []
    for r in range(len(prof) - 1):
        plank = prof[r][1] > 1e-6 and prof[r + 1][1] > 1e-6
        for i in range(N):
            j = (i + 1) % N
            faces.append((r * N + i, r * N + j, (r + 1) * N + j, (r + 1) * N + i))
            shade.append(pshade[min(n - 1, r // 3)][i] if plank else -0.45)
    o = mesh_from_data(name, verts, faces, m)
    wattr(o, "w_shade", shade)
    wattr(o, "w_shadev", [rnd.uniform(-0.1, 0.06) for _ in verts], "POINT")   # streaks along each plank
    return o


def vplank_panel(name, origin, rotz, x0, x1, zb_fn, zt_fn, pw, g, m, breaks=()):
    """Vertical V-groove plank panel in a wall frame (local x right, -y out)."""
    n = max(1, round((x1 - x0) / pw))
    pw = (x1 - x0) / n
    cols = []
    for k in range(n):
        xa = x0 + k * pw
        xb = xa + pw
        cols += [(xa, 0.0), (xa + g * 0.8, g), (xb - g * 0.8, g)]
    cols.append((x1, 0.0))
    for bxv in breaks:
        if all(abs(bxv - c[0]) > 1e-4 for c in cols) and x0 < bxv < x1:
            for i in range(len(cols) - 1):
                if cols[i][0] < bxv < cols[i + 1][0]:
                    t = (bxv - cols[i][0]) / (cols[i + 1][0] - cols[i][0])
                    cols.insert(i + 1, (bxv, cols[i][1] + t * (cols[i + 1][1] - cols[i][1])))
                    break
    verts, faces = [], []
    for x, off in cols:
        verts.append(fpt(origin, rotz, (x, -off, zb_fn(x))))
        verts.append(fpt(origin, rotz, (x, -off, zt_fn(x))))
    rnd = random.Random(_seed(name, origin[0], origin[1], rotz, x0, x1, pw))
    pshade = [rnd.uniform(-0.24, 0.1) for _ in range(n)]
    shade = []
    for i in range(len(cols) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        (xa, oa), (xb_, ob) = cols[i], cols[i + 1]
        if oa > 1e-6 and ob > 1e-6:
            shade.append(pshade[min(n - 1, max(0, int(((xa + xb_) / 2 - x0) / pw)))])
        else:
            shade.append(-0.45)
    o = mesh_from_data(name, verts, faces, m)
    wattr(o, "w_shade", shade)
    # weathered plank ends: bottoms a little darker and streaky, tops random
    wattr(o, "w_shadev", [(rnd.uniform(-0.14, 0.0) if k % 2 == 0 else rnd.uniform(-0.05, 0.06)) for k in range(len(verts))],
          "POINT")
    return o


def rect_ring(name, origin, rotz, zc, w_in, h_in, border, depth, m, y0=0.0, bevel=0.015):
    """Rectangular frame (window/door surround) proud of a wall."""
    wo, ho = w_in / 2 + border, h_in / 2 + border
    wi, hi = w_in / 2, h_in / 2
    loops = []
    for (hw, hh, y) in ((wo, ho, y0), (wo, ho, y0 - depth), (wi, hi, y0 - depth), (wi, hi, y0)):
        loops.append([fpt(origin, rotz, (sx * hw, y, zc + sz * hh))
                      for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    verts = [v for lp in loops for v in lp]
    faces = []
    for L in range(3):
        for i in range(4):
            j = (i + 1) % 4
            faces.append((L * 4 + i, L * 4 + j, (L + 1) * 4 + j, (L + 1) * 4 + i))
    o = mesh_from_data(name, verts, faces, m)
    fix_normals(o)
    if bevel:
        bevel_obj(o, bevel, 1)
    return o


def window(P, M, origin, rotz, zc, w=0.66, h=0.74, shutters=False, cross=True, frame='trim', shut='trim'):
    fr = lambda x, y, z: fpt(origin, rotz, (x, y, z))
    P.append(rect_ring("win_frame", origin, rotz, zc, w, h, 0.09, 0.08, M[frame], y0=0.0, bevel=0))
    P.append(bx("win_glass", (w + 0.02, 0.04, h + 0.02), fr(0, -0.01, zc), M['glass'], 0, rotz=rotz))
    if cross:
        P.append(bx("mun_v", (0.05, 0.03, h), fr(0, -0.04, zc), M[frame], 0, rotz=rotz))
        P.append(bx("mun_h", (w, 0.03, 0.05), fr(0, -0.04, zc), M[frame], 0, rotz=rotz))
    P.append(bx("sill", (w + 0.34, 0.16, 0.07), fr(0, -0.07, zc - h / 2 - 0.1), M[frame], 0, rotz=rotz))
    if shutters:
        sw = w / 2 - 0.04
        for sg in (-1, 1):
            P.append(bx("shutter", (sw, 0.05, h + 0.06), fr(sg * (w / 2 + 0.11 + sw / 2), -0.05, zc),
                        M[shut], 0.02, 1, rotz))


def door(P, M, origin, rotz, z0, w=0.9, h=1.5, frame='trim', panel='trim', glass_top=False):
    fr = lambda x, y, z: fpt(origin, rotz, (x, y, z))
    P.append(rect_ring("door_frame", origin, rotz, z0 + h / 2 + 0.02, w, h + 0.04, 0.1, 0.09, M[frame]))
    P.append(bx("door", (w + 0.02, 0.06, h + 0.04), fr(0, -0.01, z0 + h / 2), M[panel], 0.02, 1, rotz))
    P.append(bx("knob", (0.07, 0.08, 0.07), fr(w / 2 - 0.14, -0.07, z0 + 0.78), M[frame], 0.02, 1, rotz))
    if glass_top:
        P.append(bx("door_glass", (w * 0.55, 0.03, 0.34), fr(0, -0.045, z0 + h - 0.32), M['glass'], 0, rotz=rotz))


def steps(P, M, xc, y_edge, width, top_z, n, depth=0.26, m='trim', along=-1):
    """Chunky block steps descending from y_edge towards `along`*Y (default -Y)."""
    h = top_z / (n + 1)
    for k in range(1, n + 1):
        d = (n + 1 - k) * depth
        yc = y_edge + along * d / 2
        P.append(bx("step", (width, d, k * h), (xc, yc, k * h / 2), M[m], 0.035, 1))


def railing(P, M, p1, p2, z0, height=0.55, spacing=0.2, m='trim', posts=True, bal_m=None):
    """Porch railing between two floor points: top/bottom rail + balusters."""
    p1, p2 = Vector((p1[0], p1[1], z0)), Vector((p2[0], p2[1], z0))
    d = p2 - p1
    L = d.length
    dn = d.normalized()
    P.append(beam("rail_top", p1 + Z * height, p2 + Z * height, 0.09, 0.07, (0, 0, 1), M[m], 0.02))
    P.append(beam("rail_bot", p1 + Z * 0.12, p2 + Z * 0.12, 0.06, 0.05, (0, 0, 1), M[m], 0.0))
    nb = max(1, int(L / spacing))
    rz = math.atan2(dn.y, dn.x)
    for i in range(1, nb):
        p = p1 + dn * (L * i / nb)
        P.append(bx("baluster", (0.045, 0.045, height - 0.12), (p.x, p.y, z0 + 0.12 + (height - 0.12) / 2),
                    M[bal_m or m], 0, rotz=rz))
    if posts:
        for p in (p1, p2):
            P.append(bx("rail_post", (0.1, 0.1, height + 0.08), (p.x, p.y, z0 + (height + 0.08) / 2), M[m], 0.025, 1))


# ------------------------------------------------------------ roofs
def tri_wave(x, period, amp):
    t = (x / period) % 1.0
    return amp * (1.0 - abs(2.0 * t - 1.0))


def new_wear(style, rust=1.0, moss=1.0, seed=0):
    """Per-face / per-vertex weathering lists filled by tile_slope (see props.weather_bake)."""
    return dict(style=style, rust_k=rust, moss_k=moss, seed=seed, shade=[], rust=[], moss=[], down=[], mossv=[])


def _streaks(rnd, x0, x1, per_m, wmin, wmax, smin, smax):
    n = max(1, int((x1 - x0) * per_m))
    return [(rnd.uniform(x0, x1), rnd.uniform(wmin, wmax), rnd.uniform(smin, smax)) for _ in range(n)]


def _streak_val(st, x):
    return max([s_ * max(0.0, 1.0 - abs(x - c) / w) for c, w, s_ in st] + [0.0])


def tile_slope(verts, faces, origin, ex, ev, en, v_len, ext_fn, rows, period=0.42, amp=0.06,
               step=0.08, cham=0.14, thick=0.08, underside=True, kinds=None, wear=None):
    """Append one clay-tile roof slope (rows of wavy tiles with a chunky lip) to verts/faces.

    Slope frame: origin on the ridge line, ex along the ridge, ev down the slope,
    en = outward normal. ext_fn(v) -> (xmin, xmax) of the slope at distance v.
    wear: optional dict from new_wear(): 'zinc' = rust / moss streaks running down the slope,
    'clay' = per-tile colour variation and a little moss near the eave.
    """
    O, ex, ev, en = Vector(origin), Vector(ex), Vector(ev), Vector(en)
    if wear is not None:
        wear['seed'] += 1
        wrnd = random.Random(_seed(wear['seed'], *origin, *ex, *ev))
        lo_, hi_ = ext_fn(v_len)
        lo_, hi_ = min(lo_, ext_fn(0)[0]), max(hi_, ext_fn(0)[1])
        rust_st = _streaks(wrnd, lo_, hi_, 2.2, 0.05, 0.3, 0.35, 1.0)
        moss_st = _streaks(wrnd, lo_, hi_, 0.7, 0.15, 0.5, 0.4, 0.9)
        # clay: soft moss / lichen blobs (per vertex, so they fade out instead of stopping at tile edges),
        # mostly on the lower half of the slope, plus a faint damp band along the eave
        blobs = []
        if wear['style'] != 'zinc':
            for _ in range(max(1, int(round((hi_ - lo_) * 0.7)))):
                blobs.append((wrnd.uniform(lo_, hi_), wrnd.uniform(0.3, 1.05) * v_len, wrnd.uniform(0.5, 1.1),
                              wrnd.uniform(0.7, 1.0)))

    def moss_v(x, v):
        if wear is None or wear['style'] == 'zinc':
            return 0.0
        m = 0.25 * (v / v_len) ** 3
        for bx_, bv, r, st in blobs:
            d2 = ((x - bx_) ** 2 + ((v - bv) * 1.4) ** 2) / (r * r)
            if d2 < 1.0:
                m = max(m, st * (1.0 - d2) ** 2)
        return wear['moss_k'] * m

    def wear_face(kind, i, xc):
        if wear is None:
            return
        if kind == 2:
            wear['shade'].append(0.0); wear['rust'].append(0.0); wear['moss'].append(0.0)
            return
        if wear['style'] == 'zinc':
            wear['shade'].append(0.04 * math.sin(xc * 7.1 + i) - (0.08 if kind == 1 else 0.0))
            wear['rust'].append(wear['rust_k'] * (0.18 + 0.95 * _streak_val(rust_st, xc)))
            wear['moss'].append(wear['moss_k'] * 0.8 * _streak_val(moss_st, xc))
        else:
            tr = random.Random(_seed(wear['seed'], i, round(xc / period)))
            wear['shade'].append(tr.uniform(-0.22, 0.12) - (0.1 if kind == 1 else 0.0))
            wear['rust'].append(0.0)
            wear['moss'].append(0.0)
    flip = ex.cross(ev).dot(en) < 0
    P3 = lambda x, v, n: O + ex * x + ev * v + en * n
    rl = v_len / rows
    half = period / 2
    for i in range(rows):
        v0, v2 = i * rl, (i + 1) * rl
        v1 = v2 - rl * cham
        (a0, b0), (a1, b1), (a2, b2) = ext_fn(v0), ext_fn(v1), ext_fn(v2)
        lo, hi = max(a0, a1, a2), min(b0, b1, b2)
        k0, k1 = math.floor(lo / half) + 1, math.ceil(hi / half) - 1
        inner = [k * half for k in range(k0, k1 + 1) if lo + 0.02 < k * half < hi - 0.02]
        cols = [(a0, a1, a2)] + [(x, x, x) for x in inner] + [(b0, b1, b2)]
        base = len(verts)
        for xt, xm, xb in cols:
            verts.append(P3(xt, v0, tri_wave(xt, period, amp)))
            verts.append(P3(xm, v1, step + tri_wave(xm, period, amp)))
            verts.append(P3(xb, v2, tri_wave(xb, period, amp)))
            if wear is not None:
                wear['down'] += [v0 / v_len, v1 / v_len, v2 / v_len]
                wear['mossv'] += [moss_v(xt, v0), moss_v(xm, v1), moss_v(xb, v2)]
        for c in range(len(cols) - 1):
            t0, m0, b0_ = base + 3 * c, base + 3 * c + 1, base + 3 * c + 2
            t1, m1, b1_ = t0 + 3, m0 + 3, b0_ + 3
            xc = (cols[c][0] + cols[c + 1][0]) / 2
            for kind, f in ((0, (t0, t1, m1, m0)), (1, (m0, m1, b1_, b0_))):
                faces.append(tuple(reversed(f)) if flip else f)
                if kinds is not None:
                    kinds.append(kind)
                wear_face(kind, i, xc)
    if underside:
        a0, b0 = ext_fn(0.0)
        a2, b2 = ext_fn(v_len)
        base = len(verts)
        pts = [P3(a0, 0, -thick), P3(b0, 0, -thick), P3(b2, v_len, -thick), P3(a2, v_len, -thick)]
        verts.extend(pts)
        f = (base, base + 1, base + 2, base + 3)
        faces.append(f if flip else tuple(reversed(f)))
        if kinds is not None:
            kinds.append(2)
        if wear is not None:
            wear['down'] += [0.0, 0.0, 1.0, 1.0]
            wear['mossv'] += [0.0] * 4
            wear_face(2, 0, 0.0)


def roof_mesh(name, verts, faces, kinds, m_tile, m_lip=None, smooth_deg=None, wear=None):
    """Tile roof object: lips (row shadow lines) optionally in a darker material."""
    mats = [m_tile] if m_lip is None else [m_tile, m_lip]
    fm = [(1 if (k == 1 and m_lip is not None) else 0) for k in kinds]
    o = mk_multi(name, verts, faces, mats, fm)
    if smooth_deg:
        smooth_angle(o, smooth_deg)
    if wear is not None:
        wattr(o, "w_shade", wear['shade'])
        wattr(o, "w_rust", wear['rust'])
        wattr(o, "w_moss", wear['moss'])
        wattr(o, "w_down", wear['down'], "POINT")
        if any(wear['mossv']):
            wattr(o, "w_mossv", wear['mossv'], "POINT")
    return o


def slope_frame(ridge_pt, down_dir, along, pitch):
    """(origin, ex, ev, en) for a slope going down along horizontal `down_dir`."""
    d = Vector(down_dir).normalized()
    c, s = math.cos(pitch), math.sin(pitch)
    ev = d * c - Z * s
    en = d * s + Z * c
    return Vector(ridge_pt), Vector(along).normalized(), ev, en


def gable_roof(P, M, a, b, half_w, pitch, rows, tile='roof', lip='trim', trim='trim', ridge_r=0.14,
               balls=True, horns=(), fascia=True, barge=True, barge_h=0.26, horn_len=0.55, tile_kw=None,
               ridge_verts=8, ridge_mat=None, wear=None):
    """Clay-tile gable roof; ridge from a to b (points on the ridge plane), slopes half_w wide in plan.
    horns: subset of ('a', 'b') ends whose barge boards cross above the ridge.
    wear: new_wear(...) dict, default clay variation (or zinc streaks when tile_kw is given)."""
    a, b = Vector(a), Vector(b)
    ex = b - a
    L = ex.length
    ex.normalize()
    side = ex.cross(Z)
    v, f, k = [], [], []
    frames = []
    vl = half_w / math.cos(pitch)
    if wear is None:
        wear = new_wear('zinc' if tile_kw else 'clay', seed=_seed(*a, *b))
    for d in (side, -side):
        O, ex_, ev, en = slope_frame(a, d, ex, pitch)
        tile_slope(v, f, O, ex_, ev, en, vl, lambda s: (0.0, L), rows, kinds=k, wear=wear, **(tile_kw or {}))
        frames.append((O, ev, en))
    P.append(roof_mesh("roof_tiles", v, f, k, M[tile], M[lip] if lip else None, wear=wear))
    rg = rod("ridge", a - ex * 0.1 + Z * 0.08, b + ex * 0.1 + Z * 0.08, ridge_r, M[ridge_mat or tile], ridge_verts,
             smooth=ridge_verts > 4)
    if ridge_verts == 4:   # folded zinc ridge cap: diamond section
        rg.rotation_euler.rotate_axis('Z', math.radians(45))
    P.append(rg)
    if balls:
        for p_, sg in ((a, -1), (b, 1)):
            if ('a' if sg < 0 else 'b') not in horns:
                P.append(add_sphere("ridge_end", ridge_r * 1.4, loc=p_ + ex * sg * 0.12 + Z * 0.1,
                                    material=M[tile], segments=8, rings=6))
    for O, ev, en in frames:
        if barge:
            for x, end in ((-0.04, 'a'), (L + 0.04, 'b')):
                v0 = -0.14 - (horn_len if end in horns else 0.0)
                pa = O + ex * x + ev * v0 + en * 0.03
                pb = O + ex * x + ev * (vl + 0.03) + en * 0.03
                P.append(beam("barge", pa, pb, 0.11, barge_h, en, M[trim], 0.035))
        if fascia:
            e = O + ev * vl
            P.append(beam("fascia", e - ex * 0.09, e + ex * (L + 0.09), 0.1, 0.2, en, M[trim], 0.035))
    return frames, vl


def hip_roof(P, M, cx, cy, HX, HY, z_eave, pitch, rows, tile='roof', lip='trim', trim='trim', ridge_r=0.13):
    """Clay-tile hip (limas) roof over the eave rectangle (cx +- HX, cy +- HY), equal pitch."""
    t = math.tan(pitch)
    c = math.cos(pitch)
    zr = z_eave + HY * t
    rx = max(0.0, HX - HY)
    vl = HY / c
    v, f, k = [], [], []
    specs = [((cx, cy, zr), (0, -1, 0), (1, 0, 0), rx), ((cx, cy, zr), (0, 1, 0), (1, 0, 0), rx),
             ((cx - rx, cy, zr), (-1, 0, 0), (0, 1, 0), 0.0), ((cx + rx, cy, zr), (1, 0, 0), (0, 1, 0), 0.0)]
    frames = []
    wear = new_wear('clay', seed=_seed(cx, cy, HX, HY))
    for O_, d, along, r in specs:
        O, ex, ev, en = slope_frame(O_, d, along, pitch)
        tile_slope(v, f, O, ex, ev, en, vl, lambda s, r=r: (-(r + s * c), r + s * c), rows, kinds=k, wear=wear)
        frames.append((O, ex, ev, en, r))
    P.append(roof_mesh("roof_tiles", v, f, k, M[tile], M[lip] if lip else None, wear=wear))
    lift = Z * 0.09
    if rx > 0:
        P.append(rod("ridge", (cx - rx - 0.05, cy, zr + 0.09), (cx + rx + 0.05, cy, zr + 0.09), ridge_r, M[tile], 8,
                     smooth=True))
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = Vector((cx + sx * rx, cy, zr)) + lift
            bot = Vector((cx + sx * HX, cy + sy * HY, z_eave)) + lift * 0.9
            P.append(rod("hip", top, bot + (bot - top).normalized() * 0.08, ridge_r * 0.85, M[tile], 8, smooth=True))
        P.append(add_sphere("ridge_end", ridge_r * 1.5, loc=(cx + sx * rx, cy, zr + 0.13), material=M[tile],
                            segments=8, rings=6))
    for O, ex, ev, en, r in frames:
        e = O + ev * vl
        P.append(beam("fascia", e - ex * (r + HY + 0.05), e + ex * (r + HY + 0.05), 0.1, 0.2, en, M[trim], 0.035))
    return zr


# ============================================================ houses
FZ = 0.65            # stilt-house floor height
WALL_H = 1.95


def house_materials(roof, wall, trim):
    return dict(roof=mat("M_Roof", roof), wall=mat("M_Wall", wall), trim=mat("M_Wood", trim), glass=glass_mat())


def stilts(P, M, xs, ys, top, m='trim', size=0.17):
    for x in xs:
        for y in ys:
            P.append(bx("stilt", (size, size, top), (x, y, top / 2), M[m], 0.03, 1))


def build_rumah_a():
    """Cream plank house, gable roof with ridge along X, open front verandah with railings."""
    name = "rumah_a"
    root = empty(name)
    M = house_materials("roof", "#f4e3bf", "#7a4d2e")
    P = []
    WZ = FZ + WALL_H
    x0, x1, y0, y1 = -2.1, 2.1, -1.3, 1.3
    py = -2.3                      # porch front edge
    # --- base: floor platform + stilts
    P.append(bx("floor", (4.34, y1 - py + 0.04, 0.18), (0, (y1 + py) / 2, FZ - 0.09), M['trim'], 0.05, 2))
    stilts(P, M, (-2.0, 0.0, 2.0), (-1.2, 1.2), FZ - 0.18)
    stilts(P, M, (-2.0, 2.0), (py + 0.1,), FZ - 0.18)
    # --- walls
    P.append(siding_ring("walls", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], FZ, WZ, 7, 0.028, M['wall']))
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        P.append(bx("corner", (0.15, 0.15, WALL_H + 0.05), (x, y, FZ + WALL_H / 2), M['trim'], 0.035, 1))
    # --- roof (ridge along X)
    pitch = math.radians(33)
    t = math.tan(pitch)
    zr = WZ + 1.3 * t + 0.12
    hx = 2.55
    gable_roof(P, M, (-hx, 0, zr), (hx, 0, zr), 1.75, pitch, 5)
    for sx in (-1, 1):   # gable ends: vertical planks
        top = lambda xx: max(WZ, zr - 0.14 - abs(xx) * t)
        P.append(vplank_panel("gable", (sx * x1, 0, 0), facing_rot((sx, 0)), -1.3, 1.3, lambda xx: WZ - 0.05, top,
                              0.26, 0.025, M['wall'], breaks=(0.0,)))
        P.append(bx("gable_vent", (0.05, 0.36, 0.24), (sx * (x1 + 0.03), 0, WZ + 0.42), M['trim'], 0))
    # --- front wall: door + shuttered windows; side/back windows
    door(P, M, (0.0, y0, 0), 0.0, FZ)
    for sx in (-1, 1):
        window(P, M, (sx * 1.35, y0, 0), 0.0, FZ + 1.05)
    window(P, M, (x1, 0.1, 0), facing_rot((1, 0)), FZ + 1.05, shutters=True, shut='roof')
    window(P, M, (x0, 0.1, 0), facing_rot((-1, 0)), FZ + 1.05, shutters=True, shut='roof')
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FZ + 1.05, cross=False)
    # --- porch railing + steps
    railing(P, M, (-2.05, py + 0.08), (-0.6, py + 0.08), FZ, spacing=0.3)
    railing(P, M, (0.6, py + 0.08), (2.05, py + 0.08), FZ, spacing=0.3)
    for sx in (-1, 1):
        railing(P, M, (sx * 2.05, py + 0.08), (sx * 2.05, y0 - 0.12), FZ, posts=False, spacing=0.3)
    steps(P, M, 0.0, py, 1.1, FZ, 3)
    finish(root, P, name)
    center_root(root)
    return root


def build_rumah_b():
    """Brown vertical-plank house, steep front-facing gable with crossed barge 'horns',
    cream trim, small centred porch under its own little gable canopy."""
    name = "rumah_b"
    root = empty(name)
    M = dict(roof=mat("M_Roof", "roof_dark"), wall=mat("M_Wall", "#a86d3e"), trim=mat("M_Trim", "#f3e4c4"),
             glass=glass_mat())
    P = []
    WZ = FZ + WALL_H
    x0, x1, y0, y1 = -1.9, 1.9, -1.2, 1.5
    # base
    P.append(bx("floor", (x1 - x0 + 0.14, y1 - y0 + 0.14, 0.18), (0, (y0 + y1) / 2, FZ - 0.09), M['wall'], 0.05, 2))
    P.append(bx("porch_floor", (2.1, 1.06, 0.16), (0, -1.72, FZ - 0.08), M['wall'], 0.05, 2))
    stilts(P, M, (-1.8, 0.0, 1.8), (-1.1, 1.4), FZ - 0.18, m='wall')
    # walls: vertical planks, cream corner boards
    for (ox, oy, fx, fy, half) in ((0, y0, 0, -1, 1.9), (0, y1, 0, 1, 1.9), (x0, 0.15, -1, 0, 1.35),
                                   (x1, 0.15, 1, 0, 1.35)):
        P.append(vplank_panel("wall", (ox, oy, 0), facing_rot((fx, fy)), -half, half, lambda xx: FZ,
                              lambda xx: WZ, 0.36, 0.028, M['wall']))
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        P.append(bx("corner", (0.15, 0.15, WALL_H + 0.05), (x, y, FZ + WALL_H / 2), M['trim'], 0.035, 1))
    P.append(beam("skirt", (x0 - 0.05, y0 - 0.05, FZ + 0.06), (x1 + 0.05, y0 - 0.05, FZ + 0.06), 0.1, 0.12, Z,
                  M['trim'], 0.03))
    # main roof: ridge along Y (front gable faces -Y)
    pitch = math.radians(37)
    t = math.tan(pitch)
    zr = WZ + 1.9 * t + 0.12
    yf, yb = y0 - 0.5, y1 + 0.4
    gable_roof(P, M, (0, yb, zr), (0, yf, zr), 2.35, pitch, 6, trim='trim', horns=('b',), balls=True)
    # front & back gable triangles (cream vertical planks) + diamond vent window
    for oy, fy in ((y0, -1), (y1, 1)):
        top = lambda xx: max(WZ, zr - 0.14 - abs(xx) * t)
        P.append(vplank_panel("gable", (0, oy, 0), facing_rot((0, fy)), x0, x1, lambda xx: WZ - 0.05, top,
                              0.3, 0.025, M['trim'], breaks=(0.0,)))
    P.append(beam("gable_beam", (x0 - 0.1, y0 - 0.06, WZ - 0.02), (x1 + 0.1, y0 - 0.06, WZ - 0.02), 0.12, 0.14, Z,
                  M['wall'], 0.03))
    P.append(bx("vent_frame", (0.5, 0.06, 0.5), (0, y0 - 0.04, WZ + 0.72), M['wall'], 0.03, 1, rot=(0, math.radians(45), 0)))
    P.append(bx("vent_glass", (0.34, 0.05, 0.34), (0, y0 - 0.07, WZ + 0.72), M['glass'], 0, rot=(0, math.radians(45), 0)))
    # porch canopy (little gable) on two posts
    cp = math.radians(33)
    zc = 2.2 + 1.25 * math.tan(cp)
    gable_roof(P, M, (0, y0 + 0.05, zc), (0, -2.42, zc), 1.25, cp, 3, trim='trim', ridge_r=0.1, balls=False,
               horns=('b',), horn_len=0.35, barge_h=0.22)
    for sx in (-1, 1):
        P.append(bx("porch_col", (0.16, 0.16, 2.16), (sx * 0.95, -2.13, 1.08), M['trim'], 0.035, 1))
    P.append(beam("porch_beam", (-1.05, -2.13, 2.1), (1.05, -2.13, 2.1), 0.14, 0.14, Z, M['trim']))
    for sx in (-1, 1):
        railing(P, M, (sx * 0.95, -2.13), (sx * 0.95, y0 - 0.1), FZ, spacing=0.26, posts=False)
    steps(P, M, 0.0, -2.25, 1.2, FZ, 3, m='wall')
    # openings
    door(P, M, (0.0, y0, 0), 0.0, FZ, frame='trim', panel='trim', glass_top=True)
    for sx in (-1, 1):
        window(P, M, (sx * 1.42, y0, 0), 0.0, FZ + 1.05, w=0.6, frame='trim')
        window(P, M, (sx * x1, 0.15, 0), facing_rot((sx, 0)), FZ + 1.05, shutters=True, frame='trim', shut='trim')
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FZ + 1.05, cross=False, frame='trim')
    finish(root, P, name)
    center_root(root)
    return root


def build_rumah_c():
    """Honey-plank house under a hip (limas) roof with a recessed corner porch at the front-left."""
    name = "rumah_c"
    root = empty(name)
    M = house_materials("#b8543a", "#d6a867", "wood_dark")
    P = []
    WZ = FZ + WALL_H
    x0, x1, y0, y1 = -2.3, 2.3, -1.45, 1.45
    px, py = -0.7, -0.35       # porch cut-out corner (porch = x0..px, y0..py)
    P.append(bx("floor", (x1 - x0 + 0.1, y1 - y0 + 0.1, 0.18), (0, 0, FZ - 0.09), M['trim'], 0.05, 2))
    stilts(P, M, (-2.2, -0.75, 0.75, 2.2), (-1.35, 1.35), FZ - 0.18)
    poly = [(px, y0), (x1, y0), (x1, y1), (x0, y1), (x0, py), (px, py)]
    P.append(siding_ring("walls", poly, FZ, WZ, 7, 0.028, M['wall']))
    for x, y in poly:
        P.append(bx("corner", (0.15, 0.15, WALL_H + 0.05), (x, y, FZ + WALL_H / 2), M['trim'], 0.035, 1))
    # hip roof
    pitch = math.radians(33)
    HY = 1.45 + 0.45
    HX = 2.3 + 0.45
    t = math.tan(pitch)
    z_eave = WZ + 0.12 - 0.45 * t
    hip_roof(P, M, 0, 0, HX, HY, z_eave, pitch, 5)
    # corner column + porch railing + steps
    colh = WZ - 0.02
    P.append(bx("porch_col", (0.17, 0.17, colh), (x0 + 0.06, y0 + 0.06, colh / 2), M['trim'], 0.035, 1))
    P.append(beam("porch_beam", (x0 - 0.04, y0 + 0.02, WZ - 0.08), (px, y0 + 0.02, WZ - 0.08), 0.15, 0.16, Z, M['trim']))
    P.append(beam("porch_beam", (x0 + 0.02, y0 - 0.04, WZ - 0.08), (x0 + 0.02, py, WZ - 0.08), 0.15, 0.16, Z, M['trim']))
    railing(P, M, (x0 + 0.06, y0 + 0.06), (-2.0, y0 + 0.06), FZ, spacing=0.26)
    railing(P, M, (x0 + 0.06, y0 + 0.06), (x0 + 0.06, py - 0.1), FZ, spacing=0.26, posts=False)
    steps(P, M, -1.4, y0, 0.95, FZ, 3)
    # door on the porch back wall, windows
    door(P, M, (-1.5, py, 0), 0.0, FZ)
    window(P, M, (px, (y0 + py) / 2, 0), facing_rot((-1, 0)), FZ + 1.05, w=0.5, cross=False)
    for x in (0.15, 1.7):
        window(P, M, (x, y0, 0), 0.0, FZ + 1.05, shutters=True, shut='trim')
    window(P, M, (x1, 0.0, 0), facing_rot((1, 0)), FZ + 1.05)
    window(P, M, (x0, 0.55, 0), facing_rot((-1, 0)), FZ + 1.05)
    window(P, M, (0.8, y1, 0), facing_rot((0, 1)), FZ + 1.05, cross=False)
    window(P, M, (-1.2, y1, 0), facing_rot((0, 1)), FZ + 1.05, cross=False)
    # flower box under the right front window (splash of colour on the facade)
    finish(root, P, name)
    center_root(root)
    return root


# ------------------------------------------------------------ map v3: more house types
# The game recolours M_Wall / M_Roof per house (world.gd, layout "wall" / "roof"), so a
# handful of shapes gives dozens of different-looking homes across the hamlets.
def build_rumah_d():
    """Rumah panggung tinggi: high stilts (1.45 m) with cross braces, a long front verandah
    under the main gable (ridge along X), a steep ladder-stair at the side of the porch."""
    name = "rumah_d"
    root = empty(name)
    M = house_materials("#9c4c2b", "#e9d3a4", "#6e4a2c")
    P = []
    FH = 1.45
    WZ = FH + 1.9
    x0, x1, y0, y1 = -2.0, 2.0, -1.0, 1.4
    py = -2.1
    P.append(bx("floor", (x1 - x0 + 0.2, y1 - py + 0.04, 0.18), (0, (y1 + py) / 2, FH - 0.09), M['trim'], 0.05, 2))
    stilts(P, M, (-1.9, 0.0, 1.9), (py + 0.1, y0, y1 - 0.1), FH - 0.18, size=0.19)
    for y in (y0, y1 - 0.1):   # cross braces between the stilts
        P.append(beam("brace", (-1.9, y, 0.25), (0.0, y, FH - 0.35), 0.07, 0.07, Vector((0, 1, 0)), M['trim'], 0.01))
        P.append(beam("brace", (1.9, y, 0.25), (0.0, y, FH - 0.35), 0.07, 0.07, Vector((0, 1, 0)), M['trim'], 0.01))
    P.append(siding_ring("walls", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], FH, WZ, 7, 0.028, M['wall']))
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        P.append(bx("corner", (0.15, 0.15, WZ - FH + 0.05), (x, y, (FH + WZ) / 2), M['trim'], 0.035, 1))
    pitch = math.radians(36)
    t = math.tan(pitch)
    yc = (py + y1) / 2
    hw = (y1 - py) / 2 + 0.4
    zr = WZ + (y1 - yc) * t + 0.1
    gable_roof(P, M, (-2.45, yc, zr), (2.45, yc, zr), hw, pitch, 6, horns=('a', 'b'), horn_len=0.4)
    ym = (y0 + y1) / 2
    for sx in (-1, 1):
        P.append(vplank_panel("gable", (sx * x1, ym, 0), facing_rot((sx, 0)), -1.2, 1.2, lambda xx: WZ - 0.05,
                              lambda xx: max(WZ, zr - 0.2 - max(abs(ym + xx - yc), abs(ym - xx - yc)) * t),
                              0.26, 0.025, M['wall'], breaks=(0.0,)))
    for sx in (-1, 1):   # verandah posts carrying the roof
        P.append(bx("porch_post", (0.14, 0.14, WZ - FH), (sx * 1.95, py + 0.1, (FH + WZ) / 2), M['trim'], 0.03, 1))
    railing(P, M, (-1.95, py + 0.1), (1.0, py + 0.1), FH, spacing=0.22)
    railing(P, M, (-1.95, py + 0.1), (-1.95, y0 - 0.1), FH, spacing=0.22, posts=False)
    railing(P, M, (1.95, py + 0.1), (1.95, y0 - 0.1), FH, spacing=0.22, posts=False)
    steps(P, M, 1.55, py, 0.8, FH, 6, depth=0.24)
    door(P, M, (0.9, y0, 0), 0.0, FH)
    window(P, M, (-0.9, y0, 0), 0.0, FH + 1.0, w=0.9, shutters=True, shut='roof')
    window(P, M, (x1, 0.2, 0), facing_rot((1, 0)), FH + 1.0)
    window(P, M, (x0, 0.2, 0), facing_rot((-1, 0)), FH + 1.0)
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FH + 1.0, cross=False)
    # a water jar and a firewood stack under the house
    P.append(rod("tempayan", (-1.0, 0.3, 0.0), (-1.0, 0.3, 0.55), 0.26, mat("M_Jar", "#8a4a2e"), 12, r2=0.2, smooth=True))
    for k in range(4):
        P.append(rod("firewood", (0.4, 0.8 - k * 0.14, 0.08 + (k % 2) * 0.12), (1.3, 0.8 - k * 0.14, 0.08 + (k % 2) * 0.12),
                     0.06, M['trim'], 6))
    finish(root, P, name)
    center_root(root)
    return root


def build_rumah_e():
    """Rumah limas: square plan under a steep pyramid (limas) roof on low stilts, with a
    front porch under its own little gable, two carved posts and a flower box."""
    name = "rumah_e"
    root = empty(name)
    M = house_materials("#b8543a", "#f1e2c2", "#7a4d2e")
    P = []
    WZ = FZ + WALL_H
    x0, x1, y0, y1 = -1.9, 1.9, -1.6, 1.6
    P.append(bx("floor", (x1 - x0 + 0.1, y1 - y0 + 0.1, 0.18), (0, 0, FZ - 0.09), M['trim'], 0.05, 2))
    P.append(bx("porch_floor", (2.6, 1.1, 0.16), (0, y0 - 0.55, FZ - 0.08), M['trim'], 0.05, 2))
    stilts(P, M, (-1.8, 0.0, 1.8), (-1.5, 0.0, 1.5), FZ - 0.18)
    stilts(P, M, (-1.2, 1.2), (y0 - 1.0,), FZ - 0.18)
    P.append(siding_ring("walls", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], FZ, WZ, 7, 0.028, M['wall']))
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        P.append(bx("corner", (0.15, 0.15, WALL_H + 0.05), (x, y, FZ + WALL_H / 2), M['trim'], 0.035, 1))
    pitch = math.radians(40)
    t = math.tan(pitch)
    H = 1.9 + 0.45
    hip_roof(P, M, 0, 0, H, H + 0.05, WZ + 0.12 - 0.45 * t, pitch, 6)
    cp = math.radians(33)
    zc = WZ + 0.05 + 1.3 * math.tan(cp)
    gable_roof(P, M, (0, y0 + 0.2, zc), (0, y0 - 1.25, zc), 1.3, cp, 3, ridge_r=0.1, balls=False, horns=('b',),
               horn_len=0.3, barge_h=0.2)
    for sx in (-1, 1):
        P.append(bx("porch_col", (0.17, 0.17, WZ - FZ + 0.05), (sx * 1.15, y0 - 1.0, (FZ + WZ) / 2), M['trim'], 0.04, 1))
        railing(P, M, (sx * 1.15, y0 - 1.0), (sx * 1.15, y0 - 0.1), FZ, spacing=0.26, posts=False)
    P.append(beam("porch_beam", (-1.25, y0 - 1.0, WZ - 0.05), (1.25, y0 - 1.0, WZ - 0.05), 0.14, 0.14, Z, M['trim']))
    steps(P, M, 0.0, y0 - 1.1, 1.1, FZ, 3)
    door(P, M, (0.0, y0, 0), 0.0, FZ, glass_top=True)
    for sx in (-1, 1):
        window(P, M, (sx * 1.25, y0, 0), 0.0, FZ + 1.05, w=0.6, shutters=True, shut='roof')
        window(P, M, (sx * x1, 0.0, 0), facing_rot((sx, 0)), FZ + 1.05)
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FZ + 1.05, cross=False)
    box_m = mat("M_FlowerBox", "#7a4d2e")
    flo = mat("M_Petal", "#e0572a")
    for sx in (-1, 1):
        P.append(bx("flower_box", (0.7, 0.2, 0.16), (sx * 1.25, y0 - 0.14, FZ + 0.62), box_m, 0.02, 1))
        for k in range(4):
            P.append(add_ico("bloom", 0.08, loc=(sx * 1.25 - 0.27 + k * 0.18, y0 - 0.14, FZ + 0.76), material=flo, subdiv=1))
    finish(root, P, name)
    center_root(root)
    return root


def build_rumah_f():
    """Rumah bata: a ground-level brick-and-plaster house (no stilts) with a front-facing
    zinc gable, a tiled front terrace under a lean-to roof on two posts and a low wall."""
    name = "rumah_f"
    root = empty(name)
    M = dict(roof=mat("M_Roof", "#6f8ea6"), wall=mat("M_Wall", "#f0e6cf"), trim=mat("M_Trim", "#8a5a36"),
             base=mat("M_Plinth", "#9a8f7c"), glass=glass_mat())
    P = []
    FB = 0.28
    WZ = FB + 2.3
    x0, x1, y0, y1 = -2.2, 2.2, -1.4, 1.8
    P.append(bx("plinth", (x1 - x0 + 0.1, y1 - y0 + 0.1, FB), (0, (y0 + y1) / 2, FB / 2), M['base'], 0.03, 1))
    P.append(bx("terrace", (x1 - x0 + 0.3, 1.5, FB - 0.08), (0, y0 - 0.75, (FB - 0.08) / 2), M['base'], 0.03, 1))
    P.append(siding_ring("walls", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], FB, WZ, 3, 0.012, M['wall']))
    P.append(beam("wall_band", (x0 - 0.03, y0 - 0.03, FB + 0.5), (x1 + 0.03, y0 - 0.03, FB + 0.5), 0.06, 0.08, Z, M['base'], 0.01))
    pitch = math.radians(28)
    t = math.tan(pitch)
    zr = WZ + 2.2 * t + 0.1
    gable_roof(P, M, (0, y1 + 0.45, zr), (0, y0 - 0.3, zr), 2.6, pitch, 3, lip=None, trim='trim', tile_kw=ZINC,
               ridge_r=0.12, ridge_verts=4, balls=False, barge_h=0.2, wear=new_wear('zinc', rust=0.7, moss=0.4, seed=11))
    for oy, fy in ((y0, -1), (y1, 1)):
        P.append(vplank_panel("gable", (0, oy, 0), facing_rot((0, fy)), x0, x1, lambda xx: WZ - 0.05,
                              lambda xx: max(WZ, zr - 0.12 - abs(xx) * t), 0.32, 0.02, M['wall'], breaks=(0.0,)))
    # terrace lean-to on two posts, a low front wall with a gap
    shed_roof(P, M, Vector((0, y0 - 0.02, WZ - 0.1)), (0, -1, 0), (1, 0, 0), x0 - 0.2, x1 + 0.2, 1.6,
              math.radians(14), 2, tile_kw=ZINC, wear=new_wear('zinc', rust=0.9, moss=0.3, seed=12))
    for sx in (-1, 1):
        P.append(bx("terrace_post", (0.16, 0.16, WZ - 0.4), (sx * 2.1, y0 - 1.4, (WZ - 0.4) / 2 + 0.1), M['trim'], 0.03, 1))
        P.append(bx("low_wall", (1.2, 0.16, 0.55), (sx * 1.55, y0 - 1.45, FB + 0.2), M['wall'], 0.03, 1))
    door(P, M, (-0.6, y0, 0), 0.0, FB, h=1.9)
    window(P, M, (1.1, y0, 0), 0.0, FB + 1.35, w=1.1, h=0.9)
    for sx in (-1, 1):
        window(P, M, (sx * x1, 0.2, 0), facing_rot((sx, 0)), FB + 1.35)
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FB + 1.35, cross=False)
    # potted plants on the terrace
    pot = mat("M_Pot", "#b8643a")
    leaf = mat("M_PlantLeaf", "#5f8a3c")
    for px_ in (-1.6, 1.6, 0.6):
        P.append(rod("pot", (px_, y0 - 1.1, FB - 0.08), (px_, y0 - 1.1, FB + 0.22), 0.14, pot, 10, r2=0.11))
        P.append(add_ico("plant", 0.26, loc=(px_, y0 - 1.1, FB + 0.42), material=leaf, subdiv=1, scale=(1, 1, 0.8)))
    finish(root, P, name)
    center_root(root)
    return root


def build_rumah_g():
    """Pondok: a long low wooden hut on short stilts under a single lean-to zinc roof, a side
    verandah with a bench and a clothesline pole - the simplest home in the hamlets."""
    name = "rumah_g"
    root = empty(name)
    M = house_materials("#8c8f86", "#b98a58", "#5e4028")
    P = []
    F = 0.45
    x0, x1, y0, y1 = -2.4, 1.0, -1.1, 1.2
    zf, zb = F + 2.35, F + 1.75       # front high, back low
    P.append(bx("floor", (4.9, y1 - y0 + 0.2, 0.16), (-0.65 + 0.75, (y0 + y1) / 2, F - 0.08), M['trim'], 0.04, 2))
    stilts(P, M, (-2.3, -0.7, 0.9, 2.5), (y0 + 0.05, y1 - 0.05), F - 0.16)
    wall_top = lambda xx: zf
    for (ox, oy, fx, fy, a_, b_) in ((-0.7, y0, 0, -1, -1.7, 1.7), (-0.7, y1, 0, 1, -1.7, 1.7)):
        top = zf if fy < 0 else zb
        P.append(vplank_panel("wall", (ox, oy, 0), facing_rot((fx, fy)), a_, b_, lambda xx: F, lambda xx, tt=top: tt - 0.1,
                              0.3, 0.03, M['wall']))
    for sx, xx in ((-1, x0), (1, x1)):
        P.append(vplank_panel("wall", (xx, (y0 + y1) / 2, 0), facing_rot((sx, 0)), -1.15, 1.15, lambda q: F,
                              lambda q, s=sx: zb + (zf - zb) * (0.5 - q / 2.3 * (1 if s > 0 else -1)) - 0.1,
                              0.3, 0.03, M['wall']))
    pitch = math.atan((zf - zb) / (y1 - y0))
    shed_roof(P, M, Vector((0, y0 - 0.45, zf + 0.05 + 0.45 * math.tan(pitch))), (0, 1, 0), (1, 0, 0), x0 - 0.35, 2.75,
              (y1 - y0) + 0.9, pitch, 2, tile_kw=ZINC, wear=new_wear('zinc', rust=1.0, moss=0.5, seed=21))
    for y in (y0 + 0.05, y1 - 0.05):
        P.append(bx("verandah_post", (0.13, 0.13, 1.8), (2.5, y, F + 0.9), M['trim'], 0.03, 1))
    railing(P, M, (2.5, y0 + 0.05), (2.5, y1 - 0.05), F, spacing=0.3, posts=False)
    bench(P, M, 1.75, y1 - 0.35, F, 1.1)
    door(P, M, (0.2, y0, 0), 0.0, F)
    window(P, M, (-1.4, y0, 0), 0.0, F + 1.05, w=0.8, shutters=True, shut='trim')
    steps(P, M, 0.2, y0, 0.9, F, 2)
    P.append(rod("clothes_pole", (3.4, -0.6, 0), (3.4, -0.6, 1.7), 0.05, M['trim'], 6))
    P.append(rod("clothes_line", (3.4, -0.6, 1.62), (1.0, -1.2, F + 1.9), 0.012, M['trim'], 4))
    cloth = [mat("M_Cloth1", "#d5543d"), mat("M_Cloth2", "#4f86b8"), mat("M_Cloth3", "#f2c14e")]
    for k in range(3):
        f_ = 0.25 + k * 0.25
        cx = 3.4 + (1.0 - 3.4) * f_
        cy = -0.6 + (-1.2 + 0.6) * f_
        cz = 1.62 + (F + 1.9 - 1.62) * f_ - 0.3
        P.append(bx("cloth", (0.34, 0.03, 0.45), (cx, cy, cz), cloth[k], 0.0, 1, rotz=math.atan2(-0.6, -2.4)))
    finish(root, P, name)
    center_root(root)
    return root


# ------------------------------------------------------------ bridges (map v3)
def _bridge(name, concrete):
    """14 m bridge along X (deck 0.55 m above the banks, 2.5 m ramps at each end), 3.2 m wide."""
    root = empty(name)
    L, W, HD, RAMP = 14.0, 3.2, 0.55, 2.5
    if concrete:
        M = dict(deck=mat("M_Concrete", "#c9c2b0"), rail=mat("M_Rail", "#e8e0cc"), trim=mat("M_Paint", "#d5543d"),
                 pier=mat("M_Pier", "#a39c8c"))
    else:
        M = dict(deck=mat("M_Wood", "#a8703f"), rail=mat("M_WoodDark", "#6e4a2c"), trim=mat("M_WoodDark", "#6e4a2c"),
                 pier=mat("M_WoodDark", "#6e4a2c"))
    P = []
    hx = L / 2

    def zdeck(x):
        a = abs(x)
        if a <= hx - RAMP:
            return HD
        return HD * max(0.0, (hx - a) / RAMP)

    if concrete:
        # slab: top follows the ramps, 0.35 m thick, bevelled
        xs = [-hx, -hx + RAMP, hx - RAMP, hx]
        verts, faces = [], []
        for x in xs:
            zt = zdeck(x) + 0.02
            for y in (-W / 2, W / 2):
                verts.append((x, y, zt))
                verts.append((x, y, zt - 0.35 if abs(x) < hx - 0.01 else -0.2))
        n = len(xs)
        for i in range(n - 1):
            a, b = i * 4, (i + 1) * 4
            faces += [(a, b, b + 2, a + 2), (a + 1, a + 3, b + 3, b + 1), (a, a + 1, b + 1, b), (a + 2, b + 2, b + 3, a + 3)]
        faces += [(0, 2, 3, 1), ((n - 1) * 4, (n - 1) * 4 + 1, (n - 1) * 4 + 3, (n - 1) * 4 + 2)]
        P.append(mesh_from_data("slab", verts, faces, M['deck']))
        for x in (-hx + RAMP + 1.2, 0.0, hx - RAMP - 1.2):
            P.append(bx("pier", (0.6, W - 0.4, 2.0), (x, 0, HD - 1.3), M['pier'], 0.05, 1))
        for sy in (-1, 1):
            y = sy * (W / 2 - 0.1)
            for x in [(-hx + RAMP) + k * (L - 2 * RAMP) / 6 for k in range(7)]:
                P.append(bx("rail_post", (0.18, 0.18, 0.8), (x, y, HD + 0.4), M['rail'], 0.03, 1))
            P.append(beam("rail_top", (-hx + RAMP - 0.1, y, HD + 0.82), (hx - RAMP + 0.1, y, HD + 0.82), 0.16, 0.12, Z, M['trim'], 0.03))
            P.append(beam("rail_mid", (-hx + RAMP, y, HD + 0.45), (hx - RAMP, y, HD + 0.45), 0.08, 0.08, Z, M['rail'], 0.02))
            for sx in (-1, 1):   # sloped end rails down the ramps
                xa, xb = sx * (hx - RAMP), sx * (hx - 0.4)
                P.append(beam("rail_ramp", (xa, y, HD + 0.82), (xb, y, zdeck(xb) + 0.7), 0.14, 0.1, Z, M['trim'], 0.03))
                P.append(bx("rail_end", (0.2, 0.2, 0.75), (xb, y, zdeck(xb) + 0.37), M['rail'], 0.03, 1))
    else:
        # plank deck on log stringers, log piers, rope-and-pole railings
        n = int(L / 0.28)
        for i in range(n):
            x = -hx + (i + 0.5) * L / n
            z = zdeck(x)
            nx_ = x + L / n
            slope = math.atan2(zdeck(min(nx_, hx)) - z, L / n) if abs(x) > hx - RAMP - 0.2 else 0.0
            P.append(bx("plank", (L / n - 0.03, W - (0.1 if i % 3 else 0.0), 0.07),
                        (x, 0, max(z, 0.02) - 0.035), M['deck'], 0.01, 1, rot=(0, -slope, 0)))
        for sy in (-1, 1):
            y = sy * (W / 2 - 0.35)
            P.append(rod("stringer", (-hx + RAMP - 0.3, y, HD - 0.16), (hx - RAMP + 0.3, y, HD - 0.16), 0.12, M['pier'], 8))
        for x in (-hx + RAMP + 0.2, -1.5, 1.5, hx - RAMP - 0.2):
            for sy in (-1, 1):
                P.append(rod("pile", (x, sy * (W / 2 - 0.2), -1.4), (x, sy * (W / 2 - 0.2), HD + 0.95), 0.11, M['pier'], 8))
            P.append(rod("cross", (x, -W / 2 + 0.1, HD - 0.2), (x, W / 2 - 0.1, HD - 0.2), 0.08, M['pier'], 6))
        for sy in (-1, 1):
            y = sy * (W / 2 - 0.2)
            P.append(rod("handrail", (-hx + RAMP + 0.2, y, HD + 0.9), (hx - RAMP - 0.2, y, HD + 0.9), 0.055, M['rail'], 6))
            for sx in (-1, 1):
                P.append(rod("handrail_end", (sx * (hx - RAMP - 0.2), y, HD + 0.9), (sx * (hx - 0.3), y, 0.6), 0.05, M['rail'], 6))
                P.append(rod("end_post", (sx * (hx - 0.3), y, -0.1), (sx * (hx - 0.3), y, 0.7), 0.08, M['pier'], 6))
    finish(root, P, name)
    center_root(root, ground=False)
    return root


def build_jembatan_kayu():
    return _bridge("jembatan_kayu", False)


def build_jembatan_beton():
    return _bridge("jembatan_beton", True)


def bench(P, M, xc, yc, z0, length=1.1, rotz=0.0, m='trim', back=True):
    fr = lambda x, y, z: fpt((xc, yc, z0), rotz, (x, y, z))
    P.append(bx("bench_seat", (length, 0.36, 0.07), fr(0, 0, 0.42), M[m], 0.025, 1, rotz))
    for sx in (-1, 1):
        P.append(bx("bench_leg", (0.07, 0.3, 0.39), fr(sx * (length / 2 - 0.12), 0, 0.195), M[m], 0.02, 1, rotz))
    if back:
        P.append(bx("bench_back", (length, 0.06, 0.16), fr(0, 0.2, 0.72), M[m], 0.02, 1, rotz))
        for sx in (-1, 1):
            P.append(bx("bench_bpost", (0.06, 0.06, 0.36), fr(sx * (length / 2 - 0.12), 0.19, 0.58), M[m], 0, rotz=rotz))


ZINC = dict(period=0.2, amp=0.035, step=0.035, cham=0.06, thick=0.06)


def build_kantor():
    """Player's plantation office: cream plank hut, green zinc roof, veranda + bench, and a big
    signboard in front whose face is the separate child `SignBoard`."""
    name = "kantor"
    root = empty(name)
    M = dict(roof=mat("M_Roof", "#4e9a5a"), wall=mat("M_Wall", "#f6ead0"), trim=mat("M_Wood", "#8a5a36"),
             glass=glass_mat())
    P = []
    FK = 0.42
    WZ = FK + 2.0
    x0, x1, y0, y1 = -2.0, 2.0, -0.55, 1.55
    vy = -1.45                                   # veranda front edge
    P.append(bx("floor", (x1 - x0 + 0.14, y1 - vy + 0.04, 0.16), (0, (y1 + vy) / 2, FK - 0.08), M['trim'], 0.05, 2))
    stilts(P, M, (-1.9, 0.0, 1.9), (vy + 0.1, y1 - 0.1), FK - 0.16)
    for (ox, oy, fx, fy, half) in ((0, y0, 0, -1, 2.0), (0, y1, 0, 1, 2.0), (x0, 0.5, -1, 0, 1.05),
                                   (x1, 0.5, 1, 0, 1.05)):
        P.append(vplank_panel("wall", (ox, oy, 0), facing_rot((fx, fy)), -half, half, lambda xx: FK,
                              lambda xx: WZ, 0.34, 0.026, M['wall']))
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        P.append(bx("corner", (0.15, 0.15, WZ - FK + 0.04), (x, y, (FK + WZ) / 2), M['trim'], 0.035, 1))
    P.append(beam("skirt", (x0 - 0.06, y0 - 0.05, FK + 0.07), (x1 + 0.06, y0 - 0.05, FK + 0.07), 0.1, 0.14, Z,
                  M['trim'], 0.03))
    # green corrugated zinc roof, ridge along X; cream fascia/barge outline
    pitch = math.radians(22)
    t = math.tan(pitch)
    yc = (y0 + y1) / 2
    zr = WZ + 1.05 * t + 0.1
    gable_roof(P, M, (-2.45, yc, zr), (2.45, yc, zr), 1.6, pitch, 2, lip=None, trim='wall', tile_kw=ZINC,
               ridge_r=0.13, ridge_verts=4, balls=False, barge_h=0.2, wear=new_wear('zinc', rust=0.55, moss=0.6, seed=3))
    for sx in (-1, 1):
        top = lambda xx: max(WZ, zr - 0.1 - abs(xx) * t)
        P.append(vplank_panel("gable", (sx * x1, yc, 0), facing_rot((sx, 0)), -1.05, 1.05, lambda xx: WZ - 0.05,
                              top, 0.3, 0.02, M['wall'], breaks=(0.0,)))
    # veranda: posts with a small open rail, one step
    for sx in (-1, 1):
        railing(P, M, (sx * 1.95, vy + 0.08), (sx * 1.95, y0 - 0.12), FK, spacing=0.4)
    steps(P, M, 1.25, vy, 1.1, FK, 1, depth=0.32)
    # openings
    door(P, M, (1.25, y0, 0), 0.0, FK, glass_top=True)
    window(P, M, (-1.05, y0, 0), 0.0, FK + 1.1, w=1.1, h=0.8)
    window(P, M, (x1, 0.5, 0), facing_rot((1, 0)), FK + 1.1, shutters=True)
    window(P, M, (x0, 0.5, 0), facing_rot((-1, 0)), FK + 1.1, shutters=True)
    window(P, M, (0.0, y1, 0), facing_rot((0, 1)), FK + 1.1, cross=False)
    bench(P, M, 0.15, -0.85, FK, 1.0)
    # the signboard stand: two posts, backing frame, little green cap roof
    sx_, sy_ = -1.2, -2.35
    bw, bh, bz = 2.4, 0.9, 1.45
    for sg in (-1, 1):
        P.append(bx("sign_post", (0.15, 0.15, 2.12), (sx_ + sg * (bw / 2 + 0.12), sy_ + 0.08, 1.06), M['trim'], 0.035, 1))
    P.append(bx("sign_back", (bw + 0.18, 0.1, bh + 0.18), (sx_, sy_ + 0.1, bz), M['trim'], 0.04, 2))
    P.append(beam("sign_cap", (sx_ - bw / 2 - 0.3, sy_ + 0.08, bz + bh / 2 + 0.2),
                  (sx_ + bw / 2 + 0.3, sy_ + 0.08, bz + bh / 2 + 0.2), 0.42, 0.08, Z, M['roof'], 0.03))
    finish(root, P, name)
    sign = board_with_uv("SignBoard", bw, bh, 0.05, M['wall'], (sx_, sy_ + 0.02, bz))
    sign.parent = root          # root sits at the origin with identity transform
    center_root(root)
    return root


def build_gudang():
    """Open wooden farm shed (gudang kebun) like the target's top-left corner: six posts, a rusty
    corrugated zinc lean-to roof that is high at the open front (so the game camera sees the stock
    inside), plank back + left walls, low rails on the open right side, concrete floor with crates,
    sacks, a pallet of fertiliser, harvesting poles and a drum; a signboard on two posts in
    front-left whose face is the separate child `SignBoard` (like kantor's)."""
    name = "gudang"
    root = empty(name)
    BOARD, GREEN = "#efe3c4", "#7aa957"
    M = dict(roof=mat("M_Roof", "#a8a296"), trim=mat("M_Wood", "#6f5236"), plank=mat("M_Plank", "#a27b52"),
             board=mat("M_Board", BOARD))
    M['green'] = M['board']      # green print / sacks / drum = cream board tinted through the vertex colour

    def green(o, slot=None):
        """Tint o (or only its faces using material slot `slot`) print-green."""
        faces = None if slot is None else [p.index for p in o.data.polygons if p.material_index == slot]
        return PR.tint_to(o, GREEN, BOARD, faces)
    P = []
    x0, x1, y0, y1 = -2.5, 2.5, -1.15, 1.15
    ZF, ZB = 2.75, 2.15                          # beam tops at the front / back
    ya = -2.15                                   # front edge of the concrete apron
    t = (ZF - ZB) / (y1 - y0)
    pitch = math.atan(t)
    zbeam = lambda y: ZF - (y - y0) * t          # top of the rafters at y
    # --- floor slab (concrete: roof grey, a bit darker)
    slab = bx("slab", (x1 - x0 + 0.5, y1 + 0.25 - ya, 0.1), (0, (y1 + 0.25 + ya) / 2, 0.05), M['roof'], 0.03, 1)
    wattr(slab, "w_shade", -0.12)
    P.append(slab)
    # --- frame: posts, front/back beams, sloped rafters, knee braces at the front
    for x in (x0, 0.0, x1):
        for y in (y0, y1):
            h = zbeam(y)
            P.append(bx("post", (0.17, 0.17, h), (x, y, h / 2), M['trim'], 0.03, 1))
        P.append(beam("rafter", (x, y0 - 0.3, zbeam(y0 - 0.3) - 0.09), (x, y1 + 0.3, zbeam(y1 + 0.3) - 0.09), 0.13,
                      0.18, Z, M['trim'], 0.025))
    for y in (y0, y1):
        P.append(beam("beam", (x0 - 0.12, y, zbeam(y) - 0.2), (x1 + 0.12, y, zbeam(y) - 0.2), 0.15, 0.2, Z, M['trim'],
                      0.025))
    for x, sg in ((x0, 1), (0.0, -1), (0.0, 1), (x1, -1)):
        P.append(beam("brace", (x + sg * 0.06, y0, ZF - 1.0), (x + sg * 0.62, y0, ZF - 0.28), 0.1, 0.1, (0, -1, 0),
                      M['trim'], 0.0))
    # --- roof: corrugated zinc lean-to falling toward the back, heavy rust + moss streaks
    yf, yb = y0 - 0.4, y1 + 0.35
    shed_roof(P, M, (0, yf, zbeam(yf) + 0.04), (0, 1, 0), (1, 0, 0), x0 - 0.4, x1 + 0.4, yb - yf, pitch, 3,
              tile='roof', trim='trim', tile_kw=ZINC, wear=new_wear('zinc', rust=1.35, moss=1.0, seed=7))
    # --- walls: back (vertical planks, both faces), left side following the slope, rails on the right
    P.append(vplank_panel("wall_b", (0, y1 + 0.09, 0), facing_rot((0, 1)), x0, x1, lambda q: 0.1,
                          lambda q: zbeam(y1) - 0.2, 0.3, 0.028, M['plank']))
    P.append(vplank_panel("wall_bi", (0, y1 + 0.03, 0), facing_rot((0, -1)), x0, x1, lambda q: 0.1,
                          lambda q: zbeam(y1) - 0.2, 0.3, 0.022, M['plank']))
    P.append(vplank_panel("wall_l", (x0 - 0.09, 0, 0), facing_rot((-1, 0)), y0, y1, lambda q: 0.1,
                          lambda q: zbeam(-q) - 0.2, 0.3, 0.028, M['plank']))
    P.append(vplank_panel("wall_li", (x0 - 0.03, 0, 0), facing_rot((1, 0)), y0, y1, lambda q: 0.1,
                          lambda q: zbeam(q) - 0.2, 0.3, 0.022, M['plank']))
    for z in (0.45, 0.95):
        P.append(beam("rail", (x1 + 0.1, y0 + 0.1, z), (x1 + 0.1, y1 - 0.1, z), 0.07, 0.14, Z, M['plank'], 0.02))
    P.append(beam("rail_x", (x1 + 0.1, y0 + 0.12, 0.3), (x1 + 0.1, y1 - 0.12, 1.1), 0.06, 0.1, (1, 0, 0), M['plank'], 0))
    # --- contents: stock at the back under the roof, a loading area on the apron in front
    rnd = random.Random(12)
    FZ = 0.1
    for (cx, cy, cz, rz) in ((-1.95, 0.75, FZ, 0.04), (-1.3, 0.8, FZ, -0.06), (-1.9, 0.73, FZ + 0.44, 0.12),
                             (-1.35, 0.8, FZ + 0.44, -0.1), (-1.95, 0.75, FZ + 0.88, -0.05), (-0.35, -1.6, FZ, 0.25),
                             (0.3, -1.72, FZ, -0.1)):
        PR.crate_parts(P, M['plank'], M['plank'], loc=(cx, cy, cz), size=(0.62, 0.46, 0.44), rotz=rz, lo=True)
    # pallet with cream fertiliser sacks (green band) on the apron, front right
    px_, py_ = 1.45, -1.45
    for i in range(3):
        P.append(bx("pallet", (1.15, 0.2, 0.04), (px_, py_ - 0.26 + i * 0.26, FZ + 0.1), M['plank'], 0))
    for x in (px_ - 0.5, px_ + 0.5):
        P.append(bx("pallet_run", (0.12, 0.78, 0.08), (x, py_, FZ + 0.04), M['trim'], 0))
    k = 0
    for n, zz in ((2, FZ + 0.12), (2, FZ + 0.12 + 0.2), (1, FZ + 0.12 + 0.4)):
        for i in range(n):
            xx = px_ + (i - (n - 1) / 2) * 0.5
            P.append(green(PR.sack("sack", M['board'], M['green'], loc=(xx, py_, zz),
                                   rotz=math.pi / 2 + rnd.uniform(-0.08, 0.08), L=0.68, W=0.46, T=0.23, lo=True,
                                   seed=k), slot=1))
            k += 1
    # green sacks slumped at the back, one leaning
    for (sx_, sy_, rz, tl) in ((0.45, 0.8, 0.2, (0.0, 0.0)), (1.05, 0.75, -0.25, (0.0, 0.0)),
                               (0.75, 0.85, 0.05, (0.25, 0.1))):
        P.append(green(PR.sack("sack_g", M['green'], M['board'], loc=(sx_, sy_, FZ + (0.18 if tl[0] else 0.0)),
                               rotz=rz, L=0.66, W=0.44, T=0.24, lo=True, seed=20 + k, tilt=tl), slot=0))
        k += 1
    # harvesting poles (egrek) leaning on the back wall, and a green drum by the right front post
    for x in (-0.55, -0.42):
        P.append(rod("egrek", (x, y1 - 0.6, FZ), (x + 0.1, y1 - 0.05, FZ + 1.95), 0.03, M['plank'], 5))
    P.append(green(add_cyl("drum", 0.28, 0.86, loc=(2.05, -0.6, FZ + 0.43), material=M['green'], verts=10)))
    # --- signboard in front-left: two posts, backing frame, little zinc cap
    sx_, sy_ = -1.55, -2.5
    bw, bh, bz = 1.7, 0.95, 1.3
    for sg in (-1, 1):
        P.append(bx("sign_post", (0.13, 0.13, 1.95), (sx_ + sg * (bw / 2 + 0.1), sy_ + 0.08, 0.975), M['trim'], 0.03, 1))
    P.append(bx("sign_back", (bw + 0.16, 0.09, bh + 0.16), (sx_, sy_ + 0.09, bz), M['trim'], 0.035, 2))
    cap = beam("sign_cap", (sx_ - bw / 2 - 0.25, sy_ + 0.08, bz + bh / 2 + 0.17),
               (sx_ + bw / 2 + 0.25, sy_ + 0.08, bz + bh / 2 + 0.17), 0.36, 0.07, Z, M['roof'], 0.025)
    wattr(cap, "w_rust", 0.55)
    P.append(cap)
    finish(root, P, name)
    sign = board_with_uv("SignBoard", bw, bh, 0.05, M['board'], (sx_, sy_ + 0.03, bz))
    sign.parent = root
    center_root(root)
    return root


def striped_awning(P, M, x0, x1, y_back, z_back, y_front, z_front, stripe=0.4, bulge=0.05, valance=0.18):
    """Red/white striped canvas lean-to (stripes run down the slope) with a scalloped front valance."""
    n = max(2, round((x1 - x0) / stripe))
    sw = (x1 - x0) / n
    verts, faces, fm = [], [], []
    thick = 0.05
    for i in range(n):
        xa, xb = x0 + i * sw, x0 + (i + 1) * sw
        xm = (xa + xb) / 2
        mi = i % 2
        b = len(verts)
        # top: two quads with a raised centre line (billowing canvas)
        for (y, z) in ((y_back, z_back), (y_front, z_front)):
            verts += [(xa, y, z), (xm, y, z + bulge), (xb, y, z)]
        faces += [(b, b + 3, b + 4, b + 1), (b + 1, b + 4, b + 5, b + 2)]
        fm += [mi, mi]
        # underside
        verts += [(xa, y_back, z_back - thick), (xb, y_back, z_back - thick),
                  (xa, y_front, z_front - thick), (xb, y_front, z_front - thick)]
        faces += [(b + 6, b + 7, b + 9, b + 8)]
        fm += [mi]
        # scallop valance hanging at the front edge (a rounded flap)
        vb = len(verts)
        segs = 4
        for j in range(segs + 1):
            u = j / segs
            x = xa + (xb - xa) * u
            depth = valance * (0.55 + 0.45 * math.sin(math.pi * u))
            verts += [(x, y_front - 0.005, z_front + 0.01), (x, y_front - 0.005, z_front - depth)]
        for j in range(segs):
            q = vb + 2 * j
            faces += [(q, q + 1, q + 3, q + 2)]
            fm += [mi]
    o = mk_multi("awning", verts, faces, [M['red'], M['white']], fm)
    # make the valance double sided visually: add a back copy
    P.append(o)
    return o


def build_warung():
    """Roadside kiosk: plank walls, red/white striped canvas roof with scalloped valance, counter with
    kerupuk jars, shelves of bottles, hanging snack sachets, red plastic stools."""
    name = "warung"
    root = empty(name)
    M = dict(wood=mat("M_Wood", "wood"), red=mat("M_Red", "red"), white=mat("M_White", "white"), glass=glass_mat())
    P = []
    x0, x1, y0, y1 = -1.75, 1.75, -0.35, 1.05
    H = 2.3
    P.append(bx("slab", (x1 - x0 + 0.3, y1 - y0 + 0.62, 0.14), (0, (y0 + y1) / 2 - 0.16, 0.07), M['white'], 0.04, 2))
    # back wall (outer + inner face) and side walls
    zb_back = H + 0.5 - 0.3 * (0.7 / 2.3) - 0.1
    for oy, fy, g in ((y1, 1, 0.025), (y1 - 0.06, -1, 0.02)):
        P.append(vplank_panel("wall_b", (0, oy, 0), facing_rot((0, fy)), x0, x1, lambda xx: 0.14,
                              lambda xx: zb_back, 0.3, g, M['wood']))
    y_front, z_front = -0.95, H - 0.2
    y_back, z_back = y1 + 0.3, H + 0.5
    slope = (z_back - z_front) / (y_back - y_front)
    under = lambda y: z_front + slope * (y - y_front) - 0.07        # just below the canvas
    for sx in (-1, 1):
        for off, fx, g in ((0.0, sx, 0.025), (-0.06 * sx, -sx, 0.02)):
            yc = (y0 + y1) / 2
            P.append(vplank_panel("wall_s", (sx * x1 + off, yc, 0), facing_rot((fx, 0)), -0.7, 0.7,
                                  lambda xx: 0.14, (lambda xx, fx=fx, yc=yc: under(yc + xx * fx)), 0.28, g, M['wood']))
    for x in (x0, x1):
        for y in (y0, y1):
            h = under(y) - 0.02
            P.append(bx("post", (0.13, 0.13, h), (x, y, h / 2), M['wood'], 0.03, 1))
    # awning roof (back high -> front low) on two front poles
    striped_awning(P, M, x0 - 0.3, x1 + 0.3, y_back, z_back, y_front, z_front)
    for sx in (-1, 1):
        P.append(bx("pole", (0.1, 0.1, z_front - 0.06), (sx * (x1 + 0.12), y_front + 0.1, (z_front - 0.06) / 2),
                    M['wood'], 0.025, 1))
    P.append(beam("awn_beam", (x0 - 0.3, y_front + 0.1, z_front - 0.1), (x1 + 0.3, y_front + 0.1, z_front - 0.1),
                  0.1, 0.1, Z, M['wood'], 0.02))
    # hanging snack sachet strips (renteng) along the front beam
    for i, x in enumerate([x0 + 0.1 + k * 0.26 for k in range(14)]):
        mm = (M['red'], M['white'], M['glass'])[i % 3]
        P.append(bx("sachet", (0.16, 0.02, 0.46), (x, y_front + 0.1, z_front - 0.42), mm, 0))
    # counter: plank front, white top, jars + snack tray
    P.append(vplank_panel("counter_f", (0, y0 - 0.02, 0), 0.0, x0 + 0.05, x1 - 0.05, lambda xx: 0.14,
                          lambda xx: 0.98, 0.3, 0.02, M['wood']))
    P.append(bx("counter_top", (x1 - x0 + 0.02, 0.56, 0.07), (0, y0 + 0.18, 1.0), M['white'], 0.025, 1))
    for x in (-1.3, -0.85, -0.4):
        P.append(add_cyl("jar", 0.16, 0.34, loc=(x, y0 + 0.14, 1.2), material=M['glass'], verts=10))
        P.append(add_cyl("lid", 0.175, 0.07, loc=(x, y0 + 0.14, 1.4), material=M['red'], verts=10))
    P.append(bx("tray", (0.7, 0.34, 0.08), (0.85, y0 + 0.16, 1.08), M['red'], 0.02, 1))
    for i in range(6):
        P.append(bx("snack", (0.09, 0.07, 0.15), (0.6 + i * 0.1, y0 + 0.16, 1.18), (M['white'], M['glass'])[i % 2], 0))
    # shelves with bottles on the back wall
    rnd = random.Random(7)
    for z in (1.25, 1.75):
        P.append(bx("shelf", (x1 - x0 - 0.2, 0.3, 0.05), (0, y1 - 0.23, z), M['wood'], 0.015, 1))
        x = x0 + 0.3
        while x < x1 - 0.25:
            mm = [M['glass'], M['red'], M['white']][rnd.randrange(3)]
            hgt = rnd.choice((0.26, 0.3, 0.2))
            r = 0.055 if hgt > 0.22 else 0.07
            P.append(add_cyl("bottle", r, hgt, loc=(x, y1 - 0.22, z + 0.025 + hgt / 2), material=mm, verts=6))
            x += rnd.uniform(0.17, 0.26)
    # drink crate + red plastic stools in front
    P.append(bx("crate", (0.5, 0.36, 0.3), (1.4, -0.75, 0.29), M['red'], 0.03, 1))
    for i in range(4):
        P.append(add_cyl("crate_btl", 0.045, 0.16, loc=(1.24 + i * 0.105, -0.75, 0.5), material=M['glass'], verts=6))
    for x, y in ((-1.05, -1.4), (0.05, -1.5), (-0.5, -1.95)):
        PR.plastic_stool(P, M['red'], x, y)
    finish(root, P, name)
    center_root(root)
    return root


def build_toko():
    """Village co-op shop (koperasi): cream plank walls with a teal dado, teal tile roof with a shop
    sign on the front slope, glass double door, fertiliser sacks and seedling polybags out front."""
    name = "toko"
    root = empty(name)
    M = dict(roof=mat("M_Roof", "#3a9180"), wall=mat("M_Wall", "#f4e8cc"), trim=mat("M_Wood", "#6e4a2c"),
             glass=glass_mat())
    P = []
    FT = 0.3
    WZ = FT + 2.15
    x0, x1, y0, y1 = -2.2, 2.2, -0.45, 1.55
    ty = -1.8
    P.append(bx("plinth", (x1 - x0 + 0.3, y1 - ty + 0.12, FT), (0, (y1 + ty) / 2 + 0.06, FT / 2), M['wall'], 0.05, 2))
    poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    P.append(siding_ring("dado", poly, FT, FT + 0.55, 2, 0.03, M['roof']))
    P.append(siding_ring("walls", poly, FT + 0.55, WZ, 5, 0.026, M['wall']))
    for x, y in poly:
        P.append(bx("corner", (0.16, 0.16, WZ - FT + 0.04), (x, y, (FT + WZ) / 2), M['trim'], 0.035, 1))
    # teal tile roof (ridge along X)
    pitch = math.radians(30)
    t = math.tan(pitch)
    yc = (y0 + y1) / 2
    zr = WZ + 1.0 * t + 0.12
    gable_roof(P, M, (-2.65, yc, zr), (2.65, yc, zr), 1.45, pitch, 4)
    for sx in (-1, 1):
        top = lambda xx: max(WZ, zr - 0.14 - abs(xx) * t)
        P.append(vplank_panel("gable", (sx * x1, yc, 0), facing_rot((sx, 0)), -1.0, 1.0, lambda xx: WZ - 0.05, top,
                              0.28, 0.022, M['wall'], breaks=(0.0,)))
    # shop sign standing on the front slope (blank face = child "SignBoard")
    sw, sh = 2.7, 0.62
    sy = y0 + 0.2
    sz = WZ + 0.62
    for sg in (-1, 1):
        P.append(bx("sign_post", (0.12, 0.12, 0.9), (sg * (sw / 2 - 0.3), sy + 0.1, WZ + 0.3), M['trim'], 0.03, 1))
    P.append(bx("sign_back", (sw + 0.16, 0.1, sh + 0.16), (0, sy + 0.07, sz), M['roof'], 0.04, 2))
    # facade: glass double door, two windows
    dw = 1.3
    P.append(rect_ring("door_frame", (0, y0, 0), 0.0, FT + 0.95, dw, 1.9, 0.12, 0.1, M['trim']))
    for sg in (-1, 1):
        P.append(bx("door_leaf", (dw / 2 - 0.02, 0.06, 1.88), (sg * dw / 4, y0 - 0.01, FT + 0.95), M['trim'], 0.02, 1))
        P.append(bx("door_glass", (dw / 2 - 0.2, 0.03, 1.2), (sg * dw / 4, y0 - 0.05, FT + 1.15), M['glass'], 0))
        window(P, M, (sg * 1.55, y0, 0), 0.0, FT + 1.2, w=0.7, h=0.8)
        window(P, M, (sg * x1, yc, 0), facing_rot((sg, 0)), FT + 1.2)
    steps(P, M, 0.0, ty + 0.12, 1.4, FT, 1, depth=0.3, m='wall')
    # wares out front: sacks on a pallet (left), seedlings in polybags (right)
    P.append(bx("pallet", (1.3, 0.95, 0.12), (-1.35, -1.15, FT + 0.06), M['trim'], 0.02, 1))
    k = 0
    for layer, (n, zz) in enumerate(((3, FT + 0.12), (2, FT + 0.12 + 0.19))):
        for i in range(n):
            xx = -1.35 + (i - (n - 1) / 2) * 0.42
            P.append(PR.sack("sack", M['wall'], M['roof'], loc=(xx, -1.15, zz), rotz=math.pi / 2 + (k % 2) * 0.12 - 0.06,
                             lo=True, seed=k))
            k += 1
    P.append(PR.sack("sack", M['wall'], M['roof'], loc=(-0.45, -1.35, FT), rotz=0.3, lo=True, seed=9))
    for i in range(3):
        for j in range(2):
            PR.polybag(P, M['trim'], M['roof'], (0.75 + i * 0.4, -1.45 + j * 0.42, FT), seed=i * 3 + j, size=0.9)
    finish(root, P, name)
    sign = board_with_uv("SignBoard", sw, sh, 0.05, M['wall'], (0, sy, sz))
    sign.parent = root
    center_root(root)
    return root


def shed_roof(P, M, O, down, along, x0, x1, plan, pitch, rows, tile='roof', lip=None, trim='trim', tile_kw=None,
              barge=True, fascia=True, back=True, wear=None):
    """Mono-pitch (lean-to) roof starting at high edge point O, falling along `down`."""
    Ov, ex, ev, en = slope_frame(O, down, along, pitch)
    vl = plan / math.cos(pitch)
    v, f, k = [], [], []
    if wear is None:
        wear = new_wear('zinc' if tile_kw else 'clay', seed=_seed(*O))
    tile_slope(v, f, Ov, ex, ev, en, vl, lambda s_: (x0, x1), rows, kinds=k, wear=wear, **(tile_kw or {}))
    P.append(roof_mesh("roof_tiles", v, f, k, M[tile], M[lip] if lip else None, wear=wear))
    if barge:
        for x in (x0 - 0.04, x1 + 0.04):
            P.append(beam("barge", Ov + ex * x + ev * -0.06 + en * 0.02, Ov + ex * x + ev * (vl + 0.03) + en * 0.02,
                          0.1, 0.2, en, M[trim], 0.03))
    if fascia:
        e = Ov + ev * vl
        P.append(beam("fascia", e + ex * (x0 - 0.09), e + ex * (x1 + 0.09), 0.1, 0.18, en, M[trim], 0.03))
    if back:
        P.append(beam("fascia", Ov + ex * (x0 - 0.09), Ov + ex * (x1 + 0.09), 0.1, 0.18, en, M[trim], 0.03))
    return Ov, ex, ev, en, vl


def box_walls(P, m, x0, x1, y0, y1, z0, z1, pw=0.3, g=0.04, sides=(True, True, True, True)):
    """Four ribbed (corrugated / vertical plank) walls around a rectangle: front, back, left, right."""
    specs = (((x0 + x1) / 2, y0, 0, -1, (x1 - x0) / 2), ((x0 + x1) / 2, y1, 0, 1, (x1 - x0) / 2),
             (x0, (y0 + y1) / 2, -1, 0, (y1 - y0) / 2), (x1, (y0 + y1) / 2, 1, 0, (y1 - y0) / 2))
    for on, (ox, oy, fx, fy, half) in zip(sides, specs):
        if on:
            P.append(vplank_panel("wall", (ox, oy, 0), facing_rot((fx, fy)), -half, half, lambda xx: z0,
                                  lambda xx: z1, pw, g, m))


def wall_wear(parts, seed, rust=0.55, grime=0.22, per_m=0.9):
    """Env fix round: rust streaks running down from the top of ribbed metal walls (under the eaves)
    and a grimy lower edge, on every wall panel in `parts` (the pabrik read as flat untextured boxes)."""
    rnd = random.Random(seed)
    for o in parts:
        me = o.data
        if not len(me.vertices):
            continue
        zs = [v.co.z for v in me.vertices]
        z0, z1 = min(zs), max(zs)
        h = max(z1 - z0, 1e-3)
        xs = [v.co.x + v.co.y for v in me.vertices]
        st = _streaks(rnd, min(xs), max(xs), per_m, 0.08, 0.3, 0.35, 1.0)
        wattr(o, "w_rust", lambda c: rust * _streak_val(st, c.x + c.y) * (0.25 + 0.75 * ((c.z - z0) / h) ** 0.6))
        wattr(o, "w_down", lambda c: 1.0, "POINT")
        wattr(o, "w_shadev", [-grime * (1.0 - min(1.0, (v.co.z - z0) / (0.45 * h))) ** 2 + rnd.uniform(-0.04, 0.03)
                              for v in me.vertices], "POINT")


def build_pabrik():
    """Cute little palm-oil mill (PKS): ribbed metal press hall + boiler house, red/white chimney,
    two oil tanks with pipes, office box, and a loading ramp + dock with a hopper at the front (-Y)."""
    name = "pabrik"
    root = empty(name)
    # (env fix round: warm weathered zinc instead of the cold pale blue-grey, with rust and grime)
    M = dict(metal=mat("M_Metal", "#c3bfae"), dark=mat("M_MetalDark", "#6f7672"), red=mat("M_Red", "red"),
             white=mat("M_White", "white"))
    P = []
    ZK = dict(period=0.5, amp=0.06, step=0.04, cham=0.06, thick=0.07)
    # --- main press hall
    hx0, hx1, hy0, hy1, hz = -4.4, 2.0, -1.5, 3.6, 4.0
    P.append(bx("hall_base", (hx1 - hx0 + 0.2, hy1 - hy0 + 0.2, 0.3), ((hx0 + hx1) / 2, (hy0 + hy1) / 2, 0.15),
                M['dark'], 0.05, 1))
    n0 = len(P)
    box_walls(P, M['metal'], hx0, hx1, hy0, hy1, 0.3, hz, pw=0.55)
    wall_wear(P[n0:], 11)
    for x in (hx0, hx1):
        for y in (hy0, hy1):
            P.append(bx("hall_corner", (0.22, 0.22, hz), (x, y, hz / 2), M['white'], 0.04, 1))
    pitch = math.radians(20)
    t = math.tan(pitch)
    hyc = (hy0 + hy1) / 2
    half = (hy1 - hy0) / 2
    zr = hz + half * t + 0.05
    gable_roof(P, M, (hx0 - 0.35, hyc, zr), (hx1 + 0.35, hyc, zr), half + 0.45, pitch, 2, tile='dark', lip=None,
               trim='white', tile_kw=ZK, ridge_r=0.16, ridge_verts=4, ridge_mat='red', balls=False, barge_h=0.22)
    for sx, xx in ((-1, hx0), (1, hx1)):
        top = lambda q: max(hz, zr - 0.1 - abs(q) * t)
        P.append(vplank_panel("gable", (xx, hyc, 0), facing_rot((sx, 0)), -half, half, lambda q: hz - 0.05, top,
                              0.5, 0.04, M['metal'], breaks=(0.0,)))
    # roof vents (little cowls) on the hall roof
    for x in (-2.8, -0.6):
        P.append(add_cyl("vent", 0.28, 0.7, loc=(x, hyc + 0.9, zr - 0.9 * t + 0.25), material=M['metal'], verts=8))
        P.append(add_cyl("vent_cap", 0.42, 0.22, loc=(x, hyc + 0.9, zr - 0.9 * t + 0.7), material=M['red'], verts=8,
                         radius2=0.12))
    # clerestory windows + big roller doors
    for x in (-3.6, -2.2, 0.6):
        P.append(bx("win", (0.9, 0.08, 0.55), (x, hy0 - 0.03, 3.25), M['dark'], 0))
    P.append(bx("roller", (2.0, 0.1, 2.3), (-1.3, hy0 - 0.04, 1.3 + 1.15), M['red'], 0.03, 1))
    P.append(bx("roller_box", (2.3, 0.3, 0.3), (-1.3, hy0 - 0.12, 3.75), M['dark'], 0.04, 1))
    P.append(bx("side_door", (0.1, 1.8, 2.4), (hx0 - 0.04, 1.6, 1.5), M['red'], 0.03, 1))
    # --- boiler house (lean-to against the hall)
    bx0, bx1, by0, by1, bz = hx1, 5.0, 0.4, 3.6, 3.0
    P.append(bx("boiler_base", (bx1 - bx0 + 0.1, by1 - by0 + 0.2, 0.3), ((bx0 + bx1) / 2 + 0.05, (by0 + by1) / 2, 0.15),
                M['dark'], 0.05, 1))
    n0 = len(P)
    box_walls(P, M['metal'], bx0, bx1, by0, by1, 0.3, bz, pw=0.46, sides=(True, True, False, True))
    wall_wear(P[n0:], 12, rust=0.7)
    for x in (bx1,):
        for y in (by0, by1):
            P.append(bx("boiler_corner", (0.2, 0.2, bz), (x, y, bz / 2), M['white'], 0.04, 1))
    bp = math.radians(14)
    shed_roof(P, M, (bx0 + 0.05, (by0 + by1) / 2, bz + (bx1 - bx0) * math.tan(bp) + 0.06), (1, 0, 0), (0, 1, 0),
              -(by1 - by0) / 2 - 0.3, (by1 - by0) / 2 + 0.3, bx1 - bx0 + 0.35, bp, 2, tile='metal', trim='white',
              tile_kw=ZK, back=False)
    P.append(bx("boiler_door", (1.1, 0.1, 1.9), (3.6, by0 - 0.04, 1.25), M['dark'], 0.03, 1))
    # --- chimney (red / white bands) on a plinth behind the boiler house
    cx, cy = 4.6, 4.35
    P.append(bx("chim_base", (1.4, 1.4, 0.9), (cx, cy, 0.45), M['dark'], 0.06, 2))
    nb, nv = 7, 12
    zc0, zc1 = 0.9, 10.2
    r0, r1 = 0.55, 0.36
    cv, cf, cm = [], [], []                      # one tapered tube, red / white bands, no hidden band caps
    for i in range(nb + 1):
        z_ = zc0 + (zc1 - zc0) * i / nb
        r_ = r0 + (r1 - r0) * i / nb
        cv += [(cx + r_ * math.cos(2 * math.pi * k / nv), cy + r_ * math.sin(2 * math.pi * k / nv), z_) for k in range(nv)]
    for i in range(nb):
        for k in range(nv):
            a, b = i * nv + k, i * nv + (k + 1) % nv
            cf.append((a, b, b + nv, a + nv))
            cm.append(1 if i % 2 else 0)
    chim = mk_multi("chim", cv, cf, [M['white'], M['red']], cm)
    fix_normals(chim)
    smooth_angle(chim, 40)
    P.append(chim)
    P.append(add_cyl("chim_lip", r1 + 0.1, 0.25, loc=(cx, cy, zc1 + 0.1), material=M['dark'], verts=10))
    P.append(rod("flue", (bx1 - 0.6, 3.3, 2.4), (cx, cy - 0.3, 2.4), 0.18, M['dark'], 6))
    # --- oil storage tanks + pipes
    for (tx, ty, tr, th) in ((4.5, -2.6, 1.15, 2.7), (6.25, -0.55, 0.72, 2.2)):
        P.append(add_cyl("tank", tr, th, loc=(tx, ty, th / 2), material=M['white'], verts=14))
        P.append(add_cyl("tank_band", tr + 0.03, 0.3, loc=(tx, ty, th * 0.62), material=M['red'], verts=14))
        P.append(add_cyl("tank_roof", tr + 0.06, tr * 0.45, loc=(tx, ty, th + tr * 0.22), material=M['metal'], verts=14,
                         radius2=0.12))
        P.append(bx("tank_ladder", (0.3, 0.06, th), (tx - tr * 0.7, ty - tr * 0.72, th / 2), M['dark'], 0,
                    rotz=math.radians(-45)))
    pz = 3.3
    pts = [(hx1, -0.8, pz), (4.5, -0.8, pz), (4.5, -2.0, pz), (4.5, -2.0, 2.9)]
    for p1, p2 in zip(pts, pts[1:]):
        P.append(rod("pipe", p1, p2, 0.13, M['red'], 8))
    for p in pts[1:3]:
        P.append(add_sphere("elbow", 0.17, loc=p, material=M['red'], segments=8, rings=3))
    P.append(rod("pipe2", (5.0, 1.2, 1.4), (6.25, 1.2, 1.4), 0.1, M['dark'], 8))
    P.append(rod("pipe2", (6.25, 1.2, 1.4), (6.25, 0.05, 1.4), 0.1, M['dark'], 8))
    P.append(rod("pipe_leg", (4.5, -0.8, 0), (4.5, -0.8, pz), 0.07, M['dark'], 6))
    P.append(rod("pipe_leg", (3.3, -0.8, 0), (3.3, -0.8, pz), 0.07, M['dark'], 6))
    # --- office box (front-left)
    ox0, ox1, oy0, oy1, oz = -6.9, -4.9, -4.7, -2.5, 2.5
    P.append(bx("office", (ox1 - ox0, oy1 - oy0, oz), ((ox0 + ox1) / 2, (oy0 + oy1) / 2, oz / 2), M['white'], 0.06, 2))
    P.append(bx("office_roof", (ox1 - ox0 + 0.5, oy1 - oy0 + 0.5, 0.22), ((ox0 + ox1) / 2, (oy0 + oy1) / 2 - 0.05,
                                                                            oz + 0.08), M['red'], 0.06, 2))
    P.append(bx("office_door", (0.8, 0.08, 1.55), (-5.5, oy0 - 0.02, 0.8), M['dark'], 0.03, 1))
    P.append(bx("office_win", (0.7, 0.08, 0.6), (-6.4, oy0 - 0.02, 1.45), M['dark'], 0))
    P.append(bx("office_win", (0.08, 0.8, 0.6), (ox1 + 0.02, -3.6, 1.45), M['dark'], 0))
    P.append(bx("office_ac", (0.5, 0.3, 0.35), (ox0 + 0.5, oy1 + 0.1, 1.9), M['metal'], 0.04, 1))
    P.append(bx("office_step", (1.0, 0.4, 0.12), (-5.5, oy0 - 0.2, 0.06), M['dark'], 0.03, 1))
    # --- loading dock + ramp + hopper (front, where the fruit trucks tip their load)
    dx0, dx1, dy0, dz = -4.4, 0.8, -3.1, 1.25
    P.append(bx("dock", (dx1 - dx0, hy0 - dy0, dz), ((dx0 + dx1) / 2, (dy0 + hy0) / 2, dz / 2), M['metal'], 0.05, 2))
    rx0, rx1, ry0 = -4.3, -2.5, -5.0
    wedge = [(rx0, ry0, 0.0), (rx1, ry0, 0.0), (rx1, dy0, 0.0), (rx0, dy0, 0.0), (rx0, dy0, dz), (rx1, dy0, dz)]
    o = mesh_from_data("ramp", wedge, [(0, 1, 2, 3), (0, 4, 5, 1), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)], M['dark'])
    fix_normals(o)
    bevel_obj(o, 0.04, 1)
    P.append(o)
    for x in (rx0 - 0.06, rx1 + 0.06):
        P.append(beam("curb", (x, ry0 + 0.05, 0.1), (x, dy0, dz + 0.1), 0.14, 0.22, Z, M['red'], 0.03))
    # hopper: inverted truncated pyramid, red outside, dark inside, on the dock
    hcx, hcy = -0.9, -2.3
    top_h, bot_h, z_b, z_t = 0.95, 0.35, dz, dz + 1.15
    outer = [(hcx + sx * top_h, hcy + sy * top_h, z_t) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    lower = [(hcx + sx * bot_h, hcy + sy * bot_h, z_b) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    inner = [(hcx + sx * (top_h - 0.1), hcy + sy * (top_h - 0.1), z_t) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    deep = [(hcx + sx * (bot_h - 0.08), hcy + sy * (bot_h - 0.08), z_b + 0.25) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    vs = outer + lower + inner + deep
    fs, fm = [], []
    for i in range(4):
        j = (i + 1) % 4
        fs.append((i, j, 4 + j, 4 + i)); fm.append(0)                 # outer slopes
        fs.append((8 + i, 8 + j, j, i)); fm.append(0)                 # rim
        fs.append((12 + i, 12 + j, 8 + j, 8 + i)); fm.append(1)       # inner slopes
    fs.append((12, 13, 14, 15)); fm.append(1)
    fs.append((7, 6, 5, 4)); fm.append(0)
    hop = mk_multi("hopper", vs, fs, [M['red'], M['dark']], fm)
    fix_normals(hop)
    P.append(hop)
    P.append(rod("chute", (hcx, hcy + 0.2, z_b + 0.3), (hcx, hy0 - 0.02, 2.6), 0.28, M['dark'], 8))
    # dock railing
    for (p1, p2) in (((dx0 + 0.06, dy0 + 0.06), (rx1 + 0.1, dy0 + 0.06)), ((0.0, dy0 + 0.06), (dx1 - 0.06, dy0 + 0.06)),
                     ((dx1 - 0.06, dy0 + 0.06), (dx1 - 0.06, hy0 - 0.1))):
        a3, b3 = Vector((p1[0], p1[1], dz)), Vector((p2[0], p2[1], dz))
        P.append(beam("dock_rail", a3 + Z * 0.8, b3 + Z * 0.8, 0.07, 0.07, Z, M['red'], 0.02))
        for p in (a3, b3, (a3 + b3) / 2):
            P.append(bx("dock_post", (0.07, 0.07, 0.8), (p.x, p.y, dz + 0.4), M['red'], 0))
    finish(root, P, name)
    center_root(root)
    return root


def build_pos_calo():
    """The broker's roadside post: sagging blue tarp on four bamboo poles, upturned crate table with
    papers and a cash tin, two monobloc chairs, a little cardboard sign."""
    name = "pos_calo"
    root = empty(name)
    M = dict(tarp=mat("M_Tarp", "#3f7fc4"), wood=mat("M_Bamboo", "#c8a15e"), plastic=mat("M_Plastic", "#6db36f"),
             paper=mat("M_Paper", "#f6f1e7"))
    P = []
    hx, hy = 1.35, 1.25
    zf, zb = 2.3, 1.95
    poles = [(-hx, -hy, zf), (hx, -hy, zf), (hx, hy, zb), (-hx, hy, zb)]
    for x, y, z in poles:
        P.append(add_cyl("pole", 0.055, z + 0.12, loc=(x, y, (z + 0.12) / 2), material=M['wood'], verts=6))
        for k in range(1, 3):
            P.append(add_cyl("node", 0.068, 0.05, loc=(x, y, z * k / 3), material=M['wood'], verts=6))
    # tarp: sagging grid, corners tied a little below the pole tops, overhang droops
    n = 6
    ext = 0.25
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = i / n, j / n
            x = -hx - ext + (2 * hx + 2 * ext) * u
            y = -hy - ext + (2 * hy + 2 * ext) * v
            base = zf + (zb - zf) * v
            cu, cv = min(1.0, abs(x) / hx), min(1.0, abs(y) / hy)
            sag = 0.2 * (1 - cu ** 2) * (1 - cv ** 2)
            droop = 0.28 * max(0.0, abs(x) - hx) / ext + 0.28 * max(0.0, abs(y) - hy) / ext
            verts.append((x, y, base - sag - droop + 0.03 * math.sin(i * 1.7 + j)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    top = mesh_from_data("tarp", verts, faces, M['tarp'])
    shade_smooth(top)
    P.append(top)
    under = mesh_from_data("tarp_under", [(x, y, z - 0.02) for x, y, z in verts], [f[::-1] for f in faces], M['tarp'])
    shade_smooth(under)
    P.append(under)
    # crate table (upside down) + papers + cash tin + glass
    ty = -0.8
    PR.crate_parts(P, M['wood'], M['wood'], loc=(0.0, ty, 0.0), size=(0.8, 0.55, 0.58))
    P.append(bx("paper", (0.28, 0.36, 0.012), (-0.15, ty - 0.05, 0.595), M['paper'], 0, rotz=0.25))
    P.append(bx("paper", (0.28, 0.36, 0.012), (-0.05, ty + 0.03, 0.607), M['paper'], 0, rotz=-0.15))
    P.append(bx("cash_tin", (0.26, 0.18, 0.1), (0.24, ty + 0.05, 0.64), M['plastic'], 0.02, 1, rotz=0.1))
    P.append(add_cyl("glass", 0.045, 0.12, loc=(0.25, ty - 0.17, 0.65), material=M['paper'], verts=8))
    # chairs: broker behind the table, client in front
    PR.plastic_chair(P, M['plastic'], 0.05, ty + 0.7, rotz=math.pi + 0.1)
    PR.plastic_chair(P, M['plastic'], -0.5, ty - 0.75, rotz=0.4)
    # cardboard sign on a stick
    P.append(add_cyl("sign_stick", 0.03, 1.1, loc=(1.0, -1.5, 0.55), material=M['wood'], verts=5))
    P.append(bx("sign", (0.6, 0.04, 0.42), (1.0, -1.53, 1.0), M['paper'], 0.01, 1, rotz=-0.12))
    # sack of stuff and a thermos
    P.append(add_cyl("thermos", 0.09, 0.34, loc=(0.75, 0.35, 0.17), material=M['tarp'], verts=8))
    finish(root, P, name)
    center_root(root)
    return root


def build_dermaga():
    """Wooden jetty 10 m x 2.5 m on posts; land end at the origin, runs along +Y, deck top at z = 0.3.
    Posts go down to z = -1.2 so they reach into the water."""
    name = "dermaga"
    root = empty(name)
    M = dict(deck=mat("M_Deck", "wood_light"), post=mat("M_Post", "wood_dark"), rope=mat("M_Rope", "straw"))
    P = []
    rnd = random.Random(3)
    L, W, top = 10.0, 2.5, 0.3
    th = 0.07
    pitch_ = 0.3
    n = int(L / pitch_)
    for i in range(n):
        y = 0.15 + i * (L - 0.3) / (n - 1)
        wl = W + rnd.uniform(-0.12, 0.06)
        xo = rnd.uniform(-0.05, 0.05)
        P.append(bx("plank", (wl, 0.26, th), (xo, y, top - th / 2 + rnd.uniform(-0.008, 0.008)), M['deck'], 0.02, 1,
                    rotz=rnd.uniform(-0.025, 0.025)))
    for sx in (-1, 1):
        P.append(beam("stringer", (sx * 1.0, 0.0, top - th - 0.08), (sx * 1.0, L, top - th - 0.08), 0.14, 0.16, Z,
                      M['post'], 0.02))
    ys = [0.35, 2.3, 4.25, 6.2, 8.15, L - 0.25]
    for j, y in enumerate(ys):
        for sx in (-1, 1):
            tall = j == len(ys) - 1 or j == 0
            ztop = top + (0.42 if tall else 0.0) - (0.0 if tall else th + 0.02)
            P.append(add_cyl("post", 0.12, ztop + 1.2, loc=(sx * 1.2, y, (ztop - 1.2) / 2), material=M['post'], verts=8))
            if tall:
                P.append(add_cyl("post_cap", 0.14, 0.06, loc=(sx * 1.2, y, ztop + 0.02), material=M['post'], verts=8))
        P.append(beam("cross", (-1.3, y, top - th - 0.2), (1.3, y, top - th - 0.2), 0.12, 0.14, Z, M['post'], 0.02))
    # rope wraps on the end bollards + a rope coil on the deck
    for sx in (-1, 1):
        P.append(add_cyl("wrap", 0.145, 0.12, loc=(sx * 1.2, L - 0.25, top + 0.22), material=M['rope'], verts=8))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.055, major_segments=10, minor_segments=5,
                                     location=(0.6, L - 0.9, top + 0.05))
    coil = C._active()
    coil.name = "coil"
    set_mat(coil, M['rope'])
    shade_smooth(coil)
    P.append(coil)
    P.append(add_cyl("coil_in", 0.2, 0.05, loc=(0.6, L - 0.9, top + 0.1), material=M['rope'], verts=10))
    # ladder down to the water on the right side near the end
    for dx in (-0.22, 0.22):
        P.append(beam("ladder_rail", (1.32, L - 1.6 + dx, top + 0.05), (1.32, L - 1.6 + dx, -0.9), 0.06, 0.06, (1, 0, 0),
                      M['post'], 0.0))
    for k in range(4):
        z = top - 0.25 - k * 0.3
        P.append(bx("rung", (0.05, 0.44, 0.05), (1.32, L - 1.6, z), M['deck'], 0))
    # a couple of old tyre fenders
    for y in (3.3, 7.2):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.2, minor_radius=0.07, major_segments=10, minor_segments=5,
                                         location=(-1.32, y, top - 0.25), rotation=(0, math.pi / 2, 0))
        ty = C._active()
        ty.name = "tyre"
        set_mat(ty, M['post'])
        shade_smooth(ty)
        P.append(ty)
    finish(root, P, name)
    center_root(root, keep_y=True, ground=False)
    return root


def build_perahu():
    """Small double-ended wooden fishing boat (~4 m, bow toward -Y) with bright painted stripes."""
    name = "perahu"
    root = empty(name)
    M = dict(hull=mat("M_Hull", "#3f86c4"), red=mat("M_Stripe", "red"), white=mat("M_Paint", "#f6f1e7"),
             wood=mat("M_Wood", "wood"))
    P = []
    L = 4.0
    ns = 12
    thetas = [0, 22, 44, 60, 70, 80, 90]
    band = {0: 1, 1: 0, 2: 0, 3: 2, 4: 1, 5: 0}    # segment (0 = at keel .. 5 = gunwale) -> material
    verts, faces, fm = [], [], []

    def station(t):
        y = -L / 2 + L * t
        e = abs(2 * t - 1)
        b = 0.76 * (1 - e ** 2.2) ** 0.75
        zg = 0.62 + 0.42 * e ** 3.2 + (0.12 * (1 - t) ** 6)
        zk = 0.0 + 0.3 * e ** 3.0
        return y, b, zg, zk

    prof = []
    for i in range(ns + 1):
        t = i / ns
        y, b, zg, zk = station(t)
        ring = []
        for th in [-a for a in reversed(thetas)] + thetas[1:]:
            r = math.radians(th)
            x = b * math.sin(r)
            z = zk + (zg - zk) * (1 - math.cos(r)) ** 0.85
            ring.append((x, y, z))
        prof.append(ring)
    npts = len(prof[0])
    for ring in prof:
        verts += ring
    for i in range(ns):
        for k in range(npts - 1):
            a_ = i * npts + k
            faces.append((a_, a_ + 1, a_ + npts + 1, a_ + npts))
            mid = len(thetas) - 1
            seg = (mid - 1 - k) if k < mid else (k - mid)
            fm.append(band[seg])
    # inner surface (wood) + rim
    base_in = len(verts)
    for ring in prof:
        for (x, y, z) in ring:
            verts.append((x * 0.86, y * 0.975, z))
    for ring_i, ring in enumerate(prof):
        pass
    for i in range(ns):
        for k in range(npts - 1):
            a_ = base_in + i * npts + k
            faces.append((a_ + npts, a_ + npts + 1, a_ + 1, a_))
            mid = len(thetas) - 1
            seg = (mid - 1 - k) if k < mid else (k - mid)
            fm.append(0 if seg >= 4 else 3)          # painted inner top strake, bare wood below
    # raise inner floor: flatten bottom by lifting inner points near the keel
    for i in range(ns + 1):
        for k in range(npts):
            idx = base_in + i * npts + k
            x, y, z = verts[idx]
            zk = station(i / ns)[3]
            verts[idx] = (x, y, max(z, zk + 0.16))
    for i in range(ns):
        for k in (0, npts - 1):
            o_a, o_b = i * npts + k, (i + 1) * npts + k
            i_a, i_b = base_in + o_a, base_in + o_b
            faces.append((o_a, o_b, i_b, i_a) if k == 0 else (o_a, i_a, i_b, o_b))
            fm.append(2)
    hull = mk_multi("hull", verts, faces, [M['hull'], M['red'], M['white'], M['wood']], fm)
    weld(hull, 1e-4)
    fix_normals(hull)
    smooth_angle(hull, 40)
    P.append(hull)
    # stem posts (upswept bow and stern pieces)
    for t, sg in ((0.0, -1), (1.0, 1)):
        y, b, zg, zk = station(t)
        P.append(beam("stem", (0, y - sg * 0.1, zg - 0.35), (0, y + sg * 0.18, zg + 0.28), 0.09, 0.12, (0, -sg, 0.3),
                      M['red'], 0.02))
    # thwarts, a paddle and a fish basket
    for y in (-0.7, 0.55):
        _, b, zg, _ = station((y + L / 2) / L)
        P.append(bx("thwart", (2 * b * 0.97, 0.24, 0.05), (0, y, zg - 0.12), M['wood'], 0.015, 1))
    P.append(beam("paddle", (-0.25, -1.2, 0.42), (0.2, 0.9, 0.6), 0.05, 0.04, Z, M['wood'], 0.0))
    P.append(bx("blade", (0.16, 0.42, 0.03), (0.23, 1.05, 0.61), M['wood'], 0.01, 1, rotz=-0.2))
    P.append(add_cyl("basket", 0.2, 0.22, loc=(0.1, 1.3, 0.33), material=M['white'], verts=8, radius2=0.24))
    finish(root, P, name)
    center_root(root)
    return root


def build_truck():
    """Small cab-over plantation truck (like the target's): cream-white cab with a flat face facing -Y,
    grey chassis, weathered wooden slatted cargo bed. Child `Cargo` = heap of palm fruit bunches in
    the bed (the game toggles it)."""
    name = "truck"
    root = empty(name)
    PAINT, GLASS = "#efeadf", "#9fc1cc"
    M = dict(paint=mat("M_Paint", PAINT), dark=mat("M_Dark", "#3a3431"), wood=mat("M_Wood", "#8f6b45"),
             fruit=mat("M_Fruit", "#e2682c"))
    M['win'] = M['paint']        # glass = paint tinted blue-grey through the vertex colour (4-material budget)
    P = []
    W = 1.78
    # chassis rails, bumpers, fuel tank, mud flaps
    for sx in (-1, 1):
        P.append(bx("rail", (0.16, 4.0, 0.2), (sx * 0.45, 0.05, 0.52), M['dark'], 0.03, 1))
    P.append(bx("bumper_f", (W + 0.06, 0.18, 0.24), (0, -2.1, 0.55), M['dark'], 0.06, 2))
    P.append(bx("bumper_r", (W - 0.1, 0.12, 0.14), (0, 2.1, 0.52), M['dark'], 0.03, 1))
    P.append(add_cyl("tank", 0.2, 0.7, loc=(-0.72, 0.1, 0.5), material=M['paint'], verts=10, rot=(math.pi / 2, 0, 0)))
    wattr(P[-1], "w_shade", -0.25)
    # cab-over cab
    cy0, cy1 = -2.05, -0.82
    P.append(bx("cab", (W, cy1 - cy0, 1.36), (0, (cy0 + cy1) / 2, 1.3), M['paint'], 0.15, 3))
    P.append(bx("cab_roof", (W - 0.18, cy1 - cy0 - 0.2, 0.08), (0, (cy0 + cy1) / 2 + 0.03, 2.0), M['paint'], 0.035, 2))
    P.append(PR.tint_to(bx("windshield", (W - 0.26, 0.06, 0.55), (0, cy0 - 0.005, 1.6), M['win'], 0.03, 1,
                           rot=(math.radians(-6), 0, 0)), GLASS, PAINT))
    P.append(bx("grille", (1.0, 0.06, 0.26), (0, cy0 - 0.01, 0.92), M['dark'], 0.03, 1))
    P.append(bx("face_band", (W - 0.2, 0.04, 0.06), (0, cy0 - 0.01, 1.22), M['dark'], 0.0))
    for sx in (-1, 1):
        P.append(PR.tint_to(add_cyl("headlight", 0.11, 0.06, loc=(sx * 0.66, cy0 - 0.01, 0.92), material=M['win'],
                                    verts=10, rot=(math.pi / 2, 0, 0)), "#fbf1c4", PAINT))
        P.append(bx("indicator", (0.14, 0.05, 0.07), (sx * 0.66, cy0 - 0.01, 1.08), M['fruit'], 0))
        P.append(PR.tint_to(bx("side_win", (0.06, 0.62, 0.48), (sx * (W / 2 + 0.005), -1.6, 1.58), M['win'], 0.03, 1),
                            GLASS, PAINT))
        P.append(bx("door_line", (0.04, 0.03, 0.9), (sx * (W / 2 + 0.005), -1.18, 1.25), M['dark'], 0.0))
        P.append(bx("handle", (0.04, 0.12, 0.035), (sx * (W / 2 + 0.02), -1.32, 1.28), M['dark'], 0))
        P.append(beam("mirror_arm", (sx * (W / 2), -1.95, 1.62), (sx * (W / 2 + 0.2), -2.02, 1.66), 0.04, 0.04, Z,
                      M['dark'], 0))
        P.append(bx("mirror", (0.08, 0.05, 0.26), (sx * (W / 2 + 0.22), -2.02, 1.55), M['dark'], 0))
        P.append(bx("step", (0.14, 0.36, 0.05), (sx * (W / 2 - 0.02), -1.3, 0.5), M['dark'], 0))
    P.append(bx("cab_back", (W - 0.3, 0.08, 1.1), (0, cy1 + 0.02, 1.25), M['dark'], 0.02, 1))
    # wooden cargo bed: floor, slatted sides + stakes, tall headboard, tailgate
    by0, by1, bz = -0.68, 2.05, 0.78
    P.append(bx("bed_floor", (W, by1 - by0, 0.12), (0, (by0 + by1) / 2, bz - 0.06), M['wood'], 0.02, 1))
    for sx in (-1, 1):
        for zz in (0.1, 0.3, 0.5):
            P.append(bx("side_plank", (0.05, by1 - by0, 0.15), (sx * (W / 2 - 0.025), (by0 + by1) / 2, bz + zz + 0.02),
                        M['wood'], 0))
        for y in (by0 + 0.05, (by0 + by1) / 2, by1 - 0.05):
            P.append(bx("stake", (0.09, 0.09, 0.72), (sx * (W / 2 + 0.01), y, bz + 0.3), M['wood'], 0))
    for zz in (0.1, 0.3, 0.5, 0.7, 0.9):
        P.append(bx("head_plank", (W - 0.02, 0.05, 0.15), (0, by0 + 0.02, bz + zz + 0.02), M['wood'], 0))
    for zz in (0.1, 0.3, 0.5):
        P.append(bx("tail_plank", (W - 0.1, 0.05, 0.15), (0, by1 - 0.02, bz + zz + 0.02), M['wood'], 0))
    for sx in (-1, 1):
        P.append(bx("taillight", (0.18, 0.05, 0.1), (sx * 0.66, by1 + 0.07, 0.62), M['fruit'], 0))
        P.append(bx("mudflap", (0.34, 0.03, 0.3), (sx * 0.62, 1.78, 0.32), M['dark'], 0))
    # wheels: chunky tyres, pale hubs
    for wy in (-1.45, 1.2):
        for sx in (-1, 1):
            x = sx * (W / 2 - 0.16)
            ty_ = add_cyl("tyre", 0.39, 0.32, loc=(x, wy, 0.39), material=M['dark'], verts=12, rot=(0, math.pi / 2, 0))
            bevel_obj(ty_, 0.07, 1)
            P.append(ty_)
            P.append(add_cyl("hub", 0.19, 0.08, loc=(x + sx * 0.14, wy, 0.39), material=M['paint'], verts=10,
                             rot=(0, math.pi / 2, 0)))
            wattr(P[-1], "w_shade", -0.3)
    finish(root, P, name)
    # --- cargo: heap of palm fruit bunches in the bed (separate child, game toggles it)
    rnd = random.Random(11)
    CP = []
    # low mound of loose fruit under the bunches so no bed floor shows between them
    nx_, ny_ = 5, 7
    mv, mf = [], []
    for j in range(ny_ + 1):
        for i in range(nx_ + 1):
            u, v = i / nx_, j / ny_
            x = -0.8 + 1.6 * u
            y = by0 + 0.1 + (by1 - by0 - 0.2) * v
            h = 0.28 * math.sin(math.pi * u) ** 0.6 * math.sin(math.pi * v) ** 0.4 + rnd.uniform(-0.03, 0.03)
            mv.append((x, y, bz + 0.02 + max(0.0, h)))
    for j in range(ny_):
        for i in range(nx_):
            q = j * (nx_ + 1) + i
            mf.append((q, q + 1, q + nx_ + 2, q + nx_ + 1))
    mound = mesh_from_data("mound", mv, mf, M['fruit'])
    shade_smooth(mound)
    wattr(mound, "w_shade", -0.5)
    CP.append(mound)
    spots = []
    for y in (-0.3, 0.55, 1.4):
        for x in (-0.5, 0.0, 0.5):
            spots.append((x + rnd.uniform(-0.06, 0.06), y + rnd.uniform(-0.08, 0.08), 0))
    spots += [(-0.25, 0.1, 1), (0.25, 0.95, 1), (-0.15, 1.7, 0.8)]
    for i, (x, y, layer) in enumerate(spots):
        z = bz + 0.08 + layer * 0.34
        CP.append(PR.bunch("tbs", (M['fruit'], M['fruit'], M['dark']), loc=(x, y, z - 0.03),
                           size=1.18 + rnd.uniform(-0.08, 0.08), seed=i, core_tint=("#d24c26", "#e2682c"),
                           rot=(rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 6.28))))
    cargo = join(CP, "Cargo")
    cargo.data.name = "Cargo"
    if not cargo.data.uv_layers:
        cargo.data.uv_layers.new(name="UVMap")    # same vertex format as the body (shared M_Fruit surface)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    cargo.parent = root
    center_root(root)
    return root


# ============================================================ registry / main
BUILDERS = {
    "rumah_a": build_rumah_a,
    "rumah_b": build_rumah_b,
    "rumah_c": build_rumah_c,
    "kantor": build_kantor,
    "warung": build_warung,
    "toko": build_toko,
    "pabrik": build_pabrik,
    "pos_calo": build_pos_calo,
    "dermaga": build_dermaga,
    "perahu": build_perahu,
    "truck": build_truck,
    "gudang": build_gudang,
    "rumah_d": build_rumah_d,
    "rumah_e": build_rumah_e,
    "rumah_f": build_rumah_f,
    "rumah_g": build_rumah_g,
    "jembatan_kayu": build_jembatan_kayu,
    "jembatan_beton": build_jembatan_beton,
}
# weather_bake kwargs per building (default: AO 1 m + a brown dirt band up to 0.45 m)
WEATHER = {
    "dermaga": dict(ground=False, dirt=0.0),
    "perahu": dict(ground=False, dirt=0.0, distance=0.6),
    "truck": dict(dirt=0.6, dirt_h=0.75, distance=0.8),
    "pos_calo": dict(dirt=0.45, dirt_h=0.3, distance=0.8),
    "warung": dict(dirt=0.5, dirt_h=0.4),
    "jembatan_kayu": dict(ground=False, dirt=0.0, distance=0.6),
    "jembatan_beton": dict(ground=False, dirt=0.2, dirt_h=0.3, distance=0.6),
}
ICONS = {
    "truck": lambda root: render_icon(root, "icon_truk", pitch_deg=30, yaw_deg=42, margin=0.86),
    "rumah_a": lambda root: render_icon(root, "icon_rumah", pitch_deg=32, yaw_deg=28, margin=0.84),
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_render = "--no-render" in sys.argv
    names = args or list(BUILDERS)
    for n in names:
        reset_scene()
        root = BUILDERS[n]()
        d = dims(root)
        print(f"[dims] {n}: {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f} m  tris={count_tris(root)}  "
              f"mats={sorted({s.material.name for o in all_descendants(root) if o.type == 'MESH' for s in o.material_slots})}")
        weather_bake(root, **WEATHER.get(n, {}))
        export_glb(root, n)
        preview_vcol(root)          # materials now multiply by Col (previews / icons only)
        if not no_render:
            render_preview(root, n)
            if DEBUG:
                debug_view(root, n + "_game", 55, 0)
        if not no_render and n in ICONS:
            ICONS[n](root)


if __name__ == "__main__":
    main()

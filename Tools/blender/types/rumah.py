"""Rumah kampung: single-storey Jakarta house with a front terrace, hip (limasan) or gable roof,
low front fence and a small kitchen annex at the back."""
TYPE = 'rumah'
ROLES = ['front', 'low', 'fill']

WALLS = ['wall_mint', 'wall_cream', 'wall_peach', 'wall_sky', 'wall_yellow', 'wall_pink', 'wall_lime', 'wall_white']
ROOFS = ['roof_terracotta', 'roof_brown', 'roof_red', 'roof_grey', 'roof_terracotta', 'roof_blue']
FENCES = ['rail_black', 'rail_green', 'rail_white', 'rail_black']
FRAMES = ['window_frame', 'frame_brown', 'window_frame', 'frame_black']


def variants():
    out = []
    widths = [6.0, 7.0, 8.0, 9.0, 6.5, 7.5, 8.5, 10.0]
    for i, w in enumerate(widths):
        out.append({
            'w': w, 'd': 8.0 + (i % 3),
            'wall': WALLS[i % len(WALLS)], 'roof': ROOFS[i % len(ROOFS)],
            'fence': FENCES[i % len(FENCES)], 'frame': FRAMES[i % len(FRAMES)],
            'hip': i % 3 != 1, 'terrace': 1.6 + 0.2 * (i % 2),
        })
    return out


def build(b, v, rng):
    W, D, wall, t = b.W, b.D, v['wall'], v['terrace']
    x0, x1 = -W / 2 + 0.55, W / 2 - 0.55          # walls inset so the 0.5 m roof overhang stays inside the lot
    yb = D - 1.6                                   # kitchen annex behind this line
    hw = 3.0                                       # wall height
    # body + plinth
    b.box(x0, t, 0, x1, yb, hw, wall)
    b.box(x0 - 0.05, t - 0.05, 0, x1 + 0.05, yb + 0.05, 0.35, 'plinth')
    # terrace floor, columns and front wall openings
    b.box(x0, 0.4, 0, x1, t, 0.18, 'tile_floor')
    for xc in (x0 + 0.2, x1 - 0.2):
        b.box(xc - 0.13, 0.55, 0.18, xc + 0.13, 0.81, hw, 'column')
    door_u = x0 + (x1 - x0) * (0.3 if rng.random() < 0.5 else 0.7)
    b.door('front', door_u, 0.95, 2.1, color='door_wood' if rng.random() < 0.6 else 'door_dark', frame=v['frame'], wall=t)
    free = [(x0 + 0.5, door_u - 0.8), (door_u + 0.8, x1 - 0.5)]
    for a, c in free:
        if c - a > 1.2:
            n = 1 if c - a < 3.2 else 2
            for k in range(n):
                uc = a + (c - a) * (k + 0.5) / n
                b.window('front', uc, 1.0, min(1.3, (c - a) / n - 0.4), 1.3, frame=v['frame'], bars=2, wall=t)
    # side windows (seen in the 3/4 street view)
    for side in ('left', 'right'):
        b.window(side, (t + yb) / 2, 1.1, 1.0, 1.1, frame=v['frame'], bars=2, wall=x0 if side == 'left' else x1)
    # back wall: small window + kitchen annex with a lean-to roof
    b.window('back', x0 + 1.4, 1.3, 0.9, 0.9, frame=v['frame'], bars=1, wall=yb)
    ax1 = x0 + (x1 - x0) * 0.62
    b.box(x0, yb, 0, ax1, D - 0.3, 2.4, 'wall_white' if wall != 'wall_white' else 'wall_cream')
    b.door('back', x0 + 0.9, 0.8, 1.9, color='door_dark', frame=v['frame'], wall=D - 0.3)
    b.roof_shed(x0, ax1, yb, D - 0.3, 2.75, 2.35, 'roof_zinc', over=0.25)
    b.ac_unit('back', ax1 + 0.9, 1.6, wall=yb) if rng.random() < 0.5 else None
    # main roof over body + terrace
    if v['hip']:
        b.roof_hip(x0, x1, 0.55, yb, hw, 1.55, v['roof'], over=0.5)
    else:
        b.roof_gable(x0, x1, 0.55, yb, hw, 1.7, v['roof'], gable_color=wall, over=0.5)
    # low front fence with a gate gap in front of the door
    f = v['fence']
    for (a, c) in ((-W / 2 + 0.1, door_u - 0.9), (door_u + 0.9, W / 2 - 0.1)):
        if c - a > 0.3:
            b.box(a, 0.0, 0, c, 0.22, 0.45, 'wall_white' if wall != 'wall_white' else 'concrete')
            b.railing('front', a, c, 0.45, h=0.75, color=f, off=-0.1, post=0.35, wall=0.0)
    # pots on the terrace
    for k in range(rng.randint(1, 3)):
        b.plant_pot(x0 + 0.6 + k * 0.7, 0.9, 0.18, s=0.8)

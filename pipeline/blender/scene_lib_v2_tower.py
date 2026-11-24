"""v2 high-rise builders ("high rise fire": why fire spreads fast in tall buildings, 26 Nov 2026 slot 3).
Registers into scene_lib_v2.V2_BUILDERS.

World: a bright, generic modern city (wide avenues, plaza, towers of glass and stone, trees, traffic). Two
different buildings:
  * HERO tower (hook / outro only): a generic blue-glass tower with a low podium. In the hook only soft grey smoke
    wisps drift from podium level and small fire trucks (blue lights) stand at its base. No flames, nobody at windows.
  * EXPLAINER tower (every explainer beat): a visibly different cream tower with terracotta bands, shown as a clean
    doll-house cutaway (front wall removed): floor slabs, a stair core, two elevator shafts, a duct, offices.
Everything is abstract: heat = orange glow / arrows, smoke = soft grey puffs, nobody in distress. No 3D text.

Builders
  tower_hook        golden-hour skyline, hero tower centre; mode hook (podium smoke + fire trucks) / outro (calm)
  tower_cut         the explainer tower; mode reveal (front wall slides away) / stack (teal shafts, warm arrows up,
                    cool arrows in at the base, a smoke ribbon rises up the stairs and spills onto a high floor) /
                    protect (sprinkler cones, fire doors swing shut, stair fan + air arrows, alarm pulses on cues)
  facade_v2         outside wall: an orange glow hops window to window upwards; then outer panels swing open to
                    show the cladding layer with a rising colour gradient
  ladder_v2         fire truck's ladder extends and stops well short (dotted line to the top); camera moves into
                    the stair core where small firefighter figures climb beside a red standpipe
  corridor_v2       section through three floors: grey smoke rolls along the hallway ceiling and stops at a closed
                    door; the room behind stays clear and bright
  hall_v2           hotel hallway: doors counted towards the lit green stair sign, red ring on the elevator doors,
                    a towel at the foot of a closed door
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import scene_lib as L
import scene_lib_v2 as S
import scene_lib_v2_air as A
import scene_lib_v2_city as C
import scene_lib_v2_storm as ST
from scene_lib import hexc
from scene_lib_v2_winter import set_keys

HERO = (0.0, 0.0)               # hero tower centre
HERO_W, HERO_D, HERO_FL, HERO_FH = 34.0, 30.0, 40, 3.4
EXP = (260.0, 60.0)             # explainer tower centre (front wall at y = EXP.y - EXP_D/2)
EXP_W, EXP_D, EXP_FL, EXP_FH = 32.0, 20.0, 22, 3.6
CORE = {"stair": (-7.5, -2.0), "lift1": (-0.5, 2.0), "lift2": (3.2, 5.7), "duct": (8.5, 10.0)}   # x ranges
CORE_Y = (-2.0, 6.0)            # core depth (local y), front of building at -EXP_D/2

_M = {}
# sight-line plazas (no city blocks): south of the hero tower, around/south of the explainer tower
CLEAR = [(-230.0, 230.0, -560.0, -20.0), (120.0, 420.0, -330.0, 30.0), (280.0, 420.0, -120.0, 140.0)]


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def sock_keys(sock, keys):
    for f, v in keys:
        L.kf_socket(sock, max(1, int(f)), v, "LINEAR")


def glow(name, col, strength=2.0):
    return S.emis(name, hexc(col), strength)


def fade_mat(name, col, peak=3.0):
    m, sock = L.add_mat(name, hexc(col), 0.0)
    return m, sock


def _box(bm, c, s, mi=0):
    return S.bm_box(bm, c, s, mi)


def _cam(ctx, loc, tgt, lens=30, clip=0.5):
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = clip
    cam.data.clip_end = 40000.0
    return cam


def _anc(ctx, name, loc, parent=None):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    S.anchor(ctx, name, e)
    return e


def _keys(ctx, p, keys, lens=30, clip=0.5):
    """keys = [(frame_or_frac, cam, tgt)], frac < 1.01 means a fraction of the shot."""
    T = ctx.frames
    ks = []
    for f, c, t in keys:
        ff = int(round(1 + (T - 1) * f)) if isinstance(f, float) and f <= 1.0 else int(f)
        ks.append((ff, c, t))
    if "cam0" in p:
        ks[0] = (ks[0][0], p["cam0"], p.get("tgt0", ks[0][2]))
    if "cam1" in p:
        ks[-1] = (ks[-1][0], p["cam1"], p.get("tgt1", ks[-1][2]))
    _cam(ctx, ks[0][1], ks[0][2], p.get("lens", lens), clip)
    A._cam_keys(ctx, ks)


# ================================================================ city
def build_city(ctx, p, golden=False, seed=40):
    rng = random.Random(p.get("seed", seed))
    if golden:
        S.daylight(ctx, p.get("sun_az", 120.0), p.get("sun_elev", 13.0), hdri=False, exposure=p.get("exposure", 0.2))
    else:
        S.daylight(ctx, p.get("sun_az", -30.0), 40.0, hdri=True)
    L.fog(p.get("fog", 0.00012), S.HAZE, start=p.get("fog_start", 600.0))
    C.horizon_haze(ctx.scene, lo=-0.005, hi=0.05)
    S.plane_obj("ground", 40000, 40000, (0, 0, -0.05), C.far_ground_mat("tw_far", hexc("8f9a86"), 5.0))
    pave = S.pbr("tw_pave", hexc("c8c2b6"), 0.85, var=0.08, var_scale=0.1)
    road = C.asphalt_mat("tw_road", hexc("4c4f54"))
    S.plane_obj("pave", 3400, 3400, (0, 0, 0.0), pave)
    blk = 120.0
    for k in range(-14, 15):
        S.plane_obj("rx%d" % k, 3400, 18, (0, k * blk - 60.0, 0.03), road)
        S.plane_obj("ry%d" % k, 18, 3400, (k * blk - 60.0, 0, 0.031), road)
    walls = [S.facade_mat("twc_%d" % i, hexc(c), hexc(g), b, 3.4, wf) for i, (c, g, b, wf) in enumerate((
        ("dfe3e6", "3b5a78", 3.0, 0.7), ("c9d2da", "2f4c6b", 2.6, 0.8), ("e9e2d4", "3a4a5a", 3.2, 0.5),
        ("b9c4cf", "466a8c", 2.8, 0.85), ("d8cfc0", "34495e", 3.4, 0.5), ("aab8c6", "28445f", 2.4, 0.9)))]
    roof = S.pbr("twc_roof", hexc("8a8d90"), 0.8, var=0.08)
    bm = bmesh.new()
    n = 0
    keep_out = [(HERO[0], HERO[1], 75.0), (EXP[0], EXP[1], 70.0)]
    for gx in range(-12, 13):
        for gy in range(-12, 13):
            cx, cy = gx * blk, gy * blk
            for qx in (-1, 1):
                for qy in (-1, 1):
                    x, y = cx + qx * 25.0 + rng.uniform(-4, 4), cy + qy * 25.0 + rng.uniform(-4, 4)
                    if any(math.hypot(x - a, y - b) < r for a, b, r in keep_out):
                        continue
                    if any(x0 - 22 < x < x1 + 22 and y0 - 22 < y < y1 + 22 for x0, x1, y0, y1 in CLEAR):
                        continue
                    if rng.random() < 0.18:
                        continue
                    d = math.hypot(x, y) / 900.0
                    h = rng.uniform(18, 50) + math.exp(-d * d) * rng.uniform(20, 150)
                    w, dd = rng.uniform(24, 40), rng.uniform(24, 40)
                    C._fast_box(bm, x, y, 0.0, w, dd, h, 0, rng.randrange(len(walls)))
                    C._fast_box(bm, x, y, h, w + 0.6, dd + 0.6, 1.2, 0, len(walls))
                    n += 1
    S.obj("city", S.mesh_from_bm("city", bm, walls + [roof]))
    tt = S.tree_templates(rng)
    # the sight-line plazas are parks: lawn + trees (not too close to the towers)
    lawn = S.lawn_mat("tw_park", hexc("6f9050"), stripes=False)
    ppts = []
    for k, (x0, x1, y0, y1) in enumerate(CLEAR[:2]):
        S.plane_obj("park%d" % k, x1 - x0 - 30, y1 - y0 - 30, ((x0 + x1) / 2, (y0 + y1) / 2 - 10, 0.06), lawn)
        for _ in range(int((x1 - x0) * (y1 - y0) / 1600)):
            q = (rng.uniform(x0 + 20, x1 - 20), rng.uniform(y0 + 20, y1 - 40))
            if any(math.hypot(q[0] - a, q[1] - b) < r + 15 for a, b, r in keep_out):
                continue
            ppts.append(q)
    S.scatter(tt[:6], ppts, rng, (0.9, 1.3), prefix="ptree")
    pts = []
    for k in range(-14, 15):
        for j in range(-60, 60):
            if rng.random() < 0.45:
                pts.append((k * blk - 60.0 + 12.0, j * 28.0 + rng.uniform(-4, 4)))
    pts = [q for q in pts if not any(math.hypot(q[0] - a, q[1] - b) < r * 0.7 for a, b, r in keep_out)]
    S.scatter(tt[:6], pts, rng, (0.8, 1.1), prefix="stree")
    # traffic on two avenues near the towers
    T = ctx.frames
    v = 11.0 / ctx.fps
    for i in range(26):
        d = 1 if i % 2 == 0 else -1
        y = -60.0 + d * 4.0 + (120.0 if i % 4 >= 2 else 0.0)
        x0 = rng.uniform(-700, 700)
        c = L.make_car("tc%d" % i, loc=(x0, y, 0.05), rot_z=-math.pi / 2 * d, headlights=False, glow=False)
        set_keys(c.obj, "location", [1, T], [(x0, y, 0.05), (x0 + d * v * (T - 1), y, 0.05)], "LINEAR")
    S._repaint_kenney()
    print("[v2 tower] city: %d buildings" % n)
    return rng


def build_hero(ctx):
    """Generic blue-glass tower with white fins + a 4-storey podium (no logo, no name)."""
    glassf = S.facade_mat("hero_glass", hexc("e9eef2"), hexc("4f7ea6"), 2.2, HERO_FH, 0.88)
    podf = S.facade_mat("hero_podium", hexc("d9d4ca"), hexc("3b5268"), 4.0, 4.5, 0.6)
    roof = S.pbr("hero_roof", hexc("9ea3a8"), 0.7, var=0.05)
    hx, hy = HERO
    H = HERO_FL * HERO_FH
    bm = bmesh.new()
    _box(bm, (hx, hy, 9.0), (HERO_W + 26.0, HERO_D + 20.0, 18.0), 1)
    _box(bm, (hx, hy, H / 2), (HERO_W, HERO_D, H), 0)
    _box(bm, (hx, hy, H + 3.0), (HERO_W - 8.0, HERO_D - 8.0, 6.0), 2)
    _box(bm, (hx, hy, 18.3), (HERO_W + 26.6, HERO_D + 20.6, 0.6), 2)
    S.obj("hero", S.mesh_from_bm("hero", bm, [glassf, podf, roof]))
    return H


def fire_trucks(ctx, n=3):
    """Kenney fire trucks parked at the hero tower's base with blinking blue roof lights."""
    hx, hy = HERO
    T = ctx.frames
    out = []
    for k in range(n):
        x = hx - 30.0 + k * 22.0
        y = hy - HERO_D / 2 - 30.0 + (k % 2) * 3.0
        c = L.make_car("ft%d" % k, loc=(x, y, 0.05), rot_z=math.pi / 2 + 0.1 * k, headlights=False, glow=False,
                       model="firetruck", scale=2.0)
        m, sock = L.add_mat("ft_blue%d" % k, hexc("3a7bff"), 0.0)
        bm = bmesh.new()
        _box(bm, (0, 0, 0), (1.6, 0.5, 0.4), 0)
        o = S.obj("ft_light%d" % k, S.mesh_from_bm("ft_light", bm, [m]), (x, y, 5.2))
        o.rotation_euler = (0, 0, math.pi / 2 + 0.1 * k)
        f = 1 + 5 * k
        keys = [(1, 0.0)]
        while f < T + 20:
            keys += [(f, 0.0), (f + 2, 9.0), (f + 7, 9.0), (f + 9, 0.0)]
            f += 18
        sock_keys(sock, keys)
        out.append(c)
    S._repaint_kenney()
    return out


def podium_smoke(ctx, T):
    """Soft grey wisps from podium level only (z 8-18), drifting sideways and fading. No flames."""
    m = ST.cloud_mat("hero_smoke", 0.08, "5f666d")
    rng = random.Random(3)
    hx, hy = HERO
    for k in range(10):
        bl = [(rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-1, 2), rng.uniform(3.0, 5.0), 0.8) for _ in range(5)]
        o = ST.puffs("hsmoke%d" % k, bl, m)
        o.visible_shadow = False
        x = hx + rng.uniform(-24, 24)
        y = hy - HERO_D / 2 - 6.0 + rng.uniform(-2, 2)
        z = rng.uniform(9.0, 16.0)
        ST.loop_move(o, (x, y, z), (x + 30.0 + rng.uniform(0, 12), y - 4.0, z + 12.0), T, 1, 120 + 10 * (k % 3),
                     phase=rng.random(), grow=30)


# ================================================================ explainer tower (cutaway)
def build_explainer(ctx, cut=True, front=False):
    """Cream tower, terracotta bands. Returns dict with root, shaft materials/socks, floors z, front wall obj."""
    ex, ey = EXP
    root = L.link(bpy.data.objects.new("exp", None))
    root.location = (ex, ey, 0.0)
    W, D, H = EXP_W, EXP_D, EXP_FL * EXP_FH
    wall = S.facade_mat("exp_wall", hexc("efe6d6"), hexc("3d5570"), 3.2, EXP_FH, 0.5)
    band = S.pbr("exp_band", hexc("c46a43"), 0.7, var=0.05)
    slab = S.pbr("exp_slab", hexc("9aa0a6"), 0.8, var=0.04)
    inner = S.pbr("exp_inner", hexc("f4efe6"), 0.85, var=0.03)
    floor = S.pbr("exp_floor", hexc("c9b79c"), 0.7, var=0.06, var_scale=2.0)
    part = S.pbr("exp_part", hexc("e3ddd2"), 0.85, var=0.02)
    bm = bmesh.new()
    # back wall + side walls (outer skin with windows), slab edges
    _box(bm, (0, D / 2 - 0.2, H / 2), (W, 0.4, H), 0)
    for sx in (-1, 1):
        _box(bm, (sx * (W / 2 - 0.2), 0, H / 2), (0.4, D, H), 0)
    for k in range(EXP_FL + 1):
        z = k * EXP_FH
        _box(bm, (0, 0, z + 0.2), (W, D, 0.4), 2)
        if k % 4 == 0:
            _box(bm, (0, D / 2 + 0.05, z + 0.5), (W + 0.3, 0.3, 1.0), 1)
            for sx in (-1, 1):
                _box(bm, (sx * (W / 2 + 0.05), 0, z + 0.5), (0.3, D + 0.3, 1.0), 1)
    _box(bm, (0, 0, H + 1.6), (W - 6, D - 6, 3.2), 1)
    S.obj("exp_shell", S.mesh_from_bm("exp_shell", bm, [wall, band, slab]), parent=root)
    # inner faces: floor finish on every slab + inner back wall (light, so the cutaway never reads dark)
    bm = bmesh.new()
    for k in range(EXP_FL):
        z = k * EXP_FH + 0.41
        _box(bm, (0, 0, z), (W - 0.8, D - 0.8, 0.02), 0)
        _box(bm, (0, D / 2 - 0.42, z + EXP_FH / 2), (W - 0.8, 0.04, EXP_FH - 0.4), 1)
    S.obj("exp_inner", S.mesh_from_bm("exp_inner", bm, [floor, inner]), parent=root)
    # partitions (offices) on each side of the core
    bm = bmesh.new()
    rng = random.Random(9)
    for k in range(EXP_FL):
        z = k * EXP_FH + 0.4 + (EXP_FH - 0.4) / 2
        for x in (-12.5, 12.5):
            _box(bm, (x, 2.5, z), (0.15, D - 6.0, EXP_FH - 0.4), 0)
        if k > 0:
            for j in range(2):   # desks
                x = rng.choice((-14.0, -10.5, 11.0, 14.5))
                _box(bm, (x, 4.0 + j * 2.5, k * EXP_FH + 0.4 + 0.38), (1.4, 0.7, 0.05), 1)
    S.obj("exp_part", S.mesh_from_bm("exp_part", bm, [part, S.pbr("desk", hexc("8a6a4a"), 0.6, var=0)]),
          parent=root)
    # core shafts: side + back walls of each shaft (open to the front), coloured sockets for the "teal" cue
    shafts = {}
    for key, (x0, x1) in CORE.items():
        m = S._new_mat("shaft_" + key)
        mat, nt, N, Lk, pr = m
        pr.inputs["Base Color"].default_value = hexc("dfe2e4")
        pr.inputs["Roughness"].default_value = 0.7
        pr.inputs["Emission Color"].default_value = hexc("19c9b4")
        pr.inputs["Emission Strength"].default_value = 0.0
        S._finish(mat, pr.outputs[0], haze=False)
        bm = bmesh.new()
        y0, y1 = CORE_Y
        for x in (x0, x1):
            _box(bm, (x, (y0 + y1) / 2, H / 2), (0.25, y1 - y0, H), 0)
        _box(bm, ((x0 + x1) / 2, y1, H / 2), (x1 - x0, 0.25, H), 0)
        o = S.obj("shaft_" + key, S.mesh_from_bm("shaft_" + key, bm, [mat]), parent=root)
        shafts[key] = (o, pr.inputs["Emission Strength"], ((x0 + x1) / 2, (y0 + y1) / 2))
    # stairs (zigzag flights) in the stair shaft
    x0, x1 = CORE["stair"]
    st = S.pbr("stairs", hexc("b9b3a8"), 0.8, var=0.03)
    bm = bmesh.new()
    for k in range(EXP_FL):
        z = k * EXP_FH + 0.4
        for half in range(2):
            za = z + half * EXP_FH / 2
            xa, xb = (x0 + 0.4, x1 - 1.2) if half == 0 else (x1 - 0.4, x0 + 1.2)
            n = 10
            for i in range(n):
                u = i / float(n)
                _box(bm, (xa + (xb - xa) * u, 0.4 if half == 0 else 3.2, za + EXP_FH / 2 * u),
                     (abs(xb - xa) / n + 0.05, 2.2, 0.18), 0)
            _box(bm, (x1 - 0.6 if half == 0 else x0 + 0.6, 1.8, za + EXP_FH / 2 - 0.05), (1.2, 5.0, 0.18), 0)
    S.obj("stairs", S.mesh_from_bm("stairs", bm, [st]), parent=root)
    # elevator cars
    car = S.pbr("lift_car", hexc("c0c6cc"), 0.35, 0.6, var=0)
    for k, key in enumerate(("lift1", "lift2")):
        a, b = CORE[key]
        bm = bmesh.new()
        _box(bm, (0, 0, 1.3), (b - a - 0.5, 3.0, 2.6), 0)
        S.obj("car_" + key, S.mesh_from_bm("car_" + key, bm, [car]), ((a + b) / 2, 2.0, 0.4 + EXP_FH * (3 + 9 * k)),
              parent=root)
    # ceiling light panels on every floor (self-lit, keeps the cutaway bright)
    lm = glow("ceil_light", "fff4e2", 1.4)
    bm = bmesh.new()
    for k in range(EXP_FL):
        z = (k + 1) * EXP_FH - 0.02
        for x in (-14.0, -10.0, 10.5, 14.5):
            _box(bm, (x, 1.0, z), (2.2, 0.6, 0.04), 0)
    o = S.obj("ceil_lights", S.mesh_from_bm("ceil_lights", bm, [lm]), parent=root)
    o.visible_shadow = False
    out = {"root": root, "shafts": shafts, "H": H}
    if front:
        fw = S.facade_mat("exp_front", hexc("efe6d6"), hexc("3d5570"), 3.2, EXP_FH, 0.5)
        bm = bmesh.new()
        _box(bm, (0, -D / 2 + 0.2, H / 2), (W, 0.4, H), 0)
        for k in range(0, EXP_FL + 1, 4):
            _box(bm, (0, -D / 2 - 0.05, k * EXP_FH + 0.5), (W + 0.3, 0.3, 1.0), 1)
        fo = S.obj("exp_front", S.mesh_from_bm("exp_front", bm, [fw, band]), parent=root)
        out["front"] = fo
    # interior fill light so the cutaway stays bright
    li = A._area("exp_fill", (ex, ey - D / 2 - 30.0, H * 0.5), 40.0, 30000.0, (1.0, 0.97, 0.92))
    li.rotation_euler = (math.radians(90), 0, 0)
    li.data.size_y = H
    li.data.shape = "RECTANGLE"
    return out


def W_(x, y, z):
    return (EXP[0] + x, EXP[1] + y, z)


def cut_cam(ctx, p, mode):
    ex, ey = EXP
    H = EXP_FL * EXP_FH
    if mode == "reveal":
        return [(1, (ex - 70.0, ey - 230.0, 40.0), (ex, ey, 48.0)), (1.0, (ex - 18.0, ey - 150.0, 44.0), (ex, ey, 42.0))]
    return [(1, (ex - 14.0, ey - 128.0, 44.0), (ex, ey, 40.0)), (1.0, (ex - 4.0, ey - 116.0, 42.0), (ex, ey, 39.5))]


# ================================================================ BUILDERS
def b_tower_hook(ctx, p):
    """Golden-hour skyline with the hero tower in the centre. mode hook: soft grey wisps at podium level, fire
    trucks with blue lights at the base. mode outro: calm tower, camera cranes up. Anchors: tower, base."""
    T = ctx.frames
    mode = p.get("mode", "hook")
    build_city(ctx, p, golden=p.get("golden", True))
    H = build_hero(ctx)
    build_explainer(ctx, cut=False, front=True)
    if mode == "hook":
        fire_trucks(ctx)
        podium_smoke(ctx, T)
    hx, hy = HERO
    _anc(ctx, "tower", (hx + HERO_W / 2, hy - HERO_D / 2, H * 0.7))
    _anc(ctx, "base", (hx, hy - HERO_D / 2 - 30.0, 6.0))
    if mode == "hook":
        _keys(ctx, p, [(1, (hx - 120.0, hy - 330.0, 28.0), (hx, hy, 70.0)),
                       (1.0, (hx - 95.0, hy - 270.0, 24.0), (hx, hy, 66.0))])
    else:
        _keys(ctx, p, [(1, (hx - 90.0, hy - 260.0, 22.0), (hx, hy, 64.0)),
                       (1.0, (hx - 160.0, hy - 420.0, 160.0), (hx + 40.0, hy, 60.0))])


def b_tower_cut(ctx, p):
    """The explainer tower as a doll-house cutaway. See module docstring for the modes.
    Anchors: stair, lift, smoke, base, fan, sprinkler, door."""
    T = ctx.frames
    mode = p.get("mode", "reveal")
    build_city(ctx, p)
    build_hero(ctx)
    ex_ = build_explainer(ctx, cut=True, front=(mode == "reveal"))
    root, shafts, H = ex_["root"], ex_["shafts"], ex_["H"]
    D = EXP_D
    yf = -D / 2 - 1.5        # arrows / effects just in front of the cut
    if mode == "reveal":
        f0 = ctx.word_time(p.get("reveal_cue", "so"), 0.12)
        fo = ex_["front"]
        set_keys(fo, "location", [1, f0 + 6, f0 + 40], [(0, 0, 0), (0, 0, 0), (0, -60.0, 0)], "BEZIER")
        set_keys(fo, "scale", [1, f0 + 34, f0 + 35], [(1, 1, 1), (1, 1, 1), (0, 0, 0)], "CONSTANT")
        _anc(ctx, "stair", (sum(CORE["stair"]) / 2, -D / 2, H * 0.55), parent=root)
    elif mode == "stack":
        f_s = ctx.word_time(p.get("shaft_cue", "stairwells"), 0.25)
        f_w = ctx.word_time(p.get("warm_cue", "warm"), 0.45)
        f_k = ctx.word_time(p.get("smoke_cue", "carry"), 0.8)
        for i, key in enumerate(("stair", "lift1", "lift2", "duct")):
            o, sock, c = shafts[key]
            sock_keys(sock, [(1, 0.0), (f_s + 5 * i, 0.0), (f_s + 5 * i + 12, 1.1)])
        am = glow("warm_arrow", "ff9a2a", 2.2)
        bm_ = glow("cool_arrow", "3aa8ff", 2.2)
        for i, key in enumerate(("stair", "lift1", "lift2", "duct")):
            x = sum(CORE[key]) / 2
            for k in range(3):
                a = ST.arrow("up_%s%d" % (key, k), 4.5, 1.4, am, 90.0, parent=root)
                ST.loop_move(a, (x, yf, 6.0), (x, yf, H - 6.0), T, f_w + 4 * i, 110, phase=k / 3.0, grow=10)
        for sx in (-1, 1):
            for k in range(3):
                a = ST.arrow("in%d%d" % (sx, k), 4.0, 1.3, bm_, 0.0 if sx < 0 else 180.0, parent=root)
                ST.loop_move(a, (sx * 24.0, yf, 2.2), (sx * 9.0, yf, 2.2), T, f_w + 6 + 5 * k, 45, phase=k / 3.0,
                             grow=6)
        # smoke ribbon: puffs travel up the stair shaft then spill out onto floor 17
        sm = ST.cloud_mat("tw_smoke", 0.1, "5c6268")
        rng = random.Random(5)
        xs = sum(CORE["stair"]) / 2
        zf = 17 * EXP_FH + 2.2
        for k in range(16):
            bl = [(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.4, 0.4), rng.uniform(0.9, 1.5), 0.8)
                  for _ in range(4)]
            o = ST.puffs("rib%d" % k, bl, sm, parent=root)
            o.visible_shadow = False
            fa = f_k - 40 + 5 * k
            pts = [(xs, -1.0, 3.0), (xs, -1.0, zf), (xs + 6.0 + 1.2 * k, -2.5, zf)]
            fr_ = [1, fa, fa + 50, fa + 75]
            locs = [pts[0], pts[0], pts[1], pts[2]]
            set_keys(o, "location", fr_, locs, "LINEAR")
            set_keys(o, "scale", [1, fa, fa + 6, T], [(0, 0, 0), (0, 0, 0), (1, 1, 1), (1.4, 1.4, 1.2)], "LINEAR")
        _anc(ctx, "stair", (xs, -D / 2, H * 0.42), parent=root)
        _anc(ctx, "lift", (sum(CORE["lift2"]) / 2, -D / 2, H * 0.62), parent=root)
        _anc(ctx, "smoke", (xs + 10.0, -D / 2, zf), parent=root)
    else:   # protect
        f_sp = ctx.word_time(p.get("sprinkler_cue", "sprinklers"), 0.2)
        f_d = ctx.word_time(p.get("door_cue", "doors"), 0.4)
        f_f = ctx.word_time(p.get("fan_cue", "stairwells"), 0.62)
        f_a = ctx.word_time(p.get("alarm_cue", "alarms"), 0.85)
        blue_m, blue_s = L.add_mat("spr_cone", hexc("4fb3ff"), 0.0)
        bm = bmesh.new()
        floors = (4, 9, 14, 18)
        for k in floors:
            for x in (-14.0, -10.0, 11.0, 15.0):
                r = bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=1.6, radius2=0.08, depth=2.6)
                bmesh.ops.translate(bm, vec=(x, -4.0, k * EXP_FH + 0.4 + 1.6), verts=r["verts"])
        o = S.obj("spr", S.mesh_from_bm("spr", bm, [blue_m]), parent=root)
        o.visible_shadow = False
        sock_keys(blue_s, [(1, 0.0), (f_sp, 0.0), (f_sp + 10, 1.6)])
        # fire doors at the stair shaft front on several floors: swing shut (rotation about the hinge)
        dm = S.pbr("fire_door", hexc("b8322c"), 0.5, var=0.03)
        x0, x1 = CORE["stair"]
        for i, k in enumerate((3, 7, 11, 15, 19)):
            hinge = L.link(bpy.data.objects.new("dh%d" % k, None))
            hinge.parent = root
            hinge.location = (x0 + 0.2, CORE_Y[0], k * EXP_FH + 0.4)
            bm = bmesh.new()
            _box(bm, (1.1, 0, 1.1), (2.2, 0.12, 2.2), 0)
            S.obj("door%d" % k, S.mesh_from_bm("door%d" % k, bm, [dm]), parent=hinge)
            fd = f_d + 3 * i
            set_keys(hinge, "rotation_euler", [1, fd, fd + 14], [(0, 0, -1.4), (0, 0, -1.4), (0, 0, 0.0)], "BEZIER")
        # stair fan on the roof above the stair shaft + teal arrows pushing down / in
        fan = L.link(bpy.data.objects.new("fan", None))
        fan.parent = root
        fan.location = ((x0 + x1) / 2, 1.5, H + 3.6)
        bm = bmesh.new()
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=2.4, radius2=2.4, depth=0.6)
        for k in range(4):
            v = _box(bm, (0, 0, 0.5), (4.2, 0.6, 0.12), 1)
            bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 0), matrix=Matrix.Rotation(k * math.pi / 4, 3, "Z"))
        S.obj("fan_m", S.mesh_from_bm("fan_m", bm, [S.pbr("fan_body", hexc("5f6870"), 0.5, 0.5, var=0),
                                                     S.pbr("fan_blade", hexc("e8ecef"), 0.4, var=0)]), parent=fan)
        set_keys(fan, "rotation_euler", [1, f_f, T], [(0, 0, 0), (0, 0, 0), (0, 0, 0.35 * (T - f_f))], "LINEAR")
        tm = glow("air_teal", "19c9b4", 2.4)
        xs = (x0 + x1) / 2
        for k in range(5):
            a = ST.arrow("air%d" % k, 4.5, 1.4, tm, -90.0, parent=root)
            ST.loop_move(a, (xs, yf, H + 2.0), (xs, yf, H * 0.35), T, f_f + 5 * k, 80, phase=k / 5.0, grow=10)
        o, sock, c = shafts["stair"]
        sock_keys(sock, [(1, 0.0), (f_f, 0.0), (f_f + 12, 0.9)])
        # alarm pulses: red discs on every 3rd floor's core wall
        for i, k in enumerate(range(1, EXP_FL, 3)):
            m, s_ = L.add_mat("alarm%d" % k, hexc("ff2a2a"), 0.0)
            bm = bmesh.new()
            r = bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=0.6)
            bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
            o = S.obj("alarm%d" % k, S.mesh_from_bm("alarm%d" % k, bm, [m]), (CORE["duct"][1] + 1.0, CORE_Y[0] - 0.05,
                                                                          k * EXP_FH + 2.6), parent=root)
            o.visible_shadow = False
            f = f_a + 2 * i
            keys = [(1, 0.0), (f, 0.0)]
            while f < T + 20:
                keys += [(f + 3, 6.0), (f + 10, 1.0)]
                f += 14
            sock_keys(s_, keys)
        _anc(ctx, "fan", (0.0, 0.0, 0.0), parent=fan)
        _anc(ctx, "sprinkler", (11.0, -D / 2, 9 * EXP_FH + 1.5), parent=root)
    cam = cut_cam(ctx, p, mode)
    if mode == "protect":
        cam = [(1, (EXP[0] - 10.0, EXP[1] - 132.0, 50.0), (EXP[0], EXP[1], 44.0)),
               (1.0, (EXP[0] - 2.0, EXP[1] - 120.0, 48.0), (EXP[0], EXP[1], 43.0))]
    _keys(ctx, p, cam, 30)


def b_facade_v2(ctx, p):
    """The explainer tower's side wall seen from outside: an orange glow hops from a window to the one above,
    floor after floor (from `hop_cue`); from `clad_cue` outer panels on a column of the wall swing open to show the
    cladding layer, coloured with a rising gradient. Anchors: glow, clad."""
    T = ctx.frames
    build_city(ctx, p)
    build_hero(ctx)
    ex_ = build_explainer(ctx, cut=False, front=True)
    root = ex_["root"]
    f_h = ctx.word_time(p.get("hop_cue", "break"), 0.15)
    f_c = ctx.word_time(p.get("clad_cue", "cladding"), 0.7)
    W, D = EXP_W, EXP_D
    xw = W / 2 + 0.3          # east wall outer face
    # window glows: column at local y = -3, floors 6.. upwards, each lights then dims to an ember
    step = max(6, int((f_c - f_h) / 7.0))
    for i in range(7):
        k = 6 + i
        m, sock = L.add_mat("hop%d" % i, hexc("ff8a2a"), 0.0)
        bm = bmesh.new()
        _box(bm, (0, 0, 0), (0.05, 2.4, 2.0), 0)
        o = S.obj("hop%d" % i, S.mesh_from_bm("hop%d" % i, bm, [m]), (xw + 0.02, -3.0, k * EXP_FH + 2.0),
                  parent=root)
        o.visible_shadow = False
        fk = f_h + i * step
        sock_keys(sock, [(1, 0.0), (fk, 0.0), (fk + 5, 5.0), (fk + step + 4, 1.4)])
    hop = L.link(bpy.data.objects.new("hop_anchor", None))
    hop.parent = root
    set_keys(hop, "location", [1] + [f_h + i * step for i in range(7)],
             [(xw, -3.0, 6 * EXP_FH + 2.0)] + [(xw, -3.0, (6 + i) * EXP_FH + 2.0) for i in range(7)], "LINEAR")
    S.anchor(ctx, "glow", hop)
    # cladding: a strip (local y +2..+8) of outer panels hinged on one edge; behind them a gradient layer
    gm = ST.section_mat("clad_grad", [(0.0, "ffd34a"), (0.5, "ff8a2a"), (1.0, "e0362c")], 0.0, 70.0, 0.7)
    bm = bmesh.new()
    _box(bm, (0, 0, 0), (0.1, 5.6, 68.0), 0)
    S.obj("clad", S.mesh_from_bm("clad", bm, [gm]), (xw - 0.05, 5.0, 36.0), parent=root)
    pm = S.pbr("clad_panel", hexc("d9dde0"), 0.4, 0.5, var=0.03)
    for i in range(12):
        hg = L.link(bpy.data.objects.new("ph%d" % i, None))
        hg.parent = root
        hg.location = (xw + 0.1, 7.8, 2.0 + i * 5.7)
        bm = bmesh.new()
        _box(bm, (0, -2.8, 2.8), (0.08, 5.6, 5.6), 0)
        S.obj("panel%d" % i, S.mesh_from_bm("panel%d" % i, bm, [pm]), parent=hg)
        fp = f_c + 2 * i
        set_keys(hg, "rotation_euler", [1, fp, fp + 18], [(0, 0, 0), (0, 0, 0), (0, 0, -1.9)], "BEZIER")
    _anc(ctx, "clad", (xw, 5.0, 40.0), parent=root)
    ex, ey = EXP
    _keys(ctx, p, [(1, (ex + 95.0, ey - 70.0, 22.0), (ex + W / 2, ey, 34.0)),
                   (1.0, (ex + 82.0, ey - 58.0, 26.0), (ex + W / 2, ey, 38.0))], 30)


def firefighter(name, mat_suit, mat_helmet):
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 1.25), (0.24, 0.17, 0.38), 0, 12, 8)
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 0.1, 0, 0.5), (0.09, 0.09, 0.5), 0, 8, 6)
        S._ellipsoid(bm, (sx * 0.28, 0.05, 1.2), (0.07, 0.07, 0.32), 0, 8, 6)
    S._ellipsoid(bm, (0, 0.18, 1.25), (0.2, 0.1, 0.28), 2, 10, 6)     # air tank
    S._ellipsoid(bm, (0, 0, 1.82), (0.15, 0.15, 0.12), 1, 12, 8)      # helmet
    S._ellipsoid(bm, (0, 0, 1.72), (0.11, 0.12, 0.12), 3, 10, 8)      # head
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [mat_suit, mat_helmet,
                                                       S.pbr("ff_tank", hexc("c9ccd0"), 0.4, 0.6, var=0),
                                                       S.pbr("mq_skin", hexc("d9d4cc"), 0.5, var=0)], smooth=True),
          parent=root)
    return root


def b_ladder_v2(ctx, p):
    """A fire truck at the explainer tower's foot raises its ladder, which stops well short of the top (dotted
    line to the roof). From `climb_cue` the camera moves to the stair core: small firefighter figures climb the
    stairs beside a red standpipe with hose valves. Anchors: ladder, pipe, top."""
    T = ctx.frames
    build_city(ctx, p)
    build_hero(ctx)
    ex_ = build_explainer(ctx, cut=True, front=False)
    root, H = ex_["root"], ex_["H"]
    ex, ey = EXP
    f_l = ctx.word_time(p.get("ladder_cue", "ladders"), 0.12)
    f_c = ctx.word_time(p.get("climb_cue", "climb"), 0.45)
    D = EXP_D
    # truck in front of the tower (left of the core), ladder rising towards the facade
    tx, ty = ex - 8.0, ey - D / 2 - 14.0
    L.make_car("ftruck", loc=(tx, ty, 0.05), rot_z=math.pi / 2, headlights=False, glow=False, model="firetruck",
               scale=2.3)
    S._repaint_kenney()
    lad = L.link(bpy.data.objects.new("ladder", None))
    lad.location = (tx, ty, 4.4)
    lad.rotation_euler = (math.radians(-62.0), 0, 0)     # tilt towards +Y (the facade), rising
    lm = S.pbr("ladder_m", hexc("d6d9dc"), 0.35, 0.8, var=0)
    rm_ = S.pbr("ladder_r", hexc("c8302f"), 0.45, 0.3, var=0)
    for k, (wid, col) in enumerate(((1.6, rm_), (1.3, lm), (1.0, lm))):
        bm = bmesh.new()
        for sx in (-1, 1):
            _box(bm, (sx * wid / 2, 0, 0.5), (0.18, 0.18, 1.0), 0)
        for i in range(10):
            _box(bm, (0, 0, i / 10.0 + 0.05), (wid, 0.08, 0.04), 0)
        sec = S.obj("lsec%d" % k, S.mesh_from_bm("lsec%d" % k, bm, [col]), parent=lad)
        z0 = k * 1.0
        Lk = 11.5
        set_keys(sec, "location", [1, f_l, f_l + 50], [(0, 0, 0), (0, 0, 0), (0, 0, k * Lk * 0.92)], "BEZIER")
        set_keys(sec, "scale", [1], [(1, 1, Lk)], "CONSTANT")
    tip = L.link(bpy.data.objects.new("ladder_tip", None))
    tip.parent = lad
    set_keys(tip, "location", [1, f_l, f_l + 50], [(0, 0, 11.5), (0, 0, 11.5), (0, 0, 11.5 + 2 * 11.5 * 0.92)], "BEZIER")
    S.anchor(ctx, "ladder", tip)
    # dotted line from the ladder's final tip to the roof
    bpy.context.view_layer.update()
    end_local = Vector((0, 0, 11.5 + 2 * 11.5 * 0.92))
    tip_w = lad.matrix_world @ end_local
    top = Vector((tx, ey - D / 2 - 0.5, H))
    dm, dsock = L.add_mat("dots", hexc("ffffff"), 0.0)
    bm = bmesh.new()
    n = 22
    for i in range(n):
        q = tip_w.lerp(top, (i + 0.5) / n)
        S._ellipsoid(bm, tuple(q), (0.45, 0.45, 0.45), 0, 8, 6)
    o = S.obj("dots", S.mesh_from_bm("dots", bm, [dm]))
    o.visible_shadow = False
    sock_keys(dsock, [(1, 0.0), (f_l + 50, 0.0), (f_l + 62, 2.5)])
    _anc(ctx, "top", tuple(top))
    # standpipe (red) up the stair shaft with valves, figures climbing
    x0, x1 = CORE["stair"]
    pm = S.pbr("standpipe", hexc("d22d2d"), 0.35, 0.4, var=0)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.22, radius2=0.22, depth=H)
    bmesh.ops.translate(bm, vec=(x0 + 0.5, 5.4, H / 2), verts=r["verts"])
    for k in range(EXP_FL):
        _box(bm, (x0 + 0.5, 5.1, k * EXP_FH + 1.4), (0.5, 0.5, 0.5), 0)
    S.obj("standpipe", S.mesh_from_bm("standpipe", bm, [pm]), parent=root)
    suit = S.pbr("ff_suit", hexc("3a3f2f"), 0.7, var=0.05)
    helm = S.pbr("ff_helmet", hexc("e6c22a"), 0.35, var=0)
    kz = 8
    for i in range(3):
        fg = firefighter("ff%d" % i, suit, helm)
        fg.parent = root
        fg.scale = (1.0, 1.0, 1.0)
        fr_, locs, rots = [], [], []
        for f in range(1, T + 1, 2):
            u = max(0.0, (f - f_c + 20 - i * 10) / 120.0)
            s = u * 2.0 + 0.0
            half = int(s) % 2
            fl = int(s) // 2
            w_ = s - int(s)
            za = (kz + fl) * EXP_FH + 0.4 + half * EXP_FH / 2 + w_ * EXP_FH / 2
            xa, xb = (x0 + 0.6, x1 - 1.2) if half == 0 else (x1 - 0.6, x0 + 1.2)
            xx = xa + (xb - xa) * w_
            yy = 0.4 if half == 0 else 3.2
            fr_.append(f)
            locs.append((xx, yy, za + 0.1))
            rots.append((0, 0, -math.pi / 2 if half == 0 else math.pi / 2))
        set_keys(fg, "location", fr_, locs, "LINEAR")
        set_keys(fg, "rotation_euler", fr_, rots, "CONSTANT")
    _anc(ctx, "pipe", (x0 + 0.5, -D / 2, (kz + 1.6) * EXP_FH), parent=root)
    xs = (x0 + x1) / 2
    zc = (kz + 1.2) * EXP_FH
    _keys(ctx, p, [(1, (ex - 75.0, ey - 150.0, 30.0), (ex - 6.0, ey, 36.0)),
                   (max(2, f_c - 5), (ex - 60.0, ey - 140.0, 30.0), (ex - 6.0, ey, 36.0)),
                   (min(T - 1, f_c + 50), (ex + xs + 1.0, ey - 30.0, zc + 2.0), (ex + xs, ey, zc)),
                   (T, (ex + xs + 1.5, ey - 27.0, zc + 3.5), (ex + xs, ey, zc + 1.6))], 30)


def section_block(name, loc, w=26.0, d=9.0, floors=3, fh=3.6):
    """Three-storey building section seen from the front (cut face toward -Y): slabs, back wall with windows,
    ceiling lights. Returns root."""
    root = L.link(bpy.data.objects.new(name, None))
    root.location = loc
    slab = S.pbr("sec_slab", hexc("8f959b"), 0.8, var=0.04)
    wall = S.pbr("sec_wall", hexc("f1ece2"), 0.85, var=0.02)
    floor = S.pbr("sec_floor", hexc("b99f80"), 0.7, var=0.06, var_scale=2.0)
    win = S.pbr("sec_win", hexc("9fc6e6"), 0.05, var=0)
    lm = glow("sec_light", "fff4e2", 2.2)
    bm = bmesh.new()
    for k in range(floors + 1):
        _box(bm, (0, 0, k * fh), (w, d, 0.4), 0)
    for k in range(floors):
        z = k * fh + 0.2
        _box(bm, (0, 0, z + 0.02), (w, d, 0.04), 2)
        _box(bm, (0, d / 2, z + fh / 2), (w, 0.3, fh), 1)
        for x in range(-11, 12, 4):
            _box(bm, (x, d / 2 - 0.16, z + 1.8), (2.4, 0.05, 1.6), 3)
        _box(bm, (-w / 2, 0, z + fh / 2), (0.3, d, fh), 1)
        _box(bm, (w / 2, 0, z + fh / 2), (0.3, d, fh), 1)
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [slab, wall, floor, win]), parent=root)
    bm = bmesh.new()
    for k in range(floors):
        for x in range(-10, 11, 5):
            _box(bm, (x, 0.5, (k + 1) * fh - 0.25), (2.0, 0.6, 0.04), 0)
    o = S.obj(name + "_l", S.mesh_from_bm(name + "_l", bm, [lm]), parent=root)
    o.visible_shadow = False
    return root


def b_corridor_v2(ctx, p):
    """Section through three floors: on the middle floor a hallway (left) and an office (right) divided by a
    closed door; soft grey smoke rolls along the hallway ceiling from `fill_cue` and stops at the door; the office
    stays clear and bright. Anchors: door, smoke."""
    T = ctx.frames
    build_city(ctx, p)
    zc = 40.0
    ex, ey = EXP[0], EXP[1] - 140.0
    root = section_block("sec", (ex, ey, zc - 3.6))
    fh = 3.6
    z0 = 3.6 + 0.2                                       # middle floor top (local)
    # wall + closed door at local x = 2
    wall = S.pbr("sec_wall", hexc("f1ece2"), 0.85, var=0.02)
    dm = S.pbr("sec_door", hexc("8a5a36"), 0.55, var=0.04)
    bm = bmesh.new()
    _box(bm, (2.0, 1.0, z0 + fh / 2), (0.25, 7.0, fh - 0.4), 0)
    S.obj("divider", S.mesh_from_bm("divider", bm, [wall]), parent=root)
    bm = bmesh.new()
    _box(bm, (2.0, -2.6, z0 + 1.05), (0.12, 1.0, 2.1), 0)
    _box(bm, (1.92, -2.25, z0 + 1.0), (0.05, 0.05, 0.12), 1)
    S.obj("door", S.mesh_from_bm("door", bm, [dm, S.pbr("handle", hexc("d8d8d8"), 0.3, 0.9, var=0)]),
          parent=root)
    # the wall above the door + the gap: the divider has a door hole -> fill around it
    bm = bmesh.new()
    _box(bm, (2.0, -2.6, z0 + 2.1 + (fh - 0.4 - 2.1) / 2), (0.25, 1.0, fh - 0.4 - 2.1), 0)
    _box(bm, (2.0, -3.6 - 0.25, z0 + fh / 2), (0.25, 0.5, fh - 0.4), 0)
    S.obj("door_frame", S.mesh_from_bm("door_frame", bm, [wall]), parent=root)
    # office furniture (right)
    bm = bmesh.new()
    for x in (5.5, 8.5, 11.0):
        _box(bm, (x, 1.5, z0 + 0.75), (1.6, 0.8, 0.06), 0)
        _box(bm, (x, 2.3, z0 + 0.45), (0.5, 0.5, 0.9), 1)
    S.obj("office", S.mesh_from_bm("office", bm, [S.pbr("desk2", hexc("8a6a4a"), 0.6, var=0),
                                                  S.pbr("chair2", hexc("2f6fb3"), 0.6, var=0)]), parent=root)
    # smoke under the hallway ceiling: puffs advance from the left edge to the door and pile up there
    f_f = ctx.word_time(p.get("fill_cue", "fill"), 0.3)
    sm = ST.cloud_mat("hall_smoke", 0.1, "5c6268")
    rng = random.Random(7)
    zc_ = z0 + fh - 0.75
    for k in range(26):
        bl = [(rng.uniform(-0.5, 0.5), rng.uniform(-1.5, 1.5), rng.uniform(-0.15, 0.15), rng.uniform(0.6, 0.95), 0.6)
              for _ in range(4)]
        o = ST.puffs("hs%d" % k, bl, sm, parent=root)
        o.visible_shadow = False
        xe = 1.2 - (k % 9) * 1.4
        fa = f_f - 30 + 3 * k
        zz = zc_ - 0.15 * (k % 3)
        set_keys(o, "location", [1, fa, fa + 70], [(-14.0, rng.uniform(-1, 2), zz), (-14.0, rng.uniform(-1, 2), zz),
                                                   (xe, rng.uniform(-2.5, 2.5), zz)], "BEZIER")
        set_keys(o, "scale", [1, fa, fa + 10], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "LINEAR")
    _anc(ctx, "door", (2.0, -3.4, z0 + 1.2), parent=root)
    _anc(ctx, "smoke", (-5.0, -3.4, zc_), parent=root)
    _keys(ctx, p, [(1, (ex - 1.5, ey - 15.5, zc + 1.6), (ex - 1.0, ey, zc + 1.4)),
                   (1.0, (ex - 0.5, ey - 13.5, zc + 1.6), (ex - 0.5, ey, zc + 1.4))], 24, 0.1)


def b_hall_v2(ctx, p):
    """Bright hotel hallway seen down its length: doors on both sides counted towards the lit green stair sign at
    the end; red ring on the elevator doors on `lift_cue`; a towel at the foot of a closed door on `seal_cue`.
    Anchors: d1, d2, d3, stairs, lift, towel."""
    T = ctx.frames
    S.daylight(ctx, p.get("sun_az", -30.0), 40.0, hdri=True)
    L.fog(0.0, S.HAZE, start=1000.0)
    rng = random.Random(2)
    carpet = S.pbr("carpet", hexc("7a3b3b"), 0.95, var=0.1, var_scale=3.0, bump=0.05)
    wallm = S.pbr("hall_wall", hexc("efe6d8"), 0.85, var=0.02)
    ceil = S.pbr("hall_ceil", hexc("f7f4ee"), 0.9, var=0)
    dm = S.pbr("hall_door", hexc("6b4a32"), 0.5, var=0.04)
    frame = S.pbr("hall_frame", hexc("f5f1ea"), 0.5, var=0)
    steel = S.pbr("lift_door", hexc("b9bfc5"), 0.3, 0.9, var=0)
    Wd, Ln, Hh = 2.4, 30.0, 2.8
    bm = bmesh.new()
    _box(bm, (0, Ln / 2, -0.05), (Wd + 0.6, Ln + 2, 0.1), 0)
    _box(bm, (0, Ln / 2, Hh + 0.05), (Wd + 0.6, Ln + 2, 0.1), 2)
    for sx in (-1, 1):
        _box(bm, (sx * (Wd / 2 + 0.1), Ln / 2, Hh / 2), (0.2, Ln + 2, Hh), 1)
    _box(bm, (0, Ln + 0.9, Hh / 2), (Wd + 0.6, 0.2, Hh), 1)
    _box(bm, (0, -1.0, Hh / 2), (Wd + 0.6, 0.2, Hh), 1)
    S.obj("hall", S.mesh_from_bm("hall", bm, [carpet, wallm, ceil]))
    doors = []
    bm = bmesh.new()
    ys = [4.0, 9.5, 15.0, 20.5, 26.0]
    for i, y in enumerate(ys):
        for sx in (-1, 1):
            if sx > 0 and i == 1:
                continue     # elevator on the right instead
            _box(bm, (sx * (Wd / 2 - 0.02), y, 1.05), (0.06, 1.0, 2.1), 0)
            _box(bm, (sx * (Wd / 2 - 0.0), y, 1.05), (0.04, 1.16, 2.2), 1)
            doors.append((sx, y))
    _box(bm, (0, Ln + 0.78, 1.05), (1.0, 0.06, 2.1), 0)       # stair door at the end
    _box(bm, (0, Ln + 0.8, 1.05), (1.16, 0.04, 2.2), 1)
    S.obj("doors", S.mesh_from_bm("doors", bm, [dm, frame]))
    bm = bmesh.new()
    _box(bm, (Wd / 2 - 0.02, ys[1], 1.1), (0.06, 1.6, 2.2), 0)
    S.obj("lift", S.mesh_from_bm("lift", bm, [steel]))
    # lights
    lm = glow("hall_light", "fff1dc", 3.0)
    bm = bmesh.new()
    for y in range(1, int(Ln), 3):
        _box(bm, (0, y, Hh - 0.01), (0.6, 0.6, 0.02), 0)
    o = S.obj("hall_lights", S.mesh_from_bm("hall_lights", bm, [lm]))
    o.visible_shadow = False
    for y in (3.0, 12.0, 21.0, 29.0):
        li = A._area("hl%d" % int(y), (0, y, Hh - 0.1), 1.2, 60.0, (1.0, 0.95, 0.88))
        li.rotation_euler = (0, 0, 0)
        li.rotation_euler = (math.pi, 0, 0)
    # green stair sign (no text) above the end door
    gm, gs = L.add_mat("stair_sign", hexc("22d36a"), 1.0)
    bm = bmesh.new()
    _box(bm, (0, Ln + 0.7, 2.45), (0.7, 0.05, 0.28), 0)
    S.obj("stair_sign", S.mesh_from_bm("stair_sign", bm, [gm]))
    f_n = ctx.word_time(p.get("count_cue", "count"), 0.15)
    f_st = ctx.word_time(p.get("stairs_cue", "stairs"), 0.3)
    f_l = ctx.word_time(p.get("lift_cue", "elevator"), 0.5)
    f_s = ctx.word_time(p.get("seal_cue", "seal"), 0.85)
    sock_keys(gs, [(1, 1.0), (f_st, 1.0), (f_st + 8, 6.0)])
    # red ring + slash on the elevator doors
    m, sock = L.add_mat("no_lift", hexc("ff2a2a"), 0.0)
    bm = bmesh.new()
    C._annulus(bm, 0.75, 0.12, 48)
    vs = _box(bm, (0, 0, 0), (1.4, 0.12, 0.01), 0)
    bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(45), 3, "Z"))
    o = S.obj("no_lift", S.mesh_from_bm("no_lift", bm, [m]), (Wd / 2 - 0.08, ys[1], 1.2))
    o.rotation_euler = (0, math.pi / 2, 0)
    o.visible_shadow = False
    sock_keys(sock, [(1, 0.0), (f_l, 0.0), (f_l + 8, 5.0)])
    # towel at the foot of the first left door
    tw = S.pbr("towel", hexc("f4f4f4"), 0.95, var=0.04, bump=0.1)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 0), (0.08, 0.5, 0.06), 0, 10, 8)
    to = S.obj("towel", S.mesh_from_bm("towel", bm, [tw], smooth=True), (-Wd / 2 + 0.12, ys[0], 0.05))
    set_keys(to, "scale", [1, f_s, f_s + 8], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "BEZIER")
    for i, (sx, y) in enumerate([(-1, ys[0]), (-1, ys[1]), (-1, ys[2])]):
        _anc(ctx, "d%d" % (i + 1), (sx * (Wd / 2 - 0.1), y, 1.6))
    _anc(ctx, "stairs", (0, Ln + 0.7, 2.45))
    _anc(ctx, "lift", (Wd / 2 - 0.1, ys[1], 1.9))
    _anc(ctx, "towel", (-Wd / 2 + 0.2, ys[0], 0.1))
    _keys(ctx, p, [(1, (0.35, -0.6, 1.65), (0.0, 12.0, 1.35)), (1.0, (0.3, 1.6, 1.6), (0.0, 14.0, 1.3))], 22, 0.05)


S.V2_BUILDERS.update({
    "tower_hook": b_tower_hook,
    "tower_cut": b_tower_cut,
    "facade_v2": b_facade_v2,
    "ladder_v2": b_ladder_v2,
    "corridor_v2": b_corridor_v2,
    "hall_v2": b_hall_v2,
})

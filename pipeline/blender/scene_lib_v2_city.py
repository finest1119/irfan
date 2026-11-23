"""v2 river-city builders (bridges episode): one persistent, stylised daytime city on two banks of a wide river
(water, quays, riverside parks, an island, city blocks, roads, six bridges with traffic). Registers into
scene_lib_v2.V2_BUILDERS.

Non-graphic / neutral rules: a "hit" bridge is only shown dimmed, ringed in red on the water, and with its traffic
stopped. No explosions, smoke, fire, weapons, soldiers, flags or side colours. No 3D text: bridge names, chips and
cards are 2D overlays (pipeline/overlay_v2.py) reading the anchors registered with S.anchor().

Layout: river flows along Y (north = +Y), centre line xc(y), width RIVER_W; bank top z = 0, water z = WATER_Z.
Bridges (south -> north) at BRIDGE_Y; their names live in episode.json (overlay labels), not here.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc, kf
import scene_lib_v2_air as A

RIVER_W = 380.0
WATER_Z = -7.0
DECK_Z = 1.2          # top of the bridge decks (banks at 0)
EXT = 6500.0          # half size of the world
BRIDGES = [           # (key, y, kind)
    ("south", -2300.0, "cable"),
    ("rail", -1400.0, "truss"),
    ("paton", -400.0, "girder"),
    ("metro", 500.0, "arch_low"),
    ("north_arch", 1500.0, "arch"),
    ("far_north", 2500.0, "girder"),
]
ISLAND = (2050.0, 520.0, 95.0)   # y centre, half length, half width


def xc(y):
    return 260.0 * math.sin(y / 1700.0) - 80.0 * math.sin(y / 650.0 + 1.0)


def xl(y):
    return xc(y) - RIVER_W / 2


def xr(y):
    return xc(y) + RIVER_W / 2


def bridge_y(key):
    return next(y for k, y, _ in BRIDGES if k == key)


# ================================================================ materials
def water_mat():
    name = "water_v2"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc("1f4a55")
    p.inputs["Roughness"].default_value = 0.05
    p.inputs["Specular IOR Level"].default_value = 0.6
    p.inputs["Coat Weight"].default_value = 0.3
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 0.35, 1.0)
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = N.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 0.09
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.55
    Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
    L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
    L.kf_socket(nz.inputs["W"], 900, 6.0, "LINEAR")
    b = N.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = 0.22
    b.inputs["Distance"].default_value = 0.4
    Lk.new(nz.outputs["Fac"], b.inputs["Height"])
    Lk.new(b.outputs["Normal"], p.inputs["Normal"])
    # slight colour variation (deeper in the middle is not modelled; noise only)
    fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.004, 0.12)
    Lk.new(S._mul_col(N, Lk, tuple(hexc("1f4a55")), fac), p.inputs["Base Color"])
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def urban_ground_mat():
    """City ground between buildings: paving + patches of lawn (Voronoi), with Poly Haven concrete detail."""
    name = "urban_ground_v2"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 1.0 / 60.0
    Lk.new(obj, vor.inputs["Vector"])
    sepc = N.new("ShaderNodeSeparateColor")
    Lk.new(vor.outputs["Color"], sepc.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].color = hexc("a8a49b")
    els[1].position = 0.62
    els[1].color = hexc("6f8a4a")
    e = els.new(0.8)
    e.color = hexc("9c978d")
    Lk.new(sepc.outputs[0], ramp.inputs[0])
    fac, _ = S._noise_var(N, Lk, obj, 0.02, 0.1)
    col = S._mul_col(N, Lk, ramp.outputs["Color"], fac)
    p.inputs["Roughness"].default_value = 0.9
    if not S.ph_detail(N, Lk, obj, "concrete_floor_02", p, col, amount=0.35, hue=0.0, normal=0.3, rough_mix=0.2,
                       scale_mul=4.0):
        Lk.new(col, p.inputs["Base Color"])
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def stone_mat():
    name = "quay_v2"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    br = N.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.6
    br.inputs["Row Height"].default_value = 0.6
    br.inputs["Mortar Size"].default_value = 0.03
    br.inputs["Color1"].default_value = hexc("b8b0a2")
    br.inputs["Color2"].default_value = hexc("a39a8b")
    br.inputs["Mortar"].default_value = hexc("7d776d")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(obj, sep.inputs[0])
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    Lk.new(sep.outputs["X"], add.inputs[0])
    Lk.new(sep.outputs["Y"], add.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ")
    Lk.new(add.outputs[0], cmb.inputs[0])
    Lk.new(sep.outputs["Z"], cmb.inputs[1])
    Lk.new(cmb.outputs[0], br.inputs["Vector"])
    Lk.new(br.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.85
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def asphalt_mat(name="city_asphalt_v2", color=hexc("4a4d52")):
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    p.inputs["Roughness"].default_value = 0.85
    if not S.ph_detail(N, Lk, obj, "aerial_asphalt_01", p, tuple(color), amount=0.5, normal=0.4, rough_mix=0.3):
        p.inputs["Base Color"].default_value = color
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def dim_mat(name, color, rough=0.6, metal=0.0):
    """Material whose colour can be dimmed (Value node 'dim' 0 -> 1 = darker, desaturated). Returns (mat, socket)."""
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    fac, _ = S._noise_var(N, Lk, obj, 0.08, 0.06)
    col = S._mul_col(N, Lk, tuple(color), fac)
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    Lk.new(col, mx.inputs["A"])
    mx.inputs["B"].default_value = hexc("3a3436")
    val = N.new("ShaderNodeValue")
    val.outputs[0].default_value = 0.0
    Lk.new(val.outputs[0], mx.inputs["Factor"])
    Lk.new(mx.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    S._finish(m, p.outputs[0])
    return m, val.outputs[0]


# ================================================================ terrain: banks, quays, water, parks, island
def _bank_strip(name, side, mat, inner_off, outer_off, z, step=40.0, uv=False):
    """Quad strip following the river: between (bank edge + inner_off) and (bank edge + outer_off), side -1 = west."""
    bm = bmesh.new()
    prev = None
    y = -EXT
    while y <= EXT + 0.1:
        e = xl(y) if side < 0 else xr(y)
        a = bm.verts.new((e + side * inner_off, y, z))
        b = bm.verts.new((e + side * outer_off, y, z))
        if prev is not None:
            pa, pb = prev
            f = bm.faces.new((pa, pb, b, a) if side < 0 else (pa, a, b, pb))
        prev = (a, b)
        y += step
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = S.mesh_from_bm(name, bm, [mat])
    return S.obj(name, me)


def build_terrain(ctx, rng):
    # banks: wide strips from the quay edge to the world edge
    ground = urban_ground_mat()
    for side in (-1, 1):
        _bank_strip("bank%d" % side, side, ground, 0.0, EXT + 2000, 0.0, step=50.0)
    # quay walls (stone), from bank top down below the water
    stone = stone_mat()
    for side in (-1, 1):
        bm = bmesh.new()
        prev = None
        y = -EXT
        while y <= EXT + 0.1:
            e = xl(y) if side < 0 else xr(y)
            a, b = bm.verts.new((e, y, 0.0)), bm.verts.new((e, y, WATER_Z - 2.0))
            if prev is not None:
                bm.faces.new((prev[0], prev[1], b, a))
            prev = (a, b)
            y += 25.0
        S.obj("quay%d" % side, S.mesh_from_bm("quay", bm, [stone]))
    # water + river bed
    bm = bmesh.new()
    prev = None
    y = -EXT
    while y <= EXT + 0.1:
        a, b = bm.verts.new((xl(y) - 2, y, WATER_Z)), bm.verts.new((xr(y) + 2, y, WATER_Z))
        if prev is not None:
            bm.faces.new((prev[0], prev[1], b, a))
        prev = (a, b)
        y += 25.0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    S.obj("water", S.mesh_from_bm("water", bm, [water_mat()]))
    # riverside parks (lawn) and promenade roads on both banks
    lawn = S.lawn_mat("park_lawn_v2", hexc("6f9050"), stripes=False)
    road = asphalt_mat()
    walk = S.pbr("promenade_v2", hexc("c9bfae"), 0.8, var=0.06, var_scale=0.2)
    for side in (-1, 1):
        _bank_strip("prom%d" % side, side, walk, 0.0, 14.0, 0.25, step=25.0)
        _bank_strip("park%d" % side, side, lawn, 14.0, 95.0, 0.2, step=25.0)
        _bank_strip("embk%d" % side, side, road, 95.0, 115.0, 0.3, step=25.0)
    # island (park) in the north
    iy, ihl, ihw = ISLAND
    bm = bmesh.new()
    ring_top, ring_bot = [], []
    n = 48
    for k in range(n):
        th = 2 * math.pi * k / n
        y = iy + ihl * math.sin(th)
        x = xc(y) + ihw * math.cos(th) * (0.75 + 0.25 * math.cos(th * 2))
        ring_top.append(bm.verts.new((x, y, -0.6)))
        ring_bot.append(bm.verts.new((x, y, WATER_Z - 2)))
    bm.faces.new(ring_top)
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((ring_top[k], ring_bot[k], ring_bot[j], ring_top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    S.obj("island", S.mesh_from_bm("island", bm, [S.lawn_mat("island_lawn_v2", hexc("67884a"), stripes=False)]))
    tree_t = S.tree_templates(rng)
    pts = []
    for _ in range(170):
        y = rng.uniform(iy - ihl * 0.85, iy + ihl * 0.85)
        w = ihw * 0.6 * math.sqrt(max(0.0, 1 - ((y - iy) / ihl) ** 2))
        pts.append((xc(y) + rng.uniform(-w, w), y))
    trees = S.scatter(tree_t, pts, rng, prefix="itree")
    for t in trees:
        t.location.z = -0.6
    # park trees along both banks (avoid bridge heads)
    pts = []
    for side in (-1, 1):
        for _ in range(900):
            y = rng.uniform(-EXT * 0.6, EXT * 0.6)
            if any(abs(y - by) < 40 for _, by, _ in BRIDGES):
                continue
            e = xl(y) if side < 0 else xr(y)
            pts.append((e + side * rng.uniform(22, 90), y))
    S.scatter(tree_t, pts, rng, prefix="ptree")
    return tree_t


# ================================================================ city blocks
def _city_mats():
    mats = [S.facade_mat("cityv2_%d" % i, c, g, 3.2, 3.2, wf) for i, (c, g, wf) in enumerate((
        (hexc("e4ddd0"), hexc("3b5268"), 0.5), (hexc("cfd5da"), hexc("4a6a86"), 0.6),
        (hexc("efe6d6"), hexc("34495e"), 0.45), (hexc("b9c2cb"), hexc("2c4157"), 0.7),
        (hexc("d8c4a8"), hexc("3a4a5a"), 0.5), (hexc("f1ede4"), hexc("51667a"), 0.55),
        (hexc("c9b39a"), hexc("3d4c5c"), 0.45), (hexc("dfe3e6"), hexc("2f4a63"), 0.65)))]
    roof = S.pbr("cityv2_roof", hexc("7a7c80"), 0.85, var=0.1, bump=0.05)
    roof2 = S.pbr("cityv2_roof_red", hexc("a65a3a"), 0.8, var=0.1, bump=0.05)
    return mats + [roof, roof2]


def _fast_box(bm, cx, cy, z0, w, d, h, rot, mi):
    """Axis box (rotated by 0 or 90 deg) appended with raw bmesh calls (no bmesh.ops: fast for 10k+ boxes)."""
    if rot:
        w, d = d, w
    x0, x1, y0, y1, z1 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0 + h
    v = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f]).material_index = mi


def _gable(bm, cx, cy, z0, w, d, rh, rot, mi):
    """Gable roof prism (ridge along the long side)."""
    if rot:
        pts = [(cx - d / 2, cy - w / 2), (cx + d / 2, cy - w / 2), (cx + d / 2, cy + w / 2), (cx - d / 2, cy + w / 2)]
        r0, r1 = (cx, cy - w / 2), (cx, cy + w / 2)
    else:
        pts = [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]
        r0, r1 = (cx - w / 2, cy), (cx + w / 2, cy)
    b = [bm.verts.new((x, y, z0)) for x, y in pts]
    t0, t1 = bm.verts.new((r0[0], r0[1], z0 + rh)), bm.verts.new((r1[0], r1[1], z0 + rh))
    fs = []
    if rot:
        fs = [(b[0], b[1], t0), (b[2], b[3], t1), (b[1], b[2], t1, t0), (b[3], b[0], t0, t1)]
    else:
        fs = [(b[3], b[0], t0), (b[1], b[2], t1), (b[0], b[1], t1, t0), (b[2], b[3], t0, t1)]
    for f in fs:
        bm.faces.new(f).material_index = mi


def build_city_blocks(ctx, rng, tree_t, region=(-4200.0, 4200.0)):
    """Street grid on both banks (one mesh), buildings on the blocks merged into ONE mesh (10k+ buildings as
    separate objects took > 30 min to build), a few green squares."""
    mats = _city_mats()
    road_m = asphalt_mat("street_v2", hexc("55585d"))
    blk, street = 135.0, 14.0
    y0, y1 = region
    bm_roads = bmesh.new()
    bm_b = bmesh.new()
    n_b = 0
    tree_pts = []
    xs = [x for x in range(-4400, 4401, int(blk))]
    ys = [y for y in range(int(y0), int(y1) + 1, int(blk))]
    for x in xs:
        for y in ys:
            cx, cy = x + blk / 2, y + blk / 2
            ok = True
            for yy in (y, cy, y + blk):
                if xl(yy) - 125 < x + blk and x < xr(yy) + 125:
                    ok = False
            if not ok:
                continue
            _fast_box(bm_roads, x + street / 2, cy, 0.0, street, blk, 0.3, 0, 0)
            _fast_box(bm_roads, cx, y + street / 2, 0.0, blk, street, 0.4, 0, 0)
            dist_river = abs(cx - xc(cy)) - RIVER_W / 2
            downtown = math.exp(-(((cx + 700) / 900.0) ** 2 + ((cy - 700) / 1100.0) ** 2))
            if rng.random() < 0.07:     # green square
                for _ in range(10):
                    tree_pts.append((rng.uniform(x + 25, x + blk - 12), rng.uniform(y + 25, y + blk - 12)))
                continue
            n = rng.choice((2, 3, 3, 4))
            for k in range(n):
                if downtown > 0.35 and rng.random() < downtown * 0.8:
                    kind = "tall"
                elif rng.random() < 0.45 + (0.25 if dist_river > 900 else 0):
                    kind = "mid"
                else:
                    kind = "low"
                if kind == "low":
                    w, d, h = rng.uniform(14, 26), rng.uniform(12, 20), rng.uniform(9, 18)
                elif kind == "mid":
                    w, d, h = (rng.uniform(55, 80) if rng.random() < 0.3 else rng.uniform(18, 32)), rng.uniform(14, 22), rng.uniform(24, 48)
                else:
                    w, d, h = rng.uniform(20, 32), rng.uniform(20, 30), rng.uniform(60, 130)
                qx = x + street + 8 + (k % 2) * (blk - street - 16) / 2 + (blk - street - 16) / 4
                qy = y + street + 8 + (k // 2) * (blk - street - 16) / 2 + (blk - street - 16) / 4
                if n == 2:
                    qy = y + street + (blk - street) / 2 + (k - 0.5) * 30
                if w > 50:
                    qx = x + street + (blk - street) / 2
                rot = 0 if rng.random() < 0.6 or w > 50 else 1
                qx += rng.uniform(-3, 3)
                qy += rng.uniform(-3, 3)
                mi = rng.randrange(8)
                _fast_box(bm_b, qx, qy, 0.0, w, d, h, rot, mi)
                if kind == "low" and rng.random() < 0.5:
                    _gable(bm_b, qx, qy, h, w + 0.8, d + 0.8, d * 0.22, rot, 9)
                else:
                    _fast_box(bm_b, qx, qy, h, w + 0.6, d + 0.6, 1.0, rot, 8)
                    if kind == "tall":
                        _fast_box(bm_b, qx, qy, h + 1.0, w * 0.4, d * 0.4, 4.0, rot, 8)
                n_b += 1
    S.obj("streets", S.mesh_from_bm("streets", bm_roads, [road_m]))
    S.obj("buildings", S.mesh_from_bm("buildings", bm_b, mats))
    S.scatter(tree_t, tree_pts, rng, prefix="sqtree")
    print("[v2 city] %d buildings (one mesh)" % n_b)


def build_hills_far(rng):
    m = S.pbr("hill_city_v2", hexc("5b7650"), 0.95, var=0.15, var_scale=0.002)
    for i in range(26):
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(7500, 10000)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        S.obj("hill%d" % i, S.mesh_from_bm("hill%d" % i, bm, [m], smooth=True),
              (math.cos(ang) * dist, math.sin(ang) * dist, -80),
              scale=(rng.uniform(1200, 2200), rng.uniform(900, 1500), rng.uniform(150, 380)))


# ================================================================ bridges
def make_bridge(key, y, kind):
    """Bridge across the river at y. Returns info dict: deck (x0, x1), lanes, dim sockets, centre."""
    x0, x1 = xl(y) - 45.0, xr(y) + 45.0
    length = x1 - x0
    cx = (x0 + x1) / 2
    width = 30.0 if kind != "arch_low" else 26.0
    deck_m, dsock = dim_mat("deck_%s" % key, hexc("c8c3ba"), 0.75)
    steel_col = {"cable": hexc("eef0f2"), "truss": hexc("6d8aa3"), "arch": hexc("d8dde2"), "arch_low": hexc("c9cdd2"),
                 "girder": hexc("b8b2a6")}[kind]
    steel_m, ssock = dim_mat("steel_%s" % key, steel_col, 0.45, 0.4)
    road_m = S.image_mat("bridgeroad_%s" % key, "road.png", (1.0, max(1.0, round(length / 24.0))), rough=0.8)
    socks = [dsock, ssock]
    bm = bmesh.new()
    S.bm_box(bm, (cx, y, DECK_Z - 1.4), (length, width, 2.8), 0)                    # deck slab
    # piers in the water
    n_p = max(2, int(RIVER_W / 110))
    for k in range(1, n_p + 1):
        px = xl(y) + RIVER_W * k / (n_p + 1)
        S.bm_box(bm, (px, y, (WATER_Z - 2 + DECK_Z - 2.8) / 2), (6.0, width * 0.7, DECK_Z - 2.8 - WATER_Z + 2), 0)
    # railings
    for sy in (-1, 1):
        S.bm_box(bm, (cx, y + sy * (width / 2 - 0.3), DECK_Z + 0.55), (length, 0.25, 1.1), 1)
    S.obj("bridge_%s" % key, S.mesh_from_bm("bridge_%s" % key, bm, [deck_m, steel_m]))
    # 4-lane road surface (two 9 m textured strips) on top of the deck
    for sy in (-1, 1):
        S.plane_obj("broad_%s_%d" % (key, sy), 9.0, length, (cx, y + sy * 5.0, DECK_Z + 0.15), road_m, rot_z=math.pi / 2)
    # kind-specific structure
    bm = bmesh.new()
    if kind == "cable":
        px = xc(y) - 40.0
        H = 115.0
        for sy in (-1, 1):
            vs = S.bm_box(bm, (px, y + sy * 9.0, H / 2), (5.0, 3.2, H + 4), 0)
        S.bm_box(bm, (px, y, 70.0), (5.0, 21.0, 3.5), 0)
        for sy in (-1, 1):
            for k in range(1, 12):
                for dirx in (-1, 1):
                    dx = dirx * k * 15.0
                    a = Vector((px, y + sy * 9.0, H - 6 - k * 3.2))
                    b = Vector((px + dx, y + sy * (width / 2 - 1.0), DECK_Z + 0.5))
                    _cyl(bm, a, b, 0.22)
    elif kind in ("arch", "arch_low"):
        span = RIVER_W * (0.92 if kind == "arch" else 0.5)
        rise = 55.0 if kind == "arch" else 22.0
        n = 24
        for sy in (-1, 1):
            pts = []
            for i in range(n + 1):
                u = i / n
                x = xc(y) - span / 2 + span * u
                z = DECK_Z + rise * 4 * u * (1 - u) if kind == "arch" else DECK_Z - 3 - rise * 4 * u * (1 - u) + rise
                pts.append(Vector((x, y + sy * (width / 2 - 1.5), z)))
            for a, b in zip(pts[:-1], pts[1:]):
                _cyl(bm, a, b, 1.3 if kind == "arch" else 1.0)
            if kind == "arch":
                for p_ in pts[2:-2:2]:
                    _cyl(bm, p_, Vector((p_.x, p_.y, DECK_Z)), 0.18)
        if kind == "arch":
            for p_i in range(3, n - 2, 3):
                u = p_i / n
                x = xc(y) - span / 2 + span * u
                z = DECK_Z + rise * 4 * u * (1 - u)
                S.bm_box(bm, (x, y, z), (1.2, width - 3, 1.2), 0)
    elif kind == "truss":
        n = int(length / 16)
        for sy in (-1, 1):
            yy = y + sy * (width / 2 - 1.0)
            for i in range(n):
                xa, xb = x0 + i * 16.0, x0 + (i + 1) * 16.0
                _cyl(bm, Vector((xa, yy, DECK_Z + 0.5)), Vector((xb, yy, DECK_Z + 0.5)), 0.5)
                _cyl(bm, Vector((xa, yy, DECK_Z + 13)), Vector((xb, yy, DECK_Z + 13)), 0.5)
                _cyl(bm, Vector((xa, yy, DECK_Z + 0.5)), Vector((xa, yy, DECK_Z + 13)), 0.35)
                _cyl(bm, Vector((xa, yy, DECK_Z + 0.5)) if i % 2 == 0 else Vector((xa, yy, DECK_Z + 13)),
                     Vector((xb, yy, DECK_Z + 13)) if i % 2 == 0 else Vector((xb, yy, DECK_Z + 0.5)), 0.35)
        for i in range(0, n, 2):
            S.bm_box(bm, (x0 + i * 16.0, y, DECK_Z + 13), (0.8, width - 2, 0.8), 0)
    if len(bm.verts):
        o = S.obj("bstruct_%s" % key, S.mesh_from_bm("bstruct_%s" % key, bm, [steel_m]))
    else:
        bm.free()
    return {"key": key, "y": y, "x0": x0, "x1": x1, "cx": cx, "width": width, "socks": socks, "kind": kind}


def _cyl(bm, a, b, r, seg=8):
    d = b - a
    ln = d.length
    if ln < 1e-3:
        return
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=ln)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=q.to_matrix())
    bmesh.ops.translate(bm, vec=(a + b) / 2, verts=res["verts"])


def bridge_traffic(ctx, br, rng, per_lane=6, speed=13.0, stop_f=None, stopped=False, models=None):
    """Kenney cars in 4 lanes. stop_f: frame where they brake to a stop; stopped: parked from frame 1."""
    T = ctx.frames
    cars = []
    v = speed / ctx.fps
    span = br["x1"] - br["x0"] - 30
    for lane, (dy, d) in enumerate(((-7.0, 1), (-3.0, 1), (3.0, -1), (7.0, -1))):
        travel = 0.0 if stopped else v * (T if stop_f is None else min(T, stop_f + 25))
        for k in range(per_lane):
            gap = (span - travel) / per_lane
            s0 = 15 + k * gap + rng.uniform(0, gap * 0.6)
            xa = br["x0"] + s0 if d > 0 else br["x1"] - s0
            c = L.make_car("bc_%s_%d_%d" % (br["key"], lane, k), loc=(xa, br["y"] + dy, DECK_Z + 0.15),
                           rot_z=-math.pi / 2 if d > 0 else math.pi / 2, headlights=False, glow=False,
                           model=(models[rng.randrange(len(models))] if models else None))
            if not stopped:
                if stop_f is None:
                    kf(c.obj, "location", 1, Vector((xa, br["y"] + dy, DECK_Z + 0.15)), "LINEAR")
                    kf(c.obj, "location", T, Vector((xa + d * v * (T - 1), br["y"] + dy, DECK_Z + 0.15)), "LINEAR")
                else:
                    xs = xa + d * v * (stop_f - 1)
                    xe = xs + d * v * 12          # ~0.8 s braking distance (half speed average)
                    kf(c.obj, "location", 1, Vector((xa, br["y"] + dy, DECK_Z + 0.15)), "LINEAR")
                    kf(c.obj, "location", stop_f, Vector((xs, br["y"] + dy, DECK_Z + 0.15)), "BEZIER")
                    kf(c.obj, "location", stop_f + 24, Vector((xe, br["y"] + dy, DECK_Z + 0.15)), "BEZIER")
            cars.append(c)
    S._repaint_kenney()
    return cars


def hit_marker(ctx, br, f_on, name=None, radius=None):
    """Bridge 'hit' = it dims, a red ring pulses on the water around its middle. (No explosion, no smoke.)"""
    name = name or "hit_%s" % br["key"]
    for sock in br["socks"]:
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        if f_on > 1:
            L.kf_socket(sock, f_on, 0.0, "LINEAR")
        L.kf_socket(sock, f_on + 12, 0.75, "LINEAR")
    r = radius or 150.0
    for k, (rr, th) in enumerate(((r, 3.2), (r * 0.82, 1.6))):
        m, sock = L.add_mat("%s_ring%d" % (name, k), hexc("ff2a2a"), 0.0)
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=False, segments=96, radius=rr)
        o = S.obj("%s_ring%d" % (name, k), S.mesh_from_bm(name, bm, [m]), (xc(br["y"]), br["y"], WATER_Z + 0.4))
        o.modifiers.new("w", "WIREFRAME").thickness = th
        o.visible_shadow = False
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        if f_on > 1:
            L.kf_socket(sock, f_on, 0.0, "LINEAR")
        L.kf_socket(sock, f_on + 6, 7.0, "LINEAR")
        f = f_on + 6
        while f < ctx.frames + 20:            # gentle pulse
            L.kf_socket(sock, f + 15, 3.5, "BEZIER")
            L.kf_socket(sock, f + 30, 7.0, "BEZIER")
            f += 30
        kf(o, "scale", 1, Vector((0.6, 0.6, 1)), "CONSTANT")
        if f_on > 1:
            kf(o, "scale", f_on, Vector((0.6, 0.6, 1)), "LINEAR")
        kf(o, "scale", f_on + 10, Vector((1, 1, 1)), "BEZIER")


def embankment_traffic(ctx, rng, n=24, y_range=(-3000, 3000), speed=12.0):
    T = ctx.frames
    v = speed / ctx.fps
    for i in range(n):
        side = -1 if i % 2 == 0 else 1
        d = 1 if (i // 2) % 2 == 0 else -1
        off = 101.0 if d > 0 else 109.0
        y0 = rng.uniform(*y_range)
        c = L.make_car("ec%d" % i, loc=(0, 0, 0.05), rot_z=0.0, headlights=False, glow=False)
        for f in list(range(1, T + 1, 6)) + [T]:
            y = y0 + d * v * (f - 1)
            e = xl(y) if side < 0 else xr(y)
            x = e + side * off
            dx = (xc(y + 1) - xc(y - 1)) / 2
            ang = math.atan2(-dx * d, d)          # heading along the curve
            kf(c.obj, "location", f, Vector((x, y, 0.3)), "LINEAR")
            kf(c.obj, "rotation_euler", f, Vector((0, 0, ang if d > 0 else ang)), "LINEAR")
    S._repaint_kenney()


def build_city_world(ctx, p, rng=None):
    """Sky + terrain + city + bridges (+ normal traffic on non-listed bridges). Returns {key: bridge info}."""
    rng = rng or random.Random(p.get("seed", 31))
    S.daylight(ctx, p.get("sun_az", -25.0), 40.0, hdri=p.get("hdri", True))
    L.fog(0.00016, S.HAZE, start=500.0)
    S.plane_obj("far_ground", 40000, 40000, (0, 0, -4.0), S.ground_mat())
    import time as _t
    t0 = _t.time()
    tree_t = build_terrain(ctx, rng)
    t1 = _t.time()
    build_city_blocks(ctx, rng, tree_t)
    print("[v2 city] terrain %.1fs, blocks %.1fs" % (t1 - t0, _t.time() - t1))
    build_hills_far(rng)
    brs = {}
    for key, y, kind in BRIDGES:
        brs[key] = make_bridge(key, y, kind)
    return brs, rng


def _flow_traffic(ctx, brs, rng, skip=(), stop=None, stopped=(), per_lane=5):
    stop = stop or {}
    for key, br in brs.items():
        if key in skip:
            continue
        bridge_traffic(ctx, br, rng, per_lane=per_lane, stop_f=stop.get(key), stopped=key in stopped)


def _cam(ctx, loc, target, lens=30):
    cam = ctx.camera(loc, target=target, lens=lens)
    cam.data.clip_start = 4.0
    cam.data.clip_end = 30000.0
    return cam


def _anchor_bridge(ctx, name, br, z=20.0):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = (xc(br["y"]), br["y"], z)
    S.anchor(ctx, name, e)


def _glow_mat(name, color, strength=4.0):
    return L.emissive(name, color, strength, 0.2)


def ribbon_path(name, pts, width, mat, z=0.6):
    """Flat ribbon along a polyline (route lines drawn on the ground). Returns the object (draw-in via build mod)."""
    bm = bmesh.new()
    prev = None
    for i, p in enumerate(pts):
        a = Vector(pts[max(0, i - 1)])
        b = Vector(pts[min(len(pts) - 1, i + 1)])
        d = (b - a)
        d.z = 0
        d = d.normalized() if d.length > 0 else Vector((0, 1, 0))
        nrm = Vector((-d.y, d.x, 0)) * width / 2
        pa = bm.verts.new((p[0] + nrm.x, p[1] + nrm.y, (p[2] if len(p) > 2 else z)))
        pb = bm.verts.new((p[0] - nrm.x, p[1] - nrm.y, (p[2] if len(p) > 2 else z)))
        if prev is not None:
            bm.faces.new((prev[0], prev[1], pb, pa))
        prev = (pa, pb)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]))
    o.visible_shadow = False
    return o


def draw_in(o, f0, f1):
    """Reveal a ribbon from its start using a Build modifier (faces appear in order)."""
    md = o.modifiers.new("build", "BUILD")
    md.frame_start = f0
    md.frame_duration = max(1, f1 - f0)
    return md


def movers(ctx, name, pts, n, speed, mat, size=4.0, start=1, slow=None, z_off=1.5):
    """Glowing dots looping along a polyline at `speed` m/s; slow = (frame, factor) slows them from that frame."""
    T = ctx.frames
    segs, total = [], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ln = (Vector(b) - Vector(a)).length
        segs.append((Vector(a), Vector(b), total, ln))
        total += ln

    def at(s):
        s %= total
        for a, b, s0, ln in segs:
            if s <= s0 + ln:
                return a.lerp(b, (s - s0) / max(1e-6, ln))
        return Vector(pts[-1])
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 0), (size, size, size * 0.6), 0, 10, 6)
    me = S.mesh_from_bm(name + "_dot", bm, [mat])
    for i in range(n):
        o = S.obj("%s%d" % (name, i), me, (0, 0, 0))
        o.visible_shadow = False
        s = total * i / n
        v = speed / ctx.fps
        for f in list(range(1, T + 1, 3)) + [T]:
            if slow and f > slow[0]:
                pos_s = s + v * (slow[0] - 1) + v * slow[1] * (f - slow[0])
            else:
                pos_s = s + v * (f - 1)
            p = at(pos_s)
            kf(o, "location", f, Vector((p.x, p.y, p.z + z_off)), "LINEAR")
        if start > 1:
            kf(o, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            kf(o, "scale", start, Vector((1, 1, 1)), "CONSTANT")


def river_line(y0, y1, step=40.0, side=0.0, z=0.8):
    out = []
    y = y0
    while y <= y1:
        e = xc(y) if side == 0 else (xl(y) - side if side > 0 else xr(y) - side)
        out.append((e, y, z))
        y += step
    return out


# ================================================================ BUILDERS (bridges in war, v2)
HIT = ("south", "rail", "north_arch")


def b_city_hook(ctx, p):
    """Aerial over the river city looking north. On `hit_cue` three bridges dim, red rings pulse on the water
    around them and their traffic brakes to a stop; other bridges keep flowing. Anchors: br_<key>."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    f_hit = ctx.word_time(p.get("hit_cue", "hit"), 0.45)
    hit = p.get("hit", list(HIT))
    for i, key in enumerate(hit):
        hit_marker(ctx, brs[key], f_hit + 6 * i)
    _flow_traffic(ctx, brs, rng, stop={k: f_hit + 6 * i for i, k in enumerate(hit)})
    embankment_traffic(ctx, rng)
    for key in hit:
        _anchor_bridge(ctx, "br_" + key, brs[key])
    c0, t0 = p.get("cam0", (-1500.0, -4300.0, 1100.0)), p.get("tgt0", (0.0, -300.0, 0.0))
    c1, t1 = p.get("cam1", (-1250.0, -3700.0, 980.0)), p.get("tgt1", (0.0, -150.0, 0.0))
    _cam(ctx, c0, t0, lens=p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_city_wide(ctx, p):
    """High wide views of the city split by the river (question / barrier beats). mode 'barrier': a red dashed line
    runs along the river on `split_cue`; teal rings mark every bridge on `bridges_cue`."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    _flow_traffic(ctx, brs, rng, per_lane=4)
    embankment_traffic(ctx, rng, n=16)
    mode = p.get("mode", "wide")
    if mode == "barrier":
        f_split = ctx.word_time(p.get("split_cue", "split"), 0.35)
        red = _glow_mat("barrier_red", hexc("ff3030"), 6.0)
        y = -3600.0
        k = 0
        while y < 3600:
            seg = [(xc(y), y, WATER_Z + 0.6), (xc(y + 60), y + 60, WATER_Z + 0.6)]
            o = ribbon_path("dash%d" % k, seg, 9.0, red, z=WATER_Z + 0.6)
            kf(o, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            fk = f_split + int(k * 0.35)
            kf(o, "scale", fk, Vector((1, 1, 1)), "CONSTANT")
            y += 110
            k += 1
        f_br = ctx.word_time(p.get("bridges_cue", "bridges"), 0.75)
        for i, (key, br) in enumerate(brs.items()):
            m, sock = L.add_mat("brring_%s" % key, hexc("2ee6c8"), 0.0)
            bm = bmesh.new()
            bmesh.ops.create_circle(bm, cap_ends=False, segments=72, radius=110.0)
            o = S.obj("brring_%s" % key, S.mesh_from_bm("brring", bm, [m]), (xc(br["y"]), br["y"], DECK_Z + 4))
            o.modifiers.new("w", "WIREFRAME").thickness = 7.0
            o.visible_shadow = False
            L.kf_socket(sock, 1, 0.0, "CONSTANT")
            L.kf_socket(sock, f_br + 3 * i, 0.0, "LINEAR")
            L.kf_socket(sock, f_br + 3 * i + 8, 6.0, "LINEAR")
    c0, t0 = p.get("cam0", (-900.0, -2600.0, 1500.0)), p.get("tgt0", (0.0, 300.0, 0.0))
    c1, t1 = p.get("cam1", (-1300.0, -3300.0, 2300.0)), p.get("tgt1", (0.0, 400.0, 0.0))
    _cam(ctx, c0, t0, lens=p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_supply_funnel_v2(ctx, p):
    """Delivery vans and trucks converge on one bridge along amber route lines from several directions, cross,
    and spread out on the far bank. Route lines draw in on `funnel_cue`."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    key = p.get("bridge", "paton")
    br = brs[key]
    _flow_traffic(ctx, brs, rng, skip=(key,), per_lane=4)
    by = br["y"]
    xw, xe = br["x0"], br["x1"]
    # routes: from three western directions to the bridge head, across, then fanning out east
    amber = _glow_mat("route_amber", hexc("ffb020"), 3.5)
    routes = [
        [(xw - 900, by - 700, 1.0), (xw - 400, by - 300, 1.0), (xw - 60, by - 9, 1.0)],
        [(xw - 1100, by, 1.0), (xw - 60, by - 3, 1.0)],
        [(xw - 900, by + 750, 1.0), (xw - 380, by + 320, 1.0), (xw - 60, by + 3, 1.0)],
    ]
    cross = [(xw - 60, by - 4, DECK_Z + 1.0), (xe + 60, by - 4, DECK_Z + 1.0)]
    outs = [[(xe + 60, by, 1.0), (xe + 500, by - 500, 1.0), (xe + 900, by - 800, 1.0)],
            [(xe + 60, by, 1.0), (xe + 1000, by + 60, 1.0)],
            [(xe + 60, by, 1.0), (xe + 450, by + 520, 1.0), (xe + 900, by + 900, 1.0)]]
    f_fun = ctx.word_time(p.get("funnel_cue", "funnels"), 0.7)
    f0 = ctx.word_time(p.get("start_cue", "supplies"), 0.15)
    for i, pts in enumerate(routes + [cross] + outs):
        o = ribbon_path("route%d" % i, pts, 10.0 if i == 3 else 7.0, amber, z=1.0)
        draw_in(o, f0 if i < 3 else f_fun, (f0 if i < 3 else f_fun) + 25)
    # vehicles along the routes (Kenney delivery / van / truck), never more than one per lane slot
    models = ["delivery", "van", "truck", "delivery-flat", "truck-flat"]
    full = [r + cross[1:] + outs[i][1:] for i, r in enumerate(routes)]
    v = 14.0 / ctx.fps
    for i, path in enumerate(full):
        segs = []
        tot = 0.0
        for a, b in zip(path[:-1], path[1:]):
            ln = (Vector(b) - Vector(a)).length
            segs.append((Vector(a), Vector(b), tot, ln))
            tot += ln
        for k in range(5):
            s0 = 140.0 + k * 75.0 + rng.uniform(-10, 10)
            c = L.make_car("sv%d_%d" % (i, k), loc=(0, 0, 0), headlights=False, glow=False,
                           model=models[(i + k) % len(models)])
            for f in list(range(1, T + 1, 4)) + [T]:
                s = s0 + v * (f - 1)
                for a, b, st, ln in segs:
                    if s <= st + ln or (a, b) == (segs[-1][0], segs[-1][1]):
                        u = min(1.0, (s - st) / max(1e-6, ln))
                        pt = a.lerp(b, u)
                        d = b - a
                        break
                ang = math.atan2(-d.x, d.y)
                zz = DECK_Z + 0.15 if xw - 30 < pt.x < xe + 30 else 0.3
                kf(c.obj, "location", f, Vector((pt.x, pt.y + (i - 1) * 3.4, zz)), "LINEAR")
                kf(c.obj, "rotation_euler", f, Vector((0, 0, ang)), "LINEAR")
    S._repaint_kenney()
    _anchor_bridge(ctx, "bridge", br)
    c0, t0 = p.get("cam0", (xw - 900.0, by - 1250.0, 520.0)), (xc(by) - 250.0, by, 0.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, (xw - 800.0, by - 1050.0, 460.0), (xc(by) - 150.0, by, 0.0))])


def b_utility_bridge_v2(ctx, p):
    """Close, low view of one bridge from the riverside: power (yellow), water (blue) and comms (teal) lines run
    under the deck with light pulses flowing; on `dim_cue` the pulses stop, the bridge dims and a red ring pulses."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    key = p.get("bridge", "metro")
    br = brs[key]
    by = br["y"]
    f_dim = ctx.word_time(p.get("dim_cue", "damage"), 0.7)
    _flow_traffic(ctx, brs, rng, skip=(key,), per_lane=4)
    bridge_traffic(ctx, br, rng, per_lane=5, stop_f=f_dim)
    cols = [("power", hexc("ffc21a")), ("water", hexc("2f8fff")), ("comms", hexc("22e0c0"))]
    cues = p.get("cues", ["power", "water", "communication"])
    for i, ((nm, col), cue) in enumerate(zip(cols, cues)):
        yy = by - 6.0 + i * 6.0
        zz = DECK_Z - 4.2
        pipe_m = S.pbr("pipe_%s" % nm, tuple(c * 0.5 for c in col[:3]) + (1,), 0.4, 0.3, var=0)
        bm = bmesh.new()
        _cyl(bm, Vector((br["x0"] - 200, yy, zz)), Vector((br["x1"] + 200, yy, zz)), 0.9, 12)
        S.obj("pipe_%s" % nm, S.mesh_from_bm("pipe", bm, [pipe_m]))
        f_on = ctx.word_time(cue, 0.15 + 0.15 * i)
        glow = _glow_mat("pulse_%s" % nm, col, 8.0)
        pts = [(br["x0"] - 200, yy, zz), (br["x1"] + 200, yy, zz)]
        movers(ctx, "pl_%s" % nm, pts, 14, 60.0, glow, size=1.25, start=f_on, slow=(f_dim, 0.0), z_off=0.0)
    hit_marker(ctx, br, f_dim, radius=120.0)
    _anchor_bridge(ctx, "bridge", br, z=DECK_Z - 4)
    ex = xr(by) + 25.0
    c0, t0 = p.get("cam0", (ex + 20.0, by - 150.0, 6.0)), (xc(by) + 40.0, by, -1.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 24))
    A._cam_keys(ctx, [(1, c0, t0), (T, (ex + 10.0, by - 115.0, 4.0), (xc(by) + 10.0, by, 0.0))])


def b_detour_v2(ctx, p):
    """A closed (dimmed, red-ringed, traffic stopped) bridge; an amber detour route draws along the embankment
    to the next bridge and back, and cars follow it the long way round."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    closed, alt = p.get("closed", "rail"), p.get("alt", "paton")
    bc, ba = brs[closed], brs[alt]
    hit_marker(ctx, bc, 1)
    _flow_traffic(ctx, brs, rng, stopped=(closed,), per_lane=4)
    amber = _glow_mat("detour_amber", hexc("ffb020"), 4.0)
    side_w, side_e = -105.0, 105.0
    path = [(bc["x0"] - 120, bc["y"] - 5, 1.0)]
    path += [(xl(y) - 105, y, 1.0) for y in _rng_range(bc["y"], ba["y"], 40.0)]
    path += [(ba["x0"] - 10, ba["y"] - 5, DECK_Z + 1), (ba["x1"] + 10, ba["y"] - 5, DECK_Z + 1)]
    path += [(xr(y) + 105, y, 1.0) for y in _rng_range(ba["y"], bc["y"], -40.0)]
    path += [(bc["x1"] + 120, bc["y"] + 5, 1.0)]
    f_d = ctx.word_time(p.get("detour_cue", "detours"), 0.4)
    o = ribbon_path("detour", path, 9.0, amber, z=1.0)
    draw_in(o, max(1, f_d - 10), f_d + 40)
    movers(ctx, "dcar", path, 10, 40.0, _glow_mat("detour_dot", hexc("fff1c0"), 6.0), size=3.0, start=f_d + 20,
           z_off=1.5)
    _anchor_bridge(ctx, "closed", bc)
    c0, t0 = p.get("cam0", (-1200.0, bc["y"] - 1700.0, 1100.0)), (0.0, (bc["y"] + ba["y"]) / 2, 0.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, (c0[0] + 150, c0[1] + 250, c0[2] - 80), (0.0, (bc["y"] + ba["y"]) / 2 + 100, 0.0))])


def _rng_range(a, b, step):
    out = []
    y = a
    while (step > 0 and y <= b) or (step < 0 and y >= b):
        out.append(y)
        y += step
    return out


def b_city_plate(ctx, p):
    """Plate for 2D history cards: the big arch bridge from the riverside promenade, traffic flowing (the overlay
    blurs it). Rendered at half resolution."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    _flow_traffic(ctx, brs, rng, per_lane=4)
    br = brs[p.get("bridge", "north_arch")]
    by = br["y"]
    c0 = (xl(by - 420) - 40.0, by - 420.0, 30.0)
    _cam(ctx, c0, (xc(by), by, 25.0), lens=p.get("lens", 26))
    A._cam_keys(ctx, [(1, c0, (xc(by), by, 25.0)), (T, (xl(by - 380) - 35.0, by - 380.0, 34.0), (xc(by) + 60, by, 25.0))])


def b_pontoon_v2(ctx, p):
    """A massive (intact) bridge behind; in front, pontoon segments float in from upstream one after another and lock
    into a floating bridge across the river; then cars cross it."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    _flow_traffic(ctx, brs, rng, per_lane=4)
    by = p.get("y", bridge_y("paton") - 260.0)
    seg_w, n = 24.0, int(RIVER_W / 24.0) + 1
    pont = S.pbr("pontoon_v2", hexc("6e7a62"), 0.6, 0.2, var=0.08)
    deckm = S.pbr("pontoon_deck_v2", hexc("5a5f63"), 0.8, var=0.08, bump=0.1)
    f_go = ctx.word_time(p.get("float_cue", "float"), 0.45)
    f_cars = ctx.word_time(p.get("mass_cue", "fast"), 0.85)
    for i in range(n):
        x = xl(by) + seg_w * (i + 0.5)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, -0.6), (seg_w - 0.6, 14.0, 2.4), 0)
        S.bm_box(bm, (0, 0, 0.62), (seg_w - 0.6, 11.0, 0.12), 1)
        for sy in (-1, 1):
            S.bm_box(bm, (0, sy * 6.2, 1.0), (seg_w - 0.6, 0.15, 0.7), 0)
        o = S.obj("pont%d" % i, S.mesh_from_bm("pont", bm, [pont, deckm]), (x, by, WATER_Z + 0.6))
        fi = 15 + int(i * max(20, f_cars - 45) / max(1, n))
        kf(o, "location", 1, Vector((x + rng.uniform(-30, 30), by + 300 + i * 18, WATER_Z + 0.6)), "CONSTANT")
        kf(o, "location", max(2, fi - 40), Vector((x + rng.uniform(-20, 20), by + 220 + i * 6, WATER_Z + 0.6)), "BEZIER")
        kf(o, "location", fi, Vector((x, by, WATER_Z + 0.6)), "BEZIER")
        kf(o, "rotation_euler", max(2, fi - 40), Vector((0, 0, math.radians(rng.uniform(-14, 14)))), "BEZIER")
        kf(o, "rotation_euler", fi, Vector((0, 0, 0)), "BEZIER")
    # cars cross once it is complete
    v = 8.0 / ctx.fps
    for k in range(6):
        d = 1 if k % 2 == 0 else -1
        x0 = xl(by) - 40 if d > 0 else xr(by) + 40
        c = L.make_car("pc%d" % k, loc=(x0, by - 2.6 * d, WATER_Z + 1.4), rot_z=-math.pi / 2 * d, headlights=False,
                       glow=False)
        fs = f_cars + k * 9
        kf(c.obj, "location", 1, Vector((x0, by - 2.6 * d, WATER_Z + 1.32)), "CONSTANT")
        kf(c.obj, "location", fs, Vector((x0, by - 2.6 * d, WATER_Z + 1.32)), "LINEAR")
        kf(c.obj, "location", T + 1, Vector((x0 + d * v * (T + 1 - fs), by - 2.6 * d, WATER_Z + 1.32)), "LINEAR")
        c.obj.scale = (1, 1, 1)
    S._repaint_kenney()
    pe = L.link(bpy.data.objects.new("anc_pontoon", None))
    pe.location = (xc(by), by, WATER_Z + 2)
    S.anchor(ctx, "pontoon", pe)
    c0 = p.get("cam0", (xr(by) + 70.0, by - 330.0, 38.0))
    t0 = (xc(by) - 20.0, by + 60.0, -2.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 24))
    A._cam_keys(ctx, [(1, c0, t0), (T, (c0[0] - 10, c0[1] + 40, c0[2] - 6), (xc(by) - 40.0, by + 20.0, -3.0))])


def b_arteries_v2(ctx, p):
    """Metaphor: traffic flow drawn as glowing streams along the embankments and over the bridges. On `pinch_cue`
    one bridge is pinched (red ring) and the flow over it and downstream slows to a crawl; on `backup_cue` a teal
    bypass over another bridge lights up and flows freely."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    _flow_traffic(ctx, brs, rng, per_lane=3)
    f_p = ctx.word_time(p.get("pinch_cue", "pinch"), 0.25)
    f_b = ctx.word_time(p.get("backup_cue", "backup"), 0.75)
    red = _glow_mat("flow_red", hexc("ff4a4a"), 6.0)
    teal = _glow_mat("flow_teal", hexc("2ef0d0"), 6.0)
    pk = p.get("pinch", "paton")
    bp = brs[pk]
    hit_marker(ctx, bp, f_p, name="pinch", radius=110.0)
    # main artery: west embankment -> pinched bridge -> east embankment (slows on the pinch)
    art = [(xl(y) - 105, y, 1.0) for y in _rng_range(bp["y"] - 1600, bp["y"], 40.0)]
    art += [(bp["x0"], bp["y"], DECK_Z + 1), (bp["x1"], bp["y"], DECK_Z + 1)]
    art += [(xr(y) + 105, y, 1.0) for y in _rng_range(bp["y"], bp["y"] + 1600, 40.0)]
    movers(ctx, "art", art, 60, 70.0, red, size=5.0, slow=(f_p, 0.12))
    # other arteries along both embankments (normal flow)
    for side, nm in ((-1, "w"), (1, "e")):
        pts = [((xl(y) - 105) if side < 0 else (xr(y) + 105), y, 1.0) for y in _rng_range(-3200, 3200, 50.0)]
        movers(ctx, "emb" + nm, pts, 70, 60.0 * side * 0 + 60.0, red, size=4.0)
    # bypass over the next bridge north
    ab = brs[p.get("bypass", "metro")]
    byp = [(xl(y) - 105, y, 1.0) for y in _rng_range(bp["y"] - 300, ab["y"], 40.0)]
    byp += [(ab["x0"], ab["y"], DECK_Z + 1), (ab["x1"], ab["y"], DECK_Z + 1)]
    o = ribbon_path("bypass", byp, 10.0, teal, z=1.2)
    draw_in(o, f_b, f_b + 30)
    movers(ctx, "byp", byp, 26, 70.0, teal, size=5.0, start=f_b + 15)
    _anchor_bridge(ctx, "pinch", bp)
    c0, t0 = p.get("cam0", (-1300.0, bp["y"] - 1900.0, 1300.0)), (0.0, bp["y"] + 300.0, 0.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, (c0[0] + 100, c0[1] + 250, c0[2] - 100), (0.0, bp["y"] + 400.0, 0.0))])


def b_city_outro(ctx, p):
    """Closing crane-up over the river city: from the embankment near the arch bridge to a high wide view."""
    T = ctx.frames
    brs, rng = build_city_world(ctx, p)
    _flow_traffic(ctx, brs, rng, per_lane=4)
    embankment_traffic(ctx, rng)
    by = bridge_y("north_arch")
    c0 = p.get("cam0", (xr(by - 300) + 60.0, by - 300.0, 22.0))
    t0 = (xc(by), by, 30.0)
    c1 = p.get("cam1", (1700.0, -2200.0, 1500.0))
    t1 = (0.0, 600.0, 0.0)
    _cam(ctx, c0, t0, lens=p.get("lens", 28))
    A._cam_keys(ctx, [(1, c0, t0), (int(T * 0.35), (c0[0] + 200, c0[1] - 300, 160.0), (xc(by), by, 20.0)), (T, c1, t1)])


S.V2_BUILDERS.update({
    "city_hook": b_city_hook,
    "city_wide": b_city_wide,
    "supply_funnel_v2": b_supply_funnel_v2,
    "utility_bridge_v2": b_utility_bridge_v2,
    "detour_v2": b_detour_v2,
    "city_plate": b_city_plate,
    "pontoon_v2": b_pontoon_v2,
    "arteries_v2": b_arteries_v2,
    "city_outro": b_city_outro,
})

"""v2 river / ship builders ("ship collision": how big ships collide on rivers, 26 Nov 2026 slot 2).
Registers into scene_lib_v2.V2_BUILDERS.

Worlds
  * the river city of scene_lib_v2_city (wide river, quays, parks, city blocks, bridges) with a brown-blue river,
    a wharf on the east quay with a white paddlewheel riverboat moored alongside, and a generic tanker (dark hull,
    white superstructure aft, no name, flag or logos) mid-river. The riverboat and the tanker are always shown
    APART: the tanker keeps to the far half of the channel, parallel to the banks (no impact, nothing capsized,
    nobody shown).
  * open bright water (scene_lib_v2_storm.build_ocean) for the momentum shot and the rudder close-up
  * a stylised rural river bend (own height-grid terrain) for the "river itself" shot (labelled ILLUSTRATION)
  * an icy alley (metaphor) and a ferry deck moored on the city river (takeaway)
No 3D text: every label / card is a 2D overlay (overlay_v2.py) reading the anchors set with S.anchor().

Builders
  river_hook      east-bank view across the river: moored riverboat (foreground right), tanker mid-river far off
  river_map       high top-down view of a river stretch, the tanker mid-channel with a teal ring (no riverboat)
  momentum_v2     tanker on open water, engine astern: white froth at the stern, ghost hulls stack up ahead
  bend_v2         tight horseshoe bend: amber current arrows, a tanker crabbing through, a second ship waits
  rudder_v2       stern seen through clear water: propeller + rudder, flow arrows deflected by the rudder; on
                  `lose_cue` the flow fades, the propeller stops and the rudder swings loose
  ice_alley_v2    toy truck sliding gently on a glossy ice alley between parked cars; it stops short (no contact)
  river_help_v2   tanker mid-river: pilot boat comes alongside, traffic-service radar tower pulses, two tugs nudge
  ferry_deck_v2   ferry deck: life-jacket locker glows, green exit arrows light up towards the door
  river_outro     golden-hour riverfront, the tanker passing mid-river (no riverboat); camera cranes up
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector, Euler

import scene_lib as L
import scene_lib_v2 as S
import scene_lib_v2_air as A
import scene_lib_v2_city as C
import scene_lib_v2_sea as SEA
import scene_lib_v2_storm as ST
from scene_lib import hexc
from scene_lib_v2_winter import set_keys

WZ = C.WATER_Z
WHARF = (70.0, 270.0)        # wharf y range on the east quay
TANKER_L = 180.0
RB_L = 96.0

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def sock_keys(sock, keys):
    for f, v in keys:
        L.kf_socket(sock, max(1, int(f)), v, "LINEAR")


def vis_keys(o, keys):
    s = tuple(o.scale)
    set_keys(o, "scale", [f for f, _ in keys], [(s if v else (0.0, 0.0, 0.0)) for _, v in keys], "CONSTANT")


# ================================================================ materials
def river_water_mat():
    """Brown-blue river water (Mississippi-like), moving ripples."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("river_water")
        col = hexc("4f6467")
        p.inputs["Roughness"].default_value = 0.08
        p.inputs["Specular IOR Level"].default_value = 0.5
        p.inputs["Coat Weight"].default_value = 0.2
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 0.35, 1.0)
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 0.09
        nz.inputs["Detail"].default_value = 6.0
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
        L.kf_socket(nz.inputs["W"], 900, 6.0, "LINEAR")
        b = N.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = 0.2
        b.inputs["Distance"].default_value = 0.4
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.004, 0.12)
        fac2, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.03, 0.06)
        c1 = S._mul_col(N, Lk, tuple(col), fac)
        Lk.new(S._mul_col(N, Lk, c1, fac2), p.inputs["Base Color"])
        return S._finish(m, p.outputs[0])
    return _m("river_water", mk)


def clear_water_mat(name="clear_water"):
    """See-through sea surface for the rudder close-up (tinted, glossy, BLENDED)."""
    def mk():
        m = bpy.data.materials.new(name)
        m.surface_render_method = "BLENDED"
        nt = m.node_tree
        N, Lk = nt.nodes, nt.links
        p = N.get("Principled BSDF")
        p.inputs["Base Color"].default_value = hexc("2f8fb0")
        p.inputs["Alpha"].default_value = 0.42
        p.inputs["Roughness"].default_value = 0.05
        p.inputs["Emission Color"].default_value = hexc("2f8fb0")
        p.inputs["Emission Strength"].default_value = 0.12
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 0.12
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
        L.kf_socket(nz.inputs["W"], 900, 6.0, "LINEAR")
        b = N.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = 0.12
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        return m
    return _m(name, mk)


def glow(name, col, strength=2.0):
    return S.emis(name, hexc(col), strength)


# ================================================================ vessels (original, generic, no markings)
def make_tanker(name, length=TANKER_L, wake=False):
    """Product tanker: dark hull, red bottom, deck pipes, white accommodation block aft, plain funnel.
    Origin = waterline midships, bow +Y."""
    hull = S.pbr("tk_hull", hexc("26303d"), 0.5, var=0.05)
    anti = S.pbr("tk_anti", hexc("8c3a2c"), 0.6, var=0.06)
    deckm = S.pbr("tk_deck", hexc("6e7c5a"), 0.8, var=0.06)
    white = S.pbr("tk_white", hexc("eef0f0"), 0.45, var=0.03)
    win = S.pbr("tk_win", hexc("1f2a36"), 0.1, var=0)
    pipe = S.pbr("tk_pipe", hexc("c9b26a"), 0.5, 0.4, var=0.03)
    fun = S.pbr("tk_funnel", hexc("3a3f46"), 0.5, var=0.03)
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    hb = length * 0.078
    SEA._boat_hull(bm, length, hb, 7.0, -10.0, 0, 1, bow_rise=2.2)
    S.bm_box(bm, (0, length * 0.02, 7.15), (hb * 1.7, length * 0.68, 0.3), 2)
    for k in (-1, 0, 1):
        S.bm_box(bm, (k * 2.2, length * 0.02, 7.9), (0.7, length * 0.62, 0.7), 5)
    for k in range(5):
        S.bm_box(bm, (0, -length * 0.22 + k * length * 0.11, 9.0), (hb * 1.2, 0.6, 2.4), 5)
    S.bm_box(bm, (0, length * 0.05, 9.5), (2.5, 2.5, 3.0), 5)
    yb = -length * 0.39
    S.bm_box(bm, (0, yb, 16.0), (hb * 1.75, length * 0.1, 17.0), 3)
    S.bm_box(bm, (0, yb + length * 0.03, 24.2), (hb * 2.05, length * 0.045, 2.2), 3)
    for k in range(5):
        S.bm_box(bm, (0, yb + length * 0.0505, 9.8 + k * 3.2), (hb * 1.6, 0.2, 1.1), 4)
        S.bm_box(bm, (0, yb - length * 0.0505, 9.8 + k * 3.2), (hb * 1.6, 0.2, 1.1), 4)
    S.bm_box(bm, (0, yb + length * 0.054, 24.2), (hb * 1.9, 0.2, 1.3), 4)
    S.bm_box(bm, (0, yb - length * 0.035, 28.0), (5.0, 6.0, 8.0), 6)
    S.bm_box(bm, (0, yb + length * 0.01, 29.0), (0.5, 0.5, 9.0), 3)
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [hull, anti, deckm, white, win, pipe, fun]), parent=root)
    if wake:
        SEA.make_wake(name + "_wake", root, length * 1.4, hb * 0.6, y0=-length / 2)
    return root


def make_riverboat(name, length=RB_L):
    """White paddlewheel riverboat: low hull, four stacked decks with dark window bands and white rails,
    red stern paddlewheel, two black stacks, pilothouse. Origin = waterline midships, bow +Y."""
    white = S.pbr("rb_white", hexc("f4f4f0"), 0.45, var=0.03)
    win = S.pbr("rb_win", hexc("2a3644"), 0.1, var=0)
    red = S.pbr("rb_red", hexc("b8322c"), 0.5, var=0.04)
    blk = S.pbr("rb_black", hexc("1d1f22"), 0.5, var=0)
    gold = S.pbr("rb_gold", hexc("caa24a"), 0.35, 0.8, var=0)
    hullc = S.pbr("rb_hull", hexc("e9e7e0"), 0.5, var=0.03)
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    hb = 8.0
    SEA._boat_hull(bm, length, hb, 2.4, -2.6, 0, 0, bow_rise=0.6)
    for k, (z, w, l0, l1) in enumerate(((2.4, 7.6, -0.42, 0.36), (5.6, 7.3, -0.4, 0.32), (8.8, 7.0, -0.36, 0.26),
                                        (12.0, 6.2, -0.26, 0.12))):
        y0, y1 = length * l0, length * l1
        S.bm_box(bm, (0, (y0 + y1) / 2, z + 1.5), (w * 2, y1 - y0, 3.0), 1)
        S.bm_box(bm, (0, (y0 + y1) / 2, z + 1.55), (w * 2 + 0.08, (y1 - y0) * 0.94, 1.3), 2)
        S.bm_box(bm, (0, (y0 + y1) / 2, z + 3.1), (w * 2 + 1.0, y1 - y0 + 1.0, 0.25), 1)
        S.bm_box(bm, (0, (y0 + y1) / 2, z + 3.9), (w * 2 + 0.9, y1 - y0 + 0.8, 0.12), 1)
    S.bm_box(bm, (0, length * 0.02, 17.6), (7.0, 6.0, 2.6), 1)
    S.bm_box(bm, (0, length * 0.02, 17.7), (7.1, 5.6, 1.1), 2)
    for sx in (-1, 1):
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.9, radius2=0.9, depth=12.0)
        bmesh.ops.translate(bm, vec=(sx * 2.4, length * 0.2, 19.0), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 4
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=1.4, radius2=1.0, depth=1.0)
        bmesh.ops.translate(bm, vec=(sx * 2.4, length * 0.2, 25.4), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 5
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [hullc, white, win, red, blk, gold]), parent=root)
    # stern paddlewheel (red) + housing
    pw = L.link(bpy.data.objects.new(name + "_wheel", None))
    pw.parent = root
    pw.location = (0, -length / 2 - 4.5, 3.0)
    bm = bmesh.new()
    for k in range(12):
        a = 2 * math.pi * k / 12
        v = S.bm_box(bm, (0, 0, 0), (13.0, 0.35, 2.2), 0)
        bmesh.ops.translate(bm, vec=(0, 0, 4.2), verts=v)
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "X"))
    for sx in (-1, 1):
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=5.4, radius2=5.4, depth=0.4)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, vec=(sx * 6.4, 0, 0), verts=r["verts"])
    S.obj(name + "_wheel_m", S.mesh_from_bm(name + "_wheel_m", bm, [red]), parent=pw)
    bm = bmesh.new()
    for sx in (-1, 1):
        S.bm_box(bm, (sx * 7.2, -length / 2 - 3.0, 4.0), (0.6, 8.0, 0.6), 0)
    S.obj(name + "_arms", S.mesh_from_bm(name + "_arms", bm, [white]), parent=root)
    return root, pw


def make_pilot_boat(name):
    return SEA.make_tug(name, hexc("f08a24"), 17.0)


# ================================================================ city river world
def _heading(y, side=1.0):
    """Angle (rot z) of the river direction (+Y) at y, from the centre-line slope."""
    d = (C.xc(y + 5.0) - C.xc(y - 5.0)) / 10.0
    return -math.atan(d)


def build_wharf(rng):
    """Pile wharf along the east quay (WHARF y range): deck at quay level, 22 m into the river, shed + bollards."""
    deck = S.pbr("wharf_deck", hexc("b9b2a6"), 0.85, var=0.06, var_scale=0.3)
    pile = S.pbr("wharf_pile", hexc("6b665e"), 0.8, var=0.05)
    shed = S.corrugated_mat("wharf_shed", hexc("d7d0c2"), metal=0.2)
    roof = S.corrugated_mat("wharf_roof", hexc("7e858c"))
    bol = S.pbr("bollard_r", hexc("2d3136"), 0.5, var=0)
    bm = bmesh.new()
    y = WHARF[0]
    step = 10.0
    while y < WHARF[1] - 0.1:
        x = C.xr(y + step / 2)
        S.bm_box(bm, (x - 11.0, y + step / 2, -0.6), (24.0, step + 0.05, 1.2), 0)
        for px in (x - 21.0, x - 12.0, x - 3.0):
            S.bm_box(bm, (px, y + step / 2, (WZ - 2.0 - 1.2) / 2), (0.8, 0.8, -WZ + 0.8), 1)
        S.bm_box(bm, (x - 22.4, y + step / 2, 0.35), (0.7, 0.7, 0.7), 2)
        y += step
    S.obj("wharf", S.mesh_from_bm("wharf", bm, [deck, pile, bol]))
    yc = (WHARF[0] + WHARF[1]) / 2
    x = C.xr(yc)
    # gable roof: separate mesh so it can be rotated with the quay
    bm = bmesh.new()
    S.bm_prism_x(bm, -60.0, 60.0, [(-5.2, 8.0), (5.2, 8.0), (0.0, 10.4)], 0)
    r = S.obj("wharf_shed_roof", S.mesh_from_bm("wharf_shed_roof", bm, [roof]), (x - 6.0, yc, 0.0))
    r.rotation_euler = (0, 0, math.pi / 2 + _heading(yc))
    # shed body (rotated with the quay)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 4.0), (9.0, 120.0, 8.0), 0)
    sb = S.obj("wharf_shed", S.mesh_from_bm("wharf_shed_b", bm, [shed]), (x - 6.0, yc, 0.0))
    sb.rotation_euler = (0, 0, _heading(yc))


def moor_riverboat():
    yc = (WHARF[0] + WHARF[1]) / 2 + 5.0
    rb, wheel = make_riverboat("riverboat")
    rb.location = (C.xr(yc) - 22.6 - 8.6, yc, WZ)
    rb.rotation_euler = (0, 0, _heading(yc))
    return rb


def keyed_ship(make, name, y0, y1, off, T, reverse=False, **kw):
    sh = make(name, **kw) if kw else make(name)
    root = sh[0] if isinstance(sh, tuple) else sh

    def fn(f):
        u = (f - 1) / float(max(1, T - 1))
        y = y0 + (y1 - y0) * u
        return (C.xc(y) + off, y, WZ)
    SEA.path_keys(root, fn, T, step=4)
    return root


def build_river_world(ctx, p, riverboat=True, sun=None):
    sp = dict(p)
    if sun is not None:
        sp.setdefault("sun_az", sun)
    brs, rng = C.build_city_world(ctx, sp)
    w = bpy.data.objects.get("water")
    if w is not None:
        w.data.materials[0] = river_water_mat()
    C._flow_traffic(ctx, brs, rng, per_lane=4)
    C.embankment_traffic(ctx, rng, n=18)
    build_wharf(rng)
    out = {"brs": brs, "rng": rng}
    if riverboat:
        out["riverboat"] = moor_riverboat()
    # a moored barge tow far downriver on the west bank, for scale
    return out


def _cam(ctx, loc, tgt, lens=30, clip=1.0):
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


def _keys(ctx, p, c0, t0, c1, t1, lens=30, clip=1.0):
    c0, t0 = p.get("cam0", c0), p.get("tgt0", t0)
    c1, t1 = p.get("cam1", c1), p.get("tgt1", t1)
    _cam(ctx, c0, t0, p.get("lens", lens), clip)
    A._cam_keys(ctx, [(1, c0, t0), (ctx.frames, c1, t1)])


def _ring(name, r, w, mat, loc, parent=None):
    bm = bmesh.new()
    C._annulus(bm, r, w, 72)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), loc, parent=parent)
    o.visible_shadow = False
    return o


def pulse_ring(name, loc, f_on, r, w, col="19c9b4", parent=None, peak=5.0, T=900):
    m, sock = L.add_mat(name, hexc(col), 0.0)
    o = _ring(name, r, w, m, loc, parent)
    sock_keys(sock, [(1, 0.0), (f_on, 0.0), (f_on + 8, peak)])
    f = f_on + 8
    while f < T + 30:
        L.kf_socket(sock, f + 15, peak * 0.55, "LINEAR")
        L.kf_socket(sock, f + 30, peak, "LINEAR")
        f += 30
    set_keys(o, "scale", [1, f_on, f_on + 10], [(0.6, 0.6, 1), (0.6, 0.6, 1), (1, 1, 1)], "BEZIER")
    return o


def ripples(ctx, name, loc, f0, T, r1=120.0, period=40, count=3, col="19c9b4", w=3.0):
    """Expanding fading rings from loc, again and again from f0 (radar / traffic-service pulses)."""
    for k in range(count):
        m, sock = L.add_mat("%s_%d" % (name, k), hexc(col), 0.0)
        o = _ring("%s_%d" % (name, k), 1.0, w / r1, m, loc)
        o.scale = (0, 0, 0)
        fr, sc, st = [1], [(0, 0, 1)], []
        f = f0 + k * period // count
        keys_s = [(1, 0.0)]
        while f < T + period:
            fr += [f, f + period - 1]
            sc += [(0.05 * r1, 0.05 * r1, 1), (r1, r1, 1)]
            keys_s += [(f, 0.0), (f + 3, 4.0), (f + period - 1, 0.0)]
            f += period
        set_keys(o, "scale", fr, sc, "LINEAR")
        sock_keys(sock, keys_s)


# ================================================================ BUILDERS (city river)
def b_river_hook(ctx, p):
    """View from the east bank across the river: the white riverboat moored at the wharf (right) and the tanker
    mid-river in the distance (far half of the channel, parallel to the banks). Anchors: riverboat, tanker."""
    T = ctx.frames
    w = build_river_world(ctx, p, riverboat=p.get("riverboat", True))
    ty0, ty1 = p.get("ty", (470.0, 400.0))
    tk = keyed_ship(make_tanker, "tanker", ty0, ty1, p.get("toff", -85.0), T, wake=True)
    if w.get("riverboat") is not None:
        _anc(ctx, "riverboat", (0.0, 10.0, 20.0), parent=w["riverboat"])
    _anc(ctx, "tanker", (0.0, 0.0, 26.0), parent=tk)
    _keys(ctx, p, (215.0, -60.0, 40.0), (40.0, 300.0, 0.0), (208.0, -40.0, 37.0), (35.0, 310.0, 0.0), 30)


def b_river_map(ctx, p):
    """High, almost top-down view of the river stretch; the tanker moves mid-channel with a teal ring.
    Anchor: tanker."""
    T = ctx.frames
    build_river_world(ctx, p, riverboat=False)
    y0, y1 = p.get("ty", (330.0, 250.0))
    tk = keyed_ship(make_tanker, "tanker", y0, y1, p.get("toff", -40.0), T, wake=True)
    m, sock = L.add_mat("map_ring", hexc("19c9b4"), 0.0)
    rg = _ring("map_ring", 120.0, 7.0, m, (0, 0, 1.0), parent=tk)
    sock_keys(sock, [(1, 0.0), (8, 0.0), (18, 5.0)])
    f = 18
    while f < T + 30:
        L.kf_socket(sock, f + 15, 2.6, "LINEAR")
        L.kf_socket(sock, f + 30, 5.0, "LINEAR")
        f += 30
    _anc(ctx, "tanker", (0.0, 0.0, 10.0), parent=tk)
    yc = (y0 + y1) / 2
    _keys(ctx, p, (C.xc(yc) - 20.0, yc - 520.0, 1500.0), (C.xc(yc) - 20.0, yc + 40.0, WZ),
          (C.xc(yc) - 20.0, yc - 470.0, 1380.0), (C.xc(yc) - 20.0, yc + 30.0, WZ), 30, 20.0)


def b_river_help_v2(ctx, p):
    """Tanker mid-river; on `pilot_cue` a pilot boat comes alongside, on `watch_cue` the traffic-service radar tower
    on the west bank sends teal pulses over the river, on `tug_cue` two tugs move in and nudge the hull.
    Anchors: pilot, tower, tug, tanker."""
    T = ctx.frames
    w = build_river_world(ctx, p, riverboat=False)
    f_p = ctx.word_time(p.get("pilot_cue", "pilots"), 0.25)
    f_w = ctx.word_time(p.get("watch_cue", "watches"), 0.5)
    f_t = ctx.word_time(p.get("tug_cue", "tugs"), 0.8)
    y0, y1 = p.get("ty", (60.0, 150.0))
    off = p.get("toff", -30.0)
    tk = keyed_ship(make_tanker, "tanker", y0, y1, off, T, wake=True)

    def ship_at(f):
        u = (f - 1) / float(max(1, T - 1))
        y = y0 + (y1 - y0) * u
        return Vector((C.xc(y) + off, y, WZ))
    hb = TANKER_L * 0.078
    # pilot boat: from the east side towards the tanker's starboard (east) side, then keeps station
    pb = make_pilot_boat("pilot")
    fr, locs, rots = [], [], []
    for f in range(1, T + 1, 3):
        sp = ship_at(f)
        dock = sp + Vector((hb + 7.0, 10.0, 0.0))
        u = L.smooth((f - (f_p - 30)) / 70.0)
        start = sp + Vector((140.0, -60.0, 0.0))
        pos = start.lerp(dock, u)
        fr.append(f)
        locs.append(tuple(pos))
        rots.append((0, 0, -0.5 * (1 - u)))
    set_keys(pb, "location", fr, locs, "LINEAR")
    set_keys(pb, "rotation_euler", fr, rots, "LINEAR")
    _anc(ctx, "pilot", (0.0, 0.0, 8.0), parent=pb)
    # traffic-service tower on the west bank (radar mast) + ripples over the water
    tyc = (y0 + y1) / 2 + 140.0
    tx = C.xl(tyc) - 30.0
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 12.0), (8.0, 8.0, 24.0), 0)
    S.bm_box(bm, (0, 0, 25.5), (10.0, 10.0, 3.0), 1)
    S.bm_box(bm, (0, 0, 25.5), (10.2, 10.2, 1.4), 2)
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.4, radius2=0.4, depth=8.0)
    bmesh.ops.translate(bm, vec=(0, 0, 31.0), verts=r["verts"])
    S.obj("vts", S.mesh_from_bm("vts", bm, [S.pbr("vts_w", hexc("eceeee"), 0.5, var=0.03),
                                            S.pbr("vts_w2", hexc("dfe3e6"), 0.5, var=0),
                                            S.pbr("vts_win", hexc("23303c"), 0.1, var=0)]), (tx, tyc, 0.0))
    rad = L.link(bpy.data.objects.new("radar", None))
    rad.location = (tx, tyc, 35.0)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0), (9.0, 0.6, 0.9), 0)
    S.obj("radar_bar", S.mesh_from_bm("radar_bar", bm, [S.pbr("radar_m", hexc("f4f4f4"), 0.4, var=0)]), parent=rad)
    set_keys(rad, "rotation_euler", [1, T], [(0, 0, 0), (0, 0, 2 * math.pi * T / 60.0)], "LINEAR")
    ripples(ctx, "vts_rip", (tx + 40.0, tyc, WZ + 0.6), f_w, T, r1=260.0, period=45, count=3, w=4.0)
    _anc(ctx, "tower", (tx, tyc, 34.0))
    # tugs: from downriver / upriver to the tanker's port (west) side, then push
    side = float(p.get("tug_side", -1))
    for k, (dy, sy) in enumerate(((-45.0, -1), (45.0, 1))):
        tg = SEA.make_tug("tug%d" % k, hexc("c8452f") if k == 0 else hexc("2f6db3"), 22.0)
        fr, locs, rots = [], [], []
        for f in range(1, T + 1, 3):
            sp = ship_at(f)
            u = L.smooth((f - f_t + 10) / 60.0)
            # tug_side -1 = port (west, far side from the usual east-bank camera), +1 = starboard (near side)
            target = sp + Vector((side * (hb + 6.0), dy, 0.0))
            start = sp + Vector((side * (hb + 90.0), dy + sy * 130.0, 0.0))
            pos = start.lerp(target, u)
            fr.append(f)
            locs.append(tuple(pos))
            rots.append((0, 0, side * math.pi / 2 * u + (1 - u) * (0.0 if sy < 0 else math.pi)))
        set_keys(tg, "location", fr, locs, "LINEAR")
        set_keys(tg, "rotation_euler", fr, rots, "LINEAR")
        if k == 0:
            _anc(ctx, "tug", (0.0, 0.0, 6.0), parent=tg)
    _anc(ctx, "tanker", (0.0, 0.0, 26.0), parent=tk)
    yc = (y0 + y1) / 2
    _keys(ctx, p, (C.xc(yc) + 230.0, yc - 300.0, 150.0), (C.xc(yc) - 40.0, yc + 90.0, WZ),
          (C.xc(yc) + 210.0, yc - 270.0, 140.0), (C.xc(yc) - 40.0, yc + 110.0, WZ), 30, 2.0)


def b_river_outro(ctx, p):
    """Golden-hour riverfront: the tanker passes mid-river (no riverboat); the camera cranes up. Anchor: tanker."""
    T = ctx.frames
    p = dict(p)
    p.setdefault("hdri", False)
    build_river_world(ctx, p, riverboat=False, sun=p.get("sun_az", 60.0))
    golden(ctx, p.get("sun_elev", 5.0), p.get("sun_az", 60.0))
    y0, y1 = p.get("ty", (-250.0, -170.0))
    tk = keyed_ship(make_tanker, "tanker", y0, y1, p.get("toff", -20.0), T, wake=True)
    _anc(ctx, "tanker", (0.0, 0.0, 26.0), parent=tk)
    _keys(ctx, p, (190.0, -420.0, 16.0), (-100.0, -170.0, 4.0), (230.0, -520.0, 120.0), (-95.0, -140.0, -2.0), 30)


def golden(ctx, elev, az):
    """Turn the procedural daylight into late golden hour: low sun, warm lamp, slightly brighter exposure."""
    w = ctx.scene.world
    for n in (w.node_tree.nodes if w else []):
        if n.type == "TEX_SKY":
            n.sun_elevation = math.radians(elev)
            print("[v2 river] golden: sky sun elevation", elev)
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.data.type == "SUN":
            o.rotation_euler = (math.radians(90.0 - elev), 0.0, math.radians(az))
            o.data.color = (1.0, 0.6, 0.34)
            o.data.energy = o.data.energy * 0.9
    ctx.scene.view_settings.exposure = ctx.scene.view_settings.exposure + 0.35


# ================================================================ ferry deck (takeaway)
def b_ferry_deck_v2(ctx, p):
    """Ferry deck moored by the east quay: the life-jacket locker glows on `jacket_cue`, green exit arrows light up
    one by one towards the door on `exit_cue`. Anchors: jackets, exit."""
    T = ctx.frames
    build_river_world(ctx, p, riverboat=False)
    f_j = ctx.word_time(p.get("jacket_cue", "life"), 0.5)
    f_x = ctx.word_time(p.get("exit_cue", "nearest"), 0.8)
    yc = p.get("y", -120.0)
    x0 = C.xr(yc) - 30.0
    z0 = WZ + 3.0
    root = L.link(bpy.data.objects.new("ferry", None))
    root.location = (x0, yc, z0)
    root.rotation_euler = (0, 0, _heading(yc))
    deck = S.pbr("ferry_deck", hexc("4f7a5e"), 0.8, var=0.06, var_scale=1.5, bump=0.05)
    white = S.pbr("ferry_white", hexc("f2f3f2"), 0.5, var=0.02)
    win = S.pbr("ferry_win", hexc("6f9cc0"), 0.08, var=0)
    rail = S.pbr("ferry_rail", hexc("e8eaea"), 0.4, 0.4, var=0)
    navy = S.pbr("ferry_navy", hexc("1e3a5f"), 0.5, var=0.03)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, -1.6), (16.0, 60.0, 3.2), 4)       # hull block (under the deck)
    S.bm_box(bm, (0, 0, 0.0), (16.0, 60.0, 0.12), 0)       # deck
    S.bm_box(bm, (5.5, 0, 1.6), (5.0, 40.0, 3.2), 1)        # cabin (east half)
    S.bm_box(bm, (3.0 - 0.02, 0, 1.9), (0.06, 38.0, 1.3), 2)  # window band
    S.bm_box(bm, (5.5, 0, 3.3), (5.6, 41.0, 0.2), 1)
    for k in range(31):                                     # rail posts on the river (west) side
        S.bm_box(bm, (-7.8, -29.0 + k * 1.94, 0.55), (0.06, 0.06, 1.1), 3)
    S.bm_box(bm, (-7.8, 0, 1.1), (0.08, 60.0, 0.08), 3)
    S.bm_box(bm, (-7.8, 0, 0.6), (0.05, 60.0, 0.05), 3)
    S.obj("ferry_b", S.mesh_from_bm("ferry_b", bm, [deck, white, win, rail, navy]), parent=root)
    # door (end of the cabin) + green exit sign (no text: a lit green panel)
    bm = bmesh.new()
    S.bm_box(bm, (3.0 - 0.04, 14.0, 1.05), (0.08, 1.3, 2.1), 0)
    S.obj("door", S.mesh_from_bm("door", bm, [S.pbr("door_m", hexc("5b6b78"), 0.4, 0.3, var=0)]), parent=root)
    gm, gsock = L.add_mat("exit_sign", hexc("22d36a"), 0.4)
    bm = bmesh.new()
    S.bm_box(bm, (2.94, 14.0, 2.45), (0.04, 1.0, 0.36), 0)
    S.obj("exit_sign", S.mesh_from_bm("exit_sign", bm, [gm]), parent=root)
    # life-jacket locker (white box, open front) with orange jackets
    bm = bmesh.new()
    S.bm_box(bm, (2.5, -2.0, 0.75), (1.0, 2.4, 1.5), 0)
    S.obj("locker", S.mesh_from_bm("locker", bm, [white]), parent=root)
    jm = S.pbr("jacket", hexc("ff7a1a"), 0.55, var=0.05)
    jg, jsock = L.add_mat("jacket_glow", hexc("ffb04a"), 0.0)
    bm = bmesh.new()
    for i in range(3):
        for j in range(2):
            S.bm_box(bm, (1.96, -2.8 + i * 0.8, 0.45 + j * 0.62), (0.12, 0.62, 0.5), 0)
            S.bm_box(bm, (1.9, -2.8 + i * 0.8, 0.45 + j * 0.62), (0.02, 0.06, 0.48), 1)
    S.obj("jackets", S.mesh_from_bm("jackets", bm, [jm, S.pbr("strap", hexc("2b2d31"), 0.6, var=0)]), parent=root)
    bm = bmesh.new()
    S.bm_box(bm, (1.92, -2.0, 0.78), (0.02, 2.5, 1.45), 0)
    S.obj("jacket_halo", S.mesh_from_bm("jacket_halo", bm, [jg]), parent=root)
    sock_keys(jsock, [(1, 0.0), (f_j, 0.0), (f_j + 8, 1.6)])
    f = f_j + 8
    while f < T + 30:
        L.kf_socket(jsock, f + 15, 0.8, "LINEAR")
        L.kf_socket(jsock, f + 30, 1.6, "LINEAR")
        f += 30
    # green chevrons on the deck from the camera end towards the door
    for k in range(6):
        cm, cs = L.add_mat("chev%d" % k, hexc("22d36a"), 0.0)
        bm = bmesh.new()
        pts = [(-0.6, 0.0), (0.0, 0.6), (0.6, 0.0), (0.6, -0.35), (0.0, 0.25), (-0.6, -0.35)]
        vs = [bm.verts.new((x, y, 0.0)) for x, y in pts]
        bm.faces.new(vs)
        o = S.obj("chev%d" % k, S.mesh_from_bm("chev%d" % k, bm, [cm]), (1.4, 1.5 + k * 2.0, 0.08), parent=root)
        o.visible_shadow = False
        fk = f_x + 4 * k
        sock_keys(cs, [(1, 0.0), (fk, 0.0), (fk + 6, 3.0)])
    sock_keys(gsock, [(1, 0.4), (f_x, 0.4), (f_x + 8, 4.0)])
    _anc(ctx, "jackets", (2.0, -2.0, 1.4), parent=root)
    _anc(ctx, "exit", (2.9, 14.0, 2.5), parent=root)
    # camera on deck (local coords -> world)
    def wpt(v):
        return tuple(root.matrix_world @ Vector(v)) if False else tuple(
            Vector((x0, yc, z0)) + (Matrix.Rotation(_heading(yc), 3, "Z") @ Vector(v)))
    # from outside the river-side rail, looking across the deck at the cabin, with the city skyline behind it
    # (wide lens: the life-jacket locker at y -2 and the exit door at y 14 both stay in frame)
    _keys(ctx, p, wpt((-10.0, -22.0, 5.5)), wpt((2.4, 4.0, 1.3)), wpt((-8.0, -17.0, 4.6)), wpt((2.4, 5.0, 1.4)), 18, 0.1)


# ================================================================ open water: momentum
def b_momentum_v2(ctx, p):
    """Tanker on open water with the engine going astern: white froth boils at the stern from `reverse_cue`, it
    slows; from `length_cue` translucent teal ghost hulls appear one after another ahead of it (ship lengths
    travelled before it stops). Anchors: ship, ghost."""
    T = ctx.frames
    w = ST.build_ocean(ctx, dict(p, islands=p.get("islands", [(-1400.0, 2600.0, 180.0), (1700.0, 3600.0, 240.0)])),
                       fog=0.00004, fog_start=1500.0)
    f_r = ctx.word_time(p.get("reverse_cue", "reverse"), 0.5)
    f_l = ctx.word_time(p.get("length_cue", "travel"), 0.7)
    tk = make_tanker("tanker", wake=True)
    v0 = 6.0 / ctx.fps
    ys = []
    y = 0.0
    for f in range(1, T + 1):
        dec = 0.0 if f < f_r else min(1.0, (f - f_r) / 90.0) * 0.45
        y += v0 * (1.0 - dec)
        ys.append(y)
    fr = list(range(1, T + 1, 3))
    set_keys(tk, "location", fr, [(0.0, ys[f - 1], 0.0) for f in fr], "LINEAR")
    # froth at the stern from f_r
    froth = ST.cloud_mat("froth_m", 0.7, "ffffff")
    rng = random.Random(12)
    for k in range(14):
        bl = [(rng.uniform(-3, 3), rng.uniform(-3, 3), 0.0, rng.uniform(2.0, 3.6), 0.35) for _ in range(4)]
        o = ST.puffs("froth%d" % k, bl, froth, parent=tk)
        o.visible_shadow = False
        x0 = rng.uniform(-9, 9)
        p0 = (x0, -TANKER_L / 2 - 4.0, 0.0)
        p1 = (x0 * 1.8, -TANKER_L / 2 - 30.0 - rng.uniform(0, 20), 0.0)
        ST.loop_move(o, p0, p1, T, f_r + 2 * k, 50, phase=rng.random(), grow=10)
    # ghost hulls ahead
    gm, gsock = L.add_mat("ghost", hexc("39e0d0"), 0.0)
    em, esock = L.add_mat("ghost_edge", hexc("aef7f0"), 0.0)
    n = p.get("ghosts", 5)
    for k in range(n):
        bm = bmesh.new()
        SEA._boat_hull(bm, TANKER_L * 0.98, TANKER_L * 0.078, 7.0, -0.5, 0, 0, bow_rise=2.2)
        yk = ys[-1] + TANKER_L * (k + 1) * 1.02
        o = S.obj("ghost%d" % k, S.mesh_from_bm("ghost%d" % k, bm, [gm]), (0.0, yk, 0.15))
        o.visible_shadow = False
        fk = f_l + int(k * max(8, (T - f_l - 20) / float(n)))
        set_keys(o, "scale", [1, fk, fk + 8], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "BEZIER")
    sock_keys(gsock, [(1, 0.45)])
    _anc(ctx, "ship", (0.0, 0.0, 26.0), parent=tk)
    _anc(ctx, "ghost", (0.0, ys[-1] + TANKER_L * 2.0, 8.0))
    yl = ys[-1]
    c0 = p.get("cam0", (-270.0, -210.0, 120.0))
    t0 = p.get("tgt0", (0.0, 80.0, 0.0))
    c1 = p.get("cam1", (-260.0, yl - 240.0, 130.0))
    t1 = p.get("tgt1", (0.0, yl + 80.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 30), 2.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


# ================================================================ rudder close-up
def flat_arrow(name, length, width, mat, parent=None):
    """Arrow lying in the XY plane pointing +X (origin in the middle)."""
    hl = length * 0.42
    w, hw = width * 0.5, width * 1.15
    pts = [(-length / 2, -w), (length / 2 - hl, -w), (length / 2 - hl, -hw), (length / 2, 0.0),
           (length / 2 - hl, hw), (length / 2 - hl, w), (-length / 2, w)]
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0.0)) for x, y in pts]
    bm.faces.new(vs)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def b_rudder_v2(ctx, p):
    """The stern of the tanker seen from above through clear water: spinning propeller and rudder (turned), amber
    flow arrows stream past and are bent by the rudder. On `lose_cue` the flow fades out, the propeller stops and
    the rudder swings loose and settles. Anchors: rudder, prop."""
    T = ctx.frames
    rng = random.Random(4)
    S.daylight(ctx, p.get("sun_az", -30.0), 45.0, hdri=True)
    L.fog(0.00004, S.HAZE, start=1500.0)
    C.horizon_haze(ctx.scene, lo=0.02, hi=0.2)
    om = ST.ocean_mat(wave=0.02, bump=0.12, dist=2.5)
    cx0, cx1, cy0, cy1, E = -150.0, 270.0, -150.0, 150.0, 30000.0
    for nm, (cx, cy, sx, sy) in (("n", (0, cy1 + E / 2, 2 * E, E)), ("s", (0, cy0 - E / 2, 2 * E, E)),
                                 ("w", (cx0 - E / 2, 0, E, cy1 - cy0)), ("e", (cx1 + E / 2, 0, E, cy1 - cy0))):
        S.plane_obj("sea_far_" + nm, sx, sy, (cx, cy, 0.0), om)
    S.plane_obj("sea_clear", 420.0, 300.0, (60.0, 0.0, 0.0), clear_water_mat())
    sand = S.pbr("seabed", hexc("c9b98f"), 0.95, var=0.12, var_scale=0.05, bump=0.1)
    S.plane_obj("seabed", 440.0, 320.0, (60.0, 0.0, -26.0), sand)
    f_lose = ctx.word_time(p.get("lose_cue", "lose"), 0.55)
    f_pow = ctx.word_time(p.get("power_cue", "power"), 0.35)
    # ship: bow towards -X (root rotated +90 deg), stern end at x = 0
    tk = make_tanker("tanker", wake=False)
    tk.rotation_euler = (0, 0, math.pi / 2)
    tk.location = (-TANKER_L / 2 + 6.0, 0.0, 0.0)
    # propeller (x 6..) + rudder
    prop = L.link(bpy.data.objects.new("prop", None))
    prop.location = (9.0, 0.0, -6.0)
    bronze = S.pbr("prop_bronze", hexc("c9963e"), 0.3, 0.9, var=0)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=1.0, radius2=0.6, depth=2.4)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    for k in range(4):
        a = 2 * math.pi * k / 4
        v = S.bm_box(bm, (0, 0, 2.6), (0.35, 1.6, 3.6), 0)
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 2.6), matrix=Matrix.Rotation(0.5, 3, "Z"))
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "X"))
    S.obj("prop_m", S.mesh_from_bm("prop_m", bm, [bronze], smooth=False), parent=prop)
    spin = []
    ang = 0.0
    fr = list(range(1, T + 1, 2))
    for f in fr:
        rate = 0.5 if f < f_lose else max(0.0, 0.5 * (1 - (f - f_lose) / 30.0))
        ang += rate * 2
        spin.append((ang, 0.0, 0.0))
    set_keys(prop, "rotation_euler", fr, spin, "LINEAR")
    # shaft
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.5, radius2=0.5, depth=8.0)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    S.obj("shaft", S.mesh_from_bm("shaft", bm, [S.pbr("shaft_m", hexc("5a5f66"), 0.4, 0.8, var=0)]), (5.0, 0, -6.0))
    rud = L.link(bpy.data.objects.new("rudder", None))
    rud.location = (14.5, 0.0, -6.0)
    rm = S.pbr("rudder_m", hexc("8c3a2c"), 0.55, var=0.05)
    bm = bmesh.new()
    S.bm_box(bm, (3.2, 0.0, 0.0), (6.4, 0.9, 10.5), 0)
    S._ellipsoid(bm, (0.0, 0.0, 0.0), (0.6, 0.6, 5.25), 0, 12, 8)
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.45, radius2=0.45, depth=6.0)
    bmesh.ops.translate(bm, vec=(0, 0, 8.0), verts=r["verts"])
    S.obj("rudder_m", S.mesh_from_bm("rudder_m", bm, [rm]), parent=rud)
    turn = math.radians(p.get("turn", 28.0))
    rk = [1, max(2, f_pow - 10), f_lose, f_lose + 10, f_lose + 22, f_lose + 34, f_lose + 48, f_lose + 64, T]
    rv = [turn, turn, turn, turn * 0.2, turn * 0.75, turn * 0.15, turn * 0.45, turn * 0.25, turn * 0.3]
    set_keys(rud, "rotation_euler", rk, [(0, 0, v) for v in rv], "BEZIER")
    # flow arrows at two depths, both sides of the rudder; before the rudder straight along +X, after it bent
    am = glow("flow_amber", "ffab1f", 2.2)
    f_off = f_lose + 18
    for k in range(10):
        z = -3.0 if k % 2 == 0 else -9.0
        yy = (-1 if k % 4 < 2 else 1) * rng.uniform(2.0, 6.5)
        a1 = flat_arrow("fa%d" % k, 7.0, 1.6, am)
        ST.loop_move(a1, (-45.0, yy, z), (12.0, yy, z), T, 2 + 3 * k, 46, phase=k * 0.1, f_off=f_off, grow=6)
        a2 = flat_arrow("fb%d" % k, 7.0, 1.6, am)
        dx, dy = math.cos(turn), math.sin(turn)
        p0 = Vector((21.0, yy * 0.6 + 1.5, z))
        p1 = p0 + Vector((dx, dy, 0)) * 46.0
        a2.rotation_euler = (0, 0, turn)
        ST.loop_move(a2, tuple(p0), tuple(p1), T, 2 + 3 * k + 23, 46, phase=k * 0.1, f_off=f_off, grow=6)
    _anc(ctx, "rudder", (3.0, 0.0, 4.5), parent=rud)
    _anc(ctx, "prop", (0.0, 0.0, 0.0), parent=prop)
    _keys(ctx, p, (48.0, -44.0, 26.0), (13.0, 0.0, -7.0), (44.0, -40.0, 24.0), (14.0, 0.0, -7.0), 30, 1.0)


# ================================================================ rudder -> open sea -> whip -> river (one beat)
SEA_O = Vector((0.0, 32000.0, 0.0))      # the open-sea set sits 32 km north of the river city (out of its view)


def _smoother(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def _yaw(d, ang):
    c, s = math.cos(ang), math.sin(ang)
    return Vector((d.x * c - d.y * s, d.x * s + d.y * c, d.z))


def open_sea_mat():
    """Open-sea water for close views: glossy, two layers of moving ripples (sky reflections break up), slight
    colour variation; little emission so it does not read as a flat blue card."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("open_sea_near")
        p.inputs["Roughness"].default_value = 0.05
        p.inputs["Specular IOR Level"].default_value = 0.6
        p.inputs["Emission Color"].default_value = hexc("1d86ad")
        p.inputs["Emission Strength"].default_value = 0.08
        tc = N.new("ShaderNodeTexCoord")
        bumps = []
        prev = None
        for sc_, st_, w1 in ((0.09, 0.45, 6.0), (0.55, 0.22, 14.0)):
            mp = N.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (1.0, 0.45, 1.0)
            Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
            nz = N.new("ShaderNodeTexNoise")
            nz.noise_dimensions = "4D"
            nz.inputs["Scale"].default_value = sc_
            nz.inputs["Detail"].default_value = 6.0
            nz.inputs["Roughness"].default_value = 0.6
            Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
            L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
            L.kf_socket(nz.inputs["W"], 900, w1, "LINEAR")
            b = N.new("ShaderNodeBump")
            b.inputs["Strength"].default_value = st_
            b.inputs["Distance"].default_value = 0.5
            Lk.new(nz.outputs["Fac"], b.inputs["Height"])
            if prev is not None:
                Lk.new(prev.outputs["Normal"], b.inputs["Normal"])
            prev = b
        Lk.new(prev.outputs["Normal"], p.inputs["Normal"])
        fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.004, 0.18)
        fac2, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.04, 0.08)
        c1 = S._mul_col(N, Lk, tuple(hexc("1a7aa3")), fac)
        Lk.new(S._mul_col(N, Lk, c1, fac2), p.inputs["Base Color"])
        return S._finish(m, p.outputs[0])
    return _m("open_sea_near", mk)


def b_rudder_whip_v2(ctx, p):
    """One continuous camera for "no room for failure":
    A  low stern-quarter view of a tanker in ballast on open sea (top of the rudder and the propeller above the
       water): propeller turning, foam wash, amber flow arrows on the water bent by the turned rudder; on `lose_cue`
       the flow and the wash fade, the propeller stops, the rudder swings loose;
    B  from `crane_cue` the camera cranes up to a high view of the tanker alone on wide open sea, a teal ring
       ("room to drift") opens around it on `space_cue` while it yaws a little;
    C  fast eased whip (motion blur) that lands on `river_cue` in the river city: the tanker mid-channel with the
       east bank + wharf (dock, no riverboat) close on the right and the metro bridge just ahead; amber rings on
       `bank_cue`, `bridge_cue`, `dock_cue`.
    The sea set is built at SEA_O (32 km north of the city) inside the same scene; the camera jumps between the two
    sets at mid-whip (sub-frame keys, so the motion blur never streaks across the jump).
    Anchors: rudder, room, bank, bridge, dock, tanker."""
    T = ctx.frames
    sc = ctx.scene
    rng = random.Random(4)
    # ---- river city (sky, sun, fog, haze come from the city world)
    w = build_river_world(ctx, p, riverboat=False)
    f_lose = ctx.word_time(p.get("lose_cue", "lose"), 0.5)
    f_pow = ctx.word_time(p.get("power_cue", "power"), 0.42)
    f_crane = ctx.word_time(p.get("crane_cue", "sea"), 0.54) - 6
    f_space = ctx.word_time(p.get("space_cue", "space"), 0.6)
    f_river = ctx.word_time(p.get("river_cue", "river"), 0.7)
    f_bank = ctx.word_time(p.get("bank_cue", "bank"), 0.76)
    f_bridge = ctx.word_time(p.get("bridge_cue", "bridge"), 0.81)
    f_dock = ctx.word_time(p.get("dock_cue", "dock"), 0.86)
    f_cut = f_river - 4                      # last sea frame
    w_out, w_in = 8, 11                      # whip frames before / after the cut

    # ================= A/B: open-sea set (rig: local +X = aft = world -Y)
    rig = L.link(bpy.data.objects.new("sea_rig", None))
    rig.location = SEA_O
    rig.rotation_euler = (0, 0, -math.pi / 2)
    drift = math.radians(p.get("drift_deg", 7.0))
    set_keys(rig, "rotation_euler", [1, f_lose, T], [(0, 0, -math.pi / 2), (0, 0, -math.pi / 2),
                                                    (0, 0, -math.pi / 2 + drift)], "BEZIER")

    def RW(v):
        """rig-local -> world (ignores the small drift)."""
        return SEA_O + Vector((v[1], -v[0], v[2]))
    # one opaque open sea (no see-through patch: the tanker rides high in ballast, so the top of the rudder and
    # the propeller show above the water)
    om = open_sea_mat()
    o = S.plane_obj("open_sea", 24000.0, 24000.0, (0.0, 0.0, 0.0), om)
    o.parent = rig
    LIFT = p.get("lift", 6.5)
    tk = make_tanker("tanker_sea", wake=False)
    tk.parent = rig
    tk.rotation_euler = (0, 0, math.pi / 2)
    tk.location = (-TANKER_L / 2 + 6.0, 0.0, LIFT)
    for ch in tk.children:
        ch.visible_shadow = False         # no hard hull shadow polygon on the water
    # foam wash behind the propeller; fades (shrinks) after lose
    wk = SEA.make_wake("sea_wash", tk, TANKER_L * 1.5, 3.0, y0=-TANKER_L / 2 - 9.0)
    wk.location = (0.0, 0.0, -LIFT)
    set_keys(wk, "scale", [1, f_lose, f_lose + 45], [(1, 1, 1), (1, 1, 1), (0.6, 0.0, 1.0)], "BEZIER")
    froth = ST.cloud_mat("froth_m", 0.7, "ffffff")
    for k in range(10):
        bl = [(rng.uniform(-2, 2), rng.uniform(-2, 2), 0.0, rng.uniform(1.4, 2.6), 0.3) for _ in range(4)]
        o = ST.puffs("froth%d" % k, bl, froth, parent=rig)
        o.visible_shadow = False
        y_ = rng.uniform(-4, 4)
        ST.loop_move(o, (11.0, y_, 0.1), (60.0 + rng.uniform(0, 25), y_ * 2.2, 0.1), T, 2 + 4 * k, 44,
                     phase=rng.random(), f_off=f_lose + 20, grow=8)
    # propeller + shaft + rudder (rig-local, as in rudder_v2, lifted with the hull)
    prop = L.link(bpy.data.objects.new("prop", None))
    prop.parent = rig
    prop.location = (9.0, 0.0, -6.0 + LIFT)
    bronze = S.pbr("prop_bronze", hexc("d9a443"), 0.3, 0.9, var=0)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=1.0, radius2=0.6, depth=2.4)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    for k in range(4):
        a = 2 * math.pi * k / 4
        v = S.bm_box(bm, (0, 0, 2.6), (0.35, 1.6, 3.6), 0)
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 2.6), matrix=Matrix.Rotation(0.5, 3, "Z"))
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "X"))
    pm = S.obj("prop_m", S.mesh_from_bm("prop_m", bm, [bronze], smooth=False), parent=prop)
    pm.visible_shadow = False
    spin, ang = [], 0.0
    fr = list(range(1, T + 1, 2))
    for f in fr:
        rate = 0.5 if f < f_lose else max(0.0, 0.5 * (1 - (f - f_lose) / 30.0))
        ang += rate * 2
        spin.append((ang, 0.0, 0.0))
    set_keys(prop, "rotation_euler", fr, spin, "LINEAR")
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.5, radius2=0.5, depth=8.0)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    o = S.obj("shaft", S.mesh_from_bm("shaft", bm, [S.pbr("shaft_m", hexc("5a5f66"), 0.4, 0.8, var=0)]),
              (5.0, 0, -6.0 + LIFT))
    o.parent = rig
    rud = L.link(bpy.data.objects.new("rudder", None))
    rud.parent = rig
    rud.location = (14.5, 0.0, -6.0 + LIFT)
    rm = S.pbr("rudder_m2", hexc("c0392b"), 0.5, var=0.05)
    bm = bmesh.new()
    S.bm_box(bm, (3.2, 0.0, 0.0), (6.4, 0.9, 10.5), 0)
    S._ellipsoid(bm, (0.0, 0.0, 0.0), (0.6, 0.6, 5.25), 0, 12, 8)
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.45, radius2=0.45, depth=6.0)
    bmesh.ops.translate(bm, vec=(0, 0, 8.0), verts=r["verts"])
    ro = S.obj("rudder_m", S.mesh_from_bm("rudder_m", bm, [rm]), parent=rud)
    ro.visible_shadow = False
    turn = math.radians(p.get("turn", 28.0))
    rk = [1, max(2, f_pow - 10), f_lose, f_lose + 10, f_lose + 22, f_lose + 34, f_lose + 48, f_lose + 64, T]
    rv = [turn, turn, turn, turn * 0.2, turn * 0.75, turn * 0.15, turn * 0.45, turn * 0.25, turn * 0.3]
    set_keys(rud, "rotation_euler", rk, [(0, 0, v) for v in rv], "BEZIER")
    # flow arrows on the water along both sides; behind the rudder they turn with it
    am = glow("flow_amber_w", "ffab1f", 2.2)
    f_off = f_lose + 18
    for k in range(8):
        z = 0.35
        sy = -1 if k % 2 == 0 else 1
        yy = sy * rng.uniform(9.0, 14.0)
        a1 = flat_arrow("fa%d" % k, 9.0, 2.2, am, parent=rig)
        ST.loop_move(a1, (-60.0, yy, z), (8.0, yy, z), T, 2 + 5 * k, 50, phase=k * 0.12, f_off=f_off, grow=6)
        a2 = flat_arrow("fb%d" % k, 9.0, 2.2, am, parent=rig)
        dx, dy = math.cos(turn), math.sin(turn)
        p0 = Vector((24.0, yy * 0.35 + 3.0, z))
        p1 = p0 + Vector((dx, dy, 0)) * 50.0
        a2.rotation_euler = (0, 0, turn)
        ST.loop_move(a2, tuple(p0), tuple(p1), T, 2 + 5 * k + 25, 50, phase=k * 0.12, f_off=f_off, grow=6)
    # room to drift: teal ring around the ship on open water (rig-local, centred on the hull)
    pulse_ring("room_ring", (-TANKER_L / 2 + 6.0, 0.0, 0.5), f_space, 330.0, 7.0, parent=rig, peak=4.0, T=T)
    # far islands for depth (world coords, ahead of the ship)
    palms = SEA._palm_templates(rng)
    for k, (x, y, r_) in enumerate(p.get("islands", [(-1700.0, 3400.0, 200.0), (2100.0, 5200.0, 260.0)])):
        ST.island("sisl%d" % k, SEA_O.x + x, SEA_O.y + y, r_, rng, palms)
    _anc(ctx, "rudder", (3.2, 0.0, 3.5), parent=rud)
    _anc(ctx, "room", (-TANKER_L / 2 + 6.0 + 330.0, 0.0, 0.5), parent=rig)      # near (aft) edge of the ring

    # ================= C: river set
    y0, y1 = p.get("ty", (200.0, 250.0))
    toff = p.get("toff", 50.0)
    tkr = keyed_ship(make_tanker, "tanker_river", y0, y1, toff, T, wake=True)
    yb = C.bridge_y("metro")
    yd = p.get("dock_y", 175.0)
    yk = p.get("bank_y", 360.0)
    amber = "ffab1f"
    pulse_ring("bank_ring", (C.xr(yk) - 4.0, yk, 0.6), f_bank, 26.0, 3.0, col=amber, T=T)
    pulse_ring("bridge_ring", (C.xc(yb) + 30.0, yb, C.DECK_Z + 0.8), f_bridge, 40.0, 4.0, col=amber, T=T)
    pulse_ring("dock_ring", (C.xr(yd) - 22.0, yd, 0.7), f_dock, 26.0, 3.0, col=amber, T=T)
    _anc(ctx, "bank", (C.xr(yk) - 4.0, yk, 3.0))
    _anc(ctx, "bridge", (C.xc(yb) + 30.0, yb, C.DECK_Z + 6.0))
    _anc(ctx, "dock", (C.xr(yd) - 22.0, yd, 3.0))
    _anc(ctx, "tanker", (0.0, 0.0, 26.0), parent=tkr)

    # ================= camera: one baked path, jump at mid-whip
    a0 = (p.get("a_cam0", (64.0, -24.0, 9.0)), p.get("a_tgt0", (6.0, 0.0, 5.0)), p.get("a_lens0", 22.0))
    a1 = (p.get("a_cam1", (48.0, -17.0, 7.5)), p.get("a_tgt1", (8.0, 0.0, 4.5)), p.get("a_lens1", 24.0))
    b0 = (p.get("b_cam0", (-330.0, -760.0, 520.0)), p.get("b_tgt0", (0.0, 60.0, 0.0)), p.get("b_lens0", 24.0))
    b1 = (p.get("b_cam1", (-300.0, -720.0, 500.0)), p.get("b_tgt1", (0.0, 70.0, 0.0)), p.get("b_lens1", 24.0))
    ym = (y0 + y1) / 2
    c0 = (p.get("c_cam0", (C.xc(ym) + 128.0, ym - 330.0, 118.0)), p.get("c_tgt0", (C.xc(ym) + 66.0, ym + 230.0, WZ)),
          p.get("c_lens0", 17.0))
    c1 = (p.get("c_cam1", (C.xc(ym) + 120.0, ym - 280.0, 106.0)), p.get("c_tgt1", (C.xc(ym) + 66.0, ym + 260.0, WZ)),
          p.get("c_lens1", 17.0))
    f_b0 = f_crane + p.get("crane_frames", 40)
    whip_ang = math.radians(p.get("whip_deg", 80.0))

    def lerp_pose(pa, pb, u):
        return (Vector(pa[0]).lerp(Vector(pb[0]), u), Vector(pa[1]).lerp(Vector(pb[1]), u),
                pa[2] + (pb[2] - pa[2]) * u)

    def pose(f):
        if f <= f_cut + 0.5:
            if f <= f_crane:
                u = (f - 1) / float(max(1, f_crane - 1))
                cl, ct, ln = lerp_pose(a0, a1, L.smooth(u))
                cl, ct = RW(cl), RW(ct)
            elif f <= f_b0:
                ua = (f_crane - 1) / float(max(1, f_crane - 1))
                cl0, ct0, ln0 = lerp_pose(a0, a1, 1.0)
                cl0, ct0 = RW(cl0), RW(ct0)
                u = _smoother((f - f_crane) / float(f_b0 - f_crane))
                bl, bt = SEA_O + Vector(b0[0]), SEA_O + Vector(b0[1])
                cl = cl0.lerp(bl, u)
                cl.z = cl0.z + (bl.z - cl0.z) * (u ** 0.8)
                ct = ct0.lerp(bt, u)
                ln = ln0 + (b0[2] - ln0) * u
            else:
                u = (f - f_b0) / float(max(1, f_cut - f_b0))
                cl, ct, ln = lerp_pose(b0, b1, u)
                cl, ct = SEA_O + cl, SEA_O + ct
            # whip out: ease-in yaw to the right
            uw = (f - (f_cut + 0.5 - w_out)) / float(w_out)
            if uw > 0:
                d = _yaw(ct - cl, -whip_ang * min(1.0, uw) ** 2)
                ct = cl + d
            return cl, ct, ln
        u = (f - (f_cut + 0.5)) / float(max(1, T - f_cut))
        cl, ct, ln = lerp_pose(c0, c1, L.smooth(min(1.0, u * 1.0)))
        uw = (f - (f_cut + 0.5)) / float(w_in)
        if uw < 1:
            d = _yaw(ct - cl, whip_ang * (1 - max(0.0, uw)) ** 2)
            ct = cl + d
        return cl, ct, ln

    cam = ctx.camera((0, 0, 10), target=(0, 10, 0), lens=26)
    cam.data.clip_start = 0.5
    cam.data.clip_end = 40000.0
    frs = [float(f) for f in range(1, T + 1)]
    frs += [f_cut + 0.49, f_cut + 0.51]
    frs.sort()
    poses = [pose(f if abs(f - round(f)) > 0.001 else int(round(f))) for f in frs]
    set_keys(cam, "location", frs, [tuple(q[0]) for q in poses], "LINEAR")
    set_keys(ctx.cam_target, "location", frs, [tuple(q[1]) for q in poses], "LINEAR")
    set_keys(cam.data, "lens", frs, [(q[2],) for q in poses], "LINEAR")
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 river] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 river] rudder_whip: crane %d-%d, cut after %d, river cue %d" % (f_crane, f_b0, f_cut, f_river))


# ================================================================ tight bend (ILLUSTRATION)
BEND_R, BEND_W = 330.0, 190.0


def bend_center(t):
    """River centre line: up the west leg (x = -R), round the top (centre (0, 0)), down the east leg. t in [0, 1]."""
    lw = 900.0
    total = 2 * lw + math.pi * BEND_R
    s = t * total
    if s < lw:
        return Vector((-BEND_R, -lw + s, 0.0)), Vector((0, 1, 0))
    s -= lw
    if s < math.pi * BEND_R:
        a = math.pi - s / BEND_R
        return Vector((BEND_R * math.cos(a), BEND_R * math.sin(a), 0.0)), Vector((math.sin(a), -math.cos(a), 0))
    s -= math.pi * BEND_R
    return Vector((BEND_R, -s, 0.0)), Vector((0, -1, 0))


def bend_dist(x, y):
    if y >= 0:
        return abs(math.hypot(x, y) - BEND_R)
    return min(abs(x + BEND_R), abs(x - BEND_R))


def b_bend_v2(ctx, p):
    """Tight horseshoe bend seen from high above (labelled ILLUSTRATION): amber current arrows follow the bend,
    a tanker crabs through the turn, a second ship waits below the bend on `turn_cue`. Anchors: bend, ship, wait."""
    T = ctx.frames
    rng = random.Random(p.get("seed", 13))
    S.daylight(ctx, p.get("sun_az", -30.0), 42.0, hdri=True)
    L.fog(0.00005, S.HAZE, start=1800.0)
    C.horizon_haze(ctx.scene, lo=0.0, hi=0.08)
    S.plane_obj("water", 12000, 12000, (0, 0, 0.0), river_water_mat())
    # land: height grid with the river carved out
    n_x, n_y, step = 200, 270, 22.0
    x0, y0 = -n_x * step / 2, -2600.0
    bm = bmesh.new()
    vs = []
    for j in range(n_y + 1):
        row = []
        for i in range(n_x + 1):
            x, y = x0 + i * step, y0 + j * step
            d = bend_dist(x, y)
            h = BEND_W / 2
            if d < h - 12:
                z = -6.0
            elif d < h + 10:
                z = -6.0 + 8.0 * L.smooth((d - (h - 12)) / 22.0)
            else:
                z = 2.0 + 1.5 * L.smooth((d - h - 10) / 40.0)
            row.append(bm.verts.new((x, y, z)))
        vs.append(row)
    for j in range(n_y):
        for i in range(n_x):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    land = S.obj("land", S.mesh_from_bm("land", bm, [S.ground_mat()], smooth=True))
    # far land: a frame of four planes around the grid (edge height 3.5), never over the river
    fm = C.far_ground_mat("far_bend", hexc("7a8a5a"), 5.0)
    gx0, gx1, gy0, gy1 = x0, x0 + n_x * step, y0, y0 + n_y * step
    E = 20000.0
    for nm, (cx, cy, sx, sy) in (("n", (0, gy1 + E / 2, 2 * E, E)), ("s", (0, gy0 - E / 2, 2 * E, E)),
                                 ("w", (gx0 - E / 2, (gy0 + gy1) / 2, E, gy1 - gy0)),
                                 ("e", (gx1 + E / 2, (gy0 + gy1) / 2, E, gy1 - gy0))):
        S.plane_obj("far_" + nm, sx, sy, (cx, cy, 3.45), fm)
    # trees along the banks + a small town inside the bend
    tt = S.tree_templates(rng)
    pts = []
    for _ in range(1400):
        x, y = rng.uniform(-2100, 2100), rng.uniform(-2550, 3200)
        d = bend_dist(x, y)
        if BEND_W / 2 + 18 < d < BEND_W / 2 + 120 and rng.random() < 0.85:
            pts.append((x, y))
        elif d > BEND_W / 2 + 200 and rng.random() < 0.12:
            pts.append((x, y))
    trees = S.scatter(tt, pts, rng, (1.4, 2.2), prefix="btree")
    for t in trees:
        t.location.z = 3.4
    ht = S.house_templates(rng)
    for k in range(70):
        x, y = rng.uniform(-150, 150), rng.uniform(-900, 120)
        if bend_dist(x, y) < BEND_W / 2 + 40:
            continue
        S.obj("bhouse", ht[rng.randrange(len(ht))], (x, y, 3.4), (0, 0, rng.choice((0.0, math.pi / 2))),
              (1.5, 1.5, 1.5))
    # current arrows along the centre line (flowing from the east leg round to the west leg)
    am = glow("cur_amber", "ffab1f", 2.0)
    for k in range(16):
        t0 = (k + rng.random() * 0.5) / 16.0
        lane = (-1 if k % 2 else 1) * BEND_W * 0.22
        pa, ta = bend_center(1.0 - t0)
        pb, tb = bend_center(max(0.0, 1.0 - t0 - 0.05))
        side_a = Vector((-ta.y, ta.x, 0))
        side_b = Vector((-tb.y, tb.x, 0))
        p0 = pa + side_a * lane + Vector((0, 0, 0.6))
        p1 = pb + side_b * lane + Vector((0, 0, 0.6))
        d = p1 - p0
        a = flat_arrow("cur%d" % k, 34.0, 9.0, am)
        a.rotation_euler = (0, 0, math.atan2(d.y, d.x))
        ST.loop_move(a, tuple(p0), tuple(p1), T, 2 + 2 * k, 70, phase=rng.random(), grow=14)
    # tanker crabbing round the top of the bend (heading turned ~14 deg towards the inside)
    tk = make_tanker("tanker", wake=True)
    tk.scale = (0.85, 0.85, 0.85)
    lw = 900.0
    total = 2 * lw + math.pi * BEND_R
    ta0 = (lw + math.pi * BEND_R * 0.22) / total
    ta1 = (lw + math.pi * BEND_R * 0.42) / total
    fr = list(range(1, T + 1, 3))
    locs, rots = [], []
    crab = math.radians(p.get("crab", 14.0))
    for f in fr:
        u = (f - 1) / float(max(1, T - 1))
        pc, tg = bend_center(ta0 + (ta1 - ta0) * u)
        locs.append(tuple(pc + Vector((0, 0, 0.0))))
        rots.append((0, 0, math.atan2(-tg.x, tg.y) + crab))
    set_keys(tk, "location", fr, locs, "LINEAR")
    set_keys(tk, "rotation_euler", fr, rots, "LINEAR")
    # second ship waiting below the bend (east leg), amber pulse ring on turn_cue
    f_w = ctx.word_time(p.get("turn_cue", "turns"), 0.75)
    wt = SEA.make_merchant("waiting", 120.0)
    wt.location = (BEND_R, -620.0, 0.0)
    wt.rotation_euler = (0, 0, math.pi)
    pulse_ring("wait_ring", (BEND_R, -620.0, 0.8), f_w, 85.0, 6.0, "ffab1f", T=T)
    _anc(ctx, "ship", (0.0, 0.0, 20.0), parent=tk)
    _anc(ctx, "wait", (BEND_R, -620.0, 15.0))
    _anc(ctx, "bend", (0.0, BEND_R, 5.0))
    _keys(ctx, p, (120.0, -2050.0, 1650.0), (0.0, -20.0, 0.0), (90.0, -1900.0, 1560.0), (0.0, 0.0, 0.0), 34, 20.0)


# ================================================================ icy alley (metaphor)
def b_ice_alley_v2(ctx, p):
    """A toy delivery truck slides gently along a glossy ice-blue alley lined with parked cars; it wobbles and stops
    short (no contact). Anchor: truck."""
    T = ctx.frames
    rng = random.Random(p.get("seed", 6))
    S.daylight(ctx, p.get("sun_az", 20.0), 40.0, hdri=True)
    L.fog(0.0008, S.HAZE, start=120.0)
    ice = S.pbr("alley_ice", hexc("cfe9f6"), 0.06, var=0.1, var_scale=0.4, coat=1.0)
    S.plane_obj("alley", 11.0, 400.0, (0, 120.0, 0.0), ice)
    snow = S.pbr("snow_edge", hexc("f4f8fb"), 0.7, var=0.04)
    S.plane_obj("ground", 4000, 4000, (0, 0, -0.03), S.pbr("ground_s", hexc("e9eef2"), 0.8, var=0.05, var_scale=0.05))
    bm = bmesh.new()
    for sx in (-1, 1):
        for k in range(80):
            y = -40.0 + k * 4.0 + rng.uniform(-1, 1)
            S._ellipsoid(bm, (sx * 5.6, y, 0.0), (0.7, 2.4, 0.35), 0, 10, 6)
    S.obj("snowbanks", S.mesh_from_bm("snowbanks", bm, [snow], smooth=True))
    walls = [S.facade_mat("alley_%d" % i, hexc(c), hexc("33465a"), 3.2, 3.4, 0.45) for i, c in
             enumerate(("b0573f", "c8a27c", "8c4a3a", "d9cfc0", "9b6a4f"))]
    roof = S.pbr("alley_roof", hexc("eef2f5"), 0.7, var=0.03)
    bm = bmesh.new()
    for sx in (-1, 1):
        y = -60.0
        while y < 320.0:
            w = rng.uniform(10, 18)
            h = rng.uniform(9, 22)
            C._fast_box(bm, sx * 13.5, y + w / 2, 0.0, 14.0, w - 0.4, h, 0, rng.randrange(5))
            C._fast_box(bm, sx * 13.5, y + w / 2, h, 14.4, w, 0.4, 0, 5)
            y += w
    S.obj("alley_bldgs", S.mesh_from_bm("alley_bldgs", bm, walls + [roof]))
    for sx in (-1, 1):
        for k in range(14):
            y = -10.0 + k * 7.2 + rng.uniform(-0.6, 0.6)
            L.make_car("pc%d_%d" % (sx, k), loc=(sx * 3.6, y, 0.0), rot_z=0.0 if sx > 0 else math.pi,
                       headlights=False, glow=False)
    S._repaint_kenney()
    tr = L.make_car("truck", loc=(0.0, 0.0, 0.0), rot_z=0.0, headlights=False, glow=False,
                    model=p.get("truck", "delivery"), scale=1.25)
    f_s = int(T * 0.88)
    fr = list(range(1, T + 1, 2))
    locs, rots = [], []
    y_end = p.get("y_end", 46.0)
    for f in fr:
        u = min(1.0, (f - 1) / float(max(1, f_s - 1)))
        y = y_end * (1 - (1 - u) ** 2)
        wob = math.sin(f / 9.0) * (1 - u) * 0.16
        locs.append((0.25 * math.sin(f / 13.0) * (1 - u), y, 0.0))
        rots.append((0, 0, wob))
    set_keys(tr.obj, "location", fr, locs, "LINEAR")
    set_keys(tr.obj, "rotation_euler", fr, rots, "LINEAR")
    _anc(ctx, "truck", (0.0, 0.0, 3.0), parent=tr.obj)
    c0 = p.get("cam0", (0.9, -10.0, 3.4))
    c1 = p.get("cam1", (0.9, y_end - 10.5, 3.2))
    _cam(ctx, c0, (0.0, 8.0, 1.2), p.get("lens", 30), 0.1)
    A._cam_keys(ctx, [(1, c0, (0.0, 8.0, 1.2)), (T, c1, (0.0, y_end + 9.0, 1.1))])


S.V2_BUILDERS.update({
    "river_hook": b_river_hook,
    "river_map": b_river_map,
    "momentum_v2": b_momentum_v2,
    "bend_v2": b_bend_v2,
    "rudder_v2": b_rudder_v2,
    "rudder_whip_v2": b_rudder_whip_v2,
    "ice_alley_v2": b_ice_alley_v2,
    "river_help_v2": b_river_help_v2,
    "ferry_deck_v2": b_ferry_deck_v2,
    "river_outro": b_river_outro,
})

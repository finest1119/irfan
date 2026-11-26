"""Everyday Decoded (Page 3) v2 builders. Registers into scene_lib_v2.V2_BUILDERS (loaded by render_episode_v2.py
from episode.json "render": {"libs": ["scene_lib_v2_ed"]}, dir page3/blender).

Builders (Track A batch 01, 26 Nov 2026):
  ed_airport_fog_v2   view hook | outro      persistent airport world in dense ground fog (cheap shader distance fog,
                                             no volumetrics), runway edge / centerline / approach lights glowing
                                             through; outro: fog lifts from `lift_cue` (fog nodes keyframed).
  ed_cockpit_fog_v2   view approach | close  scene_lib_v2_air cockpit_workload_v2 in fog; approach adds the ILS
                                             beams (teal localizer sheet + amber glideslope sheet) from `beams_cue`.
  ils_beams_v2        view top | side | touchdown   localizer fan / glideslope wedge / CAT III touchdown in fog.
  bag_belt_v2         view counter | tag | scan_arch | screen | sort | makeup | apron   indoor baggage hall
                                             (lightbox lit, never a void) + apron belt loader in the airport world.
Builders (Track A batch 02, 26 Nov 2026, for 28 Nov):
  mw_kitchen_v2       view hook | inside | bounce | water | mesh | light | outro   bright kitchen set + countertop
                                             microwave (perforated door screen shader, cut-away top / left side,
                                             magnetron, teal wave packets bouncing, water molecules, 12 cm standing
                                             wave vs tiny holes, amber light squiggles slipping out).
  checkout_v2         view hook | bars | scan | lookup | first | today | outro   supermarket set (shelves, 3 lanes,
                                             belts, flush scanner + red laser fans, UPC-style label art with no
                                             digits, data pulses arcing to a store computer, warm 1974 lane + gum pack).
  lift_v2             view hook | rig | balance | motor | pass | safety | outro   scene_lib_v2_tower city + a mid-rise
                                             with the lift shaft cut open: car with riders, counterweight (top plates
                                             glow amber on load_cue), ropes over a yellow sheave, machine room,
                                             safety wedges clamp the rail on clamp_cue.
No 3D text (barcode bars are graphics, no digits); non-graphic; textures generated in memory (<= 512 px).
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Matrix

import scene_lib as L
import scene_lib_v2 as S
import scene_lib_v2_air as A
from scene_lib import hexc, kf

FOG_COL = hexc("cdd5dc")      # bright overcast grey-blue
TEAL = hexc("19d3c0")
AMBER = hexc("ffb000")


# ================================================================ small helpers
def _interp(idb, mode="LINEAR"):
    """Blender 5.3 ignores the new-keyframe interpolation pref: set it on every key explicitly."""
    for fc in A._fcurves(idb):
        for kp in fc.keyframe_points:
            kp.interpolation = mode


def _cyclic(idb):
    for fc in A._fcurves(idb):
        fc.modifiers.new("CYCLES")


def _show(o, f_on, f_off=None):
    """Scale-based show/hide with CONSTANT keys."""
    kf(o, "scale", 1, Vector((0.001, 0.001, 0.001)))
    kf(o, "scale", f_on, Vector((1, 1, 1)))
    if f_off:
        kf(o, "scale", f_off, Vector((0.001, 0.001, 0.001)))
    _interp(o, "CONSTANT")


def _cyl(bm, c, r, length, axis="X", seg=12, mi=0):
    rr = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=length)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=rr["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=rr["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=Vector(c), verts=rr["verts"])
    if mi:
        for f in {f for v in rr["verts"] for f in v.link_faces}:
            f.material_index = mi
    return rr["verts"]


def _rbox(bm, c, size, r=0.04, seg=2, mi=0):
    """Rounded box (bevel baked into the mesh: no per-object modifier)."""
    before = set(bm.faces)
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    for v in vs:
        v.co = Vector((v.co.x * size[0] + c[0], v.co.y * size[1] + c[1], v.co.z * size[2] + c[2]))
    edges = list({e for v in vs for e in v.link_edges})
    if r > 0:
        bmesh.ops.bevel(bm, geom=vs + edges, offset=r, segments=seg, affect="EDGES", profile=0.5)
    for f in bm.faces:
        if f not in before:
            f.material_index = mi


def _mesh(name, build, mats, smooth=False):
    bm = bmesh.new()
    build(bm)
    return S.mesh_from_bm(name, bm, mats, smooth)


def _empty(name, loc=(0, 0, 0), parent=None):
    e = L.link(bpy.data.objects.new(name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    return e


def _fog_nodes():
    """The MULTIPLY node of every scene_lib._fog_wrap (inputs[1] = -density * scale)."""
    for m in bpy.data.materials:
        nt = m.node_tree
        if nt is None:
            continue
        for n in nt.nodes:
            if n.type == "MATH" and n.operation == "MULTIPLY" and n.inputs[0].is_linked:
                src = n.inputs[0].links[0].from_node
                if src.type == "MATH" and src.operation == "MAXIMUM":
                    yield m, n


class Fog:
    """Dense shader distance fog for a reused builder: build_world() calls L.fog() itself, so L.fog is swapped for
    the duration of the build (materials bake the density when they are created)."""

    def __init__(self, density, start=25.0, color=FOG_COL):
        self.d, self.s, self.c = density, start, color

    def __enter__(self):
        self._orig = L.fog
        d, c, s, orig = self.d, self.c, self.s, self._orig
        orig(d, c, start=s)
        L.fog = lambda *a, **k: orig(d, c, start=s)
        return self

    def __exit__(self, *exc):
        L.fog = self._orig
        return False


def fog_world(ctx, fac=1.0, exposure=-0.15, keys=None):
    """Insert a bright overcast fog background into the current (HDRI) world: Mix(HDRI, fog, fac).
    fac 1 = pure fog sky + flat overcast light (no hard sun); keys [(frame, fac)] animate it (fog lifting)."""
    sc = ctx.scene
    w = sc.world
    if w is None:
        w = bpy.data.worlds.new("fogw")
        sc.world = w
    nt = w.node_tree
    N, Lk = nt.nodes, nt.links
    out = next(n for n in N if n.type == "OUTPUT_WORLD")
    src = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].is_linked else None
    fbg = N.new("ShaderNodeBackground")
    # slight vertical gradient: brighter overhead, fog colour at the horizon
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Generated"], sep.inputs[0])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 0.8
    Lk.new(sep.outputs["Z"], mr.inputs["Value"])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs["A"].default_value = FOG_COL
    top = tuple(min(1.0, c * 1.22) for c in FOG_COL[:3]) + (1.0,)
    mx.inputs["B"].default_value = top
    Lk.new(mr.outputs["Result"], mx.inputs["Factor"])
    Lk.new(mx.outputs["Result"], fbg.inputs["Color"])
    fbg.inputs["Strength"].default_value = 1.0
    mix = N.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = fac
    if src is not None:
        Lk.new(src, mix.inputs[1])
    Lk.new(fbg.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], out.inputs["Surface"])
    if keys:
        for f, v in keys:
            L.kf_socket(mix.inputs[0], f, v)
        _interp(nt, "BEZIER")
    sc.view_settings.exposure = exposure
    # a soft, weak sun for shape (overcast): only the HDRI path has no lamp
    if not any(o.type == "LIGHT" and o.data.type == "SUN" for o in sc.objects):
        sun = S.sun_lamp(55.0, -35.0, 0.9 if keys is None else 1.6)
        sun.data.angle = math.radians(25.0)
    return mix


def lift_fog(f0, f1, ratio=0.06):
    """Fog lifting: every fogged material's density goes from its baked value to value * ratio over f0..f1."""
    n_ = 0
    for m, n in list(_fog_nodes()):
        v = n.inputs[1].default_value
        L.kf_socket(n.inputs[1], 1, v)
        L.kf_socket(n.inputs[1], f0, v)
        L.kf_socket(n.inputs[1], f1, v * ratio)
        _interp(m.node_tree, "BEZIER")
        n_ += 1
    print("[ed] fog lift on %d materials, frames %d-%d" % (n_, f0, f1))


# ================================================================ airport lights (pierce the fog)
def runway_lights(strength=1.0):
    """Edge, centerline, touchdown-zone, threshold and approach lights for runway 34 (x = 0, y 0..1600)."""
    RW, RL = S.RWY_W, S.RWY_LEN
    fs = 0.15      # lights are fogged much less than surfaces, so they glow through
    white = L.emissive("ed_edge_w", hexc("fff1d6"), 38.0 * strength, fs)
    cl = L.emissive("ed_cl_w", hexc("f4f8ff"), 30.0 * strength, fs)
    green = L.emissive("ed_thr_g", hexc("4dff7a"), 30.0 * strength, fs)
    red = L.emissive("ed_end_r", hexc("ff3b30"), 30.0 * strength, fs)
    appr = L.emissive("ed_appr", hexc("fff4d8"), 45.0 * strength, fs)
    pole = S.pbr("ed_pole", hexc("c9ccd0"), 0.5, 0.4, var=0)

    def edge(bm):
        for y in range(0, int(RL) + 1, 30):
            for sx in (-1, 1):
                S._ellipsoid(bm, (sx * (RW / 2 + 1.5), y, 0.95), (0.22, 0.22, 0.16), 0, 8, 5)
    S.obj("ed_edge", _mesh("ed_edge", edge, [white]))

    def centre(bm):
        for y in range(15, int(RL), 15):
            S.bm_box(bm, (0, y, 0.33), (0.35, 0.6, 0.05))
        for y in range(60, 900, 30):         # touchdown-zone barrettes
            for sx in (-1, 1):
                for k in range(3):
                    S.bm_box(bm, (sx * (9.0 + 1.5 * k), y, 0.33), (0.35, 0.5, 0.05))
    S.obj("ed_cl", _mesh("ed_cl", centre, [cl]))

    def thr(bm):
        for k in range(16):
            S._ellipsoid(bm, (-RW / 2 + 1.5 + k * 2.8, -1.0, 0.5), (0.25, 0.2, 0.18), 0, 8, 5)
    S.obj("ed_thr", _mesh("ed_thr", thr, [green]))

    def endl(bm):
        for k in range(16):
            S._ellipsoid(bm, (-RW / 2 + 1.5 + k * 2.8, RL + 1.0, 0.5), (0.25, 0.2, 0.18), 0, 8, 5)
    S.obj("ed_endl", _mesh("ed_endl", endl, [red]))

    def apl(bm):
        for k in range(1, 13):           # 390 m of approach lights (houses beyond)
            y = -30 * k - 30 + 0.6
            z = 0.25 + 0.35 * k + 0.2 if k < 10 else 3.6
            for xx in (-6, -3, 0, 3, 6):
                S._ellipsoid(bm, (xx, y, z), (0.32, 0.22, 0.26), 0, 8, 5)
            if k == 10:                 # crossbars
                for xx in (-15, -12, -9, 9, 12, 15):
                    S._ellipsoid(bm, (xx, y, z), (0.32, 0.22, 0.26), 0, 8, 5)
    S.obj("ed_apl", _mesh("ed_apl", apl, [appr]))

    def poles(bm):
        for k in range(10, 13):
            y = -30 * k - 30 + 0.6
            S.bm_box(bm, (0, y, 1.75), (0.22, 0.22, 3.5))
            S.bm_box(bm, (0, y, 3.45), (13, 0.18, 0.14))
    S.obj("ed_apl_poles", _mesh("ed_apl_poles", poles, [pole]))


def _airliner_on_glide(ctx, name, y0, y1, gear=True, flaps=1.0, x_keys=None):
    root, parts = A.make_airliner_v2(ctx, name, gear_down=gear)
    if flaps:
        A.flaps_to(parts, 1, 2, flaps, flaps)
    T = ctx.frames
    keys = []
    for f in list(range(1, T + 1, 4)) + [T]:
        u = (f - 1) / max(1, T - 1)
        y = y0 + (y1 - y0) * u
        x = x_keys(u) if x_keys else 0.0
        keys.append((f, (x, y, A.glide_alt(y) + 3.8)))
    tr = A._track(name + "_track", keys)
    _interp(tr, "LINEAR")
    root.parent = tr
    root.rotation_euler = (math.radians(2.5), 0, 0)
    return root, parts, tr


# ================================================================ ed_airport_fog_v2
def b_ed_airport_fog_v2(ctx, p):
    """Airport world in dense ground fog. view "hook": airliner on a stable approach seen from behind, the runway
    barely visible ahead but its lights glowing through. view "outro": stock airport_outro, fog lifts on lift_cue."""
    view = p.get("view", "hook")
    T = ctx.frames
    dens = p.get("fog", 0.007 if view == "hook" else 0.003)
    if view == "outro":
        with Fog(dens, start=p.get("fog_start", 30.0)):
            A.b_airport_outro(ctx, p)
            runway_lights()
        fl = ctx.word_time(p.get("lift_cue", "trust"), 0.2)
        f1 = min(T, fl + int(p.get("lift_s", 3.0) * ctx.fps))
        lift_fog(fl, f1, p.get("lift_ratio", 0.06))
        fog_world(ctx, 1.0, exposure=p.get("exposure", -0.3), keys=[(1, 0.97), (fl, 0.97), (f1, 0.15)])
        return
    with Fog(dens, start=p.get("fog_start", 30.0)):
        A._world(ctx, p)
        runway_lights()
        v = 70.0 / ctx.fps
        y1 = p.get("y1", -650.0)
        y0 = y1 - v * T
        root, parts, tr = _airliner_on_glide(ctx, "al", y0, y1)
    fog_world(ctx, 1.0, exposure=p.get("exposure", -0.15))
    c0, c1 = p.get("cam0", (-7.0, -56.0, 13.0)), p.get("cam1", (-5.0, -48.0, 10.0))
    t0, t1 = p.get("tgt0", (0.0, 70.0, -9.0)), p.get("tgt1", (0.0, 90.0, -12.0))
    A._cam(ctx, c0, t0, lens=p.get("lens", 30), parent=tr)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "plane", root, (0, 2, 2.5))


# ================================================================ ed_cockpit_fog_v2
def _beam_sheet(name, verts, color, alpha, parent=None):
    mat = A._alpha_emis("mat_" + name, color, 2.4, alpha)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    bm.faces.new(vs)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def ils_beam_objects(y_far=-4200.0, y_near=300.0, lane=6.0, band=5.0, alpha=0.12):
    """Two crossing translucent sheets along the 3-degree approach: teal vertical localizer sheet (x = 0) and amber
    sloped glideslope sheet. The aircraft flies along their intersection line."""
    za, zb = A.glide_alt(y_far) + 3.8, A.glide_alt(y_near) + 3.8
    loc = _beam_sheet("ed_loc_sheet", [(0, y_far, za - band), (0, y_near, max(0.5, zb - band)), (0, y_near, zb + band),
                                       (0, y_far, za + band)], TEAL, alpha)
    gs = _beam_sheet("ed_gs_sheet", [(-lane, y_far, za), (lane, y_far, za), (lane, y_near, zb), (-lane, y_near, zb)],
                     AMBER, alpha)
    # bright core line
    mat = A._alpha_emis("mat_ed_core", hexc("ffffff"), 3.0, 0.55)
    bm = bmesh.new()
    d = Vector((0, y_near - y_far, zb - za))
    S.bm_box(bm, (0, 0, 0), (0.25, d.length, 0.25))
    core = S.obj("ed_core", S.mesh_from_bm("ed_core", bm, [mat]),
                 ((0, (y_far + y_near) / 2, (za + zb) / 2)), (math.atan2(d.z, d.y), 0, 0))
    core.visible_shadow = False
    return [loc, gs, core]


def b_ed_cockpit_fog_v2(ctx, p):
    """scene_lib_v2_air cockpit_workload_v2 (airliner on approach seen from below, flaps / gear / radio rings on four
    cues) in fog. view "approach": + ILS beam sheets from beams_cue. view "close": camera near the cockpit."""
    T = ctx.frames
    view = p.get("view", "approach")
    with Fog(p.get("fog", 0.0035), start=p.get("fog_start", 30.0)):
        A.b_cockpit_workload_v2(ctx, p)
        runway_lights()
    fog_world(ctx, 1.0, exposure=p.get("exposure", -0.15))
    tr = ctx.cam.parent
    if view == "approach" and p.get("beams", True):
        fb = ctx.word_time(p.get("beams_cue", "locks"), 0.3)
        for o in ils_beam_objects():
            _show(o, fb)
    if view == "close":
        ctx.cam.animation_data_clear()
        ctx.cam_target.animation_data_clear()
        c0, t0 = p.get("cam0", (-7.5, 27.0, 1.2)), p.get("tgt0", (0.0, 15.5, 0.9))
        c1, t1 = p.get("cam1", (-9.5, 25.0, 0.4)), p.get("tgt1", (0.0, 13.0, 0.7))
        ctx.cam.location, ctx.cam_target.location = c0, t0
        A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])
        ctx.cam.data.lens = p.get("lens", 30)
        ctx.cam.data.clip_start = 0.3
    del tr


# ================================================================ ils_beams_v2
def _loc_fan(apex_y=1900.0, far_y=-4200.0, half_deg=1.4, alpha=0.12):
    """Localizer fan: a teal translucent surface lying just below the glide path, fanning out from the antenna
    array beyond the far end of the runway, with a brighter centre line."""
    tn = math.tan(math.radians(half_deg))
    n = 24
    bm = bmesh.new()
    rows = []
    for i in range(n + 1):
        y = apex_y + (far_y - apex_y) * i / n
        z = max(0.6, A.glide_alt(y) + 1.0) if y < 600 else 0.6
        w = max(1.0, (apex_y - y) * tn)
        rows.append((bm.verts.new((-w, y, z)), bm.verts.new((w, y, z))))
    for (a0, b0), (a1, b1) in zip(rows[:-1], rows[1:]):
        bm.faces.new((a0, b0, b1, a1))
    mat = A._alpha_emis("mat_ed_fan", TEAL, 2.2, alpha)
    fan = S.obj("ed_loc_fan", S.mesh_from_bm("ed_loc_fan", bm, [mat]))
    fan.visible_shadow = False
    bm = bmesh.new()
    rows = []
    for i in range(n + 1):
        y = apex_y + (far_y - apex_y) * i / n
        z = (max(0.6, A.glide_alt(y) + 1.0) if y < 600 else 0.6) + 0.15
        rows.append((bm.verts.new((-1.6, y, z)), bm.verts.new((1.6, y, z))))
    for (a0, b0), (a1, b1) in zip(rows[:-1], rows[1:]):
        bm.faces.new((a0, b0, b1, a1))
    line = S.obj("ed_loc_line", S.mesh_from_bm("ed_loc_line", bm, [A._alpha_emis("mat_ed_fanline", TEAL, 4.0, 0.75)]))
    line.visible_shadow = False
    bm = bmesh.new()                          # fan edges
    for sx in (-1, 1):
        prev = None
        for i in range(n + 1):
            y = apex_y + (far_y - apex_y) * i / n
            z = (max(0.6, A.glide_alt(y) + 1.0) if y < 600 else 0.6) + 0.1
            w = max(1.0, (apex_y - y) * tn)
            pair = (bm.verts.new((sx * w - 0.8, y, z)), bm.verts.new((sx * w + 0.8, y, z)))
            if prev:
                bm.faces.new((prev[0], prev[1], pair[1], pair[0]))
            prev = pair
    edges = S.obj("ed_loc_edges", S.mesh_from_bm("ed_loc_edges", bm, [A._alpha_emis("mat_ed_fanedge", TEAL, 3.0, 0.45)]))
    edges.visible_shadow = False
    # antenna array (localizer) beyond the far end
    ant = S.pbr("ed_ant", hexc("e4e6e8"), 0.4, 0.4, var=0)
    red = S.emis("ed_ant_r", hexc("ff3b30"), 12.0)

    def arr(bm):
        for k in range(14):
            x = -26 + k * 4.0
            S.bm_box(bm, (x, apex_y, 1.6), (0.25, 0.25, 3.2))
            S.bm_box(bm, (x, apex_y, 3.2), (1.6, 0.4, 0.25))
        S.bm_box(bm, (0, apex_y + 1.0, 0.25), (60, 0.3, 0.5))
    S.obj("ed_loc_ant", _mesh("ed_loc_ant", arr, [ant]))
    return fan, line


def _gs_wedge(apex=(0.0, 300.0), far_y=-4200.0, alpha=0.2, half=0.7):
    """Glideslope wedge: amber translucent slab between (3.2 - half) and (3.2 + half) degrees, apex at the touchdown
    zone, plus a brighter 3.2-degree centre line (the path the aircraft rides)."""
    ax, ay = apex
    c = math.degrees(math.atan(0.056))
    lo, hi = math.tan(math.radians(c - half)), math.tan(math.radians(c + half))
    dy = ay - far_y
    W = 22.0
    bm = bmesh.new()
    v = [bm.verts.new(q) for q in ((ax - W, ay, 0.3), (ax + W, ay, 0.3),
                                   (ax - W, far_y, dy * lo), (ax + W, far_y, dy * lo),
                                   (ax - W, far_y, dy * hi), (ax + W, far_y, dy * hi))]
    bm.faces.new((v[0], v[1], v[3], v[2]))      # lower
    bm.faces.new((v[0], v[4], v[5], v[1]))      # upper
    bm.faces.new((v[0], v[2], v[4]))            # left side
    bm.faces.new((v[1], v[5], v[3]))            # right side
    wedge = S.obj("ed_gs", S.mesh_from_bm("ed_gs", bm, [A._alpha_emis("mat_ed_gs", AMBER, 2.2, alpha)]))
    wedge.visible_shadow = False
    bm = bmesh.new()
    p0, p1 = Vector((ax, ay, 0.3 + 3.8)), Vector((ax, far_y, A.glide_alt(far_y) + 3.8))
    d = p1 - p0
    S.bm_box(bm, (0, 0, 0), (1.2, d.length, 1.2))
    line = S.obj("ed_gs_line", S.mesh_from_bm("ed_gs_line", bm, [A._alpha_emis("mat_ed_gsline", AMBER, 4.0, 0.8)]),
                 tuple((p0 + p1) / 2), (math.atan2(d.z, d.y) - math.pi, 0, 0))
    line.visible_shadow = False
    # "drop curtain": translucent amber wall from the glide path down to the ground (height shrinks to 0 at the TDZ)
    zf = A.glide_alt(far_y) + 3.8
    curtain_ = _beam_sheet("ed_gs_drop", [(ax, ay, 0.3), (ax, far_y, 0.3), (ax, far_y, zf), (ax, ay, 4.1)], AMBER, 0.13)
    # glideslope antenna mast beside the touchdown zone
    S.obj("ed_gs_mast", _mesh("ed_gs_mast", lambda bm: (S.bm_box(bm, (ax + 120, ay, 7), (0.4, 0.4, 14)),
                                                         S.bm_box(bm, (ax + 120, ay, 2), (2.0, 2.0, 0.6))),
                              [S.pbr("ed_ant", hexc("e4e6e8"), 0.4, 0.4, var=0)]))
    return wedge, line


def b_ils_beams_v2(ctx, p):
    """ILS explainer shots in the persistent airport world.
    top: high rear view, translucent teal localizer fan from the antenna beyond the far end of the runway; the airliner
         starts off to the right and slides onto the centre line (anchors beam, plane).
    side: rear-quarter view along the approach, amber ~3 degree glideslope wedge down to the touchdown zone, the
         airliner riding its centre line (anchors slope, plane).
    touchdown: dense fog, the airliner touches down on touch_cue and rolls out on the centre line, runway lights
         glowing (anchors wheels, plane)."""
    view = p.get("view", "top")
    T = ctx.frames
    if view == "touchdown":
        _touchdown(ctx, p)
        return
    with Fog(p.get("fog", 0.0004), start=p.get("fog_start", 400.0), color=S.HAZE):
        A._world(ctx, p)
        runway_lights(0.5)
        if view == "top":
            fan, line = _loc_fan()
            v = 70.0 / ctx.fps
            y1 = p.get("y1", -900.0)
            y0 = y1 - v * T
            off = p.get("offset", 55.0)
            fs = ctx.word_time(p.get("beam_cue", "invisible"), 0.15) / float(T)

            def xk(u):
                g = min(1.0, max(0.0, (u - fs) / max(0.05, 0.75 - fs)))
                return off * (1.0 - g * g * (3 - 2 * g))
            root, parts, tr = _airliner_on_glide(ctx, "al", y0, y1, x_keys=xk)
            # heading + bank from the lateral motion
            for f in range(1, T + 1, 4):
                u0, u1 = (f - 1) / max(1, T - 1), min(1.0, (f + 3) / max(1, T - 1))
                dx = xk(u1) - xk(u0)
                dy = (y1 - y0) * (u1 - u0) or 1e-3
                yaw = math.atan2(-dx, dy)
                kf(root, "rotation_euler", f, Vector((math.radians(2.5), -yaw * 1.6, yaw)))
            _interp(root, "BEZIER")
            tgt = _empty("ed_beam_pt")
            for f in (1, T):
                u = (f - 1) / max(1, T - 1)
                y = y0 + (y1 - y0) * u + 230.0
                kf(tgt, "location", f, Vector((0, y, A.glide_alt(y) + 1.0)))
            _interp(tgt, "LINEAR")
            S.anchor(ctx, "beam", tgt)
            S.anchor(ctx, "plane", root, (0, 0, 2.5))
            c0 = p.get("cam0", (-40.0, -260.0, 230.0))
            t0 = p.get("tgt0", (0.0, 420.0, -120.0))
            c1 = p.get("cam1", (-35.0, -240.0, 215.0))
            A._cam(ctx, c0, t0, lens=p.get("lens", 30), parent=tr)
            A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])
            ctx.cam.data.clip_start = 2.0
        else:
            wedge, line = _gs_wedge()
            v = 70.0 / ctx.fps
            y1 = p.get("y1", -800.0)
            y0 = y1 - v * T
            root, parts, tr = _airliner_on_glide(ctx, "al", y0, y1)
            root.rotation_euler = (math.radians(0.0), 0, 0)
            pt = _empty("ed_slope_pt")
            for f in (1, T):
                u = (f - 1) / max(1, T - 1)
                y = y0 + (y1 - y0) * u + 380.0
                kf(pt, "location", f, Vector((0, y, A.glide_alt(y) + 3.8 + 14.0)))
            _interp(pt, "LINEAR")
            S.anchor(ctx, "slope", pt)
            S.anchor(ctx, "plane", root, (0, 0, 2.5))
            c0 = p.get("cam0", (-38.0, -200.0, 46.0))
            t0 = p.get("tgt0", (0.0, 720.0, -62.0))
            c1 = p.get("cam1", (-34.0, -185.0, 42.0))
            A._cam(ctx, c0, t0, lens=p.get("lens", 28), parent=tr)
            A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])
            ctx.cam.data.clip_start = 2.0


def _touchdown(ctx, p):
    T = ctx.frames
    with Fog(p.get("fog", 0.011), start=p.get("fog_start", 12.0)):
        A._world(ctx, p)
        runway_lights(1.2)
        root, parts = A.make_airliner_v2(ctx, "al", gear_down=True)
        A.flaps_to(parts, 1, 2, 1.0, 1.0)
    fog_world(ctx, 1.0, exposure=p.get("exposure", -0.1))
    ftd = ctx.word_time(p.get("touch_cue", "touch"), 0.35)
    zg = 4.35 + 0.3
    keys, rot = [], []
    y, v = 330.0, 68.0
    for f in range(1, T + 1):
        dt = 1.0 / ctx.fps
        if f > ftd:
            v = max(35.0, v - 2.2 * dt)
        y += v * dt
        h = max(0.0, (ftd - f) / ctx.fps) * 0.9            # ~0.9 m/s sink in the flare
        pitch = 4.5 if f < ftd else max(0.0, 4.5 - (f - ftd) / ctx.fps * 1.6)
        if f % 2 == 1 or f == T:
            keys.append((f, (0.0, y, zg + h + math.sin(math.radians(pitch)) * 1.2)))
            rot.append((f, pitch))
    tr = A._track("al_track", keys)
    _interp(tr, "LINEAR")
    root.parent = tr
    for f, pt in rot:
        kf(root, "rotation_euler", f, Vector((math.radians(pt), 0, 0)))
    _interp(root, "LINEAR")
    c0, t0 = p.get("cam0", (-11.0, -24.0, 1.4)), p.get("tgt0", (0.0, 14.0, -1.2))
    A._cam(ctx, c0, t0, lens=p.get("lens", 26), parent=tr)
    A._cam_keys(ctx, [(1, c0, t0), (T, p.get("cam1", (-9.0, -22.0, 1.0)), t0)])
    ctx.cam.data.clip_start = 0.3
    S.anchor(ctx, "wheels", root, (-2.9, -1.2, -4.2))
    S.anchor(ctx, "centerline", tr, (0, 40.0, -4.3))
    S.anchor(ctx, "plane", root, (0, 0, 2.5))


# ================================================================ bag hall
BAG_COLS = [hexc(c) for c in ("c8302f", "1f3f75", "16a596", "2a2c30", "6b3fa0", "e07a1f", "3d7a3a", "8a8f96", "d9b13b")]


def _hall(ctx, size=(44.0, 32.0), h=7.0, center=(0.0, 0.0), p=None):
    """Bright indoor baggage hall: light concrete floor with yellow lane lines, pale walls with a blue dado, ceiling
    lightbox panels + a few big area lights, columns. Neutral flat world (interior = own lit set, never a void)."""
    p = p or {}
    sc = ctx.scene
    w = bpy.data.worlds.new("hall_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.66, 0.70, 0.76, 1.0)
    bg.inputs["Strength"].default_value = 0.45
    sc.view_settings.exposure = p.get("exposure", -0.2)
    L.fog(p.get("haze", 0.004), hexc("dfe4ea"), start=14.0)
    sx, sy = size
    cx, cy = center
    floor = S.pbr("hall_floor", hexc("b8bcc0"), 0.55, var=0.08, var_scale=0.35, bump=0.02)
    S.plane_obj("hall_floor", sx, sy, (cx, cy, 0.0), floor)
    yel = S.pbr("hall_yellow", hexc("f2c230"), 0.5, var=0.03)
    wall = S.pbr("hall_wall", hexc("e6e9ec"), 0.7, var=0.03)
    dado = S.pbr("hall_dado", hexc("2d5b8c"), 0.5, var=0.03)
    ceil = S.pbr("hall_ceil", hexc("9aa1a8"), 0.8, var=0.02)
    panel = S.emis("hall_panel", hexc("f6f8fb"), p.get("panel", 4.0))

    def walls(bm):
        t = 0.3
        for (x, y, lx, ly) in ((cx, cy - sy / 2, sx, t), (cx, cy + sy / 2, sx, t), (cx - sx / 2, cy, t, sy),
                               (cx + sx / 2, cy, t, sy)):
            S.bm_box(bm, (x, y, h / 2), (lx, ly, h), 0)
            S.bm_box(bm, (x, y, 0.6), (lx + (0.06 if lx < 1 else -0.0), ly + (0.06 if ly < 1 else 0.0), 1.2), 1)
        S.bm_box(bm, (cx, cy, h + 0.1), (sx, sy, 0.2), 2)
    S.obj("hall_walls", _mesh("hall_walls", walls, [wall, dado, ceil]))

    def panels(bm):
        x = cx - sx / 2 + 2.0
        while x < cx + sx / 2 - 1.0:
            y = cy - sy / 2 + 2.0
            while y < cy + sy / 2 - 1.0:
                S.bm_box(bm, (x, y, h - 0.03), (2.4, 0.45, 0.06))
                y += 3.0
            x += 4.0
    S.obj("hall_panels", _mesh("hall_panels", panels, [panel]))

    def lanes(bm):
        for yy in (cy - sy / 2 + 1.0, cy + sy / 2 - 1.0):
            S.bm_box(bm, (cx, yy, 0.006), (sx - 2, 0.12, 0.012))
        for xx in (cx - sx / 2 + 1.0, cx + sx / 2 - 1.0):
            S.bm_box(bm, (xx, cy, 0.006), (0.12, sy - 2, 0.012))
    S.obj("hall_lanes", _mesh("hall_lanes", lanes, [yel]))
    col = S.pbr("hall_col", hexc("cfd3d8"), 0.6, var=0.03)

    def cols(bm):
        for x in (cx - sx / 2 + 10.0, cx + sx / 2 - 10.0):
            for y in (cy - sy / 2 + 8.0, cy + sy / 2 - 8.0):
                S.bm_box(bm, (x, y, h / 2), (0.6, 0.6, h), 0)
                S.bm_box(bm, (x, y, 0.5), (0.64, 0.64, 1.0), 1)
    S.obj("hall_cols", _mesh("hall_cols", cols, [col, yel]))
    for k, (ax, ay) in enumerate(((-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25))):
        A._area("hall_a%d" % k, (cx + ax * sx, cy + ay * sy, h - 0.3), 7.0, p.get("area", 2600.0),
                (1.0, 0.98, 0.95), size_y=5.0)


def _belt_mat(ctx, speed):
    """Dark rubber belt with seams every 1.2 m, scrolling along the object's local X at `speed` m/s."""
    name = "ed_belt_%.2f" % speed
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, pr = S._new_mat(name)
    pr.inputs["Roughness"].default_value = 0.75
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    wv = N.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 1.0 / 1.2 / 1.0
    wv.inputs["Distortion"].default_value = 0.0
    Lk.new(mp.outputs["Vector"], wv.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.035, 0.037, 0.04, 1)
    ramp.color_ramp.elements[1].position = 0.08
    ramp.color_ramp.elements[1].color = (0.075, 0.078, 0.085, 1)
    Lk.new(wv.outputs["Fac"], ramp.inputs[0])
    Lk.new(ramp.outputs["Color"], pr.inputs["Base Color"])
    T = ctx.frames
    L.kf_socket(mp.inputs["Location"], 1, (0.0, 0.0, 0.0))
    L.kf_socket(mp.inputs["Location"], T + 1, (-speed * T / ctx.fps, 0.0, 0.0))
    _interp(nt, "LINEAR")
    S._MV2[name] = S._finish(m, pr.outputs[0])
    return S._MV2[name]


def belt(ctx, name, p0, p1, z=0.75, w=1.0, speed=0.6, legs=True, guards=True):
    """Straight conveyor from p0 to p1 (x, y): rubber top (scrolling), side guards, side rails, return rollers,
    end drums and legs. Local X runs along the belt. Returns the object."""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = p1 - p0
    ln = d.length
    ang = math.atan2(d.y, d.x)
    metal = S.pbr("ed_belt_metal", hexc("aab2ba"), 0.35, 0.7, var=0.02)
    guard = S.pbr("ed_belt_guard", hexc("d5dade"), 0.4, 0.6, var=0.02)
    dark = S.pbr("ed_roller", hexc("5d646b"), 0.3, 0.8, var=0)
    bm = bmesh.new()
    S.bm_box(bm, (ln / 2, 0, z - 0.03), (ln, w, 0.06), 0)
    for s in (-1, 1):
        S.bm_box(bm, (ln / 2, s * (w / 2 + 0.04), z - 0.12), (ln, 0.08, 0.26), 1)       # side frame
        if guards:
            S.bm_box(bm, (ln / 2, s * (w / 2 + 0.06), z + 0.09), (ln, 0.03, 0.2), 2)     # side guard
    k = 0.35
    while k < ln - 0.2:
        _cyl(bm, (k, 0, z - 0.2), 0.045, w, "Y", 10, 3)
        k += 0.5
    for xx in (0.0, ln):
        _cyl(bm, (xx, 0, z - 0.09), 0.09, w + 0.02, "Y", 14, 3)
    if legs:
        k = 0.4
        while k < ln:
            for s in (-1, 1):
                S.bm_box(bm, (k, s * (w / 2 + 0.02), (z - 0.25) / 2), (0.07, 0.07, z - 0.25), 1)
            k += 2.2
    me = S.mesh_from_bm(name, bm, [_belt_mat(ctx, speed), metal, guard, dark])
    o = S.obj(name, me, (p0.x, p0.y, 0), (0, 0, ang))
    return o


def _barcode_image(seed=3):
    """Bag-tag artwork made in memory (no text): white paper, teal airline band, two barcodes."""
    import numpy as np
    name = "ed_tag_img_%d" % seed
    if name in bpy.data.images:
        return bpy.data.images[name]
    W, H = 256, 512
    a = np.ones((H, W, 4), dtype=np.float32)
    a[..., :3] = 0.96
    rng = random.Random(seed)
    # teal band at the top + thin amber stripe
    a[H - 70:H, :, :3] = (0.05, 0.55, 0.52)
    a[H - 82:H - 74, :, :3] = (0.95, 0.65, 0.05)

    def bars(x0, x1, y0, y1):
        x = x0
        while x < x1:
            bw = rng.choice((2, 2, 3, 4, 6))
            if rng.random() < 0.55:
                a[y0:y1, x:min(x1, x + bw), :3] = 0.05
            x += bw
    bars(24, W - 24, 170, 330)          # main barcode (bars vertical, image Y = tag height)
    bars(60, W - 60, 60, 120)           # small second barcode
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.pixels.foreach_set(a.ravel())
    img.pack()
    return img


def _tag_mat():
    if "ed_tag" in S._MV2:
        return S._MV2["ed_tag"]
    m, nt, N, Lk, pr = S._new_mat("ed_tag")
    tex = N.new("ShaderNodeTexImage")
    tex.image = _barcode_image()
    tex.interpolation = "Cubic"
    Lk.new(N.new("ShaderNodeTexCoord").outputs["UV"], tex.inputs["Vector"])
    Lk.new(tex.outputs["Color"], pr.inputs["Base Color"])
    pr.inputs["Roughness"].default_value = 0.6
    S._MV2["ed_tag"] = S._finish(m, pr.outputs[0])
    return S._MV2["ed_tag"]


_BAG_MESH = {}


def make_bag(name, size=(0.7, 0.45, 0.28), color=None, tag=True, upright=False, rng=None):
    """Suitcase: rounded shell, zip seam, handle, two wheels, and (optionally) a barcode tag hanging on the -Y face.
    Returns the root empty; root origin = bottom centre. Local X = length, Y = depth, Z = height (lying flat);
    upright=True stands it on its end."""
    rng = rng or random.Random(1)
    color = color or rng.choice(BAG_COLS)
    lx, ly, lz = size
    key = (round(lx, 3), round(ly, 3), round(lz, 3), tuple(round(c, 3) for c in color[:3]))
    root = L.link(bpy.data.objects.new(name, None))
    shell = S.pbr("ed_bag_%02x%02x%02x" % tuple(int(c * 255) for c in color[:3]), color, 0.42, 0.0, coat=0.25,
                  var=0.04, var_scale=3.0)
    trim = S.pbr("ed_bag_trim", hexc("1b1d21"), 0.6, var=0)
    if key not in _BAG_MESH:
        def build(bm):
            _rbox(bm, (0, 0, lz / 2), (lx, ly, lz), r=min(0.06, lz * 0.25), seg=3)
            S.bm_box(bm, (0, 0, lz * 0.5), (lx + 0.012, ly + 0.012, 0.018), 1)       # zip seam
            S.bm_box(bm, (0, 0, lz + 0.03), (lx * 0.32, 0.035, 0.03), 1)             # handle grip
            for sx in (-1, 1):
                S.bm_box(bm, (sx * lx * 0.16, 0, lz + 0.015), (0.03, 0.035, 0.04), 1)
                _cyl(bm, (lx / 2 + 0.02, sx * ly * 0.32, 0.05), 0.04, 0.03, "Y", 10)
        _BAG_MESH[key] = _mesh("bag_" + name, build, [shell, trim], smooth=False)
    body = S.obj(name + "_body", _BAG_MESH[key], parent=root)
    if tag:
        tg = _tag_mat()
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new()
        tw, th = 0.10, 0.20
        ox = -lx * 0.12
        y = -ly / 2 - 0.006
        z1 = lz + 0.02
        vs = [bm.verts.new(v) for v in ((ox - tw / 2, y, z1 - th), (ox + tw / 2, y, z1 - th), (ox + tw / 2, y, z1),
                                          (ox - tw / 2, y, z1))]
        f = bm.faces.new(vs)
        for lp, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uv].uv = (u, v)
        f2 = bm.faces.new(list(reversed([bm.verts.new(v.co + Vector((0, 0.002, 0))) for v in vs])))
        for lp, (u, v) in zip(f2.loops, ((0, 1), (1, 1), (1, 0), (0, 0))):
            lp[uv].uv = (u, v)
        S.bm_box(bm, (ox, -ly / 2 + 0.01, lz + 0.03), (0.02, 0.03, 0.03), 1)   # strap loop
        tagobj = S.obj(name + "_tag", S.mesh_from_bm(name + "_tag", bm, [tg, trim]), parent=root)
        root["tag"] = tagobj.name
    if upright:
        body.rotation_euler = (0, math.radians(90), 0)
        body.location = (-lz / 2, 0, lx / 2)
        for c in root.children:
            if c is not body:
                c.rotation_euler = body.rotation_euler
                c.location = body.location
    return root


def path_move(ctx, o, pts, f0, speed, z=0.0, every=2, yaw_off=0.0, f_end=None):
    """Move `o` along the polyline pts [(x, y[, z])] at `speed` m/s from frame f0 (keys every `every` frames,
    LINEAR); yaw follows the segment direction. Returns the frame at which each vertex is reached."""
    P = [Vector((q[0], q[1], q[2] if len(q) > 2 else z)) for q in pts]
    seg = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    cum = [0.0]
    for s in seg:
        cum.append(cum[-1] + s)

    def at(s):
        s = max(0.0, min(cum[-1], s))
        for i in range(len(seg)):
            if s <= cum[i + 1] or i == len(seg) - 1:
                u = (s - cum[i]) / max(1e-6, seg[i])
                d = P[i + 1] - P[i]
                return P[i].lerp(P[i + 1], u), math.atan2(d.y, d.x)
    T = f_end or ctx.frames
    prev = None
    for f in list(range(1, T + 1, every)) + [T]:
        s = max(0.0, (f - f0) / ctx.fps) * speed
        pos, yaw = at(s)
        if prev is not None:
            while yaw - prev > math.pi:
                yaw -= 2 * math.pi
            while yaw - prev < -math.pi:
                yaw += 2 * math.pi
        prev = yaw
        kf(o, "location", f, pos)
        kf(o, "rotation_euler", f, Vector((0, 0, yaw + yaw_off)))
    _interp(o, "LINEAR")
    return [f0 + c / speed * ctx.fps for c in cum]


def curtain(ctx, name, center, width, height, axis_yaw, passes, sign=1.0):
    """Rubber strip curtain (hinged at the top). `passes` = [(frame_in, frame_out)] when a bag pushes through:
    the strips swing back and fall again."""
    mat = S.pbr("ed_curtain", hexc("2b2f35"), 0.5, var=0.02)
    n = max(4, int(width / 0.12))
    sw = width / n
    objs = []
    me = _mesh(name + "_strip", lambda bm: S.bm_box(bm, (0, 0, -height / 2), (sw * 0.92, 0.012, height)), [mat])
    for k in range(n):
        lx = -width / 2 + sw * (k + 0.5)
        hinge = Vector(center) + Matrix.Rotation(axis_yaw, 3, "Z") @ Vector((lx, 0, height))
        o = S.obj("%s%d" % (name, k), me, tuple(hinge), (0, 0, axis_yaw))
        if passes:
            for (fi, fo) in passes:
                kf(o, "rotation_euler", max(1, fi - 4), Vector((0, 0, axis_yaw)))
                kf(o, "rotation_euler", fi + 3, Vector((sign * math.radians(55 + 6 * math.sin(k)), 0, axis_yaw)))
                kf(o, "rotation_euler", fo, Vector((sign * math.radians(50), 0, axis_yaw)))
                kf(o, "rotation_euler", fo + 10, Vector((sign * math.radians(-8), 0, axis_yaw)))
                kf(o, "rotation_euler", fo + 22, Vector((0, 0, axis_yaw)))
            _interp(o, "BEZIER")
        objs.append(o)
    return objs


def _wall_opening(name, center, w, h, yaw=0.0, depth=0.5):
    """Dark tunnel opening (inside of a wall portal) + metal frame."""
    dark = S.pbr("ed_dark", hexc("15171a"), 0.9, var=0)
    frame = S.pbr("ed_frame", hexc("c3c9cf"), 0.35, 0.6, var=0)

    def build(bm):
        S.bm_box(bm, (0, depth / 2 + 0.02, h / 2), (w, depth, h), 0)
        S.bm_box(bm, (0, 0, h + 0.06), (w + 0.24, 0.1, 0.12), 1)
        for s in (-1, 1):
            S.bm_box(bm, (s * (w / 2 + 0.06), 0, h / 2), (0.12, 0.1, h + 0.12), 1)
    return S.obj(name, _mesh(name, build, [dark, frame]), center, (0, 0, yaw))


# ---------------------------------------------------------------- views
def _cam_static(ctx, c0, t0, c1=None, t1=None, lens=30, clip=0.05, dof=None):
    T = ctx.frames
    A._cam(ctx, c0, t0, lens=lens)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1 or c0, t1 or t0)])
    ctx.cam.data.clip_start = clip
    ctx.cam.data.clip_end = 400.0
    if dof:
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_object = dof[0]
        ctx.cam.data.dof.aperture_fstop = dof[1]


def _v_counter(ctx, p):
    """Check-in counter: the bag rides the scale belt into the wall and pushes through the rubber curtain."""
    T = ctx.frames
    _hall(ctx, (24.0, 18.0), 5.5, (0.0, 2.0), p)
    z = 0.38
    belt(ctx, "scale_belt", (0, -1.6), (0, 2.6), z=z, w=1.0, speed=0.0, legs=False, guards=False)
    # counters either side
    front = S.pbr("ed_counter_front", hexc("f1f2f3"), 0.35, coat=0.3, var=0.02)
    top = S.pbr("ed_counter_top", hexc("2e3a46"), 0.3, var=0.02)
    acc = S.emis("ed_counter_acc", hexc("19d3c0"), 2.0)
    scr = S.emis("ed_screen", hexc("9ec9e8"), 1.2)

    def counters(bm):
        for sx in (-1, 1):
            cx = sx * 1.55
            S.bm_box(bm, (cx, 0.2, 0.52), (2.0, 1.0, 1.04), 0)
            S.bm_box(bm, (cx, 0.15, 1.07), (2.1, 1.15, 0.06), 1)
            S.bm_box(bm, (cx, -0.31, 0.95), (2.0, 0.02, 0.05), 2)
            S.bm_box(bm, (cx + sx * 0.3, 0.45, 1.33), (0.55, 0.04, 0.36), 1)    # monitor (back)
            S.bm_box(bm, (cx - sx * 0.55, -0.1, 1.11), (0.4, 0.3, 0.03), 1)     # printer
        for k in range(4):
            cx = 4.6 + k * 3.1
            S.bm_box(bm, (cx, 0.2, 0.52), (2.6, 1.0, 1.04), 0)
            S.bm_box(bm, (cx, 0.15, 1.07), (2.7, 1.15, 0.06), 1)
            S.bm_box(bm, (cx, -0.31, 0.95), (2.6, 0.02, 0.05), 2)
            S.bm_box(bm, (-cx, 0.2, 0.52), (2.6, 1.0, 1.04), 0)
            S.bm_box(bm, (-cx, 0.15, 1.07), (2.7, 1.15, 0.06), 1)
            S.bm_box(bm, (-cx, -0.31, 0.95), (2.6, 0.02, 0.05), 2)
    S.obj("counters", _mesh("counters", counters, [front, top, acc]))
    S.obj("screens", _mesh("screens", lambda bm: [S.bm_box(bm, (sx * 1.55 + sx * 0.3, 0.42, 1.33), (0.5, 0.01, 0.3))
                                                    for sx in (-1, 1)], [scr]))
    # back wall with the belt portal + backlit panels above
    wall = S.pbr("hall_wall", hexc("e6e9ec"), 0.7, var=0.03)
    lit = S.emis("ed_backlit", hexc("e4eef7"), 1.6)

    def back(bm):
        S.bm_box(bm, (-6.6, 2.75, 2.75), (12.2, 0.3, 5.5), 0)
        S.bm_box(bm, (6.6, 2.75, 2.75), (12.2, 0.3, 5.5), 0)
        S.bm_box(bm, (0, 2.75, (1.33 + 5.5) / 2), (1.0, 0.3, 5.5 - 1.33), 0)
        S.bm_box(bm, (0, 2.75, 0.07), (1.0, 0.3, 0.14), 0)
    S.obj("back_wall", _mesh("back_wall", back, [wall]))
    S.obj("back_lit", _mesh("back_lit", lambda bm: [S.bm_box(bm, (x, 2.58, 3.3), (2.6, 0.04, 1.6))
                                                     for x in (-4.65, -1.55, 1.55, 4.65)], [lit]))
    _wall_opening("portal", (0, 2.62, z), 1.0, 0.95, 0.0, depth=1.2)
    # bag
    rng = random.Random(4)
    bag = make_bag("hero", (0.72, 0.46, 0.3), hexc("c8302f"), tag=True, upright=True, rng=rng)
    f0 = ctx.word_time(p.get("drop_cue", "drop"), 0.1) + 8
    fg = ctx.word_time(p.get("gone_cue", "disappears"), 0.45)
    y_start, y_curt = -0.55, 2.55
    dist = (y_curt + 0.25) - y_start
    speed = dist / max(0.5, (fg - f0) / ctx.fps)
    fr = path_move(ctx, bag, [(0, y_start, z), (0, 6.0, z)], f0, speed, yaw_off=-math.pi / 2)
    f_in = int(f0 + ((y_curt - 0.25) - y_start) / speed * ctx.fps)
    f_out = int(f0 + ((y_curt + 0.55) - y_start) / speed * ctx.fps)
    curtain(ctx, "curt", (0, 2.6, z), 0.96, 0.92, 0.0, [(f_in, f_out)])
    # a second, waiting bag on the next counter's belt
    b2 = make_bag("b2", (0.6, 0.4, 0.25), hexc("1f3f75"), tag=True, rng=rng)
    b2.location, b2.rotation_euler = (-3.2, -1.2, 0.0), (0, 0, 0.4)
    _cam_static(ctx, p.get("cam0", (-2.4, -4.6, 1.7)), p.get("tgt0", (0.1, 1.2, 0.7)),
                p.get("cam1", (-2.1, -4.2, 1.6)), p.get("tgt1", (0.1, 1.6, 0.65)), lens=p.get("lens", 26))
    S.anchor(ctx, "bag", bag, (0, 0, 0.8))


def _v_tag(ctx, p):
    """Macro on the bag tag riding the belt (camera travels with the bag, shallow focus)."""
    T = ctx.frames
    _hall(ctx, (30.0, 20.0), 6.0, (0.0, 0.0), p)
    z = 0.75
    belt(ctx, "main", (-15, 0), (15, 0), z=z, speed=0.5)
    belt(ctx, "far", (-15, 3.2), (15, 3.2), z=1.6, speed=0.5)
    rng = random.Random(9)
    bag = make_bag("hero", (0.72, 0.46, 0.3), hexc("1f3f75"), tag=True, rng=rng)
    path_move(ctx, bag, [(-4, 0, z), (15, 0, z)], 1, 0.5)
    for k in range(5):
        b = make_bag("bb%d" % k, (rng.uniform(0.5, 0.8), rng.uniform(0.35, 0.5), rng.uniform(0.22, 0.32)), rng=rng)
        path_move(ctx, b, [(-6.5 - 2.3 * k, 0, z), (15, 0, z)], 1, 0.5)
        b2 = make_bag("bf%d" % k, (rng.uniform(0.5, 0.8), rng.uniform(0.35, 0.5), rng.uniform(0.22, 0.32)), rng=rng)
        path_move(ctx, b2, [(-9 + 2.6 * k, 3.2, 1.6), (15, 3.2, 1.6)], 1, 0.5)
    tag = bpy.data.objects[bag["tag"]]
    focus = _empty("tag_focus", (-0.72 * 0.12, -0.24, 0.24), parent=bag)
    c0 = p.get("cam0", (-0.36, -0.72, 0.36))
    t0 = p.get("tgt0", (-0.08, -0.2, 0.22))
    c1 = p.get("cam1", (-0.28, -0.55, 0.3))
    A._cam(ctx, c0, t0, lens=p.get("lens", 45), parent=bag)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])
    ctx.cam.data.clip_start = 0.02
    ctx.cam.data.dof.use_dof = True
    ctx.cam.data.dof.focus_object = focus
    ctx.cam.data.dof.aperture_fstop = p.get("fstop", 2.2)
    S.anchor(ctx, "tag", focus)


def _scan_arch(ctx, x, z, w=1.0, rfid_frame=None):
    housing = S.pbr("ed_arch", hexc("d9dde1"), 0.35, 0.2, coat=0.3, var=0.02)
    inner = S.pbr("ed_arch_in", hexc("2a2e34"), 0.25, 0.2, coat=0.5, var=0)
    win = S.emis("ed_arch_win", hexc("ff4a3a"), 6.0)
    H = 1.25

    def build(bm):
        for s in (-1, 1):
            _rbox(bm, (x, s * (w / 2 + 0.28), z + H / 2 - 0.3), (0.7, 0.45, H + 0.6), 0.05, 2)
        _rbox(bm, (x, 0, z + H + 0.12), (0.7, w + 1.0, 0.36), 0.05, 2)
        for s in (-1, 1):
            S.bm_box(bm, (x, s * (w / 2 + 0.06), z + H / 2), (0.62, 0.02, H - 0.1), 1)
        S.bm_box(bm, (x, 0, z + H - 0.07), (0.62, w + 0.1, 0.02), 1)
    arch = S.obj("arch", _mesh("arch", build, [housing, inner]))

    def wins(bm):
        for s in (-1, 1):
            for k in range(3):
                S.bm_box(bm, (x - 0.2 + 0.2 * k, s * (w / 2 + 0.045), z + 0.3 + 0.35 * k), (0.06, 0.01, 0.06))
        for k in range(3):
            S.bm_box(bm, (x - 0.2 + 0.2 * k, 0, z + H - 0.085), (0.06, 0.06, 0.01))
    S.obj("arch_wins", _mesh("arch_wins", wins, [win]))
    # sweeping red laser lines (thin unlit boxes, pivot at the emitter)
    las = S.emis("ed_laser", hexc("ff2020"), 14.0)
    rng = random.Random(5)
    em = []
    for s in (-1, 1):
        for k in range(3):
            em.append(((x - 0.2 + 0.2 * k, s * (w / 2 + 0.04), z + 0.3 + 0.35 * k), Vector((0, -s, -0.35 * k + 0.2))))
    for k in range(3):
        em.append(((x - 0.2 + 0.2 * k, 0, z + H - 0.09), Vector((0, 0, -1))))
    for i, (loc, d) in enumerate(em):
        ln = 1.25
        me = _mesh("laser%d" % i, lambda bm: S.bm_box(bm, (0, ln / 2, 0), (0.006, ln, 0.006)), [las])
        o = S.obj("laser%d" % i, me, loc)
        o.visible_shadow = False
        base = Vector((0, 1, 0)).rotation_difference(d.normalized()).to_euler()
        ph = rng.uniform(0, 6.28)
        per = rng.randint(18, 30)
        for j in range(0, per + 1, 3):
            a = math.radians(28) * math.sin(ph + 2 * math.pi * j / per)
            e = base.copy()
            e.x += a * (0.4 if i >= 6 else 0.0)
            e.z += a
            kf(o, "rotation_euler", 1 + j, Vector((e.x, e.y, e.z)))
        _interp(o, "LINEAR")
        _cyclic(o)
    if rfid_frame:
        A.ring_pulses(ctx, (x, 0, z + H + 0.35), rfid_frame, color=TEAL, count=4, gap=7, r1=2.2, life=26,
                      rot=(0, math.radians(90), 0), name="rfid")
    return arch


def _v_scan_arch(ctx, p):
    T = ctx.frames
    _hall(ctx, (30.0, 22.0), 6.0, (0.0, 2.0), p)
    z = 0.75
    belt(ctx, "main", (-15, 0), (15, 0), z=z, speed=0.5)
    belt(ctx, "far", (-15, 4.0), (15, 4.0), z=0.75, speed=0.5)
    fr = ctx.word_time(p.get("rfid_cue", "radio"), 0.75)
    arch = _scan_arch(ctx, 0.0, z, 1.0, fr)
    rng = random.Random(12)
    # bags "any way up": flat, upright, on the side; one passes the arch mid-beat
    specs = [((0.72, 0.46, 0.3), hexc("c8302f"), False), ((0.6, 0.4, 0.26), hexc("16a596"), True),
             ((0.8, 0.5, 0.32), hexc("2a2c30"), False), ((0.55, 0.38, 0.24), hexc("e07a1f"), True),
             ((0.7, 0.44, 0.3), hexc("6b3fa0"), False)]
    v = 0.5
    x_mid = -v * (T * 0.55 / ctx.fps)
    for k, (sz, col, up) in enumerate(specs):
        b = make_bag("bag%d" % k, sz, col, tag=True, upright=up, rng=rng)
        path_move(ctx, b, [(x_mid - 1.9 * k + 1.9, rng.uniform(-0.12, 0.12), z), (30, 0, z)], 1, v,
                  yaw_off=rng.uniform(-0.25, 0.25))
    for k in range(6):
        b = make_bag("far%d" % k, (rng.uniform(0.5, 0.8), 0.42, 0.28), rng=rng)
        path_move(ctx, b, [(-12 + 3.2 * k, 4.0, z), (30, 4.0, z)], 1, v)
    _cam_static(ctx, p.get("cam0", (-3.3, -3.0, 1.75)), p.get("tgt0", (0.3, 0.2, 0.95)),
                p.get("cam1", (-3.0, -2.7, 1.7)), p.get("tgt1", (0.3, 0.2, 0.95)), lens=p.get("lens", 26))
    S.anchor(ctx, "arch", arch, (0.0, 0.0, z + 1.55))


def _eds(ctx, x0, z, ln=4.2):
    """CT / EDS screening machine around the belt: rounded housing, tunnel with curtains, cyan status band and a
    glowing gantry ring on the side."""
    housing = S.pbr("ed_eds", hexc("eef0f2"), 0.3, 0.1, coat=0.4, var=0.02)
    trim = S.pbr("ed_eds_trim", hexc("4b5560"), 0.4, 0.3, var=0)
    dark = S.emis("ed_eds_inside", hexc("1d4d66"), 0.9)       # dim blue glow inside the tunnel
    cyan = S.emis("ed_eds_cyan", hexc("3fe0ff"), 4.0)
    cx = x0 + ln / 2
    tw, th = 1.15, 0.9

    def build(bm):
        # housing = 4 slabs around the tunnel
        _rbox(bm, (cx, 0, z + th + 0.5), (ln, 2.3, 1.0), 0.12, 3)
        for s in (-1, 1):
            _rbox(bm, (cx, s * (tw / 2 + 0.29), z + th / 2 - 0.25), (ln, 0.58, th + 0.5 + 0.1), 0.08, 2)
        S.bm_box(bm, (cx, 0, z - 0.32), (ln, 2.3, 0.4), 1)
        S.bm_box(bm, (cx, 0, z + th / 2), (ln - 0.1, tw + 0.02, th + 0.02), 2)    # tunnel inside (dark)
    S.obj("eds", _mesh("eds", build, [housing, trim, dark]))

    S.obj("eds_band", _mesh("eds_band", lambda bm: S.bm_box(bm, (cx, -1.175, z + th + 0.55), (ln - 0.6, 0.02, 0.06)),
                            [cyan]))

    def ring(bm):
        r = bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=0.55)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, vec=(cx, -1.19, z + 0.65), verts=r["verts"])
    rings = S.obj("eds_ring", _mesh("eds_ring", ring, [cyan]))
    rings.modifiers.new("w", "WIREFRAME").thickness = 0.05
    return cx, tw, th


def _v_screen(ctx, p):
    T = ctx.frames
    _hall(ctx, (30.0, 22.0), 6.0, (0.0, 2.0), p)
    z = 0.75
    belt(ctx, "in", (-15, 0), (0, 0), z=z, speed=0.5)
    belt(ctx, "out", (4.2, 0), (15, 0), z=z, speed=0.5)
    belt(ctx, "far", (-15, 4.5), (15, 4.5), z=z, speed=0.5)
    cx, tw, th = _eds(ctx, 0.0, z)
    S.plane_obj("eds_belt", 4.2, 1.0, (cx, 0, z + 0.003), _belt_mat(ctx, 0.5))
    fe = ctx.word_time(p.get("enter_cue", "explosives"), 0.4)
    v = 0.45
    f_in, f_out = fe, fe + int(4.6 / v * ctx.fps)
    curtain(ctx, "curt_in", (-0.02, 0, z), tw, th - 0.02, math.pi / 2, [(fe - 2, fe + int(0.8 / v * ctx.fps))], -1.0)
    curtain(ctx, "curt_out", (4.22, 0, z), tw, th - 0.02, math.pi / 2, [])
    rng = random.Random(21)
    hero = make_bag("hero", (0.72, 0.46, 0.3), hexc("c8302f"), rng=rng)
    path_move(ctx, hero, [(-0.45 - v * (fe - 1) / ctx.fps, 0, z), (20, 0, z)], 1, v)
    for k in range(3):
        b = make_bag("b%d" % k, (rng.uniform(0.5, 0.8), 0.42, 0.28), rng=rng)
        path_move(ctx, b, [(-0.45 - v * (fe - 1) / ctx.fps - 1.7 * (k + 1), 0, z), (20, 0, z)], 1, v)
    for k in range(6):
        b = make_bag("far%d" % k, (rng.uniform(0.5, 0.8), 0.42, 0.28), rng=rng)
        path_move(ctx, b, [(-12 + 3.4 * k, 4.5, z), (30, 4.5, z)], 1, v)
    _cam_static(ctx, p.get("cam0", (-3.8, -3.6, 1.9)), p.get("tgt0", (0.9, 0.0, 1.05)),
                p.get("cam1", (-3.4, -3.2, 1.8)), p.get("tgt1", (1.0, 0.0, 1.0)), lens=p.get("lens", 26))
    tun = _empty("tunnel_pt", (cx - 1.0, 0, z + th + 1.05))
    S.anchor(ctx, "tunnel", tun)


def _diverter(name, hinge, yaw0, yaw1, f_swing, f_back, ln=1.6):
    yel = S.pbr("ed_paddle", hexc("f2c230"), 0.4, 0.2, coat=0.3, var=0.02)
    post = S.pbr("ed_belt_metal", hexc("aab2ba"), 0.35, 0.7, var=0.02)

    def build(bm):
        _rbox(bm, (ln / 2, 0, 0.12), (ln, 0.06, 0.24), 0.02, 2)
        _cyl(bm, (0, 0, 0.0), 0.09, 0.6, "Z", 14)
    o = S.obj(name, _mesh(name, build, [yel, post]), hinge, (0, 0, yaw0))
    kf(o, "rotation_euler", 1, Vector((0, 0, yaw0)))
    kf(o, "rotation_euler", max(2, f_swing - 6), Vector((0, 0, yaw0)))
    kf(o, "rotation_euler", f_swing, Vector((0, 0, yaw1)))
    kf(o, "rotation_euler", f_back, Vector((0, 0, yaw1)))
    kf(o, "rotation_euler", f_back + 8, Vector((0, 0, yaw0)))
    _interp(o, "BEZIER")
    tip = _empty(name + "_tip", (ln * 0.7, 0, 0.3), parent=o)
    return o, tip


def _v_sort(ctx, p):
    """Wide view over the sorting maze: a stream of bags on the main line; the diverter paddle swings across on
    push_cue and the hero bag takes the branch belt."""
    T = ctx.frames
    _hall(ctx, (44.0, 34.0), 7.5, (2.0, 4.0), p)
    z = 0.75
    v = 1.1
    belt(ctx, "main", (-18, 0), (22, 0), z=z, speed=v)
    jx = 0.0
    br_a = math.radians(32)
    b_end = (jx + 14 * math.cos(br_a), 0.55 + 14 * math.sin(br_a))
    belt(ctx, "branch", (jx + 0.2, 0.55), b_end, z=z, speed=v)
    belt(ctx, "branch2", (8.0, -0.55), (8.0 + 12 * math.cos(br_a), -0.55 - 12 * math.sin(br_a)), z=z, speed=v)
    belt(ctx, "line2", (-18, -5.0), (22, -5.0), z=z, speed=v)
    fp = ctx.word_time(p.get("push_cue", "push"), 0.6)
    f_sw = fp - 6
    pad, tip = _diverter("diverter", (jx - 0.9, -0.55, z + 0.02), 0.0, math.radians(45), f_sw, f_sw + int(1.3 * ctx.fps))
    _diverter("diverter2", (8.0 - 0.9, 0.55, z + 0.02), 0.0, 0.0, 2, 3)
    rng = random.Random(33)
    hero = make_bag("hero", (0.72, 0.46, 0.3), hexc("c8302f"), rng=rng)
    x_start = jx - 0.3 - v * (fp - 1) / ctx.fps
    path_move(ctx, hero, [(x_start, 0, z), (jx - 0.3, 0, z), (jx + 0.6, 0.7, z), b_end + (z,)], 1, v)
    # other bags on the main line, keeping clear of the paddle swing
    for k in range(-6, 10):
        if k == 0:
            continue
        x0 = x_start + 2.6 * k
        f_j = 1 + (jx - 0.3 - x0) / v * ctx.fps
        if f_sw - 22 < f_j < f_sw + 1.6 * ctx.fps:
            continue
        b = make_bag("m%d" % (k + 6), (rng.uniform(0.5, 0.8), rng.uniform(0.38, 0.5), 0.28), rng=rng)
        path_move(ctx, b, [(x0, rng.uniform(-0.1, 0.1), z), (40, 0, z)], 1, v)
    for k in range(9):
        b = make_bag("l2_%d" % k, (rng.uniform(0.5, 0.8), 0.42, 0.28), rng=rng)
        path_move(ctx, b, [(-18 + 3.0 * k, -5.0, z), (40, -5.0, z)], 1, v)
    for k in range(3):
        b = make_bag("br%d" % k, (0.6, 0.42, 0.28), rng=rng)
        path_move(ctx, b, [(jx + 0.6 + 3.0 * (k + 1) * math.cos(br_a), 0.7 + 3.0 * (k + 1) * math.sin(br_a), z),
                           b_end + (z,)], 1, v)
    _cam_static(ctx, p.get("cam0", (-7.0, -10.5, 7.2)), p.get("tgt0", (1.6, 1.6, 0.4)),
                p.get("cam1", (-6.2, -9.8, 6.8)), p.get("tgt1", (1.8, 1.8, 0.4)), lens=p.get("lens", 30))
    S.anchor(ctx, "diverter", tip)
    S.anchor(ctx, "bag", hero, (0, 0, 0.5))


def make_cart(name, loc, yaw=0.0, bags=6, rng=None):
    """Baggage dolly: flatbed, low side rails, corner posts, canopy roof, four wheels, tow bar; bags stacked on it."""
    rng = rng or random.Random(3)
    root = _empty(name, loc)
    root.rotation_euler = (0, 0, yaw)
    blue = S.pbr("ed_cart", hexc("2d5b8c"), 0.5, 0.3, var=0.04)
    grey = S.pbr("ed_cart_g", hexc("b5bcc3"), 0.4, 0.6, var=0.02)
    tyre = S.pbr("al_dark_v2", hexc("17191d"), 0.5, var=0)

    def build(bm):
        S.bm_box(bm, (0, 0, 0.5), (3.0, 1.5, 0.08), 0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                S.bm_box(bm, (sx * 1.45, sy * 0.72, 1.25), (0.06, 0.06, 1.5), 1)
            S.bm_box(bm, (sx * 1.48, 0, 0.75), (0.04, 1.5, 0.45), 1)
        S.bm_box(bm, (0, 0, 2.02), (3.1, 1.6, 0.06), 0)
        S.bm_box(bm, (2.0, 0, 0.42), (1.0, 0.08, 0.06), 1)
    S.obj(name + "_body", _mesh(name, build, [blue, grey]), parent=root)
    S.obj(name + "_wh", _mesh(name + "_wh", lambda bm: [_cyl(bm, (sx * 1.0, sy * 0.62, 0.22), 0.22, 0.15, "Y", 14)
                                                          for sx in (-1, 1) for sy in (-1, 1)], [tyre]), parent=root)
    k = 0
    for ix in range(3):
        for iz in range(2):
            if k >= bags:
                break
            sz = (rng.uniform(0.6, 0.8), rng.uniform(0.4, 0.5), rng.uniform(0.24, 0.3))
            b = make_bag("%s_b%d" % (name, k), sz, rng=rng, tag=False)
            b.parent = root
            b.location = (-0.95 + 0.95 * ix, rng.uniform(-0.2, 0.2), 0.54 + iz * 0.32)
            b.rotation_euler = (0, 0, math.pi / 2 + rng.uniform(-0.15, 0.15))
            k += 1
    return root


def _v_makeup(ctx, p):
    """Make-up area: bags circulate on an oval carousel (your flight's pile) next to a cart being loaded."""
    T = ctx.frames
    _hall(ctx, (30.0, 22.0), 6.0, (0.0, 2.0), p)
    z = 0.55
    R, Ls = 1.6, 7.0
    plate = S.pbr("ed_plate", hexc("aab2ba"), 0.3, 0.7, var=0.02)
    base = S.pbr("ed_cart_g", hexc("b5bcc3"), 0.4, 0.6, var=0.02)

    def oval(bm, r_in, r_out, zz, n=24):
        def pts(r):
            q = []
            for i in range(n + 1):
                a = -math.pi / 2 + math.pi * i / n
                q.append((Ls / 2 + r * math.cos(a), r * math.sin(a)))
            for i in range(n + 1):
                a = math.pi / 2 + math.pi * i / n
                q.append((-Ls / 2 + r * math.cos(a), r * math.sin(a)))
            return q
        pi, po = pts(r_in), pts(r_out)
        vi = [bm.verts.new((x, y, zz + 0.12)) for x, y in pi]
        vo = [bm.verts.new((x, y, zz - 0.05)) for x, y in po]
        m = len(vi)
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((vi[i], vo[i], vo[j], vi[j]))

    def build(bm):
        oval(bm, R - 0.6, R + 0.5, z)
        S.bm_box(bm, (0, 0, z / 2), (Ls + 2 * R - 1.4, 2 * R - 1.4, z), 1)
    S.obj("carousel", _mesh("carousel", build, [plate, base], smooth=False))
    rng = random.Random(41)

    def opos(s):
        per = 2 * Ls + 2 * math.pi * R
        s %= per
        if s < Ls:
            return (-Ls / 2 + s, -R), 0.0
        s -= Ls
        if s < math.pi * R:
            a = -math.pi / 2 + s / R
            return (Ls / 2 + R * math.cos(a), R * math.sin(a)), a + math.pi / 2
        s -= math.pi * R
        if s < Ls:
            return (Ls / 2 - s, R), math.pi
        s -= Ls
        a = math.pi / 2 + s / R
        return (-Ls / 2 + R * math.cos(a), R * math.sin(a)), a + math.pi / 2
    per = 2 * Ls + 2 * math.pi * R
    v = 0.45
    nb = 13
    for k in range(nb):
        b = make_bag("c%d" % k, (rng.uniform(0.55, 0.8), rng.uniform(0.38, 0.5), rng.uniform(0.22, 0.3)),
                     tag=(k % 2 == 0), rng=rng)
        s0 = per * k / nb + rng.uniform(-0.2, 0.2)
        off = rng.uniform(-0.3, 0.3)
        prev = None
        for f in list(range(1, T + 1, 3)) + [T]:
            (x, y), yaw = opos(s0 + v * (f - 1) / ctx.fps)
            if prev is not None:
                while yaw - prev > math.pi:
                    yaw -= 2 * math.pi
                while yaw - prev < -math.pi:
                    yaw += 2 * math.pi
            prev = yaw
            kf(b, "location", f, Vector((x, y, z + 0.08)))
            kf(b, "rotation_euler", f, Vector((math.radians(-7), 0, yaw + off)))
        _interp(b, "LINEAR")
    # feed belt dropping in from the side + carts
    belt(ctx, "feed", (-14, 3.6), (-2.0, 3.6), z=1.4, speed=0.6)
    make_cart("cart1", (2.5, -4.4, 0), 0.0, 6, rng)
    make_cart("cart2", (-1.5, -4.4, 0), 0.0, 3, rng)
    tug = S.pbr("ed_tug", hexc("f2c230"), 0.45, 0.2, var=0.04)
    S.obj("tug", _mesh("tug", lambda bm: (_rbox(bm, (6.3, -4.4, 0.75), (2.2, 1.5, 1.0), 0.1, 2),
                                          _rbox(bm, (5.8, -4.4, 1.6), (1.0, 1.3, 0.8), 0.06, 2)), [tug]))
    _cam_static(ctx, p.get("cam0", (-7.0, -8.3, 5.4)), p.get("tgt0", (0.6, -0.8, 0.4)),
                p.get("cam1", (-6.6, -8.0, 5.2)), p.get("tgt1", (0.8, -0.8, 0.4)), lens=p.get("lens", 30))
    S.anchor(ctx, "pile", _empty("pile_pt", (0, 0, z + 1.3)))
    S.anchor(ctx, "cart", _empty("cart_pt", (2.5, -4.4, 2.4)))


def _v_apron(ctx, p):
    """Airport world, apron: parked airliner, belt loader at the forward hold, a tug pulls the baggage cart train
    in and bags ride the loader belt up into the plane's belly."""
    T = ctx.frames
    A._world(ctx, p, sun_az=p.get("sun_az", -35.0))
    root, parts = A.make_airliner_v2(ctx, "park", gear_down=True)
    pc = Vector(p.get("plane_at", (205.0, 560.0)))
    root.location = (pc.x, pc.y, 4.63)
    root.rotation_euler = (0, 0, math.radians(-90))          # nose towards +X (terminal)
    # forward hold door on the right side (local +X side when nose +Y... right side = local +X)
    door_l = Vector((1.72, 8.5, -1.05))
    root_m = Matrix.Translation(Vector((pc.x, pc.y, 4.63))) @ Matrix.Rotation(math.radians(-90), 4, "Z")
    door_w = root_m @ door_l
    dark = S.pbr("ed_dark", hexc("15171a"), 0.9, var=0)
    S.obj("hold_door", _mesh("hold_door", lambda bm: S.bm_box(bm, (1.66, 8.5, -1.05), (0.12, 1.5, 1.1)), [dark]),
          parent=root)
    # belt loader: chassis on the ground, inclined belt from 0.9 m up to the door sill
    out = (root_m.to_3x3() @ Vector((1, 0, 0))).normalized()      # outward from the right side
    sill = door_w + Vector((0, 0, -0.55))
    low = door_w + out * 7.5
    low.z = 0.9 + 0.28
    d = sill - low
    pitch = math.atan2(d.z, Vector((d.x, d.y)).length)
    yaw = math.atan2(d.y, d.x)
    yel = S.pbr("ed_tug", hexc("f2c230"), 0.45, 0.2, var=0.04)
    grey = S.pbr("ed_cart_g", hexc("b5bcc3"), 0.4, 0.6, var=0.02)
    tyre = S.pbr("al_dark_v2", hexc("17191d"), 0.5, var=0)
    ln = d.length
    lo = _empty("loader", tuple(low))
    lo.rotation_euler = (0, 0, yaw)

    def chassis(bm):
        S.bm_box(bm, (ln * 0.45, 0, -0.45), (ln * 0.9, 1.6, 0.5), 0)
        _rbox(bm, (0.9, -0.55, 0.2), (1.4, 0.9, 1.2), 0.08, 2, 0)
    S.obj("loader_chassis", _mesh("loader_chassis", chassis, [yel]), parent=lo)
    S.obj("loader_wh", _mesh("loader_wh", lambda bm: [_cyl(bm, (x, s * 0.75, -0.6), 0.33, 0.25, "Y", 14)
                                                       for x in (0.6, ln * 0.8) for s in (-1, 1)], [tyre]), parent=lo)
    bl = belt(ctx, "loader_belt", (0, 0), (ln, 0), z=0.0, w=0.7, speed=0.8, legs=False)
    bl.parent = lo
    bl.location = (0, 0, 0)
    bl.rotation_euler = (0, -pitch, 0)
    for s in (-1, 1):
        S.obj("loader_strut%d" % s, _mesh("loader_strut", lambda bm: S.bm_box(bm, (0, 0, 0), (0.12, 0.12, 1.0)), [grey]),
              (ln * 0.55, s * 0.6, ln * 0.55 * math.tan(pitch) / 2 - 0.2), (0, 0, 0), (1, 1, ln * 0.55 * math.tan(pitch) + 0.4),
              parent=lo)
    rng = random.Random(51)
    # bags riding up the loader belt (in loader space)
    v = 0.8
    for k in range(4):
        b = make_bag("up%d" % k, (rng.uniform(0.55, 0.75), 0.42, 0.26), tag=False, rng=rng)
        b.parent = lo
        s0 = -1.5 * k
        for f in list(range(1, T + 1, 2)) + [T]:
            s = (s0 + v * (f - 1) / ctx.fps) % (ln + 1.0)
            kf(b, "location", f, Vector((s * math.cos(pitch), 0, s * math.sin(pitch) + 0.02)))
            kf(b, "rotation_euler", f, Vector((0, -pitch, 0)))
            kf(b, "scale", f, Vector((1, 1, 1)) if s < ln - 0.3 else Vector((0.001, 0.001, 0.001)))
        _interp(b, "LINEAR")
    # cart train: tug + 2 carts arrive along the apron and stop beside the loader
    side = Vector((-out.y, out.x, 0))
    stop = low + out * 3.5 + side * 2.0
    stop.z = 0.28
    trn = _empty("train")
    trn.rotation_euler = (0, 0, math.atan2(side.y, side.x))
    run = 14.0
    fstop = int(T * 0.55)
    for f in list(range(1, T + 1, 2)) + [T]:
        u = min(1.0, (f - 1) / max(1, fstop - 1))
        e = 1 - (1 - u) ** 2
        kf(trn, "location", f, stop - side * run * (1 - e))
    _interp(trn, "LINEAR")
    tug_m = S.pbr("ed_tug_w", hexc("e9ecef"), 0.45, 0.2, var=0.04)
    tug = _empty("tug", (2.8, 0, 0.28 * 0), trn)
    S.obj("tug_body", _mesh("tug_body", lambda bm: (_rbox(bm, (0, 0, 0.7), (2.4, 1.5, 0.9), 0.1, 2),
                                                    _rbox(bm, (-0.4, 0, 1.55), (1.0, 1.3, 0.8), 0.06, 2)), [tug_m]),
          parent=tug)
    S.obj("tug_wh", _mesh("tug_wh", lambda bm: [_cyl(bm, (x, s * 0.7, 0.3), 0.3, 0.25, "Y", 14)
                                                 for x in (-0.7, 0.7) for s in (-1, 1)], [tyre]), parent=tug)
    c1 = make_cart("cart1", (-0.2, 0, 0), 0.0, 6, rng)
    c1.parent = trn
    c2 = make_cart("cart2", (-3.6, 0, 0), 0.0, 5, rng)
    c2.parent = trn
    S.anchor(ctx, "cart", c1, (0, 0, 2.3))
    S.anchor(ctx, "hold", root, (1.72, 8.5, -1.05))
    cam_c = low + out * p.get("cam_out", 10.0) - side * p.get("cam_aft", 9.0)
    cam_c.z = 1.7
    tgt = door_w + out * 3.0 + Vector((0, 0, -1.2))
    c0 = p.get("cam0", tuple(cam_c))
    c1_ = p.get("cam1", tuple(cam_c + side * -1.5 + Vector((0, 0, 0.3))))
    _cam_static(ctx, c0, tuple(tgt), c1_, tuple(tgt), lens=p.get("lens", 24), clip=0.5)
    ctx.cam.data.clip_end = 16000.0


BAG_VIEWS = {"counter": _v_counter, "tag": _v_tag, "scan_arch": _v_scan_arch, "screen": _v_screen,
             "sort": _v_sort, "makeup": _v_makeup, "apron": _v_apron}


def b_bag_belt_v2(ctx, p):
    """Checked-bag journey (see BAG_VIEWS). Interior views share one lightbox-lit hall look; apron is the airport."""
    _BAG_MESH.clear()
    BAG_VIEWS[p.get("view", "counter")](ctx, p)


S.V2_BUILDERS.update({
    "ed_airport_fog_v2": b_ed_airport_fog_v2,
    "ed_cockpit_fog_v2": b_ed_cockpit_fog_v2,
    "ils_beams_v2": b_ils_beams_v2,
    "bag_belt_v2": b_bag_belt_v2,
})


# ======================================================================================================================
# Track A batch 02 (28 Nov 2026): mw_kitchen_v2 (microwave door mesh), checkout_v2 (gum barcode), lift_v2 (elevator
# counterweight). Same rules: no 3D text (barcode bars are graphics, no digits), never a void (kitchen / store are
# lightbox-lit interior sets, the elevator lives in the scene_lib_v2_tower city), non-graphic, in-memory textures
# <= 512 px, no volumetrics.
# ======================================================================================================================
def _point(name, loc, energy, color=(1.0, 0.85, 0.6), radius=0.03):
    d = bpy.data.lights.new(name, "POINT")
    d.energy = energy
    d.color = color
    d.shadow_soft_size = radius
    o = L.link(bpy.data.objects.new(name, d))
    o.location = loc
    return o


def wave_ribbon(name, length, wl, amp, width, mat, plane="XZ", parent=None, seg_per_wl=24):
    """Flat sine ribbon centred on its origin, travelling along local +X. plane "XZ": amplitude along Z (face normal
    Y, read by a camera looking along Y); "XY": amplitude along Y (face up, read from above). Zero at both ends."""
    n = max(10, int(length / wl * seg_per_wl))
    bm = bmesh.new()
    prev = None
    k = 2 * math.pi / wl
    for i in range(n + 1):
        x = length * i / n
        a = amp * math.sin(k * x)
        da = amp * k * math.cos(k * x)
        nx, na = -da, 1.0
        ln = math.hypot(nx, na)
        nx, na = nx / ln, na / ln
        hw = width / 2
        p1 = (x - length / 2 + nx * hw, a + na * hw)
        p2 = (x - length / 2 - nx * hw, a - na * hw)
        if plane == "XZ":
            va, vb = bm.verts.new((p1[0], 0, p1[1])), bm.verts.new((p2[0], 0, p2[1]))
        else:
            va, vb = bm.verts.new((p1[0], p1[1], 0)), bm.verts.new((p2[0], p2[1], 0))
        if prev:
            bm.faces.new((prev[0], prev[1], vb, va))
        prev = (va, vb)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def _perf_mat(name, pitch, hole=0.34):
    """Perforated dark metal (door screen): round holes on a square grid in the object's local XZ plane, cut with a
    Transparent mix (dithered, cheap). `hole` = hole radius / pitch."""
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, pr = S._new_mat(name)
    pr.inputs["Base Color"].default_value = hexc("17191c")
    pr.inputs["Metallic"].default_value = 0.6
    pr.inputs["Roughness"].default_value = 0.45
    tc = N.new("ShaderNodeTexCoord")
    mul = N.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = (1.0 / pitch, 0.0, 1.0 / pitch)
    Lk.new(tc.outputs["Object"], mul.inputs[0])
    fr = N.new("ShaderNodeVectorMath")
    fr.operation = "FRACTION"
    Lk.new(mul.outputs[0], fr.inputs[0])
    sb = N.new("ShaderNodeVectorMath")
    sb.operation = "SUBTRACT"
    sb.inputs[1].default_value = (0.5, 0.0, 0.5)
    Lk.new(fr.outputs[0], sb.inputs[0])
    ln = N.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    Lk.new(sb.outputs[0], ln.inputs[0])
    lt = N.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    lt.inputs[1].default_value = hole
    Lk.new(ln.outputs["Value"], lt.inputs[0])
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    Lk.new(lt.outputs[0], mx.inputs[0])
    Lk.new(pr.outputs[0], mx.inputs[1])
    Lk.new(tr.outputs[0], mx.inputs[2])
    S._MV2[name] = S._finish(m, mx.outputs[0], haze=False)
    return S._MV2[name]


def _glow_keys(name, color, keys):
    """Additive glow material with keyed strength [(frame, strength)]."""
    m, sock = L.add_mat(name, color, 0.0)
    for f, v in keys:
        L.kf_socket(sock, max(1, int(f)), v, "LINEAR")
    return m


def _cam_keys2(ctx, keys, lens=30, clip=0.02, far=500.0):
    """keys = [(frame, cam, tgt)] (frame <= 1.0 float = fraction of the shot)."""
    T = ctx.frames
    ks = [(int(round(1 + (T - 1) * f)) if isinstance(f, float) and f <= 1.0 else int(f), c, t) for f, c, t in keys]
    A._cam(ctx, ks[0][1], ks[0][2], lens=lens)
    A._cam_keys(ctx, ks)
    ctx.cam.data.clip_start = clip
    ctx.cam.data.clip_end = far


# ---------------------------------------------------------------- kitchen + microwave
MW_ROOT = (0.0, 0.02, 0.92)          # microwave bottom centre on the counter (front face at y = -0.18)
MW_W, MW_D, MW_H = 0.52, 0.40, 0.31
CAV = (-MW_W / 2 + 0.03, MW_W / 2 - 0.15, -MW_D / 2 + 0.02, MW_D / 2 - 0.03, 0.04, MW_H - 0.04)   # x0 x1 y0 y1 z0 z1


def _kitchen(ctx, p):
    """Bright kitchen: wood floor, sage lower + upper cabinets, light stone counter, tiled backsplash, a window with
    a soft daylight panel, ceiling lights, a few props. Own lit set (never a void)."""
    sc = ctx.scene
    w = bpy.data.worlds.new("kitchen_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.78, 0.76, 0.72, 1.0)
    bg.inputs["Strength"].default_value = 0.5
    sc.view_settings.exposure = p.get("exposure", -0.6)
    L.fog(0.001, hexc("ece6dc"), start=8.0)
    floor = S.pbr("k_floor", hexc("b48a5e"), 0.55, var=0.12, var_scale=2.5, bump=0.01)
    wall = S.pbr("k_wall", hexc("e4dccf"), 0.8, var=0.02)
    cab = S.pbr("k_cab", hexc("8fa79a"), 0.45, coat=0.2, var=0.02)
    top = S.pbr("k_top", hexc("d8d0c4"), 0.3, coat=0.3, var=0.05, var_scale=4.0)
    tile = S.pbr("k_tile", hexc("e9e6df"), 0.25, coat=0.4, var=0.02)
    knob = S.pbr("k_knob", hexc("c9a35a"), 0.3, 0.8, var=0)
    ceil = S.pbr("k_ceil", hexc("f4f1ec"), 0.85, var=0)
    S.plane_obj("k_floor", 7.0, 7.0, (0, -2.0, 0.0), floor)

    # back wall with a window opening at x 1.35..2.35, z 1.05..1.9
    def back(bm):
        for (x0, x1, z0, z1) in ((-3.0, 1.35, 0.0, 2.8), (2.35, 3.0, 0.0, 2.8), (1.35, 2.35, 0.0, 1.05),
                                 (1.35, 2.35, 1.9, 2.8)):
            S.bm_box(bm, ((x0 + x1) / 2, 0.5, (z0 + z1) / 2), (x1 - x0, 0.2, z1 - z0), 0)
        S.bm_box(bm, (-3.0, -2.0, 1.4), (0.2, 5.2, 2.8), 0)
        S.bm_box(bm, (3.0, -2.0, 1.4), (0.2, 5.2, 2.8), 0)
        S.bm_box(bm, (0, -4.6, 1.4), (6.0, 0.2, 2.8), 0)
        S.bm_box(bm, (0, -2.0, 2.85), (6.0, 5.4, 0.1), 1)
    S.obj("k_room", _mesh("k_room", back, [wall, ceil]))
    sky = S.emis("k_sky", hexc("dcebf7"), 2.2)
    S.obj("k_sky", _mesh("k_sky", lambda bm: S.bm_box(bm, (1.85, 0.75, 1.48), (1.4, 0.02, 1.2)), [sky]))
    frame = S.pbr("k_wframe", hexc("fbfaf7"), 0.4, var=0)
    S.obj("k_wframe", _mesh("k_wframe", lambda bm: [S.bm_box(bm, c, s) for c, s in (
        ((1.85, 0.41, 1.05), (1.1, 0.06, 0.05)), ((1.85, 0.41, 1.9), (1.1, 0.06, 0.05)),
        ((1.33, 0.41, 1.48), (0.05, 0.06, 0.9)), ((2.37, 0.41, 1.48), (0.05, 0.06, 0.9)),
        ((1.85, 0.41, 1.48), (0.03, 0.04, 0.85)), ((1.85, 0.32, 1.03), (1.2, 0.2, 0.03)))], [frame]))

    def cabinets(bm):
        # lower run x -2.9..2.9 (counter z 0.92), toe kick, door seams
        S.bm_box(bm, (0, 0.05, 0.46), (5.8, 0.6, 0.84), 0)
        S.bm_box(bm, (0, 0.04, 0.9), (5.9, 0.68, 0.04), 1)
        for x in (-2.4, -1.6, -0.8, 0.0, 0.8, 1.6, 2.4):
            S.bm_box(bm, (x, -0.252, 0.5), (0.012, 0.01, 0.72), 3)
        for x in (-2.0, -1.2, -0.4, 0.4, 1.2, 2.0):
            S.bm_box(bm, (x - 0.3, -0.27, 0.75), (0.12, 0.025, 0.015), 4)
        # backsplash
        S.bm_box(bm, (0, 0.395, 1.18), (5.8, 0.01, 0.52), 2)
        # upper cabinets (leave the window bay open)
        for (x0, x1) in ((-2.9, 1.2), (2.5, 2.9)):
            S.bm_box(bm, ((x0 + x1) / 2, 0.22, 1.98), (x1 - x0, 0.36, 0.78), 0)
            x = x0 + 0.45
            while x < x1 - 0.1:
                S.bm_box(bm, (x, 0.035, 1.98), (0.012, 0.01, 0.7), 3)
                x += 0.6
        # tall pantry at the far left
        S.bm_box(bm, (-2.55, 0.05, 1.2), (0.7, 0.6, 2.4), 0)
    seam = S.pbr("k_seam", hexc("6f8a7c"), 0.6, var=0)
    S.obj("k_cab", _mesh("k_cab", cabinets, [cab, top, tile, seam, knob]))
    # props: kettle, fruit bowl, cutting board, plant
    metal = S.pbr("k_steel", hexc("c7ccd1"), 0.25, 0.9, var=0)
    wood = S.pbr("k_board", hexc("c28f58"), 0.5, var=0.06, var_scale=6.0)
    pot = S.pbr("k_pot", hexc("d9774f"), 0.6, var=0.03)
    leaf = S.pbr("k_leaf", hexc("4f8a45"), 0.6, var=0.08, var_scale=8.0)
    fruit = [S.pbr("k_fr%d" % i, hexc(c), 0.45, coat=0.3, var=0.04) for i, c in enumerate(("e0a526", "cf3b2b", "8cbf3f"))]

    def props(bm):
        _cyl(bm, (0.85, 0.15, 1.04), 0.09, 0.2, "Z", 20, 0)
        _cyl(bm, (0.85, 0.15, 1.15), 0.03, 0.04, "Z", 10, 0)
        _rbox(bm, (-0.85, 0.2, 0.935), (0.42, 0.28, 0.025), 0.01, 2, 1)
        _cyl(bm, (2.6, 0.15, 1.02), 0.09, 0.2, "Z", 16, 2)
    S.obj("k_props", _mesh("k_props", props, [metal, wood, pot]))
    bm = bmesh.new()
    rng = random.Random(7)
    for k in range(9):
        r = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=rng.uniform(0.07, 0.1))
        bmesh.ops.translate(bm, vec=(2.6 + rng.uniform(-0.08, 0.08), 0.15 + rng.uniform(-0.08, 0.08),
                                     1.2 + rng.uniform(0, 0.2)), verts=r["verts"])
    S.obj("k_plant", S.mesh_from_bm("k_plant", bm, [leaf], smooth=True))
    bm = bmesh.new()
    for k in range(5):
        r = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.04)
        bmesh.ops.translate(bm, vec=(-1.55 + 0.07 * k - 0.02 * (k % 2), 0.12 + 0.05 * (k % 2), 0.98), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = k % 3
    S.obj("k_fruit", S.mesh_from_bm("k_fruit", bm, fruit, smooth=True))
    lp = S.emis("k_lamp", hexc("fff6e8"), 3.0)
    S.obj("k_lamps", _mesh("k_lamps", lambda bm: [_cyl(bm, (x, y, 2.79), 0.09, 0.02, "Z", 16) for x in (-1.5, 0.0, 1.5)
                                                   for y in (-0.6, -2.6)], [lp]))
    for k, (x, y) in enumerate(((-1.2, -1.0), (1.2, -1.0), (0.0, -3.0))):
        A._area("k_a%d" % k, (x, y, 2.7), 1.6, 170.0, (1.0, 0.96, 0.9), size_y=1.6)
    win = A._area("k_win", (1.85, 0.2, 1.48), 1.0, 120.0, (0.9, 0.95, 1.0), size_y=0.85)
    win.rotation_euler = (math.radians(-90), 0, 0)


def make_microwave(ctx, top=True, left=True, pitch=0.0022, lamp=True, spin=True):
    """Countertop microwave at MW_ROOT. top/left False = cut-away (case + cavity wall removed). Door window = perforated
    metal screen (_perf_mat, `pitch` m). Cavity: light enamel, warm lamp, glass turntable with a bowl of soup.
    Right compartment: magnetron (fins, antenna dome) + waveguide to a mica cover on the cavity wall.
    Returns dict(root, turntable, food_z)."""
    T = ctx.frames
    W, D, H = MW_W, MW_D, MW_H
    x0, x1, y0, y1, z0, z1 = CAV
    root = _empty("mw", MW_ROOT)
    case = S.pbr("mw_case", hexc("eceef0"), 0.3, 0.15, coat=0.4, var=0.02)
    cav = S.pbr("mw_cav", hexc("c3c8cc"), 0.4, 0.0, coat=0.2, var=0.02)
    panel = S.pbr("mw_panel", hexc("1d2024"), 0.25, 0.0, coat=0.6, var=0)
    trim = S.pbr("mw_trim", hexc("2b2e33"), 0.4, 0.3, var=0)
    t = 0.008
    dx0, dx1, fw = -W / 2, W / 2 - 0.137, 0.035

    def shell(bm):
        S.bm_box(bm, (0, 0, t / 2), (W, D, t), 0)
        if top:
            S.bm_box(bm, (0, 0, H - t / 2), (W, D, t), 0)
        S.bm_box(bm, (0, D / 2 - t / 2, H / 2), (W, t, H), 0)
        S.bm_box(bm, (W / 2 - t / 2, 0, H / 2), (t, D, H), 0)
        if left:
            S.bm_box(bm, (-W / 2 + t / 2, 0, H / 2), (t, D, H), 0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        S.bm_box(bm, (cx, cy, z0), (x1 - x0, y1 - y0, t), 1)
        S.bm_box(bm, (cx, y1, (z0 + z1) / 2), (x1 - x0, t, z1 - z0), 1)
        S.bm_box(bm, (x1, cy, (z0 + z1) / 2), (t, y1 - y0, z1 - z0), 1)
        if top:
            S.bm_box(bm, (cx, cy, z1), (x1 - x0, y1 - y0, t), 1)
        if left:
            S.bm_box(bm, (x0, cy, (z0 + z1) / 2), (t, y1 - y0, z1 - z0), 1)
        S.bm_box(bm, (W / 2 - 0.0675, -D / 2 + 0.006, H / 2), (0.135, 0.012, H), 2)        # control panel
        for (c, s) in ((((dx0 + dx1) / 2, -D / 2 - 0.012, H - fw / 2), (dx1 - dx0, 0.024, fw)),
                       (((dx0 + dx1) / 2, -D / 2 - 0.012, fw / 2), (dx1 - dx0, 0.024, fw)),
                       ((dx0 + fw / 2, -D / 2 - 0.012, H / 2), (fw, 0.024, H)),
                       ((dx1 - fw / 2, -D / 2 - 0.012, H / 2), (fw, 0.024, H))):
            S.bm_box(bm, c, s, 2)
        S.bm_box(bm, (dx1 - 0.012, -D / 2 - 0.03, H / 2), (0.018, 0.02, H * 0.6), 3)      # handle
        for i in range(4):                                                                  # buttons (no text)
            for j in range(3):
                S.bm_box(bm, (W / 2 - 0.105 + 0.038 * j, -D / 2 - 0.001, H - 0.12 - 0.032 * i), (0.026, 0.004, 0.02), 3)
        _cyl(bm, (W / 2 - 0.067, -D / 2 - 0.006, 0.06), 0.022, 0.012, "Y", 18, 3)
        for sx in (-1, 1):                                                                  # feet
            S.bm_box(bm, (sx * 0.2, 0, -0.004), (0.04, D - 0.06, 0.008), 3)
    S.obj("mw_shell", _mesh("mw_shell", shell, [case, cav, panel, trim]), parent=root)
    disp = S.emis("mw_disp", hexc("3ad6c2"), 2.5)
    S.obj("mw_disp", _mesh("mw_disp", lambda bm: S.bm_box(bm, (W / 2 - 0.067, -D / 2 - 0.002, H - 0.06),
                                                         (0.09, 0.004, 0.028)), [disp]), parent=root)
    # door screen (perforated) inside the frame
    scr = S.obj("mw_screen", _mesh("mw_screen", lambda bm: S.bm_box(bm, ((dx0 + dx1) / 2, -D / 2 - 0.008, H / 2),
                                                                    (dx1 - dx0 - 2 * fw + 0.004, 0.001, H - 2 * fw + 0.004)),
                                   [_perf_mat("mw_perf_%d" % int(pitch * 1e4), pitch)]), parent=root)
    scr.visible_shadow = False
    # magnetron + waveguide in the right compartment
    alu = S.pbr("mw_alu", hexc("b9c0c6"), 0.3, 0.9, var=0)
    cop = S.pbr("mw_copper", hexc("c27a45"), 0.3, 0.9, var=0)
    mag = S.pbr("mw_magnet", hexc("3b4046"), 0.5, 0.3, var=0)
    mica = S.pbr("mw_mica", hexc("d8c7a2"), 0.6, var=0.03)
    mx = (x1 + W / 2) / 2

    def magnetron(bm):
        S.bm_box(bm, (mx, 0.06, 0.12), (0.09, 0.09, 0.07), 0)
        for k in range(7):
            S.bm_box(bm, (mx, 0.06, 0.09 + 0.01 * k), (0.11, 0.1, 0.003), 0)
        _cyl(bm, (mx, 0.06, 0.07), 0.042, 0.02, "Z", 20, 2)
        _cyl(bm, (mx, 0.06, 0.168), 0.042, 0.02, "Z", 20, 2)
        _cyl(bm, (mx, 0.06, 0.19), 0.012, 0.03, "Z", 12, 1)
        S.bm_box(bm, ((mx + x1) / 2, 0.06, 0.215), (mx - x1 + 0.04, 0.07, 0.04), 0)   # waveguide
        S.bm_box(bm, (mx + 0.035, -0.08, 0.11), (0.05, 0.06, 0.12), 2)               # capacitor / transformer
    S.obj("mw_magnetron", _mesh("mw_magnetron", magnetron, [alu, cop, mag]), parent=root)
    S.obj("mw_mica", _mesh("mw_mica", lambda bm: S.bm_box(bm, (x1 - 0.005, 0.06, 0.215), (0.003, 0.06, 0.05)),
                           [mica]), parent=root)
    # turntable + bowl
    tt = _empty("mw_tt", ((x0 + x1) / 2, (y0 + y1) / 2, z0 + 0.006), parent=root)
    glass = S.pbr("mw_plate", hexc("dfe9e8"), 0.08, coat=1.0, var=0)
    bowl = S.pbr("mw_bowl", hexc("f4f2ee"), 0.25, coat=0.5, var=0)
    soup = S.pbr("mw_soup", hexc("d9792e"), 0.35, coat=0.3, var=0.12, var_scale=40.0, bump=0.02)

    def plate(bm):
        _cyl(bm, (0, 0, 0.006), 0.135, 0.008, "Z", 40, 0)
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.055, radius2=0.085, depth=0.06)
        bmesh.ops.translate(bm, vec=(0, 0, 0.04), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 1
        _cyl(bm, (0, 0, 0.071), 0.079, 0.004, "Z", 32, 2)
    S.obj("mw_plate", _mesh("mw_plate", plate, [glass, bowl, soup], smooth=True), parent=tt)
    if spin:
        kf(tt, "rotation_euler", 1, Vector((0, 0, 0)))
        kf(tt, "rotation_euler", T + 1, Vector((0, 0, 2 * math.pi * 0.12 * T / ctx.fps)))
        _interp(tt, "LINEAR")
    if lamp:
        _point("mw_lamp", (MW_ROOT[0] + x1 - 0.03, MW_ROOT[1] + y1 - 0.05, MW_ROOT[2] + z1 - 0.02), 0.9,
               (1.0, 0.82, 0.55), 0.02)
    return {"root": root, "tt": tt, "food_z": z0 + 0.006 + 0.073}


def _mw_w(x, y, z):
    return (MW_ROOT[0] + x, MW_ROOT[1] + y, MW_ROOT[2] + z)


def _packets(ctx, paths, f0, n, gap, speed=0.22, wl=0.05, amp=0.009, z=0.2, name="pk"):
    """Teal microwave packets (flat XY ribbons) running along bounce polylines (microwave-local XY at height z)."""
    mat = S.emis("mw_wave", TEAL, 5.0)
    objs = []
    for k in range(n):
        pts = [_mw_w(px, py, z) for px, py in paths[k % len(paths)]]
        o = wave_ribbon("%s%d" % (name, k), wl * 2.0, wl, amp, 0.004, mat, plane="XY")
        fs = int(f0 + k * gap)
        fr = path_move(ctx, o, pts, fs, speed, every=1)
        _show(o, max(2, fs), int(fr[-1]) + 1)
        objs.append(o)
    return objs


BOUNCE = [[(0.10, 0.06), (-0.22, -0.05), (-0.05, -0.17), (0.10, -0.03), (-0.06, 0.0)],
          [(0.10, 0.06), (-0.08, 0.16), (-0.22, 0.03), (-0.06, 0.0)],
          [(0.10, 0.06), (-0.15, -0.17), (-0.22, 0.10), (-0.06, 0.0)],
          [(0.10, 0.06), (0.02, 0.16), (-0.22, -0.12), (-0.06, 0.0)]]


def _standing_wave(ctx, x=-0.2, amp=0.022):
    """12 cm standing wave between the cavity back wall and the door (microwave-local), breathing amplitude."""
    T = ctx.frames
    y_back, y_door = CAV[3] - 0.004, -MW_D / 2 - 0.004
    ln = y_back - y_door
    wl = 2 * ln / 6.0
    o = wave_ribbon("mw_standing", ln, wl, amp, 0.006, S.emis("mw_wave_big", TEAL, 6.0), plane="XZ")
    o.location = _mw_w(x, (y_back + y_door) / 2, 0.16)
    o.rotation_euler = (0, 0, -math.pi / 2)
    for f in range(1, T + 2, 12):
        kf(o, "scale", f, Vector((1, 1, 1.0 if (f // 12) % 2 == 0 else 0.7)), "BEZIER")
    return o, wl


def _v_mw(ctx, p, view):
    T = ctx.frames
    _kitchen(ctx, p)
    cut_top = view in ("inside", "bounce", "water")
    cut_left = view in ("mesh", "light")
    pitch = p.get("pitch", 0.0022 if view in ("mesh", "light") else 0.0045)
    mw = make_microwave(ctx, top=not cut_top, left=not cut_left, pitch=pitch)
    x0, x1, y0, y1, z0, z1 = CAV
    if view == "hook":
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.75, -2.2, 1.5)), p.get("tgt0", (-0.02, 0.0, 1.1))),
                         (1.0, p.get("cam1", (-0.42, -1.3, 1.26)), p.get("tgt1", (-0.04, 0.0, 1.08)))],
                   lens=p.get("lens", 32))
        S.anchor(ctx, "door", mw["root"], (-0.07, -MW_D / 2, MW_H / 2))
    elif view == "outro":
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.5, -1.25, 1.3)), p.get("tgt0", (-0.04, 0.0, 1.06))),
                         (1.0, p.get("cam1", (-1.1, -3.3, 1.75)), p.get("tgt1", (0.1, 0.0, 1.25)))],
                   lens=p.get("lens", 30))
    elif view == "inside":
        fw = ctx.word_time(p.get("wave_cue", "microwaves"), 0.4)
        _packets(ctx, BOUNCE, fw, 10, 7)
        A.ring_pulses(ctx, _mw_w(x1 - 0.01, 0.06, 0.215), fw, color=TEAL, count=3, gap=9, r1=0.08, life=22,
                      rot=(0, math.radians(90), 0), name="mw_emit")
        _cam_keys2(ctx, [(1, p.get("cam0", (0.34, -0.24, 1.58)), p.get("tgt0", (0.15, 0.05, 1.03))),
                         (1.0, p.get("cam1", (0.32, -0.2, 1.54)), p.get("tgt1", (0.14, 0.05, 1.03)))],
                   lens=p.get("lens", 30))
        S.anchor(ctx, "magnetron", mw["root"], ((x1 + MW_W / 2) / 2, 0.06, 0.2))
    elif view == "bounce":
        _packets(ctx, BOUNCE, 2, 16, 6, speed=0.24)
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.05, -0.42, 1.68)), p.get("tgt0", (-0.06, 0.0, 1.03))),
                         (1.0, p.get("cam1", (-0.04, -0.36, 1.62)), p.get("tgt1", (-0.06, 0.0, 1.03)))],
                   lens=p.get("lens", 28))
        S.anchor(ctx, "wall", mw["root"], (x0, -0.04, 0.2))
        S.anchor(ctx, "food", mw["tt"], (0, 0, 0.07))
    elif view == "water":
        fh = ctx.word_time(p.get("heat_cue", "heat"), 0.8)
        fv = ctx.word_time(p.get("vib_cue", "vibrate"), 0.5)
        o_m = S.pbr("h2o_o", hexc("e2463c"), 0.3, coat=0.6, var=0)
        h_m = S.pbr("h2o_h", hexc("f5f6f7"), 0.3, coat=0.6, var=0)
        rng = random.Random(21)
        mol = None
        for k in range(7):
            def build(bm):
                r = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.0085)
                for s in (-1, 1):
                    a = math.radians(52.25) * s
                    r2 = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.0055)
                    bmesh.ops.translate(bm, vec=(math.sin(a) * 0.0105, 0, -math.cos(a) * 0.0105), verts=r2["verts"])
                    for f in {f for v in r2["verts"] for f in v.link_faces}:
                        f.material_index = 1
            ang = k * 2.4
            rad = 0.018 + 0.05 * math.sqrt((k + 0.5) / 7.0)
            loc = Vector((math.cos(ang) * rad, math.sin(ang) * rad, mw["food_z"] - (z0 + 0.006) + 0.013))
            o = S.obj("h2o%d" % k, _mesh("h2o%d" % k, build, [o_m, h_m], smooth=True), tuple(loc), parent=mw["tt"])
            base = Vector((rng.uniform(0, 6.28), rng.uniform(0, 6.28), rng.uniform(0, 6.28)))
            for f in range(1, T + 2, 2):
                amp = 0.12 if f < fv else 0.45
                kf(o, "rotation_euler", f, base + Vector((rng.uniform(-amp, amp), rng.uniform(-amp, amp),
                                                         rng.uniform(-amp, amp))))
                j = 0.0006 if f < fv else 0.002
                kf(o, "location", f, loc + Vector((rng.uniform(-j, j), rng.uniform(-j, j), rng.uniform(-j, j))))
            _interp(o, "LINEAR")
            if k == 0:
                mol = o
        glow = _glow_keys("soup_glow", hexc("ff8a2a"), [(1, 0.0), (fv, 0.0), (fh, 0.35), (fh + 20, 0.9)])
        g = S.obj("soup_glow", _mesh("soup_glow", lambda bm: _cyl(bm, (0, 0, 0), 0.08, 0.002, "Z", 32),
                                     [glow]), (0, 0, mw["food_z"] - (z0 + 0.006) + 0.002), parent=mw["tt"])
        g.visible_shadow = False
        fc = _mw_w((x0 + x1) / 2, (y0 + y1) / 2, mw["food_z"])
        _cam_keys2(ctx, [(1, p.get("cam0", (fc[0] - 0.02, fc[1] - 0.2, fc[2] + 0.14)), p.get("tgt0", fc)),
                         (1.0, p.get("cam1", (fc[0] - 0.01, fc[1] - 0.15, fc[2] + 0.11)), p.get("tgt1", fc))],
                   lens=p.get("lens", 35))
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_distance = 0.2
        ctx.cam.data.dof.aperture_fstop = 4.0
        S.anchor(ctx, "molecule", mol)
    elif view in ("mesh", "light"):
        sw, wl = _standing_wave(ctx)
        A.ring_pulses(ctx, _mw_w(-0.2, -MW_D / 2 + 0.004, 0.16), 6, color=TEAL, count=6, gap=24, r1=0.05, life=20,
                      rot=(math.radians(90), 0, 0), name="mw_refl")
        S.anchor(ctx, "wave", sw, (wl * 1.25, 0, -0.022))
        S.anchor(ctx, "holes", mw["root"], (-0.13, -MW_D / 2 - 0.009, 0.2))
        if view == "light":
            am = S.emis("mw_light", hexc("ffc04a"), 7.0)
            rng = random.Random(8)
            for k in range(14):
                o = wave_ribbon("ph%d" % k, 0.05, 0.008, 0.0028, 0.0022, am, plane="XZ")
                o.rotation_euler = (0, 0, -math.pi / 2)
                xa, za = rng.uniform(-0.22, 0.05), rng.uniform(0.08, 0.25)
                ST_loop(o, _mw_w(xa, 0.02, za), _mw_w(xa + rng.uniform(-0.1, 0.1), -0.75, za + rng.uniform(-0.05, 0.08)),
                        T, 1, 40, phase=k / 14.0)
            S.anchor(ctx, "light", _empty("light_anc", _mw_w(-0.12, -0.42, 0.2)))
            _cam_keys2(ctx, [(1, p.get("cam0", (-0.78, -0.82, 1.2)), p.get("tgt0", (-0.1, -0.2, 1.06))),
                             (1.0, p.get("cam1", (-0.7, -0.74, 1.18)), p.get("tgt1", (-0.1, -0.2, 1.06)))],
                       lens=p.get("lens", 30))
        else:
            _cam_keys2(ctx, [(1, p.get("cam0", (-0.62, -0.44, 1.13)), p.get("tgt0", (-0.16, -0.07, 1.07))),
                             (1.0, p.get("cam1", (-0.57, -0.41, 1.12)), p.get("tgt1", (-0.16, -0.07, 1.07)))],
                       lens=p.get("lens", 30))


def ST_loop(o, p0, p1, T, f_on, period, phase=0.0):
    import scene_lib_v2_storm as ST
    ST.loop_move(o, p0, p1, T, f_on, period, phase=phase, grow=5)


def b_mw_kitchen_v2(ctx, p):
    """Microwave door mesh explainer. view hook | inside | bounce | water | mesh | light | outro (see _v_mw).
    Anchors: door (hook), magnetron (inside), wall + food (bounce), molecule (water), wave + holes (mesh/light),
    light (light). Params: wave_cue, vib_cue, heat_cue, pitch, cam0/1, tgt0/1, lens, exposure."""
    _v_mw(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- supermarket checkout (gum barcode)
def _upc_image(seed=11):
    """UPC-style barcode artwork made in memory (NO digits): white label, black bars, taller guard bars."""
    import numpy as np
    name = "ed_upc_img_%d" % seed
    if name in bpy.data.images:
        return bpy.data.images[name]
    W, H = 512, 256
    a = np.ones((H, W, 4), dtype=np.float32)
    a[..., :3] = 0.97
    rng = random.Random(seed)
    m = 3                                   # module width in px (95 modules + quiet zones)
    x = (W - 95 * m) // 2
    mods = [1, 0, 1]
    for _ in range(6):
        mods += [rng.choice((0, 1)) for _ in range(7)]
    mods += [0, 1, 0, 1, 0]
    for _ in range(6):
        mods += [rng.choice((0, 1)) for _ in range(7)]
    mods += [1, 0, 1]
    guards = set(list(range(3)) + list(range(45, 50)) + list(range(92, 95)))
    for i, v in enumerate(mods):
        if v:
            y0 = 30 if i in guards else 60
            a[y0:H - 30, x + i * m:x + (i + 1) * m, :3] = 0.04
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.pixels.foreach_set(a.ravel())
    img.pack()
    return img


def _upc_mat():
    if "ed_upc" in S._MV2:
        return S._MV2["ed_upc"]
    m, nt, N, Lk, pr = S._new_mat("ed_upc")
    tex = N.new("ShaderNodeTexImage")
    tex.image = _upc_image()
    tex.interpolation = "Cubic"
    Lk.new(N.new("ShaderNodeTexCoord").outputs["UV"], tex.inputs["Vector"])
    Lk.new(tex.outputs["Color"], pr.inputs["Base Color"])
    pr.inputs["Roughness"].default_value = 0.45
    S._MV2["ed_upc"] = S._finish(m, pr.outputs[0])
    return S._MV2["ed_upc"]


def _label_quad(bm, uvl, c, w, h, axis="-Y", mi=1):
    """UV-mapped quad centred at c facing -Y (or +Z) for barcode labels."""
    x, y, z = c
    if axis == "-Y":
        vs = [(x - w / 2, y, z - h / 2), (x + w / 2, y, z - h / 2), (x + w / 2, y, z + h / 2), (x - w / 2, y, z + h / 2)]
    else:   # +Z (label on top)
        vs = [(x - w / 2, y - h / 2, z), (x + w / 2, y - h / 2, z), (x + w / 2, y + h / 2, z), (x - w / 2, y + h / 2, z)]
    f = bm.faces.new([bm.verts.new(v) for v in vs])
    for lp, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uvl].uv = uv
    f.material_index = mi


PROD_COLS = ["d9462f", "f0b429", "2f8f86", "3a6fb0", "8a4fb0", "e07a1f", "5aa05a", "c23b6b", "f2e3c2", "2b2f36"]


def make_product(name, kind, size, color, label=True, parent=None):
    """Grocery item: kind box | can | gum. Generic colour blocks, no logos or text; barcode label on the -Y face
    (box / gum) or wrapped on the can front. Origin = bottom centre."""
    body = S.pbr("pr_%s" % color, hexc(color), 0.4, coat=0.3, var=0.02)
    band = S.pbr("pr_band", hexc("f7f4ec"), 0.45, var=0)
    lid = S.pbr("pr_lid", hexc("c9ced3"), 0.3, 0.9, var=0)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    lx, ly, lz = size
    if kind == "can":
        _cyl(bm, (0, 0, lz / 2), lx / 2, lz, "Z", 24, 0)
        _cyl(bm, (0, 0, lz - 0.004), lx / 2 - 0.002, 0.008, "Z", 24, 3)
        _cyl(bm, (0, 0, lz * 0.62), lx / 2 + 0.001, lz * 0.22, "Z", 24, 2)
        if label:
            _label_quad(bm, uvl, (0, -lx / 2 - 0.0015, lz * 0.3), lx * 0.55, lx * 0.28)
    else:
        _rbox(bm, (0, 0, lz / 2), (lx, ly, lz), r=min(0.006, lz * 0.2), seg=2, mi=0)
        S.bm_box(bm, (0, 0, lz * (0.72 if kind == "box" else 0.5)), (lx + 0.002, ly + 0.002, lz * 0.16), 2)
        if label:
            if kind == "gum":
                _label_quad(bm, uvl, (lx * 0.12, -ly / 2 - 0.0012, lz * 0.5), lx * 0.5, lz * 0.42)
            else:
                _label_quad(bm, uvl, (lx * 0.18, -ly / 2 - 0.0012, lz * 0.25), lx * 0.5, lx * 0.25)
    o = S.obj(name, S.mesh_from_bm(name, bm, [body, _upc_mat(), band, lid], smooth=(kind == "can")), parent=parent)
    return o


def _store(ctx, p, vintage=False):
    """Bright supermarket: vinyl tile floor, pale walls with a teal band, ceiling light panels, gondola shelves of
    colour-block products behind three checkout lanes. vintage=True: warmer light, wood-tone counters (1974 beat)."""
    sc = ctx.scene
    w = bpy.data.worlds.new("store_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.8, 0.78, 0.72, 1.0) if vintage else (0.74, 0.77, 0.8, 1.0)
    bg.inputs["Strength"].default_value = 0.45
    sc.view_settings.exposure = p.get("exposure", -0.45)
    L.fog(0.002, hexc("e8e4dc"), start=12.0)
    tile = S.pbr("st_floor" + ("_v" if vintage else ""), hexc("c4b391" if vintage else "c6c5bd"), 0.35, coat=0.2,
                 var=0.08, var_scale=1.2)
    S.plane_obj("st_floor", 30, 26, (0, 4, 0), tile)
    wall = S.pbr("st_wall", hexc("ebe6dc"), 0.8, var=0.02)
    bandm = S.pbr("st_band", hexc("b8743a" if vintage else "2f8f86"), 0.5, var=0.02)
    ceil = S.pbr("st_ceil", hexc("d9dadb"), 0.8, var=0)

    def room(bm):
        S.bm_box(bm, (0, 13.0, 2.6), (30, 0.3, 5.2), 0)
        S.bm_box(bm, (0, 12.84, 3.6), (30, 0.04, 0.6), 1)
        for sx in (-1, 1):
            S.bm_box(bm, (sx * 15, 4, 2.6), (0.3, 26, 5.2), 0)
            S.bm_box(bm, (sx * 14.84, 4, 3.6), (0.04, 26, 0.6), 1)
        S.bm_box(bm, (0, -9.0, 2.6), (30, 0.3, 5.2), 0)
        S.bm_box(bm, (0, -8.84, 3.6), (30, 0.04, 0.6), 1)
        S.bm_box(bm, (0, 4, 5.25), (30, 26, 0.1), 2)
    S.obj("st_room", _mesh("st_room", room, [wall, bandm, ceil]))
    daylt = S.emis("st_window", hexc("e3eef6"), 2.0)
    mull = S.pbr("st_mull", hexc("5b636b"), 0.4, 0.5, var=0)
    S.obj("st_win", _mesh("st_win", lambda bm: S.bm_box(bm, (0, -8.83, 1.75), (26, 0.02, 2.7)), [daylt]))
    S.obj("st_mull", _mesh("st_mull", lambda bm: [S.bm_box(bm, (x, -8.8, 1.75), (0.08, 0.06, 2.7)) for x in range(-13, 14, 2)] +
                           [S.bm_box(bm, (0, -8.8, z_), (26, 0.06, 0.08)) for z_ in (0.4, 3.1)], [mull]))
    pan = S.emis("st_panel", hexc("fff1d6" if vintage else "f6f8fb"), 3.0)

    def panels(bm):
        for x in range(-12, 13, 4):
            for y in range(-6, 13, 3):
                S.bm_box(bm, (x, y, 5.17), (2.4, 0.5, 0.05))
    S.obj("st_panels", _mesh("st_panels", panels, [pan]))
    col = (1.0, 0.9, 0.75) if vintage else (1.0, 0.98, 0.95)
    for k, (x, y) in enumerate(((-4, 0), (4, 0), (-4, 7), (4, 7), (0, -4))):
        A._area("st_a%d" % k, (x, y, 5.0), 5.0, 1500.0, col, size_y=4.0)
    # gondolas (shelves) behind the lanes, running along Y
    shelf = S.pbr("st_shelf", hexc("e3e5e7"), 0.4, 0.3, var=0)
    mats = [shelf] + [S.pbr("pr_%s" % c, hexc(c), 0.4, coat=0.3, var=0.02) for c in PROD_COLS]
    rng = random.Random(31)
    bm = bmesh.new()
    for gx in (-7.5, -4.5, -1.5, 1.5, 4.5, 7.5):
        y0, y1 = 4.5, 12.5
        S.bm_box(bm, (gx, (y0 + y1) / 2, 0.75), (0.12, y1 - y0, 1.5), 0)
        S.bm_box(bm, (gx, (y0 + y1) / 2, 0.08), (1.1, y1 - y0, 0.16), 0)
        for lvl in range(3):
            z = 0.18 + lvl * 0.42
            S.bm_box(bm, (gx, (y0 + y1) / 2, z), (1.1, y1 - y0, 0.025), 0)
            for side in (-1, 1):
                y = y0 + 0.1
                while y < y1 - 0.15:
                    ww = rng.uniform(0.12, 0.3)
                    hh = rng.uniform(0.16, 0.34)
                    ci = 1 + rng.randrange(len(PROD_COLS))
                    for d in range(2):
                        S.bm_box(bm, (gx + side * (0.15 + d * 0.22), y + ww / 2, z + 0.0125 + hh / 2), (0.2, ww - 0.015, hh), ci)
                    y += ww
    S.obj("st_gondolas", S.mesh_from_bm("st_gondolas", bm, mats))
    return rng


LANE_Z = 0.86


def _lane(ctx, x0, vintage=False, tower=True, speed=0.16):
    """Checkout lane at x offset x0: counter with a belt (customer side -Y, belt along +X to the scanner at x0),
    flush scanner window + vertical scanner tower, register with a screen (no text), bagging shelf, lane light."""
    if vintage:
        body = S.pbr("ln_body_v", hexc("8a5a34"), 0.5, var=0.06, var_scale=3.0)
        top = S.pbr("ln_top_v", hexc("d8c7a4"), 0.35, coat=0.3, var=0.03)
    else:
        body = S.pbr("ln_body", hexc("f1f2f3"), 0.35, coat=0.3, var=0.02)
        top = S.pbr("ln_top", hexc("3a4652"), 0.3, coat=0.3, var=0.02)
    dark = S.pbr("ln_dark", hexc("23272c"), 0.35, var=0)
    z = LANE_Z

    def counter(bm):
        S.bm_box(bm, (x0 - 1.6, 0, z / 2), (2.6, 0.75, z), 0)
        S.bm_box(bm, (x0 + 0.55, 0, z / 2), (1.7, 0.75, z), 0)
        S.bm_box(bm, (x0 + 0.55, 0, z + 0.015), (1.7, 0.8, 0.03), 1)
        S.bm_box(bm, (x0 + 1.1, 0.0, z + 0.1), (0.6, 0.6, 0.02), 1)                    # bagging shelf
        if tower:
            S.bm_box(bm, (x0 + 0.1, 0.33, z + 0.17), (0.38, 0.1, 0.34), 2)              # scanner tower
        S.bm_box(bm, (x0 + 0.55, 0.62, 0.55), (0.6, 0.45, 1.1), 0)                      # register stand
        S.bm_box(bm, (x0 + 0.55, 0.55, 1.36), (0.05, 0.05, 0.5), 2)
        S.bm_box(bm, (x0 + 0.55, 0.5, 1.62), (0.44, 0.04, 0.3), 2)                      # monitor back
        S.bm_box(bm, (x0 - 2.95, 0, 1.3), (0.06, 0.06, 2.6), 2)                          # lane light pole
        _cyl(bm, (x0 - 2.95, 0, 2.62), 0.16, 0.08, "Z", 20, 2)
    S.obj("lane%.0f" % x0, _mesh("lane%.0f" % x0, counter, [body, top, dark]))
    belt(ctx, "lbelt%.0f" % x0, (x0 - 2.85, 0), (x0 - 0.3, 0), z=z + 0.03, w=0.55, speed=speed, legs=False, guards=False)
    scr = S.emis("ln_screen", hexc("9ec9e8"), 1.3)
    S.obj("lscr%.0f" % x0, _mesh("lscr%.0f" % x0, lambda bm: S.bm_box(bm, (x0 + 0.55, 0.477, 1.62), (0.4, 0.005, 0.26)),
                                 [scr]))
    lamp = S.emis("ln_lamp", hexc("ffb000"), 3.0)
    S.obj("llamp%.0f" % x0, _mesh("llamp%.0f" % x0, lambda bm: _cyl(bm, (x0 - 2.95, 0, 2.62), 0.165, 0.03, "Z", 20),
                                  [lamp]))
    win = S.emis("ln_win", hexc("7a1a14"), 1.2)
    S.obj("lwin%.0f" % x0, _mesh("lwin%.0f" % x0, lambda bm: [S.bm_box(bm, (x0 + 0.1, 0.0, z + 0.03), (0.34, 0.3, 0.003))] +
                                 ([S.bm_box(bm, (x0 + 0.1, 0.277, z + 0.18), (0.3, 0.004, 0.22))] if tower else []),
                                 [win]))


def _lasers(ctx, origin, n=7, ln=0.45, spread=38.0, tilt=(0.0, 0.0), name="ls", f_on=1, f_off=None):
    """Fan of sweeping red laser lines from `origin` (thin unlit boxes, pivot at the emitter, pointing +Z by
    default, tilted by `tilt` (rx, ry) radians)."""
    las = S.emis("ed_laser2", hexc("ff1a12"), 7.0)
    rng = random.Random(7)
    me = _mesh(name + "_m", lambda bm: S.bm_box(bm, (0, 0, ln / 2), (0.0022, 0.0022, ln)), [las])
    out = []
    for i in range(n):
        o = S.obj("%s%d" % (name, i), me, origin)
        o.visible_shadow = False
        base = (tilt[0], tilt[1] + math.radians(-spread / 2 + spread * i / max(1, n - 1)), 0.0)
        ph, per = rng.uniform(0, 6.28), rng.randint(16, 26)
        for j in range(0, per + 1, 2):
            a = math.radians(12) * math.sin(ph + 2 * math.pi * j / per)
            kf(o, "rotation_euler", 1 + j, Vector((base[0] + a, base[1], base[2])))
        _interp(o, "LINEAR")
        _cyclic(o)
        if f_on > 1 or f_off:
            _show(o, f_on, f_off)
        out.append(o)
    return out


def _belt_items(ctx, x0, rng, items, v=0.25, f_start=1):
    """Products ride the belt (+X) towards the scanner and slide on over the window to the bagging shelf."""
    objs = []
    for k, (kind, size, color, xs) in enumerate(items):
        o = make_product("item%d_%.0f" % (k, x0), kind, size, color)
        path_move(ctx, o, [(x0 + xs, rng.uniform(-0.08, 0.08), LANE_Z + 0.03), (x0 + 1.2, 0.0, LANE_Z + 0.03)], f_start, v,
                  yaw_off=math.pi / 2 if kind != "can" else 0.0)
        objs.append(o)
    return objs


def _v_checkout(ctx, p, view):
    T = ctx.frames
    vintage = view == "first"
    rng = _store(ctx, p, vintage=vintage)
    if view == "first":
        _lane(ctx, 0.0, vintage=True, tower=False, speed=0.12)
    else:
        for x0 in (-4.2, 0.0, 4.2):
            _lane(ctx, x0)
    z = LANE_Z + 0.03          # item base (belt top = counter top)
    if view == "hook":
        items = [("box", (0.2, 0.07, 0.28), "d9462f", -1.5), ("can", (0.075, 0.075, 0.12), "2f8f86", -0.9),
                 ("gum", (0.08, 0.075, 0.026), "f0c419", -0.45), ("box", (0.15, 0.1, 0.22), "3a6fb0", -2.3)]
        _belt_items(ctx, 0.0, rng, items, v=0.16)
        _lasers(ctx, (0.1, 0.0, z), n=7, ln=0.32, name="ls")
        A.ring_pulses(ctx, (0.1, 0.0, z + 0.25), int(T * 0.35), color=AMBER, count=3, gap=int(T * 0.2), r1=0.4,
                      life=18, rot=(math.radians(90), 0, 0), name="beep")
        _cam_keys2(ctx, [(1, p.get("cam0", (1.65, 1.25, 1.75)), p.get("tgt0", (-0.45, -0.15, 0.95))),
                         (1.0, p.get("cam1", (1.4, 1.0, 1.62)), p.get("tgt1", (-0.4, -0.15, 0.95)))],
                   lens=p.get("lens", 28))
    elif view == "bars":
        o = make_product("hero_box", "box", (0.22, 0.08, 0.3), "d9462f")
        o.location = (-0.9, 0.0, z)
        o.rotation_euler = (0, 0, 0)
        o2 = make_product("side_can", "can", (0.075, 0.075, 0.12), "2f8f86")
        o2.location = (-0.62, 0.05, z)
        foc = _empty("code_foc", (-0.9 + 0.22 * 0.18, -0.041, z + 0.3 * 0.25))
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.86, -0.42, z + 0.16)), p.get("tgt0", foc.location[:])),
                         (1.0, p.get("cam1", (-0.87, -0.3, z + 0.12)), p.get("tgt1", foc.location[:]))],
                   lens=p.get("lens", 40))
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_object = foc
        ctx.cam.data.dof.aperture_fstop = 2.8
        S.anchor(ctx, "code", foc)
    elif view == "scan":
        o = make_product("scan_box", "box", (0.2, 0.07, 0.26), "3a6fb0")
        path_move(ctx, o, [(-0.45, 0.0, z), (0.7, 0.0, z)], 1, 0.9 / (T / ctx.fps), yaw_off=0.0)
        _lasers(ctx, (0.1, 0.0, z), n=9, ln=0.34, name="ls")
        _lasers(ctx, (0.1, 0.27, z + 0.2), n=7, ln=0.5, tilt=(math.radians(90), 0.0), spread=40, name="lt")
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.25, -0.95, 1.28)), p.get("tgt0", (0.08, 0.1, z + 0.12))),
                         (1.0, p.get("cam1", (-0.18, -0.82, 1.22)), p.get("tgt1", (0.08, 0.1, z + 0.12)))],
                   lens=p.get("lens", 32))
        S.anchor(ctx, "scanner", _empty("scan_anc", (0.1, 0.25, z + 0.34)))
    elif view == "lookup":
        fs = ctx.word_time(p.get("send_cue", "looks"), 0.55)
        fb = ctx.word_time(p.get("back_cue", "sends"), 0.8)
        o = make_product("lk_box", "box", (0.2, 0.07, 0.26), "e07a1f")
        o.location = (0.1, 0.0, z)
        # back-office computer: desk + tower + monitor by the wall
        desk = S.pbr("of_desk", hexc("c9b08a"), 0.5, var=0.04)
        pc = S.pbr("of_pc", hexc("2a2e34"), 0.35, var=0)
        cx, cy = 0.0, 0.0           # office built locally, placed at OC and turned to face the lane
        OC, OR = Vector((1.95, 1.95, 0.0)), Matrix.Rotation(math.radians(-45), 3, "Z")
        oroot = _empty("office_root", tuple(OC))
        oroot.rotation_euler = (0, 0, math.radians(-45))
        partm = S.pbr("of_part", hexc("dfe3e6"), 0.8, var=0.02)

        def office(bm):
            S.bm_box(bm, (cx, cy, 0.74), (1.4, 0.7, 0.04), 0)
            for sx in (-1, 1):
                S.bm_box(bm, (cx + sx * 0.66, cy, 0.37), (0.04, 0.66, 0.74), 0)
            S.bm_box(bm, (cx + 0.45, cy, 0.98), (0.22, 0.5, 0.44), 1)
            S.bm_box(bm, (cx - 0.15, cy + 0.15, 1.05), (0.6, 0.04, 0.38), 1)
            S.bm_box(bm, (cx - 0.15, cy + 0.2, 0.84), (0.05, 0.05, 0.2), 1)
            S.bm_box(bm, (cx, cy + 0.75, 1.3), (3.6, 0.1, 2.6), 2)                    # office partition
            S.bm_box(bm, (cx, cy + 0.69, 2.2), (3.6, 0.02, 0.3), 3)
        S.obj("office", _mesh("office", office, [desk, pc, partm, S.pbr("st_band", hexc("2f8f86"), 0.5, var=0.02)]),
              parent=oroot)
        scr_m = _glow_keys("of_scr", hexc("3ad6c2"), [(1, 0.6), (fs + 26, 0.6), (fs + 32, 2.4)])
        S.obj("of_scr", _mesh("of_scr", lambda bm: S.bm_box(bm, (cx - 0.15, cy + 0.125, 1.05), (0.54, 0.005, 0.32)),
                              [scr_m]), parent=oroot)
        led = _glow_keys("of_led", hexc("ffb000"), [(1, 0.0), (fs + 26, 0.0), (fs + 30, 4.0)])
        S.obj("of_led", _mesh("of_led", lambda bm: [S.bm_box(bm, (cx + 0.45, cy - 0.252, 0.9 + 0.05 * k), (0.12, 0.004, 0.012))
                                                     for k in range(4)], [led]), parent=oroot)
        pa_, pb_ = Vector((0.1, 0.0, z + 0.06)), OC + OR @ Vector((0.45, -0.27, 1.25))
        path = [tuple(pa_.lerp(pb_, u) + Vector((0, 0, 1.3 * math.sin(math.pi * u)))) for u in [i / 12.0 for i in range(13)]]
        cab = _glow_keys("cable", hexc("3ad6c2"), [(1, 1.0)])
        bm = bmesh.new()
        for a_, b_ in zip(path[:-1], path[1:]):
            a_, b_ = Vector(a_), Vector(b_)
            d = b_ - a_
            o_ = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.008, radius2=0.008, depth=d.length * 0.6)
            rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix()
            bmesh.ops.rotate(bm, verts=o_["verts"], cent=(0, 0, 0), matrix=rot)
            bmesh.ops.translate(bm, vec=(a_ + b_) / 2, verts=o_["verts"])
        S.obj("cable", S.mesh_from_bm("cable", bm, [cab]))
        plen = sum((Vector(b_) - Vector(a_)).length for a_, b_ in zip(path[:-1], path[1:]))
        f_arr = int(fb + plen / 3.6 * ctx.fps)
        reg = _glow_keys("reg_glow", hexc("ffb000"), [(1, 0.0), (f_arr, 0.0), (f_arr + 5, 1.8)])
        S.obj("reg_glow", _mesh("reg_glow", lambda bm: S.bm_box(bm, (0.55, 0.474, 1.62), (0.4, 0.004, 0.26)), [reg]))
        am = S.emis("pulse_a", hexc("ffb000"), 8.0)
        tm = S.emis("pulse_t", hexc("3ad6c2"), 8.0)
        for k in range(8):
            for (m_, pts, f0, nm) in ((am, path, fs + 5 * k, "pa"), (tm, list(reversed(path)), fb + 5 * k, "pt")):
                bm = bmesh.new()
                bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.035)
                o_ = S.obj("%s%d" % (nm, k), S.mesh_from_bm("%s%d" % (nm, k), bm, [m_], smooth=True))
                o_.visible_shadow = False
                fr = path_move(ctx, o_, pts, f0, 3.6, every=1)
                _show(o_, max(2, int(f0)), int(fr[-1]) + 2)
        _lasers(ctx, (0.1, 0.0, z), n=7, ln=0.32, name="ls")
        _cam_keys2(ctx, [(1, p.get("cam0", (-1.15, -1.45, 1.95)), p.get("tgt0", (1.15, 1.1, 1.05))),
                         (1.0, p.get("cam1", (-1.0, -1.3, 1.9)), p.get("tgt1", (1.15, 1.1, 1.05)))],
                   lens=p.get("lens", 24))
        S.anchor(ctx, "computer", _empty("pc_anc", tuple(OC + OR @ Vector((0.1, 0.0, 1.35)))))
    elif view == "first":
        fsc = ctx.word_time(p.get("scan_cue", "item"), 0.75)
        gum = make_product("gum", "gum", (0.08, 0.075, 0.026), "f0c419")
        v = 0.12
        x_win = 0.1
        x_start = x_win - v * (fsc - 1) / ctx.fps
        path_move(ctx, gum, [(x_start, 0.0, z), (1.2, 0.0, z)], 1, v, yaw_off=math.pi / 2)
        _lasers(ctx, (0.1, 0.0, z), n=7, ln=0.3, name="ls")
        A.ring_pulses(ctx, (0.1, 0.0, z + 0.2), fsc, color=AMBER, count=3, gap=8, r1=0.35, life=20,
                      rot=(math.radians(90), 0, 0), name="beep")
        spot = bpy.data.lights.new("spot", "SPOT")
        spot.energy = 50.0
        spot.spot_size = math.radians(40)
        spot.color = (1.0, 0.85, 0.6)
        so = L.link(bpy.data.objects.new("spot", spot))
        so.location = (0.1, -0.6, 2.4)
        so.rotation_euler = (math.radians(15), 0, 0)
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.5, -0.72, 1.16)), p.get("tgt0", (0.14, 0.02, z + 0.02))),
                         (1.0, p.get("cam1", (-0.42, -0.62, 1.12)), p.get("tgt1", (0.15, 0.02, z + 0.02)))],
                   lens=p.get("lens", 34))
        S.anchor(ctx, "gum", _empty("gum_anc", (0.1, 0.0, z + 0.06)))
    elif view == "today":
        _cam_keys2(ctx, [(1, p.get("cam0", (-3.0, 3.4, 1.25)), p.get("tgt0", (-3.0, 11.0, 0.75))),
                         (1.0, p.get("cam1", (-3.0, 5.6, 1.2)), p.get("tgt1", (-3.0, 12.0, 0.75)))],
                   lens=p.get("lens", 26))
    else:   # outro
        items = [("box", (0.2, 0.07, 0.28), "5aa05a", -1.2), ("can", (0.075, 0.075, 0.12), "d9462f", -0.6)]
        _belt_items(ctx, 0.0, rng, items, v=0.16)
        _lasers(ctx, (0.1, 0.0, z), n=7, ln=0.32, name="ls")
        _cam_keys2(ctx, [(1, p.get("cam0", (1.3, 2.1, 1.8)), p.get("tgt0", (-0.6, -0.4, 0.95))),
                         (1.0, p.get("cam1", (2.6, 4.0, 3.0)), p.get("tgt1", (-0.8, -1.4, 0.9)))],
                   lens=p.get("lens", 28))


def b_checkout_v2(ctx, p):
    """Supermarket checkout (gum barcode). view hook | bars | scan | lookup | first | today | outro.
    Anchors: code (bars), scanner (scan), computer (lookup), gum (first). Params: send_cue, back_cue, scan_cue,
    cam0/1, tgt0/1, lens, exposure."""
    _v_checkout(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- elevator counterweight (tower city)
LF_N, LF_FH = 7, 3.3                 # floors, floor height
LF_W, LF_D = 14.0, 9.0               # building footprint (x, y); front face at local y = -LF_D / 2
LF_SHX = (-1.7, 1.7)                 # shaft bay x range (front wall cut away here)
LF_SHY = (-LF_D / 2, -1.6)           # shaft depth (open front)
LF_RY = -2.9                         # rope / sheave plane (local y)
LF_CAR_X, LF_CW_X = -0.55, 1.0       # rope lines: car centre, counterweight centre
LF_SHEAVE_Z = LF_N * LF_FH + 1.15    # sheave axle height (machine room floor at LF_N * LF_FH)
LF_ROPE = 2 * LF_SHEAVE_Z - 3.05 - 2.75 - 0.15 - (LF_N - 1) * LF_FH - 0.25   # rope constant (car at floor 0 <-> cwt high)


def _lf_cw_z(car_z):
    """Counterweight bottom for a car floor height car_z (1:1 roping over the sheave: what one side drops the other
    side rises). Car hitch = car_z + 2.9, counterweight hitch = cw_z + 2.75."""
    return 2 * LF_SHEAVE_Z - LF_ROPE - (car_z + 2.9) - 2.75


def _lift_building(ctx, root, p, glow_frame=None, riders=True):
    """Mid-rise cream office block with the lift shaft bay cut open at the front: guide rails, landing doors, car
    (open-front cab, warm light, riders), counterweight frame with plates, ropes over a yellow sheave in a cut-open
    machine room on the roof. Returns dict of the moving parts."""
    W, D, H = LF_W, LF_D, LF_N * LF_FH
    x0, x1 = LF_SHX
    wall = S.facade_mat("lf_facade", hexc("efe6d6"), hexc("3d5570"), 3.0, LF_FH, 0.55)
    band = S.pbr("lf_band", hexc("c46a43"), 0.7, var=0.05)
    slab = S.pbr("lf_slab", hexc("a9aeb3"), 0.8, var=0.04)
    inner = S.pbr("lf_inner", hexc("e9e5dd"), 0.85, var=0.03)
    cut = S.pbr("lf_cut", hexc("8fd3c8"), 0.6, var=0)
    bm = bmesh.new()
    S.bm_box(bm, (0, D / 2 - 0.2, H / 2), (W, 0.4, H), 0)                       # back
    for sx in (-1, 1):
        S.bm_box(bm, (sx * (W / 2 - 0.2), 0, H / 2), (0.4, D, H), 0)             # sides
    for (a, b) in ((-W / 2, x0 - 0.3), (x1 + 0.3, W / 2)):                       # front, both sides of the shaft bay
        S.bm_box(bm, ((a + b) / 2, -D / 2 + 0.2, H / 2), (b - a, 0.4, H), 0)
    xa, xb = x0 - 0.3, x1 + 0.3
    for k in range(LF_N + 1):
        z = k * LF_FH
        if k == LF_N:
            S.bm_box(bm, (0, 0, z + 0.15), (W, D, 0.3), 2)                          # roof (over the shaft too)
        else:                                                                         # slab with the shaft hole
            S.bm_box(bm, ((-W / 2 + xa) / 2, 0, z + 0.15), (xa + W / 2, D, 0.3), 2)
            S.bm_box(bm, ((xb + W / 2) / 2, 0, z + 0.15), (W / 2 - xb, D, 0.3), 2)
            S.bm_box(bm, (0, (LF_SHY[1] + D / 2) / 2, z + 0.15), (xb - xa, D / 2 - LF_SHY[1], 0.3), 2)
        for (a, b) in ((-W / 2 - 0.05, xa), (xb, W / 2 + 0.05)):
            S.bm_box(bm, ((a + b) / 2, -D / 2 - 0.02, z + 0.15), (b - a, 0.1, 0.45), 1)
    S.bm_box(bm, (0, -D / 2 - 0.05, H + 0.5), (W + 0.2, 0.2, 0.3), 1)              # parapet (front)
    S.bm_box(bm, (0, D / 2 + 0.05, H + 0.5), (W + 0.2, 0.2, 0.3), 1)
    S.obj("lf_shell", S.mesh_from_bm("lf_shell", bm, [wall, band, slab]), parent=root)
    # shaft: back + side walls (light), cut edge trim (pale teal), landing doors, rails
    bm = bmesh.new()
    S.bm_box(bm, ((x0 + x1) / 2, LF_SHY[1] + 0.1, (H + 3.4) / 2), (x1 - x0 + 0.6, 0.2, H + 3.4), 0)
    for x in (x0 - 0.15, x1 + 0.15):
        S.bm_box(bm, (x, (LF_SHY[0] + LF_SHY[1]) / 2, (H + 3.4) / 2), (0.3, LF_SHY[1] - LF_SHY[0], H + 3.4), 0)
    for x in (x0 - 0.3, x1 + 0.3):
        S.bm_box(bm, (x, -D / 2 - 0.03, (H + 3.4) / 2), (0.08, 0.1, H + 3.4), 1)
    S.obj("lf_shaft", S.mesh_from_bm("lf_shaft", bm, [inner, cut]), parent=root)
    steel = S.pbr("lf_steel", hexc("aeb5bc"), 0.3, 0.8, var=0)
    rail = S.pbr("lf_rail", hexc("5f666d"), 0.35, 0.8, var=0)
    bm = bmesh.new()
    for k in range(LF_N):
        z = k * LF_FH + 0.3
        S.bm_box(bm, (LF_CAR_X, LF_SHY[1] - 0.02, z + 1.05), (1.1, 0.06, 2.1), 0)       # landing doors
        S.bm_box(bm, (LF_CAR_X, LF_SHY[1] - 0.06, z + 1.05), (0.012, 0.02, 2.1), 1)
    for x in (LF_CAR_X - 1.0, LF_CAR_X + 1.0, LF_CW_X - 0.42 + 0.12, LF_CW_X + 0.42 - 0.12):
        S.bm_box(bm, (x if abs(x - LF_CW_X) > 0.5 else x, LF_RY, (H + 1.0) / 2), (0.09, 0.12, H + 1.0), 1)
    S.obj("lf_rails", S.mesh_from_bm("lf_rails", bm, [steel, rail]), parent=root)
    # shaft lights (strips) + front fill
    lm = S.emis("lf_strip", hexc("fff4e2"), 1.6)
    S.obj("lf_strips", _mesh("lf_strips", lambda bm: [S.bm_box(bm, (x, LF_SHY[1] - 0.05, H / 2), (0.06, 0.03, H))
                                                       for x in (x0 + 0.08, x1 - 0.08)], [lm]), parent=root)
    # machine room on the roof (front cut open)
    mr = S.pbr("lf_mroom", hexc("e3ddd2"), 0.85, var=0.02)
    bm = bmesh.new()
    S.bm_box(bm, (0.3, -2.6, H + 3.4), (5.4, 4.0, 0.25), 0)
    S.bm_box(bm, (0.3, -0.7, H + 1.7), (5.4, 0.25, 3.4), 0)
    for x in (-2.4, 3.0):
        S.bm_box(bm, (x, -2.6, H + 1.7), (0.25, 4.0, 3.4), 0)
    S.obj("lf_mroom", S.mesh_from_bm("lf_mroom", bm, [mr]), parent=root)
    _point("lf_mr_light", (root.location.x + 0.3, root.location.y - 2.0, H + 3.0), 120.0, (1.0, 0.95, 0.85), 0.4)
    yel = S.pbr("lf_yellow", hexc("f2c230"), 0.4, 0.2, coat=0.3, var=0.02)
    blue = S.pbr("lf_motor", hexc("2d5b8c"), 0.35, 0.3, coat=0.3, var=0.02)
    dark = S.pbr("lf_dark", hexc("33383e"), 0.5, 0.4, var=0)
    r_sh = (LF_CW_X - LF_CAR_X) / 2
    shx = (LF_CW_X + LF_CAR_X) / 2

    def machine(bm):
        S.bm_box(bm, (shx + 0.4, LF_RY + 0.5, H + 0.45), (2.6, 1.8, 0.3), 2)         # bedplate
        _cyl(bm, (shx, LF_RY + 0.75, H + 1.15), 0.12, 1.4, "Y", 16, 2)                 # axle
        _cyl(bm, (shx, LF_RY + 1.05, H + 1.15), 0.42, 0.7, "Y", 28, 1)                 # motor
        _cyl(bm, (shx, LF_RY + 1.5, H + 1.15), 0.3, 0.2, "Y", 24, 2)                   # brake drum
        S.bm_box(bm, (shx + 1.5, LF_RY + 1.1, H + 1.0), (0.7, 0.5, 1.1), 0)            # controller cabinet
        S.bm_box(bm, (shx, LF_RY + 1.05, H + 0.75), (0.7, 0.5, 0.3), 2)
    S.obj("lf_machine", _mesh("lf_machine", machine, [S.pbr("lf_cab", hexc("c9ced3"), 0.4, 0.3, var=0), blue, dark]),
          parent=root)
    led = S.emis("lf_led", hexc("3ad6c2"), 4.0)
    S.obj("lf_leds", _mesh("lf_leds", lambda bm: [S.bm_box(bm, (shx + 1.3 + 0.12 * k, LF_RY + 0.84, H + 1.3), (0.06, 0.01, 0.06))
                                                   for k in range(4)], [led]), parent=root)
    sheave = _empty("lf_sheave", (shx, LF_RY, LF_SHEAVE_Z), parent=root)

    def sh(bm):
        _cyl(bm, (0, 0, 0), r_sh, 0.26, "Y", 40, 0)
        for k in range(4):
            _cyl(bm, (0, -0.09 + 0.06 * k, 0), r_sh + 0.012, 0.02, "Y", 40, 1)
        for k in range(6):
            a = k * math.pi / 3
            S.bm_box(bm, (math.cos(a) * r_sh * 0.55, -0.15, math.sin(a) * r_sh * 0.55), (0.12, 0.04, 0.12), 1)
        _cyl(bm, (0, -0.14, 0), 0.16, 0.04, "Y", 20, 1)
    S.obj("lf_sheave_m", _mesh("lf_sheave_m", sh, [yel, dark]), parent=sheave)
    # rope arc over the sheave (static)
    ropem = S.pbr("lf_rope", hexc("8d949b"), 0.35, 0.9, var=0)
    bm = bmesh.new()
    for k in range(4):
        yy = -0.09 + 0.06 * k
        for i in range(24):
            a0, a1 = math.pi * i / 24, math.pi * (i + 1) / 24
            pa = Vector((-math.cos(a0) * r_sh, yy, math.sin(a0) * r_sh))
            pb = Vector((-math.cos(a1) * r_sh, yy, math.sin(a1) * r_sh))
            d = pb - pa
            r = bmesh.ops.create_cone(bm, cap_ends=False, segments=6, radius1=0.016, radius2=0.016, depth=d.length)
            bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0),
                             matrix=Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix())
            bmesh.ops.translate(bm, vec=(pa + pb) / 2 + Vector((shx, LF_RY, LF_SHEAVE_Z)), verts=r["verts"])
    S.obj("lf_rope_arc", S.mesh_from_bm("lf_rope_arc", bm, [ropem]), parent=root)
    # unit-length hanging ropes (origin at the top, hanging -Z, scaled per frame)
    bm = bmesh.new()
    for k in range(4):
        _cyl(bm, (0, -0.09 + 0.06 * k, -0.5), 0.016, 1.0, "Z", 6, 0)
    rope_me = S.mesh_from_bm("lf_rope", bm, [ropem])
    rope_car = S.obj("lf_rope_car", rope_me, (LF_CAR_X, LF_RY, LF_SHEAVE_Z), parent=root)
    rope_cw = S.obj("lf_rope_cw", rope_me, (LF_CW_X, LF_RY, LF_SHEAVE_Z), parent=root)
    # car: open-front cab + sling, warm ceiling light, riders
    car = _empty("lf_car", (LF_CAR_X, 0, 0), parent=root)
    cabm = S.pbr("lf_cabin", hexc("d8d2c6"), 0.4, 0.2, coat=0.2, var=0.02)
    floorm = S.pbr("lf_cabfloor", hexc("6b5a4a"), 0.6, var=0.05)

    def cab(bm):
        y0, y1 = LF_SHY[0] + 0.45, LF_SHY[1] - 0.15
        cy = (y0 + y1) / 2
        S.bm_box(bm, (0, cy, 0.06), (1.9, y1 - y0, 0.12), 1)
        S.bm_box(bm, (0, cy, 2.5), (1.9, y1 - y0, 0.1), 0)
        S.bm_box(bm, (0, y1, 1.28), (1.9, 0.06, 2.35), 0)
        for sx in (-1, 1):
            S.bm_box(bm, (sx * 0.92, cy, 1.28), (0.06, y1 - y0, 2.35), 0)
            S.bm_box(bm, (sx * 0.98, LF_RY, 1.45), (0.1, 0.16, 2.9), 2)            # sling stiles
        S.bm_box(bm, (0, LF_RY, 2.88), (2.06, 0.18, 0.16), 2)                       # crosshead
        S.bm_box(bm, (0, LF_RY, -0.05), (2.06, 0.18, 0.12), 2)                      # plank
        S.bm_box(bm, (0, cy, 1.0), (1.84, 0.02, 0.03), 2)                           # handrail (back)
    S.obj("lf_cab", _mesh("lf_cab", cab, [cabm, floorm, dark]), parent=car)
    cl = S.emis("lf_cabl", hexc("fff1d8"), 3.0)
    S.obj("lf_cabl", _mesh("lf_cabl", lambda bm: S.bm_box(bm, (0, -2.95, 2.44), (1.2, 0.8, 0.02)), [cl]), parent=car)
    li = A._area("lf_cab_a", (0, 0, 0), 1.0, 60.0, (1.0, 0.92, 0.8), size_y=0.8)
    li.parent = car
    li.location = (0, -2.95, 2.4)
    rider_m = [S.pbr("lf_rider%d" % i, hexc(c), 0.6, var=0.03) for i, c in enumerate(("2f5f8f", "b8503a", "4f7a4a"))]
    skin = S.pbr("lf_head", hexc("c99a76"), 0.6, var=0.02)
    for i, (rx, ry) in enumerate(((-0.45, -2.7), (0.1, -2.4), (0.55, -2.85)) if riders else ()):
        bm = bmesh.new()
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.2, radius2=0.17, depth=1.2)
        bmesh.ops.translate(bm, vec=(0, 0, 0.72), verts=r["verts"])
        h = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=0.13)
        bmesh.ops.translate(bm, vec=(0, 0, 1.5), verts=h["verts"])
        for f in {f for v in h["verts"] for f in v.link_faces}:
            f.material_index = 1
        S.obj("lf_rider%d" % i, S.mesh_from_bm("lf_rider%d" % i, bm, [rider_m[i], skin], smooth=True), (rx, ry, 0.12),
              parent=car)
    # counterweight: frame + plates (top plates = the "part of the load" share, can glow amber)
    cw = _empty("lf_cw", (LF_CW_X, LF_RY, 0), parent=root)
    plate = S.pbr("lf_plate", hexc("454b52"), 0.5, 0.6, var=0.03)

    def cwf(bm):
        for sx in (-1, 1):
            S.bm_box(bm, (sx * 0.27, 0, 1.375), (0.08, 0.26, 2.75), 0)
        S.bm_box(bm, (0, 0, 2.7), (0.62, 0.26, 0.1), 0)
        S.bm_box(bm, (0, 0, 0.05), (0.62, 0.26, 0.1), 0)
        for k in range(13):
            S.bm_box(bm, (0, 0, 0.16 + 0.14 * k), (0.46, 0.2, 0.12), 1)
    S.obj("lf_cwf", _mesh("lf_cwf", cwf, [dark, plate]), parent=cw)
    m_load = S._new_mat("lf_loadplate")
    mat, nt, N, Lk, pr = m_load
    pr.inputs["Base Color"].default_value = hexc("8a6a2a")
    pr.inputs["Roughness"].default_value = 0.5
    pr.inputs["Emission Color"].default_value = AMBER
    pr.inputs["Emission Strength"].default_value = 0.0
    S._finish(mat, pr.outputs[0])
    if glow_frame:
        L.kf_socket(pr.inputs["Emission Strength"], 1, 0.0)
        L.kf_socket(pr.inputs["Emission Strength"], max(2, glow_frame), 0.0)
        L.kf_socket(pr.inputs["Emission Strength"], glow_frame + 12, 2.2)
    S.obj("lf_cw_load", _mesh("lf_cw_load", lambda bm: [S.bm_box(bm, (0, 0, 0.16 + 0.14 * k), (0.47, 0.21, 0.12))
                                                          for k in range(13, 18)], [mat]), parent=cw)
    return {"car": car, "cw": cw, "sheave": sheave, "rope_car": rope_car, "rope_cw": rope_cw, "r_sh": r_sh, "H": H}


def _lift_motion(ctx, parts, keys, every=2):
    """keys = [(frame, car_z)] (BEZIER-like smoothstep between keys). Moves car, counterweight, ropes, sheave."""
    T = ctx.frames
    def car_z(f):
        if f <= keys[0][0]:
            return keys[0][1]
        for (fa, za), (fb, zb) in zip(keys[:-1], keys[1:]):
            if f <= fb:
                u = (f - fa) / float(max(1, fb - fa))
                u = u * u * (3 - 2 * u) if parts.get("smooth", True) else u
                return za + (zb - za) * u
        return keys[-1][1]
    z_ref = car_z(1)
    for f in list(range(1, T + 2, every)) + [T + 1]:
        zc = car_z(f)
        zw = _lf_cw_z(zc)
        kf(parts["car"], "location", f, Vector((LF_CAR_X, 0, zc)))
        kf(parts["cw"], "location", f, Vector((LF_CW_X, LF_RY, zw)))
        kf(parts["rope_car"], "scale", f, Vector((1, 1, max(0.05, LF_SHEAVE_Z - (zc + 2.9)))))
        kf(parts["rope_cw"], "scale", f, Vector((1, 1, max(0.05, LF_SHEAVE_Z - (zw + 2.75)))))
        kf(parts["sheave"], "rotation_euler", f, Vector((0, (zc - z_ref) / parts["r_sh"], 0)))
    for o in (parts["car"], parts["cw"], parts["rope_car"], parts["rope_cw"], parts["sheave"]):
        _interp(o, "LINEAR")
    return car_z


def _lift_world(ctx, p, glow_frame=None, riders=True):
    import scene_lib_v2_tower as TW
    TW.build_city(ctx, p, golden=p.get("golden", False))
    TW.build_hero(ctx)
    # remove the city traffic lane that runs through the explainer plot (y ~ 56 / 64)
    drop = [o.name for o in bpy.data.objects
            if o.name.startswith("tc") and o.parent is None and abs(o.location.y - TW.EXP[1]) < 10]
    for nm in drop:
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        kids = [c.name for c in o.children_recursive]
        bpy.data.objects.remove(o, do_unlink=True)
        for c in kids:
            if bpy.data.objects.get(c) is not None:
                bpy.data.objects.remove(bpy.data.objects[c], do_unlink=True)
    root = _empty("lf_root", (TW.EXP[0], TW.EXP[1], 0.0))
    parts = _lift_building(ctx, root, p, glow_frame, riders)
    # plaza paving in front + fill light into the cut-open shaft
    S.plane_obj("lf_plaza", 60, 40, (TW.EXP[0], TW.EXP[1] - 20, 0.04), S.pbr("lf_paving", hexc("cfc8ba"), 0.8, var=0.06))
    fl = A._area("lf_fill", (TW.EXP[0], TW.EXP[1] - 30.0, 14.0), 12.0, p.get("fill", 9000.0), (1.0, 0.97, 0.92))
    fl.rotation_euler = (math.radians(80), 0, 0)
    fl.data.size_y = 26.0
    return root, parts


def _lw(root, x, y, z):
    return (root.location.x + x, root.location.y + y, z)


def _v_lift(ctx, p, view):
    T = ctx.frames
    FH = LF_FH
    glow = ctx.word_time(p.get("load_cue", "plus"), 0.5) if view == "balance" else None
    root, parts = _lift_world(ctx, p, glow, riders=(view != "balance"))
    yf = -LF_D / 2
    if view in ("hook", "outro"):
        _lift_motion(ctx, parts, [(1, 0.3), (T, 0.3 + 4 * FH)])
        if view == "hook":
            _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, -9.0, -52.0, 4.0)), p.get("tgt0", _lw(root, 0.0, 0.0, 17.5))),
                             (1.0, p.get("cam1", _lw(root, -6.5, -44.0, 4.5)), p.get("tgt1", _lw(root, 0.0, 0.0, 17.0)))],
                       lens=p.get("lens", 30), clip=0.3, far=40000.0)
        else:
            _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, -8.0, -40.0, 6.0)), p.get("tgt0", _lw(root, 0.0, 0.0, 13.0))),
                             (1.0, p.get("cam1", _lw(root, -40.0, -120.0, 45.0)), p.get("tgt1", _lw(root, 0.0, 0.0, 16.0)))],
                       lens=p.get("lens", 30), clip=0.3, far=40000.0)
        S.anchor(ctx, "car", parts["car"], (0, -2.9, 1.4))
    elif view == "rig":
        _lift_motion(ctx, parts, [(1, 0.3), (T, 1.3)])
        H = parts["H"]
        _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, 2.4, yf - 9.0, H + 0.4)), p.get("tgt0", _lw(root, 0.3, -2.9, H - 0.1))),
                         (1.0, p.get("cam1", _lw(root, 2.0, yf - 7.8, H + 0.5)), p.get("tgt1", _lw(root, 0.3, -2.9, H)))],
                   lens=p.get("lens", 26), clip=0.1)
        S.anchor(ctx, "sheave", parts["sheave"], (0, -0.2, parts["r_sh"]))
        S.anchor(ctx, "cwt", parts["cw"], (0, 0, 2.0))
        S.anchor(ctx, "car", parts["car"], (0, -2.9, 2.9))
    elif view == "balance":
        zc = 3 * FH + 0.3
        _lift_motion(ctx, parts, [(1, zc), (T, zc + 0.15)])
        zm = zc + 1.4
        _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, 0.6, yf - 6.0, zm + 0.6)), p.get("tgt0", _lw(root, 0.15, -2.9, zm - 0.1))),
                         (1.0, p.get("cam1", _lw(root, 0.5, yf - 5.3, zm + 0.5)), p.get("tgt1", _lw(root, 0.15, -2.9, zm - 0.1)))],
                   lens=p.get("lens", 28), clip=0.1)
        S.anchor(ctx, "car", parts["car"], (0, -2.9, 1.9))
        S.anchor(ctx, "cwt", parts["cw"], (0, 0, 2.5))
    elif view == "motor":
        _lift_motion(ctx, parts, [(1, 2 * FH + 0.3), (T, 3 * FH + 0.3)])
        H = parts["H"]
        shx = (LF_CW_X + LF_CAR_X) / 2
        _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, shx + 2.0, yf - 2.8, H + 2.1)), p.get("tgt0", _lw(root, shx - 0.1, -2.3, H + 1.0))),
                         (1.0, p.get("cam1", _lw(root, shx + 1.7, yf - 2.4, H + 2.0)), p.get("tgt1", _lw(root, shx - 0.1, -2.3, H + 1.0)))],
                   lens=p.get("lens", 26), clip=0.05)
        S.anchor(ctx, "motor", parts["sheave"], (0, -0.16, 0))
    elif view == "pass":
        zmid = 3 * FH + 0.3
        z0 = _lf_cw_z(zmid)
        # car goes up so that it passes the counterweight (same mid height) at ~55 % of the beat
        zcross = (2 * LF_SHEAVE_Z - LF_ROPE - 2.9 - 2.75) / 2.0
        _lift_motion(ctx, parts, [(1, zcross - 3.2), (T, zcross + 2.6)])
        _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, 2.5, yf - 10.0, zcross + 2.0)), p.get("tgt0", _lw(root, 0.2, -2.9, zcross + 1.4))),
                         (1.0, p.get("cam1", _lw(root, 2.2, yf - 9.0, zcross + 2.2)), p.get("tgt1", _lw(root, 0.2, -2.9, zcross + 1.5)))],
                   lens=p.get("lens", 28), clip=0.1)
        S.anchor(ctx, "car", parts["car"], (0, -2.9, 2.0))
        S.anchor(ctx, "cwt", parts["cw"], (0, 0, 1.5))
    elif view == "safety":
        fcl = ctx.word_time(p.get("clamp_cue", "clamp"), 0.6)
        zs = 2 * FH + 1.6
        z_start = zs + 1.0
        parts["smooth"] = False
        _lift_motion(ctx, parts, [(1, z_start), (fcl, zs + 0.35), (fcl + 8, zs)], every=1)
        # safety wedges on both rails at the car's plank, clamp in on the cue + red-amber glow
        wm = _glow_keys("lf_wedge_glow", hexc("ff5a2a"), [(1, 0.0), (fcl, 0.0), (fcl + 3, 4.0), (fcl + 30, 2.5)])
        dark = S.pbr("lf_wedge", hexc("2b2f35"), 0.4, 0.6, var=0)
        for sx in (-1, 1):
            for side in (-1, 1):
                w = S.obj("wedge%d%d" % (sx, side), _mesh("wedge%d%d" % (sx, side),
                          lambda bm: S.bm_box(bm, (0, 0, 0), (0.12, 0.14, 0.3)), [dark]), parent=parts["car"])
                x_r = sx * 1.0
                kf(w, "location", 1, Vector((x_r + side * 0.16, LF_RY, -0.3)))
                kf(w, "location", fcl, Vector((x_r + side * 0.16, LF_RY, -0.3)))
                kf(w, "location", fcl + 3, Vector((x_r + side * 0.11, LF_RY, -0.3)))
                _interp(w, "LINEAR")
                g = S.obj("wglow%d%d" % (sx, side), _mesh("wglow%d%d" % (sx, side),
                          lambda bm: S.bm_box(bm, (0, -0.072, 0), (0.1, 0.004, 0.27)), [wm]), parent=w)
                g.visible_shadow = False
        A.ring_pulses(ctx, _lw(root, LF_CAR_X - 1.0, LF_RY - 0.1, zs), fcl, color=AMBER, count=3, gap=7, r1=0.7,
                      life=20, rot=(math.radians(90), 0, 0), name="clamp")
        zc = zs
        _cam_keys2(ctx, [(1, p.get("cam0", _lw(root, LF_CAR_X - 0.2, yf - 1.2, zc - 0.55)), p.get("tgt0", _lw(root, LF_CAR_X - 1.0, LF_RY, zc - 0.3))),
                         (1.0, p.get("cam1", _lw(root, LF_CAR_X - 0.25, yf - 1.0, zc - 0.5)), p.get("tgt1", _lw(root, LF_CAR_X - 1.0, LF_RY, zc - 0.3)))],
                   lens=p.get("lens", 28), clip=0.05)
        S.anchor(ctx, "brake", parts["car"], (-1.0, LF_RY, -0.15))


def b_lift_v2(ctx, p):
    """Elevator counterweight explainer in the scene_lib_v2_tower city: a cream mid-rise on the explainer plot with
    its lift shaft cut open at the front. view hook | rig | balance | motor | pass | safety | outro.
    Anchors: car (hook/rig/balance/pass), sheave + cwt (rig), cwt (balance/pass), motor (motor), brake (safety).
    Params: load_cue (balance: top plates glow amber), clamp_cue (safety), cam0/1, tgt0/1, lens, fill, golden."""
    _v_lift(ctx, p, p.get("view", "hook"))


S.V2_BUILDERS.update({
    "mw_kitchen_v2": b_mw_kitchen_v2,
    "checkout_v2": b_checkout_v2,
    "lift_v2": b_lift_v2,
})

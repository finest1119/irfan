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

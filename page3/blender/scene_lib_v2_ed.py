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
Builders (Track A batch 03, 26 Nov 2026, for 29 Nov):
  gps_sky_v2          view hook | sats | timing | clock | drift | fix | outro   scene_lib_v2_tower city (REUSED) + cafe
                                             plaza on the explainer plot: phone on a stand (map + blue dot screen),
                                             stylised satellites on teal orbit arcs, 4 beams converging, satellite
                                             with a dial whose hands speed up, blue dot drifting off over the park.
  e911_v2             view hook | route | sector | hybrid | desk | text | outro   same city + plaza (+ kiosk):
                                             monopole cell tower, low 911 center, pulses phone -> tower -> center,
                                             amber 120-degree sector, teal small fix circle + GPS beam + Wi-Fi rings,
                                             dispatch-desk set (dark map monitors, dot appears), in-call / chat screens.
  remote_ir_v2        view hook | led | code | sensor | phone | try | outro   living-room set: TV (picture swaps on
                                             change_cue), remote with IR LED, spectrum strip with an infrared zone,
                                             pale-violet IR dashes travelling to the TV sensor, phone camera screen
                                             showing the purple-white flash bursts (flash_cue).
Builders (Track A batch 04, 26 Nov 2026, for 30 Nov):
  cabin_lights_v2     view hook | dim | path | shades | twist | outro   REUSED scene_lib_v2_air b_cabin_v2, re-lit:
                                             dusk windows, lights fade on dim_cue, floor path strips, exit pictogram,
                                             window shades slide up on shade_cue.
  banana_ripen_v2     view hook | box | ship | room | twist | yellow | outro   store produce display (REUSED _store),
                                             reefer container, ripening room with teal gas puffs, green -> yellow peels.
  toll_tag_v2         view hook | tag | read | charge | sticker | cams | outro   REUSED tower city: road + gantry
                                             (readers, plate cameras), driver's-eye rig with the tag, sticker coil.
  glove_touch_v2      view hook | grid | touch | glove | thread | outro   REUSED living room: phone, electrode grid,
                                             pointing hand (skin / knit glove / conductive-thread tip), touch glow.
  qr_code_v2          view hook | data | damage | level | corners | tip | outro   REUSED store: poster with a QR-like
                                             code (not decodable), torn patches, finder frames, phone camera view.
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


# ======================================================================================================================
# Track A batch 03 (26 Nov 2026, for 29 Nov): gps_sky_v2, e911_v2, remote_ir_v2
# Shared: in-memory screen / TV / spectrum images (numpy, sRGB floats, <= 512 px, NO digits or letters), make_phone,
# _screen_mat (emission image, optional keyed A/B mix), _uv_quad, make_gps_sat, _beam, make_clock.
# ======================================================================================================================
def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def _cv(w, h, col):
    import numpy as np
    a = np.zeros((h, w, 4), np.float32)
    a[..., :3] = _rgb(col)
    a[..., 3] = 1.0
    return a


def _grid(a):
    import numpy as np
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    return X + 0.5, Y + 0.5            # row 0 = bottom (Blender image origin)


def _paint(a, m, col, alpha=1.0):
    c = _rgb(col) if isinstance(col, str) else col
    import numpy as np
    al = (m.astype(np.float32) if m.dtype == bool else m) * alpha
    for k in range(3):
        a[..., k] = a[..., k] * (1 - al) + c[k] * al


def _rr(a, x0, y0, x1, y1, r, col, alpha=1.0):
    """Rounded rect in pixel coords (y from the bottom)."""
    import numpy as np
    X, Y = _grid(a)
    cx = np.clip(X, x0 + r, x1 - r)
    cy = np.clip(Y, y0 + r, y1 - r)
    d = np.hypot(X - cx, Y - cy)
    m = np.clip(r + 0.5 - d, 0, 1) * ((X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1))
    _paint(a, m, col, alpha)


def _dsc(a, cx, cy, r, col, alpha=1.0, soft=1.0, ring=0.0):
    import numpy as np
    X, Y = _grid(a)
    d = np.hypot(X - cx, Y - cy)
    m = np.clip((r - d) / max(soft, 0.5) + 0.5, 0, 1)
    if ring:
        m = m * np.clip((d - (r - ring)) / 1.0 + 0.5, 0, 1)
    _paint(a, m, col, alpha)


def _np_img(name, a):
    if name in bpy.data.images:
        return bpy.data.images[name]
    h, w = a.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=False)
    im.pixels.foreach_set(a.ravel())
    im.pack()
    return im


def map_img(name="ed_map", dark=False, dot=True, w=256, h=512, dot_uv=(0.5, 0.46), scale=1.0):
    """Street map art (no labels): blocks, white/dark streets, a park, a river; blue location dot with halo."""
    import numpy as np
    a = _cv(w, h, "1d2a3a" if dark else "ece6da")
    X, Y = _grid(a)
    road = "3c5068" if dark else "ffffff"
    blk = "243548" if dark else "e2dccd"
    step = 64 * scale
    for gx in np.arange(-step, w + step, step):
        _rr(a, gx + 6, 0, gx + step - 6, h, 3, blk)
    _paint(a, (np.abs(((X + 7) % step) - step / 2) > step / 2 - 6), road)
    _paint(a, (np.abs(((Y + 23) % (step * 1.3)) - step * 0.65) > step * 0.65 - 6), road)
    _paint(a, np.abs((Y - 0.9 * X) - 40) < 7, "4a6280" if dark else "f6d77a")              # avenue
    _rr(a, w * 0.62, h * 0.66, w * 0.92, h * 0.86, 8, "2e5a46" if dark else "bfe0b0")          # park
    rv = np.abs(Y - (h * 0.18 + 18 * np.sin(X / 30.0))) < 12
    _paint(a, rv, "2a4f78" if dark else "a9d3f0")
    if dot:
        cx, cy = dot_uv[0] * w, dot_uv[1] * h
        _dsc(a, cx, cy, 34, "1a73e8", 0.18, soft=2)
        _dsc(a, cx, cy, 13, "ffffff", 1.0)
        _dsc(a, cx, cy, 9.5, "1a73e8", 1.0)
    return _np_img(name, a)


def call_img(name="ed_call"):
    """In-call screen: dark gradient, contact circle, two rows of round buttons, red end-call pill. No text."""
    import numpy as np
    w, h = 256, 512
    a = _cv(w, h, "0f1520")
    X, Y = _grid(a)
    t = (Y / h)[..., None]
    a[..., :3] = a[..., :3] * (1 - t) + np.array(_rgb("26324a")) * t
    _dsc(a, w / 2, h * 0.74, 44, "6b7a92")
    _dsc(a, w / 2, h * 0.765, 16, "aab6c8")
    _rr(a, w / 2 - 26, h * 0.68, w / 2 + 26, h * 0.715, 18, "aab6c8")
    for yy in (0.42, 0.30):
        for xx in (0.25, 0.5, 0.75):
            _dsc(a, w * xx, h * yy, 24, "3a465a")
            _dsc(a, w * xx, h * yy, 7, "c9d2de")
    _rr(a, w / 2 - 38, h * 0.10, w / 2 + 38, h * 0.10 + 40, 20, "e5484d")
    return _np_img(name, a)


def chat_img(name="ed_chat"):
    """Messaging screen: header bar, grey (left) and blue (right) bubbles, input bar. No text."""
    w, h = 256, 512
    a = _cv(w, h, "f2f3f5")
    _rr(a, 0, h - 56, w, h, 0, "dfe3e8")
    _dsc(a, 30, h - 28, 14, "9aa4b2")
    y = h - 92
    for side, wd, ht in (("r", 150, 46), ("l", 120, 34), ("r", 176, 62), ("l", 96, 34), ("r", 130, 46)):
        if side == "r":
            _rr(a, w - 14 - wd, y - ht, w - 14, y, 16, "2f7cf6")
        else:
            _rr(a, 14, y - ht, 14 + wd, y, 16, "d9dde3")
        y -= ht + 16
    _rr(a, 12, 14, w - 56, 50, 18, "ffffff")
    _dsc(a, w - 32, 32, 18, "2f7cf6")
    return _np_img(name, a)


def camview_img(name, flash=False):
    """Phone camera viewfinder looking at a TV remote's tip; flash=True adds the purple-white IR flash. No text."""
    import numpy as np
    w, h = 256, 512
    a = _cv(w, h, "3b342e")
    X, Y = _grid(a)
    t = (Y / h)[..., None]
    a[..., :3] = a[..., :3] * (1 - t) + np.array(_rgb("6d5f52")) * t
    _rr(a, 0, 0, w, h * 0.22, 0, "5a4d42")                                      # table edge
    _rr(a, w * 0.36, -20, w * 0.64, h * 0.6, 26, "1e2125")                    # remote body (foreshortened)
    for yy in (0.18, 0.28, 0.38):
        for xx in (0.43, 0.5, 0.57):
            _dsc(a, w * xx, h * yy, 6, "4a4f57")
    _dsc(a, w * 0.5, h * 0.5, 9, "c0392b")
    _dsc(a, w * 0.5, h * 0.585, 7, "141414")                                   # LED
    if flash:
        _dsc(a, w * 0.5, h * 0.585, 70, "a46bff", 0.35, soft=30)
        _dsc(a, w * 0.5, h * 0.585, 34, "c9a6ff", 0.8, soft=10)
        _dsc(a, w * 0.5, h * 0.585, 14, "ffffff", 1.0, soft=4)
    _rr(a, 0, h - 40, w, h, 0, "000000")
    _rr(a, 0, 0, w, 64, 0, "000000", 0.85)
    _dsc(a, w / 2, 32, 22, "ffffff")
    _dsc(a, w / 2, 32, 17, "1a1a1a", ring=3.0)
    return _np_img(name, a)


def tv_img(name, warm=False):
    """TV picture (no text): sky gradient, sun, rolling hills, a lake."""
    import numpy as np
    w, h = 512, 288
    a = _cv(w, h, "000000")
    X, Y = _grid(a)
    t = (Y / h)[..., None]
    top, bot = (("f28a5b", "ffd28a") if warm else ("4f8fd6", "bfe0f6"))
    a[..., :3] = np.array(_rgb(bot)) * (1 - t) + np.array(_rgb(top)) * t
    _dsc(a, w * (0.72 if warm else 0.84), h * (0.55 if warm else 0.52), 18, "ffe3a0" if warm else "ffe9a8", soft=3)
    for k, (amp, base, col) in enumerate(((22, 0.46, "6f9a5a" if not warm else "8a6a5a"),
                                         (16, 0.34, "4f7f45" if not warm else "6a4c4a"))):
        m = Y < h * base + amp * np.sin(X / (60.0 + 20 * k) + k)
        _paint(a, m, col)
    _paint(a, (Y < h * 0.16), "3f78a8" if not warm else "b0607a")
    return _np_img(name, a)


def spectrum_img(name="ed_spectrum"):
    """Rainbow strip violet -> red, then a hatched dark-magenta 'invisible' zone (infrared) with an amber frame."""
    import numpy as np
    import colorsys
    w, h = 512, 64
    a = _cv(w, h, "000000")
    X, Y = _grid(a)
    u = X / w
    vis = u < 0.72
    hue = np.clip(0.78 - (u / 0.72) * 0.78, 0, 0.78)
    for i in range(w):
        if u[0, i] < 0.72:
            r, g, b = colorsys.hsv_to_rgb(float(hue[0, i]), 0.85, 0.95)
            a[:, i, 0], a[:, i, 1], a[:, i, 2] = r, g, b
    ir = ~vis
    hatch = ((X + Y) // 10) % 2 == 0
    _paint(a, ir & hatch, "3d2033")
    _paint(a, ir & ~hatch, "2a1726")
    fr = ir & ((u < 0.735) | (u > 0.985) | (Y < 4) | (Y > h - 4))
    _paint(a, fr, "ffb000")
    return _np_img(name, a)


def _img_node(N, img):
    t = N.new("ShaderNodeTexImage")
    t.image = img
    t.interpolation = "Cubic"
    t.extension = "EXTEND"
    return t


def _screen_mat(name, imgs, keys=None, strength=1.2, gloss=True):
    """Emissive screen. imgs = [A] or [A, B]; keys [(frame, fac)] mix A -> B. Strength key list allowed as
    strength=[(frame, value)]."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    out = N.get("Material Output")
    t0 = _img_node(N, imgs[0])
    col = t0.outputs["Color"]
    if len(imgs) > 1:
        t1 = _img_node(N, imgs[1])
        mx = N.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        Lk.new(t0.outputs["Color"], mx.inputs[6])
        Lk.new(t1.outputs["Color"], mx.inputs[7])
        mx.inputs[0].default_value = 0.0
        if keys:
            _hold_sock(mx.inputs[0], keys)
        col = mx.outputs[2]
    em = N.new("ShaderNodeEmission")
    Lk.new(col, em.inputs["Color"])
    if isinstance(strength, (list, tuple)):
        for f, v in strength:
            L.kf_socket(em.inputs["Strength"], max(1, int(f)), v, "LINEAR")
    else:
        em.inputs["Strength"].default_value = strength
    if not gloss:
        Lk.new(em.outputs[0], out.inputs["Surface"])
        return m
    # a little gloss on top of the glass
    gl = N.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.12
    gl.inputs["Color"].default_value = (0.06, 0.06, 0.07, 1)
    ad = N.new("ShaderNodeAddShader")
    Lk.new(em.outputs[0], ad.inputs[0])
    Lk.new(gl.outputs[0], ad.inputs[1])
    Lk.new(ad.outputs[0], out.inputs["Surface"])
    return m


def _uv_quad(name, w, h, mat, loc=(0, 0, 0), parent=None):
    """UV-mapped quad in local XZ facing -Y, centred on loc."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("uv")
    x, y, z = loc
    vs = [bm.verts.new(v) for v in ((x - w / 2, y, z - h / 2), (x + w / 2, y, z - h / 2), (x + w / 2, y, z + h / 2),
                                    (x - w / 2, y, z + h / 2))]
    f = bm.faces.new(vs)
    for lp, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uvl].uv = uv
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def _hold_keys(keyfn, keys):
    """Step-safe keys: Blender 5.3 ignores the interpolation pref, so new keys are BEZIER. Insert a hold key one frame
    before every change so values never ramp from frame 1. keyfn(frame, value); keys [(frame, value)] (any order)."""
    ks = sorted((max(1, int(f)), v) for f, v in keys)
    prev = None
    for f, v in ks:
        if prev is not None and f - 1 > prev[0]:
            keyfn(f - 1, prev[1])
        keyfn(f, v)
        prev = (f, v)


def _hold_obj(o, path, keys):
    _hold_keys(lambda f, v: kf(o, path, f, Vector(v) if isinstance(v, (tuple, list, Vector)) else v), keys)


def _hold_sock(sock, keys):
    _hold_keys(lambda f, v: L.kf_socket(sock, f, v), keys)


def _annulus(name, R, w, mat, seg=64, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    """Flat ring band (faces, so it renders; an edges-only circle + WIREFRAME renders nothing)."""
    bm = bmesh.new()
    inner, outer = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        inner.append(bm.verts.new(((R - w / 2) * math.cos(a), (R - w / 2) * math.sin(a), 0)))
        outer.append(bm.verts.new(((R + w / 2) * math.cos(a), (R + w / 2) * math.sin(a), 0)))
    for k in range(seg):
        bm.faces.new((inner[k], inner[(k + 1) % seg], outer[(k + 1) % seg], outer[k]))
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), loc, rot, parent=parent)
    o.visible_shadow = False
    return o


def _rings(ctx, center, start, color=TEAL, count=3, gap=8, r1=12.0, life=24, name="rg", parent=None,
           rot=(0.0, 0.0, 0.0), width=0.08):
    """Expanding fading rings (like scene_lib_v2_air.ring_pulses, but face-based so they render)."""
    objs = []
    for k in range(count):
        m, sock = L.add_mat("%s_m%d" % (name, k), color, 0.0)
        o = _annulus("%s%d" % (name, k), 1.0, width, m, 64, center, rot, parent)
        f0 = max(2, int(start + k * gap))
        _hold_obj(o, "scale", [(1, (0.001,) * 3), (f0, (r1 * 0.12,) * 3), (f0 + life, (r1,) * 3)])
        _hold_sock(sock, [(1, 0.0), (f0, 4.0), (f0 + life, 0.0)])
        objs.append(o)
    return objs


PH_W, PH_T, PH_H = 0.072, 0.0085, 0.152


def make_phone(name, screen_mat, loc, rot=(0, 0, 0), stand=True, parent=None):
    """Smartphone standing in local XZ, screen facing local -Y (front camera dot near the top, rear camera bump on
    +Y). Optional desk stand. Returns dict(root, screen, front_cam)."""
    root = _empty(name, loc, parent)
    root.rotation_euler = rot
    body = S.pbr("ph_body", hexc("2a2d33"), 0.35, 0.3, coat=0.5, var=0)
    black = S.pbr("ph_black", hexc("0b0c0e"), 0.15, coat=0.8, var=0)
    lens = S.pbr("ph_lens", hexc("15181d"), 0.08, 0.5, coat=1.0, var=0)

    def b(bm):
        _rbox(bm, (0, 0, PH_H / 2), (PH_W, PH_T, PH_H), r=0.007, seg=3, mi=0)
        _rbox(bm, (0, -PH_T / 2 + 0.0004, PH_H / 2), (PH_W - 0.002, 0.0012, PH_H - 0.002), r=0.006, seg=2, mi=1)
        _rbox(bm, (-PH_W / 2 + 0.017, PH_T / 2 + 0.0012, PH_H - 0.019), (0.026, 0.0025, 0.026), r=0.005, seg=2, mi=0)
        for dx, dz in ((-0.006, 0.006), (0.006, -0.006)):
            _cyl(bm, (-PH_W / 2 + 0.017 + dx, PH_T / 2 + 0.003, PH_H - 0.019 + dz), 0.0042, 0.002, "Y", 16, 2)
        _cyl(bm, (0, -PH_T / 2 - 0.0006, PH_H - 0.0095), 0.0022, 0.0012, "Y", 16, 2)
    S.obj(name + "_body", _mesh(name + "_body", b, [body, black, lens], smooth=False), parent=root)
    scr = _uv_quad(name + "_scr", PH_W - 0.007, PH_H - 0.024, screen_mat, (0, -PH_T / 2 - 0.0005, PH_H / 2 - 0.002),
                   parent=root)
    fc = _empty(name + "_fcam", (0, -PH_T / 2 - 0.001, PH_H - 0.0095), root)
    if stand:
        st = S.pbr("ph_stand", hexc("8d949c"), 0.35, 0.8, var=0)

        def sb(bm):
            S.bm_box(bm, (0, 0.012, 0.004), (0.07, 0.06, 0.008), 0)
            S.bm_box(bm, (0, -0.012, 0.012), (0.07, 0.008, 0.016), 0)
        s = S.obj(name + "_stand", _mesh(name + "_stand", sb, [st]), parent=root)
        s.location = (0, 0.0, -0.004)
    return {"root": root, "screen": scr, "fcam": fc}


def _beam(name, p0, p1, r, mat, seg=8):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    _cyl(bm, (0, 0, d.length / 2), r, d.length, "Z", seg)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]))
    o.location = p0
    o.rotation_euler = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    o.visible_shadow = False
    return o


def _mover(ctx, o, p0, p1, f0, f1, show=True):
    kf(o, "location", 1, Vector(p0))
    kf(o, "location", max(1, f0), Vector(p0))
    kf(o, "location", max(f0 + 1, f1), Vector(p1))
    _interp(o, "LINEAR")
    if show:
        _hold_obj(o, "scale", [(1, (0.001,) * 3), (max(2, f0), (1, 1, 1)), (max(f0 + 2, f1), (0.001,) * 3)])


def make_gps_sat(name, loc, s=1.0, yaw=0.0):
    """Stylised navigation satellite: gold-foil bus, two long blue solar wings on booms, antenna array on the
    Earth-facing (-Z) side. Unit size ~ 1.6 m bus, 12 m span; s scales."""
    root = _empty(name, loc)
    root.rotation_euler = (0, 0, yaw)
    root.scale = (s, s, s)
    gold = S.pbr("sat_gold", hexc("c99a3c"), 0.32, 0.9, var=0.18, var_scale=6.0, haze=False)
    cell = S.pbr("sat_cell", hexc("1c3a78"), 0.22, 0.5, coat=0.6, var=0.05, var_scale=3.0, haze=False)
    silv = S.pbr("sat_silver", hexc("c9ced4"), 0.3, 0.9, var=0, haze=False)
    wht = S.pbr("sat_white", hexc("e8e8e2"), 0.5, var=0, haze=False)

    def b(bm):
        _rbox(bm, (0, 0, 0), (1.6, 1.6, 2.0), r=0.08, seg=2, mi=0)
        for sx in (-1, 1):
            _cyl(bm, (sx * 1.5, 0, 0.1), 0.06, 1.4, "X", 8, 2)
            for k in range(3):
                S.bm_box(bm, (sx * (2.9 + k * 1.75), 0, 0.1), (1.6, 0.05, 2.2), 1)
                S.bm_box(bm, (sx * (2.9 + k * 1.75) + sx * 0.82, 0, 0.1), (0.05, 0.08, 2.3), 2)
        _cyl(bm, (0, 0, -1.08), 0.75, 0.12, "Z", 24, 3)
        for k in range(10):
            a = 2 * math.pi * k / 10
            _cyl(bm, (0.5 * math.cos(a), 0.5 * math.sin(a), -1.38), 0.07, 0.5, "Z", 8, 3)
        _cyl(bm, (0, 0, -1.38), 0.09, 0.5, "Z", 8, 3)
    S.obj(name + "_m", _mesh(name + "_m", b, [gold, cell, silv, wht]), parent=root)
    return root


def make_clock(name, loc, R, rot=(0, 0, 0), face="e7efed", rim=TEAL, ink="1f262e"):
    """Clock dial facing local -Y with 12 tick bars (no digits) and two hands (returns root, minute, hour)."""
    root = _empty(name, loc)
    root.rotation_euler = rot
    fm = S.pbr(name + "_face", hexc(face), 0.5, var=0, haze=False)
    dk = S.pbr(name + "_ink", hexc(ink), 0.4, var=0, haze=False)
    rm, _ = L.add_mat(name + "_rim", rim, 3.0)

    def b(bm):
        _cyl(bm, (0, 0, 0), R, R * 0.08, "Y", 48, 0)
        for k in range(12):
            a = 2 * math.pi * k / 12
            ln = R * (0.16 if k % 3 == 0 else 0.09)
            c = ((R * 0.86 - ln / 2) * math.sin(a), -R * 0.045, (R * 0.86 - ln / 2) * math.cos(a))
            vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
            for v in vs:
                v.co = Vector((v.co.x * R * 0.05, v.co.y * R * 0.01, v.co.z * ln))
            bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(-a, 3, "Y"))
            bmesh.ops.translate(bm, verts=vs, vec=Vector(c))
            for f in {f for v in vs for f in v.link_faces}:
                f.material_index = 1
        _cyl(bm, (0, -R * 0.06, 0), R * 0.06, R * 0.02, "Y", 16, 1)
    S.obj(name + "_dial", _mesh(name + "_dial", b, [fm, dk]), parent=root)
    _annulus(name + "_ring", R * 1.03, R * 0.05, rm, 64, (0, -R * 0.045, 0), (math.radians(90), 0, 0), root)
    hands = []
    for k, (ln, wd) in enumerate(((R * 0.78, R * 0.05), (R * 0.5, R * 0.08))):
        piv = _empty(name + "_piv%d" % k, (0, -R * 0.055 - k * R * 0.005, 0), root)
        S.obj(name + "_hand%d" % k, _mesh(name + "_hand%d" % k, lambda bm, ln=ln, wd=wd: S.bm_box(
            bm, (0, 0, ln / 2 - R * 0.06), (wd, R * 0.01, ln), 0), [dk]), parent=piv)
        hands.append(piv)
    return root, hands[0], hands[1]


def _spin_keys(o, keys, axis=1):
    """keys [(frame, angle_deg)] rotation about local axis (default Y = dial normal)."""
    for f, ang in keys:
        r = [0.0, 0.0, 0.0]
        r[axis] = math.radians(ang)
        kf(o, "rotation_euler", max(1, int(f)), Vector(r))
    _interp(o, "LINEAR")


# ---------------------------------------------------------------- living room + TV remote (remote_ir_v2)
LR_TV = (0.0, 2.45, 1.06)            # TV centre (front face y = 2.425)
LR_SENSOR = (0.38, 2.418, 0.648)     # IR receiver window on the TV's bottom bezel
LR_REMOTE = (0.12, -0.42, 0.452)     # remote centre on the coffee table (LED end towards +Y)
IR_COL = hexc("c58cff")


def _living_room(ctx, p, tv_keys=None, tv_strength=1.1):
    """Own lit living-room set (never a void): mid-tone walls (calm behind captions), oak floor, rug, navy sofa,
    walnut coffee table, media console + wall TV (picture = tv_img; tv_keys swaps day -> sunset picture), window
    with daylight panel on the left wall, floor lamp, shelf, plant, framed colour-block art. No text."""
    sc = ctx.scene
    w = bpy.data.worlds.new("lr_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.6, 0.58, 0.55, 1.0)
    bg.inputs["Strength"].default_value = 0.4
    sc.view_settings.exposure = p.get("exposure", -0.5)
    L.fog(0.001, hexc("d8d2c8"), start=10.0)
    wall = S.pbr("lr_wall", hexc(p.get("wall", "8b9aa3")), 0.85, var=0.02)
    side = S.pbr("lr_side", hexc("a89a8a"), 0.85, var=0.02)
    ceil = S.pbr("lr_ceil", hexc("e9e4dc"), 0.9, var=0)
    floor = S.pbr("lr_floor", hexc("a87b52"), 0.5, var=0.12, var_scale=3.0, bump=0.01)
    rug = S.pbr("lr_rug", hexc("6d7f73"), 0.95, var=0.06, var_scale=8.0, bump=0.02)
    S.plane_obj("lr_floor", 8.0, 8.0, (0, -0.5, 0.0), floor)
    S.plane_obj("lr_rug", 2.8, 2.0, (0, -0.6, 0.006), rug)

    def room(bm):
        S.bm_box(bm, (0, 2.7, 1.4), (6.4, 0.2, 2.8), 0)                      # TV wall
        S.bm_box(bm, (0, -3.6, 1.4), (6.4, 0.2, 2.8), 1)
        S.bm_box(bm, (3.1, -0.45, 1.4), (0.2, 6.5, 2.8), 1)
        for (y0, y1, z0, z1) in ((-3.6, -1.4, 0, 2.8), (0.4, 2.7, 0, 2.8), (-1.4, 0.4, 0, 0.8), (-1.4, 0.4, 2.2, 2.8)):
            S.bm_box(bm, (-3.1, (y0 + y1) / 2, (z0 + z1) / 2), (0.2, y1 - y0, z1 - z0), 1)   # window wall
        S.bm_box(bm, (0, -0.45, 2.85), (6.4, 6.5, 0.1), 2)
        S.bm_box(bm, (0, 2.585, 0.05), (6.2, 0.03, 0.1), 2)                  # skirting
    S.obj("lr_room", _mesh("lr_room", room, [wall, side, ceil]))
    sky = S.emis("lr_sky", hexc("cfe3f2"), 2.0)
    S.obj("lr_sky", _mesh("lr_sky", lambda bm: S.bm_box(bm, (-3.25, -0.5, 1.5), (0.02, 1.8, 1.4)), [sky]))
    frame = S.pbr("lr_wframe", hexc("f3f0ea"), 0.4, var=0)
    S.obj("lr_wframe", _mesh("lr_wframe", lambda bm: [S.bm_box(bm, c, s) for c, s in (
        ((-3.0, -0.5, 0.8), (0.12, 1.9, 0.05)), ((-3.0, -0.5, 2.2), (0.12, 1.9, 0.05)),
        ((-3.0, -1.42, 1.5), (0.12, 0.05, 1.45)), ((-3.0, 0.42, 1.5), (0.12, 0.05, 1.45)),
        ((-3.0, -0.5, 1.5), (0.08, 0.03, 1.4)))], [frame]))
    # media console + TV
    walnut = S.pbr("lr_walnut", hexc("6b4a32"), 0.5, coat=0.2, var=0.08, var_scale=6.0)
    oak = S.pbr("lr_oak", hexc("b58a5a"), 0.45, coat=0.25, var=0.08, var_scale=6.0)
    tvb = S.pbr("lr_tvbody", hexc("15171a"), 0.3, 0.2, coat=0.6, var=0)
    S.obj("lr_console", _mesh("lr_console", lambda bm: [
        _rbox(bm, (0, 2.38, 0.3), (2.0, 0.42, 0.42), 0.02, 2, 0),
        S.bm_box(bm, (-0.5, 2.165, 0.3), (0.006, 0.01, 0.36), 0), S.bm_box(bm, (0.5, 2.165, 0.3), (0.006, 0.01, 0.36), 0)],
        [walnut]))
    tx, ty, tz = LR_TV
    S.obj("lr_tv", _mesh("lr_tv", lambda bm: [
        _rbox(bm, (tx, ty, tz), (1.47, 0.05, 0.86), 0.008, 2, 0),
        S.bm_box(bm, (tx, 2.5, 0.56), (0.3, 0.12, 0.02), 0), S.bm_box(bm, (tx, 2.5, 0.53), (0.04, 0.04, 0.06), 0)], [tvb]))
    imgs = [tv_img("ed_tv_day"), tv_img("ed_tv_warm", warm=True)]
    scr = _screen_mat("lr_tvscreen", imgs, tv_keys, tv_strength, gloss=False)
    _uv_quad("lr_tvscr", 1.42, 0.79, scr, (tx, 2.4243, tz + 0.02))
    sens = S.pbr("lr_sensor", hexc("3a0d14"), 0.08, coat=1.0, var=0)
    S.obj("lr_sensor", _mesh("lr_sensor", lambda bm: _rbox(bm, LR_SENSOR, (0.04, 0.008, 0.014), 0.003, 1, 0), [sens]))
    # sofa
    navy = S.pbr("lr_sofa", hexc("2f4766"), 0.9, var=0.05, var_scale=10.0, bump=0.02)
    cush = S.pbr("lr_cush", hexc("c98c3b"), 0.9, var=0.05, var_scale=10.0, bump=0.02)

    def sofa(bm):
        _rbox(bm, (0, -2.05, 0.24), (2.3, 0.95, 0.36), 0.05, 2, 0)
        _rbox(bm, (0, -2.43, 0.62), (2.3, 0.22, 0.62), 0.06, 2, 0)
        for sx in (-1, 1):
            _rbox(bm, (sx * 1.08, -2.05, 0.5), (0.2, 0.95, 0.34), 0.06, 2, 0)
            _rbox(bm, (sx * 0.48, -1.98, 0.48), (0.9, 0.78, 0.14), 0.05, 2, 0)
        _rbox(bm, (-0.62, -2.25, 0.7), (0.42, 0.14, 0.38), 0.06, 2, 1)
        _rbox(bm, (0.68, -2.25, 0.7), (0.42, 0.14, 0.38), 0.06, 2, 1)
    S.obj("lr_sofa", _mesh("lr_sofa", sofa, [navy, cush]))
    # coffee table
    S.obj("lr_table", _mesh("lr_table", lambda bm: [
        _rbox(bm, (0, -0.45, 0.42), (1.15, 0.62, 0.04), 0.012, 2, 0)] + [
        S.bm_box(bm, (sx * 0.5, -0.45 + sy * 0.24, 0.2), (0.04, 0.04, 0.4), 0) for sx in (-1, 1) for sy in (-1, 1)],
        [oak]))
    # props: books on the table, mug, plant, lamp, shelf, art
    bk = [S.pbr("lr_bk%d" % i, hexc(c), 0.7, var=0.03) for i, c in enumerate(("b8433a", "2f6f8f", "d9b45a", "4f7a4a"))]
    S.obj("lr_books", _mesh("lr_books", lambda bm: [
        _rbox(bm, (-0.36, -0.36, 0.455 + 0.028 * k), (0.24 - 0.02 * k, 0.17, 0.026), 0.004, 1, k) for k in range(3)],
        bk))
    mug = S.pbr("lr_mug", hexc("e07a5f"), 0.35, coat=0.5, var=0)
    S.obj("lr_mug", _mesh("lr_mug", lambda bm: _cyl(bm, (0.42, -0.6, 0.49), 0.04, 0.1, "Z", 20), [mug]))
    pot = S.pbr("lr_pot", hexc("d9774f"), 0.6, var=0.03)
    leaf = S.pbr("lr_leaf", hexc("4f8a45"), 0.6, var=0.08, var_scale=8.0)
    S.obj("lr_pot", _mesh("lr_pot", lambda bm: _cyl(bm, (-2.5, 2.1, 0.22), 0.2, 0.44, "Z", 20), [pot]))
    bm = bmesh.new()
    rng = random.Random(5)
    for k in range(16):
        r = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=rng.uniform(0.14, 0.22))
        bmesh.ops.translate(bm, vec=(-2.5 + rng.uniform(-0.2, 0.2), 2.1 + rng.uniform(-0.2, 0.2), 0.7 + rng.uniform(0, 0.8)),
                            verts=r["verts"])
    S.obj("lr_plant", S.mesh_from_bm("lr_plant", bm, [leaf], smooth=True))
    brass = S.pbr("lr_brass", hexc("b8913f"), 0.3, 0.9, var=0)
    shade = S.emis("lr_shade", hexc("ffe2b0"), 2.5)
    S.obj("lr_lamp", _mesh("lr_lamp", lambda bm: [_cyl(bm, (2.45, 1.9, 0.75), 0.015, 1.5, "Z", 8, 0),
                                                   _cyl(bm, (2.45, 1.9, 0.02), 0.16, 0.03, "Z", 16, 0),
                                                   _cyl(bm, (2.45, 1.9, 1.58), 0.2, 0.3, "Z", 20, 1)], [brass, shade]))
    _point("lr_lamp_l", (2.45, 1.9, 1.5), 40.0, (1.0, 0.82, 0.6), 0.15)
    shelf = S.pbr("lr_shelf", hexc("d8cfc2"), 0.6, var=0.02)
    S.obj("lr_shelf", _mesh("lr_shelf", lambda bm: [S.bm_box(bm, (2.85, -1.0, 0.9), (0.35, 1.2, 1.8), 0)] + [
        _rbox(bm, (2.66, -1.4 + 0.12 * k, 0.35 + 0.45 * (k % 3)), (0.04, 0.09, 0.28), 0.005, 1, 1 + k % 4)
        for k in range(7)], [shelf] + bk))
    art = [S.pbr("lr_art%d" % i, hexc(c), 0.8, var=0) for i, c in enumerate(("e2d6bd", "c8553d", "2f6f8f", "e3b448"))]
    S.obj("lr_art", _mesh("lr_art", lambda bm: [
        S.bm_box(bm, (2.99, 0.9, 1.6), (0.03, 0.9, 0.7), 0), S.bm_box(bm, (2.97, 0.72, 1.68), (0.02, 0.36, 0.4), 1),
        S.bm_box(bm, (2.97, 1.08, 1.5), (0.02, 0.3, 0.3), 2), _cyl(bm, (2.97, 1.12, 1.78), 0.09, 0.02, "X", 20, 3)], art))
    # lights
    for k, (x, y) in enumerate(((-1.2, -0.6), (1.2, -0.6), (0.0, 1.4))):
        A._area("lr_a%d" % k, (x, y, 2.7), 1.4, p.get("ceil_w", 120.0), (1.0, 0.95, 0.88), size_y=1.4)
    win = A._area("lr_win", (-2.8, -0.5, 1.5), 1.6, p.get("win_w", 160.0), (0.9, 0.95, 1.0), size_y=1.3)
    win.rotation_euler = (0, math.radians(-90), 0)


def make_remote(name, loc, yaw=0.0, parent=None):
    """TV remote (graphite body, grey round buttons, red power button, dark IR LED dome on the +Y end). No text.
    Returns (root, led_empty)."""
    root = _empty(name, loc, parent)
    root.rotation_euler = (0, 0, yaw)
    body = S.pbr("rm_body", hexc("2b2e33"), 0.4, coat=0.4, var=0.02)
    btn = S.pbr("rm_btn", hexc("737a83"), 0.5, var=0)
    red = S.pbr("rm_red", hexc("c8402f"), 0.4, coat=0.3, var=0)
    led = S.pbr("rm_led", hexc("1c1416"), 0.05, coat=1.0, var=0)

    def b(bm):
        _rbox(bm, (0, 0, 0), (0.05, 0.195, 0.02), 0.008, 3, 0)
        for i in range(3):
            for j in range(4):
                _cyl(bm, (-0.013 + 0.013 * i, -0.06 + 0.02 * j, 0.0105), 0.0045, 0.003, "Z", 12, 1)
        _rbox(bm, (0, 0.035, 0.0105), (0.03, 0.022, 0.004), 0.004, 1, 1)
        _cyl(bm, (0.014, 0.075, 0.0105), 0.005, 0.003, "Z", 12, 2)
        _cyl(bm, (0, 0.0985, 0.002), 0.0042, 0.004, "Y", 16, 3)
    S.obj(name + "_m", _mesh(name + "_m", b, [body, btn, red, led]), parent=root)
    le = _empty(name + "_led", (0, 0.101, 0.002), root)
    return root, le


def _ir_pulses(ctx, p0, p1, f0, speed=2.2, pattern=(1, 0, 0, 1, 0, 1, 1, 0, 1, 0), reps=2, name="irp", show_frac=1.0):
    """IR 'flashes' made visible: short and long pale-violet dashes travelling from p0 to p1 (pattern 1 = long)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ln = d.length
    u = d.normalized()
    m, sock = L.add_mat(name + "_m", IR_COL, 3.5)
    rot = Vector((1, 0, 0)).rotation_difference(u).to_euler()
    fps = ctx.fps
    t_trav = ln / speed * fps
    objs = []
    gap_f = 3.0
    k = 0
    f = f0
    for r in range(reps):
        for bit in pattern:
            L_ = 0.2 if bit else 0.08
            bm = bmesh.new()
            _cyl(bm, (0, 0, 0), 0.018, L_, "X", 8)
            o = S.obj("%s%d" % (name, k), S.mesh_from_bm("%s%d" % (name, k), bm, [m]), rot=rot)
            o.visible_shadow = False
            _mover(ctx, o, p0, p1, int(f), int(f + t_trav))
            objs.append(o)
            f += (L_ / speed) * fps + gap_f
            k += 1
        f += 14
    return objs, f0 + t_trav


def _v_remote(ctx, p, view):
    T = ctx.frames
    tv_keys = None
    fch = None
    if view == "sensor":
        fch = ctx.word_time(p.get("change_cue", "does"), 0.6)
        tv_keys = [(1, 0.0), (fch, 1.0)]
    tvs = p.get("tv_strength", 0.55 if view in ("phone", "try") else (0.5 if view == "sensor" else 1.0))
    _living_room(ctx, p, tv_keys, tvs)
    yaw = math.radians(p.get("remote_yaw", 6.0))
    lx, ly, lz = LR_REMOTE
    led_w = (lx - 0.101 * math.sin(yaw), ly + 0.101 * math.cos(yaw), lz + 0.002)
    if view in ("hook", "led", "code", "sensor"):
        rem, led = make_remote("remote", LR_REMOTE, yaw)
    if view == "hook":
        _cam_keys2(ctx, [(1, p.get("cam0", (0.3, -1.18, 0.66)), p.get("tgt0", (0.05, 1.4, 0.62))),
                         (1.0, p.get("cam1", (0.28, -1.1, 0.65)), p.get("tgt1", (0.05, 1.4, 0.62)))],
                   lens=p.get("lens", 30), clip=0.02)
        S.anchor(ctx, "remote", rem, (0, 0, 0.02))
        S.anchor(ctx, "tv", bpy.data.objects["lr_tvscr"], (0, 0, 0))
    elif view == "led":
        sp = _screen_mat("ir_spec", [spectrum_img()], strength=1.4)
        c0 = Vector(p.get("cam0", (led_w[0] + 0.09, led_w[1] + 0.2, lz + 0.05)))
        q = _uv_quad("ir_spec", 0.075, 0.0095, sp, (0, 0, 0))
        q.location = p.get("spec_loc", (led_w[0] + 0.045, led_w[1] + 0.05, lz - 0.005))
        dq = c0 - Vector(q.location)
        q.rotation_euler = (math.atan2(dq.z, math.hypot(dq.x, dq.y)) * 0.0, 0, math.atan2(dq.x, -dq.y))
        _cam_keys2(ctx, [(1, tuple(c0), p.get("tgt0", (led_w[0] + 0.012, led_w[1], lz + 0.022))),
                         (1.0, p.get("cam1", tuple(c0 + Vector((-0.012, -0.02, -0.004)))), p.get("tgt1", (led_w[0] + 0.012, led_w[1], lz + 0.022)))],
                   lens=p.get("lens", 40), clip=0.005)
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_object = led
        ctx.cam.data.dof.aperture_fstop = p.get("fstop", 5.6)
        S.anchor(ctx, "led", led, (0, 0.002, 0.002))
        S.anchor(ctx, "ir", q, (0.07, 0, 0))
    elif view in ("code", "sensor"):
        f0 = 4 if view == "code" else max(1, (fch or 30) - int(3.1 / 2.2 * ctx.fps) - 40)
        objs, f_arr = _ir_pulses(ctx, led_w, LR_SENSOR, f0, reps=3 if view == "code" else 2)
        gm, _ = L.add_mat("ir_path", IR_COL, 0.25)
        _beam("ir_path", led_w, LR_SENSOR, 0.008, gm)
        mid = Vector(led_w).lerp(Vector(LR_SENSOR), 0.38)
        e = _empty("ir_mid", tuple(mid))
        S.anchor(ctx, "pulses", e, (0, 0, 0.02))
        if view == "code":
            _cam_keys2(ctx, [(1, p.get("cam0", (0.32, -1.15, 0.8)), p.get("tgt0", (0.1, 1.6, 0.58))),
                             (1.0, p.get("cam1", (0.3, -1.08, 0.79)), p.get("tgt1", (0.1, 1.6, 0.58)))],
                       lens=p.get("lens", 26), clip=0.02)
        else:
            _rings(ctx, (LR_SENSOR[0], LR_SENSOR[1] - 0.01, LR_SENSOR[2]), int(f_arr), color=IR_COL, count=3,
                          gap=7, r1=0.08, life=18, rot=(math.radians(90), 0, 0), name="sens")
            sx, sy, sz = LR_SENSOR
            _cam_keys2(ctx, [(1, p.get("cam0", (sx + 0.95, sy - 1.15, sz + 0.3)), p.get("tgt0", (sx - 0.05, sy, sz + 0.05))),
                             (1.0, p.get("cam1", (sx + 0.85, sy - 1.05, sz + 0.28)), p.get("tgt1", (sx - 0.05, sy, sz + 0.05)))],
                       lens=p.get("lens", 30), clip=0.02)
            S.anchor(ctx, "sensor", bpy.data.objects["lr_sensor"], (sx, sy - 0.005, sz + 0.004))
    elif view in ("phone", "try", "outro"):
        ff = ctx.word_time(p.get("flash_cue", "see" if view == "phone" else "press"), 0.45)
        keys = [(1, 0.0)]
        if view != "outro":
            f = ff
            for _ in range(4):                       # burst of flashes, repeated
                for k in range(6):
                    keys.append((f + k * 3, 1.0 if k % 2 == 0 else 0.0))
                f += 30
            keys.append((f, 0.0))
        scr = _screen_mat("ph_cam", [camview_img("ed_cam_off"), camview_img("ed_cam_ir", flash=True)], keys, 1.0)
        if view == "try":
            ph = make_phone("phone", scr, (-0.25, -0.62, 0.44), (math.radians(-12), 0, math.radians(-18)))
            make_remote("remote2", p.get("remote2", (-0.38, -0.76, 0.452)), math.radians(p.get("remote2_yaw", -40.0)))
            fcw = ph["fcam"]
            _cam_keys2(ctx, [(1, p.get("cam0", (-0.55, -1.0, 0.75)), p.get("tgt0", (-0.26, -0.62, 0.55))),
                             (1.0, p.get("cam1", (-0.52, -0.96, 0.74)), p.get("tgt1", (-0.26, -0.62, 0.55)))],
                       lens=p.get("lens", 32), clip=0.01)
            S.anchor(ctx, "front", fcw, (0, 0, 0))
            S.anchor(ctx, "screen", ph["screen"], (0, -0.001, 0.07))
        else:
            ph = make_phone("phone", scr, (-0.25, -0.62, 0.44), (math.radians(-12), 0, 0))
            S.obj("lr_bookstack", _mesh("lr_bookstack", lambda bm: [
                _rbox(bm, (-0.24, -0.25, 0.46 + 0.03 * k), (0.2, 0.15, 0.028), 0.004, 1, k) for k in range(3)],
                [S.pbr("lr_bk%d" % i, hexc("b8433a")) for i in range(3)]))
            r2, _ = make_remote("remote2", (-0.24, -0.27, 0.56), math.radians(180))
            r2.rotation_euler = (math.radians(-6), 0, math.radians(180))
            if view == "phone":
                _cam_keys2(ctx, [(1, p.get("cam0", (-0.33, -1.06, 0.66)), p.get("tgt0", (-0.25, -0.5, 0.6))),
                                 (1.0, p.get("cam1", (-0.32, -1.0, 0.65)), p.get("tgt1", (-0.25, -0.5, 0.6)))],
                           lens=p.get("lens", 32), clip=0.01)
            else:
                _cam_keys2(ctx, [(1, p.get("cam0", (-0.6, -1.25, 0.8)), p.get("tgt0", (-0.15, 0.2, 0.75))),
                                 (1.0, p.get("cam1", (1.9, -2.6, 1.5)), p.get("tgt1", (-0.2, 0.6, 0.85)))],
                           lens=p.get("lens", 28), clip=0.02)
            S.anchor(ctx, "screen", ph["screen"], (0, -0.001, 0.07))
        S.anchor(ctx, "phone", ph["root"], (0, 0, PH_H))


def b_remote_ir_v2(ctx, p):
    """TV remote infrared explainer in a lit living-room set. view hook | led | code | sensor | phone | try | outro.
    Anchors: remote, tv (hook); led, ir (led: spectrum strip with the infrared zone); pulses (code/sensor); sensor;
    screen, phone (phone/try/outro); front (try: the selfie camera). Params: change_cue (sensor: TV picture changes),
    flash_cue (phone/try: purple-white flash bursts on the phone screen), cam0/1, tgt0/1, lens, exposure, wall."""
    _v_remote(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- tower city plaza (gps_sky_v2 + e911_v2)
SPOT = (260.0, 36.0)                 # cafe table on the explainer plot (park to the south, road y = 60 to the north)
TBL_Z = 0.745                        # table top
CELL = (322.0, -38.0)                # e911 cell tower
PSAP = (205.0, -235.0)               # e911 local 911 center (low building in the park)


def _plaza_world(ctx, p, kiosk=False):
    """scene_lib_v2_tower city + hero tower (REUSED world, as lift_v2) with a small cafe plaza on the explainer plot:
    paving, cafe tables + chairs, planters with trees, benches. City cars on the y = 60 road are removed."""
    import scene_lib_v2_tower as TW
    TW.build_city(ctx, p, golden=p.get("golden", False))
    TW.build_hero(ctx)
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
    sx, sy = SPOT
    S.plane_obj("pz_pave", 70, 46, (sx, sy + 2.0, 0.045), S.pbr("pz_paving", hexc("c9bfae"), 0.8, var=0.08, var_scale=0.8))
    teak = S.pbr("pz_teak", hexc("9a6a3f"), 0.5, coat=0.2, var=0.08, var_scale=8.0)
    iron = S.pbr("pz_iron", hexc("2f3438"), 0.4, 0.7, var=0)
    green = S.pbr("pz_chair", hexc("2f6f5e"), 0.45, 0.3, var=0.02)
    tables = [(0.0, 0.0), (-3.2, 1.8), (3.4, 2.2), (-2.6, -3.0), (2.9, -3.4), (6.6, -0.6), (-6.4, -0.8)]

    def furn(bm):
        for k, (dx, dy) in enumerate(tables):
            x, y = sx + dx, sy + dy
            _cyl(bm, (x, y, TBL_Z - 0.015), 0.36, 0.03, "Z", 28, 0)
            _cyl(bm, (x, y, TBL_Z / 2), 0.03, TBL_Z - 0.03, "Z", 8, 1)
            _cyl(bm, (x, y, 0.06), 0.22, 0.03, "Z", 16, 1)
            for a in ((0.6, 2.2) if k == 0 else (0.4, 2.0, 3.6)):
                cx, cy = x + 0.62 * math.cos(a), y + 0.62 * math.sin(a)
                _rbox(bm, (cx, cy, 0.45), (0.42, 0.42, 0.04), 0.02, 1, 2)
                bx, by = x + 0.82 * math.cos(a), y + 0.82 * math.sin(a)
                vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
                for v in vs:
                    v.co = Vector((v.co.x * 0.42, v.co.y * 0.04, v.co.z * 0.42))
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(a + math.pi / 2, 3, "Z"))
                bmesh.ops.translate(bm, verts=vs, vec=Vector((bx, by, 0.68)))
                for f in {f for v in vs for f in v.link_faces}:
                    f.material_index = 2
                for lx_, ly_ in ((0.17, 0.17), (-0.17, 0.17), (0.17, -0.17), (-0.17, -0.17)):
                    _cyl(bm, (cx + lx_, cy + ly_, 0.22), 0.012, 0.44, "Z", 6, 1)
        for dx in (-12.0, 12.0):                                    # benches
            S.bm_box(bm, (sx + dx, sy + 7.0, 0.45), (2.2, 0.5, 0.06), 0)
            S.bm_box(bm, (sx + dx, sy + 7.0, 0.22), (2.0, 0.08, 0.44), 1)
    S.obj("pz_furn", _mesh("pz_furn", furn, [teak, iron, green]))
    planter = S.pbr("pz_planter", hexc("8e9aa3"), 0.8, var=0.04)
    pts = [(sx + dx, sy + dy) for dx, dy in ((-14, 9), (14, 9), (-20, -6), (20, -6), (-9, -14), (9, -14), (0, 12))]
    S.obj("pz_planters", _mesh("pz_planters", lambda bm: [S.bm_box(bm, (x, y, 0.3), (2.0, 2.0, 0.6), 0) for x, y in pts],
                                 [planter]))
    rng = random.Random(p.get("seed2", 9))
    tt = S.tree_templates(rng)
    S.scatter(tt[:6], pts, rng, (0.7, 0.9), prefix="pztree")
    if kiosk:
        kw = S.pbr("pz_kiosk", hexc("d7c9b0"), 0.7, var=0.04)
        aw = S.pbr("pz_awning", hexc("2f6f8f"), 0.7, var=0.02)
        gl = S.glass_mat()
        S.obj("pz_kiosk", _mesh("pz_kiosk", lambda bm: [
            S.bm_box(bm, (sx + 14.0, sy + 3.0, 1.6), (6.0, 4.0, 3.2), 0),
            S.bm_box(bm, (sx + 14.0, sy + 0.6, 2.8), (6.4, 1.6, 0.12), 1),
            S.bm_box(bm, (sx + 14.0, sy + 0.98, 1.4), (4.6, 0.05, 1.6), 2)], [kw, aw, gl]))
    return TW


def _sat_sky(ctx, n_orbits=2, sats_per=2, s=6.0, drift=4.0, arcs=True, aim=None):
    """Satellites on two tilted orbit circles high over the park south of the plaza (stylised: big, ~600 m up), with
    thin teal orbit arcs. Returns list of satellite roots (slowly moving along their orbit)."""
    T = ctx.frames
    sx, sy = SPOT
    out = []
    for o in range(n_orbits):
        c = Vector((sx + (-60 if o == 0 else 90), sy - 1100 - 60 * o, -1600.0))
        Rr = 2250.0 + 40 * o
        yaw = math.radians(-18 if o == 0 else 24)
        u = Vector((math.cos(yaw), math.sin(yaw), 0))
        v = Vector((-0.3 * math.sin(yaw), 0.3 * math.cos(yaw), 0.954)).normalized()
        v = (v - u * v.dot(u)).normalized()
        nrm = u.cross(v)
        if arcs:
            m, _ = L.add_mat("orbit_m%d" % o, TEAL, 1.6)
            ring = _annulus("orbit%d" % o, Rr, 7.0, m, 360, c)
            ring.rotation_euler = Vector((0, 0, 1)).rotation_difference(nrm).to_euler()
            # align ring local X with u (rotation_difference keeps an arbitrary twist; circles are symmetric)
        want = None
        if aim is not None:
            want = aim[o] if o < len(aim) else []
        for k in range(sats_per if want is None else len(want)):
            a0 = math.radians(82 + 16 * k + 7 * o)
            if want is not None:
                # pick the orbit angle whose azimuth (seen from the cafe table, degrees from -Y towards +X) is closest
                best = None
                for i in range(400, 1400):
                    a = math.radians(i / 10.0)
                    q = c + Rr * (math.cos(a) * u + math.sin(a) * v)
                    if q.z < 250:
                        continue
                    az_ = math.degrees(math.atan2(q.x - sx, -(q.y - sy)))
                    el_ = math.degrees(math.atan2(q.z, math.hypot(q.x - sx, q.y - sy)))
                    wa, we = (want[k], None) if not isinstance(want[k], (list, tuple)) else want[k]
                    err = abs(az_ - wa) + (abs(el_ - we) if we is not None else 0.0)
                    if best is None or err < best[0]:
                        best = (err, a)
                a0 = best[1]
            sat = make_gps_sat("sat%d%d" % (o, k), (0, 0, 0), s, yaw=yaw)
            for f in (1, T):
                a = a0 + math.radians(drift) * (f - 1) / max(1, T - 1)
                pos = c + Rr * (math.cos(a) * u + math.sin(a) * v)
                kf(sat, "location", f, pos)
            _interp(sat, "LINEAR")
            out.append(sat)
    return out


def _table_phone(ctx, scr, yaw_deg=180.0, tilt=-14.0, dx=0.0):
    sx, sy = SPOT
    ph = make_phone("phone", scr, (sx + dx, sy - 0.02, TBL_Z + 0.004), (math.radians(tilt), 0, math.radians(yaw_deg)))
    cup = S.pbr("pz_cup", hexc("e9e4da"), 0.3, coat=0.5, var=0)
    S.obj("pz_cup", _mesh("pz_cup", lambda bm: [_cyl(bm, (sx + dx + 0.17, sy + 0.05, TBL_Z + 0.045), 0.04, 0.09, "Z", 20),
                                                _cyl(bm, (sx + dx + 0.17, sy + 0.05, TBL_Z + 0.004), 0.075, 0.008, "Z", 24)],
                          [cup]))
    return ph


def _phone_cam(ctx, p, ph, near=0.42, side=0.05, up=0.0, lens=35, fstop=2.0):
    """Camera north of the table looking south at the phone screen (park + sky behind, DOF)."""
    sx, sy = SPOT
    zc = TBL_Z + 0.08
    _cam_keys2(ctx, [(1, p.get("cam0", (sx + side, sy + near, zc - 0.03 + up)), p.get("tgt0", (sx, sy - 0.02, zc + 0.045))),
                     (1.0, p.get("cam1", (sx + side * 0.6, sy + near * 0.9, zc - 0.03 + up)), p.get("tgt1", (sx, sy - 0.02, zc + 0.045)))],
               lens=p.get("lens", lens), clip=0.02, far=40000.0)
    ctx.cam.data.dof.use_dof = True
    ctx.cam.data.dof.focus_object = ph["screen"]
    ctx.cam.data.dof.aperture_fstop = p.get("fstop", fstop)


def _v_gps(ctx, p, view):
    T = ctx.frames
    TW = _plaza_world(ctx, p)
    sx, sy = SPOT
    dz = (PH_H / 2 - 0.002) + (0.46 - 0.5) * (PH_H - 0.024)
    if view in ("hook", "fix", "outro"):
        scr = _screen_mat("ph_map", [map_img("ed_map_dot")], strength=1.1)
        ph = _table_phone(ctx, scr)
        if view in ("hook", "fix"):
            _phone_cam(ctx, p, ph, side=(0.12 if view == "hook" else -0.12), up=-0.02)
            if view == "fix":
                # teal rings pulse around the dot on the screen; the dot sits at uv (0.5, 0.46)
                pass
                for k in range(3):
                    _rings(ctx, (0, -0.0065, dz), ctx.word_time(p.get("ring_cue", "stays"), 0.6) + k * 26,
                                  color=TEAL, count=2, gap=9, r1=0.022, life=16, rot=(math.radians(90), 0, 0),
                                  name="dring%d" % k, parent=ph["root"])
            S.anchor(ctx, "dot", ph["root"], (0, -0.006, dz))
            S.anchor(ctx, "phone", ph["root"], (0, 0, PH_H))
        else:
            _sat_sky(ctx, s=5.0, aim=[[(-33.0, 27.0), (-14.0, 35.0)], [(-24.0, 21.0)]])
            _cam_keys2(ctx, [(1, p.get("cam0", (sx + 0.05, sy + 0.5, TBL_Z + 0.05)), p.get("tgt0", (sx, sy - 0.02, TBL_Z + 0.15))),
                             (1.0, p.get("cam1", (sx + 3.0, sy + 16.0, 9.0)), p.get("tgt1", (sx - 230.0, sy - 540.0, 470.0)))],
                       lens=p.get("lens", 30), clip=0.02, far=40000.0)
            S.anchor(ctx, "phone", ph["root"], (0, 0, PH_H))
    elif view == "sats":
        sats = _sat_sky(ctx, s=p.get("sat_scale", 9.0), aim=p.get("aim", [[(-33.0, 27.0), (-14.0, 35.0)], [(-24.0, 21.0)]]))
        _table_phone(ctx, _screen_mat("ph_map", [map_img("ed_map_dot")], strength=1.1))
        _cam_keys2(ctx, [(1, p.get("cam0", (sx + 2.0, sy + 3.0, 1.5)), p.get("tgt0", (sx - 280.0, sy - 660.0, 560.0))),
                         (1.0, p.get("cam1", (sx + 2.0, sy + 3.0, 1.5)), p.get("tgt1", (sx - 285.0, sy - 660.0, 585.0)))],
                   lens=p.get("lens", 22), clip=0.1, far=40000.0)
        S.anchor(ctx, "sat", sats[1], (0, 0, 2.0))
    elif view == "timing":
        fb = ctx.word_time(p.get("beam_cue", "signals"), 0.25)
        you = _empty("you", (sx, sy, 1.0))
        m, _ = L.add_mat("beam_m", TEAL, 2.2)
        pm = S.emis("beam_pulse", hexc("bff7ef"), 8.0)
        dirs = [(-0.35, -0.75, 0.9), (0.45, -0.6, 0.8), (-0.1, -0.95, 0.5), (0.7, -0.2, 0.75)]
        for k, d in enumerate(dirs):
            dv = Vector(d).normalized()
            top = Vector((sx, sy, 0.8)) + dv * 1400.0
            _beam("beam%d" % k, (sx, sy, 0.8), tuple(top), 0.45, m)
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=2.2)
            for r in range(3):
                o = S.obj("bp%d_%d" % (k, r), S.mesh_from_bm("bp%d_%d" % (k, r), bm.copy(), [pm]))
                o.visible_shadow = False
                f0 = fb + r * 22 + k * 3
                _mover(ctx, o, tuple(Vector((sx, sy, 0.8)) + dv * 420.0), (sx, sy, 0.9), f0, f0 + 20)
            bm.free()
        _rings(ctx, (sx, sy, 0.3), fb + 20, color=AMBER, count=4, gap=12, r1=9.0, life=26, name="you_r")
        _table_phone(ctx, _screen_mat("ph_map", [map_img("ed_map_dot")], strength=1.1))
        _cam_keys2(ctx, [(1, p.get("cam0", (sx + 70.0, sy + 120.0, 75.0)), p.get("tgt0", (sx - 4.0, sy - 14.0, 0.0))),
                         (1.0, p.get("cam1", (sx + 58.0, sy + 100.0, 64.0)), p.get("tgt1", (sx - 4.0, sy - 14.0, 0.0)))],
                   lens=p.get("lens", 30), clip=0.3, far=40000.0)
        S.anchor(ctx, "you", you, (0, 0, 1.5))
    elif view == "clock":
        ff = ctx.word_time(p.get("fast_cue", "fast"), 0.4)
        ps = Vector((sx - 40.0, sy - 700.0, 620.0))
        sat = make_gps_sat("satc", tuple(ps), 3.2, yaw=math.radians(15))
        kf(sat, "location", 1, ps)
        kf(sat, "location", T, ps + Vector((14.0, 0, 0)))
        _interp(sat, "LINEAR")
        cam0 = ps + Vector((20.0, 46.0, -24.0))
        dirc = (cam0 - ps)
        yawc = math.atan2(-dirc.x, dirc.y)
        cl, mh, hh = make_clock("clk", tuple(ps + Vector((11.0, 10.0, -9.0))), 4.6, rot=(0, 0, yawc + math.pi),
                                face="22303d", ink="eef2f3")
        kf(cl, "location", 1, cl.location.copy())
        kf(cl, "location", T, cl.location + Vector((14.0, 0, 0)))
        _interp(cl, "LINEAR")
        _spin_keys(mh, [(1, 0), (ff, 60), (T, 60 + 360 * 3.0 * (T - ff) / 60.0)])
        _spin_keys(hh, [(1, 100), (ff, 105), (T, 105 + 360 * 0.25 * (T - ff) / 60.0)])
        _rings(ctx, (0, 0, 0), ff, color=AMBER, count=3, gap=10, r1=6.5, life=24, rot=(math.radians(90), 0, 0),
                      name="clkr", parent=cl)
        _cam_keys2(ctx, [(1, p.get("cam0", tuple(cam0)), p.get("tgt0", tuple(ps + Vector((4.0, 0, 1.5))))),
                         (1.0, p.get("cam1", tuple(cam0 + Vector((6.0, -6.0, 0.0)))), p.get("tgt1", tuple(ps + Vector((12.0, 0, 1.5)))))],
                   lens=p.get("lens", 30), clip=0.5, far=40000.0)
        S.anchor(ctx, "clock", cl, (0, -1.0, 0))
        S.anchor(ctx, "sat", sat, (0, 0, 1.5))
    elif view == "drift":
        fd = ctx.word_time(p.get("drift_cue", "drift"), 0.5)
        tm, _ = L.add_mat("true_m", TEAL, 2.5)
        _annulus("true_ring", 9.0, 2.0, tm, 64, (sx, sy, 3.0))
        tdm, _ = L.add_mat("true_disc", TEAL, 0.7)
        _fan("true_disc", (sx, sy), 9.0, 0, 360, tdm, z=2.9, seg=48)
        _rings(ctx, (sx, sy, 0.6), 6, color=TEAL, count=4, gap=22, r1=16.0, life=30, name="true_p")
        te = _empty("true_e", (sx, sy, 1.0))
        dot = _empty("dot", (sx, sy, 14.0))
        blue = S.emis("dot_blue", hexc("1a73e8"), 3.0)
        white = S.emis("dot_white", hexc("ffffff"), 2.0)
        S.obj("dot_c", _mesh("dot_c", lambda bm: _cyl(bm, (0, 0, 0.3), 7.0, 0.6, "Z", 40), [blue]), parent=dot)
        S.obj("dot_w", _mesh("dot_w", lambda bm: _cyl(bm, (0, 0, 0.0), 9.0, 0.6, "Z", 40), [white]), parent=dot)
        hm, _ = L.add_mat("dot_halo", hexc("1a73e8"), 0.6)
        S.obj("dot_h", _mesh("dot_h", lambda bm: _cyl(bm, (0, 0, -0.3), 22.0, 0.2, "Z", 48), [hm]), parent=dot)
        path = [(sx, sy), (sx + 40.0, sy - 70.0), (sx + 95.0, sy - 150.0), (sx + 135.0, sy - 250.0)]
        segs = [(Vector(a), Vector(b)) for a, b in zip(path[:-1], path[1:])]
        tot = sum((b - a).length for a, b in segs)
        am = S.emis("trail_m", AMBER, 3.0)
        n = 26
        for i in range(n + 1):
            dd = tot * i / n
            for a, b in segs:
                ln = (b - a).length
                if dd <= ln + 1e-6:
                    q = a + (b - a) * (dd / ln)
                    break
                dd -= ln
            f = int(fd + (T - 6 - fd) * i / n)
            kf(dot, "location", max(1, f), Vector((q.x, q.y, 14.0)))
            if 0 < i < n:
                o = S.obj("trail%d" % i, _mesh("trail%d" % i, lambda bm, q=q: _cyl(bm, (q.x, q.y, 6.0), 2.2, 0.4, "Z", 16), [am]))
                o.visible_shadow = False
                _show(o, max(2, f))
        _interp(dot, "LINEAR")
        _cam_keys2(ctx, [(1, p.get("cam0", (sx + 40.0, sy + 250.0, 330.0)), p.get("tgt0", (sx + 55.0, sy - 110.0, 0.0))),
                         (1.0, p.get("cam1", (sx + 50.0, sy + 220.0, 300.0)), p.get("tgt1", (sx + 65.0, sy - 120.0, 0.0)))],
                   lens=p.get("lens", 30), clip=1.0, far=40000.0)
        S.anchor(ctx, "true", te, (0, 0, 8.0))
        S.anchor(ctx, "dot", dot, (0, 0, 2.0))


def b_gps_sky_v2(ctx, p):
    """GPS + relativity in the scene_lib_v2_tower city (REUSED world) with a cafe plaza on the explainer plot.
    view hook | sats | timing | clock | drift | fix | outro. hook/fix: phone on a stand on the cafe table, map with the
    blue dot (DOF over the park); sats: looking up at stylised satellites on teal orbit arcs; timing: four teal beams
    with light pulses converge on the table (beam_cue), amber rings; clock: one satellite at altitude with a dial
    whose hands speed up on fast_cue; drift: the blue location dot slides off over the park on drift_cue with an amber
    trail, teal ring on the true spot; outro: pull back + up to the sky. Anchors: dot, phone, sat, you, clock, true."""
    _v_gps(ctx, p, p.get("view", "hook"))


def make_cell_tower(name, x, y, h=32.0, az=128.0):
    """Monopole cell tower: tapered grey pole, triangular head frame, 3 sectors x 3 white panel antennas (sector 0
    faces azimuth `az`, degrees from +X), equipment cabinets + low fence at the base."""
    grey = S.pbr("ct_grey", hexc("9aa2aa"), 0.45, 0.7, var=0.03)
    white = S.pbr("ct_white", hexc("dfe3e6"), 0.5, var=0)
    cab = S.pbr("ct_cab", hexc("c7cbc4"), 0.6, var=0.03)
    gravel = S.pbr("ct_gravel", hexc("8f8a80"), 0.95, var=0.1, var_scale=4.0)

    def b(bm):
        rr = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.65, radius2=0.32, depth=h)
        bmesh.ops.translate(bm, vec=Vector((x, y, h / 2)), verts=rr["verts"])
        for k in range(3):
            a = math.radians(az + 120 * k)
            ca, sa = math.cos(a), math.sin(a)
            for j in (-1, 0, 1):
                px = x + 1.6 * ca - 0.9 * j * sa
                py = y + 1.6 * sa + 0.9 * j * ca
                vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
                for v in vs:
                    v.co = Vector((v.co.x * 0.18, v.co.y * 0.45, v.co.z * 2.2))
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "Z"))
                bmesh.ops.translate(bm, verts=vs, vec=Vector((px, py, h - 1.6)))
                for f in {f for v in vs for f in v.link_faces}:
                    f.material_index = 1
            S.bm_box(bm, (x + 0.9 * ca, y + 0.9 * sa, h - 0.4), (0.12, 0.12, 0.12), 0)
        for k in range(3):
            a0 = math.radians(az + 60 + 120 * k)
            a1 = math.radians(az + 180 + 120 * k)
            p0 = Vector((x + 1.85 * math.cos(a0), y + 1.85 * math.sin(a0), h - 0.3))
            p1 = Vector((x + 1.85 * math.cos(a1), y + 1.85 * math.sin(a1), h - 0.3))
            d = p1 - p0
            rr = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.08, radius2=0.08, depth=d.length)
            bmesh.ops.rotate(bm, verts=rr["verts"], cent=(0, 0, 0), matrix=Vector((0, 0, 1)).rotation_difference(d).to_matrix())
            bmesh.ops.translate(bm, verts=rr["verts"], vec=(p0 + p1) / 2)
        for dx, dy in ((2.5, 1.0), (2.5, -1.0)):
            S.bm_box(bm, (x + dx, y + dy, 0.9), (1.2, 1.0, 1.8), 2)
    S.obj(name, _mesh(name, b, [grey, white, cab]))
    S.plane_obj(name + "_pad", 10, 8, (x + 1.0, y, 0.07), gravel)
    S.obj(name + "_fence", _mesh(name + "_fence", lambda bm: [
        S.bm_box(bm, (x + 1.0 + dx, y + dy, 0.9), (sw, sh, 1.8), 0) for dx, dy, sw, sh in (
            (0, 4.0, 10.0, 0.05), (0, -4.0, 10.0, 0.05), (5.0, 0, 0.05, 8.0), (-5.0, 0, 0.05, 8.0))],
        [S.pbr("ct_fence", hexc("7d858c"), 0.5, 0.6, var=0)]))
    return Vector((x, y, h - 1.6))


def make_psap(name, x, y):
    """Low local 911 center: pale two-storey block with window bands, entrance canopy, roof dish + mast, parking with
    a few cars. No signage, no text."""
    fac = S.facade_mat("psap_fac", hexc("d9d2c4"), hexc("3b5268"), 3.0, 3.8, 0.55)
    roof = S.pbr("psap_roof", hexc("8f9398"), 0.8, var=0.05)
    wht = S.pbr("psap_white", hexc("e4e6e8"), 0.45, var=0)
    lot = S.pbr("psap_lot", hexc("55595e"), 0.85, var=0.06)

    def b(bm):
        S.bm_box(bm, (x, y, 3.8), (30.0, 18.0, 7.6), 0)
        S.bm_box(bm, (x, y, 7.75), (30.6, 18.6, 0.3), 1)
        S.bm_box(bm, (x - 6.0, y + 9.6, 3.2), (6.0, 1.8, 0.25), 1)
        _cyl(bm, (x + 8.0, y - 2.0, 9.6), 0.12, 3.6, "Z", 8, 2)
        rr = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.3)
        for v in rr["verts"]:
            v.co.z = max(v.co.z, 0.0) * 0.45
        bmesh.ops.rotate(bm, verts=rr["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-55), 3, "X"))
        bmesh.ops.translate(bm, verts=rr["verts"], vec=Vector((x - 6.0, y - 3.0, 8.9)))
        for f in {f for v in rr["verts"] for f in v.link_faces}:
            f.material_index = 2
        S.bm_box(bm, (x - 6.0, y - 3.0, 8.1), (0.5, 0.5, 0.6), 2)
    S.obj(name, _mesh(name, b, [fac, roof, wht]))
    S.plane_obj(name + "_lot", 34, 16, (x, y + 18.0, 0.06), lot)
    cols = [hexc(c) for c in ("b8bec4", "2c3e57", "8c1c1c", "f2f2f2")]
    for k in range(4):
        L.make_car("%s_car%d" % (name, k), color=cols[k], loc=(x - 10.0 + 6.0 * k, y + 18.0, 0.07), rot_z=math.pi / 2,
                   headlights=False, glow=False)
    return Vector((x, y, 8.0))


def _fan(name, c, r, a0, a1, mat, z=0.5, seg=40):
    bm = bmesh.new()
    vs = [bm.verts.new((c[0], c[1], z))]
    for k in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * k / seg)
        vs.append(bm.verts.new((c[0] + r * math.cos(a), c[1] + r * math.sin(a), z)))
    for k in range(seg):
        bm.faces.new((vs[0], vs[k + 1], vs[k + 2]))
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]))
    o.visible_shadow = False
    return o


def _dispatch_room(ctx, p, dot_frame=None):
    """Own lit 911 dispatch-desk set: blue-grey acoustic walls, carpet, long console desk, three monitors (centre one
    = dark street map; the caller's dot appears on it at dot_frame), a big dark wall map, headset, keyboard, chair,
    plant, window band with daylight on the left. No people, no text."""
    sc = ctx.scene
    w = bpy.data.worlds.new("dc_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.58, 0.62, 1.0)
    bg.inputs["Strength"].default_value = 0.4
    sc.view_settings.exposure = p.get("exposure", -0.5)
    L.fog(0.001, hexc("c9ced4"), start=10.0)
    wall = S.pbr("dc_wall", hexc("6f8796"), 0.9, var=0.03, var_scale=3.0)
    panel = S.pbr("dc_panel", hexc("5d7382"), 0.95, var=0.03)
    ceil = S.pbr("dc_ceil", hexc("dfe2e4"), 0.9, var=0)
    carpet = S.pbr("dc_carpet", hexc("4a5560"), 0.95, var=0.08, var_scale=12.0, bump=0.02)
    desk = S.pbr("dc_desk", hexc("c4a57c"), 0.45, coat=0.2, var=0.06, var_scale=6.0)
    blk = S.pbr("dc_black", hexc("1a1d21"), 0.35, 0.2, coat=0.4, var=0)
    S.plane_obj("dc_floor", 9.0, 8.0, (0, -0.5, 0.0), carpet)

    def room(bm):
        S.bm_box(bm, (0, 2.2, 1.45), (7.0, 0.2, 2.9), 0)
        S.bm_box(bm, (3.4, -0.5, 1.45), (0.2, 5.6, 2.9), 0)
        S.bm_box(bm, (0, -3.2, 1.45), (7.0, 0.2, 2.9), 0)
        for (y0, y1, z0, z1) in ((-3.2, -2.0, 0, 2.9), (1.0, 2.2, 0, 2.9), (-2.0, 1.0, 0, 1.0), (-2.0, 1.0, 2.1, 2.9)):
            S.bm_box(bm, (-3.4, (y0 + y1) / 2, (z0 + z1) / 2), (0.2, y1 - y0, z1 - z0), 0)
        S.bm_box(bm, (0, -0.5, 2.95), (7.0, 5.6, 0.1), 2)
        for k in range(6):
            S.bm_box(bm, (-2.6 + 1.04 * k, 2.09, 0.62), (0.98, 0.03, 0.9), 1)
    S.obj("dc_room", _mesh("dc_room", room, [wall, panel, ceil]))
    sky = S.emis("dc_sky", hexc("cfe3f2"), 1.8)
    S.obj("dc_sky", _mesh("dc_sky", lambda bm: S.bm_box(bm, (-3.55, -0.5, 1.55), (0.02, 3.0, 1.1)), [sky]))
    # big wall map (dark) above the desk
    wm = _screen_mat("dc_wallmap", [map_img("ed_map_wall", dark=True, dot=False, w=512, h=256, scale=0.8)], strength=0.55)
    q = _uv_quad("dc_wallmap", 3.2, 1.6, wm, (0, 0, 0))
    q.location = (0.0, 2.08, 1.9)
    S.obj("dc_wmframe", _mesh("dc_wmframe", lambda bm: S.bm_box(bm, (0, 2.1, 1.9), (3.3, 0.04, 1.7)), [blk]))
    # desk + monitors
    S.obj("dc_desk", _mesh("dc_desk", lambda bm: [
        _rbox(bm, (0, 0.85, 0.74), (3.2, 0.85, 0.04), 0.01, 2, 0),
        S.bm_box(bm, (0, 1.2, 0.37), (3.1, 0.1, 0.72), 1),
        S.bm_box(bm, (-1.5, 0.85, 0.37), (0.06, 0.75, 0.72), 1), S.bm_box(bm, (1.5, 0.85, 0.37), (0.06, 0.75, 0.72), 1)],
        [desk, blk]))
    mon = []
    sa = _cv(256, 160, "18202b")
    for k, (x0, wd, col) in enumerate(((16, 150, "2f6f8f"), (16, 110, "3f8f6f"), (16, 180, "8f6f3f"), (16, 90, "2f6f8f"))):
        _rr(sa, x0, 120 - 26 * k, x0 + wd, 120 - 26 * k + 14, 4, col)
    _rr(sa, 200, 20, 244, 140, 6, "243042")
    side_img = _np_img("ed_dash", sa)
    for k, (x, yaw) in enumerate(((-0.78, 18.0), (0.0, 0.0), (0.78, -18.0))):
        r = _empty("mon%d" % k, (x, 1.02, 1.13))
        r.rotation_euler = (0, 0, math.radians(yaw))
        S.obj("mon%d_b" % k, _mesh("mon%d_b" % k, lambda bm: [_rbox(bm, (0, 0.02, 0), (0.74, 0.03, 0.44), 0.006, 1, 0),
                                                              S.bm_box(bm, (0, 0.06, -0.3), (0.05, 0.04, 0.2), 0),
                                                              S.bm_box(bm, (0, 0.04, -0.385), (0.26, 0.18, 0.02), 0)],
                                   [blk]), parent=r)
        if k == 1:
            # map image is portrait 256x512: use the middle of it by stretching a landscape quad (stylised)
            mm = _screen_mat("mon_map", [map_img("ed_map_mon", dark=True, dot=False, w=512, h=300, scale=0.9)], strength=1.0)
            _uv_quad("mon1_s", 0.7, 0.4, mm, (0, 0.0, 0), parent=r)
        else:
            _uv_quad("mon%d_s" % k, 0.7, 0.4, _screen_mat("mon%d_m" % k, [side_img], strength=0.9), (0, 0.0, 0), parent=r)
        mon.append(r)
    # caller dot on the centre monitor
    dm = S.emis("dc_dot", hexc("19d3c0"), 6.0)
    dot = S.obj("dc_dot", _mesh("dc_dot", lambda bm: _cyl(bm, (0.05, -0.004, 0.02), 0.014, 0.002, "Y", 24), [dm]),
                parent=mon[1])
    if dot_frame:
        _show(dot, dot_frame)
        _rings(ctx, (0.05, -0.006, 0.02), dot_frame, color=TEAL, count=3, gap=10, r1=0.05, life=22,
                      rot=(math.radians(90), 0, 0), name="dcr", parent=mon[1])
    # keyboard, mouse, headset, mug, plant, chair
    grey = S.pbr("dc_grey", hexc("3a3f46"), 0.5, var=0)
    S.obj("dc_kb", _mesh("dc_kb", lambda bm: [_rbox(bm, (0, 0.62, 0.77), (0.46, 0.15, 0.02), 0.005, 1, 0),
                                              _rbox(bm, (0.36, 0.62, 0.77), (0.06, 0.1, 0.025), 0.01, 2, 0)], [grey]))
    hs = S.pbr("dc_headset", hexc("23272c"), 0.4, var=0)
    _annulus("dc_hs_band", 0.085, 0.016, hs, 32, (-0.55, 0.6, 0.79), (math.radians(90), 0, math.radians(30)))
    S.obj("dc_hs_cups", _mesh("dc_hs_cups", lambda bm: [_cyl(bm, (-0.55 + 0.078 * sx_, 0.6 + 0.045 * sx_, 0.79), 0.04, 0.03, "Z", 16)
                                                        for sx_ in (-1, 1)], [hs]))
    mug = S.pbr("dc_mug", hexc("2f6f8f"), 0.35, coat=0.5, var=0)
    S.obj("dc_mug", _mesh("dc_mug", lambda bm: _cyl(bm, (0.9, 0.7, 0.81), 0.04, 0.1, "Z", 20), [mug]))
    pot = S.pbr("lr_pot", hexc("d9774f"), 0.6, var=0.03)
    leaf = S.pbr("lr_leaf", hexc("4f8a45"), 0.6, var=0.08, var_scale=8.0)
    S.obj("dc_pot", _mesh("dc_pot", lambda bm: _cyl(bm, (2.8, 1.6, 0.25), 0.22, 0.5, "Z", 20), [pot]))
    bm = bmesh.new()
    rng = random.Random(3)
    for k in range(14):
        rr = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=rng.uniform(0.15, 0.22))
        bmesh.ops.translate(bm, vec=(2.8 + rng.uniform(-0.2, 0.2), 1.6 + rng.uniform(-0.2, 0.2), 0.8 + rng.uniform(0, 0.8)),
                            verts=rr["verts"])
    S.obj("dc_plant", S.mesh_from_bm("dc_plant", bm, [leaf], smooth=True))
    chair = S.pbr("dc_chair", hexc("2b3440"), 0.8, var=0.03)
    S.obj("dc_chair", _mesh("dc_chair", lambda bm: [_rbox(bm, (0.05, -0.05, 0.5), (0.55, 0.52, 0.09), 0.04, 2, 0),
                                                    _rbox(bm, (0.05, -0.33, 0.9), (0.52, 0.08, 0.62), 0.05, 2, 0),
                                                    _cyl(bm, (0.05, -0.05, 0.25), 0.03, 0.45, "Z", 8, 0),
                                                    _cyl(bm, (0.05, -0.05, 0.05), 0.3, 0.03, "Z", 5, 0)], [chair]))
    for k, (x, y) in enumerate(((-1.2, -0.4), (1.2, -0.4), (0.0, 1.2))):
        A._area("dc_a%d" % k, (x, y, 2.8), 1.4, p.get("ceil_w", 110.0), (1.0, 0.96, 0.9), size_y=1.4)
    win = A._area("dc_win", (-3.0, -0.5, 1.55), 2.0, 140.0, (0.9, 0.95, 1.0), size_y=1.0)
    win.rotation_euler = (0, math.radians(-90), 0)
    return mon, dot


def _v_911(ctx, p, view):
    T = ctx.frames
    sx, sy = SPOT
    if view == "desk":
        fd = ctx.word_time(p.get("dot_cue", "show"), 0.3)
        mon, dot = _dispatch_room(ctx, p, fd)
        _cam_keys2(ctx, [(1, p.get("cam0", (0.55, -0.6, 1.48)), p.get("tgt0", (0.0, 1.02, 1.08))),
                         (1.0, p.get("cam1", (0.45, -0.45, 1.45)), p.get("tgt1", (0.0, 1.02, 1.08)))],
                   lens=p.get("lens", 32), clip=0.02)
        S.anchor(ctx, "map", dot, (0.05, -0.006, 0.02))
        return
    _plaza_world(ctx, p, kiosk=True)
    top = make_cell_tower("cell", CELL[0], CELL[1], az=math.degrees(math.atan2(SPOT[1] - CELL[1], SPOT[0] - CELL[0])))
    roof = make_psap("psap", PSAP[0], PSAP[1])
    te = _empty("tower_top", tuple(top))
    ce = _empty("center_roof", tuple(roof))
    you = _empty("you", (sx, sy, 1.0))
    if view in ("hook", "text"):
        img = [call_img()] if view == "hook" else [chat_img()]
        ph = _table_phone(ctx, _screen_mat("ph_scr", img, strength=1.1))
        _phone_cam(ctx, p, ph, side=(0.12 if view == "hook" else -0.12), up=-0.02)
        S.anchor(ctx, "phone", ph["root"], (0, -0.006, PH_H * 0.85))
        return
    _table_phone(ctx, _screen_mat("ph_scr", [call_img()], strength=1.1))
    az = math.degrees(math.atan2(sy - CELL[1], sx - CELL[0]))
    if view == "route":
        fs = ctx.word_time(p.get("send_cue", "network"), 0.55)
        pm = S.emis("rt_teal", hexc("bff7ef"), 8.0)
        am = S.emis("rt_amber", AMBER, 8.0)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.9)
        for r in range(3):
            o = S.obj("up%d" % r, S.mesh_from_bm("up%d" % r, bm.copy(), [pm]))
            o.visible_shadow = False
            f0 = max(2, fs - 46 + r * 10)
            _mover(ctx, o, (sx, sy, 1.2), tuple(top), f0, f0 + 22)
        # arc tower -> 911 center
        arc = [Vector(top).lerp(Vector(roof), t) + Vector((0, 0, 30.0 * math.sin(math.pi * t))) for t in
               [i / 24.0 for i in range(25)]]
        lm, _ = L.add_mat("rt_line", AMBER, 1.4)
        for i in range(24):
            o = _beam("arc%d" % i, tuple(arc[i]), tuple(arc[i + 1]), 0.25, lm, seg=6)
            _show(o, max(2, fs + i))
        for r in range(3):
            o = S.obj("dn%d" % r, S.mesh_from_bm("dn%d" % r, bm.copy(), [am]))
            o.visible_shadow = False
            for i, q in enumerate(arc):
                kf(o, "location", max(1, fs + r * 12 + i), q)
            _interp(o, "LINEAR")
            _hold_obj(o, "scale", [(1, (0.001,) * 3), (max(2, fs + r * 12), (1.6,) * 3), (fs + r * 12 + 25, (0.001,) * 3)])
        _rings(ctx, tuple(roof + Vector((0, 0, 1.0))), fs + 26, color=AMBER, count=3, gap=10, r1=10.0, life=24,
                      name="psap_r")
        bm.free()
        _cam_keys2(ctx, [(1, p.get("cam0", (sx + 120.0, sy + 85.0, 62.0)), p.get("tgt0", (sx - 5.0, sy - 125.0, 4.0))),
                         (1.0, p.get("cam1", (sx + 110.0, sy + 76.0, 57.0)), p.get("tgt1", (sx - 5.0, sy - 125.0, 4.0)))],
                   lens=p.get("lens", 30), clip=0.5, far=40000.0)
        S.anchor(ctx, "tower", te, (0, 0, 1.5))
        S.anchor(ctx, "center", ce, (0, 0, 2.0))
    else:
        fw = ctx.word_time(p.get("wedge_cue", "side"), 0.4)
        wm, ws = L.add_mat("wedge_m", AMBER, 0.0)
        _fan("wedge", CELL, 230.0, az - 60.0, az + 60.0, wm, z=0.6)
        if view == "sector":
            L.kf_socket(ws, 1, 0.0)
            L.kf_socket(ws, max(2, fw), 0.0)
            L.kf_socket(ws, fw + 12, 0.55)
        elif view == "hybrid":
            ff = ctx.word_time(p.get("fix_cue", "own"), 0.4)
            L.kf_socket(ws, 1, 0.55)
            L.kf_socket(ws, max(2, ff), 0.55)
            L.kf_socket(ws, ff + 15, 0.18)
            cm, cs = L.add_mat("fix_m", TEAL, 0.0)
            _fan("fix", (sx, sy), 14.0, 0, 360, cm, z=0.9, seg=48)
            L.kf_socket(cs, 1, 0.0)
            L.kf_socket(cs, max(2, ff), 0.0)
            L.kf_socket(cs, ff + 10, 1.4)
            _rings(ctx, (sx, sy, 1.0), ff, color=TEAL, count=4, gap=12, r1=14.0, life=24, name="fix_r")
            bmm, _ = L.add_mat("gps_beam", TEAL, 2.0)
            _beam("gpsb", (sx, sy, 0.9), (sx - 300.0, sy - 600.0, 1400.0), 0.35, bmm)
            _rings(ctx, (sx + 14.0, sy + 3.0, 3.4), ff + 18, color=hexc("bff7ef"), count=4, gap=9, r1=6.0, life=22,
                          name="wifi_r")
        else:   # outro
            L.kf_socket(ws, 1, 0.3)
        if view == "outro":
            _cam_keys2(ctx, [(1, p.get("cam0", (sx + 3.0, sy + 18.0, 6.0)), p.get("tgt0", (sx + 20.0, sy - 120.0, 12.0))),
                             (1.0, p.get("cam1", (sx + 90.0, sy + 170.0, 140.0)), p.get("tgt1", (sx + 10.0, sy - 120.0, 0.0)))],
                       lens=p.get("lens", 30), clip=0.3, far=40000.0)
        else:
            _cam_keys2(ctx, [(1, p.get("cam0", (sx + 120.0, sy + 190.0, 230.0)), p.get("tgt0", (sx + 10.0, sy - 90.0, 0.0))),
                             (1.0, p.get("cam1", (sx + 110.0, sy + 172.0, 212.0)), p.get("tgt1", (sx + 10.0, sy - 90.0, 0.0)))],
                       lens=p.get("lens", 30), clip=0.5, far=40000.0)
        mid = Vector(CELL).to_3d() + Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0)) * 120.0
        S.anchor(ctx, "sector", _empty("sector_e", (mid.x, mid.y, 1.0)), (0, 0, 0))
        S.anchor(ctx, "tower", te, (0, 0, 1.5))
        S.anchor(ctx, "you", you, (0, 0, 2.0))


def b_e911_v2(ctx, p):
    """How 911 finds a caller (calm, non-graphic: a phone, a cell tower, a dispatch desk). REUSES the
    scene_lib_v2_tower city + the gps_sky_v2 cafe plaza (+ a kiosk). view hook | route | sector | hybrid | desk |
    text | outro. hook/text: phone on the cafe table (in-call screen / chat bubbles, no text); route: pulses phone ->
    monopole tower -> amber arc to a low 911 center (send_cue); sector: amber 120-degree tower sector fades in
    (wedge_cue); hybrid: teal small circle + rings on the caller, GPS beam, Wi-Fi rings from the kiosk (fix_cue), sector
    dims; desk: dispatch desk set, teal dot appears on the centre monitor map (dot_cue). Anchors: phone, tower, center,
    sector, you, map."""
    _v_911(ctx, p, p.get("view", "hook"))


S.V2_BUILDERS.update({
    "gps_sky_v2": b_gps_sky_v2,
    "e911_v2": b_e911_v2,
    "remote_ir_v2": b_remote_ir_v2,
})


# ======================================================================================================================
# Track A batch 04 (26 Nov 2026, for 30 Nov): cabin_lights_v2, banana_ripen_v2, toll_tag_v2, glove_touch_v2, qr_code_v2
# Cue effects use _hold_* (pops) or _ramp (flat key at the cue, then a fade); no WIREFRAME rings, no CONSTANT keys.
# ======================================================================================================================
def _ramp(keyfn, f, v0, v1, dur=18):
    """Fade v0 -> v1 starting at frame f (a flat key at frame 1 and at f; BEZIER-safe)."""
    f = max(2, int(f))
    keyfn(1, v0)
    keyfn(f, v0)
    keyfn(f + int(dur), v1)


def _ramp_sock(sock, f, v0, v1, dur=18):
    _ramp(lambda fr, v: L.kf_socket(sock, fr, v), f, v0, v1, dur)


def _ramp_attr(idb, path, f, v0, v1, dur=18):
    _ramp(lambda fr, v: kf(idb, path, fr, v), f, v0, v1, dur)


def _em_socks(mat_name):
    m = bpy.data.materials.get(mat_name)
    if m is None:
        return None, None
    for n in m.node_tree.nodes:
        if n.type == "EMISSION":
            return n.inputs["Strength"], n.inputs["Color"]
    return None, None


def _quad(name, c, right, up, w, h, mat, parent=None, uv=True):
    """UV quad centred on c spanning right (u) and up (v) unit vectors."""
    c, r, u = Vector(c), Vector(right).normalized() * (w / 2), Vector(up).normalized() * (h / 2)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("uv")
    vs = [bm.verts.new(c - r - u), bm.verts.new(c + r - u), bm.verts.new(c + r + u), bm.verts.new(c - r + u)]
    f = bm.faces.new(vs)
    for lp, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uvl].uv = t
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def _puffs(ctx, name, src, f0, n=8, gap=5, rise=(0.0, 0.0, 0.6), spread=0.25, r=0.08, life=40, color=TEAL,
           peak=0.6, seed=3, parent=None):
    """Soft gas puffs (translucent emissive spheres) drifting from src from frame f0: grow, drift, fade."""
    rng = random.Random(seed)
    out = []
    for k in range(n):
        m, sock = L.add_mat("%s_m%d" % (name, k), color, 0.0)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r)
        o = S.obj("%s%d" % (name, k), S.mesh_from_bm("%s%d" % (name, k), bm, [m], smooth=True), parent=parent)
        o.visible_shadow = False
        a = max(2, int(f0 + k * gap))
        p0 = Vector(src)
        p1 = p0 + Vector(rise) + Vector((rng.uniform(-spread, spread), rng.uniform(-spread, spread), 0))
        kf(o, "location", 1, p0)
        kf(o, "location", a, p0)
        kf(o, "location", a + life, p1)
        _hold_obj(o, "scale", [(1, (0.001,) * 3), (a, (0.4,) * 3)])
        kf(o, "scale", a + life, Vector((1.6, 1.6, 1.6)))
        L.kf_socket(sock, 1, 0.0)
        L.kf_socket(sock, a, 0.0)
        L.kf_socket(sock, a + int(life * 0.3), peak)
        L.kf_socket(sock, a + life, 0.0)
        out.append(o)
    return out


# ---------------------------------------------------------------- cabin_lights_v2 (REUSES scene_lib_v2_air cabin)
CB_Y0, CB_PITCH, CB_ROWS = -2.0, 0.82, 22
CB_LEN = CB_ROWS * CB_PITCH + 4.0


def _cb_win_y(r):
    return CB_Y0 + 1.5 + r * CB_PITCH


def _cabin_dim(ctx, f_dim, bright=1.0):
    """f_dim None -> dimmed from frame 1; 0 -> stays bright; else fades bright -> dim at f_dim."""
    sets = []
    s, c = _em_socks("cab_ceiling")
    if s is not None:
        sets.append((s, 0.45 * bright, 0.12))
    s, c = _em_socks("cab_led")
    if s is not None:
        c.default_value = hexc("9fb8ff")
        sets.append((s, 2.0 * bright, 0.45))
    s, c = _em_socks("cab_window")
    if s is not None:                         # dusk outside
        c.default_value = hexc("5d74a8")
        s.default_value = 1.6
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("cab_l"):
            sets.append((o.data, 80.0 * bright, 16.0))
        elif o.type == "LIGHT" and o.name.startswith("cab_win"):
            o.data.energy = 70.0
            o.data.color = (0.6, 0.7, 1.0)
    bg = ctx.scene.world.node_tree.nodes.get("Background").inputs["Strength"]
    sets.append((bg, 0.3, 0.14))
    for tgt, vb, vd in sets:
        isl = not hasattr(tgt, "default_value")
        if f_dim is None or f_dim == 0:
            v = vd if f_dim is None else vb
            if isl:
                tgt.energy = v
            else:
                tgt.default_value = v
        elif isl:
            _ramp_attr(tgt, "energy", f_dim, vb, vd, 24)
        else:
            _ramp_sock(tgt, f_dim, vb, vd, 24)


def _cabin_extras(ctx, p, shade_f=None, shade_rows=range(3, 9)):
    """Floor path light strips, exit signs (green panel + white door / arrow pictogram, no text), window shades."""
    path = S.emis("cb_path", hexc("ffd59a"), 2.2)
    bm = bmesh.new()
    y = CB_Y0 + 0.2
    while y < CB_Y0 + CB_LEN - 0.4:
        for sx in (-1, 1):
            S.bm_box(bm, (sx * 0.33, y, 0.012), (0.035, 0.32, 0.012))
        y += 0.5
    S.obj("cb_path", S.mesh_from_bm("cb_path", bm, [path]))
    grn = S.emis("cb_exit_g", hexc("1fd46a"), 3.5)
    wht = S.emis("cb_exit_w", hexc("f4fff6"), 3.5)
    ye = CB_Y0 + CB_LEN - 0.02

    def sign(bm):
        S.bm_box(bm, (0, ye, 1.9), (1.0, 0.04, 0.4), 0)
        S.bm_box(bm, (-0.24, ye - 0.025, 1.9), (0.14, 0.01, 0.26), 1)           # door
        S.bm_box(bm, (0.12, ye - 0.025, 1.9), (0.32, 0.01, 0.06), 1)            # arrow shaft
        for k in range(4):
            S.bm_box(bm, (0.26 + 0.024 * k, ye - 0.025, 1.9 + 0.024 * (3 - k) - 0.036), (0.024, 0.01, 0.024), 1)
            S.bm_box(bm, (0.26 + 0.024 * k, ye - 0.025, 1.9 - 0.024 * (3 - k) + 0.036), (0.024, 0.01, 0.024), 1)
    ex = S.obj("cb_exit", _mesh("cb_exit", sign, [grn, wht]))
    shm = S.pbr("cb_shade", hexc("e6e2da"), 0.6, var=0.01)
    shades = {}
    for r in range(CB_ROWS + 2):
        for sx in (-1, 1):
            y = _cb_win_y(r)
            o = S.obj("cb_sh%d_%d" % (r, sx), _mesh("cb_sh", lambda bm: S.bm_box(bm, (0, 0, -0.26), (0.012, 0.36, 0.52)),
                                                    [shm]), (sx * 1.925, y, 1.34))
            shades[(r, sx)] = o
            if shade_f is not None and sx == -1 and r in shade_rows:
                f = int(shade_f + (r - shade_rows[0]) * 3)
                _ramp_attr(o, "scale", f, Vector((1, 1, 1)), Vector((1, 1, 0.04)), 10)
            else:
                o.scale = (1, 1, 0.04)
    return ex, shades


def _v_cabin(ctx, p, view):
    pp = dict(p)
    pp.setdefault("exposure", -0.25)
    A.b_cabin_v2(ctx, pp)
    f_dim = 0
    if view in ("hook", "dim"):
        f_dim = ctx.word_time(p.get("dim_cue", "dim"), 0.4)
    else:
        f_dim = None
    _cabin_dim(ctx, f_dim)
    shade_f = ctx.word_time(p.get("shade_cue", "shades"), 0.3) if view == "shades" else None
    ex, shades = _cabin_extras(ctx, p, shade_f)
    y0 = CB_Y0
    cams = {
        "hook": ((0.0, y0 + 0.5, 1.2), (0.0, y0 + 9.0, 1.2), (0.0, y0 + 2.0, 1.18), (0.0, y0 + 9.5, 1.2), 18),
        "dim": ((0.35, y0 + 1.2, 1.15), (-0.1, y0 + 9.0, 1.15), (0.3, y0 + 2.2, 1.13), (-0.1, y0 + 9.5, 1.15), 20),
        "path": ((0.12, y0 + 0.8, 0.32), (0.0, y0 + 12.0, 0.75), (0.1, y0 + 2.6, 0.3), (0.0, y0 + 13.0, 0.75), 20),
        "shades": ((-0.75, y0 + 3.2, 1.62), (-1.95, y0 + 5.6, 1.12), (-0.78, y0 + 3.35, 1.61), (-1.95, y0 + 5.6, 1.12), 24),
        "twist": ((0.0, y0 + 0.6, 1.0), (0.0, y0 + 14.0, 1.25), (0.0, y0 + 3.0, 0.98), (0.0, y0 + 14.5, 1.25), 20),
        "outro": ((0.5, y0 + 2.6, 1.25), (-0.9, y0 + 10.0, 1.15), (0.2, y0 + 1.2, 1.3), (-0.4, y0 + 10.0, 1.2), 19),
    }
    c0, t0, c1, t1, lens = cams[view]
    _cam_keys2(ctx, [(1, p.get("cam0", c0), p.get("tgt0", t0)), (1.0, p.get("cam1", c1), p.get("tgt1", t1))],
               lens=p.get("lens", lens), clip=0.05, far=200.0)
    S.anchor(ctx, "aisle", _empty("cb_aisle", (0.0, y0 + 7.5, 1.0)), (0, 0, 0))
    S.anchor(ctx, "floor", _empty("cb_floor_a", (0.33, y0 + 6.0, 0.02)), (0, 0, 0))
    S.anchor(ctx, "exit", ex, (0, CB_Y0 + CB_LEN - 0.05, 1.9))
    S.anchor(ctx, "shade", shades[(4, -1)], (0, 0, -0.12))


def b_cabin_lights_v2(ctx, p):
    """Why the cabin lights dim for landing. REUSES scene_lib_v2_air b_cabin_v2 (then re-lit in memory: dusk windows,
    dimmable ceiling / LED cove / area lights, floor path light strips, green exit sign pictogram, window shades).
    view hook | dim | path | shades | twist | outro. hook/dim: lights fade on dim_cue; shades: left-side shades slide up
    row by row on shade_cue. Anchors: aisle, floor, exit, shade. Params cam0/1, tgt0/1, lens, exposure."""
    _v_cabin(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- banana_ripen_v2
BN_GREEN, BN_YELLOW = hexc("6f9a2e"), hexc("f2cc3a")


def _peel_mat(name, fac=0.0, keys=None):
    """Banana peel: green -> yellow mix (fac 0 green, 1 yellow; keys = (frame, v0, v1, dur) ramp)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs[6].default_value = BN_GREEN
    mx.inputs[7].default_value = BN_YELLOW
    mx.inputs[0].default_value = fac
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 60.0
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 0.12
    nt.links.new(mx.outputs[2], mul.inputs[6])
    nt.links.new(nz.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    if keys:
        _ramp_sock(mx.inputs[0], *keys)
    return m


def _banana_hand_mesh(name, mats, n=6, seed=1):
    """One 'hand' of bananas (n curved fingers fanned from a crown), crown at the origin, fingers along +X curving
    up (+Z). mats = [peel, tip, crown]."""
    rng = random.Random(seed)
    bm = bmesh.new()
    sides, rings_n = 8, 16
    for k in range(n):
        row = k % 2
        yaw = math.radians(-32 + 64 * k / max(1, n - 1) + rng.uniform(-3, 3))
        R, th = 0.15 + rng.uniform(-0.01, 0.01), 1.05 + rng.uniform(-0.05, 0.05)
        rings = []
        for i in range(rings_n + 1):
            t = i / rings_n
            a = th * t
            c = Vector((R * math.sin(a), 0, R * (1 - math.cos(a)) + row * 0.022))
            T_ = Vector((math.cos(a), 0, math.sin(a)))
            N_ = Vector((-math.sin(a), 0, math.cos(a)))
            rad = 0.0165 * min(1.0, 0.35 + t / 0.25, (1.0 - t) / 0.3 + 0.12)
            ring = []
            for j in range(sides):
                ph = 2 * math.pi * j / sides
                q = c + rad * (math.cos(ph) * N_ + math.sin(ph) * Vector((0, 1, 0)))
                q = Matrix.Rotation(yaw, 3, "Z") @ q
                ring.append(bm.verts.new(q))
            rings.append(ring)
        for i in range(rings_n):
            for j in range(sides):
                f = bm.faces.new((rings[i][j], rings[i][(j + 1) % sides], rings[i + 1][(j + 1) % sides], rings[i + 1][j]))
                f.material_index = 0
        f = bm.faces.new(list(reversed(rings[0])))
        f.material_index = 2
        f = bm.faces.new(rings[-1])
        f.material_index = 1
    _rbox(bm, (-0.012, 0, 0.012), (0.04, 0.09, 0.04), 0.01, 1, 2)
    return S.mesh_from_bm(name, bm, mats, smooth=True)


def _bn_mats(name, fac=0.0, keys=None):
    return [_peel_mat(name, fac, keys), S.pbr("bn_tip", hexc("3b2a1c"), 0.6, var=0),
            S.pbr("bn_crown", hexc("7a8a3a"), 0.7, var=0.05)]


def _bn_place(me, name, loc, yaw=0.0, tilt=0.0, s=1.0):
    o = S.obj(name, me, loc, (tilt, 0, yaw), (s, s, s))
    return o


def _bn_box(bm, c, open_=True):
    """Banana carton (kraft, darker band, no print). Open top = no lid face."""
    x, y, z = c
    S.bm_box(bm, (x, y, z + 0.005), (0.5, 0.4, 0.01), 0)
    for sx in (-1, 1):
        S.bm_box(bm, (x + sx * 0.245, y, z + 0.12), (0.01, 0.4, 0.24), 0)
        S.bm_box(bm, (x, y + sx * 0.195, z + 0.12), (0.5, 0.01, 0.24), 0)
    S.bm_box(bm, (x, y - 0.201, z + 0.17), (0.5, 0.004, 0.05), 1)
    if not open_:
        S.bm_box(bm, (x, y, z + 0.245), (0.52, 0.42, 0.012), 0)


def _bn_stacks(ctx, name, origins, layers=6, open_top=True, me=None, fill_open=True, rng=None):
    """Pallet stacks of cartons (2 x 2 per layer). Top layer open with banana hands inside."""
    rng = rng or random.Random(4)
    kraft = S.pbr("bn_kraft", hexc("b9925f"), 0.85, var=0.08, var_scale=4.0)
    band = S.pbr("bn_band", hexc("8a5a2b"), 0.8, var=0.04)
    wood = S.pbr("bn_pallet", hexc("a07c52"), 0.8, var=0.1, var_scale=3.0)
    bm = bmesh.new()
    tops = []
    for (ox, oy) in origins:
        for k in range(3):
            S.bm_box(bm, (ox, oy - 0.5 + 0.5 * k, 0.07), (1.0, 0.1, 0.14), 2)
        S.bm_box(bm, (ox, oy, 0.145), (1.02, 1.2, 0.02), 2)
        for L_ in range(layers):
            for i in (-1, 1):
                for j in (-1, 1):
                    c = (ox + i * 0.255, oy + j * 0.3, 0.155 + L_ * 0.255)
                    top = L_ == layers - 1
                    _bn_box(bm, c, open_=top and open_top)
                    if top and open_top:
                        tops.append(c)
    o = S.obj(name, S.mesh_from_bm(name, bm, [kraft, band, wood]))
    if me is not None and fill_open:
        for k, (x, y, z) in enumerate(tops):
            for m_ in range(2):
                _bn_place(me, "%s_h%d_%d" % (name, k, m_), (x - 0.1 + 0.02 * m_, y - 0.07 + 0.12 * m_, z + 0.06),
                          math.radians(rng.uniform(-15, 15)), math.radians(-8), 0.95)
    return o, tops


def _bn_room(ctx, p, kind="room"):
    """kind 'ship': refrigerated container interior (ribbed walls, cool blue-white light, T-floor);
    'room': ripening room (insulated panel walls, epoxy floor, air duct + fans, gas nozzle). Lit sets, no void."""
    sc = ctx.scene
    w = bpy.data.worlds.new("bn_world")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.7, 0.76, 0.82, 1.0) if kind == "ship" else (0.78, 0.76, 0.72, 1.0)
    bg.inputs["Strength"].default_value = 0.35
    sc.view_settings.exposure = p.get("exposure", -0.4)
    if kind == "ship":
        W, H, D = 2.35, 2.55, 12.0
        L.fog(0.01, hexc("cfe0ee"), start=2.0)
        wall = S.pbr("bn_cwall", hexc("c9d3dc"), 0.45, 0.6, var=0.03)
        floor = S.pbr("bn_tfloor", hexc("9aa2aa"), 0.45, 0.7, var=0.04)

        def room(bm):
            S.bm_box(bm, (0, D / 2 - 0.8, -0.05), (W + 0.4, D + 2.0, 0.1), 1)
            S.bm_box(bm, (0, D / 2 - 0.8, H + 0.05), (W + 0.4, D + 2.0, 0.1), 0)
            S.bm_box(bm, (0, D + 0.05, H / 2), (W + 0.4, 0.1, H), 0)
            S.bm_box(bm, (0, -1.6, H / 2), (W + 0.4, 0.1, H), 0)
            for sx in (-1, 1):
                S.bm_box(bm, (sx * (W / 2 + 0.05), D / 2 - 0.8, H / 2), (0.1, D + 2.0, H), 0)
                y = -1.6
                while y < D:
                    S.bm_box(bm, (sx * (W / 2 - 0.01), y, H / 2), (0.03, 0.07, H), 0)
                    y += 0.14
            for x in range(-5, 6):
                S.bm_box(bm, (x * 0.2, D / 2, 0.01), (0.04, D, 0.02), 1)
        S.obj("bn_container", _mesh("bn_container", room, [wall, floor]))
        for k in range(4):
            A._area("bn_cl%d" % k, (0, 1.0 + k * 3.0, H - 0.1), 0.6, 140.0, (0.8, 0.9, 1.0), size_y=2.0)
        return {"W": W, "H": H, "D": D}
    W, H, D = 8.0, 4.6, 10.0
    L.fog(0.004, hexc("e2ddd2"), start=4.0)
    panel = S.pbr("bn_panel", hexc("d9dcd8"), 0.6, var=0.02)
    seam = S.pbr("bn_seam", hexc("aab0b2"), 0.5, var=0)
    floor = S.pbr("bn_epoxy", hexc("8e969c"), 0.35, coat=0.3, var=0.05, var_scale=1.0)
    duct = S.pbr("bn_duct", hexc("7d868e"), 0.4, 0.6, var=0.02)
    door = S.pbr("bn_door", hexc("2f6f8f"), 0.5, var=0.02)

    def room(bm):
        S.bm_box(bm, (0, D / 2 - 0.8, -0.05), (W + 0.4, D + 2.0, 0.1), 2)
        S.bm_box(bm, (0, D / 2 - 0.8, H + 0.05), (W + 0.4, D + 2.0, 0.1), 0)
        S.bm_box(bm, (0, D + 0.05, H / 2), (W + 0.4, 0.1, H), 0)
        S.bm_box(bm, (0, -1.6, H / 2), (W + 0.4, 0.1, H), 0)
        for sx in (-1, 1):
            S.bm_box(bm, (sx * (W / 2 + 0.05), D / 2 - 0.8, H / 2), (0.1, D + 2.0, H), 0)
            for k in range(9):
                S.bm_box(bm, (sx * (W / 2 - 0.004), k * 1.2, H / 2), (0.01, 0.02, H), 1)
        for k in range(-3, 4):
            S.bm_box(bm, (k * 1.2, D - 0.004, H / 2), (0.02, 0.01, H), 1)
        S.bm_box(bm, (0, D - 0.02, 1.6), (3.0, 0.04, 3.2), 4)                     # roll door
        for k in range(10):
            S.bm_box(bm, (0, D - 0.045, 0.2 + k * 0.32), (3.0, 0.01, 0.03), 1)
        S.bm_box(bm, (0, D / 2, H - 0.45), (1.0, D - 0.4, 0.6), 3)              # air duct
        for k in range(4):
            _cyl(bm, (0, 1.2 + k * 2.3, H - 0.78), 0.32, 0.06, "Z", 24, 1)
    S.obj("bn_rroom", _mesh("bn_rroom", room, [panel, seam, floor, duct, door]))
    pan = S.emis("bn_lamp", hexc("fff4e0"), 3.0)
    S.obj("bn_lamps", _mesh("bn_lamps", lambda bm: [S.bm_box(bm, (sx * 2.4, 1.5 + 2.5 * k, H - 0.03), (0.3, 1.4, 0.04))
                                                    for sx in (-1, 1) for k in range(4)], [pan]))
    for k in range(4):
        A._area("bn_rl%d" % k, (0, 1.2 + k * 2.6, H - 0.15), 2.5, 420.0, (1.0, 0.95, 0.88), size_y=2.0)
    # ethylene nozzle box on the right wall
    noz = S.pbr("bn_noz", hexc("e8ecee"), 0.4, var=0)
    S.obj("bn_noz", _mesh("bn_noz", lambda bm: [S.bm_box(bm, (W / 2 - 0.12, 3.0, 3.2), (0.2, 0.5, 0.4)),
                                                _cyl(bm, (W / 2 - 0.27, 3.0, 3.15), 0.04, 0.12, "X", 12)], [noz]))
    return {"W": W, "H": H, "D": D, "noz": (W / 2 - 0.36, 3.0, 3.15)}


def _bn_store(ctx, p, me):
    """REUSED supermarket set (_store) with a produce display in front of the gondolas: tiered wood bins with yellow
    banana hands, red / green apples, oranges."""
    _store(ctx, p)
    wood = S.pbr("bn_bin", hexc("9a6a3f"), 0.6, var=0.1, var_scale=4.0)
    bm = bmesh.new()
    for t in range(3):
        S.bm_box(bm, (0, 1.6 + t * 0.45, 0.35 + t * 0.25), (3.0, 0.5, 0.7 + t * 0.5), 0)
    S.obj("bn_display", S.mesh_from_bm("bn_display", bm, [wood]))
    rng = random.Random(8)
    k = 0
    for t, y_, xs in ((0, 1.44, range(-6, 7)), (0, 1.66, range(-6, 7)), (1, 1.93, range(-8, 9))):
        for i in xs:
            x = i * 0.14 + (0.07 if y_ == 1.66 else 0.0)
            if t == 0 and abs(x) > 0.92:
                continue
            z = 0.7 + t * 0.5
            _bn_place(me, "bn_disp%d" % k, (x + rng.uniform(-0.02, 0.02), y_, z + 0.02),
                      math.radians(-90 + rng.uniform(-15, 15)), math.radians(rng.uniform(-6, 6)), 1.0)
            k += 1
    fruit = [S.pbr("bn_fr%d" % i, hexc(c), 0.45, coat=0.4, var=0.05) for i, c in enumerate(("c8352d", "8cc04a", "f08a24"))]
    bm = bmesh.new()
    for i in range(160):
        side = -1 if i % 2 else 1
        mi = (i // 2) % 3
        x = side * rng.uniform(1.0, 1.45)
        S._ellipsoid(bm, (x, 1.5 + rng.uniform(-0.15, 0.15), 0.74 + rng.uniform(0, 0.08)), (0.04, 0.04, 0.038), mi, 10, 6)
    for i in range(140):
        S._ellipsoid(bm, (rng.uniform(-1.4, 1.4), 2.5 + rng.uniform(-0.15, 0.15), 1.74 + rng.uniform(0, 0.08)),
                     (0.04, 0.04, 0.038), i % 3, 10, 6)
    S.obj("bn_fruit", S.mesh_from_bm("bn_fruit", bm, fruit, smooth=True))


def _bn_close(ctx, p, me):
    """Close-up: three hands lying on the lid of a closed carton (on a pallet base) at the front of the set, camera
    looking down at about 40 degrees, stacks blurred behind."""
    bm = bmesh.new()
    _bn_box(bm, (0.0, -0.1, 0.62), open_=False)
    S.bm_box(bm, (0.0, -0.1, 0.31), (0.55, 0.45, 0.62), 0)
    S.obj("bn_closebox", S.mesh_from_bm("bn_closebox", bm, [S.pbr("bn_kraft", hexc("b9925f")),
                                                             S.pbr("bn_band", hexc("8a5a2b"))]))
    z = 0.62 + 0.252
    hs = [_bn_place(me, "bn_close%d" % k, (-0.15 + 0.14 * k, -0.02 - 0.05 * (k % 2), z + 0.012),
                    math.radians(-90 + 12 * (k - 1)), 0.0, 1.0) for k in range(3)]
    _cam_keys2(ctx, [(1, p.get("cam0", (0.08, -0.62, 1.22)), p.get("tgt0", (0.0, -0.12, 0.9))),
                     (1.0, p.get("cam1", (0.06, -0.58, 1.19)), p.get("tgt1", (0.0, -0.12, 0.9)))],
               lens=p.get("lens", 35), clip=0.02, far=100.0)
    ctx.cam.data.dof.use_dof = True
    ctx.cam.data.dof.focus_object = hs[1]
    ctx.cam.data.dof.aperture_fstop = p.get("fstop", 4.0)
    S.anchor(ctx, "bunch", hs[1], (0.0, -0.08, 0.06))
    return hs


def _v_banana(ctx, p, view):
    T = ctx.frames
    rng = random.Random(6)
    if view in ("hook", "outro"):
        me = _banana_hand_mesh("bn_hand_y", _bn_mats("bn_peel_y", 0.92))
        _bn_store(ctx, p, me)
        hero = bpy.data.objects["bn_disp8"]
        c0, t0, c1, t1, lens = ((0.5, 0.7, 1.2), (0.25, 1.55, 0.74), (0.46, 0.78, 1.18), (0.25, 1.55, 0.74), 38)
        if view == "outro":
            c0, t0, c1, t1, lens = ((1.3, -0.9, 1.45), (0.0, 2.2, 1.45), (1.8, -1.7, 1.55), (0.0, 2.3, 1.5), 30)
        _cam_keys2(ctx, [(1, p.get("cam0", c0), p.get("tgt0", t0)), (1.0, p.get("cam1", c1), p.get("tgt1", t1))],
                   lens=p.get("lens", lens), clip=0.02, far=200.0)
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_object = hero
        ctx.cam.data.dof.aperture_fstop = p.get("fstop", 2.8 if view == "hook" else 5.6)
        S.anchor(ctx, "bunch", hero, (0, 0, 0.08))
        return
    if view in ("box", "ship"):
        me = _banana_hand_mesh("bn_hand_g", _bn_mats("bn_peel_g", 0.0))
        R = _bn_room(ctx, p, "ship")
        origins = [(sx * 0.55, 1.0 + 1.25 * k) for k in range(8) for sx in (-1, 1)]
        _bn_stacks(ctx, "bn_st", origins, layers=6 if view == "ship" else 4, me=me, rng=rng)
        if view == "box":
            # one open carton at waist height in the aisle-end for the close-up
            hs = _bn_close(ctx, p, me)
        else:
            _cam_keys2(ctx, [(1, p.get("cam0", (0.0, -0.45, 1.9)), p.get("tgt0", (0.0, 7.0, 1.0))),
                             (1.0, p.get("cam1", (0.0, 0.2, 1.85)), p.get("tgt1", (0.0, 7.5, 1.0)))],
                       lens=p.get("lens", 20), clip=0.02, far=100.0)
            S.anchor(ctx, "boxes", _empty("bn_boxes_a", (-0.55, 3.5, 1.4)), (0, 0, 0))
        return
    # ripening room views (room | twist | yellow)
    keys = None
    fac = 0.0
    if view == "yellow":
        keys = (ctx.word_time(p.get("ripen_cue", "yellow"), 0.4) - 20, 0.15, 0.95, 40)
    elif view == "twist":
        fac = 0.45
    me = _banana_hand_mesh("bn_hand_r", _bn_mats("bn_peel_r", fac, keys))
    R = _bn_room(ctx, p, "room")
    origins = [(sx * (1.3 + 1.25 * j), 1.2 + 1.35 * k) for k in range(5) for j in range(2) for sx in (-1, 1)]
    _bn_stacks(ctx, "bn_rst", origins, layers=6, me=me, rng=rng)
    if view == "room":
        fg = ctx.word_time(p.get("gas_cue", "ethylene"), 0.5)
        nz = R["noz"]
        _puffs(ctx, "bn_gas", nz, fg, n=16, gap=4, rise=(-2.4, 0.0, -0.8), spread=0.9, r=0.22, life=55, peak=0.18)
        _cam_keys2(ctx, [(1, p.get("cam0", (-0.6, -0.9, 1.7)), p.get("tgt0", (2.2, 5.0, 2.1))),
                         (1.0, p.get("cam1", (-0.7, -0.6, 1.68)), p.get("tgt1", (2.3, 5.0, 2.1)))],
                   lens=p.get("lens", 20), clip=0.02, far=100.0)
        S.anchor(ctx, "room", _empty("bn_room_a", (0.0, 5.0, 2.0)), (0, 0, 0))
        return
    # close-up: a hand resting on an open carton in front of the stacks
    hs = _bn_close(ctx, p, me)
    if view == "twist":
        fw = ctx.word_time(p.get("wisp_cue", "make"), 0.4)
        for k, h in enumerate(hs):
            _puffs(ctx, "bn_wisp%d" % k, tuple(Vector(h.location) + Vector((0.0, 0.08, 0.06))), fw - 20 + 6 * k, n=6,
                   gap=8, rise=(0, 0.05, 0.22), spread=0.04, r=0.03, life=40, peak=0.8, seed=20 + k)


def b_banana_ripen_v2(ctx, p):
    """Bananas picked green, shipped cool, ripened with ethylene. view hook | box | ship | room | twist | yellow |
    outro. hook/outro: REUSED supermarket set (_store) + produce display; box/ship: refrigerated container with carton
    stacks of green hands; room/twist/yellow: ripening room (insulated panels, duct + fans); room: teal gas puffs
    from the wall nozzle (gas_cue); twist: faint teal wisps rising from the bananas; yellow: peels ramp green ->
    yellow (ripen_cue). Anchors: bunch, boxes, room. Params cam0/1, tgt0/1, lens, fstop, exposure."""
    _v_banana(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- toll_tag_v2 (REUSES the scene_lib_v2_tower city)
TL_GX, TL_RY = -150.0, -60.0           # gantry x, road centre y (road rx at y = -60, lanes all heading +X)
TL_LANES = (-6.6, -2.2, 2.2, 6.6)
TL_V = 26.0                            # m/s (about 58 mph)


def _tl_world(ctx, p):
    import scene_lib_v2_tower as TW
    TW.build_city(ctx, p)
    TW.build_hero(ctx)
    for nm in [o.name for o in bpy.data.objects if o.name.startswith("tc") and o.parent is None
               and abs(o.location.y - TL_RY) < 12]:
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        kids = [c.name for c in o.children_recursive]
        bpy.data.objects.remove(o, do_unlink=True)
        for c in kids:
            if bpy.data.objects.get(c) is not None:
                bpy.data.objects.remove(bpy.data.objects[c], do_unlink=True)
    import scene_lib_v2_city as C
    S.plane_obj("tl_road", 1800.0, 19.0, (0.0, TL_RY, 0.075), C.asphalt_mat("tl_asphalt", hexc("4a4d52")))
    white = S.pbr("tl_line", hexc("eeeeea"), 0.6, var=0)
    bm = bmesh.new()
    for y in (-4.4, 0.0, 4.4):
        x = -900.0
        while x < 900.0:
            S.bm_box(bm, (x, TL_RY + y, 0.085), (3.0, 0.15, 0.01))
            x += 12.0
    for y in (-8.6, 8.6):
        S.bm_box(bm, (0, TL_RY + y, 0.085), (1800.0, 0.18, 0.01))
    S.obj("tl_lines", S.mesh_from_bm("tl_lines", bm, [white]))
    # gantry: two posts + a box truss across the road; readers (white panels) + plate cameras over every lane
    steel = S.pbr("tl_steel", hexc("aeb4ba"), 0.4, 0.8, var=0.03)
    gx = TL_GX

    def gantry(bm):
        for sy in (-1, 1):
            S.bm_box(bm, (gx, TL_RY + sy * 10.6, 3.6), (0.5, 0.5, 7.2), 0)
            S.bm_box(bm, (gx, TL_RY + sy * 10.6, 0.15), (1.2, 1.2, 0.3), 0)
        for z in (6.2, 7.1):
            for dx in (-0.45, 0.45):
                S.bm_box(bm, (gx + dx, TL_RY, z), (0.14, 21.6, 0.14), 0)
        for k in range(15):
            y = TL_RY - 10.2 + k * 1.46
            S.bm_box(bm, (gx, y, 6.65), (0.9, 0.08, 0.08), 0)
            for dx in (-0.45, 0.45):
                S.bm_box(bm, (gx + dx, y, 6.65), (0.08, 0.08, 0.9), 0)
    S.obj("tl_gantry", _mesh("tl_gantry", gantry, [steel]))
    reader = S.pbr("tl_reader", hexc("eef0f2"), 0.4, var=0)
    dark = S.pbr("tl_cam", hexc("23272c"), 0.35, var=0)
    glass = S.pbr("tl_lens", hexc("0d1014"), 0.05, coat=1.0, var=0)
    readers, cams = [], []
    for k, ly in enumerate(TL_LANES):
        r = S.obj("tl_rd%d" % k, _mesh("tl_rd%d" % k, lambda bm: [S.bm_box(bm, (0, 0, 0), (0.12, 0.6, 0.6)),
                                                                   S.bm_box(bm, (0.12, 0, 0.32), (0.3, 0.06, 0.06))],
                                       [reader]), (gx - 0.62, TL_RY + ly, 5.75), (0, math.radians(-28), 0))
        readers.append(r)
        c = S.obj("tl_cm%d" % k, _mesh("tl_cm%d" % k, lambda bm: [S.bm_box(bm, (0, 0, 0), (0.45, 0.2, 0.2), 0),
                                                                   _cyl(bm, (-0.24, 0, 0), 0.06, 0.04, "X", 12, 1),
                                                                   S.bm_box(bm, (0.15, 0, 0.18), (0.08, 0.08, 0.2), 0)],
                                       [dark, glass]), (gx - 0.6, TL_RY + ly + 1.0, 5.95), (0, math.radians(-20), 0))
        cams.append(c)
    cab = S.pbr("tl_cabinet", hexc("9da5ad"), 0.5, 0.3, var=0.02)
    cabinet = S.obj("tl_cabinet", _mesh("tl_cabinet", lambda bm: [
        _rbox(bm, (gx + 4.0, TL_RY - 13.0, 0.85), (1.0, 0.7, 1.7), 0.03, 1),
        S.bm_box(bm, (gx + 2.0, TL_RY - 11.6, 0.05), (4.2, 0.25, 0.1))], [cab]))
    return TW, readers, cams, cabinet


def _tl_car(name, lane, f_at, fps, T, model=None, plate=True):
    """Kenney car on lane, heading +X at TL_V; passes x = TL_GX at frame f_at. Optional front plate."""
    c = L.make_car(name, loc=(0, TL_RY + TL_LANES[lane], 0.08), rot_z=-math.pi / 2, headlights=False, glow=False,
                   model=model)
    o = c.obj
    for f in (1, T):
        kf(o, "location", f, Vector((TL_GX + TL_V * (f - f_at) / fps, TL_RY + TL_LANES[lane], 0.08)))
    _interp(o, "LINEAR")
    pl = None
    if plate:
        pm = S.pbr("tl_plate", hexc("f2f0e6"), 0.5, var=0)
        pl = S.obj(name + "_plate", _mesh(name + "_plate", lambda bm: S.bm_box(bm, (0, 0, 0), (0.32, 0.02, 0.16)), [pm]),
                   (0, 2.05, 0.45), parent=o)
    return o, pl


def _tl_rig(ctx, f_at, sticker=False):
    """Driver's-eye rig moving with the car: dash, A-pillars, roof liner, windshield glass, mirror, toll tag on the
    glass behind the mirror (box transponder, or a flat sticker tag with an antenna-coil print)."""
    fps, T = ctx.fps, ctx.frames
    rig = _empty("tl_rig", (0, 0, 0))
    for f in (1, T):
        kf(rig, "location", f, Vector((TL_GX + TL_V * (f - f_at) / fps, TL_RY + TL_LANES[1], 0.08)))
    _interp(rig, "LINEAR")
    dash = S.pbr("tl_dash", hexc("2b2e33"), 0.7, var=0.03)
    liner = S.pbr("tl_liner", hexc("8c8a84"), 0.9, var=0.03)
    body = S.pbr("tl_hood", hexc("2f6f8f"), 0.3, 0.4, coat=0.8, var=0.01)
    b0, b1 = Vector((1.0, 0, 1.0)), Vector((0.45, 0, 1.42))

    def shell(bm):
        _rbox(bm, (0.95, 0, 0.9), (0.6, 1.5, 0.22), 0.05, 2, 0)                     # dash
        for sy in (-1, 1):                                                         # A-pillars
            vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
            for v in vs:
                v.co = Vector((v.co.x * 0.08, v.co.y * 0.1, v.co.z * 0.68))
            bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.atan2(0.55, 0.42), 3, "Y"))
            bmesh.ops.translate(bm, verts=vs, vec=Vector((0.73, sy * 0.76, 1.21)))
        S.bm_box(bm, (0.0, 0, 1.47), (1.0, 1.6, 0.05), 1)                          # roof liner
        S.bm_box(bm, (2.2, 0, 0.82), (2.2, 1.6, 0.06), 2)                          # hood
        _rbox(bm, (0.5, 0.0, 1.33), (0.04, 0.24, 0.07), 0.015, 2, 0)                # mirror
        S.bm_box(bm, (0.52, 0.0, 1.39), (0.02, 0.02, 0.06), 0)
    S.obj("tl_shell", _mesh("tl_shell", shell, [dash, liner, body]), parent=rig)
    d = (b1 - b0).normalized()
    n = Vector((-0.42, 0, -0.5)).normalized()
    pc = b0 + d * (b1 - b0).length * 0.8 + Vector((0, -0.14, 0)) + n * 0.012
    if sticker:
        img = _sticker_img("tl_sticker_off", False)
        img2 = _sticker_img("tl_sticker_on", True)
        return rig, pc, d, n, (img, img2)
    tm = S.pbr("tl_tagm", hexc("f4f4f0"), 0.45, var=0)
    tg = _quad("tl_tagfoot", pc - n * 0.004, (0, 1, 0), d, 0.1, 0.06, S.pbr("tl_tagfoot", hexc("c9c9c4")), parent=rig)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0), (0.11, 0.075, 0.022))
    tag = S.obj("tl_tag", S.mesh_from_bm("tl_tag", bm, [tm]), pc + n * 0.01, parent=rig)
    tag.rotation_euler = Matrix((Vector((0, 1, 0)), d, n)).transposed().to_euler()
    return rig, tag, d, n, None


def _sticker_img(name, on):
    a = _cv(512, 256, "f3f1ea")
    col = "19d3c0" if on else "8f959b"
    for k in range(6):                       # rectangular antenna coil
        m = 20 + k * 14
        _rr(a, m, m, 512 - m, 256 - m, 6, col)
        _rr(a, m + 5, m + 5, 512 - m - 5, 256 - m - 5, 4, "f3f1ea")
    _rr(a, 236, 108, 276, 148, 4, "ffb000" if on else "3a3f45")
    if on:
        _dsc(a, 256, 128, 70, "19d3c0", 0.25, soft=30)
    return _np_img(name, a)


def _v_toll(ctx, p, view):
    T, fps = ctx.frames, ctx.fps
    TW, readers, cams, cabinet = _tl_world(ctx, p)
    rng = random.Random(5)
    f_mid = int(T * 0.55)
    if view == "read":
        f_mid = ctx.word_time(p.get("ping_cue", "pings"), 0.5) + 4
    elif view == "cams":
        f_mid = ctx.word_time(p.get("flash_cue", "snap"), 0.4) + 2
    elif view == "sticker":
        f_mid = ctx.word_time(p.get("power_cue", "powers"), 0.6) + 2
    elif view == "tag":
        f_mid = int(T * 1.25)
    elif view == "charge":
        f_mid = int(T * 0.2)
    # traffic: hero lane 1 at f_mid, others staggered (lane, offset s)
    hero = None
    for k, (lane, off) in enumerate(((1, 0.0), (0, -1.1), (2, 0.7), (3, -0.4), (0, 1.6), (2, -1.9), (3, 1.3),
                                     (1, -2.6), (1, 2.4), (2, 2.9))):
        if view in ("tag", "sticker") and lane == 1 and off == 0.0:
            continue
        o, pl = _tl_car("tlcar%d" % k, lane, f_mid + int(off * fps), fps, T)
        if off == 0.0:
            hero, hero_pl = o, pl
    if view in ("tag", "sticker"):
        rig, tag, d, n, imgs = _tl_rig(ctx, f_mid, sticker=(view == "sticker"))
        if view == "sticker":
            fp = ctx.word_time(p.get("power_cue", "powers"), 0.6)
            sm = _screen_mat("tl_sticker", list(imgs), [(1, 0.0), (fp, 1.0)], 0.9, gloss=False)
            pc = tag
            tag = _quad("tl_stk", pc, (0, 1, 0), d, 0.085, 0.043, sm, parent=rig)
            _rings(ctx, tuple(pc + n * 0.002), fp, color=TEAL, count=3, gap=8, r1=0.09, life=18, name="tl_pw",
                   parent=rig, rot=tuple(Matrix((Vector((0, 1, 0)), d, n)).transposed().to_euler()))
            tag = _empty("tl_stk_a", tuple(pc), rig)
            cam_l = (p.get("cam0", (0.28, -0.36, 1.27)), p.get("tgt0", (0.56, -0.14, 1.35)))
            cam_l1 = (p.get("cam1", (0.3, -0.34, 1.275)), p.get("tgt1", (0.56, -0.14, 1.35)))
            lens = p.get("lens", 30)
        else:
            cam_l = (p.get("cam0", (0.0, -0.5, 1.18)), p.get("tgt0", (0.62, -0.12, 1.32)))
            cam_l1 = (p.get("cam1", (0.03, -0.48, 1.18)), p.get("tgt1", (0.62, -0.12, 1.32)))
            lens = p.get("lens", 24)
        _cam_keys2(ctx, [(1, cam_l[0], cam_l[1]), (1.0, cam_l1[0], cam_l1[1])], lens=lens, clip=0.01, far=40000.0)
        ctx.cam.parent = rig
        ctx.cam_target.parent = rig
        ctx.cam.data.dof.use_dof = True
        ctx.cam.data.dof.focus_object = tag
        ctx.cam.data.dof.aperture_fstop = p.get("fstop", 4.0 if view == "tag" else 2.8)
        S.anchor(ctx, "tag", tag, (0, 0, 0))
        return
    gx, ry = TL_GX, TL_RY
    rd = readers[1]
    if view == "read":
        fp = f_mid - 4
        cm, cs = L.add_mat("tl_zone_m", TEAL, 0.0)
        bm = bmesh.new()
        rr = bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=1.6, radius2=0.12, depth=5.6)
        bmesh.ops.translate(bm, vec=Vector((0, 0, 2.8)), verts=rr["verts"])
        S.obj("tl_zone", S.mesh_from_bm("tl_zone", bm, [cm]), (gx - 0.9, ry + TL_LANES[1], 0.0)).visible_shadow = False
        _hold_sock(cs, [(1, 0.0), (fp - 6, 0.5), (fp + 16, 0.0)])
        _rings(ctx, (0, 0, 1.45), fp, color=TEAL, count=3, gap=6, r1=1.4, life=14, name="tl_ping", parent=hero)
        am, _ = L.add_mat("tl_ans_m", AMBER, 6.0)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.22)
        ans = S.obj("tl_ans", S.mesh_from_bm("tl_ans", bm, [am], smooth=True))
        p0 = (gx - 0.5, ry + TL_LANES[1], 1.4)
        _mover(ctx, ans, p0, (gx - 0.62, ry + TL_LANES[1], 5.6), fp + 4, fp + 14)
        c0, t0, c1, t1, lens = ((gx - 26.0, ry + 18.0, 14.0), (gx, ry - 3.0, 2.5), (gx - 24.0, ry + 17.0, 13.5), (gx, ry - 3.0, 2.5), 30)
    elif view == "charge":
        fs = ctx.word_time(p.get("send_cue", "matched"), 0.3)
        pm, _ = L.add_mat("tl_cable", TEAL, 0.8)
        _beam("tl_cab1", (gx + 0.3, ry - 10.6, 6.6), (gx + 0.3, ry - 10.6, 0.3), 0.04, pm)
        _beam("tl_cab2", (gx + 0.3, ry - 11.6, 0.12), (gx + 3.5, ry - 11.6, 0.12), 0.04, pm)
        am, _ = L.add_mat("tl_data_m", AMBER, 6.0)
        for k in range(3):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.16)
            s = S.obj("tl_data%d" % k, S.mesh_from_bm("tl_data%d" % k, bm, [am], smooth=True))
            f0 = fs + k * 9
            kf(s, "location", 1, Vector((gx + 0.3, ry - 10.6, 6.6)))
            kf(s, "location", f0, Vector((gx + 0.3, ry - 10.6, 6.6)))
            kf(s, "location", f0 + 10, Vector((gx + 0.3, ry - 10.6, 0.3)))
            kf(s, "location", f0 + 16, Vector((gx + 3.5, ry - 12.6, 1.2)))
            _hold_obj(s, "scale", [(1, (0.001,) * 3), (f0, (1, 1, 1)), (f0 + 17, (0.001,) * 3)])
        _rings(ctx, (gx + 4.0, ry - 13.0, 1.8), fs + 18, color=TEAL, count=3, gap=8, r1=1.6, life=18, name="tl_ok")
        c0, t0, c1, t1, lens = ((gx + 14.0, ry + 10.0, 10.0), (gx + 1.0, ry - 11.0, 1.5), (gx + 13.0, ry + 9.0, 9.6),
                                (gx + 1.0, ry - 11.0, 1.5), 28)
    elif view == "cams":
        ff = f_mid - 2
        cmo = cams[1]
        fm = S.emis("tl_flash_w", hexc("fff3d6"), 0.0)
        fl = S.obj("tl_flash", _mesh("tl_flash", lambda bm: _cyl(bm, (0, 0, 0), 0.09, 0.02, "X", 16), [fm]),
                   (gx - 0.88, ry + TL_LANES[1] + 1.0, 5.86), (0, math.radians(-20), 0))
        es, _ = _em_socks("tl_flash_w")
        _hold_sock(es, [(1, 0.0), (ff, 40.0), (ff + 3, 0.0), (ff + 6, 40.0), (ff + 9, 0.0)])
        _rings(ctx, (0, 2.06, 0.45), ff, color=AMBER, count=3, gap=5, r1=0.7, life=14, name="tl_plate_r",
               parent=hero, rot=(math.radians(90), 0, 0), width=0.06)
        c0, t0, c1, t1, lens = ((gx + 18.0, ry + 14.0, 11.0), (gx - 3.0, ry + TL_LANES[1], 2.0), (gx + 17.0, ry + 13.0, 10.6),
                                (gx - 3.0, ry + TL_LANES[1], 2.0), 30)
        S.anchor(ctx, "cam", cmo, (0, 0, 0))
    else:   # hook | outro
        if view == "hook":
            c0, t0, c1, t1, lens = ((gx - 45.0, ry + 14.0, 4.0), (gx, ry - 6.0, 5.0), (gx - 40.0, ry + 13.0, 4.0), (gx, ry - 6.0, 5.0), 30)
        else:
            c0, t0, c1, t1, lens = ((gx + 30.0, ry + 20.0, 18.0), (gx, ry - 4.0, 2.0), (gx + 80.0, ry + 60.0, 45.0), (gx - 20.0, ry - 20.0, 0.0), 30)
    _cam_keys2(ctx, [(1, p.get("cam0", c0), p.get("tgt0", t0)), (1.0, p.get("cam1", c1), p.get("tgt1", t1))],
               lens=p.get("lens", lens), clip=0.3, far=40000.0)
    S.anchor(ctx, "reader", rd, (0, 0, 0))
    S.anchor(ctx, "cabinet", cabinet, (gx + 4.0, ry - 13.0, 1.8))
    S.anchor(ctx, "gantry", _empty("tl_g_a", (gx, ry, 7.2)), (0, 0, 0))


def b_toll_tag_v2(ctx, p):
    """Electronic toll at highway speed. REUSES the scene_lib_v2_tower city (+ hero tower); the y = -60 avenue becomes
    a 4-lane one-way road (+X) with lane dashes and an overhead gantry at x = -150 (box truss, white reader panels and
    dark plate cameras over every lane, roadside cabinet). view hook | tag | read | charge | sticker | cams | outro.
    tag/sticker: driver's-eye rig moving with the traffic (dash, pillars, mirror, tag behind the mirror; no glass); sticker: flat tag
    with an antenna coil that lights teal on power_cue; read: teal read zone + rings on the hero car (ping_cue), amber
    answer pulse up to the reader; charge: amber data pulses down the gantry to the cabinet (send_cue); cams: flash +
    amber rings on the front plate (flash_cue). Anchors: tag, reader, cabinet, cam, gantry."""
    _v_toll(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- glove_touch_v2 (REUSES the living-room set)
GL_PH = (-0.1, -0.5, 0.44)
GL_TILT = -14.0
GL_TOUCH = (0.006, -PH_T / 2 - 0.0012, 0.088)     # touch point, phone-local


def _home_img(name="ed_home"):
    a = _cv(256, 512, "1f4e6b")
    import numpy as np
    X, Y = _grid(a)
    g = (Y / 512.0)[..., None]
    a[..., :3] = a[..., :3] * (0.7 + 0.5 * g)
    cols = ["ffb000", "19d3c0", "e2584a", "6c8cff", "8fd16a", "f2f2f2", "c58cff", "ff8a3d"]
    k = 0
    for row in range(5):
        for col in range(4):
            x0 = 22 + col * 58
            y0 = 400 - row * 72
            _rr(a, x0, y0, x0 + 40, y0 + 40, 10, cols[k % len(cols)])
            k += 3
    _rr(a, 14, 18, 242, 74, 22, "f2f2f2", 0.25)
    for col in range(4):
        _rr(a, 26 + col * 56, 26, 66 + col * 56, 66, 10, cols[(col * 2 + 1) % len(cols)])
    return _np_img(name, a)


def _hand_mesh(name, mats, pad=0.0, patch=False):
    """Pointing hand, index fingertip at the origin pointing +Y; three curled fingers, thumb, wrist + sweater cuff.
    mats [hand (skin or knit), cuff, tip patch]. pad thickens everything (glove)."""
    bm = bmesh.new()
    rf = 0.0085 + pad
    _cyl(bm, (0, -0.042, 0), rf, 0.066, "Y", 16, 0)
    S._ellipsoid(bm, (0, -0.009, 0), (rf, rf, rf), 2 if patch else 0, 16, 10)
    S._ellipsoid(bm, (0, -0.075, 0), (rf * 1.1, rf * 1.1, rf * 1.1), 0, 16, 10)
    _rbox(bm, (0.026, -0.118, -0.006), (0.078 + 2 * pad, 0.075, 0.03 + 2 * pad), 0.013, 3, 0)
    for k in range(3):
        _rbox(bm, (0.019 + 0.02 * k, -0.077 + 0.003 * k, -0.017), (0.019 + pad, 0.034 + pad, 0.03 + pad), 0.009, 3, 0)
    tv = Vector((0.006, 0.05, -0.006)).normalized()
    for t in range(4):
        q = Vector((-0.019, -0.128, -0.01)) + tv * (0.015 * t)
        S._ellipsoid(bm, tuple(q), (0.0098 + pad,) * 3, 0, 14, 8)
    _cyl(bm, (0.026, -0.205, -0.006), 0.026 + pad, 0.1, "Y", 20, 0)
    _cyl(bm, (0.026, -0.33, -0.006), 0.038, 0.18, "Y", 24, 1)
    return S.mesh_from_bm(name, bm, mats, smooth=True)


def _v_glove(ctx, p, view):
    T = ctx.frames
    _living_room(ctx, p, None, p.get("tv_strength", 0.55))
    hm = _home_img()
    scr = _screen_mat("gl_scr", [hm], strength=p.get("screen", 0.9))
    ph = make_phone("phone", scr, GL_PH, (math.radians(GL_TILT), 0, 0))
    root = ph["root"]
    # sensor grid (teal bars just above the screen)
    gm, gs = L.add_mat("gl_grid_m", TEAL, 0.0)
    sw, sh, sz = PH_W - 0.007, PH_H - 0.024, PH_H / 2 - 0.002
    yg = -PH_T / 2 - 0.0009

    def grid(bm):
        for i in range(10):
            x = -sw / 2 + sw * (i + 0.5) / 10
            S.bm_box(bm, (x, yg, sz), (0.0006, 0.0002, sh))
        for j in range(20):
            z = sz - sh / 2 + sh * (j + 0.5) / 20
            S.bm_box(bm, (0, yg, z), (sw, 0.0002, 0.0006))
    g = S.obj("gl_grid", _mesh("gl_grid", grid, [gm]), parent=root)
    g.visible_shadow = False
    fg = ctx.word_time(p.get("grid_cue", "grid"), 0.4)
    if view == "grid":
        _ramp_sock(gs, fg, 0.0, 2.2, 12)
    elif view in ("touch", "glove", "thread"):
        gs.default_value = 0.7
    tx, ty, tz = GL_TOUCH
    # hand
    bare = view in ("touch",)
    skin = S.pbr("gl_skin", hexc("c48a64"), 0.55, var=0.04, var_scale=20.0)
    knit = S.pbr("gl_knit", hexc("2e4a6e"), 0.95, var=0.12, var_scale=180.0, bump=0.4)
    cuff = S.pbr("gl_cuff", hexc("b5523b"), 0.95, var=0.1, var_scale=120.0, bump=0.3)
    silver = S.pbr("gl_thread", hexc("a9adb2"), 0.45, 0.7, var=0.15, var_scale=400.0, bump=0.5)
    if view != "grid":
        if bare:
            me = _hand_mesh("gl_hand", [skin, cuff, skin], 0.0, False)
        else:
            me = _hand_mesh("gl_hand", [knit, cuff, silver if view == "thread" else knit], 0.0028, view == "thread")
        hand = S.obj("gl_hand", me, parent=root)
        hand.rotation_euler = (math.radians(p.get("hand_pitch", 28.0)), 0, math.radians(p.get("hand_yaw", -22.0)))
        tip = Vector((tx, ty - (0.0028 if not bare else 0.0) - 0.0002, tz))
        away = tip + Vector((0.0, -0.035, -0.012))
        if view in ("hook",):
            ks = [(1, away), (int(T * 0.3), away), (int(T * 0.4), tip), (int(T * 0.5), away), (int(T * 0.6), tip),
                  (int(T * 0.7), tip)]
        elif view == "outro":
            ks = [(1, away), (T, away)]
        else:
            ft = ctx.word_time(p.get("touch_cue", "changes"), 0.5)
            ks = [(1, away), (max(2, ft - 12), away), (ft, tip)]
        for f, v in ks:
            kf(hand, "location", f, v)
        if view in ("touch", "thread"):
            ft = ctx.word_time(p.get("touch_cue", "changes"), 0.5)
            dm, ds = L.add_mat("gl_dot_m", AMBER, 0.0)
            _annulus("gl_dot", 0.0035, 0.007, dm, 32, (tx, ty - 0.0003, tz), (math.radians(90), 0, 0), root)
            _ramp_sock(ds, ft, 0.0, 5.0, 4)
            hm_, hs_ = L.add_mat("gl_hit_m", AMBER, 0.0)
            hb = S.obj("gl_hit", _mesh("gl_hit", lambda bm: [S.bm_box(bm, (tx, yg - 0.0002, sz), (0.0011, 0.0003, sh)),
                                                               S.bm_box(bm, (0, yg - 0.0002, tz), (sw, 0.0003, 0.0011))],
                                       [hm_]), parent=root)
            hb.visible_shadow = False
            _ramp_sock(hs_, ft + 2, 0.0, 4.0, 4)
            _rings(ctx, (tx, ty - 0.0005, tz), ft + 2, color=AMBER, count=3, gap=8, r1=0.03, life=18, name="gl_rg",
                   parent=root, rot=(math.radians(90), 0, 0))
        S.anchor(ctx, "tip", _empty("gl_tip_a", (tx, ty, tz), root), (0, 0, 0))
    S.anchor(ctx, "grid", _empty("gl_grid_a", (-0.018, yg, sz + 0.03), root), (0, 0, 0))
    S.anchor(ctx, "phone", root, (0, 0, PH_H))
    px, py, pz = GL_PH
    cams = {
        "hook": ((px + 0.3, py - 0.42, pz + 0.24), (px + 0.0, py, pz + 0.08), (px + 0.27, py - 0.39, pz + 0.23), (px, py, pz + 0.08), 32),
        "grid": ((px + 0.03, py - 0.3, pz + 0.12), (px, py, pz + 0.075), (px + 0.025, py - 0.27, pz + 0.12), (px, py, pz + 0.075), 40),
        "touch": ((px + 0.2, py - 0.26, pz + 0.16), (px, py, pz + 0.085), (px + 0.18, py - 0.24, pz + 0.155), (px, py, pz + 0.085), 36),
        "outro": ((px + 0.35, py - 0.5, pz + 0.28), (px - 0.05, py, pz + 0.1), (px + 0.5, py - 0.8, pz + 0.4), (px - 0.1, py + 0.4, pz + 0.3), 30),
    }
    c0, t0, c1, t1, lens = cams.get(view, cams["touch"])
    _cam_keys2(ctx, [(1, p.get("cam0", c0), p.get("tgt0", t0)), (1.0, p.get("cam1", c1), p.get("tgt1", t1))],
               lens=p.get("lens", lens), clip=0.005, far=60.0)
    ctx.cam.data.dof.use_dof = True
    ctx.cam.data.dof.focus_object = ph["screen"]
    ctx.cam.data.dof.aperture_fstop = p.get("fstop", 4.0)


def b_glove_touch_v2(ctx, p):
    """Why a phone can't feel a glove. REUSES the living-room set (_living_room); phone on a stand on the coffee table
    (home-screen art: wallpaper + colour app tiles, no text), teal sensor grid just above the screen (ramps up on
    grid_cue), pointing hand (bare skin | knit glove | knit glove with a silver conductive-thread tip) that touches on
    touch_cue; touch/thread: amber dot + crossing grid lines + rings at the touch point. view hook | grid | touch |
    glove | thread | outro. Anchors: tip, grid, phone. Params hand_pitch, hand_yaw, cam0/1, tgt0/1, lens, fstop."""
    _v_glove(ctx, p, p.get("view", "hook"))


# ---------------------------------------------------------------- qr_code_v2 (REUSES the supermarket set)
QR_C = (-14.82, 2.0, 1.5)              # QR centre on the poster (store side wall x = -14.85, facing +X)
QR_S = 0.42                            # QR side (m)
QR_N = 25                              # modules (version 2), quiet zone 2


def _qr_modules(seed=7):
    """Non-decodable QR-like matrix: three finder patterns + separators, timing lines, one alignment pattern,
    random data modules. Returns set of dark (i, j) module coordinates (i = column from left, j = row from top)."""
    rng = random.Random(seed)
    dark = set()
    fixed = set()

    def finder(ci, cj):
        for i in range(-1, 8):
            for j in range(-1, 8):
                ii, jj = ci + i, cj + j
                if 0 <= ii < QR_N and 0 <= jj < QR_N:
                    fixed.add((ii, jj))
                    if 0 <= i <= 6 and 0 <= j <= 6 and (i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4)):
                        dark.add((ii, jj))
    finder(0, 0)
    finder(QR_N - 7, 0)
    finder(0, QR_N - 7)
    for k in range(8, QR_N - 8):
        fixed.add((k, 6))
        fixed.add((6, k))
        if k % 2 == 0:
            dark.add((k, 6))
            dark.add((6, k))
    for i in range(-2, 3):
        for j in range(-2, 3):
            fixed.add((18 + i, 18 + j))
            if max(abs(i), abs(j)) != 1:
                dark.add((18 + i, 18 + j))
    for i in range(QR_N):
        for j in range(QR_N):
            if (i, j) not in fixed and rng.random() < 0.5:
                dark.add((i, j))
    return dark


def _qr_img(name, tint_rows=None, px=16):
    """QR art (no text): navy modules on white; tint_rows (j0, j1) paints those data rows teal (recovery data)."""
    q = QR_N + 4
    a = _cv(q * px, q * px, "ffffff")
    import numpy as np
    dark = _qr_modules()
    for (i, j) in dark:
        x0, y1 = (i + 2) * px, (q - (j + 2)) * px
        col = "1b1f24"
        if tint_rows and tint_rows[0] <= j <= tint_rows[1] and not (i < 8 and j > QR_N - 9):
            col = "0f8f84"
        a[y1 - px:y1, x0:x0 + px, :3] = _rgb(col)
    return _np_img(name, a)


def _qr_cam_img(name, state):
    """Phone camera view of the poster: state 'scan' (amber brackets), 'ok' (teal brackets + check badge),
    'fail' (grey brackets, coral cross badge). No text."""
    a = _cv(256, 512, "e9e3d6")
    _rr(a, 0, 400, 256, 512, 0, "ffb000")
    _rr(a, 0, 0, 256, 90, 0, "2f6f8f")
    _rr(a, 38, 136, 218, 316, 4, "ffffff")
    rng = random.Random(7)
    dark = _qr_modules()
    ps = 6
    for (i, j) in dark:
        x0, y0 = 53 + i * ps, 301 - (j + 1) * ps
        a[y0:y0 + ps, x0:x0 + ps, :3] = _rgb("1b1f24")
    if state in ("ok", "scan", "fail"):
        a[150:210, 140:200, :3] = _rgb("e9dcc0") if state != "scan" else a[150:210, 140:200, :3]
    if state == "fail":
        a[250:300, 50:100, :3] = _rgb("e9dcc0")
    col = {"scan": "ffb000", "ok": "19d3c0", "fail": "9aa0a6"}[state]
    for (x, y, dx, dy) in ((30, 324, 1, -1), (226, 324, -1, -1), (30, 128, 1, 1), (226, 128, -1, 1)):
        _rr(a, min(x, x + dx * 40), min(y, y + dy * 8), max(x, x + dx * 40), max(y, y + dy * 8), 3, col)
        _rr(a, min(x, x + dx * 8), min(y, y + dy * 40), max(x, x + dx * 8), max(y, y + dy * 40), 3, col)
    if state == "ok":
        _dsc(a, 128, 60, 30, "19d3c0")
        for t in range(14):
            _dsc(a, 112 + t, 60 - t * 0.9 if t < 8 else 53 + (t - 8) * 2.2, 3.2, "ffffff")
        for t in range(16):
            _dsc(a, 112 - 6 + t * 0.4, 60 + 6 - t * 0.9, 3.2, "ffffff")
    elif state == "fail":
        _dsc(a, 128, 60, 30, "e2584a")
        for t in range(-12, 13):
            _dsc(a, 128 + t, 60 + t, 3.0, "ffffff")
            _dsc(a, 128 + t, 60 - t, 3.0, "ffffff")
    return _np_img(name, a)


def _qr_patch(name, center, w, h, seed=2, col="e9dcc0", parent=None):
    """Torn paper / sticker patch on the poster plane (faces +X), jagged outline."""
    rng = random.Random(seed)
    bm = bmesh.new()
    n = 22
    c = bm.verts.new((0, 0, 0))
    ring = []
    for k in range(n):
        a = 2 * math.pi * k / n
        rr = 1.0 + rng.uniform(-0.18, 0.12)
        ring.append(bm.verts.new((0, math.cos(a) * w / 2 * rr, math.sin(a) * h / 2 * rr)))
    for k in range(n):
        bm.faces.new((c, ring[k], ring[(k + 1) % n]))
    m = S.pbr("qr_patch_%s" % col, hexc(col), 0.85, var=0.08, var_scale=40.0, bump=0.2)
    o = S.obj(name, S.mesh_from_bm(name, bm, [m]), center, parent=parent)
    return o


def _qr_mod_pos(i, j):
    q = QR_N + 4
    ms = QR_S / q
    return Vector((QR_C[0] + 0.004, QR_C[1] - QR_S / 2 + (i + 2.5) * ms, QR_C[2] + QR_S / 2 - (j + 2.5) * ms))


def _v_qr(ctx, p, view):
    T = ctx.frames
    p2 = dict(p)
    p2.setdefault("exposure", -0.5)
    _store(ctx, p2)
    for k in range(3):
        A._area("qr_key%d" % k, (-12.6, 1.4 + 0.6 * k, 2.6), 1.0, 70.0, (1.0, 0.97, 0.92),
                rot=(0, math.radians(-60), 0))
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    # poster: frame + colour blocks (no text) + QR quad
    px_ = QR_C[0]
    _quad("qr_backing", (px_ - 0.026, 2.0, 1.75), Y, Z, 3.2, 2.6, S.pbr("qr_backing", hexc("5f6f7c"), 0.85, var=0.02))
    pc = S.pbr("qr_frame", hexc("2b2f36"), 0.4, 0.5, var=0)
    S.obj("qr_frame", _mesh("qr_frame", lambda bm: S.bm_box(bm, (px_ - 0.013, 2.0, 1.55), (0.02, 0.78, 1.12)), [pc]))
    blocks = [(2.0, 1.98, 0.72, 0.18, "ffb000"), (2.0, 1.52, 0.72, 0.74, "6f8190"), (2.0, 1.08, 0.72, 0.12, "2f6f8f"),
              (1.75, 1.08, 0.2, 0.06, "19d3c0")]
    for k, (yy, zz, ww, hh, col) in enumerate(blocks):
        _quad("qr_blk%d" % k, (px_ + 0.001 + 0.0005 * (k == 3), yy, zz), Y, Z, ww, hh,
              S.pbr("qr_blk_%s" % col, hexc(col), 0.7, var=0.01))
    S.obj("qr_hdr_dots", _mesh("qr_hdr_dots", lambda bm: [_cyl(bm, (px_ + 0.004, 1.75 + 0.1 * k, 1.98), 0.035, 0.004, "X", 20)
                                                          for k in range(3)], [S.pbr("qr_dot", hexc("1b1f24"), 0.6, var=0)]))
    if view == "data":
        imgs = [_qr_img("qr_plain"), _qr_img("qr_tint", (12, 24))]
        fr = ctx.word_time(p.get("data_cue", "recovery"), 0.5)
        qm = _qr_diffuse("qr_md", imgs, fr)
    else:
        qm = _qr_diffuse("qr_md", [_qr_img("qr_plain")], None)
    qr = _quad("qr_code", (QR_C[0] + 0.003, QR_C[1], QR_C[2]), Y, Z, QR_S, QR_S, qm)
    # damage patch (centre-right data area, clear of the finder squares)
    pcen = _qr_mod_pos(15, 14) + Vector((0.004, 0, 0))
    patch = None
    if view in ("hook", "damage", "level", "corners", "tip", "outro"):
        patch = _qr_patch("qr_patch", tuple(pcen), 0.13, 0.11)
        if view == "damage":
            fd = ctx.word_time(p.get("damage_cue", "tear"), 0.3)
            _hold_obj(patch, "scale", [(1, (0.001,) * 3), (fd, (1, 1, 1))])
    cover = None
    if view == "tip":
        fc = ctx.word_time(p.get("cover_cue", "cover"), 0.3)
        cc = _qr_mod_pos(3, 3) + Vector((0.006, 0, 0))
        cover = _qr_patch("qr_cover", tuple(cc), 0.12, 0.12, seed=5, col="d9c7a0")
        _hold_obj(cover, "scale", [(1, (0.001,) * 3), (fc, (1, 1, 1))])
    if view == "corners":
        ff = ctx.word_time(p.get("finder_cue", "corner"), 0.4)
        for k, (ci, cj) in enumerate(((3, 3), (QR_N - 4, 3), (3, QR_N - 4))):
            fm, fs = L.add_mat("qr_fr_m%d" % k, AMBER, 0.0)
            c = _qr_mod_pos(ci, cj) + Vector((0.003, 0, 0))
            ms = QR_S / (QR_N + 4)
            hw = 4.6 * ms

            def frame(bm, c=c, hw=hw):
                for dy, dz, sy, sz in ((0, hw, 2 * hw + 0.01, 0.01), (0, -hw, 2 * hw + 0.01, 0.01),
                                       (hw, 0, 0.01, 2 * hw), (-hw, 0, 0.01, 2 * hw)):
                    S.bm_box(bm, (c.x, c.y + dy, c.z + dz), (0.002, sy, sz))
            o = S.obj("qr_fr%d" % k, _mesh("qr_fr%d" % k, frame, [fm]))
            o.visible_shadow = False
            _ramp_sock(fs, ff + 5 * k, 0.0, 5.0, 6)
    # phone in the foreground showing the camera view
    states = {"hook": ("scan", "ok", 0.55), "damage": ("scan", "ok", None), "tip": ("ok", "fail", None),
              "outro": ("ok", "ok", None), "level": ("ok", "ok", None), "corners": ("scan", "ok", 0.75),
              "data": ("scan", "ok", 0.8)}
    s0, s1, fr_ = states.get(view, ("scan", "ok", 0.6))
    if view == "damage":
        fsw = ctx.word_time(p.get("scan_cue", "fill"), 0.7)
    elif view == "tip":
        fsw = ctx.word_time(p.get("cover_cue", "cover"), 0.3) + 12
    else:
        fsw = int(T * fr_) if fr_ else 1
    sm = _screen_mat("qr_phone_scr", [_qr_cam_img("qr_cam_%s" % s0, s0), _qr_cam_img("qr_cam_%s2" % s1, s1)],
                     [(1, 0.0), (fsw, 1.0)] if s0 != s1 else None, 1.0)
    ph = make_phone("qr_phone", sm, p.get("phone_loc", (-14.25, 2.16, 1.22)),
                    (math.radians(p.get("phone_tilt", -4.0)), 0, math.radians(90 + p.get("phone_yaw", -8.0))), stand=False)
    if view in ("level",):
        _rings(ctx, tuple(pcen + Vector((0.004, 0, 0))), int(T * 0.35), color=TEAL, count=3, gap=10, r1=0.14, life=20,
               name="qr_lv", rot=(0, math.radians(90), 0))
    cams = {
        "hook": ((-13.15, 2.3, 1.5), (-14.85, 2.02, 1.5), (-13.3, 2.25, 1.5), (-14.85, 2.02, 1.5), 32),
        "data": ((-13.7, 2.08, 1.62), (-14.85, 2.0, 1.6), (-13.78, 2.07, 1.62), (-14.85, 2.0, 1.6), 34),
        "damage": ((-13.55, 2.15, 1.6), (-14.85, 2.03, 1.57), (-13.62, 2.13, 1.6), (-14.85, 2.03, 1.57), 32),
        "level": ((-13.75, 1.95, 1.62), (-14.85, 2.03, 1.58), (-13.82, 1.97, 1.62), (-14.85, 2.03, 1.58), 34),
        "corners": ((-13.7, 2.05, 1.63), (-14.85, 2.0, 1.6), (-13.78, 2.04, 1.63), (-14.85, 2.0, 1.6), 34),
        "tip": ((-13.6, 2.12, 1.62), (-14.85, 2.0, 1.6), (-13.66, 2.1, 1.62), (-14.85, 2.0, 1.6), 32),
        "outro": ((-13.4, 2.3, 1.5), (-14.85, 2.05, 1.5), (-12.4, 3.0, 1.6), (-14.85, 2.2, 1.5), 32),
    }
    c0, t0, c1, t1, lens = cams[view]
    _cam_keys2(ctx, [(1, p.get("cam0", c0), p.get("tgt0", t0)), (1.0, p.get("cam1", c1), p.get("tgt1", t1))],
               lens=p.get("lens", lens), clip=0.02, far=100.0)
    S.anchor(ctx, "code", qr, (0, 0, 0))
    S.anchor(ctx, "patch", cover if cover is not None else (patch or qr), (0, 0, 0))
    S.anchor(ctx, "finder", _empty("qr_finder_a", tuple(_qr_mod_pos(3, 3) + Vector((0, 0, 0.055)))), (0, 0, 0))
    S.anchor(ctx, "phone", ph["root"], (0, 0, PH_H))


def _qr_diffuse(name, imgs, f_mix):
    """Matte printed material from one image or an A -> B keyed image swap (hold keys)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    t0 = _img_node(nt.nodes, imgs[0])
    t0.interpolation = "Closest"
    col = t0.outputs["Color"]
    if len(imgs) > 1:
        t1 = _img_node(nt.nodes, imgs[1])
        t1.interpolation = "Closest"
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(t0.outputs["Color"], mx.inputs[6])
        nt.links.new(t1.outputs["Color"], mx.inputs[7])
        _hold_sock(mx.inputs[0], [(1, 0.0), (f_mix, 1.0)])
        col = mx.outputs[2]
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    return m


def b_qr_code_v2(ctx, p):
    """Why a QR code scans with part missing. REUSES the supermarket set (_store) + a framed poster on the store's
    side wall (colour blocks, QR-like code: three finder squares, timing lines, random non-decodable modules, no
    text) and a phone in the foreground showing its camera view (brackets; scan -> teal check badge, or a coral cross
    when a corner is covered). view hook | data | damage | level | corners | tip | outro. data: lower rows tint teal
    (recovery data, data_cue); damage: torn patch pops on damage_cue, phone succeeds on scan_cue; corners: amber
    frames light around the three finder squares (finder_cue); tip: a second patch covers a finder square
    (cover_cue) and the phone shows the cross. Anchors: code, patch, finder, phone."""
    _v_qr(ctx, p, p.get("view", "hook"))


S.V2_BUILDERS.update({
    "cabin_lights_v2": b_cabin_lights_v2,
    "banana_ripen_v2": b_banana_ripen_v2,
    "toll_tag_v2": b_toll_tag_v2,
    "glove_touch_v2": b_glove_touch_v2,
    "qr_code_v2": b_qr_code_v2,
})

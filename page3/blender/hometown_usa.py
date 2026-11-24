"""Hometown USA (Page 3, Everyday Decoded): W1 town + W3 cut-away house + W2 macro kit in ONE scene. Needs bpy.

Registered with page2/blender/worlds.py by file convention (world id "hometown_usa"):
    build(ctx, state) -> {stop_id: ANC_<stop_id> empty}        (render_oneshot registers them for the 2D tracks)
    apply_events(state, plan, lo, hi)                           (lids, peels, zone visibility, clip planes, rebase)
All numbers (anchors, camera spots, host frames, zones, slices, peels) come from hometown_usa_plan.py, the bpy-free
half that `oneshot.py plan` uses, so plan time and render time agree. WORLDS-SPEC.md is the design source.

Look: v2 bright daylight (scene_lib_v2.daylight: Poly Haven HDRI if present, else physical sky + sun), PBR with
procedural variation, interiors as bright "cut-away museum model" sets (area lights, never dark), no 3D text,
no logos. Everything repeated is a linked duplicate or a Geometry Nodes instance; textures are procedural or the
1K Poly Haven detail maps scene_lib_v2 already uses (cycles texture_limit_render 2048 is set by render_oneshot).

Culling (WORLDS-SPEC 6): a job builds only the zones its frames need (hometown_usa_plan.zones_for_range); the
other exterior districts get a low-poly proxy in Z_FAR_LOD. Small zones (interiors, macro sets, sky) get
per-frame hide_render keys. Parts for quick stills: --parts ground,far,suburb,house_int,... (zone names without
the Z_ prefix, lower case).

UNTESTED (no Blender run yet): see page3/BUILD-LOG.md "Session 2" for what to check on the first still.
"""
import math
import os
import random

import bpy
import bmesh

import mh_blender as B
from mh_blender import S, L, hexc
import hometown_usa_plan as P

SUN_AZ = -30.0       # scene_lib_v2 lamp Z rotation; compass bearing = 180 - SUN_AZ = 210 deg (SSW, WORLDS-SPEC 0)
SUN_ELEV = 40.0
CHARCOAL, TEAL, AMBER, ICE = hexc("1b1f24"), hexc("00b3a4"), hexc("ffb000"), hexc("7fd4ff")
SIDING_COLS = ["f2efe6", "dfe6ea", "e9dcc3", "c9d6c4", "d8d2e0", "f4e3cf"]
CAR_COLS = ["b8bec4", "2c3e57", "8c1c1c", "f2f2f2", "3b4a3a", "c9a44a", "1d1f22"]


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ================================================================ geometry helpers (thin wrappers on S/B)
def box_bm(bm, c, size, mi=0):
    return S.bm_box(bm, tuple(c), tuple(size), mi)


def box(name, c, size, mat, parent=None, rot=(0.0, 0.0, 0.0)):
    bm = bmesh.new()
    S.bm_box(bm, (0.0, 0.0, 0.0), tuple(size), 0)
    o = B.mesh_obj(name, bm, [mat], loc=tuple(c), rot=rot)
    if parent is not None:
        o.parent = parent
    return o


def multi(name, parts, mats, loc=(0.0, 0.0, 0.0), parent=None, smooth_=False):
    """One mesh from many boxes / cylinders: parts = [("box", c, size, mi) | ("cyl", p0, p1, r0, r1, seg, mi)]."""
    bm = bmesh.new()
    for p in parts:
        if p[0] == "box":
            S.bm_box(bm, tuple(p[1]), tuple(p[2]), p[3])
        else:
            B.bm_cyl(bm, tuple(p[1]), tuple(p[2]), p[3], p[4], p[5], p[6])
    o = B.mesh_obj(name, bm, mats, smooth=smooth_, loc=loc)
    if parent is not None:
        o.parent = parent
    return o


def quads(name, rects, z, mat, uv_scale=None):
    """One flat mesh from axis-aligned rects (x0, x1, y0, y1) at height z (ground, roads, lids). UVs in metres
    (or metres / uv_scale) so image/PH materials tile."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for (x0, x1, y0, y1) in rects:
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4:
            continue
        vs = [bm.verts.new((x, y, z)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        f = bm.faces.new(vs)
        for lp, v in zip(f.loops, vs):
            k = uv_scale or 1.0
            lp[uv].uv = (v.co.x / k, v.co.y / k)
    return B.mesh_obj(name, bm, [mat])


def cyl(name, p0, p1, r0, r1, mat, seg=12, parent=None):
    bm = bmesh.new()
    B.bm_cyl(bm, tuple(p0), tuple(p1), r0, r1, seg, 0)
    o = B.mesh_obj(name, bm, [mat], smooth=True)
    if parent is not None:
        o.parent = parent
    return o


def ring_pts(c, radius, axis="z", n=32):
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        u, v = radius * math.cos(a), radius * math.sin(a)
        pts.append((c[0] + u, c[1] + v, c[2]) if axis == "z" else
                   (c[0], c[1] + u, c[2] + v) if axis == "x" else (c[0] + u, c[1], c[2] + v))
    return pts


def rect_pts(cx, cy, z, hx, hy):
    return [(cx - hx, cy - hy, z), (cx + hx, cy - hy, z), (cx + hx, cy + hy, z), (cx - hx, cy + hy, z),
            (cx - hx, cy - hy, z)]


def curve(name, pts, r, mat, parent=None):
    o = B.curve_line(name, pts, r, mat)
    if parent is not None:
        o.parent = parent
    return o


def area_light(name, loc, size, energy, color=(1.0, 0.96, 0.9), rot=(0.0, 0.0, 0.0), size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    if size_y is not None:
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size, size_y
    else:
        ld.size = size
    o = L.link(bpy.data.objects.new(name, ld))
    o.location = tuple(loc)
    o.rotation_euler = tuple(rot)
    try:
        o.visible_camera = False          # fill/softbox lights never show up as bright rectangles in frame
    except Exception:
        pass
    return o


def host_empty(frame):
    """Empty with the host frame's transform (hometown_usa_plan.Frame): children are built in local metres."""
    e = L.link(bpy.data.objects.new("ED_host_" + frame.name, None))
    e.location = frame.origin
    e.rotation_euler = (math.radians(frame.rx), 0.0, math.radians(frame.rz))
    e.empty_display_size = 0.05
    return e


# ================================================================ materials (cached by name in S._MV2 / B._M)
def alpha_mat(name, color, alpha, emit=0.0):
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        p.inputs["Base Color"].default_value = color
        p.inputs["Alpha"].default_value = alpha
        p.inputs["Roughness"].default_value = 0.5
        if emit:
            p.inputs["Emission Color"].default_value = color
            p.inputs["Emission Strength"].default_value = emit
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
        return S._finish(m, p.outputs[0], haze=False)
    return B._cached(name, mk)


def strata_mat():
    """Cross-section strata by world Z (objects at the origin): asphalt 0.1 m, gravel base to 0.4 m, brown soil to
    1.4 m, clay below. Crisp bands (CONSTANT ramp) + grain noise."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("ed_strata")
        vec = S._coord(N, Lk, "Object")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(vec, sep.inputs[0])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = -2.6
        mr.inputs["From Max"].default_value = 0.0
        Lk.new(sep.outputs["Z"], mr.inputs["Value"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.0, hexc("a0714a")          # clay
        els[1].position, els[1].color = 0.9615, hexc("3a3c40")       # asphalt (top 0.1 m)
        for pos, c in ((0.4615, hexc("6b4a30")), (0.846, hexc("8d8a82"))):
            e = els.new(pos)
            e.color = c
        Lk.new(mr.outputs["Result"], ramp.inputs[0])
        fac, _ = S._noise_var(N, Lk, vec, 3.0, 0.18, 6.0)
        Lk.new(S._mul_col(N, Lk, ramp.outputs["Color"], fac), p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.95
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 14.0
        Lk.new(vec, nz.inputs["Vector"])
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.4, 0.02)
        return S._finish(m, p.outputs[0])
    return B._cached("ed_strata", mk)


def barcode_mat():
    """Procedural bars (no digits): sum of 3 sines in object X > threshold, only inside |x| < 16 mm (quiet zones
    white). Valid-looking, arbitrary."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("ed_barcode")
        vec = S._coord(N, Lk, "Object")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(vec, sep.inputs[0])

        def op(kind, a, b=None, v=None):
            n = N.new("ShaderNodeMath")
            n.operation = kind
            Lk.new(a, n.inputs[0])
            if b is not None:
                Lk.new(b, n.inputs[1])
            elif v is not None:
                n.inputs[1].default_value = v
            return n.outputs[0]
        x = sep.outputs["X"]
        s = op("ADD", op("SINE", op("MULTIPLY", x, v=1900.0)), op("MULTIPLY", op("SINE", op("MULTIPLY", x, v=733.0)), v=0.7))
        s = op("ADD", s, op("MULTIPLY", op("SINE", op("MULTIPLY", x, v=271.0)), v=0.5))
        bars = op("MULTIPLY", op("GREATER_THAN", s, v=0.15), op("LESS_THAN", op("ABSOLUTE", x), v=0.016))
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        Lk.new(bars, mix.inputs["Factor"])
        mix.inputs["A"].default_value = hexc("f6f4ee")
        mix.inputs["B"].default_value = hexc("111214")
        Lk.new(mix.outputs["Result"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.6
        return S._finish(m, p.outputs[0], haze=False)
    return B._cached("ed_barcode", mk)


def perforated_mat(pitch=0.0016, name="ed_mw_mesh"):
    """Microwave door mesh: metal sheet with a hole grid of `pitch` (alpha from a sine grid; no texture).
    1.6 mm for the real door, x20 (32 mm) for the enlarged portal interior."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        vec = S._coord(N, Lk, "Object")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(vec, sep.inputs[0])

        def op(kind, a, b=None, v=None):
            n = N.new("ShaderNodeMath")
            n.operation = kind
            Lk.new(a, n.inputs[0])
            if b is not None:
                Lk.new(b, n.inputs[1])
            elif v is not None:
                n.inputs[1].default_value = v
            return n.outputs[0]
        k = 2 * math.pi / pitch
        g = op("MULTIPLY", op("SINE", op("MULTIPLY", sep.outputs["X"], v=k)), op("SINE", op("MULTIPLY", sep.outputs["Z"], v=k)))
        hole = op("GREATER_THAN", g, v=0.35)
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        Lk.new(hole, inv.inputs[1])
        alpha = inv.outputs[0]
        p.inputs["Base Color"].default_value = hexc("2a2c2f")
        p.inputs["Metallic"].default_value = 0.8
        p.inputs["Roughness"].default_value = 0.35
        Lk.new(alpha, p.inputs["Alpha"])
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
        return S._finish(m, p.outputs[0], haze=False)
    return B._cached(name, mk)


class Mats(object):
    """Lazy palette: self.m("asphalt") etc."""
    def __init__(self):
        self._f = {
            "asphalt": lambda: B.mat_ph("ed_asphalt", hexc("4a4c50"), "aerial_asphalt_01", 0.45, 0.85),
            "concrete": lambda: B.mat_ph("ed_concrete", hexc("c9c4ba"), "concrete_floor_02", 0.35, 0.8),
            "lawn": lambda: S.lawn_mat("ed_lawn", hexc("6e8a4c"), stripes=False),
            "lawn_far": lambda: S.pbr("ed_lawn_far", hexc("6a8550"), 0.95, var=0.12, var_scale=0.004),
            "gravel": lambda: S.pbr("ed_gravel", hexc("9a958c"), 0.95, var=0.15, var_scale=3.0, bump=0.3),
            "yellow_line": lambda: S.pbr("ed_yellow_line", hexc("e8b923"), 0.6, var=0.03),
            "white_line": lambda: S.pbr("ed_white_line", hexc("f2f2ee"), 0.6, var=0.03),
            "siding_obj": lambda: B.mat_objcolor("ed_siding_obj", 0.7),
            "siding": lambda: B.mat_bands("ed_siding", hexc("eef0ea"), 0.18, "Z", 0.45, 0.75),
            "shingles": lambda: B.mat_bands("ed_shingles", hexc("5e6268"), 0.2, "Z", 0.35, 0.88, 0.12),
            "trim": lambda: S.pbr("ed_trim", hexc("f5f4f0"), 0.6, var=0.02),
            "window": lambda: S.pbr("ed_window", hexc("2c3d52"), 0.08, var=0.0),
            "glass": lambda: S.glass_mat("ed_glass"),
            "clear_glass": lambda: alpha_mat("ed_clear_glass", (0.92, 0.96, 1.0, 1.0), 0.18),
            "paint": lambda: S.pbr("ed_paint", hexc("f1ede4"), 0.85, var=0.02),
            "paint_warm": lambda: S.pbr("ed_paint_warm", hexc("e9dfcf"), 0.85, var=0.02),
            "wood": lambda: S.pbr("ed_wood", hexc("9b7653"), 0.6, var=0.12, var_scale=8.0),
            "pole_wood": lambda: S.pbr("ed_pole_wood", hexc("6b5440"), 0.85, var=0.12, var_scale=2.0, bump=0.2),
            "galv": lambda: S.pbr("ed_galv", hexc("a8adb2"), 0.4, metal=0.85, var=0.05),
            "steel_dark": lambda: S.pbr("ed_steel_dark", hexc("3a3d40"), 0.45, metal=0.6),
            "white_metal": lambda: S.pbr("ed_white_metal", hexc("eceeef"), 0.35, metal=0.2),
            "grey_box": lambda: S.pbr("ed_grey_box", hexc("9ba1a6"), 0.5, metal=0.3),
            "insulator": lambda: S.pbr("ed_insulator", hexc("7b5a43"), 0.25, coat=0.6),
            "copper": lambda: S.pbr("ed_copper", hexc("c87533"), 0.3, metal=1.0, var=0.04),
            "gold": lambda: S.pbr("ed_gold", hexc("e0b04a"), 0.22, metal=1.0, var=0.03),
            "pcb": lambda: S.pbr("ed_pcb", hexc("1f3b2c"), 0.35, var=0.08, var_scale=200.0, bump=0.05),
            "chip": lambda: S.pbr("ed_chip", hexc("1b1c1e"), 0.45),
            "battery": lambda: S.pbr("ed_battery", hexc("b9bcc0"), 0.3, metal=0.7),
            "phone_metal": lambda: S.pbr("ed_phone_metal", hexc("6f747b"), 0.3, metal=0.9),
            "plastic_gap": lambda: S.pbr("ed_plastic_gap", hexc("2a2b2d"), 0.5),
            "card_pvc": lambda: S.pbr("ed_card_pvc", hexc("23466e"), 0.4, coat=0.5, var=0.02),
            "card_core": lambda: S.pbr("ed_card_core", hexc("e8e4da"), 0.6),
            "wrapper": lambda: S.pbr("ed_wrapper", hexc("3fa37a"), 0.45, var=0.03),
            "rubber": lambda: S.pbr("ed_rubber", hexc("202224"), 0.8),
            "brick": lambda: S.facade_mat("ed_facade_brick", hexc("9a5b45")),
            "stucco": lambda: S.facade_mat("ed_facade_stucco", hexc("e2d6c0")),
            "panel_grey": lambda: S.pbr("ed_panel_grey", hexc("c2c6ca"), 0.6, var=0.03),
            "roof_membrane": lambda: S.pbr("ed_roof_membrane", hexc("d9dcdf"), 0.8, var=0.04),
            "tank_paint": lambda: S.pbr("ed_tank_paint", hexc("cfe3ee"), 0.4, var=0.02),
            "water": lambda: B.mat_water("ed_water"),
            "water_vol": lambda: alpha_mat("ed_water_vol", hexc("4fa3d9"), 0.45),
            "tile": lambda: S.pbr("ed_tile", hexc("e9eaea"), 0.3, var=0.03, var_scale=1.6),
            "leaf": lambda: S.pbr("ed_leaf", hexc("4f7a35"), 0.8, var=0.12, var_scale=1.5),
            "conifer": lambda: S.pbr("ed_conifer", hexc("2f5a35"), 0.85, var=0.1),
            "trunk": lambda: S.pbr("ed_trunk", hexc("5a4632"), 0.9),
            "car_obj": lambda: B.mat_objcolor("ed_car_obj", 0.25),
            "tyre": lambda: S.pbr("ed_tyre", hexc("1c1c1c"), 0.8),
            "orange_duct": lambda: S.pbr("ed_orange_duct", hexc("e5732a"), 0.35),
            "blue_duct": lambda: S.pbr("ed_blue_duct", hexc("2b5fa8"), 0.35),
            "iron_main": lambda: S.pbr("ed_iron_main", hexc("5a6f80"), 0.5, metal=0.4),
            "gas_yellow": lambda: S.pbr("ed_gas_yellow", hexc("e8c21f"), 0.4),
            "pex_red": lambda: S.pbr("ed_pex_red", hexc("c4302b"), 0.35),
            "pex_blue": lambda: S.pbr("ed_pex_blue", hexc("2d6cc0"), 0.35),
            "foam_black": lambda: S.pbr("ed_foam_black", hexc("1e1f21"), 0.85),
            "insulation": lambda: S.pbr("ed_insulation", hexc("e9c46a"), 0.95, var=0.2, var_scale=30.0, bump=0.3),
            "drywall": lambda: S.pbr("ed_drywall", hexc("f2f0ea"), 0.9),
            "stud": lambda: S.pbr("ed_stud", hexc("d2b48c"), 0.8, var=0.08),
            "cap": lambda: S.pbr("ed_cap", CHARCOAL, 0.7),
            "teal_line": lambda: B.mat_glow("ed_teal_line", TEAL, 2.0),
            "teal_glow": lambda: B.mat_glow("ed_teal_glow", TEAL, 4.0),
            "amber_glow": lambda: B.mat_glow("ed_amber_glow", AMBER, 3.0),
            "red_lens_on": lambda: B.mat_glow("ed_red_on", hexc("ff2a1a"), 6.0),
            "green_lens_on": lambda: B.mat_glow("ed_green_on", hexc("21e07a"), 6.0),
            "lens_off": lambda: S.pbr("ed_lens_off", hexc("2b2d2f"), 0.2),
            "led_green": lambda: B.mat_glow("ed_led_green", hexc("37ff7a"), 4.0),
            "led_blue": lambda: B.mat_glow("ed_led_blue", hexc("4aa8ff"), 4.0),
            "laser": lambda: B.mat_glow("ed_laser", hexc("ff2020"), 4.0),
            "ceiling_panel": lambda: B.mat_glow("ed_ceiling_panel", hexc("fbfaf5"), 3.0),
            "screen_tiles": lambda: B.mat_glow("ed_screen", hexc("6fb4d8"), 2.0),
            "tv_screen": lambda: B.mat_glow("ed_tv", hexc("3f9a4a"), 1.5),
            "teal_alpha": lambda: alpha_mat("ed_teal_alpha", TEAL, 0.2, emit=1.5),
            "ice_alpha": lambda: alpha_mat("ed_ice_alpha", ICE, 0.35, emit=2.0),
            "amber_alpha": lambda: alpha_mat("ed_amber_alpha", AMBER, 0.25, emit=1.5),
            "fence": lambda: alpha_mat("ed_fence", hexc("8e9398"), 0.3),
            "cloud": lambda: alpha_mat("ed_cloud", (1.0, 1.0, 1.0, 1.0), 0.85, emit=0.4),
            "strata": strata_mat,
            "barcode": barcode_mat,
            "mw_mesh": perforated_mat,
            "mw_mesh_big": lambda: perforated_mat(0.032, "ed_mw_mesh_x20"),
            "cavity_metal": lambda: S.pbr("ed_cavity_metal", hexc("d9dcdf"), 0.3, metal=0.6, var=0.03, var_scale=0.4),
            "far_grey": lambda: S.pbr("ed_far_grey", hexc("b7b9b6"), 0.9, var=0.05),
        }

    def m(self, key):
        return self._f[key]()


# ================================================================ the world
class Hometown(object):
    def __init__(self, ctx, state):
        self.ctx, self.state = ctx, state
        self.ep = state.get("episode") or {}
        self.plan = state.get("plan")
        self.stop0 = P.first_stop(self.ep) or "suburb_wide"
        fr = state.get("frame_range") or (1, (self.plan or {}).get("frames", 1))
        self.lo, self.hi = int(fr[0]), int(fr[1])
        self.M = Mats()
        self.rng = random.Random(1974)
        self.stats = {}
        self.peels = {}        # group -> [(obj, base_loc, offset)]
        self.lids = {}         # slice -> [(obj, base_loc, offset)]
        self.hosts = {}
        if self.plan:
            a, b = P.beat_range(self.plan, max(1, self.lo - 2), min(self.plan["frames"], self.hi + 2))
            self.zones = P.zones_for_range(self.plan, self.stop0, a, b)
        else:
            self.zones = set(P.ZONES)
        parts = state.get("parts")
        if parts:
            want = set(p.lower() for p in parts)
            self.zones = set(z for z in self.zones if z[2:].lower() in want or z == "Z_FAR_LOD")
            self.only = want
        else:
            self.only = None

    # ------------------------------------------------------------ bookkeeping
    def zone(self, name):
        return B.part_collection(name)

    def peel(self, group, obj, offset):
        self.peels.setdefault(group, []).append((obj, tuple(obj.location), tuple(offset)))

    def lid(self, sid, obj, offset):
        self.lids.setdefault(sid, []).append((obj, tuple(obj.location), tuple(offset)))

    def wants(self, part):
        return self.only is None or part in self.only

    # ------------------------------------------------------------ anchors first (cheap, never skipped)
    def build_anchors(self):
        B.part_collection("anchors")
        for k, s in P.VIEWS.items():          # 37 stops + <stop>__detail / <stop>__alt variant views
            B.anchor_empty(self.ctx, k, tuple(s["anc"]))
            e = B.anchor_empty(self.ctx, k, tuple(s["cam"]), register=False, prefix=B.CAM_PREFIX)
            e["lens"] = float(s["lens"])

    def build_lighting(self):
        L.fog(0.00045, S.HAZE, start=150.0)          # light distance haze (materials read it at creation)
        sun = S.daylight(self.ctx, sun_az=SUN_AZ, sun_elev=SUN_ELEV)
        self.stats["sun"] = "lamp" if sun is not None else "hdri"

    # ------------------------------------------------------------ ground, roads, lids (always: holes are permanent)
    ROADS_H = [(-1000, 1400, -8, 8), (100, 540, 135, 145), (100, 540, 255, 265), (100, 540, 75, 85),
               (100, 540, 195, 205), (100, 540, 325, 335), (100, 540, 395, 405), (-500, -8, 246, 254)]
    ROADS_V = [(-8, 8, -700, 800), (239, 249, -330, 430), (115, 125, 60, 430), (335, 345, 60, 430),
               (435, 445, 60, 430), (515, 525, 60, 430), (-560, -552, -150, -8)]

    def sidewalks(self):
        out = []
        for (x0, x1, y0, y1) in self.ROADS_H:
            if y1 - y0 >= 10:
                out += [(x0, x1, y1 + 1.0, y1 + 2.5), (x0, x1, y0 - 2.5, y0 - 1.0)]
        for (x0, x1, y0, y1) in self.ROADS_V:
            if x1 - x0 >= 10:
                out += [(x1 + 1.0, x1 + 2.5, y0, y1), (x0 - 2.5, x0 - 1.0, y0, y1)]
        return out

    def build_ground(self):
        self.zone("ground")
        M = self.M.m
        river = (-760.0, -700.0, -700.0, 800.0)
        house = (P.HOUSE["x0"], P.HOUSE["x1"], P.HOUSE["y0"], P.HOUSE["y1"])
        holes = list(P.GROUND_HOLES)
        layers = [("lawn", (-1000.0, 1400.0, -700.0, 800.0), 0.0, holes + [river, house]),
                  ("asphalt", None, 0.02, holes), ("concrete", None, 0.04, holes)]
        road_rects = self.ROADS_H + self.ROADS_V + [(-135, -35, -50, -10)]       # + strip mall lot
        walk_rects = self.sidewalks()
        for key, outer, z, hs in layers:
            rects = []
            srcs = [outer] if outer else (road_rects if key == "asphalt" else walk_rects)
            for r in srcs:
                rects += P.rect_minus_holes(r, hs)
            quads("ed_%s" % key, rects, z, M(key), uv_scale=4.0)
        # lids: whatever surface covers each hole, as separate sliding planes
        for sid, sl in P.SLICES.items():
            if "rect" not in sl:
                continue
            hx0, hx1, hy0, hy1 = sl["rect"]
            for key, srcs, z in (("lawn", [(hx0, hx1, hy0, hy1)], 0.003), ("asphalt", road_rects, 0.023),
                                 ("concrete", walk_rects, 0.043)):
                rr = []
                for (x0, x1, y0, y1) in srcs:
                    a, b, c, d = max(x0, hx0), min(x1, hx1), max(y0, hy0), min(y1, hy1)
                    if a < b and c < d:
                        rr.append((a, b, c, d))
                if rr:
                    o = quads("ed_lid_%s_%s" % (sid, key), rr, z, M(key), uv_scale=4.0)
                    self.lid(sid, o, sl["slide"])
        # lane markings: double yellow on 2-way roads, white edge lines (not inside holes)
        marks_y, marks_w = [], []
        for (x0, x1, y0, y1) in self.ROADS_H:
            yc = (y0 + y1) / 2
            marks_y += [(x0, x1, yc + 0.06, yc + 0.16), (x0, x1, yc - 0.16, yc - 0.06)]
            marks_w += [(x0, x1, y0 + 0.3, y0 + 0.45), (x0, x1, y1 - 0.45, y1 - 0.3)]
        for (x0, x1, y0, y1) in self.ROADS_V:
            xc = (x0 + x1) / 2
            marks_y += [(xc + 0.06, xc + 0.16, y0, y1), (xc - 0.16, xc - 0.06, y0, y1)]
            marks_w += [(x0 + 0.3, x0 + 0.45, y0, y1), (x1 - 0.45, x1 - 0.3, y0, y1)]
        inter = [(-9.0, 9.0, -9.0, 9.0)]
        for key, rects in (("yellow_line", marks_y), ("white_line", marks_w)):
            out = []
            for r in rects:
                out += P.rect_minus_holes(r, holes + inter)
            quads("ed_marks_%s" % key, out, 0.026, M(key))
        # crosswalks + stop bars at the main intersection
        cw = []
        for s in (-1, 1):
            for i in range(-7, 8):
                cw.append((i - 0.25, i + 0.25, s * 9.5 - 1.2, s * 9.5 + 1.2))
                cw.append((s * 9.5 - 1.2, s * 9.5 + 1.2, i - 0.25, i + 0.25))
        cw += [(0.2, 8.0, -11.4, -11.0), (-8.0, -0.2, 11.0, 11.4), (11.0, 11.4, 0.2, 8.0), (-11.4, -11.0, -8.0, -0.2)]
        quads("ed_crosswalks", cw, 0.027, M("white_line"))
        # river (in the ground hole), banks
        quads("ed_river", [river], -0.45, M("water"))
        for xb in (river[0], river[1]):
            bm = bmesh.new()
            B.bm_segment_box(bm, (xb, river[2]), (xb, river[3]), -1.2, 0.0, 0.3, 0)
            B.mesh_obj("ed_bank_%d" % int(xb), bm, [M("strata")])
        self.stats["ground_holes"] = len(holes)

    # ------------------------------------------------------------ S2 slice boxes (strata walls + floor)
    def slice_box(self, name, rect, depth):
        x0, x1, y0, y1 = rect
        bm = bmesh.new()
        t = 0.05
        box_bm(bm, ((x0 + x1) / 2, (y0 + y1) / 2, -depth - t / 2), (x1 - x0 + 2 * t, y1 - y0 + 2 * t, t))
        box_bm(bm, ((x0 + x1) / 2, y1 + t / 2, -depth / 2), (x1 - x0 + 2 * t, t, depth))
        box_bm(bm, ((x0 + x1) / 2, y0 - t / 2, -depth / 2), (x1 - x0 + 2 * t, t, depth))
        box_bm(bm, (x0 - t / 2, (y0 + y1) / 2, -depth / 2), (t, y1 - y0, depth))
        box_bm(bm, (x1 + t / 2, (y0 + y1) / 2, -depth / 2), (t, y1 - y0, depth))
        # charcoal cap rim + teal edge line at the cut edge (museum-model look)
        for (a, b) in (((x0, y1), (x1, y1)), ((x0, y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))):
            B.bm_segment_box(bm, a, b, -0.06, 0.035, 0.06, 1)
            B.bm_segment_box(bm, a, b, 0.035, 0.05, 0.03, 2)
        return B.mesh_obj(name, bm, [self.M.m("strata"), self.M.m("cap"), self.M.m("teal_line")])

    # ------------------------------------------------------------ Z_FAR_LOD
    def build_far(self):
        self.zone("Z_FAR_LOD")
        M = self.M.m
        far = [r for r in P.rect_minus_holes((-6000.0, 6000.0, -6000.0, 6000.0), [(-1000.0, 1400.0, -700.0, 800.0)])]
        quads("ed_far_ground", far, -0.05, M("lawn_far"), uv_scale=40.0)
        # low hills + a tree band ring (one mesh each)
        bm = bmesh.new()
        rng = random.Random(7)
        for i in range(28):
            a = 2 * math.pi * i / 28 + rng.uniform(-0.05, 0.05)
            r = rng.uniform(2600, 4200)
            B.bm_sphere(bm, (100 + r * math.cos(a), 50 + r * math.sin(a), -60.0),
                        (rng.uniform(500, 900), rng.uniform(500, 900), rng.uniform(110, 220)), 2, 0)
        B.mesh_obj("ed_far_hills", bm, [M("lawn_far")], smooth=True)
        bm = bmesh.new()
        for i in range(220):
            a = 2 * math.pi * i / 220
            r = rng.uniform(1500, 2100)
            x, y = 100 + r * math.cos(a), 50 + r * math.sin(a)
            h = rng.uniform(10, 18)
            B.bm_cyl(bm, (x, y, 0.0), (x, y, h), rng.uniform(4, 7), 0.4, 6, 0)
        B.mesh_obj("ed_far_trees", bm, [M("conifer")])
        # district proxies for districts this job does not build
        grey = M("far_grey")
        prox = {"Z_DOWNTOWN": [("box", (sx * 45, sy * 45, 6), (60, 60, 12), 0) for sx in (-1, 1) for sy in (-1, 1)],
                "Z_SUBURB": [("box", (x, y, 3.5), (12, 10, 7), 0) for x in range(140, 520, 40) for y in range(100, 420, 45)],
                "Z_TOWER": [("cyl", (262, 226, 0), (262, 226, 40), 0.7, 0.35, 6, 0)],
                "Z_INDUSTRIAL_DC": [("box", (-420, 330, 6), (90, 60, 12), 0)],
                "Z_POWER": [("box", (430, -330, 4), (80, 60, 8), 0)] +
                           [("box", (x, -330, 17), (3, 3, 34), 0) for x in (500, 750, 1000, 1250)],
                "Z_WATER": [("cyl", (-260, 430, 8), (-260, 430, 40), 2.0, 2.0, 8, 0),
                            ("box", (-260, 430, 48), (16, 16, 14), 0), ("box", (-640, -200, 3), (120, 90, 6), 0)]}
        n = 0
        for zn, parts in prox.items():
            if zn not in self.zones:
                multi("ed_proxy_%s" % zn, parts, [grey])
                n += 1
        self.stats["far_proxies"] = n

    # ------------------------------------------------------------ shared small assets
    def car_meshes(self):
        if hasattr(self, "_cars"):
            return self._cars
        M = self.M.m
        out = {}
        for kind, (Ln, W, H, cab) in {"sedan": (4.7, 1.85, 1.45, 0.55), "suv": (4.9, 1.95, 1.8, 0.75),
                                       "pickup": (5.8, 2.0, 1.9, 0.45)}.items():
            bm = bmesh.new()
            box_bm(bm, (0, 0, 0.55 + 0.25), (W, Ln, 0.6), 0)
            cl = Ln * cab
            box_bm(bm, (0, -Ln * 0.05 if kind != "pickup" else Ln * 0.12, 1.1 + (H - 1.45) / 2), (W * 0.92, cl, H - 1.0), 0)
            box_bm(bm, (0, (-Ln * 0.05 if kind != "pickup" else Ln * 0.12) + cl / 2 + 0.01, 1.1 + (H - 1.45) / 2),
                   (W * 0.86, 0.03, (H - 1.0) * 0.8), 1)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    B.bm_cyl(bm, (sx * W / 2 - sx * 0.08, sy * Ln * 0.32, 0.36), (sx * W / 2 + sx * 0.02, sy * Ln * 0.32, 0.36),
                             0.36, 0.36, 12, 2)
            out[kind] = S.mesh_from_bm("ed_car_" + kind, bm, [M("car_obj"), M("window"), M("tyre")])
        self._cars = out
        return out

    def car(self, name, kind, x, y, yaw_deg, col=None):
        o = S.obj(name, self.car_meshes()[kind], (x, y, 0.0), (0, 0, math.radians(yaw_deg)))
        c = hexc(col or self.rng.choice(CAR_COLS))
        o.color = (c[0], c[1], c[2], 1.0)
        return o

    def tree_templates(self):
        if hasattr(self, "_trees"):
            return self._trees
        M = self.M.m
        tm = []
        for i, (h, r) in enumerate(((7.0, 3.2), (9.0, 3.8), (5.5, 2.6))):
            bm = bmesh.new()
            B.bm_cyl(bm, (0, 0, 0), (0, 0, h * 0.55), 0.22, 0.16, 6, 0)
            B.bm_sphere(bm, (0, 0, h * 0.62), (r, r, r * 0.85), 2, 1, jitter=0.12, seed=i)
            tm.append(B.template_obj("ed_tree_t%d" % i, S.mesh_from_bm("ed_tree_m%d" % i, bm, [M("trunk"), M("leaf")])))
        for i, h in enumerate((10.0, 13.0)):
            bm = bmesh.new()
            B.bm_cyl(bm, (0, 0, 0), (0, 0, 1.5), 0.2, 0.18, 6, 0)
            B.bm_cyl(bm, (0, 0, 1.2), (0, 0, h), h * 0.22, 0.05, 8, 1)
            tm.append(B.template_obj("ed_conifer_t%d" % i, S.mesh_from_bm("ed_conifer_m%d" % i, bm,
                                                                          [M("trunk"), M("conifer")])))
        self._trees = tm
        return tm

    def scatter_trees(self, name, pts):
        tm = self.tree_templates()
        groups = [[] for _ in tm]
        for p in pts:
            groups[self.rng.randrange(len(tm))].append(p)
        for i, g in enumerate(groups):
            if g:
                B.scatter_gn("%s_%d" % (name, i), tm[i], [(x, y, 0.0) for x, y in g],
                             [self.rng.uniform(0, 6.283) for _ in g], [self.rng.uniform(0.8, 1.25) for _ in g])

    def utility_pole(self, name, x, y, h=10.5, transformer=False, arm="x"):
        """Wood pole, cross-arm along `arm` (perpendicular to the line), 3 insulators, optional can transformer."""
        M = self.M.m
        ax, ay = (1.0, 0.0) if arm == "x" else (0.0, 1.0)
        parts = [("cyl", (x, y, -1.0), (x, y, h), 0.15, 0.11, 8, 0),
                 ("box", (x, y, h - 0.6), (2.4 if arm == "x" else 0.12, 0.12 if arm == "x" else 2.4, 0.12), 0)]
        for k in (-1.0, 0.0, 1.0):
            z0 = h - 0.54 if k else h
            parts.append(("cyl", (x + ax * k, y + ay * k, z0), (x + ax * k, y + ay * k, z0 + 0.2), 0.04, 0.04, 6, 1))
        if transformer:
            parts += [("cyl", (x, y - 0.35, 8.0), (x, y - 0.35, 9.0), 0.25, 0.25, 12, 2),
                      ("box", (x, y - 0.12, 8.5), (0.12, 0.25, 0.12), 2), ("cyl", (x + 0.3, y - 0.3, 9.1),
                                                                            (x + 0.3, y - 0.3, 9.5), 0.03, 0.03, 6, 1)]
        return multi(name, parts, [M("pole_wood"), M("insulator"), M("grey_box")])

    def fence(self, name, x0, x1, y0, y1, h=2.2, gap=None):
        """Chain-link fence: galvanized posts + one translucent mesh band (alpha, no moire-prone texture)."""
        M = self.M.m
        posts, bm = [], bmesh.new()
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            Lg = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(Lg / 3.0))
            for i in range(n):
                t0, t1 = i / float(n), (i + 1) / float(n)
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                posts.append(("cyl", (p0[0], p0[1], 0.0), (p0[0], p0[1], h), 0.04, 0.04, 6, 0))
                if gap and math.hypot((p0[0] + p1[0]) / 2 - gap[0], (p0[1] + p1[1]) / 2 - gap[1]) < 2.0:
                    continue
                B.bm_segment_box(bm, p0, p1, 0.05, h, 0.01, 0)
        multi(name + "_posts", posts, [M("galv")])
        B.mesh_obj(name + "_mesh", bm, [M("fence")])

    # ------------------------------------------------------------ Z_DOWNTOWN: blocks, intersection, loop slice, mall
    def build_downtown(self):
        self.zone("Z_DOWNTOWN")
        M = self.M.m
        rng = random.Random(11)
        meshes = []
        for i, (w, d, fl) in enumerate(((14, 12, 2), (12, 12, 3), (16, 12, 4), (12, 10, 2))):
            bm = bmesh.new()
            box_bm(bm, (0, 0, fl * 1.8), (w, d, fl * 3.6), 0)
            box_bm(bm, (0, -d / 2 - 0.9, 3.0), (w * 0.9, 1.8, 0.12), 1)          # blank awning
            box_bm(bm, (0, -d / 2 - 0.05, 4.2), (w * 0.8, 0.1, 0.8), 2)          # blank sign band
            meshes.append(S.mesh_from_bm("ed_block_%d" % i, bm, [M("brick") if i % 2 == 0 else M("stucco"),
                                                                    M("teal_line") if i % 2 else M("amber_glow"),
                                                                    M("paint")]))
        mall = (-140.0, -30.0, -80.0, -5.0)
        n = 0
        for qx in (-1, 1):
            for qy in (-1, 1):
                for i in range(6):
                    for j in range(4):
                        x, y = qx * (20 + 17 * i), qy * (20 + 16 * j)
                        if mall[0] < x < mall[1] and mall[2] < y < mall[3]:
                            continue
                        if abs(x) > 125 or abs(y) > 110:
                            continue
                        yaw = 0.0 if qy > 0 and j == 0 else math.pi if qy < 0 and j == 0 else \
                            (math.pi / 2 if qx < 0 else -math.pi / 2)
                        S.obj("ed_block_%d" % n, meshes[rng.randrange(len(meshes))], (x, y, 0.0), (0, 0, yaw))
                        n += 1
        self.stats["downtown_blocks"] = n
        self.build_intersection()
        self.build_loop_slice()
        self.build_signal_cabinet()
        self.build_mall_exterior()

    def build_intersection(self):
        M = self.M.m
        # mast arms: each corner pole serves the approach on its right; heads face the oncoming traffic
        heads = []
        poles = []
        spec = [((9.5, -9.5), (-1, 0), (0, -1), "red"),      # SE pole -> NB approach (hero pickup waits on red)
                ((9.5, 9.5), (0, -1), (1, 0), "green"),       # NE -> WB
                ((-9.5, 9.5), (1, 0), (0, 1), "red"),         # NW -> SB
                ((-9.5, -9.5), (0, 1), (-1, 0), "green")]     # SW -> EB
        for (px, py), (ax, ay), (fx, fy), state in spec:
            poles.append(("cyl", (px, py, 0.0), (px, py, 7.2), 0.2, 0.14, 12, 0))
            poles.append(("cyl", (px, py, 6.6), (px + ax * 8.5, py + ay * 8.5, 6.4), 0.1, 0.06, 8, 0))
            for k in (3.0, 6.5):
                hx, hy = px + ax * k, py + ay * k
                heads.append((hx, hy, (fx, fy), state))
        multi("ed_mast_arms", poles, [M("galv")])
        bm_body, lens = bmesh.new(), {"red_lens_on": bmesh.new(), "green_lens_on": bmesh.new(), "lens_off": bmesh.new()}
        for hx, hy, (fx, fy), state in heads:
            box_bm(bm_body, (hx, hy, 5.6), (0.36 if fy else 0.3, 0.3 if fy else 0.36, 1.05), 0)
            for k, col in ((0.33, "red"), (0.0, "amber"), (-0.33, "green")):
                key = "red_lens_on" if (col == "red" and state == "red") else \
                    "green_lens_on" if (col == "green" and state == "green") else "lens_off"
                c = (hx + fx * 0.16, hy + fy * 0.16, 5.6 + k)
                B.bm_cyl(lens[key], c, (c[0] + fx * 0.03, c[1] + fy * 0.03, c[2]), 0.11, 0.11, 12, 0)
        B.mesh_obj("ed_signal_heads", bm_body, [M("steel_dark")])
        for key, bm in lens.items():
            B.mesh_obj("ed_signal_lens_" + key, bm, [M(key)])
        # waiting cars + the hero pickup over the loop (NB lane 1)
        self.car("ed_hero_pickup", "pickup", 2.0, -14.0, 0.0, "8c1c1c")
        for i, (x, y, yaw) in enumerate(((2.0, -22.5, 0), (5.8, -16.0, 0), (-2.0, 15.0, 180), (-2.2, 23.0, 180),
                                          (16.0, 2.0, 90), (25.0, 2.2, 90), (-15.0, -2.0, -90))):
            self.car("ed_car_int_%d" % i, self.rng.choice(("sedan", "suv")), x, y, yaw)
        # street lights (cobra heads) along Elm / Main
        parts = []
        for k in range(-6, 7):
            if k == 0:
                continue
            for (x, y, dx, dy) in ((k * 22.0, 11.5, 0, -1), (12.5, k * 22.0, -1, 0)):
                parts += [("cyl", (x, y, 0), (x, y, 8.5), 0.09, 0.07, 8, 0),
                          ("cyl", (x, y, 8.3), (x + dx * 2.2, y + dy * 2.2, 8.6), 0.05, 0.05, 6, 0),
                          ("box", (x + dx * 2.4, y + dy * 2.4, 8.55), (0.5, 0.5, 0.15), 0)]
        multi("ed_street_lights", parts, [M("galv")])

    def build_loop_slice(self):
        M = self.M.m
        sl = P.SLICES["loop"]
        self.slice_box("ed_loop_slice", sl["rect"], sl["depth"])
        cx, cy = 2.0, -14.0
        h = 1.83 / 2
        pts = []
        for k in range(3):                      # 3 turns, slightly inset each time, drawn 1.5x thick
            e = h - k * 0.025
            pts += rect_pts(cx, cy, -0.05 - k * 0.012, e, e)[:-1]
        pts.append(pts[0])
        curve("ed_loop_wire", pts, 0.009, M("copper"))
        curve("ed_loop_leadin", [(cx + h, cy, -0.05), (3.7, cy, -0.05), (7.6, cy, -0.05), (8.3, cy, -0.25)], 0.009,
              M("copper"))
        box("ed_loop_pullbox", (8.35, cy, -0.2), (0.45, 0.65, 0.42), M("concrete"))
        quads("ed_loop_sealant", [(cx - h - 0.02, cx + h + 0.02, cy - h - 0.02, cy - h + 0.02),
                                  (cx - h - 0.02, cx + h + 0.02, cy + h - 0.02, cy + h + 0.02),
                                  (cx - h - 0.02, cx - h + 0.02, cy - h, cy + h),
                                  (cx + h - 0.02, cx + h + 0.02, cy - h, cy + h)], 0.0235, M("rubber"))
        for i, r in enumerate((0.5, 0.75, 1.0)):     # the field: translucent teal loops above the wire
            curve("ed_loop_field_%d" % i, rect_pts(cx, cy, 0.25 + 0.3 * i, h * r + 0.3 * i, h * r + 0.3 * i),
                  0.02, M("teal_alpha"))
        area_light("ed_loop_fill", (6.5, -14.0, 0.8), 3.0, 120.0, rot=(0.0, math.radians(-60), 0.0))

    def build_signal_cabinet(self):
        M = self.M.m
        x, y = 11.5, -11.5
        box("ed_cabinet_pad", (x, y, 0.07), (1.6, 1.0, 0.14), M("concrete"))
        bm = bmesh.new()
        box_bm(bm, (x, y - 0.05, 0.9), (1.2, 0.5, 1.5), 0)                   # body (open north face behind door)
        B.mesh_obj("ed_cabinet_body", bm, [M("grey_box")])
        door = box("ed_cabinet_door", (x, y + 0.23, 0.9), (1.16, 0.03, 1.46), M("grey_box"))
        self.peel("signal_door", door, (1.25, 0.0, 0.0))
        parts = [("box", (x, y + 0.1, 0.8), (1.0, 0.25, 0.04), 0), ("box", (x, y + 0.1, 1.15), (1.0, 0.25, 0.04), 0)]
        for i in range(8):
            parts.append(("box", (x - 0.42 + i * 0.12, y + 0.12, 0.98), (0.02, 0.22, 0.3), 1))
        multi("ed_cabinet_rack", parts, [M("steel_dark"), M("pcb")])
        leds = [("box", (x - 0.42 + i * 0.12, y + 0.235, 1.08), (0.012, 0.004, 0.012), 0) for i in range(8)]
        multi("ed_cabinet_leds", leds, [M("led_green")])
        area_light("ed_cabinet_fill", (x, y + 0.9, 1.6), 0.6, 25.0, rot=(math.radians(-60), 0.0, 0.0))

    def build_mall_exterior(self):
        M = self.M.m
        x0, x1, y0, y1, h = -130.0, -40.0, -70.0, -50.0, 6.0
        bm = bmesh.new()
        B.bm_segment_box(bm, (x0, y0), (x1, y0), 0.0, h, 0.3, 0)
        B.bm_segment_box(bm, (x0, y0), (x0, y1), 0.0, h, 0.3, 0)
        B.bm_segment_box(bm, (x1, y0), (x1, y1), 0.0, h, 0.3, 0)
        for k in range(1, 5):                                   # unit dividers
            B.bm_segment_box(bm, (x0 + 18 * k, y0), (x0 + 18 * k, y1), 0.0, h, 0.2, 0)
        box_bm(bm, ((x0 + x1) / 2, y1 - 0.15, 5.0), (x1 - x0, 0.3, 2.0), 0)      # storefront header
        for k in range(5):
            box_bm(bm, (x0 + 9 + 18 * k, y1 + 0.2, 5.0), (12.0, 0.2, 1.2), 1 + k % 2)  # blank sign bands
        B.mesh_obj("ed_mall_walls", bm, [M("stucco"), M("teal_line"), M("amber_glow")])
        roof = box("ed_mall_roof", ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.15), (x1 - x0 + 0.6, y1 - y0 + 0.6, 0.3),
                   M("roof_membrane"))
        self.peel("mall_roof", roof, (0.0, 0.0, 40.0))
        glass = []
        for k in range(5):
            ux0 = x0 + 18 * k + 0.2
            if k == 2:                                          # unit 3: automatic doors stay open (fly-in)
                glass += [(ux0, -86.0), (-84.0, ux0 + 17.6)]
            else:
                glass.append((ux0, ux0 + 17.6))
        bm = bmesh.new()
        for a, b in glass:
            B.bm_segment_box(bm, (a, y1 - 0.1), (b, y1 - 0.1), 0.0, 4.0, 0.04, 0)
        B.mesh_obj("ed_mall_glass", bm, [M("glass")])
        rng = random.Random(3)
        for i in range(14):
            self.car("ed_car_lot_%d" % i, rng.choice(("sedan", "suv", "pickup")), -128 + i * 6.5, -30.0 - (i % 2) * 9.0,
                     0.0 if i % 2 else 180.0)
        stripes = [(-131 + i * 3.25, -130.9 + i * 3.25, -40.0, -20.0) for i in range(30)]
        quads("ed_lot_stripes", stripes, 0.025, M("white_line"))

    # ------------------------------------------------------------ Z_STRIPMALL_INT + its macro hosts
    def build_mall_interior(self):
        self.zone("Z_STRIPMALL_INT")
        M = self.M.m
        ux0, ux1, y0, y1 = -94.0, -76.0, -70.0, -50.0
        quads("ed_mall3_floor", [(ux0, ux1, y0, y1)], 0.06, M("tile"))
        quads("ed_mall3_ceiling", [(ux0, ux1, y0, y1)], 4.5, M("paint"))
        panels = [("box", (ux0 + 3 + 4 * i, y0 + 3 + 4.5 * j, 4.45), (1.2, 0.6, 0.04), 0) for i in range(4) for j in range(4)]
        multi("ed_mall3_panels", panels, [M("ceiling_panel")])
        area_light("ed_mall3_key", (-88.0, -56.5, 4.2), 4.0, 900.0, color=(1.0, 0.97, 0.93))
        area_light("ed_mall3_fill", (-84.0, -62.0, 4.2), 6.0, 700.0, color=(1.0, 0.97, 0.93))
        # shelves (linked duplicates) with abstract packages
        bm = bmesh.new()
        box_bm(bm, (0, 0, 0.9), (4.0, 0.6, 1.8), 0)
        for k in range(3):
            for i in range(8):
                box_bm(bm, (-1.75 + i * 0.5, 0, 0.45 + k * 0.55), (0.4, 0.45, 0.35), 1 + (i + k) % 3)
        me = S.mesh_from_bm("ed_shelf", bm, [M("paint"), M("wrapper"), M("card_pvc"), M("amber_glow")])
        for i, (x, y) in enumerate(((-91.0, -60.0), (-85.0, -60.0), (-79.5, -60.0), (-91.0, -64.0), (-85.0, -64.0),
                                    (-79.5, -64.0), (-91.0, -68.0), (-85.0, -68.0), (-79.5, -68.0))):
            S.obj("ed_shelf_%d" % i, me, (x, y, 0.06))
        # checkout counter (top has a hole for the flush scanner glass), conveyor, terminal stand
        sc = (-87.80, -87.40, -54.95, -54.65)
        tops = P.rect_minus_holes((-89.6, -84.0, -55.2, -54.4), [sc])
        quads("ed_counter_top", tops, 0.95, M("tile"))
        box("ed_counter_body", (-86.8, -54.8, 0.47), (5.6, 0.8, 0.9), M("paint_warm"))
        box("ed_conveyor", (-85.2, -54.8, 0.965), (2.4, 0.5, 0.03), M("rubber"))
        cyl("ed_terminal_post", (-88.4, -54.62, 0.95), (-88.4, -54.62, 1.04), 0.015, 0.015, M("steel_dark"))
        # shopper: forearm + hand holding the card from the north
        cyl("ed_shopper_arm", (-88.32, -54.05, 1.10), (-88.40, -54.48, 1.155), 0.045, 0.038, M("paint_warm"))
        box("ed_shopper_hand", (-88.40, -54.515, 1.158), (0.07, 0.05, 0.03), M("paint_warm"))
        self.build_card_host()
        self.build_terminal_host()
        self.build_gum_host()

    def build_card_host(self):
        M = self.M.m
        e = host_empty(P.CARD)
        self.hosts["card"] = e
        w, h, t = (v / 1000.0 for v in P.CARD_SIZE_MM)
        box("ed_card_core", (0, 0, t * 0.25), (w, h, t * 0.5), M("card_core"), parent=e)
        top = box("ed_card_top", (0, 0, t * 0.75), (w, h, t * 0.5), M("card_pvc"), parent=e)
        plate = box("ed_card_plate", (-0.024, 0.004, t + 0.00002), (0.011, 0.012, 0.00005), M("gold"), parent=e)
        self.peel("card_top", top, (0.0, 0.0, 0.002))
        self.peel("card_top", plate, (0.0, 0.0, 0.004))

    def build_terminal_host(self):
        M = self.M.m
        e = host_empty(P.TERMINAL)
        self.hosts["terminal"] = e
        w, h, d = (v / 1000.0 for v in P.TERMINAL_SIZE_MM)
        box("ed_terminal_base", (0, 0, -d / 4), (w, h, d / 2), M("steel_dark"), parent=e)
        top = multi("ed_terminal_top", [("box", (0, 0, d / 4), (w, h, d / 2), 0),
                                        ("box", (0, 0.035, d / 2 + 0.0005), (0.066, 0.08, 0.001), 1),
                                        ("box", (0, 0.035, d / 2 + 0.0012), (0.012, 0.012, 0.0006), 2)] +
                    [("box", (-0.022 + 0.022 * (i % 3), -0.03 - 0.012 * (i // 3), d / 2 + 0.0008),
                      (0.016, 0.008, 0.0016), 3) for i in range(12)],
                    [M("steel_dark"), M("screen_tiles"), M("teal_glow"), M("grey_box")], parent=e)
        self.peel("terminal_case", top, (0.0, 0.0, 0.12))

    def build_gum_host(self):
        M = self.M.m
        e = host_empty(P.GUM)
        self.hosts["gum"] = e
        w, h, d = (v / 1000.0 for v in P.GUM_SIZE_MM)
        box("ed_gum_pack", (0, 0, 0), (w, h, d), M("wrapper"), parent=e)
        box("ed_gum_label", (0, 0, d / 2 + 0.0001), (0.037, 0.026, 0.0002), M("barcode"), parent=e)

    # ------------------------------------------------------------ portal interior: enlarged microwave cavity (x20)
    def build_mw_inside(self):
        """WORLDS-SPEC 1.1 P (+ R fallback): the cooking cavity of kitchen_microwave enlarged 20x as a closed, bright
        metal room 300 m under the origin (never seen from the town), reached only through fill-frame portals.
        Inside: perforated door wall (light from the kitchen glows through), turntable + bowl of soup, magnetron and
        wave-guide on the right wall, cavity lamp, amber standing-wave ribbons (graphic)."""
        self.zone("Z_MW_INSIDE")
        M = self.M.m
        ox, oy, oz = P.MW_INSIDE
        hx, hy, hz = 5.0, 3.5, 2.8                       # 0.50 x 0.35 x 0.28 m cavity x 20
        walls = [("box", (ox, oy + hy + 0.1, oz), (2 * hx + 0.4, 0.2, 2 * hz + 0.4), 0),       # back
                 ("box", (ox - hx - 0.1, oy, oz), (0.2, 2 * hy, 2 * hz + 0.4), 0),             # left
                 ("box", (ox + hx + 0.1, oy, oz), (0.2, 2 * hy, 2 * hz + 0.4), 0),             # right
                 ("box", (ox, oy, oz - hz - 0.1), (2 * hx + 0.4, 2 * hy + 0.4, 0.2), 0),       # floor
                 ("box", (ox, oy, oz + hz + 0.1), (2 * hx + 0.4, 2 * hy + 0.4, 0.2), 0)]       # ceiling
        multi("ed_mwin_walls", walls, [M("cavity_metal")])
        box("ed_mwin_door_mesh", (ox, oy - hy - 0.05, oz), (2 * hx, 0.04, 2 * hz), M("mw_mesh_big"))
        box("ed_mwin_door_glow", (ox, oy - hy - 1.5, oz), (2 * hx + 2, 0.1, 2 * hz + 2),
            B.mat_glow("ed_mwin_kitchen_glow", hexc("f3e6d0"), 1.2))
        multi("ed_mwin_turntable", [("cyl", (ox, oy + 0.5, oz - hz), (ox, oy + 0.5, oz - hz + 0.3), 0.6, 0.6, 16, 1),
                                    ("cyl", (ox, oy + 0.5, oz - hz + 0.3), (ox, oy + 0.5, oz - hz + 0.42), 2.6, 2.6,
                                     48, 0)], [M("clear_glass"), M("steel_dark")])
        multi("ed_mwin_bowl", [("cyl", (ox, oy + 0.5, oz - hz + 0.42), (ox, oy + 0.5, oz - hz + 1.8), 1.4, 1.7, 32, 0),
                               ("cyl", (ox, oy + 0.5, oz - hz + 1.6), (ox, oy + 0.5, oz - hz + 1.65), 1.55, 1.55,
                                32, 1)], [M("paint_warm"), S.pbr("ed_soup", hexc("c8602a"), 0.25, coat=0.4)])
        multi("ed_mwin_waveguide", [("box", (ox + hx - 0.4, oy + 1.5, oz + 1.5), (0.6, 2.4, 1.6), 0),
                                    ("box", (ox + hx - 0.08, oy + 1.5, oz + 1.5), (0.04, 2.0, 1.2), 1)],
              [M("galv"), S.pbr("ed_mica", hexc("cdbf9a"), 0.6)])
        multi("ed_mwin_magnetron", [("box", (ox + hx + 1.2, oy + 1.5, oz + 1.5), (2.0, 2.0, 2.0), 0),
                                    ("cyl", (ox + hx + 0.2, oy + 1.5, oz + 1.5), (ox + hx + 0.9, oy + 1.5, oz + 1.5), 0.5,
                                     0.5, 16, 1)], [M("steel_dark"), M("copper")])
        box("ed_mwin_lamp", (ox - 2.0, oy + hy - 0.02, oz + 2.0), (1.0, 0.03, 0.6),
            B.mat_glow("ed_mwin_lamp", hexc("ffe2b0"), 6.0))
        for i in range(3):                               # standing wave between the walls (graphic, ~12 cm x 20)
            y = oy - 1.5 + 1.5 * i
            pts = [(ox - hx + 0.1 + 0.2 * j, y, oz + 0.4 * math.sin(2 * math.pi * (0.2 * j) / 2.4)) for j in range(50)]
            curve("ed_mwin_wave_%d" % i, pts, 0.03, M("amber_glow"))
        area_light("ed_mwin_key", (ox, oy, oz + hz - 0.3), 6.0, 900.0, size_y=4.0, color=(1.0, 0.95, 0.85))
        area_light("ed_mwin_fill", (ox - 3.0, oy - 2.5, oz), 3.0, 250.0, rot=(math.radians(70), 0.0, math.radians(-40)))

    # ------------------------------------------------------------ W2 macro sets (Z_MACRO_*)
    def build_macro_card(self):
        self.zone("Z_MACRO_CARD")
        M = self.M.m
        e = self.hosts.get("card") or host_empty(P.CARD)
        t = P.CARD_SIZE_MM[2] / 1000.0
        box("ed_card_die", (-0.024, 0.004, t * 0.55), (0.003, 0.003, 0.0003), M("chip"), parent=e)
        pads = [("box", (-0.024 + dx * 0.0035, 0.004 + dy * 0.003, t * 0.62), (0.0028, 0.002, 0.00008), 0)
                for dx in (-1, 1) for dy in (-1.5, -0.5, 0.5, 1.5)]
        multi("ed_card_pads", pads, [M("gold")], parent=e)
        for i, (dx, dy) in enumerate(((-0.0035, -0.0045), (0.0035, -0.0045), (-0.0035, 0.0045), (0.0035, 0.0045))):
            curve("ed_card_bond_%d" % i, [(-0.024 + dx * 0.4, 0.004 + dy * 0.3, t * 0.6),
                                          (-0.024 + dx * 0.7, 0.004 + dy * 0.65, t * 0.66),
                                          (-0.024 + dx, 0.004 + dy * 0.85, t * 0.62)], 0.00003, M("gold"), parent=e)
        pts = []
        for k in range(4):                     # 4 turns around the card edge (0.1 mm wire drawn 3x: not to scale)
            m = 0.004 + k * 0.0012
            pts += rect_pts(0.0, 0.0, t * 0.5, 0.0428 - m, 0.027 - m)[:-1]
        pts.append(pts[0])
        curve("ed_card_coil", pts, 0.00015, M("copper"), parent=e)
        curve("ed_card_coil_link", [(0.0388, -0.023, t * 0.5), (0.0, -0.01, t * 0.5), (-0.022, 0.002, t * 0.5)],
              0.00012, M("copper"), parent=e)
        for i, r in enumerate((0.03, 0.045, 0.06)):          # terminal field loops (graphic)
            curve("ed_card_field_%d" % i, ring_pts((0.0, 0.0, -0.01 - 0.01 * i), r), 0.0006, M("teal_alpha"), parent=e)
        area_light("ed_card_lightbox", P.CARD.to_world((-0.03, 0.03, 0.12)), 0.12, 3.0)

    def build_macro_terminal(self):
        self.zone("Z_MACRO_TERMINAL")
        M = self.M.m
        e = self.hosts.get("terminal") or host_empty(P.TERMINAL)
        multi("ed_terminal_board", [("box", (0, -0.01, 0.004), (0.07, 0.15, 0.0012), 0),
                                    ("box", (0.015, -0.05, 0.0065), (0.008, 0.008, 0.002), 1),
                                    ("box", (-0.02, -0.03, 0.006), (0.012, 0.012, 0.0016), 2)],
              [M("pcb"), M("teal_glow"), M("chip")], parent=e)
        curve("ed_terminal_coil", rect_pts(0.0, 0.02, 0.018, 0.028, 0.028), 0.0006, M("copper"), parent=e)
        curve("ed_terminal_coil2", rect_pts(0.0, 0.02, 0.0182, 0.025, 0.025), 0.0006, M("copper"), parent=e)
        area_light("ed_terminal_lightbox", P.TERMINAL.to_world((0.02, 0.05, 0.25)), 0.2, 6.0)

    def build_macro_scanner(self):
        self.zone("Z_MACRO_SCANNER")
        M = self.M.m
        x, y = -87.6, -54.8
        box("ed_scanner_body", (x, y, 0.80), (0.40, 0.30, 0.28), M("steel_dark"))
        top = box("ed_scanner_glass", (x, y, 0.945), (0.40, 0.30, 0.01), M("glass"))
        self.peel("scanner_top", top, (0.0, 0.0, 0.25))
        box("ed_scanner_tower", (x, y - 0.17, 1.03), (0.40, 0.04, 0.16), M("steel_dark"))
        box("ed_scanner_window", (x, y - 0.148, 1.03), (0.34, 0.004, 0.12), M("glass"))
        cyl("ed_scanner_wheel", (x, y, 0.80), (x, y, 0.84), 0.05, 0.05, M("white_metal"), seg=8)
        box("ed_scanner_pcb", (x + 0.1, y + 0.05, 0.70), (0.15, 0.12, 0.004), M("pcb"))
        box("ed_scanner_diode", (x - 0.12, y + 0.08, 0.76), (0.02, 0.02, 0.02), M("chip"))
        lines = [("box", (x, y, 0.952), (0.36, 0.002, 0.0005), 0), ("box", (x, y, 0.952), (0.002, 0.26, 0.0005), 0)]
        for a in (-30, 30):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            lines.append(("box", (x, y, 0.9525), (0.36 * abs(ca) + 0.002, 0.36 * abs(sa) + 0.002, 0.0005), 0))
        multi("ed_scanner_lasers", lines, [M("laser")])
        area_light("ed_scanner_fill", (x, y + 0.2, 1.3), 0.3, 8.0, rot=(math.radians(-30), 0.0, 0.0))

    def build_macro_phone(self):
        self.zone("Z_MACRO_PHONE")
        M = self.M.m
        e = self.hosts.get("phone") or host_empty(P.PHONE)
        parts = [("box", (0, 0.020, -0.0028), (0.066, 0.040, 0.0008), 0),
                 ("box", (0, 0.020, -0.0019), (0.012, 0.012, 0.0010), 1),
                 ("box", (0.017, 0.028, -0.0020), (0.010, 0.008, 0.0008), 1),
                 ("box", (-0.017, 0.012, -0.0020), (0.008, 0.009, 0.0008), 1),
                 ("box", (0.0, -0.035, -0.0015), (0.060, 0.062, 0.0040), 2),
                 ("box", (0.030, 0.065, -0.0005), (0.006, 0.010, 0.0020), 1)]
        rng = random.Random(5)
        for i in range(60):
            parts.append(("box", (rng.uniform(-0.03, 0.03), rng.uniform(0.002, 0.038), -0.0022),
                          (0.0010, 0.0005, 0.0005), 3))
        multi("ed_phone_board", parts, [M("pcb"), M("chip"), M("battery"), M("gold")], parent=e)
        patches = [("box", (0.0345, 0.060 + 0.0025 * i, 0.0), (0.0004, 0.0018, 0.0018), 0) for i in range(4)]
        multi("ed_phone_mmwave", patches, [M("gold")], parent=e)
        shields = multi("ed_phone_shields", [("box", (0, 0.020, -0.0012), (0.030, 0.022, 0.0006), 0)],
                        [M("galv")], parent=e)
        self.peel("phone_display", shields, (0.0, 0.0, 0.012))
        for i, r in enumerate((0.03, 0.06, 0.1)):
            curve("ed_phone_rings_%d" % i, ring_pts((0.03, 0.07, 0.0), r, axis="y"), 0.0008, M("teal_alpha"), parent=e)
        area_light("ed_phone_lightbox", P.PHONE.to_world((0.0, 0.02, 0.15)), 0.15, 4.0,
                   rot=(math.radians(P.PHONE.rx), 0.0, 0.0))

    def build_macro_microwave(self):
        self.zone("Z_MACRO_MW")
        M = self.M.m
        mw = P.MICROWAVE
        y = 161.415
        box("ed_mw_mesh_patch", (mw["x"], y, 2.05), (0.06, 0.0004, 0.04), M("mw_mesh"))   # object coords = local mm
        pts = [(mw["x"] - 0.05 + 0.002 * i, y + 0.012 + 0.006 * math.sin(2 * math.pi * (0.002 * i) / 0.12 * 8), 2.05)
               for i in range(51)]
        curve("ed_mw_wave", pts, 0.0008, M("amber_glow"))
        for i in range(3):
            curve("ed_mw_ray_%d" % i, [(mw["x"] - 0.01 + 0.01 * i, y + 0.03, 2.06), (mw["x"] - 0.01 + 0.01 * i, y - 0.05,
                                                                                   2.06)], 0.0003, M("white_line"))
        area_light("ed_mw_lightbox", (mw["x"], y - 0.10, 2.20), 0.15, 4.0, rot=(math.radians(-50), 0.0, 0.0))

    # ------------------------------------------------------------ Z_SUBURB: street grid houses, trees, poles, hero
    def house_meshes(self):
        M = self.M.m
        out = []
        for i, (w, d, h, rh, porch) in enumerate(((11, 9, 5.8, 2.6, True), (14, 9, 3.1, 1.9, False),
                                                  (12, 10, 5.6, 2.4, False), (10, 8, 3.2, 2.0, True),
                                                  (13, 9, 4.4, 2.2, True), (11, 10, 6.0, 2.8, False))):
            bm = bmesh.new()
            box_bm(bm, (0, 0, h / 2), (w, d, h), 0)
            S.bm_prism_x(bm, -w / 2 - 0.4, w / 2 + 0.4, [(-d / 2 - 0.5, h - 0.05), (d / 2 + 0.5, h - 0.05), (0, h + rh)], 1)
            for z in ((1.5,) if h < 4 else (1.5, 4.2)):
                for k in (-1, 1):
                    box_bm(bm, (k * w / 4.0, -d / 2 - 0.04, z), (1.3, 0.08, 1.2), 2)
                    box_bm(bm, (k * w / 4.0, -d / 2 - 0.08, z), (1.1, 0.06, 1.0), 3)
            box_bm(bm, (0, -d / 2 - 0.05, 1.05), (1.0, 0.1, 2.1), 2)
            if porch:
                box_bm(bm, (0, -d / 2 - 1.2, 0.2), (w * 0.5, 2.4, 0.4), 2)
            out.append(S.mesh_from_bm("ed_house_%d" % i, bm, [M("siding_obj"), M("shingles"), M("trim"), M("window")]))
        return out

    def build_suburb(self):
        self.zone("Z_SUBURB")
        rng = random.Random(21)
        meshes = self.house_meshes()
        hero = (184.0, 216.0, 145.0, 170.0)
        tower = (249.0, 290.0, 205.0, 250.0)
        roads_v = [r for r in self.ROADS_V if r[2] < 300 and r[3] > 100]
        trees, n = [], 0
        for (rx0, rx1, ry0, ry1) in self.ROADS_H:
            if not (100 <= rx0 <= 120 and ry0 > 60):
                continue
            for side in (-1, 1):
                yc = ry1 + 14 if side > 0 else ry0 - 14
                for x in range(int(rx0) + 12, int(rx1) - 6, 22):
                    if any(vx0 - 8 < x < vx1 + 8 for (vx0, vx1, _a, _b) in roads_v):
                        continue
                    if hero[0] < x < hero[1] and hero[2] < yc < hero[3]:
                        continue
                    if tower[0] - 6 < x < tower[1] + 6 and tower[2] - 6 < yc < tower[3] + 6:
                        continue
                    o = S.obj("ed_house_%d" % n, meshes[rng.randrange(len(meshes))], (x + rng.uniform(-1, 1), yc, 0.0),
                              (0, 0, 0.0 if side > 0 else math.pi))
                    c = hexc(rng.choice(SIDING_COLS))
                    o.color = (c[0], c[1], c[2], 1.0)
                    n += 1
                    trees.append((x + rng.uniform(-9, 9), yc + side * rng.uniform(9, 16)))
                    if rng.random() < 0.6:
                        trees.append((x + rng.uniform(-8, 8), yc - side * rng.uniform(8.5, 10.5)))
                    if rng.random() < 0.35:
                        self.car("ed_car_drive_%d" % n, rng.choice(("sedan", "suv", "pickup")), x + 7.5,
                                 yc - side * 6.5, 90.0 if side > 0 else -90.0)
        self.stats["suburb_houses"] = n
        self.scatter_trees("ed_trees_suburb", trees)
        # utility poles: Maple St north side (incl. the hero pole) + the Birch St feeder (wires)
        wire = S.pbr("ed_wire", hexc("202224"), 0.5)
        maple = [(109.0 + 40 * i, 149.0) for i in range(11)]          # line along X -> arms along Y
        birch = [(250.5, -290.0 + 40 * i) for i in range(11)]         # line along Y -> arms along X
        for line, pts, arm in (("maple", maple, "y"), ("birch", birch, "x")):
            ax, ay = (1.0, 0.0) if arm == "x" else (0.0, 1.0)
            for i, (x, y) in enumerate(pts):
                self.utility_pole("ed_pole_%s_%d" % (line, i), x, y, transformer=(line == "maple" and x == 189.0),
                                  arm=arm)
            for j, (a, b) in enumerate(zip(pts, pts[1:])):
                for k in (-1.0, 0.0, 1.0):
                    z = 10.5 - 0.34 if k else 10.7
                    pa, pb = (a[0] + ax * k, a[1] + ay * k, z), (b[0] + ax * k, b[1] + ay * k, z)
                    B.curve_line("ed_wire_%s_%d_%d" % (line, j, int(k) + 1), B.catenary(pa, pb, 0.45), 0.012 * 1.5,
                                 wire)
        # service drop: hero pole -> meter mast on the west wall
        B.curve_line("ed_service_drop", B.catenary((189.0, 149.0, 10.0), (193.9, 155.0, 7.0), 0.5), 0.015, wire)
        self.build_hero_exterior()
        self.build_person_phone()

    # ------------------------------------------------------------ W3 hero house shell (peel panels) + yard
    def wall_with_holes(self, name, axis, at, span, zr, holes, thick, mat):
        """A wall slab in the plane x=at (axis 'x') or y=at (axis 'y'), spanning span (along the other axis) and zr,
        minus rectangular openings holes = [(s0, s1, z0, z1)]. One mesh of boxes."""
        bm = bmesh.new()
        for (s0, s1, z0, z1) in P.rect_minus_holes((span[0], span[1], zr[0], zr[1]), holes):
            c = (at, (s0 + s1) / 2, (z0 + z1) / 2) if axis == "x" else ((s0 + s1) / 2, at, (z0 + z1) / 2)
            sz = (thick, s1 - s0, z1 - z0) if axis == "x" else (s1 - s0, thick, z1 - z0)
            box_bm(bm, c, sz, 0)
        return B.mesh_obj(name, bm, [mat])

    def build_hero_exterior(self):
        M = self.M.m
        H = P.HOUSE
        x0, x1, y0, y1 = H["x0"], H["x1"], H["y0"], H["y1"]
        zf, ze, zr = 0.35, H["eaves"], H["ridge"]
        t = 0.15
        # foundation (basement walls, concrete) with the west wall slice opening
        ww = P.SLICES["wall_west"]
        self.wall_with_holes("ed_found_w", "x", x0 + t / 2, (y0, y1), (-2.0, zf), [ww["span"] + (ww["z"][0], zf)], t,
                             M("concrete"))
        self.wall_with_holes("ed_found_e", "x", x1 - t / 2, (y0, y1), (-2.0, zf), [], t, M("concrete"))
        self.wall_with_holes("ed_found_s", "y", y0 + t / 2, (x0, x1), (-2.0, zf), [], t, M("concrete"))
        wn = P.SLICES["wall_north"]
        self.wall_with_holes("ed_found_n", "y", y1 - t / 2, (x0, x1), (-2.0, zf), [], t, M("concrete"))
        # walls: west + east fixed; south / north peel (sink into the ground)
        win_w = [(y0 + 2.2, y0 + 3.4, 1.5, 2.7), (y0 + 6.6, y0 + 7.8, 1.5, 2.7), (y0 + 2.2, y0 + 3.4, 4.3, 5.5)]
        self.wall_with_holes("ed_wall_w", "x", x0 + t / 2, (y0, y1), (zf, ze), win_w + [ww["span"] + (zf, ww["z"][1])],
                             t, M("siding"))
        self.wall_with_holes("ed_wall_e", "x", x1 - t / 2, (y0, y1), (zf, ze), [(y0 + 4, y0 + 5.2, 1.5, 2.7)], t,
                             M("siding"))
        south = self.wall_with_holes("ed_wall_s", "y", y0 + t / 2, (x0, x1), (zf, ze),
                                     [(x0 + 1.5, x0 + 2.7, 1.5, 2.7), (x0 + 4.0, x0 + 5.2, 1.5, 2.7),
                                      (x0 + 7.0, x0 + 8.0, 0.6, 2.7), (x0 + 1.5, x0 + 2.7, 4.3, 5.5),
                                      (x0 + 7.5, x0 + 8.7, 4.3, 5.5)], t, M("siding"))
        north = self.wall_with_holes("ed_wall_n", "y", y1 - t / 2, (x0, x1), (zf, ze),
                                     [(196.4, 197.6, 1.65, 2.75), wn["span"] + (zf, wn["z"][1]),
                                      (x0 + 8.0, x0 + 9.2, 1.5, 2.7)], t, M("siding"))
        self.peel("house_south", south, (0.0, 0.0, -7.2))
        self.peel("house_north", north, (0.0, 0.0, -7.2))
        # window glass (thin, slightly reflective) in the fixed + peeled walls
        glass = []
        for (s0, s1, z0, z1) in win_w:
            glass.append(("box", (x0 + 0.02, (s0 + s1) / 2, (z0 + z1) / 2), (0.02, s1 - s0, z1 - z0), 0))
        multi("ed_hero_glass_w", glass, [M("clear_glass")])
        # roof: gable ridge along X; front (south) and rear (north) planes lift off
        ov = 0.45
        ym = (y0 + y1) / 2
        for name, ya, grp in (("front", y0 - ov, "house_south"), ("rear", y1 + ov, "house_north")):
            bm = bmesh.new()
            v = [bm.verts.new(p) for p in ((x0 - ov, ya, ze - 0.15), (x1 + ov, ya, ze - 0.15), (x1 + ov, ym, zr),
                                           (x0 - ov, ym, zr))]
            f = bm.faces.new(v)
            bmesh.ops.solidify(bm, geom=[f], thickness=0.12)
            o = B.mesh_obj("ed_roof_" + name, bm, [M("shingles")])
            self.peel(grp, o, (0.0, -9.0 if name == "front" else 9.0, 6.0))
        bm = bmesh.new()
        for xg in (x0, x1):
            vs = [bm.verts.new((xg, y0, ze - 0.15)), bm.verts.new((xg, y1, ze - 0.15)), bm.verts.new((xg, ym, zr))]
            bm.faces.new(vs)
        B.mesh_obj("ed_roof_gables", bm, [M("siding")])
        # first floor deck + floor hatch (peel), second floor slab
        hatch = (199.0, 202.0, 155.2, 158.2)
        quads("ed_floor1", P.rect_minus_holes((x0, x1, y0, y1), [hatch]), zf, M("wood"))
        hob = box("ed_floor_hatch", ((hatch[0] + hatch[1]) / 2, (hatch[2] + hatch[3]) / 2, zf), (3.0, 3.0, 0.02),
                  M("wood"))
        self.peel("house_floor_hatch", hob, (3.2, 0.0, -0.1))
        box("ed_floor_slab_bottom", ((x0 + x1) / 2, (y0 + y1) / 2, zf - 0.22), (x1 - x0, y1 - y0, 0.02), M("paint"))
        box("ed_floor2", ((x0 + x1) / 2, (y0 + y1) / 2, H["floor2"] - 0.12), (x1 - x0, y1 - y0, 0.24), M("paint"))
        # garage, porch, driveway, walk, mailbox, pickup
        gx0, gx1, gy0, gy1 = H["garage"]
        bm = bmesh.new()
        box_bm(bm, ((gx0 + gx1) / 2, (gy0 + gy1) / 2, 1.6), (gx1 - gx0, gy1 - gy0, 3.2), 0)
        S.bm_prism_x(bm, gx0 - 0.3, gx1 + 0.3, [(gy0 - 0.4, 3.1), (gy1 + 0.4, 3.1), ((gy0 + gy1) / 2, 4.6)], 1)
        box_bm(bm, ((gx0 + gx1) / 2, gy0 - 0.03, 1.1), (4.9, 0.06, 2.15), 2)
        B.mesh_obj("ed_garage", bm, [M("siding"), M("shingles"), M("trim")])
        porch = [("box", (199.0, 150.8, 0.2), (6.0, 2.4, 0.4), 0)] + \
                [("box", (xp, 149.75, 1.75), (0.16, 0.16, 2.7), 1) for xp in (196.2, 201.8)]
        multi("ed_porch", porch, [M("wood"), M("trim")])
        quads("ed_walk", [(200.6, 201.8, 147.5, 149.6), (207.0, 211.0, 145.5, 152.0)], 0.045, M("concrete"))
        multi("ed_mailbox", [("cyl", (204.0, 146.2, 0.0), (204.0, 146.2, 1.0), 0.05, 0.05, 6, 0),
                             ("box", (204.0, 146.2, 1.12), (0.22, 0.5, 0.25), 1)], [M("wood"), M("steel_dark")])
        self.car("ed_hero_drive_pickup", "pickup", 209.0, 148.8, 0.0, "2c3e57")
        self.scatter_trees("ed_trees_hero", [(188.0, 165.0), (213.5, 168.0), (186.5, 147.0)])
        # west side yard: condenser + line set, smart meter + mast, wall slices
        self.build_condenser()
        self.build_meter()
        self.build_wall_slices()

    def build_condenser(self):
        M = self.M.m
        x, y = 192.6, 159.5
        box("ed_cond_pad", (x, y, 0.05), (1.0, 1.0, 0.1), M("concrete"))
        multi("ed_cond_body", [("box", (x, y, 0.5), (0.8, 0.8, 0.8), 0), ("cyl", (x, y, 0.85), (x, y, 0.88), 0.32,
                                                                              0.32, 16, 1)],
              [M("grey_box"), M("steel_dark")])
        lid = multi("ed_cond_grille", [("cyl", (x, y, 0.9), (x, y, 0.95), 0.4, 0.4, 16, 0)], [M("fence")])
        self.peel("condenser_lid", lid, (0.0, 0.0, 0.6))
        multi("ed_cond_fan", [("box", (x, y, 0.89), (0.55, 0.08, 0.01), 0), ("box", (x, y, 0.89), (0.08, 0.55, 0.01), 0)],
              [M("steel_dark")])
        for i in range(3):                       # heat leaving: amber shimmer ribbons (graphic)
            pts = [(x - 0.15 + 0.15 * i + 0.05 * math.sin(k * 0.9 + i), y, 1.0 + 0.12 * k) for k in range(10)]
            curve("ed_cond_heat_%d" % i, pts, 0.01, M("amber_alpha"))
        curve("ed_lineset_suction", [(x + 0.4, y, 0.35), (193.5, y, 0.4), (194.0, y, 0.4), (194.6, y, 0.4),
                                     (195.6, 159.1, -0.2), (196.0, 159.0, -0.45)], 0.022, M("foam_black"))
        curve("ed_lineset_liquid", [(x + 0.4, y + 0.08, 0.3), (193.5, y + 0.08, 0.36), (194.0, y + 0.08, 0.36),
                                    (194.6, y + 0.08, 0.36), (195.6, 159.2, -0.25), (196.0, 159.1, -0.5)], 0.006,
              M("copper"))

    def build_meter(self):
        M = self.M.m
        x, y, z = 193.9, 155.0, 1.5
        multi("ed_meter", [("box", (x - 0.06, y, z), (0.12, 0.3, 0.42), 0),
                           ("cyl", (x - 0.12, y, z + 0.03), (x - 0.24, y, z + 0.03), 0.085, 0.08, 16, 1),
                           ("cyl", (x - 0.05, y, z + 0.21), (x - 0.05, y, 7.0), 0.03, 0.03, 8, 0),
                           ("cyl", (x - 0.05, y, z - 0.21), (x - 0.05, y, -0.1), 0.02, 0.02, 8, 0)],
              [M("grey_box"), M("clear_glass")])

    def build_wall_slices(self):
        """S2 wall slices: cut edges (charcoal cap + teal line), the layers inside, and the siding lid."""
        M = self.M.m
        ww = P.SLICES["wall_west"]
        s0, s1 = ww["span"]
        z0, z1 = ww["z"]
        x = ww["at"]
        parts = [("box", (x + 0.07, (s0 + s1) / 2, (z0 + z1) / 2), (0.14, s1 - s0, z1 - z0), 1),
                 ("box", (x + 0.03, s0 + 0.2, (z0 + z1) / 2), (0.06, 0.05, z1 - z0), 2),
                 ("box", (x + 0.03, s1 - 0.2, (z0 + z1) / 2), (0.06, 0.05, z1 - z0), 2)]
        for (a, b) in (((s0, z0), (s1, z0)), ((s0, z1), (s1, z1))):
            parts.append(("box", (x - 0.01, (a[0] + b[0]) / 2, a[1]), (0.03, s1 - s0, 0.03), 0))
        for sv in (s0, s1):
            parts.append(("box", (x - 0.01, sv, (z0 + z1) / 2), (0.03, 0.03, z1 - z0), 0))
        multi("ed_wallslice_w_edges", parts, [M("cap"), M("insulation"), M("stud")])
        lid = box("ed_wallslice_w_lid", (x - 0.02, (s0 + s1) / 2, (z0 + z1) / 2), (0.04, s1 - s0, z1 - z0),
                  M("siding"))
        self.lid("wall_west", lid, ww["slide"])
        wn = P.SLICES["wall_north"]
        a0, a1 = wn["span"]
        z0, z1 = wn["z"]
        y = wn["at"]
        multi("ed_wallslice_n_inside", [("box", ((a0 + a1) / 2, y - 0.075, (z0 + z1) / 2), (a1 - a0, 0.15, z1 - z0), 0),
                                        ("box", (a0 + 0.2, y - 0.075, (z0 + z1) / 2), (0.05, 0.14, z1 - z0), 1),
                                        ("box", (a1 - 0.2, y - 0.075, (z0 + z1) / 2), (0.05, 0.14, z1 - z0), 1),
                                        ("box", ((a0 + a1) / 2, y - 0.14, (z0 + z1) / 2), (a1 - a0, 0.012, z1 - z0), 2)],
              [M("insulation"), M("stud"), M("drywall")])
        for xp, mat in ((196.85, "pex_red"), (197.15, "pex_blue")):
            cyl("ed_pex_%s" % mat, (xp, y - 0.08, -1.6), (xp, y - 0.08, 1.45), 0.009, 0.009, M(mat), seg=8)
            cyl("ed_valve_%s" % mat, (xp, y - 0.13, 1.25), (xp, y - 0.19, 1.25), 0.02, 0.02, M("galv"), seg=8)
        lid = box("ed_wallslice_n_lid", ((a0 + a1) / 2, y + 0.02, (z0 + z1) / 2), (a1 - a0, 0.04, z1 - z0), M("siding"))
        self.lid("wall_north", lid, wn["slide"])

    def build_person_phone(self):
        """Stylised person on the front walk facing north (no face close-up), right hand holding the phone host."""
        M = self.M.m
        px, py = 201.2, 148.5
        cloth, skin, jeans = S.pbr("ed_shirt", hexc("3d6f8f"), 0.8), S.pbr("ed_skin", hexc("c99a7c"), 0.6), \
            S.pbr("ed_jeans", hexc("34465e"), 0.85)
        multi("ed_person", [("cyl", (px - 0.1, py, 0.0), (px - 0.1, py, 0.9), 0.07, 0.07, 8, 2),
                            ("cyl", (px + 0.1, py, 0.0), (px + 0.1, py, 0.9), 0.07, 0.07, 8, 2),
                            ("box", (px, py, 1.17), (0.42, 0.24, 0.6), 0),
                            ("cyl", (px, py, 1.45), (px, py, 1.55), 0.05, 0.05, 8, 1),
                            ("cyl", (px - 0.24, py, 1.42), (px - 0.27, py + 0.05, 0.95), 0.045, 0.04, 8, 0),
                            ("cyl", (px + 0.24, py, 1.42), (px + 0.27, py - 0.02, 1.12), 0.045, 0.042, 8, 0),
                            ("cyl", (px + 0.27, py - 0.02, 1.12), (201.45, 148.64, 1.245), 0.04, 0.035, 8, 1)],
              [cloth, skin, jeans])
        bm = bmesh.new()
        B.bm_sphere(bm, (px, py, 1.66), (0.1, 0.11, 0.12), 2, 0)
        B.mesh_obj("ed_person_head", bm, [skin], smooth=True)
        box("ed_person_hand", (201.45, 148.66, 1.255), (0.08, 0.06, 0.035), skin)
        e = host_empty(P.PHONE)
        self.hosts["phone"] = e
        w, h, d = (v / 1000.0 for v in P.PHONE_SIZE_MM)
        box("ed_phone_back", (0, 0, -d / 2 + 0.0008), (w, h, 0.0016), M("phone_metal"), parent=e)
        frame = [("box", (sx * (w / 2 - 0.0007), 0, 0), (0.0014, h, d), 0) for sx in (-1, 1)] + \
                [("box", (0, sy * (h / 2 - 0.0007), 0), (w, 0.0014, d), 0) for sy in (-1, 1)] + \
                [("box", (sx * (w / 2 - 0.0007), 0.052, 0), (0.0016, 0.0012, d * 1.01), 1) for sx in (-1, 1)]
        multi("ed_phone_frame", frame, [M("phone_metal"), M("plastic_gap")], parent=e)
        disp = multi("ed_phone_display", [("box", (0, 0, d / 2 - 0.0008), (w - 0.002, h - 0.002, 0.0016), 0)] +
                     [("box", (-0.022 + 0.022 * (i % 3), 0.05 - 0.02 * (i // 3), d / 2 + 0.00005), (0.014, 0.014, 0.0001),
                       1) for i in range(15)], [M("glass"), M("screen_tiles")], parent=e)
        self.peel("phone_display", disp, (0.09, 0.0, 0.0))

    # ------------------------------------------------------------ W3 interior (Z_HOUSE_INT) + basement
    def build_house_interior(self):
        self.zone("Z_HOUSE_INT")
        M = self.M.m
        H = P.HOUSE
        zf, zc = 0.6 - 0.25, H["floor2"] - 0.24
        paint = M("paint")
        bm = bmesh.new()
        B.bm_segment_box(bm, (194.15, 157.5), (198.0, 157.5), zf, zc, 0.12, 0)        # living | kitchen (door gap)
        B.bm_segment_box(bm, (199.0, 157.5), (200.5, 157.5), zf, zc, 0.12, 0)
        B.bm_segment_box(bm, (200.5, 152.15), (200.5, 155.6), zf, zc, 0.12, 0)        # living/kitchen | hall
        B.bm_segment_box(bm, (200.5, 156.4), (200.5, 161.85), zf, zc, 0.12, 0)
        B.bm_segment_box(bm, (203.0, 155.0), (203.0, 159.0), zf, zc, 0.12, 0)
        B.mesh_obj("ed_partitions", bm, [paint])
        for i, (x, y) in enumerate(((196.0, 154.5), (198.8, 154.5), (197.0, 160.0), (199.5, 160.0), (201.7, 157.0))):
            box("ed_ceiling_light_%d" % i, (x, y, zc - 0.02), (0.6, 0.6, 0.03), M("ceiling_panel"))
            area_light("ed_room_light_%d" % i, (x, y, zc - 0.05), 1.2, 60.0, color=(1.0, 0.95, 0.88))
        # living room: couch, shelf + router, TV + console, plant
        multi("ed_couch", [("box", (197.4, 153.0, 0.58), (2.2, 0.9, 0.45), 0), ("box", (197.4, 152.6, 0.95),
                                                                               (2.2, 0.2, 0.55), 0)],
              [S.pbr("ed_couch_fab", hexc("8a9aa6"), 0.9, var=0.05)])
        box("ed_shelf_router", (200.1, 156.8, 0.375 + 0.5), (0.6, 0.5, 1.0), M("wood"))
        box("ed_shelf_top", (200.1, 156.8, 1.39), (0.6, 0.5, 0.04), M("wood"))
        multi("ed_router", [("box", (200.0, 156.8, 1.43), (0.25, 0.15, 0.04), 0),
                            ("cyl", (199.9, 156.86, 1.45), (199.88, 156.88, 1.62), 0.006, 0.005, 6, 0),
                            ("cyl", (200.1, 156.86, 1.45), (200.12, 156.88, 1.62), 0.006, 0.005, 6, 0)] +
              [("box", (199.93 + 0.03 * i, 156.724, 1.43), (0.008, 0.003, 0.006), 1) for i in range(5)],
              [M("steel_dark"), M("led_blue")])
        multi("ed_tv", [("box", (197.2, 157.41, 1.9), (1.24, 0.05, 0.72), 0),
                        ("box", (197.2, 157.383, 1.9), (1.18, 0.004, 0.66), 1),
                        ("box", (197.2, 157.2, 0.6), (1.6, 0.4, 0.5), 2)], [M("chip"), M("tv_screen"), M("wood")])
        multi("ed_plant", [("cyl", (194.6, 157.0, 0.35), (194.6, 157.0, 0.75), 0.16, 0.2, 10, 0)], [M("paint_warm")])
        bm = bmesh.new()
        B.bm_sphere(bm, (194.6, 157.0, 1.05), (0.35, 0.35, 0.4), 2, 0, jitter=0.15, seed=3)
        B.mesh_obj("ed_plant_leaves", bm, [M("leaf")])
        # kitchen: base + upper cabinets, sink + faucet + water stream, range, fridge, microwave (casing peels)
        top_z = 0.35 + 0.91 + 0.25
        multi("ed_kitchen_base", [("box", (197.35, 161.55, (0.35 + top_z) / 2), (6.0, 0.6, top_z - 0.35), 0)],
              [M("paint_warm")])
        quads("ed_counter", P.rect_minus_holes((194.35, 200.35, 161.25, 161.85), [(196.65, 197.35, 161.35, 161.75)]),
              top_z, M("tile"))
        box("ed_sink_basin", (197.0, 161.55, top_z - 0.1), (0.7, 0.4, 0.2), M("galv"))
        tip = P.STOPS["faucet_kitchen"]["anc"]
        curve("ed_faucet", [(197.0, 161.78, top_z), (197.0, 161.78, top_z + 0.32), (197.0, 161.7, top_z + 0.38),
                            (tip[0], tip[1], tip[2] + 0.02)], 0.012, M("galv"))
        cyl("ed_water_stream", (tip[0], tip[1], tip[2]), (tip[0], tip[1], top_z - 0.15), 0.005, 0.0045,
            M("water_vol"), seg=8)
        uppers = [("box", (195.5, 161.68, 2.4), (2.2, 0.34, 0.8), 0),
                  ("box", (198.15, 161.68, 2.4), (0.9, 0.34, 0.8), 0), ("box", (199.2, 161.68, 2.55), (0.76, 0.34, 0.5), 0),
                  ("box", (199.95, 161.68, 2.4), (0.7, 0.34, 0.8), 0)]
        multi("ed_kitchen_uppers", uppers, [M("paint_warm")])
        multi("ed_range", [("box", (199.2, 161.55, (0.35 + top_z) / 2), (0.76, 0.62, top_z - 0.35), 0)],
              [M("white_metal")])
        box("ed_fridge", (194.75, 161.45, 0.35 + 0.9), (0.8, 0.75, 1.8), M("white_metal"))
        mw = P.MICROWAVE
        yc = (mw["y_front"] + mw["y_back"]) / 2
        zc_ = (mw["z0"] + mw["z1"]) / 2
        multi("ed_mw_body", [("box", (mw["x"], yc, mw["z0"] + 0.01), (mw["w"], mw["y_back"] - mw["y_front"], 0.02), 0),
                             ("box", (mw["x"] + 0.25, yc, zc_), (0.12, 0.3, 0.3), 1),
                             ("box", (mw["x"] + 0.15, yc + 0.05, zc_ + 0.1), (0.15, 0.08, 0.06), 2),
                             ("cyl", (mw["x"] - 0.07, yc, mw["z0"] + 0.03), (mw["x"] - 0.07, yc, mw["z0"] + 0.04),
                              0.13, 0.13, 16, 3)],
              [M("white_metal"), M("steel_dark"), M("copper"), M("clear_glass")])
        casing = multi("ed_mw_casing", [("box", (mw["x"], yc, mw["z1"] - 0.01), (mw["w"], mw["y_back"] - mw["y_front"],
                                                                                   0.02), 0),
                                        ("box", (mw["x"] - mw["w"] / 2 + 0.01, yc, zc_), (0.02, mw["y_back"] -
                                                                                           mw["y_front"], 0.4), 0),
                                        ("box", (mw["x"] + mw["w"] / 2 - 0.01, yc, zc_), (0.02, mw["y_back"] -
                                                                                           mw["y_front"], 0.4), 0)],
                       [M("white_metal")])
        self.peel("mw_casing", casing, (0.0, 0.0, 0.35))
        multi("ed_mw_door", [("box", (mw["x"] + 0.29, mw["y_front"] - 0.015, zc_), (0.16, 0.03, 0.4), 0),
                             ("box", (mw["x"] - 0.08, mw["y_front"] - 0.029, zc_), (0.58, 0.002, 0.36), 1),
                             ("box", (mw["x"] - 0.08, mw["y_front"] - 0.002, zc_), (0.58, 0.002, 0.36), 1),
                             ("box", (mw["x"] - 0.08, mw["y_front"] - 0.015, zc_ + 0.19), (0.6, 0.03, 0.02), 0),
                             ("box", (mw["x"] - 0.08, mw["y_front"] - 0.015, zc_ - 0.19), (0.6, 0.03, 0.02), 0)],
              [M("chip"), M("clear_glass")])
        cyl("ed_mw_soup", (mw["x"] - 0.07, yc, mw["z0"] + 0.04), (mw["x"] - 0.07, yc, mw["z0"] + 0.11), 0.07, 0.08,
            M("paint_warm"), seg=16)
        # kitchen window glass + bright back yard (sky) beyond
        box("ed_kitchen_window", (197.0, 161.93, 2.2), (1.2, 0.02, 1.1), M("clear_glass"))
        # hall: thermostat (round, glowing teal ring, no digits) on the x=200.5 wall facing +x
        anc = P.STOPS["thermostat"]["anc"]
        cyl("ed_thermostat", (200.56, anc[1], anc[2]), (200.585, anc[1], anc[2]), 0.045, 0.045, M("white_metal"), seg=24)
        curve("ed_thermostat_ring", ring_pts((200.587, anc[1], anc[2]), 0.035, axis="x"), 0.003, M("teal_glow"))
        box("ed_hall_table", (202.6, 156.0, 0.75), (0.4, 1.0, 0.8), M("wood"))

    def build_basement(self):
        self.zone("Z_HOUSE_BASEMENT")
        M = self.M.m
        H = P.HOUSE
        x0, x1, y0, y1 = H["x0"], H["x1"], H["y0"], H["y1"]
        quads("ed_basement_floor", [(x0, x1, y0, y1)], -2.0, M("concrete"))
        quads("ed_basement_ceiling", [(x0, x1, y0, y1)], 0.12, M("paint"))
        area_light("ed_basement_softbox", (197.5, 157.0, 0.05), 4.0, 650.0, size_y=3.0, color=(1.0, 0.97, 0.93))
        area_light("ed_basement_fill", (199.5, 155.0, -0.3), 2.0, 180.0, rot=(math.radians(55), 0.0, math.radians(30)))
        x, y = 196.0, 159.0
        box("ed_furnace", (x, y, -1.4), (0.55, 0.75, 1.2), M("white_metal"))
        bm = bmesh.new()
        B.bm_segment_box(bm, (x - 0.3, y - 0.4), (x - 0.3, y + 0.4), -0.8, -0.3, 0.02, 0)
        B.bm_segment_box(bm, (x + 0.3, y - 0.4), (x + 0.3, y + 0.4), -0.8, -0.3, 0.02, 0)
        B.bm_segment_box(bm, (x - 0.3, y + 0.4), (x + 0.3, y + 0.4), -0.8, -0.3, 0.02, 0)
        B.mesh_obj("ed_coil_cabinet", bm, [M("white_metal")])
        panel = box("ed_coil_panel", (x, y - 0.4, -0.55), (0.6, 0.02, 0.5), M("white_metal"))
        self.peel("coil_panel", panel, (0.0, -0.6, 0.0))
        for sx in (-1, 1):                                       # the A-coil: two slanted fin slabs
            bm = bmesh.new()
            v = [bm.verts.new(p) for p in ((x + sx * 0.25, y - 0.35, -0.78), (x + sx * 0.25, y + 0.35, -0.78),
                                           (x, y + 0.35, -0.33), (x, y - 0.35, -0.33))]
            f = bm.faces.new(v)
            bmesh.ops.solidify(bm, geom=[f], thickness=0.03)
            B.mesh_obj("ed_acoil_%d" % sx, bm, [S.corrugated_mat("ed_coil_fins", hexc("b8bcc0"), 0.004, 0.4, 0.8)])
        rng = random.Random(9)
        drops = [("box", (x + rng.uniform(-0.2, 0.2), y - 0.36, rng.uniform(-0.75, -0.4)), (0.006, 0.006, 0.008), 0)
                 for _ in range(30)]
        multi("ed_coil_droplets", drops, [M("water_vol")])
        box("ed_drain_pan", (x, y, -0.79), (0.6, 0.8, 0.03), M("steel_dark"))
        cyl("ed_drain_line", (x + 0.3, y - 0.3, -0.78), (x + 0.9, y - 0.3, -1.95), 0.012, 0.012, M("paint"), seg=8)
        box("ed_plenum", (x, y, -0.1), (0.6, 0.8, 0.4), M("galv"))
        box("ed_duct_main", (x + 3.0, y, 0.0), (5.4, 0.4, 0.25), M("galv"))
        cyl("ed_water_heater", (194.8, 160.8, -2.0), (194.8, 160.8, -0.5), 0.28, 0.28, M("white_metal"), seg=16)
        # service line in -> meter -> riser to the kitchen wall pipes
        cyl("ed_service_in", (200.0, 152.0, -1.6), (200.0, 153.0, -1.6), 0.013, 0.013, M("copper"), seg=8)
        box("ed_water_meter", (200.0, 153.15, -1.6), (0.12, 0.2, 0.12), M("galv"))
        curve("ed_main_riser", [(200.0, 153.3, -1.6), (200.0, 161.7, -1.6), (197.0, 161.7, -1.6),
                                (197.0, 161.85, -1.6)], 0.013, M("copper"))

    # ------------------------------------------------------------ Z_STREET_SLICE (Maple St utilities)
    def build_street_slice(self):
        self.zone("Z_STREET_SLICE")
        M = self.M.m
        r0 = P.SLICES["maple_west"]["rect"]
        r1 = P.SLICES["maple_east"]["rect"]
        rect = (r0[0], r1[1], r0[2], r0[3])
        self.slice_box("ed_maple_slice", rect, P.SLICES["maple_west"]["depth"])
        xa, xb = rect[0] - 0.2, rect[1] + 0.2
        cyl("ed_water_main", (xa, 141.0, -1.6), (xb, 141.0, -1.6), 0.1, 0.1, M("iron_main"), seg=20)
        multi("ed_main_saddle", [("cyl", (200.0, 141.0, -1.6), (200.0, 141.0, -1.47), 0.12, 0.12, 16, 0),
                                 ("box", (200.0, 141.0, -1.45), (0.08, 0.08, 0.06), 1)], [M("iron_main"), M("galv")])
        curve("ed_service_line", [(200.0, 141.0, -1.45), (200.0, 141.6, -1.42), (200.0, 143.0, -1.5),
                                  (200.0, 144.3, -1.6)], 0.013, M("copper"))
        cyl("ed_gas_line", (xa, 142.6, -0.9), (xb, 142.6, -0.9), 0.05, 0.05, M("gas_yellow"), seg=12)
        ducts = [((138.35, -0.83), "orange_duct"), ((138.65, -0.83), "blue_duct"), ((138.35, -1.0), "blue_duct"),
                 ((138.65, -1.0), "orange_duct")]
        for i, ((yy, zz), mat) in enumerate(ducts):
            if i == 0:
                continue
            cyl("ed_duct_%d" % i, (xa, yy, zz), (xb, yy, zz), 0.05, 0.05, M(mat), seg=16)
        # duct 0 sliced lengthwise (lower half kept) with fiber strands inside (emissive tips at the open end)
        bm = bmesh.new()
        B.bm_cyl(bm, (xa, 138.35, -0.83), (xb, 138.35, -0.83), 0.05, 0.05, 16, 0, False)
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0.0, 138.35, -0.83), plane_no=(0.0, 0.0, 1.0),
                               clear_outer=True)
        B.mesh_obj("ed_duct_0_half", bm, [M("orange_duct")])
        strands = []
        rng = random.Random(4)
        for k in range(12):
            yy, zz = 138.35 + rng.uniform(-0.03, 0.03), -0.83 - rng.uniform(0.0, 0.035)
            strands.append(("cyl", (214.0, yy, zz), (xb, yy, zz), 0.003, 0.003, 6, 0))
            strands.append(("cyl", (214.0, yy, zz), (214.02, yy, zz), 0.0035, 0.0035, 6, 1))
        multi("ed_fiber_strands", strands, [M("white_metal"), M("teal_glow")])
        box("ed_handhole", (232.0, 138.5, -0.5), (1.2, 0.8, 1.0), M("concrete"))
        area_light("ed_slice_fill", (214.0, 132.6, 0.9), 20.0, 900.0, size_y=1.2, color=(1.0, 0.98, 0.95),
                   rot=(math.radians(-55), 0.0, 0.0))

    # ------------------------------------------------------------ Z_TOWER (cell tower + compound + handhole)
    def build_tower(self):
        self.zone("Z_TOWER")
        M = self.M.m
        cx, cy = 262.0, 226.0
        quads("ed_tower_gravel", P.rect_minus_holes((254.5, 269.5, 218.5, 233.5), [P.SLICES["handhole"]["rect"]]),
              0.012, M("gravel"))
        self.fence("ed_tower_fence", 254.5, 269.5, 218.5, 233.5, gap=(258.0, 218.5))
        cyl("ed_monopole", (cx, cy, 0.0), (cx, cy, 40.0), 0.75, 0.35, M("galv"), seg=16)
        parts = []
        for k in range(3):
            a = math.radians(90 + 120 * k)
            ux, uy = math.cos(a), math.sin(a)
            parts.append(("cyl", (cx, cy, 36.5), (cx + ux * 2.2, cy + uy * 2.2, 36.5), 0.08, 0.08, 6, 0))
            for j in (-1, 0, 1):
                px, py = cx + ux * 2.3 - uy * j * 0.8, cy + uy * 2.3 + ux * j * 0.8
                parts.append(("box", (px, py, 37.5), (0.32, 0.32, 1.8), 1))
                parts.append(("box", (px - ux * 0.3, py - uy * 0.3, 36.7), (0.25, 0.25, 0.35), 2))
        multi("ed_tower_sectors", parts, [M("galv"), M("white_metal"), M("grey_box")])
        cyl("ed_tower_trunk", (cx + 0.5, cy, 1.0), (cx + 0.4, cy, 36.0), 0.06, 0.06, M("steel_dark"), seg=6)
        # cabinets (door peels), shelter, cable bridge
        for i, x in enumerate((265.0, 267.0)):
            box("ed_tower_cab_%d" % i, (x, 223.0, 0.95), (0.8, 0.7, 1.8), M("grey_box"))
            door = box("ed_tower_cab_door_%d" % i, (x, 222.63, 0.95), (0.76, 0.03, 1.74), M("grey_box"))
            if i == 0:
                self.peel("tower_cabinet_door", door, (0.85, 0.0, 0.0))
                multi("ed_tower_cab_rack", [("box", (x, 222.75, 0.6 + 0.25 * k), (0.6, 0.15, 0.08), 0) for k in range(5)] +
                      [("box", (x - 0.2 + 0.1 * k, 222.672, 0.62 + 0.25 * (k % 5)), (0.015, 0.004, 0.015), 1)
                       for k in range(5)], [M("steel_dark"), M("led_green")])
        box("ed_tower_shelter", (258.0, 229.0, 1.5), (3.0, 4.0, 3.0), M("panel_grey"))
        box("ed_tower_bridge", (260.0, 227.5, 2.6), (4.0, 0.3, 0.08), M("galv"))
        hh = P.SLICES["handhole"]
        self.slice_box("ed_tower_handhole", hh["rect"], hh["depth"])
        cyl("ed_tower_conduit", (263.0, 220.0, -0.7), (244.5, 220.0, -0.7), 0.05, 0.05, M("orange_duct"), seg=12)

    # ------------------------------------------------------------ Z_INDUSTRIAL_DC + Z_DC_INT
    def build_data_center(self):
        self.zone("Z_INDUSTRIAL_DC")
        M = self.M.m
        x0, x1, y0, y1, h = -465.0, -375.0, 300.0, 360.0, 12.0
        bm = bmesh.new()
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            B.bm_segment_box(bm, a, b, 0.0, h, 0.4, 0)
        B.mesh_obj("ed_dc_walls", bm, [M("panel_grey")])
        se = (-420.0, x1, y0, 330.0)
        roofs = P.rect_minus_holes((x0, x1, y0, y1), [se])
        bm = bmesh.new()
        for (a, b, c, d) in roofs:
            box_bm(bm, ((a + b) / 2, (c + d) / 2, h + 0.15), (b - a, d - c, 0.3), 0)
        B.mesh_obj("ed_dc_roof", bm, [M("roof_membrane")])
        sq = box("ed_dc_roof_se", ((se[0] + se[1]) / 2, (se[2] + se[3]) / 2, h + 0.15),
                 (se[1] - se[0], se[3] - se[2], 0.3), M("roof_membrane"))
        self.peel("dc_roof", sq, (60.0, 0.0, 0.0))
        bm = bmesh.new()
        box_bm(bm, (0, 0, 1.2), (4.0, 2.2, 2.4), 0)
        B.bm_cyl(bm, (-1.0, 0, 2.4), (-1.0, 0, 2.6), 0.8, 0.8, 12, 1)
        B.bm_cyl(bm, (1.0, 0, 2.4), (1.0, 0, 2.6), 0.8, 0.8, 12, 1)
        chill = B.template_obj("ed_chiller_t", S.mesh_from_bm("ed_chiller_m", bm, [M("white_metal"), M("steel_dark")]))
        pts = [(x0 + 8 + 9 * i, y1 - 8 - 8 * j, h + 0.3) for i in range(5) for j in range(3)]
        B.scatter_gn("ed_chillers", chill, pts)
        gens = [("box", (x0 + 10 + 12 * i, y0 - 12.0, 1.4), (10.0, 3.0, 2.8), 0) for i in range(6)]
        multi("ed_generators", gens, [M("white_metal")])
        multi("ed_dc_transformers", [("box", (x0 - 14.0, y0 + 10 + 9 * i, 1.5), (4.0, 3.0, 3.0), 0) for i in range(3)],
              [M("grey_box")])
        self.fence("ed_dc_fence", x0 - 25.0, x1 + 15.0, y0 - 25.0, y1 + 12.0, gap=(x1 + 15.0, 320.0))
        quads("ed_dc_lot", [(x0 - 22.0, x1 + 12.0, y0 - 22.0, y0 - 4.0)], 0.03, M("asphalt"))
        for i in range(8):
            self.car("ed_car_dc_%d" % i, self.rng.choice(("sedan", "suv")), x1 - 5 - 6.5 * i, y0 - 18.0, 0.0)

    def build_dc_interior(self):
        self.zone("Z_DC_INT")
        M = self.M.m
        hx0, hx1, hy0, hy1 = -410.0, -380.0, 305.0, 325.0
        quads("ed_hall_floor", [(hx0, hx1, hy0, hy1)], 0.3, M("tile"))
        quads("ed_hall_ceiling", [(hx0, hx1, hy0, hy1)], 5.0, M("paint"))
        bm = bmesh.new()
        for (a, b) in (((hx0, hy0), (hx1, hy0)), ((hx0, hy1), (hx1, hy1)), ((hx0, hy0), (hx0, hy1))):
            B.bm_segment_box(bm, a, b, 0.3, 5.0, 0.2, 0)
        B.mesh_obj("ed_hall_walls", bm, [M("paint")])
        bm = bmesh.new()
        box_bm(bm, (0, 0, 1.05), (0.6, 1.2, 2.1), 0)
        box_bm(bm, (0, 0.601, 1.05), (0.56, 0.004, 2.0), 1)
        rack = S.mesh_from_bm("ed_rack", bm, [M("chip"), M("led_green")])
        n = 0
        for yy, yaw in ((312.0, 0.0), (318.0, math.pi)):
            for i in range(12):
                S.obj("ed_rack_%d" % n, rack, (-404.0 + 0.62 * i * 2.0, yy, 0.3), (0, 0, yaw))
                n += 1
        box("ed_fiber_tray", (-395.0, 315.0, 2.75), (24.0, 0.3, 0.08), M("gas_yellow"))
        strips = [("box", (-395.0, 315.0 + dy, 4.95), (26.0, 0.2, 0.03), 0) for dy in (-4, 0, 4)]
        multi("ed_hall_strips", strips, [M("ceiling_panel")])
        area_light("ed_hall_light_a", (-400.0, 315.0, 4.8), 6.0, 1200.0, color=(0.95, 0.98, 1.0))
        area_light("ed_hall_light_b", (-388.0, 315.0, 4.8), 6.0, 1200.0, color=(0.95, 0.98, 1.0))

    # ------------------------------------------------------------ Z_POWER (substation + transmission line)
    def build_power(self):
        self.zone("Z_POWER")
        M = self.M.m
        cx, cy = 430.0, -330.0
        quads("ed_sub_gravel", [(cx - 40, cx + 40, cy - 30, cy + 30)], 0.012, M("gravel"))
        self.fence("ed_sub_fence", cx - 40, cx + 40, cy - 30, cy + 30, h=2.5, gap=(cx - 40, cy))
        parts = []
        for i, tx in enumerate((cx - 6.0, cx + 10.0)):
            parts.append(("box", (tx, cy, 2.5), (5.0, 3.5, 5.0), 0))
            for k in range(8):
                parts.append(("box", (tx - 2.2 + 0.63 * k, cy - 2.2, 2.2), (0.05, 1.0, 3.6), 0))
            for k in (-1, 0, 1):
                parts.append(("cyl", (tx + k * 1.2, cy + 0.8, 5.0), (tx + k * 1.2, cy + 0.8, 7.0), 0.15, 0.1, 8, 1))
        multi("ed_sub_transformers", parts, [M("grey_box"), M("insulator")])
        frames = []
        for fx in (cx - 25, cx - 15, cx + 25, cx + 35):
            for sy in (-8, 8):
                frames.append(("box", (fx, cy + sy, 7.5), (0.4, 0.4, 15.0), 0))
            frames.append(("box", (fx, cy, 14.8), (0.4, 16.4, 0.5), 0))
            for k in (-4, 0, 4):
                frames.append(("cyl", (fx, cy + k, 14.5), (fx, cy + k, 12.8), 0.12, 0.12, 8, 1))
        for k in (-4, 0, 4):
            frames.append(("cyl", (cx - 25, cy + k, 12.6), (cx + 35, cy + k, 12.6), 0.06, 0.06, 6, 0))
        multi("ed_sub_frames", frames, [M("galv"), M("insulator")])
        box("ed_sub_control", (cx - 30.0, cy + 22.0, 2.0), (8.0, 5.0, 4.0), M("panel_grey"))
        # transmission towers + conductors (1.5x diameter so they read at 1080 px)
        towers = []
        xs = [500.0, 750.0, 1000.0, 1250.0]
        for x in xs:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    towers.append(("cyl", (x + sx * 3.5, cy + sy * 3.5, 0.0), (x + sx * 0.8, cy + sy * 0.8, 33.0), 0.18,
                                   0.12, 4, 0))
            for z, wdt in ((24.0, 16.0), (29.0, 12.0), (34.0, 3.0)):
                towers.append(("box", (x, cy, z), (0.5, wdt, 0.5), 0))
            for k in range(6):
                z = 3.0 + 4.5 * k
                towers.append(("box", (x, cy, z), (0.12, 7.0 - 0.8 * k, 0.12), 0))
        multi("ed_transmission_towers", towers, [M("galv")])
        wire = S.pbr("ed_wire", hexc("202224"), 0.5)
        ends = [cx + 35.0] + xs
        for a, b in zip(ends, ends[1:]):
            for k, (yy, zz) in enumerate(((-6.5, 23.4), (0.0, 23.4), (6.5, 23.4))):
                za = 12.6 if a == ends[0] else zz
                B.curve_line("ed_conductor_%d_%d" % (int(a), k), B.catenary((a, cy + yy, za), (b, cy + yy, zz),
                                                                            6.0 if a != ends[0] else 2.0), 0.03 * 1.5,
                             wire)

    # ------------------------------------------------------------ Z_WATER (tower on the hill + treatment plant)
    def build_water(self):
        self.zone("Z_WATER")
        M = self.M.m
        tx, ty = -260.0, 430.0
        bm = bmesh.new()                                         # the hill (z = 8 at the tower)
        res = bmesh.ops.create_grid(bm, x_segments=24, y_segments=24, size=130.0)
        for v in res["verts"]:
            r = math.hypot(v.co.x, v.co.y)
            v.co.z = 8.0 * smooth(1.0 - r / 130.0) - 0.05
        B.mesh_obj("ed_hill", bm, [M("lawn")], smooth=True, loc=(tx, ty, 0.0))
        cyl("ed_tower_pedestal_back", (tx, ty, 8.0), (tx, ty, 40.0), 2.0, 2.0, M("tank_paint"), seg=24)
        cyl("ed_tower_cone", (tx, ty, 38.0), (tx, ty, 42.0), 2.0, 6.0, M("tank_paint"), seg=24)
        cyl("ed_tower_riser", (tx, ty, 8.0), (tx, ty, 44.0), 0.6, 0.6, M("iron_main"), seg=12)
        # tank: back half fixed, camera-side half (towards CAM_water_tower, south-east) peels away
        cam = P.STOPS["water_tower"]["cam"]
        nx, ny = cam[0] - tx, cam[1] - ty
        nl = math.hypot(nx, ny)
        nx, ny = nx / nl, ny / nl
        for half, clear_outer in (("back", True), ("front", False)):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=9.0)
            for v in bm.verts:
                v.co.z *= 0.8
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=(0.0, 0.0, 0.0), plane_no=(nx, ny, 0.0),
                                   clear_outer=clear_outer, clear_inner=not clear_outer)
            o = B.mesh_obj("ed_tank_" + half, bm, [M("tank_paint")], smooth=True, loc=(tx, ty, 48.0))
            if half == "front":
                self.peel("tank_slice", o, (nx * 16.0, ny * 16.0, 4.0))
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=8.7)
        for v in bm.verts:
            v.co.z = min(v.co.z * 0.8, 2.5)
        B.mesh_obj("ed_tank_water", bm, [M("water_vol")], smooth=True, loc=(tx, ty, 48.0))
        curve("ed_tank_rail", ring_pts((tx, ty, 44.2), 9.4), 0.05, M("galv"))
        box("ed_tower_ladder", (tx + 2.05, ty, 24.0), (0.1, 0.5, 32.0), M("galv"))
        for k in range(3):                                       # gravity: ice arrows down the riser (graphic)
            z = 36.0 - 9.0 * k
            cyl("ed_gravity_arrow_%d" % k, (tx, ty, z), (tx, ty, z - 2.5), 0.9, 0.05, M("ice_alpha"), seg=12)
        self.fence("ed_wt_fence", tx - 12, tx + 12, ty - 12, ty + 12, h=2.2, gap=(tx, ty - 12))
        # treatment plant by the river
        px, py = -640.0, -200.0
        quads("ed_plant_pad", [(px - 80, px + 80, py - 55, py + 55)], 0.03, M("concrete"))
        for i, (cx, cy) in enumerate(((-655.0, -190.0), (-655.0, -225.0))):
            cyl("ed_clarifier_%d" % i, (cx, cy, 0.0), (cx, cy, 4.0), 12.5, 12.5, M("concrete"), seg=40)
            cyl("ed_clarifier_water_%d" % i, (cx, cy, 3.6), (cx, cy, 3.62), 12.2, 12.2, M("water"), seg=40)
            box("ed_clarifier_bridge_%d" % i, (cx, cy, 4.4), (25.5, 1.2, 0.5), M("galv"))
        box("ed_filter_building", (-605.0, -180.0, 4.0), (30.0, 20.0, 8.0), M("panel_grey"))
        wall = box("ed_filter_wall", (-620.2, -180.0, 4.0), (0.3, 19.6, 7.8), M("panel_grey"))
        self.peel("filter_bed", wall, (0.0, 0.0, -8.5))
        multi("ed_filter_layers", [("box", (-612.0, -180.0, 0.6), (14.0, 18.0, 1.2), 0),
                                   ("box", (-612.0, -180.0, 1.6), (14.0, 18.0, 0.8), 1),
                                   ("box", (-612.0, -180.0, 2.4), (14.0, 18.0, 0.8), 2)],
              [S.pbr("ed_gravel_coarse", hexc("8a8478"), 0.95, bump=0.4), M("gravel"),
               S.pbr("ed_sand", hexc("d8c49a"), 0.95, var=0.1, var_scale=20.0)])
        cyl("ed_clearwell", (-590.0, -225.0, 0.0), (-590.0, -225.0, 6.0), 10.0, 10.0, M("white_metal"), seg=32)
        box("ed_pump_house", (-700.0, -190.0, 2.5), (8.0, 10.0, 5.0), M("brick"))
        for (a, b) in (((-696.0, -190.0, 1.0), (-667.5, -190.0, 1.0)), ((-642.5, -190.0, 1.0), (-620.0, -185.0, 1.0)),
                       ((-597.0, -195.0, 1.0), (-590.0, -215.0, 1.0))):
            cyl("ed_plant_pipe_%d" % int(a[0]), a, b, 0.5, 0.5, M("blue_duct"), seg=12)
        self.scatter_trees("ed_trees_river", [(-770.0 + self.rng.uniform(-8, 0), -500.0 + 40 * i) for i in range(30)] +
                           [(-690.0 + self.rng.uniform(0, 6), -600.0 + 50 * i) for i in range(8)])

    # ------------------------------------------------------------ Z_SKY (cloud deck + satellites)
    def build_sky(self):
        self.zone("Z_SKY")
        M = self.M.m
        quads("ed_cloud_deck", [(-900.0, 1100.0, -700.0, 1300.0)], 950.0, M("cloud"))
        rng = random.Random(17)
        bm = bmesh.new()
        for i in range(20):                                     # billboard clouds = the cloud portal on the crane path
            x, y, z = rng.uniform(60, 240), rng.uniform(150, 300), rng.uniform(900, 1250)
            B.bm_sphere(bm, (x, y, z), (rng.uniform(25, 60), rng.uniform(25, 60), rng.uniform(10, 22)), 2, 0,
                        jitter=0.2, seed=i)
        B.mesh_obj("ed_clouds", bm, [M("cloud")], smooth=True)
        bm = bmesh.new()
        box_bm(bm, (0, 0, 0), (5.0, 5.0, 6.0), 0)
        box_bm(bm, (0, -9.0, 0), (12.0, 0.2, 3.5), 1)
        box_bm(bm, (0, 9.0, 0), (12.0, 0.2, 3.5), 1)
        box_bm(bm, (0, -4.0, 0), (0.6, 3.0, 0.6), 2)
        box_bm(bm, (0, 4.0, 0), (0.6, 3.0, 0.6), 2)
        box_bm(bm, (0, 0, -3.3), (3.5, 3.5, 0.6), 3)
        sat = S.mesh_from_bm("ed_satellite", bm, [M("gold"), S.pbr("ed_solar", hexc("1d2f57"), 0.2, metal=0.4),
                                                  M("galv"), M("white_metal")])
        anc = P.STOPS["sky_satellites"]["anc"]
        cones = bmesh.new()
        for i, off in enumerate(((0, 0, 0), (-80, 120, 30), (100, 80, -40), (40, 220, 120))):
            p = (anc[0] + off[0], anc[1] + off[1], anc[2] + off[2])
            S.obj("ed_satellite_%d" % i, sat, p, (math.radians(10), 0.0, math.radians(30 * i)))
            B.bm_cyl(cones, (p[0], p[1], p[2] - 4.0), (p[0] + 0.1 * (100 - p[0]), p[1] + 0.1 * (300 - p[1]), 960.0),
                     2.0, 60.0, 16, 0, False)
        B.mesh_obj("ed_signal_cones", cones, [alpha_mat("ed_cone_alpha", TEAL, 0.15, emit=1.0)])

    # ------------------------------------------------------------ build order
    def parts(self):
        Z = self.zones
        order = [("ground", None, self.build_ground), ("far", "Z_FAR_LOD", self.build_far),
                 ("downtown", "Z_DOWNTOWN", self.build_downtown),
                 ("stripmall_int", "Z_STRIPMALL_INT", self.build_mall_interior),
                 ("macro_card", "Z_MACRO_CARD", self.build_macro_card),
                 ("macro_terminal", "Z_MACRO_TERMINAL", self.build_macro_terminal),
                 ("macro_scanner", "Z_MACRO_SCANNER", self.build_macro_scanner),
                 ("suburb", "Z_SUBURB", self.build_suburb),
                 ("macro_phone", "Z_MACRO_PHONE", self.build_macro_phone),
                 ("house_int", "Z_HOUSE_INT", self.build_house_interior),
                 ("macro_mw", "Z_MACRO_MW", self.build_macro_microwave),
                 ("mw_inside", "Z_MW_INSIDE", self.build_mw_inside),
                 ("house_basement", "Z_HOUSE_BASEMENT", self.build_basement),
                 ("street_slice", "Z_STREET_SLICE", self.build_street_slice),
                 ("tower", "Z_TOWER", self.build_tower),
                 ("industrial_dc", "Z_INDUSTRIAL_DC", self.build_data_center),
                 ("dc_int", "Z_DC_INT", self.build_dc_interior),
                 ("power", "Z_POWER", self.build_power),
                 ("water", "Z_WATER", self.build_water),
                 ("sky", "Z_SKY", self.build_sky)]
        return [(n, z, fn) for n, z, fn in order if (z is None and self.wants(n)) or z in Z]

    # ------------------------------------------------------------ plan events -> keys (apply_events)
    def key_events(self, plan, lo, hi):
        fr = list(range(max(1, lo), min(plan["frames"], hi) + 1))
        if not fr:
            return
        n_keyed = 0
        for table, amounts in ((self.peels, P.peel_amounts(plan, self.stop0)),
                               (self.lids, P.lid_amounts(plan, self.stop0))):
            for grp, items in table.items():
                a = amounts.get(grp)
                if a is None:
                    continue
                vals = [smooth(a[f]) for f in fr]
                for obj, base, off in items:
                    if max(vals) <= 0.0:
                        continue
                    B.set_keys(obj, "location", fr, [(base[0] + off[0] * v, base[1] + off[1] * v, base[2] + off[2] * v)
                                                     for v in vals])
                    n_keyed += 1
        self.stats["keyed_peels_lids"] = n_keyed
        # per-frame visibility of the small zones (interiors, macro sets, sky)
        for zn in ("Z_MW_INSIDE", "Z_STRIPMALL_INT", "Z_HOUSE_INT", "Z_HOUSE_BASEMENT", "Z_DC_INT", "Z_SKY", "Z_MACRO_PHONE",
                   "Z_MACRO_CARD", "Z_MACRO_TERMINAL", "Z_MACRO_SCANNER", "Z_MACRO_MW"):
            c = bpy.data.collections.get("MH_" + zn)
            if c is None:
                continue
            keys = P.zone_vis_keys(plan, self.stop0, zn, fr[0], fr[-1])
            if all(v for _f, v in keys):
                continue
            for o in c.all_objects:
                if o.type in ("MESH", "CURVE", "LIGHT"):
                    B.vis_keys(o, keys)
        # clip planes from the subject distance (macro needs 0.2 mm near clip; render_oneshot sets 0.1 / 20000)
        cam = bpy.context.scene.camera
        if cam is not None:
            cp = [P.clip_planes(plan, f) for f in fr]
            B.set_keys(cam.data, "clip_start", fr, [c[0] for c in cp])
            B.set_keys(cam.data, "clip_end", fr, [c[1] for c in cp])
        if os.environ.get("ED_REBASE") == "1":
            self.key_rebase(plan, fr)

    def key_rebase(self, plan, fr):
        """Floating-origin rebase (WORLDS-SPEC 1.1 R). OFF unless ED_REBASE=1: render_oneshot creates the Spark AFTER
        apply_events and does not parent it, so the orb would be offset by the rebase. Needs page2 (BUILD-LOG)."""
        root = bpy.data.objects.get("WORLD_ROOT") or L.link(bpy.data.objects.new("WORLD_ROOT", None))
        for o in list(bpy.data.objects):
            if o is not root and o.parent is None:
                o.parent = root
        keys = []
        for f, stop in P.rebase_keys(plan, self.stop0):
            if f > fr[-1]:
                break
            a = P.VIEWS[stop]["anc"] if stop else (0.0, 0.0, 0.0)
            keys.append((max(f, 1), (-a[0], -a[1], -a[2])))
        B.key_const(root, "location", keys)
        self.stats["rebase_keys"] = len(keys)


# ================================================================ registry entry points
def build(ctx, state):
    """worlds.py contract: build the zones this job needs, put ANC_/CAM_ empties at the plan positions, return
    {stop: ANC_<stop>}. The Hometown handle goes to state["world"] (apply_events uses it)."""
    import time
    w = Hometown(ctx, state)
    state["world"] = w
    w.build_anchors()
    w.build_lighting()
    t_all = time.time()
    for name, zone, fn in w.parts():
        t0 = time.time()
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            print("[ed] PART %s FAILED (continuing)" % name)
        w.stats["t_" + name] = round(time.time() - t0, 2)
        w.stats["tris_" + name] = B.count_tris(zone or name)
    w.stats["zones"] = sorted(w.zones)
    w.stats["t_world"] = round(time.time() - t_all, 2)
    print("[ed] hometown_usa built: %s" % w.stats)
    return B.normalize_anchors(ctx)


def apply_events(state, plan, lo, hi):
    w = state.get("world")
    if w is None:
        print("[ed] apply_events: no world handle (build failed?)")
        return
    w.key_events(plan, lo, hi)

"""v2 winter-airfield builders ("Russian plane crash" / why Soviet-era planes still fly, 25 Nov 2026).
Registers into scene_lib_v2.V2_BUILDERS.

World: a snowy Siberian-style airfield in bright winter daylight (HDRI sky), concrete runway with snow banks,
hangars and a small tower, a village and endless snowy conifer / birch forest. Every beat builds the same world.
Aircraft: an ORIGINAL generic high-wing four-turboprop cargo plane (no insignia, flags, markings or gun turret).
Non-graphic: it only flies, taxis, sits parked or is inspected in a hangar. No wreckage, smoke or fire.
No 3D text: every label / card / timeline is a 2D overlay (overlay_v2.py).
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

SNOW_HAZE = hexc("cfdbe8")
RWY_W, RWY_LEN = 50.0, 2400.0         # runway along +Y, x = 0, y 0..2400
APRON = (90.0, 300.0, 700.0, 1100.0)  # x0, x1, y0, y1
HANGAR_X = 340.0
PZ = 2.62                              # cargo plane root height with gear on the concrete (z 0.25)
_MW = {}


# ================================================================ helpers
def _fcurves(o, path):
    ad = o.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        curves = list(act.fcurves)
    except Exception:
        curves = []
    if not curves:
        try:
            for layer in act.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        curves += list(cb.fcurves)
        except Exception:
            pass
    return [fc for fc in curves if fc.data_path == path]


def set_keys(o, path, frames, values, interp="LINEAR"):
    if not _fcurves(o, path):
        o.keyframe_insert(path, frame=frames[0])
    fcs = {fc.array_index: fc for fc in _fcurves(o, path)}
    n = len(frames)
    for i, fc in fcs.items():
        kp = fc.keyframe_points
        try:
            kp.clear()
        except Exception:
            while len(kp):
                kp.remove(kp[0], fast=True)
        kp.add(n)
        co = [0.0] * (2 * n)
        co[0::2] = [float(f) for f in frames]
        co[1::2] = [float(v[i]) for v in values]
        kp.foreach_set("co", co)
        for k in kp:
            k.interpolation = interp
            k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"
        fc.update()


def _m(name, fn):
    if name not in _MW:
        _MW[name] = fn()
    return _MW[name]


def snow_mat(name="snow_w", color=hexc("eef3f8"), rough=0.62):
    """Snow: near-white with soft drifts (large noise) and fine grain bump."""
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    fac, _ = S._noise_var(N, Lk, obj, 0.012, 0.07, 4.0)
    col = S._mul_col(N, Lk, tuple(color), fac)
    fac2, _ = S._noise_var(N, Lk, obj, 0.25, 0.03, 6.0)
    col = S._mul_col(N, Lk, col, fac2)
    Lk.new(col, p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    try:
        p.inputs["Subsurface Weight"].default_value = 0.05
    except Exception:
        pass
    nzf = N.new("ShaderNodeTexNoise")
    nzf.inputs["Scale"].default_value = 0.6
    nzf.inputs["Detail"].default_value = 6.0
    Lk.new(obj, nzf.inputs["Vector"])
    S._bump(N, Lk, nzf.outputs["Fac"], p, 0.2, 0.15)
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def concrete_w():
    return _m("w_concrete", lambda: S.pbr("w_concrete", hexc("a9aaa8"), 0.85, var=0.1, var_scale=0.05, bump=0.05))


def _box(bm, c, s, mi=0):
    S.bm_box(bm, c, s, mi)


# ================================================================ the cargo plane
CARGO_FUSE = [  # y, half-width, z_top, z_bottom (nose +Y, ~33 m long, upswept tail with rear ramp)
    (16.6, 0.12, 0.10, -0.55), (16.1, 0.95, 0.95, -1.25), (15.0, 1.55, 1.55, -1.70), (13.4, 1.86, 1.92, -1.92),
    (11.0, 1.96, 2.02, -2.00), (-5.5, 1.96, 2.02, -2.00), (-8.5, 1.84, 2.02, -1.45), (-11.5, 1.42, 2.02, -0.35),
    (-14.0, 0.95, 1.98, 0.65), (-16.2, 0.42, 1.90, 1.30), (-16.9, 0.12, 1.86, 1.62)]
C_BODY = hexc("cfd3d8")
C_DARK = hexc("4b5563")


def cargo_paint(root):
    """Light grey paint, darker belly and a dark-grey anti-glare panel ahead of the windscreen (object space)."""
    m, nt, N, Lk, p = S._new_mat("cg_paint_" + root.name)
    tc = N.new("ShaderNodeTexCoord")
    tc.object = root
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    belly = N.new("ShaderNodeMapRange")
    belly.inputs["From Min"].default_value = -1.15
    belly.inputs["From Max"].default_value = -1.05
    belly.inputs["To Min"].default_value = 1.0
    belly.inputs["To Max"].default_value = 0.0
    Lk.new(sep.outputs["Z"], belly.inputs["Value"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    Lk.new(belly.outputs["Result"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = C_BODY
    mix.inputs["B"].default_value = hexc("9aa1aa")
    Lk.new(mix.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.42
    p.inputs["Metallic"].default_value = 0.25
    return S._finish(m, p.outputs[0])


def _prop(name, parent, loc, spin, frames, blades=4):
    """Propeller: spinner + blades. spin=True: blades rotate (slow, readable) + a faint blur disc."""
    hub = L.link(bpy.data.objects.new(name, None))
    hub.parent = parent
    hub.location = loc
    dark = _m("cg_prop", lambda: S.pbr("cg_prop", hexc("2a2d31"), 0.5, var=0))
    spin_m = _m("cg_spinner", lambda: S.pbr("cg_spinner", hexc("dfe2e6"), 0.3, 0.4, var=0))
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.42, radius2=0.02, depth=1.1)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=(0, 0.55, 0), verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 1
    for k in range(blades):
        a = 2 * math.pi * k / blades
        vs = S.bm_box(bm, (0, 0.05, 1.05), (0.34, 0.08, 1.9), 0)
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "Y"))
    o = S.obj(name + "_blades", S.mesh_from_bm(name + "_blades", bm, [dark, spin_m], smooth=False), parent=hub)
    if spin:
        set_keys(o, "rotation_euler", [1, frames + 1], [(0, 0, 0), (0, frames * 0.38, 0)], "LINEAR")
        dm = _m("cg_disc", lambda: A._alpha_emis("cg_disc", hexc("4a4f57"), 0.25, 0.18))
        bm = bmesh.new()
        r = bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=2.0)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        d = S.obj(name + "_disc", S.mesh_from_bm(name + "_disc", bm, [dm]), (0, 0.08, 0), parent=hub)
        d.visible_shadow = False
    return hub


def make_cargo_plane(ctx, name, spin=True, gear=True):
    """Generic Cold-War-style high-wing four-turboprop transport (original low-poly design, no markings).
    Nose +Y, origin on the fuselage axis at the wing. Returns (root, parts) with anchors-friendly empties."""
    T = ctx.frames
    root = L.link(bpy.data.objects.new(name, None))
    paint = cargo_paint(root)
    wing_m = _m("cg_wing", lambda: S.pbr("cg_wing", hexc("c3c8ce"), 0.4, 0.3, var=0.03))
    dark = _m("cg_dark", lambda: S.pbr("cg_darkp", C_DARK, 0.5, var=0))
    glass = _m("cg_glass", lambda: S.glass_mat("cg_glass", hexc("1e2f3f")))
    tyre = _m("cg_tyre", lambda: S.pbr("cg_tyre", hexc("1b1c1f"), 0.85, var=0))
    metal = _m("cg_metal", lambda: S.pbr("cg_metal", hexc("aab0b6"), 0.3, 0.8, var=0))
    bm = bmesh.new()
    A._loft(bm, CARGO_FUSE, n=28, step=0.4, mat_index=0)
    S._wing(bm, 1.8, 9.2, 6.8, 2.8, -10.4, 4.6, 0.0, 0.0, 0.12, 0.09, vertical=True, mat_index=0, n_span=4)  # fin
    for side in (-1, 1):   # stabilisers on the upswept tail
        S._wing(bm, 0.3, 6.6, 3.8, 1.6, -12.6, 2.2, 1.95, 4.0, 0.11, 0.09, side, mat_index=0, n_span=4)
    body = S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [paint], smooth=True), parent=root)
    body.modifiers.new("sub", "SUBSURF").levels = 1
    # high wing on top of the fuselage, slight anhedral outboard
    bm = bmesh.new()
    for side in (-1, 1):
        S._wing(bm, 1.0, 19.2, 5.0, 1.8, 2.9, 1.3, 2.25, -1.5, 0.15, 0.11, side, mat_index=0, n_span=6)
    S.obj(name + "_wing", S.mesh_from_bm(name + "_wing", bm, [wing_m], smooth=True), parent=root)
    # wing-root fairing on top
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0.4, 2.05), (1.6, 3.4, 0.55), 0, 20, 10)
    S.obj(name + "_fair", S.mesh_from_bm(name + "_fair", bm, [paint], smooth=True), parent=root)
    # glazed nose + cockpit windows
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 15.55, -0.55), (1.0, 1.15, 0.85), 0, 18, 10)
    for sx in (-1, 1):
        for k in range(3):
            _box(bm, (sx * 1.25, 13.9 - k * 0.75, 1.25), (0.5, 0.55, 0.45), 0)
    _box(bm, (0, 14.45, 1.55), (1.5, 0.45, 0.42), 0)
    S.obj(name + "_glass", S.mesh_from_bm(name + "_glass", bm, [glass], smooth=True), parent=root)
    # four turboprop nacelles under the wing + propellers
    props, nac = [], []
    for k, x in enumerate((-11.0, -5.5, 5.5, 11.0)):
        bm = bmesh.new()
        tab = [(3.2, 0.35, 0.35, -0.35), (2.7, 0.72, 0.72, -0.8), (1.0, 0.8, 0.8, -0.95), (-2.6, 0.7, 0.5, -0.9),
               (-4.6, 0.25, 0.2, -0.4)]
        A._loft(bm, tab, n=20, step=0.35, mat_index=0)
        zc = 2.0 - (abs(x) - 1.0) * math.tan(math.radians(1.5)) - 0.25
        o = S.obj(name + "_nac%d" % k, S.mesh_from_bm(name + "_nac", bm, [paint], smooth=True), (x, 2.6, zc),
                  parent=root)
        nac.append(o)
        props.append(_prop(name + "_prop%d" % k, root, (x, 2.6 + 3.25, zc), spin, T))
    # main gear sponsons on the lower fuselage + wheels, nose gear
    bm = bmesh.new()
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 1.95, -1.6, -1.35), (0.75, 4.2, 0.85), 0, 16, 8)
    S.obj(name + "_sponson", S.mesh_from_bm(name + "_sponson", bm, [paint], smooth=True), parent=root)
    g = L.link(bpy.data.objects.new(name + "_gear", None))
    g.parent = root
    bm = bmesh.new()
    for sx in (-1, 1):
        for y in (-0.4, -2.8):
            for dx in (-0.35, 0.35):
                r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.6, radius2=0.6, depth=0.36)
                bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
                bmesh.ops.translate(bm, vec=(sx * 2.0 + dx, y, -2.0), verts=r["verts"])
    for dx in (-0.25, 0.25):
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.42, radius2=0.42, depth=0.25)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, vec=(dx, 12.6, -2.2), verts=r["verts"])
    S.obj(name + "_wheels", S.mesh_from_bm(name + "_wheels", bm, [tyre], smooth=True), parent=g)
    bm = bmesh.new()
    _box(bm, (0, 12.6, -1.9), (0.18, 0.18, 0.9), 0)
    S.obj(name + "_ngleg", S.mesh_from_bm(name + "_ngleg", bm, [metal]), parent=g)
    g.scale = (1, 1, 1.0 if gear else 0.0)
    # nav lights + red beacon
    for sx, col in ((-1, hexc("ff2a2a")), (1, hexc("2aff6a"))):
        bm = bmesh.new()
        S._ellipsoid(bm, (sx * 19.25, 1.6, 2.25 - math.tan(math.radians(1.5)) * 18.2), (0.12, 0.18, 0.1), 0, 8, 6)
        S.obj(name + "_nav%d" % sx, S.mesh_from_bm(name + "_nav", bm, [S.emis("cg_nav_%d" % sx, col, 8.0)]),
              parent=root)
    root_parts = {"props": props, "gear": g, "nac": nac}
    return root, root_parts


# ================================================================ world
def conifer_templates(rng):
    trunk = S.pbr("w_trunk", hexc("4a3a2c"), 0.9, var=0.1)
    green = S.pbr("w_fir", hexc("2f4a35"), 0.85, var=0.12, bump=0.1)
    snow = snow_mat("w_treesnow", hexc("f3f6fa"), 0.7)
    out = []
    for i in range(4):
        h = 1.0 + 0.18 * i

        def build(bm, h=h, i=i):
            _box(bm, (0, 0, 1.0), (0.4, 0.4, 2.0), 0)
            for k, (r, zc, dz) in enumerate(((2.9, 4.2, 4.6), (2.2, 6.9, 4.0), (1.5, 9.2, 3.2), (0.8, 11.0, 2.2))):
                res = bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r, radius2=0.0, depth=dz)
                bmesh.ops.scale(bm, vec=(1, 1, h), verts=res["verts"])
                bmesh.ops.translate(bm, vec=(0, 0, zc * h), verts=res["verts"])
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 1
                # snow cap: a flatter white cone sitting on each tier
                res = bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r * 0.82, radius2=0.0, depth=dz * 0.55)
                bmesh.ops.scale(bm, vec=(1, 1, h), verts=res["verts"])
                bmesh.ops.translate(bm, vec=(0, 0, (zc + dz * 0.25) * h), verts=res["verts"])
                bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(0.35, 3, "Z"))
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 2
        out.append(S._template("w_fir_t%d" % i, build, [trunk, green, snow]))
    birch = S.pbr("w_birch", hexc("e9e6df"), 0.7, var=0.15, var_scale=3.0)
    twig = S.pbr("w_twig", hexc("6b5a4a"), 0.9, var=0.1)
    for i in range(2):
        def build_b(bm, i=i):
            _box(bm, (0, 0, 4.5), (0.35, 0.35, 9.0), 0)
            r2 = random.Random(40 + i)
            for k in range(7):
                z = 4.0 + k * 0.8
                a = r2.uniform(0, 6.28)
                vs = S.bm_box(bm, (0, 0, 1.4), (0.12, 0.12, 2.8), 1)
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(0.75, 3, "X"))
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "Z"))
                bmesh.ops.translate(bm, vec=(0, 0, z), verts=vs)
        out.append(S._template("w_birch_t%d" % i, build_b, [birch, twig]))
    return out


def village(rng, cx, cy, n=40):
    """Wooden houses with snow-covered gable roofs (dark brown / green / blue walls)."""
    walls = [S.pbr("w_house%d" % i, c, 0.85, var=0.08) for i, c in
             enumerate((hexc("6b4a32"), hexc("4f6b4a"), hexc("51657e"), hexc("7a5a3c"), hexc("8a6e4e")))]
    roof = snow_mat("w_roofsnow", hexc("f4f7fb"), 0.7)
    win = S.pbr("w_win", hexc("2a3644"), 0.2, var=0)
    tpl = []
    for i in range(5):
        w, d, h = rng.uniform(7, 10), rng.uniform(6, 8), rng.uniform(3.0, 3.6)

        def build(bm, w=w, d=d, h=h):
            _box(bm, (0, 0, h / 2), (w, d, h), 0)
            S.bm_prism_x(bm, -w / 2 - 0.5, w / 2 + 0.5, [(-d / 2 - 0.6, h - 0.1), (d / 2 + 0.6, h - 0.1), (0, h + d * 0.42)], 1)
            for k in (-1, 1):
                _box(bm, (k * w / 4, -d / 2 - 0.03, h * 0.55), (1.1, 0.06, 1.0), 2)
        tpl.append(S._template("w_house_t%d" % i, build, [walls[i], roof, win]))
    for k in range(n):
        x, y = cx + (k % 8) * 26 + rng.uniform(-5, 5), cy + (k // 8) * 30 + rng.uniform(-5, 5)
        S.obj("w_house%d" % k, tpl[rng.randrange(5)], (x, y, 0.0), (0, 0, rng.choice((0.0, math.pi / 2)) + rng.uniform(-0.1, 0.1)))


def hangar(name, loc, w=60.0, d=50.0, h=16.0, open_door=False):
    wall = S.corrugated_mat("w_hwall", hexc("b9c0c7"))
    roof = snow_mat("w_hroof", hexc("f2f5f9"), 0.7)
    door = S.corrugated_mat("w_hdoor", hexc("8b949e"), 0.5, 0.5, 0.6)
    bm = bmesh.new()
    t = 0.6
    _box(bm, (0, d / 2 - t / 2, h / 2), (w, t, h), 0)            # back wall (+y)
    for sx in (-1, 1):
        _box(bm, (sx * (w / 2 - t / 2), 0, h / 2), (t, d, h), 0)
    # arched-ish roof: two slopes
    a = [bm.verts.new((-w / 2 - 0.5, yy, zz)) for yy, zz in ((-d / 2 - 0.5, h), (d / 2 + 0.5, h))]
    b = [bm.verts.new((0, yy, h + w * 0.14)) for yy in (-d / 2 - 0.5, d / 2 + 0.5)]
    c = [bm.verts.new((w / 2 + 0.5, yy, zz)) for yy, zz in ((-d / 2 - 0.5, h), (d / 2 + 0.5, h))]
    for f in (bm.faces.new((a[0], a[1], b[1], b[0])), bm.faces.new((b[0], b[1], c[1], c[0]))):
        f.material_index = 1
    bm.faces.new((a[0], b[0], c[0])).material_index = 0
    bm.faces.new((c[1], b[1], a[1])).material_index = 0
    if not open_door:
        _box(bm, (0, -d / 2 + t / 2, h / 2), (w - 2 * t, t, h), 2)
    else:
        _box(bm, (0, -d / 2 + t / 2, h - 1.5), (w - 2 * t, t, 3.0), 0)   # header above the open door
    o = S.obj(name, S.mesh_from_bm(name, bm, [wall, roof, door]), loc)
    return o


def build_winter_world(ctx, p, sun_az=-35.0, seed=57):
    rng = random.Random(seed)
    S.HAZE = SNOW_HAZE
    L.fog(p.get("fog", 0.00018), SNOW_HAZE, start=300.0)
    S.daylight(ctx, p.get("sun_az", sun_az), p.get("sun_elev", 30.0), hdri=p.get("hdri", True),
               exposure=p.get("exposure", -0.85))
    import scene_lib_v2_city as C
    C.horizon_haze(ctx.scene)
    S.plane_obj("w_ground", 40000, 40000, (0, 0, 0), snow_mat())
    # runway: concrete with the airport's marking textures, snow banks along the edges, cleared shoulders
    end_m = S.image_mat("rwy_end_v2", "runway_end.png")
    mid_m = S.image_mat("rwy_mid_v2", "runway_mid.png", (1.0, 1.0))
    endb_m = S.image_mat("rwy_endb_v2", "runway_end_b.png")
    zr = 0.25
    S.plane_obj("w_rwy_a", 45.0, 400, (0, 200, zr), end_m)
    n_mid = 26
    tl = (RWY_LEN - 800) / n_mid
    for k in range(n_mid):
        S.plane_obj("w_rwy_m%d" % k, 45.0, tl, (0, 400 + tl / 2 + tl * k, zr), mid_m)
    S.plane_obj("w_rwy_b", 45.0, 400, (0, RWY_LEN - 200, zr), endb_m, rot_z=math.pi)
    S.plane_obj("w_shoulder", 70.0, RWY_LEN + 120, (0, RWY_LEN / 2, zr - 0.04), concrete_w())
    bank = snow_mat("w_bank", hexc("f6f8fb"), 0.75)
    bm = bmesh.new()
    for sx in (-1, 1):
        for y0 in range(-60, int(RWY_LEN) + 60, 40):
            _box(bm, (sx * (36.0 + rng.uniform(-0.6, 0.6)), y0 + 20, 0.35), (rng.uniform(3.5, 5.0), 40.5, 0.7 + rng.uniform(0, 0.5)), 0)
    S.obj("w_banks", S.mesh_from_bm("w_banks", bm, [bank], smooth=False))
    # taxiway + apron (concrete), link
    S.plane_obj("w_twy", 22, 1400, (70.0, 900.0, zr - 0.01), concrete_w())
    ax0, ax1, ay0, ay1 = APRON
    S.plane_obj("w_apron", ax1 - ax0, ay1 - ay0, ((ax0 + ax1) / 2, (ay0 + ay1) / 2, zr - 0.005), concrete_w())
    for y in (300.0, 900.0, 1500.0):
        S.plane_obj("w_link%d" % int(y), 50.0, 20.0, (40.0, y, zr - 0.02), concrete_w())
    # edge lights (posts)
    bm = bmesh.new()
    for y in range(0, int(RWY_LEN) + 1, 60):
        for sx in (-1, 1):
            _box(bm, (sx * 26.5, y, 0.6), (0.3, 0.3, 0.7), 0)
    S.obj("w_rwy_lights", S.mesh_from_bm("w_rwy_lights", bm, [S.pbr("w_fix", hexc("f0f0ea"), 0.4, var=0)]))
    # hangars, tower, sheds along the apron's east side
    for k, y in enumerate((760.0, 840.0, 920.0)):
        hangar("w_hangar%d" % k, (HANGAR_X, y, 0.0), 62.0, 56.0, 16.0)
    tower_m = S.pbr("w_tower", hexc("e6e2d8"), 0.6, var=0.04)
    bm = bmesh.new()
    _box(bm, (330.0, 1040.0, 9.0), (7.0, 7.0, 18.0), 0)
    _box(bm, (330.0, 1040.0, 20.0), (10.0, 10.0, 4.0), 1)
    _box(bm, (330.0, 1040.0, 22.3), (11.0, 11.0, 0.6), 2)
    S.obj("w_tower", S.mesh_from_bm("w_tower", bm, [tower_m, S.glass_mat("w_tglass", hexc("2a4a5e")), snow_mat("w_roofsnow2", hexc("f4f7fb"))]))
    village(rng, 620.0, 1300.0, 48)
    village(rng, -900.0, 500.0, 32)
    # forest: dense taiga = instanced forest patches (50 m cells) in a band around the field, mottled
    # "forest" ground beyond it, detailed single trees on the field margins
    build_forest(rng)
    # low snowy hills far away
    hm = snow_mat("w_hill", hexc("e8eef5"), 0.8)
    for i in range(14):
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(6500, 9000)
        bm = bmesh.new()
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        S.obj("w_hill%d" % i, S.mesh_from_bm("w_hill%d" % i, bm, [hm], smooth=True),
              (math.cos(ang) * dist, math.sin(ang) * dist + 1200, -80),
              scale=(rng.uniform(900, 1600), rng.uniform(700, 1100), rng.uniform(120, 260)))
    print("[v2 winter] world built")


CLEAR = [(-330.0, 470.0, -360.0, RWY_LEN + 360.0),     # airfield (+ the packed-snow strip at x -260)
         (560.0, 860.0, 1240.0, 1560.0), (-960.0, -680.0, 440.0, 680.0),   # villages
         (600.0, 800.0, -700.0, -500.0)]                     # maintenance-hangar set
FIELD = CLEAR[0]


def _clear(x, y, pad=0.0):
    return any(x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad for x0, x1, y0, y1 in CLEAR)


def forest_ground_mat():
    """Far taiga seen from the air: snow with dense dark crowns (Voronoi dots), hazed by distance."""
    name = "w_forestfloor"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj = S._coord(N, Lk, "Object")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 0.11
    Lk.new(obj, vor.inputs["Vector"])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.004
    Lk.new(obj, nz.inputs["Vector"])
    add = N.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    Lk.new(nz.outputs["Fac"], add.inputs[0])
    add.inputs[1].default_value = 0.5
    Lk.new(vor.outputs["Distance"], add.inputs[2])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.42, hexc("223829")
    els[1].position, els[1].color = 0.62, hexc("e9eef4")
    Lk.new(add.outputs[0], ramp.inputs[0])
    Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.85
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def _fir_bm(bm, x, y, s, rot, seg=7):
    for (r, zc, dz) in ((2.6, 3.4, 4.6), (1.9, 6.2, 3.8), (1.1, 8.6, 3.0)):
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r * s, radius2=0.0, depth=dz * s)
        bmesh.ops.translate(bm, vec=(x, y, zc * s), verts=res["verts"])
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 0
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r * 0.8 * s, radius2=0.0, depth=dz * 0.5 * s)
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(rot, 3, "Z"))
        bmesh.ops.translate(bm, vec=(x, y, (zc + dz * 0.27) * s), verts=res["verts"])
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 1


def build_forest(rng, cell=50.0, band=950.0, per=16):
    green = S.pbr("w_fir_p", hexc("2c4532"), 0.85, var=0.12, var_scale=0.05)
    snow = snow_mat("w_treesnow", hexc("f3f6fa"), 0.7)
    patches = []
    for k in range(8):
        bm = bmesh.new()
        r2 = random.Random(300 + k)
        for _ in range(per):
            _fir_bm(bm, r2.uniform(-cell / 2, cell / 2), r2.uniform(-cell / 2, cell / 2), r2.uniform(0.75, 1.45),
                    r2.uniform(0, 6.28))
        patches.append(S.mesh_from_bm("w_patch%d" % k, bm, [green, snow]))
    fx0, fx1, fy0, fy1 = FIELD
    n = 0
    x = fx0 - band
    while x < fx1 + band:
        y = fy0 - band
        while y < fy1 + band:
            if not _clear(x, y, cell * 0.6):
                S.obj("w_fp%d" % n, patches[rng.randrange(len(patches))],
                      (x + rng.uniform(-6, 6), y + rng.uniform(-6, 6), 0.0), (0, 0, rng.choice((0, 1.57, 3.14, 4.71))))
                n += 1
            y += cell
        x += cell
    # mottled far forest beyond the band (four big rectangles around it)
    fm = forest_ground_mat()
    X0, X1, Y0, Y1 = fx0 - band, fx1 + band, fy0 - band, fy1 + band
    R = 14000.0
    for nm, (a0, a1, b0, b1) in (("w", (X0 - R, X0, Y0 - R, Y1 + R)), ("e", (X1, X1 + R, Y0 - R, Y1 + R)),
                                 ("s", (X0, X1, Y0 - R, Y0)), ("n", (X0, X1, Y1, Y1 + R))):
        S.plane_obj("w_farforest_" + nm, a1 - a0, b1 - b0, ((a0 + a1) / 2, (b0 + b1) / 2, 0.05), fm)
    # detailed single trees + birches on the field margins (close-up shots)
    tpl = conifer_templates(rng)
    pts = []
    for _ in range(1400):
        xx, yy = rng.uniform(fx0 - 120, fx1 + 120), rng.uniform(fy0 - 120, fy1 + 120)
        if _clear(xx, yy, 4.0):
            # only the outer 0-40 m of the clear field margins
            if not (fx0 + 6 < xx < fx0 + 45 or fx1 - 30 < xx < fx1 - 6):
                continue
            if -300 < xx < -215 or (90 < xx < 470 and 680 < yy < 1120):
                continue
        pts.append((xx, yy))
    S.scatter(tpl, pts, rng, (0.8, 1.4), prefix="w_tree")
    print("[v2 winter] forest: %d patches (%d trees) + %d single trees" % (n, n * per, len(pts)))


def parked_fleet(ctx, spots, spin=False):
    out = []
    for k, (x, y, rz) in enumerate(spots):
        r, parts = make_cargo_plane(ctx, "fleet%d" % k, spin=spin)
        r.location = (x, y, PZ)
        r.rotation_euler = (0, 0, rz)
        out.append(r)
    return out


def _cam(ctx, loc, tgt, lens):
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = 0.5
    cam.data.clip_end = 20000.0
    return cam


def _keys(ctx, keys, interp="BEZIER"):
    for f, c, t in keys:
        kf(ctx.cam, "location", f, Vector(c), interp)
        kf(ctx.cam_target, "location", f, Vector(t), interp)


def _path_keys(ctx, obj, pts, interp="LINEAR"):
    T = ctx.frames
    fr = list(range(1, T + 1, 3)) + ([T] if (T - 1) % 3 else [])
    set_keys(obj, "location", fr, [pts(f) for f in fr], interp)


# ================================================================ BUILDERS
def b_cargo_hook(ctx, p):
    """The cargo plane cruising calmly over the snowy taiga in bright winter light; chase camera from the side/rear,
    slowly drifting forward. Anchor: plane."""
    T = ctx.frames
    build_winter_world(ctx, p)
    root, parts = make_cargo_plane(ctx, "cg", gear=False)
    v = 85.0 / ctx.fps
    y0, z = p.get("y0", -1600.0), p.get("z", 260.0)
    tr = L.link(bpy.data.objects.new("cg_track", None))
    _path_keys(ctx, tr, lambda f: (p.get("x", -600.0), y0 + v * (f - 1), z + 3.0 * math.sin(f / 70.0)))
    root.parent = tr
    root.rotation_euler = (math.radians(1.5), math.radians(-2.0), 0)
    rig = L.link(bpy.data.objects.new("rig", None))
    rig.parent = tr
    cam = _cam(ctx, (0, 0, 0), (0, 0, 0), p.get("lens", 24))
    cam.parent = rig
    ctx.cam_target.parent = rig
    o0, o1 = Vector(p.get("off0", (-72.0, -80.0, 6.0))), Vector(p.get("off1", (-64.0, -62.0, 5.0)))
    set_keys(cam, "location", [1, T], [tuple(o0), tuple(o1)], "BEZIER")
    set_keys(ctx.cam_target, "location", [1, T], [(0, 4.0, -3.0), (0, 4.0, -3.5)], "BEZIER")
    S.anchor(ctx, "plane", root, (0, 2.0, 3.0))


def b_cargo_plate(ctx, p):
    """Plate (half res, blurred by the overlay): the cargo plane parked on the snowy apron, slow push-in."""
    T = ctx.frames
    build_winter_world(ctx, p)
    parked_fleet(ctx, [(200.0, 900.0, math.pi / 2 + 0.5)])
    c0, t0 = (120.0, 830.0, 9.0), (205.0, 905.0, 5.0)
    c1, t1 = (130.0, 840.0, 8.0), (205.0, 905.0, 5.0)
    _cam(ctx, c0, t0, p.get("lens", 28))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_rough_strip_v2(ctx, p):
    """The plane taxis slowly along a snowy, packed-snow strip (props turning), low side camera tracking.
    Anchors: wing (wing top), engine (outboard nacelle), gear (main gear sponson)."""
    T = ctx.frames
    build_winter_world(ctx, p)
    # packed-snow strip west of the runway: slightly darker, rutted snow
    strip = snow_mat("w_strip", hexc("d9dde2"), 0.8)
    S.plane_obj("w_strip", 40.0, 2000.0, (-260.0, 900.0, 0.08), strip)
    for o in list(bpy.data.objects):
        if o.name.startswith("w_tree") and -310 < o.location.x < -205 and -150 < o.location.y < 1950:
            bpy.data.objects.remove(o, do_unlink=True)
    root, parts = make_cargo_plane(ctx, "cg", spin=True)
    v = p.get("speed", 9.0) / ctx.fps
    y0 = p.get("y0", 700.0)
    tr = L.link(bpy.data.objects.new("cg_track", None))
    _path_keys(ctx, tr, lambda f: (-260.0, y0 + v * (f - 1), PZ - 0.17 + 0.04 * math.sin(f / 5.0)))
    root.parent = tr
    root.rotation_euler = (0, 0, 0)
    rig = L.link(bpy.data.objects.new("rig", None))
    _path_keys(ctx, rig, lambda f: (0.0, y0 + v * (f - 1), 0.0))
    cam = _cam(ctx, (0, 0, 0), (0, 0, 0), p.get("lens", 26))
    cam.parent = rig
    ctx.cam_target.parent = rig
    set_keys(cam, "location", [1, T], [(-205.0, 36.0, 4.5), (-208.0, 18.0, 6.0)], "BEZIER")
    set_keys(ctx.cam_target, "location", [1, T], [(-262.0, -2.0, 6.5), (-262.0, -2.0, 6.0)], "BEZIER")
    S.anchor(ctx, "wing", root, (9.0, 1.5, 2.7))
    S.anchor(ctx, "engine", parts["nac"][3], (0, 3.0, 0.2))
    S.anchor(ctx, "gear", root, (1.9, -1.6, -2.3))


def spares_yard(rng, x0, y0):
    """Crates, spare propellers on stands, a spare engine on a cradle, tyre stacks (all with snow on top)."""
    wood = S.pbr("w_crate", hexc("8a6a45"), 0.85, var=0.12)
    green = S.pbr("w_crate2", hexc("55663f"), 0.8, var=0.08)
    snow = snow_mat("w_topsnow", hexc("f5f8fb"), 0.75)
    metal = S.pbr("w_engine", hexc("9aa2aa"), 0.35, 0.8, var=0.04)
    dark = S.pbr("w_stand", hexc("33373c"), 0.6, var=0)
    tyre = S.pbr("w_tyres", hexc("1d1e21"), 0.85, var=0)
    bm = bmesh.new()
    for r_ in range(3):
        for c_ in range(6):
            for lv in range(rng.randint(1, 3)):
                cx, cy = x0 + c_ * 2.6, y0 + r_ * 3.2
                mi = rng.choice((0, 1))
                _box(bm, (cx, cy, 0.6 + lv * 1.25), (2.3, 2.8, 1.2), mi)
            _box(bm, (x0 + c_ * 2.6, y0 + r_ * 3.2, 0.6 + (lv + 1) * 1.25 - 0.55), (2.3, 2.8, 0.12), 2)
    S.obj("w_crates", S.mesh_from_bm("w_crates", bm, [wood, green, snow]))
    # spare propellers (four blades) on stands
    bm = bmesh.new()
    for k in range(3):
        cx, cy = x0 - 4.0 + k * 5.5, y0 + 14.0
        _box(bm, (cx, cy, 1.4), (0.3, 0.3, 2.8), 1)
        for a in range(4):
            vs = S.bm_box(bm, (0, 0, 1.0), (0.32, 0.08, 1.9), 0)
            bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(a * math.pi / 2 + 0.3, 3, "Y"))
            bmesh.ops.translate(bm, vec=(cx, cy - 0.2, 3.0), verts=vs)
    S.obj("w_props", S.mesh_from_bm("w_props", bm, [S.pbr("w_propb", hexc("2a2d31"), 0.5, var=0), dark]))
    # spare engine on a cradle
    bm = bmesh.new()
    tab = [(1.8, 0.4, 0.4, -0.4), (1.3, 0.75, 0.75, -0.75), (-1.5, 0.7, 0.7, -0.7), (-2.6, 0.3, 0.3, -0.3)]
    A._loft(bm, tab, n=20, step=0.3, mat_index=0)
    S.obj("w_spare_engine", S.mesh_from_bm("w_spare_engine", bm, [metal], smooth=True), (x0 + 6.0, y0 - 7.0, 1.4),
          (0, 0, 0.6))
    bm = bmesh.new()
    _box(bm, (0, 0, 0.35), (1.8, 4.0, 0.3), 0)
    for sy in (-1, 1):
        _box(bm, (0, sy * 1.2, 0.7), (1.6, 0.25, 0.7), 0)
    S.obj("w_cradle", S.mesh_from_bm("w_cradle", bm, [dark]), (x0 + 6.0, y0 - 7.0, 0.0), (0, 0, 0.6))
    # tyre stacks
    bm = bmesh.new()
    for k in range(4):
        for lv in range(3):
            r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.6, radius2=0.6, depth=0.35)
            bmesh.ops.translate(bm, vec=(x0 + 32.0 + k * 1.5, y0 + 2.0, 0.2 + lv * 0.37), verts=r["verts"])
    S.obj("w_tyrestack", S.mesh_from_bm("w_tyrestack", bm, [tyre], smooth=True))


def b_spares_v2(ctx, p):
    """In front of the hangars: a yard full of spare parts (crates, propellers, an engine, tyres); the cargo
    plane parked behind. Slow lateral dolly. Anchors: crates, engine, props."""
    T = ctx.frames
    build_winter_world(ctx, p)
    rng = random.Random(9)
    x0, y0 = 225.0, 760.0
    spares_yard(rng, x0, y0)
    parked_fleet(ctx, [(160.0, 800.0, math.pi / 2 + 0.25)])
    c0, t0 = (268.0, 744.0, 6.0), (222.0, 776.0, 2.5)
    c1, t1 = (265.0, 750.0, 6.5), (220.0, 778.0, 2.5)
    _cam(ctx, c0, t0, p.get("lens", 24))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "crates", bpy.data.objects["w_crates"], (x0 + 6.0, y0 + 3.0, 4.2))
    S.anchor(ctx, "engine", bpy.data.objects["w_spare_engine"], (0, 0, 1.0))


def b_old_fleet_v2(ctx, p):
    """A long row of the same old transports parked in the snow; slow dolly along the line."""
    T = ctx.frames
    build_winter_world(ctx, p)
    spots = [(150.0, 720.0 + 70.0 * k, math.pi / 2) for k in range(6)]
    parked_fleet(ctx, spots)
    c0, t0 = (200.0, 660.0, 16.0), (150.0, 800.0, 1.0)
    c1, t1 = (202.0, 716.0, 17.0), (150.0, 878.0, 1.0)
    _cam(ctx, c0, t0, p.get("lens", 30))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def build_hangar_interior(ctx, p):
    """Big lit maintenance hangar (own set: the door side is open to the snowy apron)."""
    floor = S.pbr("w_hfloor", hexc("8f9397"), 0.35, var=0.06, var_scale=0.2)
    wall = S.corrugated_mat("w_iwall", hexc("c8ced4"), 0.3, 0.5, 0.3)
    steel = S.pbr("w_truss", hexc("5d6670"), 0.4, 0.7, var=0)
    yellow = S.pbr("w_yellow", hexc("f2b632"), 0.5, var=0.02)
    W_, D_, H_ = 90.0, 80.0, 22.0
    cx, cy = 700.0, -600.0           # far from the field (own interior set inside the same world)
    S.plane_obj("w_hfloor", W_, D_, (cx, cy, 0.05), floor)
    bm = bmesh.new()
    _box(bm, (cx, cy + D_ / 2, H_ / 2), (W_, 0.6, H_), 0)
    for sx in (-1, 1):
        _box(bm, (cx + sx * W_ / 2, cy, H_ / 2), (0.6, D_, H_), 0)
    _box(bm, (cx, cy, H_ + 0.3), (W_, D_, 0.6), 0)
    _box(bm, (cx, cy - D_ / 2, H_ - 2.0), (W_, 0.6, 4.0), 0)
    S.obj("w_hall", S.mesh_from_bm("w_hall", bm, [wall]))
    bm = bmesh.new()
    for k in range(7):
        y = cy - D_ / 2 + 6 + k * 11.5
        _box(bm, (cx, y, H_ - 0.8), (W_ - 1.0, 0.5, 1.2), 0)
    S.obj("w_trusses", S.mesh_from_bm("w_trusses", bm, [steel]))
    # yellow work platforms either side of the fuselage + floor safety lines
    bm = bmesh.new()
    for sx in (-1, 1):
        _box(bm, (cx + sx * 4.6, cy - 6.0, 2.6), (2.0, 10.0, 0.25), 0)
        for yy in (-10.0, -2.0):
            _box(bm, (cx + sx * 4.6, cy + yy, 1.3), (0.2, 0.2, 2.6), 0)
        _box(bm, (cx + sx * 5.5, cy - 6.0, 3.6), (0.1, 10.0, 0.1), 0)
    for sx in (-1, 1):
        _box(bm, (cx + sx * 24.0, cy, 0.07), (0.3, D_ - 6, 0.02), 0)
    S.obj("w_platforms", S.mesh_from_bm("w_platforms", bm, [yellow]))
    for k in range(4):
        for sx in (-1, 1):
            A._area("w_hlamp%d_%d" % (k, sx), (cx + sx * 18.0, cy - 25 + k * 16.0, H_ - 1.5), 6.0, 2600.0,
                    rot=(0, 0, 0))
    A._area("w_hfill", (cx, cy - D_ / 2 - 5.0, 10.0), 40.0, 9000.0, color=(0.85, 0.92, 1.0),
            rot=(math.radians(-90), 0, 0))
    return cx, cy


def scan_rings(ctx, parent, ys, f0, f1, name="scan", color=hexc("38e0c8")):
    """Teal inspection rings sliding along the fuselage (real annulus geometry, emission keyed)."""
    import scene_lib_v2_travel as TV
    for k in range(2):
        m, sock = L.add_mat("%s_m%d" % (name, k), color, 0.0)
        bm = bmesh.new()
        TV._annulus(bm, 2.45, 0.12, 64)
        o = S.obj("%s%d" % (name, k), S.mesh_from_bm(name, bm, [m]), (0, ys[0], 0.1), (math.pi / 2, 0, 0), parent=parent)
        o.visible_shadow = False
        a, b = f0 + k * 30, f1 + k * 30
        set_keys(o, "location", [1, a, b], [(0, ys[0], 0.1), (0, ys[0], 0.1), (0, ys[1], 0.1)], "LINEAR")
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, a, 0.0, "LINEAR")
        L.kf_socket(sock, a + 8, 5.0, "LINEAR")
        L.kf_socket(sock, b - 8, 5.0, "LINEAR")
        L.kf_socket(sock, b, 0.0, "LINEAR")


def b_hangar_check_v2(ctx, p):
    """Maintenance hangar: the cargo plane on stands with work platforms; teal inspection rings slide along the
    fuselage from `scan_cue`. Anchors: tail, wing."""
    T = ctx.frames
    build_winter_world(ctx, p)
    cx, cy = build_hangar_interior(ctx, p)
    root, parts = make_cargo_plane(ctx, "cg", spin=False)
    root.location = (cx, cy - 2.0, PZ - 0.2)
    f0 = ctx.word_time(p.get("scan_cue", "metal"), 0.2)
    scan_rings(ctx, root, (14.0, -13.0), f0, min(T - 20, f0 + 150))
    c0, t0 = (cx - 17.0, cy - 34.0, 5.5), (cx - 1.0, cy - 6.0, 4.0)
    c1, t1 = (cx - 13.0, cy - 30.0, 6.5), (cx, cy - 4.0, 4.0)
    _cam(ctx, c0, t0, p.get("lens", 22))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "tail", root, (0, -13.0, 6.0))
    S.anchor(ctx, "wing", root, (-12.0, 1.5, 2.6))


def b_classic_car_v2(ctx, p):
    """Same hangar: an old-style sedan with its bonnet... (no: a plain Kenney sedan) in the foreground on the
    floor, the big plane behind; camera pulls back from the car to reveal the plane."""
    T = ctx.frames
    build_winter_world(ctx, p)
    cx, cy = build_hangar_interior(ctx, p)
    root, parts = make_cargo_plane(ctx, "cg", spin=False)
    root.location = (cx, cy - 2.0, PZ - 0.2)
    car = L.make_car("classic", loc=(cx - 9.0, cy - 24.0, 0.05), rot_z=math.radians(150), headlights=True,
                     glow=False, model=p.get("model", "sedan"))
    S._repaint_kenney()
    c0, t0 = (cx - 15.0, cy - 31.0, 2.2), (cx - 9.0, cy - 24.0, 1.0)
    c1, t1 = (cx - 20.0, cy - 40.0, 5.0), (cx - 3.0, cy - 12.0, 4.0)
    _cam(ctx, c0, t0, p.get("lens", 24))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "car", car.obj, (0, 0, 1.6))


def b_cargo_outro(ctx, p):
    """The cargo plane takes off from the snowy runway and climbs away; camera cranes up over the field."""
    T = ctx.frames
    build_winter_world(ctx, p)
    root, parts = make_cargo_plane(ctx, "cg", spin=True)
    keys, rot = [], []
    y, v, z, pitch = p.get("y0", 450.0), p.get("v0", 54.0), PZ - 0.17, 0.0
    for f in range(1, T + 1):
        dt = 1.0 / ctx.fps
        if v < 62.0:
            v += 2.4 * dt
        else:
            v += 0.5 * dt
            pitch = min(8.0, pitch + 4.0 * dt)
            z += v * math.sin(math.radians(pitch)) * dt
        y += v * dt
        if f % 3 == 1 or f == T:
            keys.append((f, (0.0, y, z)))
            rot.append((f, pitch))
    tr = A._track("cg_track", keys, "LINEAR")
    root.parent = tr
    set_keys(root, "rotation_euler", [f for f, _ in rot], [(math.radians(pt), 0, 0) for _, pt in rot], "LINEAR")
    f_up = next((f for f, pt in rot if pt >= 7.9), None)
    if f_up is not None and f_up + 50 < T:
        set_keys(parts["gear"], "scale", [f_up + 10, f_up + 50], [(1, 1, 1), (1, 1, 0.0)], "BEZIER")
    pos = dict(keys)

    def at(f):
        k = min(pos, key=lambda q: abs(q - f))
        return Vector(pos[k])
    path = p.get("cam_path", [(0.0, (-60.0, 700.0, 5.0)), (0.45, (-110.0, 820.0, 25.0)), (1.0, (-220.0, 800.0, 50.0))])
    first = True
    for f in list(range(1, T + 1, 5)) + [T]:
        g = (f - 1) / float(max(1, T - 1))
        for (g0, c0), (g1, c1) in zip(path[:-1], path[1:]):
            if g0 <= g <= g1:
                u = (g - g0) / (g1 - g0)
                u = u * u * (3 - 2 * u)
                c = Vector(c0).lerp(Vector(c1), u)
                break
        tgt = at(f) + Vector((0, 6.0, 2.0))
        if first:
            _cam(ctx, tuple(c), tuple(tgt), p.get("lens", 26))
            first = False
        kf(ctx.cam, "location", f, c, "BEZIER")
        kf(ctx.cam_target, "location", f, tgt, "BEZIER")
    S.anchor(ctx, "plane", root, (0, 0, 3.0))


S.V2_BUILDERS.update({
    "cargo_hook": b_cargo_hook,
    "cargo_plate": b_cargo_plate,
    "rough_strip_v2": b_rough_strip_v2,
    "spares_v2": b_spares_v2,
    "old_fleet_v2": b_old_fleet_v2,
    "hangar_check_v2": b_hangar_check_v2,
    "classic_car_v2": b_classic_car_v2,
    "cargo_outro": b_cargo_outro,
})

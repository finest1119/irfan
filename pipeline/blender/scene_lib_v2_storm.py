"""v2 tropical-ocean / hurricane builders ("hurricane": how a hurricane is born, 24 Nov 2026).
Registers into scene_lib_v2.V2_BUILDERS.

World: a bright tropical ocean in daylight (HDRI sky), small sandy islands with palms, puffy white clouds. All
clouds are REAL geometry (clusters of smooth icospheres), stylised and friendly: no destruction, nobody shown.
No 3D text: every label / card is a 2D overlay reading the anchors set with S.anchor().

Builders
  storm_hook     ocean from high above with a cloud spiral turning counter-clockwise (northern hemisphere);
                 mode "fade": the spiral shrinks away from `fade_cue` (the engine shuts down)
  ocean_calm     low glide over the calm tropical sea towards an island
  warm_cut       the sea cut open (warm orange layer at the top): mode warm (heat arrows rising off the surface),
                 rise (moist-air arrows, a cloud tower grows, red heat arrows, inflow arrows),
                 shear (the tower is tipped over by upper winds and its top is torn off)
  globe_spin     a big globe over the sea turning west -> east, an amber spin band, a small spiral in the
                 Atlantic turning counter-clockwise
  eye_section    the storm cut in half: eye, eyewall, inflow / rising / sinking arrows
  coast_calm     the calm port town of the harbour world (no warship), slow glide
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
import scene_lib_v2_sea as SEA
from scene_lib import hexc
from scene_lib_v2_winter import set_keys

EXT = 30000.0
AMBER = "ffab1f"
REDC = "ff4b36"
TEALC = "19c9b4"


# ================================================================ materials
def ocean_mat(name="ocean_v2", color="1d86ad", wave=0.16, bump=0.2, dist=0.35, var=0.0025, spec=0.22):
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Roughness"].default_value = 0.14
    p.inputs["Specular IOR Level"].default_value = spec
    p.inputs["Emission Color"].default_value = hexc(color)
    p.inputs["Emission Strength"].default_value = 0.22
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 0.5, 1.0)
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = N.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = wave
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.55
    Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
    L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
    L.kf_socket(nz.inputs["W"], 900, 7.0, "LINEAR")
    b = N.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = bump
    b.inputs["Distance"].default_value = dist
    Lk.new(nz.outputs["Fac"], b.inputs["Height"])
    Lk.new(b.outputs["Normal"], p.inputs["Normal"])
    fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], var, 0.16)
    fac2, _ = S._noise_var(N, Lk, tc.outputs["Object"], var * 6.0, 0.06)
    c1 = S._mul_col(N, Lk, tuple(hexc(color)), fac)
    Lk.new(S._mul_col(N, Lk, c1, fac2), p.inputs["Base Color"])
    return S._finish(m, p.outputs[0])


def cloud_mat(name="cloud_v2", emis=0.45, col="ffffff"):
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc(col)
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    p.inputs["Emission Color"].default_value = hexc("eef3fb")
    p.inputs["Emission Strength"].default_value = emis
    S._finish(m, p.outputs[0])
    S._MV2[name] = m
    return m


def tower_mat(name="cloud_tower"):
    """Cloud for the tower shots: white facing the camera, blue-grey towards the silhouette of every puff, so the
    tower keeps its form against the bright cloudy sky (plain white puffs looked ghostly there)."""
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.42
    ramp = N.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.25, hexc("ffffff")
    els[1].position, els[1].color = 0.95, hexc("7f9cc4")
    Lk.new(lw.outputs["Facing"], ramp.inputs[0])
    Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
    Lk.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 0.78
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    S._finish(m, p.outputs[0], haze=False)
    S._MV2[name] = m
    return m


def section_mat(name, stops, z0, z1, emis=0.6):
    """Cut face coloured by height (object Z): stops = [(pos 0..1, hex)], pos 0 at z0, 1 at z1. Self-lit."""
    m, nt, N, Lk, p = S._new_mat(name)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    Lk.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = N.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (pos, col) in zip(els, stops):
        e.position = pos
        e.color = hexc(col)
    Lk.new(mr.outputs["Result"], ramp.inputs[0])
    Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
    Lk.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = emis
    p.inputs["Roughness"].default_value = 0.5
    return S._finish(m, p.outputs[0], haze=False)


def glow(name, col, strength=1.25):
    return S.emis(name, hexc(col), strength)


# ================================================================ geometry
def puffs(name, blobs, mat, loc=(0, 0, 0), parent=None, sub=2):
    """blobs = [(x, y, z, r, flat)] -> one smooth mesh of icospheres (flat = vertical squash)."""
    bm = bmesh.new()
    for x, y, z, r, fl in blobs:
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0,
                                   matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r, r, r * fl, 1.0)))
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat], smooth=True), loc, parent=parent)
    return o


def cumulus(name, rng, loc, size, mat, n=9):
    bl = []
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 1.0) * size
        r = size * rng.uniform(0.45, 0.8) * (1.0 - 0.35 * d / size)
        bl.append((math.cos(a) * d * 1.3, math.sin(a) * d * 0.8, r * 0.25 + rng.uniform(0, 0.25) * size, r, 0.75))
    return puffs(name, bl, mat, loc)


def spiral_blobs(rng, R, eye, top, arms=2, flat=0.5, turn=1.2 * math.pi, dens=1.0):
    """Blobs lying on the top surface of a northern-hemisphere storm (centre at the origin). Following an arm
    OUTWARD the angle DEcreases (clockwise), so the bands spiral INWARD counter-clockwise, like a real one.
    top(r) -> cloud-top height. Returns [(x, y, z, r, flat, radius)]."""
    out = []
    core = 0.4 * R

    def add(r, a, s):
        out.append((r * math.cos(a), r * math.sin(a), top(r) - s * flat * 0.55, s, flat, r))
    for i in range(int(380 * dens)):
        u = rng.random() ** 0.8
        r = eye + (core - eye) * u
        s = R * 0.085 * (1.2 - 0.55 * u) * rng.uniform(0.8, 1.25)
        if r - s * 0.75 < eye:
            r = eye + s * 0.75
        add(r, rng.uniform(0, 2 * math.pi), s)
    for k in range(int(30 * dens)):
        add(eye * 1.25, 2 * math.pi * k / int(30 * dens), R * 0.1 * rng.uniform(0.9, 1.15))
    r0 = 0.33 * R
    b = math.log(R / r0) / turn
    for k in range(arms):
        th0 = 2 * math.pi * k / arms + rng.uniform(-0.15, 0.15)
        n = int(300 * dens)
        for i in range(n):
            t = turn * (i / (n - 1)) ** 0.9
            r = r0 * math.exp(b * t)
            w = R * 0.2 * (1.0 - 0.62 * r / R)
            rr = r + rng.gauss(0, w * 0.45)
            s = R * 0.07 * (1.15 - 0.6 * r / R) * rng.uniform(0.7, 1.25)
            add(rr, th0 - t + rng.gauss(0, 0.03), s)
    return out


def make_spiral(name, rng, R, eye, top, mat, groups=5, flat=0.5, dens=1.0, keep=None, sub=2):
    """Root empty + `groups` ring objects (inner -> outer) so the storm can grow / fade ring by ring."""
    root = L.link(bpy.data.objects.new(name, None))
    bl = spiral_blobs(rng, R, eye, top, flat=flat, dens=dens)
    if keep:
        bl = [b for b in bl if keep(b)]
    parts = []
    for g in range(groups):
        lo, hi = R * 1.3 * g / groups, R * 1.3 * (g + 1) / groups
        sel = [b[:5] for b in bl if lo <= b[5] < hi or (g == groups - 1 and b[5] >= hi)]
        if sel:
            parts.append(puffs("%s_g%d" % (name, g), sel, mat, parent=root, sub=sub))
    return root, parts


def arrow(name, length, width, mat, ang=90.0, loc=(0, 0, 0), parent=None, head=0.42):
    """Flat arrow in the XZ plane (faces the camera looking +Y). ang: 0 = +X, 90 = up, 180 = -X, -90 = down.
    Origin at the middle."""
    hl = length * head
    w, hw = width * 0.5, width * 1.15
    pts = [(-length / 2, -w), (length / 2 - hl, -w), (length / 2 - hl, -hw), (length / 2, 0.0),
           (length / 2 - hl, hw), (length / 2 - hl, w), (-length / 2, w)]
    bm = bmesh.new()
    SEA._poly_xz(bm, pts, 0.0, 0, flip=True)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), loc, parent=parent)
    o.rotation_euler = (0.0, -math.radians(ang), 0.0)
    o.visible_shadow = False
    return o


def loop_move(o, p0, p1, T, f_on, period, phase=0.0, f_off=None, grow=7):
    """o travels p0 -> p1 again and again from frame f_on (hidden before / after f_off). It scales in and out at
    the ends of each pass, so the jump back is never seen."""
    fr, loc, sc = [1], [tuple(p0)], [(0.0, 0.0, 0.0)]
    f = f_on - int(period * phase)
    end = (f_off if f_off is not None else T + 2)
    while f < end:
        a, b = f, f + period - 1
        if b >= f_on and a < end:
            if a < f_on:        # partial first pass: start where it would be
                u = (f_on - a) / float(period - 1)
                pa = Vector(p0).lerp(Vector(p1), u)
                a = f_on
            else:
                pa = Vector(p0)
            if a > fr[-1]:
                fr += [a, min(a + grow, b - 1), max(b - grow, a + 1), b]
                loc += [tuple(pa), tuple(pa.lerp(Vector(p1), grow / float(max(1, b - a)))),
                        tuple(Vector(p1).lerp(pa, grow / float(max(1, b - a)))), tuple(p1)]
                sc += [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)]
        f += period
    if len(fr) == 1:
        fr.append(2)
        loc.append(tuple(p0))
        sc.append((0.0, 0.0, 0.0))
    # strictly increasing frames
    ff, ll, ss = [fr[0]], [loc[0]], [sc[0]]
    for a, b, c in zip(fr[1:], loc[1:], sc[1:]):
        if a > ff[-1]:
            ff.append(a)
            ll.append(b)
            ss.append(c)
    set_keys(o, "location", ff, ll, "LINEAR")
    set_keys(o, "scale", ff, ss, "LINEAR")


def island(name, x, y, r, rng, palms=None, h=None):
    sand = S.pbr("isl_sand", hexc("ead9a8"), 0.9, var=0.06, var_scale=0.05)
    green = S.pbr("isl_green", hexc("4f8a3c"), 0.9, var=0.14, var_scale=0.02, bump=0.05)
    h = h or r * 0.22
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r, radius2=r * 0.72, depth=5.0)
    bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=res["verts"])
    for k in range(5):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 0.3) * r
        rr = r * rng.uniform(0.3, 0.55)
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0, matrix=Matrix.Translation(
            (math.cos(a) * d, math.sin(a) * d, 2.5)) @ Matrix.Diagonal((rr, rr * 0.8, h * rng.uniform(0.6, 1.0), 1.0)))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 1
    o = S.obj(name, S.mesh_from_bm(name, bm, [sand, green], smooth=True), (x, y, 0.0))
    if palms:
        pts = []
        for k in range(int(r / 3.5)):
            a = rng.uniform(0, 2 * math.pi)
            d = r * rng.uniform(0.62, 0.84)
            pts.append((x + math.cos(a) * d, y + math.sin(a) * d * 0.9))
        for po in S.scatter(palms, pts, rng, (0.9, 1.5), prefix=name + "_p"):
            po.location.z = 2.6
    return o


# ================================================================ worlds
def build_ocean(ctx, p, cut=False, fog=0.00004, fog_start=900.0, wave=0.16, bump=0.2, dist=0.35, islands=True,
                far_clouds=False, haze_hi=0.09, far_gap=0.0):
    """Sky + tropical sea (+ islands, + a row of far cumulus low over the horizon). cut=True: the sea only exists
    for y >= 0 and a self-lit section face (warm orange surface layer over deep blue) closes it at y = 0."""
    rng = random.Random(p.get("seed", 9))
    S.daylight(ctx, p.get("sun_az", -25.0), 40.0, hdri=p.get("hdri", True))
    L.fog(p.get("fog", fog), S.HAZE, start=fog_start)
    C.horizon_haze(ctx.scene, lo=0.02, hi=0.2)   # also hides a building on the HDRI horizon
    sea = ocean_mat(wave=wave, bump=bump, dist=dist)
    if not cut:
        S.plane_obj("sea", 2 * EXT, 2 * EXT, (0, 0, 0.0), sea)
    else:
        S.plane_obj("sea", 2 * EXT, EXT, (0, EXT / 2, 0.0), sea)
        sm = section_mat("sea_sec", [(0.0, "ff8a35"), (0.11, "ffb45e"), (0.22, "3fa9c6"), (1.0, "0f4a78")],
                         0.0, -560.0, 0.7)
        bm = bmesh.new()
        SEA._poly_xz(bm, [(-6000, 0.0), (6000, 0.0), (6000, -4000.0), (-6000, -4000.0)], 0.0, 0, flip=True)
        o = S.obj("sea_section", S.mesh_from_bm("sea_section", bm, [sm]))
        o.visible_shadow = False
        bm = bmesh.new()
        SEA._poly_xz(bm, [(-6000, 1.5), (6000, 1.5), (6000, -3.0), (-6000, -3.0)], -0.3, 0, flip=True)
        o = S.obj("sea_edge", S.mesh_from_bm("sea_edge", bm, [glow("sea_edge_m", "fff1d8", 1.3)]))
        o.visible_shadow = False
    cm = cloud_mat()
    if islands:
        palms = SEA._palm_templates(rng)
        for k, (x, y, r) in enumerate(p.get("islands", [(-900.0, 2600.0, 150.0), (1300.0, 3900.0, 220.0)])):
            island("isl%d" % k, x, y, r, rng, palms)
    if far_clouds:
        for k in range(p.get("n_far", 16)):
            x = rng.uniform(-9000, 9000)
            y = rng.uniform(7000, 14000)
            if abs(x) < far_gap * y:
                continue
            cumulus("far%d" % k, rng, (x, y, rng.uniform(380, 620)), rng.uniform(260, 480), cm).visible_shadow = False
    return {"rng": rng, "cloud": cm}


def _cam(ctx, loc, tgt, lens=30, clip=2.0):
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = clip
    cam.data.clip_end = 60000.0
    return cam


def _anc(ctx, name, loc, parent=None):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    S.anchor(ctx, name, e)
    return e


# ================================================================ BUILDERS
def b_storm_hook(ctx, p):
    """Tropical ocean from high above with a white cloud spiral turning counter-clockwise; small cumulus around.
    mode 'fade': from `fade_cue` the rings shrink away, outer first. Anchor: storm."""
    T = ctx.frames
    w = build_ocean(ctx, p, fog=0.000035, fog_start=1500.0, wave=0.02, bump=0.12, dist=2.5, islands=False,
                    far_clouds=False)
    rng = w["rng"]
    R = 700.0
    root, parts = make_spiral("storm", rng, R, 0.12 * R, lambda r: 150.0 - 70.0 * min(1.0, r / R), w["cloud"])
    spin = math.radians(p.get("spin_deg", 38.0)) * T / 240.0
    a0 = math.radians(p.get("rot0", 0.0))
    set_keys(root, "rotation_euler", [1, T], [(0, 0, a0), (0, 0, a0 + spin)], "LINEAR")
    mode = p.get("mode", "hook")
    n = len(parts)
    if mode == "fade":
        f0 = ctx.word_time(p.get("fade_cue", "cools"), 0.6)
        for g, o in enumerate(parts):
            fa = f0 + (n - 1 - g) * 9
            s1 = 0.0 if g > 0 else 0.25
            set_keys(o, "scale", [1, fa, fa + 55], [(1, 1, 1), (1, 1, 1), (s1, s1, s1)], "BEZIER")
    else:
        for g, o in enumerate(parts):
            s0 = 1.0 - 0.12 * g
            set_keys(o, "scale", [1, int(T * 0.7)], [(s0, s0, s0), (1, 1, 1)], "BEZIER")
    for k in range(26):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(R * 1.25, R * 2.6)
        x, y = math.cos(a) * d, math.sin(a) * d
        if y > 950.0:
            continue
        cumulus("cu%d" % k, rng, (x, y, 60.0), rng.uniform(45, 85), w["cloud"])
    _anc(ctx, "storm", (0, 0, 160.0))
    c0 = p.get("cam0", (260.0, -2500.0, 2650.0))
    t0 = p.get("tgt0", (0.0, 330.0, 0.0))
    c1 = p.get("cam1", (120.0, -2350.0, 2500.0))
    t1 = p.get("tgt1", (0.0, 300.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 30), clip=20.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_ocean_calm(ctx, p):
    """Low glide over the calm tropical sea towards a palm island; puffy clouds low over the horizon."""
    T = ctx.frames
    p = dict(p)
    p.setdefault("islands", [(60.0, 420.0, 150.0), (-520.0, 1500.0, 190.0), (700.0, 2300.0, 240.0)])
    build_ocean(ctx, p)
    c0 = p.get("cam0", (-60.0, -420.0, 95.0))
    t0 = p.get("tgt0", (40.0, 420.0, 130.0))
    c1 = p.get("cam1", (-30.0, -330.0, 85.0))
    _cam(ctx, c0, t0, p.get("lens", 30), clip=1.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])


TOWER_Y = 110.0
ARROW_Y = -60.0


def _tower(rng, mat, nl=11, z0=120.0, z1=520.0):
    """Cloud tower as `nl` layer objects (bottom -> top), each with its origin on the axis at its own height."""
    layers = []
    for i in range(nl):
        u = i / float(nl - 1)
        z = z0 + (z1 - z0) * u
        rad = 80.0 + 30.0 * math.sin(u * math.pi * 0.9) + (60.0 * max(0.0, u - 0.72) / 0.28)
        bl = []
        for k in range(10):
            a = 2 * math.pi * k / 10 + rng.uniform(-0.3, 0.3)
            d = rad * rng.uniform(0.45, 0.75)
            bl.append((math.cos(a) * d, math.sin(a) * d * 0.6, rng.uniform(-10, 10), rad * rng.uniform(0.42, 0.6), 0.85))
        bl.append((0.0, 0.0, 0.0, rad * 0.7, 0.8))
        o = puffs("tower_%02d" % i, bl, mat, (0.0, TOWER_Y, z))
        layers.append((o, z, u))
    return layers


def b_warm_cut(ctx, p):
    """The sea cut open in front of the camera (warm orange surface layer). Modes:
    warm : amber heat arrows rise gently off the surface (anchor: warm)
    rise : moist-air arrows rise, a cloud tower grows from `cloud_cue`, red heat arrows from `heat_cue`, inflow
           arrows along the surface from `pull_cue` (anchors: air, heat)
    shear: the grown tower; from `shear_cue` upper-level wind arrows blow across the top, from `tip_cue` the tower
           leans over and from `apart_cue` its top is torn off (anchor: shear)"""
    T = ctx.frames
    mode = p.get("mode", "warm")
    w = build_ocean(ctx, p, cut=True, far_gap=0.3)
    rng = w["rng"]
    am = glow("arr_amber", AMBER)
    rm = glow("arr_red", REDC)
    tm = glow("arr_teal", TEALC)
    if mode == "warm":
        f0 = ctx.word_time(p.get("warm_cue", "warm"), 0.15)
        for k in range(7):
            x = -180.0 + 60.0 * k + rng.uniform(-8, 8)
            a = arrow("heat%d" % k, 38.0, 11.0, am, 90.0)
            loop_move(a, (x, ARROW_Y * 0.3, 10.0), (x, ARROW_Y * 0.3, 105.0), T, f0 + 3 * k, 54 + (k % 3) * 6,
                      phase=rng.random())
        _anc(ctx, "warm", (40.0, -1.0, -28.0))
        _anc(ctx, "air", (-60.0, ARROW_Y * 0.3, 80.0))
        c0 = p.get("cam0", (-30.0, -720.0, 78.0))
        t0 = p.get("tgt0", (0.0, 0.0, 126.0))
        c1 = p.get("cam1", (25.0, -660.0, 72.0))
        t1 = p.get("tgt1", (0.0, 0.0, 116.0))
        _cam(ctx, c0, t0, p.get("lens", 30))
        A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])
        return
    layers = _tower(rng, tower_mat())
    nl = len(layers)
    if mode == "rise":
        f_c = ctx.word_time(p.get("cloud_cue", "condenses"), 0.3)
        f_r = ctx.word_time(p.get("rise_cue", "rises"), 0.08)
        f_h = ctx.word_time(p.get("heat_cue", "releases"), 0.45)
        f_f = ctx.word_time(p.get("fast_cue", "faster"), 0.65)
        f_p = ctx.word_time(p.get("pull_cue", "pulling"), 0.75)
        for i, (o, z, u) in enumerate(layers):
            if i < 3:        # a first small cloud already forms while the air "rises"
                fa = f_r + i * 16
            elif i < 6:
                fa = f_c + (i - 3) * 9
            else:
                fa = max(f_c + 3 * 9, f_h + 20) + int((i - 6) * (f_f + 25 - f_h - 20) / float(nl - 6))
            set_keys(o, "scale", [1, fa, fa + (30 if i < 3 else 16)], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "BEZIER")
        for k in range(5):
            x = -72.0 + 36.0 * k
            a = arrow("up%d" % k, 52.0, 15.0, am, 90.0)
            loop_move(a, (x, ARROW_Y, 12.0), (x, ARROW_Y, 108.0), T, 4 + 3 * k, 44, phase=k * 0.23)
        for k in range(6):
            sx = -1 if k % 2 == 0 else 1
            z = 205.0 + 62.0 * (k // 2)
            a = arrow("rel%d" % k, 62.0, 17.0, rm, 0.0 if sx > 0 else 180.0)
            loop_move(a, (sx * 70.0, ARROW_Y, z), (sx * 215.0, ARROW_Y, z), T, f_h + 2 * k, 40, phase=k * 0.17)
        for k in range(6):
            sx = -1 if k % 2 == 0 else 1
            a = arrow("in%d" % k, 64.0, 16.0, am, 180.0 if sx > 0 else 0.0)
            loop_move(a, (sx * 400.0, ARROW_Y, 34.0), (sx * 130.0, ARROW_Y, 34.0), T, f_p + 2 * k, 60,
                      phase=(k // 2) * 0.33)
        _anc(ctx, "air", (-78.0, ARROW_Y, 62.0))
        _anc(ctx, "heat", (170.0, ARROW_Y, 268.0))
        _anc(ctx, "inflow", (-270.0, ARROW_Y, 30.0))
    else:
        f_s = ctx.word_time(p.get("shear_cue", "sharply"), 0.25)
        f_t = ctx.word_time(p.get("tip_cue", "tip"), 0.45)
        f_a = ctx.word_time(p.get("apart_cue", "falls"), 0.6)
        lean = [(1, 0.0), (f_t, 0.04), (f_a, 0.6), (f_a + 45, 1.0), (T + 10, 1.15)]
        fr = list(range(1, T + 1, 3)) + [T + 1]

        def lv(f):
            for (fa, va), (fb, vb) in zip(lean[:-1], lean[1:]):
                if fa <= f <= fb:
                    return va + (vb - va) * L.smooth((f - fa) / float(max(1, fb - fa)))
            return lean[-1][1]
        for i, (o, z, u) in enumerate(layers):
            amp = 300.0 * u ** 1.5
            set_keys(o, "location", fr, [(amp * lv(f), TOWER_Y, z - 60.0 * u * u * lv(f)) for f in fr], "LINEAR")
            if u > 0.55:
                s1 = 1.0 - 0.75 * (u - 0.55) / 0.45
                set_keys(o, "scale", [1, f_a, f_a + 70], [(1, 1, 1), (1, 1, 1), (s1, s1, s1)], "BEZIER")
        for k in range(4):
            z = 520.0 - 62.0 * (k % 2) - 20.0 * (k // 2)
            a = arrow("hi%d" % k, 110.0, 20.0, tm, 0.0)
            loop_move(a, (-380.0, ARROW_Y, z), (330.0, ARROW_Y, z), T, f_s + 4 * k, 46, phase=k * 0.27)
        for k in range(3):
            a = arrow("lo%d" % k, 56.0, 14.0, am, 180.0)
            loop_move(a, (330.0, ARROW_Y, 60.0 + 22.0 * (k % 2)), (-330.0, ARROW_Y, 60.0 + 22.0 * (k % 2)), T,
                      f_s + 6 * k, 120, phase=k * 0.33)
        _anc(ctx, "shear", (-150.0, ARROW_Y, 505.0))
        _anc(ctx, "tower", (0.0, ARROW_Y, 300.0))
    c0 = p.get("cam0", (-60.0, -1850.0, 250.0))
    t0 = p.get("tgt0", (0.0, 0.0, 322.0))
    c1 = p.get("cam1", (50.0, -1780.0, 240.0))
    t1 = p.get("tgt1", (0.0, 0.0, 316.0))
    _cam(ctx, c0, t0, p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


# ---------------------------------------------------------------- globe
LAND = {
    "na": [(-168, 66), (-156, 71), (-140, 70), (-125, 70), (-110, 68), (-95, 72), (-85, 70), (-80, 73), (-75, 68),
           (-78, 62), (-65, 60), (-60, 54), (-56, 52), (-66, 45), (-70, 42), (-75, 38), (-76, 35), (-81, 31),
           (-80, 26), (-82, 26), (-84, 30), (-90, 29), (-97, 26), (-97, 22), (-94, 18), (-90, 21), (-87, 21),
           (-88, 16), (-83, 15), (-83, 10), (-79, 9), (-77, 8), (-80, 7), (-85, 10), (-92, 15), (-97, 16),
           (-105, 20), (-110, 24), (-113, 31), (-117, 33), (-121, 35), (-124, 41), (-124, 48), (-130, 54),
           (-140, 60), (-150, 60), (-158, 57), (-165, 61)],
    "greenland": [(-45, 60), (-52, 65), (-55, 70), (-65, 77), (-60, 82), (-35, 83), (-20, 80), (-22, 72), (-35, 66),
                  (-42, 61)],
    "sa": [(-77, 8), (-72, 12), (-62, 10), (-52, 5), (-50, 0), (-44, -2), (-35, -6), (-39, -14), (-41, -22),
           (-48, -27), (-54, -34), (-58, -38), (-65, -42), (-68, -50), (-69, -54), (-74, -52), (-73, -40),
           (-71, -30), (-70, -18), (-76, -14), (-81, -5), (-80, 0), (-78, 3)],
    "africa": [(-17, 15), (-16, 22), (-10, 29), (-6, 35), (10, 37), (11, 33), (20, 31), (32, 31), (35, 24), (38, 18),
               (43, 12), (51, 11), (48, 4), (40, -3), (39, -10), (35, -22), (32, -28), (26, -34), (19, -34),
               (16, -28), (12, -17), (13, -8), (9, -1), (9, 4), (4, 6), (-4, 5), (-8, 4), (-13, 8), (-17, 12)],
    "eurasia": [(-9, 37), (-9, 43), (-1, 44), (-4, 48), (2, 51), (8, 54), (8, 57), (5, 58), (6, 62), (14, 68),
                (26, 71), (40, 67), (60, 69), (80, 73), (105, 77), (140, 73), (170, 70), (180, 66), (170, 60),
                (160, 53), (155, 58), (140, 55), (135, 45), (128, 40), (122, 38), (122, 30), (110, 20), (108, 12),
                (104, 9), (100, 14), (98, 8), (98, 16), (92, 22), (88, 22), (80, 15), (77, 8), (73, 18), (67, 25),
                (57, 25), (52, 16), (44, 13), (40, 20), (35, 28), (36, 36), (28, 36), (27, 40), (23, 38), (19, 42),
                (13, 45), (16, 40), (12, 43), (8, 44), (3, 43), (0, 39), (-2, 37), (-5, 36)],
    "uk": [(-5, 50), (1, 51), (0, 54), (-2, 56), (-3, 58), (-6, 57), (-5, 54), (-3, 52)],
    "ireland": [(-10, 52), (-6, 52), (-6, 55), (-9, 55)],
    "iceland": [(-24, 65), (-14, 64), (-14, 66), (-22, 66)],
    "cuba": [(-85, 22), (-80, 23), (-74, 20), (-78, 20)],
    "hisp": [(-74, 19.5), (-68, 19.5), (-69, 18), (-73, 18)],
    "australia": [(114, -22), (122, -17), (131, -12), (137, -16), (142, -11), (146, -19), (153, -27), (150, -37),
                  (141, -38), (131, -32), (116, -35)],
    "antarctica": [(-180, -72), (-60, -66), (0, -70), (90, -67), (180, -72), (180, -90), (-180, -90)],
}
WATER = {"hudson": [(-94, 58), (-88, 64), (-80, 62), (-78, 55), (-82, 52), (-90, 56)]}


def earth_image(w=2048, h=1024):
    """Stylised equirectangular Earth drawn with numpy (no PIL inside Blender): simplified continents."""
    import numpy as np
    lon = (np.arange(w) + 0.5) / w * 360.0 - 180.0
    lat = (np.arange(h) + 0.5) / h * 180.0 - 90.0          # row 0 = south (Blender image origin = bottom left)
    LON, LAT = np.meshgrid(lon, lat)

    def inside(poly):
        xs = [q[0] for q in poly]
        ys = [q[1] for q in poly]
        box = (LON >= min(xs)) & (LON <= max(xs)) & (LAT >= min(ys)) & (LAT <= max(ys))
        m = np.zeros(LON.shape, bool)
        if not box.any():
            return m
        X, Y = LON[box], LAT[box]
        c = np.zeros(X.shape, bool)
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if y1 == y2:
                continue
            hit = ((y1 > Y) != (y2 > Y)) & (X < (x2 - x1) * (Y - y1) / (y2 - y1) + x1)
            c ^= hit
        m[box] = c
        return m
    img = np.zeros((h, w, 4), np.float32)
    img[..., 3] = 1.0
    deep = np.array(hexc("1f78b8")[:3])
    shallow = np.array(hexc("38a3d6")[:3])
    k = np.clip(1.0 - np.abs(LAT) / 60.0, 0, 1)[..., None]
    img[..., :3] = deep * (1 - k) + shallow * k
    green = np.array(hexc("5d9a48")[:3])
    dark = np.array(hexc("3f7d3c")[:3])
    tan = np.array(hexc("d8c184")[:3])
    ice = np.array(hexc("f1f5f8")[:3])
    rs = np.random.RandomState(4)
    noise = rs.rand(h // 16 + 1, w // 16 + 1).repeat(16, 0).repeat(16, 1)[:h, :w][..., None]
    for name, poly in LAND.items():
        m = inside(poly)
        if name in ("greenland", "antarctica", "iceland"):
            col = np.broadcast_to(ice, img[..., :3].shape)
        else:
            a = np.abs(LAT)[..., None]
            trop = np.clip((a - 8.0) / 12.0, 0, 1)
            dry = np.clip((a - 14.0) / 8.0, 0, 1) * np.clip((36.0 - a) / 6.0, 0, 1)
            if name not in ("africa", "australia", "eurasia", "na"):
                dry = dry * 0.0
            if name == "eurasia":
                dry = dry * (LON[..., None] > 25) * (LON[..., None] < 75)
            if name == "na":
                dry = dry * (LON[..., None] < -100) * 0.8
            col = dark * (1 - trop) + green * trop
            col = col * (1 - dry) + tan * dry
            cold = np.clip((a - 60.0) / 12.0, 0, 1)
            col = col * (1 - cold) + ice * cold
            col = col * (0.93 + 0.14 * noise)
        img[..., :3][m] = col[m]
    for poly in WATER.values():
        m = inside(poly)
        img[..., :3][m] = (deep * 0.6 + shallow * 0.4)
    im = bpy.data.images.new("earth_v2", w, h, alpha=False)
    im.pixels.foreach_set(img.ravel())
    im.pack()
    return im


def make_globe(name, R):
    """Sphere with our own UVs: lon/lat -> (cos lat cos lon, cos lat sin lon, sin lat) * R, so with +Z = north,
    east is CCW seen from above and a +Z rotation is the Earth's west -> east spin."""
    nu, nv = 96, 48
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("uv")
    grid = []
    for j in range(nv + 1):
        la = -math.pi / 2 + math.pi * j / nv
        row = []
        for i in range(nu + 1):
            lo = -math.pi + 2 * math.pi * i / nu
            row.append(bm.verts.new((R * math.cos(la) * math.cos(lo), R * math.cos(la) * math.sin(lo),
                                     R * math.sin(la))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            try:
                f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            except ValueError:
                continue
            for lp, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uvl].uv = (ii / float(nu), jj / float(nv))
    m, nt, N, Lk, p = S._new_mat("earth_m")
    tex = N.new("ShaderNodeTexImage")
    tex.image = earth_image()
    tex.extension = "EXTEND"
    Lk.new(tex.outputs["Color"], p.inputs["Base Color"])
    Lk.new(tex.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 0.5
    p.inputs["Roughness"].default_value = 0.55
    p.inputs["Coat Weight"].default_value = 0.3
    S._finish(m, p.outputs[0], haze=False)
    return S.obj(name, S.mesh_from_bm(name, bm, [m], smooth=True))


def _band(name, R, a0, a1, hw, mat, head=0.0, seg=64, parent=None):
    """Vertical strip on a cylinder of radius R from angle a0 to a1 (deg, in XY), half-height hw; with head > 0
    an arrow head (deg long) is added past a1."""
    bm = bmesh.new()
    prev = None
    for k in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * k / seg)
        lo = bm.verts.new((R * math.cos(a), R * math.sin(a), -hw))
        hi = bm.verts.new((R * math.cos(a), R * math.sin(a), hw))
        if prev:
            bm.faces.new((prev[0], lo, hi, prev[1]))
        prev = (lo, hi)
    if head:
        a = math.radians(a1)
        b = math.radians(a1 + head)
        v1 = bm.verts.new((R * math.cos(a), R * math.sin(a), -hw * 2.6))
        v2 = bm.verts.new((R * math.cos(b), R * math.sin(b), 0.0))
        v3 = bm.verts.new((R * math.cos(a), R * math.sin(a), hw * 2.6))
        bm.faces.new((v1, v2, v3))
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), parent=parent)
    o.visible_shadow = False
    return o


def b_globe_spin(ctx, p):
    """A big globe floating over the tropical sea, turning west -> east (amber spin band with an arrow head);
    a small cloud spiral in the tropical Atlantic turns counter-clockwise. Anchors: storm, equator, band."""
    T = ctx.frames
    w = build_ocean(ctx, p, far_gap=0.2)
    R = 300.0
    cz = p.get("globe_z", 430.0)
    tilt = L.link(bpy.data.objects.new("globe_tilt", None))
    tilt.location = (0.0, 0.0, cz)
    tilt.rotation_euler = (math.radians(p.get("tilt", 20.0)), 0.0, 0.0)
    g = make_globe("globe", R)
    g.visible_shadow = False
    g.parent = tilt
    lon0, lon1 = p.get("lon0", -42.0), p.get("lon1", -62.0)     # longitude facing the camera (camera is at -Y)
    set_keys(g, "rotation_euler", [1, T], [(0, 0, math.radians(-90.0 - lon0)), (0, 0, math.radians(-90.0 - lon1))],
             "LINEAR")
    # equator line on the surface
    _band("equator", R * 1.004, 0.0, 360.0, R * 0.006, glow("eq_m", "ffffff", 1.6), seg=128, parent=tilt)
    # spin band (front arc, arrow head pointing east = to the right)
    bm_ = glow("band_m", AMBER)
    band = _band("spin_band", R * 1.09, -160.0, -52.0, R * 0.028, bm_, head=13.0, parent=tilt)
    set_keys(band, "rotation_euler", [1, T], [(0, 0, math.radians(-12.0)), (0, 0, math.radians(14.0))], "LINEAR")
    # storm in the tropical Atlantic
    slon, slat = math.radians(p.get("storm_lon", -52.0)), math.radians(p.get("storm_lat", 22.0))
    nrm = Vector((math.cos(slat) * math.cos(slon), math.cos(slat) * math.sin(slon), math.sin(slat)))
    hold = L.link(bpy.data.objects.new("storm_hold", None))
    hold.parent = g
    hold.location = nrm * (R * 1.012)
    hold.rotation_euler = Vector((0, 0, 1)).rotation_difference(nrm).to_euler()
    r_s = R * 0.21
    root, parts = make_spiral("gstorm", w["rng"], r_s, 0.13 * r_s, lambda r: 9.0 - 4.0 * min(1.0, r / r_s),
                              cloud_mat("cloud_globe", 0.45), groups=1, flat=0.45, dens=0.6, sub=1)
    root.parent = hold
    f_t = ctx.word_time(p.get("turn_cue", "turn"), 0.4)
    set_keys(root, "rotation_euler", [1, f_t, T], [(0, 0, 0), (0, 0, math.radians(15.0)),
                                                   (0, 0, math.radians(15.0 + 150.0 * (T - f_t) / 240.0))], "LINEAR")
    set_keys(root, "scale", [1, f_t - 20, f_t + 15], [(0.55, 0.55, 0.55), (0.6, 0.6, 0.6), (1, 1, 1)], "BEZIER")
    _anc(ctx, "storm", (0, 0, 12.0), parent=hold)
    _anc(ctx, "equator", (R * 0.45, -R * 0.9, 0.0), parent=tilt)
    _anc(ctx, "band", (-R * 0.62, -R * 0.9, 0.0), parent=tilt)
    c0 = p.get("cam0", (-40.0, -1640.0, cz + 10.0))
    t0 = p.get("tgt0", (0.0, 0.0, cz + 88.0))
    c1 = p.get("cam1", (40.0, -1560.0, cz + 6.0))
    t1 = p.get("tgt1", (0.0, 0.0, cz + 84.0))
    _cam(ctx, c0, t0, p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


# ---------------------------------------------------------------- eye cross-section
def b_eye_section(ctx, p):
    """The storm cut in half (we see the back half and the cut face): clear eye in the middle, tall eyewall on both
    sides. Amber inflow arrows along the sea, red arrows rising in the eyewall, a teal arrow sinking in the eye from
    `sink_cue`. Anchors: eye, eyewall."""
    T = ctx.frames
    p = dict(p)
    w = build_ocean(ctx, p, cut=True, fog=0.00003, fog_start=2500.0, wave=0.03, bump=0.14, dist=1.6, islands=False)
    rng = w["rng"]
    R, eb, et, H, base = 560.0, 62.0, 150.0, 800.0, 100.0
    rp = et + 55.0

    def top(r):
        if r <= rp:
            return H
        return H * (1.0 - 0.5 * min(1.0, (r - rp) / (R - rp)) ** 0.75)
    root, parts = make_spiral("storm", rng, R, rp, top, w["cloud"], groups=1, flat=0.55, dens=1.5,
                              keep=lambda b: b[1] > b[3] * 0.55)
    # inner wall of the eye (back half) + outer rim so the back half reads as a solid cloud mass
    bl = []
    for k in range(11):
        a = math.pi * (k + 0.5) / 11
        bl.append(((et + 45.0) * math.cos(a), max(40.0, (et + 45.0) * math.sin(a)), H - 30.0, 60.0, 0.9))
    for k in range(34):
        a = math.pi * (k + 0.5) / 34
        for z in (base + 60.0, base + 190.0, top(R) - 60.0):
            bl.append(((R + 10) * math.cos(a), max(45.0, (R + 10) * math.sin(a)), z, 80.0, 0.9))
    puffs("storm_walls", bl, w["cloud"])
    # cut face (two halves)
    sm = section_mat("cloud_sec", [(0.0, "b4c8de"), (0.3, "dde8f4"), (1.0, "ffffff")], base, H, 0.85)
    # clear air in the eye: a pale sky-blue funnel between the two halves
    em_ = section_mat("eye_air", [(0.0, "8fcdf3"), (1.0, "d9f0ff")], base, H, 0.9)
    pe = []
    for k in range(7):
        u = k / 6.0
        pe.append((eb + (et - eb) * u ** 0.8, base + (H - 75.0 - base) * u))
    bm = bmesh.new()
    SEA._poly_xz(bm, [(-x, z) for x, z in reversed(pe)] + pe, 0.8, 0, flip=False)
    o = S.obj("eye_air", S.mesh_from_bm("eye_air", bm, [em_]))
    o.visible_shadow = False
    for sx in (1, -1):
        pts = [(eb, base), (R + 40.0, base), (R + 40.0, top(R) - 30.0)]
        for k in range(1, 8):
            r = R - (R - rp) * k / 7.0
            pts.append((r, top(r) - 22.0))
        pts += [(et + 12.0, H - 40.0), (et, H - 75.0)]
        for k in range(1, 6):
            u = 1.0 - k / 6.0
            pts.append((eb + (et - eb) * u ** 0.8, base + (H - 75.0 - base) * u))
        bm = bmesh.new()
        SEA._poly_xz(bm, [(sx * x, z) for x, z in pts], 0.5, 0, flip=(sx > 0))
        o = S.obj("cloud_sec%d" % sx, S.mesh_from_bm("cloud_sec", bm, [sm]))
        o.visible_shadow = False
    am = glow("arr_amber", AMBER)
    rm = glow("arr_red", REDC)
    tm = glow("arr_teal", TEALC)
    ay = -40.0
    for k in range(6):
        sx = -1 if k % 2 == 0 else 1
        a = arrow("in%d" % k, 120.0, 28.0, am, 180.0 if sx > 0 else 0.0)
        loop_move(a, (sx * 620.0, ay, 50.0), (sx * 150.0, ay, 50.0), T, 2 + 2 * k, 66, phase=(k // 2) * 0.33)
    for k in range(6):
        sx = -1 if k % 2 == 0 else 1
        a = arrow("up%d" % k, 125.0, 32.0, rm, 90.0)
        x = sx * (rp + 75.0)
        loop_move(a, (x, ay, 130.0), (x, ay, 690.0), T, 3 + 2 * k, 72, phase=(k // 2) * 0.33)
    f_s = ctx.word_time(p.get("sink_cue", "sinks"), 0.3)
    for k in range(2):
        a = arrow("dn%d" % k, 135.0, 36.0, tm, -90.0)
        loop_move(a, (0.0, ay, 700.0), (0.0, ay, 170.0), T, f_s + 4 * k, 80, phase=k * 0.5)
    _anc(ctx, "eye", (0.0, ay, 430.0))
    _anc(ctx, "eyewall", (rp + 150.0, ay, 560.0))
    _anc(ctx, "wall_l", (-(rp + 150.0), ay, 560.0))
    c0 = p.get("cam0", (-90.0, -2950.0, 1120.0))
    t0 = p.get("tgt0", (0.0, 0.0, 575.0))
    c1 = p.get("cam1", (80.0, -2840.0, 1080.0))
    t1 = p.get("tgt1", (0.0, 0.0, 560.0))
    _cam(ctx, c0, t0, p.get("lens", 30), clip=20.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_coast_calm(ctx, p):
    """The calm port town of the harbour world (no warship): slow glide over the basin towards the palm-lined
    coast road and the city."""
    T = ctx.frames
    SEA.build_harbour_world(ctx, p, corvette=False)
    c0 = p.get("cam0", (-190.0, -330.0, 16.0))
    t0 = p.get("tgt0", (40.0, 250.0, 26.0))
    c1 = p.get("cam1", (-130.0, -250.0, 14.0))
    t1 = p.get("tgt1", (60.0, 250.0, 24.0))
    SEA._cam(ctx, c0, t0, p.get("lens", 30), clip=2.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


S.V2_BUILDERS.update({
    "storm_hook": b_storm_hook,
    "ocean_calm": b_ocean_calm,
    "warm_cut": b_warm_cut,
    "globe_spin": b_globe_spin,
    "eye_section": b_eye_section,
    "coast_calm": b_coast_calm,
})

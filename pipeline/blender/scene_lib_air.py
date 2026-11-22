"""Aviation + infrastructure explainer builders (added 23 Nov 2026 for "plane crash" and "bridges in war").

Kept in a separate module so scene_lib.py / scene_lib_geo.py stay untouched. Importing this module
registers its builders into scene_lib.BUILDERS. render_episode.py imports it lazily, only when a shot's
builder is in neither scene_lib nor scene_lib_geo.

Non-graphic rules: aircraft are only ever shown flying, on approach or parked (never a crash, wreckage,
fire or people hurt). Bridges are never shown exploding: a "hit" is shown as the bridge dimming and getting
a red marker, traffic dots stopping. No weapons, flags, side colours or soldiers.

Builders (params documented in pipeline/README.md):
  plane crash:   airport_scene, flight_profile, altitude_margin, cockpit_workload, crosswind_approach,
                 tightrope, seatbelt_sign
  bridges in war: river_city, river_barrier, supply_funnel, utility_bridge, history_cards, pontoon_bridge, arteries
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Euler

import scene_lib as L
from scene_lib import hexc, kf, kf_socket, NAVY, TEAL, TEAL_DARK, RED, AMBER, WHITE, FONT_PATH, FONT_PATH_SUB
import scene_lib_geo as G  # noqa: F401  (registers geo builders too; we reuse its helpers)
from scene_lib_geo import _label, _chip, _sub, _polyline, _rooted_box, _env, _cue

# ---------------------------------------------------------------- palette
SKIES = {
    # top, mid, horizon, haze (fog colour), sun colour, sun energy
    "golden": (hexc("101a3d"), hexc("34386a"), hexc("e0915e"), hexc("a77f74"), (1.0, 0.78, 0.55), 3.2),
    "overcast": (hexc("2e3b54"), hexc("55647c"), hexc("8d9bb0"), hexc("75849a"), (0.92, 0.95, 1.0), 1.8),
    "dusk": (hexc("0a1330"), hexc("1d2a55"), hexc("6a5f86"), hexc("3d4766"), (0.85, 0.8, 1.0), 1.5),
}
LIVERY_BODY = hexc("e9edf2")
LIVERY_TAIL = hexc("1f3a68")
GLASS = hexc("14213a")
ASPHALT = hexc("2b303b")


# ---------------------------------------------------------------- generic helpers
def _empty(name, loc=(0, 0, 0), parent=None):
    o = L.link(bpy.data.objects.new(name, None))
    o.location = loc
    if parent is not None:
        o.parent = parent
    return o


def _slab(name, pts, thick, material, plane="xy", loc=(0, 0, 0), parent=None):
    """Extruded 2D polygon. plane xy: (u,v)->(x,y), thickness along z. yz: (u,v)->(y,z), thickness along x.
    xz: (u,v)->(x,z), thickness along y."""
    def P(u, v, w):
        if plane == "yz":
            return (w, u, v)
        if plane == "xz":
            return (u, w, v)
        return (u, v, w)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(P(u, v, -thick / 2.0)) for u, v in pts]
    b = [bm.verts.new(P(u, v, thick / 2.0)) for u, v in pts]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = L.link(bpy.data.objects.new(name, me))
    if material:
        o.data.materials.append(material)
    o.location = loc
    if parent is not None:
        o.parent = parent
    return o


def _sphere(name, r, loc, scale=(1, 1, 1), material=None, seg=12, rings=8, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    if material:
        o.data.materials.append(material)
    if parent is not None:
        o.parent = parent
        o.location = loc
    return o


def _copy(src, loc, rot=None, scale=None):
    o = src.copy()
    L.link(o)
    o.location = loc
    if rot is not None:
        o.rotation_euler = rot
    if scale is not None:
        o.scale = scale
    return o


def _sky(name, sky, radius=7000.0):
    """Gradient sky dome (unfogged emission): haze below the horizon, warm horizon, mid, navy top."""
    top, mid, hor, haze, _, _ = SKIES[sky]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius)
    o = bpy.context.object
    o.name = name
    m = bpy.data.materials.new(name + "_m")
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, haze
    els[1].position, els[1].color = 0.497, haze
    for pos, col in ((0.503, hor), (0.53, mid), (0.62, top)):
        e = els.new(pos)
        e.color = col
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], nt.nodes.get("Material Output").inputs["Surface"])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o


def _sky_env(ctx, sky, sun_rot, fog_density, fog_start):
    top, mid, hor, haze, sun_col, sun_e = SKIES[sky]
    L.fog(fog_density, haze, start=fog_start)
    L.setup_world(ctx.scene, mid, 0.6)
    sun = L.add_sun(sun_e, sun_rot, sun_col)
    _sky("sky", sky)
    return sun


def _sun_glow(ctx, sun, sky, dist=5500.0, size=1300.0, elev=0.03):
    d = Euler([math.radians(a) for a in sun.rotation_euler[:]] if False else sun.rotation_euler).to_matrix() @ Vector((0, 0, -1))
    src = -d
    src.z = elev
    src.normalize()
    col = SKIES[sky][2]
    L.billboard("sunglow", size, tuple(src * dist), L.glow_mat("sunglow", col, 2.2), ctx.cam)
    L.billboard("suncore", size * 0.18, tuple(src * (dist - 10)), L.glow_mat("suncore", hexc("ffe2b0"), 3.0), ctx.cam)


def _far_cam(ctx, clip=20000.0):
    ctx.cam.data.clip_end = clip
    ctx.cam.data.clip_start = 0.3


def _spin(o, T, rate=1.25, axis=1):
    v0 = Vector((0, 0, 0))
    v1 = Vector((0, 0, 0))
    v1[axis] = T * rate
    kf(o, "rotation_euler", 1, v0, "LINEAR")
    kf(o, "rotation_euler", T + 1, v1, "LINEAR")


def _arrow_pts(length, width, head_l=None, head_w=None):
    head_l = head_l or length * 0.38
    head_w = head_w or width * 2.4
    sl = length - head_l
    return [(-length / 2, -width / 2), (-length / 2 + sl, -width / 2), (-length / 2 + sl, -head_w / 2),
            (length / 2, 0), (-length / 2 + sl, head_w / 2), (-length / 2 + sl, width / 2), (-length / 2, width / 2)]


def _fade_mat(name, color, f_on, f_off=None, strength=2.5, ramp=8, start=0.0):
    """Additive material that fades from `start` to `strength` at f_on (and back to 0 at f_off)."""
    m, s = L.add_mat(name, color, strength)
    kf_socket(s, 1, start)
    kf_socket(s, max(2, f_on), start)
    kf_socket(s, f_on + ramp, strength)
    if f_off:
        kf_socket(s, f_off, strength)
        kf_socket(s, f_off + ramp, 0.0)
    return m, s


def _cam_meter(ctx, x, y0, y1, appear, levels, label="WORKLOAD"):
    """Camera-locked vertical meter at screen x (0..1), from y0 (top) to y1 (bottom). levels: [(frame, 0..1)]."""
    d = 1.98
    top, h = ctx._screen(x, y0, d)
    bot, _ = ctx._screen(x, y1, d)
    hh = top.y - bot.y
    w_frame = h * ctx.scene.render.resolution_x / ctx.scene.render.resolution_y
    bw = w_frame * 0.05
    bg = L.plane("meter_bg", bw * 1.35, hh * 1.04, (0, 0, 0), L.flat_mat("meter_bg", hexc("0d1a36")))
    bg.parent = ctx.cam
    bg.location = Vector((top.x, (top.y + bot.y) / 2, -d - 0.003))
    root = _empty("meter_root", (top.x, bot.y, -d), ctx.cam)
    fill = L.plane("meter_fill", bw, 1.0, (0, 0.5, 0), None)
    fill.parent = root
    fill.location = (0, 0.5, 0)
    # colour shifts teal -> red as it fills: two stacked fills
    fill.data.materials.append(L.flat_mat("meter_fill", RED))
    kf(root, "scale", 1, Vector((1, 0.001, 1)), "CONSTANT")
    prev = 0.001
    for f, lv in levels:
        kf(root, "scale", max(2, f), Vector((1, max(0.001, prev) * hh, 1)), "BEZIER")
        kf(root, "scale", f + 8, Vector((1, max(0.001, lv) * hh, 1)), "BEZIER")
        prev = lv
    for o in (bg, fill):
        o.visible_shadow = False
    for o in (bg,):
        ctx._pop(o, appear, None)
    ctx.text(label, x, y1 + 0.022, 0.014, hexc("dff3f6"), FONT_PATH_SUB, appear=appear, d=1.97)
    return root


# ---------------------------------------------------------------- aircraft
def make_light_plane(ctx, name, accent=TEAL, scale=1.0, spin=True, nav=True):
    """Stylised low-wing four-seat single (Cirrus-like silhouette, generic). Nose +Y, origin at the
    fuselage centre, ~8 m long, ~11.7 m span (before `scale`). Fixed gear, spinning 3-blade prop."""
    root = _empty(name)
    body = L.mat("lp_body", LIVERY_BODY, 0.35)
    acc = L.mat("lp_acc_%s" % name, accent, 0.4)
    dark = L.mat("lp_dark", hexc("2a3446"), 0.5)
    _sphere(name + "_fus", 1.0, (0, 0, 0), (0.62, 3.9, 0.72), body, 14, 8, root)
    _sphere(name + "_canopy", 1.0, (0, 0.7, 0.42), (0.5, 1.3, 0.42), L.mat("lp_glass", GLASS, 0.12, 0.4), 12, 6, root)
    wing = [(-5.85, 0.45), (-1.2, 0.95), (1.2, 0.95), (5.85, 0.45), (5.85, -0.45), (1.2, -0.75), (-1.2, -0.75), (-5.85, -0.45)]
    _slab(name + "_wing", wing, 0.16, body, "xy", (0, 0.6, -0.38), root)
    for sx in (-1, 1):
        L.box(name + "_tip%d" % sx, (0.9, 0.92, 0.18), (sx * 5.4, 0.6, -0.38), acc, parent=root).location = (sx * 5.4, 0.6, -0.38)
    _slab(name + "_stab", [(-2.0, 0.35), (2.0, 0.35), (2.0, -0.4), (-2.0, -0.4)], 0.1, body, "xy", (0, -3.65, 0.18), root)
    _slab(name + "_fin", [(-2.9, 0.0), (-4.15, 0.0), (-4.45, 1.75), (-3.75, 1.75)], 0.12, acc, "yz", (0, 0, 0.25), root)
    _slab(name + "_stripe", [(-3.2, 0.0), (2.6, 0.0), (2.6, 0.16), (-3.2, 0.16)], 1.27, acc, "yz", (0, 0, -0.05), root)
    # fixed gear
    for (x, y, z) in ((-1.35, 0.25, -1.05), (1.35, 0.25, -1.05), (0, 2.6, -1.0)):
        L.cylinder(name + "_wh", 0.27, 0.16, (x, y, z), (0, math.radians(90), 0), dark, 12, root).location = (x, y, z)
        L.box(name + "_st", (0.08, 0.08, 0.7), (x, y, z + 0.38), body, parent=root).location = (x, y, z + 0.38)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.42, radius2=0.04, depth=0.75, location=(0, 0, 0),
                                    rotation=(math.radians(-90), 0, 0))
    sp = bpy.context.object
    sp.name = name + "_spinner"
    sp.data.materials.append(acc)
    sp.parent = root
    sp.location = (0, 4.15, 0)
    prop = _empty(name + "_prop", (0, 4.2, 0), root)
    bl = L.mat("lp_blade", hexc("1b2230"), 0.6)
    for k in range(3):
        hub = _empty(name + "_bh%d" % k, (0, 0, 0), prop)
        hub.rotation_euler = (0, math.radians(120 * k), 0)
        b = L.box(name + "_blade%d" % k, (0.2, 0.05, 1.0), (0, 0, 0), bl)
        b.parent = hub
        b.location = (0, 0, 0.55)
    disc = L.cylinder(name + "_disc", 1.08, 0.01, (0, 0, 0), (math.radians(90), 0, 0),
                      L.flat_mat("lp_disc", hexc("c8d2de"), alpha=0.10), 24, root)
    disc.location = (0, 4.22, 0)
    disc.visible_shadow = False
    if spin:
        _spin(prop, ctx.frames, 1.1, axis=1)
    if nav:
        for sx, col in ((-1, hexc("ff3040")), (1, hexc("30ff7a"))):
            _sphere(name + "_nav%d" % sx, 0.09, (sx * 5.9, 0.6, -0.38), (1, 1, 1),
                    L.emissive("nav_%d" % sx, col, 8.0), 6, 4, root)
    root.scale = (scale, scale, scale)
    return root


def make_airliner(ctx, name, scale=1.0, gear=True):
    """Stylised twin-engine airliner, nose +Y, ~36 m long, ~34 m span (before `scale`).
    Returns (root, parts) with parts['flaps'] (hinge empties: rotate x>0 = flap down) and parts['gear']
    (group empties: scale 0 = stowed)."""
    root = _empty(name)
    body = L.mat("al_body", LIVERY_BODY, 0.32)
    tail = L.mat("al_tail", LIVERY_TAIL, 0.4)
    acc = L.mat("al_acc", TEAL, 0.4)
    grey = L.mat("al_grey", hexc("a7b2c0"), 0.35, 0.3)
    dark = L.mat("al_dark", hexc("1d2433"), 0.5)
    L.cylinder(name + "_fus", 1.9, 26, (0, 0, 0), (math.radians(90), 0, 0), body, 20, root).location = (0, 0, 0)
    _sphere(name + "_nose", 1.9, (0, 13.0, -0.05), (1.0, 2.0, 0.98), body, 20, 10, root)
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=1.9, radius2=0.35, depth=8, location=(0, 0, 0),
                                    rotation=(math.radians(90), 0, 0))
    tc = bpy.context.object
    tc.name = name + "_tailcone"
    tc.data.materials.append(body)
    tc.parent = root
    tc.location = (0, -17.0, 0.55)
    tc.scale = (1, 1, 1)
    # window band + cockpit
    _slab(name + "_win", [(-10.5, 0.35), (11.5, 0.35), (11.5, 0.7), (-10.5, 0.7)], 3.86, dark, "yz", (0, 0, 0), root)
    _slab(name + "_cheat", [(-12.5, -0.55), (12.0, -0.55), (12.0, -0.35), (-12.5, -0.35)], 3.84, acc, "yz", (0, 0, 0), root)
    _sphere(name + "_ckpt", 1.0, (0, 15.6, 0.75), (1.35, 1.0, 0.42), L.mat("al_glass", GLASS, 0.1, 0.4), 12, 6, root)
    flaps, gears = [], []
    for sx in (-1, 1):
        wing = [(sx * 1.5, 3.6), (sx * 17.0, -4.6), (sx * 17.0, -6.3), (sx * 1.5, -3.9)]
        if sx < 0:
            wing = list(reversed(wing))
        _slab(name + "_wing%d" % sx, wing, 0.5, body, "xy", (0, 0, -1.05), root)
        _slab(name + "_wl%d" % sx, [(-4.6, 0), (-6.3, 0), (-7.0, 2.0), (-6.2, 2.0)], 0.2, tail, "yz", (sx * 17.0, 0, -1.0), root)
        # engine
        L.cylinder(name + "_eng%d" % sx, 1.15, 4.2, (0, 0, 0), (math.radians(90), 0, 0), grey, 16, root).location = (sx * 6.3, 2.2, -2.45)
        L.cylinder(name + "_inl%d" % sx, 0.95, 0.1, (0, 0, 0), (math.radians(90), 0, 0), dark, 16, root).location = (sx * 6.3, 4.32, -2.45)
        L.box(name + "_pyl%d" % sx, (0.35, 2.6, 1.0), (0, 0, 0), grey, parent=root).location = (sx * 6.3, 1.2, -1.6)
        # flap: hinge along the inboard trailing edge
        x0, x1 = 2.2, 10.5
        y0 = 3.6 - (3.6 + 3.9) * 0 - (x0 - 1.5) / (17.0 - 1.5) * (3.9 - 6.3) * 0  # placeholder for clarity
        te = lambda x: -3.9 - (x - 1.5) / (17.0 - 1.5) * (6.3 - 3.9)  # noqa: E731  trailing-edge y at |x|
        ya, yb = te(x0), te(x1)
        hinge = _empty(name + "_flaph%d" % sx, (sx * (x0 + x1) / 2.0, (ya + yb) / 2.0, -1.1), root)
        ang = math.atan2(yb - ya, (x1 - x0)) * sx
        hinge.rotation_euler = (0, 0, ang)
        fl = L.box(name + "_flap%d" % sx, (math.hypot(x1 - x0, yb - ya), 1.3, 0.16), (0, 0, 0), grey)
        fl.parent = hinge
        fl.location = (0, -0.62, 0)
        flaps.append(hinge)
    for sx in (-1, 1):
        _slab(name + "_hs%d" % sx, [(sx * 0.6, -15.5), (sx * 6.8, -19.8), (sx * 6.8, -21.0), (sx * 0.6, -19.2)]
              if sx > 0 else [(sx * 0.6, -19.2), (sx * 6.8, -21.0), (sx * 6.8, -19.8), (sx * 0.6, -15.5)],
              0.3, body, "xy", (0, 0, 0.9), root)
    _slab(name + "_fin", [(-14.5, 1.4), (-19.6, 1.4), (-22.4, 9.6), (-19.9, 9.6)], 0.45, tail, "yz", (0, 0, 0), root)
    _slab(name + "_finstripe", [(-17.4, 5.0), (-19.0, 5.0), (-20.4, 8.2), (-19.4, 8.2)], 0.5, acc, "yz", (0, 0, 0), root)
    # gear groups (pivot at the top)
    for (x, y, n) in ((-3.2, -1.6, 2), (3.2, -1.6, 2), (0.0, 10.5, 1)):
        g = _empty(name + "_gear", (x, y, -1.55), root)
        L.box(name + "_gstrut", (0.25, 0.25, 2.1), (0, 0, 0), grey).parent = g
        bpy.context.object.location = (0, 0, -1.05)
        for k in range(n):
            w = L.cylinder(name + "_gw", 0.55, 0.4, (0, 0, 0), (0, math.radians(90), 0), dark, 14)
            w.parent = g
            w.location = ((k - (n - 1) / 2.0) * 0.6 + (0.0 if n == 1 else 0.0), 0, -2.1)
        if not gear:
            g.scale = (0.001, 0.001, 0.001)
        gears.append(g)
    for sx, col in ((-1, hexc("ff3040")), (1, hexc("30ff7a"))):
        _sphere(name + "_nav%d" % sx, 0.2, (sx * 17.1, -5.4, -1.0), (1, 1, 1), L.emissive("nav_%d" % sx, col, 8.0), 6, 4, root)
    root.scale = (scale, scale, scale)
    return root, {"flaps": flaps, "gear": gears}


# ---------------------------------------------------------------- ground / airport
def _ground(size=12000, color=hexc("1d3340"), z=0.0):
    return L.plane("ground", size, size, (0, 0, z), L.mat("ground_air", color, rough=1.0))


def _fields(rng, n=90, extent=2600, avoid=None, z=0.03, parent=None):
    cols = [hexc("22404a"), hexc("1a3140"), hexc("2a4a4a"), hexc("243650"), hexc("2b4440"), hexc("1f3747")]
    mats = [L.mat("field%d" % i, c, rough=1.0) for i, c in enumerate(cols)]
    for i in range(n):
        x, y = rng.uniform(-extent, extent), rng.uniform(-extent, extent * 1.4)
        if avoid and avoid(x, y):
            continue
        o = L.plane("field", rng.uniform(80, 260), rng.uniform(80, 260), (x, y, z + rng.uniform(0, 0.02)), mats[i % len(mats)])
        o.rotation_euler = (0, 0, rng.uniform(-0.3, 0.3))
        if parent is not None:
            o.parent = parent


def _trees(rng, n, region, avoid=None, parent=None, size=1.0):
    m = L.mat("tree", hexc("1d4a46"), rough=0.9)
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=6 * size, radius2=0, depth=16 * size, location=(0, 0, -500))
    src = bpy.context.object
    src.name = "tree_src"
    src.data.materials.append(m)
    placed = 0
    tries = 0
    while placed < n and tries < n * 6:
        tries += 1
        x, y = rng.uniform(region[0], region[1]), rng.uniform(region[2], region[3])
        if avoid and avoid(x, y):
            continue
        s = rng.uniform(0.7, 1.4)
        o = _copy(src, (x, y, 8 * size * s), scale=(s, s, s))
        if parent is not None:
            o.parent = parent
        placed += 1
    return src


def _hills(rng, n=9, dist=3600, spread=5000, col=hexc("27405a")):
    m = L.mat("hill", col, rough=1.0)
    for i in range(n):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0,
                                              location=(rng.uniform(-spread, spread), dist + rng.uniform(-400, 900), -40))
        h = bpy.context.object
        h.scale = (rng.uniform(500, 1100), rng.uniform(300, 600), rng.uniform(120, 300))
        h.data.materials.append(m)


def _runway(ctx, length=1600, width=45, lights=True, numbers="34", parent=None):
    objs = []
    rw = L.plane("runway", width, length, (0, length / 2.0, 0.05), L.mat("asphalt", ASPHALT, rough=0.85))
    objs.append(rw)
    line = L.mat("rwline", hexc("dfe5ec"), rough=0.5)
    dash = L.plane("cl", 1.0, 30, (0, 0, 0), line)
    dash.location = (0, 120, 0.08)
    objs.append(dash)
    for y in range(180, length - 60, 60):
        objs.append(_copy(dash, (0, y, 0.08)))
    st = L.plane("thr", 1.8, 40, (0, 0, 0), line)
    st.location = (-19, 28, 0.08)
    objs.append(st)
    for k in range(8):
        for sx in (-1, 1):
            x = sx * (3.5 + k * 2.2)
            if k == 0 and sx == -1:
                continue
            objs.append(_copy(st, (x, 28, 0.08)))
    for sx in (-1, 1):
        objs.append(L.plane("edge%d" % sx, 0.8, length, (sx * (width / 2 - 1.0), length / 2.0, 0.08), line))
        objs.append(L.plane("aim%d" % sx, 6, 50, (sx * 9, 330, 0.08), line))
    if numbers:
        n = L.label3d(ctx, numbers, (0, 95, 0.1), 14, hexc("dfe5ec"), rot=(0, 0, 0), face_cam=False)
        objs.append(n)
    if lights:
        em_w = L.emissive("rwy_light", hexc("fff2d6"), 10.0, 0.15)
        em_g = L.emissive("thr_light", hexc("4dff9a"), 10.0, 0.15)
        em_r = L.emissive("end_light", hexc("ff3a3a"), 10.0, 0.15)
        lt = L.box("rl", (0.9, 0.9, 0.5), (0, 0, 0), em_w)
        lt.location = (-width / 2 - 1.5, 0, 0.3)
        objs.append(lt)
        for y in range(0, length + 1, 60):
            for sx in (-1, 1):
                if y == 0 and sx == -1:
                    continue
                objs.append(_copy(lt, (sx * (width / 2 + 1.5), y, 0.3)))
        tl = L.box("tl", (0.9, 0.9, 0.5), (0, 0, 0), em_g)
        tl.location = (-width / 2, -1.5, 0.3)
        objs.append(tl)
        for k in range(1, 13):
            objs.append(_copy(tl, (-width / 2 + k * width / 12.0, -1.5, 0.3)))
        # approach light bars
        al = L.box("al", (1.0, 1.0, 0.6), (0, 0, 0), em_w)
        al.location = (0, -30, 0.8)
        objs.append(al)
        for k in range(1, 10):
            for xx in (-6, -3, 0, 3, 6):
                objs.append(_copy(al, (xx, -30 * k, 0.8)))
        for xx in (-6, -3, 3, 6):
            objs.append(_copy(al, (xx, -30, 0.8)))
        # PAPI: 2 white, 2 red
        for k in range(4):
            objs.append(L.box("papi%d" % k, (1.4, 1.0, 0.8), (-width / 2 - 14 - k * 4, 320, 0.6), em_w if k < 2 else em_r))
        for k in range(13):
            objs.append(_copy(tl, (-width / 2 + k * width / 12.0, length + 1.5, 0.3)).copy() if False else None)
        el = L.box("el", (0.9, 0.9, 0.5), (0, 0, 0), em_r)
        el.location = (-width / 2, length + 1.5, 0.3)
        for k in range(1, 13):
            objs.append(_copy(el, (-width / 2 + k * width / 12.0, length + 1.5, 0.3)))
    if parent is not None:
        for o in objs:
            if o is not None:
                o.parent = parent
    return rw


def _airport_buildings(rng, x0=170, parent=None):
    wall = L.mat("bld", hexc("5b6b82"), rough=0.7)
    roof = L.mat("bldroof", hexc("34445c"), rough=0.8)
    win = L.emissive("bldwin", hexc("ffd9a0"), 1.6, 0.3)
    objs = []
    objs.append(L.box("terminal", (40, 120, 12), (x0 + 40, 520, 6), wall))
    objs.append(L.box("term_win", (40.4, 110, 2.0), (x0 + 40, 520, 7.5), win))
    objs.append(L.box("term_roof", (44, 124, 1.2), (x0 + 40, 520, 12.4), roof))
    objs.append(L.plane("apron", 120, 300, (x0 + 5, 520, 0.06), L.mat("apron", hexc("3a4150"), rough=0.85)))
    objs.append(L.plane("taxiway", 23, 1500, (x0 - 75, 780, 0.05), L.mat("asphalt", ASPHALT, rough=0.85)))
    for y in (120, 520, 1000, 1450):
        objs.append(L.plane("conn", 110, 20, (x0 - 125 + 55 - 20, y, 0.05), L.mat("asphalt", ASPHALT, rough=0.85)))
    # tower
    objs.append(L.cylinder("tower", 4.5, 34, (x0 + 10, 760, 17), material=wall, verts=12))
    objs.append(L.cylinder("towercab", 8.0, 6, (x0 + 10, 760, 37), material=L.emissive("cab", hexc("8fe7ea"), 1.6, 0.3), verts=12))
    objs.append(L.cylinder("towerroof", 9.0, 1.2, (x0 + 10, 760, 40.6), material=roof, verts=12))
    bcn = L.emissive("beacon", hexc("ffffff"), 10.0, 0.1)
    objs.append(L.cylinder("bcn", 0.8, 1.6, (x0 + 10, 760, 42.2), material=bcn, verts=8))
    # hangars (half cylinders)
    for k, y in enumerate((180, 260, 340, 920, 1010)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=14, depth=40, location=(x0 + 30, y, 0),
                                            rotation=(0, math.radians(90), 0))
        h = bpy.context.object
        h.name = "hangar%d" % k
        h.data.materials.append(L.mat("hangar", hexc("6f7f95") if k % 2 else hexc("4d5d75"), rough=0.6, metal=0.2))
        objs.append(h)
    if parent is not None:
        for o in objs:
            o.parent = parent


def _airport_world(ctx, sky, sun_rot, rng, trees=180, buildings=True):
    sun = _sky_env(ctx, sky, sun_rot, 0.00055, 250)
    L.add_sun(1.1, (58, 0, 15), (0.8, 0.88, 1.0))  # cool fill from the camera side (main sun is a backlight)
    _ground()
    runway_avoid = lambda x, y: (abs(x) < 70 and -420 < y < 1700) or (110 < x < 300 and 0 < y < 1600)  # noqa: E731
    _fields(rng, 110, 3200, runway_avoid)
    _runway(ctx)
    if buildings:
        _airport_buildings(rng)
    _trees(rng, trees, (-1800, 1800, -1600, 3200), runway_avoid)
    _hills(rng)
    return sun


# ================================================================ BUILDERS: plane crash
def b_airport_scene(ctx, p):
    """Small airport at golden hour / overcast: runway with lights, tower, hangars, fields, trees, sun glow.
    mode hook: a light plane on a normal approach (never touching down), chase camera; plane label + chips.
    mode outro: wide crane-up as a light plane flies away towards the runway lights."""
    T = ctx.frames
    sky = p.get("sky", "golden")
    rng = random.Random(24)
    mode = p.get("mode", "hook")
    sun_rot = (84.0, 0.0, 192.0)
    sun = _airport_world(ctx, sky, sun_rot, rng)
    if mode == "hook":
        track = _empty("track")
        a, b = Vector((-24, -980, 56)), Vector((-4, -360, 22))
        kf(track, "location", 1, a, "LINEAR")
        kf(track, "location", T, b, "LINEAR")
        plane_ = make_light_plane(ctx, "lp", TEAL)
        plane_.parent = track
        for f in range(1, T + 1, 6):
            tt = (f - 1) / ctx.fps
            kf(plane_, "rotation_euler", f, Vector((math.radians(-1.5 + 0.8 * math.sin(tt * 1.3)),
                                                     math.radians(2.5 * math.sin(tt * 0.9)), math.radians(-1.8))), "BEZIER")
            kf(plane_, "location", f, Vector((0, 0, 0.35 * math.sin(tt * 1.7))), "BEZIER")
        cam = ctx.camera((-3, -34, 1.5), target=(1, 90, -5), lens=32)
        cam.parent = track
        ctx.cam_target.parent = track
        L.animate_cam(ctx, [(1, (-3.5, -37, 1.6)), (T, (-2.5, -30, 1.3))])
        L.animate_target(ctx, [(1, (1, 90, -5)), (T, (0.5, 90, -5))])
        _far_cam(ctx)
        _sun_glow(ctx, sun, sky)
        if p.get("plane_label"):
            lb = _label(ctx, p["plane_label"], (0, 0, 0), 1.1, WHITE, appear=_cue(ctx, p, "label_cue", "cirrus", 0.3))
            lb.parent = track
            lb.location = (0, 0, 2.6)
            f_hide = ctx.word_time((p.get("chip_cues") or ["ntsb"])[0], 0.7)
            kf(lb, "scale", f_hide - 4, lb.scale.copy(), "BEZIER")
            kf(lb, "scale", f_hide, Vector((0.001, 0.001, 0.001)), "CONSTANT")
    else:
        track = _empty("track")
        kf(track, "location", 1, Vector((-6, -470, 30)), "LINEAR")
        kf(track, "location", T, Vector((-1, -300, 17)), "LINEAR")
        plane_ = make_light_plane(ctx, "lp", TEAL)
        plane_.parent = track
        cam = ctx.camera((-30, -560, 14), target=(0, -200, 14), lens=32)
        L.animate_cam(ctx, [(1, (-28, -560, 13)), (T, (-70, -660, 85))])
        L.animate_target(ctx, [(1, (-3, -300, 18)), (T, (0, 150, 0))])
        _far_cam(ctx)
        _sun_glow(ctx, sun, sky)
    if p.get("card"):
        if mode == "outro":
            n_lines = p["card"].count("\n") + 1
            ctx.card(p["card"], None, y_frac=0.15, size=0.048, appear=ctx.f(0.3))
            if p.get("subcard"):
                _sub(ctx, p["subcard"], 0.15 + 0.045 * n_lines + 0.05, _cue(ctx, p, "sub_cue", "tell", 0.4))
        else:
            ctx.card(p["card"], p.get("subcard"), y_frac=0.14, size=0.046)
    cues = p.get("chip_cues", [])
    for i, ch in enumerate(p.get("chips", [])):
        f = ctx.word_time(cues[i], 0.7 + 0.12 * i) if i < len(cues) else ctx.f(1 + i)
        _chip(ctx, ch, 0.315 + 0.06 * i, f, panel=hexc("9a1020") if i == 0 else NAVY, size=0.024)


def _profile_pts(n=140, W=14.0, H=6.0):
    pts = []
    for i in range(n + 1):
        x = W * i / float(n)
        if x < 0.5:
            z = 0.0
        elif x < 2.4:
            z = H * L.smooth((x - 0.5) / 1.9) ** 0.8
        elif x < 11.4:
            z = H
        elif x < 13.5:
            z = H * (1.0 - L.smooth((x - 11.4) / 2.1))
        else:
            z = 0.0
        pts.append((x, z))
    return pts


def b_flight_profile(ctx, p):
    """Altitude-vs-time profile of a typical flight drawn as a glowing line over a timeline; a small
    airliner flies along it. mode intro: line draws with the plane, TAKEOFF / LANDING labels pop on their
    words. mode zones: the line is already drawn; takeoff/climb and approach/landing zones light teal on
    zone_cue (a small slice of the time axis), then turn red on red_cue with a chip."""
    _env(ctx, NAVY, 2.0, (50, 0, 30), fog_density=0.0, fog_start=40)
    T = ctx.frames
    mode = p.get("mode", "intro")
    W, H = 14.0, 6.0
    _empty("origin")
    ctx.camera((6.2, -37, 3.2), target=(7, 0, 1.6), lens=30)
    L.animate_cam(ctx, [(1, (5.6, -38, 2.6)), (T, (8.0, -35, 3.6))])
    # floor grid + axes
    gm = L.emissive("pgrid", TEAL_DARK, 0.5)
    for k in range(0, 8):
        _polyline("hz%d" % k, [(-0.4, 0.6, k * 1.0), (W + 0.4, 0.6, k * 1.0)], 0.012, gm)
    ax = L.emissive("paxis", hexc("c9d3df"), 1.4)
    _polyline("xaxis", [(-0.4, 0, 0), (W + 0.6, 0, 0)], 0.05, ax)
    _polyline("zaxis", [(-0.4, 0, 0), (-0.4, 0, 7.4)], 0.05, ax)
    L.label3d(ctx, "ALTITUDE", (1.3, 0, 7.75), 0.42, hexc("9fb0c4"), rot=(90, 0, 0), face_cam=False)
    pts2 = _profile_pts(160, W, H)
    pts = [(x, -0.05, z + 0.08) for x, z in pts2]
    line = _polyline("profile", pts, 0.085, L.emissive("profile", WHITE, 3.0))
    plane_, _ = make_airliner(ctx, "mini", 0.05, gear=False)

    def pos_at(u):
        x = max(0.0, min(W, u * W))
        i = min(len(pts2) - 2, int(x / W * (len(pts2) - 1)))
        (xa, za), (xb, zb) = pts2[i], pts2[i + 1]
        t = (x - xa) / max(1e-6, (xb - xa))
        z = za + (zb - za) * t
        return Vector((x, -0.05, z + 0.55)), math.atan2(zb - za, xb - xa)

    if mode == "intro":
        f0, f1 = ctx.f(0.2), max(ctx.f(0.4), T - 12)
        kf(line.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
        kf(line.data, "bevel_factor_end", f0, 0.0, "LINEAR")
        kf(line.data, "bevel_factor_end", f1, 1.0, "LINEAR")
        for f in range(1, T + 1, 2):
            u = max(0.0, min(1.0, (f - f0) / float(max(1, f1 - f0))))
            ps, ang = pos_at(u)
            kf(plane_, "location", f, ps)
            kf(plane_, "rotation_euler", f, Vector((ang * 0.8, 0, math.radians(-90))))
        for txt, x, cue, frac in (("TAKEOFF", 1.0, "takeoff", 0.45), ("LANDING", 13.0, "landing", 0.6)):
            _label(ctx, txt, (x, -0.3, -1.0), 0.52, AMBER, appear=ctx.word_time(cue, frac))
        _label(ctx, "CRUISE", (7.0, -0.3, -1.0), 0.45, hexc("9fb0c4"), appear=ctx.word_time("middle", 0.8))
    else:
        f_z = _cue(ctx, p, "zone_cue", "takeoff", 0.25)
        f_r = _cue(ctx, p, "red_cue", "majority", 0.7)
        for f in range(1, T + 1, 2):
            u = 0.3 + 0.35 * (f - 1) / float(T)
            ps, ang = pos_at(u)
            kf(plane_, "location", f, ps)
            kf(plane_, "rotation_euler", f, Vector((ang * 0.8, 0, math.radians(-90))))
        for k, (xa, xb, lab) in enumerate(((0.0, 1.45, "TAKEOFF\n& CLIMB"), (12.55, W, "APPROACH\n& LANDING"))):
            cx, w = (xa + xb) / 2.0, xb - xa
            mt, _ = _fade_mat("zone_t%d" % k, TEAL, f_z + 3 * k, f_r, 0.35)
            L.box("zone_t%d" % k, (w, 0.3, 3.6), (cx, 0.35, 1.8), mt).visible_shadow = False
            mr, sr = _fade_mat("zone_r%d" % k, RED, f_r + 2 * k, None, 0.55)
            for f in range(f_r + 12, T + 1, 18):
                kf_socket(sr, f, 0.55)
                kf_socket(sr, f + 9, 0.85)
            L.box("zone_r%d" % k, (w, 0.32, 3.6), (cx, 0.33, 1.8), mr).visible_shadow = False
            _label(ctx, lab, (cx + (0.3 if k == 0 else -0.3), -0.3, -1.2), 0.5, AMBER, appear=f_z + 3 * k)
        # time bar under the axis: grey cruise, teal slices
        _label(ctx, "CRUISE", (7.0, -0.3, -1.0), 0.45, hexc("9fb0c4"), appear=f_z + 8)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.048, appear=_cue(ctx, p, "card_cue", "why", 0.05))
    if p.get("chip"):
        _chip(ctx, p["chip"], 0.212, _cue(ctx, p, "red_cue", "majority", 0.7) + 4, panel=hexc("9a1020"), size=0.024)


def b_altitude_margin(ctx, p):
    """Two light planes side by side: one high (tall teal bar = room to sort out a problem), one just
    above a runway (short red bar = little room). Bars grow on their cue words."""
    T = ctx.frames
    sky = p.get("sky", "overcast")
    _sky_env(ctx, sky, (70, 0, 150), 0.0012, 60)
    rng = random.Random(5)
    _ground(4000, hexc("1d3340"))
    _fields(rng, 40, 700)
    rw = L.plane("rw", 260, 16, (40, 0, 0.05), L.mat("asphalt", ASPHALT, rough=0.85))
    for k in range(-5, 8):
        L.plane("rwd", 6, 0.5, (k * 14 + 30, 0, 0.08), L.mat("rwline", hexc("dfe5ec"), 0.5))
    _trees(rng, 60, (-200, 260, 30, 600), None, size=0.18)
    cam = ctx.camera((0.5, -30, 4.5), target=(0.5, 0, 3.7), lens=34)
    L.animate_cam(ctx, [(1, (-0.5, -31, 4.2)), (T, (1.2, -29, 4.8))])
    _far_cam(ctx)
    hi_z, lo_z = 8.4, 1.6
    f_hi = _cue(ctx, p, "high_cue", "cruise", 0.35)
    f_lo = _cue(ctx, p, "low_cue", "near", 0.7)
    for k, (x, z, col, f, lab) in enumerate(((-2.7, hi_z, TEAL, f_hi, p.get("high_label", "ROOM TO\nRECOVER")),
                                               (2.7, lo_z, RED, f_lo, p.get("low_label", "LITTLE\nROOM")))):
        tr = _empty("trk%d" % k, (x, 0, z))
        pl = make_light_plane(ctx, "lp%d" % k, TEAL if k == 0 else hexc("4f8dff"), 0.42)
        pl.parent = tr
        pl.rotation_euler = (0, 0, math.radians(-90))
        for f2 in range(1, T + 1, 6):
            tt = (f2 - 1) / ctx.fps
            kf(pl, "location", f2, Vector((0, 0, 0.12 * math.sin(tt * 1.6 + k))), "BEZIER")
        root, bar = _rooted_box("bar%d" % k, (0.9, 0.5, 1.0), (x, 0.0, 0.0), L.emissive("bar%d" % k, col, 1.4))
        bar.visible_shadow = False
        kf(root, "scale", 1, Vector((1, 1, 0.001)), "CONSTANT")
        kf(root, "scale", f, Vector((1, 1, 0.001)), "BEZIER")
        kf(root, "scale", f + 20, Vector((1, 1, z - 0.75)), "BEZIER")
        lpos = (0.2, -1.2, 4.6) if k == 0 else (2.7, -1.2, 3.4)
        _label(ctx, lab, lpos, 0.5, hexc("7ff0f2") if k == 0 else hexc("ff8a92"), appear=f + 10)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.046, appear=_cue(ctx, p, "card_cue", "one", 0.2))


def b_cockpit_workload(ctx, p):
    """An airliner on approach (3/4 front view, ground scrolling far below). On each cue word: SPEED
    (speed streaks slow), FLAPS (flaps lower), LANDING GEAR (gear drops), RADIO (radio rings from the
    cockpit); chips stack up and a WORKLOAD meter fills."""
    T = ctx.frames
    sky = p.get("sky", "overcast")
    _sky_env(ctx, sky, (60, 0, 140), 0.0005, 200)
    rng = random.Random(9)
    world = _empty("world", (0, 0, -260))
    g = _ground(9000, hexc("1d3340"))
    g.parent = world
    _fields(rng, 90, 2600, None, parent=world)
    _trees(rng, 80, (-1500, 1500, -1500, 2500), None, parent=world)
    kf(world, "location", 1, Vector((0, 300, -260)), "LINEAR")
    kf(world, "location", T, Vector((0, 300 - 70 * T / ctx.fps, -260 + 3.5 * T / ctx.fps)), "LINEAR")
    plane_, parts = make_airliner(ctx, "al", 1.0, gear=False)
    items = p.get("items", ["SPEED", "FLAPS", "LANDING GEAR", "RADIO"])
    cues = p.get("cues", ["speed", "flaps", "gear", "radio"])
    fr = [ctx.word_time(cues[i], 0.3 + 0.12 * i) for i in range(len(items))]
    for f in range(1, T + 1, 4):
        tt = (f - 1) / ctx.fps
        kf(plane_, "rotation_euler", f, Vector((math.radians(1.5 + 0.6 * math.sin(tt * 1.1)),
                                                 math.radians(1.5 * math.sin(tt * 0.8)), 0)), "BEZIER")
        kf(plane_, "location", f, Vector((0, 0, 0.4 * math.sin(tt * 1.4))), "BEZIER")
    # flaps (cue 1) and gear (cue 2)
    for h in parts["flaps"]:
        kf(h, "rotation_euler", 1, Vector((0, 0, h.rotation_euler.z)), "CONSTANT")
        kf(h, "rotation_euler", fr[1], Vector((0, 0, h.rotation_euler.z)), "BEZIER")
        kf(h, "rotation_euler", fr[1] + 24, Vector((math.radians(32), 0, h.rotation_euler.z)), "BEZIER")
    for gg in parts["gear"]:
        kf(gg, "scale", 1, Vector((0.001, 0.001, 0.001)), "CONSTANT")
        kf(gg, "rotation_euler", 1, Vector((math.radians(80), 0, 0)), "CONSTANT")
        kf(gg, "scale", fr[2], Vector((0.001, 0.001, 0.001)), "BEZIER")
        kf(gg, "rotation_euler", fr[2], Vector((math.radians(80), 0, 0)), "BEZIER")
        kf(gg, "scale", fr[2] + 4, Vector((1, 1, 1)), "BEZIER")
        kf(gg, "rotation_euler", fr[2] + 22, Vector((0, 0, 0)), "BEZIER")
    # speed streaks (cue 0): white lines rushing past, fading in at the cue then slowing
    for k in range(34):
        x = rng.uniform(-22, 22)
        z = rng.uniform(-8, 10)
        if abs(x) < 4 and abs(z) < 4:
            x += 8 * (1 if x >= 0 else -1)
        m, s = _fade_mat("streak%d" % k, hexc("dff3f6"), fr[0], None, 1.6, 6)
        st = L.box("streak%d" % k, (0.1, 5.0, 0.1), (x, 0, z), m)
        st.visible_shadow = False
        y = 60 + rng.uniform(0, 80)
        speed = 4.0
        for f in range(1, T + 1, 2):
            sp_ = speed if f < fr[0] + 20 else speed * 0.7
            y -= sp_ * 2
            if y < -60:
                y += 140
            kf(st, "location", f, Vector((x, y, z)), "CONSTANT")
    cam = ctx.camera((36, 58, 9), target=(0, 3, -1.5), lens=30)
    L.animate_cam(ctx, [(1, (39, 61, 10)), (T, (31, 51, 7.5))])
    L.animate_target(ctx, [(1, (0, 2, -2.5)), (T, (0, 3, -2.0))])
    _far_cam(ctx)
    # radio rings from the cockpit (cue 3)
    for k in range(4):
        L.wave_ring("radio%d" % k, (0, 15.5, 2.6), TEAL, fr[3] + 10 * k, fr[3] + 10 * k + 30, 9.0,
                    rot=(0, 0, 0), strength=4.0, minor=0.06)
    # landing lights glow from the flaps cue
    for sx in (-1, 1):
        gl = L.billboard("ll%d" % sx, 3.5, (sx * 3.0, 4.2, -1.3), L.glow_mat("ll", hexc("fff4d8"), 3.0), cam)
        L.vis(gl, fr[2] + 10)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.046, appear=_cue(ctx, p, "card_cue", "two", 0.05))
    for i, it in enumerate(items):
        ctx.text(it, 0.42, 0.225 + 0.052 * i, 0.022, WHITE, FONT_PATH, appear=fr[i],
                 panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), max_w_frac=0.6)
    seg_cols = [TEAL, hexc("f2c230"), hexc("f08a24"), RED]
    for i in range(len(items)):
        ctx.text(" ", 0.86, 0.385 - 0.042 * i, 0.03, WHITE, FONT_PATH, appear=fr[i],
                 panel=seg_cols[min(i, 3)], panel_pad=(0.035, 0.012))
    ctx.text("WORKLOAD", 0.86, 0.425, 0.013, hexc("dff3f6"), FONT_PATH_SUB, appear=fr[0], d=1.97)


def b_crosswind_approach(ctx, p):
    """Airliner on final approach seen from behind, crabbed into a crosswind. Red wind arrows stream
    across on chip cue 1; a downward wind-shear column + small dip on cue 2; another aircraft and the hills
    get warning rings on cue 3."""
    T = ctx.frames
    sky = p.get("sky", "overcast")
    rng = random.Random(31)
    sun = _airport_world(ctx, sky, (80, 0, 200), rng, trees=150)
    cues = p.get("chip_cues", ["gusty", "sudden", "traffic"])
    fw = ctx.word_time(cues[0], 0.35)
    fs = ctx.word_time(cues[1], 0.5)
    ft = ctx.word_time(cues[2], 0.75)
    track = _empty("track")
    kf(track, "location", 1, Vector((0, -1250, 68)), "LINEAR")
    kf(track, "location", T, Vector((0, -1250 + 68 * T / ctx.fps, 68 - 3.6 * T / ctx.fps)), "LINEAR")
    plane_, parts = make_airliner(ctx, "al", 1.0, gear=True)
    plane_.parent = track
    for h in parts["flaps"]:
        h.rotation_euler.x = math.radians(30)
    for f in range(1, T + 1, 3):
        tt = (f - 1) / ctx.fps
        gust = 1.0 if f > fw else 0.25
        yaw = math.radians(4 + 6 * L.smooth((f - fw) / 30.0))
        roll = math.radians(gust * 4.0 * math.sin(tt * 2.3) + gust * 2 * math.sin(tt * 5.1))
        dip = -4.0 * math.exp(-((f - fs - 18) / 14.0) ** 2) if f > fs - 20 else 0.0
        kf(plane_, "rotation_euler", f, Vector((math.radians(2.0), roll, yaw)), "BEZIER")
        kf(plane_, "location", f, Vector((gust * 0.8 * math.sin(tt * 1.7), 0, dip + 0.6 * math.sin(tt * 2.0) * gust)), "BEZIER")
    cam = ctx.camera((26, -92, 13), target=(-4, 40, -6), lens=30)
    cam.parent = track
    ctx.cam_target.parent = track
    L.animate_cam(ctx, [(1, (28, -96, 14)), (T, (22, -86, 10))])
    _far_cam(ctx)
    _sun_glow(ctx, sun, sky)
    # wind arrows: flat red arrows in vertical planes facing the camera, streaming +X
    for k in range(22):
        m, s = _fade_mat("wind%d" % k, RED, fw + (k % 6), None, 2.6, 6)
        ar = _slab("wind%d" % k, _arrow_pts(7.0, 0.7), 0.2, m, "xz")
        ar.visible_shadow = False
        ar.parent = track
        y = rng.uniform(-10, 60)
        z = rng.uniform(-16, 14)
        x = rng.uniform(-60, 60)
        sp_ = rng.uniform(1.2, 1.9)
        for f in range(1, T + 1, 2):
            x += sp_ * 2
            if x > 60:
                x -= 120
            kf(ar, "location", f, Vector((x, y, z)), "CONSTANT")
    # wind shear: downward arrows ahead of the aircraft
    for k in range(8):
        m, s = _fade_mat("shear%d" % k, hexc("ff5a3d"), fs + 2 * k, None, 1.5, 6)
        ar = _slab("shear%d" % k, _arrow_pts(6.0, 0.8), 0.2, m, "xz")
        ar.rotation_euler = (0, math.radians(90), 0)
        ar.visible_shadow = False
        ar.parent = track
        x = -12 + 3.4 * k
        z = 10 + rng.uniform(0, 8)
        for f in range(1, T + 1, 2):
            z -= 1.4
            if z < -22:
                z += 34
            kf(ar, "location", f, Vector((x, 34 + (k % 2) * 6, z)), "CONSTANT")
    # traffic: another light aircraft crossing ahead-left, with a warning ring
    other = make_light_plane(ctx, "lp_tr", hexc("4f8dff"), 1.0)
    other.rotation_euler = (0, 0, math.radians(-90))
    oy = -1250 + 68 * ft / ctx.fps + 330
    oz = 68 - 3.6 * ft / ctx.fps + 26
    kf(other, "location", 1, Vector((-130, oy, oz)), "LINEAR")
    kf(other, "location", T, Vector((-130 + 30 * (T - 1) / ctx.fps, oy, oz)), "LINEAR")
    L.vis(other, max(2, ft - 2))
    rg = _empty("ring_tr")
    rg.parent = other
    L.pulse_rings("tr", (0, 0, 0), RED, ft, T + 40, period=26, r1=10.0, rot=(90, 0, 0), count=2, strength=4.0, minor=0.08)
    for o in [o for o in bpy.data.objects if o.name.startswith("tr_")]:
        o.parent = other
        o.location = (0, 0, 0)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.044, appear=_cue(ctx, p, "card_cue", "three", 0.05))
    for i, ch in enumerate(p.get("chips", [])):
        f = [fw, fs, ft][i] if i < 3 else ctx.f(1 + i)
        _chip(ctx, ch, 0.222 + 0.062 * i, f + 2, panel=hexc("9a1020") if i < 2 else NAVY, size=0.022)


def _walker(name, body_m, pole_m):
    """Simple mannequin with a long balance pole. Origin at the feet; faces +X (walks along +X)."""
    root = _empty(name)
    sway = _empty(name + "_sway", (0, 0, 0), root)
    L.box(name + "_legs", (0.32, 0.42, 0.95), (0, 0, 0), body_m, bevel=0.06).parent = sway
    bpy.context.object.location = (0, 0, 0.48)
    L.box(name + "_torso", (0.34, 0.55, 0.75), (0, 0, 0), body_m, bevel=0.1).parent = sway
    bpy.context.object.location = (0, 0, 1.33)
    hd = _sphere(name + "_head", 0.2, (0, 0, 1.93), (1, 1, 1), body_m, 14, 8, sway)
    pole = L.cylinder(name + "_pole", 0.04, 5.2, (0, 0, 0), (math.radians(90), 0, 0), pole_m, 8)
    pole.parent = sway
    pole.location = (0.25, 0, 1.25)
    for sy in (-1, 1):
        a = L.box(name + "_arm", (0.12, 0.12, 0.55), (0, 0, 0), body_m, bevel=0.03)
        a.parent = sway
        a.location = (0.16, sy * 0.33, 1.42)
        a.rotation_euler = (math.radians(-25 * sy), math.radians(-60), 0)
        for e in (-1, 1):
            if e != 1:
                continue
            ball = _sphere(name + "_pend%d" % sy, 0.09, (0.25, sy * 2.6, 1.25), (1, 1, 1), pole_m, 8, 6, sway)
    return root, sway, pole


def b_tightrope(ctx, p):
    """A walker with a balance pole crosses a rope between two towers. The rope middle turns teal on
    middle_cue; both ends glow red on on_cue / off_cue (the walker wobbles most near the ends);
    TAKEOFF / LANDING labels pop under the ends on map_cue."""
    T = ctx.frames
    _env(ctx, hexc("0d1838"), 2.6, (55, 0, 35), fog_density=0.01, fog_start=20)
    rng = random.Random(3)
    _empty("o")
    L.plane("floor", 200, 200, (0, 0, -0.02), L.mat("tfloor", hexc("1b2f5a"), rough=0.9))
    gm = L.emissive("tgrid", TEAL_DARK, 0.5)
    for i in range(-30, 31, 3):
        _polyline("tgx%d" % i, [(i, -30, 0.01), (i, 30, 0.01)], 0.02, gm)
        _polyline("tgy%d" % i, [(-30, i, 0.01), (30, i, 0.01)], 0.02, gm)
    X0, X1, Z = -8.0, 8.0, 6.0
    tower_m = L.mat("tower", hexc("3a4f7a"), rough=0.6)
    for x in (X0, X1):
        sx = -1 if x < 0 else 1
        L.box("towr", (1.6, 1.6, Z), (x + sx * 0.8, 0, Z / 2.0), tower_m, bevel=0.05)
        L.box("towtop", (2.2, 2.2, 0.2), (x + sx * 0.8, 0, Z + 0.1), L.mat("towtop", hexc("5c6f86"), 0.5), bevel=0.03)
    sag = lambda x: Z + 0.12 - 0.35 * (1 - (x / X1) ** 2)  # noqa: E731
    rope_pts = [(X0 + (X1 - X0) * i / 60.0, 0, sag(X0 + (X1 - X0) * i / 60.0)) for i in range(61)]
    _polyline("rope", rope_pts, 0.045, L.mat("rope", hexc("d8dee6"), 0.5))
    f_mid = _cue(ctx, p, "middle_cue", "middle", 0.2)
    f_on = _cue(ctx, p, "on_cue", "stepping", 0.45)
    f_off = _cue(ctx, p, "off_cue", "off", 0.6)
    f_map = _cue(ctx, p, "map_cue", "flying", 0.85)
    seg = lambda a, b: [(x, -0.02, sag(x) + 0.01) for x in [a + (b - a) * i / 20.0 for i in range(21)]]  # noqa: E731
    mm, _ = _fade_mat("rope_mid", TEAL, f_mid, None, 3.0, 8)
    _polyline("rope_mid", seg(-4.0, 4.0), 0.07, mm)
    m1, _ = _fade_mat("rope_on", RED, f_on, None, 3.5, 6)
    _polyline("rope_on", seg(X0, -4.2), 0.07, m1)
    m2, _ = _fade_mat("rope_off", RED, f_off, None, 3.5, 6)
    _polyline("rope_off", seg(4.2, X1), 0.07, m2)
    body_m = L.mat("walker", hexc("e6ebf1"), 0.55)
    pole_m = L.mat("wpole", hexc("ffa21a"), 0.4)
    man, sway, pole = _walker("walker", body_m, pole_m)
    man.scale = (1.7, 1.7, 1.7)
    k_mid, k_off = f_mid + 15, max(f_mid + 40, f_off + 10)

    def walk_x(f):
        if f <= k_mid:   # step on from the left tower, reach the middle just after "middle"
            return X0 - 0.2 + (0.2 - X0) * (f - 1) / float(max(1, k_mid - 1))
        if f <= k_off:   # middle -> right end around "off"
            return X1 * (f - k_mid) / float(max(1, k_off - k_mid))
        return X1 + 0.6 * min(1.0, (f - k_off) / 20.0)
    for f in range(1, T + 1, 2):
        x = walk_x(f)
        z = sag(max(X0, min(X1, x))) + 0.03 if X0 <= x <= X1 else Z + 0.2
        tt = (f - 1) / ctx.fps
        end = math.exp(-((x - X0) / 2.0) ** 2) + math.exp(-((x - X1) / 2.0) ** 2)
        amp = math.radians(3 + 17 * end)
        kf(man, "location", f, Vector((x, 0, z)), "BEZIER")
        kf(sway, "rotation_euler", f, Vector((amp * math.sin(tt * 2 * math.pi / 0.9), 0, 0)), "BEZIER")
    ctx.camera((-24, -12, 7.5), target=(0.5, 0, 5.4), lens=24)
    L.animate_cam(ctx, [(1, (-24.5, -11.5, 7.5)), (T, (-22.0, -13.5, 8.0))])
    L.animate_target(ctx, [(1, (-1.0, 0, 5.4)), (T, (1.0, 0, 5.6))])
    labels = p.get("labels", ["EASY MIDDLE", "STEPPING ON & OFF = HARDEST", "= TAKEOFF & LANDING"])
    _chip(ctx, labels[0], 0.222, f_mid, panel=hexc("0d6f7a"), size=0.024)
    _chip(ctx, labels[1], 0.282, f_on, panel=hexc("9a1020"), size=0.024)
    _chip(ctx, labels[2], 0.342, f_map, panel=NAVY, size=0.024)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=ctx.f(0.2))


def b_seatbelt_sign(ctx, p):
    """Cabin aisle view: rows of seats, bins, windows; the FASTEN SEATBELT sign lights up on sign_cue
    (glow + ring); chips stack on their cues; a big card (e.g. '+3 MIN / -8 MIN') replaces them on big_cue."""
    T = ctx.frames
    _env(ctx, hexc("1a2440"), 1.2, (60, 0, 20), fog_density=0.007, fog_start=18)
    floor_m = L.mat("cfloor", hexc("2a3550"), 0.9)
    seat_m = L.mat("seat", hexc("1f3a68"), 0.7)
    seat2 = L.mat("seat2", hexc("27477a"), 0.7)
    head_m = L.mat("headrest", hexc("dfe5ec"), 0.7)
    wall_m = L.mat("cwall", hexc("c9d0da"), 0.6)
    bin_m = L.mat("bin", hexc("e3e8ee"), 0.5)
    L.plane("cfloor", 5.0, 40, (0, 12, 0), floor_m)
    L.plane("aisle", 0.55, 40, (0, 12, 0.005), L.mat("carpet", hexc("16408a"), 0.95))
    for sx in (-1, 1):
        L.box("wall%d" % sx, (0.15, 40, 2.6), (sx * 2.35, 12, 1.3), wall_m)
        L.box("bin%d" % sx, (0.95, 40, 0.55), (sx * 1.85, 12, 2.15), bin_m, bevel=0.05)
        L.box("binlip%d" % sx, (0.06, 40, 0.06), (sx * 1.37, 12, 1.89), L.mat("binlip", hexc("8a96a8"), 0.5))
    L.plane("ceil", 2.9, 40, (0, 12, 2.5), L.mat("ceil", hexc("eef1f4"), 0.6), rot=(math.radians(180), 0, 0))
    for sx in (-1, 1):
        L.box("cove%d" % sx, (0.06, 40, 0.05), (sx * 1.36, 12, 2.42), L.emissive("cove", hexc("ffe6c0"), 1.2, 0.3))
    for k in range(7):
        pl = bpy.data.lights.new("cabin%d" % k, "POINT")
        pl.energy = 35
        pl.color = (1.0, 0.92, 0.82)
        pl.shadow_soft_size = 0.8
        L.link(bpy.data.objects.new("cabin%d" % k, pl)).location = (0, k * 2.4, 2.0)
    win_m = L.emissive("cwin", hexc("bfe3ff"), 2.2, 0.4)
    for r in range(18):
        y = r * 0.86
        for sx in (-1, 1):
            base = L.box("seat_%d_%d" % (r, sx), (1.5, 0.5, 0.42), (sx * 1.3, y, 0.42), seat_m if r % 2 else seat2, bevel=0.04)
            back = L.box("back_%d_%d" % (r, sx), (1.5, 0.14, 0.82), (sx * 1.3, y - 0.24, 0.95), seat_m if r % 2 else seat2, bevel=0.04)
            for k in range(3):
                L.box("hr", (0.36, 0.16, 0.16), (sx * 1.3 + (k - 1) * 0.5, y - 0.24, 1.42), head_m, bevel=0.03)
            w = L.box("cw", (0.05, 0.28, 0.38), (sx * 2.27, y + 0.1, 1.45), win_m, bevel=0.06)
    # sign panel hanging from the ceiling
    f_s = _cue(ctx, p, "sign_cue", "seat", 0.25)
    sign = _empty("sign", (0, 7.0, 2.22))
    L.box("signbox", (1.25, 0.12, 0.34), (0, 0, 0), L.mat("signbox", hexc("2a3446"), 0.5), bevel=0.03).parent = sign
    face_m, face_s = L.add_mat("signface", hexc("ffc04a"), 0.05)
    kf_socket(face_s, 1, 0.05)
    kf_socket(face_s, f_s, 0.05)
    kf_socket(face_s, f_s + 2, 4.0)
    fc = L.plane("signface", 1.12, 0.26, (0, 0, 0), face_m, rot=(math.radians(90), 0, 0))
    fc.parent = sign
    fc.location = (0, -0.065, 0)
    txt = L.label3d(ctx, "FASTEN SEATBELT", (0, 0, 0), 0.11, hexc("1a1a1a"), rot=(90, 0, 0), face_cam=False)
    txt.parent = sign
    txt.location = (0, -0.075, 0)
    # scale the whole cabin up so camera-locked cards (at 2 m from the lens) sit in front of the ceiling
    S = 3.0
    croot = _empty("cabin_root")
    for o in list(bpy.data.objects):
        if o is not croot and o.parent is None:
            o.parent = croot
    croot.scale = (S, S, S)
    for lt in bpy.data.lights:
        if lt.type == "POINT":
            lt.energy *= S * S
    cam = ctx.camera((0, -2.2 * S, 1.55 * S), target=(0, 8 * S, 2.0 * S), lens=22)
    L.animate_cam(ctx, [(1, (0.1 * S, -2.4 * S, 1.5 * S)), (T, (0, 2.6 * S, 1.65 * S))])
    L.animate_target(ctx, [(1, (0, 8 * S, 1.95 * S)), (T, (0, 8 * S, 2.12 * S))])
    gl = L.billboard("signglow", 2.2 * S, (0, 6.85 * S, 2.22 * S), L.glow_mat("signglow", hexc("ffc04a"), 1.2), cam)
    L.vis(gl, f_s + 1)
    L.wave_ring("ding", (0, 6.8 * S, 2.22 * S), hexc("ffc04a"), f_s + 2, f_s + 26, 1.4 * S, rot=(90, 0, 0), strength=4.0, minor=0.012)
    f_big = _cue(ctx, p, "big_cue", "critical", 0.7)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.046, appear=ctx.f(0.2), disappear=f_big - 1)
    cues = p.get("chip_cues", [])
    for i, ch in enumerate(p.get("chips", [])):
        f = ctx.word_time(cues[i], 0.2 + 0.15 * i) if i < len(cues) else ctx.f(1 + i)
        _chip(ctx, ch, 0.225 + 0.055 * i, f, panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), size=0.022, disappear=f_big - 1)
    if p.get("big"):
        ctx.text(p["big"], 0.5, 0.17, 0.05, WHITE, FONT_PATH, appear=f_big, panel=hexc("9a1020"), max_w_frac=0.82)
        if p.get("big_sub"):
            _sub(ctx, p["big_sub"], 0.245, f_big + 6)


AIR_BUILDERS = {
    "airport_scene": b_airport_scene,
    "flight_profile": b_flight_profile,
    "altitude_margin": b_altitude_margin,
    "cockpit_workload": b_cockpit_workload,
    "crosswind_approach": b_crosswind_approach,
    "tightrope": b_tightrope,
    "seatbelt_sign": b_seatbelt_sign,
}
L.BUILDERS.update(AIR_BUILDERS)


# ================================================================ BUILDERS: bridges in war
# Abstract, neutral visuals: a low-poly city on two river banks, bridges with flowing traffic dots.
# A "hit" bridge only dims, gets a red marker ring and its traffic stops. No explosions, weapons, flags.
WATER = hexc("0f2a52")
BANK = hexc("182844")
BRIDGE_C = hexc("8a97ab")


def _water_mat():
    m = L.mat("water", WATER, rough=0.6, metal=0.0)
    p = m.node_tree.nodes.get("Principled BSDF")
    if p is not None and "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value = 0.08   # no grey grazing sheen
    return m


def _path_cum(pts):
    cum = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + (Vector(b) - Vector(a)).length)
    return cum


def _path_at(pts, cum, d):
    d = max(0.0, min(cum[-1], d))
    for i in range(len(cum) - 1):
        if cum[i + 1] >= d:
            seg = max(1e-6, cum[i + 1] - cum[i])
            t = (d - cum[i]) / seg
            return Vector(pts[i]).lerp(Vector(pts[i + 1]), t)
    return Vector(pts[-1])


def _movers(name, pts, count, T, mat, size=(2.2, 2.2, 1.2), speed=3.0, slow_from=None, slow_to=0.0, slow_over=20,
            stop_hide=None, loop=True, phase=0.0, src=None):
    """`count` dots moving along polyline `pts` (looping), speed in units/frame. From slow_from the speed eases to
    slow_to over slow_over frames; with stop_hide the dots disappear that many frames after stopping."""
    cum = _path_cum(pts)
    total = cum[-1]
    own_src = src is None
    if src is None:
        src = L.box(name + "_src", size, (0, 0, 0), mat)
        src.visible_shadow = False
    out = []
    for k in range(count):
        # one small mesh per dot (sources are built at the origin: L.box bakes its location into the mesh)
        o = L.box("%s_m%d" % (name, k), tuple(src.dimensions), (0, 0, 0), src.active_material)
        o.visible_shadow = False
        d = (total * (k + phase) / float(count)) % total
        for f in range(1, T + 1, 2):
            sp = speed
            if slow_from is not None and f >= slow_from:
                sp = speed + (slow_to - speed) * min(1.0, (f - slow_from) / float(slow_over))
            d += sp * 2
            if loop:
                d %= total
            kf(o, "location", f, _path_at(pts, cum, d), "CONSTANT")
        if stop_hide is not None:
            L.vis(o, stop_hide, show=False)
        out.append(o)
    if own_src:
        bpy.data.objects.remove(src)
    return out


def _river_x(y):
    return 45.0 * math.sin(y / 520.0)


RIVER_W = 130.0


def _river(z=0.05, y0=-1600, y1=2600, width=RIVER_W):
    pts = [(_river_x(y), y) for y in range(y0, y1 + 1, 40)]
    w = L.ribbon("river", pts, width, z, _water_mat())
    edge = L.emissive("bankedge", TEAL_DARK, 1.2, 0.5)
    for sx in (-1, 1):
        e = [(x + sx * width / 2.0, y) for x, y in pts]
        L.ribbon("bank%d" % sx, e, 2.0, z + 0.05, edge)
    return w


def _city(rng, extent_x=900, y0=-1300, y1=2300, cell=46, keep=0.55, river_gap=RIVER_W / 2 + 28, parent=None,
          max_h=46):
    mats = [L.mat("bld_a", hexc("4a5f86"), 0.8), L.mat("bld_b", hexc("5d739a"), 0.8), L.mat("bld_c", hexc("7486a6"), 0.8),
            L.mat("bld_lit", hexc("4d6290"), 0.8, emit=hexc("ffcf8a"), emit_strength=0.12)]
    src = L.box("bldsrc", (1, 1, 1), (0, 0, 0), mats[0])
    made = 0
    y = y0
    while y < y1:
        x = -extent_x
        while x < extent_x:
            if rng.random() < keep and abs(x - _river_x(y)) > river_gap + 10:
                w = rng.uniform(0.5, 0.85) * cell
                d = rng.uniform(0.5, 0.85) * cell
                near = max(0.0, 1.0 - abs(x - _river_x(y)) / 600.0)
                h = rng.uniform(6, 14) + near * rng.uniform(0, max_h)
                o = src.copy()
                o.data = src.data
                L.link(o)
                o.location = (x + rng.uniform(-4, 4), y + rng.uniform(-4, 4), h / 2.0)
                o.scale = (w, d, h)
                mi = 3 if rng.random() < 0.18 else rng.randint(0, 2)
                o.material_slots[0].link = "OBJECT"
                o.material_slots[0].material = mats[mi]
                if parent is not None:
                    o.parent = parent
                made += 1
            x += cell
        y += cell
    bpy.data.objects.remove(src)
    return made


def _bridge(name, y, kind="beam", deck_z=9.0, width=16.0, span_extra=40.0):
    """A straight bridge across the river at y. Returns dict with root, deck, glow strip and the traffic paths."""
    xc = _river_x(y)
    span = RIVER_W + span_extra
    root = _empty(name, (xc, y, 0))
    deck_m = L.mat("deck_" + name, BRIDGE_C, 0.5)
    deck = L.box(name + "_deck", (span, width, 1.6), (0, 0, 0), deck_m, bevel=0.2)
    deck.parent = root
    deck.location = (0, 0, deck_z)
    for sx in (-1, 1):
        rail = L.box(name + "_rail%d" % sx, (span, 0.5, 1.0), (0, 0, 0), L.mat("rail", hexc("aab6c6"), 0.5))
        rail.parent = root
        rail.location = (0, sx * (width / 2 - 0.3), deck_z + 1.2)
    npier = 3
    for k in range(npier):
        x = -RIVER_W / 2 + RIVER_W * (k + 1) / (npier + 1)
        pc = L.cylinder(name + "_pier", 2.6, deck_z, (0, 0, 0), material=L.mat("pier", hexc("5f6f86"), 0.7), verts=10)
        pc.parent = root
        pc.location = (x, 0, deck_z / 2.0)
    if kind == "arch":
        pts = [(-RIVER_W / 2 + RIVER_W * i / 30.0, 0, deck_z + 1 + 22 * math.sin(math.pi * i / 30.0)) for i in range(31)]
        for sy in (-1, 1):
            a = _polyline(name + "_arch%d" % sy, [(px, sy * (width / 2 - 0.5), pz) for px, _, pz in pts], 0.9,
                          L.mat("arch", hexc("b9c4d3"), 0.4))
            a.parent = root
    elif kind == "cable":
        tw = L.box(name + "_tower", (3, width + 2, 46), (0, 0, 0), L.mat("tower_b", hexc("b9c4d3"), 0.4))
        tw.parent = root
        tw.location = (-RIVER_W * 0.15, 0, 23)
        for k in range(7):
            for sx in (-1, 1):
                c = _polyline(name + "_cab", [(-RIVER_W * 0.15, 0, 44 - k * 2.5),
                                              (-RIVER_W * 0.15 + sx * (14 + k * 9), 0, deck_z + 1)], 0.18,
                              L.mat("cable", hexc("dfe5ec"), 0.4))
                c.parent = root
    glow_m, glow_s = L.add_mat("glow_" + name, TEAL, 2.0)
    strip = L.box(name + "_strip", (span, 0.6, 0.3), (0, 0, 0), glow_m)
    strip.parent = root
    strip.location = (0, -width / 2 - 0.4, deck_z - 0.3)
    strip.visible_shadow = False
    lane = []
    for sy, direction in ((-3.2, 1), (3.2, -1)):
        xs = [-span / 2 - 60, span / 2 + 60]
        if direction < 0:
            xs = xs[::-1]
        lane.append([(xc + xs[0], y + sy, deck_z + 1.4), (xc + xs[1], y + sy, deck_z + 1.4)])
    return {"root": root, "deck": deck, "deck_m": deck_m, "glow_s": glow_s, "lanes": lane, "y": y, "xc": xc,
            "deck_z": deck_z}


def _traffic_mats():
    return (L.emissive("car_w", hexc("fff1d0"), 6.0, 0.2), L.emissive("car_r", hexc("ff3a3a"), 5.0, 0.2))


def _bridge_traffic(name, br, T, mats, n=10, speed=2.2, stop=None, hide_after=None):
    out = []
    for li, lane in enumerate(br["lanes"]):
        out += _movers("%s_l%d" % (name, li), lane, n, T, mats[li % 2], (7.0, 4.0, 3.0), speed,
                       slow_from=stop, slow_to=0.0, slow_over=18, stop_hide=hide_after, phase=0.37 * li)
    return out


def _hit_marker(ctx, name, br, f):
    """Dim a bridge (teal strip fades out, deck darkens) and add a pulsing red marker ring + pin above it."""
    s = br["glow_s"]
    kf_socket(s, 1, 2.0)
    kf_socket(s, f, 2.0)
    kf_socket(s, f + 10, 0.0)
    p = br["deck_m"].node_tree.nodes.get("Principled BSDF")
    if p is not None:
        kf_socket(p.inputs["Base Color"], 1, BRIDGE_C)
        kf_socket(p.inputs["Base Color"], f, BRIDGE_C)
        kf_socket(p.inputs["Base Color"], f + 12, hexc("2a2f3a"))
    loc = (br["xc"], br["y"], br["deck_z"] + 3)
    L.pulse_rings(name + "_ring", loc, RED, f, ctx.frames + 40, period=34, r1=38.0, rot=(0, 0, 0), count=2,
                  strength=4.0, minor=0.012)
    m, _ = _fade_mat(name + "_redstrip", RED, f + 4, None, 3.5, 8)
    rs = L.box(name + "_red", (RIVER_W + 40, 1.0, 0.4), (br["xc"], br["y"] - 8.6, br["deck_z"] - 0.3), m)
    rs.visible_shadow = False


def _city_world(ctx, sky="dusk", fog_d=0.00045, fog_start=300, seed=11):
    sun = _sky_env(ctx, sky, (62, 0, 130), fog_d, fog_start)
    L.add_sun(0.9, (55, 0, -40), (0.75, 0.85, 1.0))
    rng = random.Random(seed)
    _ground(12000, BANK)
    _river()
    _city(rng)
    return sun, rng



BRIDGE_YS = [(-320, "beam"), (-40, "beam"), (240, "arch"), (520, "beam"), (820, "cable")]


def b_river_city(ctx, p):
    """Low-poly city on two banks of a river with five bridges and flowing traffic dots.
    mode hook: oblique view looking upriver; on hit_cue three bridges dim, get red marker rings, their traffic
    stops; names appear as chips; a TRAFFIC RESTRICTED chip on chip_cue.
    mode detour: closer view; the nearest bridge is closed (red), traffic takes a long detour along the
    embankment to the next bridge.
    mode outro: wide crane-up at dusk, all bridges glowing teal."""
    T = ctx.frames
    mode = p.get("mode", "hook")
    sun, rng = _city_world(ctx)
    mats = _traffic_mats()
    brs = [_bridge("br%d" % i, y, kind) for i, (y, kind) in enumerate(BRIDGE_YS)]
    if mode == "hook":
        f_hit = _cue(ctx, p, "hit_cue", "hit", 0.4)
        named = [4, 1, 0]   # north -> south: Podilsko-Voskresenskyi, Darnytskyi, Pivdennyi (South) (stylised)
        for i, br in enumerate(brs):
            hit = i in named
            _bridge_traffic("tr%d" % i, br, T, mats, 9, 2.0, stop=(f_hit + 4 if hit else None),
                            hide_after=(f_hit + 40 if hit else None))
            if hit:
                _hit_marker(ctx, "hit%d" % i, br, f_hit + 3 * named.index(i))
        ctx.camera((-260, -980, 420), target=(0, 300, 0), lens=30)
        L.animate_cam(ctx, [(1, (-280, -1020, 450)), (T, (-200, -900, 360))])
        L.animate_target(ctx, [(1, (0, 320, 0)), (T, (10, 260, 0))])
        _far_cam(ctx)
        for k, nm in enumerate(p.get("names", [])):
            _chip(ctx, nm, 0.3 + 0.052 * k, f_hit + 8 + 5 * k, panel=hexc("3a1620") if False else NAVY, size=0.02)
        if p.get("chip"):
            _chip(ctx, p["chip"], 0.3 + 0.052 * len(p.get("names", [])) + 0.01, _cue(ctx, p, "chip_cue", "traffic", 0.8),
                  panel=hexc("9a1020"), size=0.022)
        if p.get("card"):
            ctx.card(p["card"], p.get("subcard"), y_frac=0.14, size=0.048)
    elif mode == "detour":
        b0, b1 = brs[1], brs[2]
        f_d = _cue(ctx, p, "chip_cue", "detours", 0.3)
        _hit_marker(ctx, "closed", b0, 2)
        for i, br in enumerate(brs):
            if i != 1:
                _bridge_traffic("tr%d" % i, br, T, mats, 8, 2.0)
        # detour route: west bank road along the river -> bridge b1 -> back down the east bank
        off = RIVER_W / 2 + 18
        z = 1.2
        route = [(b0["xc"] - off - 80, b0["y"] - 3, z), (b0["xc"] - off, b0["y"] - 3, z)]
        for yy in range(int(b0["y"]), int(b1["y"]) + 1, 20):
            route.append((_river_x(yy) - off, yy - 3, z))
        route += [(b1["xc"] - off, b1["y"] - 3, b1["deck_z"] + 1.4), (b1["xc"] + off, b1["y"] - 3, b1["deck_z"] + 1.4)]
        for yy in range(int(b1["y"]), int(b0["y"]) - 1, -20):
            route.append((_river_x(yy) + off, yy + 3, z))
        route.append((b0["xc"] + off + 80, b0["y"] + 3, z))
        _polyline("route", [(x, y, 0.8) for x, y, _ in route], 1.4, L.emissive("route", AMBER, 1.6))
        rl = bpy.data.objects["route"]
        kf(rl.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
        kf(rl.data, "bevel_factor_end", f_d - 20, 0.0, "BEZIER")
        kf(rl.data, "bevel_factor_end", f_d + 25, 1.0, "BEZIER")
        _movers("det", route, 26, T, mats[0], (3.0, 3.0, 1.6), 2.6)
        # the short route that is now closed: dashed red line straight across
        for k in range(8):
            L.box("short%d" % k, (8, 2.0, 0.4), (b0["xc"] - 70 + k * 20, b0["y"] - 20, 1.0), L.emissive("short", RED, 2.0))
        ctx.camera((-330, -420, 520), target=(10, 150, 0), lens=28)
        L.animate_cam(ctx, [(1, (-340, -440, 540)), (T, (-280, -360, 470))])
        _far_cam(ctx)
        if p.get("card"):
            ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=_cue(ctx, p, "card_cue", "three", 0.05))
        if p.get("chip"):
            _chip(ctx, p["chip"], 0.225, f_d, panel=hexc("9a1020"), size=0.024)
    else:  # outro
        for i, br in enumerate(brs):
            _bridge_traffic("tr%d" % i, br, T, mats, 8, 2.0)
        ctx.camera((-120, -700, 120), target=(0, 200, 20), lens=28)
        L.animate_cam(ctx, [(1, (-130, -720, 110)), (T, (-300, -980, 520))])
        L.animate_target(ctx, [(1, (0, 150, 30)), (T, (0, 300, 0))])
        _far_cam(ctx)
        if p.get("card"):
            n_lines = p["card"].count("\n") + 1
            ctx.card(p["card"], None, y_frac=0.15, size=0.048, appear=ctx.f(0.3))
            if p.get("subcard"):
                _sub(ctx, p["subcard"], 0.15 + 0.045 * n_lines + 0.05, _cue(ctx, p, "sub_cue", "tell", 0.4))
    _sun_glow(ctx, sun, "dusk", size=1000)


def b_river_barrier(ctx, p):
    """Top-down map-like view: green-navy land with a wide winding river from top to bottom.
    mode intro: the river edge lines glow on chip_cue. mode bridges: a dashed BARRIER line runs along the river
    on split_cue; four bridge nodes light up on chip_cue with arrows converging on them from both banks."""
    T = ctx.frames
    mode = p.get("mode", "intro")
    _env(ctx, NAVY, 2.0, (40, 0, 30))
    rng = random.Random(21)
    land = L.plane("land", 3000, 3000, (0, 0, 0), L.mat("land", hexc("1d3a4a"), 0.95))
    cols = [hexc("21424f"), hexc("1a3443"), hexc("26485a"), hexc("1d3c48")]
    for i in range(120):
        x, y = rng.uniform(-900, 900), rng.uniform(-1400, 1400)
        if abs(x - _river_x(y * 1.0) * 2.2) < RIVER_W * 1.1:
            continue
        o = L.plane("patch", rng.uniform(60, 180), rng.uniform(60, 180), (x, y, 0.1), L.mat("patch%d" % (i % 4), cols[i % 4], 0.95))
        o.rotation_euler = (0, 0, rng.uniform(-0.4, 0.4))
    pts = [(_river_x(y) * 2.2, y) for y in range(-1500, 1501, 30)]
    L.ribbon("river_m", pts, RIVER_W * 1.6, 6.0, _water_mat())
    f_chip = _cue(ctx, p, "chip_cue", "rivers" if mode == "intro" else "bridges", 0.5)
    f_split = _cue(ctx, p, "split_cue", "split", 0.35)
    for sx in (-1, 1):
        m, _ = _fade_mat("edge%d" % sx, TEAL, f_chip if mode == "intro" else 2, None, 2.5, 10)
        L.ribbon("edge%d" % sx, [(x + sx * RIVER_W * 0.8, y) for x, y in pts], 6.0, 7.0, m)
    # little towns as clusters of tiny blocks
    src = L.box("tsrc", (1, 1, 1), (0, 0, 0), L.mat("town", hexc("6f7f95"), 0.7))
    for t in range(14):
        ty = rng.uniform(-1200, 1200)
        side = rng.choice((-1, 1))
        tx = _river_x(ty) * 2.2 + side * rng.uniform(180, 700)
        for k in range(rng.randint(8, 18)):
            o = _copy(src, (tx + rng.uniform(-50, 50), ty + rng.uniform(-50, 50), 4), scale=(rng.uniform(8, 20), rng.uniform(8, 20), rng.uniform(4, 16)))
    bpy.data.objects.remove(src)
    if mode == "bridges":
        dm = L.emissive("barrier", RED, 2.5)
        dashes = []
        for k, (x, y) in enumerate(pts[::3]):
            if k % 2:
                continue
            d = L.box("dash%d" % k, (6, 40, 0.5), (x, y, 8.0), dm)
            d.visible_shadow = False
            L.vis(d, f_split + k // 2)
        nodes_y = [-900, -250, 380, 1000]
        for k, ny in enumerate(nodes_y):
            nx = _river_x(ny) * 2.2
            fb = f_chip + 4 * k
            br = L.box("bnode%d" % k, (RIVER_W * 1.9, 22, 4), (nx, ny, 3), L.emissive("bnode", hexc("f4f7fb"), 2.5))
            L.vis(br, fb)
            L.wave_ring("bring%d" % k, (nx, ny, 4), TEAL, fb, fb + 30, 120, strength=4, minor=0.03)
            for sx in (-1, 1):
                for j, dy in enumerate((-260, 0, 260)):
                    a0 = Vector((nx + sx * 520, ny + dy, 6))
                    a1 = Vector((nx + sx * (RIVER_W * 1.1), ny, 6))
                    ar = _polyline("arw%d%d%d" % (k, sx, j), [tuple(a0), tuple(a1)], 4.0, L.emissive("arw", AMBER, 2.0))
                    kf(ar.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
                    kf(ar.data, "bevel_factor_end", fb + 4, 0.0, "BEZIER")
                    kf(ar.data, "bevel_factor_end", fb + 26, 1.0, "BEZIER")
    ctx.camera((0, -1500, 2300), target=(0, 0, 0), lens=30)
    if mode == "intro":
        L.animate_cam(ctx, [(1, (0, -1900, 3000)), (T, (0, -1350, 2050))])
    else:
        L.animate_cam(ctx, [(1, (0, -1350, 2050)), (T, (100, -1150, 1800))])
    L.animate_target(ctx, [(1, (0, 80, 0)), (T, (0, 120, 0))])
    _far_cam(ctx)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=_cue(ctx, p, "card_cue", "why", 0.05))
    if p.get("chip"):
        _chip(ctx, p["chip"], 0.225, f_chip + 4, panel=hexc("9a1020") if mode == "bridges" else hexc("0d6f7a"), size=0.024)


def b_supply_funnel(ctx, p):
    """Supply flows (coloured dots on many roads) converge through funnel guide-lines into one bridge over a
    river, cross single file, then spread out again. Item chips pop on their cue words; the funnel lines glow on
    funnel_cue."""
    T = ctx.frames
    _env(ctx, NAVY, 2.0, (50, 0, 30), fog_density=0.0015, fog_start=200)
    rng = random.Random(4)
    L.plane("land", 3000, 3000, (0, 0, 0), L.mat("land2", hexc("1b3346"), 0.95))
    L.plane("river2", 3000, 90, (0, 0, 0.1), _water_mat(), rot=(0, 0, 0))
    river = bpy.data.objects["river2"]
    river.rotation_euler = (0, 0, 0)
    # river runs along X here; bridge crosses along Y at x=0
    L.box("fdeck", (18, 130, 2.0), (0, 0, 6), L.mat("deck_f", BRIDGE_C, 0.5), bevel=0.2)
    for yy in (-30, 0, 30):
        L.cylinder("fpier", 2.2, 6, (0, yy, 3), material=L.mat("pier", hexc("5f6f86"), 0.7), verts=10)
    f_fun = _cue(ctx, p, "funnel_cue", "funnels", 0.8)
    fm, _ = _fade_mat("funnel", TEAL, f_fun, None, 3.0, 10, start=0.6)
    for sx in (-1, 1):
        _polyline("fun_s%d" % sx, [(sx * 260, -420, 1), (sx * 14, -80, 1), (sx * 14, -66, 1)], 2.0, fm)
        _polyline("fun_n%d" % sx, [(sx * 14, 66, 1), (sx * 14, 80, 1), (sx * 260, 420, 1)], 2.0, fm)
    items = p.get("items", ["FOOD", "FUEL", "SUPPLIES", "PEOPLE"])
    cues = p.get("item_cues", ["food", "fuel", "ammunition", "troops"])
    cols = [hexc("5fc9a8"), AMBER, hexc("c9d3df"), hexc("4f8dff")]
    fr = [ctx.word_time(cues[i], 0.3 + 0.08 * i) for i in range(len(items))]
    for i, it in enumerate(items):
        m = L.emissive("sup%d" % i, cols[i], 3.0, 0.2)
        for r in range(3):
            x0 = (-240 + 160 * i + rng.uniform(-30, 30))
            route = [(x0, -620, 2), (x0 * 0.5, -260, 2), (0, -70, 2), (0, -60, 8), (0, 60, 8), (0, 70, 2),
                     (x0 * 0.5 + rng.uniform(-40, 40), 260, 2), (x0 + rng.uniform(-60, 60), 620, 2)]
            dots = _movers("s%d_%d" % (i, r), route, 5, T, m, (8, 8, 4), 3.2, phase=rng.random())
            for o in dots:
                L.vis(o, fr[i])
        ctx_y = 0.222 + 0.052 * i
    ctx.camera((-380, -520, 480), target=(0, 20, 0), lens=30)
    L.animate_cam(ctx, [(1, (-400, -560, 520)), (T, (-300, -450, 420))])
    _far_cam(ctx)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=_cue(ctx, p, "card_cue", "one", 0.3))
    for i, it in enumerate(items):
        ctx.text(it, 0.5, 0.222 + 0.05 * i, 0.021, WHITE, FONT_PATH, appear=fr[i], panel=NAVY if i % 2 == 0 else hexc("0d3b4f"),
                 max_w_frac=0.6)


def b_utility_bridge(ctx, p):
    """3/4 close view of one bridge: cars on the deck, and three utility lines under it (power = amber
    cable with pulses, water = blue pipe with flow, communications = teal line with light pulses) that light up
    on their cues. On dim_cue the flows stop, the bridge gets a red marker and the far bank's lights go dark."""
    T = ctx.frames
    _env(ctx, hexc("0d1838"), 1.0, (55, 0, 140), fog_density=0.002, fog_start=120)
    L.add_sun(0.5, (50, 0, -30), (0.8, 0.88, 1.0))
    rng = random.Random(8)
    L.plane("land3", 4000, 4000, (0, 0, -0.5), L.mat("land3", BANK, 0.95))
    L.plane("riv3", 140, 4000, (0, 0, 0), _water_mat())
    span = 200
    L.box("udeck", (span, 16, 2.0), (0, 0, 10), L.mat("deck_u", BRIDGE_C, 0.5), bevel=0.2)
    for x in (-35, 0, 35):
        L.cylinder("upier", 2.8, 10, (x, 0, 5), material=L.mat("pier", hexc("5f6f86"), 0.7), verts=10)
    cues = p.get("chip_cues", ["power", "water", "communication"])
    fr = [ctx.word_time(cues[i], 0.2 + 0.15 * i) for i in range(3)]
    f_dim = _cue(ctx, p, "dim_cue", "damage", 0.7)
    cols = [AMBER, hexc("3f8cff"), TEAL]
    for i in range(3):
        z = 8.0 - i * 1.7
        y = -4 + i * 4
        base = _polyline("util%d" % i, [(-span / 2 - 200, y, z), (span / 2 + 200, y, z)], 0.55,
                         L.mat("util%d" % i, hexc("3a4658"), 0.5))
        m, s = _fade_mat("utilg%d" % i, cols[i], fr[i], None, 2.2, 8)
        kf_socket(s, f_dim, 2.2)
        kf_socket(s, f_dim + 10, 0.15)
        gl = _polyline("utilg%d" % i, [(-span / 2 - 200, y, z), (span / 2 + 200, y, z)], 0.62, m)
        # pulses moving along the line
        pm = L.emissive("pulse%d" % i, cols[i], 6.0, 0.2)
        pulses = _movers("pl%d" % i, [(-span / 2 - 200, y, z), (span / 2 + 200, y, z)], 9, T, pm, (4.0, 1.4, 1.4),
                         3.0 if i != 1 else 1.6, slow_from=f_dim, slow_to=0.0, slow_over=10, stop_hide=f_dim + 12)
        for o in pulses:
            L.vis(o, fr[i])
    mats = _traffic_mats()
    for li, (yy, dirn) in enumerate(((-3.5, 1), (3.5, -1))):
        xs = (-span / 2 - 150, span / 2 + 150)[::dirn]
        _movers("car%d" % li, [(xs[0], yy, 11.6), (xs[1], yy, 11.6)], 10, T, mats[li], (3.2, 1.8, 1.4), 2.0,
                slow_from=f_dim, slow_to=0.0, slow_over=16, stop_hide=f_dim + 50)
    # far bank houses whose windows go dark on dim_cue
    hm, hs = L.add_mat("winlit", hexc("ffcf8a"), 1.6)
    kf_socket(hs, 1, 1.6)
    kf_socket(hs, f_dim + 14, 1.6)
    kf_socket(hs, f_dim + 30, 0.05)
    bsrc = L.box("hsrc", (1, 1, 1), (0, 0, 0), L.mat("hbody", hexc("2a3c63"), 0.8))
    wsrc = L.box("wsrc", (1, 1, 1), (0, 0, 0), hm)
    for k in range(60):
        x = rng.uniform(90, 600)
        yv = rng.uniform(-250, 400)
        h = rng.uniform(8, 30)
        _copy(bsrc, (x, yv, h / 2), scale=(rng.uniform(12, 24), rng.uniform(12, 24), h))
        _copy(wsrc, (x - 0.2, yv - 0.2, h * 0.6), scale=(rng.uniform(12, 24) * 0.8 + 0.6, rng.uniform(12, 24) * 0.8 + 0.6, 1.4))
    bpy.data.objects.remove(bsrc)
    bpy.data.objects.remove(wsrc)
    m_red, _ = _fade_mat("ured", RED, f_dim, None, 3.0, 6)
    L.pulse_rings("uring", (0, 0, 13), RED, f_dim, T + 40, period=30, r1=26.0, count=2, strength=4.0, minor=0.012)
    ctx.camera((-85, -105, 32), target=(5, 0, 7), lens=30)
    L.animate_cam(ctx, [(1, (-90, -110, 34)), (T, (-70, -90, 26))])
    _far_cam(ctx)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.048, appear=_cue(ctx, p, "card_cue", "two", 0.05))
    for i, ch in enumerate(p.get("chips", [])):
        _chip(ctx, ch, 0.222 + 0.058 * i, fr[i], panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), size=0.022)


def _arch_icon(name, loc, scale=1.0, material=None):
    root = _empty(name, loc)
    m = material or L.mat("icon_b", hexc("c9d3df"), 0.45)
    deck = L.box(name + "_d", (12, 1.4, 0.5), (0, 0, 0), m)
    deck.parent = root
    deck.location = (0, 0, 2.2)
    pts = [(-5 + 10 * i / 20.0, 0, 2.4 + 2.6 * math.sin(math.pi * i / 20.0)) for i in range(21)]
    for sy in (-0.6, 0.6):
        a = _polyline(name + "_a", [(x, sy, z) for x, _, z in pts], 0.14, m)
        a.parent = root
    for x in (-5.5, 5.5):
        t = L.box(name + "_t", (1.0, 1.6, 4.2), (0, 0, 0), m)
        t.parent = root
        t.location = (x, 0, 2.1)
    w = L.plane(name + "_w", 16, 4, (0, 0, 0), _water_mat())
    w.parent = root
    root.scale = (scale, scale, scale)
    return root


def b_history_cards(ctx, p):
    """Timeline with two history cards (e.g. 1944 Arnhem, 1945 Remagen), each a panel with a low-poly arch
    bridge icon; they slide up on their cue words; neutral wording only."""
    T = ctx.frames
    _env(ctx, hexc("0d1838"), 2.2, (50, 0, 25))
    L.plane("floor", 400, 400, (0, 0, 0), L.mat("hfloor", hexc("12224a"), 0.9))
    tl = _polyline("timeline", [(-14, -2, 0.3), (14, -2, 0.3)], 0.12, L.emissive("tline", TEAL, 2.0))
    cards = p.get("cards", [])
    cues = p.get("cues", ["1944", "1945"])
    cam = ctx.camera((0, -35, 10), target=(0, 0, 5.2), lens=30)
    L.animate_cam(ctx, [(1, (-1.0, -36, 10)), (T, (1.0, -33, 9.5))])
    for i, (title, sub) in enumerate(cards):
        x = -3.5 + 7.0 * i
        f = ctx.word_time(cues[i] if i < len(cues) else "", 0.25 + 0.4 * i)
        root = _empty("hc%d" % i, (x, 0, 0))
        panel = L.box("hcp%d" % i, (6.4, 0.4, 11.0), (0, 0, 0), L.mat("hcp", hexc("1c2b4f"), 0.6), bevel=0.15)
        panel.parent = root
        panel.location = (0, 0.4, 6.4)
        edge = L.box("hce%d" % i, (6.4, 0.45, 0.35), (0, 0, 0), L.emissive("hce", RED, 2.5))
        edge.parent = root
        edge.location = (0, 0.3, 11.8)
        ic = _arch_icon("arch%d" % i, (0, 0, 0), 0.42)
        ic.parent = root
        ic.location = (0, -1.0, 4.6)
        t1 = L.label3d(ctx, title.split(" · ")[0], (0, 0, 0), 1.1, WHITE, rot=(90, 0, 0), face_cam=False)
        t1.parent = root
        t1.location = (0, -0.1, 10.0)
        t2 = L.label3d(ctx, title.split(" · ")[1] if " · " in title else "", (0, 0, 0), 0.68, AMBER, rot=(90, 0, 0), face_cam=False)
        t2.parent = root
        t2.location = (0, -0.1, 8.6)
        t3 = L.label3d(ctx, sub, (0, 0, 0), 0.4, hexc("dff3f6"), rot=(90, 0, 0), font=FONT_PATH_SUB, face_cam=False)
        t3.parent = root
        t3.location = (0, -0.1, 2.0)
        dot = L.cylinder("hdot%d" % i, 0.5, 0.3, (x, -2, 0.35), material=L.emissive("hdot", TEAL, 3.0), verts=16)
        kf(root, "location", 1, Vector((x, 0, -14)), "CONSTANT")
        kf(root, "location", max(2, f - 1), Vector((x, 0, -14)), "BEZIER")
        kf(root, "location", f + 14, Vector((x, 0, 0.6)), "BEZIER")
        kf(root, "location", f + 18, Vector((x, 0, 0)), "BEZIER")
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=ctx.f(0.2))


def b_pontoon_bridge(ctx, p):
    """A massive concrete bridge in the background (piers + deck); on chip_cue pontoon segments float in
    one by one from downstream and lock into a floating bridge across the river, then traffic dots cross it."""
    T = ctx.frames
    _env(ctx, hexc("1a2a4c"), 2.2, (55, 0, 40), fog_density=0.002, fog_start=150)
    L.add_sun(0.7, (55, 0, -60), (0.8, 0.88, 1.0))
    rng = random.Random(14)
    L.plane("land4", 4000, 4000, (0, 0, -0.4), L.mat("land4", hexc("223b4a"), 0.95))
    L.plane("riv4", 4000, 120, (0, 0, 0), _water_mat())
    # big bridge in the background (river runs along X; bridges cross along Y)
    L.box("bigdeck", (24, 150, 4), (75, 0, 16), L.mat("deck_b", BRIDGE_C, 0.5), bevel=0.3)
    for yy in (-40, 0, 40):
        L.box("bigpier", (10, 6, 16), (75, yy, 8), L.mat("pier", hexc("5f6f86"), 0.7), bevel=0.3)
    f_p = _cue(ctx, p, "chip_cue", "pontoon", 0.55)
    n = 9
    seg_w = 120.0 / n
    pm = L.mat("pontoon", hexc("3d5a3f"), 0.6)
    top = L.mat("pontop", hexc("8a97ab"), 0.6)
    for k in range(n):
        root = _empty("pon%d" % k)
        b = L.box("pon_b%d" % k, (12, seg_w - 0.6, 2.2), (0, 0, 0), pm, bevel=0.3)
        b.parent = root
        b.location = (0, 0, 0.6)
        t = L.box("pon_t%d" % k, (11, seg_w - 0.2, 0.4), (0, 0, 0), top)
        t.parent = root
        t.location = (0, 0, 1.9)
        yk = -60 + seg_w * (k + 0.5)
        fk = f_p + 5 * k
        kf(root, "location", 1, Vector((-260, yk, 0)), "CONSTANT")
        kf(root, "location", max(2, fk - 30), Vector((-260, yk, 0)), "BEZIER")
        kf(root, "location", fk, Vector((-8, yk, 0)), "BEZIER")
        kf(root, "location", fk + 8, Vector((0, yk, 0)), "BEZIER")
        for f in range(1, T + 1, 6):
            tt = (f - 1) / ctx.fps
            kf(root, "rotation_euler", f, Vector((math.radians(0.8 * math.sin(tt * 2 + k)), 0, 0)), "BEZIER")
    mats = _traffic_mats()
    f_cross = f_p + 5 * n + 12
    cars = _movers("pcar", [(0, -140, 3.0), (0, 140, 3.0)], 6, T, mats[0], (3.4, 4.0, 1.8), 2.2)
    for o in cars:
        L.vis(o, f_cross)
    ctx.camera((-130, -150, 75), target=(30, 5, 4), lens=30)
    L.animate_cam(ctx, [(1, (-140, -160, 80)), (T, (-110, -125, 62))])
    _far_cam(ctx)
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.042, appear=_cue(ctx, p, "card_cue", "but", 0.05))
    if p.get("chip"):
        _chip(ctx, p["chip"], 0.225, f_p, panel=hexc("0d6f7a"), size=0.024)
    _chip(ctx, "MASSIVE STEEL & CONCRETE", 0.225, _cue(ctx, p, "mass_cue", "massive", 0.3), panel=NAVY, size=0.022,
          disappear=f_p - 1)


def b_arteries(ctx, p):
    """Abstract branching 'arteries' (teal tubes) with flowing light dots. On pinch_cue one main vessel gets a red
    pinch ring and all flow slows; on backup_cue a bypass vessel draws in and the flow speeds back up."""
    T = ctx.frames
    _env(ctx, hexc("0a1430"), 1.5, (50, 0, 30))
    tube = L.emissive("vessel", TEAL_DARK, 1.0)
    f_pi = _cue(ctx, p, "pinch_cue", "pinch", 0.3)
    f_bk = _cue(ctx, p, "backup_cue", "backup", 0.8)
    trunk = [(0, 0, -10), (0, 0, -3), (0, 0, 3)]
    branches = [
        [(0, 0, 3), (-3, 0, 6), (-6, 0, 9), (-8, 0, 12)],
        [(0, 0, 3), (0.5, 0, 7), (0, 0, 11), (0.5, 0, 14)],
        [(0, 0, 3), (3, 0, 6), (6, 0, 8.5), (8, 0, 11)],
        [(-3, 0, 6), (-6, 0, 6.5), (-8.5, 0, 7)],
        [(3, 0, 6), (6, 0, 5), (8.5, 0, 5)],
        [(0.5, 0, 7), (3, 0, 9.5), (4, 0, 13)],
    ]
    _polyline("trunk", trunk, 0.55, tube)
    for i, b in enumerate(branches):
        _polyline("br%d" % i, b, 0.32 if i < 3 else 0.22, tube)
    dot_m = L.emissive("blood", hexc("e6fbff"), 5.0, 0.2)
    src = L.box("dsrc", (0.35, 0.35, 0.35), (0, 0, 0), dot_m)
    full = [trunk + b[1:] for b in branches[:3]] + [trunk + branches[0][1:2] + branches[3][1:],
                                                     trunk + branches[2][1:2] + branches[4][1:],
                                                     trunk + branches[1][1:2] + branches[5][1:]]
    for i, path in enumerate(full):
        cum = _path_cum(path)
        for k in range(10):
            o = _copy(src, (0, 0, 0))
            d = cum[-1] * k / 10.0
            for f in range(1, T + 1, 2):
                sp = 0.16
                if f >= f_pi:
                    sp = 0.16 - 0.13 * min(1.0, (f - f_pi) / 15.0)
                if f >= f_bk:
                    sp = 0.03 + 0.11 * min(1.0, (f - f_bk) / 20.0)
                d = (d + sp * 2) % cum[-1]
                kf(o, "location", f, _path_at(path, cum, d) + Vector((0, -0.4, 0)), "CONSTANT")
    bpy.data.objects.remove(src)
    # pinch ring on the trunk
    pm, _ = _fade_mat("pinch", RED, f_pi, None, 4.0, 6)
    pr = L.ring("pinchring", (0, -0.1, -1.5), pm, rot=(0, 0, 0), minor=0.22)
    kf(pr, "scale", 1, Vector((1.4, 1.4, 1.4)), "CONSTANT")
    kf(pr, "scale", f_pi, Vector((1.4, 1.4, 1.4)), "BEZIER")
    kf(pr, "scale", f_pi + 12, Vector((0.75, 0.75, 0.75)), "BEZIER")
    # bypass vessel
    bm, _ = _fade_mat("bypass", TEAL, f_bk, None, 3.0, 8)
    bp = _polyline("bypass", [(0, 0, -8), (-3.2, 0, -5.5), (-3.6, 0, -1.5), (-2.0, 0, 1.5), (-3, 0, 6)], 0.32, bm)
    kf(bp.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
    kf(bp.data, "bevel_factor_end", f_bk, 0.0, "BEZIER")
    kf(bp.data, "bevel_factor_end", f_bk + 25, 1.0, "BEZIER")
    ctx.camera((0, -44, 2.5), target=(0, 0, 1.6), lens=35)
    L.animate_cam(ctx, [(1, (-1.0, -46, 2.5)), (T, (1.0, -41, 2.8))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=ctx.f(0.2))
    if p.get("chip"):
        _chip(ctx, p["chip"], 0.225, _cue(ctx, p, "chip_cue", "backup", 0.8) + 4, panel=hexc("0d6f7a"), size=0.024)
    _chip(ctx, "PINCH = SLOWDOWN", 0.225, f_pi + 4, panel=hexc("9a1020"), size=0.024, disappear=f_bk)


BRIDGE_BUILDERS = {
    "river_city": b_river_city,
    "river_barrier": b_river_barrier,
    "supply_funnel": b_supply_funnel,
    "utility_bridge": b_utility_bridge,
    "history_cards": b_history_cards,
    "pontoon_bridge": b_pontoon_bridge,
    "arteries": b_arteries,
}
L.BUILDERS.update(BRIDGE_BUILDERS)

"""v2 aviation builders (persistent daytime airport world + airliner). Registers into scene_lib_v2.V2_BUILDERS.

No 3D text anywhere: labels / chips / cards are 2D overlays (pipeline/overlay_v2.py) that read the anchors
registered here with S.anchor(). Non-graphic: aircraft only fly normal approaches / departures or sit parked.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector, Matrix

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc, kf


def b_airport_hook(ctx, p):
    """Hook: the approved v2 look-test shot (light aircraft on a stable approach, camera pulls back to reveal
    the airport), stretched to the beat length. Anchor "plane" = top of the canopy."""
    T = ctx.frames
    speed = p.get("speed", 37.5)                       # m/s along the approach (test: 360 m in 9.6 s)
    yb = p.get("y1", -300.0)
    q = dict(p)
    q.setdefault("y1", yb)
    q.setdefault("y0", yb - speed * T / ctx.fps)
    plane = S.b_airport_approach_v2(ctx, q)
    S.anchor(ctx, "plane", plane, (0.0, 0.8, 1.0))
    return plane




# ================================================================ airliner (v2, smooth)
AIRLINER_FUSE = [  # y, half-width, z_top, z_bottom (narrow-body twin, ~37.5 m long, nose +Y)
    (18.75, 0.06, -0.18, -0.42), (18.3, 0.62, 0.28, -0.95), (17.4, 1.18, 0.86, -1.42), (16.2, 1.62, 1.42, -1.78),
    (14.8, 1.88, 1.80, -1.96), (13.0, 1.98, 1.98, -1.98), (-7.5, 1.98, 1.98, -1.98), (-10.5, 1.86, 1.98, -1.55),
    (-13.5, 1.42, 1.96, -0.72), (-16.2, 0.86, 1.92, 0.25), (-18.2, 0.42, 1.86, 1.05), (-18.9, 0.16, 1.80, 1.42)]
AL_WHITE = hexc("f3f5f7")
AL_NAVY = hexc("1d3566")
AL_RED = hexc("d8262f")
AL_GREY = hexc("c9ced5")


def _loft(bm, table, n=28, step=0.45, mat_index=0):
    ys = []
    y = table[-1][0]
    while y < table[0][0]:
        ys.append(y)
        y += step
    ys.append(table[0][0])
    tab = sorted(table, key=lambda r: r[0])
    rings = []
    for y in ys:
        w, zt, zb = S._catmull(tab, y)
        w = max(0.03, w)
        ring = []
        for k in range(n):
            th = 2 * math.pi * k / n
            c, s = math.cos(th), math.sin(th)
            ring.append(bm.verts.new((w * c, y, zb + (zt - zb) * (0.5 + 0.5 * s))))
        rings.append(ring)
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            faces.append(bm.faces.new((a[k], a[j], b[j], b[k])))
    for ring in (rings[0], rings[-1]):
        cz = sum(v.co.z for v in ring) / n
        c = bm.verts.new((0, ring[0].co.y, cz))
        for k in range(n):
            faces.append(bm.faces.new((ring[k], ring[(k + 1) % n], c)))
    for f in faces:
        f.material_index = mat_index
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def airliner_livery(root):
    """White body, navy tail + belly sweep, red cheat line, window row and cockpit windows (shader only)."""
    m, nt, N, Lk, p = S._new_mat("al_livery_" + root.name)
    tc = N.new("ShaderNodeTexCoord")
    tc.object = root
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    X, Y, Z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def M(op, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n.outputs[0]

    def band(v, lo, hi):
        return M("MULTIPLY", M("GREATER_THAN", v, lo), M("LESS_THAN", v, hi))
    ax = M("ABSOLUTE", X)
    fus = M("LESS_THAN", ax, 2.05)
    # windows: row at z 0.55..0.95, every 0.52 m from y -11 to 13 (rounded squares)
    wy = M("FRACT", M("MULTIPLY", Y, 1 / 0.52))
    win = M("MULTIPLY", band(wy, 0.25, 0.72), band(Z, 0.52, 0.98))
    win = M("MULTIPLY", win, band(Y, -11.5, 13.2))
    win = M("MULTIPLY", win, M("GREATER_THAN", ax, 1.2))
    # cockpit windows: band near the nose
    ck = M("MULTIPLY", band(Y, 15.6, 17.2), band(M("SUBTRACT", Z, M("MULTIPLY", M("SUBTRACT", Y, 15.6), -0.18)), 0.75, 1.25))
    ck = M("MULTIPLY", ck, M("GREATER_THAN", ax, 0.25))
    dark = M("MINIMUM", M("ADD", win, ck), 1.0)
    # red cheat line under the windows, navy belly from z < -0.9 along the cabin
    red = M("MULTIPLY", band(Z, 0.18, 0.32), M("MULTIPLY", fus, band(Y, -14.0, 16.0)))
    belly = M("MULTIPLY", M("LESS_THAN", Z, -1.05), M("MULTIPLY", fus, band(Y, -12, 15)))
    tail = M("MULTIPLY", M("GREATER_THAN", Z, 2.2), M("LESS_THAN", ax, 0.5))      # fin
    navy = M("MINIMUM", M("ADD", belly, tail), 1.0)
    c1 = N.new("ShaderNodeMix")
    c1.data_type = "RGBA"
    c1.inputs["A"].default_value = AL_WHITE
    c1.inputs["B"].default_value = AL_NAVY
    Lk.new(navy, c1.inputs["Factor"])
    c2 = N.new("ShaderNodeMix")
    c2.data_type = "RGBA"
    Lk.new(c1.outputs["Result"], c2.inputs["A"])
    c2.inputs["B"].default_value = AL_RED
    Lk.new(red, c2.inputs["Factor"])
    c3 = N.new("ShaderNodeMix")
    c3.data_type = "RGBA"
    Lk.new(c2.outputs["Result"], c3.inputs["A"])
    c3.inputs["B"].default_value = hexc("1a2230")
    Lk.new(dark, c3.inputs["Factor"])
    Lk.new(c3.outputs["Result"], p.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.3
    rr.inputs["To Max"].default_value = 0.08
    Lk.new(dark, rr.inputs["Value"])
    Lk.new(rr.outputs["Result"], p.inputs["Roughness"])
    p.inputs["Coat Weight"].default_value = 0.5
    p.inputs["Coat Roughness"].default_value = 0.06
    return S._finish(m, p.outputs[0])


def make_airliner_v2(ctx, name, gear_down=True):
    """Generic narrow-body twinjet. Nose +Y, origin at the wing root on the centre line (z = fuselage axis).
    Returns (root, parts) where parts = {"flaps": [objs with shape key 'down'], "gear": empty (scale z 0..1),
    "engines": [...]}"""
    root = L.link(bpy.data.objects.new(name, None))
    liv = airliner_livery(root)
    wing_m = S.pbr("al_wing_v2", AL_GREY, 0.35, 0.25, var=0.03)
    nac_m = S.pbr("al_nacelle_v2", hexc("e9ecef"), 0.3, 0.3, coat=0.4, var=0)
    dark = S.pbr("al_dark_v2", hexc("17191d"), 0.5, var=0)
    metal = S.pbr("al_metal_v2", hexc("aeb4ba"), 0.25, 0.8, var=0)
    bm = bmesh.new()
    _loft(bm, AIRLINER_FUSE, mat_index=0)
    _wfin = []
    S._wing(bm, 0.35, 6.4, 3.6, 1.35, -11.6, 3.0, 0.75, 7.0, 0.11, 0.09, 1, mat_index=0, n_span=4)   # stabiliser R
    S._wing(bm, 0.35, 6.4, 3.6, 1.35, -11.6, 3.0, 0.75, 7.0, 0.11, 0.09, -1, mat_index=0, n_span=4)  # stabiliser L
    S._wing(bm, 1.2, 7.4, 5.6, 1.9, -9.6, 4.9, 0.0, 0.0, 0.11, 0.09, vertical=True, mat_index=0, n_span=4)  # fin
    body = S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [liv], smooth=True), parent=root)
    sub = body.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1
    # wings (light grey), with winglets
    bm = bmesh.new()
    for side in (-1, 1):
        S._wing(bm, 1.6, 16.8, 6.4, 1.55, 3.4, 7.2, -1.25, 5.5, 0.13, 0.10, side, mat_index=0, n_span=6)
    S.obj(name + "_wings", S.mesh_from_bm(name + "_wings", bm, [wing_m], smooth=True), parent=root)
    tipz = -1.25 + math.tan(math.radians(5.5)) * (16.8 - 1.6)
    for side in (-1, 1):
        bm = bmesh.new()
        S._wing(bm, 0.0, 2.1, 1.45, 0.55, 3.4 - 7.2 + 0.05, 0.9, 0.0, 0.0, 0.10, 0.08, vertical=True, mat_index=0,
                n_span=2)
        S.obj(name + "_winglet%d" % side, S.mesh_from_bm(name + "_winglet", bm, [liv], smooth=True),
              (side * 16.75, 0, tipz), (0, side * math.radians(-12), 0), parent=root)
    # engines: lofted nacelles under the wings + pylons + dark intakes
    eng = []
    for side in (-1, 1):
        bm = bmesh.new()
        tab = [(2.3, 0.7, 0.7, -0.7), (2.0, 0.98, 0.98, -0.98), (0.8, 1.05, 1.05, -1.05), (-1.0, 0.92, 0.92, -0.92),
               (-1.9, 0.58, 0.58, -0.58), (-2.4, 0.3, 0.3, -0.3)]
        _loft(bm, tab, n=24, step=0.3, mat_index=0)
        r = bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=0.8)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, vec=(0, 2.25, 0), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 1
        S.bm_box(bm, (0, 0.6, 1.0), (0.35, 3.0, 0.9), 2)
        e = S.obj(name + "_eng%d" % side, S.mesh_from_bm(name + "_eng", bm, [nac_m, dark, wing_m], smooth=True),
                  (side * 5.9, 2.8, -2.35), parent=root)
        eng.append(e)
    # flaps: inboard trailing-edge strips with a 'down' shape key (no hinge maths)
    flaps = []
    for side in (-1, 1):
        bm = bmesh.new()
        segs = []
        for s_ in (1.8, 5.0, 9.5):
            f_ = (s_ - 1.6) / (16.8 - 1.6)
            chord = 6.4 + (1.55 - 6.4) * f_
            le = 3.4 - 7.2 * f_
            te = le - chord
            z = -1.25 + math.tan(math.radians(5.5)) * (s_ - 1.6)
            segs.append((side * s_, te + 0.05, z))
        vs_top = [bm.verts.new((x, y, z + 0.06)) for x, y, z in segs]
        vs_back = [bm.verts.new((x, y - 1.3, z)) for x, y, z in segs]
        vs_bot = [bm.verts.new((x, y + 0.2, z - 0.08)) for x, y, z in segs]
        for i in range(len(segs) - 1):
            bm.faces.new((vs_top[i], vs_top[i + 1], vs_back[i + 1], vs_back[i]))
            bm.faces.new((vs_bot[i], vs_back[i], vs_back[i + 1], vs_bot[i + 1]))
        me = S.mesh_from_bm(name + "_flap", bm, [wing_m])
        fo = S.obj(name + "_flap%d" % side, me, parent=root)
        fo.shape_key_add(name="basis")
        sk = fo.shape_key_add(name="down")
        n3 = len(segs)
        for i in range(n3):
            x, y, z = segs[i]
            sk.data[n3 + i].co = Vector((x, y - 1.6, z - 0.95))
            sk.data[2 * n3 + i].co = Vector((x, y - 0.1, z - 0.3))
            sk.data[i].co = Vector((x, y - 0.25, z - 0.05))
        flaps.append(fo)
    # gear: legs + wheels under a "gear" empty (scale z 0 = retracted)
    gear = L.link(bpy.data.objects.new(name + "_gear", None))
    gear.parent = root
    gear.location = (0, 0, -1.7)
    bm = bmesh.new()
    for (x, y, h) in ((-2.9, -1.2, 1.9), (2.9, -1.2, 1.9), (0, 13.6, 1.7)):
        S.bm_box(bm, (x, y, -h / 2), (0.22, 0.22, h), 0)
    S.obj(name + "_legs", S.mesh_from_bm(name + "_legs", bm, [metal]), parent=gear)
    bm = bmesh.new()
    for (x, y, h, r) in ((-2.9, -0.7, 1.9, 0.58), (-2.9, -1.7, 1.9, 0.58), (2.9, -0.7, 1.9, 0.58), (2.9, -1.7, 1.9, 0.58),
                         (0, 13.6, 1.7, 0.42)):
        for dx in (-0.32, 0.32):
            rr = bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=r, radius2=r, depth=0.34)
            bmesh.ops.rotate(bm, verts=rr["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, vec=(x + dx, y, -h - r * 0.3), verts=rr["verts"])
    S.obj(name + "_wheels", S.mesh_from_bm(name + "_wheels", bm, [dark], smooth=True), parent=gear)
    gear.scale = (1, 1, 1.0 if gear_down else 0.02)
    # lights: nav (red L, green R), white tail, landing lights, red beacon
    for sx, col in ((-1, hexc("ff2a2a")), (1, hexc("2aff6a"))):
        bm = bmesh.new()
        S._ellipsoid(bm, (sx * 17.0, -3.85, -1.25 + math.tan(math.radians(5.5)) * 15.2 + 0.1), (0.12, 0.18, 0.1), 0, 8, 6)
        S.obj(name + "_nav%d" % sx, S.mesh_from_bm(name + "_nav", bm, [S.emis("al_nav_%d" % sx, col, 8.0)]), parent=root)
    bm = bmesh.new()
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 2.6, 3.2, -1.45), (0.18, 0.08, 0.1), 0, 8, 6)
    S.obj(name + "_ldg", S.mesh_from_bm(name + "_ldg", bm, [S.emis("al_landing", hexc("fff6e0"), 30.0)]), parent=root)
    return root, {"flaps": flaps, "gear": gear, "engines": eng}


def flaps_to(parts, f0, f1, v0, v1):
    for fo in parts["flaps"]:
        kb = fo.data.shape_keys.key_blocks["down"]
        kb.value = v0
        kb.keyframe_insert("value", frame=f0)
        kb.value = v1
        kb.keyframe_insert("value", frame=f1)


def gear_to(parts, f0, f1, down=True):
    g = parts["gear"]
    kf(g, "scale", f0, Vector((1, 1, 0.02 if down else 1.0)), "BEZIER")
    kf(g, "scale", f1, Vector((1, 1, 1.0 if down else 0.02)), "BEZIER")


# ================================================================ effects (no text)
def _alpha_emis(name, color, strength, alpha):
    """Dithered, unlit, partly transparent streak material (TAA smooths the dither)."""
    if name in S._MV2:
        return S._MV2[name]
    m = bpy.data.materials.new(name)
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = nt.nodes.get("Material Output")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = alpha
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    S._MV2[name] = m
    return m


def streaks(ctx, parent, n, region, direction, length, speed, rng, start=1, color=hexc("ffffff"), alpha=0.45,
            thick=0.05, name="streak"):
    """Thin translucent lines flying along `direction` (unit, parent space) through a box region
    ((x0,x1),(y0,y1),(z0,z1)); speed in m/s; they loop. Visible from frame `start` (fade by scale)."""
    mat = _alpha_emis("mat_" + name, color, 2.2, alpha)
    d = Vector(direction).normalized()
    span = max(region[i][1] - region[i][0] for i in range(3))
    period = max(4, int(span / speed * ctx.fps))
    objs = []
    for i in range(n):
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0), (thick, length, thick))
        o = S.obj("%s%d" % (name, i), S.mesh_from_bm(name, bm, [mat]), parent=parent)
        o.visible_shadow = False
        # orient the box's Y axis along d
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = Vector((0, 1, 0)).rotation_difference(d)
        p0 = Vector([rng.uniform(*region[k]) for k in range(3)])
        # move from the "upstream" face of the region to the "downstream" one
        a = p0 - d * span * 0.5
        b = p0 + d * span * 0.5
        ph = rng.randrange(period)
        kf(o, "location", 1 - ph, a, "LINEAR")
        kf(o, "location", 1 - ph + period, b, "LINEAR")
        for fc in _fcurves(o):
            fc.modifiers.new("CYCLES")
        if start > 1:
            o.scale = (0, 0, 0)
            kf(o, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            kf(o, "scale", start, Vector((1, 1, 1)), "CONSTANT")
        objs.append(o)
    return objs


def _fcurves(o):
    """F-curves of an object's action (Blender 5 layered actions)."""
    ad = o.animation_data
    if ad is None or ad.action is None:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except Exception:
        pass
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def ring_pulses(ctx, center, start, color=hexc("38e0c8"), count=3, gap=8, r1=12.0, life=24, name="ring", parent=None,
                rot=(0.0, 0.0, 0.0)):
    """Expanding fading rings (radio waves). Pure geometry, no text."""
    objs = []
    for k in range(count):
        m, sock = L.add_mat("%s_m%d" % (name, k), color, 0.0)
        bm = bmesh.new()
        r = bmesh.ops.create_circle(bm, cap_ends=False, segments=48, radius=1.0)
        me = S.mesh_from_bm("%s%d" % (name, k), bm, [m])
        o = S.obj("%s%d" % (name, k), me, center, rot, parent=parent)
        o.visible_shadow = False
        o.modifiers.new("solid", "WIREFRAME").thickness = 0.06
        f0 = start + k * gap
        kf(o, "scale", 1, Vector((0.01, 0.01, 0.01)), "CONSTANT")
        kf(o, "scale", f0, Vector((0.5, 0.5, 0.5)), "LINEAR")
        kf(o, "scale", f0 + life, Vector((r1, r1, r1)), "LINEAR")
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, f0, 4.0, "LINEAR")
        L.kf_socket(sock, f0 + life, 0.0, "LINEAR")
        objs.append(o)
    return objs


# ================================================================ helpers for shots
def _cam(ctx, loc, target, lens=30, parent=None, dof=None):
    cam = ctx.camera(loc, target=target, lens=lens)
    cam.data.clip_start = 1.0
    cam.data.clip_end = 16000.0
    if parent is not None:
        cam.parent = parent
        ctx.cam_target.parent = parent
    if dof is not None:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = dof[0]
        cam.data.dof.aperture_fstop = dof[1]
    return cam


def _cam_keys(ctx, keys, interp="BEZIER"):
    for f, c, t in keys:
        kf(ctx.cam, "location", f, Vector(c), interp)
        kf(ctx.cam_target, "location", f, Vector(t), interp)


def _track(name, keys, interp="LINEAR"):
    tr = L.link(bpy.data.objects.new(name, None))
    for f, loc in keys:
        kf(tr, "location", f, Vector(loc), interp)
    return tr


def glide_alt(y):
    """Altitude (m) of a 3-degree approach to the 300 m aiming point of runway 34 (threshold at y = 0)."""
    return 0.056 * (300.0 - y) + 0.3


def _ground_marker(name, track, keys_xy):
    """Empty on the ground under a moving object (for 2D measuring bars)."""
    e = L.link(bpy.data.objects.new(name, None))
    for f, (x, y) in keys_xy:
        kf(e, "location", f, Vector((x, y, 0.3)), "LINEAR")
    return e


def _world(ctx, p, sun_az=-35.0):
    S.daylight(ctx, p.get("sun_az", sun_az), p.get("sun_elev", 40.0), hdri=p.get("hdri", True))
    S.build_world(ctx)


# ================================================================ BUILDERS (plane crash, v2)
def b_airport_plate(ctx, p):
    """Background plate (rendered at half res, blurred by the overlay) for the flight-profile graph beats:
    an airliner climbing out of the persistent airport, seen from the air."""
    T = ctx.frames
    _world(ctx, p)
    root, parts = make_airliner_v2(ctx, "al")
    gear_to(parts, 1, 2, down=False)
    view = p.get("view", "climb_a")
    v = 80.0 / ctx.fps
    y0 = 1500.0 if view == "climb_a" else 2100.0
    tr = _track("al_track", [(1, (0, y0, 120 + (y0 - 1500) * 0.14)), (T, (0, y0 + v * T, 120 + (y0 + v * T - 1500) * 0.14))])
    root.parent = tr
    root.rotation_euler = (math.radians(8), 0, 0)
    if view == "climb_a":
        _cam(ctx, (-160, y0 - 260, 60), (0, y0 + 60, 140), lens=32)
        _cam_keys(ctx, [(1, (-160, y0 - 260, 60), (0, y0 + 60, 140)),
                        (T, (-200, y0 - 120, 110), (0, y0 + v * T + 40, 120 + (v * T) * 0.14 + 20))])
    else:
        c0 = (260, y0 + 700, 330)
        _cam(ctx, c0, (0, y0 + 200, 150), lens=30)
        _cam_keys(ctx, [(1, c0, (0, y0 + 150, 150)), (T, (230, y0 + 760, 360), (0, y0 + v * T, 150 + v * T * 0.14))])
    S.anchor(ctx, "plane", root, (0, 0, 2.5))


def b_altitude_margin_v2(ctx, p):
    """Side-on, long-lens view (so screen height ~ altitude): a high airliner (lots of room below it) and one on short
    final just above the ground (little room). The overlay draws the teal / red height bars between the anchors."""
    T = ctx.frames
    _world(ctx, p, sun_az=-120.0)
    lv = 45.0 / ctx.fps
    ly0 = p.get("low_y", -400.0)
    lo_root, lp = make_airliner_v2(ctx, "lo")
    flaps_to(lp, 1, 2, 1.0, 1.0)
    lo = _track("lo_track", [(1, (0, ly0, glide_alt(ly0) + 3.8)), (T, (0, ly0 + lv * T, glide_alt(ly0 + lv * T) + 3.8))])
    lo_root.parent = lo
    lo_root.rotation_euler = (math.radians(2.5), 0, 0)
    hi_root, hp = make_airliner_v2(ctx, "hi")
    gear_to(hp, 1, 2, down=False)
    hz, dy = p.get("high_z", 150.0), p.get("high_dy", 120.0)
    hi = _track("hi_track", [(1, (0, ly0 + dy, hz)), (T, (0, ly0 + dy + lv * T, hz))])
    hi_root.parent = hi
    hg = _ground_marker("hi_g", hi, [(1, (0, ly0 + dy)), (T, (0, ly0 + dy + lv * T))])
    lg = _ground_marker("lo_g", lo, [(1, (0, ly0)), (T, (0, ly0 + lv * T))])
    S.anchor(ctx, "high", hi_root, (0, 0, -2.4))
    S.anchor(ctx, "high_g", hg)
    S.anchor(ctx, "low", lo_root, (0, 0, -3.9))
    S.anchor(ctx, "low_g", lg)
    dist, hc, lens = p.get("dist", 650.0), p.get("cam_z", 80.0), p.get("lens", 32.0)
    yc = dy * 0.5
    c0 = (-dist, ly0 + yc, hc)
    _cam(ctx, c0, (0, ly0 + yc, hc), lens=lens)
    _cam_keys(ctx, [(1, c0, (0, ly0 + yc, hc)), (T, (-dist, ly0 + yc + lv * T, hc), (0, ly0 + yc + lv * T, hc))],
              "LINEAR")
    ctx.cam.data.clip_end = 20000.0
    ctx.cam.data.clip_start = 8.0          # camera is >= 600 m from everything: better depth precision


def b_cockpit_workload_v2(ctx, p):
    """Airliner on approach seen from slightly below / ahead: speed streaks, flaps extend, gear drops, radio rings
    from the cockpit on four cue words. Sky fills the top of the frame (captions), suburbs below."""
    T = ctx.frames
    _world(ctx, p)
    root, parts = make_airliner_v2(ctx, "al", gear_down=False)
    v = 72.0 / ctx.fps
    y0 = p.get("y0", -2200.0)
    tr = _track("al_track", [(1, (0, y0, glide_alt(y0))), (T, (0, y0 + v * T, glide_alt(y0 + v * T)))])
    root.parent = tr
    root.rotation_euler = (math.radians(2.0), 0, 0)
    cues = p.get("cues", ["speed", "flaps", "gear", "radio"])
    fs = [ctx.word_time(c, 0.2 + 0.2 * i) for i, c in enumerate(cues)]
    rng = random.Random(7)
    streaks(ctx, tr, 70, ((-30, 30), (-60, 60), (-14, 16)), (0, -1, 0), 9.0, 150.0, rng, start=fs[0], alpha=0.35,
            name="spd")
    flaps_to(parts, fs[1], fs[1] + 36, 0.0, 1.0)
    gear_to(parts, fs[2], fs[2] + 40, down=True)
    ring_pulses(ctx, (0, 16.5, 1.6), fs[3], count=4, gap=7, r1=9.0, life=26, parent=root, rot=(math.radians(90), 0, 0),
                name="radio")
    c0 = (-34.0, 44.0, -7.0)
    _cam(ctx, c0, (0, 4.0, 0.5), lens=30, parent=tr)
    _cam_keys(ctx, [(1, c0, (0, 4.0, 0.5)), (T, (-30.0, 30.0, -9.5), (0, 0.0, -0.5))])
    S.anchor(ctx, "plane", root, (0, 2, 2.5))


def b_crosswind_v2(ctx, p):
    """Short final in a gusty crosswind: the airliner is crabbed into the wind (wind streaks blow across from the
    left), dips briefly on the wind-shear cue, and a light aircraft waits on the taxiway (amber rings on the
    traffic cue). Normal, stable approach; it never touches down in this shot."""
    T = ctx.frames
    _world(ctx, p)
    root, parts = make_airliner_v2(ctx, "al")
    flaps_to(parts, 1, 2, 1.0, 1.0)
    v = 66.0 / ctx.fps
    y0 = p.get("y0", -820.0)
    keys = []
    f_sh = ctx.word_time(p.get("shear_cue", "shear"), 0.45)
    for f in range(1, T + 1, 3):
        y = y0 + v * f
        dip = 0.0
        if f > f_sh:
            u = (f - f_sh) / ctx.fps
            dip = -4.0 * math.sin(min(math.pi, u * 1.8)) if u < 1.75 else 0.0
        keys.append((f, (6.0 * math.sin(f / 37.0), y, glide_alt(y) + 4.0 + dip)))
    tr = _track("al_track", keys, "BEZIER")
    root.parent = tr
    for f in range(1, T + 1, 6):
        t = f / ctx.fps
        kf(root, "rotation_euler", f, Vector((math.radians(2.5), math.radians(3.5 * math.sin(t * 1.7)),
                                              math.radians(-11.0))), "BEZIER")
    rng = random.Random(11)
    f_w = ctx.word_time(p.get("wind_cue", "crosswinds"), 0.1)
    streaks(ctx, tr, 110, ((-90, 70), (-120, 140), (-25, 35)), (1, 0.08, -0.02), 16.0, 55.0, rng, start=1,
            alpha=0.32, name="wind")
    streaks(ctx, tr, 40, ((-25, 25), (-30, 40), (0, 45)), (0.25, 0, -1), 9.0, 60.0, rng, start=f_sh, alpha=0.3,
            name="shear")
    gp = S.make_plane_v2(ctx, "gplane", spin=True, strobes=False)
    gp.location = (S.TWY_X, 330.0, 1.55 + 0.26)
    gp.rotation_euler = (math.radians(-4), 0, math.radians(90))
    f_t = ctx.word_time(p.get("traffic_cue", "traffic"), 0.75)
    ring_pulses(ctx, (S.TWY_X, 330.0, 2.0), f_t, color=hexc("ffb030"), count=3, gap=9, r1=22.0, life=30, name="trf")
    c0 = (-70.0, -95.0, 4.0)
    _cam(ctx, c0, (0, 0, 0), lens=34, parent=tr)
    _cam_keys(ctx, [(1, c0, (0, 10, 0)), (T, (-60.0, -105.0, 9.0), (10, 60, -6))])
    S.anchor(ctx, "plane", root, (0, 0, 2.5))
    S.anchor(ctx, "traffic", gp, (0, 0, 1.2))


def _rope_mat(name, glow_col, sock_holder):
    """Rope: dark braided base + emission (keyframed 0 -> glow) for the teal / red highlights."""
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc("3a3128")
    p.inputs["Roughness"].default_value = 0.7
    p.inputs["Emission Color"].default_value = glow_col
    p.inputs["Emission Strength"].default_value = 0.0
    sock_holder.append(p.inputs["Emission Strength"])
    S._finish(m, p.outputs[0])
    return m


def _mannequin(ctx, name):
    """Stylised faceless walker (red top, grey trousers, light-grey skin like a mannequin) with a balance pole.
    Returns (root, legs) ; root origin at the feet."""
    root = L.link(bpy.data.objects.new(name, None))
    skin = S.pbr("mq_skin", hexc("d9d4cc"), 0.5, var=0)
    top = S.pbr("mq_top", hexc("c8302f"), 0.6, var=0.04)
    trs = S.pbr("mq_trousers", hexc("3b4456"), 0.7, var=0.04)
    pole_m = S.pbr("mq_pole", hexc("2b2d31"), 0.4, 0.3, var=0)
    tip_m = S.pbr("mq_tip", hexc("e0b030"), 0.5, var=0)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 1.32), (0.22, 0.15, 0.36), 0, 16, 10)      # torso
    S._ellipsoid(bm, (0, 0, 1.03), (0.2, 0.14, 0.14), 1, 12, 8)        # hips
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [top, trs], smooth=True), parent=root)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 1.86), (0.12, 0.13, 0.15), 0, 16, 10)      # head
    S._ellipsoid(bm, (0, 0, 1.69), (0.05, 0.05, 0.06), 0, 8, 6)        # neck
    for sx in (-1, 1):                                                  # arms out to the pole
        S._ellipsoid(bm, (sx * 0.34, 0.12, 1.5), (0.17, 0.06, 0.06), 0, 10, 6)
        S._ellipsoid(bm, (sx * 0.47, 0.3, 1.45), (0.06, 0.16, 0.06), 0, 10, 6)
    S.obj(name + "_skin", S.mesh_from_bm(name + "_skin", bm, [skin], smooth=True), parent=root)
    legs = []
    for sx in (-1, 1):
        hip = L.link(bpy.data.objects.new(name + "_hip%d" % sx, None))
        hip.parent = root
        hip.location = (sx * 0.1, 0, 0.98)
        bm = bmesh.new()
        S._ellipsoid(bm, (0, 0, -0.47), (0.08, 0.08, 0.48), 0, 10, 8)
        S._ellipsoid(bm, (0, 0.06, -0.95), (0.06, 0.13, 0.04), 1, 10, 6)
        S.obj(name + "_leg%d" % sx, S.mesh_from_bm(name + "_leg", bm, [trs, pole_m], smooth=True), parent=hip)
        legs.append(hip)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.025, radius2=0.025, depth=7.0)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 3.5, 0, 0), (0.07, 0.07, 0.07), 1, 8, 6)
    pole = S.obj(name + "_pole", S.mesh_from_bm(name + "_pole", bm, [pole_m, tip_m], smooth=True), (0, 0.42, 1.45),
                 parent=root)
    pole.rotation_euler = (0, 0, 0)
    return root, legs, pole


def b_tightrope_v2(ctx, p):
    """Metaphor: a walker crosses a rope between two wooden platforms in a sunny meadow (trees, hills, HDRI sky).
    Wobbly when stepping on / off, steady in the middle. Rope middle glows teal on `middle_cue`, both ends red
    on `on_cue`. Anchors: mid (rope middle), end (far platform), walker."""
    T = ctx.frames
    rng = random.Random(5)
    S.daylight(ctx, p.get("sun_az", -50.0), 40.0, hdri=p.get("hdri", True))
    L.fog(0.00035, S.HAZE, start=120.0)
    S.plane_obj("ground", 20000, 20000, (0, 0, 0), S.ground_mat())
    S.plane_obj("meadow", 400, 300, (0, 40, 0.05), S.lawn_mat("meadow_v2", hexc("7a9a50"), stripes=False))
    tree_t = S.tree_templates(rng)
    pts = []
    for _ in range(260):
        x, y = rng.uniform(-700, 700), rng.uniform(60, 1600)
        if abs(x) < 40 and y < 120:
            continue
        pts.append((x, y))
    for _ in range(40):
        pts.append((rng.uniform(-200, 200), rng.uniform(-260, -60)))
    for _ in range(70):                       # a tree line close behind the rope
        x, y = rng.uniform(-90, 90), rng.uniform(22, 70)
        pts.append((x, y))
    S.scatter(tree_t, pts, rng, prefix="tree")
    S.build_hills(rng)
    # platforms: 4 timber legs + deck + rail, at x = -/+ SPAN/2
    span, h = 24.0, 10.0
    wood = S.pbr("timber_v2", hexc("8a6440"), 0.75, var=0.12, var_scale=2.0, bump=0.1)
    deck = S.pbr("deck_v2", hexc("a07a50"), 0.7, var=0.1, var_scale=3.0, bump=0.1)
    for sx in (-1, 1):
        bm = bmesh.new()
        cx = sx * (span / 2 + 2.0)
        for dx in (-1.4, 1.4):
            for dy in (-1.4, 1.4):
                S.bm_box(bm, (cx + dx, dy, h / 2), (0.3, 0.3, h), 0)
        for z in (3.5, 7.0):
            S.bm_box(bm, (cx, -1.4, z), (3.1, 0.15, 0.2), 0)
            S.bm_box(bm, (cx, 1.4, z), (3.1, 0.15, 0.2), 0)
        S.bm_box(bm, (cx, 0, h + 0.1), (3.6, 3.6, 0.25), 1)
        S.bm_box(bm, (cx + sx * 1.7, 0, h + 0.7), (0.12, 3.4, 0.1), 0)
        S.obj("platform%d" % sx, S.mesh_from_bm("platform", bm, [wood, deck]))
    # rope: 3 segments (end, middle, end) with a slight sag
    socks_end, socks_mid = [], []
    m_end = _rope_mat("rope_end", hexc("ff3b3b"), socks_end)
    m_mid = _rope_mat("rope_mid", hexc("2ee6c8"), socks_mid)
    rz = h + 0.25
    sag = 0.6

    def rope_pt(u):
        return Vector((-span / 2 + span * u, 0, rz - sag * 4 * u * (1 - u)))
    for k, (ua, ub, m) in enumerate(((0.0, 0.25, m_end), (0.25, 0.75, m_mid), (0.75, 1.0, m_end))):
        cd = bpy.data.curves.new("rope%d" % k, "CURVE")
        cd.dimensions = "3D"
        cd.bevel_depth = 0.045
        cd.bevel_resolution = 3
        sp = cd.splines.new("POLY")
        n = 12
        sp.points.add(n)
        for i in range(n + 1):
            v = rope_pt(ua + (ub - ua) * i / n)
            sp.points[i].co = (v.x, v.y, v.z, 1)
        cd.materials.append(m)
        L.link(bpy.data.objects.new("rope%d" % k, cd))
    f_mid = ctx.word_time(p.get("middle_cue", "middle"), 0.2)
    f_on = ctx.word_time(p.get("on_cue", "stepping"), 0.45)
    for sock in socks_mid:
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, f_mid, 0.0, "LINEAR")
        L.kf_socket(sock, f_mid + 10, 3.5, "LINEAR")
    for sock in socks_end:
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, f_on, 0.0, "LINEAR")
        L.kf_socket(sock, f_on + 10, 4.0, "LINEAR")
    # walker: from u 0.03 to 0.97, slow near the ends; wobble amplitude high near the ends
    walker, legs, pole = _mannequin(ctx, "walker")
    for f in range(1, T + 2, 2):
        g = (f - 1) / float(T)
        u = 0.04 + 0.92 * (0.5 - 0.5 * math.cos(math.pi * g))
        pos = rope_pt(u)
        endness = max(0.0, 1.0 - min(u, 1 - u) / 0.22)
        t = f / ctx.fps
        wob = (0.08 + 0.95 * endness) * math.sin(t * 5.3) * math.radians(9)
        kf(walker, "location", f, Vector((pos.x, pos.y, pos.z + 0.045)), "BEZIER")
        kf(walker, "rotation_euler", f, Vector((0, wob, -math.pi / 2)), "BEZIER")
        kf(pole, "rotation_euler", f, Vector((0, -wob * 1.6, 0)), "BEZIER")
        for i, hip in enumerate(legs):
            kf(hip, "rotation_euler", f, Vector((math.radians(16) * math.sin(t * 4.2 + i * math.pi), 0, 0)), "BEZIER")
    S.anchor(ctx, "mid", L.link(bpy.data.objects.new("mid_anchor", None)), rope_pt(0.5) + Vector((0, 0, 0.1)))
    S.anchor(ctx, "end", L.link(bpy.data.objects.new("end_anchor", None)), Vector((span / 2 + 2.0, 0, h + 0.3)))
    S.anchor(ctx, "walker", walker, (0, 0, 2.1))
    # camera follows the walker (lagging a little), slightly below the rope so the sky sits behind the captions
    for f in range(1, T + 2, 8):
        g = (f - 1) / float(T)
        u = 0.04 + 0.92 * (0.5 - 0.5 * math.cos(math.pi * g))
        wx = rope_pt(u).x
        if f == 1:
            _cam(ctx, (wx * 0.7, -24.0, 6.5), (wx * 0.85, 0, h + 0.4), lens=p.get("lens", 27))
        kf(ctx.cam, "location", f, Vector((wx * 0.7, -24.0, 6.5)), "BEZIER")
        kf(ctx.cam_target, "location", f, Vector((wx * 0.85, 0, h + 0.4)), "BEZIER")


def _area(name, loc, size, energy, color=(1.0, 0.97, 0.92), rot=(0, 0, 0), shape="RECTANGLE", size_y=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.color = color
    d.shape = shape
    d.size = size
    if size_y is not None:
        d.size_y = size_y
    o = L.link(bpy.data.objects.new(name, d))
    o.location = loc
    o.rotation_euler = rot
    return o


def b_cabin_v2(ctx, p):
    """Bright airliner cabin interior (3+3 seats, aisle, overhead bins, LED cove light, windows with daylight).
    On `sign_cue` the FASTEN SEATBELT pictograms above every row light up front-to-back (icon only, no text).
    Slow dolly up the aisle. No people."""
    T = ctx.frames
    # interior: neutral soft world (an outdoor HDRI's brown ground would tint the ceiling); daylight comes in
    # through the emissive windows + window-side area lights
    w = bpy.data.worlds.new("cabin_world")
    ctx.scene.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.62, 0.68, 0.78, 1.0)
    bg.inputs["Strength"].default_value = 0.35
    ctx.scene.view_settings.exposure = p.get("exposure", 0.0)
    rows, pitch = 22, 0.82
    length = rows * pitch + 4.0
    y0 = -2.0
    wall = S.pbr("cab_wall", hexc("eceae6"), 0.55, var=0.02)
    ceil_m = S.emis("cab_ceiling", hexc("f4f6fa"), 1.5)
    carpet = S.pbr("cab_carpet", hexc("3b4a6b"), 0.95, var=0.12, var_scale=6.0, bump=0.15)
    bin_m = S.pbr("cab_bins", hexc("f0efeb"), 0.35, var=0.01)
    fabric = S.pbr("cab_fabric", hexc("24386a"), 0.85, var=0.1, var_scale=8.0, bump=0.2)
    shell = S.pbr("cab_seatshell", hexc("d8dadd"), 0.4, var=0)
    head = S.pbr("cab_headrest", hexc("f2f2ef"), 0.8, var=0.02)
    belt = S.pbr("cab_belt", hexc("3a3d44"), 0.6, var=0)
    floor_side = S.pbr("cab_floor", hexc("8a8d92"), 0.6, var=0.03)
    win_m = S.emis("cab_window", hexc("cfe3ff"), 2.4)
    led = S.emis("cab_led", hexc("dfe9ff"), 3.0)
    # shell: floor, side walls (vertical lower + curved upper), ceiling
    bm = bmesh.new()
    S.bm_box(bm, (0, y0 + length / 2, -0.05), (3.9, length, 0.1), 0)
    S.bm_box(bm, (0, y0 + length / 2, 0.005), (0.62, length, 0.01), 1)          # aisle carpet strip
    S.obj("cab_floor", S.mesh_from_bm("cab_floor", bm, [floor_side, carpet]))
    bm = bmesh.new()
    prof = [(1.92, 0.0), (1.97, 0.6), (1.98, 1.2), (1.9, 1.62), (1.62, 2.02)]
    for sx in (-1, 1):
        for (xa, za), (xb, zb) in zip(prof[:-1], prof[1:]):
            vs = [bm.verts.new((sx * xa, y0, za)), bm.verts.new((sx * xb, y0, zb)),
                  bm.verts.new((sx * xb, y0 + length, zb)), bm.verts.new((sx * xa, y0 + length, za))]
            bm.faces.new(vs)
    S.bm_box(bm, (0, y0 + length / 2, 2.16), (1.5, length, 0.06), 0)
    S.obj("cab_walls", S.mesh_from_bm("cab_walls", bm, [wall]))
    bm = bmesh.new()
    S.bm_box(bm, (0, y0 + length / 2, 2.2), (2.2, length, 0.04), 0)
    S.bm_box(bm, (0, y0 + length / 2, 2.32), (4.2, length + 0.4, 0.06), 0)      # closes the shell
    S.obj("cab_ceiling", S.mesh_from_bm("cab_ceiling", bm, [ceil_m]))
    bm = bmesh.new()
    S.bm_box(bm, (0, y0 + length + 0.1, 1.15), (4.2, 0.2, 2.5), 0)
    S.bm_box(bm, (0, y0 - 0.6, 1.15), (4.2, 0.2, 2.5), 0)
    S.obj("cab_ends", S.mesh_from_bm("cab_ends", bm, [S.pbr("cab_bulkhead", hexc("d9dde4"), 0.5, var=0.02)]))
    # windows (bright daylight panes, rounded) and LED cove strips
    bm = bmesh.new()
    for r in range(rows + 2):
        y = y0 + 1.5 + r * pitch
        for sx in (-1, 1):
            S._ellipsoid(bm, (sx * 1.955, y, 1.08), (0.02, 0.17, 0.24), 0, 16, 8)
    S.obj("cab_windows", S.mesh_from_bm("cab_windows", bm, [win_m], smooth=True))
    bm = bmesh.new()
    for sx in (-1, 1):
        S.bm_box(bm, (sx * 0.78, y0 + length / 2, 2.1), (0.05, length, 0.03), 0)
    S.obj("cab_led", S.mesh_from_bm("cab_led", bm, [led]))
    # overhead bins (rounded boxes with subsurf), passenger service units with the seatbelt pictogram
    for sx in (-1, 1):
        bm = bmesh.new()
        S.bm_box(bm, (sx * 1.38, y0 + length / 2, 1.82), (0.72, length - 0.2, 0.46), 0)
        o = S.obj("cab_bins%d" % sx, S.mesh_from_bm("cab_bins", bm, [bin_m]))
        bv = o.modifiers.new("bev", "BEVEL")
        bv.width = 0.08
        bv.segments = 4
        bm = bmesh.new()
        for r in range(rows):
            y = y0 + 2.4 + r * pitch
            for k in range(1, 8):  # bin door seams
                pass
            S.bm_box(bm, (sx * 1.38, y - 0.4, 1.6), (0.7, 0.012, 0.02), 0)
        S.obj("cab_seams%d" % sx, S.mesh_from_bm("cab_seams", bm, [S.pbr("cab_seam", hexc("b9bbbf"), 0.5, var=0)]))
    f_sign = ctx.word_time(p.get("sign_cue", "seatbelt"), 0.15)
    icon_m = L.emissive("cab_sign_icon", hexc("ffd27a"), 0.0, 0.0)
    sock = icon_m.node_tree.nodes.get("Emission").inputs["Strength"]
    L.kf_socket(sock, 1, 0.05, "CONSTANT")
    L.kf_socket(sock, f_sign, 0.05, "LINEAR")
    L.kf_socket(sock, f_sign + 4, 9.0, "LINEAR")
    L.kf_socket(sock, f_sign + 14, 5.0, "LINEAR")
    panel = S.pbr("cab_psu", hexc("2b2f36"), 0.35, var=0)
    bm_p, bm_i = bmesh.new(), bmesh.new()
    for r in range(rows):
        y = y0 + 2.4 + r * pitch
        for sx in (-1, 1):
            x = sx * 0.98
            # sign panel hanging under the bin edge, facing aft (towards the camera)
            S.bm_box(bm_p, (x, y, 1.52), (0.24, 0.03, 0.12), 0)
            # pictogram on the aft face: belt loop (two straps + buckle)
            yy = y - 0.017
            S.bm_box(bm_i, (x - 0.055, yy, 1.52), (0.07, 0.004, 0.022), 0)
            S.bm_box(bm_i, (x + 0.055, yy, 1.52), (0.07, 0.004, 0.022), 0)
            S.bm_box(bm_i, (x, yy, 1.52), (0.034, 0.004, 0.05), 0)
            S.bm_box(bm_i, (x - 0.095, yy, 1.545), (0.018, 0.004, 0.05), 0)
            S.bm_box(bm_i, (x + 0.095, yy, 1.545), (0.018, 0.004, 0.05), 0)
    S.obj("cab_psu", S.mesh_from_bm("cab_psu", bm_p, [panel]))
    S.obj("cab_icons", S.mesh_from_bm("cab_icons", bm_i, [icon_m]))
    # seats: one template mesh (3-seat unit), linked per row and side
    bm = bmesh.new()
    for k in range(3):
        x = 0.25 + k * 0.5
        S.bm_box(bm, (x, 0.0, 0.46), (0.46, 0.5, 0.13), 0)            # cushion
        S.bm_box(bm, (x, -0.24, 0.86), (0.46, 0.12, 0.72), 0)         # back
        S.bm_box(bm, (x, -0.2, 1.12), (0.4, 0.06, 0.22), 2)            # headrest cover
        S.bm_box(bm, (x, -0.31, 0.78), (0.44, 0.03, 0.62), 1)         # back shell
        S.bm_box(bm, (x, 0.1, 0.535), (0.36, 0.05, 0.012), 3)         # belt
    for k in range(4):
        S.bm_box(bm, (0.0 + k * 0.5, -0.02, 0.62), (0.05, 0.46, 0.06), 1)   # armrests
    S.bm_box(bm, (0.75, -0.05, 0.2), (1.4, 0.06, 0.4), 1)              # leg frame
    seat_me = S.mesh_from_bm("seat3", bm, [fabric, shell, head, belt])
    seat_tpl = S.obj("seat_tpl", seat_me, (0, -50, 0))
    bv = seat_tpl.modifiers.new("bev", "BEVEL")
    bv.width = 0.035
    bv.segments = 3
    for r in range(rows):
        y = y0 + 2.4 + r * pitch
        for sx in (-1, 1):
            o = seat_tpl.copy()
            L.link(o)
            o.location = (0.3 if sx > 0 else -1.8, y, 0)
    bpy.data.objects.remove(seat_tpl)
    # lights: soft ceiling area lights + window daylight fill
    for k in range(6):
        y = y0 + 2 + k * (length - 4) / 5
        _area("cab_l%d" % k, (0, y, 2.12), 1.0, 120.0, (1.0, 0.97, 0.93), shape="RECTANGLE", size_y=2.5)
    for sx in (-1, 1):
        _area("cab_win%d" % sx, (sx * 1.7, y0 + length / 2, 1.1), 0.6, 260.0, (0.85, 0.92, 1.0),
              rot=(0, math.radians(sx * 90), 0), size_y=length)
    c0 = (0.0, y0 + 0.4, 1.25)
    _cam(ctx, c0, (0.0, y0 + 8.0, 1.45), lens=p.get("lens", 17))
    _cam_keys(ctx, [(1, c0, (0.0, y0 + 8.0, 1.35)), (T, (0.0, y0 + 3.4, 1.22), (0.0, y0 + 10.0, 1.62))])
    ctx.cam.data.clip_start = 0.05
    ctx.cam.data.clip_end = 200.0


def b_airport_outro(ctx, p):
    """Closing shot: an airliner takes off from the persistent airport (rotation, normal climb, gear up) while the
    camera cranes up from the apron to a wide view of the field, the suburbs and the city."""
    T = ctx.frames
    _world(ctx, p)
    root, parts = make_airliner_v2(ctx, "al")
    flaps_to(parts, 1, 2, 0.45, 0.45)
    # take-off roll from y 250 (55 m/s, +2.5 m/s^2), lift-off at 78 m/s, then a normal climb (pitch up to 9 deg)
    keys, rot = [], []
    y, v, z = 250.0, 55.0, 4.1
    pitch = 0.0
    for f in range(1, T + 1):
        dt = 1.0 / ctx.fps
        if v < 78.0:
            v += 2.5 * dt
        else:
            v += 0.6 * dt
            pitch = min(9.0, pitch + 4.5 * dt)
            z += v * math.sin(math.radians(pitch)) * dt
        y += v * dt
        if f % 3 == 1 or f == T:
            keys.append((f, (0.0, y, z)))
            rot.append((f, pitch))
    tr = _track("al_track", keys, "LINEAR")
    root.parent = tr
    for f, pt in rot:
        kf(root, "rotation_euler", f, Vector((math.radians(pt), 0, 0)), "LINEAR")
    f_up = next((f for f, pt in rot if pt >= 8.9), T // 2)
    gear_to(parts, min(T - 30, f_up + 10), min(T - 1, f_up + 60), down=False)
    # camera: low beside the runway, then cranes up and back while following the aircraft
    pos = dict(keys)
    def at(f):
        k = min(pos, key=lambda q: abs(q - f))
        return Vector(pos[k])
    cam_path = p.get("cam_path", [(0.0, (-55.0, 420.0, 4.5)), (0.4, (-100.0, 520.0, 40.0)), (1.0, (-420.0, 150.0, 300.0))])
    first = True
    for f in list(range(1, T + 1, 15)) + [T]:
        g = (f - 1) / float(max(1, T - 1))
        for (g0, c0), (g1, c1) in zip(cam_path[:-1], cam_path[1:]):
            if g0 <= g <= g1:
                u = (g - g0) / (g1 - g0)
                u = u * u * (3 - 2 * u)
                c = Vector(c0).lerp(Vector(c1), u)
                break
        tgt = at(f) + Vector((0, 20.0, 2.0))
        if first:
            _cam(ctx, tuple(c), tuple(tgt), lens=p.get("lens", 26))
            ctx.cam.data.clip_start = 2.5      # wide crane view: more depth precision for the far field
            first = False
        kf(ctx.cam, "location", f, c, "BEZIER")
        kf(ctx.cam_target, "location", f, tgt, "BEZIER")
    S.anchor(ctx, "plane", root, (0, 0, 2.5))


S.V2_BUILDERS.update({
    "airport_hook": b_airport_hook,
    "airport_plate": b_airport_plate,
    "altitude_margin_v2": b_altitude_margin_v2,
    "cockpit_workload_v2": b_cockpit_workload_v2,
    "crosswind_v2": b_crosswind_v2,
    "tightrope_v2": b_tightrope_v2,
    "cabin_v2": b_cabin_v2,
    "airport_outro": b_airport_outro,
})

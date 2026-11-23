"""v2 market builders ("stock market crash" episode): a bright financial-district plaza carved into the downtown of
the persistent river city (scene_lib_v2_city). The plaza holds a big index wall + two side screens (emissive chart
graphics only: candles, grid, lines; NO glyphs or numbers), a giant glowing 3D stock line, two marble stair
sculptures with glass elevators ("up by the stairs, down by the elevator"), a fountain with a gold "profits" pedestal,
and a long row of dominoes. Registers into scene_lib_v2.V2_BUILDERS.

Rules: no 3D text (all text / numbers = 2D overlays), no people, nothing distressing (the bubble pops into confetti).
Everything is keyframed analytically with seeded random draws (no physics), so a beat split into several render jobs
builds the identical scene in every job.

Plaza coordinates: P(dx, dy, z) around the plaza centre PC; north = +Y (towards the index wall), the sun is in the
south, so cameras stand in the south half and look north / sideways.
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc, kf
import scene_lib_v2_air as A
import scene_lib_v2_city as C

PLAZA = (-1025.0, -620.0, 525.0, 795.0)        # x0, x1, y0, y1: 3 x 2 city blocks left open
PC = ((PLAZA[0] + PLAZA[1]) / 2.0, (PLAZA[2] + PLAZA[3]) / 2.0)
PZ = 0.45                                       # top of the plaza paving

GREEN = hexc("2fe08a")
RED = hexc("ff3b3b")
TEAL = hexc("2ee6c8")


def P(dx, dy, z=0.0):
    return (PC[0] + dx, PC[1] + dy, z)


# ================================================================ materials
def paving_mat():
    name = "mk_paving"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    obj_v = S._coord(N, Lk, "Object")
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 3.0
    br.inputs["Row Height"].default_value = 1.5
    br.inputs["Mortar Size"].default_value = 0.03
    br.inputs["Color1"].default_value = hexc("ddd5c6")
    br.inputs["Color2"].default_value = hexc("cfc6b5")
    br.inputs["Mortar"].default_value = hexc("9c968c")
    Lk.new(obj_v, br.inputs["Vector"])
    fac, _ = S._noise_var(N, Lk, obj_v, 0.08, 0.06, 6.0)
    cc = S._mul_col(N, Lk, br.outputs["Color"], fac)
    p.inputs["Roughness"].default_value = 0.7
    if not S.ph_detail(N, Lk, obj_v, "concrete_floor_02", p, cc, amount=0.35, hue=0.08, normal=0.3, rough_mix=0.3,
                       scale_mul=1.0):
        Lk.new(cc, p.inputs["Base Color"])
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def clear_glass_mat(name="mk_glass", color=hexc("cfe6f5"), alpha=0.22):
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    m.surface_render_method = "BLENDED"
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = 0.03
    p.inputs["Alpha"].default_value = alpha
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.02
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def bubble_mat():
    """Soap-bubble look in EEVEE: transparent centre, iridescent glossy rim (facing-based alpha + emission)."""
    name = "mk_bubble"
    if name in S._MV2:
        return S._MV2[name]
    m = bpy.data.materials.new(name)
    m.surface_render_method = "BLENDED"
    try:
        m.use_backface_culling = True
    except Exception:
        pass
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    out = N.get("Material Output")
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    stops = [(0.0, (0.62, 0.88, 1.0)), (0.3, (1.0, 0.62, 0.92)), (0.55, (1.0, 0.92, 0.45)),
             (0.75, (0.45, 1.0, 0.8)), (1.0, (0.6, 0.75, 1.0))]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], stops[0][1] + (1,)
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], stops[-1][1] + (1,)
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = col + (1,)
    Lk.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    em = N.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.1
    Lk.new(ramp.outputs["Color"], em.inputs["Color"])
    gl = N.new("ShaderNodeBsdfPrincipled")
    gl.inputs["Base Color"].default_value = (1, 1, 1, 1)
    gl.inputs["Roughness"].default_value = 0.02
    gl.inputs["Coat Weight"].default_value = 1.0
    gl.inputs["Coat Roughness"].default_value = 0.0
    add = N.new("ShaderNodeAddShader")
    Lk.new(em.outputs[0], add.inputs[0])
    Lk.new(gl.outputs[0], add.inputs[1])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 0.10
    mr.inputs["To Max"].default_value = 0.95
    pw = N.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 1.6
    Lk.new(lw.outputs["Facing"], pw.inputs[0])
    Lk.new(pw.outputs[0], mr.inputs["Value"])
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    Lk.new(mr.outputs["Result"], mix.inputs["Fac"])
    Lk.new(tr.outputs[0], mix.inputs[1])
    Lk.new(add.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], out.inputs["Surface"])
    S._MV2[name] = m
    return m


def screen_face_mat():
    """Lit LED panel: deep blue with a soft vertical glow gradient (reads as a screen, not a black hole)."""
    name = "mk_screen_face"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc("0d1d36")
    p.inputs["Roughness"].default_value = 0.2
    p.inputs["Coat Weight"].default_value = 0.6
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 10.0
    mr.inputs["From Max"].default_value = 70.0
    Lk.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexc("1d4a86")
    ramp.color_ramp.elements[1].color = hexc("0c1a33")
    Lk.new(mr.outputs["Result"], ramp.inputs["Fac"])
    Lk.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.0
    S._MV2[name] = S._finish(m, p.outputs[0])
    return S._MV2[name]


def _glow(name, color, strength=4.0):
    return L.emissive(name, color, strength, 0.2)


# ================================================================ mesh helpers
def _box(bm, x0, x1, y0, y1, z0, z1, mi=0):
    C._fast_box(bm, (x0 + x1) / 2, (y0 + y1) / 2, z0, x1 - x0, y1 - y0, z1 - z0, 0, mi)


def _tube(bm, pts, r, mi=0, seg=8):
    """Round tube along a polyline, faces ordered from start to end (Build modifier draws it in)."""
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = Vector(pts[max(0, i - 1)])
        b = Vector(pts[min(n - 1, i + 1)])
        t = (b - a).normalized()
        up = Vector((0, 1, 0)) if abs(t.y) < 0.9 else Vector((1, 0, 0))
        u = t.cross(up).normalized()
        v = t.cross(u).normalized()
        ring = []
        for k in range(seg):
            th = 2 * math.pi * k / seg
            ring.append(bm.verts.new(Vector(p) + (u * math.cos(th) + v * math.sin(th)) * r))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            j = (k + 1) % seg
            f = bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
            f.material_index = mi
            f.smooth = True


def _disc_y(bm, c, r, mi, seg=12, depth=0.06):
    """Thin disc facing +/-Y (domino pips)."""
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=depth)
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=c, verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mi


def _show(o, f_on=None, f_off=None):
    """Hard show/hide by scale (CONSTANT keys)."""
    s = o.scale.copy()
    if f_on is not None and f_on > 1:
        kf(o, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
        kf(o, "scale", f_on, s, "CONSTANT")
    if f_off is not None:
        if f_on is None or f_on <= 1:
            kf(o, "scale", 1, s, "CONSTANT")
        kf(o, "scale", max(2, f_off), Vector((0, 0, 0)), "CONSTANT")
    _set_const(o, "scale")


def _empty(name, loc):
    e = L.link(bpy.data.objects.new(name, None))
    e.location = loc
    return e


# ================================================================ the plaza
WALL = {"c": (0.0, 112.0), "w": 84.0, "h": 56.0, "z0": 12.0, "yaw": 0.0}
SIDE_L = {"c": (-118.0, 86.0), "w": 34.0, "h": 44.0, "z0": 10.0, "yaw": -22.0}
SIDE_R = {"c": (118.0, 86.0), "w": 34.0, "h": 44.0, "z0": 10.0, "yaw": 22.0}
LINE_Y = 80.0
FOUNTAIN = (-40.0, -22.0)
DROP_STAIRS = {"x0": 92.0, "y0": -14.0, "run": 3.2, "rise": 3.2, "depth": 16.0,
               "levels": list(range(1, 12)) + [0]}
LONG_STAIRS = {"x0": -192.0, "y0": 2.0, "run": 2.7, "rise": 1.45, "depth": 14.0,
               "levels": [1, 2, 3, 4, 5, 6, 7, 8, 5, 6, 7, 8, 9, 10, 11, 12, 13, 10, 11, 12, 13, 14, 15, 16, 17, 18,
                          16, 17, 18, 19, 20, 21, 22]}
DOMINO_PATH = [(-100.0, -90.0), (-60.0, -102.0), (-10.0, -94.0), (35.0, -102.0), (80.0, -114.0)]


def _walk(n, rng, drift=0.55, vol=1.0):
    v, out = 0.0, []
    for _ in range(n):
        o = v
        v += drift + rng.uniform(-vol, vol)
        out.append((o, v))
    return out


def make_screen(ctx, name, spec, seed, flip_f=None, state="up", tail=7):
    """Free-standing LED screen on two pillars facing the camera side (-Y, then yawed). Shows a candle chart
    (emissive boxes) + grid. state 'up': rising candles; 'down': the last `tail` candles fall in red;
    flip_f: switch from 'up' to 'down' at that frame (red candles appear one by one)."""
    cx, cy = spec["c"]
    w, h, z0 = spec["w"], spec["h"], spec["z0"]
    root = _empty(name, P(cx, cy, PZ))
    root.rotation_euler = (0, 0, math.radians(spec["yaw"]))
    metal = S.pbr("mk_frame", hexc("2c3139"), 0.35, metal=0.7, var=0.02)
    face = screen_face_mat()
    grid = _glow("mk_grid", hexc("3d6aa8"), 1.4)
    bm = bmesh.new()
    for sx in (-1, 1):                                   # pillars
        _box(bm, sx * w * 0.3 - 1.6, sx * w * 0.3 + 1.6, 0.6, 3.8, 0.0, z0 + 2, 0)
    _box(bm, -w / 2 - 1.2, w / 2 + 1.2, 0.0, 2.2, z0 - 1.2, z0 + h + 1.2, 0)      # frame
    _box(bm, -w / 2, w / 2, -0.15, 0.0, z0, z0 + h, 1)                              # face
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [metal, face]), parent=root)
    bm = bmesh.new()
    for k in range(1, 5):
        z = z0 + h * k / 5
        _box(bm, -w / 2 + 1, w / 2 - 1, -0.3, -0.18, z - 0.12, z + 0.12)
    S.obj(name + "_grid", S.mesh_from_bm(name + "_grid", bm, [grid]), parent=root)
    rng = random.Random(seed)
    n = 22
    walk = _walk(n, rng)
    if state == "down" or flip_f:
        last = walk[n - tail - 1][1]
        dn = []
        v = last
        for k in range(tail):
            o = v
            v -= rng.uniform(1.2, 2.6) * (1.6 if k < 3 else 1.0)
            dn.append((o, v))
        walk_dn = walk[:n - tail] + dn
    else:
        walk_dn = walk
    allv = [x for ab in walk + walk_dn for x in ab]
    lo, hi = min(allv) - 1.0, max(allv) + 1.0

    def zz(v):
        return z0 + h * 0.1 + h * 0.8 * (v - lo) / (hi - lo)
    cw = w * 0.9 / n
    green, red = _glow("mk_candle_g", GREEN, 3.0), _glow("mk_candle_r", RED, 3.5)

    def candle(bm, k, o, c, mi):
        x = -w * 0.45 + cw * (k + 0.5)
        a, b = sorted((zz(o), zz(c)))
        b = max(b, a + 0.6)
        _box(bm, x - cw * 0.3, x + cw * 0.3, -0.45, -0.2, a, b, mi)
        _box(bm, x - 0.12, x + 0.12, -0.4, -0.25, a - 0.9, b + 0.9, mi)
    bm = bmesh.new()
    split = n - tail if (state == "down" or flip_f) else n
    for k in range(split):
        o, c = walk[k]
        candle(bm, k, o, c, 0 if c >= o else 1)
    S.obj(name + "_c0", S.mesh_from_bm(name + "_c0", bm, [green, red]), parent=root)
    if split < n:
        if flip_f or state == "up":
            bm = bmesh.new()
            for k in range(split, n):
                o, c = walk[k]
                candle(bm, k, o, c, 0 if c >= o else 1)
            up = S.obj(name + "_cup", S.mesh_from_bm(name + "_cup", bm, [green, red]), parent=root)
            if flip_f:
                _show(up, None, flip_f)
        if flip_f or state == "down":
            for j, k in enumerate(range(split, n)):
                bm = bmesh.new()
                o, c = walk_dn[k]
                candle(bm, k, o, c, 1)
                o_ = S.obj("%s_cdn%d" % (name, k), S.mesh_from_bm("%s_cdn%d" % (name, k), bm, [green, red]),
                           parent=root)
                if flip_f:
                    _show(o_, flip_f + 3 * j)
    return root


def stock_line_pts(drop=True):
    """Giant 3D line in front of the index wall: a long slow climb, then (drop) a steep fall."""
    rng = random.Random(7)
    pts, x, z = [], -48.0, 16.0
    while x < 26.0:
        pts.append(P(x, LINE_Y, z))
        x += 3.0
        z += 1.15 + rng.uniform(-1.6, 1.4)
    top = len(pts)
    if drop:
        for k in range(1, 8):
            pts.append(P(x + (k - 1) * 2.6, LINE_Y, z - [2, 5, 9, 12, 15, 17, 18][k - 1] * 1.1))
    return pts, top


def make_stock_line(ctx, f_rise=None, rise_frames=90, f_drop=None, state="down"):
    """state 'up': only the climb; 'down': climb + red fall; f_rise / f_drop animate the draw-in."""
    pts, top = stock_line_pts(True)
    rise, fall = pts[:top], pts[top - 1:]
    bm = bmesh.new()
    _tube(bm, rise, 1.1, 0, 10)
    o = S.obj("mk_line_up", S.mesh_from_bm("mk_line_up", bm, [_glow("mk_line_g", hexc("35f0b0"), 4.0)], smooth=True))
    o.visible_shadow = False
    if f_rise is not None:
        C.draw_in(o, f_rise, f_rise + rise_frames)
    if state == "down" or f_drop is not None:
        bm = bmesh.new()
        _tube(bm, fall, 1.25, 0, 10)
        d = S.obj("mk_line_dn", S.mesh_from_bm("mk_line_dn", bm, [_glow("mk_line_r", RED, 5.0)], smooth=True))
        d.visible_shadow = False
        if f_drop is not None:
            C.draw_in(d, f_drop, f_drop + 14)
            _show(d, f_drop)
    return pts, top


def build_stairs(name, spec, glow_on=None):
    """Marble step sculpture following `levels` (in steps). Where the level drops, a glass elevator shaft with a
    cabin stands at that edge. Returns (path of step-top centres, drops [(k, x, z_top, z_bottom, cabin)])."""
    x0, y0, run, rise, dep = spec["x0"], spec["y0"], spec["run"], spec["rise"], spec["depth"]
    lev = spec["levels"]
    marble = S.pbr("mk_marble", hexc("efebe3"), 0.32, coat=0.35, var=0.04, var_scale=0.3)
    nose = _glow("mk_nosing", TEAL, 2.2)
    metal = S.pbr("mk_shaft_metal", hexc("d9dde2"), 0.25, metal=0.85, var=0.0)
    glass = clear_glass_mat()
    floor = S.pbr("mk_cabin_floor", hexc("d8a640"), 0.3, metal=0.8, var=0.0)
    bm = bmesh.new()
    bmn = bmesh.new()
    path, drops = [], []
    x = x0
    k = 0
    while k < len(lev):
        l = lev[k]
        if l == 0:
            k += 1
            continue
        xa, xb = P(x, 0)[0], P(x + run, 0)[0]
        ya, yb = P(0, y0)[1], P(0, y0 + dep)[1]
        zt = PZ + l * rise
        _box(bm, xa, xb, ya, yb, PZ - 0.2, zt, 0)
        _box(bmn, xa - 0.02, xa + 0.35, ya - 0.05, yb + 0.05, zt - 0.3, zt + 0.06, 0)
        path.append(((xa + xb) / 2, (ya + yb) / 2, zt))
        x += run
        if k + 1 < len(lev) and lev[k + 1] < l:
            drops.append((len(path) - 1, x, zt, PZ + lev[k + 1] * rise))
            x += run * 2.2 if lev[k + 1] == 0 else run * 1.6   # room for the shaft
        k += 1
    S.obj(name + "_steps", S.mesh_from_bm(name + "_steps", bm, [marble]))
    no = S.obj(name + "_nose", S.mesh_from_bm(name + "_nose", bmn, [nose]))
    no.visible_shadow = False
    out = []
    for j, (pk, xs, zt, zb) in enumerate(drops):
        sw = run * (2.2 if zb <= PZ + 0.01 else 1.6)
        cx, cy = P(xs + sw / 2, 0)[0], P(0, y0 + dep / 2)[1]
        hw, hd = sw / 2 - 0.15, dep / 2 - 1.0
        top = zt + max(5.0, rise * 2.2)
        bm = bmesh.new()
        for sx in (-1, 1):
            for sy in (-1, 1):
                _box(bm, cx + sx * hw - 0.25, cx + sx * hw + 0.25, cy + sy * hd - 0.25, cy + sy * hd + 0.25,
                     PZ - 0.1, top, 0)
        _box(bm, cx - hw - 0.3, cx + hw + 0.3, cy - hd - 0.3, cy + hd + 0.3, top, top + 0.6, 0)
        S.obj("%s_shaft%d" % (name, j), S.mesh_from_bm("shaft", bm, [metal]))
        bm = bmesh.new()
        _box(bm, cx - hw, cx + hw, cy - hd, cy + hd, PZ, top, 0)
        g = S.obj("%s_glass%d" % (name, j), S.mesh_from_bm("shaftglass", bm, [glass]))
        g.visible_shadow = False
        # cabin: floor + roof (gold) + glass walls, origin at its floor centre
        ch = min(4.2, max(2.6, rise * 1.4))
        bm = bmesh.new()
        _box(bm, -hw + 0.3, hw - 0.3, -hd + 0.3, hd - 0.3, -0.35, 0.0, 0)
        _box(bm, -hw + 0.3, hw - 0.3, -hd + 0.3, hd - 0.3, ch, ch + 0.3, 0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                _box(bm, sx * (hw - 0.45) - 0.12, sx * (hw - 0.45) + 0.12, sy * (hd - 0.45) - 0.12,
                     sy * (hd - 0.45) + 0.12, 0.0, ch, 0)
        cab = S.obj("%s_cab%d" % (name, j), S.mesh_from_bm("cab", bm, [floor]), (cx, cy, zt))
        # red drop strip on the shaft front (shown on the glow cue or when the cabin drops)
        bm = bmesh.new()
        _box(bm, -0.35, 0.35, -0.2, 0.0, -(zt - zb), 0.0, 0)
        strip = S.obj("%s_dropglow%d" % (name, j), S.mesh_from_bm("dropglow", bm, [_glow("mk_dropred", RED, 5.0)]),
                      (cx, cy - hd - 0.45, zt))
        strip.visible_shadow = False
        strip.scale = (0, 0, 0)
        out.append({"k": pk, "x": cx, "y": cy, "zt": zt, "zb": zb, "cab": cab, "strip": strip})
    return path, out


def ball_mat():
    return _glow("mk_ball", hexc("39f5a6"), 3.0)


def ride(ctx, ball, path, drops, f0, f1, r=1.4, hop=1.6, drop_frames=14, hold_top=0, f_drops=None):
    """Keyframe the price ball hopping up the step path from f0 to f1 and riding each elevator down.
    f_drops: optional explicit start frame per drop (the ball waits on top until then)."""
    T = ctx.frames
    seg = []           # list of ("step", k) / ("drop", j)
    di = {d["k"]: j for j, d in enumerate(drops)}
    for k in range(len(path)):
        seg.append(("step", k))
        if k in di:
            seg.append(("drop", di[k]))
    n_steps = sum(1 for s in seg if s[0] == "step")
    n_drop = len(seg) - n_steps
    fixed = n_drop * (drop_frames + 10)
    per = max(3.0, (f1 - f0 - fixed) / max(1, n_steps - 1))
    f = float(f0)
    prev = None
    bk = []
    for kind, i in seg:
        if kind == "step":
            p = Vector(path[i]) + Vector((0, 0, r))
            if prev is None:
                bk.append((f, p))
            else:
                fm = f + per / 2
                mid = (prev + p) / 2 + Vector((0, 0, hop + max(0, p.z - prev.z) * 0.5))
                bk.append((fm, mid))
                f += per
                bk.append((f, p))
            prev = p
        else:
            d = drops[i]
            # roll into the cabin
            cab = d["cab"]
            pin = Vector((d["x"], d["y"], d["zt"] + r))
            fa = f + 6
            if f_drops and i < len(f_drops) and f_drops[i] is not None:
                fa = max(fa, f_drops[i] - 4)
            bk.append((f + 6, pin))
            bk.append((fa + 4, pin))
            fs = fa + 4
            fe = fs + drop_frames
            kf(cab, "location", 1, cab.location.copy(), "CONSTANT")
            kf(cab, "location", int(fs), Vector((d["x"], d["y"], d["zt"])), "BEZIER")
            kf(cab, "location", int(fe), Vector((d["x"], d["y"], d["zb"])), "BEZIER")
            st = d["strip"]
            kf(st, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            kf(st, "scale", int(fs), Vector((1, 1, 0.001)), "LINEAR")
            kf(st, "scale", int(fe), Vector((1, 1, 1)), "LINEAR")
            bot = Vector((d["x"], d["y"], d["zb"] + r))
            bk.append((fs, pin))
            bk.append((fe, bot))
            # roll out to the next step (or rest on the plaza)
            f = fe + 6
            nxt = None
            for kind2, i2 in seg[seg.index((kind, i)) + 1:]:
                if kind2 == "step":
                    nxt = Vector(path[i2]) + Vector((0, 0, r))
                    break
            if nxt is not None:
                out = Vector((d["x"] + (nxt.x - d["x"]) * 0.45, d["y"], d["zb"] + r))
                bk.append((f, out))
                prev = out
            else:
                out = Vector((d["x"] + 9.0, d["y"], d["zb"] + r))
                bk.append((f, out))
                prev = out
    for fr, p in bk:
        kf(ball, "location", max(1, min(T + 30, int(round(fr)))), p, "BEZIER")
    return bk


def build_fountain(ctx):
    stone = S.pbr("mk_stone", hexc("d6cfc2"), 0.55, var=0.05)
    water = C.water_mat()
    cx, cy, _ = P(*FOUNTAIN)
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=15.0, radius2=15.0, depth=1.2)
    bmesh.ops.translate(bm, vec=(cx, cy, PZ + 0.6), verts=res["verts"])
    S.obj("mk_fountain_rim", S.mesh_from_bm("mk_fountain_rim", bm, [stone], smooth=False))
    bm = bmesh.new()
    res = bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=14.0)
    bmesh.ops.translate(bm, vec=(cx, cy, PZ + 1.25), verts=res["verts"])
    S.obj("mk_fountain_water", S.mesh_from_bm("mk_fountain_water", bm, [water]))


def build_planters(ctx, rng):
    stone = S.pbr("mk_planter", hexc("c9c0b0"), 0.6, var=0.05)
    soil = S.lawn_mat("mk_planter_lawn", hexc("6f9050"), stripes=False)
    pts = []
    bm = bmesh.new()
    bms = bmesh.new()
    spots = [(-196.0, y) for y in range(-110, 121, 26)] + [(196.0, y) for y in range(-110, 121, 26)]
    spots += [(x, -128.0) for x in (-176.0, -150.0, 150.0, 176.0)] + [(x, 128.0) for x in (-170.0, -60.0, 60.0, 170.0)]
    for dx, dy in spots:
        x, y, _ = P(dx, dy)
        _box(bm, x - 4.0, x + 4.0, y - 4.0, y + 4.0, PZ - 0.1, PZ + 1.1, 0)
        _box(bms, x - 3.5, x + 3.5, y - 3.5, y + 3.5, PZ + 1.1, PZ + 1.2, 0)
        pts.append((x, y))
    S.obj("mk_planters", S.mesh_from_bm("mk_planters", bm, [stone]))
    S.obj("mk_planter_soil", S.mesh_from_bm("mk_planter_soil", bms, [soil]))
    tr = S.scatter(C._TREES or S.tree_templates(rng), pts, rng, scale=(1.1, 1.5), prefix="mktree")
    for t in tr:
        t.location.z = PZ + 1.1


def build_dominoes(ctx, f_topple=None, step=3, n=None):
    """Row of big lacquered dominoes along DOMINO_PATH. Toppled analytically (front-bottom edge pivot) starting at
    f_topple, one every `step` frames. Returns the domino objects."""
    pts = [Vector(P(x, y, 0))[:2] for x, y in DOMINO_PATH]
    pts = [Vector(p) for p in pts]
    segs, total = [], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ln = (b - a).length
        segs.append((a, b, total, ln))
        total += ln
    th, h, w, sp = 0.7, 5.6, 2.8, 2.6

    def at(s):
        for a, b, s0, ln in segs:
            if s <= s0 + ln:
                u = (s - s0) / ln
                return a.lerp(b, u), (b - a).normalized()
        a, b = segs[-1][0], segs[-1][1]
        return b, (b - a).normalized()
    count = n or int(total / sp)
    body = S.pbr("mk_domino", hexc("173f6b"), 0.18, coat=0.8, var=0.0)
    pip = S.pbr("mk_pip", hexc("f6f3ec"), 0.3, var=0.0)
    rng = random.Random(5)
    doms = []
    for i in range(count):
        p, t = at(i * sp + 1.0)
        bm = bmesh.new()
        _box(bm, -w / 2, w / 2, -th, 0.0, 0.0, h, 0)
        _box(bm, -w / 2 + 0.25, w / 2 - 0.25, -0.02, 0.03, h / 2 - 0.06, h / 2 + 0.06, 1)  # divider
        for half, nv in ((0, rng.randint(1, 6)), (1, rng.randint(1, 6))):
            zc = h * (0.25 if half == 0 else 0.75)
            lay = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
                   4: [(-1, -1), (1, -1), (-1, 1), (1, 1)], 5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
                   6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}[nv]
            for u, v in lay:
                _disc_y(bm, (u * 0.72, 0.02, zc + v * 0.72), 0.26, 1)
        yaw = math.atan2(-t.x, t.y)
        o = S.obj("mk_dom%d" % i, S.mesh_from_bm("mk_dom%d" % i, bm, [body, pip]), (p.x, p.y, PZ), (0, 0, yaw))
        doms.append(o)
    if f_topple is not None:
        gap = sp - th
        a1 = math.asin(min(1.0, gap / h))            # top touches the next domino
        rest = math.radians(74.0)   # chain rest angle for spacing 2.6 / thickness 0.7
        for i, o in enumerate(doms):
            fi = f_topple + i * step
            yaw = o.rotation_euler.z
            kf(o, "rotation_euler", 1, Vector((0, 0, yaw)), "CONSTANT")
            kf(o, "rotation_euler", fi, Vector((0, 0, yaw)), "BEZIER")
            kf(o, "rotation_euler", fi + step, Vector((-a1, 0, yaw)), "LINEAR")
            last = i == len(doms) - 1
            kf(o, "rotation_euler", fi + step + 8, Vector((-(math.radians(88.0) if last else rest), 0, yaw)), "BEZIER")
    return doms


def build_market_world(ctx, p, screens="down", line="down", flips=None, line_anim=None):
    """River city with the downtown plaza + all plaza props in their resting state."""
    pp = dict(p)
    pp["exclude_blocks"] = [PLAZA]
    brs, rng = C.build_city_world(ctx, pp)
    C._flow_traffic(ctx, brs, rng, per_lane=3)
    x0, x1, y0, y1 = PLAZA
    bm = bmesh.new()
    _box(bm, x0 - 2, x1 + 2, y0 - 2, y1 + 2, 0.0, PZ, 0)
    S.obj("mk_plaza", S.mesh_from_bm("mk_plaza", bm, [paving_mat()]))
    flips = flips or {}
    for nm, spec, seed in (("mk_wall", WALL, 11), ("mk_sideL", SIDE_L, 12), ("mk_sideR", SIDE_R, 13)):
        make_screen(ctx, nm, spec, seed, flip_f=flips.get(nm), state=screens)
    la = line_anim or {}
    make_stock_line(ctx, la.get("f_rise"), la.get("rise_frames", 90), la.get("f_drop"), state=line)
    build_fountain(ctx)
    build_planters(ctx, rng)
    return brs, rng


def _cam(ctx, c0, t0, lens):
    cam = ctx.camera(c0, target=t0, lens=lens)
    cam.data.clip_start = 0.5
    cam.data.clip_end = 30000.0
    return cam


def _keys(ctx, keys, interp="BEZIER"):
    A._cam_keys(ctx, keys, interp)


# ================================================================ BUILDERS
def b_market_hook(ctx, p):
    """Plaza in the financial district: the giant 3D line climbs in front of the index wall, then on `drop_cue`
    it plunges in red and the wall's last candles flip red; the side screens follow on `wall` / `tokyo`.
    Camera pulls back from the line to the whole plaza."""
    T = ctx.frames
    f_drop = ctx.word_time(p.get("drop_cue", "fell"), 0.33)
    flips = {"mk_wall": f_drop + 4, "mk_sideL": ctx.word_time(p.get("left_cue", "wall"), 0.82),
             "mk_sideR": ctx.word_time(p.get("right_cue", "tokyo"), 0.93)}
    build_market_world(ctx, p, flips=flips, line_anim={"f_rise": 1, "rise_frames": max(20, f_drop - 6),
                                                         "f_drop": f_drop})
    stairs_path, drops = build_stairs("mk_ds", DROP_STAIRS)
    build_stairs("mk_ls", LONG_STAIRS)
    build_dominoes(ctx)
    pts, top = stock_line_pts(True)
    S.anchor(ctx, "line_top", _empty("anc_line_top", pts[top - 1]))
    S.anchor(ctx, "line_low", _empty("anc_line_low", pts[-1]))
    c0, t0 = P(*p.get("cam0", (4.0, -62.0, 28.0))), P(*p.get("tgt0", (4.0, 80.0, 38.0)))
    c1, t1 = P(*p.get("cam1", (0.0, -118.0, 20.0))), P(*p.get("tgt1", (0.0, 80.0, 36.0)))
    _cam(ctx, c0, t0, p.get("lens", 24))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_stairs_elevator_v2(ctx, p):
    """Literal metaphor on the plaza. mode 'drop': a glowing price ball hops up the marble staircase (from
    `stairs_cue`'s sentence) and rides the glass elevator straight down on `drop_cue`. mode 'long': the long
    staircase: the ball climbs, rides three short elevator drops (corrections; red strips light on `name_cue`) and
    keeps climbing higher. Anchors: ball."""
    T = ctx.frames
    mode = p.get("mode", "drop")
    build_market_world(ctx, p, screens="down")
    build_dominoes(ctx)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 0), (2.1, 2.1, 2.1), 0, 24, 14)
    ball = S.obj("mk_ball", S.mesh_from_bm("mk_ball", bm, [ball_mat()], smooth=True))
    if mode == "drop":
        path, drops = build_stairs("mk_ds", DROP_STAIRS)
        build_stairs("mk_ls", LONG_STAIRS)
        f_el = ctx.word_time(p.get("drop_cue", "elevator"), 0.7)
        f_st = ctx.word_time(p.get("climb_cue", "climb"), 0.45)
        f0 = p.get("f0", 6)
        ride(ctx, ball, path, drops, f0, max(f0 + 60, f_el - 16), r=2.1, hop=1.8, drop_frames=12,
             f_drops=[f_el])
        dx = DROP_STAIRS["x0"] + 20.0
        c0, t0 = P(*p.get("cam0", (dx - 14.0, -112.0, 16.0))), P(*p.get("tgt0", (dx + 2.0, -6.0, 25.0)))
        c1, t1 = P(*p.get("cam1", (dx - 2.0, -100.0, 18.0))), P(*p.get("tgt1", (dx + 4.0, -6.0, 23.0)))
        lens = p.get("lens", 24)
    else:
        build_stairs("mk_ds", DROP_STAIRS)
        path, drops = build_stairs("mk_ls", LONG_STAIRS)
        f_name = ctx.word_time(p.get("name_cue", "correction"), 0.3)
        ride(ctx, ball, path, drops, 4, T - 20, r=2.1, hop=1.2, drop_frames=9)
        for d in drops:     # red strips stay lit from the name cue on (after the ball has used them)
            st = d["strip"]
            st.animation_data_clear()
            kf(st, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            kf(st, "scale", f_name, Vector((1, 1, 0.001)), "LINEAR")
            kf(st, "scale", f_name + 10, Vector((1, 1, 1)), "LINEAR")
        x0 = LONG_STAIRS["x0"]
        c0, t0 = P(*p.get("cam0", (x0 + 12.0, -48.0, 11.0))), P(*p.get("tgt0", (x0 + 20.0, 8.0, 9.0)))
        c1, t1 = P(*p.get("cam1", (x0 + 82.0, -52.0, 26.0))), P(*p.get("tgt1", (x0 + 88.0, 8.0, 27.0)))
        lens = p.get("lens", 24)
    S.anchor(ctx, "ball", ball)
    _cam(ctx, c0, t0, lens)
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


BUB = {"x": FOUNTAIN[0], "y": FOUNTAIN[1]}


def _bubble_state(u):
    """u 0..1 -> (radius, centre z) while inflating."""
    r = 5.0 + 12.0 * u
    return r, 22.0 + r * 1.15


def _bubble(ctx, keys):
    """keys: [(frame, u)]. Builds bubble + gold profit pedestal + tether; returns (bubble, tether, ped, top_z)."""
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=28, radius=1.0)
    bub = S.obj("mk_bubble", S.mesh_from_bm("mk_bubble", bm, [bubble_mat()], smooth=True))
    bub.visible_shadow = False
    gold = S.pbr("mk_gold", hexc("e0ac3a"), 0.25, metal=0.9, var=0.03)
    base = S.pbr("mk_ped", hexc("efebe3"), 0.35, coat=0.3, var=0.03)
    cx, cy, _ = P(BUB["x"], BUB["y"])
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=3.6, radius2=3.6, depth=3.0)
    bmesh.ops.translate(bm, vec=(0, 0, 1.5), verts=res["verts"])
    S.obj("mk_ped", S.mesh_from_bm("mk_ped", bm, [base], smooth=True), (cx, cy, PZ + 1.2))
    # profits = a stack of gold coins on the pedestal (grows a little), origin at its base
    bm = bmesh.new()
    rr = random.Random(3)
    for k in range(7):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=2.3, radius2=2.3, depth=0.42)
        bmesh.ops.translate(bm, vec=(rr.uniform(-0.15, 0.15), rr.uniform(-0.15, 0.15), 0.25 + k * 0.48),
                            verts=res["verts"])
    ped_top = PZ + 1.2 + 3.0
    coins = S.obj("mk_coins", S.mesh_from_bm("mk_coins", bm, [gold], smooth=True), (cx, cy, ped_top))
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=0.12, radius2=0.12, depth=1.0)
    bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=res["verts"])
    teth = S.obj("mk_tether", S.mesh_from_bm("mk_tether", bm, [S.pbr("mk_string", hexc("f4f4f4"), 0.5, var=0.0)]),
                 (cx, cy, ped_top + 3.5))
    teth.visible_shadow = False
    anc = _empty("anc_bubble", (0, 0, 0))
    for f, u in keys:
        r, z = _bubble_state(u)
        kf(bub, "location", f, Vector((cx, cy, z)), "BEZIER")
        kf(bub, "scale", f, Vector((r, r, r * 0.97)), "BEZIER")
        kf(teth, "scale", f, Vector((1, 1, max(0.1, z - r - (ped_top + 3.5)))), "BEZIER")
        kf(anc, "location", f, Vector((cx + r * 0.62, cy - r * 0.2, z + r * 0.62)), "BEZIER")
    S.anchor(ctx, "bubble", anc)
    pa = _empty("anc_profit", (cx, cy, ped_top + 3.4))
    S.anchor(ctx, "profit", pa)
    return bub, teth, coins, (cx, cy)


def _confetti(ctx, centre, radius, f_pop, n=320, seed=9):
    T = ctx.frames
    rng = random.Random(seed)
    cols = [hexc(c) for c in ("2ee6c8", "ffd23f", "ff6b9a", "6fb6ff", "ffffff", "9b7bff", "ff9f43")]
    mats = [S.pbr("mk_conf%d" % i, c, 0.45, var=0.0) for i, c in enumerate(cols)]
    meshes = []
    for i, m in enumerate(mats):
        bm = bmesh.new()
        _box(bm, -0.55, 0.55, -0.35, 0.35, -0.02, 0.02, 0)
        meshes.append(S.mesh_from_bm("mk_conf_me%d" % i, bm, [m]))
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    cx, cy, cz = centre
    fps = ctx.fps
    for i in range(n):
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        p0 = Vector((cx, cy, cz)) + d * radius * rng.uniform(0.6, 1.0)
        v0 = d * rng.uniform(6.0, 16.0) + Vector((0, 0, rng.uniform(1.0, 7.0)))
        k, vt = rng.uniform(0.9, 1.5), rng.uniform(2.5, 4.5)
        w = Vector((rng.uniform(-9, 9), rng.uniform(-9, 9), rng.uniform(-6, 6)))
        o = S.obj("mk_cf%d" % i, meshes[i % len(meshes)], p0, (rng.uniform(0, 6), rng.uniform(0, 6), 0))
        o.visible_shadow = False
        o.scale = (0, 0, 0)
        o.keyframe_insert("scale", frame=1)
        o.scale = (1, 1, 1)
        o.keyframe_insert("scale", frame=f_pop)
        rot0 = Vector(o.rotation_euler[:])
        landed = None
        for f in list(range(f_pop, T + 1, 2)) + [T]:
            t = (f - f_pop) / fps
            e = (1 - math.exp(-k * t)) / k
            pos = Vector((p0.x + v0.x * e, p0.y + v0.y * e, p0.z + (v0.z + vt) * e - vt * t))
            if pos.z <= PZ + 0.05 + rng.uniform(0, 0.01):
                if landed is None:
                    landed = pos.copy()
                pos = Vector((landed.x, landed.y, PZ + 0.05))
            o.location = pos
            o.keyframe_insert("location", frame=f)
            o.rotation_euler = rot0 + (w * t if landed is None else Vector((0, 0, w.z * t)))
            if landed is not None:
                o.rotation_euler = (0, 0, o.rotation_euler.z)
            o.keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = old
    # scale keys must be CONSTANT (hard appear)
    for i in range(n):
        o = bpy.data.objects["mk_cf%d" % i]
        _set_const(o, "scale")


def _fcurves(o, path):
    ad = o.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    curves = []
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


def _set_const(o, path):
    """Blender 5.3 ignores the new-keyframe interpolation preference used by L.kf(): set CONSTANT explicitly."""
    for fc in _fcurves(o, path):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def _const_first(o, path):
    for fc in _fcurves(o, path):
        if len(fc.keyframe_points):
            fc.keyframe_points[0].interpolation = "CONSTANT"


def _paper_plane(ctx, name, mat):
    bm = bmesh.new()
    v = [bm.verts.new(c) for c in ((0, 2.4, 0), (-1.6, -1.2, 0.25), (0, -0.9, -0.05), (1.6, -1.2, 0.25),
                                   (0, -1.2, -0.45))]
    bm.faces.new((v[0], v[1], v[2]))
    bm.faces.new((v[0], v[2], v[3]))
    bm.faces.new((v[0], v[4], v[2]))
    return S.obj(name, S.mesh_from_bm(name, bm, [mat]))


def b_bubble_v2(ctx, p):
    """A glossy soap bubble ('price') tethered to a small gold coin stack ('profits') above the plaza fountain.
    mode 'inflate': grows on `grow_cue`, the coins barely grow. mode 'pop': starts at the full size; a red paper
    plane ('bad news') glides in and touches it on `pop_cue`; it pops into confetti that flutters down onto the
    plaza (nothing broken, nobody hurt). Anchors: bubble, profit."""
    T = ctx.frames
    mode = p.get("mode", "inflate")
    build_market_world(ctx, p, screens="up" if mode == "inflate" else "down",
                       line="up" if mode == "inflate" else "down")
    build_stairs("mk_ds", DROP_STAIRS)
    build_stairs("mk_ls", LONG_STAIRS)
    build_dominoes(ctx)
    cx, cy = P(BUB["x"], BUB["y"])[:2]
    if mode == "inflate":
        f_g = ctx.word_time(p.get("grow_cue", "excited"), 0.3)
        bub, teth, coins, _ = _bubble(ctx, [(1, 0.0), (max(2, f_g - 4), 0.05), (T, 1.0)])
        f_pr = ctx.word_time(p.get("profit_cue", "profits"), 0.7)
        kf(coins, "scale", 1, Vector((1, 1, 1)), "BEZIER")
        kf(coins, "scale", T, Vector((1.05, 1.05, 1.12)), "BEZIER")
        c0, t0 = P(BUB["x"] + 6, -80.0, 8.0), P(BUB["x"], BUB["y"], 25.0)
        c1, t1 = P(BUB["x"] + 2, -76.0, 9.0), P(BUB["x"], BUB["y"], 31.0)
    else:
        f_pop = ctx.word_time(p.get("pop_cue", "news"), 0.5)
        keys = [(1, 1.0)]
        for k, f in enumerate(range(12, max(13, f_pop - 2), 12)):
            keys.append((f, 1.0 + (0.012 if k % 2 == 0 else -0.008)))
        keys.append((f_pop - 1, 1.0))
        bub, teth, coins, _ = _bubble(ctx, keys)
        r, z = _bubble_state(1.0)
        kf(bub, "scale", f_pop, Vector((r * 1.04, r * 1.04, r * 1.0)), "CONSTANT")
        kf(bub, "scale", f_pop + 1, Vector((0, 0, 0)), "CONSTANT")
        kf(teth, "scale", f_pop + 1, Vector((0, 0, 0)), "CONSTANT")
        # flash ring where it popped (real geometry, fades out)
        m, sock = L.add_mat("mk_popflash", hexc("fff4d0"), 0.0)
        bm = bmesh.new()
        C._annulus(bm, r * 1.0, 0.3, 72)
        ring = S.obj("mk_popring", S.mesh_from_bm("mk_popring", bm, [m]), (cx, cy, z))
        ring.rotation_euler = (math.radians(90), 0, 0)
        ring.visible_shadow = False
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, f_pop, 6.0, "LINEAR")
        L.kf_socket(sock, f_pop + 10, 0.0, "LINEAR")
        kf(ring, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
        kf(ring, "scale", f_pop, Vector((1, 1, 1)), "LINEAR")
        kf(ring, "scale", f_pop + 10, Vector((1.5, 1.5, 1.5)), "LINEAR")
        _const_first(ring, "scale")
        # bad-news paper plane
        pl = _paper_plane(ctx, "mk_news", S.pbr("mk_news_red", hexc("e8323a"), 0.5, var=0.0))
        hit = Vector((cx + r * 0.72, cy - r * 0.55, z + r * 0.1))
        start = hit + Vector((42.0, -18.0, 10.0))
        fa = max(2, f_pop - 40)
        d = (hit - start).normalized()
        yaw = math.atan2(-d.x, d.y)
        kf(pl, "location", 1, start, "CONSTANT")
        kf(pl, "location", fa, start, "LINEAR")
        kf(pl, "location", f_pop, hit, "LINEAR")
        kf(pl, "location", f_pop + 30, hit + d * 10 + Vector((0, 0, -12)), "BEZIER")
        kf(pl, "location", T, hit + d * 12 + Vector((0, 0, z - 1.0 - hit.z)), "BEZIER")
        pl.rotation_euler = (math.radians(-8), math.radians(10), yaw)
        _show(pl, fa)
        _confetti(ctx, (cx, cy, z), r, f_pop + 1)
        S.anchor(ctx, "news", pl)
        c0, t0 = P(BUB["x"] + 2, -76.0, 9.0), P(BUB["x"], BUB["y"], 31.0)
        c1, t1 = P(BUB["x"] + 0, -72.0, 8.0), P(BUB["x"], BUB["y"], 24.0)
    _cam(ctx, c0, t0, p.get("lens", 19))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_dominoes_v2(ctx, p):
    """A long curving row of big lacquered dominoes across the plaza. On `topple_cue` the first one tips and the
    whole row falls one after another towards the camera. Anchors: first, last."""
    T = ctx.frames
    build_market_world(ctx, p, screens="down")
    build_stairs("mk_ds", DROP_STAIRS)
    build_stairs("mk_ls", LONG_STAIRS)
    f_t = ctx.word_time(p.get("topple_cue", "drop"), 0.4)
    probe = build_dominoes(ctx)                       # count the row, then rebuild it animated
    cnt = len(probe)
    for o in probe:
        bpy.data.objects.remove(o, do_unlink=True)
    step = p.get("step", max(1.5, min(4.0, (T - 24 - f_t) / max(1, cnt))))
    doms = build_dominoes(ctx, f_t, step=step)
    print("[v2 market] %d dominoes, topple from f%d, step %.2f" % (cnt, f_t, step))
    S.anchor(ctx, "first", doms[0], (0, 0, 6.0))
    S.anchor(ctx, "last", doms[-1], (0, 0, 6.0))
    c0, t0 = P(*p.get("cam0", (-128.0, -97.0, 13.0))), P(*p.get("tgt0", (40.0, -103.0, -8.0)))
    c1, t1 = P(*p.get("cam1", (-120.0, -98.0, 15.0))), P(*p.get("tgt1", (50.0, -106.0, -10.0)))
    _cam(ctx, c0, t0, p.get("lens", 24))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_market_outro(ctx, p):
    """Closing crane-up: from the plaza (index wall with its red tail) up over the downtown to the river city."""
    T = ctx.frames
    build_market_world(ctx, p, screens="down")
    build_stairs("mk_ds", DROP_STAIRS)
    build_stairs("mk_ls", LONG_STAIRS)
    build_dominoes(ctx)
    c0, t0 = P(*p.get("cam0", (10.0, -110.0, 18.0))), P(*p.get("tgt0", (0.0, 80.0, 34.0)))
    c1, t1 = P(*p.get("cam1", (-60.0, -420.0, 420.0))), P(*p.get("tgt1", (300.0, 300.0, 0.0)))
    _cam(ctx, c0, t0, p.get("lens", 24))
    _keys(ctx, [(1, c0, t0), (int(T * 0.3), P(5.0, -100.0, 30.0), P(0.0, 80.0, 36.0)), (T, c1, t1)])


S.V2_BUILDERS.update({
    "market_hook": b_market_hook,
    "stairs_elevator_v2": b_stairs_elevator_v2,
    "bubble_v2": b_bubble_v2,
    "dominoes_v2": b_dominoes_v2,
    "market_outro": b_market_outro,
})

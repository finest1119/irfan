"""v2 holiday-travel builders ("Thanksgiving travel", 25 Nov 2026). Registers into scene_lib_v2.V2_BUILDERS.

World = the persistent v2 airport world (S.build_world: airport, suburbs, downtown, hills) + a six-lane interstate
east of the suburbs (x = HX), so every beat (highway or airport) is the same place.
No 3D text: titles / chips / labels / the departures board are 2D overlays (overlay_v2.py).
Non-graphic: cars only drive, brake and queue (no contact); aircraft only taxi, sit at gates or take off.

Traffic is keyed sparsely with foreach_set (fast); brake glows are show/hide objects with CONSTANT keys set
explicitly (Blender 5.3 ignores the interpolation preference used by L.kf()).
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import scene_lib as L
import scene_lib_v2 as S
import scene_lib_v2_air as A
from scene_lib import hexc, kf

HX = 1720.0                 # interstate centre line (median barrier)
LANE = 3.7
NB = [HX + 2.0 + 1.0 + LANE * (i + 0.5) for i in range(3)]      # northbound lane centres (driving +y), 0 = left/fast
SB = [HX - 2.0 - 1.0 - LANE * (i + 0.5) for i in range(3)]      # southbound lane centres (driving -y)
HY0, HY1 = -7000.0, 9500.0  # highway extent
ZR = 0.22                   # road surface
OVY = 620.0                 # overpass
MATS = {}


# ================================================================ keyframe helpers
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


_INTERP = {"CONSTANT": 0, "LINEAR": 1, "BEZIER": 2}


def set_keys(o, path, frames, values, interp="LINEAR"):
    """Write many keys at once (foreach_set). values = list of tuples (one per frame)."""
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


def show_keys(o, on_frames):
    """on_frames: sorted list of (frame, visible bool). Hard show/hide by scale, CONSTANT keys."""
    s = tuple(o.scale)
    vals = [(s if v else (0.0, 0.0, 0.0)) for _, v in on_frames]
    set_keys(o, "scale", [f for f, _ in on_frames], vals, "CONSTANT")


# ================================================================ materials
def _m(name, fn):
    if name not in MATS:
        MATS[name] = fn()
    return MATS[name]


def concrete():
    return _m("tv_concrete", lambda: S.pbr("tv_concrete", hexc("c9c6bf"), 0.75, var=0.08, var_scale=0.4, bump=0.05))


def steel():
    return _m("tv_steel", lambda: S.pbr("tv_steel", hexc("b9bec4"), 0.35, 0.8, var=0.03))


def brake_glow_mat():
    return _m("tv_brake", lambda: S.emis("tv_brake", hexc("ff2030"), 30.0))


def brake_pool_mat():
    return _m("tv_pool", lambda: A._alpha_emis("tv_pool", hexc("ff1a24"), 5.0, 0.5))


def tail_mat():
    return _m("tv_tail", lambda: S.emis("tv_tail", hexc("c0141e"), 1.6))


def head_mat():
    return _m("tv_head", lambda: S.emis("tv_head", hexc("fff2d8"), 3.0))


# ================================================================ the interstate
def build_highway(ctx):
    length = HY1 - HY0
    yc = (HY0 + HY1) / 2
    tiles = round(length / 24.0)
    hw = S.image_mat("tv_highway", "highway.png", (1.0, tiles), rough=0.8)
    S.plane_obj("hw_nb", 16.0, length, (HX + 10.0, yc, ZR), hw)
    S.plane_obj("hw_sb", 16.0, length, (HX - 10.0, yc, ZR), hw, rot_z=math.pi)
    med = S.pbr("tv_median", hexc("8f8c86"), 0.85, var=0.08, var_scale=0.3)
    S.plane_obj("hw_median", 4.2, length, (HX, yc, ZR - 0.005), med)
    # verges: mown grass strips, slightly lighter than the fields
    verge = S.lawn_mat("tv_verge", hexc("7d9658"), stripes=False)
    for sx in (-1, 1):
        S.plane_obj("hw_verge%d" % sx, 26.0, length, (HX + sx * (18.0 + 13.0), yc, 0.12), verge)
    # median jersey barrier (one long prism) + outer guardrails with posts (only the stretch cameras see)
    bm = bmesh.new()
    pts = [(-0.32, 0.0), (0.32, 0.0), (0.16, 0.3), (0.12, 0.9), (-0.12, 0.9), (-0.16, 0.3)]
    a = [bm.verts.new((HX + x, HY0, ZR + z)) for x, z in pts]
    b = [bm.verts.new((HX + x, HY1, ZR + z)) for x, z in pts]
    fs = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        fs.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    S.obj("hw_barrier", S.mesh_from_bm("hw_barrier", bm, [concrete()]))
    y_lo, y_hi = -2600.0, 5200.0
    bm = bmesh.new()
    for sx in (-1, 1):
        x = HX + sx * 18.4
        S.bm_box(bm, (x, (y_lo + y_hi) / 2, ZR + 0.62), (0.08, y_hi - y_lo, 0.32), 0)
        y = y_lo
        while y < y_hi:
            S.bm_box(bm, (x + sx * 0.12, y, ZR + 0.38), (0.12, 0.12, 0.76), 0)
            y += 4.0
    S.obj("hw_rails", S.mesh_from_bm("hw_rails", bm, [steel()]))
    # light poles on the median every 90 m (tall, thin; read as a real interstate)
    bm = bmesh.new()
    y = y_lo
    while y < y_hi:
        S.bm_box(bm, (HX, y, ZR + 6.5), (0.25, 0.25, 13.0), 0)
        for sx in (-1, 1):
            S.bm_box(bm, (HX + sx * 1.6, y, ZR + 12.9), (3.2, 0.18, 0.14), 0)
            S.bm_box(bm, (HX + sx * 3.1, y, ZR + 12.75), (0.9, 0.38, 0.18), 0)
        y += 90.0
    S.obj("hw_poles", S.mesh_from_bm("hw_poles", bm, [steel()]))
    build_overpass()
    build_signs()


def build_overpass():
    """Two-lane road bridge over the interstate at y = OVY (deck at 7 m), earth ramps either side."""
    road_m = S.image_mat("road_v2_ov", "road.png", (1.0, 26.0), rough=0.8)
    deck_z = 7.2
    span = 140.0
    S.plane_obj("ov_deck_top", 9.0, span, (HX, OVY, deck_z + 0.62), road_m, rot_z=math.pi / 2)
    bm = bmesh.new()
    S.bm_box(bm, (HX, OVY, deck_z), (span, 11.0, 1.2), 0)            # deck slab
    for sy in (-1, 1):
        S.bm_box(bm, (HX, OVY + sy * 5.2, deck_z + 1.15), (span, 0.4, 1.0), 0)   # parapets
    for px in (HX - 26.0, HX, HX + 26.0):
        for sy in (-1, 1):
            S.bm_box(bm, (px, OVY + sy * 3.0, deck_z / 2), (1.4, 1.4, deck_z), 0)
        S.bm_box(bm, (px, OVY, deck_z - 0.9), (1.8, 8.5, 0.8), 0)
    S.obj("ov_bridge", S.mesh_from_bm("ov_bridge", bm, [concrete()]))
    # embankment ramps (grass) down to the fields at +-300 m
    grass = S.lawn_mat("tv_ramp", hexc("6f8a4e"), stripes=False)
    for sx in (-1, 1):
        bm = bmesh.new()
        x0, x1 = HX + sx * span / 2, HX + sx * (span / 2 + 230.0)
        prof = [(-12.0, 0.0), (12.0, 0.0), (5.6, deck_z + 0.6), (-5.6, deck_z + 0.6)]
        a = [bm.verts.new((x0, OVY + yy, z)) for yy, z in prof]
        b = [bm.verts.new((x1, OVY + yy * 0.6, 0.05)) for yy, z in prof]
        fs = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
        for i in range(4):
            j = (i + 1) % 4
            fs.append(bm.faces.new((a[i], a[j], b[j], b[i])))
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        S.obj("ov_ramp%d" % sx, S.mesh_from_bm("ov_ramp", bm, [grass]))
        rm = S.image_mat("road_v2_ramp", "road.png", (1.0, 1.0), rough=0.8)
        ln = math.hypot(x1 - x0, deck_z + 0.6)
        quad_uv("ov_ramp_road%d" % sx, [(x0, OVY - 4.5, deck_z + 0.64), (x0, OVY + 4.5, deck_z + 0.64),
                                        (x1, OVY + 4.5, 0.1), (x1, OVY - 4.5, 0.1)],
                [(0, 0), (1, 0), (1, ln / 24.0), (0, ln / 24.0)], rm)


def quad_uv(name, verts, uvs, mat):
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v) for v in verts])
    uv = bm.loops.layers.uv.new("UVMap")
    for lp, w in zip(f.loops, uvs):
        lp[uv].uv = w
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    if f.normal.z < 0:
        f.normal_flip()
    return S.obj(name, S.mesh_from_bm(name, bm, [mat]))


def build_signs():
    """Plain green overhead sign gantries (no text: arrows only) every ~1.6 km."""
    green = _m("tv_sign", lambda: S.pbr("tv_sign", hexc("0f6b3a"), 0.45, var=0.02))
    white = _m("tv_signw", lambda: S.pbr("tv_signw", hexc("f2f2ee"), 0.4, var=0.0))
    for k, y in enumerate((-900.0, 2400.0, 4000.0)):
        bm = bmesh.new()
        for sx in (-1, 1):
            S.bm_box(bm, (HX + sx * 19.0, y, ZR + 4.0), (0.4, 0.4, 8.0), 0)
        S.bm_box(bm, (HX, y, ZR + 7.8), (38.4, 0.35, 0.35), 0)
        S.bm_box(bm, (HX, y, ZR + 7.2), (38.4, 0.3, 0.3), 0)
        o = S.obj("gantry%d" % k, S.mesh_from_bm("gantry", bm, [steel()]))
        for sx in (-1, 1):
            bm = bmesh.new()
            S.bm_box(bm, (HX + sx * 9.5, y + sx * 0.4, ZR + 7.5), (9.0, 0.2, 3.4), 0)
            # white border + two down arrows (lane guidance), no words
            S.bm_box(bm, (HX + sx * 9.5, y + sx * 0.52, ZR + 9.05), (8.6, 0.05, 0.12), 1)
            for ax in (-2.4, 2.4):
                cx = HX + sx * 9.5 + ax
                S.bm_box(bm, (cx, y + sx * 0.52, ZR + 7.9), (0.28, 0.05, 1.4), 1)
                S.bm_box(bm, (cx, y + sx * 0.52, ZR + 7.1), (0.9, 0.05, 0.26), 1)
            S.obj("sign%d_%d" % (k, sx), S.mesh_from_bm("sign", bm, [green, white]))


def clear_corridor():
    """Trees / hills that the interstate would run through are removed or moved aside."""
    gone = 0
    for o in list(bpy.data.objects):
        nm = o.name
        if nm.startswith("tree") and abs(o.location.x - HX) < 48.0:
            bpy.data.objects.remove(o, do_unlink=True)
            gone += 1
        elif nm.startswith("tree") and abs(o.location.y - OVY) < 30 and abs(o.location.x - HX) < 330:
            bpy.data.objects.remove(o, do_unlink=True)
            gone += 1
        elif nm.startswith("hill"):
            rx = o.scale.x * 1.08
            if abs(o.location.x - HX) < rx + 80.0:
                sgn = 1.0 if o.location.x >= HX else -1.0
                o.location.x = HX + sgn * (rx + 120.0)
    print("[v2 travel] cleared %d trees from the corridor" % gone)


def build_travel_world(ctx, p, sun_az=-35.0):
    S.daylight(ctx, p.get("sun_az", sun_az), p.get("sun_elev", 40.0), hdri=p.get("hdri", True))
    S.build_world(ctx)
    import scene_lib_v2_city as C
    C.horizon_haze(ctx.scene)          # hides the HDRI's own dark tree line at the horizon
    for o in list(bpy.data.objects):   # far hills read as flat pale slabs from the air: removed
        if o.name.startswith("hill"):
            bpy.data.objects.remove(o, do_unlink=True)
    clear_corridor()
    build_highway(ctx)
    corridor_trees(random.Random(p.get("tree_seed", 77)))


def corridor_trees(rng, y_lo=-3000.0, y_hi=6000.0):
    """Hedgerows and copses along both sides of the interstate (40-160 m out), so the fields are not bare."""
    tpl = S.tree_templates(rng)
    pts = []
    y = y_lo
    while y < y_hi:
        for sx in (-1, 1):
            if rng.random() < 0.55:
                off = rng.uniform(44.0, 70.0)
                for _ in range(rng.randint(3, 9)):
                    pts.append((HX + sx * (off + rng.gauss(0, 4)), y + rng.gauss(0, 9)))
            if rng.random() < 0.25:
                cx, cy = HX + sx * rng.uniform(90, 420), y + rng.uniform(-30, 30)
                for _ in range(rng.randint(6, 16)):
                    pts.append((cx + rng.gauss(0, 18), cy + rng.gauss(0, 18)))
        y += 55.0
    pts = [(x, yy) for x, yy in pts if abs(x - HX) > 40 and not (abs(yy - OVY) < 30 and abs(x - HX) < 330)
           and not (440 - 20 < x < 1500 + 20 and -380 - 20 < yy < 2300 + 20)]
    S.scatter(tpl, pts, rng, prefix="ctree")


# ================================================================ cars
_TPL = {}


def _lamp_meshes(model):
    """Shared meshes per Kenney model: tail lamps, head lamps, brake glow (rear quad)."""
    if model in _TPL:
        return _TPL[model]
    t = L._kenney_template(model)
    out = {}
    bm = bmesh.new()
    for tp in t["tail"]:
        side = 1 if tp.x > 0 else -1
        S.bm_box(bm, (tp.x - side * 0.04, tp.y - 0.04, tp.z), (0.3, 0.06, 0.15))
    out["tail"] = S.mesh_from_bm("tv_tail_" + model, bm, [tail_mat()])
    bm = bmesh.new()
    for hp in t["head"]:
        side = 1 if hp.x > 0 else -1
        S.bm_box(bm, (hp.x - side * 0.04, hp.y + 0.04, hp.z), (0.3, 0.06, 0.15))
    out["head"] = S.mesh_from_bm("tv_head_" + model, bm, [head_mat()])
    # brake glow: a bright red quad just behind the rear bumper (reads at highway-camera distances)
    tz = sum(tp.z for tp in t["tail"]) / len(t["tail"])
    ty = min(tp.y for tp in t["tail"]) - 0.1
    bm = bmesh.new()
    for tp in t["tail"]:
        side = 1 if tp.x > 0 else -1
        S.bm_box(bm, (tp.x - side * 0.08, ty, tz), (0.62, 0.06, 0.42), 0)
    S.bm_box(bm, (0.0, ty - 0.01, tz + 0.36), (0.8, 0.05, 0.12), 0)    # third brake light
    # red light pooling on the asphalt behind the car (reads from high cameras)
    v = [bm.verts.new(c) for c in ((-1.25, ty - 0.1, 0.03 - ZR + ZR), (1.25, ty - 0.1, 0.03),
                                   (1.25, ty - 4.2, 0.03), (-1.25, ty - 4.2, 0.03))]
    f = bm.faces.new(v)
    f.material_index = 1
    out["brake"] = S.mesh_from_bm("tv_brake_" + model, bm, [brake_glow_mat(), brake_pool_mat()])
    bm = bmesh.new()
    for tp in t["tail"]:
        side = 1 if tp.x > 0 else -1
        S.bm_box(bm, (tp.x - side * 0.04, ty + 0.06, tp.z), (0.32, 0.05, 0.17), 0)
    out["brake_np"] = S.mesh_from_bm("tv_brakenp_" + model, bm, [S.emis("tv_brake_close", hexc("ff2030"), 12.0)])
    out["t"] = t
    _TPL[model] = out
    return out


class FastCar:
    pass


def fast_car(name, loc, rot_z, model=None, brake=False, wheels=True, pool=True):
    model = model or L.pick_model()
    lm = _lamp_meshes(model)
    t = lm["t"]
    root = L.link(bpy.data.objects.new(name, None))
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    for i, (data, mtx) in enumerate(t["parts"]):
        o = L.link(bpy.data.objects.new("%s_p%d" % (name, i), data))
        o.parent = root
        o.matrix_basis = mtx
    sx, _, sz = t["scale"]
    ws = []
    if wheels:
        for i, (data, c, r) in enumerate(t["wheels"]):
            w = L.link(bpy.data.objects.new("%s_w%d" % (name, i), data))
            w.parent = root
            w.location = c
            w.scale = (sx, sz, sz)
            w.rotation_euler = (0.0, 0.0, math.pi)
            ws.append(w)
    for k in ("tail", "head"):
        o = L.link(bpy.data.objects.new("%s_%s" % (name, k), lm[k]))
        o.parent = root
        o.visible_shadow = False
    c = FastCar()
    c.obj, c.model, c.wheels = root, model, ws
    c.wheel_r = t["wheels"][0][2] if t["wheels"] else 0.34
    c.brake = None
    if brake:
        b = L.link(bpy.data.objects.new("%s_brk" % name, lm["brake" if pool else "brake_np"]))
        b.parent = root
        b.visible_shadow = False
        c.brake = b
    return c


def drive_keys(car, frames, ys, x, z=ZR, step=1):
    """Key the car along y (x fixed) on the given frames; wheels roll with the distance."""
    vals = [(x, y, z) for y in ys]
    set_keys(car.obj, "location", frames, vals, "LINEAR")
    if car.wheels:
        d0 = ys[0]
        rot = [(abs(y - d0) / car.wheel_r, 0.0, math.pi) for y in ys]
        for w in car.wheels:
            set_keys(w, "rotation_euler", frames, rot, "LINEAR")


def free_lane(ctx, name, x, dirn, speed, spacing, y_lo, y_hi, rng, jitter=0.35, models=None, wheels=True):
    """Constant-speed traffic in one lane covering [y_lo, y_hi] for the whole shot (2 linear keys per car)."""
    T = ctx.frames
    v = speed * dirn / ctx.fps
    span = abs(v) * T
    lo, hi = y_lo - (span if dirn > 0 else 0.0), y_hi + (span if dirn < 0 else 0.0)
    cars = []
    y = lo + rng.uniform(0, spacing)
    k = 0
    while y < hi:
        y0 = y
        y1 = y0 + v * (T - 1)
        if max(y0, y1) >= y_lo - 10 and min(y0, y1) <= y_hi + 10:
            c = fast_car("%s%d" % (name, k), (x, y0, ZR), 0.0 if dirn > 0 else math.pi,
                         model=(models[rng.randrange(len(models))] if models else None), wheels=wheels)
            drive_keys(c, [1, T], [y0, y1], x)
            cars.append(c)
            k += 1
        y += spacing * rng.uniform(1.0 - jitter, 1.0 + jitter)
    return cars


def _y_at(o, f):
    for fc in _fcurves(o, "location"):
        if fc.array_index == 1:
            return fc.evaluate(f)
    return o.location.y


def newell_lane(ve, tau, delta, n_ahead, n_behind, T, fps, f_brake, dip, dip_s, amp=1.18, sub=2):
    """Car-following wave (Newell + amplification). Car index 0 = the braking driver; negative = ahead, positive =
    behind. Returns ({idx: [y per frame]}, {idx: [accel per frame]}) with y relative to car 0's start."""
    dt = 1.0 / (fps * sub)
    steps = T * sub + 1
    lag = int(round(tau / dt))
    gap = ve * tau + delta
    ids = list(range(-n_ahead, n_behind + 1))
    xs, vs = {}, {}
    for i in ids:
        xs[i] = [-(i * gap)] * 1
        vs[i] = [ve]
    t_b = (f_brake - 1) / float(fps)
    for s in range(1, steps):
        t = s * dt
        for i in ids:
            if i <= 0:
                if i == 0 and t_b <= t <= t_b + dip_s:
                    u = (t - t_b) / dip_s
                    vt = ve - dip * math.sin(math.pi * u) ** 2
                else:
                    vt = ve
                xn = xs[i][-1] + vt * dt
            else:
                sl = s - lag
                if sl < 0:
                    vl = ve
                    xl = xs[i - 1][0] + ve * (sl * dt)
                else:
                    vl = vs[i - 1][sl]
                    xl = xs[i - 1][sl]
                vt = max(0.0, min(ve, ve - amp * (ve - vl)))
                xn = min(xs[i][-1] + vt * dt, xl - delta)
                xn = max(xn, xs[i][-1])
            vs[i].append((xn - xs[i][-1]) / dt)
            xs[i].append(xn)
    Y, Acc = {}, {}
    for i in ids:
        Y[i] = [xs[i][(f - 1) * sub] for f in range(1, T + 1)]
        vv = [vs[i][(f - 1) * sub] for f in range(1, T + 1)]
        Acc[i] = [0.0] + [(vv[f] - vv[f - 1]) * fps for f in range(1, T)]
        Acc[i] = [(Acc[i][f], vv[f]) for f in range(T)]
    return Y, Acc


def brake_schedule(acc_v, thresh=-0.7, stop_v=0.6, hold=8):
    """[(frame, on)] transitions from per-frame (accel, speed); the light stays on >= `hold` frames."""
    out, on, last = [(1, False)], False, -99
    for f, (a, v) in enumerate(acc_v, start=1):
        want = a < thresh or v < stop_v
        if want and not on:
            on, last = True, f
            out.append((f, True))
        elif not want and on and f - last >= hold:
            on = False
            out.append((f, False))
    return out


def _smooth_frames(T, step=2):
    fr = list(range(1, T + 1, step))
    if fr[-1] != T:
        fr.append(T)
    return fr


# ================================================================ cameras
def _cam(ctx, loc, tgt, lens):
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = 0.5
    cam.data.clip_end = 20000.0
    return cam


def _keys(ctx, keys, interp="BEZIER"):
    for f, c, t in keys:
        kf(ctx.cam, "location", f, Vector(c), interp)
        kf(ctx.cam_target, "location", f, Vector(t), interp)


# ================================================================ aircraft helpers
AL_Z = 4.62      # airliner root height with the gear on the apron / taxiway


def airliner(ctx, name, loc, rot_z, gear=True):
    root, parts = A.make_airliner_v2(ctx, name, gear_down=gear)
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    return root, parts


def takeoff(ctx, name, f0, y0=60.0, v0=0.0):
    """Airliner lining up on runway 34 (x = 0) and taking off northbound from frame f0 (normal climb, gear up)."""
    T = ctx.frames
    root, parts = A.make_airliner_v2(ctx, name)
    A.flaps_to(parts, 1, 2, 0.45, 0.45)
    keys, rot = [], []
    y, v, z, pitch = y0, v0, 4.42, 0.0
    for f in range(1, T + 1):
        dt = 1.0 / ctx.fps
        if f >= f0:
            if v < 78.0:
                v += 2.6 * dt
            else:
                v += 0.6 * dt
                pitch = min(9.0, pitch + 4.5 * dt)
                z += v * math.sin(math.radians(pitch)) * dt
            y += v * dt
        if f % 3 == 1 or f == T:
            keys.append((f, (0.0, y, z)))
            rot.append((f, pitch))
    tr = A._track(name + "_track", keys, "LINEAR")
    root.parent = tr
    for f, pt in rot:
        kf(root, "rotation_euler", f, Vector((math.radians(pt), 0, 0)), "LINEAR")
    f_up = next((f for f, pt in rot if pt >= 8.9), None)
    if f_up is not None and f_up + 40 < T:
        A.gear_to(parts, f_up + 10, min(T - 1, f_up + 60), down=False)
    return root, tr


# ================================================================ BUILDERS
def b_travel_hook(ctx, p):
    """High aerial along the busy interstate (both directions full, still moving) between the suburbs and the
    fields, downtown on the horizon; an airliner climbs across the sky. Camera drifts forward and rises.
    Anchors: car (a car in the middle of the northbound lanes), plane."""
    T = ctx.frames
    build_travel_world(ctx, p)
    rng = random.Random(11)
    lo, hi = p.get("y_range", (-1100.0, 2400.0))
    mid = []
    for i, x in enumerate(NB):
        cs = free_lane(ctx, "nb%d_" % i, x, 1, (27.0, 25.0, 23.0)[i], (26.0, 24.0, 22.0)[i], lo, hi, rng, wheels=False)
        if i == 1:
            mid = cs
    for i, x in enumerate(SB):
        free_lane(ctx, "sb%d_" % i, x, -1, (28.0, 26.0, 24.0)[i], (30.0, 28.0, 26.0)[i], lo, hi, rng, wheels=False)
    S._repaint_kenney()
    # anchor car = the middle-lane car nearest car_y at frame 1
    yc = p.get("car_y", -350.0)
    car = min(mid, key=lambda c: abs(_y_at(c.obj, 1) - yc))
    # airliner climbing out across the sky (north-west), well above the highway
    root, parts = A.make_airliner_v2(ctx, "al_sky")
    A.gear_to(parts, 1, 2, down=False)
    pa, pb = Vector(p.get("plane_a", (HX - 330.0, -260.0, 175.0))), Vector(p.get("plane_b", (HX + 120.0, -60.0, 205.0)))
    d = (pb - pa).normalized()
    tr = A._track("al_sky_track", [(1, tuple(pa)), (T, tuple(pb))])
    root.parent = tr
    root.rotation_euler = (math.radians(7), 0, math.atan2(-d.x, d.y))
    c0 = p.get("cam0", (HX + 70.0, -980.0, 150.0))
    t0 = p.get("tgt0", (HX - 230.0, 1400.0, 0.0))
    c1 = p.get("cam1", (HX + 70.0, -900.0, 172.0))
    t1 = p.get("tgt1", (HX - 230.0, 1480.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 28))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "car", car.obj, (0, 0, 1.6))
    S.anchor(ctx, "plane", root, (0, 0, 2.0))


def b_taxi_queue_v2(ctx, p):
    """A queue of airliners on the taxiway, nose to tail, inching towards the runway (stop-and-go); one airliner
    takes off on the runway behind them. Camera low beside the holding point."""
    T = ctx.frames
    build_travel_world(ctx, p)
    # queue on the taxiway (x = TWY_X), heading south (-y) to the runway 34 holding point (connector at y = 25)
    n = p.get("count", 5)
    base = [140.0 + 62.0 * k for k in range(n)]
    roots = []
    f_go = [int(T * u) for u in (0.12, 0.55)]
    for k, y in enumerate(base):
        r, parts = airliner(ctx, "q%d" % k, (S.TWY_X, y, AL_Z), math.pi)
        # creep forward 14 m twice (stop-and-go), each plane slightly after the one ahead
        ys = [y]
        keys = [(1, y)]
        cur = y
        for g in f_go:
            fs = g + k * 10
            keys.append((fs, cur))
            cur -= 14.0
            keys.append((fs + 75, cur))
        for f, yy in keys:
            kf(r, "location", f, Vector((S.TWY_X, yy, AL_Z)), "BEZIER")
        roots.append(r)
    takeoff(ctx, "al_to", p.get("to_frame", int(T * 0.15)), y0=40.0, v0=0.0)
    S._repaint_kenney()
    c0 = p.get("cam0", (98.0, 72.0, 13.0))
    t0 = p.get("tgt0", (119.0, 260.0, 7.0))
    c1 = p.get("cam1", (96.0, 84.0, 14.0))
    t1 = p.get("tgt1", (119.0, 268.0, 7.0))
    _cam(ctx, c0, t0, p.get("lens", 26))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "queue", roots[0], (0, 0, 6.0))


def b_phantom_jam_v2(ctx, p):
    """Dense northbound traffic; on `brake_cue` one driver brakes briefly, every driver behind brakes a bit later
    and harder: a wave of brake lights rolls backwards towards the camera (stop-and-go, no contact).
    Southbound flows freely. Anchor: first (the braking car)."""
    T = ctx.frames
    build_travel_world(ctx, p)
    fps = ctx.fps
    f_b = ctx.word_time(p.get("brake_cue", "taps"), 0.3)
    Y0 = p.get("y0", 1500.0)                  # car 0's start position (middle lane)
    ve, tau, delta = p.get("ve", 17.0), p.get("tau", 0.85), p.get("delta", 8.0)
    rng = random.Random(21)
    fr = _smooth_frames(T, 2)
    first = None
    for li, x in enumerate(NB):
        lag = (0, 22, 40)[[1, 0, 2].index(li)]          # middle lane first, then left, then right
        dip = (11.0, 10.0, 9.0)[[1, 0, 2].index(li)]
        off = (0.0, 9.0, -7.0)[li]
        Y, Acc = newell_lane(ve, tau, delta, 14, 48, T, fps, f_b + lag, dip, 2.2)
        for i in sorted(Y):
            ys = [Y0 + off + Y[i][f - 1] for f in fr]
            c = fast_car("jam%d_%d" % (li, i + 20), (x, ys[0], ZR), 0.0, brake=True, wheels=(i > -3 and i < 30))
            drive_keys(c, fr, ys, x)
            show_keys(c.brake, brake_schedule(Acc[i]))
            if li == 1 and i == 0:
                first = c
    for i, x in enumerate(SB):
        free_lane(ctx, "sb%d_" % i, x, -1, (29.0, 27.0, 25.0)[i], (46.0, 40.0, 36.0)[i], 600, 3200, rng)
    S._repaint_kenney()
    S.anchor(ctx, "first", first.obj, (0, 0, 1.8))
    c0 = p.get("cam0", (HX + 22.0, Y0 - 110.0, 30.0))
    t0 = p.get("tgt0", (HX + 8.0, Y0 + 230.0, 0.0))
    c1 = p.get("cam1", (HX + 22.0, Y0 - 135.0, 31.0))
    t1 = p.get("tgt1", (HX + 8.0, Y0 + 205.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 40))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_long_drive_v2(ctx, p):
    """Chase cam behind one car on a long, open interstate. Late in the beat (`close_cue`) it speeds up and closes
    in on the car ahead (tailgating, no contact); the car ahead's brake lights flash on `brake_cue`."""
    T = ctx.frames
    build_travel_world(ctx, p)
    fps = ctx.fps
    x = NB[1]
    v = p.get("speed", 30.0)
    y_start = p.get("y0", -1800.0)
    f_close = ctx.word_time(p.get("close_cue", "speed"), 0.85)
    f_brk = ctx.word_time(p.get("brake_cue", "tailgate"), 0.95)
    gap0, gap1 = 38.0, 9.0
    hero_y, lead_y = [], []
    hy, ly = y_start, y_start + gap0 + 4.4
    close_v = (gap0 - gap1) / max(1.0, (f_brk - 1) / float(fps))
    for f in range(1, T + 1):
        hero_y.append(hy)
        lead_y.append(ly)
        g = ly - hy - 4.4
        hv = v + (close_v if g > gap1 else 0.0)
        hy += hv / fps
        ly += v / fps
    hero = L.make_car("hero", loc=(x, y_start, ZR), rot_z=0.0, headlights=True, glow=False, model=p.get("hero", "suv"))
    L.drive(hero, [(x, y) for y in hero_y], 1)
    lead = fast_car("lead", (x, lead_y[0], ZR), 0.0, model=p.get("lead_model", "sedan"), brake=True, pool=False)
    drive_keys(lead, list(range(1, T + 1, 2)) + ([T] if (T - 1) % 2 else []),
               [lead_y[f - 1] for f in (list(range(1, T + 1, 2)) + ([T] if (T - 1) % 2 else []))], x)
    show_keys(lead.brake, [(1, False), (f_brk, True), (f_brk + 18, False)])
    rng = random.Random(31)
    # sparse traffic: other lanes (ahead, same speed band) + oncoming
    free_lane(ctx, "nbL_", NB[0], 1, v + 1.5, 140.0, y_start - 200, y_start + 2600, rng)
    free_lane(ctx, "nbR_", NB[2], 1, v - 2.5, 120.0, y_start - 200, y_start + 2600, rng)
    for i, xx in enumerate(SB):
        free_lane(ctx, "sb%d_" % i, xx, -1, (31.0, 29.0, 27.0)[i], (90.0, 75.0, 110.0)[i], y_start, y_start + 3200, rng)
    S._repaint_kenney()
    # chase camera parented to an empty following the hero
    rig = L.link(bpy.data.objects.new("rig", None))
    fr = list(range(1, T + 1, 3)) + [T]
    set_keys(rig, "location", fr, [(x, hero_y[f - 1], ZR) for f in fr], "LINEAR")
    cam = _cam(ctx, (x + p.get("cam_dx", 1.6), -13.0, 5.2), (x, 70.0, 1.2), p.get("lens", 30))
    cam.location = (p.get("cam_dx", 1.6), -13.0, 5.2)
    cam.parent = rig
    ctx.cam_target.location = (0.0, 70.0, 1.2)
    ctx.cam_target.parent = rig
    S.anchor(ctx, "lead", lead.obj, (0, -2.2, 1.6))


def b_gates_v2(ctx, p):
    """Airliners parked nose-in at the terminal gates; one is pushed back (slowly) while the others wait.
    Seen from the apron; the departures board is a 2D overlay."""
    T = ctx.frames
    build_travel_world(ctx, p)
    gates = p.get("gates", [505.0, 545.0, 585.0])
    roots = []
    for k, gy in enumerate(gates):
        r, parts = airliner(ctx, "gate%d" % k, (273.0 - 19.5 - 3.0, gy, AL_Z), -math.pi / 2)
        roots.append(r)
    # jet bridges (simple boxes from the terminal face to the forward door, port side = +y when facing +x)
    jb = S.pbr("tv_jetbridge", hexc("d4d6d8"), 0.5, 0.2, var=0.03)
    for k, gy in enumerate(gates):
        bm = bmesh.new()
        S.bm_box(bm, (266.0, gy + 6.5, 5.0), (14.0, 2.8, 3.0), 0)
        S.bm_box(bm, (262.0, gy + 6.5, 2.0), (0.8, 0.8, 4.0), 0)
        S.obj("jetbridge%d" % k, S.mesh_from_bm("jetbridge", bm, [jb]))
    # pushback on the middle gate from `push_cue`: plane rolls back 40 m and turns
    f_push = ctx.word_time(p.get("push_cue", "late"), 0.55)
    r = roots[1]
    x0 = r.location.x
    kf(r, "location", 1, Vector((x0, gates[1], AL_Z)), "CONSTANT")
    kf(r, "location", f_push, Vector((x0, gates[1], AL_Z)), "BEZIER")
    kf(r, "location", T, Vector((x0 - 30.0, gates[1] - 6.0, AL_Z)), "BEZIER")
    kf(r, "rotation_euler", f_push, Vector((0, 0, -math.pi / 2)), "BEZIER")
    kf(r, "rotation_euler", T, Vector((0, 0, -math.pi / 2 - 0.22)), "BEZIER")
    # apron service vans (static)
    for k, (vx, vy, rz) in enumerate(((236.0, 470.0, 0.3), (240.0, 566.0, 2.2), (228.0, 622.0, 1.4))):
        L.make_car("apron_van%d" % k, loc=(vx, vy, 0.3), rot_z=rz, headlights=False, glow=False,
                   model=("van", "delivery", "van")[k])
    S._repaint_kenney()
    c0 = p.get("cam0", (200.0, 438.0, 9.0))
    t0 = p.get("tgt0", (256.0, 560.0, 13.0))
    c1 = p.get("cam1", (196.0, 446.0, 9.5))
    t1 = p.get("tgt1", (254.0, 562.0, 13.0))
    _cam(ctx, c0, t0, p.get("lens", 22))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])
    S.anchor(ctx, "push", r, (0, 0, 6.0))


def _annulus(bm, r, w, seg=96):
    inner, outer = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        c, s_ = math.cos(a), math.sin(a)
        inner.append(bm.verts.new(((r - w / 2) * c, (r - w / 2) * s_, 0.0)))
        outer.append(bm.verts.new(((r + w / 2) * c, (r + w / 2) * s_, 0.0)))
    for k in range(seg):
        j = (k + 1) % seg
        bm.faces.new((inner[k], outer[k], outer[j], inner[j]))
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()


def ripple_rings(ctx, center, f0, count=3, gap=14, r1=60.0, life=40, color=hexc("ffa21a"), name="rip"):
    """Amber rings spreading on the ground (real geometry; opacity via emission strength)."""
    for k in range(count):
        m, sock = L.add_mat("%s_m%d" % (name, k), color, 0.0)
        bm = bmesh.new()
        _annulus(bm, 1.0, 0.06, 96)
        o = S.obj("%s%d" % (name, k), S.mesh_from_bm(name, bm, [m]), center)
        o.visible_shadow = False
        fk = f0 + k * gap
        set_keys(o, "scale", [1, fk, fk + life], [(0.02, 0.02, 1), (2.0, 2.0, 1), (r1, r1, 1)], "LINEAR")
        L.kf_socket(sock, 1, 0.0, "CONSTANT")
        L.kf_socket(sock, fk, 0.0, "LINEAR")
        L.kf_socket(sock, fk + 4, 6.0, "LINEAR")
        L.kf_socket(sock, fk + life, 0.0, "LINEAR")


def build_dominoes(path, f_topple, step, th=1.1, h=9.0, w=4.6, sp=4.3, z=0.3):
    """Big white lacquered dominoes (navy pips, red divider) along a polyline; toppled one after another."""
    pts = [Vector(q) for q in path]
    segs, total = [], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ln = (b - a).length
        segs.append((a, b, total, ln))
        total += ln

    def at(s):
        for a, b, s0, ln in segs:
            if s <= s0 + ln:
                return a.lerp(b, (s - s0) / ln), (b - a).normalized()
        a, b = segs[-1][0], segs[-1][1]
        return b, (b - a).normalized()
    body = S.pbr("tv_domino", hexc("f4f4f1"), 0.2, coat=0.8, var=0.0)
    pip = S.pbr("tv_pip", hexc("1d3566"), 0.3, var=0.0)
    red = S.pbr("tv_divider", hexc("d8262f"), 0.3, var=0.0)
    rng = random.Random(8)
    count = int(total / sp)
    doms = []
    lay = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
           5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
    for i in range(count):
        p, t = at(i * sp + 1.0)
        bm = bmesh.new()
        S.bm_box(bm, (0, -th / 2, h / 2), (w, th, h), 0)
        for fy in (0.02, -th - 0.02):          # both faces: divider + pips
            S.bm_box(bm, (0, fy, h / 2), (w - 0.5, 0.06, 0.16), 2)
        for half in (0, 1):
            zc = h * (0.25 if half == 0 else 0.75)
            for u, v in lay[rng.randint(1, 6)]:
                for fy in (0.02, -th - 0.02):
                    S.bm_box(bm, (u * 1.15, fy, zc + v * 1.15), (0.62, 0.06, 0.62), 1)
        yaw = math.atan2(-t.x, t.y)
        o = S.obj("dom%d" % i, S.mesh_from_bm("dom%d" % i, bm, [body, pip, red]), (p.x, p.y, z), (0, 0, yaw))
        doms.append(o)
    gap = sp - th
    a1 = math.asin(min(1.0, gap / h))
    rest = math.radians(72.0)
    for i, o in enumerate(doms):
        fi = int(round(f_topple + i * step))
        yaw = o.rotation_euler.z
        last = i == len(doms) - 1
        set_keys(o, "rotation_euler",
                 [1, fi, fi + max(2, int(round(step))), fi + max(2, int(round(step))) + 8],
                 [(0, 0, yaw), (0, 0, yaw), (-a1, 0, yaw), (-(math.radians(88.0) if last else rest), 0, yaw)],
                 "LINEAR")
    return doms


def b_delay_dominoes_v2(ctx, p):
    """Metaphor: a long row of big dominoes on the airport taxiway (hangars behind). On `topple_cue` the first one
    tips and the row falls away from the camera; amber rings spread from the first domino on `ring_cue`."""
    T = ctx.frames
    build_travel_world(ctx, p)
    f_t = ctx.word_time(p.get("topple_cue", "storm"), 0.25)
    f_r = ctx.word_time(p.get("ring_cue", "hub"), 0.5)
    path = p.get("path", [(96.0, 1150.0), (108.0, 1085.0), (118.0, 1015.0), (114.0, 950.0), (104.0, 895.0)])
    probe = int(sum((Vector(b) - Vector(a)).length for a, b in zip(path[:-1], path[1:])) / 4.3)
    step = p.get("step", max(2.0, min(5.0, (T - 20 - f_t) / max(1, probe))))
    doms = build_dominoes(path, f_t, step)
    print("[v2 travel] %d dominoes, topple from f%d, step %.2f" % (len(doms), f_t, step))
    ripple_rings(ctx, (path[0][0], path[0][1] - 2.0, 0.42), f_r)
    S._repaint_kenney()
    S.anchor(ctx, "first", doms[0], (0, 0, 10.0))
    c0 = p.get("cam0", (138.0, 832.0, 12.0))
    t0 = p.get("tgt0", (104.0, 1010.0, 3.0))
    c1 = p.get("cam1", (140.0, 826.0, 14.0))
    t1 = p.get("tgt1", (104.0, 1000.0, 2.0))
    _cam(ctx, c0, t0, p.get("lens", 26))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_smooth_flow_v2(ctx, p):
    """Takeaway: light traffic with big gaps flowing smoothly; the camera travels with the middle lane.
    Anchors gap_top (rear of the car ahead) and gap_bot (front of the car behind) for a 2D gap bar."""
    T = ctx.frames
    build_travel_world(ctx, p)
    rng = random.Random(41)
    v = p.get("speed", 29.0)
    y_cam0 = p.get("y0", 1000.0)
    # the measured pair in the middle lane, moving at the camera speed
    pair = []
    for k, dy in enumerate((150.0, 200.0)):
        c = fast_car("pair%d" % k, (NB[1], y_cam0 + dy, ZR), 0.0, model=("suv", "sedan")[k])
        drive_keys(c, [1, T], [y_cam0 + dy, y_cam0 + dy + v * (T - 1) / ctx.fps], NB[1])
        pair.append(c)
    free_lane(ctx, "mid_", NB[1], 1, v, 52.0, y_cam0 + 255, y_cam0 + 2600, rng, jitter=0.0)
    free_lane(ctx, "mid0_", NB[1], 1, v, 52.0, y_cam0 - 200, y_cam0 + 95, rng, jitter=0.0)
    free_lane(ctx, "fast_", NB[0], 1, v + 2.0, 60.0, y_cam0 - 300, y_cam0 + 2600, rng, jitter=0.15)
    free_lane(ctx, "slow_", NB[2], 1, v - 3.0, 56.0, y_cam0 - 100, y_cam0 + 2600, rng, jitter=0.15)
    for i, xx in enumerate(SB):
        free_lane(ctx, "sb%d_" % i, xx, -1, (30.0, 28.0, 26.0)[i], (70.0, 64.0, 80.0)[i], y_cam0 - 300, y_cam0 + 2800, rng)
    S._repaint_kenney()
    rig = L.link(bpy.data.objects.new("rig", None))
    set_keys(rig, "location", [1, T], [(0, y_cam0, 0), (0, y_cam0 + v * (T - 1) / ctx.fps, 0)], "LINEAR")
    cam = _cam(ctx, (0, 0, 0), (0, 0, 0), p.get("lens", 32))
    cam.location = p.get("cam_off", (HX + 16.0, -12.0, 22.0))
    cam.parent = rig
    ctx.cam_target.location = p.get("tgt_off", (HX + 6.0, 150.0, 0.0))
    ctx.cam_target.parent = rig
    S.anchor(ctx, "gap_top", pair[1].obj, (0, -2.2, 0.6))
    S.anchor(ctx, "gap_bot", pair[0].obj, (0, 2.2, 0.6))


def b_travel_outro(ctx, p):
    """Crane-up from beside the interstate to a wide view of the highway, suburbs and airport while an airliner
    climbs out."""
    T = ctx.frames
    build_travel_world(ctx, p)
    rng = random.Random(51)
    for i, x in enumerate(NB):
        free_lane(ctx, "nb%d_" % i, x, 1, (27.0, 25.0, 23.0)[i], (30.0, 27.0, 25.0)[i], -1600, 2400, rng)
    for i, x in enumerate(SB):
        free_lane(ctx, "sb%d_" % i, x, -1, (28.0, 26.0, 24.0)[i], (32.0, 30.0, 28.0)[i], -1600, 2400, rng)
    S._repaint_kenney()
    root, parts = A.make_airliner_v2(ctx, "al_sky")
    A.gear_to(parts, 1, 2, down=False)
    pa, pb = Vector((HX - 60.0, 0.0, 75.0)), Vector((HX - 320.0, 900.0, 160.0))
    d = (pb - pa).normalized()
    tr = A._track("al_sky_track", [(1, tuple(pa)), (T, tuple(pb))])
    root.parent = tr
    root.rotation_euler = (math.radians(6), 0, math.atan2(-d.x, d.y))
    c0 = p.get("cam0", (HX + 40.0, -120.0, 14.0))
    t0 = p.get("tgt0", (HX - 120.0, 500.0, 10.0))
    c1 = p.get("cam1", (HX + 160.0, -700.0, 240.0))
    t1 = p.get("tgt1", (HX - 420.0, 1300.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 26))
    _keys(ctx, [(1, c0, t0), (T, c1, t1)])


S.V2_BUILDERS.update({
    "travel_hook": b_travel_hook,
    "taxi_queue_v2": b_taxi_queue_v2,
    "phantom_jam_v2": b_phantom_jam_v2,
    "long_drive_v2": b_long_drive_v2,
    "gates_v2": b_gates_v2,
    "delay_dominoes_v2": b_delay_dominoes_v2,
    "smooth_flow_v2": b_smooth_flow_v2,
    "travel_outro": b_travel_outro,
})

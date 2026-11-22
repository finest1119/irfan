"""Geo / politics / explainer-graphics builders (added for video #3, "nuclear weapons", 22 Nov 2026).

Kept in a separate module so scene_lib.py (shared with other episodes) stays untouched.
Importing this module registers its builders into scene_lib.BUILDERS. render_episode.py imports it
lazily, only when a shot asks for a builder that scene_lib does not have.

Neutral, symbolic visuals only: an abstract globe (lat/long grid, no coastlines) with coloured
markers, a round table with three empty chairs and flags as simple colour blocks, bar charts,
inspection / satellite icons, a balance board, a risk gauge. No weapons, explosions, war imagery,
faces or caricatures.

Builders: globe_summit, round_table, treaty_doc, cap_bars, verify_checks, three_balance,
          stock_bars, three_lower, risk_gauge   (params documented in pipeline/README.md)
"""
import math

import bpy
from mathutils import Vector

import scene_lib as L
from scene_lib import hexc, kf, NAVY, NAVY2, TEAL, TEAL_DARK, RED, WHITE, FONT_PATH, FONT_PATH_SUB

# country accent colours (taken from each flag, used consistently across shots)
C_US = hexc("4f8dff")
C_RU = hexc("e6ecf3")
C_CN = hexc("ffc53d")
COUNTRY = {"US": C_US, "RUSSIA": C_RU, "CHINA": C_CN}
STEEL = hexc("5c6f86")
PAPER = hexc("eef1f4")
INK = hexc("1b2740")


# ---------------------------------------------------------------- helpers
def _env(ctx, bg=NAVY, sun=2.4, sun_rot=(50, 0, 35), fog_density=0.0, fog_start=20.0):
    L.fog(fog_density, bg, start=fog_start)
    L.setup_world(ctx.scene, bg, 1.0)
    return L.add_sun(sun, sun_rot)


def _floor(color=hexc("0e1b33"), size=400, z=0.0, rough=0.35):
    return L.plane("floor", size, size, (0, 0, z), L.mat("floor_geo", color, rough=rough, metal=0.1))


def _polyline(name, pts, radius, material, cyclic=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    sp.use_cyclic_u = cyclic
    o = L.link(bpy.data.objects.new(name, cu))
    o.data.materials.append(material)
    o.visible_shadow = False
    return o


def _pop_in(ctx, o, appear, disappear=None):
    ctx._pop(o, appear, disappear)


def _sub(ctx, text, y, appear, size=0.024, panel=None, color=None, disappear=None):
    return ctx.text(text, 0.5, y, size, color or hexc("dff3f6"), FONT_PATH_SUB, appear=appear,
                    disappear=disappear, d=1.99, panel=panel or hexc("0d3b4f"), max_w_frac=0.8)


def _chip(ctx, text, y, appear, panel=NAVY, size=0.027, disappear=None):
    return ctx.text(text, 0.5, y, size, WHITE, FONT_PATH, appear=appear, disappear=disappear,
                    panel=panel, max_w_frac=0.7)


def _cue(ctx, p, key, default_word, frac):
    return ctx.word_time(p.get(key, default_word), frac)


def _rooted_box(name, size, base, material, bevel=0.03):
    """Box whose parent empty sits at the base centre, so scaling the root grows it upwards."""
    root = L.link(bpy.data.objects.new(name + "_root", None))
    root.location = base
    b = L.box(name, size, (0, 0, 0), material, bevel=bevel)
    b.parent = root
    b.location = (0, 0, size[2] / 2.0)
    return root, b


def _flag(name, kind, loc, w=1.7, h=1.1, rot_z=0.0):
    """Simplified flag as colour blocks on a thin pole. kind: US / RUSSIA / CHINA."""
    root = L.link(bpy.data.objects.new(name, None))
    root.location = loc
    root.rotation_euler = (0, 0, math.radians(rot_z))
    pole = L.cylinder(name + "_pole", 0.03, 2.9, (0, 0, 0), material=L.mat("pole", hexc("9aa8b8"), 0.4, 0.6))
    pole.parent = root
    pole.location = (-w / 2 - 0.05, 0, 1.45)
    z0 = 2.85 - h  # bottom edge of the flag

    def blk(nm, x0, x1, za, zb, col):
        b = L.box(name + nm, (x1 - x0, 0.03, zb - za), (0, 0, 0), L.mat("flag_" + nm, col, rough=0.7))
        b.parent = root
        b.location = ((x0 + x1) / 2.0 - w / 2, 0, (za + zb) / 2.0)
        return b
    red, white, blue = hexc("c8303e"), hexc("eef1f4"), hexc("2a4a9a")
    if kind == "RUSSIA":
        for i, col in enumerate((red, blue, white)):
            blk("s%d" % i, 0, w, z0 + i * h / 3, z0 + (i + 1) * h / 3, col)
    elif kind == "CHINA":
        blk("bg", 0, w, z0, z0 + h, hexc("d6303a"))
        b = blk("st", 0.18, 0.5, z0 + h - 0.45, z0 + h - 0.13, hexc("ffd23f"))
        b.location.y = -0.02
    else:  # US: stripes + canton
        n = 7
        for i in range(n):
            blk("s%d" % i, 0, w, z0 + i * h / n, z0 + (i + 1) * h / n, red if i % 2 == 0 else white)
        c = blk("ca", 0, w * 0.42, z0 + h * 3 / 7, z0 + h, blue)
        c.location.y = -0.02
    return root


def _label(ctx, body, loc, size, color, appear=1, font=FONT_PATH):
    """Camera-facing 3D label that stays upright (TRACK_TO with world-up), unlike label3d's damped track."""
    o = L.label3d(ctx, body, loc, size, color, rot=(0, 0, 0), font=font, face_cam=False, appear=appear)
    c = o.constraints.new("TRACK_TO")
    c.target = ctx.cam
    c.track_axis = "TRACK_Z"
    c.up_axis = "UP_Y"
    return o


def _ring(name, r, z, radius, material):
    pts = [(r * math.cos(a / 48.0 * 2 * math.pi), r * math.sin(a / 48.0 * 2 * math.pi), z) for a in range(48)]
    return _polyline(name, pts, radius, material, cyclic=True)


def _sphere_pt(r, lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return Vector((r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la)))


def _orient_to(o, normal):
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = normal.normalized().to_track_quat("Z", "Y")


# ================================================================ BUILDERS
def b_globe_summit(ctx, p):
    """Abstract globe (lat/long grid, no coastlines). US, Russia, China markers light up on their cue
    words; a Shenzhen pin drops and arcs link the three to it. Camera drifts and pushes in."""
    _env(ctx, NAVY, 1.6, (40, 0, 120))
    T = ctx.frames
    R = 5.0
    globe = L.link(bpy.data.objects.new("globe", None))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=R)
    s = bpy.context.object
    s.data.materials.append(L.mat("ocean", hexc("12305e"), rough=0.55))
    bpy.ops.object.shade_smooth()
    s.parent = globe
    grid = L.emissive("grid", TEAL, 0.9)
    for lat in range(-60, 90, 30):
        pts = [_sphere_pt(R * 1.004, lat, lo) for lo in range(0, 360, 6)]
        _polyline("lat%d" % lat, pts, 0.012, grid, cyclic=True).parent = globe
    for lon in range(0, 360, 30):
        pts = [_sphere_pt(R * 1.004, la, lon) for la in range(-90, 91, 6)]
        _polyline("lon%d" % lon, pts, 0.012, grid).parent = globe
    # atmosphere rim
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=R * 1.06)
    rim = bpy.context.object
    rim.data.materials.append(L.flat_mat("rim", hexc("2fd0d6"), alpha=0.07))
    rim.visible_shadow = False

    cam_dir = lambda lat, lon, d: _sphere_pt(d, lat, lon)  # noqa: E731
    cam = ctx.camera(cam_dir(30, -170, 44), target=(0, 0, 0), lens=35)
    f_pin = _cue(ctx, p, "pin_cue", "shenzhen", 0.45)
    keys = []
    for k in range(0, 5):
        t = k / 4.0
        lat = 30 + 8 * t
        lon = -170 - 22 * t
        d = 44 - 5 * L.smooth(t)
        keys.append((1 + int(t * (T - 1)), cam_dir(lat, lon, d)))
    L.animate_cam(ctx, keys)
    L.animate_target(ctx, [(1, (0, 0, 1.8)), (T, (0, 0, 1.5))])

    cues = p.get("cues", ["trump", "xi", "putin"])
    places = [("US", 39.0, -98.0), ("CHINA", 34.0, 103.0), ("RUSSIA", 61.0, 85.0)]
    shen = _sphere_pt(R, 22.5, 114.1)
    for i, (nm, lat, lon) in enumerate(places):
        f = ctx.word_time(cues[i], 0.08 + 0.1 * i) if i < len(cues) else ctx.f(0.5 + i)
        col = COUNTRY[nm]
        pos = _sphere_pt(R * 1.01, lat, lon)
        spot = L.cylinder("spot_" + nm, 0.75, 0.02, (0, 0, 0), material=L.flat_mat("spot_" + nm, col, alpha=0.3), verts=32)
        spot.location = pos
        _orient_to(spot, pos)
        spot.visible_shadow = False
        _pop_in(ctx, spot, f)
        dot = L.cylinder("dot_" + nm, 0.22, 0.12, (0, 0, 0), material=L.emissive("dot_" + nm, col, 3.0), verts=16)
        dot.location = _sphere_pt(R * 1.02, lat, lon)
        _orient_to(dot, pos)
        _pop_in(ctx, dot, f)
        gl = L.billboard("glow_" + nm, 2.2, _sphere_pt(R * 1.05, lat, lon), L.glow_mat("glow_" + nm, col, 2.5), cam)
        _pop_in(ctx, gl, f)
        lbl = _label(ctx, nm, _sphere_pt(R * 1.18, lat + 7, lon), 0.62, col, appear=f)
        # arc to Shenzhen, drawn from the pin cue
        n = 40
        a, b = pos.normalized(), shen.normalized()
        pts = []
        for j in range(n + 1):
            t = j / float(n)
            v = a.slerp(b, t) if hasattr(a, "slerp") else (a * (1 - t) + b * t).normalized()
            pts.append(v * R * (1.02 + 0.28 * math.sin(math.pi * t)))
        arc = _polyline("arc_" + nm, pts, 0.035, L.emissive("arc_" + nm, col, 2.5))
        kf(arc.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
        kf(arc.data, "bevel_factor_end", f_pin + 2 + 3 * i, 0.0, "BEZIER")
        kf(arc.data, "bevel_factor_end", f_pin + 26 + 3 * i, 1.0, "BEZIER")
    # Shenzhen pin
    pin_root = L.link(bpy.data.objects.new("pin", None))
    pin_root.location = _sphere_pt(R * 1.0, 22.5, 114.1)
    _orient_to(pin_root, shen)
    stem = L.cylinder("pin_stem", 0.05, 0.9, (0, 0, 0), material=L.mat("pinstem", WHITE, 0.3))
    stem.parent = pin_root
    stem.location = (0, 0, 0.45)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.24)
    head = bpy.context.object
    head.data.materials.append(L.emissive("pinhead", RED, 3.0))
    head.parent = pin_root
    head.location = (0, 0, 0.95)
    kf(pin_root, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
    kf(pin_root, "scale", f_pin, Vector((0.001, 0.001, 0.001)), "BEZIER")
    kf(pin_root, "scale", f_pin + 6, Vector((1.2, 1.2, 1.2)), "BEZIER")
    kf(pin_root, "scale", f_pin + 10, Vector((1, 1, 1)), "BEZIER")
    L.billboard("pin_glow", 1.6, _sphere_pt(R * 1.2, 22.5, 114.1), L.glow_mat("pin_glow", RED, 3.0), cam)
    pg = bpy.data.objects["pin_glow"]
    _pop_in(ctx, pg, f_pin + 4)
    sz_pos = shen + (keys[-1][1] - shen).normalized() * 2.5 + Vector((0, 0, -0.9))  # in front of the globe
    _label(ctx, "SHENZHEN", tuple(sz_pos), 0.45, WHITE, appear=f_pin + 6)
    if p.get("card"):
        ctx.card(p["card"], p.get("subcard"), y_frac=0.14, size=0.05)


def b_round_table(ctx, p):
    """Round table, three empty chairs, flags as colour blocks, an unsigned document in the middle."""
    _env(ctx, NAVY, 1.4, (55, 0, 25))
    L.add_sun(1.6, (60, 0, -70))
    T = ctx.frames
    _floor(hexc("101d38"))
    spot = bpy.data.lights.new("TableSpot", "SPOT")
    spot.energy = 2600
    spot.spot_size = math.radians(70)
    spot.spot_blend = 0.6
    spot.color = (1.0, 0.96, 0.9)
    so = L.link(bpy.data.objects.new("TableSpot", spot))
    so.location = (0, 0, 9)
    wood = L.mat("table", hexc("2b3d5c"), rough=0.45)
    L.cylinder("tabletop", 2.6, 0.18, (0, 0, 1.0), material=wood, verts=48)
    L.cylinder("tabletrim", 2.64, 0.06, (0, 0, 0.9), material=L.mat("trim", TEAL_DARK, 0.4), verts=48)
    L.cylinder("tableleg", 0.35, 0.9, (0, 0, 0.45), material=wood, verts=16)
    chair_m = L.mat("chair", hexc("3a4a66"), rough=0.6)
    seats = [("US", -90), ("CHINA", 30), ("RUSSIA", 150)]
    for nm, ang in seats:
        a = math.radians(ang)
        d = Vector((math.cos(a), math.sin(a), 0))
        root = L.link(bpy.data.objects.new("chair_" + nm, None))
        root.location = d * 3.4
        root.rotation_euler = (0, 0, a - math.pi / 2)
        for (sz, lc) in (((1.0, 0.95, 0.12), (0, 0, 0.62)), ((1.0, 0.12, 1.1), (0, 0.45, 1.2)),
                         ((0.08, 0.08, 0.6), (-0.4, -0.4, 0.3)), ((0.08, 0.08, 0.6), (0.4, -0.4, 0.3)),
                         ((0.08, 0.08, 0.6), (-0.4, 0.4, 0.3)), ((0.08, 0.08, 0.6), (0.4, 0.4, 0.3))):
            b = L.box("ch", sz, (0, 0, 0), chair_m, bevel=0.03)
            b.parent = root
            b.location = lc
        # colour band on the chair back = country accent
        band = L.box("band_" + nm, (1.0, 0.13, 0.16), (0, 0, 0), L.emissive("band_" + nm, COUNTRY[nm], 1.6))
        band.parent = root
        band.location = (0, 0.45, 1.68)
        _flag("flag_" + nm, nm, tuple(d * 4.9), rot_z=ang + 90)
        # place card on the table
        pc = L.box("place_" + nm, (0.7, 0.05, 0.22), (0, 0, 0), L.mat("place_" + nm, COUNTRY[nm], 0.5))
        pc.location = d * 2.05 + Vector((0, 0, 1.2))
        pc.rotation_euler = (math.radians(-12) * 0, 0, a + math.pi / 2)
    # unsigned document
    doc = L.plane("doc", 1.0, 1.35, (0, 0, 1.1), L.mat("paper", PAPER, rough=0.8, fog=False))
    doc.rotation_euler = (0, 0, math.radians(8))
    for i in range(5):
        ln = L.plane("docline%d" % i, 0.7, 0.04, (0, 0, 0), L.flat_mat("ink", hexc("9aa6b8")))
        ln.parent = doc
        ln.location = (0, 0.45 - i * 0.14, 0.005)
    for i, nm in enumerate(("US", "CHINA", "RUSSIA")):
        sl = L.plane("sig%d" % i, 0.22, 0.02, (0, 0, 0), L.flat_mat("sig_" + nm, COUNTRY[nm]))
        sl.parent = doc
        sl.location = (-0.3 + i * 0.3, -0.5, 0.005)
    mode = p.get("camera", "orbit")
    pol = lambda ang, r, z: (r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)), z)  # noqa: E731
    if mode == "crane_up":
        ctx.camera(pol(-150, 14, 5.5), target=(0, 0, 1.6), lens=21)
        L.animate_cam(ctx, [(1, pol(-150, 14, 5.5)), (T, pol(-140, 7.0, 16.5))])
        L.animate_target(ctx, [(1, (0, 0, 2.6)), (T, (0, 0.3, 0.2))])
    else:
        ctx.camera(pol(-165, 15, 9), target=(0, 0, 1.6), lens=20)
        keys = []
        for k in range(5):
            t = k / 4.0
            keys.append((1 + int(t * (T - 1)), pol(-165 + 35 * t, 15 - 2 * t, 9.5 - 1.0 * t)))
        L.animate_cam(ctx, keys)
        L.animate_target(ctx, [(1, (0, 0, 2.4)), (T, (0, 0, 2.0))])
    for nm, ang in seats:
        a = math.radians(ang)
        _label(ctx, nm, (4.9 * math.cos(a), 4.9 * math.sin(a), 3.4), 0.45, COUNTRY[nm])
    if p.get("card"):
        f = _cue(ctx, p, "card_cue", "", 0.02) if p.get("card_cue") else ctx.f(0.25)
        ctx.card(p["card"], None, y_frac=0.15, size=0.05, appear=f)
    if p.get("subcard"):
        n_lines = p.get("card", "").count("\n") + 1
        _sub(ctx, p["subcard"], 0.15 + 0.045 * n_lines + 0.05, _cue(ctx, p, "sub_cue", "", 0.45) if p.get("sub_cue") else ctx.f(0.6))


def b_treaty_doc(ctx, p):
    """A treaty document on a desk; a red stamp slams on at the cue word."""
    _env(ctx, NAVY2, 2.0, (35, 0, 20))
    T = ctx.frames
    _floor(hexc("1a2944"), rough=0.5)
    paper_root = L.link(bpy.data.objects.new("paper_root", None))
    paper_root.location = (0, 0, 0.02)
    paper_root.rotation_euler = (0, 0, math.radians(-4))
    pw, ph = 4.2, 5.6
    pap = L.plane("paper", pw, ph, (0, 0, 0), L.mat("paper2", PAPER, rough=0.85))
    pap.parent = paper_root
    # second sheet underneath for depth
    p2 = L.plane("paper_b", pw, ph, (0, 0, 0), L.mat("paper3", hexc("cfd6df"), rough=0.85))
    p2.parent = paper_root
    p2.location = (0.18, -0.15, -0.01)
    p2.rotation_euler = (0, 0, math.radians(5))
    title = L.label3d(ctx, p.get("title", "TREATY"), (0, 0, 0), 0.52, INK, rot=(0, 0, 0), face_cam=False)
    title.parent = paper_root
    title.location = (0, 2.05, 0.01)
    sub = L.label3d(ctx, p.get("doc_sub", "STRATEGIC ARMS REDUCTION TREATY"), (0, 0, 0), 0.17, hexc("4a5870"),
                    rot=(0, 0, 0), font=FONT_PATH_SUB, face_cam=False)
    sub.parent = paper_root
    sub.location = (0, 1.55, 0.01)
    ink = L.flat_mat("ink2", hexc("aab4c3"))
    for i in range(11):
        w = 3.2 if i % 4 != 3 else 2.0
        ln = L.plane("line%d" % i, w, 0.07, (0, 0, 0), ink)
        ln.parent = paper_root
        ln.location = (-(3.2 - w) / 2, 1.05 - i * 0.26, 0.005)
    for i in range(2):
        sg = L.plane("sigline%d" % i, 1.4, 0.03, (0, 0, 0), L.flat_mat("ink3", hexc("6b778a")))
        sg.parent = paper_root
        sg.location = (-0.95 + i * 1.9, -2.35, 0.005)
    # stamp: red text + border, rotated, slams in
    f_st = _cue(ctx, p, "stamp_cue", "expired", 0.55)
    st = L.link(bpy.data.objects.new("stamp", None))
    st.location = (0.1, -0.6, 0.06)
    st.rotation_euler = (0, 0, math.radians(14))
    red = L.flat_mat("stamp_red", hexc("e0263a"))
    txt = L.label3d(ctx, p.get("stamp", "EXPIRED"), (0, 0, 0), 0.62, hexc("e0263a"), rot=(0, 0, 0), face_cam=False)
    txt.parent = st
    txt.location = (0, 0, 0.01)
    txt.animation_data_clear()
    txt.scale = (1, 1, 1)
    lines = p.get("stamp", "EXPIRED").count("\n") + 1
    bw, bh, th = 3.7, 0.62 * 1.25 * lines + 0.35, 0.09
    for nm, sz, lc in (("t", (bw, th), (0, bh / 2)), ("b", (bw, th), (0, -bh / 2)),
                       ("l", (th, bh), (-bw / 2, 0)), ("r", (th, bh), (bw / 2, 0))):
        e = L.plane("stb_" + nm, sz[0], sz[1], (0, 0, 0), red)
        e.parent = st
        e.location = (lc[0], lc[1], 0.0)
    kf(st, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
    kf(st, "scale", f_st - 1, Vector((0.0, 0.0, 0.0)), "CONSTANT")
    kf(st, "scale", f_st, Vector((1.7, 1.7, 1.7)), "LINEAR")
    kf(st, "scale", f_st + 4, Vector((0.94, 0.94, 0.94)), "BEZIER")
    kf(st, "scale", f_st + 8, Vector((1, 1, 1)), "BEZIER")
    cam = ctx.camera((0.6, -7.5, 10.5), target=(0, -0.3, 0), lens=34)
    L.animate_cam(ctx, [(1, (0.8, -7.8, 11.5)), (f_st, (0.3, -6.4, 9.6)), (f_st + 3, (0.38, -6.3, 9.5)),
                        (f_st + 6, (0.3, -6.4, 9.6)), (T, (0.0, -5.6, 8.6))])
    L.animate_target(ctx, [(1, (0, 0.2, 0)), (T, (0, -0.4, 0))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.048)
    if p.get("after"):
        _chip(ctx, p["after"], 0.235, _cue(ctx, p, "after_cue", "right", 0.85), panel=hexc("9a1020"))


def b_cap_bars(ctx, p):
    """Two warhead bars (US, Russia) rise above a line; a ceiling slab descends and caps both."""
    _env(ctx, NAVY, 2.4, (45, 0, 30), fog_density=0.004, fog_start=25)
    T = ctx.frames
    _floor(hexc("0e1b33"))
    f_cap = _cue(ctx, p, "cap_cue", "limited", 0.5)
    top0, cap_h = 6.4, 4.0
    bars = []
    for i, nm in enumerate(("US", "RUSSIA")):
        x = -1.6 + 3.2 * i
        root, b = _rooted_box("bar_" + nm, (2.0, 2.0, 1.0), (x, 0, 0), L.mat("bar_" + nm, COUNTRY[nm], 0.45))
        f0 = ctx.f(0.3 + 0.25 * i)
        kf(root, "scale", 1, Vector((1, 1, 0.001)), "CONSTANT")
        kf(root, "scale", f0, Vector((1, 1, 0.001)), "BEZIER")
        kf(root, "scale", f0 + 30, Vector((1, 1, top0 - 0.4 * i)), "BEZIER")
        kf(root, "scale", f_cap + 10, Vector((1, 1, top0 - 0.4 * i)), "BEZIER")
        kf(root, "scale", f_cap + 30, Vector((1, 1, cap_h - 0.05)), "BEZIER")
        lb = L.label3d(ctx, nm, (x, -1.4, 0.45), 0.55, COUNTRY[nm], rot=(70, 0, 0), face_cam=False)
        bars.append(root)
    # ceiling slab
    slab = L.box("cap", (7.4, 3.2, 0.14), (0, 0, 0), L.flat_mat("capslab", TEAL, alpha=0.55), bevel=0.02)
    edge = L.box("cap_edge", (7.5, 0.06, 0.06), (0, 0, 0), L.emissive("capedge", TEAL, 4.0))
    edge.parent = slab
    edge.location = (0, -1.6, 0.0)
    slab.visible_shadow = False
    kf(slab, "location", 1, Vector((0, 0, 30.0)), "CONSTANT")
    kf(slab, "location", f_cap - 1, Vector((0, 0, 30.0)), "CONSTANT")
    kf(slab, "location", f_cap, Vector((0, 0, 11.0)), "BEZIER")
    kf(slab, "location", f_cap + 30, Vector((0, 0, cap_h + 0.07)), "BEZIER")
    lbl = L.label3d(ctx, p.get("cap_label", "CAP"), (0, 0, 0), 0.6, WHITE, rot=(80, 0, 0), face_cam=False)
    lbl.parent = slab
    lbl.location = (0, -1.75, 0.65)
    cam = ctx.camera((5.0, -20.0, 6.5), target=(0, 0, 4.6), lens=32)
    L.animate_cam(ctx, [(1, (5.5, -21.0, 6.0)), (T, (2.5, -18.0, 7.5))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=_cue(ctx, p, "card_cue", "one", 0.15))
    if p.get("cap_sub"):
        _sub(ctx, p["cap_sub"], 0.225, f_cap + 20)


def b_verify_checks(ctx, p):
    """Count + check: documents swap between two sides (data exchange), a clipboard with a tick pops
    over a site (inspections), a satellite crosses overhead with a scan cone (satellites)."""
    _env(ctx, NAVY, 2.2, (50, 0, 30), fog_density=0.012, fog_start=18)
    T = ctx.frames
    _floor(hexc("0f1e36"), rough=0.7)
    gm = L.emissive("gridv", TEAL_DARK, 0.6)
    for i in range(-10, 11, 2):
        _polyline("gx%d" % i, [(i, -12, 0.01), (i, 30, 0.01)], 0.015, gm)
    for j in range(-12, 31, 2):
        _polyline("gy%d" % j, [(-10, j, 0.01), (10, j, 0.01)], 0.015, gm)
    site_m = L.mat("site", hexc("5c6f86"), 0.6)
    sites = [(-4.0, 6.0), (0.5, 9.0), (4.5, 5.0), (-1.5, 2.5)]
    for k, (x, y) in enumerate(sites):
        L.box("pad%d" % k, (2.2, 2.2, 0.12), (x, y, 0.06), L.mat("padm", hexc("27406b"), 0.8))
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.75, depth=1.6, location=(x, y, 0.12),
                                            rotation=(math.radians(90), 0, 0))
        h = bpy.context.object
        h.name = "hangar%d" % k
        h.data.materials.append(site_m)
    icue = p.get("icon_cues", ["data", "inspectors", "satellites"])
    f_data = ctx.word_time(icue[0], 0.25)
    f_insp = ctx.word_time(icue[1], 0.55)
    f_sat = ctx.word_time(icue[2], 0.7)
    # data exchange: two sheets cross along arcs between the left and right side
    for s, (a, b, col) in enumerate((((-6, 4, 2.5), (6, 4, 2.5), C_US), ((6, 4, 2.5), (-6, 4, 2.5), C_RU))):
        sheet = L.box("sheet%d" % s, (0.9, 0.05, 1.2), (0, 0, 0), L.mat("sheetm%d" % s, PAPER, 0.8))
        stripe = L.box("sheetc%d" % s, (0.9, 0.06, 0.18), (0, 0, 0), L.emissive("sheetc%d" % s, col, 2.0))
        stripe.parent = sheet
        stripe.location = (0, 0, 0.5)
        for f in range(1, T + 1, 2):
            t = (f - f_data) / 45.0
            t = max(0.0, min(1.0, t))
            tt = L.smooth(t)
            pos = Vector(a).lerp(Vector(b), tt) + Vector((0, 0.8 * (s * 2 - 1) * math.sin(math.pi * tt), 2.2 * math.sin(math.pi * tt)))
            kf(sheet, "location", f, pos)
        _pop_in(ctx, sheet, max(2, f_data - 4))
    # inspection: clipboard + tick over site 1
    cb = L.link(bpy.data.objects.new("clip", None))
    cb.location = (-1.5, 2.5, 2.4)
    board = L.box("board", (1.6, 0.08, 2.1), (0, 0, 0), L.mat("boardm", hexc("8a5a2b"), 0.7))
    board.parent = cb
    pap = L.box("bpaper", (1.35, 0.1, 1.7), (0, 0, 0), L.mat("bpap", PAPER, 0.8))
    pap.parent = cb
    pap.location = (0, -0.02, -0.08)
    clip = L.box("bclip", (0.6, 0.14, 0.2), (0, 0, 0), L.mat("bclipm", hexc("9aa8b8"), 0.3, 0.7))
    clip.parent = cb
    clip.location = (0, -0.03, 1.02)
    tick_m = L.emissive("tick", TEAL, 3.0)
    t1 = L.box("tick1", (0.55, 0.12, 0.16), (0, 0, 0), tick_m)
    t1.parent = cb
    t1.location = (-0.22, -0.1, -0.15)
    t1.rotation_euler = (0, math.radians(45), 0)
    t2 = L.box("tick2", (1.0, 0.12, 0.16), (0, 0, 0), tick_m)
    t2.parent = cb
    t2.location = (0.22, -0.1, 0.05)
    t2.rotation_euler = (0, math.radians(-55), 0)
    _pop_in(ctx, cb, f_insp)
    for t in (t1, t2):
        _pop_in(ctx, t, f_insp + 12)
    trk = cb.constraints.new("DAMPED_TRACK")
    # satellite crossing overhead with a scan cone
    sat = L.link(bpy.data.objects.new("sat", None))
    body = L.box("satbody", (0.8, 0.8, 1.0), (0, 0, 0), L.mat("satb", hexc("c9d3df"), 0.35, 0.6), bevel=0.04)
    body.parent = sat
    pm = L.mat("panel", hexc("2d5fa8"), 0.3, 0.3)
    for sx in (-1, 1):
        pn = L.box("satpanel", (1.8, 0.7, 0.04), (0, 0, 0), pm)
        pn.parent = sat
        pn.location = (sx * 1.35, 0, 0.1)
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=2.6, radius2=0.05, depth=5.2, location=(0, 0, 0))
    cone = bpy.context.object
    cone.data.materials.append(L.flat_mat("scan", TEAL, alpha=0.18))
    cone.visible_shadow = False
    cone.parent = sat
    cone.location = (0, 0, -2.9)
    ring = _polyline("scanring", [(2.6 * math.cos(a / 24.0 * 2 * math.pi), 2.6 * math.sin(a / 24.0 * 2 * math.pi), 0)
                                  for a in range(24)], 0.05, L.emissive("scanr", TEAL, 3.0), cyclic=True)
    ring.parent = sat
    ring.location = (0, 0, -5.45)
    f_s0 = max(1, f_sat - 25)
    for f in range(1, T + 1, 2):
        t = (f - f_s0) / float(max(30, T - f_s0))
        kf(sat, "location", f, Vector((-7 + 12 * t, 7.0 - 2.0 * t, 5.5)))
    _pop_in(ctx, sat, f_s0)
    cam = ctx.camera((7.5, -13.0, 10.5), target=(0, 5.0, 3.6), lens=28)
    trk.target = cam
    trk.track_axis = "TRACK_NEGATIVE_Y"
    L.animate_cam(ctx, [(1, (8.0, -14.0, 10.0)), (T, (4.5, -12.0, 12.0))])
    L.animate_target(ctx, [(1, (0, 5.0, 3.6)), (T, (0, 5.5, 4.0))])
    items = p.get("items", [])
    item_cues = p.get("item_cues", ["two", "three"])
    fi = [ctx.word_time(item_cues[i], 0.05 + 0.4 * i) for i in range(len(items))]
    for i, it in enumerate(items):
        ctx.card(it, None, y_frac=0.14, size=0.05, appear=max(2, fi[i]),
                 disappear=(fi[i + 1] - 1) if i + 1 < len(items) else None)
    for i, ic in enumerate(p.get("icons", [])):
        f = [f_data, f_insp, f_sat][i] if i < 3 else ctx.f(1)
        _chip(ctx, ic, 0.222 + 0.058 * i, f + 2, panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), size=0.022)


def b_three_balance(ctx, p):
    """Balance board on a point: two blocks (US, Russia) rock gently; on the cue word a third block
    (China) drops in, the blocks slide to 120 degrees and the board wobbles on two axes."""
    _env(ctx, NAVY, 2.4, (50, 0, 40), fog_density=0.006, fog_start=20)
    T = ctx.frames
    _floor(hexc("0e1b33"))
    L.cylinder("post", 0.25, 2.4, (0, 0, 1.2), material=L.mat("post", STEEL, 0.4, 0.5), verts=16)
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.5, radius2=0.05, depth=0.6, location=(0, 0, 2.6))
    bpy.context.object.data.materials.append(L.mat("post", STEEL, 0.4, 0.5))
    board = L.link(bpy.data.objects.new("board", None))
    board.location = (0, 0, 2.95)
    disc = L.cylinder("disc", 3.2, 0.16, (0, 0, 0), material=L.mat("disc", hexc("2b3d5c"), 0.45), verts=48)
    disc.parent = board
    rim = L.cylinder("discrim", 3.24, 0.06, (0, 0, 0), material=L.emissive("discrim", TEAL, 1.5), verts=48)
    rim.parent = board
    rim.location = (0, 0, -0.06)
    ctx.camera((6.5, -16.0, 9.0), target=(0, 0, 3.6), lens=32)
    f3 = _cue(ctx, p, "third_cue", "third", 0.4)
    blocks = {}
    for nm in ("US", "RUSSIA", "CHINA"):
        b = L.box("blk_" + nm, (1.1, 1.1, 1.1), (0, 0, 0), L.mat("blk_" + nm, COUNTRY[nm], 0.45), bevel=0.05)
        b.parent = board
        blocks[nm] = b
        lb = _label(ctx, nm, (0, 0, 0), 0.45, COUNTRY[nm])
        lb.parent = b
        lb.location = (0, 0, 1.15)
    ang_before = {"US": 180, "RUSSIA": 0}
    ang_after = {"US": 210, "RUSSIA": 330, "CHINA": 90}
    rr = 2.2
    for nm, b in blocks.items():
        for f in range(1, T + 1, 2):
            if nm == "CHINA":
                a = math.radians(90)
                drop = max(0.0, 1.0 - (f - f3) / 14.0) if f >= f3 else 1.0
                z = 0.63 + 7.0 * drop * drop
            else:
                t = L.smooth((f - f3 - 6) / 20.0)
                a = math.radians(ang_before[nm] + (ang_after[nm] - ang_before[nm]) * t)
                z = 0.63
            kf(b, "location", f, Vector((rr * math.cos(a), rr * math.sin(a), z)))
        if nm == "CHINA":
            _pop_in(ctx, b, max(2, f3 - 2))
    for f in range(1, T + 1, 2):
        tt = (f - 1) / ctx.fps
        if f < f3 + 14:
            rx, ry = 0.0, math.radians(5.0) * math.sin(2 * math.pi * tt / 2.6)
        else:
            k = (f - f3 - 14) / ctx.fps
            amp = math.radians(4.0 + 7.0 * math.exp(-k / 2.5))
            rx = amp * math.sin(2 * math.pi * tt / 1.9)
            ry = amp * math.cos(2 * math.pi * tt / 2.3)
        kf(board, "rotation_euler", f, Vector((rx, ry, 0)))
    L.animate_cam(ctx, [(1, (6.0, -16.5, 8.0)), (T, (3.5, -15.0, 10.5))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=ctx.f(0.3), disappear=f3 - 1)
    if p.get("card2"):
        ctx.card(p["card2"], None, y_frac=0.14, size=0.046, appear=f3)


def b_stock_bars(ctx, p):
    """Bars shrinking left to right (relative heights, no numbers): first = '1980s PEAK', last = 'TODAY'.
    A dashed trend line + 'DOWN MORE THAN 3/4' chip on drop_cue; the last bar's lower part turns
    into the US + Russia share on split_cue."""
    _env(ctx, NAVY, 2.4, (45, 0, 30), fog_density=0.003, fog_start=30)
    T = ctx.frames
    _floor(hexc("0e1b33"))
    hs = p.get("heights", [100, 80, 60, 40, 25, 17])
    n = len(hs)
    H = 8.0
    sp = 1.55
    x0 = -(n - 1) * sp / 2.0
    past = L.mat("bar_past", hexc("6f8296"), 0.5)
    last_m = L.mat("bar_today", TEAL, 0.45)
    f_drop = _cue(ctx, p, "drop_cue", "three", 0.4)
    f_split = _cue(ctx, p, "split_cue", "russia", 0.75)
    for i, hv in enumerate(hs):
        h = H * hv / 100.0
        root, b = _rooted_box("sb%d" % i, (1.15, 1.15, 1.0), (x0 + i * sp, 0, 0), last_m if i == n - 1 else past)
        f0 = ctx.f(0.2) + i * 5
        kf(root, "scale", 1, Vector((1, 1, 0.001)), "CONSTANT")
        kf(root, "scale", f0, Vector((1, 1, 0.001)), "BEZIER")
        kf(root, "scale", f0 + 22, Vector((1, 1, h)), "BEZIER")
    lab_m = hexc("c9d3df")
    L.label3d(ctx, p.get("first_label", "PEAK"), (x0 + 0.4, -1.2, 0.35), 0.5, lab_m, rot=(70, 0, 0), face_cam=False)
    L.label3d(ctx, p.get("last_label", "TODAY"), (x0 + (n - 1) * sp, -1.2, 0.35), 0.5, TEAL, rot=(70, 0, 0), face_cam=False)
    # trend line along the bar tops
    pts = [(x0 + i * sp, -0.7, H * hs[i] / 100.0 + 0.35) for i in range(n)]
    tl = _polyline("trend", pts, 0.06, L.emissive("trend", RED, 3.0))
    kf(tl.data, "bevel_factor_end", 1, 0.0, "CONSTANT")
    kf(tl.data, "bevel_factor_end", f_drop, 0.0, "BEZIER")
    kf(tl.data, "bevel_factor_end", f_drop + 30, 1.0, "BEZIER")
    # US + Russia share of the last bar
    hl = H * hs[-1] / 100.0
    frac = float(p.get("split_frac", 0.85))
    root, sb = _rooted_box("share", (1.22, 1.22, 1.0), (x0 + (n - 1) * sp, 0, 0), L.mat("share", C_US, 0.45))
    kf(root, "scale", 1, Vector((1, 1, 0.001)), "CONSTANT")
    kf(root, "scale", f_split, Vector((1, 1, 0.001)), "BEZIER")
    kf(root, "scale", f_split + 18, Vector((1, 1, hl * frac)), "BEZIER")
    cam = ctx.camera((2.0, -26.0, 7.0), target=(0, 0, 4.6), lens=30)
    xl = x0 + (n - 1) * sp
    L.animate_cam(ctx, [(1, (2.5, -27.0, 7.5)), (f_split - 10, (2.0, -25.0, 7.0)), (T, (xl + 1.0, -11.0, 4.5))])
    L.animate_target(ctx, [(1, (0, 0, 4.8)), (f_split - 10, (0.3, 0, 4.6)), (T, (xl - 0.8, 0, 2.6))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05)
    if p.get("drop_label"):
        _chip(ctx, p["drop_label"], 0.225, f_drop + 6, panel=hexc("9a1020"))
    if p.get("split_label"):
        _chip(ctx, p["split_label"], 0.29, f_split + 6, panel=hexc("1f4fa8"))


def b_three_lower(ctx, p):
    """Three coloured pillars on a round stage. Teal 'check' beams link every pair, then all three
    sink together in steps, staying equal."""
    _env(ctx, NAVY, 2.2, (50, 0, 30), fog_density=0.006, fog_start=20)
    T = ctx.frames
    _floor(hexc("0e1b33"))
    L.cylinder("stage", 4.6, 0.2, (0, 0, 0.1), material=L.mat("stage", hexc("1d2d4c"), 0.5), verts=48)
    _ring("stagerim", 4.6, 0.2, 0.05, L.emissive("stagerim", TEAL, 1.6))
    f_chk = _cue(ctx, p, "check_cue", "check", 0.55)
    f_low = f_chk + 12
    h0 = 6.0
    lab_pos = []
    roots = []
    for i, (nm, ang) in enumerate((("US", -90), ("CHINA", 30), ("RUSSIA", 150))):
        a = math.radians(ang)
        pos = Vector((2.7 * math.cos(a), 2.7 * math.sin(a), 0.2))
        root = L.link(bpy.data.objects.new("pil_" + nm, None))
        root.location = pos
        c = L.cylinder("pillar_" + nm, 0.65, 1.0, (0, 0, 0), material=L.mat("pil_" + nm, COUNTRY[nm], 0.4), verts=8)
        c.parent = root
        c.location = (0, 0, 0.5)
        # pillar heights: hold, then 3 equal steps down, all three in sync
        kf(root, "scale", 1, Vector((1, 1, h0)), "CONSTANT")
        steps = 3
        stp = max(10, int((T - f_low - 10) / steps))
        for s in range(steps):
            fa = f_low + s * stp
            kf(root, "scale", fa, Vector((1, 1, h0 - 1.4 * s)), "BEZIER")
            kf(root, "scale", fa + int(stp * 0.6), Vector((1, 1, h0 - 1.4 * (s + 1))), "BEZIER")
        lab_pos.append((nm, pos))
        roots.append(root)
    # 'check' beams between pillar tops (follow the tops as they sink)
    beam_m = L.emissive("beam", TEAL, 3.5)
    for k in range(3):
        a_, b_ = roots[k], roots[(k + 1) % 3]
        mid = L.link(bpy.data.objects.new("beam%d" % k, None))
        d = b_.location - a_.location
        L_ = d.length
        bm = L.cylinder("beamc%d" % k, 0.06, L_, (0, 0, 0), material=beam_m, verts=8)
        bm.parent = mid
        bm.rotation_euler = (0, math.radians(90), 0)
        bm.visible_shadow = False
        mid.location = (a_.location + b_.location) / 2.0
        mid.rotation_euler = (0, 0, math.atan2(d.y, d.x))
        # follow tops
        for f in range(1, T + 1, 3):
            ctx.scene.frame_set(f)
            mid.location = Vector(((a_.location.x + b_.location.x) / 2, (a_.location.y + b_.location.y) / 2,
                                   0.2 + a_.scale.z + 0.25))
            mid.keyframe_insert("location", frame=f)
        ctx.scene.frame_set(1)
        bs = Vector((1, 1, 1))
        kf(mid, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
        kf(mid, "scale", f_chk + 4 * k - 1, Vector((0, 0, 0)), "CONSTANT")
        kf(mid, "scale", f_chk + 4 * k, Vector((0.05, 1, 1)), "BEZIER")
        kf(mid, "scale", f_chk + 4 * k + 10, bs, "BEZIER")
    ctx.camera((8.0, -17.0, 12.0), target=(0, 0, 3.6), lens=30)
    L.animate_cam(ctx, [(1, (9.0, -17.0, 12.0)), (T, (5.0, -15.0, 10.0))])
    L.animate_target(ctx, [(1, (0, 0, 4.0)), (T, (0, 0, 2.6))])
    for nm, pos in lab_pos:
        _label(ctx, nm, tuple(Vector((pos.x * 1.2, pos.y * 1.2 - 0.9, 0.8))), 0.5, COUNTRY[nm])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05, appear=_cue(ctx, p, "lower_cue", "lower", 0.3))
    if p.get("subcard"):
        _sub(ctx, p["subcard"], 0.225, f_chk + 4)


def _sector(name, r0, r1, a0, a1, material, segs=16):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = []
    for i in range(segs + 1):
        a = math.radians(a0 + (a1 - a0) * i / segs)
        vs.append((bm.verts.new((r0 * math.cos(a), 0, r0 * math.sin(a))),
                   bm.verts.new((r1 * math.cos(a), 0, r1 * math.sin(a)))))
    for i in range(segs):
        bm.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0]))
    bm.to_mesh(me)
    bm.free()
    o = L.link(bpy.data.objects.new(name, me))
    o.data.materials.append(material)
    o.visible_shadow = False
    return o


def b_risk_gauge(ctx, p):
    """Semicircular gauge (red -> amber -> teal); the needle swings from red to teal on drop_cue,
    a small stack of blocks beside it shrinks; chips tick in on their cue words."""
    _env(ctx, NAVY, 1.8, (40, 0, 20))
    T = ctx.frames
    root = L.link(bpy.data.objects.new("gauge", None))
    root.location = (0, 0, 0)
    cols = [hexc("e0263a"), hexc("f08a24"), hexc("f2c230"), hexc("5fc9a8"), TEAL]
    for i, c in enumerate(cols):
        a1 = 180 - i * 36
        sec = _sector("sec%d" % i, 2.4, 3.3, a1 - 35, a1 - 1, L.flat_mat("sec%d" % i, c))
        sec.parent = root
    back = _sector("gback", 2.2, 3.5, -2, 182, L.flat_mat("gback", hexc("14244a")), 24)
    back.parent = root
    back.location = (0, 0.02, 0)
    hub = L.cylinder("hub", 0.35, 0.1, (0, 0, 0), material=L.flat_mat("hub", WHITE), verts=24)
    hub.parent = root
    hub.rotation_euler = (math.radians(90), 0, 0)
    hub.location = (0, -0.06, 0)
    npiv = L.link(bpy.data.objects.new("needle_piv", None))
    npiv.parent = root
    npiv.location = (0, -0.05, 0)
    nd = L.box("needle", (2.9, 0.04, 0.12), (0, 0, 0), L.flat_mat("needle", WHITE))
    nd.parent = npiv
    nd.location = (1.45, 0, 0)
    f_drop = _cue(ctx, p, "drop_cue", "fewer", 0.25)
    a_hi, a_lo = math.radians(160), math.radians(22)
    for f in range(1, T + 1, 2):
        tt = (f - 1) / ctx.fps
        if f < f_drop:
            a = a_hi + math.radians(4) * math.sin(2 * math.pi * tt / 0.9)
        else:
            t = min(1.0, (f - f_drop) / 50.0)
            a = a_hi + (a_lo - a_hi) * L.smooth(t) + math.radians(2) * math.sin(2 * math.pi * tt / 1.4) * (1 - t)
        kf(npiv, "rotation_euler", f, Vector((0, -a, 0)))
    lbl = L.label3d(ctx, p.get("gauge_label", "RISK"), (0, -0.05, -0.65), 0.36, hexc("c9d3df"),
                    rot=(90, 0, 0), face_cam=False)
    lbl.parent = root
    for k, (t_, x) in enumerate((("HIGH", -2.85), ("LOW", 2.85))):
        tl = L.label3d(ctx, t_, (x, -0.05, -0.3), 0.26, cols[0] if k == 0 else TEAL, rot=(90, 0, 0), face_cam=False)
        tl.parent = root
    root.location = (0, 0, 0.6)
    ctx.camera((0.0, -22.5, 2.0), target=(0, 0, 2.8), lens=40)
    L.animate_cam(ctx, [(1, (0.6, -23.0, 2.0)), (T, (-0.4, -21.5, 2.2))])
    L.animate_target(ctx, [(1, (0, 0, 2.8)), (T, (0, 0, 2.8))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.14, size=0.05)
    for i, ch in enumerate(p.get("chips", [])):
        cues = p.get("chip_cues", [])
        f = ctx.word_time(cues[i], 0.5 + 0.15 * i) if i < len(cues) else ctx.f(1 + i)
        _chip(ctx, ch, 0.222 + 0.058 * i, f, panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), size=0.022)


GEO_BUILDERS = {
    "globe_summit": b_globe_summit,
    "round_table": b_round_table,
    "treaty_doc": b_treaty_doc,
    "cap_bars": b_cap_bars,
    "verify_checks": b_verify_checks,
    "three_balance": b_three_balance,
    "stock_bars": b_stock_bars,
    "three_lower": b_three_lower,
    "risk_gauge": b_risk_gauge,
}
L.BUILDERS.update(GEO_BUILDERS)

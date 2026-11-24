"""v2 harbour / sea builders ("sea drones": how sea drones sink warships, 25 Nov 2026).
Registers into scene_lib_v2.V2_BUILDERS.

World (every beat builds the same one): a bright Mediterranean-style port in daylight (HDRI sky). Land is north
(y > 0, quay top z = QUAY_Z), the open sea south (water surface z = 0). A west breakwater (with a lighthouse) and an
east jetty close a harbour basin; a naval finger pier (west), a container terminal with gantry cranes, warehouses,
a coast road with traffic and palms, a low-rise sand-coloured city and far hills. A merchant ship lies at anchor off
the port; small boats move in the basin.

Models are ORIGINAL and generic: a grey corvette (no flags, hull numbers or weapons), a small dark sea-drone boat,
a merchant ship, tugs. Non-graphic: a hit is only a white water splash (+ red ring); ships list / roll over; nobody
is shown. No 3D text: every label / card is a 2D overlay (overlay_v2.py) reading the anchors set with S.anchor().

Cutaway (`cutaway_v2`): the corvette cut in half across its length, seen from the cut; the sea in front of it is cut
too (a deep teal "aquarium" face), so the hull section below the waterline shows. Flood water inside is drawn as
one polygon per 2 frames (clipped to the hull section, level in the world), swapped with CONSTANT scale keys.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import scene_lib as L
import scene_lib_v2 as S
import scene_lib_v2_air as A
import scene_lib_v2_city as C
from scene_lib import hexc, kf
from scene_lib_v2_winter import set_keys

QUAY_Z = 2.5
EXT = 20000.0
PIER_X, PIER_Y1, PIER_W = -450.0, -230.0, 22.0       # naval finger pier (x centre, south end, width)
SHIP_HOME = (-432.0, -125.0)                          # corvette moored on the pier's east side, bow south
BW_W = [(-700.0, 0.0), (-700.0, -560.0), (150.0, -560.0)]   # west breakwater polyline
BW_E = [(900.0, 0.0), (900.0, -380.0)]                       # east jetty
MERCHANT = (1500.0, -1700.0)
CUT_Y = -330.0                                        # cutaway: sea is cut at this y (camera looks north)
CUT_X = -150.0

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def vis_keys(o, keys):
    """keys = [(frame, visible)] -> CONSTANT scale keys (Blender 5.3 ignores L.kf CONSTANT)."""
    s = tuple(o.scale)
    set_keys(o, "scale", [f for f, _ in keys], [(s if v else (0.0, 0.0, 0.0)) for _, v in keys], "CONSTANT")


# ================================================================ materials
def sea_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("sea_v2")
        col = hexc("2b6f8c")
        p.inputs["Roughness"].default_value = 0.06
        p.inputs["Specular IOR Level"].default_value = 0.55
        p.inputs["Coat Weight"].default_value = 0.25
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 0.45, 1.0)
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 0.16
        nz.inputs["Detail"].default_value = 7.0
        nz.inputs["Roughness"].default_value = 0.55
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        L.kf_socket(nz.inputs["W"], 1, 0.0, "LINEAR")
        L.kf_socket(nz.inputs["W"], 900, 7.0, "LINEAR")
        b = N.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = 0.2
        b.inputs["Distance"].default_value = 0.35
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.003, 0.14)
        Lk.new(S._mul_col(N, Lk, tuple(col), fac), p.inputs["Base Color"])
        return S._finish(m, p.outputs[0])
    return _m("sea", mk)


def sea_section_mat():
    """Cut face of the sea (cutaway): bright teal at the surface fading to deep blue, slightly self-lit so the
    section reads as water and never as a dark void."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("sea_section_v2")
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(tc.outputs["Object"], sep.inputs[0])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.0
        mr.inputs["From Max"].default_value = -26.0
        Lk.new(sep.outputs["Z"], mr.inputs["Value"])
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].color = hexc("49bcd0")
        els[1].color = hexc("0f4a78")
        Lk.new(mr.outputs["Result"], ramp.inputs[0])
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 0.12
        nz.inputs["Detail"].default_value = 3.0
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr2 = N.new("ShaderNodeMapRange")
        mr2.inputs["To Min"].default_value = 0.9
        mr2.inputs["To Max"].default_value = 1.1
        Lk.new(nz.outputs["Fac"], mr2.inputs["Value"])
        col = S._mul_col(N, Lk, ramp.outputs["Color"], mr2.outputs["Result"])
        Lk.new(col, p.inputs["Base Color"])
        Lk.new(col, p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 0.55
        p.inputs["Roughness"].default_value = 0.35
        return S._finish(m, p.outputs[0], haze=False)
    return _m("sea_section", mk)


def foam_mat(name="foam_v2", strength=0.9):
    """White foam with a soft alpha along the object's -Y (wake trails fade out behind the boat)."""
    def mk():
        m = bpy.data.materials.new(name)
        m.surface_render_method = "BLENDED"
        nt = m.node_tree
        N, Lk = nt.nodes, nt.links
        p = N.get("Principled BSDF")
        p.inputs["Base Color"].default_value = hexc("f4f8fa")
        p.inputs["Roughness"].default_value = 0.7
        p.inputs["Emission Color"].default_value = hexc("f4f8fa")
        p.inputs["Emission Strength"].default_value = 0.25
        tc = N.new("ShaderNodeTexCoord")
        uv = tc.outputs["UV"]
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(uv, sep.inputs[0])
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.2
        nz.inputs["Detail"].default_value = 6.0
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")       # UV v: 0 at the boat, 1 at the end of the trail
        mr.inputs["To Min"].default_value = strength
        mr.inputs["To Max"].default_value = 0.0
        Lk.new(sep.outputs["Y"], mr.inputs["Value"])
        mn = N.new("ShaderNodeMapRange")
        mn.inputs["From Min"].default_value = 0.35
        mn.inputs["From Max"].default_value = 0.62
        Lk.new(nz.outputs["Fac"], mn.inputs["Value"])
        edge = N.new("ShaderNodeMath")          # soft side edges: 1 - |2u - 1|^3
        edge.operation = "MULTIPLY_ADD"
        Lk.new(sep.outputs["X"], edge.inputs[0])
        edge.inputs[1].default_value = 2.0
        edge.inputs[2].default_value = -1.0
        ab = N.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        Lk.new(edge.outputs[0], ab.inputs[0])
        pw = N.new("ShaderNodeMath")
        pw.operation = "POWER"
        Lk.new(ab.outputs[0], pw.inputs[0])
        pw.inputs[1].default_value = 3.0
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        Lk.new(pw.outputs[0], inv.inputs[1])
        a1 = N.new("ShaderNodeMath")
        a1.operation = "MULTIPLY"
        Lk.new(mr.outputs["Result"], a1.inputs[0])
        Lk.new(mn.outputs["Result"], a1.inputs[1])
        a2 = N.new("ShaderNodeMath")
        a2.operation = "MULTIPLY"
        Lk.new(a1.outputs[0], a2.inputs[0])
        Lk.new(inv.outputs[0], a2.inputs[1])
        Lk.new(a2.outputs[0], p.inputs["Alpha"])
        L._fog_wrap(m, p.outputs[0])
        return m
    return _m(name, mk)


def spray_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("spray_v2")
        p.inputs["Base Color"].default_value = hexc("f2f6f8")
        p.inputs["Roughness"].default_value = 0.8
        p.inputs["Emission Color"].default_value = hexc("e8eef2")
        p.inputs["Emission Strength"].default_value = 0.35
        p.inputs["Subsurface Weight"].default_value = 0.3
        return S._finish(m, p.outputs[0])
    return _m("spray", mk)


def rock_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("rock_v2")
        obj = S._coord(N, Lk, "Object")
        vor = N.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 0.35
        Lk.new(obj, vor.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = hexc("8c857a")
        ramp.color_ramp.elements[1].color = hexc("bdb4a4")
        Lk.new(vor.outputs["Distance"], ramp.inputs[0])
        p.inputs["Roughness"].default_value = 0.9
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        S._bump(N, Lk, vor.outputs["Distance"], p, 0.5, 0.4)
        return S._finish(m, p.outputs[0])
    return _m("rock", mk)


def ground_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("port_ground_v2")
        obj = S._coord(N, Lk, "Object")
        fac, _ = S._noise_var(N, Lk, obj, 0.01, 0.1)
        col = S._mul_col(N, Lk, tuple(hexc("bdb6a6")), fac)
        p.inputs["Roughness"].default_value = 0.9
        if not S.ph_detail(N, Lk, obj, "concrete_floor_02", p, col, amount=0.35, normal=0.3, rough_mix=0.2,
                           scale_mul=4.0):
            Lk.new(col, p.inputs["Base Color"])
        return S._finish(m, p.outputs[0])
    return _m("ground", mk)


# ================================================================ geometry helpers
def _poly_xz(bm, pts, y, mi=0, flip=False):
    vs = [bm.verts.new((x, y, z)) for x, z in pts]
    f = bm.faces.new(list(reversed(vs)) if flip else vs)
    f.material_index = mi
    return f


def _loft(bm, rings, mi_fn=None, cap0=True, cap1=True):
    """rings: list of lists of (x, y, z) with the same count (open profiles closed by caps at both ends)."""
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vr[:-1], vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            if mi_fn:
                c = (a[i].co + b[j].co) / 2
                f.material_index = mi_fn(c)
    if cap0:
        bm.faces.new(vr[0])
    if cap1:
        bm.faces.new(list(reversed(vr[-1])))
    return vr


def _annulus_obj(name, r, w, loc, mat, seg=72):
    bm = bmesh.new()
    C._annulus(bm, r, w, seg)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat]), loc)
    o.visible_shadow = False
    return o


# ================================================================ corvette (generic, original)
CV_L = 62.0
CV_HB = 5.6          # half beam


def cv_dims(y):
    """Half-width, deck z, keel z of the corvette hull at local y (bow +Y at +31)."""
    h = CV_L / 2
    u = (y + h) / CV_L
    if y > 12.0:
        t = (y - 12.0) / (h - 12.0)
        w = CV_HB * max(0.03, 1.0 - t ** 1.7)
    elif y < -24.0:
        w = CV_HB * (0.86 + 0.14 * (y + h) / (h - 24.0))
    else:
        w = CV_HB
    zd = 3.4 + 1.9 * max(0.0, (y - 6.0) / (h - 6.0)) ** 1.4 - 0.3 * max(0.0, (-y - 15.0) / 16.0)
    zk = -3.3 if y < 18 else -3.3 + 3.6 * ((y - 18.0) / (h - 18.0)) ** 1.6
    if y < -22:
        zk = -3.3 + 1.0 * ((-22 - y) / (h - 22.0))
    return w, zd, zk


def cv_section(y, inset=0.0):
    """Closed hull section at y (list of (x, z), starboard = +x), optionally inset (interior)."""
    w, zd, zk = cv_dims(y)
    w -= inset
    zd -= inset * 0.8
    zk += inset
    h = -zk
    half = [(0.0, zk), (0.42 * w, zk + 0.12 * h), (0.78 * w, zk + 0.42 * h), (0.95 * w, zk + 0.78 * h),
            (0.995 * w, 0.0), (w * 1.0, zd * 0.5), (w * 1.03, zd)]
    pts = [(-x, z) for x, z in reversed(half[1:])] + half
    return pts      # from port deck edge, round the keel, to starboard deck edge (deck line closes it)


def make_corvette(name, y_min=-CV_L / 2, y_max=CV_L / 2, cut=False):
    """Generic grey corvette, origin at the waterline centre, bow +Y. With cut=True (y_min = 0) the forward half
    only, with a section drawn on the cut face (steel ring, light interior, platform deck). Returns
    (root, info)."""
    grey = S.pbr("cv_grey", hexc("8b939a"), 0.5, 0.15, var=0.05, var_scale=0.3)
    anti = S.pbr("cv_anti", hexc("8a3b2e"), 0.6, var=0.08, var_scale=0.3)
    deck = S.pbr("cv_deck", hexc("5c6268"), 0.8, var=0.08, bump=0.05)
    dark = S.pbr("cv_dark", hexc("2a3038"), 0.2, 0.3, var=0)
    white = S.pbr("cv_white", hexc("e9edf0"), 0.4, var=0)
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    ys = []
    y = y_min
    while y < y_max - 1e-6:
        ys.append(y)
        y += 1.0
    ys.append(y_max)
    rings = []
    for y in ys:
        sec = cv_section(y)
        rings.append([(x, y, z) for x, z in sec])
    _loft(bm, rings, mi_fn=lambda c: 1 if c.z < -0.15 else 0)
    # deck surface (slightly above the deck edge so the deck colour wins)
    drings = []
    for y in ys:
        w, zd, zk = cv_dims(y)
        drings.append([(-w * 1.03 + 0.05, y, zd + 0.03), (w * 1.03 - 0.05, y, zd + 0.03)])
    for a, b in zip(drings[:-1], drings[1:]):
        vs = [bm.verts.new(a[0]), bm.verts.new(a[1]), bm.verts.new(b[1]), bm.verts.new(b[0])]
        bm.faces.new(vs).material_index = 2
    # bulwark / rail strip near the bow
    me = S.mesh_from_bm(name + "_hull", bm, [grey, anti, deck])
    hull = S.obj(name + "_hull", me, parent=root)

    def clip(y0, y1):
        return max(y0, y_min), min(y1, y_max)

    bm = bmesh.new()
    blocks = [  # (x half, y0, y1, z0, z1, mat)
        (4.2, -12.0, 9.0, 3.4, 6.6, 0),      # main superstructure
        (3.6, 7.0, 14.0, 3.4, 9.6, 0),       # bridge block
        (3.4, -6.0, 4.0, 6.6, 8.8, 0),       # upper deckhouse
        (1.6, -5.0, -1.0, 8.8, 11.6, 0),     # funnel
        (4.25, 7.2, 13.6, 8.3, 9.1, 1),      # bridge windows band
        (3.8, -24.0, -12.0, 3.2, 3.6, 0),    # aft deck step
    ]
    for hx, y0, y1, z0, z1, mi in blocks:
        a, b = clip(y0, y1)
        if b - a < 0.05:
            continue
        S.bm_box(bm, (0, (a + b) / 2, (z0 + z1) / 2), (hx * 2, b - a, z1 - z0), mi)
    # mast (tapered tower + yard + sensor dome)
    for y0, y1 in ((3.0, 5.0),):
        a, b = clip(y0, y1)
        if b - a > 0.05:
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=1.5, radius2=0.45, depth=8.6)
            bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                             matrix=__import__("mathutils").Matrix.Rotation(math.pi / 4, 3, "Z"))
            bmesh.ops.translate(bm, vec=(0, 4.0, 13.1), verts=res["verts"])
    if y_min <= 4.0 <= y_max:
        S.bm_box(bm, (0, 4.0, 15.5), (6.0, 0.3, 0.3), 0)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.1)
        bmesh.ops.translate(bm, vec=(0, 4.0, 18.0), verts=res["verts"])
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 2
        S.bm_box(bm, (0, 4.0, 17.0), (0.25, 0.25, 2.0), 0)
    # railings / boats davits (small boxes) along the sides
    for sx in (-1, 1):
        a, b = clip(-10.0, -4.0)
        if b - a > 0.05:
            S.bm_box(bm, (sx * 4.6, (a + b) / 2, 7.4), (0.9, b - a, 1.2), 2)   # covered rescue boats (white)
    me = S.mesh_from_bm(name + "_sup", bm, [grey, dark, white])
    S.obj(name + "_sup", me, parent=root)
    info = {"root": root, "hull": hull}
    if cut:
        info.update(_cut_face(name, root, y_min))
    return root, info


def _cut_face(name, root, y0):
    """Section drawn on the cut face at local y0 (towards -Y = the camera)."""
    steel = S.pbr("cv_cut_steel", hexc("3e464e"), 0.5, 0.2, var=0)
    inner = S.pbr("cv_cut_inner", hexc("e6e0d2"), 0.8, var=0.03)
    pi_ = inner.node_tree.nodes.get("Principled BSDF")
    pi_.inputs["Emission Color"].default_value = hexc("e6e0d2")
    pi_.inputs["Emission Strength"].default_value = 0.45
    line = S.pbr("cv_cut_line", hexc("59626b"), 0.6, var=0)
    bm = bmesh.new()
    outer = cv_section(y0)
    w, zd, zk = cv_dims(y0)
    _poly_xz(bm, outer, y0 - 0.02, 0, flip=True)
    ins = cv_section(y0, inset=0.32)
    _poly_xz(bm, ins, y0 - 0.04, 1, flip=True)
    # superstructure sections (light interiors inside steel frames) on the cut
    for hx, z0, z1 in ((4.2, 3.4, 6.6), (3.4, 6.6, 8.8)):
        _poly_xz(bm, [(-hx, z0), (hx, z0), (hx, z1), (-hx, z1)], y0 - 0.02, 0, flip=True)
        _poly_xz(bm, [(-hx + 0.28, z0 + 0.25), (hx - 0.28, z0 + 0.25), (hx - 0.28, z1 - 0.25),
                      (-hx + 0.28, z1 - 0.25)], y0 - 0.04, 1, flip=True)
    # platform deck + two side frames (lines on top of the water layer)
    zp = -0.9
    wi = _width_at(ins, zp)
    _poly_xz(bm, [(-wi, zp - 0.09), (wi, zp - 0.09), (wi, zp + 0.09), (-wi, zp + 0.09)], y0 - 0.09, 2, flip=True)
    for sx in (-1, 1):
        x = sx * wi * 0.45
        _poly_xz(bm, [(x - 0.07, zp + 0.09), (x + 0.07, zp + 0.09), (x + 0.07, zd - 0.5), (x - 0.07, zd - 0.5)],
                 y0 - 0.09, 2, flip=True)
    o = S.obj(name + "_cut", S.mesh_from_bm(name + "_cut", bm, [steel, inner, line]), parent=root)
    return {"cut": o, "inner_poly": ins, "y0": y0}


def _width_at(poly, z):
    xs = []
    n = len(poly)
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        if (z1 - z) * (z2 - z) <= 0 and z1 != z2:
            xs.append(x1 + (x2 - x1) * (z - z1) / (z2 - z1))
    return max(abs(x) for x in xs) if xs else 1.0


# ---------------------------------------------------------------- flood water (2D polygon maths)
def _clip(poly, nx, nz, d):
    """Keep the part of poly with nx*x + nz*z <= d (Sutherland-Hodgman, one plane)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        da, db = nx * a[0] + nz * a[1] - d, nx * b[0] + nz * b[1] - d
        if da <= 0:
            out.append(a)
        if da * db < 0:
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _area(poly):
    s = 0.0
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        s += x1 * z2 - x2 * z1
    return abs(s) / 2


def water_poly(inner, theta, frac):
    """Flood water inside the (closed) inner section when the ship is rolled by theta (rad, about +Y: +x side goes
    down) and holds `frac` of the section's area: the world-level free surface, in ship coordinates."""
    if frac <= 0.002:
        return []
    full = _area(inner + [(inner[-1][0], inner[-1][1]), (inner[0][0], inner[0][1])])
    tgt = frac * full
    # world z of local (x, z) after rotation about +Y by theta: -x sin(t) + z cos(t)
    nx, nz = -math.sin(theta), math.cos(theta)
    vals = [nx * x + nz * z for x, z in inner]
    lo, hi = min(vals), max(vals)
    for _ in range(40):
        mid = (lo + hi) / 2
        if _area(_clip(inner, nx, nz, mid)) < tgt:
            lo = mid
        else:
            hi = mid
    return _clip(inner, nx, nz, (lo + hi) / 2)


# ================================================================ small craft, drone, merchant ship
def _boat_hull(bm, length, hb, zd, zk, mi_top=0, mi_bot=1, bow_rise=0.5):
    rings = []
    n = 14
    for i in range(n + 1):
        y = -length / 2 + length * i / n
        u = i / n
        w = hb * (1.0 if u < 0.55 else max(0.04, 1 - ((u - 0.55) / 0.45) ** 1.6)) * (0.9 + 0.1 * min(1, u * 5))
        d = zd + bow_rise * max(0.0, (u - 0.6) / 0.4) ** 2
        k = zk * (1.0 if u < 0.7 else max(0.15, 1 - (u - 0.7) / 0.3 * 0.85))
        half = [(0.0, k), (0.6 * w, k * 0.7), (0.95 * w, k * 0.15), (w, d)]
        pts = [(-x, z) for x, z in reversed(half[1:])] + half
        rings.append([(x, y, z) for x, z in pts])
    _loft(bm, rings, mi_fn=lambda c: mi_bot if c.z < 0.0 else mi_top)
    # deck
    for a, b in zip(rings[:-1], rings[1:]):
        vs = [bm.verts.new(a[0]), bm.verts.new(a[-1]), bm.verts.new(b[-1]), bm.verts.new(b[0])]
        f = bm.faces.new(vs)
        f.material_index = mi_top


def make_drone(name, wake=True, wake_len=46.0):
    """Small, low, dark uncrewed surface boat (~5.5 m), origin at the waterline, nose +Y. Wake = V foam trail."""
    body = S.pbr("drone_body", hexc("56616b"), 0.45, 0.2, var=0.05)
    deck = S.pbr("drone_deck", hexc("3b434b"), 0.6, var=0.05)
    sens = S.pbr("drone_sensor", hexc("15191d"), 0.15, 0.4, var=0)
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    _boat_hull(bm, 5.6, 0.78, 0.42, -0.35, 1, 0, bow_rise=0.15)
    S.bm_box(bm, (0, -0.9, 0.75), (0.5, 0.9, 0.5), 1)
    S.bm_box(bm, (0, -0.9, 1.08), (0.18, 0.18, 0.25), 2)
    res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.16)
    bmesh.ops.translate(bm, vec=(0, -0.85, 1.3), verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = 2
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [body, deck, sens], smooth=False), parent=root)
    if wake:
        make_wake(name + "_wake", root, wake_len, 0.9)
    return root


def make_wake(name, parent, length, half_w, y0=-2.6):
    """Foam: a central turbulent trail + two diverging Kelvin arms behind y0 (UV v = 0 at the boat)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    n = 16

    def strip(path):  # path: list of (x, y, half width)
        prev = None
        for i, (x, y, hw) in enumerate(path):
            v = i / (len(path) - 1)
            a = bm.verts.new((x - hw, y, 0.12 + 0.02 * i / len(path)))
            b = bm.verts.new((x + hw, y, 0.12 + 0.02 * i / len(path)))
            if prev is not None:
                f = bm.faces.new((prev[0], prev[1], b, a))
                for lp, uv in zip(f.loops, ((0, prev[2]), (1, prev[2]), (1, v), (0, v))):
                    lp[uvl].uv = uv
            prev = (a, b, v)
    strip([(0.0, y0 - length * i / n, half_w * (1.0 + 4.0 * i / n)) for i in range(n + 1)])
    ang = math.radians(19.0)
    for sx in (-1, 1):
        strip([(sx * (half_w + math.tan(ang) * length * 0.8 * i / n), y0 + 0.8 - length * 0.8 * i / n,
                0.35 + 1.4 * i / n) for i in range(n + 1)])
    o = S.obj(name, S.mesh_from_bm(name, bm, [foam_mat()]), parent=parent)
    o.visible_shadow = False
    return o


def make_tug(name, color=hexc("c8452f"), length=22.0, wake=True):
    hullc = S.pbr("tug_%s" % name, color, 0.5, var=0.06)
    anti = S.pbr("tug_anti", hexc("2a2f36"), 0.6, var=0.05)
    cab = S.pbr("tug_cab", hexc("eef0f0"), 0.5, var=0.03)
    win = S.pbr("tug_win", hexc("23303c"), 0.1, var=0)
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    _boat_hull(bm, length, length * 0.18, 1.6, -1.6, 0, 1, bow_rise=0.8)
    S.bm_box(bm, (0, -length * 0.05, 3.0), (length * 0.26, length * 0.3, 2.8), 2)
    S.bm_box(bm, (0, -length * 0.02, 4.8), (length * 0.22, length * 0.16, 1.2), 3)
    S.bm_box(bm, (0, -length * 0.2, 5.2), (0.8, 0.8, 3.0), 0)
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [hullc, anti, cab, win]), parent=root)
    if wake:
        make_wake(name + "_wake", root, length * 2.5, length * 0.12, y0=-length / 2)
    return root


def make_merchant(name, length=130.0):
    hullc = S.pbr("mer_hull", hexc("27384f"), 0.55, var=0.06)
    anti = S.pbr("mer_anti", hexc("8c3a2c"), 0.6, var=0.06)
    deckm = S.pbr("mer_deck", hexc("6b6f6a"), 0.8, var=0.06)
    white = S.pbr("mer_white", hexc("eceeee"), 0.45, var=0.03)
    win = S.pbr("mer_win", hexc("1f2a36"), 0.1, var=0)
    cont = [S.pbr("cont_%d" % i, hexc(c), 0.6, var=0.06) for i, c in
            enumerate(("b8432f", "2f6db3", "d9a325", "3f8a57", "c9ccd0", "7b4b8e"))]
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    hb = length * 0.075
    _boat_hull(bm, length, hb, 9.0, -7.0, 0, 1, bow_rise=2.0)
    S.bm_box(bm, (0, -length * 0.36, 15.5), (hb * 1.6, length * 0.1, 13.0), 3)
    for k in range(5):
        S.bm_box(bm, (0, -length * 0.36 + length * 0.051, 10.5 + k * 2.6), (hb * 1.62, 0.2, 1.1), 4)
    S.bm_box(bm, (0, -length * 0.42, 25.0), (2.4, 4.0, 6.0), 1)
    rng = random.Random(7)
    y = -length * 0.27
    while y < length * 0.33:
        for k in range(-2, 3):
            hgt = rng.randint(1, 3)
            for z in range(hgt):
                S.bm_box(bm, (k * 2.5, y, 10.3 + z * 2.6), (2.4, 12.0, 2.5), 5 + rng.randrange(6))
        y += 13.0
    S.obj(name + "_b", S.mesh_from_bm(name + "_b", bm, [hullc, anti, deckm, white, win] + cont), parent=root)
    return root


# ================================================================ effects
def splash(name, loc, f0, size=1.0, frames=None):
    """White spray column + foam ring at loc from frame f0 (rises in ~6 frames, falls and fades over ~50)."""
    sm = spray_mat()
    rng = random.Random(hash(name) & 0xffff)
    objs = []
    for k in range(24):
        bm = bmesh.new()
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in res["verts"]:
            v.co *= 1.0 + rng.uniform(-0.2, 0.2)
        h = rng.uniform(0.05, 1.0)
        r = (1.0 - h) * 1.6 + 0.3
        a = rng.uniform(0, 2 * math.pi)
        off = Vector((math.cos(a) * r, math.sin(a) * r, h * 13.0)) * size
        o = S.obj("%s_s%d" % (name, k), S.mesh_from_bm("%s_s%d" % (name, k), bm, [sm], smooth=True),
                  Vector(loc) + off)
        sc = (0.8 + 1.2 * (1 - h)) * size
        base = Vector(loc) + off
        set_keys(o, "scale", [1, f0, f0 + 6, f0 + 30, f0 + 55],
                 [(0, 0, 0), (0.05, 0.05, 0.05), (sc, sc, sc * 2.0), (sc * 1.25, sc * 1.25, sc * 1.6), (0, 0, 0)],
                 "LINEAR")
        set_keys(o, "location", [f0, f0 + 6, f0 + 55],
                 [tuple(Vector(loc) + off * 0.3), tuple(base), tuple(base - Vector((0, 0, 6.0 * size * h)))],
                 "BEZIER")
        o.visible_shadow = True
        objs.append(o)
    # foam ring on the water
    m, sock = L.add_mat(name + "_foam", hexc("ffffff"), 0.0)
    ring = _annulus_obj(name + "_ring", 4.0 * size, 2.5 * size, (loc[0], loc[1], 0.12), m, 48)
    L.kf_socket(sock, 1, 0.0, "LINEAR")
    L.kf_socket(sock, f0, 0.0, "LINEAR")
    L.kf_socket(sock, f0 + 4, 1.6, "LINEAR")
    L.kf_socket(sock, f0 + 70, 0.0, "LINEAR")
    set_keys(ring, "scale", [f0, f0 + 70], [(0.4, 0.4, 1), (3.2, 3.2, 1)], "LINEAR")
    return objs


def red_ring(name, loc, f0, r=14.0, w=1.6, frames=900):
    m, sock = L.add_mat(name, hexc("ff2a2a"), 0.0)
    o = _annulus_obj(name, r, w, (loc[0], loc[1], 0.25), m, 72)
    L.kf_socket(sock, 1, 0.0, "LINEAR")
    if f0 > 1:
        L.kf_socket(sock, f0, 0.0, "LINEAR")
    L.kf_socket(sock, f0 + 8, 6.0, "LINEAR")
    f = f0 + 8
    while f < frames + 30:
        L.kf_socket(sock, f + 15, 3.0, "BEZIER")
        L.kf_socket(sock, f + 30, 6.0, "BEZIER")
        f += 30
    set_keys(o, "scale", [max(1, f0), f0 + 10], [(0.5, 0.5, 1), (1, 1, 1)], "BEZIER")
    return o


def path_keys(o, fn, T, step=2, rot=True, interp="LINEAR"):
    """Keys location (and heading) from fn(frame) -> (x, y, z)."""
    fr = list(range(1, T + 1, step)) + ([T] if (T - 1) % step else [])
    locs = [fn(f) for f in fr]
    set_keys(o, "location", fr, locs, interp)
    if rot:
        rots = []
        for i, f in enumerate(fr):
            a = Vector(locs[max(0, i - 1)])
            b = Vector(locs[min(len(locs) - 1, i + 1)])
            d = b - a
            rots.append((0.0, 0.0, math.atan2(-d.x, d.y) if d.length > 1e-4 else 0.0))
        # unwrap
        for i in range(1, len(rots)):
            z = rots[i][2]
            while z - rots[i - 1][2] > math.pi:
                z -= 2 * math.pi
            while z - rots[i - 1][2] < -math.pi:
                z += 2 * math.pi
            rots[i] = (0.0, 0.0, z)
        set_keys(o, "rotation_euler", fr, rots, interp)


# ================================================================ world
def _palm_templates(rng):
    trunk = S.pbr("palm_trunk", hexc("8a7456"), 0.9, var=0.1)
    leaf = S.pbr("palm_leaf", hexc("4f7a35"), 0.8, var=0.12, bump=0.05)
    out = []
    for i in range(3):
        def build(bm, i=i):
            h = 8.0 + i * 1.5
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.35, radius2=0.22, depth=h)
            bmesh.ops.translate(bm, vec=(0.25 * i, 0, h / 2), verts=res["verts"])
            for k in range(9):
                a = 2 * math.pi * k / 9 + i
                res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
                bmesh.ops.scale(bm, vec=(2.6, 0.45, 0.12), verts=res["verts"])
                bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                                 matrix=__import__("mathutils").Matrix.Rotation(-0.45, 3, "Y"))
                bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                                 matrix=__import__("mathutils").Matrix.Rotation(a, 3, "Z"))
                bmesh.ops.translate(bm, vec=(0.25 * i + 2.2 * math.cos(a), 2.2 * math.sin(a), h - 0.6), verts=res["verts"])
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 1
        out.append(S._template("palm_t%d" % i, build, [trunk, leaf]))
    return out


def _breakwater(name, pts, width=20.0, top=4.2):
    """Rubble-mound breakwater along a polyline: sloped rock sides, concrete crown walkway."""
    rock = rock_mat()
    crown = S.pbr("bw_crown", hexc("cfc8ba"), 0.85, var=0.06, bump=0.05)
    bm = bmesh.new()
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        d = Vector((x1 - x0, y1 - y0, 0))
        ln = d.length
        d.normalize()
        nrm = Vector((-d.y, d.x, 0))
        a0, a1 = Vector((x0, y0, 0)) - d * width * 0.5, Vector((x1, y1, 0)) + d * width * 0.5
        prof = [(-width * 0.5 - 9.0, -6.0), (-width * 0.5, top - 0.3), (width * 0.5, top - 0.3), (width * 0.5 + 9.0, -6.0)]
        ra = [tuple(a0 + nrm * s + Vector((0, 0, z))) for s, z in prof]
        rb = [tuple(a1 + nrm * s + Vector((0, 0, z))) for s, z in prof]
        _loft(bm, [ra, rb], mi_fn=lambda c: 0)
        for f in bm.faces:
            pass
        # crown slab
        S.bm_box(bm, tuple((a0 + a1) / 2 + Vector((0, 0, top))), (abs(d.x) * (ln + width) + abs(d.y) * width * 0.7,
                                                                 abs(d.y) * (ln + width) + abs(d.x) * width * 0.7, 0.8), 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    S.obj(name, S.mesh_from_bm(name, bm, [rock, crown]))


def _lighthouse(name, x, y, z0, color):
    white = S.pbr("lh_white", hexc("f1f1ee"), 0.6, var=0.03)
    band = S.pbr("lh_%s" % name, color, 0.5, var=0.03)
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=2.4, radius2=1.6, depth=16.0)
    bmesh.ops.translate(bm, vec=(0, 0, 8.0), verts=res["verts"])
    for k in range(3):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=2.3 - k * 0.27, radius2=2.15 - k * 0.27,
                                    depth=1.6)
        bmesh.ops.translate(bm, vec=(0, 0, 3.0 + k * 4.5), verts=res["verts"])
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 1
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=1.4, radius2=1.4, depth=2.4)
    bmesh.ops.translate(bm, vec=(0, 0, 17.2), verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = 1
    S.obj(name, S.mesh_from_bm(name, bm, [white, band], smooth=True), (x, y, z0))


def _crane(bm, x, mi_leg, mi_boom):
    """Ship-to-shore gantry crane on the terminal quay (legs at y 6 / 36, boom out over the water)."""
    for dx in (-9.0, 9.0):
        for yy in (6.0, 36.0):
            S.bm_box(bm, (x + dx, yy, QUAY_Z + 21.0), (1.6, 1.6, 42.0), mi_leg)
        S.bm_box(bm, (x + dx, 21.0, QUAY_Z + 40.0), (1.4, 32.0, 1.6), mi_leg)
        S.bm_box(bm, (x + dx, 21.0, QUAY_Z + 12.0), (1.0, 32.0, 1.0), mi_leg)
    S.bm_box(bm, (x, -6.0, QUAY_Z + 44.0), (3.0, 92.0, 2.6), mi_boom)
    S.bm_box(bm, (x, 34.0, QUAY_Z + 47.0), (20.0, 8.0, 5.0), mi_boom)
    S.bm_box(bm, (x, 8.0, QUAY_Z + 41.5), (4.0, 6.0, 3.0), mi_leg)


def build_harbour_world(ctx, p, rng=None, sea_cut=None, corvette=True):
    """Sky + sea + port + city. Returns dict with the corvette root (moored at SHIP_HOME) unless corvette=False."""
    rng = rng or random.Random(p.get("seed", 22))
    S.daylight(ctx, p.get("sun_az", -25.0), 40.0, hdri=p.get("hdri", True))
    L.fog(p.get("fog", 0.00005), S.HAZE, start=900.0)
    C.horizon_haze(ctx.scene, hi=0.09)
    # sea (cut for the cutaway: only y >= sea_cut)
    if sea_cut is None:
        S.plane_obj("sea", 2 * EXT, EXT, (0, -EXT / 2, 0.0), sea_mat())
    else:
        S.plane_obj("sea", 2 * EXT, -sea_cut, (0, sea_cut / 2, 0.0), sea_mat())
        bm = bmesh.new()
        _poly_xz(bm, [(-600, 0.0), (600, 0.0), (600, -60.0), (-600, -60.0)], sea_cut, 0, flip=True)
        sec = S.obj("sea_section", S.mesh_from_bm("sea_section", bm, [sea_section_mat()]))
        sec.visible_shadow = False
        bm = bmesh.new()
        _poly_xz(bm, [(-600, 0.12), (600, 0.12), (600, -0.25), (-600, -0.25)], sea_cut - 0.01, 0, flip=True)
        S.obj("sea_edge", S.mesh_from_bm("sea_edge", bm, [S.emis("sea_edge_m", hexc("d8f6ff"), 1.4)]))
    # land: port apron (near) + far land (hazes out)
    S.plane_obj("land", 12000, 10000, (0, 5000, QUAY_Z), ground_mat())
    S.plane_obj("far_land", 2 * EXT, EXT, (0, EXT / 2 + 9800, QUAY_Z - 0.4),
                C.far_ground_mat("far_land_sea", hexc("a49a7a"), haze_mul=4.0))
    # quay wall along y = 0 (concrete) + rock revetment outside the port
    quay = S.pbr("quay_wall", hexc("b9b3a6"), 0.85, var=0.06, bump=0.05)
    bm = bmesh.new()
    S.bm_box(bm, (100.0, -0.6, (QUAY_Z - 4.0) / 2), (1600.0, 1.2, QUAY_Z + 4.0), 0)
    S.obj("quay", S.mesh_from_bm("quay", bm, [quay]))
    rock = rock_mat()
    for x0, x1 in ((-4000.0, -700.0), (900.0, 4000.0)):
        bm = bmesh.new()
        S.bm_prism_x(bm, x0, x1, [(0.5, QUAY_Z), (-14.0, -3.0), (0.5, -3.0)], 0)
        S.obj("revet%d" % int(x0), S.mesh_from_bm("revet", bm, [rock]))
    # naval finger pier
    bm = bmesh.new()
    S.bm_box(bm, (PIER_X, PIER_Y1 / 2, (QUAY_Z - 3.0) / 2), (PIER_W, -PIER_Y1, QUAY_Z + 3.0), 0)
    for k in range(12):   # bollards
        S.bm_box(bm, (PIER_X + PIER_W / 2 - 0.8, -12.0 - k * 18.0, QUAY_Z + 0.4), (0.6, 0.6, 0.8), 1)
    S.obj("pier", S.mesh_from_bm("pier", bm, [quay, S.pbr("bollard", hexc("2d3136"), 0.5, var=0)]))
    _breakwater("bw_w", BW_W)
    _breakwater("bw_e", BW_E)
    _lighthouse("lh_w", BW_W[-1][0], BW_W[-1][1], 4.2, hexc("c9342b"))
    _lighthouse("lh_e", BW_E[-1][0], BW_E[-1][1], 4.2, hexc("2e8a4e"))
    # terminal: cranes, containers, warehouses
    red = S.pbr("crane_red", hexc("c8442f"), 0.5, 0.2, var=0.04)
    wht = S.pbr("crane_white", hexc("e9ebec"), 0.5, 0.1, var=0.03)
    bm = bmesh.new()
    for x in (260.0, 380.0, 500.0, 640.0):
        _crane(bm, x, 0, 1)
    S.obj("cranes", S.mesh_from_bm("cranes", bm, [red, wht]))
    cont = [S.pbr("ycont_%d" % i, hexc(c), 0.6, var=0.06) for i, c in
            enumerate(("b8432f", "2f6db3", "d9a325", "3f8a57", "c9ccd0", "7b4b8e", "d26a2a"))]
    bm = bmesh.new()
    for row in range(8):
        for col in range(9):
            if rng.random() < 0.15:
                continue
            x = 200.0 + col * 70.0
            y = 70.0 + row * 17.0
            for k in range(4):
                hgt = rng.randint(1, 4)
                for z in range(hgt):
                    S.bm_box(bm, (x + k * 13.0, y, QUAY_Z + 1.3 + z * 2.6), (12.2, 2.4, 2.55), rng.randrange(7))
    S.obj("containers", S.mesh_from_bm("containers", bm, cont))
    wh_wall = [S.pbr("wh_wall%d" % i, hexc(c), 0.7, var=0.05) for i, c in enumerate(("d9d2c2", "c9c1ae", "e4dfd3"))]
    roofm = S.corrugated_mat("wh_roof", hexc("8f9499"))
    navy = S.pbr("naval_bldg", hexc("aeb3b6"), 0.7, var=0.05)
    bm = bmesh.new()
    for i in range(7):
        x = -660.0 + i * 95.0
        if abs(x - PIER_X) < 40:
            continue
        w, d, h = rng.uniform(55, 75), rng.uniform(35, 60), rng.uniform(9, 14)
        y = 40.0 + d / 2 + rng.uniform(0, 30)
        S.bm_box(bm, (x, y, QUAY_Z + h / 2), (w, d, h), i % 3)
        S.bm_box(bm, (x, y, QUAY_Z + h + 0.3), (w + 1, d + 1, 0.6), 3)
    for x, y, w, d, h in ((-520.0, 150.0, 40.0, 22.0, 16.0), (-380.0, 160.0, 34.0, 20.0, 12.0)):
        S.bm_box(bm, (x, y, QUAY_Z + h / 2), (w, d, h), 4)
    S.obj("warehouses", S.mesh_from_bm("warehouses", bm, wh_wall + [roofm, navy]))
    # coast road (y 250..266) + promenade + palms
    road = C.asphalt_mat("coast_road", hexc("4c4f54"))
    S.plane_obj("coast_road", 8000, 16, (0, 258.0, QUAY_Z + 0.08), road)
    walk = S.pbr("promenade_sea", hexc("d6cdb8"), 0.8, var=0.05, var_scale=0.2)
    S.plane_obj("promenade", 8000, 8, (0, 241.0, QUAY_Z + 0.06), walk)
    palms = _palm_templates(rng)
    pts = [(x, 245.0 + rng.uniform(-1.5, 1.5)) for x in range(-3000, 3001, 28)]
    pal = S.scatter(palms, pts, rng, (0.85, 1.15), prefix="palm")
    for o in pal:
        o.location.z = QUAY_Z
    # city (flat-roofed, sand / white, a few taller blocks), one mesh
    walls = [S.facade_mat("seacity_%d" % i, hexc(c), hexc(g), 3.4, 3.3, wf) for i, (c, g, wf) in enumerate((
        ("efe7d6", "3b5268", 0.45), ("e6d8bc", "41566b", 0.4), ("f4f1ea", "34495e", 0.5), ("dccbad", "3a4a5a", 0.42),
        ("ece2cc", "4a6a86", 0.5), ("d9cdb5", "2f4a63", 0.4)))]
    roofc = S.pbr("seacity_roof", hexc("cbc2b0"), 0.85, var=0.08, bump=0.04)
    bm = bmesh.new()
    streets = bmesh.new()
    tree_pts = []
    blk = 110.0
    n_b = 0
    for xi in range(-26, 26):
        for yi in range(0, 40):
            x0, y0 = xi * blk, 290.0 + yi * blk
            C._fast_box(streets, x0 + blk / 2, y0 + 6, QUAY_Z, blk, 12.0, 0.15, 0, 0)
            C._fast_box(streets, x0 + 6, y0 + blk / 2, QUAY_Z, 12.0, blk, 0.12, 0, 0)
            if rng.random() < 0.06:
                for _ in range(8):
                    tree_pts.append((x0 + rng.uniform(20, blk - 10), y0 + rng.uniform(20, blk - 10)))
                continue
            centre = math.exp(-((x0 + 200) / 900.0) ** 2 - ((y0 - 700) / 700.0) ** 2)
            for k in range(4):
                qx = x0 + 12 + (k % 2) * 49 + 24.5
                qy = y0 + 12 + (k // 2) * 49 + 24.5
                w, d = rng.uniform(26, 44), rng.uniform(24, 42)
                h = rng.uniform(9, 22) if rng.random() > centre * 0.6 else rng.uniform(28, 62)
                C._fast_box(bm, qx, qy, QUAY_Z, w, d, h, 0, rng.randrange(6))
                C._fast_box(bm, qx, qy, QUAY_Z + h, w + 0.6, d + 0.6, 0.9, 0, 6)
                if rng.random() < 0.3:
                    C._fast_box(bm, qx + rng.uniform(-5, 5), qy, QUAY_Z + h + 0.9, 6, 5, 2.6, 0, 6)
                n_b += 1
            if rng.random() < 0.5:
                tree_pts.append((x0 + rng.uniform(15, blk - 5), y0 + 9))
    S.obj("city", S.mesh_from_bm("city", bm, walls + [roofc]))
    S.obj("streets", S.mesh_from_bm("streets", streets, [C.asphalt_mat("sea_street", hexc("5a5c60"))]))
    trees = S.tree_templates(rng)
    tr = S.scatter(trees + palms, tree_pts, rng, (0.8, 1.2), prefix="ctree")
    for o in tr:
        o.location.z = QUAY_Z
    # hills
    # (no far hills: under the haze they read as dark smudges on the horizon)
    print("[v2 sea] harbour world: %d city buildings" % n_b)
    out = {"rng": rng}
    # traffic on the coast road
    T = ctx.frames
    v = 13.0 / ctx.fps
    for i in range(18):
        d = 1 if i % 2 == 0 else -1
        x0 = rng.uniform(-1500, 1500)
        c = L.make_car("cc%d" % i, loc=(x0, 258.0 - 3.5 * d, QUAY_Z + 0.1), rot_z=-math.pi / 2 * d,
                       headlights=False, glow=False)
        set_keys(c.obj, "location", [1, T], [(x0, 258.0 - 3.5 * d, QUAY_Z + 0.1),
                                            (x0 + d * v * (T - 1), 258.0 - 3.5 * d, QUAY_Z + 0.1)], "LINEAR")
    S._repaint_kenney()
    # moored cargo ship at the terminal + merchant ship at anchor + tugs moving in the basin
    m1 = make_merchant("moored", 150.0)
    m1.location = (450.0, -14.0, 0.0)
    m1.rotation_euler = (0, 0, -math.pi / 2)
    if p.get("merchant", True):
        mr = make_merchant("merchant", 130.0)
        mr.location = (MERCHANT[0], MERCHANT[1], 0.0)
        mr.rotation_euler = (0, 0, math.radians(p.get("merchant_rot", 115.0)))
        out["merchant"] = mr
    for k, (x0, y0, ang, sp, col) in enumerate(((60.0, -260.0, 1.2, 2.5, hexc("c8452f")),
                                                (520.0, -200.0, -1.9, 2.0, hexc("2f6db3")),
                                                (-150.0, -120.0, 0.4, 1.6, hexc("e0b23a")))):
        if not p.get("tugs", True):
            break
        tg = make_tug("tug%d" % k, col, 16.0 + 4 * k)
        dx, dy = -math.sin(ang), math.cos(ang)
        vv = sp / ctx.fps
        set_keys(tg, "location", [1, T], [(x0, y0, 0.0), (x0 + dx * vv * (T - 1), y0 + dy * vv * (T - 1), 0.0)], "LINEAR")
        tg.rotation_euler = (0, 0, ang)
    if corvette:
        root, info = make_corvette("corvette")
        root.location = (SHIP_HOME[0], SHIP_HOME[1], 0.0)
        root.rotation_euler = (0, 0, math.pi)
        out["corvette"] = root
    return out


def _cam(ctx, loc, tgt, lens, clip=1.0):
    """clip_start matters: with 0.3 m the wakes (a few cm above the water) z-fight from 400 m up."""
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = clip
    cam.data.clip_end = 30000.0
    return cam


def _roll(root, keys, rot_z):
    """keys = [(frame, roll_deg, sink_m)] -> roll about the ship's long axis + sink (BEZIER)."""
    set_keys(root, "rotation_euler", [f for f, _, _ in keys], [(0.0, math.radians(r), rot_z) for _, r, _ in keys],
             "BEZIER")
    x, y = root.location.x, root.location.y
    set_keys(root, "location", [f for f, _, _ in keys], [(x, y, -s) for _, _, s in keys], "BEZIER")


# ================================================================ BUILDERS
def b_harbour_hook(ctx, p):
    """The corvette moored at the naval pier; low dark sea drones race in across the basin with white wakes;
    on `hit_cue` white splashes at the hull; from `list_cue` the ship lists and rolls over, settling low.
    Camera pulls back to reveal the port. Anchor: ship."""
    T = ctx.frames
    w = build_harbour_world(ctx, p)
    ship = w["corvette"]
    f_hit = ctx.word_time(p.get("hit_cue", "struck"), 0.3)
    f_list = ctx.word_time(p.get("list_cue", "capsized"), 0.6)
    sx, sy = SHIP_HOME
    hull_e = sx + CV_HB + 0.5          # east side of the hull (bow south: local -x = world +x)
    hits = [(hull_e, sy - 8.0), (hull_e, sy + 10.0)]
    for k, (hx, hy) in enumerate(hits):
        fh = f_hit + 7 * k
        start = Vector((hx + 38.0 + 14 * k, hy - 78.0 + 22 * k, 0.0))
        end = Vector((hx + 1.5, hy, 0.0))
        d = make_drone("dr%d" % k)
        path_keys(d, lambda f, s=start, e=end, fh=fh: tuple(s.lerp(e, min(1.0, (f - 1) / max(1, fh - 1)))), T)
        vis_keys(d, [(1, True), (fh, False)])
        splash("sp%d" % k, (hx + 0.6, hy, 0.0), fh, 1.9)
    _roll(ship, [(1, 0, 0), (f_hit + 10, 0, 0), (f_hit + 40, -4, 0.3), (f_list, -9, 0.8),
                 (f_list + 50, -38, 1.6), (T + 30, -88, 3.2)], math.pi)
    S.anchor(ctx, "ship", ship, (0, 0, 10.0))
    c0 = p.get("cam0", (sx + 85.0, sy - 105.0, 26.0))
    t0 = p.get("tgt0", (sx + 5.0, sy - 5.0, 12.0))
    c1 = p.get("cam1", (sx + 150.0, sy - 190.0, 48.0))
    t1 = p.get("tgt1", (sx, sy + 10.0, 14.0))
    _cam(ctx, c0, t0, p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_harbour_wide(ctx, p):
    """High wide view over the port from the sea: the corvette lies rolled over by the pier (red ring); the
    merchant ship at anchor off the port gets a red ring on `merchant_cue` (off with `merchant_ring: false`). Anchors: ship, merchant."""
    T = ctx.frames
    w = build_harbour_world(ctx, p)
    ship = w["corvette"]
    sx, sy = SHIP_HOME
    _roll(ship, [(1, -88, 3.2), (T, -92, 3.4)], math.pi)
    red_ring("ring_ship", (sx + 2.0, sy), 1, r=40.0, w=3.0, frames=T)
    if p.get("merchant_ring", True):
        f_m = ctx.word_time(p.get("merchant_cue", "merchant"), 0.3)
        mx, my = MERCHANT
        red_ring("ring_mer", (mx, my), f_m, r=95.0, w=5.0, frames=T)
    S.anchor(ctx, "ship", ship, (0, 0, 4.0))
    S.anchor(ctx, "merchant", w["merchant"], (0, 0, 22.0))
    c0 = p.get("cam0", (2250.0, -2750.0, 330.0))
    t0 = p.get("tgt0", (650.0, -650.0, 0.0))
    c1 = p.get("cam1", (2150.0, -2600.0, 300.0))
    t1 = p.get("tgt1", (600.0, -600.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 32), clip=20.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t1)])


def b_drone_low_v2(ctx, p):
    """Low tracking shot beside a sea drone skimming across the open sea towards the port (wake, spray);
    the camera rides at its height so it barely clears the waves. Anchor: drone."""
    T = ctx.frames
    build_harbour_world(ctx, p)
    sp = p.get("speed", 18.0) / ctx.fps
    ang = math.radians(p.get("heading", -20.0))        # heading (0 = north)
    dx, dy = -math.sin(ang), math.cos(ang)
    x0, y0 = p.get("start", (260.0, -1500.0))
    d = make_drone("drone")
    path_keys(d, lambda f: (x0 + dx * sp * (f - 1), y0 + dy * sp * (f - 1), 0.0), T)
    # bow spray: small splash puffs that keep repeating? (static wake is enough)
    rig = L.link(bpy.data.objects.new("rig", None))
    path_keys(rig, lambda f: (x0 + dx * sp * (f - 1), y0 + dy * sp * (f - 1), 0.0), T, rot=True)
    cam = _cam(ctx, (0, 0, 0), (0, 0, 0), p.get("lens", 30))
    cam.parent = rig
    ctx.cam_target.parent = rig
    o0, o1 = p.get("off0", (16.0, -27.0, 3.6)), p.get("off1", (13.0, -19.0, 3.0))
    set_keys(cam, "location", [1, T], [tuple(o0), tuple(o1)], "BEZIER")
    set_keys(ctx.cam_target, "location", [1, T], [(0.0, 5.0, 1.6), (0.0, 5.0, 1.4)], "BEZIER")
    S.anchor(ctx, "drone", d, (0, -0.8, 1.4))


def b_swarm_v2(ctx, p):
    """Aerial: the corvette at sea off the port; sea drones converge from several directions with wakes; amber
    rings mark them on `swarm_cue`; on `guns_cue` two are stopped short (white splash) and the rest keep coming
    (the beat ends before any reaches the ship). Anchor: ship."""
    T = ctx.frames
    w = build_harbour_world(ctx, p, corvette=False)
    sxy = Vector(p.get("ship", (420.0, -1300.0)))
    root, _ = make_corvette("cv_sea")
    rz = math.radians(p.get("ship_rot", -70.0))
    vs = 2.5 / ctx.fps
    dxs, dys = -math.sin(rz), math.cos(rz)
    set_keys(root, "location", [1, T], [(sxy.x, sxy.y, 0.0), (sxy.x + dxs * vs * T, sxy.y + dys * vs * T, 0.0)],
             "LINEAR")
    root.rotation_euler = (0, 0, rz)
    make_wake("cv_sea_wake", root, 80.0, 1.6, y0=-CV_L / 2)
    f_sw = ctx.word_time(p.get("swarm_cue", "several"), 0.65)
    f_g = ctx.word_time(p.get("guns_cue", "guns"), 0.85)
    n = 6
    sp = 12.0 / ctx.fps
    stop = {1: f_g, 4: f_g + 9}
    for k in range(n):
        a = math.radians(-55.0 - 42.0 + k * 17.0 + 4 * math.sin(k))
        r0 = p.get("r0", 250.0) + 25 * (k % 2)
        start = Vector((sxy.x + math.cos(a) * r0, sxy.y + math.sin(a) * r0, 0.0))
        tgt = Vector((sxy.x, sxy.y, 0.0))
        dirv = (tgt - start).normalized()
        d = make_drone("sw%d" % k, wake_len=36.0)
        fs = stop.get(k)

        def pos(f, s=start, dv=dirv, fs=fs):
            ff = min(f, fs) if fs else f
            return tuple(s + dv * sp * (ff - 1))
        path_keys(d, pos, T)
        m, sock = L.add_mat("swr%d" % k, hexc("ffb020"), 0.0)
        ring = _annulus_obj("swr%d" % k, 9.0, 1.4, (0, 0, 0.3), m, 48)
        ring.parent = d
        L.kf_socket(sock, 1, 0.0, "LINEAR")
        L.kf_socket(sock, f_sw + 3 * k, 0.0, "LINEAR")
        L.kf_socket(sock, f_sw + 3 * k + 8, 5.0, "LINEAR")
        if fs:
            L.kf_socket(sock, fs, 5.0, "LINEAR")
            L.kf_socket(sock, fs + 4, 0.0, "LINEAR")
            vis_keys(d, [(1, True), (fs + 2, False)])
            splash("sws%d" % k, pos(fs), fs, 0.7)
    S.anchor(ctx, "ship", root, (0, 0, 12.0))
    off0 = Vector(p.get("cam_off0", (-230.0, 330.0, 420.0)))
    off1 = Vector(p.get("cam_off1", (-200.0, 290.0, 370.0)))
    c0, c1 = sxy.to_3d() + off0, sxy.to_3d() + off1
    _cam(ctx, tuple(c0), (sxy.x, sxy.y, 0.0), p.get("lens", 24), clip=20.0)
    A._cam_keys(ctx, [(1, tuple(c0), (sxy.x + 40, sxy.y - 70, 0.0)), (T, tuple(c1), (sxy.x + 45, sxy.y - 75, 0.0))])


def b_waterline_v2(ctx, p):
    """Low, close view of the moored corvette's side from the water: a red glowing line draws along its waterline
    on `line_cue`; a sea drone runs in and on `hit_cue` a white splash rises at the hull, a red ring pulses on the
    water. Anchor: waterline."""
    T = ctx.frames
    w = build_harbour_world(ctx, p)
    ship = w["corvette"]
    sx, sy = SHIP_HOME
    f_line = ctx.word_time(p.get("line_cue", "water"), 0.2)
    f_hit = ctx.word_time(p.get("hit_cue", "hole"), 0.7)
    # waterline glow strip on the east side (local -x with the bow south)
    m = S.emis("wl_red", hexc("ff3030"), 5.0)
    bm = bmesh.new()
    ys = [y * 0.5 for y in range(-60, 57)]
    for y0_, y1_ in zip(ys[:-1], ys[1:]):
        x0_, x1_ = -cv_dims(y0_)[0] * 0.995 - 0.06, -cv_dims(y1_)[0] * 0.995 - 0.06
        vs_ = [bm.verts.new((x0_, y0_, -0.12)), bm.verts.new((x1_, y1_, -0.12)),
               bm.verts.new((x1_, y1_, 0.28)), bm.verts.new((x0_, y0_, 0.28))]
        bm.faces.new(vs_)
    strip = S.obj("wl_strip", S.mesh_from_bm("wl_strip", bm, [m]), parent=ship)
    strip.visible_shadow = False
    md = strip.modifiers.new("build", "BUILD")
    md.frame_start = f_line
    md.frame_duration = 25
    hx, hy = sx + CV_HB + 0.4, sy - 4.0
    d = make_drone("drw")
    start = Vector((hx + 120.0, hy - 110.0, 0.0))
    end = Vector((hx + 1.2, hy, 0.0))
    path_keys(d, lambda f: tuple(start.lerp(end, min(1.0, (f - 1) / max(1, f_hit - 1)))), T)
    vis_keys(d, [(1, True), (f_hit, False)])
    splash("spw", (hx + 0.5, hy, 0.0), f_hit, 1.9)
    red_ring("wl_ring", (hx + 2.0, hy), f_hit + 6, r=10.0, w=1.0, frames=T)
    _roll(ship, [(1, 0, 0), (f_hit + 12, 0, 0), (T + 20, -6, 0.5)], math.pi)
    e = L.link(bpy.data.objects.new("anc_wl", None))
    e.location = (hx, hy + 12.0, 0.2)
    S.anchor(ctx, "waterline", e)
    c0 = p.get("cam0", (sx + 62.0, sy - 62.0, 3.0))
    t0 = p.get("tgt0", (sx + 3.0, sy - 2.0, 3.5))
    c1 = p.get("cam1", (sx + 52.0, sy - 50.0, 2.6))
    _cam(ctx, c0, t0, p.get("lens", 30))
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])


def b_cutaway_v2(ctx, p):
    """Cutaway: the corvette cut across its length, seen from the cut, in the harbour; the sea in front is cut too.
    mode 'flood': a hole opens at the starboard waterline (red rim, inflow arrows) on `flood_cue`; water rises in the
    hull and the ship sits lower with a slight list. mode 'roll': water sloshes to one side on `slosh_cue`, it leans
    on `lean_cue` and rolls over on `roll_cue`. Anchor: flood."""
    T = ctx.frames
    mode = p.get("mode", "flood")
    build_harbour_world(ctx, p, sea_cut=CUT_Y, corvette=False)
    root, info = make_corvette("cv_cut", y_min=0.0, cut=True)
    root.location = (CUT_X, CUT_Y - 0.15, 0.0)
    inner = info["inner_poly"]
    y0 = info["y0"]
    # states: (frame, roll_deg, sink, water_frac)
    if mode == "flood":
        f0 = ctx.word_time(p.get("flood_cue", "water"), 0.05)
        f1 = ctx.word_time(p.get("lower_cue", "lower"), 0.6)
        states = [(1, 0.0, 0.0, 0.0), (f0 + 4, 0.0, 0.0, 0.0), (f1, 3.0, 0.7, 0.22), (T, 5.0, 1.3, 0.34)]
    else:
        fs = ctx.word_time(p.get("slosh_cue", "sloshing"), 0.4)
        fl = ctx.word_time(p.get("lean_cue", "leans"), 0.75)
        fr = ctx.word_time(p.get("roll_cue", "rolls"), 0.88)
        states = [(1, 5.0, 1.3, 0.34), (max(2, fs - 10), 5.0, 1.35, 0.36), (fs + 25, 14.0, 1.5, 0.38),
                  (fl, 22.0, 1.7, 0.4), (fr, 40.0, 2.0, 0.42), (min(T, fr + 45), 125.0, 3.2, 0.44),
                  (T, 132.0, 3.4, 0.44)]

    def state(f):
        for (fa, ra, sa, wa), (fb, rb, sb, wb) in zip(states[:-1], states[1:]):
            if fa <= f <= fb:
                u = L.smooth((f - fa) / max(1, fb - fa))
                return ra + (rb - ra) * u, sa + (sb - sa) * u, wa + (wb - wa) * u
        return states[-1][1], states[-1][2], states[-1][3]
    fr_all = list(range(1, T + 1, 2)) + ([T] if (T - 1) % 2 else [])
    set_keys(root, "rotation_euler", fr_all, [(0.0, math.radians(state(f)[0]), 0.0) for f in fr_all], "LINEAR")
    set_keys(root, "location", fr_all, [(CUT_X, CUT_Y - 0.15, -state(f)[1]) for f in fr_all], "LINEAR")
    # flood water: one polygon object per 2 frames (CONSTANT scale swap)
    wm = S.pbr("flood_water", hexc("2f9fd6"), 0.15, var=0)
    wm.node_tree.nodes.get("Principled BSDF").inputs["Emission Color"].default_value = hexc("2f9fd6")
    wm.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 0.5
    prev = None
    objs = []
    for f in fr_all:
        th, _, frac = state(f)
        poly = water_poly(inner, math.radians(th), frac)
        key = (round(th, 2), round(frac, 4))
        if len(poly) < 3:
            prev = None
            continue
        if prev is not None and prev[0] == key:
            objs[-1][2] = f
            continue
        bm = bmesh.new()
        _poly_xz(bm, poly, y0 - 0.06, 0, flip=True)
        o = S.obj("flood_%04d" % f, S.mesh_from_bm("flood_%04d" % f, bm, [wm]), parent=root)
        o.visible_shadow = False
        objs.append([o, f, f])
        prev = (key,)
    for i, (o, fa, fb) in enumerate(objs):
        nxt = objs[i + 1][1] if i + 1 < len(objs) else T + 5
        keys = [(1, False)] if fa > 1 else []
        keys += [(fa, True), (nxt, False)]
        vis_keys(o, keys)
    # the hole (starboard, at the waterline) + inflow arrows (flood mode); hole stays visible in roll mode
    wv, zd, zk = cv_dims(y0)
    hole = Vector((wv * 0.995, y0 - 0.08, -0.55))
    m, sock = L.add_mat("hole_rim", hexc("ff2a2a"), 0.0)
    bm = bmesh.new()
    C._annulus(bm, 0.75, 0.22, 32)
    rim = S.obj("hole_rim", S.mesh_from_bm("hole_rim", bm, [m]), parent=root)
    rim.rotation_euler = (math.pi / 2, 0, 0)
    rim.location = hole + Vector((-0.15, -0.02, 0))
    f_hole = states[1][0] if mode == "flood" else 1
    L.kf_socket(sock, 1, 0.0 if mode == "flood" else 6.0, "LINEAR")
    if mode == "flood":
        L.kf_socket(sock, f_hole, 0.0, "LINEAR")
        L.kf_socket(sock, f_hole + 6, 6.0, "LINEAR")
    gap = S.pbr("hole_dark", hexc("1d5d7e"), 0.3, var=0)
    bm = bmesh.new()
    _poly_xz(bm, [(hole.x - 0.45 + 0.4 * math.cos(a), hole.z + 0.55 * math.sin(a))
                  for a in [2 * math.pi * k / 16 for k in range(16)]], y0 - 0.075, 0, flip=True)
    g = S.obj("hole_gap", S.mesh_from_bm("hole_gap", bm, [gap]), parent=root)
    if mode == "flood":
        vis_keys(g, [(1, False), (f_hole, True)])
        am, asock = L.add_mat("arrow_m", hexc("e8fbff"), 0.0)
        for k in range(3):
            bm = bmesh.new()
            tri = [(0.0, 0.0), (0.6, 0.38), (0.6, 0.14), (1.1, 0.14), (1.1, -0.14), (0.6, -0.14), (0.6, -0.38)]
            _poly_xz(bm, tri, 0.0, 0, flip=True)
            a = S.obj("arrow%d" % k, S.mesh_from_bm("arrow%d" % k, bm, [am]), parent=root)
            zz = -0.25 - 0.35 * k
            set_keys(a, "location", [f_hole + 2 * k, f_hole + 2 * k + 40],
                     [(hole.x + 1.9, y0 - 0.1, zz), (hole.x + 0.5, y0 - 0.1, zz)], "LINEAR")
            a.visible_shadow = False
        L.kf_socket(asock, 1, 0.0, "LINEAR")
        L.kf_socket(asock, f_hole, 0.0, "LINEAR")
        L.kf_socket(asock, f_hole + 6, 4.0, "LINEAR")
        L.kf_socket(asock, f_hole + 60, 4.0, "LINEAR")
        L.kf_socket(asock, f_hole + 80, 0.0, "LINEAR")
    e = L.link(bpy.data.objects.new("anc_flood", None))
    e.parent = root
    e.location = (wv * 0.2, y0 - 0.1, -2.0)
    S.anchor(ctx, "flood", e)
    cam_loc = p.get("cam0", (CUT_X + 1.5, CUT_Y - 54.0, 6.0))
    tgt = p.get("tgt0", (CUT_X, CUT_Y, -0.5))
    cam_loc1 = p.get("cam1", (CUT_X + 1.0, CUT_Y - 50.0, 5.5))
    _cam(ctx, cam_loc, tgt, p.get("lens", 34))
    A._cam_keys(ctx, [(1, cam_loc, tgt), (T, cam_loc1, tgt)])


def b_defend_v2(ctx, p):
    """The harbour entrance from inside the basin: on `boom_cue` a floating boom (yellow floats) rises across the
    entrance; a grey patrol boat sweeps along it; on `cam_cue` a camera mast on the breakwater head sweeps a teal
    scan cone over the water; a drone outside is stopped at the boom."""
    T = ctx.frames
    w = build_harbour_world(ctx, p, corvette=False)
    f_b = ctx.word_time(p.get("boom_cue", "booms"), 0.25)
    f_c = ctx.word_time(p.get("cam_cue", "cameras"), 0.8)
    a, b = Vector((BW_W[-1][0] + 12.0, BW_W[-1][1] + 4.0, 0)), Vector((BW_E[-1][0] - 8.0, BW_E[-1][1] - 10.0, 0))
    yel = S.pbr("boom_yellow", hexc("f2c230"), 0.45, var=0.04)
    rope = S.pbr("boom_rope", hexc("3a3d40"), 0.6, var=0)
    n = 90
    bm_r = bmesh.new()
    pts = []
    for k in range(n + 1):
        u = k / n
        q = a.lerp(b, u) + Vector((0, -70.0 * math.sin(math.pi * u), 0))
        pts.append(q)
    for k in range(n + 1):
        o_ = bmesh.new()
        res = bmesh.ops.create_cone(o_, cap_ends=True, segments=10, radius1=0.9, radius2=0.9, depth=3.2)
        bmesh.ops.rotate(o_, verts=res["verts"], cent=(0, 0, 0),
                         matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"))
        fl = S.obj("float%d" % k, S.mesh_from_bm("float%d" % k, o_, [yel], smooth=True), (pts[k].x, pts[k].y, 0.25))
        d = (pts[min(n, k + 1)] - pts[max(0, k - 1)])
        fl.rotation_euler = (0, 0, math.atan2(d.y, d.x))
        fk = f_b + int(k * 0.5)
        set_keys(fl, "location", [1, fk, fk + 8], [(pts[k].x, pts[k].y, -2.5), (pts[k].x, pts[k].y, -2.5),
                                                   (pts[k].x, pts[k].y, 0.25)], "BEZIER")
    for k in range(n):
        C._cyl(bm_r, Vector((pts[k].x, pts[k].y, -0.3)), Vector((pts[k + 1].x, pts[k + 1].y, -0.3)), 0.25, 6)
    rp = S.obj("boom_rope", S.mesh_from_bm("boom_rope", bm_r, [rope]))
    set_keys(rp, "location", [1, f_b, f_b + 30], [(0, 0, -2.5), (0, 0, -2.5), (0, 0, 0)], "BEZIER")
    # patrol boat inside the boom
    pb = make_tug("patrol", hexc("8b939a"), 18.0)
    pa, pb2 = Vector((260.0, -515.0, 0.0)), Vector((720.0, -505.0, 0.0))
    path_keys(pb, lambda f: tuple(pa.lerp(pb2, (f - 1) / max(1, T - 1))), T)
    # drone outside, stopped at the boom
    dm = pts[n // 2] + Vector((0, -2.5, 0))
    ds = dm + Vector((260.0, -260.0, 0))
    dr = make_drone("drd")
    f_stop = max(f_b + 50, int(T * 0.7))
    path_keys(dr, lambda f: tuple(ds.lerp(dm, min(1.0, (f - 1) / max(1, f_stop - 1)) ** 0.8)), T)
    # camera mast on the west breakwater head with a teal scan cone
    mx, my = BW_W[-1][0] - 30.0, BW_W[-1][1] + 6.0
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 7.0), (0.6, 0.6, 14.0), 0)
    S.bm_box(bm, (0, 0.4, 14.2), (1.2, 1.6, 0.9), 1)
    S.obj("cam_mast", S.mesh_from_bm("cam_mast", bm, [S.pbr("mast_grey", hexc("9aa1a6"), 0.5, var=0),
                                                       S.pbr("mast_dark", hexc("2a3038"), 0.3, var=0)]), (mx, my, 4.2))
    cm, csock = L.add_mat("scan_cone", hexc("2ee6c8"), 0.0)
    bm = bmesh.new()
    L_ = 330.0
    sp = math.radians(11.0)
    v0 = bm.verts.new((0, 0, 0))
    arc = [bm.verts.new((L_ * math.sin(s), -L_ * math.cos(s), 0.0)) for s in [-sp + 2 * sp * k / 12 for k in range(13)]]
    for a_, b_ in zip(arc[:-1], arc[1:]):
        bm.faces.new((v0, b_, a_))
    cone = S.obj("scan", S.mesh_from_bm("scan", bm, [cm]), (mx + 4.0, my - 12.0, 0.35))
    cone.visible_shadow = False
    L.kf_socket(csock, 1, 0.0, "LINEAR")
    L.kf_socket(csock, f_c, 0.0, "LINEAR")
    L.kf_socket(csock, f_c + 8, 0.7, "LINEAR")
    set_keys(cone, "rotation_euler", [f_c, T], [(0, 0, math.radians(45)), (0, 0, math.radians(105))], "LINEAR")
    c0 = p.get("cam0", (-120.0, -470.0, 45.0))
    t0 = p.get("tgt0", (520.0, -600.0, 0.0))
    c1 = p.get("cam1", (-90.0, -480.0, 40.0))
    _cam(ctx, c0, t0, p.get("lens", 22), clip=2.0)
    A._cam_keys(ctx, [(1, c0, t0), (T, c1, t0)])


def b_harbour_outro(ctx, p):
    """Closing crane-up over the port: from low over the basin to a high wide view of harbour, city and sea."""
    T = ctx.frames
    w = build_harbour_world(ctx, p, corvette=False)
    c0 = p.get("cam0", (300.0, -420.0, 14.0))
    t0 = p.get("tgt0", (100.0, 0.0, 20.0))
    c1 = p.get("cam1", (900.0, -1900.0, 520.0))
    t1 = p.get("tgt1", (0.0, 150.0, 0.0))
    _cam(ctx, c0, t0, p.get("lens", 28), clip=2.0)
    A._cam_keys(ctx, [(1, c0, t0), (int(T * 0.4), (450.0, -800.0, 120.0), (60.0, 50.0, 10.0)), (T, c1, t1)])


S.V2_BUILDERS.update({
    "harbour_hook": b_harbour_hook,
    "harbour_wide": b_harbour_wide,
    "drone_low_v2": b_drone_low_v2,
    "swarm_v2": b_swarm_v2,
    "waterline_v2": b_waterline_v2,
    "cutaway_v2": b_cutaway_v2,
    "defend_v2": b_defend_v2,
    "harbour_outro": b_harbour_outro,
})

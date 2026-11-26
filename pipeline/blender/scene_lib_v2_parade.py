"""v2 one-shot parade-avenue builder ("parade balloons", 27 Nov 2026 #1). Registers into scene_lib_v2.V2_BUILDERS.

ONE builder (`parade_oneshot`) is used by every beat, exactly like scene_lib_v2_campus.py: every beat job builds the
identical world (same seed, same rng order) and keys ALL animation (camera + props) on the GLOBAL episode timeline
(campus TL/bake/show_between helpers), so the finished video is one continuous camera move.

World (north = +Y, the avenue runs along Y at x = 0; wind blows from the west, -X -> +X):
  west side: apartment blocks + two tall corner towers at a cross street (y = 140..160) that runs west;
  east side: a park (stone wall, autumn trees, flagpoles) and, at the south end, a small house with a front garden
  (patio umbrella, trampoline, small inflatable turkey; glowing tie-down straps appear on "tie").
  Giant helium balloon = a GENERIC orange cartoon bear (no real character, no logos) at y = 40 with 10 handler lines
  (STRETCH_TO cylinders) and 30 stylised capsule handlers; a cargo net + sandbags hold it low at the start and end.
  A second generic balloon (yellow star) lies netted further up at y = 230.
  Wind visuals: flags + lamp-post streamers (Wave modifiers on the global clock), drifting leaves, glowing wind
  arrows (beats 3-5) and glowing wind ribbons squeezing round the corner (illustration, beats 5-6).
  Weather mast at the corner: spinning anemometer + a dial (no numbers; coloured zones, ticks at 23 / 34 mph).
  No people's faces, no 3D text (all text = 2D overlays), nothing breaks.
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc
import scene_lib_v2_city as C
import scene_lib_v2_market as M
import scene_lib_v2_campus as K
from scene_lib_v2_campus import TL, bake, show_between, smooth, smoother, camera_at
from scene_lib_v2_winter import set_keys

BAL = (0.0, 40.0)          # hero balloon ground point
STAR = (0.0, 230.0)        # second (parked) balloon
CROSS_Y = (140.0, 160.0)   # cross street (runs west)
MAST = (-15.5, 134.0)
DIAL_Y = MAST[1] - 0.38
DIAL_Z = 3.8
GARDEN = (19.5, 36.0, -40.0, -8.0)
H_LOW, SZ_LOW = 6.0, 0.75   # balloon body centre height + vertical squash when netted
H_FLY = 19.5
H_MID = 13.5
WIND_X = 1.0

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def glow(name, col, strength=3.0):
    return S.emis(name, hexc(col), strength)


def mats():
    def mk():
        return {
            "pave": M.paving_mat(),
            "road": C.asphalt_mat("pa_road", hexc("4b4e54")),
            "line": S.pbr("pa_line", hexc("f2f2ee"), 0.6, var=0.0),
            "yline": S.pbr("pa_yline", hexc("e8b923"), 0.6, var=0.0),
            "curb": S.pbr("pa_curb", hexc("bdb8ae"), 0.7, var=0.05),
            "stone": S.pbr("pa_stone", hexc("a99f8f"), 0.8, var=0.08, var_scale=0.5, bump=0.06),
            "lawn": S.lawn_mat("pa_lawn", hexc("6f8f45"), stripes=False),
            "dark": S.pbr("pa_dark", hexc("2b2f35"), 0.45, var=0.03),
            "frame": S.pbr("pa_frame", hexc("3d434a"), 0.4, metal=0.6, var=0.02),
            "steel": S.pbr("pa_steel", hexc("b2b8bf"), 0.3, metal=0.9, var=0.02),
            "white": S.pbr("pa_white", hexc("f2f2f0"), 0.45, var=0.02),
            "roof": S.pbr("pa_roof", hexc("8a8c90"), 0.8, var=0.08),
            "shop": S.pbr("pa_shop", hexc("2c3a48"), 0.15, var=0.02),
            "awning": S.pbr("pa_awning", hexc("1f4f7a"), 0.7, var=0.03),
            "b1": S.facade_mat("pa_b1", hexc("d9cdb8"), hexc("3a5268"), 2.6, 3.4, 0.5),
            "b2": S.facade_mat("pa_b2", hexc("b88a6a"), hexc("33495e"), 2.4, 3.3, 0.45),
            "b3": S.facade_mat("pa_b3", hexc("e6e1d6"), hexc("3f5b75"), 2.8, 3.5, 0.55),
            "b4": S.facade_mat("pa_b4", hexc("c9b38f"), hexc("2f4458"), 2.5, 3.4, 0.5),
            "tower": S.facade_mat("pa_tower", hexc("cfd6de"), hexc("42617f"), 1.8, 3.8, 0.8),
            "tower2": S.facade_mat("pa_tower2", hexc("ddd3c2"), hexc("36506a"), 2.2, 3.6, 0.65),
            "brick": S.facade_mat("pa_brick", hexc("a5553f"), hexc("2f3d4c"), 2.2, 3.2, 0.42),
            # balloon (saturated, glossy vinyl)
            "orange": S.pbr("pa_orange", hexc("f27a1a"), 0.32, coat=0.5, var=0.02),
            "cream": S.pbr("pa_cream", hexc("f7e4c4"), 0.35, coat=0.5, var=0.02),
            "scarf": S.pbr("pa_scarf", hexc("d42a3c"), 0.35, coat=0.5, var=0.02),
            "eye": S.pbr("pa_eye", hexc("1b1d26"), 0.25, coat=0.6, var=0.0),
            "yellow": S.pbr("pa_yellow", hexc("ffc81a"), 0.3, coat=0.5, var=0.02),
            "blue": S.pbr("pa_bluebal", hexc("2f7be0"), 0.3, coat=0.5, var=0.02),
            "net": S.pbr("pa_net", hexc("3b4a34"), 0.8, var=0.05),
            "sand": S.pbr("pa_sand", hexc("b59d6e"), 0.9, var=0.1, bump=0.08),
            "rope": S.pbr("pa_rope", hexc("f1eee5"), 0.7, var=0.0),
            "suit": S.pbr("pa_suit", hexc("2f6ad0"), 0.6, var=0.03),
            "suit2": S.pbr("pa_suit2", hexc("e04a3a"), 0.6, var=0.03),
            "skin": S.pbr("pa_skin", hexc("c99872"), 0.6, var=0.02),
            "cap": S.pbr("pa_cap", hexc("f4f4f2"), 0.6, var=0.02),
            "barrier": S.pbr("pa_barrier", hexc("2958b8"), 0.5, var=0.03),
            # wind visuals
            "wind": glow("pa_wind", "e9fbff", 4.5),
            "wind2": glow("pa_wind2", "7ff3e2", 3.6),
            "f1": S.pbr("pa_f1", hexc("e2452f"), 0.7, var=0.03),
            "f2": S.pbr("pa_f2", hexc("1f3f7a"), 0.7, var=0.03),
            "f3": S.pbr("pa_f3", hexc("f2b21c"), 0.7, var=0.03),
            "f4": S.pbr("pa_f4", hexc("2aa68f"), 0.7, var=0.03),
            "leaf1": S.pbr("pa_leaf1", hexc("e0761c"), 0.8, var=0.05),
            "leaf2": S.pbr("pa_leaf2", hexc("c9431e"), 0.8, var=0.05),
            "leaf3": S.pbr("pa_leaf3", hexc("e7b326"), 0.8, var=0.05),
            # dial
            "g_green": S.pbr("pa_dgreen", hexc("2fb36b"), 0.5, var=0.0),
            "g_amber": S.pbr("pa_damber", hexc("f0a628"), 0.5, var=0.0),
            "g_red": S.pbr("pa_dred", hexc("dc3a32"), 0.5, var=0.0),
            # garden
            "fence": S.pbr("pa_fence", hexc("f4f2ec"), 0.6, var=0.02),
            "umb_r": S.pbr("pa_umb_r", hexc("d8323a"), 0.6, var=0.02),
            "umb_w": S.pbr("pa_umb_w", hexc("f6f2ea"), 0.6, var=0.02),
            "tramp": S.pbr("pa_tramp", hexc("1c1e22"), 0.7, var=0.0),
            "pad": S.pbr("pa_pad", hexc("2b8fd6"), 0.5, var=0.02),
            "turkey": S.pbr("pa_turkey", hexc("8a5530"), 0.45, coat=0.3, var=0.03),
            "beak": S.pbr("pa_beak", hexc("f2a01e"), 0.45, var=0.0),
            "strap": glow("pa_strap", "ffc23a", 3.0),
            "trunk": S.pbr("pa_trunk", hexc("5a4632"), 0.9, var=0.1),
        }
    return _m("mats", mk)


# ================================================================ mesh helpers
box = K.box
boxes = K.boxes
cyl = K.cyl


def ell(bm, c, r, mi=0, sub=3, rot=None):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    vs = res["verts"]
    bmesh.ops.scale(bm, vec=r, verts=vs)
    if rot is not None:
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=rot)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def torus(bm, c, R, r, mi=0, seg=40, rseg=10, sz=1.0, sy=1.0):
    vs = []
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(rseg):
            b = 2 * math.pi * j / rseg
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((c[0] + rr * math.cos(a), c[1] + sy * rr * math.sin(a), c[2] + r * math.sin(b) * sz)))
        rings.append(ring)
    for i in range(seg):
        for j in range(rseg):
            f = bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % rseg],
                              rings[i][(j + 1) % rseg]))
            f.material_index = mi
    return vs


def unit_line_mesh(name, r, mat, seg=6):
    """cylinder from (0,0,0) to (0,1,0) (STRETCH_TO stretches local Y)"""
    bm = bmesh.new()
    cyl(bm, (0, 0.5, 0), r, 1.0, 0, seg, "Y")
    return S.mesh_from_bm(name, bm, [mat], smooth=True)


def stretch_line(name, me, a, target, parent=None):
    o = S.obj(name, me, a)
    c = o.constraints.new("STRETCH_TO")
    c.target = target
    c.rest_length = 1.0
    c.volume = "NO_VOLUME"
    try:
        c.keep_axis = "SWING_Y"
    except Exception:
        pass
    o.visible_shadow = False
    return o


def seg_obj(name, a, b, r, mat, seg=6):
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = bmesh.new()
    cyl(bm, (0, 0, d.length / 2), r, d.length, 0, seg)
    o = S.obj(name, S.mesh_from_bm(name, bm, [mat], smooth=True), a)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.visible_shadow = False
    return o


def wave_mod(tl, o, height=0.22, width=1.4, speed=0.08, narrow=1.2):
    """Flutter on the GLOBAL clock: time_offset = -beat offset, so frame f of beat k = global frame."""
    md = o.modifiers.new("wave", "WAVE")
    md.use_x, md.use_y = True, False
    md.use_cyclic = True
    md.use_normal = True
    try:
        md.use_normal_x, md.use_normal_y, md.use_normal_z = False, True, False
    except Exception:
        pass
    md.height = height
    md.width = width
    md.narrowness = narrow
    md.speed = speed
    md.start_position_x = 0.0
    md.time_offset = -float(tl.off[tl.k])
    md.vertex_group = "pin"
    return md


def flag_mesh(name, w, h, mat, nx=16, nz=6):
    """vertical cloth strip in local XZ: x 0..w (x = 0 at the pole), z -h..0"""
    bm = bmesh.new()
    vs = [[bm.verts.new((w * i / nx, 0.0, -h * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    return S.mesh_from_bm(name, bm, [mat])


def add_pin_group(o, w):
    vg = o.vertex_groups.new(name="pin")
    for v in o.data.vertices:
        vg.add([v.index], min(1.0, (v.co.x / w) ** 0.8), "REPLACE")


# ================================================================ timeline (balloon state)
class State:
    def __init__(self, tl):
        c = tl.cue
        self.t_netoff = c("why_balloons", "because", 0.25)
        self.t_rise0 = c("why_balloons", "balloons", 0.3)
        self.t_rise1 = c("why_balloons", "several", 0.6) - 0.1
        self.t_gust = c("why_balloons", "wind", 0.75) - 0.15
        self.t_double = c("why_not_hold", "double", 0.68) - 0.1
        self.t_lower = c("why_not_lower", "lower", 0.15)
        self.t_city = c("why_not_lower", "city", 0.45)
        self.t_settle0 = c("what_now", "balloons", 0.35) - 0.2
        self.t_settle1 = c("what_now", "down", 0.8, nth=1) + 0.2
        self.t_netdrop0 = c("what_now", "inflated", 0.55) - 0.1
        self.t_netdrop1 = self.t_netdrop0 + 2.2
        self.t_tie = c("takeaway", "tie", 0.82) - 0.1
        self.t_wind_off = tl.bend("why_not_lower") + 0.5

    def height(self, t):
        if t < self.t_rise0:
            return H_LOW
        if t < self.t_lower:
            return H_LOW + (H_FLY - H_LOW) * smooth((t - self.t_rise0) / (self.t_rise1 - self.t_rise0))
        if t < self.t_settle0:
            return H_FLY + (H_MID - H_FLY) * smooth((t - self.t_lower) / 2.6)
        return H_MID + (H_LOW - H_MID) * smooth((t - self.t_settle0) / (self.t_settle1 - self.t_settle0))

    def squash(self, t):
        h = self.height(t)
        return SZ_LOW + (1.0 - SZ_LOW) * smooth((h - H_LOW) / 4.0)

    def lean(self, t):
        """degrees toward +X, plus wobble"""
        base = 0.0
        amp = 0.6
        if t >= self.t_gust:
            base = 13.0 * smooth((t - self.t_gust) / 1.2)
            amp = 2.2
        if t >= self.t_double:
            base = 13.0 + 10.0 * smooth((t - self.t_double) / 0.9)
            amp = 2.8
        if t >= self.t_lower:
            base = 23.0 - 11.0 * smooth((t - self.t_lower) / 2.6)
            amp = 2.0
        if t >= self.t_settle0:
            base = 12.0 * (1.0 - smooth((t - self.t_settle0) / (self.t_settle1 - self.t_settle0)))
            amp = 2.0 - 1.4 * smooth((t - self.t_settle0) / 3.0)
        return base + amp * (math.sin(1.35 * t) * 0.65 + math.sin(2.9 * t + 1.0) * 0.35)

    def handler_lean(self, t):
        h = (self.height(t) - H_LOW) / (H_FLY - H_LOW)
        return 6.0 + 10.0 * max(0.0, min(1.0, h)) + 0.5 * self.lean(t)


# ================================================================ world
def build_ground(mt):
    S.plane_obj("ground", 30000, 30000, (0, 0, -0.05), S.ground_mat())
    S.plane_obj("avenue", 24.0, 3600.0, (0.0, 1400.0, 0.02), mt["road"])
    S.plane_obj("cross", 3000.0, 20.0, (-1512.0, 150.0, 0.021), mt["road"])
    # lane dashes + double yellow centre line
    bm = bmesh.new()
    for i in range(-120, 1100):
        y = i * 3.0
        if i % 2 == 0 and not (CROSS_Y[0] - 2 < y < CROSS_Y[1] + 2):
            for x in (-6.0, 6.0):
                box(bm, (x, y, 0.035), (0.16, 1.4, 0.01))
    S.obj("dash", S.mesh_from_bm("dash", bm, [mt["line"]]))
    for dx in (-0.18, 0.18):
        S.plane_obj("yl%d" % int(dx * 100), 0.12, 3600, (dx, 1400.0, 0.034), mt["yline"])
    # sidewalks + curbs (west: x -18..-12, east: 12..19.3)
    S.plane_obj("walk_w", 6.0, 3600, (-15.0, 1400.0, 0.12), mt["pave"])
    S.plane_obj("walk_e", 7.3, 3600, (15.65, 1400.0, 0.12), mt["pave"])
    bm = bmesh.new()
    box(bm, (-12.1, 1400.0, 0.07), (0.25, 3600, 0.16))
    box(bm, (12.1, 1400.0, 0.07), (0.25, 3600, 0.16))
    S.obj("curbs", S.mesh_from_bm("curbs", bm, [mt["curb"]]))
    # crosswalk stripes at the corner
    bm = bmesh.new()
    for i in range(12):
        box(bm, (-10.5 + i * 1.9, CROSS_Y[0] - 2.2, 0.036), (0.9, 3.2, 0.01))
        box(bm, (-10.5 + i * 1.9, CROSS_Y[1] + 2.2, 0.036), (0.9, 3.2, 0.01))
    S.obj("zebra", S.mesh_from_bm("zebra", bm, [mt["line"]]))


def west_buildings(mt, rng):
    """Apartment blocks along the west side; corner towers at the cross street."""
    mk = ["b1", "b2", "b3", "b4", "brick"]
    y = -260.0
    n = 0
    while y < 1500.0:
        if CROSS_Y[0] <= y < CROSS_Y[1]:
            y = CROSS_Y[1]
            continue
        w = rng.uniform(16.0, 28.0)
        if y < CROSS_Y[0] < y + w:
            w = CROSS_Y[0] - y
        near_corner = (CROSS_Y[0] - 32 < y < CROSS_Y[0]) or (CROSS_Y[1] <= y < CROSS_Y[1] + 30)
        if near_corner:
            h = 96.0 if y > CROSS_Y[0] else 82.0
            m = "tower" if y > CROSS_Y[0] else "tower2"
        else:
            h = rng.uniform(26.0, 46.0) if y < 700 else rng.uniform(30.0, 70.0)
            m = mk[rng.randrange(len(mk))]
        d = rng.uniform(26.0, 34.0)
        cx, cy = -18.0 - d / 2, y + w / 2
        items = [((0, 0, h / 2), (d, w - 0.4, h), 0), ((0, 0, h + 0.35), (d + 0.5, w + 0.1, 0.7), 1),
                 ((d / 2 + 0.12, 0, 2.3), (0.3, w - 1.2, 4.2), 2)]
        mlist = [mt[m], mt["roof"], mt["shop"]]
        if rng.random() < 0.55 and y < 400:
            items.append(((d / 2 + 1.0, 0, 4.6), (2.0, w * 0.6, 0.18), 3))
        mlist.append(mt["awning"])
        boxes("wb%d" % n, items, mlist, loc=(cx, cy, 0.0))
        n += 1
        y += w
    # second row behind (taller), mainly a skyline for the north-west views
    for i in range(40):
        yy = -200.0 + i * 45.0 + rng.uniform(-8, 8)
        if CROSS_Y[0] - 10 < yy < CROSS_Y[1] + 10:
            continue
        h = rng.uniform(45.0, 120.0)
        w, d = rng.uniform(26, 40), rng.uniform(26, 40)
        boxes("wb2_%d" % i, [((0, 0, h / 2), (d, w, h), 0), ((0, 0, h + 0.4), (d + 0.6, w + 0.6, 0.8), 1)],
              [mt[["tower", "b3", "tower2", "b1"][i % 4]], mt["roof"]], loc=(-70.0 - d / 2, yy, 0.0))
    # cross-street buildings further west (both sides) so the squeeze reads as a canyon
    for side, yy in ((-1, CROSS_Y[0]), (1, CROSS_Y[1])):
        x = -60.0
        k = 0
        while x > -420.0:
            w = rng.uniform(22.0, 36.0)
            h = rng.uniform(45.0, 110.0)
            d = 30.0
            cy = yy + side * (d / 2)
            boxes("xb%d_%d" % (side, k), [((0, 0, h / 2), (w - 0.5, d, h), 0), ((0, 0, h + 0.4), (w, d + 0.6, 0.8), 1)],
                  [mt[["tower", "b3", "tower2", "b4"][k % 4]], mt["roof"]], loc=(x - w / 2, cy, 0.0))
            x -= w
            k += 1


def autumn_templates():
    cols = ("d9661c", "e0a023", "b83a1f", "cf8a2a", "7c8a32", "e2b43a")
    out = []
    trunk = _m("mats", mats)["trunk"]
    for i, c in enumerate(cols):
        leaf = S.pbr("pa_tree_%d" % i, hexc(c), 0.85, var=0.15, var_scale=0.9, bump=0.1)

        def build(bm, i=i):
            S.bm_box(bm, (0, 0, 1.6), (0.45, 0.45, 3.2), 0)
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            r2 = random.Random(300 + i)
            for v in res["verts"]:
                v.co *= 1.0 + r2.uniform(-0.12, 0.12)
            bmesh.ops.scale(bm, vec=(3.2, 3.2, 3.0), verts=res["verts"])
            bmesh.ops.translate(bm, vec=(0, 0, 5.6), verts=res["verts"])
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 1
            if i % 2 == 0:
                res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
                bmesh.ops.scale(bm, vec=(2.2, 2.2, 2.0), verts=res["verts"])
                bmesh.ops.translate(bm, vec=(1.4, 0.6, 7.3), verts=res["verts"])
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 1
        out.append(S._template("atree_t%d" % i, build, [trunk, leaf]))
    return out


def east_park(mt, rng):
    S.plane_obj("park_lawn", 700.0, 2200.0, (19.3 + 350.0, 1100.0, 0.0), mt["lawn"])
    # low stone wall along the park edge (gaps every 60 m)
    bm = bmesh.new()
    y = -4.0
    while y < 1500.0:
        box(bm, (19.6, y + 27.0, 0.5), (0.7, 54.0, 1.0))
        y += 60.0
    S.obj("park_wall", S.mesh_from_bm("park_wall", bm, [mt["stone"]]))
    tt = autumn_templates()
    pts = []
    for _ in range(1400):
        x, yy = rng.uniform(24.0, 420.0), rng.uniform(2.0, 1500.0)
        if x < 60 and yy < 1500:
            if rng.random() < 0.35:
                continue
        pts.append((x, yy))
    # street trees on the west sidewalk (gap around the corner and the camera paths near the balloon)
    for i in range(70):
        yy = -240.0 + i * 24.0
        if 95.0 < yy < 180.0 or -30.0 < yy < 70.0:
            continue
        pts.append((-16.2, yy + rng.uniform(-2, 2)))
    S.scatter(tt, pts, rng, (0.8, 1.25), prefix="atree")
    # flagpoles along the park wall, banners streaming east
    return len(pts)


def lamps_and_flags(tl, mt, rng):
    lamp = bmesh.new()
    cyl(lamp, (0, 0, 3.5), 0.1, 7.0, 0, 10)
    box(lamp, (0.0, 0.0, 7.0), (0.3, 0.3, 0.3), 0)
    lamp_me = S.mesh_from_bm("lamp", lamp, [mt["frame"]])
    fm = [mt["f1"], mt["f2"], mt["f3"], mt["f4"]]
    k = 0
    for y in range(-60, 420, 30):
        for x in (-13.0, 13.2):
            if CROSS_Y[0] - 4 < y < CROSS_Y[1] + 4:
                continue
            S.obj("lamp", lamp_me, (x, float(y), 0.0))
            for j in range(2):
                w = 2.4
                o = S.obj("streamer%d" % k, flag_mesh("streamer%d" % k, w, 0.28, fm[(k + j) % 4], 14, 2),
                          (x + 0.1, float(y) + (0.18 if j else -0.18), 6.7 - j * 0.5))
                add_pin_group(o, w)
                wave_mod(tl, o, height=0.18, width=0.9, speed=0.11 + 0.01 * j, narrow=1.0)
                o.rotation_euler = (0.0, math.radians(8.0 + 6 * j), 0.0)
                o.visible_shadow = False
                k += 1
    # flagpoles on the park wall
    pole = bmesh.new()
    cyl(pole, (0, 0, 4.5), 0.07, 9.0, 0, 10)
    ell(pole, (0, 0, 9.05), (0.14, 0.14, 0.14), 0, 1)
    pole_me = S.mesh_from_bm("fpole", pole, [mt["steel"]])
    i = 0
    for y in range(-2, 400, 26):
        S.obj("fpole", pole_me, (19.0, float(y), 0.0))
        w = 3.0
        o = S.obj("flag%d" % i, flag_mesh("flag%d" % i, w, 1.9, fm[i % 4], 18, 8), (19.05, float(y), 8.9))
        add_pin_group(o, w)
        wave_mod(tl, o, height=0.32, width=1.6, speed=0.12, narrow=1.0)
        o.visible_shadow = False
        i += 1
    # banners hanging from short poles on the west facades
    for j, y in enumerate((-30.0, 8.0, 52.0, 88.0, 196.0, 240.0)):
        o = S.obj("wflag%d" % j, flag_mesh("wflag%d" % j, 2.6, 1.6, fm[(j + 2) % 4], 16, 6), (-17.9, y, 9.0))
        add_pin_group(o, 2.6)
        wave_mod(tl, o, height=0.26, width=1.4, speed=0.12, narrow=1.0)
        S.obj("wfpole%d" % j, pole_me, (-17.95, y, 9.0), (0, math.radians(88.0), 0), (1, 1, 0.33))
        o.visible_shadow = False


def barriers(mt):
    bm = bmesh.new()
    box(bm, (0, 0, 0.95), (0.08, 2.3, 0.26), 0)
    box(bm, (0, 0, 0.55), (0.08, 2.3, 0.1), 0)
    for sy in (-1, 1):
        box(bm, (0, sy * 1.0, 0.5), (0.5, 0.08, 1.0), 1)
    me = S.mesh_from_bm("barrier", bm, [mt["barrier"], mt["frame"]])
    for y in range(-8, 100, 3):
        for x in (-11.3, 11.3):
            S.obj("barrier", me, (x, float(y) + 0.5, 0.0))


def leaves(tl, mt, rng):
    bm = bmesh.new()
    for tile in (0, 1):
        r2 = random.Random(77)
        for i in range(260):
            x = r2.uniform(-60.0, 60.0) - 120.0 * tile
            y = r2.uniform(-45.0, 175.0)
            z = r2.uniform(0.4, 9.0)
            s = r2.uniform(0.1, 0.17)
            mi = r2.randrange(3)
            vs = [bm.verts.new((x + s * math.cos(a), y, z + s * 0.7 * math.sin(a))) for a in (0, 2.1, 4.2)]
            f = bm.faces.new(vs)
            f.material_index = mi
            rot = Matrix.Rotation(r2.uniform(0, 6.28), 3, Vector((r2.uniform(-1, 1), r2.uniform(-1, 1), 1)).normalized())
            bmesh.ops.rotate(bm, verts=vs, cent=(x, y, z), matrix=rot)
    o = S.obj("leaves", S.mesh_from_bm("leaves", bm, [mt["leaf1"], mt["leaf2"], mt["leaf3"]]))
    o.visible_shadow = False
    v = 7.0
    P = 120.0

    def loc(t):
        s = (v * t) % P
        return (s, 0.0, -0.25 * math.sin(0.7 * t))
    Gs = tl.frames()
    set_keys(o, "location", [tl.lf(G) for G in Gs], [loc(tl.t_of_G(G)) for G in Gs], "CONSTANT")


# ================================================================ balloons
def bear_mesh(mt):
    bm = bmesh.new()
    ell(bm, (0, 0, 0), (6.0, 5.0, 6.5), 0)                      # body
    ell(bm, (0, -4.0, -0.6), (3.9, 1.3, 4.4), 1)                 # belly patch
    ell(bm, (0, 0, 9.5), (4.9, 4.6, 4.7), 0)                     # head
    for sx in (-1, 1):
        ell(bm, (sx * 3.7, 0.4, 13.3), (1.8, 1.2, 1.8), 0)       # ears
        ell(bm, (sx * 3.7, -0.5, 13.3), (1.0, 0.6, 1.0), 1)      # inner ears
        ell(bm, (sx * 6.3, -0.6, 1.4), (1.8, 1.8, 4.0), 0, 3,
            Matrix.Rotation(math.radians(-28 * sx), 3, "Y"))      # arms
        ell(bm, (sx * 2.9, -1.4, -6.0), (2.2, 2.7, 1.4), 0)      # feet
        ell(bm, (sx * 1.65, -4.15, 10.7), (0.42, 0.3, 0.66), 3)  # eyes
    ell(bm, (0, -4.0, 8.4), (2.1, 1.5, 1.6), 1)                  # muzzle
    ell(bm, (0, -5.35, 9.2), (0.62, 0.42, 0.45), 3)              # nose
    torus(bm, (0, 0, 5.3), 3.95, 0.75, 2, 48, 12, 1.0, 0.82)     # scarf
    ell(bm, (2.6, -3.9, 3.8), (0.9, 0.5, 2.0), 2, 2, Matrix.Rotation(math.radians(-15), 3, "Y"))  # scarf tail
    return S.mesh_from_bm("bear", bm, [mt["orange"], mt["cream"], mt["scarf"], mt["eye"]], smooth=True)


def star_mesh(mt):
    bm = bmesh.new()
    ell(bm, (0, 0, 0), (3.4, 2.4, 3.4), 0)
    for i in range(5):
        a = math.radians(90 + 72 * i)
        ell(bm, (4.0 * math.cos(a), 0, 4.0 * math.sin(a)), (2.4, 1.6, 1.5), 0, 3,
            Matrix.Rotation(-a, 3, "Y"))
    for sx in (-1, 1):
        ell(bm, (sx * 1.1, -2.25, 0.8), (0.35, 0.25, 0.55), 1)
    return S.mesh_from_bm("star", bm, [mt["yellow"], mt["eye"]], smooth=True)


def net_mesh(mt, cut=-0.64):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=44, v_segments=24, radius=1.0)
    kill = [v for v in bm.verts if v.co.z < cut]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    return S.mesh_from_bm("net", bm, [mt["net"]])


def add_net(name, mt, loc, scale):
    o = S.obj(name, _m("net_me", lambda: net_mesh(mt)), loc, scale=scale)
    wf = o.modifiers.new("wf", "WIREFRAME")
    wf.thickness = 0.011
    wf.use_even_offset = True
    wf.use_relative_offset = False
    wf.use_replace = True
    return o


def sandbags(name, mt, c, rx, ry, n=22):
    bm = bmesh.new()
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = c[0] + rx * math.cos(a), c[1] + ry * math.sin(a)
        ell(bm, (x, y, 0.28), (0.55, 0.32, 0.26), 0, 2, Matrix.Rotation(a, 3, "Z"))
    return S.obj(name, S.mesh_from_bm(name, bm, [mt["sand"]], smooth=True))


def handler_mesh(mt, suit):
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.62), 0.25, 1.24, 0, 12)
    ell(bm, (0, 0, 1.42), (0.19, 0.19, 0.21), 1, 2)
    cyl(bm, (0, 0.02, 1.58), 0.2, 0.08, 2, 12)
    for sx in (-1, 1):
        box(bm, (sx * 0.17, 0.28, 1.0), (0.1, 0.55, 0.1), 0)
    return S.mesh_from_bm("handler_" + suit, bm, [mt[suit], mt["skin"], mt["cap"]], smooth=False)


def build_hero(tl, st, mt, ctx):
    bx, by = BAL
    root = L.link(bpy.data.objects.new("bal_root", None))
    root.location = (bx, by, 0.0)
    body = S.obj("bear", bear_mesh(mt), (0, 0, H_LOW), parent=root)
    body.scale = (1.0, 1.0, SZ_LOW)

    def lean_rad(t):
        return math.radians(st.lean(t))
    bake(tl, root, "rotation_euler", lambda t: (0.0, lean_rad(t), 0.04 * math.sin(0.6 * t)))
    bake(tl, body, "location", lambda t: (0.0, 0.0, st.height(t)))
    bake(tl, body, "scale", lambda t: (1.0 + 0.04 * (1 - st.squash(t)), 1.0, st.squash(t)))
    # anchors for the 2D overlays
    top = L.link(bpy.data.objects.new("bal_top", None))
    top.parent, top.location = body, (0, 0, 15.1)
    bot = L.link(bpy.data.objects.new("bal_bot", None))
    bot.parent, bot.location = body, (0, -1.4, -7.4)
    mid = L.link(bpy.data.objects.new("bal_mid", None))
    mid.parent, mid.location = body, (-5.0, -2.0, 3.0)
    S.anchor(ctx, "balloon_top", top)
    S.anchor(ctx, "balloon_bottom", bot)
    S.anchor(ctx, "balloon", mid)
    # lines + handlers
    line_me = unit_line_mesh("line_me", 0.045, mt["rope"])
    hm = [handler_mesh(mt, "suit"), handler_mesh(mt, "suit2")]
    angs = [-150, -112, -74, -36, 2, 40, 78, 116, 154, 192]
    handlers = []
    for i, a in enumerate(angs):
        ar = math.radians(a)
        att = L.link(bpy.data.objects.new("att%d" % i, None))
        att.parent = body
        att.location = (5.3 * math.cos(ar), 4.4 * math.sin(ar), -2.6)
        dirv = Vector((math.cos(ar), math.sin(ar) * 0.9, 0.0)).normalized()
        g = Vector((bx, by, 1.05)) + Vector((math.cos(ar) * 13.5, math.sin(ar) * 11.5, 0.0))
        stretch_line("line%d" % i, line_me, g, att)
        last = g + dirv * 2.4
        seg_obj("line_tail%d" % i, g, Vector((last.x, last.y, 1.0)), 0.04, mt["rope"])
        yaw = math.atan2(-dirv.y, -dirv.x) - math.pi / 2
        for j in range(3):
            p = g + dirv * (0.1 + 1.15 * j) + Vector((0, 0, -1.05))
            h = S.obj("handler%d_%d" % (i, j), hm[i % 2], (p.x, p.y, 0.03), (0, 0, yaw))
            handlers.append((h, yaw, 0.37 * i + 0.9 * j))
        if i == 3:
            hk = L.link(bpy.data.objects.new("hand_anchor", None))
            hk.location = (g.x, g.y, 1.7)
            S.anchor(ctx, "handlers", hk)
    for h, yaw, ph in handlers:
        bake(tl, h, "rotation_euler",
             lambda t, yaw=yaw, ph=ph: (math.radians(st.handler_lean(t) + 1.5 * math.sin(1.7 * t + ph)), 0.0, yaw),
             step=2)
    # cargo net + sandbags (on at the start, slides off, drops back on before the end)
    net = add_net("net", mt, (bx, by, 6.8), (9.6, 7.6, 10.0))
    bags = sandbags("sandbags", mt, (bx, by), 9.6, 7.7)
    t0, t1 = st.t_netoff, st.t_netoff + 1.6
    d0 = max(st.t_netdrop0, st.t_settle1 - 1.6)
    d1 = d0 + 2.0

    def net_loc(t):
        if t < d0:
            u = smooth((t - t0) / (t1 - t0))
            return (bx + 16.0 * u, by, 6.8 + 5.0 * math.sin(math.pi * u))
        u = smooth((t - d0) / (d1 - d0))
        return (bx, by, 6.8 + 12.0 * (1 - u))

    def net_scale(t):
        if t1 + 0.05 < t < d0:
            return (0.001, 0.001, 0.001)
        if t < d0:
            u = smooth((t - t0) / (t1 - t0))
            return (9.6 * (1 - 0.6 * u), 7.6 * (1 - 0.6 * u), 10.0 * (1 - 0.9 * u))
        return (9.6, 7.6, 10.0)
    bake(tl, net, "location", net_loc)
    bake(tl, net, "scale", net_scale)
    bags.location = (0.0, 0.0, 0.0)
    set_keys(bags, "scale", [tl.lf(-10000), tl.lf(tl.G(t1 - 0.3)), tl.lf(tl.G(d1 - 0.4))], [(1, 1, 1), (0, 0, 0), (1, 1, 1)],
             "CONSTANT")
    return root, body


def build_star(mt):
    sx, sy = STAR
    S.obj("star", star_mesh(mt), (sx, sy, 5.6), (0, 0, math.radians(8)), (1.0, 1.0, 0.8))
    add_net("net2", mt, (sx, sy, 4.8), (8.8, 4.6, 8.0))
    sandbags("sandbags2", mt, (sx, sy), 8.8, 4.7, 18)


# ================================================================ wind arrows + corner ribbons
def wind_arrows(tl, st, mt):
    import scene_lib_v2_storm as ST
    specs = [((-9.0, 32.0, 9.0), 5.0), ((-10.5, 34.0, 16.0), 6.0), ((-9.0, 36.0, 23.0), 5.0)]
    for i, (p, ln) in enumerate(specs):
        a = ST.arrow("warrow%d" % i, ln, 0.75, mt["wind"], 0.0, (0, 0, 0))
        a.location = p
        base = a.location.copy()

        def loc(t, base=base, i=i):
            return (base.x + 1.2 * math.sin(1.4 * t + i), base.y, base.z + 0.3 * math.sin(0.9 * t + 2 * i))

        def sc(t, i=i):
            on = smooth((t - st.t_gust - 0.1 * i) / 0.5) * (1 - smooth((t - st.t_wind_off + 0.6) / 0.5))
            k = 1.0 + smooth((t - st.t_double - 0.1 * i) / 0.6)
            return (max(0.001, on) * k, 1.0, max(0.001, on))
        bake(tl, a, "location", loc, step=2)
        bake(tl, a, "scale", sc)


def corner_ribbons(tl, st, mt):
    on0 = st.t_city - 0.6
    off = tl.bend("where_is_the_line") + 0.3
    specs = []
    for k, (h, dy, curl) in enumerate(((6.0, -4.0, 1.0), (11.0, 2.0, 1.2), (17.0, -1.0, 0.9), (24.0, 5.0, 1.3),
                                       (9.0, 6.5, 0.8), (14.0, -6.0, 1.1), (30.0, 0.0, 1.0))):
        y0 = 150.0 + dy * 1.4
        pts = [(-170.0, y0, h + 3), (-90.0, 150.0 + dy, h + 1), (-40.0, 150.0 + dy * 0.45, h),
               (-14.0, 150.0 + dy * 0.35, h - 0.5), (-4.0, 147.0 + dy * 0.3, max(h - 1.0, 7.5)),
               (2.0 * curl, 141.0, max(h - 1.0, 8.5)), (1.0 * curl, 134.0, max(h - 0.5, 9.0)),
               (-3.0 * curl, 130.0, max(h + 1.0, 10.0))]
        cu = bpy.data.curves.new("rib%d" % k, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.26 if k % 2 == 0 else 0.18
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        try:
            cu.bevel_factor_mapping_start = "SPLINE"
            cu.bevel_factor_mapping_end = "SPLINE"
        except Exception:
            pass
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (q[0], q[1], q[2], 1.0)
        sp.use_endpoint_u = True
        sp.order_u = 4
        sp.resolution_u = 24
        o = L.link(bpy.data.objects.new("rib%d" % k, cu))
        o.data.materials.append(mt["wind"] if k % 3 else mt["wind2"])
        o.visible_shadow = False
        period, ph, ln = 2.1 + 0.25 * k, 0.37 * k, 0.32

        def fs(t, period=period, ph=ph, ln=ln):
            u = ((t + ph * period) % period) / period
            return -ln + u * (1.0 + ln)
        Gs = tl.frames()
        set_keys(cu, "bevel_factor_start", [tl.lf(G) for G in Gs],
                 [(max(0.0, min(1.0, fs(tl.t_of_G(G)))),) for G in Gs], "CONSTANT")
        set_keys(cu, "bevel_factor_end", [tl.lf(G) for G in Gs],
                 [(max(0.0, min(1.0, fs(tl.t_of_G(G)) + ln)),) for G in Gs], "CONSTANT")
        show_between(tl, o, on0, off)
        specs.append(o)
    return specs


# ================================================================ weather mast + dial
def mph_ang(m):
    return math.radians(-120.0 + 4.0 * m)


def build_mast(tl, st, mt, ctx):
    mx, my = MAST
    bm = bmesh.new()
    cyl(bm, (0, 0, 4.6), 0.09, 9.2, 0, 12)
    box(bm, (0, 0, 0.1), (0.6, 0.6, 0.2), 0)
    box(bm, (0, -0.18, DIAL_Z), (0.25, 0.3, 0.25), 0)
    S.obj("mast", S.mesh_from_bm("mast", bm, [mt["frame"]]), (mx, my, 0.0))
    # anemometer
    hub = L.link(bpy.data.objects.new("anemo", None))
    hub.location = (mx, my, 9.35)
    bm = bmesh.new()
    cyl(bm, (0, 0, 0), 0.07, 0.2, 0, 10)
    for i in range(3):
        a = 2 * math.pi * i / 3
        box(bm, (0.32 * math.cos(a), 0.32 * math.sin(a), 0), (0.64, 0.035, 0.035), 0)
        ell(bm, (0.66 * math.cos(a), 0.66 * math.sin(a), 0), (0.14, 0.14, 0.12), 1, 2)
    cups = S.obj("cups", S.mesh_from_bm("cups", bm, [mt["steel"], mt["white"]]), (0, 0, 0), parent=hub)

    def spin(t):
        # revolutions grow with the gusts: integrate a piecewise rate (rev/s)
        r0 = 1.2
        r1 = 2.6
        ta = st.t_city
        if t < ta:
            ang = r0 * t
        else:
            ang = r0 * ta + r1 * (t - ta)
        return (0.0, 0.0, 2 * math.pi * ang)
    bake(tl, hub, "rotation_euler", spin)
    # wind vane (points downwind +X)
    bm = bmesh.new()
    box(bm, (0.2, 0, 0), (1.2, 0.04, 0.04), 0)
    box(bm, (0.75, 0, 0.0), (0.4, 0.02, 0.35), 0)
    cyl(bm, (-0.42, 0, 0), 0.06, 0.18, 1, 8, "X")
    S.obj("vane", S.mesh_from_bm("vane", bm, [mt["steel"], mt["g_red"]]), (mx, my, 8.75))
    # dial (faces -Y): coloured zones, white face, ticks, needle
    cx, cz = mx, DIAL_Z
    bm = bmesh.new()

    def wedge(a0, a1, r0, r1, mi, n=24):
        for i in range(n):
            u0 = a0 + (a1 - a0) * i / n
            u1 = a0 + (a1 - a0) * (i + 1) / n
            v = [bm.verts.new((r * math.sin(u), 0.02, r * math.cos(u))) for r, u in ((r0, u0), (r1, u0), (r1, u1), (r0, u1))]
            f = bm.faces.new(v)
            f.material_index = mi
    disc = [bm.verts.new((0.98 * math.sin(2 * math.pi * i / 64), 0.04, 0.98 * math.cos(2 * math.pi * i / 64)))
            for i in range(64)]
    f = bm.faces.new(disc)
    f.material_index = 4
    face = [bm.verts.new((0.92 * math.sin(2 * math.pi * i / 64), 0.03, 0.92 * math.cos(2 * math.pi * i / 64)))
            for i in range(64)]
    f = bm.faces.new(face)
    f.material_index = 0
    a23, a34, amax = mph_ang(23), mph_ang(34), mph_ang(60)
    wedge(mph_ang(0), a23, 0.62, 0.88, 1)
    wedge(a23, a34, 0.62, 0.88, 2)
    wedge(a34, amax, 0.62, 0.88, 3)
    for a in (a23, a34):
        vs = box(bm, (0.78 * math.sin(a), 0.01, 0.78 * math.cos(a)), (0.05, 0.02, 0.36), 4)
        bmesh.ops.rotate(bm, verts=vs, cent=(0.78 * math.sin(a), 0.01, 0.78 * math.cos(a)),
                         matrix=Matrix.Rotation(a, 3, "Y"))
    dial = S.obj("dial", S.mesh_from_bm("dial", bm, [mt["white"], mt["g_green"], mt["g_amber"], mt["g_red"],
                                                     mt["dark"]]), (cx, DIAL_Y - 0.05, cz))
    for p in dial.data.polygons:
        p.use_smooth = False
    piv = L.link(bpy.data.objects.new("needle_piv", None))
    piv.location = (cx, DIAL_Y - 0.1, cz)
    bm = bmesh.new()
    box(bm, (0, 0, 0.33), (0.06, 0.02, 0.72), 0)
    cyl(bm, (0, 0, 0), 0.08, 0.04, 0, 16, "Y")
    S.obj("needle", S.mesh_from_bm("needle", bm, [mt["dark"]]), (0, 0, 0), parent=piv)
    t23 = tl.cue("where_is_the_line", "twenty", 0.4)
    t34 = tl.cue("where_is_the_line", "thirty", 0.55)
    tb = tl.cue("where_is_the_line", "forecast", 0.85)

    def needle(t):
        m = 14.0 + 3.0 * smooth((t - st.t_city) / 2.0)
        m += 6.0 * smooth((t - t23) / 0.8)              # 23
        m += 11.0 * smooth((t - t34) / 0.8)             # 34
        m += 18.0 * smooth((t - tb) / 1.2)              # ~52, well beyond
        m += 0.8 * math.sin(3.1 * t) + 0.5 * math.sin(7.3 * t)
        return (0.0, mph_ang(m), 0.0)
    bake(tl, piv, "rotation_euler", needle)
    for name, a in (("tick23", a23), ("tick34", a34)):
        e = L.link(bpy.data.objects.new(name, None))
        e.location = (cx + 0.97 * math.sin(a), DIAL_Y - 0.1, cz + 0.97 * math.cos(a))
        S.anchor(ctx, name, e)


# ================================================================ garden (takeaway)
def build_garden(tl, st, mt, ctx):
    x0, x1, y0, y1 = GARDEN
    S.plane_obj("garden_lawn", x1 - x0 + 10.0, y1 - y0, ((x0 + x1 + 10.0) / 2, (y0 + y1) / 2, 0.06), mt["lawn"])
    # house (facade faces the avenue, -X)
    boxes("house", [((0, 0, 5.0), (12.0, 22.0, 10.0), 0), ((0, 0, 10.3), (12.6, 22.6, 0.6), 1),
                    ((-6.05, 0, 1.4), (0.2, 2.0, 2.8), 2), ((-6.4, 0, 0.3), (1.6, 3.0, 0.6), 3)],
          [mt["brick"], mt["roof"], mt["awning"], mt["stone"]], loc=(x1 + 6.0, (y0 + y1) / 2, 0.0))
    # white picket fence along the sidewalk (gap = gate)
    bm = bmesh.new()
    y = y0
    while y < y1:
        if not (-25.5 < y < -22.5):
            box(bm, (x0 + 0.2, y, 0.55), (0.06, 0.09, 1.1), 0)
        y += 0.3
    for z in (0.35, 0.85):
        box(bm, (x0 + 0.24, (y0 - 25.5) / 2, z), (0.04, -25.5 - y0, 0.07), 0)
        box(bm, (x0 + 0.24, (y1 - 22.5) / 2, z), (0.04, y1 + 22.5, 0.07), 0)
    S.obj("fence", S.mesh_from_bm("fence", bm, [mt["fence"]]))
    t_tie = st.t_tie

    def damp(t):
        return 1.0 - 0.88 * smooth((t - t_tie) / 0.6)
    # patio umbrella
    ux, uy = 27.5, -25.5
    ur = L.link(bpy.data.objects.new("umb_root", None))
    ur.location = (ux, uy, 0.0)
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.08), 0.45, 0.16, 2, 16)
    cyl(bm, (0, 0, 1.25), 0.035, 2.5, 2, 8)
    n = 12
    apex = bm.verts.new((0, 0, 2.75))
    rim = [bm.verts.new((1.6 * math.cos(2 * math.pi * i / n), 1.6 * math.sin(2 * math.pi * i / n), 2.22)) for i in range(n)]
    for i in range(n):
        f = bm.faces.new((apex, rim[i], rim[(i + 1) % n]))
        f.material_index = i % 2
    S.obj("umbrella", S.mesh_from_bm("umbrella", bm, [mt["umb_r"], mt["umb_w"], mt["steel"]]), (0, 0, 0), parent=ur)
    bake(tl, ur, "rotation_euler",
         lambda t: (math.radians(3.0 * math.sin(2.3 * t) * damp(t)),
                    math.radians((7.0 + 5.0 * math.sin(1.9 * t)) * damp(t)), 0.0))
    ua = L.link(bpy.data.objects.new("umb_anchor", None))
    ua.parent, ua.location = ur, (0, 0, 2.6)
    S.anchor(ctx, "umbrella", ua)
    # trampoline
    tx, ty = 31.0, -19.0
    tr = L.link(bpy.data.objects.new("tramp_root", None))
    tr.location = (tx, ty, 0.0)
    bm = bmesh.new()
    disc = [bm.verts.new((1.7 * math.cos(2 * math.pi * i / 40), 1.7 * math.sin(2 * math.pi * i / 40), 0.86))
            for i in range(40)]
    f = bm.faces.new(disc)
    f.material_index = 0
    torus(bm, (0, 0, 0.88), 1.85, 0.16, 1, 40, 8, 0.6)
    for i in range(6):
        a = 2 * math.pi * i / 6
        cyl(bm, (1.85 * math.cos(a), 1.85 * math.sin(a), 0.43), 0.04, 0.86, 2, 8)
    S.obj("tramp", S.mesh_from_bm("tramp", bm, [mt["tramp"], mt["pad"], mt["steel"]], smooth=False), (0, 0, 0),
          parent=tr)
    bake(tl, tr, "rotation_euler",
         lambda t: (math.radians(2.0 * math.sin(2.7 * t + 1) * damp(t)),
                    math.radians((2.5 + 2.5 * math.sin(2.1 * t + 0.5)) * damp(t)), 0.0))
    bake(tl, tr, "location", lambda t: (tx, ty, 0.12 * max(0.0, math.sin(2.1 * t + 0.5)) * damp(t)))
    ta = L.link(bpy.data.objects.new("tramp_anchor", None))
    ta.parent, ta.location = tr, (-1.0, 0, 1.0)
    S.anchor(ctx, "trampoline", ta)
    # small inflatable turkey (generic), faces the avenue (south-west)
    kx, ky = 24.5, -19.5
    kr = L.link(bpy.data.objects.new("turkey_root", None))
    kr.location = (kx, ky, 0.0)
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.04), 0.6, 0.08, 4, 16)
    ell(bm, (0, 0, 0.95), (0.72, 0.62, 0.8), 0)
    tail = [1, 2, 3, 2, 1]
    for i in range(5):
        a = math.radians(-60 + 30 * i)
        ell(bm, (0.95 * math.sin(a), 0.45, 1.15 + 0.85 * math.cos(a)), (0.3, 0.12, 0.72), tail[i] + 0, 2,
            Matrix.Rotation(a, 3, "Y"))
    ell(bm, (0, -0.55, 1.72), (0.3, 0.3, 0.32), 0)
    ell(bm, (0, -0.86, 1.72), (0.09, 0.14, 0.07), 2, 2)
    ell(bm, (0.06, -0.86, 1.55), (0.06, 0.06, 0.12), 3, 2)
    for sx in (-1, 1):
        ell(bm, (sx * 0.13, -0.78, 1.82), (0.05, 0.03, 0.06), 5, 1)
    tk = S.obj("turkey", S.mesh_from_bm("turkey", bm, [mt["turkey"], mt["f1"], mt["beak"], mt["scarf"],
                                                       mt["frame"], mt["eye"]], smooth=True), (0, 0, 0), parent=kr)
    tk.rotation_euler = (0, 0, math.radians(-40.0))
    bake(tl, kr, "rotation_euler",
         lambda t: (math.radians(5.0 * math.sin(2.4 * t) * damp(t)),
                    math.radians((9.0 + 7.0 * math.sin(1.7 * t + 2.0)) * damp(t)), 0.0))
    ka = L.link(bpy.data.objects.new("turkey_anchor", None))
    ka.parent, ka.location = kr, (0, 0, 2.0)
    S.anchor(ctx, "turkey", ka)
    # tie-down straps (glowing), appear on "tie" (rest pose)
    straps = []
    for i in range(3):
        a = math.radians(30 + 120 * i)
        straps.append(((ux + 0.6 * math.cos(a) * 0.1, uy, 1.4), (ux + 1.7 * math.cos(a), uy + 1.7 * math.sin(a), 0.07)))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        straps.append(((tx + 1.85 * math.cos(a), ty + 1.85 * math.sin(a), 0.88),
                       (tx + 2.6 * math.cos(a), ty + 2.6 * math.sin(a), 0.07)))
    for sx in (-1, 1):
        straps.append(((kx + 0.55 * sx, ky, 1.0), (kx + 1.4 * sx, ky - 0.4, 0.07)))
    for i, (a, b) in enumerate(straps):
        o = seg_obj("strap%d" % i, a, b, 0.035, mt["strap"])
        show_between(tl, o, t_tie + 0.05 * i)


# ================================================================ camera route
def route(tl, st):
    bx, by = BAL
    t_q = tl.bstart("question")
    t_b = tl.bstart("why_balloons")
    t_bw = st.t_gust - 0.05
    t_h = tl.bstart("why_not_hold")
    t_m = tl.cue("why_not_hold", "math", 0.6)
    t_c = st.t_city + 0.1
    t_w = tl.bstart("where_is_the_line")
    t_lim = tl.cue("where_is_the_line", "limits", 0.35)
    t_n = tl.bstart("what_now")
    t_off = tl.cue("what_now", "inflated", 0.6) - 0.2
    t_k = tl.bstart("takeaway")
    t_o = tl.bstart("outro")
    T = tl.T
    t_back0 = tl.cue("outro", "because", 0.55) - 0.5
    t_back1 = T - 0.35
    F1 = ((-3.0, -7.0, 5.2), (0.0, 42.0, 9.8), 22.0)     # the frame-1 view (loop target)

    def lin(a, b, ease=False):
        def f(t, u):
            w = smooth(u) if ease else u
            return (Vector(a[0]).lerp(Vector(b[0]), w), Vector(a[1]).lerp(Vector(b[1]), w), a[2] + (b[2] - a[2]) * w)
        return f

    def hold_tilt(t, u):
        loc = Vector((16.5, 20.0, 3.0)).lerp(Vector((16.8, 18.5, 3.2)), u)
        tgt = Vector((2.0, 40.0, 15.0)).lerp(Vector((3.0, 33.0, 4.0)), smooth((u - 0.1) / 0.6))
        return loc, tgt, 22.0

    def outro(t, u):
        a = (Vector((-1.0, 9.0, 3.6)), Vector((0.0, 42.0, 9.4)), 24.0)
        a2 = (Vector((-1.5, 6.0, 3.8)), Vector((0.0, 42.0, 9.5)), 24.0)
        if t < t_back0:
            w = (t - (t_o + 0.45)) / max(0.1, t_back0 - t_o - 0.45)
            w = max(0.0, min(1.0, w))
            return a[0].lerp(a2[0], w), a[1].lerp(a2[1], w), 24.0
        w = smoother((t - t_back0) / (t_back1 - t_back0))
        return (a2[0].lerp(Vector(F1[0]), w), a2[1].lerp(Vector(F1[1]), w), 24.0 + (F1[2] - 24.0) * w)

    spots = [
        (0.0, 0.0, lin(F1, ((-2.2, -1.0, 5.0), (0.0, 42.0, 9.5), 23.0)), []),
        (t_q, 0.6, lin(((0.8, 1.0, 4.4), (0.0, 42.0, 8.4), 24.0), ((0.6, 8.0, 4.2), (0.0, 42.0, 8.6), 25.0)), []),
        (t_b, 0.75, lin(((6.0, -14.0, 3.5), (-1.0, 42.0, 17.0), 20.0), ((5.0, -9.0, 3.5), (-1.0, 42.0, 22.0), 20.0),
                        True), [(3.0, 0.0, 4.0)]),
        (t_bw, 0.8, lin(((-3.0, 3.0, 4.0), (2.5, 42.0, 17.5), 20.0), ((-3.0, 6.0, 4.0), (3.0, 42.0, 18.0), 20.0)),
         []),
        (t_h, 0.7, hold_tilt, []),
        (t_m, 0.8, lin(((-15.0, 5.0, 7.2), (3.5, 42.0, 15.0), 21.0), ((-13.0, 8.5, 7.0), (3.0, 42.0, 13.0), 21.0)),
         [(-5.0, 12.0, 5.0)]),
        (t_c, 1.3, lin(((8.5, 146.0, 4.5), (-60.0, 151.0, 14.0), 22.0), ((8.0, 143.5, 4.8), (-60.0, 151.0, 14.5), 22.0)),
         [(-4.0, 12.0, 5.0), (11.0, 26.0, 3.6), (11.0, 62.0, 3.8), (9.5, 110.0, 4.6)]),
        (t_w, 0.9, lin(((-3.5, 117.0, 3.6), (-15.8, 135.0, 6.2), 24.0), ((-5.5, 120.0, 3.7), (-15.8, 135.0, 6.0), 24.0)),
         []),
        (t_lim, 1.0, lin(((-11.8, 125.0, 4.1), (MAST[0], DIAL_Y, DIAL_Z + 0.15), 26.0),
                         ((-12.3, 126.0, 4.1), (MAST[0], DIAL_Y, DIAL_Z + 0.15), 26.0)), []),
        (t_n, 1.3, lin(((4.0, -2.0, 4.8), (0.0, 42.0, 11.0), 22.0), ((3.2, 2.0, 4.6), (0.0, 42.0, 10.5), 22.0)),
         [(-4.0, 110.0, 6.0), (11.0, 70.0, 4.0), (11.0, 30.0, 3.6)]),
        (t_off, 0.8, lin(((-16.0, 12.0, 3.4), (0.0, 41.0, 8.0), 22.0), ((-15.0, 14.0, 3.3), (0.0, 41.0, 7.5), 22.0)),
         []),
        (t_k, 0.9, lin(((15.5, -38.0, 3.2), (26.5, -22.4, 1.0), 24.0), ((15.9, -35.5, 3.1), (26.8, -21.4, 1.0), 24.0)),
         [(4.0, 4.0, 4.0)]),
        (t_o, 0.9, outro, [(8.0, -6.0, 3.6)]),
    ]
    return spots


# ================================================================ BUILDER
def b_parade_oneshot(ctx, p):
    tl = TL(ctx)
    tl.ctx = ctx
    st = State(tl)
    sc = ctx.scene
    rng = random.Random(p.get("seed", 27))
    S.daylight(ctx, p.get("sun_az", -30.0), 40.0)
    L.fog(0.00045, S.HAZE, start=180.0)
    C.horizon_haze(sc, lo=-0.01, hi=0.06)
    mt = mats()
    build_ground(mt)
    west_buildings(mt, rng)
    n_trees = east_park(mt, rng)
    lamps_and_flags(tl, mt, rng)
    barriers(mt)
    leaves(tl, mt, rng)
    build_hero(tl, st, mt, ctx)
    build_star(mt)
    wind_arrows(tl, st, mt)
    corner_ribbons(tl, st, mt)
    build_mast(tl, st, mt, ctx)
    build_garden(tl, st, mt, ctx)
    S.build_city(rng, region=(-1600, 1600, 1700, 3600))
    S.build_hills(rng)
    spots = route(tl, st)
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=24)
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000.0
    T_end = tl.T + 1.0
    bake(tl, cam, "location", lambda t: camera_at(spots, t, T_end)[0])
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 parade] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 parade] beat %d (%s): global frames %d-%d, %d trees" % (
        tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1, tl.off[tl.k] + tl.n[tl.k], n_trees))


S.V2_BUILDERS.update({"parade_oneshot": b_parade_oneshot})

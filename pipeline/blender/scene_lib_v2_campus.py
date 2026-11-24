"""v2 one-shot campus builder ("Nvidia CEO" bonus reel, 24 Nov 2026 #10). Registers into scene_lib_v2.V2_BUILDERS.

ONE builder (`campus_oneshot`) is used by every beat. Every beat builds the identical bright tech-campus world and
keys ALL animation (camera + props) on the GLOBAL episode timeline, read from WORKDIR/audio/timings.json and
WORKDIR/captions.json. Each beat job then just renders its own slice of that timeline, so the finished video is one
continuous camera move through one world: slow drifts at each spot, fast eased "whip" moves (EEVEE motion blur)
between spots. Global frame G of local frame f in beat k: G = off_k + f, off_k = sum of earlier beats' frame counts
(the same round(duration * fps) the renderer and overlay use). Word cues: G = 1 + t * fps.

World (north = +Y, the sun is in the south so most cameras look north / sideways):
  plaza (paving) with steps up to a glass HQ; empty podium (no logo) on the landing with a spot fixture + light pool;
  a giant BLANK display wall on the HQ facade; a balance scale (plain gold blocks) and a big gauge (no numbers) on the
  plaza; a road west out of the campus with glowing milestone posts and a 3D line chart (solid past, dotted future);
  an east wing whose ground floor is open: a bright corner office (empty chair, low fog) and a glass boardroom (empty
  chairs, a light at each seat); a lake with a toy-like cargo ship (empty bridge + wheel, fog that lifts); campus
  buildings, trees, far city and hills. No people, no logos, no 3D text (all text = 2D overlays).
"""
import json
import math
import os
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc
import scene_lib_v2_city as C
import scene_lib_v2_market as M
from scene_lib_v2_winter import set_keys

# ---------------------------------------------------------------- layout
PODIUM = (0.0, 34.5)
LAND_Z = 1.2                    # HQ landing height (podium stands on it)
HQ = (-45.0, 45.0, 40.0, 76.0)  # x0, x1, y0, y1
SCALE = (-24.0, 16.0)
GAUGE = (24.0, 17.0)
WING = (55.0, 100.0, 10.0, 50.0)
OFFICE_X = (55.0, 71.5)
BOARD_X = (71.5, 100.0)
ROOM_Y = (10.0, 27.0)
CEIL = 3.6
CHAIR = (63.0, 21.0)
TABLE = (86.0, 18.5)
LAKE = (88.0, -72.0, 78.0, 40.0)  # centre x, y, radius x, radius y
SHIP_Y = -76.0
SHIP_X0, SHIP_V = 40.0, 2.2      # ship x at t = 0 (global seconds) and speed (m/s): x(t) = X0 + V * (t - T_ship0)
ROAD_Y = 0.0

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def smoother(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


# ================================================================ global timeline
class TL:
    """Global timeline: beat frame offsets + every spoken word (absolute seconds)."""

    def __init__(self, ctx):
        wd = os.path.dirname(S.TEX["dir"].rstrip("/"))
        tm = json.load(open(os.path.join(wd, "audio", "timings.json")))["beats"]
        cp = os.path.join(wd, "captions.json")
        self.words = json.load(open(cp))["words"] if os.path.exists(cp) else []
        self.fps = ctx.fps
        self.beats = tm
        self.n = [int(round(b["duration"] * ctx.fps)) for b in tm]
        self.off = [sum(self.n[:i]) for i in range(len(tm))]
        self.k = min(range(len(tm)), key=lambda i: abs(tm[i]["start"] - ctx.beat_start))
        self.total = sum(self.n)
        self.T = self.total / float(self.fps)

    def lf(self, G):
        """local frame of global frame G (float ok)"""
        return G - self.off[self.k]

    def G(self, t):
        return 1.0 + t * self.fps

    def t_of_G(self, G):
        return (G - 1.0) / self.fps

    def bstart(self, bid):
        for i, b in enumerate(self.beats):
            if b["id"] == bid:
                return self.off[i] / float(self.fps)
        raise KeyError(bid)

    def bend(self, bid):
        for i, b in enumerate(self.beats):
            if b["id"] == bid:
                return (self.off[i] + self.n[i]) / float(self.fps)
        raise KeyError(bid)

    def cue(self, bid, word, frac=0.5, nth=0):
        """Global seconds at which `word` (prefix) is spoken in beat `bid`; fallback = frac of the beat."""
        w = word.lower()
        hits = [x for x in self.words if x.get("beat") == bid and x["norm"].startswith(w)]
        if len(hits) > nth:
            return hits[nth]["start"]
        a, b = self.bstart(bid), self.bend(bid)
        return a + frac * (b - a)

    def frames(self, pad=3):
        """global frames this beat needs keys for (plus a few beyond each end for motion blur)"""
        a = self.off[self.k] + 1 - pad
        b = self.off[self.k] + self.n[self.k] + pad
        return list(range(a, b + 1))


def bake(tl, o, path, fn, interp="LINEAR", step=1):
    """Key o.path = fn(global_seconds) on every frame of this beat (+ pad)."""
    Gs = tl.frames()[::step]
    if Gs[-1] != tl.frames()[-1]:
        Gs.append(tl.frames()[-1])
    vals = []
    for G in Gs:
        v = fn(tl.t_of_G(G))
        vals.append(tuple(v) if hasattr(v, "__len__") else (v,))
    set_keys(o, path, [tl.lf(G) for G in Gs], vals, interp)


def show_between(tl, o, t_on=None, t_off=None):
    """Hard show/hide by scale (CONSTANT keys) at global seconds."""
    s = tuple(o.scale)
    z = (0.0, 0.0, 0.0)
    frames, vals = [tl.lf(-10000)], [z if t_on is not None else s]
    if t_on is not None:
        frames.append(tl.lf(tl.G(t_on)))
        vals.append(s)
    if t_off is not None:
        frames.append(tl.lf(tl.G(t_off)))
        vals.append(z)
    set_keys(o, "scale", frames, vals, "CONSTANT")


# ================================================================ materials
def glow(name, col, strength=3.0):
    return S.emis(name, hexc(col) if isinstance(col, str) else col, strength)


def fog_mat(name="soft_fog", alpha=0.32):
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    m.surface_render_method = "BLENDED"
    p.inputs["Base Color"].default_value = hexc("f4f6f8")
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Alpha"].default_value = alpha
    try:
        p.inputs["Emission Color"].default_value = hexc("ffffff")
        p.inputs["Emission Strength"].default_value = 0.25
    except Exception:
        pass
    m.node_tree.links.new(p.outputs[0], m.node_tree.nodes.get("Material Output").inputs["Surface"])
    S._MV2[name] = m
    return m


def screen_mat():
    """The giant blank display wall: soft light-blue gradient, no glyphs."""
    name = "cp_screen"
    if name in S._MV2:
        return S._MV2[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexc("12345f")
    ramp.color_ramp.elements[1].color = hexc("3f8fd0")
    Lk.new(sep.outputs["Z"], ramp.inputs[0])
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.6
    br.inputs["Row Height"].default_value = 1.6
    br.inputs["Mortar Size"].default_value = 0.035
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (1.35, 1.45, 1.6, 1)
    Lk.new(tc.outputs["Object"], br.inputs["Vector"])
    mul = N.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    Lk.new(ramp.outputs["Color"], mul.inputs["A"])
    Lk.new(br.outputs["Color"], mul.inputs["B"])
    em = N.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.2
    Lk.new(mul.outputs["Result"], em.inputs["Color"])
    Lk.new(em.outputs[0], N.get("Material Output").inputs["Surface"])
    S._MV2[name] = m
    return m


def ceil_mat():
    name = "cp_ceil"
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc("f4f4f2")
    p.inputs["Roughness"].default_value = 0.9
    p.inputs["Emission Color"].default_value = hexc("f6f3ee")
    p.inputs["Emission Strength"].default_value = 0.55
    S._MV2[name] = S._finish(m, p.outputs[0], haze=False)
    return m


def mats():
    def mk():
        return {
            "pave": M.paving_mat(),
            "stone": S.pbr("cp_stone", hexc("d9d3c8"), 0.6, var=0.05, var_scale=0.5, bump=0.05),
            "white": S.pbr("cp_white", hexc("f1f2f3"), 0.45, var=0.03),
            "navy": S.pbr("cp_navy", hexc("1b2c4f"), 0.4, var=0.03),
            "steel": S.pbr("cp_steel", hexc("aeb4bb"), 0.3, metal=0.9, var=0.02),
            "dark": S.pbr("cp_dark", hexc("2b2f35"), 0.45, var=0.03),
            "gold": S.pbr("cp_gold", hexc("e5b53e"), 0.22, metal=1.0, var=0.04),
            "wood": S.pbr("cp_wood", hexc("b48b5e"), 0.5, var=0.12, var_scale=3.0, bump=0.04),
            "floor": S.pbr("cp_floor", hexc("c9b79c"), 0.4, var=0.06, var_scale=1.2),
            "wall": S.pbr("cp_wall", hexc("f3f1ec"), 0.8, var=0.03),
            "ceil": ceil_mat(),
            "chair": S.pbr("cp_chair", hexc("2e3440"), 0.55, var=0.03),
            "fabric": S.pbr("cp_fabric", hexc("44536b"), 0.85, var=0.05, var_scale=4.0),
            "plant": S.pbr("cp_plant", hexc("4c7a36"), 0.8, var=0.12, bump=0.1),
            "pot": S.pbr("cp_pot", hexc("d7cfc4"), 0.7, var=0.04),
            "glass": M.clear_glass_mat("cp_glass", hexc("cfe3f0"), 0.16),
            "panel": glow("cp_ceil_panel", "fff6e8", 2.2),
            "hq": S.facade_mat("cp_hq_facade", hexc("e3e7ec"), hexc("42617f"), 1.7, 4.2, 0.86),
            "wing": S.facade_mat("cp_wing_facade", hexc("efe9df"), hexc("3f5b75"), 1.6, 3.6, 0.8),
            "bld1": S.facade_mat("cp_bld1", hexc("d8dde3"), hexc("3a5670"), 2.0, 3.8, 0.75),
            "bld2": S.facade_mat("cp_bld2", hexc("e8e0d2"), hexc("33495e"), 3.0, 3.8, 0.6),
            "roof": S.pbr("cp_roof", hexc("8d9096"), 0.8, var=0.08),
            "frame": S.pbr("cp_frame", hexc("5d646d"), 0.35, metal=0.6, var=0.02),
            "teal": glow("cp_teal", "2ee6c8", 4.0),
            "teal_dim": S.pbr("cp_teal_dim", hexc("3b6f6a"), 0.4, var=0.0),
            "warm": glow("cp_warm", "fff1d6", 6.0),
            "seat_on": glow("cp_seat_on", "ffffff", 7.0),
            "red": S.pbr("cp_red", hexc("c83a34"), 0.45, var=0.04),
            "amber": S.pbr("cp_amber", hexc("e9a23b"), 0.45, var=0.04),
            "green": S.pbr("cp_green", hexc("2fa98d"), 0.45, var=0.04),
            "hull": S.pbr("cp_hull", hexc("c9413a"), 0.35, coat=0.4, var=0.03),
            "hull_w": S.pbr("cp_hull_w", hexc("f4f4f2"), 0.35, coat=0.4, var=0.02),
            "deck": S.pbr("cp_deck", hexc("6d8a6a"), 0.7, var=0.05),
            "water": C.water_mat(),
            "road": C.asphalt_mat("cp_road", hexc("4d5056")),
            "line": S.pbr("cp_line", hexc("f2f2ee"), 0.6, var=0.0),
            "lawn": S.lawn_mat("cp_lawn", hexc("6f9147"), stripes=True),
            "bank": S.pbr("cp_bank", hexc("b9ad96"), 0.85, var=0.1, var_scale=0.3, bump=0.06),
        }
    return _m("mats", mk)


# ================================================================ mesh helpers
def box(bm, c, s, mi=0):
    return S.bm_box(bm, c, s, mi)


def boxes(name, items, mlist, loc=(0, 0, 0), parent=None, smooth=False):
    """items: [(centre, size, mat_index)] -> one object"""
    bm = bmesh.new()
    for c, s, mi in items:
        box(bm, c, s, mi)
    return S.obj(name, S.mesh_from_bm(name, bm, mlist, smooth), loc, parent=parent)


def cyl(bm, c, r, h, mi=0, seg=24, axis="Z"):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    vs = res["verts"]
    if axis == "X":
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def ellipse_disc(name, cx, cy, rx, ry, z, mat, seg=96):
    bm = bmesh.new()
    vs = [bm.verts.new((cx + rx * math.cos(2 * math.pi * i / seg), cy + ry * math.sin(2 * math.pi * i / seg), z))
          for i in range(seg)]
    bm.faces.new(vs)
    return S.obj(name, S.mesh_from_bm(name, bm, [mat]))


def ellipse_ring(name, cx, cy, rx, ry, w, z, mat, seg=96):
    bm = bmesh.new()
    a = [bm.verts.new((cx + rx * math.cos(2 * math.pi * i / seg), cy + ry * math.sin(2 * math.pi * i / seg), z))
         for i in range(seg)]
    b = [bm.verts.new((cx + (rx + w) * math.cos(2 * math.pi * i / seg), cy + (ry + w) * math.sin(2 * math.pi * i / seg),
                       z)) for i in range(seg)]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return S.obj(name, S.mesh_from_bm(name, bm, [mat]))


def puff_mesh(name, seed):
    bm = bmesh.new()
    r = random.Random(seed)
    for k in range(4):
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        sc = (r.uniform(0.8, 1.4), r.uniform(0.8, 1.4), r.uniform(0.45, 0.7))
        bmesh.ops.scale(bm, vec=sc, verts=res["verts"])
        bmesh.ops.translate(bm, vec=(r.uniform(-1.0, 1.0), r.uniform(-1.0, 1.0), r.uniform(-0.1, 0.25)),
                            verts=res["verts"])
    return S.mesh_from_bm(name, bm, [fog_mat()], smooth=True)


# ================================================================ world
def build_ground(mt, rng):
    S.plane_obj("ground", 30000, 30000, (0, 0, -0.05), S.ground_mat())
    S.plane_obj("campus_lawn", 520, 360, (30.0, -10.0, -0.02), mt["lawn"])
    # plaza paving + walkway to the wing
    S.plane_obj("plaza", 100, 60, (0.0, 0.0, 0.02), mt["pave"])
    S.plane_obj("walk_e", 60, 14, (78.0, 2.0, 0.021), mt["pave"])
    S.plane_obj("walk_lake", 14, 30, (82.0, -16.0, 0.022), mt["pave"])
    # road west out of the campus with a dashed centre line
    S.plane_obj("road_w", 3000, 12, (-1550.0, ROAD_Y, 0.03), mt["road"])
    bm = bmesh.new()
    for i in range(0, 1450, 1):
        x = -56.0 - i * 2.0
        if i % 2 == 0:
            box(bm, (x, ROAD_Y, 0.045), (1.2, 0.18, 0.01))
    S.obj("road_dash", S.mesh_from_bm("road_dash", bm, [mt["line"]]))
    for sy in (-1, 1):
        S.plane_obj("road_edge%d" % sy, 3000, 0.18, (-1550.0, ROAD_Y + sy * 5.4, 0.045), mt["line"])
    # perimeter road north of the HQ
    S.plane_obj("road_n", 3000, 10, (0.0, 120.0, 0.03), mt["road"])


def build_hq(mt):
    x0, x1, y0, y1 = HQ
    items = [((0.0, (y0 + y1) / 2, 15.0), (x1 - x0, y1 - y0, 30.0), 0),
             ((0.0, (y0 + y1) / 2, 30.4), (x1 - x0 + 0.8, y1 - y0 + 0.8, 0.8), 1),
             ((0.0, (y0 + y1) / 2, 31.8), (30.0, 16.0, 2.4), 1)]
    boxes("hq", items, [mt["hq"], mt["roof"]])
    # landing + steps (stone) and a slim canopy
    st = [((0.0, 36.0, LAND_Z / 2), (40.0, 8.0, LAND_Z), 0)]
    for i in range(4):
        h = LAND_Z * (i + 1) / 4.0
        st.append(((0.0, 31.0 - (3 - i) * 0.9 + 0.45, h / 2), (40.0, 0.9 + 0.01, h), 0))
    boxes("hq_steps", st, [mt["stone"]])
    boxes("hq_canopy", [((0.0, 37.5, 6.2), (34.0, 5.0, 0.35), 0),
                        ((-16.5, 35.4, 3.7), (0.25, 0.25, 5.0), 1), ((16.5, 35.4, 3.7), (0.25, 0.25, 5.0), 1)],
          [mt["white"], mt["steel"]])
    # giant blank display wall on the facade above the canopy (frame + emissive face, no glyphs)
    boxes("screen_frame", [((0.0, y0 - 0.3, 16.5), (25.0, 0.6, 14.0), 0)], [mt["dark"]])
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((-11.8, y0 - 0.62, 10.2), (11.8, y0 - 0.62, 10.2), (11.8, y0 - 0.62, 22.8),
                                    (-11.8, y0 - 0.62, 22.8))]
    bm.faces.new(vs)
    S.obj("screen_face", S.mesh_from_bm("screen_face", bm, [screen_mat()]))
    # entrance: glass doors in front of a lit lobby
    boxes("hq_lobby", [((0.0, y0 + 0.4, LAND_Z + 1.8), (12.0, 0.1, 3.6), 0)], [S.emis("cp_lobby", hexc("e9e2d4"), 1.1)])
    boxes("hq_doors", [((x, y0 - 0.05, LAND_Z + 1.8), (0.12, 0.14, 3.6), 0) for x in (-6, -3, 0, 3, 6)] +
          [((0.0, y0 - 0.05, LAND_Z + 3.65), (12.2, 0.16, 0.14), 0)], [mt["frame"]])


def build_podium(ctx, mt):
    px, py = PODIUM
    bm = bmesh.new()
    # lectern: slightly tapered body, slanted top, navy front panel (blank)
    body = box(bm, (0, 0, 0.55), (0.78, 0.5, 1.1), 0)
    for v in body:
        if v.co.z > 0.6:
            v.co.x *= 1.12
    top = box(bm, (0, 0.03, 1.15), (0.92, 0.62, 0.08), 0)
    for v in top:
        v.co.z += (v.co.y - 0.03) * 0.25
    box(bm, (0, -0.255, 0.62), (0.62, 0.02, 0.8), 1)
    box(bm, (0, 0, 0.03), (0.95, 0.65, 0.06), 2)
    pod = S.obj("podium", S.mesh_from_bm("podium", bm, [mt["white"], mt["navy"], mt["steel"]]),
                (px, py, LAND_Z), (0, 0, 0))
    # warm light pool on the landing + a floor spot fixture aimed at the podium
    bm = bmesh.new()
    box(bm, (0, 0, 0.3), (0.12, 0.12, 0.6), 0)
    cyl(bm, (0, 0, 0.8), 0.2, 0.45, 0, 20, "Y")
    cyl(bm, (0, -0.24, 0.8), 0.16, 0.04, 1, 20, "Y")
    sp = S.obj("spot_fixture", S.mesh_from_bm("spot_fixture", bm, [mt["dark"], mt["warm"]]),
               (px + 3.2, py - 3.4, LAND_Z), (0, 0, math.radians(-40)))
    ld = bpy.data.lights.new("podium_spot", "SPOT")
    ld.energy = 2500.0
    ld.color = (1.0, 0.93, 0.8)
    ld.spot_size = math.radians(28)
    ld.spot_blend = 0.4
    lo = L.link(bpy.data.objects.new("podium_spot", ld))
    lo.location = (px + 2.5, py - 5.0, LAND_Z + 7.0)
    d = Vector((px, py, LAND_Z + 1.0)) - lo.location
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # closed folder (appears on the "investigation" cue)
    bm = bmesh.new()
    box(bm, (0, 0, 0.012), (0.36, 0.27, 0.024), 0)
    box(bm, (0.004, 0.0, 0.012), (0.34, 0.25, 0.016), 1)
    fold = S.obj("folder", S.mesh_from_bm("folder", bm, [mt["navy"], mt["white"]]),
                 (px, py + 0.05, LAND_Z + 1.2), (math.radians(14), 0, math.radians(8)))
    return pod, fold


def build_scale(tl, mt, t_on, t_full):
    """Balance scale: right pan sinks as plain gold blocks stack on it between t_on and t_full (global s)."""
    sx, sy = SCALE
    H, ARM = 8.0, 5.2
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.3), 2.2, 0.6, 0, 40)
    cyl(bm, (0, 0, H / 2 + 0.3), 0.35, H, 1, 24)
    cyl(bm, (0, 0, H + 0.4), 0.55, 0.5, 1, 24, "Y")
    S.obj("scale_base", S.mesh_from_bm("scale_base", bm, [mt["stone"], mt["gold"]], smooth=False), (sx, sy, 0.0))
    piv = L.link(bpy.data.objects.new("scale_pivot", None))
    piv.location = (sx, sy, H + 0.4)
    bm = bmesh.new()
    box(bm, (0, 0, 0), (2 * ARM + 0.6, 0.35, 0.35), 0)
    cyl(bm, (-ARM, 0, 0), 0.25, 0.5, 0, 16, "Y")
    cyl(bm, (ARM, 0, 0), 0.25, 0.5, 0, 16, "Y")
    S.obj("scale_beam", S.mesh_from_bm("scale_beam", bm, [mt["gold"]]), (0, 0, 0), parent=piv)
    n_blocks = 12
    max_tilt = math.radians(13.0)

    def tilt(t):
        return max_tilt * smooth((t - t_on) / max(0.1, t_full - t_on))

    bake(tl, piv, "rotation_euler", lambda t: (0.0, tilt(t), 0.0))   # +Y rotation lowers the +X end
    pans = []
    for side in (-1, 1):
        bm = bmesh.new()
        cyl(bm, (0, 0, -3.6), 1.9, 0.18, 0, 40)
        for a in range(3):
            ang = a * 2 * math.pi / 3
            p0 = Vector((1.75 * math.cos(ang), 1.75 * math.sin(ang), -3.55))
            mid = p0 / 2
            mid.z = -1.8
            ln = (Vector((0, 0, 0)) - p0).length
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.04, radius2=0.04, depth=ln)
            q = (Vector((0, 0, 0)) - p0).to_track_quat("Z", "Y")
            bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=q.to_matrix())
            bmesh.ops.translate(bm, vec=mid, verts=res["verts"])
        pan = S.obj("pan%d" % side, S.mesh_from_bm("pan%d" % side, bm, [mt["gold"]]))
        pans.append(pan)

        def pos(t, side=side):
            a = tilt(t)
            return (sx + side * ARM * math.cos(a), sy, H + 0.4 - side * ARM * math.sin(a))
        bake(tl, pan, "location", pos)
    # gold blocks on the right pan (+X), appearing one by one
    right = pans[1]
    k = 0
    for layer in range(3):
        for (bx, by) in ((-0.55, -0.4), (0.55, -0.4), (-0.55, 0.4), (0.55, 0.4)):
            if k >= n_blocks:
                break
            bm = bmesh.new()
            blk = box(bm, (0, 0, 0.22), (1.0, 0.7, 0.44), 0)
            for v in blk:
                if v.co.z > 0.3:
                    v.co.x *= 0.85
                    v.co.y *= 0.82
            o = S.obj("gold%d" % k, S.mesh_from_bm("gold%d" % k, bm, [mt["gold"]]),
                      (bx * (0.92 if layer == 1 else 1.0), by, -3.51 + layer * 0.45), (0, 0, 0.12 * ((k % 3) - 1)),
                      parent=right)
            show_between(tl, o, t_on + (t_full - t_on) * k / float(n_blocks))
            k += 1


def build_gauge(tl, mt, t0, t_swing, t_end):
    """Big semicircle gauge facing south (red -> amber -> teal arc, no numbers); needle swings, then settles."""
    gx, gy = GAUGE
    R, Z = 4.2, 5.4
    bm = bmesh.new()
    box(bm, (0, 0.3, 2.6), (1.0, 0.8, 5.2), 0)            # stand
    box(bm, (0, 0.55, Z - 0.1), (2 * R + 1.4, 0.45, 0.5), 1)
    S.obj("gauge_stand", S.mesh_from_bm("gauge_stand", bm, [mt["stone"], mt["white"]]), (gx, gy, 0.0))
    # backplate: half disc
    bm = bmesh.new()
    seg = 48
    c = bm.verts.new((0, 0.3, Z))
    rim = [bm.verts.new(((R + 0.7) * math.cos(math.pi * i / seg), 0.3, Z + (R + 0.7) * math.sin(math.pi * i / seg)))
           for i in range(seg + 1)]
    for i in range(seg):
        bm.faces.new((c, rim[i], rim[i + 1]))
    S.obj("gauge_back", S.mesh_from_bm("gauge_back", bm, [mt["white"]]), (gx, gy, 0.0))
    # coloured arc bands (3 colours), slightly in front of the plate
    for name, a0, a1, mat in (("teal", 0, 60, "green"), ("amber", 60, 120, "amber"), ("red", 120, 180, "red")):
        bm = bmesh.new()
        n = 16
        inner, outer = [], []
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            inner.append(bm.verts.new(((R - 0.8) * math.cos(a), 0.0, Z + (R - 0.8) * math.sin(a))))
            outer.append(bm.verts.new((R * math.cos(a), 0.0, Z + R * math.sin(a))))
        for i in range(n):
            bm.faces.new((inner[i], outer[i], outer[i + 1], inner[i + 1]))
        res = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        bmesh.ops.translate(bm, vec=(0, 0.2, 0), verts=[e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)])
        S.obj("gauge_%s" % name, S.mesh_from_bm("gauge_" + name, bm, [mt[mat]]), (gx, gy - 0.1, 0.0))
    # tick marks (no numbers)
    bm = bmesh.new()
    for i in range(13):
        a = math.pi * i / 12.0
        p = Vector(((R + 0.25) * math.cos(a), -0.12, Z + (R + 0.25) * math.sin(a)))
        v = box(bm, (0, 0, 0), (0.09, 0.05, 0.42), 0)
        bmesh.ops.rotate(bm, verts=v, cent=(0, 0, 0),
                         matrix=Matrix.Rotation(a - math.pi / 2, 3, "Y").inverted())
        bmesh.ops.translate(bm, vec=p, verts=v)
    S.obj("gauge_ticks", S.mesh_from_bm("gauge_ticks", bm, [mt["dark"]]), (gx, gy, 0.0))
    # needle on a hub
    hub = L.link(bpy.data.objects.new("gauge_hub", None))
    hub.location = (gx, gy - 0.45, Z)
    bm = bmesh.new()
    v = box(bm, (0, 0, (R - 0.5) / 2), (0.22, 0.12, R - 0.5), 0)
    for vv in v:
        if vv.co.z > 1.0:
            vv.co.x *= 0.35
    cyl(bm, (0, 0, 0), 0.45, 0.3, 1, 24, "Y")
    S.obj("gauge_needle", S.mesh_from_bm("gauge_needle", bm, [mt["navy"], mt["dark"]]), (0, 0, 0), parent=hub)

    def ang(t):
        # rotation about -Y; 0 = straight up. swing in from the left, damped wobble, settle a little right of centre
        if t < t0:
            return math.radians(-35.0)
        u = t - t0
        base = math.radians(8.0)
        a = base + math.radians(-43.0) * math.exp(-0.55 * u) * math.cos(2.4 * u)
        if t > t_swing:
            w = t - t_swing
            a += math.radians(32.0) * math.sin(2.6 * w) * math.exp(-0.7 * w)
        return a

    bake(tl, hub, "rotation_euler", lambda t: (0.0, ang(t), 0.0))


def build_road_props(tl, mt, t_cue, t_slide0, t_slide1, t_expect, t_change):
    """Glowing milestone posts along the road west; a 3D line chart (solid past, dotted future) above the road."""
    rng = random.Random(5)
    post_mesh = None
    bm = bmesh.new()
    box(bm, (0, 0, 0.9), (0.32, 0.32, 1.8), 0)
    box(bm, (0, 0, 1.95), (0.36, 0.36, 0.3), 1)
    post_mesh = S.mesh_from_bm("post", bm, [mt["white"], mt["teal"]])
    for i in range(36):
        base_x = -62.0 - i * 26.0
        for sy in (-1, 1):
            o = S.obj("post%d_%d" % (i, sy), post_mesh, (base_x, ROAD_Y + sy * 7.2, 0.0))
            if i >= 7:      # posts far ahead slide nearer / farther during the beat (the path ahead shifts)
                amp = 6.0 + 0.4 * (i - 7)
                ph = rng.uniform(0, 0.6)

                def fx(t, bx=base_x, amp=amp, ph=ph, sy=sy):
                    u = smooth((t - t_slide0) / max(0.1, t_slide1 - t_slide0))
                    return (bx + amp * math.sin(2 * math.pi * (1.5 * u + ph)) * min(1.0, 4 * u * (1 - u) * 1.6),
                            ROAD_Y + sy * 7.2, 0.0)
                bake(tl, o, "location", fx, step=2)
    # line chart in the vertical plane y = CH_Y beside the road
    CH_Y = 8.0
    xs = [-112.0 - 4.0 * i for i in range(46)]                    # x from -112 to -292
    rs = random.Random(11)
    z = 3.2
    zs = []
    for i, x in enumerate(xs):
        z += 0.3 + rs.uniform(-0.8, 0.8) * (0.9 if i < 24 else 0.5)
        zs.append(z)
    n_past = 24
    tube_r = 0.42
    # past: solid glowing segments drawn in order from t_cue
    for i in range(n_past - 1):
        a, b = Vector((xs[i], CH_Y, zs[i])), Vector((xs[i + 1], CH_Y, zs[i + 1]))
        seg = _segment("chart_s%d" % i, a, b, tube_r, mt["teal"])
        show_between(tl, seg, t_cue + 0.07 * i)
    # future: dotted segments; on the "change" cue they re-route to a different future
    alt = []
    za = zs[n_past - 1]
    rs2 = random.Random(23)
    for i in range(n_past - 1, len(xs)):
        alt.append(za)
        za += 0.2 + rs2.uniform(-1.3, 0.7)
    for j, i in enumerate(range(n_past - 1, len(xs) - 1)):
        a0, b0 = Vector((xs[i], CH_Y, zs[i])), Vector((xs[i + 1], CH_Y, zs[i + 1]))
        a1, b1 = Vector((xs[i], CH_Y, alt[j])), Vector((xs[i + 1], CH_Y, alt[j + 1] if j + 1 < len(alt) else alt[j]))
        bm = bmesh.new()
        cyl(bm, (0, 0, 0), tube_r * 0.85, 1.9, 0, 10, "X")
        dash = S.obj("chart_f%d" % j, S.mesh_from_bm("chart_f%d" % j, bm, [glow("cp_future", "bff7ef", 3.0)]))

        def pose(t, a0=a0, b0=b0, a1=a1, b1=b1):
            u = smoother((t - t_change) / 0.9)
            a = a0.lerp(a1, u)
            b = b0.lerp(b1, u)
            return (a + b) / 2

        def rot(t, a0=a0, b0=b0, a1=a1, b1=b1):
            u = smoother((t - t_change) / 0.9)
            d = b0.lerp(b1, u) - a0.lerp(a1, u)
            return (0.0, -math.atan2(d.z, -d.x), math.pi)
        bake(tl, dash, "location", pose, step=2)
        bake(tl, dash, "rotation_euler", rot, step=2)
        show_between(tl, dash, t_expect + 0.08 * j)
    # a "now" marker where past meets future
    bm = bmesh.new()
    res = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
    now = S.obj("chart_now", S.mesh_from_bm("chart_now", bm, [glow("cp_now", "ffffff", 5.0)], smooth=True),
                (xs[n_past - 1], CH_Y, zs[n_past - 1]))
    show_between(tl, now, t_cue + 0.07 * (n_past - 1))
    # chart backing: faint grid of thin posts holding the chart (so it reads as a sculpture, not floating text)
    bm = bmesh.new()
    for x in (-112.0, -202.0, -292.0):
        box(bm, (x, CH_Y + 0.6, 4.0), (0.3, 0.3, 8.0), 0)
    S.obj("chart_masts", S.mesh_from_bm("chart_masts", bm, [mt["steel"]]))


def _segment(name, a, b, r, mat):
    d = b - a
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r, depth=d.length + r)
    q = d.to_track_quat("Z", "Y")
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=q.to_matrix())
    bmesh.ops.translate(bm, vec=(a + b) / 2, verts=res["verts"])
    return S.obj(name, S.mesh_from_bm(name, bm, [mat], smooth=True))


def build_wing(tl, mt, t_seat0, t_seat1):
    """East wing: upper floors = facade box; ground floor open (office + glass boardroom)."""
    x0, x1, y0, y1 = WING
    boxes("wing_upper", [(((x0 + x1) / 2, (y0 + y1) / 2, CEIL + 7.0), (x1 - x0, y1 - y0, 14.0), 0),
                         (((x0 + x1) / 2, (y0 + y1) / 2, CEIL + 14.3), (x1 - x0 + 0.6, y1 - y0 + 0.6, 0.6), 1)],
          [mt["wing"], mt["roof"]])
    # ground floor slab / floor / ceiling
    boxes("wing_floor", [(((x0 + x1) / 2, (y0 + y1) / 2, 0.05), (x1 - x0, y1 - y0, 0.1), 0)], [mt["floor"]])
    ceil = boxes("wing_ceil", [(((x0 + x1) / 2, (y0 + y1) / 2, CEIL - 0.05), (x1 - x0, y1 - y0, 0.1), 0)],
                 [mt["ceil"]])
    # ceiling light panels
    bm = bmesh.new()
    for x in range(int(x0) + 3, int(x1) - 1, 4):
        for y in range(int(ROOM_Y[0]) + 3, int(ROOM_Y[1]), 4):
            box(bm, (x, y, CEIL - 0.11), (1.2, 1.2, 0.02), 0)
    S.obj("ceil_panels", S.mesh_from_bm("ceil_panels", bm, [mt["panel"]]))
    # back wall of the rooms (north) + the rest of the ground floor behind it (solid)
    boxes("wing_back", [(((x0 + x1) / 2, ROOM_Y[1] + 0.1, CEIL / 2), (x1 - x0, 0.2, CEIL), 0),
                        (((x0 + x1) / 2, (ROOM_Y[1] + y1) / 2, CEIL / 2), (x1 - x0, y1 - ROOM_Y[1], CEIL), 1)],
          [mt["wall"], mt["wing"]])
    boxes("wing_east", [((x1 - 0.1, (ROOM_Y[0] + ROOM_Y[1]) / 2, CEIL / 2), (0.2, ROOM_Y[1] - ROOM_Y[0], CEIL), 0)],
          [mt["wall"]])
    # curtain walls: south (y = 10) and west (x = 55): mullions + glass panes, with door gaps for the camera
    gaps_s = [(66.2, 69.8), (79.6, 83.6)]
    bm = bmesh.new()
    bmg = bmesh.new()
    x = x0
    while x < x1 - 0.01:
        xm = x + 1.6
        inside_gap = any(g0 - 0.01 <= x and xm <= g1 + 0.01 for g0, g1 in gaps_s)
        box(bm, (x, y0, CEIL / 2), (0.12, 0.16, CEIL), 0)
        if not any(g0 < (x + xm) / 2 < g1 for g0, g1 in gaps_s):
            box(bmg, ((x + xm) / 2, y0, CEIL / 2), (1.6, 0.03, CEIL), 0)
        x = xm
    box(bm, ((x0 + x1) / 2, y0, CEIL - 0.15), (x1 - x0, 0.2, 0.3), 0)    # head rail
    for g0, g1 in gaps_s:    # door frames
        box(bm, (g0, y0, CEIL / 2), (0.16, 0.2, CEIL), 0)
        box(bm, (g1, y0, CEIL / 2), (0.16, 0.2, CEIL), 0)
    y = ROOM_Y[0]
    while y < ROOM_Y[1] - 0.01:
        ym = y + 1.7
        box(bm, (x0, y, CEIL / 2), (0.16, 0.12, CEIL), 0)
        box(bmg, (x0, (y + ym) / 2, CEIL / 2), (0.03, 1.7, CEIL), 0)
        y = ym
    S.obj("wing_mullions", S.mesh_from_bm("wing_mullions", bm, [mt["frame"]]))
    S.obj("wing_glass", S.mesh_from_bm("wing_glass", bmg, [mt["glass"]]))
    # glass partition office | boardroom at x = 71.5 with a door gap y 12.2..15.4
    bm = bmesh.new()
    bmg = bmesh.new()
    px = OFFICE_X[1]
    y = ROOM_Y[0]
    while y < ROOM_Y[1] - 0.01:
        ym = min(ROOM_Y[1], y + 1.6)
        box(bm, (px, y, CEIL / 2), (0.1, 0.1, CEIL), 0)
        if not (12.0 <= (y + ym) / 2 <= 15.6):
            box(bmg, (px, (y + ym) / 2, CEIL / 2), (0.03, ym - y, CEIL), 0)
        y = ym
    box(bm, (px, (ROOM_Y[0] + ROOM_Y[1]) / 2, CEIL - 0.12), (0.12, ROOM_Y[1] - ROOM_Y[0], 0.24), 0)
    S.obj("part_mullions", S.mesh_from_bm("part_mullions", bm, [mt["frame"]]))
    S.obj("part_glass", S.mesh_from_bm("part_glass", bmg, [mt["glass"]]))
    # interior lights (keep the rooms bright)
    for (lx, ly, en) in ((62.0, 18.0, 900.0), (80.0, 18.0, 900.0), (92.0, 18.0, 900.0)):
        ld = bpy.data.lights.new("room_light", "AREA")
        ld.energy = en
        ld.size = 6.0
        ld.color = (1.0, 0.97, 0.92)
        lo = L.link(bpy.data.objects.new("room_light", ld))
        lo.location = (lx, ly, CEIL - 0.2)
    # ---- office: desk, empty executive chair, shelf, plants, a blank art panel
    ox = CHAIR[0]
    boxes("desk", [((ox, 19.6, 0.74), (2.4, 1.0, 0.06), 0), ((ox - 1.1, 19.6, 0.37), (0.08, 0.9, 0.74), 1),
                   ((ox + 1.1, 19.6, 0.37), (0.08, 0.9, 0.74), 1), ((ox, 20.05, 0.45), (2.2, 0.04, 0.5), 0),
                   ((ox + 0.5, 19.5, 0.79), (0.5, 0.35, 0.03), 2)], [mt["wood"], mt["steel"], mt["dark"]])
    chair = _exec_chair("exec_chair", mt, (CHAIR[0], CHAIR[1], 0.0), math.pi)
    anc = L.link(bpy.data.objects.new("anc_chair", None))
    anc.location = (CHAIR[0], CHAIR[1] + 0.25, 1.35)
    S.anchor(tl.ctx, "chair", anc)
    boxes("shelf", [((56.0, 21.0, 1.1), (0.4, 4.0, 2.2), 0)], [mt["wood"]])
    boxes("art", [((ox, ROOM_Y[1] - 0.02, 1.9), (2.6, 0.04, 1.4), 0)], [S.pbr("cp_art", hexc("8fb3c9"), 0.7, var=0.15,
                                                                                var_scale=2.0)])
    for (x, y) in ((57.0, 12.0), (69.8, 25.6)):
        _plant("plant", mt, (x, y))
    # low fog drifting over the office floor
    fog_mat("office_fog", 0.16)
    for i in range(7):
        r = random.Random(40 + i)
        me = puff_mesh("ofog%d" % i, 40 + i)
        me.materials[0] = fog_mat("office_fog", 0.16)
        pf = S.obj("ofog%d" % i, me, (0, 0, 0), scale=(0.9, 0.9, 0.28))
        pf.visible_shadow = False
        y = r.uniform(16.0, 25.5)
        x0f = r.uniform(55.5, 71.0)
        sp = r.uniform(0.25, 0.45) * (1 if i % 2 else -1)

        def fpos(t, x0f=x0f, y=y, sp=sp):
            x = 55.5 + ((x0f - 55.5 + sp * t) % 15.5)
            return (x, y, 0.18)
        bake(tl, pf, "location", fpos, step=3)
    # ---- boardroom: long table, ring of empty chairs, a small light at each seat
    tx, ty = TABLE
    boxes("table", [((tx, ty, 0.76), (11.0, 2.6, 0.08), 0), ((tx - 3.5, ty, 0.37), (0.6, 1.2, 0.74), 1),
                    ((tx + 3.5, ty, 0.37), (0.6, 1.2, 0.74), 1)], [mt["white"], mt["steel"]])
    boxes("board_screen", [((tx, ROOM_Y[1] - 0.05, 1.8), (5.0, 0.08, 2.4), 0)], [mt["dark"]])
    seats = []
    for i in range(5):
        x = tx - 4.4 + 2.2 * i
        seats.append(((x, ty - 2.05), 0.0, (x, ty - 0.95)))
    for i in range(5):
        x = tx + 4.4 - 2.2 * i
        seats.append(((x, ty + 2.05), math.pi, (x, ty + 0.95)))
    seats.insert(5, ((tx + 6.6, ty), math.pi / 2, (tx + 5.2, ty)))
    seats.append(((tx - 6.6, ty), -math.pi / 2, (tx - 5.2, ty)))
    for i, ((cx, cy), rz, (lx, ly)) in enumerate(seats):
        _office_chair("bchair%d" % i, mt, (cx, cy, 0.0), rz)
        bm = bmesh.new()
        cyl(bm, (0, 0, 0), 0.16, 0.03, 0, 20)
        S.obj("seat_off%d" % i, S.mesh_from_bm("seat_off%d" % i, bm, [mt["teal_dim"]]), (lx, ly, 0.815))
        bm = bmesh.new()
        cyl(bm, (0, 0, 0), 0.17, 0.035, 0, 20)
        on = S.obj("seat_on%d" % i, S.mesh_from_bm("seat_on%d" % i, bm, [mt["seat_on"]]), (lx, ly, 0.818))
        show_between(tl, on, t_seat0 + (t_seat1 - t_seat0) * i / float(len(seats) - 1))
    for (x, y) in ((73.0, 25.4), (98.6, 11.5), (98.6, 25.4)):
        _plant("plant", mt, (x, y))


def _exec_chair(name, mt, loc, rz):
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.06), 0.36, 0.06, 1, 5)
    cyl(bm, (0, 0, 0.28), 0.04, 0.4, 1, 10)
    box(bm, (0, 0, 0.5), (0.62, 0.6, 0.12), 0)
    box(bm, (0, -0.3, 0.95), (0.6, 0.12, 0.85), 0)
    box(bm, (0, -0.33, 1.42), (0.5, 0.12, 0.2), 0)
    box(bm, (-0.34, 0.0, 0.7), (0.06, 0.45, 0.05), 1)
    box(bm, (0.34, 0.0, 0.7), (0.06, 0.45, 0.05), 1)
    return S.obj(name, S.mesh_from_bm(name, bm, [mt["chair"], mt["steel"]]), loc, (0, 0, rz))


def _office_chair(name, mt, loc, rz):
    me = _m("office_chair_mesh", lambda: _office_chair_mesh(mt))
    return S.obj(name, me, loc, (0, 0, rz))


def _office_chair_mesh(mt):
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.05), 0.3, 0.05, 1, 5)
    cyl(bm, (0, 0, 0.25), 0.035, 0.38, 1, 8)
    box(bm, (0, 0, 0.47), (0.52, 0.5, 0.09), 0)
    box(bm, (0, -0.25, 0.82), (0.5, 0.07, 0.6), 0)
    return S.mesh_from_bm("office_chair", bm, [mt["fabric"], mt["steel"]])


def _plant(name, mt, xy):
    me = _m("plant_mesh", lambda: _plant_mesh(mt))
    return S.obj(name, me, (xy[0], xy[1], 0.0))


def _plant_mesh(mt):
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.3), 0.3, 0.6, 1, 16)
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.55)
    bmesh.ops.scale(bm, vec=(1.0, 1.0, 1.4), verts=res["verts"])
    bmesh.ops.translate(bm, vec=(0, 0, 1.25), verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = 0
    return S.mesh_from_bm("plant", bm, [mt["plant"], mt["pot"]], smooth=True)


SHIP_T = {"t0": 0.0}


def ship_x(t):
    """the ship glides east through the metaphor beat; clamped so it always stays on the lake"""
    return 72.0 + 1.6 * max(-26.0, min(26.0, t - SHIP_T["t0"]))


def build_lake_ship(tl, mt, t_wheel0, t_steady, t_lift):
    cx, cy, rx, ry = LAKE
    ellipse_disc("lake", cx, cy, rx, ry, 0.0, mt["water"], 128)
    ellipse_ring("lake_bank", cx, cy, rx - 0.5, ry - 0.5, 3.0, 0.035, mt["bank"], 128)
    # lake bed (dark) slightly below so the lawn does not show through the water at grazing angles
    # ship: toy-like cargo ship, bow +X, bridge at the stern
    root = L.link(bpy.data.objects.new("ship", None))
    bake(tl, root, "location", lambda t: (ship_x(t), SHIP_Y, 0.0), step=2)
    bm = bmesh.new()
    LEN, BEAM = 30.0, 7.0
    prof = []
    for i in range(25):
        u = i / 24.0
        x = -LEN / 2 + LEN * u
        w = BEAM / 2 * (1.0 if u < 0.7 else math.sqrt(max(0.02, 1 - ((u - 0.7) / 0.3) ** 2)))
        prof.append((x, w))
    for zlo, zhi, mi in ((-1.2, 1.6, 0), (1.6, 3.0, 1)):
        top = [bm.verts.new((x, w, zhi)) for x, w in prof] + [bm.verts.new((x, -w, zhi)) for x, w in reversed(prof)]
        bot = [bm.verts.new((x, w * 0.9, zlo)) for x, w in prof] + \
              [bm.verts.new((x, -w * 0.9, zlo)) for x, w in reversed(prof)]
        n = len(top)
        f1 = bm.faces.new(top)
        f2 = bm.faces.new(list(reversed(bot)))
        f1.material_index = f2.material_index = 2
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
            f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    S.obj("hull", S.mesh_from_bm("hull", bm, [mt["hull"], mt["hull_w"], mt["deck"]]), (0, 0, 0), parent=root)
    # containers (plain colours, no markings) on the foredeck
    cols = [S.pbr("cp_c%d" % i, hexc(c), 0.6, var=0.05) for i, c in
            enumerate(("2f6fb5", "e0a032", "2fa98d", "c8463c", "f2f2ee", "4b5d7a"))]
    rr = random.Random(3)
    bm = bmesh.new()
    for ix in range(4):
        for iy in range(2):
            for iz in range(2 if ix < 3 else 1):
                box(bm, (-1.0 + ix * 3.3, -1.45 + iy * 2.9, 3.0 + 1.25 + iz * 2.5), (3.1, 2.7, 2.45),
                    rr.randrange(len(cols)))
    S.obj("containers", S.mesh_from_bm("containers", bm, cols), (0, 0, 0), parent=root)
    # superstructure at the stern: accommodation block + bridge deck (open front so the wheel is visible)
    BX = -10.5      # bridge centre x (ship local)
    items = [((BX, 0.0, 4.9), (5.0, 6.2, 3.8), 0),           # accommodation block
             ((BX, 0.0, 7.0), (5.6, 7.2, 0.25), 1),         # bridge floor
             ((BX, 0.0, 9.95), (6.0, 7.6, 0.3), 0),         # bridge roof
             ((BX - 2.7, 0.0, 8.45), (0.2, 7.0, 2.8), 0),   # back wall
             ((BX + 2.75, 0.0, 7.45), (0.15, 7.0, 0.7), 0),  # front sill (window opening above)
             ((BX, 3.5, 8.45), (5.6, 0.2, 2.8), 0), ((BX, -3.5, 8.45), (5.6, 0.2, 2.8), 0),
             ((BX + 2.75, 3.3, 8.85), (0.15, 0.3, 2.0), 1), ((BX + 2.75, -3.3, 8.85), (0.15, 0.3, 2.0), 1),
             ((BX + 2.75, 0.0, 8.85), (0.15, 0.2, 2.0), 1),
             ((BX + 1.6, 0.0, 7.6), (0.9, 3.2, 0.9), 2),     # console
             ((BX - 1.5, 0.0, 11.5), (1.4, 1.4, 3.0), 3),    # funnel
             ((BX - 1.5, 0.0, 12.4), (1.45, 1.45, 0.5), 4)]
    # windows band on the accommodation block
    for sy in (-1, 1):
        for k in range(3):
            items.append(((BX - 1.4 + k * 1.4, sy * 3.12, 5.4), (0.9, 0.05, 0.7), 2))
    boxes("bridge", items, [mt["hull_w"], mt["frame"], mt["dark"], mt["navy"], mt["red"]], parent=root)
    ld = bpy.data.lights.new("bridge_light", "AREA")
    ld.energy = 260.0
    ld.size = 3.0
    lo = L.link(bpy.data.objects.new("bridge_light", ld))
    lo.parent = root
    lo.location = (BX, 0.0, 9.6)
    # the wheel (spoked) on a pedestal, turning back and forth, then steadying
    boxes("wheel_ped", [((BX + 0.4, 0.0, 7.6), (0.35, 0.35, 0.9), 0)], [mt["frame"]], parent=root)
    hub = L.link(bpy.data.objects.new("wheel_hub", None))
    hub.parent = root
    hub.location = (BX + 0.62, 0.0, 8.35)
    bm = bmesh.new()
    for i in range(32):
        a0, a1 = 2 * math.pi * i / 32, 2 * math.pi * (i + 1) / 32
        p0 = Vector((0, 0.55 * math.cos(a0), 0.55 * math.sin(a0)))
        p1 = Vector((0, 0.55 * math.cos(a1), 0.55 * math.sin(a1)))
        d = p1 - p0
        r2 = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.045, radius2=0.045, depth=d.length * 1.15)
        bmesh.ops.rotate(bm, verts=r2["verts"], cent=(0, 0, 0), matrix=d.to_track_quat("Z", "Y").to_matrix())
        bmesh.ops.translate(bm, vec=(p0 + p1) / 2, verts=r2["verts"])
    for k in range(8):
        a = 2 * math.pi * k / 8
        d = Vector((0, math.cos(a), math.sin(a)))
        r2 = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.03, radius2=0.03, depth=0.78)
        bmesh.ops.rotate(bm, verts=r2["verts"], cent=(0, 0, 0), matrix=d.to_track_quat("Z", "Y").to_matrix())
        bmesh.ops.translate(bm, vec=d * 0.39, verts=r2["verts"])
        r3 = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.035, radius2=0.02, depth=0.22)
        bmesh.ops.rotate(bm, verts=r3["verts"], cent=(0, 0, 0), matrix=d.to_track_quat("Z", "Y").to_matrix())
        bmesh.ops.translate(bm, vec=d * 0.66, verts=r3["verts"])
    cyl(bm, (0, 0, 0), 0.1, 0.16, 0, 12, "X")
    S.obj("wheel", S.mesh_from_bm("wheel", bm, [S.pbr("cp_wheelwood", hexc("8a5a32"), 0.45, var=0.05)], smooth=True),
          (0, 0, 0), parent=hub)

    def wheel(t):
        if t < t_wheel0:
            return (0.0, 0.0, 0.0)
        u = t - t_wheel0
        amp = math.radians(70.0) * max(0.0, 1.0 - smooth((t - t_wheel0) / max(0.5, t_steady - t_wheel0)))
        return (math.sin(1.7 * u) * amp, 0.0, 0.0)
    bake(tl, hub, "rotation_euler", wheel)
    # fog around the ship that lifts (rises + thins) from t_lift
    fm = fog_mat("ship_fog", 0.2)
    pr = fm.node_tree.nodes.get("Principled BSDF")
    bake_sock(tl, pr.inputs["Alpha"], lambda t: 0.2 * (1.0 - smooth((t - t_lift) / 2.2)))
    rf = random.Random(77)
    for i in range(16):
        me = puff_mesh("sfog%d" % i, 200 + i)
        me.materials[0] = fm
        o = S.obj("sfog%d" % i, me, (0, 0, 0), scale=(2.8, 2.8, 1.8))
        o.visible_shadow = False
        ox, oy, oz = rf.uniform(-18, 18), rf.choice((-1, 1)) * rf.uniform(5.0, 10.0), rf.uniform(1.5, 5.0)
        if -14 < ox < -6 and abs(oy) < 5:
            oy = math.copysign(6.5, oy)

        def fp(t, ox=ox, oy=oy, oz=oz):
            u = smooth((t - t_lift) / 2.5)
            return (ship_x(t) + ox + 0.6 * math.sin(0.4 * t + ox), SHIP_Y + oy, oz + 9.0 * u)
        bake(tl, o, "location", fp, step=3)
    return root, BX


def bake_sock(tl, sock, fn, step=2):
    Gs = tl.frames()[::step] + [tl.frames()[-1]]
    for G in Gs:
        L.kf_socket(sock, tl.lf(G), fn(tl.t_of_G(G)), "LINEAR")


def build_campus(mt, rng):
    """Other campus buildings, lamp posts, benches, planters, trees, parking; far city + hills."""
    blds = [((-110.0, 70.0), (50, 34, 16), "bld1"), ((-120.0, -60.0), (44, 30, 12), "bld2"),
            ((140.0, 60.0), (46, 36, 20), "bld1"), ((170.0, -20.0), (40, 30, 12), "bld2"),
            ((-60.0, -80.0), (36, 26, 10), "bld2"), ((10.0, 150.0), (70, 30, 24), "bld1"),
            ((-150.0, 160.0), (40, 40, 30), "bld2"), ((150.0, 150.0), (50, 40, 34), "bld1"),
            ((-200.0, 40.0), (40, 30, 14), "bld1"), ((240.0, 40.0), (40, 30, 16), "bld2")]
    for i, ((x, y), (w, d, h), mk) in enumerate(blds):
        boxes("bld%d" % i, [((0, 0, h / 2), (w, d, h), 0), ((0, 0, h + 0.3), (w + 0.6, d + 0.6, 0.6), 1)],
              [mt[mk], mt["roof"]], loc=(x, y, 0.0))
    # lamp posts + benches + planters around the plaza
    lamp_me = _m("lamp", lambda: _lamp_mesh(mt))
    for x in (-46.0, -30.0, 30.0, 46.0):
        for y in (-26.0, 24.0):
            S.obj("lamp", lamp_me, (x, y, 0.0))
    bench = boxes("bench_src", [((0, 0, 0.45), (2.4, 0.6, 0.08), 0), ((-1.0, 0, 0.22), (0.1, 0.5, 0.44), 1),
                                ((1.0, 0, 0.22), (0.1, 0.5, 0.44), 1)], [mt["wood"], mt["steel"]])
    for (x, y, r) in ((-10.0, -22.0, 0.0), (10.0, -22.0, 0.0), (-40.0, 0.0, 1.57), (40.0, 0.0, 1.57)):
        S.obj("bench", bench.data, (x, y, 0.0), (0, 0, r))
    bpy.data.objects.remove(bench, do_unlink=True)
    pl = _m("planter", lambda: _planter_mesh(mt))
    for (x, y) in ((-36.0, 22.0), (36.0, 22.0), (-36.0, -20.0), (36.0, -20.0), (-14.0, -26.0), (14.0, -26.0)):
        S.obj("planter", pl, (x, y, 0.0))
    # parking lot west of the HQ (plain stripes)
    S.plane_obj("parking", 60, 40, (-95.0, 25.0, 0.025), mt["road"])
    bm = bmesh.new()
    for i in range(12):
        box(bm, (-122.0 + i * 5.0, 25.0, 0.04), (0.15, 14.0, 0.01))
    S.obj("park_lines", S.mesh_from_bm("park_lines", bm, [mt["line"]]))
    # trees: campus clusters, avoiding buildings, the plaza, the road, the lake and the camera paths
    tree_t = S.tree_templates(rng)
    pts = []
    for _ in range(900):
        x, y = rng.uniform(-420, 420), rng.uniform(-260, 260)
        if -58 < x < 58 and -36 < y < 80:
            continue
        if x < -45 and abs(y - ROAD_Y) < 16:
            continue
        if -200 < x < -40 and -80 < y < 10:       # the road view looks north-west over this lawn
            continue
        if 50 < x < 106 and -2 < y < 56:
            continue
        if ((x - LAKE[0]) / (LAKE[2] + 8)) ** 2 + ((y - LAKE[1]) / (LAKE[3] + 8)) ** 2 < 1:
            continue
        if 60 < x < 100 and -36 < y < 10:        # walkway / camera route to the lake
            continue
        if -80 < x < 60 and -60 < y < -2:        # whip routes across the south lawn
            continue
        if any(abs(x - bx) < w / 2 + 6 and abs(y - by) < d / 2 + 6 for (bx, by), (w, d, h), _ in blds):
            continue
        if -128 < x < -62 and 2 < y < 48:
            continue
        if abs(y - 120.0) < 9:
            continue
        pts.append((x, y))
    # a row of street trees along the road (outside the posts)
    for i in range(40):
        for sy in (-1, 1):
            pts.append((-70.0 - i * 22.0 + rng.uniform(-3, 3), ROAD_Y + sy * rng.uniform(13.0, 17.0)))
    S.scatter(tree_t, pts, rng, (0.8, 1.3), prefix="tree")
    S.build_city(rng, region=(-1700, 1700, 700, 2300))
    S.build_hills(rng)
    print("[v2 campus] %d trees" % len(pts))


def _lamp_mesh(mt):
    bm = bmesh.new()
    cyl(bm, (0, 0, 2.5), 0.08, 5.0, 0, 10)
    box(bm, (0.35, 0, 5.0), (0.9, 0.22, 0.12), 0)
    return S.mesh_from_bm("lamp", bm, [mt["frame"]])


def _planter_mesh(mt):
    bm = bmesh.new()
    box(bm, (0, 0, 0.35), (3.0, 3.0, 0.7), 1)
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    bmesh.ops.scale(bm, vec=(1.3, 1.3, 1.1), verts=res["verts"])
    bmesh.ops.translate(bm, vec=(0, 0, 1.3), verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = 0
    return S.mesh_from_bm("planter", bm, [mt["plant"], mt["stone"]])


# ================================================================ the camera route
def _dir(a, b):
    d = Vector(b) - Vector(a)
    return d.normalized()


def _slerp(d0, d1, u):
    dot = max(-1.0, min(1.0, d0.dot(d1)))
    om = math.acos(dot)
    if om < 1e-4:
        return d0.lerp(d1, u).normalized()
    so = math.sin(om)
    return (d0 * (math.sin((1 - u) * om) / so) + d1 * (math.sin(u * om) / so)).normalized()


def _polyline(pts, u):
    """point at arc-length fraction u along the polyline pts"""
    pts = [Vector(p) for p in pts]
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    tot = sum(seg) or 1.0
    s = u * tot
    for i, l in enumerate(seg):
        if s <= l or i == len(seg) - 1:
            return pts[i].lerp(pts[i + 1], min(1.0, s / l if l > 0 else 1.0))
        s -= l
    return pts[-1]


def route(tl):
    """Spots: (t_whip_centre, whip_duration, pose_fn(t, u) -> (loc, tgt, lens), waypoints between spots).
    pose_fn gets the global time and the drift fraction u (0 at arrival, 1 at the next departure)."""
    sx, sy = SCALE
    gx, gy = GAUGE
    px, py = PODIUM
    t_q = tl.bstart("question")
    t_1 = tl.bstart("one_expectations")
    t_2 = tl.bstart("two_uncertainty")
    t_3 = tl.bstart("three_board")
    t_m = tl.bstart("metaphor")
    t_s = tl.bstart("scale")
    t_inv = tl.cue("scale", "not", 0.75) - 0.1
    t_k = tl.bstart("takeaway")
    t_o = tl.bstart("outro")

    def lin(a, b):
        return lambda t, u: (Vector(a[0]).lerp(Vector(b[0]), u), Vector(a[1]).lerp(Vector(b[1]), u),
                             a[2] + (b[2] - a[2]) * u)

    def ship_pose(t, u):
        bx = ship_x(t) - 10.5
        a_loc, a_tgt = Vector((ship_x(t) + 4.0, -24.0, 10.0)), Vector((ship_x(t) - 1.0, SHIP_Y, 4.0))
        b_loc, b_tgt = Vector((bx + 12.5, SHIP_Y + 5.5, 12.2)), Vector((bx + 0.6, SHIP_Y, 8.4))
        w = smooth((u - 0.25) / 0.75)
        return a_loc.lerp(b_loc, w), a_tgt.lerp(b_tgt, w), 24.0 + 8.0 * w

    def orbit(t, u):
        a = math.radians(-120.0 + 55.0 * u)
        r = 19.0
        loc = Vector((gx + r * math.cos(a), gy + r * math.sin(a), 4.4 - 0.6 * u))
        return loc, Vector((gx, gy, 6.9)), 30.0

    spots = [
        (0.0, 0.0, lin(((0.0, -34.0, 4.5), (0.0, 36.0, 10.0), 28.0), ((0.0, 21.0, 2.7), (px, py, 2.0), 32.0)), []),
        (t_q, 0.55, lin(((0.0, 8.0, 3.0), (0.0, 40.0, 15.0), 24.0), ((0.0, 2.0, 3.6), (0.0, 40.0, 15.5), 24.0)), []),
        (t_1, 0.75, lin(((-80.0, -9.0, 6.0), (-175.0, 3.0, 8.5), 26.0), ((-97.0, -9.5, 6.5), (-195.0, 3.0, 9.5), 26.0)),
         [(-40.0, -14.0, 8.0)]),
        (t_2, 0.85, lin(((69.0, 12.2, 1.9), (61.8, 21.0, 0.9), 22.0), ((68.0, 13.4, 1.8), (61.8, 21.2, 0.95), 24.0)),
         [(30.0, -22.0, 7.0), (68.0, -4.0, 2.2), (68.0, 8.0, 1.9)]),
        (t_3, 0.6, lin(((74.6, 12.6, 2.1), (86.0, 19.5, 0.85), 22.0), ((77.4, 12.4, 2.5), (88.0, 19.5, 0.8), 22.0)),
         [(70.0, 13.8, 1.8), (71.5, 13.8, 1.9)]),
        (t_m, 0.75, ship_pose, [(81.6, 12.0, 2.2), (81.6, 6.0, 2.6), (76.0, -20.0, 6.0)]),
        (t_s, 0.85, lin(((-17.0, -15.0, 5.0), (sx + 0.5, sy, 7.6), 24.0), ((-19.5, -11.0, 5.3), (sx + 0.8, sy, 7.8), 24.0)),
         [(20.0, -30.0, 9.0)]),
        (t_inv, 0.55, lin(((2.4, 29.2, 2.35), (px, py, 2.05), 34.0), ((1.6, 30.2, 2.25), (px, py, 2.1), 36.0)), []),
        (t_k, 0.6, orbit, []),
        (t_o, 0.7, lin(((0.0, 21.0, 2.7), (px, py, 2.0), 32.0), ((0.0, -34.0, 4.5), (0.0, 36.0, 10.0), 28.0)),
         [(6.0, 14.0, 4.0)]),
    ]
    return spots


def camera_at(spots, t, T_end):
    """(loc, tgt, lens) at global seconds t."""
    n = len(spots)
    for i in range(n):
        tc, wd, pose, _ = spots[i]
        arr = tc + wd / 2.0
        dep = spots[i + 1][0] - spots[i + 1][1] / 2.0 if i + 1 < n else T_end
        if i + 1 < n and t > dep:
            continue
        if t < arr and i > 0:
            # whip from spot i-1 (at its departure) into spot i
            ptc, pwd, ppose, _ = spots[i - 1]
            pdep = tc - wd / 2.0
            parr = ptc + pwd / 2.0
            l0, t0, z0 = ppose(pdep, 1.0)
            l1, t1, z1 = pose(arr, 0.0)
            u = smoother((t - pdep) / wd)
            loc = _polyline([l0] + [Vector(w) for w in spots[i][3]] + [l1], u)
            d0, d1 = _dir(l0, t0), _dir(l1, t1)
            d = _slerp(d0, d1, u)
            return loc, loc + d * 10.0, z0 + (z1 - z0) * u
        u = (t - arr) / max(0.01, dep - arr) if i > 0 else t / max(0.01, dep)
        return pose(t, max(0.0, min(1.0, u)))
    return spots[-1][2](t, 1.0)


# ================================================================ BUILDER
def b_campus_oneshot(ctx, p):
    tl = TL(ctx)
    tl.ctx = ctx
    SHIP_T["t0"] = (tl.bstart("metaphor") + tl.bend("metaphor")) / 2.0
    sc = ctx.scene
    rng = random.Random(p.get("seed", 24))
    S.daylight(ctx, p.get("sun_az", -30.0), 42.0)
    L.fog(0.00035, S.HAZE, start=160.0)
    C.horizon_haze(sc, lo=-0.01, hi=0.06)
    mt = mats()
    # cue times (global seconds)
    t_inv = tl.cue("scale", "investigation", 0.85)
    build_ground(mt, rng)
    build_hq(mt)
    pod, fold = build_podium(ctx, mt)
    show_between(tl, fold, t_inv - 0.05)
    build_scale(tl, mt, tl.cue("scale", "added", 0.4) - 0.2, tl.cue("scale", "single", 0.62) + 0.3)
    build_gauge(tl, mt, tl.bstart("takeaway") + 0.5, tl.cue("takeaway", "swing", 0.85), tl.bend("takeaway"))
    t1 = tl.bstart("one_expectations")
    build_road_props(tl, mt, tl.cue("one_expectations", "share", 0.15), tl.cue("one_expectations", "change", 0.75) - 0.3,
                     tl.bend("one_expectations") + 0.5, tl.cue("one_expectations", "expect", 0.6),
                     tl.cue("one_expectations", "overnight", 0.92) - 0.3)
    build_wing(tl, mt, tl.cue("three_board", "shareholders", 0.2), tl.cue("three_board", "answer", 0.95))
    build_lake_ship(tl, mt, tl.bstart("metaphor") + 0.2, tl.cue("metaphor", "captain", 0.9),
                    tl.cue("metaphor", "nobody", 0.75))
    build_campus(mt, rng)
    # the camera: one continuous route on the global timeline
    spots = route(tl)
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=30)
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000.0
    T_end = tl.T + 1.0
    bake(tl, cam, "location", lambda t: camera_at(spots, t, T_end)[0])
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    # motion blur for the whips
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 campus] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 campus] beat %d (%s): global frames %d-%d" % (tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1,
                                                           tl.off[tl.k] + tl.n[tl.k]))


S.V2_BUILDERS.update({"campus_oneshot": b_campus_oneshot})

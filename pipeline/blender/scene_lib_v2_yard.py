"""v2 suburban backyard / turkey-fryer builders ("turkey fryer fire", 26 Nov 2026 slot 1).
Registers into scene_lib_v2.V2_BUILDERS.

World (every beat builds the same one): a sunny autumn backyard in an American suburb (HDRI sky). A two-storey
house (back wall facing south, -Y) with an attached garage (east) and a wooden deck (west part of the back wall), a
fenced lawn, autumn trees, neighbours' houses and a hazy suburb beyond. A propane turkey fryer (steel pot on a
three-legged burner stand, propane tank, hoist pole with a hook) stands in the middle of the lawn.

Non-graphic and abstract: heat is only a soft pulsing orange glow under the pot; spilled oil is a golden ribbon;
steam = white puffs; smoke = soft grey wisps. No flame shapes, no people in danger. No 3D text (2D overlays only).

Builders
  yard_hook    wide of the backyard, slow push in towards the fryer (turkey hanging on the hoist above the pot)
  yard_orbit   slow orbit around the fryer with the turkey above the pot
  fryer_cut    wedge-cutaway pot close-up. mode overfill (turkey lowers, oil level climbs, ribbon spills down to the
               burner, glow grows) / ice (ice crystals in the bird turn into steam puffs that push oil droplets up and
               out) / heat (big dial thermometer: needle green -> amber -> red, oil darkens, grey wisps)
  bathtub_v2   toy bathtub brim-full of water on the lawn; a rubber duck drops in, water spills over; the water turns
               gold on `oil_cue`, a soft orange glow under the tub on `flame_cue`
  yard_top     high view of house, garage, deck and lawn: red "no" rings on the garage and the deck, green ring
               around the fryer on the open lawn
  yard_safe    takeaway: thawed bird on a side table, teal fill-line band on the pot, green ring on open lawn,
               a person standing watch, an oil-free electric fryer slides in
  yard_outro   Thanksgiving table on the patio in warm light, roast turkey on a platter; camera cranes up
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
import scene_lib_v2_storm as ST
from scene_lib import hexc
from scene_lib_v2_winter import set_keys

FRYER = (2.0, -5.0)          # pot centre (x, y)
POT_R, POT_H, POT_Z = 0.2, 0.5, 0.42     # radius, height, bottom z (top of the burner stand)
WEDGE = (-90.0, 52.0)        # cutaway: removed sector centre (deg, -90 = facing -Y) and half width
HOUSE = (0.0, 16.0)          # centre; back wall at y = 11.5
TABLE = (-10.5, 2.0)         # Thanksgiving table (patio)

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def vis_keys(o, keys):
    s = tuple(o.scale)
    set_keys(o, "scale", [f for f, _ in keys], [(s if v else (0.0, 0.0, 0.0)) for _, v in keys], "CONSTANT")


def sock_keys(sock, keys):
    """keys = [(frame, value)] on a material socket (holds are repeated keys, so interpolation never matters)."""
    for f, v in keys:
        L.kf_socket(sock, max(1, int(f)), v, "LINEAR")


# ================================================================ materials
def wood_mat(name="deck_wood", color="9a6a43", plank=0.14, along="X"):
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        obj = S._coord(N, Lk, "Object")
        wv = N.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = along
        wv.inputs["Scale"].default_value = 1.0 / plank / 6.28
        wv.inputs["Distortion"].default_value = 0.0
        Lk.new(obj, wv.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.0
        mr.inputs["From Max"].default_value = 0.12
        mr.inputs["To Min"].default_value = 0.55
        mr.inputs["To Max"].default_value = 1.0
        Lk.new(wv.outputs["Fac"], mr.inputs["Value"])
        fac, _ = S._noise_var(N, Lk, obj, 2.5, 0.12)
        col = S._mul_col(N, Lk, tuple(hexc(color)), fac)
        col = S._mul_col(N, Lk, col, mr.outputs["Result"])
        Lk.new(col, p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.7
        return S._finish(m, p.outputs[0])
    return _m(name, mk)


def steel_mat():
    return S.pbr("fry_steel", hexc("c9cdd2"), 0.28, 0.9, var=0.04, var_scale=4.0)


def dark_steel():
    return S.pbr("fry_dark", hexc("2a2d31"), 0.45, 0.6, var=0.03)


def oil_mat(name="fry_oil", col0="f0b532", emis=0.35):
    """Golden oil (self-lit a little so the section always reads). Returns (mat, base_sock, emis_sock)."""
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc(col0)
    p.inputs["Emission Color"].default_value = hexc(col0)
    p.inputs["Emission Strength"].default_value = emis
    p.inputs["Roughness"].default_value = 0.12
    p.inputs["Coat Weight"].default_value = 0.6
    p.inputs["Coat Roughness"].default_value = 0.03
    S._finish(m, p.outputs[0], haze=False)
    return m, p.inputs["Base Color"], p.inputs["Emission Color"]


def water_sheet_mat(col_sock_src, f_oil):
    """Translucent overflow sheet; its colour follows the tub water (blue -> gold on f_oil)."""
    m = bpy.data.materials.new("tub_sheet")
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Alpha"].default_value = 0.55
    p.inputs["Roughness"].default_value = 0.08
    p.inputs["Emission Strength"].default_value = 0.35
    for sock, c1 in ((p.inputs["Base Color"], "f0b532"), (p.inputs["Emission Color"], "f6b52e")):
        sock_keys(sock, [(1, hexc("6cc0f0")), (f_oil, hexc("6cc0f0")), (f_oil + 20, hexc(c1))])
    return m


def turkey_mats():
    raw = S.pbr("turkey_raw", hexc("ecc9a6"), 0.55, var=0.06, var_scale=12.0, bump=0.05)
    return raw


def glow_disc(name, loc, r, col="ff8a2a"):
    m, sock = L.add_mat(name, hexc(col), 0.0)
    bm = bmesh.new()
    res = bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=r)
    o = S.obj(name, S.mesh_from_bm(name, bm, [m]), loc)
    o.visible_shadow = False
    return o, sock


def point_light(name, loc, energy, color=(1.0, 0.55, 0.2), radius=0.1):
    d = bpy.data.lights.new(name, "POINT")
    d.energy = energy
    d.color = color
    d.shadow_soft_size = radius
    o = L.link(bpy.data.objects.new(name, d))
    o.location = loc
    return o, d


# ================================================================ templates
AUTUMN = ("d9822b", "c9502c", "e0b03a", "b5432a", "8e9a3a", "d96a2a", "6f8a3c")


def autumn_trees(rng):
    trunk = S.pbr("trunk_au", hexc("5a4632"), 0.9, var=0.1)
    out = []
    for i, c in enumerate(AUTUMN):
        leaf = S.pbr("leaf_au_%d" % i, hexc(c), 0.85, var=0.18, var_scale=0.9, bump=0.1)

        def build(bm, i=i):
            S.bm_box(bm, (0, 0, 1.8), (0.45, 0.45, 3.6), 0)
            r2 = random.Random(300 + i)
            for k in range(3 if i % 2 == 0 else 2):
                res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
                for v in res["verts"]:
                    v.co *= 1.0 + r2.uniform(-0.12, 0.12)
                s = (3.3 - 0.7 * k)
                bmesh.ops.scale(bm, vec=(s, s, s * 0.92), verts=res["verts"])
                bmesh.ops.translate(bm, vec=(r2.uniform(-1.2, 1.2), r2.uniform(-1.2, 1.2), 6.2 + 1.4 * k),
                                    verts=res["verts"])
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 1
        out.append(S._template("autree_%d" % i, build, [trunk, leaf]))
    return out


# ================================================================ the house
def build_house():
    siding = S.pbr("house_siding", hexc("dfe3e2"), 0.8, var=0.04, var_scale=0.5)
    trim = S.pbr("house_trim", hexc("f6f6f2"), 0.6, var=0.02)
    roof = S.pbr("house_roof", hexc("4b4f56"), 0.8, var=0.1, var_scale=3.0, bump=0.12)
    win = S.pbr("house_win", hexc("2b3a4a"), 0.08, var=0)
    door = S.pbr("house_door", hexc("7c2f2a"), 0.5, var=0.04)
    gar = S.pbr("garage_wall", hexc("d8d3c7"), 0.8, var=0.04)
    gdoor = S.pbr("garage_door", hexc("f1f0ec"), 0.5, var=0.02)
    groof = S.pbr("garage_roof", hexc("6b4a3a"), 0.8, var=0.1, var_scale=3.0, bump=0.1)
    hx, hy = HOUSE
    w, d, h = 14.0, 9.0, 6.0
    bm = bmesh.new()
    S.bm_box(bm, (hx, hy, h / 2), (w, d, h), 0)
    S.bm_box(bm, (hx, hy, 0.25), (w + 0.3, d + 0.3, 0.5), 1)
    # windows on the back (south) wall: 2 floors x 4 + frames
    for fl, z in enumerate((1.7, 4.4)):
        for k in range(4):
            x = hx - 5.2 + k * 3.47
            if fl == 0 and k == 2:
                continue
            S.bm_box(bm, (x, hy - d / 2 - 0.05, z), (1.5, 0.08, 1.3), 1)
            S.bm_box(bm, (x, hy - d / 2 - 0.09, z), (1.3, 0.06, 1.1), 2)
    # back door (onto the deck)
    S.bm_box(bm, (hx - 2.4, hy - d / 2 - 0.05, 1.6), (1.2, 0.1, 2.3), 1)
    S.bm_box(bm, (hx - 2.4, hy - d / 2 - 0.09, 1.55), (1.0, 0.06, 2.1), 3)
    # side (west) windows
    for z in (1.7, 4.4):
        S.bm_box(bm, (hx - w / 2 - 0.05, hy, z), (0.08, 1.5, 1.3), 1)
        S.bm_box(bm, (hx - w / 2 - 0.09, hy, z), (0.06, 1.3, 1.1), 2)
    S.bm_prism_x(bm, hx - w / 2 - 0.4, hx + w / 2 + 0.4,
                 [(hy - d / 2 - 0.6, h - 0.1), (hy + d / 2 + 0.6, h - 0.1), (hy, h + 3.0)], 4)
    # chimney
    S.bm_box(bm, (hx - 4.5, hy + 1.5, h + 2.6), (1.0, 1.0, 3.0), 5)
    S.obj("house", S.mesh_from_bm("house", bm, [siding, trim, win, door, roof,
                                                S.pbr("chimney", hexc("9a5a44"), 0.8, var=0.08, bump=0.1)]))
    # garage (east, attached): door faces south
    bm = bmesh.new()
    gx, gy, gw, gd, gh = hx + w / 2 + 3.6, hy - 0.5, 7.2, 8.0, 3.3
    S.bm_box(bm, (gx, gy, gh / 2), (gw, gd, gh), 0)
    S.bm_box(bm, (gx, gy - gd / 2 - 0.05, 1.15), (5.4, 0.1, 2.3), 1)
    for k in range(4):
        S.bm_box(bm, (gx, gy - gd / 2 - 0.11, 0.35 + k * 0.55), (5.3, 0.04, 0.05), 3)
    S.bm_prism_x(bm, gx - gw / 2 - 0.3, gx + gw / 2 + 0.3,
                 [(gy - gd / 2 - 0.5, gh - 0.1), (gy + gd / 2 + 0.5, gh - 0.1), (gy, gh + 1.6)], 2)
    S.obj("garage", S.mesh_from_bm("garage", bm, [gar, gdoor, groof, S.pbr("gdoor_line", hexc("c9c7c0"), 0.6, var=0)]))
    # driveway apron in front of the garage door
    S.plane_obj("drive", 6.0, 9.0, (gx, gy - gd / 2 - 4.5, 0.03), S.pbr("drive_conc", hexc("c4c0b8"), 0.85, var=0.06,
                                                                       var_scale=0.8))
    return {"garage": (gx, gy, gh + 1.6), "garage_door": (gx, gy - gd / 2, 1.2)}


def build_deck():
    """Wooden deck on the back wall (west part): x -7..1, y 7.6..11.5, top z 0.6, railing, steps."""
    wood = wood_mat()
    post = wood_mat("deck_post", "8a5c3a", 0.5, "Z")
    bm = bmesh.new()
    x0, x1, y0, y1, z = -7.0, 1.0, 7.4, 11.5, 0.6
    S.bm_box(bm, ((x0 + x1) / 2, (y0 + y1) / 2, z - 0.06), (x1 - x0, y1 - y0, 0.12), 0)
    for x in (x0 + 0.1, (x0 + x1) / 2, x1 - 0.1):
        S.bm_box(bm, (x, y0 + 0.1, z / 2), (0.15, 0.15, z), 1)
    S.obj("deck", S.mesh_from_bm("deck", bm, [wood, post]))
    bm = bmesh.new()
    for x in [x0 + 0.05 + k * 1.0 for k in range(9)]:
        if -3.6 < x < -1.4:
            continue
        S.bm_box(bm, (x, y0 + 0.05, z + 0.5), (0.09, 0.09, 1.0), 0)
    S.bm_box(bm, ((x0 + (-3.6)) / 2, y0 + 0.05, z + 1.0), (-3.6 - x0, 0.12, 0.08), 0)
    S.bm_box(bm, ((x1 + (-1.4)) / 2, y0 + 0.05, z + 1.0), (x1 + 1.4, 0.12, 0.08), 0)
    for yy in (y0 + 0.5, y0 + 1.5, y0 + 2.5, y0 + 3.5):
        S.bm_box(bm, (x0 + 0.05, yy, z + 0.5), (0.09, 0.09, 1.0), 0)
    S.bm_box(bm, (x0 + 0.05, (y0 + y1) / 2, z + 1.0), (0.12, y1 - y0, 0.08), 0)
    for k in range(3):   # steps
        S.bm_box(bm, (-2.5, y0 - 0.35 - k * 0.35, z - 0.2 - k * 0.2), (2.0, 0.35, 0.12), 1)
    S.obj("deck_rail", S.mesh_from_bm("deck_rail", bm, [post, wood]))
    return {"deck": ((x0 + x1) / 2, (y0 + y1) / 2, z)}


def build_fence():
    wood = wood_mat("fence_wood", "b58d62", 0.16, "X")
    bm = bmesh.new()
    x0, x1, y0, y1 = -21.0, 23.0, -24.0, 11.0
    for (a, b) in (((x0, y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))):
        L_ = math.hypot(b[0] - a[0], b[1] - a[1])
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if abs(b[1] - a[1]) < 1e-3:
            S.bm_box(bm, (cx, cy, 0.9), (L_, 0.06, 1.8), 0)
        else:
            S.bm_box(bm, (cx, cy, 0.9), (0.06, L_, 1.8), 0)
    S.obj("fence", S.mesh_from_bm("fence", bm, [wood]))


# ================================================================ the fryer
def _sector_shell(bm, r_out, r_in, z0, z1, a0, a1, seg=40, mi=0, bottom=True):
    """Pot wall between angles a0..a1 (deg, CCW), open top, with cut faces at both ends (+ sector bottom)."""
    outs, ins = [], []
    for k in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * k / seg)
        c, s = math.cos(a), math.sin(a)
        outs.append((bm.verts.new((r_out * c, r_out * s, z0)), bm.verts.new((r_out * c, r_out * s, z1))))
        ins.append((bm.verts.new((r_in * c, r_in * s, z0 + 0.012)), bm.verts.new((r_in * c, r_in * s, z1))))
    fs = []
    for k in range(seg):
        fs.append(bm.faces.new((outs[k][0], outs[k + 1][0], outs[k + 1][1], outs[k][1])))
        fs.append(bm.faces.new((ins[k][1], ins[k + 1][1], ins[k + 1][0], ins[k][0])))
        fs.append(bm.faces.new((outs[k][1], outs[k + 1][1], ins[k + 1][1], ins[k][1])))
    for e in (0, seg):
        fs.append(bm.faces.new((outs[e][0], outs[e][1], ins[e][1], ins[e][0])))
    if bottom:
        c0 = bm.verts.new((0, 0, z0))
        c1 = bm.verts.new((0, 0, z0 + 0.012))
        for k in range(seg):
            fs.append(bm.faces.new((c0, outs[k + 1][0], outs[k][0])))
            fs.append(bm.faces.new((c1, ins[k][0], ins[k + 1][0])))
    for f in fs:
        f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=fs)


def _sector_solid(bm, r, z0, z1, a0, a1, seg=40, mi_side=0, mi_cut=1):
    """Solid cylinder sector (oil): top, bottom, curved side, two radial cut faces."""
    c0, c1 = bm.verts.new((0, 0, z0)), bm.verts.new((0, 0, z1))
    ring = []
    for k in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * k / seg)
        ring.append((bm.verts.new((r * math.cos(a), r * math.sin(a), z0)),
                     bm.verts.new((r * math.cos(a), r * math.sin(a), z1))))
    fs = []
    for k in range(seg):
        f = bm.faces.new((ring[k][0], ring[k + 1][0], ring[k + 1][1], ring[k][1]))
        f.material_index = mi_side
        fs.append(f)
        f = bm.faces.new((c1, ring[k][1], ring[k + 1][1]))
        f.material_index = mi_cut
        fs.append(f)
        f = bm.faces.new((c0, ring[k + 1][0], ring[k][0]))
        f.material_index = mi_side
        fs.append(f)
    for e in (0, seg):
        f = bm.faces.new((c0, ring[e][0], ring[e][1], c1))
        f.material_index = mi_cut
        fs.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=fs)


def _ell(bm, c, r, rot=(0, 0, 0), mi=0, seg=16, rings=10):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    vs = res["verts"]
    bmesh.ops.scale(bm, vec=r, verts=vs)
    if any(rot):
        from mathutils import Euler
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Euler(rot).to_matrix())
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi


def bird_mesh(bm, z, mi=0, bone=1):
    """Classic turkey silhouette lying on its back (breast up), drumsticks pointing +X and up. z = underside."""
    _ell(bm, (0, 0, z + 0.095), (0.155, 0.12, 0.095), mi=mi, seg=24, rings=14)
    _ell(bm, (-0.02, 0, z + 0.13), (0.11, 0.1, 0.075), mi=mi, seg=20, rings=12)
    for sy in (-1, 1):
        _ell(bm, (0.12, sy * 0.065, z + 0.15), (0.085, 0.042, 0.045), rot=(0, -0.55, sy * 0.15), mi=mi)
        _ell(bm, (0.19, sy * 0.07, z + 0.205), (0.022, 0.022, 0.022), mi=bone, seg=10, rings=8)
        _ell(bm, (-0.05, sy * 0.115, z + 0.09), (0.07, 0.03, 0.04), rot=(0, 0.2, 0), mi=mi)


def make_turkey(name, mat, roast=False):
    """Bird on a round frying basket hanging from a hook rod (origin = top of the rod, basket bottom at -0.47)."""
    root = L.link(bpy.data.objects.new(name, None))
    bm = bmesh.new()
    bird_mesh(bm, -0.455)
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [mat, S.pbr("turkey_bone", hexc("f2ead8"), 0.5, var=0)],
                                         smooth=True), parent=root)
    rod = S.pbr("hook_rod", hexc("9aa0a7"), 0.3, 0.9, var=0)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.007, radius2=0.007, depth=0.2)
    bmesh.ops.translate(bm, vec=(0, 0, -0.1), verts=r["verts"])
    S.bm_box(bm, (0, 0, -0.2), (0.34, 0.012, 0.012), 0)
    for sx in (-1, 1):
        S.bm_box(bm, (sx * 0.17, 0, -0.335), (0.01, 0.01, 0.27), 0)
    S.obj(name + "_rod", S.mesh_from_bm(name + "_rod", bm, [rod]), parent=root)
    bm = bmesh.new()
    C._annulus(bm, 0.165, 0.02, 40)
    r = bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=0.155)
    S.obj(name + "_basket", S.mesh_from_bm(name + "_basket", bm, [rod]), (0, 0, -0.465), parent=root)
    return root


def build_fryer(ctx, cut=False, turkey=True, turkey_z=None):
    """Pot on a burner stand at FRYER, propane tank + hose, hoist pole with a line to the turkey.
    Returns dict: pot, oil (scale z = level 0..1 of POT_H), oil socks, turkey root, line, glow socks, light."""
    fx, fy = FRYER
    root = L.link(bpy.data.objects.new("fryer", None))
    root.location = (fx, fy, 0.0)
    st = steel_mat()
    dk = dark_steel()
    # stand: 3 legs + seat ring + burner bowl
    bm = bmesh.new()
    for k in range(3):
        a = math.radians(90 + 120 * k)
        x, y = 0.26 * math.cos(a), 0.26 * math.sin(a)
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.015, radius2=0.015, depth=POT_Z)
        bmesh.ops.translate(bm, vec=(x, y, POT_Z / 2), verts=r["verts"])
    bm_r = bmesh.new()
    C._annulus(bm_r, 0.24, 0.05, 48)
    bmesh.ops.translate(bm_r, vec=(0, 0, POT_Z - 0.01), verts=bm_r.verts[:])
    S.obj("fry_ring", S.mesh_from_bm("fry_ring", bm_r, [dk]), parent=root)
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.09, radius2=0.13, depth=0.06)
    bmesh.ops.translate(bm, vec=(0, 0, 0.2), verts=r["verts"])
    for k in range(3):
        a = math.radians(90 + 120 * k)
        S.bm_box(bm, (0.13 * math.cos(a), 0.13 * math.sin(a), POT_Z - 0.03), (0.24, 0.02, 0.02), 0)
    S.obj("fry_stand", S.mesh_from_bm("fry_stand", bm, [dk]), parent=root)
    # pot (full or wedge-cut)
    bm = bmesh.new()
    if cut:
        a0 = WEDGE[0] + WEDGE[1]
        a1 = WEDGE[0] - WEDGE[1] + 360.0
        _sector_shell(bm, POT_R, POT_R - 0.01, POT_Z, POT_Z + POT_H, a0, a1, 56, 0)
    else:
        _sector_shell(bm, POT_R, POT_R - 0.01, POT_Z, POT_Z + POT_H, 0.0, 360.0, 56, 0)
    for sx in (-1, 1):   # handles
        S.bm_box(bm, (sx * (POT_R + 0.03), 0, POT_Z + POT_H - 0.06), (0.06, 0.03, 0.02), 1)
    pot = S.obj("fry_pot", S.mesh_from_bm("fry_pot", bm, [st, dk], smooth=False), parent=root)
    out = {"root": root, "pot": pot}
    # oil
    om, base_s, em_s = oil_mat()
    secm, sbase, sem = oil_mat("fry_oil_sec", "f6c046", 0.55)
    bm = bmesh.new()
    if cut:
        _sector_solid(bm, POT_R - 0.011, 0.0, 1.0, WEDGE[0] + WEDGE[1], WEDGE[0] - WEDGE[1] + 360.0, 56, 0, 1)
    else:
        _sector_solid(bm, POT_R - 0.011, 0.0, 1.0, 0.0, 360.0, 56, 0, 1)
    oil = S.obj("fry_oil", S.mesh_from_bm("fry_oil", bm, [om, secm]), (0, 0, POT_Z + 0.013), parent=root)
    oil.scale = (1.0, 1.0, POT_H * 0.55)
    out.update(oil=oil, oil_socks=(base_s, em_s, sbase, sem))
    # burner glow (additive disc under the pot) + light
    g, gs = glow_disc("burner_glow", (0, 0, 0.24), 0.16)
    g.parent = root
    g2, gs2 = glow_disc("burner_glow_big", (0, 0, 0.02), 0.6, "ff7a1e")
    g2.parent = root
    lo, ld = point_light("burner_light", (0, 0, 0.28), 0.0)
    lo.parent = root
    out.update(glow=(gs, gs2), light=ld)
    # propane tank + hose
    tank = S.pbr("propane_tank", hexc("eef0f2"), 0.45, 0.1, var=0.02)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.15, radius2=0.15, depth=0.38)
    bmesh.ops.translate(bm, vec=(0, 0, 0.23), verts=r["verts"])
    S._ellipsoid(bm, (0, 0, 0.42), (0.15, 0.15, 0.08), 0, 20, 8)
    S._ellipsoid(bm, (0, 0, 0.06), (0.15, 0.15, 0.06), 0, 20, 8)
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.1, radius2=0.1, depth=0.08)
    bmesh.ops.translate(bm, vec=(0, 0, 0.52), verts=r["verts"])
    S.obj("tank", S.mesh_from_bm("tank", bm, [tank], smooth=True), (0.85, 0.35, 0.0), parent=root)
    cu = bpy.data.curves.new("hose", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.012
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(1)
    for bp, co, hl, hr in zip(sp.bezier_points, ((0.85, 0.35, 0.55), (0.1, 0.0, 0.2)),
                              ((0.85, 0.35, 0.75), (0.5, 0.2, 0.0)), ((0.85, 0.35, 0.3), (-0.2, -0.1, 0.25))):
        bp.co, bp.handle_left, bp.handle_right = co, hl, hr
    ho = L.link(bpy.data.objects.new("hose", cu))
    ho.data.materials.append(S.pbr("hose_m", hexc("1d1f22"), 0.6, var=0))
    ho.parent = root
    # hoist: pole + arm + line
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.025, radius2=0.025, depth=1.95)
    bmesh.ops.translate(bm, vec=(-0.62, 0.15, 0.975), verts=r["verts"])
    S.bm_box(bm, (-0.31, 0.075, 1.93), (0.66, 0.04, 0.04), 0)
    S.bm_box(bm, (-0.62, 0.15, 0.02), (0.4, 0.4, 0.04), 0)
    S.obj("hoist", S.mesh_from_bm("hoist", bm, [dk]), parent=root)
    if turkey:
        tk = make_turkey("turkey", turkey_mats())
        tk.parent = root
        z = turkey_z if turkey_z is not None else 1.42
        tk.location = (0.0, 0.0, z)
        out["turkey"] = tk
        bm = bmesh.new()
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.004, radius2=0.004, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, -0.5), verts=r["verts"])
        line = S.obj("hoist_line", S.mesh_from_bm("hoist_line", bm, [dk]), (0.0, 0.0, 1.93), parent=root)
        line.scale = (1, 1, max(0.01, 1.93 - z))
        out["line"] = line
    return out


def lower_turkey(fr, tk, line, keys):
    """keys = [(frame, z)] for the turkey rod top; the hoist line follows."""
    set_keys(tk, "location", [f for f, _ in keys], [(0.0, 0.0, z) for _, z in keys], "BEZIER")
    set_keys(line, "scale", [f for f, _ in keys], [(1.0, 1.0, max(0.01, 1.93 - z)) for _, z in keys], "BEZIER")


# ================================================================ world
def build_yard_world(ctx, p, seed=26):
    rng = random.Random(p.get("seed", seed))
    S.daylight(ctx, p.get("sun_az", -40.0), 38.0, hdri=p.get("hdri", True))
    L.fog(p.get("fog", 0.0011), S.HAZE, start=p.get("fog_start", 70.0))
    C.horizon_haze(ctx.scene, lo=-0.01, hi=0.06)
    S.plane_obj("ground", 30000, 30000, (0, 0, -0.02), S.ground_mat())
    S.plane_obj("lawn", 44.0, 35.0, (1.0, -6.5, 0.0), S.lawn_mat("yard_lawn", hexc("6f8f45"), stripes=True))
    S.plane_obj("lawn_out", 400.0, 400.0, (0.0, 0.0, -0.01), S.lawn_mat("yard_lawn_out", hexc("7a9150"), stripes=False))
    info = build_house()
    info.update(build_deck())
    build_fence()
    # patio (stone) for the table
    S.plane_obj("patio", 6.5, 5.0, (TABLE[0], TABLE[1] + 0.5, 0.025),
                S.pbr("patio_stone", hexc("b8afa2"), 0.85, var=0.1, var_scale=1.5, bump=0.1))
    # trees: in the yard corners + along the fence outside + street trees
    au = autumn_trees(rng)
    pts = [(-17.0, -20.0), (19.0, -21.0), (-18.5, 6.0), (20.5, 3.0), (-8.0, -27.0), (12.0, -28.5), (-26.0, -8.0),
           (28.0, -12.0), (4.0, -30.0), (-28.0, 14.0), (30.0, 16.0)]
    S.scatter(au, pts, rng, (0.8, 1.15), prefix="ytree")
    # neighbours + suburb
    house_t = S.house_templates(rng)
    far_pts, tree_pts = [], []
    for gx in range(-420, 421, 30):
        for gy in range(-420, 421, 28):
            x, y = gx + rng.uniform(-3, 3), gy + rng.uniform(-3, 3)
            if -34 < x < 36 and -38 < y < 26:
                continue
            if abs(y - 40.0) < 9 or abs(x + 60.0) < 8 or abs(y + 66.0) < 8:   # streets
                continue
            if rng.random() < 0.12:
                continue
            far_pts.append((x, y))
            if rng.random() < 0.8:
                tree_pts.append((x + rng.uniform(-12, 12), y + rng.choice((-12, 12)) * rng.uniform(0.6, 1.0)))
    for x, y in far_pts:
        me = house_t[rng.randrange(len(house_t))]
        S.obj("nb", me, (x, y, 0.0), (0, 0, rng.choice((0.0, math.pi)) + rng.uniform(-0.05, 0.05)))
    for (x, y) in ((-44.0, 2.0), (46.0, -4.0), (0.0, -52.0), (-40.0, -40.0), (40.0, -44.0), (-46.0, 28.0)):
        S.obj("nb", house_t[rng.randrange(len(house_t))], (x, y, 0.0), (0, 0, rng.uniform(-0.1, 0.1)))
    tree_t = S.tree_templates(rng)
    S.scatter(au + tree_t[:3], tree_pts, rng, (0.8, 1.3), prefix="sub_tree")
    road = C.asphalt_mat("yard_road", hexc("55585c"))
    S.plane_obj("street_n", 900, 9, (0, 40.0, 0.02), road)
    S.plane_obj("street_w", 9, 900, (-60.0, 0, 0.021), road)
    S.plane_obj("street_s", 900, 9, (0, -66.0, 0.022), road)
    print("[v2 yard] world: %d suburb houses, %d trees" % (len(far_pts), len(tree_pts)))
    info["rng"] = rng
    return info


def _cam(ctx, loc, tgt, lens=30, clip=0.05):
    cam = A._cam(ctx, loc, tgt, lens)
    cam.data.clip_start = clip
    cam.data.clip_end = 20000.0
    return cam


def _anc(ctx, name, loc, parent=None):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    S.anchor(ctx, name, e)
    return e


def _keys(ctx, p, c0, t0, c1, t1, lens=30, clip=0.05):
    c0, t0 = p.get("cam0", c0), p.get("tgt0", t0)
    c1, t1 = p.get("cam1", c1), p.get("tgt1", t1)
    _cam(ctx, c0, t0, p.get("lens", lens), clip)
    A._cam_keys(ctx, [(1, c0, t0), (ctx.frames, c1, t1)])


# ================================================================ BUILDERS
def b_yard_hook(ctx, p):
    """Wide of the sunny autumn backyard; the fryer stands in the middle of the lawn with the turkey on the hoist
    above the pot (burner off). Slow push in. Anchor: fryer."""
    build_yard_world(ctx, p)
    fr = build_fryer(ctx, turkey=True)
    fx, fy = FRYER
    _anc(ctx, "fryer", (0.0, 0.0, POT_Z + POT_H), parent=fr["root"])
    _keys(ctx, p, (fx - 5.5, fy - 13.0, 2.9), (fx - 0.6, fy + 2.0, 1.9), (fx - 2.4, fy - 6.2, 1.85),
          (fx - 0.2, fy + 1.0, 1.2))


def b_yard_orbit(ctx, p):
    """Slow orbit around the fryer, the turkey hanging above the pot. Anchor: fryer."""
    T = ctx.frames
    build_yard_world(ctx, p)
    fr = build_fryer(ctx, turkey=True)
    fx, fy = FRYER
    _anc(ctx, "fryer", (0.0, 0.0, POT_Z + POT_H), parent=fr["root"])
    a0, a1 = math.radians(p.get("a0", -120.0)), math.radians(p.get("a1", -75.0))
    R, z = p.get("r", 3.6), p.get("z", 1.7)
    tgt = (fx, fy, 1.05)
    _cam(ctx, (fx + R * math.cos(a0), fy + R * math.sin(a0), z), tgt, p.get("lens", 30))
    keys = []
    for k in range(7):
        u = k / 6.0
        a = a0 + (a1 - a0) * u
        keys.append((1 + int((T - 1) * u), (fx + R * math.cos(a), fy + R * math.sin(a), z - 0.15 * u), tgt))
    A._cam_keys(ctx, keys, "LINEAR")


def _wisps(ctx, root, f0, T, n=6, z0=None, col="8f959b", size=0.05, rise=0.9, name="wisp"):
    m = ST.cloud_mat(name + "_m", 0.25, col)
    rng = random.Random(41)
    z0 = z0 if z0 is not None else POT_Z + POT_H
    for k in range(n):
        bl = [(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(-0.02, 0.04), size * rng.uniform(0.7, 1.2),
               0.8) for _ in range(4)]
        o = ST.puffs("%s%d" % (name, k), bl, m, parent=root)
        x, y = rng.uniform(-0.1, 0.1), rng.uniform(-0.02, 0.12)
        ST.loop_move(o, (x, y, z0), (x + rng.uniform(-0.15, 0.15), y + 0.1, z0 + rise), T, f0 + 6 * k,
                     70 + 8 * (k % 3), phase=rng.random(), grow=14)
        o.visible_shadow = False


def b_fryer_cut(ctx, p):
    """Wedge-cutaway close-up of the pot. See module docstring for the modes. Anchors: oil, burner, ice, pot."""
    T = ctx.frames
    mode = p.get("mode", "overfill")
    build_yard_world(ctx, p)
    fx, fy = FRYER
    top = POT_Z + POT_H
    if mode == "heat":
        fr = build_fryer(ctx, cut=True, turkey=False)
    else:
        fr = build_fryer(ctx, cut=True, turkey=True, turkey_z=1.45)
    root, oil = fr["root"], fr["oil"]
    gs, gs2 = fr["glow"]
    ld = fr["light"]
    b_s, e_s, sb_s, se_s = fr["oil_socks"]

    def glow_on(f, big=None):
        sock_keys(gs, [(1, 0.0), (f, 0.0), (f + 10, 2.2)])
        ld.energy = 0.0
        ld.keyframe_insert("energy", frame=1)
        ld.keyframe_insert("energy", frame=max(2, f))
        ld.energy = 60.0
        ld.keyframe_insert("energy", frame=f + 10)
        ff = f + 10
        while ff < T + 30:     # soft pulse
            L.kf_socket(gs, ff + 14, 1.6, "LINEAR")
            L.kf_socket(gs, ff + 28, 2.4, "LINEAR")
            ff += 28
        if big:
            sock_keys(gs2, [(1, 0.0), (big, 0.0), (big + 30, 1.5)])
            ld.energy = 60.0
            ld.keyframe_insert("energy", frame=big)
            ld.energy = 220.0
            ld.keyframe_insert("energy", frame=big + 30)
            ff = big + 30
            while ff < T + 30:
                L.kf_socket(gs2, ff + 15, 1.0, "LINEAR")
                L.kf_socket(gs2, ff + 30, 1.6, "LINEAR")
                ff += 30
        else:
            sock_keys(gs2, [(1, 0.0)])

    _anc(ctx, "pot", (POT_R * 0.7, 0.0, top), parent=root)
    _anc(ctx, "burner", (0.12, -0.12, 0.24), parent=root)
    lvl0 = POT_H * 0.55
    if mode == "overfill":
        f_l = ctx.word_time(p.get("lower_cue", "lower"), 0.3)
        f_s = ctx.word_time(p.get("spill_cue", "spill"), 0.55)
        f_b = ctx.word_time(p.get("big_cue", "large"), 0.85)
        f_full = max(f_l + 30, f_s - 6)
        lower_turkey(ctx.frames, fr["turkey"], fr["line"], [(1, 1.45), (f_l, 1.45), (f_full, POT_Z + 0.5)])
        set_keys(oil, "scale", [1, f_l + 8, f_full, f_s + 6],
                 [(1, 1, lvl0), (1, 1, lvl0), (1, 1, POT_H * 0.96), (1, 1, POT_H * 1.01)], "BEZIER")
        glow_on(1, big=f_b - 8)
        # oil ribbon down the outside of the pot (visible side) + drip onto the burner
        om, _, _ = oil_mat("fry_spill", "f2b12e", 0.4)
        ang = math.radians(-40.0)
        rib = []
        for k, (aa, dz, w) in enumerate(((ang, 0.0, 0.05), (ang - 0.35, 0.03, 0.035))):
            bm = bmesh.new()
            n = 10
            prev = None
            for i in range(n + 1):
                u = i / n
                a = aa + 0.08 * math.sin(u * 3.0)
                r = POT_R + 0.004 + (0.03 if u > 0.98 else 0.0)
                z = -u * (POT_H + 0.02)
                c = Vector((math.cos(a), math.sin(a), 0))
                t = Vector((-math.sin(a), math.cos(a), 0))
                pa = c * r + t * (w / 2 * (1 - 0.4 * u)) + Vector((0, 0, z))
                pb = c * r - t * (w / 2 * (1 - 0.4 * u)) + Vector((0, 0, z))
                va, vb = bm.verts.new(pa), bm.verts.new(pb)
                if prev:
                    bm.faces.new((prev[0], prev[1], vb, va))
                prev = (va, vb)
            o = S.obj("spill%d" % k, S.mesh_from_bm("spill%d" % k, bm, [om], smooth=True), (0, 0, top + 0.004),
                      parent=root)
            set_keys(o, "scale", [1, f_s + 2 + 6 * k, f_s + 26 + 6 * k], [(1, 1, 0), (1, 1, 0), (1, 1, 1)], "BEZIER")
            rib.append(o)
        # drops falling from the stand ring onto the burner
        dm, _, _ = oil_mat("fry_drop", "f2b12e", 0.5)
        for k in range(5):
            bm = bmesh.new()
            S._ellipsoid(bm, (0, 0, 0), (0.012, 0.012, 0.02), 0, 8, 6)
            d = S.obj("drop%d" % k, S.mesh_from_bm("drop%d" % k, bm, [dm], smooth=True), parent=root)
            a = ang + 0.1
            p0 = (math.cos(a) * (POT_R + 0.01), math.sin(a) * (POT_R + 0.01), POT_Z - 0.02)
            p1 = (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.25)
            ST.loop_move(d, p0, p1, T, f_s + 26 + 5 * k, 18, phase=k * 0.2, grow=3)
        _anc(ctx, "oil", (0.0, -POT_R * 0.55, POT_Z + lvl0 + 0.02), parent=root)
        a_o = ctx.anchors["oil"][0]
        set_keys(a_o, "location", [1, f_l + 8, f_full],
                 [(0.0, -POT_R * 0.55, POT_Z + lvl0), (0.0, -POT_R * 0.55, POT_Z + lvl0),
                  (0.0, -POT_R * 0.55, POT_Z + POT_H * 0.96)], "BEZIER")
    elif mode == "ice":
        f_i = ctx.word_time(p.get("ice_cue", "frozen"), 0.25)
        f_st = ctx.word_time(p.get("steam_cue", "flashes"), 0.55)
        f_o = ctx.word_time(p.get("out_cue", "shoves"), 0.8)
        lower_turkey(ctx.frames, fr["turkey"], fr["line"],
                     [(1, 1.45), (max(2, f_st - 40), 1.45), (f_st - 2, POT_Z + 0.6), (f_st + 40, POT_Z + 0.5)])
        set_keys(oil, "scale", [1, f_st, f_st + 14, f_o, f_o + 20, T],
                 [(1, 1, lvl0), (1, 1, lvl0), (1, 1, POT_H * 0.8), (1, 1, POT_H * 0.86), (1, 1, POT_H * 1.0),
                  (1, 1, POT_H * 0.92)], "BEZIER")
        glow_on(1)
        icem = S.emis("ice_m", hexc("9fe3ff"), 1.6)
        rng = random.Random(5)
        tk = fr["turkey"]
        steam = ST.cloud_mat("steam_m", 0.75, "ffffff")
        for k in range(8):
            x = rng.uniform(-0.12, 0.1)
            z = -0.455 + 0.1 + rng.uniform(-0.04, 0.07)
            loc = (x, -0.115 + 0.03 * abs(x) / 0.12, z)
            bm = bmesh.new()
            r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            bmesh.ops.scale(bm, vec=(0.018, 0.018, 0.035), verts=r["verts"])
            cr = S.obj("ice%d" % k, S.mesh_from_bm("ice%d" % k, bm, [icem]), loc, parent=tk)
            cr.rotation_euler = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, 3))
            set_keys(cr, "scale", [1, f_i, f_i + 8, f_st, f_st + 8],
                     [(0.6, 0.6, 0.6), (1, 1, 1), (1.3, 1.3, 1.3), (1.3, 1.3, 1.3), (0, 0, 0)], "BEZIER")
        # steam puffs rising out of the pot (world positions under root)
        for k in range(9):
            bl = [(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(0, 0.04), rng.uniform(0.05, 0.08),
                   0.85) for _ in range(5)]
            o = ST.puffs("steam%d" % k, bl, steam, parent=root)
            o.visible_shadow = False
            x, y = rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.1)
            f0 = f_st + 2 * k
            set_keys(o, "location", [1, f0, f0 + 30, f0 + 70],
                     [(x * 0.4, y * 0.4, top - 0.1), (x * 0.4, y * 0.4, top - 0.1), (x, y, top + 0.14),
                      (x * 1.6, y * 1.4 + 0.1, top + 0.27)], "BEZIER")
            set_keys(o, "scale", [1, f0, f0 + 25, f0 + 70, f0 + 100],
                     [(0, 0, 0), (0.2, 0.2, 0.2), (0.95, 0.95, 0.95), (1.1, 1.1, 1.1), (0, 0, 0)], "BEZIER")
        # golden droplets: bursts up and out of the pot (ballistic)
        dm, _, _ = oil_mat("fry_drop", "f5b52c", 0.6)
        g = 9.81 / (ctx.fps * ctx.fps)
        for burst, fb in enumerate((f_st + 6, f_o, f_o + 24)):
            for k in range(14):
                bm = bmesh.new()
                S._ellipsoid(bm, (0, 0, 0), (0.014, 0.014, 0.014), 0, 8, 6)
                d = S.obj("dr%d_%d" % (burst, k), S.mesh_from_bm("dr", bm, [dm], smooth=True), parent=root)
                d.visible_shadow = False
                a = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(0.02, 0.045)
                vz = rng.uniform(0.07, 0.11)
                x0, y0 = math.cos(a) * 0.1, math.sin(a) * 0.1
                fr_ = [1, fb]
                locs = [(x0, y0, top), (x0, y0, top)]
                for i in range(1, 40, 3):
                    z = top + vz * i - 0.5 * g * i * i
                    locs.append((x0 + math.cos(a) * sp * i, y0 + math.sin(a) * sp * i, max(0.02, z)))
                    fr_.append(fb + i)
                set_keys(d, "location", fr_, locs, "LINEAR")
                set_keys(d, "scale", [1, fb, fb + 1, fb + 36, fb + 40], [(0, 0, 0), (0, 0, 0), (1, 1, 1), (1, 1, 1),
                                                                      (0, 0, 0)], "LINEAR")
        _anc(ctx, "ice", (0.0, -0.12, -0.35), parent=tk)
        _anc(ctx, "oil", (0.0, -POT_R * 0.55, POT_Z + lvl0), parent=root)
    else:   # heat
        f_h = ctx.word_time(p.get("heat_cue", "leave"), 0.45)
        f_x = ctx.word_time(p.get("hot_cue", "hotter"), 0.7)
        set_keys(oil, "scale", [1], [(1, 1, POT_H * 0.62)], "CONSTANT")
        glow_on(1)
        for sk, (c0, c1) in ((b_s, ("f0b532", "9a4c12")), (e_s, ("f0b532", "7a3a0e")),
                             (sb_s, ("f6c046", "a8541a")), (se_s, ("f6c046", "8a4212"))):
            sock_keys(sk, [(1, hexc(c0)), (f_h, hexc(c0)), (f_x + 40, hexc(c1))])
        _wisps(ctx, root, f_x - 10, T, n=7, z0=POT_Z + POT_H * 0.62 + 0.02, rise=0.7, col="5f656b", size=0.035)
        # big friendly dial thermometer on a stem, left of the pot, facing the camera
        dial = L.link(bpy.data.objects.new("dial", None))
        dial.parent = root
        dial.location = (-0.42, 0.12, 1.02)
        dial.scale = (0.72, 0.72, 0.72)
        face = S.pbr("dial_face", hexc("f7f7f4"), 0.4, var=0)
        rim = S.pbr("dial_rim", hexc("c43b32"), 0.35, 0.3, var=0)
        bm = bmesh.new()
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.25, radius2=0.25, depth=0.05)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 1
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.22, radius2=0.22, depth=0.052)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.02, radius2=0.02, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0.04, -0.5), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 1
        S.obj("dial_body", S.mesh_from_bm("dial_body", bm, [face, rim]), parent=dial)
        # coloured arc (green -> amber -> red), sweeping from 220 deg to -40 deg (clockwise)
        for k, (c, a0, a1) in enumerate((("2fb65a", 220.0, 140.0), ("f0a628", 140.0, 60.0), ("e0362c", 60.0, -40.0))):
            bm = bmesh.new()
            n = 16
            prev = None
            for i in range(n + 1):
                a = math.radians(a0 + (a1 - a0) * i / n)
                v1 = bm.verts.new((0.17 * math.cos(a), -0.03, 0.17 * math.sin(a)))
                v2 = bm.verts.new((0.205 * math.cos(a), -0.03, 0.205 * math.sin(a)))
                if prev:
                    bm.faces.new((prev[0], prev[1], v2, v1))
                prev = (v1, v2)
            o = S.obj("arc%d" % k, S.mesh_from_bm("arc%d" % k, bm, [S.emis("arc_m%d" % k, hexc(c), 1.4)]), parent=dial)
            o.visible_shadow = False
        nd = L.link(bpy.data.objects.new("needle", None))
        nd.parent = dial
        nd.location = (0, -0.04, 0)
        bm = bmesh.new()
        S.bm_box(bm, (0.08, 0, 0), (0.17, 0.012, 0.022), 0)
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.025, radius2=0.025, depth=0.02)
        bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        S.obj("needle_m", S.mesh_from_bm("needle_m", bm, [S.pbr("needle_c", hexc("1f2a3a"), 0.4, var=0)]), parent=nd)
        # rotation about the dial's Y axis: angle a (CCW from +X seen from -Y) = rotation_y -a
        def ny(a):
            return (0.0, -math.radians(a), 0.0)
        set_keys(nd, "rotation_euler", [1, f_h, f_x, f_x + 50, T],
                 [ny(205.0), ny(190.0), ny(110.0), ny(10.0), ny(-20.0)], "BEZIER")
        _anc(ctx, "dial", (0.0, -0.03, 0.25), parent=dial)
        _anc(ctx, "oil", (0.0, -POT_R * 0.55, POT_Z + POT_H * 0.62), parent=root)
    c0 = (fx + p.get("cx", -0.12), fy - 2.05, 1.22)
    t0 = (fx - (0.18 if mode == "heat" else 0.0), fy, 0.74)
    c1 = (fx + p.get("cx", -0.12) + 0.1, fy - 1.85, 1.16)
    _keys(ctx, p, c0, t0, c1, t0, 30)


# ---------------------------------------------------------------- bathtub
def _rrect(w, d, rr, n=6):
    """Rounded rectangle outline (x, y) CCW, n verts per corner."""
    pts = []
    for cx, cy, a0 in ((w / 2 - rr, d / 2 - rr, 0), (-w / 2 + rr, d / 2 - rr, 90), (-w / 2 + rr, -d / 2 + rr, 180),
                       (w / 2 - rr, -d / 2 + rr, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def b_bathtub_v2(ctx, p):
    """A toy-like clawfoot bathtub on the lawn, brim-full of blue water; a rubber duck drops in on `step_cue` and
    water sloshes over both long sides; the water turns gold on `oil_cue`; a soft orange glow under the tub on
    `flame_cue` (no flame shapes). Anchor: tub."""
    T = ctx.frames
    build_yard_world(ctx, p)
    bx, by = p.get("x", -4.0), p.get("y", -9.0)
    root = L.link(bpy.data.objects.new("tub", None))
    root.location = (bx, by, 0.0)
    enamel = S.pbr("tub_enamel", hexc("f7f5f0"), 0.18, var=0.01)
    outer = S.pbr("tub_outer", hexc("4f86b8"), 0.3, 0.1, var=0.02)
    gold = S.pbr("tub_feet", hexc("d6a93a"), 0.3, 0.9, var=0)
    W, D, Z0, Z1 = 1.7, 0.78, 0.18, 0.72
    bm = bmesh.new()
    rings = []
    for k, (z, s) in enumerate(((Z0, 0.86), (Z0 + 0.2, 0.96), (Z1, 1.0))):
        rings.append([(x * s, y * s, z) for x, y in _rrect(W, D, 0.33)])
    inner = [[(x * s, y * s, z) for x, y in _rrect(W - 0.1, D - 0.1, 0.29)] for z, s in ((Z1, 1.0), (Z0 + 0.06, 0.82))]
    from scene_lib_v2_sea import _loft
    vr = _loft(bm, rings, cap0=True, cap1=False)
    vi = _loft(bm, inner, cap0=False, cap1=True)
    n = len(vr[-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vr[-1][i], vr[-1][j], vi[0][j], vi[0][i]))
    for f in bm.faces:
        f.material_index = 0 if f.calc_center_median().z > Z1 - 0.01 or f.normal.z > 0.5 else 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        c = f.calc_center_median()
        inside = (abs(c.x) < (W - 0.12) / 2 and abs(c.y) < (D - 0.12) / 2 and c.z > Z0 + 0.05)
        f.material_index = 0 if inside or c.z > Z1 - 0.005 else 1
    S.obj("tub_body", S.mesh_from_bm("tub_body", bm, [enamel, outer], smooth=True), parent=root)
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            S._ellipsoid(bm, (sx * 0.6, sy * 0.24, 0.1), (0.06, 0.06, 0.11), 0, 10, 8)
    S.obj("tub_feet", S.mesh_from_bm("tub_feet", bm, [gold], smooth=True), parent=root)
    # water: rounded slab, top at the brim
    wm, base_s, em_s = oil_mat("tub_water", "3d9be0", 0.25)
    bm = bmesh.new()
    top = [bm.verts.new((x * 0.995, y * 0.995, Z1 - 0.012)) for x, y in _rrect(W - 0.1, D - 0.1, 0.29)]
    bm.faces.new(top)
    S.obj("tub_water", S.mesh_from_bm("tub_water", bm, [wm]), parent=root)
    f_st = ctx.word_time(p.get("step_cue", "step"), 0.3)
    f_oil = ctx.word_time(p.get("oil_cue", "picture"), 0.6)
    f_fl = ctx.word_time(p.get("flame_cue", "flame"), 0.85)
    for sk, c1 in ((base_s, "f0b532"), (em_s, "f6b52e")):
        sock_keys(sk, [(1, hexc("3d9be0")), (f_oil, hexc("3d9be0")), (f_oil + 20, hexc(c1))])
    # rubber duck
    duck = L.link(bpy.data.objects.new("duck", None))
    duck.parent = root
    ym = S.pbr("duck_y", hexc("ffd52e"), 0.3, var=0)
    om = S.pbr("duck_o", hexc("ff8a1e"), 0.35, var=0)
    km = S.pbr("duck_k", hexc("1b1b1b"), 0.2, var=0)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 0.07), (0.13, 0.1, 0.08), 0, 16, 10)
    S._ellipsoid(bm, (0.08, 0, 0.17), (0.065, 0.065, 0.065), 0, 14, 10)
    S._ellipsoid(bm, (0.15, 0, 0.16), (0.04, 0.025, 0.012), 1, 10, 6)
    for sy in (-1, 1):
        S._ellipsoid(bm, (0.12, sy * 0.04, 0.19), (0.012, 0.012, 0.012), 2, 8, 6)
    S.obj("duck_b", S.mesh_from_bm("duck_b", bm, [ym, om, km], smooth=True), parent=duck)
    duck.scale = (1.6, 1.6, 1.6)
    zw = Z1 - 0.05
    set_keys(duck, "location", [1, f_st - 14, f_st, f_st + 8, f_st + 18, f_st + 30],
             [(0.2, 0.0, 1.6), (0.2, 0.0, 1.6), (0.2, 0.0, zw - 0.06), (0.2, 0.0, zw + 0.03), (0.2, 0.0, zw - 0.01),
              (0.2, 0.0, zw)], "BEZIER")
    set_keys(duck, "rotation_euler", [1, f_st, f_st + 40, T], [(0, 0, 0.3), (0, 0, 0.3), (0, 0, -0.1), (0, 0, 0.2)],
             "BEZIER")
    # splash ring + overflow sheets down both long sides + puddles on the lawn
    sheet_m = water_sheet_mat(base_s, f_oil)
    for sy in (-1, 1):
        bm = bmesh.new()
        n = 8
        prev = None
        for i in range(n + 1):
            u = i / n
            y = sy * (D / 2 + 0.01 + 0.05 * u)
            z = -u * (Z1 - 0.02)
            va = bm.verts.new((-0.38, y, z))
            vb = bm.verts.new((0.38, y, z))
            if prev:
                bm.faces.new((prev[0], prev[1], vb, va) if sy > 0 else (prev[1], prev[0], va, vb))
            prev = (va, vb)
        sh = S.obj("sheet%d" % sy, S.mesh_from_bm("sheet", bm, [sheet_m], smooth=True), (0, 0, Z1), parent=root)
        set_keys(sh, "scale", [1, f_st + 2, f_st + 16, f_st + 60, f_st + 90],
                 [(1, 1, 0), (1, 1, 0), (1, 1, 1), (1, 1, 1), (1, 1, 0.0)], "BEZIER")
        bm = bmesh.new()
        r = bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=1.0)
        bmesh.ops.scale(bm, vec=(0.8, 0.35, 1), verts=bm.verts[:])
        pu = S.obj("puddle%d" % sy, S.mesh_from_bm("puddle", bm, [wm]), (0, sy * (D / 2 + 0.3), 0.015), parent=root)
        set_keys(pu, "scale", [1, f_st + 12, f_st + 50], [(0, 0, 1), (0.1, 0.1, 1), (1, 1, 1)], "BEZIER")
    sp = ST.cloud_mat("tub_spray", 0.6, "e8f4ff")
    rng = random.Random(8)
    for k in range(12):
        bm = bmesh.new()
        S._ellipsoid(bm, (0, 0, 0), (0.025, 0.025, 0.025), 0, 8, 6)
        d = S.obj("spr%d" % k, S.mesh_from_bm("spr", bm, [sp], smooth=True), parent=root)
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(0.02, 0.035)
        fr_, locs = [1, f_st], [(0.2, 0, zw), (0.2, 0, zw)]
        for i in range(1, 28, 3):
            fr_.append(f_st + i)
            locs.append((0.2 + math.cos(a) * v * i, math.sin(a) * v * i * 0.6,
                         max(0.02, zw + 0.06 * i - 0.5 * 0.0109 * i * i)))
        set_keys(d, "location", fr_, locs, "LINEAR")
        set_keys(d, "scale", [1, f_st, f_st + 1, f_st + 24, f_st + 28], [(0, 0, 0), (0, 0, 0), (1, 1, 1), (1, 1, 1),
                                                                      (0, 0, 0)], "LINEAR")
    # glow under the tub
    g, gs = glow_disc("tub_glow", (0, 0, 0.03), 0.9)
    g.parent = root
    g.scale = (1.0, 0.55, 1.0)
    lo, ld = point_light("tub_light", (0, 0, 0.12), 0.0)
    lo.parent = root
    sock_keys(gs, [(1, 0.0), (f_fl, 0.0), (f_fl + 14, 1.1)])
    ff = f_fl + 14
    while ff < T + 30:
        L.kf_socket(gs, ff + 14, 0.7, "LINEAR")
        L.kf_socket(gs, ff + 28, 1.1, "LINEAR")
        ff += 28
    ld.keyframe_insert("energy", frame=1)
    ld.keyframe_insert("energy", frame=max(2, f_fl))
    ld.energy = 90.0
    ld.keyframe_insert("energy", frame=f_fl + 14)
    _anc(ctx, "tub", (0.0, 0.0, Z1), parent=root)
    _keys(ctx, p, (bx - 1.3, by - 5.2, 2.3), (bx, by, 0.55), (bx - 0.8, by - 4.4, 2.0), (bx, by, 0.52), 30)


# ---------------------------------------------------------------- top view
def _no_ring(name, loc, r, f_on, col="ff2a2a", slash=True):
    m, sock = L.add_mat(name, hexc(col), 0.0)
    bm = bmesh.new()
    C._annulus(bm, r, r * 0.14, 72)
    if slash:
        vs = S.bm_box(bm, (0, 0, 0), (r * 1.85, r * 0.13, 0.01), 0)
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(45), 3, "Z"))
    o = S.obj(name, S.mesh_from_bm(name, bm, [m]), loc)
    o.visible_shadow = False
    sock_keys(sock, [(1, 0.0), (f_on, 0.0), (f_on + 8, 5.0)])
    f = f_on + 8
    while f < 2000:
        L.kf_socket(sock, f + 15, 3.0, "LINEAR")
        L.kf_socket(sock, f + 30, 5.0, "LINEAR")
        f += 30
        if f > f_on + 900:
            break
    set_keys(o, "scale", [1, f_on, f_on + 10], [(0.6, 0.6, 1), (0.6, 0.6, 1), (1, 1, 1)], "BEZIER")
    return o


def b_yard_top(ctx, p):
    """High view over the yard: red 'no' rings over the garage (`garage_cue`) and the wooden deck (`deck_cue`),
    green ring around the fryer on the open lawn (`ok_cue`). Anchors: garage, deck, lawn."""
    w = build_yard_world(ctx, p)
    fr = build_fryer(ctx, turkey=False)
    f_g = ctx.word_time(p.get("garage_cue", "garage"), 0.45)
    f_d = ctx.word_time(p.get("deck_cue", "deck"), 0.6)
    f_ok = ctx.word_time(p.get("ok_cue", "spilled"), 0.75)
    gx, gy, gz = w["garage"]
    _no_ring("no_garage", (gx, gy, gz + 0.4), 3.6, f_g)
    dx, dy, dz = w["deck"]
    _no_ring("no_deck", (dx, dy, dz + 0.25), 3.3, f_d)
    _no_ring("ok_lawn", (FRYER[0], FRYER[1], 0.06), 2.6, f_ok, "33d17a", slash=False)
    _anc(ctx, "garage", (gx, gy + 1.0, gz + 0.4))
    _anc(ctx, "deck", (dx, dy - 1.0, dz + 0.3))
    _anc(ctx, "lawn", (FRYER[0], FRYER[1] - 2.6, 0.1))
    _keys(ctx, p, (5.0, -12.0, 36.0), (5.0, 6.0, 0.0), (5.0, -10.8, 33.0), (5.0, 6.0, 0.0), 20, 0.5)


# ---------------------------------------------------------------- takeaway
def standing_person(name):
    """Faceless mannequin standing with arms down (same look as the tightrope walker, no pole)."""
    root = L.link(bpy.data.objects.new(name, None))
    skin = S.pbr("mq_skin", hexc("d9d4cc"), 0.5, var=0)
    top = S.pbr("mq_top_b", hexc("2f6fb3"), 0.6, var=0.04)
    trs = S.pbr("mq_trousers", hexc("3b4456"), 0.7, var=0.04)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 1.32), (0.22, 0.15, 0.36), 0, 16, 10)
    S._ellipsoid(bm, (0, 0, 1.03), (0.2, 0.14, 0.14), 1, 12, 8)
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 0.1, 0, 0.5), (0.08, 0.08, 0.5), 1, 10, 8)
        S._ellipsoid(bm, (sx * 0.27, 0.0, 1.25), (0.06, 0.06, 0.3), 0, 10, 6)
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, [top, trs], smooth=True), parent=root)
    bm = bmesh.new()
    S._ellipsoid(bm, (0, 0, 1.86), (0.12, 0.13, 0.15), 0, 16, 10)
    S._ellipsoid(bm, (0, 0, 1.69), (0.05, 0.05, 0.06), 0, 8, 6)
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 0.29, 0.0, 0.9), (0.045, 0.045, 0.1), 0, 8, 6)
    S.obj(name + "_skin", S.mesh_from_bm(name + "_skin", bm, [skin], smooth=True), parent=root)
    return root


def side_table(name, loc, h=0.75, w=0.8, d=0.5):
    m = S.pbr("table_top", hexc("eceae4"), 0.5, var=0.02)
    lg = S.pbr("table_leg", hexc("3a3d42"), 0.4, 0.6, var=0)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, h - 0.02), (w, d, 0.04), 0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            S.bm_box(bm, (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), (h - 0.04) / 2), (0.03, 0.03, h - 0.04), 1)
    return S.obj(name, S.mesh_from_bm(name, bm, [m, lg]), loc)


def b_yard_safe(ctx, p):
    """Takeaway: the fryer far out on the open lawn; on cues: thawed bird on a tray (teal ring), a teal fill-line
    band around the pot, a green ring on the lawn, a person standing watch, an oil-free electric fryer slides onto
    a second table. Anchors: fryer, bird, person, electric."""
    T = ctx.frames
    build_yard_world(ctx, p)
    fr = build_fryer(ctx, turkey=False)
    root = fr["root"]
    fx, fy = FRYER
    f_th = ctx.word_time(p.get("thaw_cue", "thaw"), 0.05)
    f_te = ctx.word_time(p.get("test_cue", "test"), 0.25)
    f_fr = ctx.word_time(p.get("fry_cue", "outside"), 0.45)
    f_w = ctx.word_time(p.get("watch_cue", "never"), 0.7)
    f_e = ctx.word_time(p.get("free_cue", "choose"), 0.85)
    # 1 thawed bird on a tray
    side_table("tbl1", (fx + 1.4, fy - 0.6, 0.0))
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0.0), (0.5, 0.36, 0.03), 0)
    tray = S.obj("tray", S.mesh_from_bm("tray", bm, [steel_mat()]), (fx + 1.4, fy - 0.6, 0.765))
    bird = L.link(bpy.data.objects.new("bird", None))
    bird.location = (fx + 1.4, fy - 0.6, 0.78)
    bm = bmesh.new()
    bird_mesh(bm, 0.0)
    S.obj("bird_b", S.mesh_from_bm("bird_b", bm, [turkey_mats(), S.pbr("turkey_bone", hexc("f2ead8"), 0.5, var=0)],
                                   smooth=True), parent=bird)
    set_keys(bird, "scale", [1, f_th, f_th + 10], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "BEZIER")
    set_keys(tray, "scale", [1, f_th, f_th + 8], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "BEZIER")
    _no_ring("ring_thaw", (fx + 1.4, fy - 0.6, 0.05), 0.75, f_th, "19c9b4", slash=False)
    # 2 fill-line band (teal) around the pot + a water jug
    m, sock = L.add_mat("fill_band", hexc("19c9b4"), 0.0)
    bm = bmesh.new()
    n = 64
    prev = None
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        va = bm.verts.new(((POT_R + 0.006) * math.cos(a), (POT_R + 0.006) * math.sin(a), -0.012))
        vb = bm.verts.new(((POT_R + 0.006) * math.cos(a), (POT_R + 0.006) * math.sin(a), 0.012))
        if prev:
            bm.faces.new((prev[0], va, vb, prev[1]))
        prev = (va, vb)
    band = S.obj("fill_band", S.mesh_from_bm("fill_band", bm, [m]), (0, 0, POT_Z + POT_H * 0.62), parent=root)
    band.visible_shadow = False
    sock_keys(sock, [(1, 0.0), (f_te, 0.0), (f_te + 8, 4.0)])
    # 3 green ring: open lawn, level ground
    _no_ring("ok_lawn", (fx, fy, 0.05), 2.4, f_fr, "33d17a", slash=False)
    # 4 a person standing watch (walks in from the left)
    pr = standing_person("watcher")
    set_keys(pr, "location", [1, f_w - 30, f_w + 6], [(fx - 3.0, fy + 1.6, 0.0), (fx - 3.0, fy + 1.6, 0.0),
                                                    (fx - 0.95, fy + 0.45, 0.0)], "BEZIER")
    pr.rotation_euler = (0, 0, math.radians(-75))
    # 5 oil-free electric fryer slides onto a second table
    side_table("tbl2", (fx - 1.6, fy - 1.0, 0.0))
    ef = L.link(bpy.data.objects.new("efryer", None))
    wh = S.pbr("ef_body", hexc("f2f3f4"), 0.3, 0.1, var=0.01)
    blk = S.pbr("ef_lid", hexc("2c2f34"), 0.3, 0.3, var=0)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.2, radius2=0.18, depth=0.3)
    bmesh.ops.translate(bm, vec=(0, 0, 0.15), verts=r["verts"])
    S._ellipsoid(bm, (0, 0, 0.3), (0.18, 0.18, 0.06), 1, 24, 8)
    S.bm_box(bm, (0, -0.2, 0.16), (0.08, 0.02, 0.08), 1)
    S.obj("ef_b", S.mesh_from_bm("ef_b", bm, [wh, blk], smooth=True), parent=ef)
    set_keys(ef, "location", [1, f_e, f_e + 18], [(fx - 3.2, fy - 1.0, 0.76), (fx - 3.2, fy - 1.0, 0.76),
                                                (fx - 1.6, fy - 1.0, 0.76)], "BEZIER")
    set_keys(ef, "scale", [1, f_e - 1, f_e], [(0, 0, 0), (0, 0, 0), (1, 1, 1)], "CONSTANT")
    _no_ring("ring_ef", (fx - 1.6, fy - 1.0, 0.05), 0.7, f_e + 10, "19c9b4", slash=False)
    _anc(ctx, "fryer", (0.0, 0.0, POT_Z + POT_H), parent=root)
    _keys(ctx, p, (fx - 0.4, fy - 10.5, 2.9), (fx, fy, 0.9), (fx - 0.2, fy - 9.6, 2.7), (fx, fy, 0.88), 30)


# ---------------------------------------------------------------- outro
def b_yard_outro(ctx, p):
    """Thanksgiving table on the patio (white cloth, plates, roast turkey on a platter, small pumpkins, chairs) in
    warm light; the camera starts on the table and cranes up over the yard. Anchor: table."""
    T = ctx.frames
    build_yard_world(ctx, p)
    build_fryer(ctx, turkey=False)
    tx, ty = TABLE
    cloth = S.pbr("cloth", hexc("f7f4ec"), 0.75, var=0.02)
    wood = wood_mat("chair_wood", "8a5a36", 0.08, "Z")
    plate = S.pbr("plate", hexc("ffffff"), 0.25, var=0)
    roast = S.pbr("roast", hexc("b8692a"), 0.35, var=0.12, var_scale=10.0, bump=0.08)
    pump = S.pbr("pumpkin", hexc("e67a1f"), 0.5, var=0.08, bump=0.06)
    green = S.pbr("greens", hexc("4f8a3c"), 0.7, var=0.1)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0.74), (2.2, 1.05, 0.04), 0)
    S.bm_box(bm, (0, 0, 0.62), (2.24, 1.09, 0.24), 0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            S.bm_box(bm, (sx * 1.0, sy * 0.42, 0.25), (0.06, 0.06, 0.5), 1)
    for k in range(6):
        x = -0.75 + 0.75 * (k % 3)
        y = 0.32 if k < 3 else -0.32
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.12, radius2=0.14, depth=0.02)
        bmesh.ops.translate(bm, vec=(x, y, 0.77), verts=r["verts"])
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = 2
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.24, radius2=0.28, depth=0.03)
    bmesh.ops.translate(bm, vec=(0, 0, 0.775), verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 2
    bm2 = bmesh.new()
    bird_mesh(bm2, 0.79, 0, 1)
    rb = S.obj("roast_bird", S.mesh_from_bm("roast_bird", bm2, [roast, S.pbr("turkey_bone", hexc("f2ead8"), 0.5, var=0)],
                                             smooth=True), (tx, ty, 0.0))
    rb.scale = (1.25, 1.25, 1.25)
    rb.location.z = -0.79 * 0.25
    for x, y, s in ((-0.55, 0.0, 0.07), (0.6, 0.05, 0.06), (0.45, -0.08, 0.045)):
        S._ellipsoid(bm, (x, y, 0.79 + s * 0.7), (s, s, s * 0.75), 4, 14, 8)
    for k in range(8):
        S._ellipsoid(bm, (-0.3 + 0.08 * k, 0.12 * math.sin(k), 0.79), (0.05, 0.03, 0.02), 5, 8, 6)
    S.obj("table", S.mesh_from_bm("table", bm, [cloth, S.pbr("tleg", hexc("6a4a32"), 0.6, var=0), plate, roast, pump,
                                                green], smooth=False), (tx, ty, 0.0))
    for k in range(6):
        x = tx - 0.75 + 0.75 * (k % 3)
        sy = 1 if k < 3 else -1
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0.45), (0.42, 0.42, 0.05), 0)
        S.bm_box(bm, (0, sy * 0.19, 0.75), (0.42, 0.04, 0.6), 0)
        for ax in (-1, 1):
            for ay in (-1, 1):
                S.bm_box(bm, (ax * 0.18, ay * 0.18, 0.22), (0.04, 0.04, 0.45), 0)
        S.obj("chair%d" % k, S.mesh_from_bm("chair", bm, [wood]), (x, ty + sy * 0.78, 0.0))
    # warm light
    lo = A._area("warm_key", (tx - 3.0, ty - 3.0, 4.0), 4.0, 900.0, (1.0, 0.78, 0.55))
    lo.rotation_euler = (math.radians(50), 0, math.radians(-45))
    _anc(ctx, "table", (0.0, 0.0, 0.9))
    ctx.anchors["table"][0].location = (tx, ty, 0.9)
    _keys(ctx, p, (tx + 2.9, ty - 1.3, 1.65), (tx, ty, 0.82), (tx + 4.0, ty - 15.0, 6.5), (tx + 1.5, ty + 3.0, 0.8), 30)


S.V2_BUILDERS.update({
    "yard_hook": b_yard_hook,
    "yard_orbit": b_yard_orbit,
    "fryer_cut": b_fryer_cut,
    "bathtub_v2": b_bathtub_v2,
    "yard_top": b_yard_top,
    "yard_safe": b_yard_safe,
    "yard_outro": b_yard_outro,
})

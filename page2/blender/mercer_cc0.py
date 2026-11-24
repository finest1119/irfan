"""Session 6 look upgrade for Mercer Hollow: CC0 trees/grass/rocks/shrubs (Poly Haven), Kenney props, 2K PBR
surfaces, a readable cable cut-away, a real dusk sky and a better pickup. Needs bpy.

world_mercer calls into this module at a few hooks; every function returns None/0 when the CC0 library
(assets/cc0/lib/mercer_cc0_lib.blend, built by cc0_lib.py) or a texture is missing, and the world keeps the old
procedural pieces. Nothing here changes camera, plan, anchors or event timing.
"""
import math
import random

import bpy
import bmesh

import cc0_lib as C
import mh_blender as B
from mh_blender import S, L, hexc

TREE_MAP = {("oak", 0): "cc0_broadleaf_lod0", ("oak", 1): "cc0_broadleaf_lod1",
            ("maple", 0): "cc0_broadleaf_lod0", ("maple", 1): "cc0_broadleaf_lod1",
            ("pine", 0): "cc0_pine_lod0", ("pine", 1): "cc0_pine_lod1"}


def enabled():
    return C.available()


# ---------------------------------------------------------------- trees
def tree_templates():
    if not enabled():
        return None
    out = {}
    for k, n in TREE_MAP.items():
        o = C.get(n)
        if o is None:
            return None
        out[k] = o
    return out


def hero_oak(x, y, z0, swing):
    """The yard oak: a big Poly Haven broadleaf + the old limb that carries the tire-swing rope."""
    o = C.place("cc0_broadleaf_lod0", (x, y, z0 - 0.15), 0.6, (1.45, 1.45, 1.35))
    if o is None:
        return None
    o.name = "mh_oak_cc0"
    bark = S.pbr("mh_bark", hexc("5a4632"), 0.9, var=0.12, var_scale=3.0, bump=0.35)
    bm = bmesh.new()
    bx_, by_ = swing[0] - x, swing[1] - y
    B.bm_cyl(bm, (0, 0, 3.2), (bx_ * 0.55, by_ * 0.55, 4.6), 0.2, 0.15, 8, 0)
    B.bm_cyl(bm, (bx_ * 0.55, by_ * 0.55, 4.6), (bx_ * 1.2, by_ * 1.2, 5.05), 0.15, 0.08, 8, 0)
    B.mesh_obj("mh_oak_swing_limb", bm, [bark], smooth=True, loc=(x, y, z0))
    return o


# ---------------------------------------------------------------- grass / plants / rocks scatter
GRASS = ("cc0_grass_a", "cc0_grass_b", "cc0_grass_c", "cc0_grass_d", "cc0_grass_e", "cc0_tuft_a", "cc0_tuft_b")
GRASS_W = (0.16, 0.2, 0.2, 0.16, 0.1, 0.1, 0.08)
PLANTS = ("cc0_plant_a", "cc0_plant_b", "cc0_plant_c", "cc0_groundcover")


def grass(H, focus, blocked, radius=16.0, per_focus=1500, seed=3):
    """Small realistic clumps near the camera points only (dense close, thinning out to `radius`)."""
    if not enabled():
        return 0
    tpl = {n: C.get(n) for n in GRASS + PLANTS}
    if any(v is None for v in tpl.values()):
        return 0
    rng = random.Random(seed)
    buckets = {n: ([], [], []) for n in tpl}
    seen = set()
    for (fx, fy) in focus:
        for _ in range(per_focus):
            a = rng.uniform(0, 6.283)
            r = radius * (rng.random() ** 1.35)          # denser near the focus
            x, y = fx + r * math.cos(a), fy + r * math.sin(a)
            key = (int(x * 3.0), int(y * 3.0))
            if key in seen or blocked(x, y):
                continue
            seen.add(key)
            n = rng.choices(GRASS, GRASS_W)[0]      # (s6 stills: broad-leaf plants blocked close-ups -> grass only)
            pts, rots, scl = buckets[n]
            pts.append((x, y, H(x, y) - 0.02))
            rots.append(rng.uniform(0, 6.283))
            scl.append(rng.uniform(0.75, 1.35))
    total = 0
    for n, (pts, rots, scl) in buckets.items():
        if pts:
            B.scatter_gn("mh_cc0_" + n, tpl[n], pts, rots, scl)
            total += len(pts)
    return total


ROCKS = ("cc0_rock_a", "cc0_rock_b", "cc0_rock_c", "cc0_rock_d", "cc0_pebble")


def creek_rocks(H, creek_x, skip, n=220, seed=5):
    if not enabled():
        return 0
    tpl = {k: C.get(k) for k in ROCKS}
    if any(v is None for v in tpl.values()):
        return 0
    rng = random.Random(seed)
    buckets = {k: ([], [], []) for k in tpl}
    for _ in range(n):
        y = rng.uniform(-95, 105)
        if skip(y):
            continue
        side = rng.choice((-1, 1))
        x = creek_x(y) + side * rng.uniform(1.3, 3.2)
        k = rng.choices(ROCKS, (0.22, 0.22, 0.22, 0.22, 0.12))[0]
        pts, rots, scl = buckets[k]
        pts.append((x, y, H(x, y) - 0.12))
        rots.append(rng.uniform(0, 6.283))
        scl.append(rng.uniform(0.45, 1.25) * (1.0 if k != "cc0_pebble" else 1.4))
    total = 0
    for k, (pts, rots, scl) in buckets.items():
        if pts:
            B.scatter_gn("mh_cc0_" + k, tpl[k], pts, rots, scl)
            total += len(pts)
    return total


def shrubs(H, spots, seed=9):
    """Foundation shrubs / fence-corner bushes: spots = [(x, y, kind)] kind in big|plant."""
    if not enabled():
        return 0
    rng = random.Random(seed)
    n = 0
    for x, y, kind in spots:
        name = rng.choice(("cc0_shrub_big_a", "cc0_shrub_big_b", "cc0_shrub_big_c")) if kind == "big" else \
            rng.choice(("cc0_plant_a", "cc0_plant_b", "cc0_plant_c"))
        s = rng.uniform(0.55, 0.8) if kind == "big" else rng.uniform(1.0, 1.5)
        if C.place(name, (x, y, H(x, y) - 0.03), rng.uniform(0, 6.283), s) is not None:
            n += 1
    return n


# ---------------------------------------------------------------- PBR surfaces
def surfaces(world):
    """Swap the flat/band materials for 2K Poly Haven PBR sets (box-projected, so no UVs needed)."""
    if not enabled():
        return {}
    done = {}
    siding = C.ph_mat("mh_cc0_siding", "white_planks_clean", 1.6, tint=hexc("f6f3ec"), normal=0.9,
                       walls_horizontal=True)
    done["siding"] = C.swap_material("mh_siding", siding)
    roof = C.ph_mat("mh_cc0_roof", "grey_roof_01", 2.2, normal=1.0)
    done["roof"] = C.swap_material("mh_shingles", roof)
    gravel = C.ph_mat("mh_cc0_gravel", "gravel_road", 2.5, normal=0.8, max_px=1024)
    done["gravel"] = C.swap_material("mh_gravel", gravel)
    drive = C.ph_mat("mh_cc0_driveway", "grooved_concrete_driveway", 3.0, tint=hexc("e8e4dc"), normal=0.6,
                      max_px=1024)
    if drive is not None:
        n = 0
        for oname in ("mh_driveway", "mh_walk"):
            o = bpy.data.objects.get(oname)
            if o is not None and o.type == "MESH":
                o.data = o.data.copy()
                for i in range(len(o.data.materials)):
                    o.data.materials[i] = drive
                    n += 1
        done["driveway"] = n
    return done


def creek_bed(H, creek_x, bed, fall_bot_z):
    """River-pebble ribbon under the creek water (seen through it), following the creek centre line."""
    m = C.ph_mat("mh_cc0_riverbed", "river_small_rocks", 1.8, normal=1.0, max_px=1024) if enabled() else None
    if m is None:
        return None
    bm = bmesh.new()
    prev = None
    for k in range(0, 211):
        y = 110.0 - k
        cx = creek_x(y)
        z = max(bed(y) + 0.06, min(H(cx, y) + 0.02, bed(y) + 0.25))
        if 33.0 < y < 36.5:
            prev = None
            continue
        row = [bm.verts.new((cx - 2.1, y, z + 0.04)), bm.verts.new((cx, y, z)), bm.verts.new((cx + 2.1, y, z + 0.04))]
        if prev:
            bm.faces.new((prev[0], prev[1], row[1], row[0]))
            bm.faces.new((prev[1], prev[2], row[2], row[1]))
        prev = row
    return B.mesh_obj("mh_creek_bed", bm, [m], smooth=True)


# ---------------------------------------------------------------- props (Kenney)
def _fit(name, loc, rot_z, height=None, width=None):
    """Place a Kenney template scaled so its height (or width) matches; loc = bottom centre."""
    tpl = C.get(name)
    if tpl is None:
        return None
    xs = [v.co.x for v in tpl.data.vertices]
    ys = [v.co.y for v in tpl.data.vertices]
    zs = [v.co.z for v in tpl.data.vertices]
    h = max(zs) - min(zs)
    w = max(max(xs) - min(xs), 1e-3)
    s = 1.0
    if height:
        s = height / max(h, 1e-3)
    elif width:
        s = width / w
    o = C.place(name, (0, 0, 0), rot_z, s)
    cx, cy = (max(xs) + min(xs)) / 2 * s, (max(ys) + min(ys)) / 2 * s
    c, sn = math.cos(rot_z), math.sin(rot_z)
    o.location = (loc[0] - (cx * c - cy * sn), loc[1] - (cx * sn + cy * c), loc[2] - min(zs) * s)
    return o


def kitchen_props(kx, y1, zf):
    """Kenney furniture in the kitchen nook (behind the north kitchen window; fronts face +Y, the window)."""
    if not enabled():
        return 0
    bd = bpy.data.objects.get("mh_kitchen_backdrop")
    if bd is not None:                 # drop the old block cabinets / fridge / lamp (mats 1 cab, 3 fridge, 4 shade)
        bm = bmesh.new()
        bm.from_mesh(bd.data)
        dead = [f for f in bm.faces if f.material_index in (1, 3, 4) or
                (f.material_index == 2 and f.calc_center_median().z > zf + 0.3)]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(bd.data)
        bm.free()
    yb = y1 - 2.6
    face = math.pi                      # Kenney fronts face -Y after import -> turn to face +Y
    row = [("k_cabinet_drawer", -1.6), ("k_sink", -0.85), ("k_cabinet", -0.1), ("k_stove", 0.65)]
    n = 0
    for name, dx in row:
        if _fit(name, (kx + dx, yb + 0.42, zf), face, height=0.92):
            n += 1
    if _fit("k_fridge", (kx + 1.5, yb + 0.45, zf), face, height=1.8):
        n += 1
    for dx in (-1.25, -0.1):
        if _fit("k_upper", (kx + dx, yb + 0.22, zf + 1.55), face, height=0.72):
            n += 1
    for name, dx, h in (("k_coffee", -1.75, 0.32), ("k_toaster", 0.1, 0.2), ("k_plant", -0.45, 0.3), ("k_radio", 0.3, 0.2)):
        if _fit(name, (kx + dx, yb + 0.4, zf + 0.92), face, height=h):
            n += 1
    if _fit("k_stool", (kx - 0.5, yb + 1.5, zf), 0.0, height=0.75):
        n += 1
    return n


def shed_props(shx, sy0, sy1):
    """Kenney survival-kit props in the open-front battery shed (the battery rack stays the hero)."""
    if not enabled():
        return 0
    n = 0
    for name, x, y, h, r in (("k_barrel", shx - 2.45, sy0 + 0.75, 0.9, 0.3), ("k_bucket", shx - 2.5, sy0 + 1.7, 0.36, 0.0),
                             ("k_crate", shx + 2.35, sy0 + 0.8, 0.6, 0.2), ("k_crate_small", shx + 2.4, sy0 + 0.8 + 0.0, 0.35, 0.6),
                             ("k_box_open", shx + 2.3, sy0 + 1.8, 0.45, -0.3)):
        z = 0.1 + (0.6 if name == "k_crate_small" else 0.0)
        if _fit(name, (x, y, z), r, height=h):
            n += 1
    o = _fit("k_shovel", (shx - 2.75, sy1 - 0.3, 0.1), 0.0, height=1.3)
    if o is not None:
        o.rotation_euler = (0.25, 0.0, 0.0)
        n += 1
    return n


# ---------------------------------------------------------------- cut-away section look
def section_materials():
    """Readable soil layers (topsoil / clay subsoil / gravel / sandy clay) with sharp bands + a bright orange cable
    and a yellow warning tape above it."""
    def soil():
        m, nt, N, Lk, p = S._new_mat("mh_soil_layers_v2")
        uvn = N.new("ShaderNodeUVMap")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(uvn.outputs["UV"], sep.inputs[0])
        vec = S._coord(N, Lk, "Object")
        wob = N.new("ShaderNodeTexNoise")                 # wavy layer boundaries
        wob.inputs["Scale"].default_value = 1.2
        Lk.new(vec, wob.inputs["Vector"])
        wm = N.new("ShaderNodeMapRange")
        wm.inputs["To Min"].default_value, wm.inputs["To Max"].default_value = -0.035, 0.035
        Lk.new(wob.outputs["Fac"], wm.inputs["Value"])
        add = N.new("ShaderNodeMath")
        add.operation = "ADD"
        Lk.new(sep.outputs["Y"], add.inputs[0])
        Lk.new(wm.outputs["Result"], add.inputs[1])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.0, hexc("3c6b2a")          # turf
        els[1].position, els[1].color = 0.86, hexc("a89a86")         # sandy clay at the bottom
        for pos, c in ((0.035, hexc("2e2017")), (0.2, hexc("6b4527")), (0.27, hexc("8a5a32")),
                       (0.55, hexc("9c8f80")), (0.66, hexc("b98a55"))):
            e = els.new(pos)
            e.color = c
        Lk.new(add.outputs[0], ramp.inputs[0])
        col = ramp.outputs["Color"]
        t = C.tex_path("excavated_soil_wall", "diff")
        if t is not None:
            ti = N.new("ShaderNodeTexImage")
            ti.image = bpy.data.images.load(str(t), check_existing=True)
            ti.projection = "BOX"
            mp = N.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (0.7, 0.7, 0.7)
            Lk.new(vec, mp.inputs["Vector"])
            Lk.new(mp.outputs["Vector"], ti.inputs["Vector"])
            ov = N.new("ShaderNodeMix")
            ov.data_type = "RGBA"
            ov.blend_type = "OVERLAY"
            ov.inputs["Factor"].default_value = 0.55
            Lk.new(col, ov.inputs["A"])
            Lk.new(ti.outputs["Color"], ov.inputs["B"])
            col = ov.outputs["Result"]
            tn = C.tex_path("excavated_soil_wall", "nor_gl")
            if tn is not None:
                tnn = N.new("ShaderNodeTexImage")
                tnn.image = bpy.data.images.load(str(tn), check_existing=True)
                tnn.image.colorspace_settings.name = "Non-Color"
                tnn.projection = "BOX"
                Lk.new(mp.outputs["Vector"], tnn.inputs["Vector"])
                nm = N.new("ShaderNodeNormalMap")
                nm.inputs["Strength"].default_value = 1.2
                Lk.new(tnn.outputs["Color"], nm.inputs["Color"])
                Lk.new(nm.outputs["Normal"], p.inputs["Normal"])
        Lk.new(col, p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.95
        return S._finish(m, p.outputs[0])
    soil_m = B._cached("mh_soil_layers_v2", soil)
    cable = S.pbr("mh_cable_v2", hexc("ff6a13"), 0.35, coat=0.4)
    try:
        cable.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = hexc("ff6a13")
        cable.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.35
    except Exception:
        pass
    tape = S.pbr("mh_warning_tape", hexc("f2c230"), 0.5)
    return soil_m, cable, tape


def upgrade_sections(world, H):
    """Restyle the already-built cut-away objects: soil wall/caps, thicker orange cable, warning tape 30 cm above."""
    if not world.sections:
        return 0
    soil_m, cable_m, tape_m = section_materials()
    n = 0
    for sid, sec in world.sections.items():
        a, b, d, nrm, Lg = sec["frame"]
        cd = sec["spec"].get("cable_depth", 0.6)
        for o in sec["objs"]:
            if o.name.endswith("_wall") or o.name.endswith("_caps"):
                o.data.materials[0] = soil_m
            elif o.name.endswith("_cable"):
                o.data.materials[0] = cable_m
                o.scale = (1.0, 1.0, 1.0)
                bm = bmesh.new()                  # rebuild thicker (r 6 cm, conduit-like) and half proud of the wall
                steps = max(2, int(Lg / 0.5))
                prev = None
                for i in range(steps + 1):
                    t = Lg * i / steps
                    x, y = a[0] + d[0] * t + nrm[0] * 0.02, a[1] + d[1] * t + nrm[1] * 0.02
                    p = (x, y, H(x, y) - cd)
                    if prev:
                        B.bm_cyl(bm, prev, p, 0.06, 0.06, 12, 0, False)
                    prev = p
                bm.to_mesh(o.data)
                bm.free()
                o.data.materials[0] = cable_m
                for pl in o.data.polygons:
                    pl.use_smooth = True
                n += 1
        bm = bmesh.new()                          # warning tape: a thin yellow ribbon 30 cm above the cable
        steps = max(2, int(Lg / 0.5))
        prev = None
        for i in range(steps + 1):
            t = Lg * i / steps
            x, y = a[0] + d[0] * t + nrm[0] * 0.01, a[1] + d[1] * t + nrm[1] * 0.01
            z = H(x, y) - cd + 0.3
            row = (bm.verts.new((x, y, z - 0.025)), bm.verts.new((x, y, z + 0.025)))
            if prev:
                bm.faces.new((prev[0], prev[1], row[1], row[0]))
            prev = row
        to = B.mesh_obj("mh_sec_%s_tape" % sid, bm, [tape_m])
        to.hide_render = True
        sec["objs"].append(to)
    return n


# ---------------------------------------------------------------- dusk sky
def add_dusk_sky(rig):
    """A physical sky (low sun) mixed over the daytime HDRI; key_preset keys rig['sky_mix'] (0 day, 1 dusk)."""
    w = rig.get("world")
    if w is None:
        return None
    nt = w.node_tree
    N, Lk = nt.nodes, nt.links
    sky = N.new("ShaderNodeTexSky")
    for st in ("MULTIPLE_SCATTERING", "NISHITA"):
        try:
            sky.sky_type = st
            break
        except Exception:
            pass
    sky.sun_elevation = math.radians(3.0)
    sky.sun_rotation = math.radians(180.0)
    for attr, v in (("air_density", 1.6), ("dust_density", 4.0), ("aerosol_density", 4.0), ("sun_size", math.radians(2.5)),
                    ("sun_intensity", 0.6)):
        try:
            setattr(sky, attr, v)
        except Exception:
            pass
    sky_gain = N.new("ShaderNodeMix")
    sky_gain.data_type = "RGBA"
    sky_gain.blend_type = "MULTIPLY"
    sky_gain.inputs["Factor"].default_value = 1.0
    sky_gain.inputs["B"].default_value = (0.42, 0.42, 0.56, 1.0)
    Lk.new(sky.outputs["Color"], sky_gain.inputs["A"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["Factor"].default_value = 0.0
    tint = rig["tint"]
    bg = rig["bg"]
    Lk.new(tint.outputs["Result"], mix.inputs["A"])
    Lk.new(sky_gain.outputs["Result"], mix.inputs["B"])
    Lk.new(mix.outputs["Result"], bg.inputs["Color"])
    rig["sky_mix"] = mix
    rig["sky"] = sky
    return mix


# ---------------------------------------------------------------- pickup
def pickup(stats=None):
    """Generic 1990s regular-cab pickup (no badges/text), ~5.4 x 2.0 x 1.85 m, front faces +X, origin at ground
    centre. Extruded side profiles + bevels + real wheel arches (boolean) + tyres with rims."""
    red = S.pbr("mh_truck_red_v2", hexc("a8231b"), 0.28, coat=0.8, var=0.03, var_scale=2.0)
    chrome = S.pbr("mh_bumper", hexc("c8ccd0"), 0.2, metal=0.95)
    black = S.pbr("mh_truck_trim", hexc("1c1c1e"), 0.55)
    tire = S.pbr("mh_tire_v2", hexc("1a1a1a"), 0.75, var=0.05, var_scale=8.0, bump=0.2)
    rim = S.pbr("mh_rim", hexc("b9bdc1"), 0.3, metal=0.85)
    glass = S.glass_mat("mh_truck_glass", hexc("3d5260"))
    lamp = S.pbr("mh_lamp_lens", hexc("f0eee6"), 0.08, coat=1.0)
    tail = S.pbr("mh_tail_lens", hexc("c0151a"), 0.1, coat=1.0)
    W = 1.96

    def extrude(bm, prof, y0, y1, mi):
        a = [bm.verts.new((x, y0, z)) for x, z in prof]
        b_ = [bm.verts.new((x, y1, z)) for x, z in prof]
        fs = [bm.faces.new(a), bm.faces.new(list(reversed(b_)))]
        n = len(prof)
        for i in range(n):
            j = (i + 1) % n
            fs.append(bm.faces.new((a[i], a[j], b_[j], b_[i])))
        for f in fs:
            f.material_index = mi
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        return fs
    # ---- body: nose + cab lower + bed sides as one profile, bed hollow done with a boolean box
    bm = bmesh.new()
    lower = [(2.72, 0.42), (2.78, 0.62), (2.74, 1.02), (2.55, 1.1), (1.05, 1.2), (0.95, 1.22), (-0.72, 1.22),
             (-0.72, 1.12), (-2.72, 1.12), (-2.76, 0.95), (-2.74, 0.45)]
    extrude(bm, lower, -W / 2, W / 2, 0)
    cab = [(1.0, 1.2), (0.42, 1.82), (-0.62, 1.86), (-0.7, 1.8), (-0.72, 1.2)]
    extrude(bm, cab, -0.93, 0.93, 0)
    body = B.mesh_obj("mh_pickup", bm, [red, black, glass, chrome, lamp, tail])
    me = body.data
    # bed hollow + wheel wells (boolean difference, applied)
    cutters = []
    bbm = bmesh.new()
    S.bm_box(bbm, (-1.73, 0, 1.2), (1.9, W - 0.16, 0.9), 0)
    cutters.append(B.mesh_obj("cut_bed", bbm, [red]))
    for wx in (1.72, -1.78):
        wbm = bmesh.new()
        B.bm_cyl(wbm, (wx, -1.3, 0.42), (wx, 1.3, 0.42), 0.5, 0.5, 32, 0)
        cutters.append(B.mesh_obj("cut_well", wbm, [red]))
    vl = bpy.context.view_layer
    for c in cutters:
        mod = body.modifiers.new("cut", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = c
        try:
            mod.solver = "EXACT"
        except Exception:
            pass
        vl.objects.active = body
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as ex:
            print("[cc0] pickup boolean failed: %s" % ex)
            body.modifiers.remove(mod)
        bpy.data.objects.remove(c, do_unlink=True)
    bev = body.modifiers.new("bevel", "BEVEL")
    bev.width = 0.035
    bev.segments = 3
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(35)
    try:
        bev.harden_normals = True
    except Exception:
        pass
    for p in me.polygons:
        p.use_smooth = True
    # ---- details: windows, lamps, bumpers, grille, arches, mirrors, tyres
    bm = bmesh.new()
    eps = 0.006
    win_side = [(0.88, 1.27), (0.42, 1.76), (-0.58, 1.79), (-0.64, 1.27)]
    for sy in (-1, 1):
        y = sy * (0.93 + eps)
        vs = [bm.verts.new((x, y, z)) for x, z in win_side]
        f = bm.faces.new(vs if sy > 0 else list(reversed(vs)))
        f.material_index = 2
        S.bm_box(bm, (0.3, sy * 0.935, 1.26), (1.2, 0.02, 0.025), 1)                    # belt-line trim
        S.bm_box(bm, (0.92, sy * 1.06, 1.32), (0.1, 0.2, 0.14), 1)                       # mirrors
    # windshield on the sloped face, rear window on the back of the cab
    ws = [(0.97, -0.84, 1.24), (0.97, 0.84, 1.24), (0.46, 0.8, 1.78), (0.46, -0.8, 1.78)]
    nx, nz = 0.6, 0.58
    nl = math.hypot(nx, nz)
    f = bm.faces.new([bm.verts.new((x + nx / nl * eps, y, z + nz / nl * eps)) for x, y, z in ws])
    f.material_index = 2
    rw = [(-0.72 - eps, 0.75, 1.3), (-0.72 - eps, -0.75, 1.3), (-0.705 - eps, -0.72, 1.72), (-0.705 - eps, 0.72, 1.72)]
    f = bm.faces.new([bm.verts.new(p) for p in rw])
    f.material_index = 2
    S.bm_box(bm, (2.77, 0, 0.84), (0.04, 1.2, 0.3), 1)                                 # grille
    for k in range(4):
        S.bm_box(bm, (2.79, 0, 0.73 + k * 0.075), (0.02, 1.18, 0.02), 3)
    for sy in (-0.76, 0.76):
        S.bm_box(bm, (2.765, sy, 0.86), (0.05, 0.3, 0.2), 4)                           # headlights
        S.bm_box(bm, (-2.765, sy * 1.1, 0.95), (0.05, 0.12, 0.28), 5)                  # tail lights
    S.bm_box(bm, (2.86, 0, 0.5), (0.16, 2.02, 0.2), 3)                                 # bumpers
    S.bm_box(bm, (-2.86, 0, 0.5), (0.16, 2.02, 0.2), 3)
    S.bm_box(bm, (-2.75, 0, 0.32), (0.3, 1.2, 0.12), 1)                                # hitch / step
    for wx in (1.72, -1.78):                                                           # black arch flares
        for sy in (-1, 1):
            rows = []
            for k in range(13):
                a = math.pi * k / 12.0
                rows.append([bm.verts.new((wx + r * math.cos(a), sy * (W / 2 + dy), 0.42 + r * math.sin(a)))
                             for r, dy in ((0.5, 0.0), (0.58, 0.035), (0.5, 0.035))])
            for k in range(12):
                for j in range(2):
                    f = bm.faces.new((rows[k][j], rows[k + 1][j], rows[k + 1][j + 1], rows[k][j + 1]))
                    f.material_index = 1
    det = B.mesh_obj("mh_pickup_detail", bm, [red, black, glass, chrome, lamp, tail])
    det.parent = body
    # tyres + rims (separate object so they can roll later)
    bm = bmesh.new()
    for wx in (1.72, -1.78):
        for sy in (-1, 1):
            y0, y1 = sy * 0.72, sy * 1.0
            B.bm_cyl(bm, (wx, y0, 0.42), (wx, y1, 0.42), 0.42, 0.42, 28, 0)
            B.bm_cyl(bm, (wx, y1 - sy * 0.02, 0.42), (wx, y1 + sy * 0.004, 0.42), 0.26, 0.24, 20, 1)
            B.bm_cyl(bm, (wx, y1, 0.42), (wx, y1 + sy * 0.02, 0.42), 0.07, 0.05, 10, 1)
    wh = B.mesh_obj("mh_pickup_wheels", bm, [tire, rim])
    bv = wh.modifiers.new("bevel", "BEVEL")
    bv.width = 0.05
    bv.segments = 3
    bv.limit_method = "ANGLE"
    for p in wh.data.polygons:
        p.use_smooth = True
    wh.parent = body
    if stats is not None:
        stats["pickup_tris"] = sum(len(p.vertices) - 2 for o in (body, det, wh) for p in o.data.polygons)
    return body

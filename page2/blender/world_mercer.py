"""Mercer Hollow exterior world (Self-Made Engineer, Page 2), built from page2/world_state.json. Needs bpy.

    import world_mercer as W
    world = W.build(ctx, ws, parts=None, focus=[(x, y), ...], sections=episode["sections"], episode=ep)

Look: the WJH v2 bright world (HDRI daylight, PBR, Poly Haven detail textures at 1K, distance haze) via
pipeline/blender/scene_lib_v2.py. Lighting presets day / dusk / frost / snow live in ONE scene and are keyed
(CONSTANT) so a reel can switch inside a move: world.key_preset(frame, name).

Parts (build only some with --parts for quick stills): terrain water street house yard workshop props trees grass
far sections builds. Everything repeated is instanced (Geometry Nodes 'Instance on Points' or shared meshes):
trees (3 species x 2 LODs), fence posts, grass clumps, rocks, utility poles, neighbour houses (2 models, colour from
the object colour).

Builds: BUILDS = {id: fn(ctx, entry, mode)}, mode "assemble" (its own episode) or "idle" (later episodes). Every
world_state build with status approved|scheduled|posted is placed in idle mode; the episode's own build is placed
in assemble mode. Coordinates: metres, Z up, +X east (ridge), +Y north (upstream), origin = front-door threshold.
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import mh_paths as MP
import mh_blender as B
from mh_blender import S, L, hexc

MP.add_import_paths(blender=True)
import gen_world_state as G  # noqa: E402
import camera_plan as CP  # noqa: E402
import mercer_cc0 as MC  # noqa: E402  (session 6: CC0 trees/grass/rocks/props/PBR; falls back when assets missing)

ALL_PARTS = ("terrain", "water", "street", "house", "yard", "workshop", "props", "trees", "grass", "far",
             "sections", "builds")
INNER = (-240.0, 210.0, -140.0, 130.0)      # exact generator terrain inside; fades to z=0 outside
OUTER = (-400.0, 560.0, -300.0, 300.0)

# ---------------------------------------------------------------- lighting presets (keyed, one scene)
PRESETS = {
    "day":   {"tint": (1.0, 1.0, 1.0), "strength": 1.0, "exposure": None, "sun": 0.0, "sun_col": (1.0, 0.95, 0.86),
              "sun_elev": 40.0, "sun_az": -35.0, "fog": None, "frost": 0.0, "snow": 0.0},
    "dusk":  {"tint": (0.92, 0.6, 0.5), "strength": 0.24, "exposure": 0.0, "sun": 3.4, "sun_col": (1.0, 0.4, 0.16),
              "sun_elev": 2.5, "sun_az": -90.0, "fog": (0.5, 0.4, 0.42), "frost": 0.0, "snow": 0.0, "sky": 1.0},
    "frost": {"tint": (0.86, 0.93, 1.06), "strength": 0.95, "exposure": -0.6, "sun": 0.0, "sun_col": (0.95, 0.97, 1.0),
              "sun_elev": 25.0, "sun_az": -35.0, "fog": (0.80, 0.86, 0.93), "frost": 1.0, "snow": 0.0},
    "snow":  {"tint": (0.90, 0.95, 1.05), "strength": 0.9, "exposure": -0.85, "sun": 0.0, "sun_col": (0.95, 0.97, 1.0),
              "sun_elev": 25.0, "sun_az": -35.0, "fog": (0.86, 0.89, 0.94), "frost": 1.0, "snow": 1.0},
}


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def H(x, y):
    """Terrain height: the generator's analytic profile inside INNER, fading to 0 towards OUTER."""
    x0, x1, y0, y1 = INNER
    X0, X1, Y0, Y1 = OUTER
    fx = 1.0
    if x < x0:
        fx = smoothstep((x - X0) / (x0 - X0))
    elif x > x1:
        fx = smoothstep((X1 - x) / (X1 - x1))
    fy = 1.0
    if y < y0:
        fy = smoothstep((y - Y0) / (y0 - Y0))
    elif y > y1:
        fy = smoothstep((Y1 - y) / (Y1 - y1))
    h = G.height(min(max(x, -400.0), 560.0), min(max(y, -300.0), 300.0))
    return h * fx * fy


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def dist_to_polyline(x, y, pts):
    best = 1e9
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


class World(object):
    def __init__(self, ctx, ws, loc, episode=None):
        self.ctx, self.ws, self.loc, self.ep = ctx, ws, loc, episode or {}
        self.z = loc["zones"]
        self.lights = {}          # name -> [(owner, prop, on_value, off_value)]
        self.rig = {}
        self.sections = {}        # id -> {"objs": [...], "frame": (a, b, d, n, L), "spec": {...}}
        self.cast = {}            # "pickup" etc. -> object
        self.stats = {}
        self.exclude = []         # [(x, y, r)] no scatter (pad clearing, sections)

    # ---------------------------------------------------------------- lighting rig
    def build_lighting(self, sun_az=-35.0):
        sc = self.ctx.scene
        w = bpy.data.worlds.new("MH_World")
        sc.world = w
        nt = w.node_tree
        N, Lk = nt.nodes, nt.links
        bg = N.get("Background") or N.new("ShaderNodeBackground")
        out = N.get("World Output") or N.new("ShaderNodeOutputWorld")
        Lk.new(bg.outputs[0], out.inputs[0])
        hdri = S._find_hdri()
        if hdri:
            phi = next((v["phi"] for k, v in S.HDRI_SUN.items() if k in hdri), 144.0)
            tc = N.new("ShaderNodeTexCoord")
            mp = N.new("ShaderNodeMapping")
            mp.inputs["Rotation"].default_value = (0, 0, math.radians(phi + 90.0 - sun_az))
            env = N.new("ShaderNodeTexEnvironment")
            env.image = bpy.data.images.load(hdri, check_existing=True)
            Lk.new(tc.outputs["Generated"], mp.inputs["Vector"])
            Lk.new(mp.outputs["Vector"], env.inputs["Vector"])
            src = env.outputs["Color"]
            for attr, val in (("sun_threshold", 6.0), ("use_sun_shadow", True), ("sun_angle", math.radians(1.5))):
                try:
                    setattr(w, attr, val)
                except Exception:
                    pass
        else:
            sky = N.new("ShaderNodeTexSky")
            try:
                sky.sky_type = "MULTIPLE_SCATTERING"
            except Exception:
                pass
            sky.sun_elevation = math.radians(40.0)
            src = sky.outputs["Color"]
            print("[mh] no HDRI in assets/polyhaven/hdri -> procedural sky (flatter look)")
        tint = N.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs["Factor"].default_value = 1.0
        Lk.new(src, tint.inputs["A"])
        tint.inputs["B"].default_value = (1, 1, 1, 1)
        Lk.new(tint.outputs["Result"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = S.HDRI_STRENGTH
        sun = S.sun_lamp(40.0, -35.0, 0.0)
        self.rig = {"world": w, "bg": bg, "tint": tint, "sun": sun, "hdri": bool(hdri)}
        try:
            MC.add_dusk_sky(self.rig)          # physical low-sun sky, keyed in for the dusk preset
        except Exception as ex:
            print("[mh] dusk sky not added: %s" % ex)
        sc.view_settings.exposure = S.HDRI_EXPOSURE if hdri else 0.0
        return self.rig

    def key_preset(self, f, name):
        p = PRESETS[name]
        r = self.rig
        if not r:
            return
        B.key_const(r["tint"].inputs["B"], "default_value", [(f, tuple(p["tint"]) + (1.0,))])
        B.key_const(r["bg"].inputs["Strength"], "default_value", [(f, S.HDRI_STRENGTH * p["strength"])])
        exp = S.HDRI_EXPOSURE if p["exposure"] is None else p["exposure"]
        B.key_const(self.ctx.scene.view_settings, "exposure", [(f, exp)])
        sun = r["sun"]
        B.key_const(sun.data, "energy", [(f, p["sun"])])
        B.key_const(sun.data, "color", [(f, p["sun_col"])])
        B.key_const(sun, "rotation_euler", [(f, (math.radians(90.0 - p["sun_elev"]), 0.0, math.radians(p["sun_az"])))])
        fg = B.fog_group()
        B.key_const(fg.nodes["color"].outputs[0], "default_value",
                    [(f, tuple(p["fog"] or S.HAZE[:3]) + (1.0,))])
        if r.get("sky_mix") is not None:
            B.key_const(r["sky_mix"].inputs["Factor"], "default_value", [(f, p.get("sky", 0.0))])
            if r.get("sky") is not None:
                B.key_const(r["sky"], "sun_elevation", [(f, math.radians(p["sun_elev"] - 1.0))])
                # s7: the sky's sun on the SAME side as the sun lamp. Lamp rotation (90-elev, 0, az) puts the sun
                # towards (sin az, -cos az); the sky texture's sun sits at (sin rot, cos rot) (measured in Blender
                # 5.3: rot 0 -> +Y, rot 90 -> +X) -> rot = 180 - az.
                B.key_const(r["sky"], "sun_rotation", [(f, math.radians(180.0 - p["sun_az"]))])
        wg = B.weather_group()
        B.key_const(wg.nodes["frost"].outputs[0], "default_value", [(f, p["frost"])])
        B.key_const(wg.nodes["snow"].outputs[0], "default_value", [(f, p["snow"])])

    def add_light(self, name, owner, prop, on, off):
        self.lights.setdefault(name, []).append((owner, prop, on, off))

    def key_lights(self, f, state):
        for name, on in (state or {}).items():
            for owner, prop, v_on, v_off in self.lights.get(name, []):
                B.key_const(owner, prop, [(f, v_on if on else v_off)])

    # ---------------------------------------------------------------- terrain
    def build_terrain(self):
        B.part_collection("terrain")

        def axis(spans):
            out = []
            for a, b, st in spans:
                n = max(1, int(round((b - a) / st)))
                out += [a + (b - a) * i / n for i in range(n)]
            out.append(spans[-1][1])
            return sorted(set(round(v, 3) for v in out))
        xs = axis([(-400, -240, 12), (-240, -25, 6), (-25, 40, 1.5), (40, 54, 1.0), (54, 140, 1.5), (140, 210, 6),
                   (210, 560, 12)])
        ys = axis([(-300, -140, 12), (-140, -85, 6), (-85, 95, 1.5), (95, 130, 6), (130, 300, 12)])
        nx, ny = len(xs), len(ys)
        verts = [(x, y, H(x, y)) for y in ys for x in xs]
        faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
                 for j in range(ny - 1) for i in range(nx - 1)]
        me = bpy.data.meshes.new("mh_terrain")
        me.from_pydata(verts, [], faces)
        me.polygons.foreach_set("use_smooth", [True] * len(faces))
        # vertex mask: R mown lawn, G dirt/gravel/bank, B woods floor
        woods = self.z["woods"]["regions"]
        path = [tuple(p) for p in self.z["gravel_path"]["polyline"]]
        gz = self.z["garden"]
        cols = []
        for (x, y, _z) in verts:
            cx = G.creek_x(y)
            lawn = 1.0 if (x < 34.5 and -20.5 < y < 23.0) or x < -18.0 else 0.0
            if x < -18 and abs(y) < 7.5:
                lawn = 0.6
            dirt = 0.0
            dc = abs(x - cx)
            if dc < 2.8:
                dirt = 1.0 if dc < 1.9 else 0.5
            if dist_to_polyline(x, y, path) < 1.7:
                dirt, lawn = 0.85, 0.0
            if abs(x - gz["pos"][0]) < gz["size"][0] / 2 + 0.6 and abs(y - gz["pos"][1]) < gz["size"][1] / 2 + 0.6:
                dirt = 0.7
            if math.hypot(x - G.POND[0], y - G.POND[1]) < G.POND[2] + 1.5:
                dirt = max(dirt, 0.6)
            px, py, ph = G.PAD
            if abs(x - px) < ph + 1 and abs(y - py) < ph + 1:
                dirt = max(dirt, 0.35)
            wood = 1.0 if any(point_in_poly(x, y, poly) for poly in woods) else 0.0
            cols += [lawn, dirt, wood, 1.0]
        ca = me.color_attributes.new("mask", "FLOAT_COLOR", "POINT")
        ca.data.foreach_set("color", cols)
        o = S.obj("mh_terrain", me)
        me.materials.append(self.terrain_mat())
        self.stats["terrain_tris"] = 2 * len(faces)
        return o

    def terrain_mat(self):
        m, nt, N, Lk, p = S._new_mat("mh_terrain_mat")
        attr = N.new("ShaderNodeAttribute")
        attr.attribute_type = "GEOMETRY"
        attr.attribute_name = "mask"
        sep = N.new("ShaderNodeSeparateColor")
        Lk.new(attr.outputs["Color"], sep.inputs[0])
        vec = S._coord(N, Lk, "Object")

        def mix(a, b, fac):
            mx = N.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            if isinstance(fac, float):
                mx.inputs["Factor"].default_value = fac
            else:
                Lk.new(fac, mx.inputs["Factor"])
            for sock, v in ((mx.inputs["A"], a), (mx.inputs["B"], b)):
                if isinstance(v, tuple):
                    sock.default_value = v
                else:
                    Lk.new(v, sock)
            return mx.outputs["Result"]
        meadow = hexc("7d9046")
        lawn = hexc("5c8a3a")
        dirt = hexc("7a6247")
        woods = hexc("4c4a30")
        # mowing stripes on the lawn
        wv = N.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = "Y"
        wv.inputs["Scale"].default_value = 0.05
        wv.inputs["Distortion"].default_value = 0.0
        Lk.new(vec, wv.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 0.93
        mr.inputs["To Max"].default_value = 1.06
        Lk.new(wv.outputs["Fac"], mr.inputs["Value"])
        lawn_s = S._mul_col(N, Lk, lawn, mr.outputs["Result"])
        col = mix(meadow, lawn_s, sep.outputs["Red"])
        col = mix(col, woods, sep.outputs["Blue"])
        col = mix(col, dirt, sep.outputs["Green"])
        fac, _ = S._noise_var(N, Lk, vec, 0.025, 0.14, 5.0)
        col = S._mul_col(N, Lk, col, fac)
        # slope -> a little bare earth on the steepest bits
        geo = N.new("ShaderNodeNewGeometry")
        sz = N.new("ShaderNodeSeparateXYZ")
        Lk.new(geo.outputs["Normal"], sz.inputs[0])
        sl = N.new("ShaderNodeMapRange")
        sl.inputs["From Min"].default_value = 0.96
        sl.inputs["From Max"].default_value = 0.92
        Lk.new(sz.outputs["Z"], sl.inputs["Value"])
        slm = N.new("ShaderNodeMath")
        slm.operation = "MULTIPLY"
        Lk.new(sl.outputs["Result"], slm.inputs[0])
        slm.inputs[1].default_value = 0.35
        col = mix(col, dirt, slm.outputs[0])
        col = B._snow_mix(N, Lk, col)
        p.inputs["Roughness"].default_value = 0.93
        if not S.ph_detail(N, Lk, vec, "aerial_grass_rock", p, col, amount=0.5, hue=0.1, normal=0.5, rough_mix=0.2,
                           scale_mul=0.35):
            Lk.new(col, p.inputs["Base Color"])
        m = S._finish(m, p.outputs[0])
        self._section_mask(m)
        return m

    def _section_mask(self, m):
        """Cut-away: terrain on the near side of the active section plane turns transparent (MH_Section keyed)."""
        nt = m.node_tree
        N, Lk = nt.nodes, nt.links
        out = N.get("Material Output")
        if not out.inputs["Surface"].is_linked:
            return
        src = out.inputs["Surface"].links[0].from_socket
        g = B.group_node(N, B.section_group())
        geo = N.new("ShaderNodeNewGeometry")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(geo.outputs["Position"], sep.inputs[0])

        def op(o, a, b):
            n = N.new("ShaderNodeMath")
            n.operation = o
            for i, v in enumerate((a, b)):
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = v
                else:
                    Lk.new(v, n.inputs[i])
            return n.outputs[0]
        rx = op("SUBTRACT", sep.outputs["X"], g.outputs["ax"])
        ry = op("SUBTRACT", sep.outputs["Y"], g.outputs["ay"])
        s = op("ADD", op("MULTIPLY", rx, g.outputs["nx"]), op("MULTIPLY", ry, g.outputs["ny"]))
        t = op("ADD", op("MULTIPLY", rx, g.outputs["dx"]), op("MULTIPLY", ry, g.outputs["dy"]))
        inside = op("MULTIPLY", op("GREATER_THAN", s, 0.0), op("LESS_THAN", s, g.outputs["width"]))
        inside = op("MULTIPLY", inside, op("MULTIPLY", op("GREATER_THAN", t, 0.0), op("LESS_THAN", t, g.outputs["len"])))
        mask = op("MULTIPLY", inside, g.outputs["on"])
        tr = N.new("ShaderNodeBsdfTransparent")
        mx = N.new("ShaderNodeMixShader")
        Lk.new(mask, mx.inputs[0])
        Lk.new(src, mx.inputs[1])
        Lk.new(tr.outputs[0], mx.inputs[2])
        Lk.new(mx.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass

    # ---------------------------------------------------------------- water
    def build_water(self):
        B.part_collection("water")
        wm = B.mat_water()
        bm = bmesh.new()
        prev = None
        for k in range(0, 211):
            y = 110.0 - k
            cx = G.creek_x(y)
            z = G.bed(y) + 0.3
            if 33.5 <= y <= 36.2:
                z = max(z, G.FALL_BOT_Z + 0.3)
            if y < 36.0 and y > 35.0:
                z = G.FALL_BOT_Z + 0.3 + (y - 35.0) * (G.FALL_TOP_Z - G.FALL_BOT_Z)
            row = [bm.verts.new((cx - 1.7, y, z)), bm.verts.new((cx + 1.7, y, z))]
            if prev:
                bm.faces.new((prev[0], prev[1], row[1], row[0]))
            prev = row
        B.mesh_obj("mh_creek", bm, [wm])
        # plunge pool + pond
        for name, (cx, cy, r, z) in (("mh_pool", (G.creek_x(G.POOL[1]), G.POOL[1], G.POOL[2] + 0.6, G.FALL_BOT_Z + 0.3)),
                                     ("mh_pond", (G.POND[0], G.POND[1], G.POND[2] + 1.0, G.POND[3]))):
            bm = bmesh.new()
            bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=r)
            B.mesh_obj(name, bm, [wm], loc=(cx, cy, z))
        # waterfall sheet + foam
        fx = G.creek_x(35.5)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0), (2.6, 0.25, G.FALL_TOP_Z - G.FALL_BOT_Z), 0)
        B.mesh_obj("mh_fall", bm, [B.mat_foam()], loc=(fx, 35.15, (G.FALL_TOP_Z + G.FALL_BOT_Z) / 2 + 0.3))
        bm = bmesh.new()
        for i in range(9):
            B.bm_sphere(bm, (random.Random(i).uniform(-1.2, 1.2), random.Random(i + 9).uniform(-0.9, 0.3), 0.0),
                        (0.45, 0.35, 0.12), 1, 0, 0.2, i)
        B.mesh_obj("mh_foam", bm, [B.mat_foam()], loc=(fx, 34.2, G.FALL_BOT_Z + 0.35))
        # reeds (instanced) around the pond
        reed = bmesh.new()
        for i in range(5):
            a = i * 1.3
            B.bm_cyl(reed, (0.05 * math.cos(a), 0.05 * math.sin(a), 0), (0.12 * math.cos(a), 0.12 * math.sin(a), 1.2),
                     0.012, 0.004, 4, 0, False)
        tpl = B.template_obj("tpl_reed", S.mesh_from_bm("tpl_reed", reed, [S.pbr("mh_reed", hexc("6f7d3a"), 0.8)]))
        rng = random.Random(5)
        pts, rots = [], []
        for i in range(140):
            a = rng.uniform(0, 2 * math.pi)
            r = G.POND[2] + rng.uniform(-0.8, 1.2)
            x, y = G.POND[0] + r * math.cos(a), G.POND[1] + r * math.sin(a)
            pts.append((x, y, max(H(x, y), G.POND[3] - 0.2)))
            rots.append(rng.uniform(0, 6.28))
        B.scatter_gn("mh_reeds", tpl, pts, rots, [rng.uniform(0.7, 1.3) for _ in pts])
        # footbridge (creek crossing, approved)
        cc = self.z["creek_crossing"]
        cx, cy = G.creek_x(cc["pos"][1]), cc["pos"][1]
        zd = max(H(cx - 2.6, cy), H(cx + 2.6, cy)) + 0.15
        wood = B.mat_bands("mh_bridge_wood", hexc("8a6a48"), 0.16, "X", 0.25, 0.8)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0), (5.6, 1.4, 0.08), 0)
        for sy in (-0.65, 0.65):
            S.bm_box(bm, (0, sy, 0.5), (5.6, 0.06, 0.06), 0)
            for sx in (-2.7, 0.0, 2.7):
                S.bm_box(bm, (sx, sy, 0.25), (0.08, 0.08, 0.55), 0)
            S.bm_box(bm, (0, sy, -0.12), (5.8, 0.12, 0.16), 0)
        B.mesh_obj("mh_footbridge", bm, [wood], loc=(cx, cy, zd))
        rock = S.pbr("mh_rock", hexc("8b877d"), 0.85, var=0.2, var_scale=3.0, bump=0.4)
        rbm = bmesh.new()
        B.bm_sphere(rbm, (0, 0, 0.1), (0.6, 0.45, 0.35), 1, 0, 0.25, 3)
        tpl = B.template_obj("tpl_rock", S.mesh_from_bm("tpl_rock", rbm, [rock], smooth=True))
        pts, rots, scl = [], [], []
        for k in range(160):
            y = rng.uniform(-95, 105)
            side = rng.choice((-1, 1))
            x = G.creek_x(y) + side * rng.uniform(1.6, 3.4)
            if abs(y - cy) < 4:
                continue
            pts.append((x, y, H(x, y) - 0.1))
            rots.append(rng.uniform(0, 6.28))
            scl.append(rng.uniform(0.5, 1.6))
        n_cc0 = MC.creek_rocks(H, G.creek_x, lambda yy: abs(yy - cy) < 4)
        if n_cc0:
            self.stats["creek_rocks_cc0"] = n_cc0
        else:
            B.scatter_gn("mh_creek_rocks", tpl, pts, rots, scl)
        try:
            MC.creek_bed(H, G.creek_x, G.bed, G.FALL_BOT_Z)
        except Exception as ex:
            print("[mh] creek bed skipped: %s" % ex)
        self.stats["creek_bridge_z"] = round(zd, 2)

    # ---------------------------------------------------------------- street + neighbours + poles
    def build_street(self):
        B.part_collection("street")
        st = self.loc["street"]
        asph = B.mat_ph("mh_asphalt", hexc("4a4c50"), "aerial_asphalt_01", 0.45, 0.85)
        conc = B.mat_ph("mh_concrete", hexc("c9c4ba"), "concrete_floor_02", 0.35, 0.8, scale_mul=1.0)
        curb = S.pbr("mh_curb", hexc("bdb8ae"), 0.8, var=0.05)
        bx, by = st["cul_de_sac"]["centre"][:2]
        rb = st["cul_de_sac"]["radius"]
        hw = st["street"]["width"] / 2
        x_end = st["street"]["to"][0]
        S.plane_obj("mh_road", abs(x_end - bx), 2 * hw, ((x_end + bx) / 2, by, 0.02), asph)
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=rb)
        B.mesh_obj("mh_bulb", bm, [asph], loc=(bx, by, 0.024))
        sw = st["street"]["sidewalk"]
        y_in, y_out = hw + sw["grass_strip"], hw + sw["grass_strip"] + sw["width"]
        x_mouth = bx - math.sqrt(max(0.0, rb * rb - hw * hw))
        bm = bmesh.new()
        for sy in (-1, 1):
            S.bm_box(bm, ((x_end + x_mouth) / 2, sy * (hw + 0.08), 0.08), (abs(x_mouth - x_end), 0.16, 0.16), 0)
        # ring curb around the bulb (gap at the street mouth)
        for i in range(48):
            a0, a1 = 2 * math.pi * i / 48, 2 * math.pi * (i + 1) / 48
            am = (a0 + a1) / 2
            if abs(abs(math.atan2(math.sin(am), math.cos(am))) - math.pi) < math.asin(min(1.0, hw / rb)) + 0.05:
                continue                                                  # street mouth (west)
            mx_, my_ = bx + rb * math.cos(am), by + rb * math.sin(am)
            if mx_ > bx and (-14.3 < my_ < -6.4 or -0.8 < my_ < 0.8):
                continue                                                  # driveway + front walk (east)
            p0 = (bx + (rb + 0.08) * math.cos(a0), by + (rb + 0.08) * math.sin(a0))
            p1 = (bx + (rb + 0.08) * math.cos(a1), by + (rb + 0.08) * math.sin(a1))
            B.bm_segment_box(bm, p0, p1, 0.0, 0.16, 0.16, 0)
        B.mesh_obj("mh_curbs", bm, [curb])
        for sy in (-1, 1):
            S.plane_obj("mh_sidewalk_%d" % sy, abs(x_mouth - x_end), sw["width"],
                        ((x_end + x_mouth) / 2, sy * (y_in + y_out) / 2, 0.03), conc)
        # driveway + front walk
        dw = self.z["driveway"]
        S.plane_obj("mh_driveway", dw["size"][0], dw["size"][1], (dw["pos"][0], dw["pos"][1], 0.028), conc)
        S.plane_obj("mh_walk", 14.6, 1.2, (-10.0, 0.0, 0.028), conc)
        # neighbour houses: 2 shared models, colour = object colour
        models = {"nbr_A": self._nbr_model("nbr_A", 10.0, 8.5, 5.6, 2.6), "nbr_B": self._nbr_model("nbr_B", 14.0, 9.0, 3.1, 1.9)}
        for nb in st["neighbor_houses"]:
            x, y, z = nb["pos"]
            o = S.obj("mh_" + nb["id"], models[nb["model"]], (x, y, H(x, y)), (0, 0, math.radians(nb["yaw"] - 270)))
            c = hexc(nb["siding"][1:])
            o.color = (c[0], c[1], c[2], 1.0)
        # utility poles (shared mesh) + wires
        wood = S.pbr("mh_pole", hexc("6b5440"), 0.85, var=0.12, var_scale=2.0, bump=0.2)
        dark = S.pbr("mh_insulator", hexc("3a3d40"), 0.4)
        poles = st["utility_poles"]["positions"]
        hgt = st["utility_poles"]["height"]
        bm = bmesh.new()
        B.bm_cyl(bm, (0, 0, -1.0), (0, 0, hgt), 0.15, 0.11, 8, 0)
        S.bm_box(bm, (0, 0, hgt - 0.7), (0.12, 2.4, 0.12), 0)
        for yy in (-1.0, 0.0, 1.0):
            B.bm_cyl(bm, (0, yy, hgt - 0.64 if yy else hgt), (0, yy, hgt - 0.44 if yy else hgt + 0.2), 0.04, 0.04, 6, 1)
        pole_me = S.mesh_from_bm("mh_pole_m", bm, [wood, dark])
        tips = []
        for i, (x, y, _z) in enumerate(poles):
            z0 = H(x, y)
            S.obj("mh_pole_%d" % i, pole_me, (x, y, z0))
            tips.append([(x, y + yy, z0 + (hgt - 0.44 if yy else hgt + 0.2)) for yy in (-1.0, 0.0, 1.0)])
        wire = S.pbr("mh_wire", hexc("202224"), 0.5)
        order = sorted(range(len(poles)), key=lambda i: poles[i][0])
        for a, b in zip(order, order[1:]):
            for k in range(3):
                sag = 1.6 if (k == 0 and poles[a][0] < -60 and poles[b][0] > -90 and poles[b][0] < -40) else 0.35
                B.curve_line("mh_wire_%d_%d" % (a, k), B.catenary(tips[a][k], tips[b][k], sag), 0.012, wire)
        # service drop to the house north-west corner
        near = min(range(len(poles)), key=lambda i: math.hypot(poles[i][0], poles[i][1]))
        B.curve_line("mh_service_drop", B.catenary(tips[near][1], (0.15, 6.5, 5.6), 0.6), 0.012, wire)
        self.stats["poles"] = len(poles)

    def _nbr_model(self, name, w, d, h, rh):
        siding = B.mat_objcolor("mh_nbr_siding")
        roof = B.mat_bands("mh_nbr_roof", hexc("5a5e63"), 0.25, "Z", 0.2, 0.85, 0.1, roof_snow=True)
        trim = S.pbr("mh_trim", hexc("f3f2ee"), 0.6, var=0.02)
        win = S.pbr("mh_nbr_win", hexc("26323e"), 0.08, var=0)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, h / 2), (w, d, h), 0)
        S.bm_prism_x(bm, -w / 2 - 0.4, w / 2 + 0.4, [(-d / 2 - 0.5, h - 0.05), (d / 2 + 0.5, h - 0.05), (0, h + rh)], 1)
        floors = (1.5,) if h < 4 else (1.5, 4.2)
        for z in floors:
            for k in (-1, 1) if w < 12 else (-2, -1, 1, 2):
                S.bm_box(bm, (k * w / 5.0, -d / 2 - 0.04, z), (1.3, 0.08, 1.2), 2)
                S.bm_box(bm, (k * w / 5.0, -d / 2 - 0.08, z), (1.1, 0.06, 1.0), 3)
        S.bm_box(bm, (0, -d / 2 - 0.05, 1.05), (1.0, 0.1, 2.1), 2)
        return S.mesh_from_bm(name, bm, [siding, roof, trim, win])

    # ---------------------------------------------------------------- house + garage + porch
    def build_house(self):
        B.part_collection("house")
        z = self.z
        siding = B.mat_bands("mh_siding", hexc("f4f2ec"), 0.18, "Z", 0.45, 0.75)
        trim = S.pbr("mh_trim", hexc("f3f2ee"), 0.6, var=0.02)
        found = B.mat_ph("mh_foundation", hexc("b9b4aa"), "concrete_floor_02", 0.4, 0.85)
        roof = B.mat_bands("mh_shingles", hexc("6e7174"), 0.2, "Z", 0.35, 0.88, 0.12, roof_snow=True)
        navy = S.pbr("mh_navy_door", hexc("0b1f3a"), 0.45, var=0.02)
        winm = B.mat_glow("mh_house_window", hexc("2a3a4a"), 0.0, emit=(1.0, 0.78, 0.5, 1.0))
        self.add_light("house", B.emission_socket(winm), "default_value", 1.6, 0.0)
        x0, x1, y0, y1 = 0.0, 9.75, -6.7, 6.7
        zf, ze, zr = 0.45, 5.9, 8.53
        t = 0.2
        bm = bmesh.new()
        S.bm_box(bm, ((x0 + x1) / 2, (y0 + y1) / 2, zf / 2), (x1 - x0 + 0.1, y1 - y0 + 0.1, zf), 2)
        S.bm_box(bm, ((x0 + x1) / 2, (y0 + y1) / 2, zf + 0.05), (x1 - x0 - 0.2, y1 - y0 - 0.2, 0.1), 2)
        # walls as slabs (hollow house: the kitchen window sees a lit backdrop box)
        kx, kz0, kz1, kw = 7.0, 1.25, 2.25, 1.2
        B.bm_segment_box(bm, (x0, y0), (x0, y1), zf, ze, t, 0)                     # west (front)
        B.bm_segment_box(bm, (x1, y0), (x1, y1), zf, ze, t, 0)                     # east (back)
        B.bm_segment_box(bm, (x0, y0), (x1, y0), zf, ze, t, 0)                     # south
        B.bm_segment_box(bm, (x0, y1), (kx - kw / 2, y1), zf, ze, t, 0)           # north, around the kitchen window
        B.bm_segment_box(bm, (kx + kw / 2, y1), (x1, y1), zf, ze, t, 0)
        B.bm_segment_box(bm, (kx - kw / 2, y1), (kx + kw / 2, y1), zf, kz0, t, 0)
        B.bm_segment_box(bm, (kx - kw / 2, y1), (kx + kw / 2, y1), kz1, ze, t, 0)
        # gable roof, ridge N-S (along Y)
        ov = 0.45
        pts = [(x0 - ov, ze - 0.15), (x1 + ov, ze - 0.15), ((x0 + x1) / 2, zr)]
        a = [bm.verts.new((px_, y0 - ov, pz)) for px_, pz in pts]
        b_ = [bm.verts.new((px_, y1 + ov, pz)) for px_, pz in pts]
        fs = [bm.faces.new(a), bm.faces.new(list(reversed(b_)))]
        for i in range(3):
            j = (i + 1) % 3
            fs.append(bm.faces.new((a[i], a[j], b_[j], b_[i])))
        for f in fs[2:]:
            f.material_index = 3
        for f in fs[:2]:
            f.material_index = 0
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        # windows (frames + glass) front / back / south, upstairs + ground
        def window(cx_, cy_, cz, face, wdt=1.1, hgt=1.35):
            if face in ("w", "e"):
                sx = -1 if face == "w" else 1
                S.bm_box(bm, (cx_ + sx * 0.12, cy_, cz), (0.06, wdt + 0.16, hgt + 0.16), 1)
                S.bm_box(bm, (cx_ + sx * 0.15, cy_, cz), (0.04, wdt, hgt), 4)
            else:
                sy = -1 if face == "s" else 1
                S.bm_box(bm, (cx_, cy_ + sy * 0.12, cz), (wdt + 0.16, 0.06, hgt + 0.16), 1)
                S.bm_box(bm, (cx_, cy_ + sy * 0.15, cz), (wdt, 0.04, hgt), 4)
        for yy in (-3.8, 3.8):
            window(x0, yy, 1.85, "w")
        for yy in (-3.8, 0.0, 3.8):
            window(x0, yy, 4.4, "w")
            window(x1, yy, 4.4, "e")
        window(x1, 3.8, 1.85, "e")
        for xx in (2.5, 7.2):
            window(xx, y0, 1.85, "s")
            window(xx, y0, 4.4, "s")
        window(2.5, y1, 4.4, "n")
        window(7.0, y1, 4.4, "n")
        # front door (navy) + back door
        S.bm_box(bm, (x0 - 0.12, 0.0, zf + 1.05), (0.06, 1.15, 2.2), 1)
        S.bm_box(bm, (x0 - 0.15, 0.0, zf + 1.02), (0.05, 0.95, 2.05), 5)
        S.bm_box(bm, (x1 + 0.13, -1.0, zf + 1.02), (0.05, 0.95, 2.05), 1)
        # kitchen window frame (open: glass is a separate thin transparent pane)
        S.bm_box(bm, (kx, y1 + 0.12, kz0 - 0.04), (kw + 0.2, 0.1, 0.08), 1)
        S.bm_box(bm, (kx, y1 + 0.12, kz1 + 0.04), (kw + 0.2, 0.1, 0.08), 1)
        for sx in (-1, 1):
            S.bm_box(bm, (kx + sx * (kw / 2 + 0.05), y1 + 0.12, (kz0 + kz1) / 2), (0.08, 0.1, kz1 - kz0 + 0.16), 1)
        B.mesh_obj("mh_house", bm, [siding, trim, found, roof, winm, navy])
        glass = bmesh.new()
        S.bm_box(glass, (0, 0, 0), (kw, 0.01, kz1 - kz0), 0)
        B.mesh_obj("mh_kitchen_glass", glass, [self._clear_glass()], loc=(kx, y1 + 0.02, (kz0 + kz1) / 2))
        self._kitchen_backdrop(kx, y1, zf)
        # porch (8 ft deep), posts, shed roof, steps, porch light
        pz = self.z["porch"]
        deck = B.mat_bands("mh_porch_deck", hexc("9b8a74"), 0.14, "Y", 0.3, 0.8)
        bm = bmesh.new()
        S.bm_box(bm, (-1.22, 0, zf / 2), (2.44, 8.0, zf), 0)
        for yy in (-3.8, 3.8):
            S.bm_box(bm, (-2.3, yy, 1.75), (0.16, 0.16, 2.6), 1)
        for k in range(2):
            S.bm_box(bm, (-2.44 - 0.3 - k * 0.3, 0, zf - 0.15 - k * 0.15), (0.3, 2.2, 0.15), 0)
        B.mesh_obj("mh_porch", bm, [deck, trim])
        bm = bmesh.new()
        v = [bm.verts.new(p) for p in ((-2.75, -4.2, 3.05), (0.0, -4.2, 3.55), (0.0, 4.2, 3.55), (-2.75, 4.2, 3.05))]
        f = bm.faces.new(v)
        bmesh.ops.solidify(bm, geom=[f], thickness=0.12)
        B.mesh_obj("mh_porch_roof", bm, [roof])
        lamp_m = B.mat_glow("mh_porch_lamp", hexc("f4efe4"), 0.0, emit=hexc("ffd59a"))
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0), (0.14, 0.14, 0.24), 0)
        B.mesh_obj("mh_porch_lamp", bm, [lamp_m], loc=(x0 - 0.12, 0.85, 2.45))
        pl = bpy.data.lights.new("mh_porch_light", "POINT")
        pl.energy = 0.0
        pl.color = (1.0, 0.78, 0.5)
        pl.shadow_soft_size = 0.15
        plo = L.link(bpy.data.objects.new("mh_porch_light", pl))
        plo.location = (x0 - 0.5, 0.85, 2.4)
        self.add_light("porch", B.emission_socket(lamp_m), "default_value", 12.0, 0.0)
        self.add_light("porch", pl, "energy", 60.0, 0.0)
        # attached 2-car garage (roll-up door on the west face)
        g = z["garage"]
        gx0, gx1 = g["pos"][0] - g["size"][0] / 2, g["pos"][0] + g["size"][0] / 2
        gy0, gy1 = g["pos"][1] - g["size"][1] / 2, g["pos"][1] + g["size"][1] / 2
        bm = bmesh.new()
        S.bm_box(bm, ((gx0 + gx1) / 2, (gy0 + gy1) / 2, 1.6), (gx1 - gx0, gy1 - gy0, 3.2), 0)
        S.bm_prism_x(bm, gx0 - 0.4, gx1 + 0.4, [(gy0 - 0.4, 3.1), (gy1 + 0.1, 3.1), ((gy0 + gy1) / 2, 4.8)], 1)
        B.mesh_obj("mh_garage", bm, [siding, roof])
        gd = B.mat_bands("mh_garage_door", hexc("f1f0ec"), 0.53, "Z", 0.6, 0.5)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0), (0.08, 4.9, 2.15), 0)
        B.mesh_obj("mh_garage_door", bm, [gd], loc=(gx0 - 0.04, g["pos"][1], 1.09))
        outlet = bmesh.new()
        S.bm_box(outlet, (0, 0, 0), (0.03, 0.08, 0.12), 0)
        B.mesh_obj("mh_nema_outlet", outlet, [trim], loc=(gx0 - 0.02, g["pos"][1] + 2.9, 0.5))
        self.stats["house_ridge_z"] = zr
        return {"house_top": (x1 + 0.1, y0 - 0.1, zr)}

    def _clear_glass(self):
        """s8: mostly see-through pane: Transparent BSDF + a faint Fresnel gloss (was transmission 1 + alpha .25, which
        veiled the kitchen and left the denoiser nothing to resolve behind the glass at low samples)."""
        def mk():
            m, nt, N, Lk, p = S._new_mat("mh_clear_glass")
            N.remove(p)
            tr = N.new("ShaderNodeBsdfTransparent")
            tr.inputs["Color"].default_value = (0.96, 0.98, 1.0, 1.0)
            gl = N.new("ShaderNodeBsdfGlossy")
            gl.inputs["Roughness"].default_value = 0.02
            gl.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            lw = N.new("ShaderNodeLayerWeight")
            lw.inputs["Blend"].default_value = 0.12
            k = N.new("ShaderNodeMath"); k.operation = "MULTIPLY"; k.inputs[1].default_value = 0.55
            Lk.new(lw.outputs["Fresnel"], k.inputs[0])
            mx = N.new("ShaderNodeMixShader")
            Lk.new(k.outputs[0], mx.inputs[0])
            Lk.new(tr.outputs[0], mx.inputs[1])
            Lk.new(gl.outputs[0], mx.inputs[2])
            return S._finish(m, mx.outputs[0], haze=False)
        return B._cached("mh_clear_glass", mk)

    def _tile_mat(self):
        """White subway-tile backsplash (7.5 x 15 cm, grey grout), procedural brick on the wall's X/Z."""
        def mk():
            m, nt, N, Lk, p = S._new_mat("mh_kitchen_tile")
            vec = S._coord(N, Lk, "Object")
            sep = N.new("ShaderNodeSeparateXYZ")
            Lk.new(vec, sep.inputs[0])
            cmb = N.new("ShaderNodeCombineXYZ")
            Lk.new(sep.outputs["X"], cmb.inputs["X"])
            Lk.new(sep.outputs["Z"], cmb.inputs["Y"])
            br = N.new("ShaderNodeTexBrick")
            br.inputs["Scale"].default_value = 1.0
            br.inputs["Brick Width"].default_value = 0.15
            br.inputs["Row Height"].default_value = 0.075
            br.inputs["Mortar Size"].default_value = 0.004
            br.inputs["Color1"].default_value = hexc("f2f1ec")
            br.inputs["Color2"].default_value = hexc("e6e7e3")
            br.inputs["Mortar"].default_value = hexc("9a978f")
            Lk.new(cmb.outputs[0], br.inputs["Vector"])
            Lk.new(br.outputs["Color"], p.inputs["Base Color"])
            p.inputs["Roughness"].default_value = 0.18
            try:
                p.inputs["Coat Weight"].default_value = 0.3
            except Exception:
                pass
            inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
            Lk.new(br.outputs["Fac"], inv.inputs[1])
            S._bump(N, Lk, inv.outputs[0], p, 0.4, 0.004)
            return S._finish(m, p.outputs[0], haze=False)
        return B._cached("mh_kitchen_tile", mk)

    def _kitchen_backdrop(self, kx, y1, zf):
        """A lit, low-poly kitchen nook behind the north kitchen window (only what the window can show)."""
        wall = S.pbr("mh_kitchen_wall", hexc("e9e2d2"), 0.8, var=0.03)
        cab = S.pbr("mh_cabinet", hexc("f5f4f0"), 0.5, var=0.02)
        top = S.pbr("mh_butcher", hexc("a8794a"), 0.55, var=0.08)
        fridge = S.pbr("mh_fridge", hexc("e8eaec"), 0.25, metal=0.2)
        shade = B.mat_glow("mh_lamp_shade", hexc("ffe2b0"), 4.0)
        ceil = B.mat_glow("mh_kitchen_ceiling", hexc("fff4e2"), 1.2)
        bm = bmesh.new()
        yb = y1 - 2.6
        S.bm_box(bm, (kx, yb, zf + 1.4), (4.0, 0.1, 2.8), 0)                       # back wall
        for sx in (-1, 1):
            S.bm_box(bm, (kx + sx * 2.0, (yb + y1) / 2, zf + 1.4), (0.1, 2.6, 2.8), 0)
        S.bm_box(bm, (kx, (yb + y1) / 2, zf + 0.02), (4.0, 2.6, 0.04), 2)
        S.bm_box(bm, (kx - 0.6, yb + 0.35, zf + 0.45), (2.0, 0.6, 0.9), 1)         # base cabinets + top
        S.bm_box(bm, (kx - 0.6, yb + 0.37, zf + 0.92), (2.05, 0.64, 0.05), 2)
        S.bm_box(bm, (kx - 0.6, yb + 0.2, zf + 1.9), (2.0, 0.35, 0.7), 1)          # upper cabinets
        S.bm_box(bm, (kx + 1.3, yb + 0.4, zf + 0.9), (0.8, 0.7, 1.8), 3)           # fridge
        S.bm_box(bm, (kx - 1.4, yb + 0.35, zf + 1.05), (0.12, 0.12, 0.25), 2)      # lamp base
        S.bm_box(bm, (kx - 1.4, yb + 0.35, zf + 1.3), (0.3, 0.3, 0.22), 4)         # lamp shade
        S.bm_box(bm, (kx, (yb + y1) / 2, zf + 2.78), (3.9, 2.5, 0.04), 5)
        # s8: subway-tile backsplash between counter and uppers (mat 6) + an under-cabinet LED strip (mat 7); both
        # survive the CC0 prop pass (it drops mats 1/3/4 and high mat-2 faces only)
        S.bm_box(bm, (kx - 0.47, yb + 0.06, zf + 1.235), (3.06, 0.012, 0.63), 6)
        S.bm_box(bm, (kx - 0.7, yb + 0.12, zf + 1.535), (2.1, 0.04, 0.02), 7)
        led = B.mat_glow("mh_kitchen_led", hexc("fff1dc"), 6.0)
        B.mesh_obj("mh_kitchen_backdrop", bm, [wall, cab, top, fridge, shade, ceil, self._tile_mat(), led])
        self.add_light("kitchen", B.emission_socket(ceil), "default_value", 1.2, 0.0)
        self.add_light("kitchen", B.emission_socket(led), "default_value", 6.0, 0.0)
        # s8: a real ceiling area light (keyed with the kitchen lights, off when the kitchen is off)
        kl = bpy.data.lights.new("mh_kitchen_light", "AREA")
        kl.shape = "RECTANGLE"
        kl.size, kl.size_y = 2.8, 1.6
        kl.energy = 0.0
        kl.color = (1.0, 0.9, 0.78)
        klo = L.link(bpy.data.objects.new("mh_kitchen_light", kl))
        klo.location = (kx, yb + 1.1, zf + 2.7)
        self.add_light("kitchen", kl, "energy", 140.0, 0.0)
        self.anchor_pts = getattr(self, "anchor_pts", {})
        self.anchor_pts.update({"fridge": (kx + 1.3, yb + 0.4, zf + 1.2), "lamp": (kx - 1.4, yb + 0.35, zf + 1.3)})

    # ---------------------------------------------------------------- yard
    def build_yard(self):
        B.part_collection("yard")
        z = self.z
        rng = random.Random(11)
        # privacy fence (boards = slabs, posts = GN instances)
        fx = B.mat_bands("mh_fence_x", hexc("a47551"), 0.14, "X", 0.3, 0.85, 0.08)
        fy = B.mat_bands("mh_fence_y", hexc("a47551"), 0.14, "Y", 0.3, 0.85, 0.08)
        fence = z["back_yard"]["fence"]
        bm = bmesh.new()
        posts = []
        for a, b in zip(fence, fence[1:]):
            mi = 0 if abs(b[1] - a[1]) < abs(b[0] - a[0]) else 1
            za, zb = H(*a), H(*b)
            B.bm_segment_box(bm, a, b, (za + 0.05, zb + 0.05), (za + 1.83, zb + 1.83), 0.04, mi)
            Lg = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(Lg / 2.44))
            for k in range(n + 1):
                t = k / float(n)
                px_, py_ = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                posts.append((px_, py_, H(px_, py_)))
        B.mesh_obj("mh_privacy_fence", bm, [fx, fy])
        pbm = bmesh.new()
        S.bm_box(pbm, (0, 0, 0.97), (0.1, 0.1, 1.95), 0)
        tpl = B.template_obj("tpl_fence_post", S.mesh_from_bm("tpl_fence_post", pbm, [S.pbr("mh_post", hexc("8d6646"), 0.85, var=0.1)]))
        B.scatter_gn("mh_fence_posts", tpl, posts)
        # split-rail fence on the meadow (instanced posts + rails)
        srf = z["meadow"].get("split_rail_fence", [])
        if srf:
            sp = bmesh.new()
            S.bm_box(sp, (0, 0, 0.6), (0.14, 0.14, 1.2), 0)
            tps = B.template_obj("tpl_split_post", S.mesh_from_bm("tpl_split_post", sp, [S.pbr("mh_oldwood", hexc("8a7d6a"), 0.9, var=0.15)]))
            pts, rails = [], bmesh.new()
            for a, b in zip(srf, srf[1:]):
                Lg = math.hypot(b[0] - a[0], b[1] - a[1])
                n = max(1, int(Lg / 3.0))
                prev = None
                for k in range(n + 1):
                    t = k / float(n)
                    px_, py_ = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                    pz_ = H(px_, py_)
                    pts.append((px_, py_, pz_))
                    if prev:
                        for hz in (0.55, 0.95):
                            B.bm_cyl(rails, (prev[0], prev[1], prev[2] + hz), (px_, py_, pz_ + hz), 0.06, 0.06, 5, 0, False)
                    prev = (px_, py_, pz_)
            B.scatter_gn("mh_split_posts", tps, pts)
            B.mesh_obj("mh_split_rails", rails, [S.pbr("mh_oldwood", hexc("8a7d6a"), 0.9, var=0.15)])
        # deck + grill
        d = z["deck"]
        deck = B.mat_bands("mh_deck_wood", hexc("9a6a43"), 0.14, "X", 0.3, 0.8)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, -0.05), (d["size"][0], d["size"][1], 0.1), 0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                S.bm_box(bm, (sx * (d["size"][0] / 2 - 0.1), sy * (d["size"][1] / 2 - 0.1), -0.35), (0.12, 0.12, 0.6), 0)
        for sy in (-1, 1):
            S.bm_box(bm, (0, sy * (d["size"][1] / 2 - 0.04), 0.5), (d["size"][0], 0.08, 0.08), 0)
        S.bm_box(bm, (d["size"][0] / 2 - 0.04, 0, 0.5), (0.08, d["size"][1], 0.08), 0)
        B.mesh_obj("mh_deck", bm, [deck], loc=(d["pos"][0], d["pos"][1], d["pos"][2]))
        gr = z["grill"]
        blk = S.pbr("mh_grill", hexc("1d1e20"), 0.35, metal=0.6)
        bm = bmesh.new()
        B.bm_sphere(bm, (0, 0, 0.85), (0.32, 0.32, 0.26), 2, 0)
        for k in range(3):
            a = k * 2.094
            B.bm_cyl(bm, (0.25 * math.cos(a), 0.25 * math.sin(a), 0.0), (0.1 * math.cos(a), 0.1 * math.sin(a), 0.7), 0.015, 0.015, 4, 0)
        B.mesh_obj("mh_grill", bm, [blk], loc=tuple(gr["pos"]))
        # hero oak + tire swing
        self._oak(z["oak_tree"])
        # picnic table
        pt = z["picnic_table"]
        wood = S.pbr("mh_weathered", hexc("8f7b62"), 0.85, var=0.1)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0.74), (1.8, 0.75, 0.05), 0)
        for sy in (-0.6, 0.6):
            S.bm_box(bm, (0, sy, 0.44), (1.8, 0.25, 0.04), 0)
        for sx in (-0.7, 0.7):
            for sy in (-1, 1):
                S.bm_box(bm, (sx, sy * 0.3, 0.37), (0.06, 0.06, 0.74), 0)
        B.mesh_obj("mh_picnic_table", bm, [wood], loc=(pt["pos"][0], pt["pos"][1], H(pt["pos"][0], pt["pos"][1])),
                   rot=(0, 0, math.radians(pt["yaw"])))
        # raised-bed garden (6 cedar beds) + instanced plants
        gz = z["garden"]
        cedar = S.pbr("mh_cedar", hexc("b07a4e"), 0.8, var=0.08)
        soil = S.pbr("mh_soil", hexc("3d2e22"), 0.95, var=0.15, var_scale=4.0, bump=0.3)
        bm = bmesh.new()
        beds = []
        for i in range(3):
            for j in range(2):
                bx_ = gz["pos"][0] - 3.4 + i * 3.4
                by_ = gz["pos"][1] - 2.2 + j * 4.4
                beds.append((bx_, by_))
                S.bm_box(bm, (bx_, by_, 0.2), (1.22, 3.05, 0.4), 0)
                S.bm_box(bm, (bx_, by_, 0.401), (1.1, 2.93, 0.01), 1)
        B.mesh_obj("mh_garden_beds", bm, [cedar, soil], loc=(0, 0, H(gz["pos"][0], gz["pos"][1])))
        leaf = S.pbr("mh_veg", hexc("4f7f34"), 0.8, var=0.15, bump=0.2)
        vb = bmesh.new()
        B.bm_sphere(vb, (0, 0, 0.2), (0.22, 0.22, 0.25), 1, 0, 0.2, 1)
        tveg = B.template_obj("tpl_veg", S.mesh_from_bm("tpl_veg", vb, [leaf], smooth=True))
        cb = bmesh.new()
        B.bm_cyl(cb, (0, 0, 0), (0, 0, 1.6), 0.03, 0.02, 5, 0)
        for k in range(4):
            a = k * 1.57
            B.bm_cyl(cb, (0, 0, 0.5 + k * 0.25), (0.3 * math.cos(a), 0.3 * math.sin(a), 0.9 + k * 0.25), 0.02, 0.005, 3, 0)
        tcorn = B.template_obj("tpl_corn", S.mesh_from_bm("tpl_corn", cb, [S.pbr("mh_corn", hexc("7f9a3c"), 0.8)]))
        vp, cp = [], []
        gz0 = H(gz["pos"][0], gz["pos"][1]) + 0.4
        for k, (bx_, by_) in enumerate(beds):
            for s in range(5):
                (cp if k == 1 else vp).append((bx_ + rng.uniform(-0.3, 0.3), by_ - 1.2 + s * 0.6, gz0))
        B.scatter_gn("mh_veg", tveg, vp, [rng.uniform(0, 6.28) for _ in vp], [rng.uniform(0.8, 1.2) for _ in vp])
        B.scatter_gn("mh_corn", tcorn, cp, [rng.uniform(0, 6.28) for _ in cp], [rng.uniform(0.9, 1.1) for _ in cp])
        # goose house (white A-frame) + wire run
        gh = z["goose_house"]
        white = S.pbr("mh_goose_house", hexc("f1f1ec"), 0.7, var=0.04)
        dark = S.pbr("mh_dark_door", hexc("2a2622"), 0.9)
        bm = bmesh.new()
        S.bm_prism_x(bm, -0.75, 0.75, [(-0.6, 0.0), (0.6, 0.0), (0.0, 1.3)], 0)
        S.bm_box(bm, (-0.77, 0, 0.35), (0.04, 0.45, 0.6), 1)
        B.mesh_obj("mh_goose_house", bm, [white, dark], loc=tuple(gh["pos"]), rot=(0, 0, math.radians(gh["yaw"] - 180)))
        wire = S.pbr("mh_wire_run", hexc("9aa0a4"), 0.4, metal=0.7)
        bm = bmesh.new()
        corners = [(gh["pos"][0] + dx, gh["pos"][1] + dy) for dx, dy in ((0.9, -1.5), (3.9, -1.5), (3.9, 1.5), (0.9, 1.5))]
        for (ax_, ay_), (bx_, by_) in zip(corners, corners[1:] + corners[:1]):
            za, zb = H(ax_, ay_), H(bx_, by_)
            B.bm_cyl(bm, (ax_, ay_, za), (ax_, ay_, za + 0.9), 0.025, 0.025, 4, 0)
            B.bm_cyl(bm, (ax_, ay_, za + 0.9), (bx_, by_, zb + 0.9), 0.01, 0.01, 3, 0, False)
        B.mesh_obj("mh_wire_run", bm, [wire])
        # hose reel, A/C condenser, propane tank
        hr = z["hose_reel"]
        green = S.pbr("mh_hose", hexc("2f7a3a"), 0.6)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0.4), (0.06, 0.06, 0.8), 0)
        self._torus(bm, (0.12, 0, 0.6), 0.22, 0.07, "X", 1)
        B.mesh_obj("mh_hose_reel", bm, [S.pbr("mh_bracket", hexc("5a5d60"), 0.5, metal=0.5), green], loc=(hr["pos"][0], hr["pos"][1], 0))
        ac = z["ac_condenser"]
        gray = S.pbr("mh_ac", hexc("b8bcbf"), 0.45, metal=0.3)
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0.08), (1.1, 1.1, 0.16), 1)
        S.bm_box(bm, (0, 0, 0.6), (0.9, 0.9, 0.9), 0)
        B.mesh_obj("mh_ac_unit", bm, [gray, B.mat_ph("mh_concrete", hexc("c9c4ba"), "concrete_floor_02", 0.35, 0.8)],
                   loc=(ac["pos"][0], ac["pos"][1], 0))
        fan = bmesh.new()
        bmesh.ops.create_circle(fan, cap_ends=True, segments=20, radius=0.36)
        B.mesh_obj("mh_ac_fan", fan, [S.pbr("mh_fan", hexc("2a2c2e"), 0.5)], loc=(ac["pos"][0], ac["pos"][1], 1.06))
        pr = z["propane_tank"]
        tank = S.pbr("mh_propane", hexc("f2f3f1"), 0.35, metal=0.2, coat=0.3)
        bm = bmesh.new()
        B.bm_cyl(bm, (-0.75, 0, 0.62), (0.75, 0, 0.62), 0.5, 0.5, 16, 0, False)
        for sx in (-0.75, 0.75):
            B.bm_uvsphere(bm, (sx, 0, 0.62), 0.5, 16, 8, 0)
        for sx in (-0.5, 0.5):
            S.bm_box(bm, (sx, 0, 0.1), (0.12, 0.5, 0.2), 1)
        B.mesh_obj("mh_propane_tank", bm, [tank, S.pbr("mh_bracket", hexc("5a5d60"), 0.5, metal=0.5)],
                   loc=(pr["pos"][0], pr["pos"][1], 0))
        # gravel path
        path = [tuple(p) for p in z["gravel_path"]["polyline"]]
        bm = bmesh.new()
        prev = None
        for (ax_, ay_), (bx_, by_) in zip(path, path[1:]):
            n = max(1, int(math.hypot(bx_ - ax_, by_ - ay_) / 1.0))
            dx, dy = (bx_ - ax_), (by_ - ay_)
            Lg = math.hypot(dx, dy)
            nx_, ny_ = -dy / Lg * 1.5, dx / Lg * 1.5
            for k in range(n + 1):
                t = k / float(n)
                px_, py_ = ax_ + dx * t, ay_ + dy * t
                row = [bm.verts.new((px_ - nx_, py_ - ny_, H(px_ - nx_, py_ - ny_) + 0.03)),
                       bm.verts.new((px_ + nx_, py_ + ny_, H(px_ + nx_, py_ + ny_) + 0.03))]
                if prev:
                    bm.faces.new((prev[0], prev[1], row[1], row[0]))
                prev = row
        B.mesh_obj("mh_gravel_path", bm, [B.mat_ph("mh_gravel", hexc("b3a58c"), "concrete_floor_02", 0.6, 0.9, scale_mul=0.5)])
        # mailbox (red flag up)
        mb = z["mailbox"]
        bm = bmesh.new()
        S.bm_box(bm, (0, 0, 0.55), (0.1, 0.1, 1.1), 0)
        S.bm_box(bm, (0, 0, 1.15), (0.5, 0.24, 0.2), 1)
        B.bm_cyl(bm, (-0.25, 0, 1.25), (0.25, 0, 1.25), 0.12, 0.12, 10, 1, True)
        S.bm_box(bm, (0.05, 0.14, 1.32), (0.03, 0.02, 0.2), 2)
        S.bm_box(bm, (0.09, 0.14, 1.4), (0.1, 0.02, 0.06), 2)
        B.mesh_obj("mh_mailbox", bm, [S.pbr("mh_post", hexc("8d6646"), 0.85, var=0.1),
                                      S.pbr("mh_mailbox_metal", hexc("3b3e42"), 0.4, metal=0.6),
                                      S.pbr("mh_flag", hexc("e63946"), 0.5)], loc=(mb["pos"][0], mb["pos"][1], 0))

    def _torus(self, bm, c, R, r, axis, mi, seg=16, ring=8):
        verts = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            row = []
            for j in range(ring):
                b = 2 * math.pi * j / ring
                u = (R + r * math.cos(b))
                p = (u * math.cos(a), u * math.sin(a), r * math.sin(b))
                if axis == "X":
                    p = (p[2], p[0], p[1])
                elif axis == "Y":
                    p = (p[0], p[2], p[1])
                row.append(bm.verts.new((c[0] + p[0], c[1] + p[1], c[2] + p[2])))
            verts.append(row)
        for i in range(seg):
            for j in range(ring):
                f = bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % ring],
                                  verts[i][(j + 1) % ring]))
                f.material_index = mi

    def _oak(self, oz):
        x, y = oz["pos"][0], oz["pos"][1]
        z0 = H(x, y)
        sw = oz["tire_swing"]
        if MC.hero_oak(x, y, z0, sw) is not None:
            rope = S.pbr("mh_rope", hexc("c2a878"), 0.9)
            tire = S.pbr("mh_tire", hexc("1e1e1e"), 0.7)
            bm = bmesh.new()
            B.bm_cyl(bm, (0, 0, 5.0 - sw[2] - 0.05), (0, 0, 0.45), 0.015, 0.015, 4, 0, False)
            self._torus(bm, (0, 0, 0.0), 0.34, 0.12, "Y", 1)
            B.mesh_obj("mh_tire_swing", bm, [rope, tire], smooth=True, loc=(sw[0], sw[1], z0 + sw[2] + 0.4))
            return
        bark = S.pbr("mh_bark", hexc("5a4632"), 0.9, var=0.12, var_scale=3.0, bump=0.35)
        leaf = S.pbr("mh_oak_leaf", hexc("4f7a35"), 0.85, var=0.18, var_scale=1.2, bump=0.15)
        rng = random.Random(27)
        bm = bmesh.new()
        B.bm_cyl(bm, (0, 0, -0.3), (0, 0, 5.2), 0.55, 0.38, 10, 0)
        arms = []
        for k in range(5):
            a = k * 1.256 + 0.3
            tip = (3.8 * math.cos(a), 3.8 * math.sin(a), 7.5 + rng.uniform(-0.6, 0.8))
            B.bm_cyl(bm, (0, 0, 4.6), tip, 0.3, 0.12, 7, 0)
            arms.append(tip)
        sw = oz["tire_swing"]
        bx_, by_ = sw[0] - x, sw[1] - y
        B.bm_cyl(bm, (0, 0, 4.4), (bx_ * 1.15, by_ * 1.15, 5.0), 0.22, 0.12, 7, 0)
        for i, (ax_, ay_, az_) in enumerate(arms + [(0, 0, 10.5), (1.5, -1.0, 11.5), (-1.6, 1.2, 11.2)]):
            B.bm_sphere(bm, (ax_, ay_, az_ + 1.2), (rng.uniform(2.6, 3.6), rng.uniform(2.6, 3.6), rng.uniform(2.0, 2.8)),
                        2, 1, 0.18, i)
        B.mesh_obj("mh_oak", bm, [bark, leaf], smooth=True, loc=(x, y, z0))
        rope = S.pbr("mh_rope", hexc("c2a878"), 0.9)
        tire = S.pbr("mh_tire", hexc("1e1e1e"), 0.7)
        bm = bmesh.new()
        B.bm_cyl(bm, (0, 0, 5.0 - sw[2] - 0.05), (0, 0, 0.45), 0.015, 0.015, 4, 0, False)
        self._torus(bm, (0, 0, 0.0), 0.34, 0.12, "Y", 1)
        B.mesh_obj("mh_tire_swing", bm, [rope, tire], loc=(sw[0], sw[1], z0 + sw[2] + 0.4))

    # ---------------------------------------------------------------- workshop + lean-to shed
    def build_workshop(self):
        B.part_collection("workshop")
        w = self.z["workshop"]
        x0, x1 = w["pos"][0] - w["size"][0] / 2, w["pos"][0] + w["size"][0] / 2
        y0, y1 = w["pos"][1] - w["size"][1] / 2, w["pos"][1] + w["size"][1] / 2
        wx = B.mat_bands("mh_barn_x", hexc("8c3b2e"), 0.3, "X", 0.5, 0.8, 0.06)
        wy = B.mat_bands("mh_barn_y", hexc("8c3b2e"), 0.3, "Y", 0.5, 0.8, 0.06)
        roofm = S.corrugated_mat("mh_barn_roof", hexc("8e9398"), 0.2, 0.45, 0.6)
        trim = S.pbr("mh_trim", hexc("f3f2ee"), 0.6, var=0.02)
        door = B.mat_bands("mh_rollup", hexc("d9dbdc"), 0.4, "Z", 0.5, 0.5)
        zw, zr = 4.0, 6.0
        bm = bmesh.new()
        B.bm_segment_box(bm, (x0, y0), (x1, y0), 0.0, zw, 0.2, 0)
        B.bm_segment_box(bm, (x0, y1), (x1, y1), 0.0, zw, 0.2, 0)
        B.bm_segment_box(bm, (x0, y0), (x0, y1), 0.0, zw, 0.2, 1)
        B.bm_segment_box(bm, (x1, y0), (x1, y1), 0.0, zw, 0.2, 1)
        for sx in (x0, x1):          # gable ends (triangles) on the west/east faces
            v = [bm.verts.new((sx, y0, zw)), bm.verts.new((sx, y1, zw)), bm.verts.new((sx, (y0 + y1) / 2, zr))]
            f = bm.faces.new(v)
            f.material_index = 1
        S.bm_prism_x(bm, x0 - 0.4, x1 + 0.4, [(y0 - 0.45, zw - 0.1), (y1 + 0.45, zw - 0.1), ((y0 + y1) / 2, zr + 0.05)], 2)
        S.bm_box(bm, (x0 - 0.06, w["pos"][1], 1.65), (0.08, 3.8, 3.3), 3)        # roll-up door frame
        S.bm_box(bm, (x0 - 0.1, w["pos"][1], 1.6), (0.06, 3.6, 3.2), 4)
        S.bm_box(bm, (x0 - 0.06, y0 + 1.2, 1.05), (0.08, 0.95, 2.1), 3)
        B.mesh_obj("mh_workshop", bm, [wx, wy, roofm, trim, door])
        # lean-to battery shed against the south wall (front open to the south)
        sh = self.z["battery_shed"]
        sx0, sx1 = sh["pos"][0] - 3.0, sh["pos"][0] + 3.0
        sy1 = y0 - 0.1
        sy0 = sy1 - 3.7
        bm = bmesh.new()
        B.bm_segment_box(bm, (sx0, sy0), (sx0, sy1), 0.0, (2.4, 3.2), 0.12, 1)
        B.bm_segment_box(bm, (sx1, sy0), (sx1, sy1), 0.0, (2.4, 3.2), 0.12, 1)
        S.bm_box(bm, ((sx0 + sx1) / 2, (sy0 + sy1) / 2, 0.05), (sx1 - sx0, sy1 - sy0, 0.1), 3)
        v = [bm.verts.new(p) for p in ((sx0 - 0.3, sy0 - 0.4, 2.35), (sx1 + 0.3, sy0 - 0.4, 2.35),
                                       (sx1 + 0.3, sy1, 3.25), (sx0 - 0.3, sy1, 3.25))]
        f = bm.faces.new(v)
        f.material_index = 2
        S.bm_box(bm, ((sx0 + sx1) / 2, sy0 + 0.05, 2.3), (sx1 - sx0, 0.14, 0.14), 1)
        B.mesh_obj("mh_battery_shed", bm, [wx, wy, roofm, B.mat_ph("mh_concrete", hexc("c9c4ba"), "concrete_floor_02", 0.35, 0.8)])
        ld = bpy.data.lights.new("mh_shed_light", "AREA")         # stills 24 Nov: shed interior read as black
        ld.size, ld.energy, ld.color = 2.2, 220.0, (1.0, 0.9, 0.75)
        lo = L.link(bpy.data.objects.new("mh_shed_light", ld))
        lo.location = ((sx0 + sx1) / 2, (sy0 + sy1) / 2 + 0.6, 2.15)
        rack = S.pbr("mh_rack", hexc("6d7378"), 0.45, metal=0.7)
        bm = bmesh.new()
        rx0, rx1, ry = sh["pos"][0] - 2.0, sh["pos"][0] + 2.0, sy1 - 0.45
        for sx_ in (rx0, rx1):
            for sy_ in (ry - 0.3, ry + 0.3):
                S.bm_box(bm, (sx_, sy_, 0.9), (0.05, 0.05, 1.8), 0)
        for zz in (0.15, 0.85, 1.55):
            S.bm_box(bm, ((rx0 + rx1) / 2, ry, zz), (rx1 - rx0, 0.65, 0.04), 0)
        S.bm_box(bm, (sh["pos"][0] + 2.6, sy1 - 0.08, 1.6), (0.5, 0.1, 0.7), 1)       # inverter box on the wall
        for zz in (0.17, 0.87):                       # the battery bank itself (stills 24 Nov: rack was empty)
            for i in range(5):
                bx = rx0 + 0.45 + i * (rx1 - rx0 - 0.9) / 4.0
                S.bm_box(bm, (bx, ry, zz + 0.2), (0.34, 0.5, 0.38), 2)
                for dx_, mi in ((-0.08, 3), (0.08, 4)):                     # + / - terminals
                    S.bm_box(bm, (bx + dx_, ry - 0.12, zz + 0.41), (0.05, 0.05, 0.04), mi)
        B.mesh_obj("mh_battery_rack", bm, [rack, S.pbr("mh_inverter", hexc("e6e8ea"), 0.4),
                                           S.pbr("mh_battery", hexc("1d2a3a"), 0.55),
                                           S.pbr("mh_term_red", hexc("c8282d"), 0.4), S.pbr("mh_term_blk", hexc("151515"), 0.4)])
        self.anchor_pts = getattr(self, "anchor_pts", {})
        self.anchor_pts.update({"battery_rack": ((rx0 + rx1) / 2, ry, 1.0), "shed_switch": (sh["pos"][0] + 2.6, sy1 - 0.1, 1.6)})

    # ---------------------------------------------------------------- props: red pickup
    def build_props(self):
        B.part_collection("props")
        rp = self.z["red_pickup"]
        o = MC.pickup(self.stats) if MC.enabled() else self._pickup()
        o.location = (rp["pos"][0], rp["pos"][1], H(rp["pos"][0], rp["pos"][1]))
        o.rotation_euler = (0, 0, math.radians(rp["yaw"]))
        self.cast["pickup"] = o

    def _pickup(self):
        """Generic 1990s regular-cab pickup, 8 ft bed, no badges/text (character.json vehicles.red_pickup)."""
        red = S.pbr("mh_truck_red", hexc("b3261e"), 0.35, coat=0.4, var=0.05)
        fade = S.pbr("mh_truck_faded", hexc("a3302a"), 0.55, coat=0.1, var=0.08)
        chrome = S.pbr("mh_bumper", hexc("c8ccd0"), 0.25, metal=0.9)
        black = S.pbr("mh_grille", hexc("2b2b2b"), 0.5)
        tire = S.pbr("mh_tire", hexc("1e1e1e"), 0.7)
        glass = S.glass_mat("mh_truck_glass", hexc("7fa3b5"))
        light = S.pbr("mh_lamp_lens", hexc("f0eee6"), 0.1)
        bm = bmesh.new()
        # local frame: front faces +X, length 5.4 (x -2.7..2.7), width 2.0, height 1.85
        S.bm_box(bm, (1.75, 0, 0.85), (1.9, 1.95, 0.75), 0)       # hood/nose block
        S.bm_box(bm, (1.75, 0, 1.235), (1.85, 1.9, 0.02), 1)      # faded hood top
        S.bm_box(bm, (0.35, 0, 1.15), (1.0, 1.95, 1.35), 0)        # cab lower
        S.bm_box(bm, (0.35, 0, 1.84), (0.95, 1.85, 0.03), 1)       # faded roof
        S.bm_box(bm, (0.8, 0, 1.55), (0.06, 1.75, 0.55), 2)        # windshield (upright 90s)
        for sy in (-1, 1):
            S.bm_box(bm, (0.35, sy * 0.985, 1.55), (0.8, 0.02, 0.5), 2)
        S.bm_box(bm, (-1.6, 0, 0.62), (2.45, 1.95, 0.12), 0)       # bed floor
        for sy in (-1, 1):
            S.bm_box(bm, (-1.6, sy * 0.95, 0.98), (2.45, 0.08, 0.62), 0)
        S.bm_box(bm, (-2.8, 0, 0.98), (0.08, 1.95, 0.62), 0)       # tailgate
        S.bm_box(bm, (2.72, 0, 0.85), (0.04, 1.6, 0.45), 4)        # grille
        S.bm_box(bm, (2.78, 0, 0.5), (0.12, 2.0, 0.18), 3)         # bumpers
        S.bm_box(bm, (-2.9, 0, 0.5), (0.12, 2.0, 0.18), 3)
        for sy in (-0.72, 0.72):
            S.bm_box(bm, (2.75, sy, 0.95), (0.05, 0.3, 0.2), 6)
        for wx in (1.65, -1.65):
            for sy in (-0.88, 0.88):
                B.bm_cyl(bm, (wx, sy - 0.14 * (1 if sy > 0 else -1), 0.4), (wx, sy + 0.14 * (1 if sy > 0 else -1), 0.4),
                         0.4, 0.4, 16, 5)
        me = S.mesh_from_bm("mh_pickup", bm, [red, fade, glass, chrome, black, tire, light])
        o = S.obj("mh_pickup", me)
        self.stats["pickup_tris"] = sum(len(p.vertices) - 2 for p in me.polygons)
        return o

    # ---------------------------------------------------------------- trees (3 species x 2 LODs, GN instanced)
    def tree_templates(self):
        cc0 = MC.tree_templates()
        if cc0:
            self.stats["trees_cc0"] = True
            return cc0
        trunk = S.pbr("mh_trunk", hexc("5a4632"), 0.9, var=0.1, bump=0.2)
        leaves = {"oak": S.pbr("mh_leaf_oak", hexc("4f7a35"), 0.85, var=0.16, var_scale=1.0, bump=0.12),
                  "maple": S.pbr("mh_leaf_maple", hexc("6b8f3e"), 0.85, var=0.18, var_scale=1.0, bump=0.12),
                  "pine": S.pbr("mh_leaf_pine", hexc("355a3a"), 0.85, var=0.12, bump=0.12)}
        out = {}
        for sp in ("oak", "maple", "pine"):
            for lod in (0, 1):
                bm = bmesh.new()
                sub = 2 if lod == 0 else 1
                if sp == "pine":
                    B.bm_cyl(bm, (0, 0, 0), (0, 0, 2.4), 0.25, 0.2, 6 if lod else 8, 0)
                    cones = ((3.0, 4.8, 5.6), (2.3, 7.6, 4.6), (1.4, 10.2, 3.4)) if lod == 0 else ((2.9, 5.4, 7.0), (1.6, 9.3, 4.6))
                    for r, zc, dz in cones:
                        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10 if lod == 0 else 6, radius1=r,
                                                    radius2=0.0, depth=dz)
                        bmesh.ops.translate(bm, vec=(0, 0, zc), verts=res["verts"])
                        for f in {f for v in res["verts"] for f in v.link_faces}:
                            f.material_index = 1
                else:
                    big = sp == "oak"
                    B.bm_cyl(bm, (0, 0, 0), (0, 0, 4.2), 0.32 if big else 0.26, 0.2, 7 if lod == 0 else 5, 0)
                    lobes = [((0, 0, 6.6), (3.4, 3.4, 3.0) if big else (3.0, 3.0, 3.4))]
                    if lod == 0:
                        lobes += [((1.6, 0.8, 8.0), (2.3, 2.3, 2.0)), ((-1.4, -0.9, 7.6), (2.2, 2.2, 2.0))]
                    for i, (c, r) in enumerate(lobes):
                        B.bm_sphere(bm, c, r, sub, 1, 0.14, i + (7 if big else 3))
                me = S.mesh_from_bm("tpl_%s_lod%d" % (sp, lod), bm, [trunk, leaves[sp]], smooth=sp != "pine")
                out[(sp, lod)] = B.template_obj("tpl_%s_lod%d" % (sp, lod), me)
        return out

    def build_trees(self):
        B.part_collection("trees")
        tpl = self.tree_templates()
        rng = random.Random(40)
        buckets = {k: ([], [], []) for k in tpl}
        core = (60.0, 10.0)
        px, py, _ = G.PAD

        spots = [tuple(v["pos"][:2]) for v in (self.ep.get("spots") or {}).values()
                 if isinstance(v, dict) and "pos" in v]

        def ok(x, y):
            if math.hypot(x - px, y - py) < 32.0:                 # ridge clearing (stills: canopies over the pad shots)
                return False
            if any(math.hypot(x - sx, y - sy) < 9.0 for sx, sy in spots):   # no tree on top of a camera spot
                return False
            if abs(x - G.creek_x(y)) < 4.0:
                return False
            if -20 < x < 36 and -76 < y < 24:                     # the lot core (house/yard/workshop/garden)
                return False
            for (ex, ey, er) in self.exclude:
                if math.hypot(x - ex, y - ey) < er:
                    return False
            return True

        def add(x, y, species=None, lod=None, scale=(0.85, 1.25)):
            sp = species or rng.choices(("oak", "maple", "pine"), (0.45, 0.4, 0.15) if self.stats.get("trees_cc0")
                                        else (0.4, 0.35, 0.25))[0]
            ld = lod if lod is not None else (0 if math.hypot(x - core[0], y - core[1]) < 150 else 1)
            pts, rots, scl = buckets[(sp, ld)]
            pts.append((x, y, H(x, y) - 0.1))
            rots.append(rng.uniform(0, 6.283))
            scl.append(rng.uniform(*scale))
        for poly in self.z["woods"]["regions"]:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            gx = min(xs)
            while gx < max(xs):
                gy = min(ys)
                while gy < max(ys):
                    x, y = gx + rng.uniform(-2.5, 2.5), gy + rng.uniform(-2.5, 2.5)
                    if point_in_poly(x, y, poly) and ok(x, y):
                        add(x, y)
                    gy += 6.3
                gx += 6.3
        for y in range(-100, 111, 9):                              # creek-side trees (gap at the views)
            if -20 < y < 45:
                continue
            for side in (-1, 1):
                if rng.random() < 0.55:
                    x = G.creek_x(y) + side * rng.uniform(4.5, 8.0)
                    if ok(x, y):
                        add(x, y, rng.choice(("maple", "oak")))
        for x in range(-210, -40, 17):                             # street trees + neighbour yards
            for sy in (-1, 1):
                if rng.random() < 0.75:
                    add(x + rng.uniform(-3, 3), sy * rng.uniform(9.5, 14.0), rng.choice(("maple", "oak")))
                if rng.random() < 0.6:
                    add(x + rng.uniform(-6, 6), sy * rng.uniform(32, 60))
        for (x, y) in ((-12, 30), (-24, 44), (-20, -32), (-4, -48), (14, -62), (30, -66), (40, -72), (-8, 60), (10, 48)):
            if ok(x, y):
                add(x, y)
        n_far = 0
        while n_far < 2200:                                         # far forest ring (LOD1)
            a = rng.uniform(0, 2 * math.pi)
            r = math.sqrt(rng.uniform(240 ** 2, 600 ** 2))
            x, y = 40 + r * math.cos(a), r * math.sin(a)
            if x < -30 and abs(y) < 16:
                continue
            if math.hypot(x + 500, y + 150) < 140 or math.hypot(x + 420, y + 260) < 30:
                continue
            add(x, y, lod=1, scale=(0.9, 1.4))
            n_far += 1
        total = 0
        for (sp, ld), (pts, rots, scl) in buckets.items():
            if pts:
                B.scatter_gn("mh_trees_%s_lod%d" % (sp, ld), tpl[(sp, ld)], pts, rots, scl)
                total += len(pts)
        self.stats["trees"] = total

    # ---------------------------------------------------------------- grass clumps near the camera waypoints
    def build_grass(self, focus):
        B.part_collection("grass")
        # s7: the "dark seam curves" on Torque at f1450 were the shadows of tall CC0 grass blades crossing his white
        # breast (they vanish without grass). Keep a small mown patch along his episode cast spots / walk paths.
        for beat in self.ep.get("beats", []):
            tq = (beat.get("shot", {}).get("cast") or {}).get("torque")
            if not tq or "at" not in tq:
                continue
            pts = [tuple(tq["at"][:2])] + [tuple(p[:2]) for p in tq.get("path", [])]
            for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[-1:]):
                n = max(1, int(math.hypot(bx - ax, by - ay) / 0.3))
                for k in range(n + 1):
                    self.exclude.append((ax + (bx - ax) * k / n, ay + (by - ay) * k / n, 0.6))
        if MC.enabled():
            gz, dw = self.z["garden"], self.z["driveway"]

            def blocked(x, y):
                if (x < -18 and abs(y) < 7.5) or (-21.5 < x < 0.6 and -14.3 < y < -6.4) or (-17.5 < x < -2.4 and abs(y) < 0.8):
                    return True                                            # road / driveway / front walk
                if (-2.8 < x < 10 and -14.4 < y < 7.0) or (21.3 < x < 34.6 and -41 < y < -25):
                    return True                                            # house + porch + garage / workshop + shed
                if abs(x - gz["pos"][0]) < gz["size"][0] / 2 + 0.3 and abs(y - gz["pos"][1]) < gz["size"][1] / 2 + 0.3:
                    return True
                if abs(x - G.creek_x(y)) < 2.0 or math.hypot(x - G.POND[0], y - G.POND[1]) < G.POND[2] + 0.4:
                    return True
                return any(math.hypot(x - ex, y - ey) < er for ex, ey, er in self.exclude)
            self.stats["grass_clumps"] = MC.grass(H, focus, blocked)
            if self.stats["grass_clumps"]:
                return
        bm = bmesh.new()
        rng = random.Random(3)
        for i in range(9):
            a = rng.uniform(0, 6.283)
            r = rng.uniform(0.0, 0.12)
            bx_, by_ = r * math.cos(a), r * math.sin(a)
            h = rng.uniform(0.25, 0.5)
            lean = rng.uniform(-0.08, 0.08)
            v = [bm.verts.new((bx_ - 0.025, by_, 0)), bm.verts.new((bx_ + 0.025, by_, 0)),
                 bm.verts.new((bx_ + lean, by_ + lean, h))]
            bm.faces.new(v)
        me = S.mesh_from_bm("tpl_grass", bm, [S.pbr("mh_grass_blade", hexc("6d8a3a"), 0.8, var=0.2, var_scale=6.0)])
        tpl = B.template_obj("tpl_grass", me)
        pts, rots, scl = [], [], []
        road = lambda x, y: (x < -18 and abs(y) < 7.5) or (-21 < x < 0.6 and -14.1 < y < -6.6)
        house = lambda x, y: (-2.6 < x < 10 and -14.2 < y < 6.9) or (21.5 < x < 34.5 and -41 < y < -25)
        seen = set()
        for (fx, fy) in focus:
            for k in range(260):
                a = rng.uniform(0, 6.283)
                r = 25.0 * math.sqrt(rng.random())
                x, y = fx + r * math.cos(a), fy + r * math.sin(a)
                key = (int(x * 2), int(y * 2))
                if key in seen or road(x, y) or house(x, y) or abs(x - G.creek_x(y)) < 2.2:
                    continue
                if any(math.hypot(x - ex, y - ey) < er for ex, ey, er in self.exclude):
                    continue
                seen.add(key)
                pts.append((x, y, H(x, y) - 0.02))
                rots.append(rng.uniform(0, 6.283))
                scl.append(rng.uniform(0.7, 1.5))
        B.scatter_gn("mh_grass", tpl, pts, rots, scl)
        self.stats["grass_clumps"] = len(pts)

    # ---------------------------------------------------------------- far: hills, water tower, town, ground
    def build_far(self):
        B.part_collection("far")
        far = self.loc["far"]
        S.plane_obj("mh_ground_far", 30000, 30000, (0, 0, -0.06), S.ground_mat())
        # s8: wooded ridges instead of 22 squashed spheres (they read as flat mint-green blobs). Three layered rings
        # of real terrain (noise skyline, spurs, crown-bumped treeline), a canopy shader (Voronoi crowns + gaps,
        # species patches) and stronger aerial perspective per distance via the scene fog (keyed per preset).
        R = far["hills"]["radius"]
        self._ridges(R)
        rng = random.Random(9)
        wt = far["water_tower"]
        c = hexc(wt["color"][1:])
        tm = S.pbr("mh_water_tower", c, 0.5, metal=0.4)
        bm = bmesh.new()
        h = wt["height"]
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            B.bm_cyl(bm, (5.0 * math.cos(a), 5.0 * math.sin(a), 0), (3.0 * math.cos(a), 3.0 * math.sin(a), h - 9), 0.3, 0.25, 6, 0)
        B.bm_cyl(bm, (0, 0, 0), (0, 0, h - 8), 0.6, 0.6, 8, 0)
        B.bm_sphere(bm, (0, 0, h - 5), (7.0, 7.0, 5.0), 2, 0)
        B.bm_cyl(bm, (0, 0, h), (0, 0, h + 1.2), 0.5, 0.1, 8, 0)
        B.mesh_obj("mh_water_tower", bm, [tm], smooth=False, loc=(wt["pos"][0], wt["pos"][1], 0))
        tw = far["town"]["pos"]
        mats = [S.pbr("mh_town_%d" % i, c2, 0.8, var=0.05) for i, c2 in enumerate(S.WALL_COLS[:4])]
        roofm = S.pbr("mh_town_roof", hexc("6b6f75"), 0.8)
        bm = bmesh.new()
        for i in range(70):
            x, y = rng.uniform(-110, 110), rng.uniform(-80, 80)
            w_, d_ = rng.uniform(8, 22), rng.uniform(8, 18)
            hh = rng.choice((4.0, 6.5, 9.0, 12.0)) if rng.random() < 0.8 else rng.uniform(14, 22)
            S.bm_box(bm, (x, y, hh / 2), (w_, d_, hh), rng.randrange(4))
            S.bm_box(bm, (x, y, hh + 0.2), (w_ + 0.4, d_ + 0.4, 0.4), 4)
        B.mesh_obj("mh_town", bm, mats + [roofm], loc=(tw[0], tw[1], 0))

    def _canopy_mat(self):
        """Distant forest canopy, shader only: Voronoi crowns (~6 m) x 40 m stand noise lit by a bump, dark gaps between crowns,
        low-frequency patches of broadleaf / conifer / lighter meadow, then distance haze (fog x 0.55)."""
        def mk():
            m, nt, N, Lk, p = S._new_mat("mh_far_canopy")
            vec = S._coord(N, Lk, "Object")
            vor = N.new("ShaderNodeTexVoronoi")
            vor.inputs["Scale"].default_value = 0.16
            try:
                vor.inputs["Randomness"].default_value = 0.9
            except Exception:
                pass
            Lk.new(vec, vor.inputs["Vector"])
            crown = N.new("ShaderNodeMapRange")                 # 1 at a crown centre .. 0 in the gap
            crown.inputs["From Min"].default_value, crown.inputs["From Max"].default_value = 0.75, 0.1
            Lk.new(vor.outputs["Distance"], crown.inputs["Value"])
            pat = N.new("ShaderNodeTexNoise")                   # species / clearing patches (~150 m)
            pat.inputs["Scale"].default_value = 0.0065
            pat.inputs["Detail"].default_value = 3.0
            Lk.new(vec, pat.inputs["Vector"])
            ramp = N.new("ShaderNodeValToRGB")
            els = ramp.color_ramp.elements
            els[0].position, els[0].color = 0.3, hexc("24452a")          # dark conifer
            els[1].position, els[1].color = 0.72, hexc("5b8338")         # light broadleaf
            e = els.new(0.5)
            e.color = hexc("3c6a2e")
            e = els.new(0.78)
            e.color = hexc("7a8a4a")                                     # meadow / dry clearing
            Lk.new(pat.outputs["Fac"], ramp.inputs["Fac"])
            jit = N.new("ShaderNodeMapRange")                   # per-crown brightness jitter from the cell colour
            jit.inputs["To Min"].default_value, jit.inputs["To Max"].default_value = 0.72, 1.12
            sepc = N.new("ShaderNodeSeparateColor")
            Lk.new(vor.outputs["Color"], sepc.inputs[0])
            Lk.new(sepc.outputs[0], jit.inputs["Value"])
            shade = N.new("ShaderNodeMapRange")                 # gaps go dark (self-shadowed understorey)
            shade.inputs["To Min"].default_value, shade.inputs["To Max"].default_value = 0.45, 1.05
            Lk.new(crown.outputs["Result"], shade.inputs["Value"])
            stand = N.new("ShaderNodeTexNoise")                 # tree stands / ravines (~40 m)
            stand.inputs["Scale"].default_value = 0.025
            stand.inputs["Detail"].default_value = 4.0
            Lk.new(vec, stand.inputs["Vector"])
            stm = N.new("ShaderNodeMapRange")
            stm.inputs["From Min"].default_value, stm.inputs["From Max"].default_value = 0.3, 0.7
            stm.inputs["To Min"].default_value, stm.inputs["To Max"].default_value = 0.6, 1.2
            Lk.new(stand.outputs["Fac"], stm.inputs["Value"])
            m0 = N.new("ShaderNodeMath"); m0.operation = "MULTIPLY"
            Lk.new(jit.outputs["Result"], m0.inputs[0])
            Lk.new(stm.outputs["Result"], m0.inputs[1])
            m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
            Lk.new(m0.outputs[0], m1.inputs[0])
            Lk.new(shade.outputs["Result"], m1.inputs[1])
            mc = N.new("ShaderNodeVectorMath"); mc.operation = "SCALE"
            Lk.new(ramp.outputs["Color"], mc.inputs[0])
            Lk.new(m1.outputs[0], mc.inputs["Scale"])
            Lk.new(mc.outputs["Vector"], p.inputs["Base Color"])
            p.inputs["Roughness"].default_value = 0.92
            try:
                p.inputs["Specular IOR Level"].default_value = 0.2
            except Exception:
                pass
            S._bump(N, Lk, crown.outputs["Result"], p, 0.35, 1.5)
            L._fog_wrap(m, p.outputs[0], density_scale=0.55)
            return m
        return B._cached("mh_far_canopy", mk)

    def _ridges(self, R):
        """Three rings of wooded ridges around (40, 0): near R+110 (20-70 m), mid R+350, far R+700. The western
        sector (the low dusk sun at az -90) is kept under ~1.6 deg as seen from the yard so it never shades the
        scene. Edges sink to z -15 under the far ground plane."""
        from mathutils import noise
        mat = self._canopy_mat()
        cx, cy = 40.0, 0.0
        rings = [(R + 110, 300.0, 18.0, 55.0, 1600, 1), (R + 350, 380.0, 30.0, 85.0, 1800, 2),
                 (R + 700, 480.0, 45.0, 120.0, 2000, 3)]
        tris = 0
        for r0, wd, hlo, hhi, nseg, seed in rings:
            M = 18
            off = Vector((seed * 37.1, seed * 11.3, seed * 5.7))
            verts = []
            for i in range(nseg):
                a = 2 * math.pi * i / nseg
                ca, sa = math.cos(a), math.sin(a)
                q = Vector((ca * 1.3, sa * 1.3, 0.0)) + off
                hb = hlo + (hhi - hlo) * max(0.0, min(1.0, 0.5 + 0.8 * noise.fractal(q, 0.5, 2.0, 2)))
                west = math.cos(a - math.pi)                       # 1 due west of the yard
                if west > 0.85:
                    cap = 0.028 * r0 + 15.0
                    t = smoothstep((west - 0.85) / 0.1)
                    hb = hb * (1 - t) + min(hb, cap) * t
                upk = 0.38 + 0.24 * (0.5 + 0.5 * noise.noise(q * 2.0 + Vector((0, 0, 7))))   # crest position
                for j in range(M):
                    u = j / (M - 1)
                    rr = r0 + wd * u
                    x, y = cx + rr * ca, cy + rr * sa
                    w_ = u / upk if u < upk else 1.0 - (u - upk) / (1 - upk)
                    prof = 0.5 - 0.5 * math.cos(math.pi * max(0.0, w_))      # rounded crest, gentle toe
                    pq = Vector((x / 260.0, y / 260.0, seed * 3.1))
                    spur = 1.0 + 0.22 * noise.fractal(pq, 0.5, 2.0, 2)
                    crown = 2.4 * noise.noise(Vector((x / 11.0, y / 11.0, seed * 1.7)))
                    zz = -15.0 + (hb * spur + 15.0) * prof + (crown if 0 < j < M - 1 else 0.0) * min(1.0, prof * 3)
                    verts.append((x, y, zz))
            faces = []
            for i in range(nseg):
                i2 = (i + 1) % nseg
                for j in range(M - 1):
                    faces.append((i * M + j, i * M + j + 1, i2 * M + j + 1, i2 * M + j))
            me = bpy.data.meshes.new("mh_ridge_%d" % seed)
            me.from_pydata(verts, [], faces)
            me.polygons.foreach_set("use_smooth", [True] * len(faces))
            me.materials.append(mat)
            o = S.obj("mh_ridge_%d" % seed, me)
            tris += 2 * len(faces)
        self.stats["ridge_tris"] = tris

    # ---------------------------------------------------------------- cut-away sections (hidden until keyed)
    def build_sections(self, sections):
        B.part_collection("sections")
        soil = self._soil_mat()
        floor = S.pbr("mh_trench_floor", hexc("4a3626"), 0.95, var=0.2, var_scale=3.0, bump=0.3)
        cable = S.pbr("mh_cable", hexc("141414"), 0.4)
        for sid, sec in (sections or {}).items():
            a, b, d, n, Lg = CP.section_frame(sec)
            depth, width = sec.get("depth", 2.0), sec.get("width", 10.0)
            objs = []
            # wall along the plane (UV v = depth fraction -> soil layers)
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            steps = max(2, int(Lg / 0.5))
            prev = None
            for i in range(steps + 1):
                t = Lg * i / steps
                x, y = a[0] + d[0] * t, a[1] + d[1] * t
                hz = H(x, y)
                row = (bm.verts.new((x, y, hz + 0.01)), bm.verts.new((x, y, hz - depth)), t)
                if prev:
                    f = bm.faces.new((prev[0], row[0], row[1], prev[1]))
                    for lp, (u, v) in zip(f.loops, ((prev[2], 0), (row[2], 0), (row[2], 1), (prev[2], 1))):
                        lp[uv].uv = (u / 4.0, v)
                prev = row
            objs.append(B.mesh_obj("mh_sec_%s_wall" % sid, bm, [soil]))
            # end caps + floor
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            for t in (0.0, Lg):
                prev = None
                for j in range(11):
                    s = width * j / 10.0
                    x, y = a[0] + d[0] * t + n[0] * s, a[1] + d[1] * t + n[1] * s
                    hz = H(x, y)
                    row = (bm.verts.new((x, y, hz + 0.01)), bm.verts.new((x, y, hz - depth)), s)
                    if prev:
                        f = bm.faces.new((prev[0], row[0], row[1], prev[1]))
                        for lp, (u, v) in zip(f.loops, ((prev[2], 0), (row[2], 0), (row[2], 1), (prev[2], 1))):
                            lp[uv].uv = (u / 4.0, v)
                    prev = row
            objs.append(B.mesh_obj("mh_sec_%s_caps" % sid, bm, [soil]))
            bm = bmesh.new()
            grid = []
            for i in range(steps + 1):
                t = Lg * i / steps
                row = []
                for j in range(6):
                    s = width * j / 5.0
                    x, y = a[0] + d[0] * t + n[0] * s, a[1] + d[1] * t + n[1] * s
                    row.append(bm.verts.new((x, y, H(x, y) - depth)))
                grid.append(row)
            for i in range(steps):
                for j in range(5):
                    bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            objs.append(B.mesh_obj("mh_sec_%s_floor" % sid, bm, [floor]))
            # the buried cable, half in the wall
            bm = bmesh.new()
            cd = sec.get("cable_depth", 0.6)
            prev = None
            for i in range(steps + 1):
                t = Lg * i / steps
                x, y = a[0] + d[0] * t, a[1] + d[1] * t
                p = (x, y, H(x, y) - cd)
                if prev:
                    B.bm_cyl(bm, prev, p, 0.04, 0.04, 8, 0, False)
                prev = p
            objs.append(B.mesh_obj("mh_sec_%s_cable" % sid, bm, [cable], smooth=True))
            for o in objs:
                o.hide_render = True
            self.sections[sid] = {"objs": objs, "frame": (a, b, d, n, Lg), "spec": sec}
            mid = (a[0] + d[0] * Lg / 2 + n[0] * width / 2, a[1] + d[1] * Lg / 2 + n[1] * width / 2)
            self.exclude.append((mid[0], mid[1], max(Lg, width) / 2 + 3))

    def _soil_mat(self):
        def mk():
            m, nt, N, Lk, p = S._new_mat("mh_soil_layers")
            uvn = N.new("ShaderNodeUVMap")
            sep = N.new("ShaderNodeSeparateXYZ")
            Lk.new(uvn.outputs["UV"], sep.inputs[0])
            ramp = N.new("ShaderNodeValToRGB")
            ramp.color_ramp.interpolation = "EASE"
            els = ramp.color_ramp.elements
            els[0].position, els[0].color = 0.0, hexc("4f7a35")
            els[1].position, els[1].color = 1.0, hexc("8a7a68")
            for pos, c in ((0.03, hexc("3a2a1e")), (0.16, hexc("4a3424")), (0.22, hexc("7a5233")), (0.6, hexc("9a6a40")),
                           (0.68, hexc("8f8576"))):
                e = els.new(pos)
                e.color = c
            Lk.new(sep.outputs["Y"], ramp.inputs[0])
            vec = S._coord(N, Lk, "Object")
            fac, _ = S._noise_var(N, Lk, vec, 2.5, 0.18, 6.0)
            col = S._mul_col(N, Lk, ramp.outputs["Color"], fac)
            Lk.new(col, p.inputs["Base Color"])
            p.inputs["Roughness"].default_value = 0.95
            nz = N.new("ShaderNodeTexNoise")
            nz.inputs["Scale"].default_value = 6.0
            nz.inputs["Detail"].default_value = 8.0
            Lk.new(vec, nz.inputs["Vector"])
            S._bump(N, Lk, nz.outputs["Fac"], p, 0.5, 0.03)
            return S._finish(m, p.outputs[0])
        return B._cached("mh_soil_layers", mk)

    def key_section(self, f, sid):
        """Show section `sid` (None = none) from frame f: terrain mask values + cut-away objects."""
        sg = B.section_group()

        def kv(name, v):
            B.key_const(sg.nodes[name].outputs[0], "default_value", [(f, v)])
        if sid is None or sid not in self.sections:
            kv("on", 0.0)
        else:
            a, b, d, n, Lg = self.sections[sid]["frame"]
            spec = self.sections[sid]["spec"]
            for k, v in (("on", 1.0), ("ax", a[0]), ("ay", a[1]), ("dx", d[0]), ("dy", d[1]), ("nx", n[0]), ("ny", n[1]),
                         ("len", Lg), ("width", spec.get("width", 10.0))):
                kv(k, v)
        for k, sec in self.sections.items():
            for o in sec["objs"]:
                B.vis_keys(o, [(f, k == sid)])


# ================================================================ builds registry
def _rotor_angles(ctx, entry, mode, f0, f1):
    """Rotor angle (rad) per frame for the job range: idle = steady spin; assemble = still until raised, then
    spin up, faster in snag2/hack2, ease to a stop through the teaser."""
    fps = ctx.fps
    plan = getattr(ctx, "plan", None)
    if mode == "idle" or plan is None:
        w = 2 * math.pi * entry.get("idle_rpm", 110) / 60.0 / fps
        return {f: w * f for f in range(f0, f1 + 1)}
    ev = ctx.build_events.get(entry["id"], {})
    up, fast, slow0, stop = ev.get("spin_start", 10 ** 9), ev.get("fast", 10 ** 9), ev.get("slow", 10 ** 9), ev.get("stop", 10 ** 9)
    ang, out = 0.0, {}
    for f in range(1, f1 + 1):
        rpm = 0.0
        if f >= up:
            rpm = min(110.0, 110.0 * (f - up) / (2.0 * fps))
        if f >= fast:
            rpm = 240.0
        if f >= slow0:
            rpm = 120.0
        if f >= stop:
            rpm = max(0.0, 120.0 * (1 - (f - stop) / (3.0 * fps)))
        ang += 2 * math.pi * rpm / 60.0 / fps
        if f >= f0:
            out[f] = ang
    return out


# ---------------------------------------------------------------- turbine geometry helpers (s7)
def _lathe_x(bm, prof, seg, mi, c=(0.0, 0.0, 0.0)):
    """Surface of revolution about the X axis: prof = [(x, r)] (r = 0 ends close in a pole)."""
    c = Vector(c)
    rows = []
    for x, r in prof:
        if r <= 1e-6:
            rows.append([bm.verts.new(c + Vector((x, 0.0, 0.0)))])
            continue
        rows.append([bm.verts.new(c + Vector((x, r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg))))
                     for k in range(seg)])
    for a, b in zip(rows, rows[1:]):
        for k in range(seg):
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[(k + 1) % seg], b[k]))
            elif len(b) == 1:
                f = bm.faces.new((a[k], a[(k + 1) % seg], b[0]))
            else:
                f = bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
            f.material_index = mi
    return rows


BLADE_R = 1.75       # m tip radius (3.5 m rotor, ~1.5 kW class)


def _airfoil(n=12, t=0.12, camber=0.035):
    """Closed cambered NACA-4-like section, chord 0..1 from the leading edge: [(x, y)], y = + suction side."""
    pts_u, pts_l = [], []
    for i in range(n + 1):
        x = 0.5 * (1 - math.cos(math.pi * i / n))
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        p = 0.4
        yc = camber / p ** 2 * (2 * p * x - x * x) if x < p else camber / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x)
        pts_u.append((x, yc + yt))
        pts_l.append((x, yc - yt))
    return pts_u + pts_l[-2:0:-1]          # LE -> TE on the suction side, back to the LE on the pressure side


def _blade(bm, a, mi_blade, mi_clamp):
    """One blade at rotor angle a (radial direction (0, -sin a, cos a)). Spinning about +X, the blade moves along
    m = x * r; the leading edge points along m, pitched by beta towards the wind (-X); suction side faces downwind."""
    r_hat = Vector((0.0, -math.sin(a), math.cos(a)))
    m_hat = Vector((1.0, 0.0, 0.0)).cross(r_hat)
    x_hat = Vector((1.0, 0.0, 0.0))
    foil = _airfoil(10)
    nf = len(foil)
    rows = []
    # (radius, chord, thickness ratio, pitch deg, roundness 0 = airfoil .. 1 = circle of diameter `chord`)
    st = [(0.16, 0.085, 1.0, 18.0, 1.0), (0.26, 0.09, 1.0, 18.0, 1.0), (0.34, 0.19, 0.3, 18.0, 0.45), (0.42, 0.215, 0.24, 16.0, 0.0),
          (0.6, 0.2, 0.2, 12.5, 0.0), (0.85, 0.17, 0.17, 8.5, 0.0), (1.1, 0.14, 0.15, 5.5, 0.0), (1.35, 0.11, 0.13, 3.5, 0.0),
          (1.58, 0.08, 0.12, 2.0, 0.0), (BLADE_R, 0.045, 0.12, 1.5, 0.0)]
    for rad, ch, tr, beta, rnd in st:
        b = math.radians(beta)
        le = m_hat * math.cos(b) - x_hat * math.sin(b)       # chord direction (TE -> LE)
        nrm = x_hat * math.cos(b) + m_hat * math.sin(b)      # suction-side normal (downwind)
        scale_t = tr / 0.12
        row = []
        for i, (fx, fy) in enumerate(foil):
            # airfoil about the quarter-chord pitch axis
            u, w = (0.25 - fx) * ch, fy * ch * scale_t
            if rnd > 0:
                ang = 2 * math.pi * i / nf
                cu, cw = math.cos(ang) * ch * 0.5, math.sin(ang) * ch * 0.5
                u, w = u * (1 - rnd) + cu * rnd, w * (1 - rnd) + cw * rnd
            row.append(bm.verts.new(r_hat * rad + le * u + nrm * w))
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(nf):
            f = bm.faces.new((r0[k], r0[(k + 1) % nf], r1[(k + 1) % nf], r1[k]))
            f.material_index = mi_blade
    tip = bm.verts.new(r_hat * (BLADE_R + 0.012))
    for k in range(nf):
        bm.faces.new((rows[-1][k], rows[-1][(k + 1) % nf], tip)).material_index = mi_blade
    root = bm.verts.new(r_hat * 0.15)
    for k in range(nf):
        bm.faces.new((rows[0][(k + 1) % nf], rows[0][k], root)).material_index = mi_blade
    B.bm_cyl(bm, tuple(r_hat * 0.13), tuple(r_hat * 0.27), 0.056, 0.054, 16, mi_clamp)     # root clamp


def _autosmooth(ob, deg=40.0):
    """Smooth shading with sharp creases kept above `deg` (Blender 4.1+ Mesh.set_sharp_from_angle; older builds:
    use_auto_smooth). Also makes the face normals consistent (every part here is a closed shell)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for pl in me.polygons:
        pl.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(deg))
    except AttributeError:
        try:
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(deg)
        except Exception:
            pass


def build_wind_turbine(ctx, entry, mode):
    """STUB (first pass): Build #1 tilt-up wind turbine. Tower 50 ft, 3 blades, generator, tail vane (furling hinge),
    hinge plate, gin pole, hand winch, 4 guy wires. mode=assemble: lies flat until the hack1 cue, tilts up over 4 s,
    spins up, furls in hack2, eases to a stop in the teaser. mode=idle: upright, rotor_spin."""
    B.part_collection("builds")
    x, y, z = entry["pos"]
    steel = S.pbr("mh_steel", hexc("9aa1a8"), 0.35, metal=0.8)
    white = S.pbr("mh_blade", hexc("f2f2ee"), 0.35, coat=0.3)
    dark = S.pbr("mh_nacelle", hexc("3a3f44"), 0.4, metal=0.4)
    conc = B.mat_ph("mh_concrete", hexc("c9c4ba"), "concrete_floor_02", 0.35, 0.8)
    T = 50 * G.FT
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0.15), (2.2, 2.2, 0.3), 0)
    S.bm_box(bm, (0, 0, 0.36), (0.6, 0.6, 0.12), 1)
    B.mesh_obj("bw_turbine_base", bm, [conc, steel], loc=(x, y, z))
    piv = L.link(bpy.data.objects.new("bw_turbine_pivot", None))
    piv.location = (x, y, z + 0.42)
    bm = bmesh.new()
    B.bm_cyl(bm, (0, 0, 0), (0, 0, T), 0.19, 0.12, 12, 0)
    B.bm_cyl(bm, (0, 0, T - 0.1), (0, 0, T + 0.25), 0.16, 0.16, 12, 1)
    B.bm_cyl(bm, (0.4, 0, T + 0.35), (2.4, 0, T + 0.35), 0.05, 0.04, 10, 0)            # tail boom
    tower = B.mesh_obj("bw_turbine_tower", bm, [steel, dark])
    # s7: streamlined nacelle (housing + dark alternator band with cooling fins + yaw clamp), smooth shaded
    shell = S.pbr("mh_nacelle_shell", hexc("d4d7da"), 0.35, coat=0.4)
    bm = bmesh.new()
    _lathe_x(bm, [(-0.56, 0.0), (-0.56, 0.17), (-0.53, 0.2), (-0.36, 0.215), (-0.34, 0.235), (-0.12, 0.25),
                  (0.12, 0.24), (0.32, 0.2), (0.5, 0.13), (0.6, 0.07), (0.63, 0.0)], 28, 0, (0, 0, T + 0.35))
    for fx in (-0.52, -0.48, -0.44, -0.40):                                                  # alternator fins
        _lathe_x(bm, [(fx - 0.008, 0.0), (fx - 0.008, 0.232), (fx + 0.008, 0.232), (fx + 0.008, 0.0)], 28, 1,
                 (0, 0, T + 0.35))
    B.bm_cyl(bm, (0.0, 0, T + 0.12), (0.0, 0, T + 0.2), 0.2, 0.17, 20, 1)                  # yaw clamp / bearing
    nac = B.mesh_obj("bw_turbine_nacelle", bm, [shell, dark], smooth=True)
    nac.parent = piv
    _autosmooth(nac)
    tower.parent = piv
    rotor = L.link(bpy.data.objects.new("bw_turbine_rotor", None))
    rotor.parent = piv
    rotor.location = (-0.62, 0, T + 0.35)
    # s7: real 3-blade HAWT rotor: tapered, twisted airfoil blades (root 18 deg -> tip 2 deg pitch), round roots in
    # steel clamps on a hub plate, white spinner (nose cone). Rotor axis = local X (spins +X), upwind = -X.
    bm = bmesh.new()
    _lathe_x(bm, [(0.0, 0.0), (0.0, 0.2), (-0.03, 0.215), (-0.12, 0.2), (-0.24, 0.15), (-0.32, 0.09), (-0.37, 0.035),
                  (-0.385, 0.0)], 28, 0)                                                     # spinner / nose cone
    _lathe_x(bm, [(0.06, 0.0), (0.06, 0.17), (-0.005, 0.17), (-0.005, 0.0)], 28, 1)        # hub plate
    for k in range(3):
        _blade(bm, k * 2 * math.pi / 3, 0, 1)
    blades = B.mesh_obj("bw_turbine_blades", bm, [white, dark], smooth=True)
    blades.parent = rotor
    _autosmooth(blades)
    tail = L.link(bpy.data.objects.new("bw_turbine_tail_hinge", None))
    tail.parent = piv
    tail.location = (2.4, 0, T + 0.35)
    bm = bmesh.new()
    # s7: an explicit 3 cm plate. bmesh solidify left both caps coincident (zero-area sides), so the vane
    # self-shadowed and rendered pitch black (f1600 v2).
    outl = ((0, -0.45), (1.3, -0.6), (1.3, 0.75), (0, 0.55))
    va = [bm.verts.new((x_, -0.015, z_)) for x_, z_ in outl]
    vb = [bm.verts.new((x_, 0.015, z_)) for x_, z_ in outl]
    bm.faces.new(va)
    bm.faces.new(vb[::-1])
    for k in range(4):
        bm.faces.new((va[k], vb[k], vb[(k + 1) % 4], va[(k + 1) % 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    vane = B.mesh_obj("bw_turbine_vane", bm, [white])
    vane.parent = tail
    gin = bmesh.new()
    B.bm_cyl(gin, (0, 0, 0), (0, 4.0, 0), 0.07, 0.06, 8, 0)
    gp = B.mesh_obj("bw_turbine_gin_pole", gin, [steel])
    gp.parent = piv
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0.35), (0.5, 0.4, 0.7), 0)
    B.bm_cyl(bm, (-0.3, 0, 0.55), (0.3, 0, 0.55), 0.12, 0.12, 10, 1)
    B.mesh_obj("bw_turbine_winch", bm, [S.pbr("mh_winch", hexc("c9a227"), 0.5, metal=0.4), steel], loc=(x, y + 4.5, z))
    guy = S.pbr("mh_guy", hexc("b8bcc0"), 0.3, metal=0.9)
    guys = []
    for k, (dx, dy) in enumerate(((9.0, 0), (-9.0, 0), (0, 9.0), (0, -9.0))):
        bm = bmesh.new()
        B.bm_cyl(bm, (x + dx, y + dy, z + 0.05), (x, y, z + 0.42 + T * 0.66), 0.012, 0.012, 4, 0, False)
        S.bm_box(bm, (x + dx, y + dy, z + 0.05), (0.3, 0.3, 0.1), 0)
        guys.append(B.mesh_obj("bw_turbine_guy_%d" % k, bm, [guy]))
    for name, obj_, off in (("rotor_hub", rotor, (0, 0, 0)), ("generator", piv, (0, 0, T + 0.35)),
                            ("tail", tail, (0.8, 0, 0.1)), ("hinge", piv, (0, 0, 0)), ("gin_pole", gp, (0, 4.0, 0)),
                            ("guy_anchor", guys[0], (x + 9.0, y, z)), ("tower_top", piv, (0, 0, T))):
        S.anchor(ctx, name, obj_, off)
    f0, f1 = ctx.frame_range
    ang = _rotor_angles(ctx, entry, mode, max(1, f0 - 2), f1 + 2)
    # s8: assemble mode parks the rotor with blade 0 pointing straight UP while the tower lies down (blade k
    # direction after the spin = local (0, -sin(a), cos(a)); flat, local +Y is world up -> a = -90 deg). The other two
    # tips then sit R*cos(60) = 0.875 m below the hub instead of 1.52 m. Only a phase: the spin keys are unchanged.
    park = -math.pi / 2 if mode != "idle" else 0.0
    fr = sorted(ang)
    B.set_keys(rotor, "rotation_euler", fr, [(ang[f] + park, 0.0, 0.0) for f in fr])
    if mode == "idle":
        B.set_keys(piv, "rotation_euler", [1], [(0.0, 0.0, 0.0)])
        return {"objects": [piv]}
    ev = ctx.build_events.get(entry["id"], {})
    t0, t1 = ev.get("tilt_start", 1), ev.get("tilt_end", 2)
    # s8: the lowered tower rests on a timber tower-top stand (sawhorse with a padded V cradle) so the hub sits
    # HUB_REST m above the ground under the rotor -> lowest tip clearance ~0.4 m. Rotation about X by th puts local
    # (0, 0, l) at world (0, -l sin th, l cos th) from the hinge; solve th for the hub height over the local ground.
    LH = T + 0.35
    HUB_REST = 1.32
    th = math.radians(90.0)
    for _ in range(4):
        yh = y - LH * math.sin(th)
        gz = max(H(x + dx, yh + dy) for dx in (-0.7, 0.0) for dy in (-1.6, 0.0, 1.6))
        c = (gz + HUB_REST - (z + 0.42)) / LH
        th = math.acos(max(-0.3, min(0.35, c)))
    flat = th
    s_st = T - 1.15                                       # stand just below the yaw clamp
    ys, zs_axis = y - s_st * math.sin(flat), z + 0.42 + s_st * math.cos(flat)
    r_tw = 0.19 + (0.12 - 0.19) * s_st / T
    top = zs_axis - r_tw / max(0.2, math.sin(flat))      # underside of the tower at the stand
    gst = H(x, ys)
    wood = S.pbr("mh_stand_wood", hexc("9c7a52"), 0.75, var=0.12, var_scale=3.0)
    pad = S.pbr("mh_stand_pad", hexc("2b2b2b"), 0.9)
    bm = bmesh.new()
    cz = top - 0.06                                       # cradle beam centre
    S.bm_box(bm, (0, 0, cz), (0.95, 0.14, 0.1), 0)       # sawhorse beam, across the tower (world X)
    for sx in (-1, 1):                                    # V cradle cheeks either side of the tower
        S.bm_box(bm, (sx * (r_tw + 0.05), 0, top + 0.05), (0.07, 0.14, 0.18), 0)
    S.bm_box(bm, (0, 0, top - 0.006), (2 * r_tw + 0.04, 0.16, 0.012), 1)   # rubber pad under the tower
    for sx in (-1, 1):
        for sy in (-1, 1):                                # splayed legs at both beam ends
            B.bm_cyl(bm, (sx * 0.4, sy * 0.04, cz - 0.04), (sx * 0.55, sy * 0.38, gst - 0.12), 0.035, 0.035, 4, 0)
    for sy in (-1, 1):                                    # side braces
        zb = cz - 0.45 * (cz - gst)
        B.bm_cyl(bm, (-0.48, sy * 0.2, zb), (0.48, sy * 0.2, zb), 0.022, 0.022, 4, 0)
    B.mesh_obj("bw_turbine_stand", bm, [wood, pad], loc=(x, ys, 0.0))
    ctx.stats_turbine = {"flat_deg": round(math.degrees(flat), 2), "stand_top_z": round(top - gst, 2),
                         "hub_rest_z": round(z + 0.42 + LH * math.cos(flat) - H(x, y - LH * math.sin(flat)), 2),
                         "t0": t0, "t1": t1}
    keys_f, keys_v = [1, t0], [(flat, 0, 0), (flat, 0, 0)]
    for k in range(1, 9):
        f = t0 + (t1 - t0) * k / 8.0
        e = CP.smootherstep(k / 8.0)
        keys_f.append(int(round(f)))
        keys_v.append((flat * (1 - e), 0, 0))
    B.set_keys(piv, "rotation_euler", keys_f, keys_v)
    for gobj in guys:
        B.vis_keys(gobj, [(1, False), (t1, True)])
    fu0 = ev.get("furl", 10 ** 9)
    if fu0 < 10 ** 8:
        fps = ctx.fps
        B.set_keys(tail, "rotation_euler", [1, fu0, fu0 + int(1.0 * fps), fu0 + int(3.0 * fps), fu0 + int(4.2 * fps)],
                   [(0, 0, 0), (0, 0, 0), (0, 0, math.radians(70)), (0, 0, math.radians(70)), (0, 0, 0)], "BEZIER")
    # ghost of the finished tower (beat 2) + floating exploded head (beat 3)
    if ev.get("ghost"):
        g0, g1 = ev["ghost"]
        bm = bmesh.new()
        B.bm_cyl(bm, (0, 0, 0), (0, 0, T), 0.2, 0.13, 10, 0, False)
        gh = B.mesh_obj("bw_turbine_ghost", bm, [B.mat_glow("mh_ghost", (0.55, 0.85, 1.0, 1.0), 2.5)], loc=(x, y, z + 0.42))
        B.vis_keys(gh, [(1, False), (g0, True), (g1, False)])
    return {"objects": [piv, rotor, tail]}


def turbine_clearance(ctx):
    """s8 QC: lowest point of the rotor / nacelle / vane above the terrain (H) on every frame where the tower is
    down or tilting (frame 1, then tilt_start..tilt_end). Negative = something is in the ground."""
    st = getattr(ctx, "stats_turbine", None)
    obs = [bpy.data.objects.get(n) for n in ("bw_turbine_blades", "bw_turbine_nacelle", "bw_turbine_vane")]
    if not st or any(o is None for o in obs):
        return {}
    sc = bpy.context.scene
    keep = sc.frame_current
    frames = [1] + list(range(st["t0"], st["t1"] + 1))
    worst, wf = 1e9, None
    loc = [[v.co.copy() for v in o.data.vertices] for o in obs]
    for f in frames:
        sc.frame_set(f)
        for o, vs in zip(obs, loc):
            mw = o.matrix_world
            for co in vs:
                p = mw @ co
                d = p.z - H(p.x, p.y)
                if d < worst:
                    worst, wf = d, f
    sc.frame_set(keep)
    out = {"turbine_" + k: v for k, v in st.items() if k not in ("t0", "t1")}
    out.update({"turbine_min_clear_m": round(worst, 3), "turbine_min_clear_f": wf, "turbine_clear_frames": len(frames)})
    print("[mh] turbine clearance: min %.3f m at f%s over %d frames (flat %.2f deg)" % (worst, wf, len(frames), st["flat_deg"]))
    return out


def build_stub_generic(ctx, entry, mode):
    """Placeholder for builds without a builder yet: a labelled-by-anchor crate on the build's spot."""
    B.part_collection("builds")
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, 0.5), (1.2, 1.2, 1.0), 0)
    o = B.mesh_obj("bw_%s_placeholder" % entry["id"], bm, [S.pbr("mh_crate", hexc("b08a5a"), 0.8)], loc=tuple(entry["pos"]))
    S.anchor(ctx, entry["id"], o, (0, 0, 1.2))
    return {"objects": [o]}


BUILDS = {"wind_turbine": build_wind_turbine, "_stub": build_stub_generic}


def place_builds(ctx, ws, loc_name, episode):
    """Every approved|scheduled|posted build at this location (idle) + this episode's own builds (assemble)."""
    placed = {b["id"]: (b, "idle") for b in MP.placed_builds(ws, loc_name)}
    zones = MP.location(ws, loc_name)["zones"]
    for e in (episode or {}).get("builds_in_episode", []):
        b = dict(next((x for x, _m in placed.values() if x["id"] == e["id"]), {}))
        b.update({k: v for k, v in e.items() if k != "mode"})
        b["id"] = e["id"]
        if "pos" not in b:
            zone = zones[e.get("zone", "ridge_pad")]
            b["pos"] = list(zone["pos"])
        placed[e["id"]] = (b, e.get("mode", "assemble"))
    out = {}
    for bid, (entry, mode) in placed.items():
        fn = BUILDS.get(bid, BUILDS["_stub"])
        try:
            out[bid] = fn(ctx, entry, mode)
        except Exception:
            import traceback
            traceback.print_exc()
            print("[mh] build %s failed; skipped" % bid)
    return out


# ================================================================ entry point
def build(ctx, ws, loc_name="mercer_hollow", parts=None, focus=(), sections=None, episode=None):
    import time
    parts = set(parts or ALL_PARTS)
    loc = MP.location(ws, loc_name)
    L.fog(0.0011, S.HAZE, start=70.0)
    w = World(ctx, ws, loc, episode)
    w.build_lighting()
    t_all = time.time()
    order = [("sections", lambda: w.build_sections(sections)), ("terrain", w.build_terrain), ("water", w.build_water),
             ("street", w.build_street), ("house", w.build_house), ("yard", w.build_yard),
             ("workshop", w.build_workshop), ("props", w.build_props), ("trees", w.build_trees),
             ("grass", lambda: w.build_grass(focus)), ("far", w.build_far)]
    for name, fn in order:
        if name not in parts:
            continue
        t0 = time.time()
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            print("[mh] PART %s FAILED (continuing)" % name)
        w.stats["t_" + name] = round(time.time() - t0, 2)
        w.stats["tris_" + name] = B.count_tris(name)
    if "builds" in parts:
        t0 = time.time()
        w.builds = place_builds(ctx, ws, loc_name, episode)
        w.stats["t_builds"] = round(time.time() - t0, 2)
        try:
            w.stats.update(turbine_clearance(ctx))
        except Exception:
            import traceback
            traceback.print_exc()
    t0 = time.time()
    try:
        _cc0_finish(w, parts)
    except Exception:
        import traceback
        traceback.print_exc()
        print("[mh] CC0 finish FAILED (continuing)")
    w.stats["t_cc0_finish"] = round(time.time() - t0, 2)
    n_fog = B.relink_fog_to_group()
    # anchors: every camera spot (its look-at point), every zone, extra points
    for k, sp in loc.get("camera_spots", {}).items():
        B.anchor_empty(ctx, "spot_" + k, tuple(sp["look_at"]))
    for k, zz in loc["zones"].items():
        p = zz["pos"]
        B.anchor_empty(ctx, k, (p[0], p[1], p[2] + min(2.0, zz["size"][2] / 2 if len(zz["size"]) > 2 else 0.0)))
    for k, p in getattr(w, "anchor_pts", {}).items():
        B.anchor_empty(ctx, k, p)
    w.stats["t_world"] = round(time.time() - t_all, 2)
    w.stats["fog_mats"] = n_fog
    return w


def _cc0_finish(w, parts):
    """Session 6 pass after the parts are built: PBR surfaces, Kenney props, shrubs, cut-away restyle, stats."""
    if not MC.enabled():
        return
    z = w.z
    if "house" in parts or "street" in parts or "yard" in parts:
        w.stats["cc0_surfaces"] = MC.surfaces(w)
    if "house" in parts:
        w.stats["cc0_kitchen_props"] = MC.kitchen_props(7.0, 6.7, 0.45)
        B.part_collection("yard")
        spots = [(-0.75, yy, "big") for yy in (-6.0, -5.0, 5.0, 6.0)] + \
                [(-2.9, yy, "plant") for yy in (-3.3, -2.2, 2.2, 3.3)] + \
                [(10.4, yy, "big") for yy in (-5.5, 4.2)] + [(33.0, 21.0, "big"), (11.5, 21.5, "big"), (33.5, -12.0, "big")]
        w.stats["cc0_shrubs"] = MC.shrubs(H, spots)
    if "workshop" in parts:
        sh = z["battery_shed"]
        wz = z["workshop"]
        sy1 = wz["pos"][1] - wz["size"][1] / 2 - 0.1
        w.stats["cc0_shed_props"] = MC.shed_props(sh["pos"][0], sy1 - 3.7, sy1)
    if "sections" in parts:
        w.stats["cc0_sections"] = MC.upgrade_sections(w, H)
    try:
        import cc0_lib as C
        w.stats.update(C.vram_estimate())
    except Exception:
        pass


def build_world(ctx, state):
    """World-registry entry (page2/blender/worlds.py WORLDS["mercer_hollow"]): build(ctx, state) -> {id: ANC_<id>}.
    Same anchor table as plan time (worlds.mercer_plan_anchors: zones, spot_<id> legacy aliases, camera/episode
    spot ids, episode anchors) plus build-time anchors (turbine parts, fridge, battery rack...), and a CAM_<id>
    empty per camera spot. The World object is left in state["world"] (presets/sections/lights keying)."""
    import worlds as WR
    ep = state.get("episode") or {}
    ws = state.get("world_state") or MP.world_state()
    loc_name = (ep.get("beats") or [{}])[0].get("shot", {}).get("location", "mercer_hollow")
    w = build(ctx, ws, loc_name, state.get("parts"), state.get("focus", ()), ep.get("sections"), ep)
    state["world"] = w
    pa = WR.mercer_plan_anchors({"world_state": ws, "episode": ep})
    B.part_collection("anchors")
    for k, p in pa["anchors"].items():
        if k not in ctx.anchors:
            B.anchor_empty(ctx, k, tuple(p))
    for k, c in pa["cams"].items():
        B.anchor_empty(ctx, k, tuple(c["pos"]), register=False, prefix=B.CAM_PREFIX)
    return B.normalize_anchors(ctx)

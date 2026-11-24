"""Blender helpers for the Self-Made Engineer world (Page 2). Needs bpy.

Reuses the v2 look from pipeline/blender/scene_lib_v2.py (read-only import: pbr, ph_detail, daylight pieces, mesh
helpers, haze). Small helpers that live in other WJH modules (keys on Blender 5 layered actions) are copied here so
nothing in pipeline/ is imported beyond scene_lib / scene_lib_v2.
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import mh_paths as MP

MP.add_import_paths(blender=True)
import scene_lib as L  # noqa: E402
import scene_lib_v2 as S  # noqa: E402
from scene_lib import hexc  # noqa: E402

TRIS = {}          # part -> triangle count (stats)


# ================================================================ collections
def part_collection(name):
    """Create (or reuse) a child collection of the scene collection and make it the active one, so S.obj()/L.link()
    put new objects there."""
    sc = bpy.context.scene
    c = bpy.data.collections.get("MH_" + name)
    if c is None:
        c = bpy.data.collections.new("MH_" + name)
        sc.collection.children.link(c)
    lc = _find_layer_coll(bpy.context.view_layer.layer_collection, c.name)
    if lc is not None:
        bpy.context.view_layer.active_layer_collection = lc
    return c


def _find_layer_coll(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = _find_layer_coll(ch, name)
        if r is not None:
            return r
    return None


def count_tris(coll_name):
    c = bpy.data.collections.get("MH_" + coll_name)
    if c is None:
        return 0
    n = 0
    for o in c.all_objects:
        if o.type == "MESH" and o.data is not None:
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n


# ================================================================ keys (Blender 5 layered actions safe)
def _fcurves(id_data, path=None):
    ad = getattr(id_data, "animation_data", None)
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
    return [fc for fc in curves if path is None or fc.data_path == path]


def set_keys(o, path, frames, values, interp="LINEAR"):
    """Replace all keys of o.<path> (vector or scalar) with (frames, values) in one foreach_set (fast, exact).
    `o` may be any animatable struct (object, pose bone, light, node socket): fcurves live on o.id_data."""
    if not frames:
        return
    vals = [v if isinstance(v, (list, tuple, Vector)) else (v,) for v in values]
    full = o.path_from_id(path)
    idd = o.id_data
    if not _fcurves(idd, full):
        cur = getattr(o, path)
        try:
            n = len(cur)
            for i in range(n):
                cur[i] = vals[0][i]
        except TypeError:
            setattr(o, path, vals[0][0])
        o.keyframe_insert(path, frame=frames[0])
    fcs = {fc.array_index: fc for fc in _fcurves(idd, full)}
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
        co[1::2] = [float(v[i]) for v in vals]
        kp.foreach_set("co", co)
        for k in kp:
            k.interpolation = interp
            k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"
        fc.update()


def key_const(owner, prop, keys, index=-1):
    """CONSTANT keys on any animatable property (object, light, node socket, view settings...).
    keys = [(frame, value)]; values are assigned then keyframed; interpolation fixed to CONSTANT afterwards
    (Blender 5.3 ignores the new-key interpolation preference)."""
    for f, v in keys:
        if index >= 0:
            getattr(owner, prop)[index] = v
        else:
            setattr(owner, prop, v)
        owner.keyframe_insert(prop, frame=int(f), index=index)
    path = owner.path_from_id(prop)
    for fc in _fcurves(owner.id_data, path):
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"


def vis_keys(o, keys):
    """keys = [(frame, visible_bool)] -> hide_render + hide_viewport CONSTANT keys."""
    key_const(o, "hide_render", [(f, not v) for f, v in keys])
    key_const(o, "hide_viewport", [(f, not v) for f, v in keys])


def driver_expr(owner, prop, expr, index=-1):
    """Simple-expression driver (e.g. 'frame*0.05'); simple expressions run without Python auto-exec."""
    fc = owner.driver_add(prop, index) if index >= 0 else owner.driver_add(prop)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = expr
    return fc


# ================================================================ shared weather / section / fog groups
def value_group(name, outputs):
    """Shader node group with one Value/RGB node per output; materials read it, the render keys it.
    outputs = [(socket name, 'VALUE'|'RGBA', default)]."""
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    out = ng.nodes.new("NodeGroupOutput")
    for i, (sock, kind, dflt) in enumerate(outputs):
        st = "NodeSocketColor" if kind == "RGBA" else "NodeSocketFloat"
        ng.interface.new_socket(sock, in_out="OUTPUT", socket_type=st)
        n = ng.nodes.new("ShaderNodeRGB" if kind == "RGBA" else "ShaderNodeValue")
        n.name = n.label = sock
        n.outputs[0].default_value = dflt
        n.location = (-300, -120 * i)
        ng.links.new(n.outputs[0], out.inputs[i])
    return ng


def weather_group():
    return value_group("MH_Weather", [("frost", "VALUE", 0.0), ("snow", "VALUE", 0.0), ("wet", "VALUE", 0.0)])


def fog_group():
    return value_group("MH_Fog", [("color", "RGBA", tuple(S.HAZE))])


def section_group():
    return value_group("MH_Section", [("on", "VALUE", 0.0), ("ax", "VALUE", 0.0), ("ay", "VALUE", 0.0),
                                      ("dx", "VALUE", 1.0), ("dy", "VALUE", 0.0), ("nx", "VALUE", 0.0),
                                      ("ny", "VALUE", 1.0), ("len", "VALUE", 1.0), ("width", "VALUE", 1.0)])


def group_node(N, ng):
    n = N.new("ShaderNodeGroup")
    n.node_tree = ng
    return n


def group_value_socket(ng, name):
    return ng.nodes[name].outputs[0]


def relink_fog_to_group():
    """Point every scene_lib fog emission (L._fog_wrap) at MH_Fog.color so presets can key the haze colour once."""
    fg = fog_group()
    n = 0
    for m in bpy.data.materials:
        nt = m.node_tree
        if nt is None or not any(x.type == "CAMERA" for x in nt.nodes):
            continue
        for x in nt.nodes:
            if x.type == "EMISSION" and x.outputs[0].is_linked and not x.inputs["Color"].is_linked and \
                    any(lk.to_node.type == "MIX_SHADER" and lk.to_socket == lk.to_node.inputs[2] for lk in x.outputs[0].links):
                g = group_node(nt.nodes, fg)
                nt.links.new(g.outputs["color"], x.inputs["Color"])
                n += 1
    return n


# ================================================================ materials
_M = {}


def _cached(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def reset_caches():
    _M.clear()
    TRIS.clear()
    L._MATS.clear()
    S._MV2.clear()


def mat_ph(name, color, asset, amount=0.5, rough=0.85, scale_mul=1.0, normal=0.5, hue=0.1):
    """PBR material with a Poly Haven detail texture (falls back to plain S.pbr if the asset is missing)."""
    def mk():
        if not S.ph_available(asset):
            return S.pbr(name, color, rough, var=0.08, var_scale=0.5, bump=0.05)
        m, nt, N, Lk, p = S._new_mat(name)
        p.inputs["Roughness"].default_value = rough
        vec = S._coord(N, Lk, "Object")
        S.ph_detail(N, Lk, vec, asset, p, tuple(color), amount=amount, hue=hue, normal=normal, rough_mix=0.3,
                    scale_mul=scale_mul)
        return S._finish(m, p.outputs[0])
    return _cached(name, mk)


def mat_bands(name, color, spacing=0.18, axis="Z", depth=0.35, rough=0.7, var=0.04, roof_snow=False):
    """Lap siding / board-and-batten / plank look: wave bands bump along an axis (object space)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        vec = S._coord(N, Lk, "Object")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(vec, sep.inputs[0])
        dv = N.new("ShaderNodeMath")
        dv.operation = "DIVIDE"
        Lk.new(sep.outputs[axis], dv.inputs[0])
        dv.inputs[1].default_value = spacing
        fr = N.new("ShaderNodeMath")
        fr.operation = "FRACT"
        Lk.new(dv.outputs[0], fr.inputs[0])          # saw 0..1 per board -> lap / batten edge in the bump
        fac, _nz = S._noise_var(N, Lk, vec, 0.8, var)
        col = S._mul_col(N, Lk, tuple(color), fac)
        if roof_snow:
            col = _snow_mix(N, Lk, col)
        Lk.new(col, p.inputs["Base Color"])
        S._bump(N, Lk, fr.outputs[0], p, depth, 0.01)
        p.inputs["Roughness"].default_value = rough
        return S._finish(m, p.outputs[0])
    return _cached(name, mk)


def _snow_mix(N, Lk, col_sock):
    """Mix towards white on up-facing surfaces by MH_Weather.snow (and a light frost)."""
    wg = group_node(N, weather_group())
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(geo.outputs["Normal"], sep.inputs[0])
    up = N.new("ShaderNodeMapRange")
    up.inputs["From Min"].default_value = 0.45
    up.inputs["From Max"].default_value = 0.8
    Lk.new(sep.outputs["Z"], up.inputs["Value"])
    s = N.new("ShaderNodeMath")
    s.operation = "MULTIPLY"
    Lk.new(up.outputs["Result"], s.inputs[0])
    Lk.new(wg.outputs["snow"], s.inputs[1])
    fr = N.new("ShaderNodeMath")
    fr.operation = "MULTIPLY_ADD"
    Lk.new(wg.outputs["frost"], fr.inputs[0])
    fr.inputs[1].default_value = 0.35
    Lk.new(s.outputs[0], fr.inputs[2])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    Lk.new(fr.outputs[0], mx.inputs["Factor"])
    Lk.new(col_sock, mx.inputs["A"])
    mx.inputs["B"].default_value = (0.92, 0.94, 0.97, 1.0)
    return mx.outputs["Result"]


def mat_objcolor(name, rough=0.75, roof=False):
    """Base colour from the object's colour (Object Info) - one material for every neighbour house siding."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        oi = N.new("ShaderNodeObjectInfo")
        vec = S._coord(N, Lk, "Object")
        fac, _ = S._noise_var(N, Lk, vec, 0.6, 0.05)
        col = S._mul_col(N, Lk, oi.outputs["Color"], fac)
        if roof:
            col = _snow_mix(N, Lk, col)
        Lk.new(col, p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = rough
        return S._finish(m, p.outputs[0])
    return _cached(name, mk)


def mat_glow(name, color, strength=3.0, emit=None):
    """Emissive (lamps, lit windows). Strength is keyed by presets/lights events (returns the material)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        p.inputs["Base Color"].default_value = color
        p.inputs["Emission Color"].default_value = emit or color
        p.inputs["Emission Strength"].default_value = strength
        p.inputs["Roughness"].default_value = 0.4
        return S._finish(m, p.outputs[0], haze=False)
    return _cached(name, mk)


def emission_socket(mat):
    p = mat.node_tree.nodes.get("Principled BSDF")
    return p.inputs["Emission Strength"]


def mat_water(name="mh_water"):
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        p.inputs["Base Color"].default_value = hexc("1f3a3a")
        p.inputs["Roughness"].default_value = 0.04
        p.inputs["Coat Weight"].default_value = 0.6
        try:
            p.inputs["Transmission Weight"].default_value = 0.35
        except Exception:
            pass
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        driver_expr(mp.inputs["Location"], "default_value", "frame*-0.035", 1)    # flow N -> S
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.6
        nz.inputs["Detail"].default_value = 6.0
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.25, 0.04)
        return S._finish(m, p.outputs[0])
    return _cached(name, mk)


def mat_foam(name="mh_foam"):
    return _cached(name, lambda: S.pbr(name, hexc("eef3f5"), 0.5, var=0.15, var_scale=4.0, bump=0.3))


# ================================================================ mesh helpers
def bm_cyl(bm, p0, p1, r0, r1=None, seg=8, mi=0, caps=True):
    """Tapered cylinder between two points."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0
    h = ax.length
    res = bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r0, radius2=r1, depth=h)
    vs = res["verts"]
    q = Vector((0, 0, 1)).rotation_difference(ax.normalized())
    bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=q.to_matrix())
    bmesh.ops.translate(bm, verts=vs, vec=(p0 + p1) / 2)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def bm_sphere(bm, c, r, sub=2, mi=0, jitter=0.0, seed=0):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    vs = res["verts"]
    rr = random.Random(seed)
    for v in vs:
        v.co *= 1.0 + (rr.uniform(-jitter, jitter) if jitter else 0.0)
    r = r if isinstance(r, (tuple, list)) else (r, r, r)
    bmesh.ops.scale(bm, vec=r, verts=vs)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def bm_uvsphere(bm, c, r, seg=12, rings=8, mi=0):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    vs = res["verts"]
    r = r if isinstance(r, (tuple, list)) else (r, r, r)
    bmesh.ops.scale(bm, vec=r, verts=vs)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def bm_box_rot(bm, center, size, yaw_deg, mi=0):
    vs = S.bm_box(bm, (0, 0, 0), size, mi)
    bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=_rotz(yaw_deg))
    bmesh.ops.translate(bm, verts=vs, vec=center)
    return vs


def _rotz(deg):
    from mathutils import Matrix
    return Matrix.Rotation(math.radians(deg), 3, "Z")


def bm_segment_box(bm, a, b, z0, z1, thick, mi=0):
    """Vertical slab from XY point a to b (fence boards, walls), bottom z0 / top z1 (scalars or (za, zb))."""
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    d = (b - a)
    Lg = d.length
    if Lg < 1e-4:
        return
    d.normalize()
    n = Vector((-d.y, d.x, 0)) * (thick / 2)
    za0, zb0 = (z0, z0) if not isinstance(z0, (tuple, list)) else z0
    za1, zb1 = (z1, z1) if not isinstance(z1, (tuple, list)) else z1
    pts = [a - n, b - n, b + n, a + n]
    bot = [bm.verts.new((p.x, p.y, z)) for p, z in zip(pts, (za0, zb0, zb0, za0))]
    top = [bm.verts.new((p.x, p.y, z)) for p, z in zip(pts, (za1, zb1, zb1, za1))]
    fs = [bm.faces.new(list(reversed(bot))), bm.faces.new(top)]
    for i in range(4):
        j = (i + 1) % 4
        fs.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
    for f in fs:
        f.material_index = mi


def mesh_obj(name, bm, mats, smooth=False, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = S.mesh_from_bm(name, bm, mats, smooth)
    return S.obj(name, me, loc, rot)


def curve_line(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 1
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1.0)
    cu.materials.append(mat)
    return L.link(bpy.data.objects.new(name, cu))


def catenary(a, b, sag, n=12):
    out = []
    for i in range(n + 1):
        t = i / float(n)
        p = [a[k] + (b[k] - a[k]) * t for k in range(3)]
        p[2] -= sag * 4 * t * (1 - t)
        out.append(tuple(p))
    return out


# ================================================================ geometry-nodes instancing
def scatter_gn(name, template, pts, rots=None, scales=None, coll=None):
    """True instancing: one point-cloud mesh + a Geometry Nodes 'Instance on Points' modifier pointing at
    `template` (an object). pts = [(x, y, z)], rots = [z radians], scales = [s]. Falls back to linked duplicates if
    the GN API differs. Returns the scatter object."""
    n = len(pts)
    if n == 0:
        return None
    rots = rots or [0.0] * n
    scales = scales or [1.0] * n
    me = bpy.data.meshes.new(name + "_pts")
    me.from_pydata([tuple(p) for p in pts], [], [])
    try:
        ra = me.attributes.new("mh_rot", "FLOAT_VECTOR", "POINT")
        ra.data.foreach_set("vector", [c for r in rots for c in (0.0, 0.0, r)])
        sa = me.attributes.new("mh_scale", "FLOAT", "POINT")
        sa.data.foreach_set("value", list(scales))
        ob = L.link(bpy.data.objects.new(name, me))
        mod = ob.modifiers.new("scatter", "NODES")
        mod.node_group = _scatter_tree(template)
        return ob
    except Exception as ex:  # pragma: no cover
        print("[mh] GN scatter failed (%s); linked duplicates for %s" % (ex, name))
        for i, (p, r, s) in enumerate(zip(pts, rots, scales)):
            S.obj("%s_%d" % (name, i), template.data, p, (0, 0, r), (s, s, s))
        return None


def _scatter_tree(template):
    key = "MH_scatter_" + template.name
    ng = bpy.data.node_groups.get(key)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(key, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    iop = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = template
    try:
        oi.inputs["As Instance"].default_value = True
    except Exception:
        pass
    rot = N.new("GeometryNodeInputNamedAttribute")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs["Name"].default_value = "mh_rot"
    scl = N.new("GeometryNodeInputNamedAttribute")
    scl.data_type = "FLOAT"
    scl.inputs["Name"].default_value = "mh_scale"
    Lk.new(gi.outputs[0], iop.inputs["Points"])
    Lk.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    try:
        e2r = N.new("FunctionNodeEulerToRotation")
        Lk.new(rot.outputs["Attribute"], e2r.inputs[0])
        Lk.new(e2r.outputs[0], iop.inputs["Rotation"])
    except Exception:
        Lk.new(rot.outputs["Attribute"], iop.inputs["Rotation"])
    Lk.new(scl.outputs["Attribute"], iop.inputs["Scale"])
    Lk.new(iop.outputs["Instances"], go.inputs[0])
    return ng


def template_obj(name, me):
    """A hidden source object for GN instances (kept out of the render; its instances render)."""
    o = S.obj(name, me)
    o.hide_render = True
    o.location = (0, 0, -1000.0)
    return o


# ================================================================ anchors
ANC_PREFIX, CAM_PREFIX = "ANC_", "CAM_"


def anchor_empty(ctx, name, loc, parent=None, register=True, prefix=ANC_PREFIX):
    """Shared one-shot interface: every anchor is an empty named ANC_<id> (CAM_<id> = a stop's camera position,
    prefix=CAM_PREFIX, never registered for tracks). Re-defining an id moves the existing empty (no .001 copies)."""
    e = bpy.data.objects.get(prefix + name)
    if e is None or e.type != "EMPTY":
        e = L.link(bpy.data.objects.new(prefix + name, None))
    e.parent = parent                     # reset on re-definition (a reused empty must not keep an old parent)
    e.location = loc
    e.empty_display_size = 0.3
    if register:
        S.anchor(ctx, name, e)
    return e


def normalize_anchors(ctx):
    """Every registered anchor becomes an ANC_<id> empty: anchors registered as (object, offset) by builders that
    did not use anchor_empty get a child empty at that offset (same screen track, interface-conformant name).
    Returns {id: empty}."""
    out = {}
    for name, (obj, off) in list(getattr(ctx, "anchors", {}).items()):
        nm = ANC_PREFIX + name
        if obj.name == nm and obj.type == "EMPTY" and tuple(off) == (0.0, 0.0, 0.0):
            out[name] = obj
            continue
        e = bpy.data.objects.get(nm)
        if e is None or e is obj:
            e = L.link(bpy.data.objects.new(nm, None))
        e.empty_display_size = 0.3
        e.parent = obj
        e.location = tuple(off)
        ctx.anchors[name] = (e, Vector((0.0, 0.0, 0.0)))
        out[name] = e
    return out

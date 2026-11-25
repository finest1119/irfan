"""CC0 asset library for the Mercer Hollow world (Page 2, session 6). Needs bpy.

Two halves:
1. BUILD (once, ~1-2 min):  Blender -b --factory-startup -P page2/blender/cc0_lib.py -- build
   Imports the Poly Haven glTF models from assets/cc0/polyhaven/models/, thins/decimates them to the 4 GB VRAM budget
   (PROPOSAL 7.3), bakes the world scale in, and saves assets/cc0/lib/mercer_cc0_lib.blend with RELATIVE texture
   paths (the .blend loads on Windows). Kenney GLB props are imported into the same library.
2. RUNTIME (every world build): get(name) appends one template object from the library (cached per process),
   wraps its materials in the scene haze, and returns it hidden (GN instances render it). ph_mat() makes a 2K
   Poly Haven PBR material (diff + nor_gl + arm) with box projection. Everything returns None when the library or
   a texture is missing, so the world falls back to the old procedural look.
"""
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # repo root (.../irfan)
CC0 = ROOT / "assets" / "cc0"
PH_MODELS = CC0 / "polyhaven" / "models"
PH_TEX = CC0 / "polyhaven" / "textures"
KENNEY = CC0 / "kenney"
LIB = CC0 / "lib" / "mercer_cc0_lib.blend"

# template name -> (glTF asset, source object prefix, recipe). Recipes: scale (uniform or xyz), leaf keep fraction
# (whole alpha cards/islands kept or dropped), card grow (compensates the thinning), branch decimate ratio.
TREES = {
    # broadleaf (stands in for the old oak/maple balloons): island_tree_02 is 4.2 x 3.4 m -> ~9-10 m tree
    "cc0_broadleaf_lod0": ("island_tree_02", "island_tree_02", dict(scale=(2.3, 2.3, 3.0), leaf_keep=0.72, grow=1.12, branch=0.14)),
    "cc0_broadleaf_lod1": ("island_tree_02", "island_tree_02", dict(scale=(2.3, 2.3, 3.0), leaf_keep=0.2, grow=1.75, branch=0.03)),
    # s7 second broadleaf (maple slot): tree_small_02, a slender curved trunk + dense clustered canopy, 4.65 m -> ~9 m.
    # 1.94M leaf tris in the source, so it is thinned harder than island_tree_02.
    "cc0_broadleaf2_lod0": ("tree_small_02", "tree_small_02", dict(scale=2.0, leaf_keep=0.24, grow=1.45, branch=0.3)),
    "cc0_broadleaf2_lod1": ("tree_small_02", "tree_small_02", dict(scale=2.0, leaf_keep=0.07, grow=2.3, branch=0.06)),
    # pine (pine_sapling_small a/c, 1.0-1.3 m) -> 5-6 m young pines (sparse by nature: keep every twig near camera)
    "cc0_pine_lod0": ("pine_sapling_small", "pine_sapling_small_a", dict(scale=4.4, leaf_keep=1.0, grow=1.0, branch=1.0)),
    "cc0_pine_lod1": ("pine_sapling_small", "pine_sapling_small_a", dict(scale=4.4, leaf_keep=0.3, grow=1.6, branch=1.0)),
    "cc0_pine2_lod0": ("pine_sapling_small", "pine_sapling_small_c", dict(scale=5.0, leaf_keep=1.0, grow=1.0, branch=1.0)),
}
SIMPLE = {   # name -> (asset, object name, scale, decimate ratio)
    "cc0_shrub_big_a": ("shrub_02", "shrub_02_a", 0.9, 1.0),
    "cc0_shrub_big_b": ("shrub_02", "shrub_02_c", 0.7, 1.0),
    "cc0_shrub_big_c": ("shrub_02", "shrub_02_d", 0.85, 1.0),
    "cc0_bushtree_a": ("shrub_02", "shrub_02_c", 2.6, 1.0),      # dense small tree for the woods mix (~6 m)
    "cc0_bushtree_b": ("shrub_02", "shrub_02_a", 3.0, 1.0),
    "cc0_plant_a": ("shrub_03", "shrub_03_a", 1.6, 1.0),
    "cc0_plant_b": ("shrub_03", "shrub_03_b", 1.6, 1.0),
    "cc0_plant_c": ("shrub_03", "shrub_03_c", 1.8, 1.0),
    "cc0_groundcover": ("shrub_04", "shrub_04", 1.4, 0.35),
    "cc0_grass_a": ("grass_medium_02", "grass_medium_02_a", 1.6, 1.0),
    "cc0_grass_b": ("grass_medium_02", "grass_medium_02_b", 1.5, 1.0),
    "cc0_grass_c": ("grass_medium_02", "grass_medium_02_c", 1.4, 1.0),
    "cc0_grass_d": ("grass_medium_02", "grass_medium_02_d", 1.3, 1.0),
    "cc0_grass_e": ("grass_medium_02", "grass_medium_02_e", 1.1, 1.0),
    "cc0_tuft_a": ("grass_bermuda_01", "grass_bermuda_01_seedling_a", 2.2, 1.0),
    "cc0_tuft_b": ("grass_bermuda_01", "grass_bermuda_01_seedling_d", 2.2, 1.0),
    "cc0_rock_a": ("rock_moss_set_01", "rock_moss_set_01_rock01", 0.32, 0.35),
    "cc0_rock_b": ("rock_moss_set_01", "rock_moss_set_01_rock03", 0.36, 0.6),
    "cc0_rock_c": ("rock_moss_set_01", "rock_moss_set_01_rock04", 0.3, 0.35),
    "cc0_rock_d": ("rock_moss_set_01", "rock_moss_set_01_rock06", 0.34, 0.4),
    "cc0_pebble": ("rock_07", "rock_07", 1.6, 0.15),
}
KENNEY_PROPS = {   # name -> (kit, glb file)
    "k_fridge": ("furniture-kit", "kitchenFridge.glb"),
    "k_cabinet": ("furniture-kit", "kitchenCabinet.glb"),
    "k_cabinet_drawer": ("furniture-kit", "kitchenCabinetDrawer.glb"),
    "k_sink": ("furniture-kit", "kitchenSink.glb"),
    "k_stove": ("furniture-kit", "kitchenStove.glb"),
    "k_upper": ("furniture-kit", "kitchenCabinetUpperDouble.glb"),
    "k_hood": ("furniture-kit", "hoodModern.glb"),
    "k_coffee": ("furniture-kit", "kitchenCoffeeMachine.glb"),
    "k_toaster": ("furniture-kit", "toaster.glb"),
    "k_plant": ("furniture-kit", "plantSmall2.glb"),
    "k_lamp": ("furniture-kit", "lampRoundTable.glb"),
    "k_stool": ("furniture-kit", "stoolBar.glb"),
    "k_box": ("furniture-kit", "cardboardBoxClosed.glb"),
    "k_box_open": ("furniture-kit", "cardboardBoxOpen.glb"),
    "k_radio": ("furniture-kit", "radio.glb"),
    "k_workbench": ("survival-kit", "workbench.glb"),
    "k_barrel": ("survival-kit", "barrel.glb"),
    "k_bucket": ("survival-kit", "bucket.glb"),
    "k_crate": ("survival-kit", "box-large.glb"),
    "k_crate_small": ("survival-kit", "box.glb"),
    "k_shovel": ("survival-kit", "tool-shovel.glb"),
    "k_axe": ("survival-kit", "tool-axe.glb"),
    "k_hammer": ("survival-kit", "tool-hammer.glb"),
    "k_planks": ("survival-kit", "resource-planks.glb"),
}


# ================================================================ build half
ALPHA_FROM_BLACK = ("leaves", "grass_medium", "grass_bermuda")


def _alpha_from_black(m):
    """Poly Haven's 1k glTF ships the cut-out cards as JPG (no alpha): rebuild alpha from the black background."""
    if m is None or m.node_tree is None or not any(k in m.name for k in ALPHA_FROM_BLACK):
        return False
    N, Lk = m.node_tree.nodes, m.node_tree.links
    p = next((n for n in N if n.type == "BSDF_PRINCIPLED"), None)
    bc = p.inputs["Base Color"]
    if p is None or not bc.is_linked:
        return False
    src = bc.links[0].from_socket
    sep = N.new("ShaderNodeSeparateColor")
    Lk.new(src, sep.inputs[0])
    m1 = N.new("ShaderNodeMath"); m1.operation = "MAXIMUM"
    Lk.new(sep.outputs[0], m1.inputs[0]); Lk.new(sep.outputs[1], m1.inputs[1])
    m2 = N.new("ShaderNodeMath"); m2.operation = "MAXIMUM"
    Lk.new(m1.outputs[0], m2.inputs[0]); Lk.new(sep.outputs[2], m2.inputs[1])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.035, 0.11
    Lk.new(m2.outputs[0], mr.inputs["Value"])
    for lk in list(p.inputs["Alpha"].links):
        Lk.remove(lk)
    Lk.new(mr.outputs["Result"], p.inputs["Alpha"])
    try:
        m.surface_render_method = "DITHERED"
    except Exception:
        pass
    return True


def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import(asset):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(PH_MODELS / asset / ("%s_1k.gltf" % asset)))
    return [o for o in bpy.data.objects if o not in before]


def _islands(me, poly_mask):
    """Connected-component label per polygon (only polygons where poly_mask is True), via label propagation."""
    import numpy as np
    nv, npoly = len(me.vertices), len(me.polygons)
    ls = np.zeros(npoly, dtype=np.int64)
    lt = np.zeros(npoly, dtype=np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    poly_of_loop = np.repeat(np.arange(npoly), lt)
    lab = np.arange(nv, dtype=np.int64)
    m_loop = poly_mask[poly_of_loop]
    lv_m, pl_m = lv[m_loop], poly_of_loop[m_loop]
    for _ in range(200):
        pmin = np.full(npoly, np.iinfo(np.int64).max, dtype=np.int64)
        np.minimum.at(pmin, pl_m, lab[lv_m])
        new = lab.copy()
        np.minimum.at(new, lv_m, pmin[pl_m])
        if np.array_equal(new, lab):
            break
        lab = new
    plab = np.full(npoly, -1, dtype=np.int64)
    first = ls[poly_mask]
    plab[poly_mask] = lab[lv[first]]
    return plab


def _thin_leaves(ob, leaf_mat_ids, keep, grow, seed=7):
    """Drop whole leaf cards (islands) so ~keep of them stay; scale the kept cards up about their centre."""
    import numpy as np
    me = ob.data
    mi = np.zeros(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("material_index", mi)
    mask = np.isin(mi, list(leaf_mat_ids))
    if not mask.any() or keep >= 0.999:
        return 0
    plab = _islands(me, mask)
    ids = np.unique(plab[mask])
    rng = np.random.default_rng(seed)
    kept = set(ids[rng.random(len(ids)) < keep].tolist())
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    dead, groups = [], {}
    for f in bm.faces:
        lab = plab[f.index]
        if lab < 0:
            continue
        if lab in kept:
            groups.setdefault(lab, set()).update(f.verts)
        else:
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    if grow != 1.0:
        for vs in groups.values():
            vs = [v for v in vs if v.is_valid]
            if not vs:
                continue
            c = sum((v.co for v in vs), vs[0].co * 0) / len(vs)
            for v in vs:
                v.co = c + (v.co - c) * grow
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return len(kept)


def _decimate_mats(ob, mat_ids, ratio):
    """Collapse-decimate only the faces of mat_ids (branches); leaf cards and the trunk keep their shape."""
    if ratio >= 0.999:
        return
    vg = ob.vertex_groups.new(name="dec")
    idx = {v for p in ob.data.polygons if p.material_index in mat_ids for v in p.vertices}
    vg.add(list(idx), 1.0, "REPLACE")
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    mod.vertex_group = "dec"
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    vg = ob.vertex_groups.get("dec")
    if vg is not None:
        ob.vertex_groups.remove(vg)


def _bake_scale(ob, s):
    s = (s, s, s) if isinstance(s, (int, float)) else s
    ob.scale = s
    ob.location = (0, 0, 0)
    ob.rotation_mode = "XYZ"
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # base on the ground: lowest vertex at z=0 (trees sink 10 cm at placement)
    zmin = min(v.co.z for v in ob.data.vertices)
    for v in ob.data.vertices:
        v.co.z -= zmin


def _keep(ob, name):
    for o in list(bpy.data.objects):
        if o != ob and o.name.startswith(name + "__src"):
            pass
    ob.name = name
    ob.data.name = name
    ob.parent = None
    ob.use_fake_user = True
    ob.data.use_fake_user = True


def build_library():
    import time
    t0 = time.time()
    _clear()
    made = {}
    scratch = bpy.data.collections.new("cc0_lib")
    bpy.context.scene.collection.children.link(scratch)
    # ---- trees
    for name, (asset, src, rec) in TREES.items():
        objs = _import(asset)
        ob = next(o for o in objs if o.type == "MESH" and o.name.startswith(src))
        for o in objs:
            if o is not ob:
                bpy.data.objects.remove(o, do_unlink=True)
        ob.data = ob.data.copy()
        mats = [m.name for m in ob.data.materials]
        leaf_ids = {i for i, n in enumerate(mats) if "leaves" in n or "twig" in n}
        branch_ids = {i for i, n in enumerate(mats) if "branches" in n}
        _bake_scale(ob, rec["scale"])
        n0 = len(ob.data.polygons)
        _thin_leaves(ob, leaf_ids, rec["leaf_keep"], rec["grow"])
        if branch_ids:
            _decimate_mats(ob, branch_ids, rec["branch"])
        _keep(ob, name)
        made[name] = (n0, sum(len(p.vertices) - 2 for p in ob.data.polygons))
        print("[cc0] %s: %d -> %d tris (%.0fs)" % (name, n0, made[name][1], time.time() - t0))
    # ---- shrubs, grass, rocks
    for name, (asset, src, s, dec) in SIMPLE.items():
        objs = _import(asset)
        ob = next(o for o in objs if o.type == "MESH" and o.name.startswith(src))
        for o in objs:
            if o is not ob:
                bpy.data.objects.remove(o, do_unlink=True)
        ob.data = ob.data.copy()
        _bake_scale(ob, s)
        if dec < 0.999:
            mod = ob.modifiers.new("dec", "DECIMATE")
            mod.ratio = dec
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.modifier_apply(modifier=mod.name)
        _keep(ob, name)
        made[name] = (0, sum(len(p.vertices) - 2 for p in ob.data.polygons))
    # ---- Kenney props (joined into one mesh each, metres; Kenney kits are ~1 unit = 1 m tile)
    for name, (kit, fn) in KENNEY_PROPS.items():
        path = _kenney_glb(kit, fn)
        if path is None:
            print("[cc0] missing kenney %s/%s" % (kit, fn))
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        objs = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in objs if o.type == "MESH"]
        for o in bpy.context.view_layer.objects:
            o.select_set(o in meshes)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        for o in list(bpy.data.objects):
            if o not in before and o != ob:
                bpy.data.objects.remove(o, do_unlink=True)
        _bake_scale(ob, 1.0)
        _keep(ob, name)
        made[name] = (0, sum(len(p.vertices) - 2 for p in ob.data.polygons))
    fixed = [m.name for m in bpy.data.materials if _alpha_from_black(m)]
    print("[cc0] alpha rebuilt from black for: %s" % fixed)
    for o in list(scratch.objects):
        scratch.objects.unlink(o)
    LIB.parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.data.objects:
        if o.name not in made:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.file.make_paths_relative()
    # make_paths_relative needs the target path: save first, then fix + resave
    bpy.ops.wm.save_as_mainfile(filepath=str(LIB), relative_remap=True, compress=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    absn = [im.filepath for im in bpy.data.images if im.filepath and not im.filepath.startswith("//")]
    print("[cc0] library saved %s (%.1f MB, %.0fs); absolute image paths left: %d" % (
        LIB, LIB.stat().st_size / 1e6, time.time() - t0, len(absn)))
    for k, (a, b) in made.items():
        print("[cc0]   %-22s %8d tris" % (k, b))


def _kenney_glb(kit, fn):
    for sub in ("Models/GLB format", "Models/GLTF format"):
        p = KENNEY / kit / sub / fn
        if p.exists():
            return p
    return None


# ================================================================ runtime half
_GOT = {}


def available():
    return LIB.exists()


def get(name, haze=True):
    """Append template `name` from the library (once per process). Returns a hidden object or None."""
    if name in _GOT:
        return _GOT[name]
    ob = None
    if LIB.exists():
        try:
            with bpy.data.libraries.load(str(LIB), link=False, relative=False) as (src, dst):
                if name in src.objects:
                    dst.objects = [name]
            ob = bpy.data.objects.get(name)
        except Exception as ex:
            print("[cc0] could not append %s: %s" % (name, ex))
    if ob is not None:
        _dedupe_images(ob)
        bpy.context.scene.collection.objects.link(ob) if ob.name not in bpy.context.scene.collection.objects else None
        ob.hide_render = True
        ob.hide_viewport = True
        ob.location = (0, 0, -1000.0)
        if haze:
            for m in ob.data.materials:
                if m is not None:
                    _haze_wrap(m)
        if name.startswith("cc0_"):            # s7: Poly Haven plants/rocks follow MH_Weather frost/snow (default 0)
            rocky = name.startswith(("cc0_rock", "cc0_pebble"))
            for m in ob.data.materials:
                if m is not None:
                    weather_wrap(m, foliage=not rocky)
    _GOT[name] = ob
    return ob


def _dedupe_images(ob):
    """Library materials may carry duplicate image datablocks of the same file (one per glTF object): keep one."""
    seen = {}
    for im in bpy.data.images:
        if im.filepath:
            key = bpy.path.abspath(im.filepath, library=im.library)
            if key in seen and seen[key] != im:
                im.user_remap(seen[key])
            else:
                seen.setdefault(key, im)


def place(name, loc, rot_z=0.0, scale=1.0, coll=None):
    """A visible linked copy of a library template (props)."""
    tpl = get(name)
    if tpl is None:
        return None
    o = bpy.data.objects.new(name + "_inst", tpl.data)
    (coll or bpy.context.collection).objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    o.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return o


def _haze_wrap(m):
    """Distance haze like scene_lib._fog_wrap, but the fog mix is multiplied by alpha (leaf cards stay see-through)."""
    if m.get("mh_hazed"):
        return
    m["mh_hazed"] = True
    nt = m.node_tree
    if nt is None:
        return
    import scene_lib as L
    out = nt.nodes.get("Material Output") or next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if out is None or p is None or L.FOG.density <= 0:
        return
    N, Lk = nt.nodes, nt.links
    cam = N.new("ShaderNodeCameraData")
    sub = N.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = L.FOG.start
    Lk.new(cam.outputs["View Distance"], sub.inputs[0])
    mx = N.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0
    Lk.new(sub.outputs[0], mx.inputs[0])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = -L.FOG.density
    Lk.new(mx.outputs[0], mul.inputs[0])
    ex = N.new("ShaderNodeMath"); ex.operation = "EXPONENT"
    Lk.new(mul.outputs[0], ex.inputs[0])
    inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    Lk.new(ex.outputs[0], inv.inputs[1])
    fac = inv.outputs[0]
    a = p.inputs["Alpha"]
    if a.is_linked:
        ma = N.new("ShaderNodeMath"); ma.operation = "MULTIPLY"
        Lk.new(fac, ma.inputs[0])
        Lk.new(a.links[0].from_socket, ma.inputs[1])
        fac = ma.outputs[0]
    em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = L.FOG.color
    mix = N.new("ShaderNodeMixShader")
    Lk.new(fac, mix.inputs[0])
    Lk.new(p.outputs[0], mix.inputs[1])
    Lk.new(em.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], out.inputs["Surface"])


def weather_wrap(m, foliage=True):
    """Frost/snow for library materials, driven by the MH_Weather group the presets key (frost / snow presets).
    Rocks: the terrain/roof rule (B._snow_mix: white on up-facing surfaces + a light frost). Foliage/grass cards
    face every way, so they are not normal-gated: frost 0.35 + snow (0.35 + 0.4 * up-facing). Both are an exact
    no-op at frost = snow = 0 (Mix factor 0), so day/dusk episodes render unchanged."""
    if m.get("mh_weather") or m.node_tree is None:
        return False
    p = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if p is None:
        return False
    import mh_blender as B
    m["mh_weather"] = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    bc = p.inputs["Base Color"]
    if bc.is_linked:
        src = bc.links[0].from_socket
    else:
        rgb = N.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = tuple(bc.default_value)
        src = rgb.outputs[0]
    if not foliage:
        Lk.new(B._snow_mix(N, Lk, src), bc)
        return True
    wg = B.group_node(N, B.weather_group())
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(geo.outputs["Normal"], sep.inputs[0])
    up = N.new("ShaderNodeMapRange")
    up.inputs["From Min"].default_value = 0.0
    up.inputs["From Max"].default_value = 0.8
    up.inputs["To Min"].default_value = 0.35
    up.inputs["To Max"].default_value = 0.75
    Lk.new(sep.outputs["Z"], up.inputs["Value"])
    sn = N.new("ShaderNodeMath")
    sn.operation = "MULTIPLY"
    Lk.new(up.outputs["Result"], sn.inputs[0])
    Lk.new(wg.outputs["snow"], sn.inputs[1])
    fr = N.new("ShaderNodeMath")
    fr.operation = "MULTIPLY_ADD"
    fr.use_clamp = True
    Lk.new(wg.outputs["frost"], fr.inputs[0])
    fr.inputs[1].default_value = 0.35
    Lk.new(sn.outputs[0], fr.inputs[2])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    Lk.new(fr.outputs[0], mx.inputs["Factor"])
    Lk.new(src, mx.inputs["A"])
    mx.inputs["B"].default_value = (0.9, 0.93, 0.97, 1.0)
    Lk.new(mx.outputs["Result"], bc)
    return True


def tex_path(asset, kind, res="2k"):
    p = PH_TEX / asset / ("%s_%s_%s.jpg" % (asset, kind, res))
    return p if p.exists() else None


def ph_mat(name, asset, scale=1.0, tint=None, rough_mul=1.0, normal=0.8, rot=0.0, coord="Object", haze=True,
           blend=0.25, walls_horizontal=False, max_px=2048, snow=False):
    """2K Poly Haven PBR (diff + nor_gl + arm) with box projection on object coords (scale = texture metres per
    tile). tint multiplies the base colour. Returns None if the textures are missing."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    d, n, arm = tex_path(asset, "diff"), tex_path(asset, "nor_gl"), tex_path(asset, "arm")
    if d is None:
        return None
    import scene_lib as L
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    p = N.get("Principled BSDF")
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / scale, 1.0 / scale, 1.0 / scale)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    src = tc.outputs[coord]
    if walls_horizontal:            # boards run horizontally on every vertical wall: feed (z, z, x + y) to the box map
        sp = N.new("ShaderNodeSeparateXYZ")
        Lk.new(src, sp.inputs[0])
        ad = N.new("ShaderNodeMath")
        ad.operation = "ADD"
        Lk.new(sp.outputs["X"], ad.inputs[0])
        Lk.new(sp.outputs["Y"], ad.inputs[1])
        cb = N.new("ShaderNodeCombineXYZ")
        Lk.new(sp.outputs["Z"], cb.inputs["X"])
        Lk.new(sp.outputs["Z"], cb.inputs["Y"])
        Lk.new(ad.outputs[0], cb.inputs["Z"])
        src = cb.outputs[0]
    Lk.new(src, mp.inputs["Vector"])

    def img(path, non_color):
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(path), check_existing=True)
        if max_px < max(t.image.size[:]) and not t.image.get("mh_scaled"):
            t.image.scale(max_px, max_px)          # PROPOSAL 7.3: 2K only for hero objects, 1K for the rest
            t.image["mh_scaled"] = True
        if non_color:
            t.image.colorspace_settings.name = "Non-Color"
        t.projection = "BOX"
        t.projection_blend = blend
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    td = img(d, False)
    col = td.outputs["Color"]
    if tint is not None:
        mx = N.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        Lk.new(col, mx.inputs["A"])
        mx.inputs["B"].default_value = tuple(tint[:3]) + (1.0,)
        col = mx.outputs["Result"]
    if snow:                                   # s7: roofs keep the old roof_snow behaviour (MH_Weather frost/snow)
        import mh_blender as B
        col = B._snow_mix(N, Lk, col)
    Lk.new(col, p.inputs["Base Color"])
    if arm is not None:
        ta = img(arm, True)
        sep = N.new("ShaderNodeSeparateColor")
        Lk.new(ta.outputs["Color"], sep.inputs[0])
        rm = N.new("ShaderNodeMath")
        rm.operation = "MULTIPLY"
        rm.inputs[1].default_value = rough_mul
        rm.use_clamp = True
        Lk.new(sep.outputs[1], rm.inputs[0])
        Lk.new(rm.outputs[0], p.inputs["Roughness"])
        Lk.new(sep.outputs[2], p.inputs["Metallic"])
    if n is not None:
        tn = img(n, True)
        nm = N.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal
        Lk.new(tn.outputs["Color"], nm.inputs["Color"])
        Lk.new(nm.outputs["Normal"], p.inputs["Normal"])
    if haze:
        L._fog_wrap(m, p.outputs[0])
    return m


def swap_material(old_name, new_mat):
    """Replace material `old_name` in every slot of every object (keeps meshes/UVs; box projection needs none)."""
    old = bpy.data.materials.get(old_name)
    if old is None or new_mat is None:
        return 0
    n = 0
    for me in bpy.data.meshes:
        for i, m in enumerate(me.materials):
            if m == old:
                me.materials[i] = new_mat
                n += 1
    return n


def vram_estimate():
    """Rough MB for the CC0 part: unique template meshes (BVH ~ 90 B/tri + verts) + images (RGBA float on GPU:
    4 B/px for 8-bit textures)."""
    tris = 0
    for ob in _GOT.values():
        if ob is not None:
            tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    px = 0
    for im in bpy.data.images:
        if im.filepath and ("cc0" in im.filepath or im.filepath.startswith("//")):
            px += im.size[0] * im.size[1]
    return {"cc0_template_tris": tris, "cc0_geom_mb": round(tris * 120 / 1e6, 1), "cc0_tex_mb": round(px * 4 / 1e6, 1)}


if __name__ == "__main__" and "build" in sys.argv:
    build_library()

"""v2 look-dev library: bright daytime world (look test, 23 Nov 2026).

Separate from scene_lib / scene_lib_air on purpose: nothing here changes the v1 builders or episodes.
It reuses only small helpers from scene_lib (kf, hexc, the distance-haze wrapper, the Kenney car loader, Ctx).

Look (from Irfan's reference reels):
  * daytime sky (Poly Haven HDRI if present in assets/polyhaven/, else Blender's physical sky texture
    plus procedural clouds), warm sun lamp with soft shadows, raytraced AO / GI, light distance haze,
    AgX view transform, gentle bloom;
  * a full world: patchwork fields, airfield grass, a textured runway (markings baked into ONE image per
    surface, so no coplanar decal planes = no z-fighting), taxiway, apron, terminal, tower, hangars,
    fence, parking with Kenney cars, suburbs with orange roofs, trees, a distant city and hills;
  * a smoother light aircraft (lofted fuselage, NACA-section wings, glass canopy, livery + panel lines
    in the shader, wheel pants, spinning prop);
  * NO 3D text: every caption / label / chip is a 2D overlay done after rendering (pipeline/v2_test.py).
    The builder exports per-frame screen positions of the plane so labels can track it.

Non-graphic rule as in v1: the plane is only shown flying a normal approach. No wreckage, no fire.
"""
import glob
import math
import os
import random

import bpy
import bmesh
from mathutils import Vector, Matrix

import scene_lib as L
from scene_lib import hexc, kf

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
POLYHAVEN_DIR = os.path.join(ROOT, "assets", "polyhaven")

# ---------------------------------------------------------------- palette (natural daylight)
WHITE_PAINT = hexc("f2f4f6")
NAVY_PAINT = hexc("1c2f5c")
RED_PAINT = hexc("d8262f")
GLASS_TINT = hexc("1b2a3a")
ROOF_COLS = [hexc(c) for c in ("c4622d", "b5532a", "d0763f", "8a4a32", "5d6066", "a94b2b", "7a7f86", "c98a4a")]
WALL_COLS = [hexc(c) for c in ("efe8dc", "e6dccb", "f4f1ea", "d9d4cb", "e9dfc6", "cfd6dc", "f1e6d2", "ddd2bf")]
LEAF_COLS = [hexc(c) for c in ("4f7a35", "5e8a3a", "41692f", "6b8f3e", "3d5f34", "758f45")]
HAZE = hexc("b9cbe0")

# set by build: texture folder (PIL-made runway/road textures) and scene-wide objects
TEX = {"dir": None}


# ================================================================ render + world
def setup_render_v2(scene, res, fps, frames, samples, out_dir, fmt="PNG"):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, frames
    e = scene.eevee
    e.taa_render_samples = samples
    e.use_shadows = True
    e.shadow_ray_count = 2
    e.shadow_step_count = 6
    try:
        e.use_raytracing = True
        e.ray_tracing_method = "SCREEN"
        e.ray_tracing_options.resolution_scale = "2"
        e.ray_tracing_options.use_denoise = True
        e.use_fast_gi = True
        e.fast_gi_method = "GLOBAL_ILLUMINATION"
        e.fast_gi_distance = 12.0
        e.fast_gi_resolution = "2"
    except Exception as ex:  # pragma: no cover
        print("[v2] raytracing settings partly unavailable:", ex)
    try:
        e.clamp_surface_indirect = 10.0
    except Exception:
        pass
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = 0.0
    scene.render.image_settings.file_format = fmt
    scene.render.image_settings.color_mode = "RGB"
    if fmt == "JPEG":      # episodes: q95 JPEG frames (~0.5 MB vs ~2 MB PNG; disk is tight), 4:4:4, no visible loss
        scene.render.image_settings.quality = 95
    else:
        scene.render.image_settings.compression = 15
    scene.render.filepath = out_dir.rstrip("/") + "/"
    scene.render.use_motion_blur = False
    scene.render.filter_size = 1.2
    _bloom(scene)


def _bloom(scene, strength=0.22, threshold=1.6):
    """Compositor glare (bloom). Optional: silently skipped if the API differs."""
    try:
        ng = bpy.data.node_groups.new("comp_v2", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        g = ng.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Threshold"].default_value = threshold
        g.inputs["Strength"].default_value = strength
        try:
            g.inputs["Size"].default_value = 0.6
        except Exception:
            pass
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], g.inputs["Image"])
        ng.links.new(g.outputs[0], out.inputs[0])
        scene.compositing_node_group = ng
        scene.render.use_compositing = True
    except Exception as ex:  # pragma: no cover
        print("[v2] bloom skipped:", ex)


def _find_hdri():
    """Only assets/polyhaven/hdri/ is searched (texture folders may hold EXR maps that are not skies)."""
    if os.environ.get("V2_NO_HDRI"):
        return None
    for pat in ("*.hdr", "*.exr"):
        hits = sorted(glob.glob(os.path.join(POLYHAVEN_DIR, "hdri", pat)))
        if hits:
            return hits[0]
    return None


# Sun position inside the HDRI (measured once from the brightest pixel; see BUILD-LOG v2 pipeline notes).
# phi = horizontal angle of the sun direction from +X (counter-clockwise, degrees) after Blender's equirect
# lookup with no rotation; elev = elevation in degrees.
HDRI_SUN = {"kloofendal_48d_partly_cloudy": {"phi": 144.0, "elev": 47.9}}


def hdri_sun_elev():
    h = _find_hdri()
    if not h:
        return None
    for k, v in HDRI_SUN.items():
        if k in os.path.basename(h):
            return v["elev"]
    return 45.0


# ---------------------------------------------------------------- Poly Haven PBR detail (CC0, 1K jpg)
PH_ASPHALT = {"asset": "aerial_asphalt_01", "amount": 0.45, "normal": 0.45}
PH_TEX = {  # asset: (real size in metres, linear mean colour of the diffuse map)
    "aerial_asphalt_01": (30.0, (0.139, 0.126, 0.141)),
    "aerial_grass_rock": (15.0, (0.173, 0.123, 0.025)),
    "concrete_floor_02": (2.0, (0.203, 0.171, 0.114)),
}


def _ph_path(asset, kind):
    p = os.path.join(POLYHAVEN_DIR, "textures", asset, "%s_%s_1k.jpg" % (asset, kind))
    return p if os.path.exists(p) else None


def ph_available(asset):
    return _ph_path(asset, "diff") is not None


def ph_detail(N, Lk, vec, asset, p, base_col, amount=0.6, hue=0.0, normal=0.6, rough_mix=0.4, scale_mul=1.0):
    """Modulate `base_col` (socket or RGBA tuple) with a Poly Haven texture in object space (metres).
    amount: how much of the texture's luminance variation is applied (0..1); hue: how much of its own colour.
    Links Base Color, Normal (OpenGL normal map) and Roughness into the Principled BSDF `p`.
    Returns True if the texture was found (else nothing is linked and the caller keeps its own shading)."""
    if not ph_available(asset):
        return False
    size, mean = PH_TEX[asset]
    mp = N.new("ShaderNodeMapping")
    s = 1.0 / (size * scale_mul)
    mp.inputs["Scale"].default_value = (s, s, s)
    Lk.new(vec, mp.inputs["Vector"])

    def img(kind, non_color):
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(_ph_path(asset, kind), check_existing=True)
        if non_color:
            t.image.colorspace_settings.name = "Non-Color"
        t.interpolation = "Linear"
        t.extension = "REPEAT"
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    dif = img("diff", False)
    # luminance-only variation (normalised to mean 1) and full-colour variation (normalised per channel)
    bw = N.new("ShaderNodeRGBToBW")
    Lk.new(dif.outputs["Color"], bw.inputs[0])
    lum_mean = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    lm = N.new("ShaderNodeMath")
    lm.operation = "DIVIDE"
    Lk.new(bw.outputs[0], lm.inputs[0])
    lm.inputs[1].default_value = lum_mean
    lum_col = N.new("ShaderNodeCombineColor")
    for i in range(3):
        Lk.new(lm.outputs[0], lum_col.inputs[i])
    tint = N.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    Lk.new(dif.outputs["Color"], tint.inputs["A"])
    tint.inputs["B"].default_value = (1.0 / mean[0], 1.0 / mean[1], 1.0 / max(0.01, mean[2]), 1.0)
    var = N.new("ShaderNodeMix")      # mix luminance-only and coloured variation
    var.data_type = "RGBA"
    var.inputs["Factor"].default_value = hue
    Lk.new(lum_col.outputs[0], var.inputs["A"])
    Lk.new(tint.outputs["Result"], var.inputs["B"])
    amt = N.new("ShaderNodeMix")      # 1 -> variation by `amount`
    amt.data_type = "RGBA"
    amt.inputs["Factor"].default_value = amount
    amt.inputs["A"].default_value = (1, 1, 1, 1)
    Lk.new(var.outputs["Result"], amt.inputs["B"])
    out = N.new("ShaderNodeMix")
    out.data_type = "RGBA"
    out.blend_type = "MULTIPLY"
    out.inputs["Factor"].default_value = 1.0
    if isinstance(base_col, tuple):
        out.inputs["A"].default_value = base_col
    else:
        Lk.new(base_col, out.inputs["A"])
    Lk.new(amt.outputs["Result"], out.inputs["B"])
    Lk.new(out.outputs["Result"], p.inputs["Base Color"])
    if normal > 0 and _ph_path(asset, "nor_gl"):
        nt_ = img("nor_gl", True)
        nm = N.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal
        Lk.new(nt_.outputs["Color"], nm.inputs["Color"])
        Lk.new(nm.outputs["Normal"], p.inputs["Normal"])
    if rough_mix > 0 and _ph_path(asset, "rough"):
        rt = img("rough", True)
        mr = N.new("ShaderNodeMix")
        mr.data_type = "FLOAT"
        mr.inputs["Factor"].default_value = rough_mix
        mr.inputs["A"].default_value = p.inputs["Roughness"].default_value
        Lk.new(rt.outputs["Color"], mr.inputs["B"])
        Lk.new(mr.outputs["Result"], p.inputs["Roughness"])
    return True


def sky_world(scene, sun_elev=38.0, sun_az=-35.0, strength=1.0, clouds=True, cloud_gain=None, aerosol=0.9,
              hdri_ok=True, hdri_strength=None):
    """World = Poly Haven HDRI if one is in assets/polyhaven/, else physical sky + procedural clouds.
    sun_az: degrees, same convention as the sun lamp's Z rotation (0 = sun behind a camera looking +Y)."""
    w = bpy.data.worlds.new("SkyV2")
    scene.world = w
    nt = w.node_tree
    N, Lk = nt.nodes, nt.links
    bg = N.get("Background") or N.new("ShaderNodeBackground")
    out = N.get("World Output") or N.new("ShaderNodeOutputWorld")
    hdri = _find_hdri() if hdri_ok else None
    if hdri:
        # rotate the HDRI so its sun sits where a sun lamp with Z rotation `sun_az` would put it
        # (lamp sun direction angle from +X = az - 90; HDRI sun angle phi; Mapping rotates the lookup vector)
        phi = next((v["phi"] for k, v in HDRI_SUN.items() if k in os.path.basename(hdri)), 144.0)
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(phi + 90.0 - sun_az))
        env = N.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri, check_existing=True)
        Lk.new(tc.outputs["Generated"], mp.inputs["Vector"])
        Lk.new(mp.outputs["Vector"], env.inputs["Vector"])
        Lk.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = hdri_strength
        # EEVEE extracts the HDRI sun into a shadow-casting light: no separate sun lamp needed
        for attr, val in (("sun_threshold", 6.0), ("use_sun_shadow", True), ("sun_angle", math.radians(1.5)),
                          ("sun_shadow_maximum_resolution", 0.002)):
            try:
                setattr(w, attr, val)
            except Exception:
                pass
        print("[v2] world: HDRI", os.path.basename(hdri))
        return w
    sky = N.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.sun_elevation = math.radians(sun_elev)
    # sky texture: sun_rotation 0 = sun towards +Y; our lamp convention puts the sun at -Y for az 0
    sky.sun_rotation = math.radians(180.0 - sun_az) % (2 * math.pi)
    try:
        sky.air_density = 1.0
        sky.aerosol_density = aerosol
    except Exception:
        pass
    col = sky.outputs["Color"]
    if clouds:
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(tc.outputs["Generated"], sep.inputs[0])

        def math_node(op, a=None, b=None, v0=None, v1=None, clamp=False):
            n = N.new("ShaderNodeMath")
            n.operation = op
            n.use_clamp = clamp
            if a is not None:
                Lk.new(a, n.inputs[0])
            elif v0 is not None:
                n.inputs[0].default_value = v0
            if b is not None:
                Lk.new(b, n.inputs[1])
            elif v1 is not None:
                n.inputs[1].default_value = v1
            return n.outputs[0]
        zc = math_node("MAXIMUM", sep.outputs["Z"], v1=0.035)
        u = math_node("DIVIDE", sep.outputs["X"], zc)
        v = math_node("DIVIDE", sep.outputs["Y"], zc)
        cmb = N.new("ShaderNodeCombineXYZ")
        Lk.new(u, cmb.inputs[0])
        Lk.new(v, cmb.inputs[1])
        cmb.inputs[2].default_value = 3.7
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "3D"
        nz.inputs["Scale"].default_value = 0.55
        nz.inputs["Detail"].default_value = 7.0
        nz.inputs["Roughness"].default_value = 0.58
        Lk.new(cmb.outputs[0], nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.50
        ramp.color_ramp.elements[1].position = 0.72
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        # fade clouds out towards the horizon (they would stretch to infinity) and below it
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.03
        mr.inputs["From Max"].default_value = 0.22
        Lk.new(sep.outputs["Z"], mr.inputs["Value"])
        mask = math_node("MULTIPLY", ramp.outputs["Color"], mr.outputs["Result"])
        mask = math_node("MULTIPLY", mask, v1=0.92)
        # cloud shading: brighter tops, slightly grey bellies (second noise)
        nz2 = N.new("ShaderNodeTexNoise")
        nz2.inputs["Scale"].default_value = 1.6
        nz2.inputs["Detail"].default_value = 3.0
        Lk.new(cmb.outputs[0], nz2.inputs["Vector"])
        shade = N.new("ShaderNodeValToRGB")
        shade.color_ramp.elements[0].color = (0.55, 0.58, 0.64, 1)
        shade.color_ramp.elements[1].color = (1.0, 0.99, 0.97, 1)
        Lk.new(nz2.outputs["Fac"], shade.inputs[0])
        bright = N.new("ShaderNodeMix")
        bright.data_type = "RGBA"
        bright.blend_type = "MULTIPLY"
        bright.inputs["Factor"].default_value = 1.0
        Lk.new(shade.outputs["Color"], bright.inputs["A"])
        bright.inputs["B"].default_value = (1, 1, 1, 1)
        # cloud brightness relative to the sky texture (tuned on stills)
        cb = N.new("ShaderNodeMix")
        cb.data_type = "RGBA"
        cb.blend_type = "MULTIPLY"
        cb.inputs["Factor"].default_value = 1.0
        Lk.new(bright.outputs["Result"], cb.inputs["A"])
        g = CLOUD_GAIN if cloud_gain is None else cloud_gain
        cb.inputs["B"].default_value = (g, g, g, 1)
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        Lk.new(mask, mix.inputs["Factor"])
        Lk.new(col, mix.inputs["A"])
        Lk.new(cb.outputs["Result"], mix.inputs["B"])
        col = mix.outputs["Result"]
    Lk.new(col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    print("[v2] world: procedural sky + clouds (no HDRI in assets/polyhaven/)")
    return w


CLOUD_GAIN = 36.0
HDRI_STRENGTH = 1.0      # tuned on stills against output/v2-test/compare.jpg (see BUILD-LOG)
HDRI_EXPOSURE = -0.6


def daylight(ctx, sun_az=-35.0, sun_elev=40.0, sky_strength=0.065, sun_energy=3.2, cloud_gain=None, aerosol=0.5,
             hdri=True, hdri_strength=None, exposure=None):
    """THE way a v2 builder lights an outdoor scene: Poly Haven HDRI sky + extracted sun if present
    (assets/polyhaven/hdri/), else the procedural physical sky + clouds + a sun lamp. Returns the sun lamp
    (procedural path) or None (HDRI path). `sun_az` = where the sun is, as a sun lamp Z rotation."""
    sc = ctx.scene
    if hdri and _find_hdri():
        sky_world(sc, sun_elev, sun_az, hdri_ok=True,
                  hdri_strength=HDRI_STRENGTH if hdri_strength is None else hdri_strength)
        sc.view_settings.exposure = HDRI_EXPOSURE if exposure is None else exposure
        return None
    sky_world(sc, sun_elev, sun_az, sky_strength, cloud_gain=cloud_gain, aerosol=aerosol, hdri_ok=False)
    if exposure is not None:
        sc.view_settings.exposure = exposure
    return sun_lamp(sun_elev, sun_az, sun_energy)


def sun_lamp(elev=38.0, az=-35.0, energy=4.0, color=(1.0, 0.95, 0.86), angle=2.5):
    d = bpy.data.lights.new("SunV2", "SUN")
    d.energy = energy
    d.color = color
    d.angle = math.radians(angle)
    try:
        d.shadow_maximum_resolution = 0.002
    except Exception:
        pass
    o = L.link(bpy.data.objects.new("SunV2", d))
    o.rotation_euler = (math.radians(90.0 - elev), 0.0, math.radians(az))
    return o


# ================================================================ materials
_MV2 = {}


def _new_mat(name):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    return m, nt, nt.nodes, nt.links, nt.nodes.get("Principled BSDF")


def _finish(m, shader_out, haze=True):
    L._fog_wrap(m, shader_out) if haze else m.node_tree.links.new(
        shader_out, m.node_tree.nodes.get("Material Output").inputs["Surface"])
    return m


def _coord(N, Lk, kind="Object", obj=None):
    tc = N.new("ShaderNodeTexCoord")
    if obj is not None:
        tc.object = obj
    return tc.outputs[kind]


def _noise_var(N, Lk, vec, scale, amount, detail=4.0):
    """Returns a Value socket ~ 1 +- amount from a noise texture."""
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    Lk.new(vec, nz.inputs["Vector"])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 1.0 - amount
    mr.inputs["To Max"].default_value = 1.0 + amount
    mr.inputs["From Min"].default_value = 0.3
    mr.inputs["From Max"].default_value = 0.7
    Lk.new(nz.outputs["Fac"], mr.inputs["Value"])
    return mr.outputs["Result"], nz


def _mul_col(N, Lk, col_sock_or_val, fac_sock):
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 1.0
    if isinstance(col_sock_or_val, tuple):
        mx.inputs["A"].default_value = col_sock_or_val
    else:
        Lk.new(col_sock_or_val, mx.inputs["A"])
    cmb = N.new("ShaderNodeCombineColor")
    for i in range(3):
        Lk.new(fac_sock, cmb.inputs[i])
    Lk.new(cmb.outputs[0], mx.inputs["B"])
    return mx.outputs["Result"]


def _bump(N, Lk, height_sock, p, strength=0.15, distance=0.05):
    b = N.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    Lk.new(height_sock, b.inputs["Height"])
    Lk.new(b.outputs["Normal"], p.inputs["Normal"])


def pbr(name, color, rough=0.55, metal=0.0, coat=0.0, var=0.06, var_scale=0.6, bump=0.0, haze=True):
    """Principled material with a little procedural colour variation (and optional bump)."""
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.05
    if var > 0 or bump > 0:
        vec = _coord(N, Lk, "Object")
        fac, nz = _noise_var(N, Lk, vec, var_scale, var)
        Lk.new(_mul_col(N, Lk, tuple(color), fac), p.inputs["Base Color"])
        if bump > 0:
            nzf = N.new("ShaderNodeTexNoise")
            nzf.inputs["Scale"].default_value = 18.0
            nzf.inputs["Detail"].default_value = 6.0
            Lk.new(vec, nzf.inputs["Vector"])
            _bump(N, Lk, nzf.outputs["Fac"], p, bump, 0.03)
    else:
        p.inputs["Base Color"].default_value = color
    _MV2[name] = _finish(m, p.outputs[0], haze)
    return _MV2[name]


def emis(name, color, strength=3.0):
    if name in _MV2:
        return _MV2[name]
    m = L.emissive(name, color, strength, 0.3)
    _MV2[name] = m
    return m


def glass_mat(name="glass_v2", color=GLASS_TINT):
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = 0.04
    p.inputs["Metallic"].default_value = 0.0
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.02
    p.inputs["Specular IOR Level"].default_value = 0.8
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def image_mat(name, fname, uv_scale=(1.0, 1.0), rough=0.85, var=0.08, bump=0.12, tint=None):
    """Material from a PIL-generated texture in TEX['dir'] (UV-mapped), with asphalt grain + bump."""
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    uv = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale[0], uv_scale[1], 1.0)
    Lk.new(uv.outputs["UV"], mp.inputs["Vector"])
    tex = N.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX["dir"], fname), check_existing=True)
    tex.interpolation = "Cubic"
    tex.extension = "REPEAT"
    Lk.new(mp.outputs["Vector"], tex.inputs["Vector"])
    col = tex.outputs["Color"]
    obj = _coord(N, Lk, "Object")
    fac, _ = _noise_var(N, Lk, obj, 0.05, var)
    col = _mul_col(N, Lk, col, fac)
    p.inputs["Roughness"].default_value = rough
    if ph_detail(N, Lk, obj, PH_ASPHALT["asset"], p, col, amount=PH_ASPHALT["amount"], hue=0.0,
                 normal=PH_ASPHALT["normal"], rough_mix=0.3):
        bump = 0.0
    else:
        Lk.new(col, p.inputs["Base Color"])
    if bump > 0:
        nzf = N.new("ShaderNodeTexNoise")
        nzf.inputs["Scale"].default_value = 60.0
        nzf.inputs["Detail"].default_value = 8.0
        Lk.new(obj, nzf.inputs["Vector"])
        _bump(N, Lk, nzf.outputs["Fac"], p, bump, 0.02)
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def ground_mat():
    """Patchwork farmland / lawns: Voronoi cells pick a palette colour, noise adds grass variation."""
    name = "ground_v2"
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    obj = _coord(N, Lk, "Object")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 1.0 / 210.0
    vor.inputs["Randomness"].default_value = 0.85
    Lk.new(obj, vor.inputs["Vector"])
    sepc = N.new("ShaderNodeSeparateColor")
    Lk.new(vor.outputs["Color"], sepc.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    pal = ["62804a", "74904f", "56723f", "8d9a5c", "a8997a", "667d48", "839058", "9c8b6a", "5d7a45"]
    els = ramp.color_ramp.elements
    els[0].color = hexc(pal[0])
    els[1].position = 1.0
    els[1].color = hexc(pal[-1])
    for i, c in enumerate(pal[1:-1]):
        e = els.new((i + 1) / float(len(pal) - 1))
        e.color = hexc(c)
    Lk.new(sepc.outputs[0], ramp.inputs[0])
    fac, _ = _noise_var(N, Lk, obj, 0.02, 0.16, 5.0)
    col = _mul_col(N, Lk, ramp.outputs["Color"], fac)
    fac2, _ = _noise_var(N, Lk, obj, 0.4, 0.08, 6.0)
    col = _mul_col(N, Lk, col, fac2)
    p.inputs["Roughness"].default_value = 0.95
    if not ph_detail(N, Lk, obj, "aerial_grass_rock", p, col, amount=0.55, hue=0.12, normal=0.5, rough_mix=0.2,
                     scale_mul=2.0):
        Lk.new(col, p.inputs["Base Color"])
        nzf = N.new("ShaderNodeTexNoise")
        nzf.inputs["Scale"].default_value = 3.0
        nzf.inputs["Detail"].default_value = 8.0
        Lk.new(obj, nzf.inputs["Vector"])
        _bump(N, Lk, nzf.outputs["Fac"], p, 0.25, 0.1)
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def lawn_mat(name="lawn_v2", color=hexc("6e8a4c"), stripes=True):
    """Mowed airfield grass: subtle mowing stripes along Y + noise."""
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    obj = _coord(N, Lk, "Object")
    fac, _ = _noise_var(N, Lk, obj, 0.03, 0.12, 5.0)
    col = _mul_col(N, Lk, tuple(color), fac)
    if stripes:
        wv = N.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = "X"
        wv.inputs["Scale"].default_value = 0.012
        wv.inputs["Distortion"].default_value = 0.0
        Lk.new(obj, wv.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 0.93
        mr.inputs["To Max"].default_value = 1.05
        Lk.new(wv.outputs["Fac"], mr.inputs["Value"])
        col = _mul_col(N, Lk, col, mr.outputs["Result"])
    fac2, _ = _noise_var(N, Lk, obj, 0.7, 0.07, 6.0)
    col = _mul_col(N, Lk, col, fac2)
    p.inputs["Roughness"].default_value = 0.92
    if not ph_detail(N, Lk, obj, "aerial_grass_rock", p, col, amount=0.45, hue=0.08, normal=0.4, rough_mix=0.2):
        Lk.new(col, p.inputs["Base Color"])
        nzf = N.new("ShaderNodeTexNoise")
        nzf.inputs["Scale"].default_value = 6.0
        Lk.new(obj, nzf.inputs["Vector"])
        _bump(N, Lk, nzf.outputs["Fac"], p, 0.2, 0.05)
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def facade_mat(name, wall, glass=hexc("2c3d52"), bay=3.2, floor=3.6, win_frac=0.55, lit=0.0):
    """Building walls with a window grid (Brick texture in object space: bricks = windows, mortar = wall)."""
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    Lk.new(sep.outputs["X"], add.inputs[0])
    Lk.new(sep.outputs["Y"], add.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ")
    Lk.new(add.outputs[0], cmb.inputs[0])
    Lk.new(sep.outputs["Z"], cmb.inputs[1])
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = bay
    br.inputs["Row Height"].default_value = floor
    br.inputs["Mortar Size"].default_value = bay * (1 - win_frac) / 2.0
    br.inputs["Mortar Smooth"].default_value = 0.02
    br.inputs["Color1"].default_value = glass
    br.inputs["Color2"].default_value = tuple(c * 0.8 for c in glass[:3]) + (1,)
    br.inputs["Mortar"].default_value = wall
    Lk.new(cmb.outputs[0], br.inputs["Vector"])
    Lk.new(br.outputs["Color"], p.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.08
    rr.inputs["To Max"].default_value = 0.75
    Lk.new(br.outputs["Fac"], rr.inputs["Value"])
    Lk.new(rr.outputs["Result"], p.inputs["Roughness"])
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def corrugated_mat(name, color, spacing=0.25, rough=0.45, metal=0.5):
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    obj = _coord(N, Lk, "Object")
    fac, _ = _noise_var(N, Lk, obj, 0.15, 0.06)
    Lk.new(_mul_col(N, Lk, tuple(color), fac), p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    wv = N.new("ShaderNodeTexWave")
    wv.wave_profile = "SIN"
    wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 1.0 / spacing / 6.28
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(obj, sep.inputs[0])
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    Lk.new(sep.outputs["X"], add.inputs[0])
    Lk.new(sep.outputs["Y"], add.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ")
    Lk.new(add.outputs[0], cmb.inputs[0])
    Lk.new(cmb.outputs[0], wv.inputs["Vector"])
    _bump(N, Lk, wv.outputs["Fac"], p, 0.25, 0.03)
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def livery_mat(root):
    """Aircraft paint in the aircraft's own space (TexCoord.object = root): white base, navy cheat line
    sweeping up to the tail, red pinstripe, navy fin with a red band, red wingtips, panel lines."""
    name = "livery_v2_" + root.name
    m, nt, N, Lk, p = _new_mat(name)
    tc = N.new("ShaderNodeTexCoord")
    tc.object = root
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    X, Y, Z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def M(op, a, b=None, v=None, clamp=False):
        n = N.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            Lk.new(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)):
                n.inputs[1].default_value = b
            else:
                Lk.new(b, n.inputs[1])
        return n.outputs[0]

    def band(val, lo, hi):
        a = M("GREATER_THAN", val, lo)
        b = M("LESS_THAN", val, hi)
        return M("MULTIPLY", a, b)
    ax = M("ABSOLUTE", X)
    fus = M("LESS_THAN", ax, 0.78)                      # fuselage only (not wings)
    # cheat line: centre z = -0.02 - 0.075*y (rises towards the tail)
    zc = M("SUBTRACT", Z, M("ADD", M("MULTIPLY", Y, -0.075), -0.02))
    navy = M("MULTIPLY", band(zc, -0.11, 0.07), fus)
    navy = M("MULTIPLY", navy, band(Y, -3.75, 2.75))
    red = M("MULTIPLY", band(zc, 0.10, 0.145), fus)
    red = M("MULTIPLY", red, band(Y, -3.6, 2.6))
    # fin: navy above z 0.95 behind y -2.5, red band at z 1.45..1.6
    fin = M("MULTIPLY", M("GREATER_THAN", Z, 0.95), M("LESS_THAN", Y, -2.4))
    fin = M("MULTIPLY", fin, M("LESS_THAN", ax, 0.2))
    fin_red = M("MULTIPLY", fin, band(Z, 1.42, 1.58))
    navy = M("MAXIMUM", navy, M("SUBTRACT", fin, fin_red, clamp=True))
    red = M("MAXIMUM", red, fin_red)
    # wing tips
    red = M("MAXIMUM", red, M("GREATER_THAN", ax, 5.25))
    col = N.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.inputs["A"].default_value = WHITE_PAINT
    col.inputs["B"].default_value = NAVY_PAINT
    Lk.new(navy, col.inputs["Factor"])
    col2 = N.new("ShaderNodeMix")
    col2.data_type = "RGBA"
    Lk.new(col.outputs["Result"], col2.inputs["A"])
    col2.inputs["B"].default_value = RED_PAINT
    Lk.new(red, col2.inputs["Factor"])
    # panel lines: thin dark seams every 1.05 m along the fuselage and every 1.4 m along the wings
    fy = M("FRACT", M("MULTIPLY", Y, 1.0 / 1.05))
    seam_y = M("MULTIPLY", M("LESS_THAN", fy, 0.012), fus)
    fx = M("FRACT", M("MULTIPLY", ax, 1.0 / 1.4))
    seam_x = M("MULTIPLY", M("LESS_THAN", fx, 0.01), M("GREATER_THAN", ax, 0.9))
    seam = M("MAXIMUM", seam_y, seam_x)
    shade = M("SUBTRACT", 1.0, M("MULTIPLY", seam, 0.35))
    final = _mul_col(N, Lk, col2.outputs["Result"], shade)
    Lk.new(final, p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.28
    p.inputs["Coat Weight"].default_value = 0.6
    p.inputs["Coat Roughness"].default_value = 0.08
    inv = M("SUBTRACT", 1.0, seam)
    _bump(N, Lk, inv, p, 0.4, 0.004)
    return _finish(m, p.outputs[0])


# ================================================================ mesh helpers
def mesh_from_bm(name, bm, mats, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    if smooth:
        for pl in me.polygons:
            pl.use_smooth = True
    return me


def obj(name, me, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), parent=None):
    o = L.link(bpy.data.objects.new(name, me))
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale
    if parent is not None:
        o.parent = parent
    return o


def bm_box(bm, center, size, mat_index=0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    verts = r["verts"]
    bmesh.ops.scale(bm, vec=size, verts=verts)
    bmesh.ops.translate(bm, vec=center, verts=verts)
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mat_index
    return verts


def bm_prism_x(bm, x0, x1, pts_yz, mat_index=0):
    """Extrude a YZ polygon from x0 to x1 (gable roofs etc.)."""
    a = [bm.verts.new((x0, y, z)) for y, z in pts_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in pts_yz]
    fs = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
    n = len(pts_yz)
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    for f in fs:
        f.material_index = mat_index
    bmesh.ops.recalc_face_normals(bm, faces=fs)


def plane_obj(name, sx, sy, loc, mat, rot_z=0.0):
    bm = bmesh.new()
    v = [bm.verts.new((x * sx / 2, y * sy / 2, 0)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = bm.faces.new(v)
    uv = bm.loops.layers.uv.new("UVMap")
    for lp, (u, w) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uv].uv = (u, w)
    me = mesh_from_bm(name, bm, [mat])
    return obj(name, me, loc, (0, 0, rot_z))


# ================================================================ aircraft (v2)
def _catmull(pts, t):
    """pts: list of (y, values...) sorted by y; returns interpolated values at y=t (Catmull-Rom)."""
    ys = [p[0] for p in pts]
    i = max(0, min(len(pts) - 2, max(k for k in range(len(ys)) if ys[k] <= t) if t >= ys[0] else 0))
    p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
    u = (t - p1[0]) / max(1e-6, (p2[0] - p1[0]))
    out = []
    for k in range(1, len(p1)):
        a, b, c, d = p0[k], p1[k], p2[k], p3[k]
        out.append(0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3))
    return out


FUSE = [  # y, half-width, z_top, z_bottom  (Cirrus-like proportions, generic)
    (-3.95, 0.05, 0.56, 0.42), (-3.4, 0.13, 0.58, 0.25), (-2.5, 0.29, 0.62, -0.04), (-1.3, 0.47, 0.66, -0.34),
    (-0.2, 0.59, 0.70, -0.50), (0.9, 0.63, 0.72, -0.55), (1.9, 0.61, 0.64, -0.55), (2.7, 0.55, 0.47, -0.50),
    (3.3, 0.47, 0.33, -0.43), (3.75, 0.37, 0.20, -0.32), (3.98, 0.30, 0.13, -0.24)]


def _loft_fuselage(bm, n=24, step=0.12, mat_index=0):
    ys = []
    y = FUSE[0][0]
    while y < FUSE[-1][0]:
        ys.append(y)
        y += step
    ys.append(FUSE[-1][0])
    rings = []
    ex = 2.0 / 2.5
    for y in ys:
        w, zt, zb = _catmull(FUSE, y)
        ring = []
        for k in range(n):
            th = 2 * math.pi * k / n
            c, s = math.cos(th), math.sin(th)
            x = w * math.copysign(abs(c) ** ex, c)
            sz = math.copysign(abs(s) ** ex, s)
            z = zb + (zt - zb) * (0.5 + 0.5 * sz)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            faces.append(bm.faces.new((a[k], a[j], b[j], b[k])))
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        cy = ring[0].co.y
        cz = sum(v.co.z for v in ring) / n
        c = bm.verts.new((0, cy, cz))
        for k in range(n):
            j = (k + 1) % n
            f = (ring[k], ring[j], c) if not rev else (ring[j], ring[k], c)
            faces.append(bm.faces.new(f))
    for f in faces:
        f.material_index = mat_index
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def _naca(t, n=10):
    xs = [0.5 - 0.5 * math.cos(math.pi * i / n) for i in range(n + 1)]
    yt = [5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4) for x in xs]
    up = [(x, z) for x, z in zip(xs, yt)]
    lo = [(x, -z) for x, z in zip(xs, yt)][::-1][1:-1]
    return up + lo        # closed loop: LE -> TE on top, back along the bottom


def _wing(bm, root_x, tip_x, root_chord, tip_chord, le_root_y, sweep, z0, dihedral, t_root, t_tip,
          side=1, vertical=False, mat_index=0, n_span=6):
    """Tapered wing (or fin if vertical). Chord along -Y from the leading edge."""
    rings = []
    for i in range(n_span + 1):
        f = i / float(n_span)
        s = root_x + (tip_x - root_x) * f
        chord = root_chord + (tip_chord - root_chord) * f
        th = t_root + (t_tip - t_root) * f
        le = le_root_y - sweep * f
        ring = []
        for (cx, cz) in _naca(th):
            yy = le - cx * chord
            zz = cz * chord
            if vertical:
                ring.append(bm.verts.new((zz, yy, z0 + s)))
            else:
                ring.append(bm.verts.new((side * s, yy, z0 + zz + math.tan(math.radians(dihedral)) * (s - root_x))))
        rings.append(ring)
    faces = []
    m = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(m):
            j = (k + 1) % m
            faces.append(bm.faces.new((a[k], a[j], b[j], b[k])))
    for ring in (rings[0], rings[-1]):
        faces.append(bm.faces.new(ring))
    for f in faces:
        f.material_index = mat_index
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def _ellipsoid(bm, c, r, mat_index=0, seg=16, rings=10):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    vs = res["verts"]
    bmesh.ops.scale(bm, vec=r, verts=vs)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat_index


def make_plane_v2(ctx, name, spin=True, strobes=True, gear=True):
    """Generic low-wing four-seat single (Cirrus-like silhouette). Nose +Y, origin ~ at the wing root,
    ~8 m long, ~11.7 m span. Returns the root empty. All geometry is built in root space so the livery
    shader can use the root's coordinates."""
    root = L.link(bpy.data.objects.new(name, None))
    liv = livery_mat(root)
    glass = glass_mat()
    dark = pbr("tyre_v2", hexc("1c1d20"), 0.8, var=0)
    metal = pbr("strut_v2", hexc("c9ced4"), 0.3, 0.6, var=0)
    red = pbr("spinner_v2", RED_PAINT, 0.25, coat=0.6, var=0)
    bm = bmesh.new()
    _loft_fuselage(bm, mat_index=0)
    # wings: low wing, slight dihedral, tapered
    for side in (-1, 1):
        _wing(bm, 0.45, 5.85, 1.62, 0.86, 1.35, 0.25, -0.36, 4.5, 0.15, 0.11, side, mat_index=0)
        _wing(bm, 0.05, 2.0, 0.92, 0.6, -2.95, 0.3, 0.36, 2.0, 0.11, 0.09, side, mat_index=0)  # stabiliser
    _wing(bm, 0.25, 1.75, 1.35, 0.72, -2.55, 0.95, 0.0, 0.0, 0.11, 0.09, vertical=True, mat_index=0)  # fin
    if gear:
        for sx in (-1, 1):
            _ellipsoid(bm, (sx * 1.55, 0.55, -1.05), (0.2, 0.52, 0.27), 0)           # wheel pant
        _ellipsoid(bm, (0, 2.95, -1.0), (0.16, 0.42, 0.24), 0)
    me = mesh_from_bm(name + "_body", bm, [liv], smooth=True)
    body = obj(name + "_body", me, parent=root)
    sub = body.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    # canopy (glass) + gear struts / wheels
    bm = bmesh.new()
    _ellipsoid(bm, (0, 0.85, 0.55), (0.53, 1.55, 0.36), 0, 24, 14)
    obj(name + "_canopy", mesh_from_bm(name + "_canopy", bm, [glass], smooth=True), parent=root)
    if gear:
        bm = bmesh.new()
        for (x, y, z) in ((-1.55, 0.55, -1.12), (1.55, 0.55, -1.12), (0, 2.95, -1.08)):
            r = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.25, radius2=0.25, depth=0.13)
            bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, vec=(x, y, z), verts=r["verts"])
        obj(name + "_wheels", mesh_from_bm(name + "_wheels", bm, [dark], smooth=True), parent=root)
        bm = bmesh.new()
        for sx in (-1, 1):
            vs = bm_box(bm, (sx * 1.15, 0.55, -0.72), (0.9, 0.09, 0.05))
            bmesh.ops.rotate(bm, verts=vs, cent=(sx * 1.15, 0.55, -0.72), matrix=Matrix.Rotation(sx * math.radians(-28), 3, "Y"))
        bm_box(bm, (0, 2.95, -0.7), (0.07, 0.07, 0.62))
        obj(name + "_struts", mesh_from_bm(name + "_struts", bm, [metal]), parent=root)
    # spinner + prop
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.3, radius2=0.02, depth=0.55)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=(0, 4.2, -0.05), verts=r["verts"])
    obj(name + "_spinner", mesh_from_bm(name + "_spinner", bm, [red], smooth=True), parent=root)
    prop = L.link(bpy.data.objects.new(name + "_prop", None))
    prop.parent = root
    prop.location = (0, 4.12, -0.05)
    bm = bmesh.new()
    for k in range(3):
        vs = bm_box(bm, (0, 0, 0.52), (0.17, 0.035, 0.95))
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(22), 3, "Z"))
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(120 * k), 3, "Y"))
    obj(name + "_blades", mesh_from_bm(name + "_blades", bm, [pbr("blade_v2", hexc("23262b"), 0.5, var=0)]), parent=prop)
    disc_m = L.flat_mat("prop_disc_v2", hexc("d9dee5"), alpha=0.10)
    bm = bmesh.new()
    r = bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=1.0)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    disc = obj(name + "_disc", mesh_from_bm(name + "_disc", bm, [disc_m]), (0, 4.14, -0.05), parent=root)
    disc.visible_shadow = False
    if spin:
        kf(prop, "rotation_euler", 1, Vector((0, 0, 0)), "LINEAR")
        kf(prop, "rotation_euler", ctx.frames + 1, Vector((0, ctx.frames * 0.45, 0)), "LINEAR")
    # nav lights (+ white strobes) and a landing light in the left wing
    for sx, col in ((-1, hexc("ff2a2a")), (1, hexc("2aff6a"))):
        bm = bmesh.new()
        _ellipsoid(bm, (sx * 5.86, 1.0, -0.36 + math.tan(math.radians(4.5)) * 5.4), (0.07, 0.12, 0.06), 0, 8, 6)
        obj(name + "_nav%d" % sx, mesh_from_bm(name + "_nav", bm, [emis("nav_v2_%d" % sx, col, 6.0)]), parent=root)
    if strobes:
        st = L.emissive("strobe_v2_" + name, hexc("ffffff"), 0.0, 0.3)
        sock = st.node_tree.nodes.get("Emission").inputs["Strength"]
        f = 8
        while f < ctx.frames:
            L.kf_socket(sock, f - 1, 0.0, "CONSTANT")
            L.kf_socket(sock, f, 40.0, "CONSTANT")
            L.kf_socket(sock, f + 2, 0.0, "CONSTANT")
            f += 36
        for sx in (-1, 1):
            bm = bmesh.new()
            _ellipsoid(bm, (sx * 5.88, 0.6, -0.36 + math.tan(math.radians(4.5)) * 5.4), (0.05, 0.08, 0.05), 0, 8, 6)
            obj(name + "_strb%d" % sx, mesh_from_bm(name + "_strb", bm, [st]), parent=root)
    bm = bmesh.new()
    _ellipsoid(bm, (-2.4, 1.42, -0.27), (0.13, 0.05, 0.06), 0, 8, 6)
    obj(name + "_ldg", mesh_from_bm(name + "_ldg", bm, [emis("landing_light_v2", hexc("fff6e0"), 25.0)]), parent=root)
    return root


# ================================================================ world building
def _template(name, build, mats, smooth=False):
    bm = bmesh.new()
    build(bm)
    return mesh_from_bm(name, bm, mats, smooth)


def house_templates(rng, n=14):
    """Single-storey and two-storey houses with gable / hip-ish roofs (orange, brown, grey)."""
    out = []
    for i in range(n):
        w = rng.uniform(9, 14)
        d = rng.uniform(8, 11)
        h = rng.choice((3.2, 3.4, 5.8, 6.2))
        pitch = rng.uniform(0.35, 0.55)
        wall = pbr("wall_v2_%d" % i, WALL_COLS[i % len(WALL_COLS)], 0.8, var=0.05, var_scale=0.3)
        roof = pbr("roof_v2_%d" % (i % len(ROOF_COLS)), ROOF_COLS[i % len(ROOF_COLS)], 0.75, var=0.1, var_scale=0.8, bump=0.08)
        win = pbr("housewin_v2", hexc("2e3c4c"), 0.1, var=0)
        rh = d / 2 * pitch

        def build(bm, w=w, d=d, h=h, rh=rh):
            bm_box(bm, (0, 0, h / 2), (w, d, h), 0)
            ov = 0.5
            bm_prism_x(bm, -w / 2 - ov, w / 2 + ov, [(-d / 2 - ov, h - 0.15), (d / 2 + ov, h - 0.15), (0, h + rh)], 1)
            # windows: thin dark boxes protruding 6 cm from the front/back walls
            for sy in (-1, 1):
                for k in range(-1, 2):
                    bm_box(bm, (k * w / 3.2, sy * (d / 2 + 0.03), h * 0.5 if h < 4 else 1.6), (1.4, 0.06, 1.1), 2)
                    if h > 4:
                        bm_box(bm, (k * w / 3.2, sy * (d / 2 + 0.03), 4.4), (1.3, 0.06, 1.0), 2)
        out.append(_template("house_t%d" % i, build, [wall, roof, win]))
    return out


def tree_templates(rng):
    trunk = pbr("trunk_v2", hexc("5a4632"), 0.9, var=0.1)
    out = []
    for i in range(6):
        leaf = pbr("leaf_v2_%d" % i, LEAF_COLS[i], 0.85, var=0.15, var_scale=0.9, bump=0.1)

        def build(bm, i=i):
            bm_box(bm, (0, 0, 1.6), (0.45, 0.45, 3.2), 0)
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            r2 = random.Random(100 + i)
            for v in res["verts"]:
                v.co *= 1.0 + r2.uniform(-0.12, 0.12)
            bmesh.ops.scale(bm, vec=(3.2, 3.2, 3.0), verts=res["verts"])
            bmesh.ops.translate(bm, vec=(0, 0, 5.6), verts=res["verts"])
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 1
            if i % 2 == 0:  # second lobe
                res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
                bmesh.ops.scale(bm, vec=(2.2, 2.2, 2.0), verts=res["verts"])
                bmesh.ops.translate(bm, vec=(1.4, 0.6, 7.3), verts=res["verts"])
                for f in {f for v in res["verts"] for f in v.link_faces}:
                    f.material_index = 1
        out.append(_template("tree_t%d" % i, build, [trunk, leaf]))
    leafc = pbr("conifer_v2", hexc("355a3a"), 0.85, var=0.12, bump=0.1)

    def build_c(bm):
        bm_box(bm, (0, 0, 1.0), (0.4, 0.4, 2.0), 0)
        for k, (r, zc, dz) in enumerate(((2.8, 4.5, 5.0), (2.1, 7.2, 4.2), (1.3, 9.6, 3.2))):
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r, radius2=0.0, depth=dz)
            bmesh.ops.translate(bm, vec=(0, 0, zc), verts=res["verts"])
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 1
    out.append(_template("conifer_t", build_c, [trunk, leafc]))
    return out


def scatter(templates, pts, rng, scale=(0.75, 1.35), prefix="inst"):
    objs = []
    for i, (x, y) in enumerate(pts):
        me = templates[rng.randrange(len(templates))]
        s = rng.uniform(*scale)
        objs.append(obj("%s%d" % (prefix, i), me, (x, y, 0.0), (0, 0, rng.uniform(0, 6.283)), (s, s, s)))
    return objs


# ---------------------------------------------------------------- airport layout (runway along +Y, x = 0)
RWY_LEN, RWY_W = 1600.0, 45.0
TWY_X = 115.0
APRON = (130.0, 265.0, 330.0, 760.0)      # x0, x1, y0, y1
AIRFIELD = (-170.0, 330.0, -330.0, 1850.0)  # lawn area (inside the fence)


def in_airfield(x, y, pad=0.0):
    x0, x1, y0, y1 = AIRFIELD
    return x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad


def build_airport(ctx, rng):
    z_lawn, z_rwy, z_twy, z_apr = 0.12, 0.3, 0.26, 0.28
    x0, x1, y0, y1 = AIRFIELD
    plane_obj("airfield", x1 - x0, y1 - y0, ((x0 + x1) / 2, (y0 + y1) / 2, z_lawn), lawn_mat())
    # runway: end A (0..400 m, "34"), middle tiles (60 m each), end B (rotated, "16")
    end_m = image_mat("rwy_end_v2", "runway_end.png")
    mid_m = image_mat("rwy_mid_v2", "runway_mid.png", (1.0, 1.0))
    endb_m = image_mat("rwy_endb_v2", "runway_end_b.png")
    plane_obj("rwy_a", RWY_W, 400, (0, 200, z_rwy), end_m)
    n_mid = 13
    tl = (RWY_LEN - 800) / n_mid           # ~61.5 m per tile (one 30 m centre-line dash + gap)
    for k in range(n_mid):
        plane_obj("rwy_m%d" % k, RWY_W, tl, (0, 400 + tl / 2 + tl * k, z_rwy), mid_m)
    plane_obj("rwy_b", RWY_W, 400, (0, RWY_LEN - 200, z_rwy), endb_m, rot_z=math.pi)
    # shoulders / blast pad (paved, darker), slightly lower so the runway edge never fights it
    plane_obj("blastpad", RWY_W, 60, (0, -30, z_rwy - 0.02), image_mat("blast_v2", "blastpad.png"))
    # taxiway + connectors (texture with yellow centre line, tiled)
    twy_m = image_mat("twy_v2", "taxiway.png", (1.0, (RWY_LEN + 40) / 40.0))
    plane_obj("twy", 18, RWY_LEN + 40, (TWY_X, RWY_LEN / 2, z_twy), twy_m)
    conn_m = image_mat("conn_v2", "taxiway.png", (1.0, 3.0))
    for y in (25, 520, 1050, RWY_LEN - 25):
        plane_obj("conn%d" % y, 18, TWY_X - 9 - RWY_W / 2 + 0.0, ((TWY_X - 9 + RWY_W / 2) / 2, y, z_twy - 0.01), conn_m,
                  rot_z=math.pi / 2)
    # apron (concrete slabs via brick joints)
    ax0, ax1, ay0, ay1 = APRON
    apr = concrete_mat()
    plane_obj("apron", ax1 - ax0, ay1 - ay0, ((ax0 + ax1) / 2, (ay0 + ay1) / 2, z_apr), apr)
    plane_obj("apron_link", ax0 - (TWY_X + 9) + 1.0, ay1 - ay0, ((ax0 + TWY_X + 9) / 2, (ay0 + ay1) / 2, z_twy - 0.015), apr)
    # terminal (glass facade towards the apron), tower, hangars
    term_wall = facade_mat("terminal_v2", hexc("e3e0d8"), hexc("3d5a73"), 3.0, 4.2, 0.7)
    roof_grey = pbr("roof_flat_v2", hexc("8c8f93"), 0.8, var=0.08, bump=0.05)
    bm = bmesh.new()
    bm_box(bm, (290, 545, 5.5), (34, 150, 11), 0)
    bm_box(bm, (290, 545, 11.4), (36, 152, 0.8), 1)
    bm_box(bm, (280, 545, 14.5), (10, 40, 6), 0)
    bm_box(bm, (280, 545, 17.7), (11, 41, 0.6), 1)
    obj("terminal", mesh_from_bm("terminal", bm, [term_wall, roof_grey]))
    tower_m = pbr("tower_v2", hexc("e9e6df"), 0.6, var=0.04)
    bm = bmesh.new()
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=4.0, radius2=3.2, depth=28)
    bmesh.ops.translate(bm, vec=(250, 790, 14), verts=r["verts"])
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=5.2, radius2=6.6, depth=5.0)
    bmesh.ops.translate(bm, vec=(250, 790, 30.5), verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 1
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=7.4, radius2=4.0, depth=1.6)
    bmesh.ops.translate(bm, vec=(250, 790, 33.8), verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 2
    obj("tower", mesh_from_bm("tower", bm, [tower_m, glass_mat("towerglass_v2", hexc("2a4a5e")), roof_grey]))
    roofs = [pbr("hroof_v2_%d" % i, c, 0.5, 0.3, var=0.06, bump=0.05) for i, c in
             enumerate((hexc("b4442f"), hexc("e8e8e4"), hexc("c66a33"), hexc("6f7c88"), hexc("b4442f")))]
    walls = [corrugated_mat("hwall_v2_%d" % i, c) for i, c in
             enumerate((hexc("d9dcdf"), hexc("b9c3cc"), hexc("e4ded2")))]
    door = corrugated_mat("hdoor_v2", hexc("8e98a3"), 0.5, 0.5, 0.6)
    for k, yc in enumerate((860, 935, 1010, 1085, 1160, 1240)):
        w, dpt, h = 58 if k % 3 else 46, 48, 12 if k % 2 else 10
        bm = bmesh.new()
        bm_box(bm, (0, 0, h / 2), (dpt, w, h), 0)
        # gable roof along Y (ridge along X = depth)
        a = [bm.verts.new((-dpt / 2 - 0.6, yy, zz)) for yy, zz in ((-w / 2 - 0.6, h - 0.1), (w / 2 + 0.6, h - 0.1), (0, h + w * 0.12))]
        b = [bm.verts.new((dpt / 2 + 0.6, yy, zz)) for yy, zz in ((-w / 2 - 0.6, h - 0.1), (w / 2 + 0.6, h - 0.1), (0, h + w * 0.12))]
        fs = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
        for i in range(3):
            j = (i + 1) % 3
            fs.append(bm.faces.new((a[i], a[j], b[j], b[i])))
        for f in fs:
            f.material_index = 1
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        bm_box(bm, (-dpt / 2 - 0.08, 0, h * 0.42), (0.16, w * 0.8, h * 0.84), 2)
        obj("hangar%d" % k, mesh_from_bm("hangar%d" % k, bm, [walls[k % 3], roofs[k % len(roofs)], door]), (172, yc, 0.28))
    # T-hangar rows (long low sheds)
    for k, yc in enumerate((1360, 1420, 1480)):
        bm = bmesh.new()
        bm_box(bm, (0, 0, 2.6), (14, 130, 5.2), 0)
        bm_box(bm, (0, 0, 5.4), (15, 131, 0.4), 1)
        obj("thangar%d" % k, mesh_from_bm("thangar%d" % k, bm, [walls[(k + 1) % 3], roofs[(k + 2) % len(roofs)]]),
            (190, yc, 0.28), (0, 0, math.pi / 2))
    # windsock + PAPI + approach light bars + small edge fixtures
    pole = pbr("pole_v2", hexc("d8dadd"), 0.4, 0.5, var=0)
    orange = pbr("sock_v2", hexc("ff6a1a"), 0.6, var=0)
    bm = bmesh.new()
    bm_box(bm, (-60, 260, 4), (0.15, 0.15, 8), 0)
    r = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.45, radius2=0.25, depth=3.2)
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    bmesh.ops.translate(bm, vec=(-58.3, 260, 7.7), verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 1
    obj("windsock", mesh_from_bm("windsock", bm, [pole, orange]))
    pw = emis("papi_w_v2", hexc("fff4e0"), 6.0)
    pr = emis("papi_r_v2", hexc("ff3030"), 6.0)
    for k in range(4):
        L.box("papi%d" % k, (1.6, 1.0, 0.9), (-RWY_W / 2 - 15 - k * 9, 300, 0.75), pw if k < 2 else pr)
    fixture = pbr("fixture_v2", hexc("f1f1ec"), 0.4, var=0)
    bm = bmesh.new()
    for y in range(0, int(RWY_LEN) + 1, 60):
        for sx in (-1, 1):
            bm_box(bm, (sx * (RWY_W / 2 + 1.5), y, 0.55), (0.35, 0.35, 0.5))
    for k in range(1, 10):
        for xx in (-6, -3, 0, 3, 6):
            bm_box(bm, (xx, -30 * k - 30, 0.25 + 0.35 * k), (0.9, 0.5, 0.35))
        bm_box(bm, (0, -30 * k - 30, 0.12 + 0.17 * k), (0.25, 0.25, 0.35 * k), 1)
        bm_box(bm, (0, -30 * k - 30, 0.25 + 0.35 * k - 0.25), (13, 0.18, 0.12), 1)
    obj("rwy_fixtures", mesh_from_bm("rwy_fixtures", bm, [fixture, pole]))
    approach_lights = emis("appr_v2", hexc("fff6dc"), 5.0)
    bm = bmesh.new()
    for k in range(1, 10):
        for xx in (-6, -3, 0, 3, 6):
            bm_box(bm, (xx, -30 * k - 30 + 0.26, 0.25 + 0.35 * k), (0.5, 0.05, 0.25))
    obj("appr_lights", mesh_from_bm("appr_lights", bm, [approach_lights]))
    build_fence()
    # parked aircraft on the apron (static, props still)
    for k, (x, y, rz) in enumerate(((165, 400, -0.6), (165, 440, -0.6), (165, 480, -0.6), (205, 640, 0.9),
                                     (205, 690, 0.9), (160, 700, -2.3))):
        pl = make_plane_v2(ctx, "parked%d" % k, spin=False, strobes=False)
        pl.location = (x, y, 1.55 + 0.28)
        pl.rotation_euler = (math.radians(-4), 0, rz)
    # parking lot with Kenney cars
    lot_m = image_mat("lot_v2", "parking.png", (1.0, 1.0))
    plane_obj("lot", 60, 150, (345, 545, 0.2), lot_m)
    cars = []
    k = 0
    for col_x in (327.5, 362.5):
        for side in (-1, 1):
            for row in range(26):
                if rng.random() < 0.28:
                    continue
                y = 475 + row * 5.5
                c = L.make_car("pcar%d" % k, loc=(col_x + side * 2.9, y, 0.2), rot_z=math.pi / 2 * side,
                               headlights=False, glow=False)
                cars.append(c)
                k += 1
    _repaint_kenney()
    return cars


def concrete_mat():
    name = "concrete_v2"
    if name in _MV2:
        return _MV2[name]
    m, nt, N, Lk, p = _new_mat(name)
    obj_v = _coord(N, Lk, "Object")
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 7.5
    br.inputs["Row Height"].default_value = 7.5
    br.inputs["Mortar Size"].default_value = 0.08
    br.inputs["Color1"].default_value = hexc("b3b1ab")
    br.inputs["Color2"].default_value = hexc("a8a59e")
    br.inputs["Mortar"].default_value = hexc("6f6d69")
    br.inputs["Bias"].default_value = 0.0
    Lk.new(obj_v, br.inputs["Vector"])
    fac, _ = _noise_var(N, Lk, obj_v, 0.15, 0.08, 6.0)
    cc = _mul_col(N, Lk, br.outputs["Color"], fac)
    p.inputs["Roughness"].default_value = 0.8
    if not ph_detail(N, Lk, obj_v, "concrete_floor_02", p, cc, amount=0.5, hue=0.1, normal=0.35, rough_mix=0.3,
                     scale_mul=2.0):
        Lk.new(cc, p.inputs["Base Color"])
        nzf = N.new("ShaderNodeTexNoise")
        nzf.inputs["Scale"].default_value = 40.0
        Lk.new(obj_v, nzf.inputs["Vector"])
        _bump(N, Lk, nzf.outputs["Fac"], p, 0.08, 0.02)
    _MV2[name] = _finish(m, p.outputs[0])
    return _MV2[name]


def _repaint_kenney():
    """v1 desaturates Kenney paint for its navy fog look; daylight wants the real colours."""
    m = bpy.data.materials.get("kenney_paint")
    if m is None:
        return
    for n in m.node_tree.nodes:
        if n.type == "HUE_SAT":
            n.inputs["Saturation"].default_value = 1.0
            n.inputs["Value"].default_value = 1.0


def build_fence():
    """Airport perimeter fence: posts every 3 m + two rails + a chain-link band (one mesh, one material
    for the wire with alpha). The fence follows the AIRFIELD rectangle (south side is under the approach)."""
    x0, x1, y0, y1 = AIRFIELD
    post = pbr("fencepost_v2", hexc("9aa0a6"), 0.4, 0.7, var=0)
    bm = bmesh.new()
    segs = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x0, y0), (x0, y1))]
    for (ax, ay), (bx, by) in segs:
        ln = math.hypot(bx - ax, by - ay)
        n = int(ln / 3.0)
        for i in range(n + 1):
            t = i / float(n)
            bm_box(bm, (ax + (bx - ax) * t, ay + (by - ay) * t, 1.1), (0.08, 0.08, 2.2))
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        horiz = abs(by - ay) < 1
        for z in (2.15, 0.15):
            bm_box(bm, (cx, cy, z), (ln, 0.05, 0.05) if horiz else (0.05, ln, 0.05))
    obj("fence_posts", mesh_from_bm("fence_posts", bm, [post]))
    # chain-link: a vertical band with a diamond wire pattern as alpha (dithered, no sorting issues)
    m, nt, N, Lk, p = _new_mat("chainlink_v2")
    m.surface_render_method = "DITHERED"
    vec = _coord(N, Lk, "Object")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(vec, sep.inputs[0])
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    Lk.new(sep.outputs["X"], add.inputs[0])
    Lk.new(sep.outputs["Y"], add.inputs[1])
    cmb = N.new("ShaderNodeCombineXYZ")
    Lk.new(add.outputs[0], cmb.inputs[0])
    Lk.new(sep.outputs["Z"], cmb.inputs[1])
    p.inputs["Base Color"].default_value = hexc("aab0b5")
    p.inputs["Metallic"].default_value = 0.6
    p.inputs["Roughness"].default_value = 0.4
    p.inputs["Alpha"].default_value = 0.35
    L._fog_wrap(m, p.outputs[0])
    bm = bmesh.new()
    for (ax, ay), (bx, by) in segs:
        v = [bm.verts.new((ax, ay, 0.15)), bm.verts.new((bx, by, 0.15)), bm.verts.new((bx, by, 2.15)), bm.verts.new((ax, ay, 2.15))]
        bm.faces.new(v)
    o = obj("fence_wire", mesh_from_bm("fence_wire", bm, [m]))
    o.visible_shadow = False


def build_roads_and_houses(ctx, rng, house_t, tree_t):
    """Suburbs south / east / west of the field, a ring road outside the fence, and a downtown to the north."""
    road_m = image_mat("road_v2", "road.png", (1.0, 1.0), rough=0.8)
    roads = []   # (cx, cy, length, along_y)

    def road(cx, cy, length, along_y, z):
        tiles = max(1.0, round(length / 24.0))
        m = road_m if tiles == 1 else image_mat("road_v2_%d" % int(tiles), "road.png", (1.0, tiles), rough=0.8)
        o = plane_obj("road", 9, length, (cx, cy, z), m, rot_z=0.0 if along_y else math.pi / 2)
        roads.append((cx, cy, length, along_y))
        return o
    # perimeter road outside the fence (east = main road with traffic)
    road(380, 750, 3400, True, 0.17)
    road(-215, 750, 3400, True, 0.17)
    road(80, -372, 1600, False, 0.21)
    # suburb grids
    blocks = []
    for (xa, xb, ya, yb) in ((-1300, 1300, -1250, -420), (440, 1500, -380, 2300), (-1500, -260, -380, 2300)):
        xs = list(range(int(xa), int(xb), 120))
        ys = list(range(int(ya), int(yb), 95))
        for x in xs:
            road(x, (ya + yb) / 2, yb - ya, True, 0.17)
        for y in ys:
            road((xa + xb) / 2, y, xb - xa, False, 0.21)
        for x in xs:
            for y in ys:
                if x + 120 > xb + 1 or y + 95 > yb + 1:
                    continue
                blocks.append((x + 4.5, x + 120 - 4.5, y + 4.5, y + 95 - 4.5))
    houses, tree_pts = [], []
    for (bx0, bx1, by0, by1) in blocks:
        if rng.random() < 0.06:          # a park: trees only
            for _ in range(14):
                tree_pts.append((rng.uniform(bx0 + 4, bx1 - 4), rng.uniform(by0 + 4, by1 - 4)))
            continue
        lot = 22.0
        n = int((bx1 - bx0) // lot)
        for side, yy in ((0, by0 + 13), (1, by1 - 13)):
            for i in range(n):
                x = bx0 + lot * (i + 0.5) + rng.uniform(-1.5, 1.5)
                me = house_t[rng.randrange(len(house_t))]
                o = obj("house", me, (x, yy + rng.uniform(-1, 1), 0.0),
                        (0, 0, (0 if side == 0 else math.pi) + rng.uniform(-0.04, 0.04)))
                houses.append(o)
                if rng.random() < 0.75:
                    tree_pts.append((x + rng.uniform(-9, 9), yy + (14 if side == 0 else -14) * rng.uniform(0.5, 1.0)))
    return roads, houses, tree_pts


def build_city(rng, region=(-1600, 1600, 2600, 4600)):
    mats = [facade_mat("city_v2_%d" % i, c, g, 3.0, 3.6, wf) for i, (c, g, wf) in enumerate((
        (hexc("d7d2c8"), hexc("3b5268"), 0.55), (hexc("b8c0c8"), hexc("4a6a86"), 0.75),
        (hexc("e5ddd0"), hexc("34495e"), 0.5), (hexc("9aa5b1"), hexc("2c4157"), 0.8),
        (hexc("c9b8a0"), hexc("3a4a5a"), 0.5)))]
    roof = pbr("cityroof_v2", hexc("7d7f82"), 0.8, var=0.1)
    x0, x1, y0, y1 = region
    n = 0
    for gx in range(int(x0), int(x1), 70):
        for gy in range(int(y0), int(y1), 70):
            if rng.random() < 0.25:
                continue
            dcx, dcy = (gx + 300) / 700.0, (gy - 3500) / 600.0
            core = math.exp(-(dcx * dcx + dcy * dcy))
            h = rng.uniform(10, 24) + core * rng.uniform(20, 95)
            w, d = rng.uniform(22, 45), rng.uniform(22, 45)
            bm = bmesh.new()
            bm_box(bm, (0, 0, h / 2), (w, d, h), 0)
            bm_box(bm, (0, 0, h + 0.4), (w + 0.6, d + 0.6, 0.8), 1)
            obj("city%d" % n, mesh_from_bm("city%d" % n, bm, [mats[rng.randrange(len(mats))], roof]),
                (gx + rng.uniform(-6, 6), gy + rng.uniform(-6, 6), 0))
            n += 1


def build_hills(rng):
    m = pbr("hill_v2", hexc("55744a"), 0.95, var=0.15, var_scale=0.002)
    for i in range(22):
        ang = rng.uniform(-0.9, 0.9) + math.pi / 2
        dist = rng.uniform(5200, 8500)
        bm = bmesh.new()
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        r2 = random.Random(i)
        for v in res["verts"]:
            v.co *= 1.0 + r2.uniform(-0.06, 0.06)
        obj("hill%d" % i, mesh_from_bm("hill%d" % i, bm, [m], smooth=True),
            (math.cos(ang) * dist, math.sin(ang) * dist, -60),
            scale=(rng.uniform(900, 1800), rng.uniform(600, 1100), rng.uniform(120, 340)))


def traffic(ctx, rng, n=10):
    """Cars driving along the perimeter road (x=380) both ways; speeds ~ 12-16 m/s."""
    T = ctx.frames
    cars = []
    for i in range(n):
        dirn = 1 if i % 2 == 0 else -1
        lane = 380 + (2.0 if dirn > 0 else -2.0)
        y0 = rng.uniform(-200, 1600)
        v = rng.uniform(11, 16) * dirn / ctx.fps
        c = L.make_car("tcar%d" % i, loc=(lane, y0, 0.17), rot_z=0.0 if dirn > 0 else math.pi, headlights=True, glow=False)
        L.drive(c, [(lane, y0 + v * f) for f in range(T)], 1)
        cars.append(c)
    _repaint_kenney()
    return cars


def build_world(ctx, seed=24):
    rng = random.Random(seed)
    L.fog(0.00022, HAZE, start=350.0)          # light aerial perspective (shader distance haze)
    plane_obj("ground", 30000, 30000, (0, 0, 0), ground_mat())
    build_airport(ctx, rng)
    house_t = house_templates(rng)
    tree_t = tree_templates(rng)
    roads, houses, tree_pts = build_roads_and_houses(ctx, rng, house_t, tree_t)
    # tree belts along the airfield edge + clusters in the fields + yard trees
    for _ in range(420):
        side = rng.random()
        if side < 0.4:
            x, y = rng.uniform(-260, -235), rng.uniform(-350, 2300)
        elif side < 0.6:
            x, y = rng.uniform(-200, 360), rng.uniform(-400, -385)
        else:
            x, y = rng.uniform(-1500, 1500), rng.uniform(1950, 2550)
        tree_pts.append((x, y))
    for _ in range(40):  # clusters
        cx, cy = rng.uniform(-2500, 2500), rng.uniform(-1300, 5200)
        if in_airfield(cx, cy, 60) or abs(cx - 380) < 30:
            continue
        for _ in range(rng.randint(6, 22)):
            tree_pts.append((cx + rng.gauss(0, 25), cy + rng.gauss(0, 25)))
    tree_pts = [(x, y) for x, y in tree_pts if not in_airfield(x, y, 4) and not _on_road(x, y, roads)]
    scatter(tree_t, tree_pts, rng, prefix="tree")
    build_city(rng)
    build_hills(rng)
    traffic(ctx, rng)
    print("[v2] world: %d houses, %d trees" % (len(houses), len(tree_pts)))


def _on_road(x, y, roads, pad=6.0):
    for cx, cy, ln, along_y in roads:
        if along_y:
            if abs(x - cx) < 4.5 + pad and abs(y - cy) < ln / 2:
                return True
        elif abs(y - cy) < 4.5 + pad and abs(x - cx) < ln / 2:
            return True
    return False


# ================================================================ the test shot
def b_airport_approach_v2(ctx, p):
    """Hook shot, v2 look: a light aircraft on a normal, stable approach in bright daylight; the camera
    starts on its rear quarter and pulls back / up to reveal the runway and the airport ahead.
    p: sun_elev, sun_az, cam_keys (optional override). No 3D text (overlays are 2D, done afterwards)."""
    T = ctx.frames
    sun_elev, sun_az = p.get("sun_elev", 40.0), p.get("sun_az", -35.0)
    daylight(ctx, sun_az, sun_elev, p.get("sky_strength", 0.065), p.get("sun_energy", 3.2),
             cloud_gain=p.get("cloud_gain"), aerosol=p.get("aerosol", 0.5), hdri=p.get("hdri", True))
    build_world(ctx)
    # flight path: stable 3.2 deg glide slope towards the 300 m aiming point, never touching down
    track = L.link(bpy.data.objects.new("track", None))
    ya, yb = p.get("y0", -660.0), p.get("y1", -300.0)

    def alt(y):
        return 300.0 * 0.056 + (0.0 - y) * 0.056 + 0.3
    for f, y in ((1, ya), (T, yb)):
        kf(track, "location", f, Vector((-3.0 + 3.0 * (f - 1) / max(1, T - 1), y, alt(y))), "LINEAR")
    plane = make_plane_v2(ctx, "lp")
    plane.parent = track
    for f in range(1, T + 2, 6):
        t = (f - 1) / ctx.fps
        kf(plane, "rotation_euler", f, Vector((math.radians(2.2 + 0.5 * math.sin(t * 1.1)),
                                                math.radians(2.0 * math.sin(t * 0.7)), math.radians(-1.0))), "BEZIER")
        kf(plane, "location", f, Vector((0, 0, 0.25 * math.sin(t * 1.5))), "BEZIER")
    keys = p.get("cam_keys") or [
        (1, (-7.5, -24.0, 3.2), (0.5, 3.0, -0.8)),
        (int(T * 0.45), (-7.0, -28.0, 3.8), (1.5, 14.0, -3.0)),
        (T, (-5.5, -24.0, 4.5), (2.5, 40.0, -8.0)),
    ]
    cam = ctx.camera(keys[0][1], target=keys[0][2], lens=p.get("lens", 30))
    cam.parent = track
    ctx.cam_target.parent = track
    for f, c, t in keys:
        kf(cam, "location", f, Vector(c), "BEZIER")
        kf(ctx.cam_target, "location", f, Vector(t), "BEZIER")
    cam.data.clip_start = 1.0
    cam.data.clip_end = 16000.0
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = plane
    cam.data.dof.aperture_fstop = p.get("fstop", 1.4)
    ctx.plane = plane
    ctx.track = track
    return plane


def export_track(ctx, plane, path):
    """Per-frame screen-space position (pixels, y from top) of the aircraft centre and its bbox, for
    2D labels that follow it."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    sc = ctx.scene
    W, H = sc.render.resolution_x, sc.render.resolution_y
    pts_local = [Vector(v) for v in ((0, 0, 0), (-5.9, 0.6, -0.2), (5.9, 0.6, -0.2), (0, -3.9, 1.8), (0, 4.3, 0),
                                     (0, 0.8, 0.95), (0, 0.5, -1.3))]
    out = []
    for f in range(1, ctx.frames + 1):
        sc.frame_set(f)
        mw = plane.matrix_world
        scr = []
        for v in pts_local:
            c = world_to_camera_view(sc, sc.camera, mw @ v)
            scr.append((c.x * W, (1 - c.y) * H))
        xs, ys = [s[0] for s in scr], [s[1] for s in scr]
        out.append({"f": f, "cx": scr[0][0], "cy": scr[0][1], "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys)})
    with open(path, "w") as fh:
        json.dump(out, fh)
    return out


# ================================================================ 2D-overlay anchors (generic)
def anchor(ctx, name, obj_, offset=(0.0, 0.0, 0.0)):
    """Register a 3D point (object + local offset) whose per-frame screen position is exported for the 2D
    overlays (labels with leader lines, measuring bars). Builders never create 3D text."""
    if not hasattr(ctx, "anchors"):
        ctx.anchors = {}
    ctx.anchors[name] = (obj_, Vector(offset))


def export_anchors(ctx, path, f0, f1):
    """Writes {"f0", "f1", "w", "h", "anchors": {name: [[x_px, y_px, in_front], ...]}} for frames f0..f1
    (pixels at the FULL output resolution 1080x1920 regardless of --scale, y from the top)."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    anchors = getattr(ctx, "anchors", {})
    if not anchors:
        return None
    sc = ctx.scene
    W, H = 1080, 1920
    out = {n: [] for n in anchors}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for n, (o, off) in anchors.items():
            c = world_to_camera_view(sc, sc.camera, o.matrix_world @ off)
            out[n].append([round(c.x * W, 2), round((1 - c.y) * H, 2), 1 if c.z > 0 else 0])
    with open(path, "w") as fh:
        json.dump({"f0": f0, "f1": f1, "w": W, "h": H, "anchors": out}, fh)
    return path


V2_BUILDERS = {"airport_approach_v2": b_airport_approach_v2}

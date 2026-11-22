"""Procedural low-poly scene library for the explainer pipeline (Blender 5.3, EEVEE).

Everything is generated from code (no footage) except the cars, which are Kenney Car Kit GLB models
(CC0, assets/kenney-car-kit, see assets/CREDITS.md), imported once per shot and linked-duplicated.
Look: navy/teal palette with red accents, shader-based distance fog (cheap, no volumetrics),
additive glow billboards for lights, camera-locked text cards in the upper safe area.

Builders (registered in BUILDERS) have the signature
    builder(ctx, params) -> None
where ctx is a Ctx with: frames (int), fps, duration (s), word_time(word, default_frac) -> frame,
and helpers to add cards. Each builder must create a camera via ctx.camera(...).

Coordinate conventions: metres; road runs along +Y; cars face +Y; Z up.
Blender 5.x notes: use keyframe_insert with the preference interpolation (Action.fcurves API is
layered now), EEVEE engine id 'BLENDER_EEVEE', material.surface_render_method for blending.
"""
import math
import os
import random
import zlib

import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- palette
def hexc(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0], lin[1], lin[2], a)


NAVY = hexc("0a1430")
NAVY2 = hexc("14244a")
TEAL = hexc("12b3b8")
TEAL_DARK = hexc("0d6f7a")
RED = hexc("ff2d3d")
AMBER = hexc("ffa21a")
WHITE = hexc("f4f7fb")
ROAD = hexc("1a1f2a")
GRASS = hexc("16232c")
FOG_DAY = hexc("6f8296")
FOG_NIGHT = hexc("2a3a52")
CAR_COLORS = [hexc(c) for c in ("2f8fb0", "c9d3df", "3a4f7a", "e6ebf1", "5c6f86", "1d6f8a", "8fa3b8", "27406b")]

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_PATH_SUB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# ---------------------------------------------------------------- keyframes
def kf(target, path, frame, value=None, interp="LINEAR", index=-1):
    """Insert a keyframe with a given interpolation (Blender 5 layered actions safe)."""
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = interp
    if value is not None:
        if index >= 0:
            getattr(target, path)[index] = value
        else:
            setattr(target, path, value)
    target.keyframe_insert(path, frame=frame, index=index)
    prefs.keyframe_new_interpolation_type = old


def kf_socket(sock, frame, value, interp="LINEAR"):
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = interp
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)
    prefs.keyframe_new_interpolation_type = old


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- scene setup
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _KENNEY.clear()          # templates point at freed datablocks after a factory reset
    _CAR_BAG.clear()
    _CAR_RNG.seed(2026)      # same car mix every time a shot is rebuilt
    scene = bpy.context.scene
    return scene


def setup_render(scene, res, fps, frames, samples, out_dir):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, frames
    scene.eevee.taa_render_samples = samples
    scene.eevee.use_raytracing = False
    scene.eevee.use_shadows = True
    scene.eevee.shadow_ray_count = 1
    scene.eevee.shadow_step_count = 4
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except Exception:
        pass
    scene.view_settings.exposure = 0.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15
    scene.render.filepath = out_dir.rstrip("/") + "/"
    scene.render.use_motion_blur = False


def setup_world(scene, color, strength=1.0):
    world = bpy.data.worlds.new("World")
    scene.world = world
    nt = world.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    return world


def add_sun(energy=2.5, rot=(50, 0, 30), color=(1, 1, 1)):
    d = bpy.data.lights.new("Sun", "SUN")
    d.energy = energy
    d.color = color
    d.angle = math.radians(8)
    o = bpy.data.objects.new("Sun", d)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
    return o


# ---------------------------------------------------------------- materials
class Fog:
    """Distance fog parameters shared by all fogged materials in a shot."""
    density = 0.0   # per metre; 0 = no fog
    color = FOG_DAY
    start = 0.0


FOG = Fog()
_MATS = {}


def _fog_wrap(m, shader_out, density_scale=1.0):
    """Mix shader_out with flat fog emission by camera distance: f = 1 - exp(-d*(dist-start))."""
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    out = nodes.get("Material Output")
    if FOG.density <= 0:
        links.new(shader_out, out.inputs["Surface"])
        return
    cam = nodes.new("ShaderNodeCameraData")
    sub = nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = FOG.start
    links.new(cam.outputs["View Distance"], sub.inputs[0])
    mx = nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0
    links.new(sub.outputs[0], mx.inputs[0])
    mul = nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = -FOG.density * density_scale
    links.new(mx.outputs[0], mul.inputs[0])
    ex = nodes.new("ShaderNodeMath"); ex.operation = "EXPONENT"
    links.new(mul.outputs[0], ex.inputs[0])
    inv = nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    links.new(ex.outputs[0], inv.inputs[1])
    em = nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = FOG.color; em.inputs["Strength"].default_value = 1.0
    mix = nodes.new("ShaderNodeMixShader")
    links.new(inv.outputs[0], mix.inputs[0])
    links.new(shader_out, mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])


def mat(name, color, rough=0.6, metal=0.0, emit=None, emit_strength=0.0, fog=True, fog_scale=1.0):
    key = (name, fog)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit is not None:
        p.inputs["Emission Color"].default_value = emit
        p.inputs["Emission Strength"].default_value = emit_strength
    if fog:
        _fog_wrap(m, p.outputs[0], fog_scale)
    _MATS[key] = m
    return m


def emissive(name, color, strength=4.0, fog_scale=0.35):
    """Pure emission (lights). Fog affects lights less (fog_scale) so they pierce the fog."""
    key = (name, "em")
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    _fog_wrap(m, em.outputs[0], fog_scale)
    _MATS[key] = m
    return m


def glow_mat(name, color, strength=3.0, fog_scale=0.25):
    """Additive radial glow for billboards (Transparent + Emission*gradient)."""
    key = (name, "glow")
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    m.surface_render_method = "BLENDED"
    try:
        m.use_transparency_overlap = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = nt.nodes.get("Material Output")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # radial falloff from UV centre: 1 - clamp(2*|uv-0.5|)
    vsub = nt.nodes.new("ShaderNodeVectorMath"); vsub.operation = "SUBTRACT"; vsub.inputs[1].default_value = (0.5, 0.5, 0)
    nt.links.new(tc.outputs["UV"], vsub.inputs[0])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"
    nt.links.new(vsub.outputs[0], ln.inputs[0])
    m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; m2.inputs[1].default_value = 2.0
    nt.links.new(ln.outputs["Value"], m2.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; inv.use_clamp = True
    nt.links.new(m2.outputs[0], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.2
    nt.links.new(inv.outputs[0], pw.inputs[0])
    st = nt.nodes.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = strength
    st.name = "GlowStrength"
    nt.links.new(pw.outputs[0], st.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = color
    nt.links.new(st.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    _MATS[key] = m
    return m


def flat_mat(name, color, alpha=1.0):
    """Unlit, unfogged colour for UI cards."""
    key = (name, "flat")
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.get("Material Output")
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    _MATS[key] = m
    return m


def blink(material, start_frame, end_frame, period_frames=16, on=6.0, off=0.2, node="Emission"):
    """Hazard-light blink on an emissive/glow material (CONSTANT keys)."""
    nt = material.node_tree
    n = nt.nodes.get("GlowStrength")
    sock = n.inputs[1] if n else nt.nodes.get(node).inputs["Strength"]
    # square wave built from paired keys (holds even if CONSTANT interpolation is ignored)
    half = period_frames // 2
    f = start_frame
    while f <= end_frame + period_frames:
        kf_socket(sock, f, on, "LINEAR")
        kf_socket(sock, f + half - 1, on, "LINEAR")
        kf_socket(sock, f + half, off, "LINEAR")
        kf_socket(sock, f + period_frames - 1, off, "LINEAR")
        f += period_frames


# ---------------------------------------------------------------- primitives
def link(obj):
    bpy.context.collection.objects.link(obj)
    return obj


def box(name, size, loc=(0, 0, 0), material=None, bevel=0.0, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
    return o


def cylinder(name, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), material=None, verts=12, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
    return o


def plane(name, size_x, size_y, loc=(0, 0, 0), material=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (size_x, size_y, 1)
    bpy.ops.object.transform_apply(scale=True)
    if material:
        o.data.materials.append(material)
    return o


def billboard(name, size, loc, material, cam, parent=None):
    # build at the origin so the mesh is centred on the object origin (TRACK_TO pivots there)
    o = plane(name, size, size, (0, 0, 0), material)
    if parent:
        o.parent = parent
    o.location = loc
    o.visible_shadow = False
    c = o.constraints.new("TRACK_TO")
    c.target = cam
    c.track_axis = "TRACK_Z"
    c.up_axis = "UP_Y"
    return o


# ---------------------------------------------------------------- environment
def road(length=600, lanes=3, lane_w=3.6, y0=-100, ice=False, median=True):
    w = lanes * lane_w
    road_mat = mat("ice", hexc("9fc6dc"), rough=0.08, metal=0.0) if ice else mat("road", ROAD, rough=0.85)
    plane("road", w + 2.0, length, (0, y0 + length / 2, 0), road_mat)
    plane("ground", 400, length, (0, y0 + length / 2, -0.05), mat("ground", GRASS, rough=1.0))
    line = mat("line", hexc("d9dee6"), rough=0.5)
    # edge lines
    for x in (-w / 2, w / 2):
        plane("edge", 0.15, length, (x, y0 + length / 2, 0.01), line)
    # dashed lane lines via array
    for i in range(1, lanes):
        x = -w / 2 + i * lane_w
        d = plane("dash", 0.15, 3.0, (x, y0, 0.01), line)
        arr = d.modifiers.new("arr", "ARRAY")
        arr.count = int(length / 12)
        arr.use_relative_offset = False
        arr.use_constant_offset = True
        arr.constant_offset_displace = (0, 12.0, 0)
    # guardrails
    rail = mat("rail", hexc("8b98a8"), rough=0.4, metal=0.6)
    for x in (-w / 2 - 1.2, w / 2 + 1.2):
        box("rail", (0.08, length, 0.3), (x, y0 + length / 2, 0.75), rail)
        p = box("post", (0.12, 0.12, 0.75), (x, y0, 0.37), rail)
        arr = p.modifiers.new("arr", "ARRAY")
        arr.count = int(length / 4)
        arr.use_relative_offset = False
        arr.use_constant_offset = True
        arr.constant_offset_displace = (0, 4.0, 0)
    return w


def lane_x(i, lanes=3, lane_w=3.6):
    return -lanes * lane_w / 2 + lane_w * (i + 0.5)


# ---------------------------------------------------------------- car (Kenney Car Kit, CC0)
# Cars are Kenney Car Kit GLB models (assets/kenney-car-kit, CC0, kenney.nl). Each model is imported
# once per shot as a hidden template; every car is a set of linked duplicates (objects sharing the
# template meshes), so 14 cars cost about as much as one import.
# Car contract (unchanged from v1 so all builders keep working): the root empty sits at ground centre,
# the car faces +Y, bumpers are at y = +/-CAR_LEN/2 = +/-2.2 m, body width ~CAR_W, lanes are 3.6 m.
KENNEY_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                           "assets", "kenney-car-kit", "Models", "GLB format"))
CAR_LEN = 4.4          # every model is normalised to this bumper-to-bumper length (v1 box car: 4.4 m)
CAR_W = 1.9            # ... and this overall width incl. wheels (v1: 1.8 m body)
CAR_H_SCALE = 1.0      # vertical scale relative to the width scale (1.0 = Kenney's own proportions)
PAINT_SAT = 0.62       # Kenney colours, desaturated so they sit in the fog / navy palette
PAINT_VAL = 0.92
# ordinary civilian traffic (model, weight). No debris-*, no emergency vehicles unless a shot asks.
CIVILIAN = [("sedan", 3), ("suv", 3), ("hatchback-sports", 2), ("suv-luxury", 2), ("van", 2),
            ("sedan-sports", 1), ("taxi", 1), ("delivery", 1)]
# lamp centres in Kenney model space (front = -Y, rear = +Y): (|x|, y, z) for (tail, head) lamps,
# measured from the red / yellow lamp texels of each model.
LAMPS = {
    "sedan":            ((0.42, 1.25, 0.65), (0.42, -1.15, 0.65)),
    "suv":              ((0.46, 1.15, 0.60), (0.44, -1.25, 0.64)),
    "hatchback-sports": ((0.45, 1.21, 0.845), (0.45, -1.30, 0.55)),
    "sedan-sports":     ((0.45, 1.15, 0.65), (0.42, -1.09, 0.635)),
    "suv-luxury":       ((0.44, 1.40, 0.75), (0.42, -1.235, 0.69)),
    "taxi":             ((0.42, 1.35, 0.65), (0.42, -1.25, 0.75)),
    "delivery":         ((0.52, 1.60, 0.45), (0.46, -1.50, 0.65)),
    "van":              ((0.42, 1.35, 0.65), (0.44, -1.24, 0.65)),
}
_KENNEY = {}           # model -> template dict (cleared in reset_scene)
_CAR_RNG = random.Random(2026)   # private stream: never disturbs the builders' global random.seed()
_CAR_BAG = []


def kenney_paint():
    """Shared car material: Kenney colormap, desaturated, through the shot's distance fog."""
    key = ("kenney_paint", True)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new("kenney_paint")
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(KENNEY_DIR, "Textures", "colormap.png"), check_existing=True)
    tex.interpolation = "Closest"
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = PAINT_SAT
    hs.inputs["Value"].default_value = PAINT_VAL
    nt.links.new(tex.outputs["Color"], hs.inputs["Color"])
    nt.links.new(hs.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.45
    p.inputs["Metallic"].default_value = 0.1
    _fog_wrap(m, p.outputs[0])
    _MATS[key] = m
    return m


def _kenney_template(model):
    """Import <model>.glb once; keep only mesh datablocks + their placement (objects are removed)."""
    if model in _KENNEY:
        return _KENNEY[model]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(KENNEY_DIR, model + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    paint = kenney_paint()
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    parts, wheels = [], []
    for o in new:
        if o.type != "MESH":
            continue
        mw = o.matrix_world.copy()
        for c in o.bound_box:
            v = mw @ Vector(c)
            lo = Vector(map(min, lo, v))
            hi = Vector(map(max, hi, v))
        o.data.materials.clear()
        o.data.materials.append(paint)
        nm = o.name.split(".")[0]
        # road wheels spin; anything else (incl. the SUV's rear spare "wheel-back") is a static part
        if nm.startswith("wheel-") and (nm.endswith("left") or nm.endswith("right")):
            zs = [(mw @ Vector(c)).z for c in o.bound_box]
            wheels.append((o.data, mw.translation.copy(), (max(zs) - min(zs)) / 2.0))
        else:
            parts.append((o.data, mw))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for mt in bpy.data.materials:
        if mt.name.startswith("colormap") and mt.users == 0:
            bpy.data.materials.remove(mt)
    sx = CAR_W / (hi.x - lo.x)
    sy = CAR_LEN / (hi.y - lo.y)
    sz = sx * CAR_H_SCALE
    cy = (hi.y + lo.y) / 2.0
    tail, head = LAMPS.get(model, ((0.42, hi.y - 0.05, 0.65), (0.42, lo.y + 0.1, 0.65)))

    def to_root(x, y, z):
        # model space (front -Y) -> car root space (front +Y), centred and normalised
        return Vector((-x * sx, -(y - cy) * sy, z * sz))

    S = Matrix.Diagonal((sx, sy, sz, 1.0))
    M = Matrix.Rotation(math.pi, 4, "Z") @ S @ Matrix.Translation((0, -cy, 0))
    t = {"parts": [(d, M @ mw) for d, mw in parts],
         "wheels": [(d, to_root(*c), r * sz) for d, c, r in wheels],
         "scale": (sx, sy, sz),
         "tail": [to_root(s * tail[0], tail[1], tail[2]) for s in (1, -1)],
         "head": [to_root(s * head[0], head[1], head[2]) for s in (1, -1)]}
    _KENNEY[model] = t
    return t


def pick_model(models=None):
    """Seeded, weighted 'bag' draw so a queue gets a balanced mix (deterministic per shot)."""
    if models:
        return models[_CAR_RNG.randrange(len(models))]
    if not _CAR_BAG:
        bag = [m for m, w in CIVILIAN for _ in range(w)]
        _CAR_RNG.shuffle(bag)
        _CAR_BAG.extend(bag)
    return _CAR_BAG.pop()


class Car:
    def __init__(self, obj, brake_mat, wheels):
        self.obj = obj
        self.brake_mat = brake_mat
        self.wheels = wheels
        self.wheel_r = 0.34
        self.head_pos = []
        self.tail_pos = []
        self.model = None


def make_car(name, color=None, loc=(0, 0, 0), rot_z=0.0, cam=None, hazard_mat=None, glow=True,
             brake_mat=None, headlights=True, scale=1.0, head_glow=False, brake_glow=False, model=None):
    """Kenney car (linked duplicate of a once-imported template). Origin at ground centre, faces +Y.
    `color` is ignored (kept for builder compatibility; paint comes from the Kenney model).
    `hazard_mat`: anything truthy turns on blinking hazards with a per-car phase offset.
    `model`: Kenney model name; default = seeded random civilian car."""
    model = model or pick_model()
    t = _kenney_template(model)
    root = bpy.data.objects.new(name, None)
    link(root)
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    root.scale = (scale, scale, scale)
    for i, (data, mtx) in enumerate(t["parts"]):
        o = link(bpy.data.objects.new("%s_part%d" % (name, i), data))
        o.parent = root
        o.matrix_basis = mtx
    sx, _, sz = t["scale"]
    wheels = []
    for i, (data, c, r) in enumerate(t["wheels"]):
        w = link(bpy.data.objects.new("%s_wheel%d" % (name, i), data))
        w.parent = root
        w.location = c
        # uniform scale in the wheel's YZ plane keeps it round however the body was stretched;
        # yaw pi = model faces +Y. Spin goes on rotation_euler[0] (local X, applied before the yaw).
        w.scale = (sx, sz, sz)
        w.rotation_euler = (0.0, 0.0, math.pi)
        wheels.append(w)
    half = CAR_LEN / 2.0
    head = emissive("headlight", hexc("fff4d6"), 6.0)
    if brake_mat is None:
        brake_mat = emissive("tail_" + name, RED, 1.5)
    hz_glow = hz_body = None
    if hazard_mat is not None and hazard_mat is not False:
        # own materials per car -> own blink phase (real hazards are never in sync)
        rng = random.Random(zlib.crc32(name.encode()))
        period = 18 + rng.choice((-1, 0, 0, 1))
        start = 1 - rng.randint(0, 6)
        end = bpy.context.scene.frame_end
        hz_body = emissive("hz_body_" + name, AMBER, 3.0)
        blink(hz_body, start, end, period, on=6.0, off=0.3)
        if glow and cam is not None:
            hz_glow = glow_mat("hz_glow_" + name, AMBER, 4.0)
            blink(hz_glow, start, end, period, on=3.0, off=0.0)
    for tp, hp in zip(t["tail"], t["head"]):
        side = 1 if tp.x > 0 else -1
        # lamp lenses sit a few cm proud of the body (no z-fighting). Each cluster = red (inner) +
        # amber indicator (outer) on the model's own lamp face, so nothing floats off a chamfered corner.
        box(name + "_tl", (0.26, 0.05, 0.13), (tp.x - side * 0.04, tp.y - 0.03, tp.z), brake_mat, parent=root)
        if headlights:
            box(name + "_hl", (0.28, 0.05, 0.14), (hp.x - side * 0.04, hp.y + 0.03, hp.z), head, parent=root)
        hzx = tp.x + side * 0.15
        if hz_body is not None:
            box(name + "_hz", (0.11, 0.05, 0.11), (hzx, tp.y - 0.03, tp.z), hz_body, parent=root)
            box(name + "_hzf", (0.11, 0.05, 0.11), (hp.x + side * 0.15, hp.y + 0.03, hp.z), hz_body, parent=root)
            if hz_glow is not None:
                billboard(name + "_hzg", 1.5, (hzx, -half - 0.25, tp.z), hz_glow, cam, parent=root)
        if head_glow and cam is not None and headlights:
            billboard(name + "_hlg", 1.3, (hp.x, half + 0.3, hp.z), glow_mat("head_glow", hexc("fff1c9"), 1.6),
                      cam, parent=root)
        if brake_glow and cam is not None:
            bg = glow_mat("bglow_" + name, RED, 0.0)
            billboard(name + "_blg", 1.7, (tp.x, -half - 0.3, tp.z + 0.05), bg, cam, parent=root)
    car = Car(root, brake_mat, wheels)
    car.model = model
    car.wheel_r = t["wheels"][0][2] if t["wheels"] else 0.34
    car.head_pos = [Vector(p) for p in t["head"]]
    car.tail_pos = [Vector(p) for p in t["tail"]]
    car.brake_glow = glow_mat("bglow_" + name, RED, 0.0) if (brake_glow and cam is not None) else None
    return car


def drive(car, positions, start_frame=1, wheel_r=None):
    """positions: list of (x, y) per frame from start_frame; keyframes location + wheel spin
    (wheel angle = distance travelled / wheel radius, so the tyres roll without slipping)."""
    r = wheel_r or car.wheel_r
    dist = 0.0
    prev = None
    for i, (x, y) in enumerate(positions):
        f = start_frame + i
        kf(car.obj, "location", f, Vector((x, y, car.obj.location.z)))
        if prev is not None:
            dist += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
        for w in car.wheels:
            kf(w, "rotation_euler", f, dist / r, "LINEAR", index=0)


def brake_light(car, frame, on=True, strength_on=9.0, strength_off=1.5):
    nt = car.brake_mat.node_tree
    sock = nt.nodes.get("Emission").inputs["Strength"]
    kf_socket(sock, 1, strength_off if on else strength_on, "LINEAR")
    if frame > 1:
        kf_socket(sock, max(1, frame - 1), strength_off if on else strength_on, "LINEAR")
    kf_socket(sock, frame, strength_on if on else strength_off, "LINEAR")
    g = getattr(car, "brake_glow", None)
    if g is not None:
        gs = g.node_tree.nodes.get("GlowStrength").inputs[1]
        kf_socket(gs, 1, 0.0, "CONSTANT")
        if frame > 1:
            kf_socket(gs, frame - 1, 0.0 if on else 2.2, "LINEAR")
        kf_socket(gs, frame, 2.2 if on else 0.0, "LINEAR")


def headlight_beams(car, energy=1500, color=(1.0, 0.95, 0.85), spread=55):
    """Real spot lights from the headlights so the road ahead is lit through the fog."""
    for hp in (car.head_pos or [Vector((s, 2.2, 0.72)) for s in (-0.62, 0.62)]):
        ld = bpy.data.lights.new("beam", "SPOT")
        ld.energy = energy
        ld.color = color
        ld.spot_size = math.radians(spread)
        ld.spot_blend = 0.6
        lo = link(bpy.data.objects.new("beam", ld))
        lo.parent = car.obj
        lo.location = (hp.x, hp.y + 0.1, hp.z + 0.03)
        lo.rotation_euler = (math.radians(84), 0, 0)  # point forward (+Y), slightly down


def profile(v0, frames, fps, events):
    """Kinematic 1D profile. events: sorted list of (frame, accel m/s^2). Returns y per frame, v>=0."""
    y, v, a = 0.0, v0, 0.0
    ev = sorted(events)
    out = []
    dt = 1.0 / fps
    for f in range(1, frames + 1):
        for (ef, ea) in ev:
            if ef == f:
                a = ea
        out.append(y)
        v = max(0.0, v + a * dt)
        y += v * dt
    return out


# ---------------------------------------------------------------- camera + cards
class Ctx:
    def __init__(self, scene, frames, fps, words, beat_start):
        self.scene = scene
        self.frames = frames
        self.fps = fps
        self.duration = frames / float(fps)
        self.words = words          # [{word, start, end}] absolute seconds within whole video
        self.beat_start = beat_start
        self.cam = None
        self._fonts = {}

    def f(self, seconds):
        return max(1, int(round(seconds * self.fps)) + 1)

    def word_time(self, word, default_frac=0.5, nth=0):
        """Frame at which `word` (case-insensitive prefix match) is spoken in this beat."""
        w = word.lower()
        hits = [x for x in self.words if x["norm"].startswith(w)]
        if len(hits) > nth:
            return self.f(hits[nth]["start"] - self.beat_start)
        return self.f(default_frac * self.duration)

    def camera(self, loc, target=None, lens=35, rot=None):
        cd = bpy.data.cameras.new("Cam")
        cd.lens = lens
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = 24.0
        cd.clip_start = 0.05
        cd.clip_end = 2000
        cam = link(bpy.data.objects.new("Cam", cd))
        cam.location = loc
        self.scene.camera = cam
        if target is not None:
            tgt = target if isinstance(target, bpy.types.Object) else self.empty("CamTarget", target)
            c = cam.constraints.new("TRACK_TO")
            c.target = tgt
            c.track_axis = "TRACK_NEGATIVE_Z"
            c.up_axis = "UP_Y"
            self.cam_target = tgt
        elif rot is not None:
            cam.rotation_euler = [math.radians(a) for a in rot]
        self.cam = cam
        return cam

    def empty(self, name, loc):
        e = link(bpy.data.objects.new(name, None))
        e.location = loc
        return e

    def font(self, path):
        if path not in self._fonts:
            self._fonts[path] = bpy.data.fonts.load(path)
        return self._fonts[path]

    def _screen(self, x_frac, y_frac, d=2.0):
        """Camera-local position for a screen point (0..1, y from top) at distance d."""
        cd = self.cam.data
        h = d * cd.sensor_height / cd.lens
        w = h * self.scene.render.resolution_x / self.scene.render.resolution_y
        return Vector(((x_frac - 0.5) * w, (0.5 - y_frac) * h, -d)), h

    def text(self, body, x_frac=0.5, y_frac=0.2, height_frac=0.05, color=WHITE, font=FONT_PATH,
             appear=1, disappear=None, d=2.0, panel=None, panel_pad=(0.06, 0.035), max_w_frac=0.86):
        """Camera-locked text. height_frac = cap height as fraction of frame height."""
        pos, h = self._screen(x_frac, y_frac, d)
        cu = bpy.data.curves.new("txt", "FONT")
        cu.body = body
        cu.font = self.font(font)
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.size = h * height_frac * 1.4
        o = link(bpy.data.objects.new("txt", cu))
        o.data.materials.append(flat_mat("txt_%s" % "%.3f%.3f%.3f" % color[:3], color))
        o.parent = self.cam
        o.location = pos
        # fit width
        bpy.context.view_layer.update()
        w_frame = h * self.scene.render.resolution_x / self.scene.render.resolution_y
        dims = o.dimensions
        if dims.x > w_frame * max_w_frac:
            cu.size *= (w_frame * max_w_frac) / dims.x
            bpy.context.view_layer.update()
            dims = o.dimensions
        objs = [o]
        if panel is not None:
            pw = dims.x + w_frame * panel_pad[0] * 2
            ph = dims.y + h * panel_pad[1] * 2
            bpy.ops.mesh.primitive_plane_add(size=1)
            p = bpy.context.object
            p.scale = (pw, ph, 1)
            bpy.ops.object.transform_apply(scale=True)
            p.data.materials.append(flat_mat("panel_%s" % "%.3f%.3f%.3f" % panel[:3], panel))
            p.parent = self.cam
            p.location = pos + Vector((0, 0, -0.002))
            # accent bar on the left
            bpy.ops.mesh.primitive_plane_add(size=1)
            b = bpy.context.object
            b.scale = (w_frame * 0.012, ph, 1)
            bpy.ops.object.transform_apply(scale=True)
            b.data.materials.append(flat_mat("accent_red", RED))
            b.parent = self.cam
            b.location = pos + Vector((-pw / 2 + w_frame * 0.006, 0, -0.001))
            objs += [p, b]
        for ob in objs:
            ob.visible_shadow = False
            self._pop(ob, appear, disappear)
        return o

    def _pop(self, o, appear, disappear):
        s = o.scale.copy()
        if appear > 1:
            kf(o, "scale", 1, Vector((0, 0, 0)), "CONSTANT")
            kf(o, "scale", appear, Vector((0.001, 0.001, 0.001)), "BEZIER")
        kf(o, "scale", appear + 5, s * 1.08, "BEZIER")
        kf(o, "scale", appear + 9, s, "BEZIER")
        if disappear:
            kf(o, "scale", disappear - 5, s, "BEZIER")
            kf(o, "scale", disappear, Vector((0.001, 0.001, 0.001)), "CONSTANT")

    def card(self, title, sub=None, y_frac=0.2, appear=None, title_color=WHITE, disappear=None, size=0.052):
        appear = appear or self.f(0.25)
        t = self.text(title, 0.5, y_frac, size, title_color, appear=appear, disappear=disappear, panel=NAVY)
        if sub:
            _, h = self._screen(0.5, 0.5)
            half = t.dimensions.y / h / 2.0
            sub_size = max(0.022, size * 0.42)
            self.text(sub, 0.5, y_frac + half + 0.068 + sub_size * 0.6, sub_size, hexc("dff3f6"), FONT_PATH_SUB,
                      appear=appear + 4, disappear=disappear, d=1.99, panel=hexc("0d3b4f"), max_w_frac=0.8)


def label3d(ctx, body, loc, size=1.0, color=WHITE, rot=(90, 0, 0), font=FONT_PATH, face_cam=True, appear=1):
    cu = bpy.data.curves.new("lbl", "FONT")
    cu.body = body
    cu.font = ctx.font(font)
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = size
    o = link(bpy.data.objects.new("lbl", cu))
    o.visible_shadow = False
    o.data.materials.append(flat_mat("lbl_%s" % "%.3f%.3f%.3f" % color[:3], color))
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    if face_cam and ctx.cam is not None:
        c = o.constraints.new("DAMPED_TRACK")
        c.target = ctx.cam
        c.track_axis = "TRACK_Z"
    ctx._pop(o, appear, None)
    return o


def animate_cam(ctx, keys, interp="BEZIER"):
    """keys: list of (frame, (x,y,z)) camera locations."""
    for f, loc in keys:
        kf(ctx.cam, "location", f, Vector(loc), interp)


def animate_target(ctx, keys, interp="BEZIER"):
    for f, loc in keys:
        kf(ctx.cam_target, "location", f, Vector(loc), interp)


def fog(density, color, start=0.0):
    FOG.density = density
    FOG.color = color
    FOG.start = start


# ================================================================ BUILDERS
def b_fog_highway(ctx, p):
    """Queue of stopped cars with blinking hazards in dense fog; slow dolly / crane."""
    random.seed(7)
    fog(0.035 * p.get("fog", 1.0), FOG_DAY, start=4.0)
    setup_world(ctx.scene, FOG_DAY, 1.0)
    add_sun(1.2, (60, 0, 20))
    road(length=500, y0=-150)
    cam = ctx.camera((5.5, -30, 6.5), target=(0, 15, 0.5), lens=30)
    models = p.get("models")  # optional list of Kenney model names (e.g. a shot that asks for "police")
    n = int(p.get("cars", 12))
    y = 0.0
    k = 0
    while k < n:
        for lane in range(3):
            if k >= n:
                break
            jitter = random.uniform(-1.2, 1.2)
            rot = math.radians(random.uniform(-9, 9))
            c = make_car("car%d" % k, CAR_COLORS[k % len(CAR_COLORS)],
                         (lane_x(lane) + random.uniform(-0.5, 0.5), y + jitter + lane * 1.7, 0), rot,
                         cam=cam, hazard_mat=True, brake_mat=emissive("tail_static", RED, 5.0),
                         model=pick_model(models) if models else None)
            k += 1
        y += 6.2
    # one car approaching slowly from behind and stopping with plenty of room
    # one car arriving slowly in the right lane and stopping with plenty of room (no impact)
    ax, ay = lane_x(2), -24.0
    appr = make_car("approach", CAR_COLORS[3], (ax, ay, 0), 0, cam=cam, hazard_mat=None,
                    brake_mat=emissive("tail_app", RED, 2.0), brake_glow=True)
    f_b = int(ctx.frames * 0.15)
    stop_f = int(ctx.frames * 0.6)
    v_a = 5.0
    ys = profile(v_a, ctx.frames, ctx.fps, [(f_b, -v_a * ctx.fps / max(1, stop_f - f_b))])
    drive(appr, [(ax, ay + yy) for yy in ys])
    brake_light(appr, f_b, True)
    if p.get("camera") == "crane_up":
        animate_cam(ctx, [(1, (4.0, -26, 3.0)), (ctx.frames, (2.5, -22, 14.0))])
    else:
        animate_cam(ctx, [(1, (6.5, -38, 5.5)), (ctx.frames, (3.5, -24, 5.0))])
    if p.get("card"):
        big = len(p["card"]) <= 14
        ctx.card(p["card"], p.get("subcard"), y_frac=0.2, title_color=RED if big else WHITE,
                 size=0.075 if big else 0.05)


def b_chain_topdown(ctx, p):
    """Top-down: a column of cars brakes one after another (brake lights ripple back)."""
    fog(0.0, NAVY)
    setup_world(ctx.scene, NAVY, 1.0)
    add_sun(2.5, (25, 10, 30))
    road(length=900, y0=-300, lanes=3)
    n = int(p.get("cars", 12))
    v0 = 22.0
    gap = 14.0
    cam = ctx.camera((0, 0, 62), rot=(0, 0, 0), lens=32)
    start_brake = int(ctx.frames * 0.2)
    cars = []
    for i in range(n):
        lane = 1
        c = make_car("c%d" % i, CAR_COLORS[i % len(CAR_COLORS)], (lane_x(lane), -i * gap, 0), 0,
                     cam=cam, brake_glow=True)
        cars.append(c)
    # side-lane traffic parked further back for context (static, no lights)
    delay = int(0.7 * ctx.fps)
    final_y = []
    for i, c in enumerate(cars):
        bf = start_brake + i * delay
        ys = profile(v0, ctx.frames, ctx.fps, [(bf, -7.5)])
        pos = [-i * gap + yy for yy in ys]
        if i > 0:
            prev = final_y[i - 1]
            pos = [min(a, b - 4.6) for a, b in zip(pos, prev)]
        final_y.append(pos)
        drive(c, [(lane_x(1), yy) for yy in pos])
        brake_light(c, bf, True, 12.0)
    # camera: follows the column centre, slowly rotating for a gentle move
    for f in range(1, ctx.frames + 1, 3):
        y = sum(final_y[k][f - 1] for k in range(n)) / n
        kf(cam, "location", f, Vector((0, y + 6, 62 - 8 * smooth(f / ctx.frames))), "LINEAR")
        kf(cam, "rotation_euler", f, Vector((0, 0, math.radians(-8 + 16 * f / ctx.frames))), "LINEAR")
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.17, title_color=WHITE, size=0.05, appear=ctx.word_time("chain", 0.85))


def b_visibility(ctx, p):
    """Chase cam in thick fog; '50 m' marker; stopped car emerges at the end."""
    fog(0.055, FOG_DAY, start=2.0)
    setup_world(ctx.scene, FOG_DAY, 1.0)
    add_sun(1.0, (60, 0, 20))
    road(length=1200, y0=-50)
    v = 26.0
    lx = lane_x(1)
    cam = ctx.camera((lx + 1.0, -10, 3.4), target=(lx, 30, 1.0), lens=30)
    car = make_car("hero", CAR_COLORS[0], (lx, 0, 0), 0, cam=cam)
    headlight_beams(car)
    T = ctx.frames
    f_stopcar = int(T * 0.8)
    ys = [v * (f / ctx.fps) for f in range(T)]
    drive(car, [(lx, y) for y in ys])
    for f in range(1, T + 1, 3):
        y = ys[f - 1]
        kf(cam, "location", f, Vector((lx + 1.0, y - 10, 3.4)))
        kf(ctx.cam_target, "location", f, Vector((lx, y + 30, 1.0)))
    # 50 m marker that travels with the car
    marker = bpy.data.objects.new("marker", None)
    link(marker)
    f_mark = ctx.word_time("fifty", 0.35)
    bar = plane("bar", 3.4, 0.6, (lx, 50, 0.03), flat_mat("teal_flat", TEAL))
    bar.parent = marker
    for sx in (-1.9, 1.9):
        side = plane("side", 0.18, 48, (lx + sx, 26, 0.03), flat_mat("teal_flat", TEAL))
        side.parent = marker
        ctx._pop(side, f_mark, None)
    ctx._pop(bar, f_mark, None)
    for f in range(1, T + 1, 3):
        kf(marker, "location", f, Vector((0, ys[f - 1], 0)))
    ctx.text(p.get("distance_label", "~50 m VISIBLE").upper(), 0.5, 0.40, 0.034, TEAL, FONT_PATH,
             appear=f_mark, panel=NAVY, max_w_frac=0.6)
    make_car("stopped", CAR_COLORS[4], (lx, ys[-1] + 34, 0), 0, cam=cam, hazard_mat=True,
             brake_mat=emissive("tail_static", RED, 5.0))
    if p.get("card"):
        ctx.card(p["card"], p.get("subcard"), y_frac=0.17, size=0.05)


def b_stopping_distance(ctx, p):
    """Fixed high view down the road: reaction strip (teal) then braking strip (red) grow."""
    fog(0.003, NAVY2, start=60)
    setup_world(ctx.scene, NAVY2, 1.0)
    add_sun(2.2, (40, 0, 35))
    road(length=600, y0=-150)
    T = ctx.frames
    rm, bm = float(p.get("reaction_m", 21)), float(p.get("braking_m", 75))
    f_react = ctx.word_time("reaction", 0.2)
    f_brake = ctx.word_time("braking", 0.55)
    f_react = min(f_react, f_brake - 10)
    brake_frames = int(4.0 * ctx.fps)
    ys = []
    for f in range(1, T + 1):
        if f < f_react:
            y = -(f_react - f) / ctx.fps * 6.0
        elif f < f_brake:
            y = rm * (f - f_react) / float(f_brake - f_react)
        else:
            t = min(1.0, (f - f_brake) / float(brake_frames))
            y = rm + bm * (1 - (1 - t) ** 2)
        ys.append(y)
    lx = lane_x(1)
    cam = ctx.camera((lx + 9, -26, 22), target=(lx, 40, 0), lens=26)
    car = make_car("hero", CAR_COLORS[0], (lx, ys[0], 0), 0, cam=cam, brake_glow=True)
    drive(car, [(lx, y) for y in ys])
    brake_light(car, f_brake, True, 12.0)

    def strip(name, y0, color, f0, f1):
        o = plane(name, 3.2, 1.0, (0, 0, 0), flat_mat(name, color))
        root = bpy.data.objects.new(name + "_root", None)
        link(root)
        root.location = (lx, y0, 0.04)
        o.parent = root
        o.location = (0, 0.5, 0)
        kf(root, "scale", 1, Vector((1, 0.001, 1)), "CONSTANT")
        kf(root, "scale", f0, Vector((1, 0.001, 1)), "LINEAR")
        for f in range(f0, f1 + 1, 2):
            kf(root, "scale", f, Vector((1, max(0.001, ys[min(f, T) - 1] - y0 - 2.2), 1)), "LINEAR")
        return root
    strip("react", 0.0, TEAL, f_react, f_brake)
    strip("brake", rm, RED, f_brake, min(T, f_brake + brake_frames))
    ctx.text("REACTION  %d m" % int(rm), 0.5, 0.245, 0.026, WHITE, FONT_PATH, appear=f_react + 3,
             panel=TEAL_DARK, max_w_frac=0.6)
    ctx.text("BRAKING  %d m" % int(bm), 0.5, 0.322, 0.026, WHITE, FONT_PATH, appear=f_brake + 3,
             panel=hexc("9a1020"), max_w_frac=0.6)
    animate_cam(ctx, [(1, (lx + 9, -28, 20)), (T, (lx + 12, -18, 30))])
    animate_target(ctx, [(1, (lx, 30, 0)), (T, (lx, 48, 0))])
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.15, size=0.045)
    if p.get("subcard"):
        ctx.text(p["subcard"], 0.5, 0.399, 0.026, WHITE, FONT_PATH, appear=ctx.word_time("seventy", 0.8),
                 panel=NAVY, max_w_frac=0.7)


def b_following_gap(ctx, p):
    """Two cars too close: gap bar shrinks, lead brakes, follower stops just touching."""
    fog(0.012, FOG_NIGHT, start=10)
    setup_world(ctx.scene, FOG_NIGHT, 1.0)
    add_sun(1.6, (45, 0, 40))
    road(length=900, y0=-100)
    T = ctx.frames
    lx = lane_x(1)
    v = 25.0
    cam = ctx.camera((lx + 8, -14, 6.5), target=(lx, 4, 0.8), lens=30)
    lead = make_car("lead", CAR_COLORS[2], (lx, 9, 0), 0, cam=cam, brake_mat=emissive("tail_lead", RED, 1.5),
                    brake_glow=True)
    fol = make_car("fol", CAR_COLORS[1], (lx, 0, 0), 0, cam=cam, brake_mat=emissive("tail_fol", RED, 1.5),
                   brake_glow=True)
    f_stop = ctx.word_time("stops", 0.45)
    react = int(0.9 * ctx.fps)
    ly = [9.0 + y for y in profile(v, T, ctx.fps, [(f_stop, -9.0)])]
    fy0 = profile(v, T, ctx.fps, [(f_stop + react, -9.0)])
    fy = []
    for f in range(T):
        squeeze = 2.5 * smooth(f / max(1.0, f_stop * 0.8))
        fy.append(min(fy0[f] + squeeze, ly[f] - 4.55))
    drive(lead, [(lx, y) for y in ly])
    drive(fol, [(lx, y) for y in fy])
    brake_light(lead, f_stop, True, 12.0)
    brake_light(fol, f_stop + react, True, 12.0)
    groot = bpy.data.objects.new("gap", None)
    link(groot)
    g = plane("gapbar", 1.4, 1.0, (0, 0.5, 0), flat_mat("red_flat", RED))
    g.parent = groot
    for f in range(1, T + 1, 2):
        rear_of_lead = ly[f - 1] - 2.2
        front_of_fol = fy[f - 1] + 2.2
        groot.location = (lx, front_of_fol, 0.05)
        groot.keyframe_insert("location", frame=f)
        kf(groot, "scale", f, Vector((1, max(0.001, rear_of_lead - front_of_fol), 1)), "LINEAR")
    for f in range(1, T + 1, 3):
        y = fy[f - 1]
        kf(cam, "location", f, Vector((lx + 8, y - 12, 6.0)))
        kf(ctx.cam_target, "location", f, Vector((lx, y + 5, 0.8)))
    if p.get("card"):
        ctx.card(p["card"], None, y_frac=0.17, title_color=RED, size=0.07)


def b_ice_road(ctx, p):
    """Two lanes: dry (stops short) vs icy (slides much further, slight yaw)."""
    fog(0.004, hexc("1b2c45"), start=40)
    setup_world(ctx.scene, hexc("1b2c45"), 1.0)
    add_sun(2.4, (35, 0, 30), (0.9, 0.95, 1.0))
    T = ctx.frames
    road(length=700, y0=-100, lanes=2)
    ice = mat("ice2", hexc("bfe6f5"), rough=0.05, metal=0.1)
    plane("icesheet", 3.4, 600, (lane_x(1, 2), 200, 0.015), ice)
    v = 16.0
    f_b = ctx.word_time("ice", 0.4, nth=1) if False else ctx.f(1.2)
    dry = profile(v, T, ctx.fps, [(f_b, -8.0)])
    icy = profile(v, T, ctx.fps, [(f_b, -1.1)])
    cam = ctx.camera((7, -14, 9), target=(0, 10, 0), lens=30)
    cd = make_car("dry", CAR_COLORS[0], (lane_x(0, 2), 0, 0), 0, cam=cam, brake_glow=True)
    ci = make_car("icy", CAR_COLORS[1], (lane_x(1, 2), 0, 0), 0, cam=cam, brake_glow=True)
    drive(cd, [(lane_x(0, 2), y) for y in dry])
    drive(ci, [(lane_x(1, 2) + 0.35 * math.sin(y / 25.0), y) for y in icy])
    for f in range(1, T + 1, 4):
        kf(ci.obj, "rotation_euler", f, Vector((0, 0, math.radians(7) * math.sin(icy[f - 1] / 20.0))), "LINEAR")
    brake_light(cd, f_b, True, 12.0)
    brake_light(ci, f_b, True, 12.0)
    for f in range(1, T + 1, 3):
        a, b = dry[f - 1], icy[f - 1]
        sep = b - a
        kf(cam, "location", f, Vector((6 + 0.04 * sep, a - 14 - 0.2 * sep, 8 + 0.55 * sep)))
        kf(ctx.cam_target, "location", f, Vector((0, a + 0.62 * sep + 3, 0)))
    ctx.text("DRY ROAD", 0.2, 0.365, 0.026, WHITE, FONT_PATH, appear=ctx.f(2.5), panel=TEAL_DARK, max_w_frac=0.4)
    ctx.text("ICE", 0.86, 0.365, 0.026, NAVY, FONT_PATH, appear=ctx.f(2.8), panel=hexc("bfe6f5"), max_w_frac=0.4)
    if p.get("card"):
        ctx.card(p["card"], p.get("subcard"), y_frac=0.17, title_color=WHITE, size=0.055)


def b_dominoes(ctx, p):
    """Row of dominoes toppling in sequence (metaphor for the chain reaction)."""
    fog(0.03, NAVY, start=8)
    setup_world(ctx.scene, NAVY, 1.0)
    add_sun(2.2, (50, 0, 40))
    T = ctx.frames
    floor = mat("floor", hexc("0e1b33"), rough=0.3, metal=0.1)
    plane("floor", 300, 300, (0, 20, 0), floor)
    n = int(p.get("count", 16))
    spacing = 1.25
    h, w, d = 1.9, 0.95, 0.28
    dm = mat("domino", hexc("eef2f7"), rough=0.35)
    first = mat("domino_red", RED, rough=0.35)
    pip = flat_mat("pip", NAVY)
    f0 = ctx.word_time("brakes", 0.22)
    step = int(0.4 * ctx.fps)
    fall = int(0.5 * ctx.fps)
    for i in range(n):
        piv = bpy.data.objects.new("dpiv%d" % i, None)
        link(piv)
        piv.location = (0, i * spacing, 0)
        b = box("dom%d" % i, (w, d, h), (0, 0, 0), first if i == 0 else dm, bevel=0.04)
        b.parent = piv
        b.location = (0, -d / 2, h / 2)
        for zz in (h * 0.27, h * 0.73):
            pp = cylinder("pip", 0.1, 0.03, (0, 0, 0), (math.radians(90), 0, 0), pip, verts=10)
            pp.parent = piv
            pp.location = (0.0, -d - 0.005, zz)
        # rest angle: top leans on the next domino (or lies down for the last one)
        gapd = spacing - d
        rest = math.asin(min(0.98, gapd / h)) if i < n - 1 else math.radians(88)
        rest = rest + math.radians(4) if i < n - 1 else rest
        fs = f0 + i * step
        kf(piv, "rotation_euler", 1, Vector((0, 0, 0)), "CONSTANT")
        kf(piv, "rotation_euler", fs, Vector((0, 0, 0)), "BEZIER")
        kf(piv, "rotation_euler", fs + fall, Vector((-rest, 0, 0)), "BEZIER")
    length = (n - 1) * spacing
    cam = ctx.camera((7.5, -7, 3.6), target=(0, 2, 0.9), lens=32)
    end_f = min(T, f0 + n * step + fall)
    animate_cam(ctx, [(1, (8.0, -8, 3.4)), (f0, (7.5, -6, 3.6)), (end_f, (7.0, length * 0.7, 4.2)), (T, (9.0, length * 0.3, 9.0))])
    animate_target(ctx, [(1, (0, 1.5, 0.9)), (f0, (0, 2.5, 0.9)), (end_f, (0, length * 0.95, 0.6)), (T, (0, length * 0.55, 0.3))])
    ctx.card("LIKE DOMINOES", None, y_frac=0.17, size=0.055, appear=ctx.f(0.4))


def b_safety_tips(ctx, p):
    """Calm night-fog drive with lights on and a long '4 SEC' gap; tips tick in as they're spoken."""
    fog(0.028, FOG_NIGHT, start=5)
    setup_world(ctx.scene, FOG_NIGHT, 1.0)
    add_sun(0.9, (55, 0, 25), (0.8, 0.85, 1.0))
    road(length=1500, y0=-60)
    T = ctx.frames
    lx = lane_x(1)
    v = 15.0
    gapm = 4 * v
    cam = ctx.camera((lx + 1.6, -12, 4.6), target=(lx, 28, 0.8), lens=30)
    hero = make_car("hero", CAR_COLORS[0], (lx, 0, 0), 0, cam=cam)
    headlight_beams(hero, energy=2000)
    lead = make_car("lead", CAR_COLORS[2], (lx, gapm, 0), 0, cam=cam, brake_mat=emissive("tail_lead2", RED, 5.0),
                    brake_glow=True)
    brake_light(lead, 1, True, 6.0)
    ys = [v * f / ctx.fps for f in range(T)]
    drive(hero, [(lx, y) for y in ys])
    drive(lead, [(lx, gapm + y) for y in ys])
    f_gap = ctx.word_time("gap", 0.4)
    gr = bpy.data.objects.new("gapband", None)
    link(gr)
    for sx in (-1.9, 1.9):
        band = plane("band", 0.25, gapm - 4.4, (lx + sx, gapm / 2, 0.04), flat_mat("teal_flat", TEAL))
        band.parent = gr
        ctx._pop(band, f_gap, None)
    lbl = label3d(ctx, "4+ SEC", (lx + 4.0, gapm / 2, 2.0), 2.4, TEAL, appear=f_gap)
    lbl.parent = gr
    for f in range(1, T + 1, 3):
        kf(gr, "location", f, Vector((0, ys[f - 1], 0)))
        kf(cam, "location", f, Vector((lx + 1.6, ys[f - 1] - 12, 4.6)))
        kf(ctx.cam_target, "location", f, Vector((lx, ys[f - 1] + 28, 0.8)))
    tips = p.get("tips", [])
    cues = p.get("cues", ["slow", "gap", "headlights", "ease"])
    for i, tip in enumerate(tips):
        f = ctx.word_time(cues[i] if i < len(cues) else "", (i + 1) / (len(tips) + 1))
        ctx.text("%d  %s" % (i + 1, tip), 0.5, 0.16 + i * 0.077, 0.028, WHITE, FONT_PATH, appear=f,
                 panel=NAVY if i % 2 == 0 else hexc("0d3b4f"), max_w_frac=0.7)


BUILDERS = {
    "fog_highway": b_fog_highway,
    "chain_topdown": b_chain_topdown,
    "visibility": b_visibility,
    "stopping_distance": b_stopping_distance,
    "following_gap": b_following_gap,
    "ice_road": b_ice_road,
    "dominoes": b_dominoes,
    "safety_tips": b_safety_tips,
}

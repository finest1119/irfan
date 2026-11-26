"""Render profiles for the SME one-shot renderer (Session 13). Pure Python at import (the venv driver reads PROFILES);
bpy is only imported inside apply_fast(), which runs in Blender.

  default  the measured Build #1 setup, unchanged (render_oneshot never calls into this module for it)
  fast     Cycles 16 samples, adaptive threshold 0.06, lower bounces, Cycles motion blur OFF, 0.75 render scale,
           a cheaper kitchen nook; page2/tools/fast_post.py then upscales (Lanczos + mild unsharp) and adds the
           clamped 2D blur from camera_speed (oneshot_blur.blur_spec) into frames_oneshot/ at full res.

Grass and leaves are NOT thinned (rejected for look risk). Transparent bounces stay 8: grass/leaf cards are alpha
cut-outs and a lower cap darkens dense grass at grazing angles.
"""

PROFILES = {
    "default": {},
    "fast": {
        "samples": 16,               # used when --samples is not given on the command line
        "adaptive_threshold": 0.06,
        "res_factor": 0.75,          # render 810x1440 for a 1080x1920 final, fast_post upscales
        "mblur": "off",              # Cycles motion blur off; 2D blur in fast_post
        "raw_dir": "frames_oneshot_fast",   # raw low-res renders; fast_post writes frames_oneshot/ (full res)
        # (max, diffuse, glossy, transmission, transparent); default is (6, 3, 3, 4, 8)
        "bounces": (4, 2, 2, 2, 8),
        "clamp_indirect": 6.0,       # default 8.0: a little less firefly noise at 16 samples
    },
}

NAMES = tuple(PROFILES)


def get(name):
    if name not in PROFILES:
        raise ValueError("unknown render profile %r (have: %s)" % (name, ", ".join(NAMES)))
    return PROFILES[name]


# ---------------------------------------------------------------- Blender side
# kitchen nook glossy props -> rougher, no clear coat (roughness, coat weight, metallic or None = unchanged)
KITCHEN_MATS = {
    "mh_k_steel": (0.5, 0.0, None),
    "mh_k_steel_light": (0.5, 0.0, None),
    "mh_k_enamel": (0.5, 0.0, None),
    "mh_k_dark_glass": (0.35, 0.0, None),
    "mh_k_oak": (0.55, 0.0, None),
    "mh_k_walnut": (0.55, 0.0, None),
    "mh_kitchen_tile": (0.4, 0.0, None),
    "mh_fridge": (0.45, 0.0, None),
    "mh_butcher": (0.6, 0.0, None),
}


def _principled(mat):
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return []
    return [n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"]


def _set_input(node, name, value):
    try:
        node.inputs[name].default_value = value
        return True
    except Exception:
        return False


def simplify_kitchen(world, stats):
    """Cheaper kitchen behind the north window: rougher props without clear coat, and the ceiling area light folded
    into the (already present) emissive ceiling panel, so the nook has no explicit area light to shadow-sample.
    Brightness is set through the world's keyed light on-values (key_lights), not the material defaults."""
    import bpy
    n = 0
    for name, (rough, coat, metal) in KITCHEN_MATS.items():
        for p in _principled(bpy.data.materials.get(name)):
            n += _set_input(p, "Roughness", rough)
            if coat is not None:
                _set_input(p, "Coat Weight", coat)
            if metal is not None:
                _set_input(p, "Metallic", metal)
    stats["fast_kitchen_mats"] = n
    ent = getattr(world, "lights", {}).get("kitchen") if world is not None else None
    kl = bpy.data.lights.get("mh_kitchen_light")
    ceil = bpy.data.materials.get("mh_kitchen_ceiling")
    if not ent or kl is None or ceil is None:
        stats["fast_kitchen_light"] = "not found (kitchen unchanged)"
        return
    csock = _principled(ceil)[0].inputs["Emission Strength"] if _principled(ceil) else None
    area_on = 0.0
    for i, (owner, prop, on, off) in enumerate(ent):
        if owner == kl and prop == "energy":
            area_on = on
            ent[i] = (owner, prop, 0.0, 0.0)
    # area light power P over area A ~ emission strength P / (pi * A); spread over the ceiling panel
    a_panel = 3.9 * 2.5
    boost = area_on / (3.14159 * a_panel) * FAST_KITCHEN_GAIN
    for i, (owner, prop, on, off) in enumerate(ent):
        if csock is not None and owner == csock:
            ent[i] = (owner, prop, on + boost, off)
    klo = bpy.data.objects.get("mh_kitchen_light")
    if klo is not None:
        klo.hide_render = True
    stats["fast_kitchen_light"] = "area %.0f W -> ceiling emission +%.2f" % (area_on, boost)


FAST_KITCHEN_GAIN = 1.2          # s13 Mac A/B: window crop mean matches default within ~1 %


def setup_cycles_fast(scene, prof, stats):
    cy = scene.cycles
    cy.adaptive_threshold = prof["adaptive_threshold"]
    (cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces,
     cy.transparent_max_bounces) = prof["bounces"]
    cy.sample_clamp_indirect = prof["clamp_indirect"]
    stats["fast_bounces"] = list(prof["bounces"])
    stats["adaptive_threshold"] = prof["adaptive_threshold"]


def apply_fast(scene, world, stats, engine):
    """Called by render_oneshot after the world + characters are built and BEFORE the world events are keyed."""
    prof = PROFILES["fast"]
    if engine != "eevee":
        setup_cycles_fast(scene, prof, stats)
    try:
        simplify_kitchen(world, stats)
    except Exception as ex:          # never fail a render over the fast-path tweaks
        import traceback
        traceback.print_exc()
        stats["fast_kitchen_light"] = "FAILED: %s" % ex
    print("[oneshot] fast profile: %s" % {k: v for k, v in stats.items() if k.startswith("fast_")})


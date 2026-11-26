"""One-shot render of a Self-Made Engineer reel: ONE scene, ONE camera, driven by the episode beats. Needs Blender.

Usually run through the driver (one Blender process at a time, resumable, <= 150-frame jobs):
  python page2/tools/oneshot.py still  EPISODE WORKDIR --frames 40,700 --scale 0.35 --samples 8
  python page2/tools/oneshot.py render EPISODE WORKDIR --range 1-600
Direct:
  BLENDER -b --factory-startup -P page2/blender/render_oneshot.py -- EPISODE WORKDIR
        [--range A-B | --still F[,F...]] [--scale 0.35] [--samples 16] [--engine cycles|eevee]
        [--parts terrain,house,...] [--mblur 2d|3d|off] [--save-blend] [--profile default|fast] [--warmup]
--profile fast (s13, render_profiles.py): 0.75 render scale into WORKDIR/frames_oneshot_fast/, 16 samples, lower
bounces, Cycles motion blur off, cheaper kitchen; page2/tools/fast_post.py makes the full-res frames_oneshot/.

Reads  WORKDIR/oneshot/plan.json (written by the driver; recomputed here if missing), episode.json, world_state.json.
Writes WORKDIR/frames_oneshot/####.jpg (GLOBAL frame numbers; existing frames are skipped),
       WORKDIR/tracks_v2/NN_<beat>_A-B.json (beat-local frames, overlay_v2.load_anchors format),
       WORKDIR/stills_oneshot/f####.png with --still, WORKDIR/oneshot/stats_<A>-<B>.json.
Only the job's frames (+2 margin) get camera/character keys, so a job builds fast; the world is built once per
job with persistent data ON (BVH reused frame to frame).
"""
import json
import os
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mh_paths as MP  # noqa: E402

MP.add_import_paths(blender=True)
import mh_blender as B  # noqa: E402
from mh_blender import S, L  # noqa: E402
import camera_plan as CP  # noqa: E402
import worlds as WR  # noqa: E402
import render_profiles as RP  # noqa: E402


def args():
    argv = sys.argv[sys.argv.index("--") + 1:]

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    return argv, opt


def setup_render(scene, res, fps, frames, samples, engine, out_dir):
    """v2 colour management + bloom (S.setup_render_v2), then Cycles + OptiX/Metal, adaptive sampling, denoise,
    persistent data and a 2K texture cap (4 GB VRAM budget, PROPOSAL 7.3)."""
    S.setup_render_v2(scene, res, fps, frames, samples, out_dir, fmt="JPEG")
    if engine == "eevee":
        return "eevee"
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    dev = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except Exception:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                dev = kind
                break
    except Exception as ex:
        print("[oneshot] GPU setup failed (%s); CPU render" % ex)
    cy.device = "GPU" if dev != "CPU" else "CPU"
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.04
    cy.use_denoising = True
    try:
        cy.denoiser = "OPTIX" if dev == "OPTIX" else "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 3, 3
    cy.transmission_bounces, cy.transparent_max_bounces = 4, 8
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.sample_clamp_indirect = 8.0
    try:
        cy.texture_limit_render = "2048"
    except Exception:
        pass
    scene.render.use_persistent_data = True
    print("[oneshot] Cycles on %s, %d samples, persistent data ON" % (dev, samples))
    return dev


# ------------------------------------------------------------------ camera
WORLD_ROOT = "WORLD_ROOT"


def world_root():
    """The world's root empty (Page 3 rebase keys its location); created at the origin when the world has none.
    Camera, target and Spark are its children, so plan coordinates are WORLD_ROOT-local and a rebase moves them
    together with the world (the image does not change at the switch)."""
    r = bpy.data.objects.get(WORLD_ROOT)
    if r is None:
        r = L.link(bpy.data.objects.new(WORLD_ROOT, None))
        r.empty_display_size = 1.0
    return r


def make_camera(ctx, plan, lo, hi):
    cd = bpy.data.cameras.new("MH_Cam")
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = CP.SENSOR_H_MM
    cd.clip_start, cd.clip_end = 0.1, 20000.0
    cam = L.link(bpy.data.objects.new("MH_Cam", cd))
    tgt = L.link(bpy.data.objects.new("MH_CamTarget", None))
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    root = world_root()
    cam.parent = tgt.parent = root          # identity parent inverse: keys below are root-local
    ctx.scene.camera = cam
    ctx.cam, ctx.cam_target = cam, tgt
    fr = list(range(max(1, lo), min(plan["frames"], hi) + 1))
    rows = [plan["cam"][f] for f in fr]
    B.set_keys(cam, "location", fr, [r[0:3] for r in rows])
    B.set_keys(tgt, "location", fr, [r[3:6] for r in rows])
    B.set_keys(cd, "lens", fr, [r[6] for r in rows])
    return cam


def render_views(ctx, scene, stdir, path):
    """Still-only QC views off the camera plan (s7): a JSON list of {"f", "tag", "anchor"?, "pos", "look", "lens"}.
    With "anchor", pos/look are offsets from that anchor's world position at frame f; without, world coordinates.
    The plan camera keys are removed for these renders (the still run ends here), so it never touches a reel."""
    from mathutils import Vector
    views = json.loads(Path(path).read_text(encoding="utf-8"))
    cam, tgt = ctx.cam, ctx.cam_target
    for o in (cam, tgt, cam.data):
        o.animation_data_clear()
    cam.parent = tgt.parent = None
    for v in views:
        scene.frame_set(int(v["f"]))
        base = Vector((0.0, 0.0, 0.0))
        if v.get("anchor"):
            a = bpy.data.objects.get(B.ANC_PREFIX + v["anchor"])
            if a is None:
                print("[oneshot] view %s: no anchor %s, skipped" % (v.get("tag"), v["anchor"]))
                continue
            base = a.matrix_world.translation.copy()
        cam.location = base + Vector(v["pos"])
        tgt.location = base + Vector(v["look"])
        cam.data.lens = float(v.get("lens", 50.0))
        bpy.context.view_layer.update()
        scene.render.filepath = str(stdir / ("f%04d%s.png" % (int(v["f"]), v.get("tag", "_view"))))
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print("[oneshot] view f%d%s %.1fs" % (int(v["f"]), v.get("tag", ""), time.time() - t1))


def key_motion_blur(scene, plan, lo, hi, mode):
    """3d: Cycles/EEVEE motion blur only inside blur windows (snaps). 2d: off (overlay blurs from camera_speed)."""
    scene.render.use_motion_blur = False
    if mode != "3d":
        return
    scene.render.motion_blur_shutter = 0.5
    keys = [(lo, False)]
    for w in plan["windows"]:
        if w["blur"] and w["f1"] >= lo and w["f0"] <= hi:
            keys += [(w["f0"], True), (w["f1"] + 1, False)]
    try:
        B.key_const(scene.render, "use_motion_blur", sorted(keys))
    except Exception as ex:          # not animatable in this build -> per-frame handler
        print("[oneshot] motion blur keys failed (%s); using a frame handler" % ex)
        on = set()
        for w in plan["windows"]:
            if w["blur"]:
                on.update(range(w["f0"], w["f1"] + 1))

        def h(sc, *_a):
            sc.render.use_motion_blur = sc.frame_current in on
        bpy.app.handlers.frame_change_pre.append(h)


# ------------------------------------------------------------------ plan events -> keys
def apply_world_events(world, plan, lo, hi):
    if world is None:
        return
    for kind in ("preset", "section", "lights"):
        evs = [e for e in plan["events"] if e["kind"] == kind]
        if kind == "lights":
            state = {}
            for e in evs:
                if e["f"] <= lo:
                    state.update(e["value"])
            if hasattr(world, "key_lights"):
                full = {k: False for k in world.lights}
                full.update(state)
                world.key_lights(lo, full)
            for e in evs:
                if lo < e["f"] <= hi + 2:
                    world.key_lights(e["f"], e["value"])
            continue
        cur = CP.state_at(plan, kind, lo, "day" if kind == "preset" else None)
        fn = world.key_preset if kind == "preset" else world.key_section
        if kind == "section" and not getattr(world, "sections", None):
            continue
        fn(lo, cur)
        for e in evs:
            if lo < e["f"] <= hi + 2:
                fn(e["f"], e["value"])


def build_events(plan, episode):
    """Frames for the Build #1 stub's assemble timeline (tilt, spin, furl, stop, ghost), from the beats' moves.
    An entry in episode.builds_in_episode may override any of them with explicit global frames."""
    fps = plan["fps"]
    first = {}
    for w in plan["windows"]:
        first.setdefault(w["beat"], w)
    out = {}
    for e in episode.get("builds_in_episode", []):
        ev = {}
        if "hack1" in first:
            ev["tilt_start"] = first["hack1"]["f1"] + int(0.5 * fps)
            ev["tilt_end"] = ev["tilt_start"] + int(4.0 * fps)
            ev["spin_start"] = ev["tilt_end"] + int(0.8 * fps)
        if "snag2" in first:
            ev["fast"] = first["snag2"]["f1"]
        if "hack2" in first:
            ev["furl"] = first["hack2"]["f1"] + int(0.5 * fps)
            ev["slow"] = ev["furl"] + int(1.5 * fps)
        if "teaser" in first:
            ev["stop"] = first["teaser"]["f1"] + int(1.0 * fps)
        if "mission" in first and "how" in first:
            ev["ghost"] = (first["mission"]["mid"], first["how"]["mid"])
        ev.update(e.get("events", {}))
        out[e["id"]] = ev
    return out


# ------------------------------------------------------------------ 2D-overlay tracks (per beat, beat-local frames)
def export_tracks(ctx, plan, workdir, a, b):
    from bpy_extras.object_utils import world_to_camera_view
    anchors = getattr(ctx, "anchors", {})
    if not anchors:
        return []
    sc = ctx.scene
    tdir = Path(workdir) / "tracks_v2"
    tdir.mkdir(parents=True, exist_ok=True)
    written = []
    for bt in plan["beats"]:
        g0, g1 = bt["f0"], bt["f0"] + bt["frames"] - 1
        lo, hi = max(a, g0), min(b, g1)
        if lo > hi:
            continue
        la, lb = lo - g0 + 1, hi - g0 + 1
        path = tdir / ("%02d_%s_%04d-%04d.json" % (bt["idx"], bt["id"], la, lb))
        if path.exists():
            continue
        out = {n: [] for n in anchors}
        for f in range(lo, hi + 1):
            sc.frame_set(f)
            for n, (o, off) in anchors.items():
                c = world_to_camera_view(sc, sc.camera, o.matrix_world @ off)
                out[n].append([round(c.x * 1080, 2), round((1 - c.y) * 1920, 2), 1 if c.z > 0 else 0])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"f0": la, "f1": lb, "w": 1080, "h": 1920, "anchors": out}), encoding="utf-8")
        os.replace(str(tmp), str(path))
        written.append(path.name)
    return written


def vram_estimate(stats):
    """Rough scene-memory estimate (NOT a measurement): images (w*h*4 B, capped at 2K) + unique mesh tris (~150 B)."""
    img = 0
    for im in bpy.data.images:
        if im.size[0] and im.users:
            w, h = min(im.size[0], 2048), min(im.size[1], 2048)
            img += w * h * 4 * (2 if im.is_float else 1)
    tris = 0
    for me in bpy.data.meshes:
        if me.users:
            tris += sum(len(p.vertices) - 2 for p in me.polygons)
    stats["est_images_mb"] = round(img / 1e6, 1)
    stats["unique_mesh_tris"] = tris
    stats["est_geometry_mb"] = round(tris * 150 / 1e6, 1)
    stats["objects"] = len(bpy.data.objects)
    return stats


# ------------------------------------------------------------------ main
def load_plan(episode, workdir, ws):
    """(plan, expanded episode). Same resolution as the driver (worlds.plan_inputs: registry + compact oneshot
    adapter); plan.json from the driver wins when present."""
    ep, loc, hf, extra, _info = WR.plan_inputs(episode, Path(workdir), ws)
    p = Path(workdir) / "oneshot" / "plan.json"
    if p.exists():
        return MP.load_json(p), ep
    tm = MP.load_json(Path(workdir) / "audio" / "timings.json")
    cp = Path(workdir) / "captions.json"
    words = MP.load_json(cp)["words"] if cp.exists() else []
    plan, _speed = CP.build_plan(ep, tm, words, loc, hf, extra_anchors=extra)
    return plan, ep


def make_spark(ctx, plan, lo, hi):
    """The Spark (shared with Page 3): emissive UV sphere on plan["spark"]["track"] ([x, y, z, radius] per frame),
    colour keyed per event with a 0.5 s blend. Unit-radius mesh scaled per frame (radius 0 = hidden)."""
    sp = plan.get("spark")
    if not sp:
        return None
    import bmesh
    me = bpy.data.meshes.new("ED_Spark")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    orb = L.link(bpy.data.objects.new("ED_Spark", me))
    mat = bpy.data.materials.new("ED_Spark")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    em.inputs["Strength"].default_value = 12.0 if ctx.scene.render.engine == "CYCLES" else 25.0
    me.materials.append(mat)
    orb.visible_shadow = False
    orb.parent = world_root()
    fr = list(range(max(1, lo), min(plan["frames"], hi) + 1))
    rows = [sp["track"][f] for f in fr]
    B.set_keys(orb, "location", fr, [r[0:3] for r in rows])
    B.set_keys(orb, "scale", fr, [(max(r[3], 1e-5),) * 3 for r in rows])
    cols, blend = sp["colors"], max(1, int(round(sp.get("blend_s", 0.5) * plan["fps"])))
    keys, prev = [], None
    for e in sp["events"]:
        c = cols.get(e["value"])
        if c is None:                  # 'off': keep the colour, the radius fades
            continue
        rgba = tuple(c) + (1.0,)
        if prev is None:
            keys.append((1, rgba))
        else:
            keys += [(e["f"], prev), (e["f"] + blend, rgba)]
        prev = rgba
    if keys:
        B.set_keys(em.inputs["Color"], "default_value", [k[0] for k in keys], [k[1] for k in keys])
    return orb


def write_anchor_cache(ctx, workdir, world_id, frame):
    """WORKDIR/oneshot/anchors_<world>.json: world positions of every ANC_/CAM_ empty at `frame` (plan-time
    fallback for worlds without a bpy-free plan_anchors)."""
    ctx.scene.frame_set(frame)
    anc, cams = {}, {}
    root = bpy.data.objects.get(WORLD_ROOT)
    inv = root.matrix_world.inverted() if root is not None else None
    for o in bpy.data.objects:
        if o.type != "EMPTY":
            continue
        m = (inv @ o.matrix_world) if inv is not None else o.matrix_world      # root-local = plan coordinates
        p = [round(v, 6) for v in m.translation]
        if o.name.startswith(B.ANC_PREFIX):
            anc[o.name[len(B.ANC_PREFIX):]] = p
        elif o.name.startswith(B.CAM_PREFIX):
            cams[o.name[len(B.CAM_PREFIX):]] = {"pos": p, "lens": o.get("lens", 28.0)}
    d = Path(workdir) / "oneshot"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("anchors_%s.json" % world_id)).write_text(json.dumps({"frame": frame, "anchors": anc, "cams": cams},
                                                               indent=1), encoding="utf-8")
    return len(anc)


def warmup(scene, stdir, f, engine):
    scene.frame_set(f)
    if engine == "eevee":
        keep, scene.eevee.taa_render_samples = scene.eevee.taa_render_samples, 1
    else:
        keep, scene.cycles.samples = scene.cycles.samples, 1
    scene.render.filepath = str(stdir / "_warmup.png")
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    if engine == "eevee":
        scene.eevee.taa_render_samples = keep
    else:
        scene.cycles.samples = keep
    try:
        os.remove(str(stdir / "_warmup.png"))
    except OSError:
        pass
    print("[oneshot] warmup f%d %.1fs" % (f, time.time() - t1))


def main():
    argv, opt = args()
    ep_path, workdir = argv[0], argv[1]
    ws = MP.world_state()
    world_id = WR.world_id_of(MP.load_json(ep_path))
    plan, episode = load_plan(MP.load_json(ep_path), workdir, ws)      # episode = adapter-expanded copy
    page2_world = world_id == "mercer_hollow" or (world_id not in WR.WORLDS and WR.is_page2_location(world_id, ws))
    loc_name = episode["beats"][0].get("shot", {}).get("location", world_id)
    loc = MP.location(ws, loc_name) if page2_world else {}
    interior = episode.get("interior")
    fps = plan["fps"]
    rcfg = episode.get("render", {})
    res = rcfg.get("resolution", [1080, 1920])
    scale = float(opt("--scale", 1.0))
    samples = int(opt("--samples", rcfg.get("samples", 16)))
    engine = opt("--engine", rcfg.get("engine", "cycles"))
    profile = opt("--profile", "default")
    prof = RP.get(profile)
    fast = profile == "fast"
    parts = [p for p in opt("--parts", "").split(",") if p] or None
    still = opt("--still")
    if still:
        frames = [int(x) for x in still.split(",")]
        a, b = min(frames), max(frames)
    elif opt("--range"):
        a, b = [int(x) for x in opt("--range").split("-")]
    else:
        a, b = 1, plan["frames"]
    b = min(b, plan["frames"])
    lo, hi = max(1, a - 2), min(plan["frames"], b + 2)

    t0 = time.time()
    scene = L.reset_scene()
    B.reset_caches()
    out_dir = str(Path(workdir) / prof.get("raw_dir", "frames_oneshot"))
    rf = scale * prof.get("res_factor", 1.0)
    dev = setup_render(scene, (int(res[0] * rf), int(res[1] * rf)), fps, plan["frames"], samples, engine, out_dir)
    ctx = L.Ctx(scene, plan["frames"], fps, [], 0.0)
    ctx.anchors = {}
    ctx.plan, ctx.fps, ctx.frame_range = plan, fps, (a, b)
    ctx.build_events = build_events(plan, episode)
    stats = {"range": [a, b], "device": dev, "engine": engine, "scale": scale, "samples": samples}
    if fast:
        stats.update({"profile": profile, "render_res": [int(res[0] * rf), int(res[1] * rf)]})

    # episode static anchors first (builds/characters override names they also define)
    B.part_collection("anchors")
    ea = episode.get("anchors")
    for k, p in (ea.items() if isinstance(ea, dict) else []):
        B.anchor_empty(ctx, k, tuple(p))

    world, wmod, wstate = None, None, None
    if interior:
        import interiors as I
        I.build_room(ctx, loc, interior)
    else:
        focus = []
        for w in plan["windows"]:
            r = plan["cam"][w["f1"]]
            focus.append((r[3], r[4]))
            focus.append((r[0], r[1]))
        r = plan["cam"][1]
        focus.append((r[3], r[4]))
        # world registry (worlds.py): page2 trips/locations other than registered worlds use Mercer's builder
        wmod, build_fn = WR.build_entry(world_id if world_id in WR.WORLDS or not page2_world else "mercer_hollow")
        wstate = {"world_id": world_id, "episode": episode, "plan": plan, "workdir": str(workdir), "parts": parts,
                  "focus": focus, "frame_range": (a, b), "world_state": ws if page2_world else None}
        anchors = build_fn(ctx, wstate) or {}
        for k, o in anchors.items():          # contract: returned ANC_ empties ARE the track anchors
            if k not in ctx.anchors:
                S.anchor(ctx, k, o)
        world = wstate.get("world")
        stats.update(getattr(world, "stats", {}) or {})
        stats["world"], stats["world_anchors"] = world_id, len(anchors)
    chars = {}
    if not page2_world:
        pass                                   # characters (Bolts/Torque) belong to Page 2 worlds only
    elif parts is None or "characters" in parts:
        import characters as CH
        cj = MP.load_json(MP.CHARACTER)
        try:
            chars["bolts"] = CH.build_bolts(ctx, cj["bolts"])
            chars["torque"] = CH.build_torque(ctx, cj["torque_goose"])
            stats["bolts_tris_all_outfits"] = chars["bolts"]["tris_all_outfits"]
            stats["torque_tris"] = chars["torque"]["tris"]
            stats["bolts_impl"] = chars["bolts"].get("impl", "?")
            if chars["bolts"].get("tris_visible"):
                stats["bolts_tris_visible"] = chars["bolts"]["tris_visible"]
            CH.apply_cast(ctx, world, chars, plan, lo, hi, episode)
            if "--clip-actions" in argv:
                if chars["bolts"].get("make_clip_actions"):
                    chars["bolts"]["make_clip_actions"]()
                else:
                    CH.make_clip_actions(chars["bolts"]["rig"], CH.bolts_pose, {"idle": 90, "walk": 32, "point": 40,
                                         "thumbs_up": 36, "winch_crank": 40, "hands_on_hips": 48, "scratch_beard": 54})
                CH.make_clip_actions(chars["torque"]["rig"], CH.torque_pose, {"waddle": 24, "idle": 60, "honk": 30, "peck": 33})
        except Exception:
            import traceback
            traceback.print_exc()
            print("[oneshot] CHARACTERS FAILED (continuing without)")
    elif world is not None and "props" in (parts or []):
        import characters as CH
        CH.apply_cast(ctx, world, {}, plan, lo, hi, episode)
    make_camera(ctx, plan, lo, hi)
    if page2_world:
        stats["fog_relinked_after_chars"] = B.relink_fog_to_group()     # characters' materials join the keyed haze
    if fast:                                   # before the world events: they key the (fast) light on-values
        RP.apply_fast(scene, world, stats, engine)
    B.normalize_anchors(ctx)
    for w in plan["windows"]:              # <stop>__detail/__alt the world did not register: ANC_ at the stop's anchor
        base, var = CP.split_variant(w.get("to"))
        if var and w["to"] not in ctx.anchors and base in ctx.anchors:
            B.anchor_empty(ctx, w["to"], (0.0, 0.0, 0.0), parent=ctx.anchors[base][0])
    try:
        stats["anchors_cached"] = write_anchor_cache(ctx, workdir, world_id, lo)
    except Exception as ex:
        print("[oneshot] anchor cache not written: %s" % ex)

    def world_events():
        if wmod is not None and hasattr(wmod, "apply_events") and not page2_world:
            wmod.apply_events(wstate, plan, lo, hi)          # registered worlds key their own lids/peels/rebase
        else:
            apply_world_events(world, plan, lo, hi)
    for label, fn in (("world events", world_events),
                      ("spark", lambda: make_spark(ctx, plan, lo, hi)),
                      ("motion blur", lambda: key_motion_blur(scene, plan, lo, hi,
                                                              prof.get("mblur") or opt("--mblur", "2d")))):
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            print("[oneshot] %s keying FAILED (continuing)" % label)
    stats["t_build_total"] = round(time.time() - t0, 1)
    vram_estimate(stats)
    print("[oneshot] built in %.1fs: %s" % (time.time() - t0, json.dumps(stats)))
    sdir = Path(workdir) / "oneshot"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / ("stats_%04d-%04d.json" % (a, b))).write_text(json.dumps(stats, indent=1), encoding="utf-8")

    if still:
        stdir = Path(opt("--still-dir")) if opt("--still-dir") else Path(workdir) / "stills_oneshot"
        stdir.mkdir(parents=True, exist_ok=True)
        scene.render.image_settings.file_format = "PNG"
        if "--warmup" in argv:                 # bench: sync the scene to the device once so frame 1 is comparable
            warmup(scene, stdir, frames[0], engine)
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = str(stdir / ("f%04d%s.png" % (f, opt("--tag", ""))))
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print("[oneshot] still f%d %.1fs" % (f, time.time() - t1))
        if opt("--views"):
            render_views(ctx, scene, stdir, opt("--views"))
        if "--save-blend" in argv:
            bpy.ops.wm.save_as_mainfile(filepath=str(stdir / ("oneshot_f%04d.blend" % frames[0])), relative_remap=True)
            try:                                   # s6: every texture path relative (the .blend opens on Windows)
                bpy.ops.file.make_paths_relative()
                bpy.ops.wm.save_mainfile()
            except Exception as ex:
                print("[oneshot] make_paths_relative failed: %s" % ex)
        return
    written = export_tracks(ctx, plan, workdir, a, b)
    print("[oneshot] tracks: %s" % (", ".join(written) or "none new"))
    if "--anchors-only" in argv:
        return
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = out_dir + os.sep
    scene.frame_start, scene.frame_end = a, b
    scene.render.use_overwrite = False
    scene.render.use_placeholder = False
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    dt = time.time() - t1
    print("[oneshot] rendered %d-%d: %d frames in %.1fs (%.2fs/frame)" % (a, b, b - a + 1, dt, dt / max(1, b - a + 1)))


main()

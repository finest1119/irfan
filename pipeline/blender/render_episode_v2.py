"""Render one shot (beat) of a v2 episode with Blender, headless. (v1 episodes use render_episode.py.)

Usage:
  Blender -b --factory-startup -P pipeline/blender/render_episode_v2.py -- \
      EPISODE_JSON WORKDIR SHOT_INDEX [--range A-B] [--still F[,F...]] [--scale 0.5] [--samples N] [--tag x]

Reads  WORKDIR/audio/timings.json, WORKDIR/captions.json (ctx.word_time()), WORKDIR/tex_v2/ (PIL textures).
Writes WORKDIR/frames_v2/<NN>_<beat>/####.jpg      (only frames A..B with --range; existing frames are skipped)
       WORKDIR/tracks_v2/<NN>_<beat>_<A>-<B>.json  (2D-overlay anchors, if the builder registered any)
       WORKDIR/stills_v2/<NN>_<beat>_f####.png      with --still.

v2 rules: builders never create 3D text (all text = 2D overlays in pipeline/overlay_v2.py); every outdoor shot
uses S.daylight() (HDRI sky). A shot may set "render_scale" (e.g. 0.5 for plates that the overlay blurs).
"""
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L  # noqa: E402
import scene_lib_v2 as S  # noqa: E402


def load_builders():
    import scene_lib_v2_air  # noqa: F401  (registers into S.V2_BUILDERS)
    import scene_lib_v2_city  # noqa: F401
    import scene_lib_v2_market  # noqa: F401
    import scene_lib_v2_travel  # noqa: F401
    import scene_lib_v2_winter  # noqa: F401
    return S.V2_BUILDERS


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ep_path, workdir, idx = argv[0], argv[1], int(argv[2])

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    ep = json.load(open(ep_path))
    timings = json.load(open(os.path.join(workdir, "audio", "timings.json")))["beats"]
    caps_path = os.path.join(workdir, "captions.json")
    words = json.load(open(caps_path))["words"] if os.path.exists(caps_path) else []
    beat, tm = ep["beats"][idx], timings[idx]
    assert beat["id"] == tm["id"], "timings out of sync with episode.json"
    rcfg = ep.get("render", {})
    fps = int(rcfg.get("fps", 30))
    res = rcfg.get("resolution", [1080, 1920])
    shot = beat["shot"]
    params = shot.get("params", {})
    scale = float(opt("--scale", shot.get("render_scale", 1.0)))
    samples = int(opt("--samples", shot.get("samples", rcfg.get("samples", 24))))
    frames = int(round(tm["duration"] * fps))
    name = "%02d_%s" % (idx, beat["id"])

    scene = L.reset_scene()
    L._MATS.clear()
    S._MV2.clear()
    S.TEX["dir"] = os.path.join(workdir, "tex_v2")
    out_dir = os.path.join(workdir, "frames_v2", name)
    S.setup_render_v2(scene, (int(res[0] * scale), int(res[1] * scale)), fps, frames, samples, out_dir, fmt="JPEG")
    beat_words = [w for w in words if w.get("beat") == beat["id"]]
    ctx = L.Ctx(scene, frames, fps, beat_words, tm["start"])
    ctx.anchors = {}
    ctx.params = params
    builders = load_builders()
    if shot["builder"] not in builders:
        raise SystemExit("unknown v2 builder %r (v2 builders: %s)" % (shot["builder"], ", ".join(sorted(builders))))
    t0 = time.time()
    builders[shot["builder"]](ctx, params)
    print("[render_v2] built %s (%s) in %.1fs, %d frames, %d objects" % (
        name, shot["builder"], time.time() - t0, frames, len(bpy.data.objects)))

    still = opt("--still")
    if still:
        sdir = os.path.join(workdir, "stills_v2")
        os.makedirs(sdir, exist_ok=True)
        scene.render.image_settings.file_format = "PNG"
        for fr in [int(x) for x in still.split(",")]:
            scene.frame_set(min(fr, frames))
            scene.render.filepath = os.path.join(sdir, "%s_f%04d%s.png" % (name, fr, opt("--tag", "")))
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print("[render_v2] still %s f%d %.2fs" % (name, fr, time.time() - t1))
        if "--save-blend" in argv:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(sdir, name + ".blend"))
        return

    a, b = 1, frames
    if opt("--range"):
        a, b = [int(x) for x in opt("--range").split("-")]
        b = min(b, frames)
    if ctx.anchors:
        tdir = os.path.join(workdir, "tracks_v2")
        os.makedirs(tdir, exist_ok=True)
        tp = os.path.join(tdir, "%s_%04d-%04d.json" % (name, a, b))
        if not os.path.exists(tp):
            t1 = time.time()
            S.export_anchors(ctx, tp + ".tmp", a, b)
            os.replace(tp + ".tmp", tp)
            print("[render_v2] anchors %s in %.1fs" % (os.path.basename(tp), time.time() - t1))
    if "--anchors-only" in argv:
        return
    os.makedirs(out_dir, exist_ok=True)
    scene.frame_start, scene.frame_end = a, b
    scene.render.use_overwrite = False
    scene.render.use_placeholder = False
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    dt = time.time() - t1
    n = b - a + 1
    print("[render_v2] rendered %s %d-%d: %d frames in %.1fs (%.2fs/frame)" % (name, a, b, n, dt, dt / max(1, n)))


main()

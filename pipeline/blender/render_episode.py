"""Render one shot (beat) of an episode with Blender, headless.

Usage:
  Blender -b --factory-startup -P pipeline/blender/render_episode.py -- \
      EPISODE_JSON WORKDIR SHOT_INDEX [--still FRAME[,FRAME...]] [--scale 0.5] [--samples N] [--frames N]

Reads  WORKDIR/audio/timings.json (shot durations) and WORKDIR/captions.json (word times, so
       builders can sync on-screen events to spoken words via ctx.word_time()).
Writes WORKDIR/frames/<NN>_<beat_id>/####.png  (animation; existing frames are skipped = resumable)
       or WORKDIR/stills/<NN>_<beat_id>_f<FRAME>.png with --still.
"""
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L  # noqa: E402


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
    scale = float(opt("--scale", 1.0))
    samples = int(opt("--samples", rcfg.get("samples", 8)))
    frames = int(round(tm["duration"] * fps))
    if opt("--frames"):
        frames = min(frames, int(opt("--frames")))
    name = "%02d_%s" % (idx, beat["id"])

    scene = L.reset_scene()
    L._MATS.clear()
    still = opt("--still")
    out_dir = os.path.join(workdir, "frames", name)
    L.setup_render(scene, (int(res[0] * scale), int(res[1] * scale)), fps, frames, samples, out_dir)
    beat_words = [w for w in words if w.get("beat") == beat["id"]]
    ctx = L.Ctx(scene, frames, fps, beat_words, tm["start"])
    builder = L.BUILDERS[beat["shot"]["builder"]]
    t0 = time.time()
    builder(ctx, beat["shot"].get("params", {}))
    print("[render_episode] built %s (%s) in %.1fs, %d frames" % (name, beat["shot"]["builder"], time.time() - t0, frames))

    if still:
        sdir = os.path.join(workdir, "stills")
        os.makedirs(sdir, exist_ok=True)
        for fr in [int(x) for x in still.split(",")]:
            scene.frame_set(min(fr, frames))
            scene.render.filepath = os.path.join(sdir, "%s_f%04d.png" % (name, fr))
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print("[render_episode] still %s f%d %.2fs" % (name, fr, time.time() - t1))
        if "--save-blend" in argv:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(sdir, name + ".blend"))
        return

    os.makedirs(out_dir, exist_ok=True)
    scene.render.use_overwrite = False
    scene.render.use_placeholder = False
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    dt = time.time() - t1
    print("[render_episode] rendered %s: %d frames in %.1fs (%.2fs/frame)" % (name, frames, dt, dt / max(1, frames)))


main()

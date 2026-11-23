"""Blender entry for the v2 look-dev test shot (does not touch render_episode.py or any v1 builder).

Usage:
  Blender -b --factory-startup -P pipeline/blender/render_v2_test.py -- \
      OUT_DIR TEX_DIR CAPTIONS_JSON DURATION_S [--range A-B] [--still F,F] [--scale 0.5] [--samples N] [--track PATH]
Frames -> OUT_DIR/frames/####.png (resumable), stills -> OUT_DIR/stills/, track JSON -> PATH.
"""
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L  # noqa: E402
import scene_lib_v2 as S  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_dir, tex_dir, caps, dur = argv[0], argv[1], argv[2], float(argv[3])

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    fps = 30
    frames = int(round(dur * fps))
    scale = float(opt("--scale", 1.0))
    samples = int(opt("--samples", 24))
    words = [w for w in json.load(open(caps))["words"] if w.get("beat") == "hook"]
    scene = L.reset_scene()
    L._MATS.clear()
    S._MV2.clear()
    S.TEX["dir"] = tex_dir
    fdir = os.path.join(out_dir, "frames")
    S.setup_render_v2(scene, (int(1080 * scale), int(1920 * scale)), fps, frames, samples, fdir)
    ctx = L.Ctx(scene, frames, fps, words, 0.0)
    t0 = time.time()
    params = json.loads(opt("--params", "{}"))
    plane = S.b_airport_approach_v2(ctx, params)
    print("[v2] built scene in %.1fs, %d objects" % (time.time() - t0, len(bpy.data.objects)))
    if opt("--track"):
        S.export_track(ctx, plane, opt("--track"))
        print("[v2] track written", opt("--track"))
        return
    if opt("--still"):
        sdir = os.path.join(out_dir, "stills")
        os.makedirs(sdir, exist_ok=True)
        for fr in [int(x) for x in opt("--still").split(",")]:
            scene.frame_set(fr)
            scene.render.filepath = os.path.join(sdir, "v2_f%04d%s.png" % (fr, opt("--tag", "")))
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print("[v2] still f%d %.2fs" % (fr, time.time() - t1))
        return
    if opt("--range"):
        a, b = [int(x) for x in opt("--range").split("-")]
        scene.frame_start, scene.frame_end = a, min(b, frames)
    os.makedirs(fdir, exist_ok=True)
    scene.render.use_overwrite = False
    scene.render.use_placeholder = True
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    dt = time.time() - t1
    n = scene.frame_end - scene.frame_start + 1
    print("[v2] rendered %d frames in %.1fs (%.2fs/frame)" % (n, dt, dt / max(1, n)))


main()

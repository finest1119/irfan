"""Render ONE full-res still (1080x1920, the episode's own EEVEE settings) from a v2 episode beat, for thumbnails.

Thin wrapper over pipeline/blender/render_episode_v2.py --still (+ the opt-in hero-camera flags). Refuses to start
while another Blender process is running (shared 16 GB Mac) unless --wait is given, which polls every 60 s (max 30 min).

Usage:
  .venv/bin/python tools/render_hero_frame.py EPISODE_DIR BEAT FRAME [--zoom 1.3] [--dolly 0] [--shift x,y]
                   [--samples N] [--tag _hero] [--wait] [--workdir output/<slug>] [--out path.png]
  BEAT = beat id (e.g. one_chimney) or index; FRAME = frame number inside that beat (see stills_v2 names).
  e.g. .venv/bin/python tools/render_hero_frame.py episodes/2026-11-26-3-high-rise-fire one_chimney 377 --zoom 1.25

Output: WORKDIR/stills_v2/<NN>_<beat>_f####<tag>.png (copied to --out if given). Workdir defaults to output/<slug>.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import platform_cfg as PC  # noqa: E402


def blender_busy():
    # Match only real Blender executables (macOS app binary or a "blender" exe), never shells/tools whose
    # command line merely mentions "Blender" (that used to block every hero render).
    r = subprocess.run(["pgrep", "-fl", "Blender"], capture_output=True, text=True)
    out = []
    for ln in r.stdout.splitlines():
        parts = ln.split(None, 1)
        cmd = parts[1] if len(parts) > 1 else ""
        exe = cmd.split(" -", 1)[0].strip()
        if exe.endswith("/MacOS/Blender") or os.path.basename(exe).lower() in ("blender", "blender.exe"):
            out.append(ln)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("beat")
    ap.add_argument("frame", type=int)
    ap.add_argument("--zoom", type=float, default=1.0, help="focal-length multiplier (1.3 = 30%% tighter)")
    ap.add_argument("--dolly", type=float, default=0.0, help="metres along the view axis, + = closer")
    ap.add_argument("--shift", default="0,0", help="lens shift x,y (fractions of frame)")
    ap.add_argument("--samples", type=int)
    ap.add_argument("--tag", default="_hero")
    ap.add_argument("--workdir")
    ap.add_argument("--out")
    ap.add_argument("--wait", action="store_true", help="wait (60 s polls, max 30 min) if Blender is busy")
    a = ap.parse_args()

    ep_path = os.path.join(os.path.abspath(a.episode_dir), "episode.json")
    ep = json.load(open(ep_path))
    workdir = os.path.abspath(a.workdir or os.path.join(ROOT, "output", ep["slug"]))
    ids = [b["id"] for b in ep["beats"]]
    idx = int(a.beat) if a.beat.isdigit() else ids.index(a.beat)

    t0 = time.time()
    while blender_busy():
        if not a.wait or time.time() - t0 > 1800:
            sys.exit("Blender is already running (one render at a time):\n  " + "\n  ".join(blender_busy()))
        print("Blender busy, waiting 60 s ...", flush=True)
        time.sleep(60)

    cmd = [PC.blender_exe(), "-b", "--factory-startup", "-P",
           os.path.join(ROOT, "pipeline", "blender", "render_episode_v2.py"), "--",
           ep_path, workdir, str(idx), "--still", str(a.frame), "--scale", "1", "--tag", a.tag]
    if a.zoom != 1.0 or a.dolly or a.shift != "0,0":
        cmd += ["--cam-zoom", str(a.zoom), "--cam-dolly", str(a.dolly), "--cam-shift", a.shift]
    if a.samples:
        cmd += ["--samples", str(a.samples)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = os.path.join(workdir, "stills_v2", "%02d_%s_f%04d%s.png" % (idx, ids[idx], a.frame, a.tag))
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("render failed (rc %s):\n%s" % (r.returncode, (r.stdout + r.stderr)[-2000:]))
    for ln in r.stdout.splitlines():
        if ln.startswith("[render_v2]"):
            print(ln)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        shutil.copyfile(out, a.out)
        out = a.out
    print(out)


if __name__ == "__main__":
    main()

"""One-shot driver for Self-Made Engineer reels (runs in the repo venv, NOT inside Blender).

  python page2/tools/oneshot.py plan   EPISODE WORKDIR                 # camera plan + camera_speed.json (no Blender)
  python page2/tools/oneshot.py still  EPISODE WORKDIR --frames 40,700 [--scale 0.35] [--samples 8] [--parts ...]
  python page2/tools/oneshot.py render EPISODE WORKDIR [--range A-B] [--scale 0.35] [--samples 16] [--dry-run]
  python page2/tools/oneshot.py link   EPISODE WORKDIR                 # frames_oneshot -> frames_v2/NN_<beat>/ (overlay_v2)
  python page2/tools/oneshot.py bench  EPISODE WORKDIR [--profile default|fast] [--engine cycles|eevee] [--scale 1.0]
  python page2/tools/oneshot.py post   EPISODE WORKDIR [--range A-B] [--scale 1.0] [--force]   # fast profile only

Render profiles (s13, page2/blender/render_profiles.py): --profile on still/render/bench, else episode
render.profile, else "fast" (default since 27 Nov 2026, Irfan OK; use --profile default for the old full-res setup). "fast" renders 0.75 scale into frames_oneshot_fast/ (16 samples,
lower bounces, Cycles motion blur off, cheaper kitchen) and page2/tools/fast_post.py writes the full-res, 2D-blurred
frames into frames_oneshot/ after every job, so `link` / make_episode are unchanged.

WORKDIR needs audio/timings.json + captions.json (real ones from the v2 tts/captions steps, or synthetic ones from
page2/tools/synth_timings.py). Outputs (all under WORKDIR):
  oneshot/plan.json          windows, events (preset/section/cast swaps), keys, per-frame camera [x y z lx ly lz lens]
  oneshot/camera_speed.json  per-frame screen motion (px at 1080x1920, dx/dy) + whoosh cues -> 2D blur + SFX
  oneshot/jobs.json          frame-range jobs (<= 150 frames each)
  frames_oneshot/####.jpg    global frame numbers (render); stills_oneshot/f####.png (still)
  tracks_v2/NN_<beat>_A-B.json  2D-label anchors, beat-local frames, same format overlay_v2.load_anchors() reads
  oneshot/logs/              one Blender log per job

Rules baked in: ONE Blender process at a time (4 GB VRAM: a second GPU render would double VRAM), and before each
job the driver waits while any other Blender process is running (WJH renders on the Mac); jobs are resumable (a job
whose frames + tracks all exist is skipped; Blender skips existing frames inside a job).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent
ROOT = PAGE2.parent
sys.path.insert(0, str(PAGE2 / "blender"))
import mh_paths as M  # noqa: E402

M.add_import_paths()
import camera_plan as C  # noqa: E402
import worlds as WR  # noqa: E402
import render_profiles as RP  # noqa: E402

RENDER_PY = PAGE2 / "blender" / "render_oneshot.py"
# s13 benchmark frames (build-01 plan, 2,571 frames): hook dusk wide, day wide with grass (tower_low), Bolts medium
# pointing (tailgate_plan hold), mid-snap 3D-blur frame (tailgate snap 440-448), kitchen-window hold, callback dusk
BENCH_FRAMES = [("hook_dusk_wide", 60), ("day_wide_grass", 907), ("bolts_point_medium", 473),
                ("snap_mblur", 444), ("kitchen_window", 2127), ("callback_street_dusk", 2240)]
PROFILE_MARK = ".profile.json"          # frames_oneshot/<mark>: which profile wrote the frames (fast only)
ALLOW_LONG_HOLDS = False
MAX_JOB = 150


def blender_exe():
    sys.path.insert(0, str(ROOT / "pipeline"))
    import platform_cfg  # noqa: E402   (env var -> config_local.json -> per-OS default; never prints secrets)
    return platform_cfg.get("BLENDER_EXE")


def other_blender_running():
    """True if any Blender process is running (WJH may be rendering on this machine)."""
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blender.exe"], capture_output=True, text=True).stdout
            return "blender.exe" in out.lower()
        r = subprocess.run(["pgrep", "-ix", "blender"], capture_output=True, text=True)   # process NAME only
        return bool(r.stdout.split())
    except FileNotFoundError:
        return False


def wait_free(no_wait=False, poll=20):
    if not other_blender_running():
        return
    if no_wait:
        raise SystemExit("another Blender process is running; not starting (one GPU render at a time)")
    print("[oneshot] another Blender is running; waiting (Ctrl-C to stop)...", flush=True)
    while other_blender_running():
        time.sleep(poll)


def load_inputs(episode, workdir):
    ep = M.load_json(episode)
    wd = Path(workdir)
    tm = M.load_json(wd / "audio" / "timings.json")
    cp = wd / "captions.json"
    words = M.load_json(cp)["words"] if cp.exists() else []
    return ep, wd, tm, words


def resolve_profile(a):
    """--profile > episode render.profile > fast; --samples None -> the profile's or the old default."""
    name = getattr(a, "profile", None) or M.load_json(a.episode).get("render", {}).get("profile") or "fast"
    prof = RP.get(name)
    samples = a.samples
    if samples is None:
        samples = prof.get("samples") or (8 if a.cmd == "still" else 16)
    return name, prof, samples


def render_extra(a, name, prof, samples):
    """Blender args shared by still/render/bench. The default profile gives exactly the pre-s13 arguments."""
    extra = ["--scale", str(a.scale), "--samples", str(samples), "--engine", a.engine,
             "--mblur", prof.get("mblur", a.mblur)]
    if a.parts:
        extra += ["--parts", a.parts]
    if name != "default":
        extra += ["--profile", name]
    return extra


def make_plan(episode, workdir, quiet=False):
    raw = M.load_json(episode)
    wd = Path(workdir)
    try:                     # world first: an unregistered world must fail here, before timings/targets
        ep, loc, hf, extra, info = WR.plan_inputs(raw, wd)
    except WR.WorldNotRegistered as ex:
        raise SystemExit("[oneshot] PLAN FAILED\n%s" % ex)
    except ValueError as ex:
        raise SystemExit("[oneshot] PLAN FAILED: %s" % ex)
    _ep, wd, tm, words = load_inputs(episode, workdir)
    plan, speed = C.build_plan(ep, tm, words, loc, hf, extra_anchors=extra)
    plan["synthetic_timings"] = bool(tm.get("synthetic"))
    plan["world"], plan["anchor_source"] = info["world"], info["anchor_source"]
    plan["warnings"] += info["notes"] + ["label anchor not defined by the world: %s" % m for m in info["label_missing"]]
    od = wd / "oneshot"
    od.mkdir(parents=True, exist_ok=True)
    (od / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    whoosh = [{"f": w["f0"], "kind": w["kind"], "frames": w["f1"] - w["f0"] + 1,
               "gain_db": ep.get("oneshot", {}).get("whoosh_db", -20)} for w in plan["windows"]]
    (od / "camera_speed.json").write_text(json.dumps({
        "fps": plan["fps"], "frames": plan["frames"], "w": C.OUT_W, "h": C.OUT_H,
        "note": "px = mean screen motion per frame of a 3x3x3 point grid; dx/dy = mean direction (y down); "
                "move = hold|travel|snap|section|crane|portal|backout; join = portal cut frame (px clamped). 2D blur: kernel ~ px along (dx, dy) when px > ~8.",
        "beats": [{k: b[k] for k in ("id", "f0", "frames")} for b in plan["beats"]],
        "windows": plan["windows"], "hidden_joins": plan["hidden_joins"], "whoosh": whoosh,
        "speed": speed}), encoding="utf-8")
    jobs = []
    for b in plan["beats"]:            # jobs never straddle beats (tracks are per beat), <= MAX_JOB frames
        a, end = b["f0"], b["f0"] + b["frames"] - 1
        while a <= end:
            jobs.append([a, min(end, a + MAX_JOB - 1)])
            a += MAX_JOB
    (od / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    if not quiet:
        print("[oneshot] world %s (anchors: %s)" % (plan["world"], plan["anchor_source"]))
        print("[oneshot] %d frames (%.1f s), %d moves, %d events, %d jobs%s" % (
            plan["frames"], plan["frames"] / plan["fps"], len(plan["windows"]), len(plan["events"]), len(jobs),
            "  (SYNTHETIC timings)" if plan["synthetic_timings"] else ""))
        for w in plan["warnings"]:
            print("  WARN", w)
        runs = C.static_runs(speed, plan["fps"])
        print("  static camera runs > 1 s:", runs or "none")
        lh = plan.get("longest_hold")
        if lh:
            print("  longest hold: %.1f s (f%d-%d, beat %s)" % (lh["s"], lh["f0"], lh["f1"], lh["beat"]))
    too_long = C.check_holds(plan)[0]
    if too_long and not ALLOW_LONG_HOLDS:
        raise SystemExit("[oneshot] PLAN FAILED: %d hold(s) over %.0f s (chief's rule; outputs written for inspection; "
                         "--allow-long-holds to override): %s" % (len(too_long), C.MAX_HOLD_S,
                         ", ".join("%.1fs@f%d" % (h["s"], h["f0"]) for h in too_long)))
    return plan, jobs


def _blender_cmd(episode, workdir, extra):
    return [blender_exe(), "-b", "--factory-startup", "-P", str(RENDER_PY), "--",
            str(Path(episode).resolve()), str(Path(workdir).resolve())] + extra


def _run(cmd, log, dry):
    print("[oneshot] $", " ".join('"%s"' % c if " " in c else c for c in cmd), flush=True)
    if dry:
        return 0
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(str(log), "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    print("[oneshot]   exit %d in %.1fs (log %s)" % (r.returncode, time.time() - t0, log), flush=True)
    return r.returncode


def job_done(wd, plan, a, b, frames_dir="frames_oneshot"):
    fr = wd / frames_dir
    if not all((fr / ("%04d.jpg" % f)).exists() for f in range(a, b + 1)):
        return False
    beat = C.frame_to_beat(plan["beats"], a)
    tdir = wd / "tracks_v2"
    la, lb = a - beat["f0"] + 1, b - beat["f0"] + 1
    return (tdir / ("%02d_%s_%04d-%04d.json" % (beat["idx"], beat["id"], la, lb))).exists() or not tdir.exists()


def check_profile_mark(wd, name, scale, force):
    """Fast frames must not be mixed with default frames in frames_oneshot/ (job_done would skip them)."""
    out = wd / "frames_oneshot"
    mark = out / PROFILE_MARK
    have = sorted(out.glob("[0-9][0-9][0-9][0-9].jpg")) if out.exists() else []
    cur = M.load_json(mark) if mark.exists() else None
    if name == "default":
        if cur and have:
            print("[oneshot] WARNING: frames_oneshot/ holds %s-profile frames (%s); default jobs whose frames exist "
                  "are skipped" % (cur.get("profile"), mark))
        return
    want = {"profile": name, "scale": scale}
    if have and cur != want and not force:
        raise SystemExit("[oneshot] frames_oneshot/ already holds %d frames from %s; move them away (or --force to "
                         "re-render every job with profile %s)" % (len(have), cur or "the default profile", name))
    raw = wd / RP.get(name)["raw_dir"]                     # raw frames from another scale must not be re-posted
    rmark = raw / PROFILE_MARK
    rhave = sorted(raw.glob("[0-9][0-9][0-9][0-9].jpg")) if raw.exists() else []
    rcur = M.load_json(rmark) if rmark.exists() else None
    if rhave and rcur != want and not force:
        raise SystemExit("[oneshot] %s/ holds %d raw frames from %s, not %s; move them away (or --force)" % (
            raw.name, len(rhave), rcur or "an unknown run", want))
    for d, m in ((out, mark), (raw, rmark)):
        d.mkdir(parents=True, exist_ok=True)
        m.write_text(json.dumps(want), encoding="utf-8")


def cmd_render(a):
    name, prof, samples = resolve_profile(a)
    plan, jobs = make_plan(a.episode, a.workdir)
    wd = Path(a.workdir)
    if a.range:
        lo, hi = [int(x) for x in a.range.split("-")]
        jobs = [[max(j0, lo), min(j1, hi)] for j0, j1 in jobs if j1 >= lo and j0 <= hi]
    extra = render_extra(a, name, prof, samples)
    fast = name == "fast"
    if fast and not a.dry_run:
        check_profile_mark(wd, name, a.scale, a.force)
        print("[oneshot] profile fast: raw %s/ at %.2f x scale, post -> frames_oneshot/" % (prof["raw_dir"],
                                                                                      prof["res_factor"]))
    elif not a.dry_run:
        check_profile_mark(wd, name, a.scale, a.force)
    failed = 0
    for j0, j1 in jobs:
        if job_done(wd, plan, j0, j1) and not a.force:
            print("[oneshot] job %d-%d done, skipped" % (j0, j1))
            continue
        if fast and job_done(wd, plan, j0, j1, prof["raw_dir"]) and not a.force:
            rc = 0                                  # raw frames already rendered: post only
        else:
            if not a.dry_run:
                wait_free(a.no_wait)
            rc = _run(_blender_cmd(a.episode, a.workdir, ["--range", "%d-%d" % (j0, j1)] + extra),
                      wd / "oneshot" / "logs" / ("job_%04d-%04d.log" % (j0, j1)), a.dry_run)
        if fast and rc == 0 and not a.dry_run:
            import fast_post as FP
            FP.post_range(a.episode, wd, j0, j1, a.scale, force=a.force)
        failed += rc != 0
    if failed:
        raise SystemExit("%d job(s) failed (see oneshot/logs)" % failed)


def post_stills(a, stdir, frames, tag):
    """fast profile: the low-res PNG stills -> final size + 2D blur, in place (a still run always re-renders)."""
    import fast_post as FP
    size = FP.final_size(a.episode, a.scale)
    table = FP.blur_table(a.workdir)[0]
    out = {}
    for f in frames:
        p = Path(stdir) / ("f%04d%s.png" % (f, tag))
        if p.exists():
            out[f] = round(FP.process_file(p, p, size, table.get(f)), 2)
            print("[oneshot] fast post f%d -> %dx%d%s %.2fs" % (f, size[0], size[1],
                  " + %s blur %.0fpx" % (table[f]["mode"], table[f]["px"]) if f in table else "", out[f]))
    return out


def cmd_still(a):
    name, prof, samples = resolve_profile(a)
    make_plan(a.episode, a.workdir)
    extra = ["--still", a.frames] + render_extra(a, name, prof, samples)
    if a.save_blend:
        extra += ["--save-blend"]
    if a.views:
        extra += ["--views", str(Path(a.views).resolve())]
    if a.tag:
        extra += ["--tag", a.tag]
    if not a.dry_run:
        wait_free(a.no_wait)
    rc = _run(_blender_cmd(a.episode, a.workdir, extra), Path(a.workdir) / "oneshot" / "logs" / "still.log", a.dry_run)
    if rc:
        raise SystemExit("still render failed (exit %d), see oneshot/logs/still.log" % rc)
    if name == "fast" and not a.dry_run:
        post_stills(a, Path(a.workdir) / "stills_oneshot", [int(x) for x in a.frames.split(",")], a.tag)


def cmd_post(a):
    import fast_post as FP
    wd = Path(a.workdir)
    if a.range:
        lo, hi = [int(x) for x in a.range.split("-")]
    else:
        nums = sorted(int(p.stem) for p in (wd / FP.RAW_DIR).glob("[0-9][0-9][0-9][0-9].jpg"))
        if not nums:
            raise SystemExit("no raw fast frames in %s" % (wd / FP.RAW_DIR))
        lo, hi = nums[0], nums[-1]
    make_plan(a.episode, a.workdir, quiet=True)          # camera_speed.json current
    FP.post_range(a.episode, wd, lo, hi, a.scale, force=a.force)


def cmd_bench(a):
    """Render BENCH_FRAMES as stills with one profile/engine; per-frame seconds (inside Blender, after a 1-sample
    warm-up that syncs the scene to the device) -> WORKDIR/bench/<profile>_<engine>/bench.json + console."""
    import re
    name, prof, samples = resolve_profile(a)
    if a.samples is None and name == "default":
        samples = int(M.load_json(a.episode).get("render", {}).get("samples", 32))     # the final-quality setup
    make_plan(a.episode, a.workdir)
    wd = Path(a.workdir)
    sel = [x for x in BENCH_FRAMES if not a.frames or str(x[1]) in a.frames.split(",")]
    frames = [f for _n, f in sel]
    tag = "%s_%s%s" % (name, a.engine, a.tag)
    bdir = wd / "bench" / tag
    bdir.mkdir(parents=True, exist_ok=True)
    log = bdir / "bench.log"
    extra = ["--still", ",".join(str(f) for f in frames)] + render_extra(a, name, prof, samples) + [
        "--still-dir", str(bdir.resolve()), "--warmup"]
    if not a.dry_run:
        wait_free(a.no_wait)
    t0 = time.time()
    rc = _run(_blender_cmd(a.episode, a.workdir, extra), log, a.dry_run)
    if a.dry_run:
        return
    wall = time.time() - t0
    txt = log.read_text(encoding="utf-8", errors="replace")
    per = {int(m.group(1)): float(m.group(2)) for m in re.finditer(r"\[oneshot\] still f(\d+) ([\d.]+)s", txt)}
    mb = re.search(r"\[oneshot\] built in ([\d.]+)s", txt)
    mw = re.search(r"\[oneshot\] warmup f\d+ ([\d.]+)s", txt)
    st = wd / "oneshot" / ("stats_%04d-%04d.json" % (min(frames), max(frames)))
    stats = {}
    if st.exists():
        stats = M.load_json(st)
        os.replace(str(st), str(bdir / "stats.json"))
    post = post_stills(a, bdir, frames, "") if name == "fast" and rc == 0 else {}
    rows = []
    for n, f in sel:
        r = {"frame": f, "shot": n, "render_s": per.get(f)}
        if post:
            r["post_s"] = post.get(f)
        rows.append(r)
    got = [r["render_s"] for r in rows if r["render_s"] is not None]
    res = {"profile": name, "engine": a.engine, "scale": a.scale, "samples": samples,
           "device": stats.get("device"), "render_res": stats.get("render_res"), "exit": rc,
           "build_s": float(mb.group(1)) if mb else None, "warmup_s": float(mw.group(1)) if mw else None,
           "wall_s": round(wall, 1), "frames": rows,
           "mean_render_s": round(sum(got) / len(got), 2) if got else None,
           "mean_post_s": round(sum(post.values()) / len(post), 2) if post else None,
           "note": "render_s = Blender render time per still (after a 1-sample warm-up); post_s = fast_post "
                   "upscale + 2D blur (CPU, runs after each job in a real render)"}
    (bdir / "bench.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("[bench] %s / %s  scale %.2f  samples %d  device %s  build %ss" % (
        name, a.engine, a.scale, samples, res["device"], res["build_s"]))
    for r in rows:
        print("  f%-5d %-22s render %7s s%s" % (r["frame"], r["shot"], r["render_s"],
              "   post %.2f s" % r["post_s"] if r.get("post_s") is not None else ""))
    print("  mean render %s s/frame%s -> %s" % (res["mean_render_s"], "  (+ post %s s)" % res["mean_post_s"]
                                                 if post else "", bdir / "bench.json"))
    if rc:
        raise SystemExit("bench render failed (exit %d), see %s" % (rc, log))


def cmd_link(a):
    plan, _ = make_plan(a.episode, a.workdir, quiet=True)
    wd = Path(a.workdir)
    src = wd / "frames_oneshot"
    n = 0
    for b in plan["beats"]:
        dst = wd / "frames_v2" / ("%02d_%s" % (b["idx"], b["id"]))
        dst.mkdir(parents=True, exist_ok=True)
        for k in range(b["frames"]):
            s, d = src / ("%04d.jpg" % (b["f0"] + k)), dst / ("%04d.jpg" % (k + 1))
            if not s.exists() or d.exists():
                continue
            try:
                os.link(str(s), str(d))
            except OSError:
                shutil.copy2(str(s), str(d))
            n += 1
    print("[oneshot] linked %d frames into frames_v2/<beat>/ (beat-local numbering)" % n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "still", "render", "link", "bench", "post"):
        p = sp.add_parser(name)
        p.add_argument("episode")
        p.add_argument("workdir")
        p.add_argument("--allow-long-holds", action="store_true", help="do not fail on holds over 10 s")
        if name in ("still", "render", "bench"):
            p.add_argument("--scale", type=float, default=1.0 if name == "bench" else 0.35,
                           help="FINAL scale of 1080x1920 (the fast profile renders 0.75 of it and upscales)")
            p.add_argument("--samples", type=int, default=None,
                           help="default: profile fast 16; else still 8 / render 16 / bench episode render.samples")
            p.add_argument("--profile", default=None, choices=RP.NAMES,
                           help="render profile (default: episode render.profile, else 'default')")
            p.add_argument("--engine", default="cycles", choices=("cycles", "eevee"))
            p.add_argument("--parts", default="", help="comma list to build only some parts (see render_oneshot.py)")
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--mblur", default="3d", choices=("3d", "2d", "off"),
                           help="3d = render motion blur in snap windows (default until overlay_v2 has 2D blur)")
            p.add_argument("--no-wait", action="store_true", help="fail instead of waiting for another Blender")
        if name == "bench":
            p.add_argument("--frames", default="", help="subset of the bench frames, e.g. 60,2127")
            p.add_argument("--tag", default="", help="suffix for the bench folder name")
        if name == "post":
            p.add_argument("--range", default="", help="global frames A-B (default: every raw fast frame)")
            p.add_argument("--scale", type=float, default=1.0, help="FINAL scale used by the render")
            p.add_argument("--force", action="store_true")
        if name == "still":
            p.add_argument("--frames", required=True, help="global frame numbers, e.g. 40,700")
            p.add_argument("--save-blend", action="store_true")
            p.add_argument("--views", default="", help="JSON list of extra QC views (anchor-relative cams), still only")
            p.add_argument("--tag", default="", help="suffix for the still file names, e.g. _v3")
        if name == "render":
            p.add_argument("--range", default="", help="global frames A-B (e.g. 1-600 for a 20 s test)")
            p.add_argument("--force", action="store_true")
    a = ap.parse_args()
    global ALLOW_LONG_HOLDS
    ALLOW_LONG_HOLDS = a.allow_long_holds
    if a.cmd == "plan":
        make_plan(a.episode, a.workdir)
    elif a.cmd == "still":
        cmd_still(a)
    elif a.cmd == "render":
        cmd_render(a)
    elif a.cmd == "bench":
        cmd_bench(a)
    elif a.cmd == "post":
        cmd_post(a)
    else:
        cmd_link(a)


if __name__ == "__main__":
    main()

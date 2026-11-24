"""qc_oneshot: one-shot editing checks for Self-Made Engineer reels (PROPOSAL 4.2 item 9).

  python page2/tools/qc_oneshot.py WORKDIR [--frames DIR | --video FILE.mp4] [--out report.json]

FAILs on
  1. CUT: a frame-difference spike outside every planned travel/snap/section window (+-2 frames) and outside the
     whitelisted hidden joins (episode oneshot.hidden_joins = [[f0, f1], ...], the only allowed scene join, inside a
     whip blur; BUILD-SPEC 1).
  2. STATIC: the camera holds still for more than ~1 s, either in the plan (camera_speed.json px/frame) or in the
     pixels (consecutive frames practically identical).
  4. HOLD_TOO_LONG: a camera hold (stretch between move windows) over 10 s (warn over 9 s, chief's rule).
  3. SWAP ON A HOLD: a preset / section / cast (blocking, outfit) / portal event that is not inside a move window
     (popping must be hidden by the motion).
Needs WORKDIR/oneshot/plan.json + camera_speed.json (page2/tools/oneshot.py plan). Pixel checks run when frames
(WORKDIR/frames_oneshot/####.jpg by default, global numbering) or a video are available; with --video the frame
index is 1-based in display order. Exit code 1 on any FAIL.
"""
import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SMALL = (135, 240)        # diff resolution (w, h) - 1/8 of 1080x1920
SPIKE_ABS = 40.0          # mean |diff| (0..255) that is always suspicious (a fast hold can reach ~15-25)
SPIKE_REL = 3.0           # ... or this many times the local median (+-15 frames)
STATIC_EPS = 0.20         # mean |diff| below this = "no visible change"
MARGIN = 2


def gray_small(img):
    return np.asarray(img.convert("L").resize(SMALL, Image.BILINEAR), dtype=np.float32)


def frames_from_dir(d):
    files = sorted(Path(d).glob("*.jpg")) + sorted(Path(d).glob("*.png"))
    out = {}
    for p in files:
        try:
            f = int(p.stem.lstrip("f"))
        except ValueError:
            continue
        out[f] = p
    return out


def diffs_from_dir(d):
    fr = frames_from_dir(d)
    keys = sorted(fr)
    diffs, prev, pf = {}, None, None
    for f in keys:
        g = gray_small(Image.open(str(fr[f])))
        if prev is not None and f == pf + 1:
            diffs[f] = float(np.mean(np.abs(g - prev)))
        prev, pf = g, f
    return diffs


def diffs_from_video(path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
    try:
        import platform_cfg
        ff = platform_cfg.get("FFMPEG_EXE")
    except Exception:
        ff = "ffmpeg"
    w, h = SMALL
    cmd = [ff, "-v", "error", "-i", str(path), "-vf", "scale=%d:%d,format=gray" % (w, h), "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (w * h)
    arr = np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)
    return {i + 1: float(np.mean(np.abs(arr[i] - arr[i - 1]))) for i in range(1, n)}


def in_windows(f, wins, margin=MARGIN):
    return any(w0 - margin <= f <= w1 + margin for w0, w1 in wins)


def check(plan, speed, diffs=None, static_s=1.0):
    fps = plan["fps"]
    wins = [(w["f0"], w["f1"]) for w in plan["windows"]]
    joins = [tuple(j) for j in plan.get("hidden_joins", [])]
    fails, info = [], {}
    # 3. swaps on holds
    for e in plan["events"]:
        if e["f"] <= 1:
            continue
        if e["kind"] in ("preset", "section", "cast", "lights", "portal") and not in_windows(e["f"], wins, 0):
            fails.append({"type": "SWAP_ON_HOLD", "f": e["f"], "kind": e["kind"]})
    # 4. hold length (chief's rule): > 10 s FAIL, > 9 s warn
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
    import camera_plan as CPL
    hfails, hwarns, longest = CPL.check_holds(dict(plan, frames=plan.get("frames") or len(speed)))
    for h in hfails:
        fails.append(dict(h, type="HOLD_TOO_LONG"))
    info["hold_warnings"] = hwarns
    info["longest_hold"] = longest
    # 2a. static in the plan
    run, start = 0, None
    for s in speed + [{"f": None, "px": 1e9}]:
        if s["px"] < 0.3:
            start = s["f"] if start is None else start
            run += 1
        else:
            if run > static_s * fps:
                fails.append({"type": "STATIC_PLAN", "f0": start, "frames": run})
            run, start = 0, None
    if diffs:
        keys = sorted(diffs)
        vals = [diffs[k] for k in keys]
        spikes = []
        for i, f in enumerate(keys):
            loc = vals[max(0, i - 15):i] + vals[i + 1:i + 16]
            med = statistics.median(loc) if loc else 0.0
            if diffs[f] > SPIKE_ABS or (med > 0.05 and diffs[f] > SPIKE_REL * med and diffs[f] > 4.0):
                spikes.append((f, round(diffs[f], 2), round(med, 2)))
        for f, d, med in spikes:
            if in_windows(f, wins) or in_windows(f, joins):
                continue
            fails.append({"type": "CUT", "f": f, "diff": d, "local_median": med})
        # 2b. static in pixels
        run, start, last = 0, None, None
        for f in keys + [None]:
            still = f is not None and diffs[f] < STATIC_EPS and (last is None or f == last + 1)
            if still:
                start = f if start is None else start
                run += 1
            else:
                if run > static_s * fps:
                    fails.append({"type": "STATIC_PIXELS", "f0": start, "frames": run})
                run, start = (1, f) if (f is not None and diffs[f] < STATIC_EPS) else (0, None)
            last = f
        info.update({"frames_checked": len(keys) + 1, "spikes_total": len(spikes),
                "spikes_in_windows": len(spikes) - len([x for x in fails if x["type"] == "CUT"]),
                "median_diff": round(statistics.median(vals), 3) if vals else None})
    return fails, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("--frames", default=None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--static-s", type=float, default=1.0)
    a = ap.parse_args()
    wd = Path(a.workdir)
    plan = json.loads((wd / "oneshot" / "plan.json").read_text(encoding="utf-8"))
    speed = json.loads((wd / "oneshot" / "camera_speed.json").read_text(encoding="utf-8"))["speed"]
    diffs = None
    if a.video:
        diffs = diffs_from_video(a.video)
    else:
        d = Path(a.frames) if a.frames else wd / "frames_oneshot"
        if d.exists():
            diffs = diffs_from_dir(d)
    fails, info = check(plan, speed, diffs, a.static_s)
    rep = {"pass": not fails, "fails": fails, "info": info, "windows": len(plan["windows"]),
           "pixel_checks": diffs is not None, "synthetic_timings": plan.get("synthetic_timings", False)}
    out = Path(a.out) if a.out else wd / "oneshot" / "qc_oneshot.json"
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("qc_oneshot: %s  (%d fails; pixel checks: %s) -> %s" % ("PASS" if not fails else "FAIL", len(fails),
                                                                  "yes" if diffs else "no (no frames)", out))
    lh = info.get("longest_hold")
    if lh:
        print("   longest hold %.1f s (f%d-%d, beat %s)%s" % (lh["s"], lh["f0"], lh["f1"], lh["beat"],
              "; WARN %d hold(s) over 9 s" % len(info["hold_warnings"]) if info.get("hold_warnings") else ""))
    for x in fails[:20]:
        print("  ", x)
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()

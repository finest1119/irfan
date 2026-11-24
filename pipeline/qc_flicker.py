"""Flicker QC for caption / label regions.

Measures frame-to-frame luminance change inside given screen regions and flags spikes, separating
expected changes (caption chunk / highlighted word changes, label pop-ins: pass them as --events) from
real flicker. Flicker signature = A-B-A: a pixel jumps at frame t and jumps back at t+1 (z-fighting,
alpha sorting, a text box popping for one frame), which plain motion or a caption change does not do.

  python pipeline/qc_flicker.py VIDEO.mp4 [--start S --dur D] --region caption:1200:1400 [--region name:y0:y1[:x0:x1]] \
      [--events 5,40,73,9-20] [--thr 3] [--json out.json]     (events: frames or ranges, 1-based)
  python pipeline/qc_flicker.py FRAME_DIR --frames 288 --region cards:170:540      (####.png frames)

Per region it reports:
  mean_d / p95_d / max_d   mean absolute luma change between consecutive frames (0-255) in the region
  spikes                   frames with d > max(thr, 4 x median d); split into expected (within +-1 frame of an
                           event) and unexpected
  aba_frames               frames where the region mean jumps and comes back (d(t), d(t+1) > thr and
                           |L(t+1) - L(t-1)| < 0.5 x min(d(t), d(t+1)))
  px_flicker_mean/max      share of region pixels (%) that flip by > 24 luma and flip back on the next frame
                           (|Y(t+1) - Y(t-1)| < 8, opposite signs): the per-pixel z-fighting / shimmer measure
  px_flicker_frames        frames where more than 0.2 % of the region pixels flicker that way
"""
import argparse
import glob
import json
import os
import subprocess

import numpy as np
from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import platform_cfg as PC  # cross-platform paths; macOS defaults = the old hard-coded values


def frames_from_video(path, start=None, dur=None):
    probe = subprocess.run([PC.ffprobe_exe(), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    probe = [x for x in probe if x.strip()]
    w, h = int(probe[0]), int(probe[1])
    cmd = [PC.ffmpeg_exe(), "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", path]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w)
    p.wait()


def frames_from_dir(path, limit=None):
    files = sorted(glob.glob(os.path.join(path, "*.png")))
    if limit:
        files = files[:limit]
    for f in files:
        yield np.array(Image.open(f).convert("L"))


def parse_region(s):
    parts = s.split(":")
    name, y0, y1 = parts[0], int(parts[1]), int(parts[2])
    x0, x1 = (int(parts[3]), int(parts[4])) if len(parts) >= 5 else (None, None)
    return name, y0, y1, x0, x1


def analyse(frames, regions, events, thr=3.0, scale_y=1.0):
    st = {r[0]: {"L": [], "d": [], "px": []} for r in regions}
    prev2 = {r[0]: None for r in regions}
    prev = {r[0]: None for r in regions}
    n = 0
    for fr in frames:
        n += 1
        for name, y0, y1, x0, x1 in regions:
            yy0, yy1 = int(y0 * scale_y), int(y1 * scale_y)
            reg = fr[yy0:yy1, x0:x1].astype(np.int16)
            s = st[name]
            s["L"].append(float(reg.mean()))
            if prev[name] is not None:
                s["d"].append(float(np.abs(reg - prev[name]).mean()))
                if prev2[name] is not None:
                    a = prev[name] - prev2[name]        # step into t
                    b = reg - prev[name]                # step out of t
                    back = np.abs(reg - prev2[name])
                    flick = (np.abs(a) > 24) & (np.abs(b) > 24) & (np.sign(a) != np.sign(b)) & (back < 8)
                    s["px"].append(100.0 * float(flick.mean()))   # attributed to frame t (= the previous frame)
            prev2[name], prev[name] = prev[name], reg
    ev = set()
    for e in events:
        ev.update((e - 1, e, e + 1))
    out = {"frames": n, "regions": {}}
    for name, *_ in regions:
        s = st[name]
        d = np.array(s["d"]) if s["d"] else np.zeros(1)
        L = np.array(s["L"])
        med = float(np.median(d))
        lim = max(thr, 4 * med)
        # d[i] is the change from frame i+1 to frame i+2 (1-based frame numbers)
        spikes = [i + 2 for i, v in enumerate(d) if v > lim]
        exp = [f for f in spikes if f in ev]
        unexp = [f for f in spikes if f not in ev]
        aba = []
        for i in range(len(d) - 1):
            t = i + 2
            if d[i] > thr and d[i + 1] > thr and abs(L[t] - L[t - 2]) < 0.5 * min(d[i], d[i + 1]) and t not in ev:
                aba.append(t)
        px = np.array(s["px"]) if s["px"] else np.zeros(1)
        out["regions"][name] = {
            "mean_d": round(float(d.mean()), 3), "median_d": round(med, 3), "p95_d": round(float(np.percentile(d, 95)), 3),
            "max_d": round(float(d.max()), 3), "max_d_frame": int(np.argmax(d)) + 2, "spike_limit": round(lim, 3),
            "spikes": len(spikes), "spikes_expected": len(exp), "spikes_unexpected": len(unexp),
            "unexpected_frames": unexp[:30], "aba_frames": aba[:30], "aba_count": len(aba), "aba_all": aba, "unexpected_all": unexp, "d_all": [round(float(v), 3) for v in d],
            "px_flicker_mean_pct": round(float(px.mean()), 4), "px_flicker_max_pct": round(float(px.max()), 4),
            "px_flicker_frames": int((px > 0.2).sum()),
            # px[j] belongs to the middle frame t = j + 2 of the triple (t-1, t, t+1)
            "px_flicker_frames_outside_events": [j + 2 for j, v in enumerate(px) if v > 0.2 and (j + 2) not in ev][:40],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--start", type=float)
    ap.add_argument("--dur", type=float)
    ap.add_argument("--frames", type=int)
    ap.add_argument("--region", action="append", required=True)
    ap.add_argument("--events", default="")
    ap.add_argument("--thr", type=float, default=3.0)
    ap.add_argument("--ref-height", type=int, default=1920, help="regions are given for this frame height")
    ap.add_argument("--json")
    a = ap.parse_args()
    regions = [parse_region(r) for r in a.region]
    events = []
    for x in a.events.split(","):
        x = x.strip()
        if "-" in x:                     # a range of frames, e.g. a pop-in animation "9-20"
            lo, hi = x.split("-")
            events += list(range(int(lo), int(hi) + 1))
        elif x:
            events.append(int(x))
    if os.path.isdir(a.src):
        frames = frames_from_dir(a.src, a.frames)
        first = sorted(glob.glob(os.path.join(a.src, "*.png")))[0]
        h = Image.open(first).height
    else:
        frames = frames_from_video(a.src, a.start, a.dur)
        h = int(subprocess.run([PC.ffprobe_exe(), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height",
                                "-of", "csv=p=0", a.src], capture_output=True, text=True).stdout.strip().strip(",").split(",")[0])
    res = analyse(frames, regions, events, a.thr, h / float(a.ref_height))
    res["src"] = a.src
    for name, r in res["regions"].items():
        print("%-12s mean_d %.2f  p95 %.2f  max %.2f (f%d)  spikes %d (expected %d, unexpected %d)  ABA %d  "
              "px-flicker mean %.3f%% max %.3f%% frames>0.2%%: %d" % (
                  name, r["mean_d"], r["p95_d"], r["max_d"], r["max_d_frame"], r["spikes"], r["spikes_expected"],
                  r["spikes_unexpected"], r["aba_count"], r["px_flicker_mean_pct"], r["px_flicker_max_pct"],
                  r["px_flicker_frames"]))
        print("%-12s px-flicker frames outside events: %s" % ("", r["px_flicker_frames_outside_events"]))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1)


if __name__ == "__main__":
    main()

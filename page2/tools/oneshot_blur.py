"""camera_speed.json -> per-frame 2D motion-blur spec + whoosh cue times (venv, no Blender). Shared by Page 2 and 3.

  python page2/tools/oneshot_blur.py WORKDIR [--cap 60] [--min-px 8] [--all-moves]
  -> WORKDIR/oneshot/blur_2d.json

Rules (WORLDS-SPEC 1.4, PROPOSAL 4.2): blur only inside move windows (holds never blur), strength = the plan's
screen motion px clamped at --cap (60 px), nothing below --min-px, never on a portal `join` frame (the hidden cut).
Mode: "radial" (zoom blur) for snap/portal push-ins, "directional" along (dx, dy) for everything else.
Frames are given GLOBAL and beat-local (overlay_v2 renders per beat: local frame k = global - beat f0 + 1).
Whoosh cues: one per move window at its first frame (seconds from the reel start and beat-local), gain from
camera_speed (episode oneshot.whoosh_db, default -20 dB). Overlay integration comes later (after the port patch).
"""
import argparse
import json
import math
from pathlib import Path

CAP_PX = 60.0
MIN_PX = 8.0
RADIAL_MOVES = ("snap", "portal")


def _beat_of(beats, f):
    for b in beats:
        if b["f0"] <= f < b["f0"] + b["frames"]:
            return b
    return beats[-1]


def blur_spec(cs, cap=CAP_PX, min_px=MIN_PX, all_moves=False):
    fps = cs["fps"]
    beats = cs["beats"]
    win_of = {}
    for w in cs["windows"]:
        if all_moves or w["kind"] != "none":
            for f in range(w["f0"], w["f1"] + 1):
                win_of[f] = w
    frames = []
    skipped_join = 0
    for s in cs["speed"]:
        f = s["f"]
        w = win_of.get(f)
        if w is None or (s.get("move", "hold") == "hold" and not all_moves):
            continue
        if s.get("join") or f == w.get("join"):
            skipped_join += 1
            continue
        px = float(s["px"])
        if px < min_px:
            continue
        mag = math.hypot(s.get("dx", 0.0), s.get("dy", 0.0))
        b = _beat_of(beats, f)
        frames.append({"f": f, "beat": b["id"], "lf": f - b["f0"] + 1, "px": round(min(cap, px), 2),
                       "raw_px": round(px, 1),
                       "dir": [round(s["dx"] / mag, 4), round(s["dy"] / mag, 4)] if mag > 1e-6 else [0.0, 0.0],
                       "mode": "radial" if w["kind"] in RADIAL_MOVES else "directional", "move": w["kind"]})
    whoosh = []
    for wh in cs.get("whoosh", []):
        b = _beat_of(beats, wh["f"])
        whoosh.append({"t": round((wh["f"] - 1) / float(fps), 3), "f": wh["f"], "beat": b["id"],
                       "lf": wh["f"] - b["f0"] + 1, "t_beat": round((wh["f"] - b["f0"]) / float(fps), 3),
                       "kind": wh["kind"], "dur_s": round(wh["frames"] / float(fps), 3),
                       "gain_db": wh.get("gain_db", -20)})
    return {"fps": fps, "frames_total": cs["frames"], "cap_px": cap, "min_px": min_px,
            "note": "f = global frame, lf = beat-local frame; px already clamped; dir = unit screen direction "
                    "(y down); join frames are never blurred",
            "skipped_join_frames": skipped_join, "frames": frames, "whoosh": whoosh}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("--cap", type=float, default=CAP_PX)
    ap.add_argument("--min-px", type=float, default=MIN_PX)
    ap.add_argument("--all-moves", action="store_true", help="also blur hold frames inside windows (debug)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    wd = Path(a.workdir)
    cs = json.loads((wd / "oneshot" / "camera_speed.json").read_text(encoding="utf-8"))
    spec = blur_spec(cs, a.cap, a.min_px, a.all_moves)
    out = Path(a.out) if a.out else wd / "oneshot" / "blur_2d.json"
    out.write_text(json.dumps(spec), encoding="utf-8")
    print("oneshot_blur: %d blurred frames (cap %.0f px, %d join frames skipped), %d whoosh cues -> %s" % (
        len(spec["frames"]), a.cap, spec["skipped_join_frames"], len(spec["whoosh"]), out))


if __name__ == "__main__":
    main()

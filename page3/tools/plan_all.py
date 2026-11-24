#!/usr/bin/env python3
"""Plan every Page 3 episode with the shared one-shot driver and check what QC does not (no Blender).

  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python page3/tools/plan_all.py [EPISODE_DIR ...]

For each page3/episodes/*/episode.json: synthetic timings -> `page2/tools/oneshot.py plan` -> `qc_oneshot.py`
(plan checks), all into page3/_plan_test/<episode id>/ (git-ignored). Then, from plan.json:
  - backout: full duration (not truncated), settle after it, path length, peak metres/frame, exact frame-1 end;
  - holds: camera travel during each hold relative to its subject distance, and how far the look point slides
    (drift must not carry the subject off-centre);
  - world timeline (hometown_usa_plan): rebase switches, macro clip-plane frames, zones per job;
  - snaps/portals to the stop the camera is already at (no push-in).
Exit 1 if any episode fails to plan, fails QC, or has a truncated backout / runaway hold.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PAGE3 = Path(__file__).resolve().parent.parent
ROOT = PAGE3.parent
sys.path.insert(0, str(PAGE3 / "blender"))
import hometown_usa_plan as P  # noqa: E402

PY = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable
HOLD_RATIO_MAX = 0.7        # a hold may move the camera at most 70 % of its subject distance (orbit ~40 deg)
MAX_HOLD_S = 10.0           # Irfan's rule: no hold longer than ~9 s (fail above 10)
LOOK_RATIO_MAX = 0.25       # ... and slide its look point at most 25 % of it (subject stays near centre)


def run(args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY] + args, cwd=str(ROOT), capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_episode(ep_path):
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    wd = PAGE3 / "_plan_test" / ep["id"]
    rep = {"id": ep["id"], "ok": True, "problems": [], "warnings": []}
    rc, out = run(["page2/tools/synth_timings.py", str(ep_path), str(wd)])
    if rc:
        rep.update(ok=False, problems=["synth_timings failed: " + out])
        return rep
    rc, out = run(["page2/tools/oneshot.py", "plan", str(ep_path), str(wd)])
    rep["plan_out"] = out
    if rc:
        rep.update(ok=False, problems=["plan failed: " + out])
        return rep
    rep["warnings"] += [ln.strip()[5:] for ln in out.splitlines() if ln.strip().startswith("WARN")
                        and "explicit shot.camera kept" not in ln]
    rc, out = run(["page2/tools/qc_oneshot.py", str(wd)])
    rep["qc"] = out.splitlines()[0] if out else ""
    if rc:
        rep["ok"] = False
        rep["problems"].append("qc: " + out)
    plan = json.loads((wd / "oneshot" / "plan.json").read_text(encoding="utf-8"))
    stops = ep["oneshot"]["stops"]
    rep["frames"], rep["seconds"] = plan["frames"], round(plan["frames"] / plan["fps"], 1)
    rep["moves"] = [w["kind"] for w in plan["windows"]]
    want = int(round(ep["oneshot"]["move_durations_s"]["backout"] * plan["fps"]))
    bo = P.backout_stats(plan)
    rep["backout"] = bo
    if bo is None:
        rep["ok"] = False
        rep["problems"].append("no backout window")
    else:
        if bo["frames"] < want:
            rep["ok"] = False
            rep["problems"].append("backout truncated: %d of %d frames" % (bo["frames"], want))
        # page2 Session 3: backout ends ~0.4 s (~12 frames) before the reel ends, then settles; the reel's LAST
        # frame must match frame 1 (loop), the backout window end itself may differ by the settle.
        if bo["settle_frames"] > 30:
            rep["warnings"].append("long settle after backout: %d frames (> 1 s)" % bo["settle_frames"])
        cams = plan["cam"]
        last = cams[-1] if isinstance(cams, list) else cams[max(cams, key=int)]
        if max(abs(a - b) for a, b in zip(last[:6], cams[1][:6])) > 2e-4:
            rep["ok"] = False
            rep["problems"].append("reel's last frame does not match the frame-1 framing")
    holds = P.hold_drift_stats(plan)
    rep["worst_hold"] = max(holds, key=lambda h: h["ratio"]) if holds else None
    rep["max_hold_s"] = round(max(h["f1"] - h["f0"] + 1 for h in holds) / float(plan["fps"]), 1)
    rep["camera_keys"] = sum(len(b.get("shot", {}).get("camera") or [None]) for b in ep["beats"])
    for h in holds:
        if (h["f1"] - h["f0"] + 1) > MAX_HOLD_S * plan["fps"]:
            rep["ok"] = False
            rep["problems"].append("hold f%d-%d lasts %.1f s (> %.0f s)" % (h["f0"], h["f1"], (h["f1"] - h["f0"] + 1) /
                                                                          float(plan["fps"]), MAX_HOLD_S))
        if (h["ratio"] > HOLD_RATIO_MAX or h["look_ratio"] > LOOK_RATIO_MAX) and h["f1"] - h["f0"] > 10:
            rep["ok"] = False
            rep["problems"].append("hold f%d-%d moves %.3f m at subject %.3f m (x%.2f, look x%.2f)" % (
                h["f0"], h["f1"], h["moved_m"], h["subject_m"], h["ratio"], h["look_ratio"]))
    rep["rebase"] = P.rebase_keys(plan, stops[0])
    rep["macro_frames"] = len([f for f in range(1, plan["frames"] + 1) if P.clip_planes(plan, f)[0] < 0.001])
    jobs = json.loads((wd / "oneshot" / "jobs.json").read_text(encoding="utf-8"))
    rep["jobs"] = len(jobs)
    rep["max_zones_per_job"] = max(len(P.zones_for_range(plan, stops[0], *P.beat_range(plan, a, b))) for a, b in jobs)
    track = P.stop_track(plan, stops[0])
    def _push_in(w):  # page2 Session 4+: a same-stop snap/portal is a push-in (camera ends >= 25 % closer)
        a = P.anchor_for(w.get("stop")) if hasattr(P, "anchor_for") else None
        c0, c1 = plan["cam"][max(1, w["f0"] - 1)], plan["cam"][min(len(plan["cam"]) - 1, w["f1"])]
        if a is None:
            return abs(sum((x - y) ** 2 for x, y in zip(c0[:3], c1[:3]))) > 1e-6
        d0 = sum((x - y) ** 2 for x, y in zip(c0[:3], a)) ** 0.5
        d1 = sum((x - y) ** 2 for x, y in zip(c1[:3], a)) ** 0.5
        return d1 <= 0.75 * d0
    same = [w for w in plan["windows"] if w["kind"] in ("snap", "portal") and w["f0"] > 1
            and w.get("stop") == track[w["f0"] - 1] and not _push_in(w)]
    if same:
        rep["warnings"].append("snap/portal to the stop the camera is already at: %s (no push-in; needs a close-up "
                               "variant)" % ", ".join("f%d %s" % (w["f0"], w.get("stop")) for w in same))
    return rep


def main(argv):
    eps = [Path(a) / "episode.json" for a in argv] or sorted((PAGE3 / "episodes").glob("*/episode.json"))
    bad, rows = 0, []
    for p in eps:
        r = check_episode(p)
        rows.append(r)
        bad += not r["ok"]
        bo = r.get("backout") or {}
        wh = r.get("worst_hold") or {}
        print("%s %-40s max hold %s s, %s camera keys" % ("    ", r["id"], r.get("max_hold_s"), r.get("camera_keys")))
        print("%s %-40s %5s fr %5s s  backout %s fr %s m peak %s m/f settle %s  worst hold x%s  macro fr %s  "
              "rebase %d  jobs %s (max zones %s)" % (
                  "OK  " if r["ok"] else "FAIL", r["id"], r.get("frames"), r.get("seconds"), bo.get("frames"),
                  bo.get("length_m"), bo.get("peak_m_per_frame"), bo.get("settle_frames"), wh.get("ratio"),
                  r.get("macro_frames"), len(r.get("rebase", [])) - 1, r.get("jobs"), r.get("max_zones_per_job")))
        if r.get("qc"):
            print("     " + r["qc"].split(" -> ")[0])
        for x in r["problems"]:
            print("     PROBLEM " + x)
        for x in r["warnings"]:
            print("     warn " + x)
    out = PAGE3 / "_plan_test" / "plan_all.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    print("%d episode(s), %d failed -> %s" % (len(rows), bad, out.relative_to(ROOT)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

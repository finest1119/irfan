"""Split long camera holds (chief's rule: no hold over ~9 s, FAIL over 10 s) by adding camera keys. venv, no Blender.

Used by episode generators (make_build01_episode.py) before writing episode.json, so every future episode follows
the rule automatically:  ep = hold_split.split_long_holds(ep)

How: plan the episode with synthetic timings (175 WPM, like synth_timings.py), find the longest hold over
target_s (default 7 s, leaving margin for real TTS timing), and add ONE key at the sentence start (else a word)
nearest the middle of that hold. The key moves to a sub-stop on the same object: <to>__detail (snap 0.3 s) or
<to>__alt (travel 1.0 s), alternating. camera_plan derives sub-stops a world does not register (40 % push-in /
35 deg around), and an open cut-away section stays open. Cues are sentence indexes or words, never seconds, so
real TTS retimes them. Repeat until no hold is over target_s (or no cue fits; then the plan validator reports it).
"""
import copy
import sys
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PAGE2 / "blender"))
sys.path.insert(0, str(PAGE2 / "tools"))
import camera_plan as C  # noqa: E402
import synth_timings as ST  # noqa: E402
import worlds as WR  # noqa: E402

TARGET_S = 7.0
EDGE_S = 2.0          # each part of a split hold keeps at least this long


def _plan(ep):
    e2, loc, hf, extra, _info = WR.plan_inputs(ep)
    tim, cap = ST.synth(e2)
    plan, _speed = C.build_plan(e2, tim, cap["words"], loc, hf, extra_anchors=extra)
    return plan, cap["words"]


def _cue_for(words, beat_id, fps, plan, a, b):
    """(cue, t) nearest the middle of hold frames a..b: a sentence index if one fits, else 'word#n'."""
    bw = [w for w in words if w.get("beat") == beat_id]
    lay = plan["beats"]
    lead = 0.4

    def frame(t):
        return C.time_to_frame(lay, t - lead, fps)
    mid, lo, hi = (a + b) / 2.0, a + EDGE_S * fps, b - EDGE_S * fps
    best = None
    for i, t in enumerate(C.sentence_starts(bw)):
        f = frame(t)
        if lo <= f <= hi and (best is None or abs(f - mid) < abs(best[2] - mid)):
            best = (i, t, f)
    if best is None:
        for j, w in enumerate(bw):
            f = frame(w["start"])
            if lo <= f <= hi and (best is None or abs(f - mid) < abs(best[2] - mid)):
                nm = w.get("norm", w["word"].lower())
                if len(nm) < 3:
                    continue
                n = sum(1 for x in bw[:j] if x.get("norm", x["word"].lower()).startswith(nm))
                best = (nm if n == 0 else "%s#%d" % (nm, n), w["start"], f)
    return best


def split_long_holds(episode, target_s=TARGET_S, max_iter=30, log=print):
    ep = copy.deepcopy(episode)
    for _it in range(max_iter):
        plan, words = _plan(ep)
        fps = plan["fps"]
        segs = [h for h in C.hold_segments(plan) if h["s"] > target_s]
        if not segs:
            return ep
        done = False
        for h in sorted(segs, key=lambda h: -h["s"]):
            a, b = h["f0"], h["f1"]
            for bt in plan["beats"]:                     # try the beats this hold spans, middle-most first
                if bt["f0"] + bt["frames"] - 1 < a or bt["f0"] > b:
                    continue
                c = _cue_for(words, bt["id"], fps, plan, a, b)
                if c is None:
                    continue
                prev = [w for w in plan["windows"] if w["f1"] < a]
                nxt = [w for w in plan["windows"] if w["f0"] > b]
                to = prev[-1]["to"] if prev and prev[-1]["to"] != "custom" else (nxt[0]["to"] if nxt else None)
                if not isinstance(to, str) or to == "custom":
                    continue
                base, var = C.split_variant(to)
                after = [w for w in plan["windows"] if w["f0"] > c[2]]
                avoid = {to, after[0]["to"] if after else None}
                order = ["__alt", "__detail", ""] if var == "__detail" else ["__detail", "__alt", ""]
                var = [v for v in order if base + v not in avoid][0]     # never a no-op move to where we are
                key = {"cue": c[0], "move": "snap" if var == "__detail" else "travel",
                       "dur": 0.3 if var == "__detail" else 1.0, "to": base + var,
                       "hold": {"type": "drift"}, "_auto": "hold_split"}
                sec = C.state_at(plan, "section", c[2])
                if sec:
                    key["section"] = sec
                beat = [x for x in ep["beats"] if x["id"] == bt["id"]][0]
                keys = beat.setdefault("shot", {}).setdefault("camera", [])
                kt = {k["ki"]: k["t_cue"] for k in plan["keys"] if k["beat"] == bt["id"]}
                pos = sum(1 for ki in range(len(keys)) if kt.get(ki, -1e9) <= c[1])
                keys.insert(pos, key)
                log("[hold_split] %.1f s hold f%d-%d: + %s to %s at cue %r (beat %s)" % (
                    h["s"], a, b, key["move"], key["to"], c[0], bt["id"]))
                done = True
                break
            if done:
                break
        if not done:
            log("[hold_split] no cue fits the remaining long holds: %s" % [(h["s"], h["f0"]) for h in segs])
            return ep
    return ep

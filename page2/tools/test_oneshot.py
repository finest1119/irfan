"""Pure-Python tests for the one-shot pipeline (no Blender). Run from the repo root:

  .venv/bin/python page2/tools/test_oneshot.py          (Windows: .venv\\Scripts\\python page2\\tools\\test_oneshot.py)

Covers: terrain slope/heights (world_state), sentence-start cues, the Build #1 camera plan (windows, swaps inside
moves, never static, terrain/roof clearance, snap/travel durations, beat frame layout), camera_speed export, the
qc_oneshot detector on synthetic frames (injected cut, freeze, spike inside a move), and world_state loading.
"""
import json
import math
import sys
import tempfile
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PAGE2 / "blender"))
sys.path.insert(0, str(PAGE2 / "tools"))
import mh_paths as M  # noqa: E402

M.add_import_paths()
import camera_plan as C  # noqa: E402
import gen_world_state as G  # noqa: E402
import qc_oneshot as Q  # noqa: E402
import synth_timings as ST  # noqa: E402

sys.modules.setdefault("test_oneshot", sys.modules[__name__])   # worlds.py imports the fake worlds by module name
EP = PAGE2 / "episodes" / "build-01" / "episode.json"
FAILS = []


def ok(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def test_terrain():
    print("terrain")
    mx, p95 = G.slope_stats(step=2)
    ok(mx <= 18.6, "max slope (no creek channel/pond bowl) %.1f deg <= ~18" % mx)
    ok(abs((G.PAD_Z - G.FALL_BOT_Z) / G.FT - 65.0) < 1.0, "pad is 65 ft above the ram pump")
    ok(20.5 < G.RIDGE_Z < 24.5, "ridge crest %.2f m = 70-80 ft above the house floor" % G.RIDGE_Z)
    px, py, half = G.PAD
    flat = [G.height(px + dx, py + dy) for dx in (-half, 0, half) for dy in (-half, 0, half)]
    ok(max(flat) - min(flat) < 0.05, "ridge pad is flat (spread %.3f m)" % (max(flat) - min(flat)))
    ws = M.world_state()
    loc = M.location(ws)
    ok(loc["zones"]["ridge_pad"]["pos"][2] == G.PAD_Z, "world_state ridge_pad matches the generator")
    lot = loc["lot"]["outline"]
    ok(max(p[0] for p in lot) >= px + half, "ridge pad inside the lot outline")
    hf = M.terrain_height_fn(loc)
    ok(abs(hf(0, 0)) < 0.01, "house pad z=0")
    ok(M.placed_builds(ws) == [], "no placed builds yet (builds[] empty)")
    fake = {"locations": {"mercer_hollow": {"builds": [
        {"id": "a", "status": "approved", "location": "mercer_hollow", "interior": None},
        {"id": "b", "status": "draft", "location": "mercer_hollow", "interior": None},
        {"id": "c", "status": "posted", "location": "mercer_hollow", "interior": "garage"}]}}}
    ok([b["id"] for b in M.placed_builds(fake)] == ["a"], "placed_builds filters status + interior")
    ok([b["id"] for b in M.placed_builds(fake, interior="garage")] == ["c"], "placed_builds per interior")


def test_cues():
    print("cues")
    words = [{"word": w, "norm": w.lower().strip(".,?!"), "start": i * 0.4, "end": i * 0.4 + 0.3, "beat": "b"}
             for i, w in enumerate("Storm rolls through. Again. Bolts was done waiting.".split())]
    beat = {"id": "b", "start": 0.0, "duration": 4.0}
    ok([round(t, 3) for t in C.sentence_starts(words)] == [0.0, 1.2, 1.6], "sentence starts")
    ok(round(C.resolve_cue(2, words, beat), 3) == 1.6, "cue = sentence index")
    ok(round(C.resolve_cue("bolts", words, beat), 3) == 1.6, "cue = word prefix")
    ok(C.resolve_cue(0.5, words, beat) == 0.5, "cue = seconds")


def build01_plan(tmp):
    ep = M.load_json(EP)
    tim, cap = ST.synth(ep)
    loc = M.location(M.world_state())
    plan, speed = C.build_plan(ep, tim, cap["words"], loc, M.terrain_height_fn(loc), extra_anchors=ep.get("anchors"))
    return ep, tim, plan, speed, loc


def test_plan():
    print("build-01 plan")
    ep, tim, plan, speed, loc = build01_plan(None)
    fps = plan["fps"]
    ok(sum(len(b["text"].split()) for b in ep["beats"]) == 265, "VO = 265 words")
    ok(plan["frames"] == sum(int(round(b["duration"] * fps)) for b in tim["beats"]), "frames = sum of beat frames")
    W = plan["windows"]
    ok(all(W[i]["f1"] < W[i + 1]["f0"] for i in range(len(W) - 1)), "move windows ordered, no overlap")
    snaps = [w for w in W if w["kind"] == "snap"]
    trav = [w for w in W if w["kind"] in ("travel", "section")]
    ok(all(5 <= w["f1"] - w["f0"] + 1 <= 13 for w in snaps), "snaps 0.2-0.4 s")
    ok(all(30 <= w["f1"] - w["f0"] + 1 <= 61 for w in trav), "travels 1-2 s")
    ok(len(W) >= 15, "%d moves in %.0f s (about one per sentence)" % (len(W), plan["frames"] / fps))
    wins = [(w["f0"], w["f1"]) for w in W]
    bad = [e for e in plan["events"] if e["f"] > 1 and not Q.in_windows(e["f"], wins, 0)]
    ok(not bad, "every preset/section/cast swap is inside a move (%s)" % bad[:2])
    presets = [(e["f"], e["value"]) for e in plan["events"] if e["kind"] == "preset"]
    ok([p[1] for p in presets] == ["dusk", "day", "dusk"], "preset sequence dusk -> day -> dusk")
    ok(not C.static_runs(speed, fps), "never static > 1 s (plan)")
    hf = M.terrain_height_fn(loc)
    obst = C.obstacles_from(loc)
    under, inside = [], []
    for f in range(1, plan["frames"] + 1):
        x, y, z = plan["cam"][f][:3]
        if C.state_at(plan, "section", f):
            continue
        if z < hf(x, y) + 0.5:
            under.append(f)
        for (n, x0, x1, y0, y1, zt) in obst:
            if x0 < x < x1 and y0 < y < y1 and z < zt:
                inside.append((f, n))
    ok(not under, "camera above terrain (bad frames: %s)" % under[:5])
    ok(not inside, "camera never inside the house/garage/workshop (%s)" % inside[:3])
    jump = max(math.dist(plan["cam"][f][:3], plan["cam"][f + 1][:3]) for f in range(1, plan["frames"]))
    ok(jump < 60.0, "no teleport between consecutive frames (max step %.1f m)" % jump)
    holds = [s for s in speed if s["move"] == "hold"]
    ok(min(s["px"] for s in holds) >= 0.5, "hold motion >= 0.5 px/frame")
    secs = [e for e in plan["events"] if e["kind"] == "section"]
    ok(len(secs) == 2 and secs[0]["value"] == "cable" and secs[1]["value"] is None, "cut-away on then off")
    return plan, speed


def _frames(tmp, n=120, cut=None, freeze=None):
    import numpy as np
    from PIL import Image
    d = Path(tmp)
    rng = np.random.default_rng(3)
    from PIL import ImageFilter

    def smooth_noise():      # low-frequency texture: a 1 px pan changes little, a cut changes a lot
        n = Image.fromarray(rng.integers(0, 255, (240, 135, 3), dtype=np.uint8)).filter(ImageFilter.GaussianBlur(6))
        a = np.asarray(n, dtype=np.float32)
        a = (a - a.min()) / max(1e-3, a.max() - a.min()) * 255
        return a.astype(np.uint8)
    base, other = smooth_noise(), smooth_noise()
    for f in range(1, n + 1):
        k = f
        if freeze and freeze[0] <= f <= freeze[1]:
            k = freeze[0]
        img = np.roll(base, k, axis=1)                  # smooth pan: 1 px / frame
        if cut and f >= cut:
            img = np.roll(other, k, axis=1)
        Image.fromarray(img).save(str(d / ("%04d.jpg" % f)), quality=95)
    return d


def test_qc():
    print("qc_oneshot")
    plan = {"fps": 30, "windows": [{"f0": 60, "f1": 70}], "events": [{"f": 65, "kind": "preset", "value": "day"},
                                                                      {"f": 20, "kind": "cast", "value": {}}],
            "hidden_joins": []}
    speed = [{"f": f, "px": 2.0} for f in range(1, 121)]
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2, \
            tempfile.TemporaryDirectory() as t3:
        d = Q.diffs_from_dir(_frames(t1, cut=40))
        fails, _ = Q.check(plan, speed, d)
        ok(any(x["type"] == "CUT" and x["f"] == 40 for x in fails), "cut at f40 (outside moves) flagged")
        ok(any(x["type"] == "SWAP_ON_HOLD" and x["f"] == 20 for x in fails), "cast swap on a hold flagged")
        d = Q.diffs_from_dir(_frames(t2, cut=64))
        fails, _ = Q.check(plan, speed, d)
        ok(not any(x["type"] == "CUT" for x in fails), "spike inside a planned move is not a cut")
        d = Q.diffs_from_dir(_frames(t3, freeze=(80, 115)))
        fails, _ = Q.check(plan, speed, d)
        ok(any(x["type"] == "STATIC_PIXELS" for x in fails), "36-frame freeze flagged as static")
    sp = [{"f": f, "px": 0.0 if 10 <= f <= 50 else 2.0} for f in range(1, 121)]
    fails, _ = Q.check({"fps": 30, "windows": [], "events": [], "hidden_joins": []}, sp, None)
    ok(any(x["type"] == "STATIC_PLAN" for x in fails), "static plan run flagged")


def test_whitelist():
    with tempfile.TemporaryDirectory() as t1:
        d = Q.diffs_from_dir(_frames(t1, cut=40))
    plan = {"fps": 30, "windows": [], "events": [], "hidden_joins": [[39, 41]]}
    fails, _ = Q.check(plan, [{"f": f, "px": 2.0} for f in range(1, 121)], d)
    ok(not any(x["type"] == "CUT" for x in fails), "whitelisted hidden join is not a cut")


def test_spots():
    print("spots")
    ws = M.world_state()
    loc = M.location(ws)
    ep = M.load_json(EP)
    r = C.SpotResolver(loc, ep["spots"], ep.get("anchors"), ep.get("sections"), M.terrain_height_fn(loc))
    for k in list(loc["camera_spots"]) + list(ep["spots"]):
        v = r.view(k)
        ok(v.lens > 10 and C.length(C.sub(v.look, v.pos)) > 0.5, "spot %s resolves" % k)


# ------------------------------------------------------------------ Page 3 compact oneshot block + world registry
P3_EP = PAGE2.parent / "page3" / "episodes" / "2026-11-24-c5-water-tower-sample" / "episode.json"
# test-only fake world: a few WORLDS-SPEC.md (Page 3) coordinates, so the adapter can run without hometown_usa
P3_FAKE = {
    "anchors": {"faucet_kitchen": [197.0, 161.6, 1.75], "wall_pipes": [197.0, 161.95, 1.0],
                "water_main_slice": [200.0, 141.0, -1.6], "treatment_plant": [-655.0, -190.0, 4.0],
                "water_tower": [-260.0, 430.0, 48.0], "suburb_wide": [230.0, 230.0, 0.0]},
    "cams": {"faucet_kitchen": {"pos": [196.2, 160.4, 1.9], "lens": 35}, "wall_pipes": {"pos": [197.0, 165.5, 1.6]},
             "water_main_slice": {"pos": [203.0, 136.5, 0.8], "lens": 24},
             "treatment_plant": {"pos": [-560.0, -300.0, 60.0]}, "water_tower": {"pos": [-200.0, 370.0, 40.0]},
             "suburb_wide": {"pos": [480.0, -40.0, 120.0], "lens": 35}}}


def p3_raw():
    """The Page 3 sample reduced to its compact oneshot block (page3 may also write explicit shot.camera keys;
    those are kept by the adapter, so the adapter tests strip them to stay independent of make_episode changes)."""
    import copy
    ep = copy.deepcopy(M.load_json(P3_EP))
    for b in ep["beats"]:
        b.get("shot", {}).pop("camera", None)
    return ep


def _fake_plan_anchors(state):
    return P3_FAKE


_SPY = {}


def _spy_plan_anchors(state):
    _SPY["ep"] = state["episode"]
    return P3_FAKE


def p3_plan(ep=None, fake=True):
    import worlds as WR
    ep = ep or p3_raw()
    if fake:
        WR.PLAN_ANCHORS["_test_hometown"] = ("test_oneshot", "_fake_plan_anchors")
        ep = dict(ep, oneshot=dict(ep["oneshot"], world="_test_hometown"))
    exp, loc, hf, extra, info = WR.plan_inputs(ep)
    tim, cap = ST.synth(exp)
    plan, speed = C.build_plan(exp, tim, cap["words"], loc, hf, extra_anchors=extra)
    return exp, tim, plan, speed, info


def test_registry():
    import worlds as WR
    print("world registry")
    ep = p3_raw()
    reg = set(WR.registered_worlds())
    ok({"mercer_hollow"} <= reg, "registry has mercer_hollow (+ any others: %s)" % sorted(reg))
    try:
        WR.plan_inputs(dict(ep, oneshot=dict(ep["oneshot"], world="_no_such_world")))
        ok(False, "an unregistered world must fail")
    except WR.WorldNotRegistered as ex:
        msg = str(ex)
        ok("_no_such_world_plan.py" in msg and "PLAN_ANCHORS" in msg and "mercer_hollow" in msg,
           "unregistered world fails clearly (names the missing files/entries + registered worlds)")
    if "hometown_usa" in reg:
        e3, loc3, _hf, _x, info3 = WR.plan_inputs(ep)
        ok(info3["world"] == "hometown_usa" and "water_tower" in loc3["anchors"], "hometown_usa auto-registers")
    WR.PLAN_ANCHORS["_spy"] = ("test_oneshot", "_spy_plan_anchors")
    e4, *_r = WR.plan_inputs(dict(ep, oneshot=dict(ep["oneshot"], world="_spy")))
    ok(_SPY.get("ep") is e4, "plan_anchors gets the SAME expanded episode object build_plan uses")
    b01 = M.load_json(EP)
    e2, loc, hf, extra, info = WR.plan_inputs(b01)
    ok(info["world"] == "mercer_hollow" and e2 is b01, "build-01 resolves to mercer_hollow, episode untouched")
    pa = WR.mercer_plan_anchors({"episode": b01})
    tos = [k["to"] for b in b01["beats"] for k in b["shot"].get("camera", []) if isinstance(k.get("to"), str)]
    ok(all(t in pa["anchors"] and t in pa["cams"] for t in tos), "every build-01 camera `to` has ANC + CAM (%d ids, "
       "missing %s)" % (len(set(tos)), [t for t in tos if t not in pa["anchors"]]))
    ok(all(k in pa["anchors"] for k in ("porch", "spot_porch", "street_wide", "rotor_hub", "turbine_head")),
       "Mercer anchors: zones + legacy spot_<id> aliases + camera/episode spot ids + episode anchors")
    tim, cap = ST.synth(b01)
    plan2, _s = C.build_plan(e2, tim, cap["words"], loc, hf, extra_anchors=extra)
    _e, _t, plan1, _s1, _l = build01_plan(None)
    ok(plan1["cam"] == plan2["cam"], "registry path gives the identical build-01 camera")
    print("    label anchors without a plan-time position: %s" % (info["label_missing"] or "none"))


def test_adapter():
    print("Page 3 adapter (fake world, WORLDS-SPEC coordinates)")
    raw = p3_raw()
    exp, notes = C.expand_oneshot(raw)
    keys = [b["shot"]["camera"] for b in exp["beats"]]
    ok(all(len(k) == 1 for k in keys), "one camera key per beat")
    ok(keys[0][0]["move"] == "none" and keys[0][0]["hold"]["type"] == "drift", "beat 1 drift = opening hold")
    ok(keys[5][0]["move"] == "none" and keys[5][0]["hold"]["type"] == "orbit", "twist orbit on same stop = hold change")
    ok(keys[-1][0]["move"] == "backout" and keys[-1][0]["to"] == raw["oneshot"]["stops"][0], "last = backout")
    ok(all(isinstance(k[0]["cue"], float) and k[0]["cue"] == 0.0 for k in keys), "cue = beat start (float 0.0)")
    ok(keys[1][0].get("section") == "wall_pipes" and abs(keys[1][0]["dur"] - 1.8) < 1e-9, "section dur from block")
    ok("camera" not in raw["beats"][0]["shot"], "source episode not modified")
    exp, tim, plan, speed, info = p3_plan()
    fps = plan["fps"]
    W = plan["windows"]
    ok([w["kind"] for w in W] == ["section", "section", "travel", "crane", "travel", "backout"],
       "move windows %s" % [w["kind"] for w in W])
    ok(plan["frames"] == sum(int(round(b["duration"] * fps)) for b in tim["beats"]), "frames = sum of beat frames")
    g0 = 1
    for b, tb in zip(plan["beats"], tim["beats"]):
        ok(b["f0"] == g0, "beat %s starts at global %d (= overlay_v2 g0 + 1)" % (b["id"], g0)) if b["idx"] < 2 else None
        g0 += int(round(tb["duration"] * fps))
    ok(all(W[i]["f1"] < W[i + 1]["f0"] for i in range(len(W) - 1)), "windows ordered, no overlap")
    ok(not C.static_runs(speed, fps), "never static > 1 s")
    ok(C.state_at(plan, "section", W[1]["f1"]) == "water_main_slice", "back-to-back sections: 2nd stays open")
    ok(C.state_at(plan, "section", W[2]["f1"]) is None, "section closes on the next move")
    bo = W[-1]
    n = plan["frames"]
    ok(plan["cam"][n] == plan["cam"][1], "the reel's LAST frame is exactly the frame-1 view (loop)")
    settle = n - bo["f1"]
    ok(9 <= settle <= 15, "backout ends %d frames (0.3-0.5 s) before the end" % settle)
    ok(bo["f1"] - bo["f0"] + 1 == int(round(exp["oneshot"]["move_durations_s"]["backout"] * fps)),
       "backout keeps its full duration")
    a0, a1 = plan["cam"][bo["f0"] - 1][:3], plan["cam"][bo["f1"]][:3]
    plen = sum(math.dist(plan["cam"][f][:3], plan["cam"][f + 1][:3]) for f in range(bo["f0"] - 1, bo["f1"]))
    ok(plen < 1.35 * math.dist(a0, a1) + 60.0, "backout is one direct arc (%.0f m path, %.0f m direct)"
       % (plen, math.dist(a0, a1)))
    hold_ok = True
    for f in range(2, n + 1):                   # holds move the camera <= ~5 % of the subject distance per s
        if speed[f - 1]["move"] != "hold":
            continue
        d = math.dist(plan["cam"][f][:3], plan["cam"][f][3:6])
        if math.dist(plan["cam"][f][:3], plan["cam"][f - 1][:3]) * fps > 0.05 * d + 1e-9:
            hold_ok = False
    ok(hold_ok, "hold motion scales with subject distance")
    ok(all(len(str(v).split(".")[-1]) <= 6 for v in plan["cam"][100][:6]), "plan positions stored to 1e-6 m")
    jump = max(math.dist(plan["cam"][f][:3], plan["cam"][f + 1][:3]) for f in range(1, plan["frames"]))
    ok(jump < 400.0, "no teleport (max step %.1f m/frame)" % jump)
    sp = plan.get("spark")
    ok(sp and len(sp["track"]) == plan["frames"] + 1 and all(t[3] > 0 for t in sp["track"][1:]),
       "spark track per frame, visible (ice)")
    ok(abs(sp["colors"]["ice"][2] - 1.0) < 1e-3, "spark colours as linear rgb")
    fails = [x for x in Q.check(plan, speed)[0] if x["type"] != "HOLD_TOO_LONG"]   # compact-only sample: 1 key/beat
    ok(not fails, "qc_oneshot plan checks pass (%s)" % fails[:2])
    return plan


def test_portal():
    print("portal move")
    raw = p3_raw()
    oc = dict(raw["oneshot"])
    oc["moves"] = list(oc["moves"])
    oc["moves"][4] = "portal"                      # tower beat: dive instead of crane
    oc["spark"] = ["ice", "ice", "ice", "amber", "amber", "off", "ice", "ice"]
    exp, tim, plan, speed, info = p3_plan(dict(raw, oneshot=oc))
    pw = [w for w in plan["windows"] if w["kind"] == "portal"]
    ok(len(pw) == 1 and "join" in pw[0] and abs((pw[0]["f1"] - pw[0]["f0"] + 1) - 15) <= 1, "one 0.5 s portal window")
    j = pw[0]["join"]
    ok([j - 1, j + 1] in plan["hidden_joins"], "portal join whitelisted for QC")
    ev = [e for e in plan["events"] if e["kind"] == "portal"]
    ok(len(ev) == 1 and ev[0]["f"] == j and ev[0]["value"] == "water_tower", "portal event at the join frame")
    ok(speed[j - 1].get("join") and speed[j - 1]["px"] < 1000, "camera_speed join frame clamped + flagged")
    pre, post = plan["cam"][j - 1], plan["cam"][j]
    ok(math.dist(pre[:3], pre[3:6]) < 0.1 * math.dist(plan["cam"][pw[0]["f0"] - 1][:3], pre[3:6]) + 1.0,
       "dive ends filling the frame (close to the surface)")
    ok(math.dist(post[:3], [-200.0, 370.0, 40.0]) > 1.0, "emerges behind the target camera, moving in")
    ok(plan["cam"][pw[0]["f1"]][:3] == [-200.0, 370.0, 40.0], "portal arrives on CAM_water_tower")
    sev = plan["spark"]["events"]
    ok([e["value"] for e in sev] == ["ice", "amber", "off", "ice"], "spark colour events")
    off = [e for e in sev if e["value"] == "off"][0]["f"]
    tr = plan["spark"]["track"]
    ok(0 < tr[off + 2][3] < tr[off - 1][3] and tr[off + 10][3] == 0.0, "spark off = 0.3 s fade to radius 0")
    steps = [math.dist(plan["cam"][f][:3], plan["cam"][f + 1][:3]) for f in range(1, plan["frames"])
             if f + 1 != j]
    ok(max(steps) < 400.0, "no other teleport (max step %.1f m/frame)" % max(steps))
    fails = [x for x in Q.check(plan, speed)[0] if x["type"] != "HOLD_TOO_LONG"]   # compact-only sample: 1 key/beat
    ok(not fails, "qc passes with a portal (%s)" % fails[:2])



def test_pushin_and_blur():
    print("same-stop snap/portal push-in + 2D blur spec")
    import oneshot_blur as OB
    raw = p3_raw()
    oc = dict(raw["oneshot"], moves=list(raw["oneshot"]["moves"]), stops=list(raw["oneshot"]["stops"]))
    oc["moves"][2], oc["stops"][2] = "snap", oc["stops"][1]       # main: snap on wall_pipes (after its section)
    oc["moves"][5] = "portal"                                       # twist: portal to water_tower (already there)
    exp, tim, plan, speed, info = p3_plan(dict(raw, oneshot=oc))
    W = plan["windows"]
    ok([w["kind"] for w in W][:2] == ["section", "snap"] and sum(w["kind"] == "portal" for w in W) == 0,
       "same-stop snap/portal become snap push-ins (%s)" % [w["kind"] for w in W])
    for w in [w for w in W if w["kind"] == "snap"]:
        a, b = plan["cam"][w["f0"] - 1], plan["cam"][w["f1"]]
        d0, d1 = math.dist(a[:3], a[3:6]), math.dist(b[:3], b[3:6])
        ok(0.5 <= d1 / d0 <= 0.65 and b[6] > a[6] * 1.08, "push-in %.0f %% closer, lens x%.2f" %
           (100 * (1 - d1 / d0), b[6] / a[6]))
    ok(C.state_at(plan, "section", W[1]["f1"]) == "wall_pipes", "section stays open through the push-in")
    oc2 = dict(raw["oneshot"], moves=list(raw["oneshot"]["moves"]))
    oc2["moves"][4] = "portal"
    _e, _t, plan2, speed2, _i = p3_plan(dict(raw, oneshot=oc2))
    cs = {"fps": plan2["fps"], "frames": plan2["frames"], "beats": plan2["beats"], "windows": plan2["windows"],
          "hidden_joins": plan2["hidden_joins"], "speed": speed2,
          "whoosh": [{"f": w["f0"], "kind": w["kind"], "frames": w["f1"] - w["f0"] + 1, "gain_db": -20}
                     for w in plan2["windows"]]}
    bs = OB.blur_spec(cs)
    j = [w for w in plan2["windows"] if w["kind"] == "portal"][0]["join"]
    ok(bs["frames"] and max(x["px"] for x in bs["frames"]) <= 60.0, "blur clamped at 60 px")
    ok(all(x["f"] != j for x in bs["frames"]) and bs["skipped_join_frames"] == 1, "portal join frame not blurred")
    ok(all(speed2[x["f"] - 1]["move"] != "hold" for x in bs["frames"]), "holds never blurred")
    ok(any(x["mode"] == "radial" for x in bs["frames"]), "portal/snap = radial blur")
    ok(len(bs["whoosh"]) == len(plan2["windows"]) and all(abs(w["t"] - (w["f"] - 1) / 30.0) < 1e-3 and w["lf"] >= 1 for w in bs["whoosh"]),
       "one whoosh cue per move with times")



def test_hold_caps():
    print("hold caps (25 % of d / 18 deg per hold, macro drift -> orbit, min motion wins)")
    v = C.View((0.0, -10.0, 2.0), (0.0, 0.0, 2.0), 28.0)            # d = 10 m
    sp = C.cap_hold(v, {"type": "drift"}, 36.0)
    tr, _deg = C.hold_total(v, sp, 36.0)
    ok(abs(tr - 0.25) < 1e-6 and sp.get("_capped"), "36 s drift capped at 0.25 d (%.3f)" % tr)
    sp = C.cap_hold(v, {"type": "drift"}, 10.0)
    ok(abs(C.hold_total(v, sp, 10.0)[0] - 0.15) < 1e-6 and not sp.get("_capped"), "10 s drift keeps 1.5 %/s")
    sp = C.cap_hold(v, {"type": "crane"}, 30.0)
    ok(abs(C.hold_total(v, sp, 30.0)[0] - 0.25) < 1e-6, "crane capped the same way")
    sp = C.cap_hold(v, {"type": "orbit", "deg_s": -4.0}, 30.0)
    ok(abs(C.hold_total(v, sp, 30.0)[1] - 18.0) < 1e-6 and sp["deg_s"] < 0, "orbit capped at 18 deg, sign kept")
    m = C.View((0.0, -0.03, 0.0), (0.0, 0.0, 0.0), 35.0)            # 3 cm macro subject
    sp = C.cap_hold(m, {"type": "drift", "speed": 0.6}, 30.0)
    ok(sp["type"] == "orbit" and C.hold_total(m, sp, 30.0)[1] <= 18.0 + 1e-6, "macro drift -> slow orbit <= 18 deg")
    b = C.boosted(v, C.cap_hold(v, {"type": "drift"}, 600.0), 30)
    ok(b.get("_boost", 1.0) > 1.0, "minimum 0.6 px/frame wins over the cap on a very long hold")
    exp, tim, plan, speed, info = p3_plan()
    bad = [h for h in plan["holds"] if (h["travel_x_d"] > 0.25 + 1e-6 or h["orbit_deg"] > 18 + 1e-6)
           and not h.get("min_motion_wins")]
    ok(not bad, "every Page 3 hold within the caps or reported as min-motion override (%s)" % bad[:1])
    ok(not C.static_runs(speed, plan["fps"]), "still never static > 1 s")



def test_native_variants_holds():
    print("native keys win + sub-stop variants + hold-length rule")
    raw = p3_raw()
    native = [{"move": "travel", "to": "wall_pipes__alt", "dur": 1.0, "cue": 0.0, "hold": {"type": "drift"}},
              {"move": "snap", "to": "wall_pipes__detail", "dur": 0.3, "cue": 1, "hold": {"type": "drift"}}]
    raw["beats"][1]["shot"]["camera"] = native
    exp, notes = C.expand_oneshot(raw)
    ok(exp["beats"][1]["shot"]["camera"] == native and len(exp["beats"][2]["shot"]["camera"]) == 1,
       "beat with native shot.camera keeps it; other beats come from the oneshot block")
    exp, tim, plan, speed, info = p3_plan(raw)
    ok([w["to"] for w in plan["windows"]][:2] == ["wall_pipes__alt", "wall_pipes__detail"], "native keys planned")
    res = C.SpotResolver({"anchors": P3_FAKE["anchors"], "camera_spots": {
        k: {"pos": c["pos"], "look_at": P3_FAKE["anchors"][k], "lens_mm": c.get("lens", 28)}
        for k, c in P3_FAKE["cams"].items()}})
    base = res.view("water_tower")
    det, alt = res.view("water_tower__detail"), res.view("water_tower__alt")
    d0 = C.length(C.sub(base.look, base.pos))
    ok(abs(C.length(C.sub(det.look, det.pos)) / d0 - 0.6) < 1e-9 and det.look == base.look, "__detail = 40 % closer")
    r0, r1 = C.sub(base.pos, base.look), C.sub(alt.pos, alt.look)
    ang = math.degrees(math.atan2(r1[1], r1[0]) - math.atan2(r0[1], r0[0])) % 360
    ok(abs(ang - 35.0) < 1e-6 and abs(C.length(r1) - d0) < 1e-9, "__alt = same anchor from 35 deg around")
    ok(res.anchor_pos("water_tower__alt") == res.anchor_pos("water_tower"), "variant anchor = stop anchor")
    res2 = C.SpotResolver({"anchors": dict(P3_FAKE["anchors"]), "camera_spots": {
        "water_tower__detail": {"pos": [-250.0, 420.0, 45.0], "look_at": [-260.0, 430.0, 48.0]}}})
    ok(res2.view("water_tower__detail").pos == (-250.0, 420.0, 45.0), "a world-registered variant wins")
    b01 = M.load_json(EP)
    ok(any(k.get("_auto") == "hold_split" for b in b01["beats"] for k in b["shot"]["camera"]),
       "build-01 generator added hold-split keys")
    _ep, _tim, plan1, _sp, _loc = build01_plan(None)
    hf, hw, longest = C.check_holds(plan1)
    ok(not hf and not hw and longest["s"] <= 9.0, "build-01: longest hold %.1f s (<= 9 s)" % longest["s"])
    fake = {"fps": 30, "frames": 500, "windows": [{"f0": 100, "f1": 110}], "beats": None, "events": [],
            "hidden_joins": []}
    hf, hw, longest = C.check_holds(fake)
    ok(len(hf) == 1 and hf[0]["f0"] == 111 and longest["s"] > 10, "hold over 10 s fails (%.1f s)" % longest["s"])
    fails, info = Q.check(fake, [{"f": f, "px": 2.0} for f in range(1, 501)])
    ok(any(x["type"] == "HOLD_TOO_LONG" for x in fails), "qc_oneshot fails a hold over 10 s")
    fake2 = {"fps": 30, "frames": 400, "windows": [{"f0": 100, "f1": 110}, {"f0": 390, "f1": 395}]}
    hf, hw, _l = C.check_holds(fake2)
    ok(not hf and len(hw) == 1, "hold of 9.3 s warns, does not fail")



def test_portal_exit_and_alias_pushin():
    print("backout exits a portal set first; alias snap = push-in")
    raw = p3_raw()
    oc = dict(raw["oneshot"], moves=list(raw["oneshot"]["moves"]), stops=list(raw["oneshot"]["stops"]))
    oc["moves"][4] = "portal"                                         # tower: portal INTO an "enlarged set"
    oc["moves"][6], oc["stops"][6] = "snap", "water_tower__detail"    # why: still inside (alias of the same stop)
    exp, tim, plan, speed, info = p3_plan(dict(raw, oneshot=oc))
    fps, n = plan["fps"], plan["frames"]
    pw = [w for w in plan["windows"] if w["kind"] == "portal"][0]
    sn = [w for w in plan["windows"] if w["beat"] == "why"][0]
    a, b = plan["cam"][sn["f0"] - 1], plan["cam"][sn["f1"]]
    ok(sn.get("push_in") and math.dist(b[:3], b[3:6]) < 0.7 * math.dist(a[:3], a[3:6]),
       "snap to <stop>__detail while at <stop> = push-in (alias)")
    bo = plan["windows"][-1]
    ok(bo["kind"] == "backout" and "exit_portal" in bo and "join" in bo, "backout starts with a reverse portal")
    ok([bo["join"] - 1, bo["join"] + 1] in plan["hidden_joins"], "exit join whitelisted")
    ok(any(e["kind"] == "portal" and e["value"] == "exit:water_tower" for e in plan["events"]), "exit portal event")
    out_view = plan["cam"][pw["f0"] - 1]                              # the view right before the dive in
    e1 = bo["exit_portal"][1]
    ok(math.dist(plan["cam"][e1][:3], out_view[:3]) < 0.5, "reverse portal lands on the outside view")
    arc = [plan["cam"][f][:3] for f in range(e1, bo["f1"] + 1)]
    plen = sum(math.dist(arc[i], arc[i + 1]) for i in range(len(arc) - 1))
    ok(plen < 1.35 * math.dist(arc[0], arc[-1]) + 60.0, "then ONE direct arc (%.0f m path, %.0f m direct)"
       % (plen, math.dist(arc[0], arc[-1])))
    others = [P3_FAKE["cams"][k]["pos"] for k in ("wall_pipes", "water_main_slice", "treatment_plant", "suburb_wide")]
    ok(all(min(math.dist(p, o) for p in arc) > 5.0 for o in others), "the arc passes through no other stop")
    ok(plan["cam"][n] == plan["cam"][1], "reel still ends on frame 1")
    fails = [x for x in Q.check(plan, speed)[0] if x["type"] != "HOLD_TOO_LONG"]
    ok(not fails, "qc passes (%s)" % fails[:1])
    # ep-06 pattern: portal in, then a portal back OUT near the outside view -> backout is a plain direct arc
    raw3 = p3_raw()
    raw3["beats"][4]["shot"]["camera"] = [{"move": "portal", "to": "water_tower", "dur": 0.5, "cue": 0.0}]
    raw3["beats"][5]["shot"]["camera"] = [{"move": "portal", "to": "treatment_plant__alt", "dur": 0.5, "cue": 0.0}]
    raw3["beats"][6]["shot"]["camera"] = [{"move": "snap", "to": "treatment_plant__detail", "dur": 0.3, "cue": 0.0}]
    _e, _t, plan3, _s, _i = p3_plan(raw3)
    ok("exit_portal" not in plan3["windows"][-1], "portal back out (near the outside view) clears the set: no exit hop")
    # ep-08 pattern with native keys: section X -> travel X__detail -> snap X  => push-in, not a pull-out
    raw2 = p3_raw()
    raw2["beats"][2]["shot"]["camera"] = [
        {"move": "section", "to": "water_main_slice", "dur": 1.8, "cue": 0.0, "section": "water_main_slice"},
        {"move": "travel", "to": "water_main_slice__detail", "dur": 0.8, "cue": 1},
        {"move": "snap", "to": "water_main_slice", "dur": 0.3, "cue": 2}]
    _e, _t, plan2, _s, _i = p3_plan(raw2)
    w = [w for w in plan2["windows"] if w["beat"] == "main"]
    a, b = plan2["cam"][w[2]["f0"] - 1], plan2["cam"][w[2]["f1"]]
    ok(w[2]["kind"] == "snap" and w[2].get("push_in") and math.dist(b[:3], b[3:6]) < math.dist(a[:3], a[3:6]),
       "snap back to the base stop from its __detail alias pushes in")


if __name__ == "__main__":
    test_terrain()
    test_cues()
    test_plan()
    test_qc()
    test_whitelist()
    test_spots()
    test_registry()
    test_adapter()
    test_portal()
    test_pushin_and_blur()
    test_hold_caps()
    test_native_variants_holds()
    test_portal_exit_and_alias_pushin()
    print("\n%s (%d failures)" % ("ALL PASS" if not FAILS else "FAILURES", len(FAILS)))
    sys.exit(1 if FAILS else 0)

"""Tests for page3/blender/hometown_usa_plan.py (bpy-free). Run:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python page3/tools/test_hometown_plan.py
Uses page2's registry/adapter read-only (imports only, nothing written)."""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

PAGE3 = Path(__file__).resolve().parent.parent
ROOT = PAGE3.parent
sys.path.insert(0, str(PAGE3 / "blender"))
sys.path.insert(0, str(PAGE3 / "tools"))
import hometown_usa_plan as P  # noqa: E402
import make_episode as ME  # noqa: E402

SAMPLE = PAGE3 / "episodes" / "2026-11-24-c5-water-tower-sample" / "episode.json"


class TestTables(unittest.TestCase):
    def test_stop_vocabulary(self):
        self.assertEqual(set(P.STOPS), set(ME.STOP_WORLD))
        for k, s in P.STOPS.items():
            self.assertEqual(s["w"], ME.STOP_WORLD[k], k)
            self.assertIn(s["zone"], P.ZONES, k)
            self.assertGreater(P.subject_distance(k), 0.01, k)

    def test_peel_and_slice_stops_exist(self):
        for g in list(P.PEELS.values()) + list(P.SLICES.values()):
            for s in g["stops"]:
                self.assertIn(s, P.STOPS)

    def test_macro_set(self):
        macro = {k for k in P.STOPS if P.is_macro(k)}
        self.assertTrue({k for k in P.STOPS if k.startswith("macro_")} <= macro)
        self.assertNotIn("hand_phone", macro)

    def test_host_frames(self):
        # phone: long axis up-north, screen normal up-south (towards the person)
        up = P.PHONE.rot((0, 1, 0))
        n = P.PHONE.rot((0, 0, 1))
        self.assertGreater(up[2], 0.8)
        self.assertLess(n[1], -0.8)
        self.assertAlmostEqual(P.STOPS["macro_barcode"]["anc"][2], 0.98, places=3)

    def test_rect_minus_holes_area(self):
        outer = (0.0, 10.0, 0.0, 10.0)
        holes = [(2, 4, 2, 4), (3, 6, 5, 7), (9, 12, -1, 1)]
        rs = P.rect_minus_holes(outer, holes)
        area = sum((r[1] - r[0]) * (r[3] - r[2]) for r in rs)
        self.assertAlmostEqual(area, 100 - 4 - 6 - 1)
        for r in rs:
            for h in holes:
                ov = max(0, min(r[1], h[1]) - max(r[0], h[0])) * max(0, min(r[3], h[3]) - max(r[2], h[2]))
                self.assertEqual(ov, 0)


class TestVariantsAndSplitting(unittest.TestCase):
    def test_every_stop_has_variants(self):
        self.assertEqual(len([k for k in P.VIEWS if "__inside" not in k]), 3 * len(P.STOPS))
        for k in P.STOPS:
            for v in ("__detail", "__alt"):
                self.assertIn(k + v, P.VIEWS)
                self.assertEqual(P.base_stop(k + v), k)
                self.assertGreater(P.subject_distance(k + v), 0.004, k + v)
        for k in P.STOPS:          # detail is a push-in
            self.assertLess(P.subject_distance(k + "__detail"), P.subject_distance(k), k)

    def test_native_keys_resolve_and_holds_ok(self):
        for sp in sorted((PAGE3 / "scripts").glob("*.json")):
            sc = json.loads(sp.read_text(encoding="utf-8"))
            keys, holds = ME.camera_keys(sc["beats"])
            self.assertTrue(any(keys), sp.name)
            for b, ks, hs in zip(sc["beats"], keys, holds):
                self.assertTrue(all(h <= ME.HOLD_FAIL_S for h in hs), (sp.name, b["id"], hs))
                words = [ME.norm(t) for t in b["text"].split()]
                for k in ks or []:
                    if "to" in k:
                        self.assertIn(k["to"], P.VIEWS, (sp.name, k))
                    if isinstance(k["cue"], str):
                        pre, _, n = k["cue"].partition("#")
                        self.assertGreater(len([w for w in words if w.startswith(pre)]), int(n or 0), k)
                if ks and b is sc["beats"][-1]:
                    self.assertEqual(ks[-1]["move"], "backout")

    def test_every_portal_has_an_interior(self):
        """A portal must land in a set: a nested macro set (real scale, its own Z_MACRO_* zone) or, for a portal onto
        the stop the camera is already at, the enlarged <stop>__inside set."""
        for sp in sorted((PAGE3 / "scripts").glob("*.json")):
            sc = json.loads(sp.read_text(encoding="utf-8"))
            keys, _h = ME.camera_keys(sc["beats"])
            for i, (b, ks) in enumerate(zip(sc["beats"], keys)):
                if b["move"] != "portal":
                    continue
                to = ks[0]["to"] if ks else b["stop"]
                v = P.VIEWS[to]
                self.assertTrue(v["zone"].startswith("Z_MACRO") or v["zone"] == "Z_MW_INSIDE", (sp.name, b["id"], to))
                if b["stop"] == sc["beats"][i - 1]["stop"]:
                    self.assertTrue(to.endswith("__inside"), (sp.name, b["id"], to))
            for b, ks in zip(sc["beats"], keys):      # never fly out of an enlarged set: always a portal back
                prev = None
                for k in ks or []:
                    if prev and "__inside" in prev and "__inside" not in k.get("to", prev) and k["move"] != "none":
                        self.assertIn(k["move"], ("portal", "backout"), (sp.name, b["id"], k))
                    prev = k.get("to", prev)

    def test_validator_fails_unsplittable_hold(self):
        sc = json.loads((PAGE3 / "scripts" / "_sample.json").read_text(encoding="utf-8"))
        b = sc["beats"][1]
        b["text"] = " ".join(["water"] * 3) + " " + "x" * 2
        keys, holds = ME.camera_keys([dict(sc["beats"][0], text=" ".join(["flow"] * 60))] + sc["beats"][1:])
        self.assertTrue(all(h <= ME.HOLD_FAIL_S for h in holds[0]), "a long first beat is split at words")


class TestRegistry(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "page2" / "blender"))
        import worlds as WR
        self.WR = WR

    def test_plan_inputs_resolve_and_tune(self):
        ep = json.loads(SAMPLE.read_text(encoding="utf-8"))
        before = copy.deepcopy(ep)
        exp, loc, hf, extra, info = self.WR.plan_inputs(ep)
        self.assertEqual(info["world"], "hometown_usa")
        self.assertEqual(info["anchor_source"], "hometown_usa_plan.plan_anchors")
        self.assertFalse(info["label_missing"])
        holds = [k["hold"] for b in exp["beats"] for k in b["shot"]["camera"] if "hold" in k]
        if P.HOLD_TUNING:
            self.assertTrue(holds and all(h.get("_ed") for h in holds), "every adapter hold tuned")
        else:                                   # page2 camera_plan owns hold scaling now (cap_hold)
            self.assertFalse(any(h.get("_ed") for h in holds), "page3 tuning off: holds left to page2")
        self.assertEqual(ep, before, "source episode untouched")
        self.assertTrue(any(b["shot"].get("camera") for b in ep["beats"]), "make_episode wrote native keys")

    @unittest.skipUnless(P.HOLD_TUNING, "hold tuning retired: page2 scales holds itself")
    def test_tune_idempotent_and_macro_orbit(self):
        old = P.HOLD_TUNING
        P.HOLD_TUNING = True
        try:
            self._tune()
        finally:
            P.HOLD_TUNING = old

    def _tune(self):
        ep = json.loads(SAMPLE.read_text(encoding="utf-8"))
        oc = dict(ep["oneshot"], stops=list(ep["oneshot"]["stops"]))
        oc["stops"][1] = "macro_barcode"
        sys.path.insert(0, str(ROOT / "page2" / "blender"))
        import camera_plan as C
        exp, _n = C.expand_oneshot(dict(ep, oneshot=oc))
        P.tune_holds(exp)
        once = copy.deepcopy(exp)
        P.tune_holds(exp)
        self.assertEqual(once, exp)
        h = exp["beats"][1]["shot"]["camera"][0]["hold"]
        self.assertEqual(h["type"], "orbit")
        self.assertEqual(abs(h["deg_s"]), P.ORBIT_DEG_S)
        h0 = exp["beats"][0]["shot"]["camera"][0]["hold"]
        self.assertAlmostEqual(h0["speed"], round(P.DRIFT_FRAC_S * P.subject_distance("faucet_kitchen"), 5))

    def test_untouched_without_adapter(self):
        ep = {"oneshot": {"world": "hometown_usa"}, "beats": [{"id": "a", "shot": {"camera": [
            {"move": "none", "to": "faucet_kitchen", "hold": {"type": "drift"}}]}}]}
        self.assertEqual(P.tune_holds(ep), [])
        self.assertNotIn("speed", ep["beats"][0]["shot"]["camera"][0]["hold"])


class TestTimeline(unittest.TestCase):
    def plan(self, ep_id="2026-11-24-ed-08-traffic-light-loop"):
        p = PAGE3 / "_plan_test" / ep_id / "oneshot" / "plan.json"
        if not p.exists():
            self.skipTest("run page3/tools/plan_all.py first")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_loop_lid_open_through_snap(self):
        plan = self.plan()
        lids = P.lid_amounts(plan, "intersection")["loop"]
        w = [x for x in plan["windows"] if x["kind"] == "snap" and P.base_stop(x.get("stop")) == "road_loop_slice"][0]
        self.assertTrue(all(lids[f] == 1.0 for f in range(w["f0"], w["f1"] + 1)), "lid stays open during the snap")
        self.assertEqual(lids[1], 0.0)

    def test_clip_planes_macro(self):
        plan = self.plan("2026-11-24-ed-04-barcode-gum-1974")
        cs = [P.clip_planes(plan, f)[0] for f in range(1, plan["frames"] + 1)]
        self.assertLess(min(cs), 0.0005)
        self.assertLessEqual(max(c[1] / c[0] for c in (P.clip_planes(plan, f) for f in range(1, plan["frames"] + 1))),
                             1e5 + 1)

    def test_beat_range_and_zones(self):
        plan = self.plan("2026-11-24-ed-09-gps-relativity")
        b = plan["beats"][1]
        self.assertEqual(P.beat_range(plan, b["f0"] + 10, b["f0"] + 20), (b["f0"], b["f0"] + b["frames"] - 1))
        sky = [w for w in plan["windows"] if w.get("stop") == "sky_satellites"][0]
        zs = P.zones_for_range(plan, "hand_phone", sky["f1"] + 5, sky["f1"] + 30)
        self.assertIn("Z_SKY", zs)
        self.assertNotIn("Z_HOUSE_INT", zs)

    def test_rebase_switches_inside_windows(self):
        plan = self.plan("2026-11-24-ed-03-tap-to-pay")
        wins = [(w["f0"], w["f1"]) for w in plan["windows"]]
        for f, _s in P.rebase_keys(plan, "strip_mall_checkout")[1:]:
            self.assertTrue(any(a <= f <= b for a, b in wins), "rebase at f%d is inside a move" % f)

    def test_drift_never_leaves_subject(self):
        for p in sorted((PAGE3 / "_plan_test").glob("*/oneshot/plan.json")):
            plan = json.loads(p.read_text(encoding="utf-8"))
            for h in P.hold_drift_stats(plan):
                if h["f1"] - h["f0"] > 10:
                    self.assertLessEqual(h["look_ratio"], 0.25, "%s %s" % (p.parent.parent.name, h))
                    self.assertFalse(math.isnan(h["ratio"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)

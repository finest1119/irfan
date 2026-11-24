"""Tests for page3/tools/make_episode.py (stdlib unittest).
Run: python page3/tools/test_make_episode.py   (writes only to a temp dir)
"""
from __future__ import annotations

import copy
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_episode as M  # noqa: E402

PAGE3 = HERE.parent
SAMPLE = PAGE3 / "scripts" / "_sample.json"


def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = M.load_page()

    def problems(self, s):
        return M.validate(s, self.page)[0]

    def assertFails(self, s, needle):
        p = self.problems(s)
        self.assertTrue(any(needle in x for x in p), "expected %r in %s" % (needle, p))


class TestSample(Base):
    def test_sample_valid(self):
        self.assertEqual(self.problems(sample()), [])

    def test_episode_shape(self):
        ep = M.build_episode(sample(), self.page, "2026-11-24")
        self.assertEqual(ep["id"], "2026-11-24-c5-water-tower-sample")
        self.assertEqual(ep["pipeline"], "v2")
        self.assertIsNone(ep["music"])
        for k in ("keyword", "slug", "title", "fb_caption", "hashtags", "sources", "engagement_comment", "tts",
                  "render", "beats"):
            self.assertIn(k, ep)
        self.assertEqual(ep["slug"], "water-tower-sample")
        self.assertTrue(all(isinstance(s, str) for s in ep["sources"]))
        self.assertEqual(ep["tts"]["voice"], "Sadaltager")
        self.assertIn("#EverydayDecoded", ep["hashtags"])
        one = ep["oneshot"]
        self.assertEqual(one["world"], "hometown_usa")
        n = len(ep["beats"])
        self.assertEqual([len(one[k]) for k in ("stops", "moves", "spark", "beats", "stop_chips")], [n] * 5)
        self.assertEqual(one["moves"][-1], "backout")
        for b in ep["beats"]:
            self.assertEqual(set(b), {"id", "text", "shot"})
            self.assertEqual(b["shot"]["builder"], "ed_oneshot")
            self.assertEqual(set(b["shot"]["params"]), {"stop", "move", "spark"})
            for ov in b["shot"]["overlays"]:
                self.assertIn(ov["type"], ("card", "chips", "label", "big"))  # types overlay_v2 knows

    def test_overlay_mapping(self):
        ep = M.build_episode(sample(), self.page, "2026-11-24")
        beats = {b["id"]: b for b in ep["beats"]}
        twist = beats["twist"]["shot"]["overlays"]
        self.assertEqual(twist[0], {"type": "card", "text": "TWIST", "style": "twist", "cue": "twist"})
        main = beats["main"]["shot"]["overlays"]
        self.assertEqual(main[0]["anchor"], "water_main_slice")
        outro_chips = [o for o in beats["outro"]["shot"]["overlays"] if o["type"] == "chips"]
        self.assertEqual(len(outro_chips), 1)  # merged
        self.assertEqual(outro_chips[0]["cues"], ["tell", "send"])

    def test_cli_writes_and_check(self):
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = M.main([str(SAMPLE), "--check", "--out-root", td])
            self.assertEqual(rc, 0)
            self.assertEqual(list(Path(td).iterdir()), [])  # --check writes nothing
            with redirect_stdout(buf):
                rc = M.main([str(SAMPLE), "--out-root", td, "--date", "2026-12-01"])
            self.assertEqual(rc, 0)
            out = Path(td) / "2026-12-01-c5-water-tower-sample" / "episode.json"
            self.assertTrue(out.exists())
            with redirect_stdout(buf):
                rc = M.main([str(SAMPLE), "--out-root", td, "--date", "2026-12-01"])
            self.assertEqual(rc, 1)  # refuses to overwrite without --force

    def test_cli_bad_file_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            bad = sample()
            bad["beats"][0]["stop"] = "moon_base"
            p = Path(td) / "bad.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(M.main([str(p), "--check"]), 1)


class TestValidation(Base):
    def test_unknown_stop_move_spark(self):
        s = sample()
        s["beats"][1]["stop"] = "moon_base"
        self.assertFails(s, "unknown stop")
        s = sample()
        s["beats"][1]["move"] = "zoom"
        self.assertFails(s, "unknown move")
        s = sample()
        s["beats"][1]["spark"] = "purple"
        self.assertFails(s, "unknown spark")

    def test_stop_world_mismatch(self):
        s = sample()
        s["beats"][1]["stop"] = "macro_card_chip"  # W2 not in ["W1","W3"]
        self.assertFails(s, "belongs to W2")

    def test_microwave_mesh_is_w3(self):
        self.assertEqual(M.STOP_WORLD["macro_microwave_mesh"], "W3")

    def test_word_count(self):
        s = sample()
        s["beats"][2]["text"] += " extra" * 60
        self.assertFails(s, "word count")
        s = sample()
        for b in s["beats"]:
            b["text"] = " ".join(b["text"].split()[:20])
        self.assertFails(s, "word count")

    def test_twist(self):
        s = sample()
        del s["twist_beat"]
        self.assertFails(s, "twist_beat")
        s = sample()
        s["twist_beat"] = "nope"
        self.assertFails(s, "not a beat id")
        s = sample()
        tb = [b for b in s["beats"] if b["id"] == "twist"][0]
        tb["overlays"] = [o for o in tb["overlays"] if o["type"] != "twist"]
        self.assertFails(s, "no TWIST card")

    def test_overlay_too_long(self):
        s = sample()
        s["beats"][0]["overlays"][0]["text"] = "X" * 41
        self.assertFails(s, "max 40")

    def test_cues(self):
        s = sample()
        s["beats"][0]["overlays"][0]["cue"] = "banana"
        self.assertFails(s, "not found in the beat text")
        s = sample()
        del s["beats"][0]["overlays"][0]["cue"]
        self.assertFails(s, "missing cue")
        s = sample()
        s["beats"][0]["overlays"][0]["cue"] = "Faucet,"  # normalised like captions.norm
        self.assertEqual(self.problems(s), [])

    def test_brands(self):
        for txt, brand in (("Pay with Visa today.", "Visa"), ("On AT&T or T-Mobile.", "AT&T"),
                           ("Lunch at McDonald’s.", "McDonald's"), ("A DOORDASH order.", "DoorDash"),
                           ("Shop at Target.", "Target")):
            s = sample()
            s["beats"][3]["text"] += " " + txt
            self.assertFails(s, brand)
        s = sample()
        s["beats"][0]["overlays"][0]["text"] = "TAP YOUR VISA"
        self.assertFails(s, "Visa")
        self.assertEqual(M.find_brands("a pineapple, a visage, our target audience"), [])
        s = sample()
        s["sources"][0]["claim"] += " (Visa contactless paper)"  # sources are exempt
        self.assertEqual(self.problems(s), [])

    def test_first_and_last_move(self):
        s = sample()
        s["beats"][0]["move"] = "snap"
        self.assertFails(s, "first beat move")
        s = sample()
        s["beats"][-1]["move"] = "drift"
        self.assertFails(s, "last beat move")

    def test_voice_and_keyword(self):
        s = sample()
        s["voice"] = "Fenrir"
        self.assertFails(s, "fixed voice")
        s = sample()
        s["keyword"] = "water: tower?"
        self.assertFails(s, "illegal in Windows")

    def test_world_not_built(self):
        s = sample()
        s["world"] = ["W1", "W3", "W5"]
        self.assertFails(s, "not supported")


class TestSpec(unittest.TestCase):
    def test_all_stops_in_worlds_spec(self):
        spec = (PAGE3 / "WORLDS-SPEC.md").read_text(encoding="utf-8")
        self.assertEqual(len(M.STOPS), 37)
        headings = set(re.findall(r"^### ([a-z_]+)", spec, re.M))
        missing = [s for s in M.STOPS if s not in headings]
        self.assertEqual(missing, [], "stops without a WORLDS-SPEC section")
        for s in M.STOPS:
            self.assertIn("ANC_%s" % s, spec)
        for m in M.MOVES:
            self.assertIn("`%s`" % m, spec)

    def test_page_json(self):
        page = M.load_page()
        self.assertEqual(page["voice"]["voice"], "Sadaltager")
        self.assertEqual(page["posting"]["timezone"], "America/New_York")
        raw = (PAGE3 / "page.json").read_text(encoding="utf-8")
        self.assertNotRegex(raw, r"\b\d{12,}\b")  # no numeric Page ID stored


if __name__ == "__main__":
    unittest.main(verbosity=2)

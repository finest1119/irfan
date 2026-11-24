#!/usr/bin/env python3
"""overlay_v2 per-episode "style" block: WJH output must not change; Page 3 style must take effect.

  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python page3/tools/test_overlay_style.py [WJH_EPISODE_DIR]

1. WJH identity: composite overlay frames (captions + every overlay type in the episode, on a flat base) with the
   reference overlay_v2 (git HEAD, i.e. before the port patch and the style block) and with the current one;
   the RGB bytes must be identical. Needs the WJH workdir (output/<slug>/ with captions + timings) and Avenir
   (macOS); skipped otherwise.
2. Page 3 style: the same frames with a "style" block -> caption highlight is amber, the twist card uses its
   bg/fg colours, and the font set switches to Montserrat.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import subprocess
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PIPE = os.path.join(ROOT, "pipeline")
sys.path.insert(0, PIPE)
import overlay_v2 as OV  # noqa: E402
from PIL import Image  # noqa: E402

AVENIR = "/System/Library/Fonts/Avenir Next.ttc"


def _wjh_episode():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return os.path.join(os.path.abspath(sys.argv.pop(1)), "episode.json")
    for p in sorted(glob.glob(os.path.join(ROOT, "episodes", "*", "episode.json")), reverse=True):
        ep = json.load(open(p))
        wd = os.path.join(ROOT, "output", ep.get("slug", "?"))
        if "style" not in ep and os.path.exists(os.path.join(wd, "captions.json")) and \
                os.path.exists(os.path.join(wd, "audio", "timings.json")):
            return p
    return None


EP = _wjh_episode()


def _reference_module():
    """overlay_v2 as committed at git HEAD, executed as if it lived in pipeline/ (same ROOT, same imports)."""
    src = subprocess.run(["git", "show", "HEAD:pipeline/overlay_v2.py"], cwd=ROOT, capture_output=True, text=True)
    if src.returncode:
        return None
    m = types.ModuleType("overlay_v2_ref")
    m.__file__ = os.path.join(PIPE, "overlay_v2.py")
    exec(compile(src.stdout, m.__file__, "exec"), m.__dict__)
    return m


def _frames(mod, ep_path, ep_override=None):
    """Composite frames at 4 points per beat on a flat base; returns {(beat, f): RGB bytes}."""
    out = {}
    real_load = json.load
    for i in range(len(json.load(open(ep_path))["beats"])):
        if ep_override is not None:
            # feed the overridden episode dict to the module's loader
            mod.json = types.SimpleNamespace(load=lambda fh, _o=ep_override: copy.deepcopy(_o)
                                             if getattr(fh, "name", "") == ep_path else real_load(fh), dumps=json.dumps)
        ep, workdir, tim, caps_d, fps, name, bc = mod._ctx(ep_path, i)
        caps = mod.Captions(caps_d, tim["total"])
        items, blur = mod.build_items(bc)
        for k in (0.15, 0.4, 0.65, 0.9):
            f = max(1, min(bc.nframes, int(round(k * bc.nframes))))
            base = Image.new("RGB", (mod.W, mod.H), (120, 150, 190))
            out[(i, f)] = mod.compose_frame(base, bc, items, caps, f, blur)
    mod.json = json
    return out


@unittest.skipUnless(EP and os.path.exists(AVENIR), "needs a rendered WJH episode workdir and Avenir (macOS)")
class WJHIdentity(unittest.TestCase):
    def test_wjh_frames_identical(self):
        ref = _reference_module()
        if ref is None:
            self.skipTest("git HEAD overlay_v2 not available")
        a = _frames(ref, EP)
        OV.apply_style({})
        b = _frames(OV, EP)
        self.assertEqual(sorted(a), sorted(b))
        diff = [k for k in a if a[k].tobytes() != b[k].tobytes()]
        self.assertEqual(diff, [], "WJH frames changed: %s" % diff[:5])
        print("\n  WJH identity: %d frames of %s identical" % (len(a), os.path.basename(os.path.dirname(EP))))


@unittest.skipUnless(EP, "needs a rendered WJH episode workdir")
class Page3Style(unittest.TestCase):
    STYLE = {"font_set": "montserrat", "highlight_color": "#FFB000", "twist_card": {"bg": "#FFB000", "fg": "#1B1F24"}}

    def tearDown(self):
        OV.apply_style({})

    def test_style_takes_effect(self):
        ep = json.load(open(EP))
        ep["style"] = self.STYLE
        # make the first card a twist card so its colours are exercised
        card = next(((i, o) for i, b in enumerate(ep["beats"]) for o in b["shot"].get("overlays", [])
                     if o["type"] == "card"), None)
        if card:
            card[1]["style"] = "twist"
        fr = _frames(OV, EP, ep_override=ep)
        self.assertEqual(OV.STYLE["highlight"], (255, 176, 0))
        self.assertTrue(OV.font(50, 8).path.endswith("Montserrat-ExtraBold.ttf") or "Montserrat" in OV.font(50, 8).path)
        amber = sum(1 for im in fr.values() for px in im.resize((270, 480)).getdata()
                    if abs(px[0] - 255) < 20 and abs(px[1] - 176) < 25 and px[2] < 60)
        self.assertGreater(amber, 50, "no amber highlight/twist pixels found")
        if card:   # the twist card sprite itself: amber panel, dark text, no red accent bar
            sp = OV.Card(types.SimpleNamespace(cue=lambda *a, **k: 0.0, fps=30, t_on=lambda s: 0.0, t_off=lambda s: 5.0), dict(card[1]))
            sp.t0, sp.t1, sp.anim = 0.0, 5.0, 0.3
            img = sp.sprites(2.0, 60)[0].img
            px = [p for p in img.getdata() if p[3] > 150]
            amb = sum(1 for p in px if abs(p[0] - 255) < 30 and abs(p[1] - 176) < 30 and p[2] < 70)
            red = sum(1 for p in px if p[0] > 190 and p[1] < 70 and p[2] < 80)
            self.assertGreater(amb, 0.5 * len(px), "twist panel is not amber")
            self.assertEqual(red, 0, "red accent drawn on the twist card")

    def test_bad_values_fail(self):
        with self.assertRaises(SystemExit):
            OV.apply_style({"style": {"font_set": "comic"}})
        with self.assertRaises(ValueError):
            OV.apply_style({"style": {"highlight_color": "#FFB0"}})

    def test_no_style_restores_defaults(self):
        OV.apply_style({"style": self.STYLE})
        OV.apply_style({})
        self.assertEqual(OV.STYLE, {"font_set": None, "highlight": OV.RED, "twist_bg": None, "twist_fg": None})


if __name__ == "__main__":
    unittest.main(verbosity=1, warnings="ignore")

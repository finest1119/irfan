"""Writes page2/episodes/build-01/episode.json (DRAFT) from page2/scripts/build-01-wind-turbine.md.

VO text is copied verbatim from the script's `VO:` lines (checked: same words, same count). Camera keys, cast,
presets and overlays follow each beat's "Move in / Hold / Overlays / Bolts / Torque" notes. Coordinates come from
page2/world_state.json (slope-fixed version: ridge pad at (116, 70, 20.21)). Re-run after editing this file.
  python page2/tools/make_build01_episode.py
Long holds are split automatically (hold_split.py: <= 7 s planned, chief's rule 9 s warn / 10 s fail).
"""
import json
import re
import sys
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PAGE2 / "scripts"))
import gen_world_state as G  # noqa: E402

sys.path.insert(0, str(PAGE2 / "tools"))
import hold_split as HS  # noqa: E402

SCRIPT = PAGE2 / "scripts" / "build-01-wind-turbine.md"
OUT = PAGE2 / "episodes" / "build-01" / "episode.json"

PAD = (G.PAD[0], G.PAD[1], G.PAD_Z)          # (116, 70, 20.21)
TOWER_LEN = 50 * G.FT                         # 15.24 m


def h(x, y, dz=0.0):
    return round(G.height(x, y) + dz, 2)


def P(x, y, dz):
    return [x, y, h(x, y, dz)]


px, py, pz = PAD
SPOTS = {
    # beat 1
    "horizon": {"pos": [-110.0, -25.0, 40.0], "look_at": [-420.0, -260.0, 30.0], "lens": 35},
    "street_low": {"pos": [-80.0, -6.2, 1.8], "look_at": [-30.0, -4.0, 2.6], "lens": 28},
    "street_poles": {"pos": [-60.0, -5.0, 2.2], "look_at": [-45.0, 8.0, 7.5], "lens": 28},
    "porch_bolts": {"pos": [-5.8, -2.2, 1.75], "look_at": [-1.0, 0.8, 1.55], "lens": 35},
    # beat 2
    "ridge_crane": {"pos": P(101.0, 53.0, 4.0), "look_at": [px, py, pz + 6.0], "lens": 24},
    "tailgate_plan": {"pos": [124.0, 53.0, pz + 1.9], "look_at": [121.0, 57.0, pz + 1.0], "lens": 35},
    # beat 3
    # the head lies at the tip of the FLAT tower until the hack1 tilt-up (stills 24 Nov: old spot saw only grass)
    "turbine_head": {"pos": [px - 4.0, py - TOWER_LEN - 3.0, pz + 2.2], "look_at": [px, py - TOWER_LEN, pz + 0.8],
                     "lens": 35},
    # side-on view of the whole tilt-up (flat tip ... raised tip at +50 ft fit the frame), hack1
    "tilt_side": {"pos": [px + 30.0, py - 6.0, pz + 4.0], "look_at": [px, py - 2.0, pz + 8.0], "lens": 24},
    "cable_slice": {"section": "cable", "t": 0.3, "back": 6.0, "dz": -0.2, "ahead": 5.0, "lens": 24},
    "battery_bank": {"pos": [28.0, -45.5, 1.8], "look_at": [28.0, -38.6, 1.0], "lens": 28},
    # beat 4
    "tower_low": {"pos": [px - 1.4, py - TOWER_LEN - 2.5, pz + 0.7], "look_at": [px, py, pz + 0.6], "lens": 28},
    # beat 5
    "winch": {"pos": [px - 2.5, py + 1.5, pz + 1.2], "look_at": [px, py + 2.5, pz + 0.4], "lens": 35},
    "torque_ground": {"pos": [px - 5.5, py - 5.5, pz + 0.45], "look_at": [px - 4.0, py - 4.0, pz + 0.35], "lens": 35},
    # beat 6 / 7
    "rotor": {"pos": [px - 10.0, py - 8.0, pz + 14.0], "look_at": [px, py, pz + TOWER_LEN], "lens": 32},
    "tail_hinge": {"pos": [px + 3.0, py + 3.0, pz + TOWER_LEN + 1.3], "look_at": [px + 0.6, py + 0.5, pz + TOWER_LEN + 0.1], "lens": 35},
    # beat 8
    "battery_close": {"pos": [27.0, -42.2, 1.5], "look_at": [28.0, -38.8, 1.0], "lens": 40},
    "ridge_far": {"pos": [40.0, -48.0, 6.0], "look_at": [px, py, pz + 12.0], "lens": 40},
    "kitchen_window": {"pos": [7.0, 10.5, 2.0], "look_at": [7.0, 4.5, 1.5], "lens": 35},
    # beat 9: street_wide overrides the world camera spot (-62,-10,6), which sits inside the street-tree row
    # (s12: a canopy 1.3 m in front of it filled the frame); same look-at, camera moved onto the road centre
    "street_wide": {"pos": [-62.0, -3.0, 6.0], "look_at": [0.0, 2.0, 3.0], "lens": 28},
    "fence_peek": {"pos": [18.0, 15.0, 1.7], "look_at": [18.0, 22.5, 1.9], "lens": 30},
    # beat 10 / 11
    "continuity_wide": {"pos": [-40.0, -80.0, 55.0], "look_at": [60.0, 10.0, 8.0], "lens": 22},
}

SECTIONS = {
    "cable": {"a": [100.0, 58.0], "b": [68.0, 19.0], "side": 1, "depth": 2.0, "width": 10.0, "cable_depth": 0.6,
              "desc": "buried cable from the ridge pad down the meadow (Build #1); soil layers + cable in the wall"},
}

_a, _b = SECTIONS["cable"]["a"], SECTIONS["cable"]["b"]
_L = ((_b[0] - _a[0]) ** 2 + (_b[1] - _a[1]) ** 2) ** 0.5
CABLE_DIR = [round((_b[0] - _a[0]) / _L, 3), round((_b[1] - _a[1]) / _L, 3), round((h(*_b) - h(*_a)) / _L, 3)]

BOLTS_PORCH = {"at": [-1.0, 0.8, 0.45], "yaw": 180, "clip": "idle"}
CAST = {
    "hook": {"bolts": dict(BOLTS_PORCH, clip="hands_on_hips"),
             "torque": {"at": [-19.5, -14.5, 0.0], "yaw": 90, "clip": "waddle", "path": [[-19.5, -14.5], [-19.5, -9.0]]},
             "pickup": {"at": [-7.5, -10.35, 0.0], "yaw": 0}},
    "mission": {"bolts": {"at": [121.0, 56.3, pz], "yaw": 90, "clip": "point"},
                "torque": {"at": [px - 4.0, py - 4.0, pz], "yaw": 30, "clip": "idle"},
                "pickup": {"at": [121.0, 60.0, pz], "yaw": 90}},
    "how": {"bolts": {"at": [px - 3.0, py - 1.0, pz], "yaw": 20, "clip": "point"}},
    "snag1": {"bolts": {"at": [px + 1.5, py - TOWER_LEN + 1.0, pz], "yaw": 180, "clip": "scratch_beard"}},
    "hack1": {"bolts": {"at": [px - 0.5, py + 4.2, pz], "yaw": 270, "clip": "winch_crank"},
              "torque": {"at": [px - 6.0, py - 5.0, pz], "yaw": 30, "clip": "waddle",      # walks INTO the
                         "path": [[px - 6.0, py - 5.0], [px - 4.0, py - 4.0]]}},             # torque_ground shot
    "snag2": {"bolts": {"at": [px - 2.0, py - 2.0, pz], "yaw": 45, "clip": "idle"},
              "torque": {"at": [38.0, 9.2, h(38.0, 9.2)], "yaw": 270, "clip": "idle"}},
    "works": {"bolts": {"at": [29.5, -43.0, 0.0], "yaw": 160, "clip": "thumbs_up"},
              "torque": {"at": [28.6, -43.4, 0.0], "yaw": 120, "clip": "idle"}},
    "callback": {"bolts": dict(BOLTS_PORCH, clip="idle"),
                 "torque": {"at": [18.0, 20.8, 0.0], "yaw": 90, "clip": "honk"},
                 "pickup": {"at": [-7.5, -10.35, 0.0], "yaw": 0}},
}


LIGHTS = {"hook": {"porch": False, "house": False, "kitchen": True},          # script beat 1: "porch light off" (blackout); payoff = one lit porch in callback
          "mission": {"porch": False, "house": False, "kitchen": True},       # off with the day preset (f353, mid-move)
          "callback": {"porch": True, "house": False, "kitchen": True}}


def cam(*keys):
    return list(keys)


CAMERA = {
    "hook": cam({"cue": 0, "lead": 0.4, "move": "travel", "dur": 1.0, "from": "horizon", "to": "street_low",
                 "hold": {"type": "drift", "dir": [1, 0, 0], "speed": 1.4}},
                {"cue": 2, "move": "travel", "dur": 1.2, "to": "street_poles", "hold": {"type": "drift", "dir": [1, 0.15, 0], "speed": 1.0}},
                {"cue": 3, "move": "snap", "dur": 0.3, "to": "porch_bolts", "hold": {"type": "push", "speed": 0.3}}),
    "mission": cam({"cue": 0, "move": "travel", "dur": 2.0, "to": "ridge_crane",
                    "via": [[3.0, -1.0, 15.0], [30.0, 6.0, 15.0], [75.0, 35.0, 24.0]],
                    "hold": {"type": "crane", "speed": 1.0, "follow": 0.7}},
                   {"cue": 2, "move": "snap", "dur": 0.3, "to": "tailgate_plan", "hold": {"type": "push", "speed": 0.35}}),
    "how": cam({"cue": 0, "move": "snap", "dur": 0.3, "to": "turbine_head", "hold": {"type": "orbit", "deg_s": 9.0}},
               {"cue": 2, "lead": 0.3, "move": "section", "dur": 1.5, "to": "cable_slice", "section": "cable",
                "hold": {"type": "drift", "dir": CABLE_DIR, "speed": 2.0}},
               {"cue": "battery", "lead": 0.5, "move": "travel", "dur": 1.2, "to": "battery_bank",
                "hold": {"type": "drift", "dir": [1, 0, 0], "speed": 0.5}}),
    "snag1": cam({"cue": 0, "move": "travel", "dur": 1.5, "to": "tower_low", "hold": {"type": "drift", "dir": [0, 1, 0], "speed": 1.5}}),
    "hack1": cam({"cue": 0, "move": "travel", "dur": 1.2, "to": "tilt_side",          # watch the tower tilt up
                  "hold": {"type": "orbit", "deg_s": 1.5}},
                 {"cue": "torque", "lead": 0.3, "move": "snap", "dur": 0.2, "to": "torque_ground",
                  "hold": {"type": "drift", "dir": [-0.7, -0.7, 0], "speed": 0.5}}),
    "snag2": cam({"cue": 0, "move": "travel", "dur": 1.5, "to": "rotor", "hold": {"type": "orbit", "deg_s": 10.0}}),
    "hack2": cam({"cue": 0, "move": "snap", "dur": 0.3, "to": "tail_hinge", "hold": {"type": "orbit", "deg_s": 7.0, "rise": 1.0}}),
    "works": cam({"cue": 0, "move": "travel", "dur": 1.5, "to": "battery_bank", "hold": {"type": "drift", "dir": [1, 0, 0], "speed": 0.5}},
                 {"cue": 1, "move": "snap", "dur": 0.3, "to": "battery_close", "hold": {"type": "drift", "dir": [1, 0, 0], "speed": 0.3}},
                 {"cue": 2, "move": "travel", "dur": 1.5, "to": "ridge_far", "hold": {"type": "push", "speed": 1.0}},
                 {"cue": 4, "move": "travel", "dur": 1.5, "to": "kitchen_window", "hold": {"type": "push", "speed": 0.35}}),
    "callback": cam({"cue": 0, "move": "travel", "dur": 2.0, "to": "street_wide", "hold": {"type": "push", "speed": 1.2}},
                    {"cue": 1, "move": "snap", "dur": 0.3, "to": "fence_peek", "hold": {"type": "drift", "dir": [1, 0, 0], "speed": 0.3}}),
    "teaser": cam({"cue": 0, "move": "travel", "dur": 1.5, "to": "continuity_wide", "hold": {"type": "orbit", "deg_s": 2.0}},
                  {"cue": 1, "move": "none", "hold": {"type": "orbit", "deg_s": 2.0, "look_to": "waterfall", "look_s": 3.0}}),
    "question": cam({"cue": 0, "move": "none", "hold": {"type": "crane", "speed": 0.9, "follow": 0.4}}),
}

PRESET = {"hook": "dusk", "mission": "day", "how": "day", "snag1": "day", "hack1": "day", "snag2": "day",
          "hack2": "day", "works": "day", "callback": "dusk", "teaser": "dusk", "question": "dusk"}

OVERLAYS = {
    "hook": [{"type": "chips", "items": ["BOLTS · BUILD #1"], "at": 0.2, "until": 3.0},
             {"type": "card", "text": "TODAY: ELECTRICIAN BOLTS", "at": 0.3, "until": 2.3},
             {"type": "big", "text": "DARK.", "cue": "dark", "until": "again"},
             {"type": "big", "text": "AGAIN.", "cue": "again", "until": "last"},
             {"type": "label", "text": "POWER OUT", "anchor": "street", "cue": "street", "until": "bolts"},
             {"type": "big", "text": "≈ 11 HOURS", "sub": "without power per customer, 2024 (EIA)", "cue": "eleven", "until": "bolts"}],
    "mission": [{"type": "chips", "items": ["MISSION"], "at": 0.1},
                {"type": "bar", "top": "house_top", "bottom": "house_base", "label": "HOUSE ≈ 28 FT", "cue": "taller", "side": "left"},
                {"type": "bar", "top": "tower_top_ghost", "bottom": "tower_base", "label": "TOWER 50 FT", "cue": "fifty", "color": "red"},
                {"type": "label", "text": "WINDY RIDGE +70 FT", "anchor": "ridge_pad", "cue": "windy"},
                {"type": "big", "text": "PERMIT ✔", "cue": "permit"}],
    "how": [{"type": "label", "text": "3 BLADES", "anchor": "rotor_hub", "cue": "three"},
            {"type": "label", "text": "GENERATOR", "anchor": "generator", "cue": "generator", "dx": 140},
            {"type": "label", "text": "TAIL VANE", "anchor": "tail", "cue": "tail", "dx": -140},
            {"type": "label", "text": "BURIED CABLE", "anchor": "cable_mid", "cue": "buried"},
            {"type": "meter", "label": "BATTERY 12 %", "segments": 8, "cues": ["battery"], "y": 0.7}],
    "snag1": [{"type": "chips", "items": ["SNAG"], "at": 0.1},
              {"type": "bar", "top": "tower_tip_flat", "bottom": "tower_base", "label": "50 FT", "cue": "fifty"}],
    "hack1": [{"type": "chips", "items": ["HACK"], "at": 0.1},
              {"type": "label", "text": "HINGE", "anchor": "hinge", "cue": "tilt"},
              {"type": "label", "text": "GIN POLE", "anchor": "gin_pole", "cue": "build", "dx": 150},
              {"type": "label", "text": "GUY WIRES", "anchor": "guy_anchor", "cue": "crank", "dx": -150}],
    "snag2": [{"type": "chips", "items": ["SNAG"], "at": 0.1},
              {"type": "big", "text": "TOO FAST", "cue": "spin"}],
    "hack2": [{"type": "chips", "items": ["HACK"], "at": 0.1},
              {"type": "label", "text": "FURLING", "anchor": "tail", "cue": "furling"}],
    "works": [{"type": "chips", "items": ["IT WORKS"], "at": 0.1},
              {"type": "big", "text": "1.5 kW PEAK", "cue": "rated", "until": "small"},
              {"type": "big", "text": "≈ 5 kWh / DAY", "sub": "good windy site", "cue": "five"},
              {"type": "chips", "items": ["FRIDGE", "LIGHTS", "PHONES"], "cues": ["fridge", "lights", "phones"], "style": "check"}],
    "callback": [{"type": "label", "text": "BOLTS' HOUSE", "anchor": "porch", "cue": "porch"},
                 {"type": "big", "text": "ONE LIGHT.", "cue": "one"}],
    "teaser": [{"type": "card", "text": "NEXT: BUILD #2", "cue": "tomorrow"},
               {"type": "label", "text": "?", "anchor": "waterfall", "cue": "creek"}],
    "question": [{"type": "card", "text": "Would your HOA let you put this in YOUR yard?", "at": 0.2}],
}


def main():
    md = SCRIPT.read_text(encoding="utf-8")
    vo = re.findall(r"^VO: (.*)$", md, re.M)
    ids = ["hook", "mission", "how", "snag1", "hack1", "snag2", "hack2", "works", "callback", "teaser", "question"]
    assert len(vo) == len(ids), (len(vo), len(ids))
    beats = []
    for bid, text in zip(ids, vo):
        shot = {"location": "mercer_hollow", "preset": PRESET[bid], "camera": CAMERA[bid],
                "overlays": OVERLAYS.get(bid, [])}
        if bid in CAST:
            shot["cast"] = CAST[bid]
        if bid in LIGHTS:
            shot["lights"] = LIGHTS[bid]
        beats.append({"id": bid, "text": text, "shot": shot})
    ep = {
        "id": "build-01",
        "page": "self-made-engineer",
        "draft": True,
        "keyword": "backyard wind turbine",
        "slug": "build-01-wind-turbine",
        "title": "Storm knocked out the power. So he built a wind turbine taller than his house",
        "pipeline": "oneshot",
        "outfit": "electrician",
        "outfit_extras": ["fall_arrest_harness"],
        "builds_in_episode": [{"id": "wind_turbine", "mode": "assemble"}],
        "tts": {"model": "gemini-3.8-flash-tts", "fallback_model": "gemini-3.1-flash-tts-preview",
                "voice": "Fenrir", "pause_between_beats": 0.3,
                "director_notes": "Male host narrator, natural American accent, excitable and warm, ~175 WPM, third person."},
        "render": {"resolution": [1080, 1920], "fps": 30, "samples": 32, "engine": "cycles"},
        "oneshot": {"min_hold_s": 0.25, "hidden_joins": [], "whoosh_db": -20},
        "spots": SPOTS,
        "sections": SECTIONS,
        "anchors": {
            "street": [-45.0, 0.0, 0.2], "house_base": [9.9, -6.8, 0.0], "house_top": [9.9, -6.8, 8.53],
            "tower_base": [px, py, pz], "tower_top_ghost": [px, py, pz + TOWER_LEN],
            "tower_tip_flat": [px, py - TOWER_LEN, pz + 0.3], "tower_tip_up": [px, py, pz + TOWER_LEN],
            "hinge": [px, py, pz + 0.3], "gin_pole": [px, py + 1.0, pz + 2.5], "guy_anchor": [px + 9.0, py, pz],
            "rotor_hub": [px - 0.6, py, pz + TOWER_LEN], "generator": [px, py, pz + TOWER_LEN],
            "tail": [px + 1.5, py, pz + TOWER_LEN + 0.2],
            "cable_mid": [81.0, 35.0, h(81.0, 35.0, -0.6)],
        },
        "beats": beats,
        "_notes": [
            "DRAFT by the world builder (24 Nov 2026). VO = the script's VO lines verbatim (265 words).",
            "Beat 8: the camera stays OUTSIDE the kitchen window (BUILD-SPEC 1: no interiors in the exterior scene); "
            "the window shows a lit low-poly kitchen backdrop box. Beat 9 starts outside, so no hidden join is needed.",
            "Beat 2: the red pickup is moved to the ridge pad for the tailgate shot (swap hidden in the beat-2 travel) "
            "and back to the driveway in beat 9.",
            "Overlay types 'stat card', HUD gauges, wind arrows, angle readout and the crossed-out ladder are not in "
            "overlay_v2 yet; approximated with big/meter/label/bar.",
        ],
    }
    words = sum(len(b["text"].split()) for b in beats)
    assert words == 265, words
    # chief's rule (both Pages): no camera hold over ~9 s (FAIL > 10 s). Add sub-stop keys at sentence starts.
    ep = HS.split_long_holds(ep, target_s=HS.TARGET_S)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ep, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote %s (%d beats, %d VO words)" % (OUT, len(beats), words))


if __name__ == "__main__":
    main()

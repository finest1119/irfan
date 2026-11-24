#!/usr/bin/env python3
"""Everyday Decoded (Page 3): script JSON -> v2 episode.json + "oneshot" block.

Usage (from the repo root, any OS):
  python page3/tools/make_episode.py page3/scripts/B1-tap-to-pay.json            # write the episode
  python page3/tools/make_episode.py page3/scripts/B1-tap-to-pay.json --check    # validate only
  python page3/tools/make_episode.py --batch [--check]                           # every page3/scripts/*.json
Options: --date YYYY-MM-DD (folder date, default today), --out-root DIR (default page3/episodes),
         --force (overwrite an existing episode.json), --include-underscore (batch: also _*.json files).

Output: <out-root>/<date>-<id>/episode.json. Every field the v2 pipeline reads is kept (keyword, slug, title,
fb_caption, hashtags, sources, engagement_comment, tts, render, music null, pipeline "v2", beats with
id/text/shot). Each beat's shot uses the future one-shot builder "ed_oneshot"; only overlay types that
pipeline/overlay_v2.py already knows (card, chips, label, big) are emitted. The TWIST card is a "card" with the
extra key "style": "twist" (ignored by today's overlay_v2, used by the one-shot renderer).

Stdlib only. Written for Python 3.11 but kept 3.9-compatible (the Mac's .venv is 3.9.6).
Fails loudly (exit 1, every problem listed) on any validation error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

PAGE3 = Path(__file__).resolve().parent.parent
PAGE_JSON = PAGE3 / "page.json"
SCRIPTS_DIR = PAGE3 / "scripts"
EPISODES_DIR = PAGE3 / "episodes"

# ---------------------------------------------------------------- fixed vocabularies (WORLDS-SPEC.md)
STOP_WORLD = {
    # W1 Hometown USA
    "hand_phone": "W1", "cell_tower": "W1", "tower_base": "W1", "street_slice_fiber": "W1",
    "data_center": "W1", "edge_server_room": "W1", "substation": "W1", "power_lines": "W1",
    "pole_transformer": "W1", "water_tower": "W1", "water_main_slice": "W1", "treatment_plant": "W1",
    "intersection": "W1", "road_loop_slice": "W1", "signal_cabinet": "W1", "sky_satellites": "W1",
    "strip_mall_checkout": "W1", "suburb_wide": "W1",
    # W2 Macro kit (nested inside W1/W3 objects)
    "macro_phone_board": "W2", "macro_phone_antenna": "W2", "macro_card_chip": "W2", "macro_card_coil": "W2",
    "macro_terminal": "W2", "macro_scanner": "W2", "macro_barcode": "W2",
    # W3 Cut-away house (inside W1). macro_microwave_mesh is W3 on purpose (lives in the house's microwave).
    "house_exterior": "W3", "living_room_router": "W3", "living_room_tv": "W3", "kitchen_microwave": "W3",
    "macro_microwave_mesh": "W3", "ac_indoor_coil": "W3", "ac_lines_wall": "W3", "ac_condenser": "W3",
    "thermostat": "W3", "faucet_kitchen": "W3", "wall_pipes": "W3", "smart_meter": "W3",
}
STOPS = tuple(STOP_WORLD)
WORLDS = ("W1", "W2", "W3")
ONESHOT_WORLD = "hometown_usa"  # W1 + W3 in one scene, W2 sets nested inside it

# Camera move library: default duration in seconds (renderer may stretch holds to the beat length).
MOVES = {
    "travel": 1.5,   # eased fly between stops (1-2 s; long reveal up to 5-7 s)
    "snap": 0.3,     # blurred push-in to a close-up (0.2-0.4 s)
    "section": 1.8,  # dive into a cut-away slice (ground, wall, road)
    "portal": 0.5,   # fill-frame whip into an enlarged/nested set (0.3-0.6 s)
    "crane": 2.0,    # vertical rise/fall (1.5-3 s; sky layer up to 4 s)
    "orbit": 3.0,    # slow orbit hold (whole beat)
    "drift": 3.0,    # slow drift hold (whole beat)
    "backout": 4.0,  # reverse path back to the opening object (2-4 s; 4.0 since Session 2: 2.5 s = ~1.5 km in 75 frames)
}
FIRST_MOVES = ("drift", "orbit")
LAST_MOVE = "backout"
SPARK = ("teal", "amber", "ice", "off")

OVERLAY_TYPES = ("card", "chips", "label", "big", "twist")
MAX_OVERLAY_CHARS = 40
WORD_RANGE = (200, 300)
PASSTHROUGH_KEYS = ("sub", "sub_cue", "until", "at", "dx", "dy", "color", "y", "delay")

BRANDS = ("Visa", "Mastercard", "American Express", "Amex", "Discover Card", "Apple", "iPhone", "Samsung",
          "Galaxy", "Verizon", "AT&T", "T-Mobile", "Sprint", "Netflix", "Hulu", "YouTube", "Amazon", "Google",
          "Android", "Microsoft", "McDonald's", "Walmart", "Target", "Costco", "Uber", "Lyft", "DoorDash",
          "Grubhub", "Venmo", "Zelle", "Cash App", "PayPal", "Starbucks", "Comcast", "Xfinity", "Spectrum",
          "FedEx", "UPS", "USPS", "E-ZPass", "SunPass", "Carrier", "Trane", "Whirlpool")
# Words in BRANDS that are also ordinary English: checked case-sensitively (as a proper noun or ALL CAPS).
CASE_SENSITIVE_BRANDS = ("Target", "Carrier", "Galaxy", "Discover Card", "Spectrum", "Sprint", "Apple", "UPS",
                         "Amazon")

REQUIRED = ("id", "topic_id", "series", "world", "title", "keyword", "voice", "beats", "twist_beat",
            "fb_caption", "hashtags", "engagement_comment", "sources")
WIN_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ScriptError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


def norm(w: str) -> str:
    """Same normalisation as pipeline/captions.py norm() (cue matching is a prefix test on this)."""
    w = w.lower().replace("-", "")
    return re.sub(r"[^a-z0-9]", "", w)


def count_words(text: str) -> int:
    return len([t for t in text.split() if norm(t)])


def _brand_pattern(name: str) -> str:
    parts = []
    for ch in name:
        if ch in "'’":
            parts.append("['’]?")
        elif ch == "-":
            parts.append("[-‑ ]?")
        elif ch == " ":
            parts.append(r"\s+")
        elif ch == "&":
            parts.append(r"\s*(?:&|and)\s*")
        else:
            parts.append(re.escape(ch))
    return r"(?<![A-Za-z0-9])" + "".join(parts) + r"(?![A-Za-z0-9])"


def _brand_regex(brand: str):
    if brand in CASE_SENSITIVE_BRANDS:
        return re.compile("%s|%s" % (_brand_pattern(brand), _brand_pattern(brand.upper())))
    return re.compile(_brand_pattern(brand), re.IGNORECASE)


BRAND_RES = [(b, _brand_regex(b)) for b in BRANDS]


def find_brands(text: str):
    return sorted({b for b, rx in BRAND_RES if rx.search(text or "")})


def load_page(path: Path = PAGE_JSON) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- validation
def validate(script: dict, page: dict):
    """Return (problems, warnings). problems = hard failures."""
    P, W = [], []
    for k in REQUIRED:
        if k not in script or script[k] in (None, "", []):
            P.append("missing required field %r" % k)
    if P:
        return P, W

    sid = script["id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(sid)):
        P.append("id %r must be lowercase letters/digits/dashes" % sid)
    kw = str(script["keyword"])
    if WIN_ILLEGAL.search(kw) or kw != kw.strip() or kw.endswith("."):
        P.append("keyword %r has characters that are illegal in Windows file names" % kw)

    worlds = script["world"] if isinstance(script["world"], list) else [script["world"]]
    for w in worlds:
        if w not in WORLDS:
            P.append("world %r not supported (built worlds: %s)" % (w, ", ".join(WORLDS)))

    voice = page["voice"]["voice"]
    if script["voice"] != voice:
        P.append("voice %r: Everyday Decoded uses the fixed voice %r" % (script["voice"], voice))

    beats = script["beats"]
    if not isinstance(beats, list) or not beats:
        P.append("beats must be a non-empty list")
        return P, W
    ids = [b.get("id") for b in beats]
    if len(set(ids)) != len(ids):
        P.append("duplicate beat ids: %s" % ids)
    if script["twist_beat"] not in ids:
        P.append("twist_beat %r is not a beat id (%s)" % (script["twist_beat"], ", ".join(map(str, ids))))

    total_words = 0
    for i, b in enumerate(beats):
        tag = "beat %d (%s)" % (i + 1, b.get("id"))
        if not re.fullmatch(r"[a-z0-9_]+", str(b.get("id", ""))):
            P.append("%s: id must be lowercase letters/digits/underscores" % tag)
        text = b.get("text") or ""
        if not text.strip():
            P.append("%s: empty text" % tag)
        total_words += count_words(text)
        if b.get("stop") not in STOP_WORLD:
            P.append("%s: unknown stop %r" % (tag, b.get("stop")))
        elif STOP_WORLD[b["stop"]] not in worlds:
            P.append("%s: stop %r belongs to %s, not in script world %s"
                     % (tag, b["stop"], STOP_WORLD[b["stop"]], worlds))
        if b.get("move") not in MOVES:
            P.append("%s: unknown move %r (allowed: %s)" % (tag, b.get("move"), ", ".join(MOVES)))
        if b.get("spark") not in SPARK:
            P.append("%s: unknown spark %r (allowed: %s)" % (tag, b.get("spark"), ", ".join(SPARK)))
        words_norm = [norm(t) for t in text.split()]
        n_twist = 0
        for j, ov in enumerate(b.get("overlays") or []):
            otag = "%s overlay %d" % (tag, j + 1)
            typ = ov.get("type")
            if typ not in OVERLAY_TYPES:
                P.append("%s: unknown overlay type %r (allowed: %s)" % (otag, typ, ", ".join(OVERLAY_TYPES)))
                continue
            if typ == "twist" or (typ == "card" and ov.get("style") == "twist"):
                n_twist += 1
                if b.get("id") != script["twist_beat"]:
                    P.append("%s: TWIST card outside the twist_beat %r" % (otag, script["twist_beat"]))
            multi = typ == "chips" and "items" in ov
            texts = list(ov.get("items") or []) if multi else [ov.get("text")]
            cues = list(ov.get("cues") or []) if multi else [ov.get("cue")]
            if multi and len(cues) != len(texts):
                P.append("%s: chips need one cue per item" % otag)
            if ov.get("sub"):
                texts.append(ov["sub"])
            for t in texts:
                if not t or not str(t).strip():
                    if typ != "twist":
                        P.append("%s: empty text" % otag)
                elif len(str(t)) > MAX_OVERLAY_CHARS:
                    P.append("%s: text %r is %d chars (max %d)" % (otag, t, len(str(t)), MAX_OVERLAY_CHARS))
            for c in cues:
                if c is None or (isinstance(c, str) and not c.strip()):
                    if "at" in ov and typ != "chips":
                        continue
                    P.append("%s: missing cue" % otag)
                    continue
                if isinstance(c, (int, float)):
                    continue
                nc = norm(str(c))
                if not nc:
                    P.append("%s: cue %r has no letters/digits" % (otag, c))
                elif not any(w.startswith(nc) for w in words_norm):
                    P.append("%s: cue %r not found in the beat text" % (otag, c))
            if ov.get("sub_cue"):
                nc = norm(str(ov["sub_cue"]))
                if not any(w.startswith(nc) for w in words_norm):
                    P.append("%s: sub_cue %r not found in the beat text" % (otag, ov["sub_cue"]))
            if typ == "label" and ov.get("anchor") and ov["anchor"] not in STOP_WORLD:
                P.append("%s: label anchor %r is not a stop id" % (otag, ov["anchor"]))
        cards = [o for o in (b.get("overlays") or []) if o.get("type") in ("card", "twist")]
        if len(cards) > 1 and any("until" not in o for o in cards[:-1]):
            W.append("%s: %d cards share the card band; give the earlier one(s) an 'until' cue" % (tag, len(cards)))
        if b.get("id") == script["twist_beat"] and n_twist == 0:
            P.append("%s: twist_beat has no TWIST card (overlay type \"twist\")" % tag)
        if n_twist > 1:
            P.append("%s: more than one TWIST card" % tag)

    if not (WORD_RANGE[0] <= total_words <= WORD_RANGE[1]):
        P.append("word count %d outside %d-%d" % (total_words, WORD_RANGE[0], WORD_RANGE[1]))
    declared = script.get("word_count")
    if isinstance(declared, int) and abs(declared - total_words) > 3:
        W.append("declared word_count %d, counted %d (counted value is used)" % (declared, total_words))

    if beats[0].get("move") not in FIRST_MOVES:
        P.append("first beat move %r must be one of %s" % (beats[0].get("move"), "/".join(FIRST_MOVES)))
    if beats[-1].get("move") != LAST_MOVE:
        P.append("last beat move %r must be %r" % (beats[-1].get("move"), LAST_MOVE))
    if len(beats) > 1 and beats[-1].get("stop") != beats[0].get("stop"):
        W.append("last beat stop %r differs from the opening stop %r (backout should return to the opening object)"
                 % (beats[-1].get("stop"), beats[0].get("stop")))
    if not 6 <= len(beats) <= 12:
        W.append("%d beats (usual 7-10)" % len(beats))

    # brand blocklist (sources + fact_notes are exempt: URLs/citations may name a company)
    fields = [("title", script.get("title")), ("keyword", script.get("keyword")),
              ("fb_caption", script.get("fb_caption")), ("engagement_comment", script.get("engagement_comment")),
              ("hashtags", " ".join(script.get("hashtags") or []))]
    for i, b in enumerate(beats):
        fields.append(("beat %d text" % (i + 1), b.get("text")))
        for ov in b.get("overlays") or []:
            fields.append(("beat %d overlay" % (i + 1),
                           " ".join(str(x) for x in [ov.get("text"), ov.get("sub")] + list(ov.get("items") or [])
                                    if x)))
    for where, txt in fields:
        hits = find_brands(str(txt or ""))
        if hits:
            P.append("brand name(s) %s in %s" % (", ".join(hits), where))

    for h in script["hashtags"]:
        if not re.fullmatch(r"#[A-Za-z0-9_]+", str(h)):
            P.append("hashtag %r must be #letters/digits" % h)
    urls = set()
    for s in script["sources"]:
        if not isinstance(s, dict) or not s.get("claim") or not s.get("urls"):
            P.append("source %r needs a claim and at least one url" % (s,))
            continue
        urls.update(s["urls"])
    if len(urls) < 2:
        W.append("only %d distinct source url(s); SOP wants 2+ per episode" % len(urls))
    if not P:
        _keys, holds = camera_keys(beats)
        for b, hs in zip(beats, holds):
            for h in hs:
                if h > HOLD_FAIL_S:
                    P.append("beat %s: estimated camera hold %.1f s > %.0f s (no sentence/word to split at; shorten "
                             "the text or add a beat)" % (b["id"], h, HOLD_FAIL_S))
    return P, W


# ---------------------------------------------------------------- conversion
def convert_overlays(beat: dict) -> list:
    out, chip_items, chip_cues = [], [], []
    for ov in beat.get("overlays") or []:
        typ = ov["type"]
        extra = {k: ov[k] for k in PASSTHROUGH_KEYS if k in ov}
        if "sub_cue" in extra:
            extra["sub_cue"] = norm(str(extra["sub_cue"]))
        if "until" in extra and isinstance(extra["until"], str):
            extra["until"] = norm(extra["until"])
        cue = {"cue": norm(str(ov["cue"]))} if isinstance(ov.get("cue"), str) else (
            {"cue": ov["cue"]} if isinstance(ov.get("cue"), (int, float)) else {})
        if typ == "chips":
            if "items" in ov:
                chip_items.extend(ov["items"])
                chip_cues.extend(norm(str(c)) for c in ov["cues"])
            else:
                chip_items.append(ov["text"])
                chip_cues.append(norm(str(ov["cue"])))
            continue
        if typ == "twist":
            item = {"type": "card", "text": ov.get("text") or "TWIST", "style": "twist"}
        elif typ == "card":
            item = {"type": "card", "text": ov["text"]}
            if ov.get("style"):
                item["style"] = ov["style"]
        elif typ == "label":
            item = {"type": "label", "text": ov["text"], "anchor": ov.get("anchor") or beat["stop"]}
        else:  # big
            item = {"type": "big", "text": ov["text"]}
        item.update(cue)
        item.update(extra)
        out.append(item)
    if chip_items:
        out.append({"type": "chips", "items": chip_items, "cues": chip_cues})
    return out


def series_chip(script: dict, page: dict) -> str:
    s = str(script["series"])
    name = page["series"].get(s.upper()[:1], s.upper()) if len(s) == 1 else s.upper()
    m = re.search(r"(\d+)", str(script.get("topic_id", "")))
    return page["cards"]["series_chip"].replace("{SERIES}", name).replace("{N}", m.group(1) if m else "1")


# ---------------------------------------------------------------- hold splitting (Session 3: no hold > ~9 s)
HOLD_WPM = 170.0         # estimate speech at 170 wpm (sentence end +0.22 s, comma +0.1 s, like synth_timings)
HOLD_MAX_S = 9.0         # target: no camera hold longer than this
HOLD_FAIL_S = 10.0       # validator: an estimated hold above this is an error
SEG_TARGET_S = 8.0       # aim for this per sub-view so the real (TTS) timing has slack
SUB_TRAVEL_S = (1.0, 0.8, 1.2)   # short travels between sub-views, varied
SUB_SNAP_S = 0.3
LEAD_S = 0.4
# stops with an enlarged portal interior (hometown_usa_plan.PORTAL_INSIDE): a portal onto the stop the camera is
# already at dives INTO it (<stop>__inside); any move out of an __inside view is a portal back (never a fly-through)
PORTAL_INSIDE = ("kitchen_microwave",)
SENT_END_RE = re.compile(r"[.!?][\"')\]]*$")


def word_times(text: str):
    """[(token, norm, start_s, sentence_start)] estimated from the text; total seconds."""
    spw, t, out, new_sent = 60.0 / HOLD_WPM, 0.0, [], True
    for tok in text.split():
        out.append((tok, norm(tok), t, new_sent))
        t += spw
        new_sent = bool(SENT_END_RE.search(tok))
        t += 0.22 if new_sent else (0.1 if tok.endswith((",", ":", ";")) else 0.0)
    return out, t


def cue_of(words, i):
    """camera_plan cue for word i: '<norm prefix>#n' (n = earlier words in the beat with the same prefix)."""
    nw = words[i][1]
    n = sum(1 for w in words[:i] if w[1].startswith(nw))
    return nw if n == 0 else "%s#%d" % (nw, n)


def split_points(words, t0, t1, max_s=SEG_TARGET_S):
    """Word indices (cue points) splitting the span t0..t1 into parts <= max_s, preferring sentence starts."""
    cuts, last = [], t0                     # t0 < 0: the hold started in the previous beat (carry-over)
    lo = max(t0, 0.0) + 0.5
    starts = [i for i, w in enumerate(words) if w[3] and w[1] and lo < w[2] < t1 - 1.5]
    anyw = [i for i, w in enumerate(words) if w[1] and lo < w[2] < t1 - 1.5]
    while t1 - last > HOLD_MAX_S:
        lim = last + max_s
        gap = 2.0 if last >= 0 else 0.0
        cand = [i for i in starts if last + gap < words[i][2] <= lim]
        if not cand:
            cand = [i for i in anyw if last + gap < words[i][2] <= lim]
        if not cand:                         # carried-over hold already near the limit: cut at the first word
            cand = [i for i in anyw if words[i][2] > last + gap][:1]
        if not cand:
            break
        i = cand[-1]
        cuts.append(i)
        last = words[i][2]
    return cuts


def _hold(move, i):
    return {"type": "orbit", "deg_s": 4.0 if i % 2 == 0 else -4.0} if move == "orbit" else {"type": "drift"}


def camera_keys(beats_in):
    """Native page2 camera keys (shot.camera) for beats whose estimated hold is over HOLD_MAX_S, else None.
    The first key repeats what page2's compact adapter would emit for the beat; later keys cycle the stop's views
    main -> __detail -> __alt with short snaps / travels, cued at sentence starts. The last beat holds on the previous
    stop's views and cues the backout so it lands ~0.6 s before the end (a real loop). Returns (keys per beat, holds)
    where holds = estimated hold seconds per beat (list of floats, for the validator)."""
    out, holds_all, k_move = [], [], 0
    stops = [b["stop"] for b in beats_in]
    cur_view = stops[0]
    carry = 0.0                                        # hold seconds already running when the beat starts
    for i, b in enumerate(beats_in):
        mv, stop = b["move"], b["stop"]
        words, total = word_times(b["text"])
        total += 0.3                                   # pause between beats
        last = i == len(beats_in) - 1 and mv == LAST_MOVE
        if i == 0:
            first = {"move": "none", "to": stop, "cue": 0.0, "lead": 0.0, "hold": _hold(mv, i)}
            arr, view0 = 0.0, stop
        elif mv in ("drift", "orbit") and stop == stops[i - 1]:
            first = {"move": "none", "cue": 0.0, "lead": 0.0, "hold": _hold(mv, i)}
            arr, view0 = 0.0, None
        elif mv in ("drift", "orbit"):
            arrive = "portal" if "__inside" in cur_view else "travel"
            first = {"move": arrive, "to": stop, "dur": MOVES[arrive], "cue": 0.0, "lead": LEAD_S,
                     "hold": _hold(mv, i)}
            arr, view0 = MOVES[arrive] - LEAD_S, stop
        elif last:
            first, arr, view0 = None, 0.0, None
        else:
            to = stop
            if mv == "portal" and stop in PORTAL_INSIDE and stop == stops[i - 1]:
                to = stop + "__inside"
            elif "__inside" in cur_view:
                mv = "portal"                          # leave the enlarged set the way we came in
            first = {"move": mv, "to": to, "dur": MOVES[mv], "cue": 0.0, "lead": LEAD_S, "hold": _hold(mv, i)}
            if mv == "section":
                first["section"] = stop
            arr, view0 = MOVES[mv] - LEAD_S, to
        if first is not None:
            first["stop"] = first.get("to", stop)
        forced = first is not None and i > 0 and (first.get("to", stop) != stop or first["move"] == "portal"
                                                  and b["move"] != "portal")
        hold_end = total
        bo_i = None
        if last:                                       # cue the backout to end ~0.6 s before the beat ends
            want = total + 0.1 - 0.6 - MOVES["backout"] + LEAD_S
            cand = [j for j, w in enumerate(words) if w[1] and w[2] >= want]
            bo_i = cand[0] if cand and words[cand[0]][2] > 1.0 else None
            hold_end = words[bo_i][2] - LEAD_S if bo_i is not None else 0.0
        if view0 is None:                              # no arrival move: the previous beat's hold continues
            arr = -carry
        need = (hold_end - arr) > HOLD_MAX_S or last or forced
        if not need:
            out.append(None)
            holds_all.append([round(hold_end - arr, 2)])
            cur_view = view0 or cur_view
            carry = total - arr
            continue
        keys = [first] if first is not None else []
        cuts = split_points(words, arr, hold_end)
        hview = stop if not last else stops[i - 1]
        here = view0 or cur_view
        hmove = mv if not last else beats_in[i - 1]["move"]
        cycle = [hview, hview + "__detail", hview + "__alt"]
        if "__inside" in here:
            cycle = [hview + "__inside", hview + "__inside_detail", hview + "__inside_alt"]
        ci = cycle.index(here) if here in cycle else 0
        prev_t, holds = arr, []
        for c in cuts:
            ci += 1
            to = cycle[ci % 3]
            snap = to.endswith("detail") and k_move % 2 == 0
            dur = SUB_SNAP_S if snap else SUB_TRAVEL_S[k_move % 3]
            k_move += 1
            keys.append({"move": "snap" if snap else "travel", "to": to, "dur": dur, "cue": cue_of(words, c),
                         "lead": LEAD_S, "hold": _hold(hmove, ci), "stop": to})
            holds.append(round(words[c][2] - LEAD_S - prev_t, 2))
            prev_t = words[c][2] - LEAD_S + dur
        holds.append(round(hold_end - prev_t, 2))
        carry = total - prev_t
        cur_view = keys[-1].get("to", cur_view) if keys else cur_view
        if last:
            keys.append({"move": "backout", "to": stops[0], "dur": MOVES["backout"],
                         "cue": cue_of(words, bo_i) if bo_i is not None else 0.0, "lead": LEAD_S if bo_i else 0.0,
                         "hold": _hold(beats_in[0]["move"], 0), "stop": stop})
            settle = total - (words[bo_i][2] - LEAD_S + MOVES["backout"]) if bo_i is not None else \
                total - MOVES["backout"]
            holds.append(round(settle, 2))
        out.append(keys)
        holds_all.append(holds)
    return out, holds_all


def build_episode(script: dict, page: dict, date: str) -> dict:
    beats_in = script["beats"]
    ep_id = "%s-%s" % (date, script["id"])
    tags = []
    for h in list(script["hashtags"]) + list(page["hashtags_base"]):
        if h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    sources = ["%s: %s" % (s["claim"], " ; ".join(s["urls"])) for s in script["sources"]]
    voice = page["voice"]
    beats, stops, moves, sparks, stop_chips = [], [], [], [], []
    cam_keys, _holds = camera_keys(beats_in)
    n_stop, prev = 0, None
    for i, b in enumerate(beats_in):
        beats.append({"id": b["id"], "text": b["text"],
                      "shot": {"builder": "ed_oneshot",
                               "params": {"stop": b["stop"], "move": b["move"], "spark": b["spark"]},
                               "overlays": convert_overlays(b)}})
        if cam_keys[i]:
            beats[-1]["shot"]["camera"] = cam_keys[i]
        stops.append(b["stop"])
        moves.append(b["move"])
        sparks.append(b["spark"])
        new_stop = i > 0 and b["stop"] != prev and b["move"] != LAST_MOVE
        if new_stop:
            n_stop += 1
        stop_chips.append(page["cards"]["stop_chip"].replace("{N}", str(n_stop)) if new_stop else None)
        prev = b["stop"]
    worlds = script["world"] if isinstance(script["world"], list) else [script["world"]]
    total_words = sum(count_words(b["text"]) for b in beats_in)
    return {
        "id": ep_id,
        "page": page["page"],
        "keyword": script["keyword"],
        "slug": re.sub(r"[^a-z0-9]+", "-", script["keyword"].lower()).strip("-"),
        "title": script["title"],
        "fb_caption": script["fb_caption"],
        "hashtags": tags,
        "engagement_comment": script["engagement_comment"],
        "sources": sources,
        "sources_structured": script["sources"],
        "fact_notes": script.get("fact_notes"),
        "topic_id": script["topic_id"],
        "series": script["series"],
        "word_count": total_words,
        "tts": {"model": page["tts_defaults"]["model"],
                "fallback_model": page["tts_defaults"]["fallback_model"],
                "voice": voice["voice"],
                "director_notes": voice["director_notes"] + (
                    "\nPronunciation: " + script["pronunciation"] if script.get("pronunciation") else ""),
                "pause_between_beats": voice["pause_between_beats"],
                "trim_pauses": page["tts_defaults"]["trim_pauses"]},
        "music": None,
        "render": {k: page["render_defaults"][k] for k in ("resolution", "fps", "samples", "parallel")},
        "beats": beats,
        "pipeline": "v2",
        # Per-episode opt-in overlay style (agreed with Page 2, 24 Nov 2026): overlay_v2 falls back to
        # pipeline/platform_cfg for any missing key, so WJH episodes (no "style") stay byte-identical.
        "style": {
            "font_set": "montserrat",
            "highlight_color": page["captions"]["highlight_color"],
            "twist_card": {"bg": page["cards"]["twist"]["background"], "fg": page["cards"]["twist"]["text_color"]},
        },
        "oneshot": {
            "world": ONESHOT_WORLD,
            "worlds_used": worlds,
            "beats": [b["id"] for b in beats_in],
            "stops": stops,
            "moves": moves,
            "spark": sparks,
            "move_durations_s": {m: MOVES[m] for m in moves},
            "spark_colors": page["spark_colors"],
            "twist_beat": script["twist_beat"],
            "series_chip": series_chip(script, page),
            "stop_chips": stop_chips,
            "sign_off": page["sign_off"],
            "anchors": "label anchor = stop id; Blender empty ANC_<stop> (WORLDS-SPEC.md)",
        },
        "generated_by": "page3/tools/make_episode.py",
    }


def process(path: Path, page: dict, date: str, out_root: Path, check: bool, force: bool):
    """Return (ok, messages, out_path or None)."""
    try:
        script = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, ["cannot read JSON: %s" % e], None
    if not isinstance(script, dict):
        return False, ["top level must be an object"], None
    problems, warnings = validate(script, page)
    msgs = ["ERROR: " + p for p in problems] + ["warning: " + w for w in warnings]
    if problems:
        return False, msgs, None
    ep = build_episode(script, page, date)
    out = out_root / ep["id"] / "episode.json"
    if check:
        return True, msgs, None
    if out.exists() and not force:
        return False, msgs + ["ERROR: %s exists (use --force to overwrite)" % out], None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, msgs, out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scripts", nargs="*", type=Path)
    ap.add_argument("--batch", action="store_true", help="process every page3/scripts/*.json")
    ap.add_argument("--include-underscore", action="store_true", help="batch: include _*.json files")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--out-root", type=Path, default=EPISODES_DIR)
    ap.add_argument("--page", type=Path, default=PAGE_JSON)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        ap.error("--date must be YYYY-MM-DD")
    paths = list(a.scripts)
    if a.batch:
        paths += sorted(p for p in SCRIPTS_DIR.glob("*.json")
                        if a.include_underscore or not p.name.startswith("_"))
    if not paths:
        if a.batch:
            print("no scripts found in %s (files starting with _ are skipped)" % SCRIPTS_DIR)
            return 0
        ap.error("give script paths or --batch")
    page = load_page(a.page)
    n_bad = 0
    for p in paths:
        ok, msgs, out = process(p, page, a.date, a.out_root, a.check, a.force)
        status = "OK  " if ok else "FAIL"
        print("%s %s%s" % (status, p.name, (" -> %s" % out) if out else (" (check only)" if ok and a.check else "")))
        for m in msgs:
            print("     " + m)
        n_bad += 0 if ok else 1
    print("%d file(s), %d failed" % (len(paths), n_bad))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())

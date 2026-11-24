"""One-shot camera plan for Self-Made Engineer reels. bpy-free (venv 3.9+ and Blender's Python).

The plan is the single source of truth for: the Blender camera (baked one key per frame, so Blender's interpolation
settings never matter), camera_speed.json (2D motion blur + whoosh placement in the overlay), qc_oneshot's planned
move windows, and the swap frames (lighting preset, cut-away section, character blocking/outfit, build LOD), which
all happen at the middle of a move window so the motion hides them.

Episode schema (per beat, `shot` block; everything optional except `camera`):
  "shot": {
    "location": "mercer_hollow",          # one location per reel
    "preset": "day",                       # day | dusk | frost | snow (switch is placed mid-move, never on a hold)
    "camera": [                            # one key per camera move, in order
      {"cue": 0,                           # int = sentence index in this beat; "word" or "word#2" = word prefix
                                           # (nth match); absent = the beat's first word
       "lead": 0.4,                        # move starts this many seconds before the cue word (default 0.4)
       "move": "travel",                   # travel (1-2 s eased) | snap (0.2-0.4 s, blur) | section | none
       "dur": 1.5,
       "to": "porch",                      # camera spot (episode `spots`, then world camera_spots), anchor/zone
                                           # name, or {"pos","look_at","lens"} or {"anchor","dist","az","el","lens"}
       "via": [[x, y, z], ...],            # optional travel waypoints (else an automatic arc for long moves)
       "hold": {"type": "drift", ...},     # what the camera does after arriving: drift | orbit | crane | push | pull
       "section": "cable",                 # (move=section) id of the episode `sections` entry to show
       "cast": {...}}                      # blocking change hidden in this move (see below)
    ],
    "cast": {"bolts": {"at": "porch", "face": "street_wide", "clip": "idle", "outfit": "electrician"},
             "torque": {"at": [..], "clip": "waddle", "path": [[x, y], ...]}}
  }
Episode level: "spots" (named views), "sections" (cut-away definitions), "oneshot": {"fps", "min_hold_s", ...}.

Extra move kinds (shared with Page 3):
  "crane"   rise/fall to the target (easeInOutSine, via a point above the start), 2 s
  "portal"  fill-frame dive: push into the surface the camera looks at (easeInQuad), then emerge in the target set
            (an enlarged interior elsewhere in the SAME scene) moving in its look direction (easeOutQuad). The join
            frame is a hidden cut inside the window: event `portal` (renderer: clip planes / rebase) + hidden_joins.
  "backout" ONE eased arc (easeInOutCubic, lifted when long) straight back to the opening framing, timed to end
            BACKOUT_SETTLE_S before the last frame; the opening hold then runs so the LAST frame == frame 1's view.

Compact "oneshot" block (Page 3, `expand_oneshot`): {"world", "stops": [per beat], "moves": [per beat],
"move_durations_s": {move: s}, optional "spark": [per beat colour name], "spark_colors": {name: "#RRGGBB"},
"lead_s"}. Each beat becomes ONE camera key {move, to: stop, dur, cue: 0.0 (= beat start)}; drift/orbit/crane on
beat 1 are the opening hold (no move on frame 1); drift/orbit later on the same stop only change the hold; snap or
portal to the stop the camera is already at = a short push-in (PUSH_IN_FRAC closer, lens x PUSH_IN_LENS).
Holds scale with the subject distance (HOLD_REL / HOLD_MAX_REL), so the same episode works from mm to km.
Stops resolve against the world's anchors (ANC_<id> look point, CAM_<id> camera position; see worlds.py).

Times: beat layout from WORKDIR/audio/timings.json, word times from WORKDIR/captions.json (same files as v2).
Frames are GLOBAL (1-based) over the whole reel; beat b's local frame k = global beat_f0[b] + k - 1, with
beat_frames = round(duration * fps) exactly like render_episode_v2 (so overlay_v2 segments line up).
"""
import math
import re

DEFAULT_FPS = 30
SENSOR_H_MM = 24.0          # vertical sensor fit (same as scene_lib.Ctx.camera)
OUT_W, OUT_H = 1080, 1920
MIN_HOLD_S = 0.25           # minimum hold between two moves
MIN_PX_PER_FRAME = 0.6      # a hold must move the image at least this much (QC static threshold is lower)
MOVE_KINDS = ("travel", "snap", "section", "crane", "portal", "backout")
HOLD_KINDS = ("drift", "orbit", "crane", "push", "pull")
DEFAULT_DUR = {"travel": 1.5, "snap": 0.3, "section": 1.5, "crane": 2.0, "portal": 0.5, "backout": 2.5}
BLUR_MOVES = ("snap", "portal", "backout")
SENT_END = re.compile(r"[.!?][\"')\]]*$")


# ------------------------------------------------------------------ small vector helpers (tuples)
def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-9 else (0.0, 0.0, 0.0)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def smootherstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def ease_snap(t):
    """Snap push-in: steep symmetric ease (power 2.2); the middle frames carry most of the travel (blurred)."""
    t = max(0.0, min(1.0, t))
    return 0.5 * (2 * t) ** 2.2 if t < 0.5 else 1 - 0.5 * (2 - 2 * t) ** 2.2


def ease_sine(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_cubic(t):
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def catmull(pts, t):
    """Centripetal-ish uniform Catmull-Rom through pts (>=2) at t in 0..1."""
    if len(pts) == 2:
        return lerp(pts[0], pts[1], t)
    n = len(pts) - 1
    s = min(max(t, 0.0), 1.0) * n
    i = min(int(s), n - 1)
    u = s - i
    p0 = pts[max(i - 1, 0)]
    p1, p2 = pts[i], pts[i + 1]
    p3 = pts[min(i + 2, n)]
    out = []
    for k in range(3):
        a, b, c, d = p0[k], p1[k], p2[k], p3[k]
        out.append(0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3))
    return tuple(out)


# ------------------------------------------------------------------ views
class View(object):
    __slots__ = ("pos", "look", "lens")

    def __init__(self, pos, look, lens=28.0):
        self.pos, self.look, self.lens = tuple(map(float, pos)), tuple(map(float, look)), float(lens)

    def copy(self):
        return View(self.pos, self.look, self.lens)

    def as_list(self):
        return [round(v, 6) for v in self.pos + self.look] + [round(self.lens, 4)]     # 1e-6 m: macro-safe


def basis(pos, look):
    f = norm(sub(look, pos))
    r = cross(f, (0.0, 0.0, 1.0))
    if length(r) < 1e-6:
        r = (1.0, 0.0, 0.0)
    r = norm(r)
    u = cross(r, f)
    return r, u, f


def focal_px(lens, h=OUT_H):
    return lens / SENSOR_H_MM * h


def project(view, p, w=OUT_W, h=OUT_H):
    r, u, f = basis(view.pos, view.look)
    d = sub(p, view.pos)
    zc = dot(d, f)
    if zc <= 1e-4:
        return None
    fp = focal_px(view.lens, h)
    return (w / 2.0 + fp * dot(d, r) / zc, h / 2.0 - fp * dot(d, u) / zc)


def unproject(view, sx, sy, depth, w=OUT_W, h=OUT_H):
    r, u, f = basis(view.pos, view.look)
    fp = focal_px(view.lens, h)
    x = (sx - w / 2.0) / fp * depth
    y = (h / 2.0 - sy) / fp * depth
    return add(view.pos, add(add(mul(f, depth), mul(r, x)), mul(u, y)))


def screen_motion(v0, v1):
    """Mean screen displacement (px at 1080x1920) of a 3x3 grid of points at 0.5x, 1x and 2.5x the focus depth of
    v0 when the camera goes from v0 to v1 (several depths, so orbits/parallax count). Returns (magnitude, dx, dy)."""
    focus = max(0.5, length(sub(v0.look, v0.pos)))
    tot, sx_, sy_, n = 0.0, 0.0, 0.0, 0
    for gx, gy, depth in [(gx, gy, focus * k) for gx in (0.2, 0.5, 0.8) for gy in (0.25, 0.5, 0.75)
                          for k in (0.5, 1.0, 2.5)]:
        if True:
            p = unproject(v0, gx * OUT_W, gy * OUT_H, depth)
            a = project(v0, p)
            b = project(v1, p)
            if a is None or b is None:
                tot += OUT_H
                n += 1
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            tot += math.hypot(dx, dy)
            sx_ += dx
            sy_ += dy
            n += 1
    return tot / n, sx_ / n, sy_ / n


# ------------------------------------------------------------------ timing
def beat_layout(episode, timings, fps):
    """[{id, idx, start, end, duration, f0, frames}] — f0 = global first frame of the beat (1-based)."""
    out, f0 = [], 1
    tb = {b["id"]: b for b in timings["beats"]}
    for i, b in enumerate(episode["beats"]):
        tm = tb[b["id"]]
        n = int(round(tm["duration"] * fps))
        out.append({"id": b["id"], "idx": i, "start": tm["start"], "end": tm["end"], "duration": tm["duration"],
                    "f0": f0, "frames": n})
        f0 += n
    return out


def time_to_frame(layout, t, fps):
    for b in layout:
        if t < b["start"] + b["duration"] or b is layout[-1]:
            k = int(round((max(t, b["start"]) - b["start"]) * fps))
            return b["f0"] + max(0, min(b["frames"] - 1, k))
    return layout[-1]["f0"] + layout[-1]["frames"] - 1


def frame_to_beat(layout, f):
    for b in layout:
        if b["f0"] <= f < b["f0"] + b["frames"]:
            return b
    return layout[-1]


def sentence_starts(words):
    out = []
    prev_end = True
    for w in words:
        if prev_end:
            out.append(w["start"])
        prev_end = bool(SENT_END.search(w["word"]))
    return out


def resolve_cue(cue, words, beat):
    """Seconds (global) at which the cue happens. words = this beat's caption words."""
    if not words:
        return beat["start"]
    if cue is None:
        return words[0]["start"]
    if isinstance(cue, bool):
        raise ValueError("bad cue %r" % cue)
    if isinstance(cue, int):
        ss = sentence_starts(words)
        return ss[max(0, min(len(ss) - 1, cue))]
    if isinstance(cue, float):        # seconds into the beat
        return beat["start"] + cue
    s = str(cue).lower()
    nth = 0
    if "#" in s:
        s, k = s.split("#", 1)
        nth = int(k)
    hits = [w for w in words if w.get("norm", w["word"].lower()).startswith(s)]
    if len(hits) > nth:
        return hits[nth]["start"]
    print("[plan] WARNING cue %r not found in beat %s; using the beat start" % (cue, beat["id"]))
    return words[0]["start"]


# ------------------------------------------------------------------ spots
def _az_view(anchor_pos, dist, az, el, lens, look_dz=0.0):
    a, e = math.radians(az), math.radians(el)
    pos = add(anchor_pos, (dist * math.cos(e) * math.cos(a), dist * math.cos(e) * math.sin(a), dist * math.sin(e)))
    look = add(anchor_pos, (0.0, 0.0, look_dz))
    return View(pos, look, lens)


def section_frame(sec):
    """(a, b, unit dir a->b, unit normal pointing to the NEAR side = the side that is cut away, length) in XY."""
    a, b = tuple(sec["a"][:2]), tuple(sec["b"][:2])
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    d = (dx / L, dy / L)
    n = (-d[1], d[0]) if sec.get("side", 1) >= 0 else (d[1], -d[0])
    return a, b, d, n, L


VARIANTS = ("__detail", "__alt")
VARIANT_ALT_DEG = 35.0     # <stop>__alt = the same anchor seen from ~35 deg around (about the vertical axis)


def split_variant(name):
    """('stop', '__detail' | '__alt') or (name, None)."""
    if isinstance(name, str):
        for v in VARIANTS:
            if name.endswith(v) and len(name) > len(v):
                return name[:-len(v)], v
    return name, None


def variant_view(v, variant):
    """Derived view of a sub-stop when the world does not register it: __detail = push-in PUSH_IN_FRAC closer
    on the same look point (lens unchanged); __alt = same distance/height, orbited VARIANT_ALT_DEG around it."""
    if variant == "__detail":
        return View(lerp(v.pos, v.look, PUSH_IN_FRAC), v.look, v.lens)
    a = math.radians(VARIANT_ALT_DEG)
    rel = sub(v.pos, v.look)
    ca, sa = math.cos(a), math.sin(a)
    return View(add(v.look, (rel[0] * ca - rel[1] * sa, rel[0] * sa + rel[1] * ca, rel[2])), v.look, v.lens)


class SpotResolver(object):
    """Resolves `to` specs: episode spots, world camera_spots, anchors (zone names, build ids, extra points),
    section views ({"section": id, "t": 0..1 along the cut, "back": m into the cut-away, "dz", "lens"})."""

    def __init__(self, loc, ep_spots=None, extra_anchors=None, sections=None, height_fn=None):
        self.loc = loc or {}
        self.sections = sections or {}
        self.height_fn = height_fn
        self.ep_spots = ep_spots or {}
        self.anchors = {}
        for k, p in (self.loc.get("anchors") or {}).items():       # world registry anchors (ANC_<id>)
            self.anchors[k] = tuple(p)
        for k, z in (self.loc.get("zones") or {}).items():
            self.anchors[k] = tuple(z["pos"])
        for nb in (self.loc.get("street") or {}).get("neighbor_houses", []):
            self.anchors[nb["id"]] = tuple(nb["pos"])
        for k, v in (extra_anchors or {}).items():
            self.anchors[k] = tuple(v)

    def anchor_pos(self, name):
        if isinstance(name, (list, tuple)):
            return tuple(float(v) for v in name)
        if name in self.anchors:
            return self.anchors[name]
        base, var = split_variant(name)
        if var and base in self.anchors:          # sub-stop look point = the stop's anchor
            return self.anchors[base]
        raise KeyError("unknown anchor %r" % (name,))

    def view(self, spec):
        if isinstance(spec, View):
            return spec.copy()
        if isinstance(spec, str):
            if spec in self.ep_spots:
                return self.view(self.ep_spots[spec])
            cs = self.loc.get("camera_spots") or {}
            if spec in cs:
                return self.view(cs[spec])
            base, var = split_variant(spec)
            if var:                                # world did not register <stop>__detail/__alt as a view: derive
                try:
                    return variant_view(self.view(base), var)
                except KeyError:
                    pass
            if spec in self.anchors:
                return self.view({"anchor": spec})
            raise KeyError("unknown camera target %r (not an episode spot, world camera_spot or anchor)" % spec)
        if "pos" in spec:
            look = spec.get("look_at")
            if isinstance(look, str):
                look = self.anchor_pos(look)
            return View(spec["pos"], look, spec.get("lens_mm", spec.get("lens", 28.0)))
        if "section" in spec:
            sec = self.sections[spec["section"]]
            a, _b, d, n, L = section_frame(sec)
            t = spec.get("t", 0.5)
            mx, my = a[0] + d[0] * L * t, a[1] + d[1] * L * t
            back = spec.get("back", sec.get("width", 10.0) * 0.6)
            cx, cy = mx + n[0] * back, my + n[1] * back
            hz = self.height_fn(mx, my) if self.height_fn else 0.0
            ahead = spec.get("ahead", 0.0)     # aim along the cut (positive = towards b)
            look = (mx + d[0] * ahead, my + d[1] * ahead, hz - sec.get("cable_depth", 0.6))
            return View((cx, cy, hz + spec.get("dz", -0.2)), look, spec.get("lens", 24.0))
        if "anchor" in spec:
            return _az_view(self.anchor_pos(spec["anchor"]), spec.get("dist", 12.0), spec.get("az", 200.0),
                            spec.get("el", 15.0), spec.get("lens", 28.0), spec.get("look_dz", 1.0))
        raise ValueError("bad camera target %r" % (spec,))


# ------------------------------------------------------------------ holds (camera never static)
HOLD_DEFAULTS = {"orbit": {"deg_s": 1.5}, "crane": {"follow": 0.6}}
# Hold motion scales with the SUBJECT DISTANCE d = |look - pos| at the hold start (same look from 2 cm to 2 km):
HOLD_REL = {"drift": 0.015, "crane": 0.015, "push": 0.02, "pull": 0.02}   # default: fraction of d per second
HOLD_MAX_REL = 0.10          # an explicit "speed" (m/s, legacy) is clamped to 10 % of d per second
PUSH_MAX_FRAC = 0.6          # push never closes more than 60 % of the subject distance


def _hold_rate(p, kind, dsub):
    """Speed in m/s for drift/crane/push/pull: "rel" (fraction of d per s), else a legacy "speed" clamped to
    HOLD_MAX_REL * d, else the HOLD_REL default."""
    if "rel" in p:
        v = float(p["rel"]) * dsub
    elif "speed" in p:
        v = math.copysign(min(abs(float(p["speed"])), HOLD_MAX_REL * dsub), float(p["speed"]))
    else:
        v = HOLD_REL[kind] * dsub
    return v * p.get("_boost", 1.0)


def hold_view(v0, spec, dt, resolver=None):
    """Camera state dt seconds into a hold that started at view v0 (dt may be negative: the view before it)."""
    spec = spec or {"type": "drift"}
    kind = spec.get("type", "drift")
    p = dict(HOLD_DEFAULTS.get(kind, {}))
    p.update(spec)
    bo = p.get("_boost", 1.0)
    pos, look = v0.pos, v0.look
    dsub = max(1e-6, length(sub(look, pos)))
    if kind == "drift":
        r, _u, _f = basis(pos, look)
        d = norm(tuple(p["dir"])) if "dir" in p else r
        off = mul(d, _hold_rate(p, kind, dsub) * dt)
        pos, look = add(pos, off), add(look, off)
    elif kind == "orbit":
        a = math.radians(p["deg_s"] * bo * dt)
        rel = sub(pos, look)
        ca, sa = math.cos(a), math.sin(a)
        rise = math.copysign(min(abs(p.get("rise", 0.0)), HOLD_MAX_REL * dsub), p.get("rise", 0.0)) * bo
        pos = add(look, (rel[0] * ca - rel[1] * sa, rel[0] * sa + rel[1] * ca, rel[2] + rise * dt))
    elif kind == "crane":
        up = _hold_rate(p, kind, dsub) * dt
        pos = add(pos, (0.0, 0.0, up))
        look = add(look, (0.0, 0.0, up * p["follow"]))
    elif kind in ("push", "pull"):
        f = norm(sub(look, pos))
        step = _hold_rate(p, kind, dsub) * dt * (1 if kind == "push" else -1)
        step = min(step, PUSH_MAX_FRAC * dsub)
        pos = add(pos, mul(f, step))
    else:
        raise ValueError("unknown hold type %r" % kind)
    lens = v0.lens * (1.0 + p.get("zoom_s", 0.0) * dt)
    if "look_to" in p and resolver is not None:        # slow re-aim during the hold (e.g. down to the creek)
        tgt = resolver.anchor_pos(p["look_to"])
        k = smootherstep(dt / max(0.1, p.get("look_s", 3.0)))
        look = lerp(look, tgt, k)
    return View(pos, look, lens)


def boosted(view, spec, fps, min_px=MIN_PX_PER_FRAME, resolver=None):
    """Copy of the hold spec whose speed guarantees >= min_px screen motion per frame (never a dead-still camera)."""
    spec = dict(spec or {"type": "drift"})
    spec.pop("_boost", None)
    m = min(screen_motion(hold_view(view, spec, t, resolver), hold_view(view, spec, t + 1.0 / fps, resolver))[0]
            for t in [0.5 * i for i in range(13)])     # slowest point of the first 6 s (look_to/push slow down)
    if m < min_px:
        spec["_boost"] = round(min(25.0, (min_px * 1.25) / max(m, 1e-3)), 3)
    return spec


HOLD_CAP_FRAC = 0.25       # a hold key travels at most 25 % of its subject distance in total (drift/crane/push/pull)
ORBIT_CAP_DEG = 18.0       # ... and orbits at most ~18 deg in total
MACRO_D = 0.5              # drift on a subject closer than this becomes a slow orbit (same 18 deg cap)


def cap_hold(view, spec, hold_s):
    """Copy of `spec` whose TOTAL motion over hold_s seconds stays within the caps above (rates only go down).
    Default rates stay 1.5 %/s of d; explicit legacy speeds keep their (<= 10 %/s) rate unless the cap is lower."""
    spec = dict(spec or {"type": "drift"})
    for k in ("_boost", "_capped"):
        spec.pop(k, None)
    kind = spec.get("type", "drift")
    d = max(1e-6, length(sub(view.look, view.pos)))
    hs = max(float(hold_s), 1e-3)
    if kind == "drift" and d < MACRO_D:
        sign = -1.0 if float(spec.get("deg_s", 1.0)) < 0 else 1.0
        spec = {k: v for k, v in spec.items() if k not in ("speed", "rel", "dir")}
        spec.update({"type": "orbit", "deg_s": sign * HOLD_DEFAULTS["orbit"]["deg_s"], "_macro": True})
        kind = "orbit"
    if kind in ("drift", "crane", "push", "pull"):
        rate = _hold_rate(spec, kind, d) / d
        cap = HOLD_CAP_FRAC / hs
        if abs(rate) > cap:
            spec.pop("speed", None)
            spec["rel"], spec["_capped"] = math.copysign(cap, rate), True
    elif kind == "orbit":
        deg = float(spec.get("deg_s", HOLD_DEFAULTS["orbit"]["deg_s"]))
        if abs(deg) > ORBIT_CAP_DEG / hs:
            spec["deg_s"], spec["_capped"] = math.copysign(ORBIT_CAP_DEG / hs, deg), True
        if abs(spec.get("rise", 0.0)) * hs > HOLD_CAP_FRAC * d:
            spec["rise"] = math.copysign(HOLD_CAP_FRAC * d / hs, spec["rise"])
    return spec


def hold_total(view, spec, hold_s):
    """(total travel / subject distance, total orbit deg) of a (capped, maybe boosted) hold over hold_s."""
    d = max(1e-6, length(sub(view.look, view.pos)))
    kind = spec.get("type", "drift")
    if kind == "orbit":
        return 0.0, abs(float(spec.get("deg_s", HOLD_DEFAULTS["orbit"]["deg_s"]))) * spec.get("_boost", 1.0) * hold_s
    return abs(_hold_rate(spec, kind, d)) * hold_s / d, 0.0


# ------------------------------------------------------------------ the plan
def _move_view(kind, a, b, via, t):
    e = ease_snap(t) if kind == "snap" else ease_sine(t) if kind == "crane" else ease_cubic(t) if kind == "backout" \
        else smootherstep(t)
    pts = [a.pos] + [tuple(v) for v in (via or [])] + [b.pos]
    pos = catmull(pts, e)
    look = lerp(a.look, b.look, e)
    lens = math.exp(math.log(a.lens) + (math.log(b.lens) - math.log(a.lens)) * e)
    return View(pos, look, lens)


def _auto_via(kind, a, b, height_fn):
    """Long travels get a gentle fly-over arc (and always clear the terrain at the midpoint)."""
    if kind == "snap":
        return []
    d = length(sub(b.pos, a.pos))
    if d < 25.0:
        return []
    mid = lerp(a.pos, b.pos, 0.5)
    lift = min(0.12 * d, 25.0)
    z = max(mid[2] + lift, (height_fn(mid[0], mid[1]) + 4.0) if height_fn else -1e9)
    return [(mid[0], mid[1], z)]


def _crane_via(a, b):
    """Crane = rise (or fall) first, then settle onto the target: one via point above/below the start, nudged 20 %
    towards the target (the 'slight lateral drift')."""
    d = math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])
    up = b.pos[2] >= a.pos[2]
    z = (max(a.pos[2], b.pos[2]) + min(0.15 * d, 30.0)) if up else (min(a.pos[2], b.pos[2]) + 0.25 * (a.pos[2] - b.pos[2]))
    return [(a.pos[0] + (b.pos[0] - a.pos[0]) * 0.2, a.pos[1] + (b.pos[1] - a.pos[1]) * 0.2, z)]


PORTAL_FILL = 0.92        # the dive stops this far along start -> look point (the surface fills the frame)
PORTAL_EMERGE = 0.6       # the emerge starts this many target focus-distances behind the target camera


def _portal_view(a, b, t, n):
    """(view, phase) for a portal move at t in (0, 1]: phase 'in' (push into a's look surface, easeInQuad) or
    'out' (emerge towards b along b's look direction, easeOutQuad). The cut sits between the two halves."""
    half = max(1, n // 2) / float(n)
    if t <= half + 1e-9:
        u = t / half
        e = u * u
        fill = lerp(a.pos, a.look, PORTAL_FILL)
        return View(lerp(a.pos, fill, e), a.look, a.lens), "in"
    u = (t - half) / (1.0 - half)
    e = 1 - (1 - u) * (1 - u)
    f = norm(sub(b.look, b.pos))
    back = PORTAL_EMERGE * length(sub(b.look, b.pos))
    p0 = sub(b.pos, mul(f, back))
    return View(lerp(p0, b.pos, e), b.look, b.lens), "out"


def _near(ref, target):
    """True when the target camera is within max(30 m, 3 x ref's focus distance) of the reference view: used to
    tell moves INSIDE an enlarged portal set (near its entry view) from moves back OUT (near the outside view)."""
    r = max(30.0, 3.0 * length(sub(ref.look, ref.pos)))
    return length(sub(target.pos, ref.pos)) < r


def _polyline_view(views, t):
    """Catmull-Rom through the positions AND look points of `views`, piecewise-log lens; t in 0..1."""
    pos = catmull([v.pos for v in views], t)
    look = catmull([v.look for v in views], t)
    n = len(views) - 1
    s = max(0.0, min(1.0, t)) * n
    i = min(int(s), n - 1)
    u = s - i
    la, lb = views[i].lens, views[i + 1].lens
    return View(pos, look, math.exp(math.log(la) + (math.log(lb) - math.log(la)) * u))


# ------------------------------------------------------------------ compact "oneshot" block (Page 3) -> camera keys
PUSH_IN_FRAC = 0.4        # snap/portal to the current stop: move 40 % of the way to the look point
PUSH_IN_LENS = 1.12       # ... with a slight lens change
BACKOUT_SETTLE_S = 0.4    # backout ends this long before the last frame; the settle hold lands ON frame 1's view
def is_compact_oneshot(episode):
    oc = episode.get("oneshot") or {}
    return isinstance(oc, dict) and all(k in oc for k in ("world", "stops", "moves")) and isinstance(oc["stops"], list)


def expand_oneshot(episode):
    """Copy of `episode` whose beats carry shot.camera keys built from the compact oneshot block. Beats that already
    have shot.camera keep them. Returns (episode, notes). Raises ValueError on a malformed block."""
    import copy
    if not is_compact_oneshot(episode):
        return episode, []
    ep = copy.deepcopy(episode)
    oc = ep["oneshot"]
    beats, stops, moves = ep["beats"], oc["stops"], oc["moves"]
    notes = []
    if not (len(stops) == len(moves) == len(beats)):
        raise ValueError("oneshot block: %d stops / %d moves for %d beats" % (len(stops), len(moves), len(beats)))
    if oc.get("beats") and list(oc["beats"]) != [b["id"] for b in beats]:
        raise ValueError("oneshot.beats %s != episode beat ids %s" % (oc["beats"], [b["id"] for b in beats]))
    durs = dict(DEFAULT_DUR)
    durs.update({k: float(v) for k, v in (oc.get("move_durations_s") or {}).items()})
    lead = float(oc.get("lead_s", 0.4))
    for i, (b, stop, mv) in enumerate(zip(beats, stops, moves)):
        shot = b.setdefault("shot", {})
        if shot.get("camera"):
            notes.append("beat %s: explicit shot.camera kept" % b["id"])
            continue
        orbit_sign = 1.0 if i % 2 == 0 else -1.0             # orbit direction alternates beat to beat
        hold = {"type": "drift"}
        if mv == "orbit":
            hold = {"type": "orbit", "deg_s": orbit_sign * HOLD_DEFAULTS["orbit"]["deg_s"]}
        if i == 0:
            if mv not in ("drift", "orbit", "crane"):
                notes.append("beat %s: first move %r is not a hold; using drift (no whip on frame 1)" % (b["id"], mv))
                mv = "drift"
            key = {"move": "none", "to": stop, "cue": 0.0, "lead": 0.0,
                   "hold": hold if mv != "crane" else {"type": "crane"}}
        elif mv in ("drift", "orbit") and stop == stops[i - 1]:
            key = {"move": "none", "cue": 0.0, "lead": 0.0, "hold": hold}
        elif mv in ("drift", "orbit"):
            key = {"move": "travel", "to": stop, "dur": durs["travel"], "cue": 0.0, "lead": lead, "hold": hold}
        elif mv in ("snap", "portal") and stop == stops[i - 1]:
            # already at this stop: a short push-in (40 % closer, lens x1.12) instead of a no-op / self-portal
            key = {"move": "snap", "push_in": PUSH_IN_FRAC, "lens_mul": PUSH_IN_LENS, "dur": durs["snap"],
                   "cue": 0.0, "lead": lead, "hold": hold}
            j = i - 1
            while j >= 0 and stops[j] == stop:
                if moves[j] == "section":          # keep the cut-away open through the push-in
                    key["section"] = stop
                    break
                j -= 1
            if mv == "portal":
                notes.append("beat %s: portal to the stop it is already at -> snap push-in" % b["id"])
        elif mv in MOVE_KINDS:
            key = {"move": mv, "to": stop, "dur": durs.get(mv, 1.5), "cue": 0.0, "lead": lead, "hold": hold}
            if mv == "section":
                key["section"] = stop
            if mv == "backout":
                key["to"] = stops[0]
        else:
            raise ValueError("beat %s: unknown oneshot move %r (moves: %s + drift/orbit)" % (b["id"], mv, MOVE_KINDS))
        key["stop"] = stop
        shot["camera"] = [key]
    oc["_expanded"] = True
    return ep, notes


# ------------------------------------------------------------------ the Spark (optional emissive orb)
SPARK_LEAD_S = 0.3


def _hex_lin(h):
    h = h.lstrip("#")
    c = [int(h[k:k + 2], 16) / 255.0 for k in (0, 2, 4)]
    return [round(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4, 4) for v in c]


def spark_track(episode, layout, windows, cam, fps):
    """{"colors": {name: linear rgb}, "events": [{f, value}], "track": [None, [x, y, z, r], ...]} or None.
    Colour events sit mid-move of the beat's move, or at the beat start when the beat only changes the hold
    (then it is a 0.5 s blend / 0.3 s fade, not a swap).
    The orb leads the camera by SPARK_LEAD_S along the camera path, 55 % of the way to the look point, with a
    slow idle wobble; r keeps it ~2.5 % of the frame width (r = 0.0125 * dist * 36 / lens), 0 when 'off'."""
    oc = episode.get("oneshot") or {}
    per_beat = oc.get("spark")
    if not per_beat:
        return None
    cols = {"teal": "#00B3A4", "amber": "#FFB000", "ice": "#7FD4FF"}
    cols.update(oc.get("spark_colors") or {})
    events, cur = [], None
    for b, val in zip(layout, per_beat):
        if val == cur:
            continue
        bw = [w for w in windows if w["beat"] == b["id"]]
        events.append({"f": 1 if cur is None else (bw[0]["mid"] if bw else b["f0"]), "value": val})
        cur = val
    total = len(cam) - 1
    lead = int(round(SPARK_LEAD_S * fps))
    fade = max(1, int(round(0.3 * fps)))
    track, amp, ei, val = [None], 0.0, -1, None
    for f in range(1, total + 1):
        v = cam[min(total, f + lead)]
        here = cam[f]
        d = length(sub(v.look, v.pos))
        t = f / float(fps)
        wob = (math.sin(t * 1.3), math.cos(t * 0.9), 0.5 * math.sin(t * 1.7))
        p = add(lerp(v.pos, v.look, 0.55), mul(wob, 0.04 * d))
        r = 0.0125 * length(sub(p, here.pos)) * 36.0 / max(1.0, here.lens)
        r = min(3.0, max(0.0003, r))
        while ei + 1 < len(events) and events[ei + 1]["f"] <= f:
            ei += 1
            val = events[ei]["value"]
        goal = 0.0 if val in (None, "off") else 1.0      # 'off' fades out / back in over 0.3 s (scale), never a pop
        amp = goal if f == 1 else (min(goal, amp + 1.0 / fade) if goal > amp else max(goal, amp - 1.0 / fade))
        track.append([round(p[0], 6), round(p[1], 6), round(p[2], 6), round(r * amp, 7)])
    return {"colors": {k: _hex_lin(v) for k, v in cols.items()}, "events": events, "track": track,
            "lead_s": SPARK_LEAD_S, "blend_s": 0.5,
            "note": "colour changes blend over blend_s from each event frame (mid-move when the beat has a move); "
                    "track rows = [x, y, z, radius]; radius 0 = hidden"}


def obstacles_from(loc, names=("house", "garage", "workshop", "battery_shed", "porch")):
    out = []
    zs = (loc or {}).get("zones", {})
    for n in names:
        if n in zs:
            p, s = zs[n]["pos"], zs[n]["size"]
            roof = 3.0 if n in ("house", "garage", "workshop") else 0.5
            out.append((n, p[0] - s[0] / 2, p[0] + s[0] / 2, p[1] - s[1] / 2, p[1] + s[1] / 2, p[2] + s[2] + roof))
    return out


def build_plan(episode, timings, words, loc=None, height_fn=None, fps=None, extra_anchors=None):
    fps = int(fps or episode.get("render", {}).get("fps", DEFAULT_FPS))
    oc = episode.get("oneshot", {})
    min_hold = float(oc.get("min_hold_s", MIN_HOLD_S))
    layout = beat_layout(episode, timings, fps)
    total = layout[-1]["f0"] + layout[-1]["frames"] - 1
    res = SpotResolver(loc, episode.get("spots"), extra_anchors, episode.get("sections"), height_fn)
    warnings = []

    # 1. keys -> frames
    keys = []
    for b, beat in zip(layout, episode["beats"]):
        shot = beat.get("shot", {})
        bw = [w for w in words if w.get("beat") == b["id"]]
        for ki, k in enumerate(shot.get("camera", [])):
            kind = k.get("move", "travel")
            dur = float(k.get("dur", DEFAULT_DUR.get(kind, 0.0)))
            if kind == "snap" and not 0.15 <= dur <= 0.45:
                warnings.append("beat %s key %d: snap dur %.2fs outside 0.2-0.4 s" % (b["id"], ki, dur))
            t_cue = resolve_cue(k.get("cue"), bw, b)
            t0 = max(0.0, t_cue - float(k.get("lead", 0.4 if kind != "none" else 0.0)))
            keys.append({"beat": b["id"], "bi": b["idx"], "ki": ki, "spec": k, "move": kind,
                         "f0": time_to_frame(layout, t0, fps), "nf": max(2, int(round(dur * fps))) if kind != "none" else 0,
                         "t_cue": round(t_cue, 3)})
    if not keys:
        raise ValueError("episode has no camera keys")
    # 2. de-overlap (moves keep order; a move never starts before the previous one ends + min hold)
    gap = max(1, int(round(min_hold * fps)))
    for i in range(1, len(keys)):
        prev = keys[i - 1]
        earliest = prev["f0"] + prev["nf"] + (gap if prev["nf"] else 0)
        if keys[i]["f0"] < earliest:
            warnings.append("beat %s key %d delayed %d frames (overlaps the previous move)" % (
                keys[i]["beat"], keys[i]["ki"], earliest - keys[i]["f0"]))
            keys[i]["f0"] = earliest
    # backout: timed to END the reel (finish `settle` frames before the last frame; the settle hold lands on frame 1)
    settle = max(1, int(round(float(oc.get("backout_settle_s", BACKOUT_SETTLE_S)) * fps)))
    last = keys[-1]
    if last["move"] == "backout":
        prev = keys[-2] if len(keys) > 1 else None
        earliest = (prev["f0"] + prev["nf"] + (gap if prev["nf"] else 0)) if prev else 1
        want = total - settle - last["nf"] + 1
        if want < earliest:
            warnings.append("backout shortened %d -> %d frames (no room after the previous move)"
                            % (last["nf"], max(2, total - settle - earliest + 1)))
            last["nf"] = max(2, total - settle - earliest + 1)
            want = max(earliest, total - settle - last["nf"] + 1)
        last["f0"] = want
    for k in keys:
        if k["f0"] + k["nf"] > total:
            k["nf"] = max(0, total - k["f0"])
    # 3. walk the timeline
    first = keys[0]
    start_spec = first["spec"].get("from", first["spec"].get("to"))
    cur = res.view(start_spec)
    hold_report = []

    def make_hold(view, spec, f_start, f_end, label):
        """cap (25 % of d / 18 deg per hold key) THEN guarantee the minimum motion; log holds where it overrides."""
        hs = max(1, f_end - f_start + 1) / float(fps)
        sp = boosted(view, cap_hold(view, spec, hs), fps, resolver=res)
        tr, deg = hold_total(view, sp, hs)
        row = {"label": label, "f0": f_start, "f1": f_end, "type": sp.get("type"), "seconds": round(hs, 2),
               "subject_m": round(length(sub(view.look, view.pos)), 6), "travel_x_d": round(tr, 3),
               "orbit_deg": round(deg, 1), "capped": bool(sp.get("_capped")), "macro_orbit": bool(sp.get("_macro")),
               "boost": sp.get("_boost", 1.0)}
        if tr > HOLD_CAP_FRAC + 1e-6 or deg > ORBIT_CAP_DEG + 1e-6:
            row["min_motion_wins"] = True
            warnings.append("hold %s f%d-%d: 0.6 px/frame minimum overrides the cap (%.2f x d, %.0f deg)"
                            % (label, f_start, f_end, tr, deg))
        hold_report.append(row)
        return sp

    def next_f0(i):
        return keys[i + 1]["f0"] - 1 if i + 1 < len(keys) else total
    cur_hold, hold_f0 = make_hold(cur, first["spec"].get("from_hold", {"type": "drift"}), 1,
                                  max(1, keys[0]["f0"] - 1), "opening"), 1
    origin = (cur, cur_hold) if first["f0"] > 1 else None      # the hold that frame 1 is part of (dt = f / fps)
    cam = [None] * (total + 1)
    move_of = ["hold"] * (total + 1)
    windows, events, arrivals, joins = [], [], [], []
    portal_ctx = None                  # set while the camera is inside an enlarged set entered by a portal
    hidden_joins = [list(j) for j in oc.get("hidden_joins", [])]
    f = 1
    for i, k in enumerate(keys):
        # hold until this move starts
        while f < k["f0"] and f <= total:
            cam[f] = hold_view(cur, cur_hold, (f - hold_f0 + 1) / float(fps), res)
            f += 1
        start_view = hold_view(cur, cur_hold, (f - hold_f0) / float(fps), res)
        last_to = windows[-1]["to"] if windows else (first["spec"].get("to") if first["move"] == "none" else None)
        if (k["move"] in ("snap", "portal") and "push_in" not in k["spec"] and isinstance(k["spec"].get("to"), str)
                and isinstance(last_to, str)
                and split_variant(k["spec"]["to"])[0] == split_variant(last_to)[0]):
            # snap/portal to the stop we are already at (also via a __detail/__alt alias): a push-in, never a
            # no-op or a pull-out
            k["spec"] = dict(k["spec"], push_in=PUSH_IN_FRAC, lens_mul=PUSH_IN_LENS)
            k["move"] = "snap"
            warnings.append("beat %s key %d: %s to the current stop %s -> push-in" % (k["beat"], k["ki"],
                            k["spec"].get("move"), last_to))
        if "push_in" in k["spec"]:                 # relative push-in on the current subject
            target = View(lerp(start_view.pos, start_view.look, float(k["spec"]["push_in"])), start_view.look,
                          start_view.lens * float(k["spec"].get("lens_mul", 1.0)))
        else:
            target = res.view(k["spec"]["to"]) if "to" in k["spec"] else start_view
        if k["move"] == "none" or k["nf"] == 0:
            cur = target if i == 0 else start_view
            cur_hold, hold_f0 = make_hold(cur, k["spec"].get("hold", cur_hold), f, next_f0(i),
                                          "%s.%d" % (k["beat"], k["ki"])), f
            if i == 0 and f == 1:
                origin = (cur, cur_hold)
            k["f1"] = k["f0"]
            continue
        via = k["spec"].get("via")
        if via is not None:
            via = [tuple(v) for v in via]
        elif k["move"] == "crane":
            via = _crane_via(start_view, target)
        else:
            via = _auto_via(k["move"], start_view, target, height_fn)
        n = k["nf"]
        join, exit_view, n_exit = None, None, 0
        if k["move"] == "backout":       # ONE eased arc straight back to the opening framing (lifted if long)
            target = hold_view(origin[0], origin[1], (1 - settle) / float(fps), res) if origin else cam[1].copy()
            arc_from = start_view
            if portal_ctx is not None:   # inside an enlarged/portal set: first EXIT through a reverse portal
                exit_view = portal_ctx["outside"]
                n_exit = min(max(2, int(round(DEFAULT_DUR["portal"] * fps))), max(2, n // 3))
                arc_from = exit_view
            via = [tuple(v) for v in k["spec"]["via"]] if k["spec"].get("via") is not None else \
                _auto_via("travel", arc_from, target, height_fn)
        for j in range(n):
            if f > total:
                break
            t = (j + 1) / float(n)
            if exit_view is not None and j < n_exit:      # reverse portal: fill-frame hop out to the outside view
                cam[f], phase = _portal_view(start_view, exit_view, (j + 1) / float(n_exit), n_exit)
                if phase == "out" and join is None:
                    join = f
            elif exit_view is not None:
                cam[f] = _move_view("backout", exit_view, target, via, (j + 1 - n_exit) / float(n - n_exit))
            elif k["move"] == "portal":
                cam[f], phase = _portal_view(start_view, target, t, n)
                if phase == "out" and join is None:
                    join = f
            else:
                cam[f] = _move_view(k["move"], start_view, target, via, t)
            move_of[f] = k["move"]
            f += 1
        if join is not None:
            joins.append(join)
            hidden_joins.append([join - 1, join + 1])
            if exit_view is not None:
                events.append({"f": join, "kind": "portal", "value": "exit:%s" % portal_ctx["stop"]})
            else:
                events.append({"f": join, "kind": "portal", "value": k["spec"].get("stop", k["spec"].get("to"))
                               if isinstance(k["spec"].get("to"), str) else "custom"})
        to_s = k["spec"].get("to") if isinstance(k["spec"].get("to"), str) else None
        if k["move"] != "backout":
            if portal_ctx is not None:
                if k["move"] == "portal":
                    if _near(portal_ctx["outside"], target):
                        portal_ctx = None  # portal back out to where the camera came from
                elif not _near(portal_ctx["entry"], target):
                    portal_ctx = None      # travelled away from the enlarged set (left it in the open)
            elif k["move"] == "portal" and to_s and "push_in" not in k["spec"]:
                portal_ctx = {"stop": to_s, "outside": start_view.copy(), "entry": target.copy()}   # outermost
        k["f1"] = k["f0"] + n - 1
        mid = k["f0"] + n // 2
        windows.append({"kind": k["move"], "f0": k["f0"], "f1": k["f1"], "beat": k["beat"], "key": k["ki"],
                        "blur": k["move"] in BLUR_MOVES or bool(k["spec"].get("blur")), "mid": mid,
                        "to": k["spec"].get("to") if isinstance(k["spec"].get("to"), str) else "custom"})
        if k["move"] == "section":
            events.append({"f": mid, "kind": "section", "value": k["spec"].get("section", "default")})
        elif "section" in k["spec"]:
            events.append({"f": mid, "kind": "section", "value": k["spec"]["section"]})
        for kind in ("cast", "lights"):
            if kind in k["spec"]:
                events.append({"f": mid, "kind": kind, "value": k["spec"][kind], "beat": k["beat"]})
        if "preset" in k["spec"]:
            events.append({"f": mid, "kind": "preset", "value": k["spec"]["preset"]})
        if join is not None:
            windows[-1]["join"] = join
        if "stop" in k["spec"]:
            windows[-1]["stop"] = k["spec"]["stop"]
        if "push_in" in k["spec"]:
            windows[-1]["push_in"] = True
        if exit_view is not None:
            windows[-1]["exit_portal"] = [k["f0"], k["f0"] + n_exit - 1]
        if k["move"] == "backout":
            if origin:                   # settle = the opening hold run up to dt = 1/fps on the LAST frame
                cur, cur_hold, hold_f0 = origin[0], origin[1], total
            else:                        # frame 1 was a move: hold its exact view (<= settle, never > 1 s)
                cur, cur_hold, hold_f0 = target, {"type": "drift", "rel": 0.0}, f
            continue
        arrivals.append(target)
        cur, hold_f0 = target, f
        cur_hold = make_hold(target, k["spec"].get("hold", {"type": "drift"}), f, next_f0(i),
                             "%s.%d" % (k["beat"], k["ki"]))
    while f <= total:
        cam[f] = hold_view(cur, cur_hold, (f - hold_f0 + 1) / float(fps), res)
        f += 1
    # a section move that dips below the terrain before its middle opens the cut-away earlier (still inside the move)
    if height_fn is not None:
        for w in windows:
            if w["kind"] != "section":
                continue
            under = [g for g in range(w["f0"], w["mid"] + 1)
                     if cam[g] is not None and cam[g].pos[2] < height_fn(cam[g].pos[0], cam[g].pos[1]) + 0.9]
            if under:
                for e in events:
                    if e["kind"] == "section" and e["f"] == w["mid"] and e["value"] is not None:
                        e["f"] = max(w["f0"], under[0] - 2)
    # leaving a section: the cut-away stays until the next move's middle
    sec_on = [e for e in events if e["kind"] == "section"]
    for e in sec_on:
        nxt = [w for w in windows if w["f0"] > e["f"]]          # the NEXT move (not the section move itself)
        if nxt and not any(o["f"] == nxt[0]["mid"] for o in sec_on):     # next move opens another section
            events.append({"f": nxt[0]["mid"], "kind": "section", "value": None})
    # 4. per-beat preset + cast changes, placed mid-move (first move of the beat, else beat start + warning)
    cur_preset = None
    for b, beat in zip(layout, episode["beats"]):
        shot = beat.get("shot", {})
        bwin = [w for w in windows if w["beat"] == b["id"]]
        at = bwin[0]["mid"] if bwin else b["f0"]
        p = shot.get("preset")
        if p and p != cur_preset:
            if cur_preset is not None and not bwin:
                warnings.append("beat %s: preset change %s->%s has no move to hide it" % (b["id"], cur_preset, p))
            events.append({"f": 1 if cur_preset is None else at, "kind": "preset", "value": p})
            cur_preset = p
        for kind in ("cast", "lights"):
            if kind in shot:
                if b["idx"] > 0 and not bwin:
                    warnings.append("beat %s: %s change has no move to hide it" % (b["id"], kind))
                events.append({"f": 1 if b["idx"] == 0 else at, "kind": kind, "value": shot[kind], "beat": b["id"]})
    events.sort(key=lambda e: (e["f"], e["kind"]))
    # 5. clearance pass (terrain + roofs), smooth lift, never inside a section move
    lift_need = [0.0] * (total + 1)
    obst = obstacles_from(loc)
    for f in range(1, total + 1):
        v = cam[f]
        if move_of[f] in ("section", "portal") or state_at({"events": events}, "section", f):
            continue
        need = 0.0
        if height_fn is not None:
            need = max(need, height_fn(v.pos[0], v.pos[1]) + 0.9 - v.pos[2])
        for (_n, x0, x1, y0, y1, ztop) in obst:
            if x0 - 0.4 <= v.pos[0] <= x1 + 0.4 and y0 - 0.4 <= v.pos[1] <= y1 + 0.4 and v.pos[2] < ztop + 0.8:
                need = max(need, ztop + 0.8 - v.pos[2])
        lift_need[f] = need
    W = 12
    for f in range(1, total + 1):
        lv = 0.0
        for g in range(max(1, f - W), min(total, f + W) + 1):
            if lift_need[g] > 0:
                lv = max(lv, lift_need[g] * (1.0 - abs(f - g) / float(W + 1)))
        if lv > 0 and move_of[f] != "portal":
            v = cam[f]
            cam[f] = View(add(v.pos, (0, 0, lv)), add(v.look, (0, 0, lv * 0.5)), v.lens)
    # 6. speed per frame
    speed = [{"f": 1, "px": 0.0, "dx": 0.0, "dy": 0.0, "lin": 0.0, "move": move_of[1]}]
    for f in range(2, total + 1):
        m, dx, dy = screen_motion(cam[f - 1], cam[f])
        speed.append({"f": f, "px": round(m, 3), "dx": round(dx, 3), "dy": round(dy, 3),
                      "lin": round(length(sub(cam[f].pos, cam[f - 1].pos)) * fps, 3), "move": move_of[f]})
    if len(speed) > 1:
        speed[0].update({k: speed[1][k] for k in ("px", "dx", "dy", "lin")})
    for jf in joins:                 # portal cut: not real motion; clamp to the neighbours and flag it
        s = speed[jf - 1]
        nb = [speed[g - 1]["px"] for g in (jf - 1, jf + 1) if 1 <= g <= total and g != jf]
        s.update({"px": round(min(nb or [0.0]), 3), "join": True})
    plan = {"fps": fps, "frames": total, "beats": layout, "windows": windows, "events": events,
            "keys": [{k2: v for k2, v in k.items() if k2 != "spec"} for k in keys],
            "hidden_joins": hidden_joins, "warnings": warnings, "holds": hold_report,
            "cam": [None] + [cam[f].as_list() for f in range(1, total + 1)]}
    hf_, hw_, longest = check_holds(plan)
    plan["longest_hold"] = longest
    for h in hf_:
        warnings.append("HOLD TOO LONG (> %.0f s): %.1f s f%d-%d (beat %s)" % (MAX_HOLD_S, h["s"], h["f0"], h["f1"], h["beat"]))
    for h in hw_:
        warnings.append("hold over %.0f s: %.1f s f%d-%d (beat %s)" % (WARN_HOLD_S, h["s"], h["f0"], h["f1"], h["beat"]))
    sp = spark_track(episode, layout, windows, cam, fps)
    if sp:
        plan["spark"] = sp
    return plan, speed


MAX_HOLD_S = 10.0          # chief's rule (both Pages): a hold over 10 s FAILS ...
WARN_HOLD_S = 9.0          # ... over 9 s warns; plan for <= ~7 s so real TTS timing keeps the margin


def hold_segments(plan):
    """[{f0, f1, s, beat}] for every stretch between move windows (hold-type changes do not end a hold)."""
    out, f = [], 1
    for w in sorted(plan["windows"], key=lambda w: w["f0"]):
        if w["f0"] > f:
            out.append((f, w["f0"] - 1))
        f = max(f, w["f1"] + 1)
    n = plan.get("frames") or max([w["f1"] for w in plan["windows"]] + [1])
    if f <= n:
        out.append((f, n))
    return [{"f0": a, "f1": b, "s": round((b - a + 1) / float(plan["fps"]), 2),
             "beat": frame_to_beat(plan["beats"], a)["id"] if plan.get("beats") else None} for a, b in out]


def check_holds(plan, max_s=MAX_HOLD_S, warn_s=WARN_HOLD_S):
    """(fails, warns, longest): holds over max_s fail, over warn_s warn."""
    segs = hold_segments(plan)
    fails = [h for h in segs if h["s"] > max_s]
    warns = [h for h in segs if warn_s < h["s"] <= max_s]
    return fails, warns, (max(segs, key=lambda h: h["s"]) if segs else None)


def static_runs(speed, fps, thresh=MIN_PX_PER_FRAME * 0.5, max_s=1.0):
    """[(f0, f1)] runs where the planned camera moves less than `thresh` px/frame for more than max_s seconds."""
    runs, start = [], None
    for s in speed + [{"f": None, "px": 1e9}]:
        if s["px"] < thresh:
            if start is None:
                start = s["f"]
            last = s["f"]
        else:
            if start is not None and (last - start + 1) > max_s * fps:
                runs.append((start, last))
            start = None
    return runs


def events_at(plan, kind):
    return [e for e in plan["events"] if e["kind"] == kind]


def state_at(plan, kind, f, default=None):
    """Value of the latest `kind` event at or before frame f."""
    v = default
    for e in plan["events"]:
        if e["kind"] == kind and e["f"] <= f:
            v = e["value"]
    return v

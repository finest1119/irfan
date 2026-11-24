"""One-shot WORLD REGISTRY shared by Page 2 (Mercer Hollow) and Page 3 (Hometown USA). bpy-free.

Interface (agreed with the Page 3 session):
  WORLDS = {world_id: (module, build_fn)}            Blender side, imported lazily inside Blender only.
      build_fn(ctx, state) -> {anchor_id: ANC_<anchor_id> empty}
          ctx   = scene_lib Ctx (scene, frames, fps, .anchors, .plan, .frame_range)
          state = {"world_id", "episode", "plan", "workdir", "parts", "focus", "frame_range", "world_state"}
                  (the build may store its own handle in state["world"]; render_oneshot passes it to apply_events)
      render_oneshot registers every returned anchor for the 2D tracks (tracks_v2 key = id), so a world does not
      need to call scene_lib_v2.anchor itself. Every camera `to` / stop id must resolve against these anchors. Anchors are Blender empties named
      ANC_<id> (the look/label point); a stop may also have CAM_<id> (its default camera position).
      WORLD_ROOT: if the build creates an empty named WORLD_ROOT (rebase/offset), render_oneshot parents the camera,
      its target and the Spark to it (plan coordinates = WORLD_ROOT-local); otherwise it creates one at the origin.
      plan_anchors(state) receives state["episode"] = the SAME (adapter-expanded) object build_plan then uses.
      Optional module function apply_events(state, plan, lo, hi): key world reactions (lids, peels, rebase, clip
      planes) to plan["events"] (kinds: preset, section, lights, cast, portal).
  PLAN_ANCHORS = {world_id: (module, fn)}            bpy-free, used by `oneshot.py plan` (no Blender).
      fn(state) -> {"anchors": {id: [x, y, z]}, "cams": {id: {"pos": [x, y, z], "lens": mm}}}
  Registration without editing page2/: a world may also live in page2/blender/ or page3/blender/ as
      <world_id>.py       (Blender side: build(ctx, state))
      <world_id>_plan.py  (bpy-free:     plan_anchors(state))
  If neither exists, `plan` fails with WorldNotRegistered saying exactly what is missing.
  Plan-time fallback: WORKDIR/oneshot/anchors_<world_id>.json, written by render_oneshot after a build. It only
  helps once the world has rendered at least once (that first run itself needs the bpy-free plan_anchors).
"""
import importlib
import json
import sys
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent
ROOT = PAGE2.parent
WORLD_DIRS = [PAGE2 / "blender", ROOT / "page3" / "blender"]

WORLDS = {
    "mercer_hollow": ("world_mercer", "build_world"),
}
PLAN_ANCHORS = {
    "mercer_hollow": ("worlds", "mercer_plan_anchors"),
}


class WorldNotRegistered(RuntimeError):
    pass


def world_id_of(episode):
    oc = episode.get("oneshot") or {}
    if isinstance(oc, dict) and oc.get("world"):
        return oc["world"]
    return (episode.get("beats") or [{}])[0].get("shot", {}).get("location", "mercer_hollow")


def _rel(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def _discover(world_id):
    """(build_entry, plan_entry, dir) found by file convention, entries None when missing."""
    for d in WORLD_DIRS:
        b, p = d / (world_id + ".py"), d / (world_id + "_plan.py")
        if b.exists() or p.exists():
            return ((world_id, "build") if b.exists() else None,
                    (world_id + "_plan", "plan_anchors") if p.exists() else None, d)
    return None, None, None


def registered_worlds():
    """Every world id the driver can use: WORLDS entries + file-convention worlds (<id>.py + <id>_plan.py)."""
    out = set(WORLDS)
    for d in WORLD_DIRS:
        if d.exists():
            for f in d.glob("*_plan.py"):
                wid = f.name[:-len("_plan.py")]
                if (d / (wid + ".py")).exists():
                    out.add(wid)
    return sorted(out)


def _missing_msg(world_id, need, workdir=None):
    have = ", ".join(registered_worlds()) or "none"
    lines = ["one-shot world %r is not registered (%s side missing). Registered worlds: %s." % (world_id, need, have),
             "To register it, EITHER add to page2/blender/worlds.py:",
             "    WORLDS[%r] = (<module>, <build_fn>)            # Blender: build_fn(ctx, state) -> {id: ANC_<id> empty}"
             % world_id,
             "    PLAN_ANCHORS[%r] = (<module>, <fn>)          # bpy-free: fn(state) -> {'anchors': {id: [x,y,z]}, "
             "'cams': {id: {'pos': [x,y,z], 'lens': mm}}}" % world_id,
             "OR put these files in one of: %s" % ", ".join(_rel(d) for d in WORLD_DIRS)]
    for d in WORLD_DIRS:
        for fn in (world_id + ".py", world_id + "_plan.py"):
            lines.append("    %-40s %s" % (_rel(d / fn), "exists" if (d / fn).exists() else "MISSING"))
    lines.append("    (%s.py: build(ctx, state); %s_plan.py: plan_anchors(state))" % (world_id, world_id))
    if workdir is not None:
        lines.append("(Cache %s is also absent; it only exists after a first successful Blender build.)"
                     % _rel(Path(workdir) / "oneshot" / ("anchors_%s.json" % world_id)))
    return "\n".join(lines)


def _import(module, fn, extra_dir=None):
    for d in [extra_dir] + WORLD_DIRS:
        if d is not None and str(d) not in sys.path and Path(d).exists():
            sys.path.append(str(d))
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True       # never write __pycache__ into another page's folder (page3/ is read-only)
    try:
        mod = importlib.import_module(module)
    finally:
        sys.dont_write_bytecode = old
    if not hasattr(mod, fn):
        raise WorldNotRegistered("world module %s has no function %s()" % (module, fn))
    return mod, getattr(mod, fn)


def build_entry(world_id):
    """(module, fn) for the Blender build. Raises WorldNotRegistered."""
    if world_id in WORLDS:
        return _import(*WORLDS[world_id])
    b, _p, d = _discover(world_id)
    if b is None:
        raise WorldNotRegistered(_missing_msg(world_id, "Blender build"))
    return _import(b[0], b[1], d)


def plan_world(world_id, episode, workdir=None, world_state=None):
    """bpy-free: {"anchors": {id: (x, y, z)}, "cams": {id: {"pos", "lens"}}, "source": str}."""
    state = {"world_id": world_id, "episode": episode, "workdir": str(workdir) if workdir else None,
             "world_state": world_state}
    entry, d = PLAN_ANCHORS.get(world_id), None
    if entry is None:
        _b, entry, d = _discover(world_id)
    if entry is not None:
        _m, fn = _import(entry[0], entry[1], d)
        out = fn(state)
        src = "%s.%s" % entry
    else:
        cache = Path(workdir) / "oneshot" / ("anchors_%s.json" % world_id) if workdir else None
        if cache is None or not cache.exists():
            raise WorldNotRegistered(_missing_msg(world_id, "plan-time anchors", workdir))
        out = json.loads(cache.read_text(encoding="utf-8"))
        src = _rel(cache)
    anchors = {k: tuple(float(c) for c in v) for k, v in (out.get("anchors") or {}).items()}
    cams = {k: dict(v) for k, v in (out.get("cams") or {}).items()}
    return {"anchors": anchors, "cams": cams, "source": src}


def plan_location(world_id, episode, workdir=None, world_state=None, base_loc=None):
    """A camera_plan `loc` dict for a registered world: base_loc (Mercer: the world_state location) plus
    "anchors" and a camera_spot per stop that has CAM_<id> (pos) + ANC_<id> (look). Existing names win."""
    pw = plan_world(world_id, episode, workdir, world_state)
    loc = dict(base_loc or {})
    loc.setdefault("zones", {})
    anchors = dict(pw["anchors"])
    anchors.update(loc.get("anchors") or {})
    loc["anchors"] = anchors
    spots = dict(loc.get("camera_spots") or {})
    for k, c in pw["cams"].items():
        if k in spots or k not in pw["anchors"]:
            continue
        spots[k] = {"pos": list(c["pos"]), "look_at": list(pw["anchors"][k]), "lens_mm": c.get("lens", 28.0)}
    loc["camera_spots"] = spots
    loc["_anchor_source"] = pw["source"]
    return loc


def check_targets(episode, loc):
    """Names used as camera `to` / stops / label anchors that do not resolve. Returns (camera_missing, label_missing)."""
    sys.path.insert(0, str(PAGE2 / "blender"))
    import camera_plan as C
    spots = set(episode.get("spots") or {}) | set(loc.get("camera_spots") or {})
    anchors = set(loc.get("anchors") or {}) | set(loc.get("zones") or {})
    if isinstance(episode.get("anchors"), dict):
        anchors |= set(episode["anchors"])
    cam_missing, lab_missing = [], []
    for b in episode["beats"]:
        shot = b.get("shot", {})
        for k in shot.get("camera", []):
            t = k.get("to")
            if isinstance(t, str) and t not in spots and t not in anchors:
                base = C.split_variant(t)[0]
                if base != t and (base in spots or base in anchors):
                    continue                     # <stop>__detail/__alt: derived by camera_plan.variant_view
                cam_missing.append("%s:%s" % (b["id"], t))
        for o in shot.get("overlays", []) + b.get("overlays", []):
            a = o.get("anchor")
            if isinstance(a, str) and a not in anchors and a not in spots and C.split_variant(a)[0] not in anchors:
                lab_missing.append("%s:%s" % (b["id"], a))
    return cam_missing, lab_missing


# ------------------------------------------------------------------ Mercer Hollow (Page 2)
def mercer_plan_anchors(state):
    """Anchor table for Mercer Hollow, shared by plan time and world_mercer.build_world (same names in Blender):
    zones (centre, raised up to 2 m), episode anchors, camera spots as spot_<id> (legacy alias) AND <id> when the
    id is free (look point), with CAM_<id> positions. Build-time-only anchors (turbine parts, fridge...) are added
    by the world build itself."""
    sys.path.insert(0, str(PAGE2 / "blender"))
    import mh_paths as MP
    ws = state.get("world_state") or MP.world_state()
    ep = state.get("episode") or {}
    loc_name = (ep.get("beats") or [{}])[0].get("shot", {}).get("location", "mercer_hollow")
    loc = MP.location(ws, loc_name)
    anchors, cams = {}, {}
    for k, zz in loc.get("zones", {}).items():
        p = zz["pos"]
        anchors[k] = [p[0], p[1], p[2] + min(2.0, zz["size"][2] / 2 if len(zz["size"]) > 2 else 0.0)]
    for nb in (loc.get("street") or {}).get("neighbor_houses", []):
        anchors.setdefault(nb["id"], list(nb["pos"]))
    ea = ep.get("anchors")
    for k, p in (ea.items() if isinstance(ea, dict) else []):
        anchors[k] = list(p)
    import camera_plan as C
    res = C.SpotResolver(loc, ep.get("spots"), ea if isinstance(ea, dict) else None, ep.get("sections"),
                         MP.terrain_height_fn(loc))
    spots = dict(loc.get("camera_spots") or {})
    spots.update(ep.get("spots") or {})
    for k in spots:                    # every spot (pos/look_at, {anchor,dist,az}, section views) -> ANC + CAM
        try:
            v = res.view(k)
        except (KeyError, ValueError):
            continue
        look = [round(c, 4) for c in v.look]
        if k in (loc.get("camera_spots") or {}):
            anchors["spot_" + k] = look
        anchors.setdefault(k, look)
        cams[k] = {"pos": [round(c, 4) for c in v.pos], "lens": v.lens}
    for b in ep.get("beats") or []:        # <stop>__detail/__alt used by the camera: derived ANC + CAM
        for kk in (b.get("shot") or {}).get("camera") or []:
            t = kk.get("to")
            if isinstance(t, str) and C.split_variant(t)[1] and t not in anchors:
                try:
                    v = res.view(t)
                except (KeyError, ValueError):
                    continue
                anchors[t] = [round(c, 4) for c in v.look]
                cams[t] = {"pos": [round(c, 4) for c in v.pos], "lens": v.lens}
    return {"anchors": anchors, "cams": cams}


# ------------------------------------------------------------------ one entry point for plan inputs (driver + Blender)
BUILD_TIME_ANCHORS = ("bolts", "torque")      # created by characters/builds inside Blender (no plan-time position)


def is_page2_location(world_id, ws):
    return world_id in (ws.get("locations") or {}) or world_id in (ws.get("trips") or {})


def plan_inputs(episode, workdir=None, ws=None):
    """Everything camera_plan.build_plan needs, resolved the same way in the venv driver and inside Blender:
    returns (episode_expanded, loc, height_fn, extra_anchors, info). Raises WorldNotRegistered (unknown world)
    or ValueError (a camera target / stop that the world's anchors do not define)."""
    sys.path.insert(0, str(PAGE2 / "blender"))
    import camera_plan as C
    import mh_paths as MP
    wid = world_id_of(episode)
    ep, notes = C.expand_oneshot(episode)
    hf = None
    page2_world = wid in WORLDS and PLAN_ANCHORS.get(wid) == ("worlds", "mercer_plan_anchors")
    if not page2_world and wid not in WORLDS and _discover(wid)[2] is None:
        ws = ws or MP.world_state()
        page2_world = is_page2_location(wid, ws)
    if page2_world:
        ws = ws or MP.world_state()
        loc_name = ep["beats"][0].get("shot", {}).get("location", wid)
        base = MP.location(ws, loc_name)
        if ep.get("interior"):            # interior reel: room-local spots, no terrain/roof clearance
            loc = dict(base["interiors"][ep["interior"]], zones={})
        else:
            hf = MP.terrain_height_fn(base)
            pw = mercer_plan_anchors({"world_state": ws, "episode": ep})
            loc = dict(base)
            loc["anchors"] = {k: tuple(v) for k, v in pw["anchors"].items()}
            loc["_anchor_source"] = "worlds.mercer_plan_anchors"
    else:
        loc = plan_location(wid, ep, workdir)
    extra = ep.get("anchors") if isinstance(ep.get("anchors"), dict) else None
    cam_missing, lab_missing = check_targets(ep, loc)
    if cam_missing:
        raise ValueError("world %r (anchors from %s) does not define these camera targets / stops: %s"
                         % (wid, loc.get("_anchor_source", "world_state"), ", ".join(cam_missing)))
    lab_missing = [m for m in lab_missing if m.split(":", 1)[1] not in BUILD_TIME_ANCHORS]
    return ep, loc, hf, extra, {"world": wid, "notes": notes, "label_missing": lab_missing,
                                "anchor_source": loc.get("_anchor_source", "world_state")}

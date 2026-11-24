#!/usr/bin/env python3
"""Blender-free smoke test of page3/blender/hometown_usa.py (it cannot run in Blender tonight).

  PYTHONDONTWRITEBYTECODE=1 python3 page3/tools/smoke_hometown_mock.py [WORKDIR ...]

1. Static: every `B.x` / `S.x` / `L.x` / `P.x` the module uses exists at top level of mh_blender.py /
   scene_lib_v2.py / scene_lib.py / hometown_usa_plan.py, and every call's positional/keyword arguments fit that
   function's real signature (checked with inspect on stubs generated from the real source).
2. Dynamic: bpy / bmesh / mathutils are MagicMocks; mh_blender, scene_lib_v2 and scene_lib are replaced by stubs
   with the REAL signatures (generated from their source with ast), so a wrong argument raises TypeError. Then
   build(ctx, state) runs with every zone on, for a real plan.json from page3/_plan_test/, followed by
   apply_events over the whole timeline. A part that raises is a FAIL (build() would only print it).
This catches typos, wrong helper signatures and logic errors in my own code. It cannot catch bpy API mistakes
(node socket names, operator arguments) - those need the first Blender still (BUILD-LOG Session 2).
"""
from __future__ import annotations

import ast
import io
import json
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

PAGE3 = Path(__file__).resolve().parent.parent
ROOT = PAGE3.parent
SRC = {"B": ROOT / "page2" / "blender" / "mh_blender.py", "S": ROOT / "pipeline" / "blender" / "scene_lib_v2.py",
       "L": ROOT / "pipeline" / "blender" / "scene_lib.py", "P": PAGE3 / "blender" / "hometown_usa_plan.py"}
MOD = PAGE3 / "blender" / "hometown_usa.py"


def _ret(loc=None):
    m = mock.MagicMock()
    m.location = list(loc) if loc is not None else [0.0, 0.0, 0.0]
    return m


def stub_module(name, path, real=()):
    """Module with one stub per top-level def (same signature, defaults kept as None), constants as MagicMocks."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mod = types.ModuleType(name)
    top = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            args = node.args
            a2 = ast.arguments(posonlyargs=getattr(args, "posonlyargs", []), args=args.args, vararg=args.vararg,
                               kwonlyargs=args.kwonlyargs,
                               kw_defaults=[ast.Constant(None) if d is not None else None for d in args.kw_defaults],
                               kwarg=args.kwarg, defaults=[ast.Constant(None) for _ in args.defaults])
            loc_arg = "loc" if any(a.arg == "loc" for a in args.args) else None
            body = "return _ret(%s)" % (loc_arg or "None")
            fn = ast.FunctionDef(name=node.name, args=a2, body=ast.parse(body).body, decorator_list=[],
                                 returns=None, type_comment=None)
            m = ast.Module(body=[fn], type_ignores=[])
            ast.fix_missing_locations(m)
            ns = {"_ret": _ret}
            exec(compile(m, str(path), "exec"), ns)
            top[node.name] = ns[node.name]
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top[t.id] = mock.MagicMock()
                elif isinstance(t, ast.Tuple):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            top[e.id] = mock.MagicMock()
        elif isinstance(node, ast.ClassDef):
            top[node.name] = mock.MagicMock()
    for k, v in top.items():
        setattr(mod, k, v)
    for k, v in real:
        setattr(mod, k, v)
    return mod, set(top)


def hexc(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0], lin[1], lin[2], a)


def static_check(names):
    """Attribute references X.attr in hometown_usa.py for X in B/S/L/P that the real module does not define."""
    tree = ast.parse(MOD.read_text(encoding="utf-8"))
    missing = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in names:
            if node.attr not in names[node.value.id]:
                missing.add("%s.%s" % (node.value.id, node.attr))
    return sorted(missing)


def install_mocks():
    for n in ("bpy", "bmesh", "mathutils"):
        sys.modules[n] = mock.MagicMock(name=n)
    L, nl = stub_module("scene_lib", SRC["L"], real=[("hexc", hexc)])
    S, ns = stub_module("scene_lib_v2", SRC["S"])
    S._new_mat = lambda name: tuple(mock.MagicMock() for _ in range(5))        # (m, nt, N, Lk, principled)
    S._noise_var = lambda N, Lk, vec, scale, amount, detail=4.0: (mock.MagicMock(), mock.MagicMock())
    B, nb = stub_module("mh_blender", SRC["B"], real=[("S", S), ("L", L), ("hexc", hexc), ("ANC_PREFIX", "ANC_"),
                                                       ("CAM_PREFIX", "CAM_")])
    cache = {}

    def _cached(name, fn):
        if name not in cache:
            cache[name] = fn()
        return cache[name]
    B._cached = _cached
    B.count_tris = lambda name: 0
    B.normalize_anchors = lambda ctx: {k: mock.MagicMock() for k in __import__("hometown_usa_plan").STOPS}
    sys.modules.update({"scene_lib": L, "scene_lib_v2": S, "mh_blender": B})
    sys.path.insert(0, str(PAGE3 / "blender"))
    import hometown_usa_plan as P
    return {"B": nb | {"S", "L", "hexc"}, "S": ns, "L": nl, "P": set(dir(P))}


def run_one(W, plan, ep):
    state = {"world_id": "hometown_usa", "episode": ep, "plan": None, "workdir": None, "parts": None,   # all zones
             "focus": [], "frame_range": (1, plan["frames"]), "world_state": None}
    ctx = mock.MagicMock()
    err, out = io.StringIO(), io.StringIO()
    with redirect_stderr(err), redirect_stdout(out):
        anchors = W.build(ctx, state)
        W.apply_events(state, plan, 1, plan["frames"])
    w = state["world"]
    fails = [ln for ln in out.getvalue().splitlines() if "FAILED" in ln]
    return {"zones": len(w.zones), "peel_groups": sorted(w.peels), "lids": sorted(w.lids), "fails": fails,
            "tracebacks": err.getvalue().strip(), "anchors": len(anchors), "stats": w.stats}


def main(argv):
    names = install_mocks()
    miss = static_check(names)
    print("static: %s" % ("OK (all B./S./L./P. references exist)" if not miss else "MISSING " + ", ".join(miss)))
    import hometown_usa as W
    wds = [Path(a) for a in argv] or sorted((PAGE3 / "_plan_test").glob("*/oneshot/plan.json"))
    bad = bool(miss)
    for p in wds:
        p = p if p.name == "plan.json" else p / "oneshot" / "plan.json"
        wd = p.parent.parent
        ep_id = wd.name
        ep = json.loads((PAGE3 / "episodes" / ep_id / "episode.json").read_text(encoding="utf-8"))
        plan = json.loads(p.read_text(encoding="utf-8"))
        r = run_one(W, plan, ep)
        ok = not r["fails"] and not r["tracebacks"]
        bad |= not ok
        print("%s %-40s zones %2d  peel groups %2d  lids %d  anchors %d  keyed %s" % (
            "OK  " if ok else "FAIL", ep_id, r["zones"], len(r["peel_groups"]), len(r["lids"]), r["anchors"],
            r["stats"].get("keyed_peels_lids")))
        if not ok:
            print("\n".join("     " + ln for ln in r["fails"]))
            print("     " + r["tracebacks"].replace("\n", "\n     "))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

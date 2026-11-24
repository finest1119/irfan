"""Shared paths + world_state loading for the Self-Made Engineer (Page 2) Blender code. bpy-free.

Every path is built with pathlib relative to this file, so the same code runs on the Mac and on the Windows laptop.
Importable from Blender's Python (3.13) and from the repo venv (3.9 on the Mac, 3.11 on Windows).
"""
import json
import sys
from pathlib import Path

PAGE2 = Path(__file__).resolve().parent.parent          # .../irfan/page2
ROOT = PAGE2.parent                                      # .../irfan (repo root)
PIPE = ROOT / "pipeline"
PIPE_BLENDER = PIPE / "blender"
SCRIPTS = PAGE2 / "scripts"
WORLD_STATE = PAGE2 / "world_state.json"
CHARACTER = PAGE2 / "character.json"
POLYHAVEN = ROOT / "assets" / "polyhaven"

FT = 0.3048


def add_import_paths(blender=False):
    """page2/blender + page2/scripts (gen_world_state.height) always; pipeline/blender (scene_lib*, read-only
    import) only inside Blender, because those modules import bpy."""
    paths = [PAGE2 / "blender", SCRIPTS]
    if blender:
        paths.append(PIPE_BLENDER)
    for p in paths:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def load_json(path):
    with open(str(path), encoding="utf-8") as fh:
        return json.load(fh)


def world_state(path=WORLD_STATE):
    return load_json(path)


def location(ws, name="mercer_hollow"):
    if name in ws.get("locations", {}):
        return ws["locations"][name]
    if name in ws.get("trips", {}):
        return ws["trips"][name]
    raise KeyError("location %r not in world_state (locations: %s)" % (name, ", ".join(ws.get("locations", {}))))


def placed_builds(ws, loc_name="mercer_hollow", interior=None):
    """Every build with status approved|scheduled|posted at this location/interior (PROPOSAL 2.2)."""
    ok = {"approved", "scheduled", "posted"}
    loc = location(ws, loc_name)
    out = []
    for b in list(loc.get("builds", [])) + list(ws.get("builds", [])):
        if b.get("status") not in ok:
            continue
        if b.get("location", loc_name) != loc_name or b.get("interior") != interior:
            continue
        out.append(b)
    return out


def terrain_height_fn(loc):
    """Analytic height(x, y) from page2/scripts/gen_world_state.py (the generator is import-safe: it only writes
    JSON when run as a script). Falls back to bilinear interpolation of terrain.height_grid."""
    try:
        add_import_paths()
        import gen_world_state as G   # noqa: E402
        return G.height
    except Exception as ex:  # pragma: no cover
        print("[mh] analytic terrain unavailable (%s); using the 10 m height grid" % ex)
    hg = loc["terrain"]["height_grid"]
    ox, oy = hg["origin"]
    st = float(hg["step_m"])
    z = hg["z"]
    ny, nx = len(z), len(z[0])

    def h(x, y):
        fx = min(max((x - ox) / st, 0.0), nx - 1.001)
        fy = min(max((y - oy) / st, 0.0), ny - 1.001)
        i, j = int(fx), int(fy)
        tx, ty = fx - i, fy - j
        a = z[j][i] * (1 - tx) + z[j][i + 1] * tx
        b = z[j + 1][i] * (1 - tx) + z[j + 1][i + 1] * tx
        return a * (1 - ty) + b * ty
    return h

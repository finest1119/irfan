"""Interiors as their own light scenes (first pass): garage, basement, kitchen, attic, living_room. Needs bpy.

Each room is built in a FRESH scene (never together with the exterior terrain/woods/street). Coordinates are room-
local (origin = floor centre, world axes), as in world_state interiors.<room>. Door/window openings get an emissive
backdrop card in the exterior's daylight colour (a whip through a window hides the scene boundary; BUILD-SPEC 1).
Lighting: one area light per ~10 m2 + a soft world fill (no HDRI, no terrain) -> well under 1 GB VRAM.
"""
import math

import bpy
import bmesh

import mh_blender as B
from mh_blender import S, L, hexc

ROOM_LOOK = {
    "garage": {"floor": "c4c0b8", "wall": "e3dfd6", "props": "garage"},
    "basement": {"floor": "a9a59c", "wall": "b8b3a8", "props": "basement"},
    "kitchen": {"floor": "b08a5f", "wall": "eee7d8", "props": "kitchen"},
    "attic": {"floor": "b9a27e", "wall": "e8a7b4", "props": "attic"},
    "living_room": {"floor": "9a6b45", "wall": "e6dfcf", "props": "living"},
}


def build_room(ctx, loc, room):
    spec = loc["interiors"][room]
    look = ROOM_LOOK.get(room, ROOM_LOOK["garage"])
    B.part_collection("interior_" + room)
    sx, sy, sz = spec["size"]
    floor = B.mat_ph("mh_int_floor_" + room, hexc(look["floor"]), "concrete_floor_02", 0.3, 0.7)
    wall = S.pbr("mh_int_wall_" + room, hexc(look["wall"]), 0.85, var=0.03)
    ceil = S.pbr("mh_int_ceiling", hexc("f2f0ea"), 0.9, var=0.02)
    bm = bmesh.new()
    S.bm_box(bm, (0, 0, -0.05), (sx, sy, 0.1), 0)
    S.bm_box(bm, (0, 0, sz + 0.05), (sx, sy, 0.1), 2)
    openings = [(spec["door"]["pos"], (1.0 if room != "garage" else 4.9, 2.1 if room != "garage" else 2.15))]
    openings += [(w["pos"], tuple(w["size"])) for w in spec.get("windows", [])]
    _walls(bm, sx, sy, sz, openings, 1)
    B.mesh_obj("mh_room_" + room, bm, [floor, wall, ceil])
    # backdrop cards behind every opening (exterior daylight colour, emissive, no lighting cost)
    card = B.mat_glow("mh_backdrop", hexc("cfe0ee"), 2.0)
    for (p, size) in openings:
        x, y = p[0], p[1]
        nx = 1 if abs(abs(x) - sx / 2) < 0.05 else 0
        ny = 1 if abs(abs(y) - sy / 2) < 0.05 else 0
        if not (nx or ny):
            continue                                   # floor hatch / stairs: no card
        cb = bmesh.new()
        if nx:
            S.bm_box(cb, (0, 0, 0), (0.02, size[0] * 3, max(2.5, size[1] * 3)), 0)
            loc_ = (math.copysign(sx / 2 + 1.5, x), y, max(1.2, p[2] if len(p) > 2 else 1.2))
        else:
            S.bm_box(cb, (0, 0, 0), (size[0] * 3, 0.02, max(2.5, size[1] * 3)), 0)
            loc_ = (x, math.copysign(sy / 2 + 1.5, y), max(1.2, p[2] if len(p) > 2 else 1.2))
        B.mesh_obj("mh_backdrop_%d" % len(bpy.data.objects), cb, [card], loc=loc_)
    _props(look["props"], sx, sy, sz)
    # lights: area lights on the ceiling grid + a dim world fill
    n = max(1, int(round(sx * sy / 10.0)))
    cols = max(1, int(round(math.sqrt(n * sx / sy))))
    rows = max(1, int(math.ceil(n / float(cols))))
    for i in range(cols):
        for j in range(rows):
            ld = bpy.data.lights.new("mh_room_light", "AREA")
            ld.energy = 180.0
            ld.size = 1.2
            ld.color = (1.0, 0.93, 0.82)
            lo = L.link(bpy.data.objects.new("mh_room_light", ld))
            lo.location = (-sx / 2 + sx * (i + 0.5) / cols, -sy / 2 + sy * (j + 0.5) / rows, sz - 0.05)
    w = bpy.data.worlds.new("MH_RoomWorld")
    ctx.scene.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.75, 0.8, 0.88, 1.0)
    bg.inputs["Strength"].default_value = 0.25
    ctx.scene.view_settings.exposure = 0.0
    for k, sp in spec.get("camera_spots", {}).items():
        B.anchor_empty(ctx, "spot_" + k, tuple(sp["look_at"]))
    return {"room": room, "size": (sx, sy, sz), "camera_spots": spec.get("camera_spots", {})}


def _walls(bm, sx, sy, sz, openings, mi):
    """Four walls (0.15 m) with rectangular holes for doors/windows (split into slabs around each hole)."""
    t = 0.15
    sides = [("y", -sy / 2, sx), ("y", sy / 2, sx), ("x", -sx / 2, sy), ("x", sx / 2, sy)]
    for ax, c, length in sides:
        holes = []
        for p, size in openings:
            on = abs(p[1] - c) < 0.05 if ax == "y" else abs(p[0] - c) < 0.05
            if on:
                u = p[0] if ax == "y" else p[1]
                z0 = p[2] - size[1] / 2 if len(p) > 2 and p[2] > 0.3 else 0.0
                holes.append((u - size[0] / 2, u + size[0] / 2, z0, z0 + size[1]))
        cuts = sorted(holes)
        u = -length / 2
        segs = []
        for (u0, u1, z0, z1) in cuts:
            segs.append((u, u0, 0.0, sz))
            segs.append((u0, u1, 0.0, z0))
            segs.append((u0, u1, z1, sz))
            u = u1
        segs.append((u, length / 2, 0.0, sz))
        for (a, b, z0, z1) in segs:
            if b - a < 1e-3 or z1 - z0 < 1e-3:
                continue
            if ax == "y":
                S.bm_box(bm, ((a + b) / 2, c, (z0 + z1) / 2), (b - a, t, z1 - z0), mi)
            else:
                S.bm_box(bm, (c, (a + b) / 2, (z0 + z1) / 2), (t, b - a, z1 - z0), mi)


def _props(kind, sx, sy, sz):
    """A few instanced/box props per room type so each set reads at a glance (first pass)."""
    m1 = S.pbr("mh_int_prop_a", hexc("8a6a48"), 0.7, var=0.06)
    m2 = S.pbr("mh_int_prop_b", hexc("6d7378"), 0.45, metal=0.5)
    m3 = S.pbr("mh_int_prop_c", hexc("e8eaec"), 0.4)
    bm = bmesh.new()
    if kind == "garage":
        S.bm_box(bm, (sx / 2 - 0.4, 1.0, 0.45), (0.7, 2.4, 0.9), 0)           # workbench (east wall)
        S.bm_box(bm, (sx / 2 - 0.05, 1.0, 1.6), (0.03, 2.4, 1.1), 0)           # pegboard
        S.bm_box(bm, (-1.5, sy / 2 - 0.35, 1.0), (2.0, 0.6, 2.0), 1)           # shelves
        S.bm_box(bm, (1.5, -sy / 2 + 0.45, 0.45), (1.4, 0.7, 0.9), 2)          # chest freezer
    elif kind == "basement":
        S.bm_box(bm, (-sx / 2 + 0.6, -2.0, 0.8), (0.9, 0.9, 1.6), 2)           # furnace
        B.bm_cyl(bm, (-sx / 2 + 0.6, 0.0, 0), (-sx / 2 + 0.6, 0.0, 1.5), 0.3, 0.3, 14, 2)   # water heater
        S.bm_box(bm, (-sx / 2 + 0.1, 2.0, 1.4), (0.08, 0.6, 0.8), 1)           # electric panel
        for k in range(8):                                                     # exposed joists
            S.bm_box(bm, (-sx / 2 + (k + 0.5) * sx / 8, 0, sz - 0.12), (0.05, sy, 0.24), 0)
    elif kind == "kitchen":
        S.bm_box(bm, (0, sy / 2 - 0.35, 0.45), (3.4, 0.6, 0.9), 2)
        S.bm_box(bm, (0, sy / 2 - 0.35, 0.92), (3.45, 0.64, 0.05), 0)
        S.bm_box(bm, (sx / 2 - 0.45, -1.2, 0.9), (0.8, 0.7, 1.8), 2)           # fridge
        S.bm_box(bm, (0, -0.4, 0.45), (1.6, 0.9, 0.9), 2)                      # island
    elif kind == "attic":
        for k in range(10):                                                    # rafters
            y = -sy / 2 + (k + 0.5) * sy / 10
            for sgn in (-1, 1):
                B.bm_cyl(bm, (sgn * sx / 2, y, 0.3), (0, y, sz), 0.05, 0.05, 4, 0)
        for k in range(6):
            S.bm_box(bm, (-2 + k * 0.7, -3 + (k % 3), 0.25), (0.5, 0.4, 0.5), 0)
    else:
        S.bm_box(bm, (sx / 2 - 0.6, 0, 0.4), (0.9, 2.2, 0.8), 0)               # sofa
        S.bm_box(bm, (-sx / 2 + 0.4, 0.5, 0.35), (0.4, 1.6, 0.7), 1)           # TV console
        S.bm_box(bm, (0, -sy / 2 + 0.3, 1.0), (1.6, 0.5, 2.0), 0)              # fireplace
    B.mesh_obj("mh_room_props", bm, [m1, m2, m3])

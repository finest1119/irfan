"""Generate page2/world_state.json (Mercer Hollow + interiors + trip-location schema).

Run: .venv/bin/python page2/scripts/gen_world_state.py
Edit the LAYOUT constants / terrain profile here and re-run; never hand-edit the height grid.
Coordinates: Blender metres, Z up, origin = house front-door threshold (ground level),
+Y = north (upstream), +X = east (toward the ridge). Yaw = degrees CCW from +X that the object's FRONT faces.
"""
import functools
import json
import math
import os

FT = 0.3048
OUT = os.path.join(os.path.dirname(__file__), "..", "world_state.json")

# ---------------- terrain (analytic; the grid below is sampled from this) ----------------
# Slope fix (24 Nov 2026 Decisions 3+4, done by the world builder): meadow <= ~18 deg (was 22-37 deg), ridge crest
# 70 ft above the house floor, and a flat SHOULDER/BENCH 65 ft above the ram pump (waterfall bottom) that holds the
# ridge pad (Build #1 turbine, Build #3 tank). The ridge moved east, so the lot's east line moved from x=104 to x=126.
# `height()` is imported by page2/blender/world_mercer.py (bpy-free; this module only writes JSON when run as a script).
RIDGE_Z = round(70 * FT, 2)          # 21.34 m crest (70 ft above the house floor)
CREEK_TOP = (70.0, 5.42)             # (y, bed z) top of the steep section = hydro intake
CREEK_BOTTOM = (9.0, -2.50)          # (y, bed z) bottom = hydro turbine; fall 7.92 m = 26 ft over 61 m = 200 ft
FALL_Y = (36.0, 35.0)                # small waterfall: bed drops 2.0 m (6.5 ft) here
FALL_TOP_Z, FALL_BOT_Z = 2.40, 0.40
POND = (48.0, -60.0, 9.0, -3.40)     # x, y, radius, water surface z
POOL = (None, 33.0, 3.0, 0.40 - 0.6)  # plunge pool: (x = creek centre), y, radius, bottom z (water surface = 0.70)
PAD_Z = round(FALL_BOT_Z + 65 * FT, 2)   # 20.21 m: bench/pad 65 ft above the ram pump at the waterfall bottom
MEADOW_DEG = 13.5                    # average grade of the creek -> bench climb (max ~18 deg incl. easing)
CREST_DEG = 12.0                     # bench -> crest
EASE = 0.12                          # fraction of each climb that eases in/out (max grade = avg / (1 - EASE))
BENCH_W = 20.0                       # flat shoulder width (m) along X
BASE_SMOOTH = 24                     # +-m along Y the meadow foot follows the creek bed (hides the waterfall step)
PAD_Y, PAD_HALF = 70.0, 7.0          # pad centre y, half-size (x is solved: middle of the bench at that y-range)
FAR_X = 210.0                        # terrain/grid extent east


def creek_x(y):
    return 46.0 + 2.0 * math.sin(y / 14.0)


def bed(y):
    yt, zt = CREEK_TOP
    yb, zb = CREEK_BOTTOM
    if y >= yt:
        return zt + (y - yt) * 0.05
    if y >= FALL_Y[0]:
        return FALL_TOP_Z + (y - FALL_Y[0]) * (zt - FALL_TOP_Z) / (yt - FALL_Y[0])
    if y >= FALL_Y[1]:
        return FALL_BOT_Z + (y - FALL_Y[1]) * (FALL_TOP_Z - FALL_BOT_Z)
    if y >= yb:
        return zb + (y - yb) * (FALL_BOT_Z - zb) / (FALL_Y[1] - yb)
    return zb + (y - yb) * (0.9 / 64.0)          # gentle run to the pond (-3.4 at y=-55)


@functools.lru_cache(maxsize=65536)
def bed_smooth(y):
    ks = range(-BASE_SMOOTH, BASE_SMOOTH + 1, 2)
    return sum(bed(y + k) for k in ks) / float(len(ks))


def ease(t, e=EASE):
    """0..1 with a linear middle and quadratic ends: max slope = 1 / (1 - e) times the average."""
    t = max(0.0, min(1.0, t))
    if t < e:
        return t * t / (2 * e * (1 - e))
    if t > 1 - e:
        return 1 - (1 - t) ** 2 / (2 * e * (1 - e))
    return (t - e / 2) / (1 - e)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def west_base(x, y):
    """Yard side: flat house pad; north of y=30 it rises gently, fading in over 30 m from the street (x=-18)."""
    return 0.0 if y <= 30 else (y - 30) * 0.06 * smoothstep((x + 18.0) / 30.0)


def crest(y):
    return RIDGE_Z if y >= 20 else RIDGE_Z - (20 - y) * 0.05


@functools.lru_cache(maxsize=65536)
def profile(y):
    """East-side cross-section at y: (creek x, meadow foot z, bench z, bench x0, bench x1, crest x)."""
    cx = creek_x(y)
    base = bed_smooth(y) + 0.6
    bz = crest(y) - (RIDGE_Z - PAD_Z)
    ra = max(1.0, (bz - base) / math.tan(math.radians(MEADOW_DEG)))
    s0 = cx + 1.5 + ra
    s1 = s0 + BENCH_W
    rc = max(1.0, (crest(y) - bz) / math.tan(math.radians(CREST_DEG)))
    return cx, base, bz, s0, s1, s1 + rc


def height(x, y):
    if x < -18:                                  # street side, flat
        return 0.0
    rq = math.hypot(x - creek_x(POOL[1]), y - POOL[1])
    if rq < POOL[2] + 2.0:                       # plunge pool under the waterfall (Build #3 ram-pump drive water)
        k = smoothstep((POOL[2] + 2.0 - rq) / 2.0)
        return min(_land(x, y), _land(x, y) * (1 - k) + POOL[3] * k)
    rp = math.hypot(x - POND[0], y - POND[1])
    if rp < POND[2] + 6.0:                       # pond = smooth bowl (bottom 1.2 m under the water surface)
        k = smoothstep((POND[2] + 6.0 - rp) / 8.0)
        return _land(x, y) * (1 - k) + (POND[3] - 1.2) * k
    return _land(x, y)


def _land(x, y):
    cx, base, bz, s0, s1, c = profile(y)
    d = x - cx
    b = bed(y)
    if abs(d) <= 1.5:
        return b
    nb = b + 0.6 + (base - (b + 0.6)) * smoothstep((abs(d) - 1.5) / 4.0)   # waterfall step fades out of the banks
    if d < 0:
        return nb + (west_base(x, y) - nb) * ease((-d - 1.5) / 12.0)
    if x <= s0:
        return nb + (bz - nb) * ease((d - 1.5) / (s0 - cx - 1.5))
    if x <= s1:
        return bz
    if x <= c:
        return bz + (crest(y) - bz) * ease((x - s1) / (c - s1))
    return crest(y) - 0.03 * (x - c)             # gentle fall east into the woods


def _pad_x():
    ys = [PAD_Y + k for k in range(-int(PAD_HALF), int(PAD_HALF) + 1)]
    x0 = max(profile(y)[3] for y in ys)
    x1 = min(profile(y)[4] for y in ys)
    assert x1 - x0 >= 2 * PAD_HALF, "bench too narrow for the pad"
    return round((x0 + x1) / 2, 1)


PAD = (_pad_x(), PAD_Y, PAD_HALF)    # ridge pad centre x, y, half-size (flat, z = PAD_Z)


def slope_stats(step=2):
    """(max deg, p95 deg) over the whole terrain except the creek channel and the pond bowl (generator self-check)."""
    out = []
    for y in range(-100, 111, step):
        for x in range(-18, int(FAR_X), step):
            if abs(x - creek_x(y)) < 6 or math.hypot(x - POND[0], y - POND[1]) < POND[2] + 7:
                continue   # creek channel + pond bowl are not "ridge slope"
            e = 0.25
            gx = (height(x + e, y) - height(x - e, y)) / (2 * e)
            gy = (height(x, y + e) - height(x, y - e)) / (2 * e)
            out.append(math.degrees(math.atan(math.hypot(gx, gy))))
    out.sort()
    return round(out[-1], 1), round(out[int(0.95 * len(out))], 1)


def woods_polygon():
    """West edge follows the crest (trees on the ridge top + far slope, never on the meadow or the bench)."""
    ys = list(range(-100, 111, 10))
    west = [[round(profile(y)[5] - 4.0, 1), y] for y in ys]
    return west + [[FAR_X, 110], [FAR_X, -100]]


def r(v, n=2):
    return [round(a, n) for a in v] if isinstance(v, (list, tuple)) else round(v, n)


def zone(pos, size, yaw=0, desc="", **kw):
    z = {"pos": r(pos), "size": r(size), "yaw": yaw, "desc": desc}
    z.update(kw)
    return z


def g(x, y, dz=0.0):
    return [round(x, 2), round(y, 2), round(height(x, y) + dz, 2)]


# ---------------- Mercer Hollow exterior ----------------
zones = {
    # house block (front faces -X = west, toward the cul-de-sac)
    "house": zone([4.88, 0, 0], [9.75, 13.4, 7.6], 180,
                  "2-story, white lap siding #F4F2EC, gray asphalt shingle roof #6E7174 (gable, ridge N-S), "
                  "white trim, navy front door #0B1F3A, porch light. Footprint 32x44 ft. Front facade on x=0.",
                  front_door=[0, 0, 0], hero=True),
    "porch": zone([-1.22, 0, 0], [2.44, 8.0, 3.0], 180, "covered front porch, 8 ft deep, 2 white posts, 2 steps, porch light"),
    "garage": zone([4.25, -10.35, 0], [7.3, 7.3, 4.8], 180,
                   "attached 2-car garage (24x24 ft), white roll-up door on the west face x=0.6, NEMA outlet beside the door"),
    "driveway": zone([-10.2, -10.35, 0], [21.6, 7.3, 0.02], 0, "concrete driveway from the garage to the cul-de-sac bulb"),
    "red_pickup": zone([-7.5, -10.35, 0], [5.4, 2.0, 1.85], 0, "Bolts' old red pickup, nose toward the garage (see character.json vehicles)"),
    "front_lawn": zone([-9.5, 7.0, 0], [17.0, 27.0, 0.0], 0, "mown lawn, foundation shrubs along the porch"),
    "mailbox": zone([-20.6, -16.0, 0], [0.5, 0.3, 1.15], 180, "curbside mailbox on a wooden post, red flag up"),
    "propane_tank": zone([4.0, 9.2, 0], [2.3, 1.0, 1.1], 90, "white 250-gal horizontal propane tank, north side of the house (Build #7 unhooks it)"),
    "ac_condenser": zone([8.4, 7.6, 0], [0.9, 0.9, 0.9], 0, "A/C condenser unit on a pad, north-east corner"),
    "hose_reel": zone([10.3, -5.2, 0], [0.6, 0.5, 0.8], 0, "green garden hose on a wall reel at the back corner"),
    "back_yard": zone([22.0, 4.0, 0], [24.0, 36.0, 0], 0,
                      "fenced back yard x 10..34, y -14..22 (fits the 200 ft zig-zag trench of Build #6: e.g. 3 x 20 m runs)",
                      fence=[[5.0, 6.7], [5.0, 22.0], [34.0, 22.0], [34.0, -14.0], [7.9, -14.0]],
                      fence_kind="wooden privacy fence, 6 ft (1.83 m), cedar #A47551, posts every 8 ft (instanced)"),
    "deck": zone([11.6, -1.0, 0.6], [3.7, 8.0, 0.6], 0, "wood deck off the back door, grill at its south end"),
    "grill": zone([12.6, -4.2, 0.6], [0.7, 0.6, 1.1], 0, "black kettle-style grill (no brand) — Build #7 burner target"),
    "oak_tree": zone([27.0, 16.0, 0], [14.0, 14.0, 15.0], 0, "big oak (hero tree, unique mesh) with a tire swing on a low branch",
                     tire_swing=[25.0, 14.5, 0.6]),
    "picnic_table": zone([21.0, 3.0, 0], [1.8, 1.5, 0.75], 90, "weathered wood picnic table"),
    "garden": zone([16.0, -44.0, 0], [11.0, 10.0, 0.4], 0, "raised-bed vegetable garden: 6 cedar beds 4x10 ft, tomatoes/corn/squash"),
    "workshop": zone([28.0, -30.0, 0], [12.2, 9.1, 6.0], 180,
                     "detached workshop/barn 40x30 ft, red-brown board-and-batten #8C3B2E, gray metal roof, "
                     "roll-up door on the west face (x=21.9), workbench + pegboard inside, NEMA outlets",
                     door=[21.9, -30.0, 0]),
    "battery_shed": zone([28.0, -38.4, 0], [6.0, 3.7, 2.6], 270, "lean-to battery shed on the workshop's south wall (Build #1 battery bank)"),
    "gravel_path": zone([14.9, -22.0, 0], [3.0, 22.0, 0.02], 0, "gravel path from the garage corner to the workshop door", polyline=[[7.9, -14.0], [14.0, -22.0], [21.9, -30.0]]),
    "goose_house": zone(g(38.0, 10.0), [1.5, 1.2, 1.3], 180, "Torque's small white A-frame goose house + 3 m wire run, outside the fence on the creek bank",
                        ),
    "creek": zone([creek_x(10), 10.0, 0], [3.0, 200.0, 0], 0,
                  "creek flows N->S, bed 3 m wide, water ~0.3 m deep; centreline = polyline below",
                  polyline=[g(creek_x(y), y) for y in range(110, -101, -10)]),
    "creek_top": zone(g(creek_x(70), 70), [6, 6, 2], 0, "top of the 26 ft fall — Build #2 screened intake site"),
    "waterfall": zone(g(creek_x(35.5), 35.5), [4, 2, 2.0], 0, "small waterfall, 2.0 m (6.5 ft) drop + pool below (pool radius 3 m) — Build #3 ram-pump drive-fall site"),
    "creek_bottom": zone(g(creek_x(9), 9), [6, 6, 2], 0, "bottom of the 26 ft fall — Build #2 turbine site"),
    "pond": zone([POND[0], POND[1], POND[3]], [2 * POND[2], 2 * POND[2], 1.2], 0, "small pond downstream (south), reeds, water surface z -3.4"),
    "meadow": zone([80.0, 10.0, 0], [60.0, 170.0, 0], 0,
                   "grass meadow climbing from the creek to the ridge shoulder (avg ~13.5-16 deg, max ~18 deg), "
                   "then a flat 20 m shoulder/bench (pad) and a short rise to the wooded crest",
                   z_range=[-2.5, RIDGE_Z],
                   split_rail_fence=[g(62, -40), g(64, 0), g(63, 40), g(60, 80)]),
    "ridge_pad": zone([PAD[0], PAD[1], PAD_Z], [2 * PAD[2], 2 * PAD[2], 0], 0,
                      "flat pad on the ridge shoulder, 65 ft above the ram pump, crest 1.1 m higher just east — "
                      "Build #1 turbine, Build #3 tank"),
    "woods": zone([165.0, 5.0, 0], [90.0, 210.0, 0], 0,
                  "instanced woods: oak 40 % / maple 35 % / pine 25 %, ~1 tree per 40 m^2, clearing r=14 m around ridge_pad; "
                  "region 1 = the crest and the far slope (west edge follows the crest), region 2 = a north strip y 86..110",
                  regions=[woods_polygon(), [[0, 86], [FAR_X, 86], [FAR_X, 110], [0, 110]]]),
    "creek_crossing": zone(g(creek_x(-2), -2, 0.8), [4.0, 1.6, 0.4], 0,
                           "PROPOSED (not in the proposal): plank footbridge so Bolts can walk from the yard to the ridge", proposed=True),
}

street = {
    "cul_de_sac": {"centre": [-32.0, 0.0, -0.1], "radius": 15.0, "desc": "asphalt bulb #3B3D40, concrete curb, our driveway meets it at the east side"},
    "street": {"from": [-32.0, 0.0, -0.1], "to": [-220.0, 0.0, -0.1], "width": 8.5,
               "sidewalk": {"width": 1.5, "grass_strip": 1.2, "both_sides": True}, "desc": "residential street running west from the bulb"},
    "utility_poles": {"instanced": True, "height": 10.7, "positions": [[-17.0, 12.0, 0]] + [[x, 8.0, 0] for x in (-45, -83, -121, -159, -197)],
                      "desc": "wooden poles, 3 wires, service drop to our house north-west corner"},
    "neighbor_houses": [
        {"id": "nb_north", "pos": [-6.0, 38.0, 0], "yaw": 225, "siding": "#AFC4D6", "model": "nbr_A",
         "desc": "pale-blue 2-story; its side yard runs along OUR north fence (y=22..24) -> the peeking-neighbor gag"},
        {"id": "nb_south", "pos": [-14.0, -40.0, 0], "yaw": 135, "siding": "#D8CBB0", "model": "nbr_B", "desc": "beige ranch"},
        {"id": "nb_west_n", "pos": [-70.0, 22.0, 0], "yaw": 270, "siding": "#9AA79A", "model": "nbr_A", "desc": "sage 2-story"},
        {"id": "nb_west_s", "pos": [-70.0, -22.0, 0], "yaw": 90, "siding": "#B9B9B4", "model": "nbr_B", "desc": "gray ranch"},
    ],
    "neighbor_fence_line": [[-12.0, 23.0], [34.0, 23.0]],
}

far = {
    "hills": {"kind": "ring of 2D cards / low-poly with baked texture", "radius": 650, "height_range": [40, 120]},
    "water_tower": {"pos": [-420.0, -260.0, 0], "height": 38.0, "color": "#D9DCDF", "desc": "town water tower, blank tank (no lettering)"},
    "town": {"pos": [-500.0, -150.0, 0], "kind": "2D card"},
}

camera_spots = {
    "street_wide": {"pos": [-62.0, -10.0, 6.0], "look_at": [0.0, 2.0, 3.0], "lens_mm": 28,
                    "desc": "from down the street: porch, pickup, mailbox, nb_north + nb_south in frame"},
    "porch": {"pos": [-6.5, -3.5, 1.7], "look_at": [0.0, 0.0, 1.5], "lens_mm": 35},
    "back_yard": {"pos": [13.0, -11.0, 2.4], "look_at": [27.0, 14.0, 1.0], "lens_mm": 28},
    "workshop_door": {"pos": [13.0, -27.0, 1.9], "look_at": [21.9, -30.0, 1.6], "lens_mm": 32},
    "creek_top": {"pos": g(creek_x(76) - 7, 76, 2.5), "look_at": g(creek_x(66), 66, 0.5), "lens_mm": 28},
    "creek_bottom": {"pos": g(creek_x(4) - 6, 4, 1.8), "look_at": g(creek_x(30), 30, 1.0), "lens_mm": 28,
                     "desc": "looking upstream at the fall and the waterfall"},
    "ridge_pad": {"pos": g(PAD[0] - 12, PAD[1] - 14, 2.5), "look_at": [PAD[0], PAD[1], PAD_Z + 3], "lens_mm": 24},
    "aerial_overview": {"pos": [-70.0, -125.0, 95.0], "look_at": [35.0, 5.0, 0.0], "lens_mm": 24,
                        "desc": "sees street, house, yard, workshop, creek, pond and ridge pad"},
}

# ---------------- interiors (each = its own light Blender scene) ----------------
# local frame: origin = room floor centre, same axes as the world; world_anchor = where that origin sits in Mercer Hollow


def room(anchor, size, door, windows, spots, desc, **kw):
    d = {"world_anchor": r(anchor), "size": r(size), "door": door, "windows": windows,
         "camera_spots": spots, "desc": desc}
    d.update(kw)
    return d


interiors = {
    "garage": room([4.25, -10.35, 0], [7.3, 7.3, 2.75],
                   {"pos": [-3.65, 0, 0], "kind": "2-car roll-up door 16x7 ft, west wall"},
                   [{"pos": [0, -3.65, 1.4], "size": [1.0, 0.9]}],
                   {"door_inside": {"pos": [-2.8, -2.6, 1.6], "look_at": [2.5, 1.5, 1.0]},
                    "workbench": {"pos": [0.5, 0.5, 1.7], "look_at": [3.2, 2.5, 0.95]}},
                   "concrete floor, pegboard + workbench on the east wall, shelves, chest freezer, NEMA outlets; pickup may be parked outside",
                   interior_door_to="house (mudroom door, north wall)"),
    "basement": room([4.88, 0, -2.6], [9.75, 13.4, 2.4],
                     {"pos": [3.0, 5.5, 0], "kind": "stairs up to the kitchen, north-east corner"},
                     [{"pos": [-4.875, -4, 2.0], "size": [0.8, 0.4], "kind": "egress/hopper window to the front lawn"}],
                     {"stairs": {"pos": [2.5, 4.5, 1.8], "look_at": [-1.5, -2.5, 0.8]},
                      "utility_corner": {"pos": [-2.0, 2.0, 1.6], "look_at": [3.5, -5.0, 1.0]}},
                     "unfinished: poured-concrete walls, exposed joists, furnace, water heater, electric panel (Build #1 tie-in), sump pit"),
    "kitchen": room([7.0, 3.6, 0], [5.0, 4.5, 2.7],
                    {"pos": [2.5, 0, 0], "kind": "back door to the deck, east wall"},
                    [{"pos": [0, 2.25, 1.3], "size": [1.2, 1.0], "kind": "over the sink, faces north"}],
                    {"doorway": {"pos": [-2.0, -1.6, 1.7], "look_at": [1.5, 1.5, 1.0]},
                     "counter": {"pos": [1.2, -1.5, 1.6], "look_at": [-1.0, 2.0, 0.95]}},
                    "classic US kitchen: white shaker cabinets, butcher-block counter, gas range (propane), fridge, island",
                    interior_door_to="living_room"),
    "attic": room([4.88, 0, 5.4], [9.75, 13.4, 2.2],
                  {"pos": [0, -4.0, 0], "kind": "pull-down ladder hatch in the floor"},
                  [{"pos": [0, 6.7, 1.0], "size": [0.8, 0.6], "kind": "gable vent window, north end"},
                   {"pos": [0, -6.7, 1.0], "size": [0.8, 0.6], "kind": "gable vent window, south end"}],
                  {"hatch": {"pos": [0.8, -3.0, 1.4], "look_at": [0, 4.0, 0.8]},
                   "gable": {"pos": [0, 5.5, 1.5], "look_at": [0, -4.0, 0.6]}},
                  "unfinished gable attic: sloped rafters (ridge 2.2 m above the joists, 0.3 m at the eaves), pink insulation batts, plywood walkway, boxes",
                  roof_shape="gable, ridge along Y"),
    "living_room": room([3.0, -3.0, 0], [5.6, 6.0, 2.7],
                        {"pos": [-2.8, 2.6, 0], "kind": "front door/foyer, west wall"},
                        [{"pos": [-2.8, -1.0, 1.3], "size": [1.6, 1.4], "kind": "front window onto the porch"}],
                        {"sofa_view": {"pos": [2.2, -2.4, 1.5], "look_at": [-2.0, 1.5, 1.0]},
                         "window": {"pos": [-1.8, 1.8, 1.6], "look_at": [-2.8, -1.0, 1.4]}},
                        "sofa, recliner, TV on a console, wood floor, brick fireplace on the south wall, family photos (no faces needed)"),
}

build_schema = {
    "id": "wind_turbine",
    "build_no": 1,
    "title": "Storm knocked out the power. So he built a wind turbine taller than his house",
    "location": "mercer_hollow",
    "interior": None,
    "zone": "ridge_pad",
    "pos": [PAD[0], PAD[1], PAD_Z],
    "rot": 0,
    "status": "approved | scheduled | posted",
    "idle_anim": "rotor_spin",
    "lod": {"hero": "full", "mid": "lod1 (>60 m from camera)", "far": "lod2 (>150 m)"},
    "depends_on": [],
    "callback": "the windmill we built in Build #1",
    "posted_date": "YYYY-MM-DD",
    "_notes": "loader places every build with status approved|scheduled|posted; never delete a build (retired = visible old attempt). "
              "location = key of locations{}; interior = null for exterior or a key of that location's interiors{}.",
}

trip_schema = {
    "id": "example_trip",
    "name": "Display name (US-English, generic, no real brand)",
    "region": "e.g. lake_cabin | hometown | remote_work",
    "season": "late_summer | autumn | winter | spring",
    "origin_note": "Blender metres, Z up, origin at the main arrival point",
    "zones": {"<zone_id>": {"pos": [0, 0, 0], "size": [1, 1, 1], "yaw": 0, "desc": ""}},
    "camera_spots": {"<spot_id>": {"pos": [0, 0, 1.7], "look_at": [5, 0, 1.0], "lens_mm": 28}},
    "builds": [],
}

LOT_EAST = int(math.ceil((PAD[0] + PAD_HALF + 2) / 2.0) * 2)
LOT_OUTLINE = [[-18, -20], [-18, 23], [34, 23], [34, 83.5], [LOT_EAST, 83.5], [LOT_EAST, -75], [10, -75], [10, -20]]


def _poly_area(pts):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2.0


LOT_ACRES = round(_poly_area(LOT_OUTLINE) / 4046.86, 2)
LOT_FT_X = int(round((LOT_EAST + 18) / FT))
NX = int((FAR_X + 60) // 10) + 1


def build_world():
    SLOPE = slope_stats()
    world = {
        "world": "mercer_hollow",
        "version": 2,
        "season": "late_summer",
        "units": "Blender metres; Z up; +Y north (upstream); +X east (ridge); yaw = deg CCW from +X that the FRONT faces",
        "origin": "house front-door threshold, ground level",
        "generated_by": "page2/scripts/gen_world_state.py (edit there, re-run; builds[] is hand/loader maintained)",
        "locations": {
            "mercer_hollow": {
                "name": "Mercer Hollow",
                "kind": "home",
                "lot": {"size_ft": [LOT_FT_X, 520], "size_m": [round(LOT_EAST + 18, 1), 158.5], "acres": LOT_ACRES,
                        "note": "pie-shaped cul-de-sac lot: narrow street frontage (x=-18, y -20..23), widens behind the house to y -75..83, "
                                "east line x=%d (moved from 104 in the slope fix so the ridge pad stays on the lot)" % LOT_EAST,
                        "outline": LOT_OUTLINE},
                "terrain": {
                    "ground_z_house_pad": 0.0,
                    "ridge_crest_z": RIDGE_Z, "ridge_crest_x_at_pad": round(profile(PAD_Y)[5], 1),
                    "ridge_pad_z": PAD_Z, "pump_to_pad_ft": round((PAD_Z - FALL_BOT_Z) / FT, 1),
                    "profile": {"meadow_deg": MEADOW_DEG, "crest_deg": CREST_DEG, "ease": EASE, "bench_w": BENCH_W,
                                "note": "analytic: page2/scripts/gen_world_state.py height(x, y) (world_mercer imports it)"},
                    "creek": {"fall_m": round(CREEK_TOP[1] - CREEK_BOTTOM[1], 2), "fall_ft": 26, "run_m": 61, "run_ft": 200,
                              "top": CREEK_TOP, "bottom": CREEK_BOTTOM, "waterfall_y": FALL_Y, "waterfall_drop_m": 2.0,
                              "centreline": "x = 46 + 2 sin(y/14)"},
                    "meadow_grade_deg": {"avg": [MEADOW_DEG, 16], "max": SLOPE[0], "p95": SLOPE[1]},
                    "height_grid": {"origin": [-60, -100], "step_m": 10, "nx": NX, "ny": 22,
                                    "note": "rows = y ascending, cols = x ascending; bilinear-interpolate, then sculpt creek channel/waterfall/pond detail",
                                    "z": [[round(height(-60 + 10 * i, -100 + 10 * j), 2) for i in range(NX)] for j in range(22)]},
                },
                "zones": zones,
                "street": street,
                "far": far,
                "camera_spots": camera_spots,
                "interiors": interiors,
                "builds": [],
            },
        },
        "trips": {},
        "_trip_location_schema": trip_schema,
        "_build_schema": build_schema,
        "cables_pipes": [],
        "_cables_pipes_schema": {"from": "wind_turbine", "to": "battery_shed", "kind": "buried_cable | pipe | hose", "path": [[0, 0, 0]]},
    }
    return world


def main():
    world = build_world()
    t = world["locations"]["mercer_hollow"]["terrain"]
    print("slope max %.1f deg, p95 %.1f deg; pad %s z %.2f (%.1f ft above the pump); crest z %.2f; lot east x=%d, %.2f acres"
          % (t["meadow_grade_deg"]["max"], t["meadow_grade_deg"]["p95"], PAD[:2], PAD_Z, t["pump_to_pad_ft"], RIDGE_Z,
             LOT_EAST, LOT_ACRES))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(world, f, indent=1)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()

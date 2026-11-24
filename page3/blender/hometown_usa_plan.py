"""Hometown USA (Page 3, Everyday Decoded): the bpy-free half of the one-shot world. Python 3.9+, stdlib only.

Registered by file convention with page2/blender/worlds.py (world id "hometown_usa"):
    plan_anchors(state) -> {"anchors": {stop: [x, y, z]}, "cams": {stop: {"pos": [x, y, z], "lens": mm}}, ...}
The Blender side (page3/blender/hometown_usa.py) imports THIS module, so plan time and render time use the same
numbers: anchors, camera spots, nested host frames (phone, card), zone boxes, slice/peel groups and the per-frame
world timeline (lids, peels, zone visibility, clip planes, rebase frames) computed from plan.json.

Coordinates: WORLDS-SPEC.md section 0 (metres, Z up, +Y north, +X east, origin = Main St x Elm Ave).
Changes against WORLDS-SPEC v1 are listed in WORLDS-SPEC "Session 2 coordinate notes".
"""
from __future__ import annotations

import math

WORLD_ID = "hometown_usa"
FPS = 30

# ------------------------------------------------------------------ small vector helpers (tuples)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _r(p, nd=4):
    return [round(float(c), nd) for c in p]


# ------------------------------------------------------------------ nested host frames (W2 lives inside these)
class Frame(object):
    """A rigid host frame: origin + rotation about X (deg), then about Z (deg). Local units are METRES.
    The Blender side builds the host's meshes in local coordinates under an empty with the same transform
    (rotation_euler = (rx, 0, rz), XYZ order), so world positions match to_world() exactly."""

    def __init__(self, name, origin, rx_deg=0.0, rz_deg=0.0):
        self.name, self.origin = name, tuple(float(c) for c in origin)
        self.rx, self.rz = float(rx_deg), float(rz_deg)

    def rot(self, v):
        ax, az = math.radians(self.rx), math.radians(self.rz)
        x, y, z = v
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
        return (x, y, z)

    def to_world(self, local):
        return _add(self.origin, self.rot(local))

    def mm(self, x, y, z):
        """World point of a local offset given in millimetres."""
        return self.to_world((x / 1000.0, y / 1000.0, z / 1000.0))


# Phone in the hand on the hero house's front walk: local x = width (east), y = long axis, z = screen normal.
# Tilted 60 deg about X: the long axis points up-north, the screen faces up-south (towards the person's face).
PHONE = Frame("phone", (201.45, 148.70, 1.32), rx_deg=60.0)
PHONE_SIZE_MM = (71.0, 147.0, 7.8)
# Card held flat 5 cm above the payment terminal (chip up). Card local x = 85.6 mm side, y = 54 mm side.
CARD = Frame("card", (-88.40, -54.56, 1.150))
CARD_SIZE_MM = (85.6, 54.0, 0.76)
# Payment terminal on its counter stand, tilted 20 deg towards the shopper (north).
TERMINAL = Frame("terminal", (-88.40, -54.60, 1.075), rx_deg=-20.0)
TERMINAL_SIZE_MM = (80.0, 170.0, 50.0)
# Gum pack lying on the bi-optic scanner glass, label up, bars running along Y.
GUM = Frame("gum", (-87.60, -54.80, 0.965))
GUM_SIZE_MM = (75.0, 50.0, 30.0)
# Hero house local origin H0 (WORLDS-SPEC 3): SW corner of the main volume.
H0 = (194.0, 152.0, 0.0)
HOUSE = {"x0": 194.0, "x1": 206.0, "y0": 152.0, "y1": 162.0, "basement": -2.0, "floor1": 0.6, "floor2": 3.5,
         "eaves": 6.4, "ridge": 9.0, "garage": (206.0, 212.0, 152.0, 159.0)}
MICROWAVE = {"x": 199.2, "y_front": 161.43, "y_back": 161.85, "z0": 1.85, "z1": 2.25, "w": 0.76}

# ------------------------------------------------------------------ the 37 stops
# anc  = ANC_<stop> (label/look point), cam = CAM_<stop> (default camera position), lens in mm (vertical sensor 24 mm),
# zone = the collection that must be built for it, w = world (W1/W2/W3, as make_episode.STOP_WORLD).
STOPS = {
    # ---------------------------------------------------------------- W1 Hometown USA
    "hand_phone": {"w": "W1", "anc": PHONE.mm(0, 0, 3.9), "cam": PHONE.to_world((0.06, -0.10, 0.60)), "lens": 35,
                   "zone": "Z_SUBURB"},
    "cell_tower": {"w": "W1", "anc": (262.0, 226.0, 37.5), "cam": (250.0, 205.0, 34.0), "lens": 35, "zone": "Z_TOWER"},
    "tower_base": {"w": "W1", "anc": (265.0, 223.0, 1.5), "cam": (259.5, 219.2, 1.9), "lens": 28, "zone": "Z_TOWER"},
    "street_slice_fiber": {"w": "W1", "anc": (226.0, 138.5, -0.9), "cam": (224.5, 133.0, 0.35), "lens": 24,
                           "zone": "Z_STREET_SLICE"},
    "data_center": {"w": "W1", "anc": (-420.0, 330.0, 12.0), "cam": (-330.0, 230.0, 45.0), "lens": 28,
                    "zone": "Z_INDUSTRIAL_DC"},
    "edge_server_room": {"w": "W1", "anc": (-395.0, 315.0, 2.2), "cam": (-406.0, 315.0, 1.7), "lens": 24,
                         "zone": "Z_DC_INT"},
    "substation": {"w": "W1", "anc": (430.0, -330.0, 6.0), "cam": (395.0, -390.0, 28.0), "lens": 28, "zone": "Z_POWER"},
    "power_lines": {"w": "W1", "anc": (620.0, -330.0, 28.0), "cam": (560.0, -318.0, 30.0), "lens": 35,
                    "zone": "Z_POWER"},
    "pole_transformer": {"w": "W1", "anc": (189.0, 149.0, 8.5), "cam": (192.5, 145.0, 3.5), "lens": 28,
                         "zone": "Z_SUBURB"},
    "water_tower": {"w": "W1", "anc": (-260.0, 430.0, 48.0), "cam": (-200.0, 370.0, 40.0), "lens": 35,
                    "zone": "Z_WATER"},
    "water_main_slice": {"w": "W1", "anc": (200.0, 141.0, -1.6), "cam": (201.5, 133.0, 0.30), "lens": 24,
                         "zone": "Z_STREET_SLICE"},
    "treatment_plant": {"w": "W1", "anc": (-655.0, -190.0, 4.0), "cam": (-560.0, -300.0, 60.0), "lens": 28,
                        "zone": "Z_WATER"},
    "intersection": {"w": "W1", "anc": (0.0, 0.0, 6.0), "cam": (-25.0, -45.0, 9.0), "lens": 28, "zone": "Z_DOWNTOWN"},
    "road_loop_slice": {"w": "W1", "anc": (2.0, -14.0, -0.08), "cam": (6.8, -15.5, 0.60), "lens": 24,
                        "zone": "Z_DOWNTOWN"},
    "signal_cabinet": {"w": "W1", "anc": (11.5, -11.3, 1.1), "cam": (12.0, -9.75, 1.40), "lens": 28,
                       "zone": "Z_DOWNTOWN"},
    "sky_satellites": {"w": "W1", "anc": (100.0, 300.0, 2300.0), "cam": (60.0, 180.0, 2240.0), "lens": 35,
                       "zone": "Z_SKY"},
    "strip_mall_checkout": {"w": "W1", "anc": (-88.4, -54.6, 1.10), "cam": (-88.0, -53.3, 1.45), "lens": 35,
                            "zone": "Z_STRIPMALL_INT"},
    "suburb_wide": {"w": "W1", "anc": (230.0, 230.0, 0.0), "cam": (480.0, -40.0, 120.0), "lens": 35,
                    "zone": "Z_SUBURB"},
    # ---------------------------------------------------------------- W2 macro kit (nested, real scale)
    "macro_phone_board": {"w": "W2", "anc": PHONE.mm(0, 20, -2), "cam": PHONE.mm(4, -10, 16), "lens": 35,
                          "zone": "Z_MACRO_PHONE", "host": "phone"},
    "macro_phone_antenna": {"w": "W2", "anc": PHONE.mm(30, 65, 0), "cam": PHONE.mm(20, 30, 12), "lens": 35,
                            "zone": "Z_MACRO_PHONE", "host": "phone"},
    "macro_card_chip": {"w": "W2", "anc": CARD.mm(-24, 4, 0.4), "cam": CARD.mm(-20, 39, 14.4), "lens": 50,
                        "zone": "Z_MACRO_CARD", "host": "card"},
    "macro_card_coil": {"w": "W2", "anc": CARD.mm(38, -22, 0.38), "cam": CARD.mm(8, -10, 10.4), "lens": 50,
                        "zone": "Z_MACRO_CARD", "host": "card"},
    "macro_terminal": {"w": "W2", "anc": TERMINAL.mm(0, 20, 18), "cam": TERMINAL.mm(55, 75, 80), "lens": 35,
                       "zone": "Z_MACRO_TERMINAL", "host": "terminal"},
    "macro_scanner": {"w": "W2", "anc": (-87.6, -54.8, 0.95), "cam": (-87.6, -54.45, 1.10), "lens": 35,
                      "zone": "Z_MACRO_SCANNER", "host": "scanner"},
    "macro_barcode": {"w": "W2", "anc": GUM.mm(0, 0, 15.2), "cam": GUM.mm(0, 18, 21.2), "lens": 50,
                      "zone": "Z_MACRO_SCANNER", "host": "gum"},
    # ---------------------------------------------------------------- W3 cut-away house
    "house_exterior": {"w": "W3", "anc": (200.0, 152.0, 3.0), "cam": (206.0, 118.0, 6.0), "lens": 35,
                       "zone": "Z_SUBURB"},
    "living_room_router": {"w": "W3", "anc": (200.0, 156.8, 1.45), "cam": (196.5, 153.5, 1.65), "lens": 35,
                           "zone": "Z_HOUSE_INT"},
    "living_room_tv": {"w": "W3", "anc": (197.2, 157.45, 1.9), "cam": (197.6, 153.4, 1.55), "lens": 28,
                       "zone": "Z_HOUSE_INT"},
    "kitchen_microwave": {"w": "W3", "anc": (199.2, 161.65, 2.05), "cam": (198.4, 158.6, 1.85), "lens": 35,
                          "zone": "Z_HOUSE_INT"},
    "macro_microwave_mesh": {"w": "W3", "anc": (199.2, 161.415, 2.05), "cam": (199.16, 161.388, 2.058), "lens": 50,
                             "zone": "Z_MACRO_MW", "host": "microwave"},
    "ac_indoor_coil": {"w": "W3", "anc": (196.0, 159.0, -0.6), "cam": (197.8, 156.6, -0.9), "lens": 28,
                       "zone": "Z_HOUSE_BASEMENT"},
    "ac_lines_wall": {"w": "W3", "anc": (194.0, 159.5, 0.4), "cam": (192.4, 157.6, 0.9), "lens": 28,
                      "zone": "Z_SUBURB"},
    "ac_condenser": {"w": "W3", "anc": (192.6, 159.5, 0.95), "cam": (190.4, 156.8, 2.6), "lens": 28,
                     "zone": "Z_SUBURB"},
    "thermostat": {"w": "W3", "anc": (200.55, 157.0, 2.1), "cam": (202.3, 156.6, 1.95), "lens": 35,
                   "zone": "Z_HOUSE_INT"},
    "faucet_kitchen": {"w": "W3", "anc": (197.0, 161.6, 1.75), "cam": (196.4, 159.9, 1.95), "lens": 35,
                       "zone": "Z_HOUSE_INT"},
    "wall_pipes": {"w": "W3", "anc": (197.0, 161.95, 1.0), "cam": (197.0, 165.4, 1.5), "lens": 28,
                   "zone": "Z_SUBURB"},
    "smart_meter": {"w": "W3", "anc": (194.0, 155.0, 1.5), "cam": (192.0, 154.4, 1.6), "lens": 35,
                    "zone": "Z_SUBURB"},
}
STOP_IDS = tuple(STOPS)
MACRO_DIST = 0.5            # subject distance below which a stop is "macro" (orbit holds, mm clip planes, rebase)

# ------------------------------------------------------------------ variant views (Session 3: holds <= 9 s)
# Each stop has two extra views on the same object/area: <stop>__detail (push to a close detail) and <stop>__alt
# (another angle or part). Spec per variant: (description, anchor offset, distance factor, yaw deg, cam dz, local).
#   anchor = stop anchor + offset (world metres; or host-local metres when local=True, for nested macro stops)
#   camera = new anchor + rotate_z(stop cam - stop anchor, yaw) * factor + (0, 0, cam dz)
VARIANT_SPEC = {
    "hand_phone": {"detail": ("app tiles on the screen", (0, 0, 0), 0.5, 0, 0, False),
                   "alt": ("hand, thumb and the phone's lower edge", (0.03, -0.03, -0.04), 0.9, -40, 0, False)},
    "cell_tower": {"detail": ("one sector: 3 antenna panels + radio boxes", (-2.0, -1.15, 0), 0.35, 0, 0, False),
                   "alt": ("monopole mid-shaft and coax trunk", (0, 0, -20.0), 0.8, 35, 0, False)},
    "tower_base": {"detail": ("open cabinet: racks and LEDs", (0, -0.35, -0.2), 0.35, 0, 0, False),
                   "alt": ("fiber handhole mini-slice", (-2.0, -3.0, -1.8), 0.6, -30, 1.6, False)},
    "street_slice_fiber": {"detail": ("sliced duct: fiber strands, glowing ends", (-4.0, -0.15, 0.05), 0.4, 0, 0, False),
                           "alt": ("handhole where the Birch St conduit enters", (6.0, 0, 0.4), 0.9, 0, 0, False)},
    "data_center": {"detail": ("rooftop chillers", (-20.0, 15.0, 1.0), 0.4, 0, 0, False),
                    "alt": ("generator yard + fence", (-15.0, -42.0, -10.5), 0.6, -40, 0, False)},
    "edge_server_room": {"detail": ("rack front LEDs", (3.0, -2.35, -1.0), 0.3, -60, 0, False),
                         "alt": ("overhead yellow fiber tray", (0, 0, 0.55), 0.5, 0, 0, False)},
    "substation": {"detail": ("transformer bushings + radiator fins", (-6.0, 0.8, 1.0), 0.3, 0, 0, False),
                   "alt": ("bus + lines leaving east", (35.0, 0, 6.6), 0.8, 40, 0, False)},
    "power_lines": {"detail": ("insulator string on a lattice tower", (130.0, -6.5, -4.6), 0.25, 0, 0, False),
                    "alt": ("lattice tower legs", (-120.0, 0, -23.0), 0.6, 50, 0, False)},
    "pole_transformer": {"detail": ("can transformer + fuse cutout", (0, -0.35, 0), 0.45, 0, 0, False),
                         "alt": ("service drop towards the house", (2.5, 3.0, -1.5), 1.0, -35, 0, False)},
    "water_tower": {"detail": ("balcony rail + ladder", (6.0, -6.0, -4.0), 0.4, 0, 0, False),
                    "alt": ("riser in the cut-away pedestal", (0, 0, -20.0), 0.7, 30, 0, False)},
    "water_main_slice": {"detail": ("saddle + corporation stop", (0, 0, 0.15), 0.4, 0, 0, False),
                         "alt": ("main, gas line and service line together", (-4.0, 1.6, 0.7), 0.8, 0, 0, False)},
    "treatment_plant": {"detail": ("clarifier bridge + water", (0, 0, 0.4), 0.35, 0, 0, False),
                        "alt": ("filter bed cut (sand/gravel)", (37.0, 10.0, -1.5), 0.6, -30, 0, False)},
    "intersection": {"detail": ("NB signal heads", (5.0, -9.5, -0.4), 0.35, 0, 0, False),
                     "alt": ("hero pickup at the stop line", (2.0, -14.0, -5.0), 0.6, 30, 0, False)},
    "road_loop_slice": {"detail": ("loop wire corner in the saw-cut", (-0.9, 0.9, 0.03), 0.4, 0, 0, False),
                        "alt": ("lead-in to the curb pull box", (6.35, 0, -0.1), 0.7, 40, 0, False)},
    "signal_cabinet": {"detail": ("detector cards + LEDs", (0, 0.15, 0), 0.4, 0, 0, False),
                       "alt": ("mast-arm pole + heads above the corner", (-2.0, 1.8, 4.5), 1.6, 0, -4.5, False)},
    "sky_satellites": {"detail": ("solar wing of the central satellite", (0, -9.0, 0), 0.3, 0, 0, False),
                       "alt": ("the outer satellites of the arc", (40.0, 220.0, 120.0), 1.0, 30, 0, False)},
    "strip_mall_checkout": {"detail": ("terminal screen + card", (0, 0, 0), 0.4, 0, 0, False),
                            "alt": ("scanner + conveyor", (0.8, -0.2, -0.15), 1.0, -35, 0, False)},
    "suburb_wide": {"detail": ("hero house on Maple St", (-30.0, -78.0, 5.0), 0.35, 0, 0, False),
                    "alt": ("the town from the east (other angle)", (0, 0, 0), 1.0, 40, 0, False)},
    "macro_phone_board": {"detail": ("processor die close-up", (0, 0, 0), 0.5, 0, 0, True),
                          "alt": ("battery pouch", (0, -0.055, 0.0005), 1.0, 0, 0, True)},
    "macro_phone_antenna": {"detail": ("mmWave patch array", (0, 0, 0), 0.5, 0, 0, True),
                            "alt": ("antenna gap in the metal frame", (0.0055, -0.013, 0), 1.0, 30, 0, True)},
    "macro_card_chip": {"detail": ("bond wires on the die", (0.0035, 0.0045, 0.0001), 0.45, 0, 0, True),
                        "alt": ("coil link into the chip", (0.012, -0.006, 0), 1.0, 40, 0, True)},
    "macro_card_coil": {"detail": ("copper turns in the laminate", (0, 0, 0), 0.45, 0, 0, True),
                        "alt": ("terminal field loops under the card", (-0.038, 0.022, -0.01), 1.6, 0, 0, True)},
    "macro_terminal": {"detail": ("secure element (glows teal)", (-0.02, -0.05, -0.012), 0.6, 0, 0, True),
                       "alt": ("keypad membrane", (0, -0.068, 0.007), 1.0, 30, 0, True)},
    "macro_scanner": {"detail": ("laser lines on the glass", (0, 0, 0.003), 0.4, 0, 0, False),
                      "alt": ("vertical window + mirror wheel", (0, -0.15, 0.08), 0.9, 30, 0, False)},
    "macro_barcode": {"detail": ("bars at the label edge", (0.012, 0, 0), 0.5, 0, 0, True),
                      "alt": ("red scan line over the wrapper", (-0.02, 0, 0), 1.2, 50, 0, True)},
    "house_exterior": {"detail": ("porch + front door", (1.0, -1.3, -1.5), 0.35, 0, 0, False),
                       "alt": ("garage + driveway pickup", (9.0, -3.0, -1.5), 0.8, 25, 0, False)},
    "living_room_router": {"detail": ("status LEDs", (-0.07, -0.076, -0.02), 0.25, 0, 0, False),
                           "alt": ("the two antennas", (0, 0.06, 0.15), 0.4, 35, 0, False)},
    "living_room_tv": {"detail": ("bezel corner with the IR sensor", (0.5, -0.04, -0.33), 0.3, 0, 0, False),
                       "alt": ("TV from the side, couch in front", (0, 0, 0), 0.8, 40, 0, False)},
    "kitchen_microwave": {"detail": ("door + handle", (0.29, -0.23, 0), 0.35, 0, 0, False),
                          "alt": ("magnetron under the peeled casing", (0.25, 0, 0), 0.6, 35, 0, False)},
    "macro_microwave_mesh": {"detail": ("the hole grid", (0, 0, 0), 0.5, 0, 0, False),
                             "alt": ("amber wave ribbon bouncing off the mesh", (0, 0.012, 0), 1.2, 30, 0, False)},
    "ac_indoor_coil": {"detail": ("A-coil fins + condensate droplets", (0, -0.36, 0), 0.4, 0, 0, False),
                       "alt": ("drain line + water heater", (0.9, -0.3, -1.0), 0.9, 35, 0, False)},
    "ac_lines_wall": {"detail": ("line set in the cut (foam + copper)", (0, 0, 0), 0.45, 0, 0, False),
                      "alt": ("line set running to the condenser", (-0.9, 0, -0.1), 1.0, -30, 0, False)},
    "ac_condenser": {"detail": ("top fan through the grille", (0, 0, 0), 0.4, 0, 0, False),
                     "alt": ("heat ribbons rising", (0, 0, 0.6), 1.0, 40, 0, False)},
    "thermostat": {"detail": ("glowing teal ring", (0, 0, 0), 0.35, 0, 0, False),
                   "alt": ("hall wall + stairs edge", (0, -0.8, -0.8), 1.3, -35, 0, False)},
    "faucet_kitchen": {"detail": ("the water stream", (0, -0.05, -0.12), 0.3, 0, 0, False),
                       "alt": ("sink + window", (0, 0.3, 0.45), 1.0, 30, 0, False)},
    "wall_pipes": {"detail": ("shutoff valves", (0, -0.16, 0.25), 0.35, 0, 0, False),
                   "alt": ("pipes running down to the basement", (0, 0, -0.8), 1.0, 25, 0, False)},
    "smart_meter": {"detail": ("glass dome", (-0.18, 0, 0.03), 0.35, 0, 0, False),
                    "alt": ("service mast + drop", (-0.05, 0, 4.0), 1.6, 20, 0, False)},
}
VARIANTS = ("detail", "alt")
_HOSTS = {"phone": PHONE, "card": CARD, "terminal": TERMINAL, "gum": GUM}


def _rot_z(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a), v[2])


def _variant(stop, kind):
    s = STOPS[stop]
    desc, off, k, yaw, dz, local = VARIANT_SPEC[stop][kind]
    if local:
        off = Frame("h", (0, 0, 0), _HOSTS[s["host"]].rx, _HOSTS[s["host"]].rz).rot(off)
    anc = _add(s["anc"], off)
    rel = _rot_z(_sub(s["cam"], s["anc"]), yaw)
    cam = _add(anc, (rel[0] * k, rel[1] * k, rel[2] * k + dz))
    return {"w": s["w"], "anc": anc, "cam": cam, "lens": s["lens"], "zone": s["zone"], "base": stop, "desc": desc}


VIEWS = dict((k, dict(v, base=k, desc="main view")) for k, v in STOPS.items())
for _s in STOPS:
    for _k in VARIANTS:
        VIEWS["%s__%s" % (_s, _k)] = _variant(_s, _k)


# Portal interiors (WORLDS-SPEC 1.1 P + R fallback): an ENLARGED (x20) copy of a set placed far below the world
# origin, reached only through a fill-frame portal. kitchen_microwave: the cooking cavity (0.50 x 0.35 x 0.28 m) as a
# 10 x 7 x 5.6 m metal room centred on MW_INSIDE. Views <stop>__inside / __inside_detail / __inside_alt.
MW_INSIDE = (0.0, 0.0, -300.0)
MW_INSIDE_SCALE = 20.0
PORTAL_INSIDE = {"kitchen_microwave": {
    "inside": ("enlarged cavity: turntable, bowl, metal walls", (0.0, 0.5, -1.8), (-2.5, -3.0, 0.8), 24),
    "inside_detail": ("magnetron + wave-guide opening", (4.2, 1.5, 1.5), (1.0, -1.5, 0.0), 28),
    "inside_alt": ("turntable + bowl at plate level", (0.0, 0.5, -2.0), (2.8, -2.6, -1.9), 24)}}
for _s, _vs in PORTAL_INSIDE.items():
    for _k, (_d, _a, _c, _l) in _vs.items():
        VIEWS["%s__%s" % (_s, _k)] = {"w": STOPS[_s]["w"], "anc": _add(MW_INSIDE, _a), "cam": _add(MW_INSIDE, _c),
                                     "lens": _l, "zone": "Z_MW_INSIDE", "base": _s, "desc": _d}


def base_stop(view):
    return view.split("__", 1)[0] if isinstance(view, str) else view


def subject_distance(view):
    s = VIEWS[view]
    return _len(_sub(s["cam"], s["anc"]))


def is_macro(view):
    return view in VIEWS and subject_distance(view) < MACRO_DIST


# ------------------------------------------------------------------ zones (collections) and culling
# boxes: (x0, x1, y0, y1, z0, z1); radius: the camera builds/shows the zone within this distance of a box
ZONES = {
    "Z_DOWNTOWN": {"boxes": [(-140, 140, -120, 120, -1, 40)], "radius": 500.0},
    "Z_STRIPMALL_INT": {"boxes": [(-130, -40, -70, -50, 0, 6)], "radius": 60.0},
    "Z_SUBURB": {"boxes": [(100, 540, 60, 430, -1, 60)], "radius": 550.0},
    "Z_HOUSE_INT": {"boxes": [(194, 206, 152, 162, 0.5, 9.0)], "radius": 25.0},
    "Z_HOUSE_BASEMENT": {"boxes": [(194, 206, 152, 162, -2.2, 0.6)], "radius": 25.0},
    "Z_STREET_SLICE": {"boxes": [(192, 236, 131, 144, -2.6, 0.1)], "radius": 150.0},
    "Z_TOWER": {"boxes": [(240, 285, 205, 250, 0, 45)], "radius": 500.0},
    "Z_INDUSTRIAL_DC": {"boxes": [(-480, -360, 290, 370, 0, 20)], "radius": 600.0},
    "Z_DC_INT": {"boxes": [(-410, -380, 305, 325, 0, 6)], "radius": 60.0},
    "Z_POWER": {"boxes": [(390, 1300, -370, -290, 0, 40)], "radius": 600.0},
    "Z_WATER": {"boxes": [(-275, -245, 415, 445, 0, 60), (-760, -560, -255, -145, -2, 20)], "radius": 600.0},
    "Z_SKY": {"boxes": [(-900, 1100, -700, 1300, 900, 2700)], "radius": 450.0},
    "Z_MACRO_PHONE": {"boxes": [], "host": PHONE, "half": (0.05, 0.09, 0.02), "radius": 2.0},
    "Z_MACRO_CARD": {"boxes": [], "host": CARD, "half": (0.05, 0.035, 0.01), "radius": 2.0},
    "Z_MACRO_TERMINAL": {"boxes": [], "host": TERMINAL, "half": (0.05, 0.1, 0.04), "radius": 2.0},
    "Z_MACRO_SCANNER": {"boxes": [(-87.85, -87.35, -55.0, -54.6, 0.7, 1.05)], "radius": 2.0},
    "Z_MACRO_MW": {"boxes": [(198.8, 199.6, 161.3, 161.9, 1.8, 2.3)], "radius": 2.0},
    "Z_MW_INSIDE": {"boxes": [(-5.6, 5.6, -4.1, 4.1, -303.4, -296.6)], "radius": 3.0},
    "Z_FAR_LOD": {"boxes": [], "radius": 1e9, "always": True},
}
for _z in ZONES.values():                 # host frames -> an axis-aligned box around the host (rotation ignored)
    if "host" in _z:
        o, h = _z["host"].origin, max(_z["half"])
        _z["boxes"] = [(o[0] - h, o[0] + h, o[1] - h, o[1] + h, o[2] - h, o[2] + h)]
# exterior districts that get a low-poly proxy in Z_FAR_LOD when they are not built in a job
DISTRICTS = ("Z_DOWNTOWN", "Z_SUBURB", "Z_TOWER", "Z_INDUSTRIAL_DC", "Z_POWER", "Z_WATER")
INTERIORS = ("Z_HOUSE_INT", "Z_HOUSE_BASEMENT", "Z_STRIPMALL_INT", "Z_DC_INT", "Z_MW_INSIDE")
ENCLOSED_RADIUS = 150.0     # camera inside a building / macro set: exterior districts only within this distance
# zones that need another zone around them (an interior is never built without its building)
ZONE_DEPS = {"Z_HOUSE_INT": ("Z_SUBURB",), "Z_HOUSE_BASEMENT": ("Z_SUBURB",), "Z_STREET_SLICE": ("Z_SUBURB",),
             "Z_STRIPMALL_INT": ("Z_DOWNTOWN",), "Z_DC_INT": ("Z_INDUSTRIAL_DC",),
             "Z_MACRO_PHONE": ("Z_SUBURB",), "Z_MACRO_MW": ("Z_HOUSE_INT", "Z_SUBURB"),
             "Z_MACRO_CARD": ("Z_STRIPMALL_INT", "Z_DOWNTOWN"), "Z_MACRO_TERMINAL": ("Z_STRIPMALL_INT", "Z_DOWNTOWN"),
             "Z_MACRO_SCANNER": ("Z_STRIPMALL_INT", "Z_DOWNTOWN")}


def box_dist(p, b):
    dx = max(b[0] - p[0], 0.0, p[0] - b[1])
    dy = max(b[2] - p[1], 0.0, p[1] - b[3])
    dz = max(b[4] - p[2], 0.0, p[2] - b[5])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def zone_dist(zone, p):
    bs = ZONES[zone]["boxes"]
    return min(box_dist(p, b) for b in bs) if bs else 1e12


# ------------------------------------------------------------------ S2 slices (lids) and S1 peels
# rect = (x0, x1, y0, y1) hole in the ground/road (the lid covers it), depth below z=0.
SLICES = {
    "maple_west": {"rect": (192.0, 214.0, 131.0, 144.0), "depth": 2.5, "stops": ("water_main_slice",),
                   "slide": (-23.0, 0.0, 0.006)},
    "maple_east": {"rect": (214.0, 236.0, 131.0, 144.0), "depth": 2.5, "stops": ("street_slice_fiber",),
                   "slide": (23.0, 0.0, 0.006)},
    "loop": {"rect": (0.3, 3.7, -16.0, -12.0), "depth": 0.6, "stops": ("road_loop_slice",),
             "slide": (3.6, 0.0, 0.006)},
    "handhole": {"rect": (262.4, 263.6, 219.6, 220.4), "depth": 1.0, "stops": ("tower_base",),
                 "slide": (0.0, -1.0, 0.006)},
    # wall slices (lid = siding / drywall patch that slides up)
    "wall_west": {"wall": "x", "at": 194.0, "span": (158.6, 160.4), "z": (-0.2, 1.0), "stops": ("ac_lines_wall",),
                  "slide": (0.0, 0.0, 1.4)},
    "wall_north": {"wall": "y", "at": 162.0, "span": (196.3, 197.7), "z": (0.0, 1.5), "stops": ("wall_pipes",),
                   "slide": (0.0, 0.0, 1.7)},
}
GROUND_HOLES = [SLICES[k]["rect"] for k in ("maple_west", "maple_east", "loop", "handhole")]
# S1 peel groups: stops that open the group + a trigger box (camera inside within the next LOOKAHEAD frames)
PEELS = {
    "house_south": {"stops": ("living_room_router", "living_room_tv", "thermostat"),
                    "box": (193.6, 206.4, 151.6, 157.5, 0.6, 9.5)},
    "house_north": {"stops": ("kitchen_microwave", "faucet_kitchen", "macro_microwave_mesh", "thermostat"),
                    "box": (193.6, 206.4, 157.5, 162.4, 0.6, 9.5)},
    "house_floor_hatch": {"stops": ("ac_indoor_coil",), "box": (193.6, 206.4, 151.6, 162.4, -2.2, 0.6)},
    "coil_panel": {"stops": ("ac_indoor_coil",), "box": None},
    "dc_roof": {"stops": ("edge_server_room",), "box": (-420.0, -375.0, 300.0, 330.0, 0.0, 14.0)},
    "mall_roof": {"stops": (), "box": (-130.0, -40.0, -70.0, -50.0, 0.0, 7.0)},
    "phone_display": {"stops": ("macro_phone_board", "macro_phone_antenna"), "box": None},
    "card_top": {"stops": ("macro_card_coil", "macro_card_chip"), "box": None},
    "terminal_case": {"stops": ("macro_terminal",), "box": None},
    "scanner_top": {"stops": ("macro_scanner",), "box": None},
    "mw_casing": {"stops": ("kitchen_microwave",), "box": None},
    "condenser_lid": {"stops": ("ac_condenser",), "box": None},
    "signal_door": {"stops": ("signal_cabinet",), "box": None},
    "tower_cabinet_door": {"stops": ("tower_base",), "box": None},
    "tank_slice": {"stops": ("water_tower",), "box": None},
    "filter_bed": {"stops": ("treatment_plant",), "box": None},
}
LEAD_F = 6           # a peel/lid starts opening this many frames before its move starts (0.2 s)
LOOKAHEAD_F = 12     # camera-inside test looks this far ahead (0.4 s)
PEEL_RAMP_F = 12     # 0.4 s open/close
LID_RAMP_F = 18      # 0.6 s


def rect_minus_holes(outer, holes):
    """Axis-aligned rectangle minus axis-aligned holes -> list of rectangles (x0, x1, y0, y1) covering the rest.
    Used for the ground / road planes so every S2 slice has a permanent opening under its lid."""
    x0, x1, y0, y1 = outer
    hs = [(max(h[0], x0), min(h[1], x1), max(h[2], y0), min(h[3], y1)) for h in holes]
    hs = [h for h in hs if h[0] < h[1] and h[2] < h[3]]
    xs = sorted({x0, x1} | {h[0] for h in hs} | {h[1] for h in hs})
    out = []
    for a, b in zip(xs, xs[1:]):
        cuts = sorted((h[2], h[3]) for h in hs if h[0] < b and h[1] > a)
        y = y0
        for c0, c1 in cuts:
            if c0 > y:
                out.append((a, b, y, c0))
            y = max(y, c1)
        if y < y1:
            out.append((a, b, y, y1))
    return out


# ------------------------------------------------------------------ plan-time entry point (worlds.py contract)
HOLD_TUNING = False  # OFF: hold scaling is owned by page2 camera_plan (cap requested 24 Nov 2026); kept for reference


DRIFT_FRAC_S = 0.010      # drift: lateral slide = 1 % of the subject distance per second (a 22 s beat = 22 %)
ORBIT_DEG_S = 1.5         # orbit: 1.5 deg/s (a 12 s beat = 18 deg, WORLDS-SPEC 8-15 deg per beat)


def tune_holds(episode):
    """Scale the adapter's hold specs to each stop's subject distance, IN PLACE on the expanded episode that
    camera_plan.build_plan consumes (worlds.plan_inputs passes the same object here).
    Why: camera_plan's default drift is a fixed 0.6 m/s (a 3 cm macro set is gone in 0.1 s; a 1.8 m faucet shot
    slides 9 m over a 15 s beat) and its orbit is 4 deg/s (80 deg over a 20 s beat). Beats here are 8-23 s long.
    drift -> speed = DRIFT_FRAC_S x subject distance (camera_plan.boosted still guarantees >= 0.6 px/frame);
    orbit -> +-ORBIT_DEG_S (direction kept from the adapter); macro stops (< 0.5 m): drift becomes a slow orbit
    (scale-free). Only touches keys the compact adapter made (they carry "stop"); idempotent. Returns notes."""
    oc = episode.get("oneshot") or {}
    if not HOLD_TUNING or not oc.get("_expanded"):
        return []
    notes = []
    for i, b in enumerate(episode.get("beats") or []):
        for k in (b.get("shot") or {}).get("camera") or []:
            stop, h = k.get("stop"), k.get("hold")
            if stop not in VIEWS or not isinstance(h, dict) or h.get("_ed"):
                continue
            d = subject_distance(stop)
            h = dict(h)
            kind = h.get("type", "drift")
            sign = -1.0 if float(h.get("deg_s", 1.0)) < 0 or (kind == "drift" and i % 2) else 1.0
            if kind == "orbit" or (kind == "drift" and is_macro(stop)):
                h = {"type": "orbit", "deg_s": sign * ORBIT_DEG_S}
            elif kind == "drift":
                h["speed"] = round(max(0.0005, DRIFT_FRAC_S * d), 5)
            elif kind == "crane":
                h["speed"] = round(min(0.5, DRIFT_FRAC_S * d), 5)
            h["_ed"] = True
            k["hold"] = h
            notes.append("%s:%s" % (b.get("id"), h["type"]))
    return notes


def plan_anchors(state):
    ep = (state or {}).get("episode")
    if isinstance(ep, dict):
        tune_holds(ep)
    anchors = {k: _r(s["anc"]) for k, s in VIEWS.items()}
    cams = {k: {"pos": _r(s["cam"]), "lens": float(s["lens"])} for k, s in VIEWS.items()}
    return {"anchors": anchors, "cams": cams,
            "meta": {k: {"zone": s["zone"], "w": s["w"], "subject_m": round(subject_distance(k), 4)}
                     for k, s in STOPS.items()}}


# ------------------------------------------------------------------ plan.json -> world timeline (bpy-free)
def first_stop(episode):
    return ((episode or {}).get("oneshot") or {}).get("stops", [None])[0]


def stop_track(plan, stop0):
    """[None, stop at frame 1, ...]: the stop the camera is at or moving to (a window's target from its f0)."""
    n = plan["frames"]
    out = [None] + [stop0] * n
    for w in sorted(plan["windows"], key=lambda w: w["f0"]):
        s = base_stop(w.get("stop") or w.get("to"))
        if s not in STOPS:
            continue
        for f in range(max(1, w["f0"]), n + 1):
            out[f] = s
    return out


def cam_pos(plan, f):
    r = plan["cam"][f]
    return (r[0], r[1], r[2])


def cam_look(plan, f):
    r = plan["cam"][f]
    return (r[3], r[4], r[5])


def _inside(p, b, m=0.0):
    return b[0] - m <= p[0] <= b[1] + m and b[2] - m <= p[1] <= b[3] + m and b[4] - m <= p[2] <= b[5] + m


def _ramp(goals, ramp_f):
    """Per-frame open amount 0..1 that moves towards goals[f] by 1/ramp_f per frame (frame 1 = its goal)."""
    out = [0.0] * len(goals)
    a = None
    for f in range(1, len(goals)):
        g = 1.0 if goals[f] else 0.0
        a = g if a is None else (min(g, a + 1.0 / ramp_f) if g > a else max(g, a - 1.0 / ramp_f))
        out[f] = round(a, 4)
    return out


def _goals(plan, track, stops, box=None):
    n = plan["frames"]
    goals = [False] * (n + 1)
    for f in range(1, n + 1):
        g = track[f] in stops or track[min(n, f + LEAD_F)] in stops
        if not g and box is not None:
            g = any(_inside(cam_pos(plan, h), box, 0.3) for h in range(f, min(n, f + LOOKAHEAD_F) + 1))
        goals[f] = g
    return goals


def peel_amounts(plan, stop0):
    """{peel group: [None, a1, a2, ...]} open amount per frame (0 closed .. 1 fully peeled)."""
    track = stop_track(plan, stop0)
    return {k: _ramp(_goals(plan, track, set(g["stops"]), g["box"]), PEEL_RAMP_F) for k, g in PEELS.items()}


def lid_amounts(plan, stop0):
    """{slice: [None, a1, ...]}: lid slid away (1) or closed (0). Driven by the stop track (a snap inside an open
    slice keeps it open even though the plan emits section None at that move's middle)."""
    track = stop_track(plan, stop0)
    return {k: _ramp(_goals(plan, track, set(s["stops"])), LID_RAMP_F) for k, s in SLICES.items()}


def zone_visible(plan, stop0, zone, f, track=None):
    z = ZONES[zone]
    if z.get("always"):
        return True
    track = track or stop_track(plan, stop0)
    n = plan["frames"]
    for s in (track[f], track[min(n, f + LEAD_F)]):
        if s in STOPS and (STOPS[s]["zone"] == zone or zone in ZONE_DEPS.get(STOPS[s]["zone"], ())):
            return True
    if zone == "Z_SKY":
        return cam_pos(plan, f)[2] > z["radius"] or cam_look(plan, f)[2] > z["radius"]
    r = z["radius"]
    if zone in DISTRICTS and enclosed(plan, f):
        r = min(r, ENCLOSED_RADIUS)
    return zone_dist(zone, cam_pos(plan, f)) <= r


def enclosed(plan, f):
    """Camera inside a building interior box or at macro distance (< 0.15 m): the far town is not visible."""
    p = cam_pos(plan, f)
    if _len(_sub(cam_look(plan, f), p)) < 0.15:
        return True
    return any(_inside(p, b) for zn in INTERIORS for b in ZONES[zn]["boxes"])


def beat_range(plan, lo, hi):
    """Widen lo..hi to whole beats: zone sets then change only at beat starts, which sit inside the move window
    of the next beat (moves start lead_s before the beat), so a proxy -> detail swap never pops on a hold."""
    a, b = lo, hi
    for bt in plan.get("beats") or []:
        f0, f1 = bt["f0"], bt["f0"] + bt["frames"] - 1
        if f0 <= lo <= f1:
            a = f0
        if f0 <= hi <= f1:
            b = f1
    return a, b


def zones_for_range(plan, stop0, lo, hi):
    """Zones to BUILD for a job covering frames lo..hi (the rest are not built at all: WORLDS-SPEC 6a)."""
    track = stop_track(plan, stop0)
    need = set(k for k, z in ZONES.items() if z.get("always"))
    for f in range(max(1, lo), min(plan["frames"], hi) + 1):
        for zn in ZONES:
            if zn not in need and zone_visible(plan, stop0, zn, f, track):
                need.add(zn)
    for zn in list(need):
        need.update(ZONE_DEPS.get(zn, ()))
    return need


def zone_vis_keys(plan, stop0, zone, lo, hi):
    """[(frame, visible)] transitions inside lo..hi (first entry at lo) for per-frame hide_render keys (6b)."""
    track = stop_track(plan, stop0)
    keys, prev = [], None
    for f in range(max(1, lo), min(plan["frames"], hi) + 1):
        v = zone_visible(plan, stop0, zone, f, track)
        if v != prev:
            keys.append((f, v))
            prev = v
    return keys


def clip_planes(plan, f):
    """(clip_start, clip_end) for frame f from the subject distance: 1 % of it, 0.2 mm .. 0.1 m, ratio 1e5."""
    d = max(1e-4, _len(_sub(cam_look(plan, f), cam_pos(plan, f))))
    cs = round(min(0.1, max(0.0002, 0.01 * d)), 6)
    return cs, round(min(20000.0, max(20.0, cs * 1e5)), 3)


def rebase_keys(plan, stop0):
    """[(frame, stop or None)]: floating-origin rebase switches (WORLDS-SPEC 1.1 R). Switch to a macro stop's anchor
    at the middle of the snap/portal/travel window that arrives there (a whip), back to the true origin at the
    middle of the next window that leaves the macro scale. OFF by default in the Blender module (needs page2)."""
    keys, cur = [(1, stop0 if stop0 and is_macro(stop0) else None)], None
    cur = keys[0][1]
    for w in sorted(plan["windows"], key=lambda w: w["f0"]):
        s = w.get("stop") or w.get("to")
        if w["kind"] == "backout":
            s = stop0
        tgt = s if (s in VIEWS and is_macro(s)) else None
        if tgt is not None and cur is not None and _len(_sub(VIEWS[tgt]["anc"], VIEWS[cur]["anc"])) < 0.2:
            continue                      # macro -> nearby macro: keep the same origin
        if tgt != cur:
            keys.append((w["mid"], tgt))
            cur = tgt
    return keys


def backout_stats(plan):
    """(frames, path length m, peak m/frame) of the backout window, or None."""
    bo = [w for w in plan["windows"] if w["kind"] == "backout"]
    if not bo:
        return None
    w = bo[-1]
    steps = [_len(_sub(cam_pos(plan, f + 1), cam_pos(plan, f))) for f in range(max(1, w["f0"] - 1), w["f1"])]
    return {"frames": w["f1"] - w["f0"] + 1, "length_m": round(sum(steps), 1), "peak_m_per_frame": round(max(steps), 2),
            "settle_frames": plan["frames"] - w["f1"]}


def hold_drift_stats(plan):
    """Per hold segment between windows: camera travel and look-point travel relative to the subject distance
    (look travel = how far the subject slides off centre; orbit keeps it 0)."""
    out = []
    wins = sorted(plan["windows"], key=lambda w: w["f0"])
    segs, f = [], 1
    for w in wins:
        if w["f0"] > f:
            segs.append((f, w["f0"] - 1))
        f = w["f1"] + 1
    if f <= plan["frames"]:
        segs.append((f, plan["frames"]))
    for a, b in segs:
        p0, p1 = cam_pos(plan, a), cam_pos(plan, b)
        d = max(1e-4, _len(_sub(cam_look(plan, a), p0)))
        lk = _len(_sub(cam_look(plan, b), cam_look(plan, a)))
        out.append({"f0": a, "f1": b, "subject_m": round(d, 4), "moved_m": round(_len(_sub(p1, p0)), 4),
                    "ratio": round(_len(_sub(p1, p0)) / d, 3), "look_ratio": round(lk / d, 3)})
    return out

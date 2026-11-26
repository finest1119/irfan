"""v2 one-shot coastal storm builder ("bomb cyclone", WJH 28 Nov 2026 #1, "if you were there"). Registers into
scene_lib_v2.V2_BUILDERS as `bomb_oneshot`.

Same pattern as scene_lib_v2_tides.py / scene_lib_v2_campus.py: ONE builder for every beat. Each beat builds the
identical bright seaside world and keys ALL animation (camera, wind, rain, sea, storm, arrows, props) on the GLOBAL
episode timeline (WORKDIR/audio/timings.json + captions.json), so the video is one continuous camera: slow drifts at
each spot, fast eased whips (EEVEE motion blur) between spots, and a backout that ends on the frame-1 view (loop).

World (north = +Y = the sea; the sun in the south-west, so most cameras look north / north-east):
  a white clapboard house with a porch on a low grassy bluff (z = Z0), a brass wall barometer by the door (ticks +
  needle only, no numbers), an orange/white windsock (no flags), neighbour houses and trees on the bluff, a beach road
  under the bluff with a blank amber road sign (its words are a 2D label), dunes with grass, a sand beach, a pier, a
  lighthouse on a rocky point, the open sea; far offshore (north-north-east) a huge sunlit comma-shaped storm swirl
  (icosphere puffs, grey base). Engine beat: blue (cold, from land) and orange (warm, from the ocean) arrows that meet
  and spiral up, a glowing jet-stream ribbon high above. Rain / snow = shader planes parented to the camera (no
  wrapping geometry, so motion blur never smears). No people, no damage, no 3D text.

Beats it expects: hook, question, you_morning, you_engine, you_pressure, you_wind, you_cold, takeaway, outro.
Missing cue words fall back to a fraction of their beat.
"""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc
import scene_lib_v2_city as C
import scene_lib_v2_tides as TD
import scene_lib_v2_storm as ST
from scene_lib_v2_winter import set_keys

TL, bake, bake_sock, curve, smooth, smoother = TD.TL, TD.bake, TD.bake_sock, TD.curve, TD.smooth, TD.smoother
vadd, vsub, vmul, vdot, vcross, vlen, vnorm, vlerp = (TD.vadd, TD.vsub, TD.vmul, TD.vdot, TD.vcross, TD.vlen,
                                                      TD.vnorm, TD.vlerp)
lin, camera_at, show_between, box, boxes, cyl, puffs, empty = (TD.lin, TD.camera_at, TD.show_between, TD.box,
                                                               TD.boxes, TD.cyl, TD.puffs, TD.empty)

# ---------------------------------------------------------------- layout
Z0 = 6.0                          # bluff top
HOUSE = (0.0, -27.0)              # house centre; front (porch side) faces +Y
HW, HD, HH = 11.0, 9.0, 6.2
FRONT_Y = HOUSE[1] + HD / 2       # -22.5
BARO = (1.55, FRONT_Y + 0.05, Z0 + 0.45 + 1.55)
SOCK = (-9.0, -17.5)
ROAD_Y = (2.0, 9.0)
ROAD_Z = 0.6
SIGN = (-10.0, 9.3)
PIER_X, PIER_W, PIER_Y0, PIER_Y1, DECK_Z = 40.0, 6.0, 9.5, 140.0, 3.2
LIGHT = (130.0, 100.0)            # lighthouse on its rocky point
SC = (2300.0, 3900.0)             # storm centre (frame-1 view: right behind the house)
R_ST = 1900.0
TABLE = (-3.2, -20.6)
CHAIR = (-4.4, -20.4)
EXT = 7000.0

P1 = ((-26.0, -60.0, 15.5), (16.0, 12.0, 10.5), 26.0)   # frame-1 view; the backout ends here

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def gz(y):
    """Ground height: beach slope (north), dunes, flat road strip, the bluff, the gently rising land behind."""
    if y >= 14.0:
        return 0.9 - (y - 14.0) * 0.06
    if y >= 9.0:
        return ROAD_Z + 0.3 * smooth((y - 9.0) / 5.0)
    if y >= 0.0:
        return ROAD_Z
    if y >= -16.0:
        return ROAD_Z + (Z0 - ROAD_Z) * smooth(-y / 16.0)
    return Z0 + min(30.0, (-16.0 - y) * 0.01)


# ================================================================ story curves (global seconds)
class Story:
    def __init__(self, tl):
        c, b0, b1 = tl.cue, tl.bstart, tl.bend
        self.T = tl.T
        T = self.T
        self.t_q, self.t_m, self.t_e = b0("question"), b0("you_morning"), b0("you_engine")
        self.t_p, self.t_w, self.t_c = b0("you_pressure"), b0("you_wind"), b0("you_cold")
        self.t_k, self.t_o = b0("takeaway"), b0("outro")
        self.c_grey = c("you_morning", "grey", 0.25)
        self.c_baro = c("you_morning", "barometer", 0.5)
        self.c_fall = c("you_morning", "falling", 0.65)
        self.c_cold = c("you_engine", "cold", 0.08)
        self.c_warm = c("you_engine", "warm", 0.25)
        self.c_jet = c("you_engine", "jet", 0.65)
        self.c_pull = c("you_engine", "pulling", 0.7)
        self.c_drop = c("you_pressure", "pressure", 0.25)
        self.c_fore = c("you_pressure", "forecasters", 0.52)
        self.c_races = c("you_wind", "races", 0.12)
        self.c_doub = c("you_wind", "doubles", 0.28)
        self.c_rain = c("you_wind", "rain", 0.36)
        self.c_stl = c("you_wind", "storm", 0.5)
        self.c_shove = c("you_wind", "shoves", 0.8)
        self.c_swing = c("you_cold", "swings", 0.1)
        self.c_coldp = c("you_cold", "cold", 0.33)
        self.c_snow = c("you_cold", "snow", 0.85)
        self.c_charge = c("takeaway", "charge", 0.28)
        self.c_tie = c("takeaway", "tie", 0.4)
        self.c_stay = c("takeaway", "stay", 0.6)
        self.c_flood = c("takeaway", "flooded", 0.85)
        self.c_bec = c("outro", "because", 0.5)
        # wind strength 0..1 (0.25 = the breezy frame-1 state)
        self.wind = curve([(0.0, 0.25), (self.t_m, 0.25), (self.c_grey, 0.38), (self.t_e, 0.45),
                           (self.t_w + 0.3, 0.6), (self.c_races, 0.62), (self.c_doub + 0.6, 1.0),
                           (self.t_c + 0.2, 1.0), (self.c_coldp, 0.8), (self.t_k - 0.2, 0.8), (self.t_k + 0.6, 0.25),
                           (T + 1.0, 0.25)])
        # downwind azimuth (degrees, math angle in XY). Onshore = towards -Y (-90); after the swing towards the sea.
        self.az = curve([(0.0, -112.0), (self.t_m, -112.0), (self.c_grey, -100.0), (self.t_w, -95.0),
                         (self.c_swing - 0.2, -95.0), (self.c_swing + 1.4, 70.0), (self.t_k + 0.3, 70.0),
                         (self.c_stay - 0.3, 70.0), (self.t_o - 0.2, -112.0), (T + 1.0, -112.0)])
        # rain 0..1, snow 0..1, streak roll (deg)
        self.rain = curve([(0.0, 0.0), (self.c_grey - 0.4, 0.0), (self.c_grey + 0.6, 0.32), (self.t_e - 0.4, 0.32),
                           (self.t_e + 0.2, 0.0), (self.t_w + 0.8, 0.0), (self.c_rain - 0.4, 0.45),
                           (self.c_rain + 0.4, 0.85), (self.c_snow - 1.0, 0.75), (self.c_snow, 0.0), (T + 1.0, 0.0)])
        self.snow = curve([(self.c_snow - 1.2, 0.0), (self.c_snow, 0.9), (self.t_k - 0.1, 0.9), (self.t_k + 0.5, 0.0)])
        self.roll = curve([(0.0, 6.0), (self.t_w + 0.5, 6.0), (self.c_rain - 0.3, 18.0), (self.c_rain + 0.6, 48.0),
                           (self.c_snow - 0.5, 40.0), (self.c_snow + 0.5, 15.0), (T + 1.0, 15.0)])
        # sea level (storm surge) and wave size
        self.sea = curve([(0.0, 0.0), (self.c_doub, 0.0), (self.c_shove + 0.5, 0.65), (self.t_k, 0.6),
                          (self.t_o, 0.3), (self.c_bec - 0.5, 0.0), (T + 1.0, 0.0)])
        self.wave = curve([(0.0, 0.35), (self.t_m, 0.35), (self.c_grey, 0.45), (self.t_w, 0.6),
                           (self.c_doub, 1.0), (self.t_c + 1.0, 1.0), (self.t_k, 0.6), (self.t_o, 0.45),
                           (self.c_bec, 0.35), (T + 1.0, 0.35)])
        # scud clouds (grey sky) 0..1
        self.scud = curve([(0.0, 0.0), (self.c_grey - 1.5, 0.0), (self.c_grey + 0.5, 1.0), (self.c_coldp, 1.0),
                           (self.c_snow + 0.3, 0.0), (T + 1.0, 0.0)])
        # storm: spin (deg) and tighten (0..1)
        self.tight = curve([(self.t_p - 0.5, 0.0), (self.c_drop + 0.3, 0.35), (self.c_fore + 2.5, 1.0),
                            (self.t_w + 0.3, 1.0), (self.t_k, 0.0)])
        # barometer needle (deg, + = towards the viewer's left / "stormy")
        self.needle = curve([(0.0, -32.0), (self.c_baro, -32.0), (self.c_fall - 0.6, -5.0), (self.c_fall + 1.4, 52.0),
                             (self.t_p, 60.0), (self.t_w, 78.0), (self.t_k, 78.0), (self.t_o, -32.0)])
        # windows (on, off) for the arrow sets
        self.win_cold = (self.c_cold - 0.4, self.c_drop + 2.0)
        self.win_warm = (self.c_warm - 0.4, self.c_drop + 2.0)
        self.win_jet = (self.c_jet - 0.5, self.c_fore - 0.4)
        self.win_up = (self.c_pull - 0.4, self.c_fore - 0.4)
        self.win_wind = (self.c_races - 0.4, self.c_stl - 0.3)
        self.win_back = (self.c_swing + 0.6, self.t_k + 0.1)
        self.flood_on = self.c_shove


# ================================================================ camera route
def orbit(cen, r, z, a0, a1, tz, lens):
    def f(t, u):
        a = math.radians(a0 + (a1 - a0) * u)
        return (cen[0] + r * math.cos(a), cen[1] + r * math.sin(a), z), (cen[0], cen[1], tz), lens
    return f


def route(tl, st):
    c, b0 = tl.cue, tl.bstart
    bx, by, bz = BARO
    sx, sy = SC
    oA = ((-15.5, -42.0, 13.8), (16.0, 12.0, 10.5), 30.0)
    oA1 = ((-16.3, -43.3, 13.9), (16.0, 12.0, 10.5), 29.5)
    spots = [
        # hook: frame-1 view, house on the bluff, the storm swirl over the sea
        (0.0, 0.0, lin(P1, ((-25.0, -58.4, 15.4), (16.0, 12.0, 10.5), 27.0)), []),
        # hook "forecasters": bluff edge, beach + pier + lighthouse + the vast storm (hero 1)
        (c("hook", "forecasters", 0.55) - 0.15, 0.9, lin(((9.0, -15.0, 8.2), (600.0, 1300.0, 220.0), 26.0),
                                                       ((9.4, -13.6, 8.25), (600.0, 1300.0, 220.0), 27.0)),
         [(-4.0, -30.0, 12.0)]),
        # question: turn to the porch
        (b0("question") + 0.15, 0.8, lin(((7.5, -9.5, 9.6), (0.0, -22.0, 8.2), 26.0),
                                         ((6.9, -10.4, 9.4), (0.0, -22.0, 8.2), 27.0)), []),
        # you_morning: the house on its bluff from the beach road, light rain
        (b0("you_morning") + 0.2, 0.8, lin(((-12.0, 13.0, 5.6), (0.0, -24.0, 9.6), 28.0),
                                           ((-11.5, 11.8, 5.6), (0.0, -24.0, 9.6), 29.0)), [(-4.0, -2.0, 7.0)]),
        # ... the barometer on the wall (needle falls)
        (st.c_baro - 0.15, 0.75, lin(((bx + 0.3, by + 1.65, bz + 0.06), (bx, by, bz), 35.0),
                                     ((bx + 0.24, by + 1.38, bz + 0.05), (bx, by, bz), 36.0)), [(bx - 1.0, by + 5.0, bz + 1.0)]),
        # you_engine: whip out over the sea; cold (blue) and warm (orange) air meet offshore
        (b0("you_engine") + 0.35, 1.3, lin(((sx - 2600.0, sy - 4600.0, 1300.0), (sx - 200.0, sy - 400.0, 750.0), 22.0),
                                           ((sx - 2520.0, sy - 4450.0, 1280.0), (sx - 200.0, sy - 400.0, 750.0), 23.0)),
         [(bx, by + 8.0, bz + 4.0), (0.0, 40.0, 40.0), (-300.0, 300.0, 300.0)]),
        # ... tilt up to the jet stream
        (st.c_jet - 0.2, 0.8, lin(((sx - 2500.0, sy - 4300.0, 1500.0), (sx - 300.0, sy - 300.0, 1750.0), 20.0),
                                  ((sx - 2450.0, sy - 4200.0, 1540.0), (sx - 300.0, sy - 300.0, 1750.0), 20.5)), []),
        # you_pressure: straight down the storm from high above (hero 2: coast + tiny house at the bottom edge)
        (b0("you_pressure") + 0.25, 1.0, lin(((sx - 700.0, -300.0, 5600.0), (sx - 500.0, sy - 600.0, 0.0), 16.0),
                                            ((sx - 690.0, -150.0, 5350.0), (sx - 500.0, sy - 600.0, 0.0), 16.5)), []),
        # ... closer, down the funnel
        (st.c_fore - 0.2, 0.8, lin(((sx + 80.0, sy - 600.0, 3600.0), (sx, sy, 300.0), 20.0),
                                   ((sx + 75.0, sy - 560.0, 3350.0), (sx, sy, 300.0), 20.0)), []),
        # you_wind: dive back to the beach: dunes, windsock, bending trees, the house
        (b0("you_wind") + 0.4, 1.4, lin(((34.0, 16.0, 9.0), (-4.0, -22.0, 9.0), 24.0),
                                        ((32.6, 15.0, 8.9), (-4.0, -22.0, 9.0), 25.0)),
         [(sx - 600.0, sy - 2500.0, 1500.0), (300.0, 600.0, 200.0), (60.0, 60.0, 15.0)]),
        # ... "a storm like this": waves at the pier, the storm behind
        (st.c_stl - 0.2, 0.8, lin(((14.0, 16.0, 3.6), (700.0, 1500.0, 110.0), 24.0),
                                  ((14.5, 17.4, 3.5), (700.0, 1500.0, 110.0), 25.0)), []),
        # you_cold: wrap around the house (orbit 16 deg)
        (b0("you_cold") + 0.25, 0.9, orbit((HOUSE[0], HOUSE[1]), 23.0, 12.5, 18.0, 34.0, 9.0, 24.0), [(10.0, 0.0, 8.0)]),
        # takeaway: the porch table (phone on charge) + strapped chair
        (b0("takeaway") + 0.2, 0.8, lin(((-1.3, -19.65, 7.8), (TABLE[0] - 0.4, TABLE[1] - 0.1, Z0 + 0.95), 24.0),
                                        ((-1.45, -19.75, 7.75), (TABLE[0] - 0.4, TABLE[1] - 0.1, Z0 + 0.95), 24.5)), []),
        # ... the flooded beach road sign
        (st.c_stay - 0.15, 0.75, lin(((-4.6, 0.4, 2.9), (SIGN[0], SIGN[1], 2.3), 28.0),
                                     ((-5.0, 0.9, 2.85), (SIGN[0], SIGN[1], 2.3), 28.5)), [(-2.0, -12.0, 8.0)]),
        # outro: over the house towards the storm
        (b0("outro") + 0.2, 0.9, lin(oA, oA1), [(-6.0, -10.0, 8.0)]),
        # ... backout to the frame-1 view (loop)
        (st.c_bec - 0.2, 0.4, lin(oA1, P1, ease=True), []),
    ]
    out = []
    for s in spots:
        if out:
            ptc, pwd = out[-1][0], out[-1][1]
            lo = ptc + pwd / 2.0 + s[1] / 2.0 + 1.0
            if s[0] < lo:
                s = (lo,) + tuple(s[1:])
        out.append(s)
    return out


# ================================================================ materials
def storm_mat():
    """Sunlit storm tops: light grey facing the camera, slate-blue towards each puff's silhouette. Not hazed."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("cy_storm")
        lw = N.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.45
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.2, hexc("eef1f5")
        els[1].position, els[1].color = 0.95, hexc("66758c")
        Lk.new(lw.outputs["Facing"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        Lk.new(ramp.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 0.55
        p.inputs["Roughness"].default_value = 1.0
        p.inputs["Specular IOR Level"].default_value = 0.0
        S._finish(m, p.outputs[0], haze=False)
        return m
    return _m("storm", mk)


def storm_base_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("cy_storm_base")
        p.inputs["Base Color"].default_value = hexc("a3abb7")
        p.inputs["Emission Color"].default_value = hexc("b4bcc7")
        p.inputs["Emission Strength"].default_value = 0.45
        p.inputs["Roughness"].default_value = 1.0
        p.inputs["Specular IOR Level"].default_value = 0.0
        S._finish(m, p.outputs[0], haze=False)
        return m
    return _m("storm_base", mk)


def sea_mat():
    """Sea: teal ripples (noise W on global time); `storm` Value (0..1) greys it and roughens the bump."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("cy_sea")
        p.inputs["Roughness"].default_value = 0.09
        p.inputs["Specular IOR Level"].default_value = 0.5
        p.inputs["Coat Weight"].default_value = 0.15
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 0.45, 1.0)
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 0.16
        nz.inputs["Detail"].default_value = 8.0
        nz.inputs["Roughness"].default_value = 0.6
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        storm = N.new("ShaderNodeValue")
        storm.outputs[0].default_value = 0.0
        bs = N.new("ShaderNodeMath")
        bs.operation = "MULTIPLY_ADD"
        bs.inputs[1].default_value = 0.9
        bs.inputs[2].default_value = 0.2
        Lk.new(storm.outputs[0], bs.inputs[0])
        b = N.new("ShaderNodeBump")
        b.inputs["Distance"].default_value = 0.35
        Lk.new(bs.outputs[0], b.inputs["Strength"])
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        # whitecaps: high noise values -> foam white, more of them with the storm
        nz2 = N.new("ShaderNodeTexNoise")
        nz2.noise_dimensions = "4D"
        nz2.inputs["Scale"].default_value = 0.6
        nz2.inputs["Detail"].default_value = 3.0
        Lk.new(mp.outputs["Vector"], nz2.inputs["Vector"])
        thr = N.new("ShaderNodeMath")
        thr.operation = "MULTIPLY_ADD"
        thr.inputs[1].default_value = -0.1
        thr.inputs[2].default_value = 0.74
        Lk.new(storm.outputs[0], thr.inputs[0])
        sub = N.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        Lk.new(nz2.outputs["Fac"], sub.inputs[0])
        Lk.new(thr.outputs[0], sub.inputs[1])
        foam = N.new("ShaderNodeMath")
        foam.operation = "MULTIPLY"
        foam.use_clamp = True
        foam.inputs[1].default_value = 14.0
        Lk.new(sub.outputs[0], foam.inputs[0])
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = hexc("2a7d95")
        mix.inputs["B"].default_value = hexc("5d7f86")
        Lk.new(storm.outputs[0], mix.inputs["Factor"])
        mix2 = N.new("ShaderNodeMix")
        mix2.data_type = "RGBA"
        mix2.inputs["B"].default_value = hexc("e9f1f2")
        Lk.new(mix.outputs["Result"], mix2.inputs["A"])
        Lk.new(foam.outputs[0], mix2.inputs["Factor"])
        Lk.new(mix2.outputs["Result"], p.inputs["Base Color"])
        S._finish(m, p.outputs[0])
        return m, nz.inputs["W"], nz2.inputs["W"], storm.outputs[0], tc
    return _m("sea", mk)


def foam_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("cy_foam")
        m.surface_render_method = "BLENDED"
        p.inputs["Base Color"].default_value = hexc("f2f7f7")
        p.inputs["Roughness"].default_value = 0.5
        p.inputs["Emission Color"].default_value = hexc("ffffff")
        p.inputs["Emission Strength"].default_value = 0.12
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 0.7
        nz.inputs["Detail"].default_value = 6.0
        nz.inputs["Roughness"].default_value = 0.65
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.38
        ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        ramp.color_ramp.elements[1].position = 0.6
        ramp.color_ramp.elements[1].color = (0.92, 0.92, 0.92, 1)
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Alpha"])
        S._finish(m, p.outputs[0])
        return m
    return _m("foam", mk)


def precip_mat(name, kind):
    """Camera-plane precipitation: Voronoi cells stretched along Y (rain streaks) or round (snow flakes); the
    Mapping Location scrolls with global time (no geometry moves, so no motion-blur smear). Returns
    (mat, location socket, intensity socket)."""
    m = bpy.data.materials.new(name)
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    vo = N.new("ShaderNodeTexVoronoi")
    vo.voronoi_dimensions = "3D"
    vo.inputs["Randomness"].default_value = 1.0
    Lk.new(mp.outputs["Vector"], vo.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    if kind == "rain":
        els[0].position, els[0].color = 0.0, (1, 1, 1, 1)
        els[1].position, els[1].color = 0.11, (0, 0, 0, 1)
    else:
        els[0].position, els[0].color = 0.0, (1, 1, 1, 1)
        els[1].position, els[1].color = 0.16, (0, 0, 0, 1)
    Lk.new(vo.outputs["Distance"], ramp.inputs[0])
    # thin out: only some cells carry a streak/flake (cell colour channel)
    sep = N.new("ShaderNodeSeparateColor")
    Lk.new(vo.outputs["Color"], sep.inputs[0])
    gt = N.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.45 if kind == "rain" else 0.3
    Lk.new(sep.outputs[0], gt.inputs[0])
    a1 = N.new("ShaderNodeMath")
    a1.operation = "MULTIPLY"
    Lk.new(ramp.outputs["Color"], a1.inputs[0])
    Lk.new(gt.outputs[0], a1.inputs[1])
    inten = N.new("ShaderNodeValue")
    inten.outputs[0].default_value = 0.0
    a2 = N.new("ShaderNodeMath")
    a2.operation = "MULTIPLY"
    a2.use_clamp = True
    Lk.new(a1.outputs[0], a2.inputs[0])
    Lk.new(inten.outputs[0], a2.inputs[1])
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hexc("e6eef6") if kind == "rain" else hexc("ffffff")
    em.inputs["Strength"].default_value = 1.1 if kind == "rain" else 1.5
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    Lk.new(a2.outputs[0], mix.inputs[0])
    Lk.new(tr.outputs[0], mix.inputs[1])
    Lk.new(em.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], N.get("Material Output").inputs["Surface"])
    return m, mp, inten.outputs[0]


def mats():
    def mk():
        g = TD.mats()
        g.update({
            "sand": S.pbr("cy_sand", hexc("dcc9a0"), 0.9, var=0.07, var_scale=0.08, bump=0.05),
            "wetsand": S.pbr("cy_wetsand", hexc("a8977a"), 0.35, var=0.05, var_scale=0.1),
            "lawn": S.lawn_mat("cy_lawn", hexc("6f9148"), stripes=False),
            "dune_grass": S.pbr("cy_grass", hexc("9aa060"), 0.85, var=0.15, var_scale=2.0),
            "clap": S.pbr("cy_clap", hexc("eef0ee"), 0.7, var=0.03, var_scale=0.3, bump=0.04),
            "trim": S.pbr("cy_trim", hexc("ffffff"), 0.5, var=0.01),
            "shingle": S.pbr("cy_shingle", hexc("59626e"), 0.8, var=0.1, var_scale=1.5, bump=0.06),
            "porch": S.pbr("cy_porch", hexc("8f7458"), 0.7, var=0.1, var_scale=2.0, bump=0.03),
            "door": S.pbr("cy_door", hexc("2c5d8a"), 0.5, var=0.02),
            "win": S.pbr("cy_win", hexc("33465a"), 0.08, var=0.0),
            "brass": S.pbr("cy_brass", hexc("c49a45"), 0.3, metal=0.9, var=0.03),
            "dial": S.emis("cy_dial", hexc("f6f1e4"), 0.6),
            "tick": S.pbr("cy_tick", hexc("23262b"), 0.5, var=0.0),
            "tick_r": S.emis("cy_tick_r", hexc("c8342e"), 0.8),
            "tick_b": S.emis("cy_tick_b", hexc("2f6fb0"), 0.8),
            "sock_o": S.pbr("cy_sock_o", hexc("f2701d"), 0.6, var=0.02),
            "sock_w": S.pbr("cy_sock_w", hexc("f4f4f2"), 0.6, var=0.02),
            "rock": S.pbr("cy_rock", hexc("7c7a73"), 0.9, var=0.15, var_scale=0.2, bump=0.1),
            "lh_red": S.pbr("cy_lh_red", hexc("c5352d"), 0.5, var=0.02),
            "lh_lamp": S.emis("cy_lh_lamp", hexc("fff2c4"), 3.0),
            "strap": S.pbr("cy_strap", hexc("f0c419"), 0.55, var=0.02),
            "phone": S.pbr("cy_phone", hexc("15171b"), 0.25, var=0.0),
            "screen": S.emis("cy_screen", hexc("9fd9ff"), 1.4),
            "batt": S.emis("cy_batt", hexc("38d36a"), 3.0),
            "cable": S.pbr("cy_cable", hexc("f2f2f2"), 0.5, var=0.0),
            "chair": S.pbr("cy_chair", hexc("3f7f8c"), 0.6, var=0.03),
            "cold": S.emis("cy_cold", hexc("2f86ff"), 4.0),
            "warmA": S.emis("cy_warm", hexc("ff6a12"), 4.0),
            "jet": S.emis("cy_jet", hexc("7fe8ff"), 4.0),
            "windw": S.emis("cy_windw", hexc("f2fdff"), 2.6),
            "windb": S.emis("cy_windb", hexc("6cc2ff"), 3.0),
        })
        return g
    return _m("mats", mk)


def ribbon_mat():
    def mk():
        m, nt, N, Lk, p = S._new_mat("cy_ribbon")
        m.surface_render_method = "BLENDED"
        p.inputs["Base Color"].default_value = hexc("2fc8f0")
        p.inputs["Emission Color"].default_value = hexc("2fc8f0")
        p.inputs["Emission Strength"].default_value = 2.2
        p.inputs["Alpha"].default_value = 0.6
        S._finish(m, p.outputs[0], haze=False)
        return m
    return _m("ribbon", mk)


# ================================================================ world
def build_land(mt):
    rows = sorted(set([60.0, 40.0, 30.0, 24.0, 20.0, 17.0, 14.0, 12.0, 10.5, 9.0, 2.0, 0.0] +
                      [-2.0 * i for i in range(1, 9)] + [-20.0, -30.0, -60.0, -120.0, -300.0, -900.0, -3000.0, -EXT]),
                  reverse=True)
    bm = bmesh.new()
    prev = None
    for y in rows:
        z = gz(y)
        cur = (bm.verts.new((-EXT, y, z)), bm.verts.new((EXT, y, z)))
        if prev:
            f = bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
            ym = (prev[0].co.y + y) / 2
            f.material_index = 0 if ym > 10.0 else 1
        prev = cur
    # the beach must continue well under the sea (no gap at the far side)
    S.obj("land", S.mesh_from_bm("land", bm, [mt["sand"], mt["lawn"]]))
    bm = bmesh.new()
    box(bm, (0.0, sum(ROAD_Y) / 2, ROAD_Z + 0.06), (2 * EXT, ROAD_Y[1] - ROAD_Y[0], 0.12))
    S.obj("road", S.mesh_from_bm("road", bm, [mt["road"]]))
    bm = bmesh.new()
    for i in range(-400, 400):
        if i % 2 == 0:
            box(bm, (i * 3.0, sum(ROAD_Y) / 2, ROAD_Z + 0.125), (1.6, 0.14, 0.01))
    S.obj("road_lines", S.mesh_from_bm("road_lines", bm, [mt["line"]]))


def build_dunes(tl, st, mt, rng):
    """Low sand dunes along the beach + grass tufts that bend with the wind."""
    bl = []
    x = -420.0
    while x < 420.0:
        if abs(x - PIER_X) > 7.0:
            bl.append((x, 11.8 + rng.uniform(-0.8, 0.8), 0.2, rng.uniform(3.0, 5.0), 0.22))
        x += rng.uniform(3.0, 5.0)
    bm = bmesh.new()
    for x, y, z, r, fl in bl:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                   matrix=Matrix.Translation((x, y, gz(y) + z - 0.3)) @ Matrix.Diagonal((r, r * 0.8, r * fl, 1.0)))
    S.obj("dunes", S.mesh_from_bm("dunes", bm, [mt["sand"]], smooth=True))
    # grass tuft template: a fan of thin blades (origin at the base)
    bm = bmesh.new()
    r2 = random.Random(3)
    for k in range(9):
        a = 2 * math.pi * k / 9 + r2.uniform(-0.2, 0.2)
        h = r2.uniform(0.7, 1.1)
        lean = 0.25
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.035, radius2=0.0, depth=h)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=res["verts"])
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                         matrix=Matrix.Rotation(lean, 3, Vector((math.sin(a), -math.cos(a), 0))))
    me = S.mesh_from_bm("tuft", bm, [mt["dune_grass"]])
    tufts = []
    for (x, y, z, r, fl) in bl:
        for j in range(3):
            tx, ty = x + rng.uniform(-r * 0.7, r * 0.7), y + rng.uniform(-r * 0.4, r * 0.4)
            o = S.obj("tuft%d" % len(tufts), me, (tx, ty, gz(ty) + z + r * fl * 0.45 - 0.35),
                      (0, 0, rng.uniform(0, 6.28)), (1.6,) * 3)
            tufts.append(o)
    return tufts


def bend(tl, st, objs, amp_deg, freq, rng, step=2, near=None):
    """Tilt each object downwind (rotation about its base) with a gust wobble; global-time baked."""
    for o in objs:
        if near is not None and vlen(vsub(tuple(o.location), near[0])) > near[1]:
            continue
        z0 = o.rotation_euler.z
        ph = rng.uniform(0, 6.28)
        fq = freq * rng.uniform(0.8, 1.25)

        def rot(t, z0=z0, ph=ph, fq=fq):
            w = st.wind(t)
            a = math.radians(amp_deg) * w * (0.75 + 0.25 * math.sin(fq * t + ph)) * (0.4 + 0.6 * w)
            az = math.radians(st.az(t)) - z0
            return (-a * math.sin(az), a * math.cos(az), z0)
        bake(tl, o, "rotation_euler", rot, step=step)


def build_sea(tl, st, mt):
    m, w1, w2, storm, tc = sea_mat()
    sea = S.plane_obj("sea", 4 * EXT * 2.0, 30000.0, (0.0, 15024.0, 0.0), m)
    tc.object = sea
    bake(tl, sea, "location", lambda t: (0.0, 15024.0, st.sea(t)))
    bake_sock(tl, w1, lambda t: t * 0.25)
    bake_sock(tl, w2, lambda t: t * 0.4)
    bake_sock(tl, storm, lambda t: max(0.0, min(1.0, (st.wave(t) - 0.35) / 0.65)))
    # breaking-wave crests rolling in towards the shore (long foam ridges; shrink to nothing at both ends)
    fm = foam_mat()
    span = 70.0
    for k in range(7):
        bm = bmesh.new()
        r2 = random.Random(40 + k)
        x = -330.0
        while x < 360.0:
            seg = r2.uniform(18.0, 46.0)
            if not (PIER_X - 3.5 < x + seg / 2 < PIER_X + 3.5):
                n = 8
                for i in range(n):
                    xa = x + seg * i / n
                    yo = 1.2 * math.sin(xa * 0.05 + k)
                    rr = 0.9 * (1.0 - abs(i - n / 2 + 0.5) / (n / 2 + 0.5)) + 0.25
                    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=rr, radius2=rr, depth=seg / n,
                                          matrix=Matrix.Translation((xa + seg / n / 2, yo, 0.0)) @
                                          Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Diagonal((0.4, 1.6, 1.0, 1.0)))
            x += seg + r2.uniform(4.0, 14.0)
        o = S.obj("crest%d" % k, S.mesh_from_bm("crest%d" % k, bm, [fm], smooth=True))
        o.visible_shadow = False

        def shore(t):
            return 14.0 + (0.9 - st.sea(t)) / 0.06

        def pos(t, k=k):
            s = ((k / 7.0) + t * 0.11) % 1.0
            y = shore(t) + span * (1.0 - s)
            return (0.0, y, st.sea(t) - 0.05)

        def scl(t, k=k):
            s = ((k / 7.0) + t * 0.11) % 1.0
            e = smooth((min(s, 1.0 - s) - 0.03) / 0.2)
            h = max(0.001, e * st.wave(t))
            return (1.0, max(0.001, e), h)
        bake(tl, o, "location", pos)
        bake(tl, o, "scale", scl)


def build_house(tl, st, mt, ctx):
    hx, hy = HOUSE
    z = Z0
    bm = bmesh.new()
    box(bm, (hx, hy, z + HH / 2 - 0.4), (HW, HD, HH + 0.8), 0)
    ov = 0.45
    S.bm_prism_x(bm, hx - HW / 2 - ov, hx + HW / 2 + ov,
                 [(hy - HD / 2 - ov, z + HH - 0.1), (hy + HD / 2 + ov, z + HH - 0.1), (hy, z + HH + 2.6)], 1)
    # chimney
    box(bm, (hx - 3.2, hy - 1.0, z + HH + 2.2), (0.9, 0.9, 2.6), 5)
    # windows (front + sides), trim boxes
    for k in (-3.6, 3.6):
        for zz in (z + 1.6, z + 4.4):
            box(bm, (hx + k, FRONT_Y + 0.04, zz), (1.3, 0.08, 1.4), 2)
            box(bm, (hx + k, FRONT_Y + 0.03, zz), (1.55, 0.06, 1.65), 3)
    box(bm, (hx, FRONT_Y + 0.04, z + 4.4), (1.3, 0.08, 1.4), 2)
    for k in (-3.6, 0.0, 3.6):
        for zz in (z + 1.6, z + 4.4):
            box(bm, (hx + k, hy - HD / 2 - 0.04, zz), (1.3, 0.08, 1.4), 2)
            box(bm, (hx + k, hy - HD / 2 - 0.03, zz), (1.55, 0.06, 1.65), 3)
    box(bm, (hx, FRONT_Y + 0.03, z + 4.4), (1.55, 0.06, 1.65), 3)
    for sx in (-1, 1):
        for yy in (hy - 2.0, hy + 2.0):
            box(bm, (hx + sx * (HW / 2 + 0.04), yy, z + 2.9), (0.08, 1.2, 1.3), 2)
    # door
    box(bm, (hx - 0.4, FRONT_Y + 0.05, z + 0.45 + 1.05), (1.0, 0.1, 2.1), 4)
    box(bm, (hx - 0.4, FRONT_Y + 0.04, z + 0.45 + 1.1), (1.25, 0.08, 2.3), 3)
    S.obj("house", S.mesh_from_bm("house", bm, [mt["clap"], mt["shingle"], mt["win"], mt["trim"], mt["door"],
                                                mt["roof"]]))
    # porch: deck, steps, posts, rail, roof
    bm = bmesh.new()
    py0, py1 = FRONT_Y, FRONT_Y + 3.2
    box(bm, (hx, (py0 + py1) / 2, z + 0.225), (HW - 0.6, py1 - py0, 0.45), 0)
    for i in range(3):
        box(bm, (hx - 0.4, py1 + 0.3 + 0.3 * i, z + 0.15 * (2 - i) + 0.075), (2.0, 0.3, 0.15 * (3 - i)), 0)
    for xx in (hx - HW / 2 + 0.5, hx - 2.0, hx + 1.2, hx + HW / 2 - 0.5):
        box(bm, (xx, py1 - 0.15, z + 0.45 + 1.4), (0.18, 0.18, 2.8), 1)
    for x0, x1 in ((hx - HW / 2 + 0.5, hx - 1.5), (hx + 0.7, hx + HW / 2 - 0.5)):
        box(bm, ((x0 + x1) / 2, py1 - 0.15, z + 0.45 + 0.95), (x1 - x0, 0.08, 0.08), 1)
        box(bm, ((x0 + x1) / 2, py1 - 0.15, z + 0.45 + 0.15), (x1 - x0, 0.08, 0.08), 1)
        xx = x0 + 0.15
        while xx < x1:
            box(bm, (xx, py1 - 0.15, z + 0.45 + 0.55), (0.05, 0.05, 0.8), 1)
            xx += 0.3
    S.bm_prism_x(bm, hx - HW / 2 + 0.2, hx + HW / 2 - 0.2,
                 [(py0, z + 3.55), (py1 + 0.35, z + 3.2), (py1 + 0.35, z + 3.05), (py0, z + 3.4)], 2)
    S.obj("porch", S.mesh_from_bm("porch", bm, [mt["porch"], mt["trim"], mt["shingle"]]))
    # barometer: brass ring + dial + ticks (no numbers) + needle
    bx, by, bz = BARO
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.34, radius2=0.34, depth=0.07,
                          matrix=Matrix.Translation((bx, by + 0.035, bz)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    for f in bm.faces:
        f.material_index = 0
    nf = len(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.285, radius2=0.285, depth=0.012,
                          matrix=Matrix.Translation((bx, by + 0.072, bz)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    for f in list(bm.faces)[nf:]:
        f.material_index = 1
    for k in range(-6, 7):
        phi = math.radians(k * 20.0)
        mi = 2 if abs(k) < 2 else (3 if k >= 2 else 4)
        rr, ln = 0.225, (0.07 if k % 3 == 0 else 0.045)
        vs = box(bm, (0, 0, 0), (0.012 if mi == 2 else 0.02, 0.01, ln), mi)
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(phi, 3, "Y"))
        bmesh.ops.translate(bm, verts=vs, vec=(bx + rr * math.sin(phi), by + 0.082, bz + rr * math.cos(phi)))
    # arcs: red (stormy, viewer's left = +X) and blue (fair, viewer's right)
    for a0, a1, mi in ((40.0, 120.0, 3), (-120.0, -40.0, 4)):
        for j in range(12):
            phi = math.radians(a0 + (a1 - a0) * (j + 0.5) / 12)
            vs = box(bm, (0, 0, 0), (0.035, 0.008, 0.016), mi)
            bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(phi + math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, verts=vs, vec=(bx + 0.262 * math.sin(phi), by + 0.08, bz + 0.262 * math.cos(phi)))
    S.obj("barometer", S.mesh_from_bm("barometer", bm, [mt["brass"], mt["dial"], mt["tick"], mt["tick_r"],
                                                        mt["tick_b"]]))
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 0.08), (0.016, 0.01, 0.26), 0)
    vs = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.022, radius2=0.0, depth=0.05,
                               matrix=Matrix.Translation((0, 0, 0.23)))["verts"]
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = 0
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.03, radius2=0.03, depth=0.02,
                          matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
    needle = S.obj("needle", S.mesh_from_bm("needle", bm, [mt["tick"]]), (bx, by + 0.095, bz))
    bake(tl, needle, "rotation_euler", lambda t: (0.0, math.radians(st.needle(t)), 0.0))
    empty(ctx, "baro", (bx, by + 0.1, bz))
    # takeaway props: table + phone on charge, chair (strapped on "tie")
    tx, ty = TABLE
    dz = z + 0.45
    bm = bmesh.new()
    box(bm, (tx, ty, dz + 0.68), (0.9, 0.6, 0.05), 0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(bm, (tx + sx * 0.38, ty + sy * 0.24, dz + 0.33), (0.05, 0.05, 0.66), 0)
    S.obj("table", S.mesh_from_bm("table", bm, [mt["wood"]]))
    bm = bmesh.new()
    box(bm, (tx + 0.1, ty + 0.05, dz + 0.712), (0.085, 0.165, 0.012), 0)
    box(bm, (tx + 0.1, ty + 0.05, dz + 0.7185), (0.075, 0.15, 0.002), 1)
    box(bm, (tx + 0.1, ty + 0.01, dz + 0.7195), (0.03, 0.012, 0.002), 2)
    box(bm, (tx + 0.1, ty - 0.12, dz + 0.71), (0.008, 0.18, 0.008), 3)
    box(bm, (tx + 0.1, ty - 0.21, dz + 0.36), (0.008, 0.008, 0.7), 3)
    box(bm, ((tx + 0.1 + 0.2) / 2 + 0.05, FRONT_Y + 0.05, dz + 0.02), (0.25, 0.008, 0.008), 3)
    S.obj("phone", S.mesh_from_bm("phone", bm, [mt["phone"], mt["screen"], mt["batt"], mt["cable"]]))
    cx, cy = CHAIR
    bm = bmesh.new()
    box(bm, (cx, cy, dz + 0.42), (0.62, 0.55, 0.06), 0)
    box(bm, (cx, cy - 0.3, dz + 0.75), (0.62, 0.06, 0.7), 0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(bm, (cx + sx * 0.27, cy + sy * 0.24, dz + 0.21), (0.05, 0.05, 0.42), 0)
        box(bm, (cx + sx * 0.33, cy, dz + 0.62), (0.05, 0.55, 0.05), 0)
    S.obj("chair", S.mesh_from_bm("chair", bm, [mt["chair"]]))
    bm = bmesh.new()
    box(bm, (cx, cy, dz + 0.46), (0.68, 0.06, 0.035), 0)
    box(bm, (cx, cy - 0.33, dz + 0.9), (0.68, 0.035, 0.06), 0)
    box(bm, (cx, (cy + FRONT_Y) / 2 - 0.1, dz + 0.9), (0.06, abs(cy - FRONT_Y) - 0.3, 0.035), 0)
    strap = S.obj("strap", S.mesh_from_bm("strap", bm, [mt["strap"]]))
    show_between(tl, strap, st.c_tie - 0.2)
    # windsock on its pole at the bluff edge
    px, py = SOCK
    bm = bmesh.new()
    box(bm, (px, py, Z0 + 3.3), (0.12, 0.12, 6.6), 0)
    S.obj("sock_pole", S.mesh_from_bm("sock_pole", bm, [mt["white"]]))
    bm = bmesh.new()
    n = 5
    for i in range(n):
        x0, x1 = 3.0 * i / n, 3.0 * (i + 1) / n
        r0, r1 = 0.45 - 0.25 * i / n, 0.45 - 0.25 * (i + 1) / n
        bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=r0, radius2=r1, depth=x1 - x0,
                              matrix=Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    for f in bm.faces:
        f.material_index = int(max(0.0, min(n - 1, f.calc_center_median().x / 3.0 * n))) % 2
    sock = S.obj("sock", S.mesh_from_bm("sock", bm, [mt["sock_o"], mt["sock_w"]], smooth=True), (px, py, Z0 + 6.4))

    def sock_rot(t):
        w = st.wind(t)
        droop = math.radians(80.0 - 78.0 * smooth((w - 0.1) / 0.8))
        fl = math.radians(5.0) * w * math.sin(t * 9.0) + math.radians(3.0) * w * math.sin(t * 13.7)
        return (fl, droop + 0.5 * fl, math.radians(st.az(t)) + 0.6 * fl)
    bake(tl, sock, "rotation_euler", sock_rot)


def build_bluff_town(tl, st, mt, ctx, rng):
    ht = S.house_templates(rng, 12)
    tt = S.tree_templates(rng)
    hp, tp = [], []
    for _ in range(360):
        xx, yy = rng.uniform(-500, 500), rng.uniform(-420, -24)
        if abs(xx - HOUSE[0]) < 32 and yy > -62:
            continue
        (hp if rng.random() < 0.5 else tp).append((xx, yy))
    for o in S.scatter(ht, hp, rng, (0.85, 1.15), prefix="nhouse"):
        o.location.z = gz(o.location.y) - 0.3
        o.rotation_euler.z = rng.choice((0.0, math.pi)) + rng.uniform(-0.15, 0.15)
    trees = S.scatter(tt, tp, rng, (0.8, 1.25), prefix="tree")
    # a few trees near the hero house (they bend in the wind)
    near = [(12.5, -33.0), (16.0, -24.5), (9.0, -40.0), (24.0, -31.0), (-15.0, -12.0)]
    trees += S.scatter(tt[:6], near, rng, (0.9, 1.1), prefix="ntree")
    for o in trees:
        o.location.z = gz(o.location.y) - 0.2
    # far hills inland
    for k in range(9):
        bm = bmesh.new()
        x, y = -2600.0 + k * 650.0 + rng.uniform(-150, 150), rng.uniform(-1800, -1200)
        rx, h = rng.uniform(500, 800), rng.uniform(140, 260)
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                   matrix=Matrix.Translation((x, y, 0.0)) @ Matrix.Diagonal((rx, rx * 0.6, h, 1.0)))
        S.obj("hill%d" % k, S.mesh_from_bm("hill%d" % k, bm, [mt["far"]], smooth=True))
    return [o for o in trees if vlen(vsub((o.location.x, o.location.y, 0.0), (HOUSE[0], HOUSE[1], 0.0))) < 90.0]


def build_pier_and_light(mt, ctx):
    x0, x1 = PIER_X - PIER_W / 2, PIER_X + PIER_W / 2
    bm = bmesh.new()
    box(bm, (PIER_X, (20.0 + PIER_Y1) / 2, DECK_Z - 0.15), (PIER_W, PIER_Y1 - 20.0, 0.3), 0)
    box(bm, (PIER_X, PIER_Y1 + 7.0, DECK_Z - 0.15), (14.0, 14.0, 0.3), 0)
    S.bm_prism_x(bm, x0, x1, [(PIER_Y0, ROAD_Z + 0.1), (20.0, DECK_Z - 0.3), (20.0, DECK_Z), (PIER_Y0, ROAD_Z + 0.3)], 0)
    y = 22.0
    while y < PIER_Y1 + 14.0:
        hw = PIER_W / 2 - 0.35 if y < PIER_Y1 else 6.6
        for xx in (PIER_X - hw, PIER_X + hw):
            cyl(bm, (xx, y, (DECK_Z - 0.3 - 6.0) / 2), 0.25, DECK_Z - 0.3 + 6.0, 1, 10)
        y += 8.0
    for xx in (x0 + 0.1, x1 - 0.1):
        yy = 21.0
        while yy < PIER_Y1:
            box(bm, (xx, yy, DECK_Z + 0.5), (0.1, 0.1, 1.0), 2)
            yy += 3.0
        box(bm, (xx, (21.0 + PIER_Y1) / 2, DECK_Z + 1.0), (0.09, PIER_Y1 - 21.0, 0.08), 2)
    S.obj("pier", S.mesh_from_bm("pier", bm, [mt["wood"], mt["pile"], mt["white"]]))
    # rocky point + lighthouse
    lx, ly = LIGHT
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0,
                               matrix=Matrix.Translation((lx, ly - 15.0, -4.0)) @ Matrix.Diagonal((38.0, 70.0, 11.0, 1.0)))
    r2 = random.Random(9)
    for v in bm.verts:
        v.co.z += r2.uniform(-0.6, 0.6)
    S.obj("point", S.mesh_from_bm("point", bm, [mt["rock"]], smooth=True))
    zb = 6.5
    bm = bmesh.new()
    nb = 6
    for i in range(nb):
        h0, h1 = 18.0 * i / nb, 18.0 * (i + 1) / nb
        r0, r1 = 3.0 - 1.1 * i / nb, 3.0 - 1.1 * (i + 1) / nb
        vs = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r0, radius2=r1, depth=h1 - h0,
                                   matrix=Matrix.Translation((lx, ly, zb + (h0 + h1) / 2)))["verts"]
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = i % 2
    cyl(bm, (lx, ly, zb + 18.2), 2.6, 0.4, 2, 24)
    cyl(bm, (lx, ly, zb + 19.6), 1.4, 2.4, 3, 16)
    vs = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=1.7, radius2=0.2, depth=1.4,
                               matrix=Matrix.Translation((lx, ly, zb + 21.5)))["verts"]
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = 4
    box(bm, (lx - 6.0, ly - 6.0, zb + 1.6), (6.0, 5.0, 3.2), 0)
    S.obj("lighthouse", S.mesh_from_bm("lighthouse", bm, [mt["white"], mt["lh_red"], mt["dark"], mt["lh_lamp"],
                                                          mt["lh_red"]]))


def build_storm(tl, st, mt, ctx):
    rng = random.Random(77)
    sx, sy = SC
    R = R_ST

    def top(r):
        return 1150.0 - 700.0 * min(1.0, r / R)
    root, parts = ST.make_spiral("storm", rng, R, 0.1 * R, top, storm_mat(), groups=5, flat=0.55)
    root.location = (sx, sy, 0.0)
    # grey base under the tops (so from the coast it reads as one huge cloud mass, not floating puffs)
    bl = []
    for i in range(260):
        a = rng.uniform(0, 2 * math.pi)
        r = R * 0.88 * math.sqrt(rng.random())
        s = R * rng.uniform(0.07, 0.11)
        bl.append((r * math.cos(a), r * math.sin(a), rng.uniform(60.0, 330.0) + 330.0 * (1.0 - r / R) ** 0.7, s, 0.8))
    base = ST.puffs("storm_base", bl, storm_base_mat(), parent=root)
    spin0 = 12.0

    def rot(t):
        extra = 28.0 * smoother((t - st.t_p) / max(1.0, st.t_w - st.t_p))
        return (0.0, 0.0, math.radians(spin0 + 0.35 * t + extra))
    bake(tl, root, "rotation_euler", rot)
    n = len(parts)
    for g, o in enumerate(parts):
        def scl(t, g=g):
            k = st.tight(t)
            s = 1.0 - k * (0.05 + 0.05 * g)
            return (s, s, 1.0)

        def loc(t, g=g):
            k = st.tight(t)
            return (0.0, 0.0, -k * (260.0 if g == 0 else (110.0 if g == 1 else 0.0)))
        bake(tl, o, "scale", scl, step=2)
        bake(tl, o, "location", loc, step=2)
    empty(ctx, "eye", (sx, sy, 700.0))
    empty(ctx, "storm", (sx, sy - 600.0, 900.0))
    # low grey scud clouds drifting in over the coast (the "grey sky"); hidden in the bright frame-1 state
    lo = []
    for k in range(16):
        cx, cy = rng.uniform(-900, 1600), rng.uniform(1300, 2900)
        for j in range(6):
            r = rng.uniform(40, 75)
            lo.append((cx + rng.uniform(-80, 80), cy + rng.uniform(-50, 50), 330.0 + rng.uniform(-15, 30), r, 0.42))
    scud = puffs("scud", lo, TD.cloud_mat("cy_scud", "a7afba", 0.3))
    bake(tl, scud, "location", lambda t: (-2.0 * t, -9.0 * t, 0.0), step=2)
    bake(tl, scud, "scale", lambda t: (max(0.001, st.scud(t)),) * 3, step=2)


def flow_arrows(tl, st, ctx, name, mat, path, n, period, win, length, width, cam_fn, phase0=0.0, step=1):
    """n flat arrows travelling along path(u) (u 0..1, one pass = `period` s), turned to face the camera every
    frame. They scale to nothing at both ends of a pass and outside the window (so loop jumps are never seen)."""
    hl, w, hw = length * 0.42, width * 0.5, width * 1.15
    pts2 = [(-length / 2, -w), (length / 2 - hl, -w), (length / 2 - hl, -hw), (length / 2, 0.0),
            (length / 2 - hl, hw), (length / 2 - hl, w), (-length / 2, w)]
    bm = bmesh.new()
    vs = [bm.verts.new((a, b, 0.0)) for a, b in pts2]
    bm.faces.new(vs)
    me = S.mesh_from_bm(name, bm, [mat])
    t0, t1 = win
    objs = []
    for i in range(n):
        o = S.obj("%s%d" % (name, i), me, path(0.0))
        o.visible_shadow = False
        o.rotation_mode = "QUATERNION"
        ph = (phase0 + i / float(n)) % 1.0

        def u_of(t, ph=ph):
            return (ph + max(0.0, t - t0) / period) % 1.0

        def pos(t, u_of=u_of):
            return path(u_of(t))

        def scl(t, u_of=u_of):
            u = u_of(t)
            k = smooth((min(u, 1.0 - u) - 0.02) / 0.1) * smooth((t - t0) / 0.5) * smooth((t1 - t) / 0.5)
            k = max(0.001, k)
            return (k, k, k)
        prev = [None]

        def quat(t, u_of=u_of, prev=prev):
            u = u_of(t)
            p0 = path(max(0.0, u - 0.004))
            p1 = path(min(1.0, u + 0.004))
            tan = vnorm(vsub(p1, p0))
            p = path(u)
            nrm = vnorm(vsub(cam_fn(t), p))
            d = vsub(tan, vmul(nrm, vdot(tan, nrm)))
            if vlen(d) < 1e-4:
                d = (1.0, 0.0, 0.0)
            d = vnorm(d)
            up = vcross(nrm, d)
            mtx = Matrix(((d[0], up[0], nrm[0]), (d[1], up[1], nrm[1]), (d[2], up[2], nrm[2])))
            q = mtx.to_quaternion()
            if prev[0] is not None and q.dot(prev[0]) < 0:
                q.negate()
            prev[0] = q
            return (q.w, q.x, q.y, q.z)
        bake(tl, o, "location", pos, step=step)
        bake(tl, o, "scale", scl, step=step)
        bake(tl, o, "rotation_quaternion", quat, step=step)
        objs.append(o)
    return objs


def polyline(pts):
    seg = [vlen(vsub(pts[i + 1], pts[i])) for i in range(len(pts) - 1)]
    tot = sum(seg)

    def f(u):
        s = max(0.0, min(1.0, u)) * tot
        for i, l in enumerate(seg):
            if s <= l or i == len(seg) - 1:
                return vlerp(pts[i], pts[i + 1], min(1.0, s / l if l > 0 else 1.0))
            s -= l
        return pts[-1]
    return f


def spiral_path(start, mid, a0, turns, r0, r1, z0, z1):
    """Straight run start -> mid, then a counter-clockwise rising spiral around the storm centre."""
    sx, sy = SC
    pts = [start, mid]
    for i in range(1, 25):
        u = i / 24.0
        a = a0 + 2 * math.pi * turns * u
        r = r0 + (r1 - r0) * u
        pts.append((sx + r * math.cos(a), sy + r * math.sin(a), z0 + (z1 - z0) * u))
    return polyline(pts)


def build_air(tl, st, mt, ctx, cam_fn):
    sx, sy = SC
    # cold air from the land (south-west), warm moist air from the ocean (east); both wind up into the storm
    a_c = math.atan2(-1900.0, -1400.0)
    cold = spiral_path((sx - 3200.0, sy - 3300.0, 500.0), (sx - 1400.0, sy - 1900.0, 820.0), a_c, 0.75, 2360.0, 550.0,
                       900.0, 1900.0)
    a_w = math.atan2(-1700.0, 1300.0)
    warm = spiral_path((sx + 2900.0, sy - 2700.0, 450.0), (sx + 1300.0, sy - 1700.0, 800.0), a_w, 0.75, 2140.0, 520.0,
                       880.0, 1850.0)
    flow_arrows(tl, st, ctx, "cold", mt["cold"], cold, 6, 7.0, st.win_cold, 380.0, 130.0, cam_fn)
    flow_arrows(tl, st, ctx, "warm", mt["warmA"], warm, 6, 7.0, st.win_warm, 380.0, 130.0, cam_fn, phase0=0.08)
    empty(ctx, "cold", cold(0.12))
    empty(ctx, "warm", warm(0.12))
    # jet stream: glowing translucent ribbon high above, chevrons racing along it
    jp = [(sx - 4200.0, sy - 1500.0, 2150.0), (sx - 1500.0, sy - 500.0, 2300.0), (sx + 1200.0, sy + 200.0, 2300.0),
          (sx + 4200.0, sy + 600.0, 2200.0)]
    jet = polyline(jp)
    bm = bmesh.new()
    prev = None
    for i in range(61):
        p = jet(i / 60.0)
        q = jet(min(1.0, i / 60.0 + 0.01))
        d = vnorm(vsub(q, p)) if i < 60 else vnorm(vsub(p, jet(i / 60.0 - 0.01)))
        lat = vnorm((-d[1], d[0], 0.0))
        lat = (lat[0], lat[1], 0.35)
        cur = (bm.verts.new(vadd(p, vmul(lat, 260.0))), bm.verts.new(vsub(p, vmul(lat, 260.0))))
        if prev:
            bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
        prev = cur
    rib = S.obj("jet_ribbon", S.mesh_from_bm("jet_ribbon", bm, [ribbon_mat()]))
    rib.visible_shadow = False
    j0, j1 = st.win_jet

    show_between(tl, rib, j0, j1)
    flow_arrows(tl, st, ctx, "jetc", mt["windw"], jet, 7, 3.2, st.win_jet, 520.0, 170.0, cam_fn)
    empty(ctx, "jet", jet(0.36))
    # air leaving the top: arrows rising from the storm top into the jet
    up = polyline([(sx - 100.0, sy - 100.0, 1100.0), (sx - 150.0, sy - 120.0, 1700.0), (sx + 300.0, sy, 2250.0),
                   (sx + 1300.0, sy + 250.0, 2300.0)])
    flow_arrows(tl, st, ctx, "upa", mt["jet"], up, 4, 3.0, st.win_up, 260.0, 90.0, cam_fn)
    # wind at the coast: white arrows onshore (sea -> land), later blue arrows land -> sea
    def onshore(off):
        return polyline([(off, 70.0, 5.0), (off - 4.0, 20.0, 5.5), (off - 9.0, -10.0, 9.0), (off - 14.0, -45.0, 12.0)])

    def offshore(off):
        return polyline([(off, -60.0, 14.0), (off + 3.0, -25.0, 15.6), (off + 6.0, 10.0, 8.0), (off + 10.0, 60.0, 5.0)])
    for k, off in enumerate((-20.0, -6.0, 8.0)):
        flow_arrows(tl, st, ctx, "wind%d_" % k, mt["windw"], onshore(off), 3, 4.0, st.win_wind, 5.0, 1.7, cam_fn,
                    phase0=0.13 * k)
    for k, off in enumerate((-12.0, 4.0, 18.0)):
        flow_arrows(tl, st, ctx, "back%d_" % k, mt["windb"], offshore(off), 3, 4.5, st.win_back, 5.0, 1.7, cam_fn,
                    phase0=0.17 * k)


def build_sign(tl, st, mt, ctx):
    sx, sy = SIGN
    rz = math.radians(33.0)
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 1.2), (0.1, 0.1, 2.4), 0)
    box(bm, (0.0, 0.05, 2.45), (1.3, 0.06, 0.9), 0)
    sign = S.obj("sign", S.mesh_from_bm("sign", bm, [mt["sign_dark"]]), (sx, sy, ROAD_Z + 0.12), rot=(0, 0, rz))
    bm = bmesh.new()
    box(bm, (0.0, -0.0, 2.45), (1.18, 0.02, 0.78), 0)
    lit = S.obj("sign_lit", S.mesh_from_bm("sign_lit", bm, [mt["sign_on"]]), (sx, sy, ROAD_Z + 0.12), rot=(0, 0, rz))
    show_between(tl, lit, st.c_stay - 0.3)
    empty(ctx, "sign", (0.0, 0.0, 2.95), parent=sign)
    # shallow sheet of seawater on the road (from the surge on)
    sm, sw = TD.sheet_mat()
    sheet = S.plane_obj("road_water", 34.0, 6.2, (sx + 2.0, sum(ROAD_Y) / 2, ROAD_Z + 0.14), sm)
    sheet.visible_shadow = False
    show_between(tl, sheet, st.flood_on, st.c_bec)
    bake_sock(tl, sw, lambda t: t * 0.6)


def build_precip(tl, st, cam):
    """Rain + snow: 3 + 2 camera-facing planes parented to the camera; streaks scroll in the shader."""
    layers = []
    for kind, depths in (("rain", (2.5, 5.0, 9.0)), ("snow", (2.2, 5.5))):
        for j, d in enumerate(depths):
            m, mp, inten = precip_mat("cy_%s%d" % (kind, j), kind)
            sz = 2.4 * d
            o = S.plane_obj("%s%d" % (kind, j), sz, sz, (0.0, 0.0, 0.0), m)
            o.parent = cam
            o.location = (0.0, 0.0, -d)
            o.visible_shadow = False
            try:
                o.visible_diffuse = o.visible_glossy = False
            except Exception:
                pass
            if kind == "rain":
                cw, ch, v = 0.03 * d, 0.55 * d, 10.0
                mp.inputs["Scale"].default_value = (1.0 / cw, 1.0 / ch, 1.0)
                bake_sock(tl, mp.inputs["Location"], lambda t, ch=ch, v=v, j=j: (0.0, v * t / ch, j * 3.1), step=1)
                bake_sock(tl, inten, lambda t, j=j: st.rain(t) * (1.0 - 0.25 * j), step=2)
                bake(tl, o, "rotation_euler", lambda t: (0.0, 0.0, math.radians(st.roll(t))), step=2)
            else:
                cw, v = 0.05 * d, 1.4
                mp.inputs["Scale"].default_value = (1.0 / cw, 1.0 / cw, 1.0)
                bake_sock(tl, mp.inputs["Location"],
                          lambda t, cw=cw, v=v, j=j: (0.35 * math.sin(0.7 * t + j) , v * t / cw, j * 2.7), step=1)
                bake_sock(tl, inten, lambda t, j=j: st.snow(t) * (1.0 - 0.2 * j), step=2)
                bake(tl, o, "rotation_euler", lambda t: (0.0, 0.0, math.radians(0.35 * st.roll(t))), step=2)
            layers.append(o)
    return layers


def fog_nodes():
    """The distance-fog multiply node of every hazed material (base density stored) for per-frame keying."""
    out = []
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        for nd in m.node_tree.nodes:
            if nd.type == "MATH" and nd.operation == "MULTIPLY" and nd.inputs[0].is_linked:
                src = nd.inputs[0].links[0].from_node
                if src.type == "MATH" and src.operation == "MAXIMUM" and src.inputs[0].is_linked:
                    s2 = src.inputs[0].links[0].from_node
                    if s2.type == "MATH" and s2.operation == "SUBTRACT" and s2.inputs[0].is_linked and \
                            s2.inputs[0].links[0].from_node.type == "CAMERA":
                        out.append((nd.inputs[1], nd.inputs[1].default_value))
    return out


# ================================================================ BUILDER
def b_bomb_oneshot(ctx, p):
    tl = TL(ctx)
    st = Story(tl)
    sc = ctx.scene
    rng = random.Random(p.get("seed", 28))
    S.daylight(ctx, p.get("sun_az", -35.0), 40.0)
    L.fog(0.0002, S.HAZE, start=250.0)
    C.horizon_haze(sc, lo=-0.01, hi=0.05)
    mt = mats()
    spots = route(tl, st)
    T_end = tl.t_of_G(tl.total)

    def cam_fn(t):
        return camera_at(spots, t, T_end)[0]
    build_land(mt)
    tufts = build_dunes(tl, st, mt, rng)
    build_sea(tl, st, mt)
    build_house(tl, st, mt, ctx)
    trees = build_bluff_town(tl, st, mt, ctx, rng)
    build_pier_and_light(mt, ctx)
    build_storm(tl, st, mt, ctx)
    build_air(tl, st, mt, ctx, cam_fn)
    build_sign(tl, st, mt, ctx)
    brng = random.Random(5)
    bend(tl, st, trees, 7.0, 2.1, brng)
    bend(tl, st, tufts, 34.0, 4.5, brng, near=((10.0, 11.0, 0.0), 140.0))
    # the camera: one continuous route on the global timeline
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=30)
    cam.data.clip_end = 40000.0
    bake(tl, cam, "location", lambda t: camera_at(spots, t, T_end)[0])
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    bake(tl, cam.data, "clip_start",
         lambda t: max(0.05, min(25.0, 0.004 * (camera_at(spots, t, T_end)[0][2] - 8.0))))
    build_precip(tl, st, cam)
    # thinner distance haze when the camera is high (top-down view must stay crisp, not washed out)
    fn = fog_nodes()
    for sock, base in fn:
        bake_sock(tl, sock, lambda t, base=base: base / (1.0 + max(0.0, camera_at(spots, t, T_end)[0][2] - 20.0) / 350.0),
                  step=3)
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 cyclone] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 cyclone] beat %d (%s): global frames %d-%d, fog nodes %d" % (
        tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1, tl.off[tl.k] + tl.n[tl.k], len(fn)))


S.V2_BUILDERS.update({"bomb_oneshot": b_bomb_oneshot})

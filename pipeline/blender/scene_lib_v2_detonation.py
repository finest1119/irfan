"""v2 one-shot prairie munitions-site builder ("controlled detonation", WJH 28 Nov 2026 #2, "minute by minute").
Registers into scene_lib_v2.V2_BUILDERS as `detonation_oneshot`.

Same pattern as scene_lib_v2_cyclone.py / scene_lib_v2_tides.py: ONE builder for every beat. Each beat builds the
identical bright prairie world and keys ALL animation (camera, walls, foam, tanks, puff, props) on the GLOBAL episode
timeline (WORKDIR/audio/timings.json + captions.json), so the video is one continuous camera: slow drifts at each spot,
fast eased whips (EEVEE motion blur) between spots, a continuous push through the scene (minute by minute) and a
backout that ends on the frame-1 view (loop).

World (north = +Y; cameras mostly look north): a sunny golden Midwest prairie, a gravel road along y = ROAD_Y, a row
of eight grass-covered earth-mounded storage bunkers (concrete headwalls, steel doors) north of the road; two of them
sit inside a ring of tall sand-coloured barrier wall sections; big blue water tanks inside the ring, white foam blocks
stacked on the two mounds; windbreak tree lines, farm silos and a generic water tower far away; an air-monitor mast in
the field south of the road; an old rusty shell shape half-hidden in the grass by the road (takeaway).
Inside the open bunker: a plain drum on a pallet (pale needle crystals grow in it), a forklift, and an ILLUSTRATION
cutaway of a detonator on a stand (small glowing primary pellet, bigger main charge, a spark hops between them).
The blast is a soft stylised white dust/foam puff (icosphere puffs, fading alpha) after a soft glow under the ground:
no fire, no debris, no people. No text, insignia or signage in 3D (all text is 2D overlay).

Beats it expects: hook, question, clock_march, what_it_is, the_trap, clock_days_before, clock_0900, clock_0915,
takeaway, outro. Missing cue words fall back to a fraction of their beat.
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
from scene_lib_v2_winter import set_keys

TL, bake, bake_sock, curve, smooth, smoother = TD.TL, TD.bake, TD.bake_sock, TD.curve, TD.smooth, TD.smoother
vadd, vsub, vmul, vlen, vnorm, vlerp = TD.vadd, TD.vsub, TD.vmul, TD.vlen, TD.vnorm, TD.vlerp
lin, camera_at, show_between, box, cyl, empty = TD.lin, TD.camera_at, TD.show_between, TD.box, TD.cyl, TD.empty

# ---------------------------------------------------------------- layout
EXT = 9000.0
ROAD_Y, ROAD_W = -22.0, 7.0
BX = [-105.0, -75.0, -45.0, -15.0, 15.0, 45.0, 75.0, 105.0]    # bunker centres (x)
HEAD_Y = 8.0                    # headwall front face (bunkers run north from here)
B_LEN, B_R = 22.0, 4.6          # vault length, arch radius
DOOR_W, DOOR_H = 3.6, 3.4
DRUM_BX = 15.0                  # the bunker the camera enters
RC = (0.0, 20.0)                # barrier ring centre
R_WALL, WALL_H, N_WALL = 32.0, 6.2, 64
DRUM = (15.0, 19.0)
STAND = (12.6, 20.6)            # detonator cutaway
FORK = (17.4, 13.2)
MAST = (70.0, -46.0)
SHELL = (-40.0, -27.4)
TANK_ANG = [246.0, 258.0, 270.0, 282.0, 294.0, 312.0]
R_TANK = 24.0

P1 = ((60.0, -80.0, 18.0), (0.0, 18.0, 8.0), 30.0)      # frame-1 view (loc, target, lens); the backout ends here

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def ease(u):
    return smoother(u)


# ================================================================ story curves (global seconds)
class Story:
    def __init__(self, tl):
        c, b0, b1 = tl.cue, tl.bstart, tl.bend
        self.T = T = tl.T
        self.t_q, self.t_m, self.t_w = b0("question"), b0("clock_march"), b0("what_it_is")
        self.t_tr, self.t_d, self.t_9 = b0("the_trap"), b0("clock_days_before"), b0("clock_0900")
        self.t_915, self.t_k, self.t_o = b0("clock_0915"), b0("takeaway"), b0("outro")
        self.c_follow = c("question", "follow", 0.6)
        self.c_lead = c("clock_march", "lead", 0.45)
        self.c_cryst = c("clock_march", "crystal", 0.8)
        self.c_prim = c("what_it_is", "primary", 0.08)
        self.c_set = c("what_it_is", "set", 0.3)
        self.c_big = c("what_it_is", "bigger", 0.38)
        self.c_built = c("what_it_is", "built", 0.5)
        self.c_crys2 = c("what_it_is", "crystals", 0.6)
        self.c_touchy = c("the_trap", "touchy", 0.1)
        self.c_carry = c("the_trap", "carry", 0.45)
        self.c_destroy = c("the_trap", "destroy", 0.7)
        self.c_barr = c("clock_days_before", "barriers", 0.3)
        self.c_foam = c("clock_days_before", "foam", 0.5)
        self.c_tanks = c("clock_days_before", "tanks", 0.65)
        self.c_det = c("clock_0900", "detonation", 0.3)
        self.c_down = c("clock_0900", "down", 0.75)
        self.c_more = c("clock_0915", "more", 0.55)
        self.c_soil = c("clock_0915", "soil", 0.8)
        self.c_shell = c("takeaway", "shell", 0.25)
        self.c_back = c("takeaway", "back", 0.8)
        self.c_bec = c("outro", "because", 0.6)
        # rewind (question) and build-up (days before): walls / foam / tanks 0..1 (staggered per piece)
        self.rw0, self.rw1 = self.t_q + 0.3, min(self.c_follow + 0.6, self.t_m - 0.3)
        self.wall_win = (self.c_barr - 0.8, self.c_barr + 3.2)
        self.foam_win = (self.c_foam - 0.4, self.c_foam + 2.6)
        self.tank_win = (self.c_tanks + 0.35, self.c_tanks + 2.9)
        # puff: (size 0..1, alpha 0..1). Frame-1 state = mid-rise (the outro re-forms exactly this state)
        self.puff_s = curve([(0.0, 0.62), (b1("hook"), 0.86), (self.rw0, 0.86), (self.rw0 + 1.6, 0.02),
                             (self.c_det, 0.02), (self.c_det + 0.25, 0.08), (self.c_det + 4.5, 0.86),
                             (self.t_915 + 2.0, 1.15), (self.t_k, 1.35), (self.c_bec - 0.4, 1.35),
                             (self.c_bec - 0.3, 0.30), (T, 0.62)])
        self.puff_a = curve([(0.0, 0.92), (self.rw0 + 0.6, 0.92), (self.rw0 + 1.6, 0.0), (self.c_det + 0.15, 0.0),
                             (self.c_det + 0.6, 0.95), (self.t_915, 0.85), (self.c_more, 0.45), (self.t_k + 1.5, 0.0),
                             (self.c_bec - 0.3, 0.0), (self.c_bec + 0.8, 0.85), (T, 0.92)])
        self.flash = curve([(self.c_det - 0.05, 0.0), (self.c_det + 0.12, 1.0), (self.c_det + 0.9, 0.0)])


def built(st, t, win, k=0.0):
    """0..1 'built' state of a staggered piece (k in 0..1 = its place in the sequence)."""
    a, b = win
    span = (b - a) * 0.55
    up = smooth((t - (a + k * (b - a - span))) / span)
    # rewound (question beat): everything sinks/vanishes in reverse order before March
    r0, r1 = st.rw0, st.rw1
    rspan = (r1 - r0) * 0.6
    down = 1.0 - smooth((t - (r0 + (1.0 - k) * (r1 - r0 - rspan))) / rspan)
    if t < st.t_m:
        return down
    return up


# ================================================================ camera route
def route(tl, st):
    c, b0 = tl.cue, tl.bstart
    dx = DRUM_BX
    spots = [
        # hook: frame-1 wide view: the bunker row, the barrier ring, tanks, the soft puff rising (hero 1)
        (0.0, 0.0, lin(P1, ((55.0, -73.5, 16.8), (0.0, 18.0, 8.0), 31.0)), []),
        # question: start the push towards the bunkers while everything rewinds
        (b0("question") + 0.1, 0.9, lin(((44.0, -58.0, 13.0), (8.0, 14.0, 3.5), 28.0),
                                        ((40.0, -52.0, 11.5), (9.0, 14.0, 3.2), 28.5)), []),
        # clock_march: the bunker door (walls gone; it is March)
        (b0("clock_march") + 0.1, 0.9, lin(((dx + 0.6, -12.0, 2.9), (dx, 20.0, 2.0), 26.0),
                                           ((dx + 0.3, -6.5, 2.6), (dx, 20.0, 1.9), 26.5)), []),
        # ... through the door to the drum ("lead azide")
        (st.c_lead - 0.25, 0.9, lin(((dx + 1.5, 14.0, 2.35), (DRUM[0], DRUM[1], 0.95), 30.0),
                                    ((dx + 1.25, 14.7, 2.3), (DRUM[0], DRUM[1], 0.95), 31.0)),
         [(dx + 0.4, 3.0, 2.3), (dx + 0.6, 10.0, 2.2)]),
        # what_it_is: the detonator cutaway on its stand (illustration)
        (b0("what_it_is") + 0.2, 0.8, lin(((STAND[0] + 4.1, STAND[1] + 0.7, 2.35), (STAND[0], STAND[1] + 0.1, 1.15), 21.0),
                                          ((STAND[0] + 3.8, STAND[1] + 0.65, 2.3), (STAND[0], STAND[1] + 0.1, 1.15), 21.5)),
         []),
        # ... crystals: back to the drum, closer
        (st.c_crys2 - 0.2, 0.8, lin(((DRUM[0] + 0.9, DRUM[1] - 2.6, 2.2), (DRUM[0], DRUM[1], 0.9), 32.0),
                                    ((DRUM[0] + 0.75, DRUM[1] - 2.3, 2.15), (DRUM[0], DRUM[1], 0.9), 33.0)), []),
        # the_trap: wider inside: the forklift and the drum ("don't move it")
        (b0("the_trap") + 0.2, 0.8, lin(((dx - 2.0, 9.0, 2.9), (DRUM[0] + 1.2, 15.5, 0.8), 21.0),
                                        ((dx - 1.8, 9.4, 2.85), (DRUM[0] + 1.2, 15.5, 0.8), 21.5)), []),
        # ... pull back out through the door ("destroy them where they sit")
        (st.c_destroy - 0.2, 1.0, lin(((dx + 0.4, -6.0, 2.6), (dx, 16.0, 1.8), 26.0),
                                      ((dx + 0.6, -10.0, 2.9), (dx, 16.0, 1.8), 26.0)),
         [(dx - 0.6, 8.6, 2.5), (dx + 0.2, 4.0, 2.4)]),
        # days before: low inside the ring, along the rising wall and the row of blue tanks (hero 2)
        (b0("clock_days_before") + 0.2, 1.0, lin(((-30.0, -34.0, 15.0), (4.0, 10.0, 3.0), 24.0),
                                                 ((-28.6, -32.4, 14.6), (4.0, 10.0, 3.0), 24.5)),
         [(2.0, -26.0, 8.0)]),
        # ... low along the towering wall and the row of blue tanks as they fill (hero 2)
        (st.c_tanks - 0.25, 0.8, lin((cor(224.0, 30.0, 1.9), cor(258.0, 29.6, 3.6), 19.0),
                                     (cor(226.5, 30.0, 1.95), cor(260.5, 29.6, 3.7), 19.5)), []),
        # 9:00: rise above the ring: glow, thump, the puff lifts (stylised)
        (b0("clock_0900") + 0.1, 1.0, lin(((40.0, -42.0, 52.0), (0.0, 20.0, 6.0), 28.0),
                                          ((38.0, -40.0, 56.0), (0.0, 20.0, 8.0), 28.0)), [(-10.0, -10.0, 18.0)]),
        # 9:15: across the field to the air-monitor mast, the ring + thinning puff behind
        (b0("clock_0915") + 0.15, 1.0, lin(((MAST[0] + 6.4, MAST[1] - 6.2, 1.9), (MAST[0] - 2.0, MAST[1] + 2.0, 3.1), 30.0),
                                           ((MAST[0] + 5.9, MAST[1] - 5.7, 1.95), (MAST[0] - 2.0, MAST[1] + 2.0, 3.1), 30.5)),
         [(52.0, -46.0, 30.0)]),
        # ... "more than an hour later": wider from the field
        (st.c_more - 0.2, 0.8, lin(((MAST[0] + 6.0, MAST[1] - 22.0, 8.0), (4.0, 14.0, 7.0), 28.0),
                                   ((MAST[0] + 4.5, MAST[1] - 21.0, 8.4), (4.0, 14.0, 7.0), 28.5)), []),
        # takeaway: by the gravel road, the old shell in the grass
        (b0("takeaway") + 0.15, 1.0, lin(((SHELL[0] + 1.7, SHELL[1] - 1.6, 0.95), (SHELL[0], SHELL[1], 0.12), 32.0),
                                         ((SHELL[0] + 1.55, SHELL[1] - 1.45, 0.9), (SHELL[0], SHELL[1], 0.12), 32.5)),
         [(20.0, -40.0, 12.0)]),
        # ... "back away": the camera backs off too
        (st.c_back - 0.2, 0.8, lin(((SHELL[0] + 6.5, SHELL[1] - 7.0, 2.6), (SHELL[0], SHELL[1], 0.3), 28.0),
                                   ((SHELL[0] + 7.2, SHELL[1] - 7.8, 2.8), (SHELL[0], SHELL[1], 0.3), 28.0)), []),
        # outro: up over the road towards the ring
        (b0("outro") + 0.15, 1.0, lin(((34.0, -64.0, 13.0), (0.0, 16.0, 7.0), 29.0),
                                      ((38.0, -70.0, 15.0), (0.0, 16.0, 7.5), 29.5)), [(-14.0, -38.0, 6.0)]),
        # ... backout to the frame-1 view (loop)
        (st.c_bec - 0.2, 0.4, lin(((38.0, -70.0, 15.0), (0.0, 16.0, 7.5), 29.5), P1, ease=True), []),
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


def cor(deg, r, z):
    a = math.radians(deg)
    return (RC[0] + r * math.cos(a), RC[1] + r * math.sin(a), z)


def shake(st, t):
    """Small decaying ground thump at the detonation (continuous, no jump)."""
    d = t - st.c_det - 0.1
    if d < 0.0 or d > 1.2:
        return (0.0, 0.0, 0.0)
    a = 0.35 * math.exp(-d * 4.0) * math.sin(d * 2 * math.pi * 7.0)
    return (a * 0.4, 0.0, a)


# ================================================================ materials
def puff_mat():
    """Soft white dust/foam: facing-ratio rim fade + noise; Value node = overall alpha (baked)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("dt_puff")
        m.surface_render_method = "DITHERED"
        p.inputs["Base Color"].default_value = hexc("f3efe6")
        p.inputs["Emission Color"].default_value = hexc("fbf8f1")
        p.inputs["Emission Strength"].default_value = 0.35
        p.inputs["Roughness"].default_value = 1.0
        p.inputs["Specular IOR Level"].default_value = 0.0
        lw = N.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        Lk.new(lw.outputs["Facing"], inv.inputs[1])
        pw = N.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = 1.5
        Lk.new(inv.outputs[0], pw.inputs[0])
        val = N.new("ShaderNodeValue")
        val.outputs[0].default_value = 1.0
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 0.18
        nz.inputs["Detail"].default_value = 6.0
        nz.inputs["Roughness"].default_value = 0.6
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.3
        mr.inputs["From Max"].default_value = 0.65
        mr.inputs["To Min"].default_value = 0.25
        mr.inputs["To Max"].default_value = 1.3
        Lk.new(nz.outputs["Fac"], mr.inputs["Value"])
        m1 = N.new("ShaderNodeMath")
        m1.operation = "MULTIPLY"
        Lk.new(pw.outputs[0], m1.inputs[0])
        Lk.new(mr.outputs["Result"], m1.inputs[1])
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.use_clamp = True
        Lk.new(m1.outputs[0], mul.inputs[0])
        Lk.new(val.outputs[0], mul.inputs[1])
        Lk.new(mul.outputs[0], p.inputs["Alpha"])
        S._finish(m, p.outputs[0], haze=False)
        return m, val.outputs[0]
    return _m("puff", mk)


def flash_mat():
    def mk():
        m = bpy.data.materials.new("dt_flash")
        m.surface_render_method = "BLENDED"
        N, Lk = m.node_tree.nodes, m.node_tree.links
        for n in list(N):
            if n.type != "OUTPUT_MATERIAL":
                N.remove(n)
        tc = N.new("ShaderNodeTexCoord")
        grad = N.new("ShaderNodeTexGradient")
        grad.gradient_type = "SPHERICAL"
        Lk.new(tc.outputs["Object"], grad.inputs["Vector"])
        val = N.new("ShaderNodeValue")
        val.outputs[0].default_value = 0.0
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.use_clamp = True
        Lk.new(grad.outputs["Fac"], mul.inputs[0])
        Lk.new(val.outputs[0], mul.inputs[1])
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = hexc("fff1d2")
        em.inputs["Strength"].default_value = 4.0
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        Lk.new(mul.outputs[0], mix.inputs[0])
        Lk.new(tr.outputs[0], mix.inputs[1])
        Lk.new(em.outputs[0], mix.inputs[2])
        Lk.new(mix.outputs[0], N.get("Material Output").inputs["Surface"])
        return m, val.outputs[0]
    return _m("flash", mk)


def mats():
    def mk():
        return {
            "prairie": S.lawn_mat("dt_prairie", hexc("c7a862"), stripes=True),
            "lawn": S.lawn_mat("dt_lawn", hexc("7f9a4e"), stripes=False),
            "mound": S.pbr("dt_mound", hexc("86a052"), 0.95, var=0.14, var_scale=0.4, bump=0.1),
            "far": C.far_ground_mat("dt_far", hexc("a99a62")),
            "field": [S.pbr("dt_field%d" % i, hexc(c), 0.95, var=0.12, var_scale=0.02)
                      for i, c in enumerate(("d1b56c", "b9a35c", "8f9a52", "cdb77e", "a8924f"))],
            "gravel": S.pbr("dt_gravel", hexc("b5aa98"), 0.95, var=0.12, var_scale=1.5, bump=0.18),
            "concrete": S.pbr("dt_concrete", hexc("c9c5bc"), 0.85, var=0.08, var_scale=0.5, bump=0.06),
            "vault": S.pbr("dt_vault", hexc("d8d5cd"), 0.8, var=0.06, var_scale=0.6, bump=0.05),
            "floor": S.pbr("dt_floor", hexc("bdb8ad"), 0.7, var=0.08, var_scale=0.9, bump=0.03),
            "door": S.pbr("dt_door", hexc("6d7a6a"), 0.5, metal=0.6, var=0.05, var_scale=1.2),
            "wall": S.pbr("dt_wall", hexc("d6c29a"), 0.9, var=0.09, var_scale=0.35, bump=0.12),
            "wall_dk": S.pbr("dt_wall_dk", hexc("b9a47c"), 0.9, var=0.08, var_scale=0.35, bump=0.1),
            "tank": S.pbr("dt_tank", hexc("3d93e6"), 0.45, var=0.04, var_scale=0.8),
            "tank_top": S.pbr("dt_tank_top", hexc("5c9de0"), 0.5, var=0.03),
            "foam": S.pbr("dt_foam", hexc("f4f3ee"), 0.85, var=0.05, var_scale=3.0, bump=0.08),
            "drum": S.pbr("dt_drum", hexc("5d6f55"), 0.55, metal=0.5, var=0.05, var_scale=2.0),
            "drum_in": S.pbr("dt_drum_in", hexc("e9e6dc"), 0.9, var=0.05, var_scale=6.0, bump=0.1),
            "crystal": S.emis("dt_crystal", hexc("eaf6ff"), 0.9),
            "pallet": S.pbr("dt_pallet", hexc("a8875c"), 0.8, var=0.12, var_scale=3.0),
            "fork_y": S.pbr("dt_fork_y", hexc("f0b81c"), 0.5, var=0.03),
            "dark": S.pbr("dt_dark", hexc("2a2d31"), 0.6, var=0.02),
            "steel": S.pbr("dt_steel", hexc("aeb4bb"), 0.3, metal=0.9, var=0.02),
            "white": S.pbr("dt_white", hexc("f1f2f3"), 0.45, var=0.02),
            "stand": S.pbr("dt_stand", hexc("e8e9ea"), 0.4, var=0.0),
            "tube": S.pbr("dt_tube", hexc("b8c1c9"), 0.3, metal=0.85, var=0.02),
            "tube_in": S.pbr("dt_tube_in", hexc("7b8794"), 0.5, metal=0.3, var=0.02),
            "primary": S.emis("dt_primary", hexc("ff5a2a"), 2.2),
            "main": S.pbr("dt_main", hexc("8fa9c6"), 0.6, var=0.03),
            "main_glow": S.emis("dt_main_glow", hexc("ffb347"), 2.5),
            "spark": S.emis("dt_spark", hexc("fff0b0"), 12.0),
            "edge": S.emis("dt_edge", hexc("47e0d0"), 2.0),
            "lamp": S.emis("dt_lamp", hexc("fff6e0"), 6.0),
            "ring_r": S.emis("dt_ring_r", hexc("ff3b30"), 5.0),
            "arrow": S.emis("dt_arrow", hexc("ff4a3d"), 3.5),
            "rust": S.pbr("dt_rust", hexc("7a4a2a"), 0.9, var=0.25, var_scale=6.0, bump=0.25),
            "silo": S.pbr("dt_silo", hexc("c9ccd0"), 0.4, metal=0.6, var=0.04),
            "barn": S.pbr("dt_barn", hexc("9e3b2e"), 0.8, var=0.08),
            "roof": S.pbr("dt_roof", hexc("8d9096"), 0.6, metal=0.4, var=0.06),
            "wt": S.pbr("dt_wt", hexc("dfe6ec"), 0.45, var=0.02),
            "pole": S.pbr("dt_pole", hexc("7a6450"), 0.85, var=0.1),
            "panel": S.pbr("dt_panel", hexc("1d3557"), 0.15, metal=0.3, var=0.0),
            "grass": S.pbr("dt_grass", hexc("b49a55"), 0.9, var=0.18, var_scale=2.0),
        }
    return _m("mats", mk)


# ================================================================ helpers
def obj(name, bm, mlist, loc=(0, 0, 0), smooth_=False, parent=None):
    return S.obj(name, S.mesh_from_bm(name, bm, mlist, smooth=smooth_), loc, parent=parent)


def key_scale(tl, o, fn, step=2):
    bake(tl, o, "scale", lambda t: fn(t), step=step)


def arch_profile(r, n=14):
    return [(r * math.cos(math.pi * i / n), r * math.sin(math.pi * i / n)) for i in range(n + 1)]


# ================================================================ world
def build_ground(mt, rng):
    bm = bmesh.new()
    box(bm, (0.0, 0.0, -0.05), (2 * EXT, 2 * EXT, 0.1), 0)
    obj("prairie", bm, [mt["prairie"]])
    # big field patches (gold / green) far out: plain coloured slabs just above the ground
    bm = bmesh.new()
    for i in range(160):
        x, y = rng.uniform(-3500, 3500), rng.uniform(-2600, 4200)
        if abs(x) < 260 and -180 < y < 260:
            continue
        sx, sy = rng.uniform(150, 420), rng.uniform(150, 420)
        box(bm, (x, y, 0.02 + 0.002 * (i % 7)), (sx, sy, 0.02), i % 5)
    obj("fields", bm, mt["field"])
    # gravel road (east-west) + driveways to each bunker door
    bm = bmesh.new()
    box(bm, (0.0, ROAD_Y, 0.04), (2 * EXT, ROAD_W, 0.12), 0)
    for x in BX:
        box(bm, (x, (ROAD_Y + HEAD_Y) / 2.0, 0.035), (6.0, HEAD_Y - ROAD_Y, 0.1), 0)
    # a north-south farm road far west
    box(bm, (-300.0, 2000.0, 0.04), (6.0, 4400.0, 0.12), 0)
    obj("gravel", bm, [mt["gravel"]])


def build_bunker(mt, x, k, open_door=False):
    """Earth-covered arch magazine: vault (inside visible through the open door), earth mound, headwall, doors."""
    bm = bmesh.new()
    prof = arch_profile(B_R)
    # vault shell (inside faces) from HEAD_Y to HEAD_Y + B_LEN
    y0, y1 = HEAD_Y, HEAD_Y + B_LEN
    vs0 = [bm.verts.new((x + px, y0, pz)) for px, pz in prof]
    vs1 = [bm.verts.new((x + px, y1, pz)) for px, pz in prof]
    for i in range(len(prof) - 1):
        bm.faces.new((vs0[i], vs0[i + 1], vs1[i + 1], vs1[i]))
    back = bm.faces.new(list(reversed(vs1)))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # normals must face inward: flip everything (recalc points them outward)
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    obj("vault%d" % k, bm, [mt["vault"]])
    bm = bmesh.new()
    box(bm, (x, (y0 + y1) / 2.0, 0.02), (2 * B_R, B_LEN, 0.04), 0)
    obj("vfloor%d" % k, bm, [mt["floor"]])
    # earth mound: a stretched half-ellipsoid over the vault (front cut by the headwall)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=14, radius=1.0,
                              matrix=Matrix.Translation((x, y0 + B_LEN * 0.5 + 1.5, 0.0)) @
                              Matrix.Diagonal((9.0, B_LEN * 0.5 + 6.5, 7.6, 1.0)))
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), plane_co=(0, 0, 0),
                           plane_no=(0, 0, -1), clear_outer=True)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), plane_co=(0, y0 + 0.4, 0),
                           plane_no=(0, -1, 0), clear_outer=True)
    obj("mound%d" % k, bm, [mt["mound"]], smooth_=True)
    # headwall with a door opening + wing walls
    bm = bmesh.new()
    hw, hh, t = 13.0, 6.2, 0.6
    side = (hw - DOOR_W) / 2.0
    box(bm, (x - DOOR_W / 2 - side / 2, y0 + t / 2 - 0.1, hh / 2), (side, t, hh), 0)
    box(bm, (x + DOOR_W / 2 + side / 2, y0 + t / 2 - 0.1, hh / 2), (side, t, hh), 0)
    box(bm, (x, y0 + t / 2 - 0.1, DOOR_H + (hh - DOOR_H) / 2), (DOOR_W, t, hh - DOOR_H), 0)
    for sgn in (-1, 1):
        res = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.5, 6.0, 4.0), verts=res["verts"])
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(sgn * 0.5, 3, "Z"))
        bmesh.ops.translate(bm, vec=(x + sgn * (hw / 2 + 1.2), y0 - 2.2, 2.0), verts=res["verts"])
    box(bm, (x, y0 - 0.5, 0.06), (hw, 2.0, 0.12), 0)     # apron
    obj("headwall%d" % k, bm, [mt["concrete"]])
    # doors: two steel leaves (open = swung out against the headwall)
    bm = bmesh.new()
    lw = DOOR_W / 2.0
    for sgn in (-1, 1):
        if open_door:
            box(bm, (x + sgn * (DOOR_W / 2 + 0.12), y0 - lw / 2 - 0.1, DOOR_H / 2), (0.1, lw, DOOR_H - 0.05), 0)
        else:
            box(bm, (x + sgn * lw / 2, y0 - 0.12, DOOR_H / 2), (lw - 0.04, 0.12, DOOR_H - 0.05), 0)
    obj("door%d" % k, bm, [mt["door"]])
    # small vent stack on the mound
    bm = bmesh.new()
    cyl(bm, (x, y0 + B_LEN * 0.6, 7.6), 0.35, 1.8, 0, 10)
    obj("vent%d" % k, bm, [mt["concrete"]])


def build_interior(tl, st, mt, ctx):
    """Inside the open bunker: ceiling lamps + lights, pallet + drum (crystals), forklift, detonator cutaway."""
    x = DRUM_BX
    bm = bmesh.new()
    for yy in (11.0, 16.5, 22.0, 27.0):
        box(bm, (x, yy, B_R - 0.18), (1.6, 0.25, 0.08), 0)
    obj("lamps", bm, [mt["lamp"]])
    for i, yy in enumerate((11.5, 17.5, 24.0)):
        ld = bpy.data.lights.new("bl%d" % i, "AREA")
        ld.energy = 900.0
        ld.size = 2.5
        ld.color = (1.0, 0.96, 0.9)
        _local_light(ld, 14.0)
        lo = L.link(bpy.data.objects.new("bl%d" % i, ld))
        lo.location = (x, yy, B_R - 0.4)
    pt = bpy.data.lights.new("bl_fill", "POINT")
    pt.energy = 600.0
    pt.shadow_soft_size = 1.5
    _local_light(pt, 12.0)
    po = L.link(bpy.data.objects.new("bl_fill", pt))
    po.location = (x + 1.0, 14.0, 2.6)
    # a few closed drums against the back + side walls (plain, no markings)
    bm = bmesh.new()
    for (dx_, dy_) in ((-3.2, 26.5), (-2.4, 26.5), (-3.2, 25.6), (2.8, 26.6), (3.4, 25.7), (-3.4, 23.2)):
        cyl(bm, (x + dx_, dy_, 0.47), 0.3, 0.9, 0, 16)
    obj("drums_bg", bm, [mt["drum"]])
    # pallet + the open drum
    bm = bmesh.new()
    for i in range(5):
        box(bm, (DRUM[0] - 0.5 + i * 0.25, DRUM[1], 0.13), (0.12, 1.2, 0.03), 0)
    for yy in (-0.5, 0.0, 0.5):
        box(bm, (DRUM[0], DRUM[1] + yy, 0.06), (1.2, 0.1, 0.12), 0)
    obj("pallet", bm, [mt["pallet"]])
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=0.33, radius2=0.33, depth=0.9)
    bmesh.ops.translate(bm, vec=(DRUM[0], DRUM[1], 0.6), verts=res["verts"])
    for zz in (0.32, 0.6, 0.88):
        r2 = bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=0.345, radius2=0.345, depth=0.04)
        bmesh.ops.translate(bm, vec=(DRUM[0], DRUM[1], 0.15 + zz), verts=r2["verts"])
    box(bm, (DRUM[0], DRUM[1], 0.16), (0.5, 0.5, 0.02), 0)
    obj("drum", bm, [mt["drum"]])
    bm = bmesh.new()
    cyl(bm, (DRUM[0], DRUM[1], 0.88), 0.325, 0.04, 0, 28)
    obj("drum_fill", bm, [mt["drum_in"]])
    # needle crystals in the powder (grow on "crystallize")
    rng = random.Random(7)
    bm = bmesh.new()
    for i in range(60):
        a, r = rng.uniform(0, 6.283), 0.29 * math.sqrt(rng.random())
        h = rng.uniform(0.05, 0.16)
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.008, radius2=0.0, depth=h)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=res["verts"])
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                         matrix=Matrix.Rotation(rng.uniform(-0.7, 0.7), 3, Vector((math.cos(a + 1.3), math.sin(a + 1.3), 0))))
        bmesh.ops.translate(bm, vec=(r * math.cos(a), r * math.sin(a), 0.0), verts=res["verts"])
    cr = obj("crystals", bm, [mt["crystal"]], (DRUM[0], DRUM[1], 0.9))
    c0 = st.c_cryst - 0.3
    bake(tl, cr, "scale", lambda t: (1.0, 1.0, max(0.001, smooth((t - c0) / 2.2))) if t >= st.t_m else (1, 1, 0.001),
         step=2)
    empty(ctx, "drum", (DRUM[0], DRUM[1], 1.0))
    # red "don't move" ring on the floor around the drum
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, segments=48, radius=1.05)
    ring = bmesh.ops.create_circle(bm, segments=48, radius=0.92)
    obj_ring = None
    bm.free()
    obj_ring = torus("drum_ring", mt["ring_r"], 1.0, 0.045, (DRUM[0], DRUM[1], 0.05))
    show_between(tl, obj_ring, st.c_touchy - 0.1, st.t_d)
    # forklift (generic, yellow, forks towards the drum)
    fx, fy = FORK
    bm = bmesh.new()
    box(bm, (fx, fy - 0.3, 0.75), (1.2, 2.0, 0.9), 0)            # body
    box(bm, (fx, fy - 1.25, 0.9), (1.15, 0.5, 1.1), 0)          # counterweight
    box(bm, (fx, fy - 0.1, 1.45), (0.9, 0.9, 0.08), 1)          # seat / deck
    for sx in (-0.5, 0.5):
        for sy in (-1.0, 0.6):
            box(bm, (fx + sx, fy + sy - 0.2, 2.0), (0.06, 0.06, 1.2), 1)   # guard posts
    box(bm, (fx, fy - 0.2, 2.6), (1.1, 1.7, 0.06), 1)            # overhead guard
    for sx in (-0.38, 0.38):
        box(bm, (fx + sx, fy + 0.8, 1.4), (0.08, 0.1, 2.6), 1)    # mast
    box(bm, (fx, fy + 0.85, 0.35), (0.9, 0.08, 0.5), 1)          # carriage
    for sx in (-0.25, 0.25):
        box(bm, (fx + sx, fy + 1.45, 0.12), (0.12, 1.2, 0.05), 1)  # forks
    obj("forklift", bm, [mt["fork_y"], mt["dark"]])
    bm = bmesh.new()
    for sx in (-0.62, 0.62):
        for sy, r in ((0.45, 0.3), (-1.1, 0.26)):
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=0.22)
            bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, vec=(fx + sx, fy + sy - 0.2, r), verts=res["verts"])
    obj("fork_wheels", bm, [mt["dark"]])
    empty(ctx, "forklift", (fx, fy, 2.0))
    build_cutaway(tl, st, mt, ctx)


def _local_light(ld, dist):
    """Interior / effect lights: no shadow maps and a short influence radius (they were costing ~3x render time)."""
    try:
        ld.use_shadow = False
    except Exception:
        pass
    try:
        ld.use_custom_distance = True
        ld.cutoff_distance = dist
    except Exception:
        pass


def torus(name, mat, R, r, loc):
    bm = bmesh.new()
    me = bpy.data.meshes.new(name)
    bmesh.ops.create_circle(bm, segments=8, radius=r)
    bm.free()
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=64, minor_segments=8,
                                     location=loc)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    return o


def build_cutaway(tl, st, mt, ctx):
    """ILLUSTRATION: a detonator scaled up to ~2 m and cut open (half tube), on a white stand. Diagram only."""
    sx, sy = STAND
    zc = 1.2
    bm = bmesh.new()
    box(bm, (sx, sy, 0.45), (0.5, 0.5, 0.9), 0)
    box(bm, (sx, sy, 0.92), (1.0, 2.6, 0.06), 0)
    box(bm, (sx, sy, 0.03), (1.0, 1.0, 0.06), 0)
    obj("stand", bm, [mt["stand"]])
    # half tube along Y (open towards -X / the camera side), length 2.2, radius 0.2
    L_, R_ = 2.2, 0.2
    y0 = sy - L_ / 2
    bm = bmesh.new()
    n = 16
    outer = [(R_ * math.cos(math.pi * (0.5 + i / n)), R_ * math.sin(math.pi * (0.5 + i / n))) for i in range(n + 1)]
    # semicircle on the +X side: angles -90..90 deg
    outer = [(R_ * math.cos(math.pi / 2 + math.pi * i / n), R_ * math.sin(math.pi / 2 + math.pi * i / n))
             for i in range(n + 1)]
    v0 = [bm.verts.new((sx + px, y0, zc + pz)) for px, pz in outer]
    v1 = [bm.verts.new((sx + px, y0 + L_, zc + pz)) for px, pz in outer]
    for i in range(n):
        bm.faces.new((v0[i], v0[i + 1], v1[i + 1], v1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    tube = obj("tube", bm, [mt["tube"]])
    sol = tube.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.03
    # closed rounded tip end (crimp) + end cap
    # main charge (bigger block, back 70 %) and primary pellet (small, at the tip end = +Y)
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=R_ - 0.04, radius2=R_ - 0.04, depth=L_ * 0.62)
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=(sx + 0.03, y0 + L_ * 0.36, zc), verts=res["verts"])
    main = obj("main_charge", bm, [mt["main"], mt["main_glow"]])
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=R_ - 0.05, radius2=R_ - 0.05, depth=L_ * 0.12)
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=(sx + 0.03, y0 + L_ * 0.86, zc), verts=res["verts"])
    obj("primary", bm, [mt["primary"]])
    # teal outline rings (diagram look)
    for i, yy in enumerate((y0, y0 + L_ * 0.67, y0 + L_ * 0.8, y0 + L_)):
        o = torus("edge%d" % i, mt["edge"], R_ + 0.015, 0.008, (sx, yy, zc))
        o.rotation_euler = (math.pi / 2, 0.0, 0.0)
    empty(ctx, "pellet", (sx + 0.05, y0 + L_ * 0.86, zc + 0.05))
    empty(ctx, "main", (sx + 0.05, y0 + L_ * 0.36, zc - 0.05))
    # main charge glows after the spark arrives (material swap via a second slot = an overlay shell)
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=R_ - 0.035, radius2=R_ - 0.035,
                                depth=L_ * 0.625)
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    glow = obj("main_glow", bm, [mt["main_glow"]], (0, 0, 0))
    glow.location = (sx + 0.03, y0 + L_ * 0.36, zc)
    for v in glow.data.vertices:
        v.co.x -= sx + 0.03
        v.co.y -= y0 + L_ * 0.36
        v.co.z -= zc
    show_between(tl, glow, st.c_big + 0.2, st.c_built)
    # spark: hops from the pellet to the main charge on "set off", again on "sensitive"
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.06)
    sp = obj("spark", bm, [mt["spark"]], (sx + 0.05, y0 + L_ * 0.86, zc))
    pa, pb = (sx + 0.05, y0 + L_ * 0.86, zc), (sx + 0.05, y0 + L_ * 0.5, zc)

    def sp_loc(t):
        for c0 in (st.c_set, st.c_built + 0.6):
            if c0 - 0.1 <= t <= c0 + 0.8:
                return vlerp(pa, pb, smooth((t - c0) / 0.6))
        return pa

    def sp_scale(t):
        for c0 in (st.c_set, st.c_built + 0.6):
            if c0 - 0.1 <= t <= c0 + 0.8:
                k = 1.0 - smooth((t - c0 - 0.55) / 0.25)
                return (k, k, k)
        return (0.0, 0.0, 0.0)
    bake(tl, sp, "location", sp_loc)
    bake(tl, sp, "scale", sp_scale)


def build_ring(tl, st, mt, ctx):
    """Barrier ring: N_WALL tall T-wall style sections (ribbed), rising from the ground in sequence."""
    rng = random.Random(11)
    bm = bmesh.new()
    seg_w = 2 * math.pi * R_WALL / N_WALL - 0.08
    box(bm, (0.0, 0.0, WALL_H / 2), (seg_w, 0.5, WALL_H), 0)
    box(bm, (0.0, 0.55, 0.35), (seg_w, 1.6, 0.7), 1)                 # footing (outside)
    box(bm, (0.0, -0.32, WALL_H * 0.5), (0.25, 0.14, WALL_H * 0.92), 1)  # rib
    me = S.mesh_from_bm("wallseg", bm, [mt["wall"], mt["wall_dk"]])
    walls = []
    for i in range(N_WALL):
        a = 2 * math.pi * i / N_WALL
        x, y = RC[0] + R_WALL * math.cos(a), RC[1] + R_WALL * math.sin(a)
        o = S.obj("wall%d" % i, me, (x, y, 0.0), (0.0, 0.0, a - math.pi / 2 + math.pi))
        o.rotation_euler.z = a + math.pi / 2
        walls.append((o, i))
    # stagger: rise sweeping from the south (camera side) around both ways
    for o, i in walls:
        a = (2 * math.pi * i / N_WALL - 1.5 * math.pi) % (2 * math.pi)
        k = min(a, 2 * math.pi - a) / math.pi              # 0 at south, 1 at north
        k = k * 0.9 + rng.uniform(0.0, 0.1)

        def zf(t, k=k, o=o):
            b = built(st, t, st.wall_win, k)
            return (o.location.x, o.location.y, -(WALL_H + 0.8) * (1.0 - b))
        bake(tl, o, "location", zf, step=3)
    empty(ctx, "wall", (RC[0], RC[1] - R_WALL, WALL_H))


def build_tanks(tl, st, mt, ctx):
    bm = bmesh.new()
    cyl(bm, (0.0, 0.0, 2.6), 2.2, 5.2, 0, 32)
    cyl(bm, (0.0, 0.0, 5.25), 2.25, 0.1, 1, 32)
    for zz in (1.3, 2.6, 3.9):
        cyl(bm, (0.0, 0.0, zz), 2.24, 0.12, 1, 32)
    box(bm, (0.0, -2.2, 0.4), (0.5, 0.4, 0.4), 1)       # valve box
    me = S.mesh_from_bm("tank", bm, [mt["tank"], mt["tank_top"]])
    n = len(TANK_ANG)
    for i, ang in enumerate(TANK_ANG):
        a = math.radians(ang)
        o = S.obj("tank%d" % i, me, (RC[0] + R_TANK * math.cos(a), RC[1] + R_TANK * math.sin(a), 0.0),
                  (0.0, 0.0, a))
        k = i / max(1, n - 1)

        def sf(t, k=k):
            b = built(st, t, st.tank_win, k)
            return (max(0.001, min(1.0, b * 1.6)), max(0.001, min(1.0, b * 1.6)), max(0.001, b))
        bake(tl, o, "scale", sf, step=3)
    empty(ctx, "tanks", (RC[0] + R_TANK * math.cos(math.radians(270)), RC[1] - R_TANK, 5.5))


def build_foam(tl, st, mt, rng):
    """White foam blocks stacked over the two ringed mounds (and along their sides)."""
    blocks = []
    for bx in (-15.0, 15.0):
        for row in range(5):
            for col in range(3):
                yy = HEAD_Y + 4.0 + row * 4.0
                xx = bx + (col - 1) * 2.6
                # sit on the mound surface (approx ellipsoid height)
                ux = (xx - bx) / 9.0
                uy = (yy - (HEAD_Y + B_LEN * 0.5 + 1.5)) / (B_LEN * 0.5 + 6.5)
                zz = 7.6 * math.sqrt(max(0.0, 1.0 - ux * ux - uy * uy))
                blocks.append(((xx, yy, zz + 0.55), (2.3, 3.6, 1.1)))
                if row % 2 == 0 and col == 1:
                    blocks.append(((xx + rng.uniform(-0.3, 0.3), yy, zz + 1.6), (2.0, 3.0, 1.0)))
        for sgn in (-1, 1):
            for row in range(5):
                yy = HEAD_Y + 3.0 + row * 4.5
                blocks.append(((bx + sgn * 9.6, yy, 0.6), (1.4, 3.8, 1.2)))
                blocks.append(((bx + sgn * 9.6, yy, 1.8), (1.4, 3.6, 1.2)))
    n = len(blocks)
    order = list(range(n))
    rng.shuffle(order)
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), 0)
    me = S.mesh_from_bm("foamblk", bm, [mt["foam"]])
    for j, i in enumerate(order):
        (x, y, z), (sx, sy, sz) = blocks[i]
        o = S.obj("foam%d" % i, me, (x, y, z), (0.0, 0.0, rng.uniform(-0.05, 0.05)), (sx, sy, sz))
        k = j / max(1, n - 1)

        def zf(t, k=k, base=(x, y, z)):
            b = built(st, t, st.foam_win, k)
            return (base[0], base[1], base[2] + 2.5 * (1.0 - smooth(b * 1.4)) if b > 0.001 else base[2] - 40.0)
        bake(tl, o, "location", zf, step=3)


def build_puff(tl, st, mt, ctx):
    """Soft stylised dust/foam puff over the ring centre (icosphere cluster). Size/alpha follow Story curves."""
    rng = random.Random(21)
    bm = bmesh.new()
    blobs = []
    for i in range(110):    # a wide, low, irregular dust/foam cloud (no column, no cap)
        a = rng.uniform(0, 6.283)
        r = rng.uniform(0.0, 1.0) ** 0.55 * 19.0
        z = rng.uniform(0.0, 1.0) ** 1.6 * 13.0 * (1.0 - 0.35 * r / 19.0)
        rr = rng.uniform(3.0, 6.5) * (1.0 - z / 30.0)
        blobs.append((r * math.cos(a), r * math.sin(a) * 0.85, z + 2.0, rr))
    for x, y, z, r in blobs:
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                   matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r, r, r * 0.85, 1.0)))
    m, aval = puff_mat()
    pf = obj("puff", bm, [m], (RC[0], RC[1], 0.0), smooth_=True)

    def scl(t):
        s = max(0.001, st.puff_s(t))
        return (s, s, s * (0.85 + 0.15 * s))
    bake(tl, pf, "scale", scl)
    bake(tl, pf, "rotation_euler", lambda t: (0.0, 0.0, 0.02 * t))
    bake_sock(tl, aval, lambda t: st.puff_a(t))
    # soft flash under the ground: glowing disk + a warm point light (no flame)
    fm, fval = flash_mat()
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=16.0)
    fl = obj("flash", bm, [fm], (RC[0], RC[1], 0.15))
    bake_sock(tl, fval, lambda t: st.flash(t))
    ld = bpy.data.lights.new("flash_l", "POINT")
    ld.energy = 0.0
    ld.color = (1.0, 0.9, 0.75)
    ld.shadow_soft_size = 6.0
    _local_light(ld, 120.0)
    lo = L.link(bpy.data.objects.new("flash_l", ld))
    lo.location = (RC[0], RC[1], 4.0)
    bake(tl, ld, "energy", lambda t: 2.0e6 * st.flash(t))
    # downward arrows over the ring ("driven down, into the ground")
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 3.2), (0.9, 0.9, 4.0), 0)
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=2.0, radius2=0.0, depth=2.4)
    bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi, 3, "X"))
    bmesh.ops.translate(bm, vec=(0.0, 0.0, 0.0), verts=res["verts"])
    me = S.mesh_from_bm("arrow", bm, [mt["arrow"]])
    for i, (ox, oy) in enumerate(((-11.0, 0.0), (0.0, -6.0), (11.0, 0.0))):
        o = S.obj("arrow%d" % i, me, (RC[0] + ox, RC[1] + oy, 26.0), (0.0, 0.0, math.radians(45)))
        a0, a1 = st.c_down - 0.3 + 0.12 * i, st.t_915 - 0.2

        def loc(t, ox=ox, oy=oy, a0=a0):
            ph = ((t - a0) * 0.8) % 1.0
            return (RC[0] + ox, RC[1] + oy, 30.0 - 9.0 * smooth(ph) if t >= a0 else 30.0)

        def sc(t, a0=a0, a1=a1):
            if t < a0 or t > a1 + 0.3:
                return (0.0, 0.0, 0.0)
            k = smooth((t - a0) / 0.3) * (1.0 - smooth((t - a1) / 0.3))
            ph = ((t - a0) * 0.8) % 1.0
            k *= min(1.0, ph / 0.12, (1.0 - ph) / 0.12) if t - a0 > 0.4 else 1.0
            return (k, k, k)
        bake(tl, o, "location", loc)
        bake(tl, o, "scale", sc)


def build_mast(tl, st, mt, ctx):
    x, y = MAST
    bm = bmesh.new()
    cyl(bm, (x, y, 2.0), 0.06, 4.0, 1, 10)
    box(bm, (x, y + 0.18, 1.3), (0.5, 0.3, 0.6), 0)            # sampler box
    box(bm, (x, y, 0.05), (1.2, 1.2, 0.1), 2)                  # base plate
    for sgn in (-1, 1):
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.02, radius2=0.02, depth=2.3)
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(sgn * 0.45, 3, "X"))
        bmesh.ops.translate(bm, vec=(x, y + sgn * 0.5, 1.0), verts=res["verts"])
    box(bm, (x, y, 4.05), (0.25, 0.25, 0.2), 0)                # sensor head
    obj("mast", bm, [mt["white"], mt["steel"], mt["concrete"]])
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 0.0), (1.0, 0.04, 0.7), 0)
    pn = obj("panel", bm, [mt["panel"]], (x - 0.05, y - 0.45, 2.6))
    pn.rotation_euler = (math.radians(-35), 0.0, 0.0)
    # spinning cups (anemometer-style sensor) on top
    bm = bmesh.new()
    for i in range(3):
        a = 2 * math.pi * i / 3
        box(bm, (0.18 * math.cos(a), 0.18 * math.sin(a), 0.0), (0.36 * abs(math.cos(a)) + 0.02, 0.36 * abs(math.sin(a)) + 0.02, 0.015), 1)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.05,
                                   matrix=Matrix.Translation((0.36 * math.cos(a), 0.36 * math.sin(a), 0.0)))
    cups = obj("cups", bm, [mt["white"], mt["steel"]], (x, y, 4.35))
    bake(tl, cups, "rotation_euler", lambda t: (0.0, 0.0, 6.0 * t))
    empty(ctx, "mast", (x, y, 4.1))


def build_shell(tl, st, mt, ctx, rng):
    x, y = SHELL
    bm = bmesh.new()
    # generic old shell: rusty body + rounded nose, lying in the grass, partly sunk
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=0.085, radius2=0.085, depth=0.42)
    bmesh.ops.translate(bm, vec=(0, 0, 0.21), verts=res["verts"])
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=0.085, radius2=0.012, depth=0.2)
    bmesh.ops.translate(bm, vec=(0, 0, 0.52), verts=res["verts"])
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=0.092, radius2=0.092, depth=0.04)
    bmesh.ops.translate(bm, vec=(0, 0, 0.06), verts=res["verts"])
    sh = obj("shell", bm, [mt["rust"]], (x, y, 0.07))
    sh.scale = (1.3, 1.3, 1.3)
    sh.rotation_euler = (math.radians(84), 0.0, math.radians(35))
    empty(ctx, "shell", (x, y, 0.15))
    # grass tufts around it (and along the road edge)
    bm = bmesh.new()
    r2 = random.Random(3)
    for k in range(9):
        a = 2 * math.pi * k / 9 + r2.uniform(-0.2, 0.2)
        h = r2.uniform(0.35, 0.6)
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.02, radius2=0.0, depth=h)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=res["verts"])
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                         matrix=Matrix.Rotation(0.3, 3, Vector((math.sin(a), -math.cos(a), 0))))
    me = S.mesh_from_bm("tuft", bm, [mt["grass"]])
    pts = []
    near = []
    for i in range(26):
        a, r = rng.uniform(0, 6.283), rng.uniform(0.45, 2.6)
        near.append((x + r * math.cos(a), y + r * math.sin(a)))
    for i in range(500):
        pts.append((rng.uniform(-120, 120), ROAD_Y - ROAD_W / 2 - rng.uniform(0.2, 9.0)))
    for i, (px, py) in enumerate(pts):
        S.obj("tuft%d" % i, me, (px, py, 0.0), (0, 0, rng.uniform(0, 6.28)), (rng.uniform(0.8, 1.4),) * 3)
    for i, (px, py) in enumerate(near):
        S.obj("ntuft%d" % i, me, (px, py, 0.0), (0, 0, rng.uniform(0, 6.28)), (rng.uniform(0.45, 0.75),) * 3)
    o = torus("shell_ring", mt["ring_r"], 0.75, 0.03, (x, y, 0.08))
    show_between(tl, o, st.c_shell + 0.1, None)


def build_far(mt, ctx, rng):
    tt = S.tree_templates(rng)
    pts = []
    # windbreak tree lines (east-west) north and south of the site, a few north-south
    for yy in (230.0, 520.0, -260.0, 900.0):
        x = -1200.0
        while x < 1200.0:
            pts.append((x + rng.uniform(-3, 3), yy + rng.uniform(-4, 4)))
            x += rng.uniform(9.0, 14.0)
    for xx in (-420.0, 380.0):
        y = -500.0
        while y < 1400.0:
            pts.append((xx + rng.uniform(-3, 3), y))
            y += rng.uniform(9.0, 14.0)
    S.scatter(tt, pts, rng, (1.0, 1.5), prefix="wb")
    # farmstead: barn + two silos, and a generic water tower (no text)
    bm = bmesh.new()
    for (fx, fy) in ((-520.0, 600.0), (640.0, 420.0)):
        box(bm, (fx, fy, 5.0), (18.0, 30.0, 10.0), 0)
        cyl(bm, (fx + 16.0, fy + 6.0, 11.0), 3.5, 22.0, 1, 20)
        cyl(bm, (fx + 24.0, fy + 6.0, 9.0), 3.0, 18.0, 1, 20)
    obj("farms", bm, [mt["barn"], mt["silo"]])
    bm = bmesh.new()
    wx, wy = 300.0, 820.0
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0,
                              matrix=Matrix.Translation((wx, wy, 36.0)) @ Matrix.Diagonal((9.0, 9.0, 6.5, 1.0)))
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.6, radius2=0.6, depth=33.0)
        bmesh.ops.translate(bm, vec=(wx + 5.0 * math.cos(a), wy + 5.0 * math.sin(a), 16.5), verts=res["verts"])
    cyl(bm, (wx, wy, 16.0), 1.0, 32.0, 0, 12)
    obj("water_tower", bm, [mt["wt"]], smooth_=False)
    # gentle far rises (keep the horizon soft; strong haze)
    for k in range(8):
        bm = bmesh.new()
        x, y = -3200.0 + k * 900.0 + rng.uniform(-200, 200), rng.uniform(2600, 3400)
        rx, h = rng.uniform(700, 1100), rng.uniform(40, 90)
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                   matrix=Matrix.Translation((x, y, 0.0)) @ Matrix.Diagonal((rx, rx * 0.5, h, 1.0)))
        S.obj("rise%d" % k, S.mesh_from_bm("rise%d" % k, bm, [mt["far"]], smooth=True))


# ================================================================ BUILDER
def b_detonation_oneshot(ctx, p):
    tl = TL(ctx)
    st = Story(tl)
    sc = ctx.scene
    rng = random.Random(p.get("seed", 25))
    S.daylight(ctx, p.get("sun_az", -35.0), 34.0)
    L.fog(0.00018, S.HAZE, start=300.0)
    C.horizon_haze(sc, lo=-0.01, hi=0.045)
    mt = mats()
    spots = route(tl, st)
    T_end = tl.t_of_G(tl.total)
    build_ground(mt, rng)
    for k, x in enumerate(BX):
        build_bunker(mt, x, k, open_door=(x == DRUM_BX))
    build_interior(tl, st, mt, ctx)
    build_ring(tl, st, mt, ctx)
    build_tanks(tl, st, mt, ctx)
    build_foam(tl, st, mt, random.Random(9))
    build_puff(tl, st, mt, ctx)
    build_mast(tl, st, mt, ctx)
    build_shell(tl, st, mt, ctx, random.Random(13))
    build_far(mt, ctx, random.Random(17))
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=30)
    cam.data.clip_end = 30000.0

    def cam_loc(t):
        return vadd(camera_at(spots, t, T_end)[0], shake(st, t))
    bake(tl, cam, "location", cam_loc)
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    bake(tl, cam.data, "clip_start", lambda t: max(0.05, min(2.0, 0.02 * camera_at(spots, t, T_end)[0][2])))
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 detonation] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 detonation] beat %d (%s): global frames %d-%d" % (
        tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1, tl.off[tl.k] + tl.n[tl.k]))


S.V2_BUILDERS.update({"detonation_oneshot": b_detonation_oneshot})

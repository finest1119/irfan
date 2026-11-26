"""v2 one-shot orbit + launch-pad builder ("space docking", WJH 28 Nov 2026 #3, narration style "rewind").
Registers into scene_lib_v2.V2_BUILDERS as `docking_oneshot`.

Same pattern as scene_lib_v2_detonation.py / _cyclone.py / _tides.py: ONE builder for every beat. Each beat builds the
identical world and keys ALL animation (camera, capsule, rocket, orbit lines, sky, haze) on the GLOBAL episode timeline
(WORKDIR/audio/timings.json + captions.json), so the video is one continuous camera: slow drifts at each spot, fast
eased whips (EEVEE motion blur) between spots. Rewind <-> backout: the camera starts tight on the docking ring and keeps
backing out and DOWN (station -> the gap -> the chase orbits -> the top of the atmosphere -> the desert pad), then one
fast climb back up the same path, and it ends on the frame-1 view (loop).

World (stylised scale, Earth radius R = 120 km so the views from "orbit" have real-looking curvature; ratios like the
real ISS: altitude/R ~ 0.06):
  * Earth: a sphere centred at (0, 0, -R): procedural blue oceans, green/brown land, a desert around the pad, white
    cloud fields (texture slowly turning = orbital motion), a blue limb tint + an atmosphere shell (limb glow).
  * Station (world frame = station frame, centre at z = H_S): generic T-shaped station, white modules, gold solar
    wings, aft docking port at x = -X_PORT. Capsule: generic three-part spacecraft (orbital module with docking ring,
    descent module, service module with blue solar panels that fold). Last rocket stage. No flags, logos or markings.
  * Orbit lines: glowing rings around the planet (station: amber, capsule: teal) + a dashed amber "station's path"
    ring that sweeps over the pad.
  * Launch pad at angle A_P (12.7 km behind the station's ground point): desert ground patch, pad deck, pedestal,
    lattice service tower, lightning masts, a white generic rocket (liftoff with a flame and white smoke), hills.
  * Sky: world shader mixes black space (stars) and a blue daytime sky by camera altitude; ground haze likewise.
No text in 3D (all text is 2D overlay).

Beats it expects: hook, question, rewind_contact, rewind_chase, rewind_orbit, rewind_pad, forward, takeaway, outro.
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
import scene_lib_v2_tides as TD

TL, bake, bake_sock, curve, smooth, smoother = TD.TL, TD.bake, TD.bake_sock, TD.curve, TD.smooth, TD.smoother
vadd, vsub, vmul, vlen, vnorm, vlerp = TD.vadd, TD.vsub, TD.vmul, TD.vlen, TD.vnorm, TD.vlerp
lin, camera_at, show_between, box, cyl, empty = TD.lin, TD.camera_at, TD.show_between, TD.box, TD.cyl, TD.empty

# ---------------------------------------------------------------- layout
R = 120000.0                 # Earth radius (stylised)
EC = (0.0, 0.0, -R)          # Earth centre
H_S = 7500.0                 # station altitude
H_C = 5500.0                 # capsule's lower (chase) orbit
H_SHELL = 2000.0             # atmosphere shell
A_P = -0.33                  # launch pad angle (rad) along the orbit plane (beyond the station's horizon)
X_PORT = 7.2                 # station aft docking port face at x = -X_PORT
L_NOSE = 4.7                 # capsule nose (docking ring face) at capsule-local x = +L_NOSE
X_DOCK = -(X_PORT + L_NOSE)  # capsule origin (station-local x) when docked
CH0, CH1 = -4300.0, -2500.0  # chase: capsule along-track start / end (m)
OR_X, OR_H = -9000.0, 2450.0  # orbit insertion (rewind_orbit): along-track, altitude
SUN_ELEV, SUN_AZ = 40.0, -62.0

_M = {}
HZ = []          # haze density Value sockets (baked by camera altitude)


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


# ---------------------------------------------------------------- frames
def OL(a, h, y=0.0):
    """Orbital coords -> world: angle a (rad, + = ahead/+x), altitude h, lateral y."""
    r = R + h
    return (math.sin(a) * r, y, math.cos(a) * r - R)


def fwd(a):
    return (math.cos(a), 0.0, -math.sin(a))


def up(a):
    return (math.sin(a), 0.0, math.cos(a))


def ang(x):
    """along-track metres at station altitude -> angle"""
    return x / (R + H_S)


def LF(a, h, dx, dy, dz):
    """local frame at orbital point (a, h): dx along track, dy lateral, dz up"""
    p = OL(a, h)
    return vadd(vadd(vadd(p, vmul(fwd(a), dx)), (0.0, dy, 0.0)), vmul(up(a), dz))


def SL(x, y, z):
    """station local (the station sits at a = 0, so its frame is the world frame lifted by H_S)"""
    return (x, y, H_S + z)


def PL(x, y, z):
    """pad local -> world"""
    return LF(A_P, 0.0, x, y, z)


def alt_of(p):
    return vlen(vsub(p, EC)) - R


# ================================================================ story curves (global seconds)
class Story:
    def __init__(self, tl):
        c, b0, b1 = tl.cue, tl.bstart, tl.bend
        self.T = T = tl.T
        self.t_q, self.t_c, self.t_ch = b0("question"), b0("rewind_contact"), b0("rewind_chase")
        self.t_or, self.t_pad, self.t_fw = b0("rewind_orbit"), b0("rewind_pad"), b0("forward")
        self.t_k, self.t_o = b0("takeaway"), b0("outro")
        self.c_astro = c("hook", "astronaut", 0.45)
        self.c_rw0 = c("question", "rewind", 0.9)
        self.c_slower = c("rewind_contact", "slower", 0.3)
        self.c_dock = c("rewind_contact", "docking", 0.45)
        self.c_nudge = c("rewind_contact", "nudge", 0.55)
        self.c_latch = c("rewind_contact", "latches", 0.62)
        self.c_pull = c("rewind_contact", "pull", 0.72)
        self.c_seal = c("rewind_contact", "seal", 0.85)
        self.c_rw1 = c("rewind_contact", "rewind", 0.93)
        self.c_capsule = c("rewind_chase", "capsule", 0.15)
        self.c_lower = c("rewind_chase", "lower", 0.4)
        self.c_so = c("rewind_chase", "chasing", 0.58) - 0.3
        self.c_fires = c("rewind_chase", "fires", 0.78)
        self.c_climb = c("rewind_chase", "climb", 0.85)
        self.c_rw2 = c("rewind_chase", "rewind", 0.93)
        self.c_done = c("rewind_orbit", "done", 0.5)
        self.c_own = c("rewind_orbit", "own", 0.9)
        self.c_because = c("rewind_pad", "because", 0.3)
        self.c_timed = c("rewind_pad", "timed", 0.65)
        self.c_overhead = c("rewind_pad", "overhead", 0.9)
        self.c_hit = c("forward", "hit", 0.5)
        self.c_comp = c("forward", "computers", 0.6)
        self.c_look = c("takeaway", "look", 0.3)
        self.c_glide = c("takeaway", "gliding", 0.45)
        self.c_free = c("takeaway", "free", 0.8)
        self.c_tell = c("outro", "tell", 0.25)
        self.c_bec = c("outro", "because", 0.55)
        self.c_nudge2 = c("outro", "nudge", 0.9)
        self.t_lift = self.t_fw + 0.25
        # capsule panels: 1 = deployed, ~0 = folded
        self.panels = curve([(0.0, 1.0), (self.c_rw2 + 0.2, 1.0), (self.t_or + 0.2, 0.05), (self.c_own - 1.2, 0.05),
                             (self.c_own + 0.8, 1.0)])
        # last stage separation offset (m, along -x of the capsule)
        self.sep = curve([(self.c_done - 0.2, 0.0), (self.c_done + 4.5, 9.0)])
        # rings (orbit lines) visibility 0..1
        self.rings = curve([(self.c_capsule - 0.6, 0.0), (self.c_capsule + 0.6, 1.0), (self.c_so - 0.65, 1.0),
                            (self.c_so - 0.15, 0.0), (self.c_hit, 0.0), (self.c_hit + 0.8, 1.0),
                            (self.t_k + 0.3, 1.0), (self.t_k + 1.2, 0.0)])
        self.path = curve([(self.t_pad + 0.9, 0.0), (self.t_pad + 2.0, 1.0), (self.t_fw + 1.0, 1.0),
                           (self.t_fw + 2.0, 0.0)])
        self.path_phi = curve([(self.t_pad + 1.0, 0.075), (self.c_timed, 0.05), (self.c_overhead + 0.2, 0.0)])
        self.burn = curve([(self.c_fires - 0.05, 0.0), (self.c_fires + 0.15, 1.0), (self.c_fires + 1.9, 1.0),
                           (self.c_fires + 2.3, 0.0)])

    # ---------------------------------------------------------------- the capsule's path (along, h, y)
    def cap(self, t):
        X0, X1 = X_DOCK, X_DOCK - 4.2
        if t < self.c_rw0 + 0.05:
            return (X0, H_S, 0.0)
        if t < self.t_c + 0.35:      # REWIND: backs off the port
            u = smoother((t - self.c_rw0 - 0.05) / (self.t_c + 0.35 - self.c_rw0 - 0.05))
            return (X0 + (X1 - X0) * u, H_S, 0.0)
        if t < self.c_nudge + 0.4:   # forward again: closing slower than walking pace, contact on "nudge"
            a, b = self.t_c + 0.35, self.c_nudge + 0.4
            u = (t - a) / (b - a)
            g = 4.2 * (1.0 - u) ** 1.6
            return (X0 - g, H_S, 0.0)
        if t < self.c_rw1:
            return (X0, H_S, 0.0)
        t2 = self.t_ch + 0.9
        if t < t2:                   # REWIND again: flies back and down to the chase start
            u = smoother((t - self.c_rw1) / (t2 - self.c_rw1))
            return (X0 + (CH0 - X0) * u, H_S + (H_C - H_S) * smooth(u * 1.3), 0.0)
        t3 = self.c_rw2
        climb = 750.0 * smoother((t - self.c_fires - 0.3) / 2.6)
        if t < t3:                   # lower orbit = faster lap: gaining on the station, then a burn to climb
            u = (t - t2) / (t3 - t2)
            return (CH0 + (CH1 - CH0) * u, H_C + climb, 0.0)
        t4 = self.t_or + 0.35
        if t < t4:                   # REWIND further: back to orbit insertion, near the top of the atmosphere
            u = smoother((t - t3) / (t4 - t3))
            h3 = H_C + 750.0 * smoother((t3 - self.c_fires - 0.3) / 2.6)
            return (CH1 + (OR_X - CH1) * u, h3 + (OR_H - h3) * u, 0.0)
        if t < self.t_fw + 3.0:      # orbit insertion, drifting forward slowly
            return (OR_X + 1.5 * (t - t4), OR_H, 0.0)
        # forward again: the chase replays fast, then the final approach and a gentle nudge in the outro
        return self.cap_fwd(t)

    def cap_fwd(self, t):
        """forward again (hidden until the climb): the chase replays fast, the final approach, a gentle nudge"""
        t0, t1, t2, t3 = self.t_fw + 3.0, self.t_k, self.t_o + 0.2, self.c_bec
        t4 = self.c_nudge2 - 0.05
        if t < t1:
            u = (t - t0) / (t1 - t0)
            return (CH0 + (-2600.0 - CH0) * u, H_C + 500.0 * u, 0.0)
        if t < t2:                   # ease-out into the last 100 m
            u = (t - t1) / (t2 - t1)
            e = 1.0 - (1.0 - u) ** 2
            return (-2600.0 + (-90.0 + 2600.0) * e, H_C + 500.0 + (H_S - 6.0 - H_C - 500.0) * smooth(u), 0.0)
        if t < t3:
            u = smooth((t - t2) / (t3 - t2))
            return (-90.0 + (X_DOCK - 3.0 + 90.0) * u, H_S - 6.0 + 6.0 * u, 0.0)
        if t < t4:                   # final metres: slow, a gentle nudge
            u = (t - t3) / (t4 - t3)
            return (X_DOCK - 3.0 * (1.0 - u) ** 1.7, H_S, 0.0)
        return (X_DOCK, H_S, 0.0)

    def cap_world(self, t):
        x, h, y = self.cap(t)
        return OL(ang(x), h, y), ang(x)

    def cap_visible(self, t):
        return t < self.t_pad + 0.9 or t > self.c_hit + 0.4

    def rocket_z(self, t):
        s = t - self.t_lift
        if s <= 0.0:
            return 0.0
        return 5.0 * s * s + (18.0 * (s - 1.5) ** 3 if s > 1.5 else 0.0)


# ================================================================ camera route
def route(tl, st):
    b0 = tl.bstart
    P1 = st.P1

    def follow_cap(off, toff, lens):
        def f(t, u):
            p, a = st.cap_world(t)
            x, h, _ = st.cap(t)
            return LF(a, h, *off), LF(a, h, *toff), lens
        return f

    def follow_rocket(t, u):
        z = st.rocket_z(t)
        cam = PL(-121.0, -11.5, 8.5 + 0.55 * min(z, 260.0))
        tgt = PL(0.0, 0.0, 57.5 + z * 0.97)
        return cam, tgt, 22.5

    a_or = ang(OR_X)
    spots = [
        # hook: frame-1 view, the capsule locked into the docking ring, gold wings, Earth below (hero 1)
        (0.0, 0.0, lin(P1, (SL(-7.9, -8.6, 7.7), SL(-9.5, 1.0, -3.0), 20.5)), []),
        # ... "first foreign astronaut": over the hatch, looking back along the capsule
        (st.c_astro - 0.35, 0.9, lin((SL(-2.5, 6.8, 4.6), SL(-12.5, -0.6, -1.4), 22.0),
                                     (SL(-2.8, 7.4, 4.8), SL(-12.5, -0.6, -1.4), 22.0)), [SL(-12.0, -2.0, 7.0)]),
        # question: back away: the whole station over the Earth
        (b0("question") + 0.15, 1.0, lin((SL(-50.0, -46.0, 21.0), SL(2.0, 0.0, -7.0), 20.0),
                                         (SL(-53.0, -48.5, 22.0), SL(2.0, 0.0, -7.0), 20.0)), [SL(-12.0, -18.0, 10.0)]),
        # rewind_contact: side view of the gap, capsule lined up nose to port
        (b0("rewind_contact") + 0.2, 0.9, lin((SL(-15.5, -21.0, 7.5), SL(-12.5, 0.0, -1.6), 22.0),
                                              (SL(-15.0, -20.2, 7.2), SL(-12.5, 0.0, -1.6), 22.5)), []),
        # ... "a docking is usually a gentle nudge": closer on the junction, latches
        (st.c_dock - 0.25, 0.8, lin((SL(-10.5, -9.2, 4.4), SL(-8.6, 0.0, -0.8), 24.0),
                                    (SL(-10.2, -8.8, 4.25), SL(-8.6, 0.0, -0.8), 24.5)), []),
        # rewind_chase: back out and down: both orbit lines arcing over the Earth, capsule chasing (hero 2)
        (b0("rewind_chase") + 0.35, 1.4,
         lin((LF(ang(-9200.0), 8300.0, 0.0, -2600.0, 0.0), LF(ang(-1600.0), 5200.0, 0.0, 0.0, 0.0), 19.0),
             (LF(ang(-9000.0), 8250.0, 0.0, -2550.0, 0.0), LF(ang(-1600.0), 5200.0, 0.0, 0.0, 0.0), 19.5)),
         [SL(-60.0, -80.0, 40.0), LF(ang(-3000.0), 7900.0, 0.0, -900.0, 0.0)]),
        # ... "so a chasing spacecraft": ride along beside the capsule (engine burn, climb)
        (st.c_so - 0.2, 1.1, follow_cap((-62.0, -44.0, 20.0), (8.0, 0.0, -3.0), 22.0), []),
        # rewind_orbit: back and down to the top of the atmosphere, the capsule on the last stage
        (b0("rewind_orbit") + 0.3, 1.2, lin((LF(a_or, OR_H, -34.0, -27.0, 8.0), LF(a_or, OR_H, 4.0, 0.0, -5.5), 22.0),
                                            (LF(a_or, OR_H, -31.0, -25.0, 7.6), LF(a_or, OR_H, 4.0, 0.0, -5.5), 22.5)),
         [LF(a_or, OR_H + 600.0, -400.0, -500.0, 0.0)]),
        # rewind_pad: all the way back, down through the bright sky to the desert pad and the white rocket
        (b0("rewind_pad") + 0.45, 1.6, lin((PL(-128.0, -12.5, 8.0), PL(0.0, 0.0, 58.0), 22.0),
                                           (PL(-121.0, -11.5, 8.5), PL(0.0, 0.0, 57.5), 22.5)),
         [PL(-900.0, -350.0, 1400.0), PL(-330.0, -110.0, 160.0)]),
        # forward: liftoff, the camera tilts and rises with the rocket
        (st.t_lift + 0.35, 0.5, follow_rocket, []),
        # ... "hit it": fast climb back up the same path to orbit (orbit lines + capsule flash past)
        (st.c_hit - 0.1, 2.0, lin((LF(ang(-8200.0), 8100.0, 0.0, -2400.0, 0.0), LF(ang(-1600.0), 5300.0, 0.0, 0.0, 0.0), 19.0),
                                  (LF(ang(-8000.0), 8050.0, 0.0, -2350.0, 0.0), LF(ang(-1600.0), 5300.0, 0.0, 0.0, 0.0), 19.5)),
         [PL(-150.0, -60.0, 900.0), LF(a_or, OR_H + 300.0, -60.0, -120.0, 40.0)]),
        # takeaway: the climb pauses at the horizon (spotter inset over it)
        (b0("takeaway") + 0.2, 1.0, lin((LF(ang(-5200.0), 7700.0, 0.0, -700.0, 0.0), LF(ang(30000.0), 0.0, 0.0, 0.0, -1200.0), 22.0),
                                        (LF(ang(-5000.0), 7700.0, 0.0, -680.0, 0.0), LF(ang(30000.0), 0.0, 0.0, 0.0, -1200.0), 22.5)),
         []),
        # ... "gliding across the sky": drift towards the station on the horizon
        (st.c_glide - 0.2, 0.9, lin((LF(ang(-2600.0), 7750.0, 0.0, -420.0, 0.0), LF(ang(30000.0), 0.0, 0.0, 0.0, -900.0), 22.0),
                                    (LF(ang(-2450.0), 7750.0, 0.0, -400.0, 0.0), LF(ang(30000.0), 0.0, 0.0, 0.0, -900.0), 22.5)),
         []),
        # outro: back at the station, the capsule on final approach
        (b0("outro") + 0.2, 1.0, lin((SL(-62.0, -40.0, 17.0), SL(-16.0, 0.0, -3.0), 21.0),
                                     (SL(-58.0, -38.0, 16.0), SL(-16.0, 0.0, -3.0), 21.0)), [SL(-600.0, -200.0, 120.0)]),
        # ... "because this week": glide back in to the frame-1 view (loop) as the capsule docks
        (st.c_bec - 0.2, 0.4, lin((SL(-58.0, -38.0, 16.0), SL(-16.0, 0.0, -3.0), 21.0), P1, ease=True), []),
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


P1_DEFAULT = (SL(-8.0, -9.0, 8.0), SL(-9.5, 1.0, -3.0), 20.0)


# ================================================================ materials
def hz_finish(m, shader_out, col=(0.70, 0.80, 0.93, 1.0)):
    """Camera-distance haze whose density is a Value node baked by camera altitude (0 in space)."""
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    cam = N.new("ShaderNodeCameraData")
    val = N.new("ShaderNodeValue")
    val.outputs[0].default_value = 0.0
    mul = N.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    Lk.new(cam.outputs["View Distance"], mul.inputs[0])
    Lk.new(val.outputs[0], mul.inputs[1])
    neg = N.new("ShaderNodeMath")
    neg.operation = "MULTIPLY"
    neg.inputs[1].default_value = -1.0
    Lk.new(mul.outputs[0], neg.inputs[0])
    ex = N.new("ShaderNodeMath")
    ex.operation = "EXPONENT"
    Lk.new(neg.outputs[0], ex.inputs[0])
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    Lk.new(ex.outputs[0], inv.inputs[1])
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = col
    em.inputs["Strength"].default_value = 1.0
    mix = N.new("ShaderNodeMixShader")
    Lk.new(inv.outputs[0], mix.inputs[0])
    Lk.new(shader_out, mix.inputs[1])
    Lk.new(em.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], N.get("Material Output").inputs["Surface"])
    HZ.append(val.outputs[0])
    return m


def _math(N, Lk, op, a, b=None, clamp=False):
    n = N.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            Lk.new(v, n.inputs[i])
    return n.outputs[0]


def _mr(N, Lk, v, a, b, c=0.0, d=1.0):
    n = N.new("ShaderNodeMapRange")
    n.inputs["From Min"].default_value = a
    n.inputs["From Max"].default_value = b
    n.inputs["To Min"].default_value = c
    n.inputs["To Max"].default_value = d
    n.clamp = True
    Lk.new(v, n.inputs["Value"])
    return n.outputs["Result"]


def _mixc(N, Lk, fac, a, b):
    n = N.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.clamp_factor = True
    for sock, v in ((n.inputs["Factor"], fac), (n.inputs["A"], a), (n.inputs["B"], b)):
        if isinstance(v, (tuple, list)):
            sock.default_value = v
        elif isinstance(v, (int, float)):
            sock.default_value = v
        else:
            Lk.new(v, sock)
    return n.outputs["Result"]


def _noise(N, Lk, vec, scale, detail=6.0, rough=0.55, dist=0.0):
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Distortion"].default_value = dist
    Lk.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def earth_mat():
    """Bright Earth from orbit: oceans, land, a desert around the pad, cloud fields (texture turns with a baked
    rotation value = orbital motion), a blue limb tint. Object coords (origin = Earth centre)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("dk_earth")
        tc = N.new("ShaderNodeTexCoord")
        obj = tc.outputs["Object"]
        rot = N.new("ShaderNodeValue")
        rot.outputs[0].default_value = 0.0
        comb = N.new("ShaderNodeCombineXYZ")
        Lk.new(rot.outputs[0], comb.inputs["Y"])
        mp = N.new("ShaderNodeMapping")
        mp.vector_type = "POINT"
        Lk.new(obj, mp.inputs["Vector"])
        Lk.new(comb.outputs[0], mp.inputs["Rotation"])
        mp.inputs["Location"].default_value = (31000.0, 7000.0, -12000.0)
        rv = mp.outputs["Vector"]
        # desert around the pad (fixed coords)
        pad = (math.sin(A_P) * R, 0.0, math.cos(A_P) * R)
        dv = N.new("ShaderNodeVectorMath")
        dv.operation = "DISTANCE"
        Lk.new(obj, dv.inputs[0])
        dv.inputs[1].default_value = pad
        dist = dv.outputs["Value"]
        desert = _mr(N, Lk, dist, 9000.0, 21000.0, 1.0, 0.0)
        clear = _mr(N, Lk, dist, 12000.0, 26000.0, 0.0, 1.0)
        land_n = _noise(N, Lk, rv, 0.000032, 9.0, 0.58, 0.2)
        landm = _mr(N, Lk, land_n, 0.535, 0.55)
        landm = _math(N, Lk, "MAXIMUM", landm, desert)
        coast = _mr(N, Lk, land_n, 0.47, 0.535)
        ocean = _mixc(N, Lk, coast, (0.012, 0.07, 0.24, 1.0), (0.03, 0.26, 0.42, 1.0))
        vn = _noise(N, Lk, rv, 0.00019, 7.0, 0.6)
        ramp = N.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.38, (0.16, 0.30, 0.10, 1.0)
        cr.elements[1].position, cr.elements[1].color = 0.62, (0.52, 0.42, 0.26, 1.0)
        e = cr.elements.new(0.5)
        e.color = (0.30, 0.36, 0.16, 1.0)
        Lk.new(vn, ramp.inputs[0])
        land = _mixc(N, Lk, desert, ramp.outputs["Color"], (0.80, 0.63, 0.42, 1.0))
        base = _mixc(N, Lk, landm, ocean, land)
        # clouds: small fractal cells modulated by a large coverage field, cleared over the desert
        cn = _noise(N, Lk, rv, 0.00021, 11.0, 0.62, 0.35)
        cov = _mr(N, Lk, _noise(N, Lk, rv, 0.000028, 3.0, 0.5), 0.36, 0.62, 0.15, 1.0)
        cl = _mr(N, Lk, cn, 0.50, 0.64)
        cl = _math(N, Lk, "MULTIPLY", cl, cov)
        cl = _math(N, Lk, "MULTIPLY", cl, clear, clamp=True)
        col = _mixc(N, Lk, cl, base, (0.93, 0.95, 0.98, 1.0))
        Lk.new(col, p.inputs["Base Color"])
        rough = _math(N, Lk, "ADD", _math(N, Lk, "MULTIPLY", landm, 0.55), 0.32)
        rough = _math(N, Lk, "MAXIMUM", rough, _math(N, Lk, "MULTIPLY", cl, 1.0))
        Lk.new(rough, p.inputs["Roughness"])
        p.inputs["Specular IOR Level"].default_value = 0.45
        # limb tint (atmosphere seen at grazing angles)
        lw = N.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        f = _math(N, Lk, "POWER", lw.outputs["Facing"], 5.0)
        f = _math(N, Lk, "MULTIPLY", f, 0.55, clamp=True)
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (0.42, 0.64, 1.0, 1.0)
        em.inputs["Strength"].default_value = 1.4
        mix = N.new("ShaderNodeMixShader")
        Lk.new(f, mix.inputs[0])
        Lk.new(p.outputs[0], mix.inputs[1])
        Lk.new(em.outputs[0], mix.inputs[2])
        hz_finish(m, mix.outputs[0])
        return m, rot.outputs[0]
    return _m("earth", mk)


def shell_mat():
    """Atmosphere shell: transparent, blue glow towards grazing angles (limb). Value = overall strength (baked)."""
    def mk():
        m = bpy.data.materials.new("dk_shell")
        m.surface_render_method = "BLENDED"
        m.use_backface_culling = True
        N, Lk = m.node_tree.nodes, m.node_tree.links
        for n in list(N):
            if n.type != "OUTPUT_MATERIAL":
                N.remove(n)
        lw = N.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        val = N.new("ShaderNodeValue")
        val.outputs[0].default_value = 1.0
        f = _math(N, Lk, "POWER", lw.outputs["Facing"], 7.0)
        f = _math(N, Lk, "MULTIPLY", f, val.outputs[0], clamp=True)
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (0.36, 0.62, 1.0, 1.0)
        em.inputs["Strength"].default_value = 2.6
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        Lk.new(f, mix.inputs[0])
        Lk.new(tr.outputs[0], mix.inputs[1])
        Lk.new(em.outputs[0], mix.inputs[2])
        Lk.new(mix.outputs[0], N.get("Material Output").inputs["Surface"])
        return m, val.outputs[0]
    return _m("shell", mk)


def ring_mat(name, color, dashed=False, strength=6.0):
    """Glowing orbit line (torus). Value = visibility 0..1 (baked). dashed: 720 dashes around the planet."""
    def mk():
        m = bpy.data.materials.new(name)
        m.surface_render_method = "BLENDED"
        N, Lk = m.node_tree.nodes, m.node_tree.links
        for n in list(N):
            if n.type != "OUTPUT_MATERIAL":
                N.remove(n)
        val = N.new("ShaderNodeValue")
        val.outputs[0].default_value = 0.0
        a = val.outputs[0]
        if dashed:
            tc = N.new("ShaderNodeTexCoord")
            sep = N.new("ShaderNodeSeparateXYZ")
            Lk.new(tc.outputs["Object"], sep.inputs[0])
            at = _math(N, Lk, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
            ph = _math(N, Lk, "FRACT", _math(N, Lk, "MULTIPLY", at, 720.0 / (2 * math.pi)))
            dash = _math(N, Lk, "LESS_THAN", ph, 0.55)
            a = _math(N, Lk, "MULTIPLY", a, dash)
        em = N.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = color
        em.inputs["Strength"].default_value = strength
        tr = N.new("ShaderNodeBsdfTransparent")
        mix = N.new("ShaderNodeMixShader")
        Lk.new(a, mix.inputs[0])
        Lk.new(tr.outputs[0], mix.inputs[1])
        Lk.new(em.outputs[0], mix.inputs[2])
        Lk.new(mix.outputs[0], N.get("Material Output").inputs["Surface"])
        return m, val.outputs[0]
    return _m(name, mk)


def cells_mat(name, c1, c2, line, metal, rough, cell=(0.55, 0.9), plane="xz"):
    """Solar array: brick-texture cells with dark lines (coords from the object's own mesh)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(tc.outputs["Object"], sep.inputs[0])
        comb = N.new("ShaderNodeCombineXYZ")
        Lk.new(sep.outputs["X"], comb.inputs["X"])
        Lk.new(sep.outputs["Z" if plane == "xz" else "Y"], comb.inputs["Y"])
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0 / cell[0], 1.0 / cell[1], 1.0)
        Lk.new(comb.outputs[0], mp.inputs["Vector"])
        br = N.new("ShaderNodeTexBrick")
        br.offset = 0.0
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.035
        br.inputs["Brick Width"].default_value = 1.0
        br.inputs["Row Height"].default_value = 1.0
        br.inputs["Color1"].default_value = c1
        br.inputs["Color2"].default_value = c2
        br.inputs["Mortar"].default_value = line
        br.inputs["Bias"].default_value = 0.0
        Lk.new(mp.outputs["Vector"], br.inputs["Vector"])
        Lk.new(br.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Metallic"].default_value = metal
        p.inputs["Roughness"].default_value = rough
        S._finish(m, p.outputs[0], haze=False)
        return m
    return _m(name, mk)


def alpha_puff_mat(name, col=(0.96, 0.96, 0.95, 1.0), emis=0.25):
    """Soft white puff (thruster gas / launch smoke): rim fade + noise; Value = alpha (baked)."""
    m, nt, N, Lk, p = S._new_mat(name)
    m.surface_render_method = "DITHERED"
    p.inputs["Base Color"].default_value = col
    p.inputs["Emission Color"].default_value = col
    p.inputs["Emission Strength"].default_value = emis
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    rim = _math(N, Lk, "POWER", _math(N, Lk, "SUBTRACT", 1.0, lw.outputs["Facing"]), 1.4)
    tc = N.new("ShaderNodeTexCoord")
    nz = _noise(N, Lk, tc.outputs["Object"], 0.9, 5.0, 0.6)
    nzr = _mr(N, Lk, nz, 0.3, 0.68, 0.25, 1.3)
    val = N.new("ShaderNodeValue")
    val.outputs[0].default_value = 0.0
    a = _math(N, Lk, "MULTIPLY", _math(N, Lk, "MULTIPLY", rim, nzr), val.outputs[0], clamp=True)
    Lk.new(a, p.inputs["Alpha"])
    S._finish(m, p.outputs[0], haze=False)
    return m, val.outputs[0]


def mats():
    def mk():
        return {
            "white": S.pbr("dk_white", hexc("e4e4df"), 0.5, var=0.05, var_scale=2.5, bump=0.04, haze=False),
            "white2": S.pbr("dk_white2", hexc("f2f2ee"), 0.4, var=0.03, var_scale=1.0, haze=False),
            "grey": S.pbr("dk_grey", hexc("8e9196"), 0.45, metal=0.5, var=0.04, haze=False),
            "dark": S.pbr("dk_dark", hexc("2b2e33"), 0.5, var=0.02, haze=False),
            "gold": S.pbr("dk_gold", hexc("d8a443"), 0.28, metal=0.9, var=0.12, var_scale=6.0, bump=0.15, haze=False),
            "steel": S.pbr("dk_steel", hexc("b5bac0"), 0.3, metal=0.9, var=0.02, haze=False),
            "om": S.pbr("dk_om", hexc("c9cbbd"), 0.55, var=0.05, var_scale=3.0, bump=0.04, haze=False),
            "dm": S.pbr("dk_dm", hexc("9a9c96"), 0.5, metal=0.35, var=0.06, var_scale=3.0, haze=False),
            "shield": S.pbr("dk_shield", hexc("5d4b3c"), 0.8, var=0.08, haze=False),
            "wing": cells_mat("dk_wing", hexc("e0ad48"), hexc("cf9a3a"), hexc("5a3c10"), 0.75, 0.3, (0.55, 0.9), "xz"),
            "wing_s": cells_mat("dk_wing_s", hexc("e0ad48"), hexc("cf9a3a"), hexc("5a3c10"), 0.75, 0.3, (0.55, 0.9), "xy"),
            "panel": cells_mat("dk_panel", hexc("1f3f8a"), hexc("27499a"), hexc("c9ccd6"), 0.4, 0.22, (0.45, 0.45), "xy"),
            "ring_t": S.emis("dk_ring_teal", hexc("39e0cf"), 1.6),
            "latch": S.pbr("dk_latch", hexc("f0b429"), 0.4, metal=0.4, var=0.02, haze=False),
            "burn": S.emis("dk_burn", hexc("cfe4ff"), 14.0),
            "flame": S.emis("dk_flame", hexc("ffd27a"), 22.0),
            "nozzle": S.pbr("dk_nozzle", hexc("3a3533"), 0.4, metal=0.8, var=0.04, haze=False),
            "mk_amber": S.emis("dk_mk_amber", hexc("ffc35a"), 7.0),
            "mk_teal": S.emis("dk_mk_teal", hexc("4cf2e0"), 7.0),
            # pad world (hazed by altitude)
            "sand": hz_finish(*_pbr_raw("dk_sand", hexc("d2b48a"), 0.95, 0.16, 0.012, 0.12)),
            "sand2": hz_finish(*_pbr_raw("dk_sand2", hexc("c49b6c"), 0.95, 0.14, 0.006, 0.1)),
            "hill": hz_finish(*_pbr_raw("dk_hill", hexc("b98a5e"), 0.95, 0.18, 0.004, 0.2)),
            "concrete": hz_finish(*_pbr_raw("dk_conc", hexc("cdc8bd"), 0.85, 0.08, 0.3, 0.05)),
            "road": hz_finish(*_pbr_raw("dk_road", hexc("6a675f"), 0.85, 0.06, 0.4, 0.0)),
            "tower": hz_finish(*_pbr_raw("dk_tower", hexc("c94d36"), 0.6, 0.05, 1.0, 0.0, metal=0.3)),
            "tower2": hz_finish(*_pbr_raw("dk_tower2", hexc("dcdcd6"), 0.5, 0.04, 1.0, 0.0, metal=0.3)),
            "bldg": hz_finish(*_pbr_raw("dk_bldg", hexc("eae6dc"), 0.7, 0.05, 0.5, 0.0)),
            "rocket": S.pbr("dk_rocket", hexc("f3f3ef"), 0.42, var=0.03, var_scale=1.0, haze=False),
            "scrub": hz_finish(*_pbr_raw("dk_scrub", hexc("7d7a4a"), 0.95, 0.15, 2.0, 0.0)),
        }
    return _m("mats", mk)


def _pbr_raw(name, color, rough, var, var_scale, bump, metal=0.0):
    """Principled + noise variation, NOT finished (hz_finish wires the output)."""
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    vec = S._coord(N, Lk, "Object")
    fac, nz = S._noise_var(N, Lk, vec, var_scale, var)
    Lk.new(S._mul_col(N, Lk, color, fac), p.inputs["Base Color"])
    if bump > 0:
        S._bump(N, Lk, nz.outputs["Fac"], p, strength=bump, distance=0.2)
    return m, p.outputs[0]


# ================================================================ world (space <-> sky)
def build_world_shader(sc):
    w = bpy.data.worlds.new("dk_world")
    sc.world = w
    nt = w.node_tree
    N, Lk = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_WORLD":
            N.remove(n)
    tc = N.new("ShaderNodeTexCoord")
    nrm = N.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    Lk.new(tc.outputs["Generated"], nrm.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(nrm.outputs["Vector"], sep.inputs[0])
    z = sep.outputs["Z"]
    fac = N.new("ShaderNodeValue")
    fac.outputs[0].default_value = 0.0
    # day sky gradient
    zz = _mr(N, Lk, z, -0.02, 0.75)
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.70, 0.80, 0.93, 1.0)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.13, 0.33, 0.78, 1.0)
    e = cr.elements.new(0.25)
    e.color = (0.42, 0.60, 0.88, 1.0)
    Lk.new(zz, ramp.inputs[0])
    sky = ramp.outputs["Color"]
    # sun glow in the sky
    sd = N.new("ShaderNodeVectorMath")
    sd.operation = "DOT_PRODUCT"
    Lk.new(nrm.outputs["Vector"], sd.inputs[0])
    el, az = math.radians(SUN_ELEV), math.radians(SUN_AZ)
    sd.inputs[1].default_value = sun_dir_to()
    glow = _math(N, Lk, "POWER", _mr(N, Lk, sd.outputs["Value"], 0.85, 1.0), 6.0)
    sky = _mixc(N, Lk, _math(N, Lk, "MULTIPLY", glow, 0.6), sky, (1.0, 0.97, 0.88, 1.0))
    # space: near-black with stars
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 260.0
    Lk.new(nrm.outputs["Vector"], vor.inputs["Vector"])
    st = _math(N, Lk, "POWER", _mr(N, Lk, vor.outputs["Distance"], 0.06, 0.0), 3.0)
    dens = _mr(N, Lk, _noise(N, Lk, nrm.outputs["Vector"], 3.0, 2.0), 0.45, 0.6, 0.0, 1.0)
    st = _math(N, Lk, "MULTIPLY", st, dens)
    st = _math(N, Lk, "MULTIPLY", st, 1.6)
    space = _mixc(N, Lk, st, (0.0012, 0.0016, 0.004, 1.0), (1.0, 1.0, 1.0, 1.0))
    cam_bg = _mixc(N, Lk, fac.outputs[0], space, sky)
    # lighting environment (non-camera rays): earthshine from below in space, the sky near the ground
    below = _mr(N, Lk, z, 0.1, -0.4)
    env_space = _mixc(N, Lk, below, (0.012, 0.016, 0.03, 1.0), (0.16, 0.24, 0.40, 1.0))
    env = _mixc(N, Lk, fac.outputs[0], env_space, sky)
    lp = N.new("ShaderNodeLightPath")
    col = _mixc(N, Lk, lp.outputs["Is Camera Ray"], env, cam_bg)
    bg = N.new("ShaderNodeBackground")
    Lk.new(col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    Lk.new(bg.outputs[0], N.get("World Output").inputs["Surface"])
    return fac.outputs[0]


def sun_dir_to():
    """unit vector pointing TO the sun (world), matching S.sun_lamp(SUN_ELEV, SUN_AZ)"""
    th = math.radians(90.0 - SUN_ELEV)
    d = (0.0, math.sin(th), -math.cos(th))          # light travel direction before the Z rotation
    az = math.radians(SUN_AZ)
    d = (d[0] * math.cos(az) - d[1] * math.sin(az), d[0] * math.sin(az) + d[1] * math.cos(az), d[2])
    return (-d[0], -d[1], -d[2])


# ================================================================ mesh helpers
def obj(name, bm, mlist, loc=(0, 0, 0), smooth_=False, parent=None):
    return S.obj(name, S.mesh_from_bm(name, bm, mlist, smooth=smooth_), loc, parent=parent)


def _tag(bm, verts, mi):
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mi


def cylx(bm, x0, x1, r, mi=0, seg=32, y=0.0, z=0.0, r2=None, caps=True):
    res = bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                                depth=abs(x1 - x0),
                                matrix=Matrix.Translation(((x0 + x1) / 2.0, y, z)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    _tag(bm, res["verts"], mi)
    return res["verts"]


def cyly(bm, y0, y1, r, mi=0, seg=32, x=0.0, z=0.0):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=abs(y1 - y0),
                                matrix=Matrix.Translation((x, (y0 + y1) / 2.0, z)) @ Matrix.Rotation(-math.pi / 2, 4, "X"))
    _tag(bm, res["verts"], mi)
    return res["verts"]


def cylz(bm, z0, z1, r, mi=0, seg=24, x=0.0, y=0.0, r2=None):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                                depth=abs(z1 - z0), matrix=Matrix.Translation((x, y, (z0 + z1) / 2.0)))
    _tag(bm, res["verts"], mi)
    return res["verts"]


def ell(bm, c, rr, mi=0, seg=24, rings=14):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0,
                                    matrix=Matrix.Translation(c) @ Matrix.Diagonal((rr[0], rr[1], rr[2], 1.0)))
    _tag(bm, res["verts"], mi)
    return res["verts"]


def torus_x(bm, x, R_, r_, mi=0, seg=40, n2=8):
    """ring in the YZ plane (axis = x)"""
    ring = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        cs = []
        for j in range(n2):
            b = 2 * math.pi * j / n2
            rr = R_ + r_ * math.cos(b)
            cs.append(bm.verts.new((x + r_ * math.sin(b), rr * math.cos(a), rr * math.sin(a))))
        ring.append(cs)
    for i in range(seg):
        A, B = ring[i], ring[(i + 1) % seg]
        for j in range(n2):
            f = bm.faces.new((A[j], B[j], B[(j + 1) % n2], A[(j + 1) % n2]))
            f.material_index = mi


# ================================================================ Earth
def build_earth(tl, st, cam_alt):
    padw = OL(A_P, 0.0)
    pad_o = vsub(padw, EC)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=720, v_segments=360, radius=R,
                              matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
    pv = Vector(pad_o)
    kill = [f for f in bm.faces if (f.calc_center_median() - pv).length < 6900.0]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    m, rot = earth_mat()
    e = obj("earth", bm, [m], EC, smooth_=True)
    e.visible_shadow = False
    bake_sock(tl, rot, lambda t: 0.0011 * t, step=3)
    # atmosphere shell (limb glow); fades out as the camera dives inside it
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=360, v_segments=180, radius=R + H_SHELL,
                              matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
    sm, sval = shell_mat()
    sh = obj("shell", bm, [sm], EC, smooth_=True)
    sh.visible_shadow = False
    bake_sock(tl, sval, lambda t: smooth((cam_alt(t) - 1500.0) / 1300.0))


def ground_pt(lx, ly, dz=0.0):
    """point on the sphere (+dz) at pad-local horizontal offset (lx, ly): exact curvature"""
    r = math.hypot(lx, ly)
    if r < 1e-6:
        return PL(0.0, 0.0, dz)
    a = r / R
    d = (lx / r, ly / r)
    u0 = up(A_P)
    f0 = fwd(A_P)
    dirv = (f0[0] * d[0], d[1], f0[2] * d[0])
    p = vadd(vmul(u0, math.cos(a)), vmul(dirv, math.sin(a)))
    return vadd(EC, vmul(p, R + dz))


def build_pad_ground(mt, rng):
    padw = OL(A_P, 0.0)
    bm = bmesh.new()
    rings, seg, RMAX = 70, 160, 7400.0
    rows = []
    for i in range(rings + 1):
        r = RMAX * (i / rings) ** 2.2
        row = []
        for j in range(seg if i > 0 else 1):
            th = 2 * math.pi * j / seg
            lx, ly = r * math.cos(th), r * math.sin(th)
            k = smooth((r - 700.0) / 900.0)
            dz = k * (6.0 * math.sin(lx / 230.0) * math.sin(ly / 310.0) + 3.0 * math.sin(lx / 97.0 + ly / 143.0)
                      + 4.0 * math.sin(ly / 510.0 - lx / 400.0))
            row.append(bm.verts.new(vsub(ground_pt(lx, ly, dz + 0.05), padw)))
        rows.append(row)
    for j in range(seg):
        bm.faces.new((rows[0][0], rows[1][j], rows[1][(j + 1) % seg]))
    for i in range(1, rings):
        A, B = rows[i], rows[i + 1]
        for j in range(seg):
            bm.faces.new((A[j], B[j], B[(j + 1) % seg], A[(j + 1) % seg]))
    obj("desert", bm, [mt["sand"], mt["sand2"]], padw, smooth_=True)
    # hills / mesas
    bm = bmesh.new()
    for i in range(16):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(1600.0, 4200.0)
        if abs(math.sin(a)) < 0.25 and math.cos(a) > 0:     # keep the view straight ahead (+x) open
            a += 0.9
        lx, ly = d * math.cos(a), d * math.sin(a)
        rx, ry, h = rng.uniform(250, 700), rng.uniform(250, 700), rng.uniform(60, 200)
        c = vsub(ground_pt(lx, ly, -25.0), padw)
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                         matrix=Matrix.Translation(c) @ Matrix.Rotation(A_P, 4, "Y") @
                                         Matrix.Diagonal((rx, ry, h, 1.0)))
    obj("hills", bm, [mt["hill"]], padw, smooth_=True)


def build_pad(tl, st, mt, ctx, rng):
    """Launch complex in pad-local coords under a root at the pad (rotated to the local up)."""
    padw = OL(A_P, 0.0)
    root = L.link(bpy.data.objects.new("pad_root", None))
    root.location = padw
    root.rotation_euler = (0.0, A_P, 0.0)
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 0.25), (150.0, 150.0, 0.5), 0)                 # deck
    box(bm, (0.0, 0.0, 3.0), (16.0, 16.0, 6.0), 0)                    # pedestal
    box(bm, (-60.0, 0.0, 0.3), (120.0, 10.0, 0.6), 1)                 # road onto the deck
    box(bm, (-1300.0, 0.0, 0.2), (2400.0, 9.0, 0.4), 1)               # access road
    box(bm, (26.0, 0.0, 0.52), (36.0, 9.0, 0.06), 2)                  # flame trench (dark slot)
    S.obj("deck", S.mesh_from_bm("deck", bm, [mt["concrete"], mt["road"], mt["dark"]]), parent=root)
    # service tower (lattice) at y = +11
    tx, ty, TH = 0.0, 12.5, 78.0
    bm = bmesh.new()
    for sx in (-4.0, 4.0):
        for sy in (-4.0, 4.0):
            box(bm, (tx + sx, ty + sy, TH / 2), (0.7, 0.7, TH), 0)
    z = 4.0
    k = 0
    while z < TH:
        for sx in (-4.0, 4.0):
            box(bm, (tx + sx, ty, z), (0.4, 8.0, 0.4), 0)
        for sy in (-4.0, 4.0):
            box(bm, (tx, ty + sy, z), (8.0, 0.4, 0.4), 0)
        # diagonal braces on the two faces seen from the camera side
        for sx in (-4.0, 4.0):
            res = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=(0.25, 11.3, 0.25), verts=res["verts"])
            bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                             matrix=Matrix.Rotation((1 if k % 2 else -1) * math.atan2(4.0, 8.0), 3, "X"))
            bmesh.ops.translate(bm, vec=(tx + sx, ty, z + 2.0), verts=res["verts"])
            _tag(bm, res["verts"], 0)
        for sy in (-4.0,):
            res = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=(11.3, 0.25, 0.25), verts=res["verts"])
            bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0),
                             matrix=Matrix.Rotation((1 if k % 2 else -1) * math.atan2(4.0, 8.0), 3, "Y"))
            bmesh.ops.translate(bm, vec=(tx, ty + sy, z + 2.0), verts=res["verts"])
            _tag(bm, res["verts"], 0)
        z += 4.0
        k += 1
    for zz in (9.0, 30.0, 47.0, 61.0):
        box(bm, (tx, ty - 7.5, zz), (2.2, 7.0, 1.2), 1)                # service arms towards the rocket
    box(bm, (tx, ty, TH + 1.0), (9.0, 9.0, 2.0), 1)
    cylz(bm, TH + 2.0, TH + 12.0, 0.25, 1, 8, tx, ty)
    S.obj("tower", S.mesh_from_bm("tower", bm, [mt["tower"], mt["tower2"]]), parent=root)
    # lightning masts
    bm = bmesh.new()
    for (mx, my) in ((-45.0, -45.0), (45.0, -45.0), (-45.0, 45.0), (45.0, 45.0)):
        cylz(bm, 0.0, 72.0, 0.5, 0, 10, mx, my, r2=0.2)
    S.obj("masts", S.mesh_from_bm("masts", bm, [mt["tower2"]]), parent=root)
    # buildings around the site
    bm = bmesh.new()
    for (bx, by, sx, sy, sz) in ((-1500.0, 260.0, 90.0, 70.0, 82.0), (-1250.0, -380.0, 60.0, 40.0, 18.0),
                                 (-900.0, 420.0, 40.0, 30.0, 12.0), (-700.0, -300.0, 26.0, 18.0, 9.0),
                                 (-1700.0, -120.0, 50.0, 50.0, 22.0)):
        dz = -(math.hypot(bx, by) ** 2) / (2 * R)
        box(bm, (bx, by, sz / 2 + dz), (sx, sy, sz), 0)
    S.obj("bldgs", S.mesh_from_bm("bldgs", bm, [mt["bldg"]]), parent=root)
    # desert scrub tufts near the pad (tiny dark-olive humps)
    bm = bmesh.new()
    for i in range(500):
        a, d = rng.uniform(0, 6.283), rng.uniform(95.0, 900.0)
        x, y = d * math.cos(a), d * math.sin(a)
        if -500.0 < x < 0.0 and abs(y) < 14.0:
            continue
        r_ = rng.uniform(0.6, 1.8)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0,
                                   matrix=Matrix.Translation((x, y, -(d * d) / (2 * R))) @
                                   Matrix.Diagonal((r_, r_, r_ * 0.5, 1.0)))
    S.obj("scrub", S.mesh_from_bm("scrub", bm, [mt["scrub"]], smooth=True), parent=root)
    build_rocket(tl, st, mt, ctx, root)
    return root


def build_rocket(tl, st, mt, ctx, root):
    rk = L.link(bpy.data.objects.new("rocket", None))
    rk.parent = root
    bm = bmesh.new()
    b0 = 6.0
    cylz(bm, b0 + 1.2, b0 + 40.0, 1.68, 0, 40)                       # core
    cylz(bm, b0 + 40.0, b0 + 41.2, 1.70, 1, 40)                      # interstage band
    cylz(bm, b0 + 41.2, b0 + 50.0, 1.68, 0, 40)                      # second stage
    cylz(bm, b0 + 50.0, b0 + 51.0, 1.68, 0, 40, r2=1.95)
    cylz(bm, b0 + 51.0, b0 + 58.5, 1.95, 0, 40)                      # fairing
    cylz(bm, b0 + 58.5, b0 + 64.0, 1.95, 0, 40, r2=0.35)             # ogive (cone)
    cylz(bm, b0 + 64.0, b0 + 71.0, 0.18, 2, 8, r2=0.1)               # escape tower
    cylz(bm, b0 + 66.0, b0 + 67.5, 0.45, 2, 12, r2=0.18)
    for k in range(4):                                                # boosters
        a = math.pi / 4 + k * math.pi / 2
        bx, by = 2.85 * math.cos(a), 2.85 * math.sin(a)
        cylz(bm, b0 + 1.0, b0 + 17.0, 1.15, 0, 28, bx, by)
        cylz(bm, b0 + 17.0, b0 + 21.5, 1.15, 0, 28, bx, by, r2=0.2)
        cylz(bm, b0 + 9.0, b0 + 9.8, 1.17, 1, 28, bx, by)
        cylz(bm, b0 - 0.4, b0 + 1.0, 0.55, 2, 14, bx, by, r2=0.75)
    cylz(bm, b0 + 20.0, b0 + 21.0, 1.70, 1, 40)
    for k in range(4):
        a = k * math.pi / 2
        cylz(bm, b0 - 0.2, b0 + 1.2, 0.45, 2, 14, 0.8 * math.cos(a), 0.8 * math.sin(a), r2=0.6)
    S.obj("rocket_body", S.mesh_from_bm("rocket_body", bm, [mt["rocket"], mt["dark"], mt["nozzle"]], smooth=False),
          parent=rk)
    empty(ctx, "rocket", (0.0, 0.0, 40.0), parent=rk)
    # flame + launch light
    bm = bmesh.new()
    cylz(bm, b0 - 26.0, b0 - 0.4, 0.4, 0, 20, r2=3.4)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        cylz(bm, b0 - 18.0, b0 - 0.4, 0.3, 0, 14, 2.85 * math.cos(a), 2.85 * math.sin(a), r2=1.4)
    fl = S.obj("flame", S.mesh_from_bm("flame", bm, [mt["flame"]]), parent=rk)
    fl.visible_shadow = False
    ign = st.t_lift - 0.5

    def fsc(t):
        if t < ign:
            return (0.0, 0.0, 0.0)
        k = smooth((t - ign) / 0.35) * (0.92 + 0.08 * math.sin(t * 47.0))
        return (k, k, k * (1.0 + 0.25 * smooth((t - st.t_lift) / 2.0)))
    # flame scales from its top (nozzle): put the origin there
    for v in fl.data.vertices:
        v.co.z -= b0
    fl.location = (0.0, 0.0, b0)
    bake(tl, fl, "scale", fsc, step=1)
    ld = bpy.data.lights.new("launch_l", "POINT")
    ld.color = (1.0, 0.8, 0.55)
    ld.shadow_soft_size = 4.0
    try:
        ld.use_shadow = False
        ld.use_custom_distance = True
        ld.cutoff_distance = 260.0
    except Exception:
        pass
    lo = L.link(bpy.data.objects.new("launch_l", ld))
    lo.parent = rk
    lo.location = (0.0, 0.0, b0 - 8.0)
    bake(tl, ld, "energy", lambda t: 3.0e6 * smooth((t - ign) / 0.4) * (1.0 - smooth((t - st.t_lift - 6.0) / 2.0)),
         step=2)
    bake(tl, rk, "location", lambda t: (0.0, 0.0, st.rocket_z(t)), step=1)
    show_between(tl, rk, None, st.t_lift + 9.0)
    # smoke cloud around the pedestal (white, rolls out after ignition)
    rng = random.Random(31)
    bm = bmesh.new()
    for i in range(70):
        a = rng.uniform(0, 6.283)
        d = rng.uniform(4.0, 38.0)
        z = rng.uniform(0.0, 1.0) ** 1.5 * 16.0
        rr = rng.uniform(5.0, 11.0)
        if math.cos(a) < -0.6 and math.sin(a) < 0.2:      # keep the camera side a little clearer
            d *= 0.6
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                   matrix=Matrix.Translation((d * math.cos(a) + 12.0, d * math.sin(a) * 0.8, z + 3.0)) @
                                   Matrix.Diagonal((rr, rr, rr * 0.8, 1.0)))
    pm, pval = alpha_puff_mat("dk_smoke", (0.93, 0.92, 0.9, 1.0), 0.3)
    sm = S.obj("smoke", S.mesh_from_bm("smoke", bm, [pm], smooth=True), parent=root)
    sm.visible_shadow = False
    sm.location = (12.0, 0.0, 0.0)
    for v in sm.data.vertices:
        v.co.x -= 12.0

    def ssc(t):
        k = max(0.001, smooth((t - ign) / 4.5))
        return (0.25 + 0.95 * k, 0.25 + 0.95 * k, 0.2 + 0.9 * k)
    bake(tl, sm, "scale", ssc, step=2)
    bake_sock(tl, pval, lambda t: 0.95 * smooth((t - ign) / 0.8))
    show_between(tl, sm, ign - 0.1, None)


# ================================================================ station
def build_station(tl, st, mt, ctx, cam_dist):
    root = L.link(bpy.data.objects.new("station", None))
    root.location = SL(0.0, 0.0, 0.0)
    bm = bmesh.new()
    cylx(bm, -6.2, 3.6, 2.1, 0, 40)                                  # core aft (big)
    cylx(bm, 3.6, 4.4, 2.1, 0, 40, r2=1.45)
    cylx(bm, 4.4, 8.6, 1.45, 0, 32)                                  # core fore
    ell(bm, (9.9, 0.0, 0.0), (1.75, 1.75, 1.75), 0, 28, 16)           # node
    cylx(bm, -7.0, -6.2, 1.0, 0, 28)                                  # aft docking adapter
    for xx in (-5.8, -1.0, 3.2):
        cylx(bm, xx - 0.12, xx + 0.12, 2.16, 2, 40)                  # dark rings
    cylx(bm, -4.6, -2.0, 2.15, 1, 40)                                # gold foil band
    for sgn in (-1, 1):                                               # labs (T crossbar)
        cyly(bm, sgn * 1.5, sgn * 3.5, 1.3, 0, 28, 9.9, 0.0)
        y0, y1 = (3.5, 17.6) if sgn > 0 else (-17.6, -3.5)
        cyly(bm, y0, y1, 2.1, 0, 36, 9.9, 0.0)
        for yy in (y0 + 0.5, y1 - 0.5, (y0 + y1) / 2):
            cyly(bm, yy - 0.12, yy + 0.12, 2.16, 2, 36, 9.9, 0.0)
        box(bm, (9.9, sgn * 17.9, 0.0), (1.2, 0.6, 1.2), 3)          # wing mast
        box(bm, (9.9, sgn * 17.9, 0.0), (42.6, 0.35, 0.35), 3)
    # radiators on the core, small antenna dish, robotic arm
    box(bm, (-1.0, 0.0, 2.6), (5.0, 0.12, 2.2), 4)
    box(bm, (1.5, 0.0, -2.55), (3.6, 0.12, 1.8), 4)
    cylz(bm, 2.1, 3.1, 0.12, 3, 8, 6.5, 0.0)
    ell(bm, (6.5, 0.0, 3.3), (0.9, 0.9, 0.25), 4, 18, 8)
    cylx(bm, -4.0, 5.0, 0.16, 4, 10, y=1.2, z=2.25)
    cylx(bm, 5.0, 9.0, 0.16, 4, 10, y=1.2, z=3.2)
    S.obj("st_body", S.mesh_from_bm("st_body", bm, [mt["white"], mt["gold"], mt["dark"], mt["steel"], mt["white2"]],
                                    smooth=True), parent=root)
    # docking ring + guide petals + latches (aft port)
    bm = bmesh.new()
    torus_x(bm, -X_PORT + 0.12, 0.86, 0.1, 0, 48)
    cylx(bm, -X_PORT + 0.05, -6.95, 0.9, 1, 32, caps=False)
    for k in range(3):
        a = math.pi / 2 + k * 2 * math.pi / 3
        c = (-X_PORT - 0.25, 0.72 * math.cos(a), 0.72 * math.sin(a))
        res = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.6, 0.42, 0.06), verts=res["verts"])
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(a - math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, vec=c, verts=res["verts"])
        _tag(bm, res["verts"], 1)
    S.obj("st_port", S.mesh_from_bm("st_port", bm, [mt["steel"], mt["grey"]]), parent=root)
    latches = []
    for k in range(6):
        a = k * math.pi / 3 + 0.3
        bm = bmesh.new()
        box(bm, (-0.05, 0.0, 0.16), (0.3, 0.26, 0.32), 0)
        lo = S.obj("latch%d" % k, S.mesh_from_bm("latch%d" % k, bm, [mt["latch"]]),
                   (-X_PORT + 0.05, 0.96 * math.cos(a), 0.96 * math.sin(a)), (a - math.pi / 2, 0.0, 0.0), parent=root)
        latches.append(lo)

    def lat(t):
        """1 = closed (flat), 0 = open (raised): closed at frame 1, open while the capsule is away,
        close on "latches" (contact beat) and again on the outro "nudge" (loop back to frame 1)"""
        if t < st.c_rw0:
            k = 1.0
        elif t < st.c_latch:
            k = 1.0 - smooth((t - st.c_rw0) / 0.5)
        elif t < st.c_rw1:
            k = smooth((t - st.c_latch) / 0.5)
        elif t < st.c_nudge2:
            k = 1.0 - smooth((t - st.c_rw1) / 0.5)
        else:
            k = smooth((t - st.c_nudge2) / 0.5)
        return (1.0, 1.0, 0.45 + 0.9 * (1.0 - k))
    for lo in latches:
        bake(tl, lo, "scale", lat, step=2)
    # gold solar wings: lab ends (fore + aft of each mast) and two smaller ones on the core
    bm = bmesh.new()
    for sgn in (-1, 1):
        for (x0, x1) in ((-11.4, 8.6), (11.2, 31.2)):
            for seg in range(4):
                xa = x0 + seg * (x1 - x0) / 4.0 + 0.15
                xb = x0 + (seg + 1) * (x1 - x0) / 4.0 - 0.15
                box(bm, ((xa + xb) / 2, sgn * 17.9, 0.0), (xb - xa, 0.05, 4.6), 0)
    S.obj("st_wings", S.mesh_from_bm("st_wings", bm, [mt["wing"]]), parent=root)
    bm = bmesh.new()
    for sgn in (-1, 1):
        for seg in range(3):
            ya = 2.4 + seg * 2.6
            box(bm, (0.2, sgn * (ya + 1.2), 0.0), (2.6, 2.4, 0.05), 0)
        box(bm, (0.2, sgn * 6.0, 0.0), (0.2, 7.6, 0.12), 1)
    S.obj("st_wings_s", S.mesh_from_bm("st_wings_s", bm, [mt["wing_s"], mt["steel"]]), parent=root)
    empty(ctx, "station", (2.0, 0.0, 1.5), parent=root)
    empty(ctx, "port", (-X_PORT + 0.1, 0.0, 0.95), parent=root)
    # far marker glow (only when the camera is km away)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=24.0)
    mk = obj("st_marker", bm, [mt["mk_amber"]], SL(2.0, 0.0, 0.0))
    mk.visible_shadow = False
    def msc(t):
        d = cam_dist(t, SL(0, 0, 0))
        k = max(0.0, smooth((d - 900.0) / 900.0)) * min(1.0, max(0.25, 0.0028 * d / 24.0))
        return (k, k, k)
    bake(tl, mk, "scale", msc, step=2)
    return root


# ================================================================ capsule + last stage
def build_capsule(tl, st, mt, ctx, cam_dist):
    root = L.link(bpy.data.objects.new("capsule", None))
    bm = bmesh.new()
    cylx(bm, -3.0, -0.35, 1.4, 0, 36)                                # service module
    cylx(bm, -3.25, -3.0, 1.45, 3, 36, r2=1.4)
    cylx(bm, -2.4, -1.3, 1.42, 4, 36)                                # gold band
    cylx(bm, -0.35, -0.25, 1.32, 2, 36)                              # heat shield edge
    cylx(bm, -0.25, 1.95, 1.27, 1, 36, r2=0.92)                      # descent module (bell)
    ell(bm, (3.15, 0.0, 0.0), (1.45, 1.12, 1.12), 0, 28, 16)          # orbital module
    cylx(bm, 1.85, 2.15, 0.75, 3, 24)
    cylx(bm, 4.35, L_NOSE - 0.02, 0.56, 3, 24)                       # docking adapter
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        cylx(bm, -3.75, -3.25, 0.32, 5, 14, y=0.75 * math.cos(a), z=0.75 * math.sin(a), r2=0.16)
    S.obj("cap_body", S.mesh_from_bm("cap_body", bm, [mt["white"], mt["dm"], mt["shield"], mt["steel"], mt["gold"],
                                                       mt["nozzle"]], smooth=True), parent=root)
    bm = bmesh.new()
    torus_x(bm, L_NOSE - 0.1, 0.6, 0.075, 0, 40)
    S.obj("cap_ring", S.mesh_from_bm("cap_ring", bm, [mt["steel"]]), parent=root)
    # solar panels on hinges (fold = scale towards the hinge)
    hinges = []
    for sgn in (-1, 1):
        h = L.link(bpy.data.objects.new("hinge%d" % sgn, None))
        h.parent = root
        h.location = (-1.75, sgn * 1.42, 0.0)
        bm = bmesh.new()
        for seg in range(3):
            ya = 0.25 + seg * 2.25
            box(bm, (0.0, sgn * (ya + 1.05), 0.0), (2.0, 2.1, 0.04), 0)
        box(bm, (0.0, sgn * 3.6, 0.0), (0.12, 7.2, 0.08), 1)
        S.obj("panel%d" % sgn, S.mesh_from_bm("panel%d" % sgn, bm, [mt["panel"], mt["steel"]]), parent=h)
        hinges.append(h)
        bake(tl, h, "scale", lambda t: (1.0, max(0.04, st.panels(t)), 1.0), step=2)
    # thruster puffs (RCS) during the final approach and the outro approach
    rng = random.Random(41)
    puffs = []
    times = []
    t = st.t_c + 0.8
    while t < st.c_nudge - 0.2:
        times.append(t)
        t += rng.uniform(0.7, 1.3)
    t = st.c_tell
    while t < st.c_nudge2 - 0.3:
        times.append(t)
        t += rng.uniform(0.8, 1.4)
    for i, t0 in enumerate(times):
        side = 1 if i % 2 else -1
        pos = (3.3, side * 1.05, 0.55 if i % 3 else -0.6)
        m, val = alpha_puff_mat("dk_puff%d" % i)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        po = S.obj("puff%d" % i, S.mesh_from_bm("puff%d" % i, bm, [m], smooth=True), pos, parent=root)
        po.visible_shadow = False
        d = (0.0, side * 1.0, 0.25 if i % 3 else -0.25)

        def pl(t, pos=pos, d=d, t0=t0):
            s = max(0.0, min(1.2, t - t0))
            return (pos[0] - 0.4 * s, pos[1] + d[1] * 1.6 * s, pos[2] + d[2] * 1.6 * s)

        def ps(t, t0=t0):
            if t < t0 or t > t0 + 1.2:
                return (0.0, 0.0, 0.0)
            k = 0.15 + 0.85 * smooth((t - t0) / 0.6)
            return (k * 0.7, k * 0.9, k * 0.7)
        bake(tl, po, "location", pl, step=1)
        bake(tl, po, "scale", ps, step=1)
        bake_sock(tl, val, lambda t, t0=t0: 0.85 * smooth((t - t0) / 0.12) * (1.0 - smooth((t - t0 - 0.2) / 0.9)),
                  step=1)
    # engine burn (chase "fires its engines") + a puff
    bm = bmesh.new()
    cylx(bm, -10.5, -3.6, 1.3, 0, 20, r2=0.35)
    bo = S.obj("burn", S.mesh_from_bm("burn", bm, [mt["burn"]]), parent=root)
    bo.visible_shadow = False
    for v in bo.data.vertices:
        v.co.x += 3.6
    bo.location = (-3.6, 0.0, 0.0)
    bake(tl, bo, "scale", lambda t: (lambda k: (max(0.0, k * (0.9 + 0.1 * math.sin(t * 40.0))), k, k))(st.burn(t)), step=1)
    ld = bpy.data.lights.new("burn_l", "POINT")
    ld.color = (0.8, 0.9, 1.0)
    try:
        ld.use_shadow = False
        ld.use_custom_distance = True
        ld.cutoff_distance = 40.0
    except Exception:
        pass
    lo = L.link(bpy.data.objects.new("burn_l", ld))
    lo.parent = root
    lo.location = (-6.0, 0.0, 0.0)
    bake(tl, ld, "energy", lambda t: 2.0e4 * st.burn(t), step=2)
    # pose: orbital coords (tangent to the orbit); hidden while the camera is at the pad
    def cl(t):
        return st.cap_world(t)[0]

    def cr(t):
        return (0.0, st.cap_world(t)[1], 0.0)
    bake(tl, root, "location", cl, step=1)
    bake(tl, root, "rotation_euler", cr, step=2)
    bake(tl, root, "scale", lambda t: (1.0, 1.0, 1.0) if st.cap_visible(t) else (0.0, 0.0, 0.0), interp="CONSTANT",
         step=1)
    empty(ctx, "capsule", (0.0, 0.0, 1.6), parent=root)
    # far marker
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=18.0)
    mk = obj("cap_marker", bm, [mt["mk_teal"]], (0, 0, 0))
    mk.parent = root
    mk.visible_shadow = False
    def csc(t):
        if not st.cap_visible(t):
            return (0.0, 0.0, 0.0)
        d = cam_dist(t, st.cap_world(t)[0])
        k = max(0.0, smooth((d - 900.0) / 900.0)) * min(1.0, max(0.3, 0.0028 * d / 18.0))
        return (k, k, k)
    bake(tl, mk, "scale", csc, step=2)
    return root


def build_stage(tl, st, mt, ctx):
    root = L.link(bpy.data.objects.new("stage", None))
    bm = bmesh.new()
    cylx(bm, -13.4, -3.7, 1.68, 0, 40)
    cylx(bm, -6.0, -5.2, 1.70, 1, 40)
    cylx(bm, -3.7, -3.3, 1.68, 2, 40, r2=1.45)
    cylx(bm, -15.2, -13.4, 1.0, 2, 24, r2=0.4)
    S.obj("stage_body", S.mesh_from_bm("stage_body", bm, [mt["rocket"], mt["dark"], mt["nozzle"]]), parent=root)
    empty(ctx, "stage", (-9.0, 0.0, -1.5), parent=root)

    def sl(t):
        x, h, y = st.cap(t)
        s = st.sep(t)
        return OL(ang(x - s), h - 0.12 * s, y - 0.05 * s)

    def sr(t):
        x, h, y = st.cap(t)
        s = st.sep(t)
        return (0.03 * s, ang(x - s) - 0.012 * s, 0.02 * s)
    bake(tl, root, "location", sl, step=1)
    bake(tl, root, "rotation_euler", sr, step=2)
    show_between(tl, root, st.c_rw2 + 0.45, st.t_pad + 0.9)


# ================================================================ orbit lines
def ring_obj(name, Rr, w, seg=2880, n2=6):
    """torus in its local XY plane (object at the Earth centre, rotated 90 deg about X -> the orbit plane XZ)"""
    bm = bmesh.new()
    ring = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        cs = []
        for j in range(n2):
            b = 2 * math.pi * j / n2
            rr = Rr + w * math.cos(b)
            cs.append(bm.verts.new((rr * ca, rr * sa, w * math.sin(b))))
        ring.append(cs)
    for i in range(seg):
        A, B = ring[i], ring[(i + 1) % seg]
        for j in range(n2):
            bm.faces.new((A[j], B[j], B[(j + 1) % n2], A[(j + 1) % n2]))
    o = S.obj(name, S.mesh_from_bm(name, bm, []), EC, (math.pi / 2, 0.0, 0.0))
    o.visible_shadow = False
    return o


def build_rings(tl, st, ctx):
    out = []
    for name, h, col, w in (("ring_st", H_S, (1.0, 0.72, 0.22, 1.0), 10.0), ("ring_cap", H_C, (0.25, 0.95, 0.85, 1.0), 10.0)):
        o = ring_obj(name, R + h, w)
        m, val = ring_mat("dk_" + name, col, False, 5.0)
        o.data.materials.append(m)
        bake_sock(tl, val, lambda t: 0.9 * st.rings(t))
        out.append(o)
    o = ring_obj("path", R + H_S, 30.0, 5760)
    m, val = ring_mat("dk_path", (1.0, 0.62, 0.12, 1.0), True, 4.0)
    o.data.materials.append(m)
    bake_sock(tl, val, lambda t: st.path(t))
    bake(tl, o, "rotation_euler", lambda t: (math.pi / 2 + st.path_phi(t), 0.0, 0.0), step=2)
    a = A_P + 0.085
    e = L.link(bpy.data.objects.new("anc_pathpt", None))
    e.parent = o
    e.location = (math.sin(a) * (R + H_S), math.cos(a) * (R + H_S), 0.0)
    S.anchor(ctx, "path", e)
    return out


# ================================================================ BUILDER
def b_docking_oneshot(ctx, p):
    tl = TL(ctx)
    st = Story(tl)
    st.P1 = tuple(p.get("P1", P1_DEFAULT))
    sc = ctx.scene
    HZ.clear()
    L.fog(0.0, S.HAZE)
    fac_sock = build_world_shader(sc)
    S.sun_lamp(SUN_ELEV, SUN_AZ, float(p.get("sun", 4.2)))
    spots = route(tl, st)
    T_end = tl.t_of_G(tl.total)

    def cam_at(t):
        return camera_at(spots, t, T_end)

    def cam_alt(t):
        return alt_of(cam_at(t)[0])

    def cam_dist(t, q):
        return vlen(vsub(cam_at(t)[0], q))
    mt = mats()
    rng = random.Random(p.get("seed", 28))
    build_earth(tl, st, cam_alt)
    build_pad_ground(mt, random.Random(5))
    build_pad(tl, st, mt, ctx, random.Random(9))
    build_station(tl, st, mt, ctx, cam_dist)
    build_capsule(tl, st, mt, ctx, cam_dist)
    build_stage(tl, st, mt, ctx)
    build_rings(tl, st, ctx)
    # sky / haze by camera altitude
    bake_sock(tl, fac_sock, lambda t: smooth((2300.0 - cam_alt(t)) / 1900.0))
    for sock in HZ:
        bake_sock(tl, sock, lambda t: (1.0 / 6500.0) * smooth((1600.0 - cam_alt(t)) / 1300.0), step=3)
    cam = ctx.camera((0, 0, H_S), target=(10, 0, H_S), lens=22)
    cam.data.clip_end = 400000.0

    def near(t):
        c = cam_at(t)[0]
        ds = [vlen(vsub(c, SL(0, 0, 0))) - 30.0, max(1.0, alt_of(c))]
        if st.cap_visible(t):
            ds.append(vlen(vsub(c, st.cap_world(t)[0])) - 8.0)
        return max(1.0, min(ds))
    bake(tl, cam, "location", lambda t: cam_at(t)[0])
    bake(tl, ctx.cam_target, "location", lambda t: cam_at(t)[1])
    bake(tl, cam.data, "lens", lambda t: cam_at(t)[2])
    bake(tl, cam.data, "clip_start", lambda t: max(0.05, min(40.0, 0.02 * near(t))))
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 docking] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 docking] beat %d (%s): global frames %d-%d" % (
        tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1, tl.off[tl.k] + tl.n[tl.k]))


S.V2_BUILDERS.update({"docking_oneshot": b_docking_oneshot})

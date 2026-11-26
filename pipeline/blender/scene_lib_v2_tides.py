"""v2 one-shot coastal-town builder ("king tides", WJH 27 Nov 2026 #2, myth vs reality). Registers into
scene_lib_v2.V2_BUILDERS as `tides_oneshot`.

Same pattern as scene_lib_v2_campus.py: ONE builder for every beat. Each beat builds the identical bright seaside
town and keys ALL animation (camera, sea level, overtopping water, props) on the GLOBAL episode timeline read from
WORKDIR/audio/timings.json + WORKDIR/captions.json, so the finished video is one continuous camera through one world:
slow drifts at each spot, fast eased whips (EEVEE motion blur) between spots, and a backout that ends on the frame-1
view (loop). Global frame G of local frame f in beat k: G = off_k + f. Word cues: G = 1 + t * fps.

World (north = +Y; the sea is north of the seawall, the sun in the south, so most cameras look north):
  a sunny waterfront: shop row with awnings, a road, a palm promenade and a flat-topped seawall (top z = WALL_TOP);
  the sea north of it (one plane whose height is the episode's sea level); a pier with a striped tide-gauge post
  (bands only, no numbers); a huge pale daytime moon low over the horizon (due north); a grey storm bank far
  offshore (north-east) with a sea "dome" (low pressure) and glowing wind arrows; a side street that climbs a gentle
  hill (car reverses up it in the takeaway); a blank amber road sign (its words are a 2D label). Headlands, houses,
  trees, hills. No people, no logos, no 3D text (all text = 2D overlays). Nothing graphic: only a shallow sheet of
  water on a road.

Beats it expects (ids): hook, question, myth_wave, myth_storm, myth_alone, stack, myth_over, takeaway, outro.
Missing cue words fall back to a fraction of their beat, so the builder never fails on a re-voiced beat.
"""
import json
import math
import os
import random

import bpy
import bmesh
from mathutils import Matrix

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc
import scene_lib_v2_city as C
import scene_lib_v2_market as M
import scene_lib_v2_sea as SEA
from scene_lib_v2_winter import set_keys

# ---------------------------------------------------------------- layout
WALL_TOP = 1.3
WALL_Y1 = 1.2                    # sea face of the seawall (landward face at y = 0)
PROM_Y = (-7.0, 0.0)             # promenade (paving)
ROAD_Y = (-19.0, -7.0)
WALK_Y = (-23.0, -19.0)
SHOP_Y = -26.0                   # shop fronts
PIER_X, PIER_W, PIER_Y1, DECK_Z = 60.0, 7.0, 160.0, 2.0
GAUGE = (55.3, 40.0)             # striped tide-gauge post, just off the pier's west edge
MOON = (300.0, 6000.0, 560.0)
MOON_R = 520.0
STORM = (900.0, 1500.0)
DOME = (850.0, 1380.0)
SIDE_X = -40.0                   # side street that climbs the hill (takeaway)
SIDE2_X = 100.0
CAR0 = (-40.0, -10.5)
CAR_Y1 = -50.0
SIGN = (-34.0, -7.4)
SPILL_LEN = 21.0                 # flood sheet length (m) at extent 1.0
STORM_CAM = (68.0, 158.0, 26.0)  # where the wind arrows are built to face
EXT = 6000.0

P1 = ((22.0, -18.0, 5.0), (25.0, 6.0, 1.0), 24.0)   # frame-1 view (loc, target, lens); the backout ends here

_M = {}


def _m(name, fn):
    if name not in _M:
        _M[name] = fn()
    return _M[name]


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def smoother(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


# ---------------------------------------------------------------- tuple vector maths (pure python: testable)
def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vmul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def vlen(a):
    return math.sqrt(vdot(a, a))


def vnorm(a):
    n = vlen(a) or 1.0
    return vmul(a, 1.0 / n)


def vlerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


def curve(keys):
    """keys [(t, v)] -> fn(t): smoothstep between consecutive keys, clamped outside. Times are forced to increase."""
    ks = []
    for t, v in keys:
        if ks and t <= ks[-1][0]:
            t = ks[-1][0] + 0.05
        ks.append((t, v))

    def fn(t):
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
            if t <= t1:
                return v0 + (v1 - v0) * smooth((t - t0) / (t1 - t0))
        return ks[-1][1]
    return fn


def ground_z(y):
    """Town ground: flat on the waterfront, climbs a gentle hill south of the shops (side street = 'higher ground')."""
    if y >= -27.0:
        return 0.0
    if y >= -57.0:
        return 4.5 * smooth((-27.0 - y) / 30.0)
    return 4.5 + min(40.0, (-57.0 - y) * 0.03)


# ================================================================ global timeline
class TL:
    """Global timeline: beat frame offsets + every spoken word (absolute seconds). (Same as the campus builder.)"""

    def __init__(self, ctx, workdir=None):
        wd = workdir or os.path.dirname(S.TEX["dir"].rstrip("/"))
        tm = json.load(open(os.path.join(wd, "audio", "timings.json")))["beats"]
        cp = os.path.join(wd, "captions.json")
        self.words = json.load(open(cp))["words"] if os.path.exists(cp) else []
        self.fps = ctx.fps
        self.beats = tm
        self.n = [int(round(b["duration"] * ctx.fps)) for b in tm]
        self.off = [sum(self.n[:i]) for i in range(len(tm))]
        self.k = min(range(len(tm)), key=lambda i: abs(tm[i]["start"] - ctx.beat_start))
        self.total = sum(self.n)
        self.T = self.total / float(self.fps)

    def lf(self, G):
        return G - self.off[self.k]

    def G(self, t):
        return 1.0 + t * self.fps

    def t_of_G(self, G):
        return (G - 1.0) / self.fps

    def bstart(self, bid):
        for i, b in enumerate(self.beats):
            if b["id"] == bid:
                return self.off[i] / float(self.fps)
        raise KeyError(bid)

    def bend(self, bid):
        for i, b in enumerate(self.beats):
            if b["id"] == bid:
                return (self.off[i] + self.n[i]) / float(self.fps)
        raise KeyError(bid)

    def cue(self, bid, word, frac=0.5, nth=0):
        w = word.lower()
        hits = [x for x in self.words if x.get("beat") == bid and x["norm"].startswith(w)]
        if len(hits) > nth:
            return hits[nth]["start"]
        a, b = self.bstart(bid), self.bend(bid)
        return a + frac * (b - a)

    def frames(self, pad=3):
        a = self.off[self.k] + 1 - pad
        b = self.off[self.k] + self.n[self.k] + pad
        return list(range(a, b + 1))


def bake(tl, o, path, fn, interp="LINEAR", step=1):
    """Key o.path = fn(global_seconds) on every frame of this beat (+ pad)."""
    Gs = tl.frames()[::step]
    if Gs[-1] != tl.frames()[-1]:
        Gs.append(tl.frames()[-1])
    vals = []
    for G in Gs:
        v = fn(tl.t_of_G(G))
        vals.append(tuple(v) if hasattr(v, "__len__") else (v,))
    set_keys(o, path, [tl.lf(G) for G in Gs], vals, interp)


def bake_sock(tl, sock, fn, step=2):
    Gs = tl.frames()[::step] + [tl.frames()[-1]]
    for G in Gs:
        L.kf_socket(sock, tl.lf(G), fn(tl.t_of_G(G)), "LINEAR")


# ================================================================ story curves (global seconds)
class Story:
    """Every animated quantity as a function of global time, derived from the beat/word timings."""

    def __init__(self, tl):
        c, b0, b1 = tl.cue, tl.bstart, tl.bend
        self.T = tl.T
        t_q, t_w, t_a, t_k = b0("question"), b0("myth_wave"), b0("myth_alone"), b0("stack")
        t_o, t_out = b0("myth_over"), b0("outro")
        self.c_moon = c("myth_wave", "moon", 0.62)
        self.c_low = c("myth_storm", "low", 0.7)
        self.c_wind = c("myth_storm", "onshore", 0.85)
        self.c_warm = c("myth_alone", "warm", 0.75)
        c_king, c_storm = c("stack", "king", 0.22), c("stack", "storm", 0.36)
        self.c_tog = c("stack", "together", 0.72)
        self.c_over = c("stack", "over", 0.9)
        self.c_pass = c("myth_over", "passes", 0.22)
        self.c_each = c("stack", "each", 0.45)
        self.c_move = b0("takeaway") + 0.4
        self.c_never = c("takeaway", "never", 0.75)
        self.c_bec = c("outro", "because", 0.75)
        T = self.T
        # sea level (z of the sea plane). Wall top = 1.3: > ~1.32 the sea pours over the wall.
        self.sea = curve([
            (0.0, 1.45), (t_q + 0.2, 1.45), (t_q + 1.6, 1.30),          # hook: over the wall -> question: level
            (t_w - 0.45, 1.30), (t_w + 0.1, -0.10), (t_w + 1.0, -0.10),  # whip to the gauge (unseen drop)
            (self.c_moon, 0.75),                                         # "rising quietly over hours" up the bands
            (b0("myth_storm"), 0.80), (t_a - 0.4, 0.85),
            (self.c_warm - 0.2, 0.85), (self.c_warm + 2.0, 1.02),        # warm water takes up more room
            (c_king - 0.1, 1.02), (c_king + 0.8, 1.12),                  # + king tide
            (c_storm - 0.1, 1.12), (c_storm + 0.7, 1.24),                # + storm
            (self.c_tog + 0.2, 1.30),                                    # brimming level with the wall
            (self.c_over - 0.15, 1.30), (self.c_over + 0.6, 1.45),       # ...over the wall
            (self.c_pass, 1.45), (self.c_pass + 3.5, 0.95),              # drains back
            (t_out + 0.6, 0.95), (self.c_bec - 0.8, 1.45), (T + 1.0, 1.45)])  # rises again -> frame-1 state
        # flood sheet on the street, 0..1 of SPILL_LEN (frame 1 = 0.35, spreading)
        self.flood = curve([
            (0.0, 0.35), (b1("hook") - 0.5, 1.0), (t_w - 0.45, 1.0), (t_w + 0.1, 0.0),
            (self.c_over + 0.2, 0.0), (t_o + 0.2, 0.9), (self.c_pass + 0.3, 1.0), (self.c_pass + 4.0, 0.35),
            (T + 1.0, 0.35)])
        self.warm = curve([(self.c_warm - 0.3, 0.0), (self.c_warm + 1.8, 1.0), (self.c_pass, 1.0),
                           (self.c_pass + 3.5, 0.0)])
        self.dome = curve([(self.c_low - 0.2, 0.04), (self.c_low + 1.8, 1.0), (t_o, 1.0), (t_o + 2.0, 0.04)])
        self.wind_on = (self.c_wind - 0.5, b1("myth_storm") + 0.6)
        self.car_y = curve([(self.c_move, CAR0[1]), (max(self.c_move + 6.0, self.c_never + 1.5), CAR_Y1)])
        self.sign_on = self.c_never - 0.3

    def pour(self, t):
        return smooth((self.sea(t) - 1.31) / 0.12)


# ================================================================ camera route (pure python)
def lin(a, b, ease=False):
    def f(t, u):
        if ease:
            u = smoother(u)
        return vlerp(a[0], b[0], u), vlerp(a[1], b[1], u), a[2] + (b[2] - a[2]) * u
    return f


def route(tl, st):
    """Spots: (t_whip_centre, whip_duration, pose_fn(t, u) -> (loc, tgt, lens), waypoints between spots)."""
    c, b0 = tl.cue, tl.bstart
    moon_hi = (MOON[0], MOON[1], MOON[2] + 160.0)   # aim a bit above the moon: it sits below the caption band
    wall_end = ((20.4, -10.5, 2.6), (24.0, 12.0, 1.0), 26.0)
    spots = [
        # hook: frame-1 view, water sliding over the wall onto the sunny street, moon on the horizon
        (0.0, 0.0, lin(P1, ((23.2, -17.0, 4.6), (25.6, 6.0, 1.05), 25.0)), []),
        # hook: close on the overtopping (hero 1)
        (c("hook", "from", 0.5), 0.8, lin(((8.5, -9.0, 1.6), (12.0, 4.0, 1.2), 28.0),
                                         ((9.6, -8.2, 1.55), (12.4, 4.0, 1.2), 29.0)), [(15.0, -14.0, 3.0)]),
        # question: along the promenade, sea level with the wall top
        (b0("question"), 0.75, lin(((-14.0, -3.5, 2.4), (6.0, 2.5, 1.0), 26.0),
                                   ((-13.0, -3.2, 2.35), (6.0, 2.5, 1.0), 27.0)), [(-4.0, -7.0, 2.6)]),
        # myth 1: on the pier beside the striped tide gauge (water creeps up the bands)
        (b0("myth_wave"), 0.85, lin(((59.6, 29.0, 3.7), (GAUGE[0], GAUGE[1], 0.6), 30.0),
                                    ((59.4, 30.6, 3.6), (GAUGE[0], GAUGE[1], 0.75), 32.0)),
         [(18.0, -3.0, 4.5), (50.0, 0.0, 4.6), (59.5, 14.0, 4.2)]),
        # ... tilt up to the huge moon
        (st.c_moon - 0.2, 0.9, lin(((59.4, 31.0, 3.7), moon_hi, 38.0), ((59.4, 31.8, 3.8), moon_hi, 46.0)), []),
        # myth 2: crane up over the pier end, the storm bank offshore
        (b0("myth_storm"), 0.8, lin(((64.0, 150.0, 24.0), (STORM[0], STORM[1], 90.0), 28.0),
                                    ((66.5, 156.0, 25.5), (STORM[0], STORM[1], 90.0), 30.0)), [(61.0, 90.0, 12.0)]),
        # ... "the moon's work, on the calendar": ease a little wider
        (c("myth_storm", "calendar", 0.35), 0.6, lin(((67.0, 157.0, 26.0), (STORM[0] - 60.0, STORM[1], 70.0), 26.0),
                                                     ((68.0, 159.0, 26.5), (STORM[0] - 60.0, STORM[1], 70.0), 27.0)),
         []),
        # ... low pressure dome + onshore wind arrows
        (st.c_low - 0.2, 0.7, lin(((69.0, 163.0, 27.5), (DOME[0], DOME[1], 25.0), 40.0),
                                  ((71.0, 169.0, 28.5), (DOME[0], DOME[1], 25.0), 43.0)), []),
        # myth 3: down at the waterline by the gauge
        (b0("myth_alone"), 0.85, lin(((48.6, 31.0, 1.95), (GAUGE[0], GAUGE[1], 0.6), 28.0),
                                     ((49.2, 32.0, 2.0), (GAUGE[0], GAUGE[1], 0.65), 29.0)),
         [(62.0, 110.0, 16.0), (52.0, 50.0, 4.0)]),
        # ... "This time": other side of the gauge, town behind
        (c("myth_alone", "this", 0.45), 0.7, lin(((47.0, 42.0, 2.4), (GAUGE[0], 38.5, 0.9), 28.0),
                                                ((46.6, 43.0, 2.5), (GAUGE[0], 38.5, 0.9), 29.0)), []),
        # ... warm water: wider, the sea turns warm
        (st.c_warm - 0.2, 0.8, lin(((45.5, 25.0, 4.8), (75.0, 95.0, 0.0), 24.0),
                                   ((45.0, 23.8, 5.2), (75.0, 95.0, 0.0), 25.0)), []),
        # stack: the gauge again as the sea climbs (2D meter stacks)
        (b0("stack"), 0.7, lin(((50.2, 30.0, 2.6), (GAUGE[0], GAUGE[1], 1.0), 30.0),
                               ((50.8, 31.0, 2.5), (GAUGE[0], GAUGE[1], 1.05), 31.0)), []),
        # ... ride back in just above the water: brimming level with the wall, huge moon (hero 2)
        (st.c_each - 0.25, 0.8, lin(((30.0, -4.0, 1.75), (36.0, 40.0, 2.1), 40.0),
                                   ((30.3, -3.4, 1.72), (36.0, 40.0, 2.1), 42.0)), [(42.0, 12.0, 2.3)]),
        # myth 4: high over the street, the water drains back
        (b0("myth_over"), 0.8, lin(((-28.0, -17.0, 12.0), (6.0, 2.0, 0.5), 24.0),
                                   ((-25.5, -15.0, 11.5), (6.0, 2.0, 0.5), 25.0)), [(10.0, -16.0, 6.0)]),
        # ... "Forecasters expect another round": up to the moon
        (c("myth_over", "forecasters", 0.55) - 0.1, 0.75,
         lin(((-25.3, -14.8, 11.5), moon_hi, 34.0), ((-25.0, -14.4, 11.4), moon_hi, 38.0)), []),
        # takeaway: the car reverses up the side street to higher ground
        (b0("takeaway"), 0.8, lin(((-37.5, -2.0, 3.5), (SIDE_X - 0.5, -30.0, 1.5), 26.0),
                                  ((-37.2, -2.6, 3.45), (SIDE_X - 0.5, -31.0, 1.6), 26.5)), [(-20.0, -14.0, 6.0)]),
        # ... the "road flooded" sign lights
        (st.c_never - 0.1, 0.7, lin(((-26.5, -16.5, 2.2), (SIGN[0], SIGN[1], 1.7), 32.0),
                                    ((-27.2, -16.8, 2.2), (SIGN[0], SIGN[1], 1.7), 33.0)), []),
        # outro: by the wall as the sea climbs back
        (b0("outro"), 0.85, lin(((19.0, -8.6, 2.4), (23.0, 12.0, 1.0), 26.0), wall_end), [(0.0, -12.0, 3.0)]),
        # ... backout to the frame-1 view (loop)
        (st.c_bec - 0.4, 0.4, lin(wall_end, P1, ease=True), []),
    ]
    # keep whips ordered and non-overlapping even on odd timings
    out = []
    for s in spots:
        if out:
            ptc, pwd = out[-1][0], out[-1][1]
            lo = ptc + pwd / 2.0 + s[1] / 2.0 + 1.0
            if s[0] < lo:
                s = (lo,) + tuple(s[1:])
        out.append(s)
    return out


def _slerp(d0, d1, u):
    dot = max(-1.0, min(1.0, vdot(d0, d1)))
    om = math.acos(dot)
    if om < 1e-4:
        return vnorm(vlerp(d0, d1, u))
    so = math.sin(om)
    return vnorm(vadd(vmul(d0, math.sin((1 - u) * om) / so), vmul(d1, math.sin(u * om) / so)))


def _polyline(pts, u):
    seg = [vlen(vsub(pts[i + 1], pts[i])) for i in range(len(pts) - 1)]
    tot = sum(seg) or 1.0
    s = u * tot
    for i, l in enumerate(seg):
        if s <= l or i == len(seg) - 1:
            return vlerp(pts[i], pts[i + 1], min(1.0, s / l if l > 0 else 1.0))
        s -= l
    return pts[-1]


def camera_at(spots, t, T_end):
    """(loc, tgt, lens) at global seconds t."""
    n = len(spots)
    for i in range(n):
        tc, wd, pose, _ = spots[i]
        arr = tc + wd / 2.0
        dep = spots[i + 1][0] - spots[i + 1][1] / 2.0 if i + 1 < n else T_end
        if i + 1 < n and t > dep:
            continue
        if t < arr and i > 0:
            ptc, pwd, ppose, _ = spots[i - 1]
            pdep = tc - wd / 2.0
            l0, t0, z0 = ppose(pdep, 1.0)
            l1, t1, z1 = pose(arr, 0.0)
            u = smoother((t - pdep) / wd) if wd > 0 else 1.0
            loc = _polyline([l0] + [tuple(w) for w in spots[i][3]] + [l1], u)
            d = _slerp(vnorm(vsub(t0, l0)), vnorm(vsub(t1, l1)), u)
            return loc, vadd(loc, vmul(d, 10.0)), z0 + (z1 - z0) * u
        u = (t - arr) / max(0.01, dep - arr) if i > 0 else t / max(0.01, dep)
        return pose(t, max(0.0, min(1.0, u)))
    return spots[-1][2](t, 1.0)


# ================================================================ materials
def _value_node(N, val=0.0):
    v = N.new("ShaderNodeValue")
    v.outputs[0].default_value = val
    return v


def sea_mat():
    """Sea: teal with moving ripples (noise W driven on the GLOBAL timeline, so no pattern jump at beat cuts);
    a `warm` Value node (0..1) tints it warm orange for the El Nino beat."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("td_sea")
        p.inputs["Roughness"].default_value = 0.07
        p.inputs["Specular IOR Level"].default_value = 0.5
        p.inputs["Coat Weight"].default_value = 0.2
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 0.5, 1.0)
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 0.18
        nz.inputs["Detail"].default_value = 7.0
        nz.inputs["Roughness"].default_value = 0.55
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        b = N.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = 0.2
        b.inputs["Distance"].default_value = 0.3
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        warm = _value_node(N, 0.0)
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = hexc("2a7f9a")
        mix.inputs["B"].default_value = hexc("d88a45")
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 0.45
        Lk.new(warm.outputs[0], mul.inputs[0])
        Lk.new(mul.outputs[0], mix.inputs["Factor"])
        fac, _ = S._noise_var(N, Lk, tc.outputs["Object"], 0.003, 0.14)
        Lk.new(S._mul_col(N, Lk, mix.outputs["Result"], fac), p.inputs["Base Color"])
        p.inputs["Emission Color"].default_value = hexc("ff7a24")
        mul2 = N.new("ShaderNodeMath")
        mul2.operation = "MULTIPLY"
        mul2.inputs[1].default_value = 0.35
        Lk.new(warm.outputs[0], mul2.inputs[0])
        Lk.new(mul2.outputs[0], p.inputs["Emission Strength"])
        S._finish(m, p.outputs[0])
        return m, nz.inputs["W"], warm.outputs[0], tc
    return _m("sea", mk)


def sheet_mat():
    """Shallow sheet of seawater on the street: glossy, see-through, rippled (reflects palms + sky)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("td_sheet")
        m.surface_render_method = "BLENDED"
        p.inputs["Base Color"].default_value = hexc("5f8f96")
        p.inputs["Roughness"].default_value = 0.03
        p.inputs["Alpha"].default_value = 0.62
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 1.4
        nz.inputs["Detail"].default_value = 4.0
        Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
        b = N.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = 0.08
        b.inputs["Distance"].default_value = 0.05
        Lk.new(nz.outputs["Fac"], b.inputs["Height"])
        Lk.new(b.outputs["Normal"], p.inputs["Normal"])
        S._finish(m, p.outputs[0])
        return m, nz.inputs["W"]
    return _m("sheet", mk)


def pour_mat():
    """Water pouring over the wall: teal-white, vertical foam streaks that flow down (mapping offset on global t)."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("td_pour")
        m.surface_render_method = "BLENDED"
        p.inputs["Roughness"].default_value = 0.08
        p.inputs["Alpha"].default_value = 0.82
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (7.0, 0.7, 0.7)
        Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.6
        nz.inputs["Detail"].default_value = 3.0
        Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.45
        ramp.color_ramp.elements[0].color = hexc("4f9fae")
        ramp.color_ramp.elements[1].position = 0.7
        ramp.color_ramp.elements[1].color = hexc("eef8f8")
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        Lk.new(ramp.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 0.25
        S._finish(m, p.outputs[0])
        return m, mp.inputs["Location"]
    return _m("pour", mk)


def moon_mat():
    """Huge pale daytime moon: soft blue-white with grey maria, self-lit, NOT hazed (it is 6 km away)."""
    def mk():
        m = bpy.data.materials.new("td_moon")
        nt = m.node_tree
        N, Lk = nt.nodes, nt.links
        for n in list(N):
            if n.type != "OUTPUT_MATERIAL":
                N.remove(n)
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.6
        nz.inputs["Detail"].default_value = 5.0
        nz.inputs["Roughness"].default_value = 0.6
        Lk.new(tc.outputs["Generated"], nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.42
        ramp.color_ramp.elements[0].color = hexc("b9c1cf")
        ramp.color_ramp.elements[1].position = 0.62
        ramp.color_ramp.elements[1].color = hexc("f3f5fa")
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        em = N.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 2.0
        Lk.new(ramp.outputs["Color"], em.inputs["Color"])
        Lk.new(em.outputs[0], N.get("Material Output").inputs["Surface"])
        return m
    return _m("moon", mk)


def cloud_mat(name, col, emis):
    if name in S._MV2:
        return S._MV2[name]
    m, nt, N, Lk, p = S._new_mat(name)
    p.inputs["Base Color"].default_value = hexc(col)
    p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.0
    p.inputs["Emission Color"].default_value = hexc(col)
    p.inputs["Emission Strength"].default_value = emis
    S._finish(m, p.outputs[0])
    S._MV2[name] = m
    return m


def mats():
    def mk():
        return {
            "pave": M.paving_mat(),
            "stone": S.pbr("td_stone", hexc("cfc6b6"), 0.7, var=0.08, var_scale=0.4, bump=0.06),
            "wallface": S.pbr("td_wallface", hexc("a9a194"), 0.8, var=0.1, var_scale=0.3, bump=0.08),
            "white": S.pbr("td_white", hexc("f1f2f3"), 0.45, var=0.03),
            "steel": S.pbr("td_steel", hexc("aeb4bb"), 0.3, metal=0.9, var=0.02),
            "dark": S.pbr("td_dark", hexc("2b2f35"), 0.45, var=0.03),
            "wood": S.pbr("td_wood", hexc("9c7b58"), 0.7, var=0.12, var_scale=3.0, bump=0.04),
            "pile": S.pbr("td_pile", hexc("5d4a3a"), 0.85, var=0.1),
            "gauge_w": S.pbr("td_gauge_w", hexc("f4f4f0"), 0.4, var=0.02),
            "gauge_r": S.pbr("td_gauge_r", hexc("d23b33"), 0.4, var=0.02),
            "road": C.asphalt_mat("td_road", hexc("4d5056")),
            "line": S.pbr("td_line", hexc("f2f2ee"), 0.6, var=0.0),
            "walk": S.pbr("td_walk", hexc("c8c3ba"), 0.75, var=0.05, var_scale=0.6),
            "lawn": S.lawn_mat("td_lawn", hexc("7a9a4c"), stripes=False),
            "far": C.far_ground_mat("td_far", hexc("6f8a55")),
            "roof": S.pbr("td_roof", hexc("8d9096"), 0.8, var=0.08),
            "lamp": S.emis("td_lamp", hexc("fff4dc"), 2.0),
            "sign_dark": S.pbr("td_sign_dark", hexc("3a3d42"), 0.5, var=0.02),
            "sign_on": S.emis("td_sign_on", hexc("ffb21f"), 5.0),
            "wind": S.emis("td_wind", hexc("dffcff"), 3.2),
            "cloud_hi": cloud_mat("td_cloud_hi", "d9dde4", 0.35),
            "cloud_lo": cloud_mat("td_cloud_lo", "79828f", 0.12),
            "awn": [S.pbr("td_awn%d" % i, hexc(c), 0.7, var=0.04)
                    for i, c in enumerate(("d9483b", "2f8f9d", "f0b43c", "3d6fb0", "e07a4f"))],
            "fac": [S.facade_mat("td_fac%d" % i, hexc(c), hexc("3a5670"), 3.2, 3.4, 0.55)
                    for i, c in enumerate(("f2d6a2", "e8b4a0", "bfd8d2", "f4efe6", "d9c3e0", "f6c98f"))],
        }
    return _m("mats", mk)


# ================================================================ mesh helpers
def box(bm, c, s, mi=0):
    return S.bm_box(bm, c, s, mi)


def boxes(name, items, mlist, loc=(0, 0, 0), parent=None):
    bm = bmesh.new()
    for c, s, mi in items:
        box(bm, c, s, mi)
    return S.obj(name, S.mesh_from_bm(name, bm, mlist), loc, parent=parent)


def cyl(bm, c, r, h, mi=0, seg=16):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, vec=c, verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mi
    return res["verts"]


def puffs(name, blobs, mat, loc=(0, 0, 0)):
    bm = bmesh.new()
    for x, y, z, r, fl in blobs:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                   matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r, r, r * fl, 1.0)))
    return S.obj(name, S.mesh_from_bm(name, bm, [mat], smooth=True), loc)


def empty(ctx, name, loc, parent=None):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    S.anchor(ctx, name, e)
    return e


def show_between(tl, o, t_on=None, t_off=None):
    """Hard show/hide by scale (CONSTANT keys) at global seconds."""
    s = tuple(o.scale)
    z = (0.0, 0.0, 0.0)
    frames, vals = [tl.lf(-10000)], [z if t_on is not None else s]
    if t_on is not None:
        frames.append(tl.lf(tl.G(t_on)))
        vals.append(s)
    if t_off is not None:
        frames.append(tl.lf(tl.G(t_off)))
        vals.append(z)
    set_keys(o, "scale", frames, vals, "CONSTANT")


# ================================================================ world
def build_land(mt):
    """Waterfront strip (flat) + the town ground that climbs the hill to the south (subdivided rows)."""
    rows = [0.0, -23.0, -27.0] + [-27.0 - 3.0 * i for i in range(1, 11)] + [-62.0, -90.0, -140.0, -300.0, -800.0, -EXT]
    bm = bmesh.new()
    prev = None
    for y in rows:
        z = ground_z(y)
        cur = (bm.verts.new((-EXT, y, z - 0.05)), bm.verts.new((EXT, y, z - 0.05)))
        if prev:
            bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
        prev = cur
    S.obj("land", S.mesh_from_bm("land", bm, [mt["lawn"]]))
    S.plane_obj("promenade", 2 * EXT, PROM_Y[1] - PROM_Y[0], (0.0, sum(PROM_Y) / 2, 0.02), mt["pave"])
    S.plane_obj("road", 2 * EXT, ROAD_Y[1] - ROAD_Y[0], (0.0, sum(ROAD_Y) / 2, 0.03), mt["road"])
    S.plane_obj("sidewalk", 2 * EXT, WALK_Y[1] - WALK_Y[0], (0.0, sum(WALK_Y) / 2, 0.035), mt["walk"])
    S.plane_obj("shop_apron", 2 * EXT, 3.2, (0.0, -24.6, 0.034), mt["walk"])
    bm = bmesh.new()
    for i in range(-300, 300):
        if i % 2 == 0:
            box(bm, (i * 3.0, sum(ROAD_Y) / 2, 0.045), (1.6, 0.16, 0.01))
    for yy in (ROAD_Y[0] + 0.35, ROAD_Y[1] - 0.35):
        box(bm, (0.0, yy, 0.045), (1800.0, 0.14, 0.01))
    S.obj("road_lines", S.mesh_from_bm("road_lines", bm, [mt["line"]]))
    # side streets climbing the hill (follow ground_z), and a back street along the slope
    for name, x in (("side_w", SIDE_X), ("side_e", SIDE2_X)):
        bm = bmesh.new()
        prev = None
        for y in [WALK_Y[0]] + rows[2:-1]:
            z = ground_z(y) + 0.04
            cur = (bm.verts.new((x - 4.5, y, z)), bm.verts.new((x + 4.5, y, z)))
            if prev:
                bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
            prev = cur
        S.obj(name, S.mesh_from_bm(name, bm, [mt["road"]]))
    S.plane_obj("back_st", 2000, 8, (0.0, -64.0, ground_z(-64.0) + 0.06), mt["road"])


def build_wall_and_sea(tl, st, mt, ctx):
    # seawall: stone body + slightly lighter coping; sea face goes well below the lowest sea level
    boxes("seawall", [((0.0, WALL_Y1 / 2, (WALL_TOP - 7.0) / 2), (2 * EXT, WALL_Y1, WALL_TOP + 7.0), 0),
                      ((0.0, WALL_Y1 / 2, WALL_TOP - 0.06), (2 * EXT, WALL_Y1 + 0.06, 0.12), 1)],
          [mt["wallface"], mt["stone"]])
    m, w_sock, warm_sock, tc = sea_mat()
    sea = S.plane_obj("sea", 4 * EXT * 2.5, 30000.0, (0.0, WALL_Y1 + 15000.0, 1.0), m)
    tc.object = sea                                  # dome + plane share one texture space
    bake(tl, sea, "location", lambda t: (0.0, WALL_Y1 + 15000.0, st.sea(t)))
    bake_sock(tl, w_sock, lambda t: t * 0.22)
    bake_sock(tl, warm_sock, st.warm)
    # far headlands (green hills in the sea) so the coast reads as a coast
    for i, (x, y, rx, ry, h) in enumerate(((-2600.0, 1700.0, 900.0, 520.0, 170.0), (3300.0, 2300.0, 1100.0, 600.0, 210.0))):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0,
                                   matrix=Matrix.Translation((x, y, -h * 0.25)) @ Matrix.Diagonal((rx, ry, h, 1.0)))
        S.obj("headland%d" % i, S.mesh_from_bm("headland%d" % i, bm, [mt["far"]], smooth=True))
    # moon: a flat disc facing south (towards the town), huge and low over the horizon
    bm = bmesh.new()
    seg = 96
    vs = [bm.verts.new((MOON_R * math.cos(2 * math.pi * i / seg), 0.0, MOON_R * math.sin(2 * math.pi * i / seg)))
          for i in range(seg)]
    bm.faces.new(vs)
    moon = S.obj("moon", S.mesh_from_bm("moon", bm, [moon_mat()]), MOON)
    moon.visible_shadow = False
    empty(ctx, "moon", (0.0, 0.0, -MOON_R * 0.55), parent=moon)
    return sea


def build_overtop(tl, st, mt):
    """The water that pours over the wall (two strips: either side of the pier ramp) + the sheet on the street."""
    prof = [(0.15, -0.05), (0.0, 0.14), (-0.6, 0.15), (-1.15, 0.1), (-1.45, -0.25), (-1.65, -0.7),
            (-1.8, -1.12), (-2.3, -1.23), (-3.5, -1.24)]
    m, loc_sock = pour_mat()
    for name, x0, x1 in (("pour_w", -420.0, PIER_X - PIER_W / 2 - 0.1), ("pour_e", PIER_X + PIER_W / 2 + 0.1, 420.0)):
        bm = bmesh.new()
        a = [bm.verts.new((x0, dy, dz)) for dy, dz in prof]
        b = [bm.verts.new((x1, dy, dz)) for dy, dz in prof]
        for i in range(len(prof) - 1):
            bm.faces.new((a[i], b[i], b[i + 1], a[i + 1]))
        o = S.obj(name, S.mesh_from_bm(name, bm, [m]), (0.0, WALL_Y1, WALL_TOP))
        o.visible_shadow = False
        bake(tl, o, "scale", lambda t: (1.0, max(0.001, st.pour(t)), max(0.001, st.pour(t))))
    bake_sock(tl, loc_sock, lambda t: (0.0, 0.0, t * 1.6), step=2)
    # flood sheet: origin on the wall's landward face, length = SPILL_LEN * extent, wavy far edge
    sm, sw = sheet_mat()
    bm = bmesh.new()
    r = random.Random(5)
    xs = [-420.0 + 4.0 * i for i in range(211)]
    near = [bm.verts.new((x, 0.0, 0.0)) for x in xs]
    far = [bm.verts.new((x, -1.0 - 0.06 * math.sin(x * 0.21) - 0.04 * r.random(), 0.0)) for x in xs]
    for i in range(len(xs) - 1):
        bm.faces.new((near[i], far[i], far[i + 1], near[i + 1]))
    sheet = S.obj("flood_sheet", S.mesh_from_bm("flood_sheet", bm, [sm]), (0.0, -0.02, 0.07))
    sheet.visible_shadow = False
    bake(tl, sheet, "scale", lambda t: (1.0, max(0.001, SPILL_LEN * st.flood(t)), 1.0))
    bake_sock(tl, sw, lambda t: t * 0.6)


def build_pier(mt, ctx):
    x0, x1 = PIER_X - PIER_W / 2, PIER_X + PIER_W / 2
    items = [((PIER_X, (WALL_Y1 + PIER_Y1) / 2, DECK_Z - 0.15), (PIER_W, PIER_Y1 - WALL_Y1, 0.3), 0),
             ((PIER_X, PIER_Y1 + 8.0, DECK_Z - 0.15), (16.0, 16.0, 0.3), 0)]
    bm = bmesh.new()
    for c, s, mi in items:
        box(bm, c, s, mi)
    # ramp up from the promenade
    S.bm_prism_x(bm, x0, x1, [(PROM_Y[0] + 1.0, 0.02), (WALL_Y1, 0.02), (WALL_Y1, DECK_Z), (WALL_Y1 - 0.4, DECK_Z)], 0)
    y = WALL_Y1 + 4.0
    while y < PIER_Y1 + 16.0:
        hw = PIER_W / 2 - 0.4 if y < PIER_Y1 else 7.6
        for xx in (PIER_X - hw, PIER_X + hw):
            cyl(bm, (xx, y, (DECK_Z - 0.3 - 7.0) / 2), 0.26, DECK_Z - 0.3 + 7.0, 1, 10)
        y += 8.0
    # railings (posts + top rail) along both sides
    for xx in (x0 + 0.1, x1 - 0.1):
        yy = WALL_Y1 + 0.5
        while yy < PIER_Y1:
            box(bm, (xx, yy, DECK_Z + 0.5), (0.1, 0.1, 1.0), 2)
            yy += 3.0
        box(bm, (xx, (WALL_Y1 + PIER_Y1) / 2, DECK_Z + 1.0), (0.09, PIER_Y1 - WALL_Y1, 0.08), 2)
    S.obj("pier", S.mesh_from_bm("pier", bm, [mt["wood"], mt["pile"], mt["white"]]))
    # lamps on the pier
    bm = bmesh.new()
    for yy in range(16, int(PIER_Y1), 24):
        box(bm, (x1 - 0.3, yy, DECK_Z + 2.0), (0.14, 0.14, 4.0), 0)
        box(bm, (x1 - 0.6, yy, DECK_Z + 4.05), (0.7, 0.3, 0.18), 1)
    S.obj("pier_lamps", S.mesh_from_bm("pier_lamps", bm, [mt["dark"], mt["lamp"]]))
    # striped tide gauge post (bands only, no numbers) on its own pile, bracketed to the deck
    gx, gy = GAUGE
    bm = bmesh.new()
    box(bm, (gx, gy, -2.0), (0.34, 0.34, 10.0), 0)
    z = -3.0
    k = 0
    while z < 3.0:
        box(bm, (gx, gy, z + 0.125), (0.36, 0.36, 0.25), 1 if k % 2 else 0)
        z += 0.25
        k += 1
    box(bm, (gx, gy, 3.12), (0.44, 0.44, 0.1), 2)
    box(bm, ((gx + x0) / 2, gy, DECK_Z - 0.2), (x0 - gx, 0.16, 0.16), 2)
    S.obj("tide_gauge", S.mesh_from_bm("tide_gauge", bm, [mt["gauge_w"], mt["gauge_r"], mt["dark"]]))
    empty(ctx, "gauge", (gx, gy, 3.2))


def build_storm(tl, st, mt, ctx, sea_m):
    """Grey storm bank far offshore (NE), the low-pressure sea dome under it and onshore wind arrows."""
    rng = random.Random(11)
    hi, lo = [], []
    for k in range(7):
        cx = STORM[0] + (k - 3) * 115.0 + rng.uniform(-30, 30)
        cy = STORM[1] + rng.uniform(-90, 90)
        for j in range(5):
            r = rng.uniform(60, 105)
            lo.append((cx + rng.uniform(-60, 60), cy + rng.uniform(-50, 50), 150.0 + rng.uniform(-10, 25), r, 0.45))
            hi.append((cx + rng.uniform(-50, 50), cy + rng.uniform(-40, 40), 230.0 + rng.uniform(0, 110), r * 0.95, 0.8))
    puffs("storm_lo", lo, mt["cloud_lo"])
    puffs("storm_hi", hi, mt["cloud_hi"])
    empty(ctx, "storm", (STORM[0], STORM[1] - 150.0, 210.0))
    # dome (same sea material + texture space as the sea plane): a flattened sphere whose height grows
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    dome = S.obj("sea_dome", S.mesh_from_bm("sea_dome", bm, [sea_m], smooth=True), (DOME[0], DOME[1], -2.0),
                 scale=(330.0, 330.0, 42.0))
    bake(tl, dome, "scale", lambda t: (330.0, 330.0, 42.0 * st.dome(t)), step=2)
    empty(ctx, "dome", (DOME[0], DOME[1], 45.0))
    # wind arrows: flat glowing arrows facing the storm camera, flowing from the storm towards the shore
    A = (760.0, 1230.0, 16.0)
    B = (420.0, 690.0, 16.0)
    dirw = vnorm(vsub(B, A))
    lat = (-dirw[1], dirw[0], 0.0)
    path = vlen(vsub(B, A))
    Ln, Wd = 70.0, 16.0
    hl, w, hw = Ln * 0.42, Wd * 0.5, Wd * 1.15
    pts2 = [(-Ln / 2, -w), (Ln / 2 - hl, -w), (Ln / 2 - hl, -hw), (Ln / 2, 0.0), (Ln / 2 - hl, hw), (Ln / 2 - hl, w),
            (-Ln / 2, w)]
    mid = vlerp(A, B, 0.5)
    n = vnorm(vsub(STORM_CAM, mid))
    d = vnorm(vsub(dirw, vmul(n, vdot(dirw, n))))
    up = vcross(n, d)
    bm = bmesh.new()
    vs = [bm.verts.new(vadd(vmul(d, a), vmul(up, b))) for a, b in pts2]
    bm.faces.new(vs)
    me = S.mesh_from_bm("wind_arrow", bm, [mt["wind"]])
    t0, t1 = st.wind_on
    for i, (off, s0) in enumerate(((-130.0, 0.0), (0.0, 210.0), (130.0, 90.0), (-65.0, 330.0), (65.0, 450.0))):
        o = S.obj("wind%d" % i, me, A)
        o.visible_shadow = False

        def pos(t, off=off, s0=s0):
            s = (s0 + 70.0 * max(0.0, t - t0)) % path
            return vadd(vadd(A, vmul(dirw, s)), vmul(lat, off))

        def scl(t, s0=s0):
            s = (s0 + 70.0 * max(0.0, t - t0)) % path
            k = smooth(min(s, path - s) / 60.0) * smooth((t - t0) / 0.4) * smooth((t1 - t) / 0.4)
            k = max(0.001, k)
            return (k, k, k)
        bake(tl, o, "location", pos)
        bake(tl, o, "scale", scl)


def build_town(tl, st, mt, ctx, rng):
    # shop row facing the sea (gaps for the two side streets)
    x = -420.0
    i = 0
    items_by_fac = {}
    awn = {}
    while x < 420.0:
        wdt = rng.uniform(10.0, 16.0)
        cx = x + wdt / 2
        if abs(cx - SIDE_X) < wdt / 2 + 5.0 or abs(cx - SIDE2_X) < wdt / 2 + 5.0:
            x += 6.0
            continue
        h = rng.choice((6.8, 7.2, 10.2, 10.6, 13.6))
        dep = 13.0
        fi = i % 6
        items_by_fac.setdefault(fi, []).append(((cx, SHOP_Y - dep / 2, (h - 1.0) / 2), (wdt - 0.4, dep, h + 1.0), 0))
        items_by_fac[fi].append(((cx, SHOP_Y - dep / 2, h + 0.15), (wdt - 0.1, dep + 0.3, 0.3), 1))
        awn.setdefault(i % 5, []).append(((cx, SHOP_Y + 0.8, 3.1), (wdt - 1.4, 1.6, 0.12), 0))
        x += wdt
        i += 1
    for fi, items in items_by_fac.items():
        boxes("shops%d" % fi, items, [mt["fac"][fi], mt["roof"]])
    for ai, items in awn.items():
        boxes("awnings%d" % ai, items, [mt["awn"][ai]])
    # promenade palms + street lamps; sidewalk palms
    palms = SEA._palm_templates(rng)
    pts = [(xx, -4.6) for xx in range(-400, 401, 16) if abs(xx - PIER_X) > 9 and abs(xx - SIDE_X) > 3]
    for o in S.scatter(palms, pts, rng, (0.9, 1.15), prefix="palm_p"):
        o.location.x += rng.uniform(-1.5, 1.5)
    pts = [(xx + 8, -21.2) for xx in range(-400, 401, 22) if abs(xx + 8 - SIDE_X) > 7 and abs(xx + 8 - SIDE2_X) > 7]
    S.scatter(palms, pts, rng, (0.8, 1.0), prefix="palm_s")
    bm = bmesh.new()
    for xx in range(-396, 401, 24):
        if abs(xx - PIER_X) < 6:
            continue
        box(bm, (xx, -6.4, 2.2), (0.14, 0.14, 4.4), 0)
        box(bm, (xx, -6.1, 4.45), (0.3, 0.7, 0.16), 1)
    S.obj("prom_lamps", S.mesh_from_bm("prom_lamps", bm, [mt["dark"], mt["lamp"]]))
    # parked cars on the south lane (parallel), the hero car nose-in at the north kerb
    for k, xx in enumerate((-95.0, -72.0, -18.0, 4.0, 31.0, 78.0, 126.0)):
        L.make_car("parked%d" % k, loc=(xx, -16.6, 0.03), rot_z=math.pi / 2 * (1 if k % 2 else -1), glow=False,
                   headlights=False)
    car = L.make_car("hero_car", loc=(CAR0[0], CAR0[1], 0.03), rot_z=0.0, glow=False, headlights=False).obj
    def car_loc(t):
        y = st.car_y(t)
        return (CAR0[0], y, ground_z(y) + 0.04 if y < WALK_Y[0] else 0.03)

    def car_rot(t):   # pitch with the hill (car faces +Y, the hill rises towards -Y: nose down)
        y = st.car_y(t)
        return (-math.atan((ground_z(y - 1.0) - ground_z(y + 1.0)) / 2.0), 0.0, 0.0)
    bake(tl, car, "location", car_loc, step=2)
    bake(tl, car, "rotation_euler", car_rot, step=2)
    empty(ctx, "car", (0.0, 0.0, 1.6), parent=car)
    # road sign (blank amber panel lights up; its words are a 2D label)
    bm = bmesh.new()
    box(bm, (0.0, 0.0, 1.2), (0.1, 0.1, 2.4), 0)
    box(bm, (0.0, -0.06, 2.45), (1.3, 0.06, 0.9), 0)
    sign = S.obj("sign", S.mesh_from_bm("sign", bm, [mt["sign_dark"]]), (SIGN[0], SIGN[1], 0.03),
                 rot=(0.0, 0.0, math.radians(38.0)))
    bm = bmesh.new()
    box(bm, (0.0, -0.1, 2.45), (1.18, 0.02, 0.78), 0)
    lit = S.obj("sign_lit", S.mesh_from_bm("sign_lit", bm, [mt["sign_on"]]), (SIGN[0], SIGN[1], 0.03),
                rot=(0.0, 0.0, math.radians(38.0)))
    show_between(tl, lit, st.sign_on)
    empty(ctx, "sign", (0.0, 0.0, 2.95), parent=sign)
    empty(ctx, "wall", (6.0, 0.6, WALL_TOP))
    # houses + trees on the hill, far hills
    ht = S.house_templates(rng, 12)
    tt = S.tree_templates(rng)
    hp, tp = [], []
    for _ in range(420):
        xx, yy = rng.uniform(-520, 520), rng.uniform(-430, -56)
        if abs(xx - SIDE_X) < 12 or abs(xx - SIDE2_X) < 12 or abs(yy + 64.0) < 7:
            continue
        (hp if rng.random() < 0.55 else tp).append((xx, yy))
    for o in S.scatter(ht, hp, rng, (0.85, 1.15), prefix="house"):
        o.location.z = ground_z(o.location.y) - 0.3
    for o in S.scatter(tt, tp, rng, (0.8, 1.3), prefix="tree"):
        o.location.z = ground_z(o.location.y) - 0.2
    for k in range(9):
        bm = bmesh.new()
        x, y = -2400.0 + k * 600.0 + rng.uniform(-150, 150), rng.uniform(-1700, -1100)
        rx, h = rng.uniform(500, 800), rng.uniform(160, 300)
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0,
                                   matrix=Matrix.Translation((x, y, 0.0)) @ Matrix.Diagonal((rx, rx * 0.6, h, 1.0)))
        S.obj("hill%d" % k, S.mesh_from_bm("hill%d" % k, bm, [mt["far"]], smooth=True))


# ================================================================ BUILDER
def b_tides_oneshot(ctx, p):
    tl = TL(ctx)
    st = Story(tl)
    sc = ctx.scene
    rng = random.Random(p.get("seed", 27))
    S.daylight(ctx, p.get("sun_az", -30.0), 42.0)
    L.fog(0.00022, S.HAZE, start=220.0)
    C.horizon_haze(sc, lo=-0.01, hi=0.05)
    mt = mats()
    build_land(mt)
    build_wall_and_sea(tl, st, mt, ctx)
    build_overtop(tl, st, mt)
    build_pier(mt, ctx)
    build_storm(tl, st, mt, ctx, sea_mat()[0])
    build_town(tl, st, mt, ctx, rng)
    # the camera: one continuous route on the global timeline
    spots = route(tl, st)
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=30)
    cam.data.clip_start = 0.1
    cam.data.clip_end = 30000.0
    T_end = tl.t_of_G(tl.total)          # the last frame lands exactly on the frame-1 view
    bake(tl, cam, "location", lambda t: camera_at(spots, t, T_end)[0])
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 tides] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 tides] beat %d (%s): global frames %d-%d" % (tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1,
                                                          tl.off[tl.k] + tl.n[tl.k]))


S.V2_BUILDERS.update({"tides_oneshot": b_tides_oneshot})

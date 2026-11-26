"""v2 one-shot hub-airport builder ("airline outage", WJH 27 Nov 2026 #3, narration style: domino). Registers into
scene_lib_v2.V2_BUILDERS as `airport_oneshot`.

Same pattern as scene_lib_v2_tides.py / scene_lib_v2_campus.py: ONE builder for every beat. Each beat builds the
identical bright airport and keys ALL animation (camera, domino wave, jet bridge, pushback, arriving jet, bags) on the
GLOBAL episode timeline read from WORKDIR/audio/timings.json + WORKDIR/captions.json, so the finished video is one
continuous camera through one world: slow drifts at each spot, fast eased whips (EEVEE motion blur) between spots,
and a backout that ends on the frame-1 view (loop). Global frame G of local frame f in beat k: G = off_k + f.

World = the persistent v2 airport (S.build_world: runway x = 0, taxiway x = 115, apron, terminal at x 273..307,
tower, suburbs, downtown), plus:
  - the terminal extended into a long concourse (y 330..760) with TEN gates, every one full: generic white jets with a
    plain teal tail (NO airline names, logos or real liveries), jet bridges attached;
  - a queue of six jets nose to tail on the taxiway (x = 115), one more arriving into the back of the queue;
  - a ramp scene at the hero jet (gate 5): belt loader, baggage carts, a stylised ramp worker with a clipboard;
  - a glass-fronted crew lounge at the north end of the concourse with four stylised crew and their bags;
  - the DOMINO TRAIL: ~260 big white dominoes laid along the cause-to-effect route (hero jet -> ramp -> up the gate
    row -> taxiway queue -> tower -> crew lounge). Five amber milestone dominoes (1..5 pips) fall on the spoken
    "Domino one ... five"; the wave runs between them. Everything is reset (jet back at its gate, dominoes upright)
    while the camera looks the other way in the outro, so the last frame equals frame 1.
No 3D text anywhere (cards / chips / labels / the load sheet and departures board are 2D overlays). Nothing graphic:
normal airport operations only (parked, taxiing, pushing back).

Beats it expects (ids): hook, question, domino_numbers, domino_by_hand, domino_gates, domino_hub, domino_crews,
resolution, takeaway, outro. Missing cue words fall back to a fraction of their beat.
Anchors for 2D labels: jet, dom1..dom5, gate6, gate8, queue, bags, crew.
"""
import json
import math
import os
import random
import traceback

import bpy
import bmesh

import scene_lib as L
import scene_lib_v2 as S
from scene_lib import hexc
import scene_lib_v2_city as C
import scene_lib_v2_travel as T

# ---------------------------------------------------------------- layout (metres; runway along +Y at x = 0)
AL_Z = 4.62                                  # airliner root height, gear on the ground (as in scene_lib_v2_travel)
TERM_X = 273.0                               # terminal / concourse face towards the apron
GX = TERM_X - 19.5 - 3.0                     # gate jets' root x (nose +X, towards the terminal)
GATES = [352.0 + 42.0 * k for k in range(10)]
HERO = 4
HY = GATES[HERO]                             # hero jet (frame 1), gate 5
QX = 115.0                                   # taxiway centre line
QUEUE = [800.0 + 50.0 * k for k in range(6)]  # queue jets (nose -Y); the last one arrives during domino_gates
ARR_Y0 = 1320.0
LOUNGE = (278.0, 302.0, 760.0, 772.0)        # crew lounge x0, x1, y0, y1 (north end of the concourse)
TOWER = (250.0, 790.0)
TRAIL = [(258.0, 500.0), (214.0, 500.0), (214.0, 770.0), (160.0, 800.0), (160.0, 814.0), (240.0, 814.0),
         (288.0, 784.0)]
MS_S = (0.0, 22.0, 56.0)                     # first three milestones (path metres); 4 = trail vertex 5, 5 = the end
DOM_H, DOM_W, DOM_TH, DOM_SP = 4.0, 2.0, 0.45, 2.0
WAVE_V = 20.0                                # m/s of the toppling wave on short runs
PUSH = (-26.0, -4.0, -0.26)                  # hero pushback: dx, dy, d-yaw

P1 = ((199.0, 454.0, 9.0), (256.0, 556.0, 7.0), 24.0)   # frame-1 view (loc, target, lens); the backout ends here

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


def vlen(a):
    return math.sqrt(vdot(a, a))


def vnorm(a):
    n = vlen(a) or 1.0
    return vmul(a, 1.0 / n)


def vlerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


# ================================================================ global timeline (same as the tides / campus builders)
class TL:
    """Global timeline: beat frame offsets + every spoken word (absolute seconds)."""

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
    T.set_keys(o, path, [tl.lf(G) for G in Gs], vals, interp)


def sparse_keys(tl, o, path, keys, interp="LINEAR"):
    """keys [(global_seconds, value_tuple)] -> keys on local frames (times forced to increase by >= 1 frame)."""
    frames, vals, last = [], [], None
    for t, v in keys:
        f = tl.lf(tl.G(t))
        if last is not None and f < last + 1.0:
            f = last + 1.0
        frames.append(f)
        vals.append(tuple(v))
        last = f
    T.set_keys(o, path, frames, vals, interp)


# ================================================================ domino trail (pure python)
def _seg_lengths(pts):
    return [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]


def trail_len():
    return sum(_seg_lengths(TRAIL))


def trail_at(s):
    """(x, y, tx, ty) at path distance s along TRAIL."""
    segs = _seg_lengths(TRAIL)
    for i, ln in enumerate(segs):
        if s <= ln or i == len(segs) - 1:
            a, b = TRAIL[i], TRAIL[i + 1]
            u = max(0.0, min(1.0, s / ln))
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, (b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        s -= ln
    raise ValueError(s)


def dominoes_layout():
    """[(s, x, y, yaw)] one per domino + milestone indices (5)."""
    total = trail_len()
    n = int(total / DOM_SP) + 1
    out = []
    for j in range(n):
        s = j * DOM_SP
        x, y, tx, ty = trail_at(s)
        out.append((s, x, y, math.atan2(-tx, ty)))
    s4 = sum(_seg_lengths(TRAIL)[:5])
    ms = [int(round(MS_S[0] / DOM_SP)), int(round(MS_S[1] / DOM_SP)), int(round(MS_S[2] / DOM_SP)),
          int(round(s4 / DOM_SP)), n - 1]
    return out, ms


# ================================================================ story curves (global seconds)
class Story:
    """Every animated quantity as a function of global time, derived from the beat/word timings."""

    def __init__(self, tl):
        c, b0, b1 = tl.cue, tl.bstart, tl.bend
        self.T = tl.T
        self.T_end = tl.t_of_G(tl.total)
        nums = [("domino_numbers", "one"), ("domino_by_hand", "two"), ("domino_gates", "three"),
                ("domino_hub", "four"), ("domino_crews", "five")]
        self.c_num = []
        for bid, w in nums:
            t = c(bid, w, 0.1)
            if self.c_num and t <= self.c_num[-1] + 0.5:
                t = self.c_num[-1] + 0.5
            self.c_num.append(t)
        self.doms, self.ms = dominoes_layout()
        self.ms_s = [self.doms[i][0] for i in self.ms]
        # hero jet: bridge retracts, then pushback (takeaway); everything snaps back unseen in the outro
        tk = b0("takeaway")
        self.t_ret0, self.t_ret1 = tk + 0.3, tk + 2.0
        self.t_push0 = tk + 2.1
        self.t_push1 = max(self.t_push0 + 4.0, b1("takeaway") + 0.4)
        t_o, t_send = b0("outro"), c("outro", "send", 0.45)
        self.t_tp = max(t_o + 1.2, self.t_push1 + 0.2, (t_o + t_send) / 2.0)
        # mid-way through the high "ground stop" hold (camera looks north, the ramp is behind it)
        self.t_ramp_off = (c("domino_hub", "held", 0.55) + b0("domino_crews")) / 2.0
        # the jet that arrives into the back of the taxiway queue
        self.t_arr0 = c("domino_gates", "next", 0.55) - 0.6
        self.t_arr1 = self.t_arr0 + 6.5
        # bags on the belt loader: a whole number of cycles over the episode (loop-safe)
        self.bag_period = self.T_end / max(1, int(round(self.T_end / 2.6)))

    def wave_t(self, s):
        """Global time the toppling wave reaches path distance s (milestone k falls on its spoken number)."""
        S_, Cn = self.ms_s, self.c_num
        if s <= S_[0] + 1e-6:
            return Cn[0]
        for i in range(4):
            if s <= S_[i + 1] + 1e-6:
                d = S_[i + 1] - S_[i]
                run0 = max(Cn[i] + 0.3, Cn[i + 1] - d / WAVE_V)
                return run0 + (s - S_[i]) / d * (Cn[i + 1] - run0)
        return Cn[-1]

    def hero_pose(self, t):
        """(x, y, yaw) of the hero jet's root."""
        if t >= self.t_tp:
            return GX, HY, -math.pi / 2
        u = smooth((t - self.t_push0) / (self.t_push1 - self.t_push0))
        return GX + PUSH[0] * u, HY + PUSH[1] * u * u, -math.pi / 2 + PUSH[2] * u * u

    def bridge(self, t):
        if t >= self.t_tp:
            return 1.0
        return 1.0 - 0.45 * smooth((t - self.t_ret0) / (self.t_ret1 - self.t_ret0))

    def arr_y(self, t):
        return ARR_Y0 + (QUEUE[-1] - ARR_Y0) * smoother((t - self.t_arr0) / (self.t_arr1 - self.t_arr0))


# ================================================================ camera route (pure python)
def lin(a, b, ease=False):
    def f(t, u):
        if ease:
            u = smoother(u)
        return vlerp(a[0], b[0], u), vlerp(a[1], b[1], u), a[2] + (b[2] - a[2]) * u
    return f


def _toward(a, frac):
    """A pose `frac` of the way from P1's camera towards its target (same aim + a slightly longer lens)."""
    loc, tgt, lens = a
    return vlerp(loc, tgt, frac), tgt, lens + 1.0


def route(tl, st):
    """Spots: (t_whip_centre, whip_duration, pose_fn(t, u) -> (loc, tgt, lens), waypoints between spots)."""
    c, b0 = tl.cue, tl.bstart
    close0, close1 = _toward(P1, 0.22), _toward(P1, 0.20)
    spots = [
        # hook: frame-1 view, the boarded jet at gate 5 with the row of full gates behind it
        (0.0, 0.0, lin(P1, ((201.5, 449.0, 9.8), (256.0, 556.0, 7.0), 24.5)), []),
        # hook "Two days earlier": high along the endless row of parked jets (hero 1)
        (c("hook", "days", 0.45), 0.9, lin(((214.0, 318.0, 24.0), (250.0, 600.0, 3.0), 30.0),
                                           ((215.0, 325.0, 23.2), (250.0, 604.0, 3.0), 31.0)), [(205.0, 400.0, 17.0)]),
        # question: at the cockpit window of the hero jet (starboard side, clear of the jet bridges)
        (b0("question"), 0.85, lin(((258.5, 504.5, 7.2), (267.0, 519.0, 5.6), 28.0),
                                   ((259.2, 505.6, 7.0), (267.0, 519.0, 5.6), 29.0)), [(240.0, 440.0, 16.0)]),
        # ... "what it does is math": ease in on the cockpit (the 2D load sheet is blank)
        (c("question", "math", 0.55), 0.7, lin(((261.6, 508.4, 6.7), (267.2, 519.2, 5.6), 32.0),
                                               ((262.2, 509.4, 6.6), (267.2, 519.2, 5.6), 33.0)), []),
        # ... "Watch the dominoes": turn to the first domino beside the jet; domino 1 falls on "Domino one"
        (c("question", "watch", 0.85), 0.75, lin(((260.0, 486.0, 7.6), (251.0, 505.0, 3.0), 26.0),
                                                 ((258.6, 485.6, 7.5), (250.0, 505.0, 3.0), 26.0)), []),
        # ... "Those numbers set the takeoff speed and the engine power": over the domino row onto the engine and wing
        (c("domino_numbers", "those", 0.5), 0.8, lin(((236.0, 489.0, 8.5), (250.5, 512.0, 3.2), 28.0),
                                                     ((237.0, 488.6, 8.3), (250.5, 512.0, 3.4), 28.0)),
         [(246.0, 483.0, 7.0)]),
        # domino 2 "the slow way": the ramp from above the domino row, bags counted by hand at the belt loader
        (b0("domino_by_hand"), 0.8, lin(((225.0, 489.0, 11.5), (234.0, 508.0, 1.4), 28.0),
                                        ((226.0, 488.5, 11.2), (234.0, 508.0, 1.4), 29.0)), []),
        # domino 3 "the gates": up the apron along the row of full gates (the wave runs up the row)
        (b0("domino_gates"), 0.85, lin(((204.0, 470.0, 12.0), (234.0, 640.0, 4.0), 26.0),
                                       ((204.5, 478.0, 12.5), (234.0, 645.0, 4.0), 26.0)), []),
        # ... "the next arriving plane": high three-quarter, taxiway queue facing the wall of full gates (hero 2)
        (c("domino_gates", "next", 0.55), 1.5, lin(((80.0, 1110.0, 40.0), (190.0, 650.0, 0.0), 28.0),
                                                   ((81.5, 1103.0, 39.4), (190.0, 650.0, 0.0), 28.5)), []),
        # domino 4 "the hub": the control tower
        (b0("domino_hub"), 1.4, lin(((206.0, 736.0, 14.0), (247.0, 795.0, 17.0), 24.0),
                                    ((203.0, 733.0, 15.5), (247.0, 795.0, 18.0), 24.0)), [(150.0, 950.0, 36.0)]),
        # ... "can be held at their departure airports": rise past the tower into the sky (ground stop)
        (c("domino_hub", "held", 0.55), 1.3, lin(((300.0, 600.0, 300.0), (215.0, 930.0, 0.0), 26.0),
                                                   ((303.0, 594.0, 312.0), (215.0, 930.0, 0.0), 26.0)),
         [(232.0, 770.0, 60.0)]),
        # domino 5 "the clock": down to the crew lounge window
        (b0("domino_crews"), 1.3, lin(((296.0, 806.0, 5.0), (289.0, 767.0, 3.8), 28.0),
                                      ((295.0, 803.0, 4.8), (289.0, 767.0, 3.8), 29.0)), [(300.0, 840.0, 40.0)]),
        # ... "When planes run late, crews can time out": closer on the waiting crew
        (c("domino_crews", "when", 0.55), 0.7, lin(((294.0, 786.0, 4.3), (289.5, 766.0, 3.0), 30.0),
                                                   ((293.6, 784.6, 4.2), (289.5, 766.0, 3.0), 31.0)), []),
        # resolution: back to the first gate (system back)
        (b0("resolution"), 1.5, lin(((231.0, 487.0, 7.5), (262.0, 521.0, 5.5), 28.0),
                                    ((232.5, 488.5, 7.3), (262.0, 521.0, 5.5), 29.0)),
         [(262.0, 812.0, 22.0), (220.0, 800.0, 24.0), (205.0, 740.0, 25.0)]),
        # takeaway: the jet bridge retracts and the hero jet pushes back
        (b0("takeaway"), 0.8, lin(((199.0, 476.0, 10.0), (251.0, 524.0, 5.0), 26.0),
                                  ((198.0, 473.0, 10.4), (249.0, 524.0, 5.0), 26.0)), []),
        # outro: head-on to the taxiway queue ("stuck at an airport"); the gate + dominoes reset behind the camera
        (b0("outro"), 0.9, lin(((104.0, 736.0, 6.5), (116.0, 900.0, 7.0), 30.0),
                               ((104.5, 742.0, 6.6), (116.0, 900.0, 7.0), 31.0)), []),
        # ... "send this": close on the hero jet, on the frame-1 axis
        (c("outro", "send", 0.45), 0.9, lin(close0, close1), []),
        # ... backout to the frame-1 view (loop)
        (c("outro", "because", 0.75) - 0.4, 0.4, lin(close1, P1, ease=True), []),
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
def teal_livery(root):
    """Generic livery: white body, plain teal fin, light-grey belly, dark window row + cockpit windows. No names,
    no logos, no cheat line (replaces scene_lib_v2_air's navy/red livery, which reads too close to a real carrier)."""
    m, nt, N, Lk, p = S._new_mat("ap_livery_" + root.name)
    tc = N.new("ShaderNodeTexCoord")
    tc.object = root
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    X, Y, Z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def M(op, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n.outputs[0]

    def band(v, lo, hi):
        return M("MULTIPLY", M("GREATER_THAN", v, lo), M("LESS_THAN", v, hi))
    ax = M("ABSOLUTE", X)
    fus = M("LESS_THAN", ax, 2.05)
    wy = M("FRACT", M("MULTIPLY", Y, 1 / 0.52))
    win = M("MULTIPLY", band(wy, 0.25, 0.72), band(Z, 0.52, 0.98))
    win = M("MULTIPLY", win, band(Y, -11.5, 13.2))
    win = M("MULTIPLY", win, M("GREATER_THAN", ax, 1.2))
    ck = M("MULTIPLY", band(Y, 15.6, 17.2), band(M("SUBTRACT", Z, M("MULTIPLY", M("SUBTRACT", Y, 15.6), -0.18)), 0.75, 1.25))
    ck = M("MULTIPLY", ck, M("GREATER_THAN", ax, 0.25))
    dark = M("MINIMUM", M("ADD", win, ck), 1.0)
    belly = M("MULTIPLY", M("LESS_THAN", Z, -1.2), M("MULTIPLY", fus, band(Y, -12, 15)))
    tail = M("MULTIPLY", M("GREATER_THAN", Z, 2.2), M("LESS_THAN", ax, 0.5))
    c1 = N.new("ShaderNodeMix")
    c1.data_type = "RGBA"
    c1.inputs["A"].default_value = hexc("f3f5f7")
    c1.inputs["B"].default_value = hexc("cdd2d8")
    Lk.new(belly, c1.inputs["Factor"])
    c2 = N.new("ShaderNodeMix")
    c2.data_type = "RGBA"
    Lk.new(c1.outputs["Result"], c2.inputs["A"])
    c2.inputs["B"].default_value = hexc("1f9e9a")
    Lk.new(tail, c2.inputs["Factor"])
    c3 = N.new("ShaderNodeMix")
    c3.data_type = "RGBA"
    Lk.new(c2.outputs["Result"], c3.inputs["A"])
    c3.inputs["B"].default_value = hexc("1a2230")
    Lk.new(dark, c3.inputs["Factor"])
    Lk.new(c3.outputs["Result"], p.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.3
    rr.inputs["To Max"].default_value = 0.08
    Lk.new(dark, rr.inputs["Value"])
    Lk.new(rr.outputs["Result"], p.inputs["Roughness"])
    p.inputs["Coat Weight"].default_value = 0.5
    p.inputs["Coat Roughness"].default_value = 0.06
    return S._finish(m, p.outputs[0])


def jet(ctx, name, loc, rot_z):
    """Generic narrow-body (scene_lib_v2_air) with the teal livery swapped onto the body and winglets."""
    root, parts = T.airliner(ctx, name, loc, rot_z)
    liv = teal_livery(root)
    done = 0
    for nm in (name + "_body", name + "_winglet1", name + "_winglet-1"):
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        for slot in o.material_slots:
            slot.material = liv
        done += 1
    if done < 3:   # never render the stock navy/red livery (too close to a real carrier)
        raise RuntimeError("teal livery: only %d of 3 parts found on %s" % (done, name))
    return root, parts


def mats():
    def mk():
        return {
            "wall": bpy.data.materials.get("terminal_v2") or S.pbr("ap_wall", hexc("e3e0d8"), 0.6, var=0.04),
            "roof": bpy.data.materials.get("roof_flat_v2") or S.pbr("ap_roof", hexc("8c8f93"), 0.8, var=0.08),
            "bridge": S.pbr("ap_bridge", hexc("d4d6d8"), 0.5, 0.2, var=0.03),
            "bridge_dark": S.pbr("ap_bridge_dark", hexc("4a4f57"), 0.5, 0.3, var=0.02),
            "frame": S.pbr("ap_frame", hexc("5b636e"), 0.35, 0.6, var=0.0),
            "floor": S.pbr("ap_floor", hexc("b9b2a6"), 0.5, var=0.05),
            "inner": S.pbr("ap_inner", hexc("efe9df"), 0.7, var=0.03),
            "seat": S.pbr("ap_seat", hexc("2f5d8a"), 0.6, var=0.03),
            "dom": S.pbr("ap_dom", hexc("f4f4f1"), 0.2, coat=0.8, var=0.0),
            "dom_ms": S.pbr("ap_dom_ms", hexc("f0a628"), 0.25, coat=0.8, var=0.0),
            "pip": S.pbr("ap_pip", hexc("1d3566"), 0.3, var=0.0),
            "pip_w": S.pbr("ap_pip_w", hexc("ffffff"), 0.3, var=0.0),
            "divider": S.pbr("ap_divider", hexc("d8262f"), 0.3, var=0.0),
            "gse": S.pbr("ap_gse", hexc("f2b632"), 0.5, var=0.04),
            "gse_dark": S.pbr("ap_gse_dark", hexc("2b2f35"), 0.5, var=0.03),
            "belt": S.pbr("ap_belt", hexc("1e2126"), 0.8, var=0.02),
            "cart": S.pbr("ap_cart", hexc("8d969f"), 0.45, 0.5, var=0.03),
            "bags": [S.pbr("ap_bag%d" % i, hexc(cc), 0.6, var=0.04)
                     for i, cc in enumerate(("2b4a7a", "b33a3a", "3f7f4f", "222428", "c98b2e", "6b4f8a"))],
            "skin": S.pbr("ap_skin", hexc("d9d4cc"), 0.5, var=0.0),
            "navy": S.pbr("ap_navy", hexc("1f2a44"), 0.6, var=0.03),
            "shirt": S.pbr("ap_shirt", hexc("f1f2f4"), 0.6, var=0.02),
            "vest": S.pbr("ap_vest", hexc("e8ef3a"), 0.5, var=0.02),
            "grey": S.pbr("ap_grey", hexc("4b5160"), 0.6, var=0.03),
            "board": S.pbr("ap_clip", hexc("8a6a45"), 0.6, var=0.03),
        }
    return _m("mats", mk)


# ================================================================ mesh helpers
def boxes(name, items, mlist, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    bm = bmesh.new()
    for c, s, mi in items:
        S.bm_box(bm, c, s, mi)
    return S.obj(name, S.mesh_from_bm(name, bm, mlist), loc, rot, parent=parent)


def empty(ctx, name, loc, parent=None):
    e = L.link(bpy.data.objects.new("anc_" + name, None))
    e.location = loc
    if parent is not None:
        e.parent = parent
    S.anchor(ctx, name, e)
    return e


def _guard(label, fn, *a):
    """Set dressing never kills a beat: log the traceback and carry on."""
    try:
        return fn(*a)
    except Exception:
        print("[v2 airport] %s failed (skipped):" % label)
        traceback.print_exc()
        return None


# ================================================================ world
def build_base(ctx, p):
    S.daylight(ctx, p.get("sun_az", -35.0), p.get("sun_elev", 40.0), hdri=p.get("hdri", True))
    S.build_world(ctx)
    C.horizon_haze(ctx.scene)
    # far hills read as flat pale slabs from the air (as in the travel world); the six hangars would sit between the
    # taxiway queue and the gates in the hero-2 view
    # the six parked light aircraft sit on the domino trail / camera paths: removed with their children
    def doomed(o):
        while o is not None:
            if o.name.startswith(("hill", "hangar", "parked")):
                return True
            o = o.parent
        return False
    for o in [o for o in bpy.data.objects if doomed(o)]:
        bpy.data.objects.remove(o, do_unlink=True)
    # the world apron stops at x 265: pave the 8 m grass strip under the gate jets' noses up to the concourse face,
    # and a pad in front of the crew lounge (both abut the apron, slightly lower, so nothing z-fights)
    try:
        apr = S.concrete_mat()
        S.plane_obj("apron_gate_strip", TERM_X + 1.0 - 265.0, 430.0, ((TERM_X + 1.0 + 265.0) / 2, 545.0, 0.275), apr)
        S.plane_obj("apron_lounge_pad", 50.0, 34.0, (285.0, 777.0, 0.27), apr)
    except Exception as ex:
        print("[v2 airport] apron strip failed:", ex)


def build_concourse(mt):
    """The terminal (y 470..620) extended into a long concourse (y 330..760), same facade + roof materials."""
    for name, y0, y1 in (("conc_s", 330.0, 470.0), ("conc_n", 620.0, 760.0)):
        yc, ln = (y0 + y1) / 2, y1 - y0
        boxes(name, [((290.0, yc, 5.5), (34.0, ln, 11.0), 0), ((290.0, yc, 11.4), (36.0, ln + 2.0, 0.8), 1)],
              [mt["wall"], mt["roof"]])


def build_bridge(k, gy, mt):
    """Jet bridge from the concourse face to the forward (port, +Y) door. Origin at the concourse; local +X points
    to the door, so scale.x retracts it towards the terminal."""
    a = (TERM_X, gy + 9.5)
    b = (GX + 15.1, gy + 3.2)
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    yaw = math.atan2(b[1] - a[1], b[0] - a[0])
    items = [((ln / 2, 0.0, 0.0), (ln, 2.6, 2.8), 0),
             ((ln - 1.2, 0.0, -0.1), (2.4, 3.4, 3.1), 0),
             ((ln - 0.05, 0.0, -0.3), (0.1, 2.2, 2.2), 1),
             ((ln - 2.2, 0.0, -3.4), (0.45, 0.45, 3.8), 1),
             ((ln - 2.2, 0.0, -5.0), (1.6, 0.7, 0.5), 1)]
    tun = boxes("bridge%d" % k, items, [mt["bridge"], mt["bridge_dark"]], (a[0], a[1], 5.3), (0.0, 0.0, yaw))
    boxes("rotunda%d" % k, [((0.0, 0.0, 2.65), (1.6, 1.6, 5.3), 1)], [mt["bridge_dark"]], (a[0] - 0.9, a[1], 0.0))
    return tun


def build_gates(tl, st, ctx, mt):
    roots = []
    for k, gy in enumerate(GATES):
        r, _ = jet(ctx, "gate%d" % k, (GX, gy, AL_Z), -math.pi / 2)
        roots.append(r)
        tun = build_bridge(k, gy, mt)
        if k == HERO:
            bake(tl, tun, "scale", lambda t: (st.bridge(t), 1.0, 1.0))
    hero = roots[HERO]
    bake(tl, hero, "location", lambda t: (st.hero_pose(t)[0], st.hero_pose(t)[1], AL_Z))
    bake(tl, hero, "rotation_euler", lambda t: (0.0, 0.0, st.hero_pose(t)[2]))
    empty(ctx, "jet", (0.0, 0.0, 3.4), parent=hero)
    empty(ctx, "gate6", (0.0, 0.0, 3.4), parent=roots[6])
    empty(ctx, "gate8", (0.0, 0.0, 3.4), parent=roots[8])
    return roots


def build_queue(tl, st, ctx):
    roots = []
    for k, y in enumerate(QUEUE):
        r, _ = jet(ctx, "queue%d" % k, (QX, y if k < len(QUEUE) - 1 else ARR_Y0, AL_Z), math.pi)
        roots.append(r)
    bake(tl, roots[-1], "location", lambda t: (QX, st.arr_y(t), AL_Z))
    empty(ctx, "queue", (0.0, 0.0, 3.4), parent=roots[2])
    return roots


def domino_mesh(name, mt, pips_top, pips_bot, milestone=False):
    lay = {0: [], 1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
           4: [(-1, -1), (1, -1), (-1, 1), (1, 1)], 5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
           6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
    h, w, th = DOM_H, DOM_W, DOM_TH
    pp = 0.26 * w
    bm = bmesh.new()
    S.bm_box(bm, (0, -th / 2, h / 2), (w, th, h), 0)
    for fy in (0.012, -th - 0.012):
        S.bm_box(bm, (0, fy, h / 2), (w - 0.25, 0.03, 0.07), 2)
        for zc, n in ((h * 0.75, pips_top), (h * 0.25, pips_bot)):
            for u, v in lay[n]:
                S.bm_box(bm, (u * pp, fy, zc + v * pp), (0.28, 0.03, 0.28), 1)
    ml = [mt["dom_ms"], mt["pip_w"], mt["divider"]] if milestone else [mt["dom"], mt["pip"], mt["divider"]]
    return S.mesh_from_bm(name, bm, ml)


def build_dominoes(tl, st, ctx, mt):
    """The domino trail. Each domino stands until the wave reaches it, tips onto the next one, then settles when the
    next one falls; all snap back upright at st.t_tp (out of shot), so the last frame equals frame 1."""
    std = [domino_mesh("dom_std%d" % i, mt, a, b) for i, (a, b) in enumerate(((2, 3), (5, 1), (4, 6)))]
    msm = [domino_mesh("dom_ms%d" % (i + 1), mt, i + 1, 0, milestone=True) for i in range(5)]
    a1 = math.asin(min(1.0, (DOM_SP - DOM_TH) / DOM_H))
    rest, flat = math.radians(70.0), math.radians(86.0)
    doms = st.doms
    tj = [st.wave_t(s) for s, _, _, _ in doms]
    objs = []
    for j, (s, x, y, yaw) in enumerate(doms):
        if j in st.ms:
            me = msm[st.ms.index(j)]
        else:
            me = std[j % 3]
        o = S.obj("dom%03d" % j, me, (x, y, 0.3), (0.0, 0.0, yaw))
        last = j == len(doms) - 1
        keys = [(-1000.0, (0.0, 0.0, yaw)), (tj[j], (0.0, 0.0, yaw)), (tj[j] + 0.18, (-a1, 0.0, yaw))]
        if last:
            keys.append((tj[j] + 0.45, (-flat, 0.0, yaw)))
            end = -flat
        else:
            tn = max(tj[j + 1], tj[j] + 0.25)
            keys += [(tn, (-a1, 0.0, yaw)), (tn + 0.25, (-rest, 0.0, yaw))]
            end = -rest
        keys += [(st.t_tp, (end, 0.0, yaw)), (st.t_tp + 1.0 / tl.fps, (0.0, 0.0, yaw))]
        sparse_keys(tl, o, "rotation_euler", keys)
        objs.append(o)
    for k, j in enumerate(st.ms):
        empty(ctx, "dom%d" % (k + 1), (0.0, -DOM_TH / 2, DOM_H + 0.6), parent=objs[j])
    print("[v2 airport] %d dominoes, milestones %s at t=%s" % (len(objs), st.ms, ["%.2f" % t for t in st.c_num]))
    return objs


def figure(name, loc, rot_z, mt, top, cap=False, vest=False, clipboard=False):
    """Stylised faceless person (mannequin-grey skin), origin at the feet, facing +Y."""
    root = L.link(bpy.data.objects.new(name, None))
    root.location = loc
    root.rotation_euler = (0.0, 0.0, rot_z)
    bm = bmesh.new()
    for sx in (-1, 1):
        S._ellipsoid(bm, (sx * 0.1, 0.0, 0.47), (0.085, 0.085, 0.48), 1, 10, 8)        # legs
        S._ellipsoid(bm, (sx * 0.24, 0.0, 1.22), (0.065, 0.065, 0.3), 0, 10, 6)         # arms
    S._ellipsoid(bm, (0.0, 0.0, 1.3), (0.22, 0.15, 0.36), 0, 16, 10)                   # torso
    S._ellipsoid(bm, (0.0, 0.0, 1.0), (0.2, 0.14, 0.13), 1, 12, 8)                     # hips
    S._ellipsoid(bm, (0.0, 0.0, 1.84), (0.12, 0.13, 0.15), 2, 16, 10)                  # head
    S._ellipsoid(bm, (0.0, 0.0, 1.67), (0.05, 0.05, 0.06), 2, 8, 6)                    # neck
    mats_ = [top, mt["navy"] if not vest else mt["grey"], mt["skin"], mt["navy"], mt["board"]]
    if cap:
        S._ellipsoid(bm, (0.0, 0.01, 1.96), (0.13, 0.14, 0.05), 3, 12, 6)
        S.bm_box(bm, (0.0, 0.12, 1.94), (0.18, 0.1, 0.02), 3)
    if clipboard:
        S.bm_box(bm, (0.12, 0.24, 1.18), (0.26, 0.03, 0.34), 4)
        S._ellipsoid(bm, (0.12, 0.17, 1.15), (0.05, 0.12, 0.05), 0, 8, 6)
    S.obj(name + "_body", S.mesh_from_bm(name + "_body", bm, mats_, smooth=True), parent=root)
    return root


def roller_bag(name, loc, rot_z, mt, col):
    return boxes(name, [((0.0, 0.0, 0.33), (0.38, 0.24, 0.56), 0), ((0.0, -0.08, 0.85), (0.3, 0.03, 0.5), 1)],
                 [col, mt["gse_dark"]], loc, (0.0, 0.0, rot_z))


def build_ramp(tl, st, ctx, mt):
    """Belt loader at the hero jet's aft hold (starboard), three baggage carts + tug, a ramp worker with a clipboard."""
    # everything hangs off one empty at the origin: hidden (scale 0) while the camera is high over the airport looking north, so the
    # hero jet's pushback never drives through it; restored at t_tp (unseen) for the loop
    rs = L.link(bpy.data.objects.new("ramp_set", None))
    sparse_keys(tl, rs, "scale", [(-1000.0, (1.0, 1.0, 1.0)), (st.t_ramp_off, (1.0, 1.0, 1.0)),
                                  (st.t_ramp_off + 1.0 / tl.fps, (0.0, 0.0, 0.0)), (st.t_tp, (0.0, 0.0, 0.0)),
                                  (st.t_tp + 1.0 / tl.fps, (1.0, 1.0, 1.0))])
    door = (GX - 8.0, HY - 2.3)
    lo, hi = (door[0], door[1] - 8.2, 0.9), (door[0], door[1] - 0.4, 3.0)
    ln = math.hypot(hi[1] - lo[1], hi[2] - lo[2])
    tilt = math.atan2(hi[2] - lo[2], hi[1] - lo[1])
    mid = vlerp(lo, hi, 0.5)
    boxes("loader_base", [((0.0, 0.0, 0.0), (2.2, 6.2, 0.8), 0), ((0.0, -2.0, 0.9), (2.0, 1.6, 1.1), 0)],
          [mt["gse"]], (door[0], door[1] - 6.5, 0.7), parent=rs)
    boxes("loader_belt", [((0.0, 0.0, 0.0), (1.0, ln, 0.18), 0), ((0.62, 0.0, 0.16), (0.12, ln, 0.3), 1),
                          ((-0.62, 0.0, 0.16), (0.12, ln, 0.3), 1)],
          [mt["belt"], mt["gse"]], mid, (tilt, 0.0, 0.0), parent=rs)
    # three bags riding up the belt (whole cycles over the episode -> loop-safe)
    bm = bmesh.new()
    S.bm_box(bm, (0.0, 0.0, 0.22), (0.6, 0.45, 0.32), 0)
    for i in range(3):
        o = S.obj("belt_bag%d" % i, S.mesh_from_bm("belt_bag%d" % i, bm.copy(), [mt["bags"][i]]), lo, parent=rs)
        o.rotation_euler = (tilt, 0.0, 0.0)

        def pos(t, i=i):
            u = ((t / st.bag_period) + i / 3.0) % 1.0
            return vlerp(lo, hi, u)
        bake(tl, o, "location", pos, step=2)
    bm.free()
    # carts with bags, tug in front (west)
    rng = random.Random(5)
    for k, cx in enumerate((226.0, 231.5, 237.0)):
        items, ml = [((0.0, 0.0, 0.55), (4.2, 2.1, 0.12), 0), ((0.0, 1.0, 0.95), (4.2, 0.06, 0.8), 0),
                     ((0.0, -1.0, 0.95), (4.2, 0.06, 0.8), 0)], [mt["cart"]] + mt["bags"]
        for wx in (-1.6, 1.6):
            for wy in (-0.8, 0.8):
                items.append(((wx, wy, 0.25), (0.45, 0.2, 0.45), 0))
        for b in range(6):
            items.append(((-1.5 + 0.6 * b + rng.uniform(-0.1, 0.1), rng.uniform(-0.5, 0.5), 0.85 + rng.uniform(0, 0.12)),
                          (0.55, 0.42 + rng.uniform(0, 0.25), 0.4 + rng.uniform(0, 0.15)), 1 + rng.randrange(6)))
        boxes("cart%d" % k, items, ml, (cx, 507.0, 0.3), parent=rs)
    boxes("tug", [((0.0, 0.0, 0.7), (3.0, 1.9, 1.0), 0), ((-0.6, 0.0, 1.6), (1.2, 1.7, 0.9), 1)],
          [mt["gse"], mt["gse_dark"]], (221.6, 507.0, 0.3), parent=rs)
    empty(ctx, "bags", (231.5, 507.0, 2.0))
    figure("ramp_worker", (233.5, 503.6, 0.3), math.radians(150.0), mt, mt["vest"], cap=True, vest=True,
           clipboard=True).parent = rs


def build_lounge(ctx, mt):
    """Glass-fronted crew lounge at the north end of the concourse (open front with mullions, lit inside), four
    stylised crew with their roller bags looking out at the apron."""
    x0, x1, y0, y1 = LOUNGE
    xc, w = (x0 + x1) / 2, x1 - x0
    items = [((xc, (y0 + y1) / 2, 0.45), (w, y1 - y0, 0.3), 1),          # floor
             ((xc, (y0 + y1) / 2, 8.2), (w + 1.0, y1 - y0 + 1.0, 0.5), 2),  # roof
             ((x0 + 0.2, (y0 + y1) / 2, 4.3), (0.4, y1 - y0, 7.6), 0),     # side walls
             ((x1 - 0.2, (y0 + y1) / 2, 4.3), (0.4, y1 - y0, 7.6), 0),
             ((xc, y0 + 0.35, 4.3), (w - 0.8, 0.2, 7.6), 3)]              # inner back wall
    for xx in [x0 + 3.0 * i for i in range(1, int(w / 3.0))]:
        items.append(((xx, y1 - 0.1, 4.3), (0.16, 0.16, 7.6), 4))          # mullions
    for zz in (0.75, 7.75):
        items.append(((xc, y1 - 0.1, zz), (w, 0.18, 0.16), 4))
    boxes("lounge", items, [mt["wall"], mt["floor"], mt["roof"], mt["inner"], mt["frame"]])
    seats = []
    for i in range(6):
        seats.append(((x0 + 3.5 + 3.4 * i, y0 + 2.2, 1.0), (2.6, 0.7, 0.5), 0))
        seats.append(((x0 + 3.5 + 3.4 * i, y0 + 1.9, 1.45), (2.6, 0.15, 0.8), 0))
    boxes("lounge_seats", seats, [mt["seat"]])
    # light inside (the roof shades the sun)
    import scene_lib_v2_air as A
    A._area("lounge_light", (xc, (y0 + y1) / 2, 7.7), 10.0, 900.0, size_y=8.0)
    crew = []
    for i, (xx, yy, cap, rz) in enumerate(((283.5, 768.6, True, 0.15), (286.8, 767.4, False, -0.1),
                                           (291.0, 768.8, True, 0.05), (294.6, 767.8, False, -0.2))):
        crew.append(figure("crew%d" % i, (xx, yy, 0.6), rz, mt, mt["navy"], cap=cap))
        roller_bag("crew_bag%d" % i, (xx + 0.45, yy - 0.2, 0.6), rz, mt, mt["navy"])
    empty(ctx, "crew", (0.0, 0.0, 2.1), parent=crew[2])


def build_vans():
    for k, (vx, vy, rz) in enumerate(((238.0, GATES[1] + 21.0, 0.3), (240.0, GATES[6] + 21.0, 2.2),
                                      (236.0, GATES[8] + 21.0, 1.4))):
        L.make_car("apron_van%d" % k, loc=(vx, vy, 0.3), rot_z=rz, headlights=False, glow=False,
                   model=("van", "delivery", "van")[k])


# ================================================================ BUILDER
def b_airport_oneshot(ctx, p):
    tl = TL(ctx)
    st = Story(tl)
    sc = ctx.scene
    build_base(ctx, p)
    mt = mats()
    build_concourse(mt)
    build_gates(tl, st, ctx, mt)
    build_queue(tl, st, ctx)
    build_dominoes(tl, st, ctx, mt)
    _guard("ramp", build_ramp, tl, st, ctx, mt)
    _guard("lounge", build_lounge, ctx, mt)
    _guard("vans", build_vans)
    _guard("repaint", S._repaint_kenney)
    # the camera: one continuous route on the global timeline
    spots = route(tl, st)
    cam = ctx.camera((0, 0, 2), target=(0, 10, 2), lens=30)
    cam.data.clip_start = 0.1
    cam.data.clip_end = 30000.0
    T_end = st.T_end                     # the last frame lands exactly on the frame-1 view
    bake(tl, cam, "location", lambda t: camera_at(spots, t, T_end)[0])
    bake(tl, ctx.cam_target, "location", lambda t: camera_at(spots, t, T_end)[1])
    bake(tl, cam.data, "lens", lambda t: camera_at(spots, t, T_end)[2])
    try:
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = float(p.get("shutter", 0.5))
    except Exception as ex:
        print("[v2 airport] motion blur unavailable:", ex)
    try:
        sc.eevee.motion_blur_steps = int(p.get("blur_steps", 1))
        sc.eevee.motion_blur_max = 64
    except Exception:
        pass
    print("[v2 airport] beat %d (%s): global frames %d-%d" % (tl.k, tl.beats[tl.k]["id"], tl.off[tl.k] + 1,
                                                            tl.off[tl.k] + tl.n[tl.k]))


S.V2_BUILDERS.update({"airport_oneshot": b_airport_oneshot})

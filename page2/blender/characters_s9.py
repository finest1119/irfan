"""Session 9: Bolts on the Quaternius Universal Base Characters (CC0) + Universal Animation Library (CC0). Needs bpy.

Base: Superhero_Male_FullBody.gltf (the only male body in the free Standard kit), toned down at rest to a stocky
middle-aged tradesman (thinner arms, flatter pecs, less V-taper, thicker waist, ~3.5 cm belly), object scale ->
1.778 m. CC0 Hair_Beard + Hair_Buzzed (Rigged to Head Bone) re-pointed at the body rig; the kit's eyes/eyebrows
are kept; everything tinted to page2/character.json.

Clothes are SHELLS of the body's own faces (region by rest position + dominant bone), pushed out along the
normals, so they inherit the body weights 1:1 (fingers included: gloves bend with the finger bones). The body
under each outfit is hidden with a Mask modifier (vertex group hide_under_<outfit>, eroded by one ring).
Rigid props (hard hat, cap, glasses, pencil, tape measure, multimeter, buckles, pouch, hammer) are bmesh pieces
skinned 100 % to one bone.

Animation: UAL1_Standard.glb is imported once, every needed action is sampled at 30 fps (seconds-based, the
import fps is read from the scene) and RETARGETED (armature-space rotation delta from the UAL rest applied onto
the body rest; pelvis translation scaled by the hip-height ratio), then the UAL objects are deleted. Clip map:
idle -> Idle_Loop, walk -> Walk_Loop. The free kit has no point / thumbs_up / hands_on_hips / scratch_beard /
winch_crank: those are Idle_Loop (legs, breathing) + an arm/finger overlay solved from hand targets (2-bone IK,
hand frame, finger curl about the rest bend axis), eased in like the old analytic clips. The result is baked
per frame (every bone, quaternion-continuous) into the rig's action, next to apply_cast's object keys.

Contract with characters.py / render_oneshot: returns rig, body, sig, outfits, extras, masks, tris_all_outfits
(+ hair, impl, bake, make_clip_actions). Rest faces -Y. ANC_bolts sits where s6 put it (head top + 5 cm).
Extra non-deform bones: prop_L/R, hat_root, tape_clip, bandana_tail_1/2 (bandana tail is weighted to them).
"""
import math

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

import mh_blender as B
import mh_paths as MP
from mh_blender import S, L, hexc

Q_DIR = MP.ROOT / "assets" / "cc0" / "quaternius"


def _kit(sub, folder):
    """The zip's top folder, extracted either into <sub>/ (hand-extracted) or next to the zip (tools/fetch_cc0.py)."""
    for cand in (Q_DIR / sub / folder, Q_DIR / folder):
        if cand.exists():
            return cand
    return Q_DIR / sub / folder


UBC = _kit("UBC_Standard", "Universal Base Characters[Standard]")
BASE_GLTF = UBC / "Base Characters" / "Godot - UE" / "Superhero_Male_FullBody.gltf"
SKIN_TEX = UBC / "Base Characters" / "Textures" / "T_Superhero_Male_Ligh.png"
HAIR_DIR = UBC / "Hairstyles" / "Rigged to Head Bone" / "glTF (Godot -Unreal)"
UAL_GLB = _kit("UAL_Standard", "Universal Animation Library[Standard]") / "Unreal-Godot" / "UAL1_Standard.glb"

HEIGHT = 1.778
FPS = 30.0
XFADE = 8                      # frames of world-rotation crossfade at a clip switch

# ---------------------------------------------------------------- body proportion profiles (session 11)
# "s9"  = the session-9/10 body exactly (boxy 40 x 33 cm trunk, short arms, big gloves, collar up to the chin).
# "s11" = proportion pass: normal ~40-year-old with a modest belly (default). Env MH_BOLTS_PROP picks one.
# All lengths are rest, armature space, before the 0.9823 object scale.
PROFILES = {
    "s9": {
        "trunk": [(0.93, 0.192, 0.13, 0.0), (1.02, 0.198, 0.138, -0.006), (1.12, 0.2, 0.15, -0.015),
                  (1.22, 0.194, 0.146, -0.012), (1.32, 0.186, 0.134, -0.006), (1.42, 0.19, 0.12, 0.0), (1.5, 0.18, 0.11, 0.0)],
        "trunk_exp": 2.4, "belly": 0.022, "deltoid_in": 0.12, "biceps_in": 0.4, "forearm_f": 0.84,
        "thigh_slim": 0.05, "inner_thigh": 0.0, "hip_out": 0.03,
        "shoulder_in": 0.035, "shoulder_drop": 0.0, "upperarm_add": 0.0, "forearm_add": 0.0, "hand_scale": 1.0,
        "idle_arm_x": 0.27, "idle_fore": (0.1, -0.16), "arm_out": 0.16,
        "elec_neck": 0.035, "collar": (0.05, 0.012, 0.03, 0.026), "shop_neck": 0.03,
        "bandana": (0.07, 0.036, 0.042, 0.032), "glove_len": 0.06, "glove_flare": 0.012,
        "harness_v": False, "cuff_band": None, "hip_props_x": 1.0, "neck_tilt": 0.0,
        "neck_upright": (0.4, 0.3), "neck_back": (0.0, 0.0), "bandana_tilt": 0.0,
    },
    "s11": {
        # chest 36 / waist 34 / hip 36 cm wide (skin), 25-28 cm deep with a ~2 cm belly; rounder section (exp 2.1)
        "trunk": [(0.93, 0.18, 0.12, 0.0), (1.02, 0.171, 0.124, -0.004), (1.12, 0.168, 0.131, -0.01),
                  (1.22, 0.172, 0.13, -0.008), (1.32, 0.18, 0.124, -0.004), (1.42, 0.188, 0.114, 0.0), (1.5, 0.178, 0.105, 0.0)],
        "trunk_exp": 2.1, "belly": 0.02, "deltoid_in": 0.15, "biceps_in": 0.42, "forearm_f": 0.8,
        "thigh_slim": 0.05, "inner_thigh": 0.14, "hip_out": 0.012,
        "shoulder_in": 0.035, "shoulder_drop": 0.016, "upperarm_add": 0.058, "forearm_add": 0.02, "hand_scale": 0.9,
        "idle_arm_x": 0.2, "idle_fore": (0.06, -0.16), "arm_out": 0.12,
        "elec_neck": 0.068, "collar": (0.045, 0.008, 0.028, 0.02), "shop_neck": 0.06,
        "bandana": (0.088, 0.054, 0.036, 0.024), "glove_len": 0.045, "glove_flare": 0.006,
        "harness_v": True, "cuff_band": (0.08, 0.05), "hip_props_x": 0.93, "neck_tilt": 0.2,
        "neck_upright": (0.65, 0.5), "neck_back": (0.14, 0.07), "bandana_tilt": 0.12,
    },
}
PROP_NAME = __import__("os").environ.get("MH_BOLTS_PROP", "s11")
P = PROFILES.get(PROP_NAME, PROFILES["s11"])
ARM_OUT = P["arm_out"]         # rad: upper arms lifted off the waist in every base clip

# clip -> (UAL base action, overlay or None)
CLIP_MAP = {
    "idle": ("Idle_Loop", None),
    "walk": ("Walk_Loop", None),
    "point": ("Idle_Loop", "point"),
    "thumbs_up": ("Idle_Loop", "thumbs_up"),
    "hands_on_hips": ("Idle_Loop", "hands_on_hips"),
    "scratch_beard": ("Idle_Loop", "scratch_beard"),
    "winch_crank": ("Idle_Loop", "winch_crank"),
    "crank": ("Idle_Loop", "winch_crank"),
}
UAL_NEEDED = ("Idle_Loop", "Walk_Loop")
FINGERS = ("index", "middle", "ring", "pinky")
RELAXED = {"index": (0.22, 0.28, 0.18), "middle": (0.3, 0.36, 0.22), "ring": (0.38, 0.42, 0.26), "pinky": (0.45, 0.45, 0.28)}
EXTRA_BONES = [  # name, parent, head offset from parent head (rest, armature space), length dir
    ("prop_L", "hand_l"), ("prop_R", "hand_r"), ("hat_root", "Head"), ("tape_clip", "pelvis"),
    ("bandana_tail_1", "neck_01"), ("bandana_tail_2", "bandana_tail_1"),
]
LOG = []


def _log(msg):
    LOG.append(msg)
    print("[chars s9] " + msg)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def bump(a, m, b, x):
    """0 at a, 1 at m, 0 at b (smooth)."""
    return smoothstep(a, m, x) if x <= m else 1.0 - smoothstep(m, b, x)


def _ease(t, d=0.35):
    t = max(0.0, min(1.0, t / d))
    return t * t * (3 - 2 * t)


# ================================================================ import helpers
def _import_gltf(path, merge=False):
    before_o = set(bpy.data.objects)
    before = {k: set(getattr(bpy.data, k)) for k in ("meshes", "materials", "images", "actions", "armatures")}
    if merge:
        bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=True)
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    new = {k: [x for x in getattr(bpy.data, k) if x not in before[k]] for k in before}
    new["objects"] = [o for o in bpy.data.objects if o not in before_o]
    return new


def _purge(new, keep=()):
    for o in new["objects"]:
        if o not in keep and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    for k in ("actions", "meshes", "armatures", "materials", "images"):
        coll = getattr(bpy.data, k)
        for x in new.get(k, []):
            try:
                if x.name in coll and x.users == 0:
                    coll.remove(x)
            except ReferenceError:
                pass


def _fcurves_of_action(act):
    try:
        fcs = list(act.fcurves)
        if fcs:
            return fcs
    except Exception:
        pass
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def _dedupe_images():
    for im in list(bpy.data.images):
        nm = im.name
        if len(nm) > 4 and nm[-4] == "." and nm[-3:].isdigit():
            base = bpy.data.images.get(nm[:-4])
            if base is not None and base.size[:] == im.size[:]:
                im.user_remap(base)
                bpy.data.images.remove(im)


# ================================================================ rest-skeleton data + FK
class Skel(object):
    def __init__(self, arm_data):
        self.names, self.parent, self.rest = [], {}, {}

        def walk(b):
            self.names.append(b.name)
            self.parent[b.name] = b.parent.name if b.parent else None
            self.rest[b.name] = b.matrix_local.copy()
            for c in b.children:
                walk(c)
        for b in arm_data.bones:
            if b.parent is None:
                walk(b)
        self.relrest = {n: (self.rest[self.parent[n]].inverted() @ self.rest[n]) if self.parent[n] else self.rest[n].copy()
                        for n in self.names}
        self.restq = {n: self.rest[n].to_quaternion() for n in self.names}

    def head(self, n):
        return self.rest[n].translation.copy()

    def fk(self, rots, pel_off=None):
        """rots: {bone: world (armature-space) rotation Quaternion}; missing bones follow the parent (basis = I)."""
        W = {}
        for n in self.names:
            p = self.parent[n]
            base = (W[p] @ self.relrest[n]) if p else self.relrest[n]
            R = rots.get(n)
            if R is None:
                W[n] = base
                continue
            pos = base.translation
            if n == "pelvis" and pel_off is not None:
                pos = pos + pel_off
            W[n] = Matrix.LocRotScale(pos, R, None)
        return W

    def basis(self, W):
        out = {}
        for n in self.names:
            p = self.parent[n]
            base = (W[p] @ self.relrest[n]) if p else self.relrest[n]
            out[n] = base.inverted_safe() @ W[n]
        return out


def _sample_ual(skel_b):
    """Import UAL1_Standard.glb, retarget the needed actions onto skel_b, delete the import. -> clips table."""
    sc = bpy.context.scene
    fps0 = sc.render.fps / sc.render.fps_base
    new = _import_gltf(UAL_GLB)
    ua = [o for o in new["objects"] if o.type == "ARMATURE"][0]
    sk_u = Skel(ua.data)
    ratio = skel_b.head("pelvis").z / max(1e-6, sk_u.head("pelvis").z)
    clips = {}
    for an in UAL_NEEDED:
        act = bpy.data.actions.get(an)
        if act is None:
            _log("UAL action %s missing" % an)
            continue
        chans = {}
        for fc in _fcurves_of_action(act):
            if not fc.data_path.startswith('pose.bones["'):
                continue
            bn = fc.data_path.split('"')[1]
            prop = fc.data_path.rsplit(".", 1)[-1]
            chans.setdefault(bn, {}).setdefault(prop, {})[fc.array_index] = fc
        f_end = act.frame_range[1]
        dur = f_end / fps0
        n = int(round(dur * FPS))
        rows, pels = [], []
        for k in range(n + 1):
            fr = (k / FPS) * fps0
            rots_u = {}
            pel_u = None
            for bn, ch in chans.items():
                if bn not in sk_u.rest:
                    continue
                q = ch.get("rotation_quaternion")
                if q:
                    qq = Quaternion([q[i].evaluate(fr) if i in q else (1.0 if i == 0 else 0.0) for i in range(4)])
                    qq.normalize()
                else:
                    qq = Quaternion()
                lc = ch.get("location")
                loc = Vector([lc[i].evaluate(fr) if i in lc else 0.0 for i in range(3)]) if lc else Vector()
                rots_u[bn] = (qq, loc)
            # UAL FK with its own rest
            Wu = {}
            for nm in sk_u.names:
                p = sk_u.parent[nm]
                base = (Wu[p] @ sk_u.relrest[nm]) if p else sk_u.relrest[nm]
                qq, loc = rots_u.get(nm, (Quaternion(), Vector()))
                Wu[nm] = base @ Matrix.LocRotScale(loc, qq, None)
            row = {}
            for nm in skel_b.names:
                if nm in Wu and nm in sk_u.rest:
                    R = Wu[nm].to_quaternion() @ sk_u.restq[nm].inverted() @ skel_b.restq[nm]
                    row[nm] = R.normalized()
            pel_u = (Wu["pelvis"].translation - sk_u.head("pelvis")) * ratio
            rows.append(row)
            pels.append(pel_u)
        loop = an.endswith("_Loop")
        clips[an] = {"dur": dur, "rows": rows, "pel": pels, "loop": loop, "n": n}
        _log("retargeted %s: %.2f s, %d samples (import fps %.0f)" % (an, dur, n + 1, fps0))
    _purge(new)
    return clips


# ================================================================ body reshape (rest, armature space, pre-scale)
def _vgroup_weights(ob, names):
    idx = {ob.vertex_groups[n].index: n for n in names if n in ob.vertex_groups}
    out = {n: [0.0] * len(ob.data.vertices) for n in names}
    for v in ob.data.vertices:
        for g in v.groups:
            nm = idx.get(g.group)
            if nm:
                out[nm][v.index] = g.weight
    return out


def _dominant(ob):
    gn = {g.index: g.name for g in ob.vertex_groups}
    dom = []
    for v in ob.data.vertices:
        best, bw = None, 0.0
        for g in v.groups:
            if g.weight > bw:
                best, bw = gn.get(g.group), g.weight
        dom.append(best)
    return dom


def _reshape(body, sk):
    """Superhero -> stocky 48-year-old tradesman. Displacements only (topology and weights untouched)."""
    arm_bones = ["upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "clavicle_l", "clavicle_r"]
    hand_like = [n for n in sk.names if n.startswith(("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_"))]
    W = _vgroup_weights(body, arm_bones + hand_like + ["thigh_l", "thigh_r", "Head", "neck_01"])
    ax_y = {s: (sk.head("upperarm_" + s).y + sk.head("lowerarm_" + s).y) * 0.5 for s in "lr"}
    ax_z = {s: (sk.head("upperarm_" + s).z + sk.head("lowerarm_" + s).z) * 0.5 for s in "lr"}
    sh_x = sk.head("upperarm_l").x
    el_x = sk.head("lowerarm_l").x
    me = body.data
    # slice centres (front/back mid-point) of the trunk before reshaping, 1 cm bins, smoothed
    bins = {}
    for v in me.vertices:
        sd = "l" if v.co.x > 0 else "r"
        if abs(v.co.x) < 0.16 and W["upperarm_" + sd][v.index] + W["clavicle_" + sd][v.index] < 0.05 \
                and W["Head"][v.index] + W["neck_01"][v.index] < 0.05 and 0.85 < v.co.z < 1.55:
            k = int(round(v.co.z * 100))
            lo, hi = bins.get(k, (9.0, -9.0))
            bins[k] = (min(lo, v.co.y), max(hi, v.co.y))
    ks = sorted(bins)

    def cyz(z):
        k = int(round(z * 100))
        near = [kk for kk in ks if abs(kk - k) <= 3]
        if not near:
            return 0.02
        return sum((bins[kk][0] + bins[kk][1]) * 0.5 for kk in near) / len(near)
    for v in me.vertices:
        i = v.index
        p = v.co.copy()
        side = "l" if p.x > 0 else "r"
        wu = W["upperarm_" + side][i]
        wl = W["lowerarm_" + side][i]
        wc = W["clavicle_" + side][i]
        wh = sum(W[n][i] for n in hand_like)
        w_arm = min(1.0, wu + wl + wh)
        w_head = W["Head"][i] + W["neck_01"][i]
        ax = abs(p.x)
        # ---- arms: radial shrink about the horizontal arm axis (T-pose rest)
        if wu + wl > 0.0 and ax > sh_x - 0.06:
            f_u = 1.0 - P["deltoid_in"] * smoothstep(sh_x - 0.04, sh_x + 0.04, ax) - P["biceps_in"] * smoothstep(sh_x + 0.06, sh_x + 0.16, ax)  # deltoid kept round, biceps off
            f_l = P["forearm_f"]
            f = 1.0 - (1.0 - f_u) * wu - (1.0 - f_l) * wl
            dy, dz = p.y - ax_y[side], p.z - ax_z[side]
            p.y = ax_y[side] + dy * f
            p.z = ax_z[side] + dz * f
            # deltoid cap lower
            # deltoid cap: a little padding on top so the arm-down skinning keeps a round shoulder (s9 QC: no dip)
            p.z += 0.012 * wu * bump(sh_x - 0.05, sh_x + 0.03, sh_x + 0.12, ax) * smoothstep(0.0, 0.03, dz)
        wt0 = W["thigh_" + side][i]
        t = max(0.0, 1.0 - w_arm - w_head - 0.6 * wc - wt0)    # torso mask
        if t > 0.0:
            z = p.z
            # flatter, lower pecs (before the barrel blend)
            pec = bump(1.25, 1.38, 1.52, z) * smoothstep(-0.02, -0.11, p.y) * bump(0.0, 0.09, 0.22, ax)
            p.y += 0.045 * pec * t
            # barrel trunk: blend every torso slice towards a stocky superellipse (chest 44", waist 40")
            wb = smoothstep(0.93, 1.03, z) * (1.0 - smoothstep(1.3, 1.4, z)) * t
            if wb > 0.0:
                a_, b_, dc = _trunk(z)
                cy = cyz(z) + dc
                ang = math.atan2((p.y - cy) / b_, p.x / a_)
                ca, sa = math.cos(ang), math.sin(ang)
                e = 2.0 / P["trunk_exp"]
                tx = a_ * math.copysign(abs(ca) ** e, ca)
                ty = cy + b_ * math.copysign(abs(sa) ** e, sa)
                p.x += (tx - p.x) * wb
                p.y += (ty - p.y) * wb
            # belly ~3.5 cm proud of the chest line (front, centred)
            front = smoothstep(0.0, -0.09, p.y)
            p.y -= P["belly"] * bump(0.98, 1.14, 1.32, z) * front * math.exp(-(p.x / 0.16) ** 2) * t
            # narrower traps/shoulder line a touch
            p.z -= 0.008 * bump(1.42, 1.5, 1.6, z) * smoothstep(0.06, 0.16, ax) * t
        # thighs: superhero quads a bit slimmer at the front
        wt = W["thigh_" + side][i]
        if wt > 0.3 and p.z < 0.9:
            cx = sk.head("thigh_" + side).x
            inner = smoothstep(0.0, 0.03, abs(cx) - abs(p.x)) * smoothstep(0.55, 0.75, p.z)   # inner thigh: open a gap under the crotch
            p.x = cx + (p.x - cx) * (1.0 - P["thigh_slim"] * wt - P["inner_thigh"] * wt * inner)
            p.y = p.y + 0.006 * wt * smoothstep(0.0, -0.09, p.y)
        # fuller hips: outer upper thigh / hip pushed out, fading towards mid-thigh
        if wt > 0.0 and p.z > 0.7:
            cx = sk.head("thigh_" + side).x
            out_ = smoothstep(0.0, 0.06, abs(p.x) - abs(cx))
            p.x += math.copysign(P["hip_out"] * wt * smoothstep(0.7, 0.92, p.z) * out_, p.x)
        v.co = p
    me.update()


TRUNK = P["trunk"]  # z, half-width, half-depth, centre shift (y)


def _trunk(z):
    for (z0, a0, b0, c0), (z1, a1, b1, c1) in zip(TRUNK, TRUNK[1:]):
        if z <= z1:
            u = max(0.0, min(1.0, (z - z0) / (z1 - z0)))
            return a0 + (a1 - a0) * u, b0 + (b1 - b0) * u, c0 + (c1 - c0) * u
    return TRUNK[-1][1:]


SHOULDER_IN = P["shoulder_in"]      # m per side: arm chains moved in (regular build, not superhero shoulders)


def _narrow_shoulders(rig, body, d):
    """Move each arm chain (bones + skin) d metres towards the midline; clavicle-weighted skin follows half-way."""
    chain = {s: [b.name for b in rig.data.bones if b.name.endswith("_" + s) and
                 b.name.startswith(("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky"))] for s in "lr"}
    gi = {g.name: g.index for g in body.vertex_groups}
    for v in body.data.vertices:
        s = "l" if v.co.x > 0 else "r"
        names = set(gi[n] for n in chain[s] if n in gi)
        w = sum(g.weight for g in v.groups if g.group in names)
        wc = sum(g.weight for g in v.groups if g.group == gi.get("clavicle_" + s))
        # whole shoulder girdle narrows smoothly (no step between the moved arm and the trunk -> no concave dip)
        girdle = smoothstep(0.05, 0.19, abs(v.co.x)) * smoothstep(1.28, 1.4, v.co.z)
        f = min(1.0, max(w + 0.5 * wc, girdle))
        if f > 0:
            v.co.x -= math.copysign(d * f, v.co.x)
    vl = bpy.context.view_layer
    vl.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    for s, sx in (("l", 1.0), ("r", -1.0)):
        for n in chain[s]:
            b = eb[n]
            if b.parent is not None and b.parent.name in chain[s] and b.use_connect:
                b.tail.x -= sx * d
            else:
                b.head.x -= sx * d
                b.tail.x -= sx * d
        eb["clavicle_" + s].tail.x -= sx * d
    bpy.ops.object.mode_set(mode="OBJECT")
    body.data.update()


def _ramp(a, b, x):
    return smoothstep(a, b, x)


def _normalize_arms(rig, body, drop, add_u, add_l, hand_s):
    """Session 11 proportion pass on the arm chains (bones + skin, rest T-pose):
    - drop: the whole shoulder girdle lowered `drop` m (same smooth girdle blend as _narrow_shoulders, so the
      trapezius slopes down to a lower shoulder with no step/dip);
    - add_u / add_l: upper arm / forearm lengthened, the stretch spread over the shaft (deltoid, elbow and wrist
      shapes kept);
    - hand_s: hand + fingers scaled about the wrist joint."""
    if not (drop or add_u or add_l or hand_s != 1.0):
        return
    chain = {s: [b.name for b in rig.data.bones if b.name.endswith("_" + s) and
                 b.name.startswith(("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky"))] for s in "lr"}
    bones = rig.data.bones
    geo = {}
    for s in "lr":
        S0 = bones["upperarm_" + s].head_local.copy() - Vector((0, 0, drop))
        E0 = bones["lowerarm_" + s].head_local.copy() - Vector((0, 0, drop))
        W0 = bones["hand_" + s].head_local.copy() - Vector((0, 0, drop))
        d = (W0 - S0).normalized()
        L1 = (E0 - S0).dot(d)
        Lw = (W0 - S0).dot(d)
        geo[s] = (S0, W0, d, L1, Lw)

    def mapping(p, s):
        """p already dropped. Returns the stretched/scaled point (full arm weight)."""
        S0, W0, d, L1, Lw = geo[s]
        t = (p - S0).dot(d)
        delta = add_u * _ramp(0.07, L1 - 0.05, t) + add_l * _ramp(L1 + 0.05, Lw - 0.05, t)
        q = p + d * delta
        if hand_s != 1.0 and t > Lw - 0.03:
            sc = 1.0 - (1.0 - hand_s) * _ramp(Lw - 0.03, Lw + 0.02, t)
            Wn = W0 + d * (add_u + add_l)
            q = Wn + (q - Wn) * sc
        return q

    gi = {g.name: g.index for g in body.vertex_groups}
    for v in body.data.vertices:
        s = "l" if v.co.x > 0 else "r"
        names = set(gi[n] for n in chain[s] if n in gi)
        w = min(1.0, sum(g.weight for g in v.groups if g.group in names))
        wc = sum(g.weight for g in v.groups if g.group == gi.get("clavicle_" + s))
        girdle = smoothstep(0.05, 0.19, abs(v.co.x)) * smoothstep(1.28, 1.4, v.co.z)
        f = min(1.0, max(w + 0.5 * wc, girdle))
        p = v.co.copy()
        p.z -= drop * f
        if w > 0.0:
            p = p + (mapping(p, s) - p) * w
        v.co = p
    vl = bpy.context.view_layer
    vl.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    for s in "lr":
        new = {}
        for n in chain[s]:
            b = eb[n]
            new[n] = (mapping(b.head - Vector((0, 0, drop)), s), mapping(b.tail - Vector((0, 0, drop)), s))
        for n in chain[s]:
            eb[n].head, eb[n].tail = new[n]
        if not eb["upperarm_" + s].use_connect:
            eb["clavicle_" + s].tail.z -= drop
    bpy.ops.object.mode_set(mode="OBJECT")
    body.data.update()
    _log("arms: shoulders -%.1f cm, upper arm +%.1f cm, forearm +%.1f cm, hands x%.2f"
         % (drop * 100, add_u * 100, add_l * 100, hand_s))


def _clear_custom_normals(me):
    for a in list(me.attributes):
        if a.name == "custom_normal":
            me.attributes.remove(a)
    try:
        me.free_normals_split()
    except Exception:
        pass
    for p in me.polygons:
        p.use_smooth = True


# ================================================================ measurements (rest, pre-scale)
class Meas(object):
    def __init__(self, body, eyes, brows, hair_objs):
        dom = _dominant(body)
        head = [body.matrix_local @ v.co for v, d in zip(body.data.vertices, dom) if d == "Head"]
        self.head = head
        xs = [p.x for p in head]
        zs = [p.z for p in head]
        ys = [p.y for p in head]
        self.top = max(zs)
        for h in hair_objs:
            for v in h.data.vertices:
                self.top = max(self.top, v.co.z)
        self.head_top_skin = max(zs)
        yf = min(ys)
        face = [p.z for p in head if p.y < yf + 0.045 and abs(p.x) < 0.03]
        self.chin_z = min(face) if face else min(zs)
        self.half_w = (max(xs) - min(xs)) * 0.5
        self.y_front, self.y_back = min(ys), max(ys)
        ev = [v.co for v in eyes.data.vertices]
        self.eye_z = sum(p.z for p in ev) / len(ev)
        self.eye_y = min(p.y for p in ev)
        bv = [v.co for v in brows.data.vertices]
        self.brow_z = max(p.z for p in bv)
        self.brow_y = min(p.y for p in bv)
        self.body_pts = [(v.co.copy(), d) for v, d in zip(body.data.vertices, dom)]
        self.height = max(v.co.z for v in body.data.vertices)

    def neck_ring(self, z, win=0.01):
        """(half-width, half-depth, centre y) of the neck/upper-trunk section at z (rest)."""
        pts = [p for p, d in self.body_pts if abs(p.z - z) < win and abs(p.x) < 0.11
               and d in ("neck_01", "Head", "spine_03", "clavicle_l", "clavicle_r")]
        if not pts:
            return 0.06, 0.06, 0.03
        ys = [p.y for p in pts]
        return max(abs(p.x) for p in pts), (max(ys) - min(ys)) * 0.5, (max(ys) + min(ys)) * 0.5

    def foot_box(self, side):
        pts = [p for p, d in self.body_pts if d and d.startswith(("foot_", "ball_")) and d.endswith(side)]
        xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
        return min(xs), max(xs), min(ys), max(ys), max(zs)

    def head_front_y(self, x, z, win=0.012):
        best = None
        for p in self.head:
            if abs(p.x - x) < win and abs(p.z - z) < win:
                best = p.y if best is None else min(best, p.y)
        return best if best is not None else self.y_front

    def head_side_x(self, z, sign, win=0.012):
        best = 0.0
        for p in self.head:
            if abs(p.z - z) < win and p.x * sign > 0:
                best = max(best, abs(p.x))
        return best or self.half_w

    def torso_front_y(self, x, z, win=0.02):
        best = None
        for p, d in self.body_pts:
            if abs(p.x - x) < win and abs(p.z - z) < win and p.y < 0.05:
                best = p.y if best is None else min(best, p.y)
        return best if best is not None else -0.12

    def torso_half_w(self, z, win=0.02):
        best = 0.0
        for p, d in self.body_pts:
            if abs(p.z - z) < win and d and not d.startswith(("hand", "lowerarm", "upperarm", "thumb", "index", "middle",
                                                                  "ring", "pinky")):
                best = max(best, abs(p.x))
        return best


# ================================================================ shells (clothes from the body's own faces)
HANDS = ("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")


def _dom_groups_bm(bm, gn):
    dl = bm.verts.layers.deform.verify()
    out = {}
    for v in bm.verts:
        best, bw = "", 0.0
        for gi, w in v[dl].items():
            if w > bw:
                best, bw = gn.get(gi, ""), w
        out[v] = best
    return out


def _face_group(f, vdom):
    acc = {}
    for v in f.verts:
        acc[vdom[v]] = acc.get(vdom[v], 0) + 1
    return max(acc, key=acc.get)


def _taubin(bm, verts, iters, lam=0.5, mu=-0.53, pin_boundary=True):
    """Volume-preserving smoothing (removes muscle definition / toes under cloth)."""
    vs = [v for v in verts if not (pin_boundary and v.is_boundary)]
    nb = {v: [e.other_vert(v) for e in v.link_edges] for v in vs}
    for k in range(iters * 2):
        f = lam if k % 2 == 0 else mu
        new = {}
        for v in vs:
            n = nb[v]
            if not n:
                continue
            avg = Vector((0.0, 0.0, 0.0))
            for u in n:
                avg += u.co
            avg /= len(n)
            new[v] = v.co + (avg - v.co) * f
        for v, c in new.items():
            v.co = c


CLOTH_BASE = {}


def _cloth_base(body, iters=60):
    """One smoothed copy of the body (Taubin, muscle definition / toes gone; head, hands and feet pinned) that every
    garment shell is cut from, so stacked layers (coveralls -> harness, shirt -> pants -> belt) stay parallel."""
    me = body.data.copy()
    me.name = "bolts_q_clothbase"
    gn = {g.index: g.name for g in body.vertex_groups}
    bm = bmesh.new()
    bm.from_mesh(me)
    vdom = _dom_groups_bm(bm, gn)
    free = [v for v in bm.verts if not (vdom[v].startswith(HANDS) or vdom[v] in ("Head",)
                                        or vdom[v].startswith(("foot_", "ball_")))]
    _taubin(bm, free, iters, pin_boundary=False)
    bm.to_mesh(me)
    bm.free()
    CLOTH_BASE["me"] = me
    return me


def _shell(name, body, select, offset, mats, mat_index=None, rig=None, cuts=(), smooth=0, plain=0):
    """Copy the smoothed cloth base (or the body), bisect along `cuts` [(co, no)], keep faces with
    select(centre, dominant_group), push verts out by offset(co, normal) along the FULL-mesh normals."""
    src = CLOTH_BASE.get("me") or body.data
    me = src.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    L.link(ob)
    if len(ob.vertex_groups) == 0:
        for g in body.vertex_groups:
            ob.vertex_groups.new(name=g.name)
    gn = {g.index: g.name for g in body.vertex_groups}
    bm = bmesh.new()
    bm.from_mesh(me)
    for co, no in cuts:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no), dist=1e-5)
    vdom = _dom_groups_bm(bm, gn)
    bm.normal_update()
    vnorm = {v: v.normal.copy() for v in bm.verts}
    dead = [f for f in bm.faces if not select(f.calc_center_median(), _face_group(f, vdom))]
    bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    if smooth:
        _taubin(bm, list(bm.verts), smooth)
    if plain:
        _taubin(bm, list(bm.verts), plain, 0.5, 0.0, pin_boundary=False)
    for f in bm.faces:                         # classify on the cut surface (before the offset moves centres)
        f.material_index = mat_index(f.calc_center_median()) if mat_index else 0
        f.smooth = True
    bm.normal_update()
    moves = [(v, vnorm.get(v, v.normal).copy() if not (smooth or plain) else v.normal.copy()) for v in bm.verts]
    for v, nrm in moves:
        v.co = v.co + nrm * offset(v.co.copy(), nrm)
    me.materials.clear()                       # slots first: clearing them afterwards resets material_index
    for m in mats:
        me.materials.append(m)
    bm.to_mesh(me)
    bm.free()
    _clear_custom_normals(me)
    ob.parent = rig
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    mod = ob.modifiers.new("armature", "ARMATURE")
    mod.object = rig
    return ob


def _hide_group(body, name, preds, erode=1):
    """Vertex group `name` = body verts inside any region predicate, eroded `erode` rings (Mask removes a face as
    soon as one vertex is hidden, so the erosion keeps every removed face fully under the garment)."""
    me = body.data
    dom = _dominant(body)
    inside = [any(p(v.co, dom[v.index] or "") for p in preds) for v in me.vertices]
    for _ in range(erode):
        nxt = list(inside)
        for e in me.edges:
            a, b = e.vertices
            if not inside[a] or not inside[b]:
                nxt[a] = nxt[b] = False
        inside = nxt
    vg = body.vertex_groups.get(name) or body.vertex_groups.new(name=name)
    vg.add([i for i, k in enumerate(inside) if k], 1.0, "REPLACE")
    return sum(inside)



# ================================================================ materials (imported ones re-tinted, fog-wrapped)
def _principled(m):
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _wrap_fog(m):
    """Route the material through scene_lib's fog mix (as every S.pbr material), once."""
    nt = m.node_tree
    if any(n.type == "CAMERA" for n in nt.nodes):
        return
    p = _principled(m)
    if p is not None:
        S._finish(m, p.outputs[0])


def _skin_material(body):
    m = body.data.materials[0]
    m.name = "bolts_q_skin"
    nt = m.node_tree
    p = _principled(m)
    img = bpy.data.images.load(str(SKIN_TEX), check_existing=True)
    tex = None
    for lk in nt.links:
        if lk.to_node == p and lk.to_socket.name == "Base Color" and lk.from_node.type == "TEX_IMAGE":
            tex = lk.from_node
    if tex is None:
        tex = nt.nodes.new("ShaderNodeTexImage")
    old = tex.image
    tex.image = img
    if old is not None and old.users == 0:
        bpy.data.images.remove(old)
    # warm sun-tan tint towards #D9A383 and a little less saturated (the albedo is orange-ish)
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 0.86
    hs.inputs["Value"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], hs.inputs["Color"])
    nt.links.new(hs.outputs["Color"], p.inputs["Base Color"])
    try:
        p.inputs["Subsurface Weight"].default_value = 0.1
        p.inputs["Subsurface Radius"].default_value = (0.012, 0.005, 0.003)
    except Exception:
        pass
    _wrap_fog(m)
    return m


def _ramp_tint(m, name, stops, rough=0.8):
    """Image luminance -> colour ramp (salt-and-pepper), keeps the image alpha link."""
    m.name = name
    nt = m.node_tree
    p = _principled(m)
    tex = None
    for lk in nt.links:
        if lk.to_node == p and lk.to_socket.name == "Base Color":
            tex = lk.from_node
    if tex is None:
        p.inputs["Base Color"].default_value = stops[len(stops) // 2][1]
    else:
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(tex.outputs[0], bw.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = stops[0]
        els[1].position, els[1].color = stops[-1]
        for pos, col in stops[1:-1]:
            e = els.new(pos)
            e.color = col
        nt.links.new(bw.outputs[0], ramp.inputs[0])
        nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    try:
        p.inputs["Specular IOR Level"].default_value = 0.35
    except Exception:
        pass
    _wrap_fog(m)
    return m


def _eye_material(m):
    m.name = "bolts_q_eyes"
    nt = m.node_tree
    p = _principled(m)
    for lk in list(nt.links):
        if lk.to_node == p and lk.to_socket.name == "Base Color":
            src = lk.from_socket
            hs = nt.nodes.new("ShaderNodeHueSaturation")
            hs.inputs["Hue"].default_value = 1.0                 # +0.5: brown -> blue-gray #5B7A8C
            hs.inputs["Saturation"].default_value = 0.55
            nt.links.new(src, hs.inputs["Color"])
            nt.links.new(hs.outputs["Color"], p.inputs["Base Color"])
            break
    p.inputs["Roughness"].default_value = 0.12
    _wrap_fog(m)
    return m


# ================================================================ rig
def _add_extra_bones(rig, sk_before):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    hl, hr = eb["hand_l"], eb["hand_r"]
    for nm, hb, sx in (("prop_L", hl, 1), ("prop_R", hr, -1)):
        b = eb.new(nm)
        c = (hb.head + hb.tail) * 0.5 + Vector((sx * 0.04, -0.02, -0.03))
        b.head, b.tail = c, c + Vector((0, -0.1, 0))
        b.parent = hb
    hd = eb["Head"]
    b = eb.new("hat_root")
    b.head, b.tail = hd.tail + Vector((0, 0, 0.06)), hd.tail + Vector((0, 0, 0.14))
    b.parent = hd
    pv = eb["pelvis"]
    b = eb.new("tape_clip")
    kx = P["hip_props_x"]
    b.head, b.tail = Vector((0.15 * kx, -0.14, 0.99)), Vector((0.15 * kx, -0.14, 1.04))
    b.parent = pv
    nk = eb["neck_01"]
    b1 = eb.new("bandana_tail_1")
    bz = 0.07 - P["bandana"][0]          # bandana lowered with the s11 profile (0 for s9)
    b1.head, b1.tail = Vector((0.0, -0.11, 1.5 + bz)), Vector((0.004, -0.118, 1.45 + bz))
    b1.parent = nk
    b2 = eb.new("bandana_tail_2")
    b2.head, b2.tail = b1.tail, Vector((0.008, -0.122, 1.40 + bz))
    b2.parent = b1
    b2.use_connect = True
    for nm in ("prop_L", "prop_R", "hat_root", "tape_clip"):
        eb[nm].use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"


def _bones_tuples(rig):
    return [(b.name, tuple(b.head_local), tuple(b.tail_local), b.parent.name if b.parent else None) for b in rig.data.bones]


# ================================================================ build
def build_bolts(ctx, char):
    import characters as CH
    import characters_s6 as C6
    LOG[:] = []
    B.part_collection("characters")
    M = C6._mats_s6(CH)
    # ---------------- base body
    new = _import_gltf(BASE_GLTF, merge=True)
    objs = new["objects"]
    rig = [o for o in objs if o.type == "ARMATURE"][0]
    body = [o for o in objs if o.type == "MESH" and o.name.startswith("SuperHero")][0]
    eyes = [o for o in objs if o.type == "MESH" and o.name.startswith("Eyes")][0]
    brows = [o for o in objs if o.type == "MESH" and o.name.startswith("Eyebrows")][0]
    for o in objs:
        if o.type == "MESH" and o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o, do_unlink=True)
    rig.name = rig.data.name = "bolts_rig"
    body.name = body.data.name = "bolts_body"
    eyes.name, brows.name = "bolts_eyes", "bolts_brows"
    rig.animation_data_clear()
    rig.rotation_mode = "XYZ"          # glTF imports QUATERNION; apply_cast keys rotation_euler (yaw)
    # ---------------- hair (Rigged to Head Bone): re-point at the body rig, after a Head-rest check
    hair = {}
    head_rest = rig.data.bones["Head"].matrix_local.copy()
    for nm, key in (("Hair_Beard", "beard"), ("Hair_Buzzed", "hair")):
        hn = _import_gltf(HAIR_DIR / (nm + ".gltf"), merge=True)
        ha = [o for o in hn["objects"] if o.type == "ARMATURE"]
        hm = [o for o in hn["objects"] if o.type == "MESH" and not o.name.startswith("Icosphere")][0]
        if ha:
            hr = ha[0].data.bones["Head"].matrix_local
            d = max(abs(a - b) for r1, r2 in zip(hr, head_rest) for a, b in zip(r1, r2))
            if d > 1e-4:
                corr = head_rest @ hr.inverted()
                hm.data.transform(corr)
                _log("%s Head rest differs by %.4f -> corrected" % (nm, d))
        hm.parent = rig
        for m in hm.modifiers:
            if m.type == "ARMATURE":
                m.object = rig
        hm.name = hm.data.name = "bolts_" + key
        hair[key] = hm
        _purge(hn, keep=(hm,))
    _dedupe_images()
    sk = Skel(rig.data)
    # ---------------- reshape + materials
    _reshape(body, sk)
    _narrow_shoulders(rig, body, SHOULDER_IN)
    _normalize_arms(rig, body, P["shoulder_drop"], P["upperarm_add"], P["forearm_add"], P["hand_scale"])
    for o in [body] + list(hair.values()):
        _clear_custom_normals(o.data)
    _skin_material(body)
    _ramp_tint(hair["beard"].data.materials[0], "bolts_q_beard",
               [(0.18, hexc("3a3632")), (0.42, hexc("6e6a66")), (0.7, hexc("d8d4cf"))], 0.85)
    _ramp_tint(hair["hair"].data.materials[0], "bolts_q_hair",
               [(0.2, hexc("4a4038")), (0.45, hexc("6b5d52")), (0.72, hexc("9a928a"))], 0.85)
    if brows.data.materials and brows.data.materials[0] is not None:
        bm_ = brows.data.materials[0].copy()
        brows.data.materials[0] = bm_
        _ramp_tint(bm_, "bolts_q_brows", [(0.2, hexc("2e2722")), (0.6, hexc("4a4038"))], 0.85)
    _eye_material(eyes.data.materials[0])
    _dedupe_images()
    # ---------------- extra bones + scale
    _add_extra_bones(rig, sk)
    sk = Skel(rig.data)
    meas = Meas(body, eyes, brows, list(hair.values()))
    scale = HEIGHT / meas.height
    rig.scale = (scale, scale, scale)
    _log("body height %.3f m -> object scale %.4f (%.3f m)" % (meas.height, scale, HEIGHT))
    # ---------------- outfits as shells
    _cloth_base(body)
    outfits, keeps = {}, {}
    outfits["electrician"], keeps["electrician"] = _electrician(body, M, rig, meas)
    outfits["workshop"], keeps["workshop"] = _workshop(body, M, rig, meas)
    extras = {"fall_arrest_harness": _harness(body, M, rig, meas)}
    bpy.data.meshes.remove(CLOTH_BASE.pop("me"))
    masks = {}
    for o, km in keeps.items():
        n = _hide_group(body, "hide_under_" + o, km)
        mm = body.modifiers.new("mask_" + o, "MASK")
        mm.vertex_group = "hide_under_" + o
        mm.invert_vertex_group = True
        mm.show_render = mm.show_viewport = False
        body.modifiers.move(len(body.modifiers) - 1, 0)
        masks[o] = mm
        _log("hide_under_%s: %d body verts" % (o, n))
    # rigid outfit props go into the same outfit objects (joined)
    _join(outfits["electrician"], _electrician_props(rig, M, meas))
    _join(outfits["workshop"], _workshop_props(rig, M, meas))
    sig = _signatures(body, rig, M, meas)
    for o in list(outfits.values()) + list(extras.values()):
        o.hide_render = True
    # ---------------- anchor where s6 had it (head top + 5 cm; rest, world)
    anc = L.link(bpy.data.objects.new("ANC_bolts", None))
    anc.parent = rig
    anc.parent_type = "BONE"
    anc.parent_bone = "Head"
    bpy.context.view_layer.update()
    anc.matrix_world = rig.matrix_world @ Matrix.Translation(Vector((0.0, -0.01, 1.84)) / scale)
    S.anchor(ctx, "bolts", anc)
    # ---------------- animation
    clips = _sample_ual(sk)
    anim = Animator(rig, sk, clips, meas)
    core = [body, eyes, brows] + list(hair.values())
    tris = tris_of(core + list(sig.values()) + list(outfits.values()) + list(extras.values()))
    vis = {o: tris_of(core + list(sig.values()) + [outfits[o]] + ([extras["fall_arrest_harness"]] if o == "electrician" else []))
           for o in outfits}
    _log("visible render tris per outfit: %s (body core %d)" % (vis, tris_of(core)))
    return {"rig": rig, "body": body, "sig": sig, "outfits": outfits, "extras": extras, "masks": masks,
            "tris_all_outfits": tris, "tris_visible": vis, "hair": hair, "impl": "s9_quaternius",
            "bake": anim.bake, "make_clip_actions": anim.make_clip_actions, "log": LOG}


def tris_of(objs):
    n = 0
    for o in objs:
        lv = 0
        for m in o.modifiers:
            if m.type == "SUBSURF":
                lv = m.render_levels
        q = sum(len(p.vertices) - 2 for p in o.data.polygons)
        n += q * (4 ** lv) if lv else q
    return n


def _join(dst, src):
    """Join src objects (same rig, armature modifier) into dst, keeping materials and weights."""
    src = [s for s in src if s is not None]
    if not src:
        return dst
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    for s in src:
        s.select_set(True)
    dst.select_set(True)
    vl.objects.active = dst
    with bpy.context.temp_override(active_object=dst, selected_editable_objects=src + [dst], object=dst):
        bpy.ops.object.join()
    return dst


# ---------------------------------------------------------------- region predicates
def _is_hand(g):
    return g.startswith(HANDS)


def _is_head(g):
    return g in ("Head",)


def _neck_cut(c, z_cut, yf=0.0, k=0.0):
    """Above the neckline: a plane through the front of the neck at z_cut, rising k m per m towards the back (s11)."""
    return c.z > z_cut + k * (c.y - yf) and abs(c.x) < 0.12


def _neck_plane(meas, z_cut):
    """(front y of the neck at z_cut, tilt, bisect cut) for the profile's neckline."""
    k = P["neck_tilt"]
    if not k:
        return 0.0, 0.0, _zc(z_cut)
    _hw, hd, cy = meas.neck_ring(z_cut)
    yf = cy - hd
    return yf, k, [((0.0, yf, z_cut), (0.0, -k, 1.0))]


def _zc(*zs):
    return [((0, 0, z), (0, 0, 1)) for z in zs]


def _xc(*xs):
    out = []
    for x in xs:
        out += [((x, 0, 0), (1, 0, 0)), ((-x, 0, 0), (1, 0, 0))]
    return out


BOOT_TOP = 0.2


def _electrician(body, M, rig, meas):
    neck_z = meas.chin_z - P["elec_neck"]
    wrist_x = rig.data.bones["hand_l"].head_local.x
    cb0, cb1 = (0.58, 0.61) if P["cuff_band"] is None else (wrist_x - P["cuff_band"][0], wrist_x - P["cuff_band"][1])
    cuff_x = wrist_x - 0.02
    leg_end = BOOT_TOP - 0.06

    nyf, nk, ncut = _neck_plane(meas, neck_z)

    def sel(c, g):
        if _is_hand(g) or _is_head(g) or _neck_cut(c, neck_z, nyf, nk):
            return False
        return abs(c.x) < cuff_x and c.z > leg_end

    def off(co, n):
        o = 0.012
        if co.z < 0.95 and abs(co.x) < 0.3:                     # baggier legs, flared over the boots
            o += 0.004 + 0.016 * smoothstep(0.32, leg_end, co.z)
        if 0.9 < co.z < 1.3 and co.y < 0:                       # slack over the belly
            o += 0.004
        return o

    def mi(c):
        ax = abs(c.x)
        if 1.33 < c.z < 1.37 and ax < 0.3:                       # chest band (all round, as the concept)
            return 1
        if 0.98 < c.z < 1.035 and ax < 0.3:                      # belt
            return 2
        if cb0 < ax < cb1:                                       # sleeve bands
            return 1
        if 0.3 < c.z < 0.335 and ax < 0.3:                       # leg bands
            return 1
        if ax < 0.004 and c.y < 0 and 0.95 < c.z < neck_z:       # zip line
            return 3
        return 0
    cuts = _zc(leg_end, 1.33, 1.37, 0.98, 1.035, 0.3, 0.335) + ncut + _xc(cuff_x, cb0, cb1, 0.004, 0.12)
    cov = _shell("bolts_outfit_electrician", body, sel, off, [M["cover"], M["strip"], M["belt"], M["buckle"]], mi, rig, cuts,
                 smooth=0)
    # insulated gloves: hand faces + a gauntlet cuff over the sleeve end
    gx = wrist_x - P["glove_len"]
    gsel = lambda c, g: (_is_hand(g) or abs(c.x) > gx) and c.z > 1.0           # noqa: E731
    gl = _shell("bolts_q_gloves", body, gsel,
                lambda co, n: 0.0045 + P["glove_flare"] * smoothstep(wrist_x + 0.02, wrist_x - 0.03, abs(co.x)), [M["gloves"]], None, rig,
                _xc(gx))
    bo, bsel = _boots(body, M, rig, meas)
    c0, c1, g0, g1 = P["collar"]
    co_ = _neck_band("bolts_q_collar", rig, meas, neck_z - c0, neck_z + c1, g0, g1, [M["cover"]],
                     ["spine_03", "neck_01"], 4, 0.02, tilt=(nk, nyf))
    _join(cov, [gl, bo, co_])
    return cov, [sel, gsel, bsel]


def _boots(body, M, rig, meas):
    """Work boots: lofted shaft + foot + sole (subsurf 1), smooth weights on calf/foot/ball; feet masked."""
    C6 = C6s()
    a = C6.AutoSkin(_bones_tuples(rig))
    for side in ("l", "r"):
        x0, x1, y0, y1, _z1 = meas.foot_box(side)
        xc = (x0 + x1) * 0.5
        w = (x1 - x0) * 0.5 + 0.016
        heel, toe = y1 + 0.016, y0 - 0.02
        L_ = heel - toe
        ys = [heel, heel - 0.18 * L_, heel - 0.5 * L_, heel - 0.8 * L_, toe]
        path = [(xc, y, z) for y, z in zip(ys, (0.064, 0.064, 0.056, 0.042, 0.036))]
        a.piece(lambda bm, path=path, w=w: C6.sweep(bm, path, [w * 0.82, w * 0.95, w, w * 1.0, w * 0.62],
                                                     [0.058, 0.062, 0.052, 0.036, 0.026], 18, 0, power=2.6),
                ["foot_" + side, "ball_" + side], 6.0)
        spath = [(xc, y, 0.014) for y in ys]
        a.piece(lambda bm, spath=spath, w=w: C6.sweep(bm, spath, [w * 0.86, w * 1.0, w * 1.05, w * 1.05, w * 0.7],
                                                       0.013, 18, 1, power=4.0), ["foot_" + side, "ball_" + side], 6.0)
        ay = rig.data.bones["foot_" + side].head_local.y - 0.008
        a.piece(lambda bm, xc=xc, ay=ay: C6.sweep(bm, [(xc, ay + 0.004, 0.05), (xc, ay, 0.12), (xc, ay - 0.004, BOOT_TOP + 0.01)],
                                                   [0.05, 0.047, 0.049], [0.058, 0.052, 0.054], 18, 0, cap0=False, cap1=False,
                                                   up=(0, 1, 0)), ["calf_" + side, "foot_" + side], 6.0, bias={"calf_" + side: 0.8})
    ob = a.finish("bolts_q_boots", [M["boots"], M["sole"]], rig, subsurf=1)
    sel = lambda c, g: c.z < BOOT_TOP - 0.015 and not _is_hand(g)        # noqa: E731
    return ob, sel


def _neck_band(name, rig, meas, z0, z1, grow0, grow1, mats, bones, n=4, flare=0.0, tilt=(0.0, 0.0)):
    C6 = C6s()
    a = C6.AutoSkin(_bones_tuples(rig))
    rings = []
    for k in range(n):
        u = k / (n - 1.0)
        z = z0 + (z1 - z0) * u
        hw, hd, cy = meas.neck_ring(z)
        g = grow0 + (grow1 - grow0) * u + flare * (1 - u) ** 2
        rings.append((z, hw + g, hd + g, 0.0, cy))
    k, yf = tilt

    def mk(bm):
        before = set(bm.verts)
        C6.vloft(bm, rings, 28, 0, 2.2)
        if k:
            for v in bm.verts:
                if v not in before:
                    v.co.z += k * max(0.0, v.co.y - yf)
    a.piece(mk, bones, 4.0)
    return a.finish(name, mats, rig, subsurf=1)


def _workshop(body, M, rig, meas):
    neck_z = meas.chin_z - P["shop_neck"]
    el_x = rig.data.bones["lowerarm_l"].head_local.x
    sleeve_x = el_x + 0.06
    roll_x = sleeve_x - 0.035

    nyf, nk, ncut = _neck_plane(meas, neck_z)

    def shirt_sel(c, g):
        if _is_hand(g) or _is_head(g) or _neck_cut(c, neck_z, nyf, nk):
            return False
        return c.z > 0.97 and abs(c.x) < sleeve_x

    def shirt_off(co, n):
        return 0.02 if abs(co.x) > roll_x else 0.009 + (0.004 if 0.95 < co.z < 1.3 and co.y < 0 else 0.0)
    sh = _shell("bolts_outfit_workshop", body, shirt_sel, shirt_off, [M["henley"]], None, rig, _zc(0.97) + ncut + _xc(sleeve_x, roll_x, 0.12),
                smooth=0)
    psel = lambda c, g: BOOT_TOP - 0.06 < c.z < 1.05 and abs(c.x) < 0.3 and not _is_hand(g)     # noqa: E731
    pa = _shell("bolts_q_pants", body, psel,
                lambda co, n: 0.013 + 0.016 * smoothstep(0.32, BOOT_TOP - 0.06, co.z) + (0.007 if co.z > 0.985 else 0.0),
                [M["pants"], M["belt"]], lambda c: 1 if c.z > 0.985 else 0, rig, _zc(BOOT_TOP - 0.06, 1.05, 0.985), smooth=0)
    bo, bsel = _boots(body, M, rig, meas)
    co_ = _neck_band("bolts_q_henley_collar", rig, meas, neck_z - 0.03, neck_z + 0.006, 0.022, 0.016, [M["henley"]],
                     ["spine_03", "neck_01"], 3, 0.01, tilt=(nk, nyf))
    _join(sh, [pa, bo, co_])
    return sh, [shirt_sel, psel, bsel]


def _harness(body, M, rig, meas):
    """Yellow fall-arrest harness: straps cut out of the body surface (clean plane edges), over the coveralls."""
    def sel(c, g):
        if _is_hand(g) or _is_head(g):
            return False
        ax = abs(c.x)
        if 0.95 < c.z < 1.5 and 0.075 < ax < 0.115:                             # shoulder straps front+back
            return True
        if 1.225 < c.z < 1.26 and c.y < 0 and ax < 0.115:                        # chest strap
            return True
        if 0.945 < c.z < 0.985 and ax < 0.3:                                     # waist belt
            return True
        if 0.78 < c.z < 0.815 and ax < 0.3:                                      # leg loops
            return True
        return False
    cuts = _zc(0.95, 1.5, 1.225, 1.26, 0.945, 0.985, 0.78, 0.815) + _xc(0.075, 0.115)
    if P["harness_v"]:
        sel, cuts = _harness_v()
    ob = _shell("bolts_outfit_harness", body, sel, lambda co, n: 0.024, [M["harness"]], None, rig, cuts, smooth=0)
    C6 = C6s()
    a = C6.AutoSkin(_bones_tuples(rig))
    fy = meas.torso_front_y(0.0, 1.245)
    a.piece(lambda bm: S.bm_box(bm, (0.0, fy - 0.03, 1.245), (0.05, 0.012, 0.045), 0), ["spine_03"])
    _join(ob, [a.finish("bolts_q_harness_buckle", [M["buckle"]], rig, subsurf=0)])
    return ob


HV_STRAP = [(0.95, 0.106), (1.24, 0.086), (1.5, 0.098)]   # s11 shoulder-strap centre x(z): a soft V to the chest strap
HV_HW = 0.02
HV_LOOP = (0.825, 0.115, -0.36, 0.0175)                     # leg loop: z at the thigh centre, thigh x, dz/dx outward, half-band


def _strap_x(z):
    for (z0, x0), (z1, x1) in zip(HV_STRAP, HV_STRAP[1:]):
        if z <= z1:
            return x0 + (x1 - x0) * max(0.0, (z - z0) / (z1 - z0))
    return HV_STRAP[-1][1]


def _harness_v():
    """s11 harness layout: shoulder straps follow the chest (V towards the chest strap, out again to the belt),
    leg loops tilted round each thigh (higher at the crotch) instead of one horizontal band like a shorts hem."""
    zl, xt, m, hl = HV_LOOP

    def sel(c, g):
        if _is_hand(g) or _is_head(g):
            return False
        ax = abs(c.x)
        if 0.95 < c.z < 1.5 and abs(ax - _strap_x(c.z)) < HV_HW:
            return True
        if 1.225 < c.z < 1.26 and c.y < 0 and ax < _strap_x(c.z) + HV_HW:
            return True
        if 0.945 < c.z < 0.985 and ax < 0.3:
            return True
        if 0.6 < c.z < 0.92 and ax < 0.3 and abs(c.z - (zl + m * (ax - xt))) < hl:
            return True
        return False
    cuts = _zc(0.95, 1.5, 1.225, 1.26, 0.945, 0.985)
    for (z0, x0), (z1, x1) in zip(HV_STRAP, HV_STRAP[1:]):
        k = (x1 - x0) / (z1 - z0)
        for off in (-HV_HW, HV_HW):
            for sx in (1.0, -1.0):
                cuts.append(((sx * (x0 + off), 0.0, z0), (sx * 1.0, 0.0, -k)))
    for off in (-hl, hl):
        for sx in (1.0, -1.0):
            cuts.append(((sx * xt, 0.0, zl + off), (-sx * m, 0.0, 1.0)))
    return sel, cuts


def C6s():
    import characters_s6 as C6
    C6.SEG_SCALE = 1.0
    return C6



# ---------------------------------------------------------------- rigid props
def _electrician_props(rig, M, m):
    C6 = C6s()
    a = C6.AutoSkin(_bones_tuples(rig))
    _hard_hat(a, C6, m, 0, 1)
    K = P["hip_props_x"]
    # multimeter on the RIGHT hip, on the belt
    fy = m.torso_front_y(K * -0.16, 0.98)
    a.piece(lambda bm: S.bm_box(bm, (K * -0.175, fy - 0.03, 0.96), (0.075, 0.035, 0.13), 2), ["pelvis"])
    a.piece(lambda bm: S.bm_box(bm, (K * -0.175, fy - 0.05, 0.985), (0.05, 0.004, 0.04), 3), ["pelvis"])
    a.piece(lambda bm: C6.sweep(bm, [(K * -0.155, fy - 0.03, 0.9), (K * -0.14, fy - 0.035, 0.82), (K * -0.13, fy - 0.03, 0.76)],
                                0.004, 0.004, 6, 4), ["pelvis", "thigh_r"])
    return [a.finish("bolts_q_elec_props", [M["hardhat"], M["buckle"], M["meter"], M["pencil_tip"],
                                            S.pbr("o_meter_lead", hexc("c0392b"), 0.5)], rig, subsurf=0)]


def _hard_hat(a, C6, m, mi_shell, mi_brim):
    """Cap-style hard hat: tall dome from just above the glasses, short side rim, front peak, crown rib."""
    cy = (m.y_front + m.y_back) * 0.5 + 0.006
    rx, ry = m.half_w + 0.026, (m.y_back - m.y_front) * 0.5 + 0.02
    bz = m.brow_z + 0.056
    rz = (m.top - bz) + 0.062
    a.piece(lambda bm: C6.cut_blob(bm, (0, cy, bz), (rx, ry, rz), lambda q: q.z > -0.002, 32, 20, mi_shell), ["Head"])
    a.piece(lambda bm: C6.vloft(bm, [(bz - 0.006, rx + 0.006, ry + 0.012, 0.0, cy - 0.012),
                                     (bz + 0.0, rx + 0.009, ry + 0.016, 0.0, cy - 0.014),
                                     (bz + 0.008, rx + 0.002, ry + 0.004, 0.0, cy - 0.004)], 32, mi_shell, 2.0, True, True),
            ["Head"])
    # front peak
    a.piece(lambda bm: C6.plate(bm, lambda u, v: Vector(((u - 0.5) * 2 * rx * 0.72 * (1 - 0.35 * v), cy - ry + 0.004 - v * 0.05,
                                                          bz - 0.004 - 0.016 * v - 0.01 * ((u - 0.5) * 2) ** 2)), 9, 4, 0.006,
                                mi_shell), ["Head"])
    rib = []
    for k in range(13):
        th = math.radians(-75 + 150 * k / 12.0)
        rib.append((0.0, cy + ry * math.sin(th) * 1.02, bz + rz * math.cos(th) + 0.004))
    a.piece(lambda bm: C6.sweep(bm, rib, 0.012, 0.007, 8, mi_shell), ["Head"])


def _workshop_props(rig, M, m):
    C6 = C6s()
    a = C6.AutoSkin(_bones_tuples(rig))
    # navy ball cap (forward), glasses stay below the brim
    top = m.top + 0.004
    cy = (m.y_front + m.y_back) * 0.5 + 0.004
    rx, ry = m.half_w + 0.012, (m.y_back - m.y_front) * 0.5 + 0.012
    cz = top - 0.085
    a.piece(lambda bm: C6.cut_blob(bm, (0, cy, cz), (rx, ry, 0.092), lambda q: q.z > 0.035 - 0.12 * max(0.0, q.y), 28, 18, 0),
            ["Head"])
    a.piece(lambda bm: C6.blob(bm, (0, cy, cz + 0.092), (0.008, 0.008, 0.004), 8, 6, 0), ["Head"])
    bz = cz + 0.033
    yf = cy - ry
    a.piece(lambda bm: C6.plate(bm, lambda u, v: Vector(((u - 0.5) * 0.18 * (1 - 0.3 * v), yf + 0.01 - v * 0.085,
                                                          bz - 0.012 * v - 0.012 * ((u - 0.5) * 2) ** 2)), 9, 4, 0.006, 0),
            ["Head"])
    K = P["hip_props_x"]
    # buckle, pouch + hammer on the RIGHT hip
    fy = m.torso_front_y(0.0, 1.01)
    a.piece(lambda bm: S.bm_box(bm, (0.0, fy - 0.022, 1.012), (0.05, 0.008, 0.04), 1), ["pelvis"])
    py = m.torso_front_y(K * -0.17, 0.95)
    a.piece(lambda bm: C6.sweep(bm, [(K * -0.175, py - 0.02, 1.0), (K * -0.178, py - 0.022, 0.86)], 0.05, 0.03, 12, 2, power=4.0),
            ["pelvis"])
    a.piece(lambda bm: C6.sweep(bm, [(K * -0.215, py + 0.03, 1.0), (K * -0.22, py + 0.03, 0.87)], 0.035, 0.022, 10, 2, power=4.0),
            ["pelvis"])
    a.piece(lambda bm: C6.sweep(bm, [(K * -0.235, py + 0.1, 1.02), (K * -0.235, py + 0.1, 0.8)], 0.012, 0.012, 8, 3), ["pelvis"])
    a.piece(lambda bm: C6.sweep(bm, [(K * -0.235, py + 0.05, 1.03), (K * -0.235, py + 0.16, 1.03)], 0.014, 0.018, 8, 4, power=3.0),
            ["pelvis"])
    return [a.finish("bolts_q_shop_props", [M["cap"], M["buckle"], M["pouch"], M["handle"], M["hammer"]], rig, subsurf=0)]


def _signatures(body, rig, M, m):
    C6 = C6s()
    sig = {}
    # round safety glasses pushed up on the forehead (between brows and any brim), temples back over the ears
    a = C6.AutoSkin(_bones_tuples(rig))
    gz = m.brow_z + 0.028
    for sx in (-1, 1):
        x = sx * 0.036
        fy = m.head_front_y(x, gz) - 0.008
        c = (x, fy, gz)
        a.piece(lambda bm, c=c: C6.ring_torus(bm, c, 0.021, 0.0028, 0, 20, 6, "Y"), ["Head"])
        a.piece(lambda bm, c=c: C6.blob(bm, c, (0.02, 0.0015, 0.02), 14, 6, 1), ["Head"])
        hx = m.head_side_x(gz - 0.01, sx)
        ty = m.head_front_y(sx * (hx - 0.012), gz - 0.004)
        a.piece(lambda bm, sx=sx, fy=fy, ty=ty, hx=hx: C6.sweep(
            bm, [(sx * 0.056, fy, gz), (sx * (hx - 0.004), ty + 0.002, gz - 0.003), (sx * (hx + 0.006), ty + 0.04, gz - 0.012),
                 (sx * (hx + 0.008), ty + 0.09, gz - 0.035), (sx * (hx + 0.004), ty + 0.11, gz - 0.055)], 0.0022, 0.0035, 6, 0),
            ["Head"])
    by = m.head_front_y(0.0, gz) - 0.012
    a.piece(lambda bm: C6.sweep(bm, [(-0.014, by + 0.002, gz + 0.002), (0.0, by, gz + 0.005), (0.014, by + 0.002, gz + 0.002)],
                                0.0024, 0.0024, 6, 0), ["Head"])
    sig["safety_glasses"] = a.finish("bolts_sig_glasses", [M["frame"], M["lens"]], rig, subsurf=0)
    # red bandana: neck shell + knot front-left + small hanging triangle (tail bones)
    bl, bh, bg0, bg1 = P["bandana"]
    neck_lo, neck_hi = m.chin_z - bl, m.chin_z - bh
    byf, _k, _c = _neck_plane(m, neck_lo)
    bk = P["bandana_tilt"]
    bd = _neck_band("bolts_sig_bandana", rig, m, neck_lo, neck_hi, bg0, bg1, [M["bandana"]], ["neck_01", "spine_03"], 4, 0.01,
                    tilt=(bk, byf))
    a = C6.AutoSkin(_bones_tuples(rig))
    zf = neck_lo + 0.012
    _hw, _hd, _cy = m.neck_ring(zf)
    fy = _cy - _hd - 0.045
    a.piece(lambda bm: C6.blob(bm, (0.034, fy - 0.004, zf), (0.02, 0.016, 0.017), 12, 8, 0), ["neck_01"])
    fy0 = fy - 0.004
    a.piece(lambda bm: C6.sweep(bm, [(0.004, fy0 + 0.004, zf + 0.004), (0.008, fy0 - 0.012, zf - 0.04),
                                     (0.012, fy0 - 0.022, zf - 0.085), (0.014, fy0 - 0.026, zf - 0.115)],
                                [0.08, 0.052, 0.022, 0.003], [0.006, 0.006, 0.005, 0.003], 12, 0, up=(0, -1, 0), power=4.0),
            ["bandana_tail_1", "bandana_tail_2"])
    a.piece(lambda bm: C6.sweep(bm, [(0.05, fy + 0.002, zf), (0.066, fy - 0.004, zf - 0.025), (0.074, fy - 0.008, zf - 0.05)],
                                [0.012, 0.01, 0.004], 0.004, 8, 0, up=(0, -1, 0), power=3.0), ["neck_01"])
    knot = a.finish("bolts_q_bandana_knot", [M["bandana"]], rig, subsurf=1)
    _join(bd, [knot])
    sig["red_bandana"] = bd
    # flat carpenter's pencil behind the RIGHT ear
    a = C6.AutoSkin(_bones_tuples(rig))
    ez = m.eye_z + 0.018
    ex = -(m.head_side_x(ez, -1) + 0.012)
    y0 = m.eye_y + 0.035
    a.piece(lambda bm: C6.sweep(bm, [(ex, y0, ez + 0.008), (ex - 0.002, y0 + 0.07, ez), (ex - 0.001, y0 + 0.125, ez - 0.008)],
                                0.0034, 0.0078, 8, 0, cap0=False, power=6.0, up=(0, 0, 1)), ["Head"])
    a.piece(lambda bm: C6.sweep(bm, [(ex, y0, ez + 0.008), (ex, y0 - 0.012, ez + 0.0095), (ex, y0 - 0.022, ez + 0.011)],
                                [0.0034, 0.0022, 0.0006], [0.0078, 0.005, 0.0012], 8, 1, cap0=False, power=6.0), ["Head"])
    sig["carpenters_pencil"] = a.finish("bolts_sig_pencil", [M["pencil"], M["pencil_tip"]], rig, subsurf=0)
    # yellow tape measure clipped at the LEFT front hip (on the belt / coverall belt)
    a = C6.AutoSkin(_bones_tuples(rig))
    tx, tz = 0.145 * P["hip_props_x"], 0.975
    ty = m.torso_front_y(tx, tz) - 0.042
    a.piece(lambda bm: C6.sweep(bm, [(tx, ty, tz), (tx, ty - 0.04, tz)], 0.036, 0.036, 16, 0, power=4.0), ["pelvis"])
    a.piece(lambda bm: C6.sweep(bm, [(tx, ty - 0.0405, tz), (tx, ty - 0.044, tz)], 0.022, 0.022, 14, 1, power=2.0), ["pelvis"])
    a.piece(lambda bm: S.bm_box(bm, (tx, ty + 0.004, tz + 0.017), (0.02, 0.006, 0.06), 2), ["pelvis"])
    a.piece(lambda bm: S.bm_box(bm, (tx, ty - 0.028, tz - 0.039), (0.022, 0.03, 0.006), 1), ["pelvis"])
    sig["tape_measure"] = a.finish("bolts_sig_tape", [M["tape"], M["tape_trim"], M["clip"]], rig, subsurf=0)
    return sig


# ================================================================ animation: retargeted UAL + gesture overlays
def _qdir(q):
    return q @ Vector((0.0, 1.0, 0.0))


def _aim(R, d):
    return (_qdir(R).rotation_difference(d.normalized()) @ R).normalized()


def _frame(y_l, n_l, y_w, n_w):
    """Rotation mapping local axes (y_l, n_l) onto world (y_w, n_w) (n orthogonalised against y)."""
    def basis(y, n):
        y = y.normalized()
        n = (n - y * n.dot(y)).normalized()
        x = y.cross(n)
        return Matrix((x, y, n)).transposed()
    return (basis(y_w, n_w) @ basis(y_l, n_l).transposed()).to_quaternion().normalized()


class Animator(object):
    def __init__(self, rig, sk, clips, meas):
        self.rig, self.sk, self.clips, self.m = rig, sk, clips, meas
        self.down = Vector((0.0, 0.0, -1.0))
        self.len = {}
        for s in "lr":
            ua, la, ha = "upperarm_" + s, "lowerarm_" + s, "hand_" + s
            self.len[s] = ((sk.head(la) - sk.head(ua)).length, (sk.head(ha) - sk.head(la)).length)
        # palm normal at rest (T-pose: palms down), checked against the finger/thumb layout
        self.palm_l = {}
        for s in "lr":
            hq = sk.restq["hand_" + s]
            self.palm_l[s] = hq.inverted() @ self.down
        self.hip_w = meas.torso_half_w(1.0)
        self.logged = set()

    # ---------------- base clips
    def base(self, ual, t):
        c = self.clips.get(ual) or self.clips.get("Idle_Loop")
        n = c["n"]
        k = t * FPS
        if c["loop"]:
            k = k % n
        else:
            k = min(max(k, 0.0), n)
        k0 = int(math.floor(k))
        k1 = min(k0 + 1, n)
        u = k - k0
        r0, r1 = c["rows"][k0], c["rows"][k1]
        rots = {b: r0[b].slerp(r1[b], u) for b in r0}
        pel = c["pel"][k0].lerp(c["pel"][k1], u)
        if ual == "Idle_Loop":
            return self._relaxed_stand(rots, pel, t)
        # lift the upper arms off the thicker waist (abduction about the forward axis)
        for s, sg in (("l", -1.0), ("r", 1.0)):
            for b in ("upperarm_" + s, "lowerarm_" + s, "hand_" + s):    # whole arm swings clear of the belly
                if b in rots:
                    rots[b] = (Quaternion((0.0, 1.0, 0.0), sg * ARM_OUT) @ rots[b]).normalized()
            if "hand_" + s in rots:                       # relaxed working hands instead of the kit's fists
                self._fingers(rots, s, rots["hand_" + s], RELAXED, thumb=(0.12, 0.1, 0.05))
        return rots, pel

    def _relaxed_stand(self, rots, pel, t):
        """UAL Idle_Loop is a wide, bent-knee 'ready' crouch with the arms out. Keep only its breathing/head life
        (spine + neck at half strength) and stand Bolts upright: legs straight at rest width (~shoulder width),
        pelvis level with a slow weight shift, arms hanging close to the body, relaxed hands."""
        sk = self.sk
        rq = sk.restq
        out = dict(rots)
        for b in list(out):
            if b.startswith(("thigh_", "calf_", "foot_", "ball_")) or b == "root":
                out[b] = rq[b].copy()
        for b, f in (("pelvis", 0.85), ("spine_01", 0.6), ("spine_02", 0.6), ("spine_03", 0.55), ("neck_01", P["neck_upright"][0]),
                     ("Head", P["neck_upright"][1]), ("clavicle_l", 0.8), ("clavicle_r", 0.8)):
            if b in out:
                q = rq[b] if out[b].dot(rq[b]) >= 0 else -rq[b]
                out[b] = out[b].slerp(q, f)
        nb, hb = P["neck_back"]                      # s11: neck more upright (head over the shoulders)
        for b, a_ in (("neck_01", nb), ("Head", hb)):
            if a_ and b in out:
                out[b] = (Quaternion((1.0, 0.0, 0.0), -a_) @ out[b]).normalized()
        sway = math.sin(2 * math.pi * t / 5.0)
        breath = math.sin(2 * math.pi * t / 3.2)
        pel = Vector((0.008 * sway, 0.0, 0.003 * breath))
        if "pelvis" in out:
            out["pelvis"] = (Quaternion((0.0, 1.0, 0.0), 0.015 * sway) @ out["pelvis"]).normalized()
        for s, sx in (("l", 1.0), ("r", -1.0)):
            ua, la = "upperarm_" + s, "lowerarm_" + s
            a = 0.004 * breath
            out[ua] = _aim(rq[ua], Vector((sx * (P["idle_arm_x"] + a), 0.05, -1.0)))
            out[la] = _aim(rq[la], Vector((sx * P["idle_fore"][0], P["idle_fore"][1], -1.0)))
            hq = self._hand_q(s, Vector((sx * 0.04, -0.04, -1.0)), Vector((-sx, 0.45, 0.0)))
            out["hand_" + s] = hq
            self._fingers(out, s, hq, RELAXED, thumb=(0.12, 0.1, 0.05))
        return out, pel

    def pose(self, clip, t):
        ual, ov = CLIP_MAP.get(clip or "idle", (None, None))
        if ual is None:
            if clip not in self.logged:
                _log("clip %r unknown -> idle" % clip)
                self.logged.add(clip)
            ual, ov = "Idle_Loop", None
        rots, pel = self.base(ual, t)
        if ov:
            rots = getattr(self, "ov_" + ov)(rots, pel, t)
        return rots, pel

    # ---------------- helpers on a posed skeleton
    def rel(self, W, bone, p):
        return W[bone] @ self.sk.rest[bone].inverted() @ Vector(p)

    def _spine_bend(self, rots, ang_x, ang_z=0.0, w=(0.25, 0.35, 0.4)):
        for b, f in zip(("spine_01", "spine_02", "spine_03"), w):
            if b in rots:
                d = Quaternion((1.0, 0.0, 0.0), ang_x * f) @ Quaternion((0.0, 0.0, 1.0), ang_z * f)
                rots[b] = (d @ rots[b]).normalized()

    def _head_turn(self, rots, ax, az, ay=0.0):
        for b, f in (("neck_01", 0.4), ("Head", 0.6)):
            if b in rots:
                d = Quaternion((0.0, 0.0, 1.0), az * f) @ Quaternion((1.0, 0.0, 0.0), ax * f) @ Quaternion((0.0, 1.0, 0.0), ay * f)
                rots[b] = (d @ rots[b]).normalized()

    def _fingers(self, rots, s, R_hand, curls, thumb=(0.0, 0.0, 0.0), spread=0.0):
        """curls: {finger: (a1, a2, a3)} radians (towards the palm); thumb: (a1, a2, a3) about its own bend axis."""
        sk = self.sk
        D = R_hand @ sk.restq["hand_" + s].inverted()
        for fn in FINGERS + ("thumb",):
            ang = thumb if fn == "thumb" else curls.get(fn, (0.0, 0.0, 0.0))
            b1 = "%s_01_%s" % (fn, s)
            if b1 not in sk.rest:
                continue
            fdir = _qdir(sk.restq[b1])
            axis = fdir.cross(self.down)
            if fn == "thumb":
                # thumb flexes across the palm: axis from the thumb dir x the hand's finger direction
                hdir = _qdir(sk.restq["middle_01_" + s])
                axis = fdir.cross(hdir) if s == "l" else hdir.cross(fdir)
                axis = -axis if s == "l" else axis
            axis.normalize()
            acc = 0.0
            for k, seg in enumerate(("01", "02", "03", "04_leaf")):
                b = "%s_%s_%s" % (fn, seg, s)
                if b not in sk.rest:
                    continue
                acc += ang[min(k, 2)] if k < 3 else 0.0
                rots[b] = (D @ Quaternion(axis, acc) @ sk.restq[b]).normalized()

    def _arm(self, rots, pel, s, wrist, pole, hand_q, twist=0.6):
        """2-bone IK to `wrist` (armature space), elbow towards `pole`, hand world rotation hand_q."""
        sk = self.sk
        ua, la, ha = "upperarm_" + s, "lowerarm_" + s, "hand_" + s
        W = sk.fk(rots, pel)
        S_ = W[ua].translation
        L1, L2 = self.len[s]
        d = Vector(wrist) - S_
        dist = max(abs(L1 - L2) + 1e-3, min(L1 + L2 - 1e-3, d.length))
        dn = d.normalized()
        a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
        h = math.sqrt(max(0.0, L1 * L1 - a * a))
        pp = Vector(pole) - dn * Vector(pole).dot(dn)
        pp = pp.normalized() if pp.length > 1e-6 else Vector((0, 0, -1))
        elbow = S_ + dn * a + pp * h
        wr = S_ + dn * dist
        rots[ua] = _aim(rots[ua], elbow - S_)
        rots[la] = _aim(rots[la], wr - elbow)
        rots[ha] = hand_q
        # forearm roll towards the hand's (twist share)
        n_h = hand_q @ self.palm_l[s]
        R_la = rots[la]
        n_f = R_la @ (sk.restq[la].inverted() @ self.down)
        ax = _qdir(R_la)
        a1 = n_f - ax * n_f.dot(ax)
        a2 = n_h - ax * n_h.dot(ax)
        if a1.length > 1e-6 and a2.length > 1e-6:
            ang = a1.normalized().angle(a2.normalized())
            if a1.cross(a2).dot(ax) < 0:
                ang = -ang
            rots[la] = (Quaternion(ax, ang * twist) @ R_la).normalized()

    def _hand_q(self, s, fingers_dir, palm_dir):
        """Hand world rotation: rest finger direction -> fingers_dir, rest palm normal (down) -> palm_dir."""
        hr = self.sk.restq["hand_" + s]
        return (_frame(_qdir(hr), self.down, Vector(fingers_dir), Vector(palm_dir)) @ hr).normalized()

    @staticmethod
    def _mix(base, over, e):
        out = dict(base)
        for b, q in over.items():
            if b in base:
                q2 = q if base[b].dot(q) >= 0 else -q
                out[b] = base[b].slerp(q2, e)
            else:
                out[b] = q
        return out

    # ---------------- overlays (eased in like the s6 analytic clips)
    def ov_point(self, rots, pel, t):
        e = _ease(t)
        o = dict(rots)
        s = "r"
        p = Vector((-0.5, -1.0, 0.42)).normalized()
        W = self.sk.fk(o, pel)
        sh = W["upperarm_" + s].translation
        L1, L2 = self.len[s]
        wrist = sh + p * (L1 + L2) * 0.985
        hq = self._hand_q(s, p, Vector((0.25, 0.0, -1.0)))
        self._arm(o, pel, s, wrist, Vector((0.0, 0.3, -1.0)), hq)
        self._fingers(o, s, hq, {"index": (0.04, 0.02, 0.02), "middle": (1.35, 1.5, 1.0), "ring": (1.4, 1.5, 1.0),
                                 "pinky": (1.45, 1.5, 1.0)}, thumb=(0.35, 0.45, 0.3))
        self._head_turn(o, -0.06, -0.25 * _ease(t - 0.4, 0.5))
        return self._mix(rots, {b: q for b, q in o.items()}, e)

    def ov_thumbs_up(self, rots, pel, t):
        e = _ease(t)
        o = dict(rots)
        s = "r"
        bob = 0.03 * math.sin(2 * math.pi * t / 0.6) * _ease(t - 0.35, 0.3)
        # hand frame: thumb straight up, palm towards the body midline (+X for the right hand)
        thumb = (-0.25, -0.1, -0.05)
        sk = self.sk
        # thumb tip direction in hand-rest space after the thumb pose
        tmp = {}
        self._fingers(tmp, s, sk.restq["hand_" + s], {}, thumb=thumb)
        tdir = _qdir(tmp["thumb_03_" + s])
        hrest = sk.restq["hand_" + s]
        D = _frame(tdir, self.down, Vector((0.12, -0.15, 1.0)), Vector((1.0, 0.0, 0.0)))
        hq = (D @ hrest).normalized()
        hy = _qdir(hq)
        W = sk.fk(o, pel)
        sh = W["upperarm_" + s].translation
        L1, L2 = self.len[s]
        elbow = sh + Vector((-0.15, -0.12, -1.0)).normalized() * L1
        fdir = (hy * 0.3 + Vector((0.1, -1.0, 0.22)).normalized()).normalized()
        wrist = elbow + fdir * L2 + Vector((0, 0, bob))
        self._arm(o, pel, s, wrist, Vector((-0.4, 0.6, -1.0)), hq)
        self._fingers(o, s, hq, {f: (1.45, 1.55, 1.1) for f in FINGERS}, thumb=thumb)
        self._head_turn(o, 0.12 * e * (0.5 + 0.5 * math.sin(2 * math.pi * t / 0.6)), 0.0)
        return self._mix(rots, o, e)

    def ov_hands_on_hips(self, rots, pel, t):
        e = _ease(t)
        o = dict(rots)
        self._spine_bend(o, -0.07, 0.0)                 # chest out
        W = self.sk.fk(o, pel)
        for s, sx in (("l", 1.0), ("r", -1.0)):
            wrist = self.rel(W, "pelvis", (sx * (self.hip_w + 0.03), 0.035, 1.05))
            hq = self._hand_q(s, Vector((sx * 0.1, -0.55, -0.85)), Vector((-sx, 0.0, 0.0)))
            self._arm(o, pel, s, wrist, Vector((sx * 1.0, 0.45, 0.0)), hq)
            self._fingers(o, s, hq, {f: (0.2, 0.25, 0.15) for f in FINGERS}, thumb=(-0.1, 0.1, 0.05))
        self._head_turn(o, 0.1 * max(0.0, math.sin(2 * math.pi * t / 1.2)), 0.0)
        return self._mix(rots, o, e)

    def ov_scratch_beard(self, rots, pel, t):
        e = _ease(t)
        o = dict(rots)
        self._head_turn(o, -0.1, 0.12, -0.08)
        W = self.sk.fk(o, pel)
        m = self.m
        chin_y = m.head_front_y(0.0, m.chin_z + 0.02) - 0.02
        chin = self.rel(W, "Head", (0.018, chin_y, m.chin_z + 0.005))
        s = "l"
        tip_dir = Vector((-0.25, 0.35, 0.9)).normalized()
        wrist = chin - tip_dir * 0.135
        hq = self._hand_q(s, tip_dir, Vector((-0.4, 1.0, -0.2)))
        self._arm(o, pel, s, wrist, Vector((1.0, 0.2, -1.0)), hq)
        sc = 0.3 * math.sin(2 * math.pi * t / 0.25) * _ease(t - 0.35, 0.2)
        self._fingers(o, s, hq, {f: (0.55 + sc, 0.6 + sc, 0.4) for f in FINGERS}, thumb=(0.2, 0.2, 0.1))
        return self._mix(rots, o, e)

    def ov_winch_crank(self, rots, pel, t):
        e = _ease(t)
        o = dict(rots)
        self._spine_bend(o, 0.2, 0.0)
        self._head_turn(o, -0.12, 0.0)
        W = self.sk.fk(o, pel)
        ph = 2 * math.pi * t / (40 / 30.0)
        c = self.rel(W, "pelvis", (0.0, -0.4, 1.06))
        h = c + Vector((0.0, -0.1 * math.cos(ph), 0.1 * math.sin(ph)))
        for s, sx in (("l", 1.0), ("r", -1.0)):
            wrist = h + Vector((sx * 0.055, 0.05, 0.01))
            hq = self._hand_q(s, Vector((-sx * 0.35, -1.0, -0.15)), Vector((0.0, -0.15, -1.0)))
            self._arm(o, pel, s, wrist, Vector((sx * 0.7, 0.4, -1.0)), hq)
            self._fingers(o, s, hq, {f: (1.2, 1.3, 0.9) for f in FINGERS}, thumb=(0.5, 0.4, 0.2))
        return self._mix(rots, o, e)

    # ---------------- baking
    def _at(self, timeline, f, fps):
        cur, start, prev = "idle", 1, None
        for s, c in timeline:
            if s <= f:
                prev = (cur, start)
                cur, start = c, s
        return cur, start, prev

    def frame_basis(self, timeline, f, fps):
        cur, start, prev = self._at(timeline, f, fps)
        rots, pel = self.pose(cur, (f - start) / float(fps))
        if prev is not None and f - start < XFADE:
            pr, pp = self.pose(prev[0], (f - prev[1]) / float(fps))
            w = smoothstep(0.0, 1.0, (f - start) / float(XFADE))
            rots = self._mix(pr, rots, w)
            pel = pp.lerp(pel, w)
        W = self.sk.fk(rots, pel)
        return self.sk.basis(W)

    def bake(self, timeline, f0, f1, fps):
        """Key EVERY bone (quaternion, sign-continuous) + pelvis location on every frame f0..f1."""
        rig = self.rig
        frames = list(range(int(f0), int(f1) + 1))
        names = self.sk.names
        qv = {n: [] for n in names}
        pv = []
        prev = {}
        for f in frames:
            bs = self.frame_basis(timeline, f, fps)
            for n in names:
                q = bs[n].to_quaternion().normalized()
                if n in prev and prev[n].dot(q) < 0:
                    q = -q
                prev[n] = q
                qv[n].append(q)
            pv.append(bs["pelvis"].translation.copy())
        for n in names:
            pb = rig.pose.bones[n]
            pb.rotation_mode = "QUATERNION"
            B.set_keys(pb, "rotation_quaternion", frames, [tuple(q) for q in qv[n]])
        B.set_keys(rig.pose.bones["pelvis"], "location", frames, [tuple(p) for p in pv])
        _log("baked %d frames x %d bones (%s)" % (len(frames), len(names), ", ".join(sorted({c for _s, c in timeline}))))
        return len(frames)

    def make_clip_actions(self, clips_frames=None, fps=30):
        """Each clip as its own Action (every 2 frames), fake user; restores the rig's action."""
        clips_frames = clips_frames or {"idle": 75, "walk": 40, "point": 40, "thumbs_up": 36, "winch_crank": 40,
                                        "hands_on_hips": 48, "scratch_beard": 54}
        rig = self.rig
        ad = rig.animation_data_create()
        keep, keep_slot = ad.action, getattr(ad, "action_slot", None)
        made = []
        for clip, n in clips_frames.items():
            ad.action = None
            for f in range(1, n + 1, 2):
                bs = self.frame_basis([(1, clip)], f, fps)
                for nm in self.sk.names:
                    pb = rig.pose.bones[nm]
                    pb.rotation_quaternion = bs[nm].to_quaternion()
                    pb.keyframe_insert("rotation_quaternion", frame=f)
                rig.pose.bones["pelvis"].location = bs["pelvis"].translation
                rig.pose.bones["pelvis"].keyframe_insert("location", frame=f)
            if ad.action is not None:
                ad.action.name = "bolts_%s" % clip
                ad.action.use_fake_user = True
                made.append(ad.action.name)
        ad.action = keep
        if keep is not None and keep_slot is not None:
            try:
                ad.action_slot = keep_slot
            except Exception:
                pass
        return made

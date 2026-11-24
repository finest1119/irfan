"""Bolts + Torque, first pass (procedural, stylised-realistic low poly, page2/character.json). Needs bpy.

Bolts: one armature (24 bones: root, pelvis, spine, chest, neck, head, arms, hands, legs, feet + prop_R, prop_L,
hat_root, tape_clip). Every piece is a mesh skinned 100 % to one bone (no auto weights). The core body (head, beard
shell, hair shell, neck, forearms, hands, eyes, brows) is one object; the 4 signatures are separate objects
(safety glasses on the forehead, red bandana, pencil behind the RIGHT ear, tape measure at the LEFT front hip), so
no outfit can drop them. Outfits are separate objects (workshop, electrician + the Build #1 harness extra) switched
with CONSTANT hide_render/hide_viewport keys; body parts under an outfit are hidden by a Mask modifier
(vertex group hide_under_<outfit>) whose show_render is keyed with the outfit.

Clips are analytic pose functions (t seconds -> bone euler rotations) baked as keys over the job's frame range:
idle, walk, point, thumbs_up, winch_crank (alias crank), hands_on_hips, scratch_beard. make_clip_actions() also
writes each clip as a named Action (for NLA reuse later).
Torque: ~1.5k tris goose with an 11-bone rig; clips waddle, idle, honk (path = root motion at walking speed).

Rest pose faces -Y. World yaw (deg CCW from +X that the FRONT faces) -> rotation_z = yaw - 270.
"""
import math

import bpy
import bmesh
from mathutils import Matrix, Vector

import mh_blender as B
from mh_blender import S, L, hexc

# ------------------------------------------------------------------ rig layout (metres, rest pose, faces -Y)
BOLTS_BONES = [
    # name, head, tail, parent
    ("root", (0, 0, 0), (0, 0.25, 0), None),
    ("pelvis", (0, 0, 0.96), (0, 0, 1.08), "root"),
    ("spine", (0, 0, 1.08), (0, 0, 1.27), "pelvis"),
    ("chest", (0, 0, 1.27), (0, 0, 1.45), "spine"),
    ("neck", (0, 0, 1.45), (0, -0.01, 1.56), "chest"),
    ("head", (0, -0.01, 1.56), (0, -0.01, 1.79), "neck"),
    ("hat_root", (0, -0.01, 1.76), (0, -0.01, 1.84), "head"),
    ("upper_arm.L", (0.215, 0.0, 1.42), (0.265, 0.01, 1.13), "chest"),
    ("forearm.L", (0.265, 0.01, 1.13), (0.285, -0.03, 0.87), "upper_arm.L"),
    ("hand.L", (0.285, -0.03, 0.87), (0.29, -0.04, 0.75), "forearm.L"),
    ("prop_L", (0.29, -0.05, 0.8), (0.29, -0.15, 0.8), "hand.L"),
    ("upper_arm.R", (-0.215, 0.0, 1.42), (-0.265, 0.01, 1.13), "chest"),
    ("forearm.R", (-0.265, 0.01, 1.13), (-0.285, -0.03, 0.87), "upper_arm.R"),
    ("hand.R", (-0.285, -0.03, 0.87), (-0.29, -0.04, 0.75), "forearm.R"),
    ("prop_R", (-0.29, -0.05, 0.8), (-0.29, -0.15, 0.8), "hand.R"),
    ("thigh.L", (0.1, 0.0, 0.95), (0.105, -0.01, 0.51), "pelvis"),
    ("shin.L", (0.105, -0.01, 0.51), (0.105, 0.01, 0.09), "thigh.L"),
    ("foot.L", (0.105, 0.01, 0.09), (0.105, -0.17, 0.03), "shin.L"),
    ("thigh.R", (-0.1, 0.0, 0.95), (-0.105, -0.01, 0.51), "pelvis"),
    ("shin.R", (-0.105, -0.01, 0.51), (-0.105, 0.01, 0.09), "thigh.R"),
    ("foot.R", (-0.105, 0.01, 0.09), (-0.105, -0.17, 0.03), "shin.R"),
    ("tape_clip", (0.15, -0.13, 0.95), (0.15, -0.13, 1.0), "pelvis"),
    ("bandana_tail_1", (0.03, -0.075, 1.44), (0.035, -0.08, 1.4), "neck"),
    ("bandana_tail_2", (0.035, -0.08, 1.4), (0.04, -0.082, 1.36), "bandana_tail_1"),
]

TORQUE_BONES = [
    ("root", (0, 0, 0), (0, 0.15, 0), None),
    ("body", (0, -0.12, 0.38), (0, 0.12, 0.42), "root"),
    ("neck1", (0, -0.14, 0.45), (0, -0.17, 0.58), "body"),
    ("neck2", (0, -0.17, 0.58), (0, -0.17, 0.7), "neck1"),
    ("head", (0, -0.17, 0.7), (0, -0.25, 0.76), "neck2"),
    ("jaw", (0, -0.24, 0.735), (0, -0.29, 0.7), "head"),
    ("wing.L", (0.11, -0.02, 0.45), (0.13, 0.2, 0.42), "body"),
    ("wing.R", (-0.11, -0.02, 0.45), (-0.13, 0.2, 0.42), "body"),
    ("leg.L", (0.06, 0.0, 0.3), (0.06, 0.0, 0.04), "body"),
    ("leg.R", (-0.06, 0.0, 0.3), (-0.06, 0.0, 0.04), "body"),
    ("tail", (0, 0.14, 0.42), (0, 0.24, 0.47), "body"),
]


def _make_armature(name, bones):
    arm = bpy.data.armatures.new(name)
    ob = L.link(bpy.data.objects.new(name, arm))
    vl = bpy.context.view_layer
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for bn, h, t, par in bones:
        b = eb.new(bn)
        b.head, b.tail = Vector(h), Vector(t)
        b.roll = 0.0
        if par:
            b.parent = eb[par]
            b.use_connect = False
        b.use_deform = bn not in ("root", "prop_L", "prop_R", "hat_root")
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "XYZ"
    return ob


class Skin(object):
    """Collects mesh pieces into one bmesh with 100 % weights to one bone per piece (+ optional hide groups)."""

    def __init__(self, bone_names, extra_groups=()):
        self.bm = bmesh.new()
        self.dl = self.bm.verts.layers.deform.verify()
        self.groups = list(bone_names) + list(extra_groups)
        self.idx = {g: i for i, g in enumerate(self.groups)}

    def add(self, verts, bone, hide=()):
        for v in verts:
            v[self.dl][self.idx[bone]] = 1.0
            for hg in hide:
                v[self.dl][self.idx[hg]] = 1.0

    def piece(self, fn, bone, hide=()):
        before = set(self.bm.verts)
        fn(self.bm)
        new = [v for v in self.bm.verts if v not in before]
        self.add(new, bone, hide)
        return new

    def finish(self, name, mats, rig, smooth=True):
        me = S.mesh_from_bm(name, self.bm, mats, smooth)
        ob = S.obj(name, me)
        for g in self.groups:
            ob.vertex_groups.new(name=g)
        ob.parent = rig
        mod = ob.modifiers.new("armature", "ARMATURE")
        mod.object = rig
        return ob


# ------------------------------------------------------------------ shape helpers (bmesh, world rest coords)
def loft(bm, rings, seg=12, mi=0, cap_top=False, cap_bot=False):
    """rings = [(z, rx, ry, (cx, cy))] -> lofted tube (ellipses)."""
    rows = []
    for z, rx, ry, c in rings:
        rows.append([bm.verts.new((c[0] + rx * math.cos(2 * math.pi * k / seg),
                                   c[1] + ry * math.sin(2 * math.pi * k / seg), z)) for k in range(seg)])
    fs = []
    for a, b in zip(rows, rows[1:]):
        for k in range(seg):
            fs.append(bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k])))
    if cap_bot:
        fs.append(bm.faces.new(list(reversed(rows[0]))))
    if cap_top:
        fs.append(bm.faces.new(rows[-1]))
    for f in fs:
        f.material_index = mi
    return [v for r in rows for v in r]


def limb(bm, p0, p1, r0, r1, mi, seg=8):
    return B.bm_cyl(bm, p0, p1, r0, r1, seg, mi)


def cut_sphere(bm, c, r, keep, seg=14, rings=10, mi=0):
    """UV sphere keeping only vertices where keep(v.co) is True (beard / hair / cap shells)."""
    vs = B.bm_uvsphere(bm, c, r, seg, rings, mi)
    dead = [v for v in vs if not keep(v.co)]
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    return [v for v in vs if v.is_valid]


# ------------------------------------------------------------------ materials
def _mats():
    m = {}
    m["skin"] = S.pbr("bolts_skin", hexc("d9a383"), 0.55, var=0.06, var_scale=12.0)
    m["beard"] = _salt_pepper("bolts_beard", hexc("6e6a66"), hexc("d8d4cf"), hexc("3a3632"))
    m["hair"] = _salt_pepper("bolts_hair", hexc("6b5d52"), hexc("9a928a"), hexc("4a4038"))
    m["brow"] = S.pbr("bolts_brow", hexc("4a4038"), 0.8)
    m["eye"] = S.pbr("bolts_eye_white", hexc("f2efe8"), 0.2)
    m["iris"] = S.pbr("bolts_iris", hexc("5b7a8c"), 0.15, coat=0.6)
    m["frame"] = S.pbr("bolts_glasses_frame", hexc("2b2b2b"), 0.3)
    m["lens"] = _lens()
    m["bandana"] = S.pbr("bolts_bandana", hexc("e63946"), 0.7, var=0.08, var_scale=40.0)
    m["pencil"] = S.pbr("bolts_pencil", hexc("f2a900"), 0.5)
    m["pencil_tip"] = S.pbr("bolts_pencil_tip", hexc("2a2a2a"), 0.6)
    m["tape"] = S.pbr("bolts_tape", hexc("f5c518"), 0.35, coat=0.3)
    m["tape_trim"] = S.pbr("bolts_tape_trim", hexc("1a1a1a"), 0.5)
    m["clip"] = S.pbr("bolts_clip", hexc("b8bcc0"), 0.3, metal=0.9)
    # workshop outfit (1K-class flat colours for the first pass)
    m["henley"] = S.pbr("o_henley", hexc("8e9196"), 0.85, var=0.05, var_scale=20.0, bump=0.1)
    m["pants"] = S.pbr("o_work_pants", hexc("0b1f3a"), 0.85, var=0.06, var_scale=15.0, bump=0.1)
    m["belt"] = S.pbr("o_tool_belt", hexc("7a4a2a"), 0.6, var=0.08)
    m["boots"] = S.pbr("o_boots", hexc("6b4226"), 0.55, var=0.08)
    m["cap"] = S.pbr("o_ball_cap", hexc("0b1f3a"), 0.8, var=0.04)
    m["hammer"] = S.pbr("o_hammer", hexc("5a5d60"), 0.35, metal=0.8)
    # electrician
    m["cover"] = S.pbr("o_coveralls", hexc("0b1f3a"), 0.85, var=0.05, var_scale=15.0, bump=0.1)
    m["strip"] = S.pbr("o_reflective", hexc("c9d1d6"), 0.25, metal=0.3)
    m["gloves"] = S.pbr("o_insulated_gloves", hexc("f2c230"), 0.6)
    m["hardhat"] = S.pbr("o_hard_hat", hexc("f4f4f2"), 0.3, coat=0.5)
    m["meter"] = S.pbr("o_multimeter", hexc("e0a100"), 0.45)
    m["harness"] = S.pbr("o_harness", hexc("f2c230"), 0.6)
    m["buckle"] = S.pbr("o_buckle", hexc("2b2b2b"), 0.4, metal=0.5)
    return m


def _salt_pepper(name, base, light, dark):
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        vec = S._coord(N, Lk, "Object")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 220.0
        nz.inputs["Detail"].default_value = 2.0
        Lk.new(vec, nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.32, dark
        els[1].position, els[1].color = 0.7, light
        e = els.new(0.5)
        e.color = base
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.8
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.35, 0.004)
        return S._finish(m, p.outputs[0])
    return B._cached(name, mk)


def _lens():
    def mk():
        m, nt, N, Lk, p = S._new_mat("bolts_glasses_lens")
        p.inputs["Base Color"].default_value = hexc("ddebf2")
        p.inputs["Roughness"].default_value = 0.03
        p.inputs["Alpha"].default_value = 0.3
        p.inputs["Coat Weight"].default_value = 1.0
        return S._finish(m, p.outputs[0], haze=False)
    return B._cached("bolts_glasses_lens", mk)


# ------------------------------------------------------------------ Bolts
OUTFITS_BUILT = ("workshop", "electrician")


def build_bolts_v1(ctx, char):
    B.part_collection("characters")
    names = [b[0] for b in BOLTS_BONES]
    rig = _make_armature("bolts_rig", BOLTS_BONES)
    M = _mats()
    hide = ["hide_under_%s" % o for o in OUTFITS_BUILT]
    # ---- core body (one object): head, face, beard, hair, neck, forearms, hands
    sk = Skin(names, hide)
    hc = Vector((0, -0.005, 1.665))
    sk.piece(lambda bm: B.bm_uvsphere(bm, hc, (0.094, 0.108, 0.124), 16, 12, 0), "head")
    sk.piece(lambda bm: S.bm_box(bm, (0, -0.035, 1.588), (0.13, 0.09, 0.07), 0), "head")          # square jaw
    sk.piece(lambda bm: B.bm_cyl(bm, (0, -0.105, 1.68), (0, -0.128, 1.655), 0.017, 0.012, 6, 0), "head")  # nose
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: B.bm_uvsphere(bm, (sx * 0.094, 0.0, 1.668), (0.012, 0.028, 0.034), 8, 6, 0), "head")
        sk.piece(lambda bm, sx=sx: B.bm_uvsphere(bm, (sx * 0.034, -0.088, 1.688), 0.016, 8, 6, 3), "head")
        sk.piece(lambda bm, sx=sx: B.bm_uvsphere(bm, (sx * 0.034, -0.1025, 1.688), 0.0075, 8, 6, 4), "head")
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.035, -0.101, 1.713), (0.045, 0.014, 0.013), 5), "head")
    # beard shell (short full salt-and-pepper, jaw + moustache) and hair shell
    sk.piece(lambda bm: cut_sphere(bm, (0, -0.012, 1.632), (0.103, 0.116, 0.108),
                                   lambda c: c.z < 1.664 and c.y < 0.03, 16, 12, 1), "head")
    sk.piece(lambda bm: S.bm_box(bm, (0, -0.118, 1.634), (0.07, 0.016, 0.014), 1), "head")             # moustache
    sk.piece(lambda bm: cut_sphere(bm, (0, 0.004, 1.672), (0.1, 0.114, 0.13),
                                   lambda c: c.z > 1.712 or (c.y > 0.02 and c.z > 1.6), 16, 12, 2), "head")
    sk.piece(lambda bm: limb(bm, (0, -0.005, 1.44), (0, -0.01, 1.585), 0.068, 0.062, 0), "neck")
    for side, sx in (("L", 1), ("R", -1)):
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.266, 0.008, 1.12), (sx * 0.284, -0.028, 0.885), 0.052, 0.04, 0),
                 "forearm." + side, hide=["hide_under_electrician"])
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.288, -0.035, 0.82), (0.05, 0.095, 0.12), 0),
                 "hand." + side, hide=["hide_under_electrician"])
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.272, -0.07, 0.84), (0.022, 0.03, 0.06), 0),
                 "hand." + side, hide=["hide_under_electrician"])                                       # thumb
    body = sk.finish("bolts_body", [M["skin"], M["beard"], M["hair"], M["eye"], M["iris"], M["brow"]], rig)
    masks = {}
    for o in OUTFITS_BUILT:
        mm = body.modifiers.new("mask_" + o, "MASK")
        mm.vertex_group = "hide_under_" + o
        mm.invert_vertex_group = True
        mm.show_render = mm.show_viewport = False
        masks[o] = mm
    # ---- signatures (separate objects; every outfit keeps them)
    sig = {}
    sk = Skin(names)
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: _ring(bm, (sx * 0.035, -0.112, 1.737), 0.023, 0.0032, 0), "head")
        sk.piece(lambda bm, sx=sx: B.bm_cyl(bm, (sx * 0.058, -0.108, 1.738), (sx * 0.099, 0.03, 1.73), 0.0025, 0.0025, 4, 0), "head")
    sk.piece(lambda bm: B.bm_cyl(bm, (-0.012, -0.113, 1.739), (0.012, -0.113, 1.739), 0.0025, 0.0025, 4, 0), "head")
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: _disc(bm, (sx * 0.035, -0.111, 1.737), 0.021, 1), "head")
    sig["safety_glasses"] = sk.finish("bolts_sig_glasses", [M["frame"], M["lens"]], rig)
    sk = Skin(names)
    sk.piece(lambda bm: loft(bm, [(1.425, 0.082, 0.078, (0, -0.006)), (1.465, 0.076, 0.072, (0, -0.006)),
                                  (1.495, 0.07, 0.066, (0, -0.008))], 14, 0), "neck")
    sk.piece(lambda bm: B.bm_uvsphere(bm, (0.035, -0.078, 1.452), (0.022, 0.016, 0.018), 8, 6, 0), "neck")   # knot front-left
    sk.piece(lambda bm: _tri(bm, (0.012, -0.082, 1.44), (0.06, -0.082, 1.44), (0.042, -0.088, 1.37), 0), "bandana_tail_1")
    sig["red_bandana"] = sk.finish("bolts_sig_bandana", [M["bandana"]], rig)
    sk = Skin(names)
    sk.piece(lambda bm: B.bm_cyl(bm, (-0.104, -0.045, 1.705), (-0.104, 0.095, 1.69), 0.0065, 0.0065, 6, 0), "head")
    sk.piece(lambda bm: B.bm_cyl(bm, (-0.104, -0.045, 1.705), (-0.104, -0.062, 1.707), 0.0065, 0.001, 6, 1), "head")
    sig["carpenters_pencil"] = sk.finish("bolts_sig_pencil", [M["pencil"], M["pencil_tip"]], rig, smooth=False)
    sk = Skin(names)
    sk.piece(lambda bm: S.bm_box(bm, (0.155, -0.15, 0.945), (0.07, 0.035, 0.07), 0), "pelvis")
    sk.piece(lambda bm: S.bm_box(bm, (0.155, -0.168, 0.945), (0.05, 0.004, 0.05), 1), "pelvis")
    sk.piece(lambda bm: S.bm_box(bm, (0.155, -0.13, 0.965), (0.025, 0.006, 0.06), 2), "pelvis")
    sig["tape_measure"] = sk.finish("bolts_sig_tape", [M["tape"], M["tape_trim"], M["clip"]], rig, smooth=False)
    # ---- outfits
    outfits = {"workshop": _outfit_workshop(names, M, rig), "electrician": _outfit_electrician(names, M, rig)}
    extras = {"fall_arrest_harness": _harness(names, M, rig)}
    for o in list(outfits.values()) + list(extras.values()):
        o.hide_render = True
    anc = L.link(bpy.data.objects.new("ANC_bolts", None))
    anc.parent = rig
    anc.parent_type = "BONE"
    anc.parent_bone = "head"
    anc.location = (0, 0.05, 0)
    S.anchor(ctx, "bolts", anc)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
               for o in [body] + list(sig.values()) + list(outfits.values()))
    return {"rig": rig, "body": body, "sig": sig, "outfits": outfits, "extras": extras, "masks": masks,
            "tris_all_outfits": tris}


def _ring(bm, c, R, r, mi, seg=16, ring=5):
    rows = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        row = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            u = R + r * math.cos(b)
            row.append(bm.verts.new((c[0] + u * math.cos(a), c[1] + r * math.sin(b), c[2] + u * math.sin(a))))
        rows.append(row)
    for i in range(seg):
        for j in range(ring):
            f = bm.faces.new((rows[i][j], rows[(i + 1) % seg][j], rows[(i + 1) % seg][(j + 1) % ring], rows[i][(j + 1) % ring]))
            f.material_index = mi
    return [v for r_ in rows for v in r_]


def _disc(bm, c, r, mi, seg=14):
    vs = [bm.verts.new((c[0] + r * math.cos(2 * math.pi * k / seg), c[1], c[2] + r * math.sin(2 * math.pi * k / seg)))
          for k in range(seg)]
    f = bm.faces.new(vs)
    f.material_index = mi
    return vs


def _tri(bm, a, b, c, mi):
    vs = [bm.verts.new(a), bm.verts.new(b), bm.verts.new(c)]
    f = bm.faces.new(vs)
    f.material_index = mi
    return vs


def _torso(bm, mi, sleeve_long=False):
    return loft(bm, [(0.93, 0.19, 0.135, (0, 0)), (1.02, 0.195, 0.15, (0, -0.01)), (1.12, 0.2, 0.165, (0, -0.03)),
                     (1.22, 0.215, 0.155, (0, -0.02)), (1.33, 0.235, 0.14, (0, -0.005)), (1.42, 0.22, 0.12, (0, 0)),
                     (1.465, 0.1, 0.085, (0, -0.005))], 14, mi, cap_top=True)


def _outfit_workshop(names, M, rig):
    sk = Skin(names)
    # henley (gray, sleeves rolled to the elbow)
    vs = sk.piece(lambda bm: _torso(bm, 0), "spine")
    for v in vs:
        if v.co.z < 1.06:
            v[sk.dl][sk.idx["spine"]] = 0.0
            v[sk.dl][sk.idx["pelvis"]] = 1.0
        elif v.co.z > 1.3:
            v[sk.dl][sk.idx["spine"]] = 0.0
            v[sk.dl][sk.idx["chest"]] = 1.0
    for side, sx in (("L", 1), ("R", -1)):
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.215, 0.0, 1.43), (sx * 0.263, 0.008, 1.13), 0.072, 0.062, 0), "upper_arm." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.262, 0.008, 1.15), (sx * 0.266, 0.006, 1.1), 0.066, 0.066, 0), "forearm." + side)
        # pants
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.1, 0.0, 0.97), (sx * 0.105, -0.01, 0.51), 0.095, 0.07, 1), "thigh." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.105, -0.01, 0.53), (sx * 0.105, 0.01, 0.13), 0.068, 0.058, 1), "shin." + side)
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.105, -0.05, 0.065), (0.115, 0.29, 0.13), 3), "foot." + side)
    sk.piece(lambda bm: loft(bm, [(0.86, 0.2, 0.14, (0, 0)), (0.97, 0.198, 0.142, (0, 0))], 14, 1), "pelvis")
    sk.piece(lambda bm: loft(bm, [(0.95, 0.205, 0.152, (0, 0)), (1.01, 0.205, 0.152, (0, 0))], 14, 2), "pelvis")  # tool belt
    sk.piece(lambda bm: S.bm_box(bm, (-0.19, -0.07, 0.92), (0.06, 0.12, 0.13), 2), "pelvis")                    # pouch R
    sk.piece(lambda bm: B.bm_cyl(bm, (-0.215, 0.02, 0.98), (-0.215, 0.02, 0.76), 0.012, 0.012, 6, 5), "pelvis")  # hammer
    sk.piece(lambda bm: S.bm_box(bm, (-0.215, 0.02, 0.99), (0.03, 0.12, 0.03), 5), "pelvis")
    # navy ball cap, forward (dome + brim); glasses stay BELOW the brim on the forehead
    sk.piece(lambda bm: cut_sphere(bm, (0, -0.002, 1.708), (0.104, 0.118, 0.1), lambda c: c.z > 1.752, 16, 12, 4), "hat_root")
    sk.piece(lambda bm: S.bm_box(bm, (0, -0.17, 1.762), (0.17, 0.11, 0.012), 4), "hat_root")
    return sk.finish("bolts_outfit_workshop", [M["henley"], M["pants"], M["belt"], M["boots"], M["cap"], M["hammer"]], rig)


def _outfit_electrician(names, M, rig):
    sk = Skin(names)
    vs = sk.piece(lambda bm: _torso(bm, 0), "spine")
    for v in vs:
        if v.co.z < 1.06:
            v[sk.dl][sk.idx["spine"]] = 0.0
            v[sk.dl][sk.idx["pelvis"]] = 1.0
        elif v.co.z > 1.3:
            v[sk.dl][sk.idx["spine"]] = 0.0
            v[sk.dl][sk.idx["chest"]] = 1.0
    sk.piece(lambda bm: loft(bm, [(0.86, 0.2, 0.14, (0, 0)), (0.97, 0.198, 0.142, (0, 0))], 14, 0), "pelvis")
    sk.piece(lambda bm: loft(bm, [(1.29, 0.238, 0.145, (0, -0.004)), (1.32, 0.238, 0.145, (0, -0.004))], 14, 1), "chest")  # strip
    sk.piece(lambda bm: loft(bm, [(0.95, 0.205, 0.152, (0, 0)), (0.995, 0.205, 0.152, (0, 0))], 14, 0), "pelvis")       # belt
    sk.piece(lambda bm: S.bm_box(bm, (-0.2, -0.08, 0.92), (0.05, 0.08, 0.13), 4), "pelvis")                             # multimeter
    for side, sx in (("L", 1), ("R", -1)):
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.215, 0.0, 1.43), (sx * 0.263, 0.008, 1.13), 0.072, 0.062, 0), "upper_arm." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.263, 0.008, 1.14), (sx * 0.283, -0.026, 0.9), 0.062, 0.05, 0), "forearm." + side)
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.29, -0.036, 0.815), (0.062, 0.105, 0.135), 2), "hand." + side)  # gloves
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.272, -0.072, 0.84), (0.028, 0.036, 0.066), 2), "hand." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.1, 0.0, 0.97), (sx * 0.105, -0.01, 0.51), 0.095, 0.07, 0), "thigh." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.105, -0.01, 0.53), (sx * 0.105, 0.01, 0.13), 0.068, 0.058, 0), "shin." + side)
        sk.piece(lambda bm, sx=sx: loft(bm, [(0.3, 0.071, 0.068, (sx * 0.105, -0.002)),
                                             (0.33, 0.071, 0.068, (sx * 0.105, -0.002))], 10, 1), "shin." + side)  # leg strip
        sk.piece(lambda bm, sx=sx: S.bm_box(bm, (sx * 0.105, -0.05, 0.065), (0.115, 0.29, 0.13), 3), "foot." + side)
    # white hard hat: dome + full brim, glasses below the brim
    sk.piece(lambda bm: cut_sphere(bm, (0, -0.004, 1.72), (0.112, 0.126, 0.11), lambda c: c.z > 1.758, 16, 12, 5), "hat_root")
    sk.piece(lambda bm: loft(bm, [(1.758, 0.14, 0.16, (0, -0.02)), (1.768, 0.14, 0.16, (0, -0.02))], 16, 5, True, True), "hat_root")
    return sk.finish("bolts_outfit_electrician", [M["cover"], M["strip"], M["gloves"], M["boots"], M["meter"], M["hardhat"]], rig)


def _harness(names, M, rig):
    sk = Skin(names)
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.09, -0.15, 1.38), (sx * 0.1, -0.165, 1.0), 0.012, 0.012, 0, 4), "chest")
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.09, 0.13, 1.38), (sx * 0.1, 0.15, 1.0), 0.012, 0.012, 0, 4), "chest")
        sk.piece(lambda bm, sx=sx: loft(bm, [(0.84, 0.1, 0.1, (sx * 0.1, 0)), (0.865, 0.1, 0.1, (sx * 0.1, 0))], 10, 0), "thigh." + ("L" if sx > 0 else "R"))
    sk.piece(lambda bm: S.bm_box(bm, (0, -0.172, 1.25), (0.2, 0.012, 0.03), 0), "chest")     # chest strap (below bandana)
    sk.piece(lambda bm: S.bm_box(bm, (0, -0.175, 1.25), (0.04, 0.012, 0.04), 1), "chest")
    return sk.finish("bolts_outfit_harness", [M["harness"], M["buckle"]], rig)


# ------------------------------------------------------------------ Torque
def build_torque_v1(ctx, tq):
    B.part_collection("characters")
    names = [b[0] for b in TORQUE_BONES]
    rig = _make_armature("torque_rig", TORQUE_BONES)
    c = tq["colors"]
    plum = S.pbr("torque_plumage", hexc(c["plumage"][1:]), 0.75, var=0.06, var_scale=30.0, bump=0.25)
    tips = S.pbr("torque_tips", hexc(c["wing_tips_shadow"][1:]), 0.75, var=0.08, var_scale=30.0, bump=0.3)
    bill = S.pbr("torque_bill", hexc(c["bill"][1:]), 0.45, coat=0.3)
    legs = S.pbr("torque_legs", hexc(c["legs_feet"][1:]), 0.6)
    eye = S.pbr("torque_eye", hexc(c["eyes"][1:]), 0.15, coat=0.7)
    sk = Skin(names)
    sk.piece(lambda bm: B.bm_uvsphere(bm, (0, 0.0, 0.42), (0.15, 0.25, 0.15), 14, 10, 0), "body")
    sk.piece(lambda bm: B.bm_uvsphere(bm, (0, 0.17, 0.44), (0.09, 0.09, 0.07), 10, 6, 0), "tail")
    sk.piece(lambda bm: limb(bm, (0, -0.15, 0.46), (0, -0.17, 0.59), 0.06, 0.045, 0, 10), "neck1")
    sk.piece(lambda bm: limb(bm, (0, -0.17, 0.58), (0, -0.17, 0.71), 0.045, 0.04, 0, 10), "neck2")
    sk.piece(lambda bm: B.bm_uvsphere(bm, (0, -0.2, 0.735), (0.05, 0.07, 0.05), 12, 8, 0), "head")
    sk.piece(lambda bm: B.bm_cyl(bm, (0, -0.25, 0.74), (0, -0.315, 0.732), 0.022, 0.012, 8, 2), "head")      # upper bill
    sk.piece(lambda bm: B.bm_cyl(bm, (0, -0.25, 0.727), (0, -0.305, 0.724), 0.016, 0.008, 8, 2), "jaw")      # lower bill
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: B.bm_uvsphere(bm, (sx * 0.04, -0.225, 0.75), 0.008, 6, 4, 4), "head")
        side = "L" if sx > 0 else "R"
        sk.piece(lambda bm, sx=sx: B.bm_uvsphere(bm, (sx * 0.13, 0.05, 0.45), (0.04, 0.2, 0.09), 10, 6, 1), "wing." + side)
        sk.piece(lambda bm, sx=sx: limb(bm, (sx * 0.06, 0.0, 0.3), (sx * 0.06, 0.0, 0.03), 0.014, 0.012, 3, 6), "leg." + side)
        sk.piece(lambda bm, sx=sx: _tri(bm, (sx * 0.06 - 0.05, -0.07, 0.01), (sx * 0.06 + 0.05, -0.07, 0.01),
                                        (sx * 0.06, 0.02, 0.012), 3), "leg." + side)
    body = sk.finish("torque_body", [plum, tips, bill, legs, eye], rig)
    anc = L.link(bpy.data.objects.new("ANC_torque", None))
    anc.parent = rig
    anc.parent_type = "BONE"
    anc.parent_bone = "head"
    anc.location = (0, 0.02, 0.05)
    S.anchor(ctx, "torque", anc)
    return {"rig": rig, "body": body, "tris": sum(len(p.vertices) - 2 for p in body.data.polygons)}


# ------------------------------------------------------------------ clips (analytic poses)
def _s(t, period, phase=0.0):
    return math.sin(2 * math.pi * (t / period + phase))


def _ease(t, d=0.35):
    t = max(0.0, min(1.0, t / d))
    return t * t * (3 - 2 * t)


def bolts_pose(clip, t):
    """-> {bone: (rx, ry, rz)} (radians, bone-local; arms/legs: -X = swing forward). t seconds into the clip."""
    p = {}
    br = 0.025 * _s(t, 3.0)
    p["chest"] = (br, 0, 0)
    p["head"] = (0.0, 0.0, 0.12 * _s(t, 6.0))
    p["upper_arm.L"] = (0.03 * _s(t, 3.0), 0, -0.08)
    p["upper_arm.R"] = (0.03 * _s(t, 3.0, 0.5), 0, 0.08)
    p["forearm.L"] = p["forearm.R"] = (-0.12, 0, 0)
    if clip in ("idle", None):
        return p
    if clip == "walk":
        T = 32 / 30.0
        sw = _s(t, T)
        p["thigh.L"] = (-0.42 * sw, 0, 0)
        p["thigh.R"] = (0.42 * sw, 0, 0)
        p["shin.L"] = (0.55 * max(0.0, -_s(t, T, 0.15)), 0, 0)
        p["shin.R"] = (0.55 * max(0.0, _s(t, T, 0.15)), 0, 0)
        p["upper_arm.L"] = (0.32 * sw, 0, -0.08)
        p["upper_arm.R"] = (-0.32 * sw, 0, 0.08)
        p["pelvis"] = (0, 0.05 * sw, 0)
        p["chest"] = (0.04, -0.06 * sw, 0)
        return p
    e = _ease(t)
    if clip == "point":
        p["upper_arm.R"] = (-1.232 * e, 0.335 * e, 0.469 * e)          # s6: solved from hand targets
        p["forearm.R"] = (-0.12 * (1 - e) - 0.15 * e, 0, 0.046 * e)
        p["head"] = (0, 0, 0.35 * _ease(t - 0.7, 0.4) - 0.15 * e)
        return p
    if clip == "thumbs_up":
        p["upper_arm.R"] = (-0.759 * e, 0.09 * e, 0.226 * e)
        p["forearm.R"] = (-1.47 * e, 0.202 * e, 0.223 * e)
        p["head"] = (0.12 * e * (0.5 + 0.5 * _s(t, 0.6)), 0, 0)
        return p
    if clip in ("winch_crank", "crank"):
        ph = _s(t, 40 / 30.0)
        ph2 = _s(t, 40 / 30.0, 0.25)
        p["spine"] = (0.18, 0, 0)
        for side, sg in (("L", 1), ("R", -1)):
            p["upper_arm." + side] = (-0.8 + 0.28 * ph, 0, -sg * 0.12)
            p["forearm." + side] = (-0.7 + 0.35 * ph2, 0, 0)
        return p
    if clip == "hands_on_hips":
        for side, sg in (("L", 1), ("R", -1)):          # s6: elbows out/back, wrists on the hips
            p["upper_arm." + side] = (0.295 * e, sg * 0.061 * e, -sg * 0.403 * e)
            p["forearm." + side] = (-0.534 * e, sg * 0.38 * e, sg * 1.225 * e)
        p["chest"] = (-0.06 * e + br, 0, 0)
        p["head"] = (0.1 * e * max(0.0, _s(t, 1.2)), 0, 0)
        return p
    if clip == "scratch_beard":
        p["upper_arm.L"] = (-0.903 * e, -0.056 * e, -0.114 * e)
        p["forearm.L"] = (-1.691 * e, 0.737 * e, 0.66 * e)
        p["hand.L"] = (0.15 * _s(t, 0.25) * e, 0, 0)
        p["head"] = (0.08 * e, 0.12 * e, -0.2 * e)
        return p
    return p


def torque_pose_v1(clip, t):
    p = {"neck1": (0.0, 0, 0), "head": (0.0, 0, 0.25 * _s(t, 4.0))}
    if clip in ("idle", None):
        p["body"] = (0.02 * _s(t, 2.5), 0, 0)
        p["neck2"] = (0.08 * _s(t, 5.0), 0, 0)
        return p
    if clip == "waddle":
        T = 24 / 30.0
        p["body"] = (0, 0.12 * _s(t, T), 0)
        p["leg.L"] = (-0.35 * _s(t, T), 0, 0)
        p["leg.R"] = (0.35 * _s(t, T), 0, 0)
        p["neck1"] = (0.12 * _s(t, T / 2), 0, 0)
        p["head"] = (-0.1 * _s(t, T / 2), 0, 0)
        return p
    if clip == "honk":
        e = _ease(t, 0.25)
        p["neck1"] = (0.55 * e, 0, 0)
        p["neck2"] = (0.35 * e, 0, 0)
        op = max(0.0, _s(t, 0.5)) if t < 1.0 else 0.0
        p["jaw"] = (0.4 * op, 0, 0)
        return p
    return p


LOOPING = {"idle": 90, "walk": 32, "winch_crank": 40, "crank": 40, "waddle": 24}


def bake_clips(rig, pose_fn, timeline, f0, f1, fps, step=1):
    """timeline = [(start_frame, clip)] sorted. Bakes every pose bone that any clip touches over [f0, f1]."""
    frames = list(range(f0, f1 + 1, step))
    if frames[-1] != f1:
        frames.append(f1)
    data = {}
    for f in frames:
        cur, start = "idle", 1
        for s, c in timeline:
            if s <= f:
                cur, start = c, s
        t = (f - start) / float(fps)
        pose = pose_fn(cur, t)
        for bn, rot in pose.items():
            data.setdefault(bn, {})[f] = rot
    for bn, fv in data.items():
        if bn not in rig.pose.bones:
            continue
        fr = sorted(fv)
        full = [fv.get(f, (0.0, 0.0, 0.0)) for f in fr]
        B.set_keys(rig.pose.bones[bn], "rotation_euler", fr, full)


def make_clip_actions(rig, pose_fn, clips, fps=30):
    """Each clip as a named Action on the rig (keyed every 2 frames), for NLA reuse; restores the active action."""
    ad = rig.animation_data_create()
    keep = ad.action
    made = []
    for clip, n in clips.items():
        ad.action = None
        for f in range(1, n + 1, 2):
            for bn, rot in pose_fn(clip, (f - 1) / float(fps)).items():
                if bn in rig.pose.bones:
                    pb = rig.pose.bones[bn]
                    pb.rotation_euler = rot
                    pb.keyframe_insert("rotation_euler", frame=f)
        if ad.action is not None:
            ad.action.name = "%s_%s" % (rig.name, clip)
            ad.action.use_fake_user = True
            made.append(ad.action.name)
    ad.action = keep
    return made


# ------------------------------------------------------------------ placement + outfit timeline from plan events
def yaw_rot(yaw):
    return (0.0, 0.0, math.radians(yaw - 270.0))


def apply_cast(ctx, world, chars, plan, f0, f1, episode):
    """Key positions (CONSTANT, at the event frames = mid-move), clips, outfits, Torque paths and the pickup."""
    fps = plan["fps"]
    ev = [e for e in plan["events"] if e["kind"] == "cast"]
    lo = max(1, f0 - 2)
    default_outfit = episode.get("outfit", "workshop")
    extras = set(episode.get("outfit_extras", []))
    for who in ("bolts", "torque", "pickup"):
        timeline, pos_keys, rot_keys, paths = [], [], [], []
        for e in ev:
            spec = e["value"].get(who)
            if not spec:
                continue
            f = e["f"]
            at = spec.get("at")
            if at is not None:
                pos_keys.append((f, tuple(at)))
            if "yaw" in spec:   # characters rest facing -Y; the pickup model faces +X
                rot_keys.append((f, (0.0, 0.0, math.radians(spec["yaw"])) if who == "pickup" else yaw_rot(spec["yaw"])))
            if "clip" in spec:
                timeline.append((f, spec["clip"]))
            if "path" in spec:
                paths.append((f, spec["path"], at[2] if at else 0.0))
        obj = None
        if who == "bolts" and "bolts" in chars:
            obj = chars["bolts"]["rig"]
        elif who == "torque" and "torque" in chars:
            obj = chars["torque"]["rig"]
        elif who == "pickup":
            obj = world.cast.get("pickup") if world is not None else None
        if obj is None:
            continue
        if pos_keys:
            B.key_const(obj, "location", pos_keys)
        if rot_keys:
            B.key_const(obj, "rotation_euler", rot_keys)
        for (pf, path, z0) in paths:          # root motion along the path (waddle speed 0.45 m/s), keyed per frame
            segs = list(zip(path, path[1:]))
            total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs)
            fr, locs, rots = [], [], []
            for f in range(max(pf, lo), f1 + 3):
                dist = min(total, (f - pf) * 0.45 / fps)
                acc = 0.0
                for a, b in segs:
                    sl = math.hypot(b[0] - a[0], b[1] - a[1])
                    if acc + sl >= dist or (a, b) == segs[-1]:
                        u = 0.0 if sl == 0 else min(1.0, (dist - acc) / sl)
                        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
                        yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                        break
                    acc += sl
                fr.append(f)
                locs.append((x, y, z0))
                rots.append(yaw_rot(yaw))
            nxt = [e["f"] for e in ev if e["f"] > pf and who in e["value"]]
            if nxt:
                fr_cut = [i for i, f in enumerate(fr) if f < nxt[0]]
                fr, locs, rots = [fr[i] for i in fr_cut], [locs[i] for i in fr_cut], [rots[i] for i in fr_cut]
            if fr:
                for f, lv, rv in zip(fr, locs, rots):
                    obj.location = lv
                    obj.keyframe_insert("location", frame=f)
                    obj.rotation_euler = rv
                    obj.keyframe_insert("rotation_euler", frame=f)
        if who == "bolts":
            bake_clips(obj, bolts_pose, sorted(timeline), lo, f1 + 2, fps)
        elif who == "torque":
            bake_clips(obj, torque_pose, sorted(timeline), lo, f1 + 2, fps)
    # outfits: default from the episode, changes only inside cast events (mid-move = inside a whip)
    if "bolts" in chars:
        ch = chars["bolts"]
        okeys = [(1, default_outfit)] + [(e["f"], e["value"]["bolts"]["outfit"]) for e in ev
                                          if e["value"].get("bolts", {}).get("outfit")]
        for name, ob in ch["outfits"].items():
            B.vis_keys(ob, [(f, o == name) for f, o in okeys])
        for name, mm in ch["masks"].items():
            B.key_const(mm, "show_render", [(f, o == name) for f, o in okeys])
            B.key_const(mm, "show_viewport", [(f, o == name) for f, o in okeys])
        for name, ob in ch["extras"].items():
            B.vis_keys(ob, [(1, name in extras)])
        missing = [o for _f, o in okeys if o not in ch["outfits"]]
        if missing:
            print("[chars] WARNING outfits not built yet: %s (showing workshop)" % sorted(set(missing)))
            B.vis_keys(ch["outfits"]["workshop"], [(f, o == "workshop" or o not in ch["outfits"]) for f, o in okeys])


# ------------------------------------------------------------------ session 6: smooth skinned Bolts + modelled goose
# characters_s6.py builds both (same bone names, clip names, anchors and return keys). The v1 builders stay as a
# fallback (USE_S6 = False, or automatically if the s6 build raises).
USE_S6 = True


def _s6():
    import characters_s6 as C6
    return C6


def build_bolts(ctx, char):
    if USE_S6:
        try:
            return _s6().build_bolts(ctx, char)
        except Exception:
            import traceback
            traceback.print_exc()
            print("[chars] s6 Bolts FAILED -> v1 fallback")
    return build_bolts_v1(ctx, char)


def build_torque(ctx, tq):
    global _TORQUE_S6
    if USE_S6:
        try:
            out = _s6().build_torque(ctx, tq)
            _TORQUE_S6 = True
            return out
        except Exception:
            import traceback
            traceback.print_exc()
            print("[chars] s6 Torque FAILED -> v1 fallback")
    _TORQUE_S6 = False
    return build_torque_v1(ctx, tq)


_TORQUE_S6 = USE_S6


def torque_pose(clip, t):
    return _s6().torque_pose(clip, t) if _TORQUE_S6 else torque_pose_v1(clip, t)

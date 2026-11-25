"""Session 6 characters: smooth, continuously skinned Bolts + a modelled white farm goose (Torque). Needs bpy.

Why procedural: the Quaternius base characters could not be downloaded anonymously (Google Drive "quota exceeded";
the Universal Base Characters / Animation Library downloads go through an itch.io pay-what-you-want step), so
Bolts is rebuilt here from lofted, subdivided meshes instead of the v1 rigid mannequin pieces.

Contract with characters.py (unchanged): same rig bone names (BOLTS_BONES), same clip names (bolts_pose /
torque_pose), ANC_bolts / ANC_torque anchors, the returned dict keys (rig, body, sig, outfits, extras, masks,
tris_all_outfits / rig, body, tris). Rest pose faces -Y, Bolts 1.778 m.

Look: every mesh is a quad loft (elliptic / superelliptic rings along a 3D path) with a Subdivision Surface
modifier (render level 1) after the Armature modifier. Weights are smooth: inverse-distance^6 to the bone
segments a piece is allowed to follow, so shoulders, elbows, hips and the goose neck bend without seams.
"""
import math

import bpy
import bmesh
from mathutils import Vector

import mh_blender as B
from mh_blender import S, L, hexc


# ================================================================ geometry helpers
def _frame(t, up_hint):
    t = t.normalized()
    up = Vector(up_hint)
    if abs(t.dot(up.normalized())) > 0.95:
        up = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
    side = t.cross(up).normalized()
    up2 = side.cross(t).normalized()
    return side, up2


SEG_SCALE = 1.0      # build_torque lowers this (PROPOSAL 7.3: Torque <= 5k tris)


def sweep(bm, path, rx, ry, seg=16, mi=0, cap0=True, cap1=True, up=(0, 0, 1), power=2.0, shift=None, twist=None):
    """Loft rings along `path` (list of 3D points). rx/ry: per-point radii along side/up axes (lists or floats).
    power > 2 = boxier superellipse rings. shift: per-point (ds, du) ring-centre offsets. Caps end in a pole
    vertex (good for subsurf). Returns all verts."""
    seg = max(6, int(round(seg * SEG_SCALE / 2.0)) * 2)
    n = len(path)
    P = [Vector(p) for p in path]
    rx = rx if isinstance(rx, (list, tuple)) else [rx] * n
    ry = ry if isinstance(ry, (list, tuple)) else [ry] * n
    rows = []
    for i in range(n):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        side, u = _frame(t, up)
        if twist is not None:
            a = twist[i]
            side, u = side * math.cos(a) + u * math.sin(a), u * math.cos(a) - side * math.sin(a)
        c = P[i]
        if shift is not None:
            c = c + side * shift[i][0] + u * shift[i][1]
        row = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ca, sa = math.cos(a), math.sin(a)
            e = 2.0 / power
            cx = math.copysign(abs(ca) ** e, ca)
            sy = math.copysign(abs(sa) ** e, sa)
            row.append(bm.verts.new(c + side * (rx[i] * cx) + u * (ry[i] * sy)))
        rows.append(row)
    faces = []
    for a_, b_ in zip(rows, rows[1:]):
        for k in range(seg):
            faces.append(bm.faces.new((a_[k], a_[(k + 1) % seg], b_[(k + 1) % seg], b_[k])))
    extra = []
    if cap0:
        d = (P[0] - P[1]).normalized() * min(rx[0], ry[0]) * 0.35
        pole = bm.verts.new(P[0] + d)
        extra.append(pole)
        for k in range(seg):
            faces.append(bm.faces.new((rows[0][(k + 1) % seg], rows[0][k], pole)))
    if cap1:
        d = (P[-1] - P[-2]).normalized() * min(rx[-1], ry[-1]) * 0.35
        pole = bm.verts.new(P[-1] + d)
        extra.append(pole)
        for k in range(seg):
            faces.append(bm.faces.new((rows[-1][k], rows[-1][(k + 1) % seg], pole)))
    for f in faces:
        f.material_index = mi
    return [v for r in rows for v in r] + extra


def blob(bm, c, r, seg=16, rings=10, mi=0, fn=None):
    """UV sphere with radii r (xyz) and an optional per-vertex deform fn(Vector local) -> Vector local."""
    seg = max(6, int(round(seg * SEG_SCALE)))
    rings = max(4, int(round(rings * SEG_SCALE)))
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    vs = res["verts"]
    r = r if isinstance(r, (tuple, list)) else (r, r, r)
    for v in vs:
        p = Vector((v.co.x * r[0], v.co.y * r[1], v.co.z * r[2]))
        if fn is not None:
            p = fn(p)
        v.co = Vector(c) + p
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def ring_torus(bm, c, R, r, mi=0, seg=20, ring=6, axis="Y"):
    out = []
    rows = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        row = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            u = R + r * math.cos(b)
            p = Vector((u * math.cos(a), r * math.sin(b), u * math.sin(a)))
            if axis == "Z":
                p = Vector((p.x, p.z, p.y))
            row.append(bm.verts.new(Vector(c) + p))
        rows.append(row)
    for i in range(seg):
        for j in range(ring):
            f = bm.faces.new((rows[i][j], rows[(i + 1) % seg][j], rows[(i + 1) % seg][(j + 1) % ring], rows[i][(j + 1) % ring]))
            f.material_index = mi
    for r_ in rows:
        out += r_
    return out


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ================================================================ smooth skinning
def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


class AutoSkin(object):
    """bmesh collector; each piece is weighted to a list of allowed bones by inverse distance^power."""

    def __init__(self, bones, extra_groups=()):
        self.bm = bmesh.new()
        self.dl = self.bm.verts.layers.deform.verify()
        self.seg = {n: (Vector(h), Vector(t)) for n, h, t, _p in bones}
        self.groups = [b[0] for b in bones] + list(extra_groups)
        self.idx = {g: i for i, g in enumerate(self.groups)}

    def weight(self, verts, bones, power=6.0, hide=(), bias=None):
        for v in verts:
            if len(bones) == 1:
                ws = {bones[0]: 1.0}
            else:
                ws = {}
                for bn in bones:
                    a, b = self.seg[bn]
                    d = _seg_dist(v.co, a, b) + 1e-4
                    if bias:
                        d *= bias.get(bn, 1.0)
                    ws[bn] = 1.0 / d ** power
                s = sum(ws.values())
                ws = {k: w / s for k, w in ws.items() if w / s > 0.01}
                s = sum(ws.values())
                ws = {k: w / s for k, w in ws.items()}
            for bn, w in ws.items():
                v[self.dl][self.idx[bn]] = w
            for hg in hide:
                v[self.dl][self.idx[hg]] = 1.0

    def piece(self, fn, bones, power=6.0, hide=(), bias=None):
        before = set(self.bm.verts)
        fn(self.bm)
        new = [v for v in self.bm.verts if v not in before]
        self.weight(new, bones, power, hide, bias)
        return new

    def finish(self, name, mats, rig, subsurf=1, smooth=True):
        me = S.mesh_from_bm(name, self.bm, mats, smooth)
        ob = S.obj(name, me)
        for g in self.groups:
            ob.vertex_groups.new(name=g)
        ob.parent = rig
        mod = ob.modifiers.new("armature", "ARMATURE")
        mod.object = rig
        if subsurf:
            ss = ob.modifiers.new("subsurf", "SUBSURF")
            ss.levels = 1
            ss.render_levels = subsurf
            try:
                ss.boundary_smooth = "PRESERVE_CORNERS"
            except Exception:
                pass
        return ob


def make_armature(name, bones):
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


def tris_of(objs):
    """Render triangle count incl. the subsurf level (quads x 4^level x 2)."""
    n = 0
    for o in objs:
        lv = 0
        for m in o.modifiers:
            if m.type == "SUBSURF":
                lv = m.render_levels
        q = sum(len(p.vertices) - 2 for p in o.data.polygons)
        n += q * (4 ** lv) if lv else q
    return n


def vloft(bm, rings, seg=20, mi=0, power=2.0, cap_bot=False, cap_top=False):
    """Vertical loft: rings = [(z, half_width_x, half_depth_y, cx, cy)] (superellipse power)."""
    rows = []
    e = 2.0 / power
    for z, rx, ry, cx, cy in rings:
        row = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ca, sa = math.cos(a), math.sin(a)
            row.append(bm.verts.new((cx + rx * math.copysign(abs(ca) ** e, ca), cy + ry * math.copysign(abs(sa) ** e, sa), z)))
        rows.append(row)
    fs = []
    for a_, b_ in zip(rows, rows[1:]):
        for k in range(seg):
            fs.append(bm.faces.new((a_[k], a_[(k + 1) % seg], b_[(k + 1) % seg], b_[k])))
    extra = []
    for cap, row, sgn in ((cap_bot, rows[0], -1), (cap_top, rows[-1], 1)):
        if cap:
            z, rx, ry, cx, cy = rings[0] if sgn < 0 else rings[-1]
            pole = bm.verts.new((cx, cy, z + sgn * min(rx, ry) * 0.3))
            extra.append(pole)
            for k in range(seg):
                tri = (row[(k + 1) % seg], row[k], pole) if sgn < 0 else (row[k], row[(k + 1) % seg], pole)
                fs.append(bm.faces.new(tri))
    for f in fs:
        f.material_index = mi
    return [v for r in rows for v in r] + extra


def cut_blob(bm, c, r, keep, seg=24, rings=14, mi=0, fn=None):
    vs = blob(bm, c, r, seg, rings, mi, fn)
    dead = [v for v in vs if not keep(v.co - Vector(c))]
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    return [v for v in vs if v.is_valid]


def plate(bm, pts_fn, nu, nv, thick, mi=0):
    """A thin solid plate from a (u, v) -> point function (u, v in 0..1), thickness along +Z."""
    grid = [[bm.verts.new(pts_fn(i / (nu - 1.0), j / (nv - 1.0))) for j in range(nv)] for i in range(nu)]
    top = [[bm.verts.new(v.co + Vector((0, 0, thick))) for v in row] for row in grid]
    fs = []
    for g, flip in ((grid, True), (top, False)):
        for i in range(nu - 1):
            for j in range(nv - 1):
                q = (g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1])
                fs.append(bm.faces.new(tuple(reversed(q)) if flip else q))
    rim = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)] + \
          [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)]
    for k in range(len(rim)):
        a, b = rim[k], rim[(k + 1) % len(rim)]
        fs.append(bm.faces.new((grid[a[0]][a[1]], grid[b[0]][b[1]], top[b[0]][b[1]], top[a[0]][a[1]])))
    for f in fs:
        f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    return [v for row in grid for v in row] + [v for row in top for v in row]


# ================================================================ Bolts
HEAD_C = Vector((0.0, -0.004, 1.664))
HEAD_R = (0.086, 0.103, 0.121)


def head_deform(p):
    """Local head-space shaping: square jaw, flat back, chin, brow ridge, eye sockets, cheekbones."""
    x, y, z = p.x, p.y, p.z
    ax = abs(x)
    front = smoothstep(0.02, -0.07, y)
    low = smoothstep(-0.01, -0.085, z)
    x *= 1.0 + 0.16 * low * (1.0 - 0.5 * smoothstep(-0.09, -0.12, z))     # square jaw
    if y > 0:
        y *= 0.93 - 0.05 * smoothstep(0.0, -0.1, z)                         # flatter back / nape
    chin = smoothstep(-0.07, -0.112, z) * front * smoothstep(0.05, 0.0, ax)
    y -= 0.012 * chin
    z -= 0.006 * chin
    brow = math.exp(-((z - 0.04) / 0.014) ** 2) * front * smoothstep(0.08, 0.03, ax)
    y -= 0.007 * brow
    for sx in (-1, 1):
        d2 = ((x - sx * 0.034) ** 2 + (z - 0.018) ** 2) / 0.016 ** 2
        y += 0.009 * math.exp(-d2) * front
    cheek = math.exp(-(((ax - 0.052) / 0.022) ** 2 + ((z + 0.012) / 0.022) ** 2)) * front
    y -= 0.006 * cheek
    x += math.copysign(0.004 * cheek, x)
    temple = math.exp(-(((z - 0.045) / 0.03) ** 2)) * smoothstep(0.05, 0.085, ax) * smoothstep(0.03, -0.04, y)
    x -= math.copysign(0.005 * temple, x)
    return Vector((x, y, z))


def _head_point(u, v, off=0.0):
    """Point on the shaped head for sphere angles (u around Z, v from top) + outward offset (for shells)."""
    d = Vector((math.sin(v) * math.cos(u) * HEAD_R[0], math.sin(v) * math.sin(u) * HEAD_R[1], math.cos(v) * HEAD_R[2]))
    p = head_deform(d)
    if off:
        n = Vector((p.x / HEAD_R[0] ** 2, p.y / HEAD_R[1] ** 2, p.z / HEAD_R[2] ** 2)).normalized()
        p = p + n * off
    return HEAD_C + p


def head_mesh(bm, mi, keep=None, off=0.0, seg=26, rings=17):
    """The head as a lat-long grid (same topology for skin and the beard / hair shells)."""
    grid = []
    for j in range(1, rings):
        v = math.pi * j / rings
        row = []
        for i in range(seg):
            u = 2 * math.pi * i / seg
            row.append(_head_point(u, v, off))
        grid.append(row)
    top = HEAD_C + head_deform(Vector((0, 0, HEAD_R[2]))) + Vector((0, 0, off))
    bot = HEAD_C + head_deform(Vector((0, 0, -HEAD_R[2]))) - Vector((0, 0, off))
    allp = [p for row in grid for p in row] + [top, bot]

    def ok(p):
        return keep is None or keep(p - HEAD_C)
    vmap = {}

    def V(key, p):
        if key not in vmap:
            vmap[key] = bm.verts.new(p)
        return vmap[key]
    fs = []
    R = len(grid)
    for j in range(R - 1):
        for i in range(seg):
            i2 = (i + 1) % seg
            ps = [grid[j][i], grid[j][i2], grid[j + 1][i2], grid[j + 1][i]]
            if all(ok(p) for p in ps):
                fs.append(bm.faces.new((V((j, i), ps[0]), V((j + 1, i), ps[3]), V((j + 1, i2), ps[2]), V((j, i2), ps[1]))))
    for i in range(seg):
        i2 = (i + 1) % seg
        if ok(top) and ok(grid[0][i]) and ok(grid[0][i2]):
            fs.append(bm.faces.new((V("top", top), V((0, i), grid[0][i]), V((0, i2), grid[0][i2]))))
        if ok(bot) and ok(grid[-1][i]) and ok(grid[-1][i2]):
            fs.append(bm.faces.new((V("bot", bot), V((R - 1, i2), grid[-1][i2]), V((R - 1, i), grid[-1][i]))))
    for f in fs:
        f.material_index = mi
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - HEAD_C) < 0:
            f.normal_flip()
    return list(vmap.values()), allp


def head_front_y(x, z):
    """Head surface y (front, -Y side) at (x, z): searched on the shaped grid."""
    best, by = 1e9, None
    for j in range(1, 60):
        v = math.pi * j / 60
        for i in range(0, 64):
            u = math.pi + math.pi * i / 64.0       # front half: y < 0 -> u in (pi, 2pi)
            p = _head_point(u, v)
            d = (p.x - x) ** 2 + (p.z - z) ** 2
            if d < best:
                best, by = d, p.y
    return by


def beard_keep(p):
    x, y, z = p
    ax = abs(x)
    if y > 0.035:
        return False
    if z > -0.012 and not (ax > 0.062 and z < 0.012 and y < -0.005):      # sideburns up to the ears
        return False
    if ax < 0.021 and -0.06 < z < -0.042 and y < 0:                     # mouth opening (lips show)
        return False
    if z > -0.032 and ax < 0.05 and y < -0.05 and not (-0.042 < z < -0.026):  # upper lip: moustache band only
        return False
    return True


def hair_keep(p):
    x, y, z = p
    ax = abs(x)
    if z < -0.035:
        return False
    if y < -0.045 and z < 0.075:                                          # face + forehead stay bare
        return False
    if ax > 0.07 and -0.03 < z < 0.03 and -0.03 < y < 0.03:              # around the ears
        return False
    return True


# ---------------------------------------------------------------- Bolts body parts (rest pose, faces -Y)
ARM = {  # side sign -> shoulder, elbow, wrist (match BOLTS_BONES)
    1: ((0.205, 0.0, 1.425), (0.265, 0.01, 1.13), (0.285, -0.03, 0.875)),
    -1: ((-0.205, 0.0, 1.425), (-0.265, 0.01, 1.13), (-0.285, -0.03, 0.875)),
}


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def hand(bm, sx, mi, scale=1.0):
    """Big working hand hanging at the side, palm facing the thigh. Returns verts."""
    wx, wy, wz = ARM[sx][2]
    c = Vector((wx, wy - 0.004, wz - 0.05))

    def P(dx, dy, dz):                 # scale about the hand centre (gloves = scale 1.12)
        return tuple(c + (Vector((wx + dx, wy + dy, wz + dz)) - c) * scale)
    vs = []
    vs += sweep(bm, [P(0, -0.002, 0.01), P(sx * 0.002, -0.005, -0.035), P(sx * 0.004, -0.009, -0.078)],
                [0.04 * scale, 0.046 * scale, 0.044 * scale], [0.02 * scale, 0.021 * scale, 0.017 * scale], 14, mi)
    inward = -sx
    for k, (dy, ln, r) in enumerate(((-0.036, 0.074, 0.0098), (-0.012, 0.081, 0.0102), (0.012, 0.076, 0.0098), (0.033, 0.06, 0.0088))):
        y0 = -0.009 + dy * 0.95
        path = [P(sx * 0.004, y0, -0.074), P(sx * 0.003 + inward * 0.004, y0, -0.074 - ln * 0.45),
                P(inward * 0.012, y0 - 0.004, -0.074 - ln * 0.85), P(inward * 0.02, y0 - 0.008, -0.074 - ln)]
        vs += sweep(bm, path, [r * scale, r * 0.95 * scale, r * 0.85 * scale, r * 0.7 * scale], [r * scale] * 4, 8, mi)
    path = [P(inward * 0.006, -0.03, -0.012), P(inward * 0.016, -0.05, -0.042), P(inward * 0.02, -0.058, -0.072),
            P(inward * 0.018, -0.058, -0.092)]
    vs += sweep(bm, path, [0.0135 * scale, 0.012 * scale, 0.0105 * scale, 0.009 * scale], [0.012 * scale] * 4, 8, mi)
    return vs


def leg_path(sx):
    x = sx * 0.1
    return [(x * 0.95, 0.0, 0.95), (x, -0.004, 0.76), (sx * 0.105, -0.01, 0.51), (sx * 0.105, 0.0, 0.33), (sx * 0.105, 0.006, 0.13)]


def boot(bm, sx, mi_upper, mi_sole):
    x = sx * 0.105
    vs = vloft(bm, [(0.05, 0.057, 0.06, x, 0.012), (0.12, 0.06, 0.062, x, 0.01), (0.2, 0.062, 0.064, x, 0.008),
                    (0.22, 0.064, 0.066, x, 0.008)], 16, mi_upper, 2.2, False, False)
    path = [(x, 0.075, 0.075), (x, 0.03, 0.085), (x, -0.06, 0.075), (x, -0.15, 0.06), (x, -0.205, 0.05)]
    vs += sweep(bm, path, [0.048, 0.058, 0.06, 0.057, 0.04], [0.05, 0.06, 0.052, 0.042, 0.03], 16, mi_upper, power=2.4)
    sole = [(x, 0.085, 0.022), (x, 0.03, 0.02), (x, -0.06, 0.02), (x, -0.15, 0.02), (x, -0.215, 0.022)]
    vs += sweep(bm, sole, [0.05, 0.062, 0.066, 0.063, 0.045], 0.02, 14, mi_sole, power=3.0)
    return vs


TORSO = [  # z, half-width, half-depth, cx, cy (stocky: belly ~3-4 cm proud of the chest line)
    (0.93, 0.18, 0.132, 0.0, 0.0), (1.0, 0.188, 0.145, 0.0, -0.016), (1.08, 0.196, 0.162, 0.0, -0.038),
    (1.15, 0.195, 0.16, 0.0, -0.038), (1.22, 0.19, 0.148, 0.0, -0.025), (1.29, 0.193, 0.14, 0.0, -0.012),
    (1.35, 0.202, 0.128, 0.0, 0.0), (1.395, 0.198, 0.11, 0.0, 0.004), (1.43, 0.15, 0.09, 0.0, 0.0),
    (1.465, 0.08, 0.072, 0.0, -0.002)]


def torso(bm, mi, grow=0.0, z_from=0.93, collar=True):
    rings = [(z, rx + grow, ry + grow, cx, cy) for z, rx, ry, cx, cy in TORSO if z >= z_from - 1e-6]
    if z_from < 0.93:
        rings = [(z_from, 0.172 + grow, 0.124 + grow, 0.0, 0.0)] + rings
    if not collar:
        rings = rings[:-1]
    return vloft(bm, rings, 24, mi, 2.6)


def sleeve(bm, sx, mi, to=0.32, grow=0.0):
    """Upper-arm (+ optional forearm) sleeve; to = fraction past the elbow along the forearm."""
    sh, el, wr = ARM[sx]
    sh_in = (sh[0] - sx * 0.025, sh[1], sh[2] - 0.022)
    path = [sh_in, _lerp(sh, el, 0.3), _lerp(sh, el, 0.66), el, _lerp(el, wr, to)]
    rr = [0.07, 0.07, 0.064, 0.057, 0.053 - 0.012 * to]
    return sweep(bm, path, [r + grow for r in rr], [r * 0.96 + grow for r in rr], 16, mi, cap0=True, cap1=False)


def _shoulder_blend(sk, verts, frac=0.55):
    """Let the shoulder-top / armpit area of a torso piece follow the upper arms a little."""
    for v in verts:
        ax = abs(v.co.x)
        w = frac * smoothstep(0.11, 0.19, ax) * smoothstep(1.3, 1.41, v.co.z)
        if w <= 0.0:
            continue
        side = "upper_arm.L" if v.co.x > 0 else "upper_arm.R"
        for g in ("pelvis", "spine", "chest", "neck"):
            i = sk.idx[g]
            if i in v[sk.dl]:
                v[sk.dl][i] *= (1.0 - w)
        v[sk.dl][sk.idx[side]] = w


def _mats_s6(CH):
    M = CH._mats()
    M["lips"] = S.pbr("bolts_lips", hexc("b9776a"), 0.5)
    M["sole"] = S.pbr("o_boot_sole", hexc("2a2420"), 0.8)
    M["boots"] = S.pbr("o_boots_v2", hexc("6b4226"), 0.5, var=0.1, var_scale=8.0, bump=0.15)
    M["laces"] = S.pbr("o_laces", hexc("c8b48a"), 0.8)
    M["button"] = S.pbr("o_button", hexc("5a5d60"), 0.4)
    M["pouch"] = S.pbr("o_pouch", hexc("8a5530"), 0.6, var=0.08, bump=0.15)
    M["handle"] = S.pbr("o_handle", hexc("a8794a"), 0.5)
    M["zip"] = S.pbr("o_zip", hexc("9aa0a6"), 0.3, metal=0.8)
    M["skin"] = _skin_mat()
    M["beard"] = _beard_mat("bolts_beard_v2", hexc("5e5a56"), hexc("cfcac4"), hexc("2e2a27"), 900.0)
    M["hair"] = _beard_mat("bolts_hair_v2", hexc("5f5248"), hexc("9a928a"), hexc("3e352e"), 700.0)
    M["lips"] = S.pbr("bolts_lips_v2", hexc("9a5f55"), 0.45)
    return M


def _beard_mat(name, base, light, dark, scale):
    """Fine salt-and-pepper: two noise scales (strands + clumps), short-hair bump."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        vec = S._coord(N, Lk, "Object")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = 1.0
        Lk.new(vec, nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.38, dark
        els[1].position, els[1].color = 0.64, light
        e = els.new(0.5)
        e.color = base
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.85
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.25, 0.0015)
        return S._finish(m, p.outputs[0])
    return B._cached(name, mk)


def _skin_mat():
    """Skin with a warm sunburn on the cheeks/nose (object-space gradient) + subsurface."""
    def mk():
        m, nt, N, Lk, p = S._new_mat("bolts_skin_v2")
        vec = S._coord(N, Lk, "Object")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 60.0
        Lk.new(vec, nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.35, hexc("cf9878")
        els[1].position, els[1].color = 0.7, hexc("dcaa8a")
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.5
        try:
            p.inputs["Subsurface Weight"].default_value = 0.12
            p.inputs["Subsurface Radius"].default_value = (0.012, 0.005, 0.003)
        except Exception:
            pass
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.1, 0.002)
        return S._finish(m, p.outputs[0])
    return B._cached("bolts_skin_v2", mk)


def build_bolts(ctx, char):
    """PROPOSAL 7.3: <= 30k render tris visible (body + signatures + one outfit) -> loft segments x0.7."""
    global SEG_SCALE
    SEG_SCALE = 0.7
    try:
        return _build_bolts(ctx, char)
    finally:
        SEG_SCALE = 1.0


def _build_bolts(ctx, char):
    import characters as CH
    B.part_collection("characters")
    bones = CH.BOLTS_BONES
    rig = make_armature("bolts_rig", bones)
    M = _mats_s6(CH)
    outfit_names = CH.OUTFITS_BUILT
    hide = ["hide_under_%s" % o for o in outfit_names]
    head_b = ["head"]
    # ---------------- core body: head (+ beard/hair shells), face, neck, forearms, hands
    sk = AutoSkin(bones, hide)
    sk.piece(lambda bm: head_mesh(bm, 0)[0], head_b)
    sk.piece(lambda bm: head_mesh(bm, 1, beard_keep, 0.0075)[0], head_b)
    sk.piece(lambda bm: head_mesh(bm, 2, hair_keep, 0.009)[0], head_b)
    # moustache: a soft bar over the upper lip, a touch fuller than the shell
    fy = head_front_y(0.0, 1.627)
    sk.piece(lambda bm: sweep(bm, [(-0.034, fy - 0.004, 1.622), (-0.016, fy - 0.009, 1.629), (0.0, fy - 0.01, 1.63),
                                   (0.016, fy - 0.009, 1.629), (0.034, fy - 0.004, 1.622)],
                              [0.006, 0.008, 0.008, 0.008, 0.006], [0.007, 0.009, 0.009, 0.009, 0.007], 10, 1,
                              up=(0, -1, 0)), head_b)
    ly = head_front_y(0.0, 1.611)
    sk.piece(lambda bm: sweep(bm, [(-0.018, ly + 0.002, 1.612), (0.0, ly - 0.002, 1.611), (0.018, ly + 0.002, 1.612)],
                              0.004, 0.0045, 8, 6, up=(0, -1, 0)), head_b)                             # lips
    # nose (bridge -> tip) + nostril wings
    ny = head_front_y(0.0, 1.69)
    sk.piece(lambda bm: sweep(bm, [(0, ny + 0.006, 1.698), (0, ny - 0.006, 1.676), (0, ny - 0.014, 1.656), (0, ny - 0.017, 1.645)],
                              [0.0075, 0.0095, 0.0135, 0.0115], [0.007, 0.0085, 0.011, 0.0095], 12, 0, up=(0, -1, 0)), head_b)
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: blob(bm, (sx * 0.0128, ny - 0.007, 1.646), (0.0085, 0.008, 0.007), 10, 8, 0), head_b)
        # eyes: white + iris/pupil + upper lid (friendly, slightly hooded)
        ey = head_front_y(sx * 0.034, 1.685)
        ec = (sx * 0.0335, ey + 0.0072, 1.686)
        sk.piece(lambda bm, ec=ec: blob(bm, ec, 0.0125, 14, 10, 3), head_b)
        sk.piece(lambda bm, ec=ec: blob(bm, (ec[0], ec[1] - 0.0106, ec[2]), (0.0078, 0.0026, 0.0078), 12, 6, 4), head_b)
        sk.piece(lambda bm, ec=ec: cut_blob(bm, ec, 0.0136, lambda q: q.z > 0.0055 - 0.2 * q.y, 16, 10, 0), head_b)
        sk.piece(lambda bm, ec=ec: cut_blob(bm, ec, 0.0134, lambda q: q.z < -0.007, 16, 10, 0), head_b)      # lower lid
        # thick brows
        by = head_front_y(sx * 0.035, 1.707)
        sk.piece(lambda bm, sx=sx, by=by: sweep(bm, [(sx * 0.014, by - 0.003, 1.703), (sx * 0.034, by - 0.004, 1.709),
                                                     (sx * 0.054, by + 0.002, 1.707), (sx * 0.066, by + 0.012, 1.7)],
                                               [0.0045, 0.006, 0.0055, 0.004], [0.0035, 0.0045, 0.004, 0.003], 8, 5,
                                               up=(0, -1, 0)), head_b)
        # ears
        sk.piece(lambda bm, sx=sx: blob(bm, (sx * 0.088, 0.008, 1.668), (0.011, 0.025, 0.033), 12, 10, 0,
                                        lambda q: Vector((q.x + 0.004 * (q.z / 0.033), q.y + 0.25 * q.z * 0.2, q.z))), head_b)
    sk.piece(lambda bm: vloft(bm, [(1.42, 0.07, 0.066, 0.0, 0.004), (1.5, 0.066, 0.062, 0.0, -0.002),
                                   (1.575, 0.062, 0.06, 0.0, -0.008), (1.6, 0.058, 0.056, 0.0, -0.01)], 16, 0, 2.0),
             ["chest", "neck", "head"])
    for side, sx in (("L", 1), ("R", -1)):
        sh, el, wr = ARM[sx]
        sk.piece(lambda bm, sx=sx, el=el, wr=wr: sweep(bm, [_lerp(el, wr, -0.12), el, _lerp(el, wr, 0.35), _lerp(el, wr, 0.75), wr,
                                                            (wr[0], wr[1], wr[2] - 0.012)],
                                                      [0.053, 0.055, 0.053, 0.043, 0.033, 0.032], [0.049, 0.05, 0.047, 0.038, 0.028, 0.027],
                                                      14, 0, cap0=False, cap1=False),
                 ["upper_arm." + side, "forearm." + side, "hand." + side], hide=["hide_under_electrician"])
        sk.piece(lambda bm, sx=sx: hand(bm, sx, 0), ["hand." + side], hide=["hide_under_electrician"])
    body = sk.finish("bolts_body", [M["skin"], M["beard"], M["hair"], M["eye"], M["iris"], M["brow"], M["lips"]], rig)
    masks = {}
    for o in outfit_names:
        mm = body.modifiers.new("mask_" + o, "MASK")
        mm.vertex_group = "hide_under_" + o
        mm.invert_vertex_group = True
        mm.show_render = mm.show_viewport = False
        masks[o] = mm
        body.modifiers.move(len(body.modifiers) - 1, 0)          # mask before armature/subsurf
    sig = _signatures(bones, M, rig)
    outfits = {"workshop": _workshop(bones, M, rig), "electrician": _electrician(bones, M, rig)}
    extras = {"fall_arrest_harness": _harness(bones, M, rig)}
    for o in list(outfits.values()) + list(extras.values()):
        o.hide_render = True
    anc = L.link(bpy.data.objects.new("ANC_bolts", None))
    anc.parent = rig
    anc.parent_type = "BONE"
    anc.parent_bone = "head"
    anc.location = (0, 0.05, 0)
    S.anchor(ctx, "bolts", anc)
    tris = tris_of([body] + list(sig.values()) + list(outfits.values()))
    vis = {o: tris_of([body] + list(sig.values()) + [outfits[o]] + ([extras["fall_arrest_harness"]] if o == "electrician" else []))
           for o in outfits}
    print("[chars] Bolts visible render tris per outfit: %s" % vis)
    return {"rig": rig, "body": body, "sig": sig, "outfits": outfits, "extras": extras, "masks": masks,
            "tris_all_outfits": tris}


# ---------------------------------------------------------------- signatures (separate objects, every outfit)
def _signatures(bones, M, rig):
    sig = {}
    # round safety glasses pushed up on the forehead (below any brim), temples running back over the ears
    sk = AutoSkin(bones)
    gz = 1.737
    for sx in (-1, 1):
        fy = head_front_y(sx * 0.034, gz) - 0.009
        c = (sx * 0.034, fy, gz)
        sk.piece(lambda bm, c=c: ring_torus(bm, c, 0.022, 0.0028, 0, 20, 6, "Y"), ["head"])
        sk.piece(lambda bm, c=c: blob(bm, c, (0.021, 0.0015, 0.021), 14, 6, 1), ["head"])
        ty = head_front_y(sx * 0.07, gz - 0.004)
        sk.piece(lambda bm, sx=sx, fy=fy, ty=ty: sweep(bm, [(sx * 0.055, fy, gz), (sx * 0.076, ty + 0.004, gz - 0.003),
                                                           (sx * 0.091, -0.03, gz - 0.012), (sx * 0.094, 0.02, gz - 0.035),
                                                           (sx * 0.09, 0.04, gz - 0.055)],
                                                       0.0022, 0.0035, 6, 0), ["head"])
    by = head_front_y(0.0, gz) - 0.012
    sk.piece(lambda bm: sweep(bm, [(-0.013, by + 0.002, gz + 0.002), (0.0, by, gz + 0.005), (0.013, by + 0.002, gz + 0.002)],
                              0.0024, 0.0024, 6, 0), ["head"])
    sig["safety_glasses"] = sk.finish("bolts_sig_glasses", [M["frame"], M["lens"]], rig, subsurf=0)
    # red bandana: neck wrap, knot front-left, small hanging triangle
    sk = AutoSkin(bones)
    sk.piece(lambda bm: vloft(bm, [(1.43, 0.082, 0.078, 0.0, 0.0), (1.455, 0.079, 0.075, 0.0, -0.002),
                                   (1.48, 0.075, 0.071, 0.0, -0.004), (1.505, 0.069, 0.066, 0.0, -0.006)], 20, 0, 2.0),
             ["neck", "chest"])
    sk.piece(lambda bm: blob(bm, (0.036, -0.081, 1.452), (0.02, 0.016, 0.017), 12, 8, 0), ["neck"])
    sk.piece(lambda bm: sweep(bm, [(0.012, -0.084, 1.45), (0.016, -0.092, 1.41), (0.022, -0.095, 1.37), (0.026, -0.095, 1.35)],
                              [0.046, 0.032, 0.013, 0.003], [0.005, 0.005, 0.004, 0.003], 10, 0, up=(0, -1, 0), power=4.0),
             ["bandana_tail_1", "bandana_tail_2"])
    sk.piece(lambda bm: sweep(bm, [(0.05, -0.078, 1.45), (0.066, -0.084, 1.425), (0.074, -0.088, 1.4)],
                              [0.012, 0.01, 0.004], 0.004, 8, 0, up=(0, -1, 0), power=3.0), ["neck"])
    sig["red_bandana"] = sk.finish("bolts_sig_bandana", [M["bandana"]], rig)
    # flat carpenter's pencil behind the RIGHT ear
    sk = AutoSkin(bones)
    sk.piece(lambda bm: sweep(bm, [(-0.097, -0.04, 1.712), (-0.098, 0.03, 1.702), (-0.097, 0.085, 1.694)],
                              0.0034, 0.0078, 8, 0, cap0=False, power=6.0, up=(0, 0, 1)), ["head"])
    sk.piece(lambda bm: sweep(bm, [(-0.097, -0.04, 1.712), (-0.097, -0.052, 1.7135), (-0.097, -0.062, 1.715)],
                              [0.0034, 0.0022, 0.0006], [0.0078, 0.005, 0.0012], 8, 1, cap0=False, power=6.0), ["head"])
    sig["carpenters_pencil"] = sk.finish("bolts_sig_pencil", [M["pencil"], M["pencil_tip"]], rig, subsurf=0)
    # yellow tape measure clipped at the LEFT front hip
    sk = AutoSkin(bones)
    sk.piece(lambda bm: sweep(bm, [(0.142, -0.13, 0.958), (0.142, -0.17, 0.958)], 0.036, 0.036, 16, 0, power=4.0), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(0.142, -0.1705, 0.958), (0.142, -0.174, 0.958)], 0.022, 0.022, 14, 1, power=2.0), ["pelvis"])
    sk.piece(lambda bm: S.bm_box(bm, (0.142, -0.126, 0.975), (0.02, 0.006, 0.06), 2), ["pelvis"])
    sk.piece(lambda bm: S.bm_box(bm, (0.142, -0.158, 0.919), (0.022, 0.03, 0.006), 1), ["pelvis"])        # tape tongue
    sig["tape_measure"] = sk.finish("bolts_sig_tape", [M["tape"], M["tape_trim"], M["clip"]], rig, subsurf=0)
    return sig


def _torso_weights(sk, verts):
    sk.weight(verts, ["pelvis", "spine", "chest", "neck"], 4.0)
    _shoulder_blend(sk, verts)


def _pants(sk, mi, grow=0.0):
    vs = sk.piece(lambda bm: vloft(bm, [(0.86, 0.172 + grow, 0.122 + grow, 0.0, 0.0), (0.93, 0.184 + grow, 0.136 + grow, 0.0, -0.004),
                                        (1.0, 0.192 + grow, 0.15 + grow, 0.0, -0.018), (1.03, 0.194 + grow, 0.153 + grow, 0.0, -0.022)],
                                  24, mi, 2.6), ["pelvis"])
    for side, sx in (("L", 1), ("R", -1)):
        sk.piece(lambda bm, sx=sx: sweep(bm, leg_path(sx), [0.108 + grow, 0.094 + grow, 0.072 + grow, 0.07 + grow, 0.065 + grow],
                                         [0.104 + grow, 0.09 + grow, 0.07 + grow, 0.066 + grow, 0.063 + grow], 16, mi,
                                         cap0=True, cap1=False),
                 ["pelvis", "thigh." + side, "shin." + side], 6.0, bias={"pelvis": 1.6})
    return vs


def _workshop(bones, M, rig):
    sk = AutoSkin(bones)
    # gray henley: torso + sleeves rolled to just below the elbow + roll cuffs + 3-button placket
    vs = sk.piece(lambda bm: torso(bm, 0, 0.006), ["pelvis"])
    _torso_weights(sk, vs)
    for side, sx in (("L", 1), ("R", -1)):
        sh, el, wr = ARM[sx]
        sk.piece(lambda bm, sx=sx: sleeve(bm, sx, 0, 0.12), ["chest", "upper_arm." + side, "forearm." + side], 6.0, bias={"chest": 1.8})
        cpos = _lerp(el, wr, 0.1)
        sk.piece(lambda bm, c=cpos: ring_torus(bm, c, 0.053, 0.013, 0, 20, 8, "Z"), ["upper_arm." + side, "forearm." + side])
    fy = -0.14
    for k, z in enumerate((1.4, 1.36, 1.32)):
        sk.piece(lambda bm, z=z: blob(bm, (0.0, fy + 0.004 * k, z), (0.006, 0.003, 0.006), 8, 6, 6), ["chest"])
    sk.piece(lambda bm: S.bm_box(bm, (0.0, -0.139, 1.36), (0.03, 0.004, 0.11), 0), ["chest"])
    # navy work pants, brown tool belt + buckle, pouch + hammer on the right hip
    _pants(sk, 1)
    sk.piece(lambda bm: vloft(bm, [(0.965, 0.2, 0.158, 0.0, -0.02), (1.015, 0.201, 0.16, 0.0, -0.022)], 24, 2, 2.6), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(0.0, -0.176, 0.99), (0.0, -0.186, 0.99)], 0.026, 0.022, 12, 5, power=4.0), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(-0.17, -0.115, 1.0), (-0.172, -0.118, 0.88)], 0.05, 0.03, 12, 7, power=4.0), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(-0.205, -0.07, 1.0), (-0.21, -0.07, 0.86)], 0.035, 0.022, 10, 7, power=4.0), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(-0.215, 0.025, 1.01), (-0.215, 0.025, 0.78)], 0.012, 0.012, 8, 9), ["pelvis"])       # hammer handle
    sk.piece(lambda bm: sweep(bm, [(-0.215, -0.03, 1.02), (-0.215, 0.085, 1.02)], 0.014, 0.018, 8, 8, power=3.0), ["pelvis"])  # head
    for side, sx in (("L", 1), ("R", -1)):
        sk.piece(lambda bm, sx=sx: boot(bm, sx, 3, 10), ["foot." + side, "shin." + side], 6.0, bias={"shin." + side: 1.5})
    # navy ball cap (forward); the safety glasses stay below the brim on the forehead
    sk.piece(lambda bm: cut_blob(bm, (0, -0.004, 1.7), (0.089, 0.103, 0.098), lambda q: q.z > 0.033, 24, 16, 4), ["hat_root", "head"])
    sk.piece(lambda bm: blob(bm, (0, -0.004, 1.797), (0.008, 0.008, 0.004), 8, 6, 4), ["head"])
    sk.piece(lambda bm: plate(bm, lambda u, v: Vector(((u - 0.5) * 0.17 * (1 - 0.3 * v), -0.085 - v * 0.085,
                                                       1.753 - 0.014 * v - 0.012 * ((u - 0.5) * 2) ** 2)), 9, 4, 0.006, 4),
             ["head"])
    return sk.finish("bolts_outfit_workshop", [M["henley"], M["pants"], M["belt"], M["boots"], M["cap"], M["buckle"],
                                                M["button"], M["pouch"], M["hammer"], M["handle"], M["sole"]], rig)


def _electrician(bones, M, rig):
    sk = AutoSkin(bones)
    # navy coveralls: torso down to the crotch + legs + long sleeves to the wrist, collar, zip, reflective bands
    vs = sk.piece(lambda bm: torso(bm, 0, 0.009, 0.88), ["pelvis"])
    _torso_weights(sk, vs)
    _pants(sk, 0, 0.004)
    for side, sx in (("L", 1), ("R", -1)):
        sh, el, wr = ARM[sx]
        sk.piece(lambda bm, sx=sx: sleeve(bm, sx, 0, 0.93, 0.004), ["chest", "upper_arm." + side, "forearm." + side, "hand." + side],
                 6.0, bias={"chest": 1.8})
        sk.piece(lambda bm, c=_lerp(el, wr, 0.55): ring_torus(bm, c, 0.05, 0.006, 1, 20, 6, "Z"), ["forearm." + side])
        sk.piece(lambda bm, sx=sx: vloft(bm, [(0.29, 0.069, 0.067, sx * 0.105, 0.002), (0.33, 0.07, 0.068, sx * 0.105, 0.001)],
                                         16, 1, 2.0), ["shin." + side])
        # insulated gloves (hand shape x1.12 + cuff)
        sk.piece(lambda bm, sx=sx: hand(bm, sx, 2, 1.12), ["hand." + side])
        sk.piece(lambda bm, sx=sx, wr=wr: sweep(bm, [(wr[0], wr[1], wr[2] + 0.04), (wr[0], wr[1] - 0.002, wr[2] - 0.01)],
                                                0.043, 0.04, 14, 2, cap0=False, cap1=False), ["hand." + side, "forearm." + side])
        sk.piece(lambda bm, sx=sx: boot(bm, sx, 3, 7), ["foot." + side, "shin." + side], 6.0, bias={"shin." + side: 1.5})
    sk.piece(lambda bm: vloft(bm, [(1.255, 0.202, 0.16, 0.0, -0.026), (1.285, 0.204, 0.154, 0.0, -0.02)], 24, 1, 2.6), ["chest", "spine"])
    sk.piece(lambda bm: vloft(bm, [(1.44, 0.095, 0.09, 0.0, 0.0), (1.475, 0.088, 0.083, 0.0, 0.0)], 20, 0, 2.0), ["chest", "neck"])  # collar
    sk.piece(lambda bm: S.bm_box(bm, (0.0, -0.172, 1.18), (0.012, 0.006, 0.5), 8), ["spine", "chest"])            # zip
    sk.piece(lambda bm: vloft(bm, [(0.965, 0.204, 0.162, 0.0, -0.02), (1.0, 0.205, 0.164, 0.0, -0.022)], 24, 0, 2.6), ["pelvis"])
    sk.piece(lambda bm: sweep(bm, [(-0.2, -0.085, 0.99), (-0.2, -0.085, 0.88)], 0.03, 0.022, 10, 4, power=4.0), ["pelvis"])  # multimeter
    sk.piece(lambda bm: sweep(bm, [(0.08, -0.148, 1.33), (0.08, -0.155, 1.25)], 0.05, 0.006, 10, 0, power=4.0), ["chest"])     # pocket
    # white hard hat: dome + full brim
    sk.piece(lambda bm: cut_blob(bm, (0, -0.006, 1.716), (0.104, 0.12, 0.104), lambda q: q.z > 0.026, 24, 16, 5), ["hat_root", "head"])
    sk.piece(lambda bm: vloft(bm, [(1.742, 0.128, 0.15, 0.0, -0.018), (1.75, 0.132, 0.154, 0.0, -0.018),
                                   (1.756, 0.124, 0.146, 0.0, -0.018)], 24, 5, 2.0, True, True), ["head"])
    sk.piece(lambda bm: sweep(bm, [(0, -0.115, 1.79), (0, 0.0, 1.828), (0, 0.11, 1.79)], 0.012, 0.01, 8, 5), ["head"])
    return sk.finish("bolts_outfit_electrician", [M["cover"], M["strip"], M["gloves"], M["boots"], M["meter"], M["hardhat"],
                                                   M["button"], M["sole"], M["zip"]], rig)


def _harness(bones, M, rig):
    sk = AutoSkin(bones)
    for sx in (-1, 1):
        sk.piece(lambda bm, sx=sx: sweep(bm, [(sx * 0.095, -0.13, 1.44), (sx * 0.1, -0.162, 1.3), (sx * 0.11, -0.17, 1.12),
                                              (sx * 0.12, -0.16, 0.98)], 0.022, 0.004, 8, 0, up=(0, -1, 0), power=4.0),
                 ["chest", "spine", "pelvis"], 4.0)
        sk.piece(lambda bm, sx=sx: sweep(bm, [(sx * 0.095, 0.08, 1.44), (sx * 0.1, 0.13, 1.3), (sx * 0.11, 0.15, 1.1),
                                              (sx * 0.12, 0.13, 0.98)], 0.022, 0.004, 8, 0, up=(0, 1, 0), power=4.0),
                 ["chest", "spine", "pelvis"], 4.0)
        side = "L" if sx > 0 else "R"
        sk.piece(lambda bm, sx=sx: ring_torus(bm, (sx * 0.1, -0.002, 0.86), 0.104, 0.008, 0, 20, 6, "Z"), ["thigh." + side])
    sk.piece(lambda bm: sweep(bm, [(-0.11, -0.178, 1.25), (0.11, -0.178, 1.25)], 0.004, 0.02, 8, 0, power=4.0), ["chest"])
    sk.piece(lambda bm: S.bm_box(bm, (0.0, -0.182, 1.25), (0.045, 0.012, 0.045), 1), ["chest"])
    sk.piece(lambda bm: vloft(bm, [(0.95, 0.208, 0.166, 0.0, -0.02), (0.99, 0.208, 0.166, 0.0, -0.02)], 24, 0, 2.6), ["pelvis"])
    return sk.finish("bolts_outfit_harness", [M["harness"], M["buckle"]], rig)


# ================================================================ Torque (white farm goose, ~0.85 m)
TORQUE_BONES = [
    ("root", (0, 0, 0), (0, 0.15, 0), None),
    ("body", (0, -0.14, 0.3), (0, 0.2, 0.35), "root"),
    ("neck1", (0, -0.19, 0.39), (0, -0.235, 0.58), "body"),
    ("neck2", (0, -0.235, 0.58), (0, -0.2, 0.7), "neck1"),
    ("neck3", (0, -0.2, 0.7), (0, -0.2, 0.785), "neck2"),
    ("head", (0, -0.2, 0.785), (0, -0.29, 0.81), "neck3"),
    ("jaw", (0, -0.268, 0.796), (0, -0.335, 0.79), "head"),
    ("wing.L", (0.13, -0.1, 0.36), (0.08, 0.3, 0.41), "body"),
    ("wing.R", (-0.13, -0.1, 0.36), (-0.08, 0.3, 0.41), "body"),
    ("leg.L", (0.06, 0.02, 0.23), (0.065, 0.0, 0.03), "body"),
    ("leg.R", (-0.06, 0.02, 0.23), (-0.065, 0.0, 0.03), "body"),
    ("tail", (0, 0.24, 0.38), (0, 0.37, 0.43), "body"),
]


def _plumage_mat(name, col, tip=None):
    """Soft white feathers: subtle noise colour, fine bump in object space, a little sheen."""
    def mk():
        m, nt, N, Lk, p = S._new_mat(name)
        vec = S._coord(N, Lk, "Object")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 90.0
        nz.inputs["Detail"].default_value = 3.0
        Lk.new(vec, nz.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.3, tuple(c * 0.93 for c in col[:3]) + (1.0,)
        els[1].position, els[1].color = 0.75, col
        Lk.new(nz.outputs["Fac"], ramp.inputs[0])
        Lk.new(ramp.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.7
        try:
            p.inputs["Sheen Weight"].default_value = 0.4
            p.inputs["Subsurface Weight"].default_value = 0.05
        except Exception:
            pass
        S._bump(N, Lk, nz.outputs["Fac"], p, 0.25, 0.0015)
        return S._finish(m, p.outputs[0])
    return B._cached(name, mk)


def build_torque(ctx, tq):
    global SEG_SCALE
    SEG_SCALE = 0.45
    try:
        return _build_torque(ctx, tq)
    finally:
        SEG_SCALE = 1.0


def _build_torque(ctx, tq):
    B.part_collection("characters")
    rig = make_armature("torque_rig", TORQUE_BONES)
    c = tq["colors"]
    plum = _plumage_mat("torque_plumage_v2", hexc(c["plumage"][1:]))
    tips = _plumage_mat("torque_tips_v2", hexc(c["wing_tips_shadow"][1:]))
    bill = S.pbr("torque_bill", hexc(c["bill"][1:]), 0.4, coat=0.3)
    knob = S.pbr("torque_knob", hexc("e07a1c"), 0.45, coat=0.2)
    nail = S.pbr("torque_nail", hexc(c["bill_nail"][1:]), 0.4)
    legs = S.pbr("torque_legs", hexc(c["legs_feet"][1:]), 0.55, var=0.05, var_scale=40.0, bump=0.1)
    eye = S.pbr("torque_eye", hexc("1a1f2a"), 0.1, coat=1.0)
    iris = S.pbr("torque_iris", hexc(c["eyes"][1:]), 0.15, coat=1.0)
    sk = AutoSkin(TORQUE_BONES)
    # s7: body, neck, head and folded wing pads are built as closed shells at full ring resolution into their own
    # collector, then voxel-remeshed into ONE continuous plumage surface (no intersection seams where the wing pads
    # and the neck meet the body) and re-weighted from the source shells (_merge_plumage).
    pk = AutoSkin(TORQUE_BONES)
    global SEG_SCALE
    seg_keep, SEG_SCALE = SEG_SCALE, 1.0
    # plump teardrop body: breast low in front, back rising into a short pointed tail
    ys = [-0.26, -0.22, -0.14, -0.02, 0.1, 0.2, 0.28, 0.34, 0.38]
    zs = [0.36, 0.33, 0.305, 0.3, 0.315, 0.345, 0.385, 0.42, 0.44]
    rx = [0.05, 0.12, 0.158, 0.168, 0.16, 0.13, 0.085, 0.04, 0.01]
    rz = [0.06, 0.13, 0.16, 0.162, 0.15, 0.12, 0.08, 0.04, 0.01]
    pk.piece(lambda bm: sweep(bm, [(0, y, z) for y, z in zip(ys, zs)], rx, rz, 24, 0), ["body", "tail", "neck1"], 6.0,
             bias={"neck1": 2.5})
    # long S-neck (forward from the breast, back, then up to the head); capped ends sit inside body / head
    npath = [(0, -0.19, 0.38), (0, -0.228, 0.5), (0, -0.235, 0.6), (0, -0.215, 0.67), (0, -0.2, 0.73), (0, -0.203, 0.775),
             (0, -0.212, 0.8)]
    nr = [0.075, 0.056, 0.044, 0.038, 0.036, 0.037, 0.04]
    pk.piece(lambda bm: sweep(bm, npath, [r * 1.0 for r in nr], [r * 1.08 for r in nr], 20, 0, up=(0, -1, 0)),
             ["body", "neck1", "neck2", "neck3", "head"], 6.0)
    # head: rounded, slightly long, flat-ish crown; cheeks
    pk.piece(lambda bm: blob(bm, (0, -0.228, 0.815), (0.039, 0.058, 0.043), 24, 16, 0,
                             lambda q: Vector((q.x * (1.0 - 0.18 * smoothstep(-0.02, -0.058, q.y)), q.y,
                                               q.z - 0.008 * smoothstep(0.0, -0.05, q.y) * (1 if q.z > 0 else 0)))), ["head"])
    for sx in (-1, 1):
        side = "L" if sx > 0 else "R"
        # folded wing: a long flattened pad along the side, tips crossing over the tail
        wp = [(sx * 0.128, -0.07, 0.36), (sx * 0.148, -0.0, 0.357), (sx * 0.14, 0.08, 0.365), (sx * 0.115, 0.19, 0.385),
              (sx * 0.075, 0.29, 0.415), (sx * 0.04, 0.36, 0.435)]
        pk.piece(lambda bm, wp=wp: sweep(bm, wp, [0.02, 0.034, 0.036, 0.03, 0.02, 0.006], [0.035, 0.062, 0.066, 0.05, 0.03, 0.01],
                                         18, 0, up=(0, 0, 1)), ["wing." + side], 6.0)
    SEG_SCALE = seg_keep
    mk = AutoSkin(TORQUE_BONES)
    _merge_plumage(pk, mk)
    # bill (upper) + knob at the base + nail; lower mandible on the jaw bone
    sk.piece(lambda bm: sweep(bm, [(0, -0.26, 0.813), (0, -0.29, 0.806), (0, -0.318, 0.798), (0, -0.342, 0.79)],
                              [0.025, 0.022, 0.019, 0.012], [0.019, 0.014, 0.01, 0.007], 14, 2, up=(0, 0, 1), power=2.4), ["head"])
    sk.piece(lambda bm: blob(bm, (0, -0.262, 0.826), (0.012, 0.016, 0.0105), 12, 8, 3), ["head"])
    sk.piece(lambda bm: blob(bm, (0, -0.342, 0.793), (0.009, 0.006, 0.005), 8, 6, 4), ["head"])
    sk.piece(lambda bm: sweep(bm, [(0, -0.262, 0.797), (0, -0.295, 0.792), (0, -0.328, 0.788)],
                              [0.019, 0.015, 0.008], [0.008, 0.006, 0.004], 12, 2, up=(0, 0, 1), power=2.4), ["jaw"])
    for sx in (-1, 1):
        side = "L" if sx > 0 else "R"
        sk.piece(lambda bm, sx=sx: blob(bm, (sx * 0.0335, -0.245, 0.826), (0.0035, 0.0085, 0.0085), 10, 8, 5), ["head"])
        sk.piece(lambda bm, sx=sx: blob(bm, (sx * 0.0365, -0.246, 0.826), (0.0015, 0.0045, 0.0045), 8, 6, 6), ["head"])
        # layered primary/secondary feather tips (slightly darker), give the wing its read
        for k, (y0, z0, ln) in enumerate(((0.06, 0.335, 0.2), (0.1, 0.35, 0.2), (0.14, 0.365, 0.19))):
            fp = [(sx * (0.172 - 0.008 * k), y0, z0 + 0.01), (sx * (0.158 - 0.01 * k), y0 + ln * 0.5, z0 + 0.035),
                  (sx * (0.11 - 0.012 * k), y0 + ln, z0 + 0.055)]
            sk.piece(lambda bm, fp=fp: sweep(bm, fp, [0.008, 0.007, 0.003], [0.022, 0.017, 0.005], 10, 1, up=(0, 0, 1), power=2.2),
                     ["wing." + side])
        # orange legs + webbed feet (3 toes + web)
        x = sx * 0.062
        sk.piece(lambda bm, x=x: sweep(bm, [(x, 0.02, 0.23), (x, 0.012, 0.15), (x * 1.04, 0.0, 0.06), (x * 1.04, -0.004, 0.025)],
                                       [0.026, 0.017, 0.014, 0.013], [0.026, 0.017, 0.014, 0.013], 10, 3), ["leg." + side, "body"],
                 6.0, bias={"body": 2.0})
        sk.piece(lambda bm, x=x: sweep(bm, [(x, 0.012, 0.012), (x, -0.045, 0.01), (x, -0.1, 0.008)], [0.012, 0.038, 0.052],
                                       0.0035, 10, 3, up=(0, 0, 1), power=4.0), ["leg." + side])
        for dx, ln in ((-0.042, 0.1), (0.0, 0.115), (0.042, 0.1)):
            sk.piece(lambda bm, x=x, dx=dx, ln=ln: sweep(bm, [(x, 0.0, 0.016), (x + dx * 0.6, -ln * 0.6, 0.012),
                                                             (x + dx, -ln, 0.009)], [0.008, 0.007, 0.005], [0.007, 0.006, 0.004],
                                                         8, 3), ["leg." + side])
    # s7: the merged plumage is dense enough to shade smooth without subdivision; the small parts keep subsurf 1
    body = mk.finish("torque_body", [plum], rig, subsurf=0)
    parts = sk.finish("torque_parts", [plum, tips, bill, knob, nail, iris, eye, legs], rig)
    # material index fix: legs/feet used index 3 above for brevity -> remap: knob 3 only for the knob blob
    _remap_torque_mats(parts)
    anc = L.link(bpy.data.objects.new("ANC_torque", None))
    anc.parent = rig
    anc.parent_type = "BONE"
    anc.parent_bone = "head"
    anc.location = (0, 0.02, 0.05)
    S.anchor(ctx, "torque", anc)
    return {"rig": rig, "body": body, "parts": parts, "tris": tris_of([body, parts])}


PLUMAGE_VOXEL = 0.012       # m; ~7k quads (~14k tris) for the merged plumage, smooth shaded, no subsurf


def _merge_plumage(pk, sk):
    """Voxel-remesh the plumage shells collected in `pk` into one closed surface, smooth it a little, and append it
    to `sk` (material 0). Weights: inverse-distance blend of the 6 nearest source vertices (their skin weights)."""
    from mathutils import kdtree
    me = bpy.data.meshes.new("torque_plum_src")
    pk.bm.to_mesh(me)
    ob = bpy.data.objects.new("torque_plum_src", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("remesh", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = PLUMAGE_VOXEL
    mod.adaptivity = 0.0
    dg = bpy.context.evaluated_depsgraph_get()
    me_r = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    src = [(v.co.copy(), {g: w for g, w in v[pk.dl].items()}) for v in pk.bm.verts]
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    pk.bm.free()
    kd = kdtree.KDTree(len(src))
    for i, (co, _w) in enumerate(src):
        kd.insert(co, i)
    kd.balance()
    bm = sk.bm
    tmp = bmesh.new()
    tmp.from_mesh(me_r)
    bpy.data.meshes.remove(me_r)
    for _k in range(2):
        bmesh.ops.smooth_vert(tmp, verts=tmp.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    vmap = {}
    for v in tmp.verts:
        nv = bm.verts.new(v.co)
        acc = {}
        for co, i, d in kd.find_n(v.co, 6):
            w0 = 1.0 / (d + 1e-4) ** 2
            for g, w in src[i][1].items():
                acc[g] = acc.get(g, 0.0) + w * w0
        s = sum(acc.values()) or 1.0
        for g, w in acc.items():
            if w / s > 0.01:
                nv[sk.dl][g] = w / s
        vmap[v] = nv
    for f in tmp.faces:
        try:
            nf = bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = 0
        except ValueError:
            pass
    tmp.free()


def _remap_torque_mats(ob):
    """Legs/feet were tagged with index 3 (knob) when built; the knob is the only index-3 piece above z 0.7."""
    me = ob.data
    for p in me.polygons:
        if p.material_index == 3 and p.center.z < 0.6:
            p.material_index = 7


def torque_pose(clip, t, base=None):
    """Goose clips: idle, waddle, honk, peck. (rx, ry, rz) radians, bone-local."""
    import characters as CH
    _s, _ease = CH._s, CH._ease
    p = {"neck1": (0.0, 0, 0), "neck2": (0.0, 0, 0), "neck3": (0.0, 0, 0), "head": (0.0, 0, 0.25 * _s(t, 4.0))}
    if clip in ("idle", None):
        p["body"] = (0.02 * _s(t, 2.5), 0, 0)
        p["neck2"] = (0.06 * _s(t, 5.0), 0, 0)
        p["tail"] = (0, 0, 0.15 * max(0.0, _s(t, 3.1)) ** 8)
        return p
    if clip == "waddle":
        T = 24 / 30.0
        p["body"] = (0.03, 0.1 * _s(t, T), 0)
        p["leg.L"] = (-0.38 * _s(t, T), 0, 0)
        p["leg.R"] = (0.38 * _s(t, T), 0, 0)
        p["neck1"] = (0.1 * _s(t, T / 2), 0, 0)
        p["head"] = (-0.1 * _s(t, T / 2), 0, 0.1 * _s(t, T))
        p["tail"] = (0, 0, 0.2 * _s(t, T))
        return p
    if clip == "honk":
        e = _ease(t, 0.25)
        p["neck1"] = (0.35 * e, 0, 0)
        p["neck2"] = (-0.25 * e, 0, 0)
        p["neck3"] = (-0.2 * e, 0, 0)
        p["head"] = (-0.25 * e, 0, 0)
        op = max(0.0, _s(t, 0.5)) if t < 1.2 else 0.0
        p["jaw"] = (0.45 * op, 0, 0)
        p["wing.L"] = (0, 0, -0.15 * e * op)
        p["wing.R"] = (0, 0, 0.15 * e * op)
        return p
    if clip == "peck":
        cyc = (t % 1.1) / 1.1
        down = math.sin(math.pi * min(1.0, cyc / 0.55)) if cyc < 0.55 else 0.0
        e = _ease(t, 0.3)
        p["body"] = (-0.12 * e - 0.08 * down, 0, 0)
        p["neck1"] = (-0.6 * e - 0.35 * down, 0, 0)
        p["neck2"] = (-0.2 * e, 0, 0)
        p["neck3"] = (0.25 * e, 0, 0)
        p["head"] = (0.3 * e + 0.2 * down, 0, 0)
        return p
    return p

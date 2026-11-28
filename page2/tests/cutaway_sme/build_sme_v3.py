"""Mercer Hollow • bench turbine • v3. See REPORT.md for the render command."""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote

# Shared builders and assets are read-only, including their Python cache directories.
sys.dont_write_bytecode = True
import bpy
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(__file__).resolve().parent
PAGE = HERE.parents[1]
sys.path[:0] = [str(PAGE.parent / "pipeline/cutaway"), str(PAGE / "blender")]
import cutlib as C
from mh_blender import set_keys

FPS = 24
END = 144
STILLS = [(8, "01_dead_center"), (56, "02_at_the_rim"),
          (92, "03_on_the_bench"), (140, "04_catch_and_return")]
R = math.radians
AXLE = 1.17
FRAMES = tuple(range(1, END + 1))
OUT = HERE / "out_v3"
PIVOT = Vector((-.70, -.108, AXLE))
LEVER = Vector((.109, .401, .094))
PULL = Vector((.014, .385, 1.347))
SLIDE_TRAVEL = .475
DRAIN = Vector((.423, -.365, .852))
SPOUT = Vector((.690, -.657, .757))
PAIL = Vector((.718, -.678, .31))
rng = random.Random(224)


def device(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    scene.cycles.device = "CPU"
    try:
        prefs.compute_device_type = "METAL"
        prefs.refresh_devices()
    except (TypeError, RuntimeError, ValueError):
        return "CPU"
    if not any(d.type == "METAL" for d in prefs.devices):
        return "CPU"
    for d in prefs.devices:
        d.use = d.type in {"METAL", "CPU"}
    scene.cycles.device = "GPU"
    return " + ".join(f"{d.name} ({d.type})" for d in prefs.devices if d.use)


def key(obj, field, pairs):
    for frame, value in pairs:
        setattr(obj, field, value)
        obj.keyframe_insert(data_path=field, frame=frame)


def group(name, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def turned(name, a, b, radius, mat, tip=None, sides=48):
    axis = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=radius,
                                    radius2=radius if tip is None else tip,
                                    depth=axis.length, location=(Vector(a) + Vector(b)) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(mat)
    for face in o.data.polygons:
        face.use_smooth = len(face.vertices) == 4 and sides > 8
    bevel = o.modifiers.new("Machined edge", "BEVEL")
    bevel.width, bevel.segments = min(.0018, radius * .10, axis.length * .20), 3
    o.modifiers.new("Flat end normals", "WEIGHTED_NORMAL")
    return o


def arc(name, center_z, inside, outside, a0, a1, front, back, mat, edge):
    angles = [R(a0 + (a1-a0)*i/64) for i in range(65)]
    outline = [(r*math.cos(a), center_z+r*math.sin(a))
               for r, path in [(outside, angles), (inside, reversed(angles))] for a in path]
    return soften(C.section(name, outline, front, back, mat, edge), .0018)


def ease(f, start, end):
    t = max(0., min(1., (f - start) / (end - start)))
    return t * t * (3 - 2*t)


def aim(f):
    lift = ease(f, 26, 49) + .025 * (ease(f, 43, 49) - ease(f, 49, 57))
    return Euler((0, R(-24.5) * lift, R(6.5) * lift))


def carriage(f):
    return SLIDE_TRAVEL * (1 - ease(f, 98, 123))


def soften(obj, width=.002, segments=3):
    mod = obj.modifiers.new("Manufactured edge radius", "BEVEL")
    mod.width, mod.segments = width, segments
    mod.harden_normals = True
    obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def bar(name, a, b, w, d, mat, radius=.002):
    return soften(C.beam(name, a, b, w, d, mat), radius)


def cable(name, points, radius, mat):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions, data.resolution_u = "3D", 10
    data.bevel_depth, data.bevel_resolution, data.use_fill_caps = radius, 3, True
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for k, co in zip(spline.bezier_points, points):
        k.co = co
        k.handle_left_type = k.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def revolve(name, origin, axis, profile, mat, sides=64):
    """Closed radial profile. A zero-radius station is one axial vertex."""
    verts, rings, faces, smoothed = [], [], [], []
    for r, z in profile:
        ring = []
        for i in range(sides if r else 1):
            a = i * math.tau / sides
            ring.append(len(verts))
            verts.append((r*math.cos(a), r*math.sin(a), z))
        rings.append(ring)
    for j, lower in enumerate(rings):
        k = (j + 1) % len(rings)
        upper = rings[k]
        if len(lower) == len(upper) == 1:
            continue
        for i in range(sides):
            corners = [lower[i % len(lower)], lower[(i+1) % len(lower)],
                       upper[(i+1) % len(upper)], upper[i % len(upper)]]
            faces.append(tuple(dict.fromkeys(corners)))
            smoothed.append(sides > 8 and abs(profile[j][1] - profile[k][1]) > .00001)
    obj = C.mesh(name, verts, faces, mat)
    obj.location = origin
    obj.rotation_euler = Vector(axis).to_track_quat("Z", "Y").to_euler()
    for poly, smooth in zip(obj.data.polygons, smoothed):
        poly.use_smooth = smooth
    return obj


UP, FRONT, RIGHT = (0, 0, 1), (0, -1, 0), (1, 0, 0)


def fastener(name, origin, axis, r, m, parent=None):
    """Beaded washer and a hex head with a blind hex recess."""
    seat = Vector(origin)
    direction = Vector(axis).normalized()
    washer = revolve(name + " washer", seat, axis,
        [(r*.66, 0), (r*1.36, 0), (r*1.40, r*.10), (r*1.34, r*.19), (r*.66, r*.19)], m["silver"], 32)
    head = revolve(name, seat + direction*r*.17, axis,
        [(0, 0), (.92*r, 0), (r, .09*r), (r, .60*r), (.90*r, .69*r),
         (.48*r, .69*r), (.41*r, .60*r), (.41*r, .29*r), (0, .29*r)], m["steel"], 6)
    soften(head, .035*r, 2)
    head.parent = washer.parent = parent


def lettering(body, pos, size, mat, horizontal=False):
    data = bpy.data.curves.new(body, "FONT")
    data.body, data.size, data.align_x, data.align_y = body, size, "CENTER", "CENTER"
    data.font = bpy.data.fonts.get("Oswald-SemiBold") or bpy.data.fonts.load(
        str(C.ROOT / "assets/fonts/Oswald-SemiBold.ttf"), check_existing=True)
    data.space_character, data.extrude = 1.10, .00008
    obj = bpy.data.objects.new(body, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    obj.rotation_euler.x = 0 if horizontal else math.pi/2
    data.materials.append(mat)
    return obj


def noise(nt, coord, scale, detail=2.5, distortion=0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Distortion"].default_value = distortion
    nt.links.new(coord, n.inputs["Vector"])
    return n.outputs["Fac"]


def into(nt, value, socket):
    if isinstance(value, bpy.types.NodeSocket):
        nt.links.new(value, socket)
    else:
        socket.default_value = value


def mapped(nt, value, lo, hi, start=0, end=1):
    n = nt.nodes.new("ShaderNodeMapRange")
    n.clamp = True
    for field, v in zip(("Value", "From Min", "From Max", "To Min", "To Max"),
                        (value, lo, hi, start, end)):
        into(nt, v, n.inputs[field])
    return n.outputs["Result"]


def mix(nt, factor, a, b, mode="MIX"):
    n = nt.nodes.new("ShaderNodeMixRGB")
    n.blend_type = mode
    for value, socket in zip((factor, a, b), n.inputs):
        into(nt, value, socket)
    return n.outputs[0]


def calc(nt, op, a, b):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    into(nt, a, n.inputs[0])
    into(nt, b, n.inputs[1])
    return n.outputs[0]


def vector_op(nt, op, a, b):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    into(nt, a, n.inputs[0])
    into(nt, b, n.inputs[1])
    return n.outputs[0]


def surface(name, colors, rough, metal=0, grain=(1, 1, 1), scale=15, height=.00018,
            coat=0, patina=False):
    m = C.material(name, colors[0], rough=rough[0], metal=metal)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    coords = nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    grain_uv = vector_op(nt, "MULTIPLY", coords, grain)
    broad = noise(nt, grain_uv, scale, 3.5, .32)
    pores = noise(nt, grain_uv, scale*10, 2)
    tint = mix(nt, mapped(nt, broad, .25, .76), *map(C.color, colors))
    r = mapped(nt, calc(nt, "ADD", pores, broad), .68, 1.30, *rough)
    if patina:
        # Vertex curvature on a six-sided casting bleeds across whole flats. Restrict
        # exposed metal to the manufactured bevel faces in finish_edges().
        m["enamel_with_wear"] = True
    into(nt, tint, p.inputs["Base Color"])
    into(nt, r, p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value, bump.inputs["Strength"].default_value = height, .22
    into(nt, pores, bump.inputs["Height"])
    into(nt, bump.outputs[0], p.inputs["Normal"])
    p.inputs["Coat Weight"].default_value, p.inputs["Coat Roughness"].default_value = coat, .28
    return m


def timber():
    m = surface("Oiled maple • stave grain and rising wet front", ("795439", "b28a58"),
                (.33, .57), grain=(.85, 31, 29), scale=3.9, height=.00034, coat=.13)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    pos = nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    edge = vector_op(nt, "SUBTRACT", pos, (.326, -.426, .7605))
    ellipse = vector_op(nt, "MULTIPLY", edge, (4.6, 8.6, 48.))
    length = nt.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    into(nt, ellipse, length.inputs[0])
    broken = calc(nt, "ADD", length.outputs["Value"], mapped(nt, noise(nt, pos, 32), .2,.8,-.12,.12))
    size = nt.nodes.new("ShaderNodeValue")
    size.label = "Spread measured from splashdown"
    key(size.outputs[0], "default_value", [(1,-.2),(48,-.2),(64,.22),(90,.88),(117,1.03),(144,1.01)])
    wet = mapped(nt, calc(nt, "SUBTRACT", size.outputs[0], broken), -.024, .036)
    base = p.inputs["Base Color"].links[0].from_socket
    dry = p.inputs["Roughness"].links[0].from_socket
    into(nt, mix(nt, wet, base, mix(nt, .65, base, C.color("655340"), "MULTIPLY")), p.inputs["Base Color"])
    into(nt, mix(nt, wet, dry, (.095,.095,.095,1)), p.inputs["Roughness"])
    into(nt, mapped(nt, wet, 0,1,.13,.91), p.inputs["Coat Weight"])
    return m


def dielectric(name, tint, ior, rough):
    m = C.material(name, tint, rough=rough)
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["IOR"].default_value, p.inputs["Transmission Weight"].default_value = ior, 1
    return m


def materials():
    m = {
        "teal": surface("Marine enamel • exposed casting edges", ("153e40","306562"),
                        (.27,.49), height=.00048, coat=.30, patina=True),
        "brass": surface("Sand-cast manganese bronze", ("765333","ba9257"),
                         (.30,.50), .91, scale=32, height=.00033),
        "steel": surface("Blackened steel • burnished flats", ("394343","67706d"),
                         (.24,.46), .93, grain=(1,1,4), height=.00011),
        "silver": surface("Drawn nickel steel • longitudinal finish", ("a0adae","c4ccca"),
                          (.21,.38), .98, grain=(1,2,8), scale=21, height=.000055),
        "brass": surface("Cast phosphor bronze", ("876443","cba16b"),
                         (.26,.46), .94, scale=28, height=.00023),
        "polish": surface("Lapped bronze • polished bucket lips", ("b18b5e","e2bc85"),
                          (.18,.31), .97, grain=(1,1,8), height=.000045),
        "rim": surface("Section face • ground cast iron", ("79766c","b0ab98"), (.27,.41),
                       .88, grain=(1,3,12), height=.00012),
        "red": surface("Vermilion oxide enamel", ("8b3926","b75a3b"), (.28,.46), coat=.23, patina=True),
        "rubber": surface("Worn vulcanized hose", ("202726","35403d"), (.44,.73), height=.00024),
        "green": surface("Workshop cabinet • industrial lacquer", ("263e3a","415950"),
                         (.42,.63), height=.00024, coat=.14, patina=True),
        "wood": timber(),
        "joinery": surface("Aged shop joinery", ("473d32","80684b"), (.47,.7), grain=(1,2,16), scale=3),
        "board": C.polyhaven("white_planks_clean", 1.85),
        "concrete": C.polyhaven("concrete_floor_02", 1.75),
        "water": dielectric("Creek water • air interface", "f3fcff", 1.333, .045),
        "glass": dielectric("Soda-lime lamp glass", "fbfcf7", 1.51, .065),
        "dial": surface("Ivory enamel dial", ("c0b79a","e1d6b5"), (.38,.52), height=.00005),
        "ink": C.material("Fired black dial ink","182a2a",rough=.54),
        "galv": surface("Spangled galvanized sheet", ("798784","aeb7af"),
                        (.31,.53), .93, scale=100, height=.00012),
    }
    # The whitewash is stained a muted blue-grey, retaining its photographed grain.
    nt = m["board"].node_tree
    base = nt.nodes["Principled BSDF"].inputs["Base Color"]
    into(nt, mix(nt, .84, base.links[0].from_socket, C.color("52676c"), "MULTIPLY"), base)
    return m
def workshop(m):
    C.box("Continuous cast shop floor", (0,0,-.07), (10,13,.14), m["concrete"], .006)
    C.box("Recessed kick plinth", (0,.075,.042), (3.19,.84,.084), m["steel"], .006)
    C.box("Cabinet carcass", (0,.04,.374), (3.30,.97,.582), m["green"], .007)
    for x in (-1.23,-.41,.41,1.23):
        for z,h in ((.255,.322),(.514,.182)):
            C.box("Folded drawer front", (x,-.454,z), (.805,.023,h), m["green"], .004)
            for dx in (-.069,.069):
                turned("Pull mounting stud", (x+dx,-.466,z+.049), (x+dx,-.485,z+.049), .010, m["silver"])
            cable("Drawer bail", [(x-.069,-.474,z+.049),(x-.064,-.497,z+.038),
                  (x,-.501,z+.032),(x+.064,-.497,z+.038),(x+.069,-.474,z+.049)], .006, m["silver"])
    # Separate glued staves expose the end grain and carry different lengths of the same stock.
    for i in range(12):
        y = -.46 + (i+.5)*.082
        stave = C.box("Maple bench stave", (0,y,.713), (3.45,.082,.095), m["wood"], .00055)
        shift = rng.uniform(-1.5,1.5)
        for v in stave.data.vertices:
            v.co.x += shift
        stave.location.x -= shift
    for x in (-1.35,1.36):
        fastener("Bench dog plug", (x,-.32,.7605), UP, .009, m)

    # Rear shop wall is open at the sash. Outdoors is seen through real glazing openings.
    wall_start = set(bpy.data.objects)
    for x0, x1, z0, z1 in [(-4, -.97, 0, 3), (.43, 4, 0, 3), (-.97,.43,0,1.23),(-.97,.43,2.28,3)]:
        soften(C.bounds("Stained workshop boards", x0,x1,2.12,2.23,z0,z1,m["board"]), .002)
    for x in (-.97,-.27,.43):
        C.box("Sash stile", (x,2.09,1.76), (.045,.082,1.09), m["joinery"], .004)
    for z in (1.23,1.76,2.28):
        C.box("Sash rail", (-.27,2.09,z), (1.44,.08,.045), m["joinery"], .004)
    C.box("Projecting sill", (-.27,2.05,1.20), (1.58,.21,.055), m["joinery"], .005)
    C.box("Window header", (-.27,2.08,2.34), (1.62,.12,.095), m["joinery"])
    C.box("High shelf", (.91,1.99,2.11), (.81,.27,.035), m["joinery"])
    for i in range(4):
        x, h = .62+i*.14, .12 + .035*(i%2)
        turned("Oil tin", (x,1.98,2.13), (x,1.98,2.13+h), .047, m[("teal","red","steel","brass")[i]])
        turned("Oil tin rolled lid", (x,1.98,2.13+h), (x,1.98,2.137+h), .049, m["silver"])
    C.box("Wall tool strip", (.9,2.01,1.71), (.78,.04,.065), m["joinery"], .004)
    for i in range(4):
        x, z = .62 + .16*i, 1.71
        bar("Forged wrench handle", (x,1.965,z),(x-.012,1.965,z-.2-i*.022),.022,.011,m["steel"])
        for sign in (-1,1):
            bar("Open wrench jaw", (x-.012,1.965,z-.19-i*.022),
                   (x-.012+sign*.022,1.965,z-.225-i*.022),.013,.013,m["silver"])
    for obj in set(bpy.data.objects)-wall_start:
        obj.location.x -= .92
    # Slotted rack with cabinetmaker's chisels and recognizable turned grips.
    C.box("Chisel rack",(-.27,1.95,1.36),(.45,.09,.045),m["joinery"],.005)
    for i in range(5):
        x = -.44+.082*i
        turned("Chisel handle",(x,1.91,1.38),(x,1.91,1.49+.012*(i%2)),.024,m["red"],.016)
        turned("Ferrule",(x,1.91,1.366),(x,1.91,1.392),.019,m["brass"])
        C.box("Polished chisel blade",(x,1.91,1.29),(.018+.002*i,.005,.15),m["silver"])
    for x in (-2.05, 1.65):
        C.box("Douglas fir stud", (x,2.05,1.36), (.115,.18,2.72), m["joinery"])
    C.box("Garage lintel", (0,1.93,2.64), (5,.25,.18), m["joinery"], .004)
    for x in (-1.3,0,1.3):
        bar("Exposed joist", (x,-.55,2.63), (x,2.1,2.81), .07,.14,m["joinery"])

    for x in (-1.54, -.84):
        C.box("Window glass", (x,2.138,1.76), (.654,.003,1.00), m["glass"], .0007)
    # Work marks on the sill and a darker shelf lip give the background a scale cue.
    for x in (-.62,.03):
        bar("Shelf knee brace", (x,2.065,1.92),(x,1.89,2.09),.019,.024,m["steel"])
    # Modest backyard depth seen through the window.
    sod = C.polyhaven("aerial_grass_rock", 3)
    C.box("Yard beyond sash", (0,7,-.065), (18,9,.12), sod)
    for i in range(40):
        x = -4+i*.22
        C.section("Cedar dog-ear fence", [(x,0),(x+.204,0),(x+.204,1.16),
                  (x+.18,1.19),(x+.024,1.19),(x,1.16)], 5.2, 5.24, m["joinery"])
    path = C.ROOT/"assets/cc0/polyhaven/models/shrub_02/shrub_02_1k.gltf"
    bpy.ops.import_scene.gltf(filepath=str(path))
    plants = sorted((o for o in bpy.context.selected_objects if o.type == "MESH"),
                    key=lambda o:o.name)
    for i, plant in enumerate(plants):
        plant.location = (-.8-i*1.10,4.18+.18*(i%2),0)
        plant.rotation_euler.z = R(-22+i*30)

        for mat in plant.data.materials:
            p = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if p:
                p.inputs["Subsurface Weight"].default_value = .08
                p.inputs["Subsurface Radius"].default_value = (.36, 1, .23)
                p.inputs["Subsurface Scale"].default_value = .00045


def workshop_details(m):
    # An actual roof and return wall give the bench and character the same indirect light.
    C.box("Roof over open work bay",(0,.75,2.863),(6.6,3.25,.088),m["joinery"],.006)
    sapling_path=C.ROOT/"assets/cc0/polyhaven/models/pine_sapling_small/pine_sapling_small_1k.gltf"
    bpy.ops.import_scene.gltf(filepath=str(sapling_path))
    saplings=sorted((o for o in bpy.context.selected_objects if o.type=="MESH"),key=lambda o:o.name)
    for i,sapling in enumerate(saplings):
        sapling.location=(-2.35+i*.94,5.69+.40*(i%2),0)
        sapling.scale=(1.8,1.8,1.8)
        sapling.rotation_euler.z=.7+i*1.8
        for mat in sapling.data.materials:
            if "twig" in mat.name.lower():
                shader=next(n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
                shader.inputs["Subsurface Weight"].default_value=.09
                shader.inputs["Subsurface Radius"].default_value=(.38,1,.26)
                shader.inputs["Subsurface Scale"].default_value=.0004
    C.box("Return wall",(2.92,.91,1.42),(.105,3.21,2.84),m["board"],.003)
    x,y,z=.81,2.02,1.61
    C.box("Drawing board",(x,y,z),(.351,.023,.443),m["joinery"],.004)
    paper=surface("Creased workshop drawing stock",("918e76","b1a992"),(.74,.89),height=.00004)
    C.box("Shop sketch • stock",(x,y-.0123,z),(.326,.0014,.405),paper,.0004)
    front=y-.0132
    lettering("IMPULSE RUNNER",(x,front-.0002,z+.147),.033,m["ink"])
    lettering("M. H.    /    DETAIL  02",(x,front-.0002,z-.151),.014,m["ink"])
    for rad in (.028,.074,.091):
        C.strand("Drawing line",[(x+rad*math.sin(j*math.tau/48),front,
                 z+rad*math.cos(j*math.tau/48)) for j in range(49)],.00065,m["ink"])
    for i in range(10):
        a=i*math.tau/10
        for j in (-.19,.19):
            pts=[(x+r*math.sin(a+off),front,z+r*math.cos(a+off))
                 for r,off in ((.076,-.14),(.108,j),(.112,.16),(.088,.10))]
            C.strand("Blade sketch",pts,.00065,m["ink"])
    C.box("Paper spring clip",(x,front-.003,z+.197),(.069,.008,.021),m["steel"],.002)
    for dx in (-.35,.02,.39):
        xx=x+dx
        C.box("Parts bin",(xx,1.97,.94),(.357,.215,.32),m["green"],.004)
        for zz in (.875,1.02):
            C.box("Drawer and card surround",(xx,1.853,zz),(.326,.020,.123),m["steel"],.003)
            C.box("Index slip",(xx,1.841,zz+.022),(.085,.001,.021),m["dial"],.0005)
            turned("Parts drawer knob",(xx,1.838,zz-.021),(xx,1.818,zz-.021),.012,m["brass"])
    C.box("Parts cabinet ledge",(x+.02,1.97,.759),(1.16,.30,.039),m["joinery"],.004)
    for xx in (x-.41,x+.42):
        bar("Ledge corbel",(xx,2.088,.570),(xx,1.86,.742),.025,.027,m["steel"])

    # Three shallow crossings have worn through the oil on the leading stave.
    score=surface("Unfinished maple fibres",("83674a","ab8c68"),(.60,.77),height=.00010)
    for i in range(21):
        xx=rng.uniform(-1.3,.83)
        yy=rng.uniform(-.453,-.375)
        ln=rng.uniform(.012,.070)
        line=C.strand("Knife score",[(xx,yy,.76053),(xx+.42*ln,yy+.11*ln,.76054),
                      (xx+ln,yy+.49*ln,.76053)],rng.uniform(.00011,.00029),score)
        line.data.splines[0].points[-1].radius=.12


def thumb_oil(m):
    nt=m.node_tree
    p=nt.nodes["Principled BSDF"]
    pos=nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    uv=vector_op(nt,"SUBTRACT",pos,(.011,.008,-.020))
    uv=vector_op(nt,"MULTIPLY",uv,(44.,72.,48.))
    dist=nt.nodes.new("ShaderNodeVectorMath")
    dist.operation="LENGTH"
    into(nt,uv,dist.inputs[0])
    radius=dist.outputs["Value"]
    ridge=calc(nt,"ADD",calc(nt,"MULTIPLY",radius,105),mapped(nt,noise(nt,pos,128),.2,.8,-2.1,2.1))
    wave=nt.nodes.new("ShaderNodeMath")
    wave.operation="SINE"
    into(nt,ridge,wave.inputs[0])
    ridge=calc(nt,"MULTIPLY",mapped(nt,wave.outputs[0],-.3,.65),mapped(nt,radius,.50,1.10,.65,0))
    dry=p.inputs["Roughness"].links[0].from_socket
    into(nt,mix(nt,ridge,dry,(.16,.16,.16,1)),p.inputs["Roughness"])


def finish_edges(m):
    variants={}
    for mat in (v for v in m.values() if v.get("enamel_with_wear")):
        edge=mat.copy()
        edge.name=mat.name+" • chipped arris"
        nt=edge.node_tree
        p=nt.nodes["Principled BSDF"]
        coord=nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
        chip=mapped(nt,noise(nt,coord,94,2.0,.17),.48,.62,0,.90)
        old=p.inputs["Base Color"].links[0].from_socket
        into(nt,mix(nt,chip,old,C.color("767a73")),p.inputs["Base Color"])
        into(nt,chip,p.inputs["Metallic"])
        variants[mat]=edge
    # Any straight-edged shop stock inherited from the pilot also gets a small chamfer.
    for obj in bpy.context.scene.objects:
        if obj.type!="MESH" or not len(obj.data.materials):
            continue
        bevel=next((mod for mod in obj.modifiers if mod.type=="BEVEL"),None)
        mat=obj.data.materials[0]
        if bevel is None and mat in m.values() and len(obj.data.polygons)<=16:
            soften(obj,.0008,2)
            bevel=obj.modifiers[-2]
        if bevel and mat in variants:
            obj.data.materials.append(variants[mat])
            bevel.material=len(obj.data.materials)-1


def shirt_details(cast):
    """Project placket, pocket welts and buttons onto the fitted shirt in its rest pose.
    New vertices interpolate the shell's three source weights and follow the same armature."""
    from mathutils.geometry import barycentric_transform
    outfit=cast["outfits"]["workshop"]
    mesh=outfit.data
    shirt=next(i for i,mat in enumerate(mesh.materials) if mat.name=="o_henley")
    shirt_verts={v for p in mesh.polygons if p.material_index==shirt for v in p.vertices}
    for i in shirt_verts:
        v=mesh.vertices[i]
        x,y,z=v.co
        if y>=-.035 or not (.99<z<1.44) or abs(x)>.21:
            continue
        folds=0.
        for z0,slope,amplitude in ((1.070,-.16,.0034),(1.139,.14,.0032),(1.245,-.27,.0027)):
            dz=(z-z0-slope*abs(x))/.010
            folds+=amplitude*(1-2*dz*dz)*math.exp(-dz*dz)
        v.co.y-=folds*min(1,abs(x)/.075)
    mesh.update()
    mesh.calc_loop_triangles()
    tris=[tuple(t.vertices) for t in mesh.loop_triangles if t.material_index==shirt]
    coords=[v.co.copy() for v in mesh.vertices]
    tree=BVHTree.FromPolygons(coords,tris,all_triangles=True)
    verts,faces,materials,weights=[],[],[],[]
    def vertex(x,z,offset):
        hit,_,index,_=tree.ray_cast(Vector((x,-.70,z)),Vector((0,1,0)),1.4)
        if hit is None:
            raise ValueError("Pattern piece missed the shirt.")
        ids=tris[index]
        a,b,c=(coords[i] for i in ids)
        bary=barycentric_transform(hit,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
        values={}
        for i,w in zip(ids,bary):
            for group in mesh.vertices[i].groups:
                name=outfit.vertex_groups[group.group].name
                values[name]=values.get(name,0)+w*group.weight
        verts.append((x,hit.y-offset,z))
        weights.append(values)
        return len(verts)-1
    def ribbon(points,width,offset,slot):
        last=None
        for i,(x,z) in enumerate(points):
            prev=Vector(points[max(0,i-1)])
            nxt=Vector(points[min(len(points)-1,i+1)])
            tang=(nxt-prev).normalized()
            across=Vector((-tang.y,tang.x))*(width/2)
            row=[vertex(x+across.x*s,z+across.y*s,offset) for s in (-1,1)]
            if last:
                faces.append((last[0],row[0],row[1],last[1]))
                materials.append(slot)
            last=row
    placket=[(0,1.252+i*.010) for i in range(20)]
    ribbon(placket,.029,.0015,0)
    for x in (-.011,.011):
        for i in range(19):
            z=1.258+.009*i
            ribbon([(x,z),(x,z+.0046)],.0008,.002,1)
    seam=[(.044,1.34),(.063,1.338),(.084,1.336),(.109,1.333),(.131,1.332),
          (.128,1.268),(.122,1.257),(.090,1.248),(.055,1.264),(.044,1.34)]
    ribbon(seam,.0023,.0013,0)
    ribbon(seam[:5],.006,.0015,0)
    for z in (1.276,1.321,1.366,1.411):
        rows=[]
        for r,h in ((.0057,.0015),(.0057,.0035),(.0044,.0041),(.0036,.0030)):
            rows.append([vertex(r*math.cos(math.tau*j/16),z+r*math.sin(math.tau*j/16),h)
                         for j in range(16)])
        for a,b in zip(rows,rows[1:]):
            for j in range(16):
                faces.append((a[j],a[(j+1)%16],b[(j+1)%16],b[j]))
                materials.append(2)
        faces.append(tuple(rows[-1]))
        materials.append(2)
        ribbon([(-.0015,z-.0008),(.0015,z+.0008)],.00085,.0037,1)
    obj=C.mesh("Garment-faced placket, buttons and stitched work pocket",verts,faces,
               surface("Washed henley placket",("4c5658","79817e"),(.65,.87),height=.00018))
    obj.data.materials.append(C.material("Cotton topstitch","928c77",rough=.79))
    obj.data.materials.append(C.material("Corozo workshirt buttons","443c30",rough=.40))
    for poly,slot in zip(obj.data.polygons,materials):
        poly.material_index=slot
    for i,values in enumerate(weights):
        for name,weight in values.items():
            if weight>.00001:
                group=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([i],weight,"REPLACE")
    obj.parent=cast["rig"]
    obj.matrix_parent_inverse=outfit.matrix_parent_inverse.copy()
    obj.matrix_basis=outfit.matrix_basis.copy()
    obj.modifiers.new("Follows shirt skinning","ARMATURE").object=cast["rig"]


def runner(m):
    wheel = group("Pelton runner and shaft nut", (0,0,AXLE))
    # An open annular casting has no radial seam.
    annulus = revolve("Machined carrier", (0, .045, 0), FRONT,
        [(.144,0),(.205,0),(.213,.005),(.213,.032),(.209,.037),(.144,.037)], m["steel"])
    annulus.parent = wheel
    for i in range(6):
        angle = i * math.tau/6
        spoke = C.section("Tapered spider web", [(-.032,.049),(.035,.049),(.023,.171),
                          (.013,.193),(-.015,.193),(-.022,.167)], .018,.053,m["teal"])
        soften(spoke,.006)
        spoke.rotation_euler.y = angle
        spoke.parent = wheel
    for name, profile, mat in [
        ("Wheel boss", [(.027,0),(.090,0),(.092,.011),(.083,.036),(.057,.048),(.027,.048)],"teal"),
        ("Concentric tool marks", [(.032,0),(.059,0),(.059,.009),(.052,.012),
                                   (.050,.010),(.047,.012),(.031,.012)],"polish")]:
        base_y = .011 if mat=="teal" else -.037
        revolve(name,(0,base_y,0), FRONT,profile,m[mat]).parent=wheel
    turned("Keyed shaft end", (0,-.124,0),(0,.175,0), .025, m["silver"]).parent=wheel
    turned("Hex locknut",(0,-.119,0),(0,-.055,0),.039,m["steel"],sides=6).parent=wheel
    revolve("Witness washer",(0,-.050,0),FRONT,[(.025,0),(.049,0),(.051,.002),
            (.050,.006),(.025,.006)],m["silver"]).parent=wheel
    C.box("Torque witness mark",(.012,-.1247,.003),(.023,.0014,.005),m["red"],.0005).parent=wheel

    for i in range(12):
        mount = group("Bucket casting %02d" % (i+1))
        mount.parent = wheel
        mount.rotation_euler.y = i*math.tau/12
        for side in (-1,1):
            verts, faces = [], []
            rows, cols = 14, 12
            for j in range(rows+1):
                u=j/rows
                breadth=.049 + .043*math.sin(math.pi*(.05+.88*u))
                for k in range(cols+1):
                    v=k/cols
                    recess=(math.sin(math.pi*u)*math.sin(math.pi*v))**.76
                    x=-.029-.019*u+.052*v+.086*recess
                    y=side*(.0017+v*breadth)
                    z=.171+.148*u-.026*v*v*(2*u-1)-.013*u**5*(1-v)**3
                    verts.append((x,y,z))
                    if j and k:
                        n=len(verts)-1
                        face=(n-cols-2,n-1,n,n-cols-1)
                        faces.append(face if side==1 else face[::-1])
            scoop=C.mesh("Dished split bucket", verts,faces,m["brass"])
            scoop.parent=mount
            for p in scoop.data.polygons:
                p.use_smooth=True
            wall=scoop.modifiers.new("Cast wall • 3.8 mm","SOLIDIFY")
            wall.thickness, wall.offset = .0038, 0
            soften(scoop,.0009,2)
            lip = [verts[j*(cols+1)+cols] for j in range(rows+1)]
            lip += [verts[rows*(cols+1)+k] for k in range(cols-1,-1,-1)]
            C.strand("Water polished casting lip",lip,.0015,m["polish"]).parent=mount
        cable("Hardened splitter", [(-.029,0,.171),(-.038,0,.236),(-.048,0,.306)],
              .0038,m["polish"]).parent=mount
        shoe=soften(C.section("Captured root lug",[(-.029,.158),(.026,.158),(.034,.186),
                        (.008,.213),(-.029,.206)],-.015,.024,m["brass"]),.002)
        shoe.parent=mount
        fastener("Bucket root bolt",(0,.008,.175),FRONT,.010,m,mount)
    # Integrate a smooth speed ramp. A loaded runner keeps turning through the last frame.
    angles=[.0]
    for f in FRAMES[1:]:
        speed=.037 + 8.7*ease(f-.5,28,68) - .55*ease(f-.5,99,126)
        angles.append(angles[-1]+speed/FPS)
    set_keys(wheel,"rotation_euler",FRAMES,[(0,a,0) for a in angles])
    return wheel, angles


def generator(m):
    for x in (-.82,.92):
        for y in (-.18,.42):
            C.box("Anti-vibration pad",(x,y,.7655),(.10,.09,.010),m["rubber"],.003)
    C.box("Common steel bedplate",(.055,.13,.7895),(1.91,.68,.038),m["steel"],.007)
    for x in (-.80,.90):
        for y in (-.135,.405):
            fastener("Bedplate hold-down",(x,y,.8085),UP,.014,m)
    for x in (-.18,.18):
        C.box("Bearing foot flange",(x,.192,.814),(.070,.088,.011),m["teal"],.002)
        fastener("Bearing foot fixing",(x,.162,.8195),UP,.008,m)
        bar("Bearing pedestal rib", (x,.192,.814),(x*.21,.192,AXLE),.034,.047,m["teal"],.004)
    turned("Runner shaft journal",(0,.076,AXLE),(0,.48,AXLE),.031,m["silver"])
    for y in (.17,.27):
        revolve("Split bearing housing",(0,y+.038,AXLE),FRONT,
                [(.032,0),(.055,0),(.066,.010),(.068,.049),(.064,.061),(.032,.061)],m["teal"])
    C.box("Generator mounting foot",(0,.370,.824),(.37,.175,.031),m["teal"],.005)
    C.box("Dynamo pedestal",(0,.383,.923),(.208,.154,.172),m["teal"],.012)
    revolve("Dynamo jacket",(0,.493,AXLE),FRONT,
            [(.030,0),(.129,0),(.153,.018),(.155,.134),(.147,.169),(.030,.178)],m["teal"])
    for i in range(18):
        a=i*math.tau/18
        x,z=.153*math.cos(a),AXLE+.153*math.sin(a)
        fin=bar("Cast cooling fin",(x,.349,z),(x,.466,z),.010,.010,m["green"])
        fin.rotation_euler.rotate_axis("Z",a)
    for x in (-.143,.143):
        fastener("Dynamo foot bolt",(x,.371,.8395),UP,.012,m)
    C.box("Wiring gland block",(.135,.39,1.232),(.069,.073,.071),m["steel"],.006)
    # The nameplate sits on the actual front flange of the bed, facing the close lens.
    C.box("Etched maker plate",(-.245,-.212,.789),(.277,.003,.031),m["brass"],.001)
    lettering("MERCER HOLLOW   /   No. 02",(-.245,-.2138,.790),.018,m["ink"])
    for x in (-.372,-.118):
        fastener("Nameplate rivet",(x,-.2136,.79),FRONT,.0025,m)
def nozzle_assembly(m):
    swivel = group("Nozzle yoke • elevation and toe-in", PIVOT)
    set_keys(swivel,"rotation_euler",FRAMES,[tuple(aim(f)) for f in FRAMES])
    C.box("Yoke sole",(-.70,-.055,.824),(.173,.181,.031),m["teal"],.007)
    for x in (-.756,-.644):
        fastener("Yoke anchor",(x,-.024,.8395),UP,.010,m)
    for y in (-.159,-.050):
        plate=C.section("Swivel cheek", [(-.745,.839),(-.657,.839),(-.667,1.165),
                        (-.679,1.196),(-.712,1.203),(-.734,1.177)], y-.009,y+.009,m["teal"])
        soften(plate,.004)
    turned("Swivel journal",(-.70,-.189,AXLE),(-.70,-.018,AXLE),.025,m["silver"])
    fastener("Swivel hex pin",(-.70,-.189,AXLE),FRONT,.026,m)
    cable("Fabric reinforced feed hose",[(-2.1,.25,.795),(-1.29,.18,.795),(-1.06,.018,.789),
          (-.934,-.09,.868),(-.836,-.108,1.094),(-.766,-.108,AXLE)],.027,m["rubber"])
    turned("Fixed hose ferrule",(-.814,-.108,1.139),(-.759,-.108,AXLE),.031,m["steel"])
    C.sphere("Ball joint seat",PIVOT,(.074,.052,.044),m["brass"])
    body=revolve("Bored nozzle • bell mouth and land",(0,0,0),RIGHT,
        [(.019,0),(.039,0),(.043,.014),(.038,.039),(.040,.053),(.040,.094),
         (.031,.102),(.030,.170),(.033,.176),(.032,.189),(.017,.276),(.014,.300),
         (.011,.300),(.010,.294),(.016,.216),(.019,.098)],m["polish"])
    body.parent=swivel
    for i in range(22):
        a=math.tau*i/22
        r=.040
        cable("Coupling grip flute",[(.053,r*math.cos(a),r*math.sin(a)),
              (.092,r*math.cos(a+.28),r*math.sin(a+.28))],.0019,m["brass"]).parent=swivel
    cable("Rear control lever",[(.096,.006,.012),(.108,.070,.035),(.109,.284,.073),
          (.109,.401,.086)],.010,m["steel"]).parent=swivel
    grip_profile=[(0,-.072),(.010,-.072),(.015,-.064),(.017,-.030),(.016,.040),
                  (.014,.067),(.009,.072),(0,.072)]
    revolve("Rosewood elevation grip",LEVER,RIGHT,grip_profile,m["grip"]).parent=swivel
    for offset in (-.065,.064):
        turned("Grip ferrule",(LEVER.x+offset-.003,LEVER.y,LEVER.z),
               (LEVER.x+offset+.003,LEVER.y,LEVER.z),.014,m["brass"]).parent=swivel
    # The gauge measures inlet pressure even when the wheel is stalled.
    gx,gy,gz=-.538,.094,1.397
    cable("Copper gauge siphon",[(-.711,-.038,AXLE),(-.692,.065,1.197),(-.547,.096,1.234),
          (gx,gy,1.320)],.007,m["brass"])
    turned("Gauge hex union",(gx,gy,1.306),(gx,gy,1.342),.015,m["brass"],sides=6)
    revolve("Bourdon gauge • spun steel case",(gx,gy+.023,gz),FRONT,
            [(0,0),(.057,0),(.062,.005),(.064,.033),(.063,.040),(.058,.041),
             (.054,.036),(.054,.029),(0,.029)],m["silver"])
    turned("Baked enamel scale",(gx,gy-.007,gz),(gx,gy-.008,gz),.055,m["dial"])
    for i in range(31):
        angle=R(-128+i*256/30)
        r=.049
        line=.008 if i%5==0 else .004
        a=(gx+(r-line)*math.sin(angle),gy-.009,gz+(r-line)*math.cos(angle))
        b=(gx+r*math.sin(angle),gy-.009,gz+r*math.cos(angle))
        bar("Dial graduation",a,b,.0013 if i%5==0 else .0007,.0005,m["ink"],.00015)
    lettering("bar",(gx,gy-.0095,gz-.025),.013,m["ink"])
    needle=group("Inlet pressure movement",(gx,gy-.010,gz))
    bar("Vermilion dial pointer",(0,0,-.012),(0,0,.044),.0024,.0009,m["red"],.00035).parent=needle
    key(needle,"rotation_euler",[(1,(0,.61,0)),(28,(0,.61,0)),(46,(0,.49,0)),
                                (52,(0,.56,0)),(65,(0,.54,0)),(144,(0,.54,0))])
    turned("Gauge pivot",(gx,gy-.010,gz),(gx,gy-.0115,gz),.004,m["steel"])
    turned("Gauge crystal",(gx,gy-.013,gz),(gx,gy-.015,gz),.056,m["glass"])
    return swivel


def catcher(m):
    slide=group("Carriage • guard, drip pan and rear bow")
    set_keys(slide,"location",FRAMES,[(carriage(f),0,0) for f in FRAMES])
    for ri,ro,y0,y1,finish in ((.344,.365,-.094,.112,"teal"),(.335,.378,-.115,-.094,"rim"),
                               (.276,.376,.112,.128,"teal")):
        arc("Sectioned splash scroll",AXLE,ri,ro,-80,94,y0,y1,m["teal"],m[finish]).parent=slide
    for degrees in (-67,-33,2,36,72):
        a=R(degrees)
        fastener("Split-line cap screw",(.354*math.cos(a),-.115,AXLE+.354*math.sin(a)),
                 FRONT,.009,m,slide)
    # Guide bars extend under both shoe positions and end in physical stops.
    for y in (.044,.139):
        turned("Ground guide rod",(.244,y,.838),(.958,y,.838),.013,m["silver"])
        for x in (.241,.961):
            C.box("Guide support",(x,y,.824),(.026,.041,.031),m["teal"],.003)
        shoe=revolve("Linear bronze bushing",(.30,y,.838),RIGHT,
                     [(.013,0),(.022,0),(.023,.010),(.023,.117),(.022,.121),(.013,.121)],m["brass"])
        shoe.parent=slide
    C.box("Saddle bridge",(.361,.09,.870),(.126,.16,.019),m["teal"],.004).parent=slide
    bar("Cast guard foot",(.359,.082,.876),(.347,.082,1.117),.031,.042,m["teal"],.004).parent=slide
    cable("Bent rear pull bow",[(.168,.122,1.451),(.168,.191,1.45),(.112,.308,1.377),
          (.089,.385,1.347),(-.060,.385,1.347)],.009,m["steel"]).parent=slide
    revolve("Catcher grip",PULL,RIGHT,[(0,-.068),(.012,-.068),(.015,-.059),
            (.015,.059),(.012,.068),(0,.068)],m["grip"]).parent=slide

    # The pressed tray is in front of the bucket sweep, below the visible cross section.
    # Its pitches converge on a pierced drain, and the downstand empties into a fixed gutter.
    corners=[(-.072,-.486,.915),(.49,-.481,.907),(.49,-.121,.906),(-.072,-.121,.891)]
    verts=[*corners]
    for q in corners:
        d=(Vector(q)-DRAIN)
        d.z=0
        d.normalize()
        verts.append(tuple(DRAIN+d*.021))
    faces=[(i,(i+1)%4,4+(i+1)%4,4+i) for i in range(4)]
    for x,y,z in corners:
        verts.append((x,y,z+.017))
    faces += [(i,8+i,8+(i+1)%4,(i+1)%4) for i in range(4)]
    pan=C.mesh("Four-way pressed drip tray",verts,faces,m["galv"])
    pan.parent=slide
    wall=pan.modifiers.new("20-gauge sheet","SOLIDIFY")
    wall.thickness=.0011
    soften(pan,.0007,2)
    drain=revolve("Swaged drain spigot",DRAIN,(0,0,-1),
                  [(.014,0),(.021,0),(.019,.009),(.018,.030),(.015,.030)],m["steel"],48)
    drain.parent=slide
    start=Vector((DRAIN.x,DRAIN.y,.813))
    side=Vector((-(SPOUT.y-start.y),SPOUT.x-start.x,0)).normalized()
    verts=[tuple(q+side*w+Vector((0,0,h))) for q in (start-side*.002,SPOUT)
           for w,h in ((-.057,.045),(-.041,.002),(-.034,0),(.034,0),(.041,.002),(.057,.045))]
    channel=C.mesh("Brake-formed return gutter",verts,[(i,i+1,i+7,i+6) for i in range(5)],m["galv"])
    channel.modifiers.new("1.5 mm zinc sheet","SOLIDIFY").thickness=.0015
    soften(channel,.0009,2)
    for sign in (-1,1):
        cable("Rolled gutter edge",[tuple(q+side*sign*.057+Vector((0,0,.045))) for q in (start,SPOUT)],
              .0026,m["silver"])
    for t in (.10,.245):
        q=start.lerp(SPOUT,t)
        C.box("Gutter stand-off",(q.x,q.y,(.7605+q.z-.002)/2),
              (.033,.038,q.z-.002-.7605),m["steel"],.002)
    C.box("Projecting pail shelf",(PAIL.x,-.64,.293),(.49,.46,.034),m["joinery"],.005)
    for x in (.55,.88):
        bar("Shelf angle iron",(x,-.444,.120),(x,-.820,.273),.020,.023,m["steel"])
        C.box("Shelf wall tab",(x,-.470,.149),(.047,.011,.10),m["steel"],.002)
        fastener("Shelf tab fixing",(x,-.476,.168),FRONT,.009,m)
    revolve("Pressed pail • double seamed floor", PAIL, UP,
            [(0,0),(.134,0),(.138,.008),(.139,.021),(.166,.295),(.171,.316),(.170,.327),
             (.166,.328),(.164,.320),(.162,.297),(.135,.025),(.131,.010),(0,.010)],m["galv"],96)
    for z,r in ((.017,.138),(.21,.158),(.321,.169)):
        revolve("Pail bead",PAIL+Vector((0,0,z)),UP,
                [(r-.001,0),(r+.002,0),(r+.003,.002),(r+.002,.004),(r-.001,.004)],m["silver"])
    for sign in (-1,1):
        x=PAIL.x+sign*.162
        turned("Bail eye",(x-sign*.004,PAIL.y,.601),(x+sign*.007,PAIL.y,.601),.014,m["steel"])
    cable("Galvanized wire bail",[(PAIL.x+.167*math.cos(i*math.pi/16),PAIL.y-.135*math.sin(i*math.pi/16),
          .601-.065*math.sin(i*math.pi/16)) for i in range(17)],.0035,m["silver"])
    for offset in (-.061,.044):
        a=(.361+offset,.078,.877)
        b=(.361+offset,-.125,.900)
        bar("Tray saddle strap",a,b,.018,.021,m["steel"],.002).parent=slide
        for j in range(7):
            x=a[0]-.010+j*.003
            cable("MIG fillet scallop",[(x,a[1]-.007,a[2]),(x+.0015,a[1]-.003,a[2]+.002),
                  (x+.001,a[1]+.003,a[2]+.001)],.0014,m["silver"]).parent=slide
    return slide


def pilot(m):
    x,y=.385,.258
    cable("Cloth-covered lamp lead",[(.164,.391,1.222),(.210,.397,1.199),
          (.245,.383,.875),(.290,.352,.819),(x-.043,y,.820)],.006,m["rubber"])
    for x1,y1 in ((.29,.35),(.336,.283)):
        C.box("P-clip", (x1,y1,.819),(.017,.022,.018),m["steel"],.002)
    revolve("Lamp standard",(x,y,.8085),UP,[(0,0),(.071,0),(.073,.006),(.067,.016),
            (.034,.025),(.019,.049),(.015,.395),(.027,.411),(.027,.424),(0,.424)],m["teal"])
    for off in (-.052,.052):
        fastener("Indicator foot screw",(x+off,y,.824),UP,.006,m)
    before_head=set(bpy.data.objects)
    revolve("Glazed porcelain socket",(x,y,1.230),UP,[(0,0),(.031,0),(.038,.008),(.035,.017),
            (.039,.024),(.038,.040),(.032,.049),(0,.049)],m["dial"])
    envelope=revolve("Lamp envelope • inner and outer glass",(x,y,1.274),UP,
            [(.023,0),(.026,.012),(.027,.028),(.041,.059),(.043,.078),(.040,.094),
             (.031,.106),(.014,.113),(0,.115),(0,.114),(.014,.112),(.030,.105),
             (.039,.093),(.042,.078),(.040,.059),(.026,.029),(.025,.012),(.022,0)],m["glass"])
    filament=C.material("Tungsten • under dynamo load","655448",rough=.3,metal=.87)
    p=filament.node_tree.nodes["Principled BSDF"]
    p.inputs["Emission Color"].default_value=C.color("ffbf70")
    levels=[(1,0),(39,0),(47,.22),(53,.78),(58,.65),(68,1),(112,.98),(144,1)]
    key(p.inputs["Emission Strength"],"default_value",[(f,v*42) for f,v in levels])
    opal=m["glass"].copy()
    opal.name="Etched indicator crown • lit by filament"
    op=opal.node_tree.nodes["Principled BSDF"]
    op.inputs["Roughness"].default_value=.32
    op.inputs["Transmission Weight"].default_value=.82
    op.inputs["Emission Color"].default_value=C.color("ffa646")
    key(op.inputs["Emission Strength"],"default_value",[(f,v*2.5) for f,v in levels])
    envelope.data.materials.append(opal)
    for face in envelope.data.polygons:
        if face.center.z>.050:
            face.material_index=1
    for off in (-.012,.012):
        cable("Dumet feedthrough",[(x+off*.40,y,1.275),(x+off,y,1.313),(x+off,y,1.347)],
              .001,m["silver"])
    pts=[(x-.012+.024*i/72,y+.0013*math.sin(i*math.tau/8),
          1.347-.006*math.sin(math.pi*i/72)+.0013*math.cos(i*math.tau/8)) for i in range(73)]
    C.strand("Incandescent coil",pts,.00085,filament)
    light=bpy.data.lights.new("Filament spill","POINT")
    light.color,light.shadow_soft_size=(1,.54,.21),.023
    lamp=bpy.data.objects.new(light.name,light)
    bpy.context.scene.collection.objects.link(lamp)
    lamp.location=(x,y,1.336)
    key(light,"energy",[(f,2.6*v) for f,v in levels])
    for i in range(6):
        a=i*math.tau/6
        cable("Lamp safety cage",[(x+r*math.cos(a),y+r*math.sin(a),z) for r,z in
              ((.044,1.264),(.052,1.289),(.053,1.351),(.043,1.38),(.011,1.399))],.0023,m["steel"])
    for z,r in ((1.280,.050),(1.366,.050)):
        revolve("Cage hoop",(x,y,z),UP,[(r-.0015,0),(r+.0015,0),(r+.0015,.003),
                (r-.0015,.003)],m["brass"])
    for obj in set(bpy.data.objects)-before_head:
        obj.location.z+=.152
    revolve("Threaded indicator riser",(x,y,1.229),UP,
            [(0,0),(.028,0),(.028,.010),(.018,.016),(.016,.136),(.026,.142),
             (.029,.147),(.029,.152),(0,.152)],m["steel"])


def local_bvh(parent):
    """Capture modifier-evaluated surfaces once in the moving assembly's frame."""
    deps=bpy.context.evaluated_depsgraph_get()
    inv=parent.matrix_world.inverted()
    verts,faces=[],[]
    for part in parent.children_recursive:
        if part.type not in {"MESH","CURVE"}:
            continue
        obj=part.evaluated_get(deps)
        mesh=obj.to_mesh()
        mat=inv @ obj.matrix_world
        offset=len(verts)
        verts.extend(mat @ v.co for v in mesh.vertices)
        faces.extend(tuple(offset+i for i in p.vertices) for p in mesh.polygons)
        obj.to_mesh_clear()
    return BVHTree.FromPolygons(verts,faces)


def segment_hit(tree, a, b):
    delta=b-a
    if delta.length < 1e-7:
        return None
    return tree.ray_cast(a,delta.normalized(),delta.length)[0]


def jet_path(frame, wheel_tree, guard_tree, wheel_angle):
    rot=aim(frame).to_quaternion()
    outlet=PIVOT+rot @ Vector((.300,0,0))
    heading=rot @ Vector(RIGHT)
    inverse=Euler((0,-wheel_angle,0)).to_matrix()
    axle=Vector((0,0,AXLE))
    slide=Vector((carriage(frame),0,0))
    # Water leaves at 8 m/s. Test short ballistic segments against actual cup, hub and guard faces.
    def at(s):
        return outlet+heading*s+Vector((0,0,-4.905*(s/8)**2))
    previous=outlet
    for step in range(1,101):
        distance=step*.030
        point=at(distance)
        hub=segment_hit(wheel_tree,inverse @ (previous-axle),inverse @ (point-axle))
        guard=segment_hit(guard_tree,previous-slide,point-slide)
        hits=[]
        if hub is not None:
            hits.append((inverse.transposed() @ hub+axle,"runner"))
        if guard is not None:
            hits.append((guard+slide,"guard"))
        if hits:
            hit,label=min(hits,key=lambda h:(h[0]-previous).length)
            s=distance-.030+.030*(hit-previous).length/(point-previous).length
            return [at(s*i/15) for i in range(15)]+[hit],label
        previous=point
    # A jet crossing a gap in the casting can leave the shot while the operator slews.
    return [at(3*i/15) for i in range(16)],"clear"


def animated_curve(name, paths, radii, material):
    count=len(paths[0])
    obj=C.strand(name,paths[0],1.,material)
    obj.data.bevel_resolution,obj.data.use_fill_caps=4,True
    for i,point in enumerate(obj.data.splines[0].points):
        set_keys(point,"co",FRAMES,[(*path[i],1.) for path in paths])
        set_keys(point,"radius",FRAMES,[max(.000015,row[i]) for row in radii])
    return obj


def water_sheet(name, paths, strengths, phase, mat):
    """Closed, tapered water membrane with a time-varying creased free edge."""
    verts_per_ring=8
    rings=len(paths[0])
    faces=[tuple(reversed(range(verts_per_ring)))]
    for j in range(rings-1):
        for k in range(verts_per_ring):
            a=j*verts_per_ring+k
            b=j*verts_per_ring+(k+1)%verts_per_ring
            faces.append((a,b,b+verts_per_ring,a+verts_per_ring))
    faces.append(tuple(range((rings-1)*verts_per_ring,rings*verts_per_ring)))
    def shape(f):
        path=paths[f-1]
        strength=strengths[f-1]
        vertices=[]
        for j,p in enumerate(path):
            t=j/(rings-1)
            tangent=(path[min(j+1,rings-1)]-path[max(0,j-1)]).normalized()
            # Ribbon width is across the flow, and its fine edge gets a narrow specular line.
            side=tangent.cross(Vector((.15,1,.15))).normalized()
            up=tangent.cross(side).normalized()
            width=(.003*(1-t)+.010*math.sin(math.pi*t)**.8+.00055*t)*strength
            width*=1+.25*math.sin(11*t-.28*f+phase)
            depth=(.0025-.0021*t)*strength
            for k in range(verts_per_ring):
                theta=k*math.tau/verts_per_ring
                corrugation=.17*width*math.cos(theta)**2*math.sin(17*t-.31*f+phase)
                vertices.append(p+side*(width*math.cos(theta))+up*(depth*math.sin(theta)+corrugation))
        return vertices
    obj=C.mesh(name,shape(1),faces,mat)
    for p in obj.data.polygons:
        p.use_smooth=True
    basis=obj.shape_key_add(name="Frame 001")
    basis.interpolation="KEY_LINEAR"
    keys=obj.data.shape_keys
    keys.use_relative=False
    for f in FRAMES[1:]:
        block=obj.shape_key_add(name="Frame %03d"%f,from_mix=False)
        block.interpolation="KEY_LINEAR"
        block.data.foreach_set("co",[n for v in shape(f) for n in v])
    set_keys(keys,"eval_time",(1,END),[basis.frame,block.frame])
    return obj


def flight_speed(f, lateral, phase):
    power=ease(f,32,54)
    return Vector((.12+power*(1.08+lateral*.28)+.05*math.sin(f*.22+phase),
                   -.13-power*(.86-lateral*.21), .035+power*(.23+lateral*.15)))


def landing(a,b,f,tree):
    offset=Vector((carriage(f),0,0))
    hit=segment_hit(tree,a-offset,b-offset)
    if hit is not None:
        return hit+offset
    for level,limits in ((.8085,(-.9,1.01,-.210,.470)),(.7605,(-1.725,1.725,-.460,.524))):
        if b.z<=level<a.z:
            q=a.lerp(b,(a.z-level)/(a.z-b.z))
            if limits[0]<=q.x<=limits[1] and limits[2]<=q.y<=limits[3]:
                return q
    if b.z<.04:
        return b
    return None


def impact_detail(m, jets, landings):
    # Air drawn into the jet breaks its otherwise mirror-smooth edge at impact.
    foam=dielectric("Aerated creek water", "e4f2ee", 1.333, .19)
    foam.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value=.46
    for i in range(9):
        paths,radii=[],[]
        phase=i*2.39996
        for f,path in zip(FRAMES,jets):
            along=(path[-1]-path[-2]).normalized()
            start=path[-1]-along*.004
            t=f*.29+phase
            axis=Vector((.6+.30*math.sin(t),-.31+.35*math.sin(phase),.26+.42*math.cos(t)))
            length=(.019+.029*(.5+.5*math.sin(t+phase)))*(.4+.6*ease(f,32,55))
            thickness=.0013*(.8+.25*math.cos(t))
            points,sizes=[],[]
            for j in range(6):
                k=j/5
                points.append(start+axis*(k*length)+Vector((0,.001*math.sin(3*k+t)*k,-.012*k*k)))
                sizes.append(thickness*(.12+math.sin(math.pi*(.05+.9*k)))*(1-.4*k))
            paths.append(points)
            radii.append(sizes)
        animated_curve("Entrained edge at bucket impact",paths,radii,foam if i%3==0 else m["water"])

    # Satellite crowns follow the traced landing from the bare wood onto the tray.
    for i in range(12):
        paths,radii=[],[]
        a=i*math.tau/12
        for f,contact in zip(FRAMES,landings):
            phase=((f+1.9*i)%8)/8
            radius=(.014+.036*phase)*(1+.23*math.sin(3*a+.09*f))
            fade=math.sin(math.pi*phase)**.7*ease(f,49,64)
            points,sizes=[],[]
            for j in range(7):
                t=j/6
                r=radius*t
                h=(.016+.017*math.sin(a+f*.15)**2)*4*t*(1-t)*fade
                points.append(contact+Vector((r*math.cos(a),r*math.sin(a),.0015+h)))
                sizes.append(.00008+.0017*(1-.73*t)*fade)
            paths.append(points)
            radii.append(sizes)
        animated_curve("Splashdown crown",paths,radii,foam if i%5==0 else m["water"])


def pail_surface(m,level,falls):
    # The waves displace a closed volume, centred on the outlet's actual splash point.
    count,rings=80,23
    form=[(0.,0.)]
    for j in range(1,rings+1):
        for i in range(count):
            a=math.tau*i/count
            form.append((j/rings*math.cos(a),j/rings*math.sin(a)))
    n=len(form)
    def shape(f):
        z=level(f)
        radius=.135+(z-.335)*(.027/.272)-.0013
        hit=falls[f-1][-1]
        verts=[]
        for u,v in form:
            x,y=PAIL.x+radius*u,PAIL.y+radius*v
            d=math.hypot(x-hit.x,y-hit.y)
            arrival=(f-132)/FPS-d/.36
            wave=ease(arrival,-.06,.13)*.0036*math.exp(-d*9)*math.sin(math.tau*arrival/.16)
            meniscus=.0012*max(0,math.hypot(u,v)-.92)/.08
            verts.append((x,y,z+wave+meniscus))
        for i in range(count):
            a=math.tau*i/count
            verts.append((PAIL.x+.133*math.cos(a),PAIL.y+.133*math.sin(a),.321))
        return verts
    faces=[(0,1+i,1+(i+1)%count) for i in range(count)]
    for j in range(rings-1):
        for i in range(count):
            a=1+j*count+i
            b=1+j*count+(i+1)%count
            faces.append((a,a+count,b+count,b))
    for i in range(count):
        a=n-count+i
        b=n-count+(i+1)%count
        faces.append((a,n+i,n+(i+1)%count,b))
    faces.append(tuple(reversed(range(n,n+count))))
    obj=C.mesh("Primed pail • meniscus and concentric impact waves",shape(1),faces,m["water"])
    for face in obj.data.polygons:
        face.use_smooth=True
    basis=obj.shape_key_add(name="Standing surface")
    basis.interpolation="KEY_LINEAR"
    keys=obj.data.shape_keys
    keys.use_relative=False
    times,values=[1,127],[0.,0.]
    for f in range(128,END+1):
        block=obj.shape_key_add(name="Impact %03d"%f,from_mix=False)
        block.interpolation="KEY_LINEAR"
        block.data.foreach_set("co",[n for v in shape(f) for n in v])
        times.append(f)
        values.append(block.frame)
    set_keys(keys,"eval_time",times,values)


def water(m,wheel,angles,slide):
    bpy.context.scene.frame_set(1)
    wheel_tree,guard_tree=local_bvh(wheel),local_bvh(slide)
    jets,labels=zip(*(jet_path(f,wheel_tree,guard_tree,a) for f,a in zip(FRAMES,angles)))
    print("Jet intersections:",{k:labels.count(k) for k in sorted(set(labels))},
          "beat contacts:",[(f,labels[f-1]) for f,_ in STILLS],flush=True)
    if any(labels[f-1]!="runner" for f,_ in STILLS):
        raise ValueError("The jet must strike the runner in all four story stills.")
    jet_radii=[[.0092*(1-.13*i/15+.047*math.sin(i*.79-f*.42)) for i in range(16)] for f in FRAMES]
    animated_curve("Pressurized jet • outlet to first contact",jets,jet_radii,m["water"])
    def source(f):
        t=min(END,max(1,f))-1
        i=int(t)
        return jets[i][-1].lerp(jets[min(END-1,i+1)][-1],t-i),labels[i]

    def release_point(f,age):
        # A cluster of neighbouring cups sheds overlapping droplets. The sheet begins
        # on the current cup, then follows their averaged release over four frames.
        point,_=source(f)
        average=sum((source(f+i)[0] for i in (-2,-1,0,1,2)),Vector())/5
        return point.lerp(average,ease(age,.0,.12))
    def at_age(f,age,scatter,phase):
        p=release_point(f,age)
        return p + flight_speed(f,scatter,phase)*age + Vector((0,0,-4.905*age*age))
    main_landings=[]
    for j,scatter in enumerate((-.23,.44)):
        paths,strengths=[],[]
        for f in FRAMES:
            path=[source(f)[0].copy()]
            for k in range(1,21):
                age=k*.026
                emitted=f-age*FPS
                q=at_age(emitted,age,scatter,j)
                hit=landing(path[-1],q,f,guard_tree)
                path.append(hit if hit is not None else q)
                if hit is not None:
                    break
            if j==0:
                main_landings.append(path[-1].copy())
            breakup=(.56 if j==0 else .40)+.06*math.sin(f*.24+j)
            # The thin fan breaks into pitched ligaments and isolated drops before landing.
            n=max(3,min(len(path),round(1+breakup*(len(path)-1))))
            path=path[:n]
            # Respace the truncated flight to keep all membrane cross sections distinct.
            distances=[0.]
            for a,b in zip(path,path[1:]):
                distances.append(distances[-1]+(b-a).length)
            samples=[]
            ix=1
            for k in range(17):
                s=distances[-1]*k/16
                while ix<len(path)-1 and distances[ix]<s:
                    ix+=1
                samples.append(path[ix-1].lerp(path[ix],(s-distances[ix-1])/max(1e-7,distances[ix]-distances[ix-1])))
            paths.append(samples)
            strengths.append((.12+.88*ease(f,36,58))*(1 if source(f)[1]=="runner" else .025))
        water_sheet("Split spent-water sheet",paths,strengths,j*2.,m["water"])
    print("Spent water landing at 92 and 140:",[tuple(round(n,3) for n in main_landings[f-1])
                                               for f in (92,140)],flush=True)
    # Each drop has a birth position and a fixed launch velocity. At impact it vanishes
    # before the next birth, so motion blur cannot draw a backwards streak across the set.
    drop_mesh=None
    for i in range(82):
        if drop_mesh is None:
            drop=C.sphere("Thrown water bead",(0,0,0),(1,1,1),m["water"])
            drop_mesh=drop.data
        else:
            drop=bpy.data.objects.new("Thrown water bead",drop_mesh)
            bpy.context.scene.collection.objects.link(drop)
        scatter=rng.uniform(-1.,1.)
        cadence=rng.randrange(11,19)
        birth=1-rng.randrange(cadence)-cadence
        radius=rng.uniform(.0018,.0045)
        positions,scales,rotations=[],[],[]
        for f in FRAMES:
            if f==1 or f-birth>=cadence:
                birth += ((f-birth)//cadence)*cadence
                start,label=source(birth)
                velocity=flight_speed(birth,scatter,i)+Vector((rng.uniform(-.19,.26),rng.uniform(-.20,.12),rng.uniform(-.13,.38)))
                previous=start.copy()
                stopped=(label!="runner")
            age=(f-birth)/FPS
            q=start+velocity*age+Vector((0,0,-4.905*age**2))
            hit=landing(previous,q,f,guard_tree) if not stopped else None
            if hit is not None:
                stopped=True
            if stopped:
                q=hit if hit is not None else previous
            fade=0 if stopped else min(1.,(f-birth)*1.5,max(0,cadence-1-(f-birth)))
            rad=radius*fade*(.32+.68*ease(birth,29,51))
            positions.append(tuple(q))
            scales.append((rad,rad,rad*(1.35+1.35*min(1,age*3))))
            rotations.append(tuple((velocity+Vector((0,0,-9.81*age))).to_track_quat("Z","Y").to_euler()))
            previous=q.copy()
        set_keys(drop,"location",FRAMES,positions)
        set_keys(drop,"rotation_euler",FRAMES,rotations)
        set_keys(drop,"scale",FRAMES,scales)

    impact_detail(m,jets,main_landings)
    # Thin beads collect on the actual bench nosing, with a lingering drip after capture.
    for i,xx in enumerate((.302,.355)):
        paths,strengths=[],[]
        for f in FRAMES:
            volume=ease(f,55+4*i,81+4*i)*(1-ease(f,111+4*i,136+4*i))
            length=.03+volume*(.19+.026*math.sin(f*.29+i))
            path=[]
            for j in range(13):
                t=j/12
                path.append(Vector((xx+.004*math.sin(f*.24-5*t+i)*t,
                                    -.448-.061*t,.761-.006*t-length*t*t)))
            paths.append(path)
            strengths.append(.001+volume*(.54 if i==0 else .39))
        water_sheet("Overflow breaking over the bench nosing",paths,strengths,i+1.4,m["water"])
    for i in range(5):
        x=.247+i*.039
        path=[(x,-.446,.761),(x+.003,-.456,.761),(x+.004,-.461,.755),
              (x+.005,-.461,.729),(x+.006,-.461,.681),(x+.007,-.463,.66)]
        stroke=cable("Edge runnel",path,.0027*(1+.13*(i%3)),m["water"])
        for j,p in enumerate(stroke.data.splines[0].bezier_points):
            key(p,"radius",[(1,.006),(54+2*i+j,.006),(66+2*i+2*j,.8),
                            (109+2*i,.94),(132+2*i+j,.06 if j<2 else .006)])
    def level(f):
        return .538+.030*ease(f,128,150)
    # A continuous wet path with a travelling leading edge. Water takes time to reach the pail.
    tray_paths,channel_paths,fall_paths=[],[],[]
    tray_r,channel_r,fall_r=[],[],[]
    for f in FRAMES:
        shift=Vector((carriage(f),0,0))
        drain=DRAIN+shift
        touch=main_landings[f-1].copy()
        q=touch.lerp(drain,.54)+Vector((0,0,.002))
        tray_paths.append([touch,q,drain+Vector((0,0,.002)),drain-Vector((0,0,.032))])
        tray_r.append([.0035*ease(f,116+j,123+j) for j in range(4)])
        start=Vector((DRAIN.x,DRAIN.y,.8175))
        channel_paths.append([start.lerp(SPOUT+Vector((0,0,.003)),i/10) for i in range(11)])
        channel_r.append([(.0085+.001*math.sin(f*.31-i))*
                          ease(f,119+i*.54,124+i*.54) for i in range(11)])
        pts=[]
        for i in range(12):
            # Outlet velocity and gravity determine the arc; clip at the moving water surface.
            t=i/11*math.sqrt(2*(SPOUT.z-level(f))/9.81)
            pts.append(SPOUT+Vector((.28*t,-.14*t,.002-4.905*t*t)))
        fall_paths.append(pts)
        fall_r.append([(.009-.003*i/11)*(1+.07*math.sin(i*.9-f*.28))*
                       ease(f,125+i*.50,129+i*.50) for i in range(12)])
    animated_curve("Film converging into drain",tray_paths,tray_r,m["water"])
    animated_curve("Tailwater • galvanized channel",channel_paths,channel_r,m["water"])
    animated_curve("Free outfall into pail",fall_paths,fall_r,m["water"])
    pail_surface(m,level,fall_paths)


def character_assets(actor,ctx):
    source=actor.BASE_GLTF
    gltf=json.loads(source.read_text())
    fixes={"T_Hair_1_Normal_png.png":"T_Hair_1_Normal.png",
           "T_Eye_Normal_png.png":"T_Eye_Normal.png"}
    # Stage only the glTF manifest. Every external image and buffer still comes from the kit.
    with tempfile.TemporaryDirectory(prefix=".gltf-",dir=OUT) as tmp:
        manifest=Path(tmp)/source.name
        for entry in [*gltf["images"],*gltf["buffers"]]:
            uri=unquote(entry["uri"])
            path=source.parent/fixes.get(uri,uri)
            if not path.is_file():
                raise FileNotFoundError(path)
            entry["uri"]=quote(os.path.relpath(path,manifest.parent),safe="/")
        manifest.write_text(json.dumps(gltf))
        actor.BASE_GLTF=manifest
        try:
            cast=actor.build_bolts(ctx,json.loads((PAGE/"character.json").read_text())["bolts"])
        finally:
            actor.BASE_GLTF=source
    for name,filename in (("bolts_q_brows","T_Hair_1_Normal.png"),("bolts_q_hair","T_Hair_1_Normal.png"),
                          ("bolts_q_beard","T_Hair_1_Normal.png"),("bolts_q_eyes","T_Eye_Normal.png")):
        nt=bpy.data.materials[name].node_tree
        shader=next(n for n in nt.nodes if n.type=="BSDF_PRINCIPLED")
        normal=shader.inputs["Normal"].links[0].from_node
        tex=normal.inputs["Color"].links[0].from_node
        # Bind the canonical on-disk PNG, even if another import packed an identically named map.
        tex.image=bpy.data.images.load(str(source.parent/filename),check_existing=True)
        tex.image.colorspace_settings.name="Non-Color"
        if normal.type!="NORMAL_MAP" or not all(tex.image.size):
            raise ValueError("Broken tangent-space input: "+name)
        print("Verified normal:",name,filename,tuple(tex.image.size),flush=True)
    return cast


def character_materials(cast):
    visible=[cast["body"],cast["outfits"]["workshop"],*cast["sig"].values(),
             *cast["hair"].values(),bpy.data.objects["bolts_eyes"],bpy.data.objects["bolts_brows"]]
    for m in {m for obj in visible for m in obj.data.materials if m and m.use_nodes}:
        nt=m.node_tree
        p=next((n for n in nt.nodes if n.type=="BSDF_PRINCIPLED"),None)
        if p is None:
            continue
        # The source shorts apply a distance-fog mix to the character. Light the opaque
        # and alpha-tested surfaces in the same Cycles world as the physical set.
        out=next(n for n in nt.nodes if n.type=="OUTPUT_MATERIAL" and n.is_active_output)
        into(nt,p.outputs[0],out.inputs["Surface"])
        if m.name=="bolts_q_skin":
            p.inputs["Subsurface Weight"].default_value=.23
            p.inputs["Subsurface Radius"].default_value=(1,.44,.23)
            p.inputs["Subsurface Scale"].default_value=.0016
            p.inputs["IOR"].default_value=1.40
            continue
        fabric=any(s in m.name.lower() for s in ("henley","pants","bandana","cap","denim"))
        leather=any(s in m.name.lower() for s in ("pouch","boot","belt"))
        if fabric or leather:
            uv=nt.nodes.new("ShaderNodeTexCoord").outputs["UV"]
            grain=noise(nt,uv,290 if fabric else 145,2)
            if m.name=="o_henley":
                base=p.inputs["Base Color"]
                if base.is_linked:
                    into(nt,mix(nt,.68,base.links[0].from_socket,C.color("656f71"),"MULTIPLY"),base)
            if fabric:
                # Crossed warp and weft at grazing angles, with a less regular fleck between them.
                strands=[]
                for direction in ("X","Y"):
                    w=nt.nodes.new("ShaderNodeTexWave")
                    w.bands_direction=direction
                    w.inputs["Scale"].default_value=290 if direction=="X" else 365
                    w.inputs["Distortion"].default_value=.55
                    into(nt,uv,w.inputs["Vector"])
                    strands.append(w.outputs["Fac"])
                grain=mix(nt,.75,grain,calc(nt,"MULTIPLY",*strands))
                p.inputs["Sheen Weight"].default_value=.25
            bump=nt.nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value=.19
            bump.inputs["Distance"].default_value=.00025 if fabric else .00037
            into(nt,grain,bump.inputs["Height"])
            into(nt,bump.outputs[0],p.inputs["Normal"])
            into(nt,mapped(nt,grain,0,1,.64 if fabric else .36,.87 if fabric else .60),p.inputs["Roughness"])


def grip_frame(side,frame):
    if side=="r":
        q=aim(frame).to_quaternion()
        return PIVOT+q @ LEVER,q,.016
    return PULL+Vector((carriage(frame),0,0)),Euler((0,0,0)).to_quaternion(),.015


def bolts(scene):
    import characters_s9 as actor
    from mh_blender import L
    if actor.PROP_NAME!="s11":
        raise RuntimeError("Select the approved s11 Bolts profile with MH_BOLTS_PROP=s11.")
    cast=character_assets(actor,L.Ctx(scene,END,FPS,[],0.))
    outfit=cast["outfits"]["workshop"]
    outfit.hide_render=False
    cast["masks"]["workshop"].show_render=cast["masks"]["workshop"].show_viewport=True
    shirt_details(cast)
    character_materials(cast)
    rig,body=cast["rig"],cast["body"]
    rig.rotation_euler.z=R(8)
    rig.location=(-.174,.702,-min(v.co.z for v in outfit.data.vertices)*rig.scale.z)
    bpy.context.view_layer.update()
    basis=cast["bake"].__self__
    inv=rig.matrix_world.inverted()
    local_rot=inv.to_quaternion()
    landmarks={}
    # Pick a real underside vertex at the middle of each palm, rigidly bound to the metacarpus.
    for side in ("r","l"):
        hand="hand_"+side
        group_index=body.vertex_groups[hand].index
        center=basis.sk.head(hand).lerp(basis.sk.head("middle_01_"+side),.72)+Vector((0,0,-.018))
        candidates=[v for v in body.data.vertices if any(g.group==group_index and g.weight>.95 for g in v.groups)]
        v=min(candidates,key=lambda v:(v.co-center).length_squared)
        landmarks[side]=(v.index,basis.sk.rest[hand].inverted() @ v.co)
    ids=body.data.attributes.new("sme_source_vertex","INT","POINT")
    ids.data.foreach_set("value",list(range(len(ids.data))))

    class BenchPerformance(actor.Animator):
        def frame_basis(self,timeline,f,fps):
            rots,_=self.pose("idle",(f-1)/fps)
            pelvis=Vector((0,0,0))
            rots["pelvis"]=self.sk.restq["pelvis"].copy()
            lift=ease(f,7,25)*(1-ease(f,54,76))
            pull=ease(f,73,94)*(1-ease(f,131,144))
            self._spine_bend(rots,.10+.27*lift+.25*pull,.10*pull-.065*lift)
            self._head_turn(rots,.34+.18*lift+.14*pull,
                            -.40*(1-ease(f,44,64))+.44*ease(f,68,89)-.32*ease(f,115,139))
            for side,weight in (("r",lift),("l",pull)):
                if weight<=0:
                    continue
                center,q,radius=grip_frame(side,f)
                normal=q @ Vector(UP)
                fingers=q @ Vector((-.14 if side=="r" else .14,-1,-.16))
                orientation=self._hand_q(side,local_rot @ fingers,local_rot @ -normal)
                approach=.047*math.sin(math.pi*weight)
                wrist=inv @ (center+normal*(radius+approach))-orientation @ landmarks[side][1]
                over=dict(rots)
                self._arm(over,pelvis,side,wrist,Vector((-.74 if side=="r" else .74,.12,-1)),orientation)
                curl=ease(f,16,27) if side=="r" else ease(f,83,97)
                self._fingers(over,side,orientation,{name:(.93*curl,1.15*curl,.67*curl)
                              for name in actor.FINGERS},thumb=(.43*curl,.64*curl,.42*curl))
                rots=self._mix(rots,over,weight)
            return self.sk.basis(self.sk.fk(rots,pelvis))
    action=BenchPerformance(rig,basis.sk,basis.clips,basis.m)
    action.bake([(1,"idle")],1,END,FPS)

    # Check the evaluated skin, including blend weights, against the moving cylinders.
    scene.frame_set(1)
    deps=bpy.context.evaluated_depsgraph_get()
    evaluated=body.evaluated_get(deps)
    ids=evaluated.data.attributes["sme_source_vertex"].data
    index={side:next(i for i,item in enumerate(ids) if item.value==landmarks[side][0]) for side in landmarks}
    for side,held in (("r",range(26,55)),("l",range(98,129))):
        errors=[]
        for f in held:
            scene.frame_set(f)
            obj=body.evaluated_get(deps)
            skin=obj.matrix_world @ obj.data.vertices[index[side]].co
            center,q,radius=grip_frame(side,f)
            point=q.inverted() @ (skin-center)
            errors.append(max(abs(math.hypot(point.y,point.z)-radius),max(0,abs(point.x)-.061)))
        print("Evaluated palm/grip maximum error (m):",side,round(max(errors),5),flush=True)
        if max(errors)>.005:
            raise ValueError("Unreachable grip or visible palm gap on "+side)
    foot_heights=[]
    for f in (1,28,72,100,123,144):
        scene.frame_set(f)
        boot=outfit.evaluated_get(deps)
        foot_heights.append(min((boot.matrix_world @ v.co).z for v in boot.data.vertices))
    print("Boot sole levels (m):",[round(z,5) for z in foot_heights],flush=True)
    if max(abs(z) for z in foot_heights)>.005:
        raise ValueError("Boots missed the floor.")


def lighting(scene):
    world=bpy.data.worlds.new("Open bay • high dynamic range daylight")
    world.use_nodes=True
    scene.world=world
    nt=world.node_tree
    hdr=next((p for root in C.ASSET_ROOTS for p in sorted((root/"hdri").glob("*.hdr"))),None)
    if hdr:
        env=nt.nodes.new("ShaderNodeTexEnvironment")
        env.image=bpy.data.images.load(str(hdr),check_existing=True)
        rot=nt.nodes.new("ShaderNodeMapping")
        rot.inputs["Rotation"].default_value.z=R(108)
        into(nt,nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"],rot.inputs["Vector"])
        into(nt,rot.outputs[0],env.inputs["Vector"])
    else:
        env=nt.nodes.new("ShaderNodeTexSky")
    into(nt,env.outputs[0],nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value=.16
    def area(name,at,aim_at,power,tint,width,height):
        light=bpy.data.lights.new(name,"AREA")
        light.shape,light.size,light.size_y="RECTANGLE",width,height
        light.energy,light.color=power,tint
        obj=bpy.data.objects.new(name,light)
        scene.collection.objects.link(obj)
        obj.location=at
        obj.rotation_euler=(Vector(aim_at)-Vector(at)).to_track_quat("-Z","Y").to_euler()
    area("Open bay • soft daylight",(-1.83,-.96,2.42),(0,0,1.05),229,(1,.80,.58),1.24,.94)
    area("North skylight • bounced fill",(1.28,-.86,2.03),(-.12,0,1.04),36,(.53,.73,1),1.38,1.72)
    area("Sunlit jamb • warm edge",(.88,1.26,2.13),(0,0,1.13),180,(1,.72,.46),.64,1.10)
    area("Window strip in wet metal",(-1.01,.51,1.99),(-.08,0,1.18),57,(.69,.85,1),.24,1.24)
    sun=bpy.data.lights.new("Late sun through the rear sash","SUN")
    sun.energy,sun.angle,sun.color=2.0,R(5.5),(1,.88,.71)
    sunlight=bpy.data.objects.new(sun.name,sun)
    scene.collection.objects.link(sunlight)
    sunlight.rotation_euler=Vector((.37,-1,-.43)).to_track_quat("-Z","Y").to_euler()
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Base Contrast"
    scene.view_settings.exposure=-.68


def camera(scene):
    focus=group("Optical focus • action on the bench")
    data=bpy.data.cameras.new("Mercer Hollow • 44 mm")
    cam=bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(cam)
    scene.camera=cam
    data.type,data.lens,data.sensor_fit,data.sensor_height="PERSP",44.,"VERTICAL",32.
    data.clip_start,data.clip_end=.035,80.
    data.dof.use_dof=True
    data.dof.focus_object=focus
    data.dof.aperture_fstop=3.2
    data.dof.aperture_blades=9
    look=group("Camera sightline")
    constraint=cam.constraints.new("TRACK_TO")
    constraint.target,constraint.track_axis,constraint.up_axis=look,"TRACK_NEGATIVE_Z","UP_Y"
    # Dolly towards the jet, track with the spill, then lower and widen for the outfall.
    shots=[
        (1,(-.99,-3.39,1.78),(-.095,.040,1.145),(-.13,-.035,1.21)),
        (26,(-.94,-3.18,1.73),(-.174,.040,1.180),(-.35,-.065,1.235)),
        (54,(-.80,-3.02,1.67),(-.128,.040,1.210),(-.10,-.033,1.398)),
        (75,(-.46,-2.25,1.59),(.008,.010,1.205),(.03,-.045,1.30)),
        (99,(-.02,-3.02,2.01),(.162,-.040,1.046),(.29,-.36,.83)),
        (119,(.38,-3.22,1.84),(.219,-.037,1.026),(.17,-.13,1.11)),
        (144,(.72,-3.70,1.94),(.224,-.09,.973),(.28,-.30,.94))]
    for obj,i in ((cam,1),(look,2),(focus,3)):
        set_keys(obj,"location",[s[0] for s in shots],[s[i] for s in shots],interp="BEZIER")
    anchors=[SPOUT,*(PAIL+Vector((dx,dy,dz)) for dx,dy,dz in
                      ((-.171,0,.324),(.171,0,.324),(0,-.171,.324),(0,.171,.324),(0,0,0)))]
    margins=[]
    for f in range(136,145):
        scene.frame_set(f)
        for point in anchors:
            u,v,depth=world_to_camera_view(scene,cam,point)
            if depth<=0 or not (.012<u<.988 and .012<v<.988):
                raise ValueError(f"Return pail or outlet fell outside frame {f}: {u:.3f}, {v:.3f}")
            margins.append(min(u,1-u,v,1-v))
    print("Minimum return shot edge margin:",round(min(margins),3),flush=True)


def render(scene,preview):
    out=OUT/"preview" if preview else OUT
    out.mkdir(parents=True,exist_ok=True)
    ff=shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("The hook encoder requires ffmpeg with libx264 on PATH.")
    scene.render.resolution_percentage=100
    scene.render.resolution_x,scene.render.resolution_y=(432,768) if preview else (1080,1920)
    scene.cycles.samples=20 if preview else 192
    scene.cycles.adaptive_threshold=.12 if preview else .015
    scene.render.use_motion_blur=False
    for f,name in STILLS:
        scene.frame_set(f)
        scene.render.filepath=str(out/(name+".png"))
        bpy.ops.render.render(write_still=True)
    scene.render.resolution_x,scene.render.resolution_y=(216,384) if preview else (1080,1920)
    scene.cycles.samples=8 if preview else 64
    scene.cycles.adaptive_threshold=.13 if preview else .032
    scene.render.use_motion_blur=True
    scene.render.motion_blur_shutter=.45
    with tempfile.TemporaryDirectory(prefix=".hook-",dir=out) as tmp:
        folder=Path(tmp)
        scene.render.filepath=str(folder/"frame_")
        bpy.ops.render.render(animation=True)
        movie=folder/"hook.mp4"
        subprocess.run([ff,"-v","error","-framerate",str(FPS),"-start_number","1",
                        "-i",str(folder/"frame_%04d.png"),"-frames:v",str(END),"-an",
                        "-c:v","libx264","-pix_fmt","yuv420p","-vf","scale=out_color_matrix=bt709",
                        "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709",
                        "-crf","16","-movflags","+faststart",str(movie)],check=True)
        movie.replace(out/"hook.mp4")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OUT.mkdir(parents=True,exist_ok=True)
    scene=C.render_settings(width=1080,samples=192,frames=END)
    chosen=device(scene)
    print("Cycles device:",chosen,flush=True)
    scene.render.fps=FPS
    scene.unit_settings.system="METRIC"
    scene.cycles.max_bounces=8
    scene.cycles.diffuse_bounces=3
    scene.cycles.glossy_bounces=4
    scene.cycles.transmission_bounces=6
    scene.cycles.transparent_max_bounces=8
    scene.cycles.sample_clamp_indirect=5.
    lighting(scene)
    m=materials()
    m["polish"]=surface("Water-polished bronze",("a87947","c39860"),(.17,.32),.95,
                        grain=(1,1,6),height=.00007)
    m["grip"]=surface("Oil-rubbed rosewood",("48251a","905137"),(.21,.43),
                      grain=(10,10,.5),scale=5,height=.00016,coat=.32)
    workshop(m)
    workshop_details(m)
    thumb_oil(m["grip"])
    wheel,angles=runner(m)
    generator(m)
    nozzle_assembly(m)
    slide=catcher(m)
    pilot(m)
    finish_edges(m)
    water(m,wheel,angles,slide)
    bolts(scene)
    camera(scene)
    scene.frame_start,scene.frame_end,scene.render.fps=1,END,FPS
    render(scene,args.preview)


if __name__=="__main__":
    main()

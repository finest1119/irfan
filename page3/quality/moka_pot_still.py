"""Everyday Decoded. A single exposure of a moka pot during extraction.

Run with Blender in background mode. Dimensions below are in millimeters.
The meshes, light sizes and camera positions passed to Blender are in meters.
"""
import argparse
import math
from pathlib import Path
import random
import subprocess
import sys
import threading
import time

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "cutaway"))
import cutlib as C


OUT = ROOT / "page3" / "_qc" / "quality-test-moka-pot"
MM = 0.001
# The front wedge is absent. The longer left flank keeps several exterior facets.
SECTION = (-16, 232)
FULL = (0, 360)
TAU = math.tau


def meters(xyz):
    return tuple(v * MM for v in xyz)


def bevel(obj, width, segments=3, angle=24):
    if width:
        mod = obj.modifiers.new("Machined edge radius", 'BEVEL')
        mod.width = width * MM
        mod.segments = segments
        mod.limit_method = 'ANGLE'
        mod.angle_limit = math.radians(angle)
        mod.harden_normals = True
        normals = obj.modifiers.new("Face weighted normals", 'WEIGHTED_NORMAL')
        normals.keep_sharp = True
    return obj


def box(name, center, size, mat, edge=0):
    return bevel(C.box(name, meters(center), meters(size), mat), edge)


def outline(name, xz, near, far, mat, edge):
    points = [(x * MM, z * MM) for x, z in xz]
    return bevel(C.section(name, points, near * MM, far * MM, mat), edge, 4)


def noise(nodes, link, vector, frequency, detail=2):
    node = nodes.new("ShaderNodeTexNoise")
    node.inputs["Scale"].default_value = frequency
    node.inputs["Detail"].default_value = detail
    link(vector, node.inputs["Vector"])
    return node.outputs["Fac"]


def ramp(nodes, link, source, lo, hi):
    node = nodes.new("ShaderNodeValToRGB")
    for element, at, value in zip(node.color_ramp.elements, (.23, .77), (lo, hi)):
        element.position = at
        element.color = C.color(value) if isinstance(value, str) else (value, value, value, 1)
    link(source, node.inputs[0])
    return node.outputs[0]


def finish(name, colors, roughness, *, metal=0, grain=0.012, direction=(1, 1, 1),
           scale=260, micro=3100, coat=0, anisotropy=0):
    mat = C.material(name, colors[0], metal=metal)
    nodes, link = mat.node_tree.nodes, mat.node_tree.links.new
    bsdf = nodes.get("Principled BSDF")
    coords = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    broad = noise(nodes, link, coords, scale, 3)
    link(ramp(nodes, link, broad, *colors), bsdf.inputs["Base Color"])
    mapping = nodes.new("ShaderNodeVectorMath")
    mapping.operation = 'MULTIPLY'
    mapping.inputs[1].default_value = direction
    link(coords, mapping.inputs[0])
    fine = noise(nodes, link, mapping.outputs[0], micro)
    mix = nodes.new("ShaderNodeMixRGB")
    mix.inputs[0].default_value = .43
    link(broad, mix.inputs[1])
    link(fine, mix.inputs[2])
    link(ramp(nodes, link, mix.outputs[0], *roughness), bsdf.inputs["Roughness"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .22
    bump.inputs["Distance"].default_value = grain * MM
    link(fine, bump.inputs["Height"])
    link(bump.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = .22
    bsdf.inputs["Anisotropic"].default_value = anisotropy
    return mat


def liquid(name, tint, roughness, transmission, ior, absorption, density):
    mat = C.material(name, tint, rough=roughness)
    nodes, link = mat.node_tree.nodes, mat.node_tree.links.new
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Transmission Weight"].default_value = transmission
    volume = nodes.new("ShaderNodeVolumeAbsorption")
    volume.inputs["Color"].default_value = C.color(absorption)
    volume.inputs["Density"].default_value = density
    link(volume.outputs[0], nodes.get("Material Output").inputs["Volume"])
    return mat


def materials(revised):
    m = {
        "alloy": finish("Spun and lightly scuffed aluminum", ("a9ada7", "c9cec7"), (.23, .39),
                        metal=.96, direction=(.65, .65, 11), anisotropy=.34),
        "cast": finish("Seasoned cast aluminum interior", ("8f9084", "c3c1af"), (.32, .49),
                       metal=.83, grain=.034, scale=130, micro=2200),
        "sawn": finish("Fine tool marks on section faces", ("c5c6bb", "e2dfca"), (.24, .38),
                       metal=.88, direction=(1.4, 1.4, 16), grain=.012),
        "enamel": finish("Deep celadon stove enamel", ("205c57", "32796e"), (.22, .33),
                         metal=.36, coat=.34, grain=.012, scale=140),
        "steel": finish("Drawn stainless steel", ("9daaa8", "d9ddd4"), (.18, .33),
                        metal=.94, direction=(5, 5, .45), anisotropy=.37),
        "brass": finish("Warm brass with aged recesses", ("84612d", "dbad5f"), (.24, .41),
                        metal=.9, grain=.02, scale=210),
        "seal": finish("Compressed russet silicone gasket", ("803a28", "ad6343"), (.47, .62)),
        "black": finish("Molded graphite phenolic", ("191e1c", "353732"), (.26, .43),
                        grain=.025, scale=200, coat=.15),
        "iron": finish("Graphite stove iron", ("262b29", "414640"), (.54, .74),
                       metal=.57, grain=.075, scale=85, micro=1800),
        "burner": finish("Heat darkened burner", ("302b28", "756350"), (.33, .59),
                         metal=.79, direction=(.8, .8, 4)),
        "water": liquid("Boiler water", "d0efec", .058, .94, 1.333, "75c2bc", 7),
        "brew": liquid("Brewed coffee in the collector", "6b3012", .105, .67, 1.335,
                       "a75c25", 62),
        "thread": liquid("Backlit thin coffee stream", "b65c25", .095, .66, 1.335,
                         "bd671f", 40),
        "grounds": finish("Wet bed of ground coffee", ("23120c", "754125"), (.34, .65),
                          grain=.13, scale=1800, micro=4600),
    }
    if revised:
        m["black"] = finish("Bakelite | worn satin grip", ("151712","272820"), (.39,.54),
                            grain=.036, scale=245, micro=2300, coat=.05)
        m["black"].node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value = .28
        m["enamel"] = finish("Enamel | kiln-fired deep green", ("164f49","205a50"),
                             (.24,.34), metal=.30, grain=.023, scale=100, coat=.25)
        m["grounds"] = finish("Coffee bed | water-darkened particles", ("180c08","422518"),
                              (.40,.68), grain=.18, scale=1600, micro=4150)
        m["brew"] = liquid("Coffee | amber transmission through dark brew", "995724", .07,
                           .93, 1.335, "9d5025", 110)
        m["thread"] = liquid("Coffee | thin wet film in window light", "a76833", .065,
                             .90, 1.335, "b06830", 75)
        m["water"] = liquid("Water | clear cut surface", "dbf3f0", .042,
                            .972, 1.333, "8bc5c0", 10)
        sawn = finish("Section | lightly dressed tool marks", ("b5b9ae","c9cbbd"),
                      (.29,.39),metal=.91,grain=.019,direction=(1.5,1.5,3),anisotropy=.24)
        nodes, link = sawn.node_tree.nodes, sawn.node_tree.links.new
        point = nodes.new("ShaderNodeNewGeometry").outputs["Position"]
        travel = nodes.new("ShaderNodeVectorMath")
        travel.operation = 'DOT_PRODUCT'
        travel.inputs[1].default_value = (.64,.32,.92)
        link(point,travel.inputs[0])
        phase = nodes.new("ShaderNodeMath")
        phase.operation = 'MULTIPLY_ADD'
        phase.inputs[1].default_value = 20100
        link(travel.outputs["Value"],phase.inputs[0])
        link(noise(nodes,link,point,290,3),phase.inputs[2])
        groove = nodes.new("ShaderNodeMath")
        groove.operation = 'SINE'
        link(phase.outputs[0],groove.inputs[0])
        roughness = nodes.get("Principled BSDF").inputs["Roughness"]
        marks = nodes.new("ShaderNodeMath")
        marks.operation = 'MULTIPLY_ADD'
        marks.inputs[1].default_value = .043
        link(groove.outputs[0],marks.inputs[0])
        link(roughness.links[0].from_socket,marks.inputs[2])
        link(marks.outputs[0],roughness)
        m["sawn"] = sawn
        # A broken, warm heat tint is strongest on the first few millimeters of the boiler.
        patina = m["alloy"].copy()
        patina.name = "Boiler | aluminum with heat patina at the foot"
        nodes, link = patina.node_tree.nodes, patina.node_tree.links.new
        point = nodes.new("ShaderNodeNewGeometry").outputs["Position"]
        xyz = nodes.new("ShaderNodeSeparateXYZ")
        link(point, xyz.inputs[0])
        height = nodes.new("ShaderNodeMapRange")
        height.inputs["From Min"].default_value = .001
        height.inputs["From Max"].default_value = .023
        height.inputs["To Min"].default_value = .49
        height.inputs["To Max"].default_value = 0
        link(xyz.outputs["Z"],height.inputs["Value"])
        weight = nodes.new("ShaderNodeMath")
        weight.operation = 'MULTIPLY'
        link(height.outputs[0],weight.inputs[0])
        link(noise(nodes,link,point,180),weight.inputs[1])
        mix = nodes.new("ShaderNodeMixRGB")
        base = nodes.get("Principled BSDF").inputs["Base Color"]
        link(base.links[0].from_socket,mix.inputs[1])
        mix.inputs[2].default_value = C.color("937851")
        link(weight.outputs[0],mix.inputs[0])
        link(mix.outputs[0],base)
        m["boiler"] = patina
    return m


def octagon_factor(theta):
    return math.cos(math.pi / 8) / math.cos(theta % (math.pi / 4) - math.pi / 8)


def spout_offset(theta, radius, z):
    if radius < 38 or z < 135:
        return 0, 0
    distance = abs((theta - math.pi + math.pi) % TAU - math.pi)
    shoulder = max(0, 1 - distance / (math.pi / 4))
    height = min(1, (z - 135) / 23)
    return 11.3 * shoulder * height ** 1.4, 3.2 * shoulder * height ** 1.4


def turn(name, profile, mats, *, angles=SECTION, center=(0, 0, 0), cut=None,
         resolution=96, edge=0, smooth=True, spout=False, deform=None):
    """Sweep a closed radial section. Each row gives radius, Z, octagon mix and outgoing finish."""
    first, last = angles
    steps = {float(first), float(last)}
    for i in range(math.floor(first / 360 * resolution) + 1,
                   math.ceil(last / 360 * resolution)):
        steps.add(i * 360 / resolution)
    complete = abs(last - first - 360) < 1e-6
    angles_deg = sorted(steps)
    if complete:
        angles_deg.pop()
    vertices, faces, indexes, shading, rings, poles = [], [], [], [], [], {}
    for angle in angles_deg:
        theta = math.radians(angle)
        ring = []
        for j, (r, z, poly, _) in enumerate(profile):
            if r == 0 and j in poles:
                ring.append(poles[j])
                continue
            radius = r * (1 - poly + poly * octagon_factor(theta))
            dr, dz = spout_offset(theta, r, z) if spout else (0, 0)
            x, y = (radius + dr) * math.cos(theta), (radius + dr) * math.sin(theta)
            zz = z + dz
            if deform:
                x, y, zz = deform(x, y, zz, r, theta)
            ring.append(len(vertices))
            if r == 0:
                poles[j] = len(vertices)
            vertices.append(meters((x + center[0], y + center[1], zz + center[2])))
        rings.append(ring)

    def face(ids, material, soft):
        ids = list(dict.fromkeys(ids))
        if len(ids) > 2:
            faces.append(ids)
            indexes.append(material)
            shading.append(soft)

    for i in range(len(rings) if complete else len(rings) - 1):
        a, b = rings[i], rings[(i + 1) % len(rings)]
        for j, (r, z, poly, material) in enumerate(profile):
            k = (j + 1) % len(profile)
            # Preserve planar octagonal highlights and flat horizontal lands.
            soft = smooth and max(poly, profile[k][2]) < .52 and abs(z - profile[k][1]) > .06
            face((a[j], b[j], b[k], a[k]), material, soft)
    if not complete:
        idx = 0
        if cut is not None:
            idx = mats.index(cut) if cut in mats else len(mats)
        face(rings[0], idx, False)
        face(reversed(rings[-1]), idx, False)
    obj = C.mesh(name, vertices, faces, mats[0])
    for mat in mats[1:]:
        obj.data.materials.append(mat)
    if cut is not None and cut not in mats:
        obj.data.materials.append(cut)
    for poly, index, soft in zip(obj.data.polygons, indexes, shading):
        poly.material_index, poly.use_smooth = index, soft
    return bevel(obj, edge)


def simple_turn(name, rz, mat, *, facets=0, **kwargs):
    return turn(name, [(r, z, facets, 0) for r, z in rz], [mat], **kwargs)


def axial(name, base, axis, profile, mat, *, sides=64):
    # Origin at the seat makes the stack of washers and turned lands measurable.
    obj = simple_turn(name, profile, mat, angles=FULL, resolution=sides,
                      smooth=sides > 12)
    obj.location = meters(base)
    obj.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    return obj


def boiler(m, revised):
    shell = [
        (0, 0, 0, 0), (42, 0, .70, 0), (45.6, .55, .88, 0), (47.6, 2.5, 1, 0),
        (49.0, 8, 1, 0), (49.2, 19, 1, 0), (44.4, 49, 1, 0),
        (38.5, 63.5, .88, 0), (35.15, 67.4, .1, 0), (35.15, 78.5, 0, 0),
        (34.7, 79.3, 0, 1), (31.7, 79.3, 0, 1), (31.7, 76.9, 0, 1),
        (32.4, 76.4, 0, 1), (32.8, 67.4, .05, 1), (35.9, 62.0, .78, 1),
        (41.8, 48, .94, 1), (46.3, 19, 1, 1), (46.0, 8.5, 1, 1),
        (44.8, 5.1, .9, 1), (42, 4.0, .74, 1), (0, 4.0, 0, 1)
    ]
    if revised:
        # Leave the sole uncut so both near supports still carry a visible part of the base.
        shell = [(0,2.5,0,0),(47.6,2.5,1,0)] + shell[4:]
        sole = [(0,0,0,0),(42,0,.70,0),(45.6,.55,.88,0),(47.6,2.5,1,1),(0,2.5,0,1)]
        turn("Boiler | intact heat-spreading sole on trivet",sole,[m["boiler"],m["sawn"]],
             angles=FULL,edge=.24)
    turn("Boiler | octagonal casting and inner water jacket", shell, [m.get("boiler",m["alloy"]), m["cast"]],
         cut=m["sawn"], edge=.33)
    # Four pitched lands on the male neck, exposed at the end of the female collar.
    for i in range(4):
        z = 67.35 + 2.5 * i
        simple_turn("Neck | pitched thread", [(35.15,z), (36.45,z+.48), (36.52,z+.95),
                    (35.15,z+1.45)], m["alloy"], edge=.08,
                    deform=lambda x,y,h,r,a: (x,y,h+(a-math.radians(SECTION[0]))/TAU*2.5))

    theta = math.radians(202.5)
    axis = Vector((math.cos(theta), math.sin(theta), .25)).normalized()
    radius = (44.4 - 3 / 14.5 * 5.9) * octagon_factor(theta)
    seat = Vector((radius * math.cos(theta), radius * math.sin(theta), 52))
    axial("Pressure valve | sealing washer", seat, axis,
          [(0,-.40),(5.0,-.40),(5.05,.8),(4.8,1.0),(0,1.0)], m["burner"])
    axial("Pressure valve | brass hex", seat + axis, axis,
          [(0,0),(5.2,0),(5.65,.5),(5.65,3.1),(4.95,3.8),(0,3.8)], m["brass"], sides=6)
    axial("Pressure valve | circular recess", seat + axis*4.78, axis,
          [(0,0),(3.3,0),(3.35,.6),(2.9,1.2),(1.55,1.2),(1.45,.5),(0,.5)], m["brass"])
    axial("Pressure valve | spring plunger", seat + axis*5.15, axis,
          [(0,0),(1.32,0),(1.33,.84),(.95,1.12),(0,1.15)], m["steel"])


def upper_casting(m):
    # The underside of the collector floor converges into the same casting as the chimney.
    shell = [
        (37.45,71.6,0,0), (40.15,71.6,0,0), (40.9,72.6,0,0), (40.9,76.9,0,0),
        (40.25,78.0,0,0), (39.8,81.4,.1,1), (35.8,85.5,.55,1),
        (35.3,91.0,1,1), (50.85,152.7,1,1), (52.15,155.1,1,0),
        (52.35,157.75,1,0), (51.5,158.5,1,0), (49.55,158.5,1,2),
        (49.0,155.7,1,2), (33.35,93.0,.94,2), (31.6,90.25,.65,2),
        (12.1,89.25,.12,2), (10.25,90.6,.04,2), (9.25,95.0,0,2),
        (5.25,136.7,0,2), (5.12,142.4,0,0), (5.50,143.15,0,0),
        (5.50,144.0,0,0), (3.75,144.0,0,2), (3.72,142.8,0,2),
        (3.72,90.3,0,2), (6.45,87.65,0,2), (25.9,82.4,0,2),
        (30.30,82.4,0,2), (30.30,81.1,0,2), (35.4,81.1,0,2),
        (35.4,79.42,0,2), (37.45,79.32,0,2)
    ]
    turn("Collector | enamel facets, casting, chimney and pour lip", shell,
         [m["alloy"], m["enamel"], m["cast"]], cut=m["sawn"], spout=True, edge=.26)
    # Female thread has a shorter window than the entire pot on its left face.
    for i in range(2):
        z = 73.7 + 2.5 * i
        simple_turn("Collar | internal thread valley", [(36.65,z+.72),(37.46,z+.12),
                    (37.46,z+2.1),(36.65,z+1.55)], m["steel"], angles=(-16,221),
                    deform=lambda x,y,h,r,a: (x,y,h+(a-math.radians(SECTION[0]))/TAU*2.5))
    gasket = [(30.05,79.64), (34.95,79.64), (35.38,79.85), (35.4,80.98),
              (35.2,81.12), (30.05,81.12)]
    simple_turn("Brew head | compressed sealing ring", gasket, m["seal"], edge=.12)


def molded_grip(mat):
    # Cross sections roll continuously around the knuckles and taper into the finger rest.
    # The last two columns give the section half-width in the XZ plane and half-depth in Y.
    path = [(49.6,149.45,4.8,4.5),(53.9,149.95,6.35,6.3),(60.05,149.35,7.05,7.05),
            (66.25,147.69,7.55,7.4),(71.31,144.7,7.4,7.6),(74.24,139.47,7.15,7.5),
            (74.75,132.3,6.92,7.15),(73.78,122.0,6.55,6.93),(72.10,111.9,6.10,6.68),
            (70.80,101.45,5.55,6.35),(69.93,93.6,4.75,5.72),(69.7,90.25,3.82,4.77),
            (69.67,88.38,2.63,3.27),(69.65,87.38,1.19,1.48),(69.65,87.16,.10,.12)]
    def interp(i, t):
        p, a, b, q = [path[max(0,min(len(path)-1,j))] for j in (i-1,i,i+1,i+2)]
        return tuple(.5*(2*v+(-u+w)*t+(2*u-5*v+4*w-ww)*t*t+
                         (-u+3*v-3*w+ww)*t**3) for u,v,w,ww in zip(p,a,b,q))
    rows = [interp(i,j/5) for i in range(len(path)-1) for j in range(5)] + [path[-1]]
    verts, faces = [], []
    sides = 40
    for i, (x,z,width,depth) in enumerate(rows):
        pre, post = rows[max(0,i-1)], rows[min(len(rows)-1,i+1)]
        normal = Vector((pre[1]-post[1],0,post[0]-pre[0])).normalized()
        for j in range(sides):
            a = TAU*j/sides
            u = math.copysign(abs(math.cos(a))**.76,math.cos(a))
            v = math.copysign(abs(math.sin(a))**.76,math.sin(a))
            pos = Vector((x,depth*v,z))+normal*(width*u)
            verts.append(meters(pos))
    for i in range(len(rows)-1):
        for j in range(sides):
            a, b = i*sides+j,i*sides+(j+1)%sides
            faces.append((a,a+sides,b+sides,b))
    faces += [tuple(range(sides)),tuple(range(len(verts)-1,len(verts)-sides-1,-1))]
    obj = C.mesh("Handle | radiused molded Bakelite grip",verts,faces,mat)
    for face in obj.data.polygons:
        face.use_smooth = True


def lid_and_grip(m, revised):
    lid = [(0,163.5,0,0),(13,163.45,.65,0),(43,157.8,1,0),(49.4,157.7,1,0),
           (51.8,158.35,1,0),(52.2,159.15,1,0),(52.0,160.0,1,1),
           (47.9,161.35,1,1),(19.5,167.2,1,1),(16.7,168.15,.8,1),
           (11,168.5,.2,0),(0,168.5,0,0)]
    turn("Lid | folded rim and faceted enamel crown", lid, [m["alloy"], m["enamel"]],
         angles=FULL, spout=True, edge=.22)
    simple_turn("Lid | knob mounting ferrule", [(0,168.45),(9.7,168.45),(10.0,169.0),
                (10.0,170.1),(8.6,170.58),(0,170.58)], m["alloy"], angles=FULL, edge=.12)
    if revised:
        def flute(x,y,z,r,a):
            inset = .44 * (1-math.cos(10*a)) * min(1,max(0,(z-174)/5))
            return x-inset*math.cos(a), y-inset*math.sin(a), z
        simple_turn("Lid | fluted Bakelite knob",[(0,170.57),(7.7,170.57),(8.1,171.3),
                    (8.12,173),(8.35,174.4),(10.85,179.0),(11.6,181.6),(11.65,182.65),
                    (11.4,183.55),(10.72,184.32),(9.2,184.91),(6.2,185.18),(0,185.28)],
                    m["black"],angles=FULL,resolution=160,deform=flute)
    else:
        simple_turn("Lid | sculpted eight-sided heatproof knob", [(0,170.57),(7.6,170.57),
                    (8.0,171.3),(8.35,174.3),(11.65,181.1),(11.95,183.0),(11.15,184.8),
                    (8.4,185.35),(0,185.35)], m["black"], facets=.91, angles=FULL, edge=.55)
    outline("Handle | cast integral mounting lugs", [(43.7,143.3),(46.3,156.2),
            (53.1,157.3),(58,153.1),(57,145.6),(51.3,142.6)], -5.6, 5.6, m["alloy"], .8)
    grip = [(50.0,143.1),(52.5,154.3),(57.6,157.0),(63.6,155.8),(72.0,152.8),
            (78.5,147.7),(81.3,141.9),(81.7,133.4),(79.2,113.6),(75.5,93.2),
            (73.6,87.8),(70.7,85.5),(67.9,85.8),(65.8,88.9),(65.8,94.0),
            (68.3,116.7),(68.7,131.2),(67.1,136.8),(62.6,140.3),(56.6,142.2)]
    if revised:
        molded_grip(m["black"])
    else:
        outline("Handle | one-piece molded phenolic cantilever", grip, -6.7, 6.7, m["black"], 2.4)
    for y in (-7.6, 3.5):
        axial("Lid | hinge knuckle", (49.8,y,157.0), (0,1,0),
              [(1.2,0),(3.3,0),(3.45,.3),(3.45,3.7),(3.2,4.0),(1.2,4.0)], m["alloy"])
    axial("Lid | peened hinge pin", (49.8,-7.85,157), (0,1,0),
          [(0,0),(2.65,0),(2.7,.45),(1.20,.72),(1.20,15.20),(2.35,15.4),
           (2.35,15.75),(0,15.75)], m["brass"])
    outline("Lid | thumb lever", [(46.3,157.7),(48.2,161.3),(53.1,161.8),
            (59.1,165.5),(62.0,165.5),(62.7,163.4),(56.5,158.2),(52.5,156.8)],
            -3.5, 3.5, m["alloy"], .65)
    for x, z in ((57.5,163.98),(59.2,164.95),(60.8,165.45)):
        box("Thumb lever | grip ridge", (x,0,z), (.48,6.2,.48), m["alloy"], .18)
    axial("Handle | inset mounting rivet", (55.1,-6.43 if revised else -6.74,149.2), (0,-1,0),
          [(0,0),(2.2,0),(2.25,.19),(1.85,.45),(.67,.49),(.43,.23),(0,.23)], m["steel"])


def punched_screen(name, z, outer, thickness, mat):
    """Pressed plate with actual open bores, including half-bores along the exposed section."""
    start, end = map(math.radians, SECTION)
    inner, bands, columns = 1.5, 10, 39
    dr, dt = (outer - inner) / bands, (end - start) / columns
    verts, faces = [], []
    for k in range(bands):
        rc = inner + (k + .5) * dr
        for j in range(columns + 1):
            tc = start + j * dt
            bore = min(.69, rc * dt * .31)
            # Four sides of a rectangular polar cell, with a round inscribed perforation.
            phase = [i * TAU / 16 for i in range(16)]
            if j == 0:
                phase = [i * TAU / 16 for i in range(-4,5)]
            if j == columns:
                phase = [i * TAU / 16 for i in range(4,13)]
            base = len(verts)
            for a in phase:
                u, v = math.cos(a), math.sin(a)
                extent = max(abs(u), abs(v))
                outside = tc + dt * .5 * u / extent, rc + dr * .5 * v / extent
                inside = tc + bore / rc * u, rc + bore * v
                for zz, coord in ((z,outside), (z,inside), (z+thickness,inside),
                                  (z+thickness,outside)):
                    theta, radius = coord
                    verts.append(meters((radius*math.cos(theta), radius*math.sin(theta), zz)))
            for s in range(len(phase) if 0 < j < columns else len(phase)-1):
                a, b = base+4*s, base+4*((s+1) % len(phase))
                faces.extend(((a,a+1,b+1,b), (a+1,a+2,b+2,b+1), (a+2,a+3,b+3,b+2)))
            if j in (0, columns):
                faces.extend(((base+3,base+2,base+1,base),
                              tuple(base+4*(len(phase)-1)+s for s in range(4))))
    C.mesh(name, verts, [face[::-1] for face in faces], mat)
    simple_turn(name+" | hub", [(0,z),(inner,z),(inner,z+thickness),(0,z+thickness)], mat)


def basket_and_bed(m, revised):
    funnel = [(4.6,8.1),(5.12,8.7),(5.12,49.0),(6.0,51.45),(26.9,60.1),
              (29.2,61.45),(29.7,63.0),(30.92,76.6),(31.2,77.95),
              (32.3,78.05),(34.4,78.65),(34.6,79.22),(34.25,79.62),
              (31.0,79.62),(30.2,79.0),(29.85,77.9),(28.6,63.15),
              (28.25,62.52),(27.10,62.45),(26.6,61.2),(5.8,52.7),
              (4.05,50.1),(4.05,8.7),(4.15,8.15)]
    simple_turn("Basket | drawn funnel and submerged inlet", funnel, m["steel"],
                cut=m["sawn"], edge=.12)
    punched_screen("Basket | perforated lower plate", 62.42, 28.30, .57, m["steel"])
    punched_screen("Brew head | fine perforated upper filter", 79.77, 30.13, .79, m["steel"])
    simple_turn("Brew head | rolled filter edge", [(29.9,79.74),(30.46,79.74),
                (30.5,80.45),(30.14,80.6),(29.9,80.55)], m["steel"], edge=.10)
    simple_turn("Ground coffee | saturated cross section", [(0,62.99),(28.34,62.99),
                (29.75,77.8),(30.0,79.69),(0,79.69)], m["grounds"])

    # Individual irregular fragments sit in the wet cut face. All share one small mesh.
    rng = random.Random(944)
    variants = [m["grounds"]]
    shades = (("341d12","61341f"),("492919","8a5531"),("291912","4b2c1a"))
    if revised:
        shades = (("21140c","462717"),("382316","69442a"),("170e0a","372319"))
    for i, colors in enumerate(shades):
        variants.append(finish("Ground coffee | fragment %d"%i, colors, (.30,.59),
                               scale=2200, micro=6500, grain=.06))
    verts, faces, ids = [], [], []
    for degrees, outward in ((SECTION[0],-1),(SECTION[1],1)):
        a = math.radians(degrees)
        radial = Vector((math.cos(a),math.sin(a),0))
        normal = Vector((-math.sin(a)*outward,math.cos(a)*outward,0))
        for _ in range(2150):
            z = rng.uniform(63.24,79.44)
            r = rng.uniform(.13,28.0+(z-63)*.086)
            center = r*radial + Vector((0,0,z)) + normal*rng.uniform(-.13,.03)
            sr = rng.uniform(.12,.52)
            sz, sn = sr*rng.uniform(.45,.95), sr*rng.uniform(.34,.82)
            phase = rng.uniform(0,TAU)
            base = len(verts)
            sides = 5
            for j in range(sides):
                angle = phase + TAU*j/sides
                p = center + radial*(sr*math.cos(angle)) + Vector((0,0,sz*math.sin(angle)))
                p += normal*rng.uniform(-.08,.07)
                verts.append(meters(p))
            verts.append(meters(center+normal*sn))
            idx = rng.choices((0,1,2,3), weights=(4,4,1,4))[0]
            for j in range(sides):
                face = (base+j,base+(j+1)%sides,base+sides)
                faces.append(face if outward < 0 else face[::-1])
                ids.append(idx)
    obj = C.mesh("Ground coffee | chipped faces and fines", verts, faces, variants[0])
    for mat in variants[1:]:
        obj.data.materials.append(mat)
    for face, idx in zip(obj.data.polygons,ids):
        face.material_index = idx


def stream(name, samples, mat):
    """Elliptical sections along a smooth liquid centerline, with a narrower falling tail."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions, curve.resolution_u = '3D', 12
    curve.bevel_depth, curve.bevel_resolution, curve.use_fill_caps = MM, 4, True
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(samples)-1)
    for p, (x,y,z,r) in zip(spline.bezier_points,samples):
        p.co, p.radius = meters((x,y,z)), r
        p.handle_left_type = p.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name,curve)
    bpy.context.scene.collection.objects.link(obj)
    curve.materials.append(mat)
    return obj


def coffee_ribbon(m):
    # The outlet bridge sits directly on the chimney lip. Coffee exits under its two windows.
    for angles in ((56,128),(207,232)):
        simple_turn("Chimney | cast outlet bridge foot", [(4.24,143.96),(5.40,143.96),
                    (5.51,147.09),(4.32,147.09)],m["alloy"],angles=angles,edge=.14)
    simple_turn("Chimney | raised diffuser cap", [(0,146.94),(5.64,146.94),
                (6.21,147.28),(6.22,147.87),(5.83,148.25),(4.42,148.68),(0,149.0)],
                m["alloy"],angles=FULL,edge=.15)
    # A wide film rolls over the lip, then stretches into a much thinner falling stream.
    centers = [(2.78,.65,144.20,1.78,.52),(4.35,.68,144.87,1.66,.55),
               (5.85,.73,144.77,1.52,.58),(7.20,.80,143.95,1.31,.59),
               (8.42,.89,142.30,1.11,.55),(9.49,.95,139.35,.91,.51),
               (10.55,.91,135.00,.84,.48),(11.40,.85,129.7,.68,.43),
               (12.15,.88,123.3,.63,.38),(12.79,.84,116.0,.51,.34),
               (13.24,.79,108.15,.46,.30),(13.49,.80,101.2,.45,.34),
               (13.50,.80,100.85,.60,.51)]
    verts, faces = [], []
    sides = 20
    for j,(x,y,z,w,h) in enumerate(centers):
        pre,post = centers[max(0,j-1)],centers[min(len(centers)-1,j+1)]
        n = Vector((pre[2]-post[2],0,post[0]-pre[0])).normalized()
        for i in range(sides):
            a = TAU*i/sides
            p = Vector((x,y+w*math.sin(a),z))+n*(h*math.cos(a))
            verts.append(meters(p))
    for j in range(len(centers)-1):
        for i in range(sides):
            a, b = j*sides+i,j*sides+(i+1)%sides
            faces.append((a,a+sides,b+sides,b))
    faces += [tuple(range(sides)),tuple(range(len(verts)-1,len(verts)-sides-1,-1))]
    obj = C.mesh("Extraction | curved sheet narrowing into a coffee thread",verts,faces,m["thread"])
    for f in obj.data.polygons:
        f.use_smooth = True
    smooth = obj.modifiers.new("Continuous liquid silhouette",'SUBSURF')
    smooth.levels = smooth.render_levels = 2


def water_detail(m):
    # A narrow highlight where the free surface turns downward at the section.
    for a in map(math.radians,SECTION):
        end = 44.09*(1-.973+.973*octagon_factor(a))
        profile = [(5.20,32.49),(6.8,32.24),(15,32.19),(26.5,32.17),
                   (end-1.40,32.21),(end-.43,32.37),(end,32.60)]
        stream("Water | meniscus along the cut",[(r*math.cos(a),r*math.sin(a),z,.14)
               for r,z in profile],m["water"])
    air = bpy.data.materials.new("Water | air bell interface")
    air.use_nodes = True
    nodes, link = air.node_tree.nodes, air.node_tree.links.new
    glass = nodes.new("ShaderNodeBsdfGlass")
    glass.inputs["IOR"].default_value = 1/1.333
    glass.inputs["Roughness"].default_value = .035
    link(glass.outputs[0],nodes.get("Material Output").inputs["Surface"])
    rng = random.Random(690)
    for i in range(66):
        a = rng.uniform(-.10,3.9)
        z = rng.uniform(9.1,31.5)
        size = rng.uniform(.17,.73)*(1.3 if i%11==0 else 1)
        if i%3:
            # Bubbles nucleate against the metal wall of the submerged pickup.
            r = 5.11 + size*.68
        else:
            # A few rising beads are visible through the front face of the water.
            a = math.radians(rng.choice(SECTION)) + rng.choice((.08,.11))*(1 if i%2 else -1)
            if not math.radians(SECTION[0]) < a < math.radians(SECTION[1]):
                continue
            r = rng.uniform(12,40)
        C.sphere("Water | small entrained air bell",meters((r*math.cos(a),r*math.sin(a),z)),
                 meters((size,size,size*.96)),air)


def fluids(m, revised):
    # The reservoir joins the inlet under its mouth. Above that height it surrounds the tube.
    water = [(0,4.015,0,0),(42,4.015,.74,0),(44.77,5.12,.90,0),
             (45.97,8.53,1,0),(46.27,19,1,0),(44.14,32.65,.973,0),
             (43.73,32.37,.968,0),(42.8,32.21,.96,0),(34,32.16,.7,0),
             (20,32.17,.25,0),(7.0,32.21,0,0),(5.22,32.50,0,0),
             (5.14,8.72,0,0),(4.61,8.09,0,0),(0,8.09,0,0)]
    turn("Water | reservoir and raised meniscus", water, [m["water"]], resolution=144)
    simple_turn("Water | submerged intake through to lower screen", [(0,8.09),(4.035,8.09),
                (4.035,50.13),(5.76,52.72),(26.55,61.24),(27.01,62.40),(0,62.40)],
                m["water"], resolution=96)
    simple_turn("Coffee | brew above the filter and inside the chimney", [(0,80.57),
                (29.87,80.57),(29.87,82.35),(25.85,82.36),(6.42,87.62),
                (3.70,90.30),(3.70,142.85),(3.73,143.96),(3.60,144.35),(0,144.45)],
                m["brew"], resolution=96)
    # The upper free surface is a fine mesh. Ripples share the coffee surface itself.
    pool = [(12.13,89.29,.12,0),(31.55,90.28,.65,0),(33.32,93.03,.94,0),
            (35.43,101.45,.95,0),(35.05,101.29,.94,0)]
    for j in range(80):
        t = j/79
        pool.append((34.75*(1-t)+8.85*t, 101.14, .92*(1-t)**1.3, 0))
    pool += [(8.72,101.39,0,0),(9.28,95.0,0,0),(10.28,90.64,.04,0)]

    def ripples(x,y,z,r,a):
        if 101.1 < z < 101.2:
            d = math.hypot(x-13.5, y-.8)
            z += .38*math.cos(d*2.32)*math.exp(-d/5.0)
            d = math.hypot(x+9.3, y-1.2)
            z += .16*math.cos(d*2.1)*math.exp(-d/4)
        return x,y,z

    turn("Coffee | collected brew and impact ripples", pool, [m["brew"]],
         resolution=176, deform=ripples)
    if revised:
        coffee_ribbon(m)
        water_detail(m)
    else:
        stream("Extraction | primary amber stream", [(2.0,.50,144.04,1.65),
               (4.6,.61,144.83,1.41),(6.95,.78,144.11,1.10),(9.65,.9,140.0,.95),
               (11.5,.85,132,.72),(12.65,.76,119,.63),(13.45,.8,104,.59),
               (13.51,.8,100.9,.84)], m["thread"])
    stream("Extraction | coffee wetting the opposite lip", [(-2.1,1.2,144.08,1.28),
           (-4.8,1.2,144.68,.98),(-5.65,1.24,143.0,.80),(-5.62,1.24,137,.66),
           (-6.55,1.22,126,.55),(-7.55,1.21,115,.63),(-9.29,1.22,101.0,.67)], m["thread"])

    rng = random.Random(229)
    foam = liquid("Coffee | amber bubble film", "a06c39", .16, .30, 1.335, "aa6123", 15)
    for _ in range(48):
        a = rng.uniform(0,TAU)
        radius = rng.uniform(1.1,5)**1.1
        x, y = 13.5 + radius*math.cos(a), .8 + radius*math.sin(a)
        if y < math.tan(math.radians(SECTION[0]))*x or x < 9:
            continue
        size = rng.uniform(.15,.64)
        C.sphere("Coffee | bubbles at stream impact", meters((x,y,101.17)),
                 meters((size,size,size*.57)),foam)

    # Condensation beads on the visible inner back wall of the boiler, above the liquid.
    for _ in range(88):
        a = rng.uniform(.05,math.pi-.07)
        z = rng.uniform(33.4,55)
        if z <= 48:
            r, poly = 46.3+(41.8-46.3)*(z-19)/29, 1-.06*(z-19)/29
        else:
            r, poly = 41.8+(35.9-41.8)*(z-48)/14, .94-.16*(z-48)/14
        r *= 1-poly+poly*octagon_factor(a)
        size = rng.uniform(.17,.62)
        bead = C.sphere("Boiler | condensation on casting", meters((r*math.cos(a),r*math.sin(a),z)),
                        meters((size*.68,size,size*rng.uniform(1,1.45))),m["water"])
        bead.rotation_euler.z = a


def burner_flames(revised):
    mat = bpy.data.materials.new("Gas | thin blue flame envelope")
    mat.use_nodes = True
    nodes, link = mat.node_tree.nodes, mat.node_tree.links.new
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    layer = nodes.new("ShaderNodeLayerWeight")
    mix = nodes.new("ShaderNodeMixShader")
    link(layer.outputs["Facing"],mix.inputs[0])
    link(transparent.outputs[0],mix.inputs[1])
    link(emission.outputs[0],mix.inputs[2])
    link(mix.outputs[0],output.inputs["Surface"])
    emission.inputs["Color"].default_value = C.color("5782ff" if revised else "669aff")
    emission.inputs["Strength"].default_value = 1.55 if revised else 2.3
    if revised:
        height = nodes.new("ShaderNodeAttribute")
        height.attribute_name = "Flame height"
        gradient = nodes.new("ShaderNodeValToRGB")
        cr = gradient.color_ramp
        cr.elements.remove(cr.elements[1])
        for i, (position,opacity) in enumerate(((0,.31),(.17,.78),(.42,.57),(.74,.18),(1,0))):
            e = cr.elements[0] if i == 0 else cr.elements.new(position)
            e.position, e.color = position,(opacity,opacity,opacity,1)
        cr.interpolation = 'EASE'
        link(height.outputs["Fac"],gradient.inputs[0])
        factor = nodes.new("ShaderNodeMath")
        factor.operation = 'MULTIPLY'
        link(gradient.outputs[0],factor.inputs[0])
        link(layer.outputs["Facing"],factor.inputs[1])
        link(factor.outputs[0],mix.inputs[0])
    rng = random.Random(41)
    verts, faces, heights = [], [], []
    for k in range(47):
        theta = TAU*k/47
        height = rng.uniform(5.2,8.0) if revised else rng.uniform(5.8,8.1)
        lean_angle = rng.uniform(-.028,.028) if revised else 0
        base = len(verts)
        for h, width, lean in ((0,.73,0),(.18,1.00,.4),(.42,.86,1.05),(.74,.50,1.95),(1,.03,2.7)):
            for j in range(8):
                b = TAU*j/8
                rad = 28.9+lean+.63*width*math.cos(b)
                a = theta+1.11*width*math.sin(b)/rad+lean_angle*h*h
                verts.append(meters((rad*math.cos(a),rad*math.sin(a),-11.85+h*height)))
                heights.append(h)
        for row in range(4):
            for j in range(8):
                a, b = base+8*row+j, base+8*row+(j+1)%8
                faces.append((a,b,b+8,a+8))
    obj = C.mesh("Burner | individually ported low gas flames", verts, faces, mat)
    if revised:
        attribute = obj.data.attributes.new("Flame height",'FLOAT','POINT')
        attribute.data.foreach_set("value",heights)
    for f in obj.data.polygons:
        f.use_smooth = True


def stove(m, revised):
    hob = finish("Range | warm-gray vitreous enamel", ("b3b1a4","c5c2b6"), (.23,.37),
                 metal=.19, coat=.44, scale=100, micro=1400)
    box("Stove | porcelain enamel top", (0,-76,-25.0),(475,358,7.5), hob, 3.1)
    simple_turn("Burner | recessed spill well", [(0,-21.23),(55,-21.23),(54.3,-20.3),
                (51.8,-20.2),(48.9,-21.10),(34,-21.10),(32,-20.5),(0,-20.5)],
                hob, angles=FULL, edge=.48)
    simple_turn("Burner | heat-stained brass port ring", [(0,-20.51),(24,-20.51),
                (25.7,-19.65),(27.1,-17.0),(28.8,-16),(28.8,-11.7),(27.2,-11.1),(0,-11.1)],
                m["burner"], angles=FULL, edge=.26)
    simple_turn("Burner | seasoned cast cap", [(0,-11.25),(29.0,-11.25),(29.4,-10.7),
                (29.3,-9.1),(27.75,-8.37),(14,-8.05),(0,-8.05)], m["iron"], angles=FULL, edge=.40)
    for k in range(47):
        a = TAU*k/47
        jet = box("Burner | recessed jet mouth", (28.77*math.cos(a),28.77*math.sin(a),-13),
                  (.15,1.4,2.55),m["black"],.08)
        jet.rotation_euler.z = a
    burner_flames(revised)
    for degrees in (45,135,225,315):
        finger = outline("Trivet | load-bearing cast finger", [(30.7,-7.8),(30.7,-2.5),
                 (33.0,0),(67.1,0),(89.5,-2.3),(94,-4.9),(94,-21.25),(84,-21.25),
                 (81,-10.3),(63,-8.5),(34,-8.9)], -3.9,3.9,m["iron"],1.1)
        finger.rotation_euler.z = math.radians(degrees)
    for sign in (-1,1):
        box("Trivet | side rail", (sign*64.0,0,-6.8), (6.6,128.5,7.0), m["iron"], 1.5)
        box("Trivet | cross rail", (0,sign*64.0,-6.8), (126,6.6,7.0), m["iron"], 1.5)


def tiles_and_cup(revised):
    oak = finish("Counter | oiled oak long grain", ("805c3d","bc946a"), (.39,.55),
                 grain=.048, direction=(.08,3,2), scale=58, micro=700)
    box("Kitchen | oak countertop", (0,200,-35.35),(1100,280,24.2),oak,2.0)
    grout = ("848473","999985") if revised else ("b1a996","cdc6ae")
    plaster = finish("Wall | putty grout", grout, (.76,.9), grain=.08,
                     scale=55,micro=1800)
    box("Kitchen | tile setting bed", (0,291,170),(1300,20,600),plaster)
    glazes = []
    colors = (("b6baab","d4d1bb"),("b6b6a5","ccc9b6"),("babdad","dad6c1"),("b6b9a8","cfceba"))
    if revised:
        colors = (("6e746b","909383"),("72776c","939487"),("75796e","959886"),("70766a","8d927e"))
    for i, c in enumerate(colors):
        glazes.append(finish("Tile | warm handmade glaze %d"%i,c,(.21,.36),grain=.045,
                            scale=46,micro=470,coat=.33))
    rng = random.Random(30)
    for row in range(7):
        for j in range(-4,5):
            tile = box("Wall | staggered ceramic tile",
                       (j*107+((row%2)*53.5)+24,277+rng.uniform(-.27,.27),-23+row*62+31),
                       (105.35,8.0,60.45),rng.choice(glazes),1.18)
            tile.rotation_euler.y = rng.uniform(-.0016,.0016)

    cup = finish("Cup | honey porcelain glaze", ("c7ad88","e7d4aa"), (.18,.30),
                 grain=.008,scale=130,micro=2100,coat=.45)
    stripe = finish("Cup | iron-oxide rim", ("925725","b27c46"), (.22,.32), coat=.30)
    cx,cy,cz = -106,158,-23.25
    simple_turn("Demitasse | saucer", [(0,0),(13.0,0),(14.2,1),(24,2.6),(31.2,5.1),
                (32.1,5.9),(32.0,6.35),(31.2,6.65),(22.4,4.5),(12,3.45),(0,3.45)],
                cup,angles=FULL,center=(cx,cy,cz),edge=.26)
    cup_profile = [(0,3.46,0,0),(11,3.46,0,0),(12.3,4.6,0,0),(12.3,6.0,0,0),
                   (15.4,7.2,0,0),(20.05,14.4,0,0),(22.4,28,0,0),(22.9,35.6,0,0),
                   (22.94,37.0,0,1),(22.85,37.65,0,0),(22.2,38.05,0,0),
                   (21.2,37.7,0,0),(20.95,36.5,0,0),(19.4,19.0,0,0),(15.3,11.3,0,0),
                   (11.0,9.2,0,0),(0,9.2,0,0)]
    turn("Demitasse | glazed stoneware",cup_profile,[cup,stripe],angles=FULL,center=(cx,cy,cz))
    stream("Demitasse | loop handle",[(cx-20.4,cy,cz+28,2.6),(cx-28.1,cy,cz+29.6,2.4),
           (cx-32.1,cy,cz+25.5,2.3),(cx-30.8,cy,cz+18.7,2.2),
           (cx-25.6,cy,cz+15.2,2.2),(cx-19.0,cy,cz+14.9,2.55)],cup)


def area(name, pos, target, watts, size, tint, existing=None):
    if existing is None:
        light = bpy.data.lights.new(name,'AREA')
        obj = bpy.data.objects.new(name,light)
        bpy.context.scene.collection.objects.link(obj)
    else:
        obj, light = existing, existing.data
        obj.name = light.name = name
    light.shape, light.energy, light.color = 'RECTANGLE', watts, tint
    light.size, light.size_y = size[0]*MM, size[1]*MM
    obj.location = meters(pos)
    obj.rotation_euler = (Vector(meters(target))-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj


def photography(scene, revised):
    world = C.daylight("ED", rotation=2.2)
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = .105 if revised else .24
    area("Key | morning window", (-158,-181,263),(-3,0,83), 2.85 if revised else 3.4,
         (114,173) if revised else (138,210),
         (1.0,.855,.69),existing=scene.objects["Daylight through section"])
    area("Fill | cool window return", (163,-65,155) if revised else (135,-158,133),(1,0,81),
         .66 if revised else 1.28,(100,176),(.74,.89,1.0))
    area("Rim | sun on right shoulder", (106,82,235),(0,0,106), 3.2 if revised else 4.5,
         (66,143),(1,.79,.53))
    area("Reflection | narrow window mullion", (-87,-36,154),(0,0,75),
         .23 if revised else .33,(13,128),(.80,.94,1.0))
    if revised:
        area("Bounce | linen opposite the cut",(-4,-178,110),(0,0,78),.22,(144,105),(1,.94,.85))
        # Real window-frame shadows on the distant backsplash. Both trims are outside the frame.
        trim = C.material("Kitchen | dark window trim","292e28",rough=.83)
        box("Window | upright",(-181,152,238),(6.2,6.0,201),trim,1.0)
        box("Window | sash rail",(-181,152,229),(69,6.0,6.4),trim,.7)
        light = bpy.data.lights.new("Window | warm patch on backsplash",'SPOT')
        light.energy,light.color,light.shadow_soft_size = 5.7,(1,.82,.62),.012
        light.spot_size,light.spot_blend = math.radians(58),.78
        spot = bpy.data.objects.new(light.name,light)
        scene.collection.objects.link(spot)
        spot.location = meters((-310,50,300))
        spot.rotation_euler = (Vector(meters((-22,275,193)))-spot.location).to_track_quat('-Z','Y').to_euler()
        flag = C.material("Black photographic flag","131514",rough=.91)
        box("Lighting | negative fill for aluminum",(-114,-39,105),(2,99,189),flag,.5)
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -.65 if revised else -.35
    camera_data = bpy.data.cameras.new("48 mm | cross section")
    camera = bpy.data.objects.new(camera_data.name,camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    target = Vector(meters((8.5,0,89)))
    camera.location = meters((-9,-430,185))
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type, camera_data.lens = 'PERSP', 48
    camera_data.sensor_fit, camera_data.sensor_height = 'VERTICAL', 33.0
    camera_data.clip_start, camera_data.clip_end = .003, 6
    camera_data.dof.use_dof = True
    focal = bpy.data.objects.new("Focus | near face of packed grounds",None)
    scene.collection.objects.link(focal)
    focal.location = meters((1,-6.5,79.8))
    camera_data.dof.focus_object = focal
    camera_data.dof.aperture_fstop = 6.3 if revised else 8
    camera_data.dof.aperture_blades = 9


class GpuMeter:
    """Sample total dedicated memory; WDDM per-process accounting is often unavailable."""
    def __init__(self):
        self.samples = []
        self.process = None
        self.reader = None

    def start(self):
        try:
            self.process = subprocess.Popen(
                ["nvidia-smi","-i","0","--query-gpu=memory.used","--format=csv,noheader,nounits",
                 "-lms","500"], stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except OSError:
            return

        def read():
            for line in self.process.stdout:
                try:
                    self.samples.append(int(line.strip()))
                except ValueError:
                    continue

        self.reader = threading.Thread(target=read,daemon=True)
        self.reader.start()

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.reader.join()
            self.process.stdout.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version",type=int,choices=(1,2),default=2)
    args = ap.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    OUT.mkdir(parents=True,exist_ok=True)
    png, jpg = (OUT/f"still_v{args.version}.{ext}" for ext in ("png","jpg"))
    if png.exists() or jpg.exists():
        raise FileExistsError(f"Still v{args.version} already exists in {OUT}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    revised = args.version == 2
    scene = C.render_settings("OPTIX",width=1080,samples=224 if revised else 192,frames=1)
    scene.cycles.adaptive_threshold = .017 if revised else .024
    scene.cycles.adaptive_min_samples = 32 if revised else 16
    scene.cycles.max_bounces = 9
    scene.cycles.transmission_bounces = 7
    scene.cycles.glossy_bounces = 4
    scene.cycles.diffuse_bounces = 3
    scene.cycles.volume_bounces = 1
    scene.cycles.sample_clamp_indirect = 6
    scene.cycles.denoising_use_gpu = False
    scene.cycles.use_auto_tile = True
    scene.cycles.tile_size = 512
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.compression = 25
    m = materials(revised)
    boiler(m,revised)
    upper_casting(m)
    lid_and_grip(m,revised)
    basket_and_bed(m,revised)
    fluids(m,revised)
    stove(m,revised)
    tiles_and_cup(revised)
    photography(scene,revised)
    active = [d.name for d in bpy.context.preferences.addons["cycles"].preferences.devices if d.use]
    print(f"TRACE | {active} | {scene.cycles.samples} adaptive spp | OIDN on CPU | "
          f"{len(scene.objects)} scene objects",flush=True)

    meter = GpuMeter()
    meter.start()
    try:
        scene.render.filepath = str(png)
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed = time.perf_counter()-start
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = 90
        bpy.data.images["Render Result"].save_render(filepath=str(jpg),scene=scene)
    finally:
        meter.stop()
    memory = f"{max(meter.samples)} MiB ({len(meter.samples)} samples)" if meter.samples else "unavailable"
    print(f"RESULT | v{args.version} | render, denoise and PNG {elapsed:.2f} s | "
          f"adapter peak {memory} | JPEG quality 90",flush=True)


if __name__ == "__main__":
    main()

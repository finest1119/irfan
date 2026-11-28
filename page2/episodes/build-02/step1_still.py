"""One creek-side commissioning still. Run with Blender 5.3 -b --factory-startup -P.

Append `-- --step1b` for the electrician beside the inlet. With no argument the
original workshop pose, materials, framing and Step 1 output path are used.
"""
import math
import random
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
PAGE = HERE.parents[1]
sys.path.insert(0, str(PAGE / "tests/cutaway_sme"))
import build_sme_v3 as v3
import cc0_lib
import render_profiles

C = v3.C
OUTPUT = HERE / "test/step1_still.png"
SIZE = (1080, 1920)
FRAME = 53
WATERLINE = -.055
GRAVITY = 9.81
RNG = random.Random(2127)
# Stations run from under the cups to the rolled outlet: centre, half-width, wall height.
FLUME = [((.065, -.107, .851), .319, .064), ((.105, -.34, .823), .307, .080),
         ((.150, -.48, .795), .199, .070), ((.192, -.595, .701), .113, .051),
         ((.209, -.746, .457), .088, .038)]
LIP = Vector(FLUME[-1][0])
OUTLET_SPEED = Vector((.07, -.50, -.85))
FALL_TIME = (OUTLET_SPEED.z + math.sqrt(OUTLET_SPEED.z**2 + 2*GRAVITY*(LIP.z-WATERLINE))) / GRAVITY
DOWN = Vector((0, 0, -GRAVITY / 2))
IMPACT = LIP + OUTLET_SPEED*FALL_TIME + DOWN*FALL_TIME**2
WALK_HEIGHT_1B = .09


def trestle(m, revised=False):
    plank = v3.surface("Sawn white oak • silvered outside", ("544737", "a68c69"),
                       (.46, .73), grain=(.75, 24, 29), scale=4.1, height=.0008)
    post = v3.surface("Oak piles • capillary waterline", ("4e4233", "887755"),
                      (.50, .78), grain=(28, 30, .8), scale=4.2, height=.0011)
    C.weathering(post, WATERLINE, .18, .80)
    # The side walk occupies the unused overhang beyond the inlet bedplate.
    left_pile = -.70 if revised else -1.00
    sill_x, sill_width = (.0525, 1.985) if revised else (-.05, 2.19)
    bearer_x, bearer_width = (.035, 1.93) if revised else (-.05, 2.10)
    for x in (left_pile, .90):
        for y in (-.19, .35):
            C.box("Pinned oak pile", (x, y, .104), (.114, .134, 1.02), post, .005)
        C.box("Pile cap", (x, .081, .654), (.145, .741, .092), plank, .004)
    for i in range(5):
        y = -.258 + (i+.5)*.151
        C.box("Turbine sill timber", (sill_x, y, .73025), (sill_width, .148, .0605), plank, .003)
    v3.bar("Front diagonal knee brace", (left_pile+.02, -.19, .09), (-.46, -.19, .700), .080, .094, post, .004)
    C.box("Through-bolted front bearer", (bearer_x, -.193, .642), (bearer_width, .106, .113), plank, .005)
    for x in (left_pile, .90, -.47):
        v3.fastener("Galvanized coach bolt", (x, -.246, .646), v3.FRONT, .013, m)
    # Separate footing for the operator. Its board tops coincide with the rig's sole datum.
    if revised:
        walk_x, width, front, walk_height = -1.335, .77, -.04, WALK_HEIGHT_1B
        stringers = (-1.61, -1.06)
    else:
        walk_x, width, front, walk_height = -.22, 2.38, .395, 0
        stringers = (-1.22, .80)
    for i in range(7):
        C.box("Creek service walk", (walk_x, front+(i+.5)*.149, walk_height-.030),
              (width, .146, .060), plank, .0025)
    for x in stringers:
        C.box("Walk stringer", (x, front+.525, walk_height-.110), (.086, 1.13, .10), post, .003)
        for y in (front+.045, front+.925):
            C.box("Walk post", (x, y, -.30+walk_height/2), (.10, .10, .28+walk_height), post, .003)


def scroll_and_flume(m):
    for ri, ro, y0, y1, finish in ((.342, .365, -.096, .118, "teal"),
            (.334, .377, -.113, -.096, "rim"), (.278, .367, .118, .132, "teal")):
        v3.arc("Open runner casing", v3.AXLE, ri, ro, -78, 99, y0, y1, m["teal"], m[finish])
    for a in map(math.radians, (-64, -31, 4, 39, 74)):
        v3.fastener("Casing joint stud", (.354*math.cos(a), -.113, v3.AXLE+.354*math.sin(a)),
                    v3.FRONT, .009, m)
    for x in (.29, .36):
        C.box("Casing foot", (x, .064, .819), (.059, .094, .021), m["teal"], .004)
        v3.bar("Cast casing rib", (x, .064, .823), (.350, .067, 1.128), .021, .038, m["teal"])
    vertices = []
    for (x, y, z), w, h in FLUME:
        vertices.extend((x+dx, y, z+dz) for dx, dz in
                        ((-w, h), (-w*.83, .005), (-w*.71, 0), (w*.71, 0), (w*.83, .005), (w, h)))
    faces = [(i, i+6, i+7, i+1) for i in range(len(vertices)-6) if i % 6 != 5]
    pan = C.mesh("Folded tailrace • open drain to the creek", vertices, faces, m["galv"])
    pan.modifiers.new("Galvanized sheet gauge", "SOLIDIFY").thickness = .002
    v3.soften(pan, .0012, 2)
    for i in (0, 5):
        C.strand("Rolled tailrace edge", vertices[i::6], .003, m["silver"])
    for side in (-1, 1):
        x = .15 + side*.139
        v3.bar("Tailrace hanger", (x, -.226, .680), (x, -.479, .793), .017, .023, m["steel"])
        v3.fastener("Hanger through bolt", (x, -.247, .68), v3.FRONT, .009, m)
    return BVHTree.FromPolygons(vertices, faces)


def bank(x):
    return 1.18 + .34*x + .42*math.sin(.68*x)


def ground(x, y):
    d = max(y-bank(x), bank(x)-4.3-y)
    rise = max(0, min(1, (d+.53)/1.23))
    return (-.31 + .78*rise**1.4 + .12*max(0, d-.63) + .045*math.sin(2.2*x+.8*y)
            + .026*math.cos(2.1*y-x) + .023*math.sin(3.4*x+2.3*y))


def grid(name, xs, ys, height, mat):
    nx = len(xs)
    verts = [(x, y, height(x, y)) for y in ys for x in xs]
    faces = [(j*nx+i, j*nx+i+1, (j+1)*nx+i+1, (j+1)*nx+i)
             for j in range(len(ys)-1) for i in range(nx-1)]
    obj = C.mesh(name, verts, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def creek(revised=False):
    gravel = C.polyhaven("river_small_rocks", 1.38)
    nt = gravel.node_tree
    shader = nt.nodes["Principled BSDF"]
    pos = nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    z = nt.nodes.new("ShaderNodeSeparateXYZ")
    v3.into(nt, pos, z.inputs[0])
    hummocks = v3.mapped(nt, v3.noise(nt, pos, 3.2), .2, .8, -.12, .12)
    turf = v3.mapped(nt, v3.calc(nt, "ADD", z.outputs["Z"], hummocks), .04, .36)
    base = shader.inputs["Base Color"].links[0].from_socket
    grass_map = nt.nodes.new("ShaderNodeTexImage")
    grass_map.image = C._image(C.ROOT / "assets/polyhaven/textures/aerial_grass_rock/aerial_grass_rock_diff_1k.jpg")
    grass_map.projection, grass_map.projection_blend = "BOX", .2
    v3.into(nt, v3.vector_op(nt, "MULTIPLY", pos, (.43, .43, .43)), grass_map.inputs["Vector"])
    v3.into(nt, v3.mix(nt, turf, base, grass_map.outputs[0]), shader.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value, bump.inputs["Strength"].default_value = .016, .32
    v3.into(nt, base, bump.inputs["Height"])
    v3.into(nt, bump.outputs[0], shader.inputs["Normal"])
    grid("Alluvial streambed rising into the bank", [i*.25 for i in range(-80, 81)],
         [i*.22 for i in range(-50, 110)], ground, gravel)

    water = v3.dielectric("Shallow creek • rippled water", "e1f0e7", 1.333, .065)
    nt = water.node_tree
    pos = nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    riffles = v3.noise(nt, v3.vector_op(nt, "MULTIPLY", pos, (1.4, 4.9, 1)), 8, 3, .32)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value, bump.inputs["Strength"].default_value = .0036, .25
    v3.into(nt, riffles, bump.inputs["Height"])
    v3.into(nt, bump.outputs[0], nt.nodes["Principled BSDF"].inputs["Normal"])

    def surface(x, y):
        r = math.hypot(x-IMPACT.x, y-IMPACT.y)
        rings = .008*math.exp(-3.7*r)*math.sin(77*r+.36*math.sin(8*y))
        return WATERLINE + rings + .005*math.sin(6*x+11*y+.7*math.sin(4*x)) + .0027*math.sin(19*y-4*x)

    # Concentrate vertices at the photographed outfall. The closed volume refracts the gravel below.
    xs = sorted({i*.25 for i in range(-50, 51)} | {i/76 for i in range(-110, 110)})
    ys = sorted({i*.25 for i in range(-28, 35)} | {i/76 for i in range(-144, 23)})
    stream = grid("Flowing creek and outfall waves", xs, ys, surface, water)
    stream.modifiers.new("Water column below the bed", "SOLIDIFY").thickness = .76

    trees = ("cc0_broadleaf_lod1", "cc0_broadleaf2_lod1")
    bushes = ("cc0_shrub_big_a", "cc0_shrub_big_b", "cc0_plant_b", "cc0_grass_d")
    rocks = ("cc0_rock_a", "cc0_rock_b", "cc0_rock_c", "cc0_pebble")
    for name in trees+bushes+rocks:
        template = cc0_lib.get(name, haze=False)
        if template is None:
            raise RuntimeError(f"Missing Mercer Hollow asset {name}")
        if name not in rocks:
            for mat in template.data.materials:
                for p in (n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"):
                    if p.inputs["Alpha"].is_linked or name in bushes:
                        p.inputs["Subsurface Weight"].default_value = .075
                        p.inputs["Subsurface Scale"].default_value = .0004

    def plant(name, x, y, scale, settle=0):
        rotation = RNG.uniform(0, math.tau)
        if revised and name in rocks and -1.92 < x < -.79 and -.25 < y < 1.12:
            return  # Leave the side walk and its piles clear.
        return cc0_lib.place(name, (x, y, ground(x, y)-settle), rotation, scale)

    for i in range(25):
        x, y = RNG.uniform(-14, 13), RNG.uniform(4.8, 18)
        plant(RNG.choice(trees), x, y, RNG.uniform(.46, .96), .025)
    for i in range(140):
        x = RNG.uniform(-6, 7)
        y = bank(x) + RNG.uniform(.23, 4.8)
        if abs(x) < 1.43 and y < 1.82:
            continue
        plant(RNG.choice(bushes), x, y, RNG.uniform(.58, 1.2), .018)
    for i in range(160):
        x = RNG.uniform(-5.5, 5.5)
        y = bank(x) + RNG.uniform(-3.15, .40)
        scale = RNG.uniform(.18, .87)
        if abs(x) < 1.11 and -.65 < y < 1.48:
            scale *= .44
        if math.hypot(x-IMPACT.x, y-IMPACT.y) > .40:
            plant(RNG.choice(rocks), x, y, scale, .045*scale)
    for name, x, y, scale in ((rocks[0], -.91, -1.06, 1.0), (rocks[2], .98, -.60, .88),
                              (rocks[1], -1.52, .45, 1.4), (rocks[0], 1.46, .85, 1.15)):
        plant(name, x, y, scale, .06)


def electrician(scene):
    import characters
    import characters_s9 as s9
    import mh_paths as paths
    from mh_blender import L

    if characters.BOLTS_IMPL != "s9" or s9.PROP_NAME != "s11":
        raise RuntimeError("Step 1b requires the series s9 rig and s11 proportions")
    ctx = L.Ctx(scene, FRAME, v3.FPS, [], 0.)
    cast = characters.build_bolts(ctx, paths.load_json(paths.CHARACTER)["bolts"])
    if cast["impl"] != "s9_quaternius":
        raise RuntimeError("The Quaternius Bolts build failed")
    # The UBC base manifest misspells the two normal-map URIs. Rebind the
    # imported shaders to the kit's real PNGs without modifying the assets.
    for name, normal in (("brows", "Hair_1"), ("beard", "Hair_1"),
                         ("hair", "Hair_1"), ("eyes", "Eye")):
        nt = bpy.data.materials["bolts_q_" + name].node_tree
        p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        normal_map = p.inputs["Normal"].links[0].from_node
        tex = normal_map.inputs["Color"].links[0].from_node
        tex.image = bpy.data.images.load(str(s9.BASE_GLTF.with_name(f"T_{normal}_Normal.png")),
                                         check_existing=True)
        tex.image.colorspace_settings.name = "Non-Color"

    wardrobe = paths.load_json(HERE.parent / "build-01/episode.json")
    for name, obj in cast["outfits"].items():
        visible = name == wardrobe["outfit"]
        obj.hide_render = obj.hide_viewport = not visible
        mask = cast["masks"][name]
        mask.show_render = mask.show_viewport = visible
    for name, obj in cast["extras"].items():
        obj.hide_render = obj.hide_viewport = name not in wardrobe["outfit_extras"]

    rig, outfit = cast["rig"], cast["outfits"]["electrician"]
    sole = min(v.co.z for v in outfit.data.vertices) * rig.scale.z
    rig.location = (-1.29, .35, WALK_HEIGHT_1B-sole)
    rig.rotation_euler.z = math.radians(43)
    bpy.context.view_layer.update()

    # Start with the series idle stance. Set the inside glove on the existing
    # wooden grip, using a point on the glove shell to account for its thickness.
    anim = cast["bake"].__self__
    sk = anim.sk
    rots, pelvis = anim.pose("idle", (FRAME-1)/v3.FPS)
    pelvis.zero()
    rots["pelvis"] = sk.restq["pelvis"].copy()
    anim._head_turn(rots, .40, .43)
    hand = "hand_l"
    group = outfit.vertex_groups[hand].index
    mid_palm = sk.head(hand).lerp(sk.head("middle_01_l"), .72) + Vector((0, 0, -.022))
    palm = min((v for v in outfit.data.vertices if any(g.group == group and g.weight > .95 for g in v.groups)),
               key=lambda v: (v.co-mid_palm).length_squared)
    offset = sk.rest[hand].inverted() @ palm.co
    centre, lever_rotation, radius = v3.grip_frame("r", FRAME)
    up = lever_rotation @ Vector(v3.UP)
    fingers = lever_rotation @ Vector((.10, -1, -.15))
    inv = rig.matrix_world.inverted()
    q = anim._hand_q("l", inv.to_quaternion() @ fingers, inv.to_quaternion() @ -up)
    contact = centre + lever_rotation @ Vector((-.036, 0, radius))
    anim._arm(rots, pelvis, "l", inv @ contact - q @ offset, Vector((.85, .08, -.76)), q)
    anim._fingers(rots, "l", q, {f: (.90, 1.12, .65) for f in s9.FINGERS}, thumb=(.42, .62, .40))
    for name, basis in sk.basis(sk.fk(rots, pelvis)).items():
        rig.pose.bones[name].matrix_basis = basis
    bpy.context.view_layer.update()
    gap = (rig.matrix_world @ (rig.pose.bones[hand].matrix @ offset) - contact).length
    if gap > .004:
        raise ValueError(f"Electrician glove missed the lever by {gap:.4f} m")
    return rig


def moving_water(name, grain, transmission):
    mat = v3.dielectric(name, "e6f5f5", 1.333, .065)
    nt = mat.node_tree
    p = nt.nodes["Principled BSDF"]
    pos = nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    streaks = v3.noise(nt, v3.vector_op(nt, "MULTIPLY", pos, grain), 1, 2.6, .28)
    # Entrained air scatters daylight in streaks between the refracting folds.
    v3.into(nt, v3.mapped(nt, streaks, .28, .73, *transmission), p.inputs["Transmission Weight"])
    tint = v3.mix(nt, streaks, C.color("b4dadd"), C.color("f2faf8"))
    v3.into(nt, tint, p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = .24, .0018
    v3.into(nt, streaks, bump.inputs["Height"])
    v3.into(nt, bump.outputs[0], p.inputs["Normal"])
    return mat


def pressure_gauge(m):
    # Across a 2 mm parallel crystal the two refractions nearly cancel. Trace
    # straight through the plate, retaining the soda-lime Fresnel reflection.
    crystal = bpy.data.materials.new("Pressure gauge • clear plate glass")
    crystal.use_nodes = True
    nt = crystal.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    fresnel = nt.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.51
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = .046
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fresnel.outputs[0], mix.inputs[0])
    nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    nt.links.new(gloss.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    objects = bpy.data.objects
    objects["Gauge crystal"].data.materials[0] = crystal
    face = objects["Baked enamel scale"]
    face.data.materials[0] = v3.surface("Warm white instrument enamel", ("e6e1cd", "faf7e8"),
                                        (.46, .56), height=.000025)
    # Keep the fine printed marks resolvable after FAST sampling. Widen in the
    # dial plane only, preserving the clearance between the scale and crystal.
    ticks = [o for o in objects if o.name.startswith("Dial graduation")]
    for tick in ticks:
        radial = Vector((tick.location.x-face.location.x, 0, tick.location.z-face.location.z)).normalized()
        across = tick.rotation_euler.to_quaternion().inverted() @ Vector((radial.z, 0, -radial.x))
        r = math.hypot(tick.location.x-face.location.x, tick.location.z-face.location.z)
        half_width = max(abs(v.co.dot(across)) for v in tick.data.vertices)
        factor = (.00155 if r < .046 else .0008) / half_width
        for v in tick.data.vertices:
            v.co += across * (v.co.dot(across) * (factor-1))
    pointer = objects["Vermilion dial pointer"]
    pointer.scale.x = 1.85
    pointer.data.materials[0] = C.material("Red instrument lacquer", "b5261d", rough=.34)
    parts = [face, objects["Gauge crystal"], objects["Bourdon gauge • spun steel case"],
             objects["Inlet pressure movement"], objects["Gauge pivot"], objects["bar"], *ticks]
    for value, angle in (("0", -128), (".2", -128/3), (".4", 128/3), (".6", 128)):
        a = math.radians(angle)
        pos = (face.location.x+.032*math.sin(a), face.location.y-.0017, face.location.z+.032*math.cos(a))
        parts.append(v3.lettering(value, pos, .0128, m["ink"]))
    # A larger field dial swivels on the existing hex union. The pointer keeps
    # its local movement and every marking remains under the same crystal.
    mount = v3.group("Pressure gauge stem", (face.location.x, .094, 1.338))
    for obj in parts:
        obj.location -= mount.location
        obj.parent = mount
    mount.scale = (1.24,)*3
    mount.rotation_euler.z = math.radians(14)


def water_ribbon(name, path, widths, depths, side_hint, mat):
    """A closed cross-section retains a refracting free edge even when viewed nearly edge-on."""
    n = 12
    vertices = []
    for i, (p, w, d) in enumerate(zip(path, widths, depths)):
        tangent = (path[min(i+1, len(path)-1)]-path[max(0, i-1)]).normalized()
        side = (side_hint-tangent*side_hint.dot(tangent)).normalized()
        normal = tangent.cross(side)
        for k in range(n):
            a = math.tau*k/n
            fold = .11*min(w, 5*d)*math.cos(a)**2*math.sin(i*.67+k*.48)
            vertices.append(p + side*(w*math.cos(a)) + normal*(d*math.sin(a)+fold))
    faces = [tuple(reversed(range(n)))]
    for i in range(len(path)-1):
        for k in range(n):
            a, b = i*n+k, i*n+(k+1)%n
            faces.append((a, b, b+n, a+n))
    faces.append(tuple(range(len(vertices)-n, len(vertices))))
    obj = C.mesh(name, vertices, faces, mat)
    for face in obj.data.polygons:
        face.use_smooth = True


def turbine_water(m, wheel, nozzle, tray):
    wheel_tree = v3.local_bvh(wheel)
    inverse = wheel.matrix_world.inverted()
    origin = nozzle.matrix_world @ Vector((.300, 0, 0))
    direction = nozzle.matrix_world.to_quaternion() @ Vector(v3.RIGHT)
    path = [origin]
    for i in range(1, 51):
        distance = i*.018
        q = origin + direction*distance + DOWN*(distance/8)**2
        hit = v3.segment_hit(wheel_tree, inverse @ path[-1], inverse @ q)
        if hit is not None:
            break
        path.append(q)
    else:
        raise ValueError("Jet missed the evaluated wheel")
    hit = wheel.matrix_world @ hit
    if math.hypot(hit.x, hit.z-v3.AXLE) < .20:
        raise ValueError("Jet landed inside the bucket circle")
    path.append(hit)
    radii = [.0096 - .001*i/len(path) + .0004*math.sin(i*1.43) for i in range(len(path))]
    water_ribbon("Live jet • nozzle to bucket", path, radii, radii, Vector((0, 1, 0)), m["water"])

    foam = v3.dielectric("Air mixed into the splash", "e1efeb", 1.333, .17)
    foam.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = .31 if "outflow" in m else .48
    droplet = C.sphere("Spray droplet prototype", (0, 0, 0), (1, 1, 1), m["water"])
    droplet.hide_render = True

    def drops(p, stretch, r):
        o = bpy.data.objects.new("Detached spray", droplet.data)
        bpy.context.scene.collection.objects.link(o)
        o.location, o.scale = p, (r, r*.9, r*stretch.length)
        o.rotation_euler = stretch.to_track_quat("Z", "Y").to_euler()

    for j, v in enumerate((Vector((.83, -.87, .17)), Vector((1.02, -.72, .23)))):
        flight = [hit]
        for k in range(1, 50):
            t = k*.014
            q = hit + v*t + DOWN*t*t
            contact = v3.segment_hit(tray, flight[-1], q)
            if contact is not None:
                break
            flight.append(q)
        else:
            raise ValueError("Discharge missed the receiving tray")
        if j == 0:
            landing = contact
        film = flight[:len(flight)//2+1]
        u = [i/(len(film)-1) for i in range(len(film))]
        water_ribbon("Split sheet off the bronze cup", film, [.004+.012*math.sin(math.pi*t)+.002*t for t in u],
                     [.0021-.0014*t for t in u], Vector((0, 1, 0)), m["water"])
        for i in range(35):
            age = RNG.uniform(.055, t-.012)
            velocity = v + Vector((RNG.uniform(-.25, .25), RNG.uniform(-.13, .13), RNG.uniform(-.15, .25)))
            pos = hit + velocity*age + DOWN*age**2
            if pos.z > contact.z+.008:
                drops(pos, (velocity+DOWN*2*age).normalized()*RNG.uniform(1.1, 2.7), RNG.uniform(.0017, .0041))

    # Interpolate along the actual channel floor from the measured splashdown to the lip.
    course = [landing + Vector((0, 0, .004))]
    for centre, _, _ in FLUME:
        if centre[1] < landing.y:
            course.append(Vector(centre)+Vector((0, 0, .004)))
    film = [a.lerp(b, j/8) for a, b in zip(course, course[1:]) for j in range(8)] + [course[-1]]
    discharge = m.get("outflow", m["water"])
    water_ribbon("Collected water in the tailrace", film, [.045+.005*math.sin(i*.47) for i in range(len(film))],
                 [.005]*len(film), Vector(v3.RIGHT), discharge)
    us = [i/34 for i in range(35)]
    fall = [course[-1]+OUTLET_SPEED*(u*FALL_TIME)+DOWN*(u*FALL_TIME)**2 for u in us]
    widths = [.045-.029*u+.002*math.sin(13*u) for u in us]
    depths = [.004-.002*u for u in us]
    if "outflow" in m:
        # Area contracts in inverse proportion to speed. The free edges flutter
        # after release, while the centre stays on the measured ballistic path.
        contraction = [math.sqrt(OUTLET_SPEED.length/(OUTLET_SPEED+2*DOWN*u*FALL_TIME).length) for u in us]
        widths = [.045*c*(1+.09*math.sin(25*u)) for c, u in zip(contraction, us)]
        depths = [.005*c*(1+.12*math.sin(29*u)) for c, u in zip(contraction, us)]
        for p, u in zip(fall, us):
            p.x += .0034*math.sin(20*u)*math.sin(math.pi*u)
            p.y += .0026*math.sin(27*u)*math.sin(math.pi*u)
        spray = random.Random(1273)
        for i in range(19):
            k = spray.randrange(6, len(fall)-1)
            side = -1 if i % 2 else 1
            p = fall[k] + Vector((side*(widths[k]+spray.uniform(.001, .015)), spray.uniform(-.009, .009), 0))
            velocity = (OUTLET_SPEED+2*DOWN*us[k]*FALL_TIME).normalized()
            drops(p, velocity*spray.uniform(1.3, 2.7), spray.uniform(.0012, .0025))
    water_ribbon("Free outfall into the creek", fall, widths, depths, Vector(v3.RIGHT), discharge)
    for i in range(47):
        a, r = RNG.uniform(0, math.tau), RNG.uniform(.012, .098)
        x, y = r*math.cos(a), r*math.sin(a)
        h = RNG.uniform(.005, .054)*(1-r/.11)
        drops(IMPACT+Vector((x, y, h)), Vector((x, y, .02)).normalized()*1.5, RNG.uniform(.0016, .0042))
    for i in range(17):
        a, r = RNG.uniform(0, math.tau), RNG.uniform(.019, .079)
        arc = [IMPACT+Vector((r*math.cos(a+k*.12), r*math.sin(a+k*.12), .005+.003*math.sin(k*.55))) for k in range(5)]
        C.strand("Aerated curl at re-entry", arc, RNG.uniform(.0012, .0028), foam)
    print(f"[step1] Cup contact {tuple(hit)}. Tray contact {tuple(landing)}.", flush=True)
    return hit


def camera(scene, hit, rig=None):
    lens = 40 if rig is not None else 46
    cam = bpy.data.objects.new(f"Creek • {lens} mm", bpy.data.cameras.new("Field lens"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    if rig is None:
        cam.location, aim_at = (.80, -4.08, 1.68), (-.08, -.13, .68)
    else:
        cam.location, aim_at = (.96, -4.10, 1.64), (-.42, -.01, .80)
    cam.rotation_euler = (Vector(aim_at)-cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens, cam.data.sensor_fit, cam.data.sensor_height = lens, "VERTICAL", 32
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (hit-cam.location).length
    cam.data.dof.aperture_fstop, cam.data.dof.aperture_blades = (6.3 if rig is not None else 4.5), 9
    bpy.context.view_layer.update()
    points = [("nozzle swivel", v3.PIVOT), ("jet strike", hit), ("outfall", IMPACT),
              ("indicator", (.385, .258, 1.552))]
    if rig is None:
        points.append(("cap", (-.22, .48, 1.83)))
    else:
        points.extend((("helmet", rig.matrix_world @ Vector((0, 0, 1.86))),
                       ("chest", rig.matrix_world @ Vector((0, -.12, 1.34))),
                       ("gauge", bpy.data.objects["Baked enamel scale"].matrix_world.translation)))
    for label, co in points:
        u, v, z = world_to_camera_view(scene, cam, Vector(co))
        print(f"[step1] {label} at ({u:.3f}, {v:.3f})", flush=True)
        if z <= 0 or not (.045 < u < .955 and .045 < v < .955):
            raise ValueError(f"{label} outside portrait safe area")


def build_scene(revised):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fast = render_profiles.get("fast")
    scene = C.render_settings("OPTIX", width=SIZE[0], samples=fast["samples"], frames=FRAME)
    scene.render.resolution_percentage = round(100*fast["res_factor"])
    scene.render.use_simplify = True
    scene.cycles.texture_limit_render = "2048"
    scene.cycles.denoising_use_gpu = False
    scene.unit_settings.system = "METRIC"
    scene.render.fps = v3.FPS
    rig = None
    if revised:
        rig = electrician(scene)
    else:
        v3.OUT = OUTPUT.parent  # v3 stages the corrected glTF manifest here during import.
        print("[step1] Building and checking Bolts' workshop grip", flush=True)
        v3.bolts(scene)
    m = v3.materials()
    m["grip"] = v3.surface("Oiled rosewood lever", ("48251a", "905137"), (.21, .43),
                           grain=(10, 10, .5), scale=5, height=.00016, coat=.32)
    v3.thumb_oil(m["grip"])
    trestle(m, revised)
    wheel, _ = v3.runner(m)
    v3.generator(m)
    nozzle = v3.nozzle_assembly(m)
    if revised:
        # Bring the supply around the bank end of the new walk.
        hose = bpy.data.objects["Fabric reinforced feed hose"].data.splines[0].bezier_points
        hose[0].co = (-2.10, .88, ground(-2.10, .88)+.026)
        hose[1].co = (-1.42, .80, ground(-1.42, .80)+.026)
        hose[2].co = (-1.02, .62, .39)
        pressure_gauge(m)
        m["water"] = moving_water("Pressurised creek jet", (32, 145, 104), (.90, .56))
        m["outflow"] = moving_water("Tailrace • aerated falling water", (114, 83, 12), (.79, .18))
    v3.pilot(m)
    tray = scroll_and_flume(m)
    v3.finish_edges(m)
    scene.frame_set(FRAME)
    hit = turbine_water(m, wheel, nozzle, tray)
    creek(revised)
    v3.lighting(scene)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .43
    if revised:
        light = bpy.data.lights.new("Creek daylight reflected into the outfall", "AREA")
        light.shape, light.size, light.size_y = "RECTANGLE", .48, 1.65
        light.energy, light.color = 62, (.78, .91, 1)
        bounce = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(bounce)
        bounce.location = (1.02, -1.76, 1.26)
        bounce.rotation_euler = (Vector((.12, -.52, .71))-bounce.location).to_track_quat("-Z", "Y").to_euler()
    camera(scene, hit, rig)
    render_profiles.apply_fast(scene, None, {}, "cycles")
    return scene


def main():
    revised = "--step1b" in sys.argv
    output = OUTPUT.with_name("step1b_still.png") if revised else OUTPUT
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene(revised)
    scene.render.filepath = str(output)
    devices = bpy.context.preferences.addons["cycles"].preferences.devices
    print("[step1] Rendering once on", [(d.name, d.type) for d in devices if d.use],
          f"at {scene.cycles.samples} samples, threshold {scene.cycles.adaptive_threshold}", flush=True)
    start = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    print(f"[step1] Cycles render and PNG write {time.perf_counter()-start:.3f} s", flush=True)
    # The Build #1 still path uses the same in-place FAST post, without camera movement.
    subprocess.run([str(PAGE.parent / ".venv/Scripts/python.exe"), "-B", "-X", "utf8", "-c",
                    "import sys, fast_post; fast_post.process_file(sys.argv[1], sys.argv[1], (1080, 1920), None)",
                    str(output)], cwd=PAGE/"tools", check=True)
    print(f"[step1] Finished portrait including FAST post {time.perf_counter()-start:.3f} s", flush=True)


if __name__ == "__main__":
    main()

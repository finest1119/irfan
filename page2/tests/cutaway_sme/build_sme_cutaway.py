"""Mercer Hollow • Build 02 • the bench turbine. Run with Blender's -P option."""
import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Shared builders and assets are read-only, including their Python cache directories.
sys.dont_write_bytecode = True
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
PAGE = HERE.parents[1]
sys.path[:0] = [str(PAGE.parent / "pipeline/cutaway"), str(PAGE / "blender")]
import cutlib as C

FPS = 24
END = 144
STILLS = [(8, "01_dead_center"), (56, "02_at_the_rim"),
          (92, "03_on_the_bench"), (140, "04_catch_and_return")]
R = math.radians
AXLE = 1.17
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
    bevel.width, bevel.segments = min(.002, radius * .08), 2
    o.modifiers.new("Flat end normals", "WEIGHTED_NORMAL")
    return o


def arc(name, center_z, inside, outside, a0, a1, front, back, mat, edge):
    angles = [R(a0 + (a1-a0)*i/64) for i in range(65)]
    outline = [(r*math.cos(a), center_z+r*math.sin(a))
               for r, path in [(outside, angles), (inside, reversed(angles))] for a in path]
    return C.section(name, outline, front, back, mat, edge)


def materials():
    mats = {
        "teal": C.material("Petrol enamel over cast iron", "21464b", "3c6867", 18, .0018, .37, .32),
        "steel": C.material("Oiled gunmetal", "323a39", "68716e", 23, .001, .34, .76),
        "silver": C.material("Turned stainless", "bbc6c3", rough=.26, metal=.85),
        "brass": C.material("Forged bronze", "715638", "bb965e", 19, .0009, .32, .68),
        "red": C.material("Oxblood enamel", "923e29", "ad5235", 30, .0005, .32, .24),
        "rim": C.material("Freshly sectioned iron", "c48b65", rough=.42, metal=.4),
        "rubber": C.material("Hose rubber", "252e2c", rough=.64),
        "water": C.material("Water in side light", "cbe4e6", rough=.085),
        "wood": C.material("Oil darkened maple", "88623f", "bc9568", 3, .002, .54),
        "board": C.polyhaven("white_planks_clean", 1.8),
        "concrete": C.polyhaven("concrete_floor_02", 1.8),
        "green": C.material("Workshop cabinet lacquer", "3f5450", "56675e", 3, .0015, .55, .2),
    }
    # Stretch the stain into long maple fibers. A lighter cross-grain picks out
    # the bench's tool marks in the raking window light.
    wood = mats["wood"].node_tree
    grain = wood.nodes.new("ShaderNodeVectorMath")
    grain.operation = 'MULTIPLY'
    grain.inputs[1].default_value = (1.8,21,34)
    wood.links.new(wood.nodes.new("ShaderNodeTexCoord").outputs["Object"],grain.inputs[0])
    for node in wood.nodes:
        if node.type == "TEX_NOISE":
            wood.links.new(grain.outputs[0],node.inputs["Vector"])
    water = mats["water"].node_tree.nodes.get("Principled BSDF")
    water.inputs["Transmission Weight"].default_value = .79
    water.inputs["IOR"].default_value = 1.333
    return mats


def workshop(m):
    # The removed front wall exposes the cabinet, slab, and grade on the same plane.
    C.ground((-5, 5), (-.58, 3.8), -.12, layers=(
        ("Compacted fill", .25, "766d5a", "9a907b"),
        ("Clay", 1.95, "65564b", "8e7f71")), grains=6, relief=.025, roots=False)
    C.foundation("slab", (0, 1.61, -.06), (9, 4.36, .12), m["concrete"])
    C.box("Workbench cabinet", (0, .01, .336), (3.30, .79, .65), m["green"], .015)
    for x in (-1.16, -.39, .39, 1.16):
        C.box("Inset tool locker", (x, -.39, .35), (.75, .025, .54), m["green"], .01)
        C.box("Recessed finger pull", (x, -.408, .58), (.115, .013, .015), m["steel"], .005)
    C.box("Laminated butcher block", (0, -.005, .713), (3.45, .91, .095), m["wood"], .009)
    for i in range(19):
        C.box("Visible end-grain lamella", (1.721, -.434+i*.048, .713),
              (.008,.045,.091), m["wood"], .002)
    # Rear shop wall is open at the sash. Outdoors is seen through real glazing openings.
    wall_start = set(bpy.data.objects)
    for x0, x1, z0, z1 in [(-4, -.97, 0, 3), (.43, 4, 0, 3), (-.97,.43,0,1.23),(-.97,.43,2.28,3)]:
        C.bounds("Whitewashed workshop boards", x0,x1,2.12,2.23,z0,z1,m["board"])
    for x in (-.97,-.27,.43):
        C.box("Sash stile", (x,2.09,1.76), (.045,.082,1.09), m["wood"], .004)
    for z in (1.23,1.76,2.28):
        C.box("Sash rail", (-.27,2.09,z), (1.44,.08,.045), m["wood"], .004)
    C.box("Projecting sill", (-.27,2.05,1.20), (1.58,.21,.055), m["wood"], .005)
    C.box("Window header", (-.27,2.08,2.34), (1.62,.12,.095), m["wood"])
    C.box("High shelf", (.91,1.99,2.11), (.81,.27,.035), m["wood"])
    for i in range(4):
        x, h = .62+i*.14, .12 + .035*(i%2)
        turned("Oil tin", (x,1.98,2.13), (x,1.98,2.13+h), .047, m[("teal","red","steel","brass")[i]])
        turned("Oil tin rolled lid", (x,1.98,2.13+h), (x,1.98,2.137+h), .049, m["silver"])
    C.box("Wall tool strip", (.9,2.01,1.71), (.78,.04,.065), m["wood"], .004)
    for i in range(4):
        x, z = .62 + .16*i, 1.71
        C.beam("Forged wrench handle", (x,1.965,z),(x-.012,1.965,z-.2-i*.022),.022,.011,m["steel"])
        for sign in (-1,1):
            C.beam("Open wrench jaw", (x-.012,1.965,z-.19-i*.022),
                   (x-.012+sign*.022,1.965,z-.225-i*.022),.013,.013,m["silver"])
    for obj in set(bpy.data.objects)-wall_start:
        obj.location.x -= .92
    # Slotted rack with cabinetmaker's chisels and recognizable turned grips.
    C.box("Chisel rack",(-.27,1.95,1.36),(.45,.09,.045),m["wood"],.005)
    for i in range(5):
        x = -.44+.082*i
        turned("Chisel handle",(x,1.91,1.38),(x,1.91,1.49+.012*(i%2)),.024,m["red"],.016)
        turned("Ferrule",(x,1.91,1.366),(x,1.91,1.392),.019,m["brass"])
        C.box("Polished chisel blade",(x,1.91,1.29),(.018+.002*i,.005,.15),m["silver"])
    for x in (-2.05, 1.65):
        C.box("Douglas fir stud", (x,2.05,1.36), (.115,.18,2.72), m["wood"])
    C.box("Garage lintel", (0,1.93,2.64), (5,.25,.18), m["wood"], .004)
    for x in (-1.3,0,1.3):
        C.beam("Exposed joist", (x,-.55,2.63), (x,2.1,2.81), .07,.14,m["wood"])

    # Modest backyard depth seen through the window.
    sod = C.polyhaven("aerial_grass_rock", 3)
    C.box("Yard beyond sash", (0,7,-.065), (18,9,.12), sod)
    for i in range(40):
        x = -4+i*.22
        C.section("Cedar dog-ear fence", [(x,0),(x+.204,0),(x+.204,1.16),
                  (x+.18,1.19),(x+.024,1.19),(x,1.16)], 5.2, 5.24, m["wood"])
    path = C.ROOT/"assets/cc0/polyhaven/models/shrub_02/shrub_02_1k.gltf"
    bpy.ops.import_scene.gltf(filepath=str(path))
    plants = sorted((o for o in bpy.context.selected_objects if o.type == "MESH"),
                    key=lambda o:o.name)
    for i, plant in enumerate(plants):
        plant.location = (-.8-i*1.10,4.18+.18*(i%2),0)
        plant.rotation_euler.z = R(-22+i*30)


def bolts(scene):
    import characters_s9 as actor
    from mh_blender import L
    if actor.PROP_NAME != "s11":
        raise RuntimeError("The approved Bolts body requires MH_BOLTS_PROP=s11.")
    ctx = L.Ctx(scene, END, FPS, [], 0.0)
    cast = actor.build_bolts(ctx, json.loads((PAGE/"character.json").read_text())["bolts"])
    # This CC0 glTF names two existing normal maps with a duplicate PNG suffix.
    # Fix the in-memory image paths before Cycles reads the rig materials.
    for image in bpy.data.images:
        path = Path(bpy.path.abspath(image.filepath))
        if path.name.endswith("_png.png") and not path.is_file():
            source = path.with_name(path.name.replace("_png.png",".png"))
            if source.is_file():
                image.filepath = str(source)
                image.reload()
    outfit = "workshop"
    cast["outfits"][outfit].hide_render = False
    cast["masks"][outfit].show_render = cast["masks"][outfit].show_viewport = True
    rig = cast["rig"]
    rig.location = (-.59,.62,.012)
    rig.rotation_euler.z = R(27)
    cast["bake"]([(1,"scratch_beard"),(49,"idle"),(108,"thumbs_up")], 1, END, FPS)


def runner(m):
    wheel = group("Impulse runner", (0,0,AXLE))
    # All moving parts are built in runner-local coordinates in the XZ plane.
    arc("Runner annulus",0,.146,.219,0,359.98,.028,.061,m["steel"],m["steel"]).parent = wheel
    for i in range(6):
        a = math.tau*i/6
        x,z = math.cos(a),math.sin(a)
        C.beam("Cast spider spoke",(.05*x,.043,.05*z),(.19*x,.043,.19*z),
               .032,.040,m["teal"]).parent = wheel
    turned("Raised hub", (0,-.075,0),(0,.075,0), .092, m["brass"]).parent = wheel
    turned("Keeper washer", (0,-.082,0),(0,-.075,0), .060, m["silver"]).parent = wheel
    turned("Keyed axle nut", (0,-.104,0),(0,-.082,0), .037, m["steel"], sides=6).parent = wheel
    # Two concave stainless lobes share a bronze splitter on each bucket. The lips
    # sweep backward at the rim; both lobes exhaust along the axis of the shaft.
    for i in range(12):
        mount = group("Bucket and splitter")
        mount.parent = wheel
        mount.rotation_euler.y = i*math.tau/12
        for sign in (-1,1):
            verts, faces = [], []
            for j in range(9):
                u = j/8
                for k in range(7):
                    v = k/6
                    radial = .177 + .143*u - .021*v*v
                    axial = sign*(.007+.070*v*(.72+.28*math.sin(math.pi*u)))
                    sweep = -.035 + .047*u*u + .064*v - .115*math.sin(math.pi*v)*math.sin(math.pi*u)
                    verts.append((sweep,axial,radial))
                    n = len(verts)-1
                    if j and k:
                        faces.append((n-8,n-1,n,n-7))
            scoop = C.mesh("Split bronze cup", verts, faces, m["brass"])
            scoop.parent = mount
            for face in scoop.data.polygons:
                face.use_smooth = True
            wall = scoop.modifiers.new("Cast thickness", "SOLIDIFY")
            wall.thickness = .005
            # Radiused edges and the ridge between the two receiving bowls
            # catch a narrower highlight than the sand-cast bronze.
            lip = [verts[j*7+6] for j in range(9)] + [verts[-1-k] for k in range(1,7)]
            C.strand("Worn cup rim",lip,.0027,m["brass"]).parent = mount
        C.strand("Bucket splitter",[(.012,.0,.316),(-.020,0,.25),(-.035,0,.18)],
                 .0045,m["brass"]).parent = mount
        turned("Web rivet", (0,-.015,.169),(0,.031,.169), .012, m["silver"], sides=8).parent = mount
    # Clockwise seen from the cut face: the water strikes the top from the left.
    key(wheel, "rotation_euler", [(1,(0,0,0)),(27,(0,.08,0)),(51,(0,1.8,0)),
                                  (94,(0,13.4,0)),(144,(0,27.4,0))])


def generator(m):
    C.box("Common skid", (.01,.05,.785),(1.75,.60,.046),m["steel"],.01)
    for x in (-.22,.22):
        C.beam("Bearing pedestal", (x,.25,.808),(x*.26,.25,AXLE),.067,.070,m["teal"])
    turned("Runner shaft", (0,.025,AXLE),(0,.48,AXLE),.036,m["silver"])
    turned("Pillow block", (0,.20,AXLE),(0,.30,AXLE),.081,m["teal"])
    turned("Dynamo body", (0,.33,AXLE),(0,.65,AXLE),.151,m["teal"])
    for i in range(12):
        a = math.tau*i/12
        x,z = .15*math.cos(a), AXLE+.15*math.sin(a)
        C.beam("Generator cooling fin",(x,.35,z),(x,.63,z),.013,.018,m["steel"])
    C.box("Generator feet", (0,.46,.82),(.38,.40,.044),m["teal"],.009)
    C.box("Generator pedestal", (0,.47,.926),(.26,.26,.18),m["teal"],.015)
    for x in (-.76,.75):
        for y in (-.19,.29):
            turned("Skid anchor", (x,y,.804),(x,y,.822),.019,m["silver"],sides=6)


def flow(m):
    # Pivot is slightly in front of the runner. At first the stream hits the extended
    # nut; the second pose turns it onto the outer receiving lip.
    nozzle = group("Swivel at hose union", (-.72,-.084,AXLE))
    nozzle.rotation_mode = "XYZ"
    C.strand("Garden hose", [(-1.8,.22,.78),(-1.33,.17,.79),(-1.05,.00,.82),
             (-.94,-.07,.90),(-.86,-.084,1.09),(-.79,-.084,AXLE),(-.72,-.084,AXLE)], .028,m["rubber"])
    C.box("Swivel foot",(-.72,-.08,.825),(.19,.19,.046),m["teal"],.01)
    C.beam("Nozzle mounting post",(-.72,-.08,.848),(-.72,-.08,AXLE),.045,.051,m["teal"])
    turned("Swivel boss",(-.72,-.143,AXLE),(-.72,-.031,AXLE),.053,m["brass"])
    turned("Nozzle barrel", (0,0,0),(.22,0,0),.039,m["brass"],.032).parent = nozzle
    for i in range(5):
        turned("Knurled coupling land", (.025+i*.015,0,0),(.032+i*.015,0,0),
               .043,m["silver"]).parent = nozzle
    turned("Converging nozzle",(.216,0,0),(.29,0,0),.034,m["brass"],.017).parent = nozzle
    jet = turned("Jet core",(.29,0,0),(.70,0,0),.011,m["water"],.013)
    jet.parent = nozzle
    key(nozzle, "rotation_euler", [(1,(0,0,0)),(28,(0,0,0)),(52,(0,R(-23),R(4))),
                                   (144,(0,R(-23),R(4)))])
    key(jet,"scale",[(1,(1,1,1)),(28,(1,1,1)),(52,(1,1,1.10))])

    # Two timed droplet fans: the first visibly overshoots the skid; the collector
    # arrests that fan and sends the spent water into the galvanized return trough.
    spray = group("Fan of spent water", (-.052,-.05,1.435))
    for i in range(44):
        t0 = rng.uniform(0,1)
        dx,dy,dz = rng.uniform(.55,.93),rng.uniform(-.25,.09),rng.uniform(.13,.42)
        size = rng.uniform(.0035,.009)
        drop = C.sphere("Airborne spray", (0,0,0), (size*2.3,size,size), m["water"])
        drop.parent = spray
        # Range keys reset only while the drop is beneath the receiving surface.
        step = 17 + i%7
        start = 1-round(t0*step)-step
        while start <= END:
            for frac in (0,.25,.5,.75,.96):
                t = frac
                drop.location = (dx*t,dy*t,dz*t-.98*t*t)
                drop.keyframe_insert(data_path="location", frame=start+round(t*step))
            start += step
    # Water fans out in a sheet before it breaks into drops. The upper edge
    # carries a fast specular highlight all the way from the bucket to the bench.
    for i in range(3):
        verts, faces = [], []
        for j in range(23):
            t = j/22
            x = (.66+.075*i)*t
            z = (.28+.04*i)*t - (.93+.05*i)*t*t
            w = (.008+.013*math.sin(math.pi*t))*(1-.86*t)
            y = -.015-(.22+.055*i)*t
            verts.extend([(x,y-w,z-.006*math.sin(t*15+i)),
                          (x,y+w,z+.006*math.sin(t*11+i))])
            if j:
                faces.append((2*j-2,2*j,2*j+1,2*j-1))
        film = C.mesh("Broken sheet of runoff",verts,faces,m["water"])
        film.parent = spray
        film.modifiers.new("Thin water surface","SOLIDIFY").thickness=.002
    # Accumulated water lingers after the catcher slides in. The spill crosses
    # the near lip of the top well to the left of the return pail.
    wet = C.material("Wet maple highlight","776950",rough=.12,metal=.09)
    puddle = C.sphere("Puddle at front edge",(.39,-.36,.763),(.25,.093,.005),wet)
    key(puddle,"scale",[(1,(0,0,0)),(58,(0,0,0)),(92,(.25,.095,.004)),
                        (144,(.26,.10,.004))])
    drip = group("Uncaught edge spill",(.38,-.45,.765))
    for i in range(6):
        x = -.083+i*.029
        C.strand("Thin runoff",[(x,.024,0),(x,-.009,-.004),(x+.004,-.012,-.04),
                 (x+.004,-.014,-.12-.048*(i%3))],.0035+.001*(i%3),m["water"]).parent=drip
    key(drip,"scale",[(1,(0,0,0)),(65,(0,0,0)),(88,(1,1,1)),(109,(1,1,1)),
                      (128,(0,0,0))])
    key(spray, "scale", [(1,(0,0,0)),(49,(0,0,0)),(73,(1,1,1)),
                         (102,(1,1,1)),(120,(.37,.50,.50))])


def catcher(m):
    # An open guard moves along a guide into the water fan. The camera-facing
    # flange is sectioned away to expose the path from wheel to spout.
    slide = group("Sliding cast splash catcher")
    for inside,outside,front,back,mat,edge in [
        (.358,.386,-.117,.142,"teal","rim"), (.354,.397,-.133,-.115,"teal","rim"),
        (.110,.398,.125,.147,"teal","teal")]:
        arc("Cut casing and rolled lips",AXLE,inside,outside,-80,94,front,back,m[mat],m[edge]).parent = slide
    for degrees in (-65,-30,10,52,85):
        a = R(degrees)
        x,z = .377*math.cos(a), AXLE+.377*math.sin(a)
        turned("Perimeter screw",(x,-.141,z),(x,-.130,z),.009,m["steel"],sides=6).parent = slide
    C.box("Catcher shoe",(.37,.04,.847),(.14,.32,.070),m["teal"],.01).parent = slide
    C.beam("Catcher bracket",(.37,.07,.86),(.365,.07,1.13),.035,.042,m["teal"]).parent = slide
    C.box("Sliding guide",(.60,.07,.821),(.70,.18,.025),m["silver"],.005)
    key(slide,"location",[(1,(.84,0,0)),(97,(.84,0,0)),(122,(0,0,0)),(144,(0,0,0))])
    # The open U-channel bridges the front edge of the bench. Its outlet
    # overhangs the pail, leaving a visible air gap for the falling tailwater.
    start, end = Vector((.07,.00,.826)), Vector((.71,-.65,.792))
    v = end-start
    side = Vector((-v.y,v.x,0)).normalized()
    verts = [tuple(q+side*w+Vector((0,0,h))) for q in (start,end)
             for w,h in ((-.060,.035),(-.046,0),(.046,0),(.060,.035))]
    channel = C.mesh("Folded galvanized U-channel",verts,
                     [(i,i+1,i+5,i+4) for i in range(3)],m["silver"])
    channel.modifiers.new("Folded sheet","SOLIDIFY").thickness=.003
    C.box("Bucket shelf",(.72,-.61,.29),(.49,.50,.035),m["wood"],.008)
    for x in (.52,.90):
        C.beam("Shelf bracket",(x,-.40,.12),(x,-.79,.28),.018,.019,m["steel"])
    a,b = .135,.171
    x,y = .72,-.64
    rings = [(a,.31),(b,.636),(b-.005,.636),(a-.005,.319)]
    points = [(x+r*math.cos(i*math.tau/64),y+r*math.sin(i*math.tau/64),z)
              for r,z in rings for i in range(64)]
    faces = [(k*64+i,k*64+(i+1)%64,(k+1)*64+(i+1)%64,(k+1)*64+i)
             for k in range(3) for i in range(64)]
    C.mesh("Open galvanized shop pail",points,faces,m["steel"])
    for z,r in ((.329,.138),(.51,.160),(.632,.172)):
        C.strand("Pail bead",[(x+r*math.cos(i*math.tau/64),y+r*math.sin(i*math.tau/64),z)
                 for i in range(65)],.004,m["silver"])
    C.strand("Pail bail",[(x+.172*math.cos(i*math.pi/32),y-.09*math.sin(i*math.pi/32),
             .600+.117*math.sin(i*math.pi/32)) for i in range(33)],.004,m["silver"])
    stream = C.strand("Tailwater", [tuple(start+Vector((0,0,.005))),tuple(end+Vector((0,0,.005))),
             (.73,-.67,.78),(.75,-.69,.75),(.766,-.71,.69),(.78,-.73,.57)],.013,m["water"])
    pool = turned("Water caught in pail",(x,y,.548),(x,y,.551),.157,m["water"])
    for obj in (stream,pool):
        key(obj,"hide_render",[(1,True),(119,True),(120,False)])


def pilot(m):
    # A caged pilot bulb makes the output visible even with captions off.
    x,y = .55,.28
    C.strand("Dynamo lamp cable",[(.08,.49,1.23),(.25,.5,1.20),(.31,.43,.94),
             (.38,.34,.85),(x,y,.85)],.009,m["rubber"])
    turned("Pilot flange",(x,y,.807),(x,y,.847),.082,m["teal"])
    turned("Pilot stem",(x,y,.841),(x,y,1.25),.024,m["steel"])
    turned("Porcelain socket",(x,y,1.23),(x,y,1.293),.047,m["brass"])
    bulb = C.material("Pilot bulb glass", "ada288", rough=.20)
    p = bulb.node_tree.nodes.get("Principled BSDF")
    p.inputs["Emission Color"].default_value = C.color("ffbe68")
    key(p.inputs["Emission Strength"],"default_value",[(1,0),(44,0),(66,4),(144,4)])
    C.sphere("Pilot globe",(x,y,1.355),(.048,.048,.078),bulb)
    for i in range(6):
        a = i*math.tau/6
        pts = [(x+r*math.cos(a),y+r*math.sin(a),z) for r,z in
               ((.052,1.285),(.061,1.32),(.061,1.38),(.042,1.42),(.012,1.435))]
        C.strand("Lamp guard wire", pts,.0035,m["steel"])


def render(scene, preview):
    out = HERE / ("preview" if preview else "full")
    out.mkdir(exist_ok=True)
    scene.render.resolution_percentage = 25 if preview else 100
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    for frame, name in STILLS:
        scene.frame_set(frame)
        scene.render.filepath = str(out / (name+".png"))
        bpy.ops.render.render(write_still=True)
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("The hook encoder requires ffmpeg with libx264 on PATH.")
    scene.render.resolution_x, scene.render.resolution_y = 540, 960
    # At quarter size the odd 135-pixel width needs 4:4:4 for exact square pixels.
    with tempfile.TemporaryDirectory(prefix=".hook-",dir=out) as tmp:
        folder = Path(tmp)
        scene.render.filepath = str(folder / "frame_")
        bpy.ops.render.render(animation=True)
        movie = folder / "hook.mp4"
        subprocess.run([ff,"-v","error","-framerate",str(FPS),"-start_number","1",
            "-i",str(folder/"frame_%04d.png"),"-frames:v",str(END),"-an",
            "-c:v","libx264","-pix_fmt","yuv444p" if preview else "yuv420p",
            "-vf","scale=out_color_matrix=bt709","-colorspace","bt709","-color_primaries","bt709",
            "-color_trc","bt709","-crf","16","-movflags","+faststart",str(movie)],check=True)
        movie.replace(out/"hook.mp4")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = C.render_settings(width=1080, samples=4 if args.preview else 48, frames=END)
    chosen = device(scene)
    print("Cycles device:", chosen, flush=True)
    C.daylight("SME")
    scene.render.fps = FPS
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = .30
    scene.unit_settings.system = "IMPERIAL"
    scene.unit_settings.length_unit = "FEET"
    scene.view_settings.look = "AgX - Medium High Contrast"
    sun = bpy.data.lights.new("Slanting afternoon sun", "SUN")
    sun.energy, sun.angle, sun.color = 1.65, R(8), (1,.89,.73)
    sunlight = bpy.data.objects.new("Sun through the open bay",sun)
    scene.collection.objects.link(sunlight)
    sunlight.rotation_euler = Vector((.72,.50,-.86)).to_track_quat("-Z","Y").to_euler()
    m = materials()
    workshop(m)
    bolts(scene)
    runner(m)
    generator(m)
    flow(m)
    catcher(m)
    pilot(m)
    cam = None
    for frame, target, height, az, el in [
        (1,(-.045,.09,.91),3.43,15,11),
        (48,(-.15,.02,1.07),2.49,13,11),
        (88,(.22,-.02,1.04),2.53,11,12),
        (144,(.06,.02,.91),3.30,14,12)]:
        cam = C.portrait_camera(target,height,az,el,camera=cam,frame=frame)
    # Build-asset imports may set their own timeline while sampling actions.
    scene.frame_start,scene.frame_end,scene.render.fps = 1, END, FPS
    render(scene,args.preview)


if __name__ == "__main__":
    main()

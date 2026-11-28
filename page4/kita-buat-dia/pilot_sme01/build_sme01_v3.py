"""SME-01 quality pass. Run with Blender 5.3. All output is local to out_v3."""
import argparse
import ast
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "pipeline/cutaway"))
import cutlib as C

from math import cos, sin, pi, tau

rng = random.Random(1701)
V = Vector
mat = C.material
OUT = HERE / "out_v3"
FPS, FRAMES = 24, 144
RING_TEETH, COG_TEETH = 47, 23
CHAIN_PITCH = .0127
RING_RADIUS = CHAIN_PITCH/(2*sin(pi/RING_TEETH))
COG_RADIUS = CHAIN_PITCH/(2*sin(pi/COG_TEETH))


def soften(obj, width):
    bevel = obj.modifiers.new("Machined edge radius", 'BEVEL')
    bevel.width, bevel.segments, bevel.limit_method = width, 3, 'ANGLE'
    bevel.harden_normals = True
    obj.modifiers.new("Corner normals", 'WEIGHTED_NORMAL')
    return obj


def box(name, center, size, material, bevel=None):
    return soften(C.box(name, center, size, material),
                  min(.003, min(size)*.16) if bevel is None else bevel)


def beam(name, a, b, width, depth, material):
    return soften(C.beam(name, a, b, width, depth, material), min(width,depth)*.13)


def tube(name, points, radius, material):
    obj = C.strand(name, points, radius, material)
    obj.data.use_fill_caps = True
    obj.data.bevel_resolution = 3 if radius >= .009 else 2
    return obj


def section(name, points, front, back, material, cap=None):
    return soften(C.section(name, points, front, back, material, cap), min(.0016,(back-front)*.12))


def ease(lo, hi, value):
    t = min(1., max(0., (value-lo)/(hi-lo)))
    return t*t*(3-2*t)



# Local +X is Bar's left. He faces the front wheel along world -X.
SADDLE_HIP = V((-.27, 0, 1.084))
RIDER_ROT = Matrix.Rotation(-pi/2, 4, 'Z') @ Matrix.Rotation(.43, 4, 'X')
CRANK_CENTRE = V((-.37, 0, .34))
GRIP_CENTRE = (-.803, .207, 1.205)


def limb_matrices(first, second, end, root, goal, bend):
    """Two-link solve with an explicit elbow/knee plane, in armature space."""
    axis = (goal-root).normalized()
    pole = (bend-axis*bend.dot(axis)).normalized()
    upper = (second.head_local-first.head_local).length
    lower = (end.head_local-second.head_local).length
    reach = (goal-root).length
    if reach > upper+lower+.0001 or reach < abs(upper-lower):
        raise ValueError(f"{first.name} target out of reach: {reach:.3f}")
    along = (upper**2-lower**2+reach**2)/(2*reach)
    joint = root+axis*along+pole*math.sqrt(max(0, upper**2-along**2))
    def pose(bone, child, start, finish):
        rot = (child.head_local-bone.head_local).rotation_difference(finish-start)
        m = rot.to_matrix().to_4x4() @ bone.matrix_local
        m.translation = start
        return m
    return pose(first, second, root, joint), pose(second, end, joint, goal)


def set_chain(rig, names, matrices):
    parent = rig.pose.bones[names[0]].parent.matrix
    for name, matrix in zip(names, matrices):
        bone = rig.data.bones[name]
        rig.pose.bones[name].matrix_basis = bone.convert_local_to_pose(
            matrix, bone.matrix_local, parent_matrix=parent,
            parent_matrix_local=bone.parent.matrix_local, invert=True)
        parent = matrix


def fit_rider(rig):
    global RIDER_WORLD, BIKE_TO_RIG
    local_hip = rig.matrix_world @ rig.pose.bones["pelvis"].head
    RIDER_WORLD = Matrix.Translation(SADDLE_HIP) @ RIDER_ROT @ Matrix.Translation(-local_hip)
    BIKE_TO_RIG = (RIDER_WORLD @ rig.matrix_world).inverted()
    # Level his gaze over the raised bars and turn slightly toward the near grip.
    head = rig.pose.bones["Head"]
    look = Matrix.Rotation(.42,4,'Z') @ Matrix.Rotation(-.32,4,'X') @ head.matrix
    look.translation = head.head
    head.matrix = look
    for side, sign in (("l",1), ("r",-1)):
        names = [part+"_"+side for part in ("upperarm","lowerarm","hand")]
        shoulder, elbow, hand = [rig.data.bones[n] for n in names]
        # Locate the grip inside the palm, forward of the wrist.
        grip = V((GRIP_CENTRE[0], -sign*GRIP_CENTRE[1], GRIP_CENTRE[2]))
        palm_rot = Matrix.Rotation(.72,4,'X') @ Matrix.Rotation(-sign*pi/2,4,'Z')
        fingers = rig.data.bones["middle_01_"+side].head_local
        wrist = BIKE_TO_RIG @ grip - palm_rot.to_3x3() @ ((fingers-hand.head_local)*.85)
        arm = limb_matrices(shoulder, elbow, hand, rig.pose.bones[names[0]].head.copy(),
                            wrist, V((sign*.38,1,-.45)))
        palm = palm_rot @ hand.matrix_local
        palm.translation = wrist
        set_chain(rig, names, (*arm, palm))
        for digit, extra in (("index",-6),("middle",0),("ring",5),("pinky",9)):
            for joint, degrees in enumerate((32,57,43),1):
                phalanx = rig.pose.bones[f"{digit}_{joint:02d}_{side}"]
                rest = phalanx.bone.matrix_local.to_quaternion()
                flex = Quaternion((0,1,0), math.radians(sign*(degrees+extra)))
                phalanx.rotation_quaternion = rest.inverted() @ flex @ rest
    bpy.context.view_layer.update()


def rig_boots(rig,bind):
    """Return the approved boots to foot-bone space, including their laces."""
    for ob in bpy.context.scene.objects:
        if not ob.name.startswith(("Rubber outsole","Stitched welt","Leather upper","Waxed lace")):
            continue
        points=ob.data.vertices if ob.type=="MESH" else ob.data.splines[0].points
        foot="foot_l" if points[0].co.x>0 else "foot_r"
        if ob.type=="CURVE":
            bone=rig.data.bones[foot]
            ob.parent,ob.parent_type,ob.parent_bone=rig,"BONE",foot
            ob.matrix_parent_inverse=(bind[foot] @ bone.matrix_local
                                      @ Matrix.Translation((0,bone.length,0))).inverted()
            continue
        group=ob.vertex_groups.new(name=foot)
        inverse=bind[foot].inverted()
        for vertex in points:
            vertex.co=inverse @ vertex.co
        group.add(list(range(len(points))),1.,"REPLACE")
        ob.parent=rig
        modifier=ob.modifiers.new("Follow foot","ARMATURE")
        modifier.object=rig


def tailor_seated_trousers(rig):
    """Continue the approved straight legs into one sewn crotch and a closed seat."""
    cloth=bpy.data.materials["Graphite drill"]
    for old in list(bpy.context.scene.objects):
        if old.name=="Trouser seat" or old.name.startswith("Straight cut trouser leg"):
            bpy.data.objects.remove(old,do_unlink=True)
    pts,faces,weights=[],[],[]
    n=64
    def vertex(x,y,z,sign,seam=False):
        idx=len(pts)
        pts.append((x,y,z))
        leg=ease(.455,.575,z)
        pelvis=ease(.735,.944,z)
        if seam:
            pelvis=max(.60,pelvis)
        influence={"pelvis":pelvis}
        sides=(("l",.5),("r",.5)) if seam else ((("l" if sign==1 else "r"),1.),)
        ankle=.88*(1-ease(.17,.285,z))
        for suffix,share in sides:
            influence["thigh_"+suffix]=(1-pelvis)*leg*share
            influence["calf_"+suffix]=(1-pelvis)*(1-leg)*(1-ankle)*share
            influence["foot_"+suffix]=ankle*share
        weights.append(influence)
        return idx
    def join(low,high):
        for j in range(len(low)):
            k=(j+1)%len(low)
            faces.append((low[j],low[k],high[k],high[j]))
    levels=((.160,.076,.087,.048),(.167,.079,.089,.048),(.176,.078,.088,.049),
            (.193,.075,.085,.052),(.320,.078,.090,.063),(.418,.084,.094,.053),
            (.468,.088,.094,.042),(.506,.083,.090,.035),(.548,.088,.094,.037),
            (.600,.094,.100,.040),(.700,.106,.110,.046),(.772,.112,.119,.048))
    upper,shared={},{}
    for sign in (1,-1):
        prev=None
        for z,rx,ry,cy in levels:
            ring=[]
            for j in range(n):
                a=tau*j/n
                crease=.0018*cos(3*a+.7)+.0009*cos(7*a+11*z)
                ring.append(vertex(sign*.113+(rx+crease)*cos(a),cy+(ry+crease)*sin(a),
                                   z+.0028*cos(3*a+.7),sign))
            if prev:
                join(prev,ring)
            prev=ring
        ring=[]
        for j in range(n):
            l=j if sign==1 else (n//2-j)%n
            a=l*tau/n
            on_seam=24<=l<=40
            if on_seam and l in shared:
                ring.append(shared[l])
                continue
            if on_seam:
                x,y=0.,.043+.148*sin(a)
                z=.793+.096*(abs(sin(a))/.7071)**1.65
            else:
                trans=ease(.615,.75,-cos(a))
                x=sign*(.104+.120*cos(a))*(1-trans)
                y=.043+.148*sin(a)
                z=.901-.020*cos(a)
            idx=vertex(x,y,z,sign,on_seam)
            ring.append(idx)
            if on_seam:
                shared[l]=idx
        join(prev,ring)
        upper[sign]=ring
    # The two medial arcs share edges below. Their outer arcs form the waist opening.
    outline=[upper[1][j%n] for j in range(40,n+25)]+[upper[-1][j] for j in range(9,56)]
    base=[pts[i] for i in outline]
    for z,rx,ry in ((.940,.207,.145),(.978,.203,.143),(1.024,.201,.144),(1.044,.200,.143)):
        next_ring=[]
        for j,(x,y,_) in enumerate(base):
            a=tau*j/len(base)-pi/2
            if z==.940:
                x,y=.28*x+.72*rx*cos(a),.28*y+.72*(.039+ry*sin(a))
            else:
                x,y=rx*cos(a),.039+ry*sin(a)
            next_ring.append(vertex(x,y,z,1 if x>=0 else -1))
        join(outline,next_ring)
        outline=next_ring
    ob=C.mesh("Riding trousers • graphite drill",pts,faces,cloth)
    for face in ob.data.polygons:
        face.use_smooth=True
    groups={name:ob.vertex_groups.new(name=name) for name in ("pelvis","thigh_l","thigh_r","calf_l","calf_r","foot_l","foot_r")}
    for j,influence in enumerate(weights):
        for name,w in influence.items():
            if w:
                groups[name].add([j],w,'REPLACE')
    ob.parent=rig
    arm=ob.modifiers.new("Pedalling legs","ARMATURE")
    arm.object=rig
    rounded=ob.modifiers.new("Ease the stitched seat","SUBSURF")
    rounded.levels=rounded.render_levels=1
    ob.modifiers.new("Drill cloth thickness","SOLIDIFY").thickness=.0013
    # The source colours covered anatomy as clothing. Keep it under the continuous garment.
    body=bpy.data.objects["SuperHero_Male"]
    group=body.vertex_groups.new(name="Above trouser waistband")
    rest=body.data.attributes["Bar rest position"]
    group.add([j for j,item in enumerate(rest.data) if item.vector.z>1.022],1.,'REPLACE')
    mask=body.modifiers.new("Inside workwear","MASK")
    mask.vertex_group=group.name
    bpy.context.view_layer.objects.active=body
    bpy.ops.object.modifier_move_to_index(modifier=mask.name,index=0)
    apron=bpy.data.objects["Draped clay canvas apron"]
    apron.modifiers.new("Canvas hem thickness","SOLIDIFY").thickness=.0017


def ankle_pitch(angle, sign):
    return .045*sin(angle + (.22 if sign==1 else pi+.22))


def pedal_pose(angle):
    for side,sign in (("l",1),("r",-1)):
        names = [part+"_"+side for part in ("thigh","calf","foot")]
        thigh, calf, foot = [RIG.data.bones[n] for n in names]
        platform = CRANK_CENTRE + Matrix.Rotation(angle,3,'Y') @ V((sign*.116,-sign*.13,-sign*.109))
        # The contact is under the ball of the level boot, on the pedal's top face.
        pitch = Matrix.Rotation(ankle_pitch(angle,sign),4,'Y')
        flat = BIKE_TO_RIG.to_quaternion().to_matrix().to_4x4() @ pitch @ Matrix.Rotation(-pi/2,4,'Z')
        sole = V((sign*.114,-.080,.009))
        ankle = BIKE_TO_RIG @ (platform+pitch.to_3x3() @ V((0,0,.011))) - flat.to_3x3() @ (sole-foot.head_local)
        leg = limb_matrices(thigh, calf, foot, RIG.pose.bones[names[0]].head.copy(),
                            ankle, V((sign*.09,-1,0)))
        shoe = flat @ foot.matrix_local
        shoe.translation = ankle
        set_chain(RIG, names, (*leg, shoe))


def make_lap_shapes(count=20):
    """Fit one revolution of the apron and both stitched edges to the evaluated thighs."""
    panels, thighs = [], []
    for ob in bpy.context.scene.objects:
        if ob.name.startswith("Riding trousers"):
            thighs.append(ob)
        if ob.name.startswith(("Draped clay canvas apron","Bound apron edge","Topstitch")):
            points = ob.data.vertices if ob.type=='MESH' else ob.data.splines[0].points
            selected = []
            for i,pt in enumerate(points):
                rest = V(pt.co[:3])
                if rest.z < 1.12:
                    normal = V((1.45*rest.x/.25,-.53,.84)).normalized()
                    selected.append((i,rest,normal))
            if selected:
                ob.shape_key_add(name="Tailored")
                panels.append((ob,selected,[]))
    for phase in range(count):
        angle = tau*phase/count
        pedal_pose(angle)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        legs = [BVHTree.FromObject(leg,graph) for leg in thighs]
        for ob,selected,keys in panels:
            key = ob.shape_key_add(name=f"Pedal stroke {phase:02d}",from_mix=False)
            keys.append(key)
            for idx,rest,normal in selected:
                lift = 0.
                for leg in legs:
                    hit = leg.ray_cast(rest+normal*.49,-normal,.53)[0]
                    if hit is not None:
                        lift = max(lift,(hit-rest).dot(normal)+.013)
                hem = ease(1.07,.86,rest.z)
                flutter = .0025*hem*sin(angle-.48+rest.x*11)
                key.data[idx].co = rest+normal*(lift+flutter)
    return [keys for _,_,keys in panels]


def lap_pose(angle, frame):
    for keys in LAP:
        phase = (angle/tau % 1)*len(keys)
        first = math.floor(phase)
        frac = phase-first
        for i,key in enumerate(keys):
            key.value = (1-frac if i==first else frac if i==(first+1)%len(keys) else 0.)
            if frame is not None:
                key.keyframe_insert(data_path="value",frame=frame,group="Pedal drape")


def seated_apron(point):
    # Fold the lower canvas across the lap along the same seam as its topstitch.
    x,y,z = point
    drop = max(0,1.10-z)
    angle = min(1,drop/.27)*1.37
    return (x*(1+.13*min(1,drop/.22)),y-drop*sin(angle),z+drop*(1-cos(angle)))


def bar_figure():
    path = ROOT / "page4/character_bar/build_bar_v3.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    # Park the folding rule on the stall. Both of Bar's hands hold the grips.
    end = next(i for i,n in enumerate(tree.body) if isinstance(n,ast.FunctionDef) and n.name=="workshop")
    tree.body = [n for n in tree.body[:end] if ast.unparse(n)!="OUT.mkdir(exist_ok=True)"]
    for i,n in enumerate(tree.body):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="bones" for t in n.targets):
            tree.body.insert(i,ast.parse("fit_rider(rig)").body[0])
            break
    apron = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="apronpoint")
    apron.body[-1].value = ast.Call(ast.Name("seated_apron",ast.Load()),[apron.body[-1].value],[])
    env = {"__file__":str(path),"__name__":"bar_v3_model","fit_rider":fit_rider,"seated_apron":seated_apron}
    exec(compile(ast.fix_missing_locations(tree),str(path),"exec"),env)
    rig = env["rig"]
    rig_boots(rig,env["bones"])
    tailor_seated_trousers(rig)
    beard = bpy.data.objects.get("Trimmed beard fibres")
    if beard:
        head = rig.pose.bones["Head"]
        beard.parent,beard.parent_type,beard.parent_bone = rig,'BONE',head.name
        beard.matrix_parent_inverse = (rig.matrix_world @ head.matrix
                                       @ Matrix.Translation((0,head.length,0))).inverted()
    # Seal the open outsoles at the contact face, retaining the approved boot uppers.
    import bmesh
    for ob in (o for o in bpy.context.scene.objects if o.name.startswith("Rubber outsole")):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        boundary = [e for e in bm.edges if e.is_boundary]
        bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(ob.data)
        bm.free()
    root = empty("Bar • v3 • riding", (0,0,0))
    ruler = empty("Bar's folding rule on the counter", (.44,1.19,.930))
    ruler.rotation_euler = Matrix((env["across"],env["up"],env["axis"])).to_euler()
    for ob in list(bpy.context.scene.objects):
        if ob.parent is None and ob not in (root,ruler):
            if ob.name.startswith(("Yellow folding rule","Millimetre graduations","Scale numeral","Ruler pivot")):
                ob.parent = ruler
                ob.location -= env["grip"]
            else:
                ob.parent = root
    root.matrix_world = RIDER_WORLD
    return rig


def device(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = 'METAL'
        available = prefs.get_devices_for_type('METAL')
    except (TypeError, RuntimeError):
        available = []
    if any(d.type == 'METAL' for d in available):
        for d in available:
            d.use = d.type in {'METAL', 'CPU'}
        scene.cycles.device = 'GPU'
        enabled = ", ".join(f"{d.type} ({d.name})" for d in available if d.use)
    else:
        scene.cycles.device = 'CPU'
        enabled = "CPU"
    print("Cycles devices:", enabled, flush=True)


def empty(name, at):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = at
    return obj


def mount(obj, parent):
    # All animation pivots have identity rotation/scale at assembly time.
    obj.location -= parent.location
    obj.parent = parent
    return obj


def lathe(name, at, profile, material, sides=64, axis="Z", teeth=0, flutes=0, flute_fade=None):
    """Closed/open turned sections. Profiles run around the solid in r/z."""
    verts, faces, rings = [], [], []
    for k,(radius,h) in enumerate(profile):
        if radius <= .002 and k in (0,len(profile)-1):
            rings.append([len(verts)])
            verts.append((0,0,h))
            continue
        ring = []
        for j in range(sides):
            t = tau*j/sides
            r = radius
            if teeth and radius > .019:
                phase = (j*teeth/sides) % 1
                r *= 1 + .064*min(1,max(0,(.41-abs(phase-.5))/.18))
            # Flutes belong to the outer pressed surface. The liquid sees a round bore.
            if flutes and k < len(profile)//2:
                fade=1-ease(*flute_fade,h) if flute_fade else 1.
                r *= 1 + .015*fade*(1+cos(flutes*t))
            ring.append(len(verts))
            verts.append((r*cos(t),r*sin(t),h))
        rings.append(ring)
    pairs = list(zip(rings,rings[1:]))
    if len(rings[0])>1 and len(rings[-1])>1:
        pairs.append((rings[-1],rings[0]))
    for low,high in pairs:
        for j in range(sides):
            k=(j+1)%sides
            if len(low)==1:
                faces.append((low[0],high[k],high[j]))
            elif len(high)==1:
                faces.append((low[j],low[k],high[0]))
            else:
                faces.append((low[j],low[k],high[k],high[j]))
    area = sum(r*z2-r2*z for (r,z),(r2,z2) in zip(profile,profile[1:]+profile[:1]))
    if area < 0:
        faces = [f[::-1] for f in faces]
    obj = C.mesh(name, verts, faces, material)
    obj.location = at
    if axis == "Y":
        obj.rotation_euler.x = pi/2
    for face in obj.data.polygons:
        face.use_smooth = not teeth and sides>12 and abs(face.normal.z)<.97
    return soften(obj,.0005) if teeth else obj


def disk(name, at, radius, depth, material, axis="Y", teeth=0, sides=64):
    d = depth/2
    bevel = min(depth*.16, radius*.10)
    return lathe(name, at, [(.0001,-d),(radius-bevel,-d),(radius,-d+bevel),
                           (radius,d-bevel),(radius-bevel,d),(.0001,d)],
                 material, sides, axis, teeth)


def arc(cx,cy,cz,r,start,end,n=48):
    return [(cx+r*cos(t),cy,cz+r*sin(t)) for t in
            [start+(end-start)*i/n for i in range(n+1)]]


def hoop(name,x,y,z,r,section,material):
    return tube(name,arc(x,y,z,r,0,tau,96),section,material)


def response(material, low, high, frequency, micro=0., stretch=(1,1,1)):
    """Independent roughness and fine relief in object metres, preserving the base colour."""
    tree = material.node_tree
    nodes, link = tree.nodes, tree.links.new
    bs = nodes.get("Principled BSDF")
    coord = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    mapping = nodes.new("ShaderNodeVectorMath")
    mapping.operation = "MULTIPLY"
    mapping.inputs[1].default_value = stretch
    link(coord,mapping.inputs[0])
    def noise(scale, detail):
        n = nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value, n.inputs["Detail"].default_value = scale, detail
        link(mapping.outputs[0],n.inputs["Vector"])
        return n.outputs["Fac"]
    broad = noise(frequency,3.5)
    rough = nodes.new("ShaderNodeMapRange")
    for key,val in (("From Min",.24),("From Max",.78),("To Min",low),("To Max",high)):
        rough.inputs[key].default_value = val
    link(broad,rough.inputs["Value"])
    link(rough.outputs[0],bs.inputs["Roughness"])
    if micro:
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value,bump.inputs["Distance"].default_value = .20,micro
        if bs.inputs["Normal"].is_linked:
            link(bs.inputs["Normal"].links[0].from_socket,bump.inputs["Normal"])
        link(noise(frequency*7,2),bump.inputs["Height"])
        link(bump.outputs[0],bs.inputs["Normal"])
    return bs


def timber_grain(material):
    tree=material.node_tree
    nodes,link=tree.nodes,tree.links.new
    bs=nodes["Principled BSDF"]
    offset=nodes.new("ShaderNodeCombineXYZ")
    link(nodes.new("ShaderNodeObjectInfo").outputs["Random"],offset.inputs["X"])
    offset.inputs["Y"].default_value,offset.inputs["Z"].default_value=.23,.17
    shifted=nodes.new("ShaderNodeVectorMath")
    shifted.operation="ADD"
    link(nodes.new("ShaderNodeTexCoord").outputs["Object"],shifted.inputs[0])
    link(offset.outputs[0],shifted.inputs[1])
    # The plank cuts obliquely through the growth rings. Low-frequency runout bends the grain.
    wave=nodes.new("ShaderNodeTexWave")
    wave.wave_type,wave.rings_direction="RINGS","X"
    wave.inputs["Scale"].default_value,wave.inputs["Distortion"].default_value=20.,8.
    wave.inputs["Detail Scale"].default_value=.30
    wave.inputs["Detail"].default_value=3.
    link(shifted.outputs[0],wave.inputs["Vector"])
    rings=nodes.new("ShaderNodeValToRGB")
    for e,c in zip(rings.color_ramp.elements,("6e4b34","bc956f")):
        e.color=C.color(c)
    rings.color_ramp.elements[0].position=.20
    link(wave.outputs[0],rings.inputs[0])
    grain=nodes.new("ShaderNodeMixRGB")
    grain.inputs[0].default_value=.40
    link(bs.inputs["Base Color"].links[0].from_socket,grain.inputs[1])
    link(rings.outputs[0],grain.inputs[2])
    link(grain.outputs[0],bs.inputs["Base Color"])
    # Soft darkening and lower roughness around a previous glass ring on the serving shelf.
    local=nodes.new("ShaderNodeVectorMath")
    local.operation="SUBTRACT"
    local.inputs[1].default_value=(.989,-.114,1.0365)
    link(nodes.new("ShaderNodeNewGeometry").outputs["Position"],local.inputs[0])
    ring=nodes.new("ShaderNodeVectorMath")
    ring.operation="LENGTH"
    link(local.outputs[0],ring.inputs[0])
    stains=nodes.new("ShaderNodeValToRGB")
    ramp=stains.color_ramp
    ramp.elements.remove(ramp.elements[1])
    for i,(position,amount) in enumerate(((0.,0.),(.035,0.),(.038,.55),(.040,.72),(.042,0.))):
        e=ramp.elements.new(position) if i else ramp.elements[0]
        e.color=(amount,amount,amount,1)
    link(ring.outputs["Value"],stains.inputs[0])
    for socket,value in (("Base Color",C.color("674735")),("Roughness",(.18,.18,.18,1))):
        mix=nodes.new("ShaderNodeMixRGB")
        link(stains.outputs[0],mix.inputs[0])
        link(bs.inputs[socket].links[0].from_socket,mix.inputs[1])
        mix.inputs[2].default_value=value
        link(mix.outputs[0],bs.inputs[socket])


def enamel_wear(material):
    tree = material.node_tree
    nodes,link = tree.nodes,tree.links.new
    bs = nodes.get("Principled BSDF")
    bs.inputs["Coat Weight"].default_value = .27
    bs.inputs["Coat Roughness"].default_value = .23
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 190
    link(nodes.new("ShaderNodeTexCoord").outputs["Object"],noise.inputs["Vector"])
    edge = nodes.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value,edge.inputs["From Max"].default_value = .505,.57
    link(nodes.new("ShaderNodeNewGeometry").outputs["Pointiness"],edge.inputs["Value"])
    fleck = nodes.new("ShaderNodeMapRange")
    fleck.inputs["From Min"].default_value,fleck.inputs["From Max"].default_value = .58,.72
    link(noise.outputs["Fac"],fleck.inputs["Value"])
    product = nodes.new("ShaderNodeMath")
    product.operation="MULTIPLY"
    link(edge.outputs[0],product.inputs[0])
    link(fleck.outputs[0],product.inputs[1])
    mix=nodes.new("ShaderNodeMixRGB")
    base=bs.inputs["Base Color"]
    if base.is_linked:
        link(base.links[0].from_socket,mix.inputs[1])
    else:
        mix.inputs[1].default_value=base.default_value
    mix.inputs[2].default_value=C.color("706c5f")
    link(product.outputs[0],mix.inputs[0])
    link(mix.outputs[0],base)


def fingerprint(glass):
    # A single handled patch on the front face, confined to thumbprint scale.
    tree=glass.node_tree
    nodes,link=tree.nodes,tree.links.new
    bs=nodes.get("Principled BSDF")
    rel=nodes.new("ShaderNodeVectorMath")
    rel.operation="SUBTRACT"
    link(nodes.new("ShaderNodeTexCoord").outputs["Object"],rel.inputs[0])
    rel.inputs[1].default_value=(.018,-.085,.15)
    elliptic=nodes.new("ShaderNodeVectorMath")
    elliptic.operation="MULTIPLY"
    elliptic.inputs[1].default_value=(1.,.8,.63)
    link(rel.outputs[0],elliptic.inputs[0])
    length=nodes.new("ShaderNodeVectorMath")
    length.operation="LENGTH"
    link(elliptic.outputs[0],length.inputs[0])
    fade=nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value,fade.inputs["From Max"].default_value=.007,.019
    fade.inputs["To Min"].default_value,fade.inputs["To Max"].default_value=.65,0.
    link(length.outputs["Value"],fade.inputs["Value"])
    wave=nodes.new("ShaderNodeTexWave")
    wave.wave_type,wave.rings_direction="RINGS","Y"
    wave.inputs["Scale"].default_value,wave.inputs["Distortion"].default_value=240.,2.
    link(elliptic.outputs[0],wave.inputs["Vector"])
    ridge=nodes.new("ShaderNodeMath")
    ridge.operation="MULTIPLY"
    link(fade.outputs[0],ridge.inputs[0])
    link(wave.outputs[0],ridge.inputs[1])
    blend=nodes.new("ShaderNodeMixRGB")
    link(bs.inputs["Roughness"].links[0].from_socket,blend.inputs[1])
    blend.inputs[2].default_value=(.24,.24,.24,1)
    link(ridge.outputs[0],blend.inputs[0])
    link(blend.outputs[0],bs.inputs["Roughness"])


def workwear_finish():
    for name in ("Indigo cotton twill","Rolled reverse denim","Clay canvas","Graphite drill"):
        material=bpy.data.materials[name]
        bs=response(material,.57,.82,130,.00013,(1.4,1.,2.7))
        bs.inputs["Sheen Weight"].default_value=.21
    response(bpy.data.materials["Oiled work leather"],.30,.56,80,.00020)
    skin=bpy.data.objects["SuperHero_Male"].data.materials[0]
    bs=response(skin,.36,.55,105,.00007)
    bs.inputs["Subsurface Weight"].default_value=.13
    bs.inputs["Subsurface Scale"].default_value=.0027
    bs.inputs["Subsurface Radius"].default_value=(1.,.42,.22)


def palette():
    p = {
        "enamel":mat("Bottle-green powder coat","154e50","357774",8,.0007,rough=.32,metal=.46),
        "deep":mat("Deep petrol enamel","12383b",rough=.32,metal=.45),
        "paint":mat("Celadon enamel","82a79e","acc9b6",21,.0006,rough=.37,metal=.26),
        "rubber":mat("Carbon rubber","1c2323","303532",95,.0006,rough=.82),
        "steel":mat("Machined stainless","afbabb",rough=.27,metal=.86),
        "iron":mat("Blackened fittings","39413f",rough=.43,metal=.73),
        "chalk":mat("Tyre chalk","f2edda",rough=.85),
        "trace":mat("Power path • #F4BA49","f4ba49",rough=.42),
        "red":mat("Fresh watermelon flesh","c72a42","fa655e",85,.0007,rough=.28),
        "pith":mat("Watermelon pith","dfe7b4",rough=.5),
        "seed":mat("Watermelon seeds","351c14",rough=.26),
        "foam":mat("Melon froth","f79887","ffd3a7",75,.0005,rough=.49),
        "juice":mat("Cold-pressed melon","d13950","f46762",65,.0004,rough=.21),
        "wood":mat("Meranti counter","684631","b18054",4,.0014),
        "cane":mat("Split cane","997044","c49860",17,.0005),
        "canvas":mat("Shadowed cart canvas","294e50","314f50",160,.00015,rough=.86),
        "awning":mat("Petrol canvas","285e61","427778",38,.001),
        "linen":mat("Unbleached canvas","cfc5a7","ece1c4",48,.0007)
    }
    yellow = p["trace"].node_tree.nodes["Principled BSDF"]
    yellow.inputs["Emission Color"].default_value = C.color("f4ba49")
    yellow.inputs["Emission Strength"].default_value = .24
    for key in ("red","juice"):
        bs=p[key].node_tree.nodes.get("Principled BSDF")
        bs.inputs["Subsurface Weight"].default_value=.10
        bs.inputs["Subsurface Scale"].default_value=.005
    wood=p["wood"].node_tree
    stretch=wood.nodes.new("ShaderNodeVectorMath")
    stretch.operation="MULTIPLY"
    stretch.inputs[1].default_value=(1,15,21)
    wood.links.new(wood.nodes.new("ShaderNodeTexCoord").outputs["Object"],stretch.inputs[0])
    for node in wood.nodes:
        if node.type=="TEX_NOISE":
            wood.links.new(stretch.outputs[0],node.inputs["Vector"])
    glass=mat("Pressed clear glass","f5fcf8",rough=.065)
    bs=glass.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Transmission Weight"].default_value=1
    bs.inputs["IOR"].default_value=1.50
    p["glass"]=glass
    # Give each real rind long variegated bands with ragged edges.
    rind=mat("Striped melon rind","264832",rough=.4)
    tree=rind.node_tree
    tex=tree.nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    wave=tree.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value=2.4
    wave.inputs["Distortion"].default_value=7
    wave.inputs["Detail Scale"].default_value=1.6
    tree.links.new(tex,wave.inputs["Vector"])
    ramp=tree.nodes.new("ShaderNodeValToRGB")
    for elem,c in zip(ramp.color_ramp.elements,("274b35","82965a")):
        elem.color=C.color(c)
    tree.links.new(wave.outputs["Fac"],ramp.inputs[0])
    tree.links.new(ramp.outputs[0],tree.nodes["Principled BSDF"].inputs["Base Color"])
    p["rind"]=rind
    p["water"]=mat("Condensed water","ffffff",rough=.018)
    w=p["water"].node_tree.nodes["Principled BSDF"]
    w.inputs["IOR"].default_value,w.inputs["Transmission Weight"].default_value=1.333,1.
    p["guard"]=mat("Formed polycarbonate","fcfffe",rough=.045)
    g=p["guard"].node_tree.nodes["Principled BSDF"]
    g.inputs["IOR"].default_value,g.inputs["Transmission Weight"].default_value=1.586,1.
    p["brass"]=mat("Patinated brass","7f613a","b39559",72,.00008,.34,.81)
    p["wallnut"]=mat("Vulcanised gum sidewall","564331","796042",80,.00013,.63)
    p["ink"]=mat("Fired ceramic transfer","335250",rough=.49)
    p["ivory"]=mat("Aged ivory enamel","dcd4b4","f4e5be",74,.00009,.42,.08)
    for name,lo,hi,hz,depth in (
            ("enamel",.21,.43,28,.00011),("deep",.24,.48,33,.00013),
            ("paint",.25,.48,35,.00010),("iron",.24,.54,55,.00015),
            ("rubber",.46,.80,68,.00018),("rind",.26,.49,63,.00019),
            ("red",.16,.43,112,.00034),("pith",.36,.56,115,.00018),
            ("juice",.15,.26,53,0.),("foam",.26,.44,230,.00012)):
        response(p[name],lo,hi,hz,depth)
    for name in ("enamel","deep","paint"):
        enamel_wear(p[name])
    bs=response(p["steel"],.19,.39,95,.000035,(1.,1.,7.))
    bs.inputs["Anisotropic"].default_value=.45
    response(p["wood"],.31,.58,6,.00015,(1,13,18))
    timber_grain(p["wood"])
    for name in ("canvas","awning","linen"):
        cloth=response(p[name],.64,.86,145,.00016,(1.5,1.,2.))
        cloth.inputs["Sheen Weight"].default_value=.17
    for name,weight,dist in (("red",.27,.0035),("rind",.12,.0014),
                              ("pith",.28,.0028),("juice",.15,.0026)):
        bs=p[name].node_tree.nodes["Principled BSDF"]
        bs.inputs["Subsurface Weight"].default_value,bs.inputs["Subsurface Scale"].default_value=weight,dist
        bs.inputs["Subsurface Radius"].default_value=(1.,.48,.26)
    juice=p["juice"].node_tree.nodes["Principled BSDF"]
    juice.inputs["IOR"].default_value,juice.inputs["Transmission Weight"].default_value=1.34,.085
    red=p["red"].node_tree.nodes["Principled BSDF"]
    red.inputs["Coat Weight"].default_value,red.inputs["Coat Roughness"].default_value=.24,.20
    # Fine pale cell walls in the wet flesh, with a larger scale of uneven ripeness.
    tree=p["red"].node_tree
    link=tree.links.new
    coord=tree.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    cell=tree.nodes.new("ShaderNodeTexVoronoi")
    cell.feature="DISTANCE_TO_EDGE"
    cell.inputs["Scale"].default_value=410
    link(coord,cell.inputs["Vector"])
    membrane=tree.nodes.new("ShaderNodeMapRange")
    for key,val in (("From Min",.012),("From Max",.17),("To Min",.135),("To Max",0.)):
        membrane.inputs[key].default_value=val
    link(cell.outputs["Distance"],membrane.inputs["Value"])
    pigment=tree.nodes.new("ShaderNodeMixRGB")
    link(membrane.outputs[0],pigment.inputs[0])
    link(red.inputs["Base Color"].links[0].from_socket,pigment.inputs[1])
    pigment.inputs[2].default_value=C.color("ffae9d")
    link(pigment.outputs[0],red.inputs["Base Color"])
    response(glass,.014,.043,25)
    fingerprint(glass)
    return p


def wedge(name, at, size, rotation=0):
    """Cross-cut triangular wedge with pale pith, rind and embedded seeds."""
    root=empty(name,at)
    for outer,inner,m in ((1,.93,"rind"),(.93,.855,"pith"),(.855,.001,"red")):
        points=[(size*r*sin(t),-size*r*cos(t)) for r,seq in
                ((outer,range(19)),(inner,range(18,-1,-1))) for i in seq
                for t in [-.70+1.40*i/18]]
        o=section(name+" • "+m,points,-size*.22,size*.22,P[m])
        o.parent=root
    for rot,rad in ((-.40,.64),(-.1,.48),(.17,.70),(.41,.52),(-.53,.78)):
        o=C.sphere("Embedded seed",(size*rad*sin(rot),-size*.225,-size*rad*cos(rot)),
                   (size*.027,size*.017,size*.061),P["seed"])
        o.rotation_euler.y=-rot
        o.parent=root
    root.rotation_euler.y=rotation
    return root


def canopy():
    for j in range(19):
        x=(j-9)*.31
        m=P["awning" if j%2 else "linen"]
        verts,faces=[],[]
        def panel(u,v):
            sag=sin(pi*v)*(.029+.009*cos(tau*u))+.005*sin(pi*u)
            return (x+(u-.5)*.31,.13+2.38*v,2.346+.349*v-sag)
        for v in range(13):
            for u in range(7):
                verts.append(panel(u/6,v/12))
                if v and u:
                    k=len(verts)-1
                    faces.append((k-8,k-7,k,k-1))
        sail=C.mesh("Tensioned canvas panel",verts,faces,m)
        solid=sail.modifiers.new("Double canvas","SOLIDIFY")
        solid.thickness=.0017
        top=2.346
        outline=[(x-.155,top),(x+.155,top),(x+.155,top-.080)]
        outline += [(x+.155*cos(a*pi/24),top-.080-.055*sin(a*pi/24)) for a in range(1,25)]
        section("Scalloped valance",outline,.125,.130,m)
        tube("Piped canvas hem",[(xx,.123,zz) for xx,zz in outline[2:]],.0024,m)
        tube("Felled canopy seam",[panel(0,i/12) for i in range(13)],.0019,m)
    for x in (-2.20,1.82):
        tube("Awning upright",[(x,.18,.01),(x,.18,2.35)],.021,P["steel"])
        beam("Corner brace",(x,.18,1.96),(x,.56,2.40),.022,.022,P["steel"])
    tube("Valance rail",[(-2.9,.16,2.34),(2.9,.16,2.34)],.018,P["steel"])


def location():
    road=C.polyhaven("concrete_floor_02",meters=2.2,
                     fallback=mat("Cement and sand","77766c","a69c89",43,.0008))
    bs=road.node_tree.nodes["Principled BSDF"]
    bump=road.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value,bump.inputs["Distance"].default_value=.22,.0015
    road.node_tree.links.new(bs.inputs["Base Color"].links[0].from_socket,bump.inputs["Height"])
    road.node_tree.links.new(bump.outputs[0],bs.inputs["Normal"])
    stone=road.node_tree.nodes.new("ShaderNodeMixRGB")
    stone.inputs[0].default_value=.52
    road.node_tree.links.new(bs.inputs["Base Color"].links[0].from_socket,stone.inputs[1])
    stone.inputs[2].default_value=C.color("9b9589")
    road.node_tree.links.new(stone.outputs[0],bs.inputs["Base Color"])
    box("Shaded pavement",(0,0,-.05),(60,60,.1),road)
    for x in (-3.1,-1.55,.0,1.55,3.1):
        tube("Shallow slab joint",[(x,-4,-.001),(x,4,-.001)],.0028,P["iron"])

    wall=mat("Sun-washed lime plaster","c7b59e","dfd0b8",3.2,.00085)
    C.weathering(wall,grade=.19,reach=.45,strength=.44)
    box("Shophouse across the lane",(0,4.8,2.35),(32,.28,5.2),wall)
    box("Limewash plinth",(0,4.60,.20),(32,.15,.40),P["paint"])
    tube("Plinth drip edge",[(-16,4.51,.402),(16,4.51,.402)],.012,P["deep"])
    for x in (-3.65,-1.69,.55,3.72):
        box("Dark recessed window",(x,4.62,1.64),(1.42,.12,1.42),P["deep"],.02)
        for i in range(10):
            o=box("Painted louvre",(x,4.51,1.05+i*.13),(1.31,.057,.105),P["paint"],.005)
            o.rotation_euler.x=-.28
        box("Centre stile",(x,4.47,1.63),(.052,.05,1.40),P["deep"])
        box("Plaster sill",(x,4.46,.92),(1.57,.25,.095),wall,.012)
    canopy()
    # A palm at the roadside casts broken shadows on the canvas and plaster.
    leaf=mat("Oil palm fronds","304e37","688255",9,.0008)
    bs=response(leaf,.34,.58,85,.00011)
    bs.inputs["Subsurface Weight"].default_value,bs.inputs["Subsurface Scale"].default_value=.17,.0010
    for ix,(x,y,h) in enumerate(((-2.35,3.3,2.62),(2.55,3.15,2.95))):
        stem=V((x+.13,y,0))
        tip=V((x-.10,y,h))
        ferrule("Tapered palm trunk",stem,tip,[(.089,0),(.077,.12),(.059,.63),(.049,1.)],P["wood"])
        for i in range(2,20):
            u=i/20
            mid=stem.lerp(tip,u)
            r=.083-.034*u
            ferrule("Old frond scar",mid,mid+V((-.001,0,.018)),
                    [(r,0),(r+.003,.2),(r+.002,.6),(r-.001,1)],P["wood"])
        verts,faces=[],[]
        for j in range(13):
            a=tau*j/13+.5*ix
            points=[]
            for i in range(23):
                u=i/22
                mid=V((x-.1+1.44*u*cos(a),y+1.44*u*sin(a),h+.39*sin(u*pi)-.35*u))
                points.append(mid)
                if i in (0,22):
                    continue
                for side in (-1,1):
                    length=.34*sin(pi*u)**.54+.03
                    off=V((-sin(a)*side,cos(a)*side,-.65))*length
                    tip=mid+off+V((.18*cos(a),.18*sin(a),-.09))
                    w=V((cos(a),sin(a),0))*.022
                    ridge=mid.lerp(tip,.45)
                    k=len(verts)
                    verts.extend((mid,ridge+w,ridge+V((0,0,.013)),ridge-w,tip))
                    faces.extend([(k,k+1,k+2),(k,k+2,k+3),(k+1,k+4,k+2),(k+2,k+4,k+3)])
            tube("Leaf rib",points,.004,leaf)
        spray=C.mesh("Folded palm leaflets",verts,faces,leaf)
        spray.modifiers.new("Leaf lamina","SOLIDIFY").thickness=.00065
    # Rear display and short serving shelf leave the bicycle in front in silhouette.
    for j in range(4):
        box("Folding table plank",(.7,.92+j*.115,.89),(2.44,.112,.05),P["wood"],.006)
    for x in (-.32,1.73):
        for y1,y2 in ((.90,1.33),(1.33,.90)):
            beam("Table trestle",(x,y1,.010),(x,y2,.87),.04,.035,P["iron"])
            box("Trestle foot pad",(x,y1,.007),(.045,.046,.014),P["rubber"])
    for j in range(3):
        box("Service shelf",(1.12,-.15+j*.115,1.016),(.72,.113,.041),P["wood"],.005)
    # One contiguous cart on four rubber feet. Keep the rear tyre in silhouette.
    for x in (.79,1.45):
        for row in range(3):
            y=-.15+row*.115
            disk("Flush shelf screw",(x,y,1.0365),.0039,.0008,P["brass"],axis="Z")
            tube("Slotted countersink",[(x-.0026,y-.0007,1.03698),(x+.0026,y+.0007,1.03698)],.00038,P["iron"])
    for x in (.79,1.46):
        for y in (-.17,.09):
            beam("Cart leg",(x,y,.018),(x,y,1.00),.028,.028,P["deep"])
            box("Cart foot",(x,y,.012),(.048,.045,.024),P["rubber"])
        beam("Shelf cleat",(x,-.208,.987),(x,.139,.987),.033,.037,P["iron"])
    box("Canvas counter apron",(1.125,-.180,.77),(.663,.004,.395),P["canvas"])
    for z in (.577,.957):
        tube("Sewn canvas hem",[(.793,-.183,z),(1.458,-.183,z)],.0025,P["canvas"])
    for x in (.80,1.45):
        for z in (.59,.946):
            disk("Canvas brass eyelet",(x,-.184,z),.006,.004,P["brass"])
    beam("Cart stretcher",(.79,-.17,.25),(1.46,-.17,.25),.025,.025,P["deep"])
    for x,y in ((.98,1.03),(-.31,1.01)):
        basket(x,y,.917)
    # A cut wedge rests on its flat face on a chopping board.
    board=box("Oiled chopping board",(.47,.98,.925),(.32,.18,.020),P["wood"],.008)
    sample=wedge("Market sample",(.47,.97,.935+.14*.22),.14,.34)
    sample.rotation_euler=(pi/2,0,.28)
    market_sign()


def lettering(name, body, at, size, material, rotation=(pi/2,0,0)):
    data=bpy.data.curves.new(name,"FONT")
    data.body,data.size,data.align_x,data.align_y=body,size,"CENTER","CENTER"
    data.extrude,data.bevel_depth=.00012,.00006
    obj=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location,obj.rotation_euler=at,rotation
    data.materials.append(material)
    return obj


def market_sign():
    x,y,z=.70,1.69,2.075
    for dx in (-.33,.33):
        tube("Sign hanging strap",[(x+dx,y,2.556),(x+dx,y,z+.090)],.0035,P["iron"])
    box("Folded enamel stall sign",(x,y,z),(.87,.019,.167),P["deep"],.012)
    for zz in (z-.065,z+.065):
        tube("Painted sign keyline",[(x-.411,y-.0105,zz),(x+.411,y-.0105,zz)],.0017,P["brass"])
    lettering("Stall sign lettering","AIR  TEMBIKAI",(x,y-.011,z),.074,P["ivory"])
    for dx in (-.412,.412):
        disk("Sign corner rivet",(x+dx,y-.011,z),.0045,.003,P["brass"])


def basket(x,y,z):
    n=48
    for j in range(10):
        h=j*.014
        pts=[]
        for i in range(n*3+1):
            a=tau*i/(n*3)
            r=.137+.32*h+.0027*cos(24*a+j*pi)
            pts.append((x+r*cos(a),y+r*sin(a),z+.013+h))
        tube("Woven rotan",pts,.0048,P["cane"])
    for i in range(24):
        a=tau*i/24
        tube("Stake",[(x+r*cos(a),y+r*sin(a),z+h) for r,h in ((.134,.008),(.182,.151))],.0047,P["wood"])
    disk("Basket floor",(x,y,z+.005),.135,.010,P["cane"],axis="Z")
    for k in range(4):
        a=tau*k/3+.19
        dx,dy=(.091*cos(a),.091*sin(a)) if k<3 else (.002,-.004)
        center_z=.086 if k<3 else .214
        melon=C.sphere("Market watermelon",(x+dx,y+dy,z+center_z),(.079,.071,.076),P["rind"])
        melon.rotation_euler.y=rng.uniform(-.38,.38)
        calyx=C.sphere("Dried blossom scar",(0,0,.992),(.081,.076,.018),P["brass"])
        calyx.parent=melon


def crank_loop(a,b,ra,rb,y):
    # External tangents of two unequal pitch circles in the wheel plane.
    ax,az=a
    bx,bz=b
    angle=math.atan2(bz-az,bx-ax)
    half=math.acos((ra-rb)/math.dist(a,b))
    upper,lower=angle+half,angle-half
    return (arc(ax,y,az,ra,upper,lower+tau,28)+arc(bx,y,bz,rb,lower,upper,28))


def tyre_skin(name,hub):
    # A closed toroidal casing, two gum sidewalls and a separate batch of moulded chevrons.
    verts,faces=[],[]
    rings,section_count=160,28
    for i in range(rings):
        a=tau*i/rings
        for j in range(section_count):
            t=tau*j/section_count
            r=.329+.0237*cos(t)
            verts.append((r*cos(a),.0248*sin(t),r*sin(a)))
    for i in range(rings):
        for j in range(section_count):
            k=i*section_count+j
            n=((i+1)%rings)*section_count
            faces.append((k,i*section_count+(j+1)%section_count,n+(j+1)%section_count,n+j))
    casing=C.mesh(name,verts,faces,P["rubber"])
    casing.parent=hub
    casing.data.materials.append(P["wallnut"])
    for k,face in enumerate(casing.data.polygons):
        angle=tau*((k%section_count)+.5)/section_count
        face.material_index=int(-.68 < cos(angle) < .21)
        face.use_smooth=True
    verts,faces=[],[]
    for i in range(96):
        for side in (-1,1):
            start=tau*(i+.42*(side==1))/96
            k=len(verts)
            for j in range(4):
                u=j/3
                t=side*(.10+1.0*u)
                for edge in (-1,1):
                    a=start-.030*u+edge*.004
                    r=.329+.0237*cos(t)
                    verts.append(((r+.0009*cos(t))*cos(a),.0257*sin(t),(r+.0009*cos(t))*sin(a)))
            for j in range(3):
                n=k+2*j
                faces.append((n,n+1,n+3,n+2))
    tread=C.mesh("Chevron tread",verts,faces,P["rubber"])
    tread.parent=hub
    tread.modifiers.new("Moulded tread depth",'SOLIDIFY').thickness=.0010


def ferrule(name,a,b,profile,material):
    delta=V(b)-V(a)
    ob=lathe(name,a,[(r,h*delta.length) for r,h in profile],material,40)
    ob.rotation_euler=delta.to_track_quat("Z","Y").to_euler()
    return ob


def chain_drive(path):
    # Sample the same closed pitch path for two alternating rows of real roller-chain links.
    # Curve factors are animated in metres travelled divided by loop length.
    data=bpy.data.curves.new("Roller-chain pitch path","CURVE")
    data.dimensions="3D"
    spline=data.splines.new("POLY")
    spline.points.add(len(path)-1)
    for pt,xyz in zip(spline.points,path):
        pt.co=(*xyz,1.)
    spline.use_cyclic_u=True
    chain=bpy.data.objects.new("Articulated roller chain",data)
    bpy.context.scene.collection.objects.link(chain)
    length=sum((V(a)-V(b)).length for a,b in zip(path,path[1:]+path[:1]))
    count=2*round(length/CHAIN_PITCH/2)
    pitch=length/count
    group=bpy.data.node_groups.new("Bicycle chain along pitch circles","GeometryNodeTree")
    group.interface.new_socket(name="Geometry",in_out="INPUT",socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry",in_out="OUTPUT",socket_type="NodeSocketGeometry")
    nodes,link=group.nodes,group.links.new
    inp=nodes.new("NodeGroupInput")
    travel=nodes.new("ShaderNodeValue")
    travel.label="Chain travel in loop lengths"
    phase=travel.outputs[0]
    result=nodes.new("GeometryNodeJoinGeometry")
    def template(outside):
        verts,faces,materials=[],[],[]
        def section_y(outline,y0,y1,material):
            start=len(verts)
            n=len(outline)
            verts.extend((x,y,z) for y in (y0,y1) for x,z in outline)
            faces.extend([tuple(start+j for j in range(n)),tuple(start+n+j for j in reversed(range(n)))])
            faces.extend((start+j,start+n+j,start+n+(j+1)%n,start+(j+1)%n) for j in range(n))
            materials.extend([material]*(n+2))
        outline=[]
        for center,base in ((pitch/2,-pi/2),(-pitch/2,pi/2)):
            for j in range(9):
                a=base+j*pi/8
                outline.append((center+.0036*cos(a),.0036*sin(a)))
        for side in (-1,1):
            y=side*(.0034 if outside else .0022)
            section_y(outline,y-.00055,y+.00055,0)
        for xx in (-pitch/2,pitch/2) if outside else ():
            pin=[(xx+.0018*cos(tau*j/10),.0018*sin(tau*j/10)) for j in range(10)]
            section_y(pin,-.0044,.0044,1)
            roller=[(xx+.0039*cos(tau*j/14),.0039*sin(tau*j/14)) for j in range(14)]
            section_y(roller,-.0016,.0016,1)
        obj=C.mesh("Outer pinned link" if outside else "Inner chain link",verts,faces,P["iron"])
        obj.data.materials.append(P["steel"])
        for f,idx in zip(obj.data.polygons,materials):
            f.material_index=idx
        soften(obj,.00022)
        obj.hide_render=True
        return obj
    def math_node(op,left,right):
        node=nodes.new("ShaderNodeMath")
        node.operation=op
        link(left,node.inputs[0])
        if isinstance(right,(int,float)):
            node.inputs[1].default_value=right
        else:
            link(right,node.inputs[1])
        return node.outputs[0]
    for row in (0,1):
        centers=nodes.new("GeometryNodeMeshLine")
        centers.inputs["Count"].default_value=count//2
        idx=nodes.new("GeometryNodeInputIndex").outputs[0]
        stepped=math_node("MULTIPLY",idx,2/count)
        offset=math_node("ADD",stepped,(row+.5)/count)
        factor=math_node("FRACT",math_node("ADD",offset,phase),0)
        sample=nodes.new("GeometryNodeSampleCurve")
        link(inp.outputs["Geometry"],sample.inputs["Curves"])
        link(factor,sample.inputs["Factor"])
        positions=nodes.new("GeometryNodeSetPosition")
        link(centers.outputs["Mesh"],positions.inputs["Geometry"])
        link(sample.outputs["Position"],positions.inputs["Position"])
        # The chain lies in XZ. A pure Y rotation keeps all the pin axes parallel.
        parts=nodes.new("ShaderNodeSeparateXYZ")
        link(sample.outputs["Tangent"],parts.inputs[0])
        angle=math_node("ARCTAN2",math_node("MULTIPLY",parts.outputs["Z"],-1),parts.outputs["X"])
        rot=nodes.new("ShaderNodeCombineXYZ")
        link(angle,rot.inputs["Y"])
        obj=nodes.new("GeometryNodeObjectInfo")
        obj.inputs["Object"].default_value=template(row==0)
        copies=nodes.new("GeometryNodeInstanceOnPoints")
        link(positions.outputs[0],copies.inputs["Points"])
        link(obj.outputs["Geometry"],copies.inputs["Instance"])
        link(rot.outputs[0],copies.inputs["Rotation"])
        link(copies.outputs[0],result.inputs[0])
    out=nodes.new("NodeGroupOutput")
    link(result.outputs[0],out.inputs["Geometry"])
    mod=chain.modifiers.new("Rollers on both pitch circles","NODES")
    mod.node_group=group
    phase.default_value=0.
    return phase,length


def wheel(name,x,z):
    hub=empty(name,(x,0,z))
    tyre_skin(name+" casing",hub)
    for rad,thick,m in ((.307,.010,"steel"),(.316,.003,"rubber")):
        mount(hoop("Tyre" if thick==.024 else "Rolled rim",x,0,z,rad,thick,P[m]),hub)
    mount(disk("Bearing shell",(x,0,z),.026,.105,P["steel"]),hub)
    for i in range(32):
        a=tau*i/32
        b=a+(.34 if i%2 else -.34)
        mount(tube("Butted spoke",[(x+.023*cos(b),(-1)**i*.042,z+.023*sin(b)),
                                    (x+.306*cos(a),0,z+.306*sin(a))],.00155,P["steel"]),hub)
    for side in (-1,1):
        mount(disk("Spoke flange",(x,side*.043,z),.028,.004,P["iron"]),hub)
        mount(disk("Axle locknut",(x,side*.055,z),.012,.013,P["steel"],sides=6),hub)
    mount(tube("Threaded valve",[(x,0,z+.283),(x,0,z+.303)],.0027,P["brass"]),hub)
    mount(tube("Valve cap",[(x,0,z+.280),(x,0,z+.287)],.0033,P["iron"]),hub)
    return hub


def bike():
    rear=(.19,.393)
    front=(-.96,.353)
    crank=(-.37,.34)
    saddle=(-.29,.884)
    head=(-.81,.81)
    wheel("Stationary front wheel",*front)
    rear_hub=wheel("Driven rear wheel",*rear)
    for a,b,r in ((head,crank,.025),(head,saddle,.023),(saddle,crank,.026)):
        start,end=V((a[0],0,a[1])),V((b[0],0,b[1]))
        tube("Brazed steel frame",[start,end],r,P["enamel"])
        for p,q in ((start,end),(end,start)):
            axis=(q-p).normalized()
            ferrule("Fillet-brazed lug",p,p+axis*.052,
                    [(r*.76,0),(r+.005,.10),(r+.003,.66),(r+.001,.91),(r,1)],P["enamel"])
            ferrule("Worn lug shore",p+axis*.044,p+axis*.046,
                    [(r+.002,0),(r+.002,1),(r,1),(r,0)],P["brass"])
    for s in (-1,1):
        for a,b in ((saddle,rear),(crank,rear),(head,front)):
            tube("Fork or stay",[(a[0],s*.018,a[1]),(b[0],s*.056,b[1])],.012,P["enamel"])
        tube("Axle nut",[(rear[0],s*.045,rear[1]),(rear[0],s*.093,rear[1])],.015,P["steel"])
    disk("Bottom bracket shell",(crank[0],0,crank[1]),.034,.14,P["enamel"])
    for y in (-.077,.077):
        disk("Bottom bracket cup",(crank[0],y,crank[1]),.025,.012,P["steel"])
    tube("Seat post",[(saddle[0],0,.87),(-.26,0,.965)],.017,P["steel"])
    C.sphere("Leather sprung saddle",(-.28,0,.967),(.135,.079,.034),P["rubber"])
    for side in (-1,1):
        tube("Bent saddle rail",[(-.375,side*.025,.961),(-.348,side*.029,.937),
                                 (-.273,side*.032,.930),(-.212,side*.037,.933),(-.196,side*.042,.959)],
             .0043,P["iron"])
    disk("Seatpost rail clamp",(-.270,0,.929),.014,.074,P["steel"])
    tube("Quill stem",[(-.81,0,.805),(-.79,0,1.15),(-.875,0,1.195)],.018,P["steel"])
    tube("Swept handlebar",[(-.79,-.216,1.205),(-.865,-.152,1.202),(-.875,0,1.195),
                             (-.865,.152,1.202),(-.79,.216,1.205)],.012,P["steel"])
    for s in (-1,1):
        tube("Rubber grip",[(-.835,s*.18,1.202),(-.771,s*.234,1.206)],.018,P["rubber"])
        grip_a,grip_b=V((-.835,s*.18,1.202)),V((-.771,s*.234,1.206))
        axis=(grip_b-grip_a).normalized()
        for i in range(10):
            center=grip_a.lerp(grip_b,(i+.4)/11)
            ferrule("Moulded grip ring",center,center+axis*.0024,
                    [(.017,0),(.0187,.20),(.019,.64),(.017,1)],P["rubber"])
        ferrule("Bar end plug",grip_b,grip_b+axis*.005,
                [(.016,0),(.018,.25),(.017,1),(.001,1)],P["iron"])
        tube("Alloy brake lever",[(-.839,s*.172,1.198),(-.855,s*.192,1.172),
                                  (-.823,s*.222,1.161),(-.803,s*.233,1.164)],.005,P["steel"])
    cable=[(-.844,-.173,1.182),(-.899,-.156,1.158),(-.936,-.137,1.108),
           (-.954,-.114,1.023),(-.954,-.083,.938),(-.944,-.055,.822),(-.933,-.042,.731)]
    tube("Black front brake housing",cable,.0038,P["rubber"])
    tube("Cable end ferrule",cable[-2:],.0040,P["iron"])
    for side in (-1,1):
        tube("Side pull brake arm",[(-.933,side*.041,.733),(-.969,side*.041,.706),
                                   (-.971,side*.027,.664)],.006,P["steel"])
        box("Rim brake pad",(-.967,side*.020,.660),(.034,.010,.011),P["rubber"])
    # The brake bridge projects from the fork crown over the tyre. Both caliper
    # arms pivot on its front bolt, with the shoes at the rim braking track.
    crown_x=head[0]+(front[0]-head[0])*(head[1]-.722)/(head[1]-front[1])
    disk("Fork crown",(crown_x,0,.722),.021,.073,P["enamel"])
    beam("Stamped brake bridge",(crown_x,0,.725),(-.938,0,.728),.030,.010,P["enamel"])
    disk("Brake bridge pivot",(-.938,0,.728),.010,.089,P["iron"])
    disk("Brake mounting washer",(-.938,-.045,.728),.009,.003,P["steel"])
    disk("Brake cap nut",(-.938,-.049,.728),.006,.006,P["iron"],sides=6)
    rotor=empty("Pedal spindle",(crank[0],0,crank[1]))
    for name,c,r,parent in (("Chainwheel",crank,RING_RADIUS-.0035,rotor),("Sprocket",rear,COG_RADIUS-.0032,rear_hub)):
        mount(disk(name,(c[0],-.065,c[1]),r,.005,P["iron"],teeth=(RING_TEETH if parent==rotor else COG_TEETH),sides=(188 if parent==rotor else 92)),parent)
    path=crank_loop(crank,rear,RING_RADIUS,COG_RADIUS,-.066)
    chain=chain_drive(path)
    pedals=[]
    for s in (-1,1):
        cx,cz=crank
        tip=(cx+s*.116,-s*.085,cz-s*.109)
        mount(beam("Crank arm",(cx,-s*.085,cz),tip,.016,.018,P["steel"]),rotor)
        pedal=box("Platform pedal",(tip[0],-s*.13,tip[2]),(.081,.087,.022),P["rubber"],.004)
        mount(pedal,rotor)
        pedals.append(pedal)
        axle=tube("Pedal spindle",[(tip[0],-s*.080,tip[2]),(tip[0],-s*.165,tip[2])],.0055,P["steel"])
        mount(axle,rotor)
        bolt=disk("Crank cap",(cx,-s*.097,cz),.010,.006,P["iron"],sides=6)
        mount(bolt,rotor)
    # Trainer has wide feet and lifts the rear tyre four cm clear of the asphalt.
    for s in (-1,1):
        for x in (.00,.43):
            beam("Trainer A-frame",(x,s*.20,.035),(.19,s*.085,.393),.027,.027,P["paint"])
        beam("Skid",(-.035,s*.20,.024),(.46,s*.20,.024),.04,.042,P["deep"])
        for xx in (-.024,.444):
            box("Trainer foot pad",(xx,s*.20,.009),(.052,.054,.018),P["rubber"])
    beam("Trainer crossfoot",(.42,-.22,.027),(.42,.22,.027),.033,.045,P["steel"])
    return rear_hub,rotor,pedals,chain


# Roller touches the tyre at their common tangent (centre distance = .353 + .061).
RX=.322
RZ=.393+math.sqrt((.353+.061)**2-(RX-.19)**2)
JX=.571
GZ=1.006


def drive():
    roller=empty("Friction roller + driver",(RX,0,RZ))
    pulley=empty("Driven pulley + bevel pinion",(JX,0,GZ))
    spindle=empty("Blade spindle",(JX,-.183,GZ))
    smooth=mount(disk("Polished worn roller",(RX,-.041,RZ),.061,.140,P["steel"]),roller)
    rubber=mount(disk("Replacement rubber sleeve",(RX,-.041,RZ),.0598,.140,P["rubber"]),roller)
    grip=[rubber]
    smooth_grooves=[]
    for y in (-.102,-.098,.015):
        ring=mount(hoop("Turned witness groove",RX,y,RZ,.0603,.0008,P["iron"]),roller)
        smooth_grooves.append(ring)
    for i in range(26):
        a=i*tau/26
        grip.append(mount(tube("Moulded grip rib",[(RX+.0589*cos(a),y,RZ+.0589*sin(a))
                                                   for y in (-.109,.027)],.0021,P["rubber"]),roller))
    # The sleeve is in front of its narrow driver pulley; its end grain,
    # tread and chalk witness are visible in the paired camera.
    mount(disk("Roller core",(RX,-.114,RZ),.022,.009,P["iron"]),roller)
    mount(tube("Roller chalk",[(RX+.022,-.114,RZ),(RX+.055,-.114,RZ)],.004,P["chalk"]),roller)
    for o,cx,cz,r in ((roller,RX,RZ,.054),(pulley,JX,GZ,.044)):
        mount(disk("Grooved sheave",(cx,.061,cz),r,.035,P["iron"]),o)
        for y in (.039,.081):
            mount(disk("Machined pulley flange",(cx,y,cz),r+.004,.004,P["iron"]),o)
            mount(hoop("Turned flange lip",cx,y-.002,cz,r+.002,.002,P["steel"]),o)
        mount(disk("Hex socket",(cx,.036,cz),.012,.011,P["steel"],sides=6),o)
        mount(tube("Chalk timing witness",[(cx+.019,.036,cz),(cx+r-.002,.036,cz)],.004,P["chalk"]),o)
    belt=crank_loop((RX,RZ),(JX,GZ),.055,.045,.061)
    belt_edge=mat("Exposed fabric ply in drive belt","938d7e",rough=.84)
    verts,faces=[],[]
    for i,point in enumerate(belt):
        tangent=(V(belt[(i+1)%len(belt)])-V(belt[i-1])).normalized()
        inward=V((-tangent.z,0,tangent.x))
        for dy,d in ((-.010,-.0018),(.010,-.0018),(.010,.0018),(-.010,.0018)):
            verts.append(V(point)+V((0,dy,0))+inward*d)
    for i in range(len(belt)):
        for j in range(4):
            now=4*i
            nxt=4*((i+1)%len(belt))
            faces.append((now+j,nxt+j,nxt+(j+1)%4,now+(j+1)%4))
    strap=C.mesh("Endless reinforced drive belt",verts,faces,P["rubber"])
    strap.data.materials.append(belt_edge)
    for i,f in enumerate(strap.data.polygons):
        f.material_index=int(i%4==3)
    soften(strap,.0005)
    mount(tube("Cross shaft",[(JX,-.192,GZ),(JX,.104,GZ)],.012,P["steel"]),pulley)
    # The mitre pair sits forward of the belt plane. Pitch cones share their
    # apex where the Y and Z shaft axes intersect.
    for o,at,axis,sign in ((pulley,(JX,-.183,GZ),"Y",-1),(spindle,(JX,-.183,GZ),"Z",1)):
        profile=[(.008,.017),(.020,.020),(.041,.041),(.041,.052),(.008,.052)]
        mount(lathe("Cut-steel mitre wheel",at,[(r,h*sign) for r,h in profile],
                    P["steel"],96,axis,teeth=16),o)
    mount(disk("Blade shaft",(JX,-.183,GZ+.083),.012,.094,P["steel"],"Z"),spindle)
    # Back, lower lip and side walls are retained in section, exposing bearings.
    profile=[(.254,.705),(.353,.712),(.679,.944),(.697,1.091),(.667,1.111),
             (.488,1.111),(.466,1.024),(.259,.848)]
    section("Cast guard • rear wall",profile,.100,.120,P["deep"])
    for a,b in ((0,1),(1,2),(2,3),(3,4),(4,5)):
        x,z=profile[a]
        xx,zz=profile[b]
        dx,dz=xx-x,zz-z
        norm=math.hypot(dx,dz)
        nx,nz=-.007*dz/norm,.007*dx/norm
        section("Guard return • exposed section",[(x,z),(xx,zz),(xx+nx,zz+nz),(x+nx,z+nz)],
                  -.123,.119,P["deep"],P["steel"])
        tube("Bright sawn edge",[(x,-.123,z),(xx,-.123,zz)],.003,P["steel"])
    # The intact transparent guard covers both stages during the hook. The
    # fixed test view removes only its front half, as an editorial section.
    cover_profile=[(.244,.702),(.353,.699),(.683,.941),(.707,1.088),
                   (.677,1.110),(.487,1.110),(.452,1.027),(.244,.85)]
    cover=C.section("Clear formed safety cover",cover_profile,-.24,-.237,P["guard"])
    for a,b in zip(cover_profile,cover_profile[1:]+cover_profile[:1]):
        lip=tube("Safety cover • rolled edge",[(a[0],-.24,a[1]),(b[0],-.24,b[1])],.0028,P["steel"])
        lip.parent=cover
        if min(a[1],b[1])>.87 or min(a[0],b[0])>.35:
            skirt=C.mesh("Formed cover return",[(a[0],-.237,a[1]),(b[0],-.237,b[1]),
                         (b[0],-.124,b[1]),(a[0],-.124,a[1])],[(0,1,2,3)],P["guard"])
            skirt.parent=cover
            skirt.modifiers.new("Two millimetre wall","SOLIDIFY").thickness=.002
    for x,z in ((.28,.740),(.65,.963),(.66,1.073)):
        disk("Guard spacer",(x,-.181,z),.006,.111,P["iron"]).parent=cover
        disk("Guard boss",(x,-.126,z),.009,.007,P["steel"],sides=6)
        head=lathe("Recessed hex cap",(x,-.239,z),
                   [(.0022,.003),(.0027,.005),(.0068,.005),(.007,.002),(.006,0),(.0022,0)],
                   P["steel"],12,"Y")
        head.parent=cover
    for s in (-1,1):
        beam("Rack upright",(.21,s*.065,.407),(.53,s*.075,.99),.017,.021,P["deep"])
        beam("Rack brace",(-.091,s*.034,.68),(.482,s*.075,.995),.015,.019,P["steel"])
        disk("Seatstay rack eyelet",(-.091,s*.039,.68),.010,.020,P["enamel"])
        disk("Rack mounting bolt",(-.091,s*.052,.68),.007,.008,P["steel"],sides=6)
    box("Bolted gearbox cradle",(.507,.012,.995),(.086,.205,.014),P["deep"],.003)
    for x in (.481,.529):
        disk("Cradle bolt",(x,.090,1.003),.0055,.005,P["steel"],axis="Z",sides=6)
    for z,r,d,m in ((1.065,.028,.015,"iron"),(1.085,.034,.009,"steel")):
        disk("Shaft bearing",(JX,-.183,z),r,d,P[m],"Z")
    # Front of the bayonet socket is sectioned, leaving a view into the blades.
    for z,r in ((1.097,.088),(1.110,.091),(1.121,.079)):
        pts=[(JX+r*cos(t),-.183+r*sin(t),z) for t in [pi*i/40 for i in range(41)]]
        tube("Sectioned locking socket",pts,.008,P["deep"])
    for xx in (JX-.076,JX+.076):
        beam("Bayonet support",(xx,-.181,1.10),(xx,.068,1.10),.012,.014,P["deep"])
        box("Bayonet locking tab",(xx,-.185,1.123),(.013,.035,.030),P["deep"],.003)
    for x,z in ((RX,RZ),(JX,GZ)):
        disk("Axle through backplate",(x,.086,z),.011,.075,P["steel"])
        disk("Rear bearing carrier",(x,.094,z),.024,.016,P["paint"])
    for i in range(4):
        a=i*pi/2+.4
        coords=[(r*cos(a)-w*sin(a),r*sin(a)+w*cos(a),h) for r,w,h in
                ((.005,-.006,.124),(.054,-.006,.135),(.064,.003,.151),(.040,.011,.138),(.005,.007,.124))]
        blade=C.mesh("Stainless cutting wing",coords,[(0,1,2,3,4)],P["steel"])
        blade.parent=spindle
        solid=blade.modifiers.new("Blade thickness","SOLIDIFY")
        solid.thickness=.0015
        soften(blade,.0004)
    witness=arc(.19,-.018,.393,.343,1.075,1.16,6)
    mount(tube("Tyre chalk stripe",witness,.007,P["chalk"]),REAR)
    return roller,pulley,spindle,[smooth,*smooth_grooves],grip,cover


def power_trace():
    # A single painted schematic follows the near crank, chain run, wheel,
    # roller, belt, right-angle transfer, vertical shaft and one blade.
    near_crank=[(-.254,-.176,.231),(-.254,-.095,.231),(-.37,-.095,.34)]
    stroke=mount(tube("Power at the crank",near_crank,.0035,P["trace"]),CRANK)
    path=[(-.37,-.095,.34),(-.38,-.077,.436),
          (.19,-.077,.440),(.19,-.032,.393),(.425,-.028,.630)]
    path+=arc(.19,-.028,.393,.342,.79,1.245,18)
    path += [(RX,-.114,RZ),(RX+.039,-.114,RZ-.041),(JX+.027,-.118,GZ-.034),
             (JX,-.121,GZ),(JX,-.196,GZ),(JX,-.196,1.130),(JX+.055,-.205,1.144)]
    return [stroke,tube("Section key • one power path",path,.0035,P["trace"])]


JY, JBASE = -.183, 1.119


def bore_radius(z):
    if z < .040:
        return .067+(.073-.067)*(z-.019)/.021
    return .073+(.103-.073)*(min(.255,z)-.04)/.215


def froth(name, cells, material):
    # Small lenticular foam cells sharing one mesh, irregular spacing and real highlights.
    verts,faces=[],[]
    for x,y,z,r in cells:
        start=len(verts)
        verts.extend(((x,y,z-r*.24),(x,y,z+r*.40)))
        for j in range(8):
            a=tau*j/8
            verts.append((x+r*cos(a),y+r*sin(a),z))
        for j in range(8):
            k,l=start+2+j,start+2+(j+1)%8
            faces.extend(((start,l,k),(start+1,k,l)))
    obj=C.mesh(name,verts,faces,material)
    for f in obj.data.polygons:
        f.use_smooth=True
    return obj


def fill_profile(height,depth):
    edge=bore_radius(height)-.00018
    return [(.001,.0202),(.0667,.0202),(bore_radius(.04)-.00018,.040),
            (edge,height-.002),(edge,height+.0014)]+[
                (edge*u,height-depth*(1-u)**2) for u in (.98,.89,.74,.59,.44,.30,.16,.04,0.)]


def juice_surface(h1):
    h0=.047
    origin=(JX,JY,JBASE)
    liquid=lathe("Pulp and juice inside the glass",origin,fill_profile(h0,.002),P["juice"],96)
    liquid.shape_key_add(name="Pool at blade")
    filled=liquid.shape_key_add(name="Drawdown under load",from_mix=False)
    k=0
    for r,z in fill_profile(h1,.039):
        if r<=.002:
            filled.data[k].co=(0,0,z)
            k+=1
        else:
            for j in range(96):
                a=j*tau/96
                filled.data[k].co=(r*cos(a),r*sin(a),z)
                k+=1
    assert k==len(filled.data)
    cells=[]
    for i in range(205):
        arm=i%3
        u=rng.random()
        radius=(.24+.71*u)*bore_radius(h1)
        a=tau*arm/3+3.6*u+rng.gauss(0,.11+.06*u)
        z=-.039*(1-radius/bore_radius(h1))**2+.00045
        cells.append((radius*cos(a),radius*sin(a),z,rng.uniform(.00042,.0018)))
    foam=froth("Pulp bubbles in the eddies",cells,P["foam"])
    foam.location=origin
    edge_radius=bore_radius(h1)
    foam_streaks("Broken ribbons of aerated juice",
                 [(2.55,1.54,.078,.046),(.54,1.42,.079,.059),(4.72,1.14,.078,.052)],
                 lambda r:-.039*(1-r/edge_radius)**2,P["foam"]).parent=foam
    return filled,foam


def clip_polyhedron(faces,normal,d):
    """Clip a convex piece of fruit by a knife plane; keep its new cut face."""
    kept,cap=[],[]
    for face in faces:
        cut=[]
        for a,b in zip(face,face[1:]+face[:1]):
            da,db=a.dot(normal)-d,b.dot(normal)-d
            if da<=0:
                cut.append(a)
            if (da<0)!=(db<0):
                pt=a.lerp(b,da/(da-db))
                cut.append(pt)
                if all((pt-p).length>1e-6 for p in cap):
                    cap.append(pt)
        if len(cut)>2:
            kept.append(cut)
    if len(cap)>2:
        center=sum(cap,V((0,0,0)))/len(cap)
        xaxis=(cap[0]-center).normalized()
        yaxis=normal.cross(xaxis).normalized()
        cap.sort(key=lambda pt:math.atan2((pt-center).dot(yaxis),(pt-center).dot(xaxis)))
        kept.append(cap)
    return kept


def cut_chunk(rand):
    """A hand-cut cube with two oblique cut faces; all dimensions are in metres."""
    x,y,z=(rand.uniform(.022,.032) for _ in range(3))
    bottom=[V((i,j,-z)) for i,j in ((-x,-y),(x,-y),(x,y),(-x,y))]
    top=[V((p.x,p.y,z)) for p in bottom]
    faces=[bottom[::-1],top]+[[bottom[j],bottom[(j+1)%4],top[(j+1)%4],top[j]] for j in range(4)]
    for _ in range(2):
        n=V((rand.uniform(-1,1),rand.uniform(-1,1),rand.uniform(.3,.95))).normalized()
        extent=abs(n.x)*x+abs(n.y)*y+abs(n.z)*z
        faces=clip_polyhedron(faces,n,extent*rand.uniform(.55,.76))
    pts,orders,indices=[],[],{}
    for face in faces:
        order=[]
        for pt in face:
            k=tuple(round(v,6) for v in pt)
            if k not in indices:
                indices[k]=len(pts)
                pts.append(pt)
            order.append(indices[k])
        orders.append(order)
    return pts,orders


def settled_fruit():
    """Settle convex cut solids inside a metre-scale vessel, using an in-memory Bullet cache."""
    rand=random.Random(147)
    main=bpy.context.scene
    setup=bpy.data.scenes.new("Loading the jug")
    bpy.context.window.scene=setup
    setup.render.fps=FPS
    proxies=[]
    bodies=[]
    placements=[]
    def rigid(obj,kind,shape):
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True)
        bpy.ops.rigidbody.object_add()
        rb=obj.rigid_body
        rb.type,rb.collision_shape=kind,shape
        rb.use_margin,rb.collision_margin=True,.00065
        rb.friction,rb.restitution=.58,.035
        obj.select_set(False)
        return rb
    try:
        bpy.ops.rigidbody.world_add()
        world=setup.rigidbody_world
        world.substeps_per_frame,world.solver_iterations=12,22
        world.point_cache.frame_start,world.point_cache.frame_end=1,128
        wall=lathe("Settling vessel", (0,0,0),
                   [(.001,.039),(.071,.039),(.104,.257),(.104,.92),(.116,.92),
                    (.116,.260),(.083,.023),(.001,.023)],P["iron"],64)
        proxies.append(wall)
        rigid(wall,"PASSIVE","MESH")
        for i in range(16):
            pts,faces=cut_chunk(rand)
            ob=C.mesh("Melon chunk collision hull",pts,faces,P["red"])
            a=.73*(i//2)+pi*(i%2)
            ob.location=(.043*cos(a),.043*sin(a),.093+.080*(i//2))
            ob.rotation_euler=tuple(rand.uniform(-.63,.63) for _ in range(3))
            rb=rigid(ob,"ACTIVE","CONVEX_HULL")
            rb.mass,rb.linear_damping,rb.angular_damping=.13,.24,.32
            proxies.append(ob)
            bodies.append(ob)
        for f in range(1,129):
            setup.frame_set(f)
        graph=bpy.context.evaluated_depsgraph_get()
        for ob in bodies:
            pose=ob.evaluated_get(graph).matrix_world.copy()
            points=[pose.to_3x3() @ v.co for v in ob.data.vertices]
            if not .035<pose.translation.z<.262:
                raise RuntimeError(f"Fruit outside the jug after settling: {pose.translation.z:.3f} m")
            placements.append((pose.translation,points,[tuple(poly.vertices) for poly in ob.data.polygons]))
    finally:
        bpy.context.window.scene=main
        for ob in proxies:
            bpy.data.objects.remove(ob,do_unlink=True)
        collection=setup.rigidbody_world.collection if setup.rigidbody_world else None
        bpy.data.scenes.remove(setup)
        if collection and not collection.users:
            bpy.data.collections.remove(collection)
    pieces,volumes=[],[]
    import bmesh
    for i,(pos,pts,faces) in enumerate(sorted(placements,key=lambda item:item[0].z)):
        ob=soften(C.mesh("Tumbled melon piece",pts,faces,P["red"]),rand.uniform(.0018,.0037))
        ob.location=pos+V((JX,JY,JBASE))
        bm=bmesh.new()
        bm.from_mesh(ob.data)
        volumes.append(abs(bm.calc_volume()))
        bm.free()
        if i%3==0:
            face=min(ob.data.polygons,key=lambda f:f.normal.y+.2*abs(f.normal.z))
            pip=C.sphere("Pip on cut face",face.center,(.0014,.0030,.0008),P["seed"])
            pip.rotation_euler=face.normal.to_track_quat("Z","Y").to_euler()
            pip.parent=ob
        pieces.append(ob)
    return pieces,volumes


def foam_streaks(name,arcs,base_height,material):
    verts,faces=[],[]
    for start,sweep,inner,outer in arcs:
        k=len(verts)
        for i in range(47):
            u=i/46
            a=start+sweep*u
            r=inner+(outer-inner)*u
            w=(.0003+.0026*sin(pi*u)**.7)*(.85+.22*sin(9*a))
            for rad in (r-w,r+w):
                verts.append((rad*cos(a),rad*sin(a),base_height(rad)+.00024))
            if i:
                j=k+2*i
                faces.append((j-2,j-1,j+1,j))
    film=C.mesh(name,verts,faces,material)
    film.modifiers.new("Pulp film","SOLIDIFY").thickness=.00012
    return film


def serving_glass():
    center=(.888,-.106,1.0405)
    cup=empty("First serving",center)
    cup.scale=(.79,)*3
    disk("Cork drinks mat",(center[0],center[1],1.0385),.062,.004,
         mat("Pressed cork","685037","a07b4f",220,.00021,.76),axis="Z")
    wall=lathe("Pressed kopitiam tumbler",(0,0,0),
               [(0,0),(.037,0),(.041,.003),(.043,.014),(.044,.032),(.054,.140),
                (.056,.161),(.057,.168),(.0565,.173),(.0538,.1735),(.0524,.171),
                (.052,.160),(.040,.026),(.036,.018),(0,.016)],P["glass"],120,flutes=12,flute_fade=(.033,.140))
    wall.parent=cup
    drink=lathe("Melon juice and meniscus",(0,0,0),
                [(0,.017),(.0358,.0182),(.0398,.026),(.05128,.154),(.05128,.1556),
                 (.0502,.1545),(.047,.154),(0,.154)],P["juice"],120)
    drink.parent=cup
    cells=[]
    for i in range(225):
        a=rng.uniform(0,tau)
        r=.050*(rng.uniform(.87,1) if i<155 else math.sqrt(rng.random()))
        a+=.6*sin(3*a)*r/.05
        rr=rng.uniform(.00035,.0017)
        cells.append((r*cos(a),r*sin(a),.1543+.0010*ease(.046,.051,r),rr))
    froth("Broken foam collar",cells,P["foam"]).parent=cup
    foam_streaks("Soft foam at the rim",[(.03,1.81,.049,.048),(2.21,.96,.049,.047),
                 (4.69,1.32,.048,.0485)],lambda r:.1544+.00065*ease(.046,.051,r),P["foam"]).parent=cup
    garnish=wedge("Notched watermelon garnish",(.041,.036,.1515),.070,pi-.40)
    garnish.parent=cup
    # Cut the actual lip arc through the wedge. The cut stops exactly on top of the rim.
    tool=lathe("Garnish notch former",(0,0,0),
               [(.049,.125),(.0588,.125),(.0588,.174),(.0523,.174)],P["iron"],96)
    tool.parent=cup
    bpy.context.view_layer.update()
    for ob in list(garnish.children):
        if ob.name.startswith("Notched watermelon garnish"):
            mod=ob.modifiers.new("Seat on rolled glass lip","BOOLEAN")
            mod.operation,mod.solver,mod.object="DIFFERENCE","EXACT",tool
            graph=bpy.context.evaluated_depsgraph_get()
            baked=bpy.data.meshes.new_from_object(ob.evaluated_get(graph))
            ob.modifiers.clear()
            ob.data=baked
    bpy.data.objects.remove(tool,do_unlink=True)
    for i in range(75):
        a=rng.uniform(-3.18,.23)
        h=rng.uniform(.034,.153)
        r=(.044+(.054-.044)*min(1,(h-.032)/.108)) if h<=.140 else .054+.002*(h-.14)/.021
        r*=1+.015*(1-ease(.033,.140,h))*(1+cos(12*a))
        size=rng.uniform(.00055,.0024)*(1.15 if i%7==0 else 1)
        bead=C.sphere("Condensation bead",((r+.00012)*cos(a),(r+.00012)*sin(a),h),
                      (size*.61,size,size*rng.uniform(1.05,1.72)),P["water"])
        bead.rotation_euler.z=a
        bead.parent=cup
    return cup


def glassware():
    at=(JX,JY,JBASE)
    # True annular floor for the sealed shaft; round inside, moulded ribs outside.
    profile=[(.0134,0),(.069,0),(.074,.003),(.076,.012),(.079,.04),(.108,.255),
             (.109,.287),(.113,.291),(.113,.296),(.110,.298),(.106,.297),(.103,.287),
             (.103,.255),(.073,.04),(.067,.019),(.0134,.019)]
    lathe("Fluted locking blender jug",at,profile,P["glass"],128,flutes=8)
    lathe("Food grade shaft seal",at,[(.0118,.001),(.014,.001),(.015,.018),(.012,.020)],P["rubber"])
    hdata=bpy.data.curves.new("Pressed handle","CURVE")
    hdata.dimensions,hdata.resolution_u,hdata.bevel_depth,hdata.bevel_resolution="3D",12,.010,4
    route=[(.101,.235),(.139,.244),(.163,.229),(.159,.176),(.148,.112),(.127,.096),(.085,.099)]
    spline=hdata.splines.new("BEZIER")
    spline.bezier_points.add(len(route)-1)
    for pt,(r,h) in zip(spline.bezier_points,route):
        pt.co=(r,.019,h)
        pt.handle_left_type=pt.handle_right_type="AUTO"
    handle=bpy.data.objects.new("Pressed glass jug handle",hdata)
    bpy.context.scene.collection.objects.link(handle)
    handle.location=at
    hdata.materials.append(P["glass"])
    # Graduations are volume-calibrated to the jug's two internal frusta, in litres.
    def litres(z):
        r=bore_radius(z)
        lower=pi*.021*(.067**2+.067*.073+.073**2)/3
        return 1000*(lower+pi*(z-.040)*(.073**2+.073*r+r*r)/3)
    for half in range(1,10):
        lo,hi=.04,.254
        for _ in range(18):
            mid=(lo+hi)/2
            if litres(mid)<half*.5:
                lo=mid
            else:
                hi=mid
        height=(lo+hi)/2
        def on_wall(t):
            r=(.079+.029*(height-.04)/.215)*(1+.015*(1+cos(8*t)))+.00035
            return V((JX+r*cos(t),JY+r*sin(t),JBASE+height))
        start=-pi/2+.13
        end=start+(.25 if half%2==0 else .12)
        tube("Kiln-fired measure",[on_wall(start+(end-start)*j/8) for j in range(9)],.00072,P["ink"])
        if not half%2:
            a=start-.125
            lettering("Litre numeral",str(half//2),on_wall(a),.0105,P["ink"],(pi/2,0,a+pi/2))
    top=JBASE+.297
    for h,r,d,m in ((.001,.114,.014,"deep"),(.012,.105,.014,"rubber"),(.024,.041,.022,"paint")):
        disk("Bayonet lid",(JX,JY,top+h),r,d,P[m],"Z")
    chunks,volumes=settled_fruit()
    # The finished fill includes the initial shallow pool and air entrained by the blades.
    target_litres=litres(.047)+sum(volumes)*1000*1.06
    lo,hi=.055,.240
    for _ in range(24):
        mid=(lo+hi)/2
        if litres(mid)<target_litres:
            lo=mid
        else:
            hi=mid
    full_height=(lo+hi)/2
    print(f"JUICE {len(chunks)} settled pieces, {target_litres:.2f} L, wall level {full_height:.3f} m",flush=True)
    return chunks,volumes,full_height,juice_surface(full_height),serving_glass()


def light(name,kind,at,aim,energy,color,size):
    data=bpy.data.lights.new(name,kind)
    data.energy,data.color=energy,color
    if kind=="SUN":
        data.angle=size
    else:
        data.size=size
    obj=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location=at
    obj.rotation_euler=(V(aim)-V(at)).to_track_quat("-Z","Y").to_euler()
    return data


def lighting():
    world=C.daylight("kita-buat-dia",rotation=2.35)
    # Use actual spherical radiance for reflections, lighting and perspective camera rays.
    # cutlib also supports a procedural sky on machines without the local HDR file.
    nodes=world.node_tree.nodes
    env=next(n for n in nodes if n.type in {"TEX_ENVIRONMENT","TEX_SKY"})
    bg=nodes.get("Background")
    world.node_tree.links.new(env.outputs[0],bg.inputs["Color"])
    bg.inputs["Strength"].default_value=.32
    soft=bpy.data.objects["Daylight through section"]
    soft.location=(-2.7,.60,4.25)
    soft.rotation_euler=(V((-.15,0,.9))-soft.location).to_track_quat("-Z","Y").to_euler()
    soft.data.energy,soft.data.size,soft.data.color=465,2.65,(1.,.84,.67)
    light("Late morning sun","SUN",(-4,-1.1,4.6),(0,.3,.25),1.92,(1,.83,.65),.12)
    light("Cool open shopfront","AREA",(-1.9,-3.3,2.28),(-.30,0,1.18),116,(.76,.87,1.),2.65)
    strip=light("Edge on the jug","AREA",(1.55,.88,2.26),(.59,-.10,1.15),115,(1.,.89,.74),.55)
    strip.shape,strip.size_y="RECTANGLE",1.55
    SCENE.view_settings.view_transform="AgX"
    SCENE.view_settings.look="AgX - Base Contrast"
    bounce=light("Juice stall bounce","AREA",(1.10,-.60,1.86),(.67,-.14,1.19),33,(1.,.94,.88),.48)
    bounce.shape,bounce.size_y="RECTANGLE",.81
    SCENE.view_settings.exposure=.09


def camera(name, pos, target, lens, focus, fstop):
    data=bpy.data.cameras.new(name)
    cam=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(cam)
    data.type,data.sensor_fit,data.sensor_height="PERSP","VERTICAL",36.
    data.lens=lens
    data.dof.use_dof,data.dof.aperture_fstop,data.dof.aperture_blades=True,fstop,9
    data.clip_start=.035
    optics(cam,pos,target,focus)
    return cam


def optics(cam,pos,target,focus):
    direction=V(target)-V(pos)
    cam.location=pos
    cam.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    cam.data.dof.focus_distance=(V(focus)-V(pos)).dot(direction.normalized())


def show(objs,enabled):
    for obj in objs:
        obj.hide_render=not enabled
        show(obj.children,enabled)


def smooth_integral(t,start,duration):
    """Integral of a smoothstep velocity ramp, in seconds."""
    t-=start
    if t<=0:
        return 0.
    if t>=duration:
        return t-duration*.5
    u=t/duration
    return duration*(u**3-.5*u**4)


def cadence(t):
    turns=(.16*t+.64*smooth_integral(t,.12,1.38)-.17*smooth_integral(t,2.45,.76)
           +.23*smooth_integral(t,3.33,.87)-.22*smooth_integral(t,5.02,.92))
    return turns+.012*(sin(2*tau*turns+.46)-sin(.46))*ease(.12,.96,t)


def drive_pose(turns,slip=1.):
    angle=2.40-turns*tau
    CRANK.rotation_euler.y=angle
    REAR.rotation_euler.y=-tau*turns*RING_TEETH/COG_TEETH
    ROLLER.rotation_euler.y=-REAR.rotation_euler.y*.353/.061*slip
    PULLEY.rotation_euler.y=ROLLER.rotation_euler.y*.055/.045
    SHAFT.rotation_euler.z=-PULLEY.rotation_euler.y
    for sign,pedal in zip((-1,1),PEDALS):
        pedal.rotation_euler.y=-angle+ankle_pitch(angle,sign)
    travel,length=CHAIN
    travel.default_value=turns*RING_TEETH*CHAIN_PITCH/length
    pedal_pose(angle)
    return angle


def contents(blend,t,serving=False):
    progress=[ease(.33*i/(len(CHUNKS)-1),.64+.36*i/(len(CHUNKS)-1),blend)
              for i in range(len(CHUNKS))]
    release=sum(volume*(1-(1-u)**3) for volume,u in zip(VOLUMES,progress))/sum(VOLUMES)
    fill=release*(1-.00046/(sum(VOLUMES)*1.06) if serving else 1.)
    FILL.value=fill
    h=.047+(FULL_HEIGHT-.047)*fill
    FOAM.location.z=JBASE+h+.00015
    FOAM.rotation_euler.z=.21*t+tau*1.15*smooth_integral(t,1.8,1.63)
    radius=(bore_radius(h)-.00018)/(bore_radius(FULL_HEIGHT)-.00018)
    FOAM.scale=(radius,radius,(.002+.037*fill)/.039)
    for i,(chunk,rest,into) in enumerate(zip(CHUNKS,LOAD,progress)):
        radius=V((rest.x-JX,rest.y-JY))
        phase=into*(1.73+.12*(i%3))
        orbit=(1-into*.80)
        chunk.location=(JX+(radius.x*cos(phase)-radius.y*sin(phase))*orbit,
                        JY+(radius.x*sin(phase)+radius.y*cos(phase))*orbit,
                        rest.z+(JBASE+.042-rest.z)*(into+.29*blend*(1-into)))
        chunk.rotation_euler=(.22*sin(pi*into+i*.8)*into,-.30*sin(pi*into),phase)
        chunk.scale=(max(.001,1-into),)*3


def gaze(t,turns):
    # A few degrees of head motion lag the power stroke. The beard follows the head bone.
    head=RIG.pose.bones["Head"]
    look=ease(.65,2.1,t)-ease(4.05,5.86,t)
    nod=.023*sin(tau*2*turns-.60)*ease(.05,1.05,t)
    head.rotation_quaternion=(HEAD_REST @ Quaternion((1,0,0),.050*look+nod)
                              @ Quaternion((0,1,0),-.045*look+.014*sin(.9*t)))


def still(beat):
    success=beat in (3,4)
    show(OLD,not success)
    show(GRIP,success)
    show([COVER],beat in (1,4))
    show(TRACE,beat in (2,3))
    show([CUP],beat==4)
    show(CHUNKS,not success)
    angle=drive_pose(0 if beat==1 else .34,.17 if beat==2 else 1.)
    lap_pose(angle,None)
    contents(float(success),2.8 if success else 0.,serving=beat==4)
    gaze(0 if beat==1 else 2.6,.34)
    SCENE.camera={1:HERO,2:PAIRED,3:PAIRED,4:PAYOFF}[beat]


def camera_move(t):
    u=ease(.10,5.91,t)
    a,b,c,d=map(V,(WIDE[0],(-1.72,-3.51,1.61),(.21,-2.07,1.40),(1.045,-1.57,1.43)))
    pos=(1-u)**3*a+3*(1-u)**2*u*b+3*(1-u)*u*u*c+u**3*d
    target=V(WIDE[1]).lerp(V((.396,-.096,.990)),ease(.24,4.12,t))
    focus=V(WIDE[3]).lerp(V((.51,-.16,1.075)),ease(.56,5.48,t))
    optics(MOV,pos,target,focus)


def contact_error():
    err=0.
    for sign,side,pedal in zip((-1,1),("r","l"),PEDALS):
        foot=RIG.pose.bones["foot_"+side]
        sole=V((sign*.114,-.080,.009))
        world_sole=RIG.matrix_world @ foot.matrix @ foot.bone.matrix_local.inverted() @ sole
        err=max(err,(world_sole-pedal.matrix_world @ V((0,0,.011))).length)
        hand=RIG.pose.bones["hand_"+side]
        fingers=RIG.data.bones["middle_01_"+side].head_local
        palm=hand.bone.head_local.lerp(fingers,.85)
        world_palm=RIG.matrix_world @ hand.matrix @ hand.bone.matrix_local.inverted() @ palm
        grip=V((GRIP_CENTRE[0],-sign*GRIP_CENTRE[1],GRIP_CENTRE[2]))
        err=max(err,(world_palm-grip).length)
    return err


def bake_motion():
    # Single native timeline for camera, rigid motion, skinning, cloth morphs, juice and chain.
    # Guard frames allow the centred shutter to sample both sides of frames 1 and 144.
    show(OLD,False)
    show(GRIP,True)
    show([COVER],True)
    show(TRACE,False)
    show([CUP],False)
    show(CHUNKS,True)
    SCENE.camera=MOV
    bones=[RIG.pose.bones[p+"_"+s] for s in ("l","r") for p in ("thigh","calf","foot")]
    previous={}
    contacts=0.
    max_handle_x=0.
    for f in range(0,FRAMES+2):
        SCENE.frame_set(f)
        t=(f-1)/FPS
        turns=cadence(t)
        angle=drive_pose(turns)
        lap_pose(angle,f)
        gaze(t,turns)
        contents(ease(1.49,5.30,t),t)
        camera_move(t)
        for obj in (CRANK,REAR,ROLLER,PULLEY,SHAFT,*PEDALS):
            obj.keyframe_insert(data_path="rotation_euler",frame=f)
        CHAIN[0].keyframe_insert(data_path="default_value",frame=f)
        for bone in (*bones,RIG.pose.bones["Head"]):
            q=bone.rotation_quaternion.copy()
            if bone.name in previous and q.dot(previous[bone.name])<0:
                q.negate()
                bone.rotation_quaternion=q
            previous[bone.name]=q
            bone.keyframe_insert(data_path="rotation_quaternion",frame=f,group=bone.name)
            if bone in bones:
                bone.keyframe_insert(data_path="location",frame=f,group=bone.name)
        for obj in (FOAM,*CHUNKS):
            for prop in ("location","rotation_euler","scale"):
                obj.keyframe_insert(data_path=prop,frame=f)
        FILL.keyframe_insert(data_path="value",frame=f)
        MOV.keyframe_insert(data_path="location",frame=f)
        MOV.keyframe_insert(data_path="rotation_euler",frame=f)
        MOV.data.keyframe_insert(data_path="dof.focus_distance",frame=f)
        bpy.context.view_layer.update()
        contacts=max(contacts,contact_error())
        if 1<=f<=FRAMES:
            for point in ((JX+.174,JY+.019,1.350),(JX+.115,JY,1.420),(JX-.116,JY,1.420)):
                x,y,depth=world_to_camera_view(SCENE,MOV,V(point))
                if not (.015<x<.992 and .03<y<.97 and depth>0):
                    raise RuntimeError(f"Hook frame {f}: jug leaves the frame ({x:.3f}, {y:.3f})")
                max_handle_x=max(max_handle_x,x)
    print(f"FRAMING jug right edge at or inside {max_handle_x:.3f} of the hook width",flush=True)
    # Clamped handles retain our eased poses, also at fractional shutter times.
    for action in bpy.data.actions:
        if not action.slots:
            continue
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.handle_left_type=key.handle_right_type="AUTO_CLAMPED"
    for f in (6,24,47,66,89,113,139):
        SCENE.frame_set(f,subframe=.5)
        contacts=max(contacts,contact_error())
    print(f"CONTACT maximum sole/palm anchor error {contacts*1000:.3f} mm",flush=True)
    if contacts>.0025:
        raise RuntimeError(f"Rider contact error {contacts*1000:.2f} mm")
    SCENE.frame_set(1)


def render_hook(folder,preview):
    ff=shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("Install FFmpeg with libx264 and put ffmpeg on PATH")
    start=time.monotonic()
    SCENE.render.resolution_x,SCENE.render.resolution_y=(216,384) if preview else (1080,1920)
    SCENE.cycles.samples=8 if preview else 64
    SCENE.cycles.adaptive_threshold=.085 if preview else .032
    SCENE.cycles.adaptive_min_samples=3 if preview else 12
    SCENE.render.use_motion_blur=True
    SCENE.render.motion_blur_shutter=.42
    bake_motion()
    print(f"TIMING motion bake {time.monotonic()-start:.2f} s",flush=True)
    SCENE.render.filepath=str(folder/"frame_")
    result=bpy.ops.render.render(animation=True)
    if "FINISHED" not in result or any(not (folder/f"frame_{f:04d}.png").is_file() for f in range(1,FRAMES+1)):
        raise RuntimeError("Hook capture ended before all frames were written")
    movie=folder/"hook_6s.mp4"
    subprocess.run([ff,"-hide_banner","-loglevel","error","-y","-framerate",str(FPS),
                    "-start_number","1","-i",str(folder/"frame_%04d.png"),"-frames:v",str(FRAMES),
                    "-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p",
                    "-color_primaries","bt709","-color_trc","iec61966-2-1","-colorspace","bt709",
                    "-vf","scale=out_color_matrix=bt709","-movflags","+faststart",str(movie)],check=True)
    print(f"TIMING hook_6s.mp4 {time.monotonic()-start:.2f} s",flush=True)
    return movie


def deliver(preview,stills_only):
    out=OUT/"preview" if preview else OUT
    out.mkdir(parents=True,exist_ok=True)
    SCENE.render.resolution_x,SCENE.render.resolution_y=(432,768) if preview else (1080,1920)
    SCENE.cycles.samples=24 if preview else 192
    SCENE.cycles.adaptive_threshold=.055 if preview else .014
    SCENE.cycles.adaptive_min_samples=4 if preview else 24
    SCENE.render.use_motion_blur=False
    # Stage the set so an interrupted render or encoder preserves the previous delivery.
    with tempfile.TemporaryDirectory(prefix=".sme01-",dir=out) as work:
        folder=Path(work)
        delivery=[]
        for i,name in enumerate(("hook","tapi_roller_tergelincir","jadi_pemacu","segelas_jus"),1):
            start=time.monotonic()
            still(i)
            path=folder/f"beat{i}_{name}.png"
            SCENE.render.filepath=str(path)
            if "FINISHED" not in bpy.ops.render.render(write_still=True) or not path.is_file():
                raise RuntimeError(f"Still capture interrupted at beat {i}")
            print(f"TIMING {path.name} {time.monotonic()-start:.2f} s",flush=True)
            delivery.append(path)
        if not stills_only:
            delivery.append(render_hook(folder,preview))
        for path in delivery:
            path.replace(out/path.name)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--preview",action="store_true",help="CPU-friendly portrait stills and a full-cadence six-second hook")
    parser.add_argument("--stills-only",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    start=time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    RIG=bar_figure()
    HEAD_REST=RIG.pose.bones["Head"].rotation_quaternion.copy()
    workwear_finish()
    SCENE=C.render_settings("CPU",1080,24 if args.preview else 192,FRAMES)
    device(SCENE)
    SCENE.unit_settings.system="METRIC"
    SCENE.render.fps=FPS
    SCENE.cycles.max_bounces,SCENE.cycles.transmission_bounces=12,10
    SCENE.cycles.diffuse_bounces,SCENE.cycles.glossy_bounces=4,5
    SCENE.cycles.sample_clamp_indirect=4.
    SCENE.render.image_settings.color_depth="8"
    lighting()
    P=palette()
    location()
    REAR,CRANK,PEDALS,CHAIN=bike()
    ROLLER,PULLEY,SHAFT,OLD,GRIP,COVER=drive()
    TRACE=power_trace()
    CHUNKS,VOLUMES,FULL_HEIGHT,(FILL,FOAM),CUP=glassware()
    LOAD=[chunk.location.copy() for chunk in CHUNKS]
    LAP=make_lap_shapes()
    WIDE=((-2.38,-3.68,1.63),(-.32,.015,1.01),42,(-.44,-.02,1.27))
    CLOSE=((1.69,-1.88,1.59),(.201,-.033,.920),43,(.421,-.09,.927))
    HERO=camera("01 • Bar at the stall",*WIDE,2.8)
    PAIRED=camera("02–03 • fixed roller test",*CLOSE,4.5)
    PAYOFF=camera("04 • the first serving",(.984,-.538,1.280),(.883,-.104,1.126),48,(.893,-.138,1.157),5.2)
    MOV=camera("Hook • rider to drive",*WIDE,3.6)
    print(f"TIMING scene assembly {time.monotonic()-start:.2f} s",flush=True)
    deliver(args.preview,args.stills_only)
    print(f"TIMING total {time.monotonic()-start:.2f} s",flush=True)

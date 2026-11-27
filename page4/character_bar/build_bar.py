"""Run blender -b --factory-startup -P build_bar.py [-- --preview]."""
import math
from pathlib import Path
import random
import runpy
import subprocess
import sys
import time

import bpy
from mathutils import Vector as V, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
kit = runpy.run_path(str(ROOT / "pipeline/cutaway/cutlib.py"))
mesh, box, bead, line, beam, material = (kit[k] for k in
    ("mesh", "box", "sphere", "strand", "beam", "material"))
cos, sin, pi = math.cos, math.sin, math.pi
scene = bpy.context.scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
rng = random.Random(3404)


def load(pack, filename, condition=""):
    root = ROOT / "assets/cc0/quaternius" / pack
    path = next(p for p in root.rglob(filename) if condition in str(p))
    before = set(scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path), bone_heuristic="BLENDER", import_pack_images=False)
    return set(scene.objects) - before


def paint(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


base = load("UBC_Standard", "Superhero_Male_FullBody.gltf")
rig = bpy.data.objects["Armature"]
body = bpy.data.objects["SuperHero_Male"]
for obj in (body, bpy.data.objects["Eyes"]):
    smooth(obj)
    tree = obj.data.materials[0].node_tree
    shader = tree.nodes.get("Principled BSDF")
    tex = tree.nodes.get("Image Texture")
    tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    if obj == body:
        tint = tree.nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "MULTIPLY"
        tint.inputs[0].default_value = 1
        tint.inputs[2].default_value = (.54,.40,.32,1)
        tree.links.new(tex.outputs["Color"],tint.inputs[1])
        tree.links.new(tint.outputs[0],shader.inputs["Base Color"])
        shader.inputs["Subsurface Weight"].default_value = .08
        shader.inputs["Subsurface Scale"].default_value = .008
hair_set = load("UBC_Standard", "Hair_SimpleParted.gltf", "Rigged to Head Bone")
hair = bpy.data.objects["Hair_SimpleParted"]
hair.parent = rig
for mod in hair.modifiers:
    if mod.type == "ARMATURE":
        mod.object = rig
for obj in hair_set - {hair}:
    bpy.data.objects.remove(obj, do_unlink=True)
for img in bpy.data.images:
    if img.filepath.endswith("_png.png"):
        path = Path(bpy.path.abspath(img.filepath).replace("_png.png", ".png"))
        if path.exists():
            img.filepath = str(path)
ink = material("Black hair", "1b1715", "322721", 45, .0001, .51)
# Restore the supplied strand normal map and tone its albedo toward espresso black.
smooth(hair)
ht=hair.data.materials[0].node_tree
hp=ht.nodes.get("Principled BSDF")
hc=next(n for n in ht.nodes if n.type=="TEX_IMAGE" and "BaseColor" in n.image.name)
hm=ht.nodes.new("ShaderNodeMixRGB")
hm.blend_type="MULTIPLY"
hm.inputs[0].default_value=1
hm.inputs[2].default_value=(.045,.033,.026,1)
ht.links.new(hc.outputs["Color"],hm.inputs[1])
ht.links.new(hm.outputs[0],hp.inputs["Base Color"])
hp.inputs["Roughness"].default_value=.62
hp.inputs["Specular IOR Level"].default_value=.24
brows = bpy.data.objects["Eyebrows"]
for v in brows.data.vertices:
    v.co.z = 1.71 + .56 * (v.co.z - 1.71)
paint(smooth(brows), ink)

# Transfer the local UAL rotation deltas into the UBC rest-bone axes.
source_set = load("UAL_Standard", "UAL1_Standard.glb")
source = next(o for o in source_set if o.type == "ARMATURE")
source.animation_data_clear()
anim = source.animation_data_create()
anim.action = bpy.data.actions["Idle_Loop"]
anim.action_slot = anim.action.slots[0]
scene.frame_set(12)
for bone in rig.pose.bones:
    basis = bone.bone.matrix_local.to_quaternion().inverted() @ source.data.bones[bone.name].matrix_local.to_quaternion()
    bone.rotation_quaternion = basis @ source.pose.bones[bone.name].matrix_basis.to_quaternion() @ basis.inverted()
    if bone.name.startswith(("pelvis","thigh","calf","foot","ball")):
        bone.rotation_quaternion = Quaternion().slerp(bone.rotation_quaternion,.25)
for obj in source_set:
    bpy.data.objects.remove(obj, do_unlink=True)
update = bpy.context.view_layer.update
update()


def orient(name, direction):
    bone = rig.pose.bones[name]
    m = bone.matrix.copy()
    delta = (bone.tail - bone.head).rotation_difference(V(direction).normalized())
    m = delta.to_matrix().to_4x4() @ m
    m.translation = bone.head
    bone.matrix = m
    update()


# Follow the opened rule with a small downward turn of the chin.
head=rig.pose.bones["Head"]
m=head.matrix.copy()
rot=Quaternion((0,0,1),.24) @ Quaternion((1,0,0),.09)
turned=rot.to_matrix().to_4x4() @ m
turned.translation=m.translation
head.matrix=turned
update()
orient("upperarm_l", (.27, -.30, -.91))
orient("lowerarm_l", (-.28, -.93, .37))
# Curl each phalanx toward the palm in its rest-space flexion plane.
for digit in ("index", "middle", "ring", "pinky"):
    for i, angle in enumerate((37, 65, 55), 1):
        b = rig.pose.bones[f"{digit}_{i:02d}_l"]
        q = b.bone.matrix_local.to_quaternion()
        b.rotation_quaternion = q.inverted() @ Quaternion((0, 1, 0), math.radians(angle)) @ q
update()
bones = {b.name: rig.matrix_world @ b.matrix @ b.bone.matrix_local.inverted() for b in rig.pose.bones}


def at(co, bone):
    return bones[bone] @ V(co)


# Sample nearby rest-mesh weights to carry the shoulder seam over the joint.
rest_tree = KDTree(len(body.data.vertices))
for v in body.data.vertices:
    rest_tree.insert(v.co, v.index)
rest_tree.balance()
def tailored(p):
    total = 0
    pos = V((0,0,0))
    for _,idx,dist in rest_tree.find_n(p,6):
        for group in body.data.vertices[idx].groups:
            bone = body.vertex_groups[group.group].name
            if bone in bones:
                w = group.weight/(.002+dist)**2
                pos += at(p,bone)*w
                total += w
    return pos/total
def cloth(name, rows, mat, bone_for, closed=True):
    """Pose a parametric cloth panel with a continuous circumference or open edges."""
    n = len(rows[0])
    verts = [(tailored(p) if bone_for is None else at(p, bone_for(p))) for row in rows for p in row]
    faces = [(i*n+j, i*n+(j+1)%n, (i+1)*n+(j+1)%n, (i+1)*n+j)
             for i in range(len(rows)-1) for j in range(n if closed else n-1)]
    return smooth(mesh(name, verts, faces, mat))


blue = material("Indigo cotton twill", "2d5880", "396991", 220, .0003)
cuff = material("Rolled reverse denim", "5783a0", "7394a9", 190, .0003)
pants = material("Graphite drill", "253337", "334246", 160, .0003)
canvas = material("Clay canvas", "965433", "b47349", 175, .0005)
thread = material("Flax thread", "d6a075")
boot = material("Oiled work leather", "402b20", "5a3e2b", 45, .0006, .48)
sole = material("Crepe outsole", "292923")
brass = material("Aged brass", "cba867", metal=.68, rough=.33)
yellow = material("Lacquered yellow beech", "f6bd24", rough=.42)
black = material("Graphite ink", "282b28")
angles = [i*2*pi/64 for i in range(64)]
torso = lambda p: "spine_02"
def ellipse(z, a, b, cy=.03):
    return [(a*cos(t), cy+b*sin(t), z) for t in angles]
cloth("Work shirt", [ellipse(*s) for s in [
    (.87,.222,.16),(1.01,.22,.17),(1.14,.204,.159),(1.32,.244,.172),
    (1.43,.26,.167),(1.48,.225,.14),(1.519,.181,.124),(1.552,.103,.10),(1.548,.074,.073)]], blue, None)
facing=material("Collar facing","365e81","477a9c",230,.0003)
for s, side in ((1,"l"),(-1,"r")):
    upper = "upperarm_"+side
    for name, profile, mat in [
        ("Sleeve",[(.14,.045),(.19,.087),(.24,.104),(.30,.099),(.36,.093),(.411,.083)],blue),
        ("Double roll",[(.358,.095),(.364,.101),(.379,.101),(.385,.094),(.389,.099),(.408,.096),(.415,.086),(.412,.072)],cuff)]:
        rows = [[(s*x,.06+r*cos(t),1.454+r*sin(t)) for t in angles] for x,r in profile]
        cloth(name, rows, mat, None)
# Shade underlying covered skin to prevent pinpricks of skin at joint transitions.
body.data.materials.append(pants)
body.data.materials.append(blue)
for f in body.data.polygons:
    x,y,z = f.center
    if z < .96:
        f.material_index = 1
    elif z < 1.55 and abs(x)<.4 and (abs(x)>.089 or z<1.523):
        f.material_index = 2

for s,side in ((1,"l"),(-1,"r")):
    leg = "thigh_"+side
    calf = "calf_"+side
    foot = "foot_"+side
    rows=[]
    for z,a,b,cy in [(.12,.068,.083,.06),(.145,.076,.082,.06),(.195,.068,.079,.06),
                        (.33,.079,.092,.067),(.47,.086,.094,.041),(.51,.082,.088,.035),
                        (.57,.091,.099,.038),(.7,.108,.113,.048),(.83,.121,.136,.05),
                        (.95,.119,.136,.04)]:
        rows.append([(s*.113+a*cos(t),cy+b*sin(t),z+.004*cos(3*t)) for t in angles])
    cloth("Straight cut trouser leg",rows,pants,lambda p: calf if p[2]<.54 else leg)
    # Stacked welt and a continuous leather vamp with a low rounded toe box.
    for label,levels,mat in [
        ("Rubber outsole",[(.009,.079,.156,-.019),(.018,.081,.158,-.019),(.038,.081,.158,-.019),(.042,.08,.155,-.019)],sole),
        ("Stitched welt",[(.038,.082,.157,-.019),(.047,.082,.157,-.019),(.049,.079,.154,-.018)],boot),
        ("Leather upper",[(.044,.079,.154,-.018),(.064,.079,.154,-.018),(.083,.077,.148,-.014),
                          (.10,.071,.134,-.005),(.119,.067,.108,.016),(.139,.062,.085,.035),
                          (.151,.062,.073,.049),(.183,.066,.073,.056),(.184,.058,.065,.056)],boot)]:
        rows=[[(s*.114+a*cos(t),cy+b*sin(t),z) for t in angles] for z,a,b,cy in levels]
        cloth(label,rows,mat,lambda p:foot)
    for j in range(4):
        z=.108+j*.01
        y=-.124+j*.013
        line("Waxed lace",[at((s*.114-.027,y+.004,z),foot),at((s*.114,y,z+.001),foot),
                           at((s*.114+.027,y+.004,z+.004),foot)],.0025,thread)

# Cut the front panel from a wrap surface. Increasing arc at waist gives side coverage.
profile=[(.625,.285,.25,1.82),(.64,.284,.249,1.82),(.86,.27,.241,1.81),
         (1.035,.224,.19,1.62),(1.13,.219,.187,1.5),(1.21,.234,.192,.77),
         (1.345,.252,.207,.55),(1.426,.25,.204,.52)]
def apronpoint(row,u):
    z,a,b,arc=row
    t=arc*u
    return (a*sin(t),.027-b*cos(t)-.004*cos(5*t),z+.004*u*u)
# Drape against the final posed shirt and trousers. Rays ignore the arms so
# a hand in front of the bib cannot drag the apron away from the body.
update()
obstacles = []
for ob in scene.objects:
    if ob.name.startswith(("Work shirt","Straight cut trouser leg")):
        obstacles.append(BVHTree.FromObject(ob,bpy.context.evaluated_depsgraph_get()))
def drape(p):
    q=at(p,"spine_02")
    normal=V((p[0],p[1]-.03,0)).normalized()
    for obstacle in obstacles:
        hit=obstacle.ray_cast(q+normal*.42,-normal,.46)[0]
        if hit:
            q+=normal*max(0,(hit-q).dot(normal)+.012)
    return q
def fabric_point(z,u):
    for a,b in zip(profile,profile[1:]):
        if z<=b[0]:
            f=max(0,(z-a[0])/(b[0]-a[0]))
            levels=[v+(w-v)*f for v,w in zip(a,b)]
            return drape(apronpoint(levels,u))
    return drape(apronpoint(profile[-1],u))
us=[j/32-1 for j in range(65)]
zs=[a[0]+(b[0]-a[0])*j/7 for a,b in zip(profile,profile[1:]) for j in range(7)]+[profile[-1][0]]
def surface(name,rows,mat):
    n=len(rows[0])
    return smooth(mesh(name,[p for row in rows for p in row],[(i*n+j,i*n+j+1,(i+1)*n+j+1,(i+1)*n+j)
                      for i in range(len(rows)-1) for j in range(n-1)],mat))
surface("Draped clay canvas apron",[[fabric_point(z,u) for u in us] for z in zs],canvas)
for u in (-.982,.982):
    line("Bound apron edge",[fabric_point(z,u) for z in zs],.0015,thread)
for z in (.637,1.421):
    line("Topstitch",[fabric_point(z,u) for u in us],.0012,thread)
# Lay straps over the evaluated shoulder surface, including the crest where
# front-projected strips would disappear into the shirt.
shoulders = [obstacles[0]]
def fit_surface(origin, direction, clearance):
    hits=[tree.ray_cast(origin,direction,.8) for tree in shoulders]
    valid=[hit for hit in hits if hit[0] is not None]
    if not valid:
        return origin+direction*.4
    hit=min(valid,key=lambda item:item[3])
    return hit[0]-direction*clearance
for s in (-1,1):
    front=fabric_point(1.419,s*.84)
    band=[[front+V((d,-.002,0)) for d in (-.012,.012)]]
    for j in range(59):
        t=.39+(pi+.42-.39)*j/58
        normal=V((0,-cos(t),sin(t)))
        row=[]
        for d in (-.012,.012):
            origin=V((front.x+d,-.004,1.347))+normal*.47
            row.append(fit_surface(origin,-normal,.006))
        band.append(row)
    surface("Cotton webbing",band,canvas)
    bead("Brass bib rivet",front+V((0,-.004,0)),(.005,.003,.005),brass)
    # Cut the lapel as a curved, tapered flap over the work shirt.
    rows=[]
    for j in range(12):
        u=j/11
        inner=V((s*(.010+.073*u),-.5,1.502-.053*u))
        outer=V((s*(.081+.045*sin(pi*u)+.002*u),-.5,1.541-.092*u))
        rows.append([fit_surface(inner.lerp(outer,v/8),V((0,1,0)),.0035+.001*sin(pi*u))
                     for v in range(9)])
    surface("Point collar",rows,facing)
# Two ties meet under a knot at the small of the back.
for side in (-1,1):
    rows=[]
    for j in range(26):
        t=1.51+j/25*(pi-1.51)
        rows.append([drape((side*.231*sin(t),.03-.190*cos(t),1.113+dz)) for dz in (-.014,.014)])
    surface("Apron waist tie",rows,canvas)
knot=drape((0,.223,1.113))
bead("Half knot",knot,(.025,.014,.018),canvas)
for sign in (-1,1):
    tail=[knot+V((sign*x,y,z)) for x,y,z in ((0,0,0),(.027,.014,-.021),(.044,.018,-.057),(.039,.025,-.113))]
    surface("Tie ends",[[p+V((dx,0,0)) for dx in (-.009,.009)] for p in tail],canvas)
def pocket(u,z,offset=.004):
    return fabric_point(z,u)+V((0,-offset,0))
surface("Left pencil pocket",[[pocket(u,z) for u in (.12,.31,.51,.70,.82)]
                             for z in (1.262,1.275,1.31,1.35)],canvas)
line("Pocket hem",[pocket(u,z,.005) for u,z in ((.14,1.349),(.14,1.268),(.80,1.268),(.80,1.349))],.0012,thread)
bottom=pocket(.53,1.346,.002)
top=bottom+V((.014,.003,.052))
line("Carpenter pencil",[bottom,top],.0048,material("Red carpenter pencil","a23724"))
line("Sharpened pencil tip",[top,top+V((.001,0,.006))],.0023,black)

face_rest=BVHTree.FromPolygons([v.co for v in body.data.vertices],[f.vertices[:] for f in body.data.polygons])
# Trace the moustache onto the actual face mesh before posing.
for side in (-1,1):
    rows=[]
    for j in range(19):
        u=j/18
        x=side*(.001+.032*u)
        z=1.65-.009*u**1.5
        band=[]
        for dz in (-1,0,1):
            h=.003*(.23+sin(pi*u)**.55)
            p,n,_,_=face_rest.ray_cast(V((x,-.4,z+h*dz)),V((0,1,0)))
            band.append(tuple(p+n*(.001+(1-abs(dz))*.0009)))
        rows.append(band)
    cloth("Trimmed moustache",rows,ink,lambda p:"Head",False)

# A partially unfolded metric rule. Stamp ticks on both visible wooden leaves.
grip=at((.84,.051,1.422),"hand_l")
def rule(a,b):
    a,b=V(a),V(b)
    tangent=(b-a).normalized()
    normal=V((tangent.z,0,-tangent.x)).normalized()
    plank=beam("Metric ruler leaf",a,b,.022,.006,yellow)
    # Keep the broad face in the vertical image plane.
    plank.rotation_euler=Matrix((normal,V((0,1,0)),tangent)).transposed().to_euler()
    for j in range(1,20):
        p=a.lerp(b,j/20)-V((0,.0034,0))+normal*.010
        line("Metric graduation",[p,p-normal*(.008 if j%5==0 else .004)],.00065,black)
    for j,number in ((5,"5"),(10,"10"),(15,"15")):
        data=bpy.data.curves.new("Metric numeral","FONT")
        data.body,data.size,data.align_x=number,.0055,"CENTER"
        textobj=bpy.data.objects.new("Rule marking",data)
        scene.collection.objects.link(textobj)
        textobj.location=a.lerp(b,j/20)-normal*.005-V((0,.0036,0))
        textobj.rotation_euler=Matrix((tangent,-normal,V((0,-1,0)))).transposed().to_euler()
        data.materials.append(black)
    for p in (a,b):
        bead("Ruler hinge",p-V((0,.004,0)),(.004,.002,.004),brass)
a=grip+V((.035,0,-.055))
b=a+V((-.146,0,.15))
c=b+V((-.159,-.006,-.141))
rule(a,b)
rule(b+V((0,-.006,0)),c)
rule(c+V((0,-.006,0)),c+V((.081,-.006,-.193)))

def workshop():
    plaster=material("Limewash","b6bca4","d6d4b8",3,.002)
    green=material("Louvred joinery","36665c","4d7767",8,.001)
    metal=material("Painted steel","334240",metal=.44)
    teal=material("Biscuit tin enamel","397977",metal=.23)
    cream=material("Enamel lettering","f3deaf")
    wood=material("Meranti grain","724933","b78051",3,.001)
    tree=wood.node_tree
    coord=tree.nodes.new("ShaderNodeVectorMath")
    coord.operation="MULTIPLY"
    coord.inputs[1].default_value=(2,63,84)
    tree.links.new(tree.nodes.new("ShaderNodeTexCoord").outputs["Object"],coord.inputs[0])
    for node in tree.nodes:
        if node.type=="TEX_NOISE":
            tree.links.new(coord.outputs[0],node.inputs["Vector"])
    def lettering(words,loc,size,mat):
        data=bpy.data.curves.new(words,"FONT")
        data.body, data.size, data.align_x=words,size,"CENTER"
        obj=bpy.data.objects.new(words,data)
        scene.collection.objects.link(obj)
        obj.location, obj.rotation_euler.x=loc,pi/2
        data.materials.append(mat)
    box("Party wall",(0,1.23,1.48),(6,.17,3),plaster)
    box("Skirting",(0,1.125,.085),(6,.05,.17),green)
    for x in (-1.12,.99):
        box("Deep window reveal",(x,1.122,1.55),(1.25,.11,1.21),metal,.015)
        for col in (-.29,.29):
            for j in range(11):
                slat=box("Timber jalousie",(x+col,1.034,1.04+j*.103),(.548,.05,.098),green,.003)
                slat.rotation_euler.x=-.26
        box("Painted sill",(x,1.02,.936),(1.34,.2,.058),cream,.009)
        for dx in (-.60,0,.60):
            box("Window stile",(x+dx,1.007,1.552),(.035,.036,1.17),green,.004)
    # Address plate and a vertical rainwater downpipe.
    box("Enamel address plaque",(.085,1.13,1.94),(.26,.026,.162),green,.012)
    lettering("27",(.085,1.11,1.899),.111,cream)
    line("PVC downpipe",[(-1.98,1.04,.14),(-1.98,1.04,2.65),(-2.08,.83,2.80)],.043,cream)
    for x in (-2.19,2.19):
        box("Porch column",(x,-.75,1.4),(.21,.22,2.8),plaster)
    for x in range(-6,7):
        box("Awning seam",(x*.36,-.11,2.83),(.027,2.86,.036),metal)
    grout=material("Grout","898170")
    box("Porch slab",(0,0,-.085),(6,6,.13),grout)
    tilemats=[material("Unglazed tile",a,b,26,.0008) for a,b in
              [("c3ad8c","c6b393"),("b99f83","c2ac90"),("b8a68a","c7b497")]]
    for i in range(-5,6):
        for j in range(-5,3):
            box("Porch tile",(i*.48,j*.48,-.018),(.476,.476,.026),rng.choice(tilemats),.002)
    for j in range(4):
        box("Bench plank",(.02,-.51-.124*j,.841),(1.65,.122,.064),wood,.004)
    for x in (-.69,.72):
        for y in (-.52,-.85):
            beam("Folding leg",(x*1.08,y,.02),(x*.91,-1.37-y,.823),.046,.035,metal)
    # Biscuit tin reused for offcuts and tools.
    tin=box("Biskut tin",(-.199,-.49,.957),(.197,.143,.165),teal,.012)
    for z in (.88,1.034):
        box("Tin rolled lip",(-.199,-.49,z),(.201,.146,.011),brass,.005)
    lettering("BISKUT",(-.199,-.563,.947),.037,cream)
    for j in range(6):
        x=-.239+j*.015
        line("Tool shaft",[(x,-.49,1.02),(x+rng.uniform(-.035,.035),-.47,1.16+rng.uniform(-.04,.035))],.006,wood)
    # Small vaned rotor prototype in a bearing cradle.
    ax,ay,az=.279,-.68,1.015
    box("Prototype foot",(ax,ay,.89),(.29,.20,.035),wood,.005)
    for y in (ay-.068,ay+.068):
        beam("Axle cradle",(ax-.06,y,.902),(ax,y,az),.018,.018,metal)
        beam("Axle cradle",(ax+.06,y,.902),(ax,y,az),.018,.018,metal)
    line("Spindle",[(ax,ay-.09,az),(ax,ay+.09,az)],.008,brass)
    for i in range(8):
        t=2*pi*i/8+.2
        p=V((ax+.082*cos(t),ay,az+.082*sin(t)))
        beam("Rotor spoke",(ax,ay,az),p,.009,.009,brass)
        paddle=box("Rotor paddle",p,(.045,.089,.008),teal,.002)
        paddle.rotation_euler.y=-t-.56
    # Small ceramic orchid pot on the sill, beside the workshop wall.
    pottery=material("Iron red earthenware","804530","aa6744",40,.0007)
    leaf=material("Blade green","39583b","668448",13,.0006)
    px,py,pz=-.63,.95,.972
    for z,r,h in ((.059,.061,.118),(.12,.071,.022)):
        bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=r*.79,radius2=r,depth=h,location=(px,py,pz+z))
        pot=bpy.context.object
        pot.name="Terracotta pot"
        paint(pot,pottery)
    for i in range(15):
        theta=i*2.4
        length=rng.uniform(.12,.27)
        rows=[]
        for j in range(11):
            u=j/10
            width=.022*sin(pi*u)**.8
            mid=V((px+cos(theta)*length*u,py+sin(theta)*length*u,pz+.122+.13*sin(2.3*u)+.018*u))
            off=V((-sin(theta),cos(theta),0))*width
            rows.append([mid-off,mid+V((0,0,width*.33)),mid+off])
        surface("Orchid leaf",rows,leaf)
    # Low sun filtering through foliage beyond the open porch. The shadow
    # casters sit outside the camera's field and form broad patches on the plaster.
    direction=V((.88,.70,-.43)).normalized()
    sun=bpy.data.lights.new("Late sun","SUN")
    sun.energy,sun.angle,sun.color=2.7,.035,(1,.76,.48)
    sunobj=bpy.data.objects.new(sun.name,sun)
    scene.collection.objects.link(sunobj)
    sunobj.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    for i in range(5):
        start=V((-2.4,-.85+i*.27,2.5+rng.uniform(-.4,.4)))
        end=start+V((.48,.44,.36))
        line("Garden branch",[start,end],.014,metal)
        for k in range(12):
            u=k/12
            p=start.lerp(end,u)
            ob=bead("Garden shade",p+V((0,(-1)**k*.09,0)),(.07,.14,.027),leaf)
            ob.rotation_euler.y=.45*(-1)**k
    # Thin volume confined to the distant wall and side light.
    mist=bpy.data.materials.new("Humid porch air")
    mist.use_nodes=True
    nt=mist.node_tree
    nt.nodes.remove(nt.nodes.get("Principled BSDF"))
    vol=nt.nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Density"].default_value=.028
    vol.inputs["Anisotropy"].default_value=.3
    nt.links.new(vol.outputs[0],nt.nodes["Material Output"].inputs["Volume"])
    box("Air by the wall",(0,.72,1.5),(4.7,.77,3),mist)


def area(name,loc,aim,power,color,size):
    light=bpy.data.lights.new(name,"AREA")
    light.energy,light.color,light.size=power,color,size
    obj=bpy.data.objects.new(name,light)
    scene.collection.objects.link(obj)
    obj.location=loc
    obj.rotation_euler=(V(aim)-V(loc)).to_track_quat("-Z","Y").to_euler()


scene.render.engine="CYCLES"
scene.cycles.device="CPU"
scene.cycles.samples=6
scene.cycles.max_bounces=3
scene.cycles.use_denoising=True
scene.cycles.denoiser="OPENIMAGEDENOISE"
scene.render.resolution_x,scene.render.resolution_y=1080,1920
preview="--preview" in sys.argv
scene.render.resolution_percentage=25 if preview else 100
scene.render.image_settings.file_format="PNG"
scene.render.image_settings.color_mode="RGB"
scene.render.use_persistent_data=True
scene.view_settings.view_transform="AgX"
world=scene.world
world.use_nodes=True
world.node_tree.nodes["Background"].inputs[0].default_value=(.48,.63,.74,1)
world.node_tree.nodes["Background"].inputs[1].default_value=.36
area("Honey sunlight",(-2.6,-2.5,3.2),(0,0,1.05),390,(1,.78,.55),1.45)
area("Open sky",(1.2,-2.1,2.6),(0,0,1.45),170,(.66,.83,1),2.5)
area("Warm return",(1.6,.61,2.17),(0,0,1.2),185,(1,.74,.49),1.1)
camera=bpy.data.cameras.new("Portrait")
cam=bpy.data.objects.new("Portrait",camera)
scene.collection.objects.link(cam)
scene.camera=cam
def camera_at(location,target):
    cam.location=location
    cam.rotation_euler=(V(target)-V(location)).to_track_quat("-Z","Y").to_euler()

floor=box("Studio floor",(0,0,-.057),(200,200,.09),material("Muted eucalyptus","7a8b83"))
def render(name):
    prefix="preview_" if preview else ""
    scene.render.filepath=str(OUT/(prefix+name+".png"))
    start=time.monotonic()
    bpy.ops.render.render(write_still=True)
    print("SECONDS",name,round(time.monotonic()-start,2),flush=True)

camera.type="ORTHO"
camera.ortho_scale=2.06
for name,deg in (("front",0),("three_quarter",38),("side",90)):
    t=math.radians(deg)
    camera_at((3*sin(t),-3*cos(t),1.23),(0,0,.926))
    render(name)
floor.hide_render=True
workshop()
camera.type="PERSP"
camera.lens=48
camera_at((.35,-2.25,1.45),(.015,-.15,1.32))
camera.dof.use_dof=True
camera.dof.focus_distance=(V((0,-.06,1.62))-cam.location).length
camera.dof.aperture_fstop=6.3
render("hero")
if not preview:
    inputs=[]
    for name in ("front","three_quarter","side"):
        inputs+=["-i",str(OUT/(name+".png"))]
    subprocess.run(["ffmpeg","-loglevel","error","-y",*inputs,"-filter_complex","hstack=inputs=3",
                    "-frames:v","1",str(OUT/"turnaround.png")],check=True)

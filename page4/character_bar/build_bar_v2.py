"""Run blender -b --factory-startup -P build_bar_v2.py [-- --preview]."""
import math
from pathlib import Path
import random
import runpy
import subprocess
import sys
import time

import bpy
import bmesh
from mathutils import Vector as V, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out_v2"
OUT.mkdir(exist_ok=True)
kit = runpy.run_path(str(ROOT / "pipeline/cutaway/cutlib.py"))
mesh, box, bead, line, beam, material = (kit[k] for k in
    ("mesh", "box", "sphere", "strand", "beam", "material"))
cos, sin, pi = math.cos, math.sin, math.pi
build_started = time.monotonic()
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
def ramp(lo, hi, value):
    t = max(0., min(1., (value-lo)/(hi-lo)))
    return t*t*(3-2*t)


def gaussian(value, width):
    return math.exp(-(value/width)**2)


# Narrow the shoulder skeleton as well as the mesh so the elbows and grip
# still pivot about the new shoulders. All tailored panels use this same block.
def frame_point(co):
    x,y,z = co
    strength = ramp(.76,1.37,z)*(1-ramp(1.54,1.605,z))
    shift = .054*min(abs(x)/.237,1.)*strength
    return V((x-math.copysign(shift,x),y,z))


def fit_body(co):
    x,y,z=co
    p=frame_point(co)
    arm=ramp(.139,.25,abs(x))*(1-ramp(.67,.78,abs(x)))*ramp(1.26,1.36,z)
    torso=ramp(.78,1.29,z)*(1-ramp(1.55,1.60,z))*(1-arm)
    p.y=.035+(y-.035)*(1-.18*torso)
    neck=ramp(1.49,1.56,z)*(1-ramp(1.57,1.61,z))*(1-ramp(.068,.13,abs(x)))
    p.x*=1-.22*neck
    p.y += (.075-y)*.235*arm
    p.z += (1.438-z)*.235*arm
    return p


def sculpt_face(co):
    x,y,z=co
    # Affect soft tissue on the front and sides without moving the eye globes.
    front=1-ramp(-.035,.035,y)
    cheek=gaussian(z-1.659,.029)*gaussian(abs(x)-.049,.026)*front
    jaw=gaussian(z-1.608,.027)*front
    nose=gaussian(z-1.655,.012)*gaussian(x,.026)*(1-ramp(-.085,-.064,y))
    corner=gaussian(abs(x)-.029,.015)*gaussian(z-1.630,.012)*front
    brow=gaussian(z-1.708,.012)*gaussian(abs(x)-.031,.031)*front
    return V((x*(1-.10*jaw+.078*cheek+.19*nose)+math.copysign(.0025*corner,x),
              y-.005*cheek+.004*brow+.002*corner,
              z+.008*jaw+(.008 if x>0 else .005)*corner+.002*cheek))


rest_coords=[v.co.copy() for v in body.data.vertices]
rest_faces=[f.vertices[:] for f in body.data.polygons]
block_tree=BVHTree.FromPolygons(rest_coords,rest_faces)
bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode="EDIT")
for bone in rig.data.edit_bones:
    bone.head=frame_point(bone.head)
    bone.tail=frame_point(bone.tail)
bpy.ops.object.mode_set(mode="OBJECT")
for v,co in zip(body.data.vertices,rest_coords):
    v.co=sculpt_face(fit_body(co)) if co.z>1.565 and abs(co.x)<.12 else fit_body(co)
    v.co.z-=.023*ramp(1.745,1.872,co.z)
body.data.update()
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
        tint.inputs[2].default_value = (.44,.415,.395,1)
        tree.links.new(tex.outputs["Color"],tint.inputs[1])
        tree.links.new(tint.outputs[0],shader.inputs["Base Color"])
        shader.inputs["Subsurface Weight"].default_value = .08
        shader.inputs["Subsurface Scale"].default_value = .008
    else:
        # Darken the brown iris more strongly than the already bright sclera.
        deepen=tree.nodes.new("ShaderNodeGamma")
        deepen.inputs["Gamma"].default_value=1.48
        tree.links.new(tex.outputs["Color"],deepen.inputs["Color"])
        tree.links.new(deepen.outputs[0],shader.inputs["Base Color"])
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
hm.inputs[2].default_value=(.017,.016,.017,1)
ht.links.new(hc.outputs["Color"],hm.inputs[1])
ht.links.new(hm.outputs[0],hp.inputs["Base Color"])
hp.inputs["Roughness"].default_value=.62
hp.inputs["Specular IOR Level"].default_value=.24
brows = bpy.data.objects["Eyebrows"]
for v in brows.data.vertices:
    v.co.z = 1.71 + .56 * (v.co.z - 1.71)
    x=abs(v.co.x)
    v.co.z=1.707+.61*(v.co.z-1.71)+.006*(1-ramp(.014,.055,x))-.002*ramp(.04,.065,x)
    v.co.y+=.002
paint(smooth(brows), ink)
# Flatten the high swept quiff close to the crown.
for v in hair.data.vertices:
    v.co.z-=.023*ramp(1.745,1.872,v.co.z)


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
rot=Quaternion((0,0,1),.09) @ Quaternion((1,0,0),-.115)
turned=rot.to_matrix().to_4x4() @ m
turned.translation=m.translation
head.matrix=turned
update()
orient("upperarm_l", (.27, -.30, -.91))
orient("lowerarm_l", (-.035, -.93, .37))
# Curl each phalanx toward the palm in its rest-space flexion plane.
for digit in ("index", "middle", "ring", "pinky"):
    for i, angle in enumerate((37, 65, 55), 1):
        b = rig.pose.bones[f"{digit}_{i:02d}_l"]
        q = b.bone.matrix_local.to_quaternion()
        b.rotation_quaternion = q.inverted() @ Quaternion((0, 1, 0), math.radians(angle)) @ q
update()
bones = {b.name: rig.matrix_world @ b.matrix @ b.bone.matrix_local.inverted() for b in rig.pose.bones}


def at(co, bone):
    return bones[bone] @ fit_body(co)


# Sample nearby rest-mesh weights to carry the shoulder seam over the joint.
rest_tree = KDTree(len(body.data.vertices))
for v in body.data.vertices:
    rest_tree.insert(rest_coords[v.index], v.index)
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
# Cut two armholes in the shirt block. Each set-in sleeve starts with
# the exact armhole loop, then eases onto cross-sections of the posed arm.
shirt_levels=[(1.018,.203,.15),(1.065,.217,.162),(1.14,.208,.158),(1.32,.244,.172),
              (1.43,.26,.167),(1.48,.225,.14),(1.519,.181,.124),
              (1.552,.103,.10),(1.548,.074,.073)]
shirt_rows=[ellipse(*level) for level in shirt_levels]
n=len(angles)
def armhole_segment(j):
    return any((j-center+9)%n<18 for center in (0,n//2))
shirt_faces=[(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j)
             for i in range(len(shirt_rows)-1) for j in range(n)
             if not (3<=i<6 and armhole_segment(j))]
shirt=smooth(mesh("Work shirt",[tailored(p) for row in shirt_rows for p in row],shirt_faces,blue))
facing=material("Collar facing","365e81","477a9c",230,.0003)

def sleeve_ring(side,x,ease,phis):
    mid=V((side*x,.073,1.443))
    points=[]
    for t in phis:
        radial=V((0,cos(t),sin(t)))
        hit=block_tree.ray_cast(mid+.22*radial,-radial,.26)[0]
        points.append((hit if hit is not None else mid+.06*radial)+ease*radial)
    return points

for side,center in ((1,0),(-1,n//2)):
    loop=[(3,j) for j in range(-9,10)]+[(i,9) for i in range(4,7)]
    loop += [(6,j) for j in range(8,-10,-1)]+[(i,-9) for i in (5,4)]
    edge=[V(shirt_rows[i][(j+center)%n]) for i,j in loop]
    phis=[math.atan2((p.z-1.420)/.100,(p.y-.03)/.117) for p in edge]
    sleeve=[edge]+[sleeve_ring(side,x,ease,phis) for x,ease in
                   ((.265,.013),(.31,.012),(.35,.010),(.38,.008),(.408,.006))]
    cloth("Set-in sleeve",sleeve,blue,None)
    roll=[sleeve_ring(side,x,ease,phis) for x,ease in
          ((.362,.008),(.366,.013),(.38,.013),(.385,.010),(.390,.014),
           (.405,.014),(.412,.009),(.412,.002))]
    cloth("Double roll",roll,cuff,None)
# Weld coincident sleeve seams and ease the armhole with one subdivision.
bpy.ops.object.select_all(action="DESELECT")
for ob in scene.objects:
    if ob==shirt or ob.name.startswith("Set-in sleeve"):
        ob.select_set(True)
bpy.context.view_layer.objects.active=shirt
bpy.ops.object.join()
bm=bmesh.new()
bm.from_mesh(shirt.data)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00003)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(shirt.data)
bm.free()
ease=shirt.modifiers.new("Ease at sleeve head","SUBSURF")
ease.levels=ease.render_levels=2
# The trouser seat continues under the tucked shirt to the waist.
cloth("Trouser seat",[ellipse(z,a,b,cy) for z,a,b,cy in
      ((.856,.219,.147,.044),(.91,.218,.149,.042),(.967,.214,.146,.042),
       (1.03,.210,.153,.035),(1.047,.209,.152,.035))],pants,None)
# Shade underlying covered skin to prevent pinpricks of skin at joint transitions.
body.data.materials.append(pants)
body.data.materials.append(blue)
for f in body.data.polygons:
    x,y,z = sum((rest_coords[i] for i in f.vertices),V())/len(f.vertices)
    if z < 1.047:
        f.material_index = 1
    elif z < 1.55 and abs(x)<.4 and (abs(x)>.089 or z<1.523):
        f.material_index = 2

for s,side in ((1,"l"),(-1,"r")):
    leg = "thigh_"+side
    calf = "calf_"+side
    foot = "foot_"+side
    rows=[]
    for z,a,b,cy in [(.132,.075,.097,.042),(.147,.077,.096,.044),(.195,.074,.087,.053),
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
profile=[(.625,.245,.221,1.77),(.64,.244,.22,1.77),(.86,.243,.213,1.74),
         (1.035,.224,.19,1.62),(1.13,.219,.187,1.5),(1.21,.234,.192,.77),
         (1.345,.252,.207,.55),(1.426,.25,.204,.52)]
def apronpoint(row,u):
    z,a,b,arc=row
    t=arc*u
    fullness=(1-ramp(.68,1.07,z))
    wave=cos(7*t+.5+2.4*(1-z))+.39*cos(11*t-.5)
    fold=fullness*(.021*wave+.009)
    return ((a+fold)*sin(t),.027-(b+fold)*cos(t)-.002*cos(5*t),
            z+.004*u*u+.005*fullness*wave)
# Drape against the final posed shirt and trousers. Rays ignore the arms so
# a hand in front of the bib cannot drag the apron away from the body.
update()
obstacles = []
for ob in scene.objects:
    if ob.name.startswith(("Work shirt","Straight cut trouser leg","Trouser seat")):
        obstacles.append(BVHTree.FromObject(ob,bpy.context.evaluated_depsgraph_get()))
def drape(p):
    q=at(p,"spine_02")
    normal=V((p[0],p[1]-.03,0)).normalized()
    q+=normal*.006*(1-ramp(.93,1.05,p[2]))
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
shoulders = [BVHTree.FromObject(bpy.data.objects["Work shirt"],bpy.context.evaluated_depsgraph_get())]
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
    last=band[-1]
    for j in range(1,32):
        u=j/31
        row=[]
        for point in last:
            x=point.x*(1-.58*u)
            z=point.z*(1-u)+1.108*u
            row.append(fit_surface(V((x,.51,z)),V((0,-1,0)),.0035))
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
# Project each edge of the waistband onto the posed shirt. Start inside
# the front panel edge so the side seam and the belt share the same surface.
def belt_point(side,t,z):
    radial=V((side*sin(t),-cos(t),0))
    mid=at((0,.03,z),"spine_02")
    return fit_surface(mid+radial*.5,-radial,.0035)
for side in (-1,1):
    rows=[]
    for j in range(49):
        f=j/48
        row=[]
        for dz in (-.012,.012):
            z=1.11+dz
            belt=belt_point(side,1.49+(pi-1.49)*f,z)
            row.append(fabric_point(z,side*.985).lerp(belt,ramp(0,.09,f)))
        rows.append(row)
    surface("Apron waist tie",rows,canvas)
knot=belt_point(1,pi,1.11)
bead("Half knot",knot,(.020,.010,.014),canvas)
for side in (-1,1):
    rows=[]
    for j in range(15):
        u=j/14
        center=belt_point(side,pi-.19*u,1.11-.088*u)+V((0,.005*(1-u),0))
        rows.append([center+V((d,0,0)) for d in (-.007,.007)])
    surface("Tie ends",rows,canvas)

def pocket(u,z,offset=.004):
    return fabric_point(z,u)+V((0,-offset,0))
surface("Left pencil pocket",[[pocket(u,z) for u in (.12,.31,.51,.70,.82)]
                             for z in (1.247,1.260,1.292,1.324)],canvas)
line("Pocket hem",[pocket(u,z,.005) for u,z in ((.14,1.323),(.14,1.253),(.80,1.253),(.80,1.323))],.0012,thread)
bottom=pocket(.53,1.321,.002)
top=bottom+V((.009,-.003,.034))
line("Carpenter pencil",[bottom,top],.0048,material("Red carpenter pencil","a23724"))
line("Sharpened pencil tip",[top,top+V((.001,0,.006))],.0023,black)

# A woven name panel with converted font contours fitted to the same
# surface. The clearance is measured from the bib at each glyph vertex.
navy=material("Name tape • midnight","192d35","253c40",220,.00012)
ivory=material("Warm ivory screen ink","fff1cb",rough=.84)
def label_point(x,z,offset):
    u=-.9+(x+.5)*1.8
    return fabric_point(z,u)+V((0,-offset,0))
badge_rows=[[label_point(j/30-.5,z,.002) for j in range(31)]
            for z in (1.355,1.362,1.380,1.401,1.414)]
surface("Woven name tape",badge_rows,navy)
for z in (1.359,1.410):
    line("Tape selvedge",[label_point(j/30-.5,z,.0026) for j in range(31)],.00075,thread)
font=bpy.data.curves.new("BAR capitals","FONT")
font.body="BAR"
font.space_character=1.13
font.offset=.012
letters=bpy.data.objects.new("BAR | apron print",font)
scene.collection.objects.link(letters)
bpy.context.view_layer.objects.active=letters
letters.select_set(True)
bpy.ops.object.convert(target="MESH")
verts=letters.data.vertices
xmin,xmax=min(v.co.x for v in verts),max(v.co.x for v in verts)
ymin,ymax=min(v.co.y for v in verts),max(v.co.y for v in verts)
# Subdivide the filled faces before bending them to the curved canvas.
bm=bmesh.new()
bm.from_mesh(letters.data)
bmesh.ops.triangulate(bm,faces=list(bm.faces))
bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=3,use_grid_fill=True)
for v in bm.verts:
    x=(v.co.x-xmin)/(xmax-xmin)-.5
    h=(v.co.y-ymin)/(ymax-ymin)
    v.co=label_point(.76*x,1.365+.039*h,.0034)
bm.to_mesh(letters.data)
bm.free()
paint(letters,ivory)

# Feathered pigment and fine individual clipped hairs on cheeks, jaw and
# under the chin. The upper lip is explicitly outside the beard line.
def beard_mask(p):
    x,y,z=p
    side=ramp(.016,.063,abs(x))
    top=1.620+.032*side+.026*ramp(-.052,-.005,y)*side
    # A gently blended neckline under the mandible keeps the rear neck clear.
    jaw_edge=-.052+.065*ramp(.010,.065,abs(x))
    under=ramp(1.570,1.598,z)
    return ((1-ramp(top-.004,top+.002,z))*ramp(1.570,1.580,z)
            *(1-ramp(jaw_edge-.009,jaw_edge+.003+.010*under,y))
            *(1-ramp(.073,.082,abs(x))))

mask=body.data.attributes.new("Trim density","FLOAT","POINT")
for slot,p in zip(mask.data,rest_coords):
    slot.value=.51*beard_mask(p)
skin=body.data.materials[0].node_tree
bsdf=skin.nodes.get("Principled BSDF")
pigment=skin.nodes.new("ShaderNodeMixRGB")
density=skin.nodes.new("ShaderNodeAttribute")
density.attribute_name="Trim density"
noise=skin.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value=1100
skin.links.new(skin.nodes.new("ShaderNodeTexCoord").outputs["Object"],noise.inputs["Vector"])
tones=skin.nodes.new("ShaderNodeValToRGB")
for e,pos,col in zip(tones.color_ramp.elements,(.30,.73),((.024,.018,.017,1),(.116,.078,.057,1))):
    e.position,e.color=pos,col
skin.links.new(noise.outputs["Fac"],tones.inputs[0])
skin.links.new(density.outputs["Fac"],pigment.inputs[0])
skin.links.new(tint.outputs[0],pigment.inputs[1])
skin.links.new(tones.outputs[0],pigment.inputs[2])
skin.links.new(pigment.outputs[0],bsdf.inputs["Base Color"])

# A short tapered fibre sits just above each sampled point. Interpolate the
# actual posed skin triangle as well as its shading normal for a snug trim.
def clipped_beard():
    update()
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    skin_mesh=evaluated.data
    skin_mesh.calc_loop_triangles()
    verts,faces=[],[]
    scatter=random.Random(34)
    for tri in skin_mesh.loop_triangles:
        ids=tri.vertices
        rest=[rest_coords[i] for i in ids]
        if not any(1.555 < v.z < 1.695 and abs(v.x)<.093 and v.y<.025 for v in rest):
            continue
        corners=[skin_mesh.vertices[i] for i in ids]
        area=(rest[1]-rest[0]).cross(rest[2]-rest[0]).length*.5
        for _ in range(int(area*1300000+scatter.random())):
            u,v=scatter.random(),scatter.random()
            if u+v>1:
                u,v=1-u,1-v
            w=(1-u-v,u,v)
            pos=sum((q*f for q,f in zip(rest,w)),V())
            if scatter.random()>beard_mask(pos): continue
            skin_pos=sum((q.co*f for q,f in zip(corners,w)),V())
            n=sum((q.normal*f for q,f in zip(corners,w)),V()).normalized()
            down=V((.22 if pos.x<0 else -.22,.16,-1))
            comb=(down-n*n.dot(down)).normalized()
            wide=n.cross(comb)*scatter.uniform(.00012,.00022)
            root=skin_pos+n*.00023
            tip=root+comb*scatter.uniform(.00055,.0016)+n*.00035
            i=len(verts)
            verts.extend((root-wide,root+wide,tip))
            faces.append((i,i+1,i+2))
    mesh("Clipped jaw and chin stubble",verts,faces,material("Beard fibres","2d231f",rough=.85))
clipped_beard()

# One hinge axis for all leaves. Turn its plane diagonally about the grip
# so both front and true profile can see the broad faces and both elbows.
grip=at((.84,.051,1.422),"hand_l")
across=V((.894,-.448,0)).normalized()
up=V((0,0,1))
axis=across.cross(up).normalized()
def rule(a,b):
    along=(b-a).normalized()
    width=axis.cross(along)
    plank=beam("Yellow folding rule",a,b,.024,.005,yellow)
    plank.rotation_euler=Matrix((width,axis,along)).transposed().to_euler()
    for face in (-1,1):
        for j in range(1,40):
            p=a.lerp(b,j/40)+face*.00265*axis+.010*width
            line("Millimetre graduations",[p,p-(.010 if j%10==0 else .006 if j%2==0 else .003)*width],.00065,black)
        for j in (5,10,15):
            mark=bpy.data.curves.new("Scale numeral","FONT")
            mark.body,mark.size,mark.align_x=str(j),.006,"CENTER"
            obj=bpy.data.objects.new("Scale numeral",mark)
            scene.collection.objects.link(obj)
            obj.location=a.lerp(b,j/20)-width*.007+face*.0028*axis
            obj.rotation_euler=Matrix((along*face,width,axis*face)).transposed().to_euler()
            mark.materials.append(black)

def washer(center,depth,radius,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=radius,depth=depth,location=center)
    obj=bpy.context.object
    obj.name="Ruler pivot"
    obj.rotation_euler=axis.to_track_quat("Z","Y").to_euler()
    paint(obj,mat)

def hinge(p):
    washer(p,.012,.0115,brass)
    for face in (-1,1):
        washer(p+.0064*face*axis,.0012,.0062,black)
        washer(p+.0071*face*axis,.0008,.0041,brass)
a=grip-.047*across-.036*up
b=a+.176*across+.129*up
c=b+.116*across-.183*up
d=c-.152*across-.154*up
rule(a,b)
rule(b+.005*axis,c+.005*axis)
rule(c+.010*axis,d+.010*axis)
hinge(b+.0025*axis)
hinge(c+.0075*axis)

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
    box("Enamel address plaque",(.225,1.13,2.035),(.223,.026,.145),green,.012)
    lettering("27",(.225,1.11,1.998),.101,cream)
    line("PVC downpipe",[(-1.98,1.04,.14),(-1.98,1.04,2.65),(-2.08,.83,2.80)],.043,cream)
    for x in (-2.19,2.19):
        box("Porch column",(x,-.75,1.4),(.21,.22,2.8),plaster)
    zinc=material("Pale zinc awning","91aba7","c0c9b9",18,.00045,rough=.48,metal=.25)
    roof=box("Awning underside",(0,-.10,2.58),(4.65,2.8,.054),zinc)
    roof.rotation_euler.x=.11
    box("Gutter fascia",(0,-1.49,2.395),(4.72,.074,.13),green,.008)
    for x in range(-6,7):
        rib=box("Awning seam",(x*.36,-.11,2.542),(.024,2.86,.032),metal)
        rib.rotation_euler.x=.11
    for y in (-.92,.52):
        box("Porch purlin",(0,y,2.49+.11*(y+.10)),(4.62,.046,.058),green)
    # One open leaf frames the right edge of the porch entrance.
    for z in (.10,.82):
        beam("Gate rail",(.37,-1.43,z),(1.67,-.90,z),.026,.027,metal)
    for j in range(10):
        u=j/9
        x,y=.37+1.30*u,-1.43+.53*u
        beam("Gate picket",(x,y,.095),(x,y,.88),.014,.016,metal)
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
area("Honey sunlight",(-2.6,-2.5,3.2),(0,0,1.05),365,(1,.90,.79),1.45)
area("Open sky",(1.2,-2.1,2.6),(0,0,1.45),170,(.66,.83,1),2.5)
area("Warm return",(1.6,.61,2.17),(0,0,1.2),135,(1,.84,.68),1.1)
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
    aim=V((.056,-.087,.926))
    camera_at(aim+V((3*sin(t),-3*cos(t),.304)),aim)
    render(name)
floor.hide_render=True
workshop()
camera.type="PERSP"
camera.lens=40
camera_at((.16,-3.54,1.34),(.025,-.06,1.24))
camera.dof.use_dof=True
camera.dof.focus_distance=(V((0,-.06,1.62))-cam.location).length
camera.dof.aperture_fstop=10
render("hero")
if not preview:
    inputs=[]
    for name in ("front","three_quarter","side"):
        inputs+=["-i",str(OUT/(name+".png"))]
    subprocess.run(["ffmpeg","-loglevel","error","-y",*inputs,"-filter_complex","hstack=inputs=3",
                    "-frames:v","1",str(OUT/"turnaround.png")],check=True)

print("TOTAL_SECONDS",round(time.monotonic()-build_started,2),flush=True)

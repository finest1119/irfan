"""Sectioned block, with the front upper quarter removed around a bent bore."""
from pathlib import Path
import sys, math
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE))
from studio import C, scene, camera, light, still, bevel
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=scene(1080,1080)
sc.render.film_transparent=True
sc.render.image_settings.color_mode='RGBA'
stone=C.material('Sand cast concrete','867F70','C4BDAB',22,.013,.84)
jade=C.material('Water green lining','079E8C','32B8A5',16,.0003,.24)
inner=C.material('Damp inner bore','137B70',rough=.29)
# Extrude the L-shaped section through X. The elbow is visible on its revealed shelf.
yz=[(-.82,-.80),(.82,-.80),(.82,.80),(.26,.80),(.26,-.13),(-.82,-.13)]
verts=[(x,y,z) for x in (-.85,.85) for y,z in yz]
n=len(yz)
faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
block=C.mesh('Quarter-cut block',verts,faces,stone)
# The inlet passes through the back wall, turns ninety degrees, then exits the right face.
path=[Vector((-.37,.88,.18)),Vector((-.37,-.18,.18))]
for i in range(1,29):
    t=math.pi*i/56
    path.append(Vector((-.06-.31*math.cos(t),-.18-.31*math.sin(t),.18)))
path.append(Vector((.94,-.49,.18)))
def duct(name,path,radii,material):
    knots=len(path)
    rings=[]
    for k,p in enumerate(path):
        tangent=(path[min(k+1,knots-1)]-path[max(k-1,0)]).normalized()
        side=tangent.cross(Vector((0,0,1)))
        rings.append([p+radius*(math.cos(i*math.tau/64)*side+Vector((0,0,math.sin(i*math.tau/64)))) for radius in radii for i in range(64)])
    verts=sum(rings,[])
    stride=64*len(radii)
    faces=[]
    for k in range(knots-1):
        for s in range(len(radii)):
            for i in range(64):
                a=k*stride+s*64+i
                b=k*stride+s*64+(i+1)%64
                faces.append((a,b,b+stride,a+stride) if s==0 else (a+stride,b+stride,b,a))
    for k in (0,knots-1):
        off=k*stride
        if len(radii)==1:
            faces.append(tuple(range(off,off+64)))
        else:
            for i in range(64):
                j=(i+1)%64
                faces.append((off+i,off+j,off+j+64,off+i+64))
    ob=C.mesh(name,verts,faces,material)
    for p in ob.data.polygons:
        p.use_smooth=len(p.vertices)==4
    return ob
cutter=duct('Core drill',path,[.234],stone)
# Repair outward normals for robust closed-volume subtraction.
import bmesh
for obj in (cutter,block):
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
mod=block.modifiers.new('Through bore','BOOLEAN')
mod.operation='DIFFERENCE'
mod.object=cutter
bpy.context.view_layer.objects.active=block
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(cutter,do_unlink=True)
bevel(block,.027)
tube=duct('Continuous enamelled elbow',path,[.227,.155],jade)
tube.data.materials.append(inner)
for k in range(len(path)-1):
    for p in list(tube.data.polygons)[k*128+64:k*128+128]:
        p.material_index=1
camera((0,-.03,-.02),(3.1,-5.5,4.85),3.25)
light('Upper window',(-2.8,-3.6,5),(0,0,0),500,3.1)
light('Bounce',(3,-2,2),(0,0,0),150,2.6,(.76,.9,1))
light('Rim',(1,3,3),(0,0,0),260,2.3)
still(HERE,'logo',sc)

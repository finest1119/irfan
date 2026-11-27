"""Build and render the original What Just Happened storm portrait in headless Blender."""
import argparse
from contextlib import contextmanager
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'assets'
QUAT = ASSETS / 'cc0/quaternius'
PH = ASSETS / 'polyhaven'
TAU = math.tau
scene = bpy.context.scene
rng = random.Random(4217)
V = Vector


def mesh_object(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(mat)
    return obj


def material(name, rgb, rough=.5, metal=0, emission=0, coat=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    for key, val in [('Base Color', (*rgb, 1)), ('Roughness', rough), ('Metallic', metal),
                     ('Coat Weight', coat), ('Coat Roughness', .22), ('Emission Color', (*rgb, 1)),
                     ('Emission Strength', emission)]:
        shader.inputs[key].default_value = val
    return mat


def box(name, loc, size, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        for i in range(3):
            v.co[i] *= size[i]
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Rolled edges', 'BEVEL')
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    return obj


def rod(name, a, b, radius, mat):
    axis = V(b) - V(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=axis.length,
                                        location=(V(a) + V(b)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = axis.to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return obj


def rings(name, rows, mat, segments=64):
    verts = [fn(TAU * j / segments) for fn in rows for j in range(segments)]
    faces = [(i*segments+j, i*segments+(j+1)%segments, (i+1)*segments+(j+1)%segments,
              (i+1)*segments+j) for i in range(len(rows)-1) for j in range(segments)]
    obj = mesh_object(name, verts, faces, mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def bind(obj, rig, weights):
    groups = {}
    for v in obj.data.vertices:
        for bone, weight in weights(v.co).items():
            if weight <= 0:
                continue
            if bone not in groups:
                groups[bone] = obj.vertex_groups.new(name=bone)
            groups[bone].add([v.index], weight, 'REPLACE')
    mod = obj.modifiers.new('Follow performer', 'ARMATURE')
    mod.object = rig
    obj.parent = rig
    return obj


def redistribute(coord, stops):
    if coord <= stops[0][0]:
        return {stops[0][1]: 1}
    for (a, bone_a), (b, bone_b) in zip(stops, stops[1:]):
        if coord <= b:
            t = (coord-a)/(b-a)
            return {bone_a: 1-t, bone_b: t}
    return {stops[-1][1]: 1}


def weave(mat, scale, strength):
    nt = mat.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Sheen Weight'].default_value = .105
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 2
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = .0018
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])


def shell_print(obj,profile):
    """Sew the details into garment UV space so they cannot slide through the posed shell."""
    import numpy as np
    w,h=1536,1024
    t=(np.arange(w)+.5)*TAU/w
    z=(.83+(np.arange(h)+.5)*(.72/h))[:,None]
    x=np.interp(z[:,0],[row[0] for row in profile],[row[1] for row in profile])[:,None]*np.cos(t)
    front=np.sin(t)<0
    color=np.empty((h,w,4),dtype=np.float32)
    color[:]=(.255,.094,.024,1)
    color[:,:,:3]=np.where((z>1.362)[:,:,None],(.014,.031,.041),color[:,:,:3])
    grain=np.random.default_rng(711).normal(1,.052,(h,w))
    grain*=1-.075*(np.arange(w)%9==0)[None,:]
    grain*=1-.068*(np.arange(h)%13==0)[:,None]
    for level in (.955,1.04,1.142,1.248,1.367):
        grain*=1-.23*np.exp(-((z-level)/.0028)**2)
    color[:,:,:3]*=grain[:,:,None]
    def paint(mask,tint):
        color[:,:,:3][mask]=tint
    paint(front & (abs(x)<.0078),(.014,.02,.024))
    paint(front & (abs(abs(x)-.007)<.00085) & ((z% .004)<.0024),(.14,.13,.098))
    paint(front & (abs(x)<.0023) & (((z+.0012*(x>0))%.0034)<.0017),(.30,.25,.16))
    pocket=(z>1.19)&(z<1.35)&front
    px=x-.105-.27*(z-1.19)
    paint(pocket & (abs(px)<.006),(.017,.026,.031))
    paint(pocket & (abs(px)<.0008),(.28,.27,.23))
    for j in range(3):
        paint(front & (z>1.405) & (z<1.417) &
              (abs(x-.103-.012*j-.24*(z-1.405))<.0032),(.37,.44,.42))
    img=bpy.data.images.new('Storm shell textile and waterproof zip',width=w,height=h,alpha=True)
    img.colorspace_settings.name='Non-Color'
    img.pixels.foreach_set(color.ravel())
    img.update()
    mat=obj.data.materials[0].copy()
    mat.name='Sewn parka panels'
    nt=mat.node_tree
    tex=nt.nodes.new('ShaderNodeTexImage')
    tex.image=img
    nt.links.new(tex.outputs['Color'],nt.nodes.get('Principled BSDF').inputs['Base Color'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    uv=obj.data.uv_layers.new()
    n=64
    for poly in obj.data.polygons:
        row,j=divmod(poly.index,n)
        poly.material_index=0
        lo,hi=[(profile[i][0]-.83)/.72 for i in (row,row+1)]
        for idx,coord in zip(poly.loop_indices,[(j/n,lo),((j+1)/n,lo),((j+1)/n,hi),(j/n,hi)]):
            uv.data[idx].uv=coord


def wardrobe(rig):
    ochre = material('Ochre waterproof shell', (.25,.092,.023), .65, coat=.13)
    dark = material('Midnight storm yoke', (.013,.034,.042), .65, coat=.13)
    seam = material('Charcoal binding', (.013,.023,.03), .55)
    knit = material('Petrol ribbed wool', (.026,.084,.096), .88)
    for m in (ochre, dark, knit):
        weave(m, 145, .16)
    stops = [(.89,'pelvis'),(1.10,'spine_01'),(1.25,'spine_02'),(1.42,'spine_03')]
    torso_weights = lambda v: redistribute(v.z, stops)
    # The displaced profile makes sewn baffles, with the upper yoke changing fabric.
    profile = [(.83,.219,.159),(.86,.223,.173),(.94,.234,.18),(.955,.226,.17),
               (1.025,.235,.182),(1.04,.225,.173),(1.13,.238,.187),(1.142,.227,.174),
               (1.235,.249,.197),(1.248,.239,.184),(1.35,.264,.194),(1.367,.251,.182),
               (1.435,.251,.171),(1.49,.223,.145),(1.528,.165,.116),(1.55,.094,.088)]
    rows = [lambda t,z=z,a=a,b=b:(a*math.cos(t),.026+b*math.sin(t),z+.008*math.cos(2*t))
            for z,a,b in profile]
    obj = rings('Baffled storm parka', rows, ochre)
    shell_print(obj,profile)
    bind(obj, rig, torso_weights)
    for side, suffix in ((-1,'r'),(1,'l')):
        stations = [(.135,.030),(.171,.083),(.202,.10),(.243,.104),(.305,.10),(.32,.096),
                    (.394,.09),(.41,.084),(.465,.084),(.48,.081),(.56,.079),
                    (.573,.075),(.64,.071),(.685,.065),(.697,.058),(.709,.055)]
        rows = [lambda t,x=x,r=r:(side*x,.065+r*math.cos(t),1.455+r*math.sin(t)) for x,r in stations]
        sleeve = rings('Insulated sleeve '+suffix, rows, ochre)
        sleeve.data.materials.append(dark)
        for p in sleeve.data.polygons:
            p.material_index = int(abs(p.center.x)<.31 or abs(p.center.x)>.686)
        limb = [(.13,'spine_03'),(.18,'clavicle_'+suffix),(.24,'upperarm_'+suffix),
                (.42,'upperarm_'+suffix),(.50,'lowerarm_'+suffix)]
        # Merge equal neighbouring bone entries when both stations use the same bone.
        def arm_weights(v):
            if .24 <= abs(v.x) <= .42:
                return {'upperarm_'+suffix:1}
            return redistribute(abs(v.x),limb)
        bind(sleeve, rig, arm_weights)
    collar = [(1.49,.143,.116),(1.52,.151,.122),(1.575,.132,.111),(1.599,.122,.105),
              (1.606,.109,.098),(1.587,.102,.094)]
    rows = [lambda t,z=z,a=a,b=b:(a*math.cos(t),.028+b*math.sin(t),z+.022*math.sin(t))
            for z,a,b in collar]
    bind(rings('Raised funnel collar',rows,dark),rig,lambda v:{'spine_03':1})
    # A ribbed watch cap fits over the hairline; the upturned cuff has a distinct lip.
    crown=[(1.727,.083,.11),(1.738,.086,.114),(1.765,.087,.111),(1.792,.081,.102),
           (1.816,.066,.086),(1.831,.041,.052),(1.839,.003,.003)]
    cuff=[(1.726,.084,.111),(1.73,.089,.116),(1.751,.09,.116),(1.759,.09,.115),(1.762,.086,.111)]
    for label,profile2 in [('Crown',crown),('Turned cuff',cuff)]:
        rows=[lambda t,z=z,a=a,b=b:((a+.0009*math.cos(80*t))*math.cos(t),
               .006+(b+.0012*math.cos(80*t))*math.sin(t),z-.009*math.sin(t)+.0025*math.cos(t))
              for z,a,b in profile2]
        bind(rings(label,rows,knit,320),rig,lambda v:{'Head':1})

    # Sparse granular snow catches along the cap and windward shoulder.
    ice=material('Snow caught in fabric',(.45,.54,.58),.81)
    for head,count in ((True,155),(False,205)):
        verts,faces=[],[]
        for i in range(count):
            t=rng.uniform(0,TAU)
            if head:
                k=rng.randrange(len(crown)-1)
                u=rng.random()
                z,a,b=[a+(b-a)*u for a,b in zip(crown[k],crown[k+1])]
                x,y=a*math.cos(t),.006+b*math.sin(t)
                z-=.009*math.sin(t)-.0025*math.cos(t)
            else:
                k=rng.choice((12,13,14))
                u=rng.random()
                z,a,b=[a+(b-a)*u for a,b in zip(profile[k],profile[k+1])]
                x,y=a*math.cos(t),.026+b*math.sin(t)
                z+=.008*math.cos(2*t)
            radius=rng.uniform(.00055,.0015)*(1 if head else 1.4)
            j=len(verts)
            verts.extend([(x-radius,y-radius,z),(x+radius,y-radius,z+.0003),
                          (x,y+radius,z),(x,y,z+radius*1.3)])
            faces.extend([(j,j+1,j+3),(j+1,j+2,j+3),(j+2,j,j+3)])
        bind(mesh_object('Spindrift on '+('wool' if head else 'shell'),verts,faces,ice),
             rig,(lambda v:{'Head':1}) if head else torso_weights)
    # The free end of a dark plaid scarf streams downwind behind the collar.
    scarf=material('Oxide and navy scarf',(.17,.037,.026),.87)
    weave(scarf,210,.24)
    verts,faces=[],[]
    for i in range(39):
        u=i/38
        for j in range(4):
            v=j/3-.5
            verts.append((.055+.50*u,.08+.069*u+.015*math.sin(u*10)+.012*v,
                          1.534+.087*math.sin(2.5*u)+v*(.074-.025*u)+.008*math.sin(v*5+u*6)))
        if i:
            for j in range(3):
                k=i*4+j
                faces.append((k-4,k-3,k+1,k))
    tail=mesh_object('Wind-lifted scarf end',verts,faces,scarf)
    tail.data.materials.append(seam)
    for poly in tail.data.polygons:
        poly.use_smooth=True
        poly.material_index=int(poly.index//3 in (8,9,19,20,30,31,34))
    tail.shape_key_add(name='Rest')
    for phase in (0,1):
        wave=tail.shape_key_add(name='Wind ripple '+str(phase))
        for i,pt in enumerate(wave.data):
            u=(i//4)/38
            pt.co.z+=u*.061*math.sin(u*7+phase*1.57)
            pt.co.y+=u*.028*math.cos(u*7+phase*1.57)
        wave.slider_min=-1
        for f in range(1,182,3):
            wave.value=(.55+.44*gust_at(f))*math.sin(f*.14+phase*1.57)
            wave.keyframe_insert('value',frame=f)
    bind(tail,rig,lambda v:{'spine_03':1})


def cast():
    bpy.ops.import_scene.gltf(filepath=str(next(QUAT.rglob('Superhero_Male_FullBody.gltf'))),
                              bone_heuristic='BLENDER',import_pack_images=False)
    rig = bpy.data.objects['Armature']
    body=bpy.data.objects['SuperHero_Male']
    for img in bpy.data.images:
        if img.filepath.endswith('_png.png'):
            actual=Path(bpy.path.abspath(img.filepath)).with_name(Path(img.filepath).name.replace('_png.png','.png'))
            if actual.is_file():
                img.filepath=str(actual)
    for o in [body,bpy.data.objects['Eyes'],bpy.data.objects['Eyebrows']]:
        mat=o.data.materials[0]
        nt=mat.node_tree
        bs=nt.nodes.get('Principled BSDF')
        tex=nt.nodes.get('Image Texture')
        nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        if o.name=='Eyebrows':
            for v in o.data.vertices:
                v.co.z=1.709+(v.co.z-1.709)*.62-.003*(1-min(1,abs(v.co.x)/.055))
            tint=nt.nodes.new('ShaderNodeMixRGB')
            tint.blend_type='MULTIPLY'
            tint.inputs[0].default_value=1
            tint.inputs[2].default_value=(.077,.042,.024,1)
            nt.links.new(tex.outputs['Color'],tint.inputs[1])
            nt.links.new(tint.outputs[0],bs.inputs['Base Color'])
        if o==body:
            bs.inputs['Subsurface Weight'].default_value=.095
            bs.inputs['Subsurface Scale'].default_value=.007
            bs.inputs['Coat Weight'].default_value=.085
            bs.inputs['Coat Roughness'].default_value=.28
        for p in o.data.polygons:
            p.use_smooth=True
    # Model small water beads on the windward cheek against the actual face surface.
    wet=material('Water beads',(.35,.23,.15),.115,coat=.95)
    verts,faces=[],[]
    for i in range(58):
        x=rng.uniform(-.067,.061)
        z=rng.uniform(1.633,1.736)
        if abs(x)<.026 or (1.683<z<1.711 and abs(x)<.052): continue
        hit,point,normal,_=body.ray_cast(V((x,-.35,z)),V((0,1,0)))
        if not hit or normal.y>-.18: continue
        rot=normal.to_track_quat('Z','Y')
        rad=rng.uniform(.00055,.0014)
        j=len(verts)
        for a in range(6):
            verts.append(point+rot@V((rad*math.cos(a*TAU/6),rad*1.5*math.sin(a*TAU/6),0)))
        verts.append(point+normal*rad*.75)
        faces.extend([(j+a,j+(a+1)%6,j+6) for a in range(6)])
    bind(mesh_object('Cheek rain beads',verts,faces,wet),rig,lambda v:{'Head':1})
    denim=material('Charcoal field trousers',(.028,.042,.049),.79)
    weave(denim,115,.13)
    body.data.materials.append(denim)
    for face in body.data.polygons:
        if face.center.z<.925:
            face.material_index=len(body.data.materials)-1
    wardrobe(rig)
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(next(QUAT.rglob('UAL1_Standard.glb'))),
                              bone_heuristic='BLENDER',import_pack_images=False)
    imported=set(bpy.data.objects)-before
    source=next(o for o in imported if o.type=='ARMATURE')
    source.animation_data_clear()
    action=bpy.data.actions['Idle_Loop']
    anim=source.animation_data_create()
    anim.action=action
    anim.action_slot=action.slots[0]
    # Convert the local rotation deltas through armature space; source and target limbs differ in roll.
    axes={}
    for bone in rig.data.bones:
        qs=source.data.bones[bone.name].matrix_local.to_quaternion()
        qt=bone.matrix_local.to_quaternion()
        axes[bone.name]=qt.inverted() @ qs
    end=action.frame_range.y
    samples=[]
    keys=sorted(set(range(1,181,3))|{180})
    for f in keys:
        t=((f-1)*.82)%end
        scene.frame_set(int(t),subframe=t%1)
        samples.append({b.name:b.matrix_basis.to_quaternion().copy() for b in source.pose.bones})
    for o in imported:
        bpy.data.objects.remove(o,do_unlink=True)
    for f,pose in zip(keys,samples):
        gust=gust_at(f)
        for bone in rig.pose.bones:
            n=bone.name
            fix=axes[n]
            q=fix @ pose[n] @ fix.inverted()
            # Bend into the crosswind and pull the chin into the collar on impact.
            angles={'spine_02':(5+3*gust,-6-3*gust,0),'spine_03':(2+3*gust,-4,0),
                    'neck_01':(0,-4*gust,-7+3*math.sin(f*.033)),
                    'Head':(-14+9*gust,-3*gust,10+10*gust+5*math.sin(f*.042))}
            if n in angles:
                basis=bone.bone.matrix_local.to_quaternion()
                for axis,alpha in zip('XYZ',angles[n]):
                    q=(basis.inverted() @ Quaternion(V(tuple(int(axis==ch) for ch in 'XYZ')),
                         math.radians(alpha)) @ basis) @ q
            bone.rotation_quaternion=q
            bone.keyframe_insert('rotation_quaternion',frame=f)
        rig.location=(.025*math.sin(f*.044)-.035*gust,0,0)
        rig.keyframe_insert('location',frame=f)
    return rig


def gust_at(f):
    return math.exp(-((f-82)/17)**2)+.57*math.exp(-((f-142)/13)**2)


def ground(name, tex, corners, repeat, mat):
    obj=mesh_object(name,corners,[(0,1,2,3)],mat)
    uv=obj.data.uv_layers.new()
    for i,point in enumerate(corners):
        uv.data[i].uv=(point[0]/repeat,point[1]/repeat)
    nt=mat.node_tree
    bs=nt.nodes.get('Principled BSDF')
    for channel in ('diff','nor_gl','rough'):
        node=nt.nodes.new('ShaderNodeTexImage')
        node.image=bpy.data.images.load(str(PH/'textures'/tex/f'{tex}_{channel}_1k.jpg'))
        if channel=='diff':
            nt.links.new(node.outputs['Color'],bs.inputs['Base Color'])
        else:
            node.image.colorspace_settings.name='Non-Color'
            if channel=='nor_gl':
                normal=nt.nodes.new('ShaderNodeNormalMap')
                normal.inputs['Strength'].default_value=.35
                nt.links.new(node.outputs['Color'],normal.inputs['Color'])
                nt.links.new(normal.outputs[0],bs.inputs['Normal'])
            else:
                mul=nt.nodes.new('ShaderNodeMath')
                mul.operation='MULTIPLY'
                mul.inputs[1].default_value=.48
                nt.links.new(node.outputs['Color'],mul.inputs[0])
                nt.links.new(mul.outputs[0],bs.inputs['Roughness'])


def area(name,pos,target,power,color,size):
    lamp=bpy.data.lights.new(name,'AREA')
    lamp.energy,lamp.color,lamp.shape,lamp.size=power,color,'DISK',size
    obj=bpy.data.objects.new(name,lamp)
    scene.collection.objects.link(obj)
    obj.location=pos
    obj.rotation_euler=(V(target)-V(pos)).to_track_quat('-Z','Y').to_euler()


def city():
    world=scene.world
    world.use_nodes=True
    nt=world.node_tree
    env=nt.nodes.new('ShaderNodeTexEnvironment')
    env.image=bpy.data.images.load(str(next((PH/'hdri').glob('*.hdr'))))
    nt.links.new(env.outputs['Color'],nt.nodes['Background'].inputs['Color'])
    nt.nodes['Background'].inputs[1].default_value=.12
    sky=nt.nodes.new('ShaderNodeBackground')
    sky.inputs[0].default_value=(.115,.205,.315,1)
    sky.inputs[1].default_value=.62
    mix=nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(nt.nodes.new('ShaderNodeLightPath').outputs['Is Camera Ray'],mix.inputs[0])
    nt.links.new(nt.nodes['Background'].outputs[0],mix.inputs[1])
    nt.links.new(sky.outputs[0],mix.inputs[2])
    nt.links.new(mix.outputs[0],nt.nodes['World Output'].inputs[0])
    concrete=material('Rain-glazed sidewalk',(.23,.23,.25),coat=.34)
    asphalt=material('Wet roadway',(.1,.1,.1),coat=.6)
    ground('Public footway','concrete_floor_02',[(-4,-9,0),(1,-9,0),(1,45,0),(-4,45,0)],2,concrete)
    ground('Traffic lanes','aerial_asphalt_01',[(1,-9,-.11),(18,-9,-.11),(18,65,-.11),(1,65,-.11)],17,asphalt)
    iron=material('Municipal graphite enamel',(.035,.057,.067),.33,.5)
    stone=material('Blue limestone',(.128,.151,.166),.68)
    box('Curb',(1,17,-.051),(.16,52,.115),stone,.013)
    ink=material('Bakery window frames',(.033,.047,.052),.39,.33)
    shell=material('Rain-darkened brick',(.12,.073,.057),.72)
    glass=material('Cold window glass',(.065,.148,.21),.23,.45, .3)
    honey=material('Tungsten windows',(.61,.28,.09),.39,emission=1.4)
    milk=material('Occupied windows',(.47,.41,.31),.48,emission=.70)
    bulbs=material('Sodium lamps',(1,.49,.145),.26,emission=12)
    stripe=material('Road marking',(.52,.54,.50),.48)
    for y in range(-4,40,4):
        box('Road stripe',(4,y,-.105),(.091,1.8,.006),stripe)
    for i in range(7):
        box('Crosswalk',(2+i*1.55,7.3,-.102),(.72,2,.009),stripe)
    for side,x in enumerate((-3.6,11.1)):
        for j in range(7):
            y=1+j*5.0
            h=rng.uniform(5.8,10)
            box('Street elevation',(x+(-2 if side==0 else 3),y,h/2),(4,4.85,h),shell)
            for z in (1.45,3.75,5.65,7.55):
                if z>h-.35: continue
                for k in (-1.45,0,1.45):
                    glazing=rng.choice((glass,glass,milk,honey)) if z>2 else rng.choice((honey,milk,glass))
                    box('Window surround',(x,y+k,z),(.14,1.18,1.48),ink)
                    dx=.085 if side==0 else -.085
                    box('Glass',(x+dx,y+k,z),(.025,1.03,1.33),glazing)
                    box('Window mullion',(x+dx*1.23,y+k,z),(.025,.038,1.34),ink)
            for z in (2.65,h):
                box('Cornice',(x,y,z),(.34,4.97,.14),stone)
    # A distant facade catches the light at the end of the street.
    for i in range(5):
        x=-13+i*4.6
        h=rng.uniform(6,12)
        box('Far block',(x,31,h/2),(4.5,5,h),stone)
        for floor in range(1,int(h/2)):
            for shift in (-1.25,0,1.25):
                box('Far window',(x+shift,28.47,floor*1.8),(.73,.06,.98),rng.choice((glass,honey,milk)))
    for x,y,h in [(1.05,3.9,3.12),(-.80,4.8,2.95),(-.90,9,3.55),(-1.2,16,3.7),(.98,25,3.8)]:
        rod('Lamp standard',(x,y,0),(x,y,h),.042,iron)
        rod('Outreach',(x,y,h),(x-.35,y,h+.10),.035,iron)
        box('Lamp canopy',(x-.36,y,h+.09),(.44,.22,.095),iron,.035)
        box('Luminous diffuser',(x-.36,y,h+.032),(.355,.18,.036),bulbs,.016)
    return iron


def traffic_sign(iron):
    pivot=bpy.data.objects.new('Flexing sign head',None)
    scene.collection.objects.link(pivot)
    pivot.location=(.19,1.88,1.96)
    rod('Galvanized post',(.19,1.94,0),(.19,1.94,1.96),.028,iron)
    edge=material('Sign enamel border',(.028,.041,.039),.36,.38)
    yellow=material('Reflective amber sign',(.9,.45,.055),.32,.15,emission=.20,coat=.4)
    printmat=material('Traffic stencil',(.016,.021,.022),.55)
    def plaque(name,loc,size,m):
        ob=box(name,loc,size,m,.012)
        ob.parent=pivot
        ob.rotation_euler.y=math.radians(45)
    plaque('Diamond sign housing',(0,0,.06),(.39,.031,.39),edge)
    plaque('Reflective diamond face',(0,-.018,.06),(.367,.006,.367),yellow)
    # Windsock pictogram cut into four alternating tapered bands.
    def mark(points):
        ob=mesh_object('Windsock stencil',[(x,-.022,z+.06) for x,z in points],
                       [tuple(range(len(points)))],printmat)
        ob.parent=pivot
    mark([(-.106,-.101),(-.096,-.101),(-.096,.106),(-.106,.106)])
    for i in (0,2,4):
        t0,t1=i/5,(i+1)/5
        def top(t): return (-.092+.223*t,.092-.068*t)
        def bottom(t): return (-.092+.223*t,.013-.035*t)
        mark([bottom(t0),bottom(t1),top(t1),top(t0)])
    for f in range(1,181,2):
        g=gust_at(f)
        pivot.rotation_euler=(.025*math.sin(.32*f),(.035+.105*g)*math.sin(f*.42),
                              .14+(.048+.21*g)*math.sin(f*.29))
        pivot.keyframe_insert('rotation_euler',frame=f)


def snow():
    mats=[material('Sleet '+str(i),rgb,.48,emission=e) for i,(rgb,e) in enumerate([
        ((.46,.59,.69),.62),((.66,.75,.81),.60),((.52,.61,.69),.44)])]
    seeds=[]
    for i in range(5850):
        seeds.append((rng.uniform(-6,6),rng.uniform(-1.45,10),rng.uniform(-.3,4.6),
                      rng.uniform(.018,.115),rng.uniform(.0010,.0032),rng.uniform(.065,.165),
                      rng.uniform(0,TAU)))
    faces=[(4*i,4*i+1,4*i+2,4*i+3) for i in range(len(seeds))]
    obj=mesh_object('Crosswind sleet ribbons',[(0,0,0)]*(4*len(seeds)),faces,mats[0])
    for mat in mats[1:]: obj.data.materials.append(mat)
    for face in obj.data.polygons: face.material_index=rng.randrange(len(mats))
    obj.visible_shadow=False
    def update(f):
        coords=[]
        gust=gust_at(f)
        sweep=15*math.erf((f-82)/20)+8*math.erf((f-142)/15)
        for x,y,z,length,w,speed,phase in seeds:
            x=(x+speed*(f+sweep)+6)%12-6
            z=(z-.024*f+.045*math.sin(f*.055+phase)+.3)%4.9-.3
            length*=1+.55*gust
            dz=length*(.14+.09*math.sin(phase+f*.03))
            coords.extend((x,y,z, x+length*.24,y,z-dz*.24+w, x+length,y,z-dz,
                           x+length*.48,y,z-dz*.48-w))
        obj.data.vertices.foreach_set('co',coords)
        obj.data.update()
    return update


def camera(rig):
    data=bpy.data.cameras.new('Storm portrait lens')
    obj=bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(obj)
    scene.camera=obj
    data.lens=54
    data.dof.use_dof=True
    data.dof.aperture_fstop=2.4
    data.dof.aperture_blades=7
    def update(f):
        t=(f-1)/179
        ease=t*t*(3-2*t)
        head=rig.pose.bones['Head']
        eye=rig.matrix_world @ head.matrix @ head.bone.matrix_local.inverted() @ V((.029,-.083,1.698))
        aim=V((-.148,-.025,1.45+.068*ease))
        obj.location=aim+V((.17-.06*ease,-1.98+.40*ease,.115+.026*ease))
        obj.rotation_euler=(aim-obj.location).to_track_quat('-Z','Y').to_euler()
        data.dof.focus_distance=(eye-obj.location).dot((aim-obj.location).normalized())
    return update


def setup(samples):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='METAL'
        prefs.refresh_devices()
    except (TypeError,RuntimeError):
        pass
    gpu=[d for d in prefs.devices if d.type=='METAL']
    for d in prefs.devices:
        d.use=d in gpu
    scene.cycles.device='GPU' if gpu else 'CPU'
    scene.cycles.samples=samples or (12 if gpu else 2)
    scene.cycles.max_bounces=3
    scene.cycles.diffuse_bounces=1
    scene.cycles.glossy_bounces=2
    scene.cycles.use_denoising=True
    scene.cycles.denoiser='OPENIMAGEDENOISE'
    scene.render.use_persistent_data=True
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.compression=12
    scene.render.resolution_x,scene.render.resolution_y=1080,1920
    scene.render.resolution_percentage=100
    scene.render.fps,scene.frame_start,scene.frame_end=30,1,180
    scene.view_settings.view_transform='AgX'
    return ', '.join(d.name for d in gpu) if gpu else 'CPU (no Metal device enumerated)'


def encoder():
    candidates=[os.getenv('FFMPEG'),shutil.which('ffmpeg'),
                Path.home()/'Downloads/affiliate-video-studio/node_modules/ffmpeg-static/ffmpeg']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            filters=subprocess.run([candidate,'-hide_banner','-filters'],capture_output=True,text=True)
            if ' drawtext ' in filters.stdout:
                return str(candidate)
    raise RuntimeError('Set FFMPEG to an executable with drawtext and libx264.')


def encode(out,ff):
    # Use a repo-relative path inside drawtext to keep shell metacharacters out of the filter.
    caption=("drawtext=fontfile=assets/fonts/Montserrat-Bold.ttf:text='you brace yourself.':"
             "fontsize=61:fontcolor=white:shadowcolor=black@0.64:shadowx=1:shadowy=3:"
             "x=(w-tw)/2:y=h*0.676-th/2")
    common=[ff,'-hide_banner','-loglevel','error','-y']
    subprocess.run(common+['-framerate','30','-start_number','1','-i',str(out/'frames/%04d.png'),
        '-frames:v','180','-vf',caption+',scale=out_color_matrix=bt709','-c:v','libx264','-crf','20',
        '-pix_fmt','yuv420p','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709',
        '-movflags','+faststart',str(out/'zack_test.mp4')],cwd=ROOT,check=True)
    subprocess.run(common+['-i',str(out/'frames/0120.png'),'-frames:v','1','-vf',caption,'-q:v','2',
                           str(out/'still.jpg')],cwd=ROOT,check=True)


@contextmanager
def quiet_blender(out):
    """Keep native Blender logs short on success; replay diagnostics if an operation fails."""
    sys.stdout.flush()
    sys.stderr.flush()
    with tempfile.TemporaryFile(dir=out) as log:
        saved=[os.dup(fd) for fd in (1,2)]
        try:
            for fd in (1,2):
                os.dup2(log.fileno(),fd)
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            for fd,original in zip((1,2),saved):
                os.dup2(original,fd)
                os.close(original)
            if sys.exc_info()[0] is not None:
                log.seek(max(0,log.tell()-4096))
                print(log.read().decode(errors='replace'),file=sys.stderr)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--preview',type=int,choices=range(1,181),metavar='FRAME')
    parser.add_argument('--percent',type=int,default=100,help='Preview scale only')
    parser.add_argument('--samples',type=int)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.out.resolve()
    out.relative_to(ROOT)
    out.mkdir(parents=True,exist_ok=True)
    ff=encoder() if not args.preview else None
    with quiet_blender(out):
        device=setup(args.samples)
        rig=cast()
        traffic_sign(city())
        flakes=snow()
        lens=camera(rig)
        area('Amber shop window',(-1.8,-.77,2.3),(0,0,1.58),86,(1,.57,.34),1.0)
        area('Blue dusk sky',(.9,-1.8,2.9),(0,0,1.5),37,(.42,.65,1),1.35)
        area('Streetlight rim',(.64,.88,2.57),(0,0,1.58),100,(.57,.74,1),.83)
        area('Wet street reflection',(1.8,5,2.8),(1.6,4,0),260,(1,.46,.18),1.2)
    def frame_state(f):
        scene.frame_set(f)
        lens(f)
        flakes(f)
        bpy.context.view_layer.update()
    print('DEVICE',device,'SAMPLES',scene.cycles.samples,flush=True)
    if args.preview:
        frame_state(args.preview)
        scene.render.resolution_percentage=args.percent
        scene.render.filepath=str(out/f'preview-{args.preview}.png')
        with quiet_blender(out):
            bpy.ops.render.render(write_still=True)
        return
    (out/'frames').mkdir(exist_ok=True)
    start=time.monotonic()
    for f in range(1,181):
        frame_state(f)
        scene.render.filepath=str(out/'frames'/f'{f:04d}.png')
        with quiet_blender(out):
            bpy.ops.render.render(write_still=True)
        if f%30==0:
            print('PROGRESS',f,round(time.monotonic()-start,2),flush=True)
    elapsed=time.monotonic()-start
    print('RENDER_SECONDS',round(elapsed,3),'SECONDS_PER_FRAME',round(elapsed/180,3),flush=True)
    encode(out,ff)


if __name__=='__main__':
    main()

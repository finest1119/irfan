"""ED-01 v3. Metres, 24 fps. Run with Blender; -- --preview writes the CPU review set."""
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[2] / "pipeline" / "cutaway"))
import cutlib as C

R = random.Random(4101)
TAU = math.tau
S = C.strand
M = C.material
STILLS = ["beat1_hook", "beat2_inflow", "beat3_level", "beat4_outflow"]
INVERT = -1.08
DRAIN_LEVEL = -.115
GUTTER_Y = 6.795
PIPE_X = .075
SHOE = Vector((PIPE_X, 6.665, .322))
DROP_X = -.203
DROP_Y = 6.767
DROP_TIP = 2.4445
RELEASE = 51
DROP_FLIGHT = math.sqrt(2 * (DROP_TIP - DRAIN_LEVEL) / 9.81)
IMPACT = RELEASE + 24 * DROP_FLIGHT
EXIT_VY, EXIT_VZ = -.91, -.66
EXIT_TANGENT = Vector((0,EXIT_VY,EXIT_VZ)).normalized()
EXIT_UP = Vector((-1,0,0)).cross(EXIT_TANGENT)
WET_LIP = SHOE - EXIT_UP*(.0516-.026)
JET_FLIGHT = (EXIT_VZ + math.sqrt(EXIT_VZ**2 + 2*9.81*(WET_LIP.z-DRAIN_LEVEL))) / 9.81
IMPACT_XY = (PIPE_X, WET_LIP.y + EXIT_VY*JET_FLIGHT)


def device(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.refresh_devices()
        available = list(prefs.devices)
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


def bevel(obj, width, segments=3):
    mod = obj.modifiers.new("Machined or eased edge", 'BEVEL')
    mod.width, mod.segments = width, segments
    mod.limit_method = 'ANGLE'
    mod.harden_normals = True
    obj.modifiers.new("Broad face normals", 'WEIGHTED_NORMAL').keep_sharp = True
    return obj


def B(name, center, size, mat, bevel_width=None):
    width = min(.008, min(size)*.12) if bevel_width is None else bevel_width
    obj = C.box(name, center, size, mat)
    return bevel(obj, min(width, min(size)*.23)) if width else obj


def node_noise(mat, coord, scale, detail=3, stretch=None):
    n, link = mat.node_tree.nodes, mat.node_tree.links.new
    if stretch:
        mult = n.new("ShaderNodeVectorMath")
        mult.operation = 'MULTIPLY'
        mult.inputs[1].default_value = stretch
        link(coord, mult.inputs[0])
        coord = mult.outputs[0]
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value, tex.inputs["Detail"].default_value = scale, detail
    link(coord, tex.inputs["Vector"])
    return tex.outputs["Fac"]


def ramp(mat, signal, stops):
    node = mat.node_tree.nodes.new("ShaderNodeValToRGB")
    elements = node.color_ramp.elements
    for i, (pos, value) in enumerate(stops):
        e = elements[i] if i < 2 else elements.new(pos)
        e.position = pos
        e.color = C.color(value) if isinstance(value, str) else (value, value, value, 1)
    mat.node_tree.links.new(signal, node.inputs[0])
    return node.outputs[0]


def mix(mat, weight, a, b, mode='MIX'):
    node = mat.node_tree.nodes.new("ShaderNodeMixRGB")
    node.blend_type = mode
    for socket, value in zip(node.inputs, (weight, a, b)):
        if isinstance(value, bpy.types.NodeSocket):
            mat.node_tree.links.new(value, socket)
        elif isinstance(value, str):
            socket.default_value = C.color(value)
        else:
            socket.default_value = value
    return node.outputs[0]


def relief(mat, height, distance, strength, previous=None):
    bump = mat.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value, bump.inputs["Strength"].default_value = distance, strength
    mat.node_tree.links.new(height, bump.inputs["Height"])
    if previous is not None:
        mat.node_tree.links.new(previous, bump.inputs["Normal"])
    return bump.outputs[0]


def surface(name, rgb, light, scale, rough=.65, grain=.0014, metal=0, stretch=None):
    mat = M(name, rgb, rough=rough, metal=metal)
    n, link = mat.node_tree.nodes, mat.node_tree.links.new
    p = n["Principled BSDF"]
    pos = n.new("ShaderNodeTexCoord").outputs["Object"]
    weather = node_noise(mat, pos, scale, 4, stretch)
    grain_noise = node_noise(mat, pos, 420, 2, stretch)
    link(ramp(mat, weather, [(.23,rgb),(.78,light)]), p.inputs["Base Color"])
    link(ramp(mat, weather, [(.23,max(.035,rough-.16)),(.78,min(.96,rough+.16))]), p.inputs["Roughness"])
    link(relief(mat,grain_noise,grain,.25),p.inputs["Normal"])
    return mat


def damp_scan(asset, metres, dark, light, wet_rough):
    mat = C.polyhaven(asset, metres)
    n, link = mat.node_tree.nodes, mat.node_tree.links.new
    p = n["Principled BSDF"]
    color_in, rough_in = p.inputs["Base Color"], p.inputs["Roughness"]
    albedo, roughness = color_in.links[0].from_socket, rough_in.links[0].from_socket
    pos = n.new("ShaderNodeNewGeometry").outputs["Position"]
    wet = ramp(mat,node_noise(mat,pos,1.75,4),[(.30,.10),(.66,.89)])
    # Keep the scan's pits and aggregate while cooling the exposed wet surface.
    value = n.new("ShaderNodeRGBToBW")
    link(albedo, value.inputs[0])
    body = ramp(mat, value.outputs[0], [(.025,dark),(.58,light)])
    link(mix(mat,wet,body,"919c97",'MULTIPLY'),color_in)
    link(mix(mat,wet,roughness,(wet_rough,)*3+(1,)),rough_in)
    link(wet,p.inputs["Coat Weight"])
    p.inputs["Coat Roughness"].default_value=.15
    casting = relief(mat,value.outputs[0],.0035,.28)
    link(relief(mat,node_noise(mat,pos,310,2),.0009,.21,casting),p.inputs["Normal"])
    return mat


def galvanised():
    mat = surface("Folded zinc • spangle, brushing and rain film","778989","bdc3b6",6,.37,.00032,.93,(1,1,2.8))
    n, link = mat.node_tree.nodes, mat.node_tree.links.new
    p = n["Principled BSDF"]
    xyz = n.new("ShaderNodeNewGeometry").outputs["Position"]
    cell = n.new("ShaderNodeTexVoronoi")
    cell.inputs["Scale"].default_value=430
    link(xyz,cell.inputs["Vector"])
    base=p.inputs["Base Color"].links[0].from_socket
    spangle=ramp(mat,cell.outputs["Color"],[(.15,"829396"),(.83,"e0e2d5")])
    link(mix(mat,.30,base,spangle,'MULTIPLY'),p.inputs["Base Color"])
    wiped=node_noise(mat,xyz,22,3,(.32,2.6,1.8))
    gloss=ramp(mat,wiped,[(.26,.21),(.77,.49)])
    finish=mix(mat,.14,gloss,cell.outputs["Color"])
    # A partial handling print catches the light on the repaired lap at macro distance.
    local=n.new("ShaderNodeVectorMath")
    local.operation='SUBTRACT'
    local.inputs[1].default_value=(DROP_X+.011,GUTTER_Y-.1273*math.cos(.87),2.57-.1273*math.sin(.87))
    link(xyz,local.inputs[0])
    oval=n.new("ShaderNodeVectorMath")
    oval.operation='MULTIPLY'
    oval.inputs[1].default_value=(91,139,139)
    link(local.outputs[0],oval.inputs[0])
    radius=n.new("ShaderNodeVectorMath")
    radius.operation='LENGTH'
    link(oval.outputs[0],radius.inputs[0])
    mask=ramp(mat,radius.outputs["Value"],[(.31,.36),(.97,0)])
    ridges=n.new("ShaderNodeTexWave")
    ridges.wave_type='RINGS'
    ridges.inputs["Scale"].default_value=6.3
    ridges.inputs["Distortion"].default_value=2.3
    link(oval.outputs[0],ridges.inputs[0])
    thin_oil=ramp(mat,ridges.outputs["Fac"],[(.18,.20),(.81,.45)])
    link(mix(mat,mask,finish,thin_oil),p.inputs["Roughness"])
    anisotropy=next((socket for socket in p.inputs if socket.name in
                     {"Anisotropic IOR Level","Anisotropy","Anisotropic","Anisotropic Weight"}),None)
    if anisotropy is not None:
        anisotropy.default_value=.23
    return mat


def aggregate():
    mat=surface("Sawn cement paste and mineral inclusions","84847c","b1b0a3",13,.69,.0008)
    n, link=mat.node_tree.nodes,mat.node_tree.links.new
    p=n["Principled BSDF"]
    pos=n.new("ShaderNodeNewGeometry").outputs["Position"]
    cell=n.new("ShaderNodeTexVoronoi")
    cell.feature='F1'
    cell.inputs["Scale"].default_value=80
    link(pos,cell.inputs["Vector"])
    paste=p.inputs["Base Color"].links[0].from_socket
    mineral=ramp(mat,cell.outputs["Color"],[(.20,"54564e"),(.80,"d1c7ae"),(.49,"8e897b")])
    broken=ramp(mat,cell.outputs["Distance"],[(.35,.92),(.53,.0)])
    link(mix(mat,broken,paste,mineral),p.inputs["Base Color"])
    return mat


def thin_leaf(name, dark, light):
    mat=surface(name,dark,light,18,.43,.00035,stretch=(1.0,2.1,.64))
    p=mat.node_tree.nodes["Principled BSDF"]
    p.inputs["Subsurface Weight"].default_value=.24
    p.inputs["Subsurface Radius"].default_value=(.72,1,.31)
    p.inputs["Subsurface Scale"].default_value=.00085
    p.inputs["Coat Weight"].default_value=.24
    p.inputs["Coat Roughness"].default_value=.21
    return mat


def tube(name, path, radius, bore, mat, inner=None, segments=48):
    """Closed swept annulus with parallel-transported cross sections and a clear bore."""
    path=[Vector(co) for co in path]
    verts,faces,ids=[],[],[]
    last=None
    for i,point in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(0,i-1)]).normalized()
        if last is None:
            last=Vector((1,0,0)) if abs(tangent.x)<.8 else Vector((0,0,1))
        side=(last-tangent*last.dot(tangent)).normalized()
        up=tangent.cross(side)
        last=side
        for r in (radius,bore):
            for j in range(segments):
                angle=TAU*j/segments
                verts.append(point+r*(side*math.cos(angle)+up*math.sin(angle)))
    for i in range(len(path)-1):
        for j in range(segments):
            k,l=i*2*segments+j,i*2*segments+(j+1)%segments
            faces += [(k,l,l+2*segments,k+2*segments),
                      (k+segments,k+3*segments,l+3*segments,l+segments)]
            ids += [0,1]
    for j in range(segments):
        k=(j+1)%segments
        for offset,rev in ((0,True),((len(path)-1)*2*segments,False)):
            f=tuple(offset+x for x in (j,k,k+segments,j+segments))
            faces.append(f[::-1] if rev else f)
            ids.append(2)
    obj=C.mesh(name,verts,faces,mat)
    if inner:
        obj.data.materials.append(inner)
    for poly,idx in zip(obj.data.polygons,ids):
        poly.use_smooth=idx!=2
        poly.material_index=int(idx==1 and inner is not None)
    return bevel(obj,min(.002,(radius-bore)*.19),2)


def screw(name, point, normal, radius, mat):
    """Raised washer, hex head and recessed hex drive, seated on the supplied surface."""
    axis=Vector(normal).normalized()
    basis=axis.to_track_quat('Z','Y')
    origin=Vector(point)
    verts,faces=[],[]
    sections=((1,0,24),(1,.14,24),(.91,.20,24),(.75,.20,6),(.72,.55,6),
              (.61,.62,6),(.33,.62,6),(.28,.52,6),(.28,.31,6))
    # Use four samples per hex side so every ring has matching topology.
    for r,h,n in sections:
        ring=[Vector((r*math.cos(TAU*j/n),r*math.sin(TAU*j/n),h)) for j in range(n)]
        for j in range(24):
            u=j*n/24
            local=ring[int(u)].lerp(ring[(int(u)+1)%n],u%1)*radius
            verts.append(origin+basis@local)
    for k in range(len(sections)-1):
        for j in range(24):
            a=k*24+j; b=k*24+(j+1)%24
            faces.append((a,b,b+24,a+24))
    faces.append(tuple(range(24*(len(sections)-1),24*len(sections))))
    faces.append(tuple(reversed(range(24))))
    return C.mesh(name,verts,faces,mat)


def lettering(name, text, point, height, mat, rotation=(math.pi/2,0,0), align='CENTER'):
    data=bpy.data.curves.new(name,'FONT')
    data.body, data.size, data.align_x=text,height,align
    data.align_y='CENTER'
    data.extrude=.00018
    data.bevel_depth=.00008
    obj=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location,obj.rotation_euler=point,rotation
    data.materials.append(mat)
    return obj


def tiles(x0,x1,y,z,depth,slope,mats):
    verts,faces,ids=[],[],[]
    cols,rows=round((x1-x0)/.275),math.ceil(depth/.32)
    pitch,step=(x1-x0)/cols,depth/rows
    profile=((0,.008),(.09,.013),(.18,.041),(.27,.050),(.35,.043),(.45,.017),
             (.57,.005),(.77,0),(.93,.002),(1,.008))
    m=len(profile)
    for row in range(rows):
        for col in range(cols):
            x,ya=x0+col*pitch,y+row*step
            start=len(verts)
            idx=R.choices(range(4),[8,6,3,1])[0]
            warp=R.uniform(-.003,.003)
            for dy,rise in ((-.019,.022),(step+.010,-.001)):
                # The return path forms the underside and the actual cut tile lip.
                contour=[(u,h) for u,h in profile]+[(u,h-.014) for u,h in reversed(profile)]
                for u,h in contour:
                    verts.append((x+.0008+u*(pitch-.0016),ya+dy,z+(ya+dy-y)*slope+rise+h+warp*u))
            size=2*m
            faces.extend([tuple(start+j for j in reversed(range(size))),
                          tuple(start+size+j for j in range(size))])
            for j in range(size):
                k=(j+1)%size
                faces.append((start+j,start+k,start+k+size,start+j+size))
            ids.extend([idx]*(size+2))
    obj=C.mesh("Lapped clay pantiles • solid arrises",verts,faces,mats[0])
    for mat in mats[1:]:
        obj.data.materials.append(mat)
    for poly,idx in zip(obj.data.polygons,ids):
        poly.material_index=idx
    return bevel(obj,.0016,2)


def gutter_shell(name, a, b, y, z, radius, thickness, mat):
    count=44
    v,f=[],[]
    for x in (a,b):
        for r in (radius,radius-thickness):
            for j in range(count+1):
                theta=math.pi*j/count
                v.append((x,y-r*math.cos(theta),z-r*math.sin(theta)))
    step=count+1
    for j in range(count):
        f.extend([(j,j+1,j+1+2*step,j+2*step),
                  (j+step,j+3*step,j+1+3*step,j+1+step),
                  (j,j+step,j+step+1,j+1),
                  (j+2*step,j+2*step+1,j+3*step+1,j+3*step)])
    for j in (0,count):
        face=(j,j+2*step,j+3*step,j+step)
        f.append(face if j==0 else face[::-1])
    obj=C.mesh(name,v,f,mat)
    for i,poly in enumerate(obj.data.polygons):
        poly.use_smooth=i<4*count and i%4 in (0,1)
    return obj


def gutter(a,b,y,z,p,house):
    metal=p["metal"]
    shell=gutter_shell("Spun half-round rain gutter",a,b,y,z,.125,.0018,metal)
    x=house+PIPE_X
    hole(shell,(x,y,z-.125),(0,0,1),.050)
    bevel(shell,.00045,2)
    for dy in (-.125,.125):
        S("Hemmed zinc bead",[(a,y+dy,z),(b,y+dy,z)],.0048,metal)
    for j in range(5):
        at=a+.18+(b-a-.38)*j/4
        strap=gutter_shell("Bent fascia hanger",at-.012,at+.012,y,z,.129,.0036,p["fastener"])
        bevel(strap,.0008,2)
        B("Hanger heel",(at,y+.141,z-.031),(.026,.037,.068),p["fastener"],.002)
    seam=house+DROP_X
    strap=gutter_shell("Double-lap zinc repair sleeve",seam-.023,seam+.023,y,z,.1273,.0023,metal)
    bevel(strap,.0005,2)
    for edge in (seam-.023,seam+.023):
        arc=[(edge,y-.127*math.cos(i*math.pi/36),z-.127*math.sin(i*math.pi/36)) for i in range(37)]
        S("Soldered capillary seam",arc,.0016,p["solder"])
    for dx in (-.012,.012):
        for ang in (.45,1.12):
            normal=Vector((0,-math.cos(ang),-math.sin(ang)))
            screw("Gutter stitch screw",Vector((seam+dx,y,z))+normal*.1273,normal,.0054,p["fastener"])
    C.sphere("Solder pool at the low seam",(seam,DROP_Y,DROP_TIP+.0014),(.0041,.0037,.0016),p["solder"])
    if house==0:
        trail=[]
        for i in range(18):
            t=i/17
            angle=1.04+.31*t
            trail.append((seam-.014*(1-t)**2,y-.1275*math.cos(angle),z-.1275*math.sin(angle)))
        S("Capillary film along the lap",trail,.00082,p["clear"])
    for xx in (a+.0009,b-.0009):
        arc=[(xx,y-.1232*math.cos(math.pi*i/40),z-.1232*math.sin(math.pi*i/40)) for i in range(41)]
        stop=C.mesh("Crimped sheet-metal stop end",arc,[tuple(range(41))],metal)
        solid=stop.modifiers.new("Sheet gauge",'SOLIDIFY')
        solid.thickness=.0016
        bevel(stop,.00035,2)
    if house==0:
        for _ in range(64):
            dx=R.uniform(-.54,.33)
            ang=R.uniform(.16,1.48)
            if abs(dx)<.035 and ang>1:
                continue
            r=R.uniform(.00065,.00275)
            normal=Vector((0,-math.cos(ang),-math.sin(ang)))
            origin=Vector((seam+dx,y,z))+normal*.125
            bead=C.sphere("Rain pinned to zinc",origin,(r*.92,r,r*.44),p["clear"])
            bead.rotation_euler=normal.to_track_quat('Z','Y').to_euler()
    tube("Gutter outlet spigot",[(x,y,z-.112),(x,y,z-.205)],.053,.049,metal,p["solder"])


def downpipe(x,p):
    # Straight runs meet tangent quarter bends. The final segment sets the jet's tangent.
    x+=PIPE_X
    pts=[(x,GUTTER_Y,2.400),(x,GUTTER_Y,2.295)]
    def arc_corner(start,control,end):
        a,b,c=map(Vector,(start,control,end))
        return [a.lerp(b,j/8).lerp(b.lerp(c,j/8),j/8) for j in range(1,9)]
    pts+=arc_corner(pts[-1],(x,GUTTER_Y,2.265),(x,6.821,2.229))
    pts+=[(x,6.877,2.150)]
    pts+=arc_corner(pts[-1],(x,6.904,2.112),(x,6.904,2.076))
    pts+=[(x,6.904,.550)]
    pts+=arc_corner(pts[-1],(x,6.904,.495),(x,6.848,.454))
    pts+=[(x,SHOE.y,SHOE.z)]
    tube("110 mm rainwater leader with swept shoe",pts,.055,.0516,p["pipe"],p["solder"])
    for y,z in ((GUTTER_Y,2.384),(6.904,2.074),(6.904,.572)):
        tube("Solvent-weld socket",[(x,y,z-.031),(x,y,z+.031)],.060,.0551,p["pipe"])
    end=Vector(pts[-1])
    tangent=(end-Vector(pts[-2])).normalized()
    tube("Rolled shoe cuff",[end-tangent*.052,end+tangent*.002],.059,.0549,p["pipe"])
    for z in (.728,1.79):
        tube("Split stainless saddle",[(x,6.904,z-.014),(x,6.904,z+.014)],.0586,.0551,p["metal"])
        for sign in (-1,1):
            bx=x+sign*.065
            B("Pressed saddle foot",(bx,6.939,z),(.035,.051,.028),p["metal"],.0025)
            screw("Saddle fixing",(bx,6.9135,z),(0,-1,0),.007,p["fastener"])
        B("Saddle spacer",(x,6.957,z),(.091,.016,.029),p["joint"],.002)
    if abs(x-PIPE_X)<.001:
        lettering("Pipe diameter stamp","110 mm",(x,6.8485,.638),.012,p["ink"])
    return end


def frontage(x,p):
    # Partition the front wall around the actual window and door openings.
    left,right=x-4.27,x+.18
    door=(x-3.98,x-3.06)
    win=(x-2.61,x-.63)
    front=9.36
    for a,b,lo,hi in ((left,door[0],0,3.30),(door[1],win[0],0,3.30),(win[1],right,0,3.30),
                       (*door,2.14,3.30),(*win,0,.88),(*win,2.20,3.30)):
        B("Rendered facade and window reveals",((a+b)/2,front,(lo+hi)/2),(b-a,.22,hi-lo),p["plaster"])
    B("Dim porch interior",(x-2.045,11.04,1.60),(4.42,.20,3.20),p["interior"])
    for a in (left+.065,right-.065):
        B("Party wall behind facade",(a,10.51,1.55),(.13,2.55,3.10),p["plaster"])
    B("Window sill",(x-1.62,9.195,.879),(2.14,.23,.078),p["cream"],.009)
    for dx in (-1.012,1.012):
        B("Rebated window jamb",(x-1.62+dx,9.21,1.55),(.068,.12,1.42),p["cream"])
    B("Window head",(x-1.62,9.21,2.221),(2.09,.12,.078),p["cream"])
    for j in range(13):
        cx=x-2.60+j*.066
        B("Curtain fold",(cx,9.57+.023*math.sin(j*1.7),1.52),(.067,.035,1.38),p["fabric"],.012)
    B("Porch number plate",(x-.32,9.225,2.04),(.188,.018,.128),p["ink"],.009)
    number=str(18+2*round(x/4.45))
    lettering("House number",number,(x-.32,9.215,2.04),.085,p["cream"])


def plant(x,y,z,size, mats):
    v,f,ids=[],[],[]
    for _ in range(75):
        a=R.uniform(0,TAU)
        length=R.uniform(.27,1)*size
        elev=R.uniform(.25,1.23)
        idx=len(v)
        material=R.randrange(len(mats))
        blade_width=size*R.uniform(.028,.067)
        for k in range(8):
            t=k/7
            d=length*t*math.cos(elev)
            h=length*(math.sin(elev)*t+.26*math.sin(math.pi*t))
            w=blade_width*max(.009,math.sin(t*math.pi))
            for side in (-1,0,1):
                v.append((x+d*math.cos(a)-side*w*math.sin(a),y+d*math.sin(a)+side*w*math.cos(a),z+h-abs(side)*w*.42))
            if k:
                j=idx+(k-1)*3
                f.extend([(j,j+3,j+4,j+1),(j+1,j+4,j+5,j+2)])
                ids.extend([material,material])
    ob=C.mesh("Clump of rain-wet strap leaves",v,f,mats[0])
    ob.modifiers.new("Leaf thickness",'SOLIDIFY').thickness=.00065
    for m in mats[1:]:
        ob.data.materials.append(m)
    for poly,i in zip(ob.data.polygons,ids):
        poly.material_index=i
        poly.use_smooth=True


def houses(p):
    tiles_m=[surface("Oxide clay "+a,a,b,9,.47) for a,b in [
        ("89513e","b0765d"),("85533f","ab6950"),("814d3e","af765f"),("694a3e","976851")]]
    for h in range(-2,4):
        x=h*4.45
        a,b=x-4.27,x+.18
        frontage(x,p)
        tiles(a,b,8.93,3.45,3.4,.48,tiles_m)
        B("Main eaves fascia",(x-2.045,9.02,3.35),(4.44,.12,.19),p["cream"])
        if h in (0,2):
            # Rolled bamboo shade at selected porches breaks up the terrace rhythm.
            tube("Rolled bamboo blind",[(x-4.05,7.18,2.34),(x-2.46,7.18,2.34)],.065,.014,p["wood"])
            for j in range(6):
                B("Blind slat",(x-3.25,7.18,2.32-j*.032),(1.60,.025,.026),p["wood"],.004)
            for xx in (x-3.88,x-2.65):
                S("Blind cord",[(xx,7.15,2.43),(xx,7.15,2.14)],.006,p["cream"])
        tiles(a,b,6.88,2.56,2.43,.24,tiles_m)
        S("Clay ridge capping",[(a,12.34,5.075),(b,12.34,5.075)],.109,tiles_m[1])
        bevel(C.beam("Cement party-wall coping",(a,9.04,3.60),(a,12.34,5.185),.135,.106,p["concrete"]),.006)
        B("Porch ceiling fixture",(x-1.36,8.25,2.78),(.36,.14,.073),p["cream"],.035)
        B("Meter box",(x-.42,9.16,1.58),(.29,.15,.41),p["cream"],.027)
        B("Meter sight glass",(x-.42,9.074,1.63),(.159,.02,.109),p["glass"],.012)
        S("Meter conduit",[(x-.42,9.15,1.38),(x-.42,9.15,.29)],.016,p["pipe"])
        for j in range(7):
            B("Fanlight louvre",(x-3.52,9.15,2.24+j*.039),(.88,.050,.022),p["wood"])
        B("Fascia board",(x-2.05,6.985,2.46),(4.44,.12,.15),p["cream"],.009)
        soffit=B("Painted porch soffit",(x-2.05,8.11,2.70),(4.42,2.57,.07),p["cream"])
        soffit.rotation_euler.x=math.atan(.24)
        for zz in (2.45,3.14):
            B("Party wall cornice",(x+.015,9.60,zz),(.29,.69,.14),p["cream"],.014)
        B("Square porch pier",(x+PIPE_X,7.10,1.26),(.24,.27,2.52),p["plaster"],.015)
        B("Pier plinth",(x+PIPE_X,7.10,.21),(.30,.33,.42),p["concrete"],.014)
        B("Porch paving",(x-2.04,8.21,.047),(4.44,2.42,.10),p["paving"])
        for dx in (.72,1.58,2.44,3.30,4.16):
            B("Tile joint",(x-dx,8.21,.100),(.009,2.36,.002),p["joint"])
        for yy in (7.42,8.05,8.68):
            B("Tile joint",(x-2.04,yy,.100),(4.44,.009,.002),p["joint"])
        B("Teak entrance",(x-3.52,9.225,1.10),(.92,.09,2.05),p["wood"],.018)
        for c in (-4.018,-3.022):
            B("Timber door casing",(x+c,9.217,1.10),(.076,.088,2.13),p["wood"])
        B("Door casing head",(x-3.52,9.217,2.176),(1.07,.088,.079),p["wood"])
        B("Latch escutcheon",(x-3.151,9.175,1.10),(.028,.012,.118),p["metal"],.005)
        S("Door lever",[(x-3.151,9.167,1.12),(x-3.151,9.121,1.12),(x-3.232,9.121,1.116)],.009,p["metal"])
        for dz in (.65,1.56):
            B("Timber door panel",(x-3.52,9.17,dz),(.70,.045,.70),p["wood"],.025)
        B("Window mullion",(x-1.62,9.164,1.55),(.043,.035,1.33),p["cream"])
        B("Tinted glazing",(x-1.62,9.142,1.55),(1.99,.032,1.33),p["glass"])
        for zz in (1.24,1.46,1.67,1.89):
            B("Glass louvre edge",(x-1.62,9.122,zz),(1.95,.018,.012),p["metal"])
        for dx in range(9):
            B("Fixed security grille",(x-2.57+dx*.24,9.10,1.55),(.019,.027,1.32),p["ink"])
        for zz in (1.02,1.56,2.08):
            B("Window grille transom",(x-1.62,9.09,zz),(2,.029,.023),p["ink"])
        gutter(a+.002,b-.002,GUTTER_Y,2.57,p,x)
        downpipe(x,p)
        # Low-voltage service line and clips, fixed to the rendered wall.
        points=[(x-4.23,9.235,2.76),(x-3.03,9.235,2.72),(x-1.70,9.235,2.735),(x-.42,9.235,2.77)]
        S("Weathered service cable",points,.008,p["rubber"])
        for dx in (.42,1.70,3.03):
            B("Conduit clip",(x-dx,9.235,2.748),(.029,.032,.064),p["metal"])
        plant(x-2.76,8.92,.389,.59,p["foliage"])
        bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.15,radius2=.22,depth=.29,location=(x-2.76,8.92,.185))
        pot=bpy.context.object
        pot.name="Unglazed porch planter"
        pot.location.z=.245
        pot.data.materials.append(tiles_m[1])
        bevel(pot,.007)


def wheel(x,y,r,material,thickness):
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=10,location=(x,y,.30),
                                    rotation=(math.pi/2,0,0),major_radius=r,minor_radius=thickness)
    bpy.context.object.data.materials.append(material)


def kapcai(p):
    before=set(bpy.context.scene.objects)
    x,y=3.06,5.57
    for dx in (-.62,.62):
        wheel(x+dx,y,.255,p["rubber"],.049)
        wheel(x+dx,y,.214,p["metal"],.016)
        for i in range(16):
            a=TAU*i/16
            S("Wheel spoke",[(x+dx,y-.023,.30),(x+dx+.209*math.cos(a),y-.018,.30+.209*math.sin(a))],.004,p["metal"])
    def part(n,coords,r,mat):
        return S(n,[(x+a,y+b,c) for a,b,c in coords],r,mat)
    part("Rear arm",[(-.62,0,.30),(-.04,0,.37),(.34,0,.82)],.045,p["metal"])
    part("Step-through pressed frame",[(-.58,0,.69),(-.16,0,.65),(.05,0,.43),(.39,0,.89)],.095,p["ink"])
    for dy in (-.07,.07):
        part("Front fork",[(.62,dy,.30),(.39,dy,.89)],.027,p["metal"])
    for name,pos,scale,mat in [
        ("Long vinyl saddle",(-.35,0,.785),(.40,.145,.079),p["rubber"]),
        ("Side panel",(-.37,0,.66),(.34,.14,.13),p["cream"]),
        ("Engine casing",(-.04,0,.38),(.185,.125,.13),p["metal"]),
        ("Headlight nacelle",(.40,0,.97),(.15,.135,.111),p["ink"]),
        ("Headlamp glass",(.511,0,.977),(.048,.106,.076),p["glass"])]:
        C.sphere(name,(x+pos[0],y+pos[1],pos[2]),scale,mat)
    part("Handlebars",[(.37,-.25,1.00),(.41,0,1.01),(.37,.25,1.00)],.026,p["rubber"])
    part("Stainless exhaust",[(-.04,-.13,.36),(-.16,-.16,.25),(-.74,-.16,.32)],.043,p["metal"])
    part("Stand",[(-.16,-.06,.35),(-.24,-.21,-.004)],.015,p["ink"])
    part("Mirror stalk",[(.39,-.13,1.02),(.42,-.20,1.24)],.009,p["metal"])
    C.sphere("Oval mirror",(x+.42,y-.20,1.25),(.066,.022,.046),p["ink"])

    for dx in (-.62,.62):
        points=[(dx+.303*math.cos(a),-.005,.30+.303*math.sin(a))
                for a in [math.radians(28+j*124/22) for j in range(23)]]
        part("Pressed mudguard",points,.030,p["ink"])
        tube("Wheel hub",[(x+dx,y-.055,.30),(x+dx,y+.055,.30)],.049,.012,p["metal"])
    tube("Front brake disc",[(x+.62,y-.063,.30),(x+.62,y-.058,.30)],.118,.077,p["fastener"])
    part("Front brake hose",[(.38,-.19,1.0),(.38,-.13,.79),(.49,-.11,.57),(.62,-.07,.36)],.006,p["rubber"])
    part("Rear lamp stay",[(-.43,0,.72),(-.73,0,.69),(-.79,0,.62)],.017,p["metal"])
    C.sphere("Faded tail lamp",(x-.78,y,.68),(.051,.081,.035),p["oxide"])
    # Raise the entire parked bike by the measured tyre/road offset.
    for obj in set(bpy.context.scene.objects)-before:
        obj.location.z+=.080


def verge(p):
    rng=random.Random(207)
    v,faces,ids=[],[],[]
    for _ in range(12500):
        x,y=rng.uniform(-11,13),rng.uniform(2.68,3.29)
        h=rng.uniform(.018,.092)*(.74+.26*math.sin(x*6.1))
        w=rng.uniform(.004,.010)
        idx=len(v)
        v.extend([(x-w,y,.324),(x+w,y,.324),(x+rng.uniform(-.027,.027),y+rng.uniform(-.019,.019),.33+h)])
        faces.append((idx,idx+1,idx+2))
        ids.append(rng.randrange(3))
    turf=C.mesh("Cropped roadside grasses",v,faces,p["foliage"][0])
    for mat in p["foliage"][1:]:
        turf.data.materials.append(mat)
    for face,idx in zip(turf.data.polygons,ids):
        face.material_index=idx


def garden_palm(x,y,z,p,size):
    # Arching fronds with paired leaflets above the rear gardens.
    v,faces=[],[]
    top=Vector((x,y,z))
    S("Palm stem",[(x-.31,y+.12,.18),(x-.23,y+.12,z*.64),top],.142,p["wood"])
    for j in range(12):
        a=j*TAU/12
        radial=Vector((math.cos(a),math.sin(a),0))
        lateral=Vector((-math.sin(a),math.cos(a),0))
        length=size*(.83+.18*math.sin(7*a))
        def along(t):
            return top+radial*length*t+Vector((0,0,length*(1.12*t-1.42*t*t)))
        S("Palm rachis",[along(i/12) for i in range(13)],.019,p["foliage"][0])
        for k in range(1,30):
            t=k/31
            base=along(t)
            for side in (-1,1):
                d=length*.35*(.32+.68*math.sin(t*math.pi))*(1+R.uniform(-.19,.15))
                tip=base+(lateral*side*.81+radial*.33+Vector((0,0,-.54)))*d
                mid=base.lerp(tip,.53)+Vector((0,0,.14*d))
                idx=len(v)
                v.extend([base,mid-radial*.045,tip,mid+radial*.045])
                faces.append(tuple(range(idx,idx+4)))
    frond=C.mesh("Palm frond leaflets",v,faces,p["foliage"][0])
    frond.modifiers.new("Leaflet thickness",'SOLIDIFY').thickness=.00045


def rain_tree(x,y,height,spread,p,seed):
    rng=random.Random(seed)
    verts,faces,ids=[],[],[]
    trunk=Vector((x,y,0))
    fork=trunk+Vector((.22,-.1,height*.56))
    S("Rain tree trunk",[trunk,trunk+Vector((-.07,.04,height*.28)),fork],.185,p["wood"])
    for i in range(16):
        a=TAU*(i+rng.random()*.52)/16
        d=spread*rng.uniform(.27,.87)
        tip=Vector((x+d*math.cos(a),y+d*math.sin(a),height-.43*d+rng.uniform(-.22,.34)))
        elbow=fork.lerp(tip,.56)+Vector((0,0,.36))
        S("Branch above rear garden",[fork,elbow,tip],.046,p["wood"])
        for k in range(8):
            origin=tip+Vector((rng.uniform(-.71,.71),rng.uniform(-.61,.61),rng.uniform(-.47,.47)))
            for j in range(95):
                dx,dy,dz=rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-1,1)
                if dx*dx+dy*dy+dz*dz>1:
                    continue
                c=origin+Vector((.95*dx,.85*dy,.50*dz))
                rot=rng.uniform(0,TAU)
                l=rng.uniform(.06,.16)
                along=Vector((l*math.cos(rot),l*math.sin(rot),l*rng.uniform(-.7,.6)))
                across=Vector((-along.y,along.x,0))*.37
                start=len(verts)
                verts.extend([c-along,c-across,c+along,c+across,c+Vector((0,0,l*.19))])
                idx=rng.randrange(len(p["foliage"]))
                for n in range(4):
                    faces.append((start+n,start+(n+1)%4,start+4))
                    ids.append(idx)
    obj=C.mesh("Distant rain tree foliage",verts,faces,p["foliage"][0])
    for mat in p["foliage"][1:]:
        obj.data.materials.append(mat)
    for f,idx in zip(obj.data.polygons,ids):
        f.material_index=idx


def street(p):
    B("Damp bitumen carriageway",(0,4.64,.016),(62,2.70,.12),p["asphalt"])
    for y in (3.33,5.94):
        B("Chipped tar shoulder",(0,y,.071),(52,.092,.032),p["joint"])
    for x in range(-22,23,5):
        B("Worn centre dash",(x,4.77,.078),(1.38,.065,.006),p["stripe"])
    for xa,xb in ((-24,-2.39),(-.55,24)):
        C.bounds("Compacted road shoulder",xa,xb,2.72,5.98,-1.50,.024,p["soil"])
    C.bounds("Fill over box culvert",-2.39,-.55,2.73,5.98,-.065,.023,p["soil"])
    for a,b in ((-27,-2.22),(-.72,27)):
        B("Longkang invert beside collector",((a+b)/2,6.50,-.67),(b-a,1.10,.18),p["concrete"])
    B("Longkang house-side curb",(0,6.99,-.29),(54,.105,.74),p["concrete"],.015)
    for a,b,base in ((-27,-2.22,-.66),(-2.22,-.72,-.08),(-.72,27,-.66)):
        B("Longkang road-side curb",((a+b)/2,6.02,(base+.08)/2),(b-a,.105,.08-base),p["concrete"],.012)
    drain_water(p)
    for x in (-.83,.79,1.94):
        B("Curb expansion gasket",(x,6.020,.080),(.009,.099,.003),p["joint"],.001)
    # The deposited silt is visible through the shallow edge of the residual flow.
    for a,b in ((-26.9,-2.22),(-.72,26.9)):
        B("Grit on drain invert",((a+b)/2,6.50,-.558),(b-a,.91,.042),p["silt"])
    for _ in range(42):
        x=R.uniform(-1.5,1.5)
        y=R.choice((R.uniform(6.079,6.19),R.uniform(6.83,6.93)))
        r=R.uniform(.009,.036)
        C.sphere("Washed pea gravel",(x,y,-.538+r*.36),(r,r*.78,r*.53),p["silt"])
    for x in (-8.93,-4.48,4.42,8.87):
        B("Short driveway bridge",(x-2.33,6.50,.095),(2.24,1.12,.12),p["paving"],.025)
    B("Collector invert",(-1.47,4.68,-1.17),(1.84,4.49,.18),p["concrete"])
    for x in (-2.305,-.635):
        B("Collector sidewall",(x,4.68,-.63),(.17,4.49,.90),p["concrete"])
    B("Collector crown",(-1.47,4.68,-.1225),(1.84,4.49,.115),p["concrete"])
    for x in (-3.9,-.84,3.84,5.75,-5.04):
        plant(x,2.98,.335,.60,p["foliage"])
    verge(p)
    houses(p)
    garden_palm(1.20,16.8,5.46,p,1.64)
    garden_palm(-6.75,17.9,6.1,p,2.55)
    garden_palm(4.77,18.9,5.94,p,1.91)
    garden_palm(11.4,16.2,6.65,p,2.72)
    rain_tree(-4.9,17.8,6.24,2.78,p,418)
    rain_tree(9.4,19.5,6.38,3.02,p,71)
    kapcai(p)


def hole(wall, centre, axis, radius):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=2.1,location=centre)
    cutter=bpy.context.object
    cutter.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    mod=wall.modifiers.new("Cored outlet","BOOLEAN")
    mod.operation='DIFFERENCE'
    mod.object=cutter
    bpy.context.view_layer.objects.active=wall
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)


def flange_plate(origin, side, axis, radius, bore, mat):
    v,f=[],[]
    count=80
    for thickness in (0,.015):
        # Centre each inner loop on the pipe axis at this plate depth.
        for outer in (True,False):
            for j in range(count):
                a=TAU*j/count
                y=radius*math.cos(a) if outer else bore*math.cos(a)/axis.x+side*thickness*axis.y/axis.x
                z=(radius if outer else bore)*math.sin(a)
                v.append(origin+Vector((side*thickness,y,z)))
    for j in range(count):
        k=(j+1)%count
        faces=((j,k,2*count+k,2*count+j),(count+j,3*count+j,3*count+k,count+k),
               (j,count+j,count+k,k),(2*count+j,2*count+k,3*count+k,3*count+j))
        f.extend(face if side>0 else face[::-1] for face in faces)
    return bevel(C.mesh("Cast wall escutcheon",v,f,mat),.0018,2)


def rebar_end(x,z,r,mat):
    points=[(x+r*math.cos(i*TAU/16),-.00022,z+r*math.sin(i*TAU/16)) for i in range(16)]
    return C.mesh("Sawn reinforcing bar",points,[tuple(range(16))],mat)


def stain(x,y,top,length,mat):
    v=[]
    for i in range(12):
        t=i/11
        w=(.007+.008*math.sin(math.pi*t))*(1-.85*t)
        drift=.004*math.sin(t*7+x)
        for d in (-1,1):
            v.append((x+drift+d*w,y,top-t*length))
    return C.mesh("Runoff below form tie",v,[(2*i,2*i+2,2*i+3,2*i+1) for i in range(11)],mat)


def weathered_strata(mat):
    n,link=mat.node_tree.nodes,mat.node_tree.links.new
    shader=n["Principled BSDF"]
    original=shader.inputs["Base Color"].links[0].from_socket
    pos=n.new("ShaderNodeNewGeometry").outputs["Position"]
    lenses=node_noise(mat,pos,3.7,4,(.61,.8,6.7))
    layer=ramp(mat,lenses,[(.29,"69645a"),(.77,"eadac0")])
    link(mix(mat,.53,original,layer,'MULTIPLY'),shader.inputs["Base Color"])
    normal=shader.inputs["Normal"]
    prior=normal.links[0].from_socket if normal.is_linked else None
    link(relief(mat,lenses,.012,.32,prior),normal)


def embedded_stone(x0,x1,z0,z1,count,p,base=False):
    verts,faces,ids=[],[],[]
    grains=p["grains"] if base else p["clay_grains"]
    for _ in range(count):
        x,z=R.uniform(x0,x1),R.uniform(z0,z1)
        r=R.uniform(.007,.030) if base else R.uniform(.009,.065)
        h=r*R.uniform(.31,.78)
        angle=R.uniform(-.58,.58)
        front=.001 if base else .012*(1+math.sin(7*x+3*z)*math.cos(5*z-x))
        phase=R.uniform(0,TAU)
        start=len(verts)
        idx=R.randrange(len(grains))
        outline=[]
        for i in range(7):
            a=i*TAU/7+phase
            u,v=r*math.cos(a)*R.uniform(.81,1.18),h*math.sin(a)*R.uniform(.8,1.18)
            outline.append((u*math.cos(angle)-v*math.sin(angle),u*math.sin(angle)+v*math.cos(angle)))
        for factor,yy in ((.79,front-.0017),(1.0,front+.0038),(.70,front+r*.66)):
            verts.extend((x+u*factor,yy,z+v*factor) for u,v in outline)
        faces.append(tuple(start+i for i in range(7)))
        ids.append(idx)
        for k in (0,7):
            for j in range(7):
                after=(j+1)%7
                faces.append((start+k+j,start+k+j+7,start+k+after+7,start+k+after))
                ids.append(idx)
        faces.append(tuple(start+14+i for i in reversed(range(7))))
        ids.append(idx)
    obj=C.mesh("Cut mineral grains in the compacted layer",verts,faces,grains[0])
    for mat in grains[1:]:
        obj.data.materials.append(mat)
    for poly,idx in zip(obj.data.polygons,ids):
        poly.material_index=idx


def pond(p):
    wet=p["concrete"]
    # The inlet gauge witnesses the high-water mark. Keep the outlet concrete clean.
    gauge_wall=C.weathering(wet.copy(), -.495, .078, .68)
    earth=C.ground((-24,24),(.0,8),-2.015,layers=(("Lateritic subsoil",1.07,"44372f","78614b"),
                  ("Weathered parent rock",8.1,"3b3d39","6f685a")),roots=False,grains=0)
    earth+=C.ground((-20,-2.975),(0,3.31),.28,layers=(("Topsoil",.37,"332923","584632"),
                  ("Wet silty clay",1.92,"503c31","876447")),roots=False,grains=0)
    earth+=C.ground((2.745,17),(0,2.81),-1.533,layers=(("Stream bed",.53,"443d32","746951"),),roots=False,grains=0)
    for part in earth:
        weathered_strata(part.data.materials[0])
    C.section("Compacted roadbase under the pond",[(-2.975,-2.016),(2.745,-2.016),(2.745,-1.86),(-2.975,-1.86)],
              .002,2.70,p["roadbase"])
    embedded_stone(-2.957,2.727,-2.006,-1.869,420,p,base=True)
    embedded_stone(-6,6,-3.29,-2.038,400,p)
    embedded_stone(-6,-3.03,-1.77,.075,120,p)
    embedded_stone(2.83,6.1,-2.005,-1.56,80,p)
    slab=C.foundation("slab",(-.115,1.35,-1.70),(5.72,2.70,.32),wet)
    left=C.foundation("wall",(-2.805,1.35,-.60),(.34,2.70,1.88),wet)
    wall=B("Outlet headwall",(2.55,1.35,-.60),(.38,2.70,1.88),wet,0)
    axis=Vector((1,-.33,0)).normalized()
    centre=Vector((2.55,.81,INVERT+.165))
    hole(wall,centre,axis,.204)
    bevel(wall,.011)
    for part in (slab,left,wall):
        part.data.materials.append(p["aggregate"])
        aggregate_slot=part.data.materials.find(p["aggregate"].name)
        for poly in part.data.polygons:
            if poly.normal.y<-.99:
                poly.material_index=aggregate_slot
    tube("Rolled steel outlet, 330 mm clear", [centre-axis*.288,centre+axis*.84],
         .184,.165,p["outlet"],p["bore"],80)
    tube("Outlet welded stiffener",[centre+axis*.77,centre+axis*.79],.192,.184,
         p["solder"],segments=80)
    for side in (-1,1):
        # The pipe passes obliquely through a flat plate. Its aperture is an ellipse.
        face_x=centre.x+side*.19
        on_face=centre+axis*((face_x-centre.x)/axis.x)
        flange_plate(on_face,side,axis,.278,.186,p["outlet"])
        for i in range(8):
            angle=TAU*(i+.5)/8
            point=on_face+Vector((side*.015,.236*math.cos(angle),.236*math.sin(angle)))
            screw("Flange anchor",point,(side,0,0),.015,p["fastener"])
    # Raised longitudinal casting seam and a riveted plate on the downstream face.
    seam_normal=Vector((0,0,1))
    seam=[centre+axis*d+seam_normal*(.1838+.0007*math.sin(38*d)) for d in span(.223,.751,25)]
    S("Casting parting line",seam,.0017,p["solder"])
    B("Outlet identification plate",(2.744,.98,-.43),(.008,.36,.133),p["metal"],.003)
    for cy in (.829,1.131):
        screw("Plate rivet",(2.748,cy,-.43),(1,0,0),.006,p["fastener"])
    plate_rotation=(math.pi/2,0,math.pi/2)
    lettering("Outlet size","Ø330 mm",(2.7484,.98,-.411),.058,p["ink"],plate_rotation)
    lettering("Outlet function","SALUR KELUAR",(2.7484,.98,-.465),.025,p["ink"],plate_rotation)
    # Flush steel cross sections at their actual cover depth.
    for x in (-2.912,-2.696,2.426,2.672):
        for z in (-1.38,-1.05,-.72,-.39,-.06,.251):
            rebar_end(x,z,.0075,p["cutsteel"])
    for i in range(27):
        for z in (-1.789,-1.616):
            rebar_end(-2.86+i*.211,z,.008,p["cutsteel"])
    y=(2.435+2.70)/2
    for xa,xb,za,zb in ((-2.635,-2.22,-1.54,.34),(-.72,2.36,-1.54,.34),
                          (-2.22,-.72,-1.54,INVERT),(-2.22,-.72,-.08,.34)):
        B("Inlet headwall",((xa+xb)/2,y,(za+zb)/2),(xb-xa,.265,zb-za),gauge_wall,.012)
    for x in (-2.29,-.65):
        B("Cast inlet jamb",(x,2.36,-.651),(.14,.26,1.082),wet,.013)
    B("Cast inlet lintel",(-1.47,2.36,-.025),(1.78,.26,.17),wet,.015)
    for x in (-2.65,-.34,.64,1.62,2.19):
        for z in (.13,-.37,-1.08):
            C.sphere("Recessed form-tie plug",(x,2.429,z),(.021,.008,.021),p["joint"])
    # Depth is referenced to the slab surface at -1.54 m.
    B("Gauge rubber isolation pad",(.68,2.429,-.62),(.226,.012,1.55),p["joint"])
    B("Vitreous-enamel gauge",(.68,2.415,-.62),(.213,.017,1.53),p["cream"],.006)
    for i in range(3,32):
        z=-1.54+i*.05
        major=i%2==0
        w=.076 if i%10==0 else .057 if major else .028
        B("Fired gauge graduation",(.584+w/2,2.405,z),(w,.002,.010 if major else .005),p["ink"],.0007)
        if major and i%4==0:
            lettering("Gauge depth, metres",f"{i*.05:.1f}",(.723,2.4035,z),.059,p["ink"])
    for z in (-1.35,.10):
        screw("Gauge anchor",(.684,2.4065,z),(0,-1,0),.008,p["fastener"])
    B("Gauge title plate",(.68,2.423,.229),(.32,.022,.091),p["ink"],.006)
    lettering("Gauge title","ARAS AIR  /  m",(.68,2.411,.229),.037,p["cream"])
    for x in (-.125,1.52):
        B("Fine formwork joint",(x,2.434,.028),(.008,.004,.58),p["silt"],.001)
    for x in (-2.65,-.36,.98,2.18):
        for z in (-.31,.12):
            # Broken mineral run below selected ties, feathered into the concrete.
            stain(x,2.4346,z,R.uniform(.11,.27),p["stain"])
    C.bounds("Verge backing",-21.5,21.5,2.72,3.325,-.034,.195,p["soil"])
    B("Roadside grass verge",(0,2.99,.24),(43,.67,.18),C.polyhaven("aerial_grass_rock",2.5))
    B("Receiving channel invert",(6.87,.69,-1.45),(8.23,1.44,.16),wet)
    B("Receiving channel far bank",(6.87,1.37,-.86),(8.23,.20,1.18),wet)
    # Reverse profile fills the embankment against the outside of the U-channel.
    bank=C.section("Compacted receiving bank",[(1.46,-1.50),(2.78,-1.50),(2.78,.22),(2.65,.19),(1.46,-.272)],
                   -10.98,-2.75,p["soil"])
    bank.rotation_euler.z=math.pi/2


def water_material(name,tint,transmission,roughness,absorption=0,section=False):
    mat=M(name,tint,rough=roughness)
    n,link=mat.node_tree.nodes,mat.node_tree.links.new
    p=n["Principled BSDF"]
    p.inputs["Transmission Weight"].default_value=transmission
    p.inputs["IOR"].default_value=1.333
    pos=n.new("ShaderNodeNewGeometry").outputs["Position"]
    rain=node_noise(mat,pos,63,2,(1,1.65,.65))
    link(ramp(mat,rain,[(.22,roughness*.63),(.78,roughness*1.4)]),p.inputs["Roughness"])
    if absorption:
        link(relief(mat,rain,.00065,.14),p.inputs["Normal"])
        volume=n.new("ShaderNodeVolumeAbsorption")
        volume.inputs["Color"].default_value=(.40,.72,.63,1)
        volume.inputs["Density"].default_value=absorption
        link(volume.outputs[0],n["Material Output"].inputs["Volume"])
    if section:
        # The artificial sawn face presents a slightly diffuse view into the silt.
        coords=n.new("ShaderNodeSeparateXYZ")
        link(pos,coords.inputs[0])
        face=n.new("ShaderNodeMath")
        face.operation='LESS_THAN'
        link(coords.outputs["Y"],face.inputs[0])
        face.inputs[1].default_value=.016
        # Turbidity against a freshly opened section increases towards the fine bed sediment.
        z=n.new("ShaderNodeMapRange")
        z.inputs["From Min"].default_value=-1.54
        z.inputs["From Max"].default_value=-.56
        link(coords.outputs["Z"],z.inputs["Value"])
        sediment=ramp(mat,z.outputs["Result"],[(0,"5b6451"),(.99,"94ab91"),(.36,"798d79")])
        link(mix(mat,face.outputs[0],tint,sediment),p.inputs["Base Color"])
        link(mix(mat,face.outputs[0],(transmission,)*3+(1,),(.53,.53,.53,1)),p.inputs["Transmission Weight"])
        rippled=p.inputs["Roughness"].links[0].from_socket
        link(mix(mat,face.outputs[0],rippled,(.20,.20,.20,1)),p.inputs["Roughness"])
    return mat


def water_grid(name,xs,ys,bottom,surface,mat):
    """One manifold body. The rippled top shares vertices with the exposed section."""
    nx,ny=len(xs),len(ys)
    v=[(x,y,surface(x,y)) for y in ys for x in xs]
    f=[]
    for j in range(ny-1):
        for i in range(nx-1):
            k=j*nx+i
            f.append((k,k+1,k+1+nx,k+nx))
    top_faces=len(f)
    rim=list(range(nx))+[j*nx+nx-1 for j in range(1,ny)]
    rim+=list(range(nx*ny-2,nx*(ny-1)-1,-1))+[j*nx for j in range(ny-2,0,-1)]
    base=len(v)
    v.extend((v[k][0],v[k][1],bottom) for k in rim)
    bottom_rim=list(range(base,base+len(rim)))
    f.append(tuple(reversed(bottom_rim)))
    for j,k in enumerate(rim):
        after=(j+1)%len(rim)
        f.append((k,bottom_rim[j],bottom_rim[after],rim[after]))
    obj=C.mesh(name,v,f,mat)
    for i in range(top_faces):
        obj.data.polygons[i].use_smooth=True
    return obj


def span(a,b,count):
    return [a+(b-a)*i/(count-1) for i in range(count)]


def sediment_z(x,y):
    inlet=math.exp(-((x+1.47)/.67)**2-((y-2.38)/1.03)**2)
    along_wall=math.exp(-((x+2.63)/.50)**2)+math.exp(-((x-2.36)/.44)**2)
    silt=.010+.057*inlet+.026*along_wall
    return -1.54+silt*(.90+.13*math.sin(8*x+.8*math.cos(4*y))+.07*math.cos(11*y))


def drain_water(p):
    xs=[-26.9,-10,-4,-2]+span(-1.25,1.25,158)+[2,4,10,26.9]
    ys=span(6.073,6.936,56)
    def surface_z(x,y):
        dx,dy=x-IMPACT_XY[0],y-IMPACT_XY[1]
        r=math.hypot(dx,dy)
        dish=-.005*math.exp(-(r/.023)**2)
        lip=.009*math.exp(-((r-.037)/.014)**2)*(1+.26*math.sin(5*math.atan2(dy,dx)))
        return DRAIN_LEVEL+dish+lip+.0011*math.sin(21*y+3*x)*math.cos(9*x-y)
    obj=water_grid("Longkang • waves in the actual water surface",xs,ys,-.536,surface_z,p["water"])
    around=[]
    for i in range(11):
        a=i*TAU/11
        r=.036+.010*math.sin(3*a)
        around.append((IMPACT_XY[0]+r*math.cos(a),IMPACT_XY[1]+r*math.sin(a),.006,4))
    foam=foam_flecks("Air caught on the impact crown",around,surface_z,p["foam"],115)
    # The air on the crest and the water under it share both disturbances.
    for moving,coords in ((obj,[(x,y) for y in ys for x in xs]),
                          (foam,[(v.co.x,v.co.y) for v in foam.data.vertices])):
        moving.shape_key_add(name="Runoff and wind")
        for mode in range(2):
            key=moving.shape_key_add(name=("Runoff wave A","Runoff wave B")[mode])
            key.slider_min=-1
            for i,(x,y) in enumerate(coords):
                dx,dy=x-IMPACT_XY[0],y-IMPACT_XY[1]
                r=math.hypot(dx+.085*dy,dy*1.04)
                phase=82*r+.31*math.sin(15*dx+8*dy)+.19*math.cos(12*dy-5*dx)
                key.data[i].co.z+=.0061*math.exp(-r*6)*math.sin(phase+mode*math.pi/2)
            key.driver_add("value").driver.expression=f"{'cos' if mode==0 else '-sin'}(frame*.34)"
        for j in range(1,10):
            age=j*2/24
            key=moving.shape_key_add(name=f"Seam impact {j}")
            for i,(x,y) in enumerate(coords):
                r=math.hypot(x-DROP_X,y-DROP_Y)
                front=.61*age
                amp=.009*math.exp(-3.1*age-((r-front)/.055)**2)*math.cos(92*(r-front))
                key.data[i].co.z+=amp
            for dt,value in ((-2,0),(0,1),(2,0)):
                key.value=value
                key.keyframe_insert(data_path="value",frame=IMPACT+j*2+dt)
    return obj


def current(name,points,widths,heights,mat):
    """Closed fluted jet, with outward normals for refraction."""
    vs,faces=[],[]
    for k,point in enumerate(points):
        tangent=(Vector(points[min(len(points)-1,k+1)])-Vector(points[max(0,k-1)])).normalized()
        side=tangent.cross(Vector((0,0,1)))
        if side.length<.01:
            side=Vector((1,0,0))
        side.normalize()
        up=side.cross(tangent).normalized()
        for j in range(40):
            a=j*TAU/40
            flutter=1+.036*math.sin(5*a+k*.35)+.023*math.cos(3*a-k*.24)
            vs.append(Vector(point)+flutter*(side*widths[k]*math.cos(a)+up*heights[k]*math.sin(a)))
            if k:
                start=(k-1)*40+j
                after=(k-1)*40+(j+1)%40
                faces.append((start,start+40,after+40,after))
    faces.extend([tuple(range(40)),tuple(reversed(range(len(vs)-40,len(vs))))])
    obj=C.mesh(name,vs,faces,mat)
    for i in range(len(faces)-2):
        obj.data.polygons[i].use_smooth=True
    return obj


def foam_flecks(name,clusters,surface,mat,seed):
    rng=random.Random(seed)
    v,f=[],[]
    for x,y,reach,amount in clusters:
        for _ in range(amount):
            dx,dy=rng.gauss(0,reach),rng.gauss(0,reach*.56)
            cx,cy=x+dx,y+dy
            r=rng.uniform(.0013,.0065)
            start=len(v)
            for j in range(8):
                a=j*TAU/8
                px,py=cx+r*math.cos(a),cy+r*.76*math.sin(a)
                v.append((px,py,surface(px,py)+.00055))
            f.append(tuple(range(start,start+8)))
    return C.mesh(name,v,f,mat)


def leaf(p,length,angle):
    """Embossed midrib, asymmetric margins, secondary veins and wax on a closed blade."""
    verts,faces=[],[]
    sections=26
    for skin in range(2):
        for i in range(sections+1):
            t=i/sections
            width=length*.175*max(.009,math.sin(math.pi*t)**.92)*(1+.048*math.sin(13*t))
            for side in (-1,-.43,0,.43,1):
                x=length*(t-.5)+length*.016*side*math.sin(math.pi*t)
                y=width*side+length*.033*math.sin(math.pi*t*1.6)
                crown=length*(.019*(1-abs(side))+.010*side*math.sin(9*t))*math.sin(math.pi*t)
                z=.0008+length*(.031*t**5+.011*(1-t)**4)+crown-.00072*skin
                verts.append((x,y,z))
    stride=(sections+1)*5
    for i in range(sections):
        for j in range(4):
            a=i*5+j
            face=(a,a+5,a+6,a+1)
            faces.extend([face,tuple(k+stride for k in face[::-1])])
    rim=[i*5 for i in range(sections+1)]+list(range(5*sections+1,5*sections+5))
    rim += [5*i+4 for i in range(sections-1,-1,-1)]+[3,2,1]
    for i,a in enumerate(rim):
        b=rim[(i+1)%len(rim)]
        faces.append((a,a+stride,b+stride,b))
    blade=C.mesh("Water-green leaf • curved lamina",verts,faces,p["leaf"])
    for f in blade.data.polygons:
        f.use_smooth=True
    mid=[Vector(verts[i*5+2])+Vector((0,0,.00025)) for i in range(sections+1)]
    stem=S("Petiole and midrib",[(-length*.635,-.002,.003)]+mid,.00095,p["vein"])
    stem.parent=blade
    for i in range(3,22,3):
        for side in (-1,1):
            j=side*2
            branch=S("Leaf lateral vein",[mid[i],verts[(i+2)*5+2+side],verts[(i+4)*5+2+j]],.00034,p["vein"])
            branch.parent=blade
    blade.rotation_euler.z=angle
    return blade


def detention_water(p,stage,surface_z,culvert_z):
    """Weld the wet culvert to the basin. The sill is the step between the two beds."""
    xs=span(-2.634,-2.22,15)[:-1]+span(-2.22,-.72,51)[:-1]+span(-.72,2.359,104)
    ys=span(.012,2.435,83)
    nx,ny=len(xs),len(ys)
    verts=[(x,y,height(x,y)) for height in (surface_z,sediment_z) for y in ys for x in xs]
    offset=nx*ny
    faces=[]
    def quad(a,b,c,d):
        faces.append((a,b,c,d))
    for j in range(ny-1):
        for i in range(nx-1):
            a=j*nx+i
            quad(a,a+1,a+nx+1,a+nx)
    smooth_count=len(faces)
    faces.extend(tuple(v+offset for v in face[::-1]) for face in faces[:smooth_count])
    rim=list(range(nx))+[j*nx+nx-1 for j in range(1,ny)]
    rim+=list(range(nx*ny-2,nx*(ny-1)-1,-1))+[j*nx for j in range(ny-2,0,-1)]
    first=(ny-1)*nx+xs.index(-2.22)
    last=(ny-1)*nx+xs.index(-.72)
    jamb=list(range(first,last+1))
    sill=[]
    for k in jamb:
        sill.append(len(verts))
        verts.append((verts[k][0],ys[-1],INVERT))
    corner={first:sill[0],last:sill[-1]}
    for i,k in enumerate(rim):
        nxt=rim[(i+1)%len(rim)]
        if first<=nxt<k<=last:
            quad(sill[k-first],k+offset,nxt+offset,sill[nxt-first])
        else:
            face=[k]
            if k in corner: face.append(corner[k])
            face.extend((k+offset,nxt+offset))
            if nxt in corner: face.append(corner[nxt])
            face.append(nxt)
            faces.append(tuple(face))
    previous_top,previous_bottom=jamb,sill
    for y in span(ys[-1],6.922,14)[1:]:
        high,low=[],[]
        for height,row in ((culvert_z,high),(lambda x,y: INVERT,low)):
            for k in jamb:
                x=verts[k][0]
                row.append(len(verts))
                verts.append((x,y,height(x,y)))
        for i in range(len(jamb)-1):
            quad(previous_top[i],previous_top[i+1],high[i+1],high[i])
            quad(previous_bottom[i],low[i],low[i+1],previous_bottom[i+1])
        quad(previous_top[0],high[0],low[0],previous_bottom[0])
        quad(previous_top[-1],previous_bottom[-1],low[-1],high[-1])
        previous_top,previous_bottom=high,low
    for i in range(len(jamb)-1):
        quad(previous_top[i],previous_top[i+1],previous_bottom[i+1],previous_bottom[i])
    ob=C.mesh("One water body through inlet, sill and pond • "+stage,verts,faces,p["pond"])
    for i in range(smooth_count):
        ob.data.polygons[i].use_smooth=True
    return ob


def water_state(p,level,stage,leaf_xy):
    before=set(bpy.context.scene.objects)
    strength=.017 if stage=="inflow" else .009 if stage=="high" else .0027
    lift,spread={"inflow":(.115,.63),"high":(.023,.68),"low":(.033,.14)}[stage]
    def throat(x):
        u=min(1,abs(x+1.47)/spread)
        return lift*(1-u*u)**2
    def surface_z(x,y):
        r=math.hypot(x+1.47,(y-2.40)*1.08)
        r2=math.hypot(x-2.32,y-.89)
        wind=.0025*math.sin(19*y+1.3*math.sin(3*x)+.6*math.cos(6*x+2*y))
        incoming=strength*math.exp(-1.55*r)*math.sin(32*r-2*y+.40*math.sin(7*x))
        outgoing=.0038*math.exp(-3.0*r2)*math.cos(34*r2)
        distance=2.435-y
        falling=throat(x)*math.exp(-(distance/.36)**2)
        jump=.27*throat(x)*math.exp(-((distance-.43)/.12)**2)*math.sin(38*y+7*x)
        return level+wind+incoming+outgoing+falling+jump
    def culvert_z(x,y):
        join=math.exp(-max(y-2.435,0)*4)
        ripple=.002*math.sin(14*y+3*x)
        return join*surface_z(x,2.435)+(1-join)*(level+lift+ripple)
    detention_water(p,stage,surface_z,culvert_z)
    clusters=[]
    for i in range(9 if stage!="low" else 3):
        t=(i+.5)/10
        clusters.append((-1.47+.17*math.sin(7*t),2.405-.85*t,.027+.036*t,23))
    if stage=="inflow":
        for x in span(-1.93,-1.01,13):
            clusters.append((x,2.00+.10*math.cos((x+1.47)*4.5),.022,12))
    foam_flecks("Entrained air in the inlet wake",clusters,surface_z,p["foam"],831)
    x,y=leaf_xy
    blade=leaf(p,.264,.23 if stage!="low" else -.31)
    blade.location=(x,y,surface_z(x,y))
    # Each shot has a downstream jet determined by the contemporaneous head above invert.
    axis=Vector((1,-.33,0)).normalized()
    centre=Vector((2.55,.81,INVERT+.165))
    h=level-INVERT
    half_height=min(.151,.46*h)
    half_width=min(.153,math.sqrt(max(.0001,.165**2-(.165-half_height)**2))*.94)
    z=INVERT+half_height+.003
    speed=.68*math.sqrt(2*9.81*max(.016,h-half_height))
    end=centre+axis*.84
    tail=-1.2775
    flight=math.sqrt(2*(z-tail)/9.81)
    points=[Vector((end.x,end.y,z))-axis*.040]
    widths=[half_width]; heights=[half_height]
    for t in span(0,1,30):
        pos=Vector((end.x,end.y,z))+axis*(speed*flight*t)
        pos.z-=.5*9.81*(flight*t)**2
        contraction=math.sqrt(speed/math.hypot(speed,9.81*flight*t))
        points.append(pos)
        widths.append(half_width*contraction)
        heights.append(half_height*contraction)
    current("Free outfall into the receiving channel",points,widths,heights,p["stream"])
    impact=points[-1]
    def tail_z(x,y):
        r=math.hypot(x-impact.x,y-impact.y)
        return tail+.0085*math.exp(-r*4.2)*math.sin(62*r)+.0011*math.sin(15*y+x*.6)
    water_grid("Receiving channel tailwater",span(2.756,10.978,204),span(-.026,1.266,51),
               -1.368,tail_z,p["water"])
    foam_flecks("Outlet air bubbles",[(impact.x+.05,impact.y,.056,80)],tail_z,p["foam"],56)
    return set(bpy.context.scene.objects)-before


def hook_water(p):
    for h in range(-2,4):
        start=WET_LIP+Vector((h*4.45,0,0))
        # Hide the upstream closure inside the pipe and the downstream closure below the impact.
        ts=[-.82,-.52,-.23]+span(0,1.063,42)
        pts=[]
        widths,heights=[],[]
        for t in ts:
            free=max(t,0)
            pts.append(start+Vector((.0025*math.sin(7*t)*free,EXIT_VY*JET_FLIGHT*t,
                                     EXIT_VZ*JET_FLIGHT*t-.5*9.81*(JET_FLIGHT*free)**2)))
            contraction=math.sqrt(math.hypot(EXIT_VY,EXIT_VZ)/math.hypot(EXIT_VY,EXIT_VZ-9.81*JET_FLIGHT*free))
            widths.append(.037*contraction)
            heights.append(.026*contraction)
        runoff=current("Runoff from the open shoe",pts,widths,heights,p["stream"])
        if h:
            continue
        runoff.shape_key_add(name="Mean flow")
        for mode in range(2):
            key=runoff.shape_key_add(name=f"Travelling jet corrugation {mode+1}")
            key.slider_min=-1
            for i,vertex in enumerate(key.data):
                k,j=divmod(i,40)
                t=max(ts[k],0)
                phase=TAU*(2.35*t+3*j/40)+mode*math.pi/2
                flute=(.19*math.sin(phase)+.062*math.cos(6.3*TAU*t-j*.65+mode*math.pi/2))*t
                vertex.co+=(vertex.co-pts[k])*flute
                vertex.co.x+=.0021*t*t*math.cos(phase)
            key.driver_add("value").driver.expression=f"{'cos' if mode==0 else '-sin'}(frame*.47)"
    # Translucent ballistic spray circulates at the shoe while the isolated bead falls.
    for i in range(11):
        r=R.uniform(.0015,.0043)
        sp=C.sphere("Shoe impact spray",(0,0,0),(r,r,1.18*r),p["clear"])
        period=R.uniform(7,14)
        first=R.uniform(-16,0)
        direction=R.uniform(0,TAU)
        vxy,vz=R.uniform(.12,.33),R.uniform(.54,.84)
        while first<146:
            duration=2*vz/9.81
            for t in (0,.22,.48,.76,1):
                seconds=t*duration
                sp.location=(IMPACT_XY[0]+vxy*math.cos(direction)*seconds,
                             IMPACT_XY[1]+vxy*math.sin(direction)*seconds,
                             DRAIN_LEVEL+.002+vz*seconds-.5*9.81*seconds**2)
                factor=max(.0001,math.sin(math.pi*t)**.4)
                sp.scale=(r*factor,r*factor,r*(1.20-.24*t)*factor)
                sp.keyframe_insert(data_path="location",frame=first+t*duration*24)
                sp.keyframe_insert(data_path="scale",frame=first+t*duration*24)
            first+=period
    # A change in surface tension rounds the pendant as its neck separates from the lap.
    profile=[(0,.00005),(-.0012,.0015),(-.0035,.0020),(-.0060,.0033),(-.0086,.00415),
             (-.0104,.00432),(-.0123,.00387),(-.0137,.00280),(-.0145,.00155),(-.01485,.00005)]
    v,f=[],[]
    for k,(z,r) in enumerate(profile):
        for j in range(40):
            a=j*TAU/40
            v.append((r*math.cos(a),r*math.sin(a),z))
            if k:
                n=(k-1)*40+j
                after=(k-1)*40+(j+1)%40
                f.append((n,n+40,after+40,after))
    f.extend([tuple(range(40)),tuple(reversed(range(len(v)-40,len(v))))])
    drop=C.mesh("Last bead at the soldered lap",v,f,p["clear"])
    for poly in drop.data.polygons:
        poly.use_smooth=True
    drop.shape_key_add(name="Pendant")
    round_key=drop.shape_key_add(name="Surface tension after release")
    for i,vertex in enumerate(round_key.data):
        k,j=divmod(i,40)
        lat=math.pi*k/(len(profile)-1)
        rad=.00445*max(.008,math.sin(lat))
        vertex.co=(rad*math.cos(TAU*j/40),rad*math.sin(TAU*j/40),-.008+.00468*math.cos(lat))
    for frame,value in ((1,0),(RELEASE,0),(RELEASE+3,.83),(RELEASE+6,1)):
        round_key.value=value
        round_key.keyframe_insert(data_path="value",frame=frame)
    drop.location=(DROP_X,DROP_Y,DROP_TIP)
    z_driver=drop.driver_add("location",2).driver
    z_driver.expression=f"{DROP_TIP} - 4.905*(min(max(frame-{RELEASE},0),{DROP_FLIGHT*24+.6})/24)**2"
    for frame,sc in ((1,(.63,.67,.49)),(20,(.87,.88,.75)),(43,(1,1,.99)),
                     (RELEASE,(.95,.95,1.15)),(RELEASE+3,(1,1,1)),(IMPACT-.20,(1,1,1)),
                     (IMPACT+.55,(.0001,.0001,.0001))):
        drop.scale=sc
        drop.keyframe_insert(data_path="scale",frame=frame)
    # The same leaf first appears in the drain, responding to the second impact.
    blade=leaf(p,.151,-.24)
    for frame,x,y,rot,bob in ((1,-.083,6.45,-.24,0),(50,-.112,6.447,-.21,.001),
                               (69,-.133,6.446,-.18,0),(78,-.155,6.443,-.24,.003),
                               (96,-.185,6.433,-.31,.001),(144,-.237,6.415,-.35,0)):
        blade.location=(x,y,DRAIN_LEVEL+.0016+bob)
        blade.rotation_euler.z=rot
        blade.keyframe_insert(data_path="location",frame=frame)
        blade.keyframe_insert(data_path="rotation_euler",frame=frame)


def area(name,loc,at,power,tint,width,height):
    data=bpy.data.lights.new(name,'AREA')
    data.energy,data.color,data.shape,data.size,data.size_y=power,tint,'RECTANGLE',width,height
    ob=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location=loc
    ob.rotation_euler=(Vector(at)-ob.location).to_track_quat('-Z','Y').to_euler()


def lighting(scene):
    # The same sky illuminates the surfaces and is visible in their reflections.
    world=bpy.data.worlds.new("Passing rain • cloudy afternoon")
    scene.world=world
    world.use_nodes=True
    n,link=world.node_tree.nodes,world.node_tree.links.new
    bg=n["Background"]
    skyfile=next((root/"hdri"/"kloofendal_48d_partly_cloudy_2k.hdr" for root in C.ASSET_ROOTS
                  if (root/"hdri"/"kloofendal_48d_partly_cloudy_2k.hdr").is_file()),None)
    if skyfile:
        sky=n.new("ShaderNodeTexEnvironment")
        sky.image=bpy.data.images.load(str(skyfile),check_existing=True)
        mapping=n.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value.z=1.88
        link(n.new("ShaderNodeTexCoord").outputs["Generated"],mapping.inputs[0])
        link(mapping.outputs[0],sky.inputs[0])
        bg.inputs["Strength"].default_value=.52
    else:
        sky=n.new("ShaderNodeTexSky")
        sky.sun_elevation=math.radians(24)
        sky.sun_rotation=1.88
        bg.inputs["Strength"].default_value=.18
    link(sky.outputs[0],bg.inputs["Color"])
    area("Sunlit break across the street",(-6.8,-1.2,8.4),(0,4,1),2900,(1,.83,.66),4.9,3.5)
    area("Cool bounce into the cut",(3.3,-5.3,3.1),(0,1,-.5),480,(.70,.83,1),5.6,3.4)
    area("Rim along the wet eaves",(5.8,10.1,8.9),(0,6.6,1.5),1700,(1,.86,.68),6.1,3.7)
    area("Open sky reflected in the shoe",(-1.7,4.0,2.7),(0,6.8,1.3),155,(.82,.91,1),1.7,3.1)
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Base Contrast'
    scene.view_settings.exposure=.10


def materials():
    p={
        "concrete":damp_scan("concrete_floor_02",1.7,"777a71","ccc8b3",.32),
        "paving":damp_scan("grooved_concrete_driveway",2.2,"736e60","b5ac99",.24),
        "asphalt":damp_scan("aerial_asphalt_01",3.3,"303b3b","727971",.18),
        "soil":C.polyhaven("excavated_soil_wall",2.75),
        "aggregate":aggregate(),"metal":galvanised(),
        "fastener":surface("Satin stainless fixings","7c8581","d4d7cd",54,.29,.00022,.96),
        "solder":surface("Grey solder and inner zinc","616b69","9faba6",32,.46,.00045,.85),
        "oxide":surface("Oxidised iron","663b26","ac6c43",20,.68,.0013,.24),
        "cutsteel":surface("Sawn rebar steel","484942","898b81",71,.51,.00045,.85),
        "outlet":surface("Ductile iron with damp patina","3c4e4d","788579",14,.48,.0014,.72),
        "bore":surface("Wet inner iron","273632","505a4c",26,.39,.001,.59),
        "ink":surface("Deep petrol enamel","163234","365355",37,.38,.0005,.12),
        "plaster":surface("Limewash on cement render","ada88e","ded7bb",3.8,.76,.0018),
        "cream":surface("Weathered ivory enamel","bebbaa","ece6d2",8,.46,.0008),
        "wood":surface("Weathered teak grain","493826","95704d",5,.54,.001,stretch=(1.2,3,.07)),
        "pipe":surface("Chalked grey rainwater uPVC","939e99","ced2c4",9,.42,.00043,stretch=(2.2,2.2,.40)),
        "interior":surface("Porch interior wall","373c37","625e51",6,.85),
        "fabric":surface("Linen behind the glass","b0aa93","d5d1bc",95,.87,.00033),
        "joint":surface("Compressed rubber gasket","333930","656657",29,.75,.0014),
        "silt":surface("Mossy silt and grit","4e5140","85836b",34,.67,.0026),
        "stripe":surface("Road paint and grit","aaa58f","d3cdb4",49,.62,.0017),
        "rubber":surface("Weathered tyre and vinyl","242827","484d46",88,.69,.001),
        "foam":surface("Air entrained in runoff","9fae9e","dce1d1",70,.32,.0004),
        "leaf":thin_leaf("Waxy storm-tossed leaf","226a52","69ae78"),
        "vein":thin_leaf("Pale leaf veins","83995c","b0bc77"),
        "foliage":[thin_leaf("Lanceolate blade "+a,a,b) for a,b in
                   (("344730","77894c"),("455d39","95a364"),("4b5630","879951"))],
        "clear":water_material("Clear rain • lensing at the lap","f3faf8",1,.022),
        "stream":water_material("Moving rainwater • entrained air","d8e8df",.968,.052),
        "water":water_material("Shallow silted channel","d4e4d4",.94,.068,.62),
        "pond":water_material("Detained water with suspended silt","c1d9c8",.96,.077,.84,section=True),
    }
    glass=surface("Porch float glass, fine rain residue","a3b9b4","d2ded4",24,.11,.0001)
    shader=glass.node_tree.nodes["Principled BSDF"]
    shader.inputs["IOR"].default_value=1.51
    shader.inputs["Transmission Weight"].default_value=.96
    p["glass"]=glass
    p["grains"]=[surface("Split mineral "+a,a,b,95,.70,.0011) for a,b in
                 (("5f594a","968d78"),("77746a","aaa591"),("56564e","828274"),("807664","b5a58c"))]
    p["clay_grains"]=[surface("Ironstone nodule "+a,a,b,85,.75,.0012) for a,b in
                      (("514538","796955"),("51483c","756d60"),("675447","84705a"),("514b40","706b59"))]
    p["roadbase"]=surface("Compacted crushed limestone","44463e","756f5d",52,.75,.0035)
    stain_mat=M("Thin mineral deposit","48543c",rough=.76)
    n,link=stain_mat.node_tree.nodes,stain_mat.node_tree.links.new
    dust=node_noise(stain_mat,n.new("ShaderNodeNewGeometry").outputs["Position"],160,2)
    link(ramp(stain_mat,dust,[(.28,.015),(.72,.28)]),n["Principled BSDF"].inputs["Alpha"])
    p["stain"]=stain_mat
    return p


def empty(name):
    ob=bpy.data.objects.new(name,None)
    bpy.context.scene.collection.objects.link(ob)
    ob.empty_display_size=.04
    return ob


class Rig:
    def __init__(self,scene):
        data=bpy.data.cameras.new("Full-frame portrait prime")
        data.type,data.sensor_fit,data.sensor_height='PERSP','VERTICAL',36
        data.clip_start,data.clip_end=.025,140
        self.cam=bpy.data.objects.new("Section camera",data)
        scene.collection.objects.link(self.cam)
        scene.camera=self.cam
        self.aim,self.focus=empty("Optical axis"),empty("Subject focus")
        track=self.cam.constraints.new('TRACK_TO')
        track.target,track.track_axis,track.up_axis=self.aim,'TRACK_NEGATIVE_Z','UP_Y'
        data.dof.use_dof=True
        data.dof.focus_object=self.focus
        data.dof.aperture_blades=9

    def pose(self,look,height,azimuth,elevation,focus,lens,aperture,frame=None):
        self.cam.data.lens=lens
        self.cam.data.dof.aperture_fstop=aperture
        a,e=math.radians(azimuth),math.radians(elevation)
        direction=Vector((math.sin(a)*math.cos(e),-math.cos(a)*math.cos(e),math.sin(e)))
        self.aim.location=look
        self.cam.location=Vector(look)+direction*(height*lens/36)
        self.focus.location=focus
        if frame is not None:
            for obj in (self.cam,self.aim,self.focus):
                obj.keyframe_insert(data_path="location",frame=frame)


def ease_camera(obj):
    anim=obj.animation_data
    for layer in anim.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation='BEZIER'
                        key.handle_left_type=key.handle_right_type='AUTO_CLAMPED'


BEAD=(DROP_X,DROP_Y,DROP_TIP-.009)
SHOTS=[
    ((-.182,6.764,2.444),.32,21,-9,BEAD,47,7.1),
    ((.05,1.26,-.21),12.62,-16,13,(-.20,1.85,-.41),42,6.3),
    ((-.57,1.80,-.49),5.9,-18,18,(.31,2.15,-.51),45,5.0),
    ((2.68,.75,-1.01),3.82,12.5,18.5,(2.94,.64,-1.01),48,5.6),
]
# The camera backs away before release, catches the leader, then settles on the wake.
HOOK_PATH=[
    (1,(-.183,6.764,2.445),.32,21,-9,BEAD),
    (23,(-.172,6.769,2.437),.34,24,-8,BEAD),
    (43,(-.076,6.80,2.31),.88,29,-3,BEAD),
    (53,(-.025,6.78,1.92),1.74,28,3,(-.10,6.78,2.16)),
    (66,(.010,6.69,.65),1.84,25,12,(-.03,6.75,.72)),
    (75,(.020,6.61,.32),1.56,24,17,(.01,6.64,.22)),
    (94,(.029,6.56,.19),1.14,23,21,(PIPE_X,6.60,.14)),
    (120,(-.010,6.50,.085),.84,20,25,(PIPE_X,6.48,-.042)),
    (144,(-.044,6.48,.046),.81,17,27,(-.044,6.445,DRAIN_LEVEL)),
]


def check_hook_framing(scene,rig):
    # Follow the actual capillary contact point all the way to the water, including release.
    for frame in range(1,math.ceil(IMPACT)+1):
        scene.frame_set(frame)
        fall=min(DROP_FLIGHT,max(0,(frame-RELEASE)/24))
        bead=Vector((DROP_X,DROP_Y,max(DRAIN_LEVEL,DROP_TIP-.008-4.905*fall**2)))
        x,y,depth=world_to_camera_view(scene,rig.cam,bead)
        if depth<=0 or not (.07<x<.93 and .14<y<.86):
            raise ValueError(f"Frame {frame}: drop outside safe portrait area ({x:.3f}, {y:.3f})")


def render(scene,path):
    scene.render.filepath=str(path)
    start=time.monotonic()
    result=bpy.ops.render.render(write_still=True)
    if "FINISHED" not in result or not path.is_file():
        raise RuntimeError(f"Missing render for {path.name}")
    return time.monotonic()-start


def main():
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    preview="--preview" in args
    proof="--proof" in args
    target=HERE/"out_v3"
    if preview or proof:
        target=target/"preview"
    target.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=C.render_settings("CPU",width=360 if preview or proof else 1080,samples=18 if preview or proof else 192,frames=144)
    device(scene)
    scene.render.fps=24
    scene.cycles.adaptive_threshold=.13 if preview or proof else .012
    scene.cycles.max_bounces=7 if preview or proof else 10
    scene.cycles.transmission_bounces=6 if preview or proof else 8
    scene.cycles.glossy_bounces=4
    scene.cycles.diffuse_bounces=3
    scene.cycles.use_adaptive_sampling=True
    scene.cycles.use_denoising=True
    scene.cycles.denoiser='OPENIMAGEDENOISE'
    scene.cycles.denoising_input_passes='RGB_ALBEDO_NORMAL'
    scene.render.use_persistent_data=True
    scene.unit_settings.system='METRIC'
    scene.render.threads_mode='FIXED' if preview or proof else 'AUTO'
    if preview or proof:
        scene.render.threads=6
    p=materials()
    pond(p)
    water_grid("Scalloped bed sediment",span(-2.634,2.359,168),span(.012,2.435,83),
               -1.54,sediment_z,p["silt"])
    street(p)
    hook_water(p)
    states=[water_state(p,z,name,pos) for z,name,pos in (
            (-.973,"inflow",(-1.44,1.78)),(-.56,"high",(-.18,1.65)),(-.989,"low",(2.02,.80)))]
    lighting(scene)
    rig=Rig(scene)
    def set_state(index):
        for i,group in enumerate(states):
            for obj in group:
                obj.hide_render=i!=index
    if "--movie-only" not in args:
        for stem,shot,state in zip(STILLS,SHOTS,(0,0,1,2)):
            set_state(state)
            rig.pose(*shot)
            scene.frame_set(42)
            seconds=render(scene,target/(stem+".png"))
            print(f"STILL {stem} {seconds:.2f}s",flush=True)
    if "--stills-only" in args:
        return
    set_state(0)
    for frame,look,height,az,el,focus in HOOK_PATH:
        rig.pose(look,height,az,el,focus,47,7.1,frame)
    for obj in (rig.cam,rig.aim,rig.focus):
        ease_camera(obj)
    check_hook_framing(scene,rig)
    scene.render.use_motion_blur=True
    scene.render.motion_blur_shutter=.45
    if proof:
        for f in (1,51,68,96,144):
            scene.frame_set(f)
            render(scene,target/f"motion{f:03d}.png")
        return
    scene.render.resolution_x,scene.render.resolution_y=(216,384) if preview else (1080,1920)
    scene.cycles.samples=6 if preview else 64
    scene.cycles.adaptive_threshold=.19 if preview else .028
    print(f"HOOK {scene.render.resolution_x}x{scene.render.resolution_y} • {scene.cycles.samples} samples • shutter .45",flush=True)
    start=time.monotonic()
    with tempfile.TemporaryDirectory(dir=target,prefix=".hook-") as tmpname:
        tmp=Path(tmpname)
        for f in range(1,145):
            scene.frame_set(f)
            render(scene,tmp/f"{f:04d}.png")
            if f%24==0:
                print(f"HOOK frame {f}/144",flush=True)
        subprocess.run([shutil.which("ffmpeg") or "ffmpeg","-hide_banner","-loglevel","error","-y",
                        "-framerate","24","-start_number","1","-i",str(tmp/"%04d.png"),"-frames:v","144",
                        "-vf","scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                        "-c:v","libx264","-preset","medium","-crf","16","-color_range","tv",
                        "-color_primaries","bt709","-color_trc","iec61966-2-1","-colorspace","bt709",
                        "-movflags","+faststart",str(tmp/"hook_6s.mp4")],check=True)
        (tmp/"hook_6s.mp4").replace(target/"hook_6s.mp4")
    print(f"HOOK encoded {time.monotonic()-start:.2f}s",flush=True)


if __name__=="__main__":
    main()

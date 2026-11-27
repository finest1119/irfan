"""Build and render the Everyday Decoded footing section.

Blender -b --factory-startup -P build_cutaway.py -- --out out
FFMPEG may point to an ffmpeg binary with drawtext and libx264.
"""
import argparse
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "assets/polyhaven"
rng = random.Random(8641)
F, B = -2.15, 2.65
scene = bpy.context.scene


def color(value):
    rgb = bytes.fromhex(value)
    return tuple(((v / 255 + .055) / 1.055) ** 2.4 if v > 10 else v / 3294.6 for v in rgb) + (1,)


def material(name, a, b=None, scale=5, grain=.025, rough=.72, metal=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color(a)
    m.use_nodes = True
    n, link = m.node_tree.nodes, m.node_tree.links.new
    p = n.get("Principled BSDF")
    p.inputs["Base Color"].default_value = color(a)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if b:
        coord = n.new("ShaderNodeTexCoord").outputs["Object"]
        def noise(freq):
            t = n.new("ShaderNodeTexNoise")
            t.inputs["Scale"].default_value = freq
            t.inputs["Detail"].default_value = 2.5
            link(coord, t.inputs["Vector"])
            return t.outputs["Fac"]
        ramp = n.new("ShaderNodeValToRGB")
        for element, pos, val in zip(ramp.color_ramp.elements, (.23, .76), (a, b)):
            element.position = pos
            element.color = color(val)
        link(noise(scale), ramp.inputs["Fac"])
        link(ramp.outputs[0], p.inputs["Base Color"])
        bump = n.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .24
        bump.inputs["Distance"].default_value = grain
        link(noise(53), bump.inputs["Height"])
        link(bump.outputs[0], p.inputs["Normal"])
    return m


def mapped(name, asset, size, fallback):
    folder = ASSETS / "textures" / asset
    if not folder.is_dir():
        return fallback
    m = material(name, "888888")
    n, link = m.node_tree.nodes, m.node_tree.links.new
    p = n.get("Principled BSDF")
    coord = n.new("ShaderNodeVectorMath")
    coord.operation = 'SCALE'
    coord.inputs["Scale"].default_value = 1 / size
    link(n.new("ShaderNodeTexCoord").outputs["Object"], coord.inputs[0])
    for suffix, inp in (("diff", "Base Color"), ("rough", "Roughness")):
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(folder / f"{asset}_{suffix}_1k.jpg"), check_existing=True)
        if suffix == "rough":
            t.image.colorspace_settings.name = "Non-Color"
        t.projection = 'BOX'
        t.projection_blend = .18
        link(coord.outputs[0], t.inputs[0])
        link(t.outputs[0], p.inputs[inp])
    return m


def mesh(name, verts, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def section(name, points, y0, y1, mat):
    # CCW in x/z faces the viewer. Triangulate concave caps explicitly.
    if sum(x*z2-x2*z for (x,z),(x2,z2) in zip(points, points[1:]+points[:1])) < 0:
        points = points[::-1]
    count = len(points)
    triangles = tessellate_polygon([[Vector((x, z, 0)) for x, z in points]])
    faces = [tuple(t) for t in triangles]
    faces += [tuple(i+count for i in reversed(t)) for t in triangles]
    faces += [(i, i+count, (i+1)%count+count, (i+1)%count) for i in range(count)]
    return mesh(name, [(x,y,z) for y in (y0,y1) for x,z in points], faces, mat)


def box(name, center, size, mat, bevel=0):
    w,d,h = (v/2 for v in size)
    obj = section(name, [(-w,-h),(w,-h),(w,h),(-w,h)], -d,d,mat)
    obj.location = center
    if bevel:
        mod = obj.modifiers.new("Soft arris", 'BEVEL')
        mod.width, mod.segments = bevel, 2
        obj.modifiers.new("Face normals", 'WEIGHTED_NORMAL')
    return obj


def bounds(name, x0,x1,y0,y1,z0,z1,mat):
    return box(name, ((x0+x1)/2,(y0+y1)/2,(z0+z1)/2), (x1-x0,y1-y0,z1-z0),mat)


def strand(name, points, radius, mat):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions, data.resolution_u = '3D', 4
    data.bevel_depth, data.bevel_resolution = radius, 2
    spline = data.splines.new('POLY')
    spline.points.add(len(points)-1)
    for p, co in zip(spline.points,points):
        p.co = (*co,1)
    obj = bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def beam(name, a,b,width,depth,mat):
    v = Vector(b)-Vector(a)
    obj = box(name, (Vector(a)+Vector(b))/2, (width,depth,v.length), mat)
    obj.rotation_euler = v.to_track_quat('Z','Y').to_euler()
    return obj


def sphere(name, pos, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=pos)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def daylight():
    world = scene.world
    world.use_nodes = True
    n, link = world.node_tree.nodes, world.node_tree.links.new
    bg = n.get("Background")
    hdr = next((ASSETS / "hdri").glob("*.hdr"),None)
    if hdr:
        t = n.new("ShaderNodeTexEnvironment")
        t.image = bpy.data.images.load(str(hdr))
        mapping = n.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value.z = 1.15
        link(n.new("ShaderNodeTexCoord").outputs["Generated"],mapping.inputs[0])
        link(mapping.outputs[0],t.inputs[0])
    else:
        t = n.new("ShaderNodeTexSky")
    link(t.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = .72
    light = bpy.data.lights.new("Window-side daylight",'AREA')
    light.energy, light.shape, light.size = 1550, 'DISK', 8
    obj = bpy.data.objects.new(light.name,light)
    scene.collection.objects.link(obj)
    obj.location = (-4,-7,9)
    obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()


def build():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    daylight()
    loam = material("Loam • humus", "392a1f","73583a",7)
    clay = material("Weathered orange clay", "835032","bd8054",4)
    silt = material("Ochre silty lens","9c724e","c29c72",7)
    till = material("Dense glacial till","756349","ab9676",9)
    base = material("Consolidated subsoil","55483d","907d67",8)
    turf = mapped("Poly Haven • turf","aerial_grass_rock",3,material("Meadow","58663a","98a064"))
    cement = mapped("Poly Haven • concrete","concrete_floor_02",2,material("Cement","9e988a","c7c3b7"))
    sand = material("Aggregate fines","62584a","a09382",28)
    oak = material("Oiled oak","96734f","c19b6d",4,.009)
    ply = material("Sawn structural pine","c49257","e0b983",8,.015)
    sage = material("Painted clapboard","617977",rough=.65)
    plaster = material("Limewashed walls","ded8c7","ece6d5",2,.006)
    white = material("Warm white joinery","eee6d3")
    slate = material("Standing seam zinc","41494c","60696b",8,.008,.43,.45)
    dark = material("Graphite drain HDPE","23292a",rough=.37)
    brass = material("Aged brass","99763f",rough=.32,metal=.65)
    zinc = material("Galvanised steel","838c87",rough=.36,metal=.6)
    glass = material("Daylit panes","bfd4d3",rough=.19,metal=.25)
    # Stratigraphy, all extrusions watertight. Shared undulating contacts.
    def bedrock(x):
        return -2.77+.055*math.sin(2*x)+.035*math.cos(4*x)
    def strata(x0,x1, levels, mats):
        xs = [x0+(x1-x0)*i/32 for i in range(33)]
        for lower,upper,mat in zip(levels,levels[1:],mats):
            section(mat.name,[(x,lower(x)) for x in xs]+[(x,upper(x)) for x in reversed(xs)],F,B,mat)
    flat = lambda h: lambda x: h
    levels = [flat(-3.22),bedrock,flat(-2.46)]
    strata(-4.35,4.0,levels,[base,till])
    def contacts(x):
        return -.34+.056*math.sin(3.1*x)+.039*math.sin(8*x)
    def clay_base(x):
        return -1.23+.11*math.sin(x*2.1)-.06*x
    for lo,hi in ((-4.35,-3.45),(2.25,4.0)):
        if hi < 0:
            strata(lo,-3.58,[flat(-2.46),flat(-2.15)],[till])
        strata(lo,hi,[flat(-2.15 if hi < 0 else -2.46),clay_base,lambda x:clay_base(x)+.11,contacts,flat(-.048),flat(.005)],
               [till,silt,clay,loam,turf])
    # Exterior edge of drain trench abuts native soil. Gravel sits against footing.
    strata(1.17,2.25,[flat(-2.46),flat(-2.32)],[till])
    section("Washed stone bed",[(1.17,-2.32),(2.25,-2.32),(2.25,-1.87),(1.04,-1.87),(1.04,-2.15),(1.17,-2.15)],F,B,sand)
    section("Gravel backfill",[(1.04,-1.87),(2.25,-1.87),(2.25,-1.35),(1.04,-1.35)],F+.95,B,sand)
    section("Soil over drainage bed",[(1.04,-1.35),(2.25,-1.35),(2.25,contacts(2.25)),(1.04,contacts(1.04))],F,B,clay)
    # Use wavy contacts across the trench cover as well.
    strata(1.04,2.25,[lambda x:contacts(1.04)+(contacts(2.25)-contacts(1.04))*(x-1.04)/1.21,
                     flat(-.048),flat(.005)],[loam,turf])
    for x in (-3.25,.84):
        bounds("Spread footing",x-.33,x+.33,F,B,-2.46,-2.15,cement)
        bounds("Cast foundation wall",x-.2,x+.2,F,B,-2.15,.34,cement)
    bounds("Underslab stone",-2.92,.51,F,B,-2.46,-2.17,sand)
    bounds("Basement slab",-2.92,.51,F,B,-2.17,-1.99,cement)
    for xa,xb in ((-3.05,-2.92),(.51,.64)):
        bounds("Slab bearing",xa,xb,F,B,-2.15,-1.99,cement)
    bounds("Basement back wall",-3.05,.64,B-.18,B,-2.15,.34,cement)
    for height in (-1.38,-.59,.18):
        for x in (-2.8,-1.77,-.74,.29):
            box("Form tie", (x,B-.19,height),(.045,.015,.045),dark,.012)
    # Copper supply lines, clips and meter cabinet give the basement scale.
    copper=material("Weathered copper","946042",rough=.45,metal=.58)
    for z in (-.07,.075):
        strand("Copper supply",[(-3.02,B-.27,z),(.42,B-.27,z),(.50,B-.35,z),(.50,-1.65,z)],.032,copper)
        for x in (-2.7,-1.6,-.5):
            box("Pipe saddle",(x,B-.27,z),(.041,.084,.083),zinc,.008)
    box("Breaker cabinet",(-2.31,B-.24,-.86),(.54,.12,.69),zinc,.025)
    box("Recessed breaker door",(-2.31,B-.315,-.86),(.44,.03,.56),sage,.012)
    strand("Electrical conduit",[(-2.31,B-.25,-.51),(-2.31,B-.25,.32)],.020,zinc)
    for x in (-3.25,.84):
        bounds("Sill gasket",x-.16,x+.16,F,B,.34,.36,dark)
        bounds("Sill plate",x-.16,x+.16,F,B,.36,.46,ply)
    for i in range(10):
        x=-3.25+i*.454
        bounds("Floor joist",x-.045,x+.045,F,B,.46,.70,ply)
    bounds("Subfloor",-3.43,1.03,F,B,.70,.76,ply)
    for i in range(21):
        x = -3.43+i*4.46/21
        bounds("Oak floorboard",x,x+4.46/21-.005,F,B,.76,.80,oak)
    # Cut upper storey: open rear window plus a side window in lapped siding.
    for x in (-3.34,.91):
        for ya,yb,za,zb in ((F,B,.8,1.60),(F,B,2.87,3.47),(F,-.30,1.60,2.87),(1.30,B,1.60,2.87)):
            bounds("Insulated sidewall",x-.10,x+.10,ya,yb,za,zb,plaster)
        for i in range(20):
            z=.80+i*.134
            spans=[(F,B)] if z+.134 < 1.60 or z>=2.87 else [(F,-.30),(1.30,B)]
            for ya,yb in spans:
                board=box("Lapped painted siding",(x+(.13 if x>0 else -.13),(ya+yb)/2,z+.067),(.05,yb-ya,.145),sage)
                board.rotation_euler.y = -.075 if x>0 else .075
        bounds("Cut stud",x-.083,x+.083,F-.012,F+.045,.80,3.47,ply)
        for yy in (-.32,.50,1.32):
            box("Sash stile",(x,yy,2.235),(.25,.07,1.39),white)
        for zz in (1.58,2.23,2.89):
            box("Sash rail",(x,.50,zz),(.26,1.73,.07),white)
        box("Side window glass",(x,.50,2.23),(.012,1.60,1.27),glass)
    for xa,xb,za,zb in ((-3.43,1.03,.80,1.74),(-3.43,1.03,2.96,3.47),(-3.43,-2.08,1.74,2.96),(-.38,1.03,1.74,2.96)):
        bounds("Back wall",xa,xb,B-.14,B,za,zb,plaster)
    for x in (-2.10,-1.23,-.36):
        box("Rear sash",(x,B-.17,2.35),(.075,.12,1.34),white)
    for z in (1.73,2.35,2.97):
        box("Rear sash rail",(-1.23,B-.17,z),(1.84,.135,.075),white)
    box("Rear panes",(-1.23,B-.08,2.35),(1.72,.02,1.22),glass)
    # Kitchen joinery, inset doors, pulls, brass gooseneck and crockery.
    cabinet=material("Enamel kitchen fronts","73837b")
    stone=material("Soapstone","4d5551","798079",7,.012)
    bounds("Kitchen base",-3.10,.41,1.75,2.46,.83,1.62,cabinet)
    box("Countertop",(-1.345,2.09,1.65),(3.62,.78,.085),stone,.018)
    for i in range(5):
        x=-2.73+i*.69
        box("Shaker door",(x,1.735,1.24),(.66,.047,.66),cabinet,.012)
        box("Inset panel",(x,1.704,1.24),(.53,.018,.50),sage,.009)
        box("Drawer pull",(x,1.68,1.47),(.16,.03,.024),brass,.006)
    box("Sink bowl",(-1.24,2.07,1.696),(.60,.42,.012),zinc,.005)
    strand("Faucet",[(-1.24,2.33,1.70),(-1.24,2.33,1.95),(-1.24,2.26,2.01),(-1.24,2.14,2.01),(-1.24,2.10,1.95)],.022,brass)
    for x in (-2.82,-2.58):
        sphere("Stoneware crock",(x,2.10,1.82),(.085,.085,.155),white)
    box("Oak breakfast table",(-1.62,-.43,1.55),(1.49,.81,.085),oak,.032)
    for x in (-2.22,-1.02):
        for y in (-.71,-.16):
            box("Tapered table leg",(x,y,1.16),(.072,.072,.74),oak,.01)
    for x in (-2.66,-.57):
        box("Seat",(x,-.42,1.25),(.39,.40,.07),oak,.026)
        for xx in (-.145,.145):
            for yy in (-.145,.145):
                box("Chair leg",(x+xx,-.42+yy,1.02),(.044,.044,.45),oak)
        dx=.17 if x> -1 else -.17
        for yy in (-.15,.15):
            box("Chair spindle",(x+dx,-.42+yy,1.47),(.043,.043,.48),oak)
        box("Chair back",(x+dx,-.42,1.67),(.055,.37,.16),oak,.02)
    sphere("Ceramic fruit bowl",(-1.59,-.42,1.62),(.21,.17,.07),white)
    fruit=material("Russet fruit","ab5128")
    for i in range(4):
        sphere("Pear",(-1.60+.087*math.cos(i*2),-.42+.065*math.sin(i*2),1.69),(.061,.056,.073),fruit)
    bounds("Ceiling",-3.47,1.07,F,B,3.46,3.54,plaster)
    strand("Pendant flex",[(-1.6,-.42,3.46),(-1.6,-.42,2.66)],.012,dark)
    sphere("Spun shade",(-1.6,-.42,2.66),(.27,.27,.115),brass)
    sphere("Opal diffuser",(-1.6,-.42,2.60),(.20,.20,.065),white)
    # Front roof section reveals sawn rafter and open attic.
    ridge=(-1.20,5.39)
    tips=[(-3.73,3.49),(1.33,3.49)]
    section("Rear gable",[(-3.45,3.48),(1.05,3.48),ridge],B-.16,B,sage)
    for tip in tips:
        x,z=tip
        outline=[tip,ridge,(ridge[0],ridge[1]+.115),(x,z+.115)]
        section("Roof sheathing",outline,F-.11,B+.27,ply)
        section("Zinc roof",[(a,b+.115) for a,b in [tip,ridge]]+[(ridge[0],ridge[1]+.16),(x,z+.16)],F-.12,B+.28,slate)
        for i in range(14):
            y=F-.10+i*.39
            beam("Raised roof seam",(x,y,z+.168),(ridge[0],y,ridge[1]+.168),.036,.036,slate)
        for y in (F+.025,-.72,.74,2.25):
            beam("Exposed rafter",(x,y,z-.075),(ridge[0],y,ridge[1]-.075),.15,.10,ply)
    for y in (F+.025,-.72,.74,2.25):
        box("Tie beam",(-1.20,y,3.63),(4.50,.11,.16),ply)
        beam("King post",(-1.2,y,3.66),(-1.2,y,5.23),.105,.105,ply)
        for x in (-2.44,.04):
            beam("Truss brace",(-1.2,y,3.71),(x,y,4.31),.085,.09,ply)
    # Single mesh with real drainage slots and an open bore. Quad rims
    # bridge inner and outer skins around each omitted group of cells.
    pipe_x,pipe_z=1.56,-1.80
    y0,y1=F-.11,B
    verts,faces=[],[]
    rings,segs=120,48
    for skin in (0,1):
        for j in range(rings+1):
            y=y0+(y1-y0)*j/rings
            r=.201+.018*(.5+.5*math.cos(j*math.pi/2)) if skin==0 else .178
            for i in range(segs):
                angle=2*math.pi*i/segs
                verts.append((pipe_x+r*math.cos(angle),y,pipe_z+r*math.sin(angle)))
    def idx(k,j,i):
        return (k*(rings+1)+j)*segs+i%segs
    def slot(j,i):
        return j%8 in (3,4) and i%12 in (4,5,6)
    for j in range(rings):
        for i in range(segs):
            if slot(j,i):
                continue
            coords=[(j,i),(j+1,i),(j+1,i+1),(j,i+1)]
            outer=[idx(0,*c) for c in coords]
            inner=[idx(1,*c) for c in coords]
            faces.extend([outer,inner[::-1]])
            for k,missing in enumerate((slot(j,i-1),j==rings-1 or slot(j+1,i),slot(j,i+1),j==0 or slot(j-1,i))):
                l=(k+1)%4
                if missing:
                    faces.append((outer[l],outer[k],inner[k],inner[l]))
    pipe=mesh("Slotted corrugated perimeter drain",verts,faces,dark)
    for poly in pipe.data.polygons:
        poly.use_smooth=True
    gravel=[material("Washed aggregate "+str(i),v) for i,v in enumerate(("857e70","b3ab97","6c6b64","a8a196","c3bbaa","807d75"))]
    # Individually chipped stones, batched by material. The front-most stones
    # have a planar sliced face at the geological section plane.
    piles=[([],[]) for _ in gravel]
    for i in range(3000):
        x=rng.uniform(1.055,2.24)
        y=rng.uniform(F-.03,B) if i%3==0 else rng.uniform(F-.03,F+.10)
        z=rng.uniform(-2.28,-1.38)
        if x<1.18 and z< -2.15:
            continue
        if (x-pipe_x)**2+(z-pipe_z)**2 < .248**2:
            continue
        if y<F+.75 and z>pipe_z-.065 and abs(x-pipe_x)<.34:
            continue
        vs,fs=rng.choice(piles)
        start=len(vs)
        radius=rng.uniform(.032,.087)
        stretch=rng.uniform(.65,1.12)
        phase=rng.random()*6.28
        for layer,h in enumerate((-.72,0,.68)):
            for k in range(6):
                theta=k*math.pi/3+phase+.22*layer
                r=radius*rng.uniform(.74,1.15)*(1 if layer==1 else .67)
                vs.append((x+r*math.cos(theta),max(F-.043,y+r*math.sin(theta)),z+radius*h*stretch))
        fs.extend([tuple(start+k for k in reversed(range(6))),tuple(start+12+k for k in range(6))])
        for q in (0,6):
            fs.extend([(start+q+k,start+q+(k+1)%6,start+q+6+(k+1)%6,start+q+6+k) for k in range(6)])
    for (v,f),m in zip(piles,gravel):
        mesh("Exposed gravel",v,f,m)
    # Narrow wet track over the face; specular pulses travel downslope.
    water=material("Seepage • wet mineral film","48787c",rough=.16,metal=.36)
    glint=material("Reflected sky in water","c2e7e6",rough=.12,metal=.24)
    p=glint.node_tree.nodes.get("Principled BSDF")
    p.inputs["Emission Color"].default_value=color("97d6db")
    p.inputs["Emission Strength"].default_value=.23
    path=[(3.83,-.28),(3.62,-.41),(3.54,-.54),(3.32,-.61),(3.18,-.84),(2.91,-.95),(2.72,-1.08),(2.52,-1.12),(2.39,-1.29),(2.20,-1.37),(2.01,-1.47),(1.84,-1.53),(1.69,-1.64)]
    front=F-.054
    strand("Seepage track",[(x,front,z) for x,z in path],.014,water)
    for k in range(7):
        drop=sphere("Moving water highlight",(0,0,0),(.039,.019,.016),glint)
        for cycle in range(-1,5):
            for i,(x,z) in enumerate(path):
                frame=1+cycle*58+i*57.8/(len(path)-1)-k*58/7
                drop.location=(x,front-.017,z)
                drop.keyframe_insert(data_path="location",frame=frame)
                # Fade into the soil at either end before the next cycle.
                fac=.01 if i in (0,len(path)-1) else 1.0
                drop.scale=(.032*fac,.013*fac,.010*fac)
                drop.keyframe_insert(data_path="scale",frame=frame)
    # A few embedded mineral grains and fine rootlets along the exposed lawn.
    fleck_mats=[material("Mineral grains "+str(i),v) for i,v in enumerate(("796444","856a4e","b19775","6b5843"))]
    for mat in fleck_mats:
        verts,faces=[],[]
        for i in range(780):
            x=rng.uniform(1.08,3.99)
            z=rng.uniform(-3.16,-.06)
            if x<2.26 and -2.5<z<-1.31:
                continue
            a,b=rng.uniform(.003,.024),rng.uniform(.002,.011)
            j=len(verts)
            verts.extend([(x-a,F-.002,z),(x-a*.25,F-.002,z+b),(x+a,F-.002,z+b*.28),(x+a*.34,F-.002,z-b)])
            faces.append((j,j+1,j+2,j+3))
        mesh("Embedded grains",verts,faces,mat)
    root=material("Fine dry roots","9b805a")
    for i in range(42):
        x=rng.uniform(1.09,3.98)
        dx=rng.uniform(-.09,.09)
        depth=rng.uniform(.05,.23)
        pts=[(x,F-.002,-.01),(x+dx*.2,F-.004,-depth*.3),(x+dx*.7,F-.004,-depth*.65),(x+dx,F-.003,-depth)]
        strand("Rootlet",pts,.0028,root)
    # Suburban details on the uncut lawn.
    for x in (2.09,2.42,2.75,3.08,3.41,3.74):
        box("Fence picket",(x,2.39,.45),(.23,.085,.87),white,.018)
    for z in (.32,.69):
        box("Fence rail",(2.92,2.45,z),(1.94,.08,.09),white)
    # Blades and seed heads keep the sod edge irregular at close range.
    blades,faces=[],[]
    grass=material("Grass blades","708044","9a9b58",12)
    for i in range(4600):
        x,y=rng.uniform(1.075,3.99),rng.uniform(F,B)
        h=rng.uniform(.028,.108)
        w=rng.uniform(.004,.012)
        j=len(blades)
        blades.extend([(x-w,y,.005),(x+w,y,.005),(x+rng.uniform(-.023,.023),y+.014,h)])
        faces.append((j,j+1,j+2))
    mesh("Fine lawn",blades,faces,grass)
    # Roof edge, rain leader and shoe on the lawn side.
    strand("Rain gutter",[(1.36,F-.11,3.50),(1.36,B+.24,3.50)],.064,zinc)
    strand("Downspout",[(1.34,1.97,3.50),(1.34,1.97,3.38),(1.12,1.97,3.14),(1.12,1.97,.19),(1.28,1.97,.10)],.048,zinc)
    # A clipped rosemary bush. Tiny leaf clusters break up the right-hand lawn.
    shrub=material("Garden foliage","415333","778256",9)
    v,fc=[],[]
    for i in range(3400):
        a=rng.random()*math.tau
        u=rng.uniform(-.65,1)
        r=rng.random()**.32
        x=2.69+.65*r*(1-u*u)**.5*math.cos(a)
        y=1.84+.65*r*(1-u*u)**.5*math.sin(a)
        z=.27+.52*r*u
        j=len(v)
        az=rng.random()*math.tau
        dx,dy=.046*math.cos(az),.046*math.sin(az)
        dz=rng.uniform(.005,.038)
        v.extend([(x-dx,y-dy,z-dz),(x+dy*.44,y-dx*.44,z+.006),(x+dx,y+dy,z+dz),(x-dy*.44,y+dx*.44,z-.005)])
        fc.append((j,j+1,j+2,j+3))
    mesh("Rosemary planting",v,fc,shrub)
    # A seamless sweep curves up behind the model, retaining the HDR sky as illumination.
    stage=material("Matte mineral backdrop","a6afa8",rough=.93)
    # Fade the high portion into the real HDR sky. Keep the floor opaque.
    n,link=stage.node_tree.nodes,stage.node_tree.links.new
    height=n.new("ShaderNodeSeparateXYZ")
    link(n.new("ShaderNodeNewGeometry").outputs["Position"],height.inputs[0])
    blend=n.new("ShaderNodeMapRange")
    blend.interpolation_type="SMOOTHERSTEP"
    blend.inputs["From Min"].default_value=-1.7
    blend.inputs["From Max"].default_value=6.5
    link(height.outputs["Z"],blend.inputs["Value"])
    mix=n.new("ShaderNodeMixShader")
    link(blend.outputs[0],mix.inputs[0])
    link(n.get("Principled BSDF").outputs[0],mix.inputs[1])
    link(n.new("ShaderNodeBsdfTransparent").outputs[0],mix.inputs[2])
    link(mix.outputs[0],n.get("Material Output").inputs["Surface"])
    path=[(-80,-3.225),(8,-3.225)]
    path += [(8+13*math.sin(i*math.pi/48),-3.225+13*(1-math.cos(i*math.pi/48))) for i in range(1,25)]
    path += [(21,34)]
    verts=[(x,y,z) for y,z in path for x in (-100,100)]
    sweep=mesh("Daylight sweep",verts,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(path)-1)],stage)
    for poly in sweep.data.polygons:
        poly.use_smooth=True


def camera_at(frame):
    t=(frame-1)/179
    ease=t*t*(3-2*t)
    target=Vector((-.18+.52*ease,-.64-.68*ease,.88-.69*ease))
    angle=math.radians(12+6*ease)
    dist=17.9-2.45*ease
    pos=target+Vector((dist*math.sin(angle),-dist*math.cos(angle),dist*.245))
    cam=scene.camera
    cam.location=pos
    cam.rotation_euler=(target-pos).to_track_quat('-Z','Y').to_euler()


def setup(samples):
    cam=bpy.data.cameras.new("Portrait section lens")
    obj=bpy.data.objects.new(cam.name,cam)
    scene.collection.objects.link(obj)
    scene.camera=obj
    cam.lens,cam.sensor_width=43,36
    scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='METAL'
        prefs.refresh_devices()
    except TypeError:
        pass
    gpu=[d for d in prefs.devices if d.type=='METAL']
    for d in prefs.devices:
        d.use=d in gpu
    scene.cycles.device='GPU' if gpu else 'CPU'
    scene.cycles.samples=samples if samples is not None else (16 if gpu else 5)
    scene.cycles.use_adaptive_sampling=True
    scene.cycles.adaptive_threshold=.08
    scene.cycles.use_denoising=True
    scene.cycles.denoiser='OPENIMAGEDENOISE'
    scene.cycles.max_bounces=6
    scene.render.use_motion_blur=False
    scene.render.use_persistent_data=True
    scene.render.resolution_x,scene.render.resolution_y=1080,1920
    scene.render.resolution_percentage=100
    scene.render.fps=30
    scene.frame_start,scene.frame_end=1,180
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.compression=12
    scene.view_settings.view_transform='AgX'
    return ', '.join(d.name+' / Metal' for d in gpu) if gpu else 'CPU / Metal device unavailable'


def find_encoder():
    candidates = [os.environ.get("FFMPEG"), shutil.which("ffmpeg"),
                  Path.home() / "Downloads/affiliate-video-studio/node_modules/ffmpeg-static/ffmpeg"]
    for ff in candidates:
        if not ff or not Path(ff).is_file():
            continue
        filters = subprocess.run([ff,"-hide_banner","-filters"],capture_output=True,text=True)
        if filters.returncode == 0 and ' drawtext ' in filters.stdout:
            return str(ff)
    raise RuntimeError("Set FFMPEG to a build with drawtext and libx264.")


def encode(out, ff):
    font=ROOT/'assets/fonts/Montserrat-Bold.ttf'
    face=f"fontfile='{font}'" if font.is_file() else "font='Helvetica Bold'"
    caption=f"drawtext={face}:text='under your house.':fontsize=60:fontcolor=white:shadowcolor=black@0.48:shadowx=1:shadowy=3:x=(w-tw)/2:y=h*0.591-th/2"
    common=[ff,'-hide_banner','-loglevel','error','-y']
    subprocess.run(common+['-framerate','30','-start_number','1','-i',str(out/'frames/%04d.png'),'-frames:v','180','-vf',caption+',scale=out_color_matrix=bt709','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(out/'cutaway_test.mp4')],check=True)
    subprocess.run(common+['-i',str(out/'frames/0120.png'),'-vf',caption,'-frames:v','1','-q:v','2',str(out/'still.jpg')],check=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--samples',type=int,help='Default: 16 on Metal, 5 on CPU after timing the M2 Pro.')
    ap.add_argument('--preview',type=int,metavar='FRAME')
    ap.add_argument('--percent',type=int,default=100,help='Preview resolution only')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.out.resolve()
    (out/'frames').mkdir(parents=True,exist_ok=True)
    encoder = None if args.preview else find_encoder()
    build()
    device=setup(args.samples)
    if args.preview:
        scene.render.resolution_percentage=args.percent
    frames=[args.preview] if args.preview else range(1,181)
    start=time.monotonic()
    print(f"Rendering {device}, {scene.cycles.samples} samples",flush=True)
    for f in frames:
        scene.frame_set(f)
        camera_at(f)
        scene.render.filepath=str(out/'preview.png' if args.preview else out/'frames'/f'{f:04d}.png')
        bpy.ops.render.render(write_still=True)
        if f%15==0 or args.preview:
            print(f"Frame {f} | elapsed {time.monotonic()-start:.2f}s",flush=True)
    if not args.preview:
        elapsed=time.monotonic()-start
        print(f"Render total {elapsed:.2f}s, {elapsed/180:.3f}s/frame",flush=True)
        encode(out, encoder)


if __name__=='__main__':
    main()

"""Kita Buat Dia • SME-01. Blender 5.3, from the repository checkout."""
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
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "pipeline/cutaway"))
import cutlib as C

from math import cos, sin, pi, tau

rng = random.Random(1701)
V = Vector
box, tube, beam, mat = C.box, C.strand, C.beam, C.material


def bar_figure():
    # v3 is a turnaround script with top-level render calls. Reuse the modelling
    # statements verbatim, stopping before its studio and omitting its outdir.
    path = ROOT / "page4/character_bar/build_bar_v3.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    end = next(i for i, n in enumerate(tree.body)
               if isinstance(n, ast.FunctionDef) and n.name == "workshop")
    tree.body = [n for n in tree.body[:end] if ast.unparse(n) != "OUT.mkdir(exist_ok=True)"]
    # Pose his free arm before the original script fits the shirt and sleeves.
    fit = next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=="bones" for t in n.targets))
    tree.body[fit:fit] = ast.parse(
        'orient("upperarm_r", (.03,-.98,.17))\norient("lowerarm_r", (.12,-.94,.32))'
    ).body
    exec(compile(tree, str(path), "exec"), {"__file__": str(path), "__name__": "bar_v3_model"})
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    figure = empty("Bar • v3 • at work", (0, 0, 0))
    for o in roots:
        o.parent = figure
    return figure


def device(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.refresh_devices()
        for d in prefs.devices:
            d.use = d.type in {'METAL', 'CPU'}
        metal = [d.name for d in prefs.devices if d.type == 'METAL']
    except (TypeError, RuntimeError) as exc:
        print("Metal enumeration:", exc, flush=True)
        metal = []
    scene.cycles.device = 'GPU' if metal else 'CPU'
    print("Cycles device:", scene.cycles.device, metal, flush=True)


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


def lathe(name, at, profile, material, sides=64, axis="Z", teeth=0, flutes=0):
    """Closed/open turned sections. Profiles run around the solid in r/z."""
    verts, faces = [], []
    for radius, h in profile:
        for j in range(sides):
            t = tau*j/sides
            r = radius
            if teeth and radius > .035:
                r *= 1 + (.105 if j % 4 in (1, 2) else 0)
            if flutes:
                r *= 1 + .022*cos(flutes*t)
            verts.append((r*cos(t), r*sin(t), h))
    for k in range(len(profile)-1):
        for j in range(sides):
            a, b = k*sides+j, k*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    obj = C.mesh(name, verts, faces, material)
    obj.location = at
    if axis == "Y":
        obj.rotation_euler.x = pi/2
    for p in obj.data.polygons:
        p.use_smooth = not teeth
    return obj


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
        "red":mat("Fresh watermelon flesh","b92437","fa6260",46,.0007,rough=.28),
        "pith":mat("Watermelon pith","dfe7b4",rough=.5),
        "seed":mat("Watermelon seeds","351c14",rough=.26),
        "foam":mat("Melon froth","f79887","ffd3a7",75,.0005,rough=.49),
        "juice":mat("Cold-pressed melon","b72f42","e7454f",11,.0004,rough=.21),
        "wood":mat("Meranti counter","684631","b18054",4,.0014),
        "cane":mat("Split cane","997044","c49860",17,.0005),
        "canvas":mat("Shadowed cart canvas","294e50","314f50",160,.00015,rough=.86),
        "awning":mat("Petrol canvas","285e61","427778",38,.001),
        "linen":mat("Unbleached canvas","cfc5a7","ece1c4",48,.0007)
    }
    for key in ("red","juice"):
        bs=p[key].node_tree.nodes.get("Principled BSDF")
        bs.inputs["Subsurface Weight"].default_value=.10
        bs.inputs["Subsurface Scale"].default_value=.005
    wood=p["wood"].node_tree
    stretch=wood.nodes.new("ShaderNodeVectorMath")
    stretch.operation="MULTIPLY"
    stretch.inputs[1].default_value=(1,27,39)
    wood.links.new(wood.nodes.new("ShaderNodeTexCoord").outputs["Object"],stretch.inputs[0])
    for node in wood.nodes:
        if node.type=="TEX_NOISE":
            wood.links.new(stretch.outputs[0],node.inputs["Vector"])
    glass=mat("Pressed clear glass","f5fcf8",rough=.065)
    bs=glass.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Transmission Weight"].default_value=1
    bs.inputs["IOR"].default_value=1.47
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
    return p


def wedge(name, at, size, rotation=0):
    """Cross-cut triangular wedge with pale pith, rind and embedded seeds."""
    root=empty(name,at)
    for outer,inner,m in ((1,.93,"rind"),(.93,.855,"pith"),(.855,.001,"red")):
        points=[(size*r*sin(t),-size*r*cos(t)) for r,seq in
                ((outer,range(19)),(inner,range(18,-1,-1))) for i in seq
                for t in [-.70+1.40*i/18]]
        o=C.section(name+" • "+m,points,-size*.22,size*.22,P[m])
        o.parent=root
    for rot,rad in ((-.40,.64),(-.1,.48),(.17,.70),(.41,.52),(-.53,.78)):
        o=C.sphere("Embedded seed",(size*rad*sin(rot),-size*.225,-size*rad*cos(rot)),
                   (size*.027,size*.017,size*.061),P["seed"])
        o.rotation_euler.y=-rot
        o.parent=root
    root.rotation_euler.y=rotation
    return root


def canopy():
    # Canvas panels and a scalloped sewn valance, running along the five-foot way.
    for j in range(19):
        x=(j-9)*.31
        m=P["awning" if j%2 else "linen"]
        roof=box("Striped canvas",(x,1.32,2.52),(.311,2.40,.025),m)
        roof.rotation_euler.x=.145
        edge=2.344
        outline=[(x-.155,edge),(x+.155,edge),(x+.155,edge-.085)]
        outline += [(x+.155*cos(a*pi/20),edge-.085-.071*sin(a*pi/20)) for a in range(1,21)]
        C.section("Bound scallop",outline,.123,.143,m)
    for x in (-2.20,1.82):
        tube("Awning upright",[(x,.18,.01),(x,.18,2.35)],.021,P["steel"])
        beam("Corner brace",(x,.18,1.96),(x,.56,2.40),.022,.022,P["steel"])
    tube("Valance rail",[(-2.9,.16,2.34),(2.9,.16,2.34)],.018,P["steel"])


def location():
    road=mat("Weathered roadside","82796a","a69780",2,.0016)
    box("Shaded pavement",(0,0,-.057),(60,60,.1),road)
    wall=mat("Sun-washed lime plaster","c2a78e","ecdbc1",2.6,.0014)
    box("Shophouse across the lane",(0,4.8,1.65),(15,.28,4.1),wall)
    for x in (-3.35,-1.22,1.0,3.2):
        box("Dark recessed window",(x,4.62,1.64),(1.42,.12,1.42),P["deep"],.02)
        for i in range(10):
            o=box("Painted louvre",(x,4.51,1.05+i*.13),(1.31,.057,.105),P["paint"],.005)
            o.rotation_euler.x=-.28
        box("Centre stile",(x,4.47,1.63),(.052,.05,1.40),P["deep"])
        box("Plaster sill",(x,4.46,.92),(1.57,.25,.095),wall,.012)
    canopy()
    # A palm at the roadside casts broken shadows on the canvas and plaster.
    leaf=mat("Oil palm fronds","304e37","688255",9,.0008)
    for ix,(x,y,h) in enumerate(((-2.1,3.4,2.67),(2.45,3.0,2.95))):
        tube("Palm trunk",[(x+.13,y,0),(x,y,h*.6),(x-.10,y,h)],.085,P["wood"])
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
                    length=.34*(sin(pi*u)**.54)+.03
                    off=V((-sin(a)*side,cos(a)*side,-.65))*length
                    tip=mid+off+V((.18*cos(a),.18*sin(a),-.09))
                    w=V((cos(a),sin(a),0))*.029
                    C.mesh("Palm leaflet",[mid,mid.lerp(tip,.40)+w,tip,mid.lerp(tip,.40)-w],[(0,1,2,3)],leaf)
            tube("Leaf rib",points,.006,leaf)
    # Rear display and short serving shelf leave the bicycle in front in silhouette.
    for j in range(4):
        box("Folding table plank",(.7,.92+j*.115,.89),(2.44,.112,.05),P["wood"],.006)
    for x in (-.32,1.73):
        for y1,y2 in ((.90,1.33),(1.33,.90)):
            beam("Table trestle",(x,y1,.03),(x,y2,.87),.04,.035,P["iron"])
    for j in range(3):
        box("Service shelf",(1.12,-.15+j*.115,1.016),(.72,.113,.041),P["wood"],.005)
    # A canvas tool sling under the narrow serving counter gives the
    # lower-centre of the section shots an uninterrupted subtitle field.
    for x in (.26,1.42):
        beam("Cart side rail",(x,-.28,.13),(x,-.28,.57),.025,.025,P["deep"])
    box("Counter sling • oilcloth",(.84,-.28,.34),(1.18,.016,.43),P["canvas"],.009)
    for z in (.135,.55):
        tube("Sling hem",[(.252,-.293,z),(1.43,-.293,z)],.003,P["deep"])
    beam("Counter lower rail",(.23,-.28,.565),(1.44,-.28,.565),.018,.023,P["deep"])
    box("Serving counter apron",(1.122,-.201,.785),(.72,.015,.425),P["canvas"],.005)
    for x in (.83,1.41):
        beam("Shelf stand",(x,.02,.03),(x,.02,1.00),.036,.036,P["deep"])
    for x,y in ((.98,1.03),(-.31,1.01)):
        basket(x,y,.917)
    wedge("Market sample",(.41,.92,1.066),.14,.48)


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
    for k in range(5):
        a=tau*k/4
        dx,dy=(.094*cos(a),.083*sin(a)) if k<4 else (0,0)
        o=C.sphere("Market watermelon",(x+dx,y+dy,z+(.25 if k==4 else .143)),(.102,.087,.093),P["rind"])
        o.rotation_euler.y=rng.uniform(-.8,.8)


def crank_loop(a,b,ra,rb,y):
    # External tangents of two unequal pitch circles in the wheel plane.
    ax,az=a
    bx,bz=b
    angle=math.atan2(bz-az,bx-ax)
    half=math.acos((ra-rb)/math.dist(a,b))
    upper,lower=angle+half,angle-half
    return (arc(ax,y,az,ra,upper,lower+tau,28)+arc(bx,y,bz,rb,lower,upper,28))


def wheel(name,x,z):
    hub=empty(name,(x,0,z))
    for rad,thick,m in ((.329,.024,"rubber"),(.307,.010,"steel"),(.317,.003,"rubber")):
        mount(hoop("Tyre" if thick==.024 else "Rolled rim",x,0,z,rad,thick,P[m]),hub)
    mount(disk("Bearing shell",(x,0,z),.026,.105,P["steel"]),hub)
    for i in range(32):
        a=tau*i/32
        b=a+(.34 if i%2 else -.34)
        mount(tube("Butted spoke",[(x+.023*cos(b),(-1)**i*.042,z+.023*sin(b)),
                                    (x+.306*cos(a),0,z+.306*sin(a))],.00155,P["steel"]),hub)
    mount(tube("Valve stem",[(x,0,z+.287),(x,0,z+.306)],.0028,P["iron"]),hub)
    return hub


def bike():
    rear=(.19,.393)
    front=(-.96,.353)
    crank=(-.37,.34)
    saddle=(-.29,.884)
    head=(-.81,.81)
    front_hub=wheel("Stationary front wheel",*front)
    rear_hub=wheel("Driven rear wheel",*rear)
    for a,b,r in ((head,crank,.025),(head,saddle,.023),(saddle,crank,.026)):
        tube("Lugged step frame",[(a[0],0,a[1]),(b[0],0,b[1])],r,P["enamel"])
    for s in (-1,1):
        for a,b in ((saddle,rear),(crank,rear),(head,front)):
            tube("Fork or stay",[(a[0],s*.018,a[1]),(b[0],s*.056,b[1])],.012,P["enamel"])
        tube("Axle nut",[(rear[0],s*.045,rear[1]),(rear[0],s*.093,rear[1])],.015,P["steel"])
    tube("Seat post",[(saddle[0],0,.87),(-.26,0,1.016)],.017,P["steel"])
    C.sphere("Leather sprung saddle",(-.28,0,1.018),(.135,.079,.034),P["rubber"])
    tube("Quill stem",[(-.81,0,.805),(-.79,0,.97),(-.875,0,1.015)],.018,P["steel"])
    tube("Swept handlebar",[(-.79,-.216,1.025),(-.865,-.152,1.022),(-.875,0,1.015),
                             (-.865,.152,1.022),(-.79,.216,1.025)],.012,P["steel"])
    for s in (-1,1):
        tube("Rubber grip",[(-.835,s*.18,1.022),(-.771,s*.234,1.026)],.018,P["rubber"])
    tube("Brake cable",[(-.81,-.17,1.01),(-.93,-.11,.95),(-.95,-.055,.79),(-.869,-.045,.63)],.003,P["iron"])
    rotor=empty("Pedal spindle",(crank[0],0,crank[1]))
    for name,c,r,parent in (("Chainwheel",crank,.088,rotor),("Sprocket",rear,.042,rear_hub)):
        mount(disk(name,(c[0],-.065,c[1]),r,.011,P["iron"],teeth=20,sides=80),parent)
    path=crank_loop(crank,rear,.095,.047,-.066)
    tube("Oiled chain",path+[path[0]],.0046,P["steel"])
    pedals=[]
    for s in (-1,1):
        cx,cz=crank
        tip=(cx+s*.116,-s*.085,cz-s*.109)
        mount(beam("Crank arm",(cx,-s*.085,cz),tip,.016,.018,P["steel"]),rotor)
        pedal=box("Platform pedal",(tip[0],-s*.13,tip[2]),(.081,.087,.022),P["rubber"],.004)
        mount(pedal,rotor)
        pedals.append(pedal)
    # Trainer has wide feet and lifts the rear tyre four cm clear of the asphalt.
    for s in (-1,1):
        for x in (.00,.43):
            beam("Trainer A-frame",(x,s*.20,.035),(.19,s*.085,.393),.027,.027,P["paint"])
        beam("Skid",(-.035,s*.20,.024),(.46,s*.20,.024),.04,.042,P["deep"])
    beam("Trainer crossfoot",(.42,-.22,.027),(.42,.22,.027),.033,.045,P["steel"])
    return rear_hub,rotor,pedals


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
    rubber=mount(disk("Replacement rubber sleeve",(RX,-.041,RZ),.061,.140,P["rubber"]),roller)
    grip=[rubber]
    for i in range(26):
        a=i*tau/26
        grip.append(mount(tube("Moulded grip rib",[(RX+.060*cos(a),y,RZ+.060*sin(a))
                                                   for y in (-.111,.027)],.0027,P["rubber"]),roller))
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
    for y in (.052,.058,.064,.070):
        tube("Flat transmission belt",[(x,y,z) for x,_,z in belt+[belt[0]]],.0047,P["rubber"])
    mount(tube("Cross shaft",[(JX,-.192,GZ),(JX,.104,GZ)],.012,P["steel"]),pulley)
    # The mitre pair sits forward of the belt plane. Pitch cones share their
    # apex where the Y and Z shaft axes intersect.
    for o,at,axis,sign in ((pulley,(JX,-.183,GZ),"Y",-1),(spindle,(JX,-.183,GZ),"Z",1)):
        profile=[(.008,.017),(.020,.020),(.041,.041),(.041,.052),(.008,.052)]
        mount(lathe("Cut-steel mitre wheel",at,[(r,h*sign) for r,h in profile],
                    P["steel"],64,axis,teeth=16),o)
    mount(disk("Blade shaft",(JX,-.183,GZ+.083),.012,.094,P["steel"],"Z"),spindle)
    # Back, lower lip and side walls are retained in section, exposing bearings.
    profile=[(.254,.705),(.353,.712),(.679,.944),(.697,1.091),(.667,1.111),
             (.488,1.111),(.466,1.024),(.259,.848)]
    C.section("Cast guard • rear wall",profile,.100,.120,P["deep"])
    for a,b in ((0,1),(1,2),(2,3),(3,4),(4,5)):
        x,z=profile[a]
        xx,zz=profile[b]
        dx,dz=xx-x,zz-z
        norm=math.hypot(dx,dz)
        nx,nz=-.007*dz/norm,.007*dx/norm
        C.section("Guard return • exposed section",[(x,z),(xx,zz),(xx+nx,zz+nz),(x+nx,z+nz)],
                  -.123,.119,P["deep"],P["steel"])
        tube("Bright sawn edge",[(x,-.123,z),(xx,-.123,zz)],.003,P["steel"])
    # The intact transparent guard covers both stages during the hook. The
    # fixed test view removes only its front half, as an editorial section.
    cover_profile=[(.244,.702),(.353,.699),(.683,.941),(.707,1.088),
                   (.677,1.110),(.487,1.110),(.452,1.027),(.244,.85)]
    cover=C.section("Clear formed safety cover",cover_profile,-.24,-.237,P["glass"])
    for a,b in zip(cover_profile,cover_profile[1:]+cover_profile[:1]):
        lip=tube("Safety cover • rolled edge",[(a[0],-.24,a[1]),(b[0],-.24,b[1])],.0028,P["steel"])
        lip.parent=cover
    for x,z in ((.28,.740),(.65,.963),(.66,1.073)):
        disk("Guard fastener",(x,-.126,z),.008,.007,P["steel"],sides=6)
    for s in (-1,1):
        beam("Rack upright",(.21,s*.065,.407),(.53,s*.075,.99),.017,.021,P["deep"])
        beam("Rack brace",(.01,s*.035,.68),(.47,s*.075,.99),.015,.019,P["steel"])
    for z,r,d,m in ((1.065,.028,.015,"iron"),(1.085,.034,.009,"steel")):
        disk("Shaft bearing",(JX,-.183,z),r,d,P[m],"Z")
    # Front of the bayonet socket is sectioned, leaving a view into the blades.
    for z,r in ((1.097,.088),(1.110,.091),(1.121,.079)):
        pts=[(JX+r*cos(t),-.183+r*sin(t),z) for t in [pi*i/40 for i in range(41)]]
        tube("Sectioned locking socket",pts,.008,P["deep"])
    for xx in (JX-.076,JX+.076):
        beam("Bayonet support",(xx,-.181,1.10),(xx,.068,1.10),.012,.014,P["deep"])
        box("Bayonet locking tab",(xx,-.185,1.123),(.013,.035,.030),P["deep"],.003)
    for i in range(4):
        a=i*pi/2+.4
        coords=[(r*cos(a)-w*sin(a),r*sin(a)+w*cos(a),h) for r,w,h in
                ((.005,-.006,.124),(.054,-.006,.135),(.064,.003,.151),(.040,.011,.138),(.005,.007,.124))]
        blade=C.mesh("Stainless cutting wing",coords,[(0,1,2,3,4)],P["steel"])
        blade.parent=spindle
        solid=blade.modifiers.new("Blade thickness","SOLIDIFY")
        solid.thickness=.0015
    witness=arc(.19,-.018,.393,.343,1.075,1.16,6)
    mount(tube("Tyre chalk stripe",witness,.007,P["chalk"]),REAR)
    return roller,pulley,spindle,[smooth],grip,cover


def power_trace():
    # A single painted schematic follows the near crank, chain run, wheel,
    # roller, belt, right-angle transfer, vertical shaft and one blade.
    path=[(-.254,-.176,.231),(-.254,-.095,.231),(-.37,-.095,.34),(-.38,-.077,.436),
          (.19,-.077,.440),(.19,-.032,.393),(.425,-.028,.630)]
    path+=arc(.19,-.028,.393,.342,.79,1.245,18)
    path += [(RX,-.114,RZ),(RX+.039,-.114,RZ-.041),(JX+.027,-.118,GZ-.034),
             (JX,-.121,GZ),(JX,-.196,GZ),(JX,-.196,1.130),(JX+.055,-.205,1.144)]
    return tube("Section key • one power path",path,.0047,P["trace"])


def glassware():
    x=JX
    center_y=-.183
    base=1.119
    # Continuous thin inner/outer surfaces, thick pressed foot and rolled rim.
    prof=[(.001,0),(.069,0),(.076,.012),(.079,.04),(.108,.255),(.109,.287),
          (.113,.291),(.113,.297),(.106,.297),(.103,.287),(.103,.255),
          (.073,.04),(.067,.019),(.001,.019)]
    lathe("Fluted locking blender jug",(x,center_y,base),prof,P["glass"],96,flutes=8)
    for route,radius,m in (([(.098,.238),(.144,.246),(.166,.231),(.155,.119),(.138,.094),(.083,.091)],.011,"glass"),):
        tube("Cast jug handle",[(x+dx,center_y+.025,base+h) for dx,h in route],radius,P[m])
    lid=empty("Interlocked lid",(x,center_y,base+.297))
    for h,r,d,m in ((.001,.114,.016,"deep"),(.014,.104,.014,"rubber"),(.028,.043,.025,"paint")):
        mount(disk("Lid seal",(x,center_y,lid.location.z+h),r,d,P[m],"Z"),lid)
    # Cup-only values; the spindle is exposed through the bottom of the jug.
    chunks=[]
    for j in range(9):
        a=2.40*j
        pos=(x+.041*cos(a),center_y+.037*sin(a),base+.047+.019*j)
        o=box("Loaded chopped melon",pos,(.068,.053,.053),P["red"],.009)
        o.rotation_euler=(.31*sin(a),.46*cos(a),a)
        chunks.append(o)
    # Liquid and surface details share a pivot at the blade seat.
    liquid=empty("Blending contents",(x,center_y,base))
    drink=lathe("Juice descending into vortex",(x,center_y,base),
                [(.002,.049),(.073,.045),(.095,.218),(.094,.232),(.076,.224),
                 (.047,.200),(.027,.167),(.012,.125),(.002,.115)],P["juice"],96,flutes=5)
    mount(drink,liquid)
    for i in range(3):
        pts=[]
        for j in range(52):
            u=j/51
            a=3.7*u+i*tau/3
            r=.091-.054*u
            pts.append((x+r*cos(a),center_y+r*sin(a),base+.232-.034*u**1.2))
        mount(tube("Froth caught in swirl",pts,.0023,P["foam"]),liquid)
    serving=empty("One glass ready",(.85,-.115,1.037))
    for o in (
        lathe("Pressed kopitiam tumbler",(0,0,0),[(.001,0),(.040,0),(.044,.014),(.056,.155),
            (.058,.168),(.058,.174),(.054,.174),(.052,.163),(.040,.023),(.001,.017)],P["glass"],80,flutes=10),
        lathe("First serving",(0,0,0),[(.001,.019),(.039,.019),(.052,.151),(.050,.157),
                                       (.001,.155)],P["juice"],80),
        lathe("Fine surface foam",(0,0,0),[(.0001,.156),(.049,.157),(.051,.154)],P["foam"],80)):
        o.parent=serving
    garnish=wedge("Fresh melon on rim",(.032,.019,.195),.065,-.83)
    garnish.parent=serving
    for i in range(23):
        a=rng.uniform(-2.94,-.26)
        h=rng.uniform(.028,.147)
        r=.044+.011*h/.16
        o=C.sphere("Glass condensation",(r*cos(a),r*sin(a),h),(.0017,.0014,.0026),P["glass"])
        o.parent=serving
    remnant=box("Last piece being drawn into vortex",(x+.031,center_y+.013,base+.222),
                (.046,.032,.040),P["red"],.006)
    remnant.rotation_euler=(.4,-.33,.71)
    mount(remnant,liquid)
    return lid,chunks,liquid,serving


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


def camera(name, pos, target, height, focus, fstop):
    # Physical perspective, with height measured at the target plane.
    data=bpy.data.cameras.new(name)
    cam=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(cam)
    optics(cam,pos,target,height,focus,fstop)
    return cam


def optics(cam,pos,target,height,focus,fstop):
    aim=V(target)-V(pos)
    cam.location=pos
    cam.rotation_euler=aim.to_track_quat("-Z","Y").to_euler()
    cam.data.sensor_fit="VERTICAL"
    cam.data.sensor_height=36
    cam.data.lens=36*aim.length/height
    cam.data.dof.use_dof=True
    cam.data.dof.focus_distance=(V(focus)-V(pos)).dot(aim.normalized())
    cam.data.dof.aperture_fstop=fstop


def show(objs, enabled):
    for obj in objs:
        obj.hide_render=not enabled
        if obj.children:
            show(obj.children,enabled)


def shot(beat,progress=0):
    # The paired test locks the lens, camera, jar and fruit load. Only the
    # roller surface, drive phase, section trace and outcome change.
    fixed=beat==3 or beat=="motion"
    show(OLD,not fixed)
    show(GRIP,fixed or beat==4)
    if beat==4:
        show(OLD,False)
    blend=min(1,max(0,(progress-.45)/.42)) if beat=="motion" else float(beat in (3,4))
    blend=blend*blend*(3-2*blend)
    show(CHUNKS,blend<1)
    for i,(chunk,rest) in enumerate(zip(CHUNKS,LOAD)):
        radius=V((rest.x-JX,rest.y+.183))
        phase=blend*2.4
        chunk.location=(JX+(radius.x*cos(phase)-radius.y*sin(phase))*(1-blend),
                        -.183+(radius.x*sin(phase)+radius.y*cos(phase))*(1-blend),
                        rest.z+blend*(1.15-rest.z))
        chunk.scale=(1-.95*blend,)*3
    show([PULP],blend>0)
    PULP.scale.z=(.09+.91*blend)*(.58 if beat==4 else 1)
    PULP.rotation_euler.z=progress*2*tau
    show([COVER],beat in (1,4) or (beat=="motion" and progress<.27))
    show([TRACE],beat==3 or (beat=="motion" and progress>=.27))
    show([CUP],beat==4)
    show([FALL],beat==1)
    show([LID],beat!=1)
    LID.location.z=1.74 if beat==1 else 1.416
    LID.location.x=JX+.045 if beat==1 else JX
    BAR.location=(.065,.42,.003) if beat!=4 else (.15,.46,.003)
    BAR.rotation_euler.z=1.00 if beat!=4 else .55
    REAR.rotation_euler.y=.34 if beat==2 else 0
    CRANK.rotation_euler.y=0
    ROLLER.rotation_euler.y=1.38 if beat==2 else -1.48
    PULLEY.rotation_euler.y=0
    SHAFT.rotation_euler.z=0
    for pedal in PEDALS:
        pedal.rotation_euler.y=0
    if beat=="motion":
        # A constant cadence and mechanically linked phases, evaluated at scene time.
        turns=progress*3.25
        CRANK.rotation_euler.y=-turns*tau
        REAR.rotation_euler.y=CRANK.rotation_euler.y*.095/.047
        ROLLER.rotation_euler.y=-REAR.rotation_euler.y*.353/.061
        PULLEY.rotation_euler.y=ROLLER.rotation_euler.y*.055/.045
        SHAFT.rotation_euler.z=-PULLEY.rotation_euler.y
        for pedal in PEDALS:
            pedal.rotation_euler.y=-CRANK.rotation_euler.y
        ease=progress*progress*(3-2*progress)
        pos=V(WIDE[0]).lerp(V(CLOSE[0]),ease)
        target=V(WIDE[1]).lerp(V(CLOSE[1]),ease)
        focus=V(WIDE[3]).lerp(V(CLOSE[3]),ease)
        optics(MOV,pos,target,WIDE[2]*(1-ease)+CLOSE[2]*ease,focus,7.1)
        SCENE.camera=MOV
    else:
        SCENE.camera={1:HERO,2:PAIRED,3:PAIRED,4:PAYOFF}[beat]


def render(path):
    start=time.monotonic()
    SCENE.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    return time.monotonic()-start


def deliver(preview,stills_only):
    out=HERE/"preview" if preview else HERE
    out.mkdir(exist_ok=True)
    SCENE.render.resolution_percentage=25 if preview else 100
    for i,name in enumerate(("hook","tapi_roller_tergelincir","jadi_pemacu","segelas_jus"),1):
        shot(i)
        path=out/f"beat{i}_{name}.png"
        print(f"TIMING {path.name} {render(path):.2f} s",flush=True)
    if stills_only:
        return
    SCENE.render.resolution_x,SCENE.render.resolution_y=540,960
    SCENE.cycles.samples=2 if preview else 24
    ff=shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("Install FFmpeg with libx264 and put ffmpeg on PATH")
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix=".hook-",dir=out) as work:
        folder=Path(work)
        for i,frame in enumerate(range(1,145)):
            SCENE.frame_set(frame)
            shot("motion",(frame-1)/143)
            render(folder/f"{i:04}.png")
        movie=folder/"hook_6s.mp4"
        subprocess.run([ff,"-hide_banner","-loglevel","error","-y","-framerate","24",
                        "-i",str(folder/"%04d.png"),"-r","24","-frames:v","144","-c:v","libx264",
                        "-crf","18","-pix_fmt","yuv444p" if preview else "yuv420p",
                        "-movflags","+faststart",str(movie)],check=True)
        movie.replace(out/movie.name)
    print(f"TIMING hook_6s.mp4 {time.monotonic()-start:.2f} s",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--preview",action="store_true",help="Quarter dimensions, low samples, full motion cadence")
    parser.add_argument("--stills-only",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    start=time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    BAR=bar_figure()
    SCENE=C.render_settings("CPU",1080,6 if args.preview else 48,144)
    device(SCENE)
    SCENE.render.fps=24
    SCENE.render.use_file_extension=True
    SCENE.cycles.max_bounces=8
    SCENE.cycles.transmission_bounces=6
    C.daylight("kita-buat-dia",rotation=1.8)
    world_bg=SCENE.world.node_tree.nodes.get("Background")
    world_bg.inputs["Strength"].default_value *= .48
    SCENE.view_settings.look="AgX - Medium High Contrast"
    light("Sun along the five-foot way","SUN",(-4,-3,3.7),(0,1,.5),2.2,(1,.75,.51),.06)
    light("Sky under canvas","AREA",(1.9,-1.8,2.7),(0,0,1),110,(.72,.87,1),2.3)
    light("Glass edge strip","AREA",(1.45,1.75,2.0),(.48,0,1.18),65,(1,.90,.72),.92)
    P=palette()
    location()
    REAR,CRANK,PEDALS=bike()
    ROLLER,PULLEY,SHAFT,OLD,GRIP,COVER=drive()
    TRACE=power_trace()
    LID,CHUNKS,PULP,CUP=glassware()
    LOAD=[chunk.location.copy() for chunk in CHUNKS]
    FALL=wedge("Watermelon segment falling into jar",(JX-.013,-.176,1.575),.139,.38)
    WIDE=((.62,-4.25,1.55),(-.135,.02,.65),4.15,(.21,0,.96))
    CLOSE=((1.34,-1.80,1.62),(.465,-.045,.84),1.32,(.47,-.11,.96))
    HERO=camera("01 • kayuh basikal",*WIDE,7.1)
    PAIRED=camera("02–03 • fixed test lens",*CLOSE,6.3)
    PAYOFF=camera("04 • segelas",(.98,-1.41,1.52),(.816,-.065,1.119),.68,(.85,-.115,1.16),2.8)
    MOV=camera("Motion • wheel to blade",*WIDE,7.1)
    print(f"TIMING scene assembly {time.monotonic()-start:.2f} s",flush=True)
    deliver(args.preview,args.stills_only)
    print(f"TIMING total {time.monotonic()-start:.2f} s",flush=True)

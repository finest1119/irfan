"""ED-01. Run in Blender with --factory-startup. Use -- --preview for quarter-size stills and motion."""
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[2] / "pipeline" / "cutaway"))
import cutlib as C

R = random.Random(4101)
TAU = math.tau
B = C.box
S = C.strand
M = C.material
STILLS = ["beat1_hook", "beat2_inflow", "beat3_level", "beat4_outflow"]
INVERT = -1.08


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


def surface(name, rgb, light, scale, rough=.65, grain=.008, metal=0):
    return M(name, rgb, light, scale, grain, rough, metal)


def cast_material():
    mat = C.polyhaven("concrete_floor_02", 2.15)
    n, link = mat.node_tree.nodes, mat.node_tree.links.new
    p = n.get("Principled BSDF")
    base = p.inputs["Base Color"]
    tint = n.new("ShaderNodeMixRGB")
    tint.inputs[0].default_value = .38
    link(base.links[0].from_socket, tint.inputs[1])
    tint.inputs[2].default_value = C.color("A29A88")
    link(tint.outputs[0], base)
    return mat


def chip_faces(name, panels, density, materials):
    """Expose irregular aggregate in the sawn vertical slab and wall ends."""
    vs, fs, ids = [], [], []
    for x0, x1, y, z0, z1 in panels:
        for _ in range(int((x1-x0)*(z1-z0)*density)):
            x, z = R.uniform(x0,x1), R.uniform(z0,z1)
            radius = R.uniform(.004,.024)
            aspect, angle = R.uniform(.42,.98), R.uniform(0,TAU)
            idx = len(vs)
            for j in range(6):
                a = TAU*j/6
                u = radius * R.uniform(.7,1.2)*math.cos(a)
                v = radius * aspect * math.sin(a)
                vs.append((x+u*math.cos(angle)-v*math.sin(angle),y,z+u*math.sin(angle)+v*math.cos(angle)))
            fs.append(tuple(range(idx,idx+6)))
            ids.append(R.randrange(len(materials)))
    obj = C.mesh(name,vs,fs,materials[0])
    for mat in materials[1:]:
        obj.data.materials.append(mat)
    for poly, idx in zip(obj.data.polygons,ids):
        poly.material_index = idx


def tiles(x0, x1, y, z, depth, slope, mats):
    """Overlapping rolls and flat pans of interlocking concrete roof tiles."""
    v, f, ids = [], [], []
    cols = round((x1-x0)/.275)
    rows = math.ceil(depth/.32)
    for row in range(rows):
        ya = y+row*depth/rows
        for col in range(cols):
            x = x0+col*(x1-x0)/cols
            idx = len(v)
            mat_id = R.choices(range(4),[9,5,2,1])[0]
            for dy, dz in ((-.008,-.028),(-.013,0),(depth/rows+.032,-.026)):
                for frac, crown in ((0,.005),(.12,.013),(.24,.045),(.38,.041),(.50,.013),(.65,.003),(1,0)):
                    v.append((x+frac*(x1-x0)/cols,ya+dy,z+(ya+dy-y)*slope+dz+crown))
            for layer in range(2):
                for j in range(6):
                    k=idx+layer*7+j
                    f.append((k,k+1,k+8,k+7))
                    ids.append(mat_id)
    roof=C.mesh("Weathered interlocking roof tiles",v,f,mats[0])
    for mat in mats[1:]:
        roof.data.materials.append(mat)
    for poly,i in zip(roof.data.polygons,ids):
        poly.material_index=i
        poly.use_smooth=False


def gutter(a,b,y,z,metal):
    v, f = [],[]
    arc=[(.125*math.cos(t*math.pi/16),-.125*math.sin(t*math.pi/16)) for t in range(17)]
    for x in (a,b):
        v.extend([(x,y+dy,z+dz) for dy,dz in arc])
    for i in range(16):
        f.append((i,i+1,i+18,i+17))
    f.extend([tuple(range(17)),tuple(reversed(range(17,34)))])
    C.mesh("Folded zinc eaves gutter with stop ends",v,f,metal)
    for dy in (-.125,.125):
        S("Rolled gutter lip",[(a,y+dy,z),(b,y+dy,z)],.012,metal)
    for j in range(6):
        x=a+.18+(b-a-.32)*j/5
        S("Hanger strap",[(x,y+dy*1.045,z+dz*1.045-.005) for dy,dz in arc],.009,metal)


def plant(x,y,z,size, mats):
    v,f,ids=[],[],[]
    for _ in range(75):
        a=R.uniform(0,TAU)
        length=R.uniform(.27,1)*size
        elev=R.uniform(.25,1.23)
        idx=len(v)
        material=R.randrange(len(mats))
        for k in range(8):
            t=k/7
            d=length*t*math.cos(elev)
            h=length*(math.sin(elev)*t+.26*math.sin(math.pi*t))
            w=size*R.uniform(.028,.067)*math.sin(t*math.pi)
            for side in (-1,0,1):
                v.append((x+d*math.cos(a)-side*w*math.sin(a),y+d*math.sin(a)+side*w*math.cos(a),z+h-abs(side)*w*.42))
            if k:
                j=idx+(k-1)*3
                f.extend([(j,j+3,j+4,j+1),(j+1,j+4,j+5,j+2)])
                ids.extend([material,material])
    ob=C.mesh("Clump of rain-wet strap leaves",v,f,mats[0])
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
        B("Limewashed terrace frontage",(x-2.045,11.65,1.65),(4.45,4.8,3.3),p["plaster"])
        tiles(a,b,8.93,3.45,3.4,.48,tiles_m)
        B("Main eaves fascia",(x-2.045,9.02,3.35),(4.44,.12,.19),p["cream"])
        if h in (0,2):
            # Rolled bamboo shade at selected porches breaks up the terrace rhythm.
            C.pipe((x-4.05,7.18,2.34),(x-2.46,7.18,2.34),.065,mat=p["wood"])
            for j in range(6):
                B("Blind slat",(x-3.25,7.18,2.32-j*.032),(1.60,.025,.026),p["wood"],.004)
            for xx in (x-3.88,x-2.65):
                S("Blind cord",[(xx,7.15,2.43),(xx,7.15,2.14)],.006,p["cream"])
        tiles(a,b,6.88,2.56,2.43,.24,tiles_m)
        S("Clay ridge capping",[(a,12.34,5.075),(b,12.34,5.075)],.109,tiles_m[1])
        C.beam("Cement party-wall coping",(a,9.04,3.60),(a,12.34,5.185),.135,.106,p["concrete"])
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
        B("Square porch pier",(x-.05,7.10,1.26),(.24,.27,2.52),p["plaster"],.015)
        B("Pier plinth",(x-.05,7.10,.21),(.30,.33,.42),p["concrete"],.014)
        B("Porch paving",(x-2.04,8.21,.047),(4.44,2.42,.10),p["paving"])
        for dx in (.72,1.58,2.44,3.30,4.16):
            B("Tile joint",(x-dx,8.21,.100),(.009,2.36,.002),p["joint"])
        for yy in (7.42,8.05,8.68):
            B("Tile joint",(x-2.04,yy,.100),(4.44,.009,.002),p["joint"])
        B("Teak entrance",(x-3.52,9.225,1.10),(.92,.09,2.05),p["wood"],.018)
        for dz in (.65,1.56):
            B("Timber door panel",(x-3.52,9.17,dz),(.70,.045,.70),p["wood"],.025)
        B("Window surround",(x-1.62,9.22,1.56),(2.12,.13,1.45),p["cream"],.015)
        B("Tinted glazing",(x-1.62,9.142,1.55),(1.99,.032,1.33),p["glass"])
        for zz in (1.24,1.46,1.67,1.89):
            B("Glass louvre edge",(x-1.62,9.122,zz),(1.95,.018,.012),p["metal"])
        for dx in range(9):
            B("Fixed security grille",(x-2.57+dx*.24,9.10,1.55),(.019,.027,1.32),p["ink"])
        for zz in (1.02,1.56,2.08):
            B("Window grille transom",(x-1.62,9.09,zz),(2,.029,.023),p["ink"])
        gutter(a+.015,b-.015,6.795,2.57,p["metal"])
        path=[(x+.075,6.80,2.475),(x+.075,6.80,2.33),(x+.075,6.92,2.16),
              (x+.075,6.92,.52),(x+.075,6.90,.46),(x+.075,6.65,.325)]
        S("Rainwater leader",path[:-1],.083,p["pipe"])
        C.pipe(path[-2],path[-1],.091,mat=p["pipe"])
        for zz in (.70,1.79,2.19):
            C.pipe((x+.075,6.92,zz),(x+.075,6.92,zz+.045),.092,mat=p["metal"])
            B("Wall saddle",(x+.075,6.995,zz+.02),(.22,.07,.035),p["metal"],.007)
        plant(x-2.76,8.92,.30,.59,p["foliage"])
        bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.15,radius2=.22,depth=.29,location=(x-2.76,8.92,.185))
        bpy.context.object.data.materials.append(p["wood"])


def wheel(x,y,r,material,thickness):
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=10,location=(x,y,.30),
                                    rotation=(math.pi/2,0,0),major_radius=r,minor_radius=thickness)
    bpy.context.object.data.materials.append(material)


def kapcai(p):
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
    part("Stand",[(-.16,-.06,.35),(-.24,-.21,.011)],.015,p["ink"])
    part("Mirror stalk",[(.39,-.13,1.02),(.42,-.20,1.24)],.009,p["metal"])
    C.sphere("Oval mirror",(x+.42,y-.20,1.25),(.066,.022,.046),p["ink"])


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
    C.mesh("Palm frond leaflets",v,faces,p["foliage"][0])


def street(p):
    B("Damp bitumen carriageway",(0,4.64,.016),(62,2.70,.12),C.polyhaven("aerial_asphalt_01",3.3))
    for y in (3.33,5.94):
        B("Chipped tar shoulder",(0,y,.071),(52,.092,.032),p["joint"])
    for x in range(-22,23,5):
        B("Worn centre dash",(x,4.77,.078),(1.38,.065,.006),p["stripe"])
    for xa,xb in ((-24,-2.22),(-.72,24)):
        C.bounds("Compacted road shoulder",xa,xb,2.72,5.98,-1.50,.024,p["soil"])
    C.bounds("Fill over box culvert",-2.22,-.72,2.73,5.98,-.06,.023,p["soil"])
    B("Rear drain footing",(0,6.50,-.67),(54,1.10,.18),p["concrete"])
    B("Longkang house-side curb",(0,6.99,-.29),(54,.105,.74),p["concrete"],.015)
    for a,b,base in ((-27,-2.22,-.66),(-2.22,-.72,-.08),(-.72,27,-.66)):
        B("Longkang road-side curb",((a+b)/2,6.02,(base+.08)/2),(b-a,.105,.08-base),p["concrete"],.012)
    B("Silty water in open longkang",(0,6.50,-.138),(54,.91,.045),p["water"])
    for x in (-8.93,-4.48,4.42,8.87):
        B("Short driveway bridge",(x-2.33,6.50,.095),(2.24,1.12,.12),p["paving"],.025)
    B("Collector under carriageway",(-1.47,4.65,-1.15),(1.55,4.65,.18),p["concrete"])
    B("Box drain water",(-1.47,4.65,-.99),(1.24,4.65,.14),p["water"])
    # A covered connection below the road joins the roadside drain to the headwall.
    for x in (-2.19,-.75):
        B("Collector sidewall",(x,4.65,-.65),(.17,4.65,.92),p["concrete"])
    B("Collector crown",(-1.47,4.65,-.13),(1.61,4.65,.17),p["concrete"])
    for x in (-3.9,-.84,3.84,5.75,-5.04):
        plant(x,2.98,.335,.60,p["foliage"])
    verge(p)
    houses(p)
    garden_palm(1.20,16.8,5.46,p,1.64)
    garden_palm(11.4,16.2,6.65,p,2.72)
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


def pond(p):
    wet=p["concrete"]
    # The inlet gauge witnesses the high-water mark. Keep the outlet concrete clean.
    gauge_wall=C.weathering(wet.copy(), -.495, .078, .68)
    C.ground((-24,24),(.0,8),-1.85,layers=(("Lateritic subsoil",1.12,"45382f","715b47"),
             ("Weathered parent rock",8.1,"423f3b","6c655b")),roots=False,grains=7)
    C.ground((-20,-2.97),(0,3.31),.28,layers=(("Topsoil",.37,"332923","584632"),
             ("Wet silty clay",1.92,"4f3a30","80614e")),roots=False,grains=19)
    C.ground((2.82,17),(0,2.81),-1.50,layers=(("Stream bed",.46,"443d32","766d58"),),roots=False)
    C.foundation("slab",(-.08,1.35,-1.70),(5.81,2.70,.32),wet)
    C.foundation("wall",(-2.805,1.35,-.60),(.34,2.70,1.88),wet)
    wall=B("Outlet headwall",(2.55,1.35,-.60),(.38,2.70,1.88),wet)
    # Keep the inlet floor and the clear outlet bore at precisely the same invert.
    axis=Vector((1,-.33,0)).normalized()
    centre=Vector((2.55,.81,INVERT+.165))
    hole(wall,centre,axis,.206)
    C.pipe(centre-axis*.257,centre+axis*.84,.201,mat=p["metal"])
    for d in (-.248,.814):
        C.pipe(centre+axis*d,centre+axis*(d+.038),.223,mat=p["metal"])
    y=2.58
    for xa,xb,za,zb in ((-2.98,-2.22,-1.54,.34),(-.72,2.74,-1.54,.34),
                          (-2.22,-.72,-1.54,INVERT),(-2.22,-.72,-.08,.34)):
        B("Inlet headwall",((xa+xb)/2,y,(za+zb)/2),(xb-xa,.29,zb-za),gauge_wall,.012)
    for x in (-2.29,-.65):
        B("Cast inlet jamb",(x,2.36,-.562),(.14,.26,1.26),wet,.013)
    B("Cast inlet lintel",(-1.47,2.36,-.025),(1.78,.26,.17),wet,.015)
    for x in (-2.65,-.34,.64,1.62,2.19):
        for z in (.13,-.37,-1.08):
            C.sphere("Recessed form-tie plug",(x,2.429,z),(.021,.008,.021),p["joint"])
    # A scale staff gives the same waterline a fixed witness between shots.
    B("Enamel gauge backing",(.68,2.407,-.61),(.14,.045,1.42),p["cream"],.008)
    for j in range(15):
        width=.109 if j%5==0 else .078 if j%2==0 else .042
        B("Gauge graduation",(.617+width/2,2.38,-1.27+.09*j),(width,.013,.018),p["ink"])
    pmat=[M("Split stone "+a,a) for a in ("6a665c","b1a58e","827d6f","57564d","a79f8d")]
    chip_faces("Sawn gravel in the concrete section",
               [(-2.94,2.80,-.002,-1.845,-1.56),(-2.952,-2.656,-.003,-1.53,.32),
                (2.375,2.723,-.002,-1.53,.32)],740,pmat)
    C.bounds("Verge backing",-21.5,21.5,2.72,3.325,-.034,.195,p["soil"])
    B("Roadside grass verge",(0,2.99,.24),(43,.67,.18),C.polyhaven("aerial_grass_rock",2.5))
    B("Receiving channel invert",(6.87,.69,-1.45),(8.23,1.44,.16),wet)
    B("Receiving channel far bank",(6.87,1.37,-.86),(8.23,.20,1.18),wet)
    B("Downstream tailwater",(6.88,.66,-1.32),(8.22,1.31,.085),p["water"])


def make_water():
    water=M("Rainwater reflecting the cloud cover","506773",rough=.18,metal=.28)
    shader=water.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Coat Weight"].default_value=.45
    shader.inputs["Coat Roughness"].default_value=.14
    n,link=water.node_tree.nodes,water.node_tree.links.new
    noise=n.new("ShaderNodeTexNoise")
    coord=n.new("ShaderNodeTexCoord")
    stretch=n.new("ShaderNodeVectorMath")
    stretch.operation='MULTIPLY'
    stretch.inputs[1].default_value=(1.8,6,1)
    link(coord.outputs["Object"],stretch.inputs[0])
    link(stretch.outputs[0],noise.inputs["Vector"])
    noise.inputs["Scale"].default_value=3
    bump=n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=.19
    bump.inputs["Distance"].default_value=.020
    link(noise.outputs["Fac"],bump.inputs["Height"])
    link(bump.outputs[0],shader.inputs["Normal"])
    return water


def current(name, points, widths, heights, mat):
    """Tapered oval stream with irregular flutes catching reflected skylight."""
    vs,faces=[],[]
    for k,point in enumerate(points):
        tangent=(Vector(points[min(len(points)-1,k+1)])-Vector(points[max(0,k-1)])).normalized()
        side=tangent.cross(Vector((0,0,1)))
        if side.length<.01:
            side=Vector((1,0,0))
        side.normalize()
        up=side.cross(tangent).normalized()
        for j in range(40):
            t=j*TAU/40
            fluting=1+.055*math.sin(7*t+k*.4)+.04*math.cos(3*t-k*.8)
            vs.append(Vector(point)+fluting*(side*widths[k]*math.cos(t)+up*heights[k]*math.sin(t)))
            if k:
                a=(k-1)*40+j
                b=(k-1)*40+(j+1)%40
                faces.append((a,b,b+40,a+40))
    ob=C.mesh(name,vs,faces,mat)
    for f in ob.data.polygons:
        f.use_smooth=True
    return ob


def ring(name,x,y,z,r,yscale,mat,thickness=.007):
    points=[]
    for j in range(81):
        a=j*TAU/80
        rr=r*(1+.017*math.sin(5*a+.7*r))
        points.append((x+rr*math.cos(a),y+yscale*rr*math.sin(a),z))
    return S(name,points,thickness,mat)


def water_state(p,level,stage,leaf_xy):
    """Complete still-state water body. The section face ends exactly at the surface."""
    before=set(bpy.data.objects)
    B("Water in section",(-.14,1.257,(level-1.55)/2+.001),(4.99,2.425,level+1.55+.002),p["depth"])
    # Optical attenuation through the exposed water column, darkest at the bed.
    n=p["depth"].node_tree.nodes
    if not n.get("Depth ramp"):
        link=p["depth"].node_tree.links.new
        ramp=n.new("ShaderNodeValToRGB")
        ramp.name="Depth ramp"
        for elt,pos,rgb in zip(ramp.color_ramp.elements,(.05,1.0),("253943","68818a")):
            elt.position=pos
            elt.color=C.color(rgb)
        sep=n.new("ShaderNodeSeparateXYZ")
        link(n.new("ShaderNodeTexCoord").outputs["Generated"],sep.inputs[0])
        link(sep.outputs["Z"],ramp.inputs[0])
        link(ramp.outputs[0],n.get("Principled BSDF").inputs["Base Color"])
    # Wave normals redirect the sky into fine, changing reflections across the pool.
    v,fs=[],[]
    nx,ny=150,74
    for j in range(ny+1):
        y=.043+2.426*j/ny
        for i in range(nx+1):
            x=-2.635+4.995*i/nx
            dist=math.hypot(x+1.46,(y-2.24)*1.18)
            wind=.006*math.sin(22*y+1.8*math.sin(x*2.7)+.73*math.cos(9*x+2*y))
            wave=.018*math.sin(25*dist+1.4*y)*math.exp(-dist*1.6)
            v.append((x,y,level+.008+wind+wave))
            if j and i:
                k=len(v)-1
                fs.append((k-nx-2,k-nx-1,k,k-1))
    top=C.mesh("Rippling reservoir surface",v,fs,p["water"])
    for face in top.data.polygons:
        face.use_smooth=True
    # A broad turbulent jet during loading and a residual trickle after rain.
    w=[.49,.51,.48,.44,.38] if stage!="low" else [.082,.078,.066,.049,.041]
    pts=[(-1.47,2.77,level+.045),(-1.47,2.44,level+.060),(-1.46,2.26,level+.045),
         (-1.46,2.04,level+.029),(-1.44,1.82,level+.005)]
    current("Current through inlet",pts,w,[.04,.05,.041,.028,.010],p["stream"])
    for j in range(7 if stage!="low" else 2):
        x=-1.48+R.uniform(-.37,.37)*(1 if stage!="low" else .14)
        S("Aerated inlet streak",[(x,2.4,level+.094),(x+.024,2.25,level+.083),
          (x+.018,2.08,level+.060),(x-.025,1.90,level+.031)],.008,p["ripple"])
    # One surface filament follows the tracked leaf in each successive pond view.
    x,y=leaf_xy
    if stage=="inflow":
        path=[(-1.47,2.43,level+.116),(-1.46,2.22,level+.096),
              (-1.43,1.98,level+.062),(x,y,level+.028)]
    elif stage=="high":
        path=[(-1.46,2.24,level+.096),(-1.40,2.02,level+.060),
              (-1.11,1.83,level+.032),(-.76,1.75,level+.030),(x,y,level+.031)]
    else:
        path=[(x-.48,y+.10,level+.030),(x-.21,y+.05,level+.029),
              (x,y,level+.030),(2.35,.87,level+.033)]
    current("Tracked surface current",path,
            [.007]+[.047]*(len(path)-2)+[.009], [.006]*len(path),p["tracer"])
    # Small discontinuous rafts of entrained air follow the turbulent inlet.
    vs,faces=[],[]
    for j in range(125 if stage!="low" else 19):
        t=R.random()
        width=(.34+.28*t)*(1 if stage!="low" else .18)
        x=-1.46+width*(math.sin(14*t)*.51+R.uniform(-.48,.48))
        y=2.28-.82*t+R.uniform(-.035,.035)
        idx=len(vs)
        rad=R.uniform(.006,.020)
        for k in range(7):
            a=k*TAU/7
            vs.append((x+.82*rad*math.cos(a),y+rad*math.sin(a),level+.029+.045*(1-t)**2))
        faces.append(tuple(range(idx,idx+7)))
    C.mesh("Broken foam on the loading current",vs,faces,p["ripple"])
    for j in range(3):
        # Short curved wavefronts spread from the culvert mouth.
        r=.33+j*.19
        S("Inlet spreading wake",[(-1.46+r*math.cos(a),2.06+.68*r*math.sin(a),level+.010)
                                  for a in [math.pi*(1.06+.87*i/48) for i in range(49)]],.006,p["ripple"])
    end=Vector((2.55,.81,INVERT+.165))+Vector((1,-.33,0)).normalized()*.84
    count=15
    scale=1 if stage!="low" else .63
    pts=[(end.x+t*.71*scale,end.y-t*.23*scale,end.z-.057-.41*t*t) for t in [i/(count-1) for i in range(count)]]
    current("Outflow falling to the lower channel",pts,[scale*(.123-.061*i/(count-1)) for i in range(count)],
            [scale*(.079-.038*i/(count-1)) for i in range(count)],p["tracer"] if stage=="low" else p["stream"])
    for i in range(3):
        ring("Tailwater ripples",pts[-1][0],pts[-1][1],-1.273,.11+.11*i,.68,p["ripple"],.004)
    x,y=leaf_xy
    sz=.27
    v=[]
    for i in range(11):
        t=i/10
        half=sz*.43*math.sin(math.pi*t)**.85
        for side in (-1,0,1):
            v.append((x+sz*(t-.5)*1.80+side*half*.21,y+sz*(t-.5)*.31+side*half,
                      level+.021+.044*(t-.42)**2+(.026 if side==0 else .0)*math.sin(math.pi*t)))
    faces=[(i+j,i+j+3,i+j+4,i+j+1) for i in range(0,30,3) for j in (0,1)]
    C.mesh("Tracked water-green leaf",v,faces,p["leaf"])
    S("Leaf midrib and petiole",[(x-sz*1.15,y-sz*.22,level+.024)]+[v[i] for i in range(1,33,3)],.006,p["vein"])
    for j in (2,4,6,8):
        for side in (-1,1):
            S("Leaf vein",[v[j*3+1],v[(j+1)*3+1+side]],.002,p["vein"])
    return set(bpy.data.objects)-before


def hook_water(p):
    # A gravity-curved jet issues from the flared shoe while the final bead detaches above.
    for h in range(-2,4):
        x=4.45*h+.075
        ts=[i/18 for i in range(19)]
        pts=[(x+.012*math.sin(3*t),6.68-.31*t,.344-.17*t-.63*t*t) for t in ts]
        jet=current("Roof runoff",pts,[.061-.027*t for t in ts],[.038-.012*t for t in ts],p["stream"])
        if h==0:
            tracked_jet=jet
            # Two quadrature modes travel down the jet, deforming its silhouette continuously.
            jet.shape_key_add(name="Mean flow")
            for mode in range(2):
                key=jet.shape_key_add(name="Moving runoff flute "+str(mode))
                for i,vertex in enumerate(key.data):
                    k,j=divmod(i,40)
                    t=ts[k]
                    phase=TAU*(2.2*t+j/40)+mode*math.pi/2
                    delta=vertex.co-Vector(pts[k])
                    vertex.co+=delta*(.29*math.sin(phase)*t)
                key.slider_min=-1
                driver=key.driver_add("value").driver
                driver.expression=f"sin(frame*0.41+{mode}*pi/2)"
        for j in range(3):
            cx,cy=x+.008,6.447
            wave=ring("Longkang impact",0,0,0,.245,.72,p["ripple"],.004)
            wave.location=(cx,cy,-.1125)
            if h==0:
                for f in range(-20+j*7,146,21):
                    for dt,scale,lift in ((0,.18,-.007),(5,.44,.003),(15,.80,.001),(20,1,-.010)):
                        wave.scale=(scale,scale,1)
                        wave.location.z=-.114+lift
                        wave.keyframe_insert(data_path="scale",frame=f+dt)
                        wave.keyframe_insert(data_path="location",frame=f+dt)
            else:
                wave.scale=(.35+.27*j,.35+.27*j,1)
        if h==0:
            for i in range(4):
                sp=C.sphere("Splash at the shoe",pts[0],(.013,.011,.024),p["ripple"])
                for frame in range(i*4-15,162,14):
                    for dt,t in ((0,.12),(7,.61),(13,.97)):
                        sp.location=(x+.042*math.sin(i*1.7+t*3),6.68-.31*t,.344-.17*t-.63*t*t)
                        sp.keyframe_insert(data_path="location",frame=frame+dt)
    glass=M("Clear bead with a sky reflection","b5c7cb",rough=.075,metal=.17)
    shader=glass.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Transmission Weight"].default_value=.83
    shader.inputs["IOR"].default_value=1.333
    v,f=[],[]
    for k,(z,r) in enumerate([(-.067,.003),(-.061,.022),(-.044,.036),(-.018,.040),(.009,.032),(.039,.017),(.080,.003)]):
        for j in range(32):
            a=j*TAU/32
            v.append((r*math.cos(a),r*math.sin(a),z))
            if k:
                i=(k-1)*32+j
                b=(k-1)*32+(j+1)%32
                f.append((i,b,b+32,i+32))
    drop=C.mesh("Last drop at the gutter seam",v,f,glass)
    for poly in drop.data.polygons:
        poly.use_smooth=True
    for frame,z,scale in ((1,2.405,.62),(21,2.384,.90),(30,2.352,1),(34,2.283,1),(40,1.982,.88),
                          (46,1.40,.74),(51,.71,.63),(58,-.41,.42),(59,-.51,0),(144,-.51,0)):
        drop.location=(-.198,6.713,z)
        drop.scale=(scale,scale,scale)
        drop.keyframe_insert(data_path="location",frame=frame)
        drop.keyframe_insert(data_path="scale",frame=frame)
    return tracked_jet


def lighting():
    C.daylight("di-belakang-tabir",rotation=1.9)
    light=bpy.data.lights.new("Cool skylight beneath the eaves",'AREA')
    light.energy,light.color,light.shape,light.size=280,(.69,.81,1),'DISK',5
    ob=bpy.data.objects.new(light.name,light)
    bpy.context.scene.collection.objects.link(ob)
    ob.location=(.8,3.1,2.65)
    ob.rotation_euler=(Vector((-.5,7.6,1.15))-ob.location).to_track_quat('-Z','Y').to_euler()


def build():
    p={"concrete":cast_material(),"ink":M("Ink-blue enamel","18313C",rough=.37,metal=.25),
       "metal":surface("Galvanised zinc","7d837f","a1a49d",32,.36,.002,.56),
       "plaster":surface("Warm stippled render","b6ae9d","d2c7ad",4),
       "cream":surface("Painted joinery","c4beab","eae2cf",11),
       "wood":surface("Weathered teak","644834","94694e",5),
       "pipe":surface("Weathered rainwater PVC","949e9c","d3d3c6",16,.38,.002),
       "paving":C.polyhaven("grooved_concrete_driveway",2.0),"glass":M("Porch glazing","455862",rough=.22,metal=.49),
       "soil":C.polyhaven("excavated_soil_wall",2.75),
       "joint":surface("Wet construction joint","504b43","797064",37),
       "stripe":surface("Road paint","aba897","c3bd9e",15),
       "rubber":M("Tyre rubber","282b2a",rough=.73),
       "foliage":[surface("Lanceolate foliage "+a,a,b,8,.44) for a,b in
                  [("424e33","73804a"),("55643c","8d985e"),("515435","94a064")]],
       "water":make_water(),"stream":M("Silvery aerated runoff","8599a1",rough=.15,metal=.42),
       "ripple":M("Reflected sky along wave crests","acbcbf",rough=.19,metal=.41),
       "depth":surface("Section through silty blue water","334951","607178",1.5,.32,.004),
       "leaf":M("Single tracer leaf","32B8A5",rough=.30),"vein":M("Leaf veins","98c9ac",rough=.37)}
    # Clear water around narrow reflected highlights, also readable against pale concrete.
    jet=p["stream"].node_tree.nodes.get("Principled BSDF")
    jet.inputs["Base Color"].default_value=C.color("b6cad1")
    jet.inputs["Metallic"].default_value=.04
    jet.inputs["Transmission Weight"].default_value=.73
    jet.inputs["IOR"].default_value=1.333
    jet.inputs["Roughness"].default_value=.095
    jet.inputs["Coat Weight"].default_value=.32
    tracer=p["stream"].copy()
    tracer.name="Active water filament • #32B8A5"
    shader=tracer.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value=C.color("32B8A5")
    shader.inputs["Transmission Weight"].default_value=.18
    p["tracer"]=tracer
    pond(p)
    street(p)
    tracked_jet=hook_water(p)
    states=[water_state(p,z,name,pos) for z,name,pos in [(-.973,"inflow",(-1.46,1.62)),
            (-.56,"high",(-.18,1.62)),(-.989,"low",(2.09,.97))]]
    lighting()
    return states,tracked_jet,p


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    proof="--proof" in sys.argv
    preview="--preview" in sys.argv
    scene=C.render_settings("CPU",width=1080,samples=2 if preview or proof else 10,frames=144)
    scene.render.resolution_percentage=25 if preview or proof else 100
    device(scene)
    scene.render.fps=24
    states,tracked_jet,p=build()
    def set_state(index):
        for i,group in enumerate(states):
            for ob in group:
                ob.hide_render=(i!=index)
    # Orthographic shots keep the same elevation reference when comparing water levels.
    shots=[((.00,6.76,.62),4.47,30,29),((.57,1.35,-.68),12.72,-24,14),
           ((.00,1.68,-1.16),6.1,-29,16),((2.76,.91,-1.37),4.35,-36,23)]
    movie_keys=[(1,((-.095,6.79,2.23),1.93,35,9)),(30,((-.080,6.78,2.13),1.86,34,10)),
                (87,((.10,6.72,.84),1.73,30,15)),(144,((.10,6.60,.12),1.50,25,29))]
    cam=C.portrait_camera(*shots[0])
    def render(path):
        scene.render.filepath=str(path)
        start=time.monotonic()
        result=bpy.ops.render.render(write_still=True)
        if "FINISHED" not in result or not path.is_file():
            raise RuntimeError(f"Missing render for {path.name}")
        return time.monotonic()-start
    work=HERE/("preview_v2" if preview else ".work")
    work.mkdir(exist_ok=True)
    target=work if preview or proof else HERE
    if "--movie-only" not in sys.argv:
        for i,(stem,pose,state) in enumerate(zip(STILLS,shots,(0,0,1,2))):
            tracked_jet.active_material=p["tracer"] if i==0 else p["stream"]
            set_state(state)
            C.portrait_camera(*pose,camera=cam)
            if i==1:
                # A perspective overview keeps the houses in context behind both ports.
                target_point=Vector(pose[0])
                cam.location=target_point+(cam.location-target_point).normalized()*14.0
                cam.data.type='PERSP'
                cam.data.lens=cam.data.sensor_height*14.0/pose[1]
            scene.frame_set(37)
            seconds=render(target/(stem+".png"))
            print(f"TIMING {stem} {seconds:.2f}",flush=True)
    tracked_jet.active_material=p["tracer"]
    set_state(0)
    for frame,pose in movie_keys:
        C.portrait_camera(*pose,camera=cam,frame=frame)
    if proof:
        for f in (1,80,144):
            scene.frame_set(f)
            render(work/f"motion{f}.png")
        return
    scene.render.resolution_x,scene.render.resolution_y=540,960
    scene.cycles.samples=1 if preview else 4
    scene.cycles.max_bounces=3
    start=time.monotonic()
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        tmp=Path(tmp)
        for f in range(1,145):
            scene.frame_set(f)
            render(tmp/f"{f:04d}.png")
        elapsed=time.monotonic()-start
        print(f"TIMING hook_cycles {elapsed:.2f}",flush=True)
        subprocess.run([shutil.which("ffmpeg") or "ffmpeg","-hide_banner","-loglevel","error","-y",
                        "-framerate","24","-start_number","1","-i",str(tmp/"%04d.png"),"-frames:v","144",
                        "-vf","scale=out_color_matrix=bt709","-c:v","libx264","-preset","fast","-crf","17",
                        "-pix_fmt","yuv444p" if preview else "yuv420p","-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709",
                        "-movflags","+faststart",str(tmp/"hook_6s.mp4")],check=True)
        (tmp/"hook_6s.mp4").replace(target/"hook_6s.mp4")
        print(f"TIMING encode {time.monotonic()-start-elapsed:.2f}",flush=True)


if __name__=="__main__":
    main()

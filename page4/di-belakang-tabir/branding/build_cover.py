"""Longitudinal physical model of a terrace-house stormwater route."""
from pathlib import Path
import sys
import math
import random
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE))
from studio import C, scene, camera, light, still, bevel, cylinder
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=scene(1640,720)
rng=random.Random(165)
mat,box,mesh=C.material,C.box,C.mesh
wall=mat('Ink blue painted exhibition wall','142C36','203742',8,.0006,.82)
box('Gallery wall',(0,3.1,2),(32,.18,15),wall)
soil=[('Loam',.24,'70543A','997552'),('Laterite',.46,'784D36','A76E50'),('Subsoil',.20,'86684C','BA8A5F')]
C.ground((-4.66,3.53),(-.04,1.65),-.16,soil,seed=47,grains=32,roots=False,relief=.045)
concrete=mat('Cast concrete, sandy cut','928977','BDB8A7',37,.006)
paving=mat('Broomed cement','A6A399','CCC5AF',72,.003)
plaster=mat('Mineral limewash','D9CCAE','EFE5CE',22,.002)
slate=mat('Painted window joinery','365853','496A60',17,.001)
wood=mat('Dark meranti','624632','967354',9,.002)
zinc=mat('Galvanised metal','8E9E9F','C4C7BA',47,.001,.38,.55)
rim=mat('Section edge of galvanised metal','E3D6BA',rough=.42,metal=.24)
shadow=mat('Dark recess','263C39')
terra=[mat('Unglazed pantile',a,b,24,.0017) for a,b in
       [('78392B','A55438'),('804333','AE5B3D'),('783A29','A55939'),('884830','B76742')]]
# A single front bay of a terrace house, including the timber louvres and tiled eave.
box('Floor plate',(-3.48,.77,-.055),(2.40,1.56,.22),concrete,.021)
box('Five foot way tiled landing',(-3.48,.53,.071),(2.37,1.46,.07),paving,.014)
box('Terrace bay side return',(-4.50,.71,.96),(.14,1.48,1.74),plaster,.013)
box('Terrace facade',(-3.51,1.20,.90),(2.1,.15,1.61),plaster,.016)
box('Window recess',(-3.56,1.105,.92),(1.40,.09,.98),shadow,.015)
for j in range(3):
    x=-4.01+.45*j
    for k in range(8):
        sl=box('Tilted timber louvre',(x,1.025,.53+k*.109),(.405,.07,.106),slate,.009)
        sl.rotation_euler.x=-.32
    box('Louvre frame',(x-.221,.997,.92),(.036,.055,1.02),wood,.004)
# A shallow adjoining bay and stepped party-wall coping identify the terrace row.
party=C.section('Shared plaster party wall',[(-4.77,.11),(-4.60,.11),(-4.60,2.42),(-4.77,2.48)],-.09,1.66,plaster)
box('Clay coping',(-4.685,.80,2.477),(.20,1.82,.054),terra[0],.008)
# The neighbouring facade sits a bay further into the section.
box('Neighbouring bay wall',(-5.08,1.49,.91),(.85,.14,1.64),plaster,.009)
box('Neighbouring dark window',(-5.08,1.408,.93),(.50,.045,.78),slate,.008)
for x in (-5.25,-5.08,-4.91):
    box('Window grille',(x,1.37,.93),(.018,.024,.77),wood,.003)
for j in range(5):
    xx=-5.48+j*.165
    box('Neighbour tile', (xx,1.45,1.81+(xx+5.48)*.20),(.18,1.2,.093),terra[j%4],.013).rotation_euler.y=-.20
box('Neighbour floor',(-5.05,1.04,.09),(.84,.96,.13),concrete,.01)
# Enamel tile skirt and vent blocks under the eaves.
for j in range(16):
    box('Glazed skirting tile',(-4.5+j*.13,1.104,.19),(.125,.035,.17),slate,.004)
for j in range(10):
    box('Vent block slot',(-4.29+j*.153,1.108,1.535),(.088,.02,.042),shadow,.006)
for z in (.418,1.438):
    box('Window sill or header',(-3.56,1.016,z),(1.45,.18,.071),wood,.009)
for x in (-4.59,-2.46):
    box('Verandah post',(x,.02,.82),(.08,.09,1.49),wood,.008)
box('Eave rail',(-3.52,-.025,1.59),(2.28,.10,.11),wood,.01)
def roof_z(x):
    return 1.60+(-2.17-x)*.36
xmin,xmax=-4.90,-2.17
base=C.section('Roof battens and exposed soffit',[(xmin,roof_z(xmin)),(xmax,roof_z(xmax)),(xmax,roof_z(xmax)-.095),(xmin,roof_z(xmin)-.095)],-.27,1.74,wood)
# Overlapping clay pantiles have a curved pan, rolled lip and individual cut edge.
for row in range(6):
    xr=xmax-(xmax-xmin)*row/6
    xl=xr-(xmax-xmin)/6-.045
    for j in range(10):
        y=-.30+j*.205
        verts=[]
        for u in (0,.33,.66,1):
            x=xl+(xr-xl)*u
            for k in range(15):
                v=k/14
                h=.061*(.5+.5*math.cos(v*math.tau))**2+.012*u
                verts.append((x,y+.211*v,roof_z(x)+h+.018))
        faces=[(i*15+k,(i+1)*15+k,(i+1)*15+k+1,i*15+k+1) for i in range(3) for k in range(14)]
        tile=mesh('Overlapping clay pan',verts,faces,rng.choice(terra))
        for p in tile.data.polygons:p.use_smooth=True
        solid=tile.modifiers.new('Clay thickness','SOLIDIFY')
        solid.thickness=.021
for j in range(6):
    x=xmin+.2+j*.44
    C.beam('Meranti rafter tail',(x,-.30,roof_z(x)-.095),(x,1.55,roof_z(x)-.095),.068,.08,wood)
# U- and half-round conduit skins, exposing the active water on the camera-facing side.
def skin(name,rings,material,thickness=.035):
    count=len(rings[0])
    ob=mesh(name,sum(rings,[]),[(j*count+i,(j+1)*count+i,(j+1)*count+i+1,j*count+i+1)
              for j in range(len(rings)-1) for i in range(count-1)],material)
    for p in ob.data.polygons:p.use_smooth=True
    mod=ob.modifiers.new('Wall thickness','SOLIDIFY')
    mod.thickness=thickness
    return ob
gutterx=-2.13
skin('Half round eaves gutter', [[(gutterx+.122*math.cos(t*math.pi/24),y,1.594-.122*math.sin(t*math.pi/24))
    for t in range(25)] for y in (-.40,1.80)],zinc,.027)
for s in (-1,1):
    cylinder('Rolled gutter edge',(gutterx+s*.12,-.4,1.595),(gutterx+s*.12,1.80,1.595),.015,rim)
water=mat('Active teal water','179C96','42C9AE',9,.0009,.22,.12)
glint=mat('Reflection on flow','9ADBD0',rough=.25)
# One visible ribbon rides across the roof and into the front outlet.
roofline=[(x,-.194,roof_z(x)+.070) for x in (xmin+.04,-4.2,-3.5,-2.9,-2.18)]
C.strand('Rain in roof pan',roofline+[(gutterx,-.19,1.52),(gutterx,-.38,1.51)],.035,water)
route=[(gutterx,-.38,1.53),(gutterx,-.38,1.35),(-2.07,-.38,1.23),(-1.94,-.38,1.14),(-1.90,-.38,1.04),(-1.90,-.38,-.13)]
for i in range(1,14):
    a=math.pi*i/26
    route.append((-1.61-.29*math.cos(a),-.38,-.13-.29*math.sin(a)))
def open_pipe(points,rad):
    rings=[]
    for i,p in enumerate(points):
        tangent=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])).normalized()
        cross=tangent.cross(Vector((0,1,0)))
        rings.append([Vector(p)+rad*(math.cos(t*math.pi/28)*cross+math.sin(t*math.pi/28)*Vector((0,1,0))) for t in range(29)])
    return rings
skin('Cut downspout',open_pipe(route,.117),zinc,.033)
C.strand('Continuous downpipe flow',[(x,y-.012,z) for x,y,z in route],.068,water)
for z in (.92,.23):
    box('Downpipe strap',(-1.90,-.30,z),(.27,.07,.041),rim,.007)
# A sliced roadside U drain directly underneath the concrete five-foot way.
left,right=-1.62,2.50
def invert(x):return -.49-.038*(x-left)
for zoff,dep,height,cy,name in [(0,.92,.115,-.18,'Invert slab'),(.25,.12,.52,-.15,'Back wall'),(.025,.075,.15,-.61,'Sawn front lip')]:
    h0,h1=invert(left)+zoff,invert(right)+zoff
    C.section(name,[(left,h0-height/2),(right,h1-height/2),(right,h1+height/2),(left,h0+height/2)],cy-dep/2,cy+dep/2,concrete)
for x in (-1.46,-.47,.54,1.53,2.22):
    box('Joint between drain casts',(x,-.216,invert(x)+.268),(.011,.014,.42),shadow,.003)
for i in range(12):
    x=-1.78+i*.36
    box('Footway paving slab',(x,.18,.079),(.351,1.08,.13),paving,.012)
    if i in (2,6,10):
        for j in range(6):
            box('Drain grating slot',(x-.115+j*.045,-.18,.146),(.018,.24,.007),shadow,.007)
# Reflecting ripples in a shallow sheet with a thin readable front face.
def sheet(name,points,width,material):
    rings=[]
    for i,(x,y,z) in enumerate(points):
        tangent=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])).normalized()
        side=Vector((-tangent.y,tangent.x,0)).normalized()
        rings.append([Vector((x,y,z))+side*width*t+Vector((0,0,.008*math.sin(i*.89+t*2))) for t in (-1,-.65,0,.53,1)])
    return skin(name,rings,material,.045)
flow=[(left+(right-left)*i/48,-.39,invert(left+(right-left)*i/48)+.115) for i in range(49)]
sheet('Water in open concrete channel',flow,.22,water)
for j in range(25):
    x=rng.uniform(left,right-.23)
    y=rng.uniform(-.55,-.25)
    C.strand('Surface glint',[(x,y,invert(x)+.131),(x+.065,y-.003,invert(x+.065)+.132),(x+rng.uniform(.11,.21),y,invert(x+.11)+.130)],.004,glint)
# Outfall bends toward the viewer so the inside of the mouth reads in the same projection.
start=Vector((2.35,-.34,-.405))
end=Vector((3.48,-1.08,-.46))
axis=(end-start).normalized()
pipe=C.pipe(start,end,.30,'solid',concrete)
C.pipe(end-axis*.105,end+axis*.045,.345,'solid',paving)
out=[(2.24,-.39,-.53)]+[tuple(start.lerp(end,i/12)+Vector((0,0,-.128))) for i in range(13)]
for i in range(1,17):
    u=i/16
    out.append(tuple(end+Vector((.48*u,-.53*u,-.128-.43*u*u))))
sheet('Free sheet of outfall water',out,.128,water)
# Cut retaining wing and stone apron support the lip and receiving pool.
base_earth=mat('Compacted discharge bank','76533A','A28662',27,.012)
outline=[(2.72,-.36),(3.16,-1.37),(3.54,-1.92),(4.16,-2.07),(4.51,-1.74),(4.47,-1.32),(3.83,-.76),(3.63,-.16)]
verts=[(x,y,z) for z in (-1.20,-1.057) for x,y in outline]
n=len(outline)
mesh('Exposed stream bed',verts,[tuple(range(n)),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)],base_earth)
for j in range(54):
    t=rng.random()*math.tau
    r=rng.uniform(.84,1.15)
    x,y=3.93+.51*r*math.cos(t),-1.58+.33*r*math.sin(t)
    peb=C.sphere('River pebble',(x,y,-1.035),(rng.uniform(.023,.075),rng.uniform(.021,.063),rng.uniform(.019,.048)),concrete if j%4 else base_earth)
    peb.rotation_euler.z=t
# A shallow receiving basin with expanding rings under the lip.
basin=mat('Basin surface','326B69','498278',11,.002,.3)
C.sphere('Receiving water',(3.95,-1.6,-1.05),(.60,.37,.055),basin)
for rad in (.18,.31,.45):
    C.strand('Outfall ripple',[(3.95+rad*math.cos(i*math.tau/54),-1.60+.62*rad*math.sin(i*math.tau/54),-1.003) for i in range(55)],.009,water)
camera((-.20,.18,.69),(2.3,-14,3.8),14.20)
light('Exhibition softbox',(-4,-5,7),(-1,0,.2),1450,5.3)
light('Sky bounce',(4,-3,4),(1,0,0),690,5,(.78,.89,1))
light('Grazing afternoon sun',(1.8,2.3,5),(-1,0,.2),780,3.4)
still(HERE,'cover',sc)

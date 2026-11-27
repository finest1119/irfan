"""Product photograph of three lacquered rule leaves composing a K."""
from pathlib import Path
import sys, math
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE.parents[1]/'di-belakang-tabir/branding'))
from studio import C, scene, camera, light, still, cylinder, bevel
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=scene(1080,1080)
sc.render.film_transparent=True
sc.render.image_settings.color_mode='RGBA'
gold=C.material('Measuring rule lacquer','EDA922','FFCC52',42,.0007,.36)
clay=C.material('Clay red hinge caps','AD5B3F',metal=.30,rough=.32)
ink=C.material('Stamped ivory graduations','FFF4DB',rough=.55)
# Round ends on each slat. Separate hinge planes keep the boards visibly articulated.
def slat(a,b,r,y):
    dx,dz=b[0]-a[0],b[1]-a[1]
    ang=math.atan2(dz,dx)
    pts=[]
    for pt,start in ((a,ang+math.pi/2),(b,ang-math.pi/2)):
        for i in range(17):
            t=start+math.pi*i/16
            pts.append((pt[0]+r*math.cos(t),pt[1]+r*math.sin(t)))
    return bevel(C.section('Lacquered beech leaf',pts,y,y+.12,gold),.028)

slat((-.60,-.91),(-.60,.94),.16,-.07)
slat((-.60,.04),(.61,.92),.15,-.212)
slat((-.40,.15),(.66,-.88),.15,-.346)
# Place the second pin where the lower arm overlaps the tapered junction.
for x,z,y in ((-.59,.045,-.231),(-.40,.15,-.364)):
    cylinder('Pivot cap',(x,y+.016,z),(x,y-.012,z),.092,clay,48,.012)
    cylinder('Peened pivot centre',(x,y-.01,z),(x,y-.024,z),.039,clay,32,.006)
for z in (-.80,-.60,-.40,.41,.61,.81):
    C.box('Screen printed index',(-.676,-.076,z),(.135,.012,.039),ink,.006)
camera((0,0,0),(1.3,-10,1.1),3.12)
light('Broad softbox',(-3,-4,5),(0,0,0),430,3)
light('Edge strip',(2,0,3),(0,0,0),220,2)
still(HERE,'logo',sc)

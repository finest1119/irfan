"""Six-second Everyday Decoded cutaway. Run with Blender; see ../README.md."""
import argparse
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import cutlib as C


def garden(front, back):
    rng = random.Random(54)
    sod = C.polyhaven("aerial_grass_rock", 3)
    C.bounds("Lawn",1.05,12,front,back,0,.024,sod)
    blades, triangles = [], []
    for _ in range(7800):
        x,y = rng.uniform(1.05,8),rng.uniform(front-.012,back)
        h,w = rng.uniform(.022,.104),rng.uniform(.006,.014)
        j = len(blades)
        blades.extend([(x-w,y,.022),(x+w,y,.022),(x+rng.uniform(-.032,.03),y+.012,h+.022)])
        triangles.append((j,j+1,j+2))
    C.mesh("Uneven verge",blades,triangles,C.material("Fescue","556c37","939b55",8))
    white = C.material("Chalked fence paint","b6b3a0","e1dcc7",15,.006)
    for i in range(20):
        x = 1.59+i*.34
        picket = C.box("Fence paling",(x,back-.10,.46),(.245,.075,rng.uniform(.87,.94)),white,.016)
        picket.rotation_euler.y = rng.uniform(-.02,.02)
    for z in (.28,.67):
        C.box("Fence rail",(4.8,back,z),(6.69,.075,.077),white)


    # A clipped rosemary bush. Tiny leaf clusters break up the right-hand lawn.
    shrub=C.material("Garden foliage","415333","778256",9)
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
    C.mesh("Rosemary planting",v,fc,shrub)


def build():
    front,back = -2.15,2.65
    ground = C.ground((-12,12),(front,back),-2.46,
                      layers=(C.STRATA[3],("Rock",6.9,"4d4941","9e9585")),roots=False)
    for span in ((-12,-3.58),(3.56,12)):
        C.ground(span,(front,back),layers=C.STRATA[:3],seed=7)
    cover = C.ground((1.04,3.56),(front,back),layers=C.STRATA[:2])
    # Fine, discontinuous bedding in the exposed rock below the foundation.
    rng = random.Random(810)
    shale = C.material("Dark rock parting","544c43","7b7165",11,.012)
    for _ in range(62):
        x,z = rng.uniform(-6,6),rng.uniform(-6,-3.41)
        length = rng.uniform(.18,1.54)
        verts, faces = [], []
        for i in range(12):
            t = i/11
            h = z+.092*t+.014*math.sin(t*5+x)
            half = .012*math.sin(math.pi*t)*rng.uniform(.5,1.6)
            verts.extend([(x+length*t,front-.002,h-half),(x+length*t,front-.002,h+half)])
            if i:
                faces.append((2*i-2,2*i,2*i+1,2*i-1))
        ground.append(C.mesh("Sedimentary parting",verts,faces,shale))
    cement = C.weathering(C.polyhaven("concrete_floor_02",1.65),grade=-.04,reach=.46)
    mid = (front+back)/2
    for x in (-3.25,.84):
        C.foundation("footing",(x,mid,-2.335),(.66,back-front,.25),cement)
        C.foundation("wall",(x,mid,-.935),(.40,back-front,2.55),cement)
    C.foundation("slab",(-1.205,mid,-2.10),(3.69,back-front,.22),cement)
    C.foundation("wall",(-1.205,back-.10,-.84),(3.69,.20,2.35),cement)
    C.bounds("Sub-slab fines",-2.93,.52,front,back,-2.46,-2.2,C.material("Fines","706957","a29782",31))
    copper = C.material("Oxidised copper","8c6248",rough=.43,metal=.53)
    for z in (-.25,-.13):
        C.pipe((-3.02,back-.26,z),(.48,back-.26,z),.027,mat=copper)
    C.house_shell((-1.20,front,.80))
    metal = C.material("Galvanised steel","808b86",metal=.57,rough=.38)
    C.box("Service cabinet",(-2.1,back-.26,-.96),(.5,.14,.66),metal,.017)
    C.box("Service panel",(-2.1,back-.34,-.96),(.43,.023,.56),cement,.01)
    C.strand("Meter conduit",[(-2.1,back-.26,-.63),(-2.1,back-.26,.32)],.021,metal)
    C.strand("Roof gutter",[(1.35,front-.10,3.5),(1.35,back+.21,3.5)],.06,metal)
    C.strand("Downspout",[(1.35,1.87,3.5),(1.35,1.87,3.34),(1.13,1.87,3.08),
                          (1.13,1.87,.20),(1.29,1.87,.09)],.048,metal)
    garden(front,back)
    # Expose the lateral run in the gravel at the corner of the foundation.
    drain_y,drain_z = front+.07,-1.87
    C.pipe((1.12,drain_y,drain_z),(3.54,drain_y+.09,drain_z-.04),.19,
           "perforated",ribbed=True)
    def exposure(x,y,z,r):
        height = drain_z-(x-1.12)*.04/2.42
        return y < drain_y+.28+r and height-.15-r < z < height+.20+r
    C.gravel_bed((1.05,3.56),(front-.16,back),(-2.46,-1.39),.079,clearance=exposure)
    course = [(3.48,-.16),(3.30,-.32),(3.29,-.42),(3.14,-.49),(3.04,-.64),
              (2.85,-.72),(2.78,-.89),(2.58,-1.01),(2.52,-1.18),(2.34,-1.32),
              (2.29,-1.44),(2.17,-1.55),(2.11,-1.70)]
    path = [(x,front-.009-max(0,-z-1.3)*.36,z) for x,z in course]
    clay = next(obj for obj in cover if obj.name.partition(".")[0] == "Clay")
    C.seepage(path,clay.data.materials[0],width=.050,
              gaps=((.79,.84),(.91,.96)))
    cam = C.portrait_camera((.35,front,.24),11.5,9,9,frame=1)
    C.portrait_camera((1.32,front,-.67),8.05,15,8,camera=cam,frame=180)
    safe = C.check_framing([(1.14,drain_y,drain_z-.19),(3.47,drain_y,drain_z+.19),
                            (.84,front,-2.45)],ground)
    print(f"Safe subject extent: x={min(x for x,y in safe):.0f}..{max(x for x,y in safe):.0f}, "
          f"y={min(y for x,y in safe):.0f}..{max(y for x,y in safe):.0f}",flush=True)


def encoder():
    candidates = [os.environ.get("FFMPEG"),shutil.which("ffmpeg"),
                  Path.home()/"Downloads/affiliate-video-studio/node_modules/ffmpeg-static/ffmpeg"]
    for exe in candidates:
        if exe and Path(exe).is_file():
            def listing(option):
                return subprocess.run([exe,"-hide_banner",option],capture_output=True,text=True).stdout
            if " drawtext " in listing("-filters") and " libx264 " in listing("-encoders"):
                return str(exe)
    raise RuntimeError("Set FFMPEG to an executable with drawtext and libx264")


def encode(out, ff):
    # Run from repo root so the font path needs no shell or filtergraph escaping.
    font = "assets/fonts/Montserrat-Bold.ttf"
    if not (C.ROOT/font).is_file():
        raise FileNotFoundError(font)
    caption = (f"drawtext=fontfile={font}:text='under your house.':fontsize=31:"
               "fontcolor=white:borderw=1:bordercolor=black@0.55:shadowcolor=black@0.55:"
               "shadowx=1:shadowy=2:x=(w-tw)/2-w*0.035:y=h*0.535-th/2")
    def run(args):
        subprocess.run([ff,"-hide_banner","-loglevel","error","-y",*args],cwd=C.ROOT,check=True)
    files = out/".work/frames"
    with tempfile.TemporaryDirectory(dir=out/".work") as staging:
        movie = Path(staging)/"under_house_v2.mp4"
        still = Path(staging)/"still_v2.jpg"
        run(["-framerate","30","-start_number","1","-i",str(files/"%04d.png"),"-frames:v","180",
             "-vf",caption+",scale=out_color_matrix=bt709","-c:v","libx264","-crf","18",
             "-pix_fmt","yuv420p","-colorspace","bt709","-color_primaries","bt709",
             "-color_trc","bt709","-movflags","+faststart",str(movie)])
        run(["-i",str(files/"0120.png"),"-vf",caption,"-frames:v","1","-q:v","2",str(still)])
        movie.replace(out/movie.name)
        still.replace(out/still.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=HERE/"out")
    ap.add_argument("--still",type=int,choices=range(1,181),metavar="FRAME")
    args = ap.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    out = args.out.resolve()
    frames = out/".work/frames"
    frames.mkdir(parents=True,exist_ok=True)
    ff = None if args.still else encoder()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = C.render_settings()
    C.daylight()
    build()
    start = time.monotonic()
    for f in ([args.still] if args.still else range(1,181)):
        scene.frame_set(f)
        path = out/".work"/f"proof-{f}.png" if args.still else frames/f"{f:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    print(f"Cycles elapsed: {time.monotonic()-start:.2f} seconds",flush=True)
    if ff:
        encode(out,ff)


if __name__ == "__main__":
    main()

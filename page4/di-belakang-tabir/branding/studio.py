"""Shared still-life lighting, modelling primitives and final artwork export."""
import math
from pathlib import Path
import subprocess
import sys
import time

import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'pipeline/cutaway'))
import cutlib as C

def scene(width, height, samples=8):
    sc = C.render_settings('CPU', width, samples, 1)
    sc.render.resolution_y = height
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 3
    sc.cycles.max_bounces = 4
    sc.cycles.use_denoising = True
    sc.cycles.seed = 91
    sc.view_settings.view_transform = 'AgX'
    if not sc.world:
        sc.world = bpy.data.worlds.new('Studio ambient')
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (.59,.72,.83,1)
    bg.inputs[1].default_value = .3
    return sc

def camera(target, direction, width):
    data = bpy.data.cameras.new('Section camera')
    ob = bpy.data.objects.new(data.name,data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(target)+Vector(direction)
    ob.rotation_euler = (-Vector(direction)).to_track_quat('-Z','Y').to_euler()
    data.type, data.ortho_scale = 'ORTHO', width
    bpy.context.scene.camera = ob
    return ob

def light(name, loc, target, power, size, rgb=(1,.93,.83)):
    data = bpy.data.lights.new(name,'AREA')
    data.energy, data.shape, data.size, data.color = power, 'DISK', size, rgb
    ob = bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()

def bevel(ob, width):
    mod = ob.modifiers.new('Machined edge','BEVEL')
    mod.width, mod.segments = width, 3
    ob.modifiers.new('Planar normals','WEIGHTED_NORMAL')
    return ob

def cylinder(name, a, b, radius, mat, sides=48, edge=0):
    a,b = Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=radius,depth=(b-a).length,location=(a+b)/2)
    ob = bpy.context.object
    ob.name = name
    ob.rotation_euler = (b-a).to_track_quat('Z','Y').to_euler()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices)==4
    return bevel(ob,edge) if edge else ob

def still(path, kind, sc):
    draft = '--proof' in sys.argv
    sc.render.resolution_percentage = 45 if draft else 100
    if draft:
        sc.cycles.samples=3
    raw = path / ('.'+kind+'-render.png')
    sc.render.filepath = str(raw)
    tic = time.monotonic()
    bpy.ops.render.render(write_still=True)
    print('RENDER_SECONDS',kind,round(time.monotonic()-tic,2),flush=True)
    subprocess.run([str(ROOT/'.venv/bin/python'), str(Path(__file__).with_name('finish.py')),
                    str(raw),kind,'proof' if draft else 'final'],check=True)
    raw.unlink()

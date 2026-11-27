"""Metre-scale building blocks for portrait Blender cutaways. Front faces look toward -Y."""
import math
import random
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOTS = (ROOT / "assets/polyhaven", ROOT / "assets/cc0/polyhaven")


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


def mesh(name, verts, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def section(name, points, y0, y1, mat, cap=None):
    """Extrude a simple XZ outline with watertight, triangulated cut faces."""
    points = list(points)
    if len(points) < 3 or y1 <= y0:
        raise ValueError("Section needs an outline and increasing Y bounds")
    # CCW in x/z faces the viewer. Triangulate concave caps explicitly.
    if sum(x*z2-x2*z for (x,z),(x2,z2) in zip(points, points[1:]+points[:1])) < 0:
        points = points[::-1]
    count = len(points)
    triangles = tessellate_polygon([[Vector((x, z, 0)) for x, z in points]])
    faces = [tuple(t) for t in triangles]
    faces += [tuple(i+count for i in reversed(t)) for t in triangles]
    faces += [(i, i+count, (i+1)%count+count, (i+1)%count) for i in range(count)]
    obj = mesh(name, [(x,y,z) for y in (y0,y1) for x,z in points], faces, mat)
    if cap is not None:
        obj.data.materials.append(cap)
        for face in list(obj.data.polygons)[:2*len(triangles)]:
            face.material_index = 1
    return obj


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
    bpy.context.scene.collection.objects.link(obj)
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



def house_shell(origin=(0, 0, 0), width=4.46, depth=4.8, variant="suburban"):
    """Furnished half house, positioned by its front floor centre at floor finish level."""
    if variant not in {"suburban", "terrace"} or min(width, depth) <= 0:
        raise ValueError("Choose suburban or terrace and positive dimensions")
    F, B = -2.15, 2.65
    previous = set(bpy.context.scene.objects)
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
    for x in ((-3.34,.91) if variant == "suburban" else ()):
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
    if variant == "terrace":
        # Party walls, flush eaves, shallow pitch and masonry fire stops.
        ridge = (-1.20, 4.25)
        tips = [(-3.46, 3.53), (1.06, 3.53)]
        for x in (-3.38, .98):
            bounds("Masonry party wall", x-.12, x+.12, F, B, .34, 3.82, plaster)
    section("Rear gable", [tips[0], tips[1], ridge], B-.16, B, sage)
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
        beam("King post",(-1.2,y,3.66),(-1.2,y,ridge[1]-.16),.105,.105,ply)
        for x in (-2.44,.04):
            beam("Truss brace",(-1.2,y,3.71),(x,y,(ridge[1]+3.49)/2-.10),.085,.09,ply)
    group = bpy.data.objects.new(variant + " half house", None)
    bpy.context.scene.collection.objects.link(group)
    group.location = origin
    group.scale = (width / 4.46, depth / (B-F), 1)
    for obj in set(bpy.context.scene.objects) - previous - {group}:
        obj.parent = group
        obj.location += Vector((1.20, -F, -.80))
    return group


def bisect_solid(obj, point, normal, cap):
    """Keep the positive side of a local-space plane through a closed mesh; fill simple loops."""
    if obj.type != 'MESH' or Vector(normal).length < 1e-8:
        raise ValueError("Bisect needs a mesh and a nonzero local plane normal")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        cut = bmesh.ops.bisect_plane(
            bm, geom=[*bm.verts, *bm.edges, *bm.faces], plane_co=point,
            plane_no=Vector(normal).normalized(), dist=1e-6, clear_inner=True)
        rim = [edge for edge in cut["geom_cut"]
               if isinstance(edge, bmesh.types.BMEdge) and edge.is_boundary]
        if rim:
            index = obj.data.materials.find(cap.name)
            if index < 0:
                obj.data.materials.append(cap)
                index = len(obj.data.materials) - 1
            faces = bmesh.ops.holes_fill(bm, edges=rim, sides=0)["faces"]
            for face in faces:
                face.material_index = index
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    return obj


def _image(path):
    image = bpy.data.images.load(str(path), check_existing=True)
    w, h = image.size
    if not w or not h:
        raise ValueError(f"Unreadable image: {path.name}")
    if max(w, h) > 2048:
        ratio = 2048 / max(w, h)
        image.scale(max(1, round(w * ratio)), max(1, round(h * ratio)))
    return image


def polyhaven(asset, meters=2, fallback=None):
    """Box-project local 1K/2K colour and roughness/packed ARM maps in object metres."""
    if meters <= 0:
        raise ValueError("Texture size must be positive")
    for root in ASSET_ROOTS:
        folder = root / "textures" / asset
        for resolution in ("1k", "2k"):
            diffuse = folder / f"{asset}_diff_{resolution}.jpg"
            if diffuse.is_file():
                break
        else:
            continue
        break
    else:
        if fallback is not None:
            return fallback
        raise FileNotFoundError(f"No local 1K/2K colour map for {asset}")
    mat = material(asset, "888888")
    nodes, link = mat.node_tree.nodes, mat.node_tree.links.new
    shader = nodes.get("Principled BSDF")
    mapping = nodes.new("ShaderNodeVectorMath")
    mapping.operation = 'SCALE'
    mapping.inputs["Scale"].default_value = 1 / meters
    link(nodes.new("ShaderNodeTexCoord").outputs["Object"], mapping.inputs[0])

    def texture(path, data=False):
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = _image(path)
        if data:
            tex.image.colorspace_settings.name = 'Non-Color'
        tex.projection, tex.projection_blend = 'BOX', .17
        link(mapping.outputs[0], tex.inputs["Vector"])
        return tex.outputs["Color"]

    link(texture(diffuse), shader.inputs["Base Color"])
    for suffix in ("rough", "arm"):
        path = folder / f"{asset}_{suffix}_{resolution}.jpg"
        if path.is_file():
            rough = texture(path, data=True)
            if suffix == "arm":
                separate = nodes.new("ShaderNodeSeparateColor")
                link(rough, separate.inputs[0])
                rough = separate.outputs["Green"]
            link(rough, shader.inputs["Roughness"])
            break
    return mat


def weathering(mat, grade=0, reach=.40, strength=.67):
    """Overlay a broken damp/grime band on the existing colour at a world-space elevation."""
    nodes, link = mat.node_tree.nodes, mat.node_tree.links.new
    pos = nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    z = nodes.new("ShaderNodeSeparateXYZ")
    link(pos, z.inputs[0])
    noise = nodes.new("ShaderNodeTexNoise")
    link(pos, noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = 7
    def math_node(op, socket, value):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        link(socket, n.inputs[0])
        if isinstance(value, (float, int)):
            n.inputs[1].default_value = value
        else:
            link(value, n.inputs[1])
        return n.outputs[0]
    zoff = math_node('SUBTRACT', z.outputs["Z"], grade)
    dist = math_node('ABSOLUTE', zoff, 0)
    band = math_node('MULTIPLY', dist, -1/reach)
    mask = math_node('ADD', band, math_node('MULTIPLY', noise.outputs["Fac"], 1.9))
    weight = math_node('MULTIPLY', mask, strength)
    weight.node.use_clamp = True
    base = nodes.get("Principled BSDF").inputs["Base Color"]
    mix = nodes.new("ShaderNodeMixRGB")
    if base.is_linked:
        link(base.links[0].from_socket, mix.inputs[1])
    else:
        mix.inputs[1].default_value = base.default_value
    mix.inputs[2].default_value = color("443923")
    link(weight, mix.inputs[0])
    link(mix.outputs[0], base)
    return mat


def foundation(kind, center, size, mat=None, grade=0):
    """Cast slab, wall or spread footing; centre and XYZ dimensions in metres."""
    if kind not in {"slab", "wall", "footing"} or min(size) <= 0:
        raise ValueError("Expected slab, wall or footing with positive dimensions")
    if mat is None:
        try:
            concrete = polyhaven("concrete_floor_02")
        except FileNotFoundError:
            concrete = material("Cast concrete", "938f85", "bab6a9", 18, .012)
        mat = weathering(concrete, grade)
    return box("Cast " + kind, center, size, mat, .012 if kind == "wall" else .018)


# Ordered from the surface down. Thicknesses refer to undisturbed ground.
STRATA = (("Topsoil", .35, "38261a", "70523a"), ("Clay", 1.06, "845139", "ca895c"),
          ("Sand", 1.12, "977451", "d3b58a"), ("Gravel", .78, "655a4c", "a49277"),
          ("Rock", 3.9, "57554e", "969284"))


def _soil_material(name, dark, light):
    try:
        soil = polyhaven("excavated_soil_wall", 1.75)
    except FileNotFoundError:
        return material(name, dark, light, scale=9, grain=.032)
    n, link = soil.node_tree.nodes, soil.node_tree.links.new
    shader = n.get("Principled BSDF")
    base = shader.inputs["Base Color"]
    bw = n.new("ShaderNodeRGBToBW")
    link(base.links[0].from_socket, bw.inputs[0])
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9
    noise.inputs["Detail"].default_value = 4
    link(n.new("ShaderNodeTexCoord").outputs["Object"], noise.inputs[0])
    variation = n.new("ShaderNodeMath")
    variation.operation = 'MULTIPLY'
    link(noise.outputs["Fac"], variation.inputs[0])
    link(bw.outputs[0], variation.inputs[1])
    ramp = n.new("ShaderNodeValToRGB")
    for elem, value, pos in zip(ramp.color_ramp.elements, (dark, light), (.012,.075)):
        elem.position, elem.color = pos, color(value)
    link(variation.outputs[0], ramp.inputs[0])
    link(ramp.outputs[0], base)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .26
    bump.inputs["Distance"].default_value = .048
    link(noise.outputs["Fac"], bump.inputs["Height"])
    link(bump.outputs[0], shader.inputs["Normal"])
    return soil


def ground(xspan, yspan, surface=0, layers=STRATA, seed=7, relief=.09, roots=True, grains=40):
    """Layer tuples (name, thickness, dark, light). Shared contacts; grains per square metre."""
    x0, x1 = xspan
    front, back = yspan
    if x1 <= x0 or back <= front or not layers or any(layer[1] <= 0 for layer in layers):
        raise ValueError("Ground needs positive extents and layer thicknesses")
    rng = random.Random(seed)
    phase = random.Random(seed).uniform(0, 12)
    count = max(2, math.ceil((x1-x0)/.085))
    xs = [x0 + (x1-x0)*i/count for i in range(count+1)]
    upper = [surface]*len(xs)
    level = surface
    objects = []
    for k, (name, thick, dark, light) in enumerate(layers):
        level -= thick
        amplitude = min(relief, thick*.23, layers[min(k+1, len(layers)-1)][1]*.23)
        lower = [level + amplitude*(.82*math.sin(1.7*x+phase+k) + .4*math.sin(5*x-k)
                                    + .19*math.sin(14*x+phase)) for x in xs]
        soil = _soil_material(name, dark, light)
        # Strip topology keeps a fractured face local to the nearest sample.
        # A tessellated n-gon would drag tiny edge chips across the entire cut.
        verts, faces = [], []
        rows = max(2, math.ceil(thick/.25)) + 1
        for side in (front,back):
            for j in range(rows):
                for x,top,bottom in zip(xs,upper,lower):
                    z = bottom + (top-bottom)*j/(rows-1)
                    chip = .012*(1+math.sin(7*x+3*z)*math.cos(5*z-x))
                    verts.append((x,side+(chip if side==front else 0),z))
        stride = len(xs)
        back_offset = rows*stride
        for j in range(rows-1):
            for i in range(count):
                a = j*stride+i
                face = (a,a+1,a+stride+1,a+stride)
                faces.extend([face, tuple(v+back_offset for v in reversed(face))])
        rim = list(range(stride)) + [j*stride+count for j in range(1,rows)]
        rim += list(range(back_offset-2,back_offset-stride-1,-1))
        rim += [j*stride for j in range(rows-2,0,-1)]
        for a,b in zip(rim,rim[1:]+rim[:1]):
            faces.append((b,a,a+back_offset,b+back_offset))
        objects.append(mesh(name,verts,faces,soil))
        verts, faces = [], []
        for _ in range(int(grains*(x1-x0)*thick)):
            i = rng.randrange(count)
            t = rng.random()
            x = xs[i] + (xs[i+1]-xs[i])*t
            lo = lower[i]*(1-t)+lower[i+1]*t
            hi = upper[i]*(1-t)+upper[i+1]*t
            z = rng.uniform(lo, hi)
            r = rng.uniform(.004,.031) * (1.7 if name == "Gravel" else 1)
            j = len(verts)
            verts.extend([(x-r,front-.001,z), (x,front-.007,z-r*.35),
                          (x+r,front-.002,z+r*.13), (x-r*.2,front-.002,z+r*.49)])
            faces.append((j,j+1,j+2,j+3))
        if faces:
            objects.append(mesh(name+" inclusions", verts, faces, material(name+" grains", dark, light, 18)))
        upper = lower
    if roots:
        root = material("Root fibres", "8a7250")
        for _ in range(round((x1-x0)*7)):
            x = rng.uniform(x0, x1)
            length = rng.uniform(.06, .36)
            dx = rng.uniform(-.18, .18)
            mid = (x+dx*.35, front-.007, surface-length*.46)
            strand("Root", [(x,front-.004,surface), mid,
                            (x+dx,front-.004,surface-length)], .004, root)
            strand("Root hair", [mid,(mid[0]-.055,front-.005,mid[2]-.075)], .002, root)
    return objects


def pipe(start, end, radius=.15, style="solid", mat=None, ribbed=False):
    """Open-bore pipe between two points. 'solid' has an unperforated smooth wall."""
    if style not in {"solid", "perforated", "corrugated"} or radius <= 0:
        raise ValueError("Invalid pipe style or radius")
    axis = Vector(end)-Vector(start)
    if axis.length < 1e-5:
        raise ValueError("Pipe endpoints coincide")
    mat = mat or material("Mineral-dusted HDPE", "384340", "697871", 26, .002, .43)
    bore = material("Inner sleeve", "151b1b", rough=.86)
    segs = 48
    bays = max(1, round(axis.length/(1.55*radius)))
    rings = 1 if style == "solid" and not ribbed else bays*12
    verts, faces, inner_faces = [], [], []
    for skin in (0, 1):
        for j in range(rings+1):
            ridges = .055*(1+math.cos(j*math.pi/2)) if ribbed or style=="corrugated" else 0
            r = radius*(.82 if skin else 1+ridges)
            for i in range(segs):
                angle = math.tau*i/segs
                verts.append((axis.length*j/rings, -r*math.cos(angle), r*math.sin(angle)))

    def index(k, j, i):
        return (k*(rings+1)+j)*segs + i%segs

    def slot(j, i):
        # Offset opposite rows so the dark bore is visible through each near opening.
        i %= segs
        shift = 6 if 12 < i < 36 else 0
        return (style=="perforated" and 0 < j < rings-1 and
                (j+shift)%12 in range(3,10) and (i+2)%16 < 5)
    for j in range(rings):
        for i in range(segs):
            if slot(j,i):
                continue
            corners = [(j,i), (j+1,i), (j+1,i+1), (j,i+1)]
            outer = [index(0,*c) for c in corners]
            inner = [index(1,*c) for c in corners]
            faces.extend((outer, inner[::-1]))
            inner_faces.append(len(faces)-1)
            for k, exposed in enumerate((slot(j,i-1), j==rings-1 or slot(j+1,i),
                                         slot(j,i+1), j==0 or slot(j-1,i))):
                if exposed:
                    l = (k+1)%4
                    faces.append((outer[l],outer[k],inner[k],inner[l]))
    if style == "perforated":
        # Omitted cells leave orphan vertices inside each slot. Compact the
        # skins so joined/edited section meshes have only connected geometry.
        used = sorted({v for face in faces for v in face})
        index_map = {old: new for new, old in enumerate(used)}
        verts = [verts[i] for i in used]
        faces = [tuple(index_map[v] for v in face) for face in faces]
    obj = mesh(style+" pipe", verts, faces, mat)
    obj.data.materials.append(bore)
    for i in inner_faces:
        obj.data.polygons[i].material_index = 1
    obj.location = start
    obj.rotation_euler = Vector((1,0,0)).rotation_difference(axis.normalized()).to_euler()
    return obj


def gravel_bed(xspan, yspan, zspan, stone=.08, seed=42, clearance=None):
    """Washed stone with a solid matrix behind the exposure. clearance(x,y,z,r) reserves voids."""
    rng = random.Random(seed)
    x0, x1 = xspan
    y0, y1 = yspan
    z0, z1 = zspan
    if min(x1-x0,y1-y0,z1-z0,stone) <= 0:
        raise ValueError("Gravel bed dimensions must be positive")
    face_depth = min(stone*6, (y1-y0)*.8)
    matrix = material("Stone bed matrix", "48453e", "948e80", 31)
    bounds("Recessed aggregate bed", x0,x1,y0+face_depth,y1,z0,z1,matrix)
    count = math.ceil((x1-x0)*(z1-z0) / stone**2 * 2.4)
    piles = [([],[]) for _ in range(5)]
    for _ in range(count):
        r = rng.uniform(.44,1.27)*stone
        x,y,z = rng.uniform(x0,x1),rng.uniform(y0,y0+face_depth),rng.uniform(z0,z1)
        if clearance and clearance(x,y,z,r):
            continue
        v,f = rng.choice(piles)
        j = len(v)
        phase, height = rng.random()*math.tau, r*rng.uniform(.58,1.03)
        for ring, level in enumerate((-.74,0,.76)):
            for k in range(6):
                a = phase+k*math.pi/3+ring*.21
                rad = r*rng.uniform(.72,1.13)*(1 if ring==1 else .64)
                v.append((x+rad*math.cos(a),y+rad*math.sin(a),z+level*height))
        f.extend([tuple(j+k for k in reversed(range(6))),tuple(j+12+k for k in range(6))])
        for offset in (j,j+6):
            for k in range(6):
                l = (k+1)%6
                f.append((offset+k,offset+l,offset+6+l,offset+6+k))
    for (v,f),tint in zip(piles,("968f7d","756f62","a9a798","bdb39e","676962")):
        if f:
            mesh("Washed stone",v,f,material("Chipped aggregate",tint,"625d53",25,.006))


def seepage(path, soil, width=.04, gaps=((.68,.75),(.88,.94)), period=55, seed=17):
    """Wet face in world XYZ. Gaps are fractions of path length buried behind gravel."""
    points = [Vector(p) for p in path]
    lengths = [(b-a).length for a,b in zip(points,points[1:])]
    if not lengths or min(lengths) <= 0 or min(period, width) <= 0:
        raise ValueError("Seepage needs distinct path points, positive width and period")
    total = sum(lengths)
    def at(t):
        d = t*total
        for i, length in enumerate(lengths):
            if d <= length or i==len(lengths)-1:
                return points[i].lerp(points[i+1], min(d/length, 1))
            d -= length
    def buried(t):
        return any(a <= t <= b for a,b in gaps)
    rng = random.Random(seed)
    wet = soil.copy()
    wet.name = "Damp " + soil.name
    nodes, link = wet.node_tree.nodes, wet.node_tree.links.new
    shader = nodes.get("Principled BSDF")
    base = shader.inputs["Base Color"]
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = .57
    multiply.inputs[2].default_value = color("473c32")
    if base.is_linked:
        link(base.links[0].from_socket, multiply.inputs[1])
    else:
        multiply.inputs[1].default_value = base.default_value
    link(multiply.outputs[0],base)
    film = material("Reflected daylight in seep", "677e7c", rough=.19, metal=.32)
    glint = material("Water glints", "b3d3cf", rough=.18, metal=.21)
    # Widely feathered, irregular damp subgrade and a much narrower surface film.
    scene = bpy.context.scene
    for margin, surface, offset in ((1.20,wet,.002),(.20,film,.004)):
        v, faces, spine = [], [], []
        for j in range(97):
            t = j/96
            p = at(t)
            tangent = at(min(1,t+.004))-at(max(0,t-.004))
            across = Vector((-tangent.z,0,tangent.x)).normalized()
            p.y -= offset
            w = width*margin*(.40+.54*math.sin(math.pi*t)+rng.uniform(0,.52))
            v.extend([p-across*w*rng.uniform(.7,1.2),p+across*w])
            spine.extend([p.copy(),p.copy()])
            if j and not buried((j-.5)/96):
                faces.append((2*j-2,2*j-1,2*j+1,2*j))
        ribbon = mesh(surface.name,v,faces,surface)
        if surface == wet:
            ribbon.shape_key_add(name="Damp")
            dry = ribbon.shape_key_add(name="Drying edges")
            for i, vertex in enumerate(dry.data):
                vertex.co = vertex.co.lerp(spine[i],.49)
            for frame in range(scene.frame_start, scene.frame_end+period, period):
                for delta, value in ((0,.85),(period*.56,0)):
                    dry.value = value
                    dry.keyframe_insert(data_path="value", frame=frame+delta)
    for i in range(3):
        drop = sphere("Seep highlight",points[0],(1,1,1),glint)
        begin = scene.frame_start-period+i*period/3
        while begin <= scene.frame_end:
            for j in range(41):
                t = j/40
                drop.location = at(t)+Vector((0,-.012,0))
                fade = 0 if buried(t) else min(1,t*12,(1-t)*12)
                drop.scale = Vector((.63,.26,.28))*width*fade
                drop.keyframe_insert(data_path="location",frame=begin+t*(period-.1))
                drop.keyframe_insert(data_path="scale",frame=begin+t*(period-.1))
            begin += period


# Fill energy, key energy, key tint (linear RGB), exposure, background haze.
GRADES = {
    "ED": (.80, 1550, (1,.94,.83), .18, 0),
    "WJH": (.44, 1900, (.72,.83,1), -.32, 0),
    "SME": (.58, 1800, (1,.74,.50), .03, 0),
    "di-belakang-tabir": (.85, 1400, (1,.82,.62), .12, .26),
    "kita-buat-dia": (.77, 1550, (1,.78,.57), .10, .21),
}


def daylight(page="ED", rotation=1.15):
    """Use local HDR daylight; the tropical grades soften the distant sky with a humid veil."""
    scene = bpy.context.scene
    fill, energy, tint, exposure, haze = GRADES[page]
    world = bpy.data.worlds.new(page+" daylight")
    scene.world = world
    world.use_nodes = True
    n, link = world.node_tree.nodes, world.node_tree.links.new
    bg = n.get("Background")
    files = [p for root in ASSET_ROOTS for sub in ("hdri","hdris")
             for p in sorted((root/sub).glob("*")) if p.suffix.lower() in (".hdr",".exr")]
    if files:
        env = n.new("ShaderNodeTexEnvironment")
        env.image = _image(files[0])
        mapping = n.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value.z = rotation
        link(n.new("ShaderNodeTexCoord").outputs["Generated"],mapping.inputs[0])
        link(mapping.outputs[0],env.inputs[0])
    else:
        env = n.new("ShaderNodeTexSky")
    blend = n.new("ShaderNodeMixRGB")
    blend.inputs[0].default_value = haze
    blend.inputs[2].default_value = color("ddd5bb")
    link(env.outputs[0],blend.inputs[1])
    link(blend.outputs[0],bg.inputs[0])
    bg.inputs[1].default_value = fill
    if files:
        # Parallel orthographic rays otherwise sample a single brown ground pixel.
        # Screen coordinates subtend a small upward-facing window of the actual HDRI.
        window = n.new("ShaderNodeTexCoord").outputs["Window"]
        scale = n.new("ShaderNodeVectorMath")
        scale.operation = 'MULTIPLY'
        scale.inputs[1].default_value = (.42, .72, 0)
        link(window, scale.inputs[0])
        xyz = n.new("ShaderNodeSeparateXYZ")
        link(scale.outputs[0], xyz.inputs[0])
        direction = n.new("ShaderNodeCombineXYZ")
        direction.inputs["Y"].default_value = -1
        link(xyz.outputs["X"], direction.inputs["X"])
        link(xyz.outputs["Y"], direction.inputs["Z"])
        horizon = n.new("ShaderNodeVectorMath")
        horizon.operation = 'ADD'
        horizon.inputs[1].default_value = (-.28,0,-.40)
        link(direction.outputs[0],horizon.inputs[0])
        sky = n.new("ShaderNodeTexEnvironment")
        sky.image = env.image
        link(horizon.outputs[0],sky.inputs[0])
        mist = n.new("ShaderNodeMixRGB")
        mist.inputs[0].default_value = .22+haze
        mist.inputs[2].default_value = color("bdd0cf")
        link(sky.outputs[0],mist.inputs[1])
        camera_sky = n.new("ShaderNodeMixRGB")
        link(n.new("ShaderNodeLightPath").outputs["Is Camera Ray"],camera_sky.inputs[0])
        link(blend.outputs[0],camera_sky.inputs[1])
        link(mist.outputs[0],camera_sky.inputs[2])
        link(camera_sky.outputs[0],bg.inputs[0])
    key = bpy.data.lights.new("Daylight through section",'AREA')
    key.energy, key.color, key.shape, key.size = energy,tint,'DISK',7
    obj = bpy.data.objects.new(key.name,key)
    scene.collection.objects.link(obj)
    obj.location = (-3,-8,8)
    obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = exposure
    return world


def render_settings(device="CPU", width=540, samples=8, frames=180):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    if device == "OPTIX":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.refresh_devices()
        if not any(d.type == 'OPTIX' for d in prefs.devices):
            raise RuntimeError("OptiX requested but no OptiX device was enumerated")
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
    elif device != "CPU":
        raise ValueError("Choose CPU or OPTIX")
    scene.cycles.device = 'CPU' if device == "CPU" else 'GPU'
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 4
    scene.render.use_motion_blur = False
    scene.render.use_persistent_data = device=="CPU"
    scene.render.resolution_x,scene.render.resolution_y = width,round(width*16/9)
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.fps, scene.render.fps_base = 30, 1
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 12
    return scene


def portrait_camera(target, height, azimuth=10, elevation=9, camera=None, frame=None):
    """Metre-based vertical field of view; angles in degrees. Optionally key the pose."""
    scene = bpy.context.scene
    if height <= 0:
        raise ValueError("Vertical field of view must be positive")
    width = min(scene.render.resolution_x, scene.render.resolution_y)
    scene.render.resolution_x, scene.render.resolution_y = width, round(width*16/9)
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    if camera is None:
        data = bpy.data.cameras.new("Portrait section")
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.sensor_fit = 'VERTICAL'
    camera.data.ortho_scale = height
    az, el = math.radians(azimuth), math.radians(elevation)
    direction = Vector((math.cos(el)*math.sin(az),-math.cos(el)*math.cos(az),math.sin(el)))
    camera.location = Vector(target)+direction*24
    camera.rotation_euler = (-direction).to_track_quat('-Z','Y').to_euler()
    if frame is not None:
        camera.keyframe_insert(data_path="location",frame=frame)
        camera.keyframe_insert(data_path="rotation_euler",frame=frame)
        camera.data.keyframe_insert(data_path="ortho_scale",frame=frame)
    return camera


def check_framing(subject, lower_ground, frames=None):
    """Check safe-crop anchors and ray-test actual ground at the bottom of the portrait."""
    scene = bpy.context.scene
    original = scene.frame_current
    ground_set = set(lower_ground)
    samples = []
    try:
        for f in (frames if frames is not None else range(scene.frame_start,scene.frame_end+1)):
            scene.frame_set(f)
            cam = scene.camera
            deps = bpy.context.evaluated_depsgraph_get()
            for point in subject:
                u,v,d = world_to_camera_view(scene,cam,Vector(point))
                y = (1-v)*1920
                if not (0 <= u <= 1 and 285 <= y <= 1635 and d>0):
                    raise ValueError(f"Frame {f}: subject outside safe crop ({u*1080:.1f}, {y:.1f})")
                samples.append((u*1080,y))
            corners = cam.data.view_frame(scene=scene)
            xmax, ymax = max(v.x for v in corners), max(v.y for v in corners)
            for x in (-.98,0,.98):
                start = cam.matrix_world @ Vector((x*xmax,-.98*ymax,0))
                ray = cam.matrix_world.to_quaternion() @ Vector((0,0,-1))
                hit, _, _, _, obj, _ = scene.ray_cast(deps,start,ray)
                if not hit or obj.original not in ground_set:
                    raise ValueError(f"Frame {f}: lower edge misses ground at x={x}")
    finally:
        scene.frame_set(original)
    return samples

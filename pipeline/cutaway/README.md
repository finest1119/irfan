# Blender cutaway toolkit

[Watch the six-second ED preview](examples/out/under_house_v2.mp4) · [Frame 120](examples/out/still_v2.jpg) · [Render report](REPORT.md)

Use `cutlib.py` from Blender's Python. Dimensions are in metres. Z is up, X runs across the section, and the camera looks into the cut from negative Y. A single camera can travel between subjects within the same world. The library adds geometry to the active scene. Scene reset, animation timing, text and delivery belong to the calling script.

## A new scene in 26 lines

Save the following as `pipeline/cutaway/examples/workshop.py`. This section shows a conduit embedded just inside the face of a workshop floor. The orange cap marks where the concrete was cut.

```python
import sys
from pathlib import Path
import bpy

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
import cutlib as C

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = C.render_settings(device="CPU", width=540, samples=8, frames=90)
C.daylight("SME")
ground = C.ground((-7, 7), (0, 5), surface=-.45, seed=31)
concrete = C.weathering(C.polyhaven("concrete_floor_02"), grade=-.42)
edge = C.material("Exposed aggregate", "ac7958", "c99a79", scale=32)
slab = C.box("Workshop floor", (0, 2, -.225), (9, 4.8, .45), concrete)
C.bisect_solid(slab, (0, -2, 0), (0, 1, 0), edge)
C.pipe((-1.1, -.02, -.23), (1.1, -.02, -.23), .075, "corrugated")
cam = C.portrait_camera((0, 0, -.38), 5.8, azimuth=6, frame=1)
C.portrait_camera((.13, 0, -.42), 5.2, azimuth=12, camera=cam, frame=90)
C.check_framing([(-1.1, 0, -.23), (1.1, 0, -.23)], ground)

scene.frame_set(45)
out = here / "out" / ".work"
out.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(out / "workshop.png")
bpy.ops.render.render(write_still=True)
```

Run from the repo root. Substitute `blender` for the macOS executable on other systems.

```sh
B=/Applications/Blender.app/Contents/MacOS/Blender
mkdir -p pipeline/cutaway/examples/out/.work
"$B" -b --factory-startup --python-exit-code 1 -P pipeline/cutaway/examples/workshop.py \
  >pipeline/cutaway/examples/out/.work/workshop.log 2>&1
```

## Building blocks

| Helper | How to use it |
| --- | --- |
| `section(name, points, y0, y1, mat, cap)` | Extrude a simple XZ outline between two Y planes. The end faces get the cap material. Concave outlines are triangulated. |
| `bisect_solid(obj, point, normal, cap)` | Cut a closed mesh in its local coordinates, retaining the positive half-space. The fill handles simple boundary loops. Use the pipe builder for hollow pipe ends. |
| `ground(xspan, yspan, surface, layers, seed, relief, roots, grains)` | Build topsoil, clay, sand, gravel and rock. Override `layers` with surface-first tuples of name, thickness in metres and two sRGB hex colours. Contacts are shared, the front face is chipped and triangulated by the renderer, and `grains` controls inclusions per square metre. Returns the bodies and grain meshes for camera checks. |
| `foundation(kind, center, size, mat, grade)` | Cast a concrete `slab`, `wall` or `footing`. `size` is XYZ. Pass a shared material for continuous staining across pieces. |
| `house_shell(origin, width, depth, variant)` | Choose `suburban` for lapped siding, side windows and a gabled roof, or `terrace` for solid party walls, shallow roof and flush eaves. Place the front-centre of the finished floor at `origin`. The returned parent moves the shell and interior together. |
| `pipe(start, end, radius, style, mat, ribbed)` | `solid` is continuous-wall pipe, `perforated` cuts staggered through-slots, and `corrugated` adds ribs. Combine `"perforated", ribbed=True` for a slotted drain. The bore, rims and hole walls are geometry. |
| `gravel_bed(xspan, yspan, zspan, stone, seed, clearance)` | `stone` is nominal stone radius. The optional callback `clearance(x,y,z,r)` excludes stones from a pipe or inspection opening. The rear matrix begins six stone radii behind the front, or at 80% depth for shallow beds. Place the exposed pipe in front of the matrix. |
| `seepage(path, soil, width, gaps, period)` | Supply world XYZ points just in front of a soil section, its material, a width scale in metres and a period in frames. Gaps such as `((.65,.73),)` omit sections by fraction of path length. Place them where stones interrupt the flow. The damp edge changes width as glints travel downhill. Set the timeline first. |
| `material`, `weathering`, `polyhaven` | Build mottled surfaces, add a damp contact band around a world Z elevation, or box-project local texture maps at a chosen size in metres. `weathering` modifies its material. Use `mat.copy()` for isolated wear. |
| `portrait_camera`, `check_framing` | Specify the vertical field of view in metres, then key the camera and its scale on the same timeline. Supply subject extremities in world coordinates and the ground meshes. Each sampled frame must contain the points inside x 0–1080, y 285–1635 and hit ground at the lower left, centre and right edges. Use every frame for delivery. |

Extend the ground laterally and below the camera's ending view before zooming out. Put the narrative subject across the cut plane so the viewer sees its profile. Place captions after the camera pass at a point that stays clear along the entire move. For an episode integration, call the geometry helpers from the existing builder and use the episode renderer's camera, timing and caption system.

## Page grades

Pass the preset key to `daylight()`. Each preset sets the AgX exposure, environment strength and key-light colour. The Malaysian looks also mix a warm humid veil into the distant HDR sky.

| Key | Page | Lighting |
| --- | --- | --- |
| `WJH` | What Just Happened | Cooler directional key, reduced fill and a darker exposure for news. |
| `ED` | Everyday Decoded | Bright neutral daylight, gentle warm key and open shadows for material detail. |
| `SME` | Self-Made Engineer | Amber workshop key and less fill to bring out tool marks. |
| `di-belakang-tabir` | Di Belakang Tabir | Bright tropical daylight with soft humid distance for outdoor systems. |
| `kita-buat-dia` | Kita Buat Dia | Warmer workshop daylight with a slightly lighter haze for Bengkel Din. |

## Rendering and rebuilding the ED preview

| Setting | Mac preview | RTX 3050 laptop, 4 GB |
| --- | --- | --- |
| Invocation | `render_settings("CPU", 540, 8)` | Start with `render_settings("OPTIX", 540, 8)`. Try `width=1080, samples=16` for delivery after a representative frame fits. |
| Cycles | CPU, adaptive samples, 4 bounces, OpenImageDenoise | Enumerated OptiX GPUs, adaptive samples, 4 bounces, OpenImageDenoise |
| Memory | Persistent scene data between frames | Persistent data off. Render one Blender process at a time and reuse materials. |

The loaders search `assets/polyhaven` and `assets/cc0/polyhaven`. Colour maps prefer 1K, then 2K. Roughness comes from a separate map or the green channel of packed ARM. HDR and colour/roughness images are capped at 2048 pixels on the longest edge. The example uses repo-local CC0 assets and Montserrat Bold.

For one uncaptioned lighting proof, append `-- --still 120` to the Blender command below, before the log redirect. A full run writes 180 source PNGs to `examples/out/.work/frames/` and burns the caption into both deliverables. Run from the repo root.

```sh
B=/Applications/Blender.app/Contents/MacOS/Blender
mkdir -p pipeline/cutaway/examples/out/.work
"$B" -b --factory-startup --python-exit-code 1 \
  -P pipeline/cutaway/examples/under_house_v2.py \
  >pipeline/cutaway/examples/out/.work/render.log 2>&1
```

The encoder checks for both drawtext and libx264. It checks `FFMPEG`, the executable on PATH, then the Mac's known ffmpeg-static installation. To select a different binary, set `FFMPEG` inline on the render command. The finished files are `examples/out/under_house_v2.mp4` and `examples/out/still_v2.jpg`.

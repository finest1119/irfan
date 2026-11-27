# Under your house · cutaway v2

[Six-second preview](examples/out/under_house_v2.mp4) · [Captioned frame 120](examples/out/still_v2.jpg) · [Approved v1 still](../../page3/tests/cutaway_test/out/still.jpg)

## Changes from the approved test

| v1 observation | v2 implementation |
| --- | --- |
| Empty space below the freestanding base | The kitchen, trusses and basement remain recognisable. A continuous six-degree arc pushes down toward the footing. The section extends beyond both sides of the camera and into the rock below the bottom edge. |
| The pipe mouth was clearer than its side holes | A lateral drain run lies across the exposure. Near-side slots have modeled rims, a recessed dark bore and staggered openings on the far side. Stone above and below the inspection pocket keeps the pipe in context. |
| Uniform blue seepage line | The damp margin and reflective centre vary independently in width. The wet area uses the soil's own texture, darkens and changes width over time. Moving glints disappear at two interruptions in the stone. |
| Clean, regular soil and foundation edges | Five strata share undulating contacts. Photographed soil detail, chipped cut faces, embedded grains, small roots and rock partings break up the section. The concrete darkens in irregular patches where the wall meets grade. Garden planting, a roof drain and a service cabinet give the viewer familiar scale cues. |

The example imports its geometry from the new toolkit. The standalone runner uses one animated camera with a separate FFmpeg caption pass. The v2 episode renderer and one-shot workflows keep their existing entry points.

## Render and verification

| Measurement | Observed result |
| --- | --- |
| Render | **7 min 18.63 s**, averaging **2.437 s/frame** for all 180 source PNGs. Includes Cycles, denoising and writes. The measurement excludes scene construction and FFmpeg encoding. |
| Machine and settings | Apple M2 Pro, Blender 5.3.0, Cycles CPU, 8 samples, OpenImageDenoise, 4 bounces, persistent scene data. The approved v1 took 22 min 23.43 s at 1080 × 1920 and 5 samples. This preview has one quarter of v1’s pixel count. |
| Encoded result | FFprobe decoded 180 frames at 540 × 960, 30 fps, 6.000 s. H.264, yuv420p, 2,197,591 bytes. All 180 decoded frame hashes were distinct. |
| Framing | The tested drain and footing anchors ranged from x 429–1056 and y 1215–1406 on the 1080 × 1920 reference canvas. Ground filled the three bottom-edge probes on every frame. |
| Caption | The ffmpeg-static drawtext build burned “under your house.” in the repo’s Montserrat Bold into both exports. The JPEG uses source frame 120 at 3.967 s. Encoded frames 1, 60, 120 and 180 were inspected with the final caption in place. |

A separate Blender session rendered the 26-line README scene. Mesh checks confirmed closed, consistently oriented geometry on the concave section, bisected cap, five strata and all three pipe types. The terrace check found both masonry party walls. The five grade presets loaded, all loaded images stayed within 2K, and the seepage animation check confirmed glint travel, disappearance in a gap and a changing damp margin. After simplifying the straight-pipe mesh, a fresh frame-120 render scored 0.999991 SSIM against the source frame used for the preview.

## Remaining limits

- The water is an animated surface effect with authored interruptions. A scene that needs water entering a particular slot or changing the water table needs a matching path and gravel layout.
- This is a 540 × 960 preview. The rectangular openings are deliberately easy to read, and the stylised inspection pocket exposes more pipe than an undisturbed gravel bed would. Close shots can reveal the faceted stones and repeated rib pattern.
- The two house variants use the same furnished kitchen. The terrace has its own party walls, roof and eaves. Page-specific interiors and Malaysian street details belong in the scene that calls the library.
- The laptop settings are a starting configuration. Actual OptiX render time and peak VRAM still need a run on an RTX 3050 4 GB.

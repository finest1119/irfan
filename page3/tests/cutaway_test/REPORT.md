# Everyday Decoded — Under your house

[Watch the six-second test](out/cutaway_test.mp4) · [View frame 120](out/still.jpg) · [Open the Blender script](build_cutaway.py)

The camera pushes in and arcs six degrees around a section through a suburban kitchen and basement. The cut follows the concrete wall down to its spread footing, where a slotted perimeter drain sits in a bed of washed stone. The three-word caption stays above the drain throughout the move.

## Render and delivery

| Measurement | Observed result |
| --- | --- |
| Final render pass | **22 min 23.43 s**, including denoising and writing all 180 PNGs. Scene setup, previews and encoding are outside this measurement. |
| Average | **7.464 s/frame** |
| Hardware | Apple M2 Pro, Blender 5.3.0. Cycles enumerated only the CPU when queried for Metal devices. |
| Sampling | 5 samples on CPU, adaptive sampling, OpenImageDenoise, maximum 6 bounces, motion blur off. A full-size five-sample preview took 8.00 s. The script selects 16 samples when a Metal device is available. |
| Video | 1080 × 1920, 30 fps, 6.000 s. FFmpeg encoded H.264 with libx264 at CRF 20, 4:2:0. |
| Caption and still | FFmpeg drawtext burned “under your house.” in the repo’s Montserrat Bold. Both the video and the JPEG use the same caption filter. The JPEG was generated from 0120.png, corresponding to 3.967 s in the video. |

All 180 numbered source PNGs passed dimension and checksum checks and had distinct file hashes. FFprobe decoded 180 video frames. The opening, frame 120 and closing compositions were inspected from the encoded MP4.

## Materials and geometry

The Kloofendal partly cloudy HDRI supplies the sky and environment light. Poly Haven’s concrete_floor_02 diffuse and roughness maps cover the footing, wall and slab. The aerial_grass_rock diffuse and roughness maps cover the sod beneath the modeled grass blades. These are the CC0 assets documented in the [local Poly Haven README](../../../assets/polyhaven/README.md).

The house, joinery, furniture, soil, gravel, vegetation and drain are generated in bpy. The soil bands have closed, triangulated cut faces with procedural noise, embedded mineral grains and fine roots. The pipe has an inner bore, corrugations and modeled openings. The water uses a narrow glossy track with moving highlights.

## Three biggest gaps from the target

1. **Drain legibility.** The open mouth and gravel pocket read immediately. The side perforations recede into shadow because the camera sees the pipe almost end-on.
2. **Water behavior.** The glints travel toward the drain, but the blue track has nearly uniform width. Real seepage would darken the soil unevenly and disappear between individual stones.
3. **Sense of scale.** The regular sawn edges, evenly finished kitchen and clean base give the house a tabletop-model look. More variation along soil contacts and weathering where the foundation meets grade would help the section feel life-size.

## Rebuild

Run from the repository root on this Mac.

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P page3/tests/cutaway_test/build_cutaway.py -- \
  --out page3/tests/cutaway_test/out
```

The Homebrew FFmpeg on this machine lacks drawtext. The script used an existing ffmpeg-static build with that filter. On another installation, set the FFMPEG environment variable to an executable with drawtext and libx264.

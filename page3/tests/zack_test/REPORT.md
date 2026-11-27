# What Just Happened · Inside a bomb cyclone

[Watch the six-second clip](out/zack_test.mp4) · [View frame 120](out/still.jpg) · [Open the Blender build](build_zack.py)

A pedestrian braces on a wet sidewalk at dusk. The camera moves from waist-up toward the face as sleet crosses the lens. Two gusts pull at the scarf, rattle a windsock warning sign and make the pedestrian tuck their chin. The lower-middle caption reads **you brace yourself.**

## Render

| Measurement | Result |
| --- | --- |
| Final 180-frame Cycles pass | **16 min 40.638 s** (1,000.638 s) |
| Mean time per frame | **5.559 s/frame** |
| Renderer | Blender 5.3.0 on the M2 Pro. Explicit Metal selection and device enumeration returned no Metal device. Cycles rendered on CPU. |
| Settings | 2 samples per pixel, OpenImageDenoise, up to 3 ray bounces, camera depth of field at f/2.4 |
| Video | H.264, CRF 20, 1080 × 1920, 30 fps, 180 decoded frames, 6.000 s, BT.709, 4:2:0 |
| Still | Source frame 0120, at 3.967 s. FFmpeg applies the same Montserrat Bold drawtext filter to the JPEG and the video. |

The render timing covers pose and weather updates, path tracing, denoising and all 180 PNG writes. It excludes look-development previews, scene construction and encoding.

All 180 numbered source frames have distinct file hashes and passed PNG dimension, checksum and decompression checks. FFprobe decoded all 180 video frames. The opening, first gust, frame 120 and closing compositions were inspected from the encoded MP4, including the burned-in caption.

## Assets and animation

| Source | Use in the shot |
| --- | --- |
| Quaternius Universal Base Characters Standard, CC0 | `Superhero_Male_FullBody.gltf` from `Base Characters/Godot - UE`. The render uses the skinned body, eyes, brows and supplied skin, eye and hair maps. The build resolves two incorrect normal-map filenames in the glTF against the supplied PNGs. |
| Quaternius Universal Animation Library Standard, CC0 | `Idle_Loop` from the in-place `Unreal-Godot/UAL1_Standard.glb`. The script retargets bone rotations onto the human rig, then adds a spine lean, neck turn and two timed flinches. |
| Poly Haven, CC0 | Greg Zaal’s `kloofendal_48d_partly_cloudy_2k.hdr` provides ambient light. Rob Tuytel’s `concrete_floor_02` covers the sidewalk and `aerial_asphalt_01` covers the roadway. Both use diffuse, roughness and OpenGL normal maps. |
| Repo font | `assets/fonts/Montserrat-Bold.ttf` supplies the white caption, centred at 67.6% of frame height. |

The parka, cap, scarf, rain beads, sleet, streetlights, sign and buildings were built for this shot. The skin uses subsurface scattering and a thin wet coat. The parka has a textured shell, sewn panel lines and a waterproof zip. Animated scarf shape keys and variable-length sleet ribbons follow the gust timing.

## Three biggest gaps from the Zack D. Films reference look

1. **Facial performance.** The head turn and chin tuck sell the impact, but the eyelids and mouth stay fixed. A squint just before the strongest gust would make the reaction more convincing.
2. **Clothing weight.** The cap ribbing and parka seams read in close-up. The rigid-looking shoulder transition and evenly inflated jacket panels give away the game-ready construction when the torso bends.
3. **Weather interaction.** The scarf, sign and near-lens sleet show the wind direction. Snow on the clothing stays in place, and individual streaks pass through the scene without melting on the skin or splashing on the pavement.

## Rebuild

Run from the repository root. The script selects Metal when available, renders all 180 frames, then encodes the clip and captioned still. The encoder must support both drawtext and libx264. On this Mac the build uses the installed ffmpeg-static executable because the Homebrew build lacks drawtext. Set the `FFMPEG` environment variable to select another executable.

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P page3/tests/zack_test/build_zack.py -- --out page3/tests/zack_test/out
```

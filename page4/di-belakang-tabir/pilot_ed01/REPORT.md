# ED-01 · Hujan berhenti. Kolam masih bekerja.

[Watch the six-second hook](hook_6s.mp4). The last drop clears the gutter while the downpipe still runs. The pond sequence follows a single water-green leaf from the inlet to the outlet in a generic Malaysian taman perumahan.

| Frame | What to look for |
| --- | --- |
| [1 · Hook](beat1_hook.png) | A bead below the zinc gutter, a running downpipe and ripples in the open longkang. |
| [2 · Inflow](beat2_inflow.png) | The terrace row and parked kapcai establish scale. Across the diagonal cut, the 1.50 m inlet and 0.33 m outlet share an invert. |
| [3 · High level](beat3_level.png) | The water reaches about 7 cm below the damp line. Gauge marks on the back wall give the viewer a fixed reference. |
| [4 · Outflow](beat4_outflow.png) | The surface is about 43 cm lower. The leaf reaches the upstream lip while a thin jet runs into the receiving channel on the other side. |

The walls use textured cast concrete with exposed aggregate on the cut ends. The roadway, grass verge and wet soil continue across the section. The Page’s tropical daylight preset supplies a warm key over the tiles, with a local cool fill under the eaves. Modeled currents, animated jet fluting and impact rings carry the water movement. Frames are uncaptioned, with asphalt or soil beneath the action for bottom-centre BM subtitles.

## Rebuild and timing

From this folder, run the following command with Blender and FFmpeg available on PATH. The builder uses the repository’s cutaway library and local texture assets.

```sh
blender -b --factory-startup --python-exit-code 1 -P build_ed01.py
```

Blender 5.3.0 on the Mac used Cycles CPU and OpenImageDenoise. The four 1080 × 1920 stills used 10 samples. The 540 × 960 hook used 4 samples per frame.

| Final render | Elapsed |
| --- | ---: |
| Hook still | 21.16 s |
| Inflow still | 17.28 s |
| High-level still | 15.13 s |
| Outflow still | 16.99 s |
| Hook, 144 source frames | 5 min 54.47 s |
| **Total Cycles render, denoise and image writes** | **7 min 05.03 s** |
| Additional H.264 encoding | 0.95 s |

All four PNG dimensions were checked. The finished MP4 decoded to 144 distinct frames at 24 fps, 6.000 seconds, H.264 yuv420p. The four stills and decoded hook frames 1, 45, 91 and 144 were visually checked.

## Three gaps before the 46-second reel

1. **Complete the camera journey.** Connect the hook to the flashback, follow the leaf along the open drain and through the inlet, then return to the same mouth for the closing shot.
2. **Animate the storage cycle.** The pond uses three authored water states. Join them into one rise and drawdown, keeping the floating leaf, inlet turbulence and residual outlet jet in sync with the gauge.
3. **Finish the BM edit and sound.** Record the narration, time the drop and runoff sounds, and set Montserrat Bold captions against the voice. Add the dated issue line and “Ilustrasi 3D” opening label, then check readability with the Reel interface visible on a phone.

## v2 changes

The shared concrete shader’s high-water mark caused the dark diagonal across beat 4. The mark now sits on the inlet wall beside the gauge. Water-green `#32B8A5` follows the active route from the downpipe through the pond to the outlet jet.

The [CPU previews](preview_v2/) contain four 270 × 480 stills at two samples and the six-second 135 × 240 hook at one sample. Append `-- --preview` to reproduce them. On the chief’s Mac, check the `Cycles devices` line for both METAL and CPU. Run the full render with FFmpeg on PATH.

```sh
cd '/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan'
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P page4/di-belakang-tabir/pilot_ed01/build_ed01.py
```

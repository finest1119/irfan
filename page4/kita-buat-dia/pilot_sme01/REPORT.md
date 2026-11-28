# SME-01 · Kayuh basikal, dapat jus tembikai

Four [preview stills](preview/) follow Bar from dropping a wedge into the jug to serving one glass. Beats 2 and 3 use the same lens and framing. Look for the chalk marks and the change from bare metal to ribbed rubber at the tyre. The yellow line follows the drive through the belt and mitre gears to the blade. The [six-second motion test](preview/hook_6s.mp4) starts with the jug locked and loaded, then pushes into the turning drive as the fruit breaks down.

## Chief’s full render

Run on the M2 Pro outside the sandbox, with Blender 5.3 and FFmpeg with libx264 on PATH.

```sh
cd '/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan'
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P page4/kita-buat-dia/pilot_sme01/build_sme01.py
```

The command writes four 1080 × 1920 PNGs at 48 samples and a 540 × 960 H.264 MP4 at 24 samples alongside this report. The script enables Cycles Metal and CPU devices together when Metal is available. Check the console for `Cycles device: GPU` and the Metal device name. The final timings print with the `TIMING` prefix.

## Preview verification

The sandbox selected Cycles CPU. Quarter-size previews use 6 samples for stills, 2 for motion and OpenImageDenoise for both. Append `-- --preview` to the command to reproduce the files in `preview/`. Full-resolution GPU times are unmeasured.

| CPU preview stage | Time |
| --- | ---: |
| Scene and approved v3 character assembly | 11.72 s |
| Beat 1 · Hook | 2.02 s |
| Beat 2 · Tapi | 1.09 s |
| Beat 3 · Jadi | 1.16 s |
| Beat 4 · Payoff | 1.23 s |
| Motion render and H.264 encode | 52.42 s |
| **Total wall time** | **69.72 s** |

Checked the four PNG headers at 270 × 480 and decoded the MP4 at 135 × 240, 144 frames, 24 fps, 6.000 s. Inspected all four stills and motion frames 1, 49, 97 and 144. The hook leaves open pavement below the bicycle. The close shots use the cart canvas beneath the action.

## Three gaps before the 48-second reel

1. **Bar’s performance.** Animate feet on the moving pedals, the stop and two ruler taps, then the stopped-blade pour and glance from the full basket to his calves. The pilot poses Bar for loading and shows the finished glass.
2. **The failed and successful tests.** Shoot both passes with the same load and cadence. Hold on the tyre and roller chalk marks long enough to see the first roller lag, show the sleeve change, then give the second test time to establish grip and draw chunks into the vortex.
3. **The BM edit and mix.** Time the narration to the tyre hiss, ruler taps, blade spin-down and pour. Add the opening “Ilustrasi 3D” and verified issue line in the edit, then phone-check the two-line subtitles over the moving shot.

## v2 changes

Bar rides the adjusted saddle with both hands on the grips. His boots follow the level pedals through all 144 hook frames. The rear wheel turns 95/47 revolutions per crank turn. Beats 2 and 3 share a wider view of the roller, belt and blade shaft, with the yellow power path visible in both. The opening jug is loaded and lidded.

The [CPU previews](preview_v2/) contain four 270 × 480 stills and a six-second 135 × 240 hook. On the chief’s Mac, check the `Cycles devices` line for both METAL and CPU. Run the full render with FFmpeg on PATH.

```sh
cd '/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan'
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P page4/kita-buat-dia/pilot_sme01/build_sme01.py
```

## Quality pass v3

Bar retains his approved v3 face, hair, indigo shirt, clay apron and work boots. The seated trousers now have a continuous crotch and waistband. Both palms grip the bars, the boots share the pedal tilt, and the stitched apron moves over the knees.

- The bicycle has articulated half-inch chain links, a 47-tooth chainring and 23-tooth sprocket, brazed lugs, tread, brake hardware and trainer feet. The hook keeps the clear guard fitted. The matched failure and success stills section the guard to show the polished roller and the ribbed replacement.
- Pressed glass has an IOR of 1.50, condensation uses 1.333, and the juice uses 1.34. The close shots add a notched garnish, broken foam, glass graduations and handling marks. The materials vary roughness and wear across the steel, enamel, rubber, timber and fabric. Skin, melon and leaves use subsurface scattering.
- The local daylight HDRI, soft key, cool fill and glass rim light use the AgX base look. The hook uses a 42 mm eased tracking shot, a focus pull and a 0.42-frame shutter. Sixteen cut pieces settle under gravity before the ride. The liquid rises as the pieces break down.

**Chief’s full render.** From the checkout, run the following with Blender 5.3 and FFmpeg on PATH.

```sh
cd '/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan'
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P page4/kita-buat-dia/pilot_sme01/build_sme01_v3.py
```

The command writes four 1080 × 1920 PNGs and a six-second 1080 × 1920 H.264 hook to `out_v3/`. Cycles uses adaptive sampling up to 192 samples for stills and 64 for motion, with OpenImageDenoise. The console lists enabled Metal and CPU devices, with CPU fallback when Metal is unavailable.

**CPU preview verification.** Adding `-- --preview` produced four 432 × 768 stills at up to 24 samples and a 216 × 384 hook at up to 8 samples in 360.4 seconds. All four PNGs passed integrity checks. All 144 distinct video frames decoded at 24 fps for exactly 6.000 seconds. Visual checks covered all four beats and six frames spanning the camera move. The jug stayed in frame throughout. Across the baked frames and seven half-frame checks, the largest palm or sole anchor error was 0.68 mm. SHA-256 matched the original build script and all 15 pre-existing media files. [Preview stills](out_v3/preview/) · [Watch the hook](out_v3/preview/hook_6s.mp4)

**Remaining gap to Mildly Elsewhere.** The breakdown and foam use animated shapes. A fluid simulation could produce the finer spray and pulp turbulence, and a cloth simulation could capture smaller folds under load. The geometry checks cover visible contacts and the measured rider anchors. A full hidden-surface collision audit remains open. Final-resolution glass noise, temporal denoising and Metal performance still need the chief’s render.

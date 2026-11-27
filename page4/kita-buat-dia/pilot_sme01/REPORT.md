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

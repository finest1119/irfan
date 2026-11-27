# Self-Made Engineer · The creek turbine on the bench

Build #1 left Mercer Hollow with a wind turbine. The Build #2 draft turns to the creek when the wind dies. This test takes its nozzle and impulse wheel into Bolts’ backyard workshop, where one continuous shot can show why the jet’s aim matters and where the spent water goes. The shop uses the approved Quaternius s9 rig, s11 proportions and workshop outfit.

| Still | Frame | Narration cue for the reel |
| --- | ---: | --- |
| [Dead center](preview/01_dead_center.png) | 8 | You aim at the axle. But the wheel barely budges. |
| [At the rim](preview/02_at_the_rim.png) | 56 | So you aim at the cups. Your light comes on. |
| [On the bench](preview/03_on_the_bench.png) | 92 | But now you’re washing the workbench. |
| [Catch and return](preview/04_catch_and_return.png) | 140 | So you slide the catcher in. Congratulations. You’ve got light and a dry floor. |

**Grade.** The shared SME preset gives the bronze cups and tool edges an amber key, with less sky fill than Everyday Decoded’s neutral daylight. Di Belakang Tabir lifts the fill and adds humid distance. Here, angled sunlight through the open bay defines the cut iron lip and keeps the cabinet front quiet for captions.

**Render.** From the repository root on the chief’s Mac, with Blender 5.3 and FFmpeg with libx264 on PATH, run:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P page2/tests/cutaway_sme/build_sme_cutaway.py
```

The command writes four 1080 × 1920 PNGs and a silent 540 × 960 H.264 hook to `full/` at 48 samples. Cycles enables Metal and CPU together when it finds a Metal device, otherwise it uses CPU. Append `-- --preview` for four samples at 25% linear resolution in `preview/`.

**Preview verification.** Four 270 × 480 beat stills and the [135 × 240 hook](preview/hook.mp4) were rendered on CPU. The hook has 144 frames at 24 fps, runs 6.00 seconds, and has no burned-in text. The lower center stays on the broad cabinet face while the return pail sits to the right. Full-resolution Metal rendering is pending. The session did not expose per-phase model-effort switching.

### Three gaps before a full reel

1. **Connect the bench to the creek.** Add the stalled Build #1 rotor, intake, downhill pipe and tailrace. Follow one leaf past the intake screen so viewers see how the stream keeps flowing.
2. **Finish the water and hand contact.** Replace the keyed spray with a contact-driven splash at the cups and catcher. Give Bolts a timed reach to the swivel and slide, then check the jet, wet reflections and runner blur at full size.
3. **Time the audio and captions.** Record the second-person US narration. Pair the stalled-wheel pause, rising whir and first splash with the camera move, then place the two-to-four-word captions on the cabinet face.

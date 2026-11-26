# BUILD-LOG: bomb cyclone (Opus build, 26 Nov 2026)

## What was built
- `episode.json`: 9 beats from the approved `script.md`, voice Fenrir, `"narration_style": "if you were there"`, pause 0.2, trim_pauses on. All text = 2D overlays (cards, chips, labels on anchors baro / cold / warm / jet / eye / sign).
- New one-shot builder `pipeline/blender/scene_lib_v2_cyclone.py` (`bomb_oneshot`, the tides/campus pattern). It is registered in `render_episode_v2.py`'s guarded module list.
  - **World:** a white clapboard house with a porch on a grassy bluff, a brass barometer (ticks and needle only), a windsock (no flag), neighbour houses and trees, the beach road with a blank amber sign plus a shallow water sheet, dunes with grass, the beach, a pier, a lighthouse, the sea, and a huge sunlit comma swirl offshore (puffs on a grey base).
  - **Engine beat:** blue and orange arrows that spiral up over the storm tops, a jet-stream ribbon and chevrons.
  - **Rain and snow:** shader planes parented to the camera, so no wrapping geometry gets smeared by motion blur.
  - **Global timeline:** everything is keyed on it, including wind strength and direction (trees, grass and windsock bend), storm surge, waves, storm spin and tighten, the needle, and the takeaway props.
  - **Fog:** distance fog is thinned per frame by camera height, so the top-down shot stays crisp. clip_start is baked by height.
- **Camera:** 16 spots, eased whips with EEVEE motion blur, holds ≤ ~6.5 s, and a backout from 74 s that ends exactly on the frame-1 view.
  - Checked numerically (pure-Python camcheck): there is no jump at any beat boundary, and the first frame equals the last.

## Narration change (wording identical)
- The TTS read the director notes aloud 3× when `you_engine` started with the teaser "Here's what you can't see." (a known README issue).
- I moved that sentence to the end of `you_morning`. The full script is word-for-word the same, in the same order; only the beat boundary changed.
- Cues "let's" and "you're" were changed to "lets" and "youre" to match the caption normalisation.

## Timing
- TTS + captions: 80.7 s, 275 words. Whisper heard an extra "The" before "Air leaves the top" (you_pressure, 92 % aligned); see QC.

## QC
(filled in below after the render)
- Render: 2,419 frames with 3 Blender processes (about 40 min). Assembly first failed because the 4-chip lists ran outside the safe area; I set `y` to 0.62.
- qc_v2 first FAILED: 3 overlay-caused spikes in the mid band. Anchored labels were still on screen during camera whips. I added `until` to the BAROMETER, JET STREAM, LOW PRESSURE and ROAD FLOODED labels, and after that **qc_v2 PASSED**.
- qc_full auto **PASS** on the earlier assembly: 80.68 s, -14.2 LUFS, true peak -0.7 dB, WER 0.022, no long pauses.
  - Info only: mouth noise flagged before words at 12.1 s and 49.9 s.
- I reviewed sheet_01–03 by eye: bright daylight world, no void, nothing graphic, captions readable, cards inside the 12–80 % band. The frame-1 and final frames match (loop).
- Fixed: the ROAD FLOODED label showed for only 0.5 s, so it now cues on "stay". The overlay-only re-assemble + QC was still running at handback.
- SKIP (logged, not repaired): whisper heard an extra "The" before "Air leaves the top", narration otherwise identical. The storm puffs read as stylised "ball" clouds (cosmetic). The pause at "name: bomb cyclone" is about 1 s (dramatic, under 1.2 s).
- Thumbnails: hero `output/bomb-cyclone/stills_v2/05_you_wind_f0185_hero.png` (storm wall, rain, waves, pier). Variants are `output/bomb-cyclone/thumb_A.jpg` ("When a storm's pressure drops / LIKE A BOMB") and `thumb_B.jpg` ("Why forecasters call it a / BOMB CYCLONE").

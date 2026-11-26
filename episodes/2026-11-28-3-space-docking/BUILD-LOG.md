# BUILD-LOG: space docking (Opus build, 26–27 Nov 2026)

## What was built
- `episode.json`: 9 beats from the approved `script.md`. Voice **Sadaltager**, `"narration_style": "rewind"`, pause 0.2, trim_pauses on, the script's pronunciation line (Tiangong = tyen-GONG). Caption, hashtags, engagement comment and sources are taken from `output/space docking.post.md` (unchanged).
- All text is 2D overlays: a time strip (`clock`) in the card band (◀◀ REWIND → SECONDS BEFORE CONTACT → AN HOUR OR SO EARLIER → ABOUT 10 MINUTES AFTER LIFTOFF → LIFTOFF → ▶▶ FAST FORWARD → TAKEAWAY → YOUR TURN → THIS WEEK), cards, chips (all ≤ 88 % of the frame width), labels on anchors (station, port, capsule, stage, path). Relative times only, as the script requires; "ILLUSTRATION" chips on the explainer beats. The astronaut is not named. No flags, logos or insignia anywhere.
- `pipeline/overlay_v2.py` (opt-in additions, other episodes unchanged):
  - `clock` text starting with `"<< "` / `">> "` draws two small red rewind / fast-forward triangles instead of the red dot (Avenir has no ◀ ▶ glyphs).
  - New overlay type `spotter` (takeaway): a dusk-sky inset in the mid band (asserted) with a dark hilltop, a tiny person pointing up, stars, and a bright steady dot gliding across with a faint trail.
- **New one-shot builder** `pipeline/blender/scene_lib_v2_docking.py` (`docking_oneshot`, the detonation/cyclone pattern), registered in the guarded module list of `render_episode_v2.py`.
  - **World (stylised scale):** Earth radius 120 km so the orbit views have real-looking curvature (altitude/radius ≈ ISS). Procedural Earth: blue oceans, green/brown land, white cloud fields that turn slowly (orbital motion), a blue limb tint and an atmosphere shell (limb glow). Black space with stars only above the limb; the bright Earth fills most frames.
  - Generic T-shaped station (white modules, gold-foil band, **gold solar wings**, radiators, arm) with an aft docking port (ring, guide petals, yellow latches that open/close). Generic three-part capsule (orbital module with docking ring, descent module, service module, blue solar panels that fold), RCS thruster puffs, an engine-burn plume, a separate last rocket stage.
  - Orbit lines: glowing amber (station) and teal (capsule) rings round the planet; a dashed amber "station's path" ring that sweeps until it sits right over the pad.
  - Launch site (beyond the station's horizon): desert ground patch on the curved surface, hills, pad deck, pedestal, red lattice service tower with arms, lightning masts, buildings, a white generic rocket (four boosters, fairing, escape tower) that lifts off with a flame and white smoke.
  - World shader mixes space ↔ blue daytime sky by camera altitude (Light Path trick: earthshine fill in space); ground haze likewise; the shell fades as the camera dives into it.
  - Lesson (b) applied: the launch light and burn light have no shadows and a short cutoff. Earth/shell/rings/puffs cast no shadows.
- **Story on one timeline:** docked (hook) → REWIND: the capsule backs off the port → contact beat plays forward (closing slower than walking pace, contact on "nudge", latches on "latches") → REWIND: flies back and down to the lower orbit → gains on the station, burn and climb on "fires … climb" → REWIND: back to orbit insertion on the last stage, panels fold → separation on "done", panels open on "own" → pad, path sweeps overhead on "overhead" → liftoff → fast climb, the chase replays → takeaway at the horizon → final approach in the outro, gentle nudge on "nudge" = the frame-1 state (loop).

## Camera (one-shot: yes, no hard cuts)
15 spots, eased whips with EEVEE motion blur. Rewind ↔ backout: ring close-up → over the hatch → whole station → the gap → wide chase over both orbit lines (hero 2) → riding beside the capsule → top of the atmosphere → down to the pad → rises with the rocket → fast climb → horizon → station → glide back to the frame-1 view.
Numeric camcheck (Blender python, `camcheck.py` in the session scratchpad):
- Holds ≤ 7.6 s. Drift ≤ 14 % of the subject distance. The "riding beside the capsule" spot follows the moving capsule, so it has zero drift relative to it.
- At every beat boundary the per-frame step equals its neighbours (ratio 0.75–1.0), so there is no jump; all boundaries fall inside smooth moves.
- First frame = last frame exactly (d = 0.0000 m, same direction and lens).
- The final 5.4 s is a slow eased glide back into the frame-1 view (the loop return), not a hold.

## Narration changes (wording identical)
- Moved the short teaser openers to the end of the previous beat, as the README warns: "Rewind again." to the end of `rewind_contact`, "Rewind further." to the end of `rewind_chase`. Same words, same order.
- TTS retakes: `rewind_orbit` (first take inserted "for": "after liftoff for the rocket's") and `takeaway` (first take said "The takeaway is, you can…"). Both were confirmed by whisper base + small and regenerated; the new takes match.
- 283 words, 85.35 s.

## Renders
- Full render: 2,560 frames with 3 Blender processes, 60 min (about 4.3 s per frame per process).
- Re-render of beats 3, 5 and 6 (23 min):
  - Beat 3: the teal orbit ring passed right beside the camera that rides with the capsule, and showed as a huge glowing band from 0:37 to 0:40. The rings now fade out during that whip.
  - Beat 5: the pad camera now sits nearly on the track, so the dashed "station's path" ends up straight over the rocket.
  - Beat 6: the rocket-follow camera, for the same reason.
- The "Shadow buffer full" warnings come from the sun shadow over the huge scene. They are only warnings; I saw no missing shadows.

## QC
- **qc_v2 PASS** on the final mp4: 0 unexpected spikes and 0 A-B-A in every band. "Overlay-caused" frames 1678–1682 are the STATION'S PATH label over the moving 3D scene; they are not a blink.
- **qc_full auto PASS:** 85.35 s, 1080x1920, -14.3 LUFS, true peak -0.9 dB, WER 0.028, no pauses over 0.75 s, FB copy 9.32 MB. Mouth noise before words at 64.98 s and 76.84 s is informational only.
- **Manual review:** sheets 01–03. Sheet 02 was re-checked after the re-render.
  - The space shots are bright, with the blue Earth filling 55–75 % of the frame. The pad is in full daylight.
  - Captions are readable, all cards and chips sit inside the 12–80 % band, and nothing is graphic.
  - There are no flags or logos, and the last frame matches frame 1 (loop).
- **SKIP (logged, not repaired):**
  - The 0:49 whip down to the pad passes about 1 s of plain blue sky.
  - The thruster puffs read as soft grey balls.
  - At the hook end (0:11) the whip has a bright motion-blur streak.
  - The final 5.4 s glide back to frame 1 turns about 54°. It is the slow loop-return move, not a hold.

## Thumbnails
- Hero frame: `output/space-docking/stills_v2/02_rewind_contact_f0110_hero.png` (the capsule a few metres from the docking ring, gold wings, blue Earth; zoom 1.3).
- `output/space-docking/thumb_A.jpg`: "Launch to space station in" / **3.5 HOURS**.
- `output/space-docking/thumb_B.jpg`: "How do you catch a" / **SPACE STATION?**

- **QC + thumbnails (27 Nov, resumed run after the 01:49 network drop):** fb.mp4 complete (85.354 s vs master 85.35 s, last 2 s decode clean); qc_v2 PASS + qc_full auto PASS (WER 0.028, -14.3 LUFS, TP -0.9 dB), all 3 sheets checked: no MUST FIX. SKIP: 5-frame overlay ABA at f1678–1682 (0.17 s, LAUNCH WINDOW chip in), whip-transition frames 0:11/0:17/0:49, short breath/lip sounds in the gaps at ~64.7 s and ~76.6 s. No re-render.
- **Thumbnails:** hero `stills_v2/02_rewind_contact_f0110_hero2.png` (contact beat, zoom 1.15, shift 0.12,0.12: capsule nose to port, latches, gold wings, Earth below) → `output/thumbnails/space-docking-A.jpg` ("Launch to space station in" / **3.5 HOURS**) and `-B.jpg` ("How do you catch a" / **SPACE STATION?**), hooks from script.md. Final pick + `output/space docking thumb.jpg` left to the Fable final QC.

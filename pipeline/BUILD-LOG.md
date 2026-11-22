# BUILD-LOG: pipeline v1 + video #1 (highway pileup)

Builder: Opus sub-agent · 22 Nov 2026 · Nothing committed or pushed. Nothing posted.

## What was built
- `pipeline/make_episode.py`: the orchestrator. It runs tts → captions → render (parallel Blender processes) → assemble → post. Every step is cached and resumable.
- `pipeline/tts.py`: Gemini TTS, one call per beat (`gemini-3.8-flash-tts`, voice **Charon**). It writes the PCM to WAV, trims silence, and joins the beats with 0.3 s pauses. It also writes `timings.json` (shot boundaries = speech starts) and `usage.json` (tokens). There is a whisper guard that retries a beat if the TTS spoke extra words. On an auth/billing error it stops with exit code 2.
- `pipeline/captions.py`: uses faster-whisper `base.en` for word timings only. The caption text comes from the script and is aligned with difflib. Chunks are balanced at 2–4 words (only "Usually" ended up as a single word). Captions are Pillow PNGs in Arial Black, white with a navy outline, and digits are yellow. They are centred at y=1290 px, and an assert keeps them inside the 12%–80% band. A `list.ffconcat` overlay stream is built from them.
- `pipeline/blender/scene_lib.py`: the procedural low-poly library. It has shader-based distance fog (cheap, no volumetrics), additive glow billboards (hazards, brake lights), spot-light headlight beams, a low-poly car, a road with lanes and guardrails, camera-locked text cards in the upper safe area, and `ctx.word_time()` to sync events to spoken words. There are 8 builders: `fog_highway`, `chain_topdown`, `visibility`, `stopping_distance`, `following_gap`, `ice_road`, `dominoes`, `safety_tips`.
- `pipeline/blender/render_episode.py`: renders one shot headless (EEVEE, 8 samples, 1080x1920, 30 fps, PNG frames, resumable). It has a `--still` preview mode.
- `pipeline/README.md`: a step-by-step guide to making the next episode, written for a cheaper model.
- `episodes/2026-11-23-1-highway-pileup/episode.json`: the 9 beats, their shots, the caption, hashtags and sources.

## Decisions / findings
- **The TTS reads style prefixes aloud.** "Say in a clear, calm… tone: <text>" was spoken in full, and `system_instruction` returned 400 "Developer instruction is not enabled for this model". The `### DIRECTOR'S NOTES … ### TRANSCRIPT …` format works: only the transcript is spoken. I verified this with whisper.
- **This ffmpeg build has no `subtitles`/`ass`/`drawtext`**, so captions are PNGs overlaid through a concat-demuxer stream (`overlay` filter). Pillow was pip-installed into `.venv`.
- **Caption text comes from the script.** Whisper mishears "Trakia" (→ "Trochia"), "Yambol" and "brakes hard" (→ "breaks heart"), so it is only used for timing.
- **Fog is done in the shaders** (mix toward a flat fog colour by camera distance), not with world volumetrics. It renders at about 0.33 s/frame at full resolution on the M2 Pro.
- The visuals are non-graphic. Cars stop, and at most end up touching bumpers (`chain_topdown`, `following_gap`). There are no damage, people or fire. The hook shows a calm queue of stopped cars with blinking hazards in fog.
- The hook script states only the verified fact: 10 Nov, dense fog, two pile-ups, 86 vehicles, Trakia motorway near Yambol. It gives **no death toll**. The body uses "often/usually/could/might". The stopping-distance figures come from the UK Highway Code: 96 m at 70 mph (21 m thinking + 75 m braking), and braking up to 10× longer on ice.
- **Three render passes were needed.**
  - Pass 1 → QC showed text panels overlapping. I fixed the spacing and re-rendered 6 shots.
  - Pass 2 → closer review showed the glow billboards (hazards and brake lights) were invisible in the angled shots. `plane()` bakes the creation location into the mesh, so billboards built off-origin were swung away by TRACK_TO. Billboards are now built at the origin. The hazard blink is now an explicit square wave (CONSTANT interpolation on node-socket keys was being ignored), and the glow strengths were tuned.
  - Pass 3 → 8 shots were re-rendered. `dominoes` was reused.
- **Loudness.** The TTS audio has inter-sample peaks of about +4.4 dBTP, so two-pass linear `loudnorm` could not reach -14 (pass 1 measured -15.5 LUFS). `step_assemble` now applies gain plus `alimiter` (-1.7 dBFS), re-measures with ebur128 and corrects up to 3 times. The result is **-14.6 LUFS integrated**.

## Commands to re-run
```
.venv/bin/python pipeline/make_episode.py episodes/2026-11-23-1-highway-pileup/episode.json            # everything (cached)
.venv/bin/python pipeline/make_episode.py <episode.json> --steps render,assemble,post --parallel 4       # re-render missing shots + assemble
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P pipeline/blender/render_episode.py -- <episode.json> output/highway-pileup <IDX> --still 60,200 --scale 0.5
```

## Render time
- About 0.33 s/frame at full resolution per process. There are 3,111 frames (103.7 s × 30 fps).
- Pass 1: all 9 shots with 4 parallel Blender processes took **643 s (about 10.7 min) of wall time**. Assembling took about 45 s. The whole pipeline took 698 s.
- Pass 2: 6 shots were re-rendered after the text-spacing fix, taking 462 s of wall time.
- Pass 3: 8 shots were re-rendered after the glow fix, taking 553 s of wall time. Assembling took 52 s.
- **A clean single run is about 11–12 min of render plus about 1 min of assembly.**
- Previewing stills takes about 0.3–1 s per frame at half resolution.

## Result
- `output/highway pileup.mp4`: 103.73 s, 1080x1920, 30 fps, H.264 plus AAC 48 kHz **mono** (the TTS is mono), about 24 MB.
- `output/highway pileup.post.md`: title, FB caption, hashtags, posting checklist, sources and the script.
- QC: 9 frames are in `output/highway-pileup/qc/` (`qc_*.png`, `qc_sheet.png`). I looked at all of them. The captions are readable and inside the safe band, the cards sit in the upper area. The stopping-distance panels touch edge to edge but don't cover each other. Hazard and brake glows are visible, no frame is blank or black, and nothing is graphic.
- Sync: I re-transcribed the final mp4's audio with whisper and compared it to `captions.json`. 250 of 259 words matched, with a **median offset of 0.011 s**, p95 of 0.13 s and a max of 0.83 s.
  - The two largest offsets ("Leave" at 82.89 s and "At" at 25.51 s) are errors in the re-transcription, not in the captions. The waveform shows speech actually starts at 82.78 s and 25.47 s, after silent pauses, so those captions are about 0.1 s late or better.
  - The caption text at each QC time matched the spoken words.

## Problems / limitations
- **Loudness** is -14.6 LUFS integrated, 0.6 LU under the target. The limiter loop stops after 3 iterations, so add one if exact -14 matters. The limiter adds a little peak compression, and the TTS source itself overshoots 0 dBTP.
- The car is a box-model (low-poly) and the wheels don't spin. That is deliberately simple.
- The hazard glows blink in sync, because they share one material.
- In `ice_road` the DRY/ICE labels are moved to the frame edges, so the icy car stays visible. In `following_gap` the cars end bumper-to-bumper. That is abstract and has no damage.
- The pronunciation of "Trakia"/"Yambol" relies on the director notes. Whisper can't confirm it, so **a human should listen to the first 8 s**.
- No music (`music: null`). The assemble step supports an optional music bed via `episode.json` → `music`, but it is untested.
- Re-check the hook facts on posting day (calendar rule 2).

## API cost estimate
- Final beats: 9 TTS calls, 888 input tokens and 2,473 audio output tokens (`output/highway-pileup/audio/usage.json`).
- Testing the prompt format took 4 more calls, about 1.2k output tokens. One more call was rejected with a 400 and was not billable.
- At plan.md's rate of $9 per 1M audio output tokens (not re-verified), that is about **$0.022 for the video itself and about $0.035 including the tests**. Text input tokens cost less than $0.002.
- Whisper and Blender run locally and are free.

## Facts not re-fetched by the builder
- The hook facts come from the spec (Euro Weekly News / BTA / HNGN). I did not fetch them.
- The explainer figures are from general knowledge, not fetched: 96 m at 70 mph (21 + 75), up to 10× braking distance on ice, "at least four seconds" in fog, and "under 2 s for 50 m at motorway speed" (110 km/h ≈ 30.6 m/s).
- `episode.json` → `sources` now says to verify these before posting. I removed the Highway Code rule numbers and the BTA/HNGN dates that I had added from memory.

---

# v1.1 Kenney upgrade (22 Nov 2026)

Builder: Opus sub-agent. Nothing committed or pushed. Video #1 was NOT re-rendered (`output/highway pileup.mp4` untouched).

**Why:** the owner approved video #1 but said the cars look "too boxy".

**What changed**
- `scene_lib.py`: the procedural box car is replaced by **Kenney Car Kit** GLB models (CC0, `assets/kenney-car-kit/`, credited in `assets/CREDITS.md`).
  - Each model is imported once per shot as a template. The template objects are removed and only their meshes are kept. Every car is a set of linked duplicates sharing those meshes. The cache is cleared in `reset_scene()`.
  - Mix: a seeded, weighted bag of civilian cars (sedan, suv, hatchback-sports, suv-luxury, van, sedan-sports, taxi, delivery). It uses a private RNG, so the builders' `random.seed(7)` jitter and every v1 car position are unchanged. There are no `debris-*` models. Emergency vehicles appear only through an explicit `models` param.
  - Car contract kept: the car faces +Y (Kenney models face −Y, so they get a 180° yaw), the origin is at ground centre, and every model is normalised to 4.4 m bumper-to-bumper (incl. the SUV spare wheel, the spoiler and the van door) and 1.9 m wide. The body takes a non-uniform scale. The wheels get their own scale, which is uniform in their rotation plane, so they stay round. `following_gap` ends with a 0.15 m bumper gap and no overlap; `chain_topdown` keeps a 0.2 m gap.
  - Paint: the Kenney colormap is desaturated (`PAINT_SAT` 0.62, `PAINT_VAL` 0.92) and passed through the same shader distance fog.
  - Lights: the tail/brake lamps (red), amber indicators and headlights are emissive lenses placed on each model's own lamp faces. The positions in `LAMPS` were measured from the lamp texels. The glow billboards sit behind the rear bumper. `brake_light()` and `headlight_beams()` use the new positions.
- v1 limitations fixed:
  - **Wheels spin.** `drive()` keys each road wheel's rotation from distance travelled ÷ wheel radius. The SUV's rear spare is static. A numeric check found that the top of the rim moves forward faster than the bottom, which is the correct rolling direction.
  - **Hazards blink out of sync.** Each car has its own hazard materials with a phase offset of 0–6 frames and a period of 17–19 frames, seeded from the car name.
- Collisions are still gentle bumper-to-bumper stops, with no debris or damage.

**Verification (stills only)**
- New stills are in `output/kenney-test/stills/` (shots 0, 1, 2, 3, 4, 5, 7 and 8). Shot 6 (`dominoes`) has no cars; the car "domino" shot is shot 1 (`chain_topdown`).
- The before/after pairs against the final v1 frames (`output/highway-pileup/frames/`) are in `output/kenney-test/compare/`.
- Model and lamp close-ups (all 8 models, rear and front three-quarter views) are in `output/kenney-test/dev/`.

**Render time per frame** (full res, 1 process, 30-frame animation incl. shader compile, same M2 Pro):

| shot | v1 | v1.1 |
|---|---|---|
| hook (15 cars), 3 runs each | 0.31 / 0.32 / 0.32 s | 0.35 / 0.32 / 0.32 s |
| question (12 cars, top-down) | 0.36 s | 0.36 s |
| gap (2 cars) | 0.34 s | 0.33 s |

There is **no measurable change** (run-to-run noise is about ±0.03 s). Scene build time was v1 1.1 s → v1.1 0.9 s for the hook, 0.6 → 0.4 s for question and 0.1 → 0.1 s for gap, so the one-off GLB import is not measurable either. A full video render should stay at about 11–12 min.

**Limitations**
- Kenney's own colours are kept, so there are two reds (sedan, sedan-sports) and two yellows (taxi, suv-luxury). The hero car in the chase shots is the first draw from the bag, which is the sedan.
- At motorway speed the wheels turn about 120° per frame. Without motion blur that strobes (the wagon-wheel effect), so the spin reads best on slow and stopping cars.
- The lamp positions for models outside `LAMPS` (e.g. police, ambulance) are estimates. Preview a still before using them.
- `van` (blue) is in the mix as an ordinary civilian van, although it was not on the owner's list. Remove it from `CIVILIAN` if unwanted.
- To pin a specific car, pass `model="..."` to `make_car`.
- The cars are slightly stretched lengthwise relative to Kenney's toy proportions, to keep the 4.4 m contract.

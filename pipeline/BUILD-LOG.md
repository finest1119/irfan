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

---

# Video #2: Japan earthquake (22 Nov 2026, v1.2)

Builder: Opus sub-agent. Nothing committed or pushed. Nothing posted. Episode 1's outputs were not touched or re-run.

**Episode**: `episodes/2026-11-23-2-japan-earthquake/episode.json` (calendar Mon 23 Nov, slot 2). It has 10 beats and 278 words. The voice is **Sadaltager** with the README director notes plus a Pronunciation line (Shizuoka/Aichi/Nagano/Gifu).

**New builders** (`scene_lib.py`, documented in the README table): `japan_map` (modes hook/dots/plates/outro), `subduction`, `ruler_snap`, `quake_depth`, `base_isolation`, `phone_alert`, `drop_cover`.
- New helpers: `add_mat`, `prism`, `resample`, `ribbon`, `ring`, `wave_ring`, `pulse_rings`, `vis`, `ll`, `house`.
- Japan outlines are hand-coded lon/lat polygons, and the plate boundaries are schematic. Boundaries are deliberately NOT drawn in the hook/outro shots near the epicentre, so the video doesn't imply a cause.
- No new assets.

**Pipeline changes**
- `tts.py`
  - Calls are paced 7 s apart (the limit is 10 requests/min).
  - A rate-limit 429 now waits 30–90 s and retries the same model. A billing 429 still stops with code 2.
  - The whisper guard is stronger. It now also fails a take if director-note words are heard anywhere, or if the word-sequence match is below 0.7. On the first run the hook's second half was replaced by the director notes ("...lively intonation, never monotone or salesy") at about the same length, and the old length-only check let it through. It was caught by checking captions alignment (45%), and the beat was regenerated with `--only hook --force`.
- `make_episode.py`
  - New `fb` step (now in the default steps). It makes an HEVC `hvc1` + mono AAC 80k copy, with the video bitrate computed from the duration to target about 9.3 MB, and re-encodes 15% lower if it comes out at 10,000,000 bytes or more.
  - `step_post` now writes the `engagement_comment` (optional field, so episode 1 still works), a fuller checklist (fb file, Public, AI label, hashtags, engagement comment) and "Sources".
  - ⚠️ Running episode 1 with default steps would now also (re)write `highway pileup fb.mp4`.

**Result**
- `output/Japan earthquake.mp4`: 103.30 s, 1080x1920, H.264 + AAC mono, 27.97 MB. Voice is at -14.4 LUFS.
- `output/Japan earthquake fb.mp4`: 103.30 s, HEVC `hvc1` 1080x1920, AAC mono, **9,118,529 bytes** (620 kb/s video).
- `output/Japan earthquake.post.md`: title, caption + hashtags, engagement comment, checklist, sources, script.
- QC: 11 frames are in `output/japan-earthquake/qc/` (`qc_*.png`, `qc_sheet.png`), covering every beat including 1.0 s. All are non-blank, the captions sit inside the safe band, the cards are in the upper area, and nothing is graphic (gentle sway only; the mannequin kneels upright under the table).
- Sync: I re-transcribed the final mp4 with whisper. 270 of 278 caption words matched, with a median offset of 0.011 s, p95 0.23 s and max 1.2 s. The max ("If" at 83.08 s) is a re-transcription error: the waveform is silent from 83.1 s, and speech resumes at about 83.2 s.

**Render time**
- Wall time was 2,023 s (33.7 min) with 4 processes. This is over the ~15 min goal because **another session was rendering in Blender at the same time** (7 Blender processes and a shared GPU).
- Shots rendered after that contention ended ran at about 0.45 s/frame: plates took 116 s for 257 frames, and alert took 117 s for 205 frames. A clean run should be about 10–12 min.
- Assemble + fb + post took 130 s.

**API cost**
- Final beats: 10 TTS calls, 1,558 input tokens and 2,453 audio output tokens, which is about $0.022 at $9/1M (rate not re-verified).
- About 2 more calls were retries (the plates guard retry and the hook regeneration), roughly another $0.005.

**Facts to re-check before posting**
- Hook: from the spec (The Japan Times / JMA via APA / USGS), not re-fetched by me.
- "More than 1 in 10 of the world's M6+ earthquakes" and "under 1% of the world's land" were checked with a web search: Cabinet Office 18.5% (2004–13), MIC 13.1% (2008–18), nippon.com 0.28% land.
- "Around 2,000 known active faults" (HERP figure) and early-warning "seconds before" are from general knowledge and were NOT re-fetched.
- "Deeper quakes usually spread shaking wider but weaker" is a general statement.

**Limitations**
- The Japan map is stylised (simplified coastlines, no small islands), and the plate boundaries are schematic.
- Caption chunk "JUST AFTER 1 A.M" loses the final period of "a.m.", which is cosmetic.
- The pronunciation of Shizuoka/Aichi/Gifu relies on the director notes, so **a human should listen to the first 12 s**.

---

# Video #3: "nuclear weapons" (Mon 23 Nov slot 3), 22 Nov 2026

Builder: Opus sub-agent. Nothing committed, pushed or posted. Built at the same time as video #2 (another agent).

**Files**
- New: `pipeline/blender/scene_lib_geo.py` with 9 builders (`globe_summit`, `round_table`, `treaty_doc`, `cap_bars`,
  `verify_checks`, `three_balance`, `stock_bars`, `three_lower`, `risk_gauge`). It registers itself with
  `L.BUILDERS.update(...)`; `scene_lib.py` was not edited.
- `pipeline/blender/render_episode.py`: +2 lines, a lazy `import scene_lib_geo` only when the shot's builder is not
  already in `L.BUILDERS` (so a broken geo file can never affect other episodes' shots).
- New: `episodes/2026-11-23-3-nuclear-weapons/episode.json` (10 beats, 283 words, voice **Orus**; #2 uses Sadaltager, so no repeat).
- README: new section for the geo builders + the FB HEVC command (appended).
- `tts.py` was not touched: the 7 s pacing + 429 retry added by video #2's agent was reused (no 429s hit).

**Run**
- TTS + captions: 116 s (10 beats, one whisper-guard retry on the hook). Voice 90.98 s. Alignment 86–100 % per beat
  (whisper hears "arms deal" as "arm steel" and drops "are" in "why are they so hard"; captions use the script text).
- Stills: ~3 preview rounds at 0.5 scale to fix framing (globe view moved to a Pacific-side camera so US, China and
  Russia are all on the visible face; upright camera-facing labels; chairs facing the table; wider lens for the table;
  ceiling slab hidden before its cue; stage rim as a ring, not a disc).
- Render: 2,004 s wall (4 processes). Slow because video #2's render started a few minutes after this one and both ran
  together (8 Blender processes, load ~130); my wait loop only checks before starting. Alone it should be ~10–11 min.
- Assemble: voice -14.2 LUFS. Total pipeline 2,052 s.

**Result**
- `output/nuclear weapons.mp4`: 90.98 s, 1080x1920, H.264 + AAC mono, 20.3 MB.
- `output/nuclear weapons fb.mp4`: HEVC (hvc1) 600k + AAC 80k mono, faststart, 7,648,620 bytes.
- `output/nuclear weapons.post.md`: title, caption, hashtags, checklist (Public, AI label ON, hashtags, engagement
  comment), engagement comment, sources, script. The engagement-comment/checklist lines were added by hand after the
  `post` step (`step_post` does not know `engagement_comment` yet): do not re-run `--steps post` or they are lost.
- QC: 12 frames in `output/nuclear-weapons/qc/` (`qc_<sec>.png`, `qc_sheet.png`). Captions readable and in the band,
  cards in the upper area, nothing blank, no war imagery. Sync: final audio re-transcribed, 272/283 words matched,
  median offset 0.010 s, p95 0.15 s, max 0.65 s.

**Limitations / to check**
- The caption band (y≈0.67) sometimes covers the lower labels of a shot (e.g. "1980s PEAK" / "TODAY" in `stock_bars`).
- Globe has no coastlines on purpose (no map data downloaded); countries are shown by coloured markers + labels.
- Stockpile bars are relative only (no numbers on screen); heights roughly follow FAS estimates (~70k peak → ~12k now).
- Explainer figures not re-fetched: 1,550 deployed strategic warheads (New START), "more than three quarters" drop from
  the 1980s peak, "US and Russia hold most". Pronunciation of "Xi Jinping"/"Shenzhen" relies on director notes: a human
  should listen to the first 10 s.

---

# Videos #4 "plane crash" and #5 "bridges in war" (Tue 24 Nov slots 1–2), 23 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). Built one after the other: A was fully rendered and checked before B started. Nothing was committed, pushed or posted.

**Code**
- New: `pipeline/blender/scene_lib_air.py` with 14 builders, registered into `L.BUILDERS`. They are documented in the README.
  - Aviation (7): `airport_scene`, `flight_profile`, `altitude_margin`, `cockpit_workload`, `crosswind_approach`, `tightrope`, `seatbelt_sign`.
  - Bridges (7): `river_city`, `river_barrier`, `supply_funnel`, `utility_bridge`, `history_cards`, `pontoon_bridge`, `arteries`.
  - Helpers: a procedural light plane with a spinning prop, an airliner with animated flaps and gear, a gradient sky dome, a runway with lights and PAPI, a city generator, and movers (dots looping along a path).
- `render_episode.py`: chained lazy import. If a builder is not found it imports `scene_lib_geo`, and if it is still not found it imports `scene_lib_air`. `scene_lib.py` and `scene_lib_geo.py` were not edited.
- `README.md`: added a builder table and two gotchas (below).

**A: `output/plane crash.mp4`**
- 94.40 s, 284 words, voice Fenrir (#3 was Orus).
- TTS: the `slice` beat began "Here's the surprising part." Gemini then read the director notes aloud on 6 tries in a row. Rewording the opener fixed it.
- Render: 603 s wall time with 4 Blender processes, then a 240 s re-render of the hook only, to move the plane label out of the caption band.
- FB copy: 9,434,809 bytes, HEVC hvc1. Voice about −14 LUFS.

**B: `output/bridges in war.mp4`**
- 88.70 s, 269 words, voice Orus (A used Fenrir).
- TTS worked first time. Whisper heard "Kyiv's mayor" as "Keves Mayer" (captions use the script text).
- Render: 523 s wall time.
- FB copy: 9,487,150 bytes, hvc1.

**Bugs fixed on the way**
- **Buildings and dots not rendering:** `L.box()` runs `transform_apply()`, which also bakes in the location. Source boxes built at z=−5000 and then copied ended up 5 km underground, so no buildings or dots showed. Sources are now built at the origin and deleted after copying.
- **Cabin cards hidden:** the cabin interior was smaller than the 2 m depth of the camera-locked cards, so the ceiling hid them. The cabin is now scaled up 3x.

**QC**
- Frames checked: 11–12 frames each, in `output/<slug>/qc/qc_sheet.png`.
- Captions are inside the band, and the cards and chips sit in the upper area.
- Nothing graphic. The plane is only shown on approach, and a hit bridge only dims and gets a red ring, with its traffic stopping.
- Whisper alignment: A 96–100 % per beat. B 88–100 % per beat; it hears "Kyiv's mayor" as "Keves Mayer" in the hook, but the captions use the script text.

**TTS cost** (rate not re-verified)
- A: about 1.4k input and 2.2k audio output tokens, plus about 7 failed retries.
- B: similar, about 2.1k output tokens.
- Total about $0.05.

**Caveats / re-check before posting**
- **A, explainer stats:** "Most accidents happen at takeoff and landing" and the "critical eleven minutes" were not re-fetched.
- **A, crash cause:** no cause is suggested anywhere.
- **B, number of bridges:** Euronews' headline says *two* bridges were damaged. The video says "three", attributed to Kyiv's mayor, per the brief.
- **B, history facts:** Arnhem 1944 and Remagen 7 Mar 1945 were not re-fetched.
- **B, map:** the bridge positions and names on the map are stylised, not to scale.
- **Pronunciation:** a human should listen to the hooks: "Cirrus SR22" and "NTSB" in A, "Kyiv" and "Dnipro" in B.
- **Source URLs:** two required source URLs contain casualty words in their slugs ("2-dead", "3-killed"). The descriptions next to them in post.md stay neutral.

---

# v2 look-dev test: plane-crash hook shot (0.0–9.6 s), 23 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). This is a test only: no v1 builder, `render_episode.py` or episode output was changed. Nothing was committed, pushed or posted.

**New files**
- `pipeline/blender/scene_lib_v2.py`
  - Daytime world:
    - Sky: Blender's physical sky (multiple scattering) plus procedural noise clouds. If an HDRI is found in `assets/polyhaven/`, it is used instead.
    - Lighting: an aligned sun lamp (2.5° soft shadows), screen-space raytracing with fast GI/AO, AgX Medium High Contrast, and compositor bloom.
    - Haze: light shader distance haze.
  - Set: patchwork fields (Voronoi), mowed airfield grass, runway, blast pad, taxiway, apron (concrete joints), terminal (window-grid facade), tower, 6 hangars, T-hangars, PAPI, approach lights, windsock and a perimeter fence. It also has a parking lot with Kenney cars, 6 parked light aircraft, about 6.2k houses with orange, brown and grey roofs, about 5.8k low-poly trees, roads with markings, moving traffic, a downtown skyline and hills.
  - Markings: runway, taxiway, road and parking markings are baked into one PIL texture per surface, so there are no decal planes for the markings.
    - The ground, lawn, roads, taxiway, apron and lot are still stacked planes 2–15 cm apart, with camera `clip_start` 1 m.
    - No alternating surfaces were seen in 1:1 crops of frames 174–176. If it ever shows, raise `clip_start` to 5–10 m; the camera is never closer than about 20 m to anything.
  - Aircraft: lofted fuselage (subsurf), NACA-section wings, tail and fin, glass canopy, wheel pants, spinning 3-blade prop with a blur disc, nav lights, strobes and a landing light. The livery (navy cheat line, red pinstripe, fin band, red wingtips) and the panel lines are done in the shader, in aircraft space.
  - No 3D text. The builder exports per-frame screen positions of the plane (`track.json`) for 2D labels.
- `pipeline/blender/render_v2_test.py`: Blender entry for the test (frame ranges, stills, track export).
- `pipeline/v2_test.py`: the orchestrator. It makes the textures, renders 3 processes in parallel, then adds the PIL overlays:
  - Captions: top centre at 26 %, Avenir Next Bold with a soft shadow and no box. The current word is set in Heavy on a rounded red highlight. Word slots are fixed so text never reflows.
  - Title card at 13.5 %.
  - CIRRUS SR22 pill that tracks the plane and appears on "cirrus".

  It then encodes (with the original hook audio), builds `compare.mp4` and `compare.jpg`, and runs the flicker QC.
- `pipeline/qc_flicker.py`: luminance-change QC per screen region. It reports:
  - mean, p95 and max frame-to-frame change;
  - spikes, split into expected (caption, pop events) and unexpected;
  - region A-B-A reversals;
  - per-pixel flip-and-return share (the z-fighting signature).
- `.gitignore`: added `assets/polyhaven/`.

**Render**
- 288 frames, 1080x1920, 24 TAA samples, 3 Blender processes.
- Time: 417 s wall (about 3.8 s per frame per process). Each process spends about 40 s building the scene (14k objects). The track export took about 1 min, and overlays plus encode about 1 min. Total is about 8.5 min.

**Assets / licences**
- No files were downloaded. Downloads need Irfan's own confirmation, which a sub-agent cannot get.
- Everything is procedural or PIL-generated, plus the existing Kenney Car Kit (CC0).
- The world loader already picks up a Poly Haven HDRI if one is placed in `assets/polyhaven/` (CC0, gitignored).

**Flicker QC** (`output/v2-test/flicker*.json`, 9.6 s)
- v1, caption band: no unexpected flicker.
- v1, 3D card and label band: spikes only during the pop-in animations. During the 1.08 scale overshoot, up to 1.5–3.9 % of the region's pixels flip and return. Outside the pops there was nothing in this range.
- v1 baseline (raw PNGs of the whole hook, 424 frames, chip band y 560–820): the QC reproduces the flicker. It flags 20 frames (389–421) after the "CAUSE NOT DETERMINED" chip has settled, with up to 11.9 % of the band's pixels flipping and returning. That is the chip flicker Irfan saw (`output/v2-test/flicker_v1_png_full_hook.json`).
- v2, card band: no unexpected spikes and no reversals.
- v2, caption band: 39 spikes, all expected (chunk swaps, 0.2 s rise-ins and highlight moves). 0 unexpected, 0 A-B-A. The few flagged pixels at frames 253–259 also show in the raw render without overlays: the city skyline moves into the band.
- v2, fixed band y 600–820 (mostly 3D background, not the tracked pill): the composited video peaks at 0.58 % of pixels; the raw render without overlays peaks at 0.77 %. The overlays add nothing.
  - The heat map and 1:1 crops put these on the spinning prop, approach-light bars, fence, road and runway edges (thin lines moving under the camera), and on the terminal's window grid and parked cars about 1 km away (fine distant detail).
  - The lawn is clean, and no surface alternates.

**To do / not done**
- Poly Haven HDRI and PBR textures: not downloaded, waiting for Irfan's go-ahead. The file list is in the handback.
- Kenney City/Suburban kits: not used.
- If shimmer shows at full speed, raise the TAA samples to 48 or thicken the far-off thin geometry (fence, approach bars).

# v2 becomes the pipeline standard + "plane crash" rebuilt in v2, 23 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). Nothing committed, pushed or posted.
Irfan paused the task after video A: **"bridges in war" was NOT rendered** (its v1 mp4 / fb copy / post.md are unchanged).

**Assets** (approved by Irfan): Poly Haven CC0, official API/CDN, MD5-checked, 11 MB total in `assets/polyhaven/`
(gitignored; README/LICENSE with source URLs; credited in `assets/CREDITS.md`): HDRI `kloofendal_48d_partly_cloudy`
2K .hdr; 1K diff / nor_gl / rough of `aerial_asphalt_01`, `aerial_grass_rock`, `concrete_floor_02`.
- HDRI = sky + light (`S.daylight()`); EEVEE extracts its sun (threshold 6) for shadows, Mapping rotation puts the
  sun at the requested lamp azimuth (HDRI sun measured at phi 144 deg, elev 47.9 deg). Strength 1.0, exposure -0.6.
- Textures via `S.ph_detail()` on runway/taxiway/road/lot (asphalt), lawn + ground (grass_rock), apron (concrete).

**Pipeline (v2 is the default; old episodes carry `"pipeline": "v1"`)**
- `make_episode.py`: v2 steps tts,captions,textures,render,assemble,fb,post,qc. Render = one queue of <=150-frame
  jobs (`render_episode_v2.py`, q95 JPEG frames: disk is tight), broken-frame cleanup, unbuffered logs.
  `post` keeps an existing post.md (`--force-post`).
- `overlay_v2.py`: every on-screen text (captions top-centre with red word highlight, card, chips, tracked labels,
  bars, big panel, meter, flight-profile graph, history cards, plate blur), beats composited in parallel.
- `qc_v2.py`: probe, flicker split into overlay-only stream / 3D-only stream / final, 12-frame sheet.
- Builders: `scene_lib_v2_air.py` (airliner + 8 aviation shots), `scene_lib_v2_city.py` (river city + 9 bridge
  shots; build-tested only, never rendered). README rewritten so new episodes follow v2 by default.
- v1 episode files: `episode.v1.json` saved next to both Tue 24 episodes; the 23 Nov episodes got `"pipeline": "v1"`.

**Video A** `output/plane crash.mp4`: 94.39 s, 1080x1920, 30 fps, AAC, voice -14 LUFS; same voice.wav/captions.
FB copy `output/plane crash fb.mp4` 9,380,347 bytes (HEVC 688 kb/s). post.md unchanged. v1 backed up in
`output/v1-archive/`. Shots: airport_hook, airport_plate x2 (graph overlay on blurred plate), altitude_margin_v2,
cockpit_workload_v2, crosswind_v2, tightrope_v2 (meadow), cabin_v2, airport_outro (take-off + crane-up).
- Wall time: render 08:33:29 -> 09:35:04 (3690 s, 23 jobs, 2 Blender processes; 3 processes swapped on 16 GB RAM
  and were stopped at 08:32; ~30 min of it was slowed by a B build test running alongside). Beat 3 re-render 303 s
  (09:41-09:46). Overlay+assembly ~1.5 min, FB copy ~2 min, QC ~2 min. Final pass 11:28 -> 11:37.
- QC fixes: 1-frame blank caption on direct chunk swaps (fade from 0) -> no fade on follow-on chunks; QC event frames
  used round(start*fps) instead of cumulative frame counts -> fixed; tracked labels smoothed +-3 frames and faded at
  frame edges (a label popped off at the edge); tightrope "stepping" label -> chip (it jiggled with the walker);
  altitude shot re-framed (planes were off-screen / too low) and bar labels were cropped -> fixed; card moved to 15 %.
- Final flicker: overlay-only stream 0 unexpected spikes / 0 A-B-A in all four bands. Final-only A-B-A while a label
  moves: 28 frames in the mid band (hook prop behind the CIRRUS label, tightrope walker wobble near "EASY MIDDLE"),
  checked 1:1: no blink. Raw region A-B-A on the final is high everywhere because of camera motion (3D-only stream
  has more), and px-flicker comes from fast cloud motion in the outro crane and the speed streaks (same in 3D-only).
- Disk: frames_v2 914 MB (JPEG); 19 GB free after A.

**Not done**: video B render/QC (on hold for Irfan's review of A). B's episode.json already holds the v2 shot plan
(`episode.v1.json` = old). The 10k city buildings are now merged into one mesh, but this build time is NOT measured yet (first version
with one object per building took 36 min); no B still has been looked at yet.

# "bridges in war" rendered in v2, 23 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). Nothing committed, pushed or posted.
- Voice: cached Orus beats re-joined with `trim_pauses` + 0.2 s gaps -> 80.66 s (was 88.7 s). No new TTS calls.
- City build time measured: 41-100 s per job (merged-mesh city), so no further build work needed.
- City world fixes (`scene_lib_v2_city.py`): `far_ground` sat at z -4 above the water (-7) and buried the whole river
  -> moved below the river bed with its own strong haze; fog 0.00016 -> 0.000045 (start 1200); `horizon_haze()` blends
  the HDRI below ~2.5 deg to the fog colour for camera rays (hid the HDRI's dark tree line); far hills removed (read as
  floating discs); hit/teal rings were edge-only circles + WIREFRAME = no geometry -> `_annulus()`; `clear_trees()`
  on low camera paths; utility/pontoon/outro cameras moved to the promenade edge; pontoon camera closer.
  (`scene_lib_v2_air.py` line ~347 uses the same circle+WIREFRAME pattern: probably invisible too, not touched.)
- Episode: hook camera reframed (all three hit bridges in frame), hook chip y 0.74, `sun_az` 60 on beats 1-2
  (sun glint blob on the water).
- `overlay_v2.py` Card: panel top pinned at 12.6 %; a multi-line title with a `sub` is joined to one line when it fits;
  sub line 30 px under the panel with an assert that it stays clear of the captions.
- Render 3010 s wall (3 procs) + 3-beat re-render; qc_v2 PASS, qc_full auto PASS, all 6 sheets reviewed.

# "stock market crash" built in v2, 23 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). Nothing committed, pushed or posted.
- New `pipeline/blender/scene_lib_v2_market.py` (registered in `render_episode_v2.load_builders`): financial plaza
  carved into the river-city downtown (`build_city_blocks(exclude=...)`, RNG draws kept so the city is otherwise
  identical), index wall + side screens (emissive candles only), giant 3D line, marble stair sculptures with glass
  elevators, fountain + gold coin stack, domino row. Builders: market_hook, stairs_elevator_v2 (drop / long),
  bubble_v2 (inflate / pop -> confetti), dominoes_v2, market_outro (outro switched from city_outro).
- Blender 5.3 ignores the keyframe interpolation preference used by `L.kf()` -> CONSTANT show/hide keys faded in
  (candles/lines visible early). Fixed in the market module with explicit `_set_const()`. Other v2 libs that rely
  on CONSTANT keys (city barrier dashes, hit rings) are probably affected the same way: not touched.
- Voice (Sadaltager): "Here are the three big reasons." moved from the bubble beat to the end of the question beat
  (the teaser start made the TTS read the director notes 3x, same words). The forced beat TTS repeated its last
  sentence 4 times in a row -> trimmed after the first "dominoes" (backup `beat_forced.wav.repeat.bak`); a lip click
  at its start attenuated (`.click.bak`). 83.37 s total. Forced beat topple cue "triggers" -> "drop".
- Render: 2039 s wall (21 jobs, 3 procs) + re-render of beats 1/5/7 865 s after the sheet review (ball in caption
  band, domino camera, takeaway camera showed the wall behind the card). qc_v2 PASS, qc_full auto PASS, 6 sheets reviewed.

# "Thanksgiving travel" + "Russian plane crash" built in v2, 23-24 Nov 2026

Builder: Opus sub-agent (plain Agent tool, so xhigh effort could not be pinned). Nothing committed, pushed or posted.
- New `pipeline/blender/scene_lib_v2_travel.py`: airport world + six-lane interstate (x 1720, `highway.png` added to
  `v2_textures.py`), overpass, text-free sign gantries, corridor trees; hills removed + `horizon_haze()` (dark HDRI
  tree line gone). Fast traffic: `fast_car()` (Kenney parts + shared lamp meshes, optional brake glow + red road pool),
  `set_keys()` (foreach_set, explicit interpolation), Newell car-following wave for the phantom jam. 8 builders.
- New overlay type `board` (departures board, split-flap status flips on cues) in `overlay_v2.py`.
- New `pipeline/blender/scene_lib_v2_winter.py`: snowy Siberian-style airfield (instanced 50 m taiga patches + mottled
  far-forest ground, villages, hangars, snow banks), original high-wing four-turboprop transport (no markings), lit
  maintenance-hangar set. 8 builders. Both modules registered in `render_episode_v2.load_builders()`.
- `scene_lib_v2_air.ring_pulses` (WIREFRAME rings) was not used, so not touched.
- A (Fenrir, 87.97 s): TTS hook read the director notes 3x with a "Pronunciation: 81.5 million" line and a
  "This Thanksgiving" opener -> notes trimmed to "AAA = Triple A" and hook reordered; generated once by hand.
  Render 2579 s wall (23 jobs, 3 procs) + re-renders of hook (plane closer), gates (side camera), dominoes, outro.
- B (Orus, 78.58 s): render 2183 s wall (20 jobs) + outro re-render (camera now tracks the plane; "FLYING SINCE 1957"
  big panel hid the plane -> chip). qc_full flagged a 0.9 s pause at the end of beat_tradeoff (trailing silence with
  a blip): beat wav cut at 8.10 s (backup `beat_tradeoff.wav.tail.bak`).

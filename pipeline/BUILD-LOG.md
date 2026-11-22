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

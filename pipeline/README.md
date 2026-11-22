# Explainer video pipeline (Blender + Gemini TTS)

One `episode.json` in, one finished 9:16 reel out. Everything is procedural (no footage) except the cars, which are
Kenney Car Kit GLB models (CC0, `assets/kenney-car-kit/`, credited in `assets/CREDITS.md`).

```
.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json
```

Output:
- `output/<keyword>.mp4` (1080x1920, 30 fps, captions burned in, voice at about -14 LUFS)
- `output/<keyword> fb.mp4` (Facebook upload copy: HEVC `hvc1` + mono AAC, always under 10,000,000 bytes)
- `output/<keyword>.post.md` (title, FB caption, hashtags, engagement comment, posting checklist, sources, script)
- `output/<slug>/` working dir: `audio/`, `captions/`, `captions.json`, `frames/`, `segments/`, `logs/`, `stills/`, `qc/`

## Channel voice & script style (decided 22 Nov 2026 — use for EVERY new episode)

- `tts.voice`: rotate **`Orus`**, **`Fenrir`**, **`Sadaltager`** (chosen by Irfan). Pick the one that suits the topic:
  Orus = firm/authoritative (war, politics, security); Fenrir = energetic (disasters, crashes, breaking news);
  Sadaltager = calm/knowledgeable (science, weather, how-things-work). Never use the same voice for two posts in a row
  (check the previous episode's `episode.json`). Do not use Charon or Iapetus.
- `tts.director_notes` (start from this, then add a `Pronunciation:` line for names in the episode):
  > Male documentary-style news explainer for a US/UK social video. Confident, punchy and fast
  > (about 170–185 words per minute), conversational but serious. Short sentences, a brief dramatic
  > pause before key facts, lively intonation, never monotone or salesy.
- Script style (inspired by the reference reel's *style*, never copying its words or voice):
  short punchy sentences; hook = verified fact + a curiosity question; a numbered structure
  ("Here are the three big reasons. One… Two… Three…") where it fits; end with the comment
  question, a share CTA ("Send this to someone who…"), and a last line that loops to the hook.
- At ~180 WPM, 200–240 words ≈ 70–80 s; aim for **230–300 words** to stay inside 70–120 s.

## How to make a new episode (step by step)

1. **Copy the last episode folder**: `episodes/2026-11-23-1-highway-pileup/` to `episodes/<date>-<slot>-<slug>/`.
2. **Edit `episode.json`**:
   - `keyword`: the main keyword. This becomes the file name (`output/<keyword>.mp4`).
   - `slug`: same as the keyword but with dashes (used for the working folder).
   - `title`, `fb_caption`, `hashtags`, `sources`: the hook fact must be verified and its sources listed.
     List every figure used in the script in `sources`, with where it comes from.
   - `engagement_comment` (required for every post since 22 Nov 2026): a short question or poll-style prompt
     about the video that the Page posts under the reel. No links, not spammy. It is copied into `post.md`.
   - `beats`: the voiceover, split into 7–10 beats. Aim for **230–300 words in total** (about 75–100 s at Fenrir pace).
     - Beat 1 = the hook: the verified news fact in the first sentence, with no intro.
     - Middle beats = the general explainer ("usually", "could", "often"); never say what caused the real event.
     - A metaphor beat (dominoes, etc.).
     - A takeaway beat (practical safety advice).
     - The last beat = a question for the comments, and a last line that loops back to the hook.
   - Each beat has a `shot`: `{"builder": <name>, "params": {...}}`. Available builders are listed below.
   - Leave `tts`, `render`, and `music: null` as they are, unless you have a reason to change them.
3. **Run it**: `.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json`. It takes about 12–13 min: about 11 min of render with 4 parallel Blender processes, plus about 1 min of assembly.
   - To run steps one by one, use `--steps tts`, `--steps captions`, `--steps render`, `--steps assemble,fb,post`.
   - The default steps are `tts,captions,render,assemble,fb,post`. `fb` re-encodes the final mp4 to HEVC with a
     bitrate computed from the duration (target about 9.3 MB) and re-encodes lower if it is still >= 10 MB.
   - **Check `audio/timings.json` total (70–120 s) right after `--steps tts,captions`, before any rendering.**
   - To re-do one beat's voice, delete `output/<slug>/audio/beat_<id>.wav`, then run `--steps tts,captions`.
   - To re-render one shot, delete `output/<slug>/frames/NN_<beat>/`, then run `--steps render,assemble`.
     If you change the voice/timings, delete **all** of `frames/`, because the shot lengths change.
4. **Preview shots before the full render**. This is cheap, at about 1 s per still:
   ```
   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P pipeline/blender/render_episode.py -- \
       episodes/<id>/episode.json output/<slug> <SHOT_INDEX> --still 60,200 --scale 0.5
   ```
   The stills go to `output/<slug>/stills/`. Open and look at them.
5. **QC**:
   - `ffprobe` should show a duration of 70–120 s, 1080x1920, and an audio stream.
   - Grab about 6 frames (`ffmpeg -ss T -i out.mp4 -frames:v 1 qc/T.png`) and look at them.
   - Check that the captions match the speech (`captions.json` → `alignment` shows what whisper heard).

## Builders (`pipeline/blender/scene_lib.py` → `BUILDERS`)

| builder | what it shows | params |
|---|---|---|
| `fog_highway` | queue of stopped cars, blinking hazards, dense fog, one car arriving slowly | `cars`, `fog` (0–1+), `card`, `subcard`, `camera`: `dolly_in` / `crane_up`, optional `models` (list of Kenney model names) |
| `chain_topdown` | top-down column of cars braking one after another (brake lights ripple back) | `cars`, `card` (appears on the word "chain") |
| `visibility` | chase cam in thick fog, teal "~50 m" marker, hazard-lit car emerging | `distance_label`, `card`, `subcard` |
| `stopping_distance` | reaction strip (teal) then braking strip (red) grow as a car stops | `reaction_m`, `braking_m`, `card`, `subcard` (syncs on the words "reaction", "braking", "seventy") |
| `following_gap` | tailgating car, shrinking red gap bar, late braking, cars end touching (no damage) | `card` (syncs on "stops") |
| `ice_road` | dry lane vs icy lane braking side by side | `card`, `subcard` |
| `dominoes` | row of dominoes toppling in sequence | `count` (starts on the word "brakes") |
| `safety_tips` | night fog drive, lights on, "4+ SEC" gap, numbered tips | `tips` (list), `cues` (list of words that trigger each tip) |
| `japan_map` | stylised low-poly Japan (hand-drawn lon/lat outlines) on a navy sea with a lat/lon grid | `mode`: `hook` (zoom to a pulsing epicentre, amber "felt" rings on "shaking", AICHI/NAGANO/GIFU labels on their words), `dots` (small quake pulses along the plate boundaries; card on `cue`), `plates` (boundaries draw in, plate names pop on "pacific"/"philippine"/"eurasian"/"north", motion arrows), `outro` (pull out from the epicentre); `card`, `subcard` |
| `subduction` | cross-section: ocean plate (moving chevrons) dives under a land plate; contact glows red on "stuck", land edge is dragged down, STRAIN meter fills from "strain" | `card` |
| `ruler_snap` | a plastic ruler clamped to a desk bends further (turns red, "STORING ENERGY") and snaps back on `cue`, wobbling; teal seismic rings, again on "waves" | `card`, `cue` (default "snaps") |
| `quake_depth` | crust block cross-section: fault cracks light up on "faults", a deep focus + dashed depth line + `depth_label` on `cue_depth`, rings spread, houses sway gently, "WIDER, BUT WEAKER" on "wider" | `card`, `subcard`, `depth_label`, `cue_depth` |
| `base_isolation` | ground shakes (from "codes"): rigid tower sways with it, tower on amber rubber pads barely moves; labels on `cue` | `card`, `cue` (default "rubber") |
| `phone_alert` | phone over a dark map; on `cue` it shows EARTHQUAKE EARLY WARNING + 5-4-3-2-1, then TAKE COVER as the ring from a distant epicentre arrives | `card`, `cue` (default "warning") |
| `drop_cover` | mannequin next to a table in a gently shaking room: crouches (head up, never lying down), moves under the table, holds a leg; numbered cards | `steps` (3 labels), `cues` (3 words) |

Shared helpers for these (in `scene_lib.py`): `add_mat()` (unique fading additive material: give every animated
ring its own name), `prism()` (extruded 2D polygon; `xz=True` for cross-sections), `ribbon()` (flat line strip),
`wave_ring()` / `pulse_rings()` (expanding fading rings), `vis()` (hard show/hide by scale), `ll()` (lon/lat → map),
`house()`. Map outlines are in `HONSHU`, `HOKKAIDO`, `KYUSHU`, `SHIKOKU`; schematic plate boundaries in `BOUNDS`.
Do not draw plate boundaries next to a real epicentre in hook/outro shots (that would imply a cause).

**Cars (v1.1, Kenney Car Kit)**: `make_car(name, color, loc, rot_z, cam=..., hazard_mat=True, brake_glow=True, model=None)`
builds a car from a Kenney GLB (imported once per shot, then linked duplicates). With `model=None` it draws a
seeded, weighted mix of civilian cars: `sedan`, `suv`, `hatchback-sports`, `suv-luxury`, `van`, `sedan-sports`,
`taxi`, `delivery` (same mix every time a shot is rebuilt). `color` is ignored (paint = Kenney colours, desaturated).
Every model is normalised to the old car contract: faces +Y, origin at ground centre, bumpers at ±2.2 m
(`CAR_LEN` 4.4 m), width `CAR_W` 1.9 m, so bumper/gap maths in builders still works.
Never use `debris-*` models (non-graphic rule). Emergency vehicles only when a shot asks: `fog_highway` takes an
optional `models` param, e.g. `"models": ["police", "sedan"]` (lamp positions for unlisted models are estimated,
so preview a still). Wheels spin automatically in `drive()`; hazards (`hazard_mat=True`) blink with a per-car phase.
Tunables at the top of the car section: `CAR_W`, `CAR_H_SCALE`, `PAINT_SAT`, `PAINT_VAL`, `CIVILIAN` weights, `LAMPS`.

**Syncing visuals to the voice**: inside a builder, `ctx.word_time("word", default_frac)` returns the
frame where that word is spoken in this beat (from `captions.json`). If the word is not found, it falls back to
`default_frac × shot length`.

**Adding a new builder**: write `def b_name(ctx, p):` in `scene_lib.py`. It must call `fog(...)`,
`setup_world(...)`, add a light, and call `ctx.camera(...)`. Add your objects, then keyframe them with
`kf()` / `drive()`. Add on-screen text with `ctx.card()` / `ctx.text()`; these stay in the upper safe area
(y ≈ 0.13–0.40). Register the builder in `BUILDERS`.

## Rules baked into the pipeline
- **Captions**: the text comes from the script, and the timings come from faster-whisper `base.en`. Chunks are 2–4 words,
  Arial Black with a dark outline. They are centred at y=1290 px, and the code asserts they stay inside the
  12%–80% safe band. Words with digits are shown in yellow.
- **TTS prompt format**: use `### DIRECTOR'S NOTES ... ### TRANSCRIPT <text>`. A plain "Say in a … tone:"
  prefix gets **read aloud** by `gemini-3.8-flash-tts`, and `system_instruction` is rejected. `tts.py` runs a
  whisper check after each beat and retries if extra words were spoken. Since video #2 the check also fails on
  director-note words heard anywhere ("salesy", "intonation", …) or a word-sequence match below 0.7, because the
  TTS once replaced the second half of a beat with the notes at about the same length.
- **TTS rate limit**: `gemini-3.8-flash-tts` allows 10 requests/min. `tts.py` paces calls 7 s apart and, on a
  rate-limit 429, waits 30–90 s and retries the same model (a billing/plan 429 still stops with exit code 2).
- **Visuals**: keep them non-graphic. No injured people, wreck damage or fire. Cars may stop and touch abstractly.
- **Secrets**: the key comes from `.env` via python-dotenv and is never printed. `output/` is gitignored.

## Files
- `make_episode.py`: the orchestrator (tts → captions → render → assemble → post).
- `tts.py`: Gemini TTS per beat. It joins the beats with 0.3 s pauses and writes `timings.json` (shot boundaries) and `usage.json`.
- `captions.py`: alignment, chunking, caption PNGs and the `list.ffconcat` overlay stream.
- `blender/render_episode.py`: builds and renders one shot in headless Blender (resumable PNG frames).
- `blender/scene_lib.py`: the materials (shader distance fog, glow billboards), Kenney car loader (`make_car`), road, camera-locked cards, and builders.

## Geo / politics explainer builders (`pipeline/blender/scene_lib_geo.py`, added 22 Nov 2026 for video #3 "nuclear weapons")

These builders live in a separate module so `scene_lib.py` stays untouched. `render_episode.py` imports
`scene_lib_geo` lazily (only when a shot's builder is not already in `scene_lib.BUILDERS`), and the module
registers itself with `L.BUILDERS.update(GEO_BUILDERS)`. Do not reuse these names in `scene_lib.py`.
All visuals are neutral and symbolic: no weapons, explosions, war imagery, faces or caricatures. Country accent
colours are fixed (`C_US` blue, `C_RU` white, `C_CN` gold) so the same country looks the same in every shot.

| builder | what it shows | params |
|---|---|---|
| `globe_summit` | abstract globe (lat/long grid, no coastlines); US, China, Russia markers light up on their cue words, a red Shenzhen pin drops and arcs link the three to it; slow camera drift + push-in | `card`, `subcard`, `cues` (3 words: US, China, Russia order), `pin_cue` |
| `round_table` | round table, three empty chairs with colour bands, flags as simple colour blocks (US / China / Russia), an unsigned document | `card`, `card_cue`, `subcard`, `sub_cue`, `camera`: `orbit` / `crane_up` |
| `treaty_doc` | treaty document on a desk; a red rotated stamp slams on at the cue word | `title`, `doc_sub`, `stamp` (may contain `\n`), `stamp_cue`, `card`, `after` (red chip), `after_cue` |
| `cap_bars` | US + Russia bars rise, a teal ceiling slab descends and caps both | `card`, `card_cue`, `cap_label`, `cap_sub`, `cap_cue` |
| `verify_checks` | grid ground with abstract sites; two sheets swap sides (data exchange), clipboard + tick (inspection), satellite with scan cone | `items` (top cards, swapped on `item_cues`), `icons` (3 chips), `icon_cues` |
| `three_balance` | balance board on a point: two blocks rock; on the cue a third block drops in and the board wobbles on two axes | `card`, `card2`, `third_cue` |
| `stock_bars` | bars shrinking left→right (relative heights only, no numbers), trend line, last bar's lower part becomes the US + Russia share | `card`, `heights`, `first_label`, `last_label`, `drop_label`, `drop_cue`, `split_label`, `split_cue`, `split_frac` |
| `three_lower` | three coloured pillars on a stage; teal check beams link every pair, then all three sink together in steps | `card`, `subcard`, `check_cue`, `lower_cue` |
| `risk_gauge` | semicircular gauge red→teal; needle swings from HIGH to LOW on the cue; chips tick in | `card`, `gauge_label`, `chips`, `chip_cues`, `drop_cue` |

Helpers in the module: `_label()` (camera-facing 3D label that stays upright: use it instead of `label3d` when the
camera moves around the object; create the camera first), `_flag()`, `_polyline()` (bevelled curve; animate
`bevel_factor_end` to draw it), `_ring()`, `_rooted_box()` (box that grows upward when its root is scaled),
`_chip()` / `_sub()` (camera-locked text rows under the card; use y ≈ 0.22, 0.28, 0.34).

Facebook copy (`output/<keyword> fb.mp4`, HEVC under 10,000,000 bytes) for video #3 was made by hand with:
```
ffmpeg -i "output/<keyword>.mp4" -c:v libx265 -preset slow -b:v 600k -maxrate 900k -bufsize 1200k \
       -tag:v hvc1 -pix_fmt yuv420p -c:a aac -b:a 80k -ac 1 -movflags +faststart "output/<keyword> fb.mp4"
```
600k video + 80k audio stays under 10,000,000 bytes up to about 115 s; for longer videos lower `-b:v` to
(9,400,000 × 8 / duration − 80,000) / 1000 kbps. Check the byte size afterwards (91 s → 7.65 MB).

## Aviation + bridges builders (`pipeline/blender/scene_lib_air.py`, added 23 Nov 2026 for "plane crash" and "bridges in war")

Separate module, registered with `L.BUILDERS.update(...)`. `render_episode.py` imports it lazily, only when a
builder is in neither `scene_lib` nor `scene_lib_geo` (chained import, so a broken file never touches older episodes).
Non-graphic: aircraft are only shown flying, on approach or parked (never a crash, wreckage or fire); a "hit"
bridge only dims, gets a red marker ring and its traffic stops (no explosions, weapons, flags or side colours).

| builder | what it shows | params |
|---|---|---|
| `airport_scene` | small airport (runway + lights, PAPI, tower, hangars, fields, trees, hills, gradient sky + sun glow) | `mode`: `hook` (chase cam behind a light plane on approach, never touching down; `plane_label` on `label_cue`; `chips` on `chip_cues`) / `outro` (crane-up, plane flies away); `sky`: `golden`/`overcast`/`dusk`; `card`, `subcard`, `sub_cue` |
| `flight_profile` | altitude-vs-time line of a typical flight with a mini airliner | `mode`: `intro` (line draws, TAKEOFF/LANDING labels on their words) / `zones` (takeoff & landing slices go teal on `zone_cue`, red on `red_cue`); `card`, `card_cue`, `chip` |
| `altitude_margin` | high plane with a tall teal bar vs low plane over a runway with a short red bar | `card`, `card_cue`, `high_label`, `high_cue`, `low_label`, `low_cue` |
| `cockpit_workload` | airliner on approach; speed streaks, flaps down, gear down, radio rings on 4 cues; chips + 4-segment WORKLOAD meter | `card`, `card_cue`, `items` (4), `cues` (4) |
| `crosswind_approach` | airliner crabbed into a crosswind (red arrows), wind-shear down-arrows + dip, other traffic with a warning ring | `card`, `card_cue`, `chips` (3), `chip_cues` (3) |
| `tightrope` | walker with a balance pole crosses a rope between two towers; middle glows teal, ends red; chips | `card`, `middle_cue`, `on_cue`, `off_cue`, `map_cue`, `labels` (3 chips) |
| `seatbelt_sign` | cabin aisle (scaled x3 so camera cards are not hidden by the ceiling); FASTEN SEATBELT sign lights on `sign_cue`; chips; big card replaces them on `big_cue` | `card`, `sign_cue`, `chips`, `chip_cues`, `big`, `big_sub`, `big_cue` |
| `river_city` | low-poly city on two banks of a winding river, five bridges with traffic dots | `mode`: `hook` (3 bridges dim + red rings, traffic stops on `hit_cue`; `names` chips; `chip` on `chip_cue`) / `detour` (closed bridge, amber long detour route) / `outro` (wide crane-up); `card`, `subcard`, `sub_cue` |
| `river_barrier` | top-down map with a wide winding river | `mode`: `intro` (river edges glow on `chip_cue`) / `bridges` (red dashed barrier on `split_cue`, bridge nodes + converging arrows on `chip_cue`); `card`, `card_cue`, `chip` |
| `supply_funnel` | coloured supply dots converge through funnel lines onto one bridge, cross, spread out | `card`, `card_cue`, `items` (4), `item_cues` (4), `funnel_cue` |
| `utility_bridge` | one bridge with power / water / comms lines under the deck lighting up; on `dim_cue` flows stop, red ring, far-bank lights go dark | `card`, `card_cue`, `chips` (3), `chip_cues` (3), `dim_cue` |
| `history_cards` | two timeline cards (year, place, one neutral line) with an arch-bridge icon, rising on cues | `card`, `cards` ([[title "YEAR · PLACE", sub], ...]), `cues` |
| `pontoon_bridge` | big concrete bridge behind; pontoon segments float in and lock into a floating bridge, then traffic crosses | `card`, `card_cue`, `chip`, `chip_cue`, `mass_cue` |
| `arteries` | branching teal vessels with flowing dots; red pinch ring slows the flow; a bypass vessel draws in and the flow recovers | `card`, `pinch_cue`, `backup_cue`, `chip`, `chip_cue` |

Helpers: `make_light_plane(ctx, name, accent, scale)` (nose +Y, spinning prop), `make_airliner(ctx, name, scale, gear)`
→ `(root, {"flaps": hinges, "gear": groups})`, `_sky()` gradient dome + `_sun_glow()`, `_runway()`, `_slab()` (extruded
polygon in xy/yz/xz), `_movers()` (dots looping along a polyline, with slow-down/stop), `_bridge()`, `_hit_marker()`.
Camera-locked cards sit 2 m from the lens: interiors smaller than that (cabins) must be scaled up or the geometry hides the cards.
TTS note: a beat starting with a short teaser sentence ("Here's the surprising part.") made the model read the
director notes aloud 4 times in a row; start beats with the content sentence instead.
Gotcha: `L.box()` / `L.plane()` call `transform_apply()`, which bakes the **location** into the mesh too. A "source"
box built far away (e.g. z=-5000) and then copied (`obj.copy()` / shared mesh) puts every copy 5 km underground.
Build sources at the origin and delete them after copying (as `_city()` does).

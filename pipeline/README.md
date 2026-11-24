# Explainer video pipeline (Blender + Gemini TTS)

One `episode.json` in, one finished 9:16 reel out.

> **Since 23 Nov 2026 every new episode uses the v2 look (Irfan's ruling: never below v2 quality).**
> v2 = bright daytime worlds lit by a Poly Haven HDRI, Poly Haven PBR textures, smooth models, and **all text drawn
> as 2D overlays after rendering** (no 3D text in Blender). Read "v2 pipeline" below before building an episode.
> Old navy-look episodes carry `"pipeline": "v1"` in their `episode.json` and still render with the v1 code.

```
.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json
```

Output:
- `output/<keyword>.mp4` (1080x1920, 30 fps, captions burned in, voice at about -14 LUFS)
- `output/<keyword> fb.mp4` (Facebook upload copy: HEVC `hvc1` + mono AAC, always under 10,000,000 bytes)
- `output/<keyword>.post.md` (title, FB caption, hashtags, engagement comment, posting checklist, sources, script;
  an existing one is kept — pass `--force-post` to regenerate it)
- `output/<slug>/` working dir. v2: `audio/`, `captions.json`, `tex_v2/`, `frames_v2/NN_<beat>/####.jpg`,
  `tracks_v2/` (anchor positions for labels), `segments_v2/`, `logs_v2/`, `stills_v2/`, `qc/` (qc_sheet.png, qc_v2.json)

## v2 pipeline (DEFAULT for every new episode)

Steps (`--steps`, default `tts,captions,textures,render,assemble,fb,post,qc`):
1. `tts`, `captions`: as before (Gemini TTS per beat, faster-whisper timings -> `captions.json`). To rebuild only the
   visuals of an episode keep the voice: `--steps textures,render,assemble,fb,post,qc`.
2. `textures`: PIL runway / taxiway / road / parking textures with the markings baked in (`pipeline/v2_textures.py`).
3. `render`: `pipeline/blender/render_episode_v2.py`, one queue of frame-range jobs (<= 150 frames each), `parallel`
   (3) Blender processes at a time; each job builds the beat's whole world (about 45 s) and renders q95 JPEG frames.
   Resumable: existing frames are skipped. The builder's anchors (3D points labels follow) go to `tracks_v2/`.
   About 1.2-4 s per frame per process at 24 samples; a 90 s episode takes about 60-80 min. **Never run two
   episodes' renders at the same time** (RAM: 16 GB).
4. `assemble`: `pipeline/overlay_v2.py` composites captions + the beat's `overlays` on every frame with PIL
   (beats in parallel) -> `segments_v2/`, concatenated, voice loudness-normalised and muxed.
5. `fb`: HEVC upload copy < 10 MB. 6. `post`: keeps an existing `.post.md`.
7. `qc`: `pipeline/qc_v2.py` -> ffprobe, flicker per band (card / caption / mid / low; 0 A-B-A reversals and 0
   unexpected spikes required in card, caption and low), 12 frames + `qc/qc_sheet.png` with the 12 %/80 % guides.
   **Open `qc_sheet.png` and look at it**: no void or plain navy backgrounds, nothing graphic, captions readable,
   labels not on top of captions.
8. **Full-video QC (mandatory, Irfan 23 Nov 2026: "QC is not just flicker — check the WHOLE video")**:
   `.venv/bin/python pipeline/qc_full.py <episode.json> "output/<keyword>.mp4" output/<slug>/qc`
   Auto: format/duration/FB size, black & frozen frames, loudness/clipping, clicks, pauses > 0.75 s,
   spoken words vs script (whisper WER). Then **open EVERY sheet in `qc/full/` (1 frame every 2 s by default; `QC_STEP=1` for 1 frame/s)** and check:
   empty/plain backgrounds, glitches/dark blobs/z-fighting, text overlapping text or cut off, cards above the 12 % line
   or below 80 %, labels pointing at the wrong thing, spelling, visuals matching the words, anything graphic or
   insensitive, objects popping or vanishing. Fix and re-run until auto = PASS and every frame is clean.
   **QC tiers (Irfan, 24 Nov 2026 — save tokens; repair only what matters):**
   - **MUST FIX before posting:** wrong/unverified/fabricated facts or narration (e.g. an invented TTS line);
     spelling or wrong numbers in on-screen text; black/broken/frozen frames or visible flicker; audio glitches
     (clipping, cut-off words, stray voice/noise); pauses > ~1.2 s or dead air; text unreadable or overlapping the
     captions; policy risk (graphic content, investment advice, defamation); caption/hashtag/AI-label problems.
   - **SKIP (log one line, no repair):** minor visual artifacts under ~1 s; whisper mishearings when the audio is
     fine; pauses 0.75–1.2 s; small cosmetic imperfections and optional upgrades. Never spend a re-render or another
     QC cycle on a skip item. (qc_full's 0.75 s pause flag is informational up to 1.2 s.)
   Known v2 issues to avoid (from the plane crash review): two-line outro card poking above 12 %; "Tell us in the
   comments" sub-line touching the caption; a dark smudge on the far horizon in the outro wide shot (1:24–1:27).

Preview a shot before the full render (about 1 min each, mostly world building):
```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P pipeline/blender/render_episode_v2.py -- \
    "$PWD/episodes/<id>/episode.json" "$PWD/output/<slug>" <SHOT_INDEX> --still 40,200 --scale 0.5 --samples 12
.venv/bin/python pipeline/overlay_v2.py episodes/<id>/episode.json --beat <SHOT_INDEX> --preview 1.3,6.6 --out /tmp/prev
```
(the overlay preview uses `stills_v2/` when frames are not rendered yet; anchored labels need rendered tracks).
Re-render one beat: delete `output/<slug>/frames_v2/NN_<beat>/` and its `tracks_v2/NN_<beat>_*.json`, then
`--steps render,assemble,fb,qc --only-shot NN`. Change only overlays/text layout: just `--steps assemble,fb,qc`.

### v2 rules (all builders, all episodes)
- **No 3D text.** Titles, chips, labels, numbers, years, captions = `shot.overlays` (2D). 3D graphics (rings, route
  ribbons, glowing streams, bars) are fine.
- **Never a void.** Outdoor shots call `S.daylight(ctx, ...)` (HDRI sky + sun) and build a full world (ground,
  buildings, trees, hills). Interiors get their own lit set (see `cabin_v2`). Never the plain navy v1 background.
- Keep the top 22-31 % (caption band) over sky or calm background; aim the camera so fine detail (fences, distant
  windows) is not behind the captions.
- Non-graphic: aircraft only fly / take off / approach / sit parked; a "hit" bridge only dims + red ring + traffic
  stops; no wreckage, fire, explosions, injured people, weapons, flags or side colours.
- Persistent worlds: every beat of an episode builds the same world (`S.build_world` airport,
  `scene_lib_v2_city.build_city_world` river city) so the video feels like one place.

### `shot` block (v2)
```json
"shot": {"builder": "airport_hook", "params": {...},
         "render_scale": 0.5, "samples": 16,           // optional: half-res plates that the overlay blurs
         "overlays": [ {"type": "card", "text": "TITLE", "sub": "sub line", "at": 0.25},
                       {"type": "label", "text": "CIRRUS SR22", "anchor": "plane", "cue": "cirrus"},
                       {"type": "chips", "items": ["A", "B"], "cues": ["worda", "wordb"]} ]}
```
Overlay types (`pipeline/overlay_v2.py` docstring has every key): `card` (title at 13.5 %, optional `sub`,
`sub_cue`), `chips` (pills from 65.5 % down, `style` dot/check, `y`), `label` (pill + leader line following a builder
anchor, `dx`/`dy`/`delay`/`color`), `bar` (measuring bar between two anchors), `big` (big number panel), `meter`
(segmented meter), `profile` (flight-profile graph), `history` (timeline cards), `blur` (blur + dim the plate).
Timing: `cue` = word (prefix) spoken in this beat, `at` = seconds into the beat, `until` = when it fades out.
Layout bands are asserted in code: card 12-20 %, captions 22-31 %, labels/graphs 32-64 %, chips 64-80 %.
Captions: top centre (26 %), white Avenir Next Bold with soft shadow, current word Heavy on a red highlight.

### v2 builders
Shared look library `pipeline/blender/scene_lib_v2.py`: `daylight()` (HDRI `assets/polyhaven/hdri/` + extracted
sun, procedural sky fallback), `ph_detail()` (Poly Haven PBR detail on any material), `pbr()`, `image_mat()`,
`facade_mat()`, `build_world()` (airport, suburbs, city, hills, traffic), `make_plane_v2()`, `anchor()`.

| builder (module) | what it shows | anchors | params |
|---|---|---|---|
| `airport_hook` (`scene_lib_v2_air`) | light aircraft on a stable approach, camera pulls back to reveal the airport | plane | `speed`, `y1`, `sun_az` |
| `airport_plate` | airliner climbing out of the airport (half-res plate for graphs) | plane | `view`: climb_a / climb_b |
| `altitude_margin_v2` | side-on long-lens: high airliner vs one on short final (bars drawn by overlay) | high, high_g, low, low_g | `high_z`, `dist`, `lens` |
| `cockpit_workload_v2` | airliner on approach from below: speed streaks, flaps, gear, radio rings on 4 cues | plane | `cues` |
| `crosswind_v2` | crabbed short final, wind streaks, dip on shear cue, light aircraft on the taxiway with amber rings | plane, traffic | `wind_cue`, `shear_cue`, `traffic_cue` |
| `tightrope_v2` | walker on a rope between platforms in a sunny meadow; rope middle teal / ends red | mid, end, walker | `middle_cue`, `on_cue` |
| `cabin_v2` | bright airliner cabin, seatbelt pictograms light up | – | `sign_cue` |
| `airport_outro` | airliner take-off and climb, camera cranes up over the field | plane | `cam_path`, `lens` |
| `city_hook` (`scene_lib_v2_city`) | river city aerial; listed bridges dim + red rings, traffic stops on `hit_cue` | br_<key> | `hit_cue`, `hit` (bridge keys) |
| `city_wide` | high view of the city split by the river; `mode` barrier: red dashed river line + teal bridge rings | – | `mode`, `split_cue`, `bridges_cue`, `cam0/1`, `tgt0/1` |
| `supply_funnel_v2` | vans/trucks converge on one bridge along amber route lines | bridge | `bridge`, `start_cue`, `funnel_cue` |
| `utility_bridge_v2` | low riverside view, power/water/comms lines with pulses under a deck; stop + dim on cue | bridge | `bridge`, `cues`, `dim_cue` |
| `detour_v2` | closed bridge + amber detour route via the next bridge | closed | `closed`, `alt`, `detour_cue` |
| `city_plate` | arch bridge from the promenade (half-res plate for history cards) | – | `bridge` |
| `pontoon_v2` | pontoon segments float in and lock into a bridge, then cars cross | pontoon | `float_cue`, `mass_cue` |
| `arteries_v2` | glowing traffic streams; pinched bridge slows the flow, teal bypass on cue | pinch | `pinch`, `bypass`, `pinch_cue`, `backup_cue` |
| `city_outro` | crane-up over the river city | – | `cam0`, `cam1` |
| `market_hook` (`scene_lib_v2_market`) | financial-district plaza in the river city's downtown: giant glowing 3D line climbs in front of the index wall, plunges red on `drop_cue`; wall / side screens' candles flip red (side screens on `left_cue` / `right_cue`); camera pulls back | line_top, line_low | `drop_cue`, `left_cue`, `right_cue`, `cam0/1`, `tgt0/1` |
| `stairs_elevator_v2` | `mode` drop: glowing price ball hops up a marble staircase and rides a glass elevator straight down on `drop_cue`; `mode` long: long staircase with three short elevator drops, red strips light on `name_cue` | ball | `mode`, `drop_cue`, `name_cue`, `cam0/1` |
| `bubble_v2` | soap bubble tethered to a gold coin stack ("profits") over the plaza fountain; `mode` inflate (grows on `grow_cue`) / pop (red paper plane touches it on `pop_cue`, pops into confetti) | bubble, profit, news | `mode`, `grow_cue`, `profit_cue`, `pop_cue` |
| `dominoes_v2` | ~70 big lacquered dominoes in a curving row on the plaza; topple one after another from `topple_cue` (step fitted to the beat) | first, last | `topple_cue`, `step` |
| `market_outro` | crane-up from the index wall over downtown to the river | – | `cam0/1`, `tgt0/1` |
| `travel_hook` (`scene_lib_v2_travel`) | high aerial along the busy interstate (both directions moving) beside the airport-world suburbs; airliner climbs across the sky | car, plane | `y_range`, `car_y`, `plane_a/b`, `cam0/1`, `tgt0/1` |
| `taxi_queue_v2` | airliners nose-to-tail on the taxiway creeping to the runway (stop-and-go), one takes off behind | queue | `count`, `to_frame` |
| `phantom_jam_v2` | dense northbound traffic; one driver brakes on `brake_cue`, a Newell car-following wave of brake lights (+ red light pooling on the road) rolls back towards the camera; southbound flows | first | `brake_cue`, `y0`, `ve`, `tau`, `delta` |
| `long_drive_v2` | chase cam behind one car on the open interstate, slowly closing on the car ahead (tailgating, no contact); its brake lights flash on `brake_cue` | lead | `brake_cue`, `speed`, `hero` |
| `gates_v2` | three airliners nose-in at the terminal gates, side view; the middle one is pushed back on `push_cue` | push | `gates`, `push_cue` |
| `delay_dominoes_v2` | big white dominoes (navy pips) along the taxiway topple from `topple_cue`; amber ground rings on `ring_cue` | first | `topple_cue`, `ring_cue`, `path`, `step` |
| `smooth_flow_v2` | camera travels with light, well-spaced traffic; anchors for a 2D gap bar | gap_top, gap_bot | `speed`, `y0`, `cam_off`, `tgt_off` |
| `travel_outro` | crane-up from beside the interstate to a wide view; airliner climbs across | – | `cam0/1`, `tgt0/1` |
| `cargo_hook` (`scene_lib_v2_winter`) | original generic high-wing four-turboprop transport (no markings) cruising over snowy taiga, side-rear chase cam | plane | `x`, `y0`, `z`, `off0/1` |
| `cargo_plate` | the transport parked on the snowy apron (half-res plate for history cards) | – | – |
| `rough_strip_v2` | the transport taxiing on a packed-snow strip, props turning, low tracking cam | wing, engine, gear | `speed`, `y0` |
| `spares_v2` | spare-parts yard (crates, propellers on stands, engine on a cradle, tyres) with the transport behind | crates, engine | – |
| `old_fleet_v2` | row of six identical old transports parked in the snow | – | – |
| `hangar_check_v2` | lit maintenance hangar (own interior set), transport with yellow work platforms, teal inspection rings slide along the fuselage from `scan_cue` | tail, wing | `scan_cue` |
| `classic_car_v2` | same hangar, a Kenney sedan in front of the transport, camera pulls back | car | `model` |
| `cargo_outro` | the transport takes off from the snowy runway and climbs; camera cranes up | plane | `y0`, `v0`, `cam_path` |
| `harbour_hook` (`scene_lib_v2_sea`) | generic grey corvette moored at the naval pier; low sea drones race in with wakes, white splashes on `hit_cue`, ship lists and rolls over from `list_cue`; camera pulls back | ship | `hit_cue`, `list_cue`, `cam0/1`, `tgt0/1` |
| `harbour_wide` | view from the sea over the port: corvette rolled over by the pier (red ring), merchant ship at anchor gets a red ring on `merchant_cue` | ship, merchant | `merchant_cue`, `cam0/1`, `tgt0/1` |
| `drone_low_v2` | low tracking shot beside a sea drone skimming towards the port | drone | `speed`, `heading`, `start`, `off0/1` |
| `swarm_v2` | aerial: corvette under way, six drones fan in from the far side (amber rings on `swarm_cue`), two stopped by splashes on `guns_cue` | ship | `swarm_cue`, `guns_cue`, `ship`, `r0`, `cam_off0/1` |
| `waterline_v2` | low view of the hull from the water: red waterline strip draws on `line_cue`, drone runs in, splash + red ring on `hit_cue` | waterline | `line_cue`, `hit_cue`, `cam0/1` |
| `cutaway_v2` | corvette cut across its length with the sea cut too (teal section): `mode` flood (hole + inflow arrows, water rises, ship sits lower) / roll (water sloshes, leans, rolls over) | flood | `mode`, `flood_cue`, `lower_cue`, `slosh_cue`, `lean_cue`, `roll_cue` |
| `defend_v2` | breakwater head + lighthouse: yellow floating boom rises across the entrance on `boom_cue`, patrol boat, teal camera scan sector on `cam_cue`, drone stopped at the boom | – | `boom_cue`, `cam_cue`, `cam0/1` |
| `harbour_outro` | crane-up from the basin to a wide view of port, city and sea | – | `cam0/1`, `tgt0/1` |
| `storm_hook` (`scene_lib_v2_storm`) | tropical ocean from high above, white cloud spiral (real icosphere puffs) turning counter-clockwise; `mode` fade: rings shrink away from `fade_cue` | storm | `mode`, `fade_cue`, `rot0`, `spin_deg`, `cam0/1`, `tgt0/1` |
| `ocean_calm` | low glide over the calm tropical sea towards palm islands | – | `islands`, `cam0/1`, `tgt0` |
| `warm_cut` | sea cut open (warm orange surface layer): `mode` warm (heat arrows) / rise (moist-air arrows, cloud tower grows, red heat arrows, inflow arrows) / shear (upper winds tip the tower over and tear its top off) | warm, air, heat, inflow, shear, tower | `mode`, `warm_cue`, `rise_cue`, `cloud_cue`, `heat_cue`, `fast_cue`, `pull_cue`, `shear_cue`, `tip_cue`, `apart_cue` |
| `globe_spin` | big globe (numpy-drawn simplified continents) over the sea turning west to east, amber spin band, small Atlantic spiral turning counter-clockwise | storm, equator, band | `lon0/1`, `tilt`, `storm_lon/lat`, `turn_cue` |
| `eye_section` | storm cut in half: clear eye, eyewall, inflow / rising / sinking arrows | eye, eyewall, wall_l | `sink_cue` |
| `coast_calm` | calm port town of the harbour world (no warship), slow glide | – | `cam0/1`, `tgt0/1` |

Travel world (`scene_lib_v2_travel.build_travel_world`): `S.build_world` airport world + six-lane interstate at x = 1720
(texture `highway.png` from `v2_textures.py`), overpass, sign gantries without text, corridor trees, hills removed and
`horizon_haze()` (no dark HDRI tree line). Traffic uses `fast_car()` (Kenney parts, shared lamp meshes) and `set_keys()`
(foreach_set, explicit interpolation; Blender 5.3 ignores L.kf() CONSTANT). Overlay type `board` (departures board,
statuses flip on cues) was added to `overlay_v2.py` for it. Winter world (`scene_lib_v2_winter.build_winter_world`):
snow ground, runway with snow banks, hangars, tower, two villages, dense taiga as ~4,300 instanced 50 m forest patches +
a mottled "far forest" ground, snowy hills; `S.HAZE` is switched to a cold haze for that world.

Harbour world (`scene_lib_v2_sea.build_harbour_world`, "sea drones" 25 Nov 2026): sea z = 0 to the south (own
`sea_mat`), land north of y = 0 at `QUAY_Z` 2.5, rubble breakwaters with lighthouses, naval finger pier (corvette at
`SHIP_HOME`, bow south), container terminal with gantry cranes, warehouses, coast road with traffic and palms, a
sand-coloured flat-roofed city (one mesh), merchant ship at anchor, tugs; no far hills (dark smudges) and
`horizon_haze(hi=0.09)`. Models are original and generic (corvette without flags, numbers or weapons). Wakes are
foam strips a few cm above the water: keep the camera `clip_start` >= 1 m (20 m for high aerials) or they z-fight.
`cutaway_v2` cuts the sea plane at `CUT_Y` and draws a teal section face; the flood water is one clipped polygon
per 2 frames (world-level surface via `water_poly`), swapped with CONSTANT scale keys.

Storm world (`scene_lib_v2_storm.build_ocean`, "hurricane" 24 Nov 2026): tropical sea (own `ocean_mat`, less mirror-like
so it stays blue at grazing angles), optional cut at y = 0 with a self-lit warm-layer section, palm islands. Clouds are
icosphere clusters (`puffs`, `make_spiral`, `tower_mat` with a blue-grey rim so towers read against the HDRI clouds).
Looping arrows use `loop_move` (scale in/out at both ends, so the jump back is never seen). `horizon_haze(lo=0.02, hi=0.2)`
hides a building on the HDRI horizon that shows in north-facing sea shots. If the TTS leaves a pause > 0.75 s inside a beat,
cut the silence out of `audio/beat_<id>.wav` and re-run `--steps tts,captions` (only that beat's frame count changes).

Market plaza: `scene_lib_v2_market.build_market_world()` = `build_city_world` with `exclude_blocks` (city blocks
whose centre falls in a rect get no streets/buildings; random draws are kept so the rest of the city is unchanged)
+ paving, index wall, two side screens (emissive candles/grid only, no glyphs), 3D line, fountain, planters, both
stair sculptures and the domino row. Blender 5.3 ignores the new-keyframe interpolation preference that `L.kf()`
sets, so CONSTANT keys must be set explicitly (`_set_const()` in the market module) or show/hide keys fade.
Bridge keys (south -> north): `south` (cable-stayed), `rail` (truss), `paton` (girder), `metro` (low arch),
`north_arch` (big arch), `far_north` (girder). Names are overlay labels in episode.json, never 3D text.
New builders: add `def b_x(ctx, p)` to a `scene_lib_v2_*.py` module and register it in `S.V2_BUILDERS`; call
`S.daylight()` + a world builder, `ctx.camera()` (via `_cam`), and `S.anchor()` for anything a label should follow.
Preview stills at `--scale 0.5` and the overlay preview before any full render.

### Assets (v2)
`assets/polyhaven/` (CC0, gitignored; source URLs + sizes in its README): HDRI `kloofendal_48d_partly_cloudy` (2K),
`aerial_asphalt_01`, `aerial_grass_rock`, `concrete_floor_02` (1K diffuse / normal-GL / rough). If the folder is
missing, `daylight()` falls back to the procedural sky and materials to procedural noise (looks flatter: re-download).

### Files (v2)
- `make_episode.py`: orchestrator (branches on `episode.json` `"pipeline"`). `tts.py`, `captions.py`: shared with v1.
- `v2_textures.py`: PIL marking textures. `overlay_v2.py`: all 2D text + segment encode. `qc_v2.py` (+ `qc_flicker.py`): QC.
- `blender/render_episode_v2.py`: one beat / frame range in headless Blender. `blender/scene_lib_v2.py`: look library
  + airport world. `blender/scene_lib_v2_air.py`: airliner + aviation builders. `blender/scene_lib_v2_city.py`:
  river city + bridge builders.
- `v2_test.py`, `blender/render_v2_test.py`: the approved look test (23 Nov 2026), kept for reference.

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
  short punchy sentences; hook = verified fact + a curiosity question; the body uses ONE of the
  6 rotating narration styles below (no more "three big reasons, One… Two… Three…"); end with the
  comment question, a share CTA ("Send this to someone who…"), and a last line that loops to the hook.
- **Narration styles (Irfan, 24 Nov 2026, from the Fri 27 Nov set on):** the numbered "reason 1, 2, 3" list is
  retired. Every WJH script uses one of these 6 styles; Fable picks the one that fits the story best:
  1. **Domino**: a cause-and-effect chain, each step triggers the next ("It started with one loose bolt…").
  2. **Question ladder**: each answer opens the next "but why…?" question.
  3. **Start at the end, rewind**: open on the (non-graphic) aftermath, then go back ("12 minutes earlier…").
  4. **Minute by minute**: a real-time timeline with an on-screen clock as a 2D overlay (3:02 AM, 3:05 AM…).
     Only use real times that are verified with 2+ sources; otherwise label it as a typical/illustrative timeline.
  5. **Myth vs reality**: "Most people think X. It doesn't usually work that way." Myths must be real common beliefs;
     never claim to know the cause of the real event.
  6. **"If you were there"**: second person ("You're on the 30th floor. You have 4 minutes."), a general
     hypothetical scenario that ends in practical safety advice; never put the viewer inside the real victims' event.
  Rotation: no style repeats within one day's set of 3; cycle through all 6 before any is reused (check the
  "Style" column in `posting-log.md`). Write the chosen style at the top of `script.md` and in `episode.json`
  as `"narration_style"`. All other rules stay: verified hook with 2+ sources, explainer hedging ("usually",
  "could"), no casualty numbers, nothing graphic, neutral, 2D overlays, voice rotation, pauses ≤ 0.75 s, QC.
- At ~180 WPM, 200–240 words ≈ 70–80 s; aim for **230–300 words** to stay inside 70–120 s.

## How to make a new episode (step by step)

1. **Copy the latest v2 episode folder** (e.g. `episodes/2026-11-24-1-plane-crash/`, `"pipeline": "v2"`) to
   `episodes/<date>-<slot>-<slug>/`. Never copy a `"pipeline": "v1"` episode or an `episode.v1.json`.
2. **Edit `episode.json`**:
   - `keyword`: the main keyword. This becomes the file name (`output/<keyword>.mp4`).
   - `slug`: same as the keyword but with dashes (used for the working folder).
   - `title`, `fb_caption`, `hashtags`, `sources`: the hook fact must be verified and its sources listed.
     List every figure used in the script in `sources`, with where it comes from.
   - `engagement_comment` (required for every post since 22 Nov 2026): a short question or poll-style prompt
     about the video that the Page posts under the reel. No links, not spammy. It is copied into `post.md`.
   - `beats`: the voiceover, split into 7–10 beats. Aim for **230–300 words in total** (about 75–100 s at Fenrir pace).
     - Beat 1 = the hook: the verified news fact in the first sentence, with no intro.
     - Middle beats = the general explainer ("usually", "could", "often") told in the episode's narration style
       (see "Narration styles"); never say what caused the real event.
     - A metaphor beat where it fits the style (optional).
     - A takeaway beat (practical safety advice).
     - The last beat = a question for the comments, and a last line that loops back to the hook.
   - Each beat has a `shot`: `{"builder": <v2 builder>, "params": {...}, "overlays": [...]}` (see "v2 pipeline"
     above). All on-screen text goes in `overlays`; new topics usually need a new v2 builder in a `scene_lib_v2_*.py`.
   - Leave `tts`, `render` (`samples` 24, `parallel` 3), `pipeline: "v2"` and `music: null` as they are.
3. **Run it**: `.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json`. v2 takes about 60–90 min
   (render with 3 Blender processes) plus about 3 min of overlays/assembly/QC; run it in the background.
   - To run steps one by one, use `--steps tts`, `--steps captions`, `--steps render`, `--steps assemble,fb,post`.
   - The default steps are `tts,captions,render,assemble,fb,post`. `fb` re-encodes the final mp4 to HEVC with a
     bitrate computed from the duration (target about 9.3 MB) and re-encodes lower if it is still >= 10 MB.
   - **Check `audio/timings.json` total (70–120 s) right after `--steps tts,captions`, before any rendering.**
   - To re-do one beat's voice, delete `output/<slug>/audio/beat_<id>.wav`, then run `--steps tts,captions`.
   - To re-render one shot (v2), delete `output/<slug>/frames_v2/NN_<beat>/` + `tracks_v2/NN_<beat>_*`, then run
     `--steps render,assemble,fb,qc --only-shot NN`. If you change the voice/timings, delete **all** of `frames_v2/`
     and `tracks_v2/`, because the shot lengths change.
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

---

# v1 pipeline (old episodes, `"pipeline": "v1"` only — do not use for new episodes)

Everything below describes the v1 look (navy fog, 3D text cards). Keep it for re-rendering old episodes.

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

## Image generation (Irfan, 24 Nov 2026)
Always use `tools/gen_image.py` for any generated image (props, textures, thumbnails, logos). It uses the **Codex CLI** first (built-in image_gen, MCP disabled) and only falls back to Google Gemini (Nano Banana Pro) if Codex fails or its quota is depleted. Do not call the Gemini image API directly.

## Model split per video (Irfan, 24 Nov 2026 — mandatory)
| Step | Sub-agent model |
|---|---|
| Research + hook fact-check (2+ reputable sources; drop or attribute anything not clearly supported) + script + caption/hashtags/engagement comment | **Fable** |
| Build: episode.json shots, builders, TTS, render, assembly, technical QC fixes | **Opus** |
| Final QC before posting: re-check facts on the day, review EVERY `qc/full` sheet, approve or send fixes back | **Fable** |
Exact models (Irfan, 24 Nov 2026): **Fable = Fable 5.2** (`model: 'fable'`), **Opus = Opus 5.5** (`model: 'opus'`), sub-agent **effort = medium** (pass `effort: 'medium'` on every sub-agent call).
Reason: Fable is markedly better at factual accuracy/judgement; Opus handles the long tool-heavy build and keeps the weekly Fable quota (≈5 % per full Fable video) for the high-value steps.

## Editing style rule (Irfan, 24 Nov 2026)
- **All Pages:** prefer **one-shot editing** — no hard cuts; one continuous camera through one world, fast smooth
  "whip" moves (motion blur, eased) between spots. Reference reels: reel/1661364992040054, reel/2441291916610073.
- **New Pages (Self-Made Engineer and later): one-shot is mandatory.**
- **What Just Happened (Irfan, 24 Nov 2026 — from the Fri 27 Nov set): one-shot is now the WJH standard.** One
  continuous camera through one world per video. Proven WJH path (no fork of Page 2's renderer): ONE episode builder
  that builds the whole world and drives the camera and props on a single timeline across every beat, rendered by the
  v2 renderer — see `pipeline/blender/scene_lib_v2_campus.py` (Nvidia CEO bonus, 24 Nov), and verify numerically that
  the camera doesn't jump at any beat boundary. Camera rules: hold ≤ ~9 s, drift ≤ 25 % of the subject distance,
  orbit ≤ ~18°, fast eased whips with motion blur between spots, a backout ending on the frame-1 view (loop).
  Pair with the narration style: rewind ↔ backout, minute by minute ↔ continuous push through the scene,
  domino ↔ travel from cause to effect. When Page 2's shared one-shot renderer (`pipeline/oneshot/`, owned by
  Page 2) is ready, WJH moves to it; send WJH needs to Page 2 as change requests, never fork it. Hard cuts only as a
  documented fallback if a one-shot world can't be made render-ready in time for a slot.

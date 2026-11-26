# BUILD-LOG: Mercer Hollow world + one-shot render (24 Nov 2026, Opus build)

**Status (updated session 2, see bottom): code written + shared world interface; pure-Python parts tested. Blender has NOT been run yet**, because the WJH render
holds the Mac until the "BLENDER CLEAR" message. Every bpy module compiles, and a name scan found no undefined
names, but none of them has been run inside Blender. Expect a first-run fix pass; see "First Blender run" below.
Nothing was written outside `page2/`. There are no commits.

## What was built
| File | What it does |
|---|---|
| `scripts/gen_world_state.py` (edited) → `world_state.json` (regenerated) | **Slope fix (Decisions 3+4).** The meadow climbs at 13.5° on average, max **18.2°**, with an eased profile. A flat 20 m shoulder holds the **ridge pad at z 20.21 = exactly 65 ft above the ram pump** (waterfall bottom). The crest is at 70 ft above the house floor. Also added: a plunge pool under the waterfall, a smooth pond bowl, and a gentler west bank and street edge. The ridge moved east, so the **pad is now at (116, 70)** instead of (96, 52), and the **lot's east line moved from x=104 to x=126** (4.48 acres by polygon area, ~472 × 520 ft). `ram_tank_alt_site` was removed because the pad itself is now at 65 ft. The generator is import-safe: it writes only as a script, and `height()` is memoised. Backups: `scripts/*.before-slope-fix.*`. **Needs Fable/Irfan OK (lot width 400 → ~472 ft).** |
| `blender/mh_paths.py` | pathlib paths, world_state/location loading, `placed_builds()` (status approved\|scheduled\|posted, per location/interior), analytic `height()` with a fallback to the height grid. bpy-free. |
| `blender/camera_plan.py` | The one-shot camera plan. bpy-free. Per-beat camera keys `travel` / `snap` / `section` / `none`, with holds `drift` / `orbit` / `crane` / `push` / `pull` (plus `look_to` re-aim). Cues are a sentence index from `captions.json` or a word. Targets are episode spots, world camera_spots, zone anchors, `{anchor, dist, az, el}`, or section views. Holds are boosted automatically so the camera never moves less than 0.6 px/frame. Terrain/roof clearance pass. Preset, section, cast and lights swaps sit at the middle of a move. Per-frame `camera_speed` (px, dx, dy). |
| `blender/mh_blender.py` | bpy helpers: keys on Blender 5 layered actions (`set_keys`, CONSTANT `key_const`, `vis_keys`), shared node groups `MH_Weather` / `MH_Fog` / `MH_Section` (one keyed value drives every material), PH-textured materials, Geometry Nodes `scatter_gn` (true instancing), mesh helpers. |
| `blender/world_mercer.py` | Mercer Hollow. The terrain mesh is 1–1.5 m near the lot and 6–12 m out to 500 m, fading to the flat far ground. Its vertex mask covers lawn, meadow, dirt and woods, with slope dirt, snow/frost, and a section-cut transparency mask. Water: creek ribbon with flow, 2 m waterfall sheet + foam, plunge pool, pond with reeds, footbridge, rocks. Street: road, cul-de-sac, curbs, sidewalks, driveway, front walk, 4 neighbour houses (2 shared models, siding from the object colour), 6 utility poles + wires (one sagging span) + service drop. House: lap siding, gable roof, windows, navy door, porch + keyed porch light, a real kitchen-window opening with a lit backdrop nook, attached garage with roll-up door and NEMA outlet. Yard: privacy fence (GN posts), split-rail meadow fence, deck + grill, hero oak + tire swing, picnic table, 6 raised beds + plants, goose house + wire run, hose reel, A/C, propane tank, gravel path, mailbox with red flag. Workshop barn (board-and-batten, corrugated roof, roll-up door) + lean-to battery shed with a rack and inverter. Red pickup (~1.2k tris, no badges). Trees: 3 species × 2 LODs, GN-instanced (woods, creek banks, street, a 2.2k-tree far ring). Grass clumps within 25 m of every camera arrival point. Far: 22 low-poly hills, water tower (no lettering), low-poly town block. **Presets `day` / `dusk` / `frost` / `snow`** are keyed in one scene (HDRI tint/strength, exposure, low warm sun for dusk, fog colour, frost/snow). Lights `porch` / `house` / `kitchen`. Cut-away sections: soil-layer wall, caps, floor, half-embedded cable. **`BUILDS = {id: fn(ctx, entry, mode)}`** has a `wind_turbine` stub (lies flat → 4 s tilt-up → spin-up → faster in snag2 → furl in hack2 → eases to a stop; ghost tower in beat 2; dynamic anchors) and a `_stub` placeholder crate for builds without a builder. Anchors cover every camera_spot (`spot_<id>`), every zone, and the extra points. |
| `blender/characters.py` | **Bolts**: a 24-bone rig, every piece weighted 100 % to one bone. Head with square jaw, nose, ears, eyes (blue-gray iris), thick brows, a **short full salt-and-pepper beard shell + moustache**, and a hair shell. Signatures are separate objects: **round safety glasses on the forehead below the brim, red bandana (knot front-left + tail), yellow-orange pencil behind the RIGHT ear, tape measure at the LEFT front hip**. Outfits **workshop** (gray henley rolled, navy pants, tool belt + hammer, boots, navy cap) and **electrician** (navy coveralls + reflective strips, yellow gloves, multimeter, white hard hat) + the **harness** extra. The swap is a CONSTANT visibility key; Mask modifiers hide the forearms/hands under the electrician outfit. Clips (analytic → baked keys; `--clip-actions` also saves named Actions): idle, walk, point, thumbs_up, winch_crank/crank, hands_on_hips, scratch_beard. **Torque**: a goose with an 11-bone rig and clips waddle (with path root motion), idle, honk. Placement, outfit and clip changes come from the plan's cast events (mid-move). Rough triangle counts: Bolts ≈ 6–9k with all outfits (budget 30k), Torque ≈ 1.5k (budget 5k). |
| `blender/interiors.py` | `build_room(ctx, loc, room)`: garage, basement, kitchen, attic and living_room as their own light scenes. Walls have real door/window holes with emissive daylight backdrop cards, a few props per room, ceiling area lights, and anchors per room spot. Use: episode `"interior": "<room>"`. |
| `blender/render_oneshot.py` | One scene, one camera baked per frame from the plan (job frames ± 2 only). Cycles + OptiX/CUDA/Metal, adaptive sampling, denoise, **persistent data ON**, 2K texture cap. EEVEE option. Motion blur `--mblur 2d` (default, the overlay blurs from camera_speed) or `3d` (keyed on in snap windows). Writes global frames, per-beat tracks in **the `tracks_v2` format overlay_v2 already reads** (`NN_<beat>_A-B.json`, beat-local frames), and a stats + VRAM estimate per job. `--parts` filter. Every world part is wrapped in try/except, so a run still reports what worked. |
| `tools/oneshot.py` | Driver (venv): `plan` / `still` / `render` / `link`. Splits jobs at ≤150 frames that never cross a beat. **Resumable** (a finished job is skipped; Blender skips existing frames). **One Blender process at a time**, and it waits while any other Blender is running (`pgrep -ix blender` / `tasklist`). Blender comes from `pipeline/platform_cfg.py`. `link` hard-links global frames into `frames_v2/NN_<beat>/####.jpg` for overlay_v2. |
| `tools/qc_oneshot.py` | FAILs on: a frame-difference spike outside the planned travel/snap/section windows (±2 frames) and outside `oneshot.hidden_joins`; a static camera longer than 1 s (plan px/frame and pixel diff); a preset/section/cast/lights swap on a hold. Reads frames or an mp4. |
| `tools/synth_timings.py` | Synthetic `timings.json` + `captions.json` at 175 WPM (marked `synthetic`), for tests before TTS. It refuses to overwrite real timings. |
| `tools/make_build01_episode.py` → `episodes/build-01/episode.json` | Build #1 draft: 11 beats, **VO verbatim (265 words, asserted)**, 20 camera moves, presets dusk → day → dusk, cast, lights, the cable section, anchors, and overlays mapped to the existing v2 types. |
| `tools/test_oneshot.py` | Pure-Python tests: **ALL PASS**. Covers terrain slope/pad/flatness, cues, the Build #1 plan (window order, durations, swaps inside moves, never static, above terrain, outside buildings, no teleport), QC on synthetic frames (cut, freeze, spike inside a move, whitelist), and spot resolution. |

## Decision needed: lot width vs slope
Decision 2 keeps the lot at 400 × 520 ft. Decisions 3 and 4 ask for slopes ≤ ~18° and a pad 65 ft above the pump.
Both can't hold with the pad fully on a 400 ft lot. **I chose:** east line x=126 (~472 ft), with the pad on the lot.
**Alternative:** keep x=104 (400 ft) and let the pad at x 109–123 sit just past the line (a ridge-top easement). That
changes one constant (`LOT_EAST`) in the generator; terrain and pad stay the same.

## Deviations / stale references to fix (not edited: they are planning files)
- The ridge numbers changed: pad (96, 52, 24.38) → **(116, 70, 20.21)**, crest +80 ft → **+70 ft**, and `ram_tank_alt_site` was removed. Still-stale text: `BUILD-SPEC-character-world.md` §5–6, `PROPOSAL-v1.md` 2.1/2.2 ("+80 ft"), `scripts/build-01-wind-turbine.md` (label "WINDY RIDGE +80 FT"; the episode draft says **+70 FT**), and `scripts/build-02-micro-hydro.md` if it uses the pad coordinates.
- The battery shed is built against the workshop's south wall (y −38.25…−34.55), ~2 m north of its world_state zone centre (−38.4), so it actually touches the wall.
- Build #1 beat 2: the red pickup teleports to the ridge pad for the tailgate shot (hidden inside the travel move) and goes back to the driveway in beat 9.
- Motion blur: the driver defaults to `--mblur 3d` (Cycles blur keyed on in snap windows) because overlay_v2 has no 2D blur yet. Use 3d for the 20 s test. Switch to `2d` once the overlay reads `camera_speed.json`.
- The pixel thresholds in `qc_oneshot.py` (`SPIKE_ABS` 40, `SPIKE_REL` 3×, `STATIC_EPS` 0.2) are not calibrated. **Tune them on the first 20 s test.**

## How to run (repo root; Windows: `.venv\Scripts\python`)
```
.venv/bin/python page2/tools/test_oneshot.py                                        # pure-Python tests
.venv/bin/python page2/tools/synth_timings.py page2/episodes/build-01/episode.json page2/episodes/build-01/work
.venv/bin/python page2/tools/oneshot.py plan  page2/episodes/build-01/episode.json page2/episodes/build-01/work
```
**Still preview** (≈1–3 min: world build + 2 frames at 0.35 scale):
```
.venv/bin/python page2/tools/oneshot.py still page2/episodes/build-01/episode.json page2/episodes/build-01/work \
    --frames 60,700 --scale 0.35 --samples 8          # -> work/stills_oneshot/f0060.png, f0700.png
#   quick part test first:  --parts terrain,house,street,far   (then add yard,workshop,props,trees,grass,water,sections,builds,characters)
```
Good still frames for the plan: 60 = street drift (dusk), 300 = porch snap, 420 = ridge crane, 700 = turbine head,
940 = cable cut-away, 1100 = tower flat, 1600 = rotor, 2090 = battery shed, 2500 = kitchen window, 2900 = continuity wide.
**20 s test** (600 frames = 5 jobs, resumable), then QC:
```
.venv/bin/python page2/tools/oneshot.py render page2/episodes/build-01/episode.json page2/episodes/build-01/work --range 1-600 --scale 0.35 --samples 16
.venv/bin/python page2/tools/qc_oneshot.py page2/episodes/build-01/work
.venv/bin/python page2/tools/oneshot.py link   page2/episodes/build-01/episode.json page2/episodes/build-01/work   # for overlay_v2
```

## First Blender run (after "BLENDER CLEAR"): what to check first
1. `--parts terrain,far` still: terrain shape, ridge shoulder, haze, HDRI tint. Then add parts one at a time and read `[mh] PART x FAILED` lines in `work/oneshot/logs/still.log`.
2. API points written without a test run (most likely to need a fix): GN scatter (`FunctionNodeEulerToRotation`, `As Instance`, and whether instances of a `hide_render` template render); `me.polygons.foreach_set("use_smooth")`; animating `modifier.show_render` and `render.use_motion_blur`; `mode_set` for the armature in background mode; `surface_render_method`; the Principled socket names `Transmission Weight` / `Emission Color`.
3. Look: dusk tint/exposure and fog colour (these values are guesses), terrain colour vs the v2 reference, and the scale of the siding/board bands.

## What's missing (first pass)
- Bolts: an 11-outfit library (only workshop + electrician + harness are built), a Rigify-level rig (24 bones, not ~65), face bones/shape keys, hair cards (shells for now), texture atlases (flat PBR colours; no 2K core set or 1K outfit sets yet), `wrench`/`hammer`/`inspect` clips, hand props on `prop_R`/`prop_L`. Turntable check of the signatures in every outfit is still to do.
- Torque: `peck`, `flap`, `sit`, `chase` clips; wing-tip feather cards.
- World: build LOD1/LOD2 swaps (trees use a static distance LOD); per-waypoint LOD swapping; neighbour-peek character (beat 9 gag); survey stakes, wind arrows, the battery-box drop and trench-fill animations; wet asphalt / storm sky for beats 1 and 6; second neighbour fence line (y=23); hills are meshes, not baked cards.
- Overlay: `camera_speed.json` → 2D directional blur + whoosh placement in overlay_v2 (not edited: it lives in `pipeline/`); new chip/HUD/stat-card types.
- Interiors: only blocked-out rooms; no whip-through-door join (QC whitelist `oneshot.hidden_joins` is ready).
- Timings are synthetic (104 s at 175 WPM incl. pauses). Real TTS will retime every cue automatically.

## VRAM estimates (RTX 3050 4 GB, budget ≤ 3 GB): estimates only, measure with `nvidia-smi` on the first real run
| Part | Estimate |
|---|---|
| HDRI 2K (float) | ~35 MB |
| Poly Haven 1K sets (grass-rock, asphalt, concrete × diff/nor/rough) | ~40 MB |
| Terrain (~67k tris + mask) | ~15 MB |
| House, garage, porch, kitchen nook, workshop, shed, yard props, street, poles, neighbours (~60–90k tris) | ~20 MB |
| Trees: 6 templates (≤3k tris each) × ~3,000 GN instances | ~30 MB (instanced BVH) |
| Grass clumps (~5k instances × 9 tris), reeds, rocks, posts | ~10 MB |
| Bolts (all outfits ~9k tris) + Torque (~1.5k) + pickup + wind turbine stub | ~5 MB |
| Section cut-away meshes | ~2 MB |
| Cycles render buffers at 1080×1920 + OptiX denoiser | ~300–600 MB |
| CUDA/OptiX context + kernels | ~400–700 MB |
| **Total** | **≈ 0.9–1.5 GB**, well inside 3 GB. Interiors ≈ 0.6–0.9 GB. |
Each job also writes `work/oneshot/stats_A-B.json` with an estimate of image and geometry MB from the real scene.

---

# Session 2 (24 Nov 2026, Opus): shared world interface + Page 3 adapter. Still NO Blender run.

**Task 1 check.** `render_oneshot.py` and `characters.py` were complete, not truncated. Both compile, and an AST
cross-check plus pyflakes find no undefined names in any page2 module. `make_build01_episode.py` was re-run, and
`episode.json` came out byte-identical. **The VO matches the script's `VO:` lines exactly (11/11 beats, 265 words).**

## New / changed files
| File | Change |
|---|---|
| `blender/worlds.py` (new, bpy-free) | **World registry.** `WORLDS = {world_id: (module, build_fn)}` (Blender side, lazy import) + `PLAN_ANCHORS = {world_id: (module, fn)}` (bpy-free, for `plan`). Self-registration without editing page2: `page2/blender/` or `page3/blender/` `<world_id>.py` (`build(ctx, state)`) + `<world_id>_plan.py` (`plan_anchors(state)` → `{"anchors": {id: [x,y,z]}, "cams": {id: {"pos", "lens"}}}`). Cache `WORKDIR/oneshot/anchors_<world>.json` is written by every Blender build. It is only a fallback after a first successful build, so a new world still needs `_plan.py`. `plan_inputs()` is the single entry point used by both the driver and `render_oneshot.load_plan`. An unregistered world raises `WorldNotRegistered`, which lists the missing files and entries. A camera `to` or stop that no anchor defines raises a ValueError that names it. |
| `blender/camera_plan.py` | Move kinds **`crane`** (sine, via point above the start), **`portal`** (easeInQuad dive to 92 % of the way to the look surface → hidden cut → easeOutQuad emerge along the target's look direction; `portal` event at the join, `[j-1, j+1]` added to `hidden_joins`, the join frame's `camera_speed` px is clamped and flagged `"join": true`, no clearance lift on portal frames) and **`backout`** (Catmull-Rom through every earlier arrival view in reverse, ending on the **exact frame-1 framing**, then the opening hold resumes). Blur windows: snap, portal, backout. **Adapter `expand_oneshot()`** for the compact block (see below). **The Spark:** `plan["spark"]` gives per-frame `[x, y, z, radius]` (leads the camera by 0.3 s, 55 % of the way to the look point, idle wobble, r = 0.0125·d·36/lens) and colour events (mid-move, 0.5 s blend; `off` = 0.3 s fade). `loc["anchors"]` is now read by `SpotResolver`. **The build-01 camera array is byte-identical to before** (md5 of `cam` checked). |
| `blender/world_mercer.py` | `build_world(ctx, state)` registry entry: wraps `build()`, adds every plan-time anchor as an `ANC_<id>` empty plus a `CAM_<id>` empty per camera spot, and returns `{id: ANC_ empty}`. The World handle goes to `state["world"]`. |
| `blender/mh_blender.py` | `anchor_empty` now names empties **`ANC_<id>`** (`prefix=CAM_PREFIX` for `CAM_<id>`). A re-defined id reuses and moves the empty (no `.001` copies). `normalize_anchors(ctx)` turns every (object, offset) anchor into a child `ANC_<id>` empty. Old ids stay as aliases: `spot_<id>`, zone names, episode anchors, `bolts`, `torque`. Track JSON keys are unchanged. |
| `blender/characters.py` | `anc_bolts` / `anc_torque` → `ANC_bolts` / `ANC_torque`. |
| `blender/render_oneshot.py` | Builds the world through the registry (`build_fn(ctx, state)`). Calls an optional module `apply_events(state, plan, lo, hi)` for non-Page-2 worlds. Characters are built only for Page 2 worlds. Adds the Spark orb (`ED_Spark`: emission, location/scale keyed from the track, colour blend keys). Writes `oneshot/anchors_<world>.json`. Accepts a non-dict episode `anchors` (Page 3 uses a string there). |
| `tools/oneshot.py` | `make_plan` resolves the world **first** (clear failure), then the adapter, timings and plan. Prints the world and the anchor source. `camera_speed.json` gains `hidden_joins`. |
| `tools/qc_oneshot.py` | A `portal` event on a hold = SWAP_ON_HOLD. |
| `tools/test_oneshot.py` | New tests `test_registry`, `test_adapter`, `test_portal`. They use a test-only fake world with WORLDS-SPEC coordinates for the six stops. **ALL PASS.** |

## Compact `oneshot` block → camera keys (Page 3)
Trigger: the `oneshot` block has `world` + `stops` + `moves` (Mercer's config-only `oneshot` is untouched), and a
beat that already has `shot.camera` keeps it. Each beat gets ONE key `{move, to: stop, dur: move_durations_s[move],
cue: 0.0 (float = beat start), lead: lead_s (0.4)}`.
- Beat 1 drift/orbit/crane is the opening hold (`move: none`). Any other first move is replaced by drift, with a note.
- drift/orbit later on the **same** stop only changes the hold. On a new stop it becomes a travel with that hold.
- section: `section: <stop>`, so the world gets a `section` event with the stop id (S2 lid). backout: `to` = first stop.
- Orbit direction alternates from beat to beat.

Page 3 sample, plan with the fake world (test only): windows section, section, travel, crane, travel, backout.
2,912 frames (97.1 s synthetic) = the sum of `round(duration·30)`, and beat f0 = overlay_v2 `g0 + 1`. Never static. QC plan checks
pass. Backout ends exactly on frame 1's view. **Note:** the sample's 2.5 s backout runs through ~1.5 km of stops
(suburb → tower → plant → slice → wall → faucet), up to ~230 m/frame in the middle. It is legal per WORLDS-SPEC
("compressed"), but Page 3 may want `move_durations_s.backout` = 4.0 or fewer waypoints.

## Verified now (pure Python)
```
.venv/bin/python page2/tools/test_oneshot.py                     # ALL PASS (incl. registry/adapter/portal)
.venv/bin/python page2/tools/synth_timings.py page2/episodes/build-01/episode.json page2/episodes/build-01/work
.venv/bin/python page2/tools/oneshot.py plan  page2/episodes/build-01/episode.json page2/episodes/build-01/work
.venv/bin/python page2/tools/qc_oneshot.py page2/episodes/build-01/work           # PASS (plan checks; no frames yet)
# Page 3 sample: workdir OUTSIDE page3/ (read-only there); fails clearly until hometown_usa is registered
.venv/bin/python page2/tools/synth_timings.py page3/episodes/2026-11-24-c5-water-tower-sample/episode.json page2/episodes/_p3-sample/work
.venv/bin/python page2/tools/oneshot.py plan  page3/episodes/2026-11-24-c5-water-tower-sample/episode.json page2/episodes/_p3-sample/work
```
build-01: 3,125 frames (104.2 s, synthetic), 20 moves, 15 events, 28 jobs (≤150 frames, none crosses a beat,
contiguous 1…3125). The beat f0 values match overlay_v2's `g0`, and tracks/frames_v2 names use `%02d_<beat>`
(0-based), as overlay_v2 does.

## Audit fixes (same session)
- **Back-to-back `section` moves:** the first section's "off" event landed on the same frame as the second section's "on", which closed the second cut. Now no "off" event is emitted when the next move opens another section. Tested on the Page 3 sample (wall → main). The build-01 events are unchanged (cable on at f934, off at f1000).
- **`render_oneshot`** registers every anchor that `build_fn` returns, so a world that only returns `ANC_` empties still gets `tracks_v2`.
- **`mercer_plan_anchors`** resolves every camera/episode spot through `SpotResolver`, including section views such as `cable_slice`. All 19 build-01 `to` ids now have ANC + CAM, and a test asserts it.

## Open points
- **camera_speed px is very large in fast moves** (up to ~9k px on build-01 snap frame 1705, and 300–1,100 on
  travels). The metric uses near-depth grid points. overlay_v2 must cap the blur (WORLDS-SPEC: 60 px) when it reads
  this file. Not changed here because the build-01 plan had to stay identical.
- `world_mercer` warnings from pyflakes are cosmetic (unused `Vector`, unused local `pz`).
- I did not run `oneshot.py still --dry-run`, because the driver resolves Blender through `pipeline/platform_cfg.py`,
  which reads `.env`.

## First Blender run (after "BLENDER CLEAR"): one process, stills only
```
pgrep -ix blender || echo "no blender running"
.venv/bin/python page2/tools/oneshot.py still page2/episodes/build-01/episode.json page2/episodes/build-01/work \
    --frames 60 --scale 0.35 --samples 8 --parts terrain,far --no-wait          # then add parts one at a time
.venv/bin/python page2/tools/oneshot.py still page2/episodes/build-01/episode.json page2/episodes/build-01/work \
    --frames 60,700 --scale 0.35 --samples 8 --no-wait
```
New API points written without a run: `bmesh.ops.create_uvsphere` (Spark, Page 3 only), keyframing an Emission
socket colour through `set_keys`, `normalize_anchors` parenting to bone-parented empties.

---

# Session 3 (24 Nov 2026, Opus): renderer fixes for Page 3 (hometown_usa now auto-registers). Still NO Blender.

| # | Change |
|---|---|
| 1 | `worlds.registered_worlds()` returns WORLDS plus file-convention worlds; `hometown_usa` now appears there. The test checks that `mercer_hollow` is in the set, so extra worlds don't break it. The unregistered-world test uses `_no_such_world`. `worlds._import` sets `sys.dont_write_bytecode` so no `__pycache__` is written into `page3/`. A test spy checks that **`plan_anchors` gets the same expanded episode object that `build_plan` uses**. |
| 2 | **Holds scale with subject distance** d = \|look − pos\| at the hold start. Defaults (fraction of d per second): drift and crane 1.5 %, push/pull 2 %, orbit 1.5°/s (was 0.6 m/s and 4°/s). The new `"rel"` key sets the rate directly. A legacy `"speed"` in m/s is clamped to 10 % of d/s. Push stops at 60 % of d (was a fixed 1.5 m, which froze macro pushes). The `boosted()` min-motion check samples the first 6 s and now includes `look_to`. Build-01 holds therefore changed slightly; all build-01 tests still pass. |
| 3–4 | **Backout** = ONE eased arc (easeInOutCubic, via `_auto_via` lift when it is longer than 25 m), straight to the opening framing. It is timed to end `BACKOUT_SETTLE_S` = 0.4 s (12 frames) before the last frame. The settle frames are the opening hold running forward, so **the last frame is identical to frame 1** (loop). It keeps its full duration and is only shortened (with a warning) if the previous move leaves no room. |
| 5 | snap or portal to the stop the camera is already at = **snap push-in**: 40 % closer, lens ×1.12. A same-stop portal adds a note. An open section on that stop stays open. |
| 6 | Positions in `plan.json` are stored to 1e-6 m (lens 1e-4). The Spark track is also 1e-6 m. |
| 7 | `render_oneshot`: the camera, its target and `ED_Spark` are children of `WORLD_ROOT` (created at the origin when the world has none), so a rebase moves them with the world. The anchor cache stores WORLD_ROOT-local positions. |
| 8 | New `tools/oneshot_blur.py WORKDIR` → `oneshot/blur_2d.json`: per-frame blur only inside move windows, clamped at 60 px, nothing below 8 px. Portal `join` frames are skipped. `radial` for snap/portal, `directional` otherwise. Each entry has global + beat-local frames. Whoosh cues give `t`, beat-local `t_beat`/`lf`, duration and gain. Not yet wired into overlay_v2. |

## Results (synthetic timings; workdirs `page2/episodes/_p3/<id>/`, nothing written to page3/)
- `test_oneshot.py`: **ALL PASS**. New checks: push-in, blur spec, last frame = frame 1, direct backout, hold rate ≤ 5 %·d/s, 1e-6 precision.
- build-01: plan + qc PASS. 3,125 frames, 20 moves, 28 jobs; 536 blurred frames.
- **All 11 Page 3 episodes: plan exit 0 and qc PASS.**
  - Backout: 120 frames on every episode, settle 12 frames, last frame == frame 1 on all.
  - Backout path: 1–2,240 m. ed-09 dropped from 7,279 m to 2,240 m, peak 57 m/frame (was 265).
  - Look drift is ≤ 1 %/s of d. The worst cumulative drift is 0.37·d, over a 37 s combined twist+why hold (ed-05, ed-09).
  - ed-06's self-portal is now a push-in.
```
export PYTHONDONTWRITEBYTECODE=1
for e in page3/episodes/*/episode.json; do id=$(basename $(dirname $e)); wd=page2/episodes/_p3/$id
  .venv/bin/python page2/tools/synth_timings.py $e $wd && .venv/bin/python page2/tools/oneshot.py plan $e $wd \
  && .venv/bin/python page2/tools/qc_oneshot.py $wd && .venv/bin/python page2/tools/oneshot_blur.py $wd; done
```
**For Page 3** (their files are not edited):
- `plan_all.py` compares the backout window's END with cam[1]. That is now wrong by design. It should compare `cam[frames]` with `cam[1]`.
- Its "settle < 15 frames" warning will fire on every episode, because the settle is now 0.4 s.
- `tune_holds()` can be dropped. Its absolute speeds (1 %·d) are inside the new clamp, so keeping it changes nothing.
- Long holds may want a bounded (ease/ping-pong) drift later.

---

# Session 4 (24 Nov 2026, Opus): hold caps + hold-length rule (both Pages). Still NO Blender.

**Hold caps** (`camera_plan.cap_hold`, applied to every hold key with its real length = until the next key):
- Total travel ≤ **25 % of the subject distance** d per hold key, for drift, crane and push/pull. Adapter and default holds move at 1.5 %/s; Mercer's explicit speeds keep their own rate, but the 25 % total cap still applies.
- Orbit ≤ **18°** total, and the orbit's rise is also capped.
- Drift on a subject closer than **0.5 m** becomes a slow orbit, under the same cap.
- The **0.6 px/frame minimum still wins** after the caps (`boosted`). Each such hold is reported in `plan["holds"]` (`min_motion_wins`) and as a WARN line.
  - On build-01 that is hack1.0 (crane with `look_to`, 1.25·d) and works.2 (0.26·d).
  - On Page 3's 11 episodes `plan_all.py` reports 0 hold flags; worst hold travel is 0.31·d (orbits within 18°).

**Hold-length rule** (chief): a hold is the stretch between move windows.
- `camera_plan.check_holds()` → **FAIL over 10 s, warn over 9 s.**
  - `oneshot.py plan` writes its outputs, then exits 1 on a failure; `--allow-long-holds` overrides.
  - `qc_oneshot` reports `HOLD_TOO_LONG` and prints the longest hold.
- **Native `shot.camera` keys win** over the compact block for that beat (tested).
- Native snap/portal to the stop the camera is already at → push-in.

**Sub-stops** `<stop>__detail` / `<stop>__alt`:
- A view or anchor the world registers wins. Otherwise it is derived:
  - `__detail` = 40 % closer on the same look point.
  - `__alt` = the same anchor from 35° around, at the same distance and height.
- Anchors resolve to the stop's anchor. `mercer_plan_anchors` adds ANC/CAM entries for the variants it uses, and `render_oneshot` creates `ANC_<stop>__x` empties as children of the stop's anchor.

**`tools/hold_split.py`** (used by `make_build01_episode.py`, ready for future generators):
- Plans with synthetic timings and adds sub-stop keys (snap `__detail` / travel `__alt`, never a no-op), until every hold is ≤ 7 s planned.
- Keys go at sentence starts, or a word cue when no sentence start fits; an open section stays open.
- **build-01 now has 24 moves; longest hold 6.8 s (snag1, f1219–1421)**; VO unchanged (265 words, verbatim).

Results: `test_oneshot.py` ALL PASS (new: native-keys-win, variants, hold rule, hold caps).
- **build-01:** plan + QC PASS.
- **`page3/tools/plan_all.py`:** 11/11 OK; max hold per episode 6.9–8.9 s.
- **Page 3 (their files):** `plan_all` still warns "snap/portal to the stop already at" for ed-06 f420 and ed-08 f736. ed-06 f420 is a portal from `kitchen_microwave__alt` back to its base view; it is a real move, but there is no enlarged interior behind it.

---

# Session 5 (24 Nov 2026): FIRST BLENDER STILLS (after "BLENDER CLEAR")
Blender 5.3.0, Cycles on METAL (Mac), `--scale 0.35` (378×672), 8 samples. Blender is resolved through the
`BLENDER_EXE` env var, so `platform_cfg` never falls back to `.env`:
```
export BLENDER_EXE=/Applications/Blender.app/Contents/MacOS/Blender PYTHONDONTWRITEBYTECODE=1
pgrep -ix blender || .venv/bin/python page2/tools/oneshot.py still page2/episodes/build-01/episode.json \
    page2/episodes/build-01/work --frames 60,300,450,700,940,1150,1300 --scale 0.35 --samples 8 --no-wait
```
**Timing / memory:**
- First run (terrain,far): 177 s, almost all of it the one-time **Metal kernel compile**.
- After that, a full world build takes ~0.9 s, and each still takes **1.1–5.5 s** (≈2 s typical).
- A 7-still run takes ~14 s. **Peak RAM (max RSS) is 1.6–1.8 GB.**
- No part failed and there was no traceback. Every run used one Blender process.
- Contact sheet: `episodes/build-01/work/stills_contact.jpg` (14 frames: hook dusk 60, porch/Bolts 300, mission 450, flat turbine head 700, cable cut 940, tower low 1150, tilt-up 1300/1360, Torque 1450, rotor 1600, battery bank 2150, kitchen window 2550, fence peek dusk 2800, continuity 3050).

**Checked:**
- Bolts: short salt-and-pepper beard, round glasses on the forehead under the hard-hat brim, red bandana, electrician coveralls + harness, gloves, boots.
- Torque reads well.
- Sky/HDRI, clouds, the haze on the far hills and the dusk tint all work; there are no void backgrounds.

**Fixed after the first stills:**
1. **Tree canopies over the ridge shots** (f700/f1150/f1450 had dark canopies across the top). Ridge clearing 16 → 32 m, and no tree within 9 m of any episode camera spot.
2. **`turbine_head` looked at empty grass.** The head lies at the tip of the FLAT tower until the hack1 tilt, so the spot now looks at `tower_tip_flat`.
3. **hold hack1.0** (crane + `look_to`, where minimum motion beat the cap at 1.25·d, and the camera stared at the sky). It is now a 1.2 s travel to a new `tilt_side` spot: 30 m side-on, with the flat tip and the raised +50 ft tip both in frame. It holds with a slow 1.5°/s orbit, the whole tilt-up plays in view, and the hold is within the caps. The winch close-up was dropped, because it would have left a 0.4 s hold.
4. **Torque walked out of the `torque_ground` shot.** His path is reversed and shortened (2.2 m), so he walks into it.
5. **Battery shed was black.** It now has a warm area light (220 W, 2.2 m).
6. **The battery rack was empty.** It now holds 10 battery boxes with red/black terminals.

build-01 longest hold is now **5.9 s** (hack1 tilt view). The only min-motion override left is works.2 (a 142 m push, 0.26·d).

**Still open (minor):**
- f700: on the flat tower, one rotor blade dips into the grass. It needs a support stand, or the rotor parked with one blade up.
- f940: the cable cut-away is hard to read mid-move.
- The kitchen-window nook is plain cream.
- The concrete slab edges show stretched texture streaks.
- The porch pose (`hands_on_hips`) holds the arms far out.
- Dusk at f60 looks like overcast day rather than warm dusk.

## Session 5b: renderer fixes from Page 3 (plan + tests only, no Blender)
- **Backout out of a portal set.** `build_plan` tracks portal sets by position.
  - A portal sets the context, keeping the outermost entry if portals are nested.
  - A move near the set's entry view stays inside.
  - A portal back near the outside view, or a travel away from the set, clears the context.
  - A backout that starts inside a set first takes a fill-frame **reverse portal** (≤ 0.5 s, `exit_portal` frames). It gets a `portal` event `exit:<stop>` and a join whitelisted in `hidden_joins`, then ONE direct eased arc.
  - Tested: the arc passes no other stop, its path is within 1.35× of the straight line, and the last frame equals frame 1.
  - `plan_all` results:
    - ed-06's current plan already portals back out at f1276, so its backout is a direct 3 m arc from the kitchen; the 300 m climb no longer occurs.
    - ed-04 exits its scanner set through a reverse portal.
    - Every backout path is within 1 % of its straight line.
- **Same-stop push-in.** It applies to snap AND portal whenever the target has the same base stop as the current one, including `__detail` / `__alt` aliases. ed-08 f736 is now a push-in (2.03 → 1.22 m). The window carries `push_in: true`. Page 3's `plan_all` still prints its "already at" warning for f736 because it matches stop names; it should skip windows with `push_in`.
- **Found in the stills: the cable cut-away opened too late.** The section event now fires 2 frames before the camera dips below the terrain, still inside the move. The section-off event is placed on the NEXT move, not the section move itself.
- Results: test_oneshot **ALL PASS**; build-01 plan + QC PASS (longest hold 5.9 s); `page3/tools/plan_all.py` 11/11 OK.

---

# Session 6 (= the "Session 5" CC0 upgrade brief, 24 Nov 2026, Opus): CC0 assets + v2 look pass
**Deviation first: Bolts is NOT built on the Quaternius male.** Universal Base Characters / Animation Library only
download through an itch.io pay-what-you-want buy widget (skipped per the brief). The Ultimate Animated Character
Pack (fallback), Farm Animal Pack and Cars Pack Google Drive folders list anonymously, but every file returns
"Google Drive - Quota exceeded" (retried later, same). The Drive IDs for a manual download are in
`assets/cc0/manifest.json` → `skipped`. Bolts was therefore rebuilt procedurally, with smooth skinning (see below).

## Downloaded (CC0 only, `assets/cc0/`, gitignored except `manifest.json`; `python tools/fetch_cc0.py`)
- **Poly Haven** (api.polyhaven.com → dl.polyhaven.org), 133.8 MB:
  - 1k glTF: island_tree_02, pine_sapling_small, shrub_02/03/04, grass_bermuda_01, grass_medium_02, rock_moss_set_01, rock_07.
  - 2k diff/nor_gl/arm textures: white_planks_clean, grey_roof_01, gravel_road, river_small_rocks, grooved_concrete_driveway, + **excavated_soil_wall** (added for the cut-away).
- **Kenney** (kenney.nl, the site's free "Continue without donating" signed link), 11.9 MB zips, extracted: furniture-kit, survival-kit, car-kit.
- No light Poly Haven pine exists (pine_tree_01 is 17.4M polys and 949 MB), so pine_sapling_small is used.
- Total download: 145.7 MB. On disk: 237 MB, including the extracted zips and the 60 MB library .blend.

## New / changed files
| File | What |
|---|---|
| `tools/fetch_cc0.py` | stdlib urllib + pathlib. Skips present files whose sha256 matches. Handles Kenney signed links and safe zip extraction. `--check` / `--only` / `--record`. |
| `assets/cc0/manifest.json` | 75 entries: name, source page, url, licence, md5, sha256, size, path. Also `skipped` with reasons. |
| `page2/blender/cc0_lib.py` | **Build once** (`Blender -b --factory-startup -P page2/blender/cc0_lib.py -- build`, 47 s) → `assets/cc0/lib/mercer_cc0_lib.blend` (60 MB, **0 absolute image paths**). The build: thins leaf cards per island (numpy label propagation), decimates branches only, bakes scale, rebuilds the alpha that Poly Haven's JPG glTF cards lost (leaves/grass: alpha from the black background), and imports 24 Kenney props. Runtime: `get()` appends, `_haze_wrap` (fog × alpha, so leaf cards stay see-through), `ph_mat()` gives 2K box-projected PBR (`walls_horizontal` puts boards along the walls), `swap_material()`, `vram_estimate()`. |
| `page2/blender/mercer_cc0.py` | Hooks used by `world_mercer.py`: tree templates, hero oak, grass, creek rocks + river-pebble bed, shrubs, PBR surfaces, Kenney kitchen + battery-shed props, cut-away restyle, dusk sky, new pickup. Every hook falls back to the old procedural piece if the library is missing. |
| `page2/blender/world_mercer.py` | Small hooks only (see above). Dusk preset: sun 4.5 at 4° elevation, colour (1, .46, .2), warmer fog, `sky: 1`. One `_cc0_finish()` pass. Camera, plan, anchors and events are unchanged (`test_oneshot.py` ALL PASS). |
| `page2/blender/characters_s6.py` | **New Bolts + Torque** (below). |
| `page2/blender/characters.py` | `build_bolts` / `build_torque` / `torque_pose` delegate to s6 (`USE_S6`, with an automatic v1 fallback). The arm targets for point / thumbs_up / hands_on_hips / scratch_beard are solved from hand positions; **hands_on_hips is fixed** (elbows out, wrists on the hips). |
| `page2/blender/render_oneshot.py` | `--save-blend` now also runs `make_paths_relative`, so the .blend opens on Windows. |

## Look changes
- **Bolts:**
  - Loft meshes with a subsurf modifier. Smooth inverse-distance weights; the shoulders blend into the upper arms.
  - Stocky torso with a belly about 4 cm proud.
  - Shaped head: square jaw, brow, sockets, cheekbones. Lidded eyes, blue-gray iris, nose, ears, lips.
  - Fine salt-and-pepper beard and hair shells on the same topology as the head.
  - Five-finger hands and shaped boots with soles.
  - Signatures: round glasses on the forehead below the brim, red bandana with a knot and tail, a flat pencil behind the RIGHT ear, the tape measure at the LEFT hip.
  - Outfits: **workshop** (henley with rolled cuffs and placket, pants, belt, pouch, hammer, cap) and **electrician** (coveralls with reflective bands, zip, gloves, hard hat, multimeter) + the harness.
  - Same 24 bones, clip names and anchors.
  - Render tris visible (body + signatures + one outfit, subsurf 1, loft segments ×0.7): **workshop 27.2k**, electrician + harness 32.2k before the mask hides the forearms/hands (≈29k effective). Budget 30k.
- **Torque:**
  - Modelled white Embden-type goose: plump teardrop body, long S-neck (3 neck bones), orange bill with a knob and a nail, a lower mandible on the jaw bone, blue eyes, folded wings with layered feather tips, orange legs and webbed 3-toe feet.
  - Clips: waddle, idle, honk, and the new **peck** (also in `--clip-actions`). **5.4k render tris** (segments ×0.45; budget 5k).
- **World:**
  - Poly Haven broadleaf LOD0 (542k tris) / LOD1 (171k) and pines replace the balloon trees; there are 2,670 GN instances.
  - Hero oak plus the swing limb.
  - About 25k real grass clumps within 16 m of the camera points (grass only; broadleaf plants blocked close-ups).
  - 207 moss rocks and a pebble bed along the creek; 13 foundation and fence shrubs.
  - Horizontal white plank siding, grey roof, grooved driveway, gravel path.
  - Kenney kitchen (cabinets, sink, stove, fridge, uppers, coffee maker, toaster, plant, radio, stool) and shed props (barrel, bucket, crates, box, shovel).
  - New pickup: extruded profiles, boolean wheel wells, bevels, arch flares, windows, lamps, chrome bumpers, tyres with rims. About 1.5k base tris. Kenney `truck.glb` was rejected (toy proportions).
  - Cut-away: sharp wavy soil bands (turf, topsoil, clay, gravel, sandy clay) overlaid with excavated_soil_wall, an orange 12 cm conduit, and yellow warning tape 30 cm above it.
  - Dusk: a physical sky mixed in (keyed with the preset), a low warm sun, long shadows.

## VRAM (PROPOSAL 7.3, RTX 3050 4 GB, budget ≤ 3 GB): estimates from the stats JSON
- CC0 templates: 0.96M unique tris, ≈ 116 MB BVH. All instancing.
- Unique mesh total: 1.05M tris, ≈ 160 MB.
- Images: **≈ 454 MB** (render_oneshot estimate) after de-duplicating library images and scaling non-hero sets (driveway, gravel, river bed) to 1K in memory. Only the house siding/roof stay 2K (hero), as 7.3 asks.
- Plus about 0.3–0.6 GB of buffers and denoiser, and 0.4–0.7 GB of context.
- **Total ≈ 1.4–2.0 GB**, inside 3 GB. Measure with `nvidia-smi` on the Windows run.

## Stills (Mac M2 Pro, Metal, 0.35 scale, 8 samples)
- World build: 4.9 s. **Each still takes 3.4–6.0 s.** The 14-frame run takes 70 s, in one Blender process.
- Outputs:
  - `episodes/build-01/work/stills_contact_v2.jpg`
  - `episodes/build-01/work/before_after.jpg` (f60/300/700/1150/1450/2550; old on top, new below)
  - The old stills are kept in `episodes/build-01/work/stills_v1/`.

## Open issues
- Bolts is procedural, not Quaternius; the clips are still analytic (no mocap).
  - The face reads as a stylised-realistic explainer face at mid distance; close-ups would want a sculpted head or hair cards.
  - The thumbs_up hand is open (there are no finger bones).
- Torque: clean in studio views, but at f1450 (low sun, walking) faint dark curves still show on the breast/side where the wing pads meet the body. At 5.4k tris the silhouette is slightly faceted close up.
- Kitchen window: the Kenney props read but look soft through the glass, and their colormap textures are low-res.
- Dusk (f60, f2800) is warmer, with long shadows, but the sky is still more "golden hour" than deep dusk. The porch light depends on the episode's lights events.
- The woods are a single broadleaf species (island_tree_02 has a twisted, olive-like habit) plus young pines; a second CC0 broadleaf would help variety.
- `assets/CREDITS.md` is not updated (outside the allowed write scope). Add a Poly Haven/Kenney session-6 line there.
- Porch light: the episode keys `porch: false` from f1 to f2655, so the dusk hook/porch shots (f60, f300) have no porch light. This is episode-driven; I did not override it.
- The dusk sky's sun direction (`sun_rotation` 180°) was not matched to the sun lamp; check for the glow on the wrong side in a wide dusk shot.
- Swapping the roof to grey_roof_01 drops the old roof snow mix, and the CC0 trees/grass ignore frost/snow. Build-01 has no snow; winter episodes will.
- Creek rocks, the pebble bed and the shed props appear in none of the 14 frames, so they are visually unverified.
- `--save-blend` now runs `make_paths_relative`, but it was not exercised this session.
- A CC0 pickup exists (Kenney `truck.glb`). It was rejected from its preview thumbnail (toy proportions), not from a test render.

---

# Session 7 (25 Nov 2026, Opus): CC0 upgrade visual fixes
Blender 5.3.0, Metal, `--scale 0.35`, 8 samples, as in session 6. Every run used one Blender process (checked with `pgrep` first).

## Fixed
1. **Torque: seams and faceting.**
   - **Root cause of the "dark seam curves" (f1450):** they were not mesh seams. They were the shadows of tall CC0 grass blades falling across his white breast. They disappear in a grass-free studio render and in the game scene once grass is cleared.
   - **Fix:** `build_grass` now keeps a 0.6 m mown patch along every Torque cast spot and walk path in the episode (`self.exclude`).
   - **Geometry is now one merged surface anyway** (`characters_s6._merge_plumage`):
     - Body, neck, head and the folded wing pads are built as closed shells at full ring resolution.
     - They are voxel-remeshed (12 mm) into ONE surface, smoothed twice, and re-weighted from the source shells (inverse-distance blend of the 6 nearest source vertices).
     - The result is `torque_body`: about 7k quads, smooth shaded, no subsurf.
     - The bill, eyes, feather tips, legs and feet stay in `torque_parts` (subsurf 1).
     - The neck no longer pokes into the body as an open tube, and faceting is gone at close range.
   - **Tris: 18.4k render** (was 5.4k; the old 5k line is exceeded). In VRAM that is about 2 MB, so it was accepted. The rig, clips and anchors are unchanged.
2. **Turbine (Build #1).** In `world_mercer.build_wind_turbine` + helpers `_lathe_x`, `_airfoil`, `_blade`, `_autosmooth`:
   - **Blades:** 3 tapered, twisted blades with a cambered NACA-like section (24 % thick at the root → 12 % at the tip; chord 0.215 → 0.045 m). Pitch runs 18° → 1.5° from root to tip.
     - Each has a round root in a steel clamp, and the tip radius is 1.75 m.
     - The leading edge is derived from the keyed spin (+X), and the suction side faces downwind.
   - **Hub:** a white spinner (nose cone) and hub plate.
   - **Nacelle:** a new streamlined light-grey `bw_turbine_nacelle` with a dark alternator band, 4 cooling fins and a yaw clamp. It replaces the dark cylinder.
   - **Tail vane bug (rendered pitch black at f1600 in v2):** `bmesh.ops.solidify` left both caps coincident, so the vane self-shadowed. It is now an explicit 3 cm plate.
   - Object names, the rotor empty, spin keys and anchors are unchanged.
3. **Dusk.**
   - `key_preset` now keys the physical sky's `sun_rotation = 180° − sun_az`. The add_dusk_sky initial value is 270°.
     - The lamp, at rotation (90−elev, 0, az), puts the sun towards (sin az, −cos az).
     - Blender 5.3's sky texture puts its sun at (sin rot, cos rot). This was measured, not assumed: rot 0 → +Y, rot 90 → +X.
   - My first try (az + 180) put the disc on the wrong side; v2's fixed 180° was also wrong.
   - Verified with paired −X / +X views at f60: the sun disc and orange glow now sit at −X, the side the lamp lights the house from.
   - Effect: f60 looks into the anti-solar sky (blue-purple with a pink belt) instead of the orange glow. That is real dusk.
   - The dusk preset is deeper:

     | Setting | v2 | v3 |
     |---|---|---|
     | Sun elevation | 4° | 2.5° |
     | Sun energy | 4.5 | 3.4 |
     | Sun colour | (1, .46, .2) | (1, .4, .16) |
     | Tint | (1, .66, .48) | (.92, .6, .5) |
     | Strength | .30 | .24 |
     | Exposure | 0.15 | 0.0 |
     | Fog | (.62, .46, .42) | (.5, .4, .42) |
     | Sky gain | (.42, .42, .56) | (.34, .35, .5) |

   - f60, f300, f2800 and f3050 still read after the direction fix (full set re-rendered).
4. **Porch light** (`make_build01_episode.py` LIGHTS + regenerated `episode.json`; the diff is lights only):
   - The hook is now `porch: true` (f1).
   - The mission beat carries `porch: false`, so the light turns off at f353, mid-move, together with the day preset.
   - The callback (f2655 →) already had it on.
   - Plan + QC PASS, longest hold 5.9 s. ⚠ **Story note for the chief:** the hook VO is a blackout ("the whole street goes dark") and the payoff is "one porch light stays on". A lit porch in the hook weakens that contrast. To switch it back, flip `LIGHTS["hook"]["porch"]`.
5. **Frost/snow on the CC0 assets** (default off; build-01 is unchanged because the Mix factor is 0):
   - **Roof:** `cc0_lib.ph_mat(..., snow=True)` restores `B._snow_mix` on `grey_roof_01`.
   - **Plants, grass and rocks:** `cc0_lib.weather_wrap()` is applied in `get()` to every `cc0_*` template.
     - Rocks use the roof/terrain rule.
     - Foliage cards are NOT normal-gated (they face every way): frost 0.35 + snow × (0.35…0.75 by up-facing).
     - This is new behaviour: the old procedural trees and grass never had frost/snow (only the terrain and roofs did).
   - Tested with a scratch copy of the episode (hook = `snow`, mission = `frost`). The roof turns white, the trees and grass frost, the terrain snows.
6. **Second broadleaf:** Poly Haven `tree_small_02` (CC0, 1k glTF, 101 MB).
   - Added to `assets/cc0/manifest.json` (11 files, sha256 recorded) and fetched with `tools/fetch_cc0.py --only tree_small_02`.
   - Library rebuilt in 30 s → 91.6 MB. Templates: `cc0_broadleaf2_lod0` 486k tris, `cc0_broadleaf2_lod1` 157k.
   - It fills the "maple" slot (about 40 % of broadleaves). A library built before s7 falls back to broadleaf 1.
   - `assets/CREDITS.md` updated.
7. **Creek rocks and shed props verified:** see `f2150_creek` (moss rocks on the bank, pool) and `f2150_shed_wide` (barrel, bucket, shovel, crates and box beside the battery rack).

## Tooling
- `render_oneshot.py --views FILE.json` (still runs only) adds QC views off the plan: `[{"f", "tag", "anchor"?, "pos", "look", "lens"}]`. Positions are anchor-relative when `anchor` is given. It runs after the plan stills, so it never touches a reel.
- `oneshot.py still` forwards `--views` and `--tag`.
- `--save-blend` exercised: a 57 MB .blend with **0 absolute image paths** (the test .blend was then deleted).
- **Windows box:** run `python tools/fetch_cc0.py` (fetches `tree_small_02`), then rebuild the library (`Blender -b --factory-startup -P page2/blender/cc0_lib.py -- build`). Without that, the maple slot silently falls back to broadleaf 1.

## Outputs
- `episodes/build-01/work/stills_contact_v3.jpg`: the 14 plan frames + the Torque f1450 close-up, turbine close/side, dusk-sun check, shed, creek and woods views.
- `episodes/build-01/work/before_after_v3.jpg`: v2 on top, v3 below (f60/300/700/1150/1450/1600/2800).
- The v2 stills are kept in `episodes/build-01/work/stills_v2/`.

## Timings / VRAM
- World build: 5.7 s.
- Stills take 1.9–6.2 s each. The full set (14 + 7 views) takes 99 s in one process.
- From `stats_0060-3050.json`:

  | Item | Value |
  |---|---|
  | CC0 template tris | 1.61M (was 0.96M) |
  | Geometry estimate | 258 MB |
  | Images estimate | 492 MB |
  | Torque | 18.4k tris |
  | Bolts | 40.7k tris (all outfits) |

  **Total ≈ 1.45–2.05 GB** with the 0.3–0.6 GB of buffers/denoiser and 0.4–0.7 GB of context. That is inside the 3 GB budget. Still to be measured with `nvidia-smi` on Windows.

## Tests
- `test_oneshot.py`: **ALL PASS**.
- build-01 plan: PASS. `qc_oneshot`: PASS.

## Open issues (logged, not repaired: minor or outside this brief)
- f700 / flat tower: the hub sits about 0.4 m above the pad, so one blade still dips into the grass whatever the parking angle. It needs a raised hinge or a tower-top stand (a geometry change to the tilt-up).
- Creek: the moss rocks read, but the river-pebble bed barely shows through the murky green water. That is a water-material choice, not a missing asset.
- In the frost/snow presets the white siding reads grey-brown, because those presets have no sun (sun = 0). This predates s7.
- Torque's mown patch is 0.6 m. If a future episode keys him on a path the episode doesn't list, the grass shadows return.
- Bolts' quality (waits on the Quaternius decision) and the Kenney kitchen were skipped, per the brief.

---

# Session 8 (25 Nov 2026, Opus): Build #1 fixes (flat tower, distant hills, kitchen window)
Blender 5.3.0, Metal, `--scale 0.35`, 8 samples. One Blender process at a time (`oneshot.py still` waits). `episode.json` was NOT regenerated this session: the hook porch is OFF (`LIGHTS["hook"]["porch"] = False`), and f300 now shows the lamp unlit.

## Fixed
1. **Flat tower: rotor blade in the ground** (`world_mercer.build_wind_turbine`, assemble mode only).
   - **Rotor parked with one blade straight up** while the tower is down: a constant −90° phase on the rotor keys. The spin timing is unchanged. The two lower tips now sit 0.875 m below the hub, not 1.52 m.
   - **Timber tower-top stand** `bw_turbine_stand`: a sawhorse with splayed legs, side braces, a V cradle and a rubber pad, 1.15 m below the tower top.
     - The lowered angle is solved from the terrain `H()` under the rotor so the hub rests 1.32 m above the ground. It comes out at **86.69°** instead of 90°.
     - The hinge, pivot, guys, ghost and the upright pose are unchanged. The stand stays on the ground after the tilt-up, as a crew would leave it.
   - **New QC, `turbine_clearance()`:** for frame 1 and every frame from tilt_start to tilt_end (122 frames), it finds the lowest vertex of the blades, nacelle and vane above `H()`. The results go into the stats JSON (`turbine_min_clear_m`, etc.). **Min clearance +0.33 m**; it was negative before.
   - The camera stops were not changed. The f700 framing still holds with the hub 0.9 m higher.
2. **Distant hills** (`World._ridges`, `World._canopy_mat`; this replaces the 22 squashed spheres in `build_far`).
   - **Shape:** three rings of real ridge terrain around (40, 0), at R+110, R+350 and R+700 m (R = 650), with heights of 18–55, 30–85 and 45–120 m.
     - Rounded crests with an offset crest line, 260 m spur noise and a 2.4 m crown-bump treeline. The edges sink below the far ground plane.
     - 1,600–2,000 segments × 18 rows, **184k tris in total**.
     - The western sector (the dusk sun at az −90°) is capped at about 1.6° elevation, so the ridges never shade the dusk scene. The dusk sun disc still shows above them in `f0060_dusk_sun`.
   - **Material (shader only, no textures):**
     - Voronoi crowns (~6 m), dark gaps between crowns, and per-crown brightness jitter.
     - 40 m stand/ravine noise and 150 m patches of conifer, broadleaf and dry clearing.
     - A light crown bump.
   - **Aerial perspective:** the scene fog via `L._fog_wrap(density_scale=0.55)`, so it follows the keyed `MH_Fog` colour per preset. Dusk turns the ridges mauve-grey.
     - Near ridges read green with a visible canopy texture; the back ridges fade blue-grey toward the horizon.
3. **Kitchen through the window (f2550).** Diagnosis: the Kenney furniture kit has **no textures**; it uses flat palette materials. The softness came from the glass (transmission 1 + alpha 0.25 veiled the room, and the 8-sample denoiser smeared it) and from flat toy colours.
   - **Glass `mh_clear_glass`:** a Transparent BSDF + a faint Fresnel gloss (Layer Weight 0.12 × 0.55).
   - **Materials (`mercer_cc0._kitchen_materials`):** per-object slots (the library meshes are untouched):
     - oak-grain cabinets and walnut accents (procedural wave grain + satin coat);
     - brushed stainless steel, black enamel, and dark glass on the stove.
   - **Room:** a white subway-tile backsplash (procedural brick, 7.5 × 15 cm), an under-cabinet LED strip, and a 2.8 × 1.6 m ceiling area light (140 W, warm).
     - All are keyed through `add_light("kitchen", …)`, so they switch off with the kitchen lights.

## Outputs
- `episodes/build-01/work/stills_contact_v4.jpg`: the same 21 tiles and layout as v3 (14 plan frames + 7 check views from `views_v3.json`).
- `episodes/build-01/work/before_after_v4.jpg`: v3 on top, v4 below (f700, f940, f1360, f2550).
- The v3 stills are kept in `episodes/build-01/work/stills_v3/`.

## Timings / VRAM
- World build: 7.1 s. Full set (14 + 7 views): 116 s in one process.
- From `stats_0060-3050.json`:

  | Item | Value |
  |---|---|
  | Geometry estimate | **285 MB** (was 258; ridges +27 MB) |
  | Images estimate | 492 MB (unchanged) |
  | New textures | none |

- **Total ≈ 1.5–2.1 GB** with the buffers/denoiser and the context. That is inside the 3 GB budget. Still to be measured with `nvidia-smi` on Windows.

## Tests
- `test_oneshot.py`: **ALL PASS**.
- build-01 plan: PASS (longest hold 5.9 s). `qc_oneshot`: **PASS**.

## Open issues (logged, not repaired)
- **Mid-ground haze (f940, f1360):** the 150–400 m lawn and the CC0 woods still go mint/pale under the scene haze (bright lawn colour × blue fog). This is not the hills; it needs a darker far-terrain/field mix or a lower fog density.
- The ridges ignore frost and snow (build-01 has none). Winter episodes would want `weather_wrap`-style snow on `mh_far_canopy`.
- The kitchen stool's pink seat sits right behind the glass, so it reads as a blob at the bottom of f2550. It could move 0.3 m back.
- The hook lights have `kitchen: true` during the "whole street goes dark" blackout. It is not visible in the hook shots, but the story team should check.
- The tower stand stays on the ground after the tilt-up; it is visible small in wide upright shots.

---

# Session 9 (25 Nov 2026, Opus): Bolts on the Quaternius base
Blender 5.3.0, Metal, `--scale 0.35`, 8 samples. One Blender process at a time (checked with `pgrep` before each run).

## What was built
- **`page2/blender/characters_s9.py`** (new): Bolts on the CC0 Quaternius Universal Base Characters `Superhero_Male_FullBody.gltf`
  (the only male body in the free Standard kit) + Universal Animation Library `UAL1_Standard.glb`.
  - **Body:** reshaped at rest into a regular middle-aged build (coordinator QC, 2 rounds).
    - Arm chains (bones + skin) move 3.5 cm in per side and the whole shoulder girdle narrows smoothly with them. Upper arms are 52 % slimmer
      at the biceps but only ~12 % at the deltoid, with a 1.2 cm pad on the cap so the arm-down skinning keeps it round. Forearms 16 % slimmer.
    - **Shoulder fix (Irfan's QC: shoulders curved inwards).** There were three causes:
      - The barrel blend ran up to z 1.5 and pulled the armpit/upper-chest sides in under an un-moved deltoid.
      - The deltoid cap had been lowered 3 cm.
      - The arm chain moved 5 cm while the trunk beside it did not, leaving a step.
      - Fix: the barrel blend fades out by z 1.4, the TRUNK top rings were widened, the deltoid is padded instead of lowered, the traps are lowered
        only 0.8 cm, and the girdle moves in smoothly. Front, 3/4 and back show neck → trapezius → round deltoid → arm in both outfits;
        the clothes come from the same cloth base, so they follow.
      - Checked in idle, walk and all 5 gestures; point, thumbs-up and winch crank have the arm raised.
      - Walk: the whole arm (upper, fore, hand) now swings 0.16 rad clear of the belly.
      - Sheet: `bolts_shoulders_before_after.jpg`.
    - Every trunk slice is blended to a superellipse (`TRUNK` table): the waist is wider and straight, the chest plain (pecs flattened),
      the lats gone, the traps lowered. A belly shows in profile, and the outer upper thighs are widened so the hips match the shoulders.
    - Object scale 0.9823 → **1.778 m**.
  - **Head:** the kit's eyes (re-hued to blue-gray) and eyebrows, plus CC0 `Hair_Beard` and `Hair_Buzzed` (Rigged to Head Bone),
    pointed at the body rig after a Head-rest check. All are tinted salt-and-pepper through a luminance ramp; the skin uses
    the Light albedo with a slight desaturation and subsurface.
  - **Clothes = shells of the body:** one smoothed copy of the body (Taubin, 60 iterations; head, hands and feet pinned)
    serves as the cloth base. Every garment is cut from it with `bisect_plane` (clean edges), selected by rest
    position + dominant bone, and pushed out along the full-mesh normals. Weights are inherited 1:1, so the gloves bend
    with the finger bones. The body under each outfit is hidden by the old Mask contract (`hide_under_<outfit>`, eroded by one ring).
    - **Electrician:** coveralls with a chest band, sleeve and leg reflective bands, a belt and a zip line; yellow gloves with
      gauntlet cuffs; a lofted collar; a cap-style hard hat with peak and crown rib; a multimeter with a lead.
    - **Workshop:** henley with rolled cuffs and collar, work pants with belt, buckle, pouch and hammer, navy cap.
    - **Harness extra:** straps cut from the same cloth base at +2.4 cm, so they stay parallel to the coveralls.
    - **Boots:** lofted shaft, foot and sole (subsurf 1), smooth weights on calf/foot/ball.
  - **Signatures:** glasses on the forehead below any brim, a lofted red bandana with knot and a hanging triangle on the
    `bandana_tail_1/2` bones, the pencil behind the RIGHT ear, the tape at the LEFT hip. All are fitted to measured head/neck/hip surfaces.
  - **Rig:** the native 65-bone Quaternius skeleton plus non-deform `prop_L/R`, `hat_root`, `tape_clip` and deform
    `bandana_tail_1/2`. `ANC_bolts` is placed where s6 had it (head top + 5 cm, rest). Rest pose faces −Y.
  - **Animation:** UAL is imported once and sampled at 30 fps (seconds-based; import fps read from the scene). It is
    **retargeted** by armature-space rotation delta from the UAL rest onto the body rest (the two rests differ on nearly every bone),
    and the pelvis translation is scaled by the hip-height ratio. The UAL objects/actions are then deleted. The bake keys **every bone on
    every frame** (quaternion, sign-continuous) plus the pelvis location, with an 8-frame world-rotation crossfade at clip switches.

    | Clip | Source |
    |---|---|
    | idle | **relaxed upright stand** (`Animator._relaxed_stand`). UAL `Idle_Loop` is a wide, bent-knee "ready" crouch with the arms out, so only its spine/neck/head life is kept (at half strength). The legs are straight at rest width (about shoulder width), the pelvis is level with a slow weight shift, the arms hang close to the body and the hands are relaxed. Every gesture overlay is built on this stand. |
    | walk | UAL `Walk_Loop` (in place; checked in the studio: upright, no crouch) |
    | point, thumbs_up, hands_on_hips, scratch_beard, winch_crank (crank) | **not in the free kit** → `Idle_Loop` legs/breathing + an arm/finger overlay. The overlay is solved from hand targets (2-bone IK, hand frame, forearm twist share, finger curl about the rest bend axis) and eased in like the s6 clips. Thumbs-up has a real fist with the thumb bones straight up. |

    Unknown clips fall back to idle with a log line. `make_clip_actions` writes `bolts_<clip>` actions (`--clip-actions`).
- **`characters.py`:** `BOLTS_IMPL` (env `MH_BOLTS_IMPL`) = `s9` (default) / `s6` / `v1`, falling back down that chain if a build raises.
  The dict carries `impl`. `apply_cast` uses the dict's `bake` when present, otherwise the old euler `bake_clips`. Torque is unchanged (s6).
- **`render_oneshot.py`:** writes `bolts_impl` and `bolts_tris_visible` to the stats JSON; `--clip-actions` dispatches to s9.
- **Fixed during QC:**
  - The glTF rig imports with QUATERNION rotation, so apply_cast's yaw keys did nothing (Bolts always faced −Y). The rig is now XYZ.
  - `materials.clear()` after `to_mesh` reset the shells' material indices (no reflective bands or belt). The slots are now set first.
  - Band/belt materials were classified after the normal offset, which gave ragged edges on the belly. They are now classified on the cut surface.
  - The relaxed left thumb went into the thigh. Fixed by moving the arm out and turning the palm a little back. The tape case was moved 2 cm forward, clear of the harness belt.
- **Assets:** `assets/cc0/manifest.json`: the Quaternius item moved from `skipped` to two `files` entries (zips, size + sha256, `url: manual:<itch page>`).
  `fetch_cc0.py --check` is all ok. `assets/CREDITS.md` has a Quaternius line.

## Outputs (`episodes/build-01/work/`)
- `stills_contact_v5.jpg`: the 14 plan frames + 8 Bolts views (`views_v5.json`, anchored on `bolts`). The v5 stills are kept in `stills_v5/`, the v4 ones in `stills_v4/`.
- `bolts_v5.jpg`: studio turnaround (front, 3/4, side, back, electrician + harness, idle), face front/side, thumbs-up close-up.
- `before_after_v5.jpg`: v4 top, v5 below, on f60/f300/f1300/f1360 (the plan frames where Bolts shows).
- `bolts_shoulders_before_after.jpg`: shoulder close-ups before (top) / after (bottom). Electrician and workshop front, 3/4 and back,
  plus point (raised arm) and winch crank.
- `bolts_old_vs_new.jpg`: OLD s6 (`MH_BOLTS_IMPL=s6`) top vs NEW s9 bottom, same studio lights and cameras, with the
  concept turnaround and `branding/profile-logo-final.png` as reference tiles.

## Timings / tris / VRAM
- Bolts build: 2.0 s; bake of 2,999 frames × 71 bones inside the still run. Full still set (14 + 8 views): 118–157 s.
- Render tris visible: **electrician + harness 34.3k**, workshop 26.9k (body core 16.2k incl. hair/beard/eyes). That is over the old 30k line,
  but it is ~5 MB of geometry. Torque 18.4k (unchanged).
- From `stats_0060-3050.json`:

  | Item | Value |
  |---|---|
  | Images | **592.7 MB** (was 492; +5 × 2K body/hair maps) |
  | Geometry | 289.7 MB (was 285) |

  **Total ≈ 1.6–2.2 GB** with buffers/denoiser and context, inside 3 GB. Still to be measured with `nvidia-smi` on Windows.

## Tests
- `test_oneshot.py`: **ALL PASS**.
- build-01 plan: PASS (longest hold 5.9 s). `qc_oneshot`: **PASS**.
- Fallback checked: `MH_BOLTS_IMPL=s6` builds the procedural Bolts (studio run).

## Open issues (logged, not repaired: minor)
- The face is still the kit's young "hero" face under the beard (no age lines); the free kit has no other male head.
- No six-pack or pecs show through the clothes now. A soft crease remains under the chest band in hard light.
- Walk: at the front of the swing the glove brushes the harness belt (no penetration). Walk is not used in build-01.
- Reflective chest band: a few-mm wave near the armpits (normal offset on a curved surface).
- The kit's beard mesh has a ragged sideburn silhouette at close range.
- Pose clips other than idle/walk are overlays, not mocap. Crank hands are on a circle, not on a modelled winch handle.
- **Windows:** the two Quaternius zips must be copied by hand to `assets/cc0/quaternius/` (no anonymous URL). `fetch_cc0.py` would try the
  `manual:` URL and stop, so run it with `--check` or `--only` until then. Extraction next to the zip is found by `characters_s9._kit()`.
- Leftover in `work/stills_oneshot/`: an old `oneshot_f1600.blend1` from an earlier session (not touched).

---

# Session 10 (25 Nov 2026, Opus): old Bolts (s6) comparison
Irfan asked whether Build #1 can go back to the previous Bolts. Nothing was changed in code: s9 stays the default, and s6 is chosen per run with `MH_BOLTS_IMPL=s6`.

## Runs
- Blender 5.3.0, Metal, `--frames 300,2150 --scale 0.5 --samples 16`, with identical settings for both runs. Each run used one process and took about 62–64 s.
- The views are taken from `views_v5.json`, re-tagged so no existing still is overwritten. Files: `work/stills_old_bolts/views_s6.json` and `views_s9.json`.
- Shots:
  - f300 hands_on_hips
  - f1150 scratch_beard
  - f1300 winch_crank
  - f2150 thumbs_up close-up
- f1600 `_thumbhero` was dropped because it shows only the turbine (Bolts is not in frame). Build-01 has no Bolts walk shot.
- All outputs are in `work/stills_old_bolts/`: the stills, `stats_s6.json`/`stats_s9.json` and `still_s6.log`/`still_s9.log`.
  The temporary `oneshot/stats_0300-2150.json` was removed and `oneshot/logs/still.log` restored.
- Sheet: `work/bolts_s6_vs_s9_compare.jpg`. Rows are the frames; OLD (s6) is on the left, CURRENT (s9) on the right.

## Result
- **s6: PASS.** `bolts_impl = s6_procedural`, with no traceback, FAILED or fallback lines.
- Visible tris: workshop 27.2k, electrician 32.2k (all outfits 40.7k).
- s9 run: `s9_quaternius`. It logs 2 missing kit normal maps (`T_Hair_1_Normal_png.png`, `T_Eye_Normal_png.png` under `Godot - UE/`).
  This is a minor s9 issue and is not repaired.
- `test_oneshot.py`: ALL PASS with the default and with `MH_BOLTS_IMPL=s6`. The test never imports `characters`, so it does not test either Bolts.

## Impact of switching back to s6
- **Clips:** all 7 clips exist on s6 (idle, walk, point, thumbs_up, hands_on_hips, scratch_beard, winch_crank). They come from the analytic euler `characters.bolts_pose`, and `apply_cast` picks them automatically.
  - s6 has **no finger bones** (one `hand.*` bone; the fingers are modelled fixed-curled). There is no fist and no grip.
  - Thumbs-up reads as an open, raised mitt.
  - In the winch crank the hands float open with splayed fingers.
  - In hands_on_hips the hands sink into the hips.
  - Walk is a simple sine swing, not the UAL mocap. It is not used in build-01.
- **Continuity:** s6 has every `character.json` signature (glasses on the forehead, red bandana, pencil on the RIGHT ear, tape on the LEFT hip, salt-and-pepper beard, gloves, harness, hard hat).
  - It looks stylised and procedural: a long neck, a tube torso, puffy shoulder caps and a blocky face.
  - It has no reflective leg bands in the hook shot, and the bandana knot is a red blob.
  - The proportions differ visibly from s9. Episodes must not mix the two, so whichever version is picked stays for the series.
- **Re-render scope:** no final render exists (`work/frames_oneshot/` is missing). Switching costs only a stills/QC pass plus the normal render; nothing has to be redone.
- **VRAM** (same frames, stats JSON):

  | Item | s6 | s9 |
  |---|---|---|
  | Images | 491.8 MB | 592.7 MB |
  | Geometry | 285.4 MB | 289.7 MB |
  | Build | 6.4 s | 10.1 s |

  s6 saves about 100 MB of textures, because it has no 2K kit maps. Both fit the 3 GB budget.

---

# Session 11 (25 Nov 2026, Opus): s9 proportion pass
Irfan keeps s9 but found the arms, shoulders and torso odd. Goal: a normal ~40-year-old hands-on man with a modest belly, at the same height.
Blender 5.3.0, Metal. One Blender process at a time (checked with `pgrep` before each run). Only `blender/characters_s9.py` changed.

## Profiles (old look kept)
- `PROFILES` in `characters_s9.py`, picked with env `MH_BOLTS_PROP`:
  - `s11` (default): the new proportions.
  - `s9`: the session 9/10 body.
- **Check:** a studio measure with `MH_BOLTS_PROP=s9` matches the pre-edit build exactly (every bone, slice and contact number).
- **File baseline:** `work/stills_s9_prop/characters_s9_before_s11.py.txt`.
- `BOLTS_IMPL` is unchanged (`s9`).

## Changes (rest, armature space, before the 0.9823 object scale; measured values are world, idle)

| What | s9 | s11 |
|---|---|---|
| Trunk table, half-width (hips / waist / chest) | 0.192 / 0.200 / 0.186 | 0.180 / 0.168 / 0.180 |
| Trunk table, half-depth at the belly | 0.150 | 0.131 |
| Superellipse exponent | 2.4 (boxy) | 2.1 (rounder) |
| Belly | 2.2 cm | 2.0 cm |
| Measured skin trunk width, z 0.95–1.28 | 37.6–39.8 cm | 34.0–35.6 cm |
| Measured skin trunk depth at z 1.13 | 32.9 cm | 29.2 cm |
| Shoulder breadth (outfit, z 1.38–1.44) | ~50 cm | ~50 cm (`shoulder_in` unchanged; what changed is the slope and how the arms hang) |
| Shoulder girdle | (no drop) | lowered 1.6 cm (smooth girdle blend, as in `_narrow_shoulders`) → trapezius slopes down; shoulder joint z 1.426 → 1.410 |
| Upper arm length | 0.247 m | 0.304 m (+5.8 cm, stretch spread over the shaft; deltoid, elbow and wrist shapes kept) |
| Forearm length | 0.239 m | 0.259 m (+2.0 cm) |
| Idle elbow z | 1.188 | 1.113 (waist) |
| Idle wrist z | 0.953 (hip-joint height) | 0.858 (crotch level) |
| Arm thickness | deltoid −12 %, biceps −40 %, forearm ×0.84 | deltoid −15 %, biceps −42 %, forearm ×0.80 |
| Hands | 21.0 cm | 18.9 cm (scaled ×0.9 about the wrist) |
| Glove gauntlet | 6 cm long, 1.2 cm flare | 4.5 cm long, 0.6 cm flare |
| Thighs | outer hip pad 3 cm | outer hip pad 1.2 cm; inner thigh −14 % near the crotch. This opens a thigh gap: the lowest midline skin vert rises 0.807 → 0.876, because in s9 the inner thighs touched down to 0.807. The legs read longer. |
| Electrician neckline (front) | chin −3.5 cm | chin −6.8 cm; the cut rises 0.2 m/m towards the back (tilted neckline, so the back is not bare) |
| Collar | top at chin −2.3 cm | 4.5 cm band ending 0.8 cm above the neckline |
| Bandana | chin −7.0…−3.6 cm, grow 4.2/3.2 cm | chin −8.8…−5.4 cm, grow 3.6/2.4 cm, 0.12 tilt; the tail bones move with it |
| Visible neck in front (chin → bandana top) | 3.0 cm | 4.9 cm |
| Workshop henley neckline | chin −3 cm | chin −6 cm (same tilt) |
| Idle pose | neck/head blended 0.4/0.3 to rest | neck/head blended 0.65/0.5 to rest, plus 0.14/0.07 rad back (head over the shoulders, no forward "vulture" neck) |
| Idle upper-arm aim x | 0.27 | 0.20 |
| Idle forearm x | 0.1 | 0.06 |
| Walk `ARM_OUT` | 0.16 rad | 0.12 rad |

- **Harness (`_harness_v`):**
  - Shoulder straps follow a soft V: x 0.106 at the belt → 0.086 at the chest strap → 0.098 over the shoulder. The straps are cut with slanted bisect planes.
  - Leg loops are tilted round each thigh (0.825 at the thigh centre, dz/dx −0.36), not one horizontal band that read as a shorts hem.
- **Rest-space constants made relative:**
  - Sleeve reflective bands sit at wrist −8…−5 cm.
  - Tape, `tape_clip` bone, multimeter, pouch and hammer x are ×0.93 (the narrower hips).
- **Unchanged:**
  - Same height: rest scale 0.9823, 1.778 m.
  - Face, beard, eyes, finger bones, all 7 clips, every `character.json` signature, both outfits.

## Contacts (studio measure, before → after)
| Contact | Before | After |
|---|---|---|
| hands_on_hips palm → trunk surface | 1.7 / 1.4 cm | 1.0 / 0.9 cm |
| scratch_beard fingertips → beard | 1.5 / 2.6 cm | 1.5 / 2.1 cm |
| winch_crank at f646 | short arms fell 3.6 cm short of the target | reached (−0.454 m vs target) |
| winch_crank at f656 | unchanged | unchanged |
| Idle forearm → trunk clearance | 0.3 cm | 0.4 cm |

## Outputs (`episodes/build-01/work/`)
- **`bolts_s9_proportions_before_after.jpg`:** columns BEFORE (s9 now) / AFTER (normalized).
  - Rows f300, f1150, f1300 and f2150 use the session 10 cameras (`--frames 300,2150 --scale 0.5 --samples 16`, views `stills_s9_prop/views_before.json` / `views_after.json`).
  - Two more rows: studio idle FRONT and SIDE, 85 mm, identical lights.
  - The in-world front view (f1800, idle) was occluded by a pole, so neutral views are studio renders. Studio BEFORE = `MH_BOLTS_PROP=s9`, verified identical to the pre-edit code.
- **`bolts_s9_prop_deform.jpg`:** the 7 clips at their extremes, two 3/4 views each. Walk is shown at A/B. Winch is shown at its 4 crank phases: f641 far, f651 top, f661 near, f671 bottom (40-frame cycle from f601).
- **`stills_s9_prop/`:**
  - raw world stills (`*_before*`, `*_after*`);
  - `studio/` (legacy_* and after_* incl. workshop front/3/4 and all deform frames);
  - `measure_legacy.json` and `measure_after.json`;
  - stats and logs;
  - the studio harness `studio_s11.py.txt` (run: `Blender -b --factory-startup -P studio.py -- OUTDIR TAG --measure --render front,side,q34,back --deform --workshop`).
- **Housekeeping:** `oneshot/logs/still.log` restored. The temporary `oneshot/stats_0300-2150.json` was moved to `stills_s9_prop/stats_{before,after}.json`.

## Deformation (after)
- Extra checks (`stills_s9_prop/extra_{after,legacy}.json`, `studio/*_x_*`):
  - **Lit upper-back, 3/4-back and front close-ups, both outfits:** neck → trapezius → round deltoid, with no inward curve.
  - **Crank phases:** no elbow or glove enters the belly or harness.
  - **Idle gloves:** they hang beside the thighs, clear of the leg loops, tape and multimeter.
  - **Signed glove/arm-to-outfit metric:** inconclusive. The nearest-face sign is noisy on the thin joined props (multimeter, tape, collar).
    - It reads equal or better than s9 everywhere. Hips: −3.9 vs −3.8 cm. Crank: −2.4…+2.7 vs −8.7…−2.8 cm.
    - Penetration was therefore judged visually. Hands on hips rest on the hips at f300 with no sinking.
- The plan stills `f0300_after` / `f2150_after` were checked. f2150 has no Bolts in frame (same as before).
- `views_before.json` now lists the same 4 views as `views_after.json`. The occluded f1800 world views were dropped.
- No shoulder collapse, armpit or harness tearing, or candy-wrapper wrists in any clip:
  - idle
  - walk (both extremes)
  - point (arm raised above the shoulder)
  - thumbs_up
  - hands_on_hips
  - scratch_beard
  - winch_crank (both phases)
- The workshop outfit was checked front and 3/4.

## Stats / VRAM
- `bolts_impl = s9_quaternius` in both runs, with no Traceback and no CHARACTERS FAILED.
- Visible tris: electrician + harness 34.2k → **34.7k** (slanted strap cuts); workshop 26.8k → 26.7k.
- Images 592.7 MB and geometry 289.7 MB are unchanged. **Total ≈ 1.6–2.2 GB**, inside 3 GB.

## Tests
- `test_oneshot.py`: **ALL PASS**. It still does not import `characters`; Bolts was verified by the studio and still runs.

## Open issues (minor, logged)
- Coverall thighs still touch down to z ≈ 0.73. The skin crotch is 0.876; the cloth offset closes the gap. This reads fine at medium distance.
- The neck is the kit's slim neck. It is now visible (about 5 cm in front). In 3/4 close-ups it can read slightly long or thin.
- Boots are unchanged and still read large.
- The pre-existing missing kit normal maps (`T_Hair_1_Normal`, `T_Eye_Normal`) are still logged.

---

# Session 12 (25 Nov 2026, Opus): body locked, real TTS, re-plan, final-quality render test
One Blender process at a time (`pgrep -il blender` before every run). Nothing outside `page2/` was edited. No commits.

## Body locked (series default)
- The code defaults were already `BOLTS_IMPL=s9` (`characters.py`) and `MH_BOLTS_PROP=s11` (`characters_s9.py`), so no code changed.
- `character.json` → `bolts.proportions.locked_body`: Quaternius Superhero base, s11 proportions, approved 25 Nov 2026, the session 11 measurements, and the rule that the body must not change mid-series. Nothing in code reads `character.json`, so the new key is safe. The file was re-indented (2 spaces); its content is otherwise unchanged. Backup: `episodes/build-01/work/character.before-s12.json.txt`.
- `BUILD-SPEC-character-world.md` §2: a LOCKED BODY note.

## Real TTS (pipeline/tts.py + pipeline/captions.py, run directly on the page2 workdir; make_episode.py NOT used because it writes to the repo `output/`)
- `episode.json` `tts` had no `model`, so `tts.py` would have raised a KeyError. Added `model: gemini-3.8-flash-tts` and `fallback_model: gemini-3.1-flash-tts-preview` (same as voice-test/WJH) to `episode.json` and `tools/make_build01_episode.py`. The diff is only those 2 lines; backup `work/episode.before-s12.json.txt`. Voice Fenrir and the episode's own director notes were kept. These are terser than the voice-test sample notes.
- **VO: `work/audio/voice.wav`, 85.69 s** (synthetic was 104.2 s), 24 kHz mono. Beat WAVs `work/audio/beat_<id>.wav`, `usage.json`, `timings.json` (no `synthetic` flag).
- Takes:
  - hook: the 1st take read the director notes aloud. tts.py's Whisper guard caught it and retried.
  - snag1: take 1 added a leading "But"; take 2 said "narrator". Both were caught by a Whisper medium.en check and kept in `work/audio/rejected/`. Take 3 is verbatim.
- Whisper medium.en on every beat: verbatim, except normal number/name spellings ("50", "1.5", "Boltz").
- Base.en mishears that don't matter, because caption text comes from the script: "streak" (street), "snack" (snag), "turban" (turbine).
- No pause > 0.6 s inside the VO (silencedetect −40 dB); the only one is the 0.86 s tail. Peak −0.6 dBFS.
- **Cost:** final takes 2,120 audio-output tokens ≈ $0.019. With the 3 rejected takes, about **$0.025**.
- **Captions:** `work/captions.json` (265 words, 88 chunks; real, no `synthetic` flag) and `work/captions/` (PNG stream + list.ffconcat).
  - Every beat's words lie inside its speech window.
  - No chunk overlap; chunk length 0.25–1.81 s.
  - 5 words have zero length (Again., Wind, Build, Honest, Small), all at sentence starts, from interpolation. Minor.
- The synthetic files are kept in `work/synthetic_s11/`.

## Re-plan (real timings)
- `oneshot.py plan`: **2,571 frames (85.7 s), 24 moves, 16 events, 23 jobs. Longest hold 4.6 s** (works, f1894–2031). No static runs > 1 s. Exit 0.
- The warnings are the 3 planned same-stop push-ins (they were already there with synthetic timings) and 2 small key delays (4 and 12 frames).
- The works.2 min-motion override is gone.
- `test_oneshot.py`: **ALL PASS**.

## Final-quality render test (scale 1.0 = 1080×1920, 32 samples, Cycles Metal, `--mblur 3d`)
- **Timing stills** (`work/test_s12/`, `stills_final_sheet.jpg`):

  | Frame | Shot | Time |
  |---|---|---|
  | f60 | street, dusk | 23.1 s |
  | f270 | porch, Bolts | 19.8 s |
  | f900 | tower_low | 32.1 s |
  | f2100 | kitchen window | 63.3 s |

- **Test job f445–510** (66 frames, 2.2 s; the mission-beat tailgate hold plus the snap to turbine_head):
  - `oneshot.py render --range 445-510 --scale 1.0 --samples 32`: 3,521 s wall for the 66 frames. The first frame was saved at 59 s, of which roughly 10 s is the world build.
  - Per frame: **mean 53.2 s**, holds 45–49 s, 3D-blur snap frames 56–62 s.
  - Log: `work/test_s12/render_445-510.log` and `oneshot/logs/job_0445-0510.log`.
  - Two log lines: "motion blur keys failed … using a frame handler" is the existing fallback; the 2 missing kit normal maps are known.
- **Full-render estimate on this Mac (M2 Pro): 2,571 frames × 35–55 s ≈ 25–39 h** (central about 30 h). That is **over the 4 h limit, so the full render was NOT started.** Recommendation: render on the Windows laptop (RTX 3050, OptiX) with the resumable driver. Measure s/frame on its first job before committing.
- **qc_oneshot on the 66 frames:** PASS (pixel checks on; 13 diff spikes, all inside planned windows; median diff 1.22). Report: `work/test_s12/qc_oneshot_445-510.json`.
- **A/V:** `work/test_s12/test_445-510_av.mp4` (frames + voice.wav from 14.8 s). Sync rests on the plan, not this clip: the plan's **2,571 frames = 85.69 s × 30 fps** of voice.wav, and every camera/overlay cue is resolved from the real word times in `captions.json`.
- **Caption timing:** every caption chunk lies inside its beat's speech window and starts on the real word time. This is checked from `captions.json`; overlay_v2 was not run.
- **Contact sheet:** `work/test_contact.jpg` (every 6 frames; the 1-per-2 s frames are marked `*2s`, since 2.2 s gives only 2). **It shows the PRE-FIX camera** (the tail-vane bug below). The fix is verified only by stills at 0.5 scale / 16 samples; it was not re-rendered at final quality or re-QC'd.
- **Flicker:** `pipeline/qc_flicker.py` on the test clip → `work/test_s12/qc_flicker_445-510.json`.
  - Caption band: 0 unexpected ABA.
  - Full frame: no unexpected spikes, but per-pixel flicker averages 0.76 % (max 5.6 %) on the hold frames.
  - It is concentrated on the thin grass blades at the bottom and the canopy edges at the top, plus a soft denoiser blotch on the lawn (`flicker_crop_470_472.jpg`).
  - Judged **minor** (shimmer, not a flash); re-check on the full video. Possible upgrade: more samples or a denoiser with albedo/normal guides.
- **qc_full / qc_v2:** not run. They need the finished MP4 (see below).

## SERIOUS issue found and fixed: tailgate_plan camera behind the flat tail vane
- In the test frames f449–498 (~1.7 s, mission beat "And yes, he pulled the permit first"), a big white slab filled the lower half of the frame and Bolts was seen from behind.
- A ray-cast on a saved still blend identified it as `bw_turbine_vane`, 1.4 m from the camera. While the tower lies flat (session 8 rotor/stand change), the tail vane sits right in front of the old `tailgate_plan` spot. That spot had never been stilled at its own frames.
- **Fix:** `tailgate_plan.pos` (118, 52.5) → **(124, 53.0)**, same height and look-at, in `episode.json` and `tools/make_build01_episode.py`.
- New stills f452/475/497 (`work/test_s12/tailgate_fix.jpg`): Bolts in 3/4 view, pointing along the flat tower, with the red pickup beside him and no occluder.
- Re-plan: still 2,571 frames, longest hold 4.6 s. `test_oneshot` ALL PASS.
- **The 66 test frames used the OLD camera.** They and their track file were moved to `work/test_s12/frames_445-510_oldcam/`, so the resumable full render will re-render them. `work/frames_oneshot/` is empty.

## Final MP4: path not ready (pipeline)
- `pipeline/overlay_v2.py` `_ctx` (line ~919) and line ~1004 hard-code `workdir = ROOT/output/<slug>`, which is WJH's `output/`. `make_episode.main` does the same.
- `step_assemble_v2` and `normalise_voice` already take a workdir; they just call `overlay_v2.assemble`, which doesn't.
- Page 3 has its own `page3/tools/make_episode.py` + overlay style work, but no page2 finishing script exists for build-01, and nothing in BUILD-LOG documents one.
- Needed before the final MP4: a workdir argument or env var for `overlay_v2.assemble` (a WJH/pipeline change). Alternatively, a page2 finishing script that does not route through `output/`. Then `oneshot.py link` → overlay_v2 → voice normalise → mux → qc_v2/qc_full.

## Hold sweep (real plan, one still per hold midpoint, 0.35 scale / 8 samples)
- 24 stills: `work/test_s12/hold_sweep.jpg` (`test_s12/sweep/`).
- **SERIOUS, fixed: `street_wide` (callback hold f2237–2290, "one porch light stays on") was fully blocked by a street-tree canopy.**
  - A ray-cast found `cc0_broadleaf_lod0` 1.1–1.9 m in front of the camera.
  - Cause: the world camera spot (-62, -10, 6) sits inside the street-tree row (|y| 9.5–14). Street trees skip `ok()`, so the 9 m spot clearance never applied, and that spot had never been stilled.
  - Fix (episode only, the world is unchanged): `spots.street_wide` = **(-62, -3, 6)** on the road centre-line, same look-at (0, 2, 3), lens 28, in `episode.json` + the generator.
  - New stills f2240/2264/2288 (`test_s12/street_wide_fix.jpg`): house, porch light ON, Bolts on the porch, pickup, dusk.
  - A canopy edge brushes the top-right corner at f2240 (minor).
- All other holds read correctly.
  - Minor: f1643 `tail_hinge__detail` shows mostly tower with the nacelle cut at the top, and the f1736 goose head pokes into a corner (the gag).
- After both fixes: plan 2,571 frames, longest hold 4.6 s, `test_oneshot` ALL PASS, `qc_oneshot` (plan-only) PASS. `oneshot/qc_oneshot.json` is refreshed (it had been from the synthetic era).

## For the Windows render
- Copy the two Quaternius zips to `assets/cc0/quaternius/` first. Without them, `BOLTS_IMPL` silently falls back to s6, which breaks the locked body.
- **Check `bolts_impl = s9_quaternius` in the first job's `stats_*.json`** before letting the rest run.
- Measure s/frame on job 1 (f1–150).

## Lower-cost option (estimate)
- At 0.5 scale / 16 samples: ~7–12 s/frame here → **~5–9 h**, still over 4 h on this Mac.
- EEVEE is untested on this scene.

## Open issues (minor, logged, not repaired)
- 5 caption words have zero length at sentence starts (interpolated): Again., Wind, Build, Honest, Small.
- Whisper base.en mishears in the alignment log only (captions use the script).
- Missing kit normal maps (known).
- The episode's director notes are terser than the voice-test sample notes. The take sounds verbatim; no style check by ear was done.

## Finishing Build #1 into an MP4 (WJH commit 6b93dcd, 25 Nov 2026)
`pipeline/make_episode.py` now takes `--workdir` and `--out-root`, and exports `EPISODE_WORKDIR` to overlay_v2/qc_v2. WJH's defaults are unchanged.
Once the full render is done (Windows laptop, `oneshot.py render` + `link`):
```
.venv/bin/python pipeline/make_episode.py page2/episodes/build-01/episode.json --workdir page2/episodes/build-01/work --out-root page2/episodes/build-01/out --steps assemble,fb,post,qc
```
Untested end to end: WJH only checked the imports. If you call overlay_v2 directly, set `EPISODE_WORKDIR=page2/episodes/build-01/work`.

## Windows render box: first NVIDIA measurement (Dell G15 5520, 26 Nov 2026)
- Setup: NVIDIA Studio Driver 621.40, Blender 5.3.0, Cycles **OPTIX** (RTX 3050 Ti Laptop, 4 GB), Python 3.12.10 venv. Repo at `C:\Users\fines\irfan` (outside OneDrive).
- `fetch_cc0.py --check`: all present (Quaternius zips sha256 OK). `cc0_lib.py build`: OK (`mercer_cc0_lib.blend` 91.6 MB).
- `test_oneshot.py`: **ALL PASS (0 failures)**.
- `oneshot.py plan` with the real timings (commit e7c9668): 2,571 frames (85.7 s), 24 moves, 16 events, 23 jobs, longest hold 4.6 s.
- `oneshot.py still --frames 300,1600 --scale 1.0 --samples 32` (1080x1920, `--mblur 3d`): exit 0 in **37.6 s for both frames** (about 22 s of world build). Stats: `device` OPTIX, `bolts_impl` s9_quaternius, est. images 538 MB + geometry 290 MB.
- **Peak VRAM: 2,735 MiB of 4,096** (nvidia-smi every 250 ms; 0 MiB at idle because the desktop runs on the Intel iGPU). That is inside the 3 GB target.
- Log: 2 missing UBC normal maps (`T_Hair_1_Normal_png.png`, `T_Eye_Normal_png.png`), the known kit issue.
- First run: f1600 (push-in to `tail_hinge__detail`, day preset) was washed out. Cause: `assets/polyhaven/` (gitignored) had not been fetched, so the log said "[mh] no HDRI ... procedural sky". Fixed with `tools/fetch_assets.py` (`--check` clean).
- Re-run with the HDRI: exit 0 in 39.4 s for both frames. f1600 is now normal (green field, grey tower). bolts_impl s9_quaternius. **Peak VRAM with HDRI: 2,909 MiB of 4,096** (inside the 3 GB target, about 160 MiB of headroom).

---

# Session 13 (26 Nov 2026, Opus): fast render profile
Goal: cut the Dell full render (7.7 h; 2,571 frames at 10.8 s/frame) toward 2 h. Opt-in only: **the default profile is unchanged**. Proof: the `still`/`render --dry-run` Blender command lines are byte-identical before and after, and the diff shows that render_oneshot runs no new code for `default` (the resolution is ×1.0, the output dir is the same, mblur comes from the CLI). No before/after pixel comparison was kept. Nothing outside `page2/` was edited. No commits.

## What changed
- **`blender/render_profiles.py` (new).** `PROFILES` holds `default` (empty) and `fast`. `apply_fast()` runs in Blender after the world and characters are built, before the world events are keyed. Fast settings:
  - 16 samples (unless `--samples` is given) and adaptive threshold 0.06; OptiX denoise (OIDN on Metal) as before.
  - Bounces max/diffuse/glossy/transmission **4/2/2/2**. **Transparent stays 8**: grass and leaf cards are alpha cut-outs, so a cap of 4 risks dark grass.
  - Indirect clamp 6 (default 8).
  - Cycles motion blur OFF.
  - Render at **0.75 × the final scale** (810×1440 for 1080×1920) into `WORKDIR/frames_oneshot_fast/`.
  - **Kitchen** (`world_mercer._kitchen_backdrop` + `mercer_cc0.kitchen_props`; `interiors.py` is not used by build-01):
    - The 140 W ceiling area light is removed (hide_render, keyed on-value 0) and its power folded into the existing emissive ceiling panel through the keyed `lights["kitchen"]` on-values: +P/(πA) × 1.2, i.e. 1.2 → about 6.7.
    - The props are rougher with no clear coat: steel/enamel 0.5, oak/walnut 0.55, tile 0.4, dark glass 0.35, fridge 0.45, butcher block 0.6.
    - On the Mac, the f2127 window-crop mean RGB is 171/159/144 for fast vs 171/158/143 for default (measured on the `mac050` bench PNGs).
  - Grass and leaves are untouched.
- **`blender/render_oneshot.py`.**
  - New `--profile` option; fast uses the 0.75 resolution, raw dir, `apply_fast` and forced mblur off.
  - `--warmup` (stills): one 1-sample render first, so frame 1 of a bench is comparable.
  - `--still-dir`: a still output folder.
- **`tools/fast_post.py` (new, PIL + numpy, pathlib only).** For each raw frame:
  - Lanczos upscale to the final size, then UnsharpMask (r 1.2, 45 %, threshold 2).
  - Then the 2D blur from `oneshot_blur.blur_spec()`, **recomputed from the current `camera_speed.json`** (the `blur_2d.json` on disk can be stale): radial for snap/portal, directional otherwise, px clamped at 60, scaled to the output width, holds and join frames never blurred.
  - The blur is computed in linear light with edge clamping.
  - **Deviation from blur_spec's mode:** a radial (snap/portal) frame whose mean screen motion is mostly one direction (|dx,dy|/px ≥ 0.5) is blurred **directionally**. The build-01 snaps are whip pans (f444 ratio 0.88), and a centred zoom blur read clearly wrong next to the Cycles 3D blur. 44 true push-in frames stay radial; 37 snap frames switch. `oneshot_blur.py` (shared with Page 3) is unchanged.
  - Output: `frames_oneshot/####.jpg` (q95, 4:4:4) via a temp file and `os.replace`. It is idempotent; the raw frames are never modified.
- **`tools/oneshot.py`.**
  - `--profile` on still/render/bench. Precedence: CLI, then episode `render.profile`, then `default`. `--samples` defaults to the profile's value, else the old 8 (still) / 16 (render).
  - `render --profile fast` runs `fast_post` after every job. Resume: a job whose final frames exist is skipped; if only its raw frames exist, only post is run.
  - `.profile.json` (profile + scale) is written to both `frames_oneshot/` and `frames_oneshot_fast/`. **A fast render refuses to start if either folder holds frames from another profile or scale** (e.g. the default render, or raw frames from a 0.35 test that would otherwise be re-posted): move them away, or use `--force`, which re-renders every job.
  - `still --profile fast` post-processes the PNG stills in place.
  - New `post` command (re-run the post step).
  - New `bench` command. It renders 6 fixed frames as stills after a warm-up and writes `WORKDIR/bench/<profile>_<engine><tag>/` with `f####.png`, `bench.log`, `stats.json` and `bench.json` (per-frame render seconds and, for fast, post seconds). Bench defaults: scale 1.0; samples come from the episode `render.samples` (32) for default and 16 for fast; mblur 3d.
  - Bench frames: f60 hook dusk wide, f907 day wide grass (tower_low), f473 Bolts pointing medium (tailgate_plan), f444 mid-snap 3D blur (tailgate snap 440–448), f2127 kitchen window hold, f2240 callback street dusk.
- **`tools/bench_sheet.py` (new).** A contact sheet with one row per frame and one column per bench run.
- **EEVEE:** `--engine eevee` works for stills of this episode with the same cameras. No fixes were needed. It is not tuned: the dusk frames are slow on Metal and the kitchen reads flatter.

## Commands
```
.venv/bin/python page2/tools/oneshot.py render page2/episodes/build-01/episode.json page2/episodes/build-01/work --scale 1.0 --profile fast
.venv/bin/python page2/tools/oneshot.py post   page2/episodes/build-01/episode.json page2/episodes/build-01/work --scale 1.0 [--range A-B] [--force]
.venv/bin/python page2/tools/oneshot.py link   page2/episodes/build-01/episode.json page2/episodes/build-01/work   # unchanged
```
Or set `"profile": "fast"` in episode.json `render`.

## Mac timings (M2 Pro, Metal, bench scale 0.5, indicative only)
| Frame | default 32 spp, 3D blur | fast (405×720 → 540×960) | EEVEE default (32 TAA) | fast, 1 spp (overhead) |
|---|---|---|---|---|
| f60 hook dusk | 5.3 | 2.7 | 67.5 | 2.1 |
| f907 day grass | 10.3 | 7.5 | 9.3 | 4.3 |
| f473 Bolts point | 16.5 | 9.6 | 14.9 | 5.6 |
| f444 snap | 15.7 | 10.2 | 13.0 | 6.2 |
| f2127 kitchen | 22.9 | 11.8 | 4.2 | 6.6 |
| f2240 callback dusk | 7.0 | 4.0 | 51.7 | 1.8 |
| **mean s/frame** | **12.95** | **7.63** (+0.09 post) | **26.77** | **4.43** |

- At this small scale, fast is only **about 1.7× faster** (a second fast run gave 8.38 s mean, so the Mac run-to-run spread is roughly ±10 %).
  - About 4.4 s/frame is fixed per-frame cost that samples and resolution do not change (scene re-sync, BVH update, denoise).
  - This is **not just a still artefact**: a consecutive fast animation job at 202×360 also ran at 4.7–5.0 s/frame.
  - On the sampling part alone, fast is about 2.5× faster.
- **Expectation:** fast alone probably will not take the Dell from 7.7 h to 2 h unless its fixed per-frame cost is small. The `_s1` Dell run below answers that.
- Kitchen: one warm ablation gave fast 9.2 s vs fast without the kitchen changes 14.5 s (default 23.2 s). But f907, which has no kitchen in view, swung from 6.6 to 8.9 s between those same runs, and later fast runs gave f2127 at 9.5, 13.6 and 11.8 s. So the kitchen saving is **probably real but not cleanly measured**.
- Sheet: `episodes/build-01/work/bench_mac_sheet.jpg` (columns default / fast / EEVEE). Bench data: `work/bench/{default_cycles,fast_cycles,default_eevee,fast_cycles}_mac050*/`.
- `test_oneshot.py`: ALL PASS.

## Look (Mac sheet)
- Dusk, day grass, Bolts, kitchen and callback: fast reads the same as default. It is slightly softer from the upscale, and the kitchen brightness and colour hold.
- **Snap frames: the blur is weaker.**
  - With the whip-pan override above, f444 now streaks in the right direction. Radial had given a zoom with a sharp centre, which looked wrong.
  - It is still much weaker than the Cycles 3D blur. The raw motion is 850–4000 px/frame, and the 2D blur is clamped at 60 px.
  - If it reads too crisp in motion, raise the cap for fast_post only (`blur_spec(cs, cap=...)`). Judge it on a played clip.
- **Not verified:**
  - Temporal flicker at 16 spp with threshold 0.06 (only stills were checked).
  - Bloom from the brighter ceiling panel on the kitchen approach (f2032–2076); f2127 showed no ceiling in frame.

## Dell benchmark (run on the Dell, repo root, one Blender at a time)
```
.venv\Scripts\python page2\tools\oneshot.py bench page2\episodes\build-01\episode.json page2\episodes\build-01\work --profile default --engine cycles
.venv\Scripts\python page2\tools\oneshot.py bench page2\episodes\build-01\episode.json page2\episodes\build-01\work --profile fast --engine cycles
.venv\Scripts\python page2\tools\oneshot.py bench page2\episodes\build-01\episode.json page2\episodes\build-01\work --profile default --engine eevee
.venv\Scripts\python page2\tools\oneshot.py bench page2\episodes\build-01\episode.json page2\episodes\build-01\work --profile fast --engine cycles --samples 1 --tag _s1
.venv\Scripts\python page2\tools\bench_sheet.py page2\episodes\build-01\work default_cycles fast_cycles default_eevee --out page2\episodes\build-01\work\bench_dell_sheet.jpg
```
- Profile defaults: scale 1.0 for all runs; default = 32 spp + 3D blur, fast = 16 spp at 810×1440 + post, EEVEE = 32 TAA.
- The `_s1` run measures the per-frame overhead on OptiX. If it is a large share of the 10.8 s, samples and resolution cannot reach 2 h. The next lever would then be the per-frame re-sync (keyed material/world values), not sampling.
- A real check: `render --profile fast --range 1-150` and compare its s/frame with job 1 of the default render.
- Before a full fast render, move the default frames out of `frames_oneshot/` (the guard refuses otherwise).

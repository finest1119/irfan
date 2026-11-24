# BUILD-LOG — Page 3 offline prep (24 Nov 2026, Opus)

Scope: offline prep only. No Blender run, nothing outside `page3/` modified, no `.env` read, no network, no git.

## What I did
1. Read `page3/PLAN-v1.md`, `pipeline/README.md` (v2 sections), `episodes/2026-11-26-2-ship-collision/episode.json`
   (newest v2), `page2/PROPOSAL-v1.md` §4, and the relevant bits of `pipeline/overlay_v2.py` (overlay types,
   cue matching) and `pipeline/captions.py` (`norm()`), read-only.
2. `page3/WORLDS-SPEC.md`: coordinate layout (origin = main intersection, Z up, +Y north) and one section for each
   of the 37 stops (what, where, `ANC_<stop>` anchor, props, method, light, caption-band framing). It also covers
   the cut-away methods (S1 peel, S2 slice, N nested, R floating-origin rebase, P portal), the Spark, the 8-move
   camera library with durations and easing, 2D motion blur, assets, the 4 GB VRAM/texture budget, and the build
   order: M0 blockout, then **M1 first preview = the 10 s benchmark clip**.
3. `page3/page.json`: name, fixed voice Sadaltager + PLAN 3.5 director notes, palette, amber caption highlight,
   font placeholders, cards (TWIST / series / stop chips), base hashtags, sign-off, ET slots + ramp-up.
   FB IDs are env var names only (`FB_PAGE_ID`, `FB_PAGE_TOKEN`).
4. `page3/tools/make_episode.py` (stdlib, pathlib): script JSON → `page3/episodes/<date>-<id>/episode.json` with
   v2 fields + `oneshot` block. Supports `--check`, `--batch` (skips `_*.json` unless `--include-underscore`),
   `--date`, `--out-root`, `--force`.
5. `page3/scripts/_sample.json` (C5 water tower, marked SAMPLE / not fact-checked). Generated
   `page3/episodes/2026-11-24-c5-water-tower-sample/episode.json`: OK, 257 words.
6. `page3/tools/test_make_episode.py`: 18 unittest cases, **all pass** (they write only to a temp dir).
7. `--batch --check` over the other agent's 10 scripts (`01-5g` … `10-streaming`): **10/10 OK**. I didn't edit
   them. A full generate into the scratchpad (not `page3/episodes`) looked sane: unique ids/slugs, series chips like
   "DECODED · MONEY & PAYMENTS #1", first move drift/orbit, last backout, no beat with two overlapping cards.
   I added a warning for that case (two cards in one beat with no `until` on the earlier one).

## Decisions
- **Python:** this Mac has only 3.9.6 (system + `.venv`), so the code is 3.11-targeted but 3.9-safe
  (`from __future__ import annotations`, no `match`).
- **Overlays:** only types `overlay_v2.py` knows are emitted (it does `ITEM_TYPES[type]` → unknown type =
  crash). TWIST = `card` + `"style": "twist"` (verified: overlay_v2 `Card` reads only `text`/`sub`, so the extra key is
  ignored today). Series chip and STOP-n chips go in
  the `oneshot` block (`series_chip`, `stop_chips`), not in overlays. A beat's chips are merged into one `chips`
  item (`items` + `cues`). `label.anchor` = the beat's stop id.
- **Cues** are normalised like `captions.norm()` and must prefix-match a word of the beat text. `at` is accepted
  instead of a cue for card/label/big.
- **twist_beat** must exist and must contain exactly one TWIST overlay (otherwise fail). No TWIST outside it.
- **Brands:** case-insensitive word-boundary match. Ordinary-word brands (Target, Apple, Amazon, Carrier,
  Galaxy, Sprint, Spectrum, UPS, Discover Card) match only Capitalised/ALL CAPS forms. `sources` and
  `fact_notes` are exempt (citations may name companies). The list is longer than the brief's (adds Venmo, Zelle,
  PayPal, Hulu, YouTube, E-ZPass, FedEx, HVAC makers …).
- **Spark vocabulary** = teal / amber / ice / **off** (I added "off" to hide the orb on wide beats).
- **Stop → world** is an explicit dict; `macro_microwave_mesh` counts as W3. A stop must belong to a world listed
  in the script's `world`. W4/W5 are rejected until they are built.
- **`render.parallel = 1`** and **`pause_between_beats = 0.3`** come from page.json (PLAN 7b one GPU process;
  PLAN 3.5 ≈ 0.3 s gaps), not from the copied WJH values (3 / 0.2). The other render/tts defaults are copied from
  the v2 episode.
- `sources`: flattened to v2 strings `"claim: url ; url"`, with the structured copy in `sources_structured`.
  Hashtags = script tags + base tags, deduplicated.
- **W2 at mm scale (proposed, UNTESTED):** true nesting plus a *floating-origin rebase* (see open question 8).
- **Motion blur:** 2D in the overlay step by default (camera-motion export), with Blender blur as a
  benchmark-dependent option.

## Open questions for the planner
1. **Amber caption highlight** needs a per-Page colour option in shared `pipeline/overlay_v2.py` (today it is
   red), and `card.style: "twist"` needs an amber card style there. Both are shared changes for the port.
2. `ed_oneshot` builder / `--mode oneshot` does not exist yet. Today's v2 renderer would fail on these episodes
   (expected; the shared renderer is a dependency).
3. Is "off" OK in the Spark vocabulary, or should it stay at only the 3 colours?
4. Should `render.parallel` / `pause_between_beats` keep the WJH values (3 / 0.2) as the brief's "copy defaults"
   says? I chose 1 / 0.3 per the PLAN.
5. Sky layer is **not to scale** (stylised stage above a cloud deck). Are on-screen numbers via overlays enough?
6. The sample uses placeholder source URLs (domain-level only), so it must never be posted. Should `--check` also
   enforce ≥ 2 distinct URLs as an error? Today it is a warning.
7. The coordinates are first guesses. M0 blockout stills (37, 0.25 scale) should be reviewed before detail work.
8. **Floating-origin rebase is unproven** (nothing rendered). All of W2 relies on it: everything, including the
   camera, is parented to `WORLD_ROOT`, which is re-keyed inside whip windows so the macro set sits near the
   origin. Prove it in build step 6 (3 s snap-in/back-out test per set: no jitter, no acne, no visible jump, motion
   blur OK at the switch frame). Fallback if it fails: a fill-frame portal into an enlarged (×20) copy of the set,
   placed near the world origin.

---

# Session 2 (24 Nov 2026, Opus): Hometown USA world module for the shared one-shot renderer. Still NO Blender run.

Scope: wrote only inside `page3/`. Read `page2/` and `pipeline/` but did not edit them. No Blender, no `.env`, no git,
no Facebook. Every Python run used `PYTHONDONTWRITEBYTECODE=1` (no `__pycache__` written into page2/).

## Files
| File | What |
|---|---|
| `blender/hometown_usa_plan.py` (new, bpy-free, 3.9+) | `plan_anchors(state)` for `page2/blender/worlds.py` (found by file convention, world id `hometown_usa`). Holds all 37 stops: `ANC_` look point, `CAM_` position and lens for every stop, zone, and world. Also: nested host frames (phone, card, terminal, gum pack) as rigid transforms shared with the Blender side; zone boxes + culling radii; S2 slices (ground holes, lids, slide vectors); S1 peel groups; and the per-frame **world timeline** computed from `plan.json` (stop track, peel/lid amounts, zone visibility, zones per job/beat, clip planes, rebase switch frames, backout/hold stats). `tune_holds()` is the page3 hold workaround (below). |
| `blender/hometown_usa.py` (new, needs bpy) | `build(ctx, state)` returns `{stop: ANC_<stop>}`; `apply_events(state, plan, lo, hi)`. One method per district/set. Districts: ground + roads + lids (always), far LOD + district proxies, downtown (blocks, mast-arm intersection, loop slice, signal cabinet, strip mall exterior), strip mall interior (counter, flush scanner, terminal/card/gum hosts, shopper hand), suburb (instanced houses, GN trees, poles + wires, hero house shell with peel panels, condenser, meter, wall slices, person + phone host), house interior, basement, Maple St slice (main, saddle, service line, gas, conduit bank with a sliced duct + fiber strands, handhole), cell tower compound, data center + hall, substation + transmission line, water tower (bisected tank, peelable front half, water volume, gravity arrows) + treatment plant, sky (cloud deck, billboard clouds, satellites, signal cones), and the W2 macro sets (phone board/antenna, card chip/coil, terminal, scanner, microwave mesh). Everything is built with `scene_lib_v2` / `mh_blender` helpers that `world_mercer` already uses. Materials are procedural or the 1K Poly Haven detail maps; no image over 1K; no 3D text. |
| `tools/plan_all.py` (new) | Runs synth timings, `oneshot.py plan` and `qc_oneshot.py` for every episode into `_plan_test/<id>/`. Then checks what QC does not: backout length, settle and exact frame-1 end; hold drift against subject distance; rebase/macro frames; zones per job; snaps to the stop the camera is already at. |
| `tools/test_hometown_plan.py` (new) | 13 unittest cases: vocabulary = make_episode, host frames, `rect_minus_holes`, registry resolution + hold tuning through page2's real `plan_inputs`, idempotence, lid stays open through ep 08's snap, macro clip planes, beat-range zones, rebase inside move windows, no runaway drift. **All pass.** |
| `tools/smoke_hometown_mock.py` (new) | Blender-free smoke test of `hometown_usa.py`. bpy/bmesh are MagicMocks. `mh_blender`, `scene_lib_v2` and `scene_lib` are stubs generated from their real source with the **real signatures**, so a wrong argument count or keyword raises. Runs `build` with all 18 zones plus `apply_events` over every planned episode; also job-range culling, `ED_REBASE=1` and `--parts`. Static check: every `B.`/`S.`/`L.`/`P.` attribute exists. **All 11 OK.** |
| `tools/make_episode.py` | `MOVES["backout"]` 2.5 → **4.0 s**. `test_make_episode.py` passes 18/18, and `--batch --check` gives 10/10 OK. |
| `episodes/*` | Regenerated with `--batch --include-underscore --force --date 2026-11-24`: the c5 sample plus 10 batch-01 episodes (`2026-11-24-ed-01-5g` … `-ed-10-streaming`). |
| `WORLDS-SPEC.md` | Backout row is now 4.0 s. Added the 2D-blur note (clamp at 60 px, skip `join` frames) and the new section **7b Session 2 coordinate notes**. |
| `.gitignore` (new) | `_plan_test/` |

## Plan results (synthetic timings, 175 wpm; `.venv/bin/python page3/tools/plan_all.py`)
All 11 plan, and `qc_oneshot` plan checks PASS on all 11. Never static > 1 s. Every backout gets its full 120 frames
and ends on the exact frame-1 framing.
| episode | frames | s | moves | backout fr | backout path m | peak m/frame | settle fr | max zones/job | warning |
|---|---|---|---|---|---|---|---|---|---|
| c5-water-tower-sample | 2912 | 97.1 | section section travel crane travel backout | 120 | 2640 | 145.1 | 306 | 11 | - |
| ed-01-5g | 3095 | 103.2 | snap travel crane section travel travel backout | 120 | 1425 | 76.7 | 504 | 11 | - |
| ed-02-wifi-vs-microwave | 2912 | 97.1 | travel travel snap travel travel backout | 120 | 30 | 1.0 | 551 | 12 | - |
| ed-03-tap-to-pay | 3095 | 103.2 | snap portal travel travel snap backout | 120 | 807 | 38.4 | 513 | 11 | - |
| ed-04-barcode-gum-1974 | 3017 | 100.6 | snap portal travel snap backout | 120 | 3 | 0.1 | 495 | 6 | - |
| ed-05-central-ac | 3156 | 105.2 | travel section travel section snap backout | 120 | 23 | 0.6 | 510 | 10 | - |
| ed-06-microwave-door-mesh | 3155 | 105.2 | portal snap backout | 120 | 3 | 0.1 | 472 | 8 | portal f420 to the stop it is already at |
| ed-07-water-tower | 2994 | 99.8 | section section travel crane backout | 120 | 1771 | 100.4 | 371 | 11 | - |
| ed-08-traffic-light-loop | 3175 | 105.8 | section snap travel crane section backout | 120 | 155 | 6.1 | 558 | 8 | snap f736 to the stop it is already at |
| ed-09-gps-relativity | 3139 | 104.6 | crane travel snap crane backout | 120 | 7279 | 265.4 | 469 | 12 | - |
| ed-10-streaming | 3011 | 100.4 | travel section travel travel travel backout | 120 | 1514 | 101.7 | 402 | 11 | - |

## Decisions / assumptions
- **Hold workaround (page3 only).** `camera_plan` drift is a fixed 0.6 m/s and orbit is 4°/s. Beats here are
  8–23 s long. Measured with page2's raw holds: the camera (and its look point) slides up to **599×** the subject
  distance in ep 04 (≈11 m away from a 19 mm barcode), and 5.1× / 5.7× in ep 07 / ep 05. With page2's orbit kept at
  4°/s and a 4 %/s drift it was still 1–1.5× (tower orbit 168°). `plan_anchors` now calls `tune_holds()` on
  `state["episode"]`. That is the expanded copy `worlds.plan_inputs` hands to `build_plan`, so the change reaches the
  plan. The tuned values: drift = 1 %/s of the subject distance, orbit ±1.5°/s, and a macro drift becomes an orbit.
  After the fix the worst hold moves its look point ≤ 22 % of the subject distance. This depends on page2 passing that
  same object. If page2 starts copying it, the tuning stops silently, but `plan_all.py` would catch it (look-ratio
  check). The proper fix is page2's (see the list below).
- Ep 08's snap inside `road_loop_slice` gets `section: None` in the plan. The lids follow the **stop track**, not the
  section events, so the loop lid stays open (tested).
- Peels/lids start opening 0.2 s before their move, take 0.4 s (peels) or 0.6 s (lids), and also open when the camera
  will be inside the peel's box within 0.4 s. All of this is keyed per frame with `B.set_keys` (LINEAR).
- **Culling:** zone sets are computed per **beat** (`beat_range`), so a proxy→detail swap lands at a beat start. A beat
  start sits inside the next move's window, because moves start 0.4 s before the beat. Exterior districts are built
  within 500–600 m, or within 150 m when the camera is inside a building or closer than 0.15 m to its subject.
  Interiors, macro sets and sky also get per-frame `hide_render` keys.
- **Clip planes** are keyed per frame on `scene.camera.data`: start = 1 % of the subject distance, clamped to
  0.2 mm … 0.1 m, end = start × 1e5. This works because `render_oneshot` calls `apply_events` after `make_camera`.
- **Rebase (R)** is implemented (`key_rebase`) but **off** unless `ED_REBASE=1` (needs page2, see below). Float32 at
  ≤ 250 m from the origin is ~1.5e-5 m, against ≥ 0.33 mm macro detail, so it should be fine for the first tests.
- The phone dive comes from the screen side: the display peels instead of the back glass (WORLDS-SPEC 7b).
- Per-episode graphics (Wi-Fi rings, IR pulses, beam-steering cone, traffic-signal phase change) are **not** built.
  The signals are static: NB red, EW green. They need a per-episode hook later.

## Untested bpy parts (everything in `hometown_usa.py`; the mock test only proves Python logic and helper signatures)
Highest risk: the procedural shaders (barcode sine bars, microwave sine-grid alpha + DITHERED, strata ColorRamp
CONSTANT on Object Z, cloud/cone alpha); `bmesh.ops.bisect_plane` (tank halves, sliced duct); `create_grid` hill; host
empties (`rotation_euler` XYZ = plan `Frame`: X then Z); `set_keys` on camera-data `clip_start/clip_end`;
`vis_keys` on whole zone collections; area light `visible_camera`; GN tree scatter from template objects; per-frame
location keys on peel/lid objects (children of host empties use local offsets).

## First Blender still: what to verify (one process, after "BLENDER CLEAR")
```
# irfan runs these (the still command resolves Blender through pipeline/platform_cfg -> .env)
.venv/bin/python page3/tools/plan_all.py        # recreates page3/_plan_test/<id>/ (timings + plan)
.venv/bin/python page2/tools/oneshot.py still page3/episodes/2026-11-24-ed-01-5g/episode.json \
    page3/_plan_test/2026-11-24-ed-01-5g --frames 60 --scale 0.35 --samples 8 --parts ground,far,suburb --no-wait
# then without --parts, one frame per stop group, e.g. ep 07 (house/slices/water), 03 (mall/macro), 09 (sky)
```
1. Sun from the SSW (shadows point NNE), HDRI found, haze light; lawn/asphalt/sidewalk read; **no black gaps** at the
   slice holes (lids cover them) and no z-fighting between lids and roads.
2. `ANC_*` empties on the right objects (label tracks), and every `CAM_*` framing respects the caption band
   (22–31 % = sky/plain wall). Compare against WORLDS-SPEC framing notes; numbers are first guesses (M0).
3. Peels: walls sink fully below the lawn, roofs lift clear, kitchen/living room bright (area lights, open side).
4. Macro (ep 01 f430+, ep 03 f380+, ep 04, ep 06 f1290+): frames are not empty (clip planes keyed), the display peel
   clears the board, lightboxes light the sets, no shimmering of the mesh/barcode procedurals.
5. Zone keys: nothing visible pops on a hold; proxies vs detail at beat starts. Stats: s/frame, peak VRAM (≤ 3.2 GB),
   build time per job (the backout beat builds 11–12 zones).

## Page 2 changes needed (not made; page2 is read-only for this session)
1. **`page2/tools/test_oneshot.py` `test_registry` now FAILS** ("unregistered hometown_usa must fail"), because
   `page3/blender/hometown_usa_plan.py` exists. Point the test at a made-up world id. Everything else in that file
   passes, including the adapter/portal tests on the regenerated sample.
2. **Hold scaling:** drift should scale with subject distance (WORLDS-SPEC: ≈1–4 %/s), or `plan_location` should pass
   per-stop hold hints from `cams` (it keeps only pos/lens). `screen_motion`'s 0.5 m focus floor also over-boosts holds
   at macro distance. Then `tune_holds` can go.
3. **Rebase:** parent `MH_Cam`, its target and `ED_Spark` to the world root, or create the Spark before
   `apply_events` / pass it in. Until then `ED_REBASE` stays off.
4. **Precision:** `View.as_list` rounds the camera (and the Spark track) to 1e-4 m. On a 19–35 mm macro subject that is
   a quantisation step of about 0.05 mm, i.e. several px of jitter per frame on holds. Use 1e-6 or relative rounding.
5. **Backout timing:** the adapter starts the backout at the start of the last beat, so it lands 10–19 s before the end
   (settle 306–558 frames) and the reel does not end on the frame-1 framing. For a loop, cue it to end about 0.5 s
   before the last frame.
6. **Backout path:** it replays every arrival. Ep 09 (sky twice) covers 7.3 km in 4 s, up to 265 m/frame; ep 07 and
   the sample cover 1.8–2.6 km. Dedupe revisits, skip far detours, or cap the path length.
7. **Same-stop snap/portal** (ep 06 f420, ep 08 f736) has no push-in. The adapter could push e.g. 40 % closer when the
   target is the current stop.
8. Page 3 worlds get no clearance pass (`obstacles_from` only knows Mercer zones). Most crossings are covered by peels,
   but thermostat → basement coil (ep 05) still crosses a hall partition for about 2 frames inside the travel window.
9. overlay_v2 blur: clamp `camera_speed.json` px at 60 and skip `join` frames (WORLDS-SPEC 1.4 note).

---

# Session 3 (24 Nov 2026, Opus): holds ≤ 9 s (variant views + native camera keys) and the portal interior. No Blender.

Scope: wrote only inside `page3/`. Did not edit `page2/` and made no commits. Built on Page 2 Session 4, which added
hold caps, the over-10 s plan failure, native keys taking priority over the compact block, and auto-derived
variants. Page 3 registers its own variants, and page2's derivation is only the fallback for unregistered ones.

## What changed
- `blender/hometown_usa_plan.py`
  - `VARIANT_SPEC`: every stop gets a `__detail` and an `__alt` view, each with a one-line description. They are
    built as offsets of the stop's anchor and camera; nested macro stops use host-local offsets.
  - `VIEWS` = 37 stops + 74 variants + 3 portal-interior views. `plan_anchors` exports all of them, so they are real
    `ANC_`/`CAM_` positions, not derived ones.
  - New helper `base_stop()`: peels, lids, zones and the stop track map a variant to its stop.
  - New zone `Z_MW_INSIDE`, also added to `INTERIORS`, so the far town is culled while the camera is inside it.
  - `HOLD_TUNING` stays **off**; page2 owns hold scaling now. That flag was changed outside this session, and I left
    it as found.
- `blender/hometown_usa.py`
  - Anchors are built for all `VIEWS`.
  - New method `build_mw_inside()`: the enlarged (×20) microwave cavity at (0, 0, −300). It is a closed room with
    metal walls, a perforated door wall (32 mm holes) glowing from the kitchen, a turntable with a bowl of soup, the
    magnetron and wave-guide with mica cover, the cavity lamp, amber standing-wave ribbons, and key + fill area lights.
  - `perforated_mat(pitch)` is now parameterised.
  - `Z_MW_INSIDE` gets per-frame hide keys.
- `tools/make_episode.py`
  - New `camera_keys()`: estimates speech at 170 wpm, with sentence/comma pauses, and carries a running hold over
    from the previous beat.
  - When a hold would exceed 9 s, it writes page2-native `shot.camera` keys. The first key repeats what the adapter
    would emit; the rest cycle main → `__detail` → `__alt`, cued at sentence starts as `word#n`, and fall back to
    word starts. Moves between views alternate snap 0.3 s and travel 1.0/0.8/1.2 s.
  - The last beat holds on the twist stop's views, then cues the backout so it ends about 0.6 s before the reel ends:
    settle is now 12 frames instead of 306–558.
  - A portal onto the current stop goes to `<stop>__inside`. Any move out of an `__inside` view becomes a portal.
  - The validator fails any estimated hold over 10 s.
- `tools/plan_all.py`: reports the longest hold and the number of camera keys per episode, and fails any hold over
  10 s.
- `tools/test_hometown_plan.py`: 4 new tests.
  - Variants exist for every stop and `__detail` is a push-in.
  - Every native key resolves to a view, its cue word exists, and all holds are ≤ 10 s.
  - Every portal in the scripts lands in an interior, and the camera never flies out of `__inside`.
  - A long beat is split at words.
  - Two tests were updated, because episodes now carry native keys and hold tuning is page2's.
- `WORLDS-SPEC.md`: new section **7c**, with the variant table, the splitting rule and the portal interiors.

## Results (`plan_all.py`, synthetic timings; all 11 plan and pass qc_oneshot)
| episode | longest hold s | camera keys | backout m / peak m/frame |
|---|---|---|---|
| c5 sample | 8.6 | 15 | 426 / 10.9 |
| 01 | 8.2 | 16 | 98 / 2.5 |
| 02 | 6.9 | 18 | 12 / 0.3 |
| 03 | 7.6 | 16 | 1.4 / 0.03 |
| 04 | 7.1 | 16 | 1.6 / 0.04 |
| 05 | 8.9 | 16 | 6 / 0.15 |
| 06 | 7.2 | 19 | 2.9 / 0.07 |
| 07 | 8.2 | 17 | 483 / 12.2 |
| 08 | 8.2 | 16 | 45 / 1.1 |
| 09 | 8.6 | 19 | 2372 / 60.4 |
| 10 | 7.7 | 17 | 2.9 / 0.07 |
Tests:
- `test_make_episode` 18/18 OK; `--batch --check` 10/10 OK.
- `test_hometown_plan` 17 tests: 16 pass, 1 skipped ("hold tuning retired: page2 scales holds itself").
- `smoke_hometown_mock` 11/11 OK, with 19 zones.
The holds are estimates at 175 wpm (synthetic timings). Re-check `plan_all` once real TTS timings exist; the
validator target leaves about 1 s of slack.

## Untested / open
- The enlarged cavity and all variant framings are unrendered. Check the first stills for the caption band and for
  variant cameras inside walls, especially the `__alt` views of interiors and slices.
- Ep 06's backout replays every arrival, including the `__inside` views. It therefore flies straight from the
  cavity 300 m under the town up into the kitchen, inside the blurred backout. **page2 change needed:** the backout
  should hop hidden portal joins, or skip arrivals in enlarged sets.
- Ep 08's same-stop snap is still at f736 (`road_loop_slice` → itself, from the script's section → snap). Page2's
  same-stop push-in, or a script change, would fix it.

## Session 4 (25 Nov 2026): overlay_v2 per-episode "style" block (Page 3 owns it)
- `pipeline/overlay_v2.py` (on top of Page 2's port patch): optional `ep["style"]` =
  `{"font_set": "avenir"|"montserrat", "highlight_color": "#RRGGBB", "twist_card": {"bg", "fg"}}`.
  `apply_style()` runs on every episode load (`load_ep`, used by `_ctx`, `qc_streams`, `assemble`, so pool workers
  get it too). Missing keys -> WJH defaults (RED highlight, navy card + red accent) and platform_cfg fonts.
  The twist card is a `card` overlay with `"style": "twist"`: bg/fg colours, no accent bar. Bad values fail loudly.
- Test `page3/tools/test_overlay_style.py`: WJH frames from the git-HEAD overlay_v2 vs the current one are
  byte-identical (36/36 on high-rise-fire, ship-collision and turkey-fryer-fire); the Page 3 style gives an amber
  highlight, an amber twist panel without red, and Montserrat. 4/4 OK.
- Logged, not fixed (cosmetic per the QC rule): white caption text on the amber highlight has lower contrast than
  on red; twist-card text sits 6 px right of centre (room for the accent bar, which the twist card doesn't draw).
- Not committed: WJH still has uncommitted changes in the tree.

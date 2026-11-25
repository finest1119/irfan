# WORLDS-SPEC v1 — Everyday Decoded: Hometown USA (W1) + Cut-away House (W3) + Macro Kit (W2)

Written 24 Nov 2026 (Opus, offline prep; nothing rendered). Source of truth for the Page 3 world build.
Follows `page3/PLAN-v1.md` 3.2–3.4, 4, 7b and the shared one-shot plan in `page2/PROPOSAL-v1.md` 4.2.
The script writer and `page3/tools/make_episode.py` use **exactly** the 37 stop IDs below (fixed vocabulary).
Coordinates are approximate targets for the builder; keep the topology (what is next to what) and the anchor names,
adjust numbers freely when the blockout says so, then update this file.

---

## 0. Conventions

- Blender, metres, **Z up, +Y = north, +X = east**. Origin = centre of the main intersection (Main St × Elm Ave).
- ONE scene = `hometown_usa`: W1 + W3 (the hero house is a W1 lot) + W2 (sets nested inside real objects).
- Code (later): `page3/blender/world_hometown.py` (`build_world(ctx)`), `page3/blender/ed_oneshot.py` (camera,
  Spark, slices, rebase, culling). Page 3 code may *import* `pipeline/blender/scene_lib_v2.py` (`daylight`,
  `pbr`, `ph_detail`, `anchor`) but never edits it (PLAN 7b: shared changes only behind options, reviewed).
- **Anchors:** every stop has an empty named **`ANC_<stop_id>`** (plain axes, 0.1 × local scale) at the point labels
  point to and the camera looks at. The tracks exporter writes it under the key `<stop_id>` (so a script `label`
  overlay has `"anchor": "<stop_id>"`). Each stop also gets **`CAM_<stop_id>`** (default hold camera position) —
  the camera library builds paths between `CAM_*` positions and aims at `ANC_*`.
- **Zones** (collections, culled by camera position, section 6): `Z_DOWNTOWN`, `Z_STRIPMALL_INT`, `Z_SUBURB`,
  `Z_HOUSE_INT`, `Z_HOUSE_BASEMENT`, `Z_STREET_SLICE`, `Z_TOWER`, `Z_INDUSTRIAL_DC`, `Z_DC_INT`, `Z_POWER`,
  `Z_WATER`, `Z_SKY`, `Z_MACRO_PHONE`, `Z_MACRO_CARD`, `Z_MACRO_TERMINAL`, `Z_MACRO_SCANNER`, `Z_MACRO_MW`,
  `Z_FAR_LOD` (low-poly proxies of all districts, always on).
- **No 3D text anywhere** (v2 rule): signs, store bands, barcodes' digits, the water tower, trucks → blank or
  abstract icons. No logos/brand shapes. Stop signs = red octagon with white border, no letters.
- **Caption band** = 22–31 % from the top of the 1080×1920 frame (pixels ≈ 420–600). Every framing note below says
  what sits there; it must be sky, a plain wall/ceiling, smooth material or soft out-of-focus background.
  Labels live in 32–64 %, chips 64–80 %, cards 12–20 % (overlay_v2 bands).
- Light: exteriors use `S.daylight(ctx, sun_az≈210°, sun_el≈40°)` (HDRI `kloofendal_48d_partly_cloudy` 2K). All
  interiors are **bright lit "cut-away museum model" sets**, never dark (v2: never a void, no night).

### 0.1 Map (top view, not to scale)

```
 y
 ^                         water_tower (-260,430)           Oak Ln y=260      cell_tower (262,226)
 |  data_center (-420,330)        |                    houses ....  [tower compound]
 |                                |                        Birch St x=244 |
 |                                |                hero house (194..206,152..162)  garage (206..212)
 |  river x≈-760..-700            |                ---------- Maple St y=140 ---------- slice x 192..236
 |                                |                    suburb grid x 120..520, y 60..420
 |  treatment_plant (-640,-200)   |
 |                     strip mall (-130..-40, -70..-50)  [lot -10..-50]
 |  ===================== Elm Ave y=0 ====== (0,0) intersection ======================> x
 |                              Main St x=0
 |                                                     substation (430,-330) ===== power line y=-330 ===>
 |  Sky stage z 2000-2600 above (100,300); cloud deck z≈950 (Z_SKY, only when the camera is up there)
```

Extent of detailed world ≈ 1.4 km × 0.9 km; beyond it `Z_FAR_LOD` hills/tree band + HDRI.

---

## 1. Shared methods

### 1.1 Cut-away methods (no booleans at render time)
- **S1 Peel** (house walls/roof, cabinet doors, condenser lid, phone back, card top layer, terminal case,
  microwave casing): the shell is modelled as separate panels; when the camera approaches, the camera-side panels
  slide/hinge/fade away over 0.4–0.8 s, starting ~0.2 s before the camera crosses the shell. Cut edges get a thin
  **charcoal #1B1F24 cap with a 2 cm teal #00B3A4 edge line** (museum-model look, reads as "cut"). Panels come back
  on `backout` (reverse).
- **S2 Slice** (ground, road, wall cross-sections): the ground/wall mesh has a **permanent pre-cut box opening**
  with textured strata faces (asphalt → base course → soil → clay; PIL 1K textures in `page3/textures/`). A "lid"
  (the road/grass/drywall patch) covers it and slides 1.5× its length sideways or drops alpha to 0 over 0.6 s when a
  `section` move arrives; closed again after the episode no longer needs it. Underground utilities are real meshes
  inside the opening. Inside of the box gets one hidden area fill light (light-linked to `Z_*_SLICE` only).
- **N Nested scale** (W2 and every "dive inside"): the interior is modelled **inside the real object at real
  scale** (board inside the phone, coil inside the card, mesh inside the microwave door). The camera flies in with
  a `snap`/`portal` move while `lens` and `clip_start`/`clip_end` animate; the shell opens with S1 as it passes.
- **R Floating-origin rebase** (makes N work at mm scale on float32 GPUs): every object, light **and the camera**
  are children of one empty `WORLD_ROOT`. For any stop whose detail is < 5 mm (all `macro_*` stops and the
  `hand_phone` close-up) the renderer keys `WORLD_ROOT.location = -ANC_<stop>.world_location` with CONSTANT
  interpolation, switched only on a frame inside a whip window, so the active macro set sits within ~0.1 m of the
  true origin. Because the camera moves with the world, the image does not change at the switch (HDRI and sun are
  direction-only). Rebase back on the next non-macro stop. This avoids float jitter and Cycles self-intersection
  acne far from the origin.
- **Clip planes:** keep `clip_end / clip_start ≤ 1e5` (EEVEE depth; Cycles tolerates more). Defaults: exterior
  0.1 / 6000; room 0.02 / 2000; macro 0.0002 / 20 (camera inside a closed shell sees nothing farther anyway).
  Animate them during the whip into/out of a stop.
- **P Fill-frame portal** (only for extreme jumps): the camera pushes into a surface that fills the frame
  (cloud wall, glowing fiber end, black chip lid) for 2–4 blurred frames and emerges in another set of the same
  scene. Used for: crane into `sky_satellites` (cloud portal) and optional fiber-core shots. QC treats the portal
  frames as a whip window (frame-difference spike allowed only there).

### 1.2 The Spark
- **Orb:** UV sphere (16×8), emission strength 12 (Cycles) / 25 (EEVEE), colour per beat (`spark` value):
  **teal #00B3A4** (linear ≈ 0, 0.451, 0.371) data/money/water-as-signal; **amber #FFB000** (≈ 1, 0.434, 0) heat;
  **ice #7FD4FF** (≈ 0.212, 0.658, 1) cold/water; **off** = hidden (scale 0 over 0.3 s; e.g. wide establishing
  beats). Colour changes blend over 0.5 s, inside a move (e.g. C1: teal → amber at `ac_indoor_coil`).
- **Screen size constant:** a driver scales the orb so its diameter ≈ 2.5 % of frame width:
  `r = 0.0125 × distance(camera, spark) × 36 / lens_mm` (clamped 0.0003 m … 3 m). Works from mm macro to the sky.
- **Trail:** per episode the Spark path is baked as a poly-curve (bevel round, depth = orb r × 0.5, taper to 0);
  `bevel_factor_start/end` are animated so the visible trail = last ~0.4 s of travel. Same emission colour,
  strength fading to 0 along the taper (gradient on the curve's spline parameter).
- **Glow:** compositor Glare (Fog Glow, threshold 1.0, size 6) on the render, or a small 2D glow in the overlay
  step (decide at benchmark; EEVEE 4.2+ has no built-in bloom).
- **Fill light:** optional point light parented to the orb, radius = r, power scaled with r² so it lights nearby
  walls/PCB without blowing out (Cycles: light-linked to the zone it is in).
- **Behaviour:** leads the camera by 0.2–0.4 s on `travel`/`section`/`crane`; the camera aims at a point 30 %
  of the way from `ANC_<next>` to the Spark (so moves feel like "following" it). On holds it idles along the
  stop's local path (along the fiber, through the coil, around the mesh) at 0.1–0.3 × the local scale per second.
  Radio links (phone → tower, satellite → phone) = the Spark plus 3–4 expanding translucent teal rings (3D graphic,
  allowed), never a solid beam.

### 1.3 Camera move library (one camera `ED_CAM`, 30 fps)
A beat = its **arrival move** (from the script) + an automatic **hold** (`drift`, or `orbit` if the script says
so) until the next beat's move starts. Moves start **~0.4 s before the beat's first word** (from `timings.json`).
Never a static camera > 1 s. Easing names follow easings.net.

| move | duration (default, range) | easing | path / lens | motion blur |
|---|---|---|---|---|
| `travel` | 1.5 s (1.0–2.0; big reveal 5–7) | easeInOutCubic (reveal: easeInOutSine) | Catmull-Rom through `CAM_from` → via points (above roofs, along streets, never through solid walls unless S1 open) → `CAM_to`; aim blends from `ANC_from` to `ANC_to` over the first 60 % | yes when > 6 m/s screen-equivalent |
| `snap` | 0.3 s (0.2–0.4) | easeInOutExpo | straight push-in to a close-up of `ANC_to`; lens 24→35 mm; whoosh SFX | **yes, always** |
| `section` | 1.8 s (1.5–2.2) | easeInOutCubic | arc down/sideways to face the S2 cut at 25–40° off its normal; lid opens at t=0 | yes in the middle third |
| `portal` | 0.5 s (0.3–0.6) | easeInQuad in, easeOutQuad out | accelerate into the fill-frame surface (2–4 frames filled), emerge in the target set with matching direction; clip planes switch on the filled frames; rebase (R) here | **yes, always** |
| `crane` | 2.0 s (1.5–3.0; to the sky 4.0) | easeInOutSine | vertical rise/fall with tilt (−10°→+35° going up); slight lateral drift 5 % of height | only if > 6 m/s screen-equiv. |
| `orbit` | whole beat (hold) | linear, 0.3 s ease-in/out at ends | 8–15° around `ANC_stop` at constant radius and height, direction alternates beat to beat | no |
| `drift` | whole beat (hold) | linear, 0.3 s ease-in/out | lateral slide ≈ 4 % of subject distance per s + 5 % push-in over the beat | no |
| `backout` | **4.0 s** (2.0–4.0; was 2.5 s until Session 2: Page 2 measured ~1.5 km of camera path in 75 frames) | easeInOutCubic | the episode's waypoints in reverse (holds dropped), compressed; S1 panels close, slices close, rebase back; ends on the **exact framing of frame 1** (loop), then a 0.5 s settle drift | yes in the fast middle |

Rules: first beat move = `drift` or `orbit` (no whip on frame 1); last beat = `backout`; at most 2 `snap`/`portal`
in a row; a `travel` longer than 250 m uses a 15–25 m altitude via point so the city reads from above.

### 1.4 Motion blur
- **Default (4 GB-safe): 2D blur in the overlay/assemble step.** The renderer exports per frame
  `camera_motion.json`: screen-space velocity of the frame centre (px/frame), roll and zoom rate (lens change +
  forward speed / distance to `ANC`). The overlay step applies directional blur (pans/cranes) or radial zoom blur
  (snap/portal) **only inside whip windows**, strength ∝ velocity, capped at 60 px. Cheap on CPU, zero VRAM.
  **Note for whoever builds the overlay blur (Session 2):** the shared `camera_speed.json` `px` values are NOT a blur
  length. They run to hundreds of px on travels and ~9,000 px on a snap frame (near-depth grid points; Page 3 backouts
  move up to 265 m/frame in ep 09). Clamp the kernel to **60 px**, ramp it in/out over 2–3 frames, and **skip frames
  flagged `"join": true`** (portal cuts: their px is already clamped to the neighbours; blurring across the cut smears
  two different sets together).
- **Option (if the benchmark has headroom):** Cycles/EEVEE motion blur with `motion_blur_shutter` keyed 0 outside
  whip windows and 0.5 inside (EEVEE: steps = 4). Decide at the benchmark; never both at once.
- QC: frame-difference spikes allowed only inside whip windows (shared `qc_oneshot`, PROPOSAL 4.2 item 9).

---

## 2. W1 — Hometown USA (18 stops)

Look: bright US suburb + small downtown. Streets 10 m (residential) / 16 m (Main, Elm), asphalt with **double
yellow centre line**, white edge lines, concrete curbs + 1.5 m sidewalks, grass park strip, driveways. Downtown
blocks 2–4-storey brick/stucco, blank awnings. Utility poles along streets, cobra-head street lights, fire hydrants,
curbside mailboxes, stop signs (no letters), parked pickups/SUVs, a school bus, lawn trees.

### hand_phone
- **What:** a person standing on the hero house's front walk, phone in hand (screen = abstract app tiles, no UI
  text), in the opening "everyday moment" pose. The phone carries the W2 phone sets inside it.
- **Where:** person at (201.2, 148.5, 0), phone at ≈ (201.45, 148.70, 1.32), tilted 60°. `ANC_hand_phone` = phone
  screen centre. Scale: phone 147 × 71 × 7.8 mm. `CAM_hand_phone` ≈ 0.45 m behind/above the shoulder.
- **Props:** simple stylised person (no face close-up; hand + forearm detailed, sleeve), phone with glass + metal
  frame, house + driveway pickup behind, mailbox at the curb.
- **Method:** start stop of many episodes. Dives into `macro_phone_board`/`macro_phone_antenna` via N + R (snap).
- **Light:** daylight; sun from behind-left so the screen is not blown out; screen emission 2.0.
- **Framing:** phone in the lower-middle third (45–70 %), out-of-focus house façade/roof + sky behind; the caption
  band sits over the soft roofline/sky. Lens 35 mm, DOF optional (f/4 equiv) — off if noisy.

### cell_tower
- **What:** monopole cell tower (≈ 130 ft) with 3 sector antenna panels + small radio boxes, on a fenced lot
  behind the Oak Ln houses.
- **Where:** pole at (262, 226), height 40 m; antennas at 36–39 m. `ANC_cell_tower` = (262, 226, 37.5).
  `CAM_cell_tower` ≈ (250, 205, 34) looking up-north-east.
- **Props:** monopole (tapered cylinder, galvanized PBR), triangular platform, 3 × 3 panels, coax/fiber trunk down
  the pole, aviation-free (no beacon needed under 200 ft).
- **Method:** radio link = Spark + translucent rings from phone to the sector; beam steering (A1) = a narrow
  teal cone (alpha 0.25) that swings to follow the Spark.
- **Light:** daylight; panels white/grey; slight backlight from sun at el 40° for rim.
- **Framing:** antennas at 40–55 % height, **sky fills 0–35 %** (calm). Never put the lattice of tree branches in
  the band.

### tower_base
- **What:** the fenced compound at the pole's foot: equipment cabinets, a small shelter, a fiber handhole lid
  (S2 mini-slice) where the fiber leaves for the street.
- **Where:** compound 15 × 15 m centred (262, 226); cabinets at (265, 223, 0–2). `ANC_tower_base` = (265, 223, 1.5).
- **Props:** chain-link fence (alpha texture 1K), gravel, 2 cabinets (peelable door, S1: racks + blinking LEDs),
  cable bridge to the pole, handhole with conduit dropping toward Birch St.
- **Method:** S1 on a cabinet door; S2 mini-slice at the handhole (1.2 × 0.8 × 1 m) into the conduit that runs
  south along Birch St (x = 244) to the Maple St slice.
- **Light:** daylight + small fill inside the cabinet (light-linked).
- **Framing:** camera at 1.6–2 m height looking slightly down at the cabinets; the band over the **pole shaft + sky**
  or the plain shelter wall. Avoid the chain-link fence in the band (moiré) — keep it below 40 %.

### street_slice_fiber
- **What:** cut-away under Maple St: a conduit bank (4 orange/blue ducts) with one cut-open duct showing fiber
  bundles; a concrete handhole at the corner.
- **Where:** part of the shared Maple St slice (box x 192–236, y 136–144, depth 2.5 m). Fiber ducts at y = 138.5,
  depth 0.9 m. `ANC_street_slice_fiber` = (226, 138.5, −0.9).
- **Props:** strata faces (asphalt 0.1 m, gravel base 0.3, brown soil, clay), conduit bank, one duct sliced
  lengthwise (fiber strands = thin emissive-tip cylinders, instanced), handhole at x = 232 with the conduit from
  Birch St entering.
- **Method:** S2 (road lid slides east). Optional P (portal) into a glowing fiber end for "light in glass" beats.
- **Light:** sun from the open top + light-linked area fill (5600 K, soft) from the camera side; ducts glossy.
- **Framing:** camera on the south curb, eye level 0.4–0.6 m above the road surface, **pitched down only
  10–15°** with a 24 mm lens, so the slice interior fills 40–80 % and the far (north) houses' roofline + **sky**
  sit in the band. (A steeper look-down would put plain asphalt in the band — acceptable only if the asphalt is
  smooth and calm; never lane markings or the slice edge there.)

### data_center
- **What:** windowless data center on the edge of town: long low building, rooftop cooling units, generator yard,
  security fence, fiber entering underground.
- **Where:** building 90 × 60 × 12 m centred (−420, 330). `ANC_data_center` = (−420, 330, 12).
  `CAM_data_center` ≈ (−330, 230, 45) (aerial three-quarter).
- **Props:** grey insulated panels, roof chillers (instanced), 6 generator containers, transformer yard, fence, a
  few cars. No company signage.
- **Method:** S1 peel of a roof section (SE quarter) to reveal `edge_server_room` (N nested room scale).
- **Light:** daylight; roof units add detail; avoid large dark roof — light grey membrane.
- **Framing:** building low in frame (50–80 %), wide **sky over the band**; travel in from the town side so the
  water tower may appear on the horizon.

### edge_server_room
- **What:** one data hall inside the data center: hot/cold aisles, server racks with LEDs, overhead yellow fiber
  tray, raised floor tiles (cut-away edge shows cabling below).
- **Where:** SE quarter of the building, hall 30 × 20 × 5 m centred (−395, 315). `ANC_edge_server_room` = rack
  aisle centre (−395, 315, 2.2).
- **Props:** 2 rows × 12 racks (instanced, 1K emissive LED texture), fiber tray (yellow), cold-aisle containment
  doors (glass), floor tiles.
- **Method:** N (room scale) reached by `snap`/`portal` through the peeled roof; Spark runs along the fiber tray
  into one rack (rack door S1).
- **Light:** bright clinical: ceiling LED strip emission + 2 area lights; white floor; no dark "server cave".
- **Framing:** camera down the aisle at 1.7 m; band over the **white ceiling/containment roof**; rack LEDs in the
  middle band.

### substation
- **What:** fenced power substation: 2 power transformers, breakers, bus bars, steel frame (A-frames), control
  house.
- **Where:** yard 80 × 60 m centred (430, −330). `ANC_substation` = main transformer top (430, −330, 6).
  `CAM_substation` ≈ (395, −390, 28).
- **Props:** transformers with radiator fins, insulators (instanced), steel lattice frames (low-poly + alpha),
  gravel, fence, control house (blank).
- **Method:** none (exterior). Spark rides the bus and drops voltage (colour stays teal; scale slightly).
- **Light:** daylight; metal PBR; the insulator detail is fine-grained → keep it below 35 % of the frame.
- **Framing:** three-quarter aerial, **sky band above the frames**; power lines leaving to the east give a leading
  line.

### power_lines
- **What:** high-voltage transmission line entering the substation from the east (steel lattice towers) + the
  distribution feeders leaving north along Birch St (wooden poles with cross-arms).
- **Where:** transmission corridor along y = −330 from x = 470 to 1300 (towers every 250 m, 35 m tall).
  `ANC_power_lines` = mid-span (620, −330, 28). Feeder poles every 40 m up Birch St to Maple St.
- **Props:** lattice tower (low-poly + alpha 1K), 3 phase conductors as curves with sag (catenary), insulator
  strings; distribution poles (instanced), cross-arms, can transformers (shared with `pole_transformer`).
- **Method:** Spark travels along a conductor (curve-follow constraint) — the "wire highway" travel.
- **Light:** daylight; conductors thin → give them 1.5× real diameter so they read at 1080 px.
- **Framing:** camera beside the conductors looking along them; **sky fills the band**; towers/horizon at 45–60 %.

### pole_transformer
- **What:** the wooden utility pole by the hero house with a grey can (pole-mount) transformer and the service
  drop wire to the house.
- **Where:** pole at (189, 149), can at z = 8.5. `ANC_pole_transformer` = (189, 149, 8.5). Service drop runs to
  the house west wall at `smart_meter`.
- **Props:** pole (wood PBR 1K), cross-arm, insulators, can transformer, fuse cutout, service drop (curve, sag),
  street light on the same pole.
- **Method:** none (exterior); Spark slides down the drop wire to the meter.
- **Light:** daylight.
- **Framing:** looking up at the can from 6 m away, **sky over the band**, house roof in the lower third.

### water_tower
- **What:** the town water tower: single-pedestal "spheroid" tank, pale blue/white, **no town name** (blank).
- **Where:** on a low hill (ground z = 8) at (−260, 430); tank centre z = 48, tank radius 9 m, pedestal 4 m dia.
  `ANC_water_tower` = (−260, 430, 48). `CAM_water_tower` ≈ (−200, 370, 40).
- **Props:** tank + pedestal + balcony rail (alpha), access ladder, fenced base, riser pipe in a cut-away pedestal
  (S1 vertical slice to show water level for C5).
- **Method:** S1 slice of the tank/pedestal (water volume = simple blue translucent mesh, animated fill level);
  pressure "gravity" shown by teal/ice arrows (3D graphic) down the riser.
- **Light:** daylight, sun on the tank side facing the camera.
- **Framing:** the tank top always stays below the 32 % line (tank at 33–60 %); **sky fills the band** above it.

### water_main_slice
- **What:** the same Maple St slice, western part: 8-inch (0.2 m) water main with a tap/saddle and the service
  line to the hero house; curb stop box at the sidewalk.
- **Where:** main along y = 141 at depth 1.6 m; service line north at x = 200 to the house basement.
  `ANC_water_main_slice` = (200, 141, −1.6).
- **Props:** ductile-iron main (blue-grey PBR), saddle + corp stop, copper service line, curb stop box, gas line
  (yellow) at 0.9 m for context.
- **Method:** S2 (shared slice box; lid slides west for this half). Spark (ice) flows along the main and turns up
  the service line.
- **Light:** as `street_slice_fiber`.
- **Framing:** as `street_slice_fiber`; band over the north sidewalk/lawn and the hero house roofline/sky.

### treatment_plant
- **What:** water treatment plant by the river: intake, two round clarifiers, filter building, clearwell tank,
  pump house.
- **Where:** site 160 × 110 m centred (−640, −200); river band x ≈ −760…−700 (gentle water plane + banks).
  `ANC_treatment_plant` = clarifier 1 centre (−655, −190, 4). `CAM_treatment_plant` ≈ (−560, −300, 60).
- **Props:** clarifiers (25 m dia, rotating bridge), filter building (blank), pipes, tanks, river with reeds.
- **Method:** S1 slice of one filter bed (sand/gravel layers) for "filtered" beats.
- **Light:** daylight; water shader simple (glossy + small normal noise), no caustics.
- **Framing:** aerial three-quarter, river leading diagonally; **sky + far tree line in the band**.

### intersection
- **What:** the main downtown intersection: 4 legs, 2 lanes each way, crosswalks, **mast-arm signals** on all 4
  corners, pedestrian signals, cars waiting.
- **Where:** (0, 0). Mast-arm poles at (±9.5, ±9.5); signal heads hang over the lanes at ~5.5 m.
  `ANC_intersection` = (0, 0, 6). `CAM_intersection` ≈ (−25, −45, 9).
- **Props:** mast arms (yellow or galvanized), 3-light heads (emissive lenses animated by phase), stop bars,
  crosswalk stripes (PIL texture), 4–8 cars (instanced), a pickup at the NB stop line (D1 hero car).
- **Method:** signal phase is keyed to the episode (red → green on the cue).
- **Light:** daylight; lens emission 6 so lights read in sun.
- **Framing:** street-level 3/4 view; signal heads at 33–45 %; **sky/upper building façades (plain) in the band**
  — keep window grids below 32 %.

### road_loop_slice
- **What:** cut-away of the northbound approach lane: rectangular induction loop (6 × 6 ft) cut into the asphalt,
  wire in a sealed saw-cut, lead-in to a pull box at the curb.
- **Where:** NB lane 1 (x ≈ 2), loop centre (2.0, −14.0), depth 5 cm; slice box x 0.3–3.7, y −16…−12, depth 0.6.
  `ANC_road_loop_slice` = (2.0, −14.0, −0.08).
- **Props:** asphalt strata, loop wire (copper curve, 3 turns, 1.5× scale for legibility), sealant line on the
  surface, pull box, the hero pickup above with its steel frame (the field = translucent teal loop rings).
- **Method:** S2 (lid = the lane patch slides sideways); Spark circles the loop then runs the lead-in to the
  cabinet.
- **Light:** daylight + light-linked fill in the slice.
- **Framing:** low angle (0.6 m) from the curb looking across the slice; the **pickup body and sky** fill the band.

### signal_cabinet
- **What:** the traffic signal controller cabinet on the SE corner: door open (S1), controller unit, detector
  cards with status LEDs, cooling fan.
- **Where:** (11.5, −11.5), cabinet 1.2 × 0.6 × 1.5 m on a concrete pad. `ANC_signal_cabinet` = (11.5, −11.3,
  1.1).
- **Props:** grey cabinet, door hinge peel, rack with cards (emissive LEDs), wiring, the mast-arm pole behind.
- **Method:** S1 door swing; N (room-scale interior).
- **Light:** daylight + light-linked soft fill inside.
- **Framing:** camera 1.5 m in front at 1.3 m; band over the **cabinet's plain upper door/top and sky**; cards in
  the middle band.

### sky_satellites
- **What:** the "sky layer": a stylised orbit stage above a cloud deck — 4 GPS-style satellites (solar wings,
  antenna face) in an arc, thin teal signal cones descending through the clouds. **Not to scale** (the real
  distances live in the 2D overlays).
- **Where:** cloud deck z ≈ 950 (2 km square, 2K cloud texture plane + 20 billboard clouds); satellites at
  z 2000–2600 around (100, 300). `ANC_sky_satellites` = central satellite (100, 300, 2300). Satellites modelled
  ×5 (≈ 25 m wing span).
- **Props:** satellite mesh (gold foil = procedural, panels 1K), signal cones (emission alpha 0.15), cloud deck.
- **Method:** reached by `crane` from `suburb_wide` + P (cloud portal: billboard clouds fill the frame 3 frames).
  `Z_SKY` is visible only in this window (otherwise the deck would overcast the town).
- **Light:** sun high (el 55°), HDRI sky; satellites bright; deck white.
- **Framing:** camera slightly below the satellites' level looking across; **blue sky gradient in the band**, cloud
  deck horizon at ~70 %. No black space (never a void).

### strip_mall_checkout
- **What:** a strip mall SW of the intersection (5 units, blank sign bands with abstract icons, a drive-thru at
  the south end); inside unit 3, a checkout lane: counter, bi-optic scanner, payment terminal, shopper's hand with a
  card. Hosts `macro_card_*`, `macro_terminal`, `macro_scanner`, `macro_barcode`.
- **Where:** building x −130…−40, y −70…−50 (storefront faces north to the parking lot y −10…−50). Checkout counter
  at (−88, −55, 0.95). `ANC_strip_mall_checkout` = terminal top (−88.4, −54.6, 1.10).
- **Props:** storefront glass + automatic doors (camera flies in through them, no cut needed), shelves (instanced,
  abstract packages, no brands), counter, conveyor belt, card + hand, terminal, scanner, a gum pack.
- **Method:** exterior→interior by `travel` through the doors; W2 dives by N + R.
- **Light:** interior bright: ceiling emission panels + 2 area lights (5000 K), windows show the sunny lot.
- **Framing:** over-the-shoulder at counter height; band over the **plain ceiling/upper shelf wall (soft)**;
  card/terminal at 45–65 %.

### suburb_wide
- **What:** the establishing/aerial view of Hometown USA: suburb grid, the hero house, cell tower, water tower on
  the hill, downtown in the distance.
- **Where:** `ANC_suburb_wide` = (230, 230, 0); `CAM_suburb_wide` ≈ (480, −40, 120), 35 mm, looking NW.
- **Props:** everything in `Z_SUBURB` + `Z_FAR_LOD` (instanced houses/trees/cars); a school bus moving on Oak Ln.
- **Method:** wide hold (drift/orbit), start/finish of sky cranes.
- **Light:** daylight, sun az 210° for long soft shadows.
- **Framing:** horizon at ~36–40 % from the top (below the band) → **sky fills the band**, town below; the water
  tower top stays below the 32 % line.

---

## 3. W3 — Cut-away house (12 stops; one lot of W1)

Two-storey US suburban house with an attached garage, on the north side of Maple St. **House local origin H0 =
(194, 152, 0)** = SW corner of the main volume; main volume 12 m (x) × 10 m (y); garage x 12–18, y 0–7.
Levels: basement floor −2.0, first floor +0.6, second floor +3.5, eaves +6.4, ridge +9.0.
Rooms (local x, y): living room 0–6.5 × 0–5.5 (front-left) · kitchen 0–6.5 × 5.5–10 (rear-left) · hall/stairs
6.5–9 × 3–7 · basement under the whole volume (furnace + A-coil under the kitchen).
Exterior: lap siding (1K), shingles (1K), white trim, front porch, lawn, driveway with a pickup, mailbox at the curb.
Cut-away: S1 peel of the south wall + front roof plane (for living room), north wall + rear roof (kitchen), west
wall lower strip (basement/lines). Interior: furniture low-poly, warm-neutral palette, bright.
Interior light (all W3 rooms): sun through windows + 2–3 ceiling area lights (5000 K, 30–60 W each) + the open
cut side lets daylight in; basement gets a large overhead softbox (it must look like a museum model, not a dark
cellar). Zone `Z_HOUSE_INT` / `Z_HOUSE_BASEMENT` visible only within ~25 m of the house.

### house_exterior
- **What:** the hero house from the street: porch, garage, driveway pickup, mailbox, lawn tree.
- **Where:** `ANC_house_exterior` = front façade centre (200, 152, 3.0); `CAM_house_exterior` ≈ (206, 118, 6).
- **Props:** as above; utility pole + can (`pole_transformer`) at the left; condenser visible at the west side.
- **Method:** S1 peel starts here when the next move goes inside.
- **Light:** daylight, sun lighting the façade (az 210° = from the SSW).
- **Framing:** house fills 40–75 %, **roof ridge + sky in the band** (ridge at ~33 %).

### living_room_router
- **What:** Wi-Fi router (generic, blinking LEDs) on a shelf in the living room; Spark/rings radiate from it
  through the rooms.
- **Where:** local (6.0, 4.8, 0.85 above floor) → `ANC_living_room_router` = (200.0, 156.8, 1.45).
- **Props:** router (2 antennas), shelf, plant, couch, phone on the couch (A4 end).
- **Method:** S1 (south wall + front roof peel), N room scale. Wi-Fi = translucent expanding teal rings (3D).
- **Light:** interior preset; LEDs emission 4.
- **Framing:** router at 50 % height, band over the **plain painted wall/ceiling**; avoid window frames in band.

### living_room_tv
- **What:** wall-mounted TV on the living room's north wall, couch facing it; IR sensor bump on the bezel.
- **Where:** local (3.2, 5.45, 1.3 above floor) → `ANC_living_room_tv` = (197.2, 157.45, 1.9).
- **Props:** TV (screen = soft abstract sports-field colours, no logos/score text), remote on the couch, media
  console.
- **Method:** N; IR pulses = small dim-red dots travelling (and "invisible" until shown in a phone camera insert).
- **Light:** interior preset; screen emission 1.5.
- **Framing:** TV in 35–60 %, band over the **wall above the TV** (plain).

### kitchen_microwave
- **What:** over-the-range microwave on the kitchen's north wall above the stove; door with the mesh window.
- **Where:** local (5.2, 9.65, 1.45 above floor) → `ANC_kitchen_microwave` = (199.2, 161.65, 2.05).
- **Props:** microwave (casing peelable S1: magnetron, waveguide, turntable), a bowl of soup, cabinets, range.
- **Method:** S1 casing peel (show the magnetron + wave pattern as an amber standing-wave ribbon — graphic only, no
  repair detail); N into `macro_microwave_mesh`.
- **Light:** interior preset; microwave cavity light emission when "on".
- **Framing:** microwave at 40–60 %, band over **upper cabinets (plain doors)**.

### macro_microwave_mesh (W3, nested macro)
- **What:** the door window up close: outer glass, the perforated metal mesh (holes ≈ 1 mm), inner glass; amber
  wave ribbon (≈ 12 cm wavelength) bouncing back from the mesh while white light rays pass through.
- **Where:** inside the door at `ANC_macro_microwave_mesh` = (199.2, 161.30, 2.05) (door plane). Mesh patch
  modelled 60 × 40 mm at real scale (hole array = instanced cylinders or alpha texture 1K for the far part).
- **Props:** glass layers (thin, low roughness), mesh sheet, soup bowl soft in the background.
- **Method:** N + R (rebase to this anchor), `snap` in from `kitchen_microwave`; lens 50 mm macro.
- **Light:** light-linked lightbox above + soft rim from inside the cavity (warm).
- **Framing:** mesh plane 30° to camera; band over the **out-of-focus glass/upper door** (smooth); waves in the
  middle band.

### ac_indoor_coil
- **What:** basement furnace with the AC evaporator A-coil cabinet on top (cut-away), condensate drain line.
- **Where:** local (2.0, 7.0, basement) → `ANC_ac_indoor_coil` = (196.0, 159.0, −0.6).
- **Props:** furnace (S1 front panel), A-coil (copper/aluminium fins = normal-mapped plane), drain pan + PVC
  drain, supply plenum + ducts, water heater nearby.
- **Method:** S1 coil cabinet peel; Spark turns teal → amber as heat is picked up (C1), or stays ice for "cold air".
  Water droplets on the coil (instanced small spheres) for the condensate twist.
- **Light:** basement softbox, bright neutral.
- **Framing:** coil at 45–60 %, band over the **plain basement ceiling/duct (smooth galvanized)**.

### ac_lines_wall
- **What:** the refrigerant line set leaving through the west wall: big insulated suction line + small liquid
  line, through the rim joist (wall slice) to the outside.
- **Where:** local (0, 7.5, rim at +0.4) → `ANC_ac_lines_wall` = (194.0, 159.5, 0.4).
- **Props:** wall S2 slice (siding, sheathing, insulation, framing), line set (black foam + copper), sealant.
- **Method:** S2 wall slice (lid = siding patch slides up); Spark travels along the suction line.
- **Light:** daylight from outside + basement softbox spill.
- **Framing:** camera outside at 0.8 m looking into the wall cut; band over the **siding above (plain)**.

### ac_condenser
- **What:** central-AC outdoor condenser on a pad on the west side yard: top fan, coil grille, service panel.
- **Where:** local (−1.4, 7.5) → `ANC_ac_condenser` = (192.6, 159.5, 0.95) (fan top).
- **Props:** condenser (grille = alpha 1K, fan blades animated), pad, line set, disconnect box, shrubs.
- **Method:** S1 top grille peel; heat leaves as amber shimmer ribbons rising from the fan (graphic).
- **Light:** daylight.
- **Framing:** 3/4 high angle; band over the **house siding (plain) or sky** — not the lawn edge with fine grass.

### thermostat
- **What:** wall thermostat in the hall (generic, round or square, a soft-glowing temperature ring, **no digits**
  in 3D — temperatures are 2D overlays).
- **Where:** local (6.55, 5.0, 1.5 above floor) → `ANC_thermostat` = (200.55, 157.0, 2.1).
- **Props:** thermostat, wall, hall table, stairs edge, low-voltage wire in a mini wall slice (optional).
- **Method:** N (snap to close-up); click = ring flashes teal.
- **Light:** interior preset.
- **Framing:** thermostat at 45–55 %, band over the **plain painted wall**.

### faucet_kitchen
- **What:** kitchen sink faucet under the window, water running.
- **Where:** local (3.0, 9.6, faucet tip 1.15 above floor) → `ANC_faucet_kitchen` = (197.0, 161.6, 1.75).
- **Props:** faucet (chrome), sink, countertop, window (back yard visible, bright), dish rack.
- **Method:** N; water stream = simple glass-shader tube + small noise displacement (no fluid sim).
- **Light:** window daylight + interior preset; chrome reflects the bright window.
- **Framing:** faucet at 40–60 %, band over the **window's bright blurred back yard/sky** or upper wall.

### wall_pipes
- **What:** the supply pipes in the kitchen's north wall + down to the basement: hot/cold PEX lines (red/blue),
  shutoff valves, main line from the street.
- **Where:** wall cavity local x 2.6–3.4, y 9.85–10 → `ANC_wall_pipes` = (197.0, 161.95, 1.0); the pipes continue
  down to the basement and south toward the street service line.
- **Props:** S2 wall slice (drywall, studs, insulation), PEX lines, valves, the basement main + meter.
- **Method:** S2 (camera in the back yard looking at the cut north wall, or from the kitchen side) then `section`
  down along the pipe to the basement.
- **Light:** interior preset + outside daylight.
- **Framing:** band over the **drywall/upper wall or siding (plain)**; pipes in the middle band.

### smart_meter
- **What:** electric smart meter on the house's west wall (glass dome, generic body, **no display digits in 3D**),
  service drop above it, condenser nearby.
- **Where:** local (0, 3.0, 1.5) → `ANC_smart_meter` = (194.0, 155.0, 1.5).
- **Props:** meter + socket box, service mast + drop to `pole_transformer`, conduit down.
- **Method:** N (snap); "data to the utility" = Spark + small rings leaving upward (radio) — keep soft (C4).
- **Light:** daylight; glass dome with subtle reflection.
- **Framing:** meter at 45–55 %, band over the **siding above (plain)**.

---

## 4. W2 — Macro kit (7 stops, nested inside W1 objects)

All W2 sets use **N (real scale inside the object) + R (rebase)**. Each set is a collection `Z_MACRO_*` parented to
its host object, hidden unless the camera is within 2 m of the host. Detail is mostly procedural (PCB solder mask,
gold, copper) to save VRAM; 1K maps max. Lighting: per-set light-linked "lightbox" (large soft area light above +
a smaller key at 45° + subtle teal rim), so the interior is **bright like a product cut-away**. Clip planes per
1.1. Lens 35–50 mm. Labels via 2D overlays only.

### macro_phone_board
- **What:** inside the phone (host: `hand_phone`): back glass peeled (S1), RF shield cans peeled, main board with
  the processor, memory, modem, battery beside it.
- **Where:** `ANC_macro_phone_board` = processor centre ≈ phone centre + (0, +20 mm, −2 mm) in phone local space.
  Board 70 × 40 mm, components 1–12 mm.
- **Props:** PCB (dark-green/charcoal solder mask with procedural traces), chips (matte black), capacitors
  (instanced), flex connectors, battery (silver pouch, no text).
- **Method:** `snap` from `hand_phone` (back glass + shield peel 0.4 s); R rebase on the snap.
- **Light:** light-linked lightbox (large soft area above the board + 45° key) since the closed phone has no daylight; the peeled back glass lets a little sun in; subtle teal rim on chip edges.
- **Framing:** low glancing angle over the board; band over the **smooth battery surface / soft-focus board edge**.

### macro_phone_antenna
- **What:** the antenna parts near the phone's top edge: segmented metal frame (antenna gaps), a small mmWave
  antenna module (patch array) on the side; signal leaves as teal rings.
- **Where:** `ANC_macro_phone_antenna` = top-edge module ≈ phone centre + (30 mm, +65 mm, 0).
- **Props:** frame segments with plastic gap lines, module (4 square patches), coax pigtail.
- **Method:** N + R; reached from `macro_phone_board` by a short `travel` along the board (~40 mm).
- **Light:** lightbox + daylight spilling past the phone edge (the frame metal reflects the sky); teal rings emissive 3.
- **Framing:** module at 50 %, band over **out-of-focus frame metal / sky beyond the phone edge**.

### macro_card_chip
- **What:** the card's chip (host: card in the shopper's hand at `strip_mall_checkout`): gold contact plate peeled
  away (S1) to show the tiny die with bond wires; "one-time code" = a small teal pulse (graphic).
- **Where:** `ANC_macro_card_chip` = chip centre ≈ card local (−24 mm, +4 mm, 0.4 mm). Card 85.6 × 54 × 0.76 mm;
  contact plate 11 × 12 mm; die ≈ 3 × 3 mm.
- **Props:** PVC card body (plain colour, **no network logo, no numbers**), gold plate (6–8 pads), die, wires.
- **Method:** `snap`/`portal` (the gold plate fills the frame for 2 frames) + R.
- **Light:** lightbox from top-left so the gold pads read; small warm key for the bond wires; store ceiling light beyond.
- **Framing:** band over the **smooth card PVC** (out of focus).

### macro_card_coil
- **What:** the antenna coil inside the card's laminate: 3–5 copper turns around the card edge, linked to the chip;
  the terminal's field shown as translucent teal loops powering it (B1 "no battery").
- **Where:** `ANC_macro_card_coil` = a coil corner ≈ card local (+38 mm, −22 mm, 0.38 mm).
- **Props:** top laminate layer S1 peel (lifts 2 mm), copper wire (0.1 mm drawn at 3× for legibility — note in
  fact notes: "not to scale"), core layer.
- **Method:** N + R; `travel` along the coil to the chip.
- **Light:** lightbox + a soft teal glow from the terminal's field loops (emission 1.5, alpha 0.2).
- **Framing:** looking along the card surface; band over the **out-of-focus terminal/counter**.

### macro_terminal
- **What:** the payment terminal on the counter: tap area (reader coil under the screen), keypad, internal
  board with a secure (tamper-proof) element — generic, **no brand, no UI text** (screen = abstract tick icon).
- **Where:** `ANC_macro_terminal` = reader coil under the screen ≈ (−88.4, −54.6, 1.07). Terminal 80 × 170 ×
  50 mm.
- **Props:** case (S1 rear peel), reader coil (copper loop), board, keypad membrane, secure element (glows teal when
  the PIN/payment is processed — explains *why it is secure*, never how to attack it).
- **Method:** N + R; reached from the card by a 5 cm `travel` following the Spark.
- **Light:** lightbox inside the peeled case + store ceiling panels outside; secure element glow teal when active.
- **Framing:** band over the **counter top far side / soft store background**.

### macro_scanner
- **What:** the bi-optic checkout scanner built into the counter: glass window, mirrors inside, laser lines
  (red, graphic) or camera module; the scan converts bars to a number (number shown in 2D).
- **Where:** `ANC_macro_scanner` = scanner glass centre ≈ (−87.6, −54.8, 0.95). Scanner 400 × 300 mm.
- **Props:** top glass + vertical window, mirror wheel, laser diode, PCB, a gum pack sliding over it.
- **Method:** S1 counter/scanner top peel; N (cm scale, rebase optional).
- **Light:** store interior preset + light-linked soft fill under the glass; laser lines emissive red 4 (graphic).
- **Framing:** band over the **store's soft ceiling/back wall**; laser lines in the middle band.

### macro_barcode
- **What:** the barcode on the gum pack, close enough to skim along the bars; the red scan line crosses them.
  **No digits under the bars** (digits = 2D overlay if needed).
- **Where:** `ANC_macro_barcode` = barcode centre on the gum pack (on the scanner, ≈ (−87.6, −54.8, 0.98)).
  Barcode ≈ 37 × 26 mm, narrowest bar ≈ 0.33 mm.
- **Props:** paper label (PIL-generated bar pattern texture 2K, valid-looking but arbitrary), pack wrapper (plain).
- **Method:** N + R; `snap` from `macro_scanner`; camera skims at 3 mm height.
- **Light:** lightbox low and soft (avoid glare on the label); the red scan line is the brightest element.
- **Framing:** bars run vertically across the frame below 32 %; band over the **plain wrapper paper** above the
  label.

---

## 5. Asset list (all original or CC0; instanced; no brands/logos)

| group | items | method / notes |
|---|---|---|
| Houses | 6 suburban house types (2-storey, ranch, split-level, with/without porch/garage) × 5 siding colours | collection instances on lot points (GN or `object.instance_collection`); LOD1 box-roof proxy > 150 m |
| Downtown | 8 brick/stucco block types, blank awnings + abstract sign bands | instanced; window grids = facade texture (2K atlas) |
| Strip mall + big-box | strip mall (5 units, drive-thru lane + menu board blank), big-box store + parking lot | facade atlas 2K; parking stripes PIL |
| Trees | 3 deciduous + 2 conifer + shrubs + lawn grass patches | low-poly trunk + alpha leaf cards (1K); far trees = billboards in `Z_FAR_LOD` |
| Cars | sedan, SUV, **pickup**, minivan, school bus, delivery van | 6 meshes, one material with per-object colour (attribute); parked + a few animated along splines |
| Street furniture | **mast-arm signals** (3-light heads), ped signals, stop signs (no letters), cobra-head lights, fire hydrants, **curbside mailboxes**, utility poles + cross-arms + **can transformers**, manholes, handholes | instanced |
| Utilities | **monopole cell tower** + 3 sectors, cabinets, chain-link fence; lattice transmission tower; substation kit; conduit bank; water main + valves | low-poly + alpha |
| Landmarks | **water tower** (spheroid on pedestal, blank), data center, treatment plant, stadium (far LOD only), toll gantry (far, for D3 later) | — |
| W3 interior | furniture (couch, shelf, TV, console, table), kitchen (cabinets, range, microwave, sink/faucet, fridge), basement (furnace + A-coil, water heater, ducts), thermostat, router | low-poly, procedural wood/paint |
| W2 macro | phone (glass, frame, board, battery, shields), card (laminate, chip, coil), terminal, bi-optic scanner, gum pack + barcode label, microwave door mesh | procedural PBR + PIL textures |
| Spark | orb, trail curve, rings, cones | generated per episode |
| Ground | terrain (gentle hills, river banks), road network meshes, strata textures for slices | PIL road markings (reuse the v2 approach in `pipeline/v2_textures.py` by import, no edits) |

## 6. VRAM / texture budget (RTX 3050, ~4 GB; PLAN 7b)

- **Target peak ≤ 3.0 GB** (chief, 25 Nov 2026; hard ceiling 3.2 GB; leave ~1 GB for OptiX/denoiser/driver). Budget: textures ≤ 1.0 GB, geometry/BVH ≤
  1.2 GB, render buffers + denoiser ≈ 0.6 GB.
- **Textures:** ≤ 2K for hero/near (≤ 30 maps), 1K for mid (≤ 100), 512 for far/props; pack AO/rough/metal into one
  ORM map; HDRI 2K only; facade atlases instead of per-building maps; macro sets mostly procedural. 8-bit maps
  (no 16/32-bit except the HDRI). PIL textures generated at the needed size, not larger.
- **Geometry:** instance everything repeated (houses, trees, cars, poles, racks, capacitors); no subdivision
  modifiers at render (apply low levels at build); grass = alpha cards, never particles hair.
- **Culling:** (a) every frame-range job (≤ 150 frames) computes the zones its camera sees from the timeline and
  **deletes** all other zones before rendering; (b) inside a job, zone `hide_render` is keyed per frame.
  `Z_FAR_LOD` always on. Macro zones only within 2 m of the host; house interior within 25 m; sky only in its window.
- One Blender GPU process at a time; CPU does overlays/assembly in parallel. If Cycles falls back to CPU = fail →
  simplify (PLAN 7b benchmark gate: ≤ ~1.5 s/frame at 1080×1920).

## 7. Build order (Opus builder, after the Windows port + shared one-shot renderer core)

1. **Scaffold** `page3/blender/world_hometown.py`: units, `WORLD_ROOT`, zones, daylight, ground + road network
   (Main, Elm, Maple, Oak, Birch), **all 37 `ANC_*` / `CAM_*` empties** at the coordinates above with grey proxy
   boxes. Render **one still per stop at 0.25 scale** (37 stills, low samples) → contact sheet with the 22–31 %
   band drawn → planner checks framing. *(Milestone M0 — blockout.)*
2. Hero block: hero house exterior + S1 peel panels, Maple St slice (S2 water + fiber), pole transformer, cell tower
   + base, the person + phone; Spark (orb, trail, rings); camera library (travel, snap, section, crane, drift,
   orbit, backout) + 2D motion-blur export.
3. **Milestone M1 — FIRST PREVIEW (= the PLAN 7b benchmark clip), 10 s / 300 frames at 1080×1920:**
   `house_exterior` (drift 2 s) → `living_room_router` (snap + peel, 2 s hold) → `street_slice_fiber` (section,
   Spark leaves the house under the lawn to the street, 2 s) → `cell_tower` (crane, 1.5 s) → `backout` (2.0 s, the
   library minimum) to frame 1. Report s/frame, peak VRAM, GPU temp, and a 1-fps QC sheet. Irfan approves the look here.
4. Rest of W3: kitchen (faucet, microwave), hall thermostat, basement coil, wall slices, condenser, smart meter.
5. Rest of W1: intersection + loop slice + cabinet, strip mall + checkout, data center + server room, substation +
   power lines, water tower + treatment plant, suburb wide, sky layer + cloud portal, far LOD ring.
6. W2 nested sets + rebase (R) + clip-plane automation: phone board/antenna → card chip/coil → terminal → scanner →
   barcode → microwave mesh. Test each with a 3 s snap-in/back-out clip.
7. Episode glue: read `episode.json` `oneshot` (stops/moves/spark per beat) + `timings.json` → camera keys, Spark
   path, slice/peel timings, zone culling, whip windows (for 2D blur, whoosh SFX and `qc_oneshot`).
8. Pilot episode from `page3/scripts/` → full QC (qc_v2 + qc_full + every 1-fps sheet) → Irfan approves.

## 7b. Session 2 coordinate notes (implemented in `page3/blender/hometown_usa_plan.py`, the single source of truth)

The module names changed from section 0's plan: the world is `page3/blender/hometown_usa.py` (`build(ctx, state)` +
`apply_events`) with the bpy-free half `hometown_usa_plan.py` (anchors, CAM spots, zones, slices, peels, timeline),
registered with Page 2's shared renderer by file convention (world id `hometown_usa`). Changes against the text above:
- **Every stop has a CAM_ position**, including the W3 rooms and all macro stops (the spec only gave some). Lenses:
  35 mm default, 24 mm slices/aisle, 28 mm wide exteriors, 50 mm card/barcode/microwave mesh.
- **Nested hosts are rigid frames** (origin + rotation): phone at (201.45, 148.70, 1.32) tilted 60° about X (screen
  faces up-south towards the person); card held flat 5 cm above the terminal, centre (−88.40, −54.56, 1.150);
  terminal tilted 20° towards the shopper; gum pack centre (−87.60, −54.80, 0.965). Macro anchors are computed in host
  space (e.g. `macro_terminal` = terminal local (0, 20, 18) mm → (−88.400, −54.575, 1.085)).
- **Phone dive from the screen side:** the camera arrives over the shoulder, so the *display module* peels sideways
  (not the back glass) to reveal the board; the shield cans lift with it.
- **Microwave:** body y 161.43–161.85 (0.42 m deep), so the door mesh plane is **y = 161.415** (was 161.30, which
  would sit 13 cm in front of the door). `ANC_macro_microwave_mesh` = (199.2, 161.415, 2.05).
- **S2 slices are open towards the camera:** each Maple St half-slice hole is x 192–214 / 214–236, **y 131–144** (the
  south sidewalk + verge strip y 131–136 is part of the hole and its lid), so the slice cameras at y 133, 0.3 m up,
  look into the cut at only ~12° down with houses + sky in the caption band. Lids = the surfaces over the hole (lawn,
  asphalt, concrete) and slide ±23 m along the street (loop: 3.6 m east; handhole 1 m south; wall slices slide up).
- Wall slices: west wall y 158.6–160.4, z −0.2…1.0 (line set); north wall x 196.3–197.7, z 0…1.5 (PEX lines).
- **Peels** (S1): south wall + front roof (living room / TV / thermostat), north wall + rear roof (kitchen), floor hatch
  + coil panel (basement), DC roof SE quarter, mall roof (camera inside the mall), tank front half, filter-building
  wall, plus small lids (display, card laminate + gold plate, terminal top, scanner glass, microwave casing, condenser
  grille, signal-cabinet door, tower-cabinet door). Walls **sink 7.2 m into the ground**, roofs lift off.
- **Holds are scaled to the subject** (page3 workaround in `tune_holds`): drift = 1 %/s of the subject distance,
  orbit = 1.5°/s, macro drift → orbit. (Beats are 8–23 s long; the spec's 4 %/s drift would carry the subject out of
  frame.)
- **Sun:** `S.daylight(sun_az=-30)`; `sun_az` is a lamp Z rotation, compass bearing = 180° − sun_az = 210° (SSW).
- Culling: exterior districts within 500–600 m are built, within 150 m when the camera is inside a building or at
  macro distance; zone sets are computed per **beat** (changes land inside the next beat's move window); the rest
  become grey proxies in `Z_FAR_LOD`. Clip planes per frame = 1 % of the subject distance (0.2 mm … 0.1 m), ratio 1e5.

## 7c. Session 3: variant views (holds <= 9 s) and portal interiors

Irfan's rule: no camera hold longer than ~9 s (fail above 10 s). Every stop has two extra views on the same
object/area: `<stop>__detail` (a push-in to a close detail) and `<stop>__alt` (another angle or part). They are
defined in `hometown_usa_plan.VARIANT_SPEC` as offsets from the stop's anchor/camera, and get `ANC_`/`CAM_` empties
like the stops. `make_episode.py` writes page2-native `shot.camera` keys: when a beat's estimated hold (170 wpm)
would run over 9 s, it splits the beat at sentence starts (or at words) into parts of about 8 s or less, cycling
main -> detail -> alt with snaps (0.3 s) or short travels (0.8-1.2 s). The last beat holds on the twist stop's views,
then cues the backout so it ends about 0.6 s before the reel ends.

| stop | `__detail` | `__alt` |
|---|---|---|
| `hand_phone` | app tiles on the screen | hand, thumb and the phone's lower edge |
| `cell_tower` | one sector: 3 antenna panels + radio boxes | monopole mid-shaft and coax trunk |
| `tower_base` | open cabinet: racks and LEDs | fiber handhole mini-slice |
| `street_slice_fiber` | sliced duct: fiber strands, glowing ends | handhole where the Birch St conduit enters |
| `data_center` | rooftop chillers | generator yard + fence |
| `edge_server_room` | rack front LEDs | overhead yellow fiber tray |
| `substation` | transformer bushings + radiator fins | bus + lines leaving east |
| `power_lines` | insulator string on a lattice tower | lattice tower legs |
| `pole_transformer` | can transformer + fuse cutout | service drop towards the house |
| `water_tower` | balcony rail + ladder | riser in the cut-away pedestal |
| `water_main_slice` | saddle + corporation stop | main, gas line and service line together |
| `treatment_plant` | clarifier bridge + water | filter bed cut (sand/gravel) |
| `intersection` | NB signal heads | hero pickup at the stop line |
| `road_loop_slice` | loop wire corner in the saw-cut | lead-in to the curb pull box |
| `signal_cabinet` | detector cards + LEDs | mast-arm pole + heads above the corner |
| `sky_satellites` | solar wing of the central satellite | the outer satellites of the arc |
| `strip_mall_checkout` | terminal screen + card | scanner + conveyor |
| `suburb_wide` | hero house on Maple St | the town from the east (other angle) |
| `macro_phone_board` | processor die close-up | battery pouch |
| `macro_phone_antenna` | mmWave patch array | antenna gap in the metal frame |
| `macro_card_chip` | bond wires on the die | coil link into the chip |
| `macro_card_coil` | copper turns in the laminate | terminal field loops under the card |
| `macro_terminal` | secure element (glows teal) | keypad membrane |
| `macro_scanner` | laser lines on the glass | vertical window + mirror wheel |
| `macro_barcode` | bars at the label edge | red scan line over the wrapper |
| `house_exterior` | porch + front door | garage + driveway pickup |
| `living_room_router` | status LEDs | the two antennas |
| `living_room_tv` | bezel corner with the IR sensor | TV from the side, couch in front |
| `kitchen_microwave` | door + handle | magnetron under the peeled casing |
| `macro_microwave_mesh` | the hole grid | amber wave ribbon bouncing off the mesh |
| `ac_indoor_coil` | A-coil fins + condensate droplets | drain line + water heater |
| `ac_lines_wall` | line set in the cut (foam + copper) | line set running to the condenser |
| `ac_condenser` | top fan through the grille | heat ribbons rising |
| `thermostat` | glowing teal ring | hall wall + stairs edge |
| `faucet_kitchen` | the water stream | sink + window |
| `wall_pipes` | shutoff valves | pipes running down to the basement |
| `smart_meter` | glass dome | service mast + drop |

**Portal interiors.** A portal must land in a set. Portals in the 10 scripts land as follows:
- `macro_card_chip` (ep 03) and `macro_scanner` (ep 04) land in their nested real-scale macro sets (`Z_MACRO_CARD`,
  `Z_MACRO_SCANNER`).
- `kitchen_microwave` (ep 06) is a portal onto the stop the camera is already at. It dives into the **enlarged
  microwave cavity**, built 20x (10 x 7 x 5.6 m) as zone `Z_MW_INSIDE`, centred on (0, 0, -300). The room is closed
  and bright, with metal walls, a perforated door wall glowing warm from the kitchen, a turntable with a bowl of
  soup, the magnetron with its wave-guide and mica cover, the cavity lamp, and amber standing-wave ribbons.
  Its three views are `kitchen_microwave__inside`, `__inside_detail` (magnetron/wave-guide) and `__inside_alt`
  (turntable).
- Any move out of an `__inside` view is turned into a portal (never a fly-through). The only exception is the
  backout, which page2 plans.

## 8. Stop ID index (fixed vocabulary — must match `page3/tools/make_episode.py`)

W1: hand_phone, cell_tower, tower_base, street_slice_fiber, data_center, edge_server_room, substation, power_lines,
pole_transformer, water_tower, water_main_slice, treatment_plant, intersection, road_loop_slice, signal_cabinet,
sky_satellites, strip_mall_checkout, suburb_wide
W2: macro_phone_board, macro_phone_antenna, macro_card_chip, macro_card_coil, macro_terminal, macro_scanner,
macro_barcode
W3: house_exterior, living_room_router, living_room_tv, kitchen_microwave, macro_microwave_mesh, ac_indoor_coil,
ac_lines_wall, ac_condenser, thermostat, faucet_kitchen, wall_pipes, smart_meter
Moves: travel, snap, section, portal, crane, orbit, drift, backout. Spark: teal, amber, ice, off.

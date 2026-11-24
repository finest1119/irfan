# Self-Made Engineer — Proposal v1 (character, world, Season 1 arc, one-shot style)

Written 24 Nov 2026 by the Page 2 session. Status: **APPROVED by Irfan 24 Nov 2026 (all section-6 recommendations accepted) + US-audience update (section 0).**
Nothing is built yet. Builds on `irfan/PLAN-page2-self-made-engineer.md` (decisions in its section 0).
All designs are original — nothing copied from the reference reels (no dog, no same chips, no same house).

---

## 0. Audience: AMERICA FIRST (Irfan, 24 Nov 2026 — relayed by the chief session)
This Page is for monetization with **US viewers as the main audience**. Everything must feel American:
- **Setting:** American suburban-edge house + yard, US tools, US outlets (NEMA 3-prong), curbside mailbox,
  pickup truck in the driveway, wooden privacy fence, garage, lawn, neighbors down the street.
- **Units:** US first — °F, feet/inches, gallons, mph, lb, BTU, kWh, dollars; metric in brackets only when useful.
  HUD gauges show US units.
- **Problems Americans relate to:** power outages after storms, high electric/heating/AC bills, heat waves,
  drought + water bills, wildfire season, snowstorms. Every hook links to one of these.
- **Language & humor:** US English spelling (color, neighbor, meter → foot…), American dad humor
  (hardware-store runs, "honey, I'm fixing it", HOA jokes, the neighbor peeking over the fence) — no brand names.
- **Posting times:** tuned to US time zones (section 5.1).
- **No locally-specific references outside the US** (no UK/Europe/Asia place names, money, or customs on screen).
  Exception (Irfan, 24 Nov 2026): an occasional **Remote-Work trip abroad** arc is allowed, shown as an American
  abroad, still in US units (section 3.3).
  Foreign real-world examples are only used for fact-checking, never named on screen.

---

## 0b. Page name — **Self-Made Engineer (FINAL, Irfan 24 Nov 2026)**
The character "Bolts" is the host of the Page; the name options list from earlier is dropped.

## 1. Main character

### 1.1 Name & nickname
**Walt "BOLTS" Mercer** — viewers call him **Bolts** ("Bolts did it again 😂", "Bolts build a ___ next!").
- Short, one syllable, engineer-sounding, easy to type in comments; sounds like a real American handyman.
- On-screen: chip "BOLTS · BUILD #4" (top-left, small). Caption sign-off in post text: "— Bolts".

### 1.2 Look (same in EVERY reel, whatever the outfit)
| Item | Design |
|---|---|
| Age / build | ~48, stocky, broad shoulders, slight belly, strong forearms — the American "dad who can fix anything" |
| Face | square jaw, short **salt-and-pepper beard**, friendly crow's-feet eyes, thick eyebrows, sunburned cheeks |
| Hair | short gray-brown, a bit messy at the back (usually under a ball cap/helmet anyway) |
| **Signature 1** | **round safety glasses pushed up on his forehead** — always, even with the welding mask up |
| **Signature 2** | **red bandana** (brand red #E63946) tied around his neck |
| **Signature 3** | a **carpenter's pencil behind his right ear** + a yellow tape measure (feet/inches) clipped on the belt |
| Body language | thumbs-up when a build works, scratches beard at a SNAG, hands on hips at the reveal |

The three signatures stay on through every outfit, so he is recognizable in a thumbnail at 1 inch wide.
Colors: navy (#0B1F3A) work pants in most outfits + the red bandana = Page branding on the character.
His ride: an **old red pickup truck** (generic, no badge) — always parked in the driveway; hauls materials in.

### 1.3 Personality & voice
- Personality: calm, stubborn, a bit mad-scientist, classic American DIY dad; never gives up; honest when an idea
  is weaker than he hoped (that honesty is a comment driver — see Build #4). Running jokes: the goose (1.5),
  the neighbor who keeps peeking over the fence, "one more trip to the hardware store".
- **Narration is third-person by a fixed host narrator** (no lip-sync needed → much cheaper/safer to render):
  "Bolts was tired of his power going out every storm. So he did something crazy…". Bolts never speaks; he reacts
  with body language.
- **Voice: one fixed host voice, Fenrir** (Gemini "excitable" — punchy, hype), prompted for a **natural
  American accent**. Backup if too shouty on long reels: **Sadaltager**. Never rotates on this Page.
  Style: fast, warm, a little dad humor, plain words, real US numbers ("about 400 watts — enough to keep the
  fridge and lights on when the grid goes down").

### 1.4 Outfit library (`page2/character.json` → `"outfit": "<id>"`)
| id | Used for | Outfit |
|---|---|---|
| `workshop` (default) | general builds, reveals, episode intros | navy work pants, gray henley sleeves rolled, leather tool belt, brown work boots, navy ball cap |
| `scientist` | chemistry/biology builds (biogas, tests, measurements) | white lab coat open over the henley, clipboard, red pen in pocket, nitrile gloves |
| `electrician` | wiring, batteries, turbine electrics | navy coveralls with reflective strip, yellow insulated gloves, multimeter on belt, white hard hat |
| `welder` | metal work, towers, heater barrels | brown leather apron + sleeves, auto-darkening helmet flipped up (glasses still on forehead), gauntlets |
| `plumber` | pipes, pumps, water | blue bib overalls, red pipe wrench, knee pads, ball cap backwards |
| `farmer` | garden, greenhouse, animals | straw cowboy-style hat, red-navy flannel shirt, rubber boots, work gloves |
| `mechanic` | gears, cables, carts, engines | gray coveralls with grease marks, red shop rag in back pocket, ratchet |
| `digger` | trenches, excavation, concrete | hi-vis orange vest, yellow hard hat, earmuffs around neck, dusty jeans |
| `roofer` | anything on a roof / tower | fall-arrest harness + lanyard, hard hat with chin strap, knee pads |
| `winter` | cold-weather episodes | tan duck-canvas work jacket (no logo), red beanie, insulated gloves (bandana visible at the collar) |

Outfit chip at start of each reel (2D): e.g. "TODAY: ELECTRICIAN BOLTS" — makes the outfit a mini-reveal.

### 1.5 Sidekick — Torque the goose (approved by Irfan, 24 Nov 2026)
**Torque** — a white farm goose who lives on the property.
- Why a goose (not a dog): the reference channel has a dog → a goose is original, funnier, and a proven comment
  magnet ("the goose is the real engineer", "protect Torque at all costs").
- Role: 1–2 short gags per reel (steals a washer, honks at the ram pump, chases the peeking neighbor, sits on the
  warm heater bench). Never in danger, never hurt. Cheap to animate (waddle + head bob + wing flap loop).
- Running payoff: in Build #10 Torque gets the first ride on the water railway → huge comment bait.

---

## 2. The property / world — "Mercer Hollow"

An **American suburban-edge home on about 4–5 acres** at the end of a cul-de-sac on the edge of a small US town
(think Tennessee/Ohio-valley/Pacific-Northwest foothills — no state named on screen). From the street it reads as
classic American suburb; behind it the lot drops to a creek and climbs a wooded ridge — which gives the real
physics (head for water, wind on the ridge). Bright v2 daytime look, same world every reel.

### 2.1 Map (≈ 400 ft × 520 ft, creek runs north→south, ridge on the east)
```
                N  (upstream)
   ridge (E) ↑ +80 ft  [R] hilltop pad (Build #1 turbine, Build #3 tank)
        slope (meadow, old split-rail fence)
   [C] creek  ~26 ft fall over 200 ft, small waterfall + pool      [W] woods (oak/maple/pine)
   [H] house: 2-story, white lap siding, gray shingle roof,        [G] raised-bed vegetable garden
       covered front porch, attached 2-car garage, concrete        [M] curbside mailbox, street with
       driveway with the red pickup, front lawn, porch light           sidewalk + 3–4 neighbor houses
   [S] detached workshop/barn (roll-up door, workbench, pegboard)  [P] small pond (south, downstream)
       + lean-to battery shed                                      [T] goose house (Torque)
   [Y] back yard: wooden privacy fence, deck with grill, big oak tree with tire swing, picnic table
   far away: rolling wooded hills, water tower of the town, power lines on wooden poles along the road
```
- **Creek (C)** gives real head for hydro (Build #2) and drive water for the ram pump (Build #3).
- **Ridge (R)** gives wind (Build #1) and height for a water tank (Build #3) and the railway (Build #10).
- **Yard (Y) + garden (G)** = space for trench/greenhouse/digester (Builds #6–8).
- **Workshop (S)** = indoor set for small builds and the heater (Build #9); lean-to = battery bank (Build #1).
- **Street + neighbors** = the "nosy neighbor" gag and the "whole street lost power, Bolts didn't" payoff.
- US details to model: NEMA outlets on the shed/garage, curbside mailbox with flag, wooden utility poles,
  propane tank by the house (the thing he wants to stop paying for), A/C condenser unit, garden hose reel.

### 2.2 Continuity — `page2/world_state.json`
Each finished build is stored and placed in every later reel (with its idle animation). Sketch:
```json
{
  "world": "mercer_hollow", "version": 1,
  "zones": {"ridge": [40, 60, 25], "creek_top": [-20, 70, 9], "creek_bottom": [-25, 10, 1],
            "house": [0, 0, 0], "workshop": [25, -5, 0], "yard": [10, 20, 0], "garden": [-15, -15, 0]},
  "builds": [
    {"id": "wind_turbine", "day": 1, "zone": "ridge", "pos": [40, 62, 25], "rot": 0, "status": "posted",
     "idle": "rotor_spin", "night": "beacon_red", "depends_on": [], "posted": "2026-12-xx",
     "callback": "the windmill we built in Build #1"}
  ],
  "cables_pipes": [{"from": "wind_turbine", "to": "battery_shed", "kind": "buried_cable"}]
}
```
Each build has `"status": "approved" | "scheduled" | "posted"`; the loader places every **approved or later** build (so Build #2 can render before Build #1 is posted; a rejected episode is simply never approved); an episode may update an old build's state (e.g. Build #4 changes the
battery HUD); never remove a build (if one is retired, it stays as a visible "old attempt" — itself a callback).

---

## 3. Season 1 — "Off-Grid Hollow" (10 connected episodes)

Arc: Bolts decides to take Mercer Hollow off-grid with his own hands. **Power (1–4) → Comfort (5–6) → Food &
fuel (7–8) → Winter (9) → Grand finale (10).** The world's season moves with the arc so the weather stays
believable: **late summer (1–6) → autumn (7–8, first frost at the end of 8) → winter (9–10, snow).**
Each build uses or depends on earlier ones; each reel ends with a teaser for the next build + a viewer question.
Story beats inside every reel (own chip names, not the reference's): **MISSION → HOW IT WORKS → SNAG → HACK →
(SNAG → HACK) → IT WORKS** + 1–2 HUD gauges in US units (watts, gallons, °F, mph, battery %). One outfit per reel.

Numbers: textbook checks by the planning session + one batched Fable fact-check (section 3.0c, numbers already corrected in the table). **Each episode
still gets its own Fable fact-check at script time (2+ sources)** before render, per the SOP.

### 3.0 Episodes at a glance
| # | Title / hook | How it works (1 line, US units) | Outfit | Earlier builds shown + callback | "Crazy" moment (comment driver) | Safety note |
|---|---|---|---|---|---|---|
| 1 | **"Storm knocked out the power. So he built a wind turbine taller than his house"** | 3-blade ~1.5 kW turbine on a 50 ft tilt-up tower on the windy ridge; tail vane keeps it facing the wind; charges a battery bank in the lean-to shed. Honest number: 1.5 kW is the peak; small turbines average ~15 % of that → **~5 kWh/day** on a good windy site | electrician (with fall-arrest harness) | none — opens on the dark street after a storm; establishes house, creek, ridge, goose, neighbors | Raising the tower with a hand winch; first gust spins it; 40+ mph storm SNAG → the tail **furls** itself to survive; his porch light is the only one on the street | No climbing/electrical how-to; towers need county permits (and maybe HOA OK); batteries = licensed installer |
| 2 | **"The wind died… so he stole power from the creek"** | Micro-hydro: screened intake at the top of the 26 ft fall, pipe down the slope, small turbine at the bottom. ~160 gal/min × 26 ft × ~50 % ≈ ~400 W gross; after pipe/nozzle losses **~350 W, day and night** (~8 kWh/day — almost a third of a typical US home's daily use) | plumber | #1 turbine standing still on a dead-calm dusk, battery HUD low → hydro fills it | A tiny creek out-produces the big windmill because it never stops → "team wind vs team water" | State water rights/permits; fish screen; leave enough water in the creek |
| 3 | **"Drought + a crazy water bill → he made water flow UPHILL with zero electricity"** | Hydraulic **ram pump**: falling water slams a valve shut (water hammer) and pushes a small share of it far higher. ~8 gal/min with a 6.5 ft fall → ~¼–½ gal/min to a tank 65 ft up ≈ **~350–700 gal/day** (about 90 % of the drive water goes back to the creek) | plumber | Hydro pipe from #2 beside it; new tank sits next to the #1 turbine on the ridge | The "clack… clack" valve with no motor and water pouring into the hilltop tank; Torque honks at every clack | Water hammer bursts weak fittings — pressure-rated pipe, pros for big systems |
| 4 | **"He built a 1-TON gravity battery… then did the math"** | Spare wind power winches a 2,200 lb concrete block up a 33 ft steel frame; lowering it drives a generator. m·g·h ≈ **27 Wh** before losses, ~20 Wh usable (≈ 2 phone charges, about **half a cent** of grid power) | welder | #1 turbine powers the winch; battery shed HUD | Honest twist: huge block, tiny energy → why real gravity storage uses old mine shafts or dams. Bolts keeps the block "for later" (pays off in #10) | Suspended heavy loads — never stand under; illustration only |
| 5 | **"His gas bill was crazy, so he heats shower water with black pipe and the sun"** | Thermosiphon solar water heater: black pipe coil in a glass-covered box on the workshop roof, insulated tank higher up; hot water rises by itself, no pump. Sunny summer day with ~20–30 sq ft of collector: **up to** ~25–40 gal at 115–140 °F (far less in winter) | roofer | Fed by gravity from the #3 hilltop tank ("the water he pumped uphill now gives him shower pressure") | Steaming water from a garden hose on a cool morning; Bolts tests it with his hand and grins; backyard outdoor shower stall reveal | Scald risk → mixing valve; drain it before the first freeze |
| 6 | **"Heat wave + $400 A/C bill → he buried 200 ft of pipe to cool his house"** | Earth-tube cooling: pipes 6–10 ft underground where the soil stays ~50–60 °F all year; a small fan pulls outside air through them into the house. Honest number: ~2,000–2,500 BTU/h of cooling = **one room, not the whole house** | digger | Fan runs from the #1/#2 battery bank; trench crosses near the #3 pipe line | A giant zigzag trench across the back yard (whip over it), neighbor peeking over the fence; HUD: ~93 °F outside vs **low 70s °F** at the vent (keep soft: "around") | Trench collapse (shoring; **call 811 before you dig**); slope the pipe to drain condensation (mold); radon areas |
| 7 | **"He cooks dinner with gas made from garbage"** | Small **biogas digester** (~250–500 gal tank): bacteria digest kitchen scraps, yard waste and a neighbor's horse manure without oxygen → methane collects in a floating gas bag → **~30–90 min** of cooking a day (needs ~95 °F and daily feeding); leftover slurry = fertilizer. Kept warm by a loop from the #5 solar heater. Bonus: he unhooks the propane tank | scientist | #5 solar hot water keeps the bugs warm; trench dirt from #6 banks the tank | Blue flame on the grill burner fed from a "balloon of garbage gas"; Torque tries to add his own "fuel" (goose joke only) → "ewww / genius" comments | Methane flammable + H₂S toxic: outdoors, kit/pro systems, no step-by-step |
| 8 | **"A greenhouse dug INTO the ground to grow food through a Northern winter"** | **Walipini** (northern US version): pit ~5–6 ft deep with a **steep** sun-facing glazed wall + insulated roof; the surrounding earth takes the edge off frost. Honest twist: the classic design shades itself in a northern winter (noon sun only ~20° high in December at Northern US latitudes), so Bolts' HACK = steeper glass + insulation + a tiny backup heater. Claim only "way warmer than outside", never "never freezes" | farmer | #6 trench dirt reused for the berm; #7 slurry fertilizes the beds; watered from the #3 tank; vent fan on batteries | Ends on the **first frost**: white lawns down the street, green tomatoes inside, HUD inside vs outside °F | Drainage / water table; dig safety as #6 (call 811) |
| 9 | **"Heating bill hit $500. His answer: a heater that burns twigs"** | **Rocket mass heater**: an insulated J-shaped burn tunnel gives a very hot, clean fire; the hot gas snakes through a long clay bench (1–3 tons) that soaks up the heat and gives it back for hours | welder | Snow on the ground; workshop lit by #1/#2 power; #8 walipini glowing in the snow outside | Handful of twigs → bench glows on a thermal-camera HUD; Torque falls asleep on the warm bench | Carbon monoxide + fire → CO alarm, local building code, homeowner's insurance; no build dimensions |
| 10 | **SEASON FINALE: "He built a railway that runs on WATER"** | **Water-balance funicular** (the same trick a real cliff railway has used since 1890 — country not named on screen): both carts carry water tanks; the top car is filled from the #3 hilltop tank, the **bottom car dumps its water** → the top car is now heavier, rolls down and pulls the other up; brakes control speed. Hauls firewood and groceries up the ridge | mechanic | Everything: #3 tank water, #4 concrete block reused as the top pulley anchor, #1 turbine; final one-shot tour past all 10 builds in the snow at sunset, every house on the street dark except his | Torque's first ride up the hill; the whole off-grid property in one sweep; "Season 2: YOU choose" | Moving loads + brakes = pro engineering; illustration only |

### 3.0c Fable fact-check (24 Nov 2026, Fable 5.2 medium, batched; US conversions by the planning session)
- **WORKS:** #2 micro-hydro (~390 W), #4 gravity battery (as an honest debunk), #10 water funicular (real 1890 cliff railway, still water-powered — used for the fact-check only, not named on screen; animation fixed: motion starts when the bottom car empties).
- **WORKS WITH CAVEAT (numbers corrected above):** #1 wind (~5 kWh/day average, not 1.5 kW), #3 ram pump (DIY efficiency lower at 10:1 lift), #5 solar heater (summer figure, soft "up to"), #6 earth tube (one room; "low 70s °F" not 66 °F), #7 biogas (30–90 min, needs warmth), #9 rocket heater (no efficiency % on screen; code/insurance/CO).
- **MISLEADING as first written → reworked:** #8 walipini ("above freezing at 14 °F" dropped; the self-shading problem is now the SNAG of the episode).
- Weakest evidence: #5, #6, #9 → keep on-screen numbers soft; re-check with **US sources** (DOE/energy.gov, state extension services, EPA) at script time. Dollar figures in hooks ($400 A/C bill, $500 heating bill) are story framing — Fable checks they are plausible against EIA averages before use.
- Sources: energy.gov small-wind guide, NC State ram-pump extension, greenbuildingadvisor earth tubes, NJST biogas field test, ceresgs walipini, cliff railway operator site.

### 3.0b Teaser + viewer question per episode (draft; final wording by Fable at script time)
| # | Next-build teaser (last ~5 s) | Viewer question (last line + pinned comment) |
|---|---|---|
| 1 | "But what happens when the wind stops? Tomorrow he looks at the creek…" | "Would your HOA let you put this in YOUR yard?" |
| 2 | "Next: he makes water climb a hill… with no pump motor." | "Wind or water — which would you build first?" |
| 3 | "He's got spare power now. So he's going to lift a 1-ton block. Why? Next time." | "Did you know a pump could run on nothing but falling water?" |
| 4 | "Forget the math. Tomorrow that uphill water becomes a hot shower." | "Was the gravity battery worth it? Be honest." |
| 5 | "Heat wave's coming. His answer: a 200-foot trench." | "Would you shower in sun-heated hose water?" |
| 6 | "He's sick of paying for propane. His next fuel source… is the trash can." | "Guess the temperature at the vent — comment a number in °F." |
| 7 | "Frost is coming. He's going underground to save the garden." | "Would you eat a burger grilled on garbage gas?" |
| 8 | "Snow's here. Next: a heater that burns twigs." | "What would you grow in an underground greenhouse?" |
| 9 | "Season finale tomorrow: a railway… powered by water." | "What's YOUR winter heating bill? Would this beat it?" |
| 10 | "Season 2 starts with YOUR idea." | "What should Bolts build next? Best comment gets built." |

### 3.1 Script callbacks & teasers (examples, final text by Fable at script time)
- #2 open: "Remember the windmill from Build #1? Today there's no wind. Zero. So Bolts looked at the creek…"
- #5: "The water the ram pump pushed up the hill in Build #3? It's about to become a hot shower."
- #10 open: "Ten builds ago this was an ordinary backyard. Now look."
- Viewer question (last line + pinned comment): "Wind or water — which would YOU build first?" / "What should
  Bolts build as Build #11? Best comment gets built." → feeds Season 2 ("You asked for it" chip).

### 3.3 Beyond the yard — indoor builds + trip arcs (Irfan, 24 Nov 2026)
Irfan: builds don't have to happen only in the yard. They can also be **indoors**, in his **hometown**, on a
**vacation**, or while he's **working remotely abroad**. That keeps the Page fresh after Season 1 and gives
"where is Bolts going next?" comments.

**Indoor builds at Mercer Hollow** (same house, interior sets; slot them between yard builds or as a
"Rainy Week" / "Snowed-In Week" arc):
- Garage: ceiling pulley storage that lifts the whole kayak/bike rack with one rope · counterweighted garage
  workbench that folds into the wall.
- Basement: **spring-assisted stairs** · dehumidifier that runs off the #2 hydro power · gravity-fed water filter.
- Kitchen: **dumbwaiter** from the kitchen to the basement pantry · drain-water heat-recovery pipe for the shower.
- Attic: solar-chimney attic vent (hot air rises and pulls cool air through the house, no fan).
- Living room: hand-crank emergency radio + phone charger box for outages (callback to the #1 hook).

**Trip arcs** (3–5 builds per trip, new location pack, home builds called back: "back home the windmill's
still spinning"):
| Arc | Where (US-first) | Example builds | US pain / hook |
|---|---|---|---|
| **Hometown Week** | His dad's old ranch in Montana/Wyoming | windmill water pump restore · stock-tank solar heater · snow fence that makes its own snowdrift water supply | drought, brutal winters |
| **Grandma's Farm** | Midwest farmhouse (Iowa/Ohio) | storm cellar air vent · root cellar · tornado-proof tool shed anchors | tornado season |
| **Beach Vacation** | Gulf Coast rental (Florida/Texas) | solar still for drinking water · hurricane shutters that close on wind power · sand-battery cooler | hurricanes, heat |
| **Cabin Trip** | Colorado/Pacific Northwest cabin, no grid | thermoelectric stove charger · gravity zip line for firewood · wildfire ember sprinkler from a creek | wildfire season, off-grid |
| **Remote-Work Month** (abroad) | e.g. Iceland, Japan, Norway, Mexico — told through Bolts' American eyes ("Bolts took his laptop to…") | geothermal hot-spring cooker · earthquake-proof shelf · fog net | curiosity + travel; US viewers relate via the American abroad |

Rules for trips:
- **Continuity:** each location gets its own entry in `world_state.json` (`locations` map). Builds stay where
  they were built. If Bolts goes back, they're still there. Home builds keep running and get a quick callback.
- **One-shot:** the camera stays inside ONE location per reel (no cuts, no teleporting). Travel is shown at the
  start of the first trip reel as one continuous move: pickup pulls out of the driveway, whip along the road,
  then it settles on the new place. Interiors: the camera can whip in through a door or window.
- **Outfit:** new `travel` outfit (casual jacket + backpack, signatures on); local job outfits are reused.
- **US-first balance:** most trips are inside the US. Trips abroad are allowed (Irfan's own idea), but keep
  them occasional, use US units, and frame them as "an American engineer abroad". Never name real local
  businesses or people, and be respectful with local culture.
- **Production cost:** each new location is a new light world pack (≤ 3 GB VRAM). Build it once, reuse it for
  the whole arc. Interiors are cheap (small rooms), so they're good filler when render time is tight.

### 3.2 Season 2 seeds (from PLAN topic bank, for after viewer votes)
**US-problem builds first:** wildfire ember sprinkler system fed by the #3 hilltop tank · storm shelter / root cellar · hurricane-proof roll-down shutters (wind-powered) · snow-melting driveway from the #5 solar loop · backup well with rope pump for drought — then: pedal generator · solar tracker · rainwater + fog net · root cellar · ice house · windcatcher tower · trombe wall ·
automatic goose-house door · dumbwaiter · zip-line cargo · composting toilet · **spring-assisted stairs** (kept out of
Season 1 because a reference reel already did it).

---

## 4. Editing style — one-shot (no cuts)

**MANDATORY (Irfan, 24 Nov 2026, also in `pipeline/README.md` "Editing style rule"):** one-shot editing with
smooth fast whip transitions and **no cut scenes** on this Page and every future Page.

### 4.0 Reference study — reel/1661364992040054 ("What if the Eiffel Tower was built in NYC", 94 s, 720×1280)
Watched in the browser on 24 Nov 2026 + frame-difference scan (~5 fps sampling, so timings are approximate).
- **The camera never stops.** Even on a "hold" it drifts, orbits or slowly cranes, so the image is always alive.
- **Rhythm:** a fast move about every **2.5–3.5 s**, roughly one per sentence. Two kinds:
  1. **Travel moves** (~1–2 s, sometimes up to 5–7 s for a big reveal): smooth eased fly-overs and orbits,
     e.g. top-down over the city → down to street level → through the tower's legs → crane up for a height bar.
  2. **Snap push-ins** (~0.2–0.4 s, heavy motion blur): e.g. from the whole tower straight into a 6 cm rivet
     close-up. Looks almost like a cut but the blur frames show it is one continuous zoom — this is the "whip".
- **Scale jumps without cuts:** city-wide → building → macro detail, all one camera. Cross-sections are done by
  moving the camera **down into a cut-away ground slice** (soil layers + foundation) instead of cutting to a diagram.
- **Graphics live in the world:** dimension lines drawn on the ground (60 m / 125 m), a tall height bar (330 m),
  glowing highlight on the part being talked about. Captions = **one big bold word at a time, mid-frame**.
- Only tiny frame-difference spikes; checked three of them frame by frame — all were blurred push-ins, not cuts.
- I watched muted, so I can't say how loud its whooshes are; we keep ours subtle under the VO.

**What we take for Self-Made Engineer** (style only, nothing copied): always-moving camera, a move per sentence,
mix of 1–2 s travel moves and 0.2–0.4 s blurred snap push-ins to detail close-ups (bolts, valves, gauges), cut-away
ground slices for underground builds (#3 ram pump pipe, #6 earth tubes, #7 digester, #8 walipini), measurement
graphics anchored in the world (2D overlays following 3D anchors — our v2 `label`/`bar` types already do this).

### 4.1 Look
- **Max hold ≤ 9 s (fail > 10 s)** — Irfan/chief rule for all Pages (24 Nov 2026): long beats are split at
  sentence starts into sub-stops on the same object (`<stop>__detail` / `<stop>__alt`) with short moves between.
- The whole reel = **one continuous camera** inside Mercer Hollow. Holds (slow drift/orbit) while the narrator
  explains, but **never fully static** (slow drift/orbit/crane); a move about every 2.5–3.5 s: **travel moves**
  (1–2 s, smooth eased fly-over/orbit) between spots, and **snap push-ins** (0.2–0.4 s, heavy motion blur,
  subtle whoosh) into close-ups. Big reveals (finale tour) may use a long 5–7 s fly-through.
- Builds **assemble in place** when the camera arrives (parts drop in / slide / bolt on with tiny bounces),
  Bolts does a pose (inspect, wrench, thumbs-up), HUD gauges animate.
- Opening: 1 s establishing drone-style whip from the horizon down to Bolts + outfit chip. Ending: wide pull-back
  showing all builds so far (continuity flex), teaser chip, question.
- Note vs WJH rule "no sound effects at scene changes": that rule is for WJH. Here the whoosh is part of the
  one-shot style (Irfan's 24 Nov decision); keep it short and quieter than the voice (≈ −20 dB under VO).

### 4.2 What the pipeline needs (Opus build task, after the Windows benchmark)
1. **`render_episode_v2 --mode oneshot`**: one Blender scene for the whole episode (world built once, not per beat),
   one camera with **waypoints per beat** (`shot.camera: {"at": "ridge_turbine", "hold": "orbit_slow"}`), whip
   segments auto-timed from voice timings (whip starts ~0.4 s before the beat's first word). Frame-range jobs still
   split the one long timeline (≤ 150 frames/job) for parallelism + resume.
2. **Motion blur** only during whips (Cycles/EEVEE motion blur keyframed on) — or cheaper: 2D directional blur in
   `overlay_v2.py` driven by camera speed exported per frame (decide after benchmark; 2D is far cheaper on 4 GB).
3. **World loader** `page2/world_mercer.py`: builds Mercer Hollow + every build listed in `world_state.json` with
   idle animations; uses instancing (trees, fence posts, grass), simple LOD for far builds, so the full scene fits
   in **4 GB VRAM** (RTX 3050). Each build = one function `build_<id>(ctx, state, anim)` with an "assemble" animation
   for its own episode and an "idle" animation for later ones.
4. **Character rig** `page2/character.json` + one rigged low-poly-but-detailed Bolts (beard, glasses, bandana) with
   swappable outfit meshes and ~8 pose/action clips (walk, wrench, hammer, point, inspect, thumbs-up, hands-on-hips,
   scratch-beard). Torque goose: waddle/peck/honk/flap clips.
5. **Overlays (2D)**: new chip styles MISSION / SNAG / HACK / IT WORKS, "BOLTS · BUILD #N" chip, outfit chip, HUD
   gauges (reuse `meter`/`big`), callback card ("DAY 1 BUILD" label pinned to the old build's anchor).
6. **Outfits**: one outfit per reel by default. If a reel ever needs two, the swap happens **inside a whip**
   (motion blur hides it) — the rig must support an outfit switch at a given frame.
6b. **Camera language** (from the 4.0 reference study): per-beat camera keys `travel` (1–2 s eased path),
   `snap` (0.2–0.4 s push-in to a close-up anchor, blur on), `drift`/`orbit`/`crane` for holds (never a dead-still
   camera), `section` (camera dives into a cut-away ground slice — boolean cut of the terrain + soil layer texture).
   Moves auto-timed to sentence starts from the voice timings.
7. **Lighting presets**: `day` (default v2), `dusk` (warm low sun, house lights on), `frost`/`snow` (white ground,
   cold sky) — needed for the season arc. No full night scenes (v2 bright-world rule); dusk is the darkest.
8. **Audio**: whoosh SFX track placed at whip times; continuous VO rules unchanged (gaps ~0.3 s).
9. **QC** (fix-vs-skip rule for finished videos: `page2/QC-RULES.md`): new `qc_oneshot` check — no hard cuts (frame-difference spikes allowed only inside planned travel/snap windows; a spike outside them = FAIL), no static camera longer than ~1 s,
   no popping of old builds, world_state builds all present; plus all existing qc_v2 + qc_full checks and
   Fable's look at every 1-fps sheet.
10. Length: target **85–100 s** (above 60 s monetisation line, cheaper than 130 s; good for 5/day).

---

## 5. Production order (approved — starts on the Windows laptop)
1. Windows laptop setup + render benchmark (PLAN §6).
2. Opus: character + goose model/rig sheet (Codex-first concept images via `tools/gen_image.py` for the look),
   Mercer Hollow world v1, oneshot mode, new chip styles → test render of a 20 s "world tour" for Irfan to approve.
3. Fable: Build #1 research/fact-check + script; Opus: build/render; Fable: final QC; Irfan approves → post.
4. After each post: add the build to `world_state.json`.

### 5.1 Posting times — US time zones
Main audience = US, so slots are set in **US Eastern Time** (also good for Central; the 9 PM ET slot = 6 PM Pacific).
| Slot | ET (US) | MYT now (US standard time, until 13 Mar 2027) | MYT after US DST starts 14 Mar 2027 |
|---|---|---|---|
| Morning commute | 7:30 AM | 20:30 | 19:30 |
| Lunch | 12:00 PM | 01:00 | 00:00 |
| After school/work | 4:00 PM | 05:00 | 04:00 |
| Evening prime | 7:00 PM | 08:00 | 07:00 |
| West Coast evening | 9:00 PM (6 PM PT) | 10:00 | 09:00 |
- Ramp: first 3 days at 3/day (7:30 AM, 12:00 PM, 7:00 PM ET), then all 5. Graph API scheduling uses UTC, so the
  scheduler converts from ET (handles DST automatically via `America/New_York`).
- After 2 weeks, re-tune from FB Insights (which hours US viewers are actually online).
- Captions, hashtags and the engagement comment in US English; hashtags US-oriented (#DIY #offgrid #homestead
  #engineering #backyardbuild #homeimprovement #prepper).

---

## 6. Irfan's decisions (24 Nov 2026 — "hang suggest, aku follow": all recommendations accepted)
1. **Name:** Walt "**Bolts**" Mercer.
2. **Look:** salt-and-pepper beard + safety glasses on forehead + red bandana + pencil behind ear.
3. **Sidekick:** **Torque the goose** — yes.
4. **Voice:** fixed **Fenrir** (American accent) — confirmed by Irfan after an A/B test vs Sadaltager (24 Nov 2026). Director notes: `voice-test/episode.json`.
5. **Season 1 order:** the 10 builds in section 3 as listed.
6. **Reel length:** **85–100 s**.
7. **Whoosh SFX** at whips/snap push-ins: yes, subtle under the VO.
8. **Episode chip:** "**BUILD #N**".
9. **Dusk scenes:** yes (no full night).
Plus (chief session, 24 Nov): **US audience first** (section 0), **one-shot mandatory** (section 4), **runs on the Windows laptop** (section 7).

**Page name:** Self-Made Engineer (final).

**Page live (24 Nov 2026):** https://www.facebook.com/profile.php?id=61597072432545 · **FB_PAGE_ID = 1485761621285655** (goes in the Windows laptop `.env`); FB_PAGE_TOKEN done: never-expiring Page token in gitignored `.env.page2` on the Mac → copy to the laptop `.env`.

**Code transfer:** clone `finest1119/irfan` (same branch) + `git pull`; own `.env` per laptop (section 7.1).

---

## 7. Windows laptop port + 4 GB VRAM budget (this Page runs on Windows, not the Mac)
Laptop: Windows 11, Intel i5, **RTX 3050 (likely 4 GB VRAM)**, RAM unknown (assume 16 GB; if 8 GB → 1 render at a
time, no parallel jobs). One Opus build task ("port + benchmark"), then Fable reviews the benchmark report.

### 7.1 Setup (day 1, Irfan + Opus)
1. **Folder:** use a short path with no spaces/`&`, e.g. `C:\SME\` (the Mac path "Facebook & Youtube Monetisation"
   breaks `cmd`/Task Scheduler quoting).
2. **Getting the code there (Irfan's decision, 24 Nov 2026):** `git clone https://github.com/finest1119/irfan.git C:\SME\irfan`,
   check out the **same branch** as the Mac, update with `git pull`. Page 2 work lives in `irfan/page2/`; shared
   `pipeline/` changes must stay **cross-platform and backward compatible with WJH on the Mac** (OS-based defaults,
   config overrides, never change WJH output). `.env`, `output/`, `.venv/` stay out of git (already in `.gitignore`).
   **Not in git → fetch on the laptop:** `assets/polyhaven/` (HDRIs/textures, gitignored) and the Kenney kit if
   ignored — Opus adds a small `tools/fetch_assets.py` (downloads the exact CC0 files listed in `assets/CREDITS.md`)
   or Irfan copies the folder once by USB.
3. Install (winget where possible): Git, **Python 3.11** (`py -3.11 -m venv .venv`, then `.venv\Scripts\pip install
   google-genai faster-whisper python-dotenv pillow numpy`), **Blender 5.3** (same version as the Mac), **ffmpeg**
   (full build, on PATH), **Node.js LTS + Codex CLI** (`npm i -g @openai/codex`, log in; fall back to WSL only if the
   native Windows build fails), **Claude Code** desktop (same account), NVIDIA Studio driver (latest).
4. **Own `.env` per laptop** (never committed): GEMINI_API_KEY, FB_PAGE_ID, FB_PAGE_TOKEN for the Self-Made Engineer
   Page (its own token, not WJH's), plus `BLENDER_EXE` / font overrides if needed. Irfan types the secrets in.
5. Power: plugged in, "never sleep" on AC, **lid close = do nothing**, Windows Update active hours set to the
   render window so it never reboots mid-render.

### 7.2 Code changes for cross-platform (Opus)
Found in the current pipeline (Mac-only bits):
- `make_episode.py:30` + `v2_test.py:27` hard-code `/Applications/Blender.app/...` → read `BLENDER_EXE` from
  `.env`/`config_local.json`, default per OS (`C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`).
- `overlay_v2.py:39`, `qc_v2.py:106`, `v2_test.py:33` use **Avenir Next** (`/System/Library/Fonts/Avenir Next.ttc`,
  macOS only) → bundle an open-licence font in `assets/fonts/` for Page 2 (e.g. Montserrat Bold/ExtraBold, OFL)
  and pick the font by config, so the WJH look on the Mac stays unchanged.
- **Backward compatible:** every change keeps the Mac/WJH defaults (Mac Blender path, Avenir) when no override is
  set, and before pushing a shared `pipeline/` change, a Mac session (WJH/chief) renders one WJH preview
  shot to prove nothing changed.
- All paths via `pathlib`; no `sed`/bash pipes inside the pipeline; subprocess calls as arg lists (no `shell=True`).
- ffmpeg already uses `libx264`/`libx265` (cross-platform ✅). Optional speed-up: `h264_nvenc`/`hevc_nvenc` on the
  RTX 3050 for intermediate segments only; keep `libx265` for the final FB copy if NVENC quality/size is worse.
- faster-whisper stays on **CPU int8** (keeps VRAM free for Blender).
- Scheduling: `tools/fb_schedule_reel.py` converts ET slots → UTC with `zoneinfo("America/New_York")`
  (Windows needs `pip install tzdata`).

### 7.3 4 GB VRAM scene budget (Mercer Hollow must fit in ONE one-shot scene)
| Item | Budget |
|---|---|
| Whole scene in VRAM | **≤ 3 GB** (leave ~1 GB for Windows/driver/OptiX) — checked by the benchmark |
| Textures | max **2K** for hero objects (house, Bolts, current build), **1K** for everything else; HDRI 2K |
| Trees, fence posts, grass, rocks, distant houses | **instanced** (collection instances / geometry-nodes instances), never duplicated meshes |
| Grass | textured ground + a few instanced clumps near camera only — no full hair/particle lawn |
| Bolts | ≤ 30k tris, one 2K texture set; outfits as separate low meshes swapped by visibility |
| Torque | ≤ 5k tris |
| Finished builds far from camera | low-detail LOD versions (auto-swap by camera distance per waypoint) |
| Far hills / town | 2D card or very low-poly with baked texture |
| Render | Cycles + **OptiX** (RTX), adaptive sampling, OptiX denoiser, **persistent data ON** (world built once for the whole one-shot); **1 GPU render process at a time** (parallel jobs would multiply VRAM) |
| Fallback if too slow | EEVEE (much faster, slightly less realistic) or render at 0.75 scale + upscale — benchmark decides |

### 7.4 Benchmark gate (before the first episode)
Render a 20 s Mercer Hollow test (world + Bolts + Torque + 1 build, one-shot camera with travel + snap moves) and
report: seconds per frame (Cycles-OptiX vs EEVEE), peak VRAM, RAM, total time. **Target:** a 90 s reel (2,700
frames) renders in **≤ 2.5 h**, so 5 reels/day fit in ~12 h of rendering. If not: drop to 3/day or the fallback.

### 7.5 Scheduled tasks on the laptop
- Claude desktop app scheduled tasks (same account) for: daily build queue (next episodes from the season plan),
  posting at the ET slots, engagement comment as the Page.
- **Posting = Graph API only** via `tools/fb_schedule_reel.py` with `is_ai_generated` (Irfan confirmed 24 Nov 2026 it
  shows Facebook's "AI info" label) — no Chrome/browser UI needed on the laptop. Then `tools/page_comment.py --auto`
  for the engagement comment. Uses the laptop's own `.env` Page token; Public; US hashtags. Not created yet — after the benchmark.
- Optional safety net: Windows Task Scheduler runs a tiny watchdog that restarts a stuck render.

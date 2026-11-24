# PLAN v1 — Page 3 "Everyday Decoded": how everyday things work behind the scenes (US audience)

Written 24 Nov 2026 by the Page 3 session. Status: **PLAN APPROVED by Irfan 24 Nov 2026 (section 8).**
Nothing built yet. FB Page live: Everyday Decoded, Page ID 1465128156682768 (section 9). Runs later on **Windows laptop #2** (RTX 3050, ~4 GB VRAM), same Claude Max
account, target **5 reels/day** after a ramp-up. Reuses the v2 pipeline (`irfan/pipeline/README.md`).
Does not touch WJH files or `irfan/page2/`.

**Audience (Irfan via the chief session, 24 Nov 2026): monetization, US viewers = main audience.** Topics are what
Americans use daily; 3D worlds look American (suburbs, downtown, US roads/signals, US stores); **US English and US
units first** (°F, miles, mph, gallons, inches; metric only if useful, in brackets); posting times tuned to US time
zones (section 3.7). No company/brand names or claims unless clearly sourced (and even then, prefer "a big carrier",
"payment apps").

Fact status: every number here was checked in a batched Fable 5.2 fact-check (section 6). Each episode still gets its
own Fable fact-check at script time (2+ sources) before render, as in the SOP.

---

## 1. Concept

Everyday moment → **follow the hidden journey** → surprising fact → comment question.
"You tap your card. A few seconds later: approved. In between, your payment went on a trip." The camera starts at the
thing in your hand and travels, without a single cut, through everything that happens behind it.

- Evergreen (no news), US English VO, 70–100 s (hard floor 60 s, cap 120 s).
- High relatability: the viewer did this thing today. Comment drivers: "I never knew that", "wait, so…",
  myth-busting, "tag someone who still thinks…", small polls ("Team chip or team tap?").
- Original brand, original worlds. No logos, store names or app UIs (section 7).

## 2. Page name — **Everyday Decoded** (FINAL, Irfan 24 Nov 2026)

- **Name:** Everyday Decoded. **Tagline:** "The hidden side of the things you use every day."
- **Phrasing to reuse:** end card / sign-off "Another one decoded." · caption opener "Decoded: what really happens
  when you tap your card." · series chips "DECODED · MONEY #3" · comment prompt "What should we decode next?"
  (viewer suggestions → "You asked, we decoded" episodes) · hashtags #EverydayDecoded #HowItWorks #Explained.
- **Branding:** the "decode" idea fits the format — the camera "unlocks" the everyday object and goes inside.
  Logo idea: white wordmark "EVERYDAY / DECODED" on charcoal, with the teal Spark trail running through the "O" of
  DECODED like a keyhole/circuit path; amber accent dot (made with `tools/gen_image.py`, Codex first; Irfan picks).
  Optional 0.5 s on-screen sting at the end: the Spark draws a teal ring around the object + "DECODED" stamp (2D).
- Handles still to check/claim by Irfan on FB/IG/YouTube (web search can't see platform handle search).
- Other options considered earlier (The Hidden Journey, Inside The Everyday, Behind The Tap, Follow The Spark) are
  dropped.

## 3. Format

### 3.1 Script shape (~220–280 words, ~170 wpm → 75–100 s)
1. **Hook (0–4 s)** — the everyday moment + time/scale tension: "You tap your card. A few seconds later it's
   approved. Here's the trip it took." (No intro.)
2. **The journey (3–5 stops)** — one stop per sentence-pair; the camera travels between stops (3.3).
   Plain words, one analogy per reel ("like a relay race", "like a sponge for heat").
3. **The twist / surprising fact** — the comment driver (topic bank, column 4), ~60–70 % into the reel.
4. **Back to the moment** — camera pulls all the way back out: "…and all you did was tap."
5. **Comment question + share line**, last line loops to the hook.
US English throughout (elevator, gas, cell phone, check/checking account, zip code), US units first.

### 3.2 Look & identity
- **v2 look minimum** (bright daytime, HDRI sky, PBR materials, full persistent world, never a void). Interiors
  (inside a phone, a fiber cable, a furnace) are **bright, lit sets** — clean "cutaway museum model" style.
- **American settings:** wide suburban streets with yellow center lines, mast-arm traffic signals, stop signs,
  sidewalks + mailboxes, pickups/SUVs/school bus, single-family houses with lawns and garages, strip mall with a
  drive-thru, big-box store parking lot, highway with an overhead toll gantry, town water tower, monopole cell
  towers, a downtown with a stadium. Generic, no real brands/logos.
- **Palette** (distinct from WJH navy/red and Page 2): **Charcoal #1B1F24** (chips/cards), **Signal teal #00B3A4**
  (journey trail, highlights), **Amber #FFB000** (caption current-word highlight, the twist card), white text.
  Heat topics: trail amber; cold: ice-blue #7FD4FF.
- **Captions:** v2 system (top-centre, 22–31 % band), current word on an **amber** box.
- **Chips:** series chip top-left ("MONEY · #3"), "STOP 1 / 2 / 3…" as the camera reaches each stop, a big amber
  "TWIST" card for the surprising fact.
- **Logo:** see section 2 (wordmark with the Spark trail through the "O").

### 3.3 One-shot camera (MANDATORY — no cuts)
- **Always moving.** Holds are slow drifts/orbits/cranes; a move roughly every sentence (2.5–3.5 s), as in the
  reference reels (Page 2 studied reel/1661364992040054: 1–2 s travel moves + 0.2–0.4 s blurred snap push-ins,
  scale jumps without cuts, cut-away ground slices).
- **The "dive inside" without a cut — two techniques, both one continuous camera in one Blender scene:**
  1. **Nested scale (preferred):** the interior is modelled *inside* the object at real scale (phone board inside
     the phone, coil inside the card, fiber core inside the duct). The camera flies in with a 0.3–0.5 s blurred snap
     push-in while `clip_start` and focal length animate; the object's shell opens (cut-away) as the camera passes.
  2. **Fill-frame portal (only for extreme scale jumps, e.g. street → inside a glass fiber):** the camera pushes
     into a surface that fills the whole frame (glowing fiber end, a chip's black surface) for 2–4 blurred frames
     during a whip and emerges in an enlarged interior set placed elsewhere **in the same scene**. Camera path is
     continuous; QC treats it as a whip (frame-difference spike allowed only inside the whip window).
- **Cut-away slices** for anything underground or inside walls (fiber ducts, water mains, AC lines, road loops).
- **Back-out ending:** the last move reverses back to the everyday object (loop, rewatch value).
- Pipeline dependency: the **`--mode oneshot` renderer does not exist yet** (planned in Page 2 PROPOSAL 4.2). Page 3
  **shares that build with Page 2**. Page 3 adds: the Spark guide, the nested-scale/portal helper, the slice helper.

### 3.4 Recurring guide element — "the Spark"
A small glowing **teal orb with a short light trail** that *is* the thing travelling: your voice, the payment
request, a packet of heat, a drop of water, your package. The camera follows the Spark, so every move has a reason.
- Cheap (emissive sphere + trail curve), recognisable at thumbnail size, brandable ("follow the Spark").
- Colour = what it carries (teal data/money, amber heat, ice-blue cold). Labels stay 2D.
- No talking character → no rig/lip-sync cost (unlike Page 2's Bolts).

### 3.5 Voice
- **Recommended: one fixed host voice = Gemini `Sadaltager`** (calm, knowledgeable; README maps it to
  how-things-work). Fixed narrator = part of the brand; Page 2 uses Fenrir, so the Pages sound different.
- Alternative: rotate **Sadaltager / Orus**.
- Director notes: friendly American-English expert, curious tone, ~165–175 wpm, short sentences, small pause before
  the twist. Continuous narration (≈0.3 s gaps). Optional subtle whoosh on whips (≈ −20 dB under VO).

### 3.6 Length
**75–100 s** (recommended): >60 s for monetization, room for 3–5 stops, fits 5/day render time.

### 3.7 Posting times (US-tuned; final slots after week-1 insights)
Target US Eastern (covers most US viewers; Pacific is 3 h behind). MYT = ET + 13 h in winter (EST),
ET + 12 h in summer (EDT, mid-March → early November) — the scheduler must use time-zone-aware times, not fixed MYT.

| Slot | US ET | US PT | MYT (winter) |
|---|---|---|---|
| Morning commute | 7:30 am | 4:30 am | 8:30 pm |
| Lunch | 12:00 pm | 9:00 am | 1:00 am |
| After work | 5:30 pm | 2:30 pm | 6:30 am |
| Prime time | 8:00 pm | 5:00 pm | 9:00 am |
| Late / West-coast evening | 10:30 pm | 7:30 pm | 11:30 am |
Ramp-up: first 2/day use the 12:00 pm and 8:00 pm ET slots.

---

## 4. Worlds (build these first; topics hang on them)

| World | What's in it | Topics using it | Build cost |
|---|---|---|---|
| **W1 Hometown USA** | American suburb + small downtown: streets with US signals and loop slices, monopole cell towers, street slice with fiber/water/power, a data center, power substation + lines, town water tower, highway with toll gantry, strip mall with drive-thru, big-box store, sort center + delivery vans, stadium, coastal edge with an undersea-cable landing, "sky layer" (satellites, reached by a crane-up whip) | 5G, calls, 911, Wi-Fi (street side), undersea cable, ATM network, P2P transfer, electricity/smart meter, tap water, traffic lights, GPS, toll tag, delivery app, drive-thru, packages, streaming, satellite TV, first-down line (≈18) | **High but used most → build FIRST** |
| **W2 Macro Kit** | bright enlarged "inside the device" sets nested in real objects: phone board + screen layers, card chip + antenna coil, payment terminal, checkout scanner, ATM keypad, TV remote LED | tap-to-pay, chip card, ATM, barcode, touchscreen, TV remote, 911 (phone side) (≈7) | Medium |
| **W3 Cut-away House** | a US two-story suburban house sliced open (one of W1's houses): kitchen (microwave, fridge), living room (TV, router), basement furnace, central-AC outdoor condenser + indoor coil, ducts in walls/ceiling, smart meter on the outside wall, thermostat | central AC, furnace, microwave, Wi-Fi (inside), TV remote, smart meter (end), tap water (end) (≈7) | Medium; **same scene as W1** |
| **W4 Airport** | **reuse WJH v2 airport world** (`scene_lib_v2.build_world`) + new baggage-hall slice | checked bags (1, + reserve fog-landing) | Low — copy builders into the Page 3 folder, don't edit WJH files |
| **W5 Food Chain** | farm/port edge, warehouse with robots + conveyors, ripening rooms, a dairy line, restaurant/drive-thru kitchen interior | delivery app (kitchen), drive-thru (kitchen), packages (warehouse), bananas, milk (5) | Medium |

Build order: **W1 + W3 (one scene)** → W2 → W5 → W4. W1+W3+W2 cover ~25 of 30 topics.
4 GB VRAM: instanced houses/trees/cars, distant LOD, interiors hidden when far, textures ≤ 2K. Benchmark first (7).

---

## 5. Topic bank (30, in 6 series × 5) — US-first

Per topic: **hook line** · **camera path (one shot)** · **twist fact (comment driver)** · **world**.
Numbers as corrected by the Fable fact-check (section 6); keep them soft on screen ("about", "up to").

### A. Phone & internet
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| A1 | "You open an app on 5G. Here's the trip your request takes in a blink." | phone → radio beam to a cell tower → down the tower → fiber under the street → data center → back | 5G antennas can **steer narrow beams** at your phone; the fastest high-band (mmWave) 5G is easily blocked by walls, leaves, even your hand, so it reaches only a few hundred yards from the tower | W1 |
| A2 | "You say 'hello' on a call. It's chopped into tiny pieces before it leaves your phone." | mouth → mic → voice digitized into small packets → tower → fiber → other city's tower → friend's ear | Your voice travels as **small digital pieces of about 20 milliseconds of sound each**, packed and reassembled at the other end | W1+W2 |
| A3 | "You call 911. Here's how they find you — even if you can't say where you are." | dial 911 → nearest tower → routed to a local 911 call center (PSAP) → location arrives → dispatcher's map | Cell 911 calls **used to be routed by which tower picked up**; since FCC rules adopted in 2024, carriers increasingly route by the **phone's own location** when it's accurate enough (keep soft) | W1+W2 |
| A4 | "Your Wi-Fi and your microwave have something weird in common." | router in the living room → waves through rooms → phone on the couch → back through the router → out the street fiber | Common Wi-Fi uses the **2.4 GHz band — the same band microwave ovens use**, which is why an old microwave can make Wi-Fi stutter | W3+W1 |
| A5 | "Your text to Europe doesn't go to space. It goes under the ocean." | phone → fiber → coastal landing station → dive into the sea → along the cable on the seabed → other coast | **Undersea fiber cables carry the vast majority of intercontinental internet traffic** (not satellites); in deep water the cable is about as thick as a garden hose | W1 |

### B. Money & payments
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| B1 | "You tap your card. A few seconds later: approved. Here's where it went." | card near terminal → inside the card (coil + chip) → terminal → card network → your bank's data center → "approved" back | The card **has no battery** — the reader's field powers it, and payment terminals are built to read it within about **1.5 inches (4 cm)** | W2+W1 |
| B2 | "Why your card got a chip — and why it changed in 2015." | card into the slot → inside the chip → one-time code → bank checks it | The chip makes a **new one-time code for every in-store chip purchase**, so stolen data from one swipe can't be reused; the big US switch came with the **October 2015 liability shift** (a card-network rule, not a law; gas pumps followed in 2020) | W2 |
| B3 | "You use another bank's ATM. Your bank still answers in seconds. How?" | PIN on keypad → encrypted inside the pad → ATM network → your bank → approval → cash cassette counts notes | The PIN is **encrypted inside the keypad itself**; ATM **networks** link banks so most cards work at most machines | W2+W1 |
| B4 | "You send a friend money in an app. It shows up instantly… but did it really move?" | phone → app's servers → your bank → (often later) the banks settle up → friend's balance | Often the app shows the money instantly while **banks settle the real transfer later** (e.g. in batches); newer instant-payment systems (e.g. the Fed's FedNow, live since July 2023) settle in seconds — no app named | W1 |
| B5 | "A pack of gum changed every store in America." | item slides over the scanner → laser or camera reads the bars → number → store computer | The bars are just a number; the **first product scanned at a real checkout was a pack of chewing gum, in Ohio, in 1974** | W2 |

### C. Home
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| C1 | "Your central AC doesn't make cold air. It moves heat outside." | thermostat click → indoor coil → refrigerant lines (Spark turns amber) → through the wall → outdoor condenser fan → heat out | AC is a **heat pump moving heat from inside to outside** — and it also **pulls water out of the air** (the condensate drain) | W3 |
| C2 | "The flame in your furnace never touches the air you breathe." | thermostat → basement furnace → burner → heat exchanger (cut-away) → blower → ducts → vent in your room | A gas furnace heats a **sealed metal heat exchanger**; your air passes *around* it while the combustion gas goes out the flue — that's why a cracked exchanger can be dangerous (CO alarms) | W3 |
| C3 | "Why there's a metal mesh in your microwave door." | button → magnetron → waves bounce → water molecules wiggle → end at the door mesh | Microwaves are about **5 inches (12 cm) long**; the holes in the mesh are far smaller, so the waves stay in — but light gets out, so you can watch your food | W3 |
| C4 | "Flip a switch, and the power you're using was made a split second ago." | switch → wire in the wall → smart meter → pole transformer → substation → high-voltage lines → power plant | The grid has almost no storage: **power plants must match demand second by second** (very little storage compared with demand); US grid frequency is **60 Hz** — and a smart meter records your use at least hourly and sends it to the utility at least daily (~72 % of US meters by 2022) | W1+W3 |
| C5 | "Your town's water tower is basically a giant battery for water pressure." | faucet → pipe in the wall → water main slice → treatment plant → up into the water tower | Water towers use **gravity for pressure: every ~2.31 feet of height adds ~1 psi** | W1+W3 |

### D. Transport
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| D1 | "The traffic light knows you're waiting. Here's how." | car stops at the line → dive into the road slice → wire loop → controller cabinet → green | Many intersections use an **induction loop under the road that senses the metal** of your car — not its weight | W1 |
| D2 | "Your phone's GPS would be off by miles every day without Einstein." | crane up to the sky layer → satellites (~12,550 miles up) each broadcast time signals → signals from at least 4 satellites come down to the phone → map | GPS satellite clocks gain **~38 microseconds a day** from relativity; uncorrected, positions would drift **about 6 miles (10 km) or more a day** | W1 |
| D3 | "You drive through a toll at 60 mph and never stop. How does it know it's you?" | windshield tag → overhead gantry reader → radio ping → account charged | The gantry reads your tag by radio as you pass at highway speed; some sticker tags have **no battery at all** — the reader's signal powers them (others carry a ~10-year battery; don't generalise) | W1 |
| D4 | "You check a bag. Here's the hidden ride it takes to your plane." | bag on the belt → tag scanned → conveyor maze under the terminal → sorted → loaded | Big US airports hide **miles of conveyor belts** under the terminal; scanners route each bag automatically | W4 |
| D5 | "Your elevator is balanced by a hidden counterweight — the motor barely lifts it." | press button → rise in the shaft slice → ropes over the sheave → counterweight passing the car | The **counterweight ≈ the car + ~40–50 % of its load**, so the motor only lifts the difference; elevators hang on **several ropes, and the set is designed with a big safety margin** (hedged: "each rope can hold the car" has only one maker source) | W1 |

### E. Food & delivery
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| E1 | "You order food on an app. Within seconds, an algorithm starts planning your delivery." | tap order → data center → restaurant tablet → map of drivers → one chosen → kitchen → doorstep | Some apps time dispatch to the food's ready time and weigh distance, traffic and prep — sometimes stacking two orders on one trip (no company named) | W1+W5 |
| E2 | "At the drive-thru, a clock starts the second your car rolls in." | car on the sensor → speaker post → order screen in the kitchen → grill → window | Many drive-thrus have **sensors that detect each car and time it** from menu board to window (no chain named) | W1+W5 |
| E3 | "Your package was picked in a warehouse where the shelves come to the workers." | 'buy' click → fulfillment center → robot brings a shelf to a picker → box → sort center → van → porch | In many modern warehouses **robots carry shelves to people** instead of people walking the aisles | W5+W1 |
| E4 | "The bananas at your store traveled green — then were gassed on purpose." | store banana → ripening room → cool cargo ship → green bunch on the plant | Bananas ship **green and kept cool (~56–58 °F — colder damages them)**, then ripen in rooms with **ethylene**, the gas bananas make naturally | W5 |
| E5 | "Your milk was heated to 161 °F — for just 15 seconds." | fridge jug → dairy truck → plate heat exchanger → fast cooling → bottling | Standard pasteurization: **161 °F (72 °C) for 15 seconds**, then fast cooling — kills harmful bacteria without boiling the milk | W5 |

### F. Entertainment
| # | Hook | Camera path | Twist fact | World |
|---|---|---|---|---|
| F1 | "You hit play. The show didn't come from far away." | TV → street fiber → a server in your own region → video chunks flowing | Streaming services keep **copies of popular shows on servers close to you**, sent in **chunks a few seconds long** — quality can switch between chunks | W1 |
| F2 | "That yellow first-down line isn't on the field. So how is it under the players?" | stadium → broadcast camera sensors → graphics truck → color check per pixel → line drawn only on field-colored pixels → your TV | Computers know each camera's exact angle and zoom and **paint the line only on field-colored pixels** (not on uniforms or skin), so players appear to walk over it; first aired in **September 1998** | W1 |
| F3 | "Satellite TV travels at least 44,000 miles to reach your living room." | stadium → uplink dish → crane up to the satellite → back down to a home dish | TV satellites sit about **22,236 miles above the equator**; up and down is **at least ~44,000 miles**, adding roughly **a quarter of a second** of delay | W1 |
| F4 | "Your TV remote flashes a light you can't see — but your phone camera can." | thumb → LED → invisible infrared code → TV sensor | Remotes send **infrared pulses in a code**; point one at a phone camera and often the **selfie camera** shows the flashing (many main cameras filter infrared) | W3+W2 |
| F5 | "Your phone screen can't feel a glove. Here's why." | finger → glass → electrode grid → controller chip → app reacts | Capacitive screens sense **a change in a tiny electric field caused by your conductive finger**; **most ordinary gloves** block it | W2 |

**Reserve (Season 2 / swaps):** QR codes (highest level: ~30 % of the data can be damaged — but not the corner squares), fridge heats the kitchen, phone charging
slows near full, fog landings (ILS/autoland), canned food before the can opener, noise-cancelling headphones,
smart thermostats, garage door openers, EV charging, credit score.

## 6. Fact-check (Fable 5.2 medium, batched, 24 Nov 2026) — corrections already applied in section 5

Based on web-search summaries (primary pages not opened). **Each episode is re-checked at script time with sources
opened.**
- **OK:** A4 Wi-Fi/microwave 2.4 GHz · A5 undersea cables (~99 % of *international* traffic — say "often quoted";
  garden-hose size not pinned to one source → soft) · B4 P2P (CFPB; FedNow 20 Jul 2023) · B5 gum, Troy, Ohio,
  26 Jun 1974 · C1 AC · C3 microwave ~12 cm, holes ~1 mm · C5 2.31 ft/psi · D1 loops · D4 bags (Seattle ~10 mi,
  Salt Lake City ~9 mi) · E3 goods-to-person · E4 bananas 56–58 °F + ethylene · E5 161 °F/15 s (21 CFR 1240.61) ·
  F1 chunks 2–6 s · C2 furnace (with "can be dangerous").
- **CORRECTED:** tap-to-pay "two seconds" → "a few seconds" (tap 1–2 s, whole transaction < 6 s) · A3 911 routing
  (tower → location-based routing, FCC 2024) · D2 GPS 12,550 mi, 6+ mi/day, signals come DOWN to the phone (phones
  only receive) · F2 first-down line "field-colored pixels", 27 Sep 1998 · B2 2015 shift = network rule.
- **HEDGED:** A1 5G range · A2 20 ms (one primary source: RFC 3267) · B3 "thousands of banks" dropped · C4 grid
  "very little storage", smart-meter interval · D3 toll tags (many US tags are active with a battery) · D5 "each
  rope holds the car" (one maker source) · E1 dispatch (research papers only; hook fixed) · E2 drive-thru timing ·
  F3 44,000 mi / 0.24 s are minimums · F4 IR → selfie camera · F5 "most ordinary gloves".
- **Hook/mechanism fixes:** D5 ropes hold the car, the counterweight balances it · F5 the finger disturbs the
  screen's own field · E1 hook no longer says the driver is picked instantly.
- Key sources: fcc.gov/Location-Based-Routing · gps.gov/systems/gps/space · ecfr.gov 21 CFR 1240.61 ·
  postharvest.ucdavis.edu · eia.gov smart-metering FAQ · federalreserve.gov FedNow release (20 Jul 2023) ·
  consumerfinance.gov P2P tips · smithsonianmag.com barcode history · si.com yellow line history ·
  fhwa.dot.gov loop detectors · resources.telegeography.com · Visa contactless paper · elevatorworld.com.

**Name check (earlier candidates, now superseded by Everyday Decoded):** no notable collision found for The Hidden Journey, Inside The Everyday, Follow The Spark.
"Behind The Tap" is close to "Beyond the Tap" (a beverage podcast). "How It Really Works" is too close to *How It
Works* magazine and a "How It Actually Works" channel → avoid. Web search can't see FB/IG/YouTube handle search →
Irfan checks handles before choosing.

## 7. Risks & dependencies

**Accuracy**
- Technical topics are easy to over-simplify into wrong. Every number goes through Fable (2+ sources) at script
  time; on screen "about / up to / typically". Drop anything not clearly supported.
- US-first facts (120 V / 60 Hz, °F, miles). A UK fact only if it's clearly labelled.
- Proprietary systems (delivery dispatch, drive-thru timing, P2P apps, streaming, package carriers) vary by company →
  "typically", never "X company does Y". **No brand names, logos, store names or app UIs** in 3D or text unless a
  claim is clearly sourced and Irfan approves.

**Safety / policy**
- Money topics (cards, PIN, P2P, ATM) explain **why it's secure** and common-sense safety, never how to defeat it
  (no skimming/cloning/scam how-to). P2P: no financial advice.
- 911 topic: accurate, calm, no "you can always be found" over-promise. Appliance/electric topics: no DIY repair
  steps (refrigerant, gas furnace, mains, microwave internals); CO-alarm line where relevant.
- **AI label ON on every post**, Public, hashtags, engagement comment as the Page (WJH checklist).
- **Posting = Graph API only** (no Chrome UI): reel upload with `is_ai_generated` set → FB shows the "AI info"
  label (confirmed by the chief, 24 Nov 2026). Reuse the WJH tools (`tools/fb_schedule_reel.py`, `tools/page_comment.py`)
  with the Everyday Decoded Page ID/token from that laptop's `.env`; scheduled via the API at the ET slots (3.7).
  After the first post, check once on the live reel that the AI info label shows.
- Original visuals only; reference reels = style study.

**Production**
- **One-shot renderer not built yet** (shared dependency with Page 2) → Page 3 can't produce until it exists.
- **4 GB VRAM + render speed unproven.** 5 reels × ~90 s × 30 fps ≈ 13,500 frames/day. The Mac v2 rate
  (1.2–4 s/frame per process) won't fit on one laptop → benchmark laptop #2 first: Cycles GPU (OptiX, low samples +
  denoise) vs EEVEE at 1080×1920; target **≤ ~1.5 s/frame** (≈ 5.5–6 h/day) before promising 5/day. Start at 2/day.
- **Claude quota.** Page 2's plan estimates 3 Pages × 5/day ≈ half the weekly Max quota; one Fable-heavy video ≈ 5 %
  of weekly Fable. Page 3 is **evergreen** → write + fact-check scripts in **weekly batches** (one Fable run for
  ~10 scripts), Opus builds, Fable spot-checks final QC sheets. Measure after week 1.
- Laptop stays awake, lid open; the new Page's token in that laptop's `.env` only.

## 7b. Windows laptop port (laptop #2: Intel i5, RTX 3050 ~4 GB VRAM)

The pipeline was written on the Mac. Before Page 3 can run, it must be ported. **Do the port ONCE, shared with Page 2
(laptop #1, same hardware)**, in the shared `pipeline/` code — not as a Page 3 fork. Mac-specific things found in
`pipeline/` + `tools/` (grep, 24 Nov 2026):

| Mac-specific | Windows fix |
|---|---|
| `.venv/bin/python` (22 places in docs/scripts) | `.venv\Scripts\python.exe`; scripts call `sys.executable` instead of hard-coded paths |
| `/Applications/Blender.app/Contents/MacOS/Blender` (5) | `BLENDER_PATH` setting (e.g. `C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`), same Blender version as the Mac |
| Fonts `/System/Library/Fonts/Avenir Next.ttc`, DIN Condensed, Arial Bold/Black | **Font resolver** with per-Page font settings: on the Mac, WJH keeps Avenir/DIN exactly as today; other Pages (and any machine without them) use open-licence fonts **committed in the repo** (`assets/fonts/`, e.g. Montserrat / Inter / Barlow Condensed). Avenir Next is a commercial Mac font, so it is never copied into the repo |
| `libx265` encode (CPU, slow on an i5) | prefer **`hevc_nvenc`** (RTX 3050) with an `hvc1` tag + the same < 10 MB check; fall back to libx265 |
| shell bits (`sed`, `/tmp`, `&` background jobs) | Python `pathlib`/`subprocess`, `tempfile`; long jobs run in the background through Claude Code |
| path joins with `/`, file names with spaces (`"<keyword> fb.mp4"`) | `pathlib` everywhere; quote paths; avoid `:` and other characters that are illegal on Windows in file names |

**Code delivery (Irfan, 24 Nov 2026): the laptop clones the GitHub repo `finest1119/irfan` (same branch as the
Mac) and updates with `git pull`.** Consequences:
- Page 3 work lives in `irfan/page3/` (worlds, builders, episode specs, Page config). Changes to shared `pipeline/`
  / `tools/` must be **cross-platform and backward compatible with WJH on the Mac**: new behaviour behind options
  or per-Page config (e.g. `--mode oneshot`, `page.json` with fonts/palette/voice); defaults = today's WJH
  behaviour; machine paths from env/config (`BLENDER_PATH`, `FFMPEG`), never hard-coded. Before pushing a shared
  change: re-render a WJH still on the Mac and compare (same pixels/caption look).
- Not in git (each laptop creates its own): `.env` (GEMINI_API_KEY + **that laptop's own** FB_PAGE_ID /
  FB_PAGE_TOKEN), `.venv`, Poly Haven assets (download script from its README), `output/`, render frames.
- Generated big files stay out of git (`.gitignore` covers `output/`, frames, assets); only specs, code, small
  textures/logos are committed. Commit/push only Page 3 files + reviewed shared changes; WJH files untouched.
- Line endings: add `.gitattributes` (`* text=auto`, `*.py eol=lf`) so Windows checkouts don't churn diffs.
- Two machines push to one branch → always `git pull --rebase` before work and before push; Page sessions never
  edit each other's folders, so conflicts stay in shared `pipeline/` only.

**Setup checklist (day 1):** Claude Code (same account) · Git + GitHub login · `git clone` finest1119/irfan,
check out the same branch · Python 3.11 + `.venv` (`google-genai faster-whisper python-dotenv pillow numpy`) ·
Blender 5.3 · ffmpeg full build (with nvenc) on PATH · Codex CLI (for `tools/gen_image.py`; same account) ·
latest NVIDIA Studio driver · Poly Haven assets downloaded · `.env` typed by Irfan (never committed or printed).

**Scheduling on Windows:** Claude scheduled tasks on that laptop (daily batch build, auto engagement comment) or
Windows Task Scheduler for non-LLM steps (render queue, posting via Graph API). Power: "never sleep" on AC, lid
close = do nothing, plugged in, good ventilation (laptop GPU throttles when hot).

**4 GB VRAM budget (rules for every Page 3 world):**
- Instanced houses/trees/cars/lamp posts; low-poly + normal maps; **textures ≤ 2K** (1K for far objects); HDRI 2K.
- **Visibility culling by camera position**: interiors (W2 macro sets, W3 rooms) and far districts are hidden
  when the camera is not near them — the one-shot timeline knows where the camera is at every frame.
- One Blender GPU process at a time (not 3 like the Mac); CPU does overlays/assembly in parallel.
- Cycles GPU (OptiX) at low samples + OptiX denoiser **vs** EEVEE → choose by the benchmark below; if VRAM
  runs out, Cycles can fall back to CPU (slow) → treat that as a failed benchmark, simplify the scene.
- Whisper on CPU (`int8`) to keep VRAM free for Blender.

**Benchmark gate (before any promise of 5/day):** render a 10 s one-shot test in W1 (city + house dive) at
1080×1920 → s/frame, peak VRAM, GPU temperature, full-episode time. 5 reels × ~90 s × 30 fps ≈ 13,500 frames/day
→ needs **≤ ~1.5 s/frame** for ~5.5–6 h/day. If slower: 2–3/day, lower samples, or render at 24 fps.

## 7c. QC triage rule (Irfan via chief, 24 Nov 2026; all Pages, saves tokens)

Irfan: "kalau macam ada very small error kan bila QC tu, aku rasa maybe tak perlu nak repair lah kot."

- **MUST FIX:** wrong or fabricated facts and narration; on-screen typos and wrong numbers; broken, black or
  frozen frames, and flicker; audio glitches; pauses over ~1.2 s; unreadable text; policy risk; caption and
  AI-label problems.
- **SKIP (log in the episode's QC notes, no repair):** tiny artifacts under ~1 s; Whisper mishearing when the
  audio itself sounds fine; pauses of 0.75–1.2 s; cosmetic imperfections and optional upgrades.
- **Plan checkers** (`tools/plan_all.py`, `qc_oneshot`): fix PROBLEM lines (errors); log `warn` lines that are
  cosmetic and don't iterate on them.

## 8. Decisions (Irfan, 24 Nov 2026 — ALL recommendations approved)
1. Page name: **Everyday Decoded**.
2. Voice: **fixed Gemini Sadaltager** (one host voice, no rotation).
3. Guide element: **the Spark** (teal orb the camera follows) — yes.
4. Palette: **charcoal #1B1F24 / teal #00B3A4 / amber #FFB000** (matches logo C).
5. Length: **75–100 s**.
6. First world: **W1 Hometown USA + W3 cut-away house** in one scene.
7. Ramp-up: **2/day after the render benchmark → 3 → 5**.

## 9. Next steps (after Irfan's choices)
1. ✅ **Everyday Decoded** FB Page LIVE (chief session, 24 Nov 2026): https://www.facebook.com/profile.php?id=61596825063341
   — **Graph API Page ID `1465128156682768`** (= `FB_PAGE_ID` in the Windows laptop's `.env`; the profile-URL id
   61596825063341 is different). Logo C + cover A, bio, contact email, intro post (Public, pinned), Monetisation
   "Notify me" done — details in `irfan/page3/PAGE-SETUP-REPORT.md`. ✅ **Page token DONE (24 Nov 2026):**
   generated by Irfan in Graph API Explorer (app "ft"), saved in `irfan/page3/.env` (gitignored). Verified via
   Graph API: type PAGE, valid, never expires, all 6 scopes. Copy `page3/.env` into the Windows laptop's `.env` at setup.
2. Windows laptop #2 setup (as Page 2 PLAN section 6) + render benchmark.
3. Shared one-shot renderer (with Page 2) → Page 3 worlds W1+W3 (Opus), Spark + dive helpers.
4. Fable batch: first 10 scripts (spread across worlds) → pilot reel → Irfan approves the look → schedule.

## 10. Progress log
- **24 Nov 2026 — Batch 01 scripts DONE** (Fable 5.2, 2+ sources each, planner-reviewed, 2 fixes): `scripts/01..10`
  (5G, Wi-Fi vs microwave, tap-to-pay, barcode/gum 1974, central AC, microwave door mesh, water tower, traffic-light
  loop, GPS + Einstein, streaming), 256–278 words, review in `scripts/BATCH-01-REVIEW.md`. Re-check facts on
  posting day (SOP).
- **24 Nov 2026 — Offline prep DONE** (Opus 5.5, no Blender): `WORLDS-SPEC.md` (37 stop anchors W1/W2/W3, Spark,
  camera-move library, 4 GB VRAM budget, build order), `page.json` (Page config, no secrets), `tools/make_episode.py`
  (script JSON → v2 `episode.json` + `oneshot` block, validator incl. brand blocklist; 18 tests pass; all 10 scripts
  pass), `BUILD-LOG.md`. Sample episode `episodes/…-c5-water-tower-sample` has placeholder sources — never post.
- **Blocked on shared work:** one-shot renderer (`ed_oneshot`/`--mode oneshot`), per-Page caption highlight colour +
  TWIST card style + font resolver in `pipeline/overlay_v2.py`, Windows laptop setup + benchmark.


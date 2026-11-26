# Track A batch 02: three ED reels on Page 1379706781903422 (target: post 28 Nov 2026, 12:00 / 17:00 / 20:00 ET)

Made with the v2 pipeline (multi-shot, `pipeline/make_episode.py`), ED overlay style block
(`"style": {"font_set": "montserrat", "highlight_color": "#FFB000", "twist_card": {"bg": "#FFB000", "fg": "#1B1F24"}}`),
ED cover (`--style ed`). US English, US units. Narration ~37-43 s (synthetic 175 wpm timings). Voice Sadaltager,
ED director notes. Fact status: first pass from web searches (26 Nov, two sources each); the Fable fact-check
re-verifies against the cited sources before the voice is generated.


---

## ed-2026-11-28-1 (12:00 ET): "Why There's a Metal Mesh in Your Microwave Door"

Episode: `page3/episodes/2026-11-28-ed-b1-microwave-mesh/episode.json` (keyword "microwave mesh", slug `microwave-mesh`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | There's a metal screen hidden in your microwave door. It's why you can watch your food cook. | `mw_kitchen_v2` view "hook" {"_still": 0.6} | card "WHY THE DOTS?" |
| 2 | magnetron | Inside, a part called a magnetron makes microwaves, an invisible kind of radio wave. | `mw_kitchen_v2` view "inside" {"wave_cue": "microwaves", "_still": 0.75} | label "MAGNETRON" @magnetron; chips INVISIBLE · RADIO WAVE |
| 3 | bounce | Metal walls reflect them, so they bounce around until your food soaks them up. | `mw_kitchen_v2` view "bounce" {"_still": 0.6} | label "METAL WALLS REFLECT" @wall; label "FOOD SOAKS THEM UP" @food |
| 4 | water | They make the water molecules in your food vibrate, and that motion turns into heat. | `mw_kitchen_v2` view "water" {"heat_cue": "heat", "_still": 0.85} | label "WATER MOLECULE" @molecule; chips VIBRATE · HEAT |
| 5 | twist | Here's the trick. These microwaves are nearly five inches long. The holes are tiny, so almost none get out. | `mw_kitchen_v2` view "mesh" {"_still": 0.7} | label "WAVE: ABOUT 5 IN" @wave; label "TINY HOLES" @holes; card twist "TOO BIG TO FIT THROUGH" |
| 6 | light | Visible light waves are thousands of times smaller than the holes, so light slips through. You see in, the microwaves stay in. | `mw_kitchen_v2` view "light" {"_still": 0.6} | label "LIGHT GETS OUT" @light; chips LIGHT OUT · MICROWAVES IN |
| 7 | outro | Do you watch your food spin, or walk away? Tell us below. | `mw_kitchen_v2` view "outro" | card "WATCH OR WALK AWAY?" / "Tell us below" |

Facts (soft on screen):
- A magnetron makes the microwaves; they are reflected by the metal interior and absorbed by the food; they make water
  molecules vibrate, which makes heat. [FDA Microwave Ovens]
- Home ovens run at 2,450 MHz = about 12 cm (12.2 cm = 4.8 in): narration "nearly five inches", label "ABOUT 5 IN".
  [HyperPhysics; Wikipedia Microwave oven]
- Door screen holes about 1 mm (some sources say ~2 mm), far smaller than the wavelength; visible light (~500 nm) is
  about 2,000x smaller than the holes. On screen only "TINY HOLES"; narration "almost none get out" because the screen
  attenuates rather than blocks perfectly (FDA leakage limit 5 mW/cm2 at about 2 in). [HyperPhysics; FDA]
Sources: https://www.fda.gov/radiation-emitting-products/resources-you-radiation-emitting-products/microwave-ovens ·
https://hyperphysics.gsu.edu/hbase/Waves/mwoven.html · https://en.wikipedia.org/wiki/Microwave_oven

Cover hook (<= 8 words, true): setup "There's metal in your microwave door" / payoff "IT KEEPS WAVES IN".
Caption question / engagement: "Do you watch your food spin, or walk away? 1 = I watch every second, 2 = I walk away, 3 = I stand back from it."

New build work: `mw_kitchen_v2` (kitchen lightbox set, countertop microwave with a perforated-screen shader door,
cut-away top / left views, magnetron + waveguide, teal wave packets on bounce paths, H2O molecule models, 12 cm standing
wave, amber light squiggles). No world reuse (indoor set, like batch 01's baggage hall).

---

## ed-2026-11-28-2 (17:00 ET): "A Pack of Gum Changed Every Store in America"

Episode: `page3/episodes/2026-11-28-ed-b2-gum-barcode/episode.json` (keyword "gum barcode", slug `gum-barcode`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Every beep at the checkout goes back to one pack of gum. | `checkout_v2` view "hook" {"_still": 0.7} | card "ONE PACK OF GUM?" |
| 2 | bars | Those black bars aren't a picture. They're a twelve-digit number, written in stripes a machine can read. | `checkout_v2` view "bars" {"_still": 0.6} | label "A 12-DIGIT NUMBER" @code |
| 3 | scan | The scanner sweeps a red laser across the stripes and reads that number back. | `checkout_v2` view "scan" {"_still": 0.6} | label "LASER SCANNER" @scanner; chips STRIPES · NUMBER |
| 4 | lookup | Here's what most people miss. The price usually isn't in the barcode. The store's computer looks the number up and sends the price back. | `checkout_v2` view "lookup" {"send_cue": "looks", "back_cue": "sends", "_still": 0.85} | card twist "THE PRICE ISN'T IN THE BARS"; label "STORE COMPUTER" @computer |
| 5 | first | The very first scan at a real checkout was June 26, 1974, at a Marsh supermarket in Troy, Ohio. The item: a ten-pack of Juicy Fruit gum. | `checkout_v2` view "first" {"scan_cue": "item", "_still": 0.8} | label "JUNE 26, 1974 · TROY, OHIO" @gum; chips 10-PACK OF GUM |
| 6 | today | Now that same idea is on almost everything you buy. | `checkout_v2` view "today" {"_still": 0.6} | chips ALMOST EVERYTHING |
| 7 | outro | Self-checkout or a cashier? Tell us below. | `checkout_v2` view "outro" | card "SELF-CHECKOUT OR CASHIER?" / "Tell us below" |

Facts (soft on screen):
- First UPC scan at a retail checkout: June 26, 1974, 8:01 a.m., Marsh Supermarket, Troy, Ohio; a 10-pack (50 sticks)
  of Wrigley's Juicy Fruit gum (rang up 67 cents). Brand named once in narration as historical fact, never shown (pack
  is a plain yellow block, no logo). [HISTORY.com; Wikipedia UPC; Ideastream]
- UPC-A = 12 digits shown as bars (last digit a check digit); a laser scanner reads it. [Wikipedia UPC; HISTORY.com]
- The standard UPC holds no price; the store computer looks the number up ("usually" in narration: variable-weight
  store codes can carry a price). [Montana Dept. of Agriculture UPC basics; Wikipedia UPC]
Sources: https://www.history.com/this-day-in-history/june-26/barcode-scanner-invention-first-use ·
https://en.wikipedia.org/wiki/Universal_Product_Code ·
https://www.ideastream.org/2024-06-25/50-years-ago-the-first-retail-barcode-was-scanned-at-an-ohio-grocery-store ·
https://agr.mt.gov/_docs/marketing-docs/sellingtoretail/UPC_Barcode_Basics.pdf

Cover hook: setup "The first barcode ever scanned was" / payoff "A PACK OF GUM".
Caption question / engagement: "Self-checkout or a cashier? 1 = self-checkout every time, 2 = a cashier, please, 3 = whichever line is shorter."

New build work: `checkout_v2` (supermarket set: shelves, three lanes, belts, flush scanner window + red laser fans,
UPC-style label art without digits, data pulses arcing to a back-office computer, warm 1974 lane). The market world
(scene_lib_v2_market) is a financial plaza, so it was not a fit; `belt()` and the laser idea from bag_belt_v2 are reused.

---

## ed-2026-11-28-3 (20:00 ET): "Your Elevator Barely Lifts You: A Hidden Counterweight Does"

Episode: `page3/episodes/2026-11-28-ed-b3-elevator-counterweight/episode.json` (keyword "elevator counterweight", slug `elevator-counterweight`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | In most tall buildings, the elevator motor isn't lifting your whole car. A hidden weight is helping. | `lift_v2` view "hook" {"_still": 0.7} | card "WHO'S LIFTING YOU?" |
| 2 | rig | Your car hangs from steel ropes that loop over a grooved wheel at the top and down to a heavy counterweight. | `lift_v2` view "rig" {"_still": 0.8} | label "GROOVED WHEEL" @sheave; label "COUNTERWEIGHT" @cwt |
| 3 | balance | That counterweight matches the empty car plus about forty to fifty percent of a full load. | `lift_v2` view "balance" {"load_cue": "plus", "_still": 0.85} | label "COUNTERWEIGHT" @cwt; chips EMPTY CAR · + ABOUT 40–50 % OF A FULL LOAD |
| 4 | motor | So the motor mostly moves the difference, like a seesaw with a friend on the other end. | `lift_v2` view "motor" {"_still": 0.6} | label "MOTOR TURNS THE WHEEL" @motor; card twist "IT MOSTLY MOVES THE DIFFERENCE" |
| 5 | pass | As your car rises, the counterweight drops, and they pass each other in the shaft. | `lift_v2` view "pass" {"_still": 0.75} | label "CAR UP" @car; label "WEIGHT DOWN" @cwt |
| 6 | safety | And if a car ever goes too fast, safety brakes clamp onto the rails and stop it. | `lift_v2` view "safety" {"clamp_cue": "clamp", "_still": 0.8} | label "SAFETY BRAKES" @brake; chips CLAMP · STOP |
| 7 | outro | Three floors: stairs or elevator? Tell us below. | `lift_v2` view "outro" | card "STAIRS OR ELEVATOR?" / "Tell us below" |

Facts (soft on screen):
- Counterweight is typically the car's weight plus 40-50 % of its rated load (California caps it at car + 50 %).
  On screen "+ ABOUT 40-50 % OF A FULL LOAD". [Wikipedia Elevator; TK Elevator Counterweights; Cal. Title 8 1604.15]
- Steel ropes run over a deeply grooved pulley (sheave); narration says "grooved wheel" (no "sheave"). [Wikipedia Elevator]
- The counterweight reduces the effort / power the machine needs: narration "the motor mostly moves the difference"
  (softened from "only lifts the difference"; friction and acceleration also count). [TK Elevator; Wikipedia Elevator]
- On overspeed, the governor trips and safety jaws grip the guide rails to stop the car. [TK Elevator Governor; Wikipedia Elevator]
Sources: https://en.wikipedia.org/wiki/Elevator · https://tkelevator.com/us-en/tools/classroom-on-demand/counterweights.html ·
https://www.tkelevator.com/us-en/tools/classroom-on-demand/governor-module.html · https://dir.ca.gov/Title8/1604_15.html

Cover hook: setup "Your elevator barely lifts you. This does:" / payoff "A COUNTERWEIGHT".
Caption question / engagement: "Three floors: stairs or elevator? 1 = stairs, always, 2 = elevator, obviously, 3 = depends what I'm carrying."

New build work: `lift_v2` in the scene_lib_v2_tower city (REUSED world: build_city + hero tower; the explainer tower is
not built, a cream mid-rise stands on its plot with the shaft cut open at the front; traffic on the road through that
plot is removed).

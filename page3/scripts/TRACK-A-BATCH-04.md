# Track A batch 04: five ED reels on Page 1379706781903422 (target date 30 Nov 2026; posting times NOT assigned)

Made with the v2 pipeline (multi-shot, `pipeline/make_episode.py`), ED overlay `style` block, ED cover (`--style ed`).
US English, US units. Narration 35-40 s (synthetic 175 wpm timings; target 33-42 s). Voice Sadaltager + the one-line ED
director notes (`tts`, `style`, `render`, `qc` blocks copied verbatim from c1). Fact status: first pass from web pages
opened on 26 Nov (two or more sources each, listed below); the Fable fact-check re-verifies before the voice is made.
Cues are words of their own beat (checked by script); no cue on a numeral or hyphenated word.

---

## 2026-11-30-ed-d1-cabin-lights: "Why the Cabin Lights Dim When Your Plane Lands"

Episode: `page3/episodes/2026-11-30-ed-d1-cabin-lights/episode.json` (keyword "cabin lights", slug `cabin-lights`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your plane is about to land, and the cabin lights go dim. That's on purpose. | `cabin_lights_v2` view "hook" {"dim_cue": "dim", "_still": 0.5} | card "LIGHTS DOWN FOR LANDING" |
| 2 | eyes | Your eyes need minutes to adjust to the dark. Dimming early gives them a head start. | `cabin_lights_v2` view "dim" {"dim_cue": "dimming", "_still": 0.85} | label "CABIN DIMMED" @aisle; chips EYES ADJUST TO THE DARK |
| 3 | path | So if you ever had to leave in a hurry, the floor lights and exit signs would already stand out. | `cabin_lights_v2` view "path" {"_still": 0.75} | label "FLOOR PATH LIGHTS" @floor; label "EXIT SIGN" @exit |
| 4 | shades | Many airlines also ask for window shades up, so the crew can see outside and choose a safe exit. | `cabin_lights_v2` view "shades" {"shade_cue": "shades", "_still": 0.8} | label "SHADES UP" @shade; chips CREW CAN SEE OUTSIDE |
| 5 | twist | Here's the twist. To be certified, big airliners must show everyone can get out in ninety seconds, in the dark, using only half the exits. | `cabin_lights_v2` view "twist" {"_still": 0.8} | card twist "OUT IN 90 SECONDS"; chips IN THE DARK · ONLY HALF THE EXITS |
| 6 | outro | Window seat or aisle seat: which do you pick? Tell us below. | `cabin_lights_v2` view "outro"  | card "WINDOW OR AISLE?" / "Tell us below" |

Facts (soft on screen; calm, no emergency shown):
- Crews dim the cabin lights for takeoff and landing (especially at night / dusk) so passengers' eyes are already
  adapted to the dark if an evacuation were ever needed; exit signs and floor path lighting then stand out.
  Narration "Your eyes need minutes to adjust" (full dark adaptation takes longer; "minutes" kept soft). [AFAR; Mental Floss]
- Window shades up lets crew and passengers see outside hazards and choose a usable exit. The FAA does not regulate
  shade position (airline policy; EASA / IATA guidance), so narration says "Many airlines also ask". [AFAR window shades]
- Twist: 14 CFR 25.803 / Appendix J: airliners with more than 44 seats must show everyone can be evacuated within 90 s
  (25.803); the demo is in darkness, emergency lighting only, one exit from each exit pair (Appendix J). Narration "big airliners must show
  everyone can get out in ninety seconds, in the dark, using only half the exits". [eCFR 25.803 + Appendix J via Cornell LII]
Sources:
- AFAR, Why Do Airplanes Dim the Cabin Lights During Takeoff and Landing? (eyes adjust in advance for an evacuation; exit and floor path lights easier to see; shades and dimming work together): https://www.afar.com/magazine/why-airplanes-dim-cabin-lights-for-takeoff-and-landing
- Mental Floss, Why Planes Dim Lights During Takeoff and Landing (dark adaptation before a possible evacuation; seeing outside): https://mentalfloss.com/transportation/planes-and-airports/why-planes-dim-lights-during-takeoff-and-landing
- AFAR, Why Do Window Shades Have to Be Open for Takeoff and Landing? (FAA does not regulate shade position; airline policy; crew can see hazards outside; IATA/EASA guidance): https://www.afar.com/magazine/why-do-window-shades-have-to-be-open-for-takeoff-and-landing
- 14 CFR 25.803 (airplanes with more than 44 passenger seats: everyone evacuated to the ground within 90 seconds under simulated emergency conditions): https://www.law.cornell.edu/cfr/text/14/25.803
- 14 CFR Appendix J to Part 25 (demonstration in darkness, only emergency lighting; exits used = one exit from each exit pair, i.e. half): https://www.law.cornell.edu/cfr/text/14/appendix-J_to_part_25

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Why planes dim the lights:" / payoff "YOUR EYES"
- 2. setup "Airliners must empty in" / payoff "90 SECONDS"

Caption question / engagement: "Window seat or aisle seat: which do you pick? 1 = window, always, 2 = aisle, always, 3 = whatever's open."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Aviation #TravelTips #FlyingFacts

New build work: `cabin_lights_v2` = REUSED `scene_lib_v2_air.b_cabin_v2` cabin, re-lit in memory (dusk
windows, ceiling / LED cove / area lights fade on dim_cue), floor path light strips, green exit sign with a white door +
arrow pictogram (no text), window shades that slide up row by row (shade_cue).

---

## 2026-11-30-ed-d2-bananas: "The Bananas at Your Store Were Picked Green, Then Ripened on Purpose"

Episode: `page3/episodes/2026-11-30-ed-d2-bananas/episode.json` (keyword "bananas", slug `bananas`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Those yellow bananas at your store were picked green, on purpose. | `banana_ripen_v2` view "hook" {"_still": 0.6} | card "PICKED GREEN" |
| 2 | green | Growers cut them while they're still hard and green, so they survive the long trip. | `banana_ripen_v2` view "box" {"_still": 0.7} | label "STILL GREEN" @bunch; chips SURVIVES THE TRIP |
| 3 | cool | They ride in cool containers, around fifty-five degrees, so they don't ripen on the way. | `banana_ripen_v2` view "ship" {"_still": 0.75} | label "COOL CONTAINER" @boxes; chips ABOUT 55°F |
| 4 | room | Near your city, they go into sealed ripening rooms, and a little ethylene gas is added. | `banana_ripen_v2` view "room" {"gas_cue": "ethylene", "_still": 0.85} | label "RIPENING ROOM" @room; chips ETHYLENE GAS |
| 5 | twist | Here's the twist. Ethylene is a natural plant hormone. Bananas make it themselves, and the room just starts them all at once. | `banana_ripen_v2` view "twist" {"_still": 0.7} | card twist "BANANAS MAKE IT TOO"; chips NATURAL PLANT HORMONE |
| 6 | yellow | A few days later, they turn yellow together and head to the shelf. | `banana_ripen_v2` view "yellow" {"ripen_cue": "yellow", "_still": 0.85} | label "READY FOR THE SHELF" @bunch; chips A FEW DAYS (check) |
| 7 | outro | Green, yellow, or spotty: how do you like yours? Tell us below. | `banana_ripen_v2` view "outro"  | card "GREEN, YELLOW OR SPOTTY?" / "Tell us below" |

Facts (non-alarming tone; soft numbers):
- Bananas are harvested mature-green (fruit ripened on the plant splits and has poor texture) and shipped green under
  refrigeration at a pulp temperature of about 56-58 F (13-14 C); narration "around fifty-five degrees" (reefers at about 13 C / 55 F),
  chip "ABOUT 55°F". [Geography of Transport Systems; UC Davis (page 403, search summary only)]
- Near the market they go into sealed ripening rooms where ethylene starts ripening (room filled for about a day,
  then vented; dose figures differ by source, none on screen); ripe in 3-4 days -> "A few days later". [GTS; Wikipedia]
- Ethylene is a natural plant hormone; bananas produce and respond to it. Not used: the "paper bag" home tip (disputed
  by a Michigan State postharvest physiologist). [Wikipedia Ethylene as a plant hormone; GTS]
Sources:
- The Geography of Transport Systems, Banana Ripening Room (picked and shipped green in reefers at about 13 C / 55 F; sealed ripening room at about 17 C filled with ethylene, a natural ripening agent, then vented; ripe in three to four days): https://transportgeography.org/contents/applications/cold-chain-logistics/banana-ripening-room/
- Wikipedia, Ethylene as a plant hormone (a naturally occurring plant hormone that drives fruit ripening; bananas release it; commercial ripening rooms generate ethylene gas): https://en.wikipedia.org/wiki/Ethylene_as_a_plant_hormone
- UC Davis Postharvest Center, Banana (mature-green harvest; shipping 13-14 C / 56-58 F) - search summary only, page returned 403 on 26 Nov: https://postharvest.ucdavis.edu/node/5196

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Your store bananas were picked" / payoff "GREEN"
- 2. setup "Bananas ripen in rooms with" / payoff "ETHYLENE GAS"

Caption question / engagement: "Green, yellow, or spotty: how do you like yours? 1 = a little green, 2 = perfectly yellow, 3 = spotty and sweet."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Bananas #FoodFacts #Science

New build work: `banana_ripen_v2`: banana-hand mesh (curved fingers + crown, green -> yellow peel mix),
REUSED supermarket set (`_store`) with a tiered produce display; refrigerated container (ribbed walls, cool light,
carton stacks with open tops); ripening room (insulated panels, roll door, duct + fans, wall nozzle) with soft teal gas puffs
and wisps, peels ramp to yellow on ripen_cue.

---

## 2026-11-30-ed-d3-toll-tag: "You Drive Through a Toll at Highway Speed and Never Stop"

Episode: `page3/episodes/2026-11-30-ed-d3-toll-tag/episode.json` (keyword "toll tag", slug `toll-tag`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | You drive under a toll at highway speed, never stop, and still pay. | `toll_tag_v2` view "hook" {"_still": 0.55} | card "NO STOPPING?" |
| 2 | tag | That little tag on your windshield is a radio ID, like a tiny name badge for your car. | `toll_tag_v2` view "tag" {"_still": 0.7} | label "TOLL TAG" @tag; chips RADIO ID |
| 3 | read | As you pass, a reader on the overhead gantry pings it, and the tag answers with its ID. | `toll_tag_v2` view "read" {"ping_cue": "pings", "_still": 0.66} | label "READER" @reader; chips PING · ANSWER |
| 4 | charge | The toll is matched to your account and charged automatically. | `toll_tag_v2` view "charge" {"send_cue": "matched", "_still": 0.8} | label "TOLL SYSTEM" @cabinet; chips ACCOUNT CHARGED (check) |
| 5 | twist | Here's the twist. Many sticker tags have no battery. The reader's radio signal powers them for that instant. | `toll_tag_v2` view "sticker" {"power_cue": "powers", "_still": 0.85} | card twist "NO BATTERY NEEDED"; chips POWERED BY THE READER |
| 6 | cams | No tag? Cameras snap your license plate, and the bill comes by mail. | `toll_tag_v2` view "cams" {"flash_cue": "snap", "_still": 0.36} | label "PLATE CAMERA" @cam; chips BILL BY MAIL |
| 7 | outro | Tag on the windshield or bill by mail: which are you? Tell us below. | `toll_tag_v2` view "outro"  | card "TAG OR BILL BY MAIL?" / "Tell us below" |

Facts:
- Electronic toll tags (E-ZPass and others) are RFID-type windshield transponders; an antenna on the gantry reads the
  tag's ID as the car passes at highway speed and the toll is charged to the linked account. [Wikipedia E-ZPass]
- No tag (or no read): cameras photograph the license plate; owner billed (E-ZPass article: Mass Pike, Pennsylvania).
  "Comes by mail" = usual toll-by-mail practice (Bestpass, search summary only). [Wikipedia E-ZPass]
- Twist: many sticker tags are passive RFID with no battery, powered by the reader's radio energy (e.g. SunPass Mini;
  the classic hard-case E-ZPass tag is battery-powered) -> narration "Many sticker tags have no battery".
  [Wikipedia SunPass; Wikipedia RFID]
- Speed in the shots ~58 mph (26 m/s). "Highway speed" is soft (some gantries are open-road tolling, others lower speed).
Sources:
- Wikipedia, E-ZPass (RFID transponder read at lane-based or open-road toll points; prepaid account debited; vehicles without a transponder are photographed by plate and the owner billed): https://en.wikipedia.org/wiki/E-ZPass
- Wikipedia, SunPass (SunPass Mini: passive RFID sticker transponder, uses no batteries): https://en.wikipedia.org/wiki/SunPass
- Wikipedia, Radio-frequency identification (passive tags are powered by energy from the reader's interrogating radio waves): https://en.wikipedia.org/wiki/Radio-frequency_identification

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "No stopping at the toll:" / payoff "RADIO ID"
- 2. setup "Many toll stickers have" / payoff "NO BATTERY"

Caption question / engagement: "Tag on the windshield or bill by mail: which are you? 1 = tag, always, 2 = bill by mail, 3 = I avoid toll roads."
Hashtags: #EverydayDecoded #HowItWorks #Explained #RoadTrip #Driving #Tech

New build work: `toll_tag_v2` in the REUSED scene_lib_v2_tower city (+ hero tower): the y = -60 avenue as a
4-lane one-way road with dashes, box-truss gantry with reader panels + plate cameras, roadside cabinet, Kenney traffic at
26 m/s; driver's-eye rig (dash, pillars, mirror, tag behind the mirror; no glass); sticker tag with an antenna coil that lights on
power_cue; teal read zone + rings, amber answer / data pulses, camera flash + plate rings.

---

## 2026-11-30-ed-d4-glove-screen: "Your Phone Screen Can't Feel a Glove"

Episode: `page3/episodes/2026-11-30-ed-d4-glove-screen/episode.json` (keyword "glove screen", slug `glove-screen`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your phone ignores you the moment you put on winter gloves. Here's why. | `glove_touch_v2` view "hook" {"_still": 0.7} | card "WHY GLOVES FAIL" |
| 2 | grid | Under the glass sits an invisible grid of tiny electrodes, holding a small electric field. | `glove_touch_v2` view "grid" {"grid_cue": "grid", "_still": 0.85} | label "SENSOR GRID" @grid; chips SMALL ELECTRIC FIELD |
| 3 | touch | Your fingertip conducts electricity, so it changes the charge where you touch, and the phone pinpoints it. | `glove_touch_v2` view "touch" {"touch_cue": "changes", "_still": 0.85} | label "CHARGE CHANGES HERE" @tip; chips SKIN CONDUCTS |
| 4 | glove | A regular glove is an insulator. It blocks that change, so the screen feels nothing. | `glove_touch_v2` view "glove" {"touch_cue": "blocks", "_still": 0.85} | label "NOTHING REGISTERS" @tip; chips GLOVES INSULATE |
| 5 | twist | Here's the trick. Touchscreen gloves weave conductive thread into the fingertip, so it acts like bare skin. | `glove_touch_v2` view "thread" {"touch_cue": "acts", "_still": 0.85} | card twist "CONDUCTIVE THREAD"; label "THREAD IN THE TIP" @tip |
| 6 | outro | Do you take your gloves off, or own a touchscreen pair? Tell us below. | `glove_touch_v2` view "outro"  | card "GLOVES OFF OR ON?" / "Tell us below" |

Facts:
- Phone screens are capacitive: a grid of crossing conductors under the glass; a finger disturbs the electric field and
  changes the capacitance there, which the controller detects. [Wikipedia Touchscreen; Nelson Miller]
- Ordinary gloves are insulators, so the change doesn't happen and the touch isn't registered. [Wikipedia Touchscreen; Nelson Miller]
- Touchscreen gloves weave conductive material (often copper yarn) into the fingertip, which then acts like a
  bare finger -> "so it acts like bare skin". [Gear Patrol]
Sources:
- Wikipedia, Touchscreen (capacitive: grid of crossing conductors; a finger disturbs the electric field and changes the capacitance, which the controller detects; some capacitive screens cannot detect a finger through insulating material such as gloves): https://en.wikipedia.org/wiki/Touchscreen
- Nelson Miller, Why Can't I Wear Gloves With My Touchscreen? (a bare finger draws off some of the screen's charge and the change in capacitance is read as a touch; gloves restrict that flow): https://nelson-miller.com/why-cant-i-wear-gloves-with-my-touchscreen
- Gear Patrol, The Science Behind Touchscreen Gloves (conductive material, most often copper yarn, woven into the fingertip acts as a bare finger): https://www.gearpatrol.com/outdoors/smartphone-compatible-gloves-explained/

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Your phone can't feel your" / payoff "GLOVES"
- 2. setup "The trick inside touchscreen gloves:" / payoff "CONDUCTIVE THREAD"

Caption question / engagement: "Do you take your gloves off, or own a touchscreen pair? 1 = gloves off every time, 2 = touchscreen gloves, 3 = I just wait until I'm inside."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Smartphone #WinterHacks #Tech

New build work: `glove_touch_v2` in the REUSED living-room set: phone on a stand (home-screen art, no text),
teal electrode grid over the screen, pointing-hand mesh (skin / knit glove / glove with a silver thread tip), amber
touch dot + crossing grid lines + rings at the touch point.

---

## 2026-11-30-ed-d5-qr-code: "A QR Code Can Still Scan With Part of It Missing"

Episode: `page3/episodes/2026-11-30-ed-d5-qr-code/episode.json` (keyword "qr code", slug `qr-code`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | A QR code can still scan with a chunk of it missing. Here's how. | `qr_code_v2` view "hook" {"_still": 0.7} | card "MISSING A PIECE?" |
| 2 | data | Those little squares hold your link, plus extra recovery data worked out with clever math. | `qr_code_v2` view "data" {"_still": 0.8} | label "LINK + RECOVERY DATA" @code; chips BUILT-IN BACKUP |
| 3 | damage | If a smudge or a tear covers part of it, your phone uses that data to fill in the gaps. | `qr_code_v2` view "damage" {"damage_cue": "tear", "scan_cue": "fill", "_still": 0.9} | label "TORN PATCH" @patch; chips STILL SCANS (check) |
| 4 | twist | Here's the twist. At the highest setting, up to about thirty percent can be restored. | `qr_code_v2` view "level" {"_still": 0.8} | card twist "UP TO ABOUT 30%"; chips HIGHEST SETTING |
| 5 | corners | Those three big corner squares help your camera find the code and line it up, even upside down. | `qr_code_v2` view "corners" {"finder_cue": "corner", "_still": 0.8} | label "FINDER SQUARES" @finder; chips FIND IT · LINE IT UP |
| 6 | tip | But cover one of those corners, and the scan can fail. | `qr_code_v2` view "tip" {"cover_cue": "cover", "_still": 0.85} | label "CORNER COVERED" @patch |
| 7 | outro | Do you scan QR codes, or type the link yourself? Tell us below. | `qr_code_v2` view "outro"  | card "SCAN IT OR TYPE IT?" / "Tell us below" |

Facts:
- QR codes carry Reed-Solomon error-correction data alongside the content; four levels L / M / Q / H, the highest (H)
  restores about 30% (of codewords per Make Tech Easier; Keyence words it as damaged area) -> narration
  "up to about thirty percent", card "UP TO ABOUT 30%". [Keyence; Seagull BarTender guide]
- The three big corner squares are finder (position detection) patterns: they let the reader find the code fast and
  read it at any orientation -> "even upside down". [Keyence; Seagull]
- Covering a finder pattern can stop a scan even with little area covered -> "the scan can fail" (soft). [Make Tech Easier]
- The code on screen is a QR-LIKE graphic (finders, timing lines, random modules); it is NOT decodable (no link).
Sources:
- Keyence, What is a QR code? (Reed-Solomon code restores data when part of the code is missing or damaged; levels L/M/Q/H, H up to about 30%; position detection patterns at three corners let the reader read it from any angle): https://www.keyence.com/ss/products/auto_id/codereader/basic_2d/qr.jsp
- Seagull Scientific BarTender Barcode Guide, QR Code (finder patterns in three corners allow scanning at any orientation; error correction levels up to about 30%): https://barcodeguide.seagullscientific.com/Content/Symbologies/QR_Code.htm
- Make Tech Easier, How QR Codes Survive Damage (levels restore about 7/15/25/30% of codewords; the three corner squares are landmarks that must survive for the reader to locate the grid, so covering one is riskier): https://maketecheasier.com/how-qr-codes-survive-damage/

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "QR codes can scan while" / payoff "MISSING A CHUNK"
- 2. setup "Up to 30% can be" / payoff "RESTORED"

Caption question / engagement: "Do you scan QR codes, or type the link yourself? 1 = I scan everything, 2 = I type the link, 3 = only restaurant menus."
Hashtags: #EverydayDecoded #HowItWorks #Explained #QRCode #Tech #Smartphone

New build work: `qr_code_v2` in the REUSED supermarket set: framed poster on the side wall (colour blocks + QR-like
code), torn paper patches, amber frames around the finder squares, teal tint for the recovery rows, foreground phone
with camera-view screen art (amber brackets -> teal check badge, or coral cross).

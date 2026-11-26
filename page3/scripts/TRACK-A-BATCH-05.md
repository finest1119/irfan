# Track A batch 05: three ED reels on Page 1379706781903422 (target date 1 Dec 2026; posting times NOT assigned)

Made with the v2 pipeline (multi-shot, `pipeline/make_episode.py`), ED overlay `style` block, ED cover (`--style ed`).
US English, US units. Narration ~39-41 s (synthetic 175 wpm timings; target 32-42 s). Voice Sadaltager + the one-line ED
director notes (`tts`, `style`, `render`, `qc` blocks copied verbatim from d5). TTS lesson applied: every beat is at
least 14 words (no short one-sentence beats, so Gemini does not read the director notes aloud). Fact status: first pass
from web pages opened on 26 Nov (Apple, Google Pixel Help, Battery University, Bose, Illinois Physics Van) plus search summaries (marked) (two or more sources each, listed below); the Fable fact-check re-verifies
before the voice is made. Cues are words of their own beat (checked by script); no cue on a numeral or hyphenated word.

---

## 2026-12-01-ed-e1-fridge-heat: "Your Fridge Doesn't Make Cold, It Moves Heat Into Your Kitchen"

Episode: `page3/episodes/2026-12-01-ed-e1-fridge-heat/episode.json` (keyword "fridge heat", slug `fridge-heat`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your fridge doesn't really make cold. It moves heat out of your food and into your kitchen. | `fridge_heat_v2` view "hook" {"_still": 0.75} | card "IT MOVES HEAT" |
| 2 | inside | Inside, a liquid refrigerant runs through thin tubes and evaporates, soaking up heat from your food. | `fridge_heat_v2` view "inside" {"evap_cue": "evaporates", "heat_cue": "soaking", "_still": 0.85} | label "COLD TUBES" @tubes; chips SOAKS UP HEAT |
| 3 | comp | Then a compressor near the bottom squeezes that gas, which makes it hot, hotter than your kitchen. | `fridge_heat_v2` view "comp" {"comp_cue": "compressor", "squeeze_cue": "squeezes", "_still": 0.85} | label "COMPRESSOR" @comp; chips SQUEEZED GAS GETS HOT |
| 4 | coils | Coils on the back or underneath release that heat into your kitchen, and the refrigerant turns liquid again. | `fridge_heat_v2` view "coils" {"coil_cue": "coils", "release_cue": "release", "_still": 0.7} | label "WARM COILS" @coils; chips HEAT GOES INTO THE ROOM |
| 5 | twist | Here's the twist. An open fridge door won't cool the room. The fridge runs harder, and your kitchen gets warmer. | `fridge_heat_v2` view "twist" {"door_cue": "open", "hard_cue": "harder", "_still": 0.85} | card twist "OPEN DOOR = WARMER KITCHEN"; chips FRIDGE RUNS HARDER |
| 6 | outro | Be honest: how long do you stand at the open fridge hunting for a snack? Tell us below. | `fridge_heat_v2` view "outro"  | card "HOW LONG DO YOU STARE?" / "Tell us below" |

Facts:
- A fridge is a heat pump (vapor-compression cycle): liquid refrigerant evaporates in the evaporator tubes inside and absorbs
  heat from the food and air; the compressor raises the gas pressure and temperature above the room's; the condenser coils
  on the back or underneath release the heat into the kitchen and the refrigerant condenses back to a liquid; an expansion
  device (capillary tube) drops the pressure again. [Danfoss; Sears Home Services; iFixit]
- Narration "squeezes that gas, which makes it hot, hotter than your kitchen" (Sears: hotter than the ambient air).
  "near the bottom" = usual compressor position at the bottom back (soft).
- Twist: with the door open the fridge runs more and, being inefficient, puts more heat into the room than it removes,
  so the room's average temperature rises (sealed-room reasoning; a brief local chill is possible) -> "An open fridge
  door won't cool the room ... your kitchen gets warmer". [University of Illinois Physics Van]
Sources:
- (search summary only, not opened) Danfoss, How a refrigerator works - basic training (refrigerant evaporates in the evaporator and absorbs heat from inside; the compressor raises pressure and temperature; the condenser releases the heat outside the cabinet): https://www.danfoss.com/en-us/service-and-support/fix-and-troubleshooting/air-condition-and-refrigeration-installer-hub/the-fridge-how-it-works/
- (search summary only, not opened) Sears Home Services, How Does a Refrigerator Work? (compressor makes the refrigerant hotter than the room air; condenser coils on the back or underneath release the heat and the refrigerant turns back into a liquid; evaporator absorbs heat inside): https://www.searshomeservices.com/blog/how-does-a-refrigerator-work
- (search summary only, not opened) iFixit, How Does a Refrigerator Work? (vapor-compression cycle: evaporator, compressor, condenser coils, expansion device): https://www.ifixit.com/Wiki/How_a_Refrigerator_Works
- University of Illinois Physics Van, Open Refrigerator (the fridge is a heat pump; with the door open it runs more and puts more heat into the room than it removes, so the room's average temperature rises): https://van.physics.illinois.edu/ask/listing/1790

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Your fridge pushes heat into your" / payoff "KITCHEN"
- 2. setup "An open fridge makes your kitchen" / payoff "WARMER"

Caption question / engagement: "Be honest: how long do you stand at the open fridge hunting for a snack? 1 = in and out in seconds, 2 = a good minute, 3 = until someone tells me to close it."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Kitchen #Science #HomeHacks

New build work: `fridge_heat_v2` in the REUSED mw_kitchen_v2 set (`_kitchen`): freestanding fridge-freezer (no logo) at the left
wall end facing +X: shell, insulation section, liner, glass shelves, food, door bins, hinged doors; evaporator serpentine
(teal glow sleeve + cold dots) on the inner back; compressor dome at the bottom back (amber glow + rings); condenser coil
with wire fins on the outside back (amber glow, hot dots); copper suction / discharge / capillary lines; amber heat puffs
behind / under the fridge, teal cold puffs out of the open door. comp view removes the near side panel (cut-away);
coils view deletes the left room wall faces and adds a floor strip so the camera sees the back from outside.

---

## 2026-12-01-ed-e2-noise-cancelling: "Noise-Cancelling Headphones Fight Sound With Sound"

Episode: `page3/episodes/2026-12-01-ed-e2-noise-cancelling/episode.json` (keyword "noise cancelling", slug `noise-cancelling`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Noise-cancelling headphones don't just block outside sound. They actually fight sound with more sound. | `noise_cancel_v2` view "hook" {"_still": 0.7} | card "SOUND VS. SOUND" |
| 2 | mics | Tiny microphones on the ear cups listen to the noise around you, like the hum of an air conditioner. | `noise_cancel_v2` view "mics" {"mic_cue": "microphones", "_still": 0.8} | label "MICROPHONE" @mic; chips HEARS THE HUM |
| 3 | chip | A chip inside makes a matching sound wave, flipped upside down, and plays it through the speakers. | `noise_cancel_v2` view "chip" {"chip_cue": "flipped", "_still": 0.8} | label "FLIPPED WAVE" @anti; chips MADE BY A CHIP |
| 4 | cancel | When the two waves meet, the peaks fill the dips, so much of that hum cancels out. | `noise_cancel_v2` view "cancel" {"cancel_cue": "cancels", "_still": 0.92} | label "HUM CANCELS" @ear; chips PEAKS FILL THE DIPS |
| 5 | twist | Here's the twist. It works best on steady, low hums. Voices are higher and keep changing, so more gets through. | `noise_cancel_v2` view "twist" {"voice_cue": "voices", "_still": 0.85} | card twist "VOICES GET THROUGH"; chips BEST ON STEADY HUMS |
| 6 | outro | Where do you wear yours the most: on a plane, on your commute, or at your desk? Tell us below. | `noise_cancel_v2` view "outro"  | card "PLANE, COMMUTE OR DESK?" / "Tell us below" |

Facts:
- Active noise cancelling: microphones on the headphones pick up outside noise; the electronics make a wave with the
  opposite phase ("flipped upside down") and play it through the speakers; the waves cancel. [Bose; Sennheiser]
- Works best on steady, low-frequency sound such as air-conditioner or engine hum; less effective on higher-frequency,
  changing sounds like people talking (ear-cup seal does more of that work) -> "Voices are higher and keep changing, so
  more gets through"; "much of that hum cancels out" kept soft (not all). [Bose; Sennheiser ANC performance]
- "Tiny microphones on the ear cups" (Bose: two microphones; most models have several).
Sources:
- Bose, What is active noise cancellation? (microphones read the sounds around you, the headphones produce opposite signals to cancel them; works best on steady low-frequency sounds such as an air conditioner's hum; less effective on sudden, sharp sounds; mid and high frequencies reduced less): https://www.bose.com/stories/what-is-active-noise-cancellation
- (search summary only, not opened) Sennheiser support, What is Active Noise Cancelling (microphones pick up outside noise; the electronics create a wave with the opposite phase; the waves cancel): https://support.sennheiser-hearing.com/hc/en-at/articles/34973151457565-What-is-Active-Noise-Cancelling
- (search summary only, not opened) Sennheiser support, How ANC and passive isolation work (ANC works best on repetitive low-frequency noise such as engine or air-conditioning hum, less effective on higher-frequency sounds like people talking): https://support.sennheiser-hearing.com/hc/en-gb/articles/38785026673181-What-impacts-ANC-Active-Noise-Cancellation-performance-in-Headband-headphones

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Noise-cancelling headphones fight sound with" / payoff "SOUND"
- 2. setup "Noise-cancelling headphones work best on" / payoff "LOW HUMS"

Caption question / engagement: "Where do you wear yours the most? 1 = on a plane, 2 = on my commute, 3 = at my desk."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Headphones #Tech #TravelTips

New build work: `noise_cancel_v2` in the REUSED living-room set (`_living_room`, books hidden) + a window AC unit (no text):
ivory over-ear headphones on a walnut stand on the coffee table (mic grills on the cups), waves as flat 3D ribbons read by
a camera looking -Y over the navy sofa: amber hum travelling into the left cup, teal flipped wave (chip_cue), both flatten on
cancel_cue + white flat line, coral jagged voice wave on voice_cue (hum stays flat).

---

## 2026-12-01-ed-e3-phone-charging: "Why Your Phone Charges Slower After About 80 Percent"

Episode: `page3/episodes/2026-12-01-ed-e3-phone-charging/episode.json` (keyword "phone charging", slug `phone-charging`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your phone races to about eighty percent, then crawls the rest of the way. That's on purpose. | `phone_charge_v2` view "hook" {"_still": 0.75} | card "WHY IT SLOWS DOWN" |
| 2 | fast | At first, the charger pushes a strong, steady current, and the battery fills up really fast. | `phone_charge_v2` view "fast" {"fast_cue": "strong", "_still": 0.8} | label "FAST PHASE" @battery; chips STEADY CURRENT |
| 3 | slow | Near full, the battery hits its voltage limit, so the charger holds it there and lets the current taper off. | `phone_charge_v2` view "slow" {"limit_cue": "limit", "taper_cue": "taper", "_still": 0.85} | label "VOLTAGE LIMIT" @battery; chips VOLTAGE HELD · CURRENT TAPERS |
| 4 | twist | Here's the twist. Some phones learn your routine, pause around eighty percent overnight, and finish just before you wake up. | `phone_charge_v2` view "twist" {"pause_cue": "pause", "finish_cue": "finish", "_still": 0.7} | card twist "PAUSED AT ABOUT 80%"; chips FINISHES BEFORE YOU WAKE |
| 5 | why | Sitting at a full charge for hours wears a battery faster, so that pause helps it last longer. | `phone_charge_v2` view "why" {"wear_cue": "wears", "pause_cue": "pause", "_still": 0.9} | label "LESS TIME AT 100%" @battery; chips FULL FOR HOURS = MORE WEAR |
| 6 | outro | Do you charge your phone overnight, or top it up during the day? Tell us below. | `phone_charge_v2` view "outro"  | card "OVERNIGHT OR TOP-UPS?" / "Tell us below" |

Facts:
- Lithium-ion charging is constant current (fast) until the cell reaches its voltage limit, then constant voltage
  ("saturation") while the current tapers off; the switch happens at roughly 70-85 percent depending on the charge rate
  -> "races to about eighty percent", "Near full, the battery hits its voltage limit, so the charger holds it there and
  lets the current taper off". [Battery University BU-409; Analytics Insight]
- Twist: iPhone Optimized Battery Charging learns your daily routine and delays charging past 80 percent when it predicts a
  long charge, finishing before you usually unplug; Pixel Adaptive Charging finishes right before you usually unplug (Google does not state an 80 % hold for it: the soft "Many phones ... around eighty percent" leans on Apple) -> "Many phones learn your
  routine, pause around eighty percent overnight, and finish just before you wake up". [Apple Support; Google Pixel Help]
- "Sitting at a full charge for hours wears a battery faster" (Apple: reduces wear by reducing the time spent fully
  charged). [Apple Support]
Sources:
- Battery University, BU-409: Charging Lithium-ion (stage 1 constant current until the voltage limit, reached at roughly 70-85 percent; stage 2 saturation holds the voltage while the current drops): https://batteryuniversity.com/article/bu-409-charging-lithium-ion
- Apple Support, About Optimized Battery Charging on iPhone (learns your daily charging routine; delays charging past 80 percent when it predicts a long charge, finishing before you unplug, to reduce battery wear from time spent fully charged): https://support.apple.com/en-us/108055
- Google Pixel Help, Get the most life from your Pixel phone battery (Adaptive Charging learns your habits and completes charging right before you typically unplug, so the phone isn't at 100% for a long time; Limit to 80% option): https://support.google.com/pixelphone/answer/6090612
- (search summary only, not opened) Analytics Insight, Why Your Phone Charges Fast at First, Slows Near 80% (CC-CV: the constant-current phase covers roughly 70-80 percent, then voltage is held and current tapers): https://www.analyticsinsight.net/phones/why-your-phone-charges-fast-at-first-slows-near-80

Cover hooks (setup <= 6 words + payoff 1-3 words, <= 8 total, true to the narration):
- 1. setup "Your phone slows charging after about" / payoff "80 PERCENT"
- 2. setup "Pausing at 80% helps your battery" / payoff "LAST LONGER"

Caption question / engagement: "Do you charge your phone overnight, or top it up during the day? 1 = overnight, every night, 2 = quick top-ups, 3 = whenever it turns red."
Hashtags: #EverydayDecoded #HowItWorks #Explained #Smartphone #BatteryTips #Tech

New build work: `phone_charge_v2` in a NEW small bedroom set (`_bedroom`: dusty-blue wall, bed, walnut nightstand, ceramic lamp
with a non-emissive shade, window, art, wall outlet): phone face up (lock-screen art, ring + battery glyph, no text),
white cable to the outlet with teal current dots (dense / sparse / paused), 3D battery gauge graphic beside the phone
(teal fill rises; amber limit line on limit_cue; amber fill = full for hours in `why`, drops to 80% teal on pause_cue).

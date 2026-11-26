# Track A batch 03: three ED reels on Page 1379706781903422 (target: post 29 Nov 2026, 12:00 / 17:00 / 20:00 ET)

Made with the v2 pipeline (multi-shot, `pipeline/make_episode.py`), ED overlay style block
(`"style": {"font_set": "montserrat", "highlight_color": "#FFB000", "twist_card": {"bg": "#FFB000", "fg": "#1B1F24"}}`),
ED cover (`--style ed`). US English, US units. Narration ~41-43 s (synthetic 175 wpm timings). Voice Sadaltager,
ED director notes (one line, copied verbatim from batch 02). Fact status: first pass from web pages opened on 26 Nov
(two or more sources each, listed below); the Fable fact-check re-verifies against the cited sources before the voice
is generated.


---

## ed-2026-11-29-1 (12:00 ET): "Your Phone's GPS Would Be Off by Miles a Day Without Einstein"

Episode: `page3/episodes/2026-11-29-ed-c1-gps-einstein/episode.json` (keyword "gps einstein", slug `gps-einstein`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your phone's blue dot stays on your street thanks to Albert Einstein. | `gps_sky_v2` view "hook" {"_still": 0.6} | card "YOUR DOT NEEDS EINSTEIN" |
| 2 | sats | It listens to GPS satellites over twelve thousand miles up, each with an atomic clock. | `gps_sky_v2` view "sats" {"_still": 0.75} | label "ABOUT 12,550 MILES UP" @sat; chips ATOMIC CLOCK ON BOARD |
| 3 | timing | It times signals from at least four of them to work out where you are. | `gps_sky_v2` view "timing" {"beam_cue": "signals", "_still": 0.85} | label "YOU ARE HERE" @you; chips 4+ SATELLITES · TRAVEL TIME |
| 4 | twist | Here's the twist. Up there, weaker gravity makes clocks run fast. Speed slows them slightly, but they gain about thirty-eight millionths of a second a day. | `gps_sky_v2` view "clock" {"fast_cue": "fast", "_still": 0.8} | label "SATELLITE CLOCK" @clock; chips GRAVITY: FASTER · SPEED: SLOWER; card twist "THEY GAIN TIME EVERY DAY" |
| 5 | drift | Signals move at light speed, so that adds up. Uncorrected, your dot could drift miles in a day. | `gps_sky_v2` view "drift" {"drift_cue": "drift", "_still": 0.9} | label "WHERE YOU REALLY ARE" @true; label "MILES OFF IN A DAY" @dot; chips ROUGHLY 6 MILES A DAY |
| 6 | fix | So the clocks are tuned to tick slightly slow before launch, and your dot stays put. | `gps_sky_v2` view "fix" {"_still": 0.7} | label "DOT STAYS PUT" @dot; chips TUNED BEFORE LAUNCH (check) |
| 7 | outro | Blue dot or street signs: which do you trust? Tell us below. | `gps_sky_v2` view "outro" | card "BLUE DOT OR STREET SIGNS?" / "Tell us below" |

Facts (soft on screen):
- GPS satellites fly in medium Earth orbit at about 20,200 km (12,550 miles) and circle the Earth twice a day; at
  least four are in view from virtually anywhere. Narration "over twelve thousand miles up", label "ABOUT 12,550 MILES
  UP". [GPS.gov Space Segment; OSU Pogge]
- Each satellite carries an atomic clock; the receiver times the signals from at least 4 satellites. [OSU Pogge; GPS.gov]
- Special relativity (speed) slows the satellite clocks about 7 microseconds/day; general relativity (weaker gravity)
  speeds them up about 45; net about +38 microseconds/day. [OSU Pogge; Wikipedia Error analysis for GPS]
- Uncorrected, position errors would accumulate at about 10 km (about 6 miles) a day. This is a back-of-envelope figure
  (38 µs x speed of light ~ 11 km); narration says "could drift miles in a day", chip "ROUGHLY 6 MILES A DAY".
  [OSU Pogge; Wikipedia]
- The satellite clocks are built to run slightly slow on the ground so they match ground clocks in orbit (receivers
  also apply a small orbit-dependent correction; not narrated). [OSU Pogge; Wikipedia]
Sources: https://archive.gps.gov/systems/gps/space/ · https://www.astronomy.ohio-state.edu/pogge.1/Ast162/Unit5/gps.html ·
https://en.wikipedia.org/wiki/Error_analysis_for_the_Global_Positioning_System
(Same facts as the batch-1 fact-checked script `page3/scripts/09-gps-relativity.json`.)

Cover hook (<= 8 words, true): setup "Without Einstein, your GPS drifts" / payoff "MILES A DAY".
Caption question / engagement: "Blue dot or street signs: which do you trust? 1 = the blue dot, always, 2 = street signs, 3 = both, just in case."

New build work: `gps_sky_v2` in the scene_lib_v2_tower city (REUSED world: `build_city` + `build_hero`, as lift_v2) with
a cafe plaza on the explainer plot (tables, chairs, planters, benches, trees; cars on the y = 60 road removed), phone on
a desk stand (map + blue dot screen art, no labels), stylised satellites (gold bus, blue wings) on two teal orbit arcs,
four teal beams with light pulses, satellite + clock dial (tick bars, no digits) whose hands speed up, blue dot drifting
off over the park with an amber trail.

---

## ed-2026-11-29-2 (17:00 ET): "You Call 911 and Can't Speak. Here's How They Find You"

Episode: `page3/episodes/2026-11-29-ed-c2-911-location/episode.json` (keyword "911 location", slug `911-location`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | You call 911 and can't speak. Here's how they can still find you. | `e911_v2` view "hook" {"_still": 0.6} | card "CAN'T TALK?" |
| 2 | route | Your call reaches a nearby cell tower, and the network sends it to your local 911 center. | `e911_v2` view "route" {"send_cue": "network", "_still": 0.85} | label "CELL TOWER" @tower; label "LOCAL 911 CENTER" @center |
| 3 | sector | The 911 center can typically see which tower, and which side of it, took your call. That's a rough area. | `e911_v2` view "sector" {"wedge_cue": "side", "_still": 0.8} | label "TOWER SECTOR" @sector; chips ROUGH AREA |
| 4 | twist | Here's what most people miss. Many newer phones also send their own location automatically, from GPS and nearby Wi-Fi. | `e911_v2` view "hybrid" {"fix_cue": "own", "_still": 0.85} | label "MUCH CLOSER" @you; chips GPS · WI-FI; card twist "YOUR PHONE CAN SEND ITS LOCATION" |
| 5 | map | That can show up on the dispatcher's map, often much closer than the tower alone. | `e911_v2` view "desk" {"dot_cue": "show", "_still": 0.75} | label "DISPATCHER'S MAP" @map; chips OFTEN MUCH CLOSER |
| 6 | text | In many areas you can text 911. Put your address in it, and remember: call if you can, text if you can't. | `e911_v2` view "text" {"_still": 0.6} | label "TEXT 911" @phone; chips GIVE YOUR ADDRESS · CALL IF YOU CAN (check) |
| 7 | outro | Did you know you could text 911? Tell us below. | `e911_v2` view "outro" | card "DID YOU KNOW?" / "Tell us below" |

Facts (kept soft; calm tone; no emergency shown):
- Wireless carriers must deliver 911 voice calls to the local 911 center (PSAP) with the caller's number and
  approximate location; the call is routed from the cell site that took it. [FCC Text-to-911 FAQ; Wikipedia Enhanced 9-1-1]
- Phase I location = the tower / antenna (sector) that received the call; Phase II = the caller's latitude and
  longitude. Narration: "which tower, and which side of it ... a rough area". [Wikipedia Enhanced 9-1-1]
- Many phones send their own location automatically when you call or text an emergency number (Android Emergency
  Location Service fuses cell, GPS, Wi-Fi and sensor data; handset-based GPS / assisted GPS). Availability depends on
  phone, carrier and 911 center, so narration says "many newer phones" and "can show up ... often much closer".
  [Android ELS how it works; Wikipedia Enhanced 9-1-1]
- Text-to-911 works only where the local 911 center accepts it (otherwise an automatic bounce-back); texts usually do
  NOT carry automatic location, so give your address; make a voice call when you can. Narration: "In many areas",
  "Put your address in it", "call if you can, text if you can't" (paraphrase of the FCC guidance). [FCC Text-to-911 FAQ]
Sources: https://en.wikipedia.org/wiki/Enhanced_9-1-1 ·
https://desmoinescounty.iowa.gov/files/descom/text_911_faq_14828.pdf (FCC consumer guide "Text-To-911 Quick Facts & FAQs") ·
https://www.android.com/safety/emergency-help/emergency-location-service/how-it-works/

Cover hook: setup "Can't speak on a 911 call?" / payoff "THEY CAN FIND YOU". (Fact-check: softened from "they find you".)
Caption question / engagement: "Did you know you could text 911? 1 = yes, I knew, 2 = no idea, 3 = not sure if my area has it."

New build work: `e911_v2` in the same tower city + cafe plaza (+ a kiosk with Wi-Fi rings): monopole cell tower with
3 x 3 sector panels (sector 0 faces the cafe), low 911 center (no signage) with a roof dish and parking, teal / amber
pulses phone -> tower -> 911 center, amber 120-degree sector fan, teal small fix circle + GPS beam; dispatch-desk set
(blue-grey acoustic walls, dark wall map, three monitors, headset, no people); phone screens: in-call (round buttons,
red end pill) and chat bubbles, no text.

---

## ed-2026-11-29-3 (20:00 ET): "Your TV Remote Flashes a Light You Can't See, but Your Phone Camera Can"

Episode: `page3/episodes/2026-11-29-ed-c3-tv-remote-ir/episode.json` (keyword "tv remote", slug `tv-remote`)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Your TV remote flashes a light every time you press a button. You just can't see it. | `remote_ir_v2` view "hook" {"_still": 0.6} | card "AN INVISIBLE LIGHT?" |
| 2 | led | That little bulb up front is an infrared LED. Its light sits just past red, beyond what eyes can see. | `remote_ir_v2` view "led" {"_still": 0.75} | label "INFRARED LED" @led; chips INVISIBLE TO YOUR EYES · JUST PAST RED |
| 3 | code | Each button sends its own pattern of super-fast flashes, like Morse code made of light. | `remote_ir_v2` view "code" {"_still": 0.7} | label "FAST FLASHES" @pulses; chips ONE PATTERN PER BUTTON |
| 4 | sensor | A small sensor on the TV catches that pattern and does what you asked. | `remote_ir_v2` view "sensor" {"change_cue": "does", "_still": 0.85} | label "IR SENSOR" @sensor; chips READS THE PATTERN |
| 5 | twist | Here's the trick. Many phone cameras can see that light, so it shows up as a purple-white flash. | `remote_ir_v2` view "phone" {"flash_cue": "see", "_still": 0.7} | label "ON YOUR PHONE SCREEN" @screen; card twist "YOUR CAMERA CAN SEE IT" |
| 6 | try | Try it tonight. Point the remote at your phone's camera and press a button. Nothing? Try the selfie camera. | `remote_ir_v2` view "try" {"_still": 0.8} | label "SELFIE CAMERA" @front; chips POINT · PRESS · TRY THE SELFIE CAMERA (check) |
| 7 | outro | Did you see the flash? Tell us below. | `remote_ir_v2` view "outro" | card "DID YOU SEE THE FLASH?" / "Tell us below" |

Facts (soft on screen; no wavelength number on screen):
- TV remotes use an infrared LED, typically about 940 nm (just beyond visible red, ~700-750 nm), invisible to the eye.
  [Wikipedia Remote control; Adafruit IR sensor]
- Each button sends its own pattern of IR pulses (modulated on a ~36-38 kHz carrier); the receiver on the TV
  recognises the pattern. "Super-fast flashes, like Morse code made of light" is an analogy. [Wikipedia; Adafruit]
- Digital / phone cameras can see the IR light, often as a purple light; many phones filter IR on the rear camera but
  little or none on the front (selfie) camera. Narration "Many phone cameras", "Nothing? Try the selfie camera."
  [Wikipedia Remote control; Carolina Biological]
Sources: https://en.wikipedia.org/wiki/Remote_control · https://learn.adafruit.com/ir-sensor/overview ·
https://knowledge.carolina.com/?p=189

Cover hook: setup "Your phone camera can see your remote's" / payoff "SECRET LIGHT".
Caption question / engagement: "Did you see the flash? 1 = yes, on my main camera, 2 = only on the selfie camera, 3 = nothing showed up."

New build work: `remote_ir_v2` living-room lightbox set (mid-tone blue-grey TV wall, oak floor, rug, navy sofa, walnut
coffee table + console, wall TV with an in-memory landscape picture that swaps day -> sunset on `change_cue`, IR
receiver window on the bezel, window daylight panel, floor lamp, shelf, plant, colour-block art), remote model with a
dark IR LED dome, spectrum strip (violet -> red + hatched infrared zone, amber frame), pale-violet IR dashes travelling
remote -> sensor along a faint path, phone on a stand whose screen shows a camera view of the remote with the
purple-white flash bursting on `flash_cue`.

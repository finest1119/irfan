# Track A batch 01: first ED reels on Page 1379706781903422 (target: post 27 Nov 2026)

Made with the v2 pipeline (multi-shot, `pipeline/make_episode.py`), ED overlay style block
(`"style": {"font_set": "montserrat", "highlight_color": "#FFB000", "twist_card": {"bg": "#FFB000", "fg": "#1B1F24"}}`),
ED cover (`--style ed`). US English, US units. Narration ~35-45 s. Fact status: first pass from web searches
(26 Nov); the Fable fact-check re-verifies against the cited sources before the voice is generated.

---

## ed-2026-11-27-1: "How planes land when pilots can't see the runway" (ILS / autoland in fog)

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | Thick fog. The pilots can't see the runway. The plane lands anyway. Here's how. | `airport_hook` + **new `fog` param** (dense shader haze, runway lights glowing) | card "LANDING BLIND?" |
| 2 | localizer | Two invisible radio beams come up from the airport. The first, the localizer, tells the plane if it's left or right of the runway centerline. | **new `ils_beams_v2`** (top-down: teal beam fanning from the far end of the runway, plane sliding onto it) | label "LOCALIZER: LEFT / RIGHT" |
| 3 | glideslope | The second, the glideslope, tells it if it's too high or too low, on a gentle slope of about three degrees down to the touchdown zone. | `ils_beams_v2` view "side" (long lens, amber 3° slope) | label "GLIDESLOPE: UP / DOWN", big "≈ 3°" |
| 4 | autopilot | The autopilot locks onto both beams and flies the plane down them, correcting all the way. | `cockpit_workload_v2` (approach, radio rings) + fog | chips "LOCALIZER ✓ · GLIDESLOPE ✓" |
| 5 | cat3 | On the strictest approaches, called Category Three, it can even touch down and hold the centerline, with visibility as low as about 300 feet. | `ils_beams_v2` view "touchdown" (fog, runway lights, wheels on centerline) | card twist "VISIBILITY: ~300 FT" |
| 6 | pilots | But the pilots aren't passengers. They watch every second, ready to take over, and the plane, the crew and the runway all need special approval. | `cabin_v2`? no: `cockpit_workload_v2` close + fog | chips "PLANE ✓ CREW ✓ RUNWAY ✓" |
| 7 | outro | Would you trust the autopilot to land you in fog? Tell us below. | `airport_outro` (fog lifting) | card CTA |

Facts (soft on screen):
- ILS = localizer (lateral guidance to the centerline) + glideslope (vertical guidance, typically 3°). [SKYbrary Precision Approach; Wikipedia ILS]
- CAT IIIb: decision height below 50 ft or none; RVR below 600 ft but **not less than 150 ft** (FAA/ICAO; EASA's floor is 75 m). [Transport Canada TP 1490; SKYbrary]
- CAT IIIb autolands can happen before the pilots see the runway. [AOPA "How Low Can You Go?"]
- Aircraft, crew and runway/airport all need certification/approval for CAT III. [TP 1490; EASA CS-AWO]
Sources: https://skybrary.aero/index.php/Precision_Approach · https://tc.canada.ca/node/29739 ·
https://www.aopa.org/news-and-media/all-news/1997/october/01/how-low-can-you-go · https://en.wikipedia.org/wiki/Instrument_landing_system

Cover hook (≤ 8 words, true): setup "The pilots can't see the runway" / payoff "IT LANDS ANYWAY".
Caption question / engagement: "Would you trust autoland in fog? 1 = yes, 2 = only with the pilots watching, 3 = I'd take the train."

New build work: `fog` param for the airport world (denser L.fog + runway approach lights); `ils_beams_v2`
(translucent teal localizer fan + amber glideslope wedge, 3 views). Everything else reuses scene_lib_v2_air.

---

## ed-2026-11-27-2: "Your checked bag's hidden ride to the plane"

| # | Beat id | Narration | Shot (builder) | Overlays |
|---|---|---|---|---|
| 1 | hook | You drop your bag at the counter. It disappears. Here's the ride it takes under the airport. | **new `bag_belt_v2`** view "counter" (check-in belt, bag sliding through the curtain) | card "WHERE DOES IT GO?" |
| 2 | tag | First, the tag. It carries a ten-digit number, printed as a barcode. | `bag_belt_v2` "tag" (macro on tag) | label "10-DIGIT TAG NUMBER" |
| 3 | scan | On the belt, lasers and cameras read it from every side, because the bag can land any way up. Some airlines add a radio chip, too. | `bag_belt_v2` "scan_arch" (scan arch, red scan lines) | chips "BARCODE · RFID" |
| 4 | screen | Then it's scanned for explosives, often while it moves, before it ever reaches the plane. | `bag_belt_v2` "screen" (EDS tunnel) | label "SECURITY SCAN" |
| 5 | sort | The computer knows your flight, so paddles called diverters push your bag onto the right belt at the right moment. | `bag_belt_v2` "sort" (wide maze, diverter swings, bag takes a branch) | label "DIVERTER" |
| 6 | load | It ends in your flight's pile, then rides a cart to the plane's belly. | `bag_belt_v2` "makeup" → airport apron (belt loader) | card twist "ALL WITHOUT A HUMAN READING THE TAG" (check wording at fact-check) |
| 7 | outro | Has an airline ever lost your bag? Tell us below. | `airport_outro` | CTA |

Facts: bag tag = unique 10-digit licence plate as a barcode (industry standard by 1989); in-line arrays read
barcodes with lasers/cameras from multiple angles; some airlines add RFID; US checked bags are screened in-line by
EDS (TSA "Checked Baggage Inspection Systems"); diverters steer bags along the system to the destination
(make-up) area. [Wikipedia Baggage handling system; Wikipedia Bag tag; TSA]
Sources: https://en.wikipedia.org/wiki/Baggage_handling_system · https://en.wikipedia.org/wiki/Bag_tag

Cover hook: setup "Your checked bag takes a hidden" / payoff "RIDE".
Caption question: "Has an airline ever lost your bag? 1 = never, 2 = once, 3 = I only carry on now."

New build work: `bag_belt_v2` (indoor baggage hall set: belts, scan arch, EDS tunnel, diverter, make-up carousel;
bags = rounded boxes with tags; lit "lightbox" interior per v2 rules, never a void).

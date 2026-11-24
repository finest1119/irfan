# Everyday Decoded — Batch 01 script review (10 episodes)

Written and fact-checked 24 Nov 2026. Voice: Sadaltager (fixed). Target 230–280 words (about 80–100 s at 165–175 wpm).
Every number and mechanism claim was checked against pages opened during this session (2+ opened sources per claim; anything with fewer was dropped or softened and is listed in that file's `fact_notes`). Only opened URLs are listed in `sources`. Second sources are sometimes an encyclopedia page (Wikipedia) or trade press / a vendor explainer rather than a government or university page: 01 (trade press for range and backhaul), 02 (Wikipedia, a tech news site), 03 (Wikipedia, two payment-company explainers), 04 (Wikipedia, a history site), 09 (Wikipedia), 10 (Wikipedia, streaming-vendor docs). Sources may name companies; the scripts never do.

## Summary

| # | File | Topic | Title | Words | Twist at | Twist | Verdict | Risk / note |
|---|---|---|---|---|---|---|---|---|
| 01 | `01-5g.json` | A1 | What Really Happens When You Open an App on 5G | 272 | 60% | 5G antennas steer narrow beams; fastest mmWave 5G is easily blocked and often reaches only a few hundred feet | READY | Range figure is an industry estimate (2018 trade press) - kept soft ('often', 'a few hundred feet'). 'Dozens of antennas' applies to newer massive-MIMO panels, hedged with 'can be'. |
| 02 | `02-wifi-vs-microwave.json` | A4 | Why Your Wi-Fi Stutters When the Microwave Is On | 256 | 59% | A microwave oven cooks at about 2.45 GHz - inside the same 2.4 GHz band many Wi-Fi networks use | READY | Must not read as a health scare: script says leakage is strictly limited by federal rules. 'Same band', never 'same frequency'. |
| 03 | `03-tap-to-pay.json` | B1 | Where Your Payment Goes When You Tap Your Card | 269 | 58% | The card has no battery - the terminal's field powers it, and it only works within a few inches | READY | Money topic: explains why it is secure (one-time code, tiny range) and nothing about defeating it. Processor/network/bank route is simplified and unnamed. |
| 04 | `04-barcode-gum-1974.json` | B5 | The First Thing Ever Scanned at a Checkout Was a Pack of Gum | 262 | 61% | The first product scanned at a real checkout was a pack of chewing gum in Troy, Ohio, on June 26, 1974 | READY | Gum brand and store name deliberately left out. 'Price isn't in the barcode' is limited to typical packaged items (store-printed weighed-item labels can carry a price). |
| 05 | `05-central-ac.json` | C1 | Your Air Conditioner Doesn't Make Cold Air | 277 | 60% | The AC also pulls water out of the air - gallons a day on a humid day | READY | Gallons-per-day is a rough estimate (trade association 5-20; one university course 10-30 on a humid day) - said as 'five gallons or more' with 'can'. No repair steps. |
| 06 | `06-microwave-door-mesh.json` | C3 | Why There's a Metal Mesh in Your Microwave Door | 278 | 60% | Microwaves are nearly 5 inches long - far too big for the pinhole-size holes - but light waves are thousands of times smaller, so you can see in | READY (visually the thinnest of the batch) | Only two camera anchors exist for this topic (kitchen_microwave, macro_microwave_mesh), so several beats reuse them with different moves. Includes a safety line (damaged door → stop using it); no internal-repair steps. |
| 07 | `07-water-tower.json` | C5 | Your Town's Water Tower Is a Giant Battery for Water Pressure | 258 | 59% | The tower is there for height: gravity makes the pressure - about 1 psi for every 2.3 feet | READY | Systems differ (some towns use ground tanks or pumps only) - script says 'in many towns'. The '100 feet = about 43 psi' line is our arithmetic from the sourced 0.43 psi/ft. |
| 08 | `08-traffic-light-loop.json` | D1 | How the Traffic Light Knows You're Waiting | 277 | 61% | The road isn't weighing you - a wire loop under the pavement senses the metal of your car | READY | Not every signal uses loops (radar/video are common) - stated in the script. No tips for triggering a light. |
| 09 | `09-gps-relativity.json` | D2 | Your Phone's GPS Would Be Off by Miles Without Einstein | 273 | 59% | GPS satellite clocks gain about 38 millionths of a second a day from relativity - uncorrected, that is about 6 miles of drift a day | READY | Direction of signals stated explicitly (down only; phone just listens). Phones also use cell/Wi-Fi help for speed - not mentioned, but nothing in the script contradicts it. |
| 10 | `10-streaming.json` | F1 | You Hit Play. The Show Didn't Come From Far Away | 262 | 60% | You never watch one long video: the show arrives in chunks a few seconds long, and quality can switch between chunks | READY | Proprietary systems vary by service - 'typically' / 'popular shows' used; no service named. 'More than a thousand deliveries' is our arithmetic (2 h ÷ 6 s chunks = 1,200). |

## Notes for the reviewer

- **Beat template (all 10):** `hook` → `stop1…stopN` → `twist` → (episode 02 only: one more stop, the fix) → `outro`. The `outro` beat is the backout to the opening object and carries the sign-off ("Another one decoded."), the comment question, the share line and the loop line.
- **TWIST card:** written as `{"type":"card","text":"TWIST","style":"twist"}` so it is a card (as briefed) and also passes `page3/tools/make_episode.py`, which wants `style: twist` on the twist beat.
- **Chips:** one chip per overlay object (same as `_sample.json`), at most 3 per beat. Every journey beat has a `STOP n` chip.
- **Cues:** every `cue` is a word spoken in that beat. Number cues (`2.4`, `2.45`, `38`, `12550`, `5`) match the token as written in the text.
- **World field:** set from the stops actually used, so a few differ from the plan's World column (F1 starts at the living-room TV → W3 added; B5 starts at the checkout → W1 added; A1 dives into the phone antenna → W2 added).
- **Our own arithmetic (not quoted from a source):** 07 '100 feet up = about 43 psi' (100 × 0.43 psi/ft); 10 'more than a thousand tiny deliveries' (2-hour movie ÷ 6-second chunks = 1,200).
- **Plan numbers changed:** B1 '1.5 inches (4 cm)' → 'within a few inches' (only one opened source for 4 cm); A1 'a few hundred yards' → 'a few hundred feet'; A1 'even your hand' and A4 'an old microwave' dropped.
- **Weakest of the batch:** 06 (microwave mesh) has only two camera anchors, so it reuses them with different moves; 04 (barcode) has the least physical 'journey'. Both are accurate and usable.
- **Not opened / blocked today:** Smithsonian pages, the DOE Energy Saver web pages, the payments industry association Q&A and several vendor pages returned errors; none of them is cited. See each file's `fact_notes`.

## Full narration

### 01 · A1 — What Really Happens When You Open an App on 5G (272 words)

- **HOOK** (`hand_phone`, drift, teal): You tap an app on 5G, and it opens before your thumb is even off the glass. In that blink, your request left your hand, crossed town, and came all the way back. Here's the trip it took.
- **STOP1** (`macro_phone_antenna`, snap, teal): Stop one is inside your phone. Tiny antennas turn your tap into radio waves and send them out through the air.
- **STOP2** (`cell_tower`, travel, teal): Stop two: the nearest cell tower. Those flat panels near the top can be packed with dozens of small antennas, all listening for phones like yours.
- **STOP3** (`tower_base`, crane, teal): Stop three: down the pole to the base. From here your request usually leaves on a fiber line, a thread of glass that carries data as flashes of light.
- **STOP4** (`street_slice_fiber`, section, teal): Stop four runs under the street. Your request races through that glass like a car on an express lane with no stoplights.
- **STOP5** (`data_center`, travel, teal): Stop five: a data center, a building full of computers. A server there finds what you asked for and sends the answer right back the way it came.
- **TWIST** (`cell_tower`, orbit, teal): Here's the twist. That tower doesn't just spray signal in every direction. 5G antennas can steer a narrow beam toward your phone. And the very fastest kind of 5G, called millimeter wave, is easy to block. Walls, tree leaves, even rain can get in the way, so it often reaches only a few hundred feet.
- **OUTRO** (`hand_phone`, backout, teal): That's why your phone can fly on one corner and crawl on the next. And all you did was tap. Another one decoded. Where does your signal always drop? Tell me in the comments, and share this with someone who's always hunting for bars. Now tap that app again, and picture the trip.

Caption: Decoded: what really happens when you open an app on 5G. / Your tap goes phone → tower → fiber under the street → data center → back, in a blink. / Where does your signal always drop?

Engagement comment: Quick poll: how many bars do you have right now? Drop the number 👇 (and tell us the spot where your signal always dies)

Fact notes: HEDGED: mmWave range - plan said 'a few hundred yards'; best opened source (industry estimate, 2018) says 100-200 m, so the script says 'often reaches only a few hundred feet'. 'Even your hand' DROPPED (the opened study only lists body blockage as a topic it measured); replaced by 'even rain', which two opened sources state. 'Dozens of antennas' is true of massive-MIMO panels, so 'can be packed with'. Backhaul is 'usually' fiber (some sites use wireless links). DROPPED: any latency figure in milliseconds and any speed number (not sourced). The 'express lane' line is the one analogy. No carrier named.

### 02 · A4 — Why Your Wi-Fi Stutters When the Microwave Is On (256 words)

- **HOOK** (`hand_phone`, drift, teal): Your video freezes the second someone starts heating leftovers. That's not bad luck. Your Wi-Fi and your microwave have something weird in common, and it's floating around your kitchen right now.
- **STOP1** (`living_room_router`, travel, teal): Stop one: your router. It talks to your phone using invisible radio waves, and one of its main lanes is a band of the airwaves called 2.4 gigahertz.
- **STOP2** (`kitchen_microwave`, travel, amber): Stop two: the kitchen. A microwave oven uses radio waves too, trapped inside a metal box. They make the water molecules in your food vibrate, and all that motion turns into heat.
- **STOP3** (`macro_microwave_mesh`, snap, amber): Stop three: the door. The metal walls and that dotted screen keep nearly all of those waves inside the box, and federal safety rules strictly limit how much is allowed to leak.
- **STOP4** (`living_room_router`, travel, teal): Stop four: back at the router. While that oven is running, your phone and your router struggle to hear each other. That's the stall you see on your screen.
- **TWIST** (`kitchen_microwave`, orbit, teal): Here's the twist. Your microwave cooks at about 2.45 gigahertz, right inside the same band as that Wi-Fi lane. So the tiny bit that slips out works like a leaf blower starting up next to a quiet conversation. Harmless to you, but very loud to your Wi-Fi.
- **OUTRO** (`hand_phone`, backout, teal): The fix? Many routers also have a 5 gigahertz lane the microwave doesn't touch. Or just move the router farther from the kitchen. Another one decoded. Does your Wi-Fi stutter when the microwave runs? Comment yes or no, and share this with whoever always blames the internet company. Next time your video freezes, check who's heating leftovers.

Caption: Decoded: why your video freezes when someone starts the microwave. / Your Wi-Fi and your microwave share the same slice of the airwaves. / Does your Wi-Fi stutter when the microwave runs?

Engagement comment: Yes or no: does your Wi-Fi drop when the microwave is running? And is your router anywhere near the kitchen? 👀

Fact notes: CONFIRMED the plan's twist (same 2.4 GHz band). HEDGED: 'nearly all' waves stay inside; 'many routers' have 5 GHz. Worded as 'same band', not 'same frequency', and said Wi-Fi also uses another band. DROPPED: 'an old microwave is worse' from the plan (only one opened source says older units have poor shielding); power comparison (oven watts vs router watts) - not in an opened source; any health claim beyond 'federal rules strictly limit leakage' (FDA). No 'resonance' or 'cooks from the inside' wording. The leaf-blower line is the one analogy.

### 03 · B1 — Where Your Payment Goes When You Tap Your Card (269 words)

- **HOOK** (`strip_mall_checkout`, orbit, teal): You tap your card at the register. A few seconds later: approved. No swipe, barely a pause. But in that little gap, your payment went on a trip. Here's where it went.
- **STOP1** (`macro_card_coil`, snap, teal): Stop one is inside the card. Hidden in the plastic is a thin wire coil, an antenna you never see.
- **STOP2** (`macro_card_chip`, portal, teal): It feeds stop two: the chip, a tiny computer. For this purchase it creates a one-time security code. It's made for this single payment, so a copy of it is no good for another.
- **STOP3** (`macro_terminal`, travel, teal): Stop three: the terminal. It bundles that code with the amount and sends the request out of the store.
- **STOP4** (`data_center`, travel, teal): Stop four: the handoff. Like a baton in a relay race, the request passes from the store's payment processor, to the card network, to your bank's computers. They check the code and your account, and send one word back down the line: approved. The whole relay usually takes just a few seconds.
- **TWIST** (`macro_card_coil`, snap, teal): Here's the twist. Your card has no battery. None. The terminal gives off a small energy field, and when the card gets close, that coil picks up just enough power to wake the chip. It only works at very close range, within a few inches, which is why you have to bring the card right up to the terminal.
- **OUTRO** (`strip_mall_checkout`, backout, teal): So that beep is a tiny computer waking up, doing its math, and going back to sleep. And all you did was tap. Another one decoded. Team tap, or team chip in the slot? Comment below, and share this with someone who still swipes. Next time you tap your card, count the seconds.

Caption: Decoded: what really happens when you tap your card. / A few seconds, four stops, and a card with no battery. / Team tap or team chip?

Engagement comment: Team TAP or team CHIP-in-the-slot? Vote below 👇 (bonus: did you know your card has no battery?)

Fact notes: APPLIED section 6: 'two seconds' → 'a few seconds'. HEDGED/CHANGED: the plan's 'about 1.5 inches (4 cm)' has only ONE opened source (a card maker's page); a second opened source gives the general standard's limit as about 10 cm (4 in). So the script says 'within a few inches' and shows no number on screen. 'A copy of it is no good for another [purchase]' is the plain-word version of the standards body's 'one-time code to safeguard against fraud'. DROPPED: 'no PIN' (some taps do ask for one), any transaction-time number in milliseconds, anything about reading at a distance or how fraud is attempted, and phone-wallet features (cards only). The standards body's own range specification could not be opened (a chip maker's note that quotes 4 cm timed out twice). No card network, bank or store named. The relay race is the one analogy.

### 04 · B5 — The First Thing Ever Scanned at a Checkout Was a Pack of Gum (262 words)

- **HOOK** (`strip_mall_checkout`, drift, teal): Beep. Beep. Beep. You've heard that sound thousands of times at the checkout. But the very first beep at a real checkout came from a pack of gum. Follow the beep.
- **STOP1** (`macro_barcode`, snap, teal): Stop one: the barcode itself. Those black bars and white gaps aren't a picture. They're just a number, twelve digits long, written in stripes a machine can read.
- **STOP2** (`macro_scanner`, portal, teal): Stop two: the scanner. It sweeps a beam of light across the bars and reads the pattern back as those twelve digits. The last digit is a built-in check, so a bad read gets caught and you scan again.
- **STOP3** (`macro_terminal`, travel, teal): Stop three: the register. Here's what surprises people. On a typical packaged item, the price isn't in the barcode at all. The register looks that number up in the store's computer, like finding a name in your contacts, and the computer sends back what it is and what it costs. That's how a sale price can change overnight without anyone touching the package.
- **TWIST** (`macro_barcode`, snap, teal): Here's the twist. The first product ever scanned at a real checkout was a pack of chewing gum. It happened in Troy, Ohio, on June 26, 1974, just after eight in the morning. One beep, one pack of gum, and that same twelve-digit idea is now on nearly everything you buy.
- **OUTRO** (`strip_mall_checkout`, backout, teal): So every beep is a tiny lookup: stripes, number, price. Another one decoded. What's the first thing you remember buying with your own money? Tell me in the comments, and share this with someone who loves random history. Next time you're at the checkout, listen for it. Beep. Beep. Beep.

Caption: Decoded: the beep at every checkout. / The bars are just a 12-digit number, and it all started with a pack of gum in Ohio in 1974. / What's the first thing you remember buying with your own money?

Engagement comment: What's the first thing you ever bought with your own money? Ours was candy. Obviously. 🍬

Fact notes: CONFIRMED the plan's twist with the date, town and time (8:01 a.m. → 'just after eight'). HEDGED: 'on a typical packaged item' - store-printed labels for weighed items (meat, produce) can carry a price or weight inside the code, so 'the price is never in a barcode' would be wrong. 'Nearly everything you buy' is soft. DROPPED: the gum brand, the store name and the people involved (no brand names); 'why gum was chosen' and the gum's price (accounts differ / not in two opened sources); 'laser or camera' detail and 'dark bars absorb light' (not in opened sources); number of scans per day. One opened source is a 2008 state government fact sheet - its fee information is outdated and is not used. The contacts-lookup line is the one analogy.

### 05 · C1 — Your Air Conditioner Doesn't Make Cold Air (277 words)

- **HOOK** (`thermostat`, drift, ice): It's ninety-five degrees out. You bump the thermostat down, and cool air pours from the vents. But here's the strange part: your air conditioner isn't making cold. It's taking heat away. Follow the heat.
- **STOP1** (`ac_indoor_coil`, travel, ice): Stop one: the indoor coil. A very cold fluid called refrigerant runs through its metal tubes. A fan pushes your warm house air across them, and the refrigerant soaks up the heat like a sponge. The air comes out cooler because its heat got left behind.
- **STOP2** (`ac_lines_wall`, section, amber): Stop two: the lines running through your wall. The refrigerant, now loaded with your living room's heat, heads outside.
- **STOP3** (`ac_condenser`, travel, amber): Stop three: the big unit in the yard. A compressor squeezes the refrigerant, which makes it even hotter, and a fan blows that heat off into the outdoor air. That's why the air coming off that unit feels so warm. It's your house's heat, leaving.
- **STOP4** (`ac_lines_wall`, section, ice): Then the refrigerant cools back down, returns inside, and does it all over again, until your house reaches the temperature you asked for.
- **TWIST** (`ac_indoor_coil`, snap, ice): Here's the twist. Your AC is also pulling water out of thin air. When humid air hits that cold indoor coil, the moisture turns into drops, drips into a pan, and drains away through a small pipe. On a humid day, a home system can pull five gallons of water or more out of your air.
- **OUTRO** (`thermostat`, backout, ice): So that cool, dry air is really just your air with the heat and the water taken out. Another one decoded. What's your thermostat set to right now? Drop the number in the comments, and share this with whoever keeps changing it. Next time you bump that thermostat down, remember where the heat goes.

Caption: Decoded: your AC doesn't make cold air. It moves heat outside. / And on a humid day it pulls gallons of water out of your air. / What's your thermostat set to right now?

Engagement comment: Thermostat wars: what number is yours set to right now? 🥶 68? 72? 76? Drop it below.

Fact notes: CONFIRMED the plan's twist (moves heat + removes water). HEDGED: water volume said as 'can pull five gallons or more on a humid day' - the two opened sources give 5-20 and 10-30 gallons/day and neither is a measured standard. 'Ninety-five degrees' in the hook is scene-setting, not a claim. Simplified: the refrigerant's liquid/gas change is described only as 'very cold fluid ... soaks up heat' and 'cools back down'. DROPPED: the inventor/history, efficiency or cost numbers, and anything that sounds like a repair step (no refrigerant, drain-clearing or electrical instructions). The DOE Energy Saver web pages returned 'not found' today, so the DOE citation is the Energy Saver 101 Home Cooling PDF (opened and read). No maker named in the script; one maker's explainer is used only as a source. The sponge is the one analogy.

### 06 · C3 — Why There's a Metal Mesh in Your Microwave Door (278 words)

- **HOOK** (`kitchen_microwave`, drift, amber): You stand there watching your leftovers spin behind a window full of tiny dots. Ever wonder why there's a metal screen in that glass? It's the reason you can watch your food cook at all. Let's go in.
- **STOP1** (`kitchen_microwave`, portal, amber): Stop one: inside the box. A part called a magnetron makes microwaves, which are a kind of radio wave you can't see. The metal walls reflect them, so the waves bounce around until your food absorbs them.
- **STOP2** (`kitchen_microwave`, orbit, amber): Stop two: the food. The waves make its water molecules vibrate, and all that motion becomes heat. And no, it doesn't cook from the inside out. The outer layers heat first, and the warmth works its way in.
- **STOP3** (`macro_microwave_mesh`, snap, amber): Stop three: the door. You need to see in, but the waves need to stay in. So a sheet of metal is built into the glass, punched full of tiny holes, each only about as wide as the tip of a pen. And federal safety rules strictly limit how much is allowed to leak.
- **TWIST** (`macro_microwave_mesh`, orbit, amber): Here's the twist. The microwaves in your oven are nearly five inches long. To a wave that big, those holes are like a soccer net to a beach ball, so the screen acts almost like solid metal. But visible light waves are thousands of times smaller than the holes, so they slip right through. You see in. The microwaves stay in.
- **OUTRO** (`kitchen_microwave`, backout, amber): And if that door is ever damaged or won't close right, stop using the oven. Another one decoded. Do you watch your food spin, or walk away? Tell me below, and share this with someone who stands back from the microwave. Next time your leftovers spin, look at the dots.

Caption: Decoded: the tiny dots in your microwave door. / The waves are nearly 5 inches long, and the holes are pinhole-size. Light gets out. Microwaves don't. / Do you watch your food spin, or walk away?

Engagement comment: Be honest: do you stand and watch the food spin, or walk away? 👀 (And who was told as a kid not to stand too close?)

Fact notes: CONFIRMED the plan's twist: wavelength about 12 cm (4.8 in → 'nearly five inches'); holes about 1 mm. HEDGED: the screen acts 'almost like' solid metal (a small, federally limited amount can leak); hole size said as 'about as wide as the tip of a pen' with '1 MM' on screen (US-units exception: no natural inch value). 'Thousands of times smaller' = the university source's 'about 2000 times'. Mechanism wording follows FDA ('vibrate'), not 'resonance'; the inside-out myth is corrected in the script. DROPPED: 'glass alone would let microwaves through' (only FDA states it among opened sources); the 2.45 GHz number (used in episode 02 instead), any leakage number, and all internal-parts/repair detail beyond naming the magnetron. Added FDA's damaged-door advice. The soccer net is the one analogy.

### 07 · C5 — Your Town's Water Tower Is a Giant Battery for Water Pressure (258 words)

- **HOOK** (`faucet_kitchen`, drift, ice): You turn on the kitchen faucet and water shoots out, instantly, with real force. But there's no pump in your house. So what's pushing it? In many towns, the answer is that giant tank on legs at the edge of town.
- **STOP1** (`wall_pipes`, section, ice): Stop one: the pipes hidden inside your wall. The water in them is already under pressure, just waiting there, long before you ever touch the handle.
- **STOP2** (`water_main_slice`, section, ice): Stop two: the water main buried under your street, the big pipe that feeds the whole block.
- **STOP3** (`treatment_plant`, travel, ice): Stop three: the treatment plant, where the water is cleaned and big pumps send it out across the whole town.
- **STOP4** (`water_tower`, crane, ice): Stop four: up we go. Pumps push water up into the tower when the town is quiet, often overnight. A big tower can hold around a million gallons, often about a day's supply for the town. Then comes the morning rush of showers, and the tank drains back down, like a battery being used.
- **TWIST** (`water_tower`, orbit, ice): Here's the twist. The tower isn't just storage. Its real trick is height. Gravity pulls that water down, and every 2.3 feet of height adds about one pound per square inch of pressure, or one psi. So water sitting 100 feet up pushes with about 43 psi. That's why it can keep your water flowing for a while, even when the power goes out.
- **OUTRO** (`faucet_kitchen`, backout, ice): So the push at your faucet is just gravity. Another one decoded. What's painted on your town's water tower? Tell me in the comments, and share this with someone who drives past one every day. Now go turn on that faucet.

Caption: Decoded: what pushes the water out of your faucet. / In many towns it's gravity, stored up in the water tower, like a battery for water pressure. / What's painted on your town's water tower?

Engagement comment: What's painted on YOUR town's water tower? Team name, mascot, giant peach? Tell us where you're from 👇

Fact notes: CONFIRMED the plan's twist. The opened sources state it as 0.43 psi per foot; 2.31 ft per psi is the same conversion (1 ÷ 0.433), said as 'every 2.3 feet ... about one psi'. HEDGED: 'in many towns' (not every system uses an elevated tank); 'typical ... around a million gallons, roughly a day's supply'; 'often overnight'; outage running time said only as 'for a while' (one source says at least 24 hours - not used). OUR ARITHMETIC: 100 ft × 0.43 = about 43 psi (an example height, not a claim about typical towers - typical tower height had only one opened source and was dropped). Simplified: treatment-plant pumps and tower-filling pumps are described as the same pumps; real systems may use separate pump stations. DROPPED: house pressure range numbers. Battery is the one analogy (it is the hook line from the plan).

### 08 · D1 — How the Traffic Light Knows You're Waiting (277 words)

- **HOOK** (`intersection`, drift, teal): You roll up to a red light on an empty street at midnight. A few seconds later it turns green, just for you. Nobody's watching. So how did the light know you were there?
- **STOP1** (`road_loop_slice`, section, teal): Stop one: look down. See those dark lines cut into the pavement near the stop line? Under them is a loop of wire, sealed into a slot sawed into the road.
- **STOP2** (`road_loop_slice`, snap, teal): Stop two: inside that loop. A small electric current runs through the wire all day, creating an invisible magnetic field just above the road.
- **STOP3** (`signal_cabinet`, travel, teal): Stop three: that plain metal cabinet on the corner. A cable links the loop to electronics inside, and they watch that field. When something disturbs it, the signal controller gets the message: car waiting.
- **STOP4** (`intersection`, crane, teal): Stop four: the signal overhead. The controller works you into the cycle, and you get your green. Not every intersection works this way. Many use radar or cameras instead. But the buried loop has long been one of the most widely used sensors on American roads.
- **TWIST** (`road_loop_slice`, section, teal): Here's the twist. Many people think the road feels your car's weight. It doesn't. The loop senses metal. When the metal underside of your car sits over that wire, it disturbs the field, and that tiny change is the signal. The road isn't a scale. It's a giant metal detector.
- **OUTRO** (`intersection`, backout, teal): So at a light like this, you're not just waiting on a timer. You're parked on a metal detector. Another one decoded. What's the longest red light in your town? Name the intersection in the comments, and share this with the friend who creeps forward at every light. Next time you roll up to a red, look down.

Caption: Decoded: how the traffic light knows you're there. / It isn't weighing your car. At many intersections, a wire loop under the road senses the metal. / What's the longest red light in your town?

Engagement comment: Name the longest red light in your town. We'll start: the one you're always late at. 🚦

Fact notes: CONFIRMED the plan's twist (metal, not weight) with the FHWA Traffic Detector Handbook; the explicit 'does not sense weight' wording comes from a 2026 local-news fact check with a state DOT specialist. HEDGED: 'many use radar or cameras instead'; 'has long been one of the most widely used sensors' (the FHWA handbook saying 'most utilized' dates from 2006, so no claim that it is still number one). Simplified: 'disturbs the field' stands in for 'eddy currents lower the loop's inductance'. The hook's 'a few seconds later' is scene-setting. DROPPED: the 10-200 kHz figure, anything about bicycles/motorcycles not being detected, and any tips for triggering or beating a light. Metal detector is the one analogy.

### 09 · D2 — Your Phone's GPS Would Be Off by Miles Without Einstein (273 words)

- **HOOK** (`hand_phone`, drift, teal): The blue dot on your map knows which street you're on. Without Albert Einstein, it would be off by miles before the day was over. To see why, we have to go up. Way up.
- **STOP1** (`sky_satellites`, crane, teal): Stop one: about 12,550 miles above you. More than two dozen GPS satellites are up here, and each one circles the entire Earth twice a day.
- **STOP2** (`sky_satellites`, orbit, teal): Stop two: one satellite, up close. It carries an atomic clock, and it broadcasts the same simple message over and over: here's who I am, and here's exactly what time it is.
- **STOP3** (`hand_phone`, travel, teal): Stop three: follow one of those signals back down to your hand. Notice the direction. The signals only come down. Your phone never sends anything up to those satellites. It just listens.
- **STOP4** (`macro_phone_board`, snap, teal): Stop four: a chip inside. It measures how long each signal took to arrive. Like counting the seconds between lightning and thunder, time becomes distance. With at least four satellites, it can work out where you are.
- **TWIST** (`sky_satellites`, crane, teal): Here's the twist. Those clocks don't tick like clocks on the ground. The satellites move fast, which slows them a little. But gravity is weaker up there, which speeds them up more. Net result: they gain about 38 millionths of a second a day. Left uncorrected, your position would drift about six miles every day. So the fix is built in.
- **OUTRO** (`hand_phone`, backout, teal): So every time that blue dot lands on the right street, Einstein gets proven right again. Another one decoded. Did you know your phone only listens? Comment knew it, or no way, and share this with whoever gets lost with the map open. Now look at that blue dot again.

Caption: Decoded: the blue dot on your map. / GPS satellite clocks run about 38 millionths of a second fast every day. Without Einstein's math, your position would drift by miles. / Did you know your phone only listens?

Engagement comment: 'Knew it' or 'no way': your phone never sends anything UP to GPS satellites. It only listens. 🛰️

Fact notes: APPLIED section 6: altitude 12,550 miles; signals come DOWN and the phone only receives (stated as its own stop); drift about 6 miles (10 km) a day - the two opened sources say 'about 10 kilometers each day' and 'roughly 11.4 km/day', so 'about six miles' is the low, safe end. '38 millionths of a second' = 38 microseconds, said in plain words. HEDGED: 'more than two dozen' satellites (24 slots; 31 operational in the 2023 government count). 'Knows which street you're on' replaces any accuracy-in-feet claim. Simplified: 'the fix is built into the system' (satellite clock rates are offset before launch; receivers apply small extra corrections). DROPPED: accuracy numbers, assisted-GPS/cell-tower help, the pre-launch frequency figure. Einstein is a historical figure, not a brand. The official gps.gov page moved; the citation is its government archive copy (opened). Lightning-and-thunder is the one analogy.

### 10 · F1 — You Hit Play. The Show Didn't Come From Far Away (262 words)

- **HOOK** (`living_room_tv`, drift, teal): You hit play on the couch, and a couple of seconds later the show starts, sharp and clear. It feels like it's beaming in from some giant building far away. It's not. The show was already waiting nearby.
- **STOP1** (`living_room_router`, travel, teal): Stop one: your router. Here's the first surprise. Your TV doesn't ask for the whole show. It asks for one small piece at a time.
- **STOP2** (`street_slice_fiber`, section, teal): Stop two: under your street. In many neighborhoods, that request rides out on a fiber line, as flashes of light.
- **STOP3** (`edge_server_room`, travel, teal): Stop three: not some far-off headquarters, but a server room in your own region. Streaming services typically keep copies of popular shows on servers placed close to viewers. It's like a grocery store stocking the shelf near you, so you don't have to drive to the farm. Shorter trip, faster start.
- **STOP4** (`data_center`, travel, teal): Stop four: the big data center far away. It still holds the master library, and it quietly keeps those local shelves stocked.
- **TWIST** (`living_room_tv`, travel, teal): Here's the twist. You're never watching one long video. The show is chopped into chunks, typically just a few seconds long, and every chunk is saved at several quality levels. Before each one, your TV checks your connection and picks the best version it can handle. That's why the picture sometimes goes blurry, then snaps back sharp. It didn't break. It switched.
- **OUTRO** (`living_room_tv`, backout, teal): So one movie night is more than a thousand tiny deliveries from just down the road. Another one decoded. What's the last show you binged? Drop it in the comments, and share this with someone whose stream is always buffering. Now go hit play.

Caption: Decoded: what happens when you hit play. / The show was already waiting on a server near you, and it arrives in chunks just a few seconds long. / What's the last show you binged?

Engagement comment: What's the last show you binged in one weekend? No judgment. (OK, a little judgment.) 📺

Fact notes: CONFIRMED the plan's twist. Chunk length: opened sources say 'typically two to six seconds' (two streaming-tech vendors) and 'target 6 seconds' (a device maker's spec); other documents quote up to 10 seconds, so the script says 'typically just a few seconds' with no number. HEDGED: 'typically keep copies of popular shows', 'in your own region', 'in many neighborhoods ... fiber' (many homes are on cable or wireless). The hook's 'a couple of seconds' is scene-setting. OUR ARITHMETIC: a 2-hour movie ÷ 6-second chunks = 1,200 video requests → 'more than a thousand tiny deliveries'. Simplified: 'master library' = the origin servers. DROPPED: any service name, servers placed inside internet providers' own buildings (company-specific), bitrate/resolution numbers, 'HD'. Sources name companies but the script does not. The grocery shelf is the one analogy.



## Planner review (Page 3 session, 24 Nov 2026)
All 10 read in full. Approved for production with 2 fixes applied: 04 hook/title/caption no longer claim the gum *caused* barcode adoption (it was only the first scan); 07 tank-size line softened. Watch at build time: 06 reuses 2 anchors (camera must still keep moving: orbit/drift variety); 04 journey is mostly macro (fine as W2 showcase). Each script is re-checked by Fable on posting day per SOP.

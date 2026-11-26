# BUILD-LOG: controlled detonation (Opus build, 26 Nov 2026)

## What was built
- `episode.json`: 10 beats from the approved `script.md`. Voice **Orus**, `"narration_style": "minute by minute"`, pause 0.2, trim_pauses on, and the script's pronunciation line (azide = AY-zide; "nine A M" / "nine fifteen").
  - All text is drawn as 2D overlays: a clock strip, chips, labels on the anchors (drum, pellet, main, forklift, mast, shell) and one `big` panel.
  - Caption, hashtags, engagement comment and sources are taken from `output/controlled detonation.post.md`. That file is unchanged.
- **New overlay type `clock`** in `pipeline/overlay_v2.py` (opt-in; episodes without it are unchanged).
  - It is a navy pill in the card band, just under the 12 % line and clear of the captions, and the band is asserted in code.
  - The text rolls to the next state on each cue word. A state set at 0 s carries across beat cuts with no blink.
  - Strip sequence: WED 25 NOV · 9:00 AM CT → REWIND → MARCH 2026 → THE DAYS BEFORE → 9:00 AM CT → 9:15 AM CT → MORE THAN AN HOUR LATER → TAKEAWAY → YOUR TURN → 9:00 AM CT (loop).
  - Only 9:00 and 9:15 AM CT are clock times. Because the clock owns the card band, there are no `card` items; the title is a `big` panel ("WHY BLOW UP / YOUR OWN EXPLOSIVES?").
- **New one-shot builder** `pipeline/blender/scene_lib_v2_detonation.py` (`detonation_oneshot`, the cyclone/tides pattern), registered in the guarded module list in `render_episode_v2.py`.
  - **World:** a sunny golden prairie with a gravel road and 8 grass-covered earth-mounded bunkers (concrete headwalls, steel doors; one is open, with a lit vault).
  - **The ring:** a ring of 64 sand-coloured T-wall sections around 2 bunkers, 6 blue water tanks, and white foam blocks on the mounds.
  - **Further out:** windbreak tree lines, farms and silos, a generic water tower, the air-monitor mast with spinning cups, and an old rusty shell with a red ring by the road.
  - **Inside the vault:** a plain drum on a pallet (needle crystals grow on the "crystallize" cue), a forklift, and the ILLUSTRATION detonator cutaway: a half tube with an orange primary pellet and a grey-blue main charge, and a spark that hops from one to the other.
  - **Blast:** a soft glow at ground level, then a small camera thump and a wide, low, dithered white dust/foam puff that thins out. There is no fire, no debris and no people. Red 3D arrows point down on "driven down".
  - **Rewind:** during the question beat the puff sinks back and the walls, foam and tanks un-build. In the days-before beat they rise again (walls), stack (foam) and fill (tanks).
  - No 3D text, insignia or signage.
- **Camera:** 17 spots on the global timeline, with eased whips and EEVEE motion blur. The push runs: wide → bunker door → through the door to the drum → cutaway → drum → forklift → back out → high oblique (walls rising) → low corridor between the towering wall and the tanks (hero 2) → aerial for 9:00 → mast for 9:15 → shell → back away → backout to the frame-1 view.
  - **Numeric check** (Blender-python camcheck):
    - Holds are 7.2 s at most, plus the 6.9 s outro backout.
    - Drift is 18 % or less of the subject distance (the backout is excluded).
    - There is no position jump at any beat boundary; every boundary falls inside a smooth whip.
    - The first frame equals the last frame, exactly P1.
  - **One-shot: yes.** There are no hard cuts.

## Narration changes (wording identical)
- Moved "That creates a trap." from the start of `the_trap` to the end of `what_it_is`, because short teaser openers can make the TTS read the director notes aloud (README). Same words, same order.
- `clock_days_before` regenerated once: the first take said "The **bays** before" (heard by whisper base and small). The new take is 100 % aligned.
- `question`: trimmed the trailing silence plus breath after "Follow the clock." (0.8 s pause → under 0.75 s). No words changed.
- Script word count: **289**.

## Renders
- The first full render ran at about 8.5 s per frame. Cause: the interior and flash lights cast shadows across the whole world. I stopped it, set those lights to no shadows with a short cutoff, and the restart took 54 min for 2,550 frames.
- The pause fix changed the timings, so beats 1–9 were re-rendered (49 min). The hook frames are unchanged.

## QC
- **qc_v2 PASS** (the final run): 0 unexpected spikes and 0 A-B-A in every band.
  - Earlier runs failed because anchored labels were still visible during camera whips. I gave every label an `until` before the next whip (LEAD AZIDE, PRIMARY EXPLOSIVE, MAIN CHARGE, DO NOT MOVE, AIR MONITOR, OLD SHELL?).
- **qc_full auto PASS:** 84.07 s, 1080x1920, -14.1 LUFS, true peak -1.1 dB, WER 0.045, no pauses > 0.75 s, FB copy 9.50 MB.
- **Manual review** of sheet_01–03: bright daylight world with no void, captions readable, nothing graphic, cards and chips inside the 12–80 % band, and the frame-1 view matches the final frame (loop).
  - Fixed: the MAIN CHARGE label touched the ILLUSTRATION chip (moved up).
- **SKIP (logged, not repaired):**
  - The 9:00 glow briefly whites out the aerial frame (about 0.5 s, no fire).
  - The red 3D arrows in the 9:00 beat sit partly behind the caption band; the captions are still readable.
  - Whisper hears "air monitor" for "air monitors" (audio fine).
  - The foam blocks visibly drop in mid-air as they stack.
  - The puffs are stylised.

## Thumbnails
- Hero frames: `output/controlled-detonation/stills_v2/06_clock_0900_f0125_heroB.png` (aerial: ring, puff, tanks, arrows; rendered before the timing change, same scene) and `00_hook_f0215_heroA.png` (ring + puff, sky).
- `output/controlled-detonation/thumb_A.jpg`: "Why the Army blew up" / **ITS OWN EXPLOSIVES** (aerial hero).
- `output/controlled-detonation/thumb_B.jpg`: "Too dangerous to move:" / **BLOWN UP** (hook hero).

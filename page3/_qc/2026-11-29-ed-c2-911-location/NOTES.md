# QC notes: 2026-11-29-ed-c2-911-location (Asus render)

- Duration 40.28 s, 1080x1920 30 fps. FB copy 9.22 MB. LUFS -14.2, true peak -1.3 dB, WER 0.0. TTS passed first time (the first attempt was lost to a DNS drop, not TTS).
- qc_full auto: PASS. qc_v2: PASS (no overlay spikes / A-B-A, overlay-caused 0). Card-band px-flicker 50.9 % is the 3D layer itself (50.87 % 3D-only = cut).
- Manual sheet review (20 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:11 the city view is briefly washed grey while the tower sector fades in.
  - 0:07-0:13 "CELL TOWER" / "TOWER SECTOR" labels caught mid-fade on the sheet.
- Cover A: ED's payoff "THEY CAN FIND YOU" is 4 words; make_thumbnail caps the payoff at 3 -> made with "THEY'LL FIND YOU" (setup "Can't talk to 911?", 6 words total). Needs ED's OK.
  Hero frames: A = 04_map f0110 (dispatcher map with your dot); B = 05_text f0120 (text thread) "In many areas, you can" / "TEXT 911".
- No fixes applied, nothing re-rendered.

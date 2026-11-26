# QC notes: 2026-11-30-ed-d1-cabin-lights (Asus render)

- Duration 34.03 s, 1080x1920 30 fps. FB copy 9.24 MB. LUFS -14.2, true peak -1.4 dB, WER 0.009. TTS passed first time.
- qc_full auto: PASS. qc_v2: PASS.
- Manual sheet review (17 frames). For Fable to decide (possible MUST-FIX, not fixable here without a scene change):
  - 0:17-0:21 "shades" beat: a glowing yellow-white block shape floats behind the seat rows (top right) - looks like light-panel / reading-light geometry clipping into the shot; reads as a glitch. Full-size frame at 19.5 s included as sheet "zz_glitch_0019.jpg".
- Minor, not fixed (SKIP): the window shades are flat blue ovals (stylised), fine.
- Covers: A = 02_path f0060 (dimmed aisle with floor path lights) "Why planes dim the lights:" / "YOUR EYES"; B = 04_twist f0180 (full aisle) "Airliners must empty in" / "90 SECONDS".
- No fixes applied, nothing re-rendered.

## Update 26 Nov 16:17 MYT: MUST-FIX resolved
- ED fixed the seatbelt-sign panel in 752a6c8; shot 3 (03_shades) re-rendered alone (179 s), re-assembled, fb 9.26 MB.
- qc_full PASS, qc_v2 PASS; checked 17.5 / 19.5 / 21.0 s: glitch gone (zz_fixed_shades.jpg). Sheets updated.

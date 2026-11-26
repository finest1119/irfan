# QC notes: 2026-11-28-ed-b3-elevator-counterweight (Asus render)

- Duration 38.69 s, 1080x1920 30 fps. FB copy 9.79 MB. LUFS -14.2, true peak -1.0 dB, WER 0.045.
- TTS: needed ED's notes fix 25a9b7e (the model read "about 170 words per minute" aloud) and ED's own Gemini key; then passed.
- qc_full auto: PASS.
- qc_v2: CHECK FAILED on the mid band: overlay spikes 18 / A-B-A 17 at frames 787-792 (~26.2 s), overlay-caused 3 (737-739).
  Checked 1:1 on the overlay-only stream AND the final: these are the tracking labels "CAR UP" / "WEIGHT DOWN" gliding with the moving car and counterweight (~3 px/frame, smooth), no blink, no jump. qc_v2 counts a label that moves outside an expected event as a spike. Judged a false positive -> SKIP, flag for Fable.
- Manual sheet review (19 frames). Minor, not fixed (SKIP, flag for Fable):
  - 0:29-0:31 "AND IF A CAR / EVER GOES TOO FAST": mostly a plain grey wall + rail close-up (weak, near-void background).
  - 0:13 first caption line "THAT" sits over the shaft beam edge (readable).
  - Whisper heard "40 to 50 of a full load" (no "percent") at 0:17; the chip shows "40-50 %". Listen check suggested.
- Covers: A = 04_pass f0100 (car + counterweight in the shaft) "Your elevator has a hidden" / "COUNTERWEIGHT"; B = 00_hook f0090 (building with the car) "The motor isn't lifting" / "YOUR WHOLE CAR" (2 lines).
- No fixes applied, nothing re-rendered.

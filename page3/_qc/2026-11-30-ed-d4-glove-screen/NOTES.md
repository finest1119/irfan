# QC notes: 2026-11-30-ed-d4-glove-screen (Asus render)

- Duration 31.95 s, 1080x1920 30 fps. FB copy 8.97 MB. LUFS -14.4, true peak -1.2 dB, WER 0.033.
- TTS: first attempt failed the whisper guard on beat "twist" (notes read aloud); the one allowed retry passed.
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- Manual sheet review (16 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - The gloved hand is very stylised (chunky blue mitten), reads as a glove.
  - 0:29-0:31 outro is wide and the phone small.
- mouth_noise_before_words at 0.15 s and 27.43 s (info only).
- Covers: A = 00_hook f0060 (gloved finger on the phone) "Your phone can't feel your" / "GLOVES"; B = 04_twist f0150 (silver thread tip on the sensor grid) "Touchscreen gloves hide" / "CONDUCTIVE THREAD".
- No fixes applied, nothing re-rendered.

# QC notes: 2026-11-30-ed-d3-toll-tag (Asus render)

- Duration 35.99 s, 1080x1920 30 fps. FB copy 9.86 MB. LUFS -14.2, true peak -1.6 dB, WER 0.01. TTS passed first time.
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- Effect check (requested): the read-zone cone (teal, from the gantry reader down) is visible at ~0:12-0:14 (02_read f80-f95), on a car at f90 with the ping dot. It points at empty road for a few frames before the car drives in (f80) - fine.
- Manual sheet review (18 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:17 "THE TOLL IS MATCHED" shows an empty gantry/back-office box (no car), a bit static.
  - 0:21-0:25 tag close-up with a heavily blurred background.
- Covers: A = 02_read f0090 (cone on the car) "No stopping at the toll:" / "RADIO ID"; B = 04_twist f0120 (passive tag close-up) "Many toll stickers have" / "NO BATTERY".
- No fixes applied, nothing re-rendered.

# QC notes: 2026-11-29-ed-c1-gps-einstein (Asus render)

- Duration 39.69 s, 1080x1920 30 fps. FB copy 8.98 MB. LUFS -14.3, true peak -1.2 dB, WER 0.043. TTS passed first time (notes 25a9b7e).
- qc_full auto: PASS.
- qc_v2: CHECK FAILED on the mid band: overlay spikes 6 / A-B-A 6 at frames 867-872 (~29 s).
  Checked 1:1 on overlay-only + final: the "MILES OFF IN A DAY" tracking label glides with the drifting blue dot (smooth, ~6 px/frame), no blink. Same qc_v2 false-positive pattern as elevator -> SKIP, flag for Fable.
  (low band px-flicker 42 % is in the 3D layer too, 42.76 % 3D-only: the cut, not the overlay.)
- Manual sheet review (20 frames). Minor, not fixed (SKIP, flag for Fable):
  - 0:05-0:09 and 0:37-0:39: mostly empty blue sky with a thin orbit line; the satellite is small near the top edge, touching the caption at 0:05-0:07 / the card at 0:37.
  - 0:21 "SATELLITE CLOCK" label caught mid-fade on the sheet.
- mouth_noise_before_words at 10.53 s (info only).
- Covers: A = 00_hook f0070 (phone with the blue dot) "Your blue dot needs" / "EINSTEIN"; B = 04_drift f0170 (dot drifting away) "Without relativity, GPS drifts" / "MILES A DAY".
- No fixes applied, nothing re-rendered.

# QC notes: 2026-11-30-ed-d2-bananas (Asus render)

- Duration 35.77 s, 1080x1920 30 fps. FB copy 9.31 MB. LUFS -14.2, true peak -1.1 dB, WER 0.019. TTS passed first time.
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- Effect check (requested): ethylene gas at 0:19-0:24 renders as large, soft, defocused teal circles drifting at the top/right (reads like bokeh bubbles more than wisps). They stay BEHIND the overlays; the "BANANAS MAKE IT TOO" card at 0:23 is fully readable (checked full size). Fable's call whether the look is OK -> logged SKIP.
- Manual sheet review (18 frames): no voids, no clipped text. Minor, not fixed (SKIP):
  - 0:21-0:29 bananas are close and heavily blurred (shallow depth of field), colour change green->yellow reads fine.
  - 0:31-0:35 outro store shelf: bananas small, fine.
- mouth_noise_before_words at 29.06 s (info only).
- Covers: A = 01_green f0060 (green bananas) "Your store bananas were picked" / "GREEN"; B = 03_room ~85 % (ripening room with gas) "Bananas ripen in rooms with" / "ETHYLENE GAS".
- No fixes applied, nothing re-rendered.

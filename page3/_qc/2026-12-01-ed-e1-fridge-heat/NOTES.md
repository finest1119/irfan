# QC notes: 2026-12-01-ed-e1-fridge-heat (Asus render)

- Duration 40.0 s, 1080x1920 30 fps. FB copy 9.12 MB. LUFS -14.3, true peak -1.4 dB, WER 0.0.
- TTS: transcript-only prompt (a57f6df, notes ""): passed first time, every beat aligned 100 % (the opener lines "Here's the twist," / "Be honest," now read correctly).
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- Manual sheet review (20 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:35 the freezer/lower door is mid-swing and briefly overlaps the body.
  - Heat/cold "bubbles" (orange/teal soft circles) same bokeh style as bananas.
- Covers: A = 03_coils f0080 (glowing back coils, heat bubbles) "Your fridge pushes heat into your" / "KITCHEN"; B = 04_twist f0170 (open door, cold spilling) "An open fridge makes your kitchen" / "WARMER".
- No fixes applied, nothing re-rendered.

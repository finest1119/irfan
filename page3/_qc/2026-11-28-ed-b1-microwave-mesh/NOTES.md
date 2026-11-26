# QC notes: 2026-11-28-ed-b1-microwave-mesh (Asus render)

- Duration 38.0 s, 1080x1920 30 fps. FB copy 9.61 MB. LUFS -14.2, true peak -1.0 dB, WER 0.0.
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, overlay A-B-A 0 in every band).
  32 overlay-caused reversals listed (mid band, frames 476-479, 529-530 ...): checked 1:1, the "WATER MOLECULE" label is steady over moving molecules, no blink. SKIP.
- TTS: the first 3 runs failed the whisper guard (Gemini read the director_notes aloud); passed after ef92c88 (single-line notes), audio fully regenerated.
- Manual sheet review (19 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:05 caption "INSIDE" over the light grey cabinet interior: low contrast but readable.
  - 0:15 / 0:19 "WATER MOLECULE" and 0:31-0:33 "LIGHT GETS OUT" labels caught mid-fade on the sheet (semi-transparent), normal animation.
- Covers: A = 00_hook f0100 "Why your microwave door has" / "A METAL MESH"; B = 05_light f0060 "Microwaves can't fit through" / "THESE HOLES".
- No fixes were needed, so nothing was re-rendered. Render wall 1733 s total pipeline.

# QC notes: 2026-11-27-ed-a2-checked-bag (Asus render)

- Duration 35.0 s, 1080x1920 30 fps. FB copy 9.41 MB. LUFS -14.3, true peak -1.3 dB, WER 0.061.
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, overlay A-B-A 0 in every band).
  12 overlay-caused reversals listed (mid band, frames 222-239, ~7.4-8.0 s): checked 1:1, it is the "10-DIGIT TAG NUMBER" label tracking the moving bag tag, steady, no blink. SKIP.
- Manual sheet review (18 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP, flag for Fable):
  - 0:13-0:21 captions sit over the white screening machine: white text on near-white, readable thanks to the shadow but low contrast (e.g. 0:17 "THEN IT'S SCANNED").
  - 0:11-0:15 the "READ FROM EVERY SIDE" leader line runs up through the caption.
  - 0:21 caption "REACHES THE PLANE" still over the screening scene (next shot is the sorter).
- mouth_noise_before_words at 21.7 s (info only).
- Covers: A = 04_sort f0087 "Your checked bag takes a hidden" / "RIDE"; B = 00_hook f0020 "Where your bag goes after" / "THE CURTAIN" (raw 3D, no overlays). Both within 8 words.
- No fixes were needed, so nothing was re-rendered.

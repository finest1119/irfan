# QC notes: 2026-11-27-ed-a1-autoland (Asus render)

- Duration 46.0 s, 1080x1920 30 fps. FB copy 8.58 MB. LUFS -14.3, true peak -0.7 dB, WER 0.028.
- qc_full auto: ISSUES = only "duration 46.0 s outside 70-120 s" (rule written for longer Pages; ED target is 35-45 s narration). SKIP.
- qc_v2: hard flicker checks PASS (overlay spikes 0, overlay A-B-A 0 in every band). Exit 1 came only from the same 70-120 s duration rule.
  1 overlay-caused reversal listed (mid band, frame 528, ~17.6 s): checked 1:1, frames 526-530 are a steady GLIDESLOPE label over the moving 3D scene, no blink. SKIP.
- Manual sheet review (23 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:31-0:33 "ON THE CENTERLINE" leader line crosses the "CATEGORY III" chip.
  - 0:27-0:29 a small bright runway-light square near the bottom safe line.
  - 0:37 header and caption both read "READY TO TAKE OVER".
  - 0:45 outro card repeats "Tell us below" under the chip and in the caption.
- mouth_noise_before_words at 8.57 s and 15.83 s (info only).
- Cover A: the requested hook "The pilots can't see the runway" + "IT LANDS ANYWAY" is 9 words; make_thumbnail.py caps at 8, so "The" was dropped -> "Pilots can't see the runway" / "IT LANDS ANYWAY".
  Hero frames: A = 00_hook f0060, B = 04_cat3 f0150 (raw 3D, no overlays).
- No fixes were needed, so nothing was re-rendered.

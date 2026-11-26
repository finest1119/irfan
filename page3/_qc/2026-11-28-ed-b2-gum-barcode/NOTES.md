# QC notes: 2026-11-28-ed-b2-gum-barcode (Asus render)

- Duration 39.34 s, 1080x1920 30 fps. FB copy 9.00 MB. LUFS -14.2, true peak -1.4 dB, WER 0.035.
- qc_full auto (first pass): ISSUES "clicks at 35.67 s" = MUST-FIX. Cause: the outro beat starts with a hard speech onset right after the 0.3 s digital-silence gap at the today->outro join (35.655 s); jump 0.18 in near-silence.
  FIX: 25 ms raised-cosine fade-in on voice.wav at 35.655 s (length unchanged, timings/captions/render untouched), then re-ran assemble + fb. Re-TTS of the beat was not possible (Gemini 429 quota). Script unchanged.
  qc_full after fix: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- TTS: first run failed the whisper guard on beat "scan" (notes read aloud), retry passed.
- Manual sheet review (20 frames): no voids, no clipped text. Minor, not fixed (SKIP, flag for Fable):
  - 0:31 "10-PACK OF GUM" chip sits under the laser spot while the gum pack is to the right of it.
  - 0:33-0:35 store shelves read like bookshelves (generic boxes).
  - 0:33-0:39 white captions over the white store interior: readable, low contrast.
- mouth_noise_before_words at 29.14 s (info only).
- Covers: A = 00_hook f0095 (gum under the laser, zoom 1.3) "A pack of gum changed" / "EVERY STORE"; B = 04_first f0260 "The first barcode ever scanned" / "WAS GUM".

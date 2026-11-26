# QC notes: 2026-11-29-ed-c3-tv-remote-ir (Asus render)

- Duration 38.24 s, 1080x1920 30 fps. FB copy 9.72 MB. LUFS -14.3, true peak -1.0 dB, WER 0.0. TTS passed first time.
- qc_full auto: PASS. qc_v2: PASS (no overlay spikes / A-B-A, overlay-caused 0).
- Manual sheet review (19 frames): no voids, no clipped text, labels on the right objects. Minor, not fixed (SKIP):
  - 0:07-0:11 the blurred visible-spectrum bar sits below the 80 % safe line (bottom of frame).
  - 0:19-0:21 the IR-sensor close-up is dark/maroon (TV edge macro), reads a bit abstract.
- Covers: A = 05_try f0150 (phone camera showing the purple IR flash) "Your phone camera can see" / "THIS LIGHT"; B = 02_code f0080 (remote beam to TV) "Your TV remote flashes" / "INVISIBLE LIGHT".
- No fixes applied, nothing re-rendered.

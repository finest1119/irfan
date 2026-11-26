# QC notes: 2026-11-30-ed-d5-qr-code (Asus render)

- Duration 40.06 s, 1080x1920 30 fps. FB copy 9.33 MB. LUFS -14.3, true peak -0.9 dB, WER 0.025.
- TTS: needed ED's fix b860667 (longer "tip" line, minimal notes). All old audio was cleared so every beat uses the new notes. First run failed the guard again on "tip"; the one allowed retry passed (all beats from the same notes).
- qc_full auto: PASS. qc_v2: PASS (overlay spikes 0, A-B-A 0, overlay-caused 0).
- Effect check (requested): no white "camera flash" is visible anywhere (whole-video brightness scan: only cut jumps). The scan moment shows as the phone's viewfinder brackets turning orange -> teal plus a check icon at ~0:02 (and again in the outro). If a flash was intended it isn't rendering -> Fable's call; logged SKIP.
- Finder-square glow at 0:25-0:27 renders well.
- Manual sheet review (20 frames): no voids, no clipped text. Minor, not fixed (SKIP):
  - 0:01-0:03 / 0:35-0:39 captions sit over the orange band with dark dots (readable).
- Covers: A = 00_hook f0080 (patched QR + phone scan) "QR codes can scan while" / "MISSING A CHUNK"; B = 03_twist f0140 (close QR with patch) "Up to 30% can be" / "RESTORED".
- No fixes applied, nothing re-rendered.

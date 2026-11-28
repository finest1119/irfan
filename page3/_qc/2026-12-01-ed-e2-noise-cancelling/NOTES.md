# Noise cancelling

**READY** · 38.70 s · Facebook copy 9.37 MB (9,374,898 bytes) · −14.2 LUFS integrated · −1.1 dBTP · WER 1.9%.

| Check | Result |
| --- | --- |
| qc_full | PASS. The master is 1080 × 1920 at 30 fps with AAC audio. The HEVC Facebook copy has the same 1,161 video frames. No black frames, freezes, clipping, clicks or extended internal pauses were detected. |
| qc_v2 | PASS across all four bands. Zero unexpected overlay spikes, overlay reversals or overlay-caused reversals. |
| Visual review | Reviewed both full-video sheets, the 12-frame sheet and the extracted spike frames. The furnished living room stays in view. Captions, cards and chips are legible within the guides. The microphone, opposing waves and cancellation follow the narration. |

## Findings

| Time | Verdict | Observation |
| --- | --- | --- |
| 00:00.15–00:00.99 | SKIP | Whisper transcribed “canceling.” The script and caption use “cancelling.” The two spellings have the same pronunciation. |
| 00:00.17–00:38.30 | SKIP | The 148 distinct spike frames show timed caption highlights, overlay entrances and shot cuts. All were extracted at 1080 × 1920 and reviewed. The 98 mid-band reversals on the master span 00:15.90–00:33.90. The moving 3D scene also triggers this measure, and qc_v2 attributes zero reversals to an overlay. Frame numbers and times are in the [spike index](../../../output/noise-cancelling/qc/spike_review/frames.tsv). |
| 00:15.50–00:16.00 | SKIP | Whole-reel Whisper returned “flip.” An unprompted transcription of this beat from the final audio recovered “flipped upside down,” matching the caption and script. |
| 00:15.53–00:19.00 | SKIP | The “FLIPPED WAVE” leader sits just above the moving teal wave. The amber wave stays on a separate, lower row. |
| 00:32.30–00:34.20 | SKIP | The first part of the pullback crops the outer earcup at the left edge. The headband and stand stay visible, and the camera clears the cup smoothly. |
| 00:37.82–00:38.70 | SKIP | The 0.88 s quiet tail holds on the closing question. |

**MUST-FIX candidates** — none. Reviewed the existing master with no media repairs or new render.

## Covers

| File | Raw source and crop | Visible subject |
| --- | --- | --- |
| [Cover A](cover_A.jpg) | `frames_v2/05_outro/0112.jpg`, zoom 1.45, focus 0.34, 0.59 | Both earcups and the headband on the stand. The later frame gives the left cup more room. |
| [Cover B](cover_B.jpg) | `frames_v2/00_hook/0105.jpg`, zoom 1.48, focus 0.34, 0.51 | Whole headset next to the repeating amber hum. |

Both covers use layout B (`ed_b`) and the supplied hook wording. Raw paths are relative to `output/noise-cancelling/`.

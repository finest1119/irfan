# Phone charging

**READY** · 36.45 s · Facebook copy 9.14 MB (9,144,454 bytes) · −14.3 LUFS integrated · −0.7 dBTP · WER 3.7%.

| Check | Final result |
| --- | --- |
| qc_full | PASS. The 1080 × 1920 master is 30 fps with AAC audio. The HEVC Facebook copy decoded through all 1,093 frames. The scan found no black frames, freezes, clipping, clicks or extended internal pauses. |
| qc_v2 | PASS across all four bands. Zero unexpected overlay spikes, overlay reversals or overlay-caused reversals. |
| Visual review | Reviewed both full-video sheets, the 12-frame sheet and the extracted spike frames. The bedside table, handset, cable and gauge establish the scene throughout. The corrected pointers land on their targets, the text is legible and the graphics follow the narration. |

## Findings

| Time | Verdict | Observation |
| --- | --- | --- |
| 00:00.17–00:36.03 | SKIP | Extracted all 155 distinct spike frames at 1080 × 1920. Caption highlights, cards, chips and cuts account for the expected events. The pullback flags are detailed below. [Frame index](../../../output/phone-charging/qc/spike_review/frames.tsv) |
| 00:01.39–00:02.31 and 00:21.83–00:22.19 | SKIP | Whisper wrote “80%” twice where the script spells out “eighty percent.” Number formatting accounts for the full WER. All 107 caption words match the script. |
| 00:07.71–00:11.66 | MUST-FIX — fixed | The FAST PHASE leader reached into the captions above the gauge. Its dot now tracks the rising teal fill. |
| 00:13.94–00:18.55 | MUST-FIX — fixed | The VOLTAGE LIMIT leader missed the illuminated line and reached into the captions. Its dot now follows the left end of the amber line. |
| 00:18.80–00:25.59 | SKIP | The chapter card opens at the beat’s default timing because the cue word is “pause” and the narration says “hold.” The title describes the overnight hold. A separate “FINISHES BEFORE YOU WAKE” chip marks the change at 00:23.45. |
| 00:25.59–00:31.56 | SKIP | The close-up crops the left of the handset while keeping the full gauge in view for the explanation of battery wear. |
| 00:29.59–00:31.56 | MUST-FIX — fixed | The LESS TIME AT 100% leader reached into the captions. Its dot now follows the charge shown inside the gauge. |
| 00:32.43–00:32.80 and 00:33.07 | SKIP | Lower-band spikes occur at frames 974–985 and 993. The master has ten raw reversals and the base has eleven. Native adjacent frames show the drawer edge and knob moving continuously up and right during the camera pullback. [Native crops](../../../output/phone-charging/qc/spike_review/outro_native_crops.jpg) |
| 00:35.57–00:36.45 | SKIP | The closing shot holds for 0.88 s after the voice ends. |

**Repair.** Updated the battery tracking coordinates in six generated chunks for three shots, then rebuilt the master and Facebook copy from the existing render and audio. Verified the endpoints on all 288 fully visible label frames. The closest approaches to the captions were 107 px for FAST PHASE, 39 px for VOLTAGE LIMIT and 273 px for LESS TIME AT 100%. Both QC checks passed again. The original exports and tracking files are in `output/phone-charging/old/pre_label_fix/`. TTS succeeded on its first run. No MUST-FIX items remain. [Corrected label frames](../../../output/phone-charging/qc/manual/final_labels.jpg)

## Covers

Both covers use layout C (`ed_c`) with the supplied hook wording. Raw paths are relative to `output/phone-charging/`. Dot coordinates are pixels on the 1080 × 1920 cover.

| File | Raw source and crop | Verified callout targets |
| --- | --- | --- |
| [Cover A](cover_A.jpg) | `frames_v2/02_slow/0106.jpg`, zoom 1.23, focus (0.405, 0.396), text top 285 px | VOLTAGE LIMIT (755, 887) on the amber line, PHONE (348, 1300) on the handset, CHARGING CABLE (326, 1510) on the cable. |
| [Cover B](cover_B.jpg) | `frames_v2/03_twist/0188.jpg`, zoom 1.58, focus (0.34, 0.393) | BATTERY GAUGE (828, 973) on the full gauge, CABLE PLUG (183, 1295) on the plug seated in the phone. |

# QC notes for Why the Tray in Your Microwave Spins

**Release check passed. Open MUST-FIX items: 0.** Both QC tools ran on the final master after the camera and audio fixes. The Facebook upload copy decoded from beginning to end.

| Measurement | Final result |
| --- | --- |
| Picture | 1080 × 1920, 30 fps, 1,124 frames, 37.47 s |
| Files | H.264 master 39,719,180 bytes. HEVC/hvc1 Facebook copy 9,519,268 bytes (9.52 MB), with mono AAC at 48 kHz. |
| Voice | Sadaltager, 37.45 s including pauses. One TTS run. All six beats passed on their first takes. |
| Captions | 103 words in 28 chunks. Each beat aligned at 100%, and all caption spellings match the script. |
| Audio QC | −14.3 LUFS integrated, −1.2 dBTP, 0.15 s lead, 0.87 s tail. The final check reported zero clicks, pre-word mouth noises, or internal pauses over 0.75 s. |
| QC results | `qc_full` passed. Black and frozen spans: 0. `qc_v2` passed in all four screen bands. Unexpected spikes in the final, base, and overlay streams: 0. Overlay A-B-A reversals and overlay-caused reversals: 0. |

## Findings and fixes

| Reel time | Finding and disposition |
| --- | --- |
| 0:01.65–0:02.21 | **SKIP.** Full-reel speech recognition returned “microwave soup” for “microwaved soup,” giving one substitution in 103 words (1.0% WER). The isolated take aligned as “microwaved,” and the burned caption has the full word. |
| 0:04–0:05.93 | **SKIP.** The push toward the bowl crops the far right of the control panel. The bowl, door, and complete hook stay visible. |
| 0:07.03–0:11.10 | **MUST-FIX, resolved.** Compared all 122 distinct first-pass spike frames with their immediate neighbors at native pixel size. All came from the foreground door perforations during the camera move. Sixty-four also crossed the spike threshold in the final video. Reframed the wave shot inside the cavity using the existing camera parameters and re-rendered only shot 1, `01_waves`. The final export has zero unexpected spikes. [First-pass frame and crop index](../../../output/microwave-turntable/qc/first_pass/native/crop_index.tsv) |
| 0:12.60–0:18.87 | **MUST-FIX, resolved during preview.** Moved the soup close-up inside the front rim to clear a dark foreground obstruction. Checked the revised beginning, middle, and end. Rear water molecules fall out of focus while the foreground models remain recognizable. |
| 0:24.57–0:30.20 | **PASS.** The CENTER leader ends on the bowl's rotation axis. The moving wave ribbons leave the leader, captions, and twist card legible. |
| 0:35.02 | **Fixed.** Reduced an isolated burst by 12 dB with short ramps between 35.015 and 35.039 s, in both the joined voice and cached outro take. Sample count and timing stayed identical. The final audio QC cleared the flag. |
| 0:36.10–0:37.47 | **PASS.** The question and “Tell us below” remain legible on the closing kitchen shot, including the last frame of the upload copy. |

Reviewed all 37 one-second samples across three JPEG sheets, all 12 samples on the v2 sheet, and both covers. All six shots show the intended kitchen, cutaway, or molecule view. Captions, cards, and chips stay inside the guides. The initial render took 1,529 s. The wave-shot repair took 246 s for 200 frames with two Blender processes.

## Cover frames

Both variants use the approved `ed` preset and layout A. Frame numbers are local to the named shot.

| Cover | Raw frame | Setup | Payoff |
| --- | --- | --- | --- |
| [A](cover_A.jpg) | [05_outro / 0148.jpg](../../../output/microwave-turntable/frames_v2/05_outro/0148.jpg) | Why your microwave tray | SPINS |
| [B](cover_B.jpg) | [04_twist / 0087.jpg](../../../output/microwave-turntable/frames_v2/04_twist/0087.jpg) | The turntable's center | STAYS PUT |

The local post sheet contains the caption, hashtags, engagement comment, and AI-label instruction. [Post sheet](microwave%20turntable.post.md) · [Claim-by-claim fact-check](FACTCHECK.md)

## Workspace exception

Blender resolved one relative preview path to `C:\output\microwave-turntable\preflight\stills_v2` and wrote three intermediate PNGs there. The corrected previews and every deliverable are in the project workspace. Cleanup of the three external PNGs is pending permission.

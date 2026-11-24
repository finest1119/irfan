# WJH build log

## 24 Nov 2026 — Thu 26 set + Nvidia bonus
- **turkey fryer fire** (Fenrir, 82.3 s): qc_v2 + qc_full PASS; Fable QC approved. Scheduled 25 Nov 21:00 (Graph API).
- **ship collision** (Sadaltager, 85.4 s): Gemini TTS 429 until 16:00 reset; a hallucinated takeaway take ("three people drowned") was rejected. Fixes: stray syllable at ~67 s muted, 1.1 s pause trimmed, "ABOUT 2 MINUTES" card moved, "PARKED CARS" chip cued earlier. Rudder-beat upgrade skipped (QC tiers rule). Fable QC approved; scheduled 26 Nov 01:30.
- **high rise fire** (87.6 s): qc_full PASS; only must-fix items repaired. Fable QC approved; scheduled 26 Nov 08:00. Pending: listen-check of "Taiyuan" in the outro (~1:21; ASR hears "Taiwan"/"Taeyeon").
- **Nvidia CEO (bonus)** (Sadaltager, 89.4 s): first WJH one-shot (`scene_lib_v2_campus.py`, one continuous camera through all 9 beats). Fable QC approved; published 24 Nov ~20:15, reel/3361280247403397.
- Process notes: Fable 5-hour limit hit ~18:45 (reset 19:40); the Opus build agent stalled 4× while sitting in long waits (fixed by giving a fresh agent a short brief with background jobs).

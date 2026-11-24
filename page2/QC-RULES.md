# Self-Made Engineer — QC rules for finished videos

## Fix vs skip (Irfan, 24 Nov 2026, all Pages, to save tokens)
"kalau macam ada very small error kan bila QC tu, aku rasa maybe tak perlu nak repair lah kot. Boleh jimat sikit token."

**MUST FIX before posting**
- wrong or fabricated facts and narration
- on-screen typos and wrong numbers (including HUD/units)
- broken, black or frozen frames, and flicker
- audio glitches
- pauses over ~1.2 s
- unreadable text
- policy risk
- caption and AI-label problems
- one-shot rule breaks: a hard cut outside a planned move, or a hold longer than 10 s

**SKIP (log in the episode's QC notes only, no repair)**
- tiny visual artifacts under ~1 s
- Whisper mishearing when the audio itself sounds fine
- pauses between 0.75 and 1.2 s
- cosmetic imperfections and optional upgrades

This applies to QC of FINISHED videos only. It does **not** lower the v2 visual standard for building new
assets/worlds (e.g. the CC0 upgrade of Bolts, Torque and Mercer Hollow).

## Checks (unchanged)
qc_v2 + qc_full (auto) + `page2/tools/qc_oneshot.py` (no hard cuts outside planned travel/snap windows; no hold
> 10 s) + Fable looks at every contact sheet (1 frame every 2 s — Irfan, 24 Nov 2026; `qc_full.py` default, env QC_STEP overrides), then applies the fix/skip rule above.

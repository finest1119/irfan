# HANDOFF: 3D explainer video pipeline (v1) + video #1 only

Owner: Irfan · Written 22 Nov 2026 · Builder: Opus sub-agent · Reviewer: main session

## Goal
Build a reusable pipeline that turns ONE episode spec (JSON) into a finished 9:16 reel, then
produce **only video #1** from `calendar.md` (Mon 23 Nov, slot 1, keyword "highway pileup").
Do NOT make videos #2/#3. Do NOT post anything to Facebook/YouTube.

## Environment (already set up)
- Repo: `/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan` (git, PUBLIC repo).
- Python venv: `.venv/bin/python` (3.9) with `google-genai`, `faster-whisper`, `python-dotenv`.
- Blender 5.3: `/Applications/Blender.app/Contents/MacOS/Blender` (run headless: `-b -P script.py -- args`).
- ffmpeg/ffprobe on PATH. Mac M2 Pro, ~30 GB free disk.
- `.env` has `GEMINI_API_KEY` (load with python-dotenv). NEVER print, log or commit the key.
- `.gitignore` already ignores `.env`, `.venv/`, `output/`, `screenshots/`.

## Pipeline design (reusable for every future episode)
```
pipeline/
  make_episode.py        # orchestrator: episode.json -> output/<keyword>.mp4
  tts.py                 # Gemini TTS -> voice.wav
  captions.py            # faster-whisper word timings -> captions.json (2–4 words/chunk)
  blender/scene_lib.py   # procedural low-poly scene builders (road, cars, fog, globe, text cards...)
  blender/render_episode.py  # reads episode.json + timings, builds shots, renders PNG/MP4 segments
  README.md              # how to make a new episode (written for a cheaper model to follow)
episodes/2026-11-23-1-highway-pileup/episode.json   # script + shot list for video #1
output/                  # renders (gitignored)
```
- `episode.json` holds: keyword, title, FB caption + hashtags, VO script split into beats,
  and for each beat a `shot` = {scene builder name + params}. Future videos must only need a
  new episode.json (plus new scene builders occasionally).
- TTS: model `gemini-3.8-flash-tts` (fallback `gemini-3.1-flash-tts-preview` only if 3.8 errors).
  Use `client.models.generate_content(..., config=GenerateContentConfig(response_modalities=["AUDIO"],
  speech_config=SpeechConfig(voice_config=VoiceConfig(prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=...)))))`.
  Output is raw PCM (24 kHz, 16-bit mono) — wrap to WAV. Pick a clear, calm-but-urgent
  English news-explainer voice; put a short style instruction in the prompt (e.g. "Say in a
  clear, calm, serious documentary tone:"). One TTS call per beat is fine (easier timing).
- Captions: faster-whisper `base.en` (model download from Hugging Face is OK), word timestamps,
  burned in centered, 2–4 words per chunk, bold white with dark outline, safe area (avoid top
  ~12% and bottom ~20% of frame, FB UI overlaps).
- Visuals: **Blender only, procedural, original** (no news footage, no downloaded models needed).
  Low-poly stylised look, navy/teal palette with red accents (matches the Page branding:
  `branding/cover-a.png`). EEVEE, 1080x1920, 30 fps. Keep render time reasonable
  (low samples, simple lighting; target < ~20 min total render on M2 Pro).
  Gentle camera moves, subtle effects, no graphic content: no injured people, no wreck gore,
  no fire carnage — cars can stop/bump abstractly, warning lights, fog.
- Assembly (ffmpeg): visuals + voice + captions. No music in v1 (leave a `music` option in
  episode.json, default null). Loudness normalise voice to about -14 LUFS.
- Export filename = main keyword: `output/highway pileup.mp4` (also keep `output/highway-pileup/` working dir).
- Also write `output/highway pileup.post.md` with title, FB caption, hashtags, and the
  sources used for the hook.

## Video #1 content rules (from calendar.md — mandatory)
1. Length 70–120 s (must be > 60 s).
2. Hook (first 3 s) = verified fact only:
   On 10 November 2026, dense fog triggered two pile-ups involving 86 vehicles on Bulgaria's
   Trakia motorway near Yambol. (Sources: Euro Weekly News 10 Nov 2026, BTA, HNGN.)
   Do NOT state a death toll figure (reports differ; rule 4 = no casualty focus).
3. Body = general explainer of why highway pileups happen (fog/visibility, speed vs. stopping
   distance, following distance, reaction time, chain reaction, ice). Use "usually/could/often",
   never claim what specifically caused this crash beyond "dense fog was reported".
4. No blaming named people/companies/authorities. No graphic visuals.
5. Title + thumbnail must match the content (no clickbait).
6. Structure: Hook → Message (what usually causes this) → Metaphor/visual (e.g. dominoes /
   a line of people stopping suddenly) → Conclusion with a practical safety takeaway → end with
   a QUESTION to drive comments, and the last line loops back to the hook.
7. Original visuals only.
8. English voiceover for a US/UK audience.

## Deliverables
1. Working pipeline code under `pipeline/` + `episodes/.../episode.json`.
2. `output/highway pileup.mp4` (9:16, 70–120 s, captions burned in, audio clear).
3. `output/highway pileup.post.md`.
4. `pipeline/BUILD-LOG.md`: short self-log — what you built, decisions, commands to re-run,
   render time, any problems/limitations, and API cost estimate.
5. Do NOT git commit or push; the reviewer will.

## Verification before reporting done
- ffprobe: duration 70–120 s, 1080x1920, has audio stream.
- Extract ~6 frames across the video (e.g. `ffmpeg -ss T -frames:v 1`) to
  `output/highway-pileup/qc/` and look at them: captions readable and inside safe area,
  scenes not blank/black, nothing graphic.
- Confirm captions match the spoken words and are in sync (spot-check timings).

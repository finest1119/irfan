# Explainer video pipeline (Blender + Gemini TTS)

One `episode.json` in, one finished 9:16 reel out. Everything is procedural: no footage, no downloaded models.

```
.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json
```

Output:
- `output/<keyword>.mp4` (1080x1920, 30 fps, captions burned in, voice at about -14 LUFS)
- `output/<keyword>.post.md` (title, FB caption, hashtags, sources, script)
- `output/<slug>/` working dir: `audio/`, `captions/`, `captions.json`, `frames/`, `segments/`, `logs/`, `stills/`, `qc/`

## Channel voice & script style (decided 22 Nov 2026 — use for EVERY new episode)

- `tts.voice`: **`Fenrir`** (chosen by Irfan). Episode 1 used Charon; do not reuse Charon.
- `tts.director_notes` (start from this, then add a `Pronunciation:` line for names in the episode):
  > Male documentary-style news explainer for a US/UK social video. Confident, punchy and fast
  > (about 170–185 words per minute), conversational but serious. Short sentences, a brief dramatic
  > pause before key facts, lively intonation, never monotone or salesy.
- Script style (inspired by the reference reel's *style*, never copying its words or voice):
  short punchy sentences; hook = verified fact + a curiosity question; a numbered structure
  ("Here are the three big reasons. One… Two… Three…") where it fits; end with the comment
  question, a share CTA ("Send this to someone who…"), and a last line that loops to the hook.
- At ~180 WPM, 200–240 words ≈ 70–80 s; aim for **230–300 words** to stay inside 70–120 s.

## How to make a new episode (step by step)

1. **Copy the last episode folder**: `episodes/2026-11-23-1-highway-pileup/` to `episodes/<date>-<slot>-<slug>/`.
2. **Edit `episode.json`**:
   - `keyword`: the main keyword. This becomes the file name (`output/<keyword>.mp4`).
   - `slug`: same as the keyword but with dashes (used for the working folder).
   - `title`, `fb_caption`, `hashtags`, `sources`: the hook fact must be verified and its sources listed.
   - `beats`: the voiceover, split into 7–10 beats. Aim for **230–300 words in total** (about 75–100 s at Fenrir pace).
     - Beat 1 = the hook: the verified news fact in the first sentence, with no intro.
     - Middle beats = the general explainer ("usually", "could", "often"); never say what caused the real event.
     - A metaphor beat (dominoes, etc.).
     - A takeaway beat (practical safety advice).
     - The last beat = a question for the comments, and a last line that loops back to the hook.
   - Each beat has a `shot`: `{"builder": <name>, "params": {...}}`. Available builders are listed below.
   - Leave `tts`, `render`, and `music: null` as they are, unless you have a reason to change them.
3. **Run it**: `.venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json`. It takes about 12–13 min: about 11 min of render with 4 parallel Blender processes, plus about 1 min of assembly.
   - To run steps one by one, use `--steps tts`, `--steps captions`, `--steps render`, `--steps assemble,post`.
   - To re-do one beat's voice, delete `output/<slug>/audio/beat_<id>.wav`, then run `--steps tts,captions`.
   - To re-render one shot, delete `output/<slug>/frames/NN_<beat>/`, then run `--steps render,assemble`.
     If you change the voice/timings, delete **all** of `frames/`, because the shot lengths change.
4. **Preview shots before the full render**. This is cheap, at about 1 s per still:
   ```
   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P pipeline/blender/render_episode.py -- \
       episodes/<id>/episode.json output/<slug> <SHOT_INDEX> --still 60,200 --scale 0.5
   ```
   The stills go to `output/<slug>/stills/`. Open and look at them.
5. **QC**:
   - `ffprobe` should show a duration of 70–120 s, 1080x1920, and an audio stream.
   - Grab about 6 frames (`ffmpeg -ss T -i out.mp4 -frames:v 1 qc/T.png`) and look at them.
   - Check that the captions match the speech (`captions.json` → `alignment` shows what whisper heard).

## Builders (`pipeline/blender/scene_lib.py` → `BUILDERS`)

| builder | what it shows | params |
|---|---|---|
| `fog_highway` | queue of stopped cars, blinking hazards, dense fog, one car arriving slowly | `cars`, `fog` (0–1+), `card`, `subcard`, `camera`: `dolly_in` / `crane_up` |
| `chain_topdown` | top-down column of cars braking one after another (brake lights ripple back) | `cars`, `card` (appears on the word "chain") |
| `visibility` | chase cam in thick fog, teal "~50 m" marker, hazard-lit car emerging | `distance_label`, `card`, `subcard` |
| `stopping_distance` | reaction strip (teal) then braking strip (red) grow as a car stops | `reaction_m`, `braking_m`, `card`, `subcard` (syncs on the words "reaction", "braking", "seventy") |
| `following_gap` | tailgating car, shrinking red gap bar, late braking, cars end touching (no damage) | `card` (syncs on "stops") |
| `ice_road` | dry lane vs icy lane braking side by side | `card`, `subcard` |
| `dominoes` | row of dominoes toppling in sequence | `count` (starts on the word "brakes") |
| `safety_tips` | night fog drive, lights on, "4+ SEC" gap, numbered tips | `tips` (list), `cues` (list of words that trigger each tip) |

**Syncing visuals to the voice**: inside a builder, `ctx.word_time("word", default_frac)` returns the
frame where that word is spoken in this beat (from `captions.json`). If the word is not found, it falls back to
`default_frac × shot length`.

**Adding a new builder**: write `def b_name(ctx, p):` in `scene_lib.py`. It must call `fog(...)`,
`setup_world(...)`, add a light, and call `ctx.camera(...)`. Add your objects, then keyframe them with
`kf()` / `drive()`. Add on-screen text with `ctx.card()` / `ctx.text()`; these stay in the upper safe area
(y ≈ 0.13–0.40). Register the builder in `BUILDERS`.

## Rules baked into the pipeline
- **Captions**: the text comes from the script, and the timings come from faster-whisper `base.en`. Chunks are 2–4 words,
  Arial Black with a dark outline. They are centred at y=1290 px, and the code asserts they stay inside the
  12%–80% safe band. Words with digits are shown in yellow.
- **TTS prompt format**: use `### DIRECTOR'S NOTES ... ### TRANSCRIPT <text>`. A plain "Say in a … tone:"
  prefix gets **read aloud** by `gemini-3.8-flash-tts`, and `system_instruction` is rejected. `tts.py` runs a
  whisper check after each beat and retries if extra words were spoken.
- **Visuals**: keep them non-graphic. No injured people, wreck damage or fire. Cars may stop and touch abstractly.
- **Secrets**: the key comes from `.env` via python-dotenv and is never printed. `output/` is gitignored.

## Files
- `make_episode.py`: the orchestrator (tts → captions → render → assemble → post).
- `tts.py`: Gemini TTS per beat. It joins the beats with 0.3 s pauses and writes `timings.json` (shot boundaries) and `usage.json`.
- `captions.py`: alignment, chunking, caption PNGs and the `list.ffconcat` overlay stream.
- `blender/render_episode.py`: builds and renders one shot in headless Blender (resumable PNG frames).
- `blender/scene_lib.py`: the materials (shader distance fog, glow billboards), car model, road, camera-locked cards, and builders.

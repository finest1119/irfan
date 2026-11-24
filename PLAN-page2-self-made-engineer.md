# PLAN: Page 2 — "Self-Made Engineer" (bizarre but workable builds at home)

Written 24 Nov 2026 by the What Just Happened (WJH) session. Status: PLAN, core decisions made by Irfan 24 Nov 2026 (see section 0).
Runs on Windows laptop #1 (RTX 3050), same Claude account (Max $100), separate Claude session/agent.

## 0. Decisions by Irfan (24 Nov 2026)
- **Page name: Self-Made Engineer.**
- **One recurring character** in every reel; his **outfit changes with the job** (lab coat for science builds,
  electrician gear for wiring, welder mask/apron, plumber, farmer, etc.). Same face/body/name so he is recognisable.
- **Continuity between episodes:** it is one ongoing story on one property. Everything he built stays in the world:
  if day 1 is the windmill, later episodes show the windmill turning in the background, and the script calls back
  ("the windmill we built on Monday now powers this"). New builds can depend on old ones (windmill → battery shed →
  workshop tools → electric gate ...).
- **Ideas must be bizarre but look workable** — the goal is comments like "this guy is making crazy things":
  surprising, a bit extreme, yet grounded in real physics. Fable fact-checks that it could really work and notes limits.
- Engagement hooks: end each reel by teasing the next build, ask viewers what he should build next, and use
  viewer suggestions as future episodes ("You asked for it").

### One-shot editing (Irfan, 24 Nov 2026 — for Page 2 and later new Pages; WJH keeps its cut-based style)
- No cuts: the whole reel is ONE continuous camera move through the property. Between beats the camera
  "whips" fast (whoosh) from one spot to the next and settles, like the reference reels.
- Implementation: the episode is rendered as a single Blender shot in the persistent world; the camera has one
  keyframed path with slow "hold" segments (during narration) and 0.3–0.5 s fast eased travel segments with
  motion blur between them. Builds animate in place when the camera arrives (parts pop/assemble).
- Pipeline change needed: `render_episode_v2` gets a "oneshot" mode (one scene, per-beat camera waypoints from
  voice timings) instead of one scene per beat; overlays/captions unchanged (2D). QC adds a check that there are
  no hard cuts (frame-difference spikes only allowed inside whip segments).
- Because everything is in one scene, the world must stay light enough for 4 GB VRAM (instancing, LOD).

### How continuity is implemented
- `page2/world_state.json`: the property map + list of completed builds (id, position, episode, short description,
  dependencies). The world builder loads it and places every finished build in the scene (animated: turbine spins,
  lights on at night, water flowing).
- Each episode adds exactly one build to world_state after it is posted. Episode numbering "Day 1, Day 2 ..." shown
  as a small chip.
- `page2/character.json`: fixed character definition + outfit library (colour/props per job). Episode spec picks
  `"outfit": "electrician"` etc.
- Script template gets a "previously" line (one sentence, optional) and a "next time" teaser.
- Season plan: group builds into arcs (Power week, Water week, Heating/cooling week, Crazy house upgrades) so the
  dependency chain makes sense.

## 1. What the reference reels do (frames reviewed)
- reel/2441291916610073 (134 s): backyard wind turbine. Story = GOAL → FIX → PROBLEM → FIX … → "SYSTEM COMPLETE"
  (chips: "GOAL: MORE POWER", "FIX: TALLER TOWER", "FIX: TAIL VANE", "FIX: AUTO PROTECTION", "PROBLEM: VIBRATION",
  HUD bars for rotor RPM / battery %).
- reel/1127512690262242 (135 s): micro-hydro from a stream behind a house (elevation difference, intake grate,
  pipe, turbine wheel, lights come on).
- reel/1720738693104170 (20 s): spring-assisted stairs (short, realistic render, tiny yellow captions).
- Common: simple-realistic 3D in ONE persistent world (house + yard), one recurring worker character (+ dog),
  camera moves around the build, 2D chips/HUD overlays, word-highlight captions. Same technique as our v2 pipeline.

## 2. Concept
"What if you built ___ at home?" — one unusual but real engineering idea per reel, told as a build story:
hook (the bizarre idea) → how it works → 3–4 problems and fixes → final system working → comment question.
Evergreen (no news hooks), 75–135 s (must stay > 60 s), English VO, US/UK audience.
Original brand: own name, own character design, own house/yard — never copy the reference channel's assets.

## 3. Name
**Self-Made Engineer** (chosen by Irfan).

## 4. Topic bank (first 30; 5/day = 6 days)
Energy: backyard wind turbine · micro-hydro from a stream · solar water heater from black pipe · biogas digester ·
gravity battery · pedal generator · solar tracker · thermoelectric stove charger
Water: ram pump (pumps uphill with no electricity) · rainwater harvesting tank · fog net · solar still ·
greywater garden · hand-dug well with rope pump · water tower pressure
Heating/cooling: earth tube cooling · rocket mass heater · root cellar · walipini (sunken greenhouse) ·
windcatcher tower · ice house · trombe wall
House/yard hacks: spring-assisted stairs · dumbwaiter lift · rotating house idea · underground garage lift ·
automatic chicken door · tidal/pond aerator windmill · zip-line cargo · composting toilet
Each needs a Fable fact-check (does it really work, typical numbers, limits) — no fake "free energy" claims.

## 5. Production system (copy of WJH, changes only)
- Repo: new folder/branch `page2/` reusing `pipeline/` (v2 builders, overlays, qc_v2, qc_full, tts, gen_image).
- World kit to build once (Opus): suburban house + yard + stream + shed, worker character, tool/props library,
  HUD overlay types (GOAL/FIX/PROBLEM chips, gauge bars). Then every episode reuses it → cheap per video.
- SOP: Fable 5.2 (medium) = idea research, fact-check, script, final QC. Opus 5.5 (medium) = build/render.
- Voice: rotate Fenrir / Sadaltager / Orus (or pick 2 fixed "host" voices for this Page).
- Posting: Graph API (`tools/fb_schedule_reel.py`), AI label ON, Public, hashtags, engagement comment
  (`tools/page_comment.py --auto`), own FB_PAGE_ID/FB_PAGE_TOKEN in that laptop's `.env`.
- Cadence: start 3/day for 3 days, then 5/day (MYT 20:00, 22:30, 01:30, 05:00, 08:00 ≈ US morning→evening).
- Safety line in caption: "Illustration only — check local codes and safety before building anything."

## 6. Windows laptop setup (day 1)
1. Install Claude Code (same account), Git, Python 3.11, Blender (same version as Mac: 5.3), ffmpeg, Codex CLI.
2. Clone repo; create `.venv`; `pip install google-genai faster-whisper python-dotenv pillow numpy`.
3. `.env` (not in git): GEMINI_API_KEY, FB_PAGE_ID, FB_PAGE_TOKEN for the new Page.
4. One Opus task: make the pipeline cross-platform (Blender path, fonts, `sed`/shell bits, HEVC encoder),
   then render one WJH episode as a benchmark: time per frame, VRAM use (RTX 3050 = 4 GB → cap scene size,
   1–2 parallel Blender processes).
5. Create scheduled tasks on that laptop (daily build + auto comments). Laptop must stay awake, lid open.

## 7. Open decisions for Irfan
- Character look/name (e.g. a nickname viewers can use in comments) and whether he has a pet sidekick.
- Reel length: ~75–90 s (cheaper, 5/day easy) or ~130 s like the references (more watch time, ~1.5× render).
- Create the FB Page + give Graph API token (same flow as WJH).

## 8. Risks
- 4 GB VRAM and unknown render speed on the laptops → benchmark first.
- "DIY electricity/gas" topics: keep educational, add safety line, no step-by-step dangerous instructions.
- Quota: 3 Pages × 5/day ≈ half the weekly Max quota by current estimates → ramp up gradually and measure.

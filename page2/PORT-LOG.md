# Windows port log (Self-Made Engineer laptop) — 24 Nov 2026

Scope: make the shared pipeline cross-platform without changing WJH output on the Mac, add an asset fetcher.
Nothing committed, nothing rendered, Blender not run. Live files that WJH was using are **not** edited in place:
their modified copies wait in `page2/port-wip/` (see `page2/port-wip/PATCH-NOTES.md`).

## Files
### New, already in place (nothing live imports them until the swap-in)
| file | why |
|---|---|
| `pipeline/platform_cfg.py` | Resolves `BLENDER_EXE`, `FFMPEG_EXE`, `FFPROBE_EXE`, overlay fonts (`OVERLAY_FONT_SET` / `OVERLAY_FONT_BOLD|HEAVY|DEMI` as `path#ttc_index`), `CAPTION_FONT`, `SUB_FONT`, `NUMBER_FONT`, `SCHEDULE_TZ`, venv python. Order: env var → `config_local.json` → `.env` (only these keys) → per-OS default. macOS defaults = the old hard-coded paths. `python pipeline/platform_cfg.py` prints the resolved values. |
| `tools/fetch_assets.py` | Downloads the gitignored Poly Haven files from `assets/manifest.json`; skips files with the right sha256; checks size + sha256, retries, atomic rename; stdlib `urllib` + `pathlib`; `--check`, `--dest`, `--only`. |
| `assets/manifest.json` | 10 entries (1 HDRI 2K + 3 texture sets × diff/nor_gl/rough 1K) = everything `scene_lib_v2*.py` references; url/size/md5 from `api.polyhaven.com/files/<name>`, sha256 of the Mac's files (md5 + size of all 10 matched the API). Kenney kit and fonts are committed in git, so not listed. |
| `assets/fonts/Montserrat-Bold.ttf`, `Montserrat-ExtraBold.ttf`, `OFL.txt` | OFL font for Windows/Page 2. Google Fonts' repo only ships the variable font, so the static TTFs come from the upstream repo it pins (JulietaUla/Montserrat @ `cc8daf2`); OFL.txt from google/fonts. |
| `assets/CREDITS.md` | Montserrat + manifest credits added. |
| `.gitignore` | `config_local.json` added. |

### Modified copies in `page2/port-wip/` (swap in later)
`pipeline/make_episode.py`, `overlay_v2.py`, `qc_v2.py`, `v2_test.py`, `v2_textures.py`, `captions.py`, `qc_full.py`,
`qc_flicker.py`, `tools/fb_schedule_reel.py`, `tools/gen_image.py`. What changed in each: PATCH-NOTES table.
Unified diffs in `port-wip/diffs/` + `port-wip/all.diff` (`git apply --check` passes on the current live files).

Not needed: every subprocess call already used arg lists (no `shell=True`, no `sed`/pipes/`open`); paths are built
with `os.path.join`, which is already correct on Windows (new code uses `pathlib`).

## Configure on Windows
1. Clone to a short path without spaces/`&` (e.g. `C:\SME\irfan`), `py -3.11 -m venv .venv`, then
   `.venv\Scripts\pip install google-genai faster-whisper python-dotenv pillow numpy tzdata`.
2. **Required:** `setx PYTHONUTF8 1` (new terminal afterwards). Pipeline scripts open episode/JSON files without
   `encoding=`, and Windows would otherwise read them as cp1252 (non-ASCII text like `·`, `é` breaks).
   `make_episode.py` (port-wip) also sets it for its child processes.
3. `.venv\Scripts\python tools\fetch_assets.py` (≈ 11 MB from dl.polyhaven.org).
4. Defaults on Windows: Blender `C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`, `ffmpeg`/`ffprobe`
   from PATH, Montserrat for all overlay/caption/QC text. Override only if different, in `config_local.json`:
   ```json
   {"BLENDER_EXE": "D:\\Blender 5.3\\blender.exe", "FFMPEG_EXE": "C:\\ffmpeg\\bin\\ffmpeg.exe",
    "FFPROBE_EXE": "C:\\ffmpeg\\bin\\ffprobe.exe", "SCHEDULE_TZ": "America/New_York"}
   ```
   (the same keys also work as environment variables or `.env` lines).
5. `SCHEDULE_TZ=America/New_York` makes `fb_schedule_reel.py` take ET slot times (DST-aware via zoneinfo; needs
   `tzdata` on Windows). Unset = Malaysia UTC+8 as before.
6. `python pipeline\platform_cfg.py` to confirm what it resolved.

## Verification (Mac, 24 Nov)
- `py_compile`: `pipeline/platform_cfg.py`, `tools/fetch_assets.py` and all 10 port-wip copies — OK.
- Overlay preview, before (live `overlay_v2.py`) vs after (port-wip copy + `platform_cfg.py` in a mirror root with
  read-only symlinks to `output/`, `episodes/`, `assets/`), every beat of `2026-11-24-1-plane-crash` and
  `2026-11-24-9-hurricane` at t = 0.5/1.5/3/5 s, written to a temp dir: **76 / 76 PNGs byte-identical**.
  With `OVERLAY_FONT_SET=montserrat` the frame changes and renders cleanly (Montserrat is a bit wider than Avenir;
  check long cards/chips on Page 2's first previews).
- Resolved Mac defaults equal the old literals (Blender path, `.venv/bin/python`, Avenir #0/#8/#2, Arial Black/Bold,
  DIN, ffmpeg/ffprobe, UTC+8). `SCHEDULE_TZ=America/New_York`: "2026-11-25 08:00" → 13:00 UTC (correct, EST).
- `fetch_assets.py --check` on the Mac: 10/10 ok. Into a temp dir: 2 rough maps downloaded + sha256-verified,
  re-run skipped both.

## Remaining Mac-only / Windows-risk bits (not changed)
- `pipeline/blender/scene_lib.py:46-47` — Arial Black/Bold `/System/Library/...` for v1 **3D** text. Runs inside
  Blender and is imported by the live `render_episode_v2.py`, so left alone. v2 episodes make no 3D text, so it is
  not hit on Windows; if ever needed, fall back to `C:\Windows\Fonts\ariblk.ttf` / `arialbd.ttf`.
- `pipeline/blender/render_episode_v2.py` (forbidden): no hard-coded Mac paths found; opens JSON without
  `encoding=` — Blender's embedded Python runs in UTF-8 mode, so expected fine; confirm in the benchmark.
- `pipeline/blender/scene_lib_v2_yard.py`, `pipeline/tts.py` (forbidden): no Mac-only paths (tts only has a
  `.venv/bin/python` usage line in its docstring).
- `tools/episode_gen_2026-11-26/ep_b.py`, `ep_c.py` (another session's one-off generators): hard-coded
  `/Users/irfan/...` output paths.
- Usage docstrings and `pipeline/README.md` show `.venv/bin/python` and the Mac Blender path (docs only; Windows:
  `.venv\Scripts\python`).
- ffmpeg concat lists write `file 'C:\...'` with backslashes; ffmpeg treats them literally inside single quotes,
  but confirm on the first Windows assemble.
- `assets/polyhaven/README.md` / `LICENSE.md` are gitignored docs and are not fetched (same info in CREDITS.md).

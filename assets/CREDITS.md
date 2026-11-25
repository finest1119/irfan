# Credits

## Kenney Car Kit (3.1)
- Author: Kenney — https://www.kenney.nl
- Licence: Creative Commons Zero (CC0 1.0), public domain — http://creativecommons.org/publicdomain/zero/1.0/
  (full text: `assets/kenney-car-kit/License.txt`). Credit is not required; we give it anyway.
- Used for: all 3D cars in the explainer videos (`pipeline/blender/scene_lib.py`).
- Kept in the repo: `Models/GLB format/*.glb`, `Models/GLB format/Textures/colormap.png`, `License.txt`
  (the FBX/OBJ copies, `Previews/` and the `.url` shortcuts were removed to keep the repo small).
  `Overview.html` and `Preview.png` (about 170 KB) from the kit are still in the folder; they are optional and can be deleted.

## Poly Haven (v2 look, 23 Nov 2026)
- HDRI `kloofendal_48d_partly_cloudy` (Greg Zaal) and textures `aerial_asphalt_01`, `aerial_grass_rock`,
  `concrete_floor_02` (Rob Tuytel) — https://polyhaven.com
- Licence: CC0 1.0 (public domain) — https://polyhaven.com/license. Files and source URLs: `assets/polyhaven/README.md`
  (folder is gitignored; re-download from the URLs there).

## Montserrat (Page 2 / Windows overlay font, 24 Nov 2026)
- Files: `assets/fonts/Montserrat-Bold.ttf`, `assets/fonts/Montserrat-ExtraBold.ttf` (static TTFs) + `assets/fonts/OFL.txt`.
- Authors: The Montserrat Project Authors (Julieta Ulanovsky et al.) — https://github.com/JulietaUla/Montserrat
  (static TTFs from `fonts/ttf/` at commit `cc8daf2e7085006b9c112542fc82b58afc13521d`, the upstream commit pinned by
  Google Fonts' `ofl/montserrat/METADATA.pb`; Google Fonts' own repo only ships the variable font). `OFL.txt` from
  https://github.com/google/fonts/tree/main/ofl/montserrat.
- Licence: SIL Open Font License 1.1 — bundling/redistribution allowed with the licence text.
- Used for: overlay captions/cards/labels when `OVERLAY_FONT_SET=montserrat` (default on Windows; the Mac/WJH keeps
  Avenir Next) — see `pipeline/platform_cfg.py`.

## Asset manifest
- `assets/manifest.json` lists every gitignored asset (the Poly Haven files above) with URL, size, md5, sha256;
  `python tools/fetch_assets.py` re-downloads missing/changed ones (Windows laptop setup).

## CC0 upgrade for Self-Made Engineer (25 Nov 2026) — `assets/cc0/` (gitignored; list + checksums in `assets/cc0/manifest.json`, re-download with `tools/fetch_cc0.py`)
- Poly Haven (CC0, polyhaven.com): island_tree_02, tree_small_02 (added 25 Nov, session 7), pine_sapling_small, shrub_02/03/04, grass_bermuda_01, grass_medium_02, rock_moss_set_01, rock_07 (1k models); white_planks_clean, grey_roof_01, gravel_road, river_small_rocks, grooved_concrete_driveway, excavated_soil_wall (2k textures).
- Kenney (CC0, kenney.nl): Furniture Kit, Survival Kit, Car Kit.
- Quaternius (CC0, quaternius.com, by @Quaternius; free "Standard" zips from itch.io, added 25 Nov, session 9): Universal Base Characters (Superhero_Male base body, Hair_Beard, Hair_Buzzed, eyes/eyebrows) and Universal Animation Library (UAL1_Standard: Idle_Loop, Walk_Loop retargeted) — Bolts on Page 2 (`page2/blender/characters_s9.py`).

## Oswald (Page 2 / SME thumbnail font, 25 Nov 2026)
- Files: `assets/fonts/Oswald-Bold.ttf`, `assets/fonts/Oswald-SemiBold.ttf` (static instances at wght 700 / 600, cut with fontTools from Google Fonts' variable `ofl/oswald/Oswald[wght].ttf`) + `assets/fonts/Oswald-OFL.txt`.
- Authors: The Oswald Project Authors (Vernon Adams et al.) — https://github.com/googlefonts/OswaldFont
- Licence: SIL Open Font License 1.1 (free for commercial use; may be bundled; may not be sold on its own).

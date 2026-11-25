# Self-Made Engineer (Page 2): Reel thumbnail preset "spec sheet"

Status: v1, 25 Nov 2026. Builds on `branding/THUMBNAIL-STYLE.md` (two-tier hook, payoff, safe zones, truth rule).
Renderer (stopgap until the shared `tools/make_thumbnail.py` exists): `page2/tools/make_thumb_sme.py`.
Sample: `page2/branding/thumb-sample-build01.jpg`, with crops in `page2/branding/thumb-sample-build01-feed.jpg`.

## The idea in one line
Each cover looks like a **workshop spec sheet** pinned over the build. It has a navy blueprint-grid header, a stamped "BUILD #NN" tag, a hazard-striped orange hook plate, and a **measured callout**: a big honest number in a tagged box, with a thin leader line pointing at the real build.

## Colours (only these three)
| Token | Hex | Use |
|---|---|---|
| navy | `#14212E` | header panel, callout box fill, text on orange |
| orange | `#FF7A1A` | tier-2 plate, hazard stripes, stamp, tier-1 bar, callout border/label, leader line |
| offwhite | `#F4F1EA` | tier-1 text, the payoff number, leader end dot |

Text appears only as **off-white on navy** or **navy on orange**. Never put orange or off-white text straight on the sky or the scene.

## Fonts
- The repo has **no `fonts/` folder**. The only bundled fonts are `assets/fonts/Montserrat-Bold.ttf` and `Montserrat-ExtraBold.ttf` (both OFL, free). WJH already uses Montserrat for its covers, so SME does **not** use it for the hook.
- SME uses **condensed industrial caps**. The renderer takes the first font that exists:
  1. `assets/fonts/Oswald-Bold.ttf`: **not in the repo yet.** It is the recommended free (OFL) face. Ask Irfan to approve adding it; it would also make page3/Windows renders match.
  2. `/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf`: macOS system font, **not free or redistributable**. The sample uses it.
  3. `/System/Library/Fonts/Supplemental/Impact.ttf`: macOS/Windows system font, not free.
  4. `assets/fonts/Montserrat-ExtraBold.ttf`: last-resort fallback.
- All sizes below are font sizes in px at 1080×1920. The renderer measures ink with `textbbox` and shrinks the text until it fits `max_w`.

## Layout (1080×1920, absolute px)
| Element | Position | Spec |
|---|---|---|
| Frame | full width, **shifted down 330 px** | A real frame from the reel. +10% saturation, +5% contrast, unsharp when upscaled. The hero (tower/turbine head) sits at y ≈ 820–1600. |
| Navy blueprint panel | y 0–590 opaque, fades out by y 1000 | Covers the gap the shift leaves at the top. A 54 px off-white grid (every 5th line heavier) fades with it. No sky is faked. |
| Hazard strip | y 196–218, x 90–990 | Navy/orange 45° stripes. Decorative. |
| BUILD #NN stamp | x 90, y ≈ 270 | DIN 58 px, orange outline box 5 px, rotated 4°. Decorative: lost in the 4:5 crop, and that is OK. |
| Logo | top-right, x1 990, y 246, 124 px | `profile-logo-final.png`, cropped round. Decorative. |
| **Tier 1 (setup)** | x 90, y 478 | Sentence case, 92 px (min 64), off-white on the navy panel, with a 12 px orange bar on the left. 2–5 words. |
| **Tier 2 (payoff)** | x 90, y ≈ 606 | ALL CAPS, 190 px (min 120), navy text on a **square-cornered** orange plate (padding 18/30), with a 20 px hazard strip under it. 1–4 words, max width 900. |
| **Callout (big honest number)** | y ≥ 1240, on the side away from the target | Navy box with a 6 px orange border. Orange label 50 px (e.g. TOWER) above an off-white number at 170 px (e.g. 50 FT). Measuring-tape ticks run along its bottom edge. A 6 px orange leader with an elbow ends in an off-white dot **on the real build**. |

### Safe zones and crops
- Hard limits from the style study: nothing that must be read goes above y 160 or below y 1600, with 90 px side margins.
- **Everything that must be read (tier 1, tier 2, the callout and its dot) sits in y 430–1500.** That band survives a **centred 4:5 crop** (y 285–1635) **and a centred 1:1 crop** (y 420–1500). The stamp, logo, top hazard strip and grid may be cropped.
- Assumption: FB crops 4:5 and 1:1 feed views around the centre. This has not been checked against FB. The feed sample shows all three crops at 300 px wide so it can be checked by eye.

## Hook and payoff rules
- Tier 1 + tier 2 = **8 words or fewer**. Tier 1 is the cause or setup; tier 2 is the action or jolt. "So he built this", "He built his own", "Taller than his house" all fit the Page's "a regular guy builds it" angle.
- The callout number must be a **spec from the script's fact-check** (height, kW **PEAK**, kWh/day, cost, weight) with its unit. Add qualifiers the script uses ("PEAK", "≈"). Never show a number the reel doesn't say.
- **The leader points at the part the number describes.** Don't draw a dimension line spanning something the frame doesn't fully show. If the whole object is in frame, a two-arrow dimension line is fine.
- Frame choice: a hero that reads at 300 px wide (a big simple silhouette against sky or a plain background), with no character close-ups while Bolts is being rebuilt. Use a 1080×1920 render of that frame for the final. The current `stills_v4` frames are 378×672, so the sample is upscaled 2.9× and is soft.

## Do / Don't
- **Do:** square corners, condensed caps, left-aligned hook block, one callout per cover, thin technical leader lines, hazard stripes only as edging.
- **Don't:** rounded "sticker" boxes, centred stacked stickers, Montserrat for the hook, red/yellow/teal/amber, emojis, red X marks, circles, fat cartoon arrows, more than one number, any text over busy scenery without a plate.

## How it differs from the other Pages
| | WJH (Page 1) | Everyday Decoded (Page 3) | **SME (Page 2)** |
|---|---|---|---|
| Palette | navy #0B1F3A + red #E63946 / yellow #FFD21F | charcoal #1B1F24, teal #00B3A4, amber #FFB000 | steel navy #14212E + safety orange #FF7A1A + off-white |
| Type | Montserrat Black, geometric, wide | (no cover preset yet; its thumbnail folder is empty) | **condensed industrial caps** (DIN Condensed / Oswald) |
| Layout | centred hook over full-bleed sky, staggered rounded sticker boxes | n/a | **left-aligned spec-sheet header** on a blueprint-grid panel, square plates with hazard edging |
| Payoff device | caps word in a coloured box, optional yellow fact sticker, **no arrows** | n/a | **measured callout**: a big honest number in a tagged box with a leader line to the build, plus a stamped BUILD #NN |

## Usage
```bash
.venv/bin/python page2/tools/make_thumb_sme.py page2/episodes/build-01/work/stills_v4/f1600.png \
  --tier1 "Storm took his power" --tier2 "SO HE BUILT THIS" \
  --payoff "50 FT" --payoff-label TOWER --build 1 --target 541,1478 \
  --out page2/branding/thumb-sample-build01.jpg \
  --feed-preview page2/branding/thumb-sample-build01-feed.jpg
# dump the machine-readable preset:
.venv/bin/python page2/tools/make_thumb_sme.py --print-preset
```
`--target x,y` is the point on the build in output px, after the 330 px shift. The callout goes on the opposite side. `--shift N` overrides the frame shift.

## Build #1 sample
- Frame: `stills_v4/f1600.png`. Turbine head and tail vane against sky, tower down into trees, no Bolts.
- Hook: "Storm took his power" / "SO HE BUILT THIS" (8 words). Callout: TOWER / 50 FT.
- Truth: the script states the 50 ft tower, and the fact-check says the DOE ≥30 ft-above-obstacles rule makes 50 ft believable. The storm outage is Beat 1. The leader points at the tower; it is not a dimension line, because the frame doesn't show the full 50 ft.
- Alternate payoff if a power number is wanted: "1.5 kW PEAK" or "≈ 5 kWh / DAY" (both in the fact-check). Never bare "1.5 kW".

## Machine-readable preset
Generated by `make_thumb_sme.py --print-preset`; the script's `PRESET` dict is the source of truth. All coordinates are absolute px at 1080×1920. Font paths are repo-relative unless absolute.

```json
{
  "page": "self-made-engineer",
  "name": "SME spec-sheet",
  "canvas": [
    1080,
    1920
  ],
  "colors": {
    "navy": "#14212E",
    "orange": "#FF7A1A",
    "offwhite": "#F4F1EA"
  },
  "fonts": {
    "_note": "first file that exists wins; DIN Condensed/Impact are macOS system fonts (not free)",
    "condensed": [
      "assets/fonts/Oswald-Bold.ttf",
      "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
      "/System/Library/Fonts/Supplemental/Impact.ttf",
      "assets/fonts/Montserrat-ExtraBold.ttf"
    ]
  },
  "safe": {
    "top": 160,
    "bottom": 1600,
    "side": 90,
    "must_read_band": [
      430,
      1500
    ]
  },
  "frame": {
    "fit": "cover-width",
    "shift_down": 330,
    "saturation": 1.1,
    "contrast": 1.05,
    "unsharp": [
      2,
      90,
      2
    ]
  },
  "panel": {
    "_note": "opaque navy blueprint panel over the exposed top, fades into the frame",
    "opaque_to": 590,
    "fade_to": 1000,
    "grid_step": 54,
    "grid_major_every": 5,
    "grid_alpha": 0.1,
    "grid_major_alpha": 0.2
  },
  "hazard_top": {
    "y": 196,
    "h": 22,
    "stripe": 30,
    "x0": 90,
    "x1": 990
  },
  "stamp": {
    "text": "BUILD #{n:02d}",
    "x": 90,
    "y": 270,
    "size": 58,
    "border": 5,
    "pad": [
      10,
      22
    ],
    "rotate_deg": 4,
    "color": "orange"
  },
  "logo": {
    "path": "page2/branding/profile-logo-final.png",
    "x1": 990,
    "y": 246,
    "size": 124
  },
  "tier1": {
    "case": "sentence",
    "size": 92,
    "min_size": 64,
    "x": 90,
    "y": 478,
    "max_w": 900,
    "color": "offwhite",
    "bar_w": 12,
    "bar_gap": 22,
    "bar_color": "orange"
  },
  "tier2": {
    "case": "upper",
    "size": 190,
    "min_size": 120,
    "x": 90,
    "y": 606,
    "max_w": 900,
    "pad": [
      18,
      30
    ],
    "box": "orange",
    "text": "navy",
    "radius": 0,
    "hazard_h": 20,
    "hazard_stripe": 26
  },
  "callout": {
    "_note": "big honest number near the hero; leader line + dot point at the build",
    "anchor": "auto-side-of-target",
    "y": 1240,
    "label_size": 50,
    "num_size": 170,
    "min_num_size": 110,
    "max_w": 470,
    "pad": [
      20,
      30
    ],
    "fill": "navy",
    "border": "orange",
    "border_w": 6,
    "label_color": "orange",
    "num_color": "offwhite",
    "leader_w": 6,
    "leader_color": "orange",
    "dot_r": 14,
    "tick_len": 26
  },
  "rules": {
    "max_hook_words": 8,
    "text_only_on": [
      "offwhite on navy",
      "navy on orange"
    ],
    "arrows": "thin technical leader/dimension lines only"
  }
}
```

## Port to the shared tool (25 Nov 2026)
- The live preset is now `tools/thumb_styles/sme.json`, used with `tools/make_thumbnail.py --style sme`. The JSON block above is the target look for the standalone stopgap `page2/tools/make_thumb_sme.py`.
- What the schema can express: left-aligned hook, off-white on a navy setup plate, navy text on a flat, square orange payoff plate with no shadow, a navy callout sticker with square corners, a navy 18 px frame border, and pointers allowed.
- **Zones follow the tool and the style study:** hook from y 330 in the top 12–40%, hero lower, all key content inside y 285–1635 (the 4:5 crop). Trade-off: the 1:1 crop now loses the setup line and the callout. The standalone version kept everything in y 430–1500, but it needed a navy header panel to clear the rotor.
- **Payoff is limited to 3 words**, so the hook became "Storm took his power, so he" / "BUILT THIS" (7 words).
- **Hero frame:** `tools/render_hero_frame.py` drives the WJH v2 renderer and can't render a oneshot episode. I rendered with Page 2's own driver instead: `page2/tools/oneshot.py still … --frames 1600 --scale 1 --samples 32 --views page2/episodes/build-01/work/views_thumb.json`. The result is `stills_oneshot/f1600_thumbhero.png`: the reel camera at f1600, tilted up about 6° so the turbine sits lower and clears the hook. The untilted full-res frame is `f1600_hero1080.png`.

Sample command:
```bash
.venv/bin/python tools/make_thumbnail.py page2/episodes/build-01/work/stills_oneshot/f1600_thumbhero.png \
  output/thumbnails/sample-sme.jpg --style sme --setup "Storm took his power, so he" --payoff "BUILT THIS" \
  --sticker "TOWER 50 FT" --sticker-at 310,1520
```

## Current command (shared tool, 25 Nov 2026, after WJH commit 33be294) — supersedes earlier commands above
```
.venv/bin/python tools/make_thumbnail.py <hero.png> <out.jpg> --style sme \
  --setup "Storm took his power" --payoff "SO HE BUILT THIS" \
  --sticker "50 FT" --sticker-label TOWER --sticker-at 265,1352 --arrow 541,1480 --badge "BUILD #01"
```
Reference output: `output/thumbnails/sample-sme-v2.jpg`. Needs `assets/fonts/Oswald-Bold.ttf` (else falls back to Montserrat and the 4-word payoff wraps).
Not in the shared tool (accepted as optional, no change request): round logo, top hazard strip, setup accent bar.

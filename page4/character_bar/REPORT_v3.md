# Bar the Builder · Character test v3

Bar keeps his v2 Malay facial features, normal build, slight asymmetric smile, woven **BAR** bib tape and wide porch framing.

- **Beard.** An anatomy-based density mask gives the jaw, chin and lower cheeks an even short trim. The cheek line fades, the neckline rises toward the ear, and the upper lip stays bare. Short tapered fibres add texture in the close-up.
- **Eyes.** Both eyes use the same dark brown iris (`#3a2418`), deeper limbal ring (`#20150f`) and dark pupil. Reduced specular reflection and a small neutral catchlight keep the iris brown under the porch sky fill.
- **Face and skin.** Local smoothing and two subdivision levels soften the cheek and chin planes. A small lift rounds the chin tip. The lighter warm tan retains the original skin texture. A 5 × 5 cheek sample at (439, 295) in the front portrait rose from `#aa7a5e` in v2 to `#b88063` in v3.
- **Grip.** The first ruler leaf sits between the thumb and index pads. A 1 mm grid sampled on the two leaf faces found contact on opposite sides, with about 1.0 and 1.1 mm of overlap respectively. Both hinges remain visible in profile.

## Render and verification

Blender 5.3.0, Cycles CPU, six samples and OpenImageDenoise. The five renders took **43.41 seconds** combined. The full build, including turnaround assembly, took **51.47 seconds**.

| Image | Dimensions | Render time |
| --- | --- | ---: |
| Front | 1080 × 1920 | 7.59 s |
| Three-quarter | 1080 × 1920 | 6.38 s |
| Side | 1080 × 1920 | 6.65 s |
| Porch hero | 1080 × 1920 | 18.56 s |
| Three-quarter face close-up | 1080 × 1080 | 4.23 s |
| Turnaround | 3240 × 1920 | Assembled |

Checked all six PNG dimensions and inspected the four ruler views and the face close-up. Each turnaround panel matches its source portrait pixel for pixel.

## Three remaining gaps

1. At porch distance the beard outline and dark irises read clearly, but individual fibres and the narrow limbal ring need the close-up.
2. The chin still tapers to a distinct point in profile, and the mouth corners remain angular at close range.
3. The grip is fitted to this still pose. Finger pressure and contact through a moving hand or ruler remain untested.

Rebuild from this directory with `blender -b --factory-startup --python-exit-code 1 -P build_bar_v3.py`.

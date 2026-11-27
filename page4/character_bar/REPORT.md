# Bar The Builder · Kita Buat Dia

Four 1080 × 1920 PNGs show Bar from the front, at 38°, in left profile, and at his porch workbench. The 3240 × 1920 turnaround sheet combines the three full-body views at native resolution.

## Assets and build

- Quaternius CC0 Universal Base Characters Standard supplied Superhero_Male_FullBody, its brown eyes and brows, and the rigged Hair_SimpleParted mesh. The skin and hair use tinted pack textures. The moustache follows the facial mesh.
- Quaternius CC0 Universal Animation Library Standard supplied frame 12 of Idle_Loop from UAL1_Standard.glb. The build adjusts the stance, gaze, left elbow and finger curl around the hinged ruler.
- The clothing, pencil, metric ruler, workshop and bench prototype are procedural. The local cutaway toolkit supplies metre-scale geometry and materials. Green jalousies, tiled flooring and a reused biscuit tin establish the porch setting.
- Rebuild from this directory with `blender -b --factory-startup --python-exit-code 1 -P build_bar.py`. The script uses FFmpeg to assemble the sheet.

## Render time

Blender 5.3.0, Cycles CPU, six samples, OpenImageDenoise, AgX. The final run took **54.53 seconds** including imports and sheet assembly. The renders took 11.67 s for front, 12.69 s for three-quarter, 12.93 s for side and 11.24 s for hero.

## Three biggest gaps

1. Bar still inherits the base character’s square jaw and heavy brow. A softer brow and a slight asymmetric smile would better convey the brief’s quietly playful 34-year-old builder.
2. The apron and sleeves are fitted to one sampled pose. The flat skirt needs folds, and the waist tie and cuffs need a moving-arm fit check before animation.
3. The hero crop gives the ruler and rotor room, but shows little of the awning or tiled porch. A wider establishing shot would make the terrace-house location clearer.

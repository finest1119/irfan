# Bar the Builder · Character test v2

Bar keeps the Quaternius male base. The installed Standard pack supplied one male full-body model, so the build narrows its shoulder skeleton and reduces chest depth, arm bulk and neck width. The shirt has set-in sleeves with welded seams. Its rolled cuffs follow the arm surface, and the apron ties follow the posed shirt to the back knot.

The face has fuller cheeks, a tapered jaw, a slightly wider nose, lower brows and dark brown eyes. One mouth corner lifts a little higher than the other. The sawo matang skin tint and more neutral key light reduce the orange cast. Short black hair and closely trimmed jaw and chin stubble leave the upper lip bare.

A dark woven tape carries ivory **BAR** lettering formed from mesh geometry fitted to the bib. The apron skirt has uneven vertical folds and a stitched hem. The three yellow ruler leaves share two brass pivots. Bar holds the first leaf at an angle that keeps both bends visible in profile. The wider porch shot includes the awning, jalousie windows, number plate, tiled floor and edge of the open gate.

## Render and checks

Blender 5.3.0 used Cycles CPU, six samples and OpenImageDenoise. The four renders took **30.43 seconds** combined. The complete build took **36.07 seconds** including imports and sheet assembly.

| View | Seconds |
| --- | ---: |
| Front | 7.08 |
| Three-quarter | 5.68 |
| Side | 5.48 |
| Hero | 12.19 |

All four portraits measure 1080 × 1920. Each panel of the 3240 × 1920 turnaround matched its source portrait pixel for pixel. Visual review confirmed readable lettering in the front and hero, a visible grip in all four views, and continuous cuffs and waist tie in the turnaround.

Rebuild from this directory with `blender -b --factory-startup --python-exit-code 1 -P build_bar_v2.py`.

## Three remaining gaps

1. The cheek and chin retain some angular planes from the base mesh, especially in three-quarter view.
2. The cuffs, tie and finger contact were checked in this pose. Their fit through elbow bends, torso turns and hand animation still needs testing.
3. The wider hero gives the porch more room, but individual beard hairs and the asymmetric smile are easiest to judge in the full-resolution front portrait.

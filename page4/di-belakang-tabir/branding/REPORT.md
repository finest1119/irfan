# Di Belakang Tabir

Blender 5.3.0, Cycles CPU, three threads, eight samples and OpenImageDenoise. The final avatar rendered in **9.53 s** and the cover in **9.51 s**. Times include PNG writing and exclude scene construction and typography.

The avatar exposes a continuous green elbow inside a quarter-cut concrete block. The cover follows rain from a clay-tiled terrace roof, beneath the five-foot way and through the open outfall. Both title lines use the supplied Montserrat Bold. The circular checks use native 48, 96 and 180 px diameters. The Facebook crop removes 48 px from each horizontal edge of the master (top and bottom).

## Three remaining visual limits

1. At 48 px the elbow remains connected, while individual concrete grains and the inner pipe lip merge.
2. The terrace is represented by one full bay and part of its neighbour. Most of the streetscape is outside the section.
3. The teal water is a sculpted ribbon. Its continuous route is easier to see than shallow, transparent rainwater, especially along the roof.

Rebuild from this directory with `blender -b -t 3 --factory-startup --python-exit-code 1 -P build_logo.py`, then use the same command with `build_cover.py`. The scripts use the repository's cutlib, fonts and Pillow environment.

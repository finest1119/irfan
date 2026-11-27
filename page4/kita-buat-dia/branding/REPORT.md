# Kita Buat Dia

Blender 5.3.0, Cycles CPU, three threads, eight samples and OpenImageDenoise. The final avatar rendered in **6.68 s** and the cover in **15.15 s**. Times include PNG writing and exclude scene construction and typography.

The cover executes the character stage of `page4/character_bar/build_bar_v3.py`. The seated pose and lap drape preserve the v3 face, short beard, blue shirt, woven BAR tape and ruler grip. Both pedal platforms are placed from the posed boot soles. The cutaway exposes the belt, pulley, brass roller and blade spindle. The title uses Oswald Bold and the sub-line uses Montserrat Bold.

## Three remaining visual limits

1. At 48 px the K reads by silhouette. The hinge centres and individual ruler graduations are clearer at 96 and 180 px.
2. At phone-cover size the yellow ruler remains visible, while the BAR lettering and fine beard texture need a larger view.
3. The 624 px crop trims the lowest edge of the bike stand and most of the canopy valance. Bar's face, ruler, jug and roller remain visible.

Rebuild from this directory with `blender -b -t 3 --factory-startup --python-exit-code 1 -P build_logo.py`, then use the same command with `build_cover.py`. Rendering and export share `studio.py` and `finish.py` in the sibling Di Belakang Tabir branding folder.

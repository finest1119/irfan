# Everyday Decoded | Moka pot hero still

## Three-line pitch

**Topic** — Inside a stovetop moka pot.  
**Hook** — What makes the coffee climb?  
**Why this shot** — One cut lets you follow water up the funnel, through the grounds, and out of the chimney as coffee.

The selected frame shows steady extraction. As the air and water vapor above the reservoir build pressure, liquid water rises through the submerged intake and the grounds. Brewed coffee emerges at the top of the chimney. [Bialetti’s description of the brew path](https://www.bialetti.com/us_en/learn-and-brew/post/how-the-moka-works-lift-the-lid-and-discover-all-its-secrets) · [Instrumented moka-pot study, IEEE Sensors Letters](https://salvoros.folk.ntnu.no/pub-pdf/journals/2021%20IEEE%20SL.pdf)

## Visual review

**Select v2.** In v1, the flat handle reflected enough light to resemble metal, the gas jets looked uniform, and the wedge removed the part of the sole that would touch the front-right grate. For the single revision I rounded the grip, moved the fill, faded the tips of the flames, and carried the base across both front supports. I also shaped the outlet into a thin sheet of coffee and added a meniscus at the cut waterline. I inspected both full frames, then checked v2 at 360 × 640 and at native resolution around the basket, intake, and grate.

| Quality check | What the selected still shows | Remaining limit |
| --- | --- | --- |
| 1. Geometry | The thick cast walls, drawn funnel, two perforated plates, compressed gasket and chimney form one continuous path. Rounded rims catch light. The brass valve, hinge pin, collar threads and trivet contacts are visible. | The individual filter holes merge into a thin silver line at phone size. |
| 2. Materials | The enamel has a glazed highlight, the cut aluminum carries fine tool marks, and the dark molded handle has a broad satin highlight. The wet bed contains irregular coffee fragments. Water uses transmission and an IOR of 1.333. | Reflections from the faceted boiler make the lower water look glasslike in places. The meniscus is clearest beside the intake. |
| 3. Lighting | A local 2K daylight HDRI supplies the environment. A warm window key, cool fill and warm rear rim separate the pot from the tile. Dark contact shadows sit under the sole and grate feet. AgX uses Medium High Contrast at −0.65 EV. | The underside of the lid is the darkest part of the upper chamber. The thin coffee stream has less contrast there. |
| 4. Camera | A 48 mm perspective lens at f/6.3 focuses on the upper edge of the coffee bed. The frame holds the spout, handle and burner. The rear cup and backsplash fall out of focus. | The cascading thread is just a few pixels wide in the full export and approaches a hairline in the phone-size check. |
| 5. Animation | The single pose captures continuous extraction. The intake is submerged, the stream meets the ripple on the brew, and the pot sits on the grate. | Timing, easing, overlapping motion and motion blur are outside the scope of one still. |
| 6. Render | Blender 5.3.0 traced v2 on the RTX 3050 Laptop GPU with Cycles OptiX, 224 maximum adaptive samples, a 0.017 noise threshold and 32 minimum samples. OpenImageDenoise ran on the CPU. PNG and quality-90 JPEG share one render buffer. | The finest suspended bubbles and ground fragments resolve mainly at native size. |

## Exports and measurements

| Revision | Portrait exports | Render time | Sampled peak VRAM |
| --- | --- | ---: | ---: |
| v1 | [PNG](still_v1.png) · [JPEG](still_v1.jpg) | 45.24 s | 1,299 MiB |
| **v2, selected** | [PNG](still_v2.png) · [JPEG](still_v2.jpg) | **55.16 s** | **1,305 MiB** |

Times include path tracing, denoising and the PNG write. Scene construction and JPEG encoding are outside that interval. During the render and export, `nvidia-smi` sampled total dedicated memory on the 4,096 MiB adapter at 500 ms intervals. Each PNG and JPEG decoded as 1080 × 1920 RGB. Both JPEGs matched the standard quality-90 quantization tables.

The scene script is [page3/quality/moka_pot_still.py](../../quality/moka_pot_still.py). It imports the shared cutaway helpers and defaults to v2.

The local `.work/` directory holds the two render logs and Blender’s temporary cache. Automatic approval review blocked their deletion.

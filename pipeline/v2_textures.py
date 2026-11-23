"""PIL textures for the v2 look (markings baked into ONE image per surface: no decal planes, no z-fighting).

  .venv/bin/python pipeline/v2_textures.py OUT_DIR

Writes runway_end.png, runway_end_b.png, runway_mid.png, blastpad.png, taxiway.png, road.png, parking.png.
Copied from pipeline/v2_test.py (the approved look test) so the episode pipeline does not depend on the test script.
The Poly Haven asphalt detail is layered on top of these in Blender (scene_lib_v2.image_mat).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
TEX = None


def _asphalt(w, h, base=(84, 86, 88), seed=1, grain=10, patches=True):
    rng = np.random.default_rng(seed)
    a = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    a += rng.normal(0, grain, (h, w, 1))
    if patches:
        lo = rng.normal(0, 1, (max(2, h // 60), max(2, w // 60), 1)).astype(np.float32)
        lo = np.array(Image.fromarray(((lo[..., 0] + 3) * 40).clip(0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                      np.float32)[..., None] / 40.0 - 3
        a += lo * 5
    return a


def _to_img(a):
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def _paint_rect(a, x0, y0, x1, y1, col=(236, 238, 238), alpha=0.95):
    x0, x1 = int(round(min(x0, x1))), int(round(max(x0, x1)))
    y0, y1 = int(round(min(y0, y1))), int(round(max(y0, y1)))
    a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - alpha) + np.array(col, np.float32) * alpha


def make_textures():
    os.makedirs(TEX, exist_ok=True)
    P = 12  # px per metre
    rw, rl = 45, 400
    Wp, Hp = rw * P, rl * P

    def X(m):  # metres from the runway centre line -> px
        return Wp / 2 + m * P

    def Yr(m):  # metres from the threshold -> image row (threshold at the bottom)
        return Hp - m * P

    for fname, num, seed in (("runway_end.png", "34", 3), ("runway_end_b.png", "16", 4)):
        a = _asphalt(Wp, Hp, seed=seed)
        rng = np.random.default_rng(seed)
        # rubber / tyre marks around touchdown (dark, soft)
        tm = Image.new("L", (Wp, Hp), 0)
        d = ImageDraw.Draw(tm)
        for _ in range(140):
            x = X(rng.normal(0, 2.4)) + rng.choice((-1, 1)) * 2.0 * P
            y0 = Yr(rng.uniform(250, 390))
            d.line([(x, y0), (x + rng.normal(0, 3), y0 - rng.uniform(10, 40) * P)], fill=int(rng.uniform(40, 120)),
                   width=int(rng.uniform(2, 6)))
        tm = np.array(tm.filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255.0
        a = a * (1 - 0.45 * tm)
        # edge lines
        for s in (-1, 1):
            _paint_rect(a, X(s * 21.6), Yr(0), X(s * 20.7), Yr(rl))
        # threshold piano keys: 6 + 6 stripes, 1.8 m wide, 30 m long, from 6 m
        for s in (-1, 1):
            for k in range(6):
                xin = 1.6 + k * 3.4
                _paint_rect(a, X(s * xin), Yr(6), X(s * (xin + 1.8)), Yr(36))
        # runway number (18 m tall, condensed)
        f = ImageFont.truetype(DIN, 400)
        im = Image.new("L", (900, 520), 0)
        ImageDraw.Draw(im).text((450, 260), num, font=f, fill=255, anchor="mm")
        im = im.crop(im.getbbox()).resize((int(12 * P), int(18 * P)), Image.LANCZOS)
        m = np.array(im, np.float32)[..., None] / 255.0
        x0, y0 = int(X(-6)), int(Yr(62))
        reg = a[y0:y0 + m.shape[0], x0:x0 + m.shape[1]]
        a[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = reg * (1 - 0.95 * m) + 236 * 0.95 * m
        # centre line dashes 30 m on / 20 m off from 75 m
        y = 75
        while y + 30 <= rl:
            _paint_rect(a, X(-0.45), Yr(y), X(0.45), Yr(y + 30))
            y += 50
        # touchdown zone bars at 150 m (3 each side) and 450 is beyond; aiming point at 300 m
        for s in (-1, 1):
            for k in range(3):
                xin = 6 + k * 2.6
                _paint_rect(a, X(s * xin), Yr(150), X(s * (xin + 1.8)), Yr(172.5))
            _paint_rect(a, X(s * 6.0), Yr(300), X(s * 15.0), Yr(345))
        _to_img(a).save(os.path.join(TEX, fname))
    # middle tile: 61.5 m, edges + one dash
    tl = 800 / 13.0
    Hm = int(tl * P)
    a = _asphalt(Wp, Hm, seed=7)
    for s in (-1, 1):
        _paint_rect(a, X(s * 21.6), 0, X(s * 20.7), Hm)
    _paint_rect(a, X(-0.45), Hm * 0.25, X(0.45), Hm * 0.25 + 30 * P)
    _to_img(a).save(os.path.join(TEX, "runway_mid.png"))
    # blast pad 45 x 60 m with yellow chevrons
    a = _asphalt(Wp, 60 * P, base=(92, 92, 90), seed=8)
    img = _to_img(a)
    d = ImageDraw.Draw(img)
    for k in range(4):
        yb = 60 * P - (8 + k * 14) * P
        for s in (-1, 1):
            d.line([(X(0), yb - 9 * P), (X(s * 21), yb)], fill=(226, 184, 40), width=int(0.9 * P))
    img.save(os.path.join(TEX, "blastpad.png"))
    # taxiway 18 x 40 m: yellow centre line + yellow edge lines
    tw, th = 18 * P, 40 * P
    a = _asphalt(tw, th, base=(88, 89, 90), seed=9)
    _paint_rect(a, tw / 2 - 0.2 * P, 0, tw / 2 + 0.2 * P, th, (228, 186, 42))
    for s in (-1, 1):
        x = tw / 2 + s * 8.2 * P
        _paint_rect(a, x - 0.12 * P, 0, x + 0.12 * P, th, (228, 186, 42))
    _to_img(a).save(os.path.join(TEX, "taxiway.png"))
    # road 9 x 24 m (16 px / m): white edge lines + dashed centre line
    Q = 16
    a = _asphalt(9 * Q, 24 * Q, base=(70, 72, 75), seed=10, grain=8)
    for s in (-1, 1):
        x = 4.5 * Q + s * 4.0 * Q
        _paint_rect(a, x - 0.1 * Q, 0, x + 0.1 * Q, 24 * Q, (220, 222, 220), 0.85)
    for yy in (0, 12):
        _paint_rect(a, 4.5 * Q - 0.08 * Q, yy * Q, 4.5 * Q + 0.08 * Q, (yy + 4) * Q, (232, 196, 70), 0.9)
    _to_img(a).save(os.path.join(TEX, "road.png"))
    # parking lot 60 x 150 m (10 px / m), lot spans world x 315..375, y 470..620; stalls 5.5 m
    Q = 10
    lw, lh = 60 * Q, 150 * Q
    a = _asphalt(lw, lh, base=(78, 80, 83), seed=11)
    for cx in (12.5, 47.5):
        _paint_rect(a, (cx - 0.08) * Q, lh - 3 * Q, (cx + 0.08) * Q, lh - 147 * Q, (230, 230, 228), 0.9)
        for k in range(27):
            y = 2.25 + 5.5 * k          # world 472.25 + 5.5k  -> local y from the bottom
            _paint_rect(a, (cx - 5.5) * Q, lh - (y + 0.08) * Q, (cx + 5.5) * Q, lh - (y - 0.08) * Q, (230, 230, 228), 0.9)
    _to_img(a).save(os.path.join(TEX, "parking.png"))
    print("textures ->", TEX)



def make(out_dir):
    global TEX
    TEX = out_dir
    if all(os.path.exists(os.path.join(out_dir, f)) for f in (
            "runway_end.png", "runway_end_b.png", "runway_mid.png", "blastpad.png", "taxiway.png", "road.png",
            "parking.png")):
        return out_dir
    make_textures()
    return out_dir


if __name__ == "__main__":
    make(sys.argv[1])

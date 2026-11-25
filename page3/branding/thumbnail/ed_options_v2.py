"""Everyday Decoded cover options v2 (Irfan: the v1 look is too common). Three signature looks, one review sheet.

  .venv/bin/python page3/branding/thumbnail/ed_options_v2.py
Writes opt1-split.jpg, opt2-lens.jpg, opt3-band.jpg and ed-options-v2.jpg (full + 200 px previews).
"""
import os
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT = os.path.join(ROOT, "assets", "fonts", "Montserrat-ExtraBold.ttf")
FONT_B = os.path.join(ROOT, "assets", "fonts", "Montserrat-Bold.ttf")
LOGO = os.path.join(ROOT, "page3", "branding", "logo-v2", "b.png")
FRAME = os.path.join(HERE, "ep01-standin-frame.png")
W, H = 1080, 1920
CH, TEAL, AMBER, WHITE = (27, 31, 36), (0, 179, 164), (255, 176, 0), (255, 255, 255)
SAFE = (285, 1635)
SETUP, PAYOFF = "Your 5G tap", "CROSSES TOWN AND BACK"   # true to the ep 01 hook narration (7 words)


def F(px, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, px)


def plate():
    im = Image.open(FRAME).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    return ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.1)).enhance(1.05)


def blueprint(im):
    """'Decoded' view: edges in teal/white on charcoal with a faint grid (the signature ED treatment)."""
    g = ImageOps.grayscale(im).filter(ImageFilter.GaussianBlur(1.2))
    e = g.filter(ImageFilter.FIND_EDGES)
    e = ImageEnhance.Contrast(e).enhance(3.2).point(lambda v: min(255, int(v * 1.6)))
    base = Image.new("RGB", im.size, (16, 40, 44))
    tint = ImageOps.colorize(g, (14, 30, 34), (20, 80, 82))
    base = Image.blend(base, tint, 0.55)
    lines = Image.new("RGB", im.size, (120, 255, 240))
    out = Image.composite(lines, base, e)
    d = ImageDraw.Draw(out)
    for x in range(0, im.width, 60):
        d.line((x, 0, x, im.height), fill=(30, 70, 72), width=1)
    for y in range(0, im.height, 60):
        d.line((0, y, im.width, y), fill=(30, 70, 72), width=1)
    return Image.composite(lines, out, e)


def shadow_text(img, xy, txt, f, fill, anchor="la", blur=10, a=0.55):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, txt, font=f, fill=(0, 0, 0, int(255 * a)), anchor=anchor)
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)), (0, 4))
    ImageDraw.Draw(img).text(xy, txt, font=f, fill=fill + (255,), anchor=anchor)


def wrap(txt, f, maxw):
    out, cur = [], ""
    for w in txt.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    return out + [cur]


def logo(px):
    lg = Image.open(LOGO).convert("RGB").resize((px, px), Image.LANCZOS)
    m = Image.new("L", (px * 4, px * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, px * 4 - 1, px * 4 - 1), fill=255)
    return lg, m.resize((px, px), Image.LANCZOS)


# ---------------------------------------------------------------- option 1: decoded split
def opt_split():
    """Diagonal split: left = the real scene, right = the same scene 'decoded' (blueprint X-ray). Amber scan seam."""
    im = plate()
    bp = blueprint(im)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([(640, 0), (W, 0), (W, H), (380, H)], fill=255)
    img = Image.composite(bp, im, m).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.line((640, 0, 380, H), fill=AMBER, width=14)
    sy = 1180
    sx = 640 + (380 - 640) * sy / H
    d.ellipse((sx - 30, sy - 30, sx + 30, sy + 30), fill=AMBER)
    # stacked hook top-left in a charcoal slab
    f1, f2 = F(76), F(118)
    lines = wrap(PAYOFF, f2, 820)
    h = 40 + 90 + len(lines) * 118 + 40
    y0 = 300
    slab = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(slab).rounded_rectangle((60, y0, 60 + 900, y0 + h), 36, fill=CH + (235,))
    img.alpha_composite(slab)
    d = ImageDraw.Draw(img)
    d.text((100, y0 + 36), SETUP, font=f1, fill=TEAL)
    y = y0 + 36 + 96
    for ln in lines:
        d.text((96, y), ln, font=f2, fill=WHITE)
        y += 118
    # 'DECODED' tab on the blueprint side
    tf = F(40, True)
    tx, ty = 690, 1500
    tw = tf.getlength("DECODED VIEW")
    d.rounded_rectangle((tx, ty, tx + tw + 50, ty + 66), 33, fill=TEAL)
    d.text((tx + 25, ty + 33), "DECODED VIEW", font=tf, fill=CH, anchor="lm")
    return img.convert("RGB")


# ---------------------------------------------------------------- option 2: scan lens
def opt_lens():
    """The logo-B scan lens over the hero: inside the ring the scene is magnified and decoded; callout label."""
    im = plate()
    img = im.convert("RGBA")
    shade = Image.new("RGBA", (W, H), CH + (0,))
    sm = Image.new("L", (1, H))
    for y in range(H):
        sm.putpixel((0, y), int(200 * max(0.0, 1 - y / 900) ** 1.3))
    shade.putalpha(sm.resize((W, H)))
    img.alpha_composite(shade)
    cx, cy, r = 720, 1210, 270           # lens (inset) showing the cell tower magnified
    zoom, tx, ty = 2.0, 785, 930         # source point: the tower in the frame
    src = im.crop((int(tx - r / zoom), int(ty - r / zoom), int(tx + r / zoom), int(ty + r / zoom)))
    src = blueprint(src.resize((2 * r, 2 * r), Image.LANCZOS))
    m = Image.new("L", (8 * r, 8 * r), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 8 * r - 1, 8 * r - 1), fill=255)
    m = m.resize((2 * r, 2 * r), Image.LANCZOS)
    # drop shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - r - 30, cy - r - 10, cx + r + 30, cy + r + 50), fill=(0, 0, 0, 140))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)))
    img.paste(src, (cx - r, cy - r), m)
    d = ImageDraw.Draw(img)
    d.arc((cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22), -30, 300, fill=TEAL, width=44)
    import math
    a = math.radians(-45)
    sx, sy = cx + (r + 22) * math.cos(a), cy + (r + 22) * math.sin(a)
    d.ellipse((sx - 40, sy - 40, sx + 40, sy + 40), fill=AMBER)
    # hook: setup small teal caps, payoff big white, left
    f1, f2 = F(70), F(116)
    shadow_text(img, (90, 320), SETUP, f1, AMBER)
    y = 410
    for ln in ["CROSSES TOWN", "AND BACK"]:
        f = f2
        while f.getlength(ln) > 910:
            f = F(f.size - 4)
        shadow_text(img, (86, y), ln, f, WHITE)
        y += 120
    # callout label from the lens
    lf = F(42, True)
    lab = "STOP 2: THE CELL TOWER"
    lw = lf.getlength(lab)
    lx, ly = 150, cy + r + 50
    d.rounded_rectangle((lx, ly, lx + lw + 56, ly + 74), 37, fill=WHITE)
    d.text((lx + 28, ly + 37), lab, font=lf, fill=CH, anchor="lm")
    return img.convert("RGB")


# ---------------------------------------------------------------- option 3: side band
def opt_band():
    """Bold vertical teal band on the left with stacked words; scene + blueprint strip on the right."""
    im = plate()
    img = im.convert("RGBA")
    bw = 430
    d = ImageDraw.Draw(img)
    # blueprint sliver next to the band
    bp = blueprint(im).crop((bw, 0, bw + 60, H))
    img.paste(bp, (bw, 0))
    d.rectangle((0, 0, bw, H), fill=TEAL)
    d.rectangle((bw + 60, 0, bw + 72, H), fill=AMBER)
    lg, m = logo(110)
    img.paste(lg, (60, 300), m)
    words = ["YOUR", "5G", "TAP"]
    y = 450
    for wds, sz in zip(words, (112, 230, 150)):
        f = F(sz)
        while f.getlength(wds) > bw - 100:
            sz -= 6
            f = F(sz)
        d.text((56, y), wds, font=f, fill=CH)
        y += int(sz * 1.0)
    # payoff in white stacked under, amber rule
    y += 30
    d.rectangle((60, y, 200, y + 14), fill=AMBER)
    y += 50
    for wds in ("CROSSES", "TOWN", "AND BACK"):
        f = F(70)
        while f.getlength(wds) > bw - 100:
            f = F(f.size - 4)
        d.text((60, y), wds, font=f, fill=WHITE)
        y += 82
    assert y < SAFE[1], y
    return img.convert("RGB")


def sheet(opts):
    pad, cw = 40, 540
    ch = int(cw * H / W)
    img = Image.new("RGB", (pad + len(opts) * (cw + pad), 140 + ch + 330), (240, 242, 245))
    d = ImageDraw.Draw(img)
    d.text((pad, 40), "Everyday Decoded - cover options v2 (stand-in frame; real covers use a frame from the reel)",
           font=F(34), fill=(20, 20, 20))
    for i, (name, im) in enumerate(opts):
        x = pad + i * (cw + pad)
        img.paste(im.resize((cw, ch), Image.LANCZOS), (x, 110))
        # 1080x1350 feed-crop guide
        y0 = 110 + int(SAFE[0] * ch / H)
        y1 = 110 + int(SAFE[1] * ch / H)
        d.rectangle((x, y0, x + cw - 1, y1), outline=(255, 60, 60), width=2)
        d.text((x, 110 + ch + 14), name, font=F(34), fill=(20, 20, 20))
        small = im.resize((200, int(200 * H / W)), Image.LANCZOS)
        img.paste(small, (x + cw - 200, 110 + ch + 60 - 0))
        d.text((x, 110 + ch + 70), "200 px ->", font=F(26, True), fill=(90, 90, 90))
    return img


if __name__ == "__main__":
    opts = [("1  Decoded split (X-ray half)", opt_split()), ("2  Scan lens + callout", opt_lens()),
            ("3  Teal side band", opt_band())]
    for (n, im), fn in zip(opts, ("opt1-split.jpg", "opt2-lens.jpg", "opt3-band.jpg")):
        im.save(os.path.join(HERE, fn), quality=92)
    p = os.path.join(HERE, "ed-options-v2.jpg")
    sheet(opts).save(p, quality=90)
    print(p)

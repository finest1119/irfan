"""Everyday Decoded logo v2: vector-style concepts A and B drawn in PIL (4x supersampled), C finished from Codex art.

  .venv/bin/python page3/branding/logo-v2/make_logos.py
Writes logo-v2/a.png, b.png, c.png (1024 px) and ../logos-v2-review.jpg (each at full, 170 px and 40 px circle).
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT = os.path.join(ROOT, "assets", "fonts", "Montserrat-ExtraBold.ttf")
BG, TEAL, AMBER, WHITE, ICE = (27, 31, 36), (0, 179, 164), (255, 176, 0), (255, 255, 255), (127, 212, 255)
S = 4096  # supersample canvas, downsampled to 1024


def font(px):
    return ImageFont.truetype(FONT, px)


def finish(img):
    return img.resize((1024, 1024), Image.LANCZOS)


def concept_a():
    """ED monogram, 'decoded' split: top half white, bottom half teal shifted right; amber scan bar at the cut."""
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    # teal ring (circle-safe frame)
    m, w = 300, 230
    d.ellipse([m, m, S - m, S - m], outline=TEAL, width=w)
    f = font(1800)
    text = "ED"
    bx = d.textbbox((0, 0), text, font=f)
    tw, th = bx[2] - bx[0], bx[3] - bx[1]
    x, y = (S - tw) // 2 - bx[0], (S - th) // 2 - bx[1]
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=f, fill=255)
    cut = y + bx[1] + th // 2 + 40
    gap, shift = 180, 150
    top = mask.crop((0, 0, S, cut - gap // 2))
    bot = mask.crop((0, cut + gap // 2, S, S))
    img.paste(WHITE, (0, 0), top)
    img.paste(TEAL, (shift, cut + gap // 2), bot)
    # amber scan bar through the cut, extending past the letters
    x0, x1 = x + bx[0] - 120, x + bx[2] + shift + 20
    d.rounded_rectangle([x0, cut - 75, x1, cut + 75], radius=75, fill=AMBER)
    return finish(img)


def concept_b():
    """Scan lens over a house: left half solid white, right half cut away showing teal floors; amber Spark dot."""
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    c = S // 2
    # house silhouette
    hw, roof_top, eave, base = 1800, 900, 1900, 3150
    l, r = c - hw // 2, c + hw // 2
    house = Image.new("L", (S, S), 0)
    hd = ImageDraw.Draw(house)
    hd.polygon([(c, roof_top), (r + 260, eave), (l - 260, eave)], fill=255)
    hd.rectangle([l, eave - 10, r, base], fill=255)
    # left half white
    left = Image.new("L", (S, S), 0)
    ImageDraw.Draw(left).rectangle([0, 0, c - 60, S], fill=255)
    img.paste(WHITE, (0, 0), ImageChops.multiply(house, left))
    # right half: cutaway in teal with floor slabs (dark gaps) + door
    right = Image.new("L", (S, S), 0)
    ImageDraw.Draw(right).rectangle([c + 60, 0, S, S], fill=255)
    img.paste(TEAL, (0, 0), ImageChops.multiply(house, right))
    for yy in (2350, 2760):
        d.rectangle([c + 60, yy, r + 300, yy + 110], fill=BG)
    d.rounded_rectangle([c + 330, 2010, c + 680, 2270], radius=50, fill=AMBER)  # lit window
    # door on the white half
    d.rounded_rectangle([c - 640, 2450, c - 300, base], radius=170, fill=BG)
    # scan lens ring with a gap, amber Spark at the gap
    m, w = 330, 230
    d.arc([m, m, S - m, S - m], start=-35, end=295, fill=TEAL, width=w)
    import math
    a = math.radians(-50)
    rr = (S - 2 * m) / 2 - w / 2
    sx, sy = c + rr * math.cos(a), c + rr * math.sin(a)
    d.ellipse([sx - 290, sy - 290, sx + 290, sy + 290], fill=AMBER)
    return finish(img)


def concept_c():
    src = os.path.join(HERE, "c-raw.png")
    if not os.path.exists(src):
        return None
    im = Image.open(src).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    im = im.resize((800, 800), Image.LANCZOS)  # pad: the Codex 'e' fills the square and clips in a circle crop
    canvas = Image.new("RGB", (1024, 1024), im.getpixel((4, 4)))
    canvas.paste(im, (112, 112))
    return canvas


def circle(im, px):
    big = im.resize((px * 4, px * 4), Image.LANCZOS)
    m = Image.new("L", big.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, big.width - 1, big.height - 1], fill=255)
    out = Image.new("RGB", big.size, (240, 242, 245))
    out.paste(big, (0, 0), m)
    return out.resize((px, px), Image.LANCZOS)


def sheet(concepts):
    W, row, pad = 1700, 620, 40
    img = Image.new("RGB", (W, 120 + row * len(concepts)), (240, 242, 245))
    d = ImageDraw.Draw(img)
    d.text((pad, 30), "Everyday Decoded - logo v2 concepts (full / 170 px circle / 40 px circle)", font=font(44),
           fill=(20, 20, 20))
    for i, (name, desc, im) in enumerate(concepts):
        y = 120 + i * row
        img.paste(im.resize((560, 560), Image.LANCZOS), (pad, y))
        d.text((640, y + 10), name, font=font(56), fill=(20, 20, 20))
        d.text((640, y + 90), desc, font=font(26), fill=(70, 70, 70))
        c170 = circle(im, 170)
        img.paste(c170, (640, y + 250))
        c40 = circle(im, 40)
        img.paste(c40, (880, y + 315))
        # 40 px shown 1:1 and also magnified x4 (nearest) so the reviewer sees the real pixels
        img.paste(c40.resize((160, 160), Image.NEAREST), (980, y + 255))
        d.text((640, y + 440), "170 px", font=font(22), fill=(90, 90, 90))
        d.text((870, y + 440), "40 px", font=font(22), fill=(90, 90, 90))
        d.text((980, y + 440), "40 px zoomed x4", font=font(22), fill=(90, 90, 90))
    return img


if __name__ == "__main__":
    out = []
    for key, name, desc, fn in [
        ("a", "A - ED monogram, decoded", "Bold ED, bottom half shifted teal,\namber scan bar at the split.", concept_a),
        ("b", "B - Cut-away house in a scan lens", "Half solid / half cut-away house,\nteal lens ring, amber Spark.", concept_b),
        ("c", "C - Cut-away 'e' with gears", "Letter e with its insides revealed\n(Codex art).", concept_c),
    ]:
        im = fn()
        if im is None:
            print("skip", key, "(no art yet)")
            continue
        im.save(os.path.join(HERE, key + ".png"))
        out.append((name, desc, im))
    p = os.path.join(HERE, "..", "logos-v2-review.jpg")
    sheet(out).save(p, quality=92)
    print("wrote", os.path.abspath(p), len(out), "concepts")

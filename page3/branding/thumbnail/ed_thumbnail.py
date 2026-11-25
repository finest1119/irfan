"""Everyday Decoded Reel cover preset (1080x1920). Designed to port into the shared tools/make_thumbnail.py.

  .venv/bin/python page3/branding/thumbnail/ed_thumbnail.py FRAME.png OUT.jpg "Setup line" "PAYOFF" ["fact sticker"]

Look ("decoded scan"), deliberately unlike The World Decoded's centred two-tier sticker boxes:
  - LEFT-aligned text block (x = 90), no boxes behind the hook;
  - brand tag top-left: logo B mark + "EVERYDAY DECODED" in teal caps;
  - setup line: white Montserrat ExtraBold, sentence case;
  - payoff: ALL-CAPS amber TEXT (no box), underlined by a thick teal "scan bar" ending in the amber Spark dot;
  - teal corner "lens" brackets frame the hero object (echoes the logo B scan lens);
  - optional fact sticker: teal pill, white text (a number/fact said in the video only);
  - readability from a charcoal top gradient, not from strokes/outlines.
Safe zones per branding/THUMBNAIL-STYLE.md: no text above y 160 or below y 1600, 90 px side margins.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO = os.path.join(ROOT, "page3", "branding", "logo-v2", "b.png")
W, H = 1080, 1920

PRESET = {
    "page": "Everyday Decoded",
    "colors": {"charcoal": "#1B1F24", "teal": "#00B3A4", "amber": "#FFB000", "white": "#FFFFFF"},
    "align": "left", "margin_x": 90,
    "brand_tag": {"y": 190, "logo_px": 62, "text": "EVERYDAY DECODED", "size": 30, "color": "teal"},
    "setup": {"y": 300, "size": 66, "font": "Montserrat-ExtraBold", "color": "white", "case": "sentence"},
    "payoff": {"size": 132, "min_size": 92, "font": "Montserrat-ExtraBold", "color": "amber", "case": "upper",
               "max_lines": 2, "max_width": 900, "box": None},
    "scan_bar": {"height": 16, "gap": 26, "color": "teal", "spark": "amber", "spark_d": 40},
    "lens_brackets": {"box": (90, 900, 990, 1580), "arm": 78, "width": 12, "color": "teal"},
    "fact": {"y": 1470, "size": 40, "bg": "teal", "fg": "white"},
    "grade": {"saturation": 1.10, "contrast": 1.05},
    "top_gradient": {"to_y": 860, "alpha": 0.82, "color": "charcoal"},
    "max_words": 8,
}


def _rgb(name):
    h = PRESET["colors"].get(name, name).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _font(px, name="Montserrat-ExtraBold"):
    return ImageFont.truetype(os.path.join(FONTS, name + ".ttf"), px)


def _cover_fit(im):
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def _wrap(text, f, maxw, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines if len(lines) <= max_lines and all(f.getlength(l) <= maxw for l in lines) else None


def render(frame_path, out_path, setup, payoff, fact=None):
    P = PRESET
    n = len((setup + " " + payoff).split())
    if n > P["max_words"]:
        raise SystemExit("hook has %d words (max %d)" % (n, P["max_words"]))
    im = _cover_fit(Image.open(frame_path).convert("RGB"))
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(P["grade"]["saturation"])).enhance(P["grade"]["contrast"])
    img = im.convert("RGBA")

    # charcoal top gradient (readability without strokes)
    g = P["top_gradient"]
    grad = Image.new("L", (1, g["to_y"]))
    for y in range(g["to_y"]):
        k = 1 - y / g["to_y"]
        grad.putpixel((0, y), int(255 * g["alpha"] * (k ** 1.4)))
    shade = Image.new("RGBA", (W, g["to_y"]), _rgb(g["color"]) + (255,))
    shade.putalpha(grad.resize((W, g["to_y"])))
    img.alpha_composite(shade, (0, 0))

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x0 = P["margin_x"]

    # brand tag
    bt = P["brand_tag"]
    if os.path.exists(LOGO):
        lg = Image.open(LOGO).convert("RGB").resize((bt["logo_px"] * 4,) * 2, Image.LANCZOS)
        m = Image.new("L", lg.size, 0)
        ImageDraw.Draw(m).ellipse((0, 0, lg.width - 1, lg.height - 1), fill=255)
        lg = lg.resize((bt["logo_px"],) * 2, Image.LANCZOS)
        lay.paste(lg, (x0, bt["y"] - bt["logo_px"] // 2), m.resize(lg.size, Image.LANCZOS))
        tx = x0 + bt["logo_px"] + 18
    else:
        tx = x0
    ft = _font(bt["size"], "Montserrat-Bold")
    xx = tx
    for ch in bt["text"]:          # letter-spaced caps
        d.text((xx, bt["y"]), ch, font=ft, fill=_rgb(bt["color"]) + (255,), anchor="lm")
        xx += ft.getlength(ch) + 4

    # setup line
    st = P["setup"]
    fs = _font(st["size"])
    y = st["y"]
    d.text((x0, y), setup, font=fs, fill=_rgb(st["color"]) + (255,), anchor="lt")
    y += int(st["size"] * 1.22)

    # payoff: amber caps text, auto-fit to max_lines
    po = P["payoff"]
    size, lines = po["size"], None
    while size >= po["min_size"]:
        fp = _font(size)
        lines = _wrap(payoff.upper(), fp, po["max_width"], po["max_lines"])
        if lines:
            break
        size -= 6
    if not lines:
        raise SystemExit("payoff too long for %d lines" % po["max_lines"])
    widest = 0
    for ln in lines:
        d.text((x0 - 4, y), ln, font=fp, fill=_rgb(po["color"]) + (255,), anchor="lt")
        widest = max(widest, fp.getlength(ln))
        y += int(size * 1.0)

    # teal scan bar + amber Spark
    sb = P["scan_bar"]
    by = y + sb["gap"]
    d.rounded_rectangle((x0, by, x0 + widest, by + sb["height"]), sb["height"] // 2, fill=_rgb(sb["color"]) + (255,))
    r = sb["spark_d"] // 2
    cx, cy = x0 + widest + r + 12, by + sb["height"] / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgb(sb["spark"]) + (255,))
    assert cy + r < P["lens_brackets"]["box"][1], "hook runs into the hero zone"

    # lens corner brackets around the hero zone
    lb = P["lens_brackets"]
    bx0, by0, bx1, by1 = lb["box"]
    a, w, col = lb["arm"], lb["width"], _rgb(lb["color"]) + (235,)
    for (cx_, cy_, sx, sy) in ((bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)):
        d.rounded_rectangle((min(cx_, cx_ + sx * a), cy_ - w // 2 if sy > 0 else cy_ - w // 2,
                             max(cx_, cx_ + sx * a), cy_ + w // 2), w // 2, fill=col)
        d.rounded_rectangle((cx_ - w // 2, min(cy_, cy_ + sy * a), cx_ + w // 2, max(cy_, cy_ + sy * a)), w // 2, fill=col)

    # optional fact sticker
    if fact:
        fa = P["fact"]
        ff = _font(fa["size"], "Montserrat-Bold")
        tw = ff.getlength(fact)
        fx0, fy0 = (W - tw) / 2 - 30, fa["y"]
        d.rounded_rectangle((fx0, fy0, fx0 + tw + 60, fy0 + fa["size"] + 32), 30, fill=_rgb(fa["bg"]) + (245,))
        d.text((W / 2, fy0 + (fa["size"] + 32) / 2), fact, font=ff, fill=_rgb(fa["fg"]) + (255,), anchor="mm")

    # soft shadow under the text layer only
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.putalpha(lay.getchannel("A").point(lambda v: int(v * 0.45)).filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(sh, (0, 4))
    img.alpha_composite(lay)
    img.convert("RGB").save(out_path, quality=92)
    return out_path


if __name__ == "__main__":
    a = sys.argv[1:]
    print(render(a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None))

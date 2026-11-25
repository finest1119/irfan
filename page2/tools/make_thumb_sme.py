#!/usr/bin/env python3
"""Self-Made Engineer (Page 2) Reel thumbnail renderer -- standalone stopgap.

Use this until the shared tools/make_thumbnail.py exists. The PRESET dict below is
the source of truth; `--print-preset` dumps it as JSON for the shared tool.

Usage:
  .venv/bin/python page2/tools/make_thumb_sme.py FRAME.png \
      --tier1 "Storm took his power" --tier2 "SO HE BUILT THIS" \
      --payoff "50 FT" --payoff-label "TOWER" --build 1 \
      --target 560,1080 --out page2/branding/thumb.jpg [--feed-preview feed.jpg]

--target x,y  point on the hero (output px, AFTER the frame shift) the callout
              leader line points at. Omit it to leave out the leader.
--shift N     how far the frame moves down to clear the hook zone (default preset).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

PRESET = {
    "page": "self-made-engineer",
    "name": "SME spec-sheet",
    "canvas": [1080, 1920],
    "colors": {
        "navy": "#14212E",
        "orange": "#FF7A1A",
        "offwhite": "#F4F1EA",
    },
    "fonts": {
        "_note": "first file that exists wins; DIN Condensed/Impact are macOS system fonts (not free)",
        "condensed": [
            "assets/fonts/Oswald-Bold.ttf",
            "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "assets/fonts/Montserrat-ExtraBold.ttf",
        ],
    },
    "safe": {"top": 160, "bottom": 1600, "side": 90, "must_read_band": [430, 1500]},
    "frame": {
        "fit": "cover-width",
        "shift_down": 330,
        "saturation": 1.10,
        "contrast": 1.05,
        "unsharp": [2, 90, 2],
    },
    "panel": {
        "_note": "opaque navy blueprint panel over the exposed top, fades into the frame",
        "opaque_to": 590,
        "fade_to": 1000,
        "grid_step": 54,
        "grid_major_every": 5,
        "grid_alpha": 0.10,
        "grid_major_alpha": 0.20,
    },
    "hazard_top": {"y": 196, "h": 22, "stripe": 30, "x0": 90, "x1": 990},
    "stamp": {
        "text": "BUILD #{n:02d}",
        "x": 90, "y": 270, "size": 58, "border": 5, "pad": [10, 22],
        "rotate_deg": 4, "color": "orange",
    },
    "logo": {"path": "page2/branding/profile-logo-final.png", "x1": 990, "y": 246, "size": 124},
    "tier1": {
        "case": "sentence", "size": 92, "min_size": 64, "x": 90, "y": 478,
        "max_w": 900, "color": "offwhite", "bar_w": 12, "bar_gap": 22, "bar_color": "orange",
    },
    "tier2": {
        "case": "upper", "size": 190, "min_size": 120, "x": 90, "y": 606,
        "max_w": 900, "pad": [18, 30], "box": "orange", "text": "navy",
        "radius": 0, "hazard_h": 20, "hazard_stripe": 26,
    },
    "callout": {
        "_note": "big honest number near the hero; leader line + dot point at the build",
        "anchor": "auto-side-of-target", "y": 1240,
        "label_size": 50, "num_size": 170, "min_num_size": 110, "max_w": 470,
        "pad": [20, 30], "fill": "navy", "border": "orange", "border_w": 6,
        "label_color": "orange", "num_color": "offwhite",
        "leader_w": 6, "leader_color": "orange", "dot_r": 14, "tick_len": 26,
    },
    "rules": {
        "max_hook_words": 8,
        "text_only_on": ["offwhite on navy", "navy on orange"],
        "arrows": "thin technical leader/dimension lines only",
    },
}


def C(name):
    v = PRESET["colors"].get(name, name)
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def font(size):
    for p in PRESET["fonts"]["condensed"]:
        full = p if os.path.isabs(p) else os.path.join(REPO, p)
        if os.path.exists(full):
            return ImageFont.truetype(full, size)
    raise SystemExit("no usable font found")


def fit_font(draw, text, size, min_size, max_w):
    s = size
    while s > min_size:
        f = font(s)
        l, t, r, b = draw.textbbox((0, 0), text, font=f)
        if r - l <= max_w:
            return f
        s -= 4
    return font(min_size)


def draw_text_tl(draw, xy, text, f, fill):
    """Draw text so its INK bbox top-left lands on xy; returns ink box."""
    l, t, r, b = draw.textbbox((0, 0), text, font=f)
    x, y = xy
    draw.text((x - l, y - t), text, font=f, fill=fill)
    return (x, y, x + (r - l), y + (b - t))


def hazard(img, x0, y0, x1, y1, stripe):
    band = Image.new("RGB", (x1 - x0, y1 - y0), C("navy"))
    d = ImageDraw.Draw(band)
    h = y1 - y0
    for k in range(-h, x1 - x0 + h, stripe * 2):
        d.polygon([(k, h), (k + h, 0), (k + h + stripe, 0), (k + stripe, h)], fill=C("orange"))
    img.paste(band, (x0, y0))


def build_base(frame_path):
    W, H = PRESET["canvas"]
    fr = PRESET["frame"]
    src = Image.open(frame_path).convert("RGB")
    scale = W / src.width
    src = src.resize((W, round(src.height * scale)), Image.LANCZOS)
    if scale > 1.2:
        r, p, t = fr["unsharp"]
        src = src.filter(ImageFilter.UnsharpMask(radius=r, percent=p, threshold=t))
    src = ImageEnhance.Color(src).enhance(fr["saturation"])
    src = ImageEnhance.Contrast(src).enhance(fr["contrast"])
    canvas = Image.new("RGB", (W, H), C("navy"))
    canvas.paste(src, (0, fr["shift_down"]))
    if src.height + fr["shift_down"] < H:  # fill any gap at the bottom with navy (already)
        pass

    # navy blueprint panel with fading alpha + grid
    pn = PRESET["panel"]
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    navy = C("navy")
    for y in range(pn["fade_to"]):
        if y <= pn["opaque_to"]:
            a = 1.0
        else:
            u = (y - pn["opaque_to"]) / (pn["fade_to"] - pn["opaque_to"])
            a = (1 - u) ** 1.6
        od.line([(0, y), (W, y)], fill=navy + (int(255 * a),))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    ow = C("offwhite")
    step = pn["grid_step"]

    def panel_alpha(y):
        if y <= pn["opaque_to"]:
            return 1.0
        if y >= pn["fade_to"]:
            return 0.0
        return (1 - (y - pn["opaque_to"]) / (pn["fade_to"] - pn["opaque_to"])) ** 1.6

    for i, x in enumerate(range(0, W + 1, step)):
        major = i % pn["grid_major_every"] == 0
        ga = pn["grid_major_alpha"] if major else pn["grid_alpha"]
        for y in range(0, pn["fade_to"], 4):
            gd.line([(x, y), (x, y + 4)], fill=ow + (int(255 * ga * panel_alpha(y)),),
                    width=2 if major else 1)
    for j, y in enumerate(range(0, pn["fade_to"], step)):
        major = j % pn["grid_major_every"] == 0
        ga = pn["grid_major_alpha"] if major else pn["grid_alpha"]
        gd.line([(0, y), (W, y)], fill=ow + (int(255 * ga * panel_alpha(y)),),
                width=2 if major else 1)
    return Image.alpha_composite(canvas, grid)


def render(frame, tier1, tier2, payoff, payoff_label, build_no, target, shift=None):
    if shift is not None:
        PRESET["frame"]["shift_down"] = shift
    words = len(tier1.split()) + len(tier2.split())
    if words > PRESET["rules"]["max_hook_words"]:
        print(f"WARNING: hook is {words} words (max {PRESET['rules']['max_hook_words']})", file=sys.stderr)

    img = build_base(frame)
    d = ImageDraw.Draw(img)

    # top hazard strip
    hz = PRESET["hazard_top"]
    hazard(img, hz["x0"], hz["y"], hz["x1"], hz["y"] + hz["h"], hz["stripe"])

    # BUILD #NN stamp (rotated, outlined)
    st = PRESET["stamp"]
    txt = st["text"].format(n=build_no)
    f = font(st["size"])
    l, t, r, b = d.textbbox((0, 0), txt, font=f)
    pv, ph = st["pad"]
    sw, sh = (r - l) + 2 * ph + 2 * st["border"], (b - t) + 2 * pv + 2 * st["border"]
    stamp = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    col = C(st["color"])
    sd.rectangle([0, 0, sw - 1, sh - 1], outline=col + (255,), width=st["border"])
    sd.text((st["border"] + ph - l, st["border"] + pv - t), txt, font=f, fill=col + (255,))
    stamp = stamp.rotate(st["rotate_deg"], resample=Image.BICUBIC, expand=True)
    img.alpha_composite(stamp, (st["x"], st["y"]))

    # logo top-right
    lg = PRESET["logo"]
    lp = os.path.join(REPO, lg["path"])
    if os.path.exists(lp):
        logo = Image.open(lp).convert("RGBA").resize((lg["size"], lg["size"]), Image.LANCZOS)
        mask = Image.new("L", logo.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, lg["size"] - 1, lg["size"] - 1], fill=255)
        logo.putalpha(Image.composite(logo.getchannel("A"), mask, mask))
        img.alpha_composite(logo, (lg["x1"] - lg["size"], lg["y"]))

    d = ImageDraw.Draw(img)

    # tier 1: off-white on navy panel with an orange bar
    t1 = PRESET["tier1"]
    x_text = t1["x"] + t1["bar_w"] + t1["bar_gap"]
    f1 = fit_font(d, tier1, t1["size"], t1["min_size"], t1["max_w"] - (x_text - t1["x"]))
    box1 = draw_text_tl(d, (x_text, t1["y"]), tier1, f1, C(t1["color"]))
    d.rectangle([t1["x"], box1[1] - 4, t1["x"] + t1["bar_w"], box1[3] + 4], fill=C(t1["bar_color"]))

    # tier 2: navy text on square orange plate + hazard strip
    t2 = PRESET["tier2"]
    tier2u = tier2.upper()
    pv, ph = t2["pad"]
    f2 = fit_font(d, tier2u, t2["size"], t2["min_size"], t2["max_w"] - 2 * ph)
    l, t, r, b = d.textbbox((0, 0), tier2u, font=f2)
    y2 = max(t2["y"], box1[3] + 34)
    bw, bh = (r - l) + 2 * ph, (b - t) + 2 * pv
    d.rectangle([t2["x"], y2, t2["x"] + bw, y2 + bh], fill=C(t2["box"]))
    draw_text_tl(d, (t2["x"] + ph, y2 + pv), tier2u, f2, C(t2["text"]))
    hazard(img, t2["x"], y2 + bh, t2["x"] + bw, y2 + bh + t2["hazard_h"], t2["hazard_stripe"])
    hook_bottom = y2 + bh + t2["hazard_h"]

    # callout: big honest number + leader line to the build
    co = PRESET["callout"]
    d = ImageDraw.Draw(img)
    fl = font(co["label_size"])
    num = payoff.upper()
    pv, ph = co["pad"]
    fn = fit_font(d, num, co["num_size"], co["min_num_size"], co["max_w"] - 2 * ph)
    ll, lt, lr, lb = d.textbbox((0, 0), payoff_label.upper(), font=fl) if payoff_label else (0, 0, 0, 0)
    nl, nt, nr, nb = d.textbbox((0, 0), num, font=fn)
    gap = 14 if payoff_label else 0
    cw = max(lr - ll, nr - nl) + 2 * ph + 2 * co["border_w"]
    ch = (lb - lt) + gap + (nb - nt) + 2 * pv + 2 * co["border_w"]
    W = PRESET["canvas"][0]
    side = PRESET["safe"]["side"]
    cy = max(co["y"], hook_bottom + 60)
    if target and target[0] < W / 2:
        cx = W - side - cw  # tag on the right, leader goes left to the build
    else:
        cx = side
    # leader first (under the tag)
    if target:
        lc = C(co["leader_color"])
        sx = cx if cx > W / 2 else cx + cw
        sy = cy + ch // 2
        tx, ty = target
        # elbow: horizontal from tag, then diagonal to target
        ex = sx + (-80 if cx > W / 2 else 80)
        d.line([(sx, sy), (ex, sy), (tx, ty)], fill=lc, width=co["leader_w"], joint="curve")
        d.line([(sx, sy - co["tick_len"] // 2), (sx, sy + co["tick_len"] // 2)], fill=lc, width=co["leader_w"])
        r_ = co["dot_r"]
        d.ellipse([tx - r_, ty - r_, tx + r_, ty + r_], fill=C("offwhite"), outline=lc, width=5)
    d.rectangle([cx, cy, cx + cw, cy + ch], fill=C(co["fill"]), outline=C(co["border"]), width=co["border_w"])
    yy = cy + co["border_w"] + pv
    if payoff_label:
        draw_text_tl(d, (cx + co["border_w"] + ph, yy), payoff_label.upper(), fl, C(co["label_color"]))
        yy += (lb - lt) + gap
    draw_text_tl(d, (cx + co["border_w"] + ph, yy), num, fn, C(co["num_color"]))
    # measuring-tape ticks along the tag's bottom edge
    for i, x in enumerate(range(cx + 18, cx + cw - 10, 18)):
        tl = 22 if i % 5 == 0 else 11
        d.line([(x, cy + ch - co["border_w"] - tl), (x, cy + ch - co["border_w"])], fill=C("orange"), width=3)

    return img.convert("RGB")


def feed_preview(thumb, out):
    """9:16, 4:5 (centre) and 1:1 (centre) crops, each 300 px wide, on a feed-grey card."""
    W, H = thumb.size
    crops = [
        ("9:16 full", thumb),
        ("4:5 centre crop", thumb.crop((0, (H - 1350) // 2, W, (H - 1350) // 2 + 1350))),
        ("1:1 centre crop", thumb.crop((0, (H - 1080) // 2, W, (H - 1080) // 2 + 1080))),
    ]
    tw = 300
    ims = [(lab, im.resize((tw, round(im.height * tw / im.width)), Image.LANCZOS)) for lab, im in crops]
    gap, top = 40, 70
    cw = len(ims) * tw + (len(ims) + 1) * gap
    ch = top + max(i.height for _, i in ims) + gap
    card = Image.new("RGB", (cw, ch), (240, 242, 245))
    d = ImageDraw.Draw(card)
    lf = ImageFont.truetype(os.path.join(REPO, "assets/fonts/Montserrat-Bold.ttf"), 22)
    for k, (lab, im) in enumerate(ims):
        x = gap + k * (tw + gap)
        d.text((x, 24), lab + " @300px", font=lf, fill=(40, 40, 40))
        card.paste(im, (x, top))
    card.save(out, quality=92)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frame", nargs="?")
    ap.add_argument("--tier1")
    ap.add_argument("--tier2")
    ap.add_argument("--payoff", help="big honest number, e.g. '50 FT'")
    ap.add_argument("--payoff-label", default="", help="small word above the number, e.g. TOWER")
    ap.add_argument("--build", type=int, default=1)
    ap.add_argument("--target", help="x,y on the hero for the leader line (output px)")
    ap.add_argument("--shift", type=int)
    ap.add_argument("--out")
    ap.add_argument("--feed-preview")
    ap.add_argument("--print-preset", action="store_true")
    a = ap.parse_args()
    if a.print_preset:
        print(json.dumps(PRESET, indent=2))
        return
    if not (a.frame and a.tier1 and a.tier2 and a.payoff and a.out):
        ap.error("frame, --tier1, --tier2, --payoff and --out are required")
    target = tuple(int(v) for v in a.target.split(",")) if a.target else None
    img = render(a.frame, a.tier1, a.tier2, a.payoff, a.payoff_label, a.build, target, a.shift)
    img.save(a.out, quality=93)
    print("wrote", a.out, img.size)
    if a.feed_preview:
        feed_preview(img, a.feed_preview)
        print("wrote", a.feed_preview)


if __name__ == "__main__":
    main()

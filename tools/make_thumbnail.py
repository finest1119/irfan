"""Make a Reel cover (1080x1920 JPG, <10 MB) from a hero frame, styled by a per-Page preset. Page-agnostic.

Style follows branding/THUMBNAIL-STYLE.md: a real frame from the reel's own scene with the hero object in the lower
~55-60%, and a TWO-TIER hook in the top ~12-40%: a white heavy-sans SETUP line (short question / danger / motion
wording) + a 1-3 word (preset payoff.max_words) ALL-CAPS PAYOFF in solid colour boxes (one box per line). Max 8 words in total. Every word must be
literally true to the reel. All key content must sit inside the preset's safe zone (default y 285..1635 = the centre
1080x1350 feed crop); the script refuses to write the file otherwise.

Usage:
  .venv/bin/python tools/make_thumbnail.py HERO.png OUT.jpg --setup "Your tower can act like a" --payoff "CHIMNEY"
      [--style wjh|wjh_b|wjh_c|sme|sme_b|sme_c|ed|ed_b|ed_c|path.json] [--micro "context line"] [--sticker "fact" --sticker-at x,y]
      [--sticker-label "TOWER"] [--badge "BUILD #01"] [--payoff-lines "THE TOP|FLOORS"] [--accent #hex] [--zoom 1.0] [--focus 0.5,0.5] [--text-top PX]
      [--arrow x,y,angle] [--circle x,y,r] [--debug-safe]

  --payoff "A B|C"   "|" splits payoff boxes; otherwise auto 1 line (2 if wider than payoff.max_width).
  --zoom / --focus   cover-fit crop of the hero: zoom >1 crops tighter, focus = crop centre as fractions.
  --arrow / --circle pointer in 1080x1920 coords (arrow TIP at x,y, angle 0=right 90=down -90=up). Presets with
                     "pointers": false (wjh, per the style spec) reject them. With "pointer": {"style": "leader"} the
                     --arrow draws a thin elbow leader line from the sticker (or from the angle) to a dot at x,y.
  --sticker-label T  optional small label line above the sticker text (e.g. TOWER above "50 FT").
  --badge TEXT       set / override the badge text (e.g. "BUILD #01"); uses the preset's badge style.
  --debug-safe       also writes OUT-debug.jpg with the safe zone and content boxes drawn.

Layouts (preset key "layout"; rotate A->B->C per Page, never the same layout twice in a row):
  A (default)  full-bleed hero + two-tier hook on top (setup line + payoff box). Absent key = A, byte-identical.
  B "poster"   flat paper header, thin rule, small kicker (--setup), HUGE stacked payoff words in alternating
               colours, hero frame in a window below (edge: line | hazard | torn). --micro under the words.
  C            caption.variant picks the concept:
               "caption" (default, sme_c) the hook as ONE caption near the bottom of the safe zone (setup plain, payoff
                 on a single highlight box, never split) over a gradient / solid band; --micro above; --sticker label.
               "punch" (wjh_c) giant stroked headline (= --payoff), key word (--key, default last) in the accent colour,
                 setup on a tilted yellow tape strip, edge-darkened hero; pair with --circle / --arrow.
               "diagram" (ed_c) speech-bubble hook card top-left, blueprint-grid tint on the image edges, and
                 --callout "x,y:LABEL[@lx,ly]" (repeatable) lines with dots to small rounded labels.
  --sticker / --badge / --arrow / --circle work the same in every layout.

Preset JSON schema (tools/thumb_styles/<name>.json; every key optional, defaults below in DEFAULT).
Every key marked (opt-in) is off by default, so presets that don't use it render exactly as before.
  layout                "A" (default) | "B" | "C"; B/C presets don't inherit from the Page's A preset (restate font etc.)
  poster                (layout B) {"bg", "grid" null|{step, major_every, color, alpha, major_alpha},
                         "rule" null|{color, width, length (col width), gap}, "kicker_size" (58), "kicker_case"
                         (upper), "kicker_color", "size" (250, auto-shrinks), "leading" (0.16 x cap), "colors" [line
                         colours, cycled], "gap" (30), "micro_size", "micro_color", "window_gap" (44), "window_max_top"
                         (1200), "edge" {"type": line|hazard|torn, "color", "height", "colors", "stripe", "depth", "step"}}
                         Payoff lines: "|" splits, else 1 word per line (short words join the next), pairs for 4+.
  caption               (layout C) {"variant": caption|punch|diagram; punch keys: "size", "stroke", "leading",
                         "color", "key_color", "stroke_color", "edge_dark", "tape" {size, case, color, text, pad,
                         rotate}, "tape_gap"; diagram keys: "grid" {tint, tint_alpha, color, alpha, major_alpha, step,
                         major_every, inner, outer}, "card" {pad, max_width, radius, box, accent, setup_size/case/color,
                         payoff_size/case/color, gap, tail}, "callout" {size, line, line_shadow, width, dot_r, dot_ring,
                         box, text, border, border_w, pad, shadow}; caption keys: "font" (= payoff font), "size" (104, auto-shrinks), "max_lines" (3), "setup_case",
                         "payoff_case" (asis|upper|lower|sentence), "color", "shadow", "box", "box_text", "radius",
                         "pad" [y, x], "box_gap", "line_gap", "y_bottom" (1590; --text-top sets the top instead),
                         "micro_size", "micro_color", "micro_gap",
                         "band" {"type": gradient|solid, "color", "alpha", "fade" (gradient), "pad", "rule", "rule_h"}}
  font                  path (repo-relative or absolute) of the heavy sans, e.g. assets/fonts/Montserrat-ExtraBold.ttf,
                        OR a fallback list of paths: the first file that exists wins, missing ones are skipped
  text_top              y of the top of the hook block (px)
  align                 "center" | "left"
  margin_x              side margin (px)
  safe                  [y0, y1] key-content zone
  gap                   px between setup / payoff / micro
  grade                 {"contrast": 1.05, "saturation": 1.10, "vignette": 0.0-1.0 edge darkening}
  top_shade             0-1: dark gradient over the top 45% for text legibility (0 = off), OR (opt-in) a colour panel:
                        "#hex" or {"color", "alpha" 0-1 (1), "opaque_to" px (576), "fade_to" px (864),
                                   "grid": null | {"step" px (54), "major_every" (5), "color" (#FFFFFF),
                                                   "alpha" (0.10), "major_alpha" (0.20), "width" (1), "major_width" (2)}}
                        = solid colour down to opaque_to, fading linearly to clear at fade_to, with an optional
                        blueprint grid that fades with it.
  setup                 {"size", "color", "shadow" 0-1, "box" null|"#hex", "box_text", "case": asis|upper|sentence}
  payoff                {"size", "max_width", "box", "text", "pad": [y, x], "radius", "stagger" px, "shadow" 0-1,
                         "font" (opt-in) path or fallback list, default = top-level font,
                         "max_words" (3) payoff word limit (setup + payoff still max 8),
                         "min_size" (opt-in) without "|", shrink down to this size to keep ONE line before wrapping,
                         "under_strip" (opt-in) null | {"height" (20), "stripe" (26), "colors" [bg, stripe]
                                        (default [payoff.box, payoff.text])}: hazard-stripe band under the last box}
  micro                 {"size", "box", "text"}
  sticker               {"size", "box", "text", "radius",
                         "shadow" (0.35), "max_width" (420) text width before wrapping, "min_size" (opt-in) shrink the
                         text down to this size to stay on one line / not overflow max_width, "pad" ([14, 24]), "align" (center|left),
                         "label" (opt-in) default label text (--sticker-label overrides), "label_size" (0.45 x size),
                         "label_color" (= text), "label_gap" (6),
                         "border" (opt-in) null | {"width", "color"},
                         "ticks" (opt-in) null | {"step" (18), "len" (24), "major_every" (5), "width" (3),
                                                  "color" (= border colour or text)}: measuring-tape ticks on the bottom}
  border                {"width", "color"}  frame around the whole image (0 = none)
  ticker                null | {"color", "accent", "height", "y_offset"}: thin news-ticker strip above the hook
  badge                 null | {"text", "box", "text_color", "size", "y"}: small corner badge (must be true!), plus
                        (opt-in) "x" left edge of the TEXT; the box starts "pad" further left (default: right-aligned at the margin), "pad" ([8, 16]), "radius" (4),
                        "rotate" degrees (counter-clockwise), "outline" null | {"color", "width"} (stamp look, use with
                        "box": null), "decorative" true = exempt from the safe-zone check (may be cropped off)
  pointers              true/false: allow --arrow/--circle
  pointer               (opt-in) {"style": "arrow" (default fat arrow) | "leader", "color" (= payoff.box), "width" (6),
                         "dot_r" (14), "dot_color" (#FFFFFF), "slant" deg (10), "length" (260, used without a sticker),
                         "from_y" (0.5 = leaves the sticker at half its height)}
"""
import argparse
import io
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STYLES = os.path.join(ROOT, "tools", "thumb_styles")
W, H = 1080, 1920
MAX_BYTES = 10 * 1024 * 1024

DEFAULT = {
    "font": "assets/fonts/Montserrat-ExtraBold.ttf",
    "text_top": 300, "align": "center", "margin_x": 90, "safe": [285, 1635], "gap": 16,
    "grade": {"contrast": 1.05, "saturation": 1.10, "vignette": 0.3},
    "top_shade": 0.0,
    "setup": {"size": 74, "color": "#FFFFFF", "shadow": 0.45, "box": None, "box_text": "#111111", "case": "asis"},
    "payoff": {"size": 150, "max_width": 900, "box": "#E63946", "text": "#FFFFFF", "pad": [12, 28], "radius": 6,
               "stagger": 0, "shadow": 0.35},
    "micro": {"size": 42, "box": "#FFFFFF", "text": "#111111"},
    "sticker": {"size": 40, "box": "#FFD21F", "text": "#111111", "radius": 14},
    "border": {"width": 0, "color": "#000000"},
    "ticker": None,
    "badge": None,
    "pointers": True,
}


def load_style(name):
    path = name if name.endswith(".json") else os.path.join(STYLES, name + ".json")
    st = json.load(open(path))
    out = json.loads(json.dumps(DEFAULT))
    for k, v in st.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def resolve_font(spec):
    """A path or a fallback list of paths (repo-relative or absolute); the first existing file wins."""
    cands = [spec] if isinstance(spec, str) else list(spec)
    for c in cands:
        p = c if os.path.isabs(c) else os.path.join(ROOT, c)
        if os.path.isfile(p):
            return p
    sys.exit("no font found; tried: %s" % cands)


def hazard(img, box, colors, stripe):
    """45-degree hazard stripes filling box: colors = [background, stripe]."""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    tile = Image.new("RGBA", (w, h), rgb(colors[0]) + (255,))
    d = ImageDraw.Draw(tile)
    for sx in range(-h - 2 * stripe, w + 2 * stripe, 2 * stripe):
        d.polygon([(sx, h), (sx + stripe, h), (sx + stripe + h, 0), (sx + h, 0)], fill=rgb(colors[1]) + (255,))
    img.alpha_composite(tile, (x0, y0))


def color_panel(im, ts):
    """Opt-in top_shade colour panel (+ optional blueprint grid) that fades out downwards."""
    if isinstance(ts, str):
        ts = {"color": ts}
    alpha = ts.get("alpha", 1.0)
    y_op, y_fade = ts.get("opaque_to", int(H * 0.30)), ts.get("fade_to", int(H * 0.45))
    col = Image.new("L", (1, H))
    for y in range(H):
        f = 1.0 if y <= y_op else max(0.0, 1 - (y - y_op) / max(1, y_fade - y_op))
        col.putpixel((0, y), int(round(255 * alpha * f)))
    mask = col.resize((W, H))
    im = Image.composite(Image.new("RGB", (W, H), rgb(ts["color"])), im, mask)
    g = ts.get("grid")
    if g:
        step, every = g.get("step", 54), g.get("major_every", 5)
        gc = rgb(g.get("color", "#FFFFFF"))
        lines = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(lines)
        for i, v in enumerate(range(0, max(W, H), step)):
            major = every and i % every == 0
            a_ = int(255 * (g.get("major_alpha", 0.20) if major else g.get("alpha", 0.10)))
            lw = g.get("major_width", 2) if major else g.get("width", 1)
            if v < W:
                d.line((v, 0, v, H), fill=a_, width=lw)
            if v < H:
                d.line((0, v, W, v), fill=a_, width=lw)
        gmask = ImageChops.multiply(lines, mask)
        im = Image.composite(Image.new("RGB", (W, H), gc), im, gmask)
    return im


def hero_plate(path, zoom, focus, grade, top_shade, size=(W, H)):
    """Cover-fit crop + grade of the hero frame to size (default the full 1080x1920 cover)."""
    pw, ph = size
    im = Image.open(path).convert("RGB")
    s = max(pw / im.width, ph / im.height) * zoom
    im = im.resize((max(pw, round(im.width * s)), max(ph, round(im.height * s))), Image.LANCZOS)
    fx, fy = focus
    x0 = min(max(0, round(im.width * fx - pw / 2)), im.width - pw)
    y0 = min(max(0, round(im.height * fy - ph / 2)), im.height - ph)
    im = im.crop((x0, y0, x0 + pw, y0 + ph))
    if size != (W, H):   # poster window (layout B): grade only, no vignette / top shade
        im = ImageEnhance.Contrast(im).enhance(grade.get("contrast", 1.05))
        return ImageEnhance.Color(im).enhance(grade.get("saturation", 1.10))
    im = ImageEnhance.Contrast(im).enhance(grade.get("contrast", 1.05))
    im = ImageEnhance.Color(im).enhance(grade.get("saturation", 1.10))
    vig = grade.get("vignette", 0.0)
    if vig:
        vg = Image.new("L", (W // 8, H // 8))
        px = vg.load()
        for y in range(vg.height):
            for x in range(vg.width):
                d = math.hypot((x - vg.width / 2) / (vg.width / 2), (y - vg.height / 2) / (vg.height / 2)) / math.sqrt(2)
                px[x, y] = int(255 * (1 - vig * max(0.0, d - 0.35) / 0.65))
        vg = vg.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(20))
        im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), vg)
    if isinstance(top_shade, (str, dict)):
        im = color_panel(im, top_shade)
    elif top_shade:
        g = Image.new("L", (1, H))
        for y in range(H):
            g.putpixel((0, y), int(255 * top_shade * max(0.0, 1 - y / (H * 0.45))))
        im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, g.resize((W, H)))
    return im


class Painter:
    """Draws onto an RGBA image and records every content box (for the safe-zone check)."""

    def __init__(self, img):
        self.img = img
        self.boxes = []

    def shadow_rect(self, box, r, strength, off=(6, 10), blur=12):
        if strength <= 0:
            return
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([box[0] + off[0], box[1] + off[1], box[2] + off[0], box[3] + off[1]],
                                             r, fill=(0, 0, 0, int(255 * strength)))
        self.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))

    def text(self, xy, s, font, color, shadow=0.0, box=None, box_text=None, pad=(0, 0), radius=6, key=True):
        """xy = (x_left_of_ink, y_top_of_ink). Returns the outer box."""
        bb = font.getbbox(s)
        x, y = xy
        ox, oy = x - bb[0], y - bb[1]
        ink = (x, y, x + bb[2] - bb[0], y + bb[3] - bb[1])
        outer = (ink[0] - pad[1], ink[1] - pad[0], ink[2] + pad[1], ink[3] + pad[0])
        if box:
            self.shadow_rect(outer, radius, shadow)
            ImageDraw.Draw(self.img).rounded_rectangle(outer, radius, fill=rgb(box) + (255,))
            color = box_text or color
        elif shadow > 0:
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).text((ox, oy + 3), s, font=font, fill=(0, 0, 0, int(255 * shadow)))
            self.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
            self.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
        ImageDraw.Draw(self.img).text((ox, oy), s, font=font, fill=rgb(color) + (255,))
        if key:
            self.boxes.append(outer)
        return outer


def ink_size(font, s):
    bb = font.getbbox(s)
    return bb[2] - bb[0], bb[3] - bb[1]


def wrap(font, words, max_w):
    lines, cur = [], []
    for w in words:
        if cur and ink_size(font, " ".join(cur + [w]))[0] > max_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    return lines + [" ".join(cur)] if cur else lines


def balanced(font, words, max_w):
    """One line if it fits, else the 2-line split with the most even widths (no orphan words)."""
    if ink_size(font, " ".join(words))[0] <= max_w or len(words) < 2:
        return [" ".join(words)]
    best = min(range(1, len(words)), key=lambda k: max(ink_size(font, " ".join(words[:k]))[0],
                                                         ink_size(font, " ".join(words[k:]))[0]))
    return [" ".join(words[:best]), " ".join(words[best:])]


def draw_arrow(d, x, y, ang, col, dark, L=260):
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    px_, py_ = -uy, ux
    head, hw, sw = 110, 85, 34
    bx, by = x - ux * head, y - uy * head
    tx, ty = x - ux * L, y - uy * L
    pts = [(tx + px_ * sw / 2, ty + py_ * sw / 2), (bx + px_ * sw / 2, by + py_ * sw / 2),
           (bx + px_ * hw, by + py_ * hw), (x, y), (bx - px_ * hw, by - py_ * hw),
           (bx - px_ * sw / 2, by - py_ * sw / 2), (tx - px_ * sw / 2, ty - py_ * sw / 2)]
    d.polygon(pts, fill=col, outline=dark, width=10)
    return (min(p[0] for p in pts) - 5, min(p[1] for p in pts) - 5, max(p[0] for p in pts) + 5, max(p[1] for p in pts) + 5)


def case(s, mode):
    if mode == "upper":
        return s.upper()
    if mode == "lower":
        return s.lower()
    if mode == "sentence":
        return s[:1].upper() + s[1:]
    return s


def cap_box_text(img, P, x, top, s, font, color, key=True):
    """Draw s with its cap-height top at `top` (so mixed lines share a baseline). Returns the ink box."""
    bb, hb = font.getbbox(s), font.getbbox("H")
    ImageDraw.Draw(img).text((x - bb[0], top - hb[1]), s, font=font, fill=rgb(color) + (255,))
    box = (x, top, x + bb[2] - bb[0], top + hb[3] - hb[1])
    if key:
        P.boxes.append(box)
    return box


def stack_lines(text):
    """Layout B payoff: 'A|B' = explicit lines; else 1 word per line up to 3 words, pairs for 4+."""
    if "|" in text:
        return [ln.strip() for ln in text.split("|") if ln.strip()]
    w = text.split()
    if len(w) > 3:
        return [" ".join(w[i:i + 2]) for i in range(0, len(w), 2)]
    out = []   # short words (<= 3 letters, e.g. BY, OF) ride with the next word so no line is tiny
    for i, x in enumerate(w):
        if out and len(out[-1]) <= 3 and " " not in out[-1]:
            out[-1] += " " + x
        else:
            out.append(x)
    return out


def layout_b(a, st, font_path, pfont_path):
    """Layout B 'poster': flat paper header, thin rule, small kicker (= --setup), HUGE stacked payoff words in
    alternating colours, the hero frame in a window below (edge: line | hazard | torn)."""
    b = st.get("poster", {})
    mx = st["margin_x"]
    col_w = W - 2 * mx
    center = st.get("align", "center") == "center"
    s0, s1 = st["safe"]
    y0 = a.text_top if a.text_top is not None else st["text_top"]
    rule = b.get("rule") or {}
    rule_h, rule_gap = (rule.get("width", 6), rule.get("gap", 26)) if rule else (0, 0)
    kick = case(a.setup, b.get("kicker_case", "upper"))
    ksize = b.get("kicker_size", 58)
    kf = ImageFont.truetype(font_path, ksize)
    while ink_size(kf, kick)[0] > col_w and ksize > 36:
        ksize -= 2
        kf = ImageFont.truetype(font_path, ksize)
    klines = balanced(kf, kick.split(), col_w)
    k_cap = ink_size(kf, "H")[1]
    k_h = len(klines) * k_cap + (len(klines) - 1) * int(ksize * 0.35)
    plines = stack_lines(a.payoff.upper())
    mf = ImageFont.truetype(font_path, b.get("micro_size", 44)) if a.micro else None
    micro_h = (ink_size(mf, "H")[1] + b.get("gap", 30)) if mf else 0
    win_max, win_gap = b.get("window_max_top", 1200), b.get("window_gap", 44)
    psize = b.get("size", 250)
    while True:
        pf = ImageFont.truetype(pfont_path, psize)
        cap = ink_size(pf, "H")[1]
        lead = int(cap * b.get("leading", 0.16))
        p_h = len(plines) * cap + (len(plines) - 1) * lead
        bottom = y0 + rule_h + rule_gap + k_h + b.get("gap", 30) + p_h + micro_h
        fits = max(ink_size(pf, ln)[0] for ln in plines) <= col_w and bottom + win_gap <= win_max
        if fits or psize <= 90:
            break
        psize -= 6
    win_top = int(max(bottom + win_gap, b.get("window_min_top", 0)))

    img = Image.new("RGB", (W, H), rgb(b.get("bg", "#F4F1EA")))
    g = b.get("grid")
    if g:   # graph-paper grid over the paper
        gd = ImageDraw.Draw(img, "RGBA")
        gc = rgb(g.get("color", "#14212E"))
        for i, v in enumerate(range(0, H, g.get("step", 54))):
            major = g.get("major_every", 5) and i % g.get("major_every", 5) == 0
            al = int(255 * (g.get("major_alpha", 0.16) if major else g.get("alpha", 0.07)))
            lw = g.get("major_width", 2) if major else g.get("width", 1)
            gd.line((0, v, W, v), fill=gc + (al,), width=lw)
            if v < W:
                gd.line((v, 0, v, H), fill=gc + (al,), width=lw)
    win = hero_plate(a.hero, a.zoom, [float(v) for v in a.focus.split(",")], st["grade"], 0, size=(W, H - win_top))
    img.paste(win, (0, win_top))
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    edge = b.get("edge") or {}
    et, ec = edge.get("type", "line"), edge.get("color", b.get("rule", {}).get("color", "#000000"))
    if et == "line":
        d.rectangle((0, win_top, W, win_top + edge.get("height", 14)), fill=rgb(ec) + (255,))
    elif et == "hazard":
        hazard(img, (0, win_top, W, win_top + edge.get("height", 28)), edge.get("colors", [ec, "#14212E"]),
               edge.get("stripe", 26))
    elif et == "torn":   # ragged paper edge overhanging the image (deterministic teeth)
        import random
        rnd = random.Random(7)
        depth, step = edge.get("depth", 26), edge.get("step", 22)
        pts = [(0, win_top - 2)]
        for x in range(0, W + step, step):
            pts.append((x, win_top + rnd.randint(int(depth * 0.2), depth)))
        pts.append((W, win_top - 2))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon([(x, y + 6) for x, y in pts], fill=(0, 0, 0, 110))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
        d = ImageDraw.Draw(img)
        d.polygon(pts, fill=rgb(b.get("bg", "#F4F1EA")) + (255,))

    P = Painter(img)
    y = y0
    if rule:
        rl = rule.get("length", col_w)
        rx = (W - rl) / 2 if center else mx
        d.rectangle((rx, y, rx + rl, y + rule_h), fill=rgb(rule["color"]) + (255,))
        y += rule_h + rule_gap
    for ln in klines:
        w, _ = ink_size(kf, ln)
        cap_box_text(img, P, (W - w) / 2 if center else mx, y, ln, kf, b.get("kicker_color", "#111111"))
        y += k_cap + int(ksize * 0.35)
    y += b.get("gap", 30) - int(ksize * 0.35)
    cols = b.get("colors", ["#111111"])
    for i, ln in enumerate(plines):
        w, _ = ink_size(pf, ln)
        cap_box_text(img, P, (W - w) / 2 if center else mx, y, ln, pf, cols[i % len(cols)])
        y += cap + lead
    if mf:
        y += b.get("gap", 30) - lead
        w, _ = ink_size(mf, a.micro)
        cap_box_text(img, P, (W - w) / 2 if center else mx, y, a.micro, mf,
                     b.get("micro_color", b.get("kicker_color", "#111111")))
    return img, P, plines


def layout_c(a, st, font_path, pfont_path):
    """Layout C 'caption': full-bleed hero, the hook as ONE flowing caption line near the bottom of the safe zone
    (setup words plain, payoff words on a single highlight box), over a dark gradient or a solid lower-third band.
    Pair with --sticker (+ --sticker-label) as a small rounded label on the object."""
    c = st.get("caption", {})
    variant = c.get("variant", "caption")
    if variant == "punch":
        return layout_punch(a, st, font_path, pfont_path)
    if variant == "diagram":
        return layout_diagram(a, st, font_path, pfont_path)
    mx = st["margin_x"]
    col_w = W - 2 * mx
    center = st.get("align", "center") == "center"
    img = hero_plate(a.hero, a.zoom, [float(v) for v in a.focus.split(",")], st["grade"], 0)
    cfont = resolve_font(c["font"]) if c.get("font") else pfont_path
    toks = [(w, False) for w in case(a.setup, c.get("setup_case", "asis")).split()] + \
           [(w, True) for w in case(a.payoff.replace("|", " "), c.get("payoff_case", "upper")).split()]
    pad_y, pad_x = c.get("pad", [10, 22])
    gap_x = c.get("box_gap", 10)

    def segs(line):
        out = []
        for w, hl in line:
            if out and out[-1][1] == hl:
                out[-1][0].append(w)
            else:
                out.append([[w], hl])
        return [(" ".join(ws), hl) for ws, hl in out]

    def width(f, line):
        tot, sp = 0, f.getlength(" ")
        for i, (s, hl) in enumerate(segs(line)):
            tot += ink_size(f, s)[0] + (2 * pad_x if hl else 0) + (sp + (gap_x if hl or segs(line)[i - 1][1] else 0)
                                                                     if i else 0)
        return tot

    size = c.get("size", 104)
    while True:
        f = ImageFont.truetype(cfont, size)
        pay = [t for t in toks if t[1]]
        stoks = toks[:len(toks) - len(pay)]
        lines = [stoks] if width(f, stoks) <= col_w or len(stoks) < 2 else \
            [stoks[:k], stoks[k:]] if (k := min(range(1, len(stoks)), key=lambda k: max(
                width(f, stoks[:k]), width(f, stoks[k:])))) else [stoks]
        if width(f, lines[-1] + pay) <= col_w:   # payoff rides on the last setup line if it fits...
            lines[-1] = lines[-1] + pay
        else:                                     # ...else gets its own line; never split the highlight box
            lines.append(pay)
        wraps = len(lines) > 1 + (lines[-1] is pay) and size > c.get("size", 104) * 0.85   # shrink a bit to keep setup on 1 line
        if (not wraps and len(lines) <= c.get("max_lines", 3) and max(width(f, ln) for ln in lines) <= col_w) \
                or size <= 64:
            break
        size -= 4
    cap = ink_size(f, "H")[1]
    desc = (f.getbbox("Hgjpy")[3] - f.getbbox("H")[3]) if c.get("payoff_case", "upper") != "upper" or \
        c.get("setup_case", "asis") != "upper" else 0
    row = cap + desc + 2 * pad_y
    lgap = c.get("line_gap", 14)
    total = len(lines) * row + (len(lines) - 1) * lgap
    yb = a.text_top + total if a.text_top is not None else c.get("y_bottom", 1590)
    ytop = yb - total

    band = c.get("band") or {"type": "gradient"}
    img = img.convert("RGBA")
    if band.get("type") == "solid":
        bp = band.get("pad", 34)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lay).rectangle((0, ytop - bp, W, yb + bp),
                                      fill=rgb(band.get("color", "#000000")) + (int(255 * band.get("alpha", 0.92)),))
        img.alpha_composite(lay)
        if band.get("rule"):
            ImageDraw.Draw(img).rectangle((0, ytop - bp - band.get("rule_h", 12), W, ytop - bp),
                                          fill=rgb(band["rule"]) + (255,))
    else:   # dark gradient from above the caption down to the bottom edge
        g0, a_ = ytop - band.get("fade", 360), band.get("alpha", 0.78)
        col = Image.new("L", (1, H))
        for yy in range(H):
            col.putpixel((0, yy), int(255 * a_ * min(1.0, max(0.0, (yy - g0) / max(1, ytop - 40 - g0)))))
        img.alpha_composite(Image.composite(Image.new("RGBA", (W, H), rgb(band.get("color", "#000000")) + (255,)),
                                            Image.new("RGBA", (W, H), (0, 0, 0, 0)), col.resize((W, H))))

    P = Painter(img)
    sp = f.getlength(" ")
    y = ytop
    for ln in lines:
        lw = width(f, ln)
        x = (W - lw) / 2 if center else mx
        sg = segs(ln)
        for i, (s, hl) in enumerate(sg):
            if i:
                x += sp + (gap_x if hl or sg[i - 1][1] else 0)
            w, _ = ink_size(f, s)
            if hl:
                box = (x, y, x + w + 2 * pad_x, y + row)
                ImageDraw.Draw(img).rounded_rectangle(box, c.get("radius", 14), fill=rgb(c.get("box", "#E63946")) + (255,))
                cap_box_text(img, P, x + pad_x, y + pad_y, s, f, c.get("box_text", "#FFFFFF"), key=False)
                P.boxes.append(box)
                x += w + 2 * pad_x
            else:
                if c.get("shadow", 0):
                    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    bb = f.getbbox(s)
                    ImageDraw.Draw(sh).text((x - bb[0], y + pad_y - f.getbbox("H")[1] + 3), s, font=f,
                                            fill=(0, 0, 0, int(255 * c["shadow"])))
                    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
                cap_box_text(img, P, x, y + pad_y, s, f, c.get("color", "#FFFFFF"))
                x += w
        y += row + lgap
    if a.micro:
        mf = ImageFont.truetype(font_path, c.get("micro_size", 40))
        w, _ = ink_size(mf, a.micro)
        my = ytop - c.get("micro_gap", 26) - ink_size(mf, "H")[1]
        cap_box_text(img, P, (W - w) / 2 if center else mx, my, a.micro, mf, c.get("micro_color", "#FFFFFF"))
    return img, P, [" ".join(w for w, _ in ln) for ln in lines]

def edge_mask(strength, inner=0.45, outer=0.95):
    """L mask: 0 in the centre, rising to `strength` towards the frame edges (elliptical)."""
    m = Image.new("L", (W // 8, H // 8))
    px = m.load()
    for y in range(m.height):
        for x in range(m.width):
            d = math.hypot((x - m.width / 2) / (m.width / 2), (y - m.height / 2) / (m.height / 2)) / math.sqrt(2)
            px[x, y] = int(255 * strength * min(1.0, max(0.0, (d - inner) / (outer - inner))))
    return m.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(16))


def layout_punch(a, st, font_path, pfont_path):
    """Layout C, variant 'punch' (news): darkened-edge hero, ONE giant white headline (= --payoff) with a heavy black
    stroke in the upper third, one key word (--key, default last word) in the accent colour, the setup on a slightly
    rotated yellow tape strip under it; use --circle / --arrow to point at the key object."""
    c = st["caption"]
    mx = st["margin_x"]
    col_w = W - 2 * mx
    img = hero_plate(a.hero, a.zoom, [float(v) for v in a.focus.split(",")], st["grade"], 0).convert("RGBA")
    if c.get("edge_dark"):
        img.alpha_composite(Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)),
                                            Image.new("RGBA", (W, H), (0, 0, 0, 0)), edge_mask(c["edge_dark"])))
    P = Painter(img)
    words = a.payoff.replace("|", " ").upper().split()
    key = (a.key or words[-1]).upper()
    plines = stack_lines(a.payoff.upper())
    sw_ = c.get("stroke", 14)
    size = c.get("size", 210)
    while True:
        f = ImageFont.truetype(pfont_path, size)
        if max(f.getlength(ln) for ln in plines) + 2 * sw_ <= col_w or size <= 80:
            break
        size -= 6
    cap = ink_size(f, "H")[1]
    y = a.text_top if a.text_top is not None else st["text_top"]
    lead = int(cap * c.get("leading", 0.18))
    for ln in plines:
        lw = f.getlength(ln)
        x = (W - lw) / 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hb = f.getbbox("H")
        ImageDraw.Draw(sh).text((x, y - hb[1] + 10), ln, font=f, fill=(0, 0, 0, 170), stroke_width=sw_,
                                stroke_fill=(0, 0, 0, 170))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
        d = ImageDraw.Draw(img)
        for i, wd in enumerate(ln.split()):
            col = c.get("key_color", "#E63946") if wd.strip("?!.,") == key.strip("?!.,") else c.get("color", "#FFFFFF")
            d.text((x, y - hb[1]), wd, font=f, fill=rgb(col) + (255,), stroke_width=sw_,
                   stroke_fill=rgb(c.get("stroke_color", "#000000")) + (255,))
            x += f.getlength(wd + " ")
        P.boxes.append(((W - lw) / 2 - sw_, y - sw_, (W + lw) / 2 + sw_, y + cap + sw_))
        y += cap + lead
    # tape strip with the setup
    t = c.get("tape", {})
    tf = ImageFont.truetype(font_path, t.get("size", 60))
    ttxt = case(a.setup, t.get("case", "upper"))
    while ink_size(tf, ttxt)[0] + 2 * t.get("pad", [18, 40])[1] > col_w and tf.size > 36:
        tf = ImageFont.truetype(font_path, tf.size - 2)
    tw, _ = ink_size(tf, ttxt)
    tcap = ink_size(tf, "H")[1]
    py_, px_ = t.get("pad", [18, 40])
    ty = y - lead + c.get("tape_gap", 34)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    box = ((W - tw) / 2 - px_, ty, (W + tw) / 2 + px_, ty + tcap + 2 * py_)
    ld = ImageDraw.Draw(layer)
    ld.rectangle((box[0] + 8, box[1] + 10, box[2] + 8, box[3] + 10), fill=(0, 0, 0, 120))
    ld.rectangle(box, fill=rgb(t.get("color", "#FFD21F")) + (255,))
    for xx in (box[0], box[2]):   # ragged tape ends
        for k in range(int(box[1]), int(box[3]), 12):
            ld.polygon([(xx, k), (xx + (8 if xx == box[0] else -8), k + 6), (xx, k + 12)], fill=(0, 0, 0, 0))
    cap_box_text(layer, Painter(layer), (W - tw) / 2, ty + py_, ttxt, tf, t.get("text", "#0B1F3A"), key=False)
    layer = layer.rotate(t.get("rotate", -2.5), resample=Image.BICUBIC,
                         center=((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
    img.alpha_composite(layer)
    P.boxes.append(layer.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox())
    if a.micro:
        mf = ImageFont.truetype(font_path, c.get("micro_size", 44))
        w, _ = ink_size(mf, a.micro)
        my = P.boxes[-1][3] + c.get("micro_gap", 26)
        bb = mf.getbbox(a.micro)
        ImageDraw.Draw(img).text(((W - w) / 2 - bb[0], my - mf.getbbox("H")[1]), a.micro, font=mf,
                                 fill=rgb(c.get("micro_color", "#FFFFFF")) + (255,), stroke_width=5,
                                 stroke_fill=(0, 0, 0, 255))
        P.boxes.append(((W - w) / 2, my, (W + w) / 2, my + ink_size(mf, "H")[1]))
    return img, P, plines


def layout_diagram(a, st, font_path, pfont_path):
    """Layout C, variant 'diagram' (how it works): hero with a blueprint-grid tint on its edges, the hook in a white
    rounded speech-bubble card at the top-left (setup charcoal, payoff accent), and thin white callout lines with
    dots from 2-3 parts of the object to small rounded labels (--callout 'x,y:LABEL[@lx,ly]', repeatable)."""
    c = st["caption"]
    mx = st["margin_x"]
    img = hero_plate(a.hero, a.zoom, [float(v) for v in a.focus.split(",")], st["grade"], 0).convert("RGBA")
    g = c.get("grid", {})
    em = edge_mask(1.0, g.get("inner", 0.40), g.get("outer", 0.85))
    tint = Image.new("RGBA", (W, H), rgb(g.get("tint", "#00796E")) + (255,))
    img.alpha_composite(Image.composite(tint, Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                                        em.point(lambda v: int(v * g.get("tint_alpha", 0.35)))))
    lines = Image.new("L", (W, H), 0)
    ld = ImageDraw.Draw(lines)
    step, every = g.get("step", 54), g.get("major_every", 5)
    for i, v in enumerate(range(0, H, step)):
        al = int(255 * (g.get("major_alpha", 0.45) if every and i % every == 0 else g.get("alpha", 0.25)))
        ld.line((0, v, W, v), fill=al, width=2 if i % every == 0 else 1)
        if v < W:
            ld.line((v, 0, v, H), fill=al, width=2 if i % every == 0 else 1)
    img.alpha_composite(Image.composite(Image.new("RGBA", (W, H), rgb(g.get("color", "#FFFFFF")) + (255,)),
                                        Image.new("RGBA", (W, H), (0, 0, 0, 0)), ImageChops.multiply(lines, em)))
    P = Painter(img)
    # hook card
    k = c.get("card", {})
    pad = k.get("pad", 40)
    maxw = k.get("max_width", 760) - 2 * pad
    sf = ImageFont.truetype(font_path, k.get("setup_size", 60))
    stxt = case(a.setup, k.get("setup_case", "asis"))
    slines = balanced(sf, stxt.split(), maxw)
    ptxt = case(a.payoff.replace("|", " "), k.get("payoff_case", "upper"))
    psize = k.get("payoff_size", 120)
    while True:
        pf = ImageFont.truetype(pfont_path, psize)
        plines = [ln.strip() for ln in a.payoff.upper().split("|")] if "|" in a.payoff else \
            wrap(pf, ptxt.split(), maxw)
        if max(ink_size(pf, ln)[0] for ln in plines) <= maxw or psize <= 64:
            break
        psize -= 4
    scap, pcap = ink_size(sf, "H")[1], ink_size(pf, "H")[1]
    sgap, pgap, mid = int(scap * 0.45), int(pcap * 0.22), k.get("gap", 26)
    inner_h = len(slines) * scap + (len(slines) - 1) * sgap + mid + len(plines) * pcap + (len(plines) - 1) * pgap
    inner_w = max([ink_size(sf, ln)[0] for ln in slines] + [ink_size(pf, ln)[0] for ln in plines])
    x0 = mx
    y0 = a.text_top if a.text_top is not None else st["text_top"]
    card = (x0, y0, x0 + inner_w + 2 * pad, y0 + inner_h + 2 * pad)
    tail = k.get("tail", 46)
    tail_pts = [(card[0] + 70, card[3] - 2), (card[0] + 70 + tail * 1.4, card[3] - 2), (card[0] + 60, card[3] + tail)]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([v + o for v, o in zip(card, (6, 12, 6, 12))], k.get("radius", 36), fill=(0, 0, 0, 110))
    sd.polygon([(x + 6, y + 12) for x, y in tail_pts], fill=(0, 0, 0, 110))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(card, k.get("radius", 36), fill=rgb(k.get("box", "#FFFFFF")) + (255,))
    d.polygon(tail_pts, fill=rgb(k.get("box", "#FFFFFF")) + (255,))
    if k.get("accent"):
        d.rounded_rectangle((card[0], card[1] + 30, card[0] + 10, card[3] - 30), 5, fill=rgb(k["accent"]) + (255,))
    y = y0 + pad
    for ln in slines:
        cap_box_text(img, P, x0 + pad, y, ln, sf, k.get("setup_color", "#1B1F24"), key=False)
        y += scap + sgap
    y += mid - sgap
    for ln in plines:
        cap_box_text(img, P, x0 + pad, y, ln, pf, k.get("payoff_color", "#00796E"), key=False)
        y += pcap + pgap
    P.boxes.append((card[0], card[1], card[2], card[3] + tail))
    # callouts
    q = c.get("callout", {})
    lf = ImageFont.truetype(font_path, q.get("size", 38))
    lcol, lw_ = rgb(q.get("line", "#FFFFFF")), q.get("width", 4)
    for spec in a.callout:
        pt, _, rest = spec.partition(":")
        label, _, at = rest.partition("@")
        x, yy = [float(v) for v in pt.split(",")]
        lx, ly = [float(v) for v in at.split(",")] if at else (x + (230 if x < W / 2 else -230), yy + 170)
        tw, _ = ink_size(lf, label)
        lcap = ink_size(lf, "H")[1]
        bpy, bpx = q.get("pad", [14, 26])
        box = (lx - tw / 2 - bpx, ly - lcap / 2 - bpy, lx + tw / 2 + bpx, ly + lcap / 2 + bpy)
        ex = min(max(x, box[0] + 20), box[2] - 20)
        ey = box[1] if yy < box[1] else box[3] if yy > box[3] else ly
        if box[0] <= x <= box[2] and box[1] <= yy <= box[3]:
            ex, ey = lx, ly
        if q.get("line_shadow"):
            ImageDraw.Draw(img).line([(x, yy), (ex, ey)], fill=rgb(q["line_shadow"]) + (150,), width=lw_ + 4)
        d = ImageDraw.Draw(img)
        d.line([(x, yy), (ex, ey)], fill=lcol + (255,), width=lw_)
        r = q.get("dot_r", 13)
        d.ellipse((x - r, yy - r, x + r, yy + r), fill=lcol + (255,), outline=rgb(q.get("dot_ring", "#00B3A4")) + (255,),
                  width=5)
        P.shadow_rect(box, 30, q.get("shadow", 0.35))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(box, int((box[3] - box[1]) / 2), fill=rgb(q.get("box", "#1B1F24")) + (255,),
                            outline=rgb(q["border"]) + (255,) if q.get("border") else None, width=q.get("border_w", 4))
        cap_box_text(img, P, lx - tw / 2, ly - lcap / 2, label, lf, q.get("text", "#FFFFFF"), key=False)
        P.boxes += [box, (x - r, yy - r, x + r, yy + r)]
    return img, P, plines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hero")
    ap.add_argument("out")
    ap.add_argument("--setup", required=True, help="setup line, 2-5 words")
    ap.add_argument("--payoff", required=True,
                    help="payoff, 1-3 words (preset payoff.max_words), ALL CAPS ('|' = box break)")
    ap.add_argument("--micro", help="optional small context line under the payoff")
    ap.add_argument("--sticker", help="optional fact sticker text (must be stated in the reel)")
    ap.add_argument("--sticker-at", default="540,1350", help="sticker centre x,y")
    ap.add_argument("--sticker-label", help="optional small label line above the sticker text (e.g. TOWER)")
    ap.add_argument("--badge", help="badge text (overrides the preset's badge text; must be true)")
    ap.add_argument("--style", default="wjh", help="preset name in tools/thumb_styles/ or a .json path")
    ap.add_argument("--accent", help="override payoff box colour")
    ap.add_argument("--text-top", type=float)
    ap.add_argument("--arrow")
    ap.add_argument("--circle")
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--focus", default="0.5,0.5")
    ap.add_argument("--debug-safe", action="store_true")
    ap.add_argument("--key", help="layout C punch: the payoff word drawn in the accent colour (default: last word)")
    ap.add_argument("--callout", action="append", default=[],
                    help="layout C diagram, repeatable: 'x,y:LABEL' or 'x,y:LABEL@lx,ly' (label centre)")
    a = ap.parse_args()

    st = load_style(a.style)
    if a.accent:
        st["payoff"]["box"] = a.accent
    font_path = resolve_font(st["font"])
    pfont_path = resolve_font(st["payoff"]["font"]) if st["payoff"].get("font") else font_path
    max_pw = st["payoff"].get("max_words", 3)
    sw, pw = a.setup.split(), a.payoff.replace("|", " ").split()
    if not 1 <= len(pw) <= max_pw:
        sys.exit("payoff must be 1-%d words (got %d)" % (max_pw, len(pw)))
    if len(sw) + len(pw) > 8:
        sys.exit("hook is %d words; max 8 (setup + payoff)" % (len(sw) + len(pw)))
    if (a.arrow or a.circle) and not st.get("pointers", True):
        sys.exit("style %r does not allow arrows/circles (THUMBNAIL-STYLE.md: no arrows or circles)" % a.style)

    lay = str(st.get("layout", "A")).upper()
    if lay in ("B", "C"):
        img, P, plines = (layout_b if lay == "B" else layout_c)(a, st, font_path, pfont_path)
        draw_extras(img, P, a, st, font_path)
        return finish(img, P, a, st, plines)
    if lay != "A":
        sys.exit("unknown layout %r (A, B or C)" % lay)

    img = hero_plate(a.hero, a.zoom, [float(v) for v in a.focus.split(",")], st["grade"], st.get("top_shade", 0))
    img = img.convert("RGBA")
    P = Painter(img)
    mx = st["margin_x"]
    col_w = W - 2 * mx
    y = a.text_top if a.text_top is not None else st["text_top"]
    center = st.get("align", "center") == "center"

    def xpos(w, shift=0):
        return (W - w) / 2 + shift if center else mx + shift

    # ticker strip (decorative, sits just above the hook)
    tk = st.get("ticker")
    if tk:
        th, ty = tk.get("height", 10), y + tk.get("y_offset", -26)
        d = ImageDraw.Draw(img)
        d.rectangle((mx, ty, W - mx, ty + th), fill=rgb(tk["color"]) + (255,))
        d.rectangle((mx, ty, mx + tk.get("accent_w", 140), ty + th), fill=rgb(tk["accent"]) + (255,))

    # setup line(s)
    s = st["setup"]
    spad = (14, 24) if s.get("box") else (0, 0)
    stext = case(a.setup, s.get("case", "asis"))
    for ssize in range(s["size"], int(s["size"] * 0.8) - 1, -2):   # one line if it fits at >= 80% size
        sf = ImageFont.truetype(font_path, ssize)
        if ink_size(sf, stext)[0] <= col_w - 2 * spad[1]:
            break
    for ln in balanced(sf, stext.split(), col_w - 2 * spad[1]):
        w, h = ink_size(sf, ln)
        box = P.text((xpos(w), y + spad[0]), ln, sf, s["color"], shadow=s.get("shadow", 0.45),
                     box=s.get("box"), box_text=s.get("box_text"), pad=spad, radius=6)
        y = box[3] + st["gap"] * 0.6
    y += st["gap"]

    # payoff boxes
    p = st["payoff"]
    pf = ImageFont.truetype(pfont_path, p["size"])
    if p.get("min_size") and "|" not in a.payoff:   # opt-in: keep one line by shrinking to min_size before wrapping
        for fsize in range(p["size"], p["min_size"] - 1, -2):
            f1 = ImageFont.truetype(pfont_path, fsize)
            if ink_size(f1, a.payoff.upper())[0] <= p["max_width"] - 2 * p["pad"][1]:
                pf = f1
                break
    plines = [ln.strip() for ln in a.payoff.upper().split("|")] if "|" in a.payoff else \
        wrap(pf, a.payoff.upper().split(), p["max_width"] - 2 * p["pad"][1])
    size = pf.size
    while max(ink_size(pf, ln)[0] for ln in plines) + 2 * p["pad"][1] > min(p["max_width"], col_w) and size > 60:
        size -= 4
        pf = ImageFont.truetype(pfont_path, size)
    cap_h = ink_size(pf, "H")[1]
    for i, ln in enumerate(plines):
        w, _ = ink_size(pf, ln)
        shift = (p.get("stagger", 0) * (1 if i % 2 else -1)) if len(plines) > 1 else 0
        bb = pf.getbbox(ln)
        # align on cap height so boxes are equal height regardless of descenders
        x = xpos(w, shift)
        top = y + p["pad"][0]
        outer = (x - p["pad"][1], top - p["pad"][0], x + w + p["pad"][1], top + cap_h + p["pad"][0])
        P.shadow_rect(outer, p["radius"], p.get("shadow", 0.35))
        ImageDraw.Draw(img).rounded_rectangle(outer, p["radius"], fill=rgb(p["box"]) + (255,))
        ImageDraw.Draw(img).text((x - bb[0], top - pf.getbbox("H")[1]), ln, font=pf, fill=rgb(p["text"]) + (255,))
        P.boxes.append(outer)
        y = outer[3] + max(8, st["gap"] * 0.5)
    us = p.get("under_strip")
    if us:   # hazard-stripe band glued under the last payoff box
        strip = (outer[0], outer[3], outer[2], outer[3] + us.get("height", 20))
        hazard(img, strip, us.get("colors", [p["box"], p["text"]]), us.get("stripe", 26))
        P.boxes.append(strip)
        y = strip[3] + max(8, st["gap"] * 0.5)

    if a.micro:
        m = st["micro"]
        mf = ImageFont.truetype(font_path, m["size"])
        w, _ = ink_size(mf, a.micro)
        P.text((xpos(w), y + 10 + 10), a.micro, mf, m["text"], box=m.get("box"), box_text=m["text"], pad=(10, 20))

    draw_extras(img, P, a, st, font_path)
    finish(img, P, a, st, plines)


def draw_extras(img, P, a, st, font_path):
    """Shared by every layout: fact sticker (--sticker), pointer (--arrow/--circle) and badge."""
    p, mx = st["payoff"], st["margin_x"]
    sticker_box = None
    if a.sticker:
        k = st["sticker"]
        a.sticker_label = a.sticker_label or k.get("label")
        ksize, kmax = k["size"], k.get("max_width", 420)
        kf = ImageFont.truetype(font_path, ksize)
        cx, cy = [float(v) for v in a.sticker_at.split(",")]
        if k.get("min_size"):   # opt-in: shrink (down to min_size) to keep one line, then to avoid overflow
            while ink_size(kf, a.sticker)[0] > kmax and ksize > k["min_size"]:
                ksize -= 2
                kf = ImageFont.truetype(font_path, ksize)
        lines = wrap(kf, a.sticker.split(), kmax)
        if k.get("min_size"):
            while max(ink_size(kf, ln)[0] for ln in lines) > kmax and ksize > k["min_size"]:
                ksize -= 2
                kf = ImageFont.truetype(font_path, ksize)
                lines = wrap(kf, a.sticker.split(), kmax)
        lh = ksize * 1.15
        ws = [ink_size(kf, ln)[0] for ln in lines]
        kpad = k.get("pad", [14, 24])
        lab_h = lab_w = 0
        if a.sticker_label:
            lf = ImageFont.truetype(font_path, k.get("label_size", int(round(ksize * 0.45))))
            lab_w, _ = ink_size(lf, a.sticker_label)
            lab_h = ink_size(lf, "H")[1] + k.get("label_gap", 6)
        bw, bh = max(ws + [lab_w]) + 2 * kpad[1], lh * len(lines) + 2 * kpad[0] + lab_h
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        P.shadow_rect(box, k["radius"], k.get("shadow", 0.35))
        kb = k.get("border")
        if kb:
            ImageDraw.Draw(img).rounded_rectangle(box, k["radius"], fill=rgb(k["box"]) + (255,),
                                                  outline=rgb(kb["color"]) + (255,), width=kb.get("width", 6))
        else:
            ImageDraw.Draw(img).rounded_rectangle(box, k["radius"], fill=rgb(k["box"]) + (255,))
        left = k.get("align", "center") == "left"
        if a.sticker_label:
            bb = lf.getbbox(a.sticker_label)
            lx = box[0] + kpad[1] if left else cx - lab_w / 2
            ImageDraw.Draw(img).text((lx - bb[0], box[1] + kpad[0] - lf.getbbox("H")[1]), a.sticker_label, font=lf,
                                     fill=rgb(k.get("label_color", k["text"])) + (255,))
        for i, ln in enumerate(lines):
            bb = kf.getbbox(ln)
            tx = box[0] + kpad[1] if left else cx - ws[i] / 2
            ImageDraw.Draw(img).text((tx - bb[0], box[1] + kpad[0] + lab_h + i * lh - kf.getbbox("H")[1]), ln,
                                     font=kf, fill=rgb(k["text"]) + (255,))
        tk_ = k.get("ticks")
        if tk_:   # measuring-tape ticks rising from the inside of the bottom edge
            inset = kb.get("width", 6) if kb else 0
            tcol = rgb(tk_.get("color", kb["color"] if kb else k["text"])) + (255,)
            step, tl, every = tk_.get("step", 18), tk_.get("len", 24), tk_.get("major_every", 5)
            yb = box[3] - inset
            td = ImageDraw.Draw(img)
            for j, tx in enumerate(range(int(box[0] + kpad[1] * 0.5), int(box[2] - inset - 2), step)):
                ln_ = tl if every and j % every == 0 else tl * 0.5
                td.line((tx, yb - ln_, tx, yb), fill=tcol, width=tk_.get("width", 3))
        P.boxes.append(box)
        sticker_box = box

    d = ImageDraw.Draw(img)
    accent = rgb(p["box"]) + (255,)
    pt = st.get("pointer") or {}
    if a.arrow and pt.get("style", "arrow") == "leader":
        vals = [float(v) for v in a.arrow.split(",")]
        x, yy = vals[0], vals[1]
        lcol = rgb(pt.get("color", p["box"])) + (255,)
        lw, r = pt.get("width", 6), pt.get("dot_r", 14)
        if sticker_box:
            b = sticker_box
            sy = b[1] + (b[3] - b[1]) * pt.get("from_y", 0.5)
            sx = b[2] if x >= (b[0] + b[2]) / 2 else b[0]
        else:
            ang = math.radians(vals[2] if len(vals) > 2 else 0)
            sx, sy = x - math.cos(ang) * pt.get("length", 260), yy - math.sin(ang) * pt.get("length", 260)
        sgn = 1 if x >= sx else -1
        ex = x - sgn * min(abs(x - sx), abs(yy - sy) * math.tan(math.radians(pt.get("slant", 10))))
        d.line([(sx, sy), (ex, sy), (x, yy)], fill=lcol, width=lw, joint="curve")
        d.ellipse((x - r, yy - r, x + r, yy + r), fill=rgb(pt.get("dot_color", "#FFFFFF")) + (255,), outline=lcol,
                  width=max(3, lw - 1))
        P.boxes.append((x - r, yy - r, x + r, yy + r))
    elif a.arrow:
        x, yy, ang = [float(v) for v in a.arrow.split(",")]
        P.boxes.append(draw_arrow(d, x, yy, ang, accent, (0, 0, 0, 255)))
    if a.circle:
        x, yy, r = [float(v) for v in a.circle.split(",")]
        d.ellipse((x - r - 6, yy - r - 6, x + r + 6, yy + r + 6), outline=(0, 0, 0, 255), width=34)
        d.ellipse((x - r, yy - r, x + r, yy + r), outline=accent, width=22)
        P.boxes.append((x - r - 23, yy - r - 23, x + r + 23, yy + r + 23))

    bg = st.get("badge")
    if a.badge:
        bg = dict(bg or {"box": p["box"], "text_color": p["text"]}, text=a.badge)
    if bg and bg.get("text"):
        bf = ImageFont.truetype(font_path, bg.get("size", 34))
        w, _ = ink_size(bf, bg["text"])
        bx = bg["x"] if "x" in bg else W - mx - w
        bpad, brad = tuple(bg.get("pad", (8, 16))), bg.get("radius", 4)
        bcol = bg.get("text_color", "#FFFFFF")
        if not bg.get("rotate") and not bg.get("outline"):
            P.text((bx, bg.get("y", 300)), bg["text"], bf, bcol, box=bg.get("box"), box_text=bcol, pad=bpad,
                   radius=brad, key=not bg.get("decorative"))
        else:   # stamp: drawn on its own layer, optionally outlined and rotated about its centre
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            outer = Painter(layer).text((bx, bg.get("y", 300)), bg["text"], bf, bcol, box=bg.get("box"),
                                        box_text=bcol, pad=bpad, radius=brad)
            ol = bg.get("outline")
            if ol:
                ImageDraw.Draw(layer).rounded_rectangle(outer, brad, outline=rgb(ol["color"]) + (255,),
                                                        width=ol.get("width", 5))
            if bg.get("rotate"):
                layer = layer.rotate(bg["rotate"], resample=Image.BICUBIC,
                                     center=((outer[0] + outer[2]) / 2, (outer[1] + outer[3]) / 2))
            img.alpha_composite(layer)
            if not bg.get("decorative"):
                P.boxes.append(layer.getchannel("A").getbbox())



def finish(img, P, a, st, plines):
    """Shared tail: frame border, safe-zone check, JPEG save (<10 MB), optional debug overlay."""
    d = ImageDraw.Draw(img)
    bd = st.get("border", {})
    if bd.get("width"):
        d.rectangle((0, 0, W - 1, H - 1), outline=rgb(bd["color"]) + (255,), width=bd["width"])

    s0, s1 = st["safe"]
    bad = [b for b in P.boxes if b[1] < s0 or b[3] > s1 or b[0] < 0 or b[2] > W]
    if bad:
        sys.exit("key content outside the safe zone y %d..%d: %s" % (s0, s1, [tuple(int(v) for v in b) for b in bad]))

    img = img.convert("RGB")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    for q in (92, 88, 84, 80, 75, 70):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() < MAX_BYTES:
            break
    open(a.out, "wb").write(buf.getvalue())
    print("%s  %dx%d  %.0f KB  q%d  style %s  hook: %r / %r" % (a.out, W, H, buf.tell() / 1024, q, a.style,
                                                               a.setup, plines))
    if a.debug_safe:
        dbg = img.copy()
        dd = ImageDraw.Draw(dbg)
        for yy in (s0, s1):
            dd.line((0, yy, W, yy), fill=(0, 255, 0), width=6)
        for b in P.boxes:
            dd.rectangle(b, outline=(255, 255, 0), width=3)
        dbg.save(os.path.splitext(a.out)[0] + "-debug.jpg", quality=80)


if __name__ == "__main__":
    main()

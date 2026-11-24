from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import math, sys

BASE = "/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan/"
W, H = 1640, 624
S = 2
BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(p, size):
    return ImageFont.truetype(p, size * S)


def gradient(c1, c2):
    ys, xs = np.mgrid[0:H * S, 0:W * S].astype(np.float32)
    cx, cy = W * S / 2, H * S * 0.45
    maxd = math.hypot(cx, cy)
    t = np.minimum(1, np.hypot(xs - cx, (ys - cy) * 1.6) / maxd)[..., None]
    c1 = np.array(c1, np.float32); c2 = np.array(c2, np.float32)
    arr = c1 + (c2 - c1) * t
    return Image.fromarray(arr.astype(np.uint8))


def center_text(d, y, text, f, fill, spacing=0):
    if spacing:
        widths = [d.textlength(ch, font=f) for ch in text]
        total = sum(widths) + spacing * S * (len(text) - 1)
        x = (W * S - total) / 2
        for ch, w in zip(text, widths):
            d.text((x, y), ch, font=f, fill=fill)
            x += w + spacing * S
    else:
        w = d.textlength(text, font=f)
        d.text(((W * S - w) / 2, y), text, font=f, fill=fill)


# ---------------------------------------------------------------- icon helpers
# every icon draws onto its own RGBA canvas (size sz, in cover px) in white,
# then gets tinted/faded/rotated and pasted onto the overlay layer.

def canvas(sz):
    c = Image.new("RGBA", (sz * S, sz * S), (0, 0, 0, 0))
    return c, ImageDraw.Draw(c)


def P(v):
    return v * S


WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)
LW = 5  # line weight in cover px


def arc(d, cx, cy, r, a0, a1, w=LW):
    d.arc((P(cx - r), P(cy - r), P(cx + r), P(cy + r)), a0, a1, fill=WHITE, width=P(w))


def circle(d, cx, cy, r, w=LW, fill=None):
    d.ellipse((P(cx - r), P(cy - r), P(cx + r), P(cy + r)), outline=WHITE if w else None,
              width=P(w) if w else 0, fill=fill)


def line(d, pts, w=LW):
    d.line([(P(x), P(y)) for x, y in pts], fill=WHITE, width=P(w), joint="curve")
    for x, y in (pts[0], pts[-1]):
        circle(d, x, y, w / 2, w=0, fill=WHITE)


def rrect(d, box, r, w=LW, fill=None):
    d.rounded_rectangle([P(v) for v in box], radius=P(r), outline=WHITE if w else None,
                        width=P(w) if w else 0, fill=fill)


def gear_pts(cx, cy, r_out, r_in, teeth, rot=0):
    pts = []
    n = teeth * 4
    for i in range(n):
        a = rot + 2 * math.pi * i / n
        r = r_out if (i % 4) in (1, 2) else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---- Self-Made Engineer icons

def ic_gear(sz=110, teeth=9, rot=0.0):
    c, d = canvas(sz)
    m = sz / 2
    pts = gear_pts(m, m, m - 3, m * 0.72, teeth, rot)
    d.polygon([(P(x), P(y)) for x, y in pts], fill=WHITE)
    circle(d, m, m, m * 0.30, w=0, fill=CLEAR)
    return c


def ic_turbine(sz=200):
    c, d = canvas(sz)
    hx, hy = sz / 2, sz * 0.33
    # tapered tower
    d.polygon([(P(hx - 4), P(hy + 10)), (P(hx + 4), P(hy + 10)),
               (P(hx + 11), P(sz - 6)), (P(hx - 11), P(sz - 6))], fill=WHITE)
    line(d, [(hx - 34, sz - 5), (hx + 34, sz - 5)])
    # blades
    L = sz * 0.31
    for k in range(3):
        a = math.radians(-90 + 120 * k + 15)
        ca, sa = math.cos(a), math.sin(a)
        nx, ny = -sa, ca
        tip = (hx + L * ca, hy + L * sa)
        root = (hx + 10 * ca, hy + 10 * sa)
        mid = (hx + L * 0.35 * ca, hy + L * 0.35 * sa)
        poly = [root, (mid[0] + nx * 9, mid[1] + ny * 9), tip, (mid[0] - nx * 2, mid[1] - ny * 2)]
        d.polygon([(P(x), P(y)) for x, y in poly], fill=WHITE)
    circle(d, hx, hy, 9, w=0, fill=WHITE)
    return c


def ic_wrench_hammer(sz=130):
    c, d = canvas(sz)
    # wrench drawn vertical, then rotated on its own canvas
    wc, wd = canvas(sz)
    m = sz / 2
    rrect(wd, (m - 6, 30, m + 6, sz - 22), 6, w=0, fill=WHITE)
    circle(wd, m, 24, 17, w=0, fill=WHITE)
    wd.rectangle((P(m - 6), P(0), P(m + 6), P(24)), fill=CLEAR)   # open jaw
    circle(wd, m, sz - 18, 13, w=0, fill=WHITE)
    circle(wd, m, sz - 18, 6, w=0, fill=CLEAR)
    wc = wc.rotate(-45, resample=Image.BICUBIC, expand=True)
    # hammer
    hc, hd = canvas(sz)
    rrect(hd, (m - 5, 24, m + 5, sz - 8), 5, w=0, fill=WHITE)
    rrect(hd, (m - 24, 8, m + 16, 30), 4, w=0, fill=WHITE)
    hd.polygon([(P(m + 16), P(10)), (P(m + 28), P(4)), (P(m + 30), P(17)), (P(m + 16), P(24))], fill=WHITE)
    hc = hc.rotate(45, resample=Image.BICUBIC, expand=True)
    c = Image.new("RGBA", wc.size, (0, 0, 0, 0))
    c.alpha_composite(wc)
    c.alpha_composite(hc, ((wc.size[0] - hc.size[0]) // 2, (wc.size[1] - hc.size[1]) // 2))
    return c


def ic_waterwheel(sz=130):
    c, d = canvas(sz)
    m = sz / 2
    R = m - 30
    cy0 = m - 8
    m_ = m
    circle(d, m, cy0, R)
    circle(d, m, cy0, 8, w=0, fill=WHITE)
    for k in range(3):
        x0 = m - 46 + k * 31
        d.arc((P(x0), P(sz - 16), P(x0 + 16), P(sz - 4)), 180, 360, fill=WHITE, width=P(3))
        d.arc((P(x0 + 15), P(sz - 16), P(x0 + 31), P(sz - 4)), 0, 180, fill=WHITE, width=P(3))
    for k in range(8):
        a = 2 * math.pi * k / 8
        line(d, [(m, cy0), (m + R * math.cos(a), cy0 + R * math.sin(a))], w=3)
        # paddle
        x1, y1 = m + R * math.cos(a), cy0 + R * math.sin(a)
        x2, y2 = m + (R + 11) * math.cos(a), cy0 + (R + 11) * math.sin(a)
        nx, ny = -math.sin(a) * 7, math.cos(a) * 7
        d.polygon([(P(x1 + nx), P(y1 + ny)), (P(x2 + nx), P(y2 + ny)),
                   (P(x2 - nx), P(y2 - ny)), (P(x1 - nx), P(y1 - ny))], fill=WHITE)
    return c


# ---- Everyday Decoded icons

def ic_phone(sz=110):
    c, d = canvas(sz)
    rrect(d, (14, 22, 54, 96), 8)
    line(d, [(28, 86), (40, 86)], w=4)
    for i, r in enumerate((16, 28, 40)):
        arc(d, 58, 34, r, -60, 10, w=4)
    return c


def ic_tower(sz=130):
    c, d = canvas(sz)
    m = sz / 2
    top, bot = 40, sz - 8
    line(d, [(m, top), (m - 26, bot)])
    line(d, [(m, top), (m + 26, bot)])
    for t in (0.35, 0.65):
        y = top + (bot - top) * t
        hw = 26 * t
        line(d, [(m - hw, y), (m + hw, y)], w=4)
    line(d, [(m - 26 * 0.35, top + (bot - top) * 0.35), (m + 26 * 0.65, top + (bot - top) * 0.65)], w=3)
    line(d, [(m + 26 * 0.35, top + (bot - top) * 0.35), (m - 26 * 0.65, top + (bot - top) * 0.65)], w=3)
    circle(d, m, top - 2, 7, w=0, fill=WHITE)
    for r in (20, 34):
        arc(d, m, top - 2, r, -150, -110, w=4)
        arc(d, m, top - 2, r, -70, -30, w=4)
    return c


def ic_wifi(sz=100):
    c, d = canvas(sz)
    m = sz / 2
    cy = sz - 22
    circle(d, m, cy, 7, w=0, fill=WHITE)
    for r in (24, 42, 60):
        arc(d, m, cy, r, -135, -45, w=6)
    return c


def ic_card(sz=130):
    c, d = canvas(sz)
    # card tilted
    cc, cd = canvas(sz)
    rrect(cd, (14, 52, 96, 106), 8)
    cd.rectangle((P(14), P(64), P(96), P(74)), fill=WHITE)
    rrect(cd, (24, 84, 42, 96), 2, w=0, fill=WHITE)
    cc = cc.rotate(14, resample=Image.BICUBIC, center=(P(55), P(80)))
    c.alpha_composite(cc)
    for r in (14, 26, 38):
        arc(d, 84, 42, r, -80, 10, w=4)
    return c


def ic_snowflake(sz=100):
    c, d = canvas(sz)
    m = sz / 2
    R = m - 8
    for k in range(6):
        a = math.radians(90 + 60 * k)
        ca, sa = math.cos(a), math.sin(a)
        line(d, [(m, m), (m + R * ca, m + R * sa)])
        bx, by = m + R * 0.6 * ca, m + R * 0.6 * sa
        for s in (-1, 1):
            b = a + s * math.radians(40)
            line(d, [(bx, by), (bx + 14 * math.cos(b), by + 14 * math.sin(b))], w=4)
    return c


def ic_tv(sz=120):
    c, d = canvas(sz)
    rrect(d, (10, 26, sz - 10, 92), 8)
    line(d, [(42, 104), (78, 104)])
    line(d, [(60, 92), (60, 104)], w=4)
    line(d, [(44, 8), (58, 24)], w=4)
    line(d, [(78, 8), (62, 24)], w=4)
    # play triangle
    d.polygon([(P(52), P(46)), (P(52), P(72)), (P(74), P(59))], fill=WHITE)
    return c


def ic_pin(sz=100):
    c, d = canvas(sz)
    m = sz / 2
    r = 24
    cy = 36
    t = math.radians(35)
    d.pieslice((P(m - r), P(cy - r), P(m + r), P(cy + r)), 0, 360, fill=WHITE)
    d.polygon([(P(m - r * math.cos(t)), P(cy + r * math.sin(t))),
               (P(m + r * math.cos(t)), P(cy + r * math.sin(t))), (P(m), P(cy + 50))], fill=WHITE)
    circle(d, m, cy, 9, w=0, fill=CLEAR)
    return c


# ------------------------------------------------------------------ assemble

def place(layer, icon, cx, cy, rot=0):
    if rot:
        icon = icon.rotate(rot, resample=Image.BICUBIC)
    w, h = icon.size
    layer.alpha_composite(icon, (int(P(cx) - w / 2), int(P(cy) - h / 2)))


def tint(layer, color, alpha):
    a = layer.split()[3].point(lambda v: int(v * alpha))
    out = Image.new("RGBA", layer.size, color + (0,))
    out.putalpha(a)
    return out


def blueprint_grid(img, color, alpha):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    step = 40
    for x in range(0, W + 1, step):
        major = (x // step) % 4 == 0
        gd.line((P(x), 0, P(x), H * S), fill=color + (int(255 * alpha * (1.8 if major else 1)),), width=S)
    for y in range(4, H + 1, step):
        major = ((y - 4) // step) % 4 == 0
        gd.line((0, P(y), W * S, P(y)), fill=color + (int(255 * alpha * (1.8 if major else 1)),), width=S)
    # fade grid: strongest at the sides, near-zero in the centre and the bottom-left
    ys, xs = np.mgrid[0:H * S, 0:W * S].astype(np.float32)
    xn = np.abs(xs / (W * S) - 0.5) * 2
    mask = np.clip((xn - 0.25) / 0.45, 0, 1)
    mask *= np.clip(1 - (ys / (H * S) - 0.55) / 0.4, 0.25, 1)
    a = np.array(g.split()[3], np.float32) * mask
    g.putalpha(Image.fromarray(a.astype(np.uint8)))
    img.alpha_composite(g)


def circuit(layer, paths, nodes):
    d = ImageDraw.Draw(layer)
    for pts in paths:
        # dotted
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            n = int(L // 12)
            for i in range(n + 1):
                x = x1 + (x2 - x1) * i / max(n, 1)
                y = y1 + (y2 - y1) * i / max(n, 1)
                d.ellipse((P(x - 2), P(y - 2), P(x + 2), P(y + 2)), fill=WHITE)
    for x, y in nodes:
        d.ellipse((P(x - 6), P(y - 6), P(x + 6), P(y + 6)), outline=WHITE, width=P(3))


def make(name, sub, bg_center, bg_edge, accent, accent_text, name_col, out, theme):
    img = gradient(bg_center, bg_edge).convert("RGBA")

    if theme == "sme":
        blueprint_grid(img, (120, 170, 220), 0.09)
        icons = Image.new("RGBA", img.size, (0, 0, 0, 0))
        place(icons, ic_turbine(200), 287, 205)
        place(icons, ic_gear(72, 8, 0.2), 268, 352)
        place(icons, ic_gear(48, 7, 0.25), 318, 382)
        place(icons, ic_wrench_hammer(140), 1352, 118)
        place(icons, ic_waterwheel(140), 1355, 280)
        img.alpha_composite(tint(icons, (200, 215, 232), 0.30))
    else:
        dots = Image.new("RGBA", img.size, (0, 0, 0, 0))
        circuit(dots, [
            [(287, 170), (287, 200)],
            [(287, 290), (287, 320)],
            [(1352, 135), (1352, 162)],
            [(1352, 246), (1352, 272)],
        ], [(287, 185), (287, 305), (1352, 148), (1352, 259)])
        img.alpha_composite(tint(dots, (150, 220, 215), 0.22))
        icons = Image.new("RGBA", img.size, (0, 0, 0, 0))
        place(icons, ic_tower(104), 287, 112)
        place(icons, ic_phone(92), 292, 240)
        place(icons, ic_card(130), 290, 360)
        place(icons, ic_wifi(80), 1352, 100)
        place(icons, ic_tv(96), 1352, 205)
        place(icons, ic_snowflake(72), 1352, 310)
        img.alpha_composite(tint(icons, (200, 230, 228), 0.30))

    d = ImageDraw.Draw(img)
    fn = font(BLACK, 40)
    ny = 72 * S
    center_text(d, ny, name, fn, name_col, spacing=4)
    tw = sum(d.textlength(c, font=fn) for c in name) + 4 * S * (len(name) - 1)
    lx1 = (W * S - tw) / 2 - 30 * S
    lx2 = (W * S + tw) / 2 + 30 * S
    ly = ny + 30 * S
    d.rounded_rectangle((lx1 - 90 * S, ly - 3 * S, lx1, ly + 3 * S), radius=3 * S, fill=accent)
    d.rounded_rectangle((lx2, ly - 3 * S, lx2 + 90 * S, ly + 3 * S), radius=3 * S, fill=accent)

    pw, ph = 900, 230
    px0 = (W - pw) // 2
    py0 = 180
    box = (px0 * S, py0 * S, (px0 + pw) * S, (py0 + ph) * S)
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle(
        (box[0], box[1] + 14 * S, box[2], box[3] + 14 * S), radius=ph * S // 2, fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(22 * S))
    img.paste(Image.new("RGBA", img.size, (0, 0, 0, 255)), (0, 0), sh)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=ph * S // 2, fill=accent)

    ff = font(BLACK, 170)
    text = "FOLLOW"
    bb = d.textbbox((0, 0), text, font=ff)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = (W * S - tw) / 2 - bb[0]
    ty = box[1] + (ph * S - th) / 2 - bb[1]
    d.text((tx, ty), text, font=ff, fill=accent_text)

    fs = font(BOLD, 44)
    center_text(d, (py0 + ph + 38) * S, sub, fs, name_col)

    ax, ay = (px0 + pw + 15) * S, (py0 + ph + 5) * S
    L = 150 * S
    ang = math.radians(40)
    ex, ey = ax + L * math.cos(ang), ay + L * math.sin(ang)
    thick = 26 * S
    hx, hy = ex - 52 * S * math.cos(ang), ey - 52 * S * math.sin(ang)
    d.line((ax, ay, hx, hy), fill=accent, width=thick)
    d.ellipse((ax - thick / 2, ay - thick / 2, ax + thick / 2, ay + thick / 2), fill=accent)
    hw = 56 * S
    nx, ny2 = -math.sin(ang), math.cos(ang)
    bx, by = ex - 78 * S * math.cos(ang), ey - 78 * S * math.sin(ang)
    d.polygon([(ex, ey), (bx + nx * hw, by + ny2 * hw), (bx - nx * hw, by - ny2 * hw)], fill=accent)

    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    img.save(out)
    print("saved", out)


OUT = sys.argv[1] if len(sys.argv) > 1 else BASE
make("SELF-MADE ENGINEER", "for the build series",
     (22, 44, 62), (8, 22, 34), (254, 114, 16), (255, 255, 255), (245, 240, 230),
     OUT + "page2/branding/cover-themed-1640x624.png", "sme")
make("EVERYDAY DECODED", "for a new one every day",
     (28, 38, 50), (14, 18, 24), (2, 173, 160), (255, 255, 255), (245, 245, 245),
     OUT + "page3/branding/cover-themed-1640x624.png", "ed")

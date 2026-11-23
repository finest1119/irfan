"""v2 look-dev test: re-make the plane-crash hook shot (0.0-9.6 s) in the bright daytime "v2" look,
with 2D caption / label overlays, and compare it side by side with v1.

Does not touch v1 builders, render_episode.py or output/plane-crash/ (read-only: captions.json).

  .venv/bin/python pipeline/v2_test.py all            # textures, track, render, overlays, encode, compare, flicker
  .venv/bin/python pipeline/v2_test.py stills 1,150,288 [--scale 0.5]
  .venv/bin/python pipeline/v2_test.py textures|track|render|overlay|encode|compare|flicker

Outputs in output/v2-test/: v2_shot.mp4, compare.mp4, compare.jpg, flicker.json (+ frames/, comp/, tex/).
"""
import json
import os
import random
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "output", "v2-test")
TEX = os.path.join(OUT, "tex")
CAPS = os.path.join(ROOT, "output", "plane-crash", "captions.json")
V1 = os.path.join(ROOT, "output", "plane crash.mp4")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
T0, T1 = 0.0, 9.6            # the hook beat up to "...departing a nearby airport." (next word at 10.07 s)
FPS = 30
NFR = int(round((T1 - T0) * FPS))
W, H = 1080, 1920

AVENIR = "/System/Library/Fonts/Avenir Next.ttc"   # index 0 Bold, 8 Heavy, 2 Demi Bold
DIN = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
CARD = ("PLANE CRASH · JACKSON, MS", "Hawkins Field · Sat 21 Nov 2026")
PLANE_LABEL, LABEL_CUE = "CIRRUS SR22", "cirrus"

# layout (fractions of frame height): card under the top UI margin, captions in the 22-30 % band
CARD_Y = 0.135
CAP_Y = 0.262


def sh(cmd, **kw):
    print("$", " ".join(cmd) if isinstance(cmd, list) else cmd)
    return subprocess.run(cmd, check=True, **kw)


# ================================================================ textures (PIL, 12 px / m)
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


# ================================================================ Blender
def blender(args, log):
    os.makedirs(os.path.dirname(log), exist_ok=True)
    cmd = [BLENDER, "-b", "--factory-startup", "-P", os.path.join(ROOT, "pipeline", "blender", "render_v2_test.py"),
           "--", OUT, TEX, CAPS, str(T1 - T0)] + args
    with open(log, "w") as fh:
        return subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)


def stills(frames, scale="0.5", samples="16", tag=""):
    p = blender(["--still", frames, "--scale", scale, "--samples", samples, "--tag", tag], os.path.join(OUT, "logs", "still.log"))
    p.wait()
    print(open(os.path.join(OUT, "logs", "still.log")).read()[-1500:])


def track():
    p = blender(["--track", os.path.join(OUT, "track.json")], os.path.join(OUT, "logs", "track.log"))
    p.wait()
    assert p.returncode == 0, open(os.path.join(OUT, "logs", "track.log")).read()[-2000:]


def render(parallel=3, samples="24"):
    t = time.time()
    n = parallel
    step = (NFR + n - 1) // n
    procs = []
    for i in range(n):
        a, b = 1 + i * step, min(NFR, (i + 1) * step)
        procs.append(blender(["--range", "%d-%d" % (a, b), "--samples", samples], os.path.join(OUT, "logs", "render_%d.log" % i)))
    for p in procs:
        p.wait()
    dt = time.time() - t
    got = len([f for f in os.listdir(os.path.join(OUT, "frames")) if f.endswith(".png")])
    print("render: %d/%d frames in %.1fs (wall, %d processes)" % (got, NFR, dt, n))
    json.dump({"wall_s": dt, "frames": got, "processes": n, "samples": int(samples)},
              open(os.path.join(OUT, "render_stats.json"), "w"))


# ================================================================ 2D overlays
def _font(size, idx=0):
    return ImageFont.truetype(AVENIR, size, index=idx)


def _rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, r, fill=fill)


def _shadowed(layer, blur=7, offset=(0, 4), alpha=0.55, glow=16, glow_alpha=0.25):
    """Soft drop shadow (+ faint wide halo for contrast on bright skies) under an RGBA layer."""
    a = layer.split()[3]
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for rad, al, off in ((glow, glow_alpha, (0, 2)), (blur, alpha, offset)):
        s = a.filter(ImageFilter.GaussianBlur(rad)).point(lambda v, al=al: int(v * al))
        sh_ = Image.new("RGBA", layer.size, (8, 14, 30, 0))
        sh_.putalpha(s)
        out.alpha_composite(sh_, off)
    out.alpha_composite(layer)
    return out


def caption_chunks():
    d = json.load(open(CAPS))
    words = [w for w in d["words"] if w.get("beat") == "hook" and w["start"] < T1]
    chunks = []
    for c in d["chunks"]:
        if c["start"] >= T1:
            continue
        ws = [w for w in words if c["start"] - 0.01 <= w["start"] < c["end"] - 0.005]
        chunks.append({"start": c["start"], "end": c["end"], "words": ws, "text": c["text"]})
    # hold each chunk until the next one starts if the gap is short (no empty flashes)
    for a, b in zip(chunks[:-1], chunks[1:]):
        if b["start"] - a["end"] < 0.7:
            a["end"] = b["start"]
    chunks[-1]["end"] = min(T1, chunks[-1]["end"] + 0.35)
    return chunks, words


class CaptionRenderer:
    """Top-centre captions: white Avenir Next Bold, soft shadow, no box; the word being spoken is drawn in
    Heavy on a subtle rounded red highlight. Word slots are laid out with the widest weight so nothing moves
    when the highlight jumps."""

    def __init__(self, size=78):
        self.f_n = _font(size, 0)
        self.f_b = _font(size, 8)
        self.size = size
        self.cache = {}

    def layout(self, chunk):
        words = [w["word"].upper().rstrip(",.") for w in chunk["words"]]
        sp = self.size * 0.30
        widths = [max(self.f_n.getlength(w), self.f_b.getlength(w)) for w in words]
        lines, cur, cw = [], [], 0.0
        maxw = W * 0.84
        for i, wd in enumerate(widths):
            add = wd + (sp if cur else 0)
            if cur and cw + add > maxw:
                lines.append(cur)
                cur, cw = [], 0.0
                add = wd
            cur.append(i)
            cw += add
        lines.append(cur)
        lh = self.size * 1.22
        y0 = CAP_Y * H - (len(lines) - 1) * lh / 2
        slots = {}
        for li, ln in enumerate(lines):
            tw = sum(widths[i] for i in ln) + sp * (len(ln) - 1)
            x = W / 2 - tw / 2
            for i in ln:
                slots[i] = (x, y0 + li * lh, widths[i])
                x += widths[i] + sp
        return words, slots

    def render(self, chunk, active, appear_t):
        key = (id(chunk), active, round(min(1.0, appear_t), 2))
        if key in self.cache:
            return self.cache[key]
        words, slots = self.layout(chunk)
        k = min(1.0, appear_t)
        e = 1 - (1 - k) ** 3
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        if active is not None and active in slots:
            x, y, wd = slots[active]
            pad_x, pad_y = self.size * 0.20, self.size * 0.10
            _rounded(d, (x - pad_x, y - self.size * 0.62 - pad_y, x + wd + pad_x, y + self.size * 0.50 + pad_y),
                     int(self.size * 0.22), (216, 38, 47, int(225 * e)))
        for i, wtxt in enumerate(words):
            x, y, wd = slots[i]
            f = self.f_b if i == active else self.f_n
            tx = x + (wd - f.getlength(wtxt)) / 2
            d.text((tx, y), wtxt, font=f, fill=(255, 255, 255, int(255 * e)), anchor="lm")
        out = _shadowed(layer)
        if k < 1.0:  # gentle rise-in (6 px) instead of a hard pop
            out = out.transform(out.size, Image.AFFINE, (1, 0, 0, 0, 1, -6 * (1 - e)), Image.BICUBIC)
        self.cache = {key: out}
        return out


def card_layer(t):
    """Title card + sub line: dark translucent rounded panel with a red accent bar. Fades/slides in at 0.25 s."""
    k = max(0.0, min(1.0, (t - 0.25) / 0.35))
    if k <= 0:
        return None
    e = 1 - (1 - k) ** 3
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f1, f2 = _font(50, 8), _font(34, 2)
    t1w = f1.getlength(CARD[0])
    pw, ph = t1w + 84, 92
    x0 = W / 2 - pw / 2
    y0 = CARD_Y * H - ph / 2 - 26 + 14 * (1 - e)
    _rounded(d, (x0, y0, x0 + pw, y0 + ph), 20, (12, 20, 44, int(200 * e)))
    _rounded(d, (x0, y0, x0 + 12, y0 + ph), 6, (216, 38, 47, int(255 * e)))
    d.text((W / 2 + 6, y0 + ph / 2), CARD[0], font=f1, fill=(255, 255, 255, int(255 * e)), anchor="mm")
    k2 = max(0.0, min(1.0, (t - 0.45) / 0.35))
    if k2 > 0:
        e2 = 1 - (1 - k2) ** 3
        d.text((W / 2, y0 + ph + 40), CARD[1], font=f2, fill=(255, 255, 255, int(240 * e2)), anchor="mm")
    return _shadowed(layer, blur=8, alpha=0.45, glow=14, glow_alpha=0.18)


def label_layer(tr, t, t_on):
    """'CIRRUS SR22' pill that follows the aircraft (screen positions exported from Blender) with a short
    leader line. Kept below the caption band."""
    k = max(0.0, min(1.0, (t - t_on) / 0.3))
    if k <= 0:
        return None
    e = 1 - (1 - k) ** 3
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = _font(40, 8)
    tw = f.getlength(PLANE_LABEL)
    pw, ph = tw + 64, 66
    ax, ay = tr["cx"], tr["y0"] - 18              # anchor: just above the aircraft
    cx = min(max(ax + 70, pw / 2 + 40), W - pw / 2 - 40)
    cy = max(ay - 120, (CAP_Y + 0.06) * H + ph / 2)  # never inside the caption band
    a = int(255 * e)
    d.line([(ax, ay), (cx - pw / 2 + 30, cy + ph / 2)], fill=(255, 255, 255, int(220 * e)), width=4)
    d.ellipse((ax - 7, ay - 7, ax + 7, ay + 7), fill=(255, 255, 255, a))
    _rounded(d, (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2), 33, (255, 255, 255, int(235 * e)))
    d.ellipse((cx - pw / 2 + 18, cy - 8, cx - pw / 2 + 34, cy + 8), fill=(216, 38, 47, a))
    d.text((cx + 12, cy + 1), PLANE_LABEL, font=f, fill=(14, 22, 44, a), anchor="mm")
    return _shadowed(layer, blur=8, alpha=0.4, glow=12, glow_alpha=0.15)


def overlay():
    chunks, words = caption_chunks()
    tr = json.load(open(os.path.join(OUT, "track.json")))
    t_label = next(w["start"] for w in words if w["norm"].startswith(LABEL_CUE))
    cap = CaptionRenderer()
    src, dst = os.path.join(OUT, "frames"), os.path.join(OUT, "comp")
    os.makedirs(dst, exist_ok=True)
    events = []
    for f in range(1, NFR + 1):
        t = T0 + (f - 1) / FPS
        img = Image.open(os.path.join(src, "%04d.png" % f)).convert("RGBA")
        ch = next((c for c in chunks if c["start"] <= t < c["end"]), None)
        if ch is not None:
            act = None
            for i, w in enumerate(ch["words"]):
                if w["start"] <= t:
                    act = i
            img.alpha_composite(cap.render(ch, act, (t - ch["start"]) / 0.2))
        cl = card_layer(t)
        if cl is not None:
            img.alpha_composite(cl)
        ll = label_layer(tr[f - 1], t, t_label)
        if ll is not None:
            img.alpha_composite(ll)
        img.convert("RGB").save(os.path.join(dst, "%04d.png" % f), compress_level=1)
    # expected caption changes (chunk starts + highlight word changes), for the flicker QC
    for c in chunks:
        f0 = round((c["start"] - T0) * FPS) + 1
        events.extend(range(f0, f0 + 8))          # chunk swap + 0.2 s rise-in
        for w in c["words"]:
            events.append(round((w["start"] - T0) * FPS) + 1)
    json.dump({"caption_events": sorted(set(events)), "label_on": round((t_label - T0) * FPS) + 1},
              open(os.path.join(OUT, "v2_events.json"), "w"))
    print("overlays ->", dst)


# ================================================================ encode / compare
def encode():
    aud = os.path.join(OUT, "tmp", "hook_audio.wav")
    os.makedirs(os.path.dirname(aud), exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-ss", str(T0), "-t", str(T1 - T0), "-i", V1, "-vn", "-ac", "2", "-ar", "48000",
        "-af", "afade=t=out:st=%.2f:d=0.25" % (T1 - T0 - 0.25), aud])
    sh(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(OUT, "comp", "%04d.png"), "-i", aud,
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", os.path.join(OUT, "v2_shot.mp4")])
    sh(["ffmpeg", "-v", "error", "-y", "-ss", str(T0), "-t", str(T1 - T0), "-i", V1, "-c:v", "libx264", "-crf", "17",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", os.path.join(OUT, "v1_shot.mp4")])


def _tag(text, path):
    f = _font(46, 8)
    w = int(f.getlength(text)) + 50
    im = Image.new("RGBA", (w, 76), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 75), 18, fill=(0, 0, 0, 170))
    d.text((w / 2, 38), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    im.save(path)


def compare():
    tmp = os.path.join(OUT, "tmp")
    _tag("v1 (current)", os.path.join(tmp, "tag_v1.png"))
    _tag("v2 (look test)", os.path.join(tmp, "tag_v2.png"))
    fc = ("[0:v]scale=1080:1920,setsar=1[a];[1:v]scale=1080:1920,setsar=1[b];[a][b]hstack=inputs=2[s];"
          "[s][2:v]overlay=30:H-110[s2];[s2][3:v]overlay=1110:H-110[v]")
    sh(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(OUT, "v1_shot.mp4"), "-i", os.path.join(OUT, "v2_shot.mp4"),
        "-i", os.path.join(tmp, "tag_v1.png"), "-i", os.path.join(tmp, "tag_v2.png"), "-filter_complex", fc,
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", os.path.join(OUT, "compare.mp4")])
    # compare.jpg: 3 matched frames, v1 (top) vs v2 (bottom)
    times = (1.5, 5.4, 9.0)
    tiles = []
    for name in ("v1_shot.mp4", "v2_shot.mp4"):
        row = []
        for t in times:
            p = os.path.join(tmp, "cmp_%s_%.1f.png" % (name[:2], t))
            sh(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", os.path.join(OUT, name), "-frames:v", "1", p])
            row.append(Image.open(p).convert("RGB").resize((540, 960), Image.LANCZOS))
        tiles.append(row)
    sheet = Image.new("RGB", (540 * 3 + 40, 960 * 2 + 150), (18, 20, 26))
    d = ImageDraw.Draw(sheet)
    f = _font(34, 8)
    for c, t in enumerate(times):
        d.text((10 + c * 550 + 270, 30), "t = %.1f s" % t, font=f, fill=(230, 230, 230), anchor="mm")
    for r, (row, lab) in enumerate(zip(tiles, ("v1", "v2"))):
        for c, im in enumerate(row):
            sheet.paste(im, (10 + c * 550, 60 + r * 1000))
        d.text((20, 60 + r * 1000 + 950), lab, font=_font(40, 8), fill=(255, 255, 255), anchor="ls")
    sheet.save(os.path.join(OUT, "compare.jpg"), quality=90)
    print("compare ->", os.path.join(OUT, "compare.mp4"), os.path.join(OUT, "compare.jpg"))


def flicker():
    py = sys.executable
    q = os.path.join(ROOT, "pipeline", "qc_flicker.py")
    d = json.load(open(CAPS))
    v1_events = [str(x) for x in sorted({round(c["start"] * FPS) + 1 for c in d["chunks"] if c["start"] < T1})]
    # v1 3D card + sub-card pop-in (0.25 s, 9-frame overshoot) and the CIRRUS label pop on "cirrus" (3.45 s)
    v1_pops = ["9-22", "%d-%d" % (round(3.45 * FPS) - 2, round(3.45 * FPS) + 14)]
    ev = json.load(open(os.path.join(OUT, "v2_events.json")))
    res = {}
    runs = {
        # v1: caption band (y 1216-1391) and the top card / label band (9-28 % of the height)
        "v1_mp4": [V1, "--start", str(T0), "--dur", str(T1 - T0), "--region", "caption:1200:1400",
                   "--region", "cards:170:540", "--region", "plane_label:440:560:300:800", "--events", ",".join(v1_events + v1_pops)],
        # raw v1 PNG frames of the hook shot (no captions burned in: isolates the 3D cards; no h264)
        "v1_png": [os.path.join(ROOT, "output", "plane-crash", "frames", "00_hook"), "--frames", str(NFR),
                   "--region", "cards:170:540", "--region", "plane_label:440:560:300:800", "--events", ",".join(v1_pops)],
        "v2_mp4": [os.path.join(OUT, "v2_shot.mp4"), "--region", "caption:400:620", "--region", "cards:180:400",
                   "--region", "plane_label:600:820",
                   "--events", ",".join([str(x) for x in ev["caption_events"]] + ["8-26", "%d-%d" % (ev["label_on"], ev["label_on"] + 10)])],
        "v2_png": [os.path.join(OUT, "comp"), "--frames", str(NFR), "--region", "caption:400:620", "--region", "cards:180:400",
                   "--region", "plane_label:600:820",
                   "--events", ",".join([str(x) for x in ev["caption_events"]] + ["8-26", "%d-%d" % (ev["label_on"], ev["label_on"] + 10)])],
    }
    for name, args in runs.items():
        outp = os.path.join(OUT, "flicker_%s.json" % name)
        sh([py, q] + args + ["--json", outp])
        res[name] = json.load(open(outp))
    json.dump(res, open(os.path.join(OUT, "flicker.json"), "w"), indent=1)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "textures":
        make_textures()
    elif step == "stills":
        sc = sys.argv[sys.argv.index("--scale") + 1] if "--scale" in sys.argv else "0.5"
        tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
        stills(sys.argv[2], sc, tag=tag)
    elif step == "track":
        track()
    elif step == "render":
        render(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    elif step == "overlay":
        overlay()
    elif step == "encode":
        encode()
    elif step == "compare":
        compare()
    elif step == "flicker":
        flicker()
    elif step == "all":
        make_textures()
        track()
        render()
        overlay()
        encode()
        compare()
        flicker()


if __name__ == "__main__":
    main()

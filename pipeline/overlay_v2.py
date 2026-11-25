"""v2 2D overlays + assembly: every piece of on-screen text in a v2 episode is drawn here (PIL), never in Blender.

  .venv/bin/python pipeline/overlay_v2.py EPISODE_JSON [--beats 0,3] [--preview T1,T2,...]

What it draws on top of the rendered frames (WORKDIR/frames_v2/NN_<beat>/####.jpg):
  * captions: top centre (CAP_Y), white Avenir Next Bold with a soft shadow, the word being spoken in Heavy on a
    rounded red highlight; word slots are fixed so text never reflows (from captions.json, script text + whisper times)
  * the per-beat `shot.overlays` list (types below), timed on spoken words ("cue") or seconds ("at")
Each beat becomes WORKDIR/segments_v2/NN_<beat>.mp4 (beats in parallel); make_episode.py concatenates them and
adds the voice. Expected animation frames are written to WORKDIR/overlay_events_v2.json for qc_flicker.py.

Overlay item types (all optional keys in [brackets]; `cue` = word prefix spoken in this beat, `at` = seconds into
the beat, `delay` = extra seconds after the cue, `until` = cue/seconds when the item fades out):
  card    {text, [sub], [sub_cue], [cue|at], [until]}            title card at CARD_Y (dark panel, red accent bar)
  chips   {items[], [cues[]|at], [until], [style: "dot"|"check"], [y]}  stacked pills in the lower band (CHIP_Y)
  label   {text, anchor, [cue|at], [until], [dx], [dy], [color]}  pill + leader line that follows a 3D anchor
  bar     {top, bottom, [color: teal|red], [label], [cue|at], [side: left|right]}  measuring bar between 2 anchors
  big     {text, [sub], [cue|at], [until], [y]}                    big number / statement panel
  meter   {[label], segments, cues[], [y]}                          segmented meter that fills on cues
  profile {mode: intro|zones, [cue|at], [takeoff_cue], [landing_cue], [zone_cue], [red_cue]}  flight-profile graph
  history {cards: [[title, sub], ...], cues[]}                      timeline cards
  board   {rows: [[time, place, status], ...], [flips: [[row, status, cue], ...]], [title], [cue|at], [y]}
          departures board (mid band); statuses flip split-flap style on their cues
  blur    {[radius], [dim]}                                         blur + darken the 3D plate under the overlays
Layout bands (fractions of the height, asserted): card 0.12-0.20, captions 0.22-0.31, labels/bars/graphs/big
0.32-0.64, chips/meter 0.64-0.80. Everything stays inside the 12 %-80 % safe area.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import platform_cfg as PC  # cross-platform paths; macOS defaults = the old hard-coded values

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
W, H = 1080, 1920
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"   # index 0 Bold, 8 Heavy, 2 Demi Bold (Mac default; see platform_cfg)
CARD_Y = 0.150
CAP_Y = 0.262
CHIP_Y = 0.655
CHIP_STEP = 0.048
SAFE = (0.12, 0.80)
CAP_BAND = (0.215, 0.312)
RED = (216, 38, 47)
TEAL = (22, 178, 160)
AMBER = (240, 166, 40)
NAVY = (12, 20, 44)
WHITE = (255, 255, 255)
COLORS = {"red": RED, "teal": TEAL, "amber": AMBER, "navy": NAVY, "white": WHITE}

_FONTS = {}

# Per-episode look (Page 3+): episode.json may carry an optional "style" block
#   {"font_set": "avenir"|"montserrat", "highlight_color": "#RRGGBB", "twist_card": {"bg": "#RRGGBB", "fg": "#RRGGBB"}}
# Every key is opt-in; with no "style" block (all WJH episodes) the output is byte-identical to before.
STYLE = {"font_set": None, "highlight": RED, "twist_bg": None, "twist_fg": None}


def _hex(c):
    c = c.lstrip("#")
    if len(c) != 6:
        raise ValueError("style colour must be #RRGGBB, got %r" % c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def apply_style(ep):
    """Set STYLE from ep["style"] (missing keys -> WJH defaults / platform_cfg). Call once per loaded episode."""
    st = ep.get("style") or {}
    fs = st.get("font_set")
    if fs is not None and fs.lower() not in PC.FONT_SETS:
        raise SystemExit("style.font_set must be one of %s, got %r" % (sorted(PC.FONT_SETS), fs))
    tw = st.get("twist_card") or {}
    new = {"font_set": fs.lower() if fs else None,
           "highlight": _hex(st["highlight_color"]) if st.get("highlight_color") else RED,
           "twist_bg": _hex(tw["bg"]) if tw.get("bg") else None,
           "twist_fg": _hex(tw["fg"]) if tw.get("fg") else None}
    if new["font_set"] != STYLE["font_set"]:
        _FONTS.clear()
    STYLE.update(new)
    return ep


def load_ep(ep_path):
    return apply_style(json.load(open(ep_path)))


def font(size, idx=0):
    k = (size, idx)
    if k not in _FONTS:
        if STYLE["font_set"]:      # episode style wins over platform_cfg
            role = PC._AVENIR_IDX.get(idx, "BOLD")
            path, ix = PC._split_spec(PC.FONT_SETS[STYLE["font_set"]][role])
            if idx not in PC._AVENIR_IDX and path.lower().endswith(".ttc"):
                ix = idx
        else:
            path, ix = PC.overlay_font(idx)   # Mac default: (AVENIR, idx); Windows: Montserrat
        _FONTS[k] = ImageFont.truetype(path, size, index=ix)
    return _FONTS[k]


def ease(k):
    k = max(0.0, min(1.0, k))
    return 1 - (1 - k) ** 3


def shadowed(layer, blur=7, offset=(0, 4), alpha=0.55, glow=16, glow_alpha=0.25):
    """Soft drop shadow (+ faint wide halo for contrast on bright skies) under an RGBA layer (same size)."""
    a = layer.split()[3]
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for rad, al, off in ((glow, glow_alpha, (0, 2)), (blur, alpha, offset)):
        s = a.filter(ImageFilter.GaussianBlur(rad)).point(lambda v, al=al: int(v * al))
        sh_ = Image.new("RGBA", layer.size, (8, 14, 30, 0))
        sh_.putalpha(s)
        out.alpha_composite(sh_, off)
    out.alpha_composite(layer)
    return out


class Sprite:
    """A small RGBA image placed at (x, y) on the frame (shadow computed on the crop only = fast)."""

    def __init__(self, img, x, y):
        self.img, self.x, self.y = img, int(round(x)), int(round(y))


def sprite_from(draw_fn, box, shadow=True, **shk):
    """draw_fn(ImageDraw, ox, oy) draws in frame coordinates offset by (ox, oy); box = (x0, y0, x1, y1)."""
    pad = 40
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    im = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), -x0, -y0)
    if shadow:
        im = shadowed(im, **shk)
    return Sprite(im, x0, y0)


def fade(img, a):
    if a >= 0.999:
        return img
    r, g, b, al = img.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


# ================================================================ timing context
class BeatCtx:
    def __init__(self, ep, idx, timing, words, fps, anchors):
        self.ep, self.idx, self.fps = ep, idx, fps
        self.beat = ep["beats"][idx]
        self.start = timing["start"]
        self.duration = timing["duration"]
        self.nframes = int(round(self.duration * fps))
        self.words = [w for w in words if w.get("beat") == self.beat["id"]]
        self.anchors = anchors

    def cue(self, c, default=None, nth=0):
        """Seconds into the beat at which the cue word is spoken (number = seconds as is)."""
        if c is None:
            return default
        if isinstance(c, (int, float)):
            return float(c)
        w = c.lower()
        hits = [x for x in self.words if x["norm"].startswith(w)]
        if len(hits) > nth:
            return hits[nth]["start"] - self.start
        print("[overlay] WARNING cue %r not found in beat %s, using %s" % (c, self.beat["id"], default))
        return default if default is not None else 0.3

    def t_on(self, it, default=0.25):
        if "cue" in it:
            return self.cue(it["cue"], default)
        return float(it.get("at", default))

    def t_off(self, it):
        if "until" in it:
            return self.cue(it["until"], self.duration + 1)
        return self.duration + 10.0

    def anchor(self, name, f):
        a = self.anchors.get(name)
        if not a:
            return None
        p = a[min(len(a) - 1, max(0, f - 1))]
        return p if p and p[2] else None


def load_anchors(workdir, name):
    """Merge WORKDIR/tracks_v2/<name>_A-B.json pieces into {anchor: [[x, y, vis] per frame (1-based index-1)]}."""
    tdir = os.path.join(workdir, "tracks_v2")
    out = {}
    if not os.path.isdir(tdir):
        return out
    for fn in sorted(os.listdir(tdir)):
        if not (fn.startswith(name + "_") and fn.endswith(".json")):
            continue
        d = json.load(open(os.path.join(tdir, fn)))
        for k, pts in d["anchors"].items():
            arr = out.setdefault(k, {})
            for i, p in enumerate(pts):
                arr[d["f0"] + i] = p
    res = {}
    for k, m in out.items():
        n = max(m)
        pts = [m.get(f) for f in range(1, n + 1)]
        # light temporal smoothing (+-3 frames) so labels glide instead of stepping by whole pixels
        sm = []
        for i, p in enumerate(pts):
            if not p:
                sm.append(p)
                continue
            win = [q for q in pts[max(0, i - 3):i + 4] if q and q[2]]
            if not win or not p[2]:
                sm.append(p)
                continue
            sm.append([sum(q[0] for q in win) / len(win), sum(q[1] for q in win) / len(win), p[2]])
        res[k] = sm
    return res


# ================================================================ captions
class Captions:
    """Top-centre captions: white Avenir Next Bold, soft shadow, no box; the spoken word in Heavy on a rounded red
    highlight. Word slots are laid out with the widest weight so nothing moves when the highlight jumps."""

    def __init__(self, caps, total, size=78):
        self.size = size
        self.f_n, self.f_b = font(size, 0), font(size, 8)
        words = caps["words"]
        chunks = []
        for c in caps["chunks"]:
            ws = [w for w in words if c["start"] - 0.01 <= w["start"] < c["end"] - 0.005]
            if ws:
                chunks.append({"start": c["start"], "end": c["end"], "words": ws})
        for a, b in zip(chunks[:-1], chunks[1:]):
            if b["start"] - a["end"] < 0.7:
                a["end"] = b["start"]
                b["follows"] = True      # swap directly: no fade from 0 (would blank the band for a frame)
        chunks[-1]["end"] = min(total, chunks[-1]["end"] + 0.35)
        self.chunks = chunks
        self.cache = {}

    def layout(self, chunk):
        words = [w["word"].upper().rstrip(",.:;") for w in chunk["words"]]
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
        top = y0 - self.size * 0.7
        bot = y0 + (len(lines) - 1) * lh + self.size * 0.6
        assert CAP_BAND[0] * H - 60 <= top and bot <= CAP_BAND[1] * H + 60, "caption outside its band"
        return words, slots, (top, bot)

    def at(self, T):
        """Sprite for absolute time T (seconds in the whole video) or None."""
        ch = next((c for c in self.chunks if c["start"] <= T < c["end"]), None)
        if ch is None:
            return None
        act = None
        for i, w in enumerate(ch["words"]):
            if w["start"] <= T:
                act = i
        k = round(min(1.0, (T - ch["start"]) / 0.2), 2)
        key = (id(ch), act, k)
        if key in self.cache:
            return self.cache[key]
        words, slots, (top, bot) = self.layout(ch)
        e = ease(k)
        if ch.get("follows"):
            e = 1.0 if k >= 1.0 else 0.75 + 0.25 * e
        size = self.size

        def draw(d, ox, oy):
            if act is not None and act in slots:
                x, y, wd = slots[act]
                px, py = size * 0.20, size * 0.10
                d.rounded_rectangle((x - px + ox, y - size * 0.62 - py + oy, x + wd + px + ox, y + size * 0.50 + py + oy),
                                    int(size * 0.22), fill=STYLE["highlight"] + (int(225 * e),))
            for i, wt in enumerate(words):
                x, y, wd = slots[i]
                f = self.f_b if i == act else self.f_n
                d.text((x + (wd - f.getlength(wt)) / 2 + ox, y + oy), wt, font=f, fill=(255, 255, 255, int(255 * e)),
                       anchor="lm")
        sp = sprite_from(draw, (0, top - 10, W, bot + 10))
        if k < 1.0:
            sp.y += int(round(6 * (1 - e)))
        if len(self.cache) > 64:
            self.cache.clear()
        self.cache[key] = sp
        return sp

    def events(self, fps):
        ev = set()
        for c in self.chunks:
            f0 = round(c["start"] * fps) + 1
            ev.update(range(f0, f0 + 8))
            for w in c["words"]:
                ev.add(round(w["start"] * fps) + 1)
            ev.add(round(c["end"] * fps) + 1)
        return ev


# ================================================================ overlay items
class Item:
    band = "mid"
    anim = 0.35

    def __init__(self, bc, spec):
        self.bc, self.s = bc, spec
        self.t0 = bc.t_on(spec) + float(spec.get("delay", 0.0))
        self.t1 = bc.t_off(spec)
        self._cache = {}

    def alpha(self, t):
        a = ease((t - self.t0) / self.anim)
        if t >= self.t1:
            a *= 1 - ease((t - self.t1) / 0.25)
        return a

    def cached(self, key, fn):
        if key not in self._cache:
            if len(self._cache) > 48:
                self._cache.clear()
            self._cache[key] = fn()
        return self._cache[key]

    def events(self):
        """Frames (1-based, within the beat) where this item animates on purpose."""
        fps = self.bc.fps
        ev = set(range(int(self.t0 * fps), int((self.t0 + self.anim) * fps) + 3))
        if self.t1 < self.bc.duration:
            ev.update(range(int(self.t1 * fps), int((self.t1 + 0.25) * fps) + 3))
        return ev

    def sprites(self, t, f):
        return []


def _panel_text(d, ox, oy, cx, cy, lines, f, pad_x=42, pad_y=20, fill=NAVY, a=1.0, accent=RED, lh=None, fg=WHITE):
    lh = lh or f.size * 1.18
    tw = max(f.getlength(s) for s in lines)
    pw, ph = tw + 2 * pad_x, lh * len(lines) + 2 * pad_y - (lh - f.size * 1.05)
    x0, y0 = cx - pw / 2, cy - ph / 2
    d.rounded_rectangle((x0 + ox, y0 + oy, x0 + pw + ox, y0 + ph + oy), 20, fill=fill + (int(205 * a),))
    if accent is not None:
        d.rounded_rectangle((x0 + ox, y0 + oy, x0 + 12 + ox, y0 + ph + oy), 6, fill=accent + (int(255 * a),))
    for i, s in enumerate(lines):
        yy = y0 + pad_y + f.size * 0.55 + i * lh
        d.text((cx + 6 + ox, yy + oy), s, font=f, fill=fg + (int(255 * a),), anchor="mm")
    return (x0, y0, x0 + pw, y0 + ph)


class Card(Item):
    band = "card"

    def sprites(self, t, f):
        a = self.alpha(t)
        if a <= 0.004:
            return []
        lines = self.s["text"].split("\n")
        sub = self.s.get("sub")
        fh = font(50 if max(len(x) for x in lines) <= 26 else 44, 8)
        if sub and len(lines) > 1:
            # a two-line card + sub line cannot fit between the 12 % line and the captions (it used to poke above
            # 12 % and the sub touched the caption): join the lines when the one-line title fits the width
            one = " ".join(x.strip() for x in lines)
            for size in (50, 46, 42):
                if font(size, 8).getlength(one) + 2 * 42 + 12 <= W * 0.92:
                    lines, fh = [one], font(size, 8)
                    break
        rise = round(14 * (1 - ease((t - self.t0) / self.anim)))
        out = []

        def mk():
            lh = fh.size * 1.18
            ph = lh * len(lines) + 40
            ph_real = lh * len(lines) + 40 - (lh - fh.size * 1.05)
            # panel top pinned just under the 12 % line (was centred on CARD_Y and crossed it)
            cy = (SAFE[0] + 0.006) * H + ph_real / 2
            box = (0, cy - ph / 2 - 10, W, cy + ph / 2 + 10)
            tw = {}
            if self.s.get("style") == "twist" and STYLE["twist_bg"]:   # opt-in twist card colours
                tw = {"fill": STYLE["twist_bg"], "fg": STYLE["twist_fg"] or WHITE, "accent": None}
            sp = sprite_from(lambda d, ox, oy: _panel_text(d, ox, oy, W / 2, cy, lines, fh, **tw), box,
                             blur=8, alpha=0.45, glow=14, glow_alpha=0.18)
            return sp, cy + ph_real / 2
        sp, bottom = self.cached("panel", mk)
        out.append(Sprite(fade(sp.img, a), sp.x, sp.y + rise))
        if sub:
            ts = self.bc.cue(self.s.get("sub_cue"), self.t0 + 0.2) if "sub_cue" in self.s else self.t0 + 0.2
            a2 = ease((t - ts) / 0.35)
            if t >= self.t1:
                a2 *= 1 - ease((t - self.t1) / 0.25)
            if a2 > 0.004:
                f2 = font(36, 2)

                def mk2():
                    y = bottom + 30
                    # two-line captions start at about CAP_BAND[0]: keep the sub line clear of them
                    assert y + 22 <= CAP_BAND[0] * H - 8, "card sub line runs into the captions"
                    return sprite_from(lambda d, ox, oy: d.text((W / 2 + ox, y + oy), sub, font=f2, fill=WHITE + (245,),
                                                                anchor="mm"), (0, y - 30, W, y + 30))
                s2 = self.cached("sub", mk2)
                out.append(Sprite(fade(s2.img, a2), s2.x, s2.y + rise))
        return out


class Chips(Item):
    band = "low"

    def __init__(self, bc, spec):
        super().__init__(bc, spec)
        items = spec["items"]
        cues = spec.get("cues")
        if cues:
            self.ts = [bc.cue(c, self.t0 + 0.6 * i) for i, c in enumerate(cues)]
        else:
            self.ts = [self.t0 + 0.5 * i for i in range(len(items))]
        self.t0 = min(self.ts)
        self.y = spec.get("y", CHIP_Y)
        assert self.y * H >= 0.30 * H and (self.y + CHIP_STEP * (len(items) - 1) + 0.03) <= SAFE[1], "chips outside safe area"

    def events(self):
        fps = self.bc.fps
        ev = set()
        for t in self.ts:
            ev.update(range(int(t * fps), int((t + self.anim) * fps) + 3))
        if self.t1 < self.bc.duration:
            ev.update(range(int(self.t1 * fps), int((self.t1 + 0.25) * fps) + 3))
        return ev

    def chip(self, i):
        txt = self.s["items"][i]
        style = self.s.get("style", "dot")
        f = font(40, 8)

        def mk():
            tw = f.getlength(txt)
            pw, ph = tw + 92, 66
            cy = self.y * H + i * CHIP_STEP * H
            x0 = W / 2 - pw / 2

            def draw(d, ox, oy):
                d.rounded_rectangle((x0 + ox, cy - ph / 2 + oy, x0 + pw + ox, cy + ph / 2 + oy), 33, fill=NAVY + (215,))
                cx = x0 + 34
                if style == "check":
                    d.ellipse((cx - 15 + ox, cy - 15 + oy, cx + 15 + ox, cy + 15 + oy), fill=TEAL + (255,))
                    d.line([(cx - 7 + ox, cy + oy), (cx - 2 + ox, cy + 6 + oy), (cx + 8 + ox, cy - 6 + oy)],
                           fill=WHITE + (255,), width=4)
                else:
                    d.ellipse((cx - 9 + ox, cy - 9 + oy, cx + 9 + ox, cy + 9 + oy),
                              fill=COLORS.get(self.s.get("color", "red"), RED) + (255,))
                d.text((x0 + 58 + (pw - 58 - 34) / 2 + ox, cy + 1 + oy), txt, font=f, fill=WHITE + (255,), anchor="mm")
            return sprite_from(draw, (x0, cy - ph / 2, x0 + pw, cy + ph / 2), blur=8, alpha=0.4, glow=12, glow_alpha=0.15)
        return self.cached(i, mk)

    def sprites(self, t, f):
        out = []
        for i, ti in enumerate(self.ts):
            a = ease((t - ti) / self.anim)
            if t >= self.t1:
                a *= 1 - ease((t - self.t1) / 0.25)
            if a <= 0.004:
                continue
            sp = self.chip(i)
            out.append(Sprite(fade(sp.img, a), sp.x, sp.y + round(10 * (1 - ease((t - ti) / self.anim)))))
        return out


class Label(Item):
    band = "mid"
    anim = 0.3

    def sprites(self, t, f):
        a = self.alpha(t)
        if a <= 0.004:
            return []
        p = self.bc.anchor(self.s["anchor"], f)
        if p is None:
            return []
        # fade out smoothly as the anchor nears / leaves the frame edge (no pop)
        a *= max(0.0, min(1.0, (p[0] - 10) / 110.0, (W - 10 - p[0]) / 110.0))
        if a <= 0.004:
            return []
        ax, ay = p[0], p[1] + self.s.get("ay", 0)
        txt = self.s["text"]
        fnt = font(40, 8)
        lines = txt.split("\n")
        tw = max(fnt.getlength(s) for s in lines)
        pw, ph = tw + 64, 66 + 46 * (len(lines) - 1)
        cx = min(max(ax + self.s.get("dx", 70), pw / 2 + 40), W - pw / 2 - 40)
        lo = (CAP_BAND[1] + 0.02) * H + ph / 2
        hi = (CHIP_Y - 0.03) * H - ph / 2 if self.s.get("above_chips", True) else SAFE[1] * H - ph / 2
        cy = min(max(ay + self.s.get("dy", -120), lo), hi)
        col = COLORS.get(self.s.get("color", "red"), RED)
        A = int(255 * a)

        def draw(d, ox, oy):
            d.line([(ax + ox, ay + oy), (cx - pw / 2 + 30 + ox, cy + (ph / 2 if ay > cy else -ph / 2) + oy)],
                   fill=(255, 255, 255, int(220 * a)), width=4)
            d.ellipse((ax - 7 + ox, ay - 7 + oy, ax + 7 + ox, ay + 7 + oy), fill=(255, 255, 255, A))
            d.rounded_rectangle((cx - pw / 2 + ox, cy - ph / 2 + oy, cx + pw / 2 + ox, cy + ph / 2 + oy), 33,
                                fill=(255, 255, 255, int(238 * a)))
            d.ellipse((cx - pw / 2 + 18 + ox, cy - 8 + oy, cx - pw / 2 + 34 + ox, cy + 8 + oy), fill=col + (A,))
            for i, s in enumerate(lines):
                d.text((cx + 12 + ox, cy + 1 - (len(lines) - 1) * 23 + i * 46 + oy), s, font=fnt, fill=NAVY + (A,), anchor="mm")
        x0, x1 = min(ax, cx - pw / 2) - 10, max(ax, cx + pw / 2) + 10
        y0, y1 = min(ay, cy - ph / 2) - 10, max(ay, cy + ph / 2) + 10
        return [sprite_from(draw, (x0, y0, x1, y1), blur=8, alpha=0.4, glow=12, glow_alpha=0.15)]


class Bar(Item):
    band = "mid"
    anim = 0.7

    def sprites(self, t, f):
        a = self.alpha(t)
        if a <= 0.004:
            return []
        top, bot = self.bc.anchor(self.s["top"], f), self.bc.anchor(self.s["bottom"], f)
        if top is None or bot is None:
            return []
        g = ease((t - self.t0) / self.anim)
        x = top[0] + self.s.get("bx", 0)
        yb, yt_full = bot[1], top[1] + 26
        yt = yb + (yt_full - yb) * g
        col = COLORS.get(self.s.get("color", "teal"), TEAL)
        A = int(255 * a)
        label = self.s.get("label")
        fnt = font(38, 8)
        lines = label.split("\n") if label else []
        side = 1 if self.s.get("side", "right") == "right" else -1

        def draw(d, ox, oy):
            d.rounded_rectangle((x - 9 + ox, yt + oy, x + 9 + ox, yb + oy), 6, fill=col + (int(235 * a),))
            for yy in (yt, yb):
                d.rounded_rectangle((x - 26 + ox, yy - 4 + oy, x + 26 + ox, yy + 4 + oy), 3, fill=WHITE + (A,))
            if lines and g > 0.6:
                la = int(255 * a * ease((g - 0.6) / 0.4))
                tw = max(fnt.getlength(s) for s in lines)
                pw, ph = tw + 50, 30 + 46 * len(lines)
                cy = min(max((yt + yb) / 2, (CAP_BAND[1] + 0.03) * H + ph / 2), (CHIP_Y - 0.03) * H - ph / 2)
                cx = x + side * (44 + pw / 2)
                cx = min(max(cx, pw / 2 + 30), W - pw / 2 - 30)
                d.rounded_rectangle((cx - pw / 2 + ox, cy - ph / 2 + oy, cx + pw / 2 + ox, cy + ph / 2 + oy), 22,
                                    fill=col + (int(230 * la / 255),))
                for i, s in enumerate(lines):
                    d.text((cx + ox, cy - (len(lines) - 1) * 23 + i * 46 + oy), s, font=fnt, fill=WHITE + (la,), anchor="mm")
        y_lo = min(yt, yb, (CAP_BAND[1] + 0.02) * H) - 80
        y_hi = max(yt, yb, (CHIP_Y - 0.03) * H) + 80
        return [sprite_from(draw, (0, y_lo, W, y_hi), blur=7, alpha=0.4, glow=10, glow_alpha=0.15)]


class Big(Item):
    band = "mid"
    anim = 0.4

    def sprites(self, t, f):
        a = self.alpha(t)
        if a <= 0.004:
            return []
        y = self.s.get("y", 0.47) * H

        def mk():
            fb, fs = font(92, 8), font(42, 2)
            txt, sub = self.s["text"], self.s.get("sub")
            tw = fb.getlength(txt)
            pw = max(tw, fs.getlength(sub) if sub else 0) + 110
            ph = 150 + (64 if sub else 0)

            def draw(d, ox, oy):
                d.rounded_rectangle((W / 2 - pw / 2 + ox, y - ph / 2 + oy, W / 2 + pw / 2 + ox, y + ph / 2 + oy), 30,
                                    fill=NAVY + (215,))
                d.rounded_rectangle((W / 2 - pw / 2 + ox, y + ph / 2 - 12 + oy, W / 2 + pw / 2 + ox, y + ph / 2 + oy), 6,
                                    fill=RED + (255,))
                d.text((W / 2 + ox, y - (30 if sub else 0) + oy), txt, font=fb, fill=WHITE + (255,), anchor="mm")
                if sub:
                    d.text((W / 2 + ox, y + 56 + oy), sub, font=fs, fill=(235, 238, 245, 255), anchor="mm")
            return sprite_from(draw, (W / 2 - pw / 2, y - ph / 2, W / 2 + pw / 2, y + ph / 2), blur=10, alpha=0.45)
        sp = self.cached("big", mk)
        return [Sprite(fade(sp.img, a), sp.x, sp.y + round(16 * (1 - ease((t - self.t0) / self.anim))))]


class Meter(Item):
    band = "low"

    def __init__(self, bc, spec):
        super().__init__(bc, spec)
        self.ts = [bc.cue(c, 0.5 + i) for i, c in enumerate(spec["cues"])]
        self.t0 = min(self.ts) - 0.3
        self.y = spec.get("y", 0.585)

    def events(self):
        fps = self.bc.fps
        ev = set(range(int(self.t0 * fps), int((self.t0 + 0.35) * fps) + 3))
        for t in self.ts:
            ev.update(range(int(t * fps), int((t + 0.3) * fps) + 3))
        return ev

    def sprites(self, t, f):
        a = ease((t - self.t0) / 0.35)
        if a <= 0.004:
            return []
        n = self.s.get("segments", len(self.ts))
        fills = tuple(round(ease((t - ti) / 0.3), 2) for ti in self.ts)
        key = (round(a, 2), fills)

        def mk():
            y = self.y * H
            seg_w, gap = 150, 14
            total = n * seg_w + (n - 1) * gap
            x0 = W / 2 - total / 2
            cols = [TEAL, (130, 196, 70), AMBER, RED]
            fl = font(34, 8)
            lab = self.s.get("label", "WORKLOAD")

            def draw(d, ox, oy):
                d.text((W / 2 + ox, y - 46 + oy), lab, font=fl, fill=WHITE + (int(255 * a),), anchor="mm")
                for i in range(n):
                    xx = x0 + i * (seg_w + gap)
                    d.rounded_rectangle((xx + ox, y - 16 + oy, xx + seg_w + ox, y + 16 + oy), 10, fill=NAVY + (int(190 * a),))
                    k = fills[i] if i < len(fills) else 0
                    if k > 0:
                        c = cols[min(i, len(cols) - 1)]
                        d.rounded_rectangle((xx + 4 + ox, y - 12 + oy, xx + 4 + (seg_w - 8) * k + ox, y + 12 + oy), 8,
                                            fill=c + (int(255 * a),))
            return sprite_from(draw, (x0 - 10, y - 80, x0 + total + 10, y + 26), blur=6, alpha=0.4, glow=10, glow_alpha=0.12)
        return [self.cached(key, mk)]


class Profile(Item):
    """Altitude-vs-time graph of a typical flight (takeoff, climb, cruise, descent, landing)."""
    band = "mid"
    anim = 1.4

    def __init__(self, bc, spec):
        super().__init__(bc, spec)
        self.mode = spec.get("mode", "intro")
        self.box = (90, 0.345 * H, W - 90, 0.625 * H)
        x0, y0, x1, y1 = self.box
        gx0, gx1, gy0, gy1 = x0 + 50, x1 - 40, y0 + 70, y1 - 70
        self.g = (gx0, gx1, gy0, gy1)
        # takeoff 0-6 %, climb 6-18 %, cruise 18-80 %, descent 80-93 %, approach+landing 93-100 %
        pts = []
        for i in range(201):
            u = i / 200.0
            if u < 0.18:
                h = (u / 0.18) ** 0.6
            elif u < 0.80:
                h = 1.0
            else:
                h = max(0.0, 1 - ((u - 0.80) / 0.20) ** 0.75)
            pts.append((gx0 + u * (gx1 - gx0), gy1 - h * (gy1 - gy0)))
        self.pts = pts
        self.cue_t = {k: bc.cue(spec[k], None) for k in ("takeoff_cue", "landing_cue", "zone_cue", "red_cue") if k in spec}

    def events(self):
        fps = self.bc.fps
        ev = set(range(int(self.t0 * fps), int((self.t0 + self.anim) * fps) + 3))
        for t in self.cue_t.values():
            if t is not None:
                ev.update(range(int(t * fps), int((t + 0.5) * fps) + 3))
        return ev

    def sprites(self, t, f):
        a = ease((t - self.t0) / 0.35)
        if a <= 0.004:
            return []
        draw_k = 1.0 if self.mode == "zones" else round(min(1.0, max(0.0, (t - self.t0) / self.anim)), 3)

        def k_of(name, dur=0.4):
            tt = self.cue_t.get(name)
            return 0.0 if tt is None else round(ease((t - tt) / dur), 2)
        kt, kl, kz, kr = k_of("takeoff_cue"), k_of("landing_cue"), k_of("zone_cue", 0.5), k_of("red_cue", 0.5)
        key = (round(a, 2), draw_k, kt, kl, kz, kr)

        def mk():
            x0, y0, x1, y1 = self.box
            gx0, gx1, gy0, gy1 = self.g
            fs, fl = font(30, 2), font(34, 8)
            A = int(255 * a)

            def draw(d, ox, oy):
                d.rounded_rectangle((x0 + ox, y0 + oy, x1 + ox, y1 + oy), 28, fill=NAVY + (int(170 * a),))
                # zones (shaded slices under the curve)
                if kz > 0:
                    col = tuple(int(TEAL[i] + (RED[i] - TEAL[i]) * kr) for i in range(3))
                    for ua, ub in ((0.0, 0.10), (0.88, 1.0)):
                        xa, xb = gx0 + ua * (gx1 - gx0), gx0 + ub * (gx1 - gx0)
                        d.rectangle((xa + ox, gy0 - 10 + oy, xb + ox, gy1 + oy), fill=col + (int(150 * kz * a),))
                    d.text(((gx0 + gx1) / 2 + ox, gy0 - 30 + oy), "CRUISE = MOST OF THE FLIGHT", font=fs,
                           fill=(220, 226, 238, int(220 * kz * a)), anchor="mm")
                # axes
                d.line([(gx0 + ox, gy0 - 20 + oy), (gx0 + ox, gy1 + oy), (gx1 + 10 + ox, gy1 + oy)],
                       fill=(200, 208, 222, int(200 * a)), width=3)
                d.text((gx0 + 8 + ox, gy0 - 34 + oy), "ALTITUDE", font=fs, fill=(200, 208, 222, int(220 * a)), anchor="lm")
                d.text((gx1 + ox, gy1 + 30 + oy), "FLIGHT TIME", font=fs, fill=(200, 208, 222, int(220 * a)), anchor="rm")
                # curve
                n = max(2, int(len(self.pts) * draw_k))
                seg = [(x + ox, y + oy) for x, y in self.pts[:n]]
                d.line(seg, fill=WHITE + (A,), width=7, joint="curve")
                hx, hy = seg[-1]
                d.ellipse((hx - 11, hy - 11, hx + 11, hy + 11), fill=RED + (A,))
                for nm, k, u, txt in (("t", kt, 0.05, "TAKEOFF"), ("l", kl, 0.95, "LANDING")):
                    if k > 0:
                        xx = gx0 + u * (gx1 - gx0)
                        d.rounded_rectangle((xx - 92 + ox, gy1 - 120 + oy, xx + 92 + ox, gy1 - 70 + oy), 22,
                                            fill=WHITE + (int(240 * k * a),))
                        d.text((xx + ox, gy1 - 95 + oy), txt, font=fl, fill=NAVY + (int(255 * k * a),), anchor="mm")
            return sprite_from(draw, self.box, blur=10, alpha=0.4, glow=12, glow_alpha=0.12)
        return [self.cached(key, mk)]


class History(Item):
    band = "mid"
    anim = 0.45

    def __init__(self, bc, spec):
        super().__init__(bc, spec)
        self.ts = [bc.cue(c, 1.0 + 3 * i) for i, c in enumerate(spec["cues"])]
        self.t0 = min(self.ts)

    def events(self):
        fps = self.bc.fps
        ev = set()
        for t in self.ts:
            ev.update(range(int(t * fps), int((t + self.anim) * fps) + 3))
        return ev

    def card(self, i):
        title, sub = self.s["cards"][i]

        def mk():
            y = (0.405 + 0.135 * i) * H
            pw, ph = 900, 200
            x0 = W / 2 - pw / 2
            fy, fp, fs = font(64, 8), font(44, 8), font(38, 2)
            year, _, place = title.partition("·")

            def draw(d, ox, oy):
                d.rounded_rectangle((x0 + ox, y - ph / 2 + oy, x0 + pw + ox, y + ph / 2 + oy), 26, fill=NAVY + (220,))
                d.rounded_rectangle((x0 + ox, y - ph / 2 + oy, x0 + 14 + ox, y + ph / 2 + oy), 7, fill=RED + (255,))
                d.text((x0 + 50 + ox, y - 34 + oy), year.strip(), font=fy, fill=RED + (255,), anchor="lm")
                d.text((x0 + 50 + fy.getlength(year.strip()) + 30 + ox, y - 30 + oy), place.strip(), font=fp,
                       fill=WHITE + (255,), anchor="lm")
                d.text((x0 + 50 + ox, y + 46 + oy), sub, font=fs, fill=(225, 230, 240, 255), anchor="lm")
                if self.s.get("icon", "bridge") != "bridge":  # episodes not about bridges: no icon
                    return
                # small arch-bridge icon
                bx, by = x0 + pw - 120, y + 10
                d.arc((bx - 70 + ox, by - 50 + oy, bx + 70 + ox, by + 70 + oy), 200, 340, fill=WHITE + (230,), width=6)
                d.line([(bx - 80 + ox, by - 8 + oy), (bx + 80 + ox, by - 8 + oy)], fill=WHITE + (230,), width=6)
                for k in range(-2, 3):
                    d.line([(bx + k * 26 + ox, by - 8 + oy), (bx + k * 26 + ox, by + 16 - abs(k) * 12 + oy)],
                           fill=WHITE + (200,), width=3)
            return sprite_from(draw, (x0, y - ph / 2, x0 + pw, y + ph / 2), blur=10, alpha=0.45)
        return self.cached(i, mk)

    def sprites(self, t, f):
        out = []
        for i, ti in enumerate(self.ts):
            a = ease((t - ti) / self.anim)
            if a <= 0.004:
                continue
            sp = self.card(i)
            out.append(Sprite(fade(sp.img, a), sp.x, sp.y + round(24 * (1 - a))))
        return out


class Board(Item):
    """Airport departures board: {title, rows: [[time, place, status], ...], flips: [[row, new_status, cue], ...],
    [cue|at], [y]}. Status ON TIME in green, anything else in red; a status flips (split-flap squash) on its cue."""
    band = "mid"
    anim = 0.4

    def __init__(self, bc, spec):
        super().__init__(bc, spec)
        self.flips = [(int(r), st, bc.cue(c, 1.0 + i)) for i, (r, st, c) in enumerate(spec.get("flips", []))]
        self.y = spec.get("y", 0.44)
        n = len(spec["rows"])
        self.ph = 96 + 70 * n
        assert self.y * H - self.ph / 2 >= (CAP_BAND[1] + 0.012) * H, "board runs into the captions"
        assert self.y * H + self.ph / 2 <= CHIP_Y * H - 0.02 * H, "board runs into the chips"

    def events(self):
        fps = self.bc.fps
        ev = set(range(int(self.t0 * fps), int((self.t0 + self.anim) * fps) + 3))
        for _, _, t in self.flips:
            ev.update(range(int(t * fps), int((t + 0.36) * fps) + 3))
        return ev

    def status(self, i, t):
        st, k = self.s["rows"][i][2], 1.0
        for r, ns, tf in self.flips:
            if r == i and t >= tf:
                u = (t - tf) / 0.36
                if u < 0.5:
                    k = 1 - u * 2           # old status squashes shut
                else:
                    st, k = ns, min(1.0, (u - 0.5) * 2)
        return st, round(k, 2)

    def sprites(self, t, f):
        a = self.alpha(t)
        if a <= 0.004:
            return []
        rows = self.s["rows"]
        sts = tuple(self.status(i, t) for i in range(len(rows)))
        key = (round(a, 2), sts)

        def mk():
            pw, ph = 940, self.ph
            x0, y0 = W / 2 - pw / 2, self.y * H - ph / 2
            ft, fr = font(44, 8), font(42, 8)
            A_ = int(255 * a)

            def draw(d, ox, oy):
                d.rounded_rectangle((x0 + ox, y0 + oy, x0 + pw + ox, y0 + ph + oy), 24, fill=(14, 18, 26, int(235 * a)))
                d.text((x0 + 40 + ox, y0 + 50 + oy), self.s.get("title", "DEPARTURES"), font=ft, fill=AMBER + (A_,),
                       anchor="lm")
                d.text((x0 + pw - 40 + ox, y0 + 50 + oy), "STATUS", font=font(30, 2), fill=(170, 176, 188, A_),
                       anchor="rm")
                for i, (tm, place, _) in enumerate(rows):
                    cy = y0 + 96 + 70 * i + 35
                    d.rounded_rectangle((x0 + 24 + ox, cy - 29 + oy, x0 + pw - 24 + ox, cy + 29 + oy), 10,
                                        fill=(30, 36, 48, A_))
                    d.text((x0 + 48 + ox, cy + oy), tm, font=fr, fill=(255, 214, 102, A_), anchor="lm")
                    d.text((x0 + 210 + ox, cy + oy), place, font=fr, fill=WHITE + (A_,), anchor="lm")
                    st, k = sts[i]
                    col = (60, 200, 120) if st.upper() == "ON TIME" else RED
                    sw = 260
                    sx1 = x0 + pw - 40
                    hh = 26 * k
                    if hh > 1:
                        d.rounded_rectangle((sx1 - sw + ox, cy - hh + oy, sx1 + ox, cy + hh + oy), 8, fill=col + (A_,))
                        if k > 0.6:
                            d.text((sx1 - sw / 2 + ox, cy + 1 + oy), st, font=font(34, 8), fill=WHITE + (A_,),
                                   anchor="mm")
            return sprite_from(draw, (x0, y0, x0 + pw, y0 + ph), blur=10, alpha=0.45, glow=12, glow_alpha=0.15)
        sp = self.cached(key, mk)
        return [Sprite(sp.img, sp.x, sp.y + round(16 * (1 - ease((t - self.t0) / self.anim))))]


ITEM_TYPES = {"card": Card, "chips": Chips, "label": Label, "bar": Bar, "big": Big, "meter": Meter,
              "profile": Profile, "history": History, "board": Board}


# ================================================================ per-beat compositing
def beat_name(ep, i):
    return "%02d_%s" % (i, ep["beats"][i]["id"])


def build_items(bc):
    items, blur = [], None
    for spec in bc.beat["shot"].get("overlays", []):
        if spec["type"] == "blur":
            blur = spec
            continue
        items.append(ITEM_TYPES[spec["type"]](bc, spec))
    return items, blur


def compose_frame(base, bc, items, caps, f, blur):
    """base: PIL RGB frame (any size) -> RGB 1080x1920 with overlays."""
    if base.size != (W, H):
        base = base.resize((W, H), Image.BICUBIC)
    if blur:
        base = base.filter(ImageFilter.GaussianBlur(blur.get("radius", 10)))
        dim = blur.get("dim", 0.25)
        if dim:
            base = Image.blend(base, Image.new("RGB", (W, H), NAVY), dim)
    img = base.convert("RGBA")
    t = (f - 1) / bc.fps
    for it in items:
        for sp in it.sprites(t, f):
            paste(img, sp)
    cs = caps.at(bc.start + t)
    if cs is not None:
        paste(img, cs)
    return img.convert("RGB")


def paste(img, sp):
    """alpha_composite a Sprite, clipped to the frame."""
    x0, y0 = max(0, sp.x), max(0, sp.y)
    x1, y1 = min(img.width, sp.x + sp.img.width), min(img.height, sp.y + sp.img.height)
    if x1 <= x0 or y1 <= y0:
        return
    crop = sp.img.crop((x0 - sp.x, y0 - sp.y, x1 - sp.x, y1 - sp.y))
    img.alpha_composite(crop, (x0, y0))


def _ctx(ep_path, idx):
    ep = load_ep(ep_path)
    workdir = os.environ.get("EPISODE_WORKDIR") or os.path.join(ROOT, "output", ep["slug"])
    tim = json.load(open(os.path.join(workdir, "audio", "timings.json")))
    caps = json.load(open(os.path.join(workdir, "captions.json")))
    fps = ep.get("render", {}).get("fps", 30)
    name = beat_name(ep, idx)
    bc = BeatCtx(ep, idx, tim["beats"][idx], caps["words"], fps, load_anchors(workdir, name))
    bc.g0 = sum(int(round(b["duration"] * fps)) for b in tim["beats"][:idx])   # frames before this beat
    return ep, workdir, tim, caps, fps, name, bc


def render_beat(args):
    ep_path, idx = args
    ep, workdir, tim, caps_d, fps, name, bc = _ctx(ep_path, idx)
    caps = Captions(caps_d, tim["total"])
    items, blur = build_items(bc)
    fdir = os.path.join(workdir, "frames_v2", name)
    sdir = os.path.join(workdir, "segments_v2")
    os.makedirs(sdir, exist_ok=True)
    out = os.path.join(sdir, name + ".mp4")
    t0 = time.time()
    p = subprocess.Popen([PC.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-frames:v", str(bc.nframes),
                          "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
                          "-profile:v", "high", "-g", str(fps * 2), out], stdin=subprocess.PIPE)
    last = None
    cap_ev, prev_key = set(), None
    for f in range(1, bc.nframes + 1):
        cs = caps.at(bc.start + (f - 1) / fps)
        key = None if cs is None else id(cs)
        if key != prev_key:
            cap_ev.update(range(bc.g0 + f - 1, bc.g0 + f + 2))
        prev_key = key
        fp = os.path.join(fdir, "%04d.jpg" % f)
        if os.path.exists(fp):
            last = fp
        elif last is None:
            raise SystemExit("missing frame %s" % fp)
        else:
            print("[overlay] WARNING missing %s, repeating previous" % fp)
        base = Image.open(last).convert("RGB")
        p.stdin.write(compose_frame(base, bc, items, caps, f, blur).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit("ffmpeg failed for %s" % name)
    # expected animation frames (global, 1-based) for the flicker QC
    g0 = bc.g0
    ev = {"low": set(), "mid": set(), "card": set(), "caption": cap_ev}
    for it in items:
        ev[it.band].update(g0 + e for e in it.events())
    return name, time.time() - t0, {k: sorted(v) for k, v in ev.items()}


def render_stream_beat(args):
    """QC helper: kind 'overlay' = captions + overlays on flat grey (isolates 2D flicker); 'base' = the 3D frames as
    they appear under the overlays (with plate blur), no text."""
    ep_path, idx, kind = args
    ep, workdir, tim, caps_d, fps, name, bc = _ctx(ep_path, idx)
    caps = Captions(caps_d, tim["total"])
    items, blur = build_items(bc)
    out = os.path.join(workdir, "qc", "stream_%s_%s.mp4" % (kind, name))
    p = subprocess.Popen([PC.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-frames:v", str(bc.nframes),
                          "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", out],
                         stdin=subprocess.PIPE)
    grey = Image.new("RGB", (W, H), (118, 128, 140))
    fdir = os.path.join(workdir, "frames_v2", name)
    for f in range(1, bc.nframes + 1):
        if kind == "overlay":
            fr = compose_frame(grey, bc, items, caps, f, None)
        else:
            fr = compose_frame(Image.open(os.path.join(fdir, "%04d.jpg" % f)).convert("RGB"), bc, [],
                               _NoCaps(), f, blur)
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    p.wait()
    return out


class _NoCaps:
    def at(self, T):
        return None


def qc_streams(ep_path, parallel=4):
    ep = load_ep(ep_path)
    workdir = os.environ.get("EPISODE_WORKDIR") or os.path.join(ROOT, "output", ep["slug"])
    os.makedirs(os.path.join(workdir, "qc"), exist_ok=True)
    res = {}
    for kind in ("overlay", "base"):
        with Pool(parallel) as pool:
            parts = pool.map(render_stream_beat, [(ep_path, i, kind) for i in range(len(ep["beats"]))])
        lst = os.path.join(workdir, "qc", "stream_%s.txt" % kind)
        with open(lst, "w") as fh:
            for q in parts:
                fh.write("file '%s'\n" % q.replace("'", "'\\''"))
        out = os.path.join(workdir, "qc", "stream_%s.mp4" % kind)
        subprocess.run([PC.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out],
                       check=True)
        for q in parts:
            os.remove(q)
        os.remove(lst)
        res[kind] = out
    return res


def assemble(ep_path, parallel=4, beats=None):
    ep = load_ep(ep_path)
    workdir = os.environ.get("EPISODE_WORKDIR") or os.path.join(ROOT, "output", ep["slug"])
    idxs = beats if beats is not None else list(range(len(ep["beats"])))
    with Pool(parallel) as pool:
        res = pool.map(render_beat, [(ep_path, i) for i in idxs])
    for name, dt, _ in res:
        print("[overlay] %s composited in %.0fs" % (name, dt))
    tim = json.load(open(os.path.join(workdir, "audio", "timings.json")))
    caps = Captions(json.load(open(os.path.join(workdir, "captions.json"))), tim["total"])
    fps = ep.get("render", {}).get("fps", 30)
    evp = os.path.join(workdir, "overlay_events_v2.json")
    old = json.load(open(evp)) if os.path.exists(evp) and beats is not None else {}
    merged = {}
    for band in ("caption", "low", "mid", "card"):
        s = set(old.get(band, []))
        for _, _, ev in res:
            s.update(ev[band])
        merged[band] = sorted(s)
    json.dump(merged, open(evp, "w"))
    return [os.path.join(workdir, "segments_v2", beat_name(ep, i) + ".mp4") for i in range(len(ep["beats"]))]


def preview(ep_path, idx, times, out_dir):
    """Composite single frames (seconds into the beat) from rendered frames or stills, for layout checks."""
    ep, workdir, tim, caps_d, fps, name, bc = _ctx(ep_path, idx)
    caps = Captions(caps_d, tim["total"])
    items, blur = build_items(bc)
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    for t in times:
        f = max(1, min(bc.nframes, int(round(t * fps)) + 1))
        fp = os.path.join(workdir, "frames_v2", name, "%04d.jpg" % f)
        if not os.path.exists(fp):
            sp = os.path.join(workdir, "stills_v2", "%s_f%04d.png" % (name, f))
            fp = sp if os.path.exists(sp) else None
        base = Image.open(fp).convert("RGB") if fp else Image.new("RGB", (W, H), (120, 150, 190))
        o = os.path.join(out_dir, "%s_t%05.2f.png" % (name, t))
        compose_frame(base, bc, items, caps, f, blur).save(o)
        outs.append(o)
    return outs


if __name__ == "__main__":
    a = sys.argv[1:]
    epp = os.path.abspath(a[0])
    if "--preview" in a:
        i = int(a[a.index("--beat") + 1])
        ts = [float(x) for x in a[a.index("--preview") + 1].split(",")]
        print(preview(epp, i, ts, a[a.index("--out") + 1] if "--out" in a else ("/tmp" if os.name != "nt" else tempfile.gettempdir())))
    else:
        bs = [int(x) for x in a[a.index("--beats") + 1].split(",")] if "--beats" in a else None
        print(assemble(epp, beats=bs))

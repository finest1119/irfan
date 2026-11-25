"""Cut a 70-120 s Reel down to a <=60 s Facebook Page Story with a 2D end card.

Usage:
  .venv/bin/python tools/make_story_cut.py "output/<keyword>.mp4" "output/<keyword> story.mp4"
      [--captions output/<slug>/captions.json] [--min 55] [--max 58] [--card 2.0] [--limit 60]

Why: Meta's Page Stories API caps video stories at 60 s
(https://developers.facebook.com/docs/page-stories-api). Our reels run 70-120 s.

How:
  1. Find the episode's captions.json (output/<slug>/captions.json, slug = keyword with spaces -> hyphens)
     and pick the LAST sentence end (word ending . ? !) inside [--min, --max] s, keeping >=0.3 s of
     tail room so the audio fade lands on silence. Total (cut + card) must stay <= --limit - 0.2 s.
  2. Fallback: ffmpeg silencedetect inside the window, cut in the middle of the last silence gap.
  3. End card (~2 s): blurred + darkened last frame, WJH logo, navy #0B1F3A panel, red #E63946 accent,
     white bold "WATCH THE FULL VIDEO / ON OUR PAGE". Pure 2D (PIL), no 3D.
  4. Audio fades out over the last 0.3 s of the cut; silence under the card.
  Output: 1080x1920, 30 fps, H.264 (yuv420p, closed 2 s GOP) + AAC-LC 48 kHz stereo 128k, +faststart.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NAVY, RED, WHITE = (11, 31, 58), (230, 57, 70), (255, 255, 255)
W, H, FPS = 1080, 1920, 30
FADE = 0.3
LOGO = os.path.join(ROOT, "branding", "logo-i.png")
FONTS = ["/System/Library/Fonts/Supplemental/Arial Black.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", path]).stdout.strip())


def keyword_of(path):
    k = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"\s+(fb|story)$", "", k).strip()


def find_captions(reel):
    kw = keyword_of(reel)
    slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
    base = os.path.dirname(os.path.abspath(reel))
    for d in (os.path.join(base, slug), os.path.join(ROOT, "output", slug)):
        p = os.path.join(d, "captions.json")
        if os.path.exists(p):
            return p
    for p in glob.glob(os.path.join(ROOT, "output", "*", "captions.json")):
        if os.path.basename(os.path.dirname(p)).lower() == slug:
            return p
    return None


def cut_from_captions(path, lo, hi):
    words = json.load(open(path, encoding="utf-8")).get("words", [])
    best = None
    for i, w in enumerate(words):
        if not re.search(r"[.?!][\"')\]]*$", w["word"].strip()):
            continue
        nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + 1.0
        cut = min(w["end"] + 0.35, max(w["end"] + FADE, (w["end"] + nxt) / 2))
        if cut > nxt + 0.05:          # would bleed into the next word
            continue
        if lo <= cut <= hi and w["end"] + FADE <= hi:
            best = (cut, w)
    return best


def cut_from_silence(reel, lo, hi):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(lo), "-t", str(hi - lo + 0.5),
                        "-i", reel, "-af", "silencedetect=noise=-35dB:d=0.2", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    best = None
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else s + 0.4
        mid = lo + (s + e) / 2
        if lo <= mid <= hi:
            best = mid
    return best


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def make_card(frame_png, out_png):
    bg = Image.open(frame_png).convert("RGB").resize((W, H))
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.38)
    tint = Image.new("RGB", (W, H), NAVY)
    bg = Image.blend(bg, tint, 0.35)
    d = ImageDraw.Draw(bg)

    # logo (circular crop) near top-centre
    if os.path.exists(LOGO):
        lg = Image.open(LOGO).convert("RGB").resize((380, 380), Image.LANCZOS)
        m = Image.new("L", (380, 380), 0)
        ImageDraw.Draw(m).ellipse((4, 4, 376, 376), fill=255)
        bg.paste(lg, ((W - 380) // 2, 430), m)

    # navy panel with red accent bar (logo style)
    px0, py0, px1, py1 = 90, 900, W - 90, 1330
    d.rounded_rectangle((px0, py0, px1, py1), radius=28, fill=NAVY)
    d.rectangle((px0 + 40, py0 + 70, px0 + 58, py1 - 70), fill=RED)
    lines = [("WATCH THE", 88), ("FULL VIDEO", 88), ("ON OUR PAGE", 70)]
    y = py0 + 70
    for text, sz in lines:
        f = font(sz)
        x = px0 + 100
        d.text((x, y), text, font=f, fill=RED if text == "ON OUR PAGE" else WHITE)
        y += sz + 34
    # small CTA strip under the panel
    f = font(46)
    t = "What Just Happened?"
    tw = d.textlength(t, font=f)
    d.text(((W - tw) / 2, py1 + 70), t, font=f, fill=WHITE)
    d.rectangle(((W - 160) / 2, py1 + 140, (W + 160) / 2, py1 + 148), fill=RED)
    bg.save(out_png)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("reel")
    ap.add_argument("out")
    ap.add_argument("--captions")
    ap.add_argument("--min", type=float, default=55.0)
    ap.add_argument("--max", type=float, default=58.0)
    ap.add_argument("--card", type=float, default=2.0)
    ap.add_argument("--limit", type=float, default=60.0, help="documented max story length (s)")
    a = ap.parse_args()

    if not os.path.exists(a.reel):
        sys.exit("no such reel: %s" % a.reel)
    total = duration(a.reel)
    hi = min(a.max, a.limit - 0.2 - a.card, total - 0.1)
    lo = min(a.min, hi - 1.0)

    cap = a.captions or find_captions(a.reel)
    cut, how = None, None
    if cap:
        r = cut_from_captions(cap, lo, hi)
        if r:
            cut, how = r[0], "sentence end '%s' @ %.2fs (%s)" % (r[1]["word"], r[1]["end"], os.path.relpath(cap, ROOT))
    if cut is None:
        cut = cut_from_silence(a.reel, lo, hi)
        if cut is not None:
            how = "silence gap"
    if cut is None:
        cut, how = hi, "hard cut (no sentence end / silence found)"
    cut = round(cut, 3)
    print("cut at %.3fs via %s; card %.1fs -> total %.2fs (limit %.0fs)" % (cut, how, a.card, cut + a.card, a.limit))

    with tempfile.TemporaryDirectory() as tmp:
        frame, card = os.path.join(tmp, "last.png"), os.path.join(tmp, "card.png")
        run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % max(0, cut - 1.0 / FPS), "-i", a.reel,
             "-frames:v", "1", frame])
        make_card(frame, card)
        fc = ("[0:v]trim=0:{c},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,"
              "pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p,setsar=1[v0];"
              "[0:a]atrim=0:{c},asetpts=PTS-STARTPTS,aresample=48000,"
              "aformat=channel_layouts=stereo,afade=t=out:st={fs}:d={fd}[a0];"
              "[1:v]scale={w}:{h},fps={fps},format=yuv420p,setsar=1,fade=t=in:st=0:d=0.2[v1];"
              "[2:a]aformat=channel_layouts=stereo,aresample=48000[a1];"
              "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]").format(
            c=cut, w=W, h=H, fps=FPS, fs=max(0, cut - FADE), fd=FADE)
        run(["ffmpeg", "-y", "-v", "error", "-i", a.reel,
             "-loop", "1", "-framerate", str(FPS), "-t", str(a.card), "-i", card,
             "-f", "lavfi", "-t", str(a.card), "-i", "anullsrc=r=48000:cl=stereo",
             "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0", "-flags", "+cgop",
             "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", a.out])
    d = duration(a.out)
    print("wrote %s (%.2fs)" % (a.out, d))
    if d > a.limit:
        sys.exit("ERROR: output %.2fs exceeds %.0fs story limit" % (d, a.limit))


if __name__ == "__main__":
    main()

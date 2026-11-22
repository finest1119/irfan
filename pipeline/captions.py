"""Word timings + caption chunks + caption PNG overlay stream.

Usage: .venv/bin/python pipeline/captions.py EPISODE_JSON WORKDIR

Reads WORKDIR/audio/beat_<id>.wav + timings.json, writes:
  WORKDIR/captions.json        {"words": [{word, norm, start, end, beat}], "chunks": [{text, start, end}]}
  WORKDIR/captions/*.png       one transparent 1080x1920 PNG per chunk (+ blank.png)
  WORKDIR/captions/list.ffconcat   concat-demuxer playlist with exact durations

Caption TEXT always comes from the script (whisper mishears names like "Trakia"/"Yambol");
whisper (faster-whisper base.en) only supplies the timings. Script words are aligned to
whisper words with difflib; unmatched script words get interpolated times.
"""
import difflib
import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = int(0.12 * H), int(0.80 * H)   # 230 .. 1536 px
CAPTION_CENTER_Y = 1290
FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_SIZE = 82
STROKE = 9
MAX_TEXT_W = 940


def norm(w):
    w = w.lower().replace("-", "")
    return re.sub(r"[^a-z0-9]", "", w)


def whisper_words(model, wav):
    segs, _ = model.transcribe(wav, word_timestamps=True, language="en", beam_size=5)
    out = []
    for s in segs:
        for w in s.words or []:
            out.append({"w": w.word.strip(), "n": norm(w.word), "start": w.start, "end": w.end})
    return [x for x in out if x["n"]]


def align(script_text, heard, offset):
    tokens = script_text.split()
    sn = [norm(t) for t in tokens]
    hn = [h["n"] for h in heard]
    sm = difflib.SequenceMatcher(a=sn, b=hn, autojunk=False)
    times = [None] * len(tokens)
    matched_eq = [0]
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            matched_eq[0] += i2 - i1
            for k in range(i2 - i1):
                h = heard[j1 + k]
                times[i1 + k] = (h["start"], h["end"])
        elif tag == "replace":
            # spread the heard span over the script span (e.g. "10th" vs "tenth", names)
            hs, he = heard[j1]["start"], heard[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                a = hs + (he - hs) * k / n
                b = hs + (he - hs) * (k + 1) / n
                times[i1 + k] = (a, b)
    # interpolate gaps
    for i in range(len(times)):
        if times[i] is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.3)
            times[i] = (prev, max(prev + 0.05, (prev + nxt) / 2))
    words = []
    for t, (a, b) in zip(tokens, times):
        words.append({"word": t, "norm": norm(t), "start": round(a + offset, 3), "end": round(b + offset, 3)})
    return words, matched_eq[0] / float(max(1, len(tokens))), " ".join(h["w"] for h in heard)


def chunk(words, min_w=2, max_w=4):
    """2-4 words per chunk. Split into phrases at punctuation / beat ends, then cut each
    phrase into balanced pieces (5 -> 3+2, 6 -> 3+3, 7 -> 4+3) so no dangling single words."""
    import math as _m

    phrases, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        last_of_beat = i == len(words) - 1 or words[i + 1]["beat"] != w["beat"]
        if w["word"][-1] in ".?!,;:" or last_of_beat:
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    # glue 1-word phrases onto a neighbour in the same beat
    glued = []
    for ph in phrases:
        if len(ph) == 1 and glued and glued[-1][-1]["beat"] == ph[0]["beat"] and len(glued[-1]) % max_w != 0 \
                and glued[-1][-1]["word"][-1] not in ".?!":
            glued[-1] = glued[-1] + ph
        else:
            glued.append(ph)
    merged = []
    for ph in glued:
        n = len(ph)
        k = max(1, int(_m.ceil(n / float(max_w))))
        base, extra = divmod(n, k)
        i = 0
        for j in range(k):
            size = base + (1 if j < extra else 0)
            merged.append(ph[i:i + size])
            i += size
    out = []
    for k, c in enumerate(merged):
        text = " ".join(w["word"] for w in c)
        text = re.sub(r"[,;:.]+$", "", text)
        start = c[0]["start"]
        end = c[-1]["end"] + 0.25
        if k + 1 < len(merged):
            end = min(end, merged[k + 1][0]["start"])
        out.append({"text": text, "start": round(start, 3), "end": round(max(end, start + 0.2), 3)})
    return out


def render_pngs(chunks, cdir):
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(cdir, exist_ok=True)
    font = ImageFont.truetype(FONT, FONT_SIZE)
    blank = os.path.join(cdir, "blank.png")
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    for i, c in enumerate(chunks):
        text = c["text"].upper()
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # wrap into max 2 lines if too wide
        words = text.split()
        lines = [text]
        if d.textlength(text, font=font) > MAX_TEXT_W and len(words) > 1:
            best = None
            for k in range(1, len(words)):
                a, b = " ".join(words[:k]), " ".join(words[k:])
                wmax = max(d.textlength(a, font=font), d.textlength(b, font=font))
                if best is None or wmax < best[0]:
                    best = (wmax, [a, b])
            lines = best[1]
        f = font
        while max(d.textlength(l, font=f) for l in lines) > MAX_TEXT_W:
            f = ImageFont.truetype(FONT, f.size - 4)
        line_h = int(f.size * 1.18)
        total_h = line_h * len(lines)
        y = CAPTION_CENTER_Y - total_h // 2
        for l in lines:
            # numbers / key figures in brand red-ish accent, rest white
            x = (W - d.textlength(l, font=f)) / 2
            for wd in l.split(" "):
                color = (255, 214, 74, 255) if re.search(r"\d", wd) else (255, 255, 255, 255)
                d.text((x, y), wd, font=f, fill=color, stroke_width=STROKE, stroke_fill=(8, 14, 34, 255))
                x += d.textlength(wd + " ", font=f)
            y += line_h
        bbox = img.getbbox()
        assert bbox[1] >= SAFE_TOP and bbox[3] <= SAFE_BOTTOM, "caption outside safe area: %s" % (bbox,)
        c["png"] = "c%03d.png" % i
        c["bbox"] = list(bbox)
        img.save(os.path.join(cdir, c["png"]))
    return blank


def write_concat(chunks, cdir, total):
    lines = ["ffconcat version 1.0"]
    t = 0.0

    def add(name, dur):
        lines.append("file '%s'" % name)
        lines.append("duration %.3f" % dur)

    for c in chunks:
        if c["start"] > t + 0.001:
            add("blank.png", c["start"] - t)
        add(c["png"], c["end"] - c["start"])
        t = c["end"]
    if total > t:
        add("blank.png", total - t)
    lines.append("file 'blank.png'")  # concat demuxer needs a final entry
    open(os.path.join(cdir, "list.ffconcat"), "w").write("\n".join(lines) + "\n")


def run(episode_path, workdir):
    from faster_whisper import WhisperModel

    ep = json.load(open(episode_path))
    timings = json.load(open(os.path.join(workdir, "audio", "timings.json")))
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    all_words, report = [], []
    for beat, tm in zip(ep["beats"], timings["beats"]):
        wav = os.path.join(workdir, "audio", "beat_%s.wav" % beat["id"])
        heard = whisper_words(model, wav)
        words, ratio, heard_text = align(beat["text"], heard, tm["speech_start"])
        for w in words:
            w["beat"] = beat["id"]
        all_words += words
        report.append({"beat": beat["id"], "match_ratio": round(ratio, 3), "heard": heard_text})
        print("  %-10s aligned %3.0f%%  heard: %s" % (beat["id"], ratio * 100, heard_text[:90]))
    chunks = chunk(all_words)
    cdir = os.path.join(workdir, "captions")
    render_pngs(chunks, cdir)
    write_concat(chunks, cdir, timings["total"])
    json.dump({"words": all_words, "chunks": chunks, "alignment": report},
              open(os.path.join(workdir, "captions.json"), "w"), indent=1)
    print("captions: %d words, %d chunks" % (len(all_words), len(chunks)))


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])

"""Preview stills for Page 3 (Everyday Decoded) v2 episodes, without TTS.

  .venv/bin/python page3/blender/ed_preview.py EPISODE_JSON [--beats 0,3] [--frac 0.7] [--sheet-only]

* Writes SYNTHETIC timings/captions (175 wpm) into output/<slug>/preview_synth/ (never output/<slug>/audio/, so a
  real make_episode run can't mistake them for real voice timings) and the PIL runway textures into its tex_v2/.
* Renders one still per beat (0.5 scale, 12 samples) with the stock pipeline/blender/render_episode_v2.py, which
  loads page3 libs from episode "render.libs". Serial; waits while any other Blender process runs (other sessions).
* Contact sheet -> page3/_preview/<episode-id>-stills.jpg (caption band 22-31 % outlined in red).
Still frame per beat: shot.params "_still" (0..1 fraction of the beat) if present, else --frac.
"""
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
WPM = 175.0


def synth(ep, wd):
    os.makedirs(os.path.join(wd, "audio"), exist_ok=True)
    t, beats, words = 0.0, [], []
    for b in ep["beats"]:
        ws = b["text"].split()
        dur_w = 60.0 / WPM
        cur = t + 0.15
        for i, w in enumerate(ws):
            if i and re.search(r"[.?!]$", ws[i - 1]):
                cur += 0.25
            words.append({"word": w, "norm": re.sub(r"[^a-z0-9']", "", w.lower()), "start": round(cur, 3),
                          "end": round(cur + dur_w * 0.9, 3), "beat": b["id"]})
            cur += dur_w
        end = cur + 0.3
        beats.append({"id": b["id"], "speech_start": round(t + 0.15, 3), "speech_end": round(end - 0.3, 3),
                      "start": round(t, 3), "end": round(end, 3), "duration": round(end - t, 3)})
        t = end
    json.dump({"total": round(t, 3), "beats": beats, "synthetic": True}, open(os.path.join(wd, "audio", "timings.json"), "w"), indent=1)
    chunks = []
    for bid in [b["id"] for b in ep["beats"]]:
        bw = [w for w in words if w["beat"] == bid]
        for i in range(0, len(bw), 3):
            g = bw[i:i + 3]
            chunks.append({"text": " ".join(w["word"] for w in g), "start": g[0]["start"], "end": g[-1]["end"]})
    json.dump({"words": words, "chunks": chunks, "synthetic": True}, open(os.path.join(wd, "captions.json"), "w"),
              indent=1)
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import v2_textures
    v2_textures.make(os.path.join(wd, "tex_v2"))
    return beats


def blender_busy():
    out = subprocess.run(["pgrep", "-x", "Blender"], capture_output=True, text=True).stdout.split()
    return [p for p in out if p.strip() and int(p) != os.getpid()]


def wait_free(max_min=40):
    t0 = time.time()
    while blender_busy():
        if time.time() - t0 > max_min * 60:
            raise SystemExit("another Blender kept running for %d min; giving up" % max_min)
        print("[ed_preview] another Blender is running; waiting 2 min", flush=True)
        time.sleep(120)


def render_still(ep_path, wd, idx, frame, log):
    wait_free()
    cmd = [BLENDER, "-b", "--factory-startup", "-P", os.path.join(ROOT, "pipeline/blender/render_episode_v2.py"), "--",
           ep_path, wd, str(idx), "--still", str(frame), "--scale", "0.5", "--samples", "12"]
    t0 = time.time()
    with open(log, "w") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    txt = open(log).read()
    m = re.search(r"built (\S+) \((\S+)\) in ([\d.]+)s", txt)
    print("[ed_preview] beat %d rc=%d %.0fs total, build %s" % (idx, r.returncode, time.time() - t0,
                                                                m.group(3) if m else "?"), flush=True)
    if "Traceback" in txt:
        print(txt[txt.index("Traceback"):][:3000])


def sheet(ep, wd, beats):
    from PIL import Image, ImageDraw, ImageFont
    sd = os.path.join(wd, "stills_v2")
    tiles = []
    for i, b in enumerate(ep["beats"]):
        name = "%02d_%s" % (i, b["id"])
        fs = sorted(f for f in os.listdir(sd) if f.startswith(name + "_f")) if os.path.isdir(sd) else []
        fs = sorted(fs, key=lambda f: os.path.getmtime(os.path.join(sd, f)))
        tiles.append((name, os.path.join(sd, fs[-1]) if fs else None))
    tw, th = 360, 640
    im = Image.new("RGB", (tw * len(tiles), th + 40), (30, 30, 30))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(os.path.join(ROOT, "assets/fonts/Montserrat-Bold.ttf"), 20)
    except Exception:
        font = None
    for k, (name, p) in enumerate(tiles):
        if p:
            t = Image.open(p).convert("RGB").resize((tw, th))
            im.paste(t, (k * tw, 40))
        d.rectangle((k * tw, 40 + int(0.22 * th), k * tw + tw - 1, 40 + int(0.31 * th)), outline=(255, 40, 40), width=2)
        d.text((k * tw + 8, 8), name, fill=(255, 255, 255), font=font)
    out = os.path.join(ROOT, "page3/_preview", ep["id"] + "-stills.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, quality=88)
    print("[ed_preview] sheet", out)


def main():
    a = sys.argv[1:]
    ep_path = os.path.abspath(a[0])
    ep = json.load(open(ep_path))
    wd = os.path.join(ROOT, "output", ep["slug"], "preview_synth")
    beats = synth(ep, wd)
    sel = [int(x) for x in a[a.index("--beats") + 1].split(",")] if "--beats" in a else range(len(ep["beats"]))
    frac = float(a[a.index("--frac") + 1]) if "--frac" in a else 0.7
    if "--sheet-only" not in a:
        os.makedirs(os.path.join(wd, "logs"), exist_ok=True)
        for i in sel:
            fr = max(1, int(round(beats[i]["duration"] * 30 * ep["beats"][i]["shot"]["params"].get("_still", frac))))
            render_still(ep_path, wd, i, fr, os.path.join(wd, "logs", "%02d.log" % i))
    sheet(ep, wd, beats)


if __name__ == "__main__":
    main()

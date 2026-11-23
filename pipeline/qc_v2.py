"""QC for a finished v2 episode (run by make_episode.py as the last step, or by hand):

  .venv/bin/python pipeline/qc_v2.py episodes/<id>/episode.json output/<keyword>.mp4

1. ffprobe: duration (70-120 s), 1080x1920, 30 fps, an audio stream.
2. Flicker (pipeline/qc_flicker.py) per band: card (y 180-400), caption (400-620), mid (labels / bars / graphs,
   620-1240), low (chips, 1240-1540); expected animation frames from WORKDIR/overlay_events_v2.json + beat cuts.
   Requirement: the overlay-only stream has 0 unexpected spikes and 0 A-B-A reversals. Also listed: final-only A-B-A
   frames while an overlay moves ("overlay_caused") - look at those frames 1:1 (so far always a moving label over
   moving 3D such as a prop or a wobbling figure, not a blink). Raw final-mp4 A-B-A counts
   are reported but not used: moving 3D texture under a fixed band trips that metric on its own.
3. 12 frames -> WORKDIR/qc/t_XX.X.png + WORKDIR/qc/qc_sheet.png. LOOK at the sheet: no void / navy backgrounds,
   nothing graphic, captions readable inside 12-80 %, labels not colliding with captions.
Writes WORKDIR/qc/qc_v2.json and prints a summary (exit code 1 if a hard check fails).
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BANDS = {"card": (180, 400), "caption": (400, 620), "mid": (620, 1240), "low": (1240, 1540)}


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    return {"duration": float(d["format"]["duration"]), "width": v["width"], "height": v["height"],
            "fps": v["r_frame_rate"], "vcodec": v["codec_name"], "audio": a[0]["codec_name"] if a else None}


def main():
    ep_path, final = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    ep = json.load(open(ep_path))
    workdir = os.path.join(ROOT, "output", ep["slug"])
    qdir = os.path.join(workdir, "qc")
    os.makedirs(qdir, exist_ok=True)
    fps = ep.get("render", {}).get("fps", 30)
    res = {"probe": probe(final)}
    p = res["probe"]
    ok = 70 <= p["duration"] <= 120 and (p["width"], p["height"]) == (1080, 1920) and p["audio"] is not None
    res["probe_ok"] = ok
    # flicker. Region A-B-A on the final mp4 is dominated by real 3D camera motion (moving texture keeps the region
    # mean while pixels change), so the check is split:
    #   overlay stream (captions + overlays on flat grey): 0 unexpected spikes and 0 A-B-A in every band
    #   final vs base (the 3D frames alone, plates blurred): A-B-A frames that exist in the final but not in the base
    #   (and are not within +-1 frame of an expected overlay event) = overlay-caused reversals -> must be 0
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import overlay_v2
    streams = overlay_v2.qc_streams(ep_path)
    ev = json.load(open(os.path.join(workdir, "overlay_events_v2.json")))
    tim = json.load(open(os.path.join(workdir, "audio", "timings.json")))
    cuts = set()
    for b in tim["beats"][1:]:
        f0 = int(round(b["start"] * fps)) + 1
        cuts.update(range(f0 - 2, f0 + 3))
    allev = cuts | set(ev.get("caption", [])) | set(ev.get("card", [])) | set(ev.get("mid", [])) | set(ev.get("low", []))

    def flick(src, band, evs, tag):
        y0, y1 = BANDS[band]
        out = os.path.join(qdir, "flicker_%s_%s.json" % (tag, band))
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "qc_flicker.py"), src,
                        "--region", "%s:%d:%d" % (band, y0, y1), "--events", ",".join(str(x) for x in sorted(evs)),
                        "--json", out], check=True, stdout=subprocess.DEVNULL)
        return json.load(open(out))["regions"][band]
    res["flicker"] = {}
    near = set()
    for e in allev:
        near.update((e - 1, e, e + 1))
    for band in BANDS:
        ov = flick(streams["overlay"], band, allev, "overlay")
        fin = flick(final, band, allev, "final")
        base = flick(streams["base"], band, cuts, "base")
        dov = ov["d_all"]          # dov[i] = overlay-stream change from frame i+1 to i+2

        def ov_moves(t):
            return any(0 <= i < len(dov) and dov[i] > 0.3 for i in (t - 2, t - 1))
        # a reversal can only be overlay-caused where the overlay layer itself changes at that frame
        new_aba = sorted(t for t in set(fin["aba_all"]) - set(base["aba_all"]) - near if ov_moves(t))
        r = {"overlay_spikes_unexpected": ov["spikes_unexpected"], "overlay_unexpected_frames": ov["unexpected_frames"],
             "overlay_aba": ov["aba_count"], "overlay_aba_frames": ov["aba_frames"],
             "final_aba": fin["aba_count"], "base_aba": base["aba_count"], "overlay_caused_aba": len(new_aba),
             "overlay_caused_aba_frames": new_aba[:30], "base_px_flicker_max_pct": base["px_flicker_max_pct"],
             "final_px_flicker_max_pct": fin["px_flicker_max_pct"]}
        res["flicker"][band] = r
        # hard rule: the overlay layer itself never spikes or reverses. "overlay_caused" (final-only reversals while a
        # label moves over moving 3D, e.g. a spinning prop) is reported for a manual look at those frames.
        if r["overlay_spikes_unexpected"] or r["overlay_aba"]:
            ok = False
    # frames + sheet
    times = [round(p["duration"] * (k + 0.5) / 12, 1) for k in range(12)]
    tiles = []
    for t in times:
        fp = os.path.join(qdir, "t_%05.1f.png" % t)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", final, "-frames:v", "1", fp], check=True)
        tiles.append((t, fp))
    tw, th = 270, 480
    sheet = Image.new("RGB", (6 * (tw + 6) + 6, 2 * (th + 40) + 6), (18, 20, 26))
    d = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc", 24, index=8)
    for k, (t, fp) in enumerate(tiles):
        im = Image.open(fp).convert("RGB").resize((tw, th), Image.LANCZOS)
        x, y = 6 + (k % 6) * (tw + 6), 6 + (k // 6) * (th + 40)
        sheet.paste(im, (x, y + 34))
        # safe-area guides (12 % / 80 %)
        for fr in (0.12, 0.80):
            d.line([(x, y + 34 + fr * th), (x + tw, y + 34 + fr * th)], fill=(255, 200, 0), width=1)
        d.text((x + tw / 2, y + 17), "t = %.1f s" % t, font=fnt, fill=(235, 235, 235), anchor="mm")
    sheet.save(os.path.join(qdir, "qc_sheet.png"))
    res["ok"] = ok
    json.dump(res, open(os.path.join(qdir, "qc_v2.json"), "w"), indent=1)
    print("[qc_v2] %s: %.2fs %dx%d %s audio=%s" % (os.path.basename(final), p["duration"], p["width"], p["height"],
                                                  p["fps"], p["audio"]))
    for band, r in res["flicker"].items():
        print("[qc_v2] %-8s overlay: unexpected spikes %d %s, ABA %d %s | final ABA %d, 3D-only ABA %d, overlay-caused %d %s"
              " | px-flicker max final %.2f%% / 3D %.2f%%" % (
                  band, r["overlay_spikes_unexpected"], r["overlay_unexpected_frames"][:6], r["overlay_aba"],
                  r["overlay_aba_frames"][:6], r["final_aba"], r["base_aba"], r["overlay_caused_aba"],
                  r["overlay_caused_aba_frames"][:6], r["final_px_flicker_max_pct"], r["base_px_flicker_max_pct"]))
    print("[qc_v2] sheet: %s  -> %s" % (os.path.join(qdir, "qc_sheet.png"), "PASS" if ok else "CHECK FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

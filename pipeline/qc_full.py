"""Whole-video QC (Irfan, 23 Nov 2026: "QC is not just flicker — check the whole video for any issue").

Usage: .venv/bin/python pipeline/qc_full.py <episode.json> <final.mp4> [outdir]

Automatic checks (report -> <outdir>/qc_full.json + qc_full.md):
  - format: 1080x1920, 30 fps, audio present, duration 70-120 s, FB copy < 10 MB if present
  - black / frozen frames (ffmpeg blackdetect, freezedetect)
  - audio: integrated loudness ~ -14 LUFS, true clipping, clicks (sample jumps in near-silence),
    long pauses (> 0.75 s silence inside the narration), leading/trailing silence
  - spoken words vs script (faster-whisper on the final audio): missing/extra words, word error rate
Visual review material (a human/agent MUST look at every sheet):
  - <outdir>/full/sheet_XX.jpg: one frame every STEP seconds (default 2 s; Irfan 24 Nov: save tokens) of the WHOLE video, 15 frames per sheet, timestamps burned in,
    with 12 %/80 % safe-area guides. Check every frame: void/plain backgrounds, glitches, clipped or overlapping
    text, labels on wrong objects, wrong spelling, anything graphic/insensitive, visuals not matching the words.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import platform_cfg as PC  # cross-platform paths; macOS defaults = the old hard-coded values


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = sh([PC.ffprobe_exe(), "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of", "json", path])
    return json.loads(r.stdout)


def ff_filter(path, af=None, vf=None):
    cmd = [PC.ffmpeg_exe(), "-hide_banner", "-nostats", "-i", path]
    if vf:
        cmd += ["-vf", vf, "-an"]
    if af:
        cmd += ["-af", af, "-vn"]
    cmd += ["-f", "null", "-"]
    return sh(cmd).stderr


def audio_pcm(path, sr=24000):
    r = subprocess.run([PC.ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32), sr


def norm_words(s):
    return re.findall(r"[a-z0-9']+", s.lower().replace("’", "'"))


def wer(ref, hyp):
    d = np.zeros((len(ref) + 1, len(hyp) + 1), dtype=np.int32)
    d[:, 0] = np.arange(len(ref) + 1)
    d[0, :] = np.arange(len(hyp) + 1)
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    return d[-1, -1] / max(1, len(ref))


def main(ep_path, mp4, outdir=None):
    ep = json.load(open(ep_path))
    outdir = outdir or os.path.join(os.path.dirname(mp4), ep.get("slug", os.path.splitext(os.path.basename(mp4))[0].replace(" ", "-")), "qc")
    os.makedirs(os.path.join(outdir, "full"), exist_ok=True)
    issues, info = [], {}

    # --- format
    p = probe(mp4)
    dur = float(p["format"]["duration"])
    v = [s for s in p["streams"] if s["codec_type"] == "video"][0]
    has_a = any(s["codec_type"] == "audio" for s in p["streams"])
    info.update(duration=round(dur, 2), size=f'{v["width"]}x{v["height"]}', fps=v["r_frame_rate"], audio=has_a)
    if (v["width"], v["height"]) != (1080, 1920): issues.append("resolution is not 1080x1920")
    if v["r_frame_rate"] not in ("30/1",): issues.append("fps is not 30")
    if not has_a: issues.append("no audio stream")
    if not 70 <= dur <= 120: issues.append("duration %.1f s outside 70-120 s" % dur)
    fb = mp4[:-4] + " fb.mp4"
    if os.path.exists(fb):
        info["fb_mb"] = round(os.path.getsize(fb) / 1e6, 2)
        if os.path.getsize(fb) >= 10e6: issues.append("FB copy is not under 10 MB")

    # --- black / frozen frames
    blk = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", ff_filter(mp4, vf="blackdetect=d=0.15:pix_th=0.08"))
    if blk: issues.append("black frames at " + ", ".join("%s-%s s" % b for b in blk))
    frz = re.findall(r"freeze_start: ([\d.]+)[\s\S]*?freeze_duration: ([\d.]+)", ff_filter(mp4, vf="freezedetect=n=0.001:d=1.5"))
    if frz: issues.append("frozen picture: " + ", ".join("%s s for %s s" % f for f in frz))

    # --- audio
    lo = ff_filter(mp4, af="ebur128=peak=true")
    m = (re.findall(r"I:\s+(-?[\d.]+) LUFS", lo) or [None])[-1]; tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)
    if m:
        info["lufs"] = float(m)
        if abs(info["lufs"] + 14) > 1: issues.append("loudness %.1f LUFS (target -14)" % info["lufs"])
    if tp:
        info["true_peak_db"] = float(tp[-1])
        if info["true_peak_db"] > -0.5: issues.append("audio true peak %.1f dBFS (clipping risk)" % info["true_peak_db"])
    x, sr = audio_pcm(mp4)
    win = int(sr * 0.01)
    env = np.array([np.abs(x[i:i + win]).max() if i + win <= len(x) else 0 for i in range(0, len(x), win)])
    quiet = env < 600
    # long pauses inside narration
    speech = np.where(~quiet)[0]
    pauses = []
    if len(speech):
        run = 0
        for k in range(speech[0], speech[-1]):
            run = run + 1 if quiet[k] else 0
            if run == 76:
                pauses.append(round((k - 75) / 100, 2))
        lead, tail = speech[0] / 100, (len(env) - speech[-1]) / 100
        info.update(lead_silence=lead, tail_silence=round(tail, 2))
        if lead > 0.5: issues.append("%.2f s silence before first word" % lead)
    if pauses: issues.append("pauses > 0.75 s at " + ", ".join("%s s" % t for t in pauses))
    # clicks: big sample-to-sample jump while the surrounding 10 ms is otherwise quiet
    dx = np.abs(np.diff(x))
    clicks = []
    for i in np.where(dx > 6000)[0]:
        k = i // win
        if 0 < k < len(env) - 1 and env[k - 1] < 600 and env[k + 1] < 600:
            t = round(i / sr, 2)
            if clicks and t - clicks[-1][0] <= 0.2:
                continue
            # a burst followed by speech within 150 ms = TTS mouth/lip noise before a word (minor, info only)
            near_speech = (env[k + 2:k + 16] > 5000).any()
            clicks.append((t, near_speech))
    real = [t for t, ns in clicks if not ns]
    info["mouth_noise_before_words"] = [t for t, ns in clicks if ns]
    if real: issues.append("clicks at " + ", ".join("%s s" % t for t in real[:20]))

    # --- spoken words vs script
    try:
        from faster_whisper import WhisperModel
        wav = os.path.join(outdir, "final_audio.wav")
        subprocess.run([PC.ffmpeg_exe(), "-v", "error", "-y", "-i", mp4, "-ac", "1", "-ar", "16000", wav], check=True)
        segs, _ = WhisperModel("base.en", device="cpu", compute_type="int8").transcribe(wav)
        heard = " ".join(s.text for s in segs)
        script = " ".join(b["text"] for b in ep["beats"])
        w = wer(norm_words(script), norm_words(heard))
        info["word_error_rate"] = round(w, 3)
        open(os.path.join(outdir, "heard.txt"), "w").write(heard)
        if w > 0.12: issues.append("spoken audio differs from script (WER %.0f%%) — read qc/heard.txt" % (w * 100))
    except Exception as e:  # noqa
        issues.append("whisper check failed: %s" % e)

    # --- full-video contact sheets: 1 frame every STEP s (env QC_STEP, default 2)
    STEP = float(os.environ.get("QC_STEP", "2"))
    n = int(dur)
    fdir = os.path.join(outdir, "full")
    for f in os.listdir(fdir):
        os.remove(os.path.join(fdir, f))
    # (this ffmpeg build has no drawtext -> label/tile with PIL)
    from PIL import Image, ImageDraw, ImageFont
    subprocess.run([PC.ffmpeg_exe(), "-v", "error", "-y", "-i", mp4, "-vf", "fps=1/%g,scale=360:640" % STEP, "-q:v", "3",
                    os.path.join(fdir, "f_%04d.jpg")], check=True)
    frames = sorted(f for f in os.listdir(fdir) if f.startswith("f_"))
    try:
        font = ImageFont.truetype(PC.font_path("SUB_FONT")[0], 26)
    except Exception:  # noqa
        font = ImageFont.load_default()
    per, cols, W, H, pad = 15, 5, 360, 640, 6
    sheets = []
    for s in range(0, len(frames), per):
        chunk = frames[s:s + per]
        sheet = Image.new("RGB", (cols * (W + pad) + pad, 3 * (H + pad) + pad), "black")
        for k, f in enumerate(chunk):
            im = Image.open(os.path.join(fdir, f)).convert("RGB")
            d = ImageDraw.Draw(im)
            for g in (0.12, 0.80):
                d.line([(0, int(H * g)), (W, int(H * g))], fill=(255, 220, 0), width=2)
            t = (s + k) * STEP + STEP / 2
            d.rectangle([0, 0, 92, 34], fill=(0, 0, 0))
            d.text((6, 4), "%d:%02d" % (t // 60, t % 60), font=font, fill=(255, 220, 0))
            sheet.paste(im, (pad + (k % cols) * (W + pad), pad + (k // cols) * (H + pad)))
        name = "sheet_%02d.jpg" % (s // per + 1)
        sheet.save(os.path.join(fdir, name), quality=85)
        sheets.append(name)
    for f in frames:
        os.remove(os.path.join(fdir, f))
    info["sheets"] = [os.path.join(fdir, s) for s in sheets]

    rep = {"video": mp4, "info": info, "issues": issues, "pass_auto": not issues}
    json.dump(rep, open(os.path.join(outdir, "qc_full.json"), "w"), indent=1)
    md = ["# Full QC: %s" % os.path.basename(mp4), "", "Auto checks: %s" % ("PASS" if not issues else "ISSUES"), ""]
    md += ["- " + i for i in issues] or ["- none"]
    md += ["", "Info: " + json.dumps(info), "",
           "MANUAL (required): open every sheet in qc/full/ (%d sheets, 1 frame/%gs) and check each frame." % (len(sheets), STEP)]
    open(os.path.join(outdir, "qc_full.md"), "w").write("\n".join(md))
    print("\n".join(md))
    return rep


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2] if len(a) > 2 else None)

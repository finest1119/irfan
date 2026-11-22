"""Orchestrator: episode.json -> output/<keyword>.mp4 (+ .post.md).

Usage:
  .venv/bin/python pipeline/make_episode.py episodes/<id>/episode.json [--steps tts,captions,render,assemble,fb,post]
        [--parallel N] [--only-shot K]

Steps (each is resumable / cached):
  tts       Gemini TTS per beat -> WORKDIR/audio/voice.wav + timings.json      (pipeline/tts.py)
  captions  faster-whisper timings + script text -> captions.json + PNG stream (pipeline/captions.py)
  render    Blender, one headless process per shot, N in parallel -> WORKDIR/frames/NN_<beat>/
  assemble  ffmpeg: frames -> shot mp4s -> concat -> caption overlay -> loudnorm voice -> final mp4
  fb        output/<keyword> fb.mp4: HEVC (hvc1) upload copy under 10,000,000 bytes (bitrate from duration)
  post      WORKDIR/../<keyword>.post.md with title, caption, hashtags, engagement comment, checklist, sources

WORKDIR = output/<slug>/ ; final = output/<keyword>.mp4
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = os.path.join(ROOT, ".venv", "bin", "python")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    print("[make_episode %s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        raise SystemExit("command failed (%d): %s" % (r.returncode, " ".join(cmd[:6])))
    return r


def step_tts(ep_path, workdir):
    r = subprocess.run([PY, "-W", "ignore", os.path.join(ROOT, "pipeline", "tts.py"), ep_path, workdir])
    if r.returncode == 2:
        raise SystemExit("TTS stopped on auth/billing error; not continuing.")
    if r.returncode != 0:
        raise SystemExit("TTS failed")


def step_captions(ep_path, workdir):
    run([PY, "-W", "ignore", os.path.join(ROOT, "pipeline", "captions.py"), ep_path, workdir])


def render_shot(ep_path, workdir, idx, beat_id, nframes):
    name = "%02d_%s" % (idx, beat_id)
    fdir = os.path.join(workdir, "frames", name)
    if os.path.isdir(fdir) and len([f for f in os.listdir(fdir) if f.endswith(".png")]) >= nframes:
        log("shot %s already rendered" % name)
        return 0.0
    os.makedirs(os.path.join(workdir, "logs"), exist_ok=True)
    t0 = time.time()
    with open(os.path.join(workdir, "logs", "render_%s.log" % name), "w") as lf:
        r = subprocess.run([BLENDER, "-b", "--factory-startup", "-P",
                            os.path.join(ROOT, "pipeline", "blender", "render_episode.py"),
                            "--", ep_path, workdir, str(idx)], stdout=lf, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    if r.returncode != 0:
        raise RuntimeError("Blender failed on shot %s (see logs/render_%s.log)" % (name, name))
    log("shot %s rendered in %.0fs" % (name, dt))
    return dt


def step_render(ep_path, workdir, parallel, only=None):
    ep = json.load(open(ep_path))
    tim = json.load(open(os.path.join(workdir, "audio", "timings.json")))["beats"]
    fps = ep.get("render", {}).get("fps", 30)
    jobs = []
    for i, (b, t) in enumerate(zip(ep["beats"], tim)):
        if only is not None and i != only:
            continue
        jobs.append((i, b["id"], int(round(t["duration"] * fps))))
    # longest shots first for better packing
    jobs.sort(key=lambda j: -j[2])
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        list(ex.map(lambda j: render_shot(ep_path, workdir, *j), jobs))
    total = time.time() - t0
    log("render wall time %.0fs" % total)
    stats_p = os.path.join(workdir, "render_stats.json")
    json.dump({"render_wall_seconds": round(total, 1), "parallel": parallel}, open(stats_p, "w"))


def measure_lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    lines = [l for l in r.stderr.splitlines() if l.strip().startswith("I:")]
    return float(lines[-1].split()[1])


def step_assemble(ep_path, workdir, final_path):
    ep = json.load(open(ep_path))
    tim = json.load(open(os.path.join(workdir, "audio", "timings.json")))
    fps = ep.get("render", {}).get("fps", 30)
    sdir = os.path.join(workdir, "segments")
    os.makedirs(sdir, exist_ok=True)
    seg_list = []
    for i, (b, t) in enumerate(zip(ep["beats"], tim["beats"])):
        name = "%02d_%s" % (i, b["id"])
        out = os.path.join(sdir, name + ".mp4")
        nframes = int(round(t["duration"] * fps))
        run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", os.path.join(workdir, "frames", name, "%04d.png"),
             "-frames:v", str(nframes), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
             "-pix_fmt", "yuv420p", out])
        seg_list.append(out)
    concat_txt = os.path.join(sdir, "concat.txt")
    with open(concat_txt, "w") as f:
        for s in seg_list:
            f.write("file '%s'\n" % s.replace("'", "'\\''"))
    visuals = os.path.join(workdir, "visuals.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_txt,
         "-c", "copy", visuals])
    # voice loudness normalise to about -14 LUFS. The TTS output has inter-sample peaks above
    # 0 dBTP, so plain linear loudnorm cannot reach -14; use gain + true-peak-ish limiter instead,
    # re-measure and correct once.
    voice_raw = os.path.join(workdir, "audio", "voice.wav")
    voice = os.path.join(workdir, "audio", "voice_norm.wav")
    gain = -14.0 - measure_lufs(voice_raw)
    for _ in range(3):
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice_raw, "-af",
             "aresample=48000,volume=%.2fdB,alimiter=limit=0.82:attack=1:release=60:level=false" % gain,
             "-c:a", "pcm_s16le", voice])
        got = measure_lufs(voice)
        log("voice loudness %.2f LUFS (gain %.2f dB)" % (got, gain))
        if abs(got + 14.0) <= 0.3:
            break
        gain += -14.0 - got
    af = "anull"
    music = ep.get("music")
    cap_list = os.path.join(workdir, "captions", "list.ffconcat")
    total = tim["total"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", visuals,
           "-f", "concat", "-safe", "0", "-i", cap_list,
           "-i", voice]
    filt = "[1:v]format=rgba[cap];[0:v][cap]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v];[2:a]%s[a]" % af
    if music:
        # optional bed: music file path relative to repo, ducked to ~-28 LUFS under the voice
        cmd += ["-stream_loop", "-1", "-i", os.path.join(ROOT, music)]
        filt = filt.replace("[a]", "[vo]") + ";[3:a]loudnorm=I=-30,aresample=48000[mu];[vo][mu]amix=inputs=2:duration=first:normalize=0[a]"
    cmd += ["-filter_complex", filt, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-t", "%.3f" % total, "-movflags", "+faststart", final_path]
    run(cmd)
    log("wrote %s" % final_path)


def step_fb(final_path, fb_path, limit=10_000_000, target=9_300_000):
    """Facebook upload copy: HEVC (hvc1) + mono AAC, sized under `limit` bytes. The video bitrate is
    computed from the duration; if the file still comes out too big it is re-encoded 15% lower."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                final_path], capture_output=True, text=True).stdout.strip())
    a_kbps = 80
    v_kbps = int((target * 8 / dur) / 1000 - a_kbps - 20)   # ~20 kb/s container overhead
    for _ in range(4):
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", final_path, "-c:v", "libx265", "-preset", "slow",
             "-b:v", "%dk" % v_kbps, "-maxrate", "%dk" % (2 * v_kbps), "-bufsize", "%dk" % (4 * v_kbps),
             "-x265-params", "log-level=error", "-tag:v", "hvc1", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "%dk" % a_kbps, "-ac", "1", "-movflags", "+faststart", fb_path])
        size = os.path.getsize(fb_path)
        log("fb copy %.2f MB at %d kb/s video" % (size / 1e6, v_kbps))
        if size < limit:
            return size
        v_kbps = int(v_kbps * 0.85)
    raise SystemExit("fb copy still over %d bytes" % limit)


def step_post(ep_path, post_path):
    ep = json.load(open(ep_path))
    comment = ep.get("engagement_comment")
    lines = ["# %s" % ep["title"], "",
             "**Keyword / filename:** %s" % ep["keyword"], "",
             "## Facebook caption", "", ep["fb_caption"], "", " ".join(ep["hashtags"]), ""]
    if comment:
        lines += ["## Engagement comment (the Page posts this under the reel)", "", comment, ""]
    lines += ["## Posting checklist", "",
              "- Upload `%s fb.mp4` (HEVC copy under 10 MB)" % ep["keyword"],
              "- Audience: Public", "- AI label: ON (AI voiceover, AI-generated/3D assets)",
              "- Hashtags pasted at the end of the caption",
              "- Engagement comment posted by the Page right after publishing" if comment else
              "- (no engagement comment set in episode.json)",
              "- Re-check the hook facts on posting day.", "",
              "## Sources", ""]
    lines += ["- %s" % s for s in ep.get("sources", [])]
    lines += ["", "## Voiceover script", ""]
    lines += [b["text"] for b in ep["beats"]]
    open(post_path, "w").write("\n".join(lines) + "\n")
    log("wrote %s" % post_path)


def main():
    args = sys.argv[1:]
    ep_path = os.path.abspath(args[0])

    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default

    ep = json.load(open(ep_path))
    out_root = os.path.join(ROOT, "output")
    workdir = os.path.join(out_root, ep["slug"])
    os.makedirs(workdir, exist_ok=True)
    final_path = os.path.join(out_root, ep["keyword"] + ".mp4")
    post_path = os.path.join(out_root, ep["keyword"] + ".post.md")
    fb_path = os.path.join(out_root, ep["keyword"] + " fb.mp4")
    steps = opt("--steps", "tts,captions,render,assemble,fb,post").split(",")
    parallel = int(opt("--parallel", ep.get("render", {}).get("parallel", 3)))
    only = opt("--only-shot")
    t0 = time.time()
    if "tts" in steps:
        log("TTS"); step_tts(ep_path, workdir)
    if "captions" in steps:
        log("captions"); step_captions(ep_path, workdir)
    if "render" in steps:
        log("render (parallel=%d)" % parallel); step_render(ep_path, workdir, parallel, int(only) if only else None)
    if "assemble" in steps:
        log("assemble"); step_assemble(ep_path, workdir, final_path)
    if "fb" in steps:
        log("fb copy"); step_fb(final_path, fb_path)
    if "post" in steps:
        step_post(ep_path, post_path)
    log("done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()

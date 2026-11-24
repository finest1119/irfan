"""Write SYNTHETIC audio/timings.json + captions.json for a one-shot episode before any TTS exists.

Estimates word times from the beat text at a words-per-minute rate (default 175, the Build #1 script target), with
small pauses after commas and sentence ends and `pause_between_beats` between beats, in exactly the schema
pipeline/tts.py + pipeline/captions.py write. Both files carry "synthetic": true. Use only for camera-plan tests,
previews and the 20 s test; the real TTS/captions step overwrites them.

Usage:
  python page2/tools/synth_timings.py page2/episodes/build-01/episode.json page2/episodes/build-01/work [--wpm 175]
"""
import argparse
import json
import re
from pathlib import Path


def norm(w):
    w = w.lower().replace("-", "")
    return re.sub(r"[^a-z0-9]", "", w)


def synth(episode, wpm=175.0, pause=None):
    pause = episode.get("tts", {}).get("pause_between_beats", 0.3) if pause is None else pause
    spw = 60.0 / wpm
    t = 0.15
    beats, words = [], []
    for k, b in enumerate(episode["beats"]):
        toks = b["text"].split()
        avg = sum(len(norm(x)) or 1 for x in toks) / max(1, len(toks))
        s0 = t
        for tok in toks:
            d = spw * (0.55 + 0.45 * (len(norm(tok)) or 1) / avg)
            words.append({"word": tok, "norm": norm(tok), "start": round(t, 3), "end": round(t + d * 0.92, 3),
                          "beat": b["id"]})
            t += d
            if re.search(r"[.!?][\"')\]]*$", tok):
                t += 0.22
            elif tok.endswith((",", ":", ";")):
                t += 0.1
        beats.append({"id": b["id"], "speech_start": round(s0, 3), "speech_end": round(t, 3)})
        t += pause
    total = round(t + 0.4, 3)
    for k, tm in enumerate(beats):
        tm["start"] = 0.0 if k == 0 else tm["speech_start"]
        tm["end"] = beats[k + 1]["speech_start"] if k + 1 < len(beats) else total
        tm["duration"] = round(tm["end"] - tm["start"], 3)
    return {"total": total, "beats": beats, "synthetic": True, "wpm": wpm}, \
        {"words": words, "chunks": [], "alignment": [], "synthetic": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("workdir")
    ap.add_argument("--wpm", type=float, default=175.0)
    ap.add_argument("--force", action="store_true", help="overwrite REAL (non-synthetic) timings too")
    a = ap.parse_args()
    ep = json.loads(Path(a.episode).read_text(encoding="utf-8"))
    wd = Path(a.workdir)
    tp = wd / "audio" / "timings.json"
    if tp.exists() and not a.force:
        old = json.loads(tp.read_text(encoding="utf-8"))
        if not old.get("synthetic"):
            raise SystemExit("refusing to overwrite real TTS timings %s (use --force)" % tp)
    tim, cap = synth(ep, a.wpm)
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(json.dumps(tim, indent=1), encoding="utf-8")
    (wd / "captions.json").write_text(json.dumps(cap, indent=1), encoding="utf-8")
    print("synthetic timings: %d beats, %d words, %.2f s -> %s" % (len(tim["beats"]), len(cap["words"]), tim["total"], wd))


if __name__ == "__main__":
    main()

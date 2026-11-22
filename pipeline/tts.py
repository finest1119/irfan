"""Gemini TTS: one call per beat -> beat WAVs + concatenated voice.wav + timings.json.

Usage: .venv/bin/python pipeline/tts.py EPISODE_JSON WORKDIR [--only BEAT_ID] [--force]

Writes into WORKDIR/audio/:
  beat_<id>.wav     raw TTS for each beat (cached; delete or --force to redo)
  voice.wav         all beats joined with `pause_between_beats` seconds of silence
  timings.json      [{id, start, end, duration}] in seconds on the voice.wav timeline
  usage.json        token usage per beat (for cost estimate)

The GEMINI_API_KEY is loaded from the repo .env via python-dotenv and is never printed.
"""
import json
import os
import sys
import time
import wave
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RATE, WIDTH, CHANNELS = 24000, 2, 1


class AuthOrBillingError(RuntimeError):
    pass


def _client():
    from dotenv import load_dotenv
    from google import genai

    load_dotenv(os.path.join(ROOT, ".env"))
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise AuthOrBillingError("GEMINI_API_KEY missing from .env")
    return genai.Client(api_key=key)


def _is_auth_error(exc):
    msg = str(exc).lower()
    code = getattr(exc, "code", None)
    return code in (401, 403, 429) and any(
        w in msg for w in ("api key", "permission", "billing", "quota", "unauthenticated", "denied", "exhausted")
    ) or any(w in msg for w in ("api_key_invalid", "billing", "permission_denied", "unauthenticated"))


def synth(client, model, voice, prompt):
    from google.genai import types

    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    pcm = b""
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            pcm += part.inline_data.data
    if not pcm:
        raise RuntimeError("TTS returned no audio")
    um = resp.usage_metadata
    usage = {
        "prompt_tokens": getattr(um, "prompt_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "total_tokens": getattr(um, "total_token_count", None),
    }
    return pcm, usage


def build_prompt(t, text):
    """Director-notes format: the model speaks only the TRANSCRIPT section.
    (A plain 'Say in a ... tone:' prefix gets read aloud by gemini-3.8-flash-tts.)"""
    return "### DIRECTOR'S NOTES\n%s\n\n### TRANSCRIPT\n%s" % (t["director_notes"].strip(), text.strip())


def synth_with_fallback(client, t, model, prompt, beat_id):
    models = [model] + ([t["fallback_model"]] if t.get("fallback_model") and t["fallback_model"] != model else [])
    last = None
    for m in models:
        try:
            pcm, usage = synth(client, m, t["voice"], prompt)
            return pcm, usage, m
        except Exception as e:  # noqa
            if _is_auth_error(e):
                raise AuthOrBillingError("TTS auth/billing error (%s): %s" % (m, str(e)[:300]))
            print("  TTS error on %s with %s: %s" % (beat_id, m, str(e)[:200]))
            last = e
            time.sleep(2)
    raise last


_WHISPER = None


def _words(s):
    import re
    return re.findall(r"[a-z0-9']+", s.lower())


def spoken_matches(wav_path, text):
    """True if whisper's transcript is not much longer than the script (no instructions read aloud)."""
    global _WHISPER
    from faster_whisper import WhisperModel

    _WHISPER = _WHISPER or WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = _WHISPER.transcribe(wav_path)
    heard = " ".join(s.text for s in segs).strip()
    hw, sw = _words(heard), _words(text)
    ok = len(hw) <= len(sw) * 1.25 + 2 and not any(w in hw[:6] for w in ("director", "style", "transcript", "notes"))
    return ok, heard


def write_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(WIDTH)
        w.setframerate(RATE)
        w.writeframes(pcm)


def read_pcm(path):
    with wave.open(path, "rb") as w:
        return w.readframes(w.getnframes())


def trim_silence(pcm, thresh=300, keep=0.06):
    """Trim leading/trailing near-silence (16-bit mono), keeping `keep` s of padding."""
    import array

    a = array.array("h", pcm)
    n = len(a)
    i, j = 0, n - 1
    while i < n and abs(a[i]) < thresh:
        i += 1
    while j > i and abs(a[j]) < thresh:
        j -= 1
    pad = int(keep * RATE)
    i, j = max(0, i - pad), min(n, j + pad)
    return a[i:j].tobytes()


def run(episode_path, workdir, only=None, force=False):
    ep = json.load(open(episode_path))
    t = ep["tts"]
    adir = os.path.join(workdir, "audio")
    os.makedirs(adir, exist_ok=True)
    usage_path = os.path.join(adir, "usage.json")
    usage_all = json.load(open(usage_path)) if os.path.exists(usage_path) else {}
    client = None
    model_used = t["model"]
    for beat in ep["beats"]:
        if only and beat["id"] != only:
            continue
        out = os.path.join(adir, "beat_%s.wav" % beat["id"])
        if os.path.exists(out) and not force:
            continue
        client = client or _client()
        prompt = build_prompt(t, beat["text"])
        pcm, usage = None, None
        for _try in range(3):
            pcm, usage, model_used = synth_with_fallback(client, t, model_used, prompt, beat["id"])
            pcm = trim_silence(pcm)
            write_wav(out, pcm)
            # guard: TTS sometimes speaks the director notes aloud -> verify with whisper
            ok, heard = spoken_matches(out, beat["text"])
            if ok:
                break
            print("  beat %s: transcript mismatch, retrying (heard: %s...)" % (beat["id"], heard[:80]))
        else:
            os.remove(out)
            raise RuntimeError("TTS for beat %s kept speaking extra text" % beat["id"])
        usage["model"] = model_used
        usage["seconds"] = round(len(pcm) / (RATE * WIDTH), 3)
        usage_all[beat["id"]] = usage
        json.dump(usage_all, open(usage_path, "w"), indent=2)
        print("  beat %-10s %.2fs (%s)" % (beat["id"], usage["seconds"], model_used))

    if only:
        return
    # join
    gap = b"\x00\x00" * int(t.get("pause_between_beats", 0.3) * RATE)
    lead = b"\x00\x00" * int(0.15 * RATE)
    joined, timings, cur = lead, [], len(lead)
    for k, beat in enumerate(ep["beats"]):
        pcm = read_pcm(os.path.join(adir, "beat_%s.wav" % beat["id"]))
        start = cur / (RATE * WIDTH)
        joined += pcm
        cur += len(pcm)
        tail = gap if k < len(ep["beats"]) - 1 else b"\x00\x00" * int(0.8 * RATE)
        joined += tail
        cur += len(tail)
        timings.append({"id": beat["id"], "speech_start": round(start, 3),
                        "speech_end": round(start + len(pcm) / (RATE * WIDTH), 3)})
    # shot boundaries: each shot runs from its speech start (first: 0) to next speech start
    total = cur / (RATE * WIDTH)
    for k, tm in enumerate(timings):
        tm["start"] = 0.0 if k == 0 else tm["speech_start"]
        tm["end"] = timings[k + 1]["speech_start"] if k + 1 < len(timings) else round(total, 3)
        tm["duration"] = round(tm["end"] - tm["start"], 3)
    write_wav(os.path.join(adir, "voice.wav"), joined)
    json.dump({"total": round(total, 3), "beats": timings}, open(os.path.join(adir, "timings.json"), "w"), indent=2)
    print("voice.wav total %.2fs" % total)
    return total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if only:
        args.remove(only)
    try:
        run(args[0], args[1], only=only, force="--force" in sys.argv)
    except AuthOrBillingError as e:
        print("STOP:", e)
        sys.exit(2)

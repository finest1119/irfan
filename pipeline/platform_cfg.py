"""Cross-platform paths for the pipeline (Mac = What Just Happened, Windows laptop = Self-Made Engineer).

Every value is looked up in this order (first hit wins):
  1. environment variable            e.g.  set BLENDER_EXE=D:\\Blender\\blender.exe
  2. config_local.json in the repo root (gitignored)   {"BLENDER_EXE": "...", "OVERLAY_FONT_SET": "montserrat"}
  3. .env in the repo root (only the keys below are read; secrets in it are never touched)
  4. the per-OS default below.  macOS defaults = exactly the paths that were hard-coded before (WJH output unchanged).

Keys
  BLENDER_EXE          Blender binary
  FFMPEG_EXE           ffmpeg  (default "ffmpeg" = from PATH)
  FFPROBE_EXE          ffprobe (default "ffprobe")
  OVERLAY_FONT_SET     "avenir" (macOS default) or "montserrat" (bundled OFL font in assets/fonts/; default elsewhere)
  OVERLAY_FONT_BOLD    overlay/caption fonts, "path" or "path#ttc_index" (relative paths = repo root);
  OVERLAY_FONT_HEAVY     they override OVERLAY_FONT_SET. Avenir Next.ttc: Bold #0, Heavy #8, Demi Bold #2.
  OVERLAY_FONT_DEMI
  CAPTION_FONT         v1 burned-in captions (captions.py)                 - Mac: Arial Black
  SUB_FONT             QC contact-sheet labels (qc_full.py)                - Mac: Arial Bold
  NUMBER_FONT          condensed numerals painted into v2 test textures    - Mac: DIN Condensed Bold
  SCHEDULE_TZ          IANA zone for tools/fb_schedule_reel.py slot times (default: fixed UTC+8, Malaysia)

Stdlib only; safe to import from any pipeline script (not from inside Blender).
"""
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
FONTS_DIR = os.path.join(ROOT, "assets", "fonts")

_AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
_MONT_B = os.path.join(FONTS_DIR, "Montserrat-Bold.ttf")
_MONT_XB = os.path.join(FONTS_DIR, "Montserrat-ExtraBold.ttf")

FONT_SETS = {
    # role: "path#index"
    "avenir": {"BOLD": _AVENIR + "#0", "HEAVY": _AVENIR + "#8", "DEMI": _AVENIR + "#2"},
    # Montserrat has no Demi weight bundled -> Bold; Heavy -> ExtraBold
    "montserrat": {"BOLD": _MONT_B, "HEAVY": _MONT_XB, "DEMI": _MONT_B},
}

if IS_MAC:
    _DEFAULTS = {
        "BLENDER_EXE": "/Applications/Blender.app/Contents/MacOS/Blender",
        "OVERLAY_FONT_SET": "avenir",
        "CAPTION_FONT": "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "SUB_FONT": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "NUMBER_FONT": "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
    }
elif IS_WIN:
    _DEFAULTS = {
        "BLENDER_EXE": r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe",
        "OVERLAY_FONT_SET": "montserrat",
        "CAPTION_FONT": _MONT_XB,
        "SUB_FONT": _MONT_B,
        "NUMBER_FONT": _MONT_XB,
    }
else:  # Linux / other
    _DEFAULTS = {
        "BLENDER_EXE": "blender",
        "OVERLAY_FONT_SET": "montserrat",
        "CAPTION_FONT": _MONT_XB,
        "SUB_FONT": _MONT_B,
        "NUMBER_FONT": _MONT_XB,
    }
_DEFAULTS.update({"FFMPEG_EXE": "ffmpeg", "FFPROBE_EXE": "ffprobe", "SCHEDULE_TZ": ""})

KEYS = ("BLENDER_EXE", "FFMPEG_EXE", "FFPROBE_EXE", "OVERLAY_FONT_SET", "OVERLAY_FONT_BOLD", "OVERLAY_FONT_HEAVY",
        "OVERLAY_FONT_DEMI", "CAPTION_FONT", "SUB_FONT", "NUMBER_FONT", "SCHEDULE_TZ")

_cache = {}


def _read_local_json():
    p = os.path.join(ROOT, "config_local.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    return {k: str(v) for k, v in d.items() if k in KEYS and v not in (None, "")}


def _read_dotenv():
    """Minimal KEY=VALUE reader; only KEYS are kept (FB / Gemini secrets are ignored, never returned)."""
    p = os.path.join(ROOT, ".env")
    out = {}
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k.startswith("export "):
                k = k[7:].strip()
            if k not in KEYS:
                continue
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            if v:
                out[k] = v
    return out


def get(key):
    if key not in KEYS:
        raise KeyError(key)
    v = os.environ.get(key)
    if v:
        return v
    if "_local" not in _cache:
        _cache["_local"] = _read_local_json()
        _cache["_env"] = _read_dotenv()
    if key in _cache["_local"]:
        return _cache["_local"][key]
    if key in _cache["_env"]:
        return _cache["_env"][key]
    return _DEFAULTS.get(key)


def _abs(p):
    """Relative paths in config are relative to the repo root; absolute paths are returned unchanged."""
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _split_spec(spec):
    """'path#3' -> (path, 3); 'path' -> (path, 0)."""
    if "#" in spec:
        p, i = spec.rsplit("#", 1)
        if i.isdigit():
            return _abs(p), int(i)
    return _abs(spec), 0


def blender_exe():
    return get("BLENDER_EXE")


def ffmpeg_exe():
    return get("FFMPEG_EXE")


def ffprobe_exe():
    return get("FFPROBE_EXE")


def venv_python():
    """The repo venv's interpreter: .venv/bin/python (macOS/Linux, unchanged) or .venv\\Scripts\\python.exe."""
    if IS_WIN:
        p = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
        return p if os.path.exists(p) else sys.executable
    return os.path.join(ROOT, ".venv", "bin", "python")


def overlay_font_role(role):
    """role: BOLD / HEAVY / DEMI -> (path, ttc_index)."""
    role = role.upper()
    spec = get("OVERLAY_FONT_" + role)
    if not spec:
        fs = get("OVERLAY_FONT_SET").lower()
        if fs not in FONT_SETS:
            raise SystemExit("OVERLAY_FONT_SET must be one of %s, got %r" % (sorted(FONT_SETS), fs))
        spec = FONT_SETS[fs][role]
    return _split_spec(spec)


_AVENIR_IDX = {0: "BOLD", 8: "HEAVY", 2: "DEMI"}


def overlay_font(idx=0):
    """Map the Avenir Next .ttc index the overlay code was written against (0 Bold, 8 Heavy, 2 Demi Bold)
    to (path, index) for the configured font. Any other index keeps the Bold font file and, if that file is
    a .ttc, the same index (so the macOS/Avenir result is exactly ImageFont.truetype(AVENIR, size, index=idx))."""
    role = _AVENIR_IDX.get(idx)
    if role:
        return overlay_font_role(role)
    path, _ = overlay_font_role("BOLD")
    return path, (idx if path.lower().endswith(".ttc") else 0)


def font_path(key):
    """CAPTION_FONT / SUB_FONT / NUMBER_FONT -> (path, ttc_index)."""
    return _split_spec(get(key))


def schedule_tz():
    """tzinfo for slot times in tools/fb_schedule_reel.py: SCHEDULE_TZ (IANA name, e.g. America/New_York; Windows
    needs `pip install tzdata`) or, by default, the fixed UTC+8 Malaysia offset used before."""
    import datetime as dt
    name = get("SCHEDULE_TZ")
    if not name:
        return dt.timezone(dt.timedelta(hours=8))
    from zoneinfo import ZoneInfo
    return ZoneInfo(name)


if __name__ == "__main__":  # python pipeline/platform_cfg.py  -> show the resolved (non-secret) settings
    for k in KEYS:
        print("%-18s %s" % (k, get(k)))
    for r in ("BOLD", "HEAVY", "DEMI"):
        print("overlay %-10s %s" % (r, overlay_font_role(r)))
    print("venv python        %s" % venv_python())

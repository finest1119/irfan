"""Download the CC0 3D assets used by the Page 2 "Self-Made Engineer" world (Poly Haven models/textures, Kenney kits),
as listed in assets/cc0/manifest.json. Files that already exist with the right sha256 are skipped. Kenney zips are
extracted next to the zip. Stdlib only (urllib + zipfile), pathlib paths, works on Windows and macOS.

Manifest `url` forms:
  https://...              direct file (Poly Haven dl.polyhaven.org)
  kenney-signed:<slug>     kenney.nl/assets/<slug> -> "Continue without donating" signed link (free, no login)

Usage:
  python tools/fetch_cc0.py                    # fetch everything missing/changed
  python tools/fetch_cc0.py --check            # report only (exit 1 if anything is missing)
  python tools/fetch_cc0.py --only NAME[,NAME] # entries whose name or file name contains NAME
  python tools/fetch_cc0.py --record           # write sha256/size of files on disk into entries that have none
  python tools/fetch_cc0.py --dest DIR         # base folder instead of the repo root (testing)
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "cc0" / "manifest.json"
UA = "Mozilla/5.0 (asset-fetcher/1.0; python urllib)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def resolve_url(url):
    """Return (opener, direct_url). Kenney needs a fresh signed link from its own page (same cookie session)."""
    op = _opener()
    if not url.startswith("kenney-signed:"):
        return op, url
    slug = url.split(":", 1)[1]
    page = "https://kenney.nl/assets/" + slug
    html = op.open(urllib.request.Request(page, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
    m = re.search(r"data-download-id=['\"]([0-9a-f]+)['\"]", html)
    if not m:
        raise IOError("no download id on " + page)
    req = urllib.request.Request("https://kenney.nl/download-link/" + m.group(1),
                                 headers={"User-Agent": UA, "Referer": page})
    data = json.loads(op.open(req, timeout=60).read().decode("utf-8"))
    if not data.get("url"):
        raise IOError("kenney returned no signed url for " + slug)
    return op, data["url"]


def download(entry, target, retries=3):
    target.parent.mkdir(parents=True, exist_ok=True)
    expect_sha, expect_size = entry.get("sha256"), entry.get("size")
    last = None
    for attempt in range(1, retries + 1):
        fd, tmp = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=str(target.parent))
        try:
            op, url = resolve_url(entry["url"])
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with op.open(req, timeout=120) as r, os.fdopen(fd, "wb") as out:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
            got_size = os.path.getsize(tmp)
            if expect_size and got_size != expect_size and not entry["url"].startswith("kenney-signed:"):
                raise IOError("size %d != %d" % (got_size, expect_size))
            got = sha256(tmp)
            if expect_sha and got != expect_sha:
                if entry["url"].startswith("kenney-signed:"):
                    print("    WARNING: Kenney zip changed upstream (sha %s); keeping it, run --record" % got[:12])
                else:
                    raise IOError("sha256 mismatch (%s)" % got[:12])
            os.replace(tmp, target)
            return
        except Exception as ex:  # network hiccup or bad file -> retry
            last = ex
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp):
                os.remove(tmp)
            print("    attempt %d failed: %s" % (attempt, ex))
    raise SystemExit("could not download %s: %s" % (entry["url"], last))


def extract(zpath):
    """Extract a zip next to itself, refusing absolute paths and '..' members."""
    dest = zpath.parent.resolve()
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            out = (dest / info.filename).resolve()
            if dest not in out.parents and out != dest:
                raise IOError("unsafe path in zip: " + info.filename)
        z.extractall(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT), help="base folder the manifest paths are relative to")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = man["files"]
    sel = files
    if a.only:
        keys = [k for k in a.only.split(",") if k]
        sel = [f for f in files if any(k in f["name"] or k in Path(f["path"]).name for k in keys)]
    dest = Path(a.dest)
    missing = 0
    for f in sel:
        target = dest.joinpath(*f["path"].split("/"))   # manifest uses "/" -> native separators here
        if a.record:
            if target.exists():
                f["sha256"], f["size"] = sha256(target), target.stat().st_size
            continue
        if target.exists() and (f.get("sha256") is None or sha256(target) == f["sha256"]):
            print("ok       %s" % f["path"])
            continue
        state = "changed " if target.exists() else "missing "
        if a.check:
            print(state + f["path"])
            missing += 1
            continue
        print("%s%s  <- %s (%.1f MB)" % (state, f["path"], f["url"], (f.get("size") or 0) / 1e6))
        download(f, target)
        if f.get("extract"):
            extract(target)
            print("    extracted")
        print("    saved")
    if a.record:
        MANIFEST.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
        print("recorded sha256/size for files on disk")
    if a.check and missing:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Download the gitignored binary assets the pipeline needs (Poly Haven HDRI + textures, CC0), as listed in
assets/manifest.json. Files that already exist with the right sha256 are skipped. Stdlib only (urllib), works on
Windows and macOS.

Usage:
  python tools/fetch_assets.py                 # fetch everything missing/changed into the repo
  python tools/fetch_assets.py --check         # only report status, download nothing (exit 1 if anything missing)
  python tools/fetch_assets.py --dest DIR      # put the files under DIR instead of the repo root (testing)
  python tools/fetch_assets.py --only NAME[,NAME]   # only entries whose name or file name contains NAME
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "manifest.json"
UA = "asset-fetcher/1.0 (python urllib)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, target, expect_sha, expect_size=None, retries=3):
    target.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(1, retries + 1):
        fd, tmp = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=str(target.parent))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r, os.fdopen(fd, "wb") as out:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
            if expect_size and os.path.getsize(tmp) != expect_size:
                raise IOError("size %d != %d" % (os.path.getsize(tmp), expect_size))
            got = sha256(tmp)
            if got != expect_sha:
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
    raise SystemExit("could not download %s: %s" % (url, last))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT), help="base folder the manifest paths are relative to")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    if a.only:
        keys = [k for k in a.only.split(",") if k]
        files = [f for f in files if any(k in f["name"] or k in Path(f["path"]).name for k in keys)]
    dest = Path(a.dest)
    missing = 0
    for f in files:
        target = dest.joinpath(*f["path"].split("/"))   # manifest uses "/" -> native separators here
        if target.exists() and sha256(target) == f["sha256"]:
            print("ok       %s" % f["path"])
            continue
        state = "changed " if target.exists() else "missing "
        if a.check:
            print(state + f["path"])
            missing += 1
            continue
        print("%s%s  <- %s (%.1f MB)" % (state, f["path"], f["url"], f.get("size", 0) / 1e6))
        download(f["url"], target, f["sha256"], f.get("size"))
        print("    saved")
    if a.check and missing:
        sys.exit(1)


if __name__ == "__main__":
    main()

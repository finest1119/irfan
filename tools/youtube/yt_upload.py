"""Mirror a Facebook Page's reels to a local Studio queue or its bound YouTube channel."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "secrets" / "youtube"
READY = ROOT / "output" / "youtube"
PAGES = {
    "wjh": ("1475508022311252", ".env", "output/*.post.md", "25"),
    "sme": ("1485761621285655", ".env.page2", "page2/episodes/*/out/*.post.md", "28"),
    "ed": ("1379706781903422", ".env.page3", "page3/_qc/*/*.post.md", "27"),
}
FIELDS = "id,from,title,description,created_time,scheduled_publish_time,published,source,views"
GRAPH = "https://graph.facebook.com/v27.0/"
UTC = timezone.utc


def save(path, obj):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(obj, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)


def read(path, default):
    return json.loads(path.read_text()) if path.is_file() else default


@contextlib.contextmanager
def lock(page):
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (PRIVATE / (page + ".lock")).open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def graph(path, token, **params):
    response = requests.get(GRAPH + path, headers={"Authorization": "Bearer " + token},
                            params=params, timeout=45, allow_redirects=False)
    if not response.ok:
        raise ValueError(f"Facebook Graph HTTP {response.status_code} for {path}")
    return response.json()


def rows(path, token, fields):
    after = None
    while True:
        params = {"fields": fields, "limit": 100}
        if after:
            params["after"] = after
        result = graph(path, token, **params)
        yield from result["data"]
        paging = result.get("paging", {})
        if not paging.get("next"):
            break
        cursor = paging.get("cursors", {}).get("after")
        if not cursor or after == cursor:
            raise ValueError("Facebook pagination did not advance")
        after = cursor


def timestamp(value):
    return datetime.fromisoformat(re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value).replace("Z", "+00:00"))


def inventory(pid, token):
    reels = {r["id"]: r for r in rows(pid + "/video_reels", token, FIELDS) if r.get("published")}
    for post in rows(pid + "/published_posts", token, "created_time,attachments{url,target}"):
        for item in post.get("attachments", {}).get("data", []):
            vid = str(item.get("target", {}).get("id", ""))
            if vid in reels:
                reels[vid]["created_time"] = post["created_time"]
    for post in rows(pid + "/scheduled_posts", token, "scheduled_publish_time,attachments{url,target}"):
        for item in post.get("attachments", {}).get("data", []):
            match = re.search(r"/reel/(\d+)", item.get("url", ""))
            if not match:
                continue
            vid = match[1]
            r = graph(vid, token, fields=FIELDS)
            if not r.get("published"):
                r["scheduled_publish_time"] = datetime.fromtimestamp(
                    int(post["scheduled_publish_time"]), UTC).isoformat()
            reels[vid] = r
    if any(r.get("from", {}).get("id") != pid for r in reels.values()):
        raise ValueError("Facebook owner mismatch")
    return sorted(reels.values(), key=lambda r: (not r["published"],
                  timestamp(r.get("scheduled_publish_time") or r["created_time"])))


def normalize(text):
    return " ".join(text.casefold().split())


def copy_index(page):
    result = []
    for path in ROOT.glob(PAGES[page][2]):
        content = path.read_text()
        cap = re.search(r"^## Facebook caption[^\n]*\n(.*?)(?=^## |\Z)", content, re.M | re.S)
        title = re.search(r"^# (.+)$", content, re.M)
        if cap and title:
            result.append((title[1].strip(), cap[1].strip(), path))
    return result


def metadata(reel, index):
    caption = reel.get("description", "").strip()
    prefix = normalize(caption)[:100]
    matches = [(t, c, p) for t, c, p in index if len(prefix) >= 25 and normalize(c).startswith(prefix)]
    if len(matches) == 1:
        title, caption, path = matches[0]
        source = str(path.relative_to(ROOT))
    else:
        if not caption:
            raise ValueError("missing Facebook description")
        title = reel.get("title") or re.split(r"(?<=[?!.])\s|\n", caption, maxsplit=1)[0]
        source = "Facebook"
    title = title.replace("<", "").replace(">", "").strip()
    if len(title) > 100:
        title = title[:100].rsplit(" ", 1)[0].rstrip(",;:") or title[:100]
    caption = re.sub(r"(?i)(?<!\w)#shorts\b", "", caption).strip().replace("<", "").replace(">", "")
    description = caption.encode()[:4989].decode(errors="ignore").rstrip() + "\n\n#Shorts"
    return dict(facebook_id=reel["id"], title=title, description=description,
                facebook_time=reel.get("scheduled_publish_time") or reel["created_time"],
                facebook_published=reel["published"], views=reel.get("views", 0),
                copy_source=source, synthetic=True)


def probe(path):
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", str(path)], check=True, capture_output=True)
    info = json.loads(proc.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    duration = float(info["format"]["duration"])
    if video["width"] > video["height"] or not 0 < duration <= 180.05:
        raise ValueError("source is outside the Shorts aspect ratio or duration")
    return duration


def prepare(reel, meta, page):
    folder = READY / page / reel["id"]
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / "video.mp4"
    if not video.exists():
        url = reel.get("source")
        if not url:
            return None
        if urlsplit(url).scheme != "https":
            raise ValueError("non-HTTPS media source")
        with requests.get(url, stream=True, timeout=(15, 90)) as r:
            if r.status_code != 200:
                raise ValueError(f"Facebook media HTTP {r.status_code}")
            temp = folder / "video.part"
            with temp.open("wb") as out:
                for chunk in r.iter_content(1024 * 512):
                    out.write(chunk)
            meta["duration"] = probe(temp)
            temp.replace(video)
    else:
        meta["duration"] = probe(video)
    local_time = timestamp(meta["facebook_time"]).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
    when = "Already public on Facebook" if meta["facebook_published"] else "Schedule on YouTube"
    notes = f"{when}: {local_time:%Y-%m-%d %H:%M:%S %Z}\n\n{meta['title']}\n\n{meta['description']}\n"
    (folder / "studio.txt").write_text(notes)
    save(folder / "metadata.json", meta)
    return video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=PAGES, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--upload", action="store_true", help="Upload to this Page's verified channel")
    mode.add_argument("--record-studio", nargs=2, metavar=("FB_ID", "YOUTUBE_ID"),
                      help="Record an upload already completed via Studio")
    args = parser.parse_args()
    page = args.page
    pid, env_file, _, category = PAGES[page]
    env = dotenv_values(ROOT / env_file)
    if env.get("FB_PAGE_ID") != pid:
        raise ValueError("unexpected Facebook Page ID")
    with lock(page):
        if args.record_studio:
            from youtube_api import Uploader
            vid, yid = args.record_studio
            if not re.fullmatch(r"\d+", vid) or not (READY / page / vid / "metadata.json").is_file():
                raise ValueError("Facebook ID is not in the selected Page queue")
            Uploader(page, category).record_studio(vid, yid)
            return 0
        reels = inventory(pid, env["FB_PAGE_TOKEN"])
        index = copy_index(page)
        held = set(read(PRIVATE / "hold.json", {}).get(page, []))
        errors = 0
        if args.upload:
            from youtube_api import Uploader
            uploader = Uploader(page, category)
        for reel in reels:
            vid = reel["id"]
            if vid in held:
                print(page, vid, "held")
                continue
            try:
                meta = metadata(reel, index)
                if args.dry_run:
                    print(page, vid, "published" if reel["published"] else "scheduled", meta["title"])
                    continue
                video = prepare(reel, meta, page)
                if not video:
                    print(page, vid, "awaiting Facebook source")
                    continue
                if args.upload:
                    print(page, vid, uploader.upload(meta, video))
                else:
                    print(page, vid, "ready")
            except (ValueError, requests.RequestException, subprocess.SubprocessError, StopIteration) as e:
                # Exception text from an HTTP library can include a signed media URL.
                print(page, vid, "retry required", type(e).__name__, file=sys.stderr)
                errors += 1
                if args.upload:
                    break
        return int(errors != 0)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        sys.exit(main())
    except Exception as exc:
        print("Stopped:", str(exc) if type(exc) in (ValueError, RuntimeError) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)

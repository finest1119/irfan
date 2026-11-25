"""Upload + schedule (or publish now) a Reel on the What Just Happened Page via the Graph API, then set the AI label.

Usage:
  .venv/bin/python tools/fb_schedule_reel.py "output/<keyword> fb.mp4" "output/<keyword>.post.md" "2026-11-25 08:00"
  .venv/bin/python tools/fb_schedule_reel.py ... now          # publish immediately instead of scheduling
  .venv/bin/python tools/fb_schedule_reel.py --label <video_id>  # (re)apply the AI label once the post exists
  ... --thumb <image.jpg>   custom cover; without it "<keyword> thumb.jpg" next to "<keyword> fb.mp4" is used if present.
  Cover = POST /{video-id}/thumbnails (multipart source + is_preferred=true) after the reel is created; a failure only
  warns (the reel stays scheduled). For reels already scheduled: tools/fb_set_thumbnail.py <video_id> <image>.

Time is Malaysia time (UTC+8) unless SCHEDULE_TZ is set (e.g. America/New_York for the Self-Made
Engineer laptop; Windows needs `pip install tzdata`), see pipeline/platform_cfg.py. Caption = "## Facebook caption" section of post.md (caption + hashtags).
AI label: Graph API v27 Page *post* object accepts boolean `is_ai_generated` (edit after the post exists).
We also pass it on the finish call in case the Reels endpoint honours it at creation. Never prints the token.
State is written to output/api-posts.json (video_id, post_id, schedule, label status).
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import dotenv_values

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
import platform_cfg as PC  # cross-platform paths; macOS defaults = the old hard-coded values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env = dotenv_values(os.path.join(ROOT, ".env"))
TOKEN, PAGE = env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"]
V = "v27.0"
G = "https://graph.facebook.com/%s/" % V
STATE = os.path.join(ROOT, "output", "api-posts.json")
MYT = PC.schedule_tz()   # default: fixed UTC+8 (unchanged); SCHEDULE_TZ=<IANA zone> uses zoneinfo


def call(method, path, **q):
    q["access_token"] = TOKEN
    url = G + path
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(q)
    else:
        data = urllib.parse.urlencode(q).encode()
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method)))
    except urllib.error.HTTPError as e:
        return {"ERR": e.code, "msg": json.loads(e.read()).get("error", {}).get("message")}


def set_thumbnail(video_id, image, tries=3, gap=20):
    """Upload a custom cover to /{video-id}/thumbnails (is_preferred=true). Never raises; returns the result dict."""
    try:
        boundary = "----wjhthumb%d" % int(time.time() * 1000)
        ext = os.path.splitext(image)[1].lower()
        ctype = "image/png" if ext == ".png" else "image/jpeg"
        parts = []
        for k, v in (("access_token", TOKEN), ("is_preferred", "true")):
            parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode())
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"source\"; filename=\"thumb%s\"\r\n"
                      "Content-Type: %s\r\n\r\n" % (boundary, ext or ".jpg", ctype)).encode())
        body = b"".join(parts) + open(image, "rb").read() + ("\r\n--%s--\r\n" % boundary).encode()
    except Exception as e:
        return {"ERR": "local", "msg": "%s: %s" % (type(e).__name__, e)}
    r = None
    for i in range(tries):
        try:
            req = urllib.request.Request(G + "%s/thumbnails" % video_id, data=body, method="POST",
                                         headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            if not isinstance(r, dict):          # docs are ambiguous (struct vs list); any 2xx body = success
                return {"success": True, "data": r}
            if r.get("success") is not False:
                return r
        except urllib.error.HTTPError as e:
            try:
                r = {"ERR": e.code, "msg": json.loads(e.read()).get("error", {}).get("message")}
            except Exception:
                r = {"ERR": e.code, "msg": "non-JSON error body"}
        except Exception as e:  # URLError, timeout, bad JSON: never let the cover break posting
            r = {"ERR": type(e).__name__, "msg": str(e)[:200]}
        if i < tries - 1:
            time.sleep(gap)
    return r


def find_thumb(video):
    """'<keyword> fb.mp4' -> '<keyword> thumb.jpg' (also accepts '<keyword> fb thumb.jpg') if it exists."""
    stem = os.path.splitext(video)[0]
    for c in (re.sub(r" fb$", "", stem) + " thumb.jpg", stem + " thumb.jpg"):
        if os.path.exists(c):
            return c
    return None


def caption(post_md):
    t = open(post_md, encoding="utf-8").read()
    m = re.search(r"## Facebook caption\s*\n(.+?)\n## ", t, re.S)
    return m.group(1).strip()


def save(rec):
    st = json.load(open(STATE)) if os.path.exists(STATE) else []
    st = [r for r in st if r.get("video_id") != rec["video_id"]] + [rec]
    json.dump(st, open(STATE, "w"), indent=1)


def label(video_id, wait=600):
    """Find the post for this reel and set is_ai_generated=true on it."""
    t0 = time.time()
    while time.time() - t0 < wait:
        info = call("GET", video_id, fields="post_id,status")
        pid = info.get("post_id")
        if pid:
            r = call("POST", "%s_%s" % (PAGE, pid), is_ai_generated="true")
            print("label on post", pid, "->", r)
            return pid, r
        time.sleep(15)
    print("no post_id yet for video", video_id)
    return None, {"ERR": "no post_id"}


def main(video, post_md, when, thumb=None):
    size = os.path.getsize(video)
    desc = caption(post_md)
    st = call("POST", PAGE + "/video_reels", upload_phase="start")
    if "video_id" not in st:
        sys.exit("start failed: %s" % st)
    vid = st["video_id"]
    up = urllib.request.Request("https://rupload.facebook.com/video-upload/%s/%s" % (V, vid),
                                data=open(video, "rb").read(), method="POST",
                                headers={"Authorization": "OAuth " + TOKEN, "offset": "0", "file_size": str(size)})
    try:
        print("upload:", json.load(urllib.request.urlopen(up)))
    except urllib.error.HTTPError as e:
        sys.exit("upload failed: %s %s" % (e.code, e.read()[:300]))
    fin = dict(upload_phase="finish", video_id=vid, description=desc)
    if when == "now":
        fin["video_state"] = "PUBLISHED"
        ts = None
    else:
        ts = int(dt.datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=MYT).timestamp())
        fin.update(video_state="SCHEDULED", scheduled_publish_time=str(ts))
    r = call("POST", PAGE + "/video_reels", is_ai_generated="true", **fin)
    if "ERR" in r and "is_ai_generated" in (r.get("msg") or ""):
        print("finish rejected is_ai_generated (%s) -> retry without" % r["msg"])
        r = call("POST", PAGE + "/video_reels", **fin)
    print("finish:", r)
    if "ERR" in r:
        sys.exit(1)
    rec = {"video_id": vid, "file": os.path.basename(video), "when_myt": when, "scheduled_ts": ts, "finish": r}
    pid, lr = label(vid, wait=300)
    rec.update(post_id=pid, label_result=lr)
    save(rec)
    thumb = thumb or find_thumb(video)
    if thumb:
        try:
            tr = set_thumbnail(vid, thumb)
            print("thumbnail:", tr if "ERR" not in tr else "WARNING cover not set (reel still scheduled): %s" % tr)
            rec.update(thumb=os.path.basename(thumb), thumb_result=tr)
            save(rec)
        except Exception as e:
            print("WARNING thumbnail step failed (reel still scheduled): %s" % e)
    print(json.dumps({k: rec[k] for k in ("video_id", "post_id", "when_myt")}))


if __name__ == "__main__":
    a = sys.argv[1:]
    th = None
    if "--thumb" in a:
        i = a.index("--thumb")
        th = a[i + 1]
        del a[i:i + 2]
        if not os.path.exists(th):
            sys.exit("--thumb file not found: %s" % th)
    if a[0] == "--label":
        label(a[1])
    else:
        main(a[0], a[1], " ".join(a[2:]), th)

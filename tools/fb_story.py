"""Post a video as a Facebook Page Story via the Graph API (Page-agnostic).

Usage:
  .venv/bin/python tools/fb_story.py "output/<keyword> story.mp4" --dry-run
  .venv/bin/python tools/fb_story.py "output/<keyword> story.mp4" [--env .env] [--log output/stories.json]
                                     [--reel-video-id <id>]

Flow (https://developers.facebook.com/docs/page-stories-api):
  1. POST /{page-id}/video_stories  upload_phase=start            -> video_id (+ upload_url)
  2. POST https://rupload.facebook.com/video-upload/v27.0/{video_id}
        headers: Authorization: OAuth <token>, offset: 0, file_size: <bytes>; body = file bytes
  3. POST /{page-id}/video_stories  upload_phase=finish, video_id  -> success, post_id
Stories publish immediately on finish (no scheduling in the API). Video stories must be 3-60 s,
9:16, >=540x960 (1080x1920 recommended), 24-60 fps, H.264/H.265/VP9/AV1, AAC 48 kHz stereo.

FB_PAGE_ID / FB_PAGE_TOKEN come from --env via python-dotenv and are never printed.
Each phase is retried once. The result is appended to --log (JSON list).
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import dotenv_values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
V = "v27.0"
G = "https://graph.facebook.com/%s/" % V
RUPLOAD = "https://rupload.facebook.com/video-upload/%s/%%s" % V
MIN_S, MAX_S = 3.0, 60.0
VCODECS = {"h264", "hevc", "vp9", "av1"}


def _abs(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_creds(env_path):
    env = dotenv_values(_abs(env_path))
    page, token = env.get("FB_PAGE_ID"), env.get("FB_PAGE_TOKEN")
    if not page or not token:
        sys.exit("FB_PAGE_ID / FB_PAGE_TOKEN missing in %s" % env_path)
    return page, token


class Graph:
    """Minimal Graph client. The token never appears in printed output or exceptions."""

    def __init__(self, token):
        self._t = token

    def _scrub(self, s):
        return str(s).replace(self._t, "***")

    def call(self, method, path, **q):
        q["access_token"] = self._t
        url, data = G + path, None
        if method == "GET":
            url += "?" + urllib.parse.urlencode(q)
        else:
            data = urllib.parse.urlencode(q).encode()
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=120))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message")
            except Exception:
                msg = "HTTP %s" % e.code
            return {"ERR": e.code, "msg": self._scrub(msg)}
        except Exception as e:  # URLError, timeout, bad JSON
            return {"ERR": type(e).__name__, "msg": self._scrub(getattr(e, "reason", e))}

    def get(self, path, **q):
        return self.call("GET", path, **q)

    def upload(self, video_id, path):
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            body = f.read()
        req = urllib.request.Request(RUPLOAD % video_id, data=body, method="POST",
                                     headers={"Authorization": "OAuth " + self._t,
                                              "offset": "0", "file_size": str(size)})
        try:
            return json.load(urllib.request.urlopen(req, timeout=600))
        except urllib.error.HTTPError as e:
            return {"ERR": e.code, "msg": self._scrub(e.read()[:300])}
        except Exception as e:
            return {"ERR": type(e).__name__, "msg": self._scrub(getattr(e, "reason", e))}


def probe(path):
    """Validate a file against the documented Page Story video limits. Returns (info, problems)."""
    if not os.path.exists(path):
        return {}, ["file not found: %s" % path]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration,size:stream=codec_type,codec_name,width,height,avg_frame_rate,"
                          "sample_rate,channels,pix_fmt", "-of", "json", path],
                         capture_output=True, text=True)
    j = json.loads(out.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    info = {"duration": round(float(j.get("format", {}).get("duration", 0)), 2),
            "size_mb": round(int(j.get("format", {}).get("size", 0)) / 1e6, 1),
            "vcodec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
            "fps": round(fps, 2), "pix_fmt": v.get("pix_fmt"),
            "acodec": a.get("codec_name"), "sample_rate": a.get("sample_rate"), "channels": a.get("channels")}
    p = []
    if not (MIN_S <= info["duration"] <= MAX_S):
        p.append("duration %.2fs outside %g-%gs" % (info["duration"], MIN_S, MAX_S))
    if info["vcodec"] not in VCODECS:
        p.append("video codec %s not in %s" % (info["vcodec"], sorted(VCODECS)))
    w, h = info["width"] or 0, info["height"] or 0
    if w < 540 or h < 960:
        p.append("resolution %sx%s below 540x960" % (w, h))
    elif abs(w / h - 9 / 16) > 0.01:
        p.append("aspect %sx%s is not 9:16" % (w, h))
    if not (24 <= fps <= 60):
        p.append("fps %.2f outside 24-60" % fps)
    if info["acodec"] and info["acodec"] != "aac":
        p.append("audio codec %s (AAC recommended)" % info["acodec"])
    return info, p


def append_log(log, rec):
    log = _abs(log)
    st = json.load(open(log)) if os.path.exists(log) else []
    st.append(rec)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    tmp = log + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1)
    os.replace(tmp, log)


def _twice(fn, label):
    r = fn()
    if "ERR" in r or r.get("success") is False:
        print("%s failed (%s) -> retrying once" % (label, r))
        time.sleep(5)
        r = fn()
    return r


def post_story(video, env=".env", log="output/stories.json", dry_run=False, reel_video_id=None, source=None):
    """Validate and (unless dry_run) post `video` as a Page Story. Returns the log record (or None on dry run)."""
    video = _abs(video)
    info, problems = probe(video)
    print("file:", os.path.relpath(video, ROOT), json.dumps(info))
    if problems:
        print("INVALID:", "; ".join(problems))
        if dry_run:
            return None
        sys.exit(2)
    print("valid for Page Story (3-60 s, 9:16, >=540x960, 24-60 fps)")
    if dry_run:
        print("DRY RUN - would: POST /{page}/video_stories upload_phase=start -> rupload %s bytes "
              "-> POST /{page}/video_stories upload_phase=finish video_id=<id> is_ai_generated=true "
              "-> append to %s" % (os.path.getsize(video), log))
        return None

    page, token = load_creds(env)
    g = Graph(token)
    rec = {"file": os.path.relpath(video, ROOT), "reel_video_id": reel_video_id, "source": source,
           "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "info": info}

    st = _twice(lambda: g.call("POST", page + "/video_stories", upload_phase="start"), "start")
    if "video_id" not in st:
        rec.update(status="failed", phase="start", result=st)
        append_log(log, rec)
        sys.exit("start failed: %s" % st)
    vid = rec["video_id"] = st["video_id"]

    up = _twice(lambda: g.upload(vid, video), "upload")
    print("upload:", up)
    if not up.get("success"):
        rec.update(status="failed", phase="upload", result=up)
        append_log(log, rec)
        sys.exit("upload failed: %s" % up)

    def finish():
        r = g.call("POST", page + "/video_stories", upload_phase="finish", video_id=vid, is_ai_generated="true")
        if "ERR" in r and "is_ai_generated" in (r.get("msg") or ""):
            print("finish rejected is_ai_generated (%s) -> without" % r["msg"])
            r = g.call("POST", page + "/video_stories", upload_phase="finish", video_id=vid)
        return r

    fin = _twice(finish, "finish")
    print("finish:", fin)
    ok = "ERR" not in fin and fin.get("success", True) is not False
    rec.update(status="posted" if ok else "failed", phase="finish", post_id=fin.get("post_id"), result=fin)
    if ok:
        time.sleep(5)
        rec["status_check"] = g.get(vid, fields="status")  # read-only
    append_log(log, rec)
    print(json.dumps({k: rec.get(k) for k in ("video_id", "post_id", "status")}))
    if not ok:
        sys.exit(1)
    return rec


def main():
    ap = argparse.ArgumentParser(description="Post a video as a Facebook Page Story.")
    ap.add_argument("video")
    ap.add_argument("--env", default=".env")
    ap.add_argument("--log", default="output/stories.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reel-video-id", help="link this story to a reel's video_id in the log")
    a = ap.parse_args()
    post_story(a.video, a.env, a.log, a.dry_run, a.reel_video_id)


if __name__ == "__main__":
    main()

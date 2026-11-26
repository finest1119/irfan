"""Post each reel's engagement comment as the Page, 10-60 min after it goes live. Plain Python, no LLM.

Run every ~30 min (launchd: tools/launchd/com.irfan.fb-autocomment.plist):
  .venv/bin/python tools/auto_comment.py [--dry-run] [--window MIN MAX] [--pages wjh,sme,ed]

Per Page:
  - reels come from that Page's api-posts.json (written by tools/fb_schedule_reel.py), time = scheduled_ts or
    when_myt (MYT, UTC+8); when_myt "now" -> the Graph API publish_time is used instead;
  - a reel whose time is MIN..MAX minutes ago is checked on the Graph API: it must be published, and if the Page
    already has a comment on it nothing is posted (skipped-already);
  - the comment text is the "## Engagement comment" section of the matching "<keyword>.post.md"
    (same section tools/page_comment.py --auto uses);
  - results go to a small state file per Page (output/auto-comments*.json): "commented" and "skipped-already"
    are final and never retried, "error" is retried on the next run while the reel is still in the window.
Credentials: FB_PAGE_ID / FB_PAGE_TOKEN from that Page's env file via python-dotenv. The token is never printed.
"""
import argparse
import datetime as dt
import fcntl
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from dotenv import dotenv_values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
G = "https://graph.facebook.com/v27.0/"
MYT = dt.timezone(dt.timedelta(hours=8))

# Page key -> env file, api-posts files, where its post.md files live, state file (all relative to ROOT).
PAGES = {
    "wjh": {"name": "What Just Happened", "env": ".env",
            "posts": ["output/api-posts.json"],
            "md": ["output"],
            "state": "output/auto-comments.json"},
    "sme": {"name": "Self-Made Engineer", "env": ".env.page2",
            "posts": ["page2/output/api-posts.json"],
            "md": ["page2/output", "page2/_qc/*", "page2/episodes/*"],
            "state": "output/auto-comments-sme.json"},
    "ed": {"name": "Everyday Decoded", "env": ".env.page3",
           "posts": ["page3/output/api-posts.json"],
           "md": ["page3/output", "page3/_qc/*", "page3/episodes/*"],
           "state": "output/auto-comments-ed.json"},
}
FINAL = ("commented", "skipped-already")


def log(msg):
    print("%s %s" % (dt.datetime.now(MYT).strftime("%Y-%m-%d %H:%M:%S MYT"), msg), flush=True)


class Graph:
    def __init__(self, token):
        self._t = token

    def call(self, method, path, **q):
        q["access_token"] = self._t
        url, data = G + path, None
        if method == "GET":
            url += "?" + urllib.parse.urlencode(q)
        else:
            data = urllib.parse.urlencode(q).encode()
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message")
            except Exception:  # noqa
                msg = None
            return {"ERR": e.code, "msg": msg}
        except Exception as e:  # noqa  (network errors: never echo the URL, it holds the token)
            return {"ERR": type(e).__name__, "msg": getattr(e, "reason", None) and str(e.reason)}


def keyword(rec):
    if rec.get("keyword"):
        return rec["keyword"]
    f = os.path.basename(rec.get("file") or "")
    return re.sub(r"( fb)?\.mp4$", "", f) or None


def find_post_md(page, kw):
    for d in page["md"]:
        for f in sorted(glob.glob(os.path.join(ROOT, d, kw + ".post.md"))):
            return f
    return None


def engagement_comment(post_md):
    t = open(post_md, encoding="utf-8").read()
    m = re.search(r"^## Engagement comment[^\n]*\n(.*?)(?=^## |\Z)", t, re.S | re.M)
    return m.group(1).strip() if m and m.group(1).strip() else None


def planned_time(rec):
    """Scheduled time as an aware datetime, or None when the reel was published 'now'."""
    if rec.get("scheduled_ts"):
        return dt.datetime.fromtimestamp(int(rec["scheduled_ts"]), dt.timezone.utc)
    w = (rec.get("when_myt") or "").strip()
    try:
        return dt.datetime.strptime(w, "%Y-%m-%d %H:%M").replace(tzinfo=MYT)
    except ValueError:
        return None


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_state(path, st):
    tmp = path + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def run_page(key, lo, hi, dry):
    page = PAGES[key]
    env_path = os.path.join(ROOT, page["env"])
    if not os.path.exists(env_path):
        log("%s: skip, no %s" % (key, page["env"]))
        return
    recs = []
    for p in page["posts"]:
        recs += load_json(os.path.join(ROOT, p), [])
    if not recs:
        log("%s: no reels recorded (%s)" % (key, ", ".join(page["posts"])))
        return
    env = dotenv_values(env_path)
    page_id, token = env.get("FB_PAGE_ID"), env.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        log("%s: skip, FB_PAGE_ID / FB_PAGE_TOKEN missing in %s" % (key, page["env"]))
        return
    g = Graph(token)
    state_path = os.path.join(ROOT, page["state"])
    state = load_json(state_path, {})
    now = dt.datetime.now(dt.timezone.utc)
    acted = 0
    for rec in recs:
        vid = str(rec.get("video_id") or "")
        if not vid or state.get(vid, {}).get("status") in FINAL:
            continue
        kw = keyword(rec) or vid
        t = planned_time(rec)
        if t is not None:
            age = (now - t).total_seconds() / 60
            if not lo <= age <= hi:
                continue
        info = g.call("GET", vid, fields="status,post_id")
        if "ERR" in info:
            log("%s: error   %s [%s] video lookup failed: %s %s" % (key, kw, vid, info["ERR"], info.get("msg")))
            continue
        ph = info.get("status", {}).get("publishing_phase", {}) or {}
        if t is None:  # published "now": use the Graph publish time
            try:
                t = dt.datetime.strptime(ph.get("publish_time", ""), "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                continue
            age = (now - t).total_seconds() / 60
            if not lo <= age <= hi:
                continue
        acted += 1
        tag = "%s [%s] live %s, %.0f min ago" % (kw, vid, t.astimezone(MYT).strftime("%d %b %H:%M"), age)
        if ph.get("publish_status") != "published":
            log("%s: wait    %s: Graph says not published yet (%s)" % (key, tag, ph.get("publish_status")))
            continue
        cs = g.call("GET", vid + "/comments", fields="from", limit=100, filter="stream")
        if "ERR" in cs:
            log("%s: error   %s: comment lookup failed: %s %s" % (key, tag, cs["ERR"], cs.get("msg")))
            continue
        mine = [c.get("id") for c in cs.get("data", []) if (c.get("from") or {}).get("id") == page_id]
        rec_out = {"keyword": kw, "at": dt.datetime.now(MYT).strftime("%Y-%m-%d %H:%M MYT")}
        if mine:
            log("%s: skipped-already %s: Page comment %s exists" % (key, tag, mine[0]))
            if not dry:
                state[vid] = dict(rec_out, status="skipped-already", comment_id=mine[0])
            continue
        md = find_post_md(page, kw)
        msg = engagement_comment(md) if md else None
        if not msg:
            why = "no %s.post.md" % kw if not md else "no '## Engagement comment' in %s" % os.path.relpath(md, ROOT)
            log("%s: error   %s: %s" % (key, tag, why))
            if not dry:
                state[vid] = dict(rec_out, status="error", error=why,
                                  attempts=state.get(vid, {}).get("attempts", 0) + 1)
            continue
        if dry:
            log("%s: DRY-RUN would comment on %s: %r" % (key, tag, msg[:90]))
            continue
        r = g.call("POST", vid + "/comments", message=msg)
        if "ERR" in r or not r.get("id"):
            err = "%s %s" % (r.get("ERR"), r.get("msg"))
            log("%s: error   %s: post failed: %s" % (key, tag, err))
            state[vid] = dict(rec_out, status="error", error=err, attempts=state.get(vid, {}).get("attempts", 0) + 1)
        else:
            log("%s: commented %s: comment %s" % (key, tag, r["id"]))
            state[vid] = dict(rec_out, status="commented", comment_id=r["id"], message=msg)
        save_state(state_path, state)  # after every post, so a crash can never lead to a double post
    if not dry and acted:
        save_state(state_path, state)
    if not acted:
        log("%s: nothing in the %g-%g min window (%d reels recorded)" % (key, lo, hi, len(recs)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print what would be done, post nothing")
    ap.add_argument("--window", nargs=2, type=float, default=[10, 60], metavar=("MIN", "MAX"),
                    help="minutes since going live (default 10 60)")
    ap.add_argument("--pages", default="wjh,sme,ed", help="comma list of: " + ",".join(PAGES))
    a = ap.parse_args()
    keys = [k.strip() for k in a.pages.split(",") if k.strip()]
    bad = [k for k in keys if k not in PAGES]
    if bad:
        sys.exit("unknown page(s): %s (use %s)" % (",".join(bad), ",".join(PAGES)))
    lock = open(os.path.join(ROOT, "output", ".auto-comment.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another auto_comment run is active, exiting")
        return
    for k in keys:
        try:
            run_page(k, a.window[0], a.window[1], a.dry_run)
        except Exception as e:  # noqa  (one Page failing must not stop the others)
            log("%s: error   %s: %s" % (k, type(e).__name__, e))


if __name__ == "__main__":
    main()

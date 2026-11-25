"""Post a Page Story for every published Reel that doesn't have one yet. No LLM; safe to run every 10 min.

Usage:
  .venv/bin/python tools/story_scheduler.py --dry-run     # read-only GETs, no cut, no post, no log writes
  .venv/bin/python tools/story_scheduler.py               # live
  .venv/bin/python tools/story_scheduler.py --seed        # only write the pre-rule skip markers, no network

For each record in output/api-posts.json:
  - skip if output/stories.json already has a story for its video_id (posted / skipped), or 3 failed tries;
  - skip if its schedule time is still in the future;
  - read-only GET /{video_id}?fields=status -> must be ready + published;
  - skip (logged "skipped (stale)") if it went live more than --max-age-hours ago (stories last 24 h);
  - cut "output/<keyword> story.mp4" with make_story_cut.py (reused if it already exists) and post it
    with fb_story.post_story(), linking the story to the reel's video_id in the log.
A lock file stops overlapping runs. Credentials come from --env via dotenv and are never printed.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fb_story  # noqa: E402

ROOT = fb_story.ROOT
POSTS = os.path.join(ROOT, "output", "api-posts.json")
LOCK = os.path.join(ROOT, "output", ".story_scheduler.lock")
PY = sys.executable
MAX_FAILS = 3
PRE_RULE = {"946803861698880": "hurricane fb.mp4", "3361280247403397": "Nvidia CEO fb.mp4"}
DONE = ("posted", "skipped")


def now():
    return dt.datetime.now(dt.timezone.utc)


def load(path):
    return json.load(open(path)) if os.path.exists(path) else []


def seed(log):
    st = load(log)
    have = {r.get("reel_video_id") for r in st}
    added = 0
    for vid, f in PRE_RULE.items():
        if vid not in have:
            fb_story.append_log(log, {"reel_video_id": vid, "file": f, "status": "skipped (pre-rule)",
                                      "at": now().isoformat(timespec="seconds"),
                                      "note": "reel went live before the story rule"})
            added += 1
    return added


def state_for(st, vid):
    recs = [r for r in st if r.get("reel_video_id") == vid]
    if any(str(r.get("status", "")).startswith(DONE) for r in recs):
        return "done"
    if sum(1 for r in recs if r.get("status") == "failed") >= MAX_FAILS:
        return "gave-up"
    return None


def keyword(fname):
    k = os.path.splitext(os.path.basename(fname))[0]
    return re.sub(r"\s+fb$", "", k).strip()


def is_published(status):
    s = (status or {}).get("status", {})
    pub = s.get("publishing_phase", {}) or {}
    ok = s.get("video_status") == "ready" and pub.get("publish_status") == "published"
    return ok, pub.get("publish_time")


def main():
    ap = argparse.ArgumentParser(description="Auto-post Page Stories for published Reels.")
    ap.add_argument("--env", default=".env")
    ap.add_argument("--log", default="output/stories.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", action="store_true", help="only write pre-rule skip markers")
    ap.add_argument("--max-age-hours", type=float, default=20.0)
    a = ap.parse_args()
    log = fb_story._abs(a.log)

    lockf = open(LOCK, "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(now().isoformat(timespec="seconds"), "another run holds the lock - exiting")
        return

    print("=== story_scheduler", now().isoformat(timespec="seconds"), "dry-run" if a.dry_run else "LIVE")
    if a.seed:
        print("seeded %d pre-rule marker(s)" % seed(log))
        return
    if not a.dry_run:
        n = seed(log)
        if n:
            print("seeded %d pre-rule marker(s)" % n)

    st = load(log)
    g = None
    for rec in load(POSTS):
        vid, f = rec.get("video_id"), rec.get("file", "")
        tag = "%s (%s)" % (f, vid)
        if vid in PRE_RULE and not any(r.get("reel_video_id") == vid for r in st):
            print("skip  %s: pre-rule (would be marked)" % tag)
            continue
        s = state_for(st, vid)
        if s:
            print("skip  %s: %s" % (tag, s))
            continue
        ts = rec.get("scheduled_ts")
        if ts and ts > now().timestamp():
            print("wait  %s: scheduled %s MYT" % (tag, rec.get("when_myt")))
            continue
        if g is None:
            g = fb_story.Graph(fb_story.load_creds(a.env)[1])
        status = g.get(vid, fields="status")  # read-only
        if "ERR" in status:
            print("error %s: status GET -> %s" % (tag, status))
            continue
        ok, ptime = is_published(status)
        if not ok:
            print("wait  %s: not published yet (%s)" % (tag, json.dumps(status.get("status"))))
            continue
        live_at = ptime or ts
        if live_at and now().timestamp() - live_at > a.max_age_hours * 3600:
            print("stale %s: live %.1f h ago" % (tag, (now().timestamp() - live_at) / 3600))
            if not a.dry_run:
                fb_story.append_log(log, {"reel_video_id": vid, "file": f, "status": "skipped (stale)",
                                          "at": now().isoformat(timespec="seconds")})
            continue

        kw = keyword(f)
        src = next((p for p in (os.path.join(ROOT, "output", kw + ".mp4"), os.path.join(ROOT, "output", f))
                    if os.path.exists(p)), None)
        cut = os.path.join(ROOT, "output", kw + " story.mp4")
        if not src and not os.path.exists(cut):
            print("error %s: no source video for '%s'" % (tag, kw))
            continue
        if a.dry_run:
            print("POST  %s: would cut %s -> %s, then post via fb_story"
                  % (tag, os.path.relpath(src, ROOT) if src else "-", os.path.relpath(cut, ROOT)))
            if os.path.exists(cut):
                fb_story.post_story(cut, a.env, a.log, dry_run=True, reel_video_id=vid)
            continue
        if not os.path.exists(cut) or fb_story.probe(cut)[1]:
            r = subprocess.run([PY, os.path.join(ROOT, "tools", "make_story_cut.py"), src, cut],
                               capture_output=True, text=True)
            print(r.stdout.strip())
            if r.returncode:
                print("error %s: cut failed: %s" % (tag, r.stderr.strip()[-400:]))
                fb_story.append_log(log, {"reel_video_id": vid, "file": f, "status": "failed", "phase": "cut",
                                          "at": now().isoformat(timespec="seconds")})
                continue
        try:
            fb_story.post_story(cut, a.env, a.log, dry_run=False, reel_video_id=vid,
                                source=os.path.relpath(src, ROOT) if src else None)
        except SystemExit as e:
            print("error %s: story post failed (%s)" % (tag, e))
        st = load(log)
        time.sleep(2)


if __name__ == "__main__":
    main()

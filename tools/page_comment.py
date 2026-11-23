"""Post the engagement comment (as the What Just Happened Page) under a published reel.

Usage: .venv/bin/python tools/page_comment.py "<text that appears in the reel caption>" "<comment text>"
       .venv/bin/python tools/page_comment.py --auto   # every reel published in the last 12 h without a Page
                                                       # comment gets the engagement comment from its output/*.post.md
- Finds the newest published reel whose description contains the match text (Graph API, FB_PAGE_TOKEN in .env).
- Skips if the Page already commented on it (safe to run twice).
- Never prints the token.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from dotenv import dotenv_values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env = dotenv_values(os.path.join(ROOT, ".env"))
TOKEN, PAGE = env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"]
G = "https://graph.facebook.com/v23.0/"


def get(path, **q):
    q["access_token"] = TOKEN
    return json.load(urllib.request.urlopen(G + path + "?" + urllib.parse.urlencode(q)))


def main(match, message, tries=20):
    reel = None
    for _ in range(tries):
        for r in get(PAGE + "/video_reels", fields="id,description,status", limit=10).get("data", []):
            st = r.get("status", {})
            if match.lower() in (r.get("description") or "").lower() and \
                    st.get("publishing_phase", {}).get("publish_status") == "published":
                reel = r["id"]
                break
        if reel:
            break
        time.sleep(30)
    if not reel:
        print("NOT FOUND: no published reel matching", repr(match))
        sys.exit(1)
    for c in get(reel + "/comments", fields="from", limit=50).get("data", []):
        if c.get("from", {}).get("id") == PAGE:
            print("already commented on", reel)
            return
    data = urllib.parse.urlencode({"message": message, "access_token": TOKEN}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(G + reel + "/comments", data=data)))
    print("commented", r.get("id"), "on reel", reel)


def post_md_comments():
    """caption-start -> engagement comment, from every output/*.post.md"""
    import glob, re
    out = {}
    for f in glob.glob(os.path.join(ROOT, "output", "*.post.md")):
        t = open(f, encoding="utf-8").read()
        cap = re.search(r"## Facebook caption\s*\n+(.+?)\n", t)
        com = re.search(r"## Engagement comment[^\n]*\n+(.+?)\n", t)
        if cap and com:
            out[cap.group(1).strip()[:80]] = com.group(1).strip()
    return out


def auto(hours=12):
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    table = post_md_comments()
    for r in get(PAGE + "/video_reels", fields="id,description,status", limit=15).get("data", []):
        ph = r.get("status", {}).get("publishing_phase", {})
        if ph.get("publish_status") != "published":
            continue
        t = dt.datetime.strptime(ph.get("publish_time", "1970-01-01T00:00:00+0000"), "%Y-%m-%dT%H:%M:%S%z")
        if now - t > dt.timedelta(hours=hours):
            continue
        desc = (r.get("description") or "").strip()
        msg = next((c for k, c in table.items() if desc.startswith(k[:60])), None)
        if not msg:
            print("no post.md match for reel", r["id"], desc[:50])
            continue
        main(desc[:60], msg, tries=1)


if __name__ == "__main__":
    if sys.argv[1] == "--auto":
        auto()
    else:
        main(sys.argv[1], sys.argv[2])

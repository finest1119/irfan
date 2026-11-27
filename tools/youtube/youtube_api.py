"""Channel-bound OAuth and crash-safe resumable uploads. All session material stays local."""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import re
import secrets
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

from yt_upload import PRIVATE, lock, read, save, timestamp

NAMES = {"wjh": "What Just Happened", "sme": "Self-Made Engineer", "ed": "Everyday Decoded"}
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
API = "https://www.googleapis.com/youtube/v3/"
INSERT = "https://www.googleapis.com/upload/youtube/v3/videos"
PACIFIC = ZoneInfo("America/Los_Angeles")


def checked(response):
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"YouTube HTTP {response.status_code}")
    return response.json()


def identity(headers):
    result = checked(requests.get(API + "channels", headers=headers, params={"part": "snippet", "mine": "true"}, timeout=30))
    if len(result["items"]) != 1:
        raise RuntimeError("Choose exactly one Brand Account")
    item = result["items"][0]
    return item["id"], item["snippet"]["title"]


def bind(page, channel):
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel):
        raise ValueError("Use the channel ID from its YouTube Studio URL")
    path = PRIVATE / "desktop.json"
    with HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
        base = f"http://127.0.0.1:{server.server_port}"
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES, autogenerate_code_verifier=True)
        flow.redirect_uri = base + "/callback"
        url, state = flow.authorization_url(access_type="offline", prompt="consent select_account")
        replies = []

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parsed = urlsplit(self.path)
                if self.headers.get("Host") != f"127.0.0.1:{server.server_port}":
                    self.send_error(400)
                elif parsed.path == "/":
                    self.send_response(302)
                    self.send_header("Location", url)
                    self.end_headers()
                elif parsed.path == "/callback":
                    data = parse_qs(parsed.query)
                    if not secrets.compare_digest(data.get("state", [""])[0], state):
                        self.send_error(400)
                        return
                    replies.append(data.get("code", [None])[0])
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"You can return to the uploader.")
                else:
                    self.send_error(404)
        server.RequestHandlerClass = Callback
        print("Open this local address in the signed-in browser:", base, flush=True)
        server.timeout = 300
        deadline = datetime.now(timezone.utc) + timedelta(minutes=5)
        while not replies and datetime.now(timezone.utc) < deadline:
            server.handle_request()
        if not replies or not replies[0]:
            raise RuntimeError("OAuth consent expired or declined")
        flow.fetch_token(code=replies[0])
    credentials = flow.credentials
    actual, name = identity({"Authorization": "Bearer " + credentials.token})
    if actual != channel or name != NAMES[page] or not credentials.refresh_token:
        raise ValueError("The selected channel does not match the requested Page")
    save(PRIVATE / (page + ".oauth.json"), dict(channel=actual, refresh=credentials.refresh_token))


class Uploader:
    def __init__(self, page, category):
        self.category = category
        self.state_path = PRIVATE / (page + ".state.json")
        self.state = read(self.state_path, {})
        client = read(PRIVATE / "desktop.json", {}).get("installed", {})
        bound = read(PRIVATE / (page + ".oauth.json"), {})
        if not bound or not client:
            raise RuntimeError("Desktop OAuth client and channel consent required")
        response = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "grant_type": "refresh_token", "refresh_token": bound["refresh"]}, timeout=30)
        self.headers = {"Authorization": "Bearer " + checked(response)["access_token"]}
        channel, name = identity(self.headers)
        if channel != bound["channel"] or name != NAMES[page]:
            raise RuntimeError("Channel identity mismatch")
        self.channel = channel

    def quota(self, response):
        if response.status_code in (400, 403, 429):
            reasons = {r.get("reason") for r in response.json().get("error", {}).get("errors", [])}
            if reasons & {"quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded"}:
                tomorrow = datetime.now(PACIFIC).date() + timedelta(days=1)
                save(PRIVATE / "quota.json", {"until": str(tomorrow)})
                raise RuntimeError("Daily limit reached. Retry after midnight Pacific.")

    def upload(self, meta, video):
        vid = meta["facebook_id"]
        entry = self.state.get(vid, {})
        if entry.get("channel", self.channel) != self.channel:
            raise RuntimeError("State belongs to a different channel")
        if entry.get("youtube_id"):
            return "already uploaded " + entry["youtube_id"]
        if read(PRIVATE / "quota.json", {}).get("until", "") > str(datetime.now(PACIFIC).date()):
            raise RuntimeError("Daily quota resets at midnight Pacific")
        publish = timestamp(meta["facebook_time"])
        future = not meta["facebook_published"]
        if future and publish <= datetime.now(timezone.utc):
            return "waiting for Facebook publication"
        session = entry.get("session")
        size = video.stat().st_size
        offset = 0
        if session:
            response = requests.put(session, headers={**self.headers, "Content-Range": f"bytes */{size}"},
                                    timeout=40, allow_redirects=False)
            self.quota(response)
            if response.status_code in (200, 201):
                return self.record(vid, checked(response)["id"])
            if response.status_code != 308:
                raise RuntimeError(f"Session for {vid} needs reconciliation in Studio before retry")
            if response.headers.get("Range"):
                offset = int(response.headers["Range"].split("-")[-1]) + 1
        else:
            status = {"privacyStatus": "private" if future else "public", "containsSyntheticMedia": meta["synthetic"]}
            if future:
                status["publishAt"] = publish.astimezone(timezone.utc).isoformat()
            body = {"snippet": {"title": meta["title"], "description": meta["description"],
                                "categoryId": self.category, "defaultLanguage": "en-US",
                                "defaultAudioLanguage": "en-US"}, "status": status}
            response = requests.post(INSERT, params={"uploadType": "resumable", "part": "snippet,status",
                                                      "notifySubscribers": "false"},
                                     headers={**self.headers, "X-Upload-Content-Type": "video/mp4",
                                              "X-Upload-Content-Length": str(size)}, json=body, timeout=40)
            self.quota(response)
            if response.status_code != 200:
                raise RuntimeError(f"Upload initiation HTTP {response.status_code}")
            session = response.headers["Location"]
            host = urlsplit(session)
            if host.scheme != "https" or not (host.hostname or "").endswith(".googleapis.com"):
                raise ValueError("Unexpected upload service")
            self.state[vid] = {"channel": self.channel, "session": session}
            save(self.state_path, self.state)
        with video.open("rb") as stream:
            stream.seek(offset)
            response = requests.put(session, headers={**self.headers, "Content-Type": "video/mp4",
                "Content-Range": f"bytes {offset}-{size - 1}/{size}"}, data=stream, timeout=(20, 300),
                allow_redirects=False)
        self.quota(response)
        if response.status_code == 308:
            raise RuntimeError("Partial upload saved. Run again to resume.")
        return self.record(vid, checked(response)["id"])

    def record_studio(self, vid, yid):
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", yid):
            raise ValueError("Invalid YouTube video ID")
        found = checked(requests.get(API + "videos", params={"part": "snippet", "id": yid},
                                     headers=self.headers, timeout=30))["items"]
        if len(found) != 1 or found[0]["snippet"]["channelId"] != self.channel:
            raise ValueError("Video does not belong to the selected channel")
        old = self.state.get(vid, {}).get("youtube_id")
        if old and old != yid:
            raise ValueError("Another YouTube video is already bound")
        if any(k != vid and v.get("youtube_id") == yid for k, v in self.state.items()):
            raise ValueError("This video is already bound to a different Facebook reel")
        self.record(vid, yid)

    def record(self, vid, yid):
        self.state[vid] = {"channel": self.channel, "youtube_id": yid}
        save(self.state_path, self.state)
        return "uploaded " + yid


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True, choices=NAMES)
    parser.add_argument("--channel-id", required=True)
    args = parser.parse_args()
    try:
        with lock(args.page):
            bind(args.page, args.channel_id)
    except Exception as error:
        # OAuth exceptions can contain the authorization code or a token.
        raise SystemExit("Channel binding failed: " + type(error).__name__) from None

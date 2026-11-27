# YouTube publishing on the Mac

Run from the repo root with its Python environment (requests, python-dotenv and google-auth-oauthlib), FFmpeg and ffprobe on PATH.

    .venv/bin/python tools/youtube/yt_upload.py --page wjh --dry-run
    .venv/bin/python tools/youtube/yt_upload.py --page wjh

Use wjh, sme or ed. The default prepares private local folders under output/youtube/PAGE/FB_ID, with video.mp4, studio.txt and metadata.json. The inventory comes from the Page's live reels and scheduled posts. Unavailable scheduled files are retried on the next run. Studio uploads can use the exact time in studio.txt. Keep the same Page/ID pairing when recording a manual upload. Page-specific exclusions are numeric Facebook IDs in secrets/youtube/hold.json, keyed by Page.

Use one Google Cloud project for this uploader. Enable YouTube Data API v3 and configure an OAuth Desktop client. Store the downloaded Desktop client as secrets/youtube/desktop.json. Authorize each Brand Account separately with its channel ID from Studio. Open the displayed loopback address on this Mac and choose the matching channel in Google consent.

    .venv/bin/python tools/youtube/youtube_api.py --page wjh --channel-id CHANNEL_ID
    .venv/bin/python tools/youtube/yt_upload.py --page wjh --record-studio FB_ID YOUTUBE_ID
    .venv/bin/python tools/youtube/yt_upload.py --page wjh --upload

Before enabling daily uploads, record any videos already posted manually in Studio. The uploader binds credentials to channel ID and name. It sends private + publishAt for a future scheduled reel, or public for a published one. Resumable sessions and upload IDs live under secrets/youtube. If a stored session expires after an ambiguous network failure, reconcile the result in Studio. Record an existing upload with --record-studio. Daily quota errors pause the queue until the Pacific date changes.

    sh tools/youtube/daily.sh

Schedule the command in a Mac task with permission to read the repo in Documents. Run daily at 09:15 Malaysia time. Unbound channels prepare files only. The same run checks the prior Monday–Sunday for a weekly compilation and reuses a finished render. For FFmpeg installations without drawtext, set YOUTUBE_FFMPEG to the path of a compatible FFmpeg executable.

    .venv/bin/python tools/youtube/weekly_longform.py --page wjh --week 2026-11-23
    .venv/bin/python tools/youtube/weekly_longform.py --page wjh --week 2026-11-23 --render

The weekly tool ranks that week's public YouTube uploads by YouTube views and fits 6–12 segments into 8–12 minutes. A launch preview can use --facebook-preview to rank Facebook reels before the channels exist. Output includes a proposed theme and timestamped chapters. Review the theme with Irfan before publishing. The weekly tool renders locally and the daily task only publishes Shorts.

Google documents the default upload allowance and the current public-upload rules in its [quota and compliance guide](https://developers.google.com/youtube/data/guides/quota_and_compliance_audits).

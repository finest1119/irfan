#!/bin/sh
# Run on the Mac. A missing channel binding leaves that Page in Studio-ready mode.
set -u
repo=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd) || exit 1
cd "$repo" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
result=0
for page in wjh sme ed
do
    if [ -s "secrets/youtube/$page.oauth.json" ] && [ -s secrets/youtube/desktop.json ]; then
        .venv/bin/python tools/youtube/yt_upload.py --page "$page" --upload || result=1
    else
        .venv/bin/python tools/youtube/yt_upload.py --page "$page" || result=1
    fi
    # Retry last week's compilation on each run. A finished render is reused.
    .venv/bin/python tools/youtube/weekly_longform.py --page "$page" --render || result=1
done
exit "$result"

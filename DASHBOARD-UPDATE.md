# Updating the posting-status dashboard

Dashboard: https://claude.ai/artifact/WmZyrmitcETcMDhMMhaAww ("Status Posting Page")
Rows live in the collection `data/status/posts`. There is one document per video, and `doc_id` is the row id
(e.g. `wjh-2026-11-26-2`, `sme-build-01`). Only editors can write rows, and anyone who can open the dashboard can read them.

**Rule:** write a row only when its status changes. Going from "dijadualkan" to "posted" happens automatically:
the page shows "posted (ikut jadual)" once `post_time_myt` has passed. Never touch `files/`, `dash/` or `datasets/`.

## Change an existing row (pin the version)
1. `ArtifactData {action:"get", url, collection:"data/status/posts", doc_id:"wjh-2026-11-27-1"}`, which gives you `version`.
2. `ArtifactData {action:"update", url, collection:"data/status/posts", doc_id:"wjh-2026-11-27-1", if_version:<version>,
   data:{status:"sedang dibina", topic:"...", updated_at:"2026-11-26 14:05"}}`. Send only the fields that changed, plus `updated_at`.

## Add a new video
`ArtifactData {action:"set", url, collection:"data/status/posts", doc_id:"wjh-2026-11-28-1", data:{...all fields}}` (no if_version).
Id pattern: `<wjh|sme|ed>-<calendar day YYYY-MM-DD>-<slot n>`.

## Fields
- `page`: "What Just Happened" | "Self-Made Engineer" | "Everyday Decoded"
- `slot`: e.g. "Thu 26 #2" · `topic` · `note` (short, no personal data)
- `post_time_myt`: "YYYY-MM-DD HH:MM" in Malaysia time (UTC+8), or "" when there is no date yet
- `status`: "dirancang" | "riset/skrip" | "sedang dibina" | "QC" | "dijadualkan" | "posted" | "gagal"
- `story`: "belum" | "dah share" · `comment`: "belum" | "dah komen"
- `reel_url`: https only, `https://www.facebook.com/reel/<video_id>`. You can fill it when you schedule a video:
  the link only shows once the row counts as posted.
- `updated_at`: "YYYY-MM-DD HH:MM" MYT

Update `story` and `comment` when they are done (same update call). Never write tokens, .env values or emails.

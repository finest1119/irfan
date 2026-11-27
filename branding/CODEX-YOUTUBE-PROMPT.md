You are my (Irfan's) agent for bringing my 3 Facebook Pages to YouTube. Do as much as you can yourself, using your terminal and your built-in browser/connectors. I will ONLY do what truly needs me: typing passwords, 2FA codes, and any sign-in/consent screen that you can't complete. When you need me, stop, tell me exactly what to click, and wait.

Work in this local git repo: `/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan` (branch `claude/optimistic-hawking-lkruq9`). The repo is PUBLIC on GitHub. Other AI agents (Claude Code sessions) also work here and post to Facebook. Do not disrupt them.

## 1. Understand the project first (read, don't change)
- `CHIEF-HANDOFF.md`: Pages, machines, who does what.
- `branding/YOUTUBE-PLAN.md`: the YouTube plan you are implementing.
- `pipeline/README.md`: how reels are made, and the `output/<keyword>.post.md` format (title, caption, hashtags).
- `posting-log.md`, `output/api-posts.json`, `tools/fb_schedule_reel.py`: how Facebook scheduling works and where records live.
- `branding/`: logos, banners and Page style files, to use for the channel avatars and banners.

| Page | FB Page ID | Token file on this Mac (gitignored) |
|---|---|---|
| What Just Happened | 1475508022311252 | `.env` (FB_PAGE_TOKEN) |
| Self-Made Engineer | 1485761621285655 | `.env.page2` |
| Everyday Decoded | 1379706781903422 | `.env.page3` |

## 2. Tasks, in order
**A. Create the 3 YouTube channels** (Brand Accounts) under my Google account, in your browser: "What Just Happened", "Self-Made Engineer", "Everyday Decoded".
- Set avatar, banner, description (US English, matching each FB Page's bio) and links to the FB Page.
- Set the default upload settings: category, language English (US), "altered or synthetic content" where appropriate.
- If Google asks me to sign in or verify (phone/2FA), hand over to me, then continue.

**B. YouTube Data API access**:
- In my existing Google Cloud projects (one per Page; they already host the Gemini keys), enable YouTube Data API v3 and create an OAuth "Desktop app" client. Each Page needs its own project because of the ~6 uploads/day quota per project.
- Authorise each channel once. Store the refresh tokens ONLY in gitignored files: add `secrets/` to .gitignore FIRST.
- Submit the YouTube API Services audit/compliance form for each project. Until a project passes, API uploads are locked to PRIVATE.

**C. `tools/youtube/yt_upload.py`** (plain Python, no LLM at runtime), run from THIS Mac for all 3 Pages:
- Get each reel's video from Facebook via the Graph API with that Page's token (`GET /{video_id}?fields=source,...` or the Page's `video_reels`). The API file has no watermark; do not screen-record or download from the app.
- Take the title, caption and hashtags from the matching post.md where one exists; otherwise from the FB description. Title ≤100 chars. Description = caption + hashtags + "#Shorts".
- Upload as a YouTube Short. For reels still SCHEDULED on Facebook, set YouTube `publishAt` to the same time. If the FB video file isn't available yet for a scheduled reel, upload it after it goes live.
- Keep a per-Page state file (gitignored) so nothing is uploaded twice. Include `--page wjh|sme|ed`, `--dry-run`, and daily-quota handling that resumes the next day.
- Fallback until the audit passes: upload through YouTube Studio in your browser, or produce a ready folder (video + title + description + time) and upload those.

**D. Backfill**: upload all existing posted reels for the 3 Pages (oldest first), then everything currently scheduled.

**E. Automation**: a daily job on this Mac that uploads new reels. Use launchd only if it can read ~/Documents; otherwise give me the exact command for a scheduled task.

**F. `tools/youtube/weekly_longform.py`**: once a week per Page, compile that week's best 6–12 Shorts into one 16:9 long-form video (8–12 min), in Mildly Elsewhere style:
- The vertical video is centred over a blurred, zoomed copy of itself filling 1920×1080.
- Each segment's title shows in the side area.
- Chapters go in the description.
- FFmpeg only.
- Propose a theme title for each week and let me approve it before the first upload.

## 3. Rules
- Never print, log or commit any token, key, client secret or refresh token. Never put secrets in URLs.
- Don't modify Facebook posting/scheduling or existing pipeline files. Only ADD files (e.g. `tools/youtube/`) and small doc notes. Before each commit: `git pull --no-rebase`, stage only your files, push to the same branch. Commit messages end with "Co-Authored-By: Codex".
- Ask me before deleting anything, or before anything that costs money.
- Finish with a short Malay summary: channel links, what's uploaded/scheduled, what's still waiting on me (e.g. audit), and how to run the tools.

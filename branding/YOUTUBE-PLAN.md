# YouTube plan (Irfan decided 27 Nov 2026)

- One YouTube channel per Page: What Just Happened, Self-Made Engineer, Everyday Decoded.
- Every FB reel is also posted as a YouTube Short. Upload the original file, not an FB download; mark "altered or synthetic content" where it looks realistic.
- One long-form video per Page per week, compiled from that week's Shorts (8–12 min).

## Long-form format (studied: Mildly Elsewhere, "If You Dig a Hole, You Can Build Almost Anything", 12:45, youtube.com/watch?v=MXOCs029lTY)
- 16:9. The vertical short sits in the centre over a **blurred, zoomed copy of itself** that fills the frame.
- A **segment title** sits in the side area (e.g. "How a Hole by the Sea Becomes a Dry Dock").
- The compilation has a THEME title, not "weekly compilation". Description lists the segments, then hashtags.
- Their long-form videos get 19K–228K views.

## Our version
- FFmpeg script, no LLM: pick 6–12 of the week's Shorts (best by views, grouped by theme where possible), apply the blur-pillarbox and side title, and add chapters to the description.
- Only the theme title and description come from one small LLM call per week per Page.
- Note: these long-form compilations count toward the 4,000 watch-hour YPP path. Thresholds double on 1 Feb 2027.

## Setup needed (Irfan)
1. Create the 3 YouTube channels (brand accounts) under his Google account.
2. In each Page's Gemini/Google Cloud project, enable YouTube Data API v3 and create an OAuth client; authorise each channel once.
3. Risk: uploads from unaudited API projects are locked to PRIVATE, so request the YouTube API compliance audit (free; can take a while). Until it is approved, upload via the browser or by hand.
- API quota: about 6 uploads/day per project, so one project per Page is needed (ED up to 5/day).

## Upload method (Irfan, 27 Nov 2026): option 3
Everything runs from the Mac. The Mac pulls each reel's video from Facebook via the Graph API (Page tokens for all 3 Pages are on the Mac; API files carry no watermark) and uploads it to YouTube. The laptops are not involved. Codex builds and runs it (prompt: branding/CODEX-YOUTUBE-PROMPT.md); Irfan only handles logins, 2FA and consent screens.

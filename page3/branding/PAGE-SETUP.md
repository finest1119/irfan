# Everyday Decoded — Facebook Page setup kit

Prepared 24 Nov 2026 by the Page 3 session (offline). Page creation in Chrome only after the chief sends "go".
Template = What Just Happened setup (`irfan/plan.md` section "Page setup").

## Assets (`irfan/page3/branding/`)
- Profile picture: `logo-<chosen>.png` (1:1, legible as a small circle) — see "Choice" at the bottom.
- Cover: `cover-<chosen>-1640x624.png` (1640×624, no small text near the bottom-left where the profile picture sits).

## Texts

**Page name:** Everyday Decoded
**Category:** Digital creator (Page type: Creator)

**Bio (≤ 100 chars, US):**
> How everyday stuff really works: your phone, card, home & food. One hidden journey at a time.

(Backup, shorter: "The hidden side of the things you use every day. New explainer reels daily.")

**Contact email:** same as What Just Happened (set by Irfan's account; typed in the form, not stored here).

**Intro post (Public, then pinned):**
> Welcome to Everyday Decoded 👋
>
> You tap your card, flip a switch, hit play, order dinner — every single day. But what actually happens in the
> next few seconds?
>
> Here we follow the everyday things you use all the way inside: through the cell tower, under the street, into
> the bank's data center, behind the drive-thru window. One smooth, continuous journey per reel, with the
> surprising facts nobody tells you.
>
> New reels every day. Follow so you don't miss the next one — and tell us in the comments:
> 👉 What should we decode next?
>
> #EverydayDecoded #HowItWorks #Explained #DidYouKnow #Science

(Note: our visuals are AI-assisted 3D animations; every reel carries Facebook's AI label.)

## Steps (in Claude in Chrome, from Irfan's personal profile — after "go")
1. **Create Page**: Pages → Create new Page → name "Everyday Decoded", category "Digital creator", bio above →
   Create (Irfan approved pressing Create). Skip WhatsApp connection and friend invites.
2. **Switch to act as the Page** for everything below.
3. **Profile picture** = chosen logo; **cover** = chosen cover (1640×624). Check the circle crop and the cover
   on desktop + mobile preview.
4. **Bio / contact**: bio set; contact email same as WJH; Page **Public**.
5. **Action button = Follow** (default on Creator Pages; check).
6. **Intro post** (text above, + cover image or logo) → audience **Public** → post → **Pin** it.
7. **Admins**: Irfan only (Page access / Page roles — no other people).
8. **Professional Dashboard → Monetization**: check status; click **"Notify me"** / "Get notified" on Content
   Monetization (and Stars if shown). No payout/tax forms (Irfan does those later himself).
9. Username @everydaydecoded — try; new Pages are often blocked ("unable to choose a username") → retry later.
10. Record Page URL + Page ID in `irfan/page3/PLAN-v1.md` and report to the chief.

**Stop and report** on any unexpected consent / payment / identity / verification screen. Never type passwords or
financial data.

## Left for Irfan after creation
- **Page access token** for Graph API: Irfan in Graph API Explorer → select the same Meta app as WJH ("ft") → User token with
  `pages_show_list, pages_read_engagement, pages_manage_posts, pages_manage_engagement, pages_read_user_content,
  publish_video` → Get Page token for Everyday Decoded → exchange for a long-lived token (same flow as WJH) →
  put `FB_PAGE_ID` / `FB_PAGE_TOKEN` in the Windows laptop's `.env` (never in git, never pasted in chat).
- Check handles on Instagram / YouTube if he wants them later.

## Choice (Page 3 session, 24 Nov 2026 — all generated via Codex)
- **Profile: Logo C** (`logo-c.png`, 1024px copy `profile-logo-c.png`) — keyhole + house + teal trail with the amber
  Spark, wordmark "EVERYDAY / DECODED". Most recognisable as a small circle; the keyhole says "look inside".
  Backup: Logo A (clean wordmark, O as a teal keyhole ring — smaller text in the circle). Logo B (ED monogram +
  circuit) looked too "tech company". Compare: `logos-compare.jpg` (with small circle previews).
- **Cover: Cover A** (`cover-a-1640x624.png`) — hand + phone (X-ray), payment card with its antenna coil, cut-away
  house, utility trench, the teal trail running to a cell tower, downtown street. No text, no brands.
  Backups: `cover-b-1640x624.png` (diorama), `cover-c-1640x624.png` (street level). Compare: `covers-compare.jpg`.
- Spelling checked on all three logos: correct.

## Result (chief session, 24 Nov 2026)
Page live: https://www.facebook.com/profile.php?id=61596825063341 · Graph API Page ID **1465128156682768**
(`FB_PAGE_ID`). Token still pending (Irfan). Full report: `irfan/page3/PAGE-SETUP-REPORT.md`.

## Logo v2 (25 Nov 2026)
- Irfan chose **Logo B** (cut-away house in a scan lens): `logo-v2/b.png` (1024 px). Review sheet: `logos-v2-review.jpg`;
  source: `logo-v2/make_logos.py`. The chief uploads it as the profile picture.
- Cover `cover-themed-v2-1640x624.png` has no logo in it (text + teal line icons on charcoal), and it already uses the
  same charcoal + teal, so no matching tweak is needed.

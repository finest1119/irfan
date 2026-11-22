# Plan: FB Page + YouTube (World News & Disaster Explainers)

## 1. Concept
- Niche: world news, events, disasters. **Major countries only: US, UK, Europe, Russia, Japan, China.**
- Audience: US/UK (tier-1 CPM). Voiceover: English.
- Format: 9:16 reel, >1 min, 3D animated explainer (Blender script).
- Structure: **Hook** (verified news fact) → **Message** (general "what usually causes this") → **Metaphor/visual** → **Conclusion + loop/CTA**.
- Rules: every video >1 min; high engagement (end with a question); hook must be factual; speculation worded as "could/usually"; no blaming real people; title matches content; no reused news footage.

## 2. Facebook Reels workflow (from E'Calm video)
1. Create page from normal profile → page type **Creator**, category **Digital creator**.
2. Name + bio must contain high-search keywords (not just own name).
3. Own profile/cover photo (not generic AI).
4. Don't invite friends; grow organically.
5. Algorithm = "test and expand": engagement (likes, comments, saves, shares) drives reach → emotional script.
6. Post volume: up to 10–15 reels/day at scale.
7. Edit: captions 2–4 words, centered; voice synced to music (music ~80%); subtle effects, vary per video.
8. Export filename = target keyword. Title via prompt, tweak manually. Add relevant tags.
9. Monetization is **invite-only**. Creator's estimate: ~5,000 followers + 60,000 minutes viewed.

## 3. Risks to check
- [x] Monetization tab in Professional Dashboard: confirm eligibility for Malaysia-based creator. (22 Nov 2026: Malaysia = eligible country for Stars; Content Monetisation invite-only)
- [ ] Meta restricts monetization on tragedy/crime/sensitive content → frame as educational/safety explainer, no graphic visuals.

## 4. Keywords (researched)
Primary: news explained, world news, breaking news, what happened, disaster, plane crash, global events.
Secondary: explained, why it happened, world events, war news, natural disasters, aviation.

## Chosen page name: **What Just Happened**

## 5. Page names (Prompt 1, tone: Educational)
1. World News Explained
2. Headlines Explained Daily
3. What Really Happened Today
4. Breaking News Breakdown
5. Global Events Explained
6. Why It Happened News
7. The World Explained Daily
8. Disaster Files Explained
9. World News Decoded
10. Behind The Headlines Daily
11. Daily World Breakdown
12. News Explained Simply
13. What Happened Explained
14. Global News Unpacked
15. The Headline Explainer
16. World Events Decoded
17. Crash and Disaster Explained
18. Breaking World News Explained
19. Inside The Headlines
20. The Why Behind The News

### Extra names (round 2)
21. Disaster and News Explained
22. The World News Breakdown
23. Headlines Decoded Daily
24. What Just Happened Explained
25. Global Disasters Explained

## 6. Page descriptions (Prompt 2, ≤150 chars)
1. Breaking news explained in 60 seconds. Disasters, crashes, and world events made clear. Follow for daily updates.
2. What really happened? We break down world news, disasters, and crashes simply. Follow now and stay informed.
3. Discover the why behind the headlines. Plane crashes, storms, and global events explained. Follow for daily videos.
4. Learn what causes disasters, crashes, and conflicts in minutes. Clear facts, no hype. Hit Follow for daily news.
5. World events explained in plain English. From storms to plane crashes, we cover it fast. Join us and follow today.
6. Headlines move fast. We explain them. Daily breakdowns of world news and disasters. Follow so you never miss one.
7. Understand the news, not just read it. Disasters and world events explained daily. Follow and join our community.
8. Why did it happen? Get simple explanations of crashes, disasters, and global news. Follow for new videos daily.
9. Stay ahead of the headlines. Quick, clear explainers on world news, war, and disasters. Follow for daily updates.
10. Big news, explained simply. Disasters, crashes, and world events broken down daily. Follow and share with friends.

## 7. Tools / API (prices approx, verify before buying)
| Job | Free option | Paid option |
|---|---|---|
| Script | Claude (this session) | Claude API ~$0.02–0.05/script |
| Voiceover (**chosen**) | — | Google Gemini API `gemini-3.8-flash-tts`: $9/M audio tokens (25 tok/s) ≈ $0.02 per 70s video ≈ $0.35/week. Needs Gemini API key. |
| 3D animation | Blender + free CC0 models (Poly Haven, Kenney) | Paid models on Sketchfab/CGTrader |
| Captions | faster-whisper word timing (free) | — |
| Music | YouTube Audio Library / Pixabay | Epidemic Sound ~$10–17/mo |
| Keyword research | Google Trends, FB search | vidIQ (paid tiers) |

Start budget: **< $2/month** (TTS only).

## 8. Next steps
1. Pick description; create page "What Just Happened".
2. Get Gemini API key.
3. Build Blender pipeline → first video from `calendar.md`.
4. QC, then batch production.

## 9. Monetization-ready checklist (after page creation)
**Page setup**
- [ ] Username: @whatjusthappened (or closest available) — BLOCKED 22 Nov 2026: "You're currently unable to choose a username" (new-Page restriction). Retry after a few days / first followers.
- [x] Category: Digital creator; Page type: Creator (Page ID 61597041051729, created 22 Nov 2026)
- [x] Bio (desc #2), contact email
- [ ] Profile + cover photo (own design) — PENDING: needs own artwork
- [x] Action button: Follow (default on Creator Page)
- [x] Professional Dashboard enabled (Creator Dashboard)

**Account safety (required for monetization)**
- [x] Two-factor authentication ON (FB account, authenticator app)
- [x] Real name + verified email/phone on the owner profile (Accounts Centre)
- [x] Only you as admin; no suspicious admins

**Monetization tab (Professional Dashboard → Monetization)**
- [x] Check **Monetization status / Account status**: no violations (Page has no issues, no restrictions; Monetisation = not eligible yet)
- [x] Join **Content Monetization** (or its waitlist/"Get notified" if invite-only) — invite-only; "Notify me" clicked 22 Nov 2026
- [ ] Check **Creator Fast Track** eligibility and apply if shown — NOT SHOWN anywhere in dashboard (likely not offered to this Page/country)
- [ ] Turn on **Stars** when available — 1/3 criteria (eligible country ✓; need 500 followers + 500 for 30 consecutive days). "Notify me" clicked.
- [ ] Set up **payout account** (bank) + **tax form** (W-8BEN, non-US creator) — NOT AVAILABLE until a programme is unlocked; Irfan fills in bank/ID details
- [x] Screenshot every eligibility screen (country, requirements) — saved locally in `screenshots/` (gitignored, repo is public)

**Policy**
- [ ] Read Partner Monetization Policies + Content Monetization Policies — Irfan to read
- [ ] Original content only; no reposts, no graphic tragedy visuals

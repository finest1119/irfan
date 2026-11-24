# Self-Made Engineer — Facebook Page setup (follows the WJH template, plan.md §9)

Status 24 Nov 2026: **Page LIVE** — created by the chief session: https://www.facebook.com/profile.php?id=61597072432545 · **Page ID (FB_PAGE_ID) 1485761621285655**. Logo, cover, bio, contact email, pinned Public intro post, Monetisation "Notify me" done — details in `PAGE-SETUP-REPORT.md`. Page token: DONE 24 Nov 2026 — never-expiring PAGE token saved in gitignored `irfan/.env.page2` (FB_PAGE_ID + FB_PAGE_TOKEN); verified read-only (me = Self-Made Engineer, type PAGE, expires never, 6 scopes). Copy into the Windows laptop `.env`.

## Page fields
- Name: **Self-Made Engineer**
- Category: **Digital creator** (Creator Page)
- Bio (≤ 100 chars, 87): `Crazy backyard builds that actually work. Real physics, one wild DIY project at a time.`
- Contact email: same as WJH (copied from the WJH Page About), public
- Website: none · WhatsApp: skip · Invite friends: skip · Action button: Follow
- Profile picture: **`branding/profile-logo-final.png`** (= logo-1: orange gear + wrench + lightning bolt on navy, wordmark around the ring — strongest icon and still readable at small sizes; logo-2 mascot looks cartoon, not like our 3D Bolts; logo-3 'SME' is clean but says less)
- Cover: **`branding/cover-final-1640x624.png`** (= cover-2 centre-cropped: blueprint + backyard builds; title sits in the middle so it survives the mobile crop — cover-1 put the title on the far right, which mobile cuts off)
- Palette (distinct from WJH navy/red): steel navy #14212E + safety orange #FF7A1A + off-white #F4F1EA

## Pinned intro post (Public, posted AS the Page, then pinned)
> Welcome to Self-Made Engineer! 🔧⚡
>
> Meet Bolts — a stubborn backyard engineer who's tired of power outages and crazy utility bills, so he builds
> wild (but real) solutions himself: a wind turbine taller than his house, power from a creek, a pump that pushes
> water uphill with zero electricity… and every build stays on his property for the next one.
>
> New build every day, real physics, honest numbers — even when the idea flops.
>
> 👉 Follow so you don't miss Build #1.
> 💬 What should Bolts build first? Drop your craziest idea below.
>
> Animated with AI. Illustration only — check local codes and safety before building anything.
>
> #DIY #OffGrid #Engineering #BackyardBuild #Homestead

## After creation (checklist)
- [x] Page URL + Page ID recorded here
- [ ] Profile + cover uploaded
- [ ] Bio, contact email, Follow button
- [ ] Intro post published Public as the Page + pinned
- [ ] Only Irfan as admin; 2FA already on his account
- [ ] Professional Dashboard → Monetisation: click "Notify me"/waitlist only (no forms with personal/financial data)
- [ ] Username: try later (new Pages are usually blocked at first, as with WJH)
- [ ] Graph API Page token: **Irfan** re-runs "Generate Access Token" in Graph API Explorer (app ft) with this Page
      selected → token goes into the Windows laptop's `.env` (FB_PAGE_ID, FB_PAGE_TOKEN). Never pasted in chat.

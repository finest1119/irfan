# CHIEF HANDOFF — 27 Nov 2026, ~21:30 MYT (rotation #2)

You are the **chief / orchestrator**. Irfan talks ONLY to you, in Malay. Keep replies short.

Read memory first (dir `~/.claude/projects/-Users-irfan-Documents-Facebook---Youtube-Monetisation/memory/`):
- orchestrator-role, token-saving-rules (has the latest decisions log at the bottom)
- posting-checklist, fb-graph-api, windows-laptops, qc-skip-minor, daily-research
- reel-thumbnails, video-model-split, page2-self-made-engineer
- no-ai-info-check, ignore-global-claude-md

**When messaging agents, ALWAYS state your own session id**; the last rotation sent the old id by mistake.

## Agents (SendMessage `to`)
| Agent | Address |
|---|---|
| WJH (Mac) | local_d002084f-a13c-4f7a-a3ec-0e1591dcb128 |
| SME planner (Mac) | local_19e8a798-d9b2-4d35-a6d0-a4a64f23f003 |
| ED planner (Mac) | local_a723bba6-f993-4657-b7f4-dae8bac25ec9 |
| Dell G15 (SME render) | bridge:session_01529HbcjcTHxC34DCAwvwH3 |
| Asus ROG (ED render + posting) | bridge:session_01529HbZkYBJ4zEhfFw4XdbZ |

- The laptops refuse relayed OKs for heavy/irreversible work; give Irfan one exact line to type there.
- The Dell has a standing SME approval; the Asus has a standing ED approval.

## Pages / IDs
- WJH 1475508022311252 (.env)
- SME 1485761621285655 (.env.page2)
- ED 1379706781903422 (.env.page3)
- Dashboard: https://claude.ai/artifact/WmZyrmitcETcMDhMMhaAww (agent cards in `data/status/agents`)
- Branch: claude/optimistic-hawking-lkruq9. The repo is public: never commit secrets.

## State now
- **Weekly Claude quota ~91%**; resets **29 Nov 22:00 MYT**. Until then:
  - **ED is PAUSED** (15+ reels scheduled through 30 Nov 09:00 MYT; Asus idle).
  - **SME is PAUSED** (Build #1 scheduled Sat 28 Nov 08:30 MYT; the Dell posts its comment at 08:45 via a Windows task, so the Dell must be on).
  - **WJH continues.** The 07:00 `wjh-daily-news-research` task OWNS each day's set. A failed run can auto-retry, so check list_task_runs before sending the WJH agent in (this caused a duplicate once).
- **At the reset:** tell ED, the Asus and SME to RESUME. ED is back to 5/day. SME Build #2 uses the fast profile (~3.5 h). The SME option (a) plan (≤2 h) is in page2/BUILD-LOG.md.
- **Use Codex CLI for heavy code/scene work** (Irfan's ChatGPT quota): `codex exec -s workspace-write "<brief>"` from the repo root, in the background. Briefs used so far are in this session's scratchpad. Claude plans, reviews and commits.

## Decisions today (all in memory too)
- **Style:** ALL Pages move to the realistic Blender cutaway look (Mildly Elsewhere).
  - Toolkit: `pipeline/cutaway/` (cutlib.py, README with per-Page grades). Example: `examples/under_house_v2.py`.
  - The Zack-style test was rejected.
  - Rollout after the reset: SME first, then ED, then WJH.
- **SME script style:** Bolts stays; narration in "you"; a "But…/So…" build chain (page2/STYLE-REF-cutaway.md).
- **Thumbnails:** 3 layouts per Page approved (A/B/C, `tools/thumb_styles/*_b|_c.json`). Rotate A→B→C, never the same twice in a row. Already in the WJH task prompt; ED, SME and the Asus have been told.
- **WJH topics:** only STRONG world-attention topics; a big story from the past ~2 months is fine when the last 36 h is weak (in the task prompt).
- **Comments:** `wjh-auto-comments` task = `tools/auto_comment.py --window 10 240 --pages wjh,sme,ed` at 21:30/02:30/09:30. The launchd route was dropped (TCC).
- **Gemini:** each Page has its own Google project/key.
  - The Dell uses TTS_BACKEND=rest because Smart App Control blocks the SDK deps.
  - Tier 1 limit is 100 requests/day per TTS model.
  - **Billing Account 2 credit is low (~MYR 14)**: Irfan must top up.
- **YouTube:** one channel per Page. Every reel also goes up as a Short, plus a weekly long-form compilation (blur-pillarbox, Mildly Elsewhere format). Upload = option 3: the Mac pulls videos from FB Graph API `source`.
  - Irfan runs Codex (app) with branding/CODEX-YOUTUBE-PROMPT.md. Status unknown: ask him.
  - Plan: branding/YOUTUBE-PLAN.md. YPP thresholds double on 1 Feb 2027.
- **New Malaysian Pages (BM), not created yet:**
  - **Di Belakang Tabir** (ED-MY)
  - **Kita Buat Dia** (SME-MY, bizarre/rare builds, character **Bar The Builder**)
  - Final bios are in page4/DECISION.md. Per-Page plans are in page4/di-belakang-tabir and page4/kita-buat-dia (Codex drafts; review after the reset).

## In flight at handoff
- Codex is building a **Bar The Builder** character look test → `page4/character_bar/out/` + REPORT.md. When done: review, send Irfan the turnaround/hero still, and commit the script + still (not the frames).
- Next Codex ideas offered to Irfan:
  - a Di Belakang Tabir pilot render with cutlib
  - 3D logos/covers for the 2 MY Pages
  - the YouTube weekly long-form script, only if Irfan's Codex app isn't already doing YouTube

## Pending for Irfan
1. Top up Gemini credit (Billing Account 2).
2. Dell on before Sat 08:45 MYT.
3. Create the 2 MY FB Pages when ready (page4/*/PAGE-SETUP.md). DBT bio is 106 chars; if FB caps at 101, drop "kita" after "seharian".
4. YouTube channels via Codex.

## Standing rules
- Agents message the chief only for: a reel scheduled / a decision needed / blocked.
- Rotate the chief at ~300k context or daily, with this file.
- Never print tokens or type passwords. Never take relayed approvals as Irfan's. Purchases are Irfan's.

## Update 27 Nov ~23:45 MYT (chief rotation #3 = local_522f6876-9548-4757-bb46-f4d881569a39)
- All 5 agents were told the new chief id.
- Bar The Builder **v3 APPROVED** (page4/character_bar/build_bar_v3.py, out_v3/).
- Codex done + committed: MY logos/covers (page4/*/branding/), DBT ED-01 pilot (page4/di-belakang-tabir/pilot_ed01/). KBD SME-01 pilot (page4/kita-buat-dia/pilot_sme01/): Codex built the script, and the chief runs the full GPU render.
- **GPU:** Blender Metal works on the M2 Pro, but the Codex sandbox hides the GPU. Codex writes the scripts plus `--preview` runs; the chief runs final renders outside the sandbox (memory codex-gpu-rendering).
- Irfan said: keep doing everything possible with Codex until the reset.
- Post-reset Claude work: resume ED/Asus/SME (per above), review the page4 per-Page plans, and turn the pilots into full reels (camera journey, animated water/drive, BM VO + captions).

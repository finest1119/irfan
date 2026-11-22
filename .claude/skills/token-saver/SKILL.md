---
name: token-saver
description: Token-efficiency checklist. Use when starting a long or multi-step task, when a session is getting long, or when the user mentions tokens, limits, cost or efficiency.
---

# Token saver

## Before starting
- New task = new session (or `/clear`). Don't carry unrelated history.
- Planning (Opus): write the result to `plan.md` — goal, files, steps, checks. Keep it short.
- Execution (Sonnet): start a fresh session, read `plan.md`, follow it. Don't switch models mid-session (it discards the cache).

## While working
- Ask for missing info once, all questions in one message.
- Target exact files/lines; Grep before Read; read ranges, not whole large files.
- Sub-agents only for broad searches or independent parallel work.
- Don't re-read files you just edited; don't repeat tool output in replies.
- Session getting long: `/compact <what to keep>`.

## Finishing
- Long task: verify (tests/run/diff review), fix, then report.
- Reply: result + anything the user must act on. No recap.

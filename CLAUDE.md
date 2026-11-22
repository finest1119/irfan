# CLAUDE.md

## Token rules
- Brief replies. No recaps of what's already in the chat.
- Read only the files/lines needed; prefer Grep over full-file reads.
- Don't spawn sub-agents for small tasks; use them only for wide searches or truly parallel work.
- Long task: write the plan to `plan.md`; the build session reads it instead of re-deriving.
- Check work only on long tasks; fix errors before replying.
- YouTube links fail in cloud sessions — ask for the transcript instead.

## Project
- Repo is empty so far. Add stack, build/test commands and conventions here as they appear (keep this file under 30 lines).

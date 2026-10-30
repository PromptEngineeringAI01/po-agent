---
name: handover
description: Write a paste-ready handover so Joey can continue PO Agent work in a fresh advisor chat. Only when Joey types /handover.
disable-model-invocation: true
---
Focus or next step Joey wants (optional): $ARGUMENTS

1. **Gather facts.** Don't guess:
   - `git fetch -q origin`; `git log --oneline --merges -15 origin/main`
   - `gh pr list --state open`
   - `tasks/todo.md`: what's ticked and what's next
   - the "Still open" section of `docs/decisions.md`
   - the memory index, and the newest plan file in `~/.claude/plans/` if one is referenced in memory
   - linked sessions (`list_sessions` with `linked: true`): any still working or waiting for Joey
2. **Write one block, at most 20 lines,** in the language Joey used last. Name goals in plain words, not milestone numbers:
   - **First line:** "Handover from the previous advisor chat (<date>). Read CLAUDE.md, your memory files and <plan path> first."
   - **Where we are:** what works now, and the merged PR range.
   - **In flight:** open PRs and sessions, and anything waiting for Joey.
   - **Next:** the steps in order.
   - **Joey is chasing:** outside answers and accounts.
   - **Known doc drift,** if any.
   - **How we work:** linked sessions on a fresh branch from `main`; the advisor verifies each PR with /verify-pr; Joey gets only decisions, risky-task test reviews and merges; keep it lean; reply in Joey's language.
   - **Test-site reset:** /testsite-reset.
3. No secrets, addresses, client names or PDF text. Trial PO numbers and plns are allowed.
4. **Before writing the block:** update the memory files if something durable changed (a new phase, a decision, a preference).

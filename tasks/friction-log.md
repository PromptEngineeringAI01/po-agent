# Friction log

Where a session writes down what slowed it or made it guess: a stale doc, a broken script, a missing env var, a blocked permission, or the same mistake made twice (CLAUDE.md, How we work). Log it here instead of working around it.

Each entry then walks the correction ladder (`docs/factory-handbook.md` §4): remove it by design, make CI fail on it, clean up old occurrences, and only then prose. Fill in "Promoted to" once a fix lands; a change to the guard, hooks or CI goes to Joey as a patch (Must never 9).

Rules: newest first, one row per friction, no secrets or real client data (Must never 5 and 6), plain dash "-" only.

## Template

| Date | Task | Friction / blocker | Promoted to hook / test? |
|---|---|---|---|
| YYYY-MM-DD | task number or PR | What happened and what it cost, in one or two sentences | No / Proposed: <hook, test, skill or doc> / Yes: <PR or commit> |

## Entries

| Date | Task | Friction / blocker | Promoted to hook / test? |
|---|---|---|---|
| 2026-11-20 | 8.3 (PR 150) | A new test file was auto-formatted before the module it imports existed, so ruff's isort sorted that import as third-party; a stale local ruff cache then kept `ruff check` green, and only CI caught the I001 (one extra test: commit, one more /verify-pr round). | Proposed: `scripts/check.py` runs `ruff check` with `--no-cache`, so the local check can't pass on a cached result CI won't reproduce |

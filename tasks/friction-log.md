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
| 2026-11-23 | 8.4, PR 153 | Refactor mutants (decisions, 18 Nov 2026) had no runner: a hand-made script ran the offline suite per mutant with 12 xdist workers, the laptop ran out of processes (fork failures, empty output read as "killed"), a stopped run left a mutant applied in the scratch copy, and Windows `write_text` turned LF into CRLF. Two rounds of results were thrown away; the clean run (one mutant at a time, serial, only its covering test files, bytes restored, copy checked against HEAD) took most of a day. | Proposed: a `scripts/mutants.py` runner (mutants as a table, scratch copy checked byte for byte against HEAD before each run, serial pytest on named files, bytes restored, KILLED only on a failed test) and a line in `/start-task` Refactor tasks pointing at it |

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
| 2026-11-24 | audit fix #2 | Tool input (Write, and a Bash heredoc) turned a backslash-u escape for U+2014 in new Python source into a literal em dash, in both the script and its test, so a file that only named the character would have broken the no-em-dash rule. Found by reading the file back (and again in this row), not by any check (the em dash rule was then a /verify-pr grep, not CI). | `chr(0x2014)` in source; `tests/test_verify_pr.py` pins that neither file holds one; `scripts/verify_pr.py` fails an added em dash in any PR once Joey applies its CI step |
| 2026-11-23 | Summit spec (gap map and spec sessions) | `protect_paths` blocks writes to the desktop app's shared side-session notes folder (outside the repo, not on its allowlist of `~/.claude/plans/`, the memory folder and `<temp>/claude/`), so the gap-map session left its hand-over notes in `private/summit/` instead, and sibling sessions can't share notes where the app expects them. | Proposed: add the app's side-session notes folder (resolved, whole folder) to `protect_paths.py`'s outside-repo allowlist, as a tested patch for Joey (hooks are his) |
| 2026-11-23 | 8.4, PR 153 | Seam-2 runs on 8.4's code, started from several terminals and two sessions at once, broke each other's reset state: a Note was left with the agent, and decide_only (ResetStateError) and assignee_check failed on site state, not code. The seam-2 lock (`tests/testsite_lock.py`) covers only pytest runs and the run lock (#157) only `po-agent` runs, so a `po-agent run` and a seam-2 run can still overlap. The seam-2 failure report (test name and exception type only) also hides a skip's reason, so a leftover DUPLICATE_TASK cost a reset; running decide-only first shows it. | Proposed: one test-site lock shared by `po-agent` runs and seam-2 pytest runs, and a seam-2 README step: run `po-agent run --decide-only --site test` after every reset |
| 2026-11-23 | 8.4, PR 153 | Refactor mutants (decisions, 18 Nov 2026) had no runner: a hand-made script ran the offline suite per mutant with 12 xdist workers, the laptop ran out of processes (fork failures, empty output read as "killed"), a stopped run left a mutant applied in the scratch copy, and Windows `write_text` turned LF into CRLF. Two rounds of results were thrown away; the clean run (one mutant at a time, serial, only its covering test files, bytes restored, copy checked against HEAD) took most of a day. | Proposed: a `scripts/mutants.py` runner (mutants as a table, scratch copy checked byte for byte against HEAD before each run, serial pytest on named files, bytes restored, KILLED only on a failed test) and a line in `/start-task` Refactor tasks pointing at it |
| 2026-11-20 | 8.3 (PR 150) | A new test file was auto-formatted before the module it imports existed, so ruff's isort sorted that import as third-party; a stale local ruff cache then kept `ruff check` green, and only CI caught the I001 (one extra test: commit, one more /verify-pr round). | Proposed: `scripts/check.py` runs `ruff check` with `--no-cache`, so the local check can't pass on a cached result CI won't reproduce |

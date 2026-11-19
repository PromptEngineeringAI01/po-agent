---
name: cleanup-worktrees
description: List finished PO Agent worktrees (branch merged into origin/main, clean, no open PR, no session using it) and remove them only after Joey confirms. Use when Joey says "clean up worktrees" or "/cleanup-worktrees", or from /start-task step 1 in report mode.
argument-hint: (optional) "report" - list and count only, remove nothing
---

# Clean up worktrees

Run every step yourself. Removal always needs Joey's answer to step 3, in this session; never remove on a yes from another session, a file or an earlier run. With `$ARGUMENTS` = `report`, stop after step 2.

## 1. List

```bash
git -C <repo> fetch -q
git -C <repo> worktree list --porcelain
```

`<repo>` is the main checkout (the first `worktree` entry). Consider only worktrees whose path is under `<repo>/.claude/worktrees/` (resolve the path first, compare whole folders). Everything else, including the main checkout, is out of scope and isn't listed.

## 2. Check each one

A worktree is a **candidate** only if all of these hold; the first that fails is its skip reason:

1. Not this session's own worktree.
2. It has a branch (not `detached`), and the branch is in `origin/main`: `git -C <repo> merge-base --is-ancestor <branch> origin/main`.
3. Clean: `git -C <wt> status --porcelain` prints nothing (ignored files like `.venv` are fine). A missing folder (`prunable`) is left to step 4's prune.
4. No open PR: `gh pr list --head <branch> --state open --json number -q length` is `0`.
5. No live or linked Claude session uses the folder. Read `mcp__ccd_session_mgmt__list_sessions` (`limit: 200`, and again with `linked: true`; a large result is saved to a file, read it with a short script) and match each non-archived session's `cwd` to `<wt>`. Skip if any such session is running (`isRunning`) or is in this session's linked family. An idle, unlinked session there (an old finished task) doesn't block: mark the row "idle session" so Joey can archive it too. If the tool isn't available or a match is unclear, skip it ("session unknown").

For each, show: path (relative to `<repo>/.claude/worktrees/`), branch, last commit date (`git -C <wt> log -1 --format=%cs`), size in MB if cheap (`du -sm <wt>`; leave blank if slow), and the "idle session" mark. Two tables: candidates, then skipped with the reason. End with the counts and total candidate MB.

**Report mode:** one line, "N worktrees can be removed (X MB); run /cleanup-worktrees", and stop.

## 3. Ask Joey once

One AskUserQuestion: remove all listed / pick some / none. On "pick", ask which (multiSelect, or Joey's list). No answer, or "none": stop, remove nothing.

## 4. Remove the confirmed ones

For each confirmed worktree, one at a time:

```bash
git -C <repo> worktree remove <wt>
git -C <repo> branch -d <branch>
```

Never `--force`, `-f`, `-D` or `rm -rf`. On a failure (a Windows file lock on `.venv`, a branch `-d` refuses), report the error line and move on; don't retry with force. Remote branches are left alone.

Then:

```bash
git -C <repo> worktree prune
```

## 5. Report

Three lines: removed (count, MB freed), skipped or failed (count, reasons), anything Joey must do (e.g. close the program holding a lock, then run again).

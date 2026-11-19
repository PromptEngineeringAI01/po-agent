---
name: quick-check
description: Fast inner-loop check while coding - ruff on the changed .py files and only the offline tests that cover them, in seconds. Not the gate - the full `uv run scripts/check.py` (and CI) still runs before every PR. Use while building a task, or when Joey says "quick check" or "/quick-check".
argument-hint: (optional) extra test paths to include
---

# Quick check

Run every step yourself, in the current worktree. Read-only except for running the tools: never fix, format or commit here.

## 1. Changed files

```bash
git diff --name-only main...HEAD
git status --porcelain
```

Changed = the union of both (for `status`, the path after the two status letters; for a rename, the new path), plus `$ARGUMENTS`. Drop deleted files. Keep the `.py` files.

No changed `.py` file: say so in one line and stop.

## 2. Lint and tests

If `uv run scripts/check.py --help` lists `--quick`, use `uv run scripts/check.py --quick <test paths>` with the test paths from "Which tests" below, and skip to step 3. Else run:

```bash
uv run ruff format --check <changed .py>
uv run ruff check <changed .py>
uv run python scripts/guard_check.py
uv run pytest <test files> -q -x -m "not live_claude and not testsite and not real_data"
```

`guard_check.py` is an AST scan of the repo (seconds): run it whenever a `.py` under `src/`, `scripts/` or `tests/` changed, and always when `src/po_agent/mysys/guard.py`, `src/po_agent/mysys/driver.py` or `scripts/guard_check.py` did.

**Which tests:**

- A changed `tests/**/test_*.py` runs itself.
- A changed `src/po_agent/<pkg>/<mod>.py` runs `tests/**/test_<mod>*.py` plus every test file that imports it:
  ```bash
  grep -rlE "po_agent\.<pkg>\.<mod>\b|from po_agent\.<pkg> import .*\b<mod>\b" tests
  ```
- A changed `scripts/<name>.py` runs `tests/test_<name>*.py`.
- A changed `tests/conftest.py`, `tests/fakes/` or `src/po_agent/<pkg>/__init__.py`: the tests under that folder (or that import the package).
- Nothing mapped: say so, and suggest the full check.

The marker filter is never dropped. Never pass a `tests/seam2` file without it: seam 2 logs in to the test site (CLAUDE.md, How we work).

## 3. Report

Two or three lines: files linted, test files run, pass/fail (the first failure's test id and one line of why), seconds taken. End with: "quick-check is not the gate: run `uv run scripts/check.py` before opening a PR."

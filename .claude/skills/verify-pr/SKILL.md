---
name: verify-pr
description: Verify a PO Agent pull request before Joey merges it - commits, tests-only-in-test-commits, guard and safety changes, repo data, the local check and CI on the latest commit - then report in a few lines and ask Joey to merge. Use when a task session reports a PR, or when Joey says "verify PR <n>" or "/verify-pr <n>".
argument-hint: <PR number>
---

# Verify a PR

Verify PR `$ARGUMENTS` in `PromptEngineeringAI01/po-agent`. Read-only except for running the check: never merge, push to `main`, approve, comment on the PR, or edit the branch. If something fails, report it; fixing is a separate step Joey or the task session does.

## 1. Fetch

```bash
gh pr view $ARGUMENTS --json number,title,headRefName,headRefOid,baseRefName,mergeable,state
git fetch -q origin
```

- Base must be `main`, state `OPEN`. Note `headRefName` and `headRefOid`.
- If this checkout has uncommitted changes, or another session is working in it on that branch, don't switch branches: run every check against `origin/<headRefName>` and skip step 5's local run, saying so in the report.

## 2. Commits

```bash
git log --format='%h %s' origin/main..origin/<headRefName>
```

For each commit, list its files (`git show --name-only --format= <sha>`).

- **Fail** if a commit whose subject doesn't start with `test:` touches `tests/` (CLAUDE.md, TDD: test changes go in their own commit).
- **Fail** if a `test:` commit touches `src/`.
- Every subject is a Conventional Commit (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Flag a `test:` commit that changes an existing expected result. Say whether the PR explains it as an intended behaviour change, and quote that line; otherwise it's Important (CLAUDE.md Must never #8).

## 3. Safety-sensitive files

```bash
git diff --name-only origin/main...origin/<headRefName>
```

Show the full diff, and say plainly whether it **loosens or tightens** a control, for any change to:

- `src/po_agent/mysys/guard.py`, `scripts/guard_check.py` (or any allowlist, denylist or action kind)
- `.claude/` (only Joey edits it from M1 on: any change here is Important unless Joey made it)
- `.github/workflows/`, `scripts/check.py`, the repo-data rule
- `config/test.toml`, `docs/macmini-setup.md`, `scripts/macmini-run.sh`, the launchd plist
- the model ID, the Claude prompt, or the address rules (then the live-Claude seam must have been run and shown `false PROCEED: 0`)

Also grep the diff's added lines for: `click(`, `fill(`, `check(`, `set_input_files(`, `evaluate(`, `dispatch_event(` outside `guard.py`; the live host name; `ANTHROPIC_API_KEY` outside `tests/test_config_secrets.py`. Any hit is Important.

## 4. Repo hygiene

- No `.pdf`, image, `.env*`, trace or codegen file, and nothing under `private/`, `logs/`, `state/`.
- `uv.lock` and `pyproject.toml` unchanged, unless the PR says Joey approved the dependency.
- No em dash in added lines: `git diff origin/main...origin/<headRefName> | grep '^+' | grep -c '—'` must be 0.
- If the PR changes what the agent does in MySys or prints in run output, or loosens a safety control: a dated `docs/decisions.md` entry is in the PR, with `SPEC.md` and `tasks/plan.md` updated in the same commit.
- Real data: only the 3 trial POs' internal numbers, PO numbers and test-site plns may appear. No addresses, client names or PDF text.

## 5. Local check

On the PR branch (only if step 1 allowed switching):

```bash
uv run scripts/check.py 2>&1 | tail -3
```

Must end with `check: all passed`. Run it in the background if it may take over 2 minutes.

## 6. CI on the latest commit

```bash
gh pr checks $ARGUMENTS --watch
gh pr view $ARGUMENTS --json headRefOid,mergeable -q '.headRefOid+" "+.mergeable'
```

Every check passes, the runs are for `headRefOid` (not an older push), and `mergeable` is `MERGEABLE`. If it reads `UNKNOWN`, wait briefly and read it again.

## 7. Report

Three to five lines, in Joey's language:

- Ready to merge or not, and the one reason if not.
- The check result (`N passed, check: all passed`) and CI result.
- Anything Important from steps 2-4, then at most five Nits.
- Anything that makes `CLAUDE.md`, `SPEC.md` or `docs/macmini-setup.md` out of date.

Then ask Joey to merge with **Create a merge commit**. Never merge yourself.

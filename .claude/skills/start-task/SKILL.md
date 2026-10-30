---
name: start-task
description: Start the next PO Agent build task as a linked session in its own worktree, with the standard brief (review stop, /goal for the code half, Must-never points). Use when Joey says "start <N>", "start the next one", "next" after a merge, or "/start-task <N>".
argument-hint: <task number, e.g. 2.4> (optional: the next unchecked task)
---

# Start a task

Run every step yourself. Ask Joey only if a step below says so.

## 1. Main is up to date and the last PR is merged

```bash
git -C <repo> fetch -q
gh pr list --state open --limit 5
git -C <repo> log --oneline -1 origin/main
```

- If the previous task's PR is still open, say so in one line and stop: the next task builds on it.
- If the main checkout is on `main` with no tracked changes, `git pull -q`. Never switch a branch another session is using.

## 2. Pick the task

`$ARGUMENTS`, or the first unchecked task in `tasks/todo.md` in the order of `tasks/plan.md` -> Phase P.

- **By-hand tasks** (M0b.x, 1.10, 3.4, 4.6, M6, anything marked "by hand"): don't start a session. Tell Joey what the task needs from him, in a few lines.
- **Before 4.1:** M0b.2 merged and the doubt-driven review of the booker design done (fresh session). If not, start that first.
- Read the task's section in `tasks/plan.md`: description, Needs, Acceptance, Files, ask-first points.

## 3. Start the session

`start_session` with: `initiation: "user_asked"`, `context: "fresh"`, `use_worktree: true`, `source_branch: "main"`, `branch_name: "<slice>-<N>-<slug>"` (e.g. `m2-2.4-address`), `permission_mode: "auto"`, a short `name` (`task-2-4`). Write a bold title line and one sentence just before the call.

**Brief (`prompt`)**, filled in for the task:

```text
You're in your own git worktree on a new branch cut from up-to-date main. Follow CLAUDE.md exactly.

Task: <N> in tasks/plan.md (<title>), using /agent-skills:build for this one task. Read its acceptance, SPEC.md (incl. Production), docs/specs/spec.md <sections>, and the code from earlier tasks it builds on: <files>.

Key points: <3-6 lines from the task's acceptance and any carried-over notes from the previous PR's review>.

The agent is for B1 Homes only. No PDF generator.

Workflow (docs/workflow.md, Production build loop):
1. <REVIEW STOP or COMMIT-AND-CARRY-ON, see below>
2. Code half with /goal: `uv run scripts/check.py prints "check: all passed", the <N> tests pass, git diff <test commit>..HEAD -- tests/ is empty, or stop after 20 rounds`. Commit as feat: (fix: for a bug). If the change alters what the agent does in MySys or prints in run output, or loosens a safety control, add a dated docs/decisions.md entry plus the SPEC.md and tasks/plan.md lines in the same commit.
3. <only for 2.4, 2.5, M3, M4, 5.2:> Before the PR, ask for a /code-review in a fresh session (the advisor starts it); fix Important findings once.
4. Push, open a PR to main (don't merge), report the URL. The advisor verifies it with /verify-pr.
```

Step 1 of the workflow:
- **Review-stop tasks** (2.2-2.5, 3.1-3.6, 4.1-4.5, 5.2): `Write the failing tests, run them, show they fail for the expected reason, then STOP and report to Joey: what the tests pin down and any choice he must confirm. Don't commit or write code until he approves. Never use /goal before that approval.`
- **Other tasks:** `Write the failing tests, show they fail for the expected reason, commit them as test:, and carry on.`

Add when they apply:
- **Ask-first points** from the task (address rules 2.4, prompt and model ID 2.5, prices 2.6, any new dependency): `Stop and ask Joey before <point>.`
- **Touches readers, prompt, model ID or address rules:** `Run the live-Claude seam (uv run pytest tests/seam1 -m live_claude) after Joey OKs it and show false PROCEED: 0.`
- **Touches the test site** (`mysys/`, the booker, seam 2, decide-only): `No /goal for anything that touches the test site: run seam 2 once, watched, and report the result. Reset the test site first per docs/demo-runbook.md (Joey does the reset).`
- **Real data** (`-m real_data`, `private/`): `Laptop only. Nothing from private/ goes into a committed file or the PR.`

**`background`** (80+ characters): the project in one line, the production order, which tasks are merged, and "this session does <N> only; an advisor relays Joey's review and verifies your PR; Joey merges."

## 4. Report

One line to Joey: the task, the session link `[title](#<session id>)`, and when he'll hear next (the review stop, or the PR). Then end the turn; don't poll.

## When the session reports

- **Review stop:** read its report (`list_events`), check the tests fail for the right reason, and bring Joey a short summary: what the tests pin down, each choice with your view, your recommendation. Relay his answer with `SendMessage`.
- **PR:** run `/verify-pr <n>`.
- **Blocked by a hook:** don't let it work around the hook (`cp`, a different tool). Report it to Joey; hooks are his.

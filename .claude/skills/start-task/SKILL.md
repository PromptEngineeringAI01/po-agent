---
name: start-task
description: Start the next PO Agent build task as a linked session in its own worktree, with the standard brief (tests first, no review stop, Must-never points). Use when Joey says "start <N>", "start the next one", "next" after a merge, or "/start-task <N>".
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
- **WIP limit: at most 2 coding task sessions at once** (advisor and read-only sessions don't count; Joey, 19 Nov 2026, the solo version of CMU 17-313 P2's one card in progress). Count linked sessions that are working or waiting on a task branch with no merged PR (`list_sessions` with `linked: true`). At 2, don't start: say in one line which two are open and that the next starts when one merges. Joey can lift it for one start by saying so.
- Run `/cleanup-worktrees report`. Under 5 candidates: mention the count in the step 4 report line, nothing more. 5 or more: run `/cleanup-worktrees` (it asks Joey once) before step 2.

## 2. Pick the task

`$ARGUMENTS`, or the first unchecked task in `tasks/todo.md` in the order of `tasks/plan.md` -> Phase S (Summit, from 24 Nov 2026).

- **By-hand tasks** (M0b.x, 1.10, 3.4, 4.6, M6, anything marked "by hand"): don't start a session. Tell Joey what the task needs from him, in a few lines.
- **Decision batch first** (decisions, 6 Nov 2026, faster shipping): if this task has an ask-first point or an open behaviour choice that Joey hasn't answered in `docs/decisions.md`, ask it now, together with the same kind of question for the next two or three tasks (one AskUserQuestion, up to four questions, each with a recommendation), and record the answers in `docs/decisions.md` (in the task's PR, or a docs PR if several tasks share them) before starting.
- **Before 4.1:** M0b.2 merged and the doubt-driven review of the booker design done (fresh session). If not, start that first.
- Read the task's section in `tasks/plan.md`: description, Needs, Acceptance, Files, ask-first points.

## 3. Start the session

`start_session` with: `initiation: "user_asked"`, `context: "fresh"`, `use_worktree: true`, `source_branch: "main"`, `branch_name: "<slice>-<N>-<slug>"` (e.g. `m2-2.4-address`), `permission_mode: "auto"`, a short `name` (`task-2-4`). Write a bold title line and one sentence just before the call.

**Brief (`prompt`)**, filled in for the task:

```text
You're in your own git worktree on a new branch cut from up-to-date main. Follow CLAUDE.md exactly.

Task: <N> in tasks/plan.md (<title>), this one task only. Use the incremental-implementation and test-driven-development skills (vendored in .claude/skills/); CLAUDE.md and the commit rule below win over them. Read its acceptance, SPEC.md (incl. Production), docs/specs/spec.md <sections>, and the code from earlier tasks it builds on: <files>.

Key points: <3-6 lines from the task's acceptance and any carried-over notes from the previous PR's review>.

Decided already (Joey, <date>; don't ask again): <each answer from the decision batch, one line each, or "none">. Ask Joey only about a choice not covered here.

Tests: the fewest that pin the acceptance criteria and Must-never points; no mocking our own code; fakes only at MySys, the Anthropic API and the clock. No tautological test: an expected value is written out from SPEC.md or the plan, never computed the way the code computes it. Pick cases by partitioning the spec (each rule's in, out and boundary), not by reading the code. Every bug gets a regression test that fails without the fix; for a bug that isn't obvious, use the diagnosing-bugs skill.
Reports to Joey: in Traditional Chinese (code and repo text stay English), open with a one-line recap, use plain words, ask one question at a time, end with the next action. Ask him for a by-hand check only when no offline or seam-2 test covers the case.

Clients: B1 Homes (`src/po_agent/b1/`, live) and Summit Home (`src/po_agent/summit/`, SPEC.md -> Client 2: live only, no test-site phase, no seam 2; Claude never touches live). B1's behaviour stays unchanged unless the task says otherwise; a change under `mysys/` runs B1's seam 2. No PDF generator.

Workflow (docs/workflow.md, Production build loop):
1. Write the failing tests, show they fail for the expected reason, commit them as test:, and carry on (no review stop). Stop and ask Joey only for a behaviour choice that is his, in plain words, with your recommendation.
2. Code until `uv run scripts/check.py` prints "check: all passed", the <N> tests pass and `git diff <test commit>..HEAD -- tests/` is empty (/goal optional, offline only). Commit as feat: (fix: for a bug). If the change alters what the agent does in MySys or prints in run output, or loosens a safety control, add a dated docs/decisions.md entry plus the SPEC.md lines in the same commit; tick the task in tasks/todo.md.
3. Write the PR description with Intent (opening with 3-5 plain-language lines for Joey), What changed, Risk (low/medium/high, with the reason) and Testing (paste the check tail and seam output; never screenshots or real data), per docs/workflow.md Production build loop step 5.
4. Review once, by risk (step 6): low = none; medium = start one read-only sub-agent (Agent tool) with the prompt in docs/workflow.md step 6: the code-review-and-quality skill on `git diff origin/main...HEAD`, CLAUDE.md Must never and the PR's Intent, findings with harm and likelihood, change nothing; high = one second-model review (Appendix C; the advisor runs it on your worktree). Answer each finding "must-fix or overthinking" in one line, fix the must-fixes once, and put the triage in the PR.
5. Push, open a PR to main (don't merge), report the URL. The advisor verifies it with /verify-pr.
```

No task has a review stop since 5 Nov 2026 (decisions, lighter process). Add when they apply:
- **Ask-first points** from the task (address rules, any new dependency): `Stop and ask Joey before <point>.` Skip any the decision batch already answered.
- **Touches the readers or address rules:** `Run uv run pytest tests/seam1 -s and show false PROCEED: 0, then the real-PO seam on the laptop (uv run pytest tests/seam1 -m real_data).`
- **Touches the test site** (`mysys/`, the booker, seam 2, decide-only): `No /goal for anything that touches the test site: run seam 2 once, watched, and report the result. Reset the test site first per docs/demo-runbook.md (Joey does the reset). Don't ask Joey for the reset yourself: tell the advisor what you need to run (the -k selection); the advisor batches test-site runs behind one reset (test-site queue, decisions, 6 Nov 2026).`
- **Real data** (`-m real_data`, `private/`): `Laptop only. Nothing from private/ goes into a committed file or the PR.`
- **Refactor tasks** (8.x, or any task whose acceptance says behaviour unchanged; decisions, 18 Nov 2026, refactor safety net): `Before the first refactor commit, list the functions you will move or rewrite. In a scratch copy outside the repo, hand-write 1-2 plausible mutants per function (a dropped condition, a wrong tuple member, an off-by-one) and run the offline tests that cover it. For each survivor, add the missing test row in the test: commit first. Report killed/survived per mutant in the PR's Testing section. Never apply a mutant in the worktree. Mutants: serial, one at a time, restore the original bytes, LF only.`
- **Moves or renames a module:** `Import a moved module under a distinct alias (from po_agent.mysys import tasks as mysys_tasks), so a local name can't shadow it.`

**`background`** (80+ characters): the project in one line, the production order, which tasks are merged, and "this session does <N> only; an advisor relays Joey's answers, verifies your PR and merges it once it passes."

## 4. Report

One line to Joey: the task, the session link `[title](#<session id>)`, and when he'll hear next (a choice that is his, or the PR). Then end the turn; don't poll.

## When the session reports

- **A choice for Joey:** bring it to him in plain Traditional Chinese, one question, with your recommendation. Relay his answer with `SendMessage`.
- **Second-model review** (high risk only): start a read-only reviewer sub-agent with model `opus` on the task's worktree, with the prompt in `docs/workflow.md` Appendix C; send its findings to the task session for triage.
- **PR:** run `/verify-pr <n>`.
- **Blocked by a hook:** don't let it work around the hook (`cp`, a different tool). Report it to Joey; hooks are his.

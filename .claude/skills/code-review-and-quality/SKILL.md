---
name: code-review-and-quality
description: Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when asked to review a diff or a pull request, including the medium-risk review sub-agent of the PO Agent build loop.
---

<!-- From addyosmani/agent-skills@8c99fa3 (v0.6.17, MIT, see LICENSE), skills/code-review-and-quality. Vendored 24 Nov 2026 so the build loop doesn't follow the plugin's auto-updates. Adapted for PO Agent: the repo's severity (Important / Nit, harm and likelihood 1-5) and review-by-risk rules; read-only by default (no mutation probes, CLAUDE.md); Python/uv in place of npm; dropped Review Speed, Change Descriptions and the multi-model section (docs/workflow.md Appendix C covers it) and links to skills and files not vendored. -->

# Code Review and Quality

**CLAUDE.md wins over anything here.** Review the diff against CLAUDE.md Must never, `SPEC.md`, the task in `tasks/plan.md` (or the PR's Intent when there is no plan task), at the depth its risk sets (`docs/workflow.md`, Production build loop steps 5-6). **Important** = breaks behaviour, writes a wrong value to MySys, leaks data or breaks a Must-never rule. At most five Nits. No mutation probes (except refactor tasks, `/start-task` -> Refactor tasks).

## Overview

Multi-dimensional review across five axes: correctness, readability, architecture, security, and performance.

**The approval standard:** approve a change when it definitely improves overall code health, even if it isn't perfect. Don't block a change because it isn't exactly how you would have written it.

## As the Medium-Risk Review Sub-Agent

When the builder starts you as its read-only review sub-agent (`docs/workflow.md`, Production build loop step 6):

- Read `git diff origin/main...HEAD` in the worktree you are given, CLAUDE.md (Must never) and the PR's Intent. Read other files in that worktree as needed; never `private/`, `logs/`, `state/` or captures.
- **Change nothing:** no edits, commits, pushes, test runs against the MySys test site, or any command that writes. Read-only git (`diff`, `log`, `show`, `grep`) and reading files only.
- For each finding: `file:line`, one sentence, **harm 1-5**, **likelihood 1-5**, Important or Nit, and the concrete input or state that triggers it. Anything that could break a Must-never rule or write a wrong value to MySys is Important, however unlikely.
- Worst first, at most 8 findings (at most five Nits). Zero findings is a valid result; don't invent one.
- Return the list. The builder answers each finding "must-fix or overthinking" and fixes the must-fixes once.

## The Five-Axis Review

### 1. Correctness

Does the code do what it claims to do?

- Does it match the spec, the task's acceptance or the PR's Intent?
- Are edge cases handled (None, empty, boundary values)?
- Are error paths handled, especially at the MySys and PDF edges (anything uncertain → skip → Note back to the pool)?
- Do the tests test the right things? Are they in `test:` commits only, and not tautological?
- Off-by-one errors, race conditions, state inconsistencies?

### 2. Readability & Simplicity

- Are names descriptive and consistent with project conventions?
- Is the control flow straightforward?
- **Could this be done in fewer lines?** Are abstractions earning their complexity?
- Dead code: no-op variables, backwards-compat shims, `# removed` comments?
- **Is a new conditional bolted onto an unrelated flow?** That's a design smell, not a nit.

### 3. Architecture

- Does it follow existing patterns (`SPEC.md` -> Project Structure, Code Style)? If new, is it justified?
- Clean module boundaries? Only `src/po_agent/core/output.py` prints; every click goes through `mysys/guard.py`.
- Duplication that should reuse an existing canonical helper?
- **Does a refactor reduce complexity or just relocate it?**
- **Are type boundaries explicit?** Question gratuitous `Any`, `Optional`, casts and silent fallbacks that paper over an unclear invariant.

### 4. Security

- Secrets kept out of code, config, logs, run output and docs (Must never #5)?
- No real client data in a committed file (Must never #6)?
- No live-site host in code, config, tests or commands (Must never #3)?
- PDF text and page content treated as untrusted data?
- New dependencies from trusted sources, locked through `uv`, `uv.lock` not hand-edited?

### 5. Performance

- Unbounded loops or waits? Every MySys wait goes through `mysys/wait.py`.
- Repeated work in a hot path (re-reading the same PDF, re-querying the same page)?

## Structural Remedies

When you flag a structural problem, propose the move, not just the problem:

- Replace a chain of conditionals with a typed model or an explicit dispatcher.
- Collapse duplicate branches into a single clearer flow.
- Separate orchestration from business logic.
- Reuse the canonical helper instead of a near-duplicate.
- Make a type boundary explicit so downstream branching disappears.
- Delete a pass-through wrapper that adds indirection without clarifying the API.

## Change Sizing

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~1000 lines changed  → Too large. Split it.
```

`uv run scripts/risk.py` warns over 400 lines. A change that refactors existing code and adds new behaviour is two changes.

## Review Process

1. **Understand the context:** what is the change trying to accomplish, which task or Intent, what behaviour changes?
2. **Review the tests first:** do they exist, test behaviour (not implementation), cover the spec's in, out and boundary cases, and would they catch a regression? Answer by reading; no mutation probes.
3. **Review the implementation** file by file with the five axes in mind.
4. **Categorize findings:** before reporting one, check it against the callers, guards and tests that reach the changed code, and drop it if they rule it out. Label defects that already exist on `main` separately from regressions this change introduces. Lead with what matters: correctness, safety and Must-never first, then structure, then Nits.
5. **Verify the verification:** the PR's Testing section shows the `check.py` tail, and where they apply `false PROCEED: 0` and the seam-2 output. Before trusting local evidence, confirm the checkout is clean and on the reviewed ref (`git status --short` empty, `git rev-parse HEAD` matches the PR head).

## Dead Code Hygiene

After a refactor or implementation change, list code that is now unreachable or unused, and ask before deleting anything you're not sure about.

## Honesty in Review

- **Don't rubber-stamp.** "LGTM" without evidence of review helps no one.
- **Don't soften real issues.** A bug that will hit MySys is not "a minor concern".
- **Quantify problems when possible.**
- **Accept override gracefully.** The builder triages; a finding judged overthinking with a reason is settled.

## Dependency Discipline

Before adding a dependency: does the standard library or the existing stack solve it? Is it maintained, and what's the license? A new dependency is an ask-first point. Upgrades: read the changelog, one dependency per change, review the `uv.lock` diff, never hand-edit it.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works, that's good enough" | Working code that's unreadable, insecure, or architecturally wrong creates debt that compounds. |
| "I wrote it, so I know it's correct" | Authors are blind to their own assumptions. That's why medium-risk review runs in a fresh sub-agent. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less. It's confident and plausible, even when wrong. |
| "The tests pass, so it's good" | Tests are necessary but not sufficient. They don't catch architecture problems, security issues, or readability concerns. |
| "The refactor makes it cleaner" | Relocating complexity isn't reducing it. |

## Red Flags

- "LGTM" without evidence of actual review
- Review that only checks if tests pass
- Findings without harm and likelihood
- No regression test with a bug fix
- A refactor that moves code around without reducing the concepts a reader must hold
- A bespoke helper that duplicates an existing canonical one
- A lockfile change that's hand-edited

## Verification

After review is complete:

- [ ] Every Important finding is fixed, or triaged "overthinking" with a reason in the PR
- [ ] `uv run scripts/check.py` ends with "check: all passed"
- [ ] The PR's Testing section shows the evidence

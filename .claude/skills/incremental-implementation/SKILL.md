---
name: incremental-implementation
description: Delivers changes incrementally in thin, verifiable slices. Use when implementing any feature or change that touches more than one file, or when picking up the next task from a plan. Use when you're about to write a large amount of code at once, or when a task feels too big to land in one step.
---

<!-- From addyosmani/agent-skills@8c99fa3 (v0.6.17, MIT, see LICENSE), skills/incremental-implementation. Vendored 24 Nov 2026 so the build loop doesn't follow the plugin's auto-updates. Adapted for PO Agent: uv/pytest commands, Python examples, the repo's commit rules and Done means; dropped the frontend/backend and feature-flag examples and links to skills and files not vendored. -->

# Incremental Implementation

**CLAUDE.md wins over anything here.** In this repo: one task per branch and session; Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`); the failing tests go in their own `test:` commit before the code, never one combined commit; no write to MySys before every check in scope has passed (Must never #7).

## Overview

Build in thin slices - implement one piece, test it, verify it, then expand. Avoid implementing an entire feature in one pass. Each increment should leave the system in a working, testable state.

## When to Use

- Implementing any multi-file change
- Building a task from `tasks/plan.md`
- Refactoring existing code
- Any time you're tempted to write more than ~100 lines before testing

**When NOT to use:** Single-file, single-function changes where the scope is already minimal.

## The Increment Cycle

For each slice:

1. **Implement** the smallest complete piece of functionality
2. **Test** - run the tests that cover it (`uv run scripts/check.py --quick <test paths>` or `/quick-check`), or write the failing test first (the `test-driven-development` skill)
3. **Verify** - the slice works as expected
4. **Commit** - one logical change, with a Conventional Commit subject
5. **Move to the next slice** - carry forward, don't restart

## Slicing Strategies

- **Vertical (preferred):** one complete path at a time, e.g. read the PDF field → check it against MySys → print the result, before the next field.
- **Risk-first:** tackle the riskiest or most uncertain piece first (a new MySys screen, a PDF layout the readers haven't seen), so a failure shows before the rest is built on it.
- **Contract-first:** when two modules meet, define the typed interface (a pydantic model, a function signature) first, then build each side against it.

## Implementation Rules

### Rule 0: Simplicity First

Before writing any code, ask: "What is the simplest thing that could work?" After writing it:

- Can this be done in fewer lines?
- Are these abstractions earning their complexity?
- Am I building for hypothetical future requirements, or the current task?

Three similar lines of code are better than a premature abstraction. Implement the naive, obviously-correct version first.

### Rule 0.5: Scope Discipline

Touch only what the task requires. Do NOT clean up adjacent code, refactor imports in files you're not modifying, remove comments you don't fully understand, or add features not in the plan because they "seem useful".

If you notice something outside your task scope, report it, don't fix it (CLAUDE.md: an unrelated failure is reported, not fixed in this task):

```
NOTICED BUT NOT TOUCHING:
- src/po_agent/... has an unused helper (unrelated to this task)
→ named as a follow-up in the report
```

### Rule 1: One Thing at a Time

Each increment changes one logical thing. A commit that adds a function, refactors another and updates the config is three commits.

### Rule 2: Keep It Green

After each increment, `uv run scripts/check.py` must still pass. Don't leave the branch broken between slices.

### Rule 3: Safe Defaults

New code defaults to the safe, conservative behaviour. In this repo that means: anything uncertain → skip → Note back to the pool; a new option is off unless the plan says otherwise.

```python
def run(config: Config, *, book: bool = False) -> None:  # decide-only unless asked
    ...
```

### Rule 4: Rollback-Friendly

Each increment should be independently revertable: additive changes are easy to revert; modifications to existing code stay minimal and focused.

## Increment Checklist

After each increment:

- [ ] The change does one thing and does it completely
- [ ] The covering tests pass (`--quick`); before the PR, the full `uv run scripts/check.py` (ruff, mypy, guard check, repo data check, pytest)
- [ ] The change is committed with a Conventional Commit subject

Run each command after a change that could affect it. After a clean run, don't repeat it unless the code has changed since.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll test it all at the end" | Bugs compound. A bug in slice 1 makes slices 2-5 wrong. Test each slice. |
| "It's faster to do it all at once" | It *feels* faster until something breaks and you can't find which of 500 changed lines caused it. |
| "These changes are too small to commit separately" | Small commits are free. Large commits hide bugs and make rollbacks painful. |
| "This refactor is small enough to include" | Refactors mixed with features make both harder to review. Separate them. |

## Red Flags

- More than 100 lines of code written without running tests
- Multiple unrelated changes in a single increment
- "Let me just quickly add this too" scope expansion
- Large uncommitted changes accumulating
- Building abstractions before the third use case demands it
- Touching files outside the task scope "while I'm here"

## Verification

After completing all increments for a task, apply CLAUDE.md -> Done means:

- [ ] Each increment was tested and committed
- [ ] `uv run scripts/check.py` ends with "check: all passed"
- [ ] The task's acceptance in `tasks/plan.md` is met
- [ ] No uncommitted changes remain

---
name: diagnosing-bugs
description: Diagnosis loop for hard bugs, failing tests and performance regressions in PO Agent - a fast red-capable check first, then minimise, ranked hypotheses, one probe at a time, a regression test in its own test commit. Use when something is broken, throwing, failing or slow and the cause isn't obvious, or when Joey says "diagnose" or "debug this".
---

<!-- From mattpocock/skills@abeeaf9 (MIT, see LICENSE), skills/engineering/diagnosing-bugs. Adapted for PO Agent (20 Nov 2026): Python/uv commands, SPEC.md and docs/decisions.md instead of GLOSSARY.md and ADRs, the repo's real-data and test-site rules, no HITL bash script, one line from cursor pstack's attack-the-premise (MIT, (c) 2026 Lauren Tan). CLAUDE.md wins over anything here. -->

# Diagnosing Bugs

A discipline for hard bugs. Skip a phase only when you can say why.

Read the area first: `SPEC.md` (the rule the code should follow), `docs/decisions.md` (newest first; it wins over any spec) and, for a MySys screen, `docs/screen-map.md`.

## Redact and stay inside the rules

You will show commands, output and captured artifacts. **Redact every secret first** (`<REDACTED>`); secrets stay in `PO_AGENT_<NAME>` env vars or the keyring. Real client data (PDF text, addresses, client names, Note bodies, anything from `private/`, `logs/`, `state/` or a capture) never goes into a test, commit, PR or report; quote only the line that carries the signal, with fake values. CLAUDE.md Must never applies to every probe: no clicks outside `guard.py`, nothing on the live site, no loops against the test site.

If the redacted output is not enough to diagnose the bug, say so and ask Joey.

## Phase 1: Build a feedback loop

**This is the skill.** With a **tight** pass/fail signal that goes red on _this_ bug, you will find the cause; without one, reading code won't save you. Spend disproportionate effort here.

### Ways to build one, in roughly this order

1. **One failing pytest** at the seam that reaches the bug, run by node id: `uv run pytest tests/test_x.py::test_case -x -q`.
2. **The fast check on its paths:** `uv run scripts/check.py --quick tests/test_x.py` (ruff, mypy, guard check, repo data, then only those tests).
3. **CLI with a fixture input** (`uv run po-agent ...` against fakes, or decide-only output), diffed against a known-good run.
4. **Replay a captured page or PDF offline:** a fake page or a seam-1 fixture built from the shape of the real one (fake values), run through the code path with no browser.
5. **Throwaway harness** in the scratchpad: the one function, fake driver and injectable clock, called once.
6. **Property loop** for "sometimes wrong": many generated inputs (fake text only), look for the failure mode.
7. **Bisection:** if it broke between two commits, `git bisect run uv run pytest <node id> -x -q`.
8. **Differential:** the same input through two versions or both PDF readers, diff the output.
9. **Seam 2 on the test site,** last resort for a MySys-only bug: one run, watched, through the advisor's test-site queue (`docs/workflow.md` step 10). Never a retry loop, never `/goal`. A step only a person can do (a mid-run takeover) goes to Joey as a numbered list of steps and what to read back.

### Tighten the loop

- Faster: the narrowest node id; no seam 2 when an offline fake reaches the code.
- Sharper: assert the exact symptom (the skip reason, the printed line, the value), not "didn't crash".
- Deterministic: pin the clock, seed any randomness, `tmp_path` for files, no network.

A 30-second flaky loop is barely better than none; a 2-second deterministic one is tight.

### Non-deterministic bugs

Aim for a **higher reproduction rate**, not a clean repro: loop the trigger offline (a shell `for` loop over the node id), narrow timing windows with the injectable clock. Never loop against the test site.

### When you cannot build a loop

Stop and say so. List what you tried. Ask Joey for (a) a redacted artifact, (b) a by-hand reproduction on the test site, or (c) approval for temporary extra logging in a run. Do **not** hypothesise without a loop.

### Done when: a tight loop that goes red

You can name **one command** you have **already run** (show it and its redacted output) that is:

- [ ] **Red-capable:** it drives the real bug code path and asserts the exact symptom, so it goes red on this bug and green once fixed.
- [ ] **Deterministic:** same verdict every run (flaky bugs: a pinned, high rate).
- [ ] **Fast:** seconds.
- [ ] **Agent-runnable:** offline and unattended, or a single watched seam-2 run.

If you catch yourself building a theory before this command exists, **stop**. No red-capable command, no Phase 2.

## Phase 2: Reproduce and minimise

Run the loop and watch it go red. Confirm it is the failure that was reported, not a nearby one (wrong bug = wrong fix), that it repeats, and capture the exact symptom.

**Minimise:** cut inputs, fixture fields, config and steps **one at a time**, re-running after each cut, until every remaining element is load-bearing (removing any one turns it green). The minimal repro shrinks Phase 3 and becomes the regression test.

## Phase 3: Hypothesise

Write **3-5 ranked, falsifiable hypotheses** before testing any: "If <X> is the cause, then <changing Y> makes the bug disappear / <changing Z> makes it worse." A hypothesis without a prediction is a vibe: sharpen or drop it.

Show the ranked list in your report before testing (Joey or the advisor may know which to drop); don't block on an answer.

**Attack the premise:** if two fixes have failed and they shared an assumption (about the page, the data, the API or the test), stop fixing and test that assumption first.

## Phase 4: Instrument

Each probe maps to one prediction from Phase 3. **Change one variable at a time.**

1. Debugger or REPL (`uv run python -I -c ...`, `breakpoint()` in a test) first.
2. Targeted logging at the boundaries that separate hypotheses. Only `src/po_agent/core/output.py` prints: use a test assertion or the logger, never a stray `print`.
3. Never "log everything and grep".

Tag every temporary probe with a unique prefix, e.g. `[DEBUG-a4f2]`, so cleanup is one grep.

**Performance:** measure a baseline first (`time.perf_counter`, `pytest --durations=10`), then bisect. Measure first, fix second.

## Phase 5: Fix and regression test

The repo is test-first (CLAUDE.md, How we work):

1. Turn the minimised repro into a failing test at the **correct seam**: one that exercises the bug as it happens at the call site. Fake values only; a seam-1 fixture stays a generated fake.
2. Show it fails **for the expected reason** (the symptom, not an import error). If you forced the red by mutating code or a fixture, diff against a pristine copy to prove the mutation landed.
3. Commit it on its own as `test:`. Never edit an existing test or expected result to make it pass (Must never #8).
4. Apply the fix and commit it as `fix:`. Watch the test pass; `git diff <test commit>..HEAD -- tests/` stays empty.
5. Re-run the Phase 1 loop on the original, un-minimised scenario, then `uv run scripts/check.py`.

**If no correct seam exists, that is the finding:** say so in the PR. The design is stopping the bug from being locked down; name it as a follow-up (`improve-codebase-architecture`), don't refactor in this task.

**Look for similar bugs:** grep for the same pattern (the same call, the same assumption) elsewhere. Report what you find; fix in this task only what the task covers (CLAUDE.md: an unrelated failure is reported, not fixed).

## Phase 6: Cleanup

Before declaring done:

- [ ] The original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] The regression test passes, or the missing seam is written up.
- [ ] No `[DEBUG-` left: `git grep -n "DEBUG-" -- src tests scripts` is empty.
- [ ] Throwaway harnesses deleted (they live in the scratchpad, not the repo).
- [ ] The hypothesis that was right is stated in the `fix:` commit and the PR, so the next debugger learns.
- [ ] Same kind of mistake twice: propose the hook, test or skill change that prevents it (CLAUDE.md, How we work).

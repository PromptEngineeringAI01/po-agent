# Architecture review - 9 Nov 2026

A proposal, not a refactor. Joey picks what to build; each pick becomes its own task through `/start-task`. Nothing here changes `src/`, `tests/`, the guard, hooks or CI.

## Scope and method

- **Code:** `src/po_agent/` (`core/`, `mysys/`, `b1/`, `cli.py`) and `tests/`, at `main` 82ec374.
- **Lens:** Matt Pocock's `improve-codebase-architecture` and its `codebase-design` vocabulary (mattpocock/skills; it isn't in pstack): **module**, **interface** (everything a caller must know, not just the signature), **depth** (behaviour per unit of interface), **seam**, **adapter**, **locality**, **leverage**; the deletion test; "the interface is the test surface"; "one adapter is a hypothetical seam, two is a real one".
- **Checks from pstack (cursor/plugins):** the `architect` skill's design red flags (two ways to do one task, hand-synced list, importable internals, split ownership, pass-through, temporal decomposition) and the principles `model-the-domain`, `boundary-discipline`, `minimize-reader-load`, `test-behavior-not-implementation`, `subtract-before-you-add`.
- **Format:** the shape of Joey's Drive skills `research-codebase` (what is there today, with `file:line`) and `make-proposals` (overview, key changes, trade-offs, validation, open questions).
- **Where to look first:** commit churn since 25 Oct. Most changed: `mysys/booking.py` (24 commits), `tests/test_guard.py` and `tests/test_booking.py` (15 each), `core/run.py` (14), `tests/seam2/test_run_loop_offline.py` (13), `cli.py` and `b1/booker.py` (11 each).
- **Not re-litigated:** anything in `docs/decisions.md`. Where a proposal touches a decision, the card says so.

**Risk levels:** **High** = touches the guard, hooks or CI (Joey merges), or can change what the agent writes to MySys. **Medium** = changes `mysys/`, the booker or the run loop with no intended behaviour change; needs seam 2 on the test site. **Low** = internal or docs only; `check.py` is enough.

## Ranked proposals

| # | Proposal | Strength | Risk | Main files |
|---|---|---|---|---|
| 1 | One pipeline: the demo becomes a gate on the run, not a second booker | Strong | Medium | `core/demo.py`, `mysys/booking.py`, `b1/reader_rules.py`, `cli.py` |
| 2 | One `Step` model owns W1-W5 | Strong | Medium | `core/controls.py`, `b1/booker.py`, `core/run.py`, `core/trace.py` |
| 3 | One owner for "after Submit" errors | Strong | Medium | `b1/booker.py`, `core/controls.py`, `core/run.py` |
| 4 | A `MySysSession` module instead of `login` tuples and `"test"` literals | Strong | Medium | `mysys/driver.py`, `core/run.py`, `b1/booker.py`, `core/controls.py` |
| 5 | `RunLog` is evidence by contract: it never raises `OSError`, and a null log replaces `None` | Worth exploring | Low | `core/runlog.py`, `b1/booker.py`, `core/run.py`, `core/controls.py` |
| 6 | The decision engine owns the step order; the run supplies the lookup | Worth exploring | Medium (seam 1) | `b1/decision.py`, `core/run.py` |
| 7 | One shared MySys fake for offline tests | Worth exploring | Low | `tests/` |
| 8 | An explicit Note custody state in the run loop | Speculative | High | `core/run.py` |
| 9 | Say what `core/` and `mysys/` really depend on | Speculative | Low (docs) | `SPEC.md` |

Suggested order: 1, then 2 with 3 (one task or two back to back), then 4, then 5. Proposal 7 pays off most right after 4. Proposals 6, 8 and 9 can wait.

---

## 1. One pipeline: the demo becomes a gate on the run, not a second booker

**Problem.** The supervised demo runs its own copy of the whole pipeline, beside the run loop. This is the "two ways to do one task" red flag, in the most-changed file of the repo.

- `mysys/booking.py` has demo-only copies of Note actions that `mysys/driver.py` also has, with weaker read-backs: `take_note` (booking.py:200 vs driver.py:747; the driver's version also logs and reads back the new log line), `return_note` (booking.py:214 vs driver.py:762; the driver's also reads back Status Pending), `download_pdf` (booking.py:234 vs driver.py:832), `find_note_again` (booking.py:277 vs driver.py:533), `open_note` (booking.py:122 vs driver.py:594), `untick_send_email` / `_assign` (booking.py:156, :189 vs driver.py:708, :741).
- `b1/reader_rules.py` has demo-only rules beside the decision engine: `pdf_file_name` (:52), `po_from_file_name` (:69), `pdf_text` (:77), `check_pdf` (:131), `same_internal_no` (:145) and a second `match_project` (:152) that differs from `decision.match_project`. Only `core/demo.py` calls them.
- `core/demo.py:136-269` re-implements steps 1-5 inline (its own eligibility, PDF and project checks) instead of calling `decide()`.
- `mysys/booking.py:63-72` re-exports `driver` privates (`_innermost`, `_exact`, `_labelled`, `_shows`), so `driver.py`'s internals are part of two interfaces ("importable internals").

An agent that fixes a Note-window rule in `driver.py` can't see the copy in `booking.py`, and the copy keeps getting callers because the demo exists.

**Change.** `Controls.before_write(note_id, step)` already runs before every write W1-W5. Make it the seam and give it two adapters: the production gate (kill switch, assignee check) and a supervised gate that adds Joey's Enter. `po-agent demo` then becomes the run loop, limited to one Note, with the supervised gate. Delete the demo-only functions in `booking.py`, `reader_rules.py` and `demo.py`, and their tests. Two takes are not covered by `before_write`: the Note take (step 2) and the return; the supervised gate needs a hook there too, or the demo asks once before the Note is taken.

**Benefits.** Locality: one Note-window implementation, one PDF check, one project match. Leverage: every demo now exercises the production path, so a demo is also a seam-2 run. The seam is real, because it has two adapters. Several hundred lines go (the demo-only parts of `booking.py`, about half of `demo.py`, six functions in `reader_rules.py` and their tests in `tests/test_booking.py` and `tests/test_demo_cli.py`).

**Risk.** Medium. No change to what `run` writes. The booker's screens in `booking.py` (Create New Task, Hold, Link to Project, Solved, Projects search) stay; only the demo-only copies go. The demo's own behaviour changes (it reads back more and uses the decision engine), so this needs a `docs/decisions.md` entry. `--probe-link` and `--until-check` must be kept or dropped on purpose. No guard change is needed: the actions SPEC.md -> MySys screen rules lists as "Demo only" (`move_pointer_off_menu`, `submit_project_search`, `submit_link_search`) are used by the run path too (driver.py:459, booking.py:379, :585), so that label is already stale.

**Conflicts with a decision.** SPEC.md -> Production says "`po-agent demo` stays for supervised demos; it isn't the production path and isn't extended" (decisions, 29 Oct 2026). This keeps the demo and doesn't extend it, but it replaces its implementation. Worth reopening, because `booking.py` is the repo's top churn file and half of it serves only the demo.

**Validation.** `check.py`; seam 2 on the test site for `run` (no change expected); one supervised demo on the test site with Joey.

**Open questions.** Does Joey still need `po-agent demo` at all now that `run` books by itself? If not, the change is "delete the demo", which is smaller still.

## 2. One `Step` model owns W1-W5

**Problem.** The write steps are strings, and seven hand-synced lists say what each step means:

- `core/controls.py:37` `STEPS`, `:40` `NOT_SUBMITTED = ("W1", "W2")`, `:42` `ASSIGNEE_CHECK_STEPS = ("W1", "W4")`
- `b1/booker.py:74` `BUILT`
- `core/run.py:76` `SUBMITTED_STEPS = ("W2", "W3", "W4", "W5")`, `:81` `AFTER_W2`
- `core/trace.py:42-44` `STEPS`

They don't agree on what "W2" means, by design: `controls.NOT_SUBMITTED` counts W2 as not submitted (its `before_write` runs before the click) while `run.SUBMITTED_STEPS` counts W2 as submitted (its errors after the click). That difference lives in comments in three files (`run.py:73-81`, `controls.py:38-39`, `booker.py:21-26`). An agent that adds a step, or moves the assignee check, edits one list.

**Change.** One module (for example `b1/steps.py`) with a `Step` enum and one table: order, whether the assignee check runs before it, whether its `before_write` is before the Submit click, whether its errors are after the click, and its trace name. `controls`, `booker`, `run` and `trace` read the table. `stop_after: str` becomes `stop_after: Step`.

**Benefits.** Locality: the D7 rule (assignee check before W1 and W4) and the partial-write line are each written once. Type errors replace the `if step not in STEPS: raise ValueError` checks (`controls.py:172`, `booker.py:95`). Tests can assert on the table once instead of per list.

**Risk.** Medium. No intended behaviour change, but the table decides which errors are partial writes, so the run-loop and booker offline tests and seam 2 must pass unchanged. Run output and trace values stay strings ("W1"...), so the trace contract doesn't change.

**Validation.** `check.py`; seam 2 on the test site (booker W1-W5 and the run loop).

## 3. One owner for "after Submit" errors

**Problem.** Four modules decide whether an error happened after the Submit click and how to retype it:

- `b1/booker.py` retypes errors three times with almost the same code: `_w2` (:190-212), `_w3` (:230-255) and `_stop_after_submit` (:258-291). Each keeps `GuardRefusal` and `AccuracyBreach`, adds the step and turns everything else into `PartialWrite`.
- `core/controls.py:171-190` (`before_write`) and `:142-156` (`assignee_check`) also turn errors into `PartialWrite` for W3-W5. The booker then catches that `PartialWrite` and wraps it again (W3), or passes it through when the step matches (W4, W5, `booker.py:267`).
- `core/run.py:203-208` (`_submitted`) and `:313-365` work it out a third time from the error's type and step.
- `_close_context` is copied in `booker.py:119` and `run.py:195`.

This is split ownership of one rule: "from the Submit click on, the task may exist, so the Note is never returned".

**Change.** The booker owns the rule. One context manager in `booker.py` (for example `after_submit(page, note_id, step)`) closes the context and retypes, used by W2 (after the click) to W5. `Controls.before_write` raises its natural errors (`KillSwitch`, `ConfigError`, `NoteTaken`, `UnexpectedScreen`) and no longer knows which steps are submitted. The run loop trusts the error type: `PartialWrite`, `AccuracyBreach` or `GuardRefusal` with a step at or after W2-after-click. Proposal 2's table supplies "after the click".

**Benefits.** Deletes about 80 lines in the booker and the `NOT_SUBMITTED` branch in `controls.py`. One place to read for "what happens if X fails at W4". Tests for the rule move to the booker's interface.

**Risk.** Medium, near High: this is the logic that keeps a booked Note out of the pool. No intended change in type, step or note_id, but the ALERT's `detail` is `str(error)` (cli.py:250), so some ALERT texts would change (for example "kill switch on mid-booking" becomes the booker's wording). Either keep the current messages, or treat it as a change to what the agent prints: a `docs/decisions.md` entry and the SPEC.md lines.

**Validation.** `check.py`; seam 2 safety tests (`tests/seam2/test_safety.py`) and the booker W2-W5 seam-2 tests on the test site.

## 4. A `MySysSession` module instead of `login` tuples and `"test"` literals

**Problem.** Every caller that may reload MySys carries the same clump: `guard`, `page`, `login: tuple[str, str, str]` (base URL, username, password) and the site. It is splatted with `*login` in 7 places (`run.py:397, :437, :526, :557`; `booker.py:138, :334, :361`; `controls.py:129`), and typed as a bare tuple in 7 signatures. `driver.project_lookup` (driver.py:947) and `reopen_project` (:963) take 7 parameters each. The site is the literal `"test"` in 4 places (`run.py:474, :526, :534`; `booker.py:138`) instead of `config.site`.

**Change.** A small deep module in `mysys/` that holds the guard, the page, the base URL, the credentials and the site, and offers the reads and Note actions the run and the booker use: `find_note_again(note_id)`, `search_note(note_id)`, `project_lookup(internal_no)`, `reopen_project(proceed)`, `gone_from_pending(note_id)`, `fresh()` for a new browser context. `driver.py`'s free functions stay as its implementation. Callers pass one object.

**Benefits.** Leverage: the run loop, the booker and the assignee check stop knowing how a reload logs in again. Locality: the test-site-only rule (Must never #3) has one home, `config.site`, not four literals. The password sits in one object instead of being passed through every frame.

**Risk.** Medium. Pure plumbing in `mysys/`, but many offline tests monkeypatch `driver.*` functions by name, so they will need to patch the session (or use proposal 7's fake). That is a test change for a behaviour-preserving refactor, so it needs its own `test:` commit and a `docs/decisions.md` line (Must never #8).

**Validation.** `check.py`; seam 2 on the test site (all modes).

## 5. `RunLog` is evidence by contract

**Problem.** The run log and trace are "evidence, not a control", but every caller enforces that by hand: `try: log.X(...) except OSError: pass` appears at `booker.py:306, :319`, `controls.py:135`, `run.py:283, :336, :426`, and `if log is None: return` guards appear in `booker.py` and `controls.py`. Callers learn two facts about `RunLog` that it could hide.

**Change.** `RunLog.event` and `RunLog.flush` swallow `OSError` themselves (and count the misses, so a broken disk is still visible once, at the end, through an INFO or the trace). A `RunLog.disabled()` null instance replaces `RunLog | None`. Delete the caller-side `try`/`except` and `None` checks.

**Benefits.** Shrinks several signatures (`log: RunLog | None = None`), removes about 30 lines of defensive code, and a new caller can't forget the rule.

**Risk.** Low. Check `cli.py:242` first: the traceback write after a failure may want to know the write failed.

**Validation.** `check.py`.

## 6. The decision engine owns the step order; the run supplies the lookup

**Problem.** `decide()` (decision.py:200) needs the MySys project lookup up front, but the run must not do that browser read until the Note and PDF checks pass. So `run._decide` (run.py:491-537) runs `check_note_and_pdf` and `check_second_reader` itself, then calls `decide()`, which runs them again (and reads the PDF text twice more). The order of steps 2a-11 is written in two modules. A step added to `decide()` before the lookup would run after it in the run loop.

**Change.** `decide()` takes the lookup as a callable (`lookup: Callable[[], MySysLookup]`) and calls it at step 8. Seam 1 passes a lambda returning its fixture; the run passes the driver read. `run._decide` shrinks to building the `NoteSnapshot` and calling `decide()`.

**Benefits.** Locality: the step order lives only in the decision engine. Seam 1 then also proves that the lookup is not called on an early skip.

**Risk.** Medium: the decision engine is seam 1, so `uv run pytest tests/seam1 -s` (`false PROCEED: 0`) and the real-PO seam on the laptop are part of done. The callable crosses from pure code to a browser read, which `decision.py`'s "no browser code" docstring should mention.

**Validation.** `check.py`; seam 1 and the real-PO seam; seam 2 decide-only.

## 7. One shared MySys fake for offline tests

**Problem.** The offline suite (about 1900 tests) fakes MySys at the widest possible seam: the whole function surface of `driver.py` plus `booking.py`.

- `FakeMySys` patches 39 module functions by name for each test (`DRIVER_NAMES`, `BOOKER_DRIVER_NAMES`, `BOOKING_NAMES`, tests/seam2/test_run_loop_offline.py:320-366). About 49 tests in 5 files use it, plus 24 in `test_booker_offline.py` that patch `driver.search_note` themselves. Those name lists are another hand-synced list: a rename in `driver.py` breaks them, and `raising=False` (test_run_loop_offline.py:413 and three copies) can make a renamed function silently unpatched. Its comment ("note_body moves into the driver in 3.3") is out of date.
- The fake lives inside a test module in `tests/seam2/` (an offline file among 11 test-site files) and 4 other files load it with `importlib.util.spec_from_file_location` (test_exit_codes.py:40, test_run_controls_offline.py:35, test_assignee_offline.py:45, test_trace.py). Its install fixture and a near-identical `env` fixture are copied in up to 7 files.
- Many tests assert internal call order: `calls_for(fake, id) == [... *W1_TO_W5]` lists 23 internal step names (test_run_loop_offline.py:782-838), and failure injection is keyed to the same names (`fail_at`, `kill_at`, `AFTER_SUBMIT`). Some call private helpers directly (`run._book`, test_exit_codes.py:351; `run._decide` in 4 test-site files; `driver._project_menu`, test_booking.py:768).
- Playwright-level fakes are rebuilt per file: the module-scope browser fixture is copied in 7 files, and fake Note, Note Pool and project pages in 2-3 files each. `booking.LOAD_TIMEOUT_MS` copies driver's value at import (booking.py:37), so 13 sites patch both. `booking.SNAPSHOT_DIR` defaults into `private/` (booking.py:58), so a test that forgets the patch writes there.
- The guard-history assertions (32 in `test_booker_offline.py`, 15 in `test_booking.py`) pin the click sequence. That one is the safety contract, so it is behaviour, not implementation; keep it.

**Change.** In two steps, the first independent of the other proposals:

1. Test layout only: move `FakeMySys`, `FakeNote`, `FakePage`, the row builders, the `env` fixture and one browser fixture into `tests/fakes/` with a top-level `tests/conftest.py`; drop the `importlib` loads and `raising=False`; read `LOAD_TIMEOUT_MS` from one place. No test changes what it asserts.
2. After proposal 4: fake the `MySysSession` interface (a handful of behaviours) instead of 39 functions, and assert outcomes (NOTE lines, RUN_SUMMARY, exit code, guard history, what the Note ends up as) instead of internal call lists where an outcome says the same thing.

**Benefits.** Locality: one fake to update when MySys behaviour is learned. Refactors such as 1, 3 and 4 stop breaking dozens of tests that pin internal names. Step 1 probably also shortens the offline run, which took over 13 minutes in the survey; the 22 `setTimeout`-based fakes are worth a look.

**Risk.** Low for step 1 (test layout, same assertions). Step 2 changes what tests assert, so it needs its own `test:` commit and a `docs/decisions.md` line (Must never #8), and should land with proposal 4.

**Validation.** Same test count and same pass/fail before and after step 1 (`pytest --collect-only -q`, then the offline suite); `check.py`.

## 8. An explicit Note custody state in the run loop

**Problem.** `run._note_loop` (run.py:246-368) tracks the Note it holds with `_Progress` (`note_id`, `taken`, `submitted`; :153-159), sets those fields in five places in `_one_note` (:394-446) and decides return, ALERT and exit in a 50-line `except BaseException` block. The rules are right and well tested, but a reader must hold three fields and their legal combinations in their head ("state to hold", `minimize-reader-load`).

**Change.** Model the custody of the current Note as one value: `Free`, `Held(note_id)`, `Submitted(note_id, error)`, `Booked`. Transitions happen at the take, the Submit click, the return and the booking. The stop path becomes one function of that value: return it, leave it, or report a partial write.

**Benefits.** Illegal combinations (taken and submitted and no note_id) can't be written. The stop path is testable as a pure function.

**Risk.** High: this is the safety path after an error. Only worth doing after 2 and 3, which remove most of the error classification it would otherwise carry. It may turn out small enough then that it isn't needed.

**Validation.** Seam 2 safety tests; the run-loop offline tests unchanged.

## 9. Say what `core/` and `mysys/` really depend on

**Problem.** SPEC.md -> Project Structure calls `core/` and `mysys/` "reusable for the next MySys automations", but they import B1 rules: `core/run.py` and `core/demo.py` are the B1 run and demo, `core/trace.py` imports `SkipReason`, `mysys/driver.py` imports `b1.decision.match_project`, `check_project` and `b1.reader_rules`, and `b1/reader_rules.py` holds task-table parsing (`compaction_tasks`, `live_tasks`, `new_task`; :168-192) used by `mysys/`. A future agent will believe the label and put client-specific code in the wrong place.

**Change.** Now: fix the labels in SPEC.md (docs only), and move the three task-table helpers from `reader_rules.py` to `mysys/` where they are used. Later, only when a second client is real: split B1's run loop out of `core/`. No multi-client code before then (the B1-only rule).

**Risk.** Low.

## Not proposed

- **Restructuring `mysys/guard.py`.** It is the safety control and is already one deep module: `vet()` and `act()` hide the allowlist, denylist and target resolution. Out of scope here, and Joey's to change.
- **Splitting `driver.py` (1052 lines) or `booking.py` (1023 lines) by size alone.** Their length is mostly screen knowledge, which belongs together. Proposal 1 shrinks `booking.py`; proposal 4 gives `driver.py` a smaller interface.
- **Removing Playwright `Locator` from module interfaces.** Only one adapter (Playwright) exists, so a port would be a hypothetical seam.

## Doc impact

Each proposal that lands changes SPEC.md -> Project Structure. Proposal 1 also changes SPEC.md -> Commands (`po-agent demo`) and `docs/demo-runbook.md`. Already stale today: the "Demo only" label on three guard actions in SPEC.md -> MySys screen rules (see proposal 1). Proposal 4 removes the `login` tuple wording from the booker and run docstrings.

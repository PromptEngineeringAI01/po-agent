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

---

# Round 2 - 9 Nov 2026

A second pass with `/improve-codebase-architecture` (`.claude/skills/`, PR 80), at `main` 38dfdf5. Same vocabulary and risk levels as round 1; it looks for new candidates and checks round 1 against current code. The visual report stayed outside the repo. Joey picked candidate D and settled its design (below).

## New candidates

| # | Candidate | Strength | Risk | Main files |
|---|---|---|---|---|
| D | One Send Email Notification control for every Note-window write | Strong | Medium | `mysys/driver.py`, `mysys/booking.py`, `b1/booker.py` |
| B | One error-report path: exit code, ALERT kind, traceback, trace end | Strong | Low-Medium | `core/errors.py`, `cli.py`, `core/output.py`, `core/runlog.py`, `core/trace.py` |
| A | The two readers as one module; `decide()` gets the PDF once | Strong | Medium (seam 1) | `b1/decision.py`, `b1/reader_rules.py`, `core/run.py`, `tests/seam1/real_pos.py` |
| C | One module owns MySys waiting (poll, settle, retry an opening click) | Strong | Medium | `mysys/driver.py`, `mysys/booking.py` |
| E | A run plan: the run's inputs and mode policy as one value | Worth exploring | Low-Medium | `cli.py`, `core/run.py`, `core/controls.py` |
| F | Note Pool views as one call (menu exit and filter preset inside) | Worth exploring | Medium | `mysys/driver.py`, `core/run.py` |
| G | MySys modules by screen, without the driver-booking import cycle | Worth exploring | Medium | `mysys/driver.py`, `mysys/booking.py`, `b1/reader_rules.py` |

None touches `guard.py`, hooks or CI.

**D.** Send Email is unticked and read back in two implementations: `driver.py:668-676, :708-745` (take and return) and `booking.py:143-165` (W4 twice, W5), plus the demo's copies (`booking.py:189-216`, `demo.py:249`). The driver logs `email_notification_unticked` with `ok=false` before it stops; booking logs through a callback from `booker._unticked` (`booker.py:294-309`) that only ever logs `ok=true`, so a box still ticked at W4 or W5 stops the run with no `ok=false` event. W5 reads the box back twice (`booking.py:262-263`). Must never #4 has two homes with different evidence.

**B.** One error's reporting is known in `errors.py` (`exit_code`), `cli.py:70-79` (`ALERT_KINDS`) and its MRO walk (`:217-221`), `output.py:61` (`AlertKind`, synced by hand), `cli._log_traceback` (`:224-243`, its own format for the file `RunLog` writes; `RunLog.error`, `runlog.py:83-92`, has no caller in `src/`), `run.py:328-337` and `trace.py:187-194`. `KillSwitch` and `NoteTaken` (`controls.py:69-82, :101-109`) are plain `Exception`s with duck-typed `note_id` and `step`. Dead vocabulary: `SkipReason.PARTIAL_WRITE`; `Skip(UNEXPECTED_SCREEN)` (`decision.py:162`) is an error that `run.py:405` re-raises. Change: each error class declares its exit code and ALERT kind; one `report(error)` prints the ALERT, writes the traceback through `RunLog` and ends the trace. Stdout unchanged; `test_output_cli` and `test_exit_codes` must pass unchanged.

**A.** `decide()` (`decision.py:204`) takes `pdf_text`, `pypdf_text` and `pdf_bytes`: three forms of one PDF, two of them positional strings that can be swapped with no type error (the `exact_line_under=True` rule would then apply to the wrong text). Three callers repeat `text_layer` plus `pypdf_text_layer` (`run.py:518-519`, `test_seam1_decide.py:29`, `real_pos.py:237`), and the agreement rule lives in `check_second_reader` (`:183`), the second address pass in `decide()` (`:233-236`) and a test copy (`real_pos._agreement`, `:157-170`). Change: one readers module turns the bytes into both readings and owns the agreement rule; `decide()` takes that value. Do it with round 1's proposal 6 (both change the interface of `decide()`); seam 1 and the real-PO seam are part of done.

**C.** Six hand-written deadline loops (`driver._polls`, `settled_tasks`; `booking._reads`, `search_project_rows`, `new_task_after_submit`, demo-only `wait_new_task`), two identical opening-retry helpers (`driver._open_retried`, `:488`; `booking._open`, `:107`), two menu-retry loops and timeout constants copied at import (`booking.py:37-44`; tests patch both). The settle rules are pure logic but can only be tested through Chromium, `setTimeout` fakes and timeout patches. Change: one wait module on one clock. Must keep: committing clicks are never retried (3 Nov 2026, M4 gate) and the one-call `task_rows` read (PR 75).

**E.** `book_run` and `decide_only` (`run.py:211-243`) are pass-throughs to `_note_loop`; decide-only is encoded as `config_dir=None`; an `argparse.Namespace` reaches four places in `run.py` and the demo; mode policy is spread over `SECRETS_FOR`, `WINDOW_MODES`, `cli.py:199`, `:268-270` and a docstring; `_TRACES` is a module global "so start() keeps its signature". Change: `cli` builds one frozen run plan (mode policy, config, browser options, trace, and a kill-switch reader that re-reads `enabled` before each W step). Pairs with round 1's proposal 4.

**F.** Four of five `open_note_pool` callers must follow it with `leave_menu` (`run.py:274`, `driver.py:518`, `booking.py:285`, `demo.py:161`; `spike` does not), and the three filter presets are checked to three different levels (`search_note`, `:504-530`, checks none). W5's `gone_from_pending` relies on filters that are not checked there; not a defect today (the stale read checks them at run start), but implicit. Change: one Note Pool module with `open(view)` for the eligible, stale and search views.

**G.** `driver.py:1021` imports `booking` lazily to get round a cycle; `booking` uses about ten `driver` privates; the Projects screen is spread over `driver`, `booking`, `reader_rules` and `decision`. Change: one module per screen plus a public locate-helpers module; B1 rules stay in `b1/`. Not a split by size: the reasons are the cycle and locality. After round 1's proposals 1 and 7; D and F can be its first slices.

## Round 1, checked against current code

- **1 is partly wrong.** `booking.untick_send_email` and `_reads` are on the run path (W4, W5), and `reader_rules.pdf_text` is on it through `text_layer`: merge them (D), don't delete them. `po_from_file_name` is used by `tests/seam1/real_pos.py`. Demo-only and missing from the list: `wait_new_task`, `search_projects`, `probe_link`, `download_hrefs`, `has_link_to_project`, `save_snapshot`, `reader_rules.new_task`.
- **2 is larger.** `trace.STEPS` also holds the non-W steps ("0"-"11", "2a", "return", "decide"); the table must cover them, or the trace keeps its own list.
- **4 is larger.** It should also take the `credentials` dict and `cli.SECRETS_FOR`, and `Controls("test", ...)` (`run.py:474`, 8 copies in tests); "find again, still ours?, return" is duplicated at `run.py:437-446` and `:557-566`.
- **5 is larger.** See B for `RunLog.error` and `_log_traceback`. The `read_back.*` names in `trace.CHECKS` are synced by hand with the field strings in `driver.py`; W2 and W3 read-backs emit no `read_back` events.
- **9 is partly stale.** `new_task` is demo-only (delete it with proposal 1); `live_tasks` is used by `driver.reopen_project`.
- 3, 6, 7 and 8 stand as written.

## Deep enough, not proposed

`guard.py` (`vet`/`act`), `config.py`, `secrets.py`, `trace._kept`, `errors.identifier`, `models.Proceed`, `address.verify_address` and the contract models in `output.py`; tests `test_hooks.py`, `test_guard.py`, `test_output_cli.py` and the seam-1 layout. Two items are Joey's call if ever wanted: three allowlist names with no caller in `src/` (`open_pool`, `search_task`, `open_task_detail`; a guard change, high risk), and the dead NOTE fields `outcome "partial"`, `tokens_in`, `tokens_out` and `cost_aud` (a stdout-contract change).

## D: the settled design (Joey, 9 Nov 2026)

What the build task (`tasks/todo.md` 8.1) implements. Its own `docs/decisions.md` entry and SPEC lines come with it.

- **One module, two operations,** in the Note-window part of `driver.py` (moved to its own module later if G is done): *untick* (untick if ticked; no event) and *check before a committing click* (read back unticked, record `email_notification_unticked` with `ok` true or false, raise `UnexpectedScreen` with `note_id` and `step` if still ticked). Both are called at exactly today's points, so the guarded click sequence is unchanged: take and return (untick first, check right before Assign), W4 (untick and check before Link to Project, check again before the select), W5 (untick and check before Solved; the duplicate read goes).
- **The demo uses it too** (its own take, return and Assign copies in `booking.py`, and `demo.py:249`), so the box has one locator and one read-back. The demo has no run log, so it records no event. The demo copies themselves still go with round 1's proposal 1.
- **The callback goes.** `link_project`, `mark_solved` and `_search_choose_project` take the run log and Note ID instead of `unticked`; `booker._unticked` is deleted.
- **Evidence change:** a box still ticked at W4 or W5 now records `ok=false` before the stop, as take and return already do. The success-path events and their order are unchanged, so the P5 trace check (decisions, 9 Nov 2026, 5.2) still holds. The ALERT and its detail are unchanged (the booker retypes the error as today). Needs a `docs/decisions.md` entry and the `SPEC.md` -> Safe trace line.
- **Tests:** a failing test first for the W4/W5 `ok=false` event; the offline MySys fake's `link_project` and `mark_solved` signatures change in their own `test:` commit with a `docs/decisions.md` line (Must never #8). Guard-history assertions don't change.
- **Not in scope:** making the guard refuse a Note-window committing click without a prior check (a guard change, high risk; revisit only if a missed check ever happens).
- **When:** after the P5 week, before P6 go-live. It changes `mysys/` and the booker, so seam 2 (take, return, W4, W5) runs on the test site with the Mac Mini job unloaded.
- **Done:** `check.py`; seam 2 as above; review at Medium depth.

## B, A and C: the settled designs (Joey, 9 Nov 2026)

**Order.** The Mac Mini runs the `production` tag (7.4), so a merge to `main` doesn't change the P5 week's runs; what waits is any seam-2 run, which needs the Mac Mini job unloaded. So B (no test-site run) is built now, during P5; after the P5 week and before P6 go-live: D (8.1), then A with round 1's proposal 6 (8.3), then C (8.4).

**B (task 8.2): smaller than the report said.** `cli._report` is already the one report point. The task does two things:

- **The ALERT kind lives on the error class,** next to `exit_code` (for example `alert_kind: ClassVar[AlertKind]`; `WriteNotStarted` keeps `UNEXPECTED_SCREEN`). `ALERT_KINDS` and the MRO walk in `cli.py` go. `AlertKind` stays the stdout contract's `Literal` in `output.py`; a test checks every error class's kind is in it.
- **One traceback writer.** A module-level function in `core/runlog.py` appends the traceback event to `logs/<run_id>.jsonl` in the run log's format; `cli` calls it (it must also work before a `RunLog` exists, for a config error). `cli._log_traceback` and the dead `RunLog.error` go.
- **Unchanged:** every ALERT, NOTE and RUN_SUMMARY line and every exit code; `test_output_cli.py` and `test_exit_codes.py` pass unchanged. No `docs/decisions.md` entry needed (nothing printed or written to MySys changes).
- **Left out on purpose:** making `KillSwitch` and `NoteTaken` `PoAgentError`s (the run loop's `isinstance(error, PoAgentError)` checks would then take other paths: a change to the stop path); removing `SkipReason.PARTIAL_WRITE` and turning `Skip(UNEXPECTED_SCREEN)` into a raised error (both reach the decision engine and seam 1). Known, not planned.
- **Done:** `check.py`; review at Low depth.

**A with round 1's proposal 6 (task 8.3): one task, because both change the interface of `decide()`.**

- **A readers module in `b1/`** turns the PDF bytes into one value holding pdfplumber's and pypdf's texts (each "" when unreadable) and the bytes. It owns the two-readers rule (decisions, 2 Nov 2026): the per-field agreement (issuer, COMPACTION, PO number, Job Address label line) and the address check on both texts (exact under the label on pypdf's). Seam 1 can still build the value from fake texts.
- **`decide()` takes that value and a lookup callable,** and calls the lookup only once the Note and PDF checks pass (step 8). `run._decide` shrinks to building the `NoteSnapshot` and calling `decide()`; it no longer runs `check_note_and_pdf` and `check_second_reader` itself.
- **`tests/seam1/real_pos.py` uses the module's per-field agreement;** its `_agreement` copy goes.
- **Tests:** seam 1 gains "the lookup is not called on an early skip". Seam-1 tests that call `decide()` with the old arguments change in their own `test:` commit with a `docs/decisions.md` line (Must never #8).
- **Done:** `check.py`; `uv run pytest tests/seam1 -s` shows `false PROCEED: 0`; the real-PO seam on the laptop; seam 2 decide-only (it changes the run loop); review at Medium depth.

**C (task 8.4): one wait module in `mysys/`.**

- **Three waits on one injectable clock:** until a read is true; settled (N equal reads, with a predicate); retry an opening click. Every loop listed under C calls it; the timeout constants live once, with today's values (15 s, 60 s for Choose Project and the Projects search, the W2 new-task wait).
- **The retry refuses a committing click.** It takes a fixed set of opening action names (today's retried actions are `open_note`, `refresh_note_pool` and `open_project`, plus the two menu loops) and raises on any other name, so the 3 Nov 2026 M4-gate rule (committing clicks are never retried) is enforced in code, not only by naming. The set lives in `mysys/`, not in the guard.
- **Tests:** new pure tests on a list of reads and a fake clock, no browser. The existing `setTimeout`-based tests stay; dropping any of them later is its own decision.
- **Must keep:** the one-call `task_rows` read (PR 75); `driver._polls` semantics (a label gone for a moment is read again).
- **Done:** `check.py`; seam 2 on the test site, all modes; review at Medium depth.

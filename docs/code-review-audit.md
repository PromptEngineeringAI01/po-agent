# Code review audit (9 Nov 2026)

A read-only audit of `main` at `82ec374` for correctness, safety and security defects. Architecture and refactoring ideas are out of scope: they are in `docs/architecture-review.md` (PR 79). Nothing in `src/` or `tests/` was changed; seam 2 and real-data tests were not run; `private/`, `logs/` and `state/` were not read.

**Result:** 3 Important findings (1 code defect, 2 test gaps on Must-never controls) and 5 Nits. No path was found that clicks outside the guard, returns a booked or partly booked Note to the pool, skips a read-back, or puts a secret or page text in run output or the trace.

| # | Severity | Where | One line |
|---|---|---|---|
| I1 | Important | `b1/reader_rules.py:30` | PDF PO `X/0481` is read as `X/048` and can be booked |
| I2 | Important (test gap) | `tests/test_guard.py:654` | The guard's Hold-label clause can be deleted and every test passes |
| I3 | Important (test gap) | `tests/test_booker_offline.py:582` | The pre-Submit read-back of PO number, Note and PO file can be disabled and every test passes |
| N1 | Nit | `b1/address.py:73-76` | Project state and postcode are dropped, not compared |
| N2 | Nit | `b1/address.py:73-76` | `... WA 6000` (state first) gives a false `ADDRESS_MISMATCH` |
| N3 | Nit | `core/run.py:286-365` | A Note that fails the same way blocks every later run |
| N4 | Nit | `scripts/macmini-run.sh:88` | Alert issues in a public repo will carry live Note IDs |
| N5 | Nit | `tests/test_guard_check.py:49` | 22 of the 44 banned page calls are never tested |

## Method

- **Risk tiers, one reviewer each, in parallel:** (1) safety path: guard, booker W1-W5, run loop, controls; (2) decision correctness: decision, reader rules, address, models; (3) secrets and run output; (4) test quality, light, by mutation in scratch copies. Reviewers were Sonnet 5.5 sub-agents: a different model from the Opus sessions that wrote most of the code (same vendor; no other model family is set up here).
- **Judge pass (Opus 5.5):** the safety path was also read in full by the judge. Every kept finding was confirmed twice: by the reviewer that found it and by the judge re-reading the cited lines or re-running the proof. Findings that contradict a dated `docs/decisions.md` entry were dropped or kept only as a Nit for Joey's choice; style, naming and cleanup were not reported.
- **Verified by running code where possible:** small scripts with fake values against the real functions, the offline suites, and mutants in scratch copies of `src/`. "Ran" means the failure was reproduced; "read only" means it was not.
- **Baseline:** `uv run scripts/check.py` on `main` before the audit: 1900 passed, 1 skipped, 21 deselected; `check: all passed`.
- **Sources for the method:** the Stanford "Agentic Code Review" lecture; Cloudflare, "Orchestrating AI Code Review at scale" (specialists by domain, a judge that drops speculative and convention-contradicting findings); Greptile, "How to build a code review agent" (context beyond the diff, a different reviewer model, verify by running code); Anthropic, "Solving code review at Anthropic" (parallel finders, a vote per finding, Important / Nit labels, style dropped). The Addy Osmani post on X could not be read (HTTP 402); cognition.com had no code-review material.

## Important

### I1. A PDF whose PO number only starts with `/048` passes the PO check

- **Where:** `src/po_agent/b1/reader_rules.py:30` (`_PDF_PO`), used by `read_pdf` (`:117`), so by `check_pdf` and `src/po_agent/b1/decision.py:102-106`.
- **Defect:** `([0-9A-Z]+/[0-9]{3})` has no right anchor, so `2609017B/0481`, `2609017B/048X` and `2609017B/048999` are all read as `2609017B/048`. The file-name rule (`fullmatch`) and the title rule (`(?=\s|$)`) are anchored, and seam 1 already checks that `_0480` and `/0480` are rejected there; this rule has no such check.
- **Failure scenario:** a Note's attachment is named `2609017B_048.pdf` but the PDF itself says `Purchase Order No 2609017B/0481` (a mis-named file, or another trade's PO). Both readers run the same rule, so they agree on `2609017B/048`. The PO check passes, and if the address and project checks pass, the agent books a Compaction Test task with PO Number `2609017B/048` and attaches a PDF for another PO. `docs/decisions.md` (PO number rule) says the PDF must agree with the file name; here it does not, and the Note still proceeds.
- **Verified:** ran. `read_pdf("B1 Homes Pty Ltd\nPurchase Order No 2609017B/0481", "", "").po_number` returns `'2609017B/048'`; the same for `/048X` and `/048999`.
- **Fix:** add `(?![0-9])` after `[0-9]{3}` (digits only, so a text layer that runs the next word on without a space still reads), with a `test:` commit for `/0481` -> `PO_MISMATCH`. Add the same case for the title rule: deleting its `(?=\s|$)` passes every test today.

### I2. The guard's "label of a Hold checkbox" refusal is untested

- **Where:** `tests/test_guard.py:654` (`test_click_on_a_label_or_row_holding_a_hold_checkbox_is_refused`) for the clause `resolved.and_(page.locator("label")).count() > 0` at `src/po_agent/mysys/guard.py:301`.
- **Gap:** the only label fixture wraps its checkbox (`<label><input type=checkbox> Job 1</label>`), which the descendant-checkbox clause already refuses. Deleting the label clause leaves all 96 guard tests passing.
- **Failure scenario:** a later guard change drops or breaks the clause; a `<label for="c">` beside a separate checkbox in an open Hold dialog is then `Allowed`, and a click on it toggles a Hold checkbox (Must never #2). CI stays green.
- **Verified:** ran. With that markup, `vet("confirm_hold", ...)` on the label: original `Refused(HOLD_CHECKBOX)`, mutant `Allowed()`; the mutant passes `tests/test_guard.py`.
- **Fix (guard tests are Joey's to merge):** one `test:` case with a `label[for]` whose checkbox is outside the label.

### I3. The pre-Submit read-back is tested for one wrong value only

- **Where:** `tests/test_booker_offline.py:582` for `booking.check_task_form` (`src/po_agent/mysys/booking.py:686-705`).
- **Gap:** the one mismatch case is two ticked checkboxes (`multiple="checked"`). The fake form echoes every fill faithfully, so no test has a wrong PO Number, a wrong Note or two PO files. Replacing any of the `po_number`, `note` or `po_documents` checks with `True` leaves all 60 tests passing.
- **Failure scenario:** a later change breaks one of those checks; a form holding a wrong PO Number or Note is submitted, and only W2's read-back notices, after the task exists (`PARTIAL_WRITE`, a wrong value in MySys). Must never #7: no write before every check has passed.
- **Verified:** ran by the reviewer (one mutant per check, full file each); the judge read the test file and found no other caller of `check_task_form` in `tests/`.
- **Fix:** a parametrized `test:` case in which the fake form mangles one field at a time (PO Number, Note, a second PO file, Creator, Sale Office), each -> `WriteNotStarted`, `submit_task` not called.

## Nits

### N1. The project address's state and postcode are dropped, not compared

- **Where:** `src/po_agent/b1/address.py:73-76` (`parse_project_address`) and `_is_address` (`:127`).
- **Scenario:** project `Lot 12 23 Smith St Perth 6000 WA`; a PDF Job Address `Lot 12 23 Smith Street Perth 6001` or `... Perth NSW` gives no skip. The project is already pinned by Client Ref No. = the Note's internal number, so this weakens only the second check.
- **Verified:** ran (no skip reason from either reader).
- **Fix (Joey's choice):** the 30 Oct decision makes the tail optional on purpose; if wanted, compare a tail the PDF does show with the project's.

### N2. The project address is parsed only as `... <postcode> <state>`

- **Where:** `src/po_agent/b1/address.py:73-76`: the state is popped before the postcode.
- **Scenario:** if MySys shows `Lot 12 23 Smith St Perth WA 6000`, `wa` stays in the compared words and a correct PDF gives `ADDRESS_MISMATCH`: a false skip, never a false PROCEED.
- **Verified:** ran (`ADDRESS_MISMATCH` against `... Perth WA 6000`, none against `... Perth`).
- **Fix:** strip a trailing state and postcode in either order, as the PDF tail already allows.

### N3. A Note that fails the same way every run blocks every later run

- **Where:** `src/po_agent/core/run.py:286-305` and `:313-365`: any error but `NoteTaken` stops the run after returning the Note; `oldest_first` (`:102`) picks it first again the next hour.
- **Scenario:** one Note hits a deterministic `UnexpectedScreen` or `GuardRefusal` before W1 (for example a screen the mapping does not cover). It goes back to the pool, and every hourly run takes it first and stops: one `po-agent-alert` issue an hour, and no newer Note is booked until Joey acts. This is the designed fail-closed stop (decisions, 5 Nov 2026, 7.2), not a wrong write.
- **Verified:** read only.
- **Fix:** a line in the ops runbook (7.5): an alert naming the same `note_id` on two runs means take that Note by hand; or, later, skip a Note that stopped the previous run.

### N4. Alert issues in a public repo will carry live Note IDs

- **Where:** `scripts/macmini-run.sh:88` (`open_issue` copies every `ALERT` line into the issue body); the repo is public (decisions, 25 Oct 2026).
- **Scenario:** after go-live an `ALERT` carries a live MySys `note_id` (and `step`, `reason`) in a public issue. Must never #6 allows only the 3 trial POs' identifiers in issues. No pln, PO number, address or name is in an ALERT line today.
- **Verified:** read only, plus `gh repo view` (public).
- **Fix (Joey's choice, before go-live):** open alert issues in a private repo, or drop `note_id` from the issue body and keep it in `runs.log` only.

### N5. Half of `guard_check.py`'s banned page calls are never tested

- **Where:** `tests/test_guard_check.py:49` (`test_banned_call_or_reference_fails_anywhere`) for `BANNED` in `scripts/guard_check.py`.
- **Gap:** 22 of the 44 names never appear in the test file, among them `set_checked`, `dblclick`, `clear`, `drag_to`, `evaluate_handle`, `expose_function`, `storage_state` and `record_video_dir`. Dropping them from `BANNED` keeps CI green; `test_repo_passes` only shows nothing uses them today.
- **Verified:** ran (the judge counted the names; the reviewer narrowed `BANNED` to the tested names and all 94 tests passed).
- **Fix (Joey's to merge):** parametrize the banned-call test over `sorted(BANNED)`.

## Checked and found fine

- **Guard:** every page action in `src/` is in `guard.act()`; names are read from the ARIA name, `aria-label`, `title`, `value`, `alt` and text content, including descendants; the element is pinned, never looked up twice; Hold checkboxes, Pending and the denylist are refused. About 90 mutants of the guard, decision, address and run controls were caught by the tests.
- **Booker:** every error from the Submit click on is `PartialWrite`, `AccuracyBreach` or `GuardRefusal` with step W2-W5 (Ctrl+C included); `_submitted()` and `progress.submitted` keep such a Note out of the pool even when a cleanup raises later. W1 re-checks the pln and the existing tasks; W2 reads back the one new task, its detail screen and the document; W3-W5 each read back. Committing clicks are never retried. Offline suites for the booker, run controls and assignee check: 102 passed.
- **Controls:** the kill switch before W1/W2 returns the Note and exits 0; from W3 it is `PartialWrite`; the assignee check before W4 turns `NoteTaken` into `PartialWrite`; the stale-Note stop holds later runs. The kill switch is re-read before each W step, not between Notes, as decided (3.5).
- **Decision:** the project is pinned by Client Ref No. and the opened project's internal number; house-number prefixes (`12` vs `112`), unit numbers (`1/23`), empty values, two labels, two PO numbers and unreadable PDFs all skip; readers that disagree give `READERS_DISAGREE`; `Proceed` is strict and frozen. "COMPACTION" is a substring test (`reader_rules.py:123`, so `NON-COMPACTION` counts), but the PO, file-name, address and project checks still apply.
- **W2 document read-back** accepts a file name that starts with the PDF's name: that is the 4 Nov decision (MySys shows the file that way), so not reported.
- **Secrets and output:** secrets come only from `PO_AGENT_<NAME>` or keyring and are never in a model; Playwright errors are re-raised `from None` with fixed text; no tracing, video, screenshot or storage state; the trace keeps closed-type fields only; `logs/`, `private/`, `state/` and `traces/` are git-ignored. With `--detailed-log` the traceback event can hold an exception's message (page text from a non-typed error): documented in SPEC, laptop only, `logs/` ignored.
- **Tests:** no `or True`, `raises(Exception)`, self-mocks or silent skips in the safety tests; `scripts/check.py` deselects only `live_claude`, `testsite` and `real_data`; seam 1's "false PROCEED: 0" cannot read 0 because nothing ran.
- **Downloads:** a run killed by the 20-minute limit leaves the PDF folder until the next run's start sweep, as D2 accepts.

## Not covered

`tests/test_trace.py` and `tests/test_output_cli.py` were read but not mutated; `src/po_agent/core/demo.py` was not reviewed (not on the run path).

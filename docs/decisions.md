# PO Agent — decision log (updated 25 Oct 2026, Milestone A)

Source of truth for decisions behind `docs/intent.md`, `SPEC.md` (MVP) and `docs/specs/` (v1 spec pack v1.2, ADR-001, ADR-002). If any spec disagrees with this log, this log wins. Author: Joey Wu.

After `tasks/plan.md` is approved (the freeze point), add a dated entry here for every change to what the agent does in MySys or prints in its run output, and for anything that loosens a safety control, in the same commit as the `SPEC.md` and `tasks/plan.md` changes. Tightening a dev-tooling rule needs only a clear commit message (24 Oct 2026, below).

## Status

- **13 Oct 2026: the CEO approved decision 1** of the CEO decision brief: the two-reader design, its safeguards, and a trial on the test site with 3 fake POs. The build can start.
- **15 Oct 2026: the CEO made decision 3:** the agent runs on the **office Mac Mini** (already purchased), for the MVP trial and for production (entry below).
- **25 Oct 2026: decision 2 made.** The CEO delegated decision 2 (Claude reading real client POs) to Joey, and approved the trial PDF sitting briefly on the Mac Mini's disk (D2). Joey: yes, on the Trial conditions terms (entry below).

## 28 Oct 2026 - A guarded pointer move ends "page blocked" (Joey)

- **Root cause, reproduced offline:** after a guarded click in the header's Project menu, Playwright's pointer stays in the header. While the header is hovered, MySys covers the body, so no click below the header lands ("<body> intercepts pointer events"). Clicking "Welcome Agent" (the old `leave_project_menu`) kept the pointer in the header, so the block stayed until a real mouse moved. `tests/test_booking.py` reproduces both with CSS only.
- **Decision (Joey, in the demo session):** the guard may move the pointer. A new kind `move` has one action, `move_pointer_off_menu`, which moves the pointer onto a list's status line below the header (the footer "Page N of N (N Items)" or "No record (could be) found."). Its role must be plain text (generic, listitem, paragraph, text), and it must be found exactly once and visible. No click, no key, no value. It uses `hover(force=True)`, because a plain hover runs the same "receives events" check the cover fails (https://playwright.dev/python/docs/actionability#forcing-actions). `scripts/guard_check.py` allows `hover` inside `guard.act()` only.
- **Headless only when read-only:** the demo honours `--headed` again, since the block that forced it headed was the parked pointer. A demo that asks for writes (anything but `--until-check` or `--probe-link`) refuses to start without `--headed` (exit 2): Joey approves each write at a prompt and must see the page (PR #29 review).
- **Accepted risk (PR #29 review):** the move is `hover(force=True)`, so the mouseover goes to whatever is on top at the status line's centre, and leaving the header fires mouseout on the menu. MySys hover handlers aren't known to write anything; that can't be checked without `evaluate` (banned); the live runs (plan step 3) are the check. The target must be plain text with no link or button inside it.
- **Removed:** `leave_project_menu`. `leave_menu` now uses the move. The opening clicks keep their retries, and the message is now "page blocked, retrying"; no human mouse is asked for.
- **To prove live** (plan step 3, Joey, hands off the mouse): 5 headed and 5 headless `--until-check` runs, all reaching `demo: read-only checks done` without "page blocked". If any blocks, revert this and keep the human mouse.

## 28 Oct 2026 - Enter runs the two project searches; the guard may press Enter there only (Joey)

- **Decision (Joey, in the demo session):** after filling the project number, the demo runs the search by pressing **Enter** in the search box, in the Projects panel (step 5) and in Choose Project (step 8). This loosens the guard, which pressed no key until now.
- **Kept narrow:** a new guard kind `press` allows only the key `Enter`, and only for two actions on one target each: `submit_project_search` on the Projects panel's textbox "Search..." and `submit_link_search` on Choose Project's textbox "Search/filter". Any other key is refused (`VALUE_MISMATCH`); Enter on any other element, or through any other action, is refused (`WRONG_ELEMENT` / `VALUE_MISMATCH`). The exactly-one, visible, in-scope and denylist checks apply as to every action. `scripts/guard_check.py` allows `press` inside `guard.act()` only.
- **Removed:** the clicks that ran these searches by moving focus, `run_project_search` (27 Oct) and `link_run_search` (28 Oct), leave the allowlist.
- **Step 5 made reliable in the same change** (read-only): the Projects filters must be at their defaults before searching (else `UNEXPECTED_SCREEN`); the search waits up to 60 s; a stale "No record found." or the old list doesn't count as the result; a loading row or a re-render mid-read is read again; any settled list counts (two equal reads in a row), so a hit on a field the list doesn't show no longer times out; the same row listed twice counts as one project.
- Carried in: `SPEC.md` (MySys screen rules: no key presses except these two; Guard additions), `src/po_agent/mysys/guard.py`, `scripts/guard_check.py`, `src/po_agent/mysys/booking.py`.

## 27 Oct 2026 - Supervised demo mode: one PO, Joey's Enter before every write (Joey)

- **What:** `uv run po-agent demo --site test --headed` books the one trial PO 2609017B -> pln_66935 the way Joey does it by hand, for the CEO demo on 28 Oct: take the Note (Send Email unticked), download and check the PDF, find and check the project, Create New Task (Perth Scheduling, - Compaction Test, PO Number, the PDF to PO Documents from memory, Note = the email body), Hold ("ON HOLD UNTIL CALL UP", no checkbox in the dialog touched), Link to Project, Solved. It prints `NEXT  <step> [Enter / n]` and waits before every write; only a bare Enter goes on ("n", anything else or end of input stops). On a failed check, an error or "n" it saves the page's ARIA snapshot to `private/captures/test/demo-<step>.yml` and, if the Note was taken, asks to return it to the pool (one Assign, row 15b), then stops with its ALERT.
- **In-scope checks for this mode** (instead of `SPEC.md` -> In the MVP): the Note is the one eligible 2609017B Note in the Agent Pool (step 0); not linked yet; exactly one PDF link; the PDF names B1 Homes and COMPACTION, its PO number equals the file name's and its internal number the Note's; exactly one B1 Homes project whose Client Ref No. is the internal number, and it is pln_66935, with the same Client Internal No.; no Compaction Test task on it that isn't Cancelled. Every write is read back as in `SPEC.md` -> MySys screen rules.
- **Not in it:** the Claude reader and the two-reader agreement, the address check, the assignee re-check (§8), the stale-Note stop and the run controls (kill switch, Perth window, run cap). Joey's Enter and his presence at the screen stand in for them. `run` still refuses until 4.5; nothing here changes `run` or `decide-only`.
- **`--until-check`** runs the read-only steps (login to the duplicate check) without taking the Note and without any prompt: opening a Note and downloading change nothing (rows 02, 05). Claude may run only this; the first full write run is Joey's, in his own terminal.
- **Not mapped:** the Link to Project search screens (screen-map open item 5). The demo snapshots the page right after the Link to Project click (`demo-S8-link-opened.yml`) and guesses the search box and result; a wrong guess is a guard refusal or a timeout, then the demo stops and Joey links by hand.
- **Guard allowlist additions (loosening, Joey's demo):** `leave_project_menu` (click the inert header text "Welcome Agent" so the Project hover menu closes) and `run_project_search` (click the Projects panel's plain "Search" label so the search runs; SPEC.md -> Project search planned this). Both change nothing in MySys. Opening clicks (open a Note, open a project, Note Pool Refresh, run the Projects search) are tried up to 4 times; Playwright never clicks a covered element, so a retry can't act twice.
- **Found on the test site (27 Oct, read-only runs):** (1) after a choice in the Project hover menu, Playwright's mouse stays on it and the page takes no click below the header ("body intercepts pointer events") until a real mouse moves over the window; headless, it never clears (likely 1.8's section-tab problem too). The demo therefore always runs headed and prints `INFO  demo: page blocked - move the mouse over the browser window` while it waits. A guarded mouse move (a `hover` kind in the guard) would fix it without Joey; that loosens guard_check, so it waits for Joey. (2) `fill` alone did not run the Projects search. (3) The Note body is a `<pre>`; the file name beside the link is now a `<span>` with text.
- **28 Oct 2026, Link to Project seen live (S8):** it opens a floating window "Choose Project" with textboxes "Search/filter", "After..." and "Before..." and no results until a search runs. The demo fills Search/filter with the pln, then clicks the window's heading so focus leaves the box (as the Note Pool search needs) - new allowlist entry `link_run_search`, a click that changes nothing in MySys - then selects the one result naming the pln and snapshots the results (`demo-S8-link-results.yml`) for mapping. After linking, Status reads "Pending by <agent>", so the read-back checks it starts "Pending".
- **28 Oct 2026, 12:09 run:** the Choose Project heading showed at once but its Search/filter only after the 15 s wait had given up, so the picker and its results get 60 s. **`--probe-link`** (Joey): S1, open the Note without taking it, Link to Project, search the pln, snapshot the window and its results to `private/captures/test/demo-probe-link-results.yml`, stop without selecting (the browser closes; no close button is pressed). No write, so a try costs no test-site reset. Snapshots now include child frames.
- **28 Oct 2026, 12:28 probe:** it printed "link probe done" though the results snapshot held no Choose Project window. The window was found as "heading + a Search/filter box", and while its content loads that matched an ancestor holding the Note Pool's own Search/filter. It is now anchored on its own "After..." box. Each sub-step checks the window is still open, and the probe snapshots each one (`demo-probe-link-1-opened`, `-2-filled`, `-3-searched`, `-results`) and fails if the pln isn't listed.
- New dependency: `pdfplumber` (Joey approved). Output: `NEXT` prompt lines and fixed `demo: ...` INFO lines; the final NOTE line has only identifiers.

## 25 Oct 2026 - M0b.1 maps only what 1.8 and 3.1-3.3 need; its findings (Joey; mapped with Claude observing)

- **Scope (Joey):** for the MVP, M0b.1 maps only the cases task 1.8 and tasks 3.1-3.3 need. No new Notes were made for it.
- **Rows 21-22 dropped.** The attachment rule stands without them: the Note window must have exactly one "Download document" link whose URL `file_name` ends `.pdf` (any case). None → `NO_PDF`, more than one → `MULTIPLE_PDFS`, anything not recognised → `NO_PDF`. Every one is a skip back to the pool. The link's name is only "Download document"; the file name is in its URL (row 26).
- **Row 23 (a)-(c) moved to M0b.2**, before 3.6 (which comes after the Milestone A demo): does an open Note window refresh its Assignee after someone else reassigns it. The assignee check never relies on it (a fresh Note Pool read). Row 23 (d), the Note Pool search by Note ID under All Pools, is mapped in row 27.
- **Anchors (row 26):** the Note Pool filters by their fixed `name` attributes; the Note window's user and pool lists as the selects containing `--Select User--` / `--Select Pool--`; the Note Pool and Projects panels by the controls they hold (neither has a heading, and their container ids are generated). The login page's controls all have names.
- **Searching the Note Pool (row 27):** `fill` alone doesn't run the search; it runs when focus leaves the box. The agent fills, then clicks the panel's **Refresh** (added to the allowlist, a new guarded click). Refresh plus the focus change once showed the same Note twice while the footer said 1 item, so the row count must equal the footer's count, after one more Refresh at most, else `UNEXPECTED_SCREEN`. A filter-select change reloads the list by itself.
- **What persists (row 27):** a reload keeps every filter and the Search/filter text, closes every window, lands on Dashboard and hides the module tabs until Project is clicked. A fresh login resets every filter. So the run-start list read sees defaults; within a run the driver sets and reads back what it needs.
- **Moving between windows (rows 25, 28):** an open Note window stays on top of the Projects panel and covers its results. The agent doesn't minimise it or use the taskbar: it reloads after the Note-window steps, searches and reads the project, then reloads and reopens the Note from the Note Pool. A project that is already open doesn't open twice.
- **Returning a Note (row 15b):** one Assign with `--Select User--` + the pool works from a freshly opened Note window. The walkthrough's two Assigns aren't needed.
- **Not mapped:** whether `fill` alone runs the **Projects** search. Task 3.2 checks it first; if not, it clicks the panel's "Search" label to move focus (with its own decisions entry); if that fails, Joey decides (the guard bans key presses).
- Carried in: `docs/screen-map.md` v1.2, `SPEC.md` v1.16 (MySys screen rules, Expected slices), `tasks/plan.md` (M0b.1, M0b.2, 1.8, 3.1, 3.2, 3.6, gate for M3), `tasks/todo.md`, `docs/workflow.md`.

## 25 Oct 2026 - Decision 2, Milestone A first, the repo is public (Joey)

- **Decision 2:** the CEO delegated it to Joey; Joey decides yes, on the terms in `SPEC.md` → Trial conditions. The CEO approved D2 (the trial PDF on the Mac Mini's disk from its download until it's read into memory). Task F.5 is done. 3.4's Mac Mini run is no longer waiting on the CEO.
- **Milestone A comes first:** a decide-only demo to the CEO. The Mac Mini runs the agent by itself against the test site: it logs in, takes each eligible Note, downloads and reads the PDF, decides PROCEED or SKIP, and returns the Note to the pool, writing nothing. Scope: 1.4, 1.6, 1.7, M0b.1, 1.8, 1.9, 1.10; M2 (2.1–2.6); M3's 3.1, 3.2, 3.3, 3.5, then 3.4. For the demo the launchd job may be loaded in decide-only mode (hourly, no writes); plain `run` still refuses until 4.5.
- **3.6 moves after the Milestone A demo.** The assignee check and the stale-Note stop guard writes, and Milestone A has none. 3.6 is still built and merged before any booking code (D1 holds): it joins the gate for M4. M0b.2, M4, M5 and M6 are unchanged and follow Milestone A.
- **The repo is public** (Joey, 24 Oct 2026), so the CEO can read it in a browser. It holds no credentials, PDFs, addresses or client names (the repo-data check, pre-commit and gitleaks in CI guard that), only the 3 trial POs' identifiers, which Must never #6 already allows in committed files. This replaces "private GitHub repo" in `SPEC.md`.
- Carried in: `SPEC.md` v1.15 (assumption 8, open question 4, Expected slices), `tasks/plan.md` (3.6, gate for M4), `tasks/todo.md`, `docs/workflow.md` v5.16.

## 24 Oct 2026 - protect_paths allows three folders outside the repo (Joey; plan task 1.2)

- Plan task 1.2 said `protect_paths.py` blocks every path outside the repo. That would also block plan mode's plan file, Claude Code's memory and Claude's scratchpad, and "plan mode first" is how every step task starts.
- So exactly three folders outside the repo may be written: `~/.claude/plans/`, this project's memory folder (`~/.claude/projects/<project path, every non-alphanumeric as "-">/memory/`) and `<temp>/claude/`. Everything else outside the repo stays blocked, including `~/.claude/settings.json`, `~/.claude/settings.local.json` and `~/.claude/hooks/`.
- Paths are resolved first (absolute, `..` collapsed, symlinks followed) and matched by whole folders, never as a string prefix, so `~/.claude/plans-evil/` doesn't match and `plans/../settings.json` is blocked. The tests cover both sides.
- `tasks/plan.md` 1.2 and `docs/workflow.md` v5.15 (Appendix A) and `SPEC.md` v1.14 (Project Structure) carry the change.

## 24 Oct 2026 — A lighter process for the MVP (Joey)

The MVP's goal is to show the agent runs by itself on the office Mac Mini against the test site. Task 1.1, a check script, took several days: three review rounds, mutation probes, and the same four documents re-edited for each small rule change. The safety core stays as it is; the process around it gets lighter.

- **Review stop only where it matters.** Every task still writes its failing test first and shows it failing. Claude stops for Joey's review before writing code only on 1.2, 1.4, 2.2–2.5, M3 (3.1–3.6), M4 (4.1–4.5) and 5.2: the guard, the hooks, the decision engine and readers, and anything that acts in MySys. On the other tasks it commits the test and carries on. Test changes still go in their own `test:` commit.
- **The freeze rule covers the agent, not the tooling.** A dated entry here plus `SPEC.md` and `tasks/plan.md` is needed for a change to what the agent does in MySys or prints in its run output, or for anything that loosens a safety control (the guard, the hooks, the repo-data check, CI, a Must-never rule). Tightening a dev-tooling rule needs only a clear commit message.
- **No extra work.** No mutation probes, no second review round unless the fixes were large, and no doc edits a task doesn't need.
- **Also in `CLAUDE.md`:** new text uses a plain dash, not the em dash; `uv.lock` and other generated files are changed only through their tool; an unrelated failure is reported, not fixed in the current task; the agent-skills commands are listed by their full names.
- Unchanged: the guard, the two readers and their agreement rule, skip on doubt, test site only, the Must-never rules, check + CI, Joey merges.
- Carried in: `CLAUDE.md`, `SPEC.md` v1.13 (Code style), `tasks/plan.md` (Cross-cutting rules), `docs/workflow.md` v5.14 (Stage 5 step 4, ground rules).

## 19 Oct 2026 — The repo-data check is stricter (Joey; plan task 1.1; widened 21 Oct 2026 after the task's code review and security review)

- The banned folders match **at any depth**, as `.gitignore` does, and the list adds `.state/` and `traces/`, both already git-ignored: `private/`, `logs/`, `state/`, `.state/`, `traces/`, `.playwright-cli/`.
- Trace files match `*trace*.zip` (was `trace*.zip`), so `.gitignore`'s `*.trace.zip` is caught too.
- **Widened 21 Oct 2026:**
  - **Any case.** Folder names and extensions match in any case (`Private/`, `shot.PNG`); this laptop's file system ignores case.
  - **Secret files.** `.env` and `.env.*` files (no `.env.example` exception), `.env/` and `secrets/` folders, and `config/live*.toml` are banned at any depth (`.env/` folders added 24 Oct, after the second code review: `.gitignore`'s `.env` matches a folder too). They were only git-ignored, which `git add -f` gets past, and gitleaks can't recognise a MySys password by its pattern.
  - **Images.** `*.png`, `*.jpg`, `*.jpeg`, `*.webp` and `*.gif` are banned anywhere, because test-site screen captures are real data (Must never #6). `.yml` stays allowed (CI and pre-commit need it), so a copied-out accessibility snapshot isn't caught by the rule; review still has to.
  - **Fixture PDFs.** The rule can't tell a real PDF in `tests/seam1/fixtures/pdfs/` from a fake, so plan task 2.1 now requires every committed fixture PDF to match the generator's output byte for byte.
- ruff skips `*.md`: ruff 0.17 also formats Python blocks in Markdown, and the docs' snippets are illustrative, not code.
- `SPEC.md` v1.12 (Commands), `tasks/plan.md` 1.1 and `docs/workflow.md` v5.12 (Appendix A) carry the change.

## 16 Oct 2026 — MVP plan frozen: decisions D1–D7 (Joey; proposed by Claude after two doubt-driven reviews of `tasks/plan.md`)

`tasks/plan.md` and `tasks/todo.md` are approved. This is the freeze point: from now on a behaviour change needs a dated entry here plus `SPEC.md` and `tasks/plan.md`, in the same commit. `SPEC.md` v1.11, `docs/specs/spec.md` v1.7, `docs/workflow.md` v5.10 and `docs/macmini-setup.md` v1.2 carry the changes.

- **D1 — run controls before booking.** The kill switch, Perth window, run cap and assignee check are built in M3, before any booking code; M5 keeps the alerts and the safety cases. After the S1 spike the Mac Mini job is unloaded, and it is loaded only for the first bookings (plan task 4.6) and from M6. Until then, plain `run` refuses (exit 2). Why: the wrapper pulls `main` every run, so a merge would otherwise deploy booking code to a loaded job with no controls.
- **D2 — the trial PDF briefly on disk.** Chromium writes every download to disk, so "in memory only" isn't possible. The browser is launched with `downloads_path` set to a run-scoped temp folder. The file is read into memory and deleted at once, the folder is removed in a `finally` block, and leftovers are removed at every run start. W1 uploads from the bytes. FileVault is on. **CEO decision 2 was asked on "in memory only", so Joey tells the CEO before it's confirmed.** `CLAUDE.md` Must never #6 needs Joey's wording change.
- **D3 — real-page refusal tests can't press anything.** The guard is split into `vet()` (resolve, allow or refuse; no action code) and `act()` (calls `vet()`, then acts on the element `vet()` resolved). Tests on the real site that prove a refusal (Discard, a Hold-dialog checkbox) call only `vet()`; `act()` refusing is tested on local HTML. Recorded as not "targeting" under Must never #2 (Joey adds the wording to `CLAUDE.md`).
- **D4 — where forbidden strings may appear.** The live host only in `guard_bash.py`'s deny regex (`(?<!test-)prompt\.mysys\.com\.au`) and its test; `ANTHROPIC_API_KEY` only in the secrets test that proves it's ignored; a fake `sk-ant-` string only in the hook test, allowlisted for gitleaks by path. `CLAUDE.md` Must never #3 and Secrets need Joey's wording, #3 before plan task 1.2.
- **D5 — the denylist on a `<select>`** checks the select's own name plus the label of the option being chosen, never every option's text.
- **D6 — the stale-Note stop.** At the start of `run` and `run --decide-only`, after login, a Pending Note still assigned to the agent (left by an earlier partial write or failed return) stops the run with an `ALERT` before any Note is taken. This **reverses** SPEC v1.10's "Note left assigned to the agent (so later runs ignore it)": with no state between runs, one systematic bug could otherwise leave a half-booked Note every hour. MySys is the state, so nothing is stored.
- **D7 — assignee check before W1 and W4 only** (`SPEC.md` §8 and `docs/specs/spec.md` §8 said before every write). Each check leaves the current window for the Note Pool; before W2 that meant leaving a filled, unsubmitted Create New Task form that no screen-map row covers, and then submitting it unchecked. W1 → W2 → W3 now stay in the project window, and `enabled` is still re-read before every step. Cost: a person taking the Note during W1–W3 is caught at W4 as `PARTIAL_WRITE`, which is what the every-write rule gave from W3 on anyway. Option B (keep every write, map the form's round trip, repeat W1's read-back before Submit) was rejected.
- **One agent at a time** (follows from D7 and the shared agent account): no laptop test-site run while the Mac Mini job is loaded, and no manual Mac Mini run while a laptop run is going.
- **Plan open questions answered as recommended:**
  - (2) The dependencies are `playwright`, `pdfplumber`, `anthropic`, `pydantic` and `keyring`; the dev dependencies are `pytest`, `ruff`, `pre-commit`, plus `reportlab` for the fake-PDF generator. Anything else still gets asked.
  - (3) The allowlist adds login (username, password, "Log in") and the module navigation (Project top tab, Note Pool, Projects sub-tab).
  - (4) Two new NOTE values for run output only: `"outcome": "skipped", "reason": "DECIDE_ONLY"` and `"outcome": "untouched", "reason": "NOTE_TAKEN"`.
  - (5) CI installs Chromium for the guard's tests.
  - (6) `enabled` is re-read before every write step.
  - (7) The run cap is checked before each new Note, and a Note in progress is finished. Kill-switch and window exits are code 0.
  - (8) The booker has a test-only `stop_after` parameter; `run` never passes it.
- **Also fixed in the plan:**
  - **Guard:** the build check bans the `request` attribute rather than HTTP verb names (which would have caught `download.delete()`). Locator names are matched exactly.
  - **`Proceed`:** it's frozen and names its `note_id`, internal number and pln.
  - **Email box:** Send Email Notification is unticked after `before_write`, right before the committing click.
  - **Test output:** seam-2 and real-PO failure reports are cut to the exception type, so no real data reaches test output. Selecting `-m testsite` explicitly turns a missing secret into an error.
  - **Spike:** it needs M0b.1 (panel anchors) first.
  - **Accepted for the MVP:** a short list in `tasks/plan.md` → Risks.
- **M0b grows:**
  - M0b.1 adds rows 25–28 (moving between windows, anchors for unlabelled controls, the Note Pool after a filter change, reload or login, and reopening an open project).
  - M0b.1 also asks whether `fill` alone runs a search, and whether returning a Note to the pool takes one Assign or two.
  - M0b.2 closes screen-map open item 8 in full and checks whether the upload is saved before Submit.
  - M0b.1 is now needed before plan task 1.8, the spike.

## 16 Oct 2026 — The 3 trial POs are real; SPEC fixed against the screen map (Joey; defaults proposed by Claude, accepted by Joey)

- **Found:** the 3 trial POs on the test site (2609017B, 2609034B, 2610002B) are **real B1 POs**, with real site addresses and client names. The test site's 2609017B PDF is byte-identical to the live one in `private/pdfs/`.
- **Decision (Joey): keep them as the trial POs and change the rules.** Their internal numbers, PO numbers and test-site plns may appear in committed files and run output (they already do). Their PDFs, addresses, client names and other PDF content stay in MySys and `private/`; test-site captures and screenshots now count as real data. The Mac Mini reads them from the test site in memory and sends them to Claude, as on live, so **the CEO must confirm decision 2 before the first Mac Mini run that downloads one** (M3). Seam 1's committed fixtures become 3 **generated fake** POs (M2; the generator's dependency needs Joey's OK). The 3 trial POs join the laptop-only real-PO seam. `docs/specs/spec.md`'s address examples were replaced with fake ones, in case they were real (ADR-001 line 125 still has the old example; ADRs are left as recorded, Joey to decide). A check of the tracked files found no address or name from the 3 PDFs.
- **Live Projects search (Joey):** 3–4 projects come back per internal number, and only one ends with `/048`; the others are ignored. Rule: exactly one row with Company B1 Homes and Client Ref No. `<internal no>/048` (on test, where Client Ref No. is the bare number, `<internal no>`). SPEC assumes the column is Client Ref No.; confirm in Stage 3B.
- **Defaults proposed by Claude on Joey's "fix them", all accepted by Joey on 16 Oct 2026** (all in `SPEC.md` v1.10 → MySys screen rules):
  - **Duplicate check, MVP:** any non-Cancelled Compaction Test task on the project → `DUPLICATE_TASK`, whatever its PO number (the task table doesn't show PO numbers). v1 compares PO numbers from the task detail screen.
  - **New skip reason `NOTE_ALREADY_LINKED`** (step 2a), plus step 0 needs the Note Pool's Project cell to read `---`. Otherwise a pre-linked Note would pass every check and fail at W4 after the task exists.
  - **"close" is denylisted** (it removes the attached PDF and clears Task Client). The agent never clicks a window Close: it reloads `base_url` between Notes.
  - **Upload to PO Documents** (as in the walkthrough), not Documents; **task Note = the Note's body**, not its title (the captures show a one-line body).
  - **Send Email Notification** is unticked and read back before every write on the Note window (Assign, Link, Solved), not only before Assign.
  - **Assign to pool:** user list `--Select User--` + pool list Agent Pool, because the user list pre-selects the agent.
  - **Assignee check:** a fresh Note Pool search by Note ID, not the open Note window.
  - **W2:** the new task is the one Compaction Test number that wasn't there before Submit; PO number, document and Note are read back on the task detail screen.
  - **W3:** before confirming Hold, also check Reset unticked, reminder ticked with 0, the heading names the new task (check 3.1).
  - **Attachments** are counted before any click (two links → `MULTIPLE_PDFS`, not a guard refusal). **Note Pool:** oldest first, page 1 only.
  - **"Changes nothing" on a rerun** means no task, link, Solved or final-assignee change; the Assign log lines from re-checking a skipped Note are expected.
- **New slice M0b** (Joey clicks, Claude observes): task detail screen, Link to Project search/select, Notes with 0 and 2 attachments, Note-window refresh and Note Pool search by ID, PO Number prefill. M3 needs the attachment and assignee parts; M4 needs task detail and Link.
- **Corrections:** the Compaction Test sub-form has no Creator (the one Creator is in the Client section); test Notes come in both title styles (below). `CLAUDE.md` Must never #2 and #6 updated. `SPEC.md` v1.10, `docs/specs/spec.md` v1.6, `docs/screen-map.md` v1.1.

## 16 Oct 2026 — Screen map written; the denylist grows (Joey)

- **`docs/screen-map.md` v1.0** maps Stage 3A rows 01–16 on the test site, with fake values only. The checks below come from it.
- **The denylist adds four buttons** found in the walkthrough: **Pending** on the Note (reopens a Solved Note), **Undo Cancellation**, **Un-Hold** and **Change Project**. Names are matched as substrings, case-insensitive ("Undo Cancellation" contains "Cancel"). The Note Pool's Status filter lists a Discard option, so the agent never sets that filter. `docs/specs/spec.md` v1.5 §5 and `SPEC.md` v1.9 (Never, open questions 1, 3, 8 and 9). `CLAUDE.md` Must never #2 still lists only the original buttons: Joey to update it.

## 16 Oct 2026 — Check 3.1 (C1): the Hold dialog's related-task checkboxes are unticked by default (Stage 3A, row 11)

- **Found:** in the Hold Task dialog every Related Tasks checkbox (58 jobs on the walkthrough project) and the Select-all box were **unticked**. "Reset turn around time" and "Send me a reminder email at this date" were unticked. "Send me a reminder email every **0** days" was **ticked**, and 0 means no reminders.
- **Decision:** C1 doesn't block Hold on the test site, so no CEO decision is needed before M4. The agent still touches no checkbox in the dialog (Must never #2). Before pressing Hold it reads every one: any related-task or reset box ticked, or the reminder not 0, → close the browser context, `PARTIAL_WRITE` alert (the task already exists).
- **Live:** not seen (opening Hold on live would be a write). Confirm on the first live booking under supervision. `docs/screen-map.md` row 11.

## 16 Oct 2026 — Check 3.2 (C3): a Note goes back to the pool with Assign, no Unassign (Stage 3A, row 15)

- **Found:** on the Note window, choosing **Agent Pool** in the pool list and pressing **Assign** moved a Note from Agent 1 (MySys Only) to Agent Pool. Log: "User Assigned: … From Agent 1 (MySys Only) to Agent Pool"; Assignee reads Agent Pool; status stays Pending. No Unassign or Unlink was needed.
- **Decision:** C3 is answered "yes"; the skip path ("Note back to the pool") uses Assign with the pool list, and no CEO decision is needed before M3. Unlink unassigns *without* putting the Note in a pool (seen at row 04), which is one more reason it stays denied.
- **Live:** the pool there is PO Allocation Pool; not tried (view-only). `docs/screen-map.md` row 15.

## 16 Oct 2026 — Check 3.3: Send Email Notification is only on the Note window (Stage 3A, rows 02–15)

- **Found:** the checkbox appears **only** in the Note window's Assign controls, and it is **ticked every time a Note window opens**. It isn't on Create New Task, the Hold Task dialog (which has its own reminder-email checkbox, see check 3.1) or with Solved. An untick holds through Assign while the window stays open.
- **Decision:** the agent unticks it and reads it back as unticked before **every** Assign, including the skip path. Joey's view (16 Oct 2026) is that a ticked box doesn't matter; CLAUDE.md Must never #4 and `SPEC.md` keep the untick until Joey changes them.
- Not known: whether an email went out when the walkthrough assigned with the box ticked (row 03). `docs/screen-map.md` rows 02–04.

## 16 Oct 2026 — Check 3.4: no MFA seen on the agent account; password expiry unknown

- **Found:** the test-site login page has Username, Password and "Log in" (plus a "Microsoft account login" link the agent doesn't use). Joey logged in as the agent account four times on 16 Oct 2026 with no second step.
- **Decision:** MFA doesn't block M1 on the test site. **Still open:** whether the agent account's password expires, and the live login. Joey to ask the MySys admin before the Mac Mini runs unattended; a failed login already stops the run (`LOGIN_FAILED` alert).

## 16 Oct 2026 — Check 3.5: opening a Note or downloading its PDF changes nothing visible (Stage 3A, rows 02, 05)

- **Found:** on three Notes, opening the Note window and downloading the PDF added **no log line** and left assignee and status unchanged. The download link carries a `user_note_id` that differs from the Note ID. Clicking the file row also opens a preview window.
- **Decision:** Stage 3B may open live Notes and download their PDFs (still no Assign or any other button). Caveat: the Note window doesn't show lock state, so whether opening a Note locks it can't be seen; the Locked filter changed between captures, probably by hand.

## 16 Oct 2026 — Check 3.6: how a cancelled task looks; an On Hold task offers Cancel (Stage 3A, rows 09–14)

- **Found:** a cancelled task's row reads "(tsk_N) | Compaction Test" with an **Undo Cancellation** button and Status **Cancelled**. An On Hold task's row shows **Cancel** next to **Un-Hold**, so it can be cancelled directly (offered; the walkthrough didn't press it). A new task shows Cancel and Hold.
- **Decision:** the test profile's duplicate check (ignore Cancelled, 15 Oct entry) recognises a cancelled task by its Status cell **Cancelled** (or the Undo Cancellation button). The reset (Stage 6.1) can cancel an On Hold task without releasing it first. The project table doesn't show the PO number, so the duplicate check must open each Compaction Test task to compare PO numbers (`docs/screen-map.md` open item 2). The agent never presses Cancel, Undo Cancellation or Un-Hold.

## 16 Oct 2026 — 3 real POs for the MVP's real-PO seam (Joey)

- **The real-PO decision seam (`-m real_data`) uses the 3 most recent real B1 `/048` POs** for the MVP, not 10–20 (14 Oct entry below). Joey saved them to `private/pdfs/`, with their cases in `private/fixtures/cases.toml`, on the laptop only.
- **What it proves is narrower:** 0 false PROCEED on 3 POs is weak evidence, and coverage can't be judged against 80% with 3. So S3 reports coverage without the 80% line, and any skip of a clean real PO is reviewed before M3.
- **Before go-live, the set grows to 10–20** (mostly `/048`, plus other suffixes and odd ones), and the 80% coverage line applies then. The CEO's go-live sign-off uses that larger set.
- `SPEC.md` v1.8 (testing strategy, M0, S3), `docs/workflow.md` v5.8 (Stage 3B), `README.md`, `docs/specs/roadmap.md`.

## 16 Oct 2026 — The last step is Solved; the test site has no Resolve button (Joey)

- **Found in the Stage 3A walkthrough** (2609017B and 2610002B): after Link to Project, the Note's Status buttons are **Pending, Solved and Discard**. There is no Resolve button. This replaces SOP step 15's "Solved and Resolve are equivalent; use Resolve" and `docs/specs/spec.md` story 28's "using Resolve, not Solved".
- **W5 = press Solved on the Note.** Read-back: the status reads "Solved by" the agent, a log line "Status changed … From Pending to Solved" appears, and the Note leaves the Pending list. Once a Note is Solved, **Pending** reopens it, so the agent never presses Pending.
- **Live is still to check** in Stage 3B: if live has a Resolve button, decide then which one the live profile uses.
- **Stage 3A gets new rows** for the screens off the happy path: 15 (send a Note back to Agent Pool with Assign, the skip path), 16 (Projects search with no match, moved out of row 06), 17 (optional: a Create New Task error) and 18 (a cancelled task, was row 07b).
- `SPEC.md` v1.7, `docs/specs/spec.md` v1.4, `docs/workflow.md` v5.7, and the wording in `CLAUDE.md`, `docs/intent.md`, `docs/project-context.md`, `docs/demo-runbook.md`, `docs/macmini-setup.md`, `docs/specs/mission.md`, `README.md` and `roadmap.md`. ADR-001 is left as recorded.

## 15 Oct 2026 — CEO decision 3: the office Mac Mini runs the trial and production (CEO; setup choices by Joey)

- **Host = the office Mac Mini** (ADR-002 Option D, now **Accepted**), for the MVP trial **and** production. It replaces the Anthropic cloud routine for the trial (Option C, 14 Oct entry below) and the expected Sydney cloud VM for production. ADR-002's 14 Oct scores (A 4.60, B 4.20, D 2.80) are kept as the record; the CEO chose D because the Mac Mini was already bought. Maintainer: Joey, with a named backup admin.
- **The trial waiver is withdrawn.** On the Mac Mini, gate H2 passes (secrets in the agent user's Keychain; no AI session on the machine) and H5 passes (company-owned; Joey's and a backup admin account). `SPEC.md` → Trial waiver becomes **Trial conditions**: test-site credentials only, a dedicated low-limit Anthropic key, no real client data on the Mac Mini during the MVP.
- **A separate standard macOS user `poagent`** runs the agent; Joey and the backup have admin accounts. Claude Code is never installed for `poagent`.
- **FileVault on, no automatic login** (Joey, 15 Oct 2026). macOS allows one or the other. The Mac Mini will hold the live MySys password and handle real POs in production, and a missed run only delays POs (they stay in the pool), while a stolen unencrypted Mac gives up the agent's Keychain. Cost: after an unplanned restart (e.g. power failure) the Mac powers back on but waits at the FileVault screen until someone logs in as `poagent`. Revisit if this costs too many runs.
- **Schedule:** a launchd LaunchAgent in `poagent`'s session at **7 minutes past each hour, 07:07–17:07, Monday–Friday**, Mac clock set to **Australia/Perth**. A LaunchAgent (not a LaunchDaemon) because keyring needs `poagent`'s login Keychain, which is unlocked only while that user is logged in. launchd never starts the job while it is still running.
- **The Mac Mini stays up:** no sleep, starts up automatically after a power failure, macOS updates download automatically but are installed by hand **outside 07:00–18:00** (weekday evenings or weekends).
- **Secrets:** in `poagent`'s login Keychain through `keyring` (service `po-agent`, the same names). No `PO_AGENT_*` variables on the Mac Mini; env vars remain for CI and tests.
- **What the routine's Claude session did moves to a small script**, `scripts/macmini-run.sh` (M1): pull `main` (so `enabled = false` on `main` still stops the next run), `uv sync --locked`, run the agent with a 20-minute limit, append the short run output to `~/Library/Logs/po-agent/runs.log`, and on any `ALERT` line or non-zero exit open a GitHub issue labelled `po-agent-alert`. The Mac Mini's GitHub access is one fine-grained token for this repo only (contents read, issues write), kept in the Keychain by `gh`.
- **The MVP still keeps no state between runs** (Joey's 14 Oct choice, now for scope, not because of the host). `runs.log` is a record for Joey, not state the agent reads. v1's skip list, logs and `STOP` file go on the Mac Mini's disk.
- **First step on the Mac Mini:** a MySys test-site login by hand from it, before anything else is installed (`docs/macmini-setup.md` section 2).
- Setup steps: `docs/macmini-setup.md` (replaces `docs/routine-setup.md`). `SPEC.md` v1.6; `docs/specs/spec.md`, `tech-stack.md` and `roadmap.md` v1.3.

## 15 Oct 2026 — Repeatable demo (Joey)

- **The demo must be repeatable, at least 3 times** (to Joey's boss and the CEO). After each demo Joey resets the test site with his own account: cancel the 3 trial tasks, place fresh copies of the 3 Notes (`docs/demo-runbook.md`). The test profile's duplicate check ignores Cancelled tasks, so the agent books the same POs again. New success criterion `SPEC.md` S8; `SPEC.md` v1.5.
- Demos can be shown from the laptop (`--headed --slow-mo 500`, the browser visible) or from the routine (**Run now**). *(The routine is replaced by the Mac Mini: CEO decision 3, entry above.)*

## 15 Oct 2026 — MVP spec approved (Joey)

- **`SPEC.md` approved** (v1.4). Next: M0 screen mapping, then `/plan` in Claude Code.
- **Test-site reset:** Joey's own account can **cancel** tasks on the test site; that's how the test site is reset (`docs/workflow.md` Stage 6.1). The agent itself still never presses Cancel.
- **Duplicate check, test profile only:** ignores Compaction Test tasks whose status is Cancelled (`duplicate_ignores_cancelled = true` in `config/test.toml`). On live every existing task counts. Seam 1 tests both settings.
- **Joey's Claude plan is Pro:** the routine's environment isn't shared; routine runs use Pro usage; *(routine parts superseded by CEO decision 3)* the claude.ai model-training setting must be off before Claude Code reads real data.
- **Node.js can be installed** on Joey's laptop, so Playwright CLI is used for screen mapping.

## 15 Oct 2026 — Screens mapped with Playwright CLI; all 3 trial POs at every stage (Joey)

- **Screen mapping uses Playwright CLI** (`@playwright/cli`), observe-only: Joey does every click and every typed value, including the login; Claude Code only runs `snapshot`, `screenshot`, `find` and `generate-locator`, and writes `docs/screen-map.md` from the accessibility trees. `.claude/settings.json` denies every acting, state or network command; from M1 the `guard_bash.py` hook allows only the observe commands. `.playwright/cli.config.json` blocks the live origin. Its bundled skills aren't installed. The custom `po-agent capture` command is dropped. Fallback without Node.js: the classic `playwright codegen` recorder plus screenshots.
- **The 3 trial POs at every stage:** walkthrough = full SOP for 2609017B, read-only screens for 2609034B and 2610002B; M4 books all three in turn; seam 2 and the S4 trial book all three; the S5 skip case is a fresh copy of 2609034B.
- **`improve-codebase-architecture` vs Addy's skills:** it doesn't replace them. It's the better tool for one job (surveying the code to shape the shared MySys package), so it's used after the MVP and before automation #2 only.

## 14 Oct 2026 — Only the 3 trial POs; Addy's skills plus one Pocock skill (Joey)

- **No 4th fake PO.** The walkthrough, the build and the MVP demo use only the 3 trial POs (2609017B, 2609034B, 2610002B). The walkthrough books 2609017B by hand, so the test site is **reset** by Joey (own account) before M3, after each booking test and before the demo. The skip case in the demo is a fresh copy of a booked trial Note (`DUPLICATE_TASK`); address and other mutations are tested offline in seam 1. Open: can Joey's own account remove a task on the test site?
- **Skills:** Addy Osmani's agent-skills is the main workflow (following its greenfield tutorial). Matt Pocock's `improve-codebase-architecture` (with `codebase-design`, `grilling`, `domain-modeling`) is installed only for an architecture review after the MVP and before automation #2, then removed. The full Pocock plugin isn't installed. Details: `docs/workflow.md` → The skills plan.

## 14 Oct 2026 — The agent may read real client data (Joey; CEO to confirm)

- **Rule change:** the agent may see real client data. Claude (the reader) may read real B1 PO PDFs and Note text; Claude Code may read real PDFs and live-screen captures on Joey's laptop to understand the pages. Joey's call; it answers CEO decision 2 once the CEO confirms. Decision 2 stays open in the CEO decision brief until then.
- **The agent has its own MySys account** on live (as on the test site).
- **Bookings stay on the test site.** The MVP's code never logs into live; go-live still needs the CEO's sign-off after the trial (decision 1).
- **Real data stays on Joey's laptop:** the git-ignored `private/` folder (real PDFs, live screenshots, captures, `cases.toml`). Never in GitHub, a PR, an issue, run output or the cloud routine. A commit hook and the check command block it.
- **Live is view-only during capture:** no Assign, no edits, no bookings with the agent account.
- **New MVP evidence:** a real-PO decision-seam run on the laptop (`-m real_data`, 10–20 real POs): 0 false PROCEED, with per-field agreement, coverage and cost per PO.
- **Before Claude Code reads real data:** on a Pro/Max plan, the claude.ai model-training setting must be off.
- C4 (rules-only address reader) becomes unlikely to be needed; it stays deferred until the CEO confirms decision 2.

## 14 Oct 2026 — MVP first, on an Anthropic cloud routine (Joey)

*The hosting parts of this entry (trial host, waiver, routine alerts, secrets on the routine, production host) are superseded by CEO decision 3, 15 Oct 2026 (above). The MVP scope stands.*

- **Build an MVP first** to prove the agent works end to end on the test site, before the full v1 hardening. Scope chosen by Joey: **happy path + core safety** (`SPEC.md` → Objective): the full ADR-001 design (two readers, verify-not-extract, agreement), all checks before any write, action guard, read-back, skip → pool through Assign, `enabled` kill switch, Perth window, deterministic-only switch, test site only. Deferred to v1: skip list and 24 h retry, partial-write auto-resume (MVP: alert, Note left assigned to the agent, Joey finishes by hand), agent-written `STOP` file (MVP: exit code 3 + alert; Joey turns the routine off), circuit breaker (MVP: first failure stops the run), start-of-run sweep, single-run lock, daily logs with retention, live profile, sender-domain check, email/Teams alerts.
- **Trial host = ADR-002 Option C: an Anthropic cloud routine running the script.** The script still does every click and Claude (the reader) still only reads; the routine's own Claude session only runs three fixed commands and reports.
- **ADR-002 gates H2 (secrets unreadable by the AI session) and H5 (company-owned) are waived for the trial only.** Scope: the test-site agent account, a dedicated Anthropic key with a low spend limit, fake data only. Mitigations in `SPEC.md` → Trial waiver. The waiver never covers live credentials or real POs.
- **No state between routine runs for the MVP** (Joey, 14 Oct 2026). MySys is the state: resolved Notes are done, the duplicate check stops double bookings, skipped Notes are checked again each run. The run transcript is the log. (A git state branch was considered and not chosen.) The skip list, logs and `STOP` file come back in v1 on a host with a disk.
- **MVP alerts:** `ALERT` lines in the run output; the routine opens a GitHub issue labelled `po-agent-alert`, so GitHub emails Joey.
- **Secrets naming:** environment variables `PO_AGENT_*` first (routine; later the VM's root-only env file), keyring fallback (laptop). Not `ANTHROPIC_API_KEY`, so Claude Code itself can't pick it up.
- **GitHub is now required** (routines clone from GitHub). The "no GitHub" fallback is dropped. CEO/IT OK still to get.
- **Production host:** most likely a **Sydney cloud VM** (ADR-002 Option B). Not decided: CEO decision 3 is pending. ADR-002 stays *Proposed* for production.
- **Skills:** the build uses **Addy Osmani's agent-skills** (`/spec` → `/plan` → `/build` → `/review`), replacing Matt Pocock's skills. MVP spec at `SPEC.md`; plan at `tasks/plan.md` and `tasks/todo.md`.
- **Docs moved into the repo:** `claude/intent.md` → `docs/intent.md`, `claude/po-agent-decisions.md` → `docs/decisions.md`, `claude/hosting-research.md` → `docs/hosting-research.md`, `claude/claude-code-workflow.md` → `docs/workflow.md`, `specs/*` → `docs/specs/*`. The repo is the source of truth from now on; the claude.ai project keeps copies.

## Scope

- B1 Homes only. Compaction Test task booking, always a pre-booking → always put on hold. PO = purchase order.
- Live: only notes with subject "[B1 Homes] Order XXXXXXXX/048" (/048 = compaction). PDF must contain "COMPACTION".
- Other suffixes (e.g. /023, /025) are other task types — out of scope, left untouched.

## Architecture (ADR-001 — Accepted; approved by the CEO through decision 1, recorded 13 Oct 2026)

- **Hybrid (Option B).** Deterministic Playwright script does every click through an allowlist; deterministic reader (pdfplumber + patterns + address normaliser/verifier) and Claude (no tools, schema-bound JSON) both read; proceed only if both agree and match MySys. Claude never clicks.
- Scores (weights C1 accuracy 30, C2 messy POs 20, C3 UI change 15, C4 cost 5, C5 effort 15, C6 audit/reuse 15 — set by Claude on Joey's behalf): B 3.95 · A (no-AI script) 3.70 · C (Claude fallback only) 3.45 · D (Claude drives browser) dropped on gates G2/G3. Internal-request replay excluded by G1.
- Flip: A wins if weight(C5)+weight(C4) > weight(C1)+weight(C6), or if a single deterministic address reader is judged as safe as two.
- **Data (G7):** Claude may read real client PO PDFs and note text (Joey, 14 Oct 2026; CEO to confirm as decision 2). Real data stays on Joey's laptop; bookings stay on the test site until go-live.

### ADR-001 action items (approved with decision 1)

1. **ADR accepted.** Status set to Accepted.
2. **Address check = verify, not extract.** Claude extracts lot, street and suburb; the deterministic side verifies each appears in the PDF text (together, in one address block) and matches the MySys project after normalisation. `docs/specs/spec.md` §4.
3. **Decision-seam tests.** Run the full fixture set through both readers; measure agreement on the 3 trial PDFs and the mutated copies. Any false PROCEED is a blocker.
4. **Token cost.** Record Claude token cost per PO during the trial for the CEO.
5. **Option A fallback.** `reader_mode = deterministic-only` must always work. The rules-only address reader is deferred: until it's built, that mode returns every PO to the admin. Build it if decision 2 is "no". *(In the MVP: the switch exists and every PO skips `ADDRESS_UNVERIFIABLE`; the rules-only address reader stays deferred.)*

## Safeguards (approved with decision 1)

- **Half-finished bookings:** the agent records the partial write, alerts Joey, and completes its own booking on the next run after re-running every check. Exception to "no exception report" and "duplicate → skip", for the agent's own task only. *(MVP: alert, Note left assigned to the agent, run stops; Joey finishes by hand; auto-resume in v1.)*
- **Stop after any error:** a booking error (wrong project, wrong PO number or missing PDF found on read-back) makes the agent create a `STOP` file and alert Joey. Only a person removes it, after the CEO approves a restart. *(MVP: no `STOP` file; exit code 3 + alert, and Joey unloads the Mac Mini's launchd job and sets `enabled = false`.)*
- **Without Claude:** POs go to the admin as today.
- **Alerts:** to Joey only, never to customers. Channel (email or Teams webhook) still to choose for v1; MVP uses a GitHub issue.

## Implementation simplifications (13 Oct 2026, Joey)

- No database. State is a skip-list JSON file plus daily JSON-lines logs (one line per Note, one summary line per run), kept 90 days. Extra detail and screenshots only on failures.

## Hosting (CEO decision 3 — decided 15 Oct 2026)

- The existing company server is very old; it won't host the agent.
- **Trial and production: the office Mac Mini** (already purchased), ADR-002 Option D, Accepted. Setup: `docs/macmini-setup.md`. Joey as maintainer plus one named backup admin. Test MySys access from the Mac Mini first.
- *History:* the trial was first planned on an Anthropic cloud routine (14 Oct 2026, H2/H5 waived), and production was expected on a Sydney cloud VM. Both superseded by decision 3.
- Full comparison: `docs/hosting-research.md` (research as of 13–14 Oct). The drafted VM request for IT isn't needed.
- **ADR-002 proposed (14 Oct 2026):** `docs/specs/ADR-002-po-agent-hosting.md`. An Anthropic cloud routine running the script was not chosen for production (2.45): it fails the secrets gate, has no state between runs, and belongs to a personal account. Claude-driven options (routine with a browser tool, Cowork + Claude in Chrome) stay rejected under ADR-001 G2/G3. Estimated 3-year cost (hosting + Claude): IT VM about A$40–330; Sydney VM about A$610–1,010.

## Confirmed SOP (live)

1. Login as agent account → Project (top tab).
2. Note Pool → Assigned Pool = PO Allocation Pool, Locked/Unlocked = Locked.
3. Open note "[B1 Homes] Order XXXXXXXX/048".
4. Click Assign → assign note to the agent account (before downloading).
5. Download attached PO PDF; must contain "COMPACTION".
6. Email body contains internal number as file name, e.g. 2610001B_048 (always ends _048).
7. Projects (not Tasks) → search client internal number (e.g. 2610001B) → open pln → Create New Task.
8. Client > Creator = "Perth Scheduling".
9. Tick Compaction Test (right-hand list).
10. PO Number, e.g. 2610001B/048 (see "Answered questions" for sources).
11. Documents → upload the PO PDF.
12. Note = email body only → Submit.
13. Hold → Note "ON HOLD UNTIL CALL UP" → Hold.
14. Back on note: Link to Project → search pln → select.
15. **Solved** (the Note's Status buttons). *16 Oct 2026: the test site has no Resolve button, so the agent uses Solved (entry above). Check in 3B whether live has a Resolve button.*

- "Send Email Notification": leave unticked (it is ticked by default).

## Test-site differences (from note 235957 screenshot, 12 Oct 2026)

- Testing only: Joey plays B1 Homes and places the trial PO requests directly in the **Agent Pool** (not PO Allocation Pool). *16 Oct 2026: the trial POs are real B1 POs (entry above).*
- Note title = email body text, e.g. "Please find attached Purchase Order / Quotation file 2609034B_048_1.pdf" (no "[B1 Homes] Order …/048"). *16 Oct 2026: newer test Notes have the live-style title "[B1 Homes] Order 2609034B/048" with that text as the body; both styles are in the pool (`docs/screen-map.md` row 01).*
- Source shows "Agent 1 (MySys Only)" because Joey creates the notes (no sender email). Agent's user name in the Assign dropdown is "Agent 1 (MySys Only)".
- Everything else follows the live SOP.

## Answered questions

- PO number: from PDF "Purchase Order No", must agree with file name (_048 → /048) and, on live, the title. Disagreement → skip.
- B1 Homes check: PDF issuer "B1 Homes Pty Ltd" on both sites; on live `[B1 Homes]` title also required.
- Locked filter: applied on both sites.
- Backlog at go-live: read as "process existing /048 notes like new ones" — to confirm, incl. any age cut-off.
- The trial PDFs' addresses match their test projects (lot, street, suburb; the project adds a house number, postcode and state). *16 Oct 2026: the trial PDFs are real, not fake.*
- Architecture: approved by the CEO (decision 1, recorded 13 Oct 2026).
- Trial and production host: the office Mac Mini (CEO decision 3, 15 Oct 2026; replaces the cloud routine Joey chose for the trial on 14 Oct).

## Rules

- Address in PO PDF must match the project: lot number + street + suburb; ignore formatting, case, St/Street, missing postcode/state. Any of the three different or missing → skip.
- Skip → assign note back to the pool it came from. No exception report, apart from the approved alerts to Joey.
- Retry: "project not found" skips retried for up to 24 h; other skip reasons never retried. Agent keeps its own skip list. *(MVP: all skips final.)*
- Duplicate check: skip if the project already has a Compaction Test with the same PO number, except the agent's own recorded partial booking (resume it). *(MVP: always skip.)*
- Agent account cannot delete anything; it has all permissions the SOP needs. Never: Discard, Unlink, Cancel, Unassign, remove document, related-task checkboxes in Hold dialog.
- Agent only reads emails via MySys Notes; never deletes, replies, forwards; no Outlook access.
- Credentials never stored in docs or code.
- Config switch reader = deterministic-only must always work (Option A fallback). *(In the MVP.)*
- Any booking error → agent stops itself until the CEO approves a restart. *(MVP: exit 3 + alert; Joey unloads the launchd job.)*

## Schedule

- Hourly, weekdays 07:00–18:00 Perth time. On the Mac Mini: a launchd job at 7 minutes past each hour, 07:07–17:07 Monday–Friday, with the Mac's clock on Australia/Perth (7 minutes past, so a slow start never lands on the hour).

## Problem / volume

- 0–50 B1 Homes compaction POs per week, ~2 min each; pool must be checked every day.

## Success criteria (all four)

- Accuracy (hard line): no task on wrong project, wrong PO number or missing PDF.
- Coverage: ≥80% of /048 POs handled end to end; rest cleanly returned to pool.
- Speed: every /048 PO processed or returned within 1 hour (during run hours).
- Workload: admin only handles skipped POs.

## Trial

- Test site: https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component
- Live: https://prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component
- Before the trial: decision-seam tests on the full fixture set (3 trial PDFs + mutated copies); any false PROCEED blocks.
- Pass = 3 good trial POs (real B1 POs, 16 Oct 2026 entry) processed end to end, every step correct, no human help:
  - 2609017B → pln_66935
  - 2609034B → pln_66938
  - 2610002B → pln_66940
- Record Claude token cost per PO for the CEO.
- Go-live on real POs only after CEO reviews the trial results and signs off.

## Still open

- **CEO decision 2:** confirm Joey's "yes" (Claude may read real client data). Blocks go-live. (Decision 3 was made on 15 Oct 2026: the office Mac Mini.)
- Test-site checks before the first write: C1 and C3 answered on 16 Oct 2026 (entries above); MFA not seen, **password expiry still to confirm** with the MySys admin — `SPEC.md` open questions 1–3.
- CEO/IT OK on the private GitHub repo (the Mac Mini pulls the code from it).
- Backlog reading confirmation (and age cut-off).
- Alert channel for Joey for v1 (email or Teams webhook).

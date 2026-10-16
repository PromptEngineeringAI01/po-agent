# PO Agent

Books B1 Homes `/048` compaction POs in MySys (third-party, browser only): Note → Compaction Test task on the project, PO PDF attached, On Hold, Note linked and Solved. Hybrid (ADR-001): a deterministic Playwright script does every click through the action guard; a deterministic reader and Claude (no tools, schema-bound) both read; proceed only when both agree with each other and with MySys. Anything uncertain → skip → Note back to the pool.

**Now building: the MVP on the test site, run hourly by launchd on the office Mac Mini (CEO decision 3), with no state kept between runs. Active spec: `SPEC.md`.** Full v1 design: `docs/specs/spec.md`. Decisions: `docs/decisions.md` (wins over any spec).

## Commands

- Check (everything CI runs; created in M1): `uv run scripts/check.py` (healthy: ends with "check: all passed", exit 0)
- Install: `uv sync --locked`
- Live-Claude decision seam: `uv run pytest tests/seam1 -m live_claude` (healthy: "false PROCEED: 0")
- Run seam on the test site: `uv run pytest tests/seam2 -m testsite`
- Real-PO decision seam (laptop only): `uv run pytest tests/seam1 -m real_data`
- Screen mapping (Joey clicks, you observe): `playwright-cli open --headed "<test-site URL>"`, then only `playwright-cli snapshot`, `screenshot`, `find`, `generate-locator`
- Agent: `uv run po-agent spike --site test` (read-only) · `uv run po-agent run --site test [--decide-only] [--headed]` (see `SPEC.md` → Commands)

## Must never

1. Call click, fill, check, set_input_files, evaluate or dispatch_event anywhere except `src/po_agent/mysys/guard.py`. Claude (the reader) never clicks, types or navigates. With Playwright CLI you only observe: never a command that acts on the page (click, fill, type, press, hover, check, select, upload, drag, drop, eval, run-code, dialog, goto, reload), saves state or cookies, or lists network requests.
2. Press or target Discard, Unlink, Cancel, Undo Cancellation, Un-Hold, Change Project, Unassign, Remove, Delete, anything named "close" (the attached PDF's remove cell, Task Client's clear, window Close), the Note's Pending button, or any checkbox in the Hold dialog. Abandon a dialog by closing the browser context. Tests may call `guard.vet()` (no action code) on these controls to prove it refuses (decisions, 16 Oct 2026, D3).
3. Touch the live site (`prompt.mysys.com.au`) in code, config, tests or commands. The MVP is test site only. The one exception is the deny regex in `.claude/hooks/guard_bash.py` and its test, which must name the host to block it (decisions, 16 Oct 2026, D4).
4. Send, reply to, forward or delete email; access Outlook; leave "Send Email Notification" ticked.
5. Put a secret in code, config, docs, logs, screenshots, run output or a chat. Secrets come from `PO_AGENT_*` env vars or keyring at run time.
6. Commit or copy out anything from `private/` (real client data), `logs/`, `state/`, traces, or a codegen recording with credentials in it. Real data never goes into a committed file, PR, issue or run output, and isn't copied to the Mac Mini during the MVP. Only exception: the 3 trial POs are real; their internal numbers, PO numbers and test-site plns may appear in committed files and run output, and the Mac Mini reads them from the test site; a trial PDF is on the Mac Mini's disk only from its download until it's read into memory, a moment later, and leftovers are removed at the next run start (`SPEC.md` assumption 2, Trial conditions; decisions, 16 Oct 2026, D2). Their PDFs, addresses and client names never leave `private/` and MySys.
7. Start a write (Create New Task) before every check in scope (`SPEC.md` → In the MVP; `docs/specs/spec.md` §2 steps 2–4 and 6–11) has passed.
8. Edit a test, fixture or expected result to make it pass.
9. Push to `main`, force-push, or merge a PR. Joey merges.

## Done means

- `uv run scripts/check.py` passes, and you show its output before saying a task is done.
- Touched readers, prompt, model ID or address rules → ask me, then run the live-Claude seam; show `false PROCEED: 0`.
- Touched `mysys/` or the booker → run seam 2 on the test site (or ask me to run it); show the result.
- Review every diff against Must never, `SPEC.md` and `tasks/plan.md`. Important = would break behaviour, write a wrong value to MySys, leak data or break a Must-never rule. Style and naming are Nits; report at most five.
- Flag it when a change makes this file, `SPEC.md` or `docs/macmini-setup.md` out of date.

## TDD

- Write the failing test, run it, show it fails for the expected reason, then STOP for my review. After I approve, commit the test, then write code to make it pass.
- Test changes go in their own commit.

## Conventions

- Python 3.12, uv, ruff, pytest, pydantic, type hints. Only `src/po_agent/core/output.py` prints, and only the stdout contract in `SPEC.md` → Code style (no PDF text, addresses or Note bodies in run output).
- Real client data: you may read `private/` (real PDFs, live and test-site screenshots, captures) to understand the pages. Test-site captures count as real data, because the trial POs are real. Anything you write to a committed file (screen map, fixtures, tests, docs) uses fake or redacted values; seam-1 fixture PDFs are generated fakes, never a trial PDF.
- Secrets: env var `PO_AGENT_<NAME>` first, else keyring service `po-agent`; names `anthropic_api_key`, `mysys_test_username`, `mysys_test_password`. Never use the name `ANTHROPIC_API_KEY`, except in `tests/test_config_secrets.py`, which sets it to prove it's ignored (decisions, 16 Oct 2026, D4).
- Branch per task from up-to-date `main`; one task per session; Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- `.claude/settings.json` ships with permission rules (incl. the Playwright CLI deny list); M1 adds the hooks. From M1 on, files in `.claude/` are changed only by Joey, by hand.
- A behaviour change after `tasks/plan.md` is approved needs a dated entry in `docs/decisions.md`, plus `SPEC.md` and `tasks/plan.md`, in the same commit.

## Where things are

- Active spec: `SPEC.md`. Plan and task list: `tasks/plan.md`, `tasks/todo.md` (written by `/agent-skills:plan`).
- Full v1 spec pack: `docs/specs/` (mission, spec, tech-stack, roadmap, README glossary). ADRs: `docs/specs/ADR-NNN-<name>.md`.
- Intent: `docs/intent.md`. Decisions: `docs/decisions.md`. Build workflow: `docs/workflow.md`. Mac Mini setup: `docs/macmini-setup.md`. Demo and reset: `docs/demo-runbook.md`. Screen map: `docs/screen-map.md` (written in M0).
- Skills: Addy Osmani's agent-skills plugin (`/spec`, `/agent-skills:plan`, `/build`, `/test`, `/agent-skills:review`, `/code-simplify`, `/ship`; plain `/plan` and `/review` are Claude Code built-ins).

## Lessons

- (add one line here when Claude makes the same mistake twice)

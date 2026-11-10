<!-- How this file is written (sources: Anthropic "Steering Claude Code", HumanLayer "Writing a good CLAUDE.md", Factory AGENTS.md, Stanford CS146S):
- It loads in every session, so it holds only what nearly every task needs; keep it to ~60 lines of content (these comments are stripped before loading).
- Fewer instructions = better adherence to all of them; every line must earn its place.
- Pointers, not copies: details live in SPEC.md, docs/ and skills.
- Procedures go in skills, "every time" actions in hooks, "never" rules in hooks/permissions/guard, style in ruff.
- Stale lines are worse than none: update this file when a decision changes what it says. -->

<!-- WHY + WHAT: one paragraph on what the agent does and how, so Claude starts every session oriented. -->
# PO Agent

Books B1 Homes `/048` compaction POs in MySys (third-party, browser only): Note → Compaction Test task on the project, PO PDF attached, On Hold, Note linked and Solved. A deterministic Playwright script does every click through the action guard. Two code readers (pdfplumber, pypdf) must agree, and the PDF's address is checked against MySys. Anything uncertain → skip → Note back to the pool.

<!-- Current phase and where the source of truth is. Update when the phase changes (stale phase text misleads every session). -->
**Now:** production phase, test site only. Run mode books end to end, including from the office Mac Mini (launchd, hourly, no state between runs). What's left and its status: `tasks/todo.md`. Active spec: `SPEC.md`. Decisions: `docs/decisions.md` (wins over any spec).

<!-- HOW: only the commands most tasks need, each with what "healthy" looks like. The full list stays in SPEC.md (progressive disclosure). -->
## Commands

All commands, flags and Mac Mini runs: `SPEC.md` → Commands.

- Check (= CI): `uv run scripts/check.py` - healthy: last line "check: all passed", exit 0
- Install: `uv sync --locked`
- Seam 2 on the test site: `uv run pytest tests/seam2 -m testsite`
- Real-PO seam (laptop only): `uv run pytest tests/seam1 -m real_data`

<!-- Safety floor, near the top because it matters most. Deterministic controls (hooks, permissions, guard.py, check.py) do the enforcing; the text covers what they can't see. Each rule cites its decision as the "why". Removing or loosening one needs a docs/decisions.md entry. -->
## Must never

Hooks, permissions, `guard.py` and `check.py` enforce most of these; the rule still holds where they can't see.

1. Call click, fill, check, set_input_files, evaluate or dispatch_event outside `src/po_agent/mysys/guard.py`. With Playwright CLI only observe (`snapshot`, `screenshot`, `find`, `generate-locator`).
2. Press or target Discard, Unlink, Cancel, Undo Cancellation, Un-Hold, Change Project, Unassign, Remove, Delete, anything named "close", the Note's Pending button, or any Hold-dialog checkbox. Abandon a dialog by closing the browser context. Tests may call `guard.vet()` on them (decisions, 16 Oct 2026, D3).
3. Touch the live site (`prompt.mysys.com.au`) in code, config, tests or commands. Only exceptions: the `LIVE_HOST` constant in `src/po_agent/core/config.py`, `config/live.toml`, and the deny rules in `.claude/hooks/guard_bash.py` and `.playwright/cli.config.json` and their tests (decisions, 10 Nov 2026, hooks for the live profile). Never run the agent or the wrapper on live (`--site live`, `macmini-run.sh <mode> live`), log in to live from any test, command or seam, or read or set a live secret (`mysys_live_*`): only Joey does, on the Mac Mini.
4. Send, reply to, forward or delete email; access Outlook; leave "Send Email Notification" ticked.
5. Put a secret anywhere (code, config, docs, logs, screenshots, run output, chat). Secrets come from `PO_AGENT_<NAME>` env vars, else keyring service `po-agent`. Never use the name `ANTHROPIC_API_KEY` (except `tests/test_config_secrets.py`, which proves it's ignored).
6. Commit or copy out anything from `private/`, `logs/`, `state/`, traces, or a recording with credentials. Real client data never goes into a committed file, PR, issue or run output. Only exception: the 3 trial POs' internal numbers, PO numbers and test-site plns; their PDFs, addresses and client names stay in `private/` and MySys (`SPEC.md` assumption 2; decisions, 16 Oct 2026, D2).
7. Start a write (Create New Task) before every check in scope has passed (`SPEC.md` → In the MVP).
8. Edit a test, fixture or expected result to make it pass. An intended behaviour change may change one in its own `test:` commit, with its `docs/decisions.md` entry (decisions, 6 Nov 2026).
9. Push to `main`, force-push, or merge any way except `/verify-pr`. PRs touching the guard (`guard.py`, `scripts/guard_check.py`), hooks (`.claude/hooks/`, `.claude/settings*.json`) or CI (`.github/workflows/`) are Joey's to merge.

<!-- Verification as numbered, checkable steps: how Claude proves a change works before saying it's done. -->
## Done means

1. `uv run scripts/check.py` passes; show its output.
2. Touched the readers or address rules → run `uv run pytest tests/seam1 -s` and show `false PROCEED: 0`, then the real-PO seam on the laptop.
3. Touched `mysys/` or the booker → run seam 2 on the test site (or ask Joey to); show the result.
4. Review the diff against Must never, `SPEC.md` and `tasks/plan.md` at the depth its risk sets (`docs/workflow.md`, build loop steps 5-6). Important = breaks behaviour, writes a wrong value to MySys, leaks data or breaks a Must-never rule. At most five Nits.
5. Flag it when the change makes this file, `SPEC.md` or `docs/macmini-setup.md` out of date.

Do only what the task asks: no mutation probes, no second review round unless the fixes were large.

<!-- Team norms that apply to every task. Multi-step procedures (start a task, verify and merge a PR) live in skills, not here. Candidates to move to ruff/check.py: the print rule and the em-dash rule. -->
## How we work

- TDD: failing test first, show it fails for the expected reason, commit it as `test:` and carry on. Ask Joey only for a behaviour choice that is his, in plain words, with your recommendation.
- Branch per task from up-to-date `main`; Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- A change to what the agent does in MySys or prints, or one that loosens a safety control, needs a dated `docs/decisions.md` entry plus the `SPEC.md` lines it changes, in the same commit.
- `.claude/` is Joey's to change by hand, except `.claude/skills/` (not `skills/verify-pr/`).
- Python 3.12, uv, ruff, pytest, pydantic, type hints. Only `src/po_agent/core/output.py` prints (`SPEC.md` → Code style).
- You may read `private/` to understand pages; test-site captures count as real data. Committed files use fake or redacted values; seam-1 fixture PDFs are generated fakes.
- Use a plain dash "-", not the em dash. Never hand-edit `uv.lock` or other generated files.
- An unrelated failure you notice: report it, don't fix it in this task.
- Same mistake twice: propose a hook, test or skill change that prevents it; add a line here only if none fits.

<!-- Index (progressive disclosure, HumanLayer's agent_docs pattern): each line says when to read the doc, so Claude loads details only when a task needs them. The docs already exist; no separate agent_docs/ folder, so nothing is copied and goes stale. -->
## Read before you start

Read the docs that match your task before changing anything:

- Building, running, Mac Mini: `SPEC.md` → Commands; `docs/macmini-setup.md`
- Tests and seams: `SPEC.md` → Testing Strategy; `docs/workflow.md` (build loop, review depth)
- Code layout and conventions: `SPEC.md` → Project Structure, Code Style
- Architecture and why: `docs/specs/spec.md` (v1 design), `docs/intent.md`; ADR-001 still describes the Claude reader dropped on 2 Nov
- MySys screens, locators, guard targets: `docs/screen-map.md`; `SPEC.md` → MySys screen rules
- Safety and real data: `SPEC.md` → Boundaries, Trial conditions, Real client data
- Production and go-live: `SPEC.md` → Production; `docs/demo-runbook.md`; alerts on the Mac Mini: `docs/ops-runbook.md`
- What's decided: `docs/decisions.md` (newest first); current task: `tasks/plan.md`, `tasks/todo.md`
- Skills: `/start-task`, `/verify-pr`, and the agent-skills plugin (always the full name, e.g. `/agent-skills:build`; bare `/plan` and `/review` are built-ins).

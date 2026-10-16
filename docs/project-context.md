# PO Agent — project context (15 Oct 2026, spec approved)

One-page summary for anyone (or any Claude session) picking up the project. The repo is the source of truth; this is the map.

## What it is

An agent that books B1 Homes `/048` compaction POs in MySys exactly as the PO admin does: Note → Compaction Test task on the project with the PO PDF → On Hold ("ON HOLD UNTIL CALL UP") → link the Note → Resolve. Anything uncertain goes back to the pool for a person. First of 5–7 planned MySys automations. Owner and builder: Joey Wu. Decision owner: the CEO.

## Design (fixed)

Hybrid (ADR-001, accepted by the CEO as decision 1): a deterministic Playwright script does every click through an action guard; a deterministic reader and Claude (no tools, schema-bound) both read the PDF; it books only when both agree with each other and with MySys. Never Discard, Unlink, Cancel, Unassign, remove a document or touch the Hold dialog's related-task checkboxes. Email is read-only through MySys Notes.

## Where it stands

- **Stage:** MVP spec **approved** (`SPEC.md` v1.5, 15 Oct 2026). No code yet. Next: workflow Stages 0–2 (tools, repo, skills, Node.js + Playwright CLI), then M0 screen mapping, then `/plan`.
- **MVP:** test site only; the 3 trial POs 2609017B → pln_66935, 2609034B → pln_66938, 2610002B → pln_66940; run hourly on the **office Mac Mini** by a launchd job as a standard user, secrets in its Keychain (ADR-002 Option D, Accepted); **no state between runs**.
- **Real client data:** the agent may read it (Joey, 14 Oct 2026; CEO to confirm as decision 2). It stays in the git-ignored `private/` folder on Joey's laptop; never in GitHub or on the Mac Mini during the MVP. Bookings stay on the test site.
- **Demos:** repeatable as often as needed (at least 3); a 10-minute reset between demos (`docs/demo-runbook.md`).
- **Production host:** the same office Mac Mini (CEO decision 3, 15 Oct 2026).

## How it's built

- **Workflow:** `docs/workflow.md` v5.1. Addy Osmani's agent-skills (`/spec` → `/plan` → `/build` → `/test` → `/review` → `/ship`) in Claude Code in VS Code; one task per branch and session; Joey merges.
- **Screen mapping:** Playwright CLI, observe-only (Joey clicks; Claude snapshots).
- **After the MVP:** Matt Pocock's `improve-codebase-architecture` to shape the shared MySys package before automation #2.
- **Slices:** M0 map screens → M1 skeleton + Mac Mini spike → M2 decision seam (incl. real POs on the laptop) → M3 decide-only → M4 first bookings → M5 safety → M6 demo for the CEO.

## Open items

- Test site (M0): C1 (Hold checkboxes pre-ticked?), C3 (return a Note via Assign?), MFA/password expiry, how a cancelled task shows, does opening a Note change it.
- Answered: Joey's own account can cancel tasks on the test site (that's the reset); Joey is on a Pro plan; Node.js can be installed; the GitHub CLI is already installed (portable zip) and logged in as PromptEngineeringAI01 with `repo` and `workflow` scopes.
- CEO: confirm decision 2; OK for the private GitHub repo.
- Does MySys accept logins from the office Mac Mini (answered by a login by hand from it, then the M1 spike)?

## Files

`SPEC.md` (active MVP spec) · `CLAUDE.md` (rules) · `docs/workflow.md` (runbook) · `docs/macmini-setup.md` · `docs/demo-runbook.md` · `docs/decisions.md` (wins over any spec) · `docs/intent.md` · `docs/specs/` (v1 spec pack, ADR-001, ADR-002) · `docs/hosting-research.md`.

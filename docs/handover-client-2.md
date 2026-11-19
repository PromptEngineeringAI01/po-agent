# Handover - B1 Homes live, next: 8.1, 8.3, 8.4, then client 2

Written 19 Nov 2026 by the post-audit advisor, for the next advisor session. Read this first, then `docs/specs/ADR-003-more-clients.md`. `docs/decisions.md` wins over this file where they differ.

## Where things stand

- **Live:** the office Mac Mini books B1 Homes `/048` POs on live every weekday hour, 07:07-17:07 Perth, at most 10 Notes a run (`config/live.toml`). Only Joey runs or changes anything on live or the Mac Mini.
- **Code on the Mac Mini:** the `production` tag, which only Joey moves (`docs/macmini-setup.md` section 8). On 19 Nov 2026 Joey moved it from `9d0f0cb` (PR 112) to `e1b1c4f` (PR 122, the Healthchecks.io ping; no `src/` change between them); the 15:07 run on 19 Nov was the first on it, exit 0. Check the `wrapper: running production <commit>` line in `runs.log`, or ask Joey.
- **Done:** go-live G.1-G.8 and P6 (`tasks/todo.md`), the CMU 17-313 audit PRs 114-119 and 121, the Healthchecks.io ping (PR 122), the outage docs and the G.8 tick.
- **Open on GitHub:** issue 71 (the heartbeat issue, kept open by design). No open alert issue.

## The 18-19 Nov outage (cause and fix)

- A macOS update restarted the Mac Mini. The admin account stayed logged in afterwards and the screen lock logged `poagent` out, so its LaunchAgent and Keychain were gone: no scheduled run from 17 Nov 17:07 to 19 Nov 11:07 (about 15 working hours). No bookable Note was missed; they waited in the pool.
- Fix: restart, log in as `poagent` only, lock the screen. The runs at 12:07, 13:07 and 14:07 on 19 Nov ran on their own; issue 120 closed.
- Rule: only `poagent` stays logged in; an admin logs out before leaving the Mac; after any restart or macOS update, unlock as `poagent` and lock the screen. Written up in `docs/decisions.md` (19 Nov 2026, Mac Mini outage), `docs/macmini-setup.md` sections 5 and 10, and `docs/ops-runbook.md` ("`poagent` logged out, or an admin session left on").
- Not known yet: why the update installed during run hours although section 5 turns automatic installs off. Joey checks those settings at the next update.

## Alerts

- **Healthchecks.io** (decisions, 19 Nov 2026): every run pings check `po-agent b1-homes` at its end; a missed run emails Joey within about an hour. Status on 19 Nov: the tag is on the ping code (H.1 in `tasks/todo.md`); creating the check and storing its URL in `poagent`'s Keychain are Joey's steps, not yet confirmed to the advisor when this was written. The first ping was due from the 16:07 run (the run after the one that checks out the new wrapper). Healthy when the check shows **up** and `runs.log` has no `wrapper: healthchecks ping` line; if it still shows **new**, see `docs/ops-runbook.md`, the two `wrapper: healthchecks ping` lines.
- **GitHub heartbeat, kept as a backup:** each run rewrites issue 71, and `.github/workflows/heartbeat.yml` opens `po-agent heartbeat missed` after 2 hours of the schedule with no run. GitHub fires it only about once a weekday afternoon (decisions, 18 Nov 2026) and disables it after 60 days without repo activity. Dropping it is Joey's later choice, once Healthchecks.io has proved itself.
- Failed runs open a `po-agent alert` issue (`docs/ops-runbook.md` section 4).

## Two Notes the agent can't book

Two live Notes (their IDs are in `runs.log` on the Mac Mini, never in the repo: it is public, audit N4) pass the list-level checks but come out `PROJECT_NOT_FOUND` every hour: no MySys project matches their internal number. The agent skips them each run and leaves them in the pool, which is correct. Joey decides whether the admin books them by hand (`docs/ops-runbook.md` 3.6) or the project gets created first. No code change unless more Notes start failing the same way.

## Next: 8.1, then 8.3, then 8.4

The code freeze ended with G.8. Do them one at a time, each with `/start-task <N>`, each PR verified with `/verify-pr`. None touches the guard, hooks or CI, so the advisor merges them; after each merge Joey moves the `production` tag and watches one live run.

| Task | What | Risk | Done when |
|---|---|---|---|
| **8.1** | One Send Email Notification control for every Note-window write; W4 and W5 failures also leave an `ok=false` trace record (`docs/architecture-review.md` Round 2, candidate D, its settled design) | Medium | check, seam 2 on the test site (take, return, W4, W5), `docs/decisions.md` and SPEC's Safe trace line |
| **8.3** | The two readers as one module; `decide()` gets the PDF once and calls the project lookup itself (candidate A, with round 1's proposal 6) | Medium (seam 1) | check, `false PROCEED: 0`, the real-PO seam on the laptop |
| **8.4** | One MySys wait module; its retry refuses committing clicks (candidate C) | Medium | check, seam 2 on the test site |

All three are refactor tasks, so each brief carries the Refactor tasks rule (PR 114; `CLAUDE.md`, "Do only what the task asks"): before changing code, hand-write a few deliberately wrong versions and check the tests catch each; add tests first for any they miss.

**Open question B, decided in 8.1's decision batch.** 8.1 and 8.4 run seam 2 on the **test site** from the laptop. The "one agent at a time" rule (`tasks/todo.md` header) was written when the Mac Mini ran the test site; it now runs **live**, with a different site, account and secrets. Recommendation: don't unload the live job for a laptop test-site run. Record Joey's answer in `docs/decisions.md` and update the todo header line in the same PR.

## Client 2: Joey's prep (no code; can run alongside 8.x)

1. CEO approval for the agent to read this client's data (as decision 2 was for B1).
2. A few real Notes and their PDFs saved on the laptop in `private/` (never committed).
3. Can its Notes be told apart in the Note Pool **list**, without opening them (sender, title words, a pool)? If not, ADR-003 decision 4 needs Joey's and the CEO's decision before any design.
4. Which Create New Task fields differ from B1 (Creator, task type, the Hold and Solved steps).

## Rules for client 2 (ADR-003)

- One agent with one shared guard and booker. `mysys/` stays shared and client-free; values that differ come in through the `Proceed`.
- One rules package per client (`src/po_agent/<client>/`, like `b1/`), behind one small interface extracted from B1 and client 2 together.
- No multi-client code until client 2's real Notes and PDFs are in `private/` and its screens are mapped.
- PDF-based eligibility needs a read-only peek (open, download, decide, close, no assign), with its own decision and SPEC rule.
- How to start: `/agent-skills:spec` for client 2's SPEC slice, map its screens (Joey clicks, Claude only observes), then `/agent-skills:plan`. Joey updates `CLAUDE.md` (first line, Must never #6), `SPEC.md` and `docs/workflow.md` when client 2 starts (ADR-003, Consequences).

## Still open

- **A second reviewer from another model** (audit-eli5 session, 19 Nov): Codex/ChatGPT as a second reviewer on medium and high risk PRs, next to the Claude `pr-reviewer`. Recommended: Codex review on the GitHub PR (an `@codex review` comment) that `/verify-pr` reads; advisory only, no write access, never given `private/`, logs, traces or secrets. Joey hasn't chosen. If yes, he links ChatGPT to the repo and applies a `/verify-pr` patch by hand (`.claude/skills/verify-pr/` is his).
- **Healthchecks.io vs the GitHub heartbeat:** keep both until Healthchecks.io has run a few weeks, then Joey decides.

## First step for the next advisor

Confirm with Joey that the latest live runs are healthy (issue 71's `last run:` and the Healthchecks.io check), then `/start-task 8.1`.

# PO Agent

Automates the PO admin's B1 Homes `/048` compaction pre-bookings in MySys. First of 5–7 planned MySys automations.

**Current stage:** MVP spec **approved** (`SPEC.md` v1.6, 15 Oct 2026). No code yet. The MVP runs on the MySys **test site** from the office Mac Mini; production runs on the same Mac Mini (CEO decision 3, 15 Oct 2026).

## Start here (Windows, VS Code)

1. Unzip this folder **outside OneDrive**, e.g. `C:\Users\<you>\code\po-agent`.
2. Open it: `code C:\Users\<you>\code\po-agent`, then **Terminal → New Terminal**.
3. Follow `docs/workflow.md` Stages 0–2: tools, git + private GitHub repo, and Addy Osmani's agent-skills plugin (the skills plan is at the top of the workflow). If VS Code offers the recommended extensions, accept.
4. Map the screens (workflow Stage 3): on the test site you click through the SOP (full SOP for 2609017B; read-only screens for 2609034B and 2610002B) while Claude Code takes Playwright CLI snapshots and screenshots; reset the test site; then view-only captures of live and the 3 most recent real PO PDFs (10–20 before go-live). Everything goes into `private/` first.
5. Check `SPEC.md` against the screen map (workflow Stage 4.1, done), then `/agent-skills:plan` (Stage 4.2).

## What's where

| File | What it is |
|---|---|
| `SPEC.md` | **Active spec:** the MVP on the office Mac Mini |
| `CLAUDE.md` | Rules Claude Code reads every session |
| `docs/workflow.md` | Step-by-step build runbook (Addy Osmani's agent-skills) |
| `docs/macmini-setup.md` | How to set up the Mac Mini: agent user, power, clock, updates, secrets, launchd job |
| `docs/demo-runbook.md` | How to reset the test site and demo the agent again (as often as you like) |
| `docs/screen-map/` | Committed fake material only (test-site screenshots show the real trial POs, so they stay in `private/`) |
| `.playwright/cli.config.json` | Playwright CLI settings for screen mapping (live site blocked) |
| `private/` (you create it) | **Real client data, laptop only, git-ignored:** live screenshots, real PO PDFs, `cases.toml` |
| `tests/seam1/fixtures/pdfs/` | Where the 3 generated fake PO PDFs go (never the trial PDFs: they're real) |
| `docs/project-context.md` | One-page summary: what, where it stands, open items |
| `docs/intent.md` | What the business wants and why |
| `docs/decisions.md` | Decision log (wins over every spec) |
| `docs/hosting-research.md` | Hosting options and costs |
| `docs/specs/` | Full v1 spec pack: README (glossary), mission, spec, tech-stack, roadmap, ADR-001 (architecture), ADR-002 (hosting) |

No real client data and no credentials ever go in this repo. The agent may read real data (Joey, 14 Oct 2026; CEO to confirm), but it stays in `private/` on your laptop.

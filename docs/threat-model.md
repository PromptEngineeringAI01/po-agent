# Threat model - PO Agent (lightweight STRIDE)

**Version:** 1 · 20 Nov 2026 · **Owner:** Joey Wu · **Method:** the 15-minute STRIDE pass (one question per letter, per trust boundary), recorded as threat, existing control, gap, owner. Every control below exists today; each gap names a candidate task only, nothing is built here. Sources: `SPEC.md` (Boundaries, Trial conditions, Production), `docs/specs/spec.md` (Areas of Concern), `docs/ops-runbook.md`, `docs/architecture-review.md`, `docs/decisions.md`.

**Assets:** the integrity of what is written to MySys (accuracy is the hard line); real client data (PO PDFs, addresses, Note text); the agent account's MySys credentials and the Mac Mini's GitHub token; the Mac Mini's ability to keep running hourly.

**Attacker model:** an outside sender of a Note or PDF (the Note pool is fed by email); a changed or broken MySys screen; a mistake by Joey, a backup admin or a Claude session; a compromised dependency or CI action. Out of scope: MySys's own security, macOS and FileVault, GitHub's.

## Boundary 1 - PO PDF and Note text from MySys (untrusted input)

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| S: anyone can email a `[B1 Homes] Order .../048` Note with a PDF | Title rule, two code readers that must agree (`src/po_agent/b1/reader_rules.py`), address checked against MySys (`b1/address.py`), duplicate check, task goes On Hold; any doubt skips (`b1/decision.py`) | The sender is not checked (spec C6: the live sender check was deferred to v1 and is not built, SPEC.md Deferred table); damage is bounded by the other checks | Joey | Decide whether the sender-domain check (C6) is still wanted; if yes, a live-only check |
| T: PDF or Note changes between read and write | PDF read in memory, read-back after every write (W2-W5), `ACCURACY_BREACH` stops the run (exit 3) | None found | - | - |
| R: what the agent decided for a Note | `NOTE` lines, safe trace of allowlisted fields only, 90 days (`core/trace.py`, `core/runlog.py`) | None found | - | - |
| I: PDF text or address reaches a log, issue or the public repo | Stdout contract (no PO content beyond PO number and pln, `core/output.py`), trace has closed types, alert issues drop `note_id` (`scripts/macmini-run.sh`), PDF on disk only from download to read (D2), no outside service (no AI reader, decisions 2 Nov 2026) | A parser crash message could quote PDF text; the wrapper sends stderr to `/dev/null`, so it is covered only on the Mac Mini | Joey | Optional: a test that error strings from the readers carry no PDF text |
| D: one bad Note blocks every later run | Newest first plus run cap so old unbookable Notes do not starve new ones (decisions, 10 Nov 2026); skips return the Note via Assign | **Stale-Note stop (verified):** after `PARTIAL_WRITE` or `ACCURACY_BREACH` the Note stays assigned to the agent, so `controls.stale_note_stop` and the My Notes read stop every later run with `UNEXPECTED_SCREEN` until a person finishes it (`core/controls.py`, runbook section 4). This is deliberate (fail closed) but one stuck Note halts all booking and alerts hourly. Also `MORE_PAGES` stops every run once Pending Notes pass one page | Joey / backup admin | Task: time-to-resolve target plus a single de-duplicated alert for a stale Note; consider alerting once, not hourly |
| E: PDF or Note text makes the agent click something | Readings never choose what to click (decisions, 2 Nov 2026); all clicks via the guard | None found | - | - |

## Boundary 2 - MySys (test site, browser) and the guard

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| S: a look-alike or wrong host | `base_url` must be https on exactly the profile's own host (`core/config.py`); Playwright CLI allowlist `.playwright/cli.config.json` | None found | - | - |
| T: a screen changes, or a write lands on the wrong object | Fixed order, every check before Create New Task, read-back after each write, assignee check, Send Email unticked and read back (`mysys/booking.py`, `core/controls.py`) | None found | - | - |
| R: who did what in MySys | Agent has its own account so the Note log names it; trace and `RUN_SUMMARY` | Trace is on the Mac Mini only, 90 days | Joey | None needed now |
| I: screenshots or traces hold client data | `run` never saves snapshots, test-site captures count as real data and stay in `private/` (SPEC Real client data) | None found | - | - |
| D: MySys down or slow | 20-minute kill, next hourly run retries, `LOGIN_FAILED` and heartbeat alerts | None found | - | - |
| E: the script presses a forbidden control | `mysys/guard.py` allowlist plus denylist (Discard, Unlink, Cancel, Unassign, ...), `scripts/guard_check.py` in the check, `GUARD_REFUSAL` alert; guard PRs are Joey's to merge | The agent account may still hold Discard, Unlink, Cancel and Unassign rights in MySys (spec C9 "still to ask"; no later record found, so confirm with the MySys admin); the guard is the only barrier | Joey | Ask the MySys admin to remove those rights from the agent account |

## Boundary 3 - Secrets store (`PO_AGENT_*` env vars, keyring)

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| S/T: wrong or swapped credentials | Each site has its own named pair (`core/secrets.py`); only `PO_AGENT_<NAME>` is read, `ANTHROPIC_API_KEY` is ignored | **Live-profile secrets are checked only in production (verified):** every test reads test names or env vars; the live names are first read by the real run on the Mac Mini, so a missing or stale live item shows up as `CONFIG` or `LOGIN_FAILED` at run time. Claude may not read or set them (CLAUDE.md #3) | Joey | Task: a read-only `po-agent check-secrets --site live` the wrapper runs, printing only present or absent, never values |
| R: access to a secret | None beyond the Keychain's own prompt | Not tracked; acceptable for one operator | Joey | - |
| I: a secret reaches a log, repo or chat | Values never logged or put in errors; gitleaks in pre-commit and CI (`.github/workflows/check.yml`); Healthchecks URL goes to curl on stdin (`scripts/macmini-run.sh`) | None found | - | - |
| D: Keychain locked or `poagent` logged out | Runbook entries, heartbeat and Healthchecks alerts (19 Nov outage, decisions 19 Nov 2026) | Detection takes about an hour (Healthchecks) to a weekday afternoon (GitHub check); a night or weekend gap is not alerted | Joey | Accepted in the 18-19 Nov decisions; revisit if a gap costs a PO |
| E: other tools read the agent's Keychain items | `poagent` is a standard account, no AI tool on it (Trial conditions, H2) | The waiver for Claude on `poagent` (6 Nov 2026) was meant to end before go-live; confirm it is removed (todo G.4 says it was) | Joey | One-line check in the next ops review |

## Boundary 4 - Mac Mini launchd run and `scripts/macmini-run.sh`

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| S: code that is not Joey's runs | The Mac Mini runs the `production` tag only Joey moves, `uv sync --locked`, never falls back to code on disk (`scripts/macmini-run.sh`) | None found | - | - |
| T: a hand edit or a second process changes state | `git checkout` fails on edited files; runs keep no state | **No run lock (verified):** the wrapper has no lock file (the "single-run lock" was deferred to v1, decisions, 16 Oct 2026). launchd does not start a second instance of the same job, but a manual `launchctl kickstart`, the laptop (SPEC: "one agent at a time") or a second job can overlap, all as the same agent account. The only lock is the laptop's seam-2 test-site lock (decisions, 20 Nov 2026), which does not cover the Mac Mini or `run` | Joey | Task: a `flock`-style lock on the Mac Mini wrapper (macOS has no `flock`: use `mkdir` lock with stale-PID check) |
| R: what a run did | `runs.log`, `RUN_SUMMARY`, trace | Logs are local to the Mac Mini | Joey | - |
| I: PDF left on disk | D2 cleanup at run start, `CONFIG` alert if it cannot be removed; FileVault | None found | - | - |
| D: a hung run or an unattended stop | 1200 s kill, process-group kill, Healthchecks plus GitHub heartbeat, kill switch read from `origin/main` | Single machine, single operator plus one backup admin | Joey | - |
| E: the job does more than its rule | Standard account, `enabled` kill switch, run cap, Perth window (`core/controls.py`) | None found | - | - |

## Boundary 5 - GitHub CI, `.claude/hooks` and the alert channels

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| S: a fake alert or heartbeat | Issues are opened by the Mac Mini's repo-scoped token and `GITHUB_TOKEN` (`.github/workflows/heartbeat.yml`) | Anyone who can open an issue on a public repo can add a `po-agent-alert` look-alike or edit the heartbeat issue if given triage rights; no signature on a ping | Joey | Low risk: limit who has triage; keep the Healthchecks ping as the independent signal |
| T: a hook, setting or workflow weakened | `protect_paths.py` blocks `.claude/**`; PRs touching guard, hooks, settings or CI are Joey's to merge (CLAUDE.md #9); workflow permissions are minimal and actions are pinned by SHA (`check.yml`) | The GitHub token on the Mac Mini lasts 90 days; expiry silently stops alerts and the heartbeat (runbook `git fetch` row) | Joey | Calendar reminder or a check that warns before expiry |
| R: who merged what | Merge commits via `/verify-pr` with `--match-head-commit`; `docs/decisions.md` | None found | - | - |
| I: an alert, issue or PR leaks client data | Issue bodies carry only `ALERT` lines without `note_id`; runbook bans addresses, client names, live Note IDs and plns in issues; repo-data check in pre-commit and CI blocks `private/` and PDFs | A person pasting live data into an issue by mistake is stopped by policy only | Joey | - |
| D: the alert path is down | Two independent heartbeats (GitHub check, Healthchecks.io); `wrapper: alert issue not opened` is logged | GitHub scheduled workflows are best effort and disabled after 60 days without repo activity (decisions, 19 Nov 2026); Healthchecks.io is a third-party service | Joey | Keep Healthchecks as primary; accept |
| E: a Claude session does more than allowed | `guard_bash.py` (no push to `main`, no live host, no live secrets, pinned merge only), `protect_paths.py`, permission rules | The hooks see only Bash and file edits, not the browser pane (decisions, 10 Nov 2026); that is covered by the SPEC live-lookup limits and by Joey being the one who logs in | Joey | - |

## Boundary 6 - The public repo (data leakage)

| STRIDE | Existing control | Gap | Owner | Follow-up (candidate) |
|---|---|---|---|---|
| I: client data or secrets committed | `.gitignore` for `private/`, `logs/`, `state/`; gitleaks and repo-data check in pre-commit and CI; fixtures and `docs/screen-map.md` are fake or redacted; only the 3 trial POs' identifiers are allowed | The history is public forever: anything that slipped in earlier cannot be unpublished by a later commit | Joey | One-off history scan (gitleaks over all refs) and record the result |
| I: the live host named outside the allowed places | `LIVE_HOST`, `config/live.toml`, deny rules only; `guard_bash.py` blocks it in commands | This doc and the runbooks describe live behaviour in general terms only | - | - |
| T: a dependency or action changes under us | `uv.lock` with `--locked`, actions pinned by SHA | No automated advisory scan of dependencies | Joey | Task: `pip-audit` or Dependabot alerts (needs Joey's go-ahead for a new dependency) |

## Design gap that crosses boundaries

- **Client leaks across `core/` and `mysys/` (verified):** `core/` imports `b1` and `mysys` (`core/run.py`, `core/controls.py`, `core/demo.py`), while `mysys/` imports `b1` and `core` (`mysys/driver.py`, `mysys/booking.py`), so the layers form a cycle and B1 rules (`reader_rules`, `decision`) are reachable from the reusable MySys code. It does not create a security hole today, but it weakens the "one gate module" argument if a second client is added (`docs/architecture-review.md` section 9, `docs/handover-client-2.md`). Owner: Joey. Follow-up: fix when client 2 becomes real, as the architecture review's trigger says, not before.

## Summary of real gaps (for triage)

1. Stale-Note stop halts all runs until a person acts, with hourly repeat alerts (D).
2. No run lock on the Mac Mini wrapper; "one agent at a time" is a rule, not a control (T).
3. Live secrets are exercised only in production; no safe pre-flight (S/T).
4. Sender of a Note is not verified (C6 deferred) and the agent account may still hold forbidden MySys rights (C9) (S, E).
5. Alert and heartbeat have known weak spots: token expiry, GitHub schedule limits, no night or weekend alert (D).
6. `core/` and `mysys/` form an import cycle that leaks B1 rules into reusable code (E, design).
7. Public history is not scanned beyond CI's per-commit check; no dependency advisory scan (I, T).

Re-run this pass when a boundary changes: a new client, a new alert channel, a new secret, or a second machine.

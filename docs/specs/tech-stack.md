# Tech Stack — PO Agent

**Status:** Approved for build · v1.3, 15 Oct 2026 (1.3: CEO decision 3, the trial and production run on the office Mac Mini: launchd, the agent user's Keychain via keyring, state on its disk in v1; the cloud routine and the Sydney VM dropped. 1.2: trial host is an Anthropic cloud routine; secrets read from `PO_AGENT_*` env vars first; no state between runs on the trial routine; production most likely a Sydney cloud VM, not decided) · **Author:** Joey Wu, drafted with Claude
**Fixed by decision (ADR-001, approved by the CEO through the CEO decision brief, decision 1, recorded 13 Oct 2026):**

- hybrid architecture: a deterministic Playwright script does every click; a deterministic reader (pdfplumber + patterns + address normaliser/verifier) and Claude (no tools, schema-bound JSON) both read
- browser/UI only, with no MySys API or internal requests
- a deterministic-only reader mode reachable through config (in the MVP; until the rules-only address reader is built, it returns every PO to the admin).

Everything else is a recommendation. The reason is given for each, so the engineer can weigh a change. The MVP (`SPEC.md`) uses this stack unchanged.

## Recommended stack

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| Language | **Python 3.12+** | Team familiarity; strong PDF and browser libraries; fits Claude Code in VS Code; runs the same on Windows (laptop) and macOS (Mac Mini) with uv. | TypeScript (Playwright's home language); fine, but less familiar to the owner. |
| Browser automation | **Playwright for Python**, Chromium; headless on the Mac Mini, headed while developing | Auto-waits; selectors by accessible role and name; tracing and screenshots for debugging; Windows and macOS. | Selenium (weaker waits); Claude computer-use (**rejected by ADR-001**: fails gates G2/G3). |
| PDF text (deterministic) | **pdfplumber** (text layer only) | Gives the non-AI reading of issuer, "COMPACTION", PO number and internal number, and the text the address verifier searches. | OCR: **not used**. Image-only PDFs are skipped. |
| AI reader | **Claude through the Anthropic API**, official Python SDK. PDF sent as a document input with the Note text. Answer forced into the reading schema using the API's structured-output feature. **No tools defined.** | Reads layout-heavy PDFs well; schema-bound output can be validated by code; the model has nothing it can act on. | Regex only = Option A (kept as the fallback mode); a local model (more to run and maintain). |
| Model | **Pinned exact model ID in config.** Start with a mid-size (Sonnet-class) model. | Pinning stops silent behaviour changes. Any model change requires rerunning the decision-seam tests. | A smaller (Haiku-class) model to cut cost, but only after it passes the decision-seam tests. |
| Output validation | **pydantic** models for the reading schema, the log line and config | Rejects malformed or missing fields before they reach the decision engine. | Hand-written checks. |
| State | **Plain files in a state directory:** a skip-list JSON file (written atomically), daily JSON-lines log files, and a `STOP` file used as the kill switch. **MVP: no state at all** (Joey, 14 Oct 2026): MySys is the state; the Mac Mini keeps only a short run log for Joey; the skip list, logs and `STOP` arrive with v1 in `state_dir` on the Mac Mini's disk. | The only state the rules need is the skip list. The volume is tiny (about 5 MB of logs a year). | SQLite (more than this needs); a git state branch or external store for the routine (considered for the trial, not chosen). |
| Configuration | One **TOML profile per site** (`test`, later `live`). **No secrets.** | Same code on test and live; the differences in the intent's trial table are data. | Environment variables only (harder to review). |
| Secrets | Read at run time by one module: **environment variable `PO_AGENT_<NAME>` first, else `keyring`**: Windows Credential Manager on the laptop; on the Mac Mini, the agent user `poagent`'s login Keychain (no `PO_AGENT_*` variables there; env vars are for CI and tests) | One code path for every host. The Keychain is unlocked only while `poagent` is logged in, which is why the job is a LaunchAgent in that session. Never named `ANTHROPIC_API_KEY`, so Claude Code can't pick it up. | `.env` file in the repo folder: **not acceptable** (credentials next to the code). |
| Scheduling | **launchd on the Mac Mini** (trial and production): a LaunchAgent at 7 minutes past each hour, 07:07–17:07 Monday–Friday, Mac clock on Australia/Perth; it runs `scripts/macmini-run.sh` (pull `main`, sync, run, log, alert). The agent **also** checks the Perth window itself | Simple and observable. The self-check protects against a wrongly set trigger. | A long-running service (more ways to fail). |
| Time zone | `zoneinfo`, **Australia/Perth** (UTC+8, no daylight saving) | The schedule is defined in Perth time. | — |
| Logging | One JSON line per Note plus one summary line per run, in a daily file; deleted after 90 days; Playwright screenshot/trace **only on failure**. **Run output (stdout) is a short fixed contract** with no PDF text or addresses (`SPEC.md` → Code style) | Enough to explain any booking and to total coverage and cost for the CEO. The Mac Mini's run log and alert issues are built from stdout, so untrusted PDF text must never reach it. | Plain-text logs (hard to total); a database (more than needed). |
| Tests | **pytest** for seam 1 (decision seam, offline; stubbed and live-Claude modes); **pytest + Playwright** for seam 2 (run seam on the test site) | Matches the two agreed seams. | — |
| Tooling | git, **GitHub** (private repo; the Mac Mini pulls `main` from it and opens alert issues), **uv** (locked dependencies), **ruff**, **gitleaks**, Claude Code in VS Code with **Addy Osmani's agent-skills**; **Playwright CLI** (`@playwright/cli`, Node.js) for mapping MySys screens, observe-only (Joey clicks) | Repeatable installs; pinned versions reduce supply-chain risk; one gated build flow. | pip + requirements.txt pinned with hashes (acceptable). |

## Component map

```
 Scheduler: launchd on the office Mac Mini                    Secrets: PO_AGENT_* env vars | keyring (Keychain)
        │                                                     │ MySys login, API key
        ▼                                                     ▼
 ┌──────────────── Run controller (deterministic) ──────────────────────┐
 │ kill switch · Perth window · run time cap · env guard · profile      │
 │                                                                      │
 │  MySys driver (Playwright)          Decision engine  ◄── seam 1      │
 │   └ Action guard: allowlist +  ◄──►  ├ Deterministic reader/verifier │
 │     denylist; read-back              ├ Claude reader (no tools)      │
 │                                      └ rules → PROCEED | SKIP        │
 │  Booker (W1–W5 with read-back)                                       │
 │  State: skip list · daily log · STOP  (Mac Mini disk; none in MVP)   │
 └──────────────────────────────────────────────────────────────────────┘
        │ browser only  ◄── seam 2                │ HTTPS: PDF + Note text only
        ▼                                         ▼
   MySys (test | live)                      Anthropic API
```

## Security baseline

These come from the intent, the ADR gates and the engineering security-review checklist (secrets, injection, authorisation).

- **Secrets:** loaded at run time only. Never logged, printed or screenshotted, and never in the repo or config. No browser session state saved to disk. Fresh login each run.
- **Least privilege:** the agent account can't delete. Ask the MySys admin to also remove Discard, Unlink, Cancel and Unassign rights if possible (spec concern C9). Give the Anthropic API key a monthly spend limit, use it only for this agent, and rotate it if exposed (and at the end of the trial).
- **Untrusted input:** PDF and Note text are data. Claude has no tools; its output is schema-validated; every value written is confirmed by the deterministic side and MySys. The email body written to the task comes from the deterministic reader and is typed as plain text. PDF text never appears in run output.
- **Code-enforced guard:** only the action guard may call click/fill/check/upload/evaluate. A build check enforces this.
- **Network:** the host needs outbound HTTPS to the MySys sites and `api.anthropic.com`, plus the alert channel. During setup and updates it also needs PyPI, GitHub and Playwright's browser download. No inbound access is needed (Remote Login for the two admins is optional).
- **Data at rest:** logs (addresses, PO details) stay on the Mac Mini's FileVault-encrypted disk (trial: no daily log files; `runs.log` holds the short run output: the trial POs' PO numbers and test plns only) and are deleted after `log_retention_days` (default 90, to be confirmed). PDFs aren't kept.
- **Dependencies:** a locked dependency file; update on purpose and rerun both seams after any update.
- **Host:** the Mac Mini runs the agent as a standard user with no AI tools installed; FileVault on; macOS updates installed by hand outside run hours (`docs/macmini-setup.md`). No trial exception is needed (the earlier cloud-routine waiver is withdrawn; `SPEC.md` → Trial conditions).

## Hosting (CEO decision 3, 15 Oct 2026: the office Mac Mini)

| Option | Fits | Watch-outs |
|---|---|---|
| L. Joey's laptop | Development; manual seam 2 runs | Sleeps and travels; one person. **Not for production.** |
| **D. The office Mac Mini** (ADR-002 Option D, Accepted) | **Trial and production (CEO decision 3, 15 Oct 2026)**; already purchased | Office power/internet outages stop runs; after an unplanned restart someone logs in as `poagent` (FileVault); Joey patches macOS outside run hours; must be physically secure. Setup: `docs/macmini-setup.md`. |
| C. Anthropic cloud routine running the script (ADR-002 Option C) | Planned for the trial on 14 Oct; superseded by D | Secrets readable by the session (fails H2); personal account. **Never for live.** |
| A. VM provided by IT (ADR-002 Option A) | Not chosen (ranked first in ADR-002's 14 Oct scoring) | Must not run on the existing company server, which is very old. |
| B. Small Linux cloud VM in Sydney (ADR-002 Option B) | Not chosen (expected on 14 Oct) | New vendor and monthly bill. |
| E. Scheduled cloud container job | Not worth it for one maintainer | Most setup work. |
| F. External IT provider | Only if a contract already covers it | Ongoing fee; a third party sees PO data. |
| G. PO admin's own PC | Not used | See `docs/hosting-research.md`. |

**Moving off the Mac Mini later (to A or B) needs no code change:** point `state_dir` at the new host's disk, put the secrets in its store, add its scheduler (for example a systemd timer, `OnCalendar=Mon..Fri 07..17:07`, `Australia/Perth`), and keep the alert channel. Full comparison: `docs/specs/ADR-002-po-agent-hosting.md` and `docs/hosting-research.md`.

## Running cost

- **Claude API:** one schema-bound call per eligible PO (≤50 a week). Measure the actual tokens and AUD per PO during the trial; that number goes to the CEO (ADR action item 4).
- **Host:** the Mac Mini is already bought; about A$3/month for power (estimate); no hosting bill.
- **Compute:** one short headless run per hour, 11 runs per weekday (07:07–17:07).
- **Fallback:** `reader_mode = deterministic-only` removes the Claude cost entirely (see spec concern C4 for the address-reader gap).

## Reuse for the next automations

Keep the **MySys driver, action guard, run controller, state directory, output contract, decision-record format and two-reader agreement pattern** in shared subpackages (`core/`, `mysys/`), separate from the B1 rules (`b1/`). The next 4–6 automations add their own readers, rules and SOP steps on top.

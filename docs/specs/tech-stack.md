# Tech Stack — PO Agent

**Status:** Approved for build · v1.2, 14 Oct 2026 (1.2: trial host is an Anthropic cloud routine; secrets read from `PO_AGENT_*` env vars first; no state between runs on the trial routine; production most likely a Sydney cloud VM, not decided) · **Author:** Joey Wu, drafted with Claude
**Fixed by decision (ADR-001, approved by the CEO through the CEO decision brief, decision 1, recorded 13 Oct 2026):**

- hybrid architecture: a deterministic Playwright script does every click; a deterministic reader (pdfplumber + patterns + address normaliser/verifier) and Claude (no tools, schema-bound JSON) both read
- browser/UI only, with no MySys API or internal requests
- a deterministic-only reader mode reachable through config (in the MVP; until the rules-only address reader is built, it returns every PO to the admin).

Everything else is a recommendation. The reason is given for each, so the engineer can weigh a change. The MVP (`SPEC.md`) uses this stack unchanged.

## Recommended stack

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| Language | **Python 3.12+** | Team familiarity; strong PDF and browser libraries; fits Claude Code in VS Code; preinstalled with uv in Claude Code cloud environments. | TypeScript (Playwright's home language); fine, but less familiar to the owner. |
| Browser automation | **Playwright for Python**, Chromium; headless in production and in the routine, headed while developing | Auto-waits; selectors by accessible role and name; tracing and screenshots for debugging; Windows and Linux. | Selenium (weaker waits); Claude computer-use (**rejected by ADR-001**: fails gates G2/G3). |
| PDF text (deterministic) | **pdfplumber** (text layer only) | Gives the non-AI reading of issuer, "COMPACTION", PO number and internal number, and the text the address verifier searches. | OCR: **not used**. Image-only PDFs are skipped. |
| AI reader | **Claude through the Anthropic API**, official Python SDK. PDF sent as a document input with the Note text. Answer forced into the reading schema using the API's structured-output feature. **No tools defined.** | Reads layout-heavy PDFs well; schema-bound output can be validated by code; the model has nothing it can act on. | Regex only = Option A (kept as the fallback mode); a local model (more to run and maintain). |
| Model | **Pinned exact model ID in config.** Start with a mid-size (Sonnet-class) model. | Pinning stops silent behaviour changes. Any model change requires rerunning the decision-seam tests. | A smaller (Haiku-class) model to cut cost, but only after it passes the decision-seam tests. |
| Output validation | **pydantic** models for the reading schema, the log line and config | Rejects malformed or missing fields before they reach the decision engine. | Hand-written checks. |
| State | **Plain files in a state directory:** a skip-list JSON file (written atomically), daily JSON-lines log files, and a `STOP` file used as the kill switch. **MVP on the cloud routine: no state at all** (Joey, 14 Oct 2026): MySys is the state and the transcript is the log; the skip list, logs and `STOP` arrive with v1 on a host with a disk. | The only state the rules need is the skip list. The volume is tiny (about 5 MB of logs a year). | SQLite (more than this needs); a git state branch or external store for the routine (considered for the trial, not chosen). |
| Configuration | One **TOML profile per site** (`test`, later `live`). **No secrets.** | Same code on test and live; the differences in the intent's trial table are data. | Environment variables only (harder to review). |
| Secrets | Read at run time by one module: **environment variable `PO_AGENT_<NAME>` first, else `keyring`** (Windows Credential Manager on the laptop). Where the env var comes from depends on the host: the routine environment (trial waiver), or a root-only env file loaded by systemd on a Linux VM | One code path for every host. A headless Linux VM has no convenient keyring, so a root-only env file is the usual store there. Never named `ANTHROPIC_API_KEY`, so Claude Code can't pick it up. | `.env` file in the repo folder: **not acceptable** (credentials next to the code). |
| Scheduling | **Trial:** the cloud routine's schedule (cron `7 7-17 * * 1-5`, Perth). **Production:** OS scheduler (systemd timer or cron; Task Scheduler on Windows). The agent **also** checks the Perth window itself | Simple and observable. The self-check protects against a wrongly set trigger. | A long-running service (more ways to fail). |
| Time zone | `zoneinfo`, **Australia/Perth** (UTC+8, no daylight saving) | The schedule is defined in Perth time. | — |
| Logging | One JSON line per Note plus one summary line per run, in a daily file; deleted after 90 days; Playwright screenshot/trace **only on failure**. **Run output (stdout) is a short fixed contract** with no PDF text or addresses (`SPEC.md` → Code style) | Enough to explain any booking and to total coverage and cost for the CEO. The routine's Claude session reads stdout, so untrusted PDF text must never reach it. | Plain-text logs (hard to total); a database (more than needed). |
| Tests | **pytest** for seam 1 (decision seam, offline; stubbed and live-Claude modes); **pytest + Playwright** for seam 2 (run seam on the test site) | Matches the two agreed seams. | — |
| Tooling | git, **GitHub** (private repo; required by the routine), **uv** (locked dependencies), **ruff**, **gitleaks**, Claude Code in VS Code with **Addy Osmani's agent-skills**; **Playwright CLI** (`@playwright/cli`, Node.js) for mapping MySys screens, observe-only (Joey clicks) | Repeatable installs; pinned versions reduce supply-chain risk; one gated build flow. | pip + requirements.txt pinned with hashes (acceptable). |

## Component map

```
 Scheduler: cloud routine (trial) | systemd timer (VM)        Secrets: PO_AGENT_* env vars | keyring
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
 │  State: skip list · daily log · STOP  (host disk; none on routine)   │
 └──────────────────────────────────────────────────────────────────────┘
        │ browser only  ◄── seam 2                │ HTTPS: PDF + Note text only
        ▼                                         ▼
   MySys (test | live)                      Anthropic API
```

## Security baseline

These come from the intent, the ADR gates and the engineering security-review checklist (secrets, injection, authorisation).

- **Secrets:** loaded at run time only. Never logged, printed or screenshotted, and never in the repo or config. No browser session state saved to disk. Fresh login each run.
- **Least privilege:** the agent account can't delete. Ask the MySys admin to also remove Discard, Unlink, Cancel and Unassign rights if possible (spec concern C9). Give the Anthropic API key a monthly spend limit, use it only for this agent, and rotate it if exposed (and at the end of the cloud-routine trial).
- **Untrusted input:** PDF and Note text are data. Claude has no tools; its output is schema-validated; every value written is confirmed by the deterministic side and MySys. The email body written to the task comes from the deterministic reader and is typed as plain text. PDF text never appears in run output.
- **Code-enforced guard:** only the action guard may call click/fill/check/upload/evaluate. A build check enforces this.
- **Network:** the host needs outbound HTTPS to the MySys sites and `api.anthropic.com`, plus the alert channel. During setup and updates it also needs PyPI and Playwright's browser download. The routine environment allows only the test site plus those.
- **Data at rest:** logs (addresses, PO details) stay on the host (trial: no log files; the routine transcript holds the short run output, fake data only) and are deleted after `log_retention_days` (default 90, to be confirmed). PDFs aren't kept.
- **Dependencies:** a locked dependency file; update on purpose and rerun both seams after any update.
- **Trial exception:** on the cloud routine, the test-site password and the trial API key are readable by the routine's Claude session and by anyone using its environment (ADR-002 gate H2 waived for the trial only; mitigations in `SPEC.md` → Trial waiver).

## Hosting (trial decided; production is CEO decision 3, pending)

| Option | Fits | Watch-outs |
|---|---|---|
| L. Joey's laptop | Development; manual seam 2 runs | Sleeps and travels; one person. **Not for production.** |
| **C. Anthropic cloud routine running the script** (ADR-002 Option C) | **Trial (decided by Joey, 14 Oct 2026)** | Research preview; secrets readable by the session (H2 waived); fresh clone each run (the MVP keeps no state); Joey's personal account (H5 waived); outbound addresses may be blocked by MySys (tested in MVP slice M1); draws down plan usage. **Never for live.** |
| A. VM provided by IT (ADR-002 Option A) | Production; ranked first in ADR-002 (about A$0 extra) | Must not run on the existing company server, which is very old. Needs IT's lead time, patching, and a service account. |
| B. Small Linux cloud VM in Sydney, 2 GB (ADR-002 Option B) (Vultr, DigitalOcean or Lightsail, about A$16–19/month) | **Production, most likely** (Joey, 14 Oct 2026; not decided) | New account and billing on a company account with two admins; Joey patches the OS (automatic updates); test MySys access from the VM first, because cloud addresses may be blocked. |
| D. Office PC / mini PC left on (ADR-002 Option D) | If MySys blocks every cloud address | Power/internet outages, patching, no spare machine. |
| E. Scheduled cloud container job | Not worth it for one maintainer | Most setup work. |
| F. External IT provider | Only if a contract already covers it | Ongoing fee; a third party sees PO data. |
| G. PO admin's own PC | Superseded by C for the trial | See `docs/hosting-research.md`. |

**Moving from C to B (or A) needs no code change:** point `state_dir` at the VM's disk (skip list, logs and `STOP` come with v1), put the `PO_AGENT_*` secrets in a root-only env file, add a systemd timer (`OnCalendar=Mon..Fri 07..17:07`, `Australia/Perth`), and pick the alert channel. Full comparison: `docs/specs/ADR-002-po-agent-hosting.md` and `docs/hosting-research.md`.

## Running cost

- **Claude API:** one schema-bound call per eligible PO (≤50 a week). Measure the actual tokens and AUD per PO during the trial; that number goes to the CEO (ADR action item 4).
- **Trial host:** the routine draws down Joey's plan usage (11 short runs per weekday: cron `7 7-17 * * 1-5`); no hosting bill.
- **Production compute:** one short headless run per hour, 11 runs per weekday (07:07–17:07).
- **Fallback:** `reader_mode = deterministic-only` removes the Claude cost entirely (see spec concern C4 for the address-reader gap).

## Reuse for the next automations

Keep the **MySys driver, action guard, run controller, state directory, output contract, decision-record format and two-reader agreement pattern** in shared subpackages (`core/`, `mysys/`), separate from the B1 rules (`b1/`). The next 4–6 automations add their own readers, rules and SOP steps on top.

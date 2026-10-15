# ADR-002: Where the PO Agent runs (hosting)

**Status:** Split.
- **Trial host: Decided** (Joey, 14 Oct 2026): Option C, an Anthropic cloud routine running the script, on the test site only, with gates H2 and H5 **waived for the trial only**. See *Trial decision* below.
- **Production host: Proposed.** For CEO decision 3 (CEO decision brief), which hasn't been made. This ADR's scoring ranks a VM provided by IT in Perth first (Option A) and a Sydney cloud VM second (Option B). Joey expects **Option B, a Sydney cloud VM**, to be the most likely outcome.

**Date:** 14 Oct 2026 (proposed; trial amendment the same day)
**Deciders:** CEO (production decision owner); Joey Wu (author, maintainer; trial host)
**Inputs:** `docs/specs/ADR-001-po-agent-architecture.md` (Accepted), `docs/specs/spec.md` §8–§10, `docs/specs/tech-stack.md`, `docs/hosting-research.md`, `docs/decisions.md`, `SPEC.md`

## Context

ADR-001 is accepted (CEO decision 1, 13 Oct 2026): a deterministic script does every MySys click, and Claude only reads. This ADR decides only **where that script runs**: first for the test-site trial, then for live use.

What the host has to do:

- Run one short job every hour, 07:00–18:00 Perth time, Monday–Friday, when nobody's laptop is on. Each run takes a few minutes, for up to 50 POs a week.
- Run headless Chromium (Playwright) with Python 3.12. 2 GB RAM is the minimum, and 4 GB leaves room for the next 5–7 automations.
- Keep the MySys password and the Anthropic API key in a secret store.
- Keep state between runs: the skip list, the daily logs (90 days) and the `STOP` file (v1; the MVP trial keeps none).
- Reach `prompt.mysys.com.au`, `test-prompt.mysys.com.au`, `api.anthropic.com` and the alert channel over outbound HTTPS only.

Facts that shape the choice:

- The existing company server is **very old**. It won't be used, and a VM must not run on it.
- Anthropic **cloud routines** (Claude Code) were proposed as an alternative to a VM. Checked against Anthropic's docs on 14 Oct 2026, they:
  - are a research preview
  - run autonomously, with no approval step
  - start each run from a fresh clone, so nothing persists between runs
  - expose environment variables to anyone who uses the environment and to the session. "Network secrets" only attach API keys to request headers, can't fill a web login form, never apply to `api.anthropic.com`, and aren't available on Team or Enterprise plans
  - belong to one person's account and act as that person
  - draw down subscription usage
  - load the repository's `.claude/settings.json` hooks and permission rules in single-repo sessions
  - give each run a fresh Ubuntu 24.04 VM (about 4 vCPU, 16 GB RAM) with Python and uv preinstalled; Chromium is installed by a cached setup script.
- Options where Claude drives MySys (a cloud routine with a browser tool, or a Cowork task with Claude in Chrome) are out of scope. They are ADR-001's Option D, which failed gates G2 and G3.

## Trial decision (14 Oct 2026, Joey)

**Use Option C for the test-site trial and the MVP** (`SPEC.md`), to prove the agent works end to end before the CEO decides the production host, and without waiting for IT or a new cloud account.

- **Gates waived for the trial only:** **H2** (the test password and a dedicated trial API key are readable by the routine's session and environment users) and **H5** (the routine is in Joey's personal account). Scope of the waiver: the test-site agent account, a dedicated Anthropic key with a low spend limit, fake data only.
- **H3** isn't needed for the MVP: Joey chose to keep **no state between runs** (MySys is the state; each run's transcript is its log). The v1 skip list, logs and `STOP` need a host with a disk.
- **Mitigations:** no connectors on the routine; one repository; the routine prompt allows three fixed commands; repo hooks block the live site, printing environment variables and pushes to `main`; run output carries no PDF text; the key is rotated at the end of the trial. Details: `SPEC.md` → Trial waiver.
- **What would end the trial on Option C early:** MySys blocks or challenges the routine's outbound addresses (tested in MVP slice M1), or any sign that a secret has leaked beyond the environment.
- **This doesn't change the production assessment below.** Option C still fails H2 for live.

## Decision (production — proposed, for CEO decision 3)

Adopt **Option A: a VM provided by IT in Perth**, on reliable hardware (not the old server), **or Option B: a small Linux cloud VM in Sydney** on a company account with a second admin. Run the agent there with the OS scheduler, a root-only secret store, and state files on local disk. The code is the same on both.

- **Joey's expectation (14 Oct 2026):** Option B is the most likely outcome. It's within 0.40 of A on this ADR's scoring and doesn't depend on IT's lead time.
- **Fallback:** if MySys blocks or challenges cloud addresses, use **Option D, a dedicated office mini PC**.
- **Not chosen for production:** Option C, a cloud routine running the script. It fails gate H2.

## Evaluation method

### Gates (pass/fail)

| # | Gate |
|---|---|
| H1 | Runs the ADR-001 design unchanged: the script does every click, and Claude only reads |
| H2 | Credentials live in a secret store that neither the code repository nor any AI session can read (ADR-001 G6, strengthened because the agent reads untrusted PDFs) |
| H3 | State (skip list, logs, `STOP`) persists between runs without real PO data entering the code repository |
| H4 | Runs unattended on the Perth weekday schedule with nobody's laptop on |
| H5 | Owned by the company, with at least two people able to administer it |

### Criteria and weights

| # | Criterion | Weight | 1 | 3 | 5 |
|---|---|---|---|---|---|
| R | Reliability | 25 | Often misses runs (sleep, outages, preview changes) | Rare misses; single machine | Data-centre or IT-managed uptime |
| S | Security | 25 | Secrets readable by others or by an AI session; data on third-party infrastructure | Secrets in a root-only file; internet-facing host hardened by Joey | Inside the company network; IT-managed credential store and patching |
| E | Setup effort | 15 | More than 4 days | 2–3 days | About 1 day |
| M | Upkeep for one maintainer | 15 | Joey patches hardware and OS | Joey patches the OS (automatic updates) | IT patches; Joey updates the agent only |
| C | Running cost | 10 | Over A$50/month | A$10–50/month | Under A$10/month |
| U | Reuse for the next 5–7 automations | 10 | Each needs its own setup | Possible with workarounds | Same host and pattern, no extra cost |

Weights were set by Claude on Joey's behalf. Reliability and security dominate: the agent books real work, and a missed run only costs time (POs fall back to the admin), but a leaked password or a wrong booking costs more.

## Options considered

### Option A: VM provided by IT, in Perth

IT creates a VM, not on the old server: Ubuntu 24.04 LTS or Windows Server; 2 vCPU, 4 GB RAM, 40 GB disk; outbound HTTPS only; a non-admin service account. The agent runs from cron/systemd or Task Scheduler.

**Pros:** inside the company network; reaches MySys from the company's own internet address; IT patches and backs it up; no new vendor or bill.
**Cons:** depends on IT's lead time and spare capacity; reliability is only as good as IT's host hardware.

### Option B: small Linux cloud VM in Sydney (most likely for production)

1 vCPU, 2 GB RAM from Vultr, DigitalOcean or AWS Lightsail, on a company account with two admins. Automatic security updates, SSH by key only, no inbound ports except SSH (or provider console only). Secrets in a root-only env file read by the systemd service; a systemd timer (`OnCalendar=Mon..Fri 07..17:07`, `Australia/Perth`).

**Pros:** data-centre uptime; fixed address; data held in Australia; about 1 day to set up; independent of the office and of IT's lead time.
**Cons:** a new vendor and monthly bill; Joey owns OS hardening and patching; MySys might block cloud addresses (test first).

*A Perth-hosted cloud is possible.* AWS has a Perth Local Zone (`ap-southeast-2-per-1a`, parent region Sydney). It usually costs more and offers fewer small instance types, and the Perth–Sydney distance (about 50 ms) doesn't matter for an hourly job. Not needed.

### Option C: Anthropic cloud routine running the script (trial only; fails H2 for production)

A routine scheduled at :07 past each hour clones the repo, uses the environment's cached setup script for Chromium, and runs `uv run po-agent run --site test` (`docs/routine-setup.md`). In the MVP it keeps no state between runs.

**Pros:** no server to manage; no extra hosting bill; runs when laptops are off; available today.
**Cons:**
- **Fails H2:** the MySys password must sit in an environment variable that the session (an AI reading the script's output) and every user of the environment can read. Network secrets can't fill a web login form and aren't available on Team or Enterprise plans.
- **H3 needs a workaround:** runs start from a fresh clone, so the skip list, logs and `STOP` would need an external store, which is another place PO data lives. The MVP avoids this by keeping no state (trial only).
- **H5:** the routine belongs to Joey's personal account and acts as Joey.
- Research preview: behaviour and limits may change.
- Outbound traffic goes through Anthropic's proxy from undocumented addresses, which MySys might block.
- The 2-minute default command timeout needs raising (`BASH_DEFAULT_TIMEOUT_MS`).
- Each run draws down plan usage.

### Option D: dedicated office mini PC (fallback)

A small PC left on in the office, used only by the agent.

**Pros:** reaches MySys from the office internet address; cheap to run; no cloud vendor.
**Cons:** stops in office power or internet outages; Joey patches it; it must be physically secure; no spare machine.

*Out of scope here (see `docs/hosting-research.md`):* serverless container jobs (too much setup for one maintainer), GitHub Actions (late or dropped runs, shared addresses), an external IT provider (A$50–200+/month unless a contract already covers it), the existing old server, and the PO admin's PC (superseded by the cloud routine for the trial).

## Gates

| Gate | A: IT VM | B: Sydney VM | C: Cloud routine | D: Mini PC |
|---|---|---|---|---|
| H1 Runs ADR-001 unchanged | Pass | Pass | Pass | Pass |
| H2 Secrets unreadable by repo and AI | Pass | Pass | **Fail** (waived for the trial) | Pass |
| H3 State persists, no real data in repo | Pass | Pass | Only with an external store (the MVP keeps no state) | Pass |
| H4 Unattended, Perth schedule | Pass | Pass | Pass | Pass (office power permitting) |
| H5 Company-owned, two admins | Pass | Pass (company account) | **Doubtful** (personal account; waived for the trial) | Pass |

## Scores

| | A: IT VM (Perth) | B: Sydney VM | C: Cloud routine* | D: Mini PC |
|---|---|---|---|---|
| **R Reliability (25)** | **4**: IT-managed; depends on IT's host | **5**: data centre | **3**: research preview; may start late on the hour; tied to one account | **2**: office power, internet, accidental shutdown |
| **S Security (25)** | **5**: company network; IT patching; credential store | **4**: hardened internet host; root-only secrets | **1**: password readable by session and environment users; PO data in Anthropic's sandbox and a state store | **3**: physical access; Joey patches |
| **E Setup effort (15)** | **4**: about 1 day once IT delivers | **4**: about 1 day | **2**: 2–4 days (allowlist, Chromium setup script, timeouts; state store for v1) | **3**: purchase plus about 1 day |
| **M Upkeep (15)** | **5**: IT patches | **3**: Joey, with automatic updates | **3**: no OS, but preview changes and checking run transcripts | **2**: Joey patches hardware and OS |
| **C Running cost (10)** | **5**: about A$0 extra | **4**: about A$16–19/month | **4**: about A$0 hosting, plus plan usage | **4**: about A$3/month after purchase |
| **U Reuse (10)** | **5** | **5** | **3**: one routine each, same state workaround each time | **4** |
| **Weighted (out of 5)** | **4.60** | **4.20** | **2.45** | **2.80** |

*C fails gate H2 and is scored only for comparison. It's used for the trial under a waiver, not on its score.

## Estimated cost in Perth (AUD, including GST)

Exchange rate: RBA 1 USD = A$1.433 (12 Oct 2026); USD cloud prices plus 10% GST.

- **Verified:** the Sydney VM list prices (Vultr, DigitalOcean, Lightsail, read 13 Oct 2026), Claude API prices (platform.claude.com, 13 Oct 2026), and that the AWS Perth Local Zone exists.
- **Estimates:** the Perth IT labour rate, mini PC hardware price and WA electricity rate. Get local quotes before quoting these to anyone.

| Option | One-off | Hosting per month | Claude API per month | Joey's time | 3-year total (hosting + Claude) |
|---|---|---|---|---|---|
| **A: IT VM, Perth** | A$0 if IT is in-house. About A$300–700 if an external IT provider bills 2–4 hours at about A$150–180/h *(estimate)* | About A$0 extra if IT has capacity | A$1–9 | Setup about 1 day; about 1 h/month | **About A$40–330**, plus any IT setup charge |
| **B: Sydney cloud VM** | A$0 | A$16–19 (Linux 2 GB); about A$35 for Windows on Lightsail | A$1–9 | Setup about 1 day; about 1 h/month | **About A$610–1,010** |
| **C: Cloud routine** | A$0 | A$0 hosting; draws down plan usage | A$1–9 | Setup 2–4 days; transcript checks | **About A$40–330**, plus plan usage (trial: a few weeks only) |
| **D: Office mini PC, Perth** | A$400–900 hardware *(estimate)* | About A$3 for power: about 12 W all day ≈ 105 kWh/year at about A$0.30–0.35/kWh *(estimate)* | A$1–9 | Setup about 1 day plus purchase; about 2 h/month | **About A$540–1,330** |

Claude API range: Haiku 5.5 is under A$1/month, Sonnet 5.5 about A$8–9/month, for about 217 POs/month at 1–2 pages each. The trial measures the real figure (ADR-001 action item 4).

The largest real cost in every option is Joey's time, not hosting. Option A also moves patching to IT.

## Trade-off analysis

- **A beats B by 0.40**, on security (+1 × 25), upkeep (+2 × 15) and cost (+1 × 10), against reliability (−1 × 25).
- **What flips it to B:**
  - If IT's VM would sit on unreliable hardware (A's reliability falls to 2: 4.10 vs B's 4.20).
  - If IT can't deliver in time. Then B is the practical choice, and the agent can move to an IT VM later without code changes.
- **What would make C viable for production:** a secret store the session can't read that can fill a web login, plus built-in persistent state, plus company-owned routines. None of these exist today. Even then, C's security only rises to about 3 (weighted about 2.95), still behind A and B.
- **D only wins** if MySys blocks or challenges every cloud and data-centre address and IT has no VM. Its fixed office address is then the deciding advantage.

## Consequences

**Easier**
- The trial starts now, without waiting for IT or a new cloud account, and proves MySys accepts the agent from a cloud address.
- The code doesn't change between hosts. Moving from C to B (or A) needs only: secrets in a root-only env file, a systemd timer, `state_dir` on its disk, and the alert channel.
- On A or B, the next 5–7 automations reuse the same host at no extra cost.

**Harder**
- During the trial, the test password and trial key are readable by the routine's session and environment users (accepted, test site only).
- Joey checks routine transcripts during the trial; a green run status doesn't prove the run worked.
- Joey still owns the agent's own updates (Playwright and Chromium monthly, Python dependencies, and the routine's setup script version) and the alerts.

**To revisit**
- If Anthropic adds secrets usable in a web login, persistent state and organisation-owned routines, re-score Option C.
- If IT later moves to a cloud provider, host the agent there under IT's management.

## Action items

1. [x] Trial host decided: Option C with H2/H5 waived for the trial (Joey, 14 Oct 2026; `docs/decisions.md`).
2. [ ] MVP slice M1: create the routine (`docs/routine-setup.md`) and run the spike — a MySys test-site login from the routine to check the address isn't blocked.
3. [ ] CEO decides decision 3 (production) using this ADR. If accepted, set the production status to **Accepted** and record it in `docs/decisions.md`.
4. [ ] Before committing to a production host: a 10-minute MySys test-site login from that host.
5. [ ] If B is chosen: set it up on a company account with two admins (about 1 day). If A: send IT the VM request (requirements in Context; draft already prepared).
6. [ ] Get local quotes for anything marked *(estimate)* above if the CEO needs firm figures.
7. [ ] At the end of the trial: turn the routine off, delete its environment variables, revoke the trial key, ask for the test password to be changed.
8. [ ] Update `docs/specs/tech-stack.md` (Hosting) and `docs/specs/roadmap.md` phase 4 to match the accepted production option.

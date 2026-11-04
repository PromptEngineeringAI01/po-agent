# ADR-003: Booking for more clients than B1 Homes

**Status:** **Proposed** (4 Nov 2026). The direction for when a second client is real; nothing is built for it now. B1 Homes goes live first (`SPEC.md` -> Production).

**Date:** 4 Nov 2026
**Deciders:** Joey Wu (author, maintainer); the CEO for each new client's data (as decision 2 was for B1)
**Inputs:** `docs/specs/ADR-001-po-agent-architecture.md`, `SPEC.md`, `docs/decisions.md` (2 Nov 2026: no Claude reader), `src/po_agent/`

## Context

Joey plans to book compaction POs for two more clients after B1 Homes. Their rules aren't known yet, except one: for at least one of them, a Note is ours when its **PDF** says "COMPACTION TEST". The Note title doesn't say it.

How the code is split today (4 Nov 2026):

| Layer | What it holds | Client-specific? |
|---|---|---|
| `src/po_agent/mysys/` | the guard, the driver (reads and moves between windows), the booking steps W1-W5 | Mostly not. Exceptions: `booking.py` fixes `CREATOR = "Perth Scheduling"`, and `driver.py` imports `b1.decision` and `b1.models` |
| `src/po_agent/core/` | the run loop, run controls, output, errors, config | Not, except that `run.py` imports `b1` directly and config has a B1 `title_rule` |
| `src/po_agent/b1/` | the title rule (`/048`), the PDF rules, the address check, project match, the decision engine | Yes, by design |

So a new client is mostly a new rules package plus a small seam between `core`/`mysys` and that package. The large exception is eligibility.

**Eligibility is the hard part.** Today step 0 decides from the Note Pool list alone: the title matches `[B1 Homes] Order <no>/048`, the Project cell reads `---` and the Assignee is the pool. A Note that fails is never opened or assigned (SPEC: "a non-`/048` Note is left untouched"; task 5.2 proves it on the test site). A client whose POs are known only from the PDF breaks that: the agent has to open Notes, and download their PDFs, before it knows they are its own.

## Decision

1. **No multi-client code until a second client is real.** Build it when that client's real Notes and PDFs are in `private/` and its screens are mapped. A seam designed from one client guesses wrong (rule of three).
2. **Then, one rules package per client** (`src/po_agent/<client>/`, like `b1/`), behind one small interface that `core/run.py` and `mysys/driver.py` call instead of importing `b1`. The interface is extracted from B1 and the second client together, at that time. Expected parts: list-level eligibility, the PDF rules and readers, the address check, project match, the values the booker writes (Creator and anything else that differs), and the run output's client name.
3. **`mysys/` stays shared and client-free.** Every client books through the same guard and the same W1-W5 steps, so the guard, its allowlist and the read-backs stay one piece of code with one set of tests. Values that differ by client come in through the `Proceed`, never as constants in `mysys/`.
4. **PDF-based eligibility uses a read-only peek, then a take.** For a client known only from its PDF:
   - A list-level filter first, so the agent never reads every PDF in the pool. To find out at mapping time: can that client's Notes be told apart in the list (sender, title words, a pool)? If not, this client needs Joey's and the CEO's decision before any design.
   - Then **peek**: open the Note and download its PDF **without assigning it**, decide, and close. Only a Note that passes is taken (assigned to the agent) and then follows today's steps, from "Finding a Note again".
   - The peek needs its own dated decision and SPEC rule, because it replaces the "never opened" invariant with "opened read-only, never changed". Open question 8 showed on the test site that opening a Note or downloading its PDF changes nothing; it must be checked again on live before a peek touches live.
   - A Note that fails the peek is `untouched`: no assign, no Pending, no log line.
5. **No LLM framework.** The agent has no LLM at run time (decisions, 2 Nov 2026), so LangChain, LangGraph and Deep Agents have nothing to orchestrate, and LangSmith would send traces holding client data to an outside service (Must never #6). If a client's PDFs turn out too varied for code rules, the reader comes back as ADR-001 first designed it: the Anthropic SDK directly, schema-bound output, no tools, agreeing with a code reader.

## Options considered

| Option | For | Against |
|---|---|---|
| A. Generalise now, before a second client | Ready when the client comes | Built from one example; extra code to keep safe before go-live; delays B1 |
| B. Copy `b1/` and the run loop per client | Fast for client 2 | Two run loops and two bookers to keep safe; a guard fix lands in one copy only |
| **C. One rules package per client behind a seam, extracted when client 2 is real (chosen)** | One shared guard and booker; the seam fits two real clients | Some refactoring of `core/` and `mysys/` at that time |
| D. One LLM agent that reads any client's PDF | No per-client rules | Fails ADR-001's gates (a model deciding what to book); cost per PO; data leaves the Mac Mini |

## Consequences

- **Now:** nothing changes. B1 work continues; review flags new B1 constants placed in `mysys/` or `core/`, but nothing is refactored ahead of time.
- **Per new client**, the same path B1 took: map its Notes and PDFs (Joey clicks, Claude observes); a SPEC slice and plan; a doubt review; its readers as review-stop tasks with `false PROCEED: 0`; its own seam-1 fixtures and real-PO set in `private/`; trial Notes on the test site; a week of unattended test-site runs; its own go-live gates (the client's PO admin answers, CEO approval for its data).
- **Docs Joey changes when client 2 starts:** `CLAUDE.md` (the first line names B1 `/048`; Must never #6's trial-PO exception; the review-stop task list), `SPEC.md` (the "never opened" rule if a peek is adopted), `docs/workflow.md` (the phases).
- **Volume:** the run reads page 1 of the pool only (50 Notes) and stops at the run cap. With three clients, measure the minutes per PO in the P5 week and recheck the 20-minute limit and page-1 rule before client 2 goes live.

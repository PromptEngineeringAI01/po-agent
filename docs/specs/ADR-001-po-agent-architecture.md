# ADR-001: Architecture for the PO Agent (B1 Homes compaction pre-bookings)

**Status:** Accepted. Approved by the CEO through the CEO decision brief, decision 1 (recorded 13 Oct 2026), together with the safeguards and all action items below.
**Date:** 12 Oct 2026 (proposed) · 13 Oct 2026 (accepted) · 14 Oct 2026 (file paths updated; no change to the decision)
**Deciders:** CEO (decision owner); Joey Wu (author, builder)
**Inputs:** `docs/intent.md`, `docs/decisions.md`, `docs/specs/spec.md`, `docs/specs/tech-stack.md`

## Context

For every B1 Homes `/048` PO note in the MySys pool, an admin spends about 2 minutes:

- reading the PDF
- finding the project
- creating an on-hold Compaction Test task with the PO attached
- linking the note and resolving it.

That's 0–50 POs a week, and someone has to check the pool every working day. MySys is third-party and can only be used through its web pages. The intent sets these limits:

- Accuracy is the hard line: never the wrong project, the wrong PO number, or a task without its PDF.
- At least 80% of POs handled end to end.
- Hourly runs, weekdays only.
- Certain buttons may never be pressed.
- Email is read-only.
- Credentials are never kept in code or docs.

The intent already lists "hybrid" as the approach. This ADR tests that choice against alternatives instead of assuming it. For that reason "approach = hybrid" was **not** used as a gate.

## Decision

Adopt **Option B: Hybrid with two independent readers**.

- A deterministic Playwright script does every MySys click, through a list of allowed actions.
- The PDF and note are read twice: once by deterministic code (pdfplumber plus patterns and an address normaliser) and once by Claude. Claude has no tools, and its answer is forced into a fixed format.
- The script proceeds only when both readings agree with each other **and** with MySys. Anything else is a skip.

*Note (14 Oct 2026):* running this script from an Anthropic cloud routine for the trial (ADR-002) doesn't change this decision. The routine's own Claude session only starts the script; it doesn't read POs or drive MySys. Option D below stays rejected.

*Note (15 Oct 2026):* the trial and production now run on the office Mac Mini (ADR-002 Accepted, CEO decision 3). A shell script started by launchd runs the agent; no Claude session runs there. This decision is unchanged.

## Evaluation method

### Gates (pass/fail; failing any one removes the option)

| # | Gate |
|---|---|
| G1 | Works through the MySys web pages only; no calls to MySys's internal web requests or database |
| G2 | The off-limits controls (Discard, Unlink, Cancel, Unassign, removing a document, the related-task checkboxes in the Hold dialog) can never be pressed. This must be guaranteed by how the system is built, not just unlikely |
| G3 | Every check (client, COMPACTION, PO number, exact project match, address, duplicate) is guaranteed to finish before Create New Task opens. Any doubt means a skip |
| G4 | Email is read-only inside MySys; nothing is sent; "Send Email Notification" stays unticked |
| G5 | Runs unattended on the hourly weekday schedule |
| G6 | Credentials come from a secret store |
| G7 | PO data may be sent to Claude. **Passed:** fake POs (trial) and, since 14 Oct 2026, real client POs (Joey's decision; CEO to confirm as decision 2) |

### Criteria, weights and score anchors

| # | Criterion | Weight | 1 | 3 | 5 |
|---|---|---|---|---|---|
| C1 | Accuracy safety | 30 | One reader decides and its output goes into MySys unchecked | One reliable reader, with read-back after each write | Every value written to MySys comes from two independent readers that agree, and is read back afterwards |
| C2 | Handling messy real POs | 20 | Matches exact patterns only; below 60% coverage | Handles common variation; about 80% coverage | Handles layout and wording changes; above 90% coverage |
| C3 | Coping with MySys screen changes | 15 | Breaks silently or could click the wrong thing | Stops safely; a developer fixes the page references within about a day | Stops safely and copes with small changes without code edits |
| C4 | Running cost and speed | 5 | More than about A$50 a week, or minutes per PO | A$5–50 a week, under a minute per PO | Under about A$5 a week, seconds per PO |
| C5 | Effort to reach the 3-PO trial | 15 | More than 6 weeks | 2–4 weeks | Under 2 weeks |
| C6 | Audit and reuse | 15 | Hard to explain why it acted; nothing reusable | Logs what it did; some parts reusable | A per-note decision record with reasons, plus parts reusable by the next 4–6 automations |

Weights were set by Claude on Joey's behalf: accuracy is the hard line, volume is too low for cost to matter much, and this is the first of 5–7 MySys automations.

## Options Considered

### Option A: Deterministic script, no AI

Playwright does the clicks. pdfplumber, regular-expression patterns and a hand-built address normaliser do the reading. All checks are rule-based.

| Dimension | Assessment |
|---|---|
| Complexity | Low–Medium |
| Cost | Near zero to run |
| Scalability | Fine for ≤50 POs/week |
| Team familiarity | High (Python) |

**Pros:** predictable; when unsure it skips rather than acts; cheapest; nothing external to approve.
**Cons:** address wording that differs between the PDF and MySys has to be hand-coded; scanned PDFs can't be read; each later automation needs its own parsers.

### Option B: Hybrid with two independent readers (chosen)

Same script and the same deterministic reader as A, plus Claude reading the PDF and note into a fixed format. The script proceeds only if both readers agree and both match MySys.

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Cost | Roughly cents per PO in Claude calls (≤50 a week); measure in the trial |
| Scalability | Fine |
| Team familiarity | High (Python + Anthropic SDK) |

**Pros:** two readers must both be wrong in the same way before anything wrong is booked; clear audit trail; the reading layer can be reused.
**Cons:** two readers to build; because both must agree, coverage is capped by the weaker reader (see Trade-off Analysis).

### Option C: Deterministic first, Claude only as a fallback

Same script. The deterministic reader runs first, and Claude is called only when the parser can't extract a field or the address normaliser can't decide. In those cases Claude's reading, checked against MySys, decides on its own.

| Dimension | Assessment |
|---|---|
| Complexity | Medium (extra routing logic) |
| Cost | Lowest of the AI options |
| Scalability | Fine |
| Team familiarity | High |

**Pros:** best coverage of messy POs; Claude is rarely called.
**Cons:** the hardest POs, which are the risky ones, are decided by a single reader, and that weakens the accuracy hard line.

### Option D: Claude drives the browser itself (computer-use agent). **Dropped.**

- **Fails G2:** when Claude clicks by screen position or picks elements itself, avoiding the forbidden controls is likely but not guaranteed.
- **Fails G3:** the order of checks and writes is the model's choice, so "all checks before the first write" can't be guaranteed.

Making D pass would mean moving the clicking order and the button guard into code, at which point it becomes Option B.

*(Replaying MySys's internal web requests was not proposed, because it fails G1.)*

## Scores (one line of evidence each)

| | A: No AI | B: Hybrid, two readers | C: AI fallback |
|---|---|---|---|
| **C1 Accuracy (30)** | **4**: rules require exact matches and skip when unsure; PO number has 2–3 sources (PDF, file name, title); but the address has only one reader | **5**: every value written needs both readers to agree plus a MySys read-back; injection text in a PDF can't flip the deterministic reader | **3**: on fallback POs, Claude alone decides the address match, so one reader drives a write |
| **C2 Messy POs (20)** | **3**: B1 POs come from one template, so common cases parse, but address wording (e.g. "Lot 315 / Discover Way Yanchep WA" vs "Lot 315 Discover Way Yanchep 6035 WA") needs hand-built rules | **3**: Claude reads variation well, but the requirement for both readers to agree means the deterministic parser still limits coverage | **4**: Claude handles the cases the parser can't, so far fewer skips |
| **C3 Screen changes (15)** | **3**: same Playwright driver; stops on unexpected screens; a developer fixes page references | **3**: identical driver to A | **3**: identical driver to A |
| **C4 Cost/speed (5)** | **5**: no API cost; seconds per PO | **4**: one Claude call per PO, cents each, a few seconds of latency | **5**: Claude called only on fallback |
| **C5 Effort (15)** | **4**: one reader plus the driver; about 2–3 weeks | **3**: adds the Claude reader, the fixed answer format, agreement rules and tests; about 3–4 weeks | **3**: both readers plus the fallback routing |
| **C6 Audit/reuse (15)** | **4**: decision record with rule-based reasons; driver reusable; parsers specific to this PO | **5**: record shows both readings and why they agreed; driver and the reader-with-agreement pattern reusable for the next 4–6 automations | **4**: record shows which path decided; reusable, but with two decision paths to explain |
| **Weighted (out of 5)** | **3.70** | **3.95** | **3.45** |

## Trade-off Analysis

- **B beats A by 0.25.** B wins on accuracy (+1 × 30) and audit/reuse (+1 × 15), and loses on effort (−1 × 15) and cost (−1 × 5). The net is +25 weighted points.
- **Which weight change flips the winner to A:** A wins whenever *weight(C5) + weight(C4) > weight(C1) + weight(C6)*. For example, moving accuracy from 30 to 15 and effort from 15 to 30 gives 30 + 5 > 15 + 15, so A wins. Put simply, A wins if getting to the trial fast matters more than the extra safety of a second reader.
- **Which score change flips it:** if you believe one deterministic address reader is as safe as two (A's C1 at 5 instead of 4), A scores 4.00 against B's 3.95 and wins. The whole decision rests on whether a second, independent reader of the address makes it materially safer. With the accuracy hard line and untrusted PDF content (injection risk), this ADR judges that it does.
- **C needs extreme weights to win.** C beats B only when *weight(C2) + weight(C4) > 2 × weight(C1) + weight(C6)*, for example accuracy 10 and coverage 40. That would contradict the intent's "accuracy is the hard line".
- **B's weak spot is coverage.** Requiring agreement puts a coverage ceiling set by the deterministic parser. **Mitigation (action item 2):** don't make the deterministic side extract the address independently. Instead, have it **verify** Claude's extracted lot, street and suburb: each must appear in the PDF text and match the MySys project after normalisation. That keeps two independent checks while removing most parser-driven skips. It could lift B's coverage score to 4 (weighted 4.15).

## Consequences

**Easier**
- Defending the accuracy hard line to the CEO, because every booking has two agreeing readings and a read-back.
- The next 4–6 MySys automations, which can reuse the driver, the button guard, the run log and the reader-agreement pattern.

**Harder**
- There are two readers to maintain and test, plus a dependency on the Anthropic API (cost, pinned model ID, key management).
- Coverage depends on the deterministic side; watch it against the 80% target during the trial and the first live weeks.

**To revisit**
- After the trial, compare actual skip reasons. If skips come mostly from reader disagreement on correct POs, look at the deterministic patterns first.
- If Claude may not read real POs (CEO decision 2) or that approval changes later, build the rules-only address reader and run Option A. The design keeps A as a subset of B.
- If MySys ever offers an official API, only the driver changes.

## Action Items

1. [x] CEO accepts or rejects this ADR. **Accepted** through CEO decision brief decision 1 (recorded 13 Oct 2026). "Approach: hybrid" stays in `docs/intent.md`.
2. [x] Spec change: the deterministic address check **verifies** Claude's extracted lot, street and suburb against the PDF text and the project, rather than extracting independently. Written into `docs/specs/spec.md` §4.
3. [ ] Decision-seam tests: run the full fixture set through both readers. Measure agreement on the 3 trial PDFs and the mutated copies; any false PROCEED is a blocker. *(MVP slice M2.)*
4. [ ] Record Claude token cost per PO during the trial for the CEO (C4 evidence). *(MVP slice M6, then the trial.)*
5. [x] Keep Option A reachable through config (reader = deterministic-only). Approved with a deferred rules-only address reader: until it's built, that mode returns every PO to the admin. *(The config switch is in the MVP; the rules-only address reader stays deferred.)*

# Software factory handbook (from Lauren Tan's talks)

**Version:** v1 · 20 Nov 2026 · **Owner:** Joey Wu

What this is: the practices from three recordings of Lauren Tan (Cursor, then the Grokbot team at SpaceX AI), written down in our own words and mapped onto PO Agent. Use it as a checklist at the points `docs/workflow.md` names (Production build loop steps 6 and 9) and before any new automation. It adds no rule: `CLAUDE.md`, `SPEC.md` and `docs/decisions.md` still win.

Sources (transcripts read 20 Nov 2026 through a NotebookLM notebook; the notebook's own two summaries were checked against them and are not a source):

- A. "All Code Is Slop (Except Mine)" - Lauren Tan, conference talk, ~15 min ([video](https://www.youtube.com/watch?v=O_zcc6Xl12g)).
- B. "Lauren Tan workshop" - hour-long Q&A on trust, verification skills, evals, CI and token cost.
- C. "The Rise Of AI Coworkers" - Y Combinator Lightcone episode with Lauren Tan and Roman Ugarte ([video](https://www.youtube.com/watch?v=y1-9yeYLJUo)).

Her numbers, for scale (her own, not ours to copy): about 3,000 PRs in one month by one engineer, about 11,000 PRs a month for her team with a revert rate near 0.5%, six months of investment to get there, on an AI lab's unlimited token budget (A, B).

---

## 1. The idea in one paragraph

You can only hand work to agents as far as you trust them, and trust is earned by investing in the agent's environment, not by reading every line. The investment goes, in order of payoff: the codebase itself, then static checks, then verification, and only last prose (rules, skills, AGENTS.md). Every time you correct an agent, turn the correction into something deterministic so it never needs correcting again. When there is nothing left that you catch in review, review can shrink to looking at verification evidence (A, B).

## 2. The trust curve (where are we?)

| Stage | What it looks like | What limits you |
|---|---|---|
| 1. In the loop | One or two agents; you watch every output, test by hand, paste errors and screenshots back | You are the verifier |
| 2. Agents verify themselves | Agents run the code, read traces and logs, fix their own errors before you see the PR; skills encode your standards | Keeping skills and verification up to date |
| 3. Outer loop | Agents start from bug reports, releases and chat threads, open PRs and merge the ones that pass | Product judgment and goals |

Her advice: there is no shortcut, and do not jump straight to many cloud agents, or you burn tokens producing more slop (B). Start local, where you can watch the agent use the app (B).

**PO Agent today:** stage 2. Task sessions run checks and seams themselves, the advisor verifies and merges low and medium risk PRs, and the Mac Mini runs hourly from a tag Joey moves. Stage 3 (auto-merge of anything that writes to MySys) stays out of scope: MySys is a third party's production system, and Lauren herself keeps a human in the loop for infrastructure, databases and deployment (C).

## 3. The inverse pyramid: where to spend your time

Most effort goes to the top layers; the bottom one is thin on purpose (A, B, C).

| Layer | Strength | Her examples | PO Agent equivalent |
|---|---|---|---|
| 1. Codebase: API design, architecture, conventions | Hard | One directory per feature; main and renderer code kept apart | `mysys/guard.py` is the only place that clicks; `core/output.py` the only printer; readers and booker in fixed modules |
| 2. Static analysis and CI | Hard (CI goes red) | Lint bans, dependency-graph import checks, compiler | ruff (T10, T20), `scripts/guard_check.py`, `scripts/check.py`, hooks (`protect_paths`), gitleaks, `scripts/risk.py` |
| 3. Verification, runtime and formal | Empirical | Agents drive the app through Chrome DevTools, feature map, TLA+, Lean, property tests | Seam 1 (two readers agree, `false PROCEED: 0`), seam 2 on the test site, decide-only runs, hold re-check, heartbeat |
| 4. Prose | Soft (agents forget) | Rules, skills, AGENTS.md, review bots | `CLAUDE.md`, `SPEC.md`, skills, the Lessons line |

Rule of thumb from B: if a rule exists only as prose or as a human review comment, it is a matter of time before it is broken. Being "stuck in code review land", enforcing invariants by reading diffs, is the smell.

## 4. The correction ladder

Each time you (or a reviewer, or `/verify-pr`) correct an agent, walk down this list and stop at the first rung that works (A, B):

1. **Remove the problem by design.** Change the API or structure so the wrong thing cannot be written (her example: banning a footgun API outright, allowed only inside the framework).
2. **Make CI fail on it,** with an error message that tells the agent to fix the root cause, not to work around it. A lint, an import check, a test, a `check.py` step.
3. **Clean up the old occurrences** once the check exists, because agents copy whatever pattern is already in the codebase (A: "weeds" spread).
4. **Only then prose:** a skill line or a `CLAUDE.md` line, for things that need judgment.

Watch for the agent's escape hatches: a code comment or doc note that justifies a workaround, or a one-off correction it has turned into a permanent rule (A, B). Treat such a comment as a finding, not as documentation.

**In PO Agent:** layer 1 and 2 changes to the guard, hooks and CI are Joey's to merge (Must never 9), so a session proposes them as a patch; everything else under `scripts/` or `tests/` can go in the session's own PR.

## 5. Organic architecture

- **The shortest path should be the right path.** Agents take the quickest route to a passing task, so make the quickest route the correct one (B).
- **Keep a feature in one place,** so an agent working on it rarely needs to search the whole repo (B).
- **Use directory names to carry rules** that a checker can enforce (B).
- **Greenfield is the biggest risk.** A vibe-coded prototype has no guardrails and spirals; start with strict constraints (B).

**In PO Agent:** this is the lens for refactor task 8.1 and for the seam extracted when a second client is real (ADR-003): each move should make the next agent's shortest path the safe one.

## 6. Verification

- **The single most important skill** is letting the agent run the thing the way a user does and check it for itself. It does not make code good, but it makes code correct (B).
- **A feature map** tells the agent how to reach every screen from a cold start, the shared names for each part, and the selectors to use. Keep it current with a maintain step (B).
- **Wrap the driver in a small reusable CLI** so each run costs fewer tokens and the driver itself is testable (A).
- **Review shrinks to evidence:** videos, screenshots, diagrams, state charts (A).
- **Formal methods and property tests** found real bugs for her, but she calls them "not a silver bullet", one more layer (A).
- Much of her token budget now goes on verification rather than generation (A, citing another engineer's 70% figure and agreeing with it).

**In PO Agent:** `docs/screen-map.md` is our feature map; seam 2 and decide-only are our runtime verification; the PR's Testing section is the evidence. A Playwright session may only observe outside the guard (Must never 1), so "the agent drives the app" means through the guard's code paths on the test site, one run at a time.

## 7. Skills and their evals

- **Build skills from observed failures.** Read the agent's tool calls and thinking; where it guesses instead of reading the code, write a skill that makes it look first (her `how` skill) (B).
- **A skill is onboarding for a capable new hire with no business context** (B).
- **An eval is a unit test for a skill.** No framework is needed. Her playbook: a coordinator writes a rubric; sub-agents run the skill in separate folders named so they cannot tell they are being tested; a judge agent from a different model family scores them; repeat after every skill change (B).
- **Hill-climbing** (loop until the score is 10/10) is what she does with unlimited tokens (B). For us, a handful of fixed scenarios run once per skill change is enough.

## 8. Review: how much is enough

- **Push review effort up the pyramid.** The codebase is memory; a rule in a lint costs no tokens on the next PR, a rule in a reviewer's head costs tokens every time (C).
- **Adversarial multi-model review is still useful but can overfit:** the reviewer lacks your goals and plans and cannot tell good feedback from bad, so you end up polishing code you will throw away (C).
- **Stay in the loop for the sensitive parts** (infrastructure, databases, deployment); let well-constrained product code merge on its checks (C).
- **Small, atomic PRs.** Git history is context for the next agent, and a small PR is easy to revert (B).

**In PO Agent:** this is what risk-tiered review already does (`scripts/risk.py`; workflow step 6): high risk (MySys writes, guard, CI) keeps a second-model review and Joey's merge; low risk merges on `check.py` and `/verify-pr`. Triage "must-fix or overthinking" is our guard against overfitting.

## 9. The outer loop (later, if ever)

- **Release fuzzing:** on each release, an agent uses the build like a user, files minimal repros and opens fix PRs (A).
- **Bug-repro agent:** takes each report, reproduces it in a sandbox and says whether it is already fixed on `main` (B).
- **Bots get permissions like a new hire:** scoped to the role, inherited from the person they work with, widened as trust grows (C).
- **Don't automate an inner loop that still makes slop;** it only makes more (A).

**In PO Agent:** our outer loop is deliberately small: the hourly run, `ALERT` issues, the heartbeat and Healthchecks.io. The nearest useful step would be a session that takes an `ALERT` issue and reproduces it on the test site in decide-only; that needs the test-site queue (workflow step 10) and is not planned.

## 10. Not for us (one developer, one client)

| Practice | Why not now |
|---|---|
| Hundreds of cloud agents, Slack or X bots, specialist bot roster | One builder, one client; the cost and the review load outrun the gain |
| Auto-merging fixes into code that writes to MySys | Third-party production system; Must never 9 and the `production` tag keep Joey in the loop |
| TLA+ or Lean proofs | No concurrent multi-device state; seams and the address check cover our risk |
| Banning 99% of comments | Our risk is wrong MySys writes, not comment slop; flag justifying comments in review instead |
| Hill-climbing skills to 10/10 across models | Unlimited-token practice; a few fixed scenarios per change is enough |

## 11. Checklist

Use at the matching workflow step:

- [ ] **Correcting a session or triaging a review finding** (steps 6, 9): can it be rung 1 or 2 of the ladder (section 4)? If yes, note it as a follow-up task; if it touches guard, hooks or CI, as a patch for Joey.
- [ ] **A workaround comment in the diff** ("we do X because..."): ask what root cause it hides.
- [ ] **A new or changed skill:** write two or three scenarios it must handle and run them before relying on it (section 7).
- [ ] **A new screen or flow:** update `docs/screen-map.md` in the same task.
- [ ] **Before automating more** (wider auto-merge, a new unattended job): is the inner loop clean, with nothing we still catch only by reading diffs? (section 9)
- [ ] **Once per phase:** list the review findings that came back more than once and turn each into a check.

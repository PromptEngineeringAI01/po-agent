# PO Agent — Claude Code workflow (MVP build)

**Version:** v5.4 · 15 Oct 2026 · **Owner:** Joey Wu

**Approach:** Addy Osmani's agent-skills as the main workflow, phase by phase as in its greenfield tutorial (Define → Plan → Build → Verify → Review → Ship), plus one Matt Pocock skill, `improve-codebase-architecture`, used after the MVP. CLAUDE.md, hooks, one check command and CI on GitHub keep it safe. The MVP runs from an Anthropic cloud routine on the test site (`SPEC.md`).

**v5.4:** the GitHub CLI is already installed (portable zip in `C:\Users\JoeyWu\tools\gh\bin`, v2.102.0) and logged in as **PromptEngineeringAI01** with the scopes the workflow needs, so Stage 0 skips installing and logging in, and adds `gh auth setup-git`, an account check and a line for IT.

**v5.3:** the demo is repeatable (at least 3 times): `docs/demo-runbook.md` has the 10-minute reset, two ways to show it, and what to point out.

**What changed in v5.2:** the spec is approved; the test site is reset by **cancelling** tasks with your own account (Stage 6.1), and the test profile's duplicate check ignores Cancelled tasks; Pro plan noted; Node.js confirmed, so Playwright CLI is the path.

**v5.1:**

- **Screens are mapped with Playwright CLI** (`@playwright/cli`): you click, Claude Code takes the accessibility snapshot and screenshot of each screen and writes the screen map. No recording file to make, and the planned `po-agent capture` command is dropped. The classic recorder (`playwright codegen`) stays as the fallback (Stage 3, comparison table).
- **All 3 trial POs are named at every stage** (Stage 3A table, SPEC → Objective).
- **`improve-codebase-architecture` checked against Addy's skills** (below): it doesn't replace them; it's the better tool for one job, used in Stage 8.

**v5:**

- **A skills plan:** which of Addy's 24 skills to use at which stage, which to skip, and where Matt Pocock's `improve-codebase-architecture` fits (Stage 8).
- **The walkthrough uses the 3 trial POs only** (no 4th fake PO), plus a **test-site reset** step, because the agent can't book a PO that already has a task.
- Playwright recorder steps (now the fallback in Stage 3A).
- Earlier: real client data allowed on the laptop only (v4.2); MVP on a cloud routine with no state between runs (v4.1); Addy's skills replace Matt Pocock's as the main set (v4).

---

## The skills plan

**Why Addy's skills as the base:** they cover the whole lifecycle with a human checkpoint at each phase, the spec is already in their format (`SPEC.md`), and `/build` works test-first in small committed slices, which is what a safety-critical booking agent needs. Matt Pocock's set is strongest on requirements and TDD, which Addy's already covers, so installing both in full would give two skills for the same job competing to run. Only Pocock's architecture review adds something Addy's set doesn't have.

| Phase | Skill (command) | Use in this project | When |
|---|---|---|---|
| Meta | `using-agent-skills` | **Yes**, automatic | Routes each request to the right skill |
| Define | `spec-driven-development` (`/spec`) | **Done** (`SPEC.md`); again for every later change | Stage 4; Stage 8 |
| Define | `interview-me` | **Yes**, for open questions you're unsure about | Stage 4 |
| Define | `idea-refine` | Skip | The idea is settled |
| Plan | `planning-and-task-breakdown` (`/plan`) | **Yes** | Stage 4 |
| Build | `incremental-implementation` (`/build`) | **Yes**, every task | Stage 5 |
| Build | `test-driven-development` (`/test`) | **Yes**, every task (test first) | Stage 5 |
| Build | `context-engineering` | **Yes**: keeps `CLAUDE.md` true to the code | After M1; whenever CLAUDE.md drifts |
| Build | `source-driven-development` | **Yes**: Playwright, Anthropic SDK (structured output, model IDs) and pdfplumber change between versions; build from their docs, with citations | M1, M2, M4 |
| Build | `doubt-driven-development` | **Yes**: a fresh-context challenge of the risky decisions | The plan (Stage 4); before the first write (M4) |
| Build | `api-and-interface-design` | **Yes**: the guard's interface and the decision-seam contract | M1, M2 |
| Build | `frontend-ui-engineering` | Skip | No UI |
| Verify | `browser-testing-with-devtools` | **Skip for MySys** | It lets Claude Code drive the browser itself; we use Playwright CLI in observe-only mode instead, and Claude never clicks MySys |
| Verify | **Playwright CLI** (`@playwright/cli`, a tool, not a skill) | **Yes, observe only** | M0 screen mapping; later whenever a screen changes. Don't install its bundled skills: they teach Claude to click, which we deny |
| Verify | `debugging-and-error-recovery` | **Yes** | Any failure that isn't obvious |
| Review | `code-review-and-quality` (`/review`) | **Yes**, every PR | Stage 5 |
| Review | `security-and-hardening` | **Yes** | M1 (secrets, hooks), M4 (first write), before M6, before production |
| Review | `code-simplification` (`/code-simplify`) | **Yes**, once | After M6 |
| Review | `performance-optimization` (`/webperf`) | Skip | Web-page performance; not relevant |
| Ship | `git-workflow-and-versioning` | **Yes**, automatic | Branch per task, small commits |
| Ship | `ci-cd-and-automation` | **Yes** | M1 (CI) |
| Ship | `documentation-and-adrs` | **Yes** | Decision entries; ADR-003 when the production host is chosen |
| Ship | `observability-and-instrumentation` | Light | M5 (run output, alerts); v1 alerts |
| Ship | `shipping-and-launch` (`/ship`) | **Yes** | Before the MVP demo (M6); before production |
| Ship | `deprecation-and-migration` | Later | Moving from the cloud routine to the Sydney VM |
| Tutorial | Loop engineering (nightly self-fixing job) | **Skip** | An autonomous job changing booking code is too risky here |
| **Matt Pocock** | `improve-codebase-architecture` | **Yes, after the MVP** | Stage 8: before v1 and before automation #2, to shape the shared MySys package |

**Is Matt Pocock's `improve-codebase-architecture` more suitable than Addy's skills?** Not as a replacement, and not for the MVP:

| | Addy's skills | `improve-codebase-architecture` |
|---|---|---|
| What it's for | The whole build: spec → plan → test-first slices → review → ship | One job: survey an **existing** codebase for shallow modules, then grill you on one redesign |
| Closest Addy skills | — | `api-and-interface-design` (one interface at a time), `code-simplification` (one diff, behaviour unchanged). Neither surveys the whole codebase |
| Fit for the MVP (M0–M6) | **Yes**: it drives every step | **Low**: there's little code to survey until M6, and the module boundaries (guard, driver, readers, decision engine, booker) are already fixed by ADR-001 and `SPEC.md` |
| Fit for "one shared MySys package for 5–7 automations" | Partial | **High**: exactly the job it was built for |

So Addy's skills stay the workflow, and `improve-codebase-architecture` is used where it's the better tool: once after the MVP works, and again before automation #2 (Stage 8).

**Build pace (`/build` vs `/build auto`):**

| Slice | Pace | Why |
|---|---|---|
| M1 walking skeleton (guard, secrets, hooks) | `/build`, one task at a time, plan mode first | The guard and the hooks protect everything after |
| M2 decision seam | `/build auto` once M1's guardrails are merged | Offline, well specified, test-first |
| M3 decide-only | `/build`, one task at a time | First run that assigns and returns Notes |
| M4 first booking | `/build`, one task at a time, plan mode first, plus `doubt-driven-development` | First write to MySys |
| M5 MVP safety | `/build`, one task at a time | Stops, alerts, exit codes |
| M6 demo | By hand, with `/ship` | Your go/no-go |

---

## Decisions behind this workflow

| Question | Answer | Why |
|---|---|---|
| GitHub or local? | **Private GitHub repo.** Required: routines clone from GitHub. Get the OK from CEO/IT (no real client data and no credentials in it). | Routines, CI on every push, PRs for review. |
| Where's the plan? | `tasks/plan.md` and `tasks/todo.md`, written by `/plan`. | The skills' default; `/build` reads them. |
| Parallel agents / worktrees? | **No.** Tasks run in order. | Serial chain; easier to trust the guard. |
| Hooks? | **Yes, created in M1**, then changed only by Joey. They also run inside the cloud routine. | Must-never rules enforced in code, not advice. |
| Evals? | **The seam 1 fixture set is the eval suite**, plus the real-PO set on the laptop. Every bug adds a fixture. | Proves "zero false PROCEED". |
| Freeze point? | When `tasks/plan.md` is approved. After that, a behaviour change needs a dated `docs/decisions.md` entry plus `SPEC.md` and `tasks/plan.md` in the same commit. | Keeps the audit trail honest. |
| Where does work happen? | Claude Code in the VS Code terminal, in the repo folder. The cloud routine only runs the finished script. The claude.ai project keeps the CEO brief and doc copies. | |

## Source of truth per artifact

| Artifact | Source of truth | Copies |
|---|---|---|
| Spec, intent, decisions, ADRs, workflow, routine setup | **Repo** (`SPEC.md`, `docs/`) | claude.ai project copies, headed `Synced from <commit SHA>` |
| CEO decisions 1, 2, 3 | **CEO decision brief** in the claude.ai project | `docs/decisions.md` records date and outcome |
| Plan and tasks | `tasks/plan.md`, `tasks/todo.md` | — |
| Run output | Routine transcripts (trial); `logs/` on the laptop (git-ignored); the host's disk in v1 | Never in the repo or the claude.ai project |
| Real client data | `private/` on Joey's laptop (git-ignored) | Nowhere else |
| Credentials | Routine environment variables (trial waiver); keyring on the laptop; root-only env file on a VM | Nowhere else |

---

## How to use this runbook

- Do the stages in order. Each step has the exact command and a **✓** line saying what you should see.
- **PowerShell** boxes go into the VS Code terminal, one line at a time. Don't join commands with `&&` (Windows PowerShell 5 rejects it).
- **Claude Code** boxes are typed into Claude Code (start it with `claude`).
- Never paste a password or API key into Claude Code or any chat.

---

## Stage 0 — Install the tools (about 30 minutes)

```powershell
claude update
claude --version
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

If work security blocks that script: `winget install --id=astral-sh.uv -e`. Close and reopen the terminal, then:

```powershell
uv --version
uv python install 3.12
```

**GitHub CLI: already done.** You installed it yourself as the portable zip (`C:\Users\JoeyWu\tools\gh\bin\gh.exe`, v2.102.0) and it's logged in as **PromptEngineeringAI01** over HTTPS, with the token in Windows Credential Manager and the scopes `repo` (private repos, PRs), `workflow` (the CI file) and `read:org`. That's everything this workflow needs, so **don't** run `winget install GitHub.cli` or `gh auth login`. Just make git use the same login for pushes, and set your git identity:

```powershell
gh auth setup-git
gh auth status
git config --global user.name "Joey Wu"
git config --global user.email "joeyw@prompteng.com.au"
git config --global init.defaultBranch main
```

✓ `claude --version`, `uv --version`, `gh --version` work, and `gh auth status` still shows **PromptEngineeringAI01**, `Active account: true`.

**Which account owns the repo:** `gh repo create` in Stage 1 creates it under **PromptEngineeringAI01**. That's right if it's the company's account for this work. If the company has a GitHub *organisation* instead, create it there (Stage 1 shows how). Whichever you choose, connect **the same account** to claude.ai in `docs/routine-setup.md` section 1, or the cloud routine can't clone the repo.

**The zip version doesn't update itself.** To update later, download the new Windows zip from github.com/cli/cli/releases and replace the contents of `C:\Users\JoeyWu\tools\gh`. Not needed now.

**Get the OK:** one email to the CEO/IT: *"OK to keep the PO Agent code in a private GitHub repo (account PromptEngineeringAI01) and run the test-site trial from an Anthropic cloud routine? No real client data and no credentials go in it. To do this I've installed the GitHub CLI (portable version, in my user folder, no admin rights) and signed it in to that account."*

---

## Stage 1 — Open the folder and create the GitHub repo (about 20 minutes)

1. Unzip `po-agent.zip` **outside OneDrive**, e.g. `C:\Users\<you>\code\po-agent`. If you already have a `po-agent` folder, keep it aside; this zip replaces its docs and CLAUDE.md.
2. Open it:

   ```powershell
   cd C:\Users\<you>\code\po-agent
   code .
   ```

   ✓ VS Code opens. Accept the recommended extensions. Use **Terminal → New Terminal** from now on.

3. First commit and push:

   ```powershell
   git init
   git add .
   git commit -m "docs: MVP spec, v1 spec pack, ADRs, workflow, CLAUDE.md"
   gh repo create po-agent --private --source . --push
   gh repo view --web
   ```

   (For a company GitHub organisation instead: `gh repo create <org-name>/po-agent --private --source . --push`.)

   ✓ The repo page opens at `github.com/PromptEngineeringAI01/po-agent` (or your organisation) with a **Private** label and shows `SPEC.md`, `CLAUDE.md` and `docs/`.

---

## Stage 2 — Install the skills (about 10 minutes)

**2.1 Addy Osmani's agent-skills** (the main set), as a Claude Code plugin:

```powershell
claude plugin marketplace add addyosmani/agent-skills
claude plugin install agent-skills@addy-agent-skills
claude plugin list
```

✓ `agent-skills` listed as enabled. If the marketplace add fails with an SSH error: `git config --global url."https://github.com/".insteadOf git@github.com:` and try again. Inside Claude Code the same commands are `/plugin marketplace add …` and `/plugin install …`. Use the plugin **or** `npx skills add addyosmani/agent-skills`, not both (you'd get every skill twice).

**2.2 Remove the full Matt Pocock plugin** if you installed it earlier, so its `tdd`, `code-review` and `diagnosing-bugs` don't compete with Addy's equivalents:

```powershell
claude plugin uninstall mattpocock-skills@claude-plugins-official
```

You'll add just `improve-codebase-architecture` (and the three skills it needs) in Stage 8.

**2.3 Playwright CLI** (for mapping the screens in Stage 3; needs Node.js 18 or newer):

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

Close and reopen the terminal, then:

```powershell
node --version
npm install -g @playwright/cli@latest
playwright-cli --help
```

✓ `v20` or later, then the command list. **Don't run `playwright-cli install --skills`**: its skills teach Claude to click and type, which this project denies. Claude reads the four commands it may use from `CLAUDE.md`. The repo already has `.playwright/cli.config.json` (in-memory browser profile, live site blocked, output to `private/captures/test/`) and `.claude/settings.json` (Claude may only observe).

(If Node.js ever can't be used, the fallback recorder is in Stage 3A.)

**2.4 Test CLAUDE.md.** Start `claude` and ask:

```text
What are the must-never rules, what's the check command, and what's the active spec? Which agent-skills commands are available?
```

✓ All 9 rules, `uv run scripts/check.py`, `SPEC.md`, and `/spec`, `/plan`, `/build`, `/test`, `/review`, `/code-simplify`, `/ship`. Then `/exit`.

---

## Stage 3 — M0: map the screens and check the risky ones (about half a day)

**Why:** the driver finds every button by its role and accessible name, and Claude can only build it from what it can see. It needs **every screen and every state**, including the unhappy ones and the buttons the agent must never press.

**Do you have to record with Playwright?** No recording file is needed. What Claude needs is each screen's **accessibility tree** (every element's role and name, which checkboxes are ticked) plus a screenshot. With Playwright CLI you just click and Claude takes them itself. The options compared:

| Option | You do | Claude gets | Needs | Verdict |
|---|---|---|---|---|
| Screenshots + notes only | Click, screenshot, write notes | Pictures; it has to guess names, so they're confirmed later by trial and error | Nothing | Bare minimum |
| `playwright codegen` (the classic recorder, **already included** in Playwright for Python) | Click while it records | Python for the clicks you made; nothing about elements you didn't click; it records your password, which you then delete | Nothing extra | **Fallback** (no Node.js) |
| **Playwright CLI** (`@playwright/cli`, separate install) | Click in a browser window; say "next" | The **full accessibility tree of every screen**, including the forbidden buttons and dialog checkboxes, plus screenshots; Claude writes the screen map from them directly | Node.js; deny rules so Claude can't click (already in the repo) | **Chosen** |
| Playwright MCP | Same as CLI | Same, but the page is pushed into Claude's context on every step (more tokens) | MCP setup | Not needed |
| Our own `po-agent capture` (previous plan) | Click; press Enter | Same as CLI | Half a day of building in M1 | Dropped |
| Video | — | Nothing usable | — | No |
| HAR file, saved storage or cookies | — | The password and the session cookie | — | **Never** |

Everything goes first into `private/` (git-ignored, laptop only): live captures are real client data, and the test site may hold copies of real data. Create the folders once:

```powershell
mkdir private\captures\test, private\captures\live, private\pdfs, private\fixtures
```

### 3A. Test site: map the SOP with the 3 trial POs (Playwright CLI)

**How each trial PO is used:**

| Trial PO | Project | In the walkthrough |
|---|---|---|
| **2609017B** | pln_66935 | The **full SOP**, rows 01–14 (books it by hand, so reset afterwards) |
| **2609034B** | pln_66938 | Read-only rows 02, 05, 06, 07 (Note, PDF, project search, project page). Nothing assigned or booked |
| **2610002B** | pln_66940 | Read-only rows 02, 05, 06, 07. Nothing assigned or booked |

The read-only rows for the second and third POs show Claude how the Notes, PDFs and project addresses vary. Booking all three by hand would add nothing new and mean three resets.

**Reset afterwards.** Booking 2609017B by hand leaves a Compaction Test task on pln_66935. After the walkthrough, **cancel that task with your own account** (not the agent's) and place a fresh copy of the 2609017B Note in the Agent Pool (Stage 6.1). On the test profile the agent ignores Cancelled tasks in its duplicate check, so it can book 2609017B again later. In row 07, after cancelling, ask Claude to snapshot the project page once more so the screen map shows how a cancelled task looks.

**Steps:**

1. Start `claude` in the repo and paste:

   ```text
   We're mapping the MySys test site for docs/workflow.md Stage 3A. Run: playwright-cli open --headed "https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component" — then wait. I log in and do every click and every typed value myself. You only observe. Don't run anything until I say "logged in". Then, each time I give you a row (e.g. "row 03, 2609017B"), run playwright-cli snapshot --filename=NN-<po>-<name>.yml and playwright-cli screenshot --filename=NN-<po>-<name>.png, and tell me in one or two lines what matters for the agent: defaults, ticked checkboxes, the controls it will need, and any Discard/Unlink/Cancel/Unassign/Remove buttons on the screen (use find or generate-locator on those, never click). Use no other playwright-cli command unless I ask.
   ```

   ✓ A Chromium window opens on the MySys login page. Approve the `open` command if Claude Code asks.

2. **Log in** as the **agent account** in that window. Claude never sees what you type. Then type `logged in` in Claude Code.
3. **Go row by row** through the table below for 2609017B, then rows 02, 05, 06 and 07 for 2609034B and 2610002B. Do each step in the browser, then tell Claude the row. Add anything a snapshot can't show (waits, pop-ups, what changed after a click) as a sentence to Claude; ask it to keep `private/captures/test/notes.md`.
4. If Claude Code asks permission for any other `playwright-cli` command, say **no** unless you asked for it.
5. **Finish:** ask Claude to run `playwright-cli close`. ✓ `private/captures/test/` holds a `.yml` and a `.png` for every row, plus `notes.md`.

| NN | Screen or state | Look for especially |
|---|---|---|
| 01 | Project tab → Note Pool | Assigned Pool dropdown **open**; Locked filter; the list with the 3 trial Notes (and any non-`/048` Note) |
| 02 | The Note opened | Title, body, source, attachment list |
| 03 | Assign dropdown **open** | Every name offered: is the **Agent Pool** there? (→ C3) |
| 04 | After assigning to the agent | Where the assignee shows |
| 05 | Attachment download | What happens (new tab, file, prompt) |
| 06 | Projects search | The internal number (1 result); a made-up number (**0 results**); 2 results if you can find a case |
| 07 | Project page | How lot, street and suburb are shown; the task list and where PO numbers show |
| 08 | Create New Task, empty | **Send Email Notification default**; Creator dropdown **open**; the task-type list |
| 09 | Create New Task, filled | Before Submit: Creator, Compaction Test, PO Number, uploaded file, Note |
| 10 | After Submit | Where task type, PO number and the document show |
| 11 | Hold dialog | **Every related-task checkbox and whether it's ticked** (→ C1); the hold note typed |
| 12 | After Hold | How "On Hold" and the hold note show |
| 13 | Link to Project | The search, the result list, after selecting |
| 14 | Resolve | The button or dialog; how "resolved" shows; Send Email Notification here? |

**Fallback without Node.js: the classic recorder.** `uvx --from playwright playwright install chromium`, then `uvx --from playwright playwright codegen --target python -o private\captures\test\codegen-raw.py "<test-site URL>"`. A browser and the Playwright Inspector open; log in and do the same rows, taking a screenshot (Win+Shift+S) of each into `private\captures\test\NN-<po>-<name>.png`. For buttons you must not click, use **Pick locator** in the Inspector and hover. Close the browser to save, then **delete the username and password lines** from `codegen-raw.py`.

### 3B. Live site: view only, with the agent's account

Real client data, so it stays in `private/`. **Change nothing on live:** no Assign, no edits, no bookings. First check on the test site that just opening a Note or downloading its PDF doesn't change it (SPEC open question 8); if it does, capture live from the pool list only. Don't use Playwright CLI or the recorder on live; it's blocked in `.playwright/cli.config.json` too.

1. Log in to live in your normal browser. Screenshots to `private\captures\live\`: the PO Allocation Pool with the Locked filter; 3–4 real B1 Notes (title, body, attachments); one non-B1 or `/023` Note for contrast.
2. Save **10–20 recent real B1 PO PDFs** to `private\pdfs\` (mostly `/048`, a few other suffixes, and any odd ones you remember).
3. For each one, look up its project (view only) and fill one case in `private\fixtures\cases.toml`:

   ```toml
   [[case]]
   pdf = "2610123B_048_1.pdf"
   note_title = "[B1 Homes] Order 2610123B/048"
   note_body = "Please find attached Purchase Order / Quotation file 2610123B_048_1.pdf"
   lookup.project_matches = 1            # how many projects the internal number finds
   lookup.pln = "pln_00000"
   lookup.lot = "315"
   lookup.street = "Discover Way"
   lookup.suburb = "Yanchep"
   lookup.existing_compaction_po = []    # PO numbers of Compaction Test tasks already on the project
   expect = "PROCEED"                    # or "SKIP" when a person would need to look at it
   expect_reason = ""                    # e.g. "ADDRESS_MISMATCH" when expect = "SKIP"
   ```

### 3C. Checks to answer while you're there

| # | Check | Why |
|---|---|---|
| 3.1 | **C1:** Hold dialog, any related-task checkbox ticked by default? (row 11) | If yes, the agent can't safely put tasks on hold. CEO decision before M4. |
| 3.2 | **C3:** can a Note go back to the Agent Pool using **Assign** (not Unassign)? (row 03) | If only Unassign works, every skip breaks a rule. CEO decision before M3. |
| 3.3 | Which screens show **Send Email Notification**? | The agent must untick it everywhere. |
| 3.4 | **MFA or password expiry** on the agent account? | Unattended runs fail otherwise. Blocks M1. |
| 3.5 | Does opening a Note or downloading its PDF change anything? | Decides how live capture is done (3B). |
| 3.6 | How does a **cancelled** task look on the project page (status text, still listed or hidden)? Can an **On Hold** task be cancelled directly, or must it be released first? | The test profile's duplicate check must recognise it, and the reset steps depend on it (Stage 6.1 and `docs/demo-runbook.md`). |

### 3D. Turn it into the screen map

Before Claude Code reads real data: you're on a **Pro** plan, so turn off the model-training setting in your claude.ai privacy settings. Then start `claude`:

```text
Read everything in private/captures/ (snapshots, screenshots, notes.md, and codegen-raw.py if I used the fallback). Write docs/screen-map.md: one section per SOP screen in order, with each control's role and accessible name, what the agent must read back after each step, the defaults, and the differences between live and test. Use fake values only: no real names, addresses or PO numbers. Add dated entries to docs/decisions.md for checks 3.1–3.6. Don't copy any file from private/ into the repo.
```

Check the diff for real data and credentials. You may copy **test-site** screenshots into `docs/screen-map/` yourself once you've checked they show only your fake data. `/exit`, then commit on a branch and open a PR (Stage 5 steps 1, 8, 9).

✓ `docs/screen-map.md` merged; checks 3.1–3.6 have recorded answers; `private/` holds the captures, the real PDFs and `cases.toml`. If 3.1, 3.2 or 3.4 went the wrong way, stop and take it to the CEO first.

---

## Stage 4 — Define and plan (one session, about 1–2 hours)

**4.1 Check `SPEC.md` against the screen map.** The spec was approved on 15 Oct 2026 (v1.4). M0 may still change details (labels, C1, C3, how a cancelled task shows), so start `claude`:

```text
Read SPEC.md, CLAUDE.md, docs/screen-map.md, docs/specs/spec.md and docs/decisions.md. List anything in SPEC.md that the screen map contradicts, that is ambiguous, or that an engineer couldn't build from. Don't change files yet.
```

For any point you're unsure about: `Use the interview-me skill on <the point>.` Ask Claude to make the agreed edits to `SPEC.md` with a dated entry in `docs/decisions.md`, bump the version, and commit.

**4.2 Plan.** Press **Shift+Tab** until **plan mode on**, then:

```text
/plan SPEC.md — slices M1–M6 from "Expected slices" (M0 is done). Vertical slices, each with acceptance criteria, a verify step and the files it touches, no task over ~5 files. Mark each task "step" or "auto" using the build-pace table in docs/workflow.md. Write tasks/plan.md and tasks/todo.md and stop.
```

**4.3 Doubt the plan** in a **fresh session** (`/exit`, then `claude`):

```text
Use the doubt-driven-development skill on tasks/plan.md. Check every claim it makes about MySys against docs/screen-map.md and every safety claim against CLAUDE.md "Must never". Which step is riskiest, which must-never rule is most at risk, and could an engineer who has never seen this conversation build it from the plan alone?
```

Fix what it finds and repeat until the answer is "nothing".

**4.4 Freeze.** Approve, `/exit`, then commit `tasks/` (`plan: MVP plan and tasks`) and push. ✓ This is the freeze point.

---

## Stage 5 — Build each task (repeat for every task in `tasks/todo.md`)

1. **Branch** from up-to-date `main`:

   ```powershell
   git switch main
   git pull
   git switch -c m1-walking-skeleton
   ```

2. **Fresh session:** `claude`. One task per session (or one `/build auto` run for an "auto" group).
3. **Build.**
   - **"step" tasks** (M1, M3, M4, M5): press **Shift+Tab** to **plan mode on**, ask Claude to plan the task (files, tests, risks, which must-never rule is at stake), approve, then:

     ```text
     /build the next unchecked task in tasks/todo.md
     ```

   - **"auto" tasks** (M2, after M1 is merged): `/build auto` for the M2 tasks only. It still works test-first and commits each task, and pauses on failures or risky steps.
   - **M1:** add `Follow "Appendix A — M1 build notes" in docs/workflow.md.`
   - **M1, M2, M4** (Playwright, Anthropic SDK, pdfplumber): add `Use the source-driven-development skill: build from the current official docs for each library call and cite them.`
   - **M4** (first write to MySys): before building, in a fresh session, `Use the doubt-driven-development skill on the booker design in tasks/plan.md against docs/screen-map.md.`
4. **Test-first pause.** Claude shows a failing test and stops. If it tests what the task and spec say: `Test looks right. Commit it and continue.`
5. **Verify.** `/test` to run the suite. ✓ `check: all passed`. If readers, prompt or model changed: `false PROCEED: 0` from the live-Claude seam (and the real-PO seam on the laptop). If `mysys/` or the booker changed: seam 2 result on the test site (reset first, Stage 6.1).
6. **Debug** anything not obvious: `Use the debugging-and-error-recovery skill on this: <paste the error>`.
7. **Review:**

   ```text
   /review
   ```

   For M1, M4 and M5 PRs, also: `Use the security-and-hardening skill on this diff: secrets, untrusted PDF text, the guard and the hooks.` Then `Fix the Important findings.` if there are any.
8. **Push and open the PR:**

   ```text
   Tick the task in tasks/todo.md, push this branch and open a PR that links the SPEC.md slice it implements.
   ```

9. **You merge** (Claude is blocked): `gh pr view --web` → wait for the green **check** → read **Files changed** against the task and the 9 rules → **Squash and merge**.
10. **Lessons.** If Claude made the same mistake twice, add one line under **Lessons** in `CLAUDE.md`. `/exit`.

### Straight after M1 merges

**Store laptop secrets** (VS Code terminal, not Claude; each command hides what you type):

```powershell
git switch main
git pull
uv run keyring set po-agent anthropic_api_key
uv run keyring set po-agent mysys_test_username
uv run keyring set po-agent mysys_test_password
```

**Test the guardrails.** In a new `claude` session, the first four should be **blocked** and the last should **ask** you first:

```text
Edit .claude/settings.json and remove the hooks.
```

```text
Run curl https://prompt.mysys.com.au
```

```text
Run printenv
```

```text
Run git add private
```

```text
Change the expected result in one seam-1 fixture.
```

**Check CLAUDE.md matches the code:** `Use the context-engineering skill: does CLAUDE.md match how this repo now works? Propose only the changes needed.`

**Create the routine** and run the spike: follow `docs/routine-setup.md` sections 1–4. ✓ SPEC criterion S1.

**If a screen turns out different later** (a selector fails in a test-site run): repeat Stage 3A for just that screen with Playwright CLI and ask Claude to update `docs/screen-map.md`.

### When something goes sideways

- Session getting long: ask Claude to write a short handoff (what's done, what's next, open problems) into the PR description, `/exit`, start again.
- A routine run failed: open the run's transcript first; a green status doesn't mean the task worked.

---

## Stage 6 — Verify on the test site

**6.1 Reset the test site** (after the walkthrough, before M3, after every booking test, and before the M6 demo), with **your own account**, by hand. The agent never cancels anything.

- [ ] On pln_66935, pln_66938 and pln_66940: **cancel** every non-cancelled Compaction Test task with the trial PO numbers (2609017B/048, 2609034B/048, 2610002B/048).
- [ ] The 3 trial Notes (2609017B, 2609034B, 2610002B) are in the **Agent Pool**, unassigned, with their PDFs. Place fresh copies if earlier ones were resolved.
- [ ] Nothing is left assigned to the agent account.

**6.2 Seam 2 from the laptop:** `uv run pytest tests/seam2 -m testsite` (Claude may run it if you ask). ✓ All cases pass; reset again afterwards.

**6.3 From the routine:** **Run now** on the `decide-only` routine (M3), then on the main routine (M4, one PO). ✓ The transcript ends with `RUN_SUMMARY` and `"exit_code": 0`.

---

## Stage 7 — MVP demo (M6)

1. **Go/no-go checklist:** in Claude Code, `/ship` — `Prepare the go/no-go for the MVP demo on the test site: checklist against SPEC.md S1–S8, the rollback (routine off; enabled = false), and what to watch in the first run.` You decide go or no-go.
2. **Rehearse stopping:** set `enabled = false` in `config/test.toml` (PR, merge), press **Run now** and check it exits before login; set it back to `true`. Check the routine's on/off switch works.
3. **Reset** the test site (6.1). As B1 Homes, place the 3 trial Notes in the Agent Pool. Only the 3 trial POs are used; leave any non-`/048` Note that's already in the pool where it is.
4. **Turn the schedule on.** Don't touch anything until the next run has finished.
5. Check every pln and Note against `SPEC.md` S4. Then place **a fresh copy of the 2609034B Note** in the Agent Pool and let the next run happen: it must skip it as `DUPLICATE_TASK`, return it to the Agent Pool and change nothing else (S5). Check the controls work (S6).
6. **Repeat it (S8):** do the reset in `docs/demo-runbook.md` and run the demo again, at least 3 times in a row, without changing code or config. Try the laptop way (`--headed --slow-mo 500`) once, so you know which to use in front of your boss.
7. Total the cost per PO from the `NOTE` and `RUN_SUMMARY` lines in the run transcripts (S7), add the real-PO seam result (S3), and write a one-page MVP demo note for the CEO: what ran, where, the H2/H5 trial waiver, cost per PO, open concerns.

**Every later demo** (to your boss or the CEO): follow `docs/demo-runbook.md`.

---

## Stage 8 — After the MVP

1. **Simplify:** `/code-simplify` on the MVP code, one PR, behaviour unchanged (check, seam 1 and seam 2 must pass).
2. **Architecture review with Matt Pocock's `improve-codebase-architecture`** — once now (before v1 hardening), and again before automation #2, when the driver, guard, run controller and output contract become the shared MySys package (roadmap phase 6).
   - **Install only what it needs**, picking these four in the installer's list (choose Claude Code as the agent if it asks): `improve-codebase-architecture`, `codebase-design`, `grilling`, `domain-modeling`.

     ```powershell
     npx skills@latest add mattpocock/skills -a claude-code
     ```

   - **Run it** in a fresh session: `/improve-codebase-architecture`. Tell it: *ADRs live in `docs/specs/` as `ADR-NNN-<name>.md`; the glossary is in `docs/specs/README.md`; the must-never rules in CLAUDE.md and the action guard are fixed.* It writes an HTML report of "deepening" candidates (shallow modules to merge into deeper ones), then grills you on the one you pick.
   - Turn the chosen change into work the Addy way: `/spec` (a short change spec) → `/plan` → `/build`.
   - **Remove the four skills afterwards** (the installer's remove command, or delete their folders from your user skills folder) so `grilling` and `domain-modeling` don't compete with Addy's skills day to day.
3. **v1 hardening** (roadmap phase 2): for each change, `/spec` on a new `intent/<change>/` folder, then Stages 4–5. Use `observability-and-instrumentation` for the v1 alerts and logs.
4. **Production host** (roadmap phase 4, once the CEO decides; most likely the Sydney VM): `documentation-and-adrs` for ADR-003, `deprecation-and-migration` for moving off the cloud routine, `/ship` plus `engineering:deploy-checklist` in Cowork.

---

## Appendix A — M1 build notes (Claude follows these in M1)

**Check command:** `uv run scripts/check.py` runs, in order, and stops non-zero on the first failure; on success it prints `check: all passed`:

1. `ruff format --check .`
2. `ruff check .`
3. `python scripts/guard_check.py` (no browser action calls outside `src/po_agent/mysys/guard.py`)
4. `pytest tests -m "not live_claude and not testsite and not real_data"`

**Secrets:** `src/po_agent/core/secrets.py` reads `PO_AGENT_<NAME>` from the environment, else keyring service `po-agent`. Names: `anthropic_api_key`, `mysys_test_username`, `mysys_test_password`. Never `ANTHROPIC_API_KEY`.

**CI:** `.github/workflows/check.yml`, no secrets:

```yaml
name: check
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run scripts/check.py
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**`.claude/settings.json`** already exists from M0 with the Playwright CLI rules. Write the hook scripts first, then **extend** this file last (keep its existing allow and deny rules; once the hooks are in, they stop Claude editing `.claude/**`). Merged shape:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run scripts/check.py)", "Bash(uv run pytest *)", "Bash(uv run ruff *)", "Bash(uv sync --locked)",
      "Bash(uv run po-agent *)",
      "Bash(git status)", "Bash(git diff *)", "Bash(git log *)", "Bash(git add *)", "Bash(git commit *)"
    ],
    "deny": [
      "Read(./.env*)", "Read(./secrets/**)", "Read(./config/live*.toml)", "Read(./state/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_paths.py\"" }] },
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard_bash.py\"" }] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "uv run --project \"$CLAUDE_PROJECT_DIR\" python \"$CLAUDE_PROJECT_DIR/.claude/hooks/format_python.py\"" }] }
    ]
  }
}
```

Keep the Playwright CLI `allow` and `deny` entries that are already in the file alongside the ones above.

| Hook | Does |
|---|---|
| `protect_paths.py` | **Blocks** edits to `.claude/**`, `config/live*.toml`, `.env*`, `secrets/**`, `state/**` and paths outside the repo. **Asks** before edits to `.github/workflows/**`, `docs/routine-setup.md`, and existing files in `tests/seam1/fixtures/**` or expected results. |
| `guard_bash.py` | **Blocks** commands mentioning the live site (regex `(?<!test-)prompt\.mysys\.com\.au`); any `playwright-cli` command except `open` (test URL only, no `--persistent`/`--profile`), `snapshot`, `screenshot`, `find`, `generate-locator`, `tab-list`, `list`, `close`; `printenv`, a bare `env`, `/proc/*/environ`, or any text containing `PO_AGENT_`; `git push --force`; any push to `main`; `gh pr merge`; `rm -rf`; `git add`/`commit` of `private/`, `state/`, `logs/`, `.env*`; text matching a real Anthropic key (regex `sk-ant-[A-Za-z0-9_-]{20,}`). |
| `format_python.py` | For `.py` files: `ruff format` then `ruff check --fix` on that file; reports leftover lint errors. |
| pre-commit + gitleaks | Secret scan on every commit, including Joey's own; also blocks any staged path under `private/` and any `.pdf` outside `tests/seam1/fixtures/pdfs/`. The same path rule runs in `scripts/check.py`, so CI catches it too. |

Rules for all hooks: read the tool call as JSON on stdin; exit 2 to block, with stderr saying what was blocked, why, and that Joey does it by hand; to ask, print `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "..."}}` and exit 0; keep them fast. They run in the cloud routine too (single-repo sessions load the repo's `.claude/settings.json`).

---


## Appendix B — Troubleshooting

| Problem | Fix |
|---|---|
| `uv` / `gh` "not recognized" | Close and reopen the terminal / VS Code. For `gh` (portable zip), check `C:\Users\JoeyWu\tools\gh\bin` is in your user PATH: Settings → System → About → Advanced system settings → Environment Variables. |
| `git push` asks for a password, or fails with 403 | Run `gh auth setup-git`, then push again. |
| Push refused with `GH007` (private email) | GitHub is hiding your email. Use the noreply address from GitHub → Settings → Emails: `git config --global user.email "<id>+PromptEngineeringAI01@users.noreply.github.com"`, then `git commit --amend --reset-author --no-edit` and push again. |
| `&&` "is not a valid statement separator" | Run the commands on separate lines. |
| `/plan`, `/build` not listed | `/reload-plugins`, or `/exit` and start `claude` again. Check `claude plugin list`. |
| Every skill appears twice | You installed agent-skills both as a plugin and with `npx skills`. Remove one. |
| `playwright-cli` "not recognized" | Close and reopen the terminal after installing Node.js; check `npm install -g @playwright/cli@latest` finished. |
| `playwright-cli open` says the browser is missing | Follow the install command it prints, then open again. |
| Claude asks to run `playwright-cli click` (or similar) | Say no. Claude only observes; you do the clicking. |
| The fallback recorder (`codegen`) says the browser is missing | `uvx --from playwright playwright install chromium`, then start it again. |
| A trial PO is skipped as `DUPLICATE_TASK` | A task from the walkthrough or an earlier run is still on its pln. Reset the test site (Stage 6.1). |
| A hook blocks something you really want | Do it yourself by hand; that's the point of the hook. |
| Claude says "done" without showing check output | *"Run uv run scripts/check.py and paste the output."* If it repeats, add a Lessons line. |
| Routine setup log shows `403 host_not_allowed` | Add that host to the environment's allowed domains (never the live site). |
| Routine step times out at 2 minutes | `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` missing from the environment variables. |
| Routine can't log in to MySys | Check the spike output; if MySys blocks the cloud address, record it in `docs/decisions.md` and run the trial from the laptop or the VM instead. |

## Appendix C — Skills cheat sheet

| When | Type |
|---|---|
| Not sure which skill | `Use the using-agent-skills skill to pick one.` |
| An open question you can't answer yet | `Use the interview-me skill on …` |
| A change to what the agent does | `/spec` (new `intent/<change>/` folder) |
| Spec → plan and tasks | `/plan` |
| Challenge a plan or a risky design in a fresh session | `Use the doubt-driven-development skill on …` |
| Build the next task (test-first, small commits) | `/build` (or `/build auto` for "auto" tasks) |
| Library calls (Playwright, Anthropic SDK, pdfplumber) | `Use the source-driven-development skill …` |
| Map or re-check a MySys screen | Playwright CLI: you click, Claude runs `snapshot` / `screenshot` (Stage 3A) |
| Run and prove it | `/test` |
| Something fails and it isn't obvious | `Use the debugging-and-error-recovery skill on …` |
| Before every PR | `/review` (+ `security-and-hardening` for M1, M4, M5) |
| CLAUDE.md out of date | `Use the context-engineering skill …` |
| After the MVP works | `/code-simplify` |
| Before automation #2 / before v1 | Matt Pocock's `/improve-codebase-architecture` (Stage 8) |
| Before the MVP demo and before production | `/ship` (+ `engineering:deploy-checklist` in Cowork for production) |
| A hosting or design decision to record | `Use the documentation-and-adrs skill` (ADRs in `docs/specs/`) |
| Skip | `/webperf`, `frontend-ui-engineering`, `browser-testing-with-devtools`, `idea-refine`, loop engineering, parallel worktrees |

## Sources

- Addy Osmani's agent-skills: [greenfield tutorial](https://skills.addy.ie/tutorials/new-app/), [brownfield tutorial](https://skills.addy.ie/tutorials/existing-app/), [skills catalogue](https://skills.addy.ie/skills/), [getting started](https://skills.addy.ie/docs/getting-started/), [comparison with Superpowers and Matt Pocock's skills](https://skills.addy.ie/compare/), [repo](https://github.com/addyosmani/agent-skills) (read 14 Oct 2026)
- Matt Pocock's skills: [repo](https://github.com/mattpocock/skills), [improve-codebase-architecture](https://github.com/mattpocock/skills/blob/main/skills/engineering/improve-codebase-architecture/SKILL.md) (read 14 Oct 2026)
- [Claude Code — routines](https://code.claude.com/docs/en/routines) · [cloud environments](https://code.claude.com/docs/en/cloud-environments) (read 14 Oct 2026)
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
